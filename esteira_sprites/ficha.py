"""A ficha persistente: uma fonte de verdade por item da esteira."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config

ESTADOS = ("pedido", "gerado", "limpo", "medido", "julgado", "a_conferir",
           "aprovado", "refazer", "descartado", "na_biblioteca")


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def caminho(item_id: str) -> Path:
    return config.pasta(item_id) / "ficha.json"


def ler(item_id: str) -> dict | None:
    try:
        dados = json.loads(caminho(item_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def nova(item: dict) -> dict:
    return {"item_id": item["id"], "item": item, "estado": "pedido",
            "tentativas": [], "criado_em": agora(), "atualizado_em": agora()}


def gravar(dados: dict) -> dict:
    item_id = dados["item_id"]
    alvo = caminho(item_id)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    dados["atualizado_em"] = agora()
    tmp = alvo.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(alvo)
    return dados


def registrar(dados: dict, tipo: str, **campos) -> dict:
    evento = {"tipo": tipo, "em": agora(), **campos}
    dados.setdefault("historico", []).append(evento)
    return dados


def mudar(dados: dict, estado: str, motivo: str = "") -> dict:
    if estado not in ESTADOS:
        raise ValueError(f"estado invalido: {estado}")
    anterior = dados.get("estado")
    dados["estado"] = estado
    registrar(dados, "estado", de=anterior, para=estado, motivo=motivo)
    return gravar(dados)
