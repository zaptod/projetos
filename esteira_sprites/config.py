"""Caminhos e leitura do inventario, concentrados para facilitar testes."""
from __future__ import annotations

import json
import os
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
RAIZ = Path(os.environ.get("ESTEIRA_SPRITES_PASTA",
                            r"E:\projetos\outputs\_ias\esteira_sprites"))
INVENTARIO = RAIZ_PROJETO / "docs" / "palco" / "inventario_sprites.json"
PAGINA = "237c51f24a0147f8bfd605374665fc02"


def itens() -> list[dict]:
    dados = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    return list(dados.get("itens", []))


def item(item_id: str) -> dict:
    achado = next((i for i in itens() if i.get("id") == item_id), None)
    if achado is None:
        raise ValueError(f"item desconhecido: {item_id}")
    return achado


def pasta(item_id: str) -> Path:
    return RAIZ / str(item_id)


def mestra() -> Path:
    return RAIZ / "_mestra" / "aprovada.png"
