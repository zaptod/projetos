"""`main.py palco vitrine`: um video de REVISAO com as pecas da biblioteca
animadas (os 24 rostos, os eventos, os efeitos por tipo x elemento, o HUD e
as armas), pagina por pagina. Nao e luta e nao publica: sai em
outputs/_palco/vitrine/.

O Godot grava pela cena `res://ferramentas/vitrine.tscn` (as mesmas guardas do
palco: rc 3 sem --fixed-fps, rc 4 janela minimizada) e o ffmpeg comprime uma
vez, com uma faixa de audio muda (so para os players do celular). A
conferencia: h264 1080x1920, quadros = os do relatorio, nenhum quadro liso.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import checagens, config, godot
from .config import ErroPalco

CENA = "res://ferramentas/vitrine.tscn"


def gerar(saida: Path | None = None, *, so: str | None = None, cfg: dict | None = None) -> dict:
    cfg = config.carregar() if cfg is None else cfg
    saida = Path(saida or config.SAIDAS / "vitrine" / "vitrine.mp4").resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)
    trabalho = saida.parent / f"_{saida.stem}_trabalho"
    trabalho.mkdir(parents=True, exist_ok=True)
    relatorio = trabalho / "relatorio.json"
    relatorio.unlink(missing_ok=True)
    avi = trabalho / f"{saida.stem}.avi"
    avi.unlink(missing_ok=True)
    argumentos = [f"--relatorio={relatorio}"] + ([f"--so={so}"] if so else [])
    filme = godot.gravar_filme(None, avi, cfg=cfg, cena=CENA, argumentos=argumentos, timeout=600)
    (trabalho / "godot.log").write_text(filme["saida"], encoding="utf-8")
    try:
        rel = json.loads(relatorio.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rel = {}
    if filme["rc"] != 0 or not rel.get("ok"):
        raise ErroPalco(f"a vitrine falhou: {filme['motivo'] or 'relatorio sem ok'} "
                        f"({'; '.join(rel.get('avisos') or []) or filme['saida'][-1200:]})")
    enc = cfg.get("encode") or {}
    feito = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(avi), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-shortest", "-vf", "scale=out_range=tv,format=yuv420p", "-color_range", "tv",
         "-c:v", "libx264", "-preset", str(enc.get("preset", "medium")), "-crf", str(enc.get("crf", 18)),
         "-c:a", "aac", "-b:a", "96k", "-map", "0:v", "-map", "1:a", "-movflags", "+faststart", str(saida)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=checagens.SEM_JANELA)
    if feito.returncode != 0:
        raise ErroPalco(f"ffmpeg da vitrine falhou: {feito.stderr[-800:]}")
    info = checagens.sonda(saida)
    video = next((s for s in info.get("streams") or [] if s.get("codec_type") == "video"), {})
    problemas = []
    if (int(video.get("width", 0)), int(video.get("height", 0))) != (1080, 1920):
        problemas.append(f"resolucao {video.get('width')}x{video.get('height')}")
    if int(video.get("nb_frames") or 0) != int(rel["quadros"]):
        problemas.append(f"{video.get('nb_frames')} quadros no mp4, a vitrine fez {rel['quadros']}")
    lisos = checagens.quadros_lisos(saida, float(rel["duracao"]), amostras=6)
    if any(d < 2.0 for d in lisos):
        problemas.append(f"quadro liso: {lisos}")
    resumo = {"ok": not problemas, "problemas": problemas, "saida": str(saida), "quadros": rel.get("quadros"),
              "duracao": rel.get("duracao"), "paginas": rel.get("paginas"), "pecas": rel.get("pecas"),
              "reservas": rel.get("reservas"), "tempo": {"godot_s": filme["segundos"], "laco_ms": rel.get("laco_ms")},
              "desvio_luma": [round(d, 1) for d in lisos]}
    saida.with_suffix(".vitrine.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    if problemas:
        raise ErroPalco("a vitrine nao passou na conferencia: " + "; ".join(problemas))
    shutil.rmtree(trabalho, ignore_errors=True)
    return resumo
