# -*- coding: utf-8 -*-
"""Onde cada cena comeca e termina no mp4 que foi ao disco.

O render grava `partes/pNN/edit_plan.json` com um evento por cena: numero,
inicio e duracao medidos depois da voz. E a unica fonte que diz "a cena 6 vai
de 41 s a 48 s" — e e isso que deixa quem assiste ao video apontar a CENA
certa, e nao um "quadro" numerado do jeito dele.

POR QUE ISTO EXISTE. Ate 13/09/2026 o parecer da IA pedia "o numero do
quadro" sem dizer o que era um quadro. Na folha de contato era a sexta de
doze miniaturas espacadas no tempo, numa parte de 13 ou 14 cenas; no video,
era a contagem do proprio Gemini. O reparador lia esse numero como cena e
podia refazer a imagem boa e deixar a ruim.

Sem o plano (video antigo, render interrompido), a conta sai do TEMPO que o
roteiro pediu para cada cena: aproximada, mas na ordem certa.
"""
from __future__ import annotations

import json
from pathlib import Path


def caminho_do_plano(historia_id: str, parte: int) -> Path:
    from ..roteiro import roteiro as R
    return (R.OUTPUTS / historia_id / "partes" / f"p{int(parte):02d}"
            / "edit_plan.json")


def cenas_do_plano(caminho: Path) -> list:
    """`[{n, inicio, fim, narracao}]` do plano gravado, ou `[]`.

    Uma cena longa pode virar mais de um plano de camera com o mesmo numero;
    aqui ela volta a ser uma so, do primeiro inicio ao ultimo fim.
    """
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return []
    por_numero = {}
    for evento in (dados or {}).get("events") or []:
        if not isinstance(evento, dict) or evento.get("type") != "cena":
            continue
        try:
            n = int(evento.get("n"))
            inicio = float(evento.get("start") or 0.0)
            fim = inicio + float(evento.get("duration") or 0.0)
        except (TypeError, ValueError):
            continue
        atual = por_numero.get(n)
        if atual is None:
            por_numero[n] = {"n": n, "inicio": inicio, "fim": fim,
                             "narracao": str(evento.get("narracao") or "")}
        else:
            atual["inicio"] = min(atual["inicio"], inicio)
            atual["fim"] = max(atual["fim"], fim)
    cenas = sorted(por_numero.values(), key=lambda c: c["inicio"])
    for cena in cenas:
        cena["inicio"] = round(cena["inicio"], 2)
        cena["fim"] = round(cena["fim"], 2)
    return cenas


def cenas_do_roteiro(roteiro: dict, parte: int) -> list:
    """A mesma lista, estimada pelo TEMPO pedido no roteiro."""
    from .timeline import cenas_da_parte

    instante, saida = 0.0, []
    for cena in cenas_da_parte(roteiro, parte):
        try:
            duracao = float(cena.get("tempo") or 4.0)
        except (TypeError, ValueError):
            duracao = 4.0
        try:
            n = int(cena.get("n"))
        except (TypeError, ValueError):
            continue
        saida.append({"n": n, "inicio": round(instante, 2),
                      "fim": round(instante + duracao, 2),
                      "narracao": str(cena.get("narracao") or "")})
        instante += duracao
    return saida


def cenas_com_tempo(historia_id: str, parte: int,
                    roteiro: dict | None = None) -> list:
    """As cenas do video com o trecho de cada uma. Prefere o medido."""
    cenas = cenas_do_plano(caminho_do_plano(historia_id, parte))
    if cenas:
        return cenas
    if roteiro is None:
        from ..roteiro import roteiro as R
        roteiro = R.carregar(historia_id)
    return cenas_do_roteiro(roteiro, parte)


__all__ = ["caminho_do_plano", "cenas_com_tempo", "cenas_do_plano",
           "cenas_do_roteiro"]
