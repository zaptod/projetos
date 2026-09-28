# -*- coding: utf-8 -*-
"""A tela Decisoes: registro, midia por Range, resposta e aviso.

Nada aqui toca a rede de verdade nem o registro real: a pasta do registro, o
arquivo de pareamento e o Telegram sao trocados por dubles, e o servidor sobe
numa porta aleatoria do loopback.
"""
from __future__ import annotations

import http.client
import json
import threading

import pytest

from remoto import acoes, api_http, decisoes

VIDEO = bytes(range(256)) * 400            # 102.400 bytes; o conteudo nao importa
IMAGEM = b"\x89PNG\r\n\x1a\n" + b"x" * 5000


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(decisoes, "PASTA", tmp_path / "decisoes")
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    avisos = []
    monkeypatch.setattr(acoes, "_entregar", avisos.append)
    midia = tmp_path / "midia"
    midia.mkdir()
    (midia / "duelo_ANTES.mp4").write_bytes(VIDEO)
    (midia / "duelo_DEPOIS.mp4").write_bytes(VIDEO[::-1])
    (midia / "quadro.png").write_bytes(IMAGEM)
    (midia / "segredo.txt").write_text("nao", encoding="utf-8")
    yield type("Mundo", (), {"tmp": tmp_path, "midia": midia, "avisos": avisos})
    acoes._FILA_AVISOS.join()


def _item(mundo, **k):
    padrao = dict(titulo="Som real da luta (16A)",
                  pergunta="O som real (DEPOIS) substitui o sintetizado (ANTES)?",
                  opcoes=["Aprovar|re-render na madrugada",
                          "Aprovar, mas trocar alguns sons (diga quais)",
                          "Reprovar: manter o sintetizado"],
                  midias=[(mundo.midia / "duelo_ANTES.mp4", "ANTES"),
                          (mundo.midia / "duelo_DEPOIS.mp4", "DEPOIS"),
                          (mundo.midia / "quadro.png", "QUADRO")])
    padrao.update(k)
    return decisoes.adicionar(padrao.pop("titulo"), padrao.pop("pergunta"),
                              padrao.pop("opcoes"), padrao.pop("midias"), **padrao)


# ============================================================ registro
def test_o_celular_nunca_ve_caminho(mundo):
    _item(mundo)
    (item,) = decisoes.listar("pendente")
    texto = json.dumps(item, ensure_ascii=False)
    assert str(mundo.midia) not in texto and "arquivo" not in texto
    assert [m["rotulo"] for m in item["midias"]] == ["ANTES", "DEPOIS", "QUADRO"]
    assert [m["tipo"] for m in item["midias"]] == ["video/mp4", "video/mp4", "image/png"]
    assert item["opcoes"][1]["pede_comentario"] is True
    assert item["opcoes"][0] == {"rotulo": "Aprovar", "descricao": "re-render na madrugada",
                                 "pede_comentario": False}


@pytest.mark.parametrize("midia,trecho", [
    ("nao_existe.mp4", "não existe"),
    ("segredo.txt", "não toca"),
])
def test_midia_que_nao_existe_ou_nao_toca_nao_entra(mundo, midia, trecho):
    with pytest.raises(decisoes.Recusa, match=trecho):
        _item(mundo, midias=[(mundo.midia / midia, "X")])
    assert not decisoes.caminho_registro().exists()


def test_id_vem_do_titulo_e_nao_repete(mundo):
    assert _item(mundo)["id"] == "som-real-da-luta-16a"
    assert _item(mundo)["id"] == "som-real-da-luta-16a-2"
    with pytest.raises(decisoes.Recusa, match="já existe"):
        _item(mundo, id="som-real-da-luta-16a")


def test_copiar_traz_a_midia_para_a_pasta_do_registro(mundo):
    item = _item(mundo, midias=[(mundo.midia / "quadro.png", "")], copiar=True)
    (caminho, tipo) = decisoes.midia(item["id"], 0)
    assert tipo == "image/png" and decisoes.pasta() in caminho.parents
    (mundo.midia / "quadro.png").unlink()              # o original some
    assert decisoes.midia(item["id"], 0) is not None


def test_registro_ilegivel_recusa_e_nao_e_regravado(mundo):
    decisoes.caminho_registro().parent.mkdir(parents=True)
    decisoes.caminho_registro().write_text("{quebrado", encoding="utf-8")
    with pytest.raises(decisoes.Recusa, match="ilegível"):
        _item(mundo)
    assert decisoes.caminho_registro().read_text(encoding="utf-8") == "{quebrado"


# ============================================================ resposta
def test_resposta_vai_para_o_jsonl_e_marca_o_item(mundo):
    item = _item(mundo)
    resposta = decisoes.responder(item["id"], 2, "  ficou abafado  ", "ap123")
    (linha,) = [json.loads(l) for l in
                decisoes.caminho_respostas().read_text(encoding="utf-8").splitlines()]
    assert linha == resposta
    assert {k: linha[k] for k in ("id", "opcao", "opcao_rotulo", "comentario")} == {
        "id": item["id"], "opcao": 2, "opcao_rotulo": "Reprovar: manter o sintetizado",
        "comentario": "ficou abafado"}
    assert linha["em"] and linha["aparelho"] == "ap123"
    assert decisoes.listar("pendente") == []
    (feita,) = decisoes.listar("respondida")
    assert feita["resposta"]["opcao_rotulo"] == "Reprovar: manter o sintetizado"
    with pytest.raises(decisoes.Recusa, match="já foi respondida"):
        decisoes.responder(item["id"], 0)


@pytest.mark.parametrize("opcao", [3, -1, "0", None, True])
def test_opcao_invalida_nao_grava(mundo, opcao):
    item = _item(mundo)
    with pytest.raises(decisoes.Recusa):
        decisoes.responder(item["id"], opcao)
    assert not decisoes.caminho_respostas().exists()


def test_opcao_que_pede_comentario_sem_comentario(mundo):
    item = _item(mundo)
    with pytest.raises(decisoes.Recusa, match="pede um comentário"):
        decisoes.responder(item["id"], 1, "   ")
    assert decisoes.responder(item["id"], 1, "trocar o soco")["opcao"] == 1


def test_aviso_do_telegram(mundo):
    item = _item(mundo)
    texto = decisoes.texto_do_aviso(decisoes.responder(item["id"], 0))
    assert texto == "🗳 Adrian decidiu: Som real da luta (16A) → Aprovar"


# ============================================================ servidor
@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None, cabecalhos=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
    cab = {"Host": f"127.0.0.1:{porta}", **(cabecalhos or {})}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    if corpo is not None:
        corpo = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    conexao.request(metodo, caminho, body=corpo, headers=cab)
    resp = conexao.getresponse()
    dados = resp.read()
    conexao.close()
    return resp, dados


def _token():
    return api_http.trocar_codigo(api_http.novo_codigo(), "moto")


def _url(srv, item_id, indice, token):
    resp, dados = _pedir(srv, "GET", f"/api/decisao/{item_id}/midia/{indice}",
                         token=token)
    assert resp.status == 200, dados
    return json.loads(dados)


def test_sem_token_nada_sai(servidor, mundo):
    item = _item(mundo)
    assert _pedir(servidor, "GET", "/api/decisoes")[0].status == 401
    assert _pedir(servidor, "GET", f"/api/decisao/{item['id']}/midia/0")[0].status == 401
    resp, _ = _pedir(servidor, "POST", "/api/decisao/responder",
                     {"id": item["id"], "opcao": 0})
    assert resp.status == 401
    assert not decisoes.caminho_respostas().exists()


def test_video_toca_por_range(servidor, mundo):
    item = _item(mundo)
    token = _token()
    ficha = _url(servidor, item["id"], 0, token)
    assert ficha["url"].startswith("/v/") and ficha["tipo"] == "video/mp4"
    assert str(mundo.midia) not in json.dumps(ficha)
    total = len(VIDEO)

    resp, corpo = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": "bytes=0-9"})
    assert resp.status == 206 and corpo == VIDEO[:10]
    assert resp.getheader("Content-Range") == f"bytes 0-9/{total}"
    assert resp.getheader("Content-Type") == "video/mp4"
    assert resp.getheader("Accept-Ranges") == "bytes"

    # o Android pede "bytes=0-" e depois pula para o meio (o avancar)
    resp, corpo = _pedir(servidor, "GET", ficha["url"],
                         cabecalhos={"Range": f"bytes=50000-{total - 1}"})
    assert resp.status == 206 and corpo == VIDEO[50000:]
    assert resp.getheader("Content-Range") == f"bytes 50000-{total - 1}/{total}"

    resp, _ = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": f"bytes={total}-"})
    assert resp.status == 416 and resp.getheader("Content-Range") == f"bytes */{total}"
    resp, _ = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": "linhas=0-9"})
    assert resp.status == 416


def test_imagem_vem_inteira_e_com_o_tipo_certo(servidor, mundo):
    item = _item(mundo)
    ficha = _url(servidor, item["id"], 2, _token())
    assert ficha["tipo"] == "image/png"
    resp, corpo = _pedir(servidor, "GET", ficha["url"])
    assert resp.status == 200 and corpo == IMAGEM
    assert resp.getheader("Content-Type") == "image/png"
    resp, corpo = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": "bytes=0-7"})
    assert resp.status == 206 and corpo == IMAGEM[:8]


@pytest.mark.parametrize("caminho", [
    "/api/decisao/som-real-da-luta-16a/midia/3",          # indice fora
    "/api/decisao/nao-existe/midia/0",                    # item que nao existe
    "/api/decisao/..%2F..%2Fsegredo/midia/0",             # caminho disfarcado
    "/api/decisao/som-real-da-luta-16a/midia/-1",
    "/api/decisao/som-real-da-luta-16a/midia/0/../../segredo.txt",
])
def test_midia_fora_do_registro_e_recusada(servidor, mundo, caminho):
    _item(mundo)
    resp, _ = _pedir(servidor, "GET", caminho, token=_token())
    assert resp.status == 404


def test_arquivo_que_sumiu_depois_do_registro(servidor, mundo):
    item = _item(mundo)
    (mundo.midia / "duelo_ANTES.mp4").unlink()
    resp, _ = _pedir(servidor, "GET", f"/api/decisao/{item['id']}/midia/0",
                     token=_token())
    assert resp.status == 404


def test_bilhete_inventado_nao_serve_nada(servidor, mundo):
    _item(mundo)
    resp, _ = _pedir(servidor, "GET", "/v/inventado", cabecalhos={"Range": "bytes=0-9"})
    assert resp.status == 404


def test_responder_pelo_app_grava_marca_e_avisa(servidor, mundo):
    item = _item(mundo)
    token = _token()
    resp, dados = _pedir(servidor, "POST", "/api/decisao/responder",
                         {"id": item["id"], "opcao": 1, "comentario": "trocar o soco"},
                         token=token)
    assert resp.status == 200, dados
    (linha,) = decisoes.caminho_respostas().read_text(encoding="utf-8").splitlines()
    assert json.loads(linha)["opcao_rotulo"] == "Aprovar, mas trocar alguns sons (diga quais)"
    acoes._FILA_AVISOS.join()
    (aviso,) = mundo.avisos
    assert "Adrian decidiu: Som real da luta (16A) → Aprovar, mas trocar" in aviso
    assert "trocar o soco" in aviso
    resp, dados = _pedir(servidor, "GET", "/api/decisoes", token=token)
    lista = json.loads(dados)
    assert lista["pendentes"] == [] and lista["respondidas"][0]["id"] == item["id"]
    resp, _ = _pedir(servidor, "POST", "/api/decisao/responder",
                     {"id": item["id"], "opcao": 0}, token=token)
    assert resp.status == 409
    resp, _ = _pedir(servidor, "POST", "/api/decisao/responder",
                     {"id": "nao-existe", "opcao": 0}, token=token)
    assert resp.status == 404


def test_a_tela_e_servida(servidor, mundo):
    resp, corpo = _pedir(servidor, "GET", "/decisoes.js")
    assert resp.status == 200 and b"decisoesMostrar" in corpo
    resp, corpo = _pedir(servidor, "GET", "/")
    assert b'data-tela="decisoes"' in corpo and b'src="decisoes.js"' in corpo


# ================================================================= cli
def test_cli_adicionar_listar_e_onde(mundo, capsys):
    assert decisoes.main([
        "adicionar", "--titulo", "Hitstop: a pausinha no impacto",
        "--pergunta", "Ligar a pausa curta?", "--opcao", "Ligar",
        "--opcao", "Deixar desligado",
        "--midia", f"{mundo.midia / 'quadro.png'}|QUADRO", "--copiar"]) == 0
    assert "registrada: hitstop-a-pausinha-no-impacto" in capsys.readouterr().out
    assert decisoes.main(["listar"]) == 0
    assert "Hitstop" in capsys.readouterr().out
    assert decisoes.main(["onde"]) == 0
    saida = capsys.readouterr().out
    assert str(decisoes.caminho_respostas()) in saida
    assert decisoes.main(["adicionar", "--titulo", "sem opcao"]) == 2
