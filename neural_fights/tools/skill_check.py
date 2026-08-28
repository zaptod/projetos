# -*- coding: utf-8 -*-
"""Checagem 1-a-1 de skills (Onda 11B): casta CADA skill num cenário
determinístico do MOTOR REAL e verifica que a ``consequencia_esperada``
declarada no contrato aconteceu de verdade.

Usado pelo CLI (``skill_inspector checar``) e pelo harness de regressão
(``tests/test_skill_one_by_one.py``). Importa o jogo — é dev-tool, não faz
parte do caminho import-safe do inspetor.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from neural_fights.core.skill_contract import (
    SkillContract,
    derivar_contrato,
)
from neural_fights.core.skills import SKILL_DB, get_skill_data
from neural_fights.core.status_runtime import STATUS_TIMER_ATTRS, normalizar_efeito
from neural_fights.models.characters import Personagem

CLASSE_NEUTRA = "Guerreiro (Força Bruta)"
DURACAO_CENARIO_S = 5.0
FPS = 60

# Status que o runtime materializa por outro canal: PARALISIA congela via o
# timer de stun (ATORDOADO); KNOCK_UP é física vertical (z/vel_z).
_STATUS_EQUIVALENTES = {
    "ATORDOADO": ("PARALISIA",),
    "PARALISIA": ("ATORDOADO",),
}


def _provider_sintetico(nome_caster: str, nome_alvo: str):
    """Roster provider com dois bonecos neutros e sem arma (contrato do
    ``roster_provider`` do Simulador: resolver(nome) -> Personagem)."""

    def resolver(nome: str) -> Personagem:
        eh_caster = nome == nome_caster
        personagem = Personagem(
            nome,
            1.7,            # tamanho
            5.0,            # força
            8.0,            # mana
            "",             # sem arma
            0.0,            # peso da arma
            220 if eh_caster else 90,
            90,
            90 if eh_caster else 220,
            CLASSE_NEUTRA,
            "Aleatório",
        )
        personagem.arma_obj = None
        return personagem

    return resolver


def _distancia_do_cenario(contrato: SkillContract) -> float:
    """Distância caster→dummy derivada da geometria declarada."""
    alcance = contrato.alcance_lancamento
    if alcance <= 0.0:
        # Self-cast: dummy perto o bastante para auras/novas o cobrirem.
        return max(1.6, min(2.0, contrato.raio_efeito * 0.8 or 2.0))
    if contrato.tipo == "DASH":
        return max(2.5, min(alcance, 5.0))
    return max(1.8, min(alcance * 0.6, 6.0))


class _Observador:
    """Observa o mundo por frame e marca as consequências que aconteceram."""

    def __init__(self, sim, contrato: SkillContract):
        self.sim = sim
        self.contrato = contrato
        self.observadas: set = set()
        p1, p2 = sim.p1, sim.p2
        self.vida_alvo_base = float(p2.vida)
        self.vida_caster_base = float(p1.vida)
        self.pos_alvo_base = (float(p2.pos[0]), float(p2.pos[1]))
        self.pos_caster_base = (float(p1.pos[0]), float(p1.pos[1]))

    def ancorar_pre_cast(self, custo_vida_previsto: float):
        """A base do caster desconta o custo de vida que o cast VAI cobrar —
        assim curas instantâneas aplicadas dentro do próprio cast aparecem."""
        self.vida_caster_base = float(self.sim.p1.vida) - max(
            0.0, float(custo_vida_previsto)
        )
        self.vida_alvo_base = float(self.sim.p2.vida)

    def _statuses_ativos(self, alvo) -> set:
        ativos = set()
        for attr, status_id in STATUS_TIMER_ATTRS.items():
            if float(getattr(alvo, attr, 0.0) or 0.0) > 0.0:
                ativos.add(status_id)
        if getattr(alvo, "congelado", False) or (
            float(getattr(alvo, "congelado_timer", 0.0) or 0.0) > 0.0
        ):
            ativos.add("CONGELADO")
        for dot in getattr(alvo, "dots_ativos", ()) or ():
            tipo = normalizar_efeito(getattr(dot, "tipo", ""))
            if tipo and getattr(dot, "ativo", True):
                ativos.add(tipo)
        # KNOCK_UP é física: o alvo saiu do chão contra a vontade.
        if float(getattr(alvo, "z", 0.0) or 0.0) > 0.05 or float(
            getattr(alvo, "vel_z", 0.0) or 0.0
        ) > 0.5:
            ativos.add("KNOCK_UP")
        for status_id in tuple(ativos):
            ativos.update(_STATUS_EQUIVALENTES.get(status_id, ()))
        return ativos

    def amostrar(self):
        sim = self.sim
        p1, p2 = sim.p1, sim.p2
        obs = self.observadas

        # Objetos: no mundo OU ainda no buffer do cast (projéteis de contato
        # podem nascer e morrer dentro de um único passo do simulador).
        if getattr(sim, "projeteis", None) or getattr(p1, "buffer_projeteis", None):
            obs.add("objeto:projetil")
        areas = list(getattr(sim, "areas", None) or []) + list(
            getattr(p1, "buffer_areas", None) or []
        )
        if areas:
            obs.add("objeto:area")
            if any(getattr(a, "ground", False) for a in areas):
                obs.add("terreno")
            if any(float(getattr(a, "forca_puxar", 0.0) or 0.0) > 0.0 for a in areas):
                # O vórtice está armado sobre o alvo — puxar do centro para o
                # centro não desloca, mas a mecânica está viva.
                obs.add("deslocamento:puxa")
        if getattr(sim, "beams", None) or getattr(p1, "buffer_beams", None):
            obs.add("objeto:beam")
        if getattr(sim, "summons", None) or getattr(p1, "buffer_summons", None):
            obs.add("objeto:summon")
        traps = list(getattr(sim, "traps", None) or []) + list(
            getattr(p1, "buffer_traps", None) or []
        )
        if traps:
            obs.add("objeto:trap")
            for trap in traps:
                if getattr(trap, "bloqueia_projeteis", False):
                    obs.add("bloqueio_projeteis")
                if getattr(trap, "bloqueia_movimento", False):
                    obs.add("bloqueio_movimento")
        if getattr(sim, "portais", None):
            obs.add("objeto:portal")

        if getattr(p1, "canalizando", False):
            obs.add("canalizacao")
        if getattr(p1, "transformacao_ativa", None) is not None:
            obs.add("transformacao")
        if getattr(p1, "buffs_ativos", None):
            obs.add("buff")
            for buff in p1.buffs_ativos:
                if (
                    float(getattr(buff, "escudo", 0.0) or 0.0) > 0.0
                    or float(getattr(buff, "escudo_restante", 0.0) or 0.0) > 0.0
                ):
                    obs.add("escudo")
        if float(getattr(p1, "imune_debuffs_timer", 0.0) or 0.0) > 0.0:
            obs.add("buff")  # imunidade a debuffs é um estado ativo no caster

        if float(p2.vida) < self.vida_alvo_base - 0.01:
            obs.add("dano")
        if float(p1.vida) < self.vida_caster_base - 0.01:
            obs.add("dano")  # backfire/afeta_caster também é dano real
        if float(p1.vida) > self.vida_caster_base + 0.01:
            obs.add("cura")

        statuses = self._statuses_ativos(p2)
        for status_id in statuses:
            obs.add(f"status:{status_id}")
        if statuses:
            obs.add("status:ALEATORIO")
        if getattr(p2, "dots_ativos", None):
            obs.add("dot")

        # Deslocamento do dummy (brain=None: ele não anda sozinho).
        if getattr(p2, "puxao", None):
            obs.add("deslocamento:puxa")
        dx = float(p2.pos[0]) - self.pos_alvo_base[0]
        dy = float(p2.pos[1]) - self.pos_alvo_base[1]
        if math.hypot(dx, dy) > 0.6:
            if "deslocamento:puxa" not in obs:
                obs.add("deslocamento:empurra")
        if float(getattr(p2, "lancado_timer", 0.0) or 0.0) > 0.0:
            obs.add("deslocamento:empurra")

        # Deslocamento do caster (dash/teleporte/troca).
        cx = float(p1.pos[0]) - self.pos_caster_base[0]
        cy = float(p1.pos[1]) - self.pos_caster_base[1]
        if math.hypot(cx, cy) > 0.8 or float(getattr(p1, "dash_timer", 0.0) or 0.0) > 0.0:
            obs.add("deslocamento:dash")
        if math.hypot(
            float(p1.pos[0]) - self.pos_alvo_base[0],
            float(p1.pos[1]) - self.pos_alvo_base[1],
        ) < 0.6:
            obs.add("deslocamento:troca")


def _consequencias_exigidas(contrato: SkillContract) -> set:
    """Subconjunto DETERMINÍSTICO das consequências (o que o cenário exige).

    Efeitos probabilísticos (``chance_efeito < 1``) e o rótulo genérico
    ``status:ALEATORIO`` continuam declarados no contrato, mas não reprovam
    a checagem quando o dado não cai.
    """
    exigidas = set(contrato.consequencias)
    if contrato.chance_efeito < 1.0 and contrato.efeito:
        exigidas.discard(f"status:{contrato.efeito}")
    if contrato.efeito_aleatorio:
        exigidas.discard("status:ALEATORIO")
        # o status sorteado específico não é previsível
        exigidas = {c for c in exigidas if not c.startswith("status:")}
    if contrato.executa:
        # Um execute mata o alvo; status no cadáver é sabor, não contrato.
        exigidas = {c for c in exigidas if not c.startswith("status:")}
    return exigidas


def checar_skill(nome: str, *, seed: int = 101) -> Dict:
    """Roda o cenário 1-a-1 de UMA skill e devolve o veredito."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from neural_fights.simulation.simulacao import Simulador

    data = get_skill_data(nome)
    contrato = derivar_contrato(nome)
    resultado: Dict = {
        "skill": nome,
        "tipo": contrato.tipo,
        "ok": False,
        "esperadas": sorted(_consequencias_exigidas(contrato)),
        "observadas": [],
        "faltando": [],
        "erro": None,
    }
    if contrato.tipo == "NADA":
        resultado["erro"] = "skill sentinela"
        return resultado

    passiva_de_morte = bool(
        data.get("ativa_ao_morrer") or data.get("revive_hp_percent")
    )

    caster_nome, alvo_nome = "Demo Caster", "Demo Alvo"
    sim = None
    try:
        sim = Simulador(
            match_config={
                "p1_nome": caster_nome,
                "p2_nome": alvo_nome,
                "cenario": "Arena",
                "best_of": 1,
            },
            headless=True,
            seed=seed,
            roster_provider=_provider_sintetico(caster_nome, alvo_nome),
        )
        p1, p2 = sim.p1, sim.p2
        p1.brain = None
        p2.brain = None

        distancia = _distancia_do_cenario(contrato)
        p1.pos[0], p1.pos[1] = 5.0, 5.0
        p2.pos[0], p2.pos[1] = 5.0 + distancia, 5.0
        p1.angulo_olhar = 0.0
        p2.angulo_olhar = 180.0

        # Recursos de sobra + espaço para observar cura.
        p1.mana_max = max(p1.mana_max, 500.0)
        p1.mana = p1.mana_max
        p1.vida = p1.vida_max * 0.6

        # Kit = só a skill checada.
        p1.skills_classe = [
            {"nome": nome, "custo": data.get("custo", 0.0), "data": data}
        ]
        p1.cd_skills[nome] = 0.0

        # Gates condicionais recebem o estado prévio no dummy.
        if contrato.condicao == "ALVO_BAIXA_VIDA":
            p2.vida = p2.vida_max * max(
                0.05, contrato.condicao_limiar - 0.1
            )
        elif contrato.condicao_status:
            p2.tomar_dano(
                0.0, 0.0, 0.0, contrato.condicao_status,
                atacante=p1, metadata_impacto={"eh_skill": True},
            )
        if data.get("reverte_estado") is not None:
            # A skill rebobina N segundos — o cenário roda esse tempo antes
            # do cast para o histórico existir (registro é automático no
            # update do lutador).
            segundos = float(data.get("reverte_estado") or 0.0)
            for _ in range(int((segundos + 0.6) * FPS)):
                sim.update(1.0 / FPS)

        observador = _Observador(sim, contrato)
        from neural_fights.core.skill_contract import custo_vida_do_cast
        observador.ancorar_pre_cast(custo_vida_do_cast(contrato, p1.vida_max))

        # DASH sem propósito segue o olhar em linha reta ATRAVÉS do alvo —
        # o cenário quer o contato; propósito tático é decisão da IA.
        proposito = None if contrato.tipo == "DASH" else "ENGAGE"
        castou = p1.usar_skill_classe(nome, alvo=p2, proposito=proposito)
        if passiva_de_morte:
            # O contrato correto é o cast RECUSAR uma passiva de morte.
            resultado["ok"] = not castou
            resultado["esperadas"] = ["gate:passiva_de_morte_recusa_cast"]
            resultado["observadas"] = (
                [] if castou else ["gate:passiva_de_morte_recusa_cast"]
            )
            if castou:
                resultado["erro"] = "passiva de morte foi castável"
            return resultado
        if not castou:
            resultado["erro"] = "cast recusado pelo runtime"
            return resultado

        exigidas = _consequencias_exigidas(contrato)
        dt = 1.0 / FPS
        # Amostra o instante do cast: projéteis de contato podem nascer e
        # morrer dentro do primeiro passo do simulador.
        observador.amostrar()
        for _ in range(int(DURACAO_CENARIO_S * FPS)):
            sim.update(dt)
            observador.amostrar()
            if exigidas <= observador.observadas:
                break

        resultado["observadas"] = sorted(observador.observadas)
        resultado["faltando"] = sorted(exigidas - observador.observadas)
        resultado["ok"] = not resultado["faltando"]
        return resultado
    except Exception as exc:  # o veredito reporta, nunca explode o lote
        resultado["erro"] = f"{type(exc).__name__}: {exc}"
        return resultado
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass


def checar_todas(*, seed: int = 101, nomes: Optional[List[str]] = None) -> List[Dict]:
    alvos = nomes if nomes is not None else [
        nome for nome in SKILL_DB if nome != "Nenhuma"
    ]
    return [checar_skill(nome, seed=seed) for nome in alvos]


__all__ = ["checar_skill", "checar_todas"]
