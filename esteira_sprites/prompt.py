"""A biblia textual de estilo enviada a cada pedido de imagem."""
from __future__ import annotations

from . import config

ROXOS_OU_ROSAS = ("TREVAS", "ARCANO", "VOID", "TEMPO", "GRAVITACAO",
                   "ROXO", "ROXA", "ROSA", "MAGENTA")


def fundo_do(item: dict) -> str:
    texto = " ".join((str(item.get("id", "")), str(item.get("nome_arquivo", "")),
                       str(item.get("descricao", "")))).upper()
    return "#00FF00" if any(nome in texto for nome in ROXOS_OU_ROSAS) else "#FF00FF"


def montar(item: dict, defeitos: str = "") -> str:
    fundo = fundo_do(item)
    tipo = item.get("tipo", "peca")
    partes = [
        "Sprite pixel-art para Neural Fights.",
        f"Desenhe: {item.get('descricao') or item.get('nome_arquivo') or item['id']}.",
        "Contorno #14141A de 3-4 px; cel shading de exatamente 2 tons; luz do alto a esquerda; cores saturadas e legiveis pequenos.",
        "Sem texto, numeros, grade desenhada ou moldura.",
        f"Fundo liso uniforme {fundo}, sem sombra no fundo.",
    ]
    if tipo == "folha":
        partes.append("Folha 4x4 com exatamente 16 quadros de animacao, igualmente espacados, sem linhas entre quadros.")
    else:
        partes.append("Peca parada: um objeto unico, centrado, sem tocar a borda.")
        texto = " ".join(str(item.get(k, "")) for k in ("id", "nome_arquivo", "descricao")).lower()
        if "arma" in texto or "projetil" in texto:
            partes.append("Arma ou projetil aponta para a direita.")
    if config.mestra().is_file():
        partes.append("Siga rigorosamente o estilo da imagem-mestra aprovada anexada a este pedido.")
    if defeitos:
        partes.append(f"Corrija estes defeitos da tentativa anterior: {defeitos}.")
    return " ".join(partes)
