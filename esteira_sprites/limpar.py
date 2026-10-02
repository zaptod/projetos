"""Limpeza adaptada da Oficina, sem alterar seus modulos."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from painel.sprites import fundo_auto, receita

from . import ficha, prompt


def _receita(item: dict) -> receita.Receita:
    folha = item.get("tipo") == "folha"
    colunas, linhas = prompt.grade(item) if folha else (0, 0)
    anim = prompt.animacao(item)
    cor = prompt.fundo_do(item)
    rgb = [int(cor[i:i + 2], 16) for i in (1, 3, 5)]
    extra = {}
    if anim is not None:
        # Ciclo: cada linha e uma direcao, entao celula vazia NAO pode sumir
        # (os quadros seguintes subiriam de linha) -- o portao conta e reprova.
        # Pes no mesmo ponto quando a animacao anda; o resto, pela massa.
        extra = {"ignorar_vazias": False,
                 "ancora": "pe" if anim.get("ancora") in ("pes", "base") else "massa"}
    return receita.Receita(fundo="cor", cor_fundo=rgb, fatiar="uniforme",
                           colunas=colunas, linhas=linhas, **extra)


def limpar(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "gerado":
        return False
    tentativa = dados["tentativas"][-1]
    origem = Path(tentativa["caminhos"]["gerada"])
    item = dados["item"]
    destino = ficha.caminho(item_id).parent / "limpo.png"
    if prompt.opaco(item):
        # textura opaca: nao ha chroma para tirar; o portao mede a emenda
        with Image.open(origem) as imagem:
            imagem.convert("RGBA").save(destino, "PNG")
        tentativa["receita"] = {"fundo": "opaco"}
    else:
        r = _receita(item)
        with Image.open(origem) as imagem:
            res = receita.processar(imagem, r)
        saida = res.folha if item.get("tipo") == "folha" else res.limpo
        # a IA as vezes ignora o chroma pedido e desenha xadrez ou branco: o
        # fundo automatico descobre qual e e tira (02/10/2026: 7 passaram assim)
        saida, achado = fundo_auto.remover(saida)
        tentativa["fundo_detectado"] = achado["tipo"]
        Image.fromarray(saida, "RGBA").save(destino, "PNG")
        tentativa["receita"] = r.para_dict()
    tentativa["caminhos"]["limpo"] = str(destino)
    dados["estado"] = "limpo"
    ficha.registrar(dados, "limpo", caminho=str(destino))
    ficha.gravar(dados)
    return True
