"""
=============================================================================
NEURAL FIGHTS - MAGIC SYSTEM v2.0 COLOSSAL EDITION
=============================================================================
Sistema de Magia Expandido com:
- 15+ Status Effects com mecânicas únicas
- 8 Elementos com reações entre si
- Sistema de Combo Mágico
- Condições especiais de ativação
- Modificadores e Amplificadores
- Magias Carregáveis e Canalizáveis
=============================================================================
"""

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# =============================================================================
# ELEMENTOS E SUAS INTERAÇÕES
# =============================================================================

class Elemento(Enum):
    FOGO = "FOGO"
    GELO = "GELO"
    RAIO = "RAIO"
    TREVAS = "TREVAS"
    LUZ = "LUZ"
    NATUREZA = "NATUREZA"
    ARCANO = "ARCANO"
    CAOS = "CAOS"
    VOID = "VOID"
    SANGUE = "SANGUE"
    TEMPO = "TEMPO"
    GRAVITACAO = "GRAVITACAO"


# Cores dos elementos
ELEMENTO_CORES = {
    Elemento.FOGO: (255, 100, 0),
    Elemento.GELO: (150, 220, 255),
    Elemento.RAIO: (255, 255, 100),
    Elemento.TREVAS: (80, 0, 120),
    Elemento.LUZ: (255, 255, 220),
    Elemento.NATUREZA: (100, 200, 80),
    Elemento.ARCANO: (180, 100, 255),
    Elemento.CAOS: (255, 50, 150),
    Elemento.VOID: (30, 0, 50),
    Elemento.SANGUE: (180, 0, 30),
    Elemento.TEMPO: (200, 180, 255),
    Elemento.GRAVITACAO: (100, 50, 150),
}

# Reações elementais: (elem1, elem2) -> (nome_reacao, efeito, multiplicador_dano)
REACOES_ELEMENTAIS = {
    # Fogo + Gelo = Evaporação (dano + cegueira)
    (Elemento.FOGO, Elemento.GELO): ("EVAPORACAO", "CEGUEIRA", 1.5),
    (Elemento.GELO, Elemento.FOGO): ("EVAPORACAO", "CEGUEIRA", 1.5),
    
    # Fogo + Raio = Combustão (explosão massiva)
    (Elemento.FOGO, Elemento.RAIO): ("COMBUSTAO", "EXPLOSAO_MASSIVA", 2.0),
    (Elemento.RAIO, Elemento.FOGO): ("COMBUSTAO", "EXPLOSAO_MASSIVA", 2.0),
    
    # Gelo + Raio = Supercondução (dano amplificado + paralisia)
    (Elemento.GELO, Elemento.RAIO): ("SUPERCONDUCAO", "PARALISIA", 1.8),
    (Elemento.RAIO, Elemento.GELO): ("SUPERCONDUCAO", "PARALISIA", 1.8),
    
    # Fogo + Natureza = Incêndio (DoT massivo)
    (Elemento.FOGO, Elemento.NATUREZA): ("INCENDIO", "QUEIMADURA_SEVERA", 1.3),
    (Elemento.NATUREZA, Elemento.FOGO): ("INCENDIO", "QUEIMADURA_SEVERA", 1.3),
    
    # Gelo + Natureza = Hibernação (stun longo)
    (Elemento.GELO, Elemento.NATUREZA): ("HIBERNACAO", "SONO", 1.2),
    (Elemento.NATUREZA, Elemento.GELO): ("HIBERNACAO", "SONO", 1.2),
    
    # Raio + Natureza = Eletrificação (chain lightning)
    (Elemento.RAIO, Elemento.NATUREZA): ("ELETRIFICACAO", "CHAIN", 1.4),
    (Elemento.NATUREZA, Elemento.RAIO): ("ELETRIFICACAO", "CHAIN", 1.4),
    
    # Trevas + Luz = Caos Primordial (dano aleatório massivo)
    (Elemento.TREVAS, Elemento.LUZ): ("CAOS_PRIMORDIAL", "DANO_ALEATORIO", 2.5),
    (Elemento.LUZ, Elemento.TREVAS): ("CAOS_PRIMORDIAL", "DANO_ALEATORIO", 2.5),
    
    # Trevas + Fogo = Chamas Negras (ignora defesa)
    (Elemento.TREVAS, Elemento.FOGO): ("CHAMAS_NEGRAS", "IGNORA_DEFESA", 1.6),
    (Elemento.FOGO, Elemento.TREVAS): ("CHAMAS_NEGRAS", "IGNORA_DEFESA", 1.6),
    
    # Luz + Gelo = Prisma (reflete dano)
    (Elemento.LUZ, Elemento.GELO): ("PRISMA", "REFLEXAO", 1.3),
    (Elemento.GELO, Elemento.LUZ): ("PRISMA", "REFLEXAO", 1.3),
    
    # Arcano + qualquer = Amplificação
    (Elemento.ARCANO, Elemento.FOGO): ("AMPLIFICACAO", "DANO_BONUS", 1.5),
    (Elemento.ARCANO, Elemento.GELO): ("AMPLIFICACAO", "DANO_BONUS", 1.5),
    (Elemento.ARCANO, Elemento.RAIO): ("AMPLIFICACAO", "DANO_BONUS", 1.5),
    (Elemento.ARCANO, Elemento.TREVAS): ("AMPLIFICACAO", "DANO_BONUS", 1.5),
    (Elemento.ARCANO, Elemento.LUZ): ("AMPLIFICACAO", "DANO_BONUS", 1.5),
    
    # Void + qualquer = Aniquilação (remove buffs + dano)
    (Elemento.VOID, Elemento.FOGO): ("ANIQUILACAO", "PURGE", 1.4),
    (Elemento.VOID, Elemento.GELO): ("ANIQUILACAO", "PURGE", 1.4),
    (Elemento.VOID, Elemento.RAIO): ("ANIQUILACAO", "PURGE", 1.4),
    
    # Sangue + Trevas = Corrupção (drena vida massivo)
    (Elemento.SANGUE, Elemento.TREVAS): ("CORRUPCAO", "DRAIN_MASSIVO", 1.7),
    (Elemento.TREVAS, Elemento.SANGUE): ("CORRUPCAO", "DRAIN_MASSIVO", 1.7),
    
    # Tempo + Gravitação = Singularidade (puxa e stun)
    (Elemento.TEMPO, Elemento.GRAVITACAO): ("SINGULARIDADE", "VORTEX", 2.0),
    (Elemento.GRAVITACAO, Elemento.TEMPO): ("SINGULARIDADE", "VORTEX", 2.0),
}


# =============================================================================
# STATUS EFFECTS EXPANDIDOS
# =============================================================================

@dataclass
class StatusEffect:
    """Classe base para todos os status effects"""
    nome: str
    duracao: float
    tempo_restante: float = field(init=False)
    stackable: bool = False
    max_stacks: int = 1
    stacks: int = 1
    
    # Efeitos
    dano_por_tick: float = 0.0
    tick_interval: float = 0.5
    tempo_ultimo_tick: float = 0.0
    
    # Modificadores
    mod_velocidade: float = 1.0
    mod_dano_recebido: float = 1.0
    mod_dano_causado: float = 1.0
    mod_cura_recebida: float = 1.0
    mod_cooldown: float = 1.0
    mod_mana_custo: float = 1.0
    
    # Flags
    pode_mover: bool = True
    pode_atacar: bool = True
    pode_usar_skill: bool = True
    invisivel: bool = False
    intangivel: bool = False
    
    # Visual
    cor: Tuple[int, int, int] = (255, 255, 255)
    particulas: bool = False
    
    def __post_init__(self):
        self.tempo_restante = self.duracao
    
    def update(self, dt: float, alvo) -> Tuple[bool, float]:
        """
        Atualiza o status effect.
        Retorna (ainda_ativo, dano_causado)
        """
        self.tempo_restante -= dt
        dano = 0.0
        
        # Processa ticks de dano
        if self.dano_por_tick > 0:
            self.tempo_ultimo_tick += dt
            if self.tempo_ultimo_tick >= self.tick_interval:
                self.tempo_ultimo_tick = 0
                dano = self.dano_por_tick * self.stacks
        
        return self.tempo_restante > 0, dano
    
    def on_apply(self, alvo):
        """Chamado quando o efeito é aplicado"""
        pass
    
    def on_remove(self, alvo):
        """Chamado quando o efeito é removido"""
        pass
    
    def on_stack(self):
        """Chamado quando o efeito recebe mais stacks"""
        if self.stackable and self.stacks < self.max_stacks:
            self.stacks += 1
            self.tempo_restante = self.duracao  # Renova duração


# =============================================================================
# DEFINIÇÕES DE STATUS EFFECTS
# =============================================================================

STATUS_EFFECTS_DB = {
    # =========================================================================
    # CROWD CONTROL (CC)
    # =========================================================================
    "ATORDOADO": {
        "nome": "Atordoado",
        "duracao": 1.5,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "cor": (255, 255, 100),
        "descricao": "Incapaz de agir"
    },
    "CONGELADO": {
        "nome": "Congelado",
        "duracao": 2.0,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "mod_dano_recebido": 1.5,  # Recebe 50% mais dano
        "cor": (150, 220, 255),
        "descricao": "Completamente imóvel, vulnerável a dano"
    },
    "ENRAIZADO": {
        "nome": "Enraizado",
        "duracao": 2.5,
        "pode_mover": False,
        "pode_atacar": True,  # Pode atacar!
        "pode_usar_skill": True,
        "cor": (100, 150, 50),
        "descricao": "Preso no lugar mas pode atacar"
    },
    "SILENCIADO": {
        "nome": "Silenciado",
        "duracao": 3.0,
        "pode_mover": True,
        "pode_atacar": True,
        "pode_usar_skill": False,  # Não pode usar skills
        "cor": (150, 50, 150),
        "descricao": "Incapaz de usar habilidades"
    },
    "CEGO": {
        "nome": "Cego",
        "duracao": 2.0,
        "mod_velocidade": 0.5,  # Move mais devagar
        "cor": (50, 50, 50),
        "descricao": "Visão prejudicada, movimento lento"
    },
    "MEDO": {
        "nome": "Medo",
        "duracao": 2.0,
        "pode_atacar": False,
        "cor": (100, 0, 100),
        "descricao": "Foge em pânico, não pode atacar"
    },
    "CHARME": {
        "nome": "Charme",
        "duracao": 2.5,
        "pode_atacar": False,
        "cor": (255, 100, 200),
        "descricao": "Encantado, caminha em direção ao conjurador"
    },
    "SONO": {
        "nome": "Sono",
        "duracao": 4.0,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "mod_dano_recebido": 2.0,  # DOBRO de dano!
        "cor": (200, 200, 255),
        "descricao": "Dorme profundamente - acorda ao tomar dano (dano dobrado)"
    },
    "PARALISIA": {
        "nome": "Paralisia",
        "duracao": 1.0,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "cor": (255, 255, 150),
        "descricao": "Choque elétrico paralisante"
    },
    "KNOCK_UP": {
        "nome": "Knock Up",
        "duracao": 0.8,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "cor": (200, 200, 200),
        "descricao": "Jogado para o ar"
    },
    "PUXADO": {
        "nome": "Puxado",
        "duracao": 0.5,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "cor": (100, 50, 150),
        "descricao": "Sendo puxado para um ponto"
    },
    
    # =========================================================================
    # DANO OVER TIME (DoT)
    # =========================================================================
    "QUEIMANDO": {
        "nome": "Queimando",
        "duracao": 4.0,
        "dano_por_tick": 8.0,
        "tick_interval": 0.5,
        "stackable": True,
        "max_stacks": 5,
        "cor": (255, 100, 0),
        "particulas": True,
        "descricao": "Dano de fogo contínuo"
    },
    "ENVENENADO": {
        "nome": "Envenenado",
        "duracao": 6.0,
        "dano_por_tick": 5.0,
        "tick_interval": 1.0,
        "stackable": True,
        "max_stacks": 10,
        "mod_cura_recebida": 0.5,  # 50% menos cura
        "cor": (100, 255, 100),
        "particulas": True,
        "descricao": "Dano de veneno e cura reduzida"
    },
    "SANGRANDO": {
        "nome": "Sangrando",
        "duracao": 5.0,
        "dano_por_tick": 6.0,
        "tick_interval": 0.5,
        "stackable": True,
        "max_stacks": 5,
        "cor": (180, 0, 30),
        "particulas": True,
        "descricao": "Perde sangue continuamente"
    },
    "CORROENDO": {
        "nome": "Corroendo",
        "duracao": 4.0,
        "dano_por_tick": 4.0,
        "tick_interval": 0.5,
        "mod_dano_recebido": 1.2,  # +20% dano recebido
        "stackable": True,
        "max_stacks": 3,
        "cor": (150, 100, 50),
        "descricao": "Armadura sendo corroída"
    },
    "MALDITO": {
        "nome": "Maldito",
        "duracao": 8.0,
        "dano_por_tick": 3.0,
        "tick_interval": 1.0,
        "mod_dano_causado": 0.8,  # -20% dano causado
        "mod_cura_recebida": 0.5,
        "cor": (80, 0, 100),
        "descricao": "Maldição que enfraquece"
    },
    "NECROSE": {
        "nome": "Necrose",
        "duracao": 5.0,
        "dano_por_tick": 10.0,  # Dano alto
        "tick_interval": 1.0,
        "mod_cura_recebida": 0.0,  # SEM CURA!
        "cor": (30, 30, 30),
        "descricao": "Tecido morrendo, cura impossível"
    },
    
    # =========================================================================
    # DEBUFFS
    # =========================================================================
    "LENTO": {
        "nome": "Lento",
        "duracao": 3.0,
        "mod_velocidade": 0.5,
        "stackable": True,
        "max_stacks": 3,
        "cor": (100, 200, 255),
        "descricao": "Movimento desacelerado"
    },
    "FRACO": {
        "nome": "Fraco",
        "duracao": 4.0,
        "mod_dano_causado": 0.6,  # -40% dano
        "cor": (150, 100, 100),
        "descricao": "Dano causado reduzido"
    },
    "VULNERAVEL": {
        "nome": "Vulnerável",
        "duracao": 4.0,
        "mod_dano_recebido": 1.5,  # +50% dano recebido
        "cor": (255, 150, 150),
        "descricao": "Recebe mais dano"
    },
    "EXAUSTO": {
        "nome": "Exausto",
        "duracao": 5.0,
        "mod_cooldown": 1.5,  # +50% cooldown
        "mod_mana_custo": 1.5,  # +50% custo de mana
        "mod_velocidade": 0.8,
        "cor": (150, 150, 150),
        "descricao": "Skills mais lentas e custosas"
    },
    "MARCADO": {
        "nome": "Marcado",
        "duracao": 6.0,
        "mod_dano_recebido": 1.3,
        "cor": (255, 0, 0),
        "descricao": "Marcado para morte"
    },
    "EXPOSTO": {
        "nome": "Exposto",
        "duracao": 3.0,
        "mod_dano_recebido": 2.0,  # DOBRO!
        "cor": (255, 200, 100),
        "descricao": "Defesas completamente abertas"
    },
    
    # =========================================================================
    # BUFFS
    # =========================================================================
    "ACELERADO": {
        "nome": "Acelerado",
        "duracao": 5.0,
        "mod_velocidade": 1.5,  # +50% velocidade
        "cor": (255, 255, 150),
        "descricao": "Movimento acelerado"
    },
    "FORTALECIDO": {
        "nome": "Fortalecido",
        "duracao": 6.0,
        "mod_dano_causado": 1.5,  # +50% dano
        "cor": (255, 100, 100),
        "descricao": "Dano aumentado"
    },
    "BLINDADO": {
        "nome": "Blindado",
        "duracao": 5.0,
        "mod_dano_recebido": 0.5,  # -50% dano recebido
        "cor": (150, 150, 200),
        "descricao": "Resistência aumentada"
    },
    "REGENERANDO": {
        "nome": "Regenerando",
        "duracao": 6.0,
        "dano_por_tick": -8.0,  # CURA!
        "tick_interval": 0.5,
        "cor": (100, 255, 150),
        "particulas": True,
        "descricao": "Recuperando vida"
    },
    "ESCUDO_MAGICO": {
        "nome": "Escudo Mágico",
        "duracao": 8.0,
        "mod_dano_recebido": 0.7,
        "cor": (100, 150, 255),
        "descricao": "Barreira mágica protetora"
    },
    "FURIA": {
        "nome": "Fúria",
        "duracao": 4.0,
        "mod_dano_causado": 1.8,  # +80% dano
        "mod_velocidade": 1.2,
        "mod_dano_recebido": 1.3,  # +30% dano recebido
        "cor": (255, 50, 50),
        "descricao": "Fúria berserker - mais dano, mais vulnerável"
    },
    "INVISIVEL": {
        "nome": "Invisível",
        "duracao": 4.0,
        "invisivel": True,
        "cor": (200, 200, 200),
        "descricao": "Invisibilidade - quebra ao atacar"
    },
    "INTANGIVEL": {
        "nome": "Intangível",
        "duracao": 2.0,
        "intangivel": True,
        "pode_atacar": False,
        "cor": (180, 180, 255),
        "descricao": "Forma etérea - imune mas não pode atacar"
    },
    "DETERMINADO": {
        "nome": "Determinado",
        "duracao": 5.0,
        "mod_cooldown": 0.5,  # -50% cooldown
        "cor": (255, 200, 100),
        "descricao": "Cooldowns reduzidos"
    },
    "ABENÇOADO": {
        "nome": "Abençoado",
        "duracao": 8.0,
        "mod_cura_recebida": 1.5,  # +50% cura
        "dano_por_tick": -3.0,  # Cura leve
        "tick_interval": 1.0,
        "cor": (255, 255, 200),
        "descricao": "Bênção divina"
    },
    
    # =========================================================================
    # ESPECIAIS
    # =========================================================================
    "TEMPO_PARADO": {
        "nome": "Tempo Parado",
        "duracao": 2.0,
        "pode_mover": False,
        "pode_atacar": False,
        "pode_usar_skill": False,
        "intangivel": True,  # Não recebe dano durante
        "cor": (200, 180, 255),
        "descricao": "Preso no tempo, invulnerável"
    },
    "VORTEX": {
        "nome": "Vórtex",
        "duracao": 3.0,
        "pode_mover": False,
        "dano_por_tick": 5.0,
        "tick_interval": 0.3,
        "cor": (100, 50, 150),
        "descricao": "Sendo sugado por um vórtex"
    },
    "POSSESSO": {
        "nome": "Possesso",
        "duracao": 3.0,
        "cor": (150, 0, 150),
        "descricao": "Mente controlada - ataca aliados"
    },
    "RESSURREICAO": {
        "nome": "Ressurreição",
        "duracao": 0.1,  # Instantâneo
        "cor": (255, 255, 200),
        "descricao": "Revive com 30% HP"
    },
    "IMORTAL": {
        "nome": "Imortal",
        "duracao": 3.0,
        "cor": (255, 215, 0),
        "descricao": "Não pode morrer (HP mínimo 1)"
    },
    "ESPELHADO": {
        "nome": "Espelhado",
        "duracao": 4.0,
        "cor": (200, 200, 255),
        "descricao": "Reflete 50% do dano recebido"
    },
    "LINK_ALMA": {
        "nome": "Link de Alma",
        "duracao": 6.0,
        "cor": (255, 100, 255),
        "descricao": "Dano dividido com o conjurador"
    },
    "BOMBA_RELOGIO": {
        "nome": "Bomba Relógio",
        "duracao": 3.0,
        "cor": (255, 100, 0),
        "descricao": "Explode após a duração causando dano massivo"
    },
}


# =============================================================================
# CONDIÇÕES ESPECIAIS DE ATIVAÇÃO
# =============================================================================

CONDICOES_SKILL = {
    "SEMPRE": lambda caster, alvo: True,
    "ALVO_BAIXA_VIDA": lambda caster, alvo: alvo.vida / alvo.vida_max < 0.3,
    "ALVO_ALTA_VIDA": lambda caster, alvo: alvo.vida / alvo.vida_max > 0.7,
    "CASTER_BAIXA_VIDA": lambda caster, alvo: caster.vida / caster.vida_max < 0.3,
    "CASTER_ALTA_VIDA": lambda caster, alvo: caster.vida / caster.vida_max > 0.7,
    "ALVO_ATORDOADO": lambda caster, alvo: any(e.nome == "Atordoado" for e in getattr(alvo, 'status_effects', [])),
    "ALVO_QUEIMANDO": lambda caster, alvo: any(e.nome == "Queimando" for e in getattr(alvo, 'status_effects', [])),
    "ALVO_CONGELADO": lambda caster, alvo: any(e.nome == "Congelado" for e in getattr(alvo, 'status_effects', [])),
    "ALVO_ENVENENADO": lambda caster, alvo: any(e.nome == "Envenenado" for e in getattr(alvo, 'status_effects', [])),
    "ALVO_DEBUFFADO": lambda caster, alvo: len([e for e in getattr(alvo, 'status_effects', []) if e.mod_dano_recebido > 1.0]) > 0,
    "ALVO_NO_AR": lambda caster, alvo: getattr(alvo, 'z', 0) > 0.5,
    "COSTAS_ALVO": lambda caster, alvo: _esta_nas_costas(caster, alvo),
    "DISTANCIA_CURTA": lambda caster, alvo: _distancia(caster, alvo) < 2.0,
    "DISTANCIA_LONGA": lambda caster, alvo: _distancia(caster, alvo) > 5.0,
    "COMBO_ATIVO": lambda caster, alvo: getattr(caster, 'combo_count', 0) >= 3,
    "MANA_CHEIA": lambda caster, alvo: caster.mana >= caster.mana_max * 0.9,
    "ULTIMO_HIT": lambda caster, alvo: alvo.vida <= caster.dados.forca * 2,
}


def _distancia(a, b):
    """Calcula distância entre duas entidades"""
    return math.sqrt((a.pos[0] - b.pos[0])**2 + (a.pos[1] - b.pos[1])**2)


def _esta_nas_costas(caster, alvo):
    """Verifica se caster está nas costas do alvo"""
    ang_para_caster = math.atan2(caster.pos[1] - alvo.pos[1], caster.pos[0] - alvo.pos[0])
    ang_olhar = getattr(alvo, 'angulo_olhar', 0)
    diff = abs(ang_para_caster - ang_olhar)
    if diff > math.pi:
        diff = 2 * math.pi - diff
    return diff > math.pi * 0.6  # > 108 graus = nas costas


# =============================================================================
# AMPLIFICADORES E MODIFICADORES DE MAGIA
# =============================================================================

MODIFICADORES_MAGIA = {
    # Amplificação de dano baseado em elemento
    "AFINIDADE_FOGO": {"elementos": [Elemento.FOGO], "mod_dano": 1.3},
    "AFINIDADE_GELO": {"elementos": [Elemento.GELO], "mod_dano": 1.3},
    "AFINIDADE_RAIO": {"elementos": [Elemento.RAIO], "mod_dano": 1.3},
    "AFINIDADE_TREVAS": {"elementos": [Elemento.TREVAS], "mod_dano": 1.3},
    "AFINIDADE_LUZ": {"elementos": [Elemento.LUZ], "mod_dano": 1.3},
    
    # Modificadores de efeito
    "PROLONGAR": {"mod_duracao_status": 1.5},
    "INTENSIFICAR": {"mod_dano_dot": 1.5},
    "PROPAGAR": {"mod_area": 1.3},
    "PERFURAR": {"ignora_escudo": True},
    "VAMPIRISMO": {"lifesteal": 0.2},
    
    # Modificadores de custo
    "EFICIENCIA": {"mod_custo_mana": 0.7},
    "SOBRECARGA": {"mod_custo_mana": 1.5, "mod_dano": 1.8},
    
    # Modificadores especiais
    "CRITICO_MAGICO": {"crit_chance": 0.25, "crit_mult": 2.0},
    "PENETRACAO": {"ignora_resistencia": 0.5},
    "RICOCHETE": {"bounce": 2},  # Reflete em até 2 alvos
    "EXPLOSIVO": {"on_hit_explosion": True, "explosion_radius": 1.5},
}


# =============================================================================
# COMBOS MÁGICOS
# =============================================================================

# Sequências de elementos que criam efeitos especiais
COMBOS_MAGICOS = {
    # Fogo -> Fogo -> Fogo = Inferno
    ("FOGO", "FOGO", "FOGO"): {
        "nome": "INFERNO",
        "bonus_dano": 2.0,
        "efeito_bonus": "QUEIMADURA_SEVERA",
        "visual": "inferno_explosion"
    },
    # Gelo -> Gelo -> Gelo = Zero Absoluto
    ("GELO", "GELO", "GELO"): {
        "nome": "ZERO_ABSOLUTO",
        "bonus_dano": 1.5,
        "efeito_bonus": "CONGELADO",
        "duracao_bonus": 2.0,
        "visual": "freeze_shatter"
    },
    # Raio -> Raio -> Raio = Tempestade Elétrica
    ("RAIO", "RAIO", "RAIO"): {
        "nome": "TEMPESTADE_ELETRICA",
        "bonus_dano": 1.8,
        "efeito_bonus": "CHAIN",
        "chain_count": 5,
        "visual": "lightning_storm"
    },
    # Fogo -> Gelo -> Raio = Caos Elemental
    ("FOGO", "GELO", "RAIO"): {
        "nome": "CAOS_ELEMENTAL",
        "bonus_dano": 2.5,
        "efeito_bonus": "RANDOM_STATUS",
        "visual": "elemental_chaos"
    },
    # Trevas -> Sangue -> Trevas = Ritual Sombrio
    ("TREVAS", "SANGUE", "TREVAS"): {
        "nome": "RITUAL_SOMBRIO",
        "bonus_dano": 1.5,
        "efeito_bonus": "DRAIN_MASSIVO",
        "lifesteal": 0.5,
        "visual": "dark_ritual"
    },
    # Luz -> Luz -> Luz = Julgamento Divino
    ("LUZ", "LUZ", "LUZ"): {
        "nome": "JULGAMENTO_DIVINO",
        "bonus_dano": 2.0,
        "efeito_bonus": "EXPOSTO",
        "cura_caster": 0.2,
        "visual": "divine_judgment"
    },
    # Natureza -> Veneno -> Natureza = Praga
    ("NATUREZA", "VENENO", "NATUREZA"): {
        "nome": "PRAGA",
        "bonus_dano": 1.3,
        "efeito_bonus": "ENVENENADO",
        "stacks_bonus": 5,
        "visual": "plague_spread"
    },
    # Tempo -> Arcano -> Tempo = Paradoxo Temporal
    ("TEMPO", "ARCANO", "TEMPO"): {
        "nome": "PARADOXO_TEMPORAL",
        "bonus_dano": 1.5,
        "efeito_bonus": "TEMPO_PARADO",
        "reset_cooldowns": True,
        "visual": "time_paradox"
    },
}


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def criar_status_effect(nome: str, duracao_override: float = None) -> Optional[StatusEffect]:
    """Cria um status effect a partir do banco de dados"""
    if nome not in STATUS_EFFECTS_DB:
        return None
    
    dados = STATUS_EFFECTS_DB[nome].copy()
    duracao = duracao_override if duracao_override else dados.pop("duracao", 1.0)
    nome_display = dados.pop("nome", nome)
    descricao = dados.pop("descricao", "")
    
    effect = StatusEffect(nome=nome_display, duracao=duracao)
    
    # Aplica propriedades
    for key, value in dados.items():
        if hasattr(effect, key):
            setattr(effect, key, value)
    
    return effect


def verificar_reacao_elemental(elem1: Elemento, elem2: Elemento) -> Optional[Tuple[str, str, float]]:
    """Verifica se há reação entre dois elementos"""
    return REACOES_ELEMENTAIS.get((elem1, elem2))


def verificar_combo_magico(sequencia: List[str]) -> Optional[Dict]:
    """Verifica se uma sequência de elementos forma um combo"""
    if len(sequencia) < 3:
        return None
    
    # Pega os últimos 3 elementos
    ultimos = tuple(sequencia[-3:])
    return COMBOS_MAGICOS.get(ultimos)


def verificar_condicao(nome_condicao: str, caster, alvo) -> bool:
    """Verifica se uma condição de skill é satisfeita"""
    if nome_condicao not in CONDICOES_SKILL:
        return True  # Condição desconhecida = sempre verdadeiro
    
    try:
        return CONDICOES_SKILL[nome_condicao](caster, alvo)
    except:
        return False


def calcular_dano_magico(dano_base: float, caster, alvo, elemento: Elemento = None,
                         modificadores: List[str] = None) -> Tuple[float, bool, List[str]]:
    """
    Calcula dano mágico final com todos os modificadores.
    Retorna (dano_final, is_critico, lista_de_efeitos_aplicados)
    """
    dano = dano_base
    is_critico = False
    efeitos = []
    
    # Aplica modificadores do caster
    if modificadores:
        for mod_nome in modificadores:
            if mod_nome in MODIFICADORES_MAGIA:
                mod = MODIFICADORES_MAGIA[mod_nome]
                
                # Modificador de dano geral
                if "mod_dano" in mod:
                    dano *= mod["mod_dano"]
                
                # Modificador específico de elemento
                if elemento and "elementos" in mod and elemento in mod["elementos"]:
                    dano *= mod.get("mod_dano", 1.0)
                
                # Crítico mágico
                if "crit_chance" in mod:
                    if random.random() < mod["crit_chance"]:
                        is_critico = True
                        dano *= mod.get("crit_mult", 2.0)
                
                # Lifesteal
                if "lifesteal" in mod:
                    efeitos.append(f"LIFESTEAL_{int(mod['lifesteal'] * 100)}")
    
    # Aplica modificadores do alvo (debuffs)
    if hasattr(alvo, 'status_effects'):
        for effect in alvo.status_effects:
            dano *= effect.mod_dano_recebido
    
    # Aplica modificadores do caster (buffs)
    if hasattr(caster, 'status_effects'):
        for effect in caster.status_effects:
            dano *= effect.mod_dano_causado
    
    return dano, is_critico, efeitos


# =============================================================================
# EXPORTAÇÕES
# =============================================================================

__all__ = [
    'Elemento',
    'ELEMENTO_CORES',
    'REACOES_ELEMENTAIS',
    'StatusEffect',
    'STATUS_EFFECTS_DB',
    'CONDICOES_SKILL',
    'MODIFICADORES_MAGIA',
    'COMBOS_MAGICOS',
    'criar_status_effect',
    'verificar_reacao_elemental',
    'verificar_combo_magico',
    'verificar_condicao',
    'calcular_dano_magico',
]
