"""O som da LUTA no video: o que o jogo tocou, com os arquivos reais (Onda 16A).

Ate 28/09/2026 a luta de todo video soava com `trilha.sfx_da_luta`: um hit e
um grave SINTETIZADOS por golpe — medido no duelo, 25 vezes o mesmo hit e 14
vezes o mesmo grave. O som do jogo (20 arquivos do pacote e os 11 wav que o
Adrian ajustou em 28/08) nunca tinha chegado a um mp4.

Agora o gravador anota cada som que o jogo tocaria (`luta["sons"]`, ja no
relogio do clipe depois do corte de tedio) e aqui ele vira a trilha do
segmento de luta, misturada com os mesmos arquivos que o jogo usa
(`neural_fights.effects.mixagem`).

Regras:
- luta SEM a lista (gravada antes do anotador) devolve None: o renderer segue
  no sintetizado de sempre, e `main.py som-da-luta` re-anota sem regravar;
- `start_offset` (o round decisivo no fim do video de build) desloca a
  janela: o som que comecou antes do trecho entra pela cauda;
- `sintetizado_de_reforco` soma o sintetizado antigo por baixo, antes de
  normalizar — desligado por padrao (`config/editing.json -> som_da_luta`).
"""
from __future__ import annotations

from pathlib import Path

from . import trilha

PADRAO = {"real": True, "sintetizado_de_reforco": False, "alvo_db": None}


def config_do_evento(event: dict) -> dict:
    """O bloco `som_da_luta` do plano sobre o padrao (plano antigo nao tem)."""
    bloco = dict(PADRAO)
    proprio = event.get("som_da_luta")
    if isinstance(proprio, dict):
        bloco.update({k: v for k, v in proprio.items() if k in PADRAO})
    return bloco


def sons_do_evento(event: dict) -> list | None:
    """A lista `sons` da luta deste evento, ou None se ela e de antes do anotador."""
    luta = event.get("luta") or {}
    sons = luta.get("sons")
    return sons if isinstance(sons, list) else None


def _sintetizado(event: dict, taxa: int):
    """As camadas do som antigo como matriz (n, 2), ou None."""
    if not trilha.disponivel():
        return None
    import numpy as np
    camadas = trilha.sfx_da_luta(event, taxa)
    if not camadas:
        return None
    total = max(1, int(round(float(event["duration"]) * taxa)))
    buf = np.zeros(total, dtype=np.float32)
    for quando, amostras, ganho in camadas:
        ini = int(float(quando) * taxa)
        if ini >= total:
            continue
        seg = np.asarray(amostras, dtype=np.float32)[: max(0, total - ini)]
        buf[max(0, ini): max(0, ini) + len(seg)] += seg * float(ganho)
    return np.stack([buf, buf], axis=1)


def gravar(event: dict, destino: Path, taxa: int = 44100) -> Path | None:
    """WAV do segmento de luta com o som real, ou None para cair no antigo.

    None quando: o evento nao e luta, o som real esta desligado, a luta nao
    tem `sons` (anterior ao anotador), nao ha numpy, ou nenhum som caiu no
    trecho. Quem chama decide o que fazer — e nunca e fingir que ha som.
    """
    if event.get("type") != "gameplay":
        return None
    cfg = config_do_evento(event)
    sons = sons_do_evento(event)
    if not cfg["real"] or sons is None:
        return None
    from neural_fights.effects import mixagem
    if not mixagem.disponivel():
        return None
    extra = _sintetizado(event, taxa) if cfg["sintetizado_de_reforco"] else None
    alvo = cfg.get("alvo_db")
    wav = Path(destino).with_suffix(".wav")
    relatorio = mixagem.trilha_da_luta(
        sons, float(event["duration"]), wav,
        inicio=float(event.get("start_offset") or 0.0), taxa=int(taxa),
        alvo_db=float(alvo) if alvo is not None else mixagem.ALVO_DB,
        extra=extra)
    if relatorio is None:
        return None
    if relatorio.get("sem_arquivo"):
        print(f"[som] sem arquivo para {', '.join(relatorio['sem_arquivo'])} "
              f"(ficaram de fora da luta)", flush=True)
    return wav


def resumo(sons: list | None) -> dict:
    """Contagem para medir a variedade: quantos sons, ids e arquivos distintos."""
    from neural_fights.effects.audio_anotador import arquivos_de_som
    arquivos = arquivos_de_som()
    ids = sorted({str(s.get("id")) for s in sons or [] if isinstance(s, dict)})
    distintos = sorted({arquivos[i].name for i in ids if i in arquivos})
    return {"sons": len(sons or []), "ids": ids, "arquivos": distintos}
