from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


AQUI = Path(__file__).resolve().parent


def rodar(*args: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, text=True, capture_output=True)


def git(pasta: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=pasta, check=True, text=True, capture_output=True)


def test_montar_gera_as_duas_paginas_e_escapa_script(tmp_path: Path) -> None:
    dados = tmp_path / "itens.json"
    dados.write_text(json.dumps({"itens": [
        {"id": "um", "ordem": 2, "grupo": "base", "descricao": "normal"},
        {"id": "dois", "ordem": 1, "grupo": "arena", "descricao": "</script><b>x"},
        {"id": "tres", "ordem": 3, "grupo": "hud", "descricao": "fim"},
    ]}), encoding="utf-8")
    saida = tmp_path / "saida"
    r = rodar(AQUI / "inventario/montar.py", "pagina-do-app", "--dados", dados, "--saida", saida)
    assert r.returncode == 0, r.stderr
    claude = (saida / "inventario_sprites.html").read_text(encoding="utf-8")
    app = (saida / "inventario_app.html").read_text(encoding="utf-8")
    assert 'const PAGINA_APP = "__PAGINA_APP__"' in claude
    assert 'const PAGINA_APP = "pagina-do-app"' in app
    assert "/*__DADOS__*/[]" not in claude
    assert "<\\/script><b>x" in claude


def test_copiar_conserva_destino_modificado_e_conferir_nao_escreve(tmp_path: Path) -> None:
    destino, origem = tmp_path / "destino", tmp_path / "origem"
    destino.mkdir()
    (destino / "arquivo.txt").write_text("velho\n", encoding="utf-8")
    git(destino, "init")
    git(destino, "config", "user.email", "teste@example.invalid")
    git(destino, "config", "user.name", "Teste")
    git(destino, "add", "arquivo.txt")
    git(destino, "commit", "-m", "base")
    origem.mkdir()
    (origem / "arquivo.txt").write_text("novo\n", encoding="utf-8")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=destino, text=True, capture_output=True,
                          check=True).stdout.strip()
    script = AQUI / "copiar.py"
    r = rodar(script, base, origem, destino, "arquivo.txt", "--conferir")
    assert r.returncode == 0, r.stderr
    assert (destino / "arquivo.txt").read_text(encoding="utf-8") == "velho\n"
    r = rodar(script, base, origem, destino, "arquivo.txt")
    assert r.returncode == 0, r.stderr
    assert (destino / "arquivo.txt").read_text(encoding="utf-8") == "novo\n"
    (destino / "arquivo.txt").write_text("mudou\n", encoding="utf-8")
    r = rodar(script, base, origem, destino, "arquivo.txt", "--conferir")
    assert r.returncode == 1
    assert "DESTINO MUDOU" in r.stdout
    assert (destino / "arquivo.txt").read_text(encoding="utf-8") == "mudou\n"


def test_scripts_exibem_ajuda() -> None:
    for script in ("copiar.py", "vigia_som.py", "vigia_som_dia.py", "parecer_gemini_video.py", "inventario/montar.py"):
        r = rodar(AQUI / script, "--help")
        assert r.returncode == 0, (script, r.stderr)
        assert "uso:" in r.stdout.lower() or "usage:" in r.stdout.lower()


def test_nao_ha_referencia_a_pasta_temporaria_da_sessao() -> None:
    proibido = "AppData" + "\\Local\\Temp\\claude"
    for arquivo in AQUI.rglob("*"):
        if arquivo.is_file():
            assert proibido.encode() not in arquivo.read_bytes()
