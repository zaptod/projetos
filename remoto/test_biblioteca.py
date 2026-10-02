# -*- coding: utf-8 -*-
"""A Biblioteca: registro, fontes automaticas, rotas e Markdown seguro."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from remoto import biblioteca
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
