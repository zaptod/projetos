# -*- coding: utf-8 -*-
"""A tela do coordenador le o estado opcional e so guarda pedidos fechados."""
from __future__ import annotations

import http.client
import json
import threading
import time

import pytest

from remoto import api_http, orquestrador


def _estado(pulso=None):
    agora = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    return {"pid": 123, "desde": agora, "pulso_em": pulso or agora, "versao": "abc123",
            "servicos": {"app": {"situacao": "rodando", "saude": "ok",
                                    "reinicios_24h": 0}},
            "acoes_pc": [{"id": "bloquear_tela", "rotulo": "Bloquear a tela", "perigo": False},
                          {"id": "apagar", "rotulo": "Apagar", "perigo": True}],
            "eventos": []}


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    return tmp_path / "local" / "neural-fights" / "coordenador" / "estado.json"


@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, com_acoes=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cab = {"Host": f"127.0.0.1:{porta}"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    if corpo is not None:
        corpo = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    conexao.request(metodo, caminho, body=corpo, headers=cab)
    resposta = conexao.getresponse()
    dados = json.loads(resposta.read() or b"{}")
    conexao.close()
    return resposta.status, dados


def _parear(srv):
    codigo = api_http.novo_codigo()
    status, dados = _pedir(srv, "POST", "/api/parear", {"codigo": codigo, "nome": "moto"})
    assert status == 200
    return dados["token"]


def _gravar_estado(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def test_get_sem_arquivo_diz_que_o_coordenador_nao_esta_rodando(servidor):
    status, dados = _pedir(servidor, "GET", "/api/coordenador", token=_parear(servidor))
    assert status == 200
    assert dados == {"vivo": False, "motivo": "o coordenador não está rodando"}


def test_get_com_arquivo_calcula_pulso_e_idade(servidor, mundo):
    _gravar_estado(mundo, _estado())
    status, dados = _pedir(servidor, "GET", "/api/coordenador", token=_parear(servidor))
    assert status == 200
    assert dados["vivo"] is True and isinstance(dados["idade_s"], int)
    assert dados["servicos"]["app"]["saude"] == "ok"


def test_get_com_pulso_velho_diz_que_esta_fora(servidor, mundo):
    velho = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 31))
    _gravar_estado(mundo, _estado(velho))
    status, dados = _pedir(servidor, "GET", "/api/coordenador", token=_parear(servidor))
    assert status == 200 and dados["vivo"] is False


def test_post_valido_grava_comando(servidor, mundo, monkeypatch):
    _gravar_estado(mundo, _estado())
    gravados = []
    monkeypatch.setattr(orquestrador, "gravar_comando",
                        lambda cmd, valor, aparelho="": gravados.append((cmd, valor, aparelho))
                        or {"id": "pedido"})
    token = _parear(servidor)
    status, dados = _pedir(servidor, "POST", "/api/coordenador/comando",
                           {"cmd": "servico_reiniciar", "valor": "app"}, token)
    assert status == 200 and dados["feito"] is True
    assert gravados == [("servico_reiniciar", "app", gravados[0][2])]
    assert len(gravados[0][2]) == 8


def test_post_recusa_cmd_fora_da_lista(servidor, mundo):
    _gravar_estado(mundo, _estado())
    status, _ = _pedir(servidor, "POST", "/api/coordenador/comando",
                        {"cmd": "apagar_tudo", "valor": "app"}, _parear(servidor))
    assert status == 400


@pytest.mark.parametrize("corpo", [
    {"cmd": "servico_ligar", "valor": "desconhecido"},
    {"cmd": "pc_acao", "valor": "desconhecida"},
])
def test_post_recusa_servico_ou_acao_desconhecidos(servidor, mundo, corpo):
    _gravar_estado(mundo, _estado())
    status, _ = _pedir(servidor, "POST", "/api/coordenador/comando", corpo, _parear(servidor))
    assert status == 400


def test_post_perigoso_exige_confirmacao(servidor, mundo):
    _gravar_estado(mundo, _estado())
    status, _ = _pedir(servidor, "POST", "/api/coordenador/comando",
                        {"cmd": "pc_acao", "valor": "apagar"}, _parear(servidor))
    assert status == 400


def test_post_sem_token_e_recusado(servidor):
    status, _ = _pedir(servidor, "POST", "/api/coordenador/comando",
                        {"cmd": "servico_ligar", "valor": "app"})
    assert status == 401


def test_post_sem_acoes_e_recusado(mundo):
    _gravar_estado(mundo, _estado())
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, _ = _pedir(srv, "POST", "/api/coordenador/comando",
                            {"cmd": "servico_ligar", "valor": "app"}, _parear(srv))
        assert status == 403
    finally:
        srv.shutdown()
        srv.server_close()


# ------------------------------------------------ o cerebro (02/10/2026)
@pytest.fixture
def cerebro_isolado(tmp_path, monkeypatch):
    """A pasta do cerebro e a do teste; executar uma proposta nao toca o PC."""
    from coordenador import cerebro
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coordenador"))
    executadas = []
    monkeypatch.setattr(cerebro, "_executar_proposta",
                        lambda acao: executadas.append(acao) or "executada (dublê)")
    monkeypatch.setattr(cerebro, "executadas", executadas, raising=False)
    return cerebro


def test_falar_grava_a_entrada_e_a_conversa(servidor, cerebro_isolado):
    token = _parear(servidor)
    status, dados = _pedir(servidor, "POST", "/api/coordenador/falar",
                           {"texto": "como estão os serviços?"}, token)
    assert status == 200 and dados["feito"] is True
    assert [e["texto"] for e in cerebro_isolado.entradas_novas()] == ["como estão os serviços?"]
    status, dados = _pedir(servidor, "GET", "/api/coordenador/conversa", token=token)
    assert status == 200
    assert dados["conversa"][-1]["de"] == "adrian" and dados["propostas"] == []
    assert "limite_hora" in dados["cerebro"]


def test_falar_longo_com_acento_passa_dos_4_kb(servidor, cerebro_isolado):
    from coordenador import pedidos
    texto = "ação " * 700                        # 3500 caracteres, mais de 4 KB em UTF-8
    status, dados = _pedir(servidor, "POST", "/api/coordenador/falar", {"texto": texto},
                           _parear(servidor))
    assert status == 200 and dados["para"] == "orquestrador"
    assert [p["texto"] for p in pedidos.para_o_app()["pedidos"]] == [texto.strip()]


def test_pedido_vira_item_do_orquestrador_e_aparece_na_conversa(servidor, cerebro_isolado):
    """03/10: o pedido livre nao vai ao cerebro (so leitura): vira `pedido`,
    que o pulso do coordenador entrega a um trabalhador `orquestrador`."""
    from coordenador import pedidos
    token = _parear(servidor)
    status, dados = _pedir(servidor, "POST", "/api/coordenador/falar",
                           {"texto": "conserte o botão de reiniciar do app"}, token)
    assert status == 200 and dados["para"] == "orquestrador" and dados["situacao"] == "recebido"
    assert cerebro_isolado.entradas_novas() == []
    assert dados["titulo"] == "conserte o botão de reiniciar do app"
    # 05/10 (conferente 3): texto solto nunca continua; e pedido novo
    status, dados2 = _pedir(servidor, "POST", "/api/coordenador/falar",
                            {"texto": "e o de parar também"}, token)
    assert dados2["id"] != dados["id"] and dados2["continuacao"] is False
    status, velho = _pedir(servidor, "POST", "/api/coordenador/falar", {"novo": True}, token)
    assert status == 200 and velho["novo_assunto"] is False        # a casca velha nao quebra
    assert pedidos.para_o_app()["novo_assunto"] is False
    status, dados3 = _pedir(servidor, "POST", "/api/coordenador/pedido/" + dados["id"]
                            + "/responder", {"texto": "e o de parar junto"}, token)
    assert status == 200 and dados3["id"] == dados["id"]
    assert dados3["titulo"] == "conserte o botão de reiniciar do app"
    status, conversa = _pedir(servidor, "GET", "/api/coordenador/conversa", token=token)
    assert status == 200 and conversa["propostas"] == []           # o cerebro continua la
    assert [p["id"] for p in conversa["pedidos"]] == [dados2["id"], dados["id"]]
    textos = [m["texto"] for m in conversa["conversa"]]
    assert "conserte o botão de reiniciar do app" in textos and "e o de parar também" in textos
    assert any(m.get("de") == "orquestrador" for m in conversa["conversa"])


def test_falar_vazio_e_recusado(servidor, cerebro_isolado):
    status, _ = _pedir(servidor, "POST", "/api/coordenador/falar", {"texto": "  "},
                       _parear(servidor))
    assert status == 400


def test_proposta_confirmada_pelo_app_executa_e_a_vencida_nao(servidor, cerebro_isolado):
    from datetime import datetime, timedelta
    viva = cerebro_isolado.propor({"tipo": "pc_acao", "valor": "suspender", "porque": "x",
                                   "perigo": True})
    velha = cerebro_isolado.propor({"tipo": "pc_acao", "valor": "suspender", "porque": "x",
                                    "perigo": True}, agora=datetime.now() - timedelta(minutes=31))
    token = _parear(servidor)
    status, dados = _pedir(servidor, "GET", "/api/coordenador/conversa", token=token)
    assert [p["situacao"] for p in dados["propostas"]] == ["vencida", "pendente"]
    status, dados = _pedir(servidor, "POST", f"/api/coordenador/proposta/{viva['id']}",
                           {"decisao": "confirmar"}, token)
    assert status == 200 and dados["feito"] is True
    assert [a["valor"] for a in cerebro_isolado.executadas] == ["suspender"]
    status, _ = _pedir(servidor, "POST", f"/api/coordenador/proposta/{velha['id']}",
                       {"decisao": "confirmar"}, token)
    assert status == 409 and len(cerebro_isolado.executadas) == 1
    status, _ = _pedir(servidor, "POST", "/api/coordenador/proposta/0123456789ab",
                       {"decisao": "confirmar"}, token)
    assert status == 404
    status, _ = _pedir(servidor, "POST", f"/api/coordenador/proposta/{viva['id']}",
                       {"decisao": "talvez"}, token)
    assert status == 400


def _parado_esperando_voce(pedidos, texto="arquive os vídeos no Drive"):
    """Um pedido que parou esperando o Adrian, com trabalhador (como o cd2e5e0c)."""
    p = pedidos.registrar(texto, "app", novo=True)
    with pedidos._TRAVA:
        dados = pedidos._ler()
        alvo = next(x for x in dados["pedidos"] if x["id"] == p["id"])
        alvo.update(situacao="esperando_voce", trabalhador=p["id"],
                    motivo="bloqueado: falta o login do Drive")
        pedidos._gravar(dados)
    return p


def test_responder_vai_ao_pedido_parado_pelo_id_e_o_texto_livre_nao(servidor, cerebro_isolado):
    """v2 (05/10): o pedido que parou so recebe a resposta EXPLICITA."""
    from coordenador import pedidos
    token = _parear(servidor)
    p = _parado_esperando_voce(pedidos)
    status, solto = _pedir(servidor, "POST", "/api/coordenador/falar",
                           {"texto": "já loguei no Drive"}, token)
    assert status == 200 and solto["id"] != p["id"] and solto["continuacao"] is False
    status, dados = _pedir(servidor, "POST", f"/api/coordenador/pedido/{p['id']}/responder",
                           {"texto": "já loguei no Drive"}, token)
    assert status == 200 and dados["id"] == p["id"] and dados["continuacao"] is True
    alvo = next(x for x in pedidos.para_o_app()["pedidos"] if x["id"] == p["id"])
    assert alvo["continuar"] is True and alvo["texto"].endswith("já loguei no Drive")


def test_responder_erros(servidor, cerebro_isolado):
    from coordenador import pedidos
    token = _parear(servidor)
    p = _parado_esperando_voce(pedidos)
    rota = f"/api/coordenador/pedido/{p['id']}/responder"
    assert _pedir(servidor, "POST", rota, {"texto": "  "}, token)[0] == 400
    assert _pedir(servidor, "POST", rota, {"texto": "x" * 4001}, token)[0] == 400
    assert _pedir(servidor, "POST", "/api/coordenador/pedido/pedido-00000000/responder",
                  {"texto": "oi"}, token)[0] == 404
    conversa = pedidos.registrar("Coordenador?", "app")          # sem trabalhador
    assert _pedir(servidor, "POST", f"/api/coordenador/pedido/{conversa['id']}/responder",
                  {"texto": "e então"}, token)[0] == 409
    # id fora do formato nem chega na rota
    assert _pedir(servidor, "POST", "/api/coordenador/pedido/../responder",
                  {"texto": "oi"}, token)[0] == 404


def test_responder_com_permissao_de_estado_pendente_e_409(servidor, cerebro_isolado, monkeypatch):
    """Conferente 3 (defeito 7): "sim, pode ligar" pelo Responder negava a
    permissao. Texto nao aprova nem nega: 409, e o cartao tem Permitir/Negar."""
    from coordenador import pedidos
    token = _parear(servidor)
    p = _parado_esperando_voce(pedidos)
    with pedidos._TRAVA:
        dados = pedidos._ler()
        alvo = next(x for x in dados["pedidos"] if x["id"] == p["id"])
        alvo["permissao_estado"] = {"nome": "gerente", "args": ["ligar"], "comando": "gerente ligar",
                                    "trabalhador": p["id"]}
        pedidos._gravar(dados)
    monkeypatch.setattr(pedidos.MESA, "_estado_do", lambda ident: {
        "situacao": "aguardando_permissao", "pedido_permissao": {"categoria": "estado_do_servidor"}})
    status, dados = _pedir(servidor, "POST", f"/api/coordenador/pedido/{p['id']}/responder",
                           {"texto": "sim, pode ligar"}, token)
    assert status == 409 and "Permitir ou Negar" in str(dados)
    alvo = next(x for x in pedidos.para_o_app()["pedidos"] if x["id"] == p["id"])
    assert "sim, pode ligar" not in alvo["texto"] and alvo["permissao_estado"]["comando"] == \
        "gerente ligar"


def test_o_app_tem_um_so_coordenviar_e_o_responder_usa_a_rota():
    """05/10: havia DUAS `function coordEnviar` em coordenador.js; a segunda
    (a do texto) vencia, e o "Reiniciar" de um servico virava um pedido."""
    from pathlib import Path
    js = (Path(api_http.__file__).resolve().parent / "app" / "coordenador.js").read_text(
        encoding="utf-8")
    assert js.count("function coordEnviar(") == 1
    assert "async function coordEnviar(cmd, valor" in js
    assert "/api/coordenador/comando" in js[js.index("async function coordEnviar("):][:600]
    assert "/api/coordenador/pedido/${encodeURIComponent(id)}/responder" in js
    assert "cloneNode" not in js[js.index("function pedidosDesenhar"):]   # o clone perdia o toque
    # conferente 3: a permissao de estado tem Permitir/Negar no proprio
    # cartao (a rota da Equipe), e o "Novo assunto" saiu (todo texto e novo)
    linha = js[js.index("function pedidoLinha"):][:900]
    assert "p.permissao_estado" in linha and "pedidoPermissao(p)" in linha
    permissao = js[js.index("function pedidoPermissao"):][:1500]
    assert "/api/equipe/${encodeURIComponent(" in permissao and "/permissao`" in permissao
    assert "Continuação enviada ao mesmo orquestrador" not in js
    html = (Path(api_http.__file__).resolve().parent / "app" / "index.html").read_text(
        encoding="utf-8")
    assert "pedido-novo" not in html and "coord-novo" not in html and "pedido-novo" not in js


@pytest.mark.parametrize("metodo,rota,corpo", [
    ("GET", "/api/coordenador/conversa", None),
    ("POST", "/api/coordenador/falar", {"texto": "oi"}),
    ("POST", "/api/coordenador/proposta/0123456789ab", {"decisao": "confirmar"}),
    ("POST", "/api/coordenador/pedido/pedido-0123abcd/responder", {"texto": "oi"}),
])
def test_rotas_do_cerebro_exigem_pareamento(servidor, cerebro_isolado, metodo, rota, corpo):
    status, _ = _pedir(servidor, metodo, rota, corpo)
    assert status == 401


@pytest.mark.parametrize("rota,corpo", [
    ("/api/coordenador/falar", {"texto": "oi"}),
    ("/api/coordenador/proposta/0123456789ab", {"decisao": "confirmar"}),
    ("/api/coordenador/pedido/pedido-0123abcd/responder", {"texto": "oi"}),
])
def test_rotas_do_cerebro_que_agem_exigem_acoes(mundo, cerebro_isolado, rota, corpo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, _ = _pedir(srv, "POST", rota, corpo, _parear(srv))
        assert status == 403
        assert cerebro_isolado.entradas_novas() == []
        from coordenador import pedidos
        assert pedidos.para_o_app()["pedidos"] == []
    finally:
        srv.shutdown()
        srv.server_close()
