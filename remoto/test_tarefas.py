# -*- coding: utf-8 -*-
"""As tarefas pesadas do app (`remoto.tarefas`): a guarda "ja tem X rodando".

APP-4 da auditoria profunda de 11/10 (consertado em 14/10):
  - `rodando()` so olhava as 40 pastas mais novas: uma tarefa viva atras de
    40 pastas novas sumia da guarda, e o mesmo comando subia em paralelo;
  - se a filha nao subia, a ficha ficava sem pid e "rodando" para sempre
    (barrava o comando, aparecia no resumo, nunca era limpa).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest

from remoto import acoes, publicacao_filha, tarefas


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(tarefas, "PASTA", tmp_path / "tarefas")
    return tmp_path / "tarefas"


def _ficha(pasta, chave, acao, *, pid=None, criado=None, fim=False, inicio=None,
           filho=None):
    alvo = pasta / chave
    alvo.mkdir(parents=True)
    ficha = {"chave": chave, "acao": acao, "rotulo": acao, "comando": [], "cwd": ".",
             "inicio": (inicio or datetime.now()).isoformat(timespec="seconds")}
    if pid is not None:
        ficha["pid"], ficha["criado"] = pid, criado
    (alvo / "tarefa.json").write_text(json.dumps(ficha), encoding="utf-8")
    if filho is not None:
        (alvo / "filho.json").write_text(json.dumps(filho), encoding="utf-8")
    if fim:
        (alvo / "fim.json").write_text('{"codigo": 0}', encoding="utf-8")


def test_tarefa_viva_atras_de_40_novas_ainda_barra(pasta):
    eu = os.getpid()
    _ficha(pasta, "20261001-000000-aaaaaa", "escoar", pid=eu,
           criado=publicacao_filha.criado_em(eu),
           filho={"pid": eu, "criado": publicacao_filha.criado_em(eu)})
    for n in range(40):
        _ficha(pasta, f"20261014-{n:06d}-bbbbbb", "escoar", pid=eu, fim=True)
    # antes do conserto: [] (a viva ficava fora do listar(40))
    vivas = tarefas.rodando("escoar")
    assert [t["chave"] for t in vivas] == ["20261001-000000-aaaaaa"]
    assert tarefas.resumo()["rodando"] == 1


def test_filha_que_nao_sobe_nao_fica_rodando(pasta, monkeypatch):
    def nao_sobe(pasta_, comando, cwd):
        raise OSError("sem permissao para criar o processo")
    monkeypatch.setattr(acoes, "_iniciar_filha", nao_sobe)
    with pytest.raises(OSError):
        tarefas.iniciar("gerar_historia", "gerar", ["python", "x"], ".", chave="t1")
    ficha = tarefas.uma("t1")
    assert ficha["situacao"] == "terminou" and "não subiu" in ficha["erro"]
    assert tarefas.rodando("gerar_historia") == []


def test_ficha_sem_pid_e_sem_filho_vira_sumiu_depois_de_um_minuto(pasta):
    """A ficha de antes do conserto (sem pid, sem fim): o processo do servidor
    caiu entre gravar a ficha e subir a filha."""
    _ficha(pasta, "velha", "trilha", inicio=datetime.now() - timedelta(minutes=5))
    _ficha(pasta, "nova", "trilha")
    assert tarefas.uma("velha")["situacao"] == "sumiu"
    assert tarefas.uma("nova")["situacao"] == "rodando"      # pode estar subindo
    assert [t["chave"] for t in tarefas.rodando("trilha")] == ["nova"]


def test_limpar_velhas_alcanca_alem_das_100_mais_novas(pasta):
    antiga = datetime.now() - timedelta(days=30)
    _ficha(pasta, "20200101-000000-velhaa", "trilha", fim=True, inicio=antiga)
    for n in range(101):
        _ficha(pasta, f"20261014-{n:06d}-nova00", "trilha", fim=True)
    assert tarefas.limpar_velhas() == 1
    assert not (pasta / "20200101-000000-velhaa").exists()
