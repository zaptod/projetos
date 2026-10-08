# -*- coding: utf-8 -*-
"""O apurador entrega diagnosticos a Mesa, sem criar remendo proprio."""
from coordenador import pedidos
from remoto import apurador


def test_mesmo_erro_do_apurador_abre_um_pedido(tmp_path, monkeypatch):
    monkeypatch.setattr(pedidos, "_arquivo", lambda: tmp_path / "pedidos.json")
    mesa = pedidos.MesaPedidos()
    monkeypatch.setattr(pedidos, "MESA", mesa)
    erros = [{"ts": "2026-10-07T20:00:00", "fabrica": "app", "detalhe": "tela caiu"}]
    primeiro = apurador.abrir_pedido(erros, "A tela falha ao abrir.")
    repetido = apurador.abrir_pedido(erros, "Diagnostico refeito.")
    assert primeiro["id"] == repetido["id"] and repetido["duplicado"]
    item = pedidos._ler()["pedidos"]
    assert len(item) == 1 and item[0]["origem"] == "apurador"
    assert "Diagnostico do apurador" in item[0]["texto"]
