# -*- coding: utf-8 -*-
"""Arena do celular: pareamento, uma GPU por vez e MP4 com Range."""
from __future__ import annotations

import json
import sys
import types
import urllib.parse

from remoto import api_http, arena, tarefas
from remoto.test_api_http import _parear, _pedir


def _opcoes():
    return {"personagens": [
        {"nome": "Ana", "classe": "Mago", "cor_classe": "#123456", "arma": "Cajado", "tipo_arma": "Magica"},
        {"nome": "Beto", "classe": "Ninja", "cor_classe": "#654321", "arma": "Kunai", "tipo_arma": "Dupla"},
    ], "mapas": [{"id": "Arena", "nome": "Arena"}]}


def test_worker_exporta_e_renderiza_com_duble(tmp_path, monkeypatch):
    comandos = []
    monkeypatch.setattr(arena.subprocess, "run", lambda comando, check: comandos.append(comando))
    monkeypatch.setitem(sys.modules, "neural_fights.recording.timeline_arquivo",
                        types.SimpleNamespace(carregar=lambda caminho: {"resultado": {"vencedor": "Ana"}}))

    def renderizar(timeline, mp4):
        assert timeline["resultado"]["vencedor"] == "Ana"
        mp4.write_bytes(b"mp4 falso")
    monkeypatch.setitem(sys.modules, "random_builds.builds.palco.render",
                        types.SimpleNamespace(renderizar=renderizar))
    arena.executar("Ana", "Beto", "Arena", 77, tmp_path)
    assert comandos[0][2:4] == ["neural_fights.simulation.manual", "--exportar-palco"]
    assert comandos[0][comandos[0].index("--seed") + 1] == "77"
    assert (tmp_path / "luta.mp4").read_bytes() == b"mp4 falso"
    assert json.loads((tmp_path / "luta.json").read_text(encoding="utf-8"))["vencedor"] == "Ana"


def test_arena_pede_pareamento_acoes_e_sobe_tarefa(servidor, mundo, monkeypatch):
    monkeypatch.setattr(api_http, "PASTA_ARENA", mundo.tmp / "arena")
    monkeypatch.setattr(api_http, "opcoes_da_arena", _opcoes)
    pedidos = []
    monkeypatch.setattr(tarefas, "rodando", lambda acao: [])
    monkeypatch.setattr(tarefas, "iniciar", lambda *args: pedidos.append(args) or args[-1])
    corpo = {"p1": "Ana", "p2": "Beto", "mapa": "Arena", "semente": 77}
    assert _pedir(servidor, "POST", "/api/arena/luta", corpo)[0].status == 401
    token = _parear(servidor)
    assert _pedir(servidor, "POST", "/api/arena/luta", corpo, token=token)[0].status == 403
    servidor.RequestHandlerClass.estado.com_acoes = True
    resp, dados = _pedir(servidor, "POST", "/api/arena/luta", corpo, token=token)
    assert resp.status == 202
    luta = json.loads(dados)
    assert luta["semente"] == 77 and luta["id"]
    comando = pedidos[0][2]
    assert comando[:3] == [api_http.sys.executable, "-m", "remoto.arena"]
    assert comando[comando.index("--semente") + 1] == "77"
    assert "--pasta" in comando and comando[comando.index("--pasta") + 1].endswith(luta["id"])


def test_arena_recusa_segundo_render_e_video_tem_range(servidor, mundo, monkeypatch):
    pasta = mundo.tmp / "arena" / "luta-1"
    pasta.mkdir(parents=True)
    (pasta / "luta.mp4").write_bytes(b"0123456789")
    (pasta / "luta.json").write_text(json.dumps({"tarefa": "luta-1", "p1": "Ana", "p2": "Beto", "mapa": "Arena", "semente": 4}), encoding="utf-8")
    monkeypatch.setattr(api_http, "PASTA_ARENA", pasta.parent)
    monkeypatch.setattr(api_http, "opcoes_da_arena", _opcoes)
    monkeypatch.setattr(tarefas, "rodando", lambda acao: [{"acao": "arena"}])
    monkeypatch.setattr(tarefas, "uma", lambda chave: {"situacao": "terminou", "codigo": 1})
    token = _parear(servidor)
    servidor.RequestHandlerClass.estado.com_acoes = True
    resp, _ = _pedir(servidor, "POST", "/api/arena/luta", {"p1": "Ana", "p2": "Beto", "mapa": "Arena"}, token=token)
    assert resp.status == 409
    resp, dados = _pedir(servidor, "GET", "/api/arena/lutas", token=token)
    luta = json.loads(dados)["lutas"][0]
    assert luta["situacao"] == "pronta" and luta["video_url"]
    url = urllib.parse.urlsplit(luta["video_url"])
    resp, corpo = _pedir(servidor, "GET", url.path + "?" + url.query, cabecalhos={"Range": "bytes=2-5"})
    assert resp.status == 206 and corpo == b"2345"


def test_arena_lista_falhou(servidor, mundo, monkeypatch):
    pasta = mundo.tmp / "arena" / "falhou-1"
    pasta.mkdir(parents=True)
    (pasta / "luta.json").write_text(json.dumps({"tarefa": "falhou-1", "p1": "Ana", "p2": "Beto", "mapa": "Arena", "semente": 4}), encoding="utf-8")
    monkeypatch.setattr(api_http, "PASTA_ARENA", pasta.parent)
    monkeypatch.setattr(tarefas, "uma", lambda chave: {"situacao": "terminou", "codigo": 1})
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "GET", "/api/arena/lutas", token=token)
    assert resp.status == 200 and json.loads(dados)["lutas"][0]["situacao"] == "falhou"
