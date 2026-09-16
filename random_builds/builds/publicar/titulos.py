# -*- coding: utf-8 -*-
"""Titulo comparavel — e a fila que nao repete titulo.

Por que existe (auditoria de 15/09/2026): 13 das 40 builds foram ao ar DUAS
vezes, com titulo identico, competindo entre si pelo mesmo termo de busca e
pela mesma recomendacao. Nao foi descuido de quem publicou: a deduplicacao
do projeto inteiro e por `video_id`, e a variante "gancho B" tem id com
sufixo `":B"` e o MESMO titulo. Para o codigo eram dois videos diferentes;
para o YouTube eram dois videos iguais.

A funcao `chave` nao e nova: ela morava em `metricas._chave_de_titulo`,
usada so para reconciliar id faltante. Ela foi MOVIDA para ca, e o nome
antigo ficou como apelido — inventar um segundo criterio de "titulo igual"
seria criar a proxima divergencia.

Este modulo nao le disco e nao sabe o que e um canal: recebe as linhas do
ledger e devolve conjuntos. E o que permite testa-lo sem tocar em nada.
"""
from __future__ import annotations

import re

# O corte em 60 e o do criterio original: o Studio devolve o titulo que ele
# ACEITOU (corta em 100), e comparar o rabo de dois titulos longos gera mais
# falso negativo do que acerto.
TAMANHO = 60


def chave(texto: str) -> str:
    """Titulo comparavel: sem acento de pontuacao, sem emoji, sem caixa."""
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip().lower()
    limpo = "".join(c for c in limpo if c.isalnum() or c.isspace())
    return re.sub(r"\s+", " ", limpo).strip()[:TAMANHO]


def ja_publicados(linhas) -> set:
    """As chaves de titulo que ja foram ao ar, vindas do ledger.

    So conta linha que de fato saiu (`url` preenchida) — uma linha sem
    destino nao ocupou lugar nenhum no canal e nao deve barrar ninguem.
    """
    vistos = set()
    for linha in linhas or ():
        if not isinstance(linha, dict) or not linha.get("url"):
            continue
        k = chave(linha.get("titulo"))
        if k:
            vistos.add(k)
    return vistos


def repetido(titulo: str, ja: set) -> bool:
    """Este titulo ja esta no ar?

    Titulo vazio NUNCA e repetido: `chave("")` e `chave("   ")` dao a mesma
    string vazia, e trata-la como igual barraria todo video sem titulo
    contra todo outro video sem titulo.
    """
    k = chave(titulo)
    return bool(k) and k in (ja or set())


__all__ = ["TAMANHO", "chave", "ja_publicados", "repetido"]
