"""
NEURAL FIGHTS - Sistema de Game Feel
====================================

Sistema completo de 'Game Feel' para adicionar peso, impacto e tensão
cinematográfica ao combate, especialmente para classes de Força e Magia.

Arquitetura:
    - HitStopManager: Congela o jogo em momentos de impacto (classes de Força)
    - SuperArmorSystem: Permite "trade" de golpes sem stagger (Berserkers/Tanks)
    - ChannelingSystem: Sistema de carga para magias poderosas (Magos)
    - CameraFeel: Shake e efeitos de câmera baseados em intensidade

Filosofia de Design:
    - Classes de FORÇA: Golpes lentos mas devastadores - o mundo PARA quando acertam
    - Classes ÁGEIS: Já funcionam bem - mantemos velocidade e responsividade
    - Classes MÁGICAS: Risco/Recompensa - tempo de carga cria tensão e payoff épico
"""

import math
import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any


# =============================================================================
# CONSTANTES DE GAME FEEL
# =============================================================================

# Hit Stop - Quanto tempo o jogo "congela" em frames (convertido para segundos)
HITSTOP_FRAMES = {
    "LEVE": 2,      # ~0.033s @ 60fps - Golpes leves, projéteis pequenos
    "MEDIO": 4,     # ~0.066s @ 60fps - Golpes normais
    "PESADO": 8,    # ~0.133s @ 60fps - Golpes de armas pesadas
    "DEVASTADOR": 12,  # ~0.200s @ 60fps - Ataques finalizadores, críticos de força
    "EPICO": 18,    # ~0.300s @ 60fps - Golpes de execução, magias carregadas
}

# Multiplicadores de Hit Stop por classe (baseado no "peso" do personagem)
CLASS_HITSTOP_MULT = {
    "Guerreiro (Força Bruta)": 1.5,
    "Berserker (Fúria)": 1.8,  # Berserkers sentem impacto MÁXIMO
    "Gladiador (Combate)": 1.3,
    "Cavaleiro (Defesa)": 1.6,
    # Ágeis - hit stop mínimo para manter fluidez
    "Assassino (Crítico)": 0.5,  # Críticos ainda têm pequeno hit stop
    "Ladino (Evasão)": 0.3,
    "Ninja (Velocidade)": 0.2,
    "Duelista (Precisão)": 0.6,
    # Magos - hit stop em magias carregadas é ÉPICO
    "Mago (Arcano)": 1.0,  # Depende da magia, não do ataque básico
    "Piromante (Fogo)": 1.2,  # Explosões = impacto
    "Criomante (Gelo)": 0.8,
    "Necromante (Trevas)": 1.1,
    # Híbridos
    "Paladino (Sagrado)": 1.4,
    "Druida (Natureza)": 0.9,
    "Feiticeiro (Caos)": 1.3,
    "Monge (Chi)": 0.7,  # Fluxo contínuo de golpes
}

# Super Armor - Configuração por classe
SUPER_ARMOR_CONFIG = {
    "Berserker (Fúria)": {
        "ativacao": "ataque",  # Ativa durante frames de ataque
        "reducao_dano": 0.5,   # Recebe 50% do dano
        "frames_armor": (0.1, 0.4),  # Do frame 10% ao 40% da animação
        "knockback_resist": 1.0,  # 100% resistência a knockback
        "visual": "red_glow",  # Feedback visual
    },
    "Guerreiro (Força Bruta)": {
        "ativacao": "ataque_pesado",
        "reducao_dano": 0.7,
        "frames_armor": (0.15, 0.35),
        "knockback_resist": 0.8,
        "visual": "golden_flash",
    },
    "Cavaleiro (Defesa)": {
        "ativacao": "sempre_ativo",  # Tank sempre tem alguma armor
        "reducao_dano": 0.25,  # Sempre 25% de redução
        "frames_armor": (0.0, 1.0),
        "knockback_resist": 0.5,
        "visual": "shield_shimmer",
    },
    "Gladiador (Combate)": {
        "ativacao": "contra_ataque",
        "reducao_dano": 0.6,
        "frames_armor": (0.05, 0.25),
        "knockback_resist": 0.7,
        "visual": "battle_aura",
    },
    "Paladino (Sagrado)": {
        "ativacao": "skill",
        "reducao_dano": 0.4,
        "frames_armor": (0.0, 0.5),
        "knockback_resist": 0.9,
        "visual": "holy_shield",
    },
}

# Channeling - Configuração de magias carregadas
CHANNELING_CONFIG = {
    "Mago (Arcano)": {
        "tempo_base": 1.5,      # Segundos para carregar magia
        "bonus_dano_max": 2.5,  # Multiplicador se carregar completo
        "bonus_area_max": 1.8,  # Área aumenta com carga
        "interruptivel": True,
        "dano_minimo": 0.3,     # Se cancelar cedo, ainda causa 30%
        "visual": "arcane_rings",
    },
    "Piromante (Fogo)": {
        "tempo_base": 2.0,      # Mais demorado, mais devastador
        "bonus_dano_max": 3.0,
        "bonus_area_max": 2.2,
        "interruptivel": True,
        "dano_minimo": 0.4,
        "visual": "fire_spiral",
    },
    "Criomante (Gelo)": {
        "tempo_base": 1.2,
        "bonus_dano_max": 2.0,
        "bonus_area_max": 1.5,
        "interruptivel": True,
        "dano_minimo": 0.5,
        "visual": "ice_crystals",
    },
    "Necromante (Trevas)": {
        "tempo_base": 2.5,      # O mais lento - payoff máximo
        "bonus_dano_max": 3.5,
        "bonus_area_max": 2.0,
        "interruptivel": True,
        "dano_minimo": 0.2,     # Alto risco se interrompido
        "visual": "dark_vortex",
    },
    "Feiticeiro (Caos)": {
        "tempo_base": 1.0,      # Caótico e imprevisível
        "bonus_dano_max": 4.0,  # Potencial máximo
        "bonus_area_max": 2.5,
        "interruptivel": True,
        "dano_minimo": 0.1,     # Muito arriscado
        "visual": "chaos_storm",
    },
}


# =============================================================================
# ENUMS E DATACLASSES
# =============================================================================

class ChannelState(Enum):
    """Estados da máquina de estados de Channeling"""
    IDLE = auto()        # Pronto para começar
    CHARGING = auto()    # Carregando magia
    RELEASING = auto()   # Liberando (ponto sem retorno)
    INTERRUPTED = auto() # Foi interrompido
    COOLDOWN = auto()    # Em cooldown pós-uso


class SuperArmorState(Enum):
    """Estados do Super Armor"""
    INACTIVE = auto()    # Armor desativada
    ACTIVE = auto()      # Armor ativa - não sofre stagger
    BROKEN = auto()      # Armor quebrada por dano excessivo


@dataclass
class HitStopEvent:
    """Evento de Hit Stop para ser processado pelo sistema"""
    duracao: float          # Duração em segundos
    intensidade: float      # 0.0 a 1.0 - afeta camera shake também
    atacante: Any           # Quem causou
    alvo: Any               # Quem recebeu
    tipo_golpe: str         # "leve", "pesado", "critico", "magia"
    posicao: tuple          # (x, y) onde ocorreu o impacto
    
    # Efeitos adicionais
    camera_shake: float = 0.0
    camera_zoom_punch: float = 0.0
    cor_flash: tuple = (255, 255, 255)


@dataclass
class ChannelData:
    """Dados de uma magia sendo canalizada"""
    skill_nome: str
    tempo_inicio: float
    tempo_necessario: float
    carga_atual: float = 0.0
    
    # Modificadores baseados na carga
    mult_dano: float = 1.0
    mult_area: float = 1.0
    
    # Estado
    estado: ChannelState = ChannelState.IDLE
    interrompido: bool = False
    
    # Visual
    particulas: List = field(default_factory=list)


@dataclass  
class SuperArmorData:
    """Dados do estado de Super Armor"""
    ativo: bool = False
    reducao_dano: float = 1.0  # 1.0 = sem redução
    knockback_resist: float = 0.0
    dano_absorvido: float = 0.0
    
    # Limite de absorção (se exceder, armor quebra)
    limite_dano: float = 50.0
    quebrada: bool = False
    
    # Timer para quando está ativa por frames de animação
    frame_inicio: float = 0.0
    frame_fim: float = 1.0
    
    # Visual feedback
    tipo_visual: str = "none"


# =============================================================================
# HIT STOP MANAGER
# =============================================================================

class HitStopManager:
    """
    Gerenciador central de Hit Stop.
    
    O Hit Stop é a técnica de "congelar" o jogo por alguns frames quando um
    golpe conecta, para dar sensação de peso e impacto. É crucial para
    'game feel' em jogos de luta.
    
    Comportamento por classe:
    - FORÇA (Berserker, Guerreiro): Hit stops LONGOS - cada golpe é um evento
    - ÁGEIS (Ninja, Assassino): Hit stops CURTOS ou inexistentes - fluidez
    - MAGOS: Hit stops VARIÁVEIS - magias carregadas têm hit stop épico
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Singleton para acesso global"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset para nova partida"""
        cls._instance = None
    
    def __init__(self):
        self.timer_ativo = 0.0
        self.evento_atual: Optional[HitStopEvent] = None
        self.fila_eventos: List[HitStopEvent] = []
        
        # Callbacks para feedback visual
        self.on_hitstop_start: Optional[Callable] = None
        self.on_hitstop_end: Optional[Callable] = None
        
        # Estatísticas para debug
        self.total_hitstops = 0
        self.tempo_total_parado = 0.0
    
    def calcular_duracao_hitstop(self, dano: float, classe_atacante: str, 
                                  tipo_golpe: str = "MEDIO", is_critico: bool = False) -> float:
        """
        Calcula duração do hit stop baseado em múltiplos fatores.
        
        Args:
            dano: Dano base do golpe
            classe_atacante: Nome da classe do atacante
            tipo_golpe: "LEVE", "MEDIO", "PESADO", "DEVASTADOR", "EPICO"
            is_critico: Se foi golpe crítico
        
        Returns:
            Duração em segundos
        
        Design Notes:
            - Dano escala logaritmicamente para evitar hit stops infinitos
            - Classes de força têm multiplicador alto
            - Críticos sempre adicionam frames extras
        """
        # Frames base
        frames_base = HITSTOP_FRAMES.get(tipo_golpe, HITSTOP_FRAMES["MEDIO"])
        
        # Multiplicador de classe
        mult_classe = CLASS_HITSTOP_MULT.get(classe_atacante, 1.0)
        
        # Escala logarítmica com dano (evita valores absurdos)
        # Dano de 10 = 1.0x, Dano de 50 = ~1.7x, Dano de 100 = ~2.0x
        mult_dano = 1.0 + math.log10(max(1, dano / 10))
        
        # Bônus de crítico
        mult_critico = 1.5 if is_critico else 1.0
        
        # Calcula frames finais
        frames_finais = frames_base * mult_classe * mult_dano * mult_critico
        
        # Converte para segundos (assumindo 60 FPS como referência)
        duracao = frames_finais / 60.0
        
        # Clamp para valores razoáveis (0.016s a 0.5s)
        return max(0.016, min(0.5, duracao))
    
    def registrar_hit(self, atacante, alvo, dano: float, posicao: tuple,
                      tipo_golpe: str = "MEDIO", is_critico: bool = False,
                      cor_flash: tuple = (255, 255, 255)):
        """
        Registra um hit para processamento de hit stop.
        
        Chamado pelo sistema de combate quando um golpe conecta.
        """
        classe_atacante = getattr(atacante, 'classe_nome', "Guerreiro (Força Bruta)")
        
        duracao = self.calcular_duracao_hitstop(dano, classe_atacante, tipo_golpe, is_critico)
        
        # Intensidade para efeitos visuais (0.0 a 1.0)
        intensidade = min(1.0, duracao / 0.3)  # Normaliza para 0.3s como máximo
        
        # Camera shake proporcional - força > velocidade
        # Classes de força causam shake MUITO maior
        shake_mult = CLASS_HITSTOP_MULT.get(classe_atacante, 1.0)
        camera_shake = 5.0 + (dano * 0.3 * shake_mult)
        
        # Zoom punch para impactos pesados
        camera_zoom = 0.0
        if tipo_golpe in ["PESADO", "DEVASTADOR", "EPICO"] or is_critico:
            camera_zoom = 0.1 + (intensidade * 0.15)
        
        evento = HitStopEvent(
            duracao=duracao,
            intensidade=intensidade,
            atacante=atacante,
            alvo=alvo,
            tipo_golpe=tipo_golpe,
            posicao=posicao,
            camera_shake=camera_shake,
            camera_zoom_punch=camera_zoom,
            cor_flash=cor_flash
        )
        
        # Se já tem hit stop ativo, empilha (usa o maior)
        if self.timer_ativo > 0 and self.evento_atual:
            if duracao > self.evento_atual.duracao:
                self.fila_eventos.append(evento)
        else:
            self._iniciar_hitstop(evento)
    
    def _iniciar_hitstop(self, evento: HitStopEvent):
        """Inicia um hit stop"""
        self.evento_atual = evento
        self.timer_ativo = evento.duracao
        self.total_hitstops += 1
        
        if self.on_hitstop_start:
            self.on_hitstop_start(evento)
    
    def update(self, dt: float) -> float:
        """
        Atualiza o sistema de hit stop.
        
        Args:
            dt: Delta time do frame
            
        Returns:
            dt modificado (0 se em hit stop, dt normal se não)
            
        Note:
            O simulador deve usar este valor retornado como seu dt efetivo.
            Durante hit stop, o jogo efetivamente "congela".
        """
        if self.timer_ativo > 0:
            self.timer_ativo -= dt
            self.tempo_total_parado += dt
            
            if self.timer_ativo <= 0:
                # Hit stop terminou
                evento_terminado = self.evento_atual
                self.evento_atual = None
                
                if self.on_hitstop_end:
                    self.on_hitstop_end(evento_terminado)
                
                # Processa próximo da fila se houver
                if self.fila_eventos:
                    proximo = self.fila_eventos.pop(0)
                    self._iniciar_hitstop(proximo)
                    return 0.0  # Continua em hit stop
            
            return 0.0  # Durante hit stop, dt = 0
        
        return dt  # Sem hit stop, dt normal
    
    @property
    def em_hitstop(self) -> bool:
        """Verifica se está em hit stop"""
        return self.timer_ativo > 0


# =============================================================================
# SUPER ARMOR SYSTEM
# =============================================================================

class SuperArmorSystem:
    """
    Sistema de Super Armor para classes tank/berserker.
    
    Super Armor permite que um personagem receba dano reduzido e NÃO seja
    interrompido (stagger) durante certos frames de animação de ataque.
    
    Isso cria o "trade" característico - berserkers trocam dano brutalmente.
    
    Comportamento:
    - Ativa automaticamente durante frames específicos de ataque
    - Reduz dano recebido (mas não anula)
    - Previne knockback e stagger
    - Tem limite de dano - se exceder, armor quebra
    - Feedback visual claro para o jogador entender o que está acontecendo
    """
    
    def __init__(self, lutador):
        self.lutador = lutador
        self.classe_nome = getattr(lutador, 'classe_nome', "")
        
        # Carrega configuração da classe
        self.config = SUPER_ARMOR_CONFIG.get(self.classe_nome, None)
        
        # Estado atual
        self.data = SuperArmorData()
        
        # Se a classe tem super armor configurada
        if self.config:
            self.data.reducao_dano = 1.0 - self.config["reducao_dano"]
            self.data.knockback_resist = self.config["knockback_resist"]
            self.data.tipo_visual = self.config["visual"]
            self.data.frame_inicio = self.config["frames_armor"][0]
            self.data.frame_fim = self.config["frames_armor"][1]
            
            # Limite de dano escala com vida do personagem
            self.data.limite_dano = lutador.vida_max * 0.3
        
        # Callbacks visuais
        self.on_armor_ativada: Optional[Callable] = None
        self.on_armor_hit: Optional[Callable] = None
        self.on_armor_quebrada: Optional[Callable] = None
    
    def tem_super_armor(self) -> bool:
        """Verifica se a classe do lutador tem super armor"""
        return self.config is not None
    
    def verificar_ativacao(self, progresso_animacao: float = 0.0, 
                           acao_atual: str = "") -> bool:
        """
        Verifica se a super armor deve estar ativa.
        
        Args:
            progresso_animacao: 0.0 a 1.0 - progresso da animação de ataque
            acao_atual: Ação atual da IA ("MATAR", "ESMAGAR", etc)
        
        Returns:
            True se armor está ativa
        """
        if not self.config:
            return False
        
        if self.data.quebrada:
            return False
        
        tipo_ativacao = self.config["ativacao"]
        
        if tipo_ativacao == "sempre_ativo":
            # Cavaleiros sempre têm armor passiva
            self.data.ativo = True
            return True
        
        elif tipo_ativacao == "ataque":
            # Ativa durante qualquer ataque
            if acao_atual in ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "COMBATE"]:
                esta_no_frame = (self.data.frame_inicio <= progresso_animacao <= self.data.frame_fim)
                
                if esta_no_frame and not self.data.ativo:
                    self._ativar_armor()
                elif not esta_no_frame and self.data.ativo:
                    self._desativar_armor()
                    
                return self.data.ativo
        
        elif tipo_ativacao == "ataque_pesado":
            # Apenas ataques pesados
            if acao_atual in ["ESMAGAR", "MATAR"]:
                esta_no_frame = (self.data.frame_inicio <= progresso_animacao <= self.data.frame_fim)
                
                if esta_no_frame and not self.data.ativo:
                    self._ativar_armor()
                elif not esta_no_frame and self.data.ativo:
                    self._desativar_armor()
                    
                return self.data.ativo
        
        elif tipo_ativacao == "contra_ataque":
            # Gladiadores ativam em contra-ataques
            if acao_atual == "CONTRA_ATAQUE":
                esta_no_frame = (self.data.frame_inicio <= progresso_animacao <= self.data.frame_fim)
                
                if esta_no_frame and not self.data.ativo:
                    self._ativar_armor()
                elif not esta_no_frame and self.data.ativo:
                    self._desativar_armor()
                    
                return self.data.ativo
        
        elif tipo_ativacao == "skill":
            # Paladinos ativam durante skills
            if hasattr(self.lutador, 'usando_skill') and self.lutador.usando_skill:
                if not self.data.ativo:
                    self._ativar_armor()
                return True
        
        # Desativa se nenhuma condição foi atendida
        if self.data.ativo:
            self._desativar_armor()
        
        return False
    
    def _ativar_armor(self):
        """Ativa a super armor"""
        self.data.ativo = True
        self.data.dano_absorvido = 0.0
        
        if self.on_armor_ativada:
            self.on_armor_ativada(self.lutador, self.data.tipo_visual)
    
    def _desativar_armor(self):
        """Desativa a super armor"""
        self.data.ativo = False
    
    def processar_dano(self, dano_base: float, knockback_x: float = 0, 
                       knockback_y: float = 0) -> tuple:
        """
        Processa dano recebido através da super armor.
        
        Args:
            dano_base: Dano original
            knockback_x: Componente X do knockback
            knockback_y: Componente Y do knockback
        
        Returns:
            (dano_final, kb_x_final, kb_y_final, foi_stagger)
            
        Design Notes:
            - Dano é REDUZIDO mas não anulado
            - Knockback pode ser completamente anulado
            - Se acumular muito dano, armor QUEBRA
        """
        if not self.data.ativo or self.data.quebrada:
            return (dano_base, knockback_x, knockback_y, True)  # Stagger normal
        
        # Reduz dano
        dano_final = dano_base * self.data.reducao_dano
        
        # Reduz/anula knockback
        kb_mult = 1.0 - self.data.knockback_resist
        kb_x_final = knockback_x * kb_mult
        kb_y_final = knockback_y * kb_mult
        
        # Acumula dano absorvido
        dano_absorvido = dano_base - dano_final
        self.data.dano_absorvido += dano_absorvido
        
        # Feedback visual de hit na armor
        if self.on_armor_hit:
            self.on_armor_hit(self.lutador, dano_absorvido)
        
        # Verifica se armor quebra
        if self.data.dano_absorvido >= self.data.limite_dano:
            self._quebrar_armor()
            return (dano_base * 0.5, knockback_x, knockback_y, True)  # Stagger quando quebra
        
        return (dano_final, kb_x_final, kb_y_final, False)  # Sem stagger
    
    def _quebrar_armor(self):
        """Quebra a super armor"""
        self.data.quebrada = True
        self.data.ativo = False
        
        if self.on_armor_quebrada:
            self.on_armor_quebrada(self.lutador)
    
    def reset_armor(self):
        """Reseta a armor (entre rounds ou após cooldown)"""
        self.data.quebrada = False
        self.data.dano_absorvido = 0.0
        self.data.ativo = False


# =============================================================================
# CHANNELING SYSTEM (MÁQUINA DE ESTADOS PARA MAGOS)
# =============================================================================

class ChannelingSystem:
    """
    Sistema de Channeling para magias carregadas.
    
    Implementa uma máquina de estados para magias que exigem tempo de
    preparação, criando tensão de risco/recompensa.
    
    Estados:
        IDLE -> CHARGING -> RELEASING -> COOLDOWN
                    |
                    v
                INTERRUPTED
    
    Comportamento:
    - Mago começa a canalizar (CHARGING)
    - Durante canalização, fica vulnerável
    - Se tomar dano, pode ser interrompido (INTERRUPTED)
    - Se completar, libera magia com bônus massivo (RELEASING)
    - Após liberar, entra em cooldown (COOLDOWN)
    
    Design Notes:
    - Carga parcial ainda libera magia, mas com eficácia reduzida
    - Certas skills podem ter "ponto sem retorno" - não interrompíveis no final
    - Feedback visual intensifica conforme carga aumenta
    """
    
    def __init__(self, lutador):
        self.lutador = lutador
        self.classe_nome = getattr(lutador, 'classe_nome', "")
        
        # Carrega configuração da classe
        self.config = CHANNELING_CONFIG.get(self.classe_nome, None)
        
        # Dados da canalização atual
        self.channel_data: Optional[ChannelData] = None
        
        # Timer interno
        self.timer = 0.0
        
        # Callback para quando magia é liberada
        self.on_channel_start: Optional[Callable] = None
        self.on_channel_progress: Optional[Callable] = None  # Para feedback visual
        self.on_channel_complete: Optional[Callable] = None
        self.on_channel_interrupted: Optional[Callable] = None
        self.on_channel_release: Optional[Callable] = None
    
    def pode_canalizar(self) -> bool:
        """Verifica se pode iniciar canalização"""
        if not self.config:
            return False
        if self.channel_data and self.channel_data.estado != ChannelState.IDLE:
            return False
        return True
    
    def iniciar_canalizacao(self, skill_nome: str, skill_data: dict) -> bool:
        """
        Inicia a canalização de uma magia.
        
        Args:
            skill_nome: Nome da skill
            skill_data: Dados da skill
        
        Returns:
            True se iniciou com sucesso
        """
        if not self.pode_canalizar():
            return False
        
        # Calcula tempo de canalização
        # Skills podem ter override de tempo de carga
        tempo_base = self.config["tempo_base"]
        tempo_skill = skill_data.get("tempo_carga", tempo_base)
        
        # Redução de tempo para magos experientes (baseado em mana max)
        reducao_mana = min(0.3, self.lutador.mana_max / 500.0)  # Até 30% redução
        tempo_final = tempo_skill * (1.0 - reducao_mana)
        
        self.channel_data = ChannelData(
            skill_nome=skill_nome,
            tempo_inicio=0.0,
            tempo_necessario=tempo_final,
            estado=ChannelState.CHARGING
        )
        
        if self.on_channel_start:
            self.on_channel_start(self.lutador, skill_nome, tempo_final)
        
        return True
    
    def update(self, dt: float) -> Optional[dict]:
        """
        Atualiza o sistema de canalização.
        
        Args:
            dt: Delta time
            
        Returns:
            Dict com dados da magia liberada, ou None se ainda canalizando
            
        Return format quando completa:
            {
                "skill_nome": str,
                "mult_dano": float,
                "mult_area": float,
                "foi_interrumpido": bool,
                "carga_final": float  # 0.0 a 1.0
            }
        """
        if not self.channel_data:
            return None
        
        estado = self.channel_data.estado
        
        if estado == ChannelState.CHARGING:
            # Incrementa carga
            self.timer += dt
            self.channel_data.carga_atual = min(1.0, self.timer / self.channel_data.tempo_necessario)
            
            # Calcula multiplicadores baseado na carga
            # Usa curva exponencial para recompensar carga completa
            carga = self.channel_data.carga_atual
            curva_carga = carga ** 2  # Curva exponencial - últimos 20% valem muito
            
            self.channel_data.mult_dano = 1.0 + (self.config["bonus_dano_max"] - 1.0) * curva_carga
            self.channel_data.mult_area = 1.0 + (self.config["bonus_area_max"] - 1.0) * curva_carga
            
            # Feedback visual de progresso
            if self.on_channel_progress:
                self.on_channel_progress(self.lutador, carga, self.config["visual"])
            
            # Verifica se completou
            if self.channel_data.carga_atual >= 1.0:
                return self._completar_canalizacao()
        
        elif estado == ChannelState.INTERRUPTED:
            # Foi interrompido - libera magia parcial ou falha
            return self._liberar_interrupcao()
        
        elif estado == ChannelState.RELEASING:
            # Liberando magia (ponto sem retorno)
            self.timer -= dt
            if self.timer <= 0:
                return self._finalizar_liberacao()
        
        return None
    
    def _completar_canalizacao(self) -> dict:
        """Completa a canalização com sucesso"""
        self.channel_data.estado = ChannelState.RELEASING
        self.timer = 0.3  # 0.3s de "liberação" dramática
        
        if self.on_channel_complete:
            self.on_channel_complete(self.lutador, self.channel_data.skill_nome)
        
        return None  # Ainda não libera, espera a animação de release
    
    def _finalizar_liberacao(self) -> dict:
        """Finaliza a liberação da magia"""
        resultado = {
            "skill_nome": self.channel_data.skill_nome,
            "mult_dano": self.channel_data.mult_dano,
            "mult_area": self.channel_data.mult_area,
            "foi_interrumpido": False,
            "carga_final": 1.0
        }
        
        if self.on_channel_release:
            self.on_channel_release(self.lutador, resultado)
        
        # Reset para próxima canalização
        self.channel_data = ChannelData(
            skill_nome="",
            tempo_inicio=0.0,
            tempo_necessario=0.0,
            estado=ChannelState.COOLDOWN
        )
        self.timer = 2.0  # Cooldown antes de poder canalizar novamente
        
        return resultado
    
    def interromper(self, dano_recebido: float) -> bool:
        """
        Tenta interromper a canalização.
        
        Args:
            dano_recebido: Dano que causou a tentativa de interrupção
            
        Returns:
            True se foi interrompido
            
        Design Notes:
            - Dano alto tem mais chance de interromper
            - Canalização avançada é mais difícil de interromper
            - Algumas classes têm resistência a interrupção
        """
        if not self.channel_data or self.channel_data.estado != ChannelState.CHARGING:
            return False
        
        if not self.config["interruptivel"]:
            return False
        
        # Chance de interrupção baseada em dano
        # Dano alto (30+) quase sempre interrompe
        # Dano baixo (<10) tem chance baixa
        chance_base = min(0.9, dano_recebido / 40.0)
        
        # Resistência baseada na carga (mais difícil interromper no final)
        carga = self.channel_data.carga_atual
        if carga > 0.8:  # Últimos 20% são "ponto sem retorno"
            chance_base *= 0.3
        elif carga > 0.5:
            chance_base *= 0.6
        
        # Resistência de classe (magos têm concentração)
        if "Mago" in self.classe_nome:
            chance_base *= 0.7
        
        if random.random() < chance_base:
            self.channel_data.estado = ChannelState.INTERRUPTED
            self.channel_data.interrompido = True
            
            if self.on_channel_interrupted:
                self.on_channel_interrupted(self.lutador, self.channel_data.skill_nome, carga)
            
            return True
        
        return False
    
    def _liberar_interrupcao(self) -> dict:
        """Libera magia parcial após interrupção"""
        carga = self.channel_data.carga_atual
        dano_minimo = self.config["dano_minimo"]
        
        # Se carga muito baixa, magia falha completamente
        if carga < 0.2:
            resultado = {
                "skill_nome": self.channel_data.skill_nome,
                "mult_dano": 0.0,  # Falha total
                "mult_area": 0.0,
                "foi_interrumpido": True,
                "carga_final": carga
            }
        else:
            # Libera magia parcial
            mult_efetivo = dano_minimo + (carga * (1.0 - dano_minimo))
            resultado = {
                "skill_nome": self.channel_data.skill_nome,
                "mult_dano": mult_efetivo,
                "mult_area": mult_efetivo * 0.8,
                "foi_interrumpido": True,
                "carga_final": carga
            }
        
        # Reset
        self.channel_data = None
        self.timer = 0.0
        
        return resultado
    
    def cancelar(self):
        """Cancela canalização voluntariamente"""
        if self.channel_data:
            self.channel_data.estado = ChannelState.INTERRUPTED
            self.channel_data.interrompido = True
    
    @property
    def esta_canalizando(self) -> bool:
        """Verifica se está ativamente canalizando"""
        return (self.channel_data is not None and 
                self.channel_data.estado == ChannelState.CHARGING)
    
    @property
    def carga_atual(self) -> float:
        """Retorna carga atual (0.0 a 1.0)"""
        if self.channel_data:
            return self.channel_data.carga_atual
        return 0.0


# =============================================================================
# CAMERA FEEL - SHAKE BASEADO EM INTENSIDADE/FORÇA
# =============================================================================

class CameraFeel:
    """
    Sistema de feedback de câmera baseado em INTENSIDADE (força), não velocidade.
    
    Golpes pesados causam camera shake massivo.
    Golpes rápidos causam shake mínimo.
    Magias carregadas causam shake + zoom épico.
    
    Tipos de efeitos:
    - Shake: Tremor da câmera
    - Zoom Punch: Zoom rápido para dentro + retorno
    - Focus: Foco momentâneo no ponto de impacto
    - Chromatic: Aberração cromática (para dano crítico)
    """
    
    def __init__(self, camera_ref):
        """
        Args:
            camera_ref: Referência para a câmera do jogo
        """
        self.camera = camera_ref
        
        # Shake acumulado (permite empilhar múltiplos hits)
        self.shake_acumulado = 0.0
        self.shake_decay = 15.0  # Velocidade que shake diminui
        
        # Direção do shake (baseado no golpe)
        self.shake_dir_x = 0.0
        self.shake_dir_y = 0.0
        
        # Zoom punch
        self.zoom_punch_ativo = False
        self.zoom_punch_timer = 0.0
        self.zoom_punch_intensidade = 0.0
        
        # Focus (câmera move para ponto de impacto)
        self.focus_ativo = False
        self.focus_pos = (0, 0)
        self.focus_timer = 0.0
    
    def aplicar_impacto(self, dano: float, classe_atacante: str, posicao: tuple,
                        tipo_golpe: str = "MEDIO", direcao: tuple = (0, 0)):
        """
        Aplica efeitos de câmera para um impacto.
        
        Args:
            dano: Dano do golpe
            classe_atacante: Classe do atacante (afeta intensidade)
            posicao: (x, y) do impacto
            tipo_golpe: "LEVE", "MEDIO", "PESADO", "DEVASTADOR", "EPICO"
            direcao: Direção do golpe normalizada
        """
        # Multiplicador de classe
        mult_classe = CLASS_HITSTOP_MULT.get(classe_atacante, 1.0)
        
        # Base de shake
        shake_base = {
            "LEVE": 3.0,
            "MEDIO": 6.0,
            "PESADO": 12.0,
            "DEVASTADOR": 20.0,
            "EPICO": 30.0
        }.get(tipo_golpe, 6.0)
        
        # Escala com dano
        shake_dano = math.sqrt(dano) * 0.5
        
        # Shake final
        shake_final = (shake_base + shake_dano) * mult_classe
        
        # Acumula shake (com cap)
        self.shake_acumulado = min(40.0, self.shake_acumulado + shake_final)
        
        # Direção do shake (golpe empurra câmera na direção oposta brevemente)
        if direcao != (0, 0):
            self.shake_dir_x = -direcao[0] * 0.3
            self.shake_dir_y = -direcao[1] * 0.3
        
        # Zoom punch para golpes pesados
        if tipo_golpe in ["PESADO", "DEVASTADOR", "EPICO"]:
            intensidade_zoom = {
                "PESADO": 0.08,
                "DEVASTADOR": 0.15,
                "EPICO": 0.25
            }.get(tipo_golpe, 0.1)
            
            self._iniciar_zoom_punch(intensidade_zoom * mult_classe)
        
        # Focus para golpes épicos
        if tipo_golpe == "EPICO":
            self._iniciar_focus(posicao, 0.15)
    
    def aplicar_magia_carregada(self, carga: float, posicao: tuple):
        """
        Efeito especial para magias completamente carregadas.
        
        Cria um momento dramático de "BUILD UP" seguido de "RELEASE".
        """
        if carga >= 1.0:
            # Magia completa = efeito máximo
            self.shake_acumulado = 35.0
            self._iniciar_zoom_punch(0.3)
            self._iniciar_focus(posicao, 0.25)
        else:
            # Magia parcial = efeito proporcional
            self.shake_acumulado = min(25.0, 10.0 + carga * 15.0)
            if carga > 0.5:
                self._iniciar_zoom_punch(carga * 0.2)
    
    def _iniciar_zoom_punch(self, intensidade: float):
        """Inicia efeito de zoom punch"""
        self.zoom_punch_ativo = True
        self.zoom_punch_timer = 0.15  # 0.15s de duração
        self.zoom_punch_intensidade = intensidade
        
        if self.camera:
            self.camera.zoom_punch(intensidade, 0.15)
    
    def _iniciar_focus(self, posicao: tuple, duracao: float):
        """Inicia focus momentâneo"""
        self.focus_ativo = True
        self.focus_pos = posicao
        self.focus_timer = duracao
    
    def update(self, dt: float):
        """Atualiza efeitos de câmera"""
        # Decay do shake
        if self.shake_acumulado > 0:
            self.shake_acumulado -= self.shake_decay * dt
            self.shake_acumulado = max(0, self.shake_acumulado)
            
            # Aplica shake na câmera
            if self.camera and self.shake_acumulado > 0:
                # Shake com direção (empurra na direção do golpe, depois randomiza)
                dir_factor = max(0, 1.0 - self.shake_acumulado / 20.0)
                
                shake_x = self.shake_acumulado * (random.uniform(-1, 1) * 0.7 + self.shake_dir_x * dir_factor)
                shake_y = self.shake_acumulado * (random.uniform(-1, 1) * 0.7 + self.shake_dir_y * dir_factor)
                
                self.camera.offset_x = shake_x
                self.camera.offset_y = shake_y
        
        # Decay da direção
        self.shake_dir_x *= (1.0 - dt * 5.0)
        self.shake_dir_y *= (1.0 - dt * 5.0)
        
        # Zoom punch
        if self.zoom_punch_ativo:
            self.zoom_punch_timer -= dt
            if self.zoom_punch_timer <= 0:
                self.zoom_punch_ativo = False
        
        # Focus
        if self.focus_ativo:
            self.focus_timer -= dt
            if self.focus_timer <= 0:
                self.focus_ativo = False


# =============================================================================
# GAME FEEL MANAGER - CLASSE PRINCIPAL DE INTEGRAÇÃO
# =============================================================================

class GameFeelManager:
    """
    Gerenciador central que integra todos os sistemas de Game Feel.
    
    Esta classe é o ponto único de acesso para o simulador interagir com:
    - Hit Stop
    - Super Armor
    - Channeling
    - Camera Feel
    
    Uso típico:
        manager = GameFeelManager.get_instance()
        manager.registrar_lutadores(p1, p2)
        
        # No loop de update:
        dt_efetivo = manager.update(dt)
        
        # Quando um golpe conecta:
        resultado = manager.processar_hit(atacante, alvo, dano, posicao, ...)
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Singleton para acesso global"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset para nova partida"""
        if cls._instance:
            HitStopManager.reset()
        cls._instance = None
    
    def __init__(self):
        self.hit_stop = HitStopManager.get_instance()
        self.camera_feel: Optional[CameraFeel] = None
        
        # Sistemas por lutador
        self.super_armor_systems: Dict[Any, SuperArmorSystem] = {}
        self.channeling_systems: Dict[Any, ChannelingSystem] = {}
        
        # Referências
        self.lutadores = []
        self.camera = None
    
    def set_camera(self, camera):
        """Define a referência da câmera"""
        self.camera = camera
        self.camera_feel = CameraFeel(camera)
    
    def registrar_lutadores(self, *lutadores):
        """Registra lutadores e inicializa seus sistemas"""
        self.lutadores = list(lutadores)
        
        for lutador in lutadores:
            # Sistema de Super Armor
            self.super_armor_systems[lutador] = SuperArmorSystem(lutador)
            
            # Sistema de Channeling
            self.channeling_systems[lutador] = ChannelingSystem(lutador)
    
    def update(self, dt: float) -> float:
        """
        Atualiza todos os sistemas de game feel.
        
        Args:
            dt: Delta time original
            
        Returns:
            dt modificado (pode ser 0 durante hit stop)
        """
        # Hit stop pode zerar o dt
        dt_efetivo = self.hit_stop.update(dt)
        
        # Camera feel sempre atualiza (mesmo em hit stop, para shake suave)
        if self.camera_feel:
            self.camera_feel.update(dt)
        
        # Channeling atualiza com dt efetivo
        for lutador, channeling in self.channeling_systems.items():
            resultado = channeling.update(dt_efetivo)
            if resultado:
                # Uma magia foi liberada - processa
                self._processar_magia_liberada(lutador, resultado)
        
        return dt_efetivo
    
    def processar_hit(self, atacante, alvo, dano: float, posicao: tuple,
                      tipo_golpe: str = "MEDIO", is_critico: bool = False,
                      knockback: tuple = (0, 0)) -> dict:
        """
        Processa um hit completo através de todos os sistemas.
        
        Args:
            atacante: Quem atacou
            alvo: Quem foi atingido
            dano: Dano base
            posicao: (x, y) do impacto
            tipo_golpe: Tipo do golpe
            is_critico: Se foi crítico
            knockback: (kb_x, kb_y) knockback base
            
        Returns:
            Dict com resultado processado:
            {
                "dano_final": float,
                "knockback": (float, float),
                "sofreu_stagger": bool,
                "super_armor_ativa": bool,
                "hit_stop_duracao": float
            }
        """
        classe_atacante = getattr(atacante, 'classe_nome', "Guerreiro (Força Bruta)")
        
        # Verifica Super Armor do alvo
        armor_system = self.super_armor_systems.get(alvo)
        dano_final = dano
        kb_final = knockback
        sofreu_stagger = True
        super_armor_ativa = False
        
        if armor_system and armor_system.data.ativo:
            dano_final, kb_x, kb_y, sofreu_stagger = armor_system.processar_dano(
                dano, knockback[0], knockback[1]
            )
            kb_final = (kb_x, kb_y)
            super_armor_ativa = True
        
        # Verifica interrupção de Channeling do alvo
        channeling_system = self.channeling_systems.get(alvo)
        if channeling_system and channeling_system.esta_canalizando:
            channeling_system.interromper(dano_final)
        
        # Registra hit stop
        cor_flash = (255, 50, 50) if is_critico else (255, 255, 255)
        self.hit_stop.registrar_hit(
            atacante, alvo, dano_final, posicao,
            tipo_golpe, is_critico, cor_flash
        )
        
        # Camera feel
        if self.camera_feel:
            # Calcula direção
            dx = alvo.pos[0] - atacante.pos[0]
            dy = alvo.pos[1] - atacante.pos[1]
            dist = math.hypot(dx, dy) or 1
            direcao = (dx/dist, dy/dist)
            
            self.camera_feel.aplicar_impacto(
                dano_final, classe_atacante, posicao,
                tipo_golpe, direcao
            )
        
        return {
            "dano_final": dano_final,
            "knockback": kb_final,
            "sofreu_stagger": sofreu_stagger,
            "super_armor_ativa": super_armor_ativa,
            "hit_stop_duracao": self.hit_stop.evento_atual.duracao if self.hit_stop.evento_atual else 0
        }
    
    def iniciar_canalizacao(self, lutador, skill_nome: str, skill_data: dict) -> bool:
        """Inicia canalização de magia para um lutador"""
        channeling = self.channeling_systems.get(lutador)
        if channeling:
            return channeling.iniciar_canalizacao(skill_nome, skill_data)
        return False
    
    def _processar_magia_liberada(self, lutador, resultado: dict):
        """Processa uma magia que foi liberada (completa ou interrompida)"""
        if resultado["foi_interrumpido"]:
            # Magia interrompida - efeito visual de falha
            if self.camera_feel:
                self.camera_feel.shake_acumulado = 5.0
        else:
            # Magia completa - efeito épico
            if self.camera_feel:
                self.camera_feel.aplicar_magia_carregada(
                    resultado["carga_final"],
                    (lutador.pos[0], lutador.pos[1])
                )
            
            # Hit stop épico para magia carregada
            self.hit_stop.registrar_hit(
                lutador, None, 100 * resultado["mult_dano"],
                (lutador.pos[0], lutador.pos[1]),
                "EPICO", False, (100, 100, 255)
            )
    
    def verificar_super_armor(self, lutador, progresso_animacao: float = 0.0,
                              acao_atual: str = "") -> bool:
        """Verifica e atualiza super armor de um lutador"""
        armor_system = self.super_armor_systems.get(lutador)
        if armor_system:
            return armor_system.verificar_ativacao(progresso_animacao, acao_atual)
        return False
    
    @property
    def em_hitstop(self) -> bool:
        """Verifica se está em hit stop global"""
        return self.hit_stop.em_hitstop
    
    def get_channeling_system(self, lutador) -> Optional[ChannelingSystem]:
        """Retorna o sistema de channeling de um lutador"""
        return self.channeling_systems.get(lutador)
    
    def get_super_armor_system(self, lutador) -> Optional[SuperArmorSystem]:
        """Retorna o sistema de super armor de um lutador"""
        return self.super_armor_systems.get(lutador)
