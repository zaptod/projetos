"""Limpeza adaptada da Oficina, sem alterar seus modulos."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from painel.sprites import receita

from . import ficha, prompt


def limpar(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "gerado":
        return False
    tentativa = dados["tentativas"][-1]
    origem = Path(tentativa["caminhos"]["gerada"])
    item = dados["item"]
    cor = prompt.fundo_do(item)
    rgb = [int(cor[i:i + 2], 16) for i in (1, 3, 5)]
    r = receita.Receita(fundo="cor", cor_fundo=rgb, fatiar="uniforme",
                        colunas=4 if item.get("tipo") == "folha" else 0,
                        linhas=4 if item.get("tipo") == "folha" else 0)
    with Image.open(origem) as imagem:
        res = receita.processar(imagem, r)
    destino = ficha.caminho(item_id).parent / "limpo.png"
    saida = res.folha if item.get("tipo") == "folha" else res.limpo
    Image.fromarray(saida, "RGBA").save(destino, "PNG")
    tentativa["caminhos"]["limpo"] = str(destino)
    tentativa["receita"] = r.para_dict()
    dados["estado"] = "limpo"
    ficha.registrar(dados, "limpo", caminho=str(destino))
    ficha.gravar(dados)
    return True
