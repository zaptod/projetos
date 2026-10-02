"""Colhe a resposta do carteiro sem depender de navegador ou IA."""
from __future__ import annotations

import shutil
from pathlib import Path

from ias import correio

from . import ficha


def _tentativa(dados: dict) -> dict:
    if not dados.get("tentativas"):
        raise ValueError("ficha sem tentativa")
    return dados["tentativas"][-1]


def _imagem(mensagem: dict, tentativa: dict) -> Path | None:
    caminho = mensagem.get("imagem", {}).get("caminho") if isinstance(mensagem.get("imagem"), dict) else None
    if caminho and Path(caminho).is_file():
        return Path(caminho)
    return correio.arquivo_da_imagem(tentativa.get("caixa", "chatgpt"), tentativa["correio_id"])


def colher(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "pedido":
        return False
    tentativa = _tentativa(dados)
    mensagem = correio.uma(tentativa.get("caixa", "chatgpt"), tentativa["correio_id"])
    if not mensagem or mensagem.get("situacao") not in ("respondida", "falhou"):
        return False
    if mensagem["situacao"] == "falhou":
        tentativa["erro"] = mensagem.get("erro") or "o correio falhou"
        dados["estado"] = "refazer"
        ficha.registrar(dados, "falhou", motivo=tentativa["erro"])
        ficha.gravar(dados)
        return True
    origem = _imagem(mensagem, tentativa)
    if origem is None:
        tentativa["erro"] = "resposta sem imagem valida"
        dados["estado"] = "refazer"
        ficha.gravar(dados)
        return True
    destino = ficha.caminho(item_id).parent / ("gerada" + origem.suffix.lower())
    shutil.copy2(origem, destino)
    prova_origem = origem.with_suffix(".prova.json")
    prova = None
    if prova_origem.is_file():
        prova = ficha.caminho(item_id).parent / "prova.json"
        shutil.copy2(prova_origem, prova)
    tentativa["caminhos"].update({"gerada": str(destino), "prova": str(prova) if prova else ""})
    dados["estado"] = "gerado"
    ficha.registrar(dados, "gerado", caminho=str(destino))
    ficha.gravar(dados)
    return True
