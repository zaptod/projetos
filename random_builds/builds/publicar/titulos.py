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


def _publicado(linha) -> bool:
    # Import tardio: `metricas` importa este modulo.
    from .metricas import publicado
    return publicado(linha)


# O corte em 60 e o do criterio original: o Studio devolve o titulo que ele
# ACEITOU (corta em 100), e comparar o rabo de dois titulos longos gera mais
# falso negativo do que acerto.
TAMANHO = 60


# O "(Parte 3/6)" do fim do titulo, em qualquer das formas que o projeto usa.
# E a UNICA diferenca entre duas partes da mesma serie, e por isso ele nao
# pode ser o pedaco que o corte joga fora.
PARTE = re.compile(r"\(?\s*parte\s*(\d+)\s*[/de]{1,2}\s*(\d+)\s*\)?\s*$",
                   re.IGNORECASE)


def chave(texto: str) -> str:
    """Titulo comparavel: sem acento de pontuacao, sem emoji, sem caixa.

    O SUFIXO DA PARTE SOBREVIVE AO CORTE. Medido em 17/09/2026: o corte em 60
    caracteres ainda nao colidia por sorte — a diferenca entre as partes cai
    antes do limite em 13 das 14 series, e a 14a estava a 3 caracteres. Com o
    formato de titulo-pergunta que esta chegando ("Eu sou o babaca por nao
    deixar minha irma usar o vestido de noiva da nossa mae?"), as SEIS partes
    dao a MESMA chave.

    Isso era inofensivo enquanto a valvula de titulo repetido apenas avisava.
    Desde que ela fecha (17/09), duas partes com a mesma chave viram uma
    serie que PARA na parte 1 — e ninguem descobre, porque o sintoma e um
    horario vazio, nao um erro.

    Entao o corte passa a comer o corpo do titulo, nunca a parte.
    """
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip().lower()
    achado = PARTE.search(limpo)
    sufixo = ""
    if achado:
        limpo = limpo[:achado.start()].strip()
        sufixo = f" parte {achado.group(1)} de {achado.group(2)}"
    limpo = "".join(c for c in limpo if c.isalnum() or c.isspace())
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return (limpo[:max(0, TAMANHO - len(sufixo))] + sufixo).strip()


def ja_publicados(linhas) -> set:
    """As chaves de titulo que ja foram ao ar, vindas do ledger.

    So conta linha que de fato saiu (`metricas.publicado`) — uma linha sem
    destino nao ocupou lugar nenhum no canal e nao deve barrar ninguem.
    """
    vistos = set()
    for linha in linhas or ():
        if not isinstance(linha, dict) or not _publicado(linha):
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
