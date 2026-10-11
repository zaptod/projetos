# -*- coding: utf-8 -*-
"""Auditoria 11/10/2026 (#3 do RESUMO): `pedidos.json` ilegivel NUNCA vira `{}`.

Uma leitura que falhava uma vez (arquivo trancado no Windows, JSON partido)
devolvia a Mesa vazia, e a proxima gravacao sobrescrevia todos os pedidos e a
conversa. Agora: ausente = vazio; trancado = tenta de novo; ilegivel de vez =
copia guardada e excecao, sem ninguem gravar por cima."""
from __future__ import annotations

import json
import pathlib
import time

import pytest

from coordenador import pedidos
from coordenador.test_pedidos import ClaudeFalso, DespachanteFalso, Relogio


@pytest.fixture
def mesa(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    monkeypatch.setattr(pedidos, "LER_ESPERA_S", 0, raising=False)
    return pedidos.MesaPedidos(despachante=DespachanteFalso(tmp_path / "delegados"),
                               claude=ClaudeFalso(), relogio=Relogio(),
                               avisar=lambda *_: None, uso=lambda: {"passou_teto": False})


def _com_um_pedido(mesa):
    item = mesa.registrar("conserte o botao do app", "app", triar=False)
    return item["id"], pedidos._arquivo().read_bytes()


def test_arquivo_ausente_continua_mesa_vazia(mesa):
    assert not pedidos._arquivo().exists()
    dados = pedidos._ler()
    assert dados["pedidos"] == [] and dados["conversa"] == []


def test_json_partido_nao_e_sobrescrito_e_fica_copia(mesa):
    _com_um_pedido(mesa)
    partido = b'{"pedidos":[{"id":"pedido-velho","texto":"preservar historico"'
    pedidos._arquivo().write_bytes(partido)

    with pytest.raises(OSError):
        mesa.registrar("pedido novo depois da queda", "app", triar=False)

    assert pedidos._arquivo().read_bytes() == partido, "o original foi sobrescrito"
    copias = list(pedidos._arquivo().parent.glob("pedidos.json.ilegivel-*"))
    assert len(copias) == 1 and copias[0].read_bytes() == partido

    # o pulso seguinte tenta de novo e nao empilha uma copia por volta
    with pytest.raises(OSError):
        pedidos._ler()
    assert len(list(pedidos._arquivo().parent.glob("pedidos.json.ilegivel-*"))) == 1


def test_leitura_trancada_por_um_instante_tenta_de_novo(mesa, monkeypatch):
    ident, _ = _com_um_pedido(mesa)
    alvo = pedidos._arquivo()
    original = pathlib.Path.read_text
    falhas = {"n": 2}

    def trancado(self, *args, **kwargs):
        if self == alvo and falhas["n"]:
            falhas["n"] -= 1
            raise PermissionError(13, "O arquivo ja esta sendo usado por outro processo")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(pathlib.Path, "read_text", trancado)

    mesa.registrar("segundo pedido", "app", triar=False)

    monkeypatch.setattr(pathlib.Path, "read_text", original)
    ids = [p["id"] for p in json.loads(alvo.read_text(encoding="utf-8"))["pedidos"]]
    assert ident in ids, "o pedido antigo sumiu: a leitura trancada virou Mesa vazia"
    assert len(ids) == 2


def test_supervisor_registra_o_erro_e_o_laco_segue(mesa):
    from coordenador.test_coordenador import supervisor
    _com_um_pedido(mesa)
    pedidos._arquivo().write_text("{partido", encoding="utf-8")
    eventos = []
    s, _ = supervisor(pedidos=pedidos._ler, log=eventos.append)

    for _ in range(2):          # duas voltas: a segunda tambem roda
        s.processar_pedidos()
        s.fundos["pedidos"].join(timeout=10)
        time.sleep(0)
    erros = [e for e in s.eventos if e["tipo"] == "pedidos_erro"]
    assert len(erros) == 2 and "ilegivel" in erros[0]["texto"].lower()
    assert pedidos._arquivo().read_text(encoding="utf-8") == "{partido"
