"""De onde vem a timeline: seed -> luta -> timeline v1, e o corte de tedio.

A luta roda no MESMO laco do gravador (`neural_fights.recording.timeline.
gravar_timeline`, da 16C) e SEM desenhar: medido pela 16C, e o mesmo hash de
estado em todos os passos e custa 10 s contra 43 s. Empate refaz com a seed
seguinte, como `runner.gravar_confronto` (tres tentativas).

O corte de tedio e o do duelo de hoje (`highlights.planejar_corte_tedio` com o
`config_gameplay(..., "duelo")`), alimentado pelos eventos de dano da
timeline no relogio do video do gravador. Vira `remapeamento` e o palco o
renderiza direto: acaba a terceira compressao.
"""
from __future__ import annotations

import math

from .config import ErroPalco


def timeline_da_luta(*, p1: str, p2: str, seed: int, cenario: str,
                     camera_largura_min_m: float | None = None,
                     camera_espera_zoom_in: float | None = None,
                     tentativas: int = 3, corrente_v2: bool | None = None) -> tuple[dict, int]:
    """(documento da timeline, seed usada). A seed pode andar em empate.

    `corrente_v2`: a chave da corrente nova desta luta. Luta GRAVADA passa o
    carimbo do fight.json (`runner.corrente_da_luta`); luta nova so do palco,
    None = o padrao do motor (hoje desligada)."""
    try:
        from neural_fights.recording.timeline import gravar_timeline
    except ImportError as erro:
        raise ErroPalco("a timeline da 16C (neural_fights/recording/timeline.py) nao esta no disco") from erro
    documento, semente = None, seed
    for tentativa in range(max(1, tentativas)):
        semente = seed + tentativa
        saida = gravar_timeline(p1=p1, p2=p2, seed=semente, cenario=cenario, resolucao=(1080, 1920),
                                camera_modo="DIRETOR", camera_largura_min_m=camera_largura_min_m,
                                camera_espera_zoom_in=camera_espera_zoom_in, desenhar=False,
                                corrente_v2=corrente_v2)
        documento = saida["timeline"]
        if not (saida.get("resultado") or {}).get("empate"):
            break
    return documento, semente


def eventos_de_dano(doc: dict) -> list[tuple]:
    """Os golpes no relogio do VIDEO do gravador, como a SondaDeDano grava:
    o passo i cai no quadro ceil(i / passos_por_quadro)."""
    resultado = doc.get("resultado") or {}
    por_quadro = int(resultado.get("passos_por_quadro") or 2)
    fps = int(doc.get("hz", 60)) / por_quadro
    saida = []
    for ev in doc.get("eventos") or []:
        if ev.get("tipo") in ("acerto", "dano"):
            t = math.ceil(int(ev["i"]) / por_quadro) / fps
            saida.append((round(t, 3), ev.get("alvo"), float(ev.get("dano", 0.0)), str(ev.get("categoria") or "")))
    return saida


def corte_de_tedio(doc: dict, gameplay: dict) -> list[list[float]]:
    """Trechos [inicio, duracao, 1.0] que ficam, pela regra do duelo de hoje."""
    from ..tournament import highlights

    resultado = doc.get("resultado") or {}
    gravacao = {
        "duracao_video": round(float(resultado.get("duracao_video") or doc["n"] / doc["hz"]), 2),
        "ko_em_video": None if resultado.get("ko_em_video") is None else round(float(resultado["ko_em_video"]), 2),
        "eventos_dano": eventos_de_dano(doc),
    }
    trechos = highlights.planejar_corte_tedio(
        gravacao, max_total=float(gameplay["max_total"]), seca_min=float(gameplay["seca"]),
        contexto=float(gameplay["contexto"]), protecao_ko=float(gameplay["protecao_ko"]),
        abertura=float(gameplay["abertura"]),
        minimo_para_cortar=float(gameplay.get("minimo_para_cortar", 12.0)))
    return [[float(ini), float(dur), 1.0] for ini, dur in trechos]
