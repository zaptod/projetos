# -*- coding: utf-8 -*-
"""O interruptor do Claude de cada teste mora na pasta do teste.

`remoto/claude_estado.py` le `claude.json` a cada chamada, e quase todo
modulo daqui obedece a ele (orquestrador, apurador, servidor). Sem isto, um
teste que proibe o Claude deixaria o arquivo na pasta de runtime do pytest,
e o proximo teste (de outro arquivo) acharia o Claude proibido.
"""
import pytest

from remoto import claude_estado


@pytest.fixture(autouse=True)
def _claude_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_estado, "ARQUIVO", tmp_path / "claude_estado" / "claude.json")
    monkeypatch.delenv("NF_CLAUDE_ESTADO", raising=False)
    yield
