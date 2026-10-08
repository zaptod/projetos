"""Catalogo do Atelie para a arte da Vila, gerado do inventario."""
from __future__ import annotations

import json
import re
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
INVENTARIO = RAIZ / "docs" / "vila" / "inventario_vila.json"
_ID = re.compile(r"[^a-z0-9_.-]+")
_ROTULOS = {"chatgpt": "ChatGPT", "deepseek": "DeepSeek", "grok": "Grok",
            "chao_grama": "Chão de grama", "caminho_terra": "Caminho de terra",
            "passaro": "Pássaro"}
_CATEGORIAS = {"habitantes": "Habitantes", "predios": "Prédios",
                "cenario": "Cenário", "bichos": "Bichos", "objetos": "Objetos",
                "interface": "Interface"}



# Quando cada animacao da Vila toca (a vida -> pose -> animacao, em
# `painel/flutuante/vida.py` e `arte_pronta.POSE_PARA_ANIMACAO`). Pose sem
# folha cai em "parado" e depois em "andar"; direcao sem folha usa a que
# existe (a direita espelhada vira a esquerda). 08/10/2026: o cartao dizia so
# "quando toca: pose" e o Adrian nao sabia o que dispara cada uma.
QUANDO_TOCA = {
    "parado": "parado olhando a vila (e reserva de toda pose sem desenho)",
    "andar": "andando pela vila (e reserva se nao houver Parado)",
    "trabalhar": "trabalhando: tarefa da IA rodando, ou regando",
    "conversar": "conversando, acenando, olhando os patos ou consolando",
    "triste": "triste: a tarefa dela deu erro",
    "comemorar": "comemorando: deu certo",
    "sentado": "sentado no banco, descansando",
}

def _id(valor: object) -> str:
    return _ID.sub("_", str(valor).lower()).strip("_.-")


def chave_do_item(item: dict) -> tuple[str, str] | None:
    """(peca, estado) correspondente a uma entrada do inventario."""
    nome = str(item.get("nome_arquivo") or "").split(" (")[0]
    partes = Path(nome).parts
    grupo = _id(item.get("grupo") or (partes[0] if partes else "vila"))
    base = _id(Path(nome).stem) or _id(item.get("id"))
    if not grupo or not base:
        return None
    chave = _id(item.get("subgrupo") or base) if grupo == "habitantes" else base
    return f"vila.{grupo}.{chave}", base


def rotulo(valor: object) -> str:
    valor = _id(valor)
    return _ROTULOS.get(valor, valor.replace("_", " ").title())


def item_da_chave(peca: str, estado: str) -> dict | None:
    """Entrada do inventario que originou uma folha do Atelie."""
    try:
        itens = json.loads(INVENTARIO.read_text(encoding="utf-8")).get("itens", [])
    except (OSError, ValueError):
        return None
    return next((item for item in itens if isinstance(item, dict)
                 and chave_do_item(item) == (peca, estado)), None)


def catalogo(inventario: Path | None = None) -> list[dict]:
    """Pecas do Atelie. Uma folha do inventario vira um estado da peca."""
    try:
        itens = json.loads((inventario or INVENTARIO).read_text(encoding="utf-8")).get("itens", [])
    except (OSError, ValueError):
        itens = []
    pecas: dict[str, dict] = {}
    for item in itens:
        if not isinstance(item, dict) or not item.get("nome_arquivo") or item.get("grupo") == "base":
            continue
        nome = str(item["nome_arquivo"]).split(" (")[0]
        chave_item = chave_do_item(item)
        if chave_item is None:
            continue
        peca_id, base = chave_item
        grupo = _id(str(item.get("grupo") or ""))
        subgrupo = peca_id.rsplit(".", 1)[-1]
        # Habitantes agrupam as folhas (parado, andar...) da mesma IA.
        peca = pecas.setdefault(peca_id, {"id": peca_id, "grupo": "vila",
            "rotulo": rotulo(subgrupo), "categoria_vila": _CATEGORIAS.get(grupo, rotulo(grupo)),
            "descricao": item.get("descricao", ""),
            "tamanho": item.get("tamanho", ""), "estados": [], "itens_vila": []})
        peca["itens_vila"].append(nome)
        estado = next((e for e in peca["estados"] if e["id"] == base), None)
        if estado is None:
            estado = {"id": base, "rotulo": rotulo(base), "animacoes": []}
            peca["estados"].append(estado)
        ciclos = (item.get("animacao") or {}).get("ciclos") or []
        quando = QUANDO_TOCA.get(base, "na Vila")
        animacoes = [{"id": _id(c.get("nome")), "rotulo": rotulo(c.get("nome")),
                      "gatilho": quando, "loop": bool(c.get("loop", True))}
                     for c in ciclos if isinstance(c, dict) and c.get("nome")]
        if not animacoes:
            animacoes = [{"id": "parado", "rotulo": "Parado", "gatilho": quando, "loop": True}]
        estado["animacoes"] = animacoes
    return sorted(pecas.values(), key=lambda p: p["id"])
