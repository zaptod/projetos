"""config/palco.json e os caminhos do palco. Nenhum caminho escrito no codigo:
o Godot vem de NF_GODOT ou do config; o projeto, do config ou de
<repositorio>/palco."""
from __future__ import annotations

import json
import os
from pathlib import Path

RAIZ_RANDOM_BUILDS = Path(__file__).resolve().parents[2]
RAIZ_PROJETOS = Path(__file__).resolve().parents[3]
ARQUIVO = RAIZ_RANDOM_BUILDS / "config" / "palco.json"
OUTPUTS = RAIZ_RANDOM_BUILDS / "outputs"
SAIDAS = OUTPUTS / "_palco"
VARIAVEL_GODOT = "NF_GODOT"


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


def projeto(cfg: dict | None = None) -> Path:
    cfg = carregar() if cfg is None else cfg
    pasta = Path(cfg["projeto"]) if cfg.get("projeto") else RAIZ_PROJETOS / "palco"
    if not (pasta / "project.godot").is_file():
        raise ErroPalco(f"projeto do palco nao encontrado em {pasta}")
    return pasta


def appdata(cfg: dict | None = None) -> Path:
    cfg = carregar() if cfg is None else cfg
    pasta = Path(cfg.get("appdata") or projeto(cfg) / "_userdata")
    pasta.mkdir(parents=True, exist_ok=True)
    # sem isto o Godot tenta importar o que cair aqui dentro
    (pasta / ".gdignore").touch(exist_ok=True)
    return pasta
