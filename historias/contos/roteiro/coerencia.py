# -*- coding: utf-8 -*-
"""Numeros e datas que a historia cita mais de uma vez — e nao batem.

A biblia sempre segurou a consistencia VISUAL: a descricao fisica do
protagonista e repetida em toda cena, e por isso 84 imagens parecem a mesma
pessoa. Nada fazia o mesmo pelos FATOS, e eles derraparam sem ninguem ver.

Medido na historia 8 (02/09/2026):

    aluguel     "tres mil e oitocentos" (p01c04, p01c05, p06c10)
                "cinco mil reais"       (p02c01)
    encontro    "dois anos antes da gente se conhecer", com o primeiro
                pagamento em 2018 => 2020 (p02c06)
                "quando eu conheci o Tiago, no final de 2018" (p04c07)

Nenhum parser pega isso: as duas frases sao validas, bem escritas e cabem no
contrato. So a comparacao entre partes denuncia.

Este modulo confere a narracao contra a ficha de FATOS que a biblia fixou, e
aponta a cena exata. O que ele pega: o valor que ninguem fixou — foi assim que
"cinco mil" apareceu numa historia cujo aluguel era 3.800.

O QUE ELE NAO PEGA, e nao adianta fingir que pega: o numero certo usado para a
coisa errada. "2018" e um fato legitimo desta historia (o primeiro pagamento),
entao "quando eu conheci o Tiago, no final de 2018" passa aqui — sao os dois
o mesmo numero, e separar um do outro exige entender a frase. Contra esse caso
quem trabalha e o prompt: a ficha vai junto em toda parte, com o valor certo
ao lado do nome do fato, para o modelo nao precisar lembrar.
"""
from __future__ import annotations

import re
import unicodedata

# Numero por extenso ate as dezenas de milhar, que e o que aparece num relato
# ("tres mil e oitocentos", "cinco mil"). Acima disso ninguem fala por extenso.
UNIDADES = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20, "trinta": 30, "quarenta": 40,
    "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80,
    "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200,
    "trezentos": 300, "quatrocentos": 400, "quinhentos": 500,
    "seiscentos": 600, "setecentos": 700, "oitocentos": 800,
    "novecentos": 900,
}
# "quatro contos" = quatro mil, na boca de quem esta desabafando.
MIL = ("mil", "conto", "contos", "k")

ANO = re.compile(r"\b(?:19|20)\d{2}\b")
DINHEIRO_DIGITO = re.compile(
    r"r\$\s*([\d.]+(?:,\d{2})?)|\b(\d{1,3}(?:\.\d{3})+|\d{3,6})\s*"
    r"(?:reais|conto|contos|pila)\b")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


def _por_extenso(texto: str) -> list[int]:
    """Valores em dinheiro escritos por extenso: 'tres mil e oitocentos' -> 3800."""
    palavras = re.findall(r"[a-z]+", _sem_acento(texto))
    achados, i = [], 0
    while i < len(palavras):
        if palavras[i] not in UNIDADES:
            i += 1
            continue
        # <unidade> [e <unidade>]* mil [e <resto>]
        base, j = UNIDADES[palavras[i]], i + 1
        while j + 1 < len(palavras) and palavras[j] == "e" \
                and palavras[j + 1] in UNIDADES:
            base += UNIDADES[palavras[j + 1]]
            j += 2
        if j < len(palavras) and palavras[j] in MIL:
            total, j = base * 1000, j + 1
            while j + 1 < len(palavras) and palavras[j] == "e" \
                    and palavras[j + 1] in UNIDADES:
                total += UNIDADES[palavras[j + 1]]
                j += 2
            achados.append(total)
            i = j
            continue
        i += 1
    return achados


def _dinheiro(texto: str) -> list[int]:
    valores = []
    for bruto, simples in DINHEIRO_DIGITO.findall(_sem_acento(texto)):
        cru = (bruto or simples).replace(".", "").split(",")[0]
        if cru.isdigit():
            valores.append(int(cru))
    return valores + _por_extenso(texto)


def _anos(texto: str) -> list[int]:
    return [int(a) for a in ANO.findall(str(texto or ""))]


def citacoes(roteiro: dict) -> dict:
    """{'dinheiro': [(valor, 'p02c01')], 'ano': [...]} — tudo que a historia cita."""
    saida = {"dinheiro": [], "ano": []}
    for parte in roteiro.get("partes") or []:
        for cena in parte.get("cenas") or []:
            onde = "p%02dc%02d" % (int(parte["n"]), int(cena["n"]))
            texto = str(cena.get("narracao") or "")
            for valor in _dinheiro(texto):
                saida["dinheiro"].append((valor, onde))
            for valor in _anos(texto):
                saida["ano"].append((valor, onde))
    return saida


def valores_da_ficha(fatos: str) -> set:
    """Os numeros que a biblia FIXOU. E contra eles que a narracao e conferida."""
    declarados = set()
    for valor in _dinheiro(fatos) + _anos(fatos):
        declarados.add(valor)
    # "R$ 3.800" na ficha e "tres mil e oitocentos" na fala sao o mesmo numero,
    # e as duas formas passam pelo mesmo extrator — nao ha o que normalizar.
    for cru in re.findall(r"\d[\d.]*", str(fatos or "")):
        limpo = cru.replace(".", "")
        if limpo.isdigit():
            declarados.add(int(limpo))
    return declarados


def conferir(roteiro: dict) -> list[str]:
    """Avisos de coerencia. Lista vazia = nada que peca uma segunda olhada.

    A ficha de FATOS da biblia e a autoridade: ela existe justamente para que
    todo numero recorrente tenha UM valor. Entao a pergunta aqui e simples e
    de baixo ruido — que numero a narracao cita que a ficha nao fixou?

    Sem ficha (historias geradas antes de ela existir) nao da para julgar
    nada, e tentar adivinhar so produziria lista longa e inutil: uma historia
    cita dezenas de valores legitimamente diferentes. Nesse caso o aviso e um
    so, e a lista completa fica no `main.py conferir --numeros`.
    """
    partes = roteiro.get("partes") or []
    if not partes:
        return []
    fatos = str(roteiro.get("fatos") or "").strip()
    if not fatos:
        return ["a biblia nao tem a linha FATOS: os numeros desta historia nao "
                "foram fixados antes de escrever, entao nada garante que o "
                "mesmo valor apareca igual em todas as partes "
                "(`main.py conferir <id> --numeros` lista o que ela cita)."]

    declarados = valores_da_ficha(fatos)
    achados = citacoes(roteiro)
    avisos = []
    for tipo, rotulo in (("dinheiro", "valor em dinheiro"), ("ano", "ano")):
        fora = {}
        for valor, onde in achados[tipo]:
            if valor not in declarados:
                fora.setdefault(valor, []).append(onde)
        for valor, onde in sorted(fora.items()):
            avisos.append(
                f"{rotulo} {valor} em {', '.join(onde[:4])} nao esta na ficha "
                "de FATOS da biblia: ou ele contradiz o que foi fixado, ou "
                "faltou fixar.")
    return avisos
