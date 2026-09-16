# -*- coding: utf-8 -*-
"""Quanto tempo cada etapa levou, por dia — e o que piorou.

Por que existe: ate 16/09/2026 nao havia UM campo de duracao por etapa em
todo o repositorio. O unico cronometro era o da rodada inteira
(`agenda.rodar`), e ele ia para o TEXTO do Telegram, nunca para disco. Os
numeros que o projeto repetia ("2h12 por historia", "84 imagens em 3h13")
eram comentarios escritos a mao no config, nao medicoes. Otimizar assim
seria trocar um palpite por outro.

Por que consolidar, em vez de so ler o diario: `atividade.jsonl` e podado
acima de 4000 linhas para 2000. Com instrumentacao fina isso e menos de um
dia — um jsonl podado nao e serie temporal. Entao uma vez por noite o dia
que passou vira um arquivo proprio, que ninguem poda.

Este modulo ESCREVE, e por isso mora aqui e nao no `panorama`, que e so
leitura.

    from builds import tempos
    tempos.consolidar()            # fecha o dia de ontem
    tempos.series(dias=14)         # a evolucao, para ver o que piorou
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import atividade, contas


def pasta() -> Path:
    return contas.runtime_dir() / "tempos"


def _arquivo(dia: str) -> Path:
    return pasta() / f"{dia}.json"


def _dia_de(ts: str) -> str:
    """O dia LOCAL do evento. O diario grava em UTC."""
    try:
        quando = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return ""
    if quando.tzinfo is not None:
        quando = quando.astimezone()
    return quando.date().isoformat()


def _percentil(valores: list, p: float) -> float:
    """Percentil simples, sem numpy. Lista ja ordenada."""
    if not valores:
        return 0.0
    if len(valores) == 1:
        return round(float(valores[0]), 1)
    posicao = (len(valores) - 1) * p
    baixo = int(posicao)
    alto = min(baixo + 1, len(valores) - 1)
    peso = posicao - baixo
    return round(valores[baixo] * (1 - peso) + valores[alto] * peso, 1)


def resumir(eventos) -> dict:
    """As fichas por `canal/fabrica/etapa`, a partir de eventos do diario.

    Funcao PURA: e por isso que `consolidar` a chama em vez de fazer a conta
    dentro do laco de leitura — assim ela se testa com lista na mao, sem
    disco e sem relogio.
    """
    baldes: dict = {}
    for ev in eventos or ():
        if not isinstance(ev, dict):
            continue
        if ev.get("dur_s") is None:
            continue
        status = ev.get("status")
        if status not in (atividade.OK, atividade.ERRO, atividade.LOG):
            continue
        chave = "/".join((str(ev.get("canal") or "?"),
                          str(ev.get("fabrica") or "?"),
                          str(ev.get("etapa") or "")))
        ficha = baldes.setdefault(chave, {"n": 0, "ok": 0, "erro": 0,
                                          "_v": [], "refs": set()})
        ficha["n"] += 1
        ficha["erro" if status == atividade.ERRO else "ok"] += 1
        ficha["_v"].append(float(ev["dur_s"]))
        if ev.get("ref"):
            ficha["refs"].add(str(ev["ref"]))

    etapas = {}
    for chave, ficha in sorted(baldes.items()):
        valores = sorted(ficha["_v"])
        etapas[chave] = {
            "n": ficha["n"], "ok": ficha["ok"], "erro": ficha["erro"],
            "p50": _percentil(valores, 0.5),
            "p90": _percentil(valores, 0.9),
            "max": round(valores[-1], 1),
            # `total_s` e o que responde "onde o dia foi embora" — e o que a
            # mediana esconde quando algo e barato e acontece 84 vezes.
            "total_s": round(sum(valores), 1),
            "refs": len(ficha["refs"]),
        }
    return etapas


def consolidar(dia: str | None = None, *, eventos=None) -> Path:
    """Fecha um dia num arquivo proprio. Idempotente: reescreve o do dia.

    Sem `dia`, fecha ONTEM — o dia de hoje ainda esta acontecendo, e um
    arquivo de dia incompleto sendo reescrito o tempo todo confunde quem le
    a serie.
    """
    if dia is None:
        dia = (date.today() - timedelta(days=1)).isoformat()
    if eventos is None:
        eventos = [ev for ev in atividade.recentes(100000)
                   if _dia_de(ev.get("ts")) == dia]
    ficha = {
        "dia": dia,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "etapas": resumir(eventos),
    }
    destino = _arquivo(dia)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(ficha, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return destino


def carregar(dia: str) -> dict:
    """A ficha daquele dia, ou `{}`. Nunca levanta."""
    try:
        return json.loads(_arquivo(dia).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def series(dias: int = 14) -> dict:
    """{etapa: [ficha por dia, do mais velho ao mais novo]}.

    O dia sem medida entra como `None` em vez de sumir: buraco na serie e
    informacao (a maquina estava desligada, a rodada nao correu), e fechar
    o buraco faria duas semanas parecerem continuas quando nao foram.
    """
    hoje = date.today()
    ordem = [(hoje - timedelta(days=n)).isoformat()
             for n in range(dias, 0, -1)]
    fichas = {d: carregar(d).get("etapas") or {} for d in ordem}
    nomes = sorted({etapa for f in fichas.values() for etapa in f})
    return {etapa: [fichas[d].get(etapa) for d in ordem] for etapa in nomes}


def piorou(dias: int = 14, *, minimo: int = 3) -> list:
    """As etapas cuja mediana subiu do primeiro ao ultimo dia com medida.

    `minimo` e quantos dias com medida a etapa precisa ter para entrar: com
    dois pontos qualquer coisa "piorou 40%", e um alarme que dispara sempre
    e um alarme que ninguem le.
    """
    achados = []
    for etapa, linha in series(dias).items():
        medidos = [f for f in linha if f]
        if len(medidos) < minimo:
            continue
        antes, agora = medidos[0]["p50"], medidos[-1]["p50"]
        if antes <= 0 or agora <= antes:
            continue
        achados.append({"etapa": etapa, "de": antes, "para": agora,
                        "vezes": round(agora / antes, 2),
                        "dias": len(medidos)})
    return sorted(achados, key=lambda a: a["vezes"], reverse=True)


__all__ = ["carregar", "consolidar", "pasta", "piorou", "resumir", "series"]
