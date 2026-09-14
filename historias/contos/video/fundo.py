# -*- coding: utf-8 -*-
"""O video da metade de baixo da tela dividida.

Pedido dele (14/09/2026): "na parte de baixo uma parte aleatoria retirada
desse video". O arquivo e um video de maquiagem de 61 minutos, sem faixa de
audio — a metade de baixo sai muda de qualquer jeito.

ALEATORIO, MAS O MESMO TRECHO PARA A MESMA PARTE. A parte e renderizada de novo
com frequencia (o reparo refaz uma imagem e re-renderiza), e sortear a cada
render trocaria o fundo de um video que ja passou pela revisao da IA. O sorteio
e o hash de `historia:parte`: espalha bem pelo video e se repete sozinho.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from builds.video import medidas as _rb_video_medidas

MARGEM_INICIO_S = 20.0
MARGEM_FIM_S = 20.0


def caminho(cfg_fundo: dict | None, assets: Path) -> Path | None:
    """O arquivo configurado: relativo a `assets/`, ou absoluto."""
    arquivo = str((cfg_fundo or {}).get("arquivo") or "").strip()
    if not arquivo:
        return None
    alvo = Path(arquivo)
    return alvo if alvo.is_absolute() else Path(assets) / alvo


def offset(historia_id: str, parte: int, total: float, duracao_clipe: float,
           margem_inicio: float = MARGEM_INICIO_S,
           margem_fim: float = MARGEM_FIM_S) -> float:
    """Onde o trecho comeca dentro do video de fundo, em segundos.

    Fica longe das pontas (abertura e encerramento costumam ter texto e tela
    preta). Se o clipe e curto demais para as margens, elas somem antes do
    trecho; se e mais curto que o video inteiro, comeca do zero e o renderer
    repete o clipe.
    """
    total = max(0.0, float(total))
    duracao_clipe = max(0.0, float(duracao_clipe))
    livre = duracao_clipe - total - margem_inicio - margem_fim
    base = float(margem_inicio)
    if livre <= 0:
        livre, base = duracao_clipe - total, 0.0
        if livre <= 0:
            return 0.0
    semente = hashlib.sha1(f"{historia_id}:{int(parte)}".encode("utf-8"))
    fracao = int(semente.hexdigest()[:12], 16) / float(16 ** 12)
    return round(base + fracao * livre, 3)


def escolher(historia_id: str, parte: int, total: float,
             cfg_fundo: dict | None, assets: Path) -> dict | None:
    """`{arquivo, offset_s, duracao_clipe, repetir}` ou None se nao ha fundo.

    None quer dizer "sai no layout de sempre": sem o arquivo a parte nao pode
    deixar de existir.
    """
    alvo = caminho(cfg_fundo, assets)
    if alvo is None or not alvo.is_file():
        return None
    duracao = _rb_video_medidas.duracao(alvo)
    if not duracao or duracao <= 1.0:
        return None
    cfg = cfg_fundo or {}
    inicio = offset(historia_id, parte, total, duracao,
                    float(cfg.get("margem_inicio_s", MARGEM_INICIO_S)),
                    float(cfg.get("margem_fim_s", MARGEM_FIM_S)))
    return {"arquivo": str(alvo), "offset_s": inicio,
            "duracao_clipe": round(float(duracao), 3),
            "repetir": float(duracao) < float(total)}


__all__ = ["caminho", "escolher", "offset"]
