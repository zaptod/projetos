from neural_fights.tools import catalogo_vila


def test_catalogo_da_vila_cobre_inventario_e_direcoes():
    pecas = catalogo_vila.catalogo()
    assert sum(len(p["itens_vila"]) for p in pecas) == 132
    assert all(not p["id"].startswith("vila.base.") for p in pecas)
    grok = next(p for p in pecas if p["id"] == "vila.habitantes.grok")
    andar = next(e for e in grok["estados"] if e["id"] == "andar")
    assert [a["id"] for a in andar["animacoes"]] == ["frente", "esquerda", "direita", "costas"]
    assert all(a["gatilho"] == "pose" for a in andar["animacoes"])
    assert grok["categoria_vila"] == "Habitantes" and grok["rotulo"] == "Grok"
