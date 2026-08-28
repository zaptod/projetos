# -*- coding: utf-8 -*-
"""Agarrão e arremesso (Onda 10A).

Funções PURAS sobre dois lutadores: quem tem iniciativa, os pesos de cada
desfecho e a aplicação do desfecho nos corpos. O ciclo (lock de 0,25s,
cooldown, tells, VFX) vive no ``Simulador``; aqui só a mecânica — o que
permite testar com fakes de contrato e reproduzir replays.

Doutrina de determinismo: todo sorteio usa o ``rng`` recebido (o stream
do MOTOR, ``rng_runtime`` do iniciador). Nada aqui toca ``random``.
"""

from __future__ import annotations

import math

from neural_fights.utils.config import (
    DANO_ARREMESSO_PCT,
    FORCA_ARREMESSO,
)

DESFECHOS = ("ARREMESSO", "JOELHADA", "EMPURRAO", "REVERSAO", "ESCAPE")

# Desfechos que o NOVO iniciador pode aplicar depois de uma reversão —
# reverter uma reversão seria ping-pong, não luta.
_DESFECHOS_POS_REVERSAO = ("ARREMESSO", "JOELHADA", "EMPURRAO")

_CLASSES_PESADAS = ("Cavaleiro", "Berserker", "Guerreiro")
_CLASSES_AGEIS = ("Ninja", "Ladino", "Assassino")
_ARMAS_RANGED = ("Arco", "Arremesso", "Mágica")


def _perfil(lutador) -> dict:
    brain = getattr(lutador, "brain", None)
    perfil = getattr(brain, "perfil", None) if brain is not None else None
    return perfil if isinstance(perfil, dict) else {}


def _eixo(lutador, nome: str) -> float:
    try:
        return max(0.0, float(_perfil(lutador).get(nome, 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _forca(lutador) -> float:
    try:
        return float(getattr(getattr(lutador, "dados", None), "forca", 5.0) or 5.0)
    except (TypeError, ValueError):
        return 5.0


def _classe(lutador) -> str:
    return str(getattr(lutador, "classe_nome", "") or "")


def _arquetipo(lutador) -> str:
    brain = getattr(lutador, "brain", None)
    return str(getattr(brain, "arquetipo", "") or "").upper()


def _leitura(lutador) -> float:
    brain = getattr(lutador, "brain", None)
    try:
        return max(0.0, min(1.0, float(getattr(brain, "habilidade_leitura", 0.3) or 0.3)))
    except (TypeError, ValueError):
        return 0.3


def _estamina(lutador) -> float:
    try:
        return max(0.0, float(getattr(lutador, "estamina", 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def iniciativa(lutador, rng) -> float:
    """Quem agarra: agressividade + força + fôlego + um pouco de sorte."""
    brain = getattr(lutador, "brain", None)
    base = 0.5
    if brain is not None and hasattr(brain, "agressividade_efetiva"):
        try:
            base = float(brain.agressividade_efetiva())
        except Exception:
            base = 0.5
    return (
        base
        + _forca(lutador) * 0.03
        + _estamina(lutador) / 500.0
        + rng.uniform(0.0, 0.15)
    )


def pesos_desfecho(ini, alvo) -> dict[str, float]:
    """Roleta ponderada: o bruto arremessa, o ágil reverte ou escapa."""
    forca_ini = _forca(ini)
    agress = _eixo(ini, "agressao")
    cautela = _eixo(ini, "cautela")
    mob_alvo = _eixo(alvo, "mobilidade")
    leitura_alvo = _leitura(alvo)
    classe_ini = _classe(ini)
    classe_alvo = _classe(alvo)

    arma = getattr(getattr(ini, "dados", None), "arma_obj", None)
    arma_melee = getattr(arma, "tipo", "") not in _ARMAS_RANGED
    pesado = (
        any(c in classe_ini for c in _CLASSES_PESADAS)
        or "COLOSSO" in _arquetipo(ini)
    )
    agil_alvo = any(c in classe_alvo for c in _CLASSES_AGEIS)

    return {
        "ARREMESSO": 0.30 + forca_ini * 0.04 + (0.25 if pesado else 0.0),
        "JOELHADA": (0.20 + agress * 0.25) if arma_melee else 0.0,
        "EMPURRAO": 0.15 + cautela * 0.2,
        "REVERSAO": max(
            0.0,
            0.10 + mob_alvo * 0.25 + leitura_alvo * 0.25
            + (0.2 if agil_alvo else 0.0) - forca_ini * 0.02,
        ),
        "ESCAPE": (
            0.10 + mob_alvo * 0.3 + _estamina(alvo) / 400.0
            + (0.15 if agil_alvo else 0.0)
        ),
    }


def sortear_desfecho(pesos: dict[str, float], rng) -> str:
    """Roleta por peso (mesma forma do resolvedor de clinch da 8G)."""
    total = sum(max(0.0, p) for p in pesos.values())
    if total <= 0.0:
        return "EMPURRAO"
    sorteio = rng.uniform(0.0, total)
    escolhido = "EMPURRAO"
    for nome, peso in pesos.items():
        peso = max(0.0, peso)
        if peso <= 0.0:
            continue
        sorteio -= peso
        if sorteio <= 0.0:
            escolhido = nome
            break
    return escolhido


def _cabo_dano(lutador) -> float:
    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    try:
        return float(getattr(arma, "cabo_dano", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def aplicar_desfecho(ini, alvo, desfecho: str, ex: float, ey: float):
    """Aplica o desfecho nos corpos e devolve ``(modo, revertido, ini, alvo)``.

    ``(ex, ey)`` é a normal do iniciador para o alvo. Em REVERSAO os papéis
    trocam UMA vez e o novo iniciador sorteia entre arremesso/joelhada/
    empurrão (no stream dele). Nenhum desfecho conta combo/hitstun de
    golpe: o arremesso é queda, não pancada — só a joelhada é corpo a corpo.
    """
    revertido = False
    if desfecho == "REVERSAO":
        ini, alvo = alvo, ini
        ex, ey = -ex, -ey
        rng = getattr(ini, "rng_runtime", None)
        pesos = {
            nome: peso for nome, peso in pesos_desfecho(ini, alvo).items()
            if nome in _DESFECHOS_POS_REVERSAO
        }
        desfecho = sortear_desfecho(pesos, rng) if rng is not None else "EMPURRAO"
        revertido = True

    if desfecho == "ARREMESSO":
        alvo.vel[0] += ex * FORCA_ARREMESSO
        alvo.vel[1] += ey * FORCA_ARREMESSO
        alvo.stun_timer = max(alvo.stun_timer, 0.45)
        alvo.lancado_por = ini
        alvo.lancado_timer = 0.6
        forca_norm = max(0.0, min(1.0, (_forca(ini) - 2.0) / 8.0))
        pct = DANO_ARREMESSO_PCT[0] + (
            DANO_ARREMESSO_PCT[1] - DANO_ARREMESSO_PCT[0]
        ) * forca_norm
        dano = float(getattr(alvo, "vida_max", 0.0) or 0.0) * pct
        if dano > 0.0 and callable(getattr(alvo, "tomar_dano", None)):
            alvo.tomar_dano(
                dano, 0.0, 0.0, "NORMAL",
                atacante=ini,
                metadata_impacto={"tipo_fonte": "arremesso"},
                ignorar_invencibilidade=True,
                gerar_invencibilidade=False,
            )
    elif desfecho == "JOELHADA":
        dano = min(_cabo_dano(ini) or 8.0, 12.0)
        if callable(getattr(alvo, "resolver_impacto", None)):
            alvo.resolver_impacto(
                dano, ex, ey,
                atacante=ini,
                metadata_impacto={"eh_corpo_a_corpo": True,
                                  "tipo_fonte": "joelhada"},
                ignorar_invencibilidade=True,
            )
        alvo.stun_timer = max(alvo.stun_timer, 0.2)
        alvo.vel[0] += ex * 8.0
        alvo.vel[1] += ey * 8.0
    elif desfecho == "ESCAPE":
        ang_fuga = math.atan2(-ey, -ex)
        dash = getattr(alvo, "iniciar_dash", None)
        saiu = False
        if callable(dash):
            try:
                saiu = bool(dash(ang_fuga, forca=18.0, ignorar_custo=True))
            except TypeError:
                saiu = bool(dash(ang_fuga, 18.0))
        if not saiu:
            alvo.vel[0] -= ex * 12.0
            alvo.vel[1] -= ey * 12.0
        # Quem agarrou e perdeu o alvo fica aberto: janela de punição.
        ini.stun_timer = max(ini.stun_timer, 0.3)
    else:  # EMPURRAO
        desfecho = "EMPURRAO"
        alvo.vel[0] += ex * 16.0
        alvo.vel[1] += ey * 16.0
        ini.vel[0] -= ex * 4.0
        ini.vel[1] -= ey * 4.0

    for lutador in (ini, alvo):
        lutador.agarrao_timer = 0.0
        lutador.agarrao_papel = None
    return desfecho, revertido, ini, alvo


__all__ = [
    "DESFECHOS",
    "aplicar_desfecho",
    "iniciativa",
    "pesos_desfecho",
    "sortear_desfecho",
]
