# -*- coding: utf-8 -*-
"""A parte escrita e mesmo DESTA historia?

NAO confundir com `coerencia.py`, que e vizinho e responde outra pergunta:
la os NUMEROS da historia batem entre si (aluguel de 3.800 na parte 1 e 5.000
na parte 2); aqui o TEXTO e da historia certa.

O QUE ACONTECEU, e nao e hipotese (11/09/2026). A `historia_00005` e um
desabafo de um homem que esconde da esposa quem paga o apartamento. As partes
3 a 6 foram para o disco com os prompts de imagem assim:

    cena 1  "Gameplay de parkour no Minecraft, pulando entre blocos de areia."
    cena 2  "O jogador quase cai, mas consegue pular para o proximo bloco."
    cena 3  "O jogador entra numa caverna escura e acende uma tocha."

A parte 3 era pior ainda: a NARRACAO tambem era de outra historia (uma mulher
achando uma arma enrolada numa toalha). Texto de um assunto, imagem de outro,
nenhum dos dois da serie.

A causa e conhecida e ja foi consertada uma vez: em chat com varios turnos, o
seletor pegava a resposta ANTERIOR. O que nao existia era rede embaixo — o
unico criterio para aceitar uma parte era CONTAR CENAS. Com 14 cenas de
Minecraft ela passava, virava video, e ia ao ar. A parte 3 foi publicada no
YouTube e no TikTok as 15:08 de 11/09/2026 antes de alguem ver.

O sinal usado aqui e barato e foi o que denunciou tudo: o contrato manda o
prompt de imagem em INGLES ("IMAGEM: <prompt em ingles>"), e as 56 cenas
contaminadas estavam em portugues. Nao e um detector de assunto — e um
detector de TEXTO QUE VEIO DE OUTRO LUGAR, que e o defeito real.

Deliberadamente NAO se tenta adivinhar tema. Um classificador de assunto
erraria nos dois sentidos e ninguem confiaria nele; este aqui responde uma
pergunta fechada, com um numero, e por isso pode bloquear publicacao.
"""
from __future__ import annotations

import re

# Palavras-funcao, nao conteudo: elas aparecem em qualquer frase da lingua e
# nao dependem do assunto da historia.
PT = re.compile(
    r"\b(o|a|os|as|um|uma|uns|umas|de|da|do|das|dos|na|no|nas|nos|em|que|"
    r"com|para|pra|por|ele|ela|eles|elas|seu|sua|mas|quando|enquanto|"
    r"sobre|entre|ate|depois|antes|onde|tela|cena|plano)\b", re.I)
EN = re.compile(
    r"\b(the|a|an|of|in|on|at|with|and|or|his|her|their|its|to|from|"
    r"into|over|under|while|as|is|are|was|were|wearing|holding|standing|"
    r"sitting|looking|close|shot|view)\b", re.I)

# Abaixo disto a parte e recusada. Nao e 100% de proposito: uma cena pode
# citar um nome proprio portugues ("Marginal Tiete") sem que a parte esteja
# contaminada, e recusar a parte inteira por uma cena seria pior do que o
# problema. Com 14 cenas, isto tolera 4 duvidosas.
MINIMO_EM_INGLES = 0.70


def _ingles(texto: str) -> bool | None:
    """`True` ingles, `False` portugues, `None` curto demais para dizer."""
    limpo = str(texto or "").strip()
    if len(limpo.split()) < 4:
        return None
    pt, en = len(PT.findall(limpo)), len(EN.findall(limpo))
    if pt == en:
        return None
    return en > pt


def fracao_em_ingles(cenas: list) -> float | None:
    """Que fatia dos prompts de imagem esta em ingles. `None` sem amostra."""
    votos = [_ingles(c.get("imagem")) for c in cenas or []]
    votos = [v for v in votos if v is not None]
    if not votos:
        return None
    return sum(1 for v in votos if v) / len(votos)


def problemas(cenas: list, *, minimo: float = MINIMO_EM_INGLES) -> list[str]:
    """Os motivos para NAO aceitar estas cenas. Lista vazia = pode seguir."""
    achados = []
    if not cenas:
        return ["nenhuma cena"]
    sem_imagem = [c.get("n") for c in cenas if not str(c.get("imagem") or "").strip()]
    if sem_imagem:
        achados.append(f"cenas sem prompt de imagem: {sem_imagem[:6]}")
    sem_narracao = [c.get("n") for c in cenas
                    if not str(c.get("narracao") or "").strip()]
    if sem_narracao:
        achados.append(f"cenas sem narracao: {sem_narracao[:6]}")
    fatia = fracao_em_ingles(cenas)
    if fatia is not None and fatia < minimo:
        achados.append(
            f"so {fatia * 100:.0f}% dos prompts de imagem estao em ingles "
            f"(minimo {minimo * 100:.0f}%). O contrato pede ingles, entao "
            "portugues aqui e texto que veio de OUTRA conversa — foi assim "
            "que 56 cenas de Minecraft entraram na historia_00005.")
    return achados


def parte_confiavel(cenas: list) -> bool:
    return not problemas(cenas)


__all__ = ["problemas", "parte_confiavel", "fracao_em_ingles",
           "MINIMO_EM_INGLES"]
