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

import re
import time
from pathlib import Path

from builds.identity import browser as _rb_identity_browser
from builds.identity import client as _rb_identity_client
from builds.identity import config as _rb_identity_config
from builds.identity import picasso_client as _rb_identity_picasso_client
from builds.identity import session as _rb_identity_session
from builds.identity import controle as _rb_identity_controle
from builds.identity import moderacao as _rb_identity_moderacao
from builds.identity import provedores as _rb_identity_provedores
from builds.identity import proveniencia as _rb_identity_proveniencia
import builds.travas as _rb_travas
from . import composicao, fila

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


class NaoRodou(RuntimeError):
    """Motivo humano para a passada nao ter acontecido (trava, pausa, login)."""


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


def gerar(historia_id: str, *, limite: int | None = None,
          headless: bool = False, parte: int | None = None, log=print) -> dict:
    """Gera as imagens que faltam. Devolve {geradas, faltam, erros}."""
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
                                                 roteiro))
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
                        for volta in range(1, TENTATIVAS_DE_COMPOSICAO):
                            razao = composicao.motivo(destino)
                            if not razao:
                                break
                            log(f"[imagens] {rotulo}: {razao} Refazendo "
                                f"({volta}/{TENTATIVAS_DE_COMPOSICAO - 1}).")
                            time.sleep(float(ajustes.get("min_interval", 8)))
                            alvo, antes = _gerar_esperando(
                                cliente, tentativa, config, ajustes, log,
                                rotulo)
                            prova = proveniencia.comprovar(
                                cliente, historia_id, rotulo,
                                cliente.prompt_enviado, cliente.enviado_em,
                                alvo, ajustes)
                            cliente.download(prova.get("url") or alvo, destino)
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
                        fila.registrar(historia_id, n,
                                       prompt=cliente.prompt_enviado,
                                       arquivo=destino, prova=prova,
                                       url=prova.get("url") or alvo,
                                       parte=numero_parte, nivel=nivel)
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
                    except Exception as exc:
                        falha_tecnica = exc
                        erros.append(f"{rotulo}: {type(exc).__name__}: {exc}")
                        log(f"[imagens] {rotulo} FALHOU: {exc}")
                        if type(exc).__name__ in ("BrowserMorreu",):
                            morreu = True
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
                if morreu:
                    break

    if reescritor is not None:
        reescritor.fechar()

    faltam = len(fila.pendentes(historia_id, roteiro, parte))
    if recusadas:
        log(f"[imagens] {len(recusadas)} cena(s) barrada(s) pelo filtro de "
            "conteudo: " + ", ".join(r["cena"] for r in recusadas))
    log(f"[imagens] {historia_id}: {geradas} gerada(s), {faltam} pendente(s).")
    return {"geradas": geradas, "faltam": faltam, "erros": erros,
            "recusadas": recusadas}
