"""A/B: a MESMA luta no visual de hoje e no palco, lado a lado, para ver E
ouvir.

Um arquivo so, em duas passadas: a primeira com o som do lado esquerdo (o de
HOJE), a segunda com o som do lado direito (o PALCO). A moldura amarela marca
de quem e o som que esta tocando. As duas metades tem o mesmo tempo porque
sao a mesma seed, a mesma arena e o mesmo corte de tedio; a mais curta
congela no ultimo quadro ate a outra acabar.

Nada disto entra no catalogo: mora em outputs/_palco/.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import checagens
from .config import ErroPalco

FONTE = "C\\:/Windows/Fonts/arialbd.ttf"


def _duracao(caminho: Path) -> float:
    info = checagens.sonda(caminho)
    return float((info.get("format") or {}).get("duration") or 0.0)


def _tem_audio(caminho: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in checagens.sonda(caminho).get("streams") or [])


def lado_a_lado(esquerda: Path, direita: Path, saida: Path, *, rotulos=("HOJE", "PALCO 16D"),
                largura: int = 540, altura: int = 960) -> Path:
    esquerda, direita, saida = Path(esquerda), Path(direita), Path(saida)
    duracao = max(_duracao(esquerda), _duracao(direita))
    if duracao <= 0:
        raise ErroPalco("A/B: nao consegui ler a duracao dos dois videos")
    entradas = ["-i", str(esquerda), "-i", str(direita)]
    audios = []
    for k, arquivo in enumerate((esquerda, direita)):
        if _tem_audio(arquivo):
            audios.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{duracao:.3f}[a{k}]")
        else:
            audios.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{duracao:.3f}[a{k}]")

    def texto(t: str, x: str, y: str, tam: int) -> str:
        return (f"drawtext=fontfile='{FONTE}':text='{t}':x={x}:y={y}:fontsize={tam}:fontcolor=white:"
                "borderw=4:bordercolor=black")

    filtro = ";".join([
        f"[0:v]scale={largura}:{altura}:force_original_aspect_ratio=decrease,pad={largura}:{altura}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={duracao:.3f},trim=0:{duracao:.3f},"
        f"{texto(rotulos[0], '(w-text_w)/2', '24', 40)}[e]",
        f"[1:v]scale={largura}:{altura}:force_original_aspect_ratio=decrease,pad={largura}:{altura}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={duracao:.3f},trim=0:{duracao:.3f},"
        f"{texto(rotulos[1], '(w-text_w)/2', '24', 40)}[d]",
        "[e][d]hstack=inputs=2,setpts=PTS-STARTPTS,split=2[s1][s2]",
        f"[s1]drawbox=x=0:y=0:w={largura}:h={altura}:color=yellow@0.9:t=10,"
        # sem ':' no texto: no filtergraph ele separa opcoes
        f"{texto('OUVINDO ' + rotulos[0], '(w-text_w)/2', 'h-90', 44)}[v1]",
        f"[s2]drawbox=x={largura}:y=0:w={largura}:h={altura}:color=yellow@0.9:t=10,"
        f"{texto('OUVINDO ' + rotulos[1], '(w-text_w)/2', 'h-90', 44)}[v2]",
        *audios,
        "[v1][a0][v2][a1]concat=n=2:v=1:a=1[v][a]",
    ])
    saida.parent.mkdir(parents=True, exist_ok=True)
    comando = ["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(saida)]
    feito = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=checagens.SEM_JANELA)
    if feito.returncode != 0:
        raise ErroPalco(f"A/B: ffmpeg falhou: {feito.stderr[-900:]}")
    return saida


def quadro(ab: Path, png: Path, t: float) -> Path:
    """Um quadro do A/B (da primeira passada) para olhar sem abrir o video."""
    feito = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(ab), "-frames:v", "1",
                            str(png)], capture_output=True, text=True, creationflags=checagens.SEM_JANELA)
    if feito.returncode != 0:
        raise ErroPalco(f"A/B: nao extraí o quadro: {feito.stderr[-400:]}")
    return png
