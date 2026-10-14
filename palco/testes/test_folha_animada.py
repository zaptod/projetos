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


def test_folha_recomeca_e_guarda_transformacoes_no_draw():
    texto = (RAIZ / "nucleo" / "tocador_folha.gd").read_text(encoding="utf-8")
    assert "func _trocar" in texto
    assert "indice = 0" in texto
    assert "fps <= 0.0" in texto
    assert "quadro fora da folha" in texto
    assert "rotacao_json" in texto and "espelho_json" in texto


def _rodar_no_godot(tmp_path, script: str) -> None:
    env = dict(os.environ, APPDATA=str(tmp_path / "appdata"))
    if not (RAIZ / ".godot").is_dir():
        subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--import"], env=env,
                       capture_output=True, timeout=600)
    # --quit-after: erro de script no _init deixa o SceneTree sem quit() e o
    # Godot ficava aberto ate o timeout; assim sai, e o "0 falha(s)" falta
    p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--quit-after", "120", "--script", script],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    saida = (p.stdout or "") + (p.stderr or "")
    assert p.returncode == 0, saida[-3000:]
    assert "0 falha(s)" in saida, saida[-3000:]
    assert "SCRIPT ERROR" not in saida, saida[-3000:]


@pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")
def test_folha_animada_com_lista_no_godot(tmp_path):
    _rodar_no_godot(tmp_path, "res://testes/folha_animada_lista.gd")


@pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")
def test_evento_da_arma_toca_ate_o_fim_no_godot(tmp_path):
    """GOD-3: o `ocioso`/`golpe_fase` de todo quadro nao corta o evento."""
    _rodar_no_godot(tmp_path, "res://testes/tocador_folha.gd")


@pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")
def test_rosto_pendurado_anda_cresce_e_segue_a_expressao_no_godot(tmp_path):
    """GOD-1: um gatilho por quadro, estado = expressao, filhos com avancar/ajustar_corpo."""
    _rodar_no_godot(tmp_path, "res://testes/rosto_folha.gd")


def test_palco_manda_um_gatilho_por_quadro_ao_lutador():
    """GOD-1: `expr` e `golpe_fase` no mesmo quadro faziam a boca trocar duas vezes."""
    texto = (RAIZ / "nucleo" / "palco.gd").read_text(encoding="utf-8")
    assert '"golpe_fase" if int(s.get("golpe_fase", 0)) > 0 else "expr"' in texto
    assert 'no.gatilho("expr")' not in texto
    assert '_repassar(no, "estado", [_nome_expr(s)])' in texto
