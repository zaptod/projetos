from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def test_buscas_novas_da_biblioteca_do_palco():
    biblioteca = (RAIZ / "nucleo" / "biblioteca.gd").read_text(encoding="utf-8")
    timeline = (RAIZ / "nucleo" / "timeline.gd").read_text(encoding="utf-8")
    palco = (RAIZ / "nucleo" / "palco.gd").read_text(encoding="utf-8")
    lutador = (RAIZ / "biblioteca" / "lutadores" / "lutador_padrao.gd").read_text(encoding="utf-8")

    assert "func candidatos_evento" in biblioteca
    assert '"eventos/%s_%s" % [nome, UtilPalco.slug(variante)]' in biblioteca
    assert '"eventos/%s_%s" % [nome, UtilPalco.slug(elemento)]' in biblioteca
    assert "func candidatos_peca_lutador" in biblioteca
    assert '"%s/_padrao" % pasta' in biblioteca
    assert '"movimento": true' in timeline
    assert '"projetil_fim": true' in timeline
    assert 'variante = str(ev.get("gatilho", ""))' in palco
    assert 'variante = str(ev.get("motivo", ""))' in palco
    assert '"buff": "buffs", "canal": "canais", "transformacao": "transformacoes"' in lutador
