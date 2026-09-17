# -*- coding: utf-8 -*-
"""Quem faz o que entre os LLMs: a lista de provedores de cada PAPEL.

Decisao do Adrian (16/09/2026): o DeepSeek ESCREVE os roteiros e o Gemini e o
ChatGPT ficam para a ANALISE de qualidade. Cada provedor tem conta e trava
proprias, entao escrever uma historia e analisar outra deixam de disputar o
mesmo navegador.

O nome do provedor mora no `config/llm.json`, nunca no codigo de quem chama:

    {"papeis": {"roteiro": ["deepseek", "gemini"], ...}}

A lista e uma ORDEM DE QUEDA: o primeiro tenta, e se falhar o proximo
assume (e isso fica registrado no diario e no roteiro).
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / "config" / "llm.json"

ROTEIRO = "roteiro"            # biblia, aberturas, partes e revisao por parte
QUALIDADE = "qualidade"        # parecer de folha/video e conserto de cena
IMAGEM_PROMPT = "imagem_prompt"  # reescrever o prompt que o PicassoIA recusou

# O comportamento de ANTES desta mudanca, para config ausente ou torto.
PADRAO = {
    ROTEIRO: ["gemini"],
    QUALIDADE: ["gemini", "chatgpt"],
    IMAGEM_PROMPT: ["chatgpt"],
}
CONHECIDOS = ("deepseek", "gemini", "chatgpt")


def carregar(caminho: Path | None = None) -> dict:
    """`{papel: [provedores]}`. Nunca levanta: config ilegivel = padrao."""
    try:
        with open(caminho or ARQUIVO, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        dados = {}
    papeis = dados.get("papeis") if isinstance(dados, dict) else None
    saida = {k: list(v) for k, v in PADRAO.items()}
    if isinstance(papeis, dict):
        for papel, lista in papeis.items():
            limpa = _limpar(lista)
            if limpa:
                saida[str(papel)] = limpa
    return saida


def _limpar(lista) -> list:
    """Nomes conhecidos, minusculos, sem repetir, na ordem dada."""
    if isinstance(lista, str):
        lista = [lista]
    if not isinstance(lista, (list, tuple)):
        return []
    saida = []
    for nome in lista:
        nome = str(nome or "").strip().lower()
        if nome in CONHECIDOS and nome not in saida:
            saida.append(nome)
    return saida


def provedores(papel: str, *, papeis: dict | None = None) -> list:
    """A ordem de queda daquele papel. Papel desconhecido: lista vazia."""
    papeis = carregar() if papeis is None else papeis
    return list(papeis.get(papel) or [])


def com_preferido(preferido: str | None, lista) -> list:
    """`preferido` primeiro, depois o resto da lista, sem repetir.

    Serve a retomada: a historia que o DeepSeek comecou continua com ele (o
    estilo e dele), e so cai para o proximo se ele falhar.
    """
    ordem = _limpar([preferido]) if preferido else []
    for nome in _limpar(list(lista or [])):
        if nome not in ordem:
            ordem.append(nome)
    return ordem


def ajustes(provedor: str, caminho: Path | None = None) -> dict:
    """O bloco daquele provedor no `config/llm.json` (ex.: `deepthink`)."""
    try:
        with open(caminho or ARQUIVO, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {}
    bloco = dados.get(str(provedor).lower()) if isinstance(dados, dict) else None
    return dict(bloco) if isinstance(bloco, dict) else {}
