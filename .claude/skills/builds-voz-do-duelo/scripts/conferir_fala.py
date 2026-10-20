# -*- coding: utf-8 -*-
"""Sintetiza UMA fala pelo caminho real (`builds.content.voz.sintetizar`) e mede.

    python .claude/skills/builds-voz-do-duelo/scripts/conferir_fala.py \
        "Sword versus Dagger. Who wins?" --voz en-US-GuyNeural --saida E:/tmp_pytest/voz

    python .claude/skills/builds-voz-do-duelo/scripts/conferir_fala.py --wav <arquivo.wav|mp3>

O cache vai para --saida (NUNCA o `random_builds/outputs/_voz_cache` de producao:
uma entrada ruim la e servida para sempre). Diz qual motor respondeu (edge ou a
reserva SAPI — a reserva e SILENCIOSA no render), a duracao, palavras/s e o
veredito de `voz.implausivel`, e conta os "pipocos" (corridas de zero exato de
5-120 ms no meio da fala, o defeito de 10/09/2026).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def pcm_mono(arquivo: Path, taxa: int = 44100):
    import numpy as np
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-i", str(arquivo), "-f", "s16le",
                            "-ac", "1", "-ar", str(taxa), "-"], capture_output=True,
                           timeout=120, creationflags=SEM_JANELA).stdout
    return np.frombuffer(bruto, dtype=np.int16), taxa


def pipocos(arquivo: Path) -> dict:
    """Corridas de zero EXATO entre 5 e 120 ms, so entre a 1a e a ultima amostra com som."""
    import numpy as np
    pcm, taxa = pcm_mono(arquivo)
    if pcm.size == 0:
        return {"erro": "audio vazio"}
    com_som = np.flatnonzero(pcm != 0)
    if com_som.size == 0:
        return {"duracao_s": round(pcm.size / taxa, 3), "pipocos": None, "erro": "tudo zero"}
    miolo = pcm[com_som[0]:com_som[-1] + 1]
    zero = np.concatenate(([0], (miolo == 0).astype(np.int8), [0]))
    bordas = np.flatnonzero(np.diff(zero))
    corridas = (bordas[1::2] - bordas[0::2]) / taxa
    n = int(((corridas >= 0.005) & (corridas <= 0.120)).sum())
    fala = miolo.size / taxa
    return {"duracao_s": round(pcm.size / taxa, 3), "fala_s": round(fala, 3),
            "pipocos_5_120ms": n, "pipocos_por_s": round(n / fala, 2) if fala else None}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("texto", nargs="?", default="")
    p.add_argument("--voz", default="", help="voz do edge-tts (ex.: en-US-GuyNeural); "
                                             "padrao: a do render.json")
    p.add_argument("--voz-sapi", default="", help="reserva do Windows (Maria, Zira, David)")
    p.add_argument("--saida", type=Path, default=Path(r"E:\tmp_pytest\voz_conferir"))
    p.add_argument("--wav", type=Path, help="so mede um audio que ja existe")
    a = p.parse_args(argv)

    if a.wav:
        print(json.dumps({"arquivo": str(a.wav), **pipocos(a.wav)}, ensure_ascii=False, indent=1))
        return 0
    if not a.texto:
        p.error("diga o texto (ou --wav)")

    from builds.content import voz
    render = Path(voz.RAIZ) / "config" / "render.json"
    cfg_render = json.loads(render.read_text(encoding="utf-8")).get("audio", {}).get("voz", {})
    cfg = voz.config(cfg_render)
    if a.voz:
        cfg["voz"] = a.voz
    if a.voz_sapi:
        cfg["voz_sapi"] = a.voz_sapi
    cache = a.saida / "_cache"
    texto = voz.falavel(a.texto)
    logs: list[str] = []
    try:
        arquivo = voz.sintetizar(texto, cfg, cache=cache, log=logs.append)
    except voz.VozIndisponivel as exc:
        print(json.dumps({"erro": f"os dois motores falharam: {exc}", "log": logs},
                         ensure_ascii=False, indent=1))
        return 1
    motor = "edge" if arquivo.suffix == ".mp3" else "sapi (RESERVA do Windows)"
    medida = pipocos(arquivo)
    duracao = medida.get("fala_s") or medida.get("duracao_s") or 0.0
    saida = {
        "texto_de_tela": a.texto, "texto_falado": texto,
        "falavel_mudou": texto.rstrip(".") != a.texto.rstrip("."),
        "motor": motor, "voz": cfg["voz"] if motor == "edge" else cfg["voz_sapi"],
        "arquivo": str(arquivo), "palavras": len(texto.split()),
        "palavras_por_s": voz.taxa_de_fala(texto, duracao),
        "implausivel": voz.implausivel(texto, duracao) or "",
        **medida, "log": logs,
    }
    print(json.dumps(saida, ensure_ascii=False, indent=1))
    return 0 if motor == "edge" else 3


if __name__ == "__main__":
    sys.exit(main())
