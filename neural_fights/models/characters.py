"""
NEURAL FIGHTS - Sistema de Personagens
Classe Personagem e funções relacionadas
"""

from neural_fights.models.constants import get_class_data


BASE_VIDA = 80.0
VIDA_POR_RESISTENCIA = 5.0
BASE_MANA = 50.0
MANA_POR_PONTO = 10.0
ESCALA_VELOCIDADE_MOVIMENTO = 3.0


class Personagem:
    """
    Classe de Personagem com sistema de classes e personalidade.
    """
    def __init__(self, nome, tamanho, forca, mana, nome_arma="", peso_arma_cache=0, 
                 r=200, g=50, b=50, classe="Guerreiro (Força Bruta)", personalidade="Aleatório"):
        self.nome = nome
        self.tamanho = float(tamanho)
        self.forca = float(forca)
        self.mana = float(mana)
        self.nome_arma = nome_arma
        self.cor_r = int(r)
        self.cor_g = int(g)
        self.cor_b = int(b)
        self.classe = classe
        self.personalidade = personalidade  # Personalidade da IA
        self.peso_arma = max(0.0, float(peso_arma_cache))
        
        # Carrega dados da classe
        self.class_data = get_class_data(classe)
        
        self.velocidade = 0.0
        self.resistencia = 0.0
        self.calcular_status(self.peso_arma)

    def calcular_status(self, peso_arma=0):
        """Calcula os atributos derivados usados pela UI e pelo runtime.

        Cada modificador de classe e aplicado exatamente uma vez. O peso da
        arma faz parte do contrato, em vez de existir apenas no carregamento.
        """
        cd = self.class_data
        self.peso_arma = max(0.0, float(peso_arma))
        
        # Força efetiva com modificador de classe
        forca_eff = self.forca * cd.get("mod_forca", 1.0)
        
        massa_total = self.tamanho + self.peso_arma
        if massa_total > 0:
            base_vel = (forca_eff * 2) / massa_total
            self.velocidade = base_vel * cd.get("mod_velocidade", 1.0)
        else:
            self.velocidade = 0
        
        # Resistência base * modificador de vida
        self.resistencia_base = self.tamanho * self.forca
        self.resistencia = self.resistencia_base * cd.get("mod_vida", 1.0)

    def get_vida_max(self):
        """Retorna vida máxima calculada"""
        base = BASE_VIDA + (self.resistencia_base * VIDA_POR_RESISTENCIA)
        return base * self.class_data.get("mod_vida", 1.0)
    
    def get_mana_max(self):
        """Retorna mana máxima calculada"""
        base = BASE_MANA + (self.mana * MANA_POR_PONTO)
        return base * self.class_data.get("mod_mana", 1.0)

    def get_velocidade_movimento(self):
        """Converte o atributo exibido em velocidade planar do runtime."""
        return max(0.0, self.velocidade * ESCALA_VELOCIDADE_MOVIMENTO)
    
    def get_regen_mana(self):
        """Retorna regeneração de mana por segundo"""
        return self.class_data.get("regen_mana", 3.0)
    
    def get_cor_aura(self):
        """Retorna cor de aura da classe"""
        return self.class_data.get("cor_aura", (200, 200, 200))

    def to_dict(self):
        return {
            "nome": self.nome,
            "tamanho": self.tamanho,
            "forca": self.forca,
            "mana": self.mana,
            "nome_arma": self.nome_arma,
            "cor_r": self.cor_r, 
            "cor_g": self.cor_g, 
            "cor_b": self.cor_b,
            "classe": self.classe,
            "personalidade": self.personalidade
        }
