"""config/palco.json e os caminhos do palco. Nenhum caminho escrito no codigo:
o Godot vem de NF_GODOT ou do config; o projeto, do config ou de
<repositorio>/palco."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

RAIZ_RANDOM_BUILDS = Path(__file__).resolve().parents[2]
RAIZ_PROJETOS = Path(__file__).resolve().parents[3]
ARQUIVO = RAIZ_RANDOM_BUILDS / "config" / "palco.json"
OUTPUTS = RAIZ_RANDOM_BUILDS / "outputs"
SAIDAS = OUTPUTS / "_palco"
VARIAVEL_GODOT = "NF_GODOT"
VARIAVEL_APPDATA = "NF_PALCO_APPDATA"
_VERSOES_GODOT: dict[Path, str] = {}


class ErroPalco(RuntimeError):
    """O palco nao entregou um video conferido. Nunca e engolido."""


def carregar() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise ErroPalco(f"config/palco.json ilegivel: {erro}") from erro


def godot(cfg: dict | None = None) -> Path:
    """O executavel do Godot (o `_console.exe`, que devolve o codigo de saida).

    NF_GODOT vence o config. Sem nenhum dos dois, ou apontando para arquivo
    que nao existe, e erro com o motivo — nunca um caminho adivinhado."""
    cfg = carregar() if cfg is None else cfg
    valor = os.environ.get(VARIAVEL_GODOT) or cfg.get("godot")
    if not valor:
        raise ErroPalco(f"Godot nao configurado: defina {VARIAVEL_GODOT} ou `godot` em {ARQUIVO}")
    caminho = Path(valor)
    if not caminho.is_file():
        raise ErroPalco(f"Godot nao encontrado em {caminho} (de "
                        f"{'NF_GODOT' if os.environ.get(VARIAVEL_GODOT) else ARQUIVO.name})")
    return caminho


def godot_disponivel() -> Path | None:
    try:
        return godot()
    except ErroPalco:
        return None


def conferir_versao_godot(cfg: dict | None = None) -> str:
    """Confere o major.minor do executavel com `config/features` do projeto."""
    cfg = carregar() if cfg is None else cfg
    executavel = godot(cfg)
    if executavel not in _VERSOES_GODOT:
        try:
            resultado = subprocess.run([str(executavel), "--version"], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=20,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        except OSError as erro:
            raise ErroPalco(f"nao consegui consultar a versao do Godot em {executavel}: {erro}") from erro
        achado = re.search(r"(\d+\.\d+)", (resultado.stdout or "") + (resultado.stderr or ""))
        if resultado.returncode != 0 or achado is None:
            raise ErroPalco(f"nao consegui ler a versao do Godot em {executavel}")
        _VERSOES_GODOT[executavel] = achado.group(1)
    texto = (projeto(cfg) / "project.godot").read_text(encoding="utf-8")
    esperado = re.search(r'config/features=PackedStringArray\("(\d+\.\d+)"', texto)
    if esperado is None:
        raise ErroPalco("project.godot sem config/features do Godot")
    versao = _VERSOES_GODOT[executavel]
    if versao != esperado.group(1):
        raise ErroPalco(f"Godot {versao} nao corresponde ao projeto {esperado.group(1)}")
    return versao


def projeto(cfg: dict | None = None) -> Path:
    cfg = carregar() if cfg is None else cfg
    pasta = Path(cfg["projeto"]) if cfg.get("projeto") else RAIZ_PROJETOS / "palco"
    if not (pasta / "project.godot").is_file():
        raise ErroPalco(f"projeto do palco nao encontrado em {pasta}")
    return pasta


def appdata(cfg: dict | None = None) -> Path:
    cfg = carregar() if cfg is None else cfg
    pasta = Path(os.environ.get(VARIAVEL_APPDATA) or cfg.get("appdata") or projeto(cfg) / "_userdata")
    pasta.mkdir(parents=True, exist_ok=True)
    # sem isto o Godot tenta importar o que cair aqui dentro
    (pasta / ".gdignore").touch(exist_ok=True)
    return pasta
