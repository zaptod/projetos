# -*- coding: utf-8 -*-
"""Telegram: texto sem / vira mensagem para o coordenador (02/10/2026).

O bot nao pensa nem executa: grava na entrada do cerebro e responde que
recebeu. Os comandos com / continuam iguais."""
import pytest

from remoto import comandos


@pytest.fixture
def cerebro(tmp_path, monkeypatch):
    from coordenador import cerebro as modulo
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coordenador"))
    return modulo


def test_texto_livre_grava_a_entrada_e_responde_recebido(cerebro):
    resposta, arquivo = comandos.executar("reinicia o carteiro, por favor")
    assert arquivo is None
    assert resposta.startswith("🛰 recebido, pensando") and "/ajuda" in resposta
    entradas = cerebro.entradas_novas()
    assert [(e["texto"], e["origem"]) for e in entradas] == [
        ("reinicia o carteiro, por favor", "telegram")]
    assert cerebro.conversa()[-1]["de"] == "adrian"


def test_comando_com_barra_continua_igual(cerebro, monkeypatch):
    monkeypatch.setitem(comandos.TABELA, "teste_coord", lambda args: f"ok {args}")
    assert comandos.executar("/teste_coord x") == ("ok x", None)
    assert cerebro.entradas_novas() == []


def test_falha_ao_guardar_responde_sem_derrubar_o_bot(cerebro, monkeypatch):
    def quebra(*a, **k):
        raise OSError("disco cheio")
    monkeypatch.setattr(cerebro, "registrar_entrada", quebra)
    resposta, _ = comandos.executar("oi")
    assert "não consegui guardar" in resposta and "/ajuda" in resposta


def test_sem_pasta_escolhida_o_pytest_nao_escreve_na_entrada_real(monkeypatch):
    # o teste antigo do bot ("apaga tudo por favor") passa por aqui sem
    # escolher pasta: tem de cair na pasta descartavel, nunca na real
    import os
    from coordenador import estado
    monkeypatch.delenv("NF_COORDENADOR_PASTA", raising=False)
    real = os.path.join(os.environ.get("LOCALAPPDATA", ""), "neural-fights", "coordenador")
    assert os.path.normcase(str(estado.pasta())) != os.path.normcase(real)
