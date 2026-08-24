"""Melhores momentos: escolhe QUAIS segundos da luta entram no video.

A luta inteira e gravada uma vez (`neural_fights.recording.fight_recorder`);
aqui decidimos o recorte. O critério vem dos eventos de dano que a gravacao
coletou — mesmo mecanismo da `FightQualityProbe` do jogo, que ja usa uma
janela deslizante de 1 s para achar o trecho mais quente
(`neural_fights/simulation/probes.py:237-244`).

Recorte padrao: **a janela mais violenta + o desfecho terminando no KO**.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def janela_mais_quente(eventos: list, duracao_janela: float) -> tuple[float, float]:
    """Trecho de `duracao_janela` segundos com mais dano acumulado.

    Dois ponteiros sobre os eventos ja ordenados por tempo — o mesmo formato
    de varredura da sonda do jogo.
    """
    if not eventos:
        return 0.0, 0.0
    tempos = [float(e[0]) for e in eventos]
    danos = [float(e[2]) for e in eventos]
    melhor_soma, melhor_inicio = -1.0, tempos[0]
    inicio = 0
    soma = 0.0
    for fim, t_fim in enumerate(tempos):
        soma += danos[fim]
        while tempos[inicio] < t_fim - duracao_janela:
            soma -= danos[inicio]
            inicio += 1
        if soma > melhor_soma:
            melhor_soma = soma
            melhor_inicio = tempos[inicio]
    return max(0.0, melhor_inicio), melhor_soma


def planejar_recorte(gravacao: dict, *, alvo: float = 10.0,
                     minimo_para_cortar: float = 12.0,
                     desfecho: float = 6.0) -> list[tuple[float, float]]:
    """Devolve os trechos `(inicio, duracao)` a extrair do mp4 da luta.

    - Luta curta (<= `minimo_para_cortar`): entra inteira, sem corte.
    - Luta longa: janela mais quente + desfecho terminando no KO.
    Os trechos nunca se sobrepoem e respeitam os limites do arquivo.
    """
    total = float(gravacao.get("duracao_video") or 0.0)
    if total <= 0:
        return []
    if total <= minimo_para_cortar:
        return [(0.0, total)]

    # O desfecho e ancorado no KO (que ja inclui slow-mo + letterbox gravados).
    fim_video = float(gravacao.get("ko_em_video") or total)
    fim_video = min(total, fim_video + 3.0)
    dur_desfecho = min(desfecho, total, fim_video)
    inicio_desfecho = max(0.0, fim_video - dur_desfecho)

    dur_quente = max(0.0, alvo - dur_desfecho)
    if dur_quente < 1.0:
        return [(round(inicio_desfecho, 2), round(dur_desfecho, 2))]

    inicio_quente, _ = janela_mais_quente(
        gravacao.get("eventos_dano") or [], dur_quente)
    inicio_quente = max(0.0, min(inicio_quente, total - dur_quente))

    # Se a janela quente ja estiver dentro do desfecho, nao repete o trecho:
    # estica o desfecho ate o alvo e entrega um corte so.
    if inicio_quente + dur_quente > inicio_desfecho:
        dur = min(alvo, fim_video)
        return [(round(max(0.0, fim_video - dur), 2), round(dur, 2))]

    return [(round(inicio_quente, 2), round(dur_quente, 2)),
            (round(inicio_desfecho, 2), round(dur_desfecho, 2))]


def extrair(origem: Path, destino: Path, trechos: list[tuple[float, float]],
            *, crf: int = 20, preset: str = "veryfast") -> float:
    """Corta os trechos do mp4 e emenda num arquivo so. Devolve a duracao."""
    origem, destino = Path(origem), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not trechos:
        return 0.0

    if len(trechos) == 1 and trechos[0][0] <= 0.01:
        inicio, duracao = trechos[0]
        comando = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origem),
                   "-t", str(duracao), "-c", "copy", str(destino)]
        if subprocess.run(comando, capture_output=True, creationflags=NO_WINDOW).returncode == 0:
            return duracao

    partes = []
    for indice, (inicio, duracao) in enumerate(trechos):
        parte = destino.with_name(f"{destino.stem}_p{indice}.mp4")
        comando = ["ffmpeg", "-y", "-loglevel", "error",
                   "-ss", str(inicio), "-i", str(origem), "-t", str(duracao),
                   "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                   "-pix_fmt", "yuv420p", "-an", str(parte)]
        if subprocess.run(comando, capture_output=True, creationflags=NO_WINDOW).returncode != 0:
            continue
        partes.append(parte)

    if not partes:
        return 0.0
    if len(partes) == 1:
        partes[0].replace(destino)
    else:
        lista = destino.with_suffix(".txt")
        lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in partes),
                         encoding="utf-8")
        comando = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                   "-safe", "0", "-i", str(lista), "-c", "copy", str(destino)]
        if subprocess.run(comando, capture_output=True, creationflags=NO_WINDOW).returncode != 0:
            partes[0].replace(destino)
        for parte in partes:
            parte.unlink(missing_ok=True)
        lista.unlink(missing_ok=True)
    return round(sum(d for _, d in trechos), 2)
