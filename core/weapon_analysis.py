# weapon_analysis.py - Sistema de Análise de Armas v1.0
"""
Sistema avançado para análise e comparação de armas.
Fornece informações detalhadas sobre alcance, perigo, velocidade e matchups.
Usado pela IA para tomar decisões táticas baseadas em armas.
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from enum import Enum


class WeaponStyle(Enum):
    """Estilos de arma que afetam o combate"""
    MELEE_BLADE = "blade"          # Espadas, adagas - ataque linear
    MELEE_CHAIN = "chain"          # Corrente, mangual - ataque em arco
    MELEE_DUAL = "dual"            # Armas duplas - ataques rápidos
    RANGED_THROW = "throw"         # Arremesso - projéteis múltiplos
    RANGED_BOW = "bow"             # Arco - projétil único preciso
    MAGIC_AREA = "magic"           # Mágica - área de efeito
    ORBITAL_DEFENSE = "orbital"    # Orbital - defesa/ataque automático
    TRANSFORM = "transform"        # Transformável - versatilidade


class ThreatLevel(Enum):
    """Níveis de ameaça de uma arma"""
    MINIMAL = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    EXTREME = 4


@dataclass
class WeaponProfile:
    """Perfil detalhado de uma arma para análise tática"""
    # Identificação
    nome: str
    tipo: str
    estilo: WeaponStyle
    
    # Alcances (em metros do jogo)
    alcance_minimo: float      # Distância mínima efetiva
    alcance_ideal: float       # Distância ótima para ataque
    alcance_maximo: float      # Distância máxima de hit
    zona_morta: float          # Zona onde a arma é ineficaz (muito perto)
    
    # Cobertura angular (graus)
    arco_ataque: float         # Ângulo coberto pelo ataque
    arco_perigo: float         # Ângulo de zona de perigo total
    direcao_principal: str     # "frontal", "lateral", "circular"
    
    # Temporização (em segundos)
    tempo_startup: float       # Tempo antes do hit
    tempo_ativo: float         # Janela de hit
    tempo_recovery: float      # Recuperação após ataque
    velocidade_rating: float   # 0-1, quão rápida é a arma
    
    # Características de combate
    dano_base: float
    pode_combo: bool
    interrompe_ataques: bool   # Se causa stagger
    penetra_defesa: float      # 0-1, bypass de defesa
    
    # Zonas de perigo
    zonas_perigosas: List[Tuple[float, float, float]]  # (dist_min, dist_max, angulo)
    pontos_cegos: List[Tuple[float, float, float]]     # (dist_min, dist_max, angulo)
    
    # Matchup info
    forte_contra: List[str]    # Estilos contra os quais é eficaz
    fraco_contra: List[str]    # Estilos que a contrapõem
    
    def get_threat_at_distance(self, distancia: float, angulo_relativo: float = 0) -> ThreatLevel:
        """Calcula nível de ameaça em uma posição específica"""
        # Dentro da zona morta = pouca ameaça
        if distancia < self.zona_morta:
            return ThreatLevel.LOW
        
        # Fora do alcance máximo = sem ameaça
        if distancia > self.alcance_maximo * 1.1:
            return ThreatLevel.MINIMAL
        
        # Normaliza ângulo para -180 a 180
        while angulo_relativo > 180:
            angulo_relativo -= 360
        while angulo_relativo < -180:
            angulo_relativo += 360
        
        # Verifica se está no arco de ataque
        no_arco = abs(angulo_relativo) <= self.arco_perigo / 2
        
        if not no_arco:
            return ThreatLevel.MINIMAL
        
        # Dentro do arco, calcula nível baseado na distância
        if self.alcance_minimo <= distancia <= self.alcance_ideal:
            return ThreatLevel.EXTREME
        elif distancia < self.alcance_minimo:
            return ThreatLevel.MODERATE
        elif distancia <= self.alcance_maximo:
            return ThreatLevel.HIGH
        
        return ThreatLevel.LOW


class WeaponAnalyzer:
    """Analisador de armas para criar perfis e comparações"""
    
    # Dados base por tipo de arma
    WEAPON_BASE_DATA = {
        "Reta": {
            "estilo": WeaponStyle.MELEE_BLADE,
            "zona_morta_mult": 0.2,
            "alcance_mult": 2.5,
            "arco_base": 90,
            "velocidade": 0.6,
            "direcao": "frontal",
            "forte": ["chain", "magic"],
            "fraco": ["dual", "orbital"],
        },
        "Dupla": {
            "estilo": WeaponStyle.MELEE_DUAL,
            "zona_morta_mult": 0.1,
            "alcance_mult": 1.5,
            "arco_base": 120,
            "velocidade": 0.85,
            "direcao": "frontal",
            "forte": ["blade", "bow"],
            "fraco": ["chain", "magic"],
        },
        "Corrente": {
            "estilo": WeaponStyle.MELEE_CHAIN,
            "zona_morta_mult": 0.3,
            "alcance_mult": 4.0,
            "arco_base": 180,
            "velocidade": 0.45,
            "direcao": "circular",
            "forte": ["dual", "throw"],
            "fraco": ["blade", "bow"],
        },
        "Arremesso": {
            "estilo": WeaponStyle.RANGED_THROW,
            "zona_morta_mult": 0.5,
            "alcance_mult": 5.0,
            "arco_base": 60,
            "velocidade": 0.7,
            "direcao": "frontal",
            "forte": ["magic", "blade"],
            "fraco": ["chain", "orbital"],
        },
        "Arco": {
            "estilo": WeaponStyle.RANGED_BOW,
            "zona_morta_mult": 0.8,
            "alcance_mult": 8.0,
            "arco_base": 30,
            "velocidade": 0.5,
            "direcao": "frontal",
            "forte": ["chain", "magic"],
            "fraco": ["dual", "blade"],
        },
        "Mágica": {
            "estilo": WeaponStyle.MAGIC_AREA,
            "zona_morta_mult": 0.0,
            "alcance_mult": 3.0,
            "arco_base": 120,
            "velocidade": 0.4,
            "direcao": "frontal",
            "forte": ["orbital", "dual"],
            "fraco": ["bow", "throw"],
        },
        "Orbital": {
            "estilo": WeaponStyle.ORBITAL_DEFENSE,
            "zona_morta_mult": 0.0,
            "alcance_mult": 1.5,
            "arco_base": 360,
            "velocidade": 0.3,
            "direcao": "circular",
            "forte": ["throw", "blade"],
            "fraco": ["magic", "chain"],
        },
        "Transformável": {
            "estilo": WeaponStyle.TRANSFORM,
            "zona_morta_mult": 0.15,
            "alcance_mult": 2.5,
            "arco_base": 100,
            "velocidade": 0.55,
            "direcao": "frontal",
            "forte": ["dual", "throw"],
            "fraco": ["chain", "bow"],
        },
    }
    
    def __init__(self):
        self._cache_profiles: Dict[str, WeaponProfile] = {}
    
    def analisar_arma(self, arma) -> Optional[WeaponProfile]:
        """Cria perfil detalhado de uma arma"""
        if arma is None:
            return self._criar_perfil_desarmado()
        
        # Cache por nome da arma
        cache_key = f"{arma.nome}_{arma.tipo}"
        if cache_key in self._cache_profiles:
            return self._cache_profiles[cache_key]
        
        tipo = arma.tipo
        base_data = self.WEAPON_BASE_DATA.get(tipo, self.WEAPON_BASE_DATA["Reta"])
        
        # Calcula alcances baseado no tipo
        tamanho_base = self._calcular_tamanho_arma(arma)
        
        alcance_max = tamanho_base * base_data["alcance_mult"]
        zona_morta = tamanho_base * base_data["zona_morta_mult"]
        alcance_ideal = (alcance_max + zona_morta) / 2
        alcance_min = zona_morta * 1.2
        
        # Calcula velocidade
        peso = getattr(arma, 'peso', 5.0)
        vel_base = base_data["velocidade"]
        vel_ajustada = vel_base * (1.0 - peso * 0.03)  # Peso reduz velocidade
        vel_ajustada = max(0.2, min(1.0, vel_ajustada))
        
        # Tempos de animação estimados
        tempo_total = 0.5 / vel_ajustada
        tempo_startup = tempo_total * 0.25
        tempo_ativo = tempo_total * 0.35
        tempo_recovery = tempo_total * 0.4
        
        # Zonas perigosas e pontos cegos
        zonas = self._calcular_zonas_perigosas(tipo, alcance_min, alcance_max, base_data["arco_base"])
        cegos = self._calcular_pontos_cegos(tipo, zona_morta, alcance_max, base_data["arco_base"])
        
        profile = WeaponProfile(
            nome=arma.nome,
            tipo=tipo,
            estilo=base_data["estilo"],
            alcance_minimo=alcance_min,
            alcance_ideal=alcance_ideal,
            alcance_maximo=alcance_max,
            zona_morta=zona_morta,
            arco_ataque=base_data["arco_base"],
            arco_perigo=base_data["arco_base"] * 1.2,
            direcao_principal=base_data["direcao"],
            tempo_startup=tempo_startup,
            tempo_ativo=tempo_ativo,
            tempo_recovery=tempo_recovery,
            velocidade_rating=vel_ajustada,
            dano_base=getattr(arma, 'dano', 10),
            pode_combo="Dupla" in tipo or vel_ajustada > 0.6,
            interrompe_ataques=peso > 5.0,
            penetra_defesa=0.1 if "Mágica" in tipo else 0.0,
            zonas_perigosas=zonas,
            pontos_cegos=cegos,
            forte_contra=base_data["forte"],
            fraco_contra=base_data["fraco"],
        )
        
        self._cache_profiles[cache_key] = profile
        return profile
    
    def _criar_perfil_desarmado(self) -> WeaponProfile:
        """Perfil para combate desarmado"""
        return WeaponProfile(
            nome="Desarmado",
            tipo="Desarmado",
            estilo=WeaponStyle.MELEE_DUAL,
            alcance_minimo=0.3,
            alcance_ideal=0.8,
            alcance_maximo=1.2,
            zona_morta=0.0,
            arco_ataque=120,
            arco_perigo=140,
            direcao_principal="frontal",
            tempo_startup=0.1,
            tempo_ativo=0.15,
            tempo_recovery=0.15,
            velocidade_rating=0.9,
            dano_base=5,
            pode_combo=True,
            interrompe_ataques=False,
            penetra_defesa=0.0,
            zonas_perigosas=[(0.3, 1.2, 120)],
            pontos_cegos=[(0.0, 10.0, 180)],  # Atrás
            forte_contra=["magic"],
            fraco_contra=["blade", "chain"],
        )
    
    def _calcular_tamanho_arma(self, arma) -> float:
        """Calcula tamanho efetivo da arma em metros"""
        tipo = arma.tipo
        
        if tipo == "Reta":
            return (arma.comp_cabo + arma.comp_lamina) / 100.0
        elif tipo == "Dupla":
            return (arma.comp_cabo + arma.comp_lamina) / 100.0 * 0.7
        elif tipo == "Corrente":
            return (getattr(arma, 'comp_corrente', 100) + getattr(arma, 'comp_ponta', 20)) / 100.0
        elif tipo == "Arremesso":
            return getattr(arma, 'tamanho_projetil', 15) / 100.0
        elif tipo == "Arco":
            return getattr(arma, 'tamanho_arco', 80) / 100.0
        elif tipo == "Orbital":
            return (getattr(arma, 'distancia', 30) + arma.largura) / 100.0
        elif tipo == "Mágica":
            return getattr(arma, 'distancia_max', 60) / 100.0
        elif tipo == "Transformável":
            forma1 = (getattr(arma, 'forma1_cabo', 20) + getattr(arma, 'forma1_lamina', 50)) / 100.0
            forma2 = (getattr(arma, 'forma2_cabo', 80) + getattr(arma, 'forma2_lamina', 30)) / 100.0
            return max(forma1, forma2)
        
        return (arma.comp_cabo + arma.comp_lamina + arma.largura) / 100.0
    
    def _calcular_zonas_perigosas(self, tipo: str, alcance_min: float, 
                                   alcance_max: float, arco: float) -> List[Tuple[float, float, float]]:
        """Calcula zonas onde a arma é perigosa"""
        zonas = []
        
        if tipo == "Corrente":
            # Correntes são perigosas em um anel ao redor
            zonas.append((alcance_min, alcance_max, 180))  # Frontal amplo
            zonas.append((alcance_min * 0.8, alcance_max * 0.9, 90))  # Laterais
        elif tipo == "Orbital":
            # Orbital é perigoso em 360 graus
            zonas.append((0, alcance_max, 360))
        elif tipo in ["Arco", "Arremesso"]:
            # Ranged são perigosos em linha reta
            zonas.append((alcance_min, alcance_max, arco))
        else:
            # Melee padrão - frontal
            zonas.append((alcance_min, alcance_max, arco))
        
        return zonas
    
    def _calcular_pontos_cegos(self, tipo: str, zona_morta: float,
                                alcance_max: float, arco: float) -> List[Tuple[float, float, float]]:
        """Calcula pontos cegos da arma"""
        cegos = []
        
        # Ponto cego atrás (quase todas as armas)
        if tipo != "Orbital":
            cegos.append((0, alcance_max * 2, 180 - arco / 2))  # Nas costas
        
        # Ponto cego muito perto para correntes
        if tipo == "Corrente":
            cegos.append((0, zona_morta, 360))  # Muito perto
        
        # Armas ranged tem ponto cego de perto
        if tipo in ["Arco", "Arremesso"]:
            cegos.append((0, zona_morta, 360))
        
        return cegos
    
    def comparar_armas(self, arma1, arma2) -> Dict:
        """Compara duas armas e retorna vantagens/desvantagens"""
        p1 = self.analisar_arma(arma1)
        p2 = self.analisar_arma(arma2)
        
        if not p1 or not p2:
            return {"vencedor": None, "detalhes": "Arma inválida"}
        
        vantagens_1 = []
        vantagens_2 = []
        
        # Compara alcance
        diff_alcance = p1.alcance_maximo - p2.alcance_maximo
        if diff_alcance > 0.5:
            vantagens_1.append(("alcance", diff_alcance))
        elif diff_alcance < -0.5:
            vantagens_2.append(("alcance", -diff_alcance))
        
        # Compara velocidade
        diff_vel = p1.velocidade_rating - p2.velocidade_rating
        if diff_vel > 0.1:
            vantagens_1.append(("velocidade", diff_vel))
        elif diff_vel < -0.1:
            vantagens_2.append(("velocidade", -diff_vel))
        
        # Compara cobertura
        diff_arco = p1.arco_ataque - p2.arco_ataque
        if diff_arco > 20:
            vantagens_1.append(("cobertura", diff_arco))
        elif diff_arco < -20:
            vantagens_2.append(("cobertura", -diff_arco))
        
        # Matchup de estilos
        estilo1 = p1.estilo.value
        estilo2 = p2.estilo.value
        
        if estilo2 in p1.forte_contra:
            vantagens_1.append(("matchup", 0.3))
        if estilo1 in p2.forte_contra:
            vantagens_2.append(("matchup", 0.3))
        
        if estilo2 in p1.fraco_contra:
            vantagens_2.append(("counter", 0.2))
        if estilo1 in p2.fraco_contra:
            vantagens_1.append(("counter", 0.2))
        
        # Calcula score total
        score1 = sum(v[1] for v in vantagens_1)
        score2 = sum(v[1] for v in vantagens_2)
        
        return {
            "arma1": p1.nome,
            "arma2": p2.nome,
            "vantagens_1": vantagens_1,
            "vantagens_2": vantagens_2,
            "score_1": score1,
            "score_2": score2,
            "vencedor": 1 if score1 > score2 else (2 if score2 > score1 else 0),
            "diferenca": abs(score1 - score2),
        }
    
    def calcular_distancia_segura(self, minha_arma, arma_inimigo) -> float:
        """Calcula distância segura contra uma arma inimiga"""
        p_inimigo = self.analisar_arma(arma_inimigo)
        p_minha = self.analisar_arma(minha_arma)
        
        if not p_inimigo:
            return 2.0  # Default seguro
        
        # Distância segura = fora do alcance máximo do inimigo
        dist_segura = p_inimigo.alcance_maximo * 1.2
        
        # Se minha arma tem mais alcance, posso ficar mais perto
        if p_minha and p_minha.alcance_maximo > p_inimigo.alcance_maximo:
            # Fico na minha zona de alcance, fora da dele
            dist_segura = (p_minha.alcance_ideal + p_inimigo.alcance_maximo) / 2
        
        return dist_segura
    
    def calcular_angulo_ataque_ideal(self, minha_arma, arma_inimigo, 
                                      angulo_inimigo: float) -> float:
        """Calcula melhor ângulo para atacar considerando a arma do inimigo"""
        p_inimigo = self.analisar_arma(arma_inimigo)
        
        if not p_inimigo:
            return angulo_inimigo  # Ataca de frente
        
        # Encontra pontos cegos do inimigo
        for dist_min, dist_max, arco_cego in p_inimigo.pontos_cegos:
            if arco_cego >= 90:  # Ponto cego significativo atrás
                # Ataca pelas costas
                return (angulo_inimigo + 180) % 360
        
        # Para correntes, ataca por dentro
        if p_inimigo.estilo == WeaponStyle.MELEE_CHAIN:
            return angulo_inimigo  # Entra na zona morta
        
        # Para armas ranged, flanqueia
        if p_inimigo.estilo in [WeaponStyle.RANGED_BOW, WeaponStyle.RANGED_THROW]:
            # Ataca em diagonal
            return (angulo_inimigo + 45) % 360
        
        return angulo_inimigo
    
    def avaliar_posicao_combate(self, minha_arma, arma_inimigo,
                                 distancia: float, angulo_relativo: float) -> Dict:
        """Avalia uma posição de combate"""
        p_minha = self.analisar_arma(minha_arma)
        p_inimigo = self.analisar_arma(arma_inimigo)
        
        resultado = {
            "posso_atacar": False,
            "inimigo_pode_atacar": False,
            "vantagem": 0.0,
            "recomendacao": "neutro",
            "ameaca_inimigo": ThreatLevel.MINIMAL,
        }
        
        if p_minha:
            # Verifico se estou em posição de atacar
            if p_minha.alcance_minimo <= distancia <= p_minha.alcance_maximo:
                if abs(angulo_relativo) <= p_minha.arco_ataque / 2:
                    resultado["posso_atacar"] = True
        
        if p_inimigo:
            # Verifico ameaça do inimigo
            angulo_para_mim = (angulo_relativo + 180) % 360 - 180
            ameaca = p_inimigo.get_threat_at_distance(distancia, angulo_para_mim)
            resultado["ameaca_inimigo"] = ameaca
            
            if ameaca.value >= ThreatLevel.HIGH.value:
                resultado["inimigo_pode_atacar"] = True
        
        # Calcula vantagem
        if resultado["posso_atacar"] and not resultado["inimigo_pode_atacar"]:
            resultado["vantagem"] = 0.8
            resultado["recomendacao"] = "atacar"
        elif not resultado["posso_atacar"] and resultado["inimigo_pode_atacar"]:
            resultado["vantagem"] = -0.6
            resultado["recomendacao"] = "recuar"
        elif resultado["posso_atacar"] and resultado["inimigo_pode_atacar"]:
            # Compara velocidades
            if p_minha and p_inimigo:
                if p_minha.velocidade_rating > p_inimigo.velocidade_rating:
                    resultado["vantagem"] = 0.3
                    resultado["recomendacao"] = "atacar_rapido"
                else:
                    resultado["vantagem"] = -0.2
                    resultado["recomendacao"] = "esperar"
        else:
            resultado["recomendacao"] = "aproximar"
        
        return resultado


# Instância global do analisador
analisador_armas = WeaponAnalyzer()


def get_weapon_profile(arma) -> Optional[WeaponProfile]:
    """Função de conveniência para obter perfil de arma"""
    return analisador_armas.analisar_arma(arma)


def compare_weapons(arma1, arma2) -> Dict:
    """Função de conveniência para comparar armas"""
    return analisador_armas.comparar_armas(arma1, arma2)


def get_safe_distance(minha_arma, arma_inimigo) -> float:
    """Função de conveniência para calcular distância segura"""
    return analisador_armas.calcular_distancia_segura(minha_arma, arma_inimigo)


def evaluate_combat_position(minha_arma, arma_inimigo, distancia: float, angulo: float) -> Dict:
    """Função de conveniência para avaliar posição de combate"""
    return analisador_armas.avaliar_posicao_combate(minha_arma, arma_inimigo, distancia, angulo)
