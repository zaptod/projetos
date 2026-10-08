"""Cobertura entre os gatilhos do catalogo do Atelie e a timeline do palco."""
from __future__ import annotations

import json
from pathlib import Path

from neural_fights.tools import catalogo_animacoes


RAIZ = Path(__file__).resolve().parents[1]
GRUPOS = {"skill", "efeito", "elemento", "estado_personagem", "buff"}


def _gatilhos_por_grupo() -> dict[str, set[str]]:
    catalogo = json.loads((RAIZ / "palco/biblioteca/catalogo_animacoes.json").read_text(encoding="utf-8"))
    return {
        grupo: {
            animacao["gatilho"]
            for peca in catalogo["pecas"] if peca["grupo"] == grupo
            for estado in peca["estados"] for animacao in estado["animacoes"]
        }
        for grupo in GRUPOS
    }


def test_gatilhos_dos_cinco_grupos_tem_sinal_na_timeline():
    sinais = set(catalogo_animacoes.gatilhos_do_jogo())
    for grupo, gatilhos in _gatilhos_por_grupo().items():
        assert gatilhos <= sinais, f"{grupo}: {sorted(gatilhos - sinais)} sem evento/canal da timeline"


def test_palco_consumo_catalogo_para_evento_objeto_e_trilha_persistente():
    biblioteca = (RAIZ / "palco/nucleo/biblioteca.gd").read_text(encoding="utf-8")
    palco = (RAIZ / "palco/nucleo/palco.gd").read_text(encoding="utf-8")
    assert '"skill." + UtilPalco.slug(skill)' in biblioteca
    assert '"efeito." + UtilPalco.slug(tipo)' in biblioteca
    assert '"elemento." + UtilPalco.slug(elemento)' in biblioteca
    assert '"estado." if tipo == "status"' in biblioteca
    assert '"buff." if tipo == "buff"' in biblioteca
    assert '"estado_lutador." + UtilPalco.slug(nome)' in biblioteca
    assert "func _atelie_efeitos" in palco
    assert 'tl.vivas("efeitos", i)' in palco
