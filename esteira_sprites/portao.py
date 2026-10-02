"""Portao objetivo: mede defeitos tecnicos antes de chamar o juiz."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from painel.sprites import medidas

from . import ficha, prompt

LIMITE_FRANJA = 0
LIMITE_PONTINHOS = 0
LIMITE_PROPORCAO = 0.10


def _arr(caminho: str) -> np.ndarray:
    return np.asarray(Image.open(caminho).convert("RGBA"))


def _na_borda(arr: np.ndarray) -> int:
    alfa = arr[..., 3] > 0
    return int(alfa[0].sum() + alfa[-1].sum() + alfa[1:-1, 0].sum() + alfa[1:-1, -1].sum())


def _folha(arr: np.ndarray) -> tuple[list[str], dict]:
    h, w = arr.shape[:2]
    erros, valores = [], {"quadros_nao_vazios": 0, "proporcao_desvio": 0.0}
    if w % 4 or h % 4:
        return [f"folha com dimensoes nao divisiveis por 4 ({w}x{h})"], valores
    cw, ch = w // 4, h // 4
    areas = []
    for linha in range(4):
        for coluna in range(4):
            quadro = arr[linha * ch:(linha + 1) * ch, coluna * cw:(coluna + 1) * cw]
            area = int((quadro[..., 3] > 0).sum())
            areas.append(area)
    valores["quadros_nao_vazios"] = sum(a > 0 for a in areas)
    if valores["quadros_nao_vazios"] != 16:
        erros.append(f"folha com {valores['quadros_nao_vazios']} quadros nao-vazios (esperados 16)")
    proporcoes = [cw / ch] * 16
    valores["proporcao_desvio"] = round(max(proporcoes) - min(proporcoes), 3)
    if valores["proporcao_desvio"] > LIMITE_PROPORCAO:
        erros.append(f"proporcao entre quadros variou {valores['proporcao_desvio']:.3f} (limite {LIMITE_PROPORCAO:.3f})")
    return erros, valores


def validar(item: dict, caminho: str | Path) -> dict:
    arr = _arr(str(caminho))
    alfa = arr[..., 3]
    cor_hex = prompt.fundo_do(item)
    cor = [int(cor_hex[i:i + 2], 16) for i in (1, 3, 5)]
    franja = medidas.franja(arr, cor)
    linhas = medidas.linhas_de_grade(arr)
    visivel = arr[..., 3] > 0
    # A medicao da Oficina procura linhas que se destacam dos quadros. Esta
    # segunda conta cobre a grade que atravessa toda a folha, inclusive a
    # moldura que chega ate as bordas.
    linhas = max(linhas, int((visivel.mean(axis=1) >= 0.90).sum()
                              + (visivel.mean(axis=0) >= 0.90).sum()))
    pontos = medidas.pontinhos(arr)
    borda = _na_borda(arr)
    valores = {"transparencia": int((alfa == 0).sum()),
               "franja": franja, "linhas_de_grade": linhas,
               "pontinhos": pontos, "pixels_na_borda": borda}
    erros = []
    if not valores["transparencia"]:
        erros.append("nao sobrou transparencia (0 pixels alfa=0)")
    total_franja = franja["visivel"] + franja["oculta"]
    if total_franja > LIMITE_FRANJA:
        erros.append(f"franja de chroma: {total_franja} px (limite {LIMITE_FRANJA})")
    if linhas:
        erros.append(f"linhas de grade detectadas: {linhas} (limite 0)")
    if pontos > LIMITE_PONTINHOS:
        erros.append(f"pontinhos soltos: {pontos} (limite {LIMITE_PONTINHOS})")
    if borda:
        erros.append(f"peca encosta na borda: {borda} px")
    if item.get("tipo") == "folha":
        folhas, valores_folha = _folha(arr)
        erros.extend(folhas)
        valores.update(valores_folha)
    return {"aprovado": not erros, "erros": erros, "medidas": valores}


def passar(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "limpo":
        return False
    tentativa = dados["tentativas"][-1]
    resultado = validar(dados["item"], tentativa["caminhos"]["limpo"])
    tentativa["medidas"] = resultado["medidas"]
    tentativa["portao"] = resultado
    if resultado["aprovado"]:
        dados["estado"] = "medido"
        ficha.registrar(dados, "portao_aprovou", medidas=resultado["medidas"])
    else:
        dados["estado"] = "refazer"
        tentativa["motivo"] = "; ".join(resultado["erros"])
        ficha.registrar(dados, "portao_reprovou", motivo=tentativa["motivo"])
    ficha.gravar(dados)
    return True
