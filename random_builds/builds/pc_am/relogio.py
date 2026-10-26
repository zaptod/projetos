# -*- coding: utf-8 -*-
"""O PONTO UNICO do relogio do PC am: "agora pode mandar trabalho pesado?".

Por que o am respeita a janela das postagens, se o trabalho roda LA: o envio
do codigo e das entradas e a busca do produto passam pela mesma rede (Wi-Fi
deste PC) por onde sobe o video da postagem, e o `git diff`/zip sao daqui.
A lei (CLAUDE.md, secao 4): nada pesado de `post-12` a `post+18` min.

A fonte e a TRAVA CENTRAL `builds.janela.em_janela` (26/10/2026: uma
conta so, com as grades reais de cada canal e a publicacao em voo). Para
trocar a regra, e so aqui:

  1. `builds.janela.em_janela`               (a central; preferida)
  2. `bluelock.comum.janela_das_postagens`   (so o relogio; se a central nao importa)
  3. `builds.grade` (post-12..post+18)       (ultimo recurso, sem o coordenador)

Nao consegui ler nenhuma das tres = NAO libera (mesmo criterio do
`bluelock.comum.pode_pesado`): na duvida, espera.
"""
from __future__ import annotations

from datetime import datetime, timedelta

ANTES_MIN = 12
DEPOIS_MIN = 18


def _pela_central(agora):
    from .. import janela
    dentro, motivo, _ate = janela.em_janela(agora, antes=ANTES_MIN, depois=DEPOIS_MIN)
    return dentro, motivo


def _pelo_bluelock(agora):
    from bluelock import comum
    return comum.janela_das_postagens(agora)


def _pela_grade(agora):
    from .. import grade
    for hora, minuto in grade.GRADE:
        post = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        for dia in (-1, 0, 1):
            p = post + timedelta(days=dia)
            if p - timedelta(minutes=ANTES_MIN) <= agora < p + timedelta(minutes=DEPOIS_MIN):
                return True, f"janela das postagens ({p:%H:%M})"
    return False, ""


FONTES = (_pela_central, _pelo_bluelock, _pela_grade)


def liberado(agora: datetime | None = None, *, fontes=None) -> tuple[bool, str]:
    """(pode, motivo). Motivo vazio quando pode."""
    agora = agora or datetime.now()
    erro = None
    for fonte in (fontes or FONTES):
        try:
            dentro, motivo = fonte(agora)
        except Exception as exc:                               # noqa: BLE001
            erro = f"{type(exc).__name__}: {exc}"
            continue
        return (not dentro), (motivo if dentro else "")
    return False, f"nao consegui ler a grade das postagens ({erro})"
