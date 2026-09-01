"""Bloqueio de nome ofensivo vindo de comentario.

Este e o unico ponto do sistema em que texto de um estranho vira pixel na tela:
o nome pedido nos comentarios e desenhado na placa do personagem e sai num video
publico. Sem esta camada, "puta que pariu" virava o nome do personagem.

Duas passadas, porque as duas fraudes sao diferentes:
  - palavra inteira: termo curto que e xingamento sozinho mas vive dentro de
    palavra inocente ("cu" esta em "escuro", "obscuro", "curso"). So casa se for
    a palavra toda.
  - trecho: termo longo que nao aparece por acaso ("caralho" nunca e parte de
    outra palavra). Casa em qualquer posicao, inclusive com os espacos removidos,
    porque "c a r a l h o" e a evasao mais obvia que existe.

A lista mora em config/moderacao.json para o dono ajustar sem mexer em codigo.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_CONFIG = Path(__file__).resolve().parents[2] / "config" / "moderacao.json"

MOTIVO = "conteudo ofensivo"


@lru_cache(maxsize=1)
def _regras() -> tuple:
    """(palavras_inteiras, trechos, tabela_leet). Em cache: e lido por nome."""
    try:
        with open(_CONFIG, encoding="utf-8") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        # Sem o arquivo o programa continua funcionando; o que ele NAO pode e
        # fingir que filtrou. Quem chama trata a lista vazia como "nao sei dizer".
        return frozenset(), tuple(), {}
    inteiras = frozenset(str(p).lower() for p in dados.get("palavra_inteira", []))
    trechos = tuple(sorted((str(p).lower() for p in dados.get("trecho", [])),
                           key=len, reverse=True))
    leet = {str(k): str(v) for k, v in (dados.get("leet") or {}).items()}
    return inteiras, trechos, leet


def normalizar(texto: str) -> str:
    """Forma canonica para comparar: sem acento, minusculo, sem leet, so letras.

    Preserva o espaco porque a passada de palavra inteira depende dele.
    """
    if not isinstance(texto, str):
        return ""
    _, _, leet = _regras()
    plano = unicodedata.normalize("NFD", texto)
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    plano = plano.lower()
    plano = "".join(leet.get(c, c) for c in plano)
    plano = re.sub(r"[^a-z\s]+", " ", plano)
    # "puuuta" e "puta" com ruido: corre 3+ repeticoes para 1. Duas ficam, senao
    # nome legitimo com letra dobrada ("Anna", "Gassner") seria remodelado a toa.
    plano = re.sub(r"(.)\1{2,}", r"\1", plano)
    return re.sub(r"\s+", " ", plano).strip()


def _juntar_letras_soltas(plano: str) -> str:
    """Cola sequencias de letras isoladas: "p u t a" -> "puta".

    So cola corrida de 3 ou mais tokens de uma letra. Colar tudo seria pior que
    nao filtrar: "Escurinho" sem espaco contem "cu", e um nome legitimo com
    inicial no meio ("Ana B Silva") nao pode virar palavra nova.
    """
    tokens = plano.split()
    saida, corrida = [], []
    for token in tokens + [""]:
        if len(token) == 1:
            corrida.append(token)
            continue
        if len(corrida) >= 3:
            saida.append("".join(corrida))
        else:
            saida.extend(corrida)
        corrida = []
        if token:
            saida.append(token)
    return " ".join(saida)


def ofensivo(texto: str) -> str | None:
    """O termo que bloqueou, ou None se o texto passa.

    Devolve o termo (e nao so True) para o teste poder afirmar QUAL regra pegou,
    e para o operador entender uma recusa sem adivinhar.
    """
    inteiras, trechos, _ = _regras()
    if not inteiras and not trechos:
        return None
    plano = normalizar(texto)
    if not plano:
        return None
    for forma in (plano, _juntar_letras_soltas(plano)):
        for palavra in forma.split():
            if palavra in inteiras:
                return palavra
    # Sem espaco nenhum: pega "c a r a l h o" e "vai tomar no cu" grudados.
    grudado = plano.replace(" ", "")
    for trecho in trechos:
        if trecho in grudado:
            return trecho
    return None
