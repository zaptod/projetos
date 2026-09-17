# -*- coding: utf-8 -*-
"""A resposta do LLM antes do parser: tira o que e ENFEITE do site.

O DeepSeek (16/09/2026) escreve em markdown mais carregado que o Gemini
(`### CENA 3`, citacao com `>`, linhas `---`, italico) e, com o DeepThink
ligado, pode deixar o RACIOCINIO na mesma pagina da resposta. O parser dos
roteiros ja tolera `**`, `#` e marcador de lista; o que ficava de fora e
tratado aqui, sem tocar no conteudo das linhas.

O RACIOCINIO NUNCA ENTRA NO ROTEIRO. Um paragrafo de "vou pensar em como a
protagonista reage" lido como narracao viraria fala no video.
"""
from __future__ import annotations

import re

# `<think>...</think>`: a forma do raciocinio quando ele vem no mesmo texto.
PENSAMENTO = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
# O rotulo que o site poe acima do raciocinio ("Thought for 12 seconds").
# SO A LINHA INTEIRA NESSAS FORMAS: "Pensando bem, ..." e narracao.
ROTULO_DE_PENSAMENTO = re.compile(
    r"^\s*(?:(?:thought|pensou|raciocinou)\s+(?:for|por)\s+[\d.,]+\s*"
    r"(?:s|sec|secs|seconds?|segundos?|min|minutos?)\.?"
    r"|thinking\.{0,3}|pensando\.{0,3}"
    r"|(?:deepthink|pensamento profundo)(?:\s*\(r1\))?\s*"
    r"(?:conclu[ií]do|completed?)?\.?)\s*$",
    re.IGNORECASE | re.MULTILINE)
REGUA = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE)
CITACAO = re.compile(r"^\s*>\s?", re.MULTILINE)
CABECALHO = re.compile(r"^\s*#{1,6}\s+", re.MULTILINE)
# `*CENA 3*` ou `_Titulo:_` de ponta a ponta — italico de linha inteira.
ITALICO_DA_LINHA = re.compile(r"^(\s*)[*_](?![*_\s])(.+?)(?<![*_\s])[*_](\s*)$",
                              re.MULTILINE)
# `**NARRAÇÃO:** *texto*` — o italico e do VALOR, depois do rotulo.
ITALICO_DO_VALOR = re.compile(
    r"^([^\n:]{1,40}:\**\s*)[*_](?![*_\s])([^\n]+?)(?<![*_\s])[*_](\s*)$",
    re.MULTILINE)


def limpar_resposta(texto: str) -> str:
    """O texto sem raciocinio e sem enfeite de markdown. Nunca levanta."""
    texto = str(texto or "").replace("\r\n", "\n")
    texto = PENSAMENTO.sub("", texto)
    # Um `<think>` aberto e nunca fechado (resposta cortada no meio do
    # raciocinio): nada dali em diante e resposta.
    aberto = re.search(r"<think>", texto, re.IGNORECASE)
    if aberto:
        texto = texto[:aberto.start()]
    texto = ROTULO_DE_PENSAMENTO.sub("", texto)
    texto = REGUA.sub("", texto)
    texto = CITACAO.sub("", texto)
    texto = CABECALHO.sub("", texto)
    texto = ITALICO_DO_VALOR.sub(r"\1\2\3", texto)
    texto = ITALICO_DA_LINHA.sub(r"\1\2\3", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()
