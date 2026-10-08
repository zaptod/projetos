"""Regressoes da porta unica de trabalho (b3)."""
from __future__ import annotations

import json

from coordenador import __main__ as cli
from coordenador import pedidos
from remoto import delegar, orquestrador


def test_pedir_cria_um_pedido_e_deduplica(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coordenador"))
    assert cli.main(["pedir", "arrume a tela", "--permitido", "remoto/app/**"]) == 0
    primeiro = capsys.readouterr().out.strip()
    assert cli.main(["pedir", "arrume a tela", "--permitido", "remoto/app/**"]) == 0
    assert capsys.readouterr().out.strip() == primeiro
    pedido = pedidos.MESA.para_o_app()["pedidos"][0]
    assert pedido["id"] == primeiro and pedido["origem"] == "chat"


def test_delegar_criar_sem_pedido_recusa(capsys):
    assert delegar.main(["criar", "--id", "porta-teste", "--tarefa", "nao-existe.md",
                         "--permitido", "coordenador/**"]) == 3
    assert "registre o pedido" in capsys.readouterr().err


def test_fila_adicionar_cria_pedido_sem_delegado_direto(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coordenador"))
    monkeypatch.setattr(orquestrador, "PASTA", tmp_path / "orquestrador")
    item = orquestrador.fila_adicionar("builds", "conserte a fila")
    pedido = pedidos.MESA.para_o_app()["pedidos"][0]
    assert pedido["id"] == item["id"] and pedido["origem"] == "fila"
    assert pedido["contratos"] == 0


def test_fila_e_visao_do_pedido_e_migracao_e_idempotente(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coordenador"))
    monkeypatch.setattr(orquestrador, "PASTA", tmp_path / "orquestrador")
    (tmp_path / "orquestrador").mkdir()
    (tmp_path / "orquestrador" / "estado.json").write_text(json.dumps({
        "agora": [], "fila": [{"id": "antigo", "parte": "builds", "item": "migre",
                              "prioridade": 1}], "concluidos_hoje": []}), encoding="utf-8")
    primeira = orquestrador.ler_estado()["fila"]
    segunda = orquestrador.ler_estado()["fila"]
    assert len(primeira) == len(segunda) == 1
    pedido = pedidos.MESA.para_o_app()["pedidos"][0]
    assert pedido["origem"] == "fila" and pedido["contratos"] == 0
