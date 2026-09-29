# -*- coding: utf-8 -*-
"""A rota do correio no app (Vila das IAs, fase 2): 401 sem token, o
histórico (caso ZERO incluído), o envio (só com `--acoes`), o anexo, o
"visto" e a linha do carteiro na Mesa. O correio vai para `tmp_path`
(`NF_IAS_PASTA`); nada toca o `%LOCALAPPDATA%` real, e nenhum navegador abre.
"""
from __future__ import annotations

import base64
import json
import threading

import pytest

from remoto import api_http, orquestrador
from remoto.test_api_http import _parear, _pedir, mundo, servidor  # noqa: F401

IAS = ("deepseek", "chatgpt", "gemini", "grok")


@pytest.fixture
def caixa(mundo, monkeypatch):                                  # noqa: F811
    monkeypatch.setenv("NF_IAS_PASTA", str(mundo.tmp / "ias"))
    from ias import correio
    return correio


@pytest.fixture
def servidor_com_acoes(caixa):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, com_acoes=True)
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def test_sem_token_nao_le_nem_escreve(servidor, caixa):        # noqa: F811
    resp, _ = _pedir(servidor, "GET", "/api/correio")
    assert resp.status == 401
    resp, _ = _pedir(servidor, "GET", "/api/correio/deepseek")
    assert resp.status == 401
    resp, _ = _pedir(servidor, "POST", "/api/correio/deepseek", {"texto": "oi"})
    assert resp.status == 401
    assert caixa.ler("deepseek") == []


def test_caso_zero_todas_as_caixas_vazias_e_carteiro_nunca(servidor, caixa):   # noqa: F811
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "GET", "/api/correio", token=token)
    assert resp.status == 200
    d = json.loads(dados)
    assert [c["ia"] for c in d["ias"]] == list(IAS)
    assert all(c["pendentes"] == 0 and c["nao_vistas"] == 0 and c["ultima"] is None
               for c in d["ias"])
    assert d["carteiro"]["situacao"] == "nunca"
    assert d["enviar"] is False                       # servidor sem --acoes
    resp, dados = _pedir(servidor, "GET", "/api/correio/grok", token=token)
    assert resp.status == 200
    d = json.loads(dados)
    assert d["mensagens"] == [] and d["rotulo"] == "Grok" and d["casa"]["geracao"] == 0


def test_ia_que_nao_conversa_nao_tem_rota_de_texto(servidor, caixa):   # noqa: F811
    token = _parear(servidor)
    # desde 29/09 o PicassoIA tem caixa (pedidos de imagem): ler e 200, mas
    # texto para ele continua sem rota; IA que o correio nao conhece e 404
    resp, dados = _pedir(servidor, "GET", "/api/correio/picasso", token=token)
    assert resp.status == 200
    d = json.loads(dados)
    assert d["conversa"] is False and d["gerador"]["ia"] == "picasso"
    resp, _ = _pedir(servidor, "POST", "/api/correio/picasso", {"texto": "x"}, token=token)
    assert resp.status == 404
    resp, _ = _pedir(servidor, "GET", "/api/correio/dall-e", token=token)
    assert resp.status == 404


def test_enviar_sem_acoes_e_403_e_nada_entra_na_caixa(servidor, caixa):   # noqa: F811
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "POST", "/api/correio/deepseek", {"texto": "oi"},
                         token=token)
    assert resp.status == 403
    assert "desligadas" in json.loads(dados)["erro"]
    assert caixa.ler("deepseek") == []


def test_enviar_com_acoes_deixa_a_mensagem_pendente_e_o_historico_a_mostra(
        servidor_com_acoes, caixa):
    srv = servidor_com_acoes
    token = _parear(srv)
    resp, dados = _pedir(srv, "POST", "/api/correio/deepseek",
                         {"texto": "PEDIDO DE TEXTO: responda só OK"}, token=token)
    assert resp.status == 200, dados
    d = json.loads(dados)
    assert d["feito"] and d["mensagem"]["situacao"] == "pendente"
    assert d["mensagem"]["de"] == "adrian" and d["mensagem"]["thread"] == "casa:deepseek"
    assert d["carteiro"]["situacao"] == "nunca"
    mid = d["mensagem"]["id"]
    # na caixa de verdade, e so nela
    assert [m["id"] for m in caixa.pendentes("deepseek")] == [mid]
    assert caixa.proxima_pendente()["id"] == mid
    assert caixa.ler("gemini") == []
    resp, dados = _pedir(srv, "GET", "/api/correio/deepseek", token=token)
    d = json.loads(dados)
    assert d["enviar"] is True
    assert [m["id"] for m in d["mensagens"]] == [mid]
    assert d["mensagens"][0]["texto"] == "PEDIDO DE TEXTO: responda só OK"
    # ler a caixa registra a presenca: o carteiro nao manda ao Telegram
    assert caixa.app_esta_olhando("deepseek")
    assert not caixa.app_esta_olhando("gemini")
    resp, dados = _pedir(srv, "GET", "/api/correio", token=token)
    d = json.loads(dados)
    ds = next(c for c in d["ias"] if c["ia"] == "deepseek")
    assert ds["pendentes"] == 1 and ds["ultima"]["id"] == mid


def test_texto_vazio_e_400(servidor_com_acoes, caixa):
    token = _parear(servidor_com_acoes)
    resp, dados = _pedir(servidor_com_acoes, "POST", "/api/correio/gemini", {"texto": "  "},
                         token=token)
    assert resp.status == 400
    assert "vazia" in json.loads(dados)["erro"]


def test_anexo_em_base64_vai_para_a_pasta_da_ia_e_o_historico_so_mostra_o_nome(
        servidor_com_acoes, caixa):
    srv = servidor_com_acoes
    token = _parear(srv)
    png = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
    resp, dados = _pedir(srv, "POST", "/api/correio/gemini", {
        "texto": "o que é isto?",
        "anexos": [{"nome": "foto.png", "b64": base64.b64encode(png).decode()}]}, token=token)
    assert resp.status == 200, dados
    m = json.loads(dados)["mensagem"]
    assert len(m["anexos"]) == 1
    caminho = caixa.pasta("gemini") / "anexos"
    assert caminho.is_dir() and any(caminho.iterdir())
    resp, dados = _pedir(srv, "GET", "/api/correio/gemini", token=token)
    listado = json.loads(dados)["mensagens"][0]["anexos"]
    assert listado and listado[0].endswith("foto.png") and "\\" not in listado[0]
    # anexo que nao e imagem, ou base64 podre: 400 e nada na caixa
    resp, _ = _pedir(srv, "POST", "/api/correio/gemini", {
        "texto": "x", "anexos": [{"nome": "v.exe", "b64": base64.b64encode(b"MZ").decode()}]},
        token=token)
    assert resp.status == 400
    resp, _ = _pedir(srv, "POST", "/api/correio/gemini", {
        "texto": "x", "anexos": [{"nome": "a.png", "b64": "%%%"}]}, token=token)
    assert resp.status == 400
    assert len(caixa.ler("gemini")) == 1


def test_resposta_do_carteiro_aparece_e_o_visto_a_marca(servidor_com_acoes, caixa):
    srv = servidor_com_acoes
    token = _parear(srv)
    m = caixa.enviar("chatgpt", "oi")
    caixa.atualizar("chatgpt", m["id"], situacao="entregue", entregue_em="x")
    caixa.atualizar("chatgpt", m["id"], situacao="respondida", resposta="OK, Adrian.",
                    dur_s=6.2, modelo="GPT")
    resp, dados = _pedir(srv, "GET", "/api/correio", token=token)
    c = next(x for x in json.loads(dados)["ias"] if x["ia"] == "chatgpt")
    assert c["nao_vistas"] == 1 and c["ultima"]["resposta"] == "OK, Adrian."
    resp, dados = _pedir(srv, "GET", "/api/correio/chatgpt", token=token)
    h = json.loads(dados)["mensagens"][0]
    assert h["situacao"] == "respondida" and h["resposta"] == "OK, Adrian."
    assert h["modelo"] == "GPT" and h["dur_s"] == 6.2
    resp, dados = _pedir(srv, "POST", "/api/correio/chatgpt/visto", {}, token=token)
    assert resp.status == 200 and json.loads(dados)["vistas"] == 1
    resp, dados = _pedir(srv, "GET", "/api/correio", token=token)
    c = next(x for x in json.loads(dados)["ias"] if x["ia"] == "chatgpt")
    assert c["nao_vistas"] == 0
    # o visto nao depende de --acoes (nao executa nada): funciona sem elas
    resp, dados = _pedir(srv, "POST", "/api/correio/chatgpt/visto", {}, token=token)
    assert resp.status == 200 and json.loads(dados)["vistas"] == 0


def test_falha_do_carteiro_vem_com_o_motivo(servidor_com_acoes, caixa):
    srv = servidor_com_acoes
    token = _parear(srv)
    m = caixa.enviar("grok", "oi")
    caixa.atualizar("grok", m["id"], situacao="falhou", erro="o site diz: «limite»",
                    categoria="limite")
    resp, dados = _pedir(srv, "GET", "/api/correio/grok", token=token)
    h = json.loads(dados)["mensagens"][0]
    assert h["situacao"] == "falhou" and h["categoria"] == "limite" and "limite" in h["erro"]


def test_a_mesa_mostra_o_carteiro_e_as_caixas(caixa, monkeypatch, tmp_path):
    monkeypatch.setenv("NF_ORQUESTRADOR_PASTA", str(tmp_path / "orq"))
    # caso ZERO: nunca rodou, caixas vazias, e a Mesa nao quebra
    d = orquestrador.para_o_app()
    assert d["carteiro"]["situacao"] == "nunca"
    assert d["carteiro"]["pendentes"] == 0
    assert [c["ia"] for c in d["carteiro"]["caixas"]] == list(IAS)
    caixa.enviar("deepseek", "oi")
    caixa.gravar_estado_do_carteiro({"situacao": "entregando", "ia": "deepseek",
                                     "mensagem_id": "x", "desde": "2026-09-29T07:00:00"})
    d = orquestrador.para_o_app()
    assert d["carteiro"]["situacao"] == "entregando" and d["carteiro"]["ia"] == "deepseek"
    assert d["carteiro"]["pendentes"] == 1
    ds = next(c for c in d["carteiro"]["caixas"] if c["ia"] == "deepseek")
    assert ds["pendentes"] == 1


def test_o_servidor_serve_o_conversa_js_e_o_html_o_carrega(servidor):   # noqa: F811
    resp, dados = _pedir(servidor, "GET", "/conversa.js")
    assert resp.status == 200 and b"conversaAbrir" in dados
    resp, dados = _pedir(servidor, "GET", "/")
    assert b'<script src="conversa.js"></script>' in dados
    assert b'id="tela-conversa"' in dados
