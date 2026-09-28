"""Som real para lutas JA gravadas (Onda 16A): anota sem regravar o clipe.

Toda luta gravada antes de 28/09/2026 tem o clipe (`gameplay/luta_*.mp4`)
mas nao tem a lista `sons` — o gravador ainda nao anotava. A luta e
deterministica pela seed, entao nao e preciso regravar o video: roda-se a
MESMA luta sem codificar (`fight_recorder --sem-video`, com o anotador) e os
sons vao para o relogio do clipe pelos MESMOS trechos do corte de tedio que
o `fight.json` guardou.

Antes de confiar, confere: vencedor, duracao e os golpes remapeados tem que
bater com os do `fight.json`. Se nao batem, a luta re-simulada nao e a do
clipe (motor mudou desde a gravacao) e o som sairia fora de sincronia — a
funcao recusa em vez de entregar som errado.
"""
from __future__ import annotations

from . import capture, highlights
from .runner import (PORTRAIT_POR_PERFIL, RESOLUCAO_POR_PERFIL,
                     camera_do_perfil)

# Tolerancias da conferencia: o fight.json guarda o tempo dos golpes com 3
# casas e a duracao com 1.
TOLERANCIA_T = 0.002
TOLERANCIA_DURACAO = 0.051


class LutaDiferente(RuntimeError):
    """A luta re-simulada nao e a mesma do clipe: o som ficaria fora de sincronia."""


def _referencia(luta: dict) -> tuple[str, dict]:
    """O perfil cuja gravacao decidiu o corte (o celular, quando existe)."""
    clipes = luta.get("clipes") or {}
    if not clipes:
        raise ValueError("luta sem clipe gravado: nao ha o que sonorizar")
    perfil = "celular" if "celular" in clipes else next(iter(clipes))
    return perfil, clipes[perfil]


def conferir(luta: dict, resultado: dict, trechos: list) -> None:
    """Levanta `LutaDiferente` se a re-simulacao nao e a luta do clipe."""
    vencedor = resultado.get("vencedor") or luta.get("p1")
    if vencedor != luta.get("vencedor"):
        raise LutaDiferente(
            f"vencedor mudou: {luta.get('vencedor')!r} no clipe, {vencedor!r} agora")
    try:
        duracao = float(resultado.get("duracao_jogo"))
        esperada = float(luta.get("duracao"))
    except (TypeError, ValueError):
        duracao = esperada = 0.0
    if abs(round(duracao, 1) - esperada) > TOLERANCIA_DURACAO:
        raise LutaDiferente(f"duracao mudou: {esperada} s no clipe, {duracao} s agora")
    guardados = luta.get("eventos_dano")
    if not guardados:
        return
    agora = highlights.remapear_gravacao(resultado, trechos)["eventos_dano"]
    if len(agora) != len(guardados):
        raise LutaDiferente(
            f"{len(guardados)} golpes no clipe, {len(agora)} na re-simulacao")
    for antes, depois in zip(guardados, agora):
        if (abs(float(antes[0]) - float(depois[0])) > TOLERANCIA_T
                or str(antes[1]) != str(depois[1])
                or abs(float(antes[2]) - float(depois[2])) > 1e-6):
            raise LutaDiferente(f"golpe diferente: {list(antes)[:3]} x {list(depois)[:3]}")


def anotar_luta(luta: dict, gameplay: dict, origem: str) -> list[dict]:
    """Os sons da luta, no relogio do clipe, sem regravar o video."""
    perfil, clipe = _referencia(luta)
    trechos = [(float(a), float(b)) for a, b in (clipe.get("trechos") or [])]
    if not trechos:
        raise ValueError("o clipe nao guardou os trechos do corte")
    resolucao = clipe.get("resolucao") or RESOLUCAO_POR_PERFIL.get(perfil)
    resultado = capture.gravar_uma(
        p1=luta["p1"], p2=luta["p2"], seed=int(luta["seed"]), saida=None,
        cenario=luta["cenario"], portrait=PORTRAIT_POR_PERFIL.get(perfil, False),
        camera_modo=luta.get("camera") or camera_do_perfil(gameplay, origem, perfil),
        resolucao=tuple(resolucao) if resolucao else None,
        sem_hud=bool(gameplay.get("sem_hud", True)),
        camera_largura_min=gameplay.get("camera_largura_min"),
        camera_espera_zoom=gameplay.get("camera_espera_zoom"))
    if not resultado.get("sucesso"):
        raise RuntimeError(f"re-simulacao falhou: {resultado.get('erro')}")
    if "sons" not in resultado:
        raise RuntimeError("o gravador nao devolveu `sons` (anotador desligado?)")
    conferir(luta, resultado, trechos)
    return highlights.remapear_gravacao(resultado, trechos)["sons"]


def rounds_de(fight: dict) -> list[dict]:
    return list(fight.get("lutas") or ([fight["luta"]] if fight.get("luta") else []))


def anotar_fight(fight: dict, gameplay: dict, origem: str, *, forcar: bool = False,
                 progresso=None) -> int:
    """Poe `sons` em cada round com clipe; devolve quantos anotou.

    `luta` (o round que fechou a serie) e uma copia do ultimo de `lutas` no
    JSON: recebe a mesma lista, pelo `match_id`.
    """
    feitos = 0
    rounds = rounds_de(fight)
    for luta in rounds:
        if not luta.get("clipes"):
            continue
        if isinstance(luta.get("sons"), list) and not forcar:
            continue
        luta["sons"] = anotar_luta(luta, gameplay, origem)
        feitos += 1
        if progresso:
            progresso(luta)
    decisiva = fight.get("luta")
    if isinstance(decisiva, dict) and decisiva is not (rounds[-1] if rounds else None):
        sons = sons_por_round(fight).get(decisiva.get("match_id", 0))
        if sons is not None:
            decisiva["sons"] = sons
    return feitos


def sons_por_round(fight: dict) -> dict:
    """`match_id -> sons` dos rounds que ja tem a lista."""
    return {luta.get("match_id", 0): luta["sons"] for luta in rounds_de(fight)
            if isinstance(luta.get("sons"), list)}


def aplicar_no_plano(plano: dict, sons: dict, som_cfg: dict | None) -> int:
    """Copia `sons` para a luta de cada evento de gameplay do plano JA montado.

    O plano nao e remontado de proposito: legenda, callout e corte continuam
    exatamente os do video que existe — so o som da luta muda.
    """
    feitos = 0
    for evento in plano.get("events") or []:
        if evento.get("type") != "gameplay":
            continue
        luta = evento.get("luta")
        if not isinstance(luta, dict):
            continue
        chave = luta.get("match_id", evento.get("match_id", 0))
        if chave not in sons:
            continue
        luta["sons"] = sons[chave]
        if som_cfg:
            evento["som_da_luta"] = dict(som_cfg)
        feitos += 1
    return feitos
