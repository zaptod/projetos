# -*- coding: utf-8 -*-
"""A Biblioteca: registro, fontes automaticas, rotas e Markdown seguro."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from remoto import api_http, biblioteca
from remoto.test_api_http import _parear, _pedir, mundo, servidor  # noqa: F401


@pytest.fixture
def acervo(tmp_path, monkeypatch):
    planos, palco, sessoes, docs = [tmp_path / nome for nome in
                                    ("planos", "palco", "sessoes", "docs")]
    for pasta in (planos, palco, sessoes, docs):
        pasta.mkdir()
    monkeypatch.setattr(biblioteca, "ARQUIVO", tmp_path / "biblioteca" / "itens.json")
    monkeypatch.setattr(biblioteca, "PLANOS", planos)
    monkeypatch.setattr(biblioteca, "PALCO", palco)
    monkeypatch.setattr(biblioteca, "SESSOES", sessoes)
    monkeypatch.setattr(biblioteca, "DOCS_REPOSITORIO", docs)
    return type("Acervo", (), {"planos": planos, "palco": palco,
                                 "sessoes": sessoes, "docs": docs})()


def test_adicionar_listar_e_remover(acervo):
    documento = acervo.planos / "ideia.md"
    documento.write_text("# Ideia\n", encoding="utf-8")
    pagina = biblioteca.adicionar("Sprites", "pagina", url="https://claude.ai/publicacao",
                                 descricao="inventario", tags=["arte"])
    local = biblioteca.adicionar("Ideia", "documento", caminho=documento)
    assert {item["id"] for item in biblioteca.listar()} >= {pagina["id"], local["id"]}
    assert biblioteca.remover(pagina["id"]) is True
    assert biblioteca.remover(pagina["id"]) is False
    assert json.loads(biblioteca.arquivo().read_text(encoding="utf-8"))[0]["id"] == local["id"]


def test_fontes_automaticas_encontram_planos(acervo):
    (acervo.planos / "vila.md").write_text("# Plano da Vila\ntexto", encoding="utf-8")
    itens = biblioteca.listar()
    assert any(item["titulo"] == "Plano da Vila" and item["tipo"] == "documento"
               and item["tags"] == ["plano"] for item in itens)


def test_recusa_url_sem_https_e_caminho_fora_da_raiz(acervo):
    fora = acervo.planos.parent / "segredo.md"
    fora.write_text("segredo", encoding="utf-8")
    with pytest.raises(ValueError):
        biblioteca.adicionar("ruim", "pagina", url="http://claude.ai/x")
    with pytest.raises(ValueError):
        biblioteca.adicionar("fora", "documento", caminho=fora)
    with pytest.raises(ValueError):
        biblioteca.adicionar("subida", "documento", caminho=acervo.planos / ".." / "segredo.md")


def test_ler_documento_tem_raiz_e_limite(acervo):
    dentro = acervo.docs / "nota.md"
    dentro.write_text("# Nota\ncorpo", encoding="utf-8")
    item = biblioteca.adicionar("Nota", "documento", caminho=dentro)
    assert biblioteca.ler_documento(item["id"]) == "# Nota\ncorpo"
    grande = acervo.docs / "grande.md"
    grande.write_bytes(b"x" * (biblioteca.LIMITE_DOCUMENTO + 1))
    item_grande = biblioteca.adicionar("Grande", "documento", caminho=grande)
    assert biblioteca.ler_documento(item_grande["id"]) is None
    assert biblioteca.ler_documento("inexistente") is None


def test_rotas_sao_so_leitura_e_pedem_aparelho(servidor, acervo):  # noqa: F811
    plano = acervo.planos / "rota.md"
    plano.write_text("# Rota\ntexto", encoding="utf-8")
    item = biblioteca.adicionar("Rota", "documento", caminho=plano)
    assert _pedir(servidor, "GET", "/api/biblioteca")[0].status == 401
    assert _pedir(servidor, "GET", f"/api/biblioteca/doc/{item['id']}")[0].status == 401
    token = _parear(servidor)
    resposta, bruto = _pedir(servidor, "GET", "/api/biblioteca", token=token)
    assert resposta.status == 200 and item["id"] in {x["id"] for x in json.loads(bruto)["itens"]}
    resposta, bruto = _pedir(servidor, "GET", f"/api/biblioteca/doc/{item['id']}", token=token)
    assert resposta.status == 200 and json.loads(bruto)["texto"] == "# Rota\ntexto"
    assert _pedir(servidor, "POST", "/api/biblioteca", {"x": 1}, token=token)[0].status == 404


def test_pagina_local_vai_por_bilhete_e_ganha_esqueleto(servidor, acervo):  # noqa: F811
    html = acervo.docs / "inventario.html"
    html.write_text("<title>Inventario</title><style>.x{color:red}</style><main>oi</main>",
                    encoding="utf-8")
    pagina = biblioteca.adicionar("Inventario", "pagina", url="https://claude.ai/inventario")
    assert biblioteca.main(["guardar", "--id", pagina["id"], "--html", str(html)]) == 0
    assert (biblioteca.pasta_paginas() / f'{pagina["id"]}.html').is_file()
    token = _parear(servidor)
    assert _pedir(servidor, "POST", f'/api/biblioteca/bilhete/{pagina["id"]}')[0].status == 401
    resposta, bruto = _pedir(servidor, "POST", f'/api/biblioteca/bilhete/{pagina["id"]}',
                              token=token)
    assert resposta.status == 200
    url = json.loads(bruto)["url"]
    assert url.startswith("/p/")
    resposta, bruto = _pedir(servidor, "GET", url)
    texto = bruto.decode("utf-8")
    assert resposta.status == 200
    assert texto.startswith("<!doctype html>") and "viewport-fit=cover" in texto
    assert "body{margin:0}" in texto and "<main>oi</main>" in texto
    csp = resposta.getheader("Content-Security-Policy")
    assert "cdnjs.cloudflare.com" in csp and "connect-src 'self'" in csp
    assert resposta.getheader("X-Content-Type-Options") == "nosniff"
    assert _pedir(servidor, "GET", "/p/")[0].status == 404
    assert _pedir(servidor, "GET", "/p/bilhete-inventado")[0].status == 404


def test_pagina_com_html_completo_nao_e_envolvida_e_bilhete_vence(servidor, acervo,
                                                                   monkeypatch):  # noqa: F811
    html = acervo.docs / "completa.html"
    html.write_text("<!doctype html><html><head><title>Completa</title></head><body>x</body></html>",
                    encoding="utf-8")
    pagina = biblioteca.adicionar("Completa", "pagina", html=html)
    token = _parear(servidor)
    _, bruto = _pedir(servidor, "POST", f'/api/biblioteca/bilhete/{pagina["id"]}', token=token)
    url = json.loads(bruto)["url"]
    resposta, bruto = _pedir(servidor, "GET", url)
    assert resposta.status == 200 and bruto.decode("utf-8") == html.read_text(encoding="utf-8")
    agora = api_http.time.time()
    monkeypatch.setattr(api_http.time, "time",
                        lambda: agora + api_http.BILHETE_VALE_S + 1)
    assert _pedir(servidor, "GET", url)[0].status == 404


def test_estado_da_pagina_pede_token_valida_e_cli_grava(servidor, acervo, capsys):  # noqa: F811
    pagina = biblioteca.adicionar("Inventario", "pagina", url="https://claude.ai/inventario")
    rota = f'/api/biblioteca/estado/{pagina["id"]}'
    assert _pedir(servidor, "GET", rota)[0].status == 401
    token = _parear(servidor)
    resposta, bruto = _pedir(servidor, "GET", rota, token=token)
    assert resposta.status == 200 and json.loads(bruto) == {}
    resposta, bruto = _pedir(servidor, "POST", rota,
                              {"doc_id": "sprite_01", "estado": "pronto"}, token=token)
    assert resposta.status == 200
    assert json.loads(bruto)["sprite_01"]["estado"] == "pronto"
    assert _pedir(servidor, "POST", rota,
                  {"doc_id": "sprite_01", "estado": "errado"}, token=token)[0].status == 400
    assert _pedir(servidor, "POST", rota,
                  {"doc_id": "../torto", "estado": "pronto"}, token=token)[0].status == 400
    assert biblioteca.main(["marcar", "--pagina", pagina["id"], "--doc", "sprite_02",
                            "--estado", "esteira"]) == 0
    assert biblioteca.ver_estado(pagina["id"])["sprite_02"]["estado"] == "esteira"
    assert biblioteca.main(["ver-estado", "--pagina", pagina["id"]]) == 0
    assert "sprite_02" in capsys.readouterr().out


def test_markdown_escapa_script(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("sem Node nesta maquina")
    app = Path(__file__).resolve().parent / "app" / "biblioteca.js"
    harness = tmp_path / "harness.js"
    harness.write_text("""
const fs = require("fs");
global.$ = () => ({addEventListener() {}});
eval(fs.readFileSync(process.argv[2], "utf8") + "\\nglobal.render = bibliotecaMarkdown;");
console.log(global.render("# Titulo\\n<script>alert(1)</script>"));
""", encoding="utf-8")
    saida = subprocess.run([node, str(harness), str(app)], capture_output=True,
                           text=True, timeout=30)
    assert saida.returncode == 0, saida.stderr
    assert "&lt;script&gt;" in saida.stdout and "<script>" not in saida.stdout
