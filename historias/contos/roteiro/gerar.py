# -*- coding: utf-8 -*-
"""Gera a historia inteira sozinho: abre o LLM no browser e conduz a conversa.

E o passo que era manual (montar prompt, colar no site, copiar a resposta)
virando automatico. O ganho nao e so de cliques: como as duas etapas
acontecem no MESMO chat, a parte 7 e escrita com a biblia e as seis partes
anteriores ainda no contexto — coisa que copiar e colar nao dava.

Tres cuidados que vieram da experiencia com os outros sites:

  SALVA A CADA PARTE. Uma serie de 8 partes leva muitos minutos; se o site
  cair na parte 6, as cinco anteriores continuam no disco e a retomada
  comeca de onde parou.
  RESPOSTA CORTADA E NORMAL. Os sites cortam mensagem longa. Quando vem
  menos cena do que se pediu, o proximo turno e "continue da cena N" — e
  nao uma tentativa nova do zero.
  NADA E DADO COMO FEITO SEM PROVA. Biblia sem protagonista ou parte sem
  cena viram erro com o motivo, nao um roteiro pela metade.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import roteiro as R
from . import serie as S
from .modelo import carregar_config

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"


class GeracaoFalhou(RuntimeError):
    """Erro humano: o que aconteceu e o que fazer."""


def _gravar(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def _guardar_conversa(pasta: Path, nome: str, texto: str) -> None:
    destino = pasta / "conversa"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nome).write_text(texto, encoding="utf-8")


class _Diario:
    """Escreve na tela E num arquivo, para a corrida deixar rastro.

    As pastas `historia_00006` e `historia_00007` sao duas tentativas que
    morreram em 01/09/2026 as 18:00 e as 18:01 e nao deixaram NADA — o projeto
    inteiro imprimia em stdout e jogava fora, entao nao ha como saber por que
    elas falharam. A partir daqui ha.
    """

    def __init__(self, log, destino: Path):
        self._log = log or (lambda _: None)
        self.destino = Path(destino)
        self.destino.parent.mkdir(parents=True, exist_ok=True)
        self.linhas = []

    def __call__(self, texto: str) -> None:
        self._log(texto)
        carimbo = datetime.now().strftime("%H:%M:%S")
        self.linhas.append(f"{carimbo} {texto}")
        try:
            with open(self.destino, "a", encoding="utf-8") as fh:
                fh.write(f"{carimbo} {texto}\n")
        except OSError:      # o log nao pode derrubar a geracao
            pass

    def mudar_de_casa(self, novo: Path) -> None:
        """O id so existe depois da biblia; o log escrito antes vai junto."""
        novo = Path(novo)
        if novo == self.destino:
            return
        novo.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(novo, "a", encoding="utf-8") as fh:
                fh.write("\n".join(self.linhas) + "\n")
            self.destino.unlink(missing_ok=True)
        except OSError:
            return
        self.destino = novo


def _completar_parte(cliente, texto: str, numero: int, cenas_alvo: int,
                     pasta: Path, log) -> dict:
    """A parte parseada, pedindo continuacao enquanto vier cortada."""
    parcial = R.parse(texto)
    tentativas = 0
    while len(parcial["cenas"]) < cenas_alvo and tentativas < 3:
        tentativas += 1
        ultima = len(parcial["cenas"])
        log(f"[serie] parte {numero}: vieram {ultima}/{cenas_alvo} cenas; "
            f"pedindo continuacao ({tentativas}/3)")
        extra = cliente.perguntar(
            S.prompt_continuar(numero, ultima, cenas_alvo))
        _guardar_conversa(pasta, f"parte_{numero:02d}_cont{tentativas}.txt", extra)
        novas = R.parse(extra)["cenas"]
        if not novas:
            break
        parcial["cenas"].extend(novas)
        for ordem, cena in enumerate(parcial["cenas"], 1):
            cena["n"] = ordem
    return parcial


def _revisar_parte(cliente, parcial: dict, numero: int, cenas_alvo: int,
                   pasta: Path, config: dict, log) -> dict:
    """Um turno a mais: o modelo relê o que escreveu e reescreve melhor.

    E a mudanca que mais levanta qualidade de texto de LLM. A primeira versao
    e a MEDIA do que ele ja viu — clichê, frase de efeito, todas as cenas do
    mesmo tamanho. Ele reconhece isso quando perguntado; so nao faz de gratis.

    Conservadora de proposito: se a revisao vier com menos cenas do que a
    original, ela e DESCARTADA. Uma parte pela metade e pior do que uma parte
    mediana, e o custo de errar aqui e o video inteiro.
    """
    try:
        texto = cliente.perguntar(
            S.prompt_revisao(numero, cenas_alvo, config=config))
    except Exception as exc:                                   # noqa: BLE001
        log(f"[serie] a revisao da parte {numero} nao veio ({exc}); "
            "fico com a primeira versao.")
        return parcial
    _guardar_conversa(pasta, f"parte_{numero:02d}_revisao.txt", texto)
    revisada = R.parse(texto)
    if len(revisada["cenas"]) < len(parcial["cenas"]):
        log(f"[serie] a revisao da parte {numero} veio com "
            f"{len(revisada['cenas'])} de {len(parcial['cenas'])} cenas; "
            "fico com a primeira versao.")
        return parcial
    log(f"[serie] parte {numero} revisada ({len(revisada['cenas'])} cenas).")
    return {"titulo": revisada["titulo"] or parcial["titulo"],
            "cta": revisada["cta"] or parcial["cta"],
            "cenas": revisada["cenas"]}


TENTATIVAS_DE_TROCA = 2


def _trocar_premissa_se_precisar(cliente, biblia: dict, partes: int,
                                 pasta: Path, log) -> dict:
    """Biblia que a plataforma derrubaria -> a mesma historia, sem o ponto.

    Duas coisas que este passo NAO e. Nao e censura de palavra: trocar o termo
    esconderia de quem le, nao de quem revisa, e a revisao olha do que a
    historia trata. E nao e descarte: a premissa fica, o molde fica, as
    alavancas ficam — muda de onde vem a pressao, que passa a ser divida,
    poder e vergonha entre adultos. Isso prende igual ou mais.

    Duas tentativas. Se o modelo insistir, a historia nao nasce — mas ai ela
    morre custando dois turnos de chat, e nao seis partes mais 84 imagens.
    """
    from . import linguagem

    for tentativa in range(1, TENTATIVAS_DE_TROCA + 1):
        achados = linguagem.conferir_biblia(biblia)
        if not achados["pare"]:
            if tentativa > 1:
                log("[linguagem] premissa trocada; a historia segue.")
            return biblia
        termos = linguagem.termos_de_pare(achados)
        onde = ", ".join(i["onde"] for i in achados["pare"])
        log(f"[linguagem] a biblia cai em assunto impublicavel "
            f"({', '.join(termos)}) em: {onde}. Pedindo a troca da premissa "
            f"({tentativa}/{TENTATIVAS_DE_TROCA}) — o molde e as alavancas "
            "ficam, muda de onde vem a pressao.")
        try:
            texto = cliente.perguntar(
                S.prompt_trocar_premissa(termos, partes))
        except Exception as exc:                               # noqa: BLE001
            raise GeracaoFalhou(
                "a premissa planejada nao pode ir ao ar "
                f"({', '.join(termos)}) e o pedido de troca nao chegou ao "
                f"modelo ({exc}). Nenhuma parte foi escrita.") from exc
        _guardar_conversa(pasta, f"biblia_troca{tentativa}.txt", texto)
        nova = S.parse_biblia(texto, partes)
        if not nova.get("partes"):
            log(f"[linguagem] a troca {tentativa} voltou fora do formato.")
            continue
        biblia = nova

    achados = linguagem.conferir_biblia(biblia)
    if achados["pare"]:
        raise GeracaoFalhou(
            "a premissa insiste em um assunto que a plataforma remove ("
            + ", ".join(linguagem.termos_de_pare(achados)) +
            f") depois de {TENTATIVAS_DE_TROCA} pedidos de troca. Nenhuma "
            f"parte foi escrita e nenhuma imagem foi gerada. O texto cru esta "
            f"em {pasta / 'conversa'}.")
    return biblia


def retomar_serie(historia_id: str, *, provedor: str = "gemini",
                  cenas_por_parte: int = S.CENAS_POR_PARTE,
                  headless: bool = False, config: dict | None = None,
                  log=print) -> dict:
    """Escreve so as PARTES QUE FALTAM de uma historia que parou no meio.

    Existe porque a escrita ja salva a cada parte e a biblia fica em disco: um
    roteiro que morreu na parte 3 nao precisa nascer de novo, precisa
    continuar. Em 10/09/2026 as 06:15 o Gemini bateu no limite de uso no meio
    da parte 3 e a `historia_00005` ficou com 2 de 6 — recomecar do zero seria
    jogar fora duas partes boas E o planejamento inteiro.

    A diferenca em relacao a `gerar_serie` e so o contexto: aqui o chat e novo
    e nao viu as partes anteriores. `prompt_parte` ja e auto-suficiente (leva a
    biblia, o elenco e a ficha de FATOS), entao o que se perde e a memoria
    fina do texto — e e por isso que ela vale como CONSERTO, nao como o jeito
    normal de escrever.
    """
    from ..llm.cliente import abrir_cliente

    config = config or carregar_config()
    pasta = OUTPUTS / historia_id
    diario = _Diario(log, pasta / "log.txt")
    log = diario

    roteiro = R.carregar(historia_id)
    faltam = R.partes_que_faltam(roteiro)
    if not faltam:
        log(f"[serie] {historia_id} nao tem parte faltando.")
        return {"historia_id": historia_id, "partes": 0, "retomada": False}
    with open(pasta / "biblia.json", encoding="utf-8-sig") as fh:
        biblia = json.load(fh)

    partes_prontas = [dict(p) for p in (roteiro.get("partes") or [])]
    log(f"[serie] retomando {historia_id}: faltam as partes {faltam} de "
        f"{roteiro.get('partes_esperadas')}.")
    with abrir_cliente(provedor, headless=headless, log=log) as cliente:
        cliente.abrir(novo_chat=True)
        for numero in faltam:
            log(f"[serie] retomada: escrevendo a parte {numero}...")
            texto = cliente.perguntar(
                S.prompt_parte(biblia, numero, cenas=cenas_por_parte,
                               config=config))
            _guardar_conversa(pasta, f"parte_{numero:02d}_retomada.txt", texto)
            parcial = _completar_parte(cliente, texto, numero, cenas_por_parte,
                                       pasta, log)
            if not parcial["cenas"]:
                raise GeracaoFalhou(
                    f"a parte {numero} voltou sem cena legivel na retomada. "
                    f"As partes anteriores continuam salvas.")
            parcial = _revisar_parte(cliente, parcial, numero, cenas_por_parte,
                                     pasta, config, log)
            plano = next((p for p in biblia["partes"] if p["n"] == numero), {})
            partes_prontas.append({
                "n": numero,
                "titulo": parcial["titulo"] or plano.get("titulo") or "",
                "cliffhanger": plano.get("cliffhanger", ""),
                "cta": parcial["cta"],
                "cenas": parcial["cenas"],
            })
            partes_prontas.sort(key=lambda p: int(p["n"]))
            R.salvar_serie(biblia, partes_prontas, historia_id,
                           tema=roteiro.get("tema") or "", provedor=provedor,
                           estrutura=roteiro.get("estrutura") or "",
                           modelo_llm=getattr(cliente, "modelo_atual", "") or "",
                           ganchos=roteiro.get("ganchos") or [],
                           narrador=roteiro.get("narrador") or "")
            log(f"[serie] parte {numero} pronta na retomada "
                f"({len(parcial['cenas'])} cenas).")
    ainda = R.partes_que_faltam(R.carregar(historia_id))
    log(f"[serie] {historia_id}: retomada terminou "
        + (f"e ainda faltam {ainda}." if ainda else "COMPLETA."))
    return {"historia_id": historia_id, "partes": len(faltam),
            "retomada": True, "faltam": ainda}


def gerar_serie(*, provedor: str = "chatgpt", partes: int = S.PARTES_PADRAO,
                cenas_por_parte: int = S.CENAS_POR_PARTE,
                tema: str | None = None, historia_id: str | None = None,
                headless: bool = False, config: dict | None = None,
                log=print) -> dict:
    """Conduz a conversa inteira e devolve {historia_id, partes, cenas}."""
    from ..llm.cliente import abrir_cliente

    config = config or carregar_config()
    # O ID SO E ALOCADO DEPOIS QUE A BIBLIA EXISTE. Antes ele era tirado aqui,
    # junto com a pasta, e uma corrida que morresse ao abrir o navegador (nao
    # logado, trava ocupada) queimava um numero e deixava uma pasta vazia no
    # painel para sempre. Ate a biblia parsear, tudo o que ha e um log em
    # `outputs/_logs/`, que e onde a proxima falha vai ser explicada.
    inicio = datetime.now()
    provisorio = OUTPUTS / "_logs" / inicio.strftime("%Y%m%d_%H%M%S.txt")
    diario = _Diario(log, provisorio)
    log = diario
    log(f"[serie] {partes} parte(s) de {cenas_por_parte} cenas via {provedor}"
        + (f", tema: {tema}" if tema else ""))

    try:
        with abrir_cliente(provedor, headless=headless, log=log) as cliente:
            cliente.abrir(novo_chat=True)
            # QUAL MODELO ESCREVEU ESTA HISTORIA. Guardado porque a qualidade
            # mudou de patamar em 08/09/2026 (Flash -> 3.1 Pro, mais molde,
            # revisao e alavancas) e sem isso nao da para distinguir o que e
            # do jeito novo do que sobrou do antigo — nem na fila de postagem,
            # nem daqui a um mes olhando para tras.
            modelo_llm = getattr(cliente, "modelo_atual", "") or ""
            # O QUE ESCREVEU DE VERDADE, inclusive quando deu errado. Em
            # 09/09/2026 as 22:59 a troca de modelo estourou por timeout e a
            # `historia_00004` inteira saiu no Flash-Lite — e `modelo_llm`
            # gravou VAZIO, entao no dia seguinte nao havia como distinguir
            # essa historia de uma boa sem reabrir o log. Vazio nao e
            # ausencia de informacao: e a informacao mais importante.
            if not getattr(cliente, "modelo_confirmado", True):
                modelo_llm = f"NAO CONFIRMADO ({modelo_llm or 'desconhecido'})"
                log(f"[serie] ATENCAO: a historia esta sendo escrita SEM "
                    f"confirmar o modelo forte ({modelo_llm}). O texto tende "
                    "a sair mais curto e mais raso.")

            # --- etapa 1: a biblia
            estrutura = S.proxima_estrutura(R.estruturas_recentes(), config)
            # QUEM NARRA E QUAIS ALAVANCAS, decididos AQUI e nao pelo modelo.
            # A ordem importa: as alavancas sao de genero ("marido que nao
            # cresce" so funciona na boca dela), entao o narrador tem que ser
            # conhecido antes de montar o prompt.
            narrador = S.proximo_narrador(R.narradores_recentes())
            ganchos = S.proximos_ganchos(R.ganchos_recentes(), narrador, config)
            log(f"[serie] etapa 1: planejando a historia inteira "
                f"(molde: {estrutura or 'nenhum'}, narrador: {narrador}, "
                f"alavancas: {' + '.join(ganchos) or 'nenhuma'})...")
            texto = cliente.perguntar(
                S.prompt_biblia(partes=partes, cenas_por_parte=cenas_por_parte,
                                tema=tema, config=config,
                                # O chat e novo a cada rodada: sem esta lista o
                                # modelo nao sabe o que o canal ja tem, e com o
                                # tema livre ele repete o mesmo gancho.
                                evitar=R.titulos_recentes(),
                                # E sem MOLDE ele repete tambem a forma: a
                                # serie nunca usou os tres de `roteiro.json`.
                                estrutura=estrutura,
                                # Sem estes dois ele repetia as MESMAS duas
                                # alavancas em 5 de 5 historias.
                                ganchos=ganchos, narrador=narrador))
            biblia = S.parse_biblia(texto, partes)
            problemas = S.problemas_da_biblia(biblia)

            historia_id = historia_id or R.proximo_id()
            pasta = OUTPUTS / historia_id
            pasta.mkdir(parents=True, exist_ok=True)
            diario.mudar_de_casa(pasta / "log.txt")
            log(f"[serie] {historia_id}: a biblia chegou.")
            _guardar_conversa(pasta, "biblia.txt", texto)
            if problemas:
                log(f"[serie] a biblia veio incompleta ({'; '.join(problemas)}); "
                    "pedindo de novo no formato.")
                texto = cliente.perguntar(
                    "A resposta nao seguiu o formato pedido: "
                    + "; ".join(problemas) +
                    ". Reescreva a BIBLIA inteira exatamente no formato solicitado, "
                    "sem texto fora dele.")
                _guardar_conversa(pasta, "biblia_2.txt", texto)
                biblia = S.parse_biblia(texto, partes)
                problemas = S.problemas_da_biblia(biblia)
                if not biblia.get("partes"):
                    raise GeracaoFalhou(
                        "o modelo nao devolveu a biblia no formato mesmo depois de "
                        f"corrigir ({'; '.join(problemas)}). O texto cru esta em "
                        f"{pasta / 'conversa'}.")
            # A PREMISSA IMPUBLICAVEL SE DESCOBRE AQUI, e aqui ela ainda tem
            # conserto. Depois desta linha vem seis turnos de escrita, 84
            # imagens (~40 min) e ~1h de render — e a agenda so descobria no
            # fim, jogando a historia inteira fora. Custa um turno de chat.
            biblia = _trocar_premissa_se_precisar(
                cliente, biblia, partes, pasta, log)

            _gravar(pasta / "biblia.json", biblia)
            log(f"[serie] biblia pronta: {biblia['titulo'] or '(sem titulo)'} "
                f"- {len(biblia['partes'])} parte(s)")

            # --- etapa 2: uma parte por vez, salvando a cada uma
            total = len(biblia["partes"]) or partes
            partes_prontas = []
            for numero in range(1, total + 1):
                log(f"[serie] etapa 2: escrevendo a parte {numero}/{total}...")
                texto = cliente.perguntar(
                    S.prompt_parte(biblia, numero, cenas=cenas_por_parte,
                                   config=config))
                _guardar_conversa(pasta, f"parte_{numero:02d}.txt", texto)
                parcial = _completar_parte(cliente, texto, numero, cenas_por_parte,
                                           pasta, log)
                if not parcial["cenas"]:
                    raise GeracaoFalhou(
                        f"a parte {numero} voltou sem nenhuma cena legivel. O texto "
                        f"cru esta em {pasta / 'conversa'}; as partes anteriores "
                        "ja estao salvas.")
                parcial = _revisar_parte(cliente, parcial, numero,
                                         cenas_por_parte, pasta, config, log)
                plano = next((p for p in biblia["partes"] if p["n"] == numero), {})
                partes_prontas.append({
                    "n": numero,
                    "titulo": parcial["titulo"] or plano.get("titulo") or "",
                    "cliffhanger": plano.get("cliffhanger", ""),
                    "cta": parcial["cta"],
                    "cenas": parcial["cenas"],
                })
                R.salvar_serie(biblia, partes_prontas, historia_id, tema=tema or "",
                               provedor=provedor, estrutura=estrutura,
                               modelo_llm=modelo_llm,
                               # NAS DUAS chamadas: esta salva a cada parte, e
                               # uma corrida que morra na parte 3 nao pode
                               # deixar memoria vazia para o rodizio.
                               ganchos=ganchos, narrador=narrador)
                log(f"[serie] parte {numero}/{total} pronta: "
                    f"{len(parcial['cenas'])} cenas")
    except Exception as exc:
        # A corrida que morre tem que dizer POR QUE. Sem isto sobrava uma
        # pasta vazia e nenhuma pista (historias 6 e 7, 01/09/2026).
        log(f"[serie] FALHOU: {type(exc).__name__}: {exc}")
        log(f"[serie] o registro desta tentativa esta em {diario.destino}")
        raise

    caminho = R.salvar_serie(biblia, partes_prontas, historia_id,
                             tema=tema or "", provedor=provedor,
                             estrutura=estrutura, modelo_llm=modelo_llm,
                             ganchos=ganchos, narrador=narrador)
    cenas = sum(len(p["cenas"]) for p in partes_prontas)
    log(f"[serie] {historia_id} completa: {len(partes_prontas)} parte(s), "
        f"{cenas} cenas -> {caminho}")

    # Os numeros so podem brigar depois que a serie inteira existe: e uma
    # pergunta entre partes, e nenhuma parte sozinha responde.
    from . import coerencia
    avisos = coerencia.conferir(R.carregar(historia_id))
    for aviso in avisos:
        log(f"[coerencia] {aviso}")
    return {"historia_id": historia_id, "titulo": biblia["titulo"],
            "partes": len(partes_prontas), "cenas": cenas,
            "coerencia": avisos,
            "gerado_em": datetime.now().isoformat(timespec="seconds")}
