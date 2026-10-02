# -*- coding: utf-8 -*-
"""Estado pequeno e tolerante a falhas, consumido pela tela do celular."""
from __future__ import annotations

import json
import os
from pathlib import Path


def pasta() -> Path:
    teste = os.environ.get("NF_COORDENADOR_PASTA")
    if teste:
        return Path(teste)
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "neural-fights" / "coordenador"


def caminho() -> Path:
    return pasta() / "estado.json"


def ler_estado() -> dict:
    """Le o contrato; arquivo ausente ou ruim nunca derruba quem consulta."""
    try:
        dados = json.loads(caminho().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def gravar_estado(dados: dict) -> None:
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name("." + alvo.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
                          encoding="utf-8")
    os.replace(temporario, alvo)


def gravar_comando_servico(comando: str, valor: str, aparelho: str = "") -> dict:
    """Atalho para clientes locais: usa a mesma fila e validacao do app."""
    from remoto.orquestrador import gravar_comando
    return gravar_comando(comando, valor, aparelho)
