# -*- coding: utf-8 -*-
"""O lote da semana numa pergunta: o estoque chega ate segunda?

Decisoes do Adrian em 30/09/2026 (Grimorio `geral/lote-*`): o trabalho pesado
sai da madrugada e vira LOTE SEMANAL DE DIA — janela 07-22h, historias
seg-qua, builds seg-ter, piso de reposicao qui-dom de 20 videos, e o 1o lote
na segunda 05/10.

UM CALCULO, TRES TELAS. O relatorio de metas e o /lote do bot (Markdown), o
painel flutuante (Tk) e o app do celular (os dois pela previsao,
`painel.flutuante.previsao`) mostram o MESMO `resumo()`. E os numeros nem sao
daqui:

  videos, piso, alvo, fim   `postar.estoque_do_lote` — o funil da escolha da
                            publicacao (`pendentes_por_canal`, sem as
                            retidas), o piso de `postar.piso_de_alerta` e o
                            alvo pela regua da agenda (horarios da grade ate
                            segunda 07h, mais o piso).
  janela e dias de lote     o config de quem cria: `agenda.json` (historias)
                            e `geracao.json` (builds).
  em curso / proximo lote   `agenda.lote_valendo`.

Ate 30/09/2026 o relatorio e o painel alertavam abaixo de UM DIA
(`PISO_DE_ESTOQUE = 1`, `dias < 1`), enquanto a criacao ja repunha abaixo de
20 videos. Medido as 11:53 desse dia: builds com 17 videos saia "1 dia(s)",
sem alerta nenhum, com a criacao ja abaixo do piso.

CASO ZERO (memoria "relatorio verde que mente"): canal que nao deu para
contar diz isso, e nunca "cobre"; zero video e zero, abaixo do piso. Nada
aqui levanta: um relatorio que quebra o bot seria pior do que nenhum.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CANAIS = {"historias": {"emoji": "📖", "rotulo": "histórias"},
          "builds": {"emoji": "⚔️", "rotulo": "builds"}}
SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")

SEM_CONTA = "não deu para contar o estoque"


# ------------------------------------------------------------ as fontes
def _carregar_postar():
    """O `ferramentas/postar.py`, carregado pelo caminho (ele nao e pacote)."""
    caminho = RAIZ / "ferramentas" / "postar.py"
    spec = importlib.util.spec_from_file_location("postar_lote", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _agenda():
    """(modulo, config) da criacao de historias — quem manda no calendario."""
    from contos.pipeline import agenda
    return agenda, agenda.carregar()


def _geracao() -> dict:
    """O config da geracao de builds (`geracao.json`)."""
    from builds.pipeline import noite
    return noite.carregar()


# ------------------------------------------------------------ o texto
def _numero(n: float) -> str:
    """`0,6` — uma casa, virgula brasileira."""
    return f"{n:.1f}".replace(".", ",")


def _janela(config: dict | None) -> str | None:
    """"07–22h", da `janela_pesada` do config; None sem ela."""
    janela = (config or {}).get("janela_pesada") or {}
    try:
        return (f"{int(janela['inicio']) % 24:02d}–"
                f"{int(janela['fim']) % 24:02d}h")
    except (KeyError, TypeError, ValueError):
        return None


def _dias_de_lote(config: dict | None) -> str | None:
    """"seg–qua"; dias soltos viram lista; None sem `dias_de_lote`."""
    try:
        dias = sorted({int(d) % 7
                       for d in (config or {}).get("dias_de_lote") or []})
    except (TypeError, ValueError):
        return None
    if not dias:
        return None
    if len(dias) > 1 and dias == list(range(dias[0], dias[-1] + 1)):
        return f"{SEMANA[dias[0]]}–{SEMANA[dias[-1]]}"
    return ", ".join(SEMANA[d] for d in dias)


def _situacao(ficha: dict) -> str:
    """sem_conta | abaixo_do_piso | sem_alvo | falta | cobre."""
    if not ficha["contou"]:
        return "sem_conta"
    if ficha["magro"]:
        return "abaixo_do_piso"
    if ficha["alvo"] is None:
        return "sem_alvo"
    return "falta" if ficha["faltam"] else "cobre"


def _texto_do_canal(ficha: dict) -> str:
    """A linha de um canal, sem emoji e sem Markdown (serve as tres telas)."""
    partes = []
    if not ficha["contou"]:
        partes.append(SEM_CONTA)
        if ficha["alvo"] is not None:
            partes.append(f"alvo {ficha['alvo']}")
    elif ficha["alvo"] is not None:
        partes.append(f"lote {ficha['videos']}/{ficha['alvo']} "
                      f"({_numero(ficha['dias'])} dia)")
    else:
        partes.append(f"{ficha['videos']} vídeo(s) "
                      f"({_numero(ficha['dias'])} dia), sem alvo")
    if ficha["piso"] is not None:
        partes.append(f"piso {ficha['piso']}")
    if ficha["janela"]:
        janela = f"janela {ficha['janela']}"
        if ficha["dias_de_lote"]:
            janela += f" {ficha['dias_de_lote']}"
        partes.append(janela)
    alerta = {"abaixo_do_piso": "⚠ abaixo do piso",
              "falta": f"faltam {ficha['faltam']}",
              "cobre": "✓ cobre"}.get(ficha["situacao"])
    texto = " · ".join(partes)
    return f"{texto} {alerta}" if alerta else texto


def _quando(momento: datetime, *, hora: bool = False) -> str:
    texto = f"{SEMANA[momento.weekday()]} {momento:%d/%m}"
    return f"{texto} {momento:%H}h" if hora else texto


# ------------------------------------------------------------ o calendario
def _calendario(agenda, config: dict, agora: datetime) -> str:
    """"lote em curso até qua 01/10 22h" ou "próximo lote: seg 05/10".

    Pelo `agenda.lote_valendo`, que ja sabe do `lote_a_partir_de`: antes da
    primeira segunda, dia de lote ainda nao e lote.
    """
    janela = config.get("janela_pesada") or {}
    inicio = int(janela.get("inicio", 0)) % 24
    fim = int(janela.get("fim", 24))

    def _abre(dia: datetime) -> datetime:
        return dia.replace(hour=inicio, minute=0, second=0, microsecond=0)

    def _fecha(dia: datetime) -> datetime:
        if inicio < fim < 24:
            return dia.replace(hour=fim, minute=0, second=0, microsecond=0)
        return dia.replace(hour=23, minute=59, second=0, microsecond=0)

    for adiante in range(15):
        dia = _abre(agora + timedelta(days=adiante))
        if not agenda.lote_valendo(config, dia):
            continue
        if adiante == 0 and agora >= _fecha(dia):
            continue
        if adiante == 0 and agora >= dia:
            ultimo = dia
            for _ in range(6):
                seguinte = ultimo + timedelta(days=1)
                if not agenda.lote_valendo(config, seguinte):
                    break
                ultimo = seguinte
            return f"lote em curso até {_quando(_fecha(ultimo), hora=True)}"
        return f"próximo lote: {_quando(dia)}"
    return "nenhum lote marcado na agenda"


# ------------------------------------------------------------ o resumo
def resumo(agora: datetime | None = None, *, postar=None) -> dict:
    """O lote da semana, pronto para JSON. Nunca levanta.

    `{"em", "canais": {canal: {"videos", "dias", "piso", "alvo", "faltam",
    "contou", "magro", "janela", "dias_de_lote", "situacao", "texto"}},
    "cobertura", "calendario", "erros"}`. Todo canal de `CANAIS` aparece,
    mesmo o que ninguem contou.
    """
    agora = agora or datetime.now()
    saida: dict = {"em": agora.isoformat(timespec="minutes"), "canais": {},
                   "cobertura": None, "calendario": None, "erros": []}

    lote: dict = {}
    try:
        postar = postar if postar is not None else _carregar_postar()
        lote = postar.estoque_do_lote(agora) or {}
    except Exception as exc:                                   # noqa: BLE001
        saida["erros"].append(f"estoque: {type(exc).__name__}: {exc}")

    configs: dict = {}
    agenda = None
    try:
        agenda, configs["historias"] = _agenda()
    except Exception as exc:                                   # noqa: BLE001
        saida["erros"].append(f"agenda: {type(exc).__name__}: {exc}")
    try:
        configs["builds"] = _geracao()
    except Exception as exc:                                   # noqa: BLE001
        saida["erros"].append(f"geração: {type(exc).__name__}: {exc}")

    fim, horarios, piso_somado = None, None, False
    for canal in CANAIS:
        f = lote.get(canal) or {}
        videos = f.get("videos")
        contou = (isinstance(videos, int) and not isinstance(videos, bool)
                  and videos >= 0)
        alvo = f.get("alvo") if isinstance(f.get("alvo"), int) else None
        faltam = f.get("faltam") if contou and alvo is not None else None
        ficha = {
            "videos": videos if contou else None,
            "dias": float(f.get("dias") or 0) if contou else None,
            "piso": f.get("piso") if isinstance(f.get("piso"), int) else None,
            "alvo": alvo,
            "faltam": faltam,
            "contou": contou,
            # a regra do piso e a do `postar` (`magro`); zero e magro
            "magro": bool(contou and f.get("magro")),
            "janela": _janela(configs.get(canal)),
            "dias_de_lote": _dias_de_lote(configs.get(canal)),
        }
        ficha["situacao"] = _situacao(ficha)
        ficha["texto"] = _texto_do_canal(ficha)
        saida["canais"][canal] = ficha
        if f.get("fim") is not None and fim is None:
            fim, horarios = f.get("fim"), f.get("horarios")
            piso_somado = alvo is not None and alvo != horarios

    if isinstance(fim, datetime) and horarios is not None:
        saida["cobertura"] = (f"alvo = {horarios} horário(s) até "
                              f"{_quando(fim, hora=True)}"
                              + (" + piso" if piso_somado else ""))
    if agenda is not None:
        try:
            saida["calendario"] = _calendario(agenda, configs["historias"],
                                              agora)
        except Exception as exc:                               # noqa: BLE001
            saida["erros"].append(
                f"calendário: {type(exc).__name__}: {exc}")
    return saida


# ------------------------------------------------------------ o Telegram
def _escapar(texto: str) -> str:
    """Markdown do Telegram: dois `_` num id viram italico e somem texto."""
    for sinal in ("\\", "_", "*", "`", "["):
        texto = texto.replace(sinal, "\\" + sinal)
    return texto


def linhas(dados: dict) -> list[str]:
    """O resumo em Markdown do Telegram: cabeca, um canal por linha, datas."""
    cabeca = "*Lote da semana*"
    if dados.get("cobertura"):
        cabeca += f" — {dados['cobertura']}"
    saida = [cabeca]
    canais = dados.get("canais") or {}
    for canal, ficha in CANAIS.items():
        f = canais.get(canal)
        texto = f["texto"] if f else SEM_CONTA
        saida.append(f"  {ficha['emoji']} {ficha['rotulo']}: {texto}")
    if dados.get("calendario"):
        saida.append(f"  {dados['calendario']}")
    for erro in (dados.get("erros") or [])[:3]:
        saida.append(f"  ⚠ não consegui ler {_escapar(erro)[:110]}")
    return saida


def texto(agora: datetime | None = None) -> str:
    """O /lote do bot. So leitura."""
    try:
        return "\n".join(linhas(resumo(agora)))
    except Exception as exc:                                   # noqa: BLE001
        return (f"*Lote da semana* — {SEM_CONTA} "
                f"({type(exc).__name__})")
