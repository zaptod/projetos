# -*- coding: utf-8 -*-
"""O que se MEDE para dizer "ficou limpo" sem depender de olhar.

Nenhuma destas contas e sobre gosto; cada uma responde a um defeito que a
folha do ChatGPT tinha e que o `piriri.py` deixava passar:

  grade      linhas de grade que ainda se detectam (e px dentro das faixas
             onde elas estavam)
  franja     px VISIVEIS com a cor da franja (verde forte: distancia <= 20
             na escala 0..255), e px INVISIVEIS que ainda guardam essa cor
             (o fantasma que aparece em quem ignora o alfa)
  pontinhos  componentes menores que o minimo de ilha
  buracos    px que eram desenho (alfa >= 200) e viraram transparentes --
             o limiar de branco furava o brilho da bola
  ancoras    o quanto a ancora de cada quadro se afasta da ancora da celula
"""
from __future__ import annotations

import numpy as np

from . import alinhar, limpeza
from .rotulos import rotular

FRANJA_FORTE = 20.0


def franja(arr: np.ndarray, cor) -> dict:
    if cor is None:
        return {"visivel": 0, "oculta": 0}
    d = limpeza.distancia(arr[..., :3], cor)
    a = arr[..., 3]
    perto = d <= FRANJA_FORTE
    # "oculta" so conta cor de verdade: preto em pixel transparente e o
    # vazio, nao a franja (a menos que a franja seja preta)
    oculta = perto & (a == 0)
    if limpeza.distancia(np.zeros((1, 1, 3)), cor)[0, 0] > FRANJA_FORTE:
        oculta &= arr[..., :3].any(-1)
    return {"visivel": int((perto & (a > 0)).sum()), "oculta": int(oculta.sum())}


def linhas_de_grade(arr: np.ndarray) -> int:
    visivel = arr[..., 3] > 0
    return (len(limpeza.detectar_linhas(visivel))
            + len(limpeza.detectar_linhas(visivel.T)))


def px_nas_faixas(arr: np.ndarray, horizontais, verticais) -> int:
    marca = np.zeros(arr.shape[:2], bool)
    for y0, y1 in horizontais:
        marca[y0:y1] = True
    for x0, x1 in verticais:
        marca[:, x0:x1] = True
    return int(((arr[..., 3] > 0) & marca).sum())


def pontinhos(arr: np.ndarray, area_min: int = 12) -> int:
    comps = rotular(arr[..., 3] > 0)
    return int((comps.areas < area_min).sum())


def buracos(original: np.ndarray, limpo: np.ndarray) -> int:
    return int(((original[..., 3] >= 200) & (limpo[..., 3] == 0)).sum())


def desvio_das_ancoras(alinhado, modo: str = "massa") -> float:
    """Maior diferenca (px, em x ou em y) entre a ancora recalculada de cada
    quadro e a ancora da celula. Por construcao fica em ate 0,5 px (a
    colagem e em px inteiros) -- mais que isso e quadro desalinhado. Com a
    celula reduzida (`largura_max`) a reamostragem soma um pouco."""
    if not alinhado.quadros:
        return 0.0
    ax, ay = alinhado.ancora
    pior = 0.0
    for q in alinhado.quadros:
        qx, qy = alinhar.ancora_de(q, modo)
        pior = max(pior, abs(qx - ax), abs(qy - ay))
    return float(pior)


def medir(res, receita=None) -> dict:
    """As medidas de um `receita.Resultado`, antes (origem) e depois."""
    area_min = getattr(receita, "ilha_min", 12) or 12
    modo = getattr(receita, "ancora", "massa")
    antes_f = franja(res.original, res.franja)
    depois_f = franja(res.limpo, res.franja)
    folha_f = franja(res.folha, res.franja)
    return {
        "quadros": len(res.caixas),
        "grade": {"colunas": res.grade.colunas if res.grade else None,
                  "linhas": res.grade.linhas if res.grade else None,
                  "modo": res.modo_fatiar},
        "linhas_de_grade": {"antes": len(res.linhas_h) + len(res.linhas_v),
                            "folha": linhas_de_grade(res.folha)},
        "px_nas_faixas": {
            "antes": px_nas_faixas(res.original, res.linhas_h, res.linhas_v),
            "depois": px_nas_faixas(res.limpo, res.linhas_h, res.linhas_v)},
        "franja": {"antes": antes_f, "depois": depois_f, "folha": folha_f},
        "pontinhos": {"antes": pontinhos(res.original, area_min),
                      "folha": pontinhos(res.folha, area_min)},
        "buracos": buracos(res.original, res.limpo),
        "ancoras_desvio_px": round(desvio_das_ancoras(res.alinhado, modo), 3),
        "celula": list(res.alinhado.celula),
        "folha": [int(res.folha.shape[1]), int(res.folha.shape[0])],
        "colunas": res.colunas, "linhas": res.linhas,
    }


def resumo(m: dict) -> str:
    """Uma linha para a tela."""
    f = m["franja"]["folha"]
    return (f"{m['quadros']} quadros · grade {m['linhas_de_grade']['folha']} "
            f"linha(s) · franja {f['visivel'] + f['oculta']} px · "
            f"pontinhos {m['pontinhos']['folha']} · buracos {m['buracos']} · "
            f"âncoras ±{m['ancoras_desvio_px']:.1f} px")


__all__ = ["FRANJA_FORTE", "buracos", "desvio_das_ancoras", "franja",
           "linhas_de_grade", "medir", "pontinhos", "px_nas_faixas", "resumo"]
