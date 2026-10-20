# -*- coding: utf-8 -*-
"""A voz do quadro 0 do duelo: "Sword versus Dagger, who will win?".

Semana 1 do plano, acrescimo de 20/10/2026 (docs/pesquisa/som-ganchos-e-
musica.md, item 2): os dois duelos campeoes que abrem com voz — o de 22,1 mi
do Orbitality e o de 3,7 mi do pulsebattles — leem o confronto e perguntam
quem vence nos primeiros 2-3 s, junto da pergunta escrita. Aqui a frase sai
do MESMO rotulo do titulo e da faixa (`publicar/confronto.py`), em ingles
(decisao `geral/canal-em-ingles`), pela voz neural en-US do edge-tts. A luta
continua em movimento por baixo: a voz e so uma faixa a mais na mixagem final
do renderer (`render(..., voz=)`), que ja abaixa a musica sob a fala.

SO O EDGE-TTS. A reserva do `voz.sintetizar` e o SAPI do Windows, que neste
PC e a Maria (pt-BR): a frase em ingles lida por ela foi o defeito das 51
roletas de 12 a 19/10 (memoria "voz 403"). Sem o edge, o duelo sai SEM a voz
— a pergunta escrita continua no quadro 0 —, nunca com a voz errada.

Nada aqui mexe na trilha (isso e a semana 2).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import voz

# A mais proxima da voz de sempre (pt-BR-AntonioNeural, masculina, neutra).
VOZ_PADRAO = "en-US-GuyNeural"
PADRAO = {
    "ativa": True,
    "voz": VOZ_PADRAO,
    # um pouco mais rapida que a natural: a frase tem de caber em ~2 s
    "taxa": "+12%",
    "tom": "+0Hz",
    "inicio_s": 0.0,          # no quadro 0
    "volume": 1.0,
}
ARQUIVO = "voz_gancho.wav"
REGISTRO = "voz_gancho.json"


def frase(lado1: str, lado2: str) -> str:
    """"Tactical Knives versus Kusarigama, who will win?"."""
    return f"{str(lado1).strip()} versus {str(lado2).strip()}, who will win?"


def config(bloco: dict | None) -> dict:
    saida = dict(PADRAO)
    saida.update({k: v for k, v in (bloco or {}).items() if v is not None})
    return saida


def _sintetizar_edge(texto: str, cfg: dict, cache: Path, log) -> Path | None:
    """O mp3 da frase pelo edge-tts (cache por hash, como o `voz.py`)."""
    cfg_voz = voz.config({"motor": "edge", "voz": cfg["voz"], "taxa": cfg["taxa"],
                          "tom": cfg["tom"]})
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    chave = voz._chave("edge", cfg_voz["voz"], cfg_voz["taxa"], cfg_voz["tom"], texto)
    destino = cache / f"{chave}.mp3"
    if destino.is_file() and not voz.motivo_do_cache_ruim(destino, texto, "edge"):
        return destino
    try:
        return voz._edge(texto, destino, cfg_voz)
    except voz.VozIndisponivel as erro:
        log(f"[voz do duelo] edge-tts indisponivel ({erro}); o duelo sai sem a voz")
        return None


def gerar(out_dir: Path, lado1: str, lado2: str, bloco: dict | None = None,
          taxa: int = 44100, cache: Path = voz.CACHE_PADRAO, log=print) -> Path | None:
    """Escreve ``voz_gancho.wav`` (a frase no ``inicio_s``) e o registro
    ``voz_gancho.json``; devolve o wav, ou None (sem a voz, o render segue).
    """
    cfg = config(bloco)
    out_dir = Path(out_dir)
    alvo, registro = out_dir / ARQUIVO, out_dir / REGISTRO
    if not cfg.get("ativa", True) or not (lado1 and lado2):
        alvo.unlink(missing_ok=True)
        return None
    if voz.np is None or not shutil.which("ffmpeg"):
        log("[voz do duelo] sem numpy/ffmpeg; o duelo sai sem a voz")
        return None
    texto = frase(lado1, lado2)
    mp3 = _sintetizar_edge(texto, cfg, cache, log)
    if mp3 is None:
        alvo.unlink(missing_ok=True)
        return None
    try:
        pcm = voz._pcm(mp3, taxa)
    except voz.VozIndisponivel as erro:
        log(f"[voz do duelo] {erro}; o duelo sai sem a voz")
        return None
    np = voz.np
    # O edge-tts abre com ~0,2 s de silencio (medido no duelo_00001: a voz
    # comecava aos 0,195 s). O `_pcm` so apara o FIM; o inicio sai aqui,
    # deixando 20 ms de ar, para a voz comecar no quadro 0 de verdade.
    acima = np.nonzero(np.abs(pcm) > 0.02)[0]
    if len(acima):
        pcm = pcm[max(0, int(acima[0]) - int(0.02 * taxa)):]
    inicio = max(0, int(float(cfg["inicio_s"]) * taxa))
    buf = np.zeros(inicio + len(pcm))
    buf[inicio:] = pcm
    pico = float(np.max(np.abs(buf))) if len(buf) else 0.0
    if pico > 1e-6:
        buf *= min(1.0, 0.92 / pico) * float(cfg.get("volume", 1.0))
    from ..video.trilha import gravar_wav
    gravar_wav(alvo, np.clip(buf, -1, 1), taxa)
    registro.write_text(json.dumps({
        "texto": texto, "voz": cfg["voz"], "taxa": cfg["taxa"], "motor": "edge-tts",
        "inicio_s": round(inicio / taxa, 3), "duracao_s": round(len(pcm) / taxa, 3),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return alvo


__all__ = ["ARQUIVO", "PADRAO", "REGISTRO", "VOZ_PADRAO", "config", "frase", "gerar"]
