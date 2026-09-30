"""A conta dos quadros do palco, em Python: o espelho de `palco/nucleo/plano.gd`.

Serve para conferir o mp4 SEM confiar no Godot: o numero de quadros que o
video tem de ter sai daqui e do relatorio do Godot, e os dois tem de bater.

- Sem remapeamento: um trecho so, [0, duracao, 1].
- Trecho [inicio, duracao, velocidade]: round(duracao / velocidade * fps)
  quadros. O `round` e o do GDScript (meio para longe do zero), nao o
  arredondamento bancario do Python — a diferenca aparece em x,5.
"""
from __future__ import annotations

import math


def arredondar(x: float) -> int:
    """round() do GDScript: 2,5 -> 3 (o do Python daria 2)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def trechos(remapeamento, duracao_total: float) -> list[tuple[float, float, float]]:
    lista = (remapeamento or {}).get("trechos") if isinstance(remapeamento, dict) else remapeamento
    if not lista:
        return [(0.0, float(duracao_total), 1.0)]
    saida = []
    for trecho in lista:
        velocidade = float(trecho[2]) if len(trecho) > 2 else 1.0
        saida.append((float(trecho[0]), float(trecho[1]), velocidade))
    return saida


def quadros(duracao_total: float, remapeamento=None, fps: int = 30) -> int:
    return sum(arredondar(dur / vel * fps) for _ini, dur, vel in trechos(remapeamento, duracao_total))


def mapear(t: float, duracao_total: float, remapeamento=None, fps: int = 30) -> int:
    """Instante da gravacao -> quadro do video (-1 se caiu num corte)."""
    inicio = 0
    for ini, dur, vel in trechos(remapeamento, duracao_total):
        n = arredondar(dur / vel * fps)
        if t < ini - 1e-6:
            return -1
        if t <= ini + dur + 1e-6:
            return inicio + min(max(0, arredondar((t - ini) / vel * fps)), max(0, n - 1))
        inicio += n
    return -1


# ---------------------------------------------------------------- hitstop
# O hitstop EXTRA do render (estilo do palco, `hitstop_<tier>` em segundos):
# quadros repetidos logo depois do quadro-base de cada `acerto`, o maior
# vencendo quando dois acertos caem no mesmo quadro. Espelho de
# `PlanoQuadros.com_hitstop` (plano.gd). Os valores moram no ESTILO GLOBAL:
# os padroes em `palco/nucleo/estilo.gd`, o que o Adrian mexeu no inspetor em
# `palco/biblioteca/estilo.tres`, e o job ainda pode sobrepor campo a campo.
CAMPO_HITSTOP = {"light": "hitstop_leve", "medium": "hitstop_medio", "heavy": "hitstop_pesado",
                 "colossal": "hitstop_colossal"}


def _valores_float(texto: str, *, gd: bool) -> dict[str, float]:
    import re
    padrao = (r"var\s+(hitstop_\w+)\s*:\s*float\s*=\s*([-0-9.]+)" if gd
              else r"^\s*(hitstop_\w+)\s*=\s*([-0-9.]+)\s*$")
    return {m.group(1): float(m.group(2)) for m in re.finditer(padrao, texto, re.MULTILINE)}


def hitstop_do_estilo(projeto, sobrepor: dict | None = None) -> dict[str, float]:
    """{tier: segundos, "dano_min": fracao} do estilo global do palco
    (estilo.gd < estilo.tres < job)."""
    from pathlib import Path
    projeto = Path(projeto)
    campos: dict[str, float] = {}
    for arquivo, gd in ((projeto / "nucleo" / "estilo.gd", True), (projeto / "biblioteca" / "estilo.tres", False)):
        try:
            campos.update(_valores_float(arquivo.read_text(encoding="utf-8"), gd=gd))
        except OSError:
            pass
    for chave, valor in (sobrepor or {}).items():
        if chave in CAMPO_HITSTOP.values() or chave == "hitstop_dano_min":
            campos[chave] = float(valor)
    saida = {tier: float(campos.get(campo, 0.0)) for tier, campo in CAMPO_HITSTOP.items()}
    saida["dano_min"] = float(campos.get("hitstop_dano_min", 0.0))
    return saida


def quadros_de_hitstop(doc: dict, segundos_por_tier: dict, remapeamento=None, fps: int = 30) -> int:
    """Quantos quadros parados o hitstop do render acrescenta a esta luta.

    So para o acerto que tirou pelo menos `dano_min` da vida do alvo: o tier e
    do AUTOR (a forca dele), nao do golpe, e sem este piso o tique de um
    projetil de 1% parava o video como uma machadada."""
    return sum(paradas_de_hitstop(doc, segundos_por_tier, remapeamento, fps).values())


def paradas_de_hitstop(doc: dict, segundos_por_tier: dict, remapeamento=None, fps: int = 30) -> dict[int, int]:
    """{quadro-base do acerto: quadros parados logo depois dele} — ONDE o
    hitstop para o video, e nao so quanto. A edicao do duelo por cima do palco
    (16G) usa isto para levar HUD, callouts e som ao relogio do palco."""
    dano_min = float(segundos_por_tier.get("dano_min", 0.0))
    hz = int(doc["hz"])
    duracao = int(doc["n"]) / hz
    remap = remapeamento if remapeamento is not None else doc.get("remapeamento")
    paradas: dict[int, int] = {}
    for ev in doc.get("eventos") or []:
        if ev.get("tipo") != "acerto" or float(ev.get("dano_pct") or 0.0) < dano_min:
            continue
        segundos = float(segundos_por_tier.get(str(ev.get("tier", "")), 0.0))
        if segundos <= 0.0:
            continue
        base = mapear(int(ev["i"]) / hz, duracao, remap, fps)
        quantos = arredondar(segundos * fps)
        if base >= 0 and quantos > 0:
            paradas[base] = max(paradas.get(base, 0), quantos)
    return paradas


def atraso_de_hitstop(paradas: dict[int, int], t: float, fps: int = 30) -> float:
    """Quanto o instante `t` do clipe SEM hitstop anda no video COM hitstop.

    O quadro-base b vai para b + (parados antes dele): o proprio acerto aparece
    no quadro dele e so DEPOIS a imagem para (espelho de
    `PlanoQuadros._aplicar_paradas`)."""
    quadro = arredondar(float(t) * fps)
    return sum(q for b, q in paradas.items() if b < quadro) / fps
