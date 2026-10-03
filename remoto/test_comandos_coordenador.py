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


def test_pergunta_de_estado_grava_a_entrada_e_responde_recebido(cerebro):
    resposta, arquivo = comandos.executar("o carteiro está rodando?")
    assert arquivo is None
    assert resposta.startswith("🛰 recebido, pensando") and "/ajuda" in resposta
    entradas = cerebro.entradas_novas()
    assert [(e["texto"], e["origem"]) for e in entradas] == [
        ("o carteiro está rodando?", "telegram")]
    assert cerebro.conversa()[-1]["de"] == "adrian"


def test_texto_livre_vira_pedido_do_orquestrador(cerebro):
    """03/10: o resto e PEDIDO; um trabalhador `orquestrador` do servidor
    atende, sem o VS Code. /novo abre outro assunto."""
    from coordenador import pedidos
    resposta, _ = comandos.executar("reinicia o carteiro, por favor")
    assert resposta.startswith("🧭 recebido") and "/ajuda" in resposta
    assert cerebro.entradas_novas() == []
    lista = pedidos.para_o_app()["pedidos"]
    assert [(p["texto"], p["origem"]) for p in lista] == [
        ("reinicia o carteiro, por favor", "telegram")]
    resposta, _ = comandos.executar("e o bot também")
    assert "MESMO orquestrador" in resposta
    assert len(pedidos.para_o_app()["pedidos"]) == 1
    assert "assunto novo" in comandos.executar("/novo")[0]
    comandos.executar("outra coisa")
    assert len(pedidos.para_o_app()["pedidos"]) == 2


def test_comando_com_barra_continua_igual(cerebro, monkeypatch):
    monkeypatch.setitem(comandos.TABELA, "teste_coord", lambda args: f"ok {args}")
    assert comandos.executar("/teste_coord x") == ("ok x", None)
    assert cerebro.entradas_novas() == []


def test_falha_ao_guardar_responde_sem_derrubar_o_bot(cerebro, monkeypatch):
    def quebra(*a, **k):
        raise OSError("disco cheio")
    from coordenador import pedidos
    monkeypatch.setattr(cerebro, "registrar_entrada", quebra)
    monkeypatch.setattr(pedidos, "registrar", quebra)
    for texto in ("oi", "o app está no ar?"):
        resposta, _ = comandos.executar(texto)
        assert "não consegui guardar" in resposta and "/ajuda" in resposta


def test_sem_pasta_escolhida_o_pytest_nao_escreve_na_entrada_real(monkeypatch):
    # o teste antigo do bot ("apaga tudo por favor") passa por aqui sem
    # escolher pasta: tem de cair na pasta descartavel, nunca na real
    import os
    from coordenador import estado
    monkeypatch.delenv("NF_COORDENADOR_PASTA", raising=False)
    real = os.path.join(os.environ.get("LOCALAPPDATA", ""), "neural-fights", "coordenador")
    assert os.path.normcase(str(estado.pasta())) != os.path.normcase(real)
