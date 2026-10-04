# -*- coding: utf-8 -*-
"""Gera as imagens das cenas no PicassoIA.

Reusa o cliente do `random_builds` inteiro — browser furtivo (patchright +
Chrome real), login persistente no MESMO perfil (uma conta, um login) e a
prova de origem que a conta compartilhada exige. O que muda aqui e so o
laco: em vez de tres slots de uma build, sao N cenas de uma historia.

Tres regras que vieram de bug real no outro projeto e valem igual aqui:

  - TRAVA COMPARTILHADA. Os dois projetos abrem o mesmo `user_data_dir`.
    Dois processos no mesmo perfil = Chrome recusando abrir. A trava e a
    mesma (`queue.instancia_unica`), entao um espera o outro.
  - PROVA DE ORIGEM. A imagem so vira cena se o historico do site mostrar o
    NOSSO prompt. Sem prova, nada e baixado e a cena fica pendente.
  - INTERRUPTOR. Se a pipeline estiver pausada (o Adrian usando a conta), o
    worker nem abre o browser.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

# O pacote `ias` (correio, carteiro, rodizio) mora na RAIZ do repositorio e nao
# e instalado: rodando de `historias/` (main.py auto) ele nao era achado, e toda
# passada de imagens morreu com "No module named 'ias'" em 04/10/2026 -- os
# testes passavam porque o pytest roda da raiz.
_RAIZ_DO_REPO = str(Path(__file__).resolve().parents[3])
if _RAIZ_DO_REPO not in sys.path:
    sys.path.append(_RAIZ_DO_REPO)

from builds.identity import browser as _rb_identity_browser
from builds.identity import client as _rb_identity_client
from builds.identity import config as _rb_identity_config
from builds.identity import picasso_client as _rb_identity_picasso_client
from builds.identity import session as _rb_identity_session
from builds.identity import controle as _rb_identity_controle
from builds.identity import moderacao as _rb_identity_moderacao
from builds.identity import provedores as _rb_identity_provedores
from builds.identity import proveniencia as _rb_identity_proveniencia
import builds.atividade as _rb_atividade
import builds.travas as _rb_travas
from . import composicao, cota, fila

RAIZ = Path(__file__).resolve().parents[2]


def _com_reescrita(degraus, reescritor, ultima_recusa, maximo, log, rotulo):
    """Escalada com o LLM ENTRE o original e a suavizacao mecanica.

    Rende `(rotulo_do_nivel, prompt, mudancas)`. O rotulo e texto de
    proposito: "llm 1" e "2" contam historias diferentes no log e no
    `imagens.json` — e importa saber qual dos dois salvou a cena.

    O LLM so entra DEPOIS de uma recusa de verdade (`ultima_recusa()` deixa
    de ser None): reescrever antes de o site reclamar seria pagar o custo do
    navegador por adivinhacao.
    """
    degraus = list(degraus)
    if not degraus:
        return
    nivel, prompt, mudancas = degraus[0]
    yield (nivel or 0, prompt, mudancas)

    if reescritor is not None:
        atual = prompt
        # Garantir que maximo e sempre um inteiro, mesmo se foi passado como
        # string de um estado corrupto (ex: "llm 1" ao inves de 2). Tira apenas
        # o numero da string se houver, senao usa 0.
        try:
            maximo_int = int(maximo)
        except (ValueError, TypeError):
            # Se maximo e string como "llm 1", extrai o numero ou usa 0
            match = re.search(r'\d+', str(maximo or 0))
            maximo_int = int(match.group()) if match else 0
        for volta in range(max(0, maximo_int)):
            motivo = ultima_recusa()
            if not motivo:
                break        # nao foi recusa: nao ha o que reescrever
            novo = reescritor.reescrever(atual, motivo, primeira=volta == 0)
            if not novo:
                break
            log(f"[imagens] {rotulo}: prompt reescrito pelo "
                f"{reescritor.provedor} -> {novo[:110]}")
            atual = novo
            yield (f"llm {volta + 1}", novo, ["reescrito pelo LLM"])

    for nivel, tentativa, mudancas in degraus[1:]:
        yield (nivel, tentativa, mudancas)


def _gerar_esperando(cliente, prompt: str, config: dict, ajustes: dict,
                     log, rotulo: str) -> tuple:
    """Manda o prompt e espera a imagem. Estouro de espera TENTA DE NOVO.

    Medido no dia 08/09/2026, 87 envios: imagem que da certo volta em 9 a 42
    segundos — a maioria nem chega a imprimir o primeiro "gerando...", que so
    sai aos 20 s. Quando falha, nao demora: NUNCA VOLTA. Fica os 600 s
    inteiros e estoura.

    E isso era tratado como fim da cena. `EsperaEstourou` caia no `except
    Exception` generico, que registrava o erro e saia do laco de escalada —
    sem nenhuma nova tentativa. O resultado no disco:

        historia_00010  p01_cena_01 estourou as 10:12, as 12:10 e as 15:10,
                        em tres disparos seguidos, e ficou PRONTA as 15:35 —
                        o mesmo prompt, numa tentativa a mais.
        historia_00011  81 de 84 imagens; faltaram a cena 1 da parte 1 (o
                        gancho) e a ultima da parte 6 (o CTA), e por isso
                        duas das seis partes nao viraram video.

    Reenviar o MESMO texto e o certo aqui, e e o oposto do que se faz com
    recusa: recusa e sobre o conteudo (reenviar identico seria recusado de
    novo, por definicao), estouro e sobre o site. Suavizar por causa de um
    timeout pioraria a imagem para consertar o que nao era problema dela.
    """
    from builds.identity.client import BrowserMorreu, EsperaEstourou

    espera = int(ajustes.get("render_timeout", 150))
    tentativas = max(1, int(config.get("tentativas_por_espera", 3)))
    for volta in range(1, tentativas + 1):
        # O TETO DO DIA E CONFERIDO A CADA ENVIO, e nao so ao abrir: e aqui
        # que um laco (reenvio, refeita, recusa em cadeia) gastaria a conta
        # compartilhada. Conta ANTES de enviar: envio que o site recebeu e
        # imagem gerada do lado dele, aproveitada ou nao.
        _conferir_cota(config)
        cota.contar()
        antes = cliente.submit_prompt(
            prompt, aspect=str(config.get("aspect", "9:16")))
        try:
            return cliente.wait_for_render(antes=antes), antes
        except BrowserMorreu:
            raise                       # aba fechada nao se resolve tentando
        except EsperaEstourou:
            if volta >= tentativas:
                raise
            log(f"[imagens] {rotulo}: nada voltou em {espera}s "
                f"(tentativa {volta}/{tentativas}). Mandando de novo — "
                "imagem boa volta em menos de 45s, entao isto e o site, "
                "nao o prompt.")
            time.sleep(float(ajustes.get("min_interval", 8)))
    raise AssertionError("inalcancavel")


# Quantas vezes mandar o MESMO prompt quando a imagem volta em
# painel. Duas refeitas: mais do que isso gasta a conta
# compartilhada atras de um desenho que o modelo insiste em errar,
# e uma colagem no ar ainda e melhor do que cena sem imagem.
TENTATIVAS_DE_COMPOSICAO = 3

# EXPERIMENTO SEM MEDIDA (17/09/2026). A partir da SEGUNDA refeita, o prompt
# ganha um enquadramento que quebra a simetria. O motivo: na historia_00018
# p04_cena_03 ("as duas face a face") as tres tentativas com o MESMO texto
# voltaram com a mesma calha em ~49%, e nao ha no acervo nenhum caso de
# refeita por colagem que tenha dado certo para comparar. Varridas as 1336
# imagens do disco, colagem e 3% no total, mas 0,17% nas historias novas
# (1 em 588): o gatilho antigo — duas descricoes fisicas completas no mesmo
# prompt, 14,8% — ja foi consertado em 14-15/09.
#
# ENTAO ISTO E HIPOTESE, e nao conclusao. Cada refeita fica registrada em
# `imagens.json` ("refeita": voltas/variacao/colagem_no_fim) e no diario,
# para decidir com dado daqui a um mes se fica ou sai.
VARIACAO_DA_REFEITA = ("over-the-shoulder framing, one camera, "
                       "one continuous photograph")


def variar_enquadramento(prompt: str) -> str:
    """O mesmo pedido, com um enquadramento que nao cabe em dois paineis."""
    texto = str(prompt or "").strip()
    if not texto or VARIACAO_DA_REFEITA in texto:
        return texto
    return f"{texto.rstrip('.')}, {VARIACAO_DA_REFEITA}"


class NaoRodou(RuntimeError):
    """Motivo humano para a passada nao ter acontecido (trava, pausa, login)."""


class TetoDoDia(NaoRodou, cota.TetoDoDia):
    """O teto diario de envios ao PicassoIA bateu (`cota`, 30/09/2026).

    E `NaoRodou` de proposito: para o reparo, isto e "a maquina nao podia
    agora" (adiado, sem gastar tentativa do video), e nao falha do video.
    """


def _conferir_cota(config: dict) -> None:
    """Levanta `TetoDoDia` (e registra no diario) se o teto do dia bateu."""
    texto = cota.motivo(config)
    if not texto:
        return
    try:
        _rb_atividade.registrar("picasso", _rb_atividade.LOG, texto,
                                "historias", etapa="imagens.teto_do_dia")
    except Exception:                                          # noqa: BLE001
        pass
    raise TetoDoDia(texto)


def _pausado(alvo: str = "picasso"):
    """(pausado?, motivo) segundo o interruptor compartilhado."""
    try:
        controle = _rb_identity_controle
    except Exception:
        return False, ""
    try:
        estado = controle.estado()
    except Exception:
        return False, ""
    if estado.get("situacao") == controle.PARANDO:
        return True, "a pipeline esta em PARADA LIMPA"
    for chave in (controle.TUDO, alvo):
        pausa = (estado.get("pausas") or {}).get(chave)
        if pausa:
            motivo = pausa.get("motivo") or "sem motivo anotado"
            return True, f"pausado ({chave}): {motivo}"
    return False, ""


def _ordem_de_geradores(config: dict) -> list[str]:
    """Os geradores permitidos, do que trabalhou ha mais tempo ao ultimo."""
    from ias import imagem

    permitidos = [str(g).lower() for g in config.get("geradores_imagem", [])]
    ordem = [g for g in imagem.rodizio_ordem() if g in permitidos]
    horas = float(config.get("cota_pausa_h", 6))
    return [g for g in ordem if imagem.gerador(g).get("disponivel")
            and not imagem.fora_de_cota(g, horas)]


def _entregar_imagem(pedido: dict, prazo_s: float):
    """Entrega sincronicamente pelo correio; o prazo e do cliente da casa."""
    from ias.carteiro import Carteiro

    carteiro = Carteiro(ajustes={"resposta_timeout_s": prazo_s},
                        avisar=lambda _texto: False,
                        avisar_arquivo=lambda _caminho, _legenda: False)
    return carteiro.entregar(pedido)


def _imagem_do_correio(caixa: str, mensagem_id: str, resposta: dict) -> tuple:
    """(arquivo, gerador, prova, erro, categoria), apenas se ha prova gravada."""
    from ias import correio

    atual = correio.uma(caixa, mensagem_id) or resposta or {}
    if atual.get("situacao") != "respondida":
        return None, "", None, str(atual.get("erro") or "o correio nao respondeu"), \
            str(atual.get("categoria") or "erro")
    resumo = atual.get("imagem") if isinstance(atual.get("imagem"), dict) else {}
    if not resumo.get("prova"):
        return None, "", None, "imagem sem prova de origem", "sem_prova"
    origem = correio.arquivo_da_imagem(caixa, mensagem_id)
    if origem is None or not origem.is_file():
        return None, "", None, "o arquivo provado nao esta no correio", "arquivo"
    try:
        registro = json.loads(origem.with_suffix(".prova.json").read_text(encoding="utf-8"))
        prova = registro.get("prova") if isinstance(registro, dict) else None
    except (OSError, ValueError):
        prova = None
    if not isinstance(prova, dict) or not prova.get("comprovada"):
        return None, "", None, "imagem sem prova de origem", "sem_prova"
    gerador = str(atual.get("gerador") or "")
    return origem, gerador, prova, "", ""


def _pedir_uma_imagem(caixa: str, prompt: str, proporcao: str, prazo_s: float,
                       entregador) -> tuple:
    """Pede, espera a entrega e devolve somente um arquivo com prova."""
    from ias import correio

    pedido = correio.pedir_imagem(caixa, prompt, proporcao=proporcao,
                                  de="historias")
    resposta = entregador(pedido, prazo_s)
    origem, gerador, prova, erro, categoria = _imagem_do_correio(
        caixa, str(pedido["id"]), resposta)
    return origem, gerador, prova, erro, categoria, str(pedido["id"])


def _gerar_pelo_correio(historia_id: str, *, limite: int | None = None,
                        parte: int | None = None, headless: bool = False,
                        log=print, entregador=None) -> dict:
    """Gera cenas pelo correio, conservando o arquivo e a prova da entrega."""
    from ias import correio
    from ..roteiro import roteiro as R

    roteiro = R.carregar(historia_id)
    config = fila.carregar_config()
    config["aspect"] = fila.aspecto_da_historia(historia_id)
    pendentes = fila.pendentes(historia_id, roteiro, parte)
    if limite:
        pendentes = pendentes[:limite]
    if not pendentes:
        return {"geradas": 0, "faltam": 0, "erros": [], "recusadas": []}

    divisao = str(config.get("divisao") or "por-historia")
    prazo_s = float(config.get("espera_correio_s", 420))
    entregador = entregador or _entregar_imagem
    ordem = _ordem_de_geradores(config)
    if divisao == "por-historia" and not ordem:
        raise NaoRodou("nenhum gerador de imagem esta livre ou em cota")
    fixado = fila.gerador_da_historia(historia_id)
    if divisao == "por-historia" and not fixado:
        fixado = ordem[0]
        fila.definir_gerador_da_historia(historia_id, fixado)
        log(f"[imagens] {historia_id}: {fixado} fixado para a historia.")

    geradas, erros, recusadas = 0, [], []
    protagonista = str(roteiro.get("protagonista") or "")
    moderacao = _rb_identity_moderacao
    from .reescritor import Reescritor
    reescritor = (Reescritor(str(config.get("llm_provedor", "chatgpt")),
                             headless=headless, log=log)
                  if config.get("reescrever_com_llm", True) else None)
    for linha in pendentes:
        n, numero_parte = linha["n"], linha.get("parte", 1)
        bloco = next(p for p in roteiro["partes"] if p["n"] == numero_parte)
        cena = next(c for c in bloco["cenas"] if c["n"] == n)
        prompt = fila.prompt_da_cena(cena, config, protagonista,
                                     estilo=fila.estilo_do_roteiro(roteiro),
                                     elenco=str(roteiro.get("elenco") or ""))
        rotulo = f"p{numero_parte:02d}_cena_{n:02d}"
        ultima_recusa, salvo = None, False
        degraus = moderacao.escalonar(
            prompt, max_nivel=int(config.get("suavizacao_max", 3)),
            preventivo=bool(config.get("suavizar_antes", True)))
        for nivel, tentativa, _mudancas in _com_reescrita(
                degraus, reescritor, lambda: ultima_recusa,
                int(config.get("reescritas_max", 2)), log, rotulo):
            caixas = [correio.LIVRE] if divisao == "por-cena" else [fixado]
            if divisao == "por-historia":
                caixas.extend(g for g in ordem if g != fixado)
            for caixa in caixas:
                tentativas = 1 if caixa == correio.LIVRE else 2
                for _volta in range(tentativas):
                    origem, gerador, prova, erro, categoria, pedido = _pedir_uma_imagem(
                        caixa, tentativa, config["aspect"], prazo_s, entregador)
                    gerador = gerador or caixa
                    if origem is not None:
                        destino = Path(linha["arquivo"])
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(origem, destino)
                        fila.registrar(historia_id, n, prompt=tentativa, arquivo=destino,
                                       prova=prova,
                                       parte=numero_parte, nivel=nivel, gerador=gerador,
                                       pedido=pedido)
                        geradas += 1
                        salvo = True
                        break
                    if categoria == "conteudo":
                        ultima_recusa = erro
                        break
                    falhas = fila.registrar_falha_de_gerador(
                        historia_id, n, parte=numero_parte, gerador=gerador, motivo=erro)
                    if falhas >= 2:
                        log(f"[imagens] {rotulo}: {gerador} falhou 2x; tento o proximo.")
                        break
                if salvo:
                    break
            if salvo:
                break
        if salvo:
            continue
        if ultima_recusa:
            fila.registrar_recusa(historia_id, n, parte=numero_parte,
                                  motivo=ultima_recusa, prompt=prompt,
                                  ultima_tentativa=tentativa)
            recusadas.append(rotulo)
        else:
            erros.append(f"{rotulo}: imagem nao entregue com prova de origem")
    faltam = len(fila.pendentes(historia_id, roteiro, parte))
    return {"geradas": geradas, "faltam": faltam, "erros": erros, "recusadas": recusadas}


def gerar(historia_id: str, *, limite: int | None = None,
          headless: bool = False, parte: int | None = None, log=print,
          entregador=None) -> dict:
    """Gera as imagens que faltam. Devolve {geradas, faltam, erros}.

    PAREDE DE PLANOS (17/09/2026): se o PicassoIA pedir assinatura numa conta
    que tem plano, o navegador e FECHADO e o perfil REABERTO uma vez — foi o
    que resolveu na madrugada. Se a parede voltar, a rodada para como erro de
    infraestrutura (`NaoRodou`): a historia continua pendente e a proxima
    rodada tenta de novo; o video nao e abandonado.

    QUANTAS REABERTURAS (30/09/2026): `reaberturas_na_parede` no
    `config/imagens.json` (padrao 1, como era). O lote de dia pede ~330
    imagens por dia, e a parede de 17/09 veio depois de 112 numa noite:
    com o lote, cair nela no meio de uma historia deixa de ser raro. Entre
    uma reabertura e outra, `pausa_antes_de_reabrir_s`.
    """
    try:
        ajustes = fila.carregar_config()
    except Exception:                                          # noqa: BLE001
        ajustes = {}
    # Configuracoes antigas continuam no caminho PicassoIA; a configuracao
    # nova declara os tres geradores e passa pelo correio.
    if ajustes.get("geradores_imagem"):
        return _gerar_pelo_correio(historia_id, limite=limite, parte=parte,
                                   headless=headless, log=log, entregador=entregador)
    Parede = _rb_identity_picasso_client.ParedeDePlanos
    reaberturas = max(0, int(ajustes.get("reaberturas_na_parede", 1)))
    pausa = float(ajustes.get("pausa_antes_de_reabrir_s", 0) or 0)
    for volta in range(reaberturas + 1):
        try:
            return _gerar(historia_id, limite=limite, headless=headless,
                          parte=parte, log=log)
        except Parede as exc:
            if volta >= reaberturas:
                _registrar_parede(historia_id, exc)
                raise NaoRodou(f"{exc} (de novo, depois de reabrir o perfil "
                               f"{reaberturas}x)") from exc
            log(f"[imagens] {exc}. Fecho o navegador e reabro o perfil "
                f"({volta + 1}/{reaberturas}).")
            if pausa:
                time.sleep(pausa)
    raise AssertionError("inalcancavel")


def _registrar_parede(historia_id: str, exc) -> None:
    try:
        import builds.atividade as atividade
        atividade.registrar(
            "picasso", atividade.ERRO,
            f"{historia_id}: {str(exc)[:200]} - reabri o perfil e continuou; "
            "confira a conta logada no perfil do PicassoIA",
            "historias", etapa="imagens.parede_de_planos", ref=historia_id)
    except Exception:                                          # noqa: BLE001
        pass


def _gerar(historia_id: str, *, limite: int | None = None,
           headless: bool = False, parte: int | None = None,
           log=print) -> dict:
    """Uma passada com UM navegador aberto."""
    from ..roteiro import roteiro as R

    roteiro = R.carregar(historia_id)
    config = fila.carregar_config()
    # A PROPORCAO E DA HISTORIA, e nao do imagens.json: historia antiga tem
    # fotos 9:16 e o reparo de uma cena dela nao pode voltar quadrado.
    config["aspect"] = fila.aspecto_da_historia(historia_id)
    pendentes = fila.pendentes(historia_id, roteiro, parte)
    if not pendentes:
        log(f"[imagens] {historia_id}: todas as cenas ja tem imagem.")
        return {"geradas": 0, "faltam": 0, "erros": [], "recusadas": []}

    pausado, motivo = _pausado()
    if pausado:
        raise NaoRodou(f"nao abri o PicassoIA: {motivo}. "
                       "Retome pelo painel (faixa PIPELINE) e rode de novo.")
    # Teto do dia batido: nem abre o navegador (30/09/2026, `cota`).
    _conferir_cota(config)

    if limite:
        pendentes = pendentes[:limite]
    protagonista = str(roteiro.get("protagonista") or "")

    Cliente = _rb_identity_picasso_client.PicassoClient
    contexto_persistente = _rb_identity_browser.contexto_persistente
    pagina = _rb_identity_browser.pagina
    ensure_logged_in = _rb_identity_session.ensure_logged_in
    icfg = _rb_identity_config
    ajustes = {**icfg.settings("picasso"), **{
        k: v for k, v in config.items() if not k.startswith("_")}}

    geradas, erros, recusadas = 0, [], []
    morreu = False
    parede = None
    teto_batido = None
    moderacao = _rb_identity_moderacao
    ConteudoRecusado = _rb_identity_client.ConteudoRecusado
    from .reescritor import Reescritor
    reescritor = (Reescritor(str(config.get("llm_provedor", "chatgpt")),
                             headless=headless, log=log)
                  if config.get("reescrever_com_llm", True) else None)
    log(f"[imagens] {historia_id}: {len(pendentes)} cena(s) para gerar.")

    travas = _rb_travas
    from contextlib import ExitStack
    pilha = ExitStack()
    nome_trava = travas.do_perfil("picasso", "historias")
    if not pilha.enter_context(travas.trava(nome_trava, esperar=20.0)):
        pilha.close()
        raise NaoRodou(
            f"a conta do PicassoIA ({nome_trava}) esta em uso por outro "
            "processo agora (provavelmente o worker de builds). Com uma conta "
            "propria para as historias (pagina Contas), os dois rodam em "
            "paralelo.")
    with pilha:
        seletores = _rb_identity_provedores.seletores("picasso")
        # Canal `historias`: o registro de contas pode apontar para outra
        # conta do PicassoIA que nao a do canal de builds.
        with contexto_persistente(
                headless=headless,
                profile=icfg.profile_dir("picasso", canal="historias")) as ctx:
            page = pagina(ctx)
            # `sel` explicito: o padrao de `ensure_logged_in` e o Digen, e com
            # ele o login abriria a pagina errada.
            ensure_logged_in(page, ajustes, sel=seletores, provedor="picasso")
            cliente = Cliente(ctx, page, ajustes)
            proveniencia = _rb_identity_proveniencia

            for i, linha in enumerate(pendentes):
                n, numero_parte = linha["n"], linha.get("parte", 1)
                bloco = next(p for p in roteiro["partes"]
                             if p["n"] == numero_parte)
                cena = next(c for c in bloco["cenas"] if c["n"] == n)
                prompt = fila.prompt_da_cena(cena, config, protagonista,
                                             estilo=fila.estilo_do_roteiro(
                                                 roteiro),
                                             elenco=str(roteiro.get("elenco")
                                                        or ""))
                rotulo = f"p{numero_parte:02d}_cena_{n:02d}"
                if i:
                    time.sleep(float(ajustes.get("min_interval", 8)))

                # Uma cena, ate 4 tentativas: o prompt como veio e, a cada
                # RECUSA do filtro de conteudo, uma versao mais suave. Sem
                # isso a cena ficava sem imagem para sempre: reenviar o mesmo
                # texto e ser recusado de novo, por definicao.
                feito, ultima_recusa, ultima_tentativa = False, None, prompt
                falha_tecnica = None
                # A escalada nao e uma lista fixa: depois de uma recusa REAL
                # entra o LLM (que escreveu a historia e sabe o que a cena
                # esta contando) e so depois a troca mecanica, que e a rede
                # de seguranca para quando o navegador do LLM nao abrir.
                degraus = moderacao.escalonar(
                    prompt, max_nivel=int(config.get("suavizacao_max", 3)),
                    preventivo=bool(config.get("suavizar_antes", True)))
                for nivel, tentativa, mudancas in _com_reescrita(
                        degraus, reescritor, lambda: ultima_recusa,
                        int(config.get("reescritas_max", 2)), log, rotulo):
                    if nivel:
                        log(f"[imagens] {rotulo}: tentando {nivel} "
                            f"({', '.join(mudancas) or 'suavizado'})")
                    try:
                        alvo, antes = _gerar_esperando(
                            cliente, tentativa, config, ajustes, log, rotulo)
                        prova = proveniencia.comprovar(
                            cliente, historia_id, rotulo,
                            cliente.prompt_enviado, cliente.enviado_em, alvo,
                            ajustes)
                        if (config.get("exigir_prova_de_origem", True)
                                and not prova.get("comprovada")):
                            # Falha de prova nao e recusa de conteudo: e erro
                            # tecnico (site falhou ao confirmar origem), e a
                            # cena volta na proxima passada.
                            #
                            # NADA VAI AO DISCO. Ate 14/09/2026 este ramo
                            # baixava a imagem "para registrar a tentativa" e
                            # gravava `prova` com comprovada: false. A imagem
                            # que aparece sem card nosso e, por definicao, de
                            # OUTRA pessoa da conta compartilhada: as 20:26 a
                            # historia_00011 p06_cena_07 (um rapaz preso num
                            # conteiner) virou uma mulher se maquiando, o
                            # reparo aceitou o arquivo e renderizou a parte com
                            # ela. So o Gemini barrou.
                            falha_tecnica = ValueError(
                                f"Prova: {prova.get('motivo')}")
                            erros.append(f"{rotulo}: sem prova de origem "
                                         f"({prova.get('motivo')}). Nada baixado.")
                            log(f"[imagens] {rotulo}: {erros[-1]}")
                            break
                        destino = linha["arquivo"]
                        cliente.download(prova.get("url") or alvo, destino)
                        # COLAGEM SE REFAZ COM O MESMO PROMPT, e nao se
                        # suaviza: o texto esta certo, quem errou foi o
                        # desenho. Suavizar aqui pioraria a cena para
                        # consertar o que nao era problema dela — a mesma
                        # regra do estouro de espera.
                        #
                        # A REFEITA TAMBEM EXIGE PROVA (revisao de 15/09/2026).
                        # Este laco baixava `prova.get("url") or alvo` sem olhar
                        # `comprovada`: numa conta compartilhada, a primeira
                        # imagem nova com a forma pedida pode ser de outra
                        # pessoa, e ela sobrescrevia a imagem PROVADA. Sem
                        # prova, fica a que ja estava (e a prova dela).
                        refeita = {"voltas": 0, "variacao": False}
                        for volta in range(1, TENTATIVAS_DE_COMPOSICAO):
                            razao = composicao.motivo(destino)
                            if not razao:
                                break
                            # A 1a refeita repete o texto (o desenho e que
                            # errou); da 2a em diante entra a variacao de
                            # enquadramento (experimento, ver a constante).
                            com_variacao = volta >= 2
                            pedido = (variar_enquadramento(tentativa)
                                      if com_variacao else tentativa)
                            refeita["voltas"] = volta
                            refeita["variacao"] = (refeita["variacao"]
                                                   or com_variacao)
                            log(f"[imagens] {rotulo}: {razao} Refazendo "
                                f"({volta}/{TENTATIVAS_DE_COMPOSICAO - 1})"
                                + (" com outro enquadramento."
                                   if com_variacao else "."))
                            time.sleep(float(ajustes.get("min_interval", 8)))
                            try:
                                alvo, antes = _gerar_esperando(
                                    cliente, pedido, config, ajustes, log,
                                    rotulo)
                            except TetoDoDia as exc:
                                # A imagem PROVADA que ja esta no disco fica
                                # e e registrada abaixo; a passada para
                                # depois desta cena.
                                teto_batido = exc
                                log(f"[imagens] {rotulo}: {exc}; fica a "
                                    "imagem anterior.")
                                break
                            nova = proveniencia.comprovar(
                                cliente, historia_id, rotulo,
                                cliente.prompt_enviado, cliente.enviado_em,
                                alvo, ajustes)
                            if not (nova.get("comprovada") and nova.get("url")):
                                log(f"[imagens] {rotulo}: a refeita nao tem "
                                    f"prova de origem ({nova.get('motivo')}); "
                                    "fica a imagem anterior.")
                                break
                            cliente.download(nova["url"], destino)
                            prova = nova
                        # O DOWNLOAD FALHA CALADO, e o laco acima acredita
                        # nele: `composicao.motivo` de um caminho inexistente
                        # devolve "", que quer dizer "nao e colagem", e a cena
                        # sairia registrada como pronta. Um "sim" tirado de uma
                        # pergunta que nao pode ser respondida.
                        #
                        # Medido em 11/09/2026 na p05_cena_11: o registro dizia
                        # sucesso e o arquivo nunca chegou ao disco.
                        if not Path(destino).is_file():
                            falha_tecnica = FileNotFoundError(
                                f"Download nao criou o arquivo: {destino}")
                            erros.append(f"{rotulo}: arquivo nao foi criado "
                                         f"apos download. Nada salvo.")
                            log(f"[imagens] {rotulo} FALHOU: {falha_tecnica}")
                            break
                        proveniencia.reivindicar(prova, historia_id, rotulo)
                        if refeita["voltas"]:
                            # O QUE PERMITE MEDIR DEPOIS: quantas refeitas, se
                            # alguma levou a variacao, e se no fim ainda era
                            # colagem. Sem isto o experimento nunca poderia ser
                            # julgado, so lembrado.
                            refeita["colagem_no_fim"] = bool(
                                composicao.motivo(destino))
                            _rb_atividade.registrar(
                                "picasso", _rb_atividade.LOG,
                                f"{rotulo}: refeita por colagem "
                                f"{refeita['voltas']}x, "
                                f"variacao={refeita['variacao']}, "
                                f"colagem_no_fim={refeita['colagem_no_fim']}",
                                "historias", etapa="imagens.refeita",
                                ref=f"{historia_id}:{rotulo}")
                        fila.registrar(historia_id, n,
                                       prompt=cliente.prompt_enviado,
                                       arquivo=destino, prova=prova,
                                       url=prova.get("url") or alvo,
                                       parte=numero_parte, nivel=nivel,
                                       refeita=refeita if refeita["voltas"]
                                       else None)
                        geradas += 1
                        feito = True
                        aviso = (f" [{nivel}: "
                                 f"{', '.join(mudancas)}]" if nivel else "")
                        log(f"[imagens] {rotulo} pronta "
                            f"({geradas}/{len(pendentes)}){aviso}")
                        break
                    except ConteudoRecusado as exc:
                        ultima_recusa, ultima_tentativa = str(exc), tentativa
                        log(f"[imagens] {rotulo}: RECUSADO no nivel {nivel} "
                            f"- {exc}")
                        time.sleep(float(ajustes.get("min_interval", 8)) / 2)
                        continue
                    except TetoDoDia as exc:
                        # PARA A PASSADA INTEIRA, e nao so a cena: o teto e
                        # do dia, e a cena seguinte bateria nele de novo.
                        # Sobe depois de fechar o navegador (como a parede).
                        teto_batido, morreu = exc, True
                        log(f"[imagens] {rotulo}: {exc}. Paro aqui.")
                        break
                    except Exception as exc:
                        falha_tecnica = exc
                        erros.append(f"{rotulo}: {type(exc).__name__}: {exc}")
                        log(f"[imagens] {rotulo} FALHOU: {exc}")
                        if type(exc).__name__ in ("BrowserMorreu",):
                            morreu = True
                        if isinstance(
                                exc,
                                _rb_identity_picasso_client.ParedeDePlanos):
                            # Sai do navegador inteiro: quem chama reabre.
                            parede, morreu = exc, True
                        break

                if not feito and falha_tecnica is not None:
                    # PAROU POR ERRO NOSSO, NAO POR RECUSA DO SITE — e a
                    # diferenca muda o que se faz depois: recusa pede prompt
                    # novo no roteiro (trabalho humano), erro tecnico pede
                    # conserto no codigo e a cena volta sozinha.
                    #
                    # Sem esta separacao a mentira era completa. Em 09/09/2026,
                    # `historia_00012` p01_cena_10: o PicassoIA recusou, o
                    # ChatGPT reescreveu, a imagem NOVA passou e foi baixada —
                    # e ai `fila.registrar` estourou num `int("llm 1")`. O
                    # `except` generico pegou, `feito` ficou False, e como
                    # havia uma recusa antiga guardada a cena foi gravada como
                    # "recusado pelo filtro ate o ultimo nivel". Tres cenas
                    # ficaram assim: imagem no disco, sem prova de origem, e
                    # marcadas como impossiveis.
                    log(f"[imagens] {rotulo}: parou por erro tecnico "
                        f"({type(falha_tecnica).__name__}), NAO por recusa. "
                        "A cena volta na proxima passada.")
                elif not feito and ultima_recusa:
                    # Esgotou ate o nivel ambiente: a cena fica marcada com o
                    # motivo (o painel mostra) e a geracao SEGUE. Uma cena
                    # barrada nao pode parar a historia inteira.
                    recusadas.append({"cena": rotulo, "motivo": ultima_recusa,
                                      "prompt": prompt})
                    fila.registrar_recusa(historia_id, n, parte=numero_parte,
                                          motivo=ultima_recusa, prompt=prompt,
                                          ultima_tentativa=ultima_tentativa)
                    erros.append(f"{rotulo}: recusado pelo filtro de conteudo "
                                 "ate o ultimo nivel. Reescreva o prompt de "
                                 "imagem desta cena no roteiro.")
                    log(f"[imagens] {rotulo}: {erros[-1]}")
                if morreu or teto_batido is not None:
                    break

    if reescritor is not None:
        reescritor.fechar()
    if parede is not None:
        raise parede
    if teto_batido is not None:
        raise teto_batido

    faltam = len(fila.pendentes(historia_id, roteiro, parte))
    if recusadas:
        log(f"[imagens] {len(recusadas)} cena(s) barrada(s) pelo filtro de "
            "conteudo: " + ", ".join(r["cena"] for r in recusadas))
    log(f"[imagens] {historia_id}: {geradas} gerada(s), {faltam} pendente(s).")
    return {"geradas": geradas, "faltam": faltam, "erros": erros,
            "recusadas": recusadas}
