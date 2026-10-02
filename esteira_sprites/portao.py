"""Portao objetivo: mede defeitos tecnicos antes de chamar o juiz."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from painel.sprites import fundo_auto, medidas

from . import animacao, ficha, prompt

LIMITE_FRANJA = 0
LIMITE_PONTINHOS = 0
# borda que continua opaca depois da limpeza = fundo grudado (02/10/2026)
LIMITE_FUNDO = 0.02
LIMITE_PROPORCAO = 0.10
LIMITE_COSTURA_FATOR = 3.0   # textura opaca: emenda ate 3x o salto entre vizinhos
LIMITE_COSTURA_MIN = 12.0    # ...e nunca reprova abaixo disto (niveis 0..255)


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


def _costura(arr: np.ndarray) -> tuple[float, float]:
    """(salto na emenda, salto tipico entre vizinhos), em niveis de 0..255."""
    rgb = arr[..., :3].astype(np.float32)
    emenda = max(float(np.abs(rgb[:, 0] - rgb[:, -1]).mean()),
                 float(np.abs(rgb[0] - rgb[-1]).mean()))
    tipico = max(float(np.abs(np.diff(rgb, axis=1)).mean()),
                 float(np.abs(np.diff(rgb, axis=0)).mean()))
    return round(emenda, 2), round(tipico, 2)


def _validar_opaco(arr: np.ndarray) -> dict:
    """Textura opaca (chao, caminho): sem chroma; tem de emendar nos lados."""
    emenda, tipico = _costura(arr)
    limite = max(LIMITE_COSTURA_FATOR * tipico, LIMITE_COSTURA_MIN)
    valores = {"transparentes": int((arr[..., 3] < 255).sum()),
               "costura": emenda, "vizinhos": tipico}
    erros = []
    if valores["transparentes"]:
        erros.append(f"textura opaca com {valores['transparentes']} px transparentes (limite 0)")
    if emenda > limite:
        erros.append(f"a textura nao emenda: salto de {emenda:.1f} na costura contra {tipico:.1f} "
                     f"entre vizinhos (limite {limite:.1f})")
    return {"aprovado": not erros, "erros": erros, "medidas": valores}


def validar(item: dict, caminho: str | Path) -> dict:
    arr = _arr(str(caminho))
    if prompt.opaco(item):
        return _validar_opaco(arr)
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
    sobra = fundo_auto.sobra_de_fundo(arr)
    valores["fundo_na_borda"] = round(sobra, 3)
    if sobra > LIMITE_FUNDO:
        erros.append(f"fundo grudado: {sobra:.0%} da borda continua opaca (limite {LIMITE_FUNDO:.0%})")
    total_franja = franja["visivel"] + franja["oculta"]
    if total_franja > LIMITE_FRANJA:
        erros.append(f"franja de chroma: {total_franja} px (limite {LIMITE_FRANJA})")
    if linhas:
        erros.append(f"linhas de grade detectadas: {linhas} (limite 0)")
    if pontos > LIMITE_PONTINHOS:
        erros.append(f"pontinhos soltos: {pontos} (limite {LIMITE_PONTINHOS})")
    if borda:
        erros.append(f"peca encosta na borda: {borda} px")
    if prompt.animacao(item) is not None:
        # folha em ciclo: o validador de animacao conta os quadros pela
        # grade do item e mede ancora, escala, paleta, loop e contorno
        anim_erros, anim_valores = animacao.validar(arr, item)
        erros.extend(anim_erros)
        valores["animacao"] = anim_valores
    elif item.get("tipo") == "folha":
        folhas, valores_folha = _folha(arr)
        erros.extend(folhas)
        valores.update(valores_folha)
    elif item.get("contorno"):
        falta = animacao.contorno_falta(arr)
        valores["contorno_falta"] = falta
        if falta > animacao.CONTORNO_FALTA_MAX:
            erros.append(f"contorno escuro falta em {falta * 100:.0f}% do perimetro "
                         f"(limite {animacao.CONTORNO_FALTA_MAX * 100:.0f}%)")
    return {"aprovado": not erros, "erros": erros, "medidas": valores}


def _previa(dados: dict, tentativa: dict) -> None:
    """GIF/WebP do ciclo para o juiz e a tela de conferir (mesmo reprovado)."""
    item = dados["item"]
    if prompt.animacao(item) is None:
        return
    destino = ficha.caminho(dados["item_id"]).parent / "previa"
    saida = animacao.previa(_arr(tentativa["caminhos"]["limpo"]), item, destino)
    tentativa["caminhos"]["previa_gif"] = saida.get("gif", "")
    tentativa["caminhos"]["previa_webp"] = saida.get("webp", "")


def passar(item_id: str) -> bool:
    dados = ficha.ler(item_id)
    if not dados or dados.get("estado") != "limpo":
        return False
    tentativa = dados["tentativas"][-1]
    resultado = validar(dados["item"], tentativa["caminhos"]["limpo"])
    _previa(dados, tentativa)
    tentativa["medidas"] = resultado["medidas"]
    tentativa["portao"] = resultado
    if resultado["aprovado"]:
        dados["estado"] = "medido"
        ficha.registrar(dados, "portao_aprovou", medidas=resultado["medidas"])
    else:
        # reprovado pela medida tambem vai ao juiz: ele ve a imagem, o prompt usado
        # e o que a medida achou, e devolve o prompt corrigido (02/10/2026)
        dados["estado"] = "medido"
        tentativa["motivo"] = "; ".join(resultado["erros"])
        tentativa["portao_reprovou"] = list(resultado["erros"])
        ficha.registrar(dados, "portao_reprovou", motivo=tentativa["motivo"])
    ficha.gravar(dados)
    return True
