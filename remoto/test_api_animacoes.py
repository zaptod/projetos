import base64
import http.client
import io
import json
import threading
from pathlib import Path

from PIL import Image

from neural_fights.tools import atelie_animacoes as atelie
from remoto import api_http


def pedir(srv, metodo, caminho, corpo=None, token=None):
    porta = srv.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", porta)
    cab = {"Host": f"127.0.0.1:{porta}"}
    if token: cab["Authorization"] = f"Bearer {token}"
    if corpo is not None: cab["Content-Type"] = "application/json"; corpo = json.dumps(corpo).encode()
    con.request(metodo, caminho, corpo, cab); resp = con.getresponse(); bruto = resp.read(); con.close()
    return resp, bruto


def png():
    imagem = Image.new("RGBA", (8, 8), "white"); saida = io.BytesIO(); imagem.save(saida, "PNG")
    return saida.getvalue()


def test_rotas_animacoes_autenticacao_limite_e_caminho(tmp_path, monkeypatch):
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app.json")
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    monkeypatch.setattr(atelie, "AJUSTES", tmp_path / "ajustes.json")
    monkeypatch.setattr(atelie, "CATALOGO", tmp_path / "catalogo.json")
    (tmp_path / "catalogo.json").write_text('{"pecas": []}', encoding="utf-8")
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    fio = threading.Thread(target=srv.serve_forever, daemon=True); fio.start()
    try:
        assert pedir(srv, "GET", "/api/animacoes/arvore")[0].status == 401
        codigo = api_http.novo_codigo()
        token = json.loads(pedir(srv, "POST", "/api/parear", {"codigo": codigo, "nome": "teste"})[1])["token"]
        assert pedir(srv, "GET", "/api/animacoes/../x/y", token=token)[0].status in (400, 404)
        monkeypatch.setattr(api_http, "ANIMACAO_MAX", 5)
        corpo = {"imagem": "x" * 70000}
        assert pedir(srv, "POST", "/api/animacoes/subir", corpo, token)[0].status == 413
    finally:
        srv.shutdown(); srv.server_close()


def test_montagem_expoe_camadas_e_marcador_sem_arte(tmp_path, monkeypatch):
    monkeypatch.setattr(atelie, "CATALOGO", tmp_path / "catalogo.json")
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    (tmp_path / "catalogo.json").write_text(json.dumps({"pecas": [{"id": "corpo", "grupo": "lutador", "estados": [{"id": "parado", "animacoes": [{"id": "respirar", "gatilho": "ocioso", "camada": 20, "tamanho_padrao": "1,0 do corpo"}]}]}]}), encoding="utf-8")
    dados = atelie.montagem()
    camada = dados["camadas"][0]
    assert dados["largura"] == 320 and camada["marcador"]
    assert camada["posicao"] == {"x": 160, "y": 100} and camada["camada"] == 20
    assert camada["categoria_marcador"] == "lutadores"


def test_previa_godot_roda_uma_vez_e_entrega_video(tmp_path, monkeypatch):
    catalogo = {"pecas": [{"id": "classe.mago", "grupo": "lutador", "estados": [{"id": "parado", "animacoes": [{"id": "respirar", "gatilho": "ocioso"}]}]}]}
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app.json")
    monkeypatch.setattr(api_http, "runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(atelie, "CATALOGO", tmp_path / "catalogo.json")
    monkeypatch.setattr(atelie, "ANIMACOES", tmp_path / "animacoes")
    (tmp_path / "catalogo.json").write_text(json.dumps(catalogo), encoding="utf-8")
    atelie.salvar("classe.mago", "parado", "respirar", png(), {"fps": 12, "ancora": {"x": .5, "y": 1}, "quadros": [{"x": 0, "y": 0, "w": 8, "h": 8}]})
    iniciou, liberar = threading.Event(), threading.Event()
    chamadas = []
    def duble(peca, estado, animacao, pasta):
        chamadas.append((peca, estado, animacao)); iniciou.set(); liberar.wait(2)
        arquivo = Path(pasta) / "previa.mp4"; arquivo.parent.mkdir(parents=True, exist_ok=True); arquivo.write_bytes(b"mp4")
        return arquivo
    monkeypatch.setattr(api_http, "renderizar_previa", duble)
    with api_http._TRAVA_PREVIAS_ANIMACOES:
        api_http._PREVIAS_ANIMACOES.clear(); api_http._FILA_PREVIAS_ANIMACOES.clear(); api_http._PREVIA_ANIMACAO_OCUPADA = False
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    fio = threading.Thread(target=srv.serve_forever, daemon=True); fio.start()
    try:
        token = json.loads(pedir(srv, "POST", "/api/parear", {"codigo": api_http.novo_codigo(), "nome": "teste"})[1])["token"]
        corpo = {"peca": "classe.mago", "estado": "parado", "animacao": "respirar"}
        primeiro = json.loads(pedir(srv, "POST", "/api/animacoes/previa-godot", corpo, token)[1])
        segundo = json.loads(pedir(srv, "POST", "/api/animacoes/previa-godot", corpo, token)[1])
        assert primeiro["id"] == segundo["id"] and iniciou.wait(1)
        assert json.loads(pedir(srv, "GET", "/api/animacoes/previa-godot/" + primeiro["id"], token=token)[1])["situacao"] == "rodando"
        liberar.set()
        for _ in range(30):
            dados = json.loads(pedir(srv, "GET", "/api/animacoes/previa-godot/" + primeiro["id"], token=token)[1])
            if dados["situacao"] == "pronto": break
            threading.Event().wait(.02)
        assert dados["situacao"] == "pronto" and dados["video"].startswith("/v/") and len(chamadas) == 1
    finally:
        liberar.set(); srv.shutdown(); srv.server_close()
