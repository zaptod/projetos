# -*- coding: utf-8 -*-
"""16F: a arma com o `peca.gd` estica ate o comprimento da timeline.

A Oficina exporta a arma (painel/sprites/exportar.py) de um PNG gerado aqui
por codigo; o `palco/testes/arma_estica.gd` (headless, sem render) poe essa
cena no `_arma` do palco de verdade e confere que a empunhadura fica na mao e
a ponta da arte vai a ponta da hitbox, em dois comprimentos. Sem Godot, so a
parte estatica roda (o resto e pulado com motivo).

A arte da cena exportada e trocada por um PNG que ja existe no projeto (a
geometria esta no offset e na rotacao do Sprite2D, nao nos pixels): assim o
Godot nao precisa importar arquivo novo.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ARTE_DO_PROJETO = "res://biblioteca/lutadores/rosto/eye_open.png"


def _godot():
    try:
        from builds.palco import config
        return config.godot_disponivel()
    except Exception:                                        # noqa: BLE001
        return None


GODOT = _godot()
precisa_godot = pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")


def test_o_palco_estica_toda_peca_que_nao_se_desenha_no_comprimento():
    palco = (RAIZ / "nucleo" / "palco.gd").read_text(encoding="utf-8")
    corpo = palco.split("func _arma(", 1)[1].split("\nfunc ", 1)[0]
    # a escala vale ANTES do atualizar e para qualquer peca (antes era so no
    # `else` de quem nao tinha atualizar, e o peca.gd tem um)
    assert "UtilPalco.esticar_arma(no, L)" in corpo
    assert corpo.index("UtilPalco.esticar_arma(no, L)") < corpo.index("no.atualizar(s, ctx)")
    assert "else:\n\t\tvar ref = no.get(\"comprimento_ref\")" not in corpo
    util = (RAIZ / "nucleo" / "util.gd").read_text(encoding="utf-8")
    assert "static func esticar_arma(no: Node2D, comprimento_px: float)" in util
    padrao = (RAIZ / "biblioteca" / "armas" / "arma_padrao.gd").read_text(encoding="utf-8")
    assert "var desenha_comprimento := true" in padrao


def _exportar_espada(pasta: Path) -> tuple[Path, Path]:
    from painel.sprites import exportar
    from painel.sprites.receita import processar
    from painel.test_oficina_armas import espada_em_magenta

    res = processar(espada_em_magenta())
    bib = pasta / "biblioteca"
    bib.mkdir()
    ident = exportar.Identidade(tipo="arma", nome="Espada Longa", prova="teste")
    feito = exportar.exportar(res, ident, biblioteca=bib)
    cena, meta = Path(feito["cena"]), Path(feito["metadados"])
    texto = cena.read_text(encoding="utf-8")
    texto, n = re.subn(r'path="res://biblioteca/armas/estilos/espada_longa\.png"',
                       f'path="{ARTE_DO_PROJETO}"', texto)
    assert n == 1
    fora = pasta / "espada_longa.tscn"
    fora.write_text(texto, encoding="utf-8")
    return fora, meta


def _rodar(argumentos: list, appdata: Path) -> tuple[int, str]:
    env = dict(os.environ, APPDATA=str(appdata))
    if not (RAIZ / ".godot").is_dir():
        subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--import"], env=env,
                       capture_output=True, timeout=600)
    p = subprocess.run([str(GODOT), "--headless", "--path", str(RAIZ), "--script",
                        "res://testes/arma_estica.gd", "--", *argumentos], env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


@precisa_godot
def test_a_arma_exportada_pela_oficina_estica_no_palco(tmp_path):
    cena, meta = _exportar_espada(tmp_path)
    appdata = tmp_path / "appdata"
    appdata.mkdir()
    rc, saida = _rodar([f"--cena={cena.as_posix()}", f"--meta={meta.as_posix()}"], appdata)
    assert rc == 0, saida[-2500:]
    assert "0 falha(s)" in saida
    # a cena da Oficina foi conferida de verdade (nao so a de codigo)
    assert "cena da Oficina: conferida" in saida
