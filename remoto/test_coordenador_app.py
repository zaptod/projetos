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
    texto = "ação " * 700                        # 3500 caracteres, mais de 4 KB em UTF-8
    status, _ = _pedir(servidor, "POST", "/api/coordenador/falar", {"texto": texto},
                       _parear(servidor))
    assert status == 200 and len(cerebro_isolado.entradas_novas()) == 1


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


@pytest.mark.parametrize("metodo,rota,corpo", [
    ("GET", "/api/coordenador/conversa", None),
    ("POST", "/api/coordenador/falar", {"texto": "oi"}),
    ("POST", "/api/coordenador/proposta/0123456789ab", {"decisao": "confirmar"}),
])
def test_rotas_do_cerebro_exigem_pareamento(servidor, cerebro_isolado, metodo, rota, corpo):
    status, _ = _pedir(servidor, metodo, rota, corpo)
    assert status == 401


@pytest.mark.parametrize("rota,corpo", [
    ("/api/coordenador/falar", {"texto": "oi"}),
    ("/api/coordenador/proposta/0123456789ab", {"decisao": "confirmar"}),
])
def test_rotas_do_cerebro_que_agem_exigem_acoes(mundo, cerebro_isolado, rota, corpo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, _ = _pedir(srv, "POST", rota, corpo, _parear(srv))
        assert status == 403
        assert cerebro_isolado.entradas_novas() == []
    finally:
        srv.shutdown()
        srv.server_close()
