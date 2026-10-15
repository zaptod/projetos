# -*- coding: utf-8 -*-
"""O interruptor do Claude de cada teste mora na pasta do teste.

`remoto/claude_estado.py` le `claude.json` a cada chamada, e quase todo
modulo daqui obedece a ele (orquestrador, apurador, servidor). Sem isto, um
teste que proibe o Claude deixaria o arquivo na pasta de runtime do pytest,
e o proximo teste (de outro arquivo) acharia o Claude proibido.

E nenhum teste pega trava de PRODUCAO (15/10/2026): em 14/10 16:01, com a
prova de tela do app rodando, a trava real do Grimorio
(`%LOCALAPPDATA%\\neural-fights\\decisoes.lock`) ficou presa por minutos.
Toda trava passa por `api_http.trava_arquivo`; aqui ela recusa (OSError,
como trava ocupada) qualquer alvo dentro do runtime de verdade, e o teste
que tentou falha dizendo qual.
"""
import os
from pathlib import Path

import pytest

from remoto import avisos, claude_estado

# O runtime de verdade, lido ANTES de qualquer teste trocar o LOCALAPPDATA
# (o conftest da raiz so troca o NEURAL_FIGHTS_RUNTIME_DIR).
_PRODUCAO = Path(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")) / "neural-fights"


def _em_producao(alvo) -> bool:
    try:
        Path(alvo).resolve().relative_to(_PRODUCAO.resolve())
    except (ValueError, OSError):
        return False
    return True


@pytest.fixture(autouse=True)
def _claude_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_estado, "ARQUIVO", tmp_path / "claude_estado" / "claude.json")
    monkeypatch.delenv("NF_CLAUDE_ESTADO", raising=False)
    # o porteiro dos avisos tambem: um aviso de um teste nao cala o do outro
    monkeypatch.setattr(avisos, "ARQUIVO", tmp_path / "avisos" / "avisos_estado.json")
    monkeypatch.setattr(avisos, "REGISTRO", tmp_path / "avisos" / "avisos_enviados.jsonl")
    # e a fila de pendentes: o bot de verdade mandaria ao Adrian o aviso de teste
    monkeypatch.setattr(avisos, "PENDENTES", tmp_path / "avisos" / "avisos_pendentes.jsonl")
    # e a marca-d'agua dos alertas do bot (APP-11): um Bot() de teste nao pode
    # avancar a do bot de verdade e calar um erro real
    from remoto import bot
    monkeypatch.setattr(bot, "BOT_VISTO", tmp_path / "bot" / "bot_visto.json")
    yield


@pytest.fixture(autouse=True)
def _sem_trava_de_producao(monkeypatch):
    """Todo `trava_arquivo` (decisoes, orquestrador, app, Claude, delegar,
    coordenador) importa a funcao na hora da chamada, entao a troca abaixo
    vale para todos, inclusive nas threads do servidor de teste."""
    from remoto import api_http

    original = api_http.trava_arquivo
    tentadas = []

    def vigiada(alvo, *args, **kwargs):
        if _em_producao(alvo):
            tentadas.append(str(alvo))
            raise OSError(f"teste tentou a trava de PRODUCAO: {alvo}")
        return original(alvo, *args, **kwargs)

    vigiada.tentadas = tentadas           # a prova da propria guarda limpa a lista
    monkeypatch.setattr(api_http, "trava_arquivo", vigiada)
    yield
    assert not tentadas, f"o teste tentou travar arquivo do runtime real: {tentadas}"
