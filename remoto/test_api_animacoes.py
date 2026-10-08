import base64
import http.client
import io
import json
import threading

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
