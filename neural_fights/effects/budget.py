# -*- coding: utf-8 -*-
"""ORÇAMENTO VISUAL — a doutrina de efeitos com força de lei.

Reforma "luta limpa": o problema medido não era volume de partículas, era
REDUNDÂNCIA DE CANAL (um hit disparava 4 sistemas de faísca) somada a 11
listas de VFX sem teto nenhum. Este módulo é o funil único por onde todo
spawn passa.

Três camadas (a doutrina):
  A LEITURA    — informação de gameplay. Nunca orçada, nunca congelada.
  B PONTUAÇÃO  — o acento do evento. Orçada; um evento = uma leitura por
                 canal (canal ocupado → substitui, não empilha).
  C ATMOSFERA  — clima, decoração, trilhas. Primeira a morrer; CONGELA
                 durante hit-stop e letterbox.
"""

# --- prioridades (menor = mais importante) --------------------------------
PRIORIDADE_IMPACTO = 0     # hit, clash, morte, defesa
PRIORIDADE_ARMA = 1        # encantamento, trilha de arma
PRIORIDADE_SKILL = 2       # explosão, área, beam, summon, canalização
PRIORIDADE_AMBIENTE = 3    # clima, poeira de sprint, colisão de parede

# --- tetos globais (alvo da reforma) --------------------------------------
TETO_PARTICULAS = 260

# fração do teto que cada prioridade pode ocupar
FATOR_PRIORIDADE = {
    PRIORIDADE_IMPACTO: 1.00,
    PRIORIDADE_ARMA: 0.85,
    PRIORIDADE_SKILL: 0.60,
    PRIORIDADE_AMBIENTE: 0.35,
}

# --- teto por lista de VFX (as 11 listas que não tinham nenhum) ------------
TETO_POR_LISTA = {
    "textos": 3,
    "shockwaves": 3,
    "impact_flashes": 4,
    "hit_sparks": 6,
    "magic_clashes": 2,
    "block_effects": 3,
    "dash_trails": 4,
    "decals": 18,
}


class FrameBudget:
    """Orçamento de um frame. `congelado` desliga as camadas B/C durante
    hit-stop e letterbox — hoje efeito continua nascendo com o jogo
    parado."""

    __slots__ = ("teto", "congelado")

    def __init__(self, teto: int = TETO_PARTICULAS):
        self.teto = teto
        self.congelado = False

    def permitidas(self, atuais: int, pedido: int,
                   prioridade: int = PRIORIDADE_SKILL) -> int:
        """Quantas partículas do pedido cabem, dada a prioridade."""
        if pedido <= 0:
            return 0
        if self.congelado and prioridade >= PRIORIDADE_SKILL:
            return 0
        fator = FATOR_PRIORIDADE.get(prioridade, 0.6)
        limite = int(self.teto * fator)
        return max(0, min(pedido, limite - atuais))

    def cabe_vfx(self, nome_lista: str, atual: int,
                 prioridade: int = PRIORIDADE_IMPACTO) -> bool:
        """Se a lista aceita mais um objeto (o chamador descarta o mais
        antigo quando não cabe — o evento novo é o relevante)."""
        if self.congelado and prioridade >= PRIORIDADE_SKILL:
            return False
        return atual < TETO_POR_LISTA.get(nome_lista, 8)

    def teto_de(self, nome_lista: str) -> int:
        return TETO_POR_LISTA.get(nome_lista, 8)
