"""
=============================================================================
NEURAL FIGHTS - Sistema de Estratégia de Skills v2.0 BATTLE PLAN EDITION
=============================================================================
Sistema inteligente que analisa TODAS as habilidades disponíveis e cria
um plano de batalha completo e consciente.

A IA agora:
- Conhece TODAS as suas habilidades e limitações
- Categoriza cada skill por PROPÓSITO (opener, finisher, sustain, escape, poke)
- Cria ROTAÇÕES de skills baseadas na fase do combate
- Adapta estratégia ao estado atual (HP, mana, distância)
- Entende SINERGIAS entre skills (freeze + shatter, burn + detonate)
- Define PRIORIDADES dinâmicas por situação
=============================================================================
"""

import random
import math
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from core.skills import get_skill_data


# =============================================================================
# ENUMS E CONSTANTES
# =============================================================================

class StrategicRole(Enum):
    """Papel estratégico principal baseado no kit de skills"""
    BURST_MAGE = "burst_mage"           # Combo rápido de dano alto
    CONTROL_MAGE = "control_mage"       # CC e debuffs
    SUMMONER = "summoner"               # Foco em invocações
    TRAP_MASTER = "trap_master"         # Controle de área
    BATTLE_MAGE = "battle_mage"         # Mix combate + magia
    BUFFER = "buffer"                   # Auto-buffs e sustain
    TRANSFORMER = "transformer"         # Transformações
    CHANNELER = "channeler"             # Skills canalizadas
    DASHER = "dasher"                   # Mobilidade agressiva
    ARTILLERY = "artillery"             # Dano à distância
    HYBRID = "hybrid"                   # Equilibrado


class SkillPurpose(Enum):
    """Propósito de uma skill no plano de batalha"""
    OPENER = "opener"           # Iniciar combate (buffs, summons)
    POKE = "poke"               # Dano à distância segura
    ENGAGE = "engage"           # Entrar no combate (dash ofensivo)
    BURST = "burst"             # Dano alto rápido
    SUSTAIN = "sustain"         # Manter-se vivo (cura, escudo)
    CONTROL = "control"         # CC (stun, slow, root)
    FINISHER = "finisher"       # Matar inimigo com HP baixo
    ESCAPE = "escape"           # Fugir de perigo
    ZONING = "zoning"           # Controle de área (traps, AoE persistente)
    UTILITY = "utility"         # Utilidade geral


class CombatPhase(Enum):
    """Fase atual do combate"""
    OPENING = "opening"         # Início (0-5s) - buffs, summons
    NEUTRAL = "neutral"         # Neutro - poke, posicionamento
    ADVANTAGE = "advantage"     # Vantagem - pressionar
    DISADVANTAGE = "disadvantage"  # Desvantagem - defender, recuperar
    FINISHING = "finishing"     # Finalizando - burst final
    CRITICAL = "critical"       # HP crítico - sobreviver


class SkillPriority(Enum):
    """Prioridade de uso"""
    CRITICAL = 5      # Emergência (cura em HP crítico)
    VERY_HIGH = 4     # Muito alta (oportunidade perfeita)
    HIGH = 3          # Alta
    MEDIUM = 2        # Normal
    LOW = 1           # Baixa
    NONE = 0          # Não usar


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SkillProfile:
    """Perfil completo de uma skill"""
    nome: str
    tipo: str
    custo: float
    cooldown: float
    data: Dict
    fonte: str
    
    # Propósitos (uma skill pode ter múltiplos)
    propositos: List[SkillPurpose] = field(default_factory=list)
    proposito_principal: SkillPurpose = SkillPurpose.UTILITY
    
    # Métricas calculadas
    dano_total: float = 0.0
    alcance_efetivo: float = 0.0
    tempo_efeito: float = 0.0
    dano_por_mana: float = 0.0  # Eficiência
    
    # Condições ideais de uso
    distancia_min: float = 0.0
    distancia_max: float = 999.0
    hp_proprio_min: float = 0.0
    hp_proprio_max: float = 1.0
    hp_inimigo_min: float = 0.0
    hp_inimigo_max: float = 1.0
    
    # Flags especiais
    requer_setup: bool = False
    setup_skill: Optional[str] = None  # Skill que prepara esta
    pode_combo_apos: List[str] = field(default_factory=list)
    
    # Scores
    score_ofensivo: float = 0.0
    score_defensivo: float = 0.0
    score_utilidade: float = 0.0


@dataclass
class BattlePlan:
    """Plano de batalha baseado nas skills disponíveis"""
    # Rotações por fase
    rotacao_opening: List[str] = field(default_factory=list)
    rotacao_neutral: List[str] = field(default_factory=list)
    rotacao_advantage: List[str] = field(default_factory=list)
    rotacao_disadvantage: List[str] = field(default_factory=list)
    rotacao_finishing: List[str] = field(default_factory=list)
    rotacao_critical: List[str] = field(default_factory=list)
    
    # Skills por propósito
    openers: List[str] = field(default_factory=list)
    pokes: List[str] = field(default_factory=list)
    engages: List[str] = field(default_factory=list)
    bursts: List[str] = field(default_factory=list)
    sustains: List[str] = field(default_factory=list)
    controls: List[str] = field(default_factory=list)
    finishers: List[str] = field(default_factory=list)
    escapes: List[str] = field(default_factory=list)
    
    # Combos descobertos
    combos: List[Tuple[str, str, str]] = field(default_factory=list)
    
    # Estratégia geral
    distancia_preferida: float = 3.0
    estilo: str = "balanced"  # "aggressive", "defensive", "balanced", "kite"
    foco_mana: str = "balanced"  # "conserve", "balanced", "spam"


@dataclass
class CombatSituation:
    """Estado atual do combate"""
    distancia: float
    meu_hp_percent: float
    inimigo_hp_percent: float
    meu_mana_percent: float
    estou_encurralado: bool = False
    inimigo_encurralado: bool = False
    inimigo_atacando: bool = False
    inimigo_stunado: bool = False
    tenho_summons_ativos: int = 0
    tenho_traps_ativos: int = 0
    tenho_buffs_ativos: int = 0
    inimigo_debuffado: bool = False
    momentum: float = 0.0
    tempo_combate: float = 0.0
    fase: CombatPhase = CombatPhase.NEUTRAL


# =============================================================================
# SISTEMA PRINCIPAL DE ESTRATÉGIA
# =============================================================================

class SkillStrategySystem:
    """
    Sistema central de estratégia de skills v2.0
    Cria e executa planos de batalha baseados no kit de habilidades.
    """
    
    def __init__(self, parent, brain):
        self.parent = parent
        self.brain = brain
        
        # Todas as skills analisadas
        self.skills: Dict[str, SkillProfile] = {}
        self.todas_skills = self.skills  # Alias para compatibilidade
        self.skills_por_tipo: Dict[str, List[SkillProfile]] = {
            "PROJETIL": [], "BEAM": [], "AREA": [], "DASH": [],
            "BUFF": [], "SUMMON": [], "TRAP": [], "TRANSFORM": [], "CHANNEL": []
        }
        self.skills_por_proposito: Dict[SkillPurpose, List[SkillProfile]] = {
            p: [] for p in SkillPurpose
        }
        
        # Plano de batalha
        self.plano: BattlePlan = BattlePlan()
        self.role_principal: StrategicRole = StrategicRole.HYBRID
        
        # Preferências (compatibilidade)
        self.preferencias = {
            "distancia_preferida": 3.0,
            "estilo_kite": False,
        }
        
        # Estado de execução
        self.fase_atual: CombatPhase = CombatPhase.OPENING
        self.rotacao_index: int = 0
        self.ultima_skill: Optional[str] = None
        self.skills_usadas: List[str] = []
        self.combo_em_andamento: Optional[List[str]] = None
        self.combo_index: int = 0
        
        # Combos (compatibilidade)
        self.combos_disponiveis: List[Tuple[str, str, str]] = []
        
        # Cooldowns internos
        self.cd_global: float = 0.0
        self.cd_por_tipo: Dict[str, float] = {
            "SUMMON": 0.0, "TRAP": 0.0, "TRANSFORM": 0.0, "BUFF": 0.0
        }
        
        # Análise e criação do plano
        self._analisar_todas_skills()
        self._categorizar_por_proposito()
        self._calcular_role()
        self._criar_plano_batalha()
        self._descobrir_combos()
        
        # Atualiza alias
        self.combos_disponiveis = self.plano.combos
        self.preferencias["distancia_preferida"] = self.plano.distancia_preferida
        self.preferencias["estilo_kite"] = self.plano.estilo == "kite"
        
        # Log do plano
        self._log_plano()
    
    # =========================================================================
    # ANÁLISE DE SKILLS
    # =========================================================================
    
    def _analisar_todas_skills(self):
        """Analisa TODAS as skills disponíveis do personagem"""
        p = self.parent
        
        # Skills da arma
        for skill_info in getattr(p, 'skills_arma', []):
            self._analisar_skill(skill_info, "arma")
        
        # Skills da classe
        for skill_info in getattr(p, 'skills_classe', []):
            self._analisar_skill(skill_info, "classe")
    
    def _analisar_skill(self, skill_info: Dict, fonte: str):
        """Analisa uma skill individual em profundidade"""
        nome = skill_info.get("nome", "Nenhuma")
        if nome == "Nenhuma" or nome in self.skills:
            return
        
        data = skill_info.get("data", get_skill_data(nome))
        tipo = data.get("tipo", "NADA")
        if tipo == "NADA":
            return
        
        custo = skill_info.get("custo", data.get("custo", 15))
        cooldown = data.get("cooldown", 5.0)
        
        # Cria perfil
        perfil = SkillProfile(
            nome=nome,
            tipo=tipo,
            custo=custo,
            cooldown=cooldown,
            data=data,
            fonte=fonte
        )
        
        # Calcula métricas
        self._calcular_metricas(perfil)
        
        # Determina propósitos
        self._determinar_propositos(perfil)
        
        # Calcula scores
        self._calcular_scores(perfil)
        
        # Armazena
        self.skills[nome] = perfil
        if tipo in self.skills_por_tipo:
            self.skills_por_tipo[tipo].append(perfil)
    
    def _calcular_metricas(self, perfil: SkillProfile):
        """Calcula métricas numéricas da skill"""
        data = perfil.data
        tipo = perfil.tipo
        
        # Dano total
        perfil.dano_total = data.get("dano", 0)
        if data.get("dano_tick"):
            duracao = data.get("duracao", 3.0)
            perfil.dano_total += data["dano_tick"] * duracao
        if data.get("dano_por_segundo"):
            duracao = data.get("duracao_max", 3.0)
            perfil.dano_total += data["dano_por_segundo"] * duracao
        if tipo == "SUMMON":
            duracao = data.get("duracao", 10)
            summon_dano = data.get("summon_dano", 10)
            perfil.dano_total = summon_dano * duracao * 0.5  # Estimativa
        
        # Alcance efetivo
        if tipo == "PROJETIL":
            vel = data.get("velocidade", 10)
            vida = data.get("vida", 1.5)
            perfil.alcance_efetivo = vel * vida * 0.8
        elif tipo == "BEAM":
            perfil.alcance_efetivo = data.get("alcance", 6.0)
        elif tipo == "AREA":
            perfil.alcance_efetivo = data.get("raio_area", 3.0)
        elif tipo == "DASH":
            perfil.alcance_efetivo = data.get("distancia", 4.0)
        else:
            perfil.alcance_efetivo = 0  # Self-cast
        
        # Eficiência de mana
        if perfil.custo > 0:
            perfil.dano_por_mana = perfil.dano_total / perfil.custo
        
        # Duração do efeito
        perfil.tempo_efeito = data.get("duracao", 0)
        
        # Condições de distância
        if tipo in ["PROJETIL", "BEAM"]:
            perfil.distancia_min = 2.0
            perfil.distancia_max = perfil.alcance_efetivo
        elif tipo == "AREA":
            perfil.distancia_min = 0
            perfil.distancia_max = perfil.alcance_efetivo + 1.0
        elif tipo == "DASH":
            perfil.distancia_min = 3.0
            perfil.distancia_max = perfil.alcance_efetivo + 3.0
    
    def _determinar_propositos(self, perfil: SkillProfile):
        """Determina os propósitos estratégicos da skill"""
        data = perfil.data
        tipo = perfil.tipo
        propositos = []
        
        # BUFFS
        if tipo == "BUFF":
            if data.get("cura") or data.get("cura_por_segundo"):
                propositos.append(SkillPurpose.SUSTAIN)
                perfil.hp_proprio_max = 0.7  # Usar quando HP < 70%
            if data.get("escudo"):
                propositos.append(SkillPurpose.SUSTAIN)
                propositos.append(SkillPurpose.OPENER)
            if data.get("buff_dano"):
                propositos.append(SkillPurpose.OPENER)
                propositos.append(SkillPurpose.BURST)
            if data.get("buff_velocidade"):
                propositos.append(SkillPurpose.ESCAPE)
                propositos.append(SkillPurpose.ENGAGE)
            if data.get("refletir"):
                propositos.append(SkillPurpose.SUSTAIN)
        
        # SUMMON
        elif tipo == "SUMMON":
            propositos.append(SkillPurpose.OPENER)  # Invocar no início
            propositos.append(SkillPurpose.SUSTAIN)  # Distração
            propositos.append(SkillPurpose.ZONING)   # Controle de área
        
        # TRAP
        elif tipo == "TRAP":
            propositos.append(SkillPurpose.ZONING)
            propositos.append(SkillPurpose.CONTROL)
            if data.get("bloqueia_movimento"):
                propositos.append(SkillPurpose.ESCAPE)
        
        # TRANSFORM
        elif tipo == "TRANSFORM":
            if data.get("bonus_resistencia", 0) > 0.3:
                propositos.append(SkillPurpose.SUSTAIN)
            if data.get("bonus_dano") or data.get("dano_contato"):
                propositos.append(SkillPurpose.BURST)
            propositos.append(SkillPurpose.OPENER)
        
        # DASH
        elif tipo == "DASH":
            if data.get("dano_chegada", 0) > 0 or data.get("dano", 0) > 0:
                propositos.append(SkillPurpose.ENGAGE)
                propositos.append(SkillPurpose.BURST)
            propositos.append(SkillPurpose.ESCAPE)
            if data.get("invencivel"):
                propositos.append(SkillPurpose.SUSTAIN)
        
        # PROJETIL
        elif tipo == "PROJETIL":
            if perfil.alcance_efetivo > 6:
                propositos.append(SkillPurpose.POKE)
            if perfil.dano_total > 40:
                propositos.append(SkillPurpose.BURST)
            if data.get("efeito") in ["LENTO", "PARALISIA", "CONGELADO", "ENRAIZADO"]:
                propositos.append(SkillPurpose.CONTROL)
            if data.get("condicao") == "ALVO_BAIXA_VIDA" or data.get("executa"):
                propositos.append(SkillPurpose.FINISHER)
                perfil.hp_inimigo_max = 0.3
        
        # BEAM
        elif tipo == "BEAM":
            propositos.append(SkillPurpose.POKE)
            if perfil.dano_total > 30:
                propositos.append(SkillPurpose.BURST)
            if data.get("efeito") in ["PARALISIA", "CEGO"]:
                propositos.append(SkillPurpose.CONTROL)
        
        # AREA
        elif tipo == "AREA":
            if perfil.dano_total > 40:
                propositos.append(SkillPurpose.BURST)
            if data.get("duracao", 0) > 2:
                propositos.append(SkillPurpose.ZONING)
            if data.get("efeito") in ["LENTO", "PARALISIA", "CONGELADO", "MEDO"]:
                propositos.append(SkillPurpose.CONTROL)
        
        # CHANNEL
        elif tipo == "CHANNEL":
            propositos.append(SkillPurpose.BURST)
            propositos.append(SkillPurpose.POKE)
        
        # Default
        if not propositos:
            propositos.append(SkillPurpose.UTILITY)
        
        perfil.propositos = propositos
        perfil.proposito_principal = propositos[0]
    
    def _calcular_scores(self, perfil: SkillProfile):
        """Calcula scores de ofensivo/defensivo/utilidade"""
        data = perfil.data
        
        # Ofensivo
        perfil.score_ofensivo = min(1.0, perfil.dano_total / 60)
        if perfil.proposito_principal in [SkillPurpose.BURST, SkillPurpose.POKE, SkillPurpose.FINISHER]:
            perfil.score_ofensivo += 0.2
        
        # Defensivo
        if data.get("cura") or data.get("escudo"):
            perfil.score_defensivo = 0.8
        if data.get("refletir"):
            perfil.score_defensivo = 0.7
        if perfil.tipo == "DASH":
            perfil.score_defensivo = 0.5
        if data.get("invencivel"):
            perfil.score_defensivo = 0.9
        
        # Utilidade
        if perfil.tipo in ["BUFF", "SUMMON", "TRAP"]:
            perfil.score_utilidade = 0.7
        if data.get("efeito") in ["LENTO", "PARALISIA", "CONGELADO"]:
            perfil.score_utilidade = 0.6
    
    def _categorizar_por_proposito(self):
        """Organiza skills por propósito"""
        for perfil in self.skills.values():
            for proposito in perfil.propositos:
                self.skills_por_proposito[proposito].append(perfil)
    
    # =========================================================================
    # DETERMINAÇÃO DE ROLE
    # =========================================================================
    
    def _calcular_role(self):
        """Determina o role estratégico baseado no kit"""
        contagem_tipo = {t: len(s) for t, s in self.skills_por_tipo.items()}
        contagem_prop = {p: len(s) for p, s in self.skills_por_proposito.items()}
        
        # Soma de dano total
        dano_total = sum(s.dano_total for s in self.skills.values())
        
        # Lógica de determinação
        if contagem_tipo["SUMMON"] >= 2:
            self.role_principal = StrategicRole.SUMMONER
        elif contagem_tipo["TRAP"] >= 2:
            self.role_principal = StrategicRole.TRAP_MASTER
        elif contagem_tipo["TRANSFORM"] >= 1 and contagem_tipo["BUFF"] >= 2:
            self.role_principal = StrategicRole.TRANSFORMER
        elif contagem_prop[SkillPurpose.BURST] >= 3 and dano_total > 150:
            self.role_principal = StrategicRole.BURST_MAGE
        elif contagem_prop[SkillPurpose.CONTROL] >= 2:
            self.role_principal = StrategicRole.CONTROL_MAGE
        elif contagem_prop[SkillPurpose.POKE] >= 2 and contagem_tipo["PROJETIL"] >= 2:
            self.role_principal = StrategicRole.ARTILLERY
        elif contagem_tipo["DASH"] >= 2:
            self.role_principal = StrategicRole.DASHER
        elif contagem_tipo["BUFF"] >= 3:
            self.role_principal = StrategicRole.BUFFER
        elif contagem_tipo["AREA"] >= 2 and contagem_tipo["PROJETIL"] >= 1:
            self.role_principal = StrategicRole.BATTLE_MAGE
        else:
            self.role_principal = StrategicRole.HYBRID
    
    # =========================================================================
    # CRIAÇÃO DO PLANO DE BATALHA
    # =========================================================================
    
    def _criar_plano_batalha(self):
        """Cria o plano de batalha completo"""
        plano = self.plano
        
        # Categoriza por propósito
        plano.openers = [s.nome for s in self.skills_por_proposito[SkillPurpose.OPENER]]
        plano.pokes = [s.nome for s in self.skills_por_proposito[SkillPurpose.POKE]]
        plano.engages = [s.nome for s in self.skills_por_proposito[SkillPurpose.ENGAGE]]
        plano.bursts = [s.nome for s in self.skills_por_proposito[SkillPurpose.BURST]]
        plano.sustains = [s.nome for s in self.skills_por_proposito[SkillPurpose.SUSTAIN]]
        plano.controls = [s.nome for s in self.skills_por_proposito[SkillPurpose.CONTROL]]
        plano.finishers = [s.nome for s in self.skills_por_proposito[SkillPurpose.FINISHER]]
        plano.escapes = [s.nome for s in self.skills_por_proposito[SkillPurpose.ESCAPE]]
        
        # Cria rotações por fase
        plano.rotacao_opening = self._criar_rotacao_opening()
        plano.rotacao_neutral = self._criar_rotacao_neutral()
        plano.rotacao_advantage = self._criar_rotacao_advantage()
        plano.rotacao_disadvantage = self._criar_rotacao_disadvantage()
        plano.rotacao_finishing = self._criar_rotacao_finishing()
        plano.rotacao_critical = self._criar_rotacao_critical()
        
        # Define estilo baseado no role
        self._definir_estilo()
    
    def _criar_rotacao_opening(self) -> List[str]:
        """Rotação para início de combate"""
        rotacao = []
        
        # Prioridade: Buffs > Summons > Traps
        for s in self.skills_por_proposito[SkillPurpose.OPENER]:
            if s.tipo == "BUFF" and s.data.get("buff_dano"):
                rotacao.insert(0, s.nome)  # Buff de dano primeiro
            elif s.tipo == "SUMMON":
                rotacao.append(s.nome)
            elif s.tipo == "TRANSFORM":
                rotacao.append(s.nome)
        
        # Adiciona pokes para manter pressão
        for s in self.skills_por_proposito[SkillPurpose.POKE][:2]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        
        return rotacao
    
    def _criar_rotacao_neutral(self) -> List[str]:
        """Rotação para fase neutra"""
        rotacao = []
        
        # Pokes e controle
        for s in self.skills_por_proposito[SkillPurpose.POKE]:
            rotacao.append(s.nome)
        for s in self.skills_por_proposito[SkillPurpose.CONTROL]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        
        # Ordena por eficiência de mana
        rotacao.sort(key=lambda n: self.skills[n].dano_por_mana if n in self.skills else 0, reverse=True)
        
        return rotacao
    
    def _criar_rotacao_advantage(self) -> List[str]:
        """Rotação quando tem vantagem"""
        rotacao = []
        
        # Burst e engage
        for s in self.skills_por_proposito[SkillPurpose.BURST]:
            rotacao.append(s.nome)
        for s in self.skills_por_proposito[SkillPurpose.ENGAGE]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        
        # Ordena por dano
        rotacao.sort(key=lambda n: self.skills[n].dano_total if n in self.skills else 0, reverse=True)
        
        return rotacao
    
    def _criar_rotacao_disadvantage(self) -> List[str]:
        """Rotação quando está em desvantagem"""
        rotacao = []
        
        # Sustain e escape
        for s in self.skills_por_proposito[SkillPurpose.SUSTAIN]:
            rotacao.append(s.nome)
        for s in self.skills_por_proposito[SkillPurpose.ESCAPE]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        for s in self.skills_por_proposito[SkillPurpose.CONTROL]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        
        return rotacao
    
    def _criar_rotacao_finishing(self) -> List[str]:
        """Rotação para finalizar inimigo"""
        rotacao = []
        
        # Finishers primeiro, depois burst
        for s in self.skills_por_proposito[SkillPurpose.FINISHER]:
            rotacao.append(s.nome)
        for s in self.skills_por_proposito[SkillPurpose.BURST]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        
        # Ordena por dano
        rotacao.sort(key=lambda n: self.skills[n].dano_total if n in self.skills else 0, reverse=True)
        
        return rotacao
    
    def _criar_rotacao_critical(self) -> List[str]:
        """Rotação quando HP crítico"""
        rotacao = []
        
        # Curas primeiro!
        for s in self.skills.values():
            if s.data.get("cura") or s.data.get("cura_por_segundo"):
                rotacao.insert(0, s.nome)
            elif s.data.get("escudo"):
                rotacao.append(s.nome)
        
        # Escapes
        for s in self.skills_por_proposito[SkillPurpose.ESCAPE]:
            if s.nome not in rotacao:
                rotacao.append(s.nome)
        
        return rotacao
    
    def _definir_estilo(self):
        """Define estilo de combate baseado no kit"""
        role = self.role_principal
        plano = self.plano
        
        if role in [StrategicRole.BURST_MAGE, StrategicRole.DASHER]:
            plano.estilo = "aggressive"
            plano.distancia_preferida = 3.0
        elif role in [StrategicRole.ARTILLERY, StrategicRole.CONTROL_MAGE]:
            plano.estilo = "kite"
            plano.distancia_preferida = 6.0
        elif role == StrategicRole.SUMMONER:
            plano.estilo = "balanced"
            plano.distancia_preferida = 5.0
        elif role == StrategicRole.TRAP_MASTER:
            plano.estilo = "defensive"
            plano.distancia_preferida = 4.0
        elif role == StrategicRole.BUFFER:
            plano.estilo = "defensive"
            plano.distancia_preferida = 3.0
        else:
            plano.estilo = "balanced"
            plano.distancia_preferida = 4.0
        
        # Foco de mana
        total_custo = sum(s.custo for s in self.skills.values())
        mana_max = self.parent.mana_max if hasattr(self.parent, 'mana_max') else 100
        
        if total_custo > mana_max * 2:
            plano.foco_mana = "conserve"
        elif total_custo < mana_max:
            plano.foco_mana = "spam"
        else:
            plano.foco_mana = "balanced"
    
    # =========================================================================
    # DESCOBERTA DE COMBOS
    # =========================================================================
    
    def _descobrir_combos(self):
        """Descobre combos e sinergias entre skills"""
        combos = []
        
        # Congelamento + Shatter
        freeze_skills = [s for s in self.skills.values() 
                        if s.data.get("efeito") == "CONGELADO"]
        shatter_skills = [s for s in self.skills.values() 
                         if s.data.get("condicao") == "ALVO_CONGELADO"]
        for freeze in freeze_skills:
            for shatter in shatter_skills:
                combos.append((freeze.nome, shatter.nome, "freeze_shatter"))
                freeze.pode_combo_apos.append(shatter.nome)
                shatter.requer_setup = True
                shatter.setup_skill = freeze.nome
        
        # Queimadura + Combustão
        burn_skills = [s for s in self.skills.values() 
                       if s.data.get("efeito") == "QUEIMANDO"]
        detonate_skills = [s for s in self.skills.values() 
                          if s.data.get("condicao") == "ALVO_QUEIMANDO"]
        for burn in burn_skills:
            for det in detonate_skills:
                combos.append((burn.nome, det.nome, "burn_detonate"))
                burn.pode_combo_apos.append(det.nome)
        
        # Buff + Burst
        buff_dano = [s for s in self.skills.values() 
                     if s.data.get("buff_dano")]
        bursts = [s for s in self.skills_por_proposito[SkillPurpose.BURST]]
        for buff in buff_dano:
            for burst in bursts[:2]:  # Top 2 bursts
                if buff.nome != burst.nome:
                    combos.append((buff.nome, burst.nome, "buff_burst"))
        
        # Summon + Buff
        summons = self.skills_por_tipo["SUMMON"]
        for summon in summons:
            for buff in buff_dano:
                combos.append((buff.nome, summon.nome, "buff_summon"))
        
        # Control + Burst
        controls = self.skills_por_proposito[SkillPurpose.CONTROL]
        for ctrl in controls:
            for burst in bursts[:2]:
                if ctrl.nome != burst.nome:
                    combos.append((ctrl.nome, burst.nome, "control_burst"))
        
        self.plano.combos = combos
    
    # =========================================================================
    # EXECUÇÃO DO PLANO
    # =========================================================================
    
    def atualizar(self, dt: float):
        """Atualiza timers"""
        if self.cd_global > 0:
            self.cd_global -= dt
        for tipo in self.cd_por_tipo:
            if self.cd_por_tipo[tipo] > 0:
                self.cd_por_tipo[tipo] -= dt
    
    def determinar_fase(self, situacao: CombatSituation) -> CombatPhase:
        """Determina a fase atual do combate"""
        # HP crítico sempre tem prioridade
        if situacao.meu_hp_percent < 0.25:
            return CombatPhase.CRITICAL
        
        # Início do combate
        if situacao.tempo_combate < 5.0:
            return CombatPhase.OPENING
        
        # Finalizando inimigo
        if situacao.inimigo_hp_percent < 0.3:
            return CombatPhase.FINISHING
        
        # Vantagem ou desvantagem
        hp_diff = situacao.meu_hp_percent - situacao.inimigo_hp_percent
        if hp_diff > 0.2 or situacao.inimigo_encurralado:
            return CombatPhase.ADVANTAGE
        elif hp_diff < -0.2 or situacao.estou_encurralado:
            return CombatPhase.DISADVANTAGE
        
        return CombatPhase.NEUTRAL
    
    def obter_rotacao_atual(self, fase: CombatPhase) -> List[str]:
        """Retorna a rotação para a fase atual"""
        plano = self.plano
        if fase == CombatPhase.OPENING:
            return plano.rotacao_opening
        elif fase == CombatPhase.NEUTRAL:
            return plano.rotacao_neutral
        elif fase == CombatPhase.ADVANTAGE:
            return plano.rotacao_advantage
        elif fase == CombatPhase.DISADVANTAGE:
            return plano.rotacao_disadvantage
        elif fase == CombatPhase.FINISHING:
            return plano.rotacao_finishing
        elif fase == CombatPhase.CRITICAL:
            return plano.rotacao_critical
        return plano.rotacao_neutral
    
    def obter_melhor_skill(self, situacao: CombatSituation) -> Optional[Tuple[SkillProfile, str]]:
        """Obtém a melhor skill para usar agora baseado no plano"""
        p = self.parent
        
        # Atualiza fase
        fase = self.determinar_fase(situacao)
        self.fase_atual = fase
        
        # Se está em combo, continua
        if self.combo_em_andamento and self.combo_index < len(self.combo_em_andamento):
            skill_nome = self.combo_em_andamento[self.combo_index]
            if self._pode_usar_skill(skill_nome, situacao):
                self.combo_index += 1
                return (self.skills[skill_nome], f"combo_{self.combo_index}")
            else:
                self.combo_em_andamento = None
                self.combo_index = 0
        
        # Verifica combos disponíveis
        combo = self._verificar_combo_disponivel(situacao)
        if combo and random.random() < 0.5:
            skill1, skill2, razao = combo
            if self._pode_usar_skill(skill1, situacao):
                self.combo_em_andamento = [skill1, skill2]
                self.combo_index = 1
                return (self.skills[skill1], f"iniciando_combo_{razao}")
        
        # Obtém rotação da fase
        rotacao = self.obter_rotacao_atual(fase)
        
        # Procura skill disponível na rotação (ignora condições ideais para ser mais agressivo)
        for skill_nome in rotacao:
            if self._pode_usar_skill(skill_nome, situacao):
                return (self.skills[skill_nome], f"rotacao_{fase.value}")
        
        # Fallback: qualquer skill disponível
        for skill in self.skills.values():
            if self._pode_usar_skill(skill.nome, situacao):
                return (skill, "fallback")
        
        return None
    
    def _pode_usar_skill(self, nome: str, situacao: CombatSituation) -> bool:
        """Verifica se uma skill pode ser usada"""
        if nome not in self.skills:
            return False
        
        skill = self.skills[nome]
        p = self.parent
        
        # Mana
        if p.mana < skill.custo:
            return False
        
        # Cooldown do jogo
        if nome in p.cd_skills and p.cd_skills[nome] > 0:
            return False
        
        # Cooldown interno por tipo
        if skill.tipo in self.cd_por_tipo:
            if self.cd_por_tipo[skill.tipo] > 0:
                return False
        
        return True
    
    def _condicoes_ideais(self, nome: str, sit: CombatSituation) -> bool:
        """Verifica se as condições são ideais para usar a skill"""
        skill = self.skills[nome]
        
        # Distância
        if skill.alcance_efetivo > 0:
            if sit.distancia < skill.distancia_min * 0.5:  # Mais flexível
                return False
            if sit.distancia > skill.distancia_max * 1.2:  # Mais flexível
                return False
        
        # HP próprio
        if sit.meu_hp_percent < skill.hp_proprio_min:
            return False
        if sit.meu_hp_percent > skill.hp_proprio_max:
            # Para skills de cura, só retorna False se HP > max
            if skill.proposito_principal == SkillPurpose.SUSTAIN:
                return False
        
        # HP inimigo (para finishers)
        if skill.proposito_principal == SkillPurpose.FINISHER:
            if sit.inimigo_hp_percent > skill.hp_inimigo_max:
                return False
        
        # Skills que não dependem de distância (BUFF, SUMMON, TRANSFORM)
        if skill.tipo in ["BUFF", "SUMMON", "TRANSFORM", "TRAP"]:
            return True  # Sempre pode usar se tiver mana
        
        return True
    
    def _verificar_combo_disponivel(self, situacao: CombatSituation) -> Optional[Tuple[str, str, str]]:
        """Verifica se há um combo disponível"""
        for skill1, skill2, razao in self.plano.combos:
            if skill1 in self.skills and skill2 in self.skills:
                if self._pode_usar_skill(skill1, situacao):
                    # Verifica se terá mana para ambas
                    custo_total = self.skills[skill1].custo + self.skills[skill2].custo
                    if self.parent.mana >= custo_total * 0.9:  # Margem de 10%
                        return (skill1, skill2, razao)
        return None
    
    def get_combo_recomendado(self) -> Optional[Tuple[str, str, str]]:
        """Retorna um combo recomendado (compatibilidade)"""
        p = self.parent
        for skill1, skill2, razao in self.plano.combos:
            if skill1 in self.skills and skill2 in self.skills:
                s1, s2 = self.skills[skill1], self.skills[skill2]
                if p.mana >= s1.custo + s2.custo:
                    if skill1 not in p.cd_skills or p.cd_skills[skill1] <= 0:
                        if skill2 not in p.cd_skills or p.cd_skills[skill2] <= 0:
                            return (skill1, skill2, razao)
        return None
    
    def registrar_uso(self, nome: str):
        """Registra que uma skill foi usada"""
        self.ultima_skill = nome
        self.skills_usadas.append(nome)
        if len(self.skills_usadas) > 10:
            self.skills_usadas.pop(0)
        
        # Aplica cooldown interno
        if nome in self.skills:
            skill = self.skills[nome]
            if skill.tipo in self.cd_por_tipo:
                self.cd_por_tipo[skill.tipo] = 3.0
            self.cd_global = 0.3  # Pequeno delay entre skills
    
    def registrar_uso_skill(self, nome: str):
        """Alias para registrar_uso (compatibilidade)"""
        self.registrar_uso(nome)
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def get_distancia_preferida(self) -> float:
        """Retorna distância preferida de combate"""
        return self.plano.distancia_preferida
    
    def get_estilo(self) -> str:
        """Retorna estilo de combate"""
        return self.plano.estilo
    
    def ajustar_para_arma(self, alcance_arma: float, velocidade_arma: float):
        """Ajusta estratégia baseado na arma"""
        # Se arma tem alcance maior que skills, usar mais a arma
        max_skill_range = max((s.alcance_efetivo for s in self.skills.values()), default=0)
        
        if alcance_arma > max_skill_range:
            self.plano.distancia_preferida = alcance_arma
        
        # Arma lenta = mais skills
        if velocidade_arma < 0.7:
            self.plano.foco_mana = "spam"
        
        # Atualiza preferências
        self.preferencias["distancia_preferida"] = self.plano.distancia_preferida
    
    def _log_plano(self):
        """Loga o plano de batalha criado"""
        p = self.parent
        print(f"\n{'='*60}")
        print(f"[BATTLE PLAN] {p.dados.nome}")
        print(f"{'='*60}")
        print(f"  Role: {self.role_principal.value.upper()}")
        print(f"  Estilo: {self.plano.estilo} | Distância: {self.plano.distancia_preferida:.1f}m | Mana: {self.plano.foco_mana}")
        print(f"\n  === SKILLS ANALISADAS ({len(self.skills)}) ===")
        for skill in self.skills.values():
            props = ", ".join([p.value for p in skill.propositos])
            print(f"    [{skill.tipo:8}] {skill.nome:25} | Custo:{skill.custo:5.0f} | Dano:{skill.dano_total:5.0f} | {props}")
        
        if self.plano.combos:
            print(f"\n  === COMBOS DESCOBERTOS ({len(self.plano.combos)}) ===")
            for s1, s2, razao in self.plano.combos[:5]:
                print(f"    {s1} -> {s2} ({razao})")
        
        print(f"\n  === ROTAÇÕES ===")
        print(f"    Opening:      {self.plano.rotacao_opening}")
        print(f"    Neutral:      {self.plano.rotacao_neutral}")
        print(f"    Advantage:    {self.plano.rotacao_advantage}")
        print(f"    Disadvantage: {self.plano.rotacao_disadvantage}")
        print(f"    Finishing:    {self.plano.rotacao_finishing}")
        print(f"    Critical:     {self.plano.rotacao_critical}")
        print(f"{'='*60}\n")
