# hitbox.py - Sistema de Hitbox Modular com Debug v2.0
"""
Sistema centralizado de detecção de colisão para combate.
Inclui logging extensivo para debug.
v2.0 - Integração com WeaponAnalysis para hitboxes mais precisas
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
from utils.config import PPM

# === CONFIGURAÇÃO DE DEBUG ===
DEBUG_HITBOX = False  # Ativar/desativar prints de debug (MUITO VERBOSO)
DEBUG_VISUAL = True  # Mostrar hitboxes visuais no jogo


# === PERFIS DE HITBOX POR TIPO DE ARMA v2.0 ===
# Define características específicas de hitbox para cada tipo
HITBOX_PROFILES = {
    "Reta": {
        "shape": "arc",           # Durante ataque usa arco
        "idle_shape": "line",     # Fora de ataque usa linha
        "base_arc": 90,           # Arco base de ataque em graus
        "attack_arc_mult": 1.2,   # Multiplicador de arco durante ataque
        "range_mult": 2.0,        # Multiplicador de alcance (x raio_char)
        "min_range_ratio": 0.3,   # Ratio mínimo do alcance (para zona morta)
        "hit_window_start": 0.2,  # Quando começa a janela de hit (% da animação)
        "hit_window_end": 0.85,   # Quando termina
        "sweet_spot_start": 0.6,  # Zona de dano máximo início
        "sweet_spot_end": 1.0,    # Zona de dano máximo fim (% do alcance)
    },
    "Dupla": {
        "shape": "dual_arc",
        "idle_shape": "dual_line",
        "base_arc": 100,           # Arco amplo para adagas
        "attack_arc_mult": 2.0,    # Swing bem amplo
        "range_mult": 2.8,         # Alcance maior (adagas velozes)
        "min_range_ratio": 0.05,   # Quase sem zona morta
        "hit_window_start": 0.10,  # Janela mais cedo (ataques rápidos)
        "hit_window_end": 0.85,
        "sweet_spot_start": 0.2,
        "sweet_spot_end": 1.0,
        "offset_angles": [-40, 40],  # Ângulos bem abertos das lâminas
    },
    "Corrente": {
        "shape": "sweep_arc",
        "idle_shape": "arc",
        "base_arc": 180,
        "attack_arc_mult": 1.1,
        "range_mult": 4.0,
        "min_range_ratio": 0.25,    # Zona morta maior
        "hit_window_start": 0.1,
        "hit_window_end": 0.9,
        "sweet_spot_start": 0.7,
        "sweet_spot_end": 1.0,
        "has_dead_zone": True,      # Não acerta muito perto
    },
    "Arremesso": {
        "shape": "projectile_cone",
        "idle_shape": "point",
        "base_arc": 30,
        "attack_arc_mult": 2.0,     # Spread quando joga múltiplos
        "range_mult": 5.0,
        "min_range_ratio": 0.5,
        "hit_window_start": 0.0,
        "hit_window_end": 1.0,
        "is_projectile": True,
    },
    "Arco": {
        "shape": "line",
        "idle_shape": "point",
        "base_arc": 15,
        "attack_arc_mult": 1.0,
        "range_mult": 20.0,        # Arco tem MUITO alcance!
        "min_range_ratio": 0.1,     # Pode atirar de perto também
        "hit_window_start": 0.2,
        "hit_window_end": 0.8,
        "is_projectile": True,
    },
    "Mágica": {
        "shape": "area",
        "idle_shape": "aura",
        "base_arc": 120,
        "attack_arc_mult": 1.0,
        "range_mult": 2.5,
        "min_range_ratio": 0.0,     # Sem zona morta
        "hit_window_start": 0.2,
        "hit_window_end": 0.8,
        "is_area": True,
    },
    "Orbital": {
        "shape": "circle",
        "idle_shape": "circle",
        "base_arc": 360,
        "attack_arc_mult": 1.0,
        "range_mult": 1.5,
        "min_range_ratio": 0.0,
        "hit_window_start": 0.0,
        "hit_window_end": 1.0,
        "always_active": True,
    },
    "Transformável": {
        "shape": "arc",
        "idle_shape": "line",
        "base_arc": 100,
        "attack_arc_mult": 1.15,
        "range_mult": 2.5,
        "min_range_ratio": 0.15,
        "hit_window_start": 0.2,
        "hit_window_end": 0.8,
        "sweet_spot_start": 0.5,
        "sweet_spot_end": 1.0,
    },
}

def debug_log(msg: str, categoria: str = "INFO"):
    """Log de debug condicional"""
    if DEBUG_HITBOX:
        print(f"[HITBOX:{categoria}] {msg}")


def get_hitbox_profile(tipo: str) -> Dict:
    """Retorna o perfil de hitbox para um tipo de arma"""
    # Tenta match exato primeiro
    if tipo in HITBOX_PROFILES:
        return HITBOX_PROFILES[tipo]
    
    # Tenta match parcial
    for key in HITBOX_PROFILES:
        if key in tipo:
            return HITBOX_PROFILES[key]
    
    # Fallback para Reta
    return HITBOX_PROFILES["Reta"]


@dataclass
class HitboxInfo:
    """Informações de uma hitbox para debug e colisão v2.0"""
    tipo: str
    centro: Tuple[float, float]  # Em pixels
    alcance: float  # Em pixels
    angulo: float  # Em graus
    largura_angular: float  # Em graus (para armas de área)
    pontos: List[Tuple[float, float]] = None  # Pontos da linha (para armas de lâmina)
    ativo: bool = False
    
    # Novos campos v2.0
    alcance_minimo: float = 0.0      # Zona morta
    sweet_spot_min: float = 0.0      # Início do sweet spot
    sweet_spot_max: float = 0.0      # Fim do sweet spot
    forma: str = "arc"               # Forma da hitbox
    dano_mult: float = 1.0           # Multiplicador de dano na posição
    profile: Dict = field(default_factory=dict)  # Perfil completo
    
    def __str__(self):
        if self.pontos:
            return f"Hitbox[{self.tipo}] linha=({self.pontos[0]}) -> ({self.pontos[1]}) alcance={self.alcance:.1f}px"
        return f"Hitbox[{self.tipo}] centro={self.centro} alcance={self.alcance:.1f}px ang={self.angulo:.1f}° larg={self.largura_angular:.1f}°"
    
    def get_damage_at_distance(self, dist: float) -> float:
        """Calcula multiplicador de dano baseado na distância (sweet spot)"""
        if dist < self.alcance_minimo:
            return 0.3  # Na zona morta
        
        # Calcula posição relativa no alcance
        alcance_efetivo = self.alcance - self.alcance_minimo
        if alcance_efetivo <= 0:
            return 1.0
        
        pos_relativa = (dist - self.alcance_minimo) / alcance_efetivo
        
        # Verifica se está no sweet spot
        if self.sweet_spot_min <= pos_relativa <= self.sweet_spot_max:
            return 1.2  # Dano aumentado no sweet spot
        
        return 1.0  # Dano normal
    
    def is_in_hitbox(self, pos: Tuple[float, float], raio_alvo: float = 0) -> Tuple[bool, float]:
        """
        Verifica se uma posição está dentro da hitbox.
        Retorna (está_dentro, multiplicador_dano)
        """
        cx, cy = self.centro
        px, py = pos
        
        dist = math.hypot(px - cx, py - cy)
        
        # Verifica alcance
        alcance_efetivo = self.alcance + raio_alvo
        if dist > alcance_efetivo:
            return False, 0.0
        
        if dist < self.alcance_minimo - raio_alvo:
            return False, 0.0
        
        # Verifica ângulo
        ang_para_pos = math.degrees(math.atan2(py - cy, px - cx))
        diff_ang = ang_para_pos - self.angulo
        while diff_ang > 180:
            diff_ang -= 360
        while diff_ang < -180:
            diff_ang += 360
        
        if abs(diff_ang) > self.largura_angular / 2:
            return False, 0.0
        
        # Calcula multiplicador de dano
        dano_mult = self.get_damage_at_distance(dist)
        
        return True, dano_mult


class SistemaHitbox:
    """Sistema centralizado de hitbox com debug"""
    
    def __init__(self):
        self.ultimo_ataque_info = {}  # Cache de info para debug visual
        self.hits_registrados = []  # Histórico de hits
        
    def calcular_hitbox_arma(self, lutador) -> Optional[HitboxInfo]:
        """
        Calcula a hitbox da arma de um lutador.
        Retorna None se não houver hitbox ativa.
        """
        arma = lutador.dados.arma_obj
        if not arma:
            debug_log(f"{lutador.dados.nome}: Sem arma equipada", "WARN")
            return None
        
        # Posição central do lutador em pixels
        cx = lutador.pos[0] * PPM
        cy = lutador.pos[1] * PPM
        raio_char = (lutador.dados.tamanho / 2) * PPM
        fator = lutador.fator_escala
        
        tipo = arma.tipo
        angulo = lutador.angulo_arma_visual
        rad = math.radians(angulo)
        
        debug_log(f"{lutador.dados.nome}: Calculando hitbox tipo={tipo} pos=({cx:.1f}, {cy:.1f}) ang={angulo:.1f}°", "CALC")
        
        # === ARMAS DE CORRENTE (colisão por arco/varredura) ===
        if self._eh_arma_corrente(tipo):
            return self._calcular_hitbox_corrente(lutador, arma, cx, cy, rad, fator, raio_char)
        
        # === ARMAS DE LÂMINA (colisão por linha) ===
        elif self._eh_arma_lamina(tipo):
            return self._calcular_hitbox_lamina(lutador, arma, cx, cy, rad, fator, raio_char)
        
        # === ARMAS RANGED (Arremesso/Arco) - Usam projéteis, não hitbox direta ===
        elif self._eh_arma_ranged(tipo):
            return self._calcular_hitbox_ranged(lutador, arma, cx, cy, rad, fator, raio_char)
        
        # === ARMAS DE ÁREA (Mágica) ===
        elif self._eh_arma_area(tipo):
            return self._calcular_hitbox_area(lutador, arma, cx, cy, rad, fator, raio_char)
        
        # === ARMAS ORBITAIS (colisão especial) ===
        elif "Orbital" in tipo:
            return self._calcular_hitbox_orbital(lutador, arma, cx, cy, fator, raio_char)
        
        # === FALLBACK ===
        else:
            debug_log(f"{lutador.dados.nome}: Tipo de arma desconhecido: {tipo}", "WARN")
            return self._calcular_hitbox_lamina(lutador, arma, cx, cy, rad, fator, raio_char)
    
    def _eh_arma_corrente(self, tipo: str) -> bool:
        """Verifica se é arma de corrente/mangual (usa colisão de arco)"""
        return "Corrente" in tipo
    
    def _eh_arma_lamina(self, tipo: str) -> bool:
        """Verifica se é arma de lâmina (usa colisão de linha)"""
        return any(t in tipo for t in ["Reta", "Dupla", "Transformável"])
    
    def _eh_arma_ranged(self, tipo: str) -> bool:
        """Verifica se é arma ranged (usa projéteis) - inclui Mágica"""
        return any(t in tipo for t in ["Arremesso", "Arco", "Mágica"])
    
    def _eh_arma_area(self, tipo: str) -> bool:
        """Verifica se é arma de área (usa colisão de distância) - Apenas Mágica"""
        return "Mágica" in tipo
    
    def _calcular_hitbox_lamina(self, lutador, arma, cx, cy, rad, fator, raio_char) -> HitboxInfo:
        """
        Calcula hitbox para armas de lâmina v2.0.
        Usa perfis de hitbox para características precisas por tipo.
        """
        tipo = arma.tipo
        profile = get_hitbox_profile(tipo)
        
        # Determina comprimento do cabo e lâmina
        if "Transformável" in tipo:
            forma = getattr(arma, 'forma_atual', 1)
            if forma == 1:
                cabo = getattr(arma, 'forma1_cabo', arma.comp_cabo)
                lamina = getattr(arma, 'forma1_lamina', arma.comp_lamina)
            else:
                cabo = getattr(arma, 'forma2_cabo', arma.comp_cabo)
                lamina = getattr(arma, 'forma2_lamina', arma.comp_lamina)
            debug_log(f"  Transformável forma={forma}: cabo={cabo} lamina={lamina}", "CALC")
        else:
            cabo = arma.comp_cabo
            lamina = arma.comp_lamina
        
        # === LÓGICA DE ESCALA COM PERFIL ===
        tam_base = cabo + lamina
        fator_arma = profile["range_mult"]
        
        # Alcance alvo em pixels
        alcance_alvo = raio_char * fator_arma
        escala = alcance_alvo / max(tam_base, 1)
        
        cabo_px = cabo * escala
        lamina_px = lamina * escala
        alcance_total = cabo_px + lamina_px
        
        # Calcula zona morta e sweet spot baseado no perfil
        alcance_minimo = alcance_total * profile["min_range_ratio"]
        sweet_spot_start = profile.get("sweet_spot_start", 0.6)
        sweet_spot_end = profile.get("sweet_spot_end", 1.0)
        
        # === DURANTE ATAQUE: USA ARCO DE VARREDURA ===
        if lutador.atacando:
            # Pega o perfil de animação para saber o arco total
            try:
                from effects.weapon_animations import WEAPON_PROFILES
                anim_profile = WEAPON_PROFILES.get(tipo, WEAPON_PROFILES.get("Reta"))
                arco_total = abs(anim_profile.anticipation_angle) + abs(anim_profile.attack_angle)
                angulo_centro = lutador.angulo_olhar
            except ImportError:
                arco_total = profile["base_arc"]
                angulo_centro = math.degrees(rad)
            
            # Largura angular: arco de ataque * multiplicador do perfil
            largura_angular = max(profile["base_arc"], arco_total * profile["attack_arc_mult"])
            
            debug_log(f"  Lâmina ATAQUE v2: arco={arco_total:.1f}° largura={largura_angular:.1f}° centro={angulo_centro:.1f}°", "CALC")
            
            return HitboxInfo(
                tipo=tipo,
                centro=(cx, cy),
                alcance=alcance_total,
                angulo=angulo_centro,
                largura_angular=largura_angular,
                pontos=None,
                ativo=True,
                alcance_minimo=alcance_minimo,
                sweet_spot_min=sweet_spot_start,
                sweet_spot_max=sweet_spot_end,
                forma=profile["shape"],
                profile=profile
            )
        
        # === FORA DE ATAQUE: USA LINHA (para debug visual) ===
        x1 = cx + math.cos(rad) * cabo_px
        y1 = cy + math.sin(rad) * cabo_px
        x2 = cx + math.cos(rad) * (cabo_px + lamina_px)
        y2 = cy + math.sin(rad) * (cabo_px + lamina_px)
        
        debug_log(f"  Lâmina IDLE: cabo_px={cabo_px:.1f} lamina_px={lamina_px:.1f}", "CALC")
        
        return HitboxInfo(
            tipo=tipo,
            centro=(cx, cy),
            alcance=alcance_total,
            angulo=math.degrees(rad),
            largura_angular=30.0,
            pontos=[(x1, y1), (x2, y2)],
            ativo=False,
            alcance_minimo=alcance_minimo,
            sweet_spot_min=sweet_spot_start,
            sweet_spot_max=sweet_spot_end,
            forma=profile["idle_shape"],
            profile=profile
        )
    
    def _calcular_hitbox_corrente(self, lutador, arma, cx, cy, rad, fator, raio_char) -> HitboxInfo:
        """
        Calcula hitbox para armas de corrente v2.0.
        A hitbox segue a posição da BOLA na ponta da corrente.
        Usa perfis de hitbox para características precisas.
        """
        tipo = arma.tipo
        profile = get_hitbox_profile("Corrente")
        
        # Pega valores específicos de corrente
        comp_corrente = getattr(arma, 'comp_corrente', 100)
        comp_ponta = getattr(arma, 'comp_ponta', 20)
        largura_ponta = getattr(arma, 'largura_ponta', 10)
        
        # Usa multiplicador do perfil
        fator_arma = profile["range_mult"]
        alcance_alvo = raio_char * fator_arma
        
        # Escala baseada no comp_corrente
        escala = alcance_alvo / max(comp_corrente, 1)
        alcance_px = comp_corrente * escala
        
        # Zona morta - correntes não acertam muito perto
        alcance_minimo = alcance_px * profile["min_range_ratio"]
        
        # A bola está no ângulo atual da arma
        angulo_bola = math.degrees(rad)
        
        # Largura angular da hitbox
        tamanho_bola = max(largura_ponta * escala, raio_char * 0.2)
        largura_base = math.degrees(2 * math.atan2(tamanho_bola, alcance_px))
        
        # Durante ataque, a corrente varre um arco muito maior
        if lutador.atacando:
            angulo_bola = lutador.angulo_olhar
            largura_angular = profile["base_arc"] * profile["attack_arc_mult"]
        else:
            largura_angular = max(largura_base + 30, 45)
        
        debug_log(f"  Corrente v2: comp={comp_corrente} alcance={alcance_px:.1f} zona_morta={alcance_minimo:.1f}", "CALC")
        debug_log(f"  Corrente v2: ang={angulo_bola:.1f}° largura={largura_angular:.1f}° atacando={lutador.atacando}", "CALC")
        
        # Gera pontos do arco para visualização
        pontos_arco = []
        num_segmentos = 6
        ang_inicio = angulo_bola - largura_angular / 2
        ang_fim = angulo_bola + largura_angular / 2
        
        for i in range(num_segmentos + 1):
            ang = math.radians(ang_inicio + (ang_fim - ang_inicio) * i / num_segmentos)
            px = cx + math.cos(ang) * alcance_px
            py = cy + math.sin(ang) * alcance_px
            pontos_arco.append((px, py))
        
        return HitboxInfo(
            tipo="Corrente",
            centro=(cx, cy),
            alcance=alcance_px,
            angulo=angulo_bola,
            largura_angular=largura_angular,
            pontos=pontos_arco,
            ativo=lutador.atacando,
            alcance_minimo=alcance_minimo,
            sweet_spot_min=profile.get("sweet_spot_start", 0.7),
            sweet_spot_max=profile.get("sweet_spot_end", 1.0),
            forma=profile["shape"] if lutador.atacando else profile["idle_shape"],
            profile=profile
        )
    
    def _calcular_hitbox_ranged(self, lutador, arma, cx, cy, rad, fator, raio_char) -> HitboxInfo:
        """
        Calcula hitbox para armas ranged (Arremesso, Arco).
        Estas armas usam PROJÉTEIS, então a hitbox aqui é apenas visual/informativa.
        O dano real é feito pelos projéteis.
        """
        tipo = arma.tipo
        
        # Armas ranged têm alcance maior (onde os projéteis vão)
        if "Arremesso" in tipo:
            fator_arma = 5.0  # Facas voam longe
            qtd = int(getattr(arma, 'quantidade', 3))
        elif "Arco" in tipo:
            fator_arma = 8.0  # Flechas vão mais longe ainda
            qtd = 1
        else:
            fator_arma = 4.0
            qtd = 1
        
        alcance_px = raio_char * fator_arma
        
        # Spread visual (para arremesso com múltiplos projéteis)
        largura_angular = 30.0 if qtd > 1 else 10.0
        
        debug_log(f"  Ranged: tipo={tipo} alcance_px={alcance_px:.1f} qtd={qtd}", "CALC")
        
        # Gera linhas de trajetória para visualização
        pontos_traj = []
        if qtd > 1:
            spread = 25  # graus
            for i in range(qtd):
                offset = -spread/2 + (spread / (qtd-1)) * i
                ang = math.radians(math.degrees(rad) + offset)
                px = cx + math.cos(ang) * alcance_px
                py = cy + math.sin(ang) * alcance_px
                pontos_traj.append((px, py))
        else:
            # Linha única
            px = cx + math.cos(rad) * alcance_px
            py = cy + math.sin(rad) * alcance_px
            pontos_traj = [(cx, cy), (px, py)]
        
        return HitboxInfo(
            tipo=tipo,
            centro=(cx, cy),
            alcance=alcance_px,
            angulo=math.degrees(rad),
            largura_angular=largura_angular,
            pontos=pontos_traj,  # Linhas de trajetória
            ativo=lutador.atacando  # Só mostra quando ataca
        )
    
    def _calcular_hitbox_area(self, lutador, arma, cx, cy, rad, fator, raio_char) -> HitboxInfo:
        """Calcula hitbox para armas de área (Mágica)"""
        tipo = arma.tipo
        
        if "Mágica" in tipo:
            # Mágica: 2.5x o raio
            fator_arma = 2.5
        else:
            fator_arma = 2.0
        
        alcance_px = raio_char * fator_arma
        largura_ang = max(60.0, arma.largura * 2)  # Arco mais generoso
        
        debug_log(f"  Área: raio_char={raio_char:.1f} fator={fator_arma} alcance_px={alcance_px:.1f} largura={largura_ang}°", "CALC")
        
        return HitboxInfo(
            tipo=tipo,
            centro=(cx, cy),
            alcance=alcance_px,
            angulo=math.degrees(rad),
            largura_angular=largura_ang,
            ativo=True  # Armas de área sempre ativas quando equipadas
        )
    
    def _calcular_hitbox_orbital(self, lutador, arma, cx, cy, fator, raio_char) -> HitboxInfo:
        """Calcula hitbox para armas orbitais"""
        # Orbital: 1.5x o raio (escudo/drone orbita perto)
        fator_arma = 1.5
        dist_orbital = raio_char * fator_arma
        
        debug_log(f"  Orbital: raio_char={raio_char:.1f} fator={fator_arma} dist_px={dist_orbital:.1f}", "CALC")
        
        return HitboxInfo(
            tipo="Orbital",
            centro=(cx, cy),
            alcance=dist_orbital,
            angulo=lutador.angulo_arma_visual,
            largura_angular=arma.largura,
            ativo=True
        )
    
    def _verificar_janela_hit(self, atacante, tipo_arma: str) -> bool:
        """
        Verifica se o atacante está na janela de hit correta.
        MUITO MAIS GENEROSA: praticamente toda a animação de ataque conta.
        
        A janela de hit é durante as fases: ATTACK, IMPACT e quase todo FOLLOW_THROUGH
        """
        if not hasattr(atacante, 'timer_animacao'):
            return True  # Se não tem timer, assume que pode acertar
        
        timer = atacante.timer_animacao
        
        # Se não está atacando, sem hit
        if not atacante.atacando:
            return False
        
        # Tenta obter o perfil de animação
        try:
            from effects.weapon_animations import WEAPON_PROFILES
            profile = WEAPON_PROFILES.get(tipo_arma, WEAPON_PROFILES.get("Reta"))
            
            if profile:
                total_time = profile.total_time
                
                # O timer começa em total_time e vai até 0
                if total_time > 0:
                    # Calcula quanto tempo passou desde o início
                    tempo_passado = total_time - timer
                    
                    # Fases da animação (tempos acumulados)
                    t_anticipation_end = profile.anticipation_time
                    t_attack_end = t_anticipation_end + profile.attack_time
                    t_impact_end = t_attack_end + profile.impact_time
                    t_follow_end = t_impact_end + profile.follow_through_time
                    
                    # JANELA GENEROSA: 
                    # Começa bem no início da fase de ataque (50% da anticipation)
                    # Vai até 90% do follow_through
                    janela_inicio = t_anticipation_end * 0.5
                    janela_fim = t_impact_end + (profile.follow_through_time * 0.9)
                    
                    # Verifica se está na janela
                    na_janela = janela_inicio <= tempo_passado <= janela_fim
                    
                    debug_log(f"  Janela hit: tipo={tipo_arma} t_passado={tempo_passado:.3f} " +
                             f"janela=[{janela_inicio:.3f}, {janela_fim:.3f}] ok={na_janela}", "CHECK")
                    
                    return na_janela
        except ImportError:
            pass
        
        # Fallback: muito generoso - quase toda a animação
        # Para correntes, janela mais ampla
        if "Corrente" in tipo_arma:
            return timer < 0.7  # 70% da animação
        # Para armas duplas, janela curta mas frequente
        elif "Dupla" in tipo_arma:
            return timer < 0.25
        # Padrão - muito generoso
        else:
            return timer < 0.5  # 50% da animação
    
    def verificar_colisao(self, atacante, defensor) -> Tuple[bool, str]:
        """
        Verifica se o atacante acerta o defensor.
        Retorna (acertou: bool, motivo: str)
        """
        if defensor.morto:
            return False, "defensor morto"
        
        arma = atacante.dados.arma_obj
        if not arma:
            return False, "sem arma"
        
        # Armas de arremesso, arco e mágicas causam dano APENAS através de projéteis
        # Não verificam colisão por hitbox convencional
        if arma.tipo in ["Arremesso", "Arco", "Mágica"]:
            return False, "arma ranged/mágica - dano via projétil"
        
        # Verifica altura (Z)
        diff_z = abs(atacante.z - defensor.z)
        if diff_z > 1.5:
            debug_log(f"{atacante.dados.nome} vs {defensor.dados.nome}: Falhou - diff_z={diff_z:.2f}", "MISS")
            return False, f"altura diferente (z={diff_z:.2f})"
        
        # Calcula hitbox do atacante
        hitbox = self.calcular_hitbox_arma(atacante)
        if not hitbox:
            return False, "hitbox inválida"
        
        # Posição e raio do defensor
        dx = defensor.pos[0] * PPM
        dy = defensor.pos[1] * PPM
        raio_def = (defensor.dados.tamanho / 2) * PPM
        
        debug_log(f"  Defensor {defensor.dados.nome}: pos=({dx:.1f}, {dy:.1f}) raio={raio_def:.1f}px", "CHECK")
        
        # Armazena info para debug visual
        self.ultimo_ataque_info[atacante.dados.nome] = {
            'hitbox': hitbox,
            'alvo': (dx, dy, raio_def),
            'tempo': 0.5  # segundos para mostrar
        }
        
        # === COLISÃO POR TIPO ===
        
        # Armas ORBITAIS (escudo): sempre causam dano quando o alvo encosta
        if hitbox.tipo == "Orbital":
            # Orbitais não precisam de janela de hit - sempre ativos
            # Verifica apenas distância e ângulo
            acertou, motivo = self._colisao_orbital(hitbox, (dx, dy), raio_def)
            
            if acertou:
                debug_log(f"  HIT! {atacante.dados.nome} -> {defensor.dados.nome} (Orbital)", "HIT")
                self.hits_registrados.append({
                    'atacante': atacante.dados.nome,
                    'defensor': defensor.dados.nome,
                    'tipo': hitbox.tipo
                })
            else:
                debug_log(f"  MISS (Orbital): {motivo}", "MISS")
            
            return acertou, motivo
        
        # Armas de corrente: verifica colisão por arco/varredura
        elif hitbox.tipo == "Corrente":
            # Verifica se está atacando
            if not hitbox.ativo:
                debug_log(f"  {atacante.dados.nome}: Corrente mas não está atacando", "MISS")
                return False, "não está atacando"
            
            # Verifica janela de animação usando o novo sistema de fases
            hit_window_ok = self._verificar_janela_hit(atacante, "Corrente")
            if not hit_window_ok:
                debug_log(f"  {atacante.dados.nome}: Fora da janela de hit", "MISS")
                return False, "fora da janela de hit"
            
            # Colisão por arco: verifica distância E se está dentro do arco angular
            acertou, motivo = self._colisao_arco(hitbox, (dx, dy), raio_def)
            
            if acertou:
                debug_log(f"  HIT! {atacante.dados.nome} -> {defensor.dados.nome} (Corrente)", "HIT")
                self.hits_registrados.append({
                    'atacante': atacante.dados.nome,
                    'defensor': defensor.dados.nome,
                    'tipo': hitbox.tipo
                })
            else:
                debug_log(f"  MISS: {motivo}", "MISS")
            
            return acertou, motivo
        
        # Armas de lâmina ATACANDO: usa colisão de ARCO (varredura)
        elif hitbox.ativo and hitbox.pontos is None:
            # Novo sistema: durante ataque, lâminas usam colisão de arco
            # Verifica janela de animação
            tipo_arma = hitbox.tipo if hitbox.tipo else "Reta"
            hit_window_ok = self._verificar_janela_hit(atacante, tipo_arma)
            if not hit_window_ok:
                debug_log(f"  {atacante.dados.nome}: Fora da janela de hit (arco)", "MISS")
                return False, "fora da janela de hit"
            
            # Usa colisão de área com margem interna zero (lâminas podem acertar de perto)
            acertou, motivo = self._colisao_lamina_arco(hitbox, (dx, dy), raio_def)
            
            # Para armas duplas, segunda chance com offset
            if not acertou and "Dupla" in hitbox.tipo:
                # Tenta com offsets angulares
                for offset in [-25, 25]:
                    hitbox_offset = HitboxInfo(
                        tipo=hitbox.tipo,
                        centro=hitbox.centro,
                        alcance=hitbox.alcance,
                        angulo=hitbox.angulo + offset,
                        largura_angular=hitbox.largura_angular,
                        ativo=True
                    )
                    acertou, motivo = self._colisao_lamina_arco(hitbox_offset, (dx, dy), raio_def)
                    if acertou:
                        break
            
            if acertou:
                debug_log(f"  HIT! {atacante.dados.nome} -> {defensor.dados.nome} (Lâmina Arco)", "HIT")
                self.hits_registrados.append({
                    'atacante': atacante.dados.nome,
                    'defensor': defensor.dados.nome,
                    'tipo': hitbox.tipo
                })
            else:
                debug_log(f"  MISS (arco): {motivo}", "MISS")
            
            return acertou, motivo
        
        # Armas de lâmina NÃO atacando ou com pontos definidos: usa linha
        elif hitbox.pontos and len(hitbox.pontos) == 2:
            # Verifica se está atacando (para armas de swing)
            if not hitbox.ativo:
                debug_log(f"  {atacante.dados.nome}: Arma de lâmina mas não está atacando", "MISS")
                return False, "não está atacando"
            
            # Verifica janela de animação usando o novo sistema de fases
            tipo_arma = hitbox.tipo if hitbox.tipo else "Reta"
            hit_window_ok = self._verificar_janela_hit(atacante, tipo_arma)
            if not hit_window_ok:
                debug_log(f"  {atacante.dados.nome}: Fora da janela de hit", "MISS")
                return False, "fora da janela de hit"
            
            acertou, motivo = self._colisao_linha_circulo(
                hitbox.pontos[0], hitbox.pontos[1],
                (dx, dy), raio_def
            )
            
            # Para armas duplas, verifica segunda lâmina
            if not acertou and "Dupla" in hitbox.tipo:
                acertou, motivo = self._verificar_segunda_lamina(
                    atacante, arma, (dx, dy), raio_def
                )
            
            if acertou:
                debug_log(f"  HIT! {atacante.dados.nome} -> {defensor.dados.nome}", "HIT")
                self.hits_registrados.append({
                    'atacante': atacante.dados.nome,
                    'defensor': defensor.dados.nome,
                    'tipo': hitbox.tipo
                })
            else:
                debug_log(f"  MISS: {motivo}", "MISS")
            
            return acertou, motivo
        
        # Armas de área: verifica distância e ângulo
        else:
            return self._colisao_area(hitbox, (dx, dy), raio_def, atacante.dados.nome)
    
    def _colisao_linha_circulo(self, p1: Tuple[float, float], p2: Tuple[float, float],
                               centro: Tuple[float, float], raio: float) -> Tuple[bool, str]:
        """
        Verifica colisão entre linha (p1->p2) e círculo (centro, raio).
        Retorna (colidiu, motivo)
        """
        x1, y1 = p1
        x2, y2 = p2
        cx, cy = centro
        
        # Vetor da linha
        dx_linha = x2 - x1
        dy_linha = y2 - y1
        
        # Vetor do início da linha até o centro do círculo
        dx_circ = cx - x1
        dy_circ = cy - y1
        
        # Comprimento da linha ao quadrado
        len_sq = dx_linha * dx_linha + dy_linha * dy_linha
        
        if len_sq == 0:
            # Linha degenerada (ponto)
            dist = math.hypot(dx_circ, dy_circ)
            if dist <= raio:
                return True, "ponto dentro do círculo"
            return False, f"ponto fora (dist={dist:.1f}, raio={raio:.1f})"
        
        # Projeção do ponto no segmento (0 = p1, 1 = p2)
        t = max(0, min(1, (dx_circ * dx_linha + dy_circ * dy_linha) / len_sq))
        
        # Ponto mais próximo na linha
        px = x1 + t * dx_linha
        py = y1 + t * dy_linha
        
        # Distância do ponto mais próximo ao centro
        dist = math.hypot(cx - px, cy - py)
        
        debug_log(f"    Linha-círculo: t={t:.2f} ponto_proximo=({px:.1f}, {py:.1f}) dist={dist:.1f} raio={raio:.1f}", "GEOM")
        
        if dist <= raio:
            return True, f"colisão em t={t:.2f}"
        return False, f"sem colisão (dist={dist:.1f} > raio={raio:.1f})"
    
    def _verificar_segunda_lamina(self, atacante, arma, alvo: Tuple[float, float], 
                                   raio: float) -> Tuple[bool, str]:
        """Verifica segunda lâmina de armas duplas"""
        cx = atacante.pos[0] * PPM
        cy = atacante.pos[1] * PPM
        rad = math.radians(atacante.angulo_arma_visual)
        raio_char = (atacante.dados.tamanho / 2) * PPM
        
        # Usa a mesma lógica de escala do _calcular_hitbox_lamina
        cabo = arma.comp_cabo
        lamina = arma.comp_lamina
        tam_base = cabo + lamina
        
        # Adagas: 1.5x o raio
        fator_arma = 1.5
        alcance_alvo = raio_char * fator_arma
        escala = alcance_alvo / max(tam_base, 1)
        
        cabo_px = cabo * escala
        lamina_px = lamina * escala
        
        # Testa ambos os offsets de ângulo
        for offset in [-25, 25]:
            r2 = rad + math.radians(offset)
            x1 = cx + math.cos(r2) * cabo_px
            y1 = cy + math.sin(r2) * cabo_px
            x2 = cx + math.cos(r2) * (cabo_px + lamina_px)
            y2 = cy + math.sin(r2) * (cabo_px + lamina_px)
            
            acertou, motivo = self._colisao_linha_circulo((x1, y1), (x2, y2), alvo, raio)
            if acertou:
                debug_log(f"    Segunda lâmina (offset={offset}°) acertou!", "HIT")
                return True, f"segunda lâmina offset={offset}°"
        
        return False, "segunda lâmina também falhou"
    
    def _colisao_lamina_arco(self, hitbox: HitboxInfo, alvo: Tuple[float, float],
                             raio_alvo: float) -> Tuple[bool, str]:
        """
        Verifica colisão de arco para armas de lâmina.
        Similar ao arco de correntes, mas SEM margem interna (pode acertar de perto).
        """
        cx, cy = hitbox.centro
        ax, ay = alvo
        
        # Distância do centro do atacante ao centro do alvo
        dist = math.hypot(ax - cx, ay - cy)
        
        # Alcance máximo: alcance da arma + raio do alvo + margem
        alcance_max = hitbox.alcance + raio_alvo * 1.2
        
        debug_log(f"    Lâmina arco: dist={dist:.1f} alcance_max={alcance_max:.1f}", "GEOM")
        
        if dist > alcance_max:
            return False, f"fora de alcance (dist={dist:.1f} > max={alcance_max:.1f})"
        
        # Ângulo para o alvo
        ang_para_alvo = math.degrees(math.atan2(ay - cy, ax - cx))
        
        # Diferença angular
        diff_ang = self._normalizar_angulo(ang_para_alvo - hitbox.angulo)
        
        # Para lâminas, a margem angular é metade da largura_angular
        margem = hitbox.largura_angular / 2
        
        debug_log(f"    Lâmina ang: para_alvo={ang_para_alvo:.1f}° hitbox={hitbox.angulo:.1f}° diff={diff_ang:.1f}° margem={margem:.1f}°", "GEOM")
        
        if abs(diff_ang) > margem:
            return False, f"fora do arco (diff={diff_ang:.1f}° > margem={margem:.1f}°)"
        
        return True, "colisão de lâmina (arco)"
    
    def _colisao_area(self, hitbox: HitboxInfo, alvo: Tuple[float, float], 
                      raio_alvo: float, nome_atacante: str) -> Tuple[bool, str]:
        """Verifica colisão de área (distância + ângulo)"""
        cx, cy = hitbox.centro
        dx, dy = alvo
        
        # Distância entre centros
        dist = math.hypot(dx - cx, dy - cy)
        
        # Alcance efetivo (hitbox alcança + raio do alvo)
        alcance_efetivo = hitbox.alcance + raio_alvo
        
        debug_log(f"    Área: dist={dist:.1f} alcance_efetivo={alcance_efetivo:.1f}", "GEOM")
        
        if dist > alcance_efetivo:
            return False, f"fora de alcance (dist={dist:.1f} > alcance={alcance_efetivo:.1f})"
        
        # Ângulo para o alvo
        ang_para_alvo = math.degrees(math.atan2(dy - cy, dx - cx))
        
        # Diferença angular
        diff_ang = self._normalizar_angulo(ang_para_alvo - hitbox.angulo)
        
        debug_log(f"    Ângulo: para_alvo={ang_para_alvo:.1f}° hitbox={hitbox.angulo:.1f}° diff={diff_ang:.1f}° margem={hitbox.largura_angular/2:.1f}°", "GEOM")
        
        if abs(diff_ang) > hitbox.largura_angular / 2:
            return False, f"fora do arco (diff={diff_ang:.1f}° > margem={hitbox.largura_angular/2:.1f}°)"
        
        return True, "colisão de área confirmada"
    
    def _colisao_orbital(self, hitbox: HitboxInfo, alvo: Tuple[float, float],
                         raio_alvo: float) -> Tuple[bool, str]:
        """
        Verifica colisão para armas orbitais (escudo, drone).
        O orbital gira ao redor do personagem e causa dano quando colide.
        
        Verifica se o alvo está próximo da posição atual do orbital.
        """
        cx, cy = hitbox.centro
        ax, ay = alvo
        
        # Posição atual do orbital (no ângulo visual)
        rad = math.radians(hitbox.angulo)
        orbital_x = cx + math.cos(rad) * hitbox.alcance
        orbital_y = cy + math.sin(rad) * hitbox.alcance
        
        # Distância do orbital ao centro do alvo
        dist = math.hypot(ax - orbital_x, ay - orbital_y)
        
        # Raio do orbital (largura está em CENTÍMETROS -> converter para pixels)
        # largura_angular aqui guarda a largura do escudo em cm
        # cm -> m -> px: (cm / 100) * PPM
        raio_orbital = (hitbox.largura_angular / 100.0) * PPM * 0.5
        
        # Garantir raio mínimo visível
        raio_orbital = max(raio_orbital, 15.0)  # mínimo 15px
        
        # Raio de colisão generoso: orbital + alvo + margem
        raio_colisao = raio_orbital + raio_alvo + 5  # +5px de margem
        
        debug_log(f"    Orbital: pos=({orbital_x:.1f}, {orbital_y:.1f}) dist={dist:.1f} raio_col={raio_colisao:.1f} (raio_orb={raio_orbital:.1f})", "GEOM")
        
        if dist <= raio_colisao:
            return True, "colisão orbital (escudo)"
        
        return False, f"orbital fora de alcance (dist={dist:.1f} > raio={raio_colisao:.1f})"
    
    def _colisao_arco(self, hitbox: HitboxInfo, alvo: Tuple[float, float],
                      raio_alvo: float) -> Tuple[bool, str]:
        """
        Verifica colisão de arco (para correntes/mangual).
        A corrente varre um arco, então verifica:
        1. Se o alvo está dentro do alcance da corrente
        2. Se o alvo está dentro do arco angular da varredura
        """
        cx, cy = hitbox.centro
        ax, ay = alvo
        
        # Distância do centro do atacante ao centro do alvo
        dist = math.hypot(ax - cx, ay - cy)
        
        # A corrente tem um "anel" de área de hit
        # Margem interna reduzida: 25% do alcance (para correntes menores)
        # Margem externa: alcance + raio do alvo + margem generosa
        alcance_min = hitbox.alcance * 0.25  # Reduzido de 0.4 para 0.25
        alcance_max = hitbox.alcance + raio_alvo * 1.5  # Margem extra
        
        debug_log(f"    Arco: dist={dist:.1f} alcance_min={alcance_min:.1f} alcance_max={alcance_max:.1f}", "GEOM")
        
        if dist < alcance_min:
            return False, f"muito perto para corrente (dist={dist:.1f} < min={alcance_min:.1f})"
        
        if dist > alcance_max:
            return False, f"fora de alcance (dist={dist:.1f} > max={alcance_max:.1f})"
        
        # Ângulo para o alvo
        ang_para_alvo = math.degrees(math.atan2(ay - cy, ax - cx))
        
        # Diferença angular
        diff_ang = self._normalizar_angulo(ang_para_alvo - hitbox.angulo)
        
        debug_log(f"    Arco ang: para_alvo={ang_para_alvo:.1f}° hitbox={hitbox.angulo:.1f}° diff={diff_ang:.1f}° margem={hitbox.largura_angular/2:.1f}°", "GEOM")
        
        if abs(diff_ang) > hitbox.largura_angular / 2:
            return False, f"fora do arco (diff={diff_ang:.1f}° > margem={hitbox.largura_angular/2:.1f}°)"
        
        return True, "colisão de arco (corrente)"
    
    def _normalizar_angulo(self, ang: float) -> float:
        """Normaliza ângulo para -180 a 180"""
        while ang > 180:
            ang -= 360
        while ang < -180:
            ang += 360
        return ang
    
    def atualizar_debug_visual(self, dt: float):
        """Atualiza timers de debug visual"""
        for nome in list(self.ultimo_ataque_info.keys()):
            self.ultimo_ataque_info[nome]['tempo'] -= dt
            if self.ultimo_ataque_info[nome]['tempo'] <= 0:
                del self.ultimo_ataque_info[nome]
    
    def get_debug_info(self) -> dict:
        """Retorna info de debug para renderização"""
        return {
            'ataques': self.ultimo_ataque_info.copy(),
            'hits': self.hits_registrados[-10:] if self.hits_registrados else []
        }
    
    def limpar_historico(self):
        """Limpa histórico de hits"""
        self.hits_registrados.clear()


# Instância global do sistema
sistema_hitbox = SistemaHitbox()


def verificar_hit(atacante, defensor) -> Tuple[bool, str]:
    """Função de conveniência para verificar hit"""
    return sistema_hitbox.verificar_colisao(atacante, defensor)


def get_debug_visual():
    """Retorna dados para debug visual"""
    return sistema_hitbox.get_debug_info()


def atualizar_debug(dt: float):
    """Atualiza sistema de debug"""
    sistema_hitbox.atualizar_debug_visual(dt)
