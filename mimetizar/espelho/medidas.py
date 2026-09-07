# -*- coding: utf-8 -*-
"""Etapa 2b: os numeros do video, sem IA nenhuma.

Um LLM olhando um video diz "o corte e agil". O ffmpeg diz "4,2 cortes por
minuto". Toda a autoridade da biblia vem daqui: cada afirmacao dela precisa
ter numero ou timestamp atras, senao e texto generico sobre YouTube.

Quatro passadas, e a ordem e por custo:

  SONDA     ffprobe: duracao, resolucao, fps, se ha audio.   instantaneo
  AUDIO     silencio + loudness numa passada so.             rapido
  COR       um pixel por keyframe (`-skip_frame nokey`).     rapido
  CORTES    deteccao de cena em 320px de largura.            CARO

A deteccao de cena e a unica que decodifica o video inteiro, e e por isso que
existe `amostra_s` na configuracao: num acervo de 300 videos, limitar aos
primeiros minutos troca precisao por uma noite de diferenca.

Nada de `metadata=print:file=...` para colher os resultados: aquele filtro
recebe um CAMINHO dentro da string do filtro, e caminho do Windows tem `\\` e
`:` — os dois caracteres que a sintaxe de filtro do ffmpeg usa como escape.
Aqui se le `showinfo` no stderr, que nao precisa de caminho nenhum.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import baixar as _baixar
from . import canal as _canal
from . import config, estado, ffmpeg

# `pts_time:41.234` nas linhas do showinfo — o instante de cada corte.
_TEMPO = re.compile(r"pts_time:\s*([\d.]+)")
# `I:  -14.2 LUFS` no resumo do ebur128. O `^\s*I:` evita casar com o
# `Threshold:` que vem logo abaixo com o mesmo sufixo.
_LUFS = re.compile(r"^\s*I:\s*(-?[\d.]+)\s*LUFS", re.M)
_LRA = re.compile(r"^\s*LRA:\s*(-?[\d.]+)\s*LU", re.M)
_SILENCIO = re.compile(r"silence_duration:\s*([\d.]+)")


class NaoMediu(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


def _limite(cfg: dict) -> list:
    """`-t N` quando a configuracao pede so um pedaco do video."""
    amostra = float(cfg.get("amostra_s") or 0)
    return ["-t", str(amostra)] if amostra > 0 else []


def cortes(caminho: Path, cfg: dict) -> dict:
    """Os instantes de troca de plano, e a taxa por minuto."""
    limiar = float(cfg.get("cena_limiar") or 0.30)
    largura = int(cfg.get("cena_largura") or 320)
    codigo, _saida, erro = ffmpeg.ffmpeg(
        ["-nostats"] + _limite(cfg) + [
            "-i", str(caminho), "-an", "-sn",
            "-vf", f"scale={largura}:-2,select='gt(scene,{limiar})',showinfo",
            "-f", "null", "-"],
        timeout=float(cfg.get("timeout_por_video_s") or 3600))
    if codigo not in (0, 124):
        raise NaoMediu(f"a deteccao de cena falhou: {erro.strip()[-300:]}")
    brutos = [round(float(t), 2) for t in _TEMPO.findall(erro)]
    instantes = _juntar_transicoes(brutos, float(cfg.get("corte_min_s") or 0.4))
    return {"cortes": len(instantes), "instantes": instantes,
            "deteccoes_cruas": len(brutos), "parcial": codigo == 124}


def _juntar_transicoes(instantes: list, minimo: float = 0.4) -> list:
    """Deteccoes coladas sao UM corte, nao varios.

    Um dissolve, um whip pan ou um flash faz vários frames seguidos passarem
    do limiar de cena, e cada um vira uma linha do showinfo. Medido num video
    real: cinco "cortes" dentro do segundo 57, que eram uma transicao so.
    Contar cru inflava `cortes_por_min` — o numero em que a biblia mais se
    apoia — em quase um terco.

    O minimo e o menor plano que um humano percebe como plano. Abaixo disso
    e transicao, nao troca de cena.
    """
    juntos = []
    for instante in sorted(instantes):
        if juntos and instante - juntos[-1] < minimo:
            continue
        juntos.append(instante)
    return juntos


def audio(caminho: Path, cfg: dict) -> dict:
    """Silencio e loudness numa passada so — os dois leem o mesmo audio."""
    db = float(cfg.get("silencio_db") or -35)
    minimo = float(cfg.get("silencio_min_s") or 0.35)
    codigo, _saida, erro = ffmpeg.ffmpeg(
        ["-nostats"] + _limite(cfg) + [
            "-i", str(caminho), "-vn", "-sn",
            "-af", f"silencedetect=noise={db}dB:d={minimo},ebur128",
            "-f", "null", "-"],
        timeout=float(cfg.get("timeout_por_video_s") or 3600))
    if codigo not in (0, 124):
        return {"tem_audio": False, "erro": erro.strip()[-200:]}
    silencios = [float(s) for s in _SILENCIO.findall(erro)]
    lufs = _LUFS.findall(erro)
    lra = _LRA.findall(erro)
    return {
        "tem_audio": True,
        "lufs": float(lufs[-1]) if lufs else None,
        "faixa_lu": float(lra[-1]) if lra else None,
        "silencio_s": round(sum(silencios), 2),
        "pausas": len(silencios),
    }


def cor(caminho: Path, cfg: dict) -> dict:
    """A paleta media, amostrada um pixel por keyframe.

    `-skip_frame nokey` decodifica so os keyframes — e o que torna esta
    passada barata. Para cor media e brilho, keyframe e amostra honesta: eles
    sao espalhados pelo video e nao privilegiam nenhum tipo de plano.
    """
    codigo, bruto, erro = ffmpeg.ffmpeg_binario(
        ["-nostats", "-skip_frame", "nokey"] + _limite(cfg) + [
            "-i", str(caminho), "-an", "-sn", "-vf", "scale=1:1",
            # Sem `passthrough` o muxer DUPLICA frames para manter taxa
            # constante, e os keyframes esparsos voltam como o video inteiro:
            # medido, um clipe de 2047 frames devolvia 2069 "amostras". A
            # contagem errada e o que espaca o mosaico de contato.
            "-fps_mode", "passthrough",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        timeout=float(cfg.get("timeout_por_video_s") or 3600))
    if codigo not in (0, 124) or len(bruto) < 3:
        return {"amostras": 0, "erro": (erro or "").strip()[-200:]}

    amostras = [tuple(bruto[i:i + 3]) for i in range(0, len(bruto) - 2, 3)]
    total = len(amostras)
    medio = [round(sum(p[c] for p in amostras) / total, 1) for c in range(3)]
    # Brilho perceptual (Rec. 601): o olho pesa verde muito mais que azul.
    brilho = round(0.299 * medio[0] + 0.587 * medio[1] + 0.114 * medio[2], 1)
    saturacoes = [(max(p) - min(p)) / 255.0 for p in amostras]
    return {
        "amostras": total,
        "rgb_medio": medio,
        "brilho": brilho,
        "saturacao": round(sum(saturacoes) / total, 3),
        # Quente = mais vermelho que azul. Diz mais sobre a correcao de cor do
        # canal do que o RGB cru, e e comparavel entre videos.
        "temperatura": round((medio[0] - medio[2]) / 255.0, 3),
        "escuro": brilho < 60,
    }


def contato(caminho: Path, destino: Path, cfg: dict, *,
            keyframes: int = 0) -> Path | None:
    """O mosaico de frames que sobe no chat. Um JPG por video.

    Espalha pelo video com `framestep` em vez de `select=mod(n,K)`: aquele
    exige uma virgula ESCAPADA dentro da string do filtro, e barra invertida
    em fonte deste repositorio ja quebrou codigo em silencio antes.
    """
    colunas = int(cfg.get("contato_colunas") or 4)
    linhas = int(cfg.get("contato_linhas") or 4)
    quadros = max(1, colunas * linhas)
    passo = max(1, keyframes // quadros) if keyframes else 1
    largura = int(cfg.get("contato_largura") or 320)

    destino.parent.mkdir(parents=True, exist_ok=True)
    codigo, _saida, erro = ffmpeg.ffmpeg(
        ["-nostats", "-skip_frame", "nokey"] + _limite(cfg) + [
            "-i", str(caminho), "-an", "-sn",
            "-fps_mode", "passthrough",
            "-vf", (f"framestep=step={passo},scale={largura}:-2,"
                    f"tile={colunas}x{linhas}"),
            "-frames:v", "1", "-q:v", str(int(cfg.get("contato_qualidade") or 4)),
            "-y", str(destino)],
        timeout=float(cfg.get("timeout_por_video_s") or 3600))
    if codigo not in (0, 124) or not destino.is_file():
        return None
    return destino


def medir_video(caminho: Path, *, cfg: dict | None = None,
                contato_em: Path | None = None) -> dict:
    """Todas as passadas num video. Devolve o dicionario que vira JSON."""
    cfg = cfg or config.carregar("medidas")
    sonda = ffmpeg.sondar(caminho)
    som = audio(caminho, cfg)
    paleta = cor(caminho, cfg)
    planos = cortes(caminho, cfg)

    analisado = min(float(cfg.get("amostra_s") or 0) or sonda["duracao_s"],
                    sonda["duracao_s"])
    minutos = max(analisado / 60.0, 1e-6)
    medida = {
        "arquivo": caminho.name,
        "analisado_s": round(analisado, 2),
        "amostra_parcial": analisado < sonda["duracao_s"] - 0.5,
        **sonda,
        "audio": som,
        "cor": paleta,
        "cortes": planos["cortes"],
        # Quantas vezes o ffmpeg passou do limiar antes de juntar transicoes.
        # Fica gravado porque a diferenca entre os dois numeros e a medida de
        # quanto o canal usa dissolve/flash em vez de corte seco.
        "deteccoes_cruas": planos.get("deteccoes_cruas", planos["cortes"]),
        "cortes_por_min": round(planos["cortes"] / minutos, 2),
        "plano_medio_s": round(analisado / (planos["cortes"] + 1), 2),
        "instantes_de_corte": planos["instantes"][:400],
    }
    if som.get("tem_audio") and som.get("silencio_s") is not None:
        medida["silencio_pct"] = round(100.0 * som["silencio_s"] / analisado, 1)
        medida["fala_pct"] = round(100.0 - medida["silencio_pct"], 1)
    if contato_em is not None:
        folha = contato(caminho, contato_em, cfg,
                        keyframes=paleta.get("amostras", 0))
        medida["contato"] = str(folha) if folha else ""
    return medida


def medir(canal_id: str, *, limite: int = 0, refazer: bool = False,
          log=print) -> dict:
    """Mede o que ja esta em disco e ainda nao foi medido."""
    ffmpeg.exigir()
    pasta = config.pasta_do_canal(canal_id)
    cfg = config.carregar("medidas")
    destino = pasta / "medidas"
    destino.mkdir(parents=True, exist_ok=True)
    folhas = pasta / "contatos"

    catalogo = {v["id"]: v for v in _canal.videos(pasta)}
    prontos = _baixar.baixados(pasta)
    alvos = [vid for vid in catalogo if vid in prontos]
    if not refazer:
        alvos = [vid for vid in alvos if not (destino / f"{vid}.json").is_file()]
    if limite and limite > 0:
        alvos = alvos[:limite]

    if not alvos:
        log("[medir] nada a medir — tudo que esta em disco ja foi medido.")
        return {"medidos": 0, "falharam": 0, "total": len(prontos)}

    log(f"[medir] {len(alvos)} video(s) a medir "
        f"(de {len(prontos)} em disco).")
    if not cfg.get("amostra_s"):
        log("[medir] a deteccao de cena le o video inteiro; conte alguns "
            "minutos por hora de video. `amostra_s` em config/medidas.json "
            "limita isso.")

    medidos, falharam = 0, []
    for ordem, video_id in enumerate(alvos, 1):
        arquivo = _baixar.video_de(pasta, video_id)
        titulo = (catalogo.get(video_id) or {}).get("titulo", "")[:52]
        if arquivo is None:
            falharam.append((video_id, "sem arquivo de video na pasta"))
            continue
        log(f"[medir] {ordem}/{len(alvos)}  {video_id}  {titulo}")
        try:
            medida = medir_video(arquivo, cfg=cfg,
                                 contato_em=folhas / f"{video_id}.jpg")
        except (ffmpeg.NaoMediu, NaoMediu, ffmpeg.SemFerramenta) as exc:
            log(f"           ! {exc}")
            falharam.append((video_id, str(exc)))
            continue
        medida["video_id"] = video_id
        medida["titulo"] = (catalogo.get(video_id) or {}).get("titulo", "")
        (destino / f"{video_id}.json").write_text(
            json.dumps(medida, ensure_ascii=False, indent=2), encoding="utf-8")
        medidos += 1
        log(f"           {medida['cortes_por_min']:.1f} cortes/min · "
            f"{medida['duracao_s'] / 60:.1f}min · "
            f"{medida['audio'].get('lufs') or 0:.1f} LUFS · "
            f"{medida.get('fala_pct', 0):.0f}% fala")

    estado.marcar(pasta, "medir", medidos=medidos, falharam=len(falharam))
    if falharam:
        log(f"\n[medir] {len(falharam)} falharam:")
        for video_id, motivo in falharam[:8]:
            log(f"    {video_id}: {motivo[:110]}")
    return {"medidos": medidos, "falharam": len(falharam),
            "total": len(prontos)}


def carregar(pasta: Path, video_id: str) -> dict:
    """A medida gravada daquele video (vazia quando nao foi medido)."""
    caminho = Path(pasta) / "medidas" / f"{video_id}.json"
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def todas(pasta: Path) -> list:
    """Todas as medidas gravadas, na ordem do catalogo."""
    encontradas = []
    for video in _canal.videos(pasta):
        medida = carregar(pasta, video["id"])
        if medida:
            encontradas.append(medida)
    return encontradas
