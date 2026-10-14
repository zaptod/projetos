from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def test_buscas_novas_da_biblioteca_do_palco():
    biblioteca = (RAIZ / "nucleo" / "biblioteca.gd").read_text(encoding="utf-8")
    timeline = (RAIZ / "nucleo" / "timeline.gd").read_text(encoding="utf-8")
    palco = (RAIZ / "nucleo" / "palco.gd").read_text(encoding="utf-8")

    assert "func candidatos_evento" in biblioteca
    assert '"eventos/%s_%s" % [nome, UtilPalco.slug(variante)]' in biblioteca
    assert '"eventos/%s_%s" % [nome, UtilPalco.slug(elemento)]' in biblioteca
    assert "func candidatos_peca_lutador" in biblioteca
    assert '"%s/_padrao" % pasta' in biblioteca
    assert '"movimento": true' in timeline
    assert '"projetil_fim": true' in timeline
    # a variante mora na biblioteca: uma conta para o palco e o validar.gd
    assert "Biblioteca.variante_do_evento(ev, cab)" in palco
    assert 'return str(ev.get("gatilho", ""))' in biblioteca
    assert 'return str(ev.get("motivo", ""))' in biblioteca
    assert '"movimento." + UtilPalco.slug(variante)' in biblioteca
    assert "func rostos()" in biblioteca
    assert '"lutador.rosto.boca"' in biblioteca
    assert "func _donos_do_gatilho" in palco
    assert 'tipo == "acerto"' in palco and 'tipo == "ko"' in palco
    assert "peca_png.gd" not in biblioteca


def test_sobras_da_cadeia_png_sairam():
    """GOD-4 (#12): codigo morto e documentacao fora de sincronia."""
    biblioteca = (RAIZ / "nucleo" / "biblioteca.gd").read_text(encoding="utf-8")
    validar = (RAIZ / "ferramentas" / "validar.gd").read_text(encoding="utf-8")
    godot_py = (RAIZ.parent / "random_builds" / "builds" / "palco" / "godot.py").read_text(encoding="utf-8")
    for morto in ("func _id_slot", "func candidatos_objeto_png", "func candidatos_evento_com_png",
                  "func candidato_camada_png", "func opcoes_do_png", "ajustes_png"):
        assert morto not in biblioteca, morto
    assert "vitrine.tscn" not in godot_py
    # o validador resolve o evento com a MESMA cadeia do palco
    assert "Biblioteca.variante_do_evento(ev, cab)" in validar
    assert "nome_skill, tipo_skill)" in validar
