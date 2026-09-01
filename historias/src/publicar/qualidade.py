# -*- coding: utf-8 -*-
"""O que impede uma parte de ir ao ar — conferido no ARQUIVO, nao no plano.

"Publicar com um clique" so e seguro se algo olhar o mp4 antes. Um roteiro
perfeito nao garante video bom: a imagem pode ter faltado, a voz pode nao ter
sido sintetizada (sem rede), o render pode ter saido mudo, e nada disso
levanta excecao — o arquivo existe do mesmo jeito.

Entao cada parte passa por uma vistoria antes do upload:

    ERRO    nao publica. Video sem audio, sem imagem nenhuma, curto demais.
    AVISO   publica, mas voce fica sabendo. Cena sem imagem, audio baixo.

Tudo medido com ffprobe/ffmpeg, que ja sao dependencia do render.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Faixas de um vertical publicavel. Fora disto nao e "estilo": e defeito.
DURACAO_MINIMA = 8.0
DURACAO_MAXIMA = 180.0
# As plataformas normalizam para perto de -14 LUFS; abaixo de -30 dB de media
# o video esta praticamente mudo no celular (foi o diagnostico do outro canal).
MEDIA_MINIMA_DB = -30.0
BYTES_MINIMOS = 100_000


def _ffprobe(caminho: Path) -> dict:
    try:
        saida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:stream=codec_type,codec_name",
             "-of", "json", str(caminho)],
            capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
        return json.loads(saida.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def _volume(caminho: Path) -> float | None:
    try:
        saida = subprocess.run(
            ["ffmpeg", "-i", str(caminho), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=180, creationflags=NO_WINDOW)
        for linha in (saida.stderr or "").splitlines():
            if "mean_volume:" in linha:
                return float(linha.split("mean_volume:")[1].split("dB")[0].strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def vistoriar_arquivo(caminho: Path) -> dict:
    """O que o mp4 tem de fato: duracao, faixas e nivel de audio."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return {"existe": False, "erros": [f"{caminho.name} nao existe"],
                "avisos": []}
    dados = _ffprobe(caminho)
    fluxos = dados.get("streams") or []
    duracao = float((dados.get("format") or {}).get("duration") or 0.0)
    tem_video = any(f.get("codec_type") == "video" for f in fluxos)
    tem_audio = any(f.get("codec_type") == "audio" for f in fluxos)
    tamanho = caminho.stat().st_size

    erros, avisos = [], []
    if tamanho < BYTES_MINIMOS:
        erros.append(f"arquivo de {tamanho / 1000:.0f} KB: render interrompido")
    if not tem_video:
        erros.append("sem faixa de video")
    if not tem_audio:
        erros.append("sem faixa de audio: o video vai ao ar mudo")
    if duracao < DURACAO_MINIMA:
        erros.append(f"{duracao:.1f}s e curto demais para uma historia")
    elif duracao > DURACAO_MAXIMA:
        avisos.append(f"{duracao:.0f}s: longo para um Short/Reel")

    media = _volume(caminho) if tem_audio else None
    if media is not None and media < MEDIA_MINIMA_DB:
        erros.append(f"audio a {media:.1f} dB de media: praticamente mudo")

    return {"existe": True, "duracao": round(duracao, 2), "bytes": tamanho,
            "audio": tem_audio, "video": tem_video, "media_db": media,
            "erros": erros, "avisos": avisos}


def vistoriar_parte(historia_id: str, parte: int, caminho: Path,
                    roteiro: dict | None = None) -> dict:
    """A vistoria do arquivo MAIS o que so o roteiro sabe dizer."""
    from ..imagens import fila
    from ..roteiro import roteiro as R

    roteiro = roteiro or R.carregar(historia_id)
    laudo = vistoriar_arquivo(caminho)
    imagens = fila.resumo(historia_id, roteiro, parte)
    if imagens["total"] and imagens["prontas"] == 0:
        laudo["erros"].append(
            "nenhuma cena tem imagem: o video inteiro e cartao de texto")
    elif imagens["faltam"]:
        laudo["avisos"].append(
            f"{imagens['faltam']} de {imagens['total']} cena(s) sem imagem")

    # O mp4 mais velho que a ultima imagem = a imagem nova nao entrou nele.
    novas = [l["arquivo"] for l in fila.estado(historia_id, roteiro, parte)
             if l["pronta"]]
    if novas and laudo.get("existe"):
        mais_nova = max(a.stat().st_mtime for a in novas)
        if Path(caminho).stat().st_mtime + 5 < mais_nova:
            laudo["erros"].append(
                "imagem mais nova que o video: re-renderize antes de publicar")

    laudo.update({"parte": parte, "imagens": imagens,
                  "titulo": R.titulo_da_parte(roteiro, parte),
                  "ok": not laudo["erros"]})
    return laudo


def vistoriar_serie(historia_id: str, videos: list) -> dict:
    """Vistoria de todas as partes prontas. `videos` sao os do catalogo."""
    from ..roteiro import roteiro as R
    roteiro = R.carregar(historia_id)
    partes = [vistoriar_parte(historia_id, v.parte, v.caminho, roteiro)
              for v in videos]
    esperadas = len(roteiro["partes"])
    faltando = sorted({p["n"] for p in roteiro["partes"]}
                      - {v.parte for v in videos})
    resumo = {
        "historia_id": historia_id, "titulo": roteiro.get("titulo", ""),
        "partes": partes, "esperadas": esperadas,
        "prontas": len(videos), "faltando": faltando,
        "erros": [f"parte {p['parte']}: {e}" for p in partes for e in p["erros"]],
        "avisos": [f"parte {p['parte']}: {a}" for p in partes for a in p["avisos"]],
    }
    if faltando:
        resumo["erros"].insert(
            0, f"faltam os videos da(s) parte(s) {', '.join(map(str, faltando))}")
    resumo["ok"] = not resumo["erros"]
    return resumo
