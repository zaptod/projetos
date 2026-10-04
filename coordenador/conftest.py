# -*- coding: utf-8 -*-
"""Cada teste do coordenador numa pasta propria, sem Codex de verdade.

- a pasta do coordenador (conversa, propostas, entrada, memoria do vigia) e a
  do teste: nada cai na real, que o coordenador de verdade atenderia;
- o interruptor do Claude mora na pasta do teste (como em `remoto/`);
- `cerebro.rodar_codex` vira uma bomba que REGISTRA a chamada: o `pensar`
  engole excecao e responderia "nao consegui pensar", entao o teste confere
  no fim que ninguem chamou o Codex de verdade.
"""
import pytest

from remoto import avisos, claude_estado


@pytest.fixture(autouse=True)
def _coordenador_isolado(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coordenador"))
    monkeypatch.setattr(avisos, "ARQUIVO", tmp_path / "avisos" / "avisos_estado.json")
    monkeypatch.setattr(avisos, "REGISTRO", tmp_path / "avisos" / "avisos_enviados.jsonl")
    monkeypatch.setattr(claude_estado, "ARQUIVO", tmp_path / "claude_estado" / "claude.json")
    monkeypatch.delenv("NF_CLAUDE_ESTADO", raising=False)
    from coordenador import cerebro
    chamadas = []

    def bomba(*args, **kwargs):
        chamadas.append(args)
        raise AssertionError("o Codex de verdade nunca roda num teste")
    bomba.original = cerebro.rodar_codex     # o teste do comando a chama com subprocess dublado
    monkeypatch.setattr(cerebro, "rodar_codex", bomba)
    yield
    assert not chamadas, "um teste chamou o Codex de verdade"
