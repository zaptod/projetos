# -*- coding: utf-8 -*-
"""Velocidade e layout de uma HISTORIA, e nao de um render.

Em 14/09/2026 o video de historia ganhou 1,7x e tela dividida — "em todos os
videos daqui pra frente", e so nos novos. O perigo e a serie que ja esta no
meio: o reparo re-renderiza partes de historias antigas depois de refazer uma
imagem, e a `historia_00011` tinha a parte 2 publicada no formato antigo
enquanto as outras cinco ainda iam ser renderizadas. Sem travar o formato, a
mesma serie trocaria de velocidade e de tela de uma parte para a outra.

A regra, na ordem:

  1. `outputs/<id>/formato.json` — escolha explicita, para converter uma
     historia de proposito;
  2. se QUALQUER parte ja renderizada nao tem o campo `formato` no plano (ou
     so ha mp4 sem plano), a historia e de antes da mudanca: formato antigo;
  3. senao, o `formato` dos planos — a primeira parte renderizada decide
     pelas outras;
  4. senao, o que o `render.json` pede hoje.
"""
from __future__ import annotations

import json
from pathlib import Path

LEGADO = {"velocidade": 1.0, "layout": "vertical"}
# Fracao da altura que a historia ocupa na tela dividida. Constante, e nao
# config: o renderer desenha nela e o parecer recorta a folha de contato por
# ela — um valor em cada lugar mostraria ao revisor metade do video errada.
PAINEL = 0.5
LAYOUTS = ("vertical", "dividido")
PREFIXO = "contos:"


def normalizar(dados: dict | None) -> dict:
    dados = dados or {}
    try:
        velocidade = float(dados.get("velocidade") or 1.0)
    except (TypeError, ValueError):
        velocidade = 1.0
    layout = str(dados.get("layout") or "vertical").strip().lower()
    return {"velocidade": round(min(2.0, max(0.5, velocidade)), 3),
            "layout": layout if layout in LAYOUTS else "vertical"}


def do_config(cfg_render: dict | None) -> dict:
    return normalizar((cfg_render or {}).get("formato"))


def _ler_json(caminho: Path):
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def resolver(historia_id: str, cfg_render: dict | None, pasta: Path) -> dict:
    """O formato desta historia, com `origem` dizendo de onde veio."""
    pasta = Path(pasta)
    escolhido = _ler_json(pasta / "formato.json")
    if isinstance(escolhido, dict):
        return {**normalizar(escolhido), "origem": "formato.json"}

    planos = sorted((pasta / "partes").glob("p*/edit_plan.json"))
    achados = []
    for plano in planos:
        dados = _ler_json(plano)
        pedido = dados.get("formato") if isinstance(dados, dict) else None
        if not isinstance(pedido, dict):
            # UMA PARTE ANTIGA BASTA. Todo render desde 14/09/2026 grava o
            # campo, entao plano sem ele e de antes da mudanca — e a serie
            # tem parte no ar no formato antigo. Achado pela revisao
            # adversarial: "o primeiro plano que tiver formato decide" deixava
            # uma parte convertida por engano arrastar as irmas antigas.
            return {**LEGADO,
                    "origem": f"{plano.parent.name} e de antes da mudanca"}
        achados.append((plano, pedido))
    if achados:
        plano, pedido = achados[0]
        return {**normalizar(pedido),
                "origem": f"{plano.parent.name}/edit_plan.json"}
    if any(pasta.glob("final_*.mp4")):
        return {**LEGADO, "origem": "historia anterior a mudanca"}
    return {**do_config(cfg_render), "origem": "render.json"}


def rotulo(formato: dict) -> str:
    """O texto gravado no `comment` do mp4: o arquivo diz como foi feito."""
    f = normalizar(formato)
    return f"{PREFIXO}velocidade={f['velocidade']:.3f};layout={f['layout']}"


def ler_rotulo(texto: str | None) -> dict | None:
    texto = str(texto or "").strip()
    if not texto.startswith(PREFIXO):
        return None
    campos = {}
    for pedaco in texto[len(PREFIXO):].split(";"):
        chave, _, valor = pedaco.partition("=")
        if chave.strip():
            campos[chave.strip()] = valor.strip()
    return normalizar(campos)


__all__ = ["LEGADO", "do_config", "ler_rotulo", "normalizar", "resolver",
           "rotulo"]
