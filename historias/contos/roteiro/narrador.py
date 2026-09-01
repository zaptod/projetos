# -*- coding: utf-8 -*-
"""Quem narra a história — e, por consequência, com que voz.

A história é contada em PRIMEIRA PESSOA. Até 01/09/2026 todas saíam na
mesma voz masculina (`pt-BR-AntonioNeural`, catalogada pelo motor como
*Friendly, Positive*), independentemente de quem estivesse falando. Numa
história de desabafo narrada por uma mulher, ou num relato tenso lido em tom
de propaganda, o ouvido percebe a mentira antes da segunda frase — e não
perdoa.

Como a bíblia da série já fixa a descrição FÍSICA do protagonista em inglês
(é ela que mantém as imagens parecidas entre as cenas), dá para descobrir
quem narra sem pedir nada novo: `A 29-year-old man with short dark curly
hair` diz homem, e diz a idade.

O catálogo é curto de propósito: o motor gratuito só oferece três vozes em
pt-BR. Escolher bem entre três já resolve o problema; inventar mais seria
prometer o que não existe.
"""
from __future__ import annotations

import re
import unicodedata

# O que o edge-tts realmente tem em pt-BR (conferido em 01/09/2026).
VOZES = {
    "homem": "pt-BR-AntonioNeural",
    "mulher": "pt-BR-FranciscaNeural",
    "mulher_alt": "pt-BR-ThalitaMultilingualNeural",
}
PADRAO = "homem"

# Pistas na descrição física (inglês) e no texto em português.
HOMEM = (r"\b(man|male|boy|guy|father|dad|husband|son|brother|grandfather"
         r"|his)\b|homem|rapaz|garoto|pai\b|marido|filho\b|irmao|irmão")
MULHER = (r"\b(woman|female|girl|lady|mother|mom|wife|daughter|sister"
          r"|grandmother|her)\b|mulher|moca|moça|garota|mae\b|mãe|esposa"
          r"|filha|irma\b|irmã")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


def quem_narra(roteiro: dict) -> str:
    """"homem" ou "mulher", lido do roteiro (nunca levanta).

    Um campo explícito vence a adivinhação: se a bíblia disser, é isso.
    """
    explicito = _sem_acento(roteiro.get("narrador") or "").strip()
    if explicito.startswith(("mulher", "fem", "f")):
        return "mulher"
    if explicito.startswith(("homem", "masc", "m")):
        return "homem"

    descricao = _sem_acento(roteiro.get("protagonista") or "")
    if not descricao:
        return PADRAO
    # Conta as pistas em vez de aceitar a primeira: "her husband" tem as
    # duas, e o que decide é quem aparece mais na descrição do PRÓPRIO
    # protagonista.
    homem = len(re.findall(HOMEM, descricao))
    mulher = len(re.findall(MULHER, descricao))
    if mulher > homem:
        return "mulher"
    if homem > mulher:
        return "homem"
    return PADRAO


def idade(roteiro: dict):
    """A idade aparente do protagonista, quando a descrição a informa."""
    achado = re.search(r"(\d{1,2})[\s-]*(?:year|anos|ano)",
                       _sem_acento(roteiro.get("protagonista") or ""))
    return int(achado.group(1)) if achado else None


def voz_para(roteiro: dict, cfg: dict) -> dict:
    """A config de voz DESTA história (a original não é modificada).

    Além da voz, ajusta o tom pela idade: um relato de alguém na casa dos
    cinquenta lido com a mesma altura de um de vinte soa jovem demais, e é
    esse tipo de desencontro que faz o vídeo parecer feito por máquina.
    """
    novo = dict(cfg or {})
    if not novo.get("por_narrador", True):
        return novo
    catalogo = {**VOZES, **(novo.get("vozes") or {})}
    quem = quem_narra(roteiro)
    novo["voz"] = catalogo.get(quem, catalogo.get(PADRAO))
    novo["narrador"] = quem

    anos = idade(roteiro)
    if anos and not str(novo.get("tom", "")).strip("+-0Hz "):
        if anos >= 45:
            novo["tom"] = "-4Hz"
        elif anos <= 24:
            novo["tom"] = "+3Hz"
    return novo
