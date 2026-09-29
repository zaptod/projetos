# -*- coding: utf-8 -*-
"""A mesma receita em varias folhas (o botao Lote e a linha de comando).

Cada folha sai limpa numa pasta, com um .json ao lado (a receita e as
medidas). O palco NAO recebe nada daqui: identificar (tipo, elemento, prova)
e de uma folha por vez, na pagina.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import limpeza, medidas
from .receita import Receita, processar


def limpar_lote(arquivos, receita: Receita, pasta) -> list:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    receita = receita.para_lote()
    saida = []
    for arquivo in arquivos:
        arquivo = Path(arquivo)
        try:
            res = processar(limpeza.abrir(arquivo), receita)
            m = medidas.medir(res, receita)
            destino = pasta / f"{arquivo.stem}_folha.png"
            limpeza.para_imagem(res.folha).save(destino, "PNG", optimize=True)
            destino.with_suffix(".json").write_text(json.dumps(
                {"fonte": arquivo.name, "receita": receita.para_dict(),
                 "medidas": m, "ancora": list(res.alinhado.ancora)},
                ensure_ascii=False, indent=2), encoding="utf-8")
            saida.append({"arquivo": arquivo.name, "destino": str(destino),
                          "medidas": m, "resumo": medidas.resumo(m)})
        except Exception as erro:                            # noqa: BLE001
            saida.append({"arquivo": arquivo.name, "erro": True,
                          "resumo": f"{type(erro).__name__}: {erro}"})
    return saida


__all__ = ["limpar_lote"]
