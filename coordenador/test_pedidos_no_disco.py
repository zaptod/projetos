# -*- coding: utf-8 -*-
"""16/10/2026 21:38: o PC desligou logo depois de gravar e o pedidos.json voltou
com 810.926 bytes, todos zero. A gravacao trocava o nome do arquivo sem forcar
o conteudo no disco. Agora o temporario leva `fsync` ANTES do `os.replace`."""
from __future__ import annotations

import json
import os

from coordenador import pedidos


def _registrar_ordem(monkeypatch):
    ordem = []
    fsync, replace = os.fsync, os.replace

    def fsync_espiao(fd):
        ordem.append("fsync")
        return fsync(fd)

    def replace_espiao(origem, destino):
        ordem.append("replace")
        return replace(origem, destino)

    monkeypatch.setattr(pedidos.os, "fsync", fsync_espiao)
    monkeypatch.setattr(pedidos.os, "replace", replace_espiao)
    return ordem


def test_mesa_vai_ao_disco_antes_de_trocar_o_nome(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    ordem = _registrar_ordem(monkeypatch)
    pedidos._gravar({"pedidos": [{"id": "pedido-1"}], "conversa": []})
    assert ordem == ["fsync", "replace"]
    lido = json.loads(pedidos._arquivo().read_text(encoding="utf-8"))
    assert lido["pedidos"] == [{"id": "pedido-1"}]


def test_json_auxiliar_tambem_vai_ao_disco_antes(tmp_path, monkeypatch):
    ordem = _registrar_ordem(monkeypatch)
    alvo = tmp_path / "resultado.json"
    pedidos._gravar_json(alvo, {"ok": True})
    assert ordem == ["fsync", "replace"]
    assert json.loads(alvo.read_text(encoding="utf-8")) == {"ok": True}


def test_caso_zero_mesa_vazia_tambem_e_forcada(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    ordem = _registrar_ordem(monkeypatch)
    pedidos._gravar({"pedidos": [], "conversa": []})
    assert ordem == ["fsync", "replace"]
