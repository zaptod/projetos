# -*- coding: utf-8 -*-
"""API do app do celular: trancas, pareamento, video e leitura.

Nada aqui toca a rede de verdade (o servidor sobe no loopback, porta
escolhida pelo sistema), o diario real ou o `app_celular.json` real: a config
vai para `tmp_path` e as fontes de `painel_dados` sao dubles.
"""
from __future__ import annotations

import http.client
import base64
import io
import json
import socket
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest
from PIL import Image

from remoto import api_http, painel_dados
from esteira_sprites import config as sprites_config


# ------------------------------------------------------------------ dubles
class _AtividadeFalsa:
    FABRICAS = {"picasso": {"rotulo": "PicassoIA", "emoji": "🎨", "faz": "imagens"},
                "estudio": {"rotulo": "Estúdio", "emoji": "🎬", "faz": "render"}}
    EVENTOS = [  # do mais novo para o mais velho, como `recentes`
        {"ts": "2026-09-17T10:03:00", "fabrica": "estudio", "status": "erro",
         "detalhe": "render falhou"},
        {"ts": "2026-09-17T10:02:00", "fabrica": "picasso", "status": "ok",
         "detalhe": "cena 3"},
        {"ts": "2026-09-17T10:01:00", "fabrica": "picasso", "status": "inicio",
         "detalhe": "cena 3"},
    ]

    def estado_das_fabricas(self):
        return {"picasso": {"status": "trabalhando", "detalhe": "cena 3",
                            "canal": "historias", "ha_s": 4.0}}

    def recentes(self, n=60, fabrica=None):
        return list(self.EVENTOS)[:n]

    def registrar(self, *a, **k):          # pragma: no cover - nao pode ser chamado
        raise AssertionError("a API nao escreve no diario")


class _ControleFalso:
    def estado(self):
        return {"situacao": "rodando", "pausas": {}, "resumo": "rodando normalmente"}


class _GradeFalsa:
    def proximo(self):
        return "12:37"

    def horarios(self):
        return ["06:37", "12:37"]


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    atividade = _AtividadeFalsa()
    monkeypatch.setattr(painel_dados, "_atividade", lambda: atividade)
    monkeypatch.setattr(painel_dados, "_controle", lambda: _ControleFalso())
    monkeypatch.setattr(painel_dados, "_grade", lambda: _GradeFalsa())
    monkeypatch.setattr(painel_dados._Previsao, "disponivel", staticmethod(lambda: False))
    monkeypatch.setattr(painel_dados, "_RELATORIOS_CACHE", {})

    saida = tmp_path / "outputs"
    (saida / "generation_00001").mkdir(parents=True)
    dentro = saida / "generation_00001" / "video.mp4"
    # PEQUENO de proposito, com a fatia reduzida junto: um "video" de 10 MB
    # por teste encheu o disco C: em 17/09/2026 (pytest guarda 3 rodadas),
    # e era essa a falha "intermitente" da suite.
    monkeypatch.setattr(api_http, "FATIA_MAX", 64 * 1024)
    dentro.write_bytes(bytes(range(256)) * 1200)             # ~300 KB
    fora = tmp_path / "segredo.mp4"
    fora.write_bytes(b"x" * 1000)

    def video(id_, caminho, quando):
        return types.SimpleNamespace(id=id_, caminho=caminho, titulo=f"t {id_}",
                                     perfil="celular", origem="build",
                                     bytes=Path(caminho).stat().st_size,
                                     quando=quando, pendencias=[])

    catalogo = types.SimpleNamespace(
        OUTPUTS=saida,
        listar=lambda: [video("bom", dentro, 2.0), video("fugido", fora, 1.0),
                        video("h_1:celular:p02", dentro, 3.0)])
    monkeypatch.setattr(painel_dados, "_catalogos", lambda: {"builds": catalogo})
    return types.SimpleNamespace(tmp=tmp_path, dentro=dentro, atividade=atividade)


@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None, host=None, cabecalhos=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    extra = {"Host": host or f"127.0.0.1:{porta}"}
    if token:
        extra["Authorization"] = f"Bearer {token}"
    if corpo is not None:
        corpo = json.dumps(corpo).encode()
        extra["Content-Type"] = "application/json"
    extra.update(cabecalhos or {})
    conexao.request(metodo, caminho, body=corpo, headers=extra)
    resposta = conexao.getresponse()
    dados = resposta.read()
    conexao.close()
    return resposta, dados


def _parear(srv):
    codigo = api_http.novo_codigo()
    resp, dados = _pedir(srv, "POST", "/api/parear", {"codigo": codigo, "nome": "moto"})
    assert resp.status == 200
    return json.loads(dados)["token"]


def _imagem_atelie():
    imagem = Image.new("RGB", (20, 20), "#ff00ff")
    for x in range(5, 15):
        for y in range(4, 17):
            imagem.putpixel((x, y), (30, 80, 200))
    saida = io.BytesIO()
    imagem.save(saida, "PNG")
    return base64.b64encode(saida.getvalue()).decode("ascii")


def test_atelie_exige_pareamento_acoes_e_slot_existente(servidor):
    pedido = {"imagem": _imagem_atelie(), "opcoes": {"sujeito": "lutador",
              "slot": "nao-existe", "nome": "teste"}}
    assert _pedir(servidor, "POST", "/api/atelie/importar", pedido)[0].status == 401
    token = _parear(servidor)
    assert _pedir(servidor, "POST", "/api/atelie/importar", pedido, token)[0].status == 403
    servidor.RequestHandlerClass.estado.com_acoes = True
    assert _pedir(servidor, "POST", "/api/atelie/importar", pedido, token)[0].status == 400
    pedido["opcoes"]["slot"] = "parado_direita"
    resposta, bruto = _pedir(servidor, "POST", "/api/atelie/importar", pedido, token)
    assert resposta.status == 200
    dados = json.loads(bruto)
    assert dados["quadros"] == 1 and dados["limpa"].startswith("/api/atelie/arquivo/")


def test_atelie_limita_corpo_antes_de_ler(servidor):
    token = _parear(servidor)
    servidor.RequestHandlerClass.estado.com_acoes = True
    resposta, _ = _pedir(servidor, "POST", "/api/atelie/importar",
                         {"imagem": "x" * (api_http.ATELIE_MAX + 70000)}, token)
    assert resposta.status == 413


def test_assembleia_exige_pareamento_e_acoes(servidor, monkeypatch):
    """Consultar e convocar seguem as mesmas trancas da bancada."""
    from ias import assembleia
    resp, _ = _pedir(servidor, "GET", "/api/assembleias")
    assert resp.status == 401
    token = _parear(servidor)
    monkeypatch.setattr(assembleia, "listar", lambda: [])
    assert _pedir(servidor, "GET", "/api/assembleias", token=token)[0].status == 200
    resp, _ = _pedir(servidor, "POST", "/api/assembleia", {"pergunta": "x"}, token=token)
    assert resp.status == 403


# ------------------------------------------------------------------ rede
@pytest.mark.parametrize("ip,local,esperado", [
    ("100.95.104.33", False, True),
    ("100.64.0.1", False, True),
    ("0.0.0.0", False, False),
    ("192.168.0.10", False, False),
    ("127.0.0.1", False, False),
    ("127.0.0.1", True, True),
    ("100.95.104.33", True, False),
    ("lixo", False, False),
])
def test_so_tailscale_ou_loopback(ip, local, esperado):
    assert api_http.endereco_permitido(ip, local) is esperado


def test_servidor_recusa_qualquer_endereco_e_a_porta_do_youtube():
    with pytest.raises(ValueError):
        api_http.criar_servidor("0.0.0.0", 8931, local=False)
    with pytest.raises(ValueError):
        api_http.criar_servidor("127.0.0.1", 8931, local=False)
    with pytest.raises(ValueError):
        api_http.criar_servidor("127.0.0.1", 8765, local=True)


def test_ip_do_tailscale_ignora_ip_fora_da_rede(monkeypatch):
    monkeypatch.setattr(api_http, "_tailscale_exe", lambda: "tailscale")
    saida = types.SimpleNamespace(stdout="192.168.0.5\n100.95.104.33\n")
    assert api_http.ip_do_tailscale(lambda *a, **k: saida) == "100.95.104.33"
    so_lan = types.SimpleNamespace(stdout="192.168.0.5\n")
    assert api_http.ip_do_tailscale(lambda *a, **k: so_lan) is None
    monkeypatch.setattr(api_http, "_tailscale_exe", lambda: None)
    assert api_http.ip_do_tailscale(lambda *a, **k: saida) is None


def test_host_estranho_e_recusado(servidor):
    resp, _ = _pedir(servidor, "GET", "/api/estado", host="atacante.example:8931")
    assert resp.status == 421


# ------------------------------------------------------------ pareamento
def test_codigo_vale_uma_vez_e_o_disco_nao_guarda_o_token(mundo):
    codigo = api_http.novo_codigo()
    token = api_http.trocar_codigo(codigo, "moto")
    assert token
    assert api_http.trocar_codigo(codigo, "moto") is None
    bruto = (mundo.tmp / "app_celular.json").read_text(encoding="utf-8")
    assert token not in bruto and codigo not in bruto
    assert api_http.aparelho_do_token(token) == "moto"
    assert api_http.aparelho_do_token("outro") is None
    assert api_http.aparelho_do_token("") is None


def test_codigo_vence_e_cinco_erros_o_matam(mundo):
    codigo = api_http.novo_codigo(agora=1000.0)
    assert api_http.trocar_codigo(codigo, "x", agora=1000.0 + 301) is None

    codigo = api_http.novo_codigo()
    errado = f"{(int(codigo) + 1) % 10**6:06d}"
    for _ in range(api_http.CODIGO_TENTATIVAS):
        assert api_http.trocar_codigo(errado, "x") is None
    assert api_http.trocar_codigo(codigo, "x") is None


def test_sem_token_nao_le_nada(servidor):
    for rota in ("/api/estado", "/api/diario", "/api/videos",
                 "/api/video/builds/bom", "/api/relatorio/metas"):
        resp, _ = _pedir(servidor, "GET", rota)
        assert resp.status == 401, rota
    resp, _ = _pedir(servidor, "GET", "/api/estado", token="chute")
    assert resp.status == 401


def test_chutes_demais_bloqueiam_o_ip(servidor, monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 3)
    for _ in range(3):
        _pedir(servidor, "GET", "/api/estado", token="chute")
    resp, _ = _pedir(servidor, "GET", "/api/estado", token="chute")
    assert resp.status == 429
    resp, _ = _pedir(servidor, "POST", "/api/parear", {"codigo": "000000"})
    assert resp.status == 429
    resp, _ = _pedir(servidor, "GET", "/v/bilhete-inventado")
    assert resp.status == 429


def test_chute_alheio_nao_trava_o_celular_pareado(servidor, monkeypatch):
    # Atras do `tailscale serve` todos chegam de 127.0.0.1: o celular com
    # token valido continua lendo mesmo com o IP "bloqueado".
    monkeypatch.setattr(api_http, "FALHAS_MAX", 3)
    token = _parear(servidor)
    for _ in range(5):
        _pedir(servidor, "GET", "/api/estado", token="chute",
               cabecalhos={"X-Forwarded-For": "100.1.2.3"})
    resp, _ = _pedir(servidor, "GET", "/api/estado", token=token)
    assert resp.status == 200


def test_host_do_tailscale_serve_e_aceito(servidor):
    token = _parear(servidor)
    resp, _ = _pedir(servidor, "GET", "/api/estado", token=token,
                     host="desktop-tgti3ek.tail1234.ts.net")
    assert resp.status == 200


def test_pareamento_pela_rota_e_corpo_invalido(servidor):
    resp, _ = _pedir(servidor, "POST", "/api/parear", {"codigo": "000000"})
    assert resp.status == 403
    resp, _ = _pedir(servidor, "POST", "/api/parear", ["lista"])
    assert resp.status == 400
    resp, _ = _pedir(servidor, "POST", "/api/qualquer", {"x": 1})
    assert resp.status == 404
    resp, _ = _pedir(servidor, "POST", "/api/parear", {"codigo": "1" * 5000})
    assert resp.status == 413


# ---------------------------------------------------------------- leitura
def test_estado_e_diario(servidor):
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "GET", "/api/estado", token=token)
    assert resp.status == 200
    estado = json.loads(dados)
    assert estado["proxima"]["horario"] == "12:37"
    assert estado["pausa"]["situacao"] == "rodando"
    picasso = next(f for f in estado["fabricas"] if f["nome"] == "picasso")
    assert picasso["status"] == "trabalhando"
    assert estado["previsao"] is None

    resp, dados = _pedir(servidor, "GET",
                         "/api/diario?desde=2026-09-17T10:01:00", token=token)
    eventos = json.loads(dados)
    assert [e["ts"][-5:] for e in eventos] == ["02:00", "03:00"]   # velho -> novo

    resp, dados = _pedir(servidor, "GET", "/api/erros", token=token)
    assert [e["detalhe"] for e in json.loads(dados)] == ["render falhou"]


def test_relatorio_so_da_lista(servidor, monkeypatch):
    token = _parear(servidor)
    from remoto import relatorios
    monkeypatch.setattr(relatorios, "montar", lambda nome: f"texto {nome}")
    resp, dados = _pedir(servidor, "GET", "/api/relatorio/metas", token=token)
    assert json.loads(dados) == {"texto": "texto metas"}
    resp, _ = _pedir(servidor, "GET", "/api/relatorio/montar", token=token)
    assert resp.status == 404


def test_estatico_so_os_arquivos_da_tabela(servidor):
    resp, dados = _pedir(servidor, "GET", "/")
    assert resp.status == 200 and b"<html" in dados
    csp = resp.getheader("Content-Security-Policy")
    assert "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp
    # as imagens com token (Sprites, 02/10/2026) viram blob: — sem isso a CSP
    # as bloqueava e o celular mostrava imagem quebrada
    assert "img-src 'self' blob:" in csp
    assert b"<script>" not in dados and b"<style>" not in dados
    for rota in ("/app.js", "/app.css", "/sw.js", "/manifest.webmanifest"):
        resp, _ = _pedir(servidor, "GET", rota)
        assert resp.status == 200, rota
    # o ícone (29/09) é binário e sai inteiro, com o tipo certo
    for rota, tipo in (("/icones/icone-512.png", "image/png"),
                       ("/apple-touch-icon.png", "image/png"),
                       ("/favicon.ico", "image/x-icon")):
        resp, dados = _pedir(servidor, "GET", rota)
        assert resp.status == 200 and resp.getheader("Content-Type") == tipo, rota
        assert len(dados) == int(resp.getheader("Content-Length")) > 100, rota
    resp, _ = _pedir(servidor, "GET", "/icone.svg")
    assert resp.status == 404
    for rota in ("/../api_http.py", "/app/index.html", "/api_http.py",
                 "/%2e%2e/config.py"):
        resp, _ = _pedir(servidor, "GET", rota)
        assert resp.status == 404, rota


# ------------------------------------------------------------------ video
def test_video_fora_da_pasta_de_saida_nao_sai(servidor):
    token = _parear(servidor)
    resp, _ = _pedir(servidor, "GET", "/api/video/builds/fugido", token=token)
    assert resp.status == 404
    resp, _ = _pedir(servidor, "GET", "/api/video/builds/inexistente", token=token)
    assert resp.status == 404
    resp, _ = _pedir(servidor, "GET", "/api/video/outro/bom", token=token)
    assert resp.status == 404


def test_video_por_bilhete_em_fatias(servidor, mundo):
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "GET", "/api/video/builds/bom", token=token)
    url = json.loads(dados)["url"]
    assert url.startswith("/v/")

    total = mundo.dentro.stat().st_size
    resp, corpo = _pedir(servidor, "GET", url)            # sem Range
    assert resp.status == 206
    assert len(corpo) == api_http.FATIA_MAX
    assert resp.getheader("Content-Range") == \
        f"bytes 0-{api_http.FATIA_MAX - 1}/{total}"

    resp, corpo = _pedir(servidor, "GET", url, cabecalhos={"Range": "bytes=10-19"})
    assert resp.status == 206
    assert corpo == mundo.dentro.read_bytes()[10:20]

    resp, _ = _pedir(servidor, "GET", url, cabecalhos={"Range": f"bytes={total}-"})
    assert resp.status == 416

    resp, _ = _pedir(servidor, "GET", "/v/bilhete-inventado")
    assert resp.status == 404


def test_id_com_dois_pontos_codificado(servidor):
    token = _parear(servidor)
    resp, dados = _pedir(servidor, "GET", "/api/video/builds/h_1%3Acelular%3Ap02",
                         token=token)
    assert resp.status == 200 and json.loads(dados)["url"].startswith("/v/")


def test_bilhete_vence(servidor, mundo, monkeypatch):
    token = _parear(servidor)
    _, dados = _pedir(servidor, "GET", "/api/video/builds/bom", token=token)
    url = json.loads(dados)["url"]
    agora = api_http.time.time()
    monkeypatch.setattr(api_http.time, "time",
                        lambda: agora + api_http.BILHETE_VALE_S + 1)
    resp, _ = _pedir(servidor, "GET", url)
    assert resp.status == 410


def test_bilhete_vencido_do_proprio_celular_nao_e_chute(servidor, monkeypatch):
    monkeypatch.setattr(api_http, "FALHAS_MAX", 2)
    token = _parear(servidor)
    _, dados = _pedir(servidor, "GET", "/api/video/builds/bom", token=token)
    url = json.loads(dados)["url"]
    agora = api_http.time.time()
    monkeypatch.setattr(api_http.time, "time",
                        lambda: agora + api_http.BILHETE_VALE_S + 1)
    for _ in range(5):
        resp, _ = _pedir(servidor, "GET", url)
        assert resp.status == 410
    resp, _ = _pedir(servidor, "POST", "/api/parear", {"codigo": "000000"})
    assert resp.status == 403                       # ainda nao bloqueado


def test_esquecer_revoga_os_bilhetes_do_aparelho(servidor, capsys):
    token = _parear(servidor)
    _, dados = _pedir(servidor, "GET", "/api/video/builds/bom", token=token)
    url = json.loads(dados)["url"]
    resp, _ = _pedir(servidor, "GET", url, cabecalhos={"Range": "bytes=0-9"})
    assert resp.status == 206
    (aparelho,) = api_http.aparelhos()
    assert api_http.main(["--esquecer", aparelho["id"]]) == 0
    resp, _ = _pedir(servidor, "GET", url, cabecalhos={"Range": "bytes=0-9"})
    assert resp.status == 403
    resp, _ = _pedir(servidor, "GET", "/api/estado", token=token)
    assert resp.status == 401


def test_range_com_numero_gigante_e_416(servidor):
    token = _parear(servidor)
    _, dados = _pedir(servidor, "GET", "/api/video/builds/bom", token=token)
    url = json.loads(dados)["url"]
    resp, _ = _pedir(servidor, "GET", url,
                     cabecalhos={"Range": "bytes=" + "9" * 5000 + "-"})
    assert resp.status == 416


# ---------------------------------------------------------- robustez
def _cru(srv, dados: bytes, esperar: float = 5.0) -> bytes:
    with socket.create_connection(srv.server_address, timeout=esperar) as s:
        s.sendall(dados)
        pedacos = []
        try:
            while True:
                pedaco = s.recv(65536)
                if not pedaco:
                    break
                pedacos.append(pedaco)
        except (socket.timeout, ConnectionError):
            pass
    return b"".join(pedacos)


def test_requisicao_malformada_nao_vaza_bilhete_no_log(servidor, capsys):
    resposta = _cru(servidor, b"GET /v/SEGREDO123 HTTP/1.1 lixo\r\n\r\n")
    assert b" 400 " in resposta.split(b"\r\n")[0]
    _cru(servidor, b"\x16\x03\x01lixo-binario\r\n\r\n")
    time.sleep(0.2)
    erro = capsys.readouterr().err
    assert "SEGREDO123" not in erro
    assert "Traceback" not in erro


def test_post_que_promete_corpo_e_nao_manda_nao_prende_a_thread(servidor, monkeypatch):
    monkeypatch.setattr(api_http.Manipulador, "timeout", 0.5)
    inicio = time.monotonic()
    _cru(servidor, b"POST /api/parear HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                   b"Content-Length: 100\r\n\r\n", esperar=5.0)
    assert time.monotonic() - inicio < 4.0


def test_teto_de_conexoes(mundo, monkeypatch):
    monkeypatch.setattr(api_http, "CONEXOES_MAX", 2)
    monkeypatch.setattr(api_http.Manipulador, "timeout", 3)
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        paradas = [socket.create_connection(srv.server_address) for _ in range(2)]
        time.sleep(0.3)
        with socket.create_connection(srv.server_address, timeout=2) as terceira:
            terceira.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            try:
                assert terceira.recv(100) == b""       # fechada sem resposta
            except ConnectionError:
                pass
        for conexao in paradas:
            conexao.close()
        time.sleep(0.3)
        resp, _ = _pedir(srv, "GET", "/")
        assert resp.status == 200                      # as vagas voltaram
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.parametrize("cabecalho,total,esperado", [
    ("", 100, (0, 99)),
    ("bytes=0-", 100, (0, 99)),
    ("bytes=5-9", 100, (5, 9)),
    ("bytes=-10", 100, (90, 99)),
    ("bytes=90-500", 100, (90, 99)),
    ("bytes=100-", 100, (None, None)),
    ("bytes=9-5", 100, (None, None)),
    ("bytes=-", 100, (None, None)),
    ("itens=0-1", 100, (None, None)),
    ("bytes=0-1,5-6", 100, (None, None)),
    ("", 0, (None, None)),
    ("bytes=" + "9" * 5000 + "-", 100, (None, None)),
    ("bytes=0-" + "9" * 5000, 100, (None, None)),
])
def test_intervalo(cabecalho, total, esperado):
    assert api_http.intervalo(cabecalho, total) == esperado


def test_intervalo_nunca_passa_da_fatia():
    assert api_http.intervalo("bytes=0-", 10**9) == (0, api_http.FATIA_MAX - 1)


# ------------------------------------------------------- aparelhos e trava
def test_esquecer_pelo_id_e_nao_pelo_nome(mundo):
    primeiro = api_http.trocar_codigo(api_http.novo_codigo(), "moto")
    segundo = api_http.trocar_codigo(api_http.novo_codigo(), "moto")
    lista = api_http.aparelhos()
    assert [a["nome"] for a in lista] == ["moto", "moto"]
    assert all(len(a["id"]) == 8 for a in lista)
    assert api_http.esquecer("moto") == 0
    assert api_http.esquecer(lista[0]["id"][:4]) == 0          # curto demais
    assert api_http.esquecer(lista[0]["id"].upper()) == 1
    assert api_http.aparelho_do_token(primeiro) is None
    assert api_http.aparelho_do_token(segundo) == "moto"
    assert api_http.main(["--esquecer", "00000000"]) == 1


def test_trava_do_json_vale_entre_processos(mundo):
    alvo = api_http.caminho()
    segurar = (
        "import sys, time\n"
        "from remoto import api_http\n"
        f"api_http.ARQUIVO = {str(alvo)!r}\n"
        "with api_http._trava_config():\n"
        "    print('peguei', flush=True)\n"
        "    time.sleep(1.5)\n"
    )
    outro = subprocess.Popen([sys.executable, "-c", segurar],
                             stdout=subprocess.PIPE, text=True,
                             cwd=str(Path(api_http.__file__).parents[1]))
    try:
        assert outro.stdout.readline().strip() == "peguei"
        inicio = time.monotonic()
        api_http.novo_codigo()
        assert time.monotonic() - inicio > 1.0      # esperou o outro soltar
    finally:
        outro.wait(timeout=20)


# ------------------------------------------------------------- filtro
@pytest.mark.parametrize("entrada,esperado", [
    ("falhou em https://x.com/a?token=abc agora", "falhou em [link] agora"),
    ("C:\\Users\\adrian\\AppData\\x.txt", "C:\\Users\\…\\AppData\\x.txt"),
    ("C:/Users/Adrian Silva/x", "C:/Users/…/x"),
    ("chave ya29.A0ARrdaM_abcdefghijklmnopqrstuvwxyz0123456789 fim",
     "chave ya29.[…] fim"),
    ("historia_00017:celular:p06 parte 3", "historia_00017:celular:p06 parte 3"),
    ("E:\\projetos\\historias\\outputs", "E:\\projetos\\historias\\outputs"),
    (None, ""),
])
def test_limpar(entrada, esperado):
    assert painel_dados.limpar(entrada) == esperado


def test_diario_e_relatorio_saem_limpos(servidor, mundo, monkeypatch):
    token = _parear(servidor)
    mundo.atividade.EVENTOS = [{"ts": "2026-09-17T11:00:00", "fabrica": "estudio",
                                "status": "erro",
                                "detalhe": "C:\\Users\\adrian\\x https://a.b/c"}]
    _, dados = _pedir(servidor, "GET", "/api/diario", token=token)
    assert "adrian" not in dados.decode() and "a.b" not in dados.decode()

    from remoto import relatorios
    chamadas = []
    monkeypatch.setattr(relatorios, "montar",
                        lambda nome: chamadas.append(nome) or "ver https://x.y/z")
    for _ in range(3):
        _, dados = _pedir(servidor, "GET", "/api/relatorio/funcionamento",
                          token=token)
        assert json.loads(dados) == {"texto": "ver [link]"}
    assert chamadas == ["funcionamento"]             # guardado, sem refazer


# ----------------------------------------------------------- sprites
@pytest.fixture
def sprites_temporarios(tmp_path, monkeypatch):
    """Fichas pequenas, nunca as da esteira que esta rodando no PC."""
    raiz = tmp_path / "esteira_sprites"
    monkeypatch.setattr(sprites_config, "RAIZ", raiz)
    antigo = sprites_config.PERFIL

    def criar(perfil, item_id, estado="a_conferir"):
        pasta = raiz / ("vila" if perfil == "vila" else "") / item_id
        pasta.mkdir(parents=True)
        limpo = pasta / "limpo.png"
        limpo.write_bytes(b"png de teste")
        (pasta / "previa.gif").write_bytes(b"gif de teste")
        ficha = {"item_id": item_id, "perfil": perfil, "estado": estado,
                 "item": {"id": item_id, "descricao": f"sprite {item_id}"},
                 "tentativas": [{"caminhos": {"limpo": str(limpo),
                                                "previa_gif": str(pasta / "previa.gif")},
                                 "veredito": {"defeitos": [{"gravidade": "grave",
                                                               "o_que": "corte",
                                                               "onde": "direita",
                                                               "como_corrigir": "refazer"}]},
                                 "portao_reprovou": ["borda"]}]}
        (pasta / "ficha.json").write_text(json.dumps(ficha), encoding="utf-8")
        return pasta

    yield criar
    sprites_config.usar(antigo)


def test_sprites_lista_arquivos_e_vazio(servidor, sprites_temporarios, monkeypatch):
    pasta_fogo = sprites_temporarios("palco", "fogo")
    (pasta_fogo / "tamanho_real.png").write_bytes(b"tamanho de teste")
    sprites_temporarios("vila", "folha")
    sprites_temporarios("palco", "fora", "pedido")
    token = _parear(servidor)
    resp, corpo = _pedir(servidor, "GET", "/api/sprites/conferir", token=token)
    assert resp.status == 200
    itens = json.loads(corpo)["itens"]
    assert [(i["perfil"], i["id"]) for i in itens] == [("palco", "fogo"), ("vila", "folha")]
    assert itens[0]["veredito"]["defeitos"][0]["onde"] == "direita"
    assert itens[0]["portao_reprovou"] == ["borda"]
    assert itens[0]["imagens"]["limpo.png"].endswith("/palco/fogo/limpo.png")
    assert itens[0]["tamanho_real_url"].endswith("/palco/fogo/tamanho_real.png")
    resp, corpo = _pedir(servidor, "GET", "/api/sprites/arquivo/palco/fogo/limpo.png", token=token)
    assert resp.status == 200 and corpo == b"png de teste"
    assert _pedir(servidor, "GET", "/api/sprites/arquivo/palco/fogo/segredo.png", token=token)[0].status == 404
    assert _pedir(servidor, "GET", "/api/sprites/arquivo/palco/fogo/../limpo.png", token=token)[0].status == 404
    for ficha in (sprites_config.RAIZ / "fogo" / "ficha.json", sprites_config.RAIZ / "vila" / "folha" / "ficha.json"):
        dados = json.loads(ficha.read_text(encoding="utf-8")); dados["estado"] = "pedido"
        ficha.write_text(json.dumps(dados), encoding="utf-8")
    assert json.loads(_pedir(servidor, "GET", "/api/sprites/conferir", token=token)[1])["itens"] == []


def test_sprites_acoes_exigem_acoes_e_refazer_reabre_contagem(servidor, sprites_temporarios, monkeypatch):
    sprites_temporarios("palco", "fogo")
    token = _parear(servidor)
    rota = "/api/sprites/palco/fogo/refazer"
    assert _pedir(servidor, "POST", rota, {"motivo": "mais brilho"}, token)[0].status == 403
    servidor.RequestHandlerClass.estado.com_acoes = True
    resp, _ = _pedir(servidor, "POST", rota, {"motivo": "mais brilho"}, token)
    assert resp.status == 200
    dados = json.loads((sprites_config.RAIZ / "fogo" / "ficha.json").read_text(encoding="utf-8"))
    assert dados["estado"] == "refazer" and dados["contar_desde"] == 1
    assert dados["tentativas"][-1]["motivo"] == "mais brilho"
    dados["estado"] = "a_conferir"
    (sprites_config.RAIZ / "fogo" / "ficha.json").write_text(json.dumps(dados), encoding="utf-8")
    assert _pedir(servidor, "POST", "/api/sprites/palco/fogo/descartar", {}, token)[0].status == 200
    assert json.loads((sprites_config.RAIZ / "fogo" / "ficha.json").read_text(encoding="utf-8"))["estado"] == "descartado"


def test_sprite_aprovar_chama_a_funcao_da_esteira(servidor, sprites_temporarios, monkeypatch):
    sprites_temporarios("vila", "folha")
    servidor.RequestHandlerClass.estado.com_acoes = True
    chamado = []
    monkeypatch.setattr(api_http.sprites_aprovar, "aprovar",
                        lambda item_id: chamado.append(item_id) or {"estado": "na_biblioteca"})
    token = _parear(servidor)
    resp, corpo = _pedir(servidor, "POST", "/api/sprites/vila/folha/aprovar", {}, token)
    assert resp.status == 200 and chamado == ["folha"]
    assert json.loads(corpo)["estado"] == "na_biblioteca"
