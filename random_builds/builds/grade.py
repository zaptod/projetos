# -*- coding: utf-8 -*-
"""A grade do dia: a que horas sai video, e quantos.

UM lugar so. Ate 11/09/2026 a mesma tupla `(6, 7, 8, 10, 12, 15, 17, 20)`
estava escrita em `ferramentas/postar.py` e em `remoto/relatorios.py`, e a
auditoria ia escrever a terceira. Duas copias ja bastam para o relatorio dizer
"bateu a meta" enquanto a postagem trabalha com outro horario — e quem ler as
duas telas nao tem como saber qual esta certa.

Mora em `builds` porque e o pacote que todos importam (`contos` inclusive), e
porque a grade nao e de um canal: os dois publicam nos mesmos horarios.
"""
from __future__ import annotations

from datetime import datetime

# Oito horarios, espalhados pelo dia. Nao e "de duas em duas horas": a manha
# e mais densa de proposito (6, 7, 8) porque e quando o feed roda mais.
HORAS = (6, 7, 8, 10, 12, 15, 17, 20)
# :07 e nao :00 — horario redondo e quando todo mundo publica.
MINUTO = 7

# Quantos videos cada canal deve por no ar por dia. E len(HORAS) por
# definicao: um video por canal por horario.
META_DIARIA_POR_CANAL = len(HORAS)
CANAIS = ("historias", "builds")
PLATAFORMAS = ("youtube", "tiktok")
# Cada video vai aos dois lugares, entao a conta cheia do dia e esta.
META_DIARIA_TOTAL = META_DIARIA_POR_CANAL * len(CANAIS) * len(PLATAFORMAS)


def horarios() -> list[str]:
    """`['06:07', '07:07', ...]` — a grade como ela aparece nas telas."""
    return [f"{h:02d}:{MINUTO:02d}" for h in HORAS]


def vencidos(agora: datetime | None = None) -> list[int]:
    """As horas da grade que JA passaram hoje.

    E contra esta lista que se mede o dia. Comparar com as oito o dia inteiro
    faria o relatorio das 09:00 acusar seis horarios perdidos que ainda nem
    chegaram.
    """
    agora = agora or datetime.now()
    minuto = agora.hour * 60 + agora.minute
    return [h for h in HORAS if h * 60 + MINUTO <= minuto]


def proximo(agora: datetime | None = None) -> str:
    """O proximo horario da grade, com a marca de amanha quando virou o dia."""
    agora = agora or datetime.now()
    minuto = agora.hour * 60 + agora.minute
    for h in HORAS:
        if h * 60 + MINUTO > minuto:
            return f"{h:02d}:{MINUTO:02d}"
    return f"{HORAS[0]:02d}:{MINUTO:02d} (amanha)"


__all__ = ["HORAS", "MINUTO", "META_DIARIA_POR_CANAL", "META_DIARIA_TOTAL",
           "CANAIS", "PLATAFORMAS", "horarios", "vencidos", "proximo"]
