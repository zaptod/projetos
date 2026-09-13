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

CANAIS = ("historias", "builds")
PLATAFORMAS = ("youtube", "tiktok")

# O TIKTOK NAO POSTA EM TODOS OS HORARIOS. Medido em 13/09/2026 nas duas
# contas: em todas as cinco sessoes com mais de seis posts, so os seis
# primeiros tiveram distribuicao (80 a 180 views); do setimo em diante, 1 ou
# 2 views, ate uma pausa longa sem postar. Oito por dia deixava a conta nessa
# faixa quase o dia inteiro. E correlacao, nao causa provada — por isso a
# coleta de metricas do TikTok continua de pe para confirmar ou desmentir.
#
# Decisao dele no mesmo dia: seis, pulando 7h e 8h, que sao os horarios
# colados, e preservando a pausa de dez horas durante a noite. O YouTube
# segue com os oito.
HORAS_POR_PLATAFORMA = {
    "youtube": HORAS,
    "tiktok": (6, 10, 12, 15, 17, 20),
}

# Quantos videos cada canal deve por no ar por dia, POR PLATAFORMA.
META_DIARIA_POR_PLATAFORMA = {p: len(h) for p, h in HORAS_POR_PLATAFORMA.items()}
# Os horarios da grade de um canal: um video por horario no YouTube, que e o
# destino que usa todos.
META_DIARIA_POR_CANAL = len(HORAS)
# A conta cheia do dia: cada canal, cada plataforma, com a grade de cada uma.
META_DIARIA_TOTAL = len(CANAIS) * sum(META_DIARIA_POR_PLATAFORMA[p]
                                      for p in PLATAFORMAS)


def horas_da_plataforma(plataforma: str = "youtube") -> tuple:
    """Os horarios em que ESSA plataforma recebe video."""
    return HORAS_POR_PLATAFORMA.get(str(plataforma).lower(), HORAS)


def publica_em(plataforma: str, hora: int) -> bool:
    """Essa plataforma posta no horario `hora`?"""
    return int(hora) in horas_da_plataforma(plataforma)


def horarios(plataforma: str | None = None) -> list[str]:
    """`['06:07', '07:07', ...]` — a grade como ela aparece nas telas."""
    horas = HORAS if plataforma is None else horas_da_plataforma(plataforma)
    return [f"{h:02d}:{MINUTO:02d}" for h in horas]


def vencidos(agora: datetime | None = None,
             plataforma: str | None = None) -> list[int]:
    """As horas da grade que JA passaram hoje.

    E contra esta lista que se mede o dia. Comparar com as oito o dia inteiro
    faria o relatorio das 09:00 acusar seis horarios perdidos que ainda nem
    chegaram. Com `plataforma`, so os horarios dela: o TikTok nao deve o que
    nunca foi da grade dele.
    """
    agora = agora or datetime.now()
    minuto = agora.hour * 60 + agora.minute
    horas = HORAS if plataforma is None else horas_da_plataforma(plataforma)
    return [h for h in horas if h * 60 + MINUTO <= minuto]


def proximo(agora: datetime | None = None) -> str:
    """O proximo horario da grade, com a marca de amanha quando virou o dia."""
    agora = agora or datetime.now()
    minuto = agora.hour * 60 + agora.minute
    for h in HORAS:
        if h * 60 + MINUTO > minuto:
            return f"{h:02d}:{MINUTO:02d}"
    return f"{HORAS[0]:02d}:{MINUTO:02d} (amanha)"


__all__ = ["HORAS", "MINUTO", "META_DIARIA_POR_CANAL", "META_DIARIA_TOTAL",
           "META_DIARIA_POR_PLATAFORMA", "HORAS_POR_PLATAFORMA", "CANAIS",
           "PLATAFORMAS", "horarios", "horas_da_plataforma", "publica_em",
           "vencidos", "proximo"]
