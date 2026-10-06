"""Catraca: catalogo novo na engine nao pode ficar invisivel no painel."""
from __future__ import annotations

import json

from neural_fights.tools import manifesto_sprites


def test_manifesto_commitado_e_igual_ao_gerado():
    gerado = manifesto_sprites.gerar()
    atual = json.loads(manifesto_sprites.PADRAO.read_text(encoding="utf-8"))
    assert atual == gerado


def test_toda_lista_da_engine_tem_um_lugar_no_manifesto():
    manifesto = manifesto_sprites.gerar()
    resumo = manifesto["resumo"]
    slots = manifesto["slots"]
    assert len(slots) == resumo["total_slots"] == 1867
    assert {s["grupo"] for s in slots} == {"lutador", "camada_estado", "arma", "skill", "efeito", "arena", "hud"}
    assert len({s["id"] for s in slots}) == len(slots)
    # Estes totais saem dos catalogos importados no prototipo; uma classe,
    # expressao, skill, arma, status ou arena nova muda o JSON e a catraca cai.
    contagens = resumo["contagens_engine"]
    assert contagens["classes"] == 16
    assert contagens["expressoes"] == 24
    assert contagens["skills"] == 118
    assert contagens["tipos_arma"] == 8
    assert contagens["status"] == 29
    assert contagens["arenas"] == 20
