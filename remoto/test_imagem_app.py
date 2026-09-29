# -*- coding: utf-8 -*-
"""Pedir imagem pelo app (29/09/2026): a rota do pedido (token, `--acoes`,
proporcao pela ficha, gerador que nao gera), a imagem servida SO com token e
SO de pedido registrado e respondido (nada de caminho vindo do celular), a
galeria e o caso ZERO. O correio vai para `tmp_path` (`NF_IAS_PASTA`);
nenhum navegador abre.
"""
from __future__ import annotations

import json
import threading

import pytest

from remoto import api_http
from remoto.test_api_http import _parear, _pedir, mundo, servidor  # noqa: F401


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


def _respondida(caixa, onde="picasso", gerador="picasso"):
    """Um pedido que o carteiro (dublê) ja gerou: imagem com prova no disco."""
    from ias import imagem
    m = caixa.pedir_imagem(onde, "a red circle on white", proporcao="1:1")
    corpo = imagem.png_de_teste(32, 32)
    salvo = imagem.guardar(gerador, m["id"], corpo, {"comprovada": True, "metodo": "duble"})
    caixa.atualizar(onde, m["id"], situacao="respondida", gerador=gerador, imagem=salvo,
                    resposta="imagem pronta", respondida_em=caixa.agora())
    return m, corpo


def test_as_listas_de_caixas_batem_com_o_correio(caixa):
    assert tuple(api_http.CAIXAS_DO_CORREIO) == tuple(caixa.CAIXAS)
    assert tuple(api_http.GERADORES_DE_IMAGEM) == tuple(caixa.GERADORES)


def test_caso_zero(servidor, caixa):                           # noqa: F811
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "GET", "/api/imagens", token=token)
    assert resp.status == 200
    assert json.loads(dados)["imagens"] == []
    resp, dados = _pedir(servidor, "GET", "/api/correio", token=token)
    d = json.loads(dados)
    assert {g["ia"] for g in d["geradores"]} == set(caixa.GERADORES)
    assert [c["ia"] for c in d["imagens"]] == ["picasso", "dreamface", "digen", "livre"]
    assert all(c["ultima"] is None for c in d["imagens"])
    resp, dados = _pedir(servidor, "GET", "/api/correio/livre", token=token)
    d = json.loads(dados)
    assert d["mensagens"] == [] and d["rodizio"][0] == "picasso"
    resp, _ = _pedir(servidor, "GET", "/api/imagem/picasso/abcdef12", token=token)
    assert resp.status == 404


def test_sem_token_nada(servidor, caixa):                      # noqa: F811
    m, _ = _respondida(caixa)
    for rota in ("/api/imagens", f"/api/imagem/picasso/{m['id']}", "/api/correio/picasso"):
        resp, _ = _pedir(servidor, "GET", rota)
        assert resp.status == 401, rota
    resp, _ = _pedir(servidor, "POST", "/api/correio/picasso/imagem",
                     {"prompt": "x", "proporcao": "1:1"})
    assert resp.status == 401


def test_pedir_sem_acoes_e_403(servidor, caixa):               # noqa: F811
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "POST", "/api/correio/picasso/imagem",
                         {"prompt": "x", "proporcao": "1:1"}, token=token)
    assert resp.status == 403
    assert caixa.ler("picasso") == []


def test_pedir_imagem_entra_na_caixa(servidor_com_acoes, caixa):
    token = _parear(servidor_com_acoes)
    resp, dados = _pedir(servidor_com_acoes, "POST", "/api/correio/picasso/imagem",
                         {"prompt": "a red circle on white", "proporcao": "1:1"}, token=token)
    assert resp.status == 200, dados
    m = json.loads(dados)["mensagem"]
    assert m["tipo"] == "imagem" and m["proporcao"] == "1:1" and m["gerador"] == "picasso"
    assert caixa.ler("picasso")[0]["texto"] == "a red circle on white"
    # o rodizio tambem
    resp, dados = _pedir(servidor_com_acoes, "POST", "/api/correio/livre/imagem",
                         {"prompt": "x", "proporcao": "1:1"}, token=token)
    assert resp.status == 200
    assert json.loads(dados)["mensagem"]["gerador"] is None


def test_pedir_imagem_recusa_com_motivo(servidor_com_acoes, caixa):
    token = _parear(servidor_com_acoes)
    casos = [
        ("picasso", {"prompt": "x", "proporcao": "5:7"}, "oferece"),
        ("picasso", {"prompt": "", "proporcao": "1:1"}, "vazio"),
        ("picasso", {"prompt": "a" * 5001, "proporcao": "1:1"}, "5000"),
        ("dreamface", {"prompt": "x", "proporcao": "1:1"}, "créditos 0"),
        ("digen", {"prompt": "x", "proporcao": "1:1"}, "VÍDEO"),
        ("picasso", {"prompt": "x", "proporcao": "1:1", "modelo": "GPT IMAGE 9"}, "modelo"),
    ]
    for ia, corpo, trecho in casos:
        resp, dados = _pedir(servidor_com_acoes, "POST", f"/api/correio/{ia}/imagem", corpo,
                             token=token)
        assert resp.status == 400, (ia, corpo)
        assert trecho in json.loads(dados)["erro"], (ia, dados)
    for ia in ("picasso", "dreamface", "digen"):
        assert caixa.ler(ia) == []
    # quem nao gera nem tem rota de pedido
    resp, _ = _pedir(servidor_com_acoes, "POST", "/api/correio/deepseek/imagem",
                     {"prompt": "x", "proporcao": "1:1"}, token=token)
    assert resp.status == 404


def test_imagem_servida_so_por_bilhete_de_pedido_respondido(servidor, caixa):   # noqa: F811
    token = _parear(servidor)
    m, corpo = _respondida(caixa)
    resp, dados = _pedir(servidor, "GET", f"/api/imagem/picasso/{m['id']}", token=token)
    assert resp.status == 200
    d = json.loads(dados)
    assert d["url"].startswith("/v/") and d["tipo"] == "image/png"
    assert d["nome"] == f"picasso_{m['id']}.png"
    resp, bruto = _pedir(servidor, "GET", d["url"])
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "image/png"
    assert bruto == corpo                                   # bytes originais
    # o mesmo aparelho, pedindo de novo, recebe o MESMO bilhete (nao acumula)
    resp, dados2 = _pedir(servidor, "GET", f"/api/imagem/picasso/{m['id']}", token=token)
    assert json.loads(dados2)["url"] == d["url"]
    # a caixa traz a imagem com o bilhete, e nunca o caminho
    resp, dados = _pedir(servidor, "GET", "/api/correio/picasso", token=token)
    msg = json.loads(dados)["mensagens"][0]
    assert msg["imagem"]["url"] == d["url"]
    texto = dados.decode("utf-8") if isinstance(dados, bytes) else str(dados)
    assert str(caixa.raiz()) not in texto and json.dumps(str(caixa.raiz()))[1:-1] not in texto


def test_pedido_pendente_ou_adulterado_nao_serve(servidor, caixa):   # noqa: F811
    token = _parear(servidor)
    pendente = caixa.pedir_imagem("picasso", "x", proporcao="1:1")
    resp, _ = _pedir(servidor, "GET", f"/api/imagem/picasso/{pendente['id']}", token=token)
    assert resp.status == 404
    m, _ = _respondida(caixa)
    # o registro aponta para fora da pasta: nao serve
    caixa.atualizar("picasso", m["id"], imagem={"arquivo": "../../../remoto.json"})
    resp, _ = _pedir(servidor, "GET", f"/api/imagem/picasso/{m['id']}", token=token)
    assert resp.status == 404
    # id que nao e hex de 8, ou caixa que nao existe: nem casa a rota
    for rota in ("/api/imagem/picasso/..%2F..%2Fx", "/api/imagem/picasso/ABCDEF12",
                 "/api/imagem/etc/abcdef12", f"/api/imagem/picasso/{m['id']}.png"):
        resp, _ = _pedir(servidor, "GET", rota, token=token)
        assert resp.status == 404, rota


def test_galeria_por_ia_e_rodizio(servidor, caixa):            # noqa: F811
    token = _parear(servidor)
    a, _ = _respondida(caixa)
    b, _ = _respondida(caixa, onde="livre", gerador="gemini")
    resp, dados = _pedir(servidor, "GET", "/api/imagens", token=token)
    ids = [i["id"] for i in json.loads(dados)["imagens"]]
    assert set(ids) == {a["id"], b["id"]}
    resp, dados = _pedir(servidor, "GET", "/api/imagens?ia=gemini", token=token)
    itens = json.loads(dados)["imagens"]
    assert [i["id"] for i in itens] == [b["id"]]
    assert itens[0]["caixa"] == "livre" and itens[0]["imagem"]["url"].startswith("/v/")
    resp, dados = _pedir(servidor, "GET", f"/api/imagem/livre/{b['id']}", token=token)
    assert resp.status == 200
    resp, dados = _pedir(servidor, "GET", "/api/imagens?ia=deepseek", token=token)
    assert json.loads(dados)["imagens"] == []


def test_conversa_que_respondeu_com_imagem_mostra_a_imagem(servidor, caixa):   # noqa: F811
    """O gato do Gemini (29/09 14:24): a mensagem e de TEXTO, a resposta foi
    uma imagem; a caixa do Gemini traz a miniatura por bilhete, e a galeria
    do Gemini tambem."""
    from ias import imagem
    token = _parear(servidor)
    m = caixa.enviar("gemini", "Tudo ótimo, gere uma imagem de um gato pra mim")
    corpo = imagem.png_de_teste(300, 300)
    salvo = imagem.guardar("gemini", m["id"], corpo, {"comprovada": True,
                                                       "metodo": "turno_na_casa"})
    caixa.atualizar("gemini", m["id"], situacao="respondida", resposta="(imagem)",
                    imagem=salvo, gerador="gemini", respondida_em=caixa.agora())
    resp, dados = _pedir(servidor, "GET", "/api/correio/gemini", token=token)
    msg = json.loads(dados)["mensagens"][0]
    assert msg["imagem"]["url"].startswith("/v/")
    resp, bruto = _pedir(servidor, "GET", msg["imagem"]["url"])
    assert resp.status == 200 and bruto == corpo
    resp, dados = _pedir(servidor, "GET", "/api/imagens?ia=gemini", token=token)
    assert [i["id"] for i in json.loads(dados)["imagens"]] == [m["id"]]


def test_visto_vale_para_caixa_de_imagem(servidor, caixa):     # noqa: F811
    token = _parear(servidor)
    _respondida(caixa)
    resp, dados = _pedir(servidor, "POST", "/api/correio/picasso/visto", {}, token=token)
    assert resp.status == 200
    assert json.loads(dados)["vistas"] == 1
