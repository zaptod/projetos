# -*- coding: utf-8 -*-
"""Mede um mp4 de duelo/build e tira os quadros para OLHAR. So le o mp4.

    python .claude/skills/conferente-video-mp4/scripts/medir_video.py VIDEO.mp4 \
        --saida E:/tmp_pytest/conferente/<tarefa>

Grava em --saida: medida.json, quadro_<t>s.png, quadro_<t>s_zona.png (com a
zona das plataformas pintada) e folha.png (contato). Nada no repositorio, nada
no runtime: a guarda de audio e chamada pela regua SEM memoria
(`audio.medir`, nunca `medir_lembrado`, que grava em audio_medido.json).

Usa so ffmpeg/ffprobe e Pillow. Se `builds` importa, mede tambem pela regua
da publicacao (arquivo inteiro + cada trecho de luta do edit_plan.json).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

# Mesma constante do renderer (builds/video/renderer.py: ZONA_DAS_PLATAFORMAS).
ZONA_PADRAO = {"topo": 0.10, "baixo": 0.20, "direita": 0.12}
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _rodar(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=SEM_JANELA)


def sonda(mp4: Path) -> dict:
    r = _rodar(["ffprobe", "-v", "error", "-show_entries",
                "format=duration:stream=codec_type,width,height,r_frame_rate",
                "-of", "json", str(mp4)])
    dados = json.loads(r.stdout or "{}")
    video = next((s for s in dados.get("streams", []) if s.get("codec_type") == "video"), {})
    num, _, den = str(video.get("r_frame_rate", "0/1")).partition("/")
    return {
        "duracao_s": round(float(dados.get("format", {}).get("duration") or 0), 3),
        "largura": video.get("width"), "altura": video.get("height"),
        "fps": round(float(num) / float(den or 1), 3) if num else None,
        "tem_audio": any(s.get("codec_type") == "audio" for s in dados.get("streams", [])),
    }


def som(mp4: Path, duracao: float) -> dict:
    """Integrado (LUFS), pico verdadeiro (dBTP), silencios e congelados."""
    r = _rodar(["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4),
                "-af", "ebur128=peak=true,silencedetect=n=-40dB:d=0.3",
                "-vf", "freezedetect=n=0.001:d=0.3", "-f", "null", "-"])
    texto = r.stderr or ""
    resumo = texto[texto.rfind("Summary:"):] if "Summary:" in texto else ""
    integrado = re.search(r"I:\s+(-?[\d.]+) LUFS", resumo)
    pico = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", resumo)

    def pares(ini_re, fim_re):
        inicios = [float(x) for x in re.findall(ini_re, texto)]
        fins = [float(x) for x in re.findall(fim_re, texto)]
        saida = []
        for i, a in enumerate(inicios):
            b = fins[i] if i < len(fins) else duracao   # aberto ate o fim do arquivo
            saida.append([round(a, 2), round(b, 2)])
        return saida

    silencios = pares(r"silence_start: (-?[\d.]+)", r"silence_end: (-?[\d.]+)")
    congelados = pares(r"freeze_start: (-?[\d.]+)", r"freeze_end: (-?[\d.]+)")
    # Silencio final: so o bloco que fecha NO FIM do arquivo (o ffmpeg fecha o
    # ultimo bloco no EOF; "tem silence_end" nao quer dizer "acabou antes").
    final = next((round(duracao - a, 2) for a, b in silencios if b >= duracao - 0.05), 0.0)
    return {
        "lufs_integrado": float(integrado.group(1)) if integrado else None,
        "pico_verdadeiro_dbtp": (None if not pico else
                                 (float("-inf") if pico.group(1) == "-inf" else float(pico.group(1)))),
        "silencios_-40dB_0.3s": silencios,
        "silencio_final_s": final,
        "congelados_0.001_0.3s": congelados,
    }


def regua_da_publicacao(mp4: Path) -> dict:
    """O que a guarda de audio da publicacao diria, sem gravar a memoria dela."""
    try:
        from builds.publicar import audio
    except Exception as exc:  # noqa: BLE001
        return {"erro": f"builds nao importa: {exc}"}
    perfil = "celular" if "celular" in mp4.stem else "normal"
    video = SimpleNamespace(caminho=mp4, perfil=perfil)
    inteiro = audio.medir(mp4)
    luta = audio.luta_muda(video, medir=lambda t: audio.medir(t, fracao=False))
    trechos = audio.trechos_de_luta(video)
    return {"arquivo_inteiro": inteiro, "luta": luta,
            "trechos_de_luta": [str(t.name) for t in (trechos or [])],
            "leitura": "'' = tem som; texto = barra; None = nao mediu"}


def quadros(mp4: Path, saida: Path, tempos: list[float], zona: dict) -> list[str]:
    from PIL import Image, ImageDraw
    feitos = []
    for t in tempos:
        png = saida / f"quadro_{t:06.2f}s.png"
        _rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4),
                "-frames:v", "1", str(png)], timeout=120)
        if not png.is_file():
            continue
        feitos.append(png.name)
        img = Image.open(png).convert("RGBA")
        w, h = img.size
        camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        vermelho = (255, 0, 64, 90)
        d.rectangle([0, 0, w, int(h * zona["topo"])], fill=vermelho)
        d.rectangle([0, int(h * (1 - zona["baixo"])), w, h], fill=vermelho)
        d.rectangle([int(w * (1 - zona["direita"])), 0, w, h], fill=vermelho)
        Image.alpha_composite(img, camada).convert("RGB").save(
            saida / png.name.replace(".png", "_zona.png"))
    return feitos


def folha(saida: Path, nomes: list[str], colunas: int = 4, largura: int = 270) -> str | None:
    from PIL import Image
    imgs = [Image.open(saida / n).convert("RGB") for n in nomes]
    if not imgs:
        return None
    escala = largura / imgs[0].width
    alto = int(imgs[0].height * escala)
    linhas = (len(imgs) + colunas - 1) // colunas
    tela = Image.new("RGB", (colunas * largura, linhas * alto), (0, 160, 0))  # fundo de contraste
    for i, img in enumerate(imgs):
        tela.paste(img.resize((largura, alto)), ((i % colunas) * largura, (i // colunas) * alto))
    tela.save(saida / "folha.png")
    return "folha.png"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mp4", type=Path)
    p.add_argument("--saida", type=Path, required=True,
                   help="pasta das capturas (fora do repo: E:/tmp_pytest/conferente/...)")
    p.add_argument("--tempos", default="",
                   help="segundos separados por virgula; padrao: 0, 1, 1/4, 1/2, 3/4, fim-0,3")
    a = p.parse_args(argv)
    if not a.mp4.is_file():
        print(f"nao existe: {a.mp4}")
        return 2
    a.saida.mkdir(parents=True, exist_ok=True)
    info = sonda(a.mp4)
    d = info["duracao_s"]
    tempos = ([float(x) for x in a.tempos.split(",") if x.strip()] if a.tempos else
              sorted({0.0, min(1.0, d), round(d / 4, 2), round(d / 2, 2),
                      # fim-0,3: com -ss a 0,1 s do fim o ffmpeg nao devolve quadro
                      round(3 * d / 4, 2), max(0.0, round(d - 0.3, 2))}))
    medida = {"mp4": str(a.mp4), **info, **som(a.mp4, d),
              "regua_da_publicacao": regua_da_publicacao(a.mp4),
              "zona_das_plataformas": ZONA_PADRAO}
    medida["quadros"] = quadros(a.mp4, a.saida, tempos, ZONA_PADRAO)
    medida["folha"] = folha(a.saida, medida["quadros"])
    (a.saida / "medida.json").write_text(json.dumps(medida, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps(medida, ensure_ascii=False, indent=1))
    print(f"\nOLHE: {a.saida / 'folha.png'} e cada quadro_*_zona.png (Read na imagem).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
