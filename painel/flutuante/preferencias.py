# -*- coding: utf-8 -*-
"""Onde a janela estava, de que tamanho e se fica por cima. Nada mais.

E o UNICO arquivo que a janela escreve (`flutuante.json` no runtime), e ele
e dela: nao e estado do sistema.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

MODOS = ("mini", "medio", "grande", "icone")

# A tela dele e 1366x768 com a barra do Windows de ~40 px. O MEDIO nao passa
# de 720x520 (pedido explicito); o GRANDE cresce ate caber.
TAMANHOS = {"mini": (340, 64), "medio": (720, 520), "icone": (56, 56)}
GRANDE_MAX = (1180, 700)
BARRA_DO_WINDOWS = 48

PADRAO = {"modo": "medio", "anterior": "medio", "topo": True,
          "x": None, "y": None, "aba": "diario", "terminal": "postar",
          "gaveta": False, "arte": "fofa", "colecao": None}
ARTES = ("fofa", "classico")
# Um enfeite novo na Vila a cada N publicacoes do dia (o "passatempo").
PUBLICACOES_POR_ENFEITE = 3
ENFEITES = 6


def atualizar_colecao(prefs: dict, publicados_hoje: int, dia: str) -> int:
    """O nivel de enfeites de hoje. Guarda o dia e o recorde em `prefs`.

    Nunca desce no mesmo dia (um ledger relido pela metade nao pode tirar
    enfeite da tela); vira o dia, recomeca do zero. Devolve o nivel.
    """
    nivel = min(ENFEITES, max(0, int(publicados_hoje)) //
                PUBLICACOES_POR_ENFEITE)
    atual = prefs.get("colecao") if isinstance(prefs.get("colecao"),
                                               dict) else {}
    if atual.get("dia") == dia:
        nivel = max(nivel, int(atual.get("nivel") or 0))
    recorde = max(nivel, int(atual.get("recorde") or 0))
    prefs["colecao"] = {"dia": dia, "nivel": nivel, "recorde": recorde}
    return nivel


def tamanho(modo: str, tela: tuple) -> tuple:
    if modo == "grande":
        return (min(GRANDE_MAX[0], tela[0] - 24),
                min(GRANDE_MAX[1], tela[1] - BARRA_DO_WINDOWS - 12))
    return TAMANHOS.get(modo, TAMANHOS["medio"])


def encaixar(x, y, largura: int, altura: int, tela: tuple) -> tuple:
    """A posicao dentro da tela. Sem posicao salva: canto superior direito.

    Salvo com outro monitor (ou antes de trocar de tamanho), a janela podia
    nascer fora da tela — e uma janela sem borda fora da tela nao tem como
    ser puxada de volta.
    """
    livre_x = max(0, tela[0] - largura)
    livre_y = max(0, tela[1] - BARRA_DO_WINDOWS - altura)
    if x is None or y is None:
        return livre_x - 16 if livre_x >= 16 else livre_x, min(16, livre_y)
    return (min(max(0, int(x)), livre_x), min(max(0, int(y)), livre_y))


def ler(caminho: Path) -> dict:
    dados = dict(PADRAO)
    try:
        with open(caminho, encoding="utf-8") as fh:
            salvo = json.load(fh)
        if isinstance(salvo, dict):
            dados.update({k: v for k, v in salvo.items() if k in PADRAO})
    except (OSError, ValueError):
        pass
    if dados["modo"] not in MODOS:
        dados["modo"] = "medio"
    if dados["anterior"] not in MODOS or dados["anterior"] == "icone":
        dados["anterior"] = "medio"
    if dados["arte"] not in ARTES:
        dados["arte"] = "fofa"
    return dados


def gravar(caminho: Path, dados: dict) -> bool:
    """Grava de um jeito que nao deixa arquivo pela metade. Nunca levanta."""
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(
            {k: dados.get(k) for k in PADRAO}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        os.replace(temporario, caminho)
        return True
    except OSError:
        return False


__all__ = ["MODOS", "PADRAO", "TAMANHOS", "encaixar", "gravar", "ler",
           "tamanho"]
