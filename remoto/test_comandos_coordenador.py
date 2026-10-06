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
    # 06/10: o recibo de gente (o que entendi, quando comeca), o id so no fim
    assert resposta.startswith("🧭 Entendi: «reinicia o carteiro, por favor».")
    assert cerebro.entradas_novas() == []
    lista = pedidos.para_o_app()["pedidos"]
    assert [(p["texto"], p["origem"]) for p in lista] == [
        ("reinicia o carteiro, por favor", "telegram")]
    # 05/10 (conferente 3): texto solto nunca gruda; continuar e explicito
    primeiro = lista[0]["id"]
    assert f"/responder {primeiro[len('pedido-'):]} <texto>" in resposta
    resposta, _ = comandos.executar("e o bot também")
    assert resposta.startswith("🧭 Entendi: «e o bot também».")
    assert len(pedidos.para_o_app()["pedidos"]) == 2
    curto = primeiro[len("pedido-"):]
    resposta, _ = comandos.executar(f"/responder {curto} e reinicia o app junto")
    assert resposta.startswith(f"🧭 continuação enviada ao pedido {primeiro}")
    assert "reinicia o carteiro" in resposta                # diz DE QUAL pedido
    assert len(pedidos.para_o_app()["pedidos"]) == 2
    alvo = next(p for p in pedidos.para_o_app()["pedidos"] if p["id"] == primeiro)
    assert alvo["continuar"] is True and "e reinicia o app junto" in alvo["texto"]
    assert "não há o pedido" in comandos.executar("/responder ffffffff oi")[0]
    assert "use: /responder" in comandos.executar("/responder")[0]
    assert "pedido novo" in comandos.executar("/novo")[0]


def test_responder_com_quebra_de_linha_depois_do_id(cerebro):
    """Conferente 4: "/responder 7c727778" + quebra de linha + texto virava o
    id "pedido-7c727778\\nja" ("não há o pedido")."""
    from coordenador import pedidos
    comandos.executar("reinicia o carteiro, por favor")
    primeiro = pedidos.para_o_app()["pedidos"][0]["id"]
    curto = primeiro[len("pedido-"):]
    for separador in ("\n", "\t", "  \n "):
        resposta, _ = comandos.executar(f"/responder {curto}{separador}já loguei no Drive")
        assert resposta.startswith(f"🧭 continuação enviada ao pedido {primeiro}"), resposta
    alvo = next(p for p in pedidos.para_o_app()["pedidos"] if p["id"] == primeiro)
    assert alvo["ultima_continuacao"] == "já loguei no Drive"
    assert "use: /responder" in comandos.executar(f"/responder {curto}\n")[0]


@pytest.mark.parametrize("texto", ["ok", "valeu", "obrigado", "beleza"])
def test_mensagem_curta_no_telegram_nao_abre_pedido(cerebro, texto):
    """Conferente 4: "ok" respondia "recebido como pedido novo" e contratava um
    orquestrador pago. Agradecimento solto (lista fixa, conferente 5): um "de
    nada" e o lembrete do /responder (06/10: sem o retrato)."""
    from coordenador import pedidos
    resposta, _ = comandos.executar(texto)
    assert resposta.startswith("🧭 De nada!"), resposta
    assert "/responder" in resposta and "Entendi" not in resposta
    assert [p.get("conversa") for p in pedidos.para_o_app()["pedidos"]] == [True]


@pytest.mark.parametrize("texto", ["já loguei", "e o gerente?", "reinicie o app",
                                   "pode ligar o gerente?"])
def test_texto_curto_fora_da_lista_fixa_e_pedido_no_telegram(cerebro, texto):
    """Conferente 5 (05/10/2026): o "curto" por contagem de palavras engolia
    pedidos de verdade. So a lista fixa e conversa; o resto e pedido."""
    from coordenador import pedidos
    resposta, _ = comandos.executar(texto)
    # 06/10: o recibo de gente, na hora; o id so no fim, para o /responder
    assert resposta.startswith("🧭 Entendi: «"), resposta
    item = pedidos.para_o_app()["pedidos"][0]
    assert resposta.rstrip().endswith(f"/responder {item['id'][len('pedido-'):]} <texto>)")
    assert [p.get("conversa") for p in pedidos.para_o_app()["pedidos"]] == [None]


@pytest.mark.parametrize("texto", ["qual o progresso?", "Coordenador?", "oi",
                                   "bom dia coordenador, qual o progresso?"])
def test_conversa_solta_no_telegram_responde_como_gente(cerebro, texto):
    """Conferente 3 (05/10/2026): o bot respondia "um orquestrador vai atender"
    a "qual o progresso?", que nasce respondido sem orquestrador, e a resposta
    ia ao `avisar` vazio do processo do bot. Desde 06/10 a resposta e de
    gente (nao o retrato com ids), na hora."""
    from coordenador import pedidos
    comandos.executar("corrija o X do aplicativo agora")
    resposta, _ = comandos.executar(texto)
    assert resposta.startswith("🧭 Oi, Adrian!"), resposta
    assert "orquestrador do servidor vai atender" not in resposta
    assert "Tem 1 esperando para começar" in resposta       # o pedido aberto conta
    assert "pedido-" not in resposta and "Retrato" not in resposta
    situacoes = sorted(p["situacao"] for p in pedidos.para_o_app()["pedidos"])
    assert situacoes == ["recebido", "respondido"]


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
