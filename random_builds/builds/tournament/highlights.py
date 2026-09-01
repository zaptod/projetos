"""Melhores momentos: escolhe QUAIS segundos da luta entram no video.

A luta inteira e gravada uma vez (`neural_fights.recording.fight_recorder`);
aqui decidimos o recorte. O critério vem dos eventos de dano que a gravacao
coletou — mesmo mecanismo da `FightQualityProbe` do jogo, que ja usa uma
janela deslizante de 1 s para achar o trecho mais quente
(`neural_fights/simulation/probes.py:237-244`).

Dois recortes, duas doutrinas:

- `planejar_corte_tedio` (Onda 9, padrao): a luta e o elemento dominante,
  entao ela entra QUASE INTEIRA. So saem as janelas secas (mais de 4 s sem
  ninguem tomar dano), preservando 1 s de contexto em cada ponta e nunca
  tocando nos ultimos 8 s antes do KO. Um combo e uma sequencia de golpes a
  menos de 1 s um do outro — por construcao nenhum corte cai dentro dele.
- `planejar_recorte` (formato antigo): **a janela mais violenta + o desfecho
  terminando no KO**, para quando so cabem ~10 s.

Cortar a gravacao muda o tempo: `remapear_gravacao` leva a serie de HP, os
golpes e os eventos narrativos para o relogio do CLIPE, que e o que o
renderer ve.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _fundir(cortes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Intervalos (inicio, fim) ordenados e sem sobreposicao."""
    saida: list[list[float]] = []
    for ini, fim in sorted(cortes):
        if fim <= ini:
            continue
        if saida and ini <= saida[-1][1]:
            saida[-1][1] = max(saida[-1][1], fim)
        else:
            saida.append([ini, fim])
    return [(a, b) for a, b in saida]


def _complemento(cortes: list[tuple[float, float]], total: float
                 ) -> list[tuple[float, float]]:
    """O que FICA: (inicio, duracao) de cada trecho entre os cortes."""
    trechos = []
    cursor = 0.0
    for ini, fim in cortes:
        if ini - cursor > 0.05:
            trechos.append((round(cursor, 2), round(ini - cursor, 2)))
        cursor = max(cursor, fim)
    if total - cursor > 0.05:
        trechos.append((round(cursor, 2), round(total - cursor, 2)))
    return trechos


def duracao_total(trechos: list[tuple[float, float]]) -> float:
    return round(sum(float(d) for _, d in trechos), 2)


def planejar_corte_tedio(gravacao: dict, *, max_total: float = 45.0,
                         seca_min: float = 4.0, contexto: float = 1.0,
                         protecao_ko: float = 8.0, abertura: float = 0.8,
                         minimo_para_cortar: float = 12.0
                         ) -> list[tuple[float, float]]:
    """Trechos `(inicio, duracao)` que FICAM: a luta menos o tedio.

    - Luta curta (<= `minimo_para_cortar`): inteira.
    - Janela sem dano maior que `seca_min`: sai o miolo, ficam `contexto`
      segundos em cada ponta (o golpe que fechou a janela e o que abriu a
      proxima continuam com o seu antes e depois). A aproximacao inicial
      mantem so `abertura` segundos de estabelecimento.
    - Os ultimos `protecao_ko` s antes do nocaute nunca sao cortados: o
      desfecho e o que o espectador veio ver.
    - Se ainda passar de `max_total`, a regra de seca aperta em degraus;
      se nem assim couber, cai no recorte quente+desfecho do formato antigo.
    """
    total = float(gravacao.get("duracao_video") or 0.0)
    if total <= 0:
        return []
    if total <= min(minimo_para_cortar, max_total):
        return [(0.0, round(total, 2))]

    fim_luta = float(gravacao.get("ko_em_video") or total)
    tempos = sorted(float(e[0]) for e in (gravacao.get("eventos_dano") or []))

    def cortes_para(seca: float) -> list[tuple[float, float]]:
        marcos = [0.0, *tempos, fim_luta]
        cortes = []
        for a, b in zip(marcos, marcos[1:]):
            if b - a <= seca:
                continue
            ini = abertura if a == 0.0 else a + contexto
            fim = min(b - contexto, fim_luta - protecao_ko)
            if fim - ini >= 0.8:
                cortes.append((round(ini, 2), round(fim, 2)))
        return _fundir(cortes)

    for seca in (seca_min, seca_min * 0.75, seca_min * 0.5, max(1.5, seca_min * 0.375)):
        trechos = _complemento(cortes_para(seca), total)
        if duracao_total(trechos) <= max_total + 1e-6:
            return trechos

    # Luta longa e densa demais: o corte de tedio nao basta. Ficam a ABERTURA
    # (quem e quem, primeiro sangue) e o DESFECHO ate o teto, com um jump cut
    # no meio — melhor 45 s com comeco e fim que 90 s inteiros.
    abertura_longa = round(min(4.0, max_total * 0.1), 2)
    inicio_final = round(max(abertura_longa, total - (max_total - abertura_longa)), 2)
    return [(0.0, abertura_longa), (inicio_final, round(total - inicio_final, 2))]


def mapear_tempo(trechos: list[tuple[float, float]], t: float) -> float | None:
    """Tempo da gravacao -> tempo do clipe cortado (None se caiu num corte)."""
    acumulado = 0.0
    for ini, dur in trechos:
        ini, dur = float(ini), float(dur)
        if t < ini - 1e-6:
            return None
        if t <= ini + dur + 1e-6:
            return round(acumulado + (t - ini), 3)
        acumulado += dur
    return None


def remapear_gravacao(gravacao: dict, trechos: list[tuple[float, float]]) -> dict:
    """Serie de HP, golpes, eventos narrativos e KO no relogio do clipe.

    Amostras e eventos que cairam num corte somem — o HUD le "a ultima
    amostra antes de t", entao um salto de HP num jump cut e exatamente o
    que aconteceu: o tempo passou.
    """
    def _mapa(t):
        return mapear_tempo(trechos, float(t))

    serie = []
    for amostra in gravacao.get("serie_hp") or []:
        t = _mapa(amostra[0])
        if t is not None:
            serie.append((t, float(amostra[1]), float(amostra[2])))
    planos = []
    for amostra in gravacao.get("serie_plano") or []:
        t = _mapa(amostra[0])
        if t is not None:
            planos.append((t, *amostra[1:]))
    golpes = []
    for evento in gravacao.get("eventos_dano") or []:
        t = _mapa(evento[0])
        if t is not None:
            golpes.append((t, *evento[1:]))
    narrativos = []
    for evento in gravacao.get("eventos_narrativos") or []:
        t = _mapa(evento.get("t", 0.0))
        if t is not None:
            narrativos.append({**evento, "t": t})
    ko = gravacao.get("ko_em_video")
    return {
        "serie_hp": serie,
        "serie_plano": planos,
        "eventos_dano": golpes,
        "eventos_narrativos": narrativos,
        "ko_em_video": _mapa(ko) if ko is not None else None,
        "duracao": duracao_total(trechos),
    }


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
