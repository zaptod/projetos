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


# A RECUSA ENLATADA DO GEMINI (27/09/2026). Nao e o modelo julgando e
# dizendo nao: e uma frase de uma lista fixa, sorteada, que o site poe no
# lugar da resposta. Medidas nos logs de 13 a 27/09: "Sou uma IA com base em
# texto, e isso esta alem das minhas capacidades", "Nao fui programado para
# fazer isso", "Sou apenas um modelo de linguagem...", "Nao consigo criar esse
# tipo de video". Veio com o mp4 anexado E sem anexo nenhum (a reescrita de
# prompt das 02:18 de 27/09). No parecer, e o VIDEO do lado do Google: o mesmo
# pedido sem o video nao foi recusado, e a taxa e por video (a `00034 p04`
# 1 de 7 tentativas assistidas, a `00034 p01` 6 de 7), em rajadas.
RECUSA_ENLATADA = re.compile(
    r"modelo\s+de\s+linguagem"
    r"|ia\s+(?:com\s+)?base(?:ada)?\s+em\s+texto"
    # "Nao fui programado", e em 28/09 00:07 "Fui criado apenas para
    # processar e gerar texto": a lista do site e maior que a amostra.
    r"|fui\s+(?:programad|criad|treinad|feit)[oa]"
    r"|(?:processar|gerar)\s+(?:e\s+(?:processar|gerar)\s+)?texto"
    r"|al[eé]m\s+das\s+minhas\s+(?:capacidades|habili)"
    r"|n[aã]o\s+consigo\s+criar\s+(?:esse|este)\s+tipo"
    r"|n[aã]o\s+(?:tenho\s+como|consigo|posso)\s+(?:te\s+)?ajudar"
    r"|language\s+model|text[-\s]based\s+ai|not\s+programmed\s+to"
    r"|outside\s+(?:of\s+)?my\s+capabilities",
    re.IGNORECASE)
# A frase enlatada e curta (43 a 121 caracteres nas 18 medidas). Um texto
# longo que cita "language model" e resposta de verdade, nao recusa.
RECUSA_MAXIMA = 300


def e_recusa_enlatada(texto) -> bool:
    """A resposta e a frase fixa de "isso eu nao faco"? Nunca levanta."""
    limpo = " ".join(str(texto or "").split())
    if not limpo or len(limpo) > RECUSA_MAXIMA:
        return False
    return bool(RECUSA_ENLATADA.search(limpo))
