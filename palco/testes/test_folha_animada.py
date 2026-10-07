# -*- coding: utf-8 -*-
"""A folha animada (a peca que a Oficina exporta) com canais em LISTA.

O palco passa ao `configurar` a trilha inteira do objeto, com `ang`, `r`...
como listas. `folha_animada.gd` fazia `float(dados.get("ang"))` e cada
projetil da Oficina (o fogo do Adrian) dava SCRIPT ERROR — o mesmo defeito
que a ponte do Atelie consertou no peca_png.gd com `_numero()` (07/10/2026).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FOLHA = RAIZ / "biblioteca" / "efeitos" / "folha_animada.gd"


def _godot():
    try:
        from builds.palco import config
        return config.godot_disponivel()
    except Exception:                                        # noqa: BLE001
        caminho = Path("E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe")
        return caminho if caminho.is_file() else None


GODOT = _godot()


def test_folha_animada_nao_faz_float_de_lista():
    texto = FOLHA.read_text(encoding="utf-8")
    assert "static func _numero(" in texto
    for cru in ('float(dados.get(', 'float(amostra.get(', 'float(ctx.get('):
        assert cru not in texto, cru


@pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")
def test_folha_animada_com_lista_no_godot(tmp_path):
    env = dict(os.environ, APPDATA=str(tmp_path / "appdata"))
    if not (RAIZ / ".godot").is_dir():
        subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--import"], env=env,
                       capture_output=True, timeout=600)
    p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--script",
                        "res://testes/folha_animada_lista.gd"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    saida = (p.stdout or "") + (p.stderr or "")
    assert p.returncode == 0, saida[-3000:]
    assert "0 falha(s)" in saida, saida[-3000:]
    assert "SCRIPT ERROR" not in saida, saida[-3000:]
