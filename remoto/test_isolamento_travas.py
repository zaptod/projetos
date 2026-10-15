# -*- coding: utf-8 -*-
"""Nenhum teste do remoto pega trava do runtime REAL (15/10/2026).

Em 14/10 16:01, com a prova de tela do app rodando, a trava real do Grimorio
(`%LOCALAPPDATA%\\neural-fights\\decisoes.lock`) ficou presa por minutos. A
guarda mora no `remoto/conftest.py`; aqui a prova de que ela recusa sem
tocar no arquivo, e de que o Grimorio, o orquestrador e a prova de tela
travam fora do runtime real.
"""
from __future__ import annotations

import pytest

from remoto import api_http, conftest, decisoes, orquestrador


def _alvo_da_trava(fabrica, monkeypatch) -> str:
    """Qual arquivo a trava pediria, sem travar nada."""
    pedido = []

    def anotar(alvo, *args, **kwargs):
        pedido.append(str(alvo))
        raise RuntimeError("so anotar")

    monkeypatch.setattr(api_http, "trava_arquivo", anotar)
    with pytest.raises(RuntimeError):
        fabrica()
    return pedido[0]


def test_a_guarda_recusa_a_trava_de_producao_sem_abrir_o_arquivo():
    alvo = conftest._PRODUCAO / "decisoes.lock"
    with pytest.raises(OSError, match="PRODUCAO"):
        with api_http.trava_arquivo(alvo):
            pass
    tentadas = api_http.trava_arquivo.tentadas
    assert tentadas == [str(alvo)]
    tentadas.clear()                          # a falha foi provocada aqui de proposito


def test_grimorio_e_orquestrador_travam_fora_do_runtime_real(monkeypatch):
    for fabrica in (decisoes._trava, orquestrador._trava):
        alvo = _alvo_da_trava(fabrica, monkeypatch)
        assert not conftest._em_producao(alvo), alvo


def test_a_prova_de_tela_trava_o_grimorio_na_pasta_do_teste(tmp_path, monkeypatch):
    """O `tela_isolada` troca LOCALAPPDATA e NEURAL_FIGHTS_RUNTIME_DIR; o
    Grimorio que o servidor da prova le trava dentro da pasta do teste."""
    local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(local / "neural-fights"))
    monkeypatch.delenv("NF_DECISOES_REPO", raising=False)
    monkeypatch.setattr(decisoes, "TRAVA", None)
    alvo = _alvo_da_trava(decisoes._trava, monkeypatch)
    assert alvo.startswith(str(local)), alvo
