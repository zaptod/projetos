"""Timeline -> mp4 conferido, pelo palco.

    renderizar(timeline, saida)

1. monta o job: a timeline, os arquivos de som resolvidos AGORA pela cadeia do
   jogo, o estilo e o relatorio que o Godot escreve;
2. o Godot grava o AVI (MJPEG 0,95 + PCM 48 kHz, video e audio sincronizados
   pelo Movie Maker);
3. UMA compressao so: h264 crf 18 + aac 192k, com o nivel do trecho de luta
   levado a -18 LUFS (o nivel da luta na mistura da 16A) e pico limitado;
4. o AVI e apagado e o mp4 e CONFERIDO (checagens.conferir). Qualquer
   problema e ErroPalco: nada sai com rc 0 calado.

O resumo (tempos, pecas usadas, sons, medidas) fica em `<saida>.palco.json`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from . import checagens, config, godot, plano, sons
from .config import ErroPalco


def carregar_timeline(caminho: Path) -> dict:
    caminho = Path(caminho)
    try:
        from neural_fights.recording import timeline_arquivo
    except ImportError:
        timeline_arquivo = None
    if timeline_arquivo is not None:
        return timeline_arquivo.carregar(caminho)
    return json.loads(caminho.read_text(encoding="utf-8"))


def _ler_json(caminho: Path) -> dict:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def renderizar(timeline, saida, *, estilo: dict | None = None, hud: bool = False,
               quadros: int | None = None, remapeamento: list | None = None,
               sons_da_luta: list | None = None, cfg: dict | None = None,
               manter_avi: bool = False) -> dict:
    cfg = config.carregar() if cfg is None else cfg
    timeline, saida = Path(timeline).resolve(), Path(saida).resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)
    doc = carregar_timeline(timeline)

    itens = sons_da_luta
    origem_sons = "job"
    if itens is None:
        itens = ((doc.get("sons") or {}).get("itens") or []) if isinstance(doc.get("sons"), dict) else []
        origem_sons = "timeline (16A: o que o jogo tocou)"
        if not itens:
            itens = sons.sons_dos_eventos(doc)
            origem_sons = "eventos (reserva: a timeline nao tem a secao sons)"
            sons_da_luta = itens
    arquivos = sons.arquivos_de_som(s.get("id") for s in itens)

    trabalho = saida.parent / f"_{saida.stem}_trabalho"
    trabalho.mkdir(parents=True, exist_ok=True)
    relatorio = trabalho / "relatorio_godot.json"
    relatorio.unlink(missing_ok=True)
    job = {"timeline": str(timeline), "relatorio": str(relatorio), "sons_arquivos": arquivos,
           "estilo": dict(estilo or {}), "hud": bool(hud)}
    if quadros:
        job["quadros"] = int(quadros)
    if remapeamento is not None:
        job["remapeamento"] = {"relogio": "gravacao", "trechos": [list(t) for t in remapeamento]}
    if sons_da_luta is not None:
        job["sons"] = sons_da_luta
    arquivo_job = trabalho / "job.json"
    arquivo_job.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")

    avi = trabalho / f"{saida.stem}.avi"
    avi.unlink(missing_ok=True)
    # Prazo pelo tamanho da luta, e nao um teto fixo: medido 42-58 s de Godot
    # para 25 s de video com a maquina cheia. Um palco que nao encerra (o loop
    # de previa, 28/09: 1,1 GB de AVI em 10 min para um video de 2 s) morre
    # aqui em minutos, nao em quinze.
    remap_job = job.get("remapeamento") or doc.get("remapeamento")
    parados_py = plano.quadros_de_hitstop(doc, plano.hitstop_do_estilo(config.projeto(cfg), job["estilo"]), remap_job)
    duracao_video = (plano.quadros(int(doc["n"]) / int(doc["hz"]), remap_job) + parados_py) / 30.0
    prazo = min(float(cfg.get("timeout_s", 900)), 90.0 + 8.0 * duracao_video)
    filme = godot.gravar_filme(arquivo_job, avi, cfg=cfg, timeout=prazo)
    (trabalho / "godot.log").write_text(filme["saida"], encoding="utf-8")
    rel = _ler_json(relatorio)
    if filme["rc"] != 0 or not rel.get("ok"):
        avisos = "; ".join(rel.get("avisos") or []) or filme["saida"][-1200:]
        raise ErroPalco(f"o palco falhou: {filme['motivo'] or 'relatorio sem ok'} ({avisos})")
    if not avi.is_file() or avi.stat().st_size == 0:
        raise ErroPalco(f"o Godot saiu 0 mas o AVI nao existe: {avi}")

    som_cfg = cfg.get("som") or {}
    ganho, lufs_avi = checagens.ganho_para_alvo(avi, alvo_lufs=float(som_cfg.get("alvo_lufs", -18.0)),
                                                ganho_max_db=float(som_cfg.get("ganho_max_db", 18.0)))
    limite = 10 ** (float(som_cfg.get("pico_db", -1.0)) / 20.0)
    enc = cfg.get("encode") or {}
    inicio = time.time()
    comando = ["ffmpeg", "-v", "error", "-y", "-i", str(avi),
               "-vf", "scale=out_range=tv,format=yuv420p", "-color_range", "tv",
               "-c:v", "libx264", "-preset", str(enc.get("preset", "medium")), "-crf", str(enc.get("crf", 18)),
               "-af", f"volume={ganho:.2f}dB,alimiter=limit={limite:.4f}:level=false",
               "-c:a", "aac", "-b:a", f"{int(enc.get('audio_kbps', 192))}k", "-ar", "48000",
               "-movflags", "+faststart", str(saida)]
    comprimir = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               creationflags=checagens.SEM_JANELA)
    segundos_encode = round(time.time() - inicio, 1)
    if comprimir.returncode != 0:
        raise ErroPalco(f"ffmpeg falhou ({comprimir.returncode}): {comprimir.stderr[-800:]}")
    tamanho_avi = avi.stat().st_size
    if not manter_avi:
        avi.unlink(missing_ok=True)

    fps = int(rel.get("fps", cfg.get("fps", 30)))
    largura, altura = (int(v) for v in rel.get("tela", [1080, 1920]))
    problemas, medidas = checagens.conferir(
        saida, quadros=int(rel["quadros"]), fps=fps, largura=largura, altura=altura,
        piso_lufs=float((cfg.get("checagens") or {}).get("piso_lufs", -40.0)),
        piso_media_db=float((cfg.get("checagens") or {}).get("piso_media_db", -45.0)))
    # a conta dos quadros tambem em Python: o Godot nao confere a si mesmo
    remap_usado = job.get("remapeamento") or doc.get("remapeamento")
    esperado = plano.quadros(int(doc["n"]) / int(doc["hz"]), remap_usado, fps)
    parados = int((rel.get("plano") or {}).get("quadros_de_hitstop") or 0)
    if parados != parados_py:
        problemas.append(f"hitstop do render: o Python conta {parados_py} quadros parados, o Godot {parados}")
    if not quadros and esperado + parados_py != int(rel["quadros"]):
        problemas.append(f"o plano em Python da {esperado} + {parados_py} quadros, o Godot fez {rel['quadros']}")
    sons_rel = rel.get("sons") or {}
    minimo = int((cfg.get("checagens") or {}).get("min_ids_distintos", 1))
    if int(sons_rel.get("ids_distintos") or 0) < minimo:
        problemas.append(f"so {sons_rel.get('ids_distintos')} som(ns) distinto(s) tocado(s), minimo {minimo}")
    if sons_rel.get("faltando"):
        problemas.append(f"sons sem arquivo: {sorted(sons_rel['faltando'])}")

    resumo = {
        "ok": not problemas, "problemas": problemas, "saida": str(saida), "timeline": str(timeline),
        "quadros": rel.get("quadros"), "duracao": rel.get("duracao"), "sons_origem": origem_sons,
        "hitstop": {"quadros": parados_py, "segundos": round(parados_py / fps, 3),
                    "sem_hitstop_s": round(esperado / fps, 3)},
        "sons": sons_rel, "eventos": rel.get("eventos"), "pecas": rel.get("pecas"),
        "reservas": rel.get("reservas"), "avisos_godot": rel.get("avisos"),
        "tempo": {"godot_s": filme["segundos"], "laco_godot_ms": rel.get("laco_ms"), "encode_s": segundos_encode},
        "avi_mb": round(tamanho_avi / 2 ** 20, 1),
        "nivel": {"lufs_antes": lufs_avi, "ganho_db": round(ganho, 2)}, "medidas": medidas,
        "video": rel.get("video"), "comando": filme["comando"],
    }
    saida.with_suffix(".palco.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=str),
                                                encoding="utf-8")
    if problemas:
        raise ErroPalco("o mp4 do palco nao passou na conferencia: " + "; ".join(problemas))
    if not manter_avi:
        shutil.rmtree(trabalho, ignore_errors=True)
    return resumo
