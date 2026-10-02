"""Caminhos, perfis e leitura do inventario, concentrados para facilitar testes.

PERFIS (02/10/2026): a esteira nasceu para o palco e agora serve tambem a
Vila. O perfil escolhe o inventario padrao, a biblia de estilo do prompt
(`prompt.py`), a subpasta das fichas e o destino da arte aprovada. A
imagem-mestra e UMA so: a Vila usa a mesma do Neural (decisao
`painel-e-vila/vila-estilo-novo` = "mesmo estilo do Neural").
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
RAIZ = Path(os.environ.get("ESTEIRA_SPRITES_PASTA",
                            r"E:\projetos\outputs\_ias\esteira_sprites"))


@dataclass(frozen=True)
class Perfil:
    nome: str
    inventario: Path
    subpasta: str                # "" = fichas direto na RAIZ (o palco, como sempre foi)
    biblioteca: Path | None      # None = a biblioteca padrao da Oficina (palco)
    pagina: str | None           # pagina do inventario no app; None = nao marca
    exige_mestra: bool = False   # `lote` nao pede nada sem a mestra aprovada


PERFIS = {
    "palco": Perfil("palco",
                    RAIZ_PROJETO / "docs" / "palco" / "inventario_sprites.json",
                    "", None, "237c51f24a0147f8bfd605374665fc02"),
    # A pasta `vila/` da raiz foi aposentada (no `aposentar-vila-pixel`):
    # a arte nova mora ao lado de quem a desenha, a janela flutuante.
    "vila": Perfil("vila",
                   RAIZ_PROJETO / "docs" / "vila" / "inventario_vila.json",
                   "vila", RAIZ_PROJETO / "painel" / "flutuante" / "arte_vila",
                   None, exige_mestra=True),
}

PERFIL = "palco"
INVENTARIO = PERFIS[PERFIL].inventario
PAGINA = PERFIS[PERFIL].pagina


def usar(nome: str = "palco", inventario: str | Path | None = None) -> Perfil:
    """Escolhe o perfil (e, se dado, outro inventario) para este processo."""
    global PERFIL, INVENTARIO, PAGINA
    if nome not in PERFIS:
        raise ValueError(f"perfil desconhecido: {nome} (use {', '.join(PERFIS)})")
    PERFIL = nome
    INVENTARIO = Path(inventario) if inventario else PERFIS[nome].inventario
    PAGINA = PERFIS[nome].pagina
    return PERFIS[nome]


def perfil() -> Perfil:
    return PERFIS[PERFIL]


def itens() -> list[dict]:
    dados = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    return list(dados.get("itens", []))


def item(item_id: str) -> dict:
    achado = next((i for i in itens() if i.get("id") == item_id), None)
    if achado is None:
        raise ValueError(f"item desconhecido: {item_id}")
    return achado


def pasta_do_perfil() -> Path:
    """Onde ficam as fichas deste perfil (o palco segue direto na RAIZ)."""
    sub = perfil().subpasta
    return RAIZ / sub if sub else RAIZ


def pasta(item_id: str) -> Path:
    return pasta_do_perfil() / str(item_id)


def mestra() -> Path:
    """A imagem-mestra aprovada. Compartilhada: palco e Vila usam a mesma."""
    return RAIZ / "_mestra" / "aprovada.png"


def biblioteca() -> Path | None:
    return perfil().biblioteca
