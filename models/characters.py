"""
NEURAL FIGHTS - Sistema de Personagens
Classe Personagem e funções relacionadas
"""

from .constants import get_class_data


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
        
        # Carrega dados da classe
        self.class_data = get_class_data(classe)
        
        self.velocidade = 0.0
        self.resistencia = 0.0
        self.calcular_status(peso_arma_cache)

    def calcular_status(self, peso_arma=0):
        """Calcula status com modificadores da classe"""
        cd = self.class_data
        
        # Força efetiva com modificador de classe
        forca_eff = self.forca * cd.get("mod_forca", 1.0)
        
        massa_total = self.tamanho + peso_arma
        if massa_total > 0:
            base_vel = (forca_eff * 2) / massa_total
            self.velocidade = base_vel * cd.get("mod_velocidade", 1.0)
        else:
            self.velocidade = 0
        
        # Resistência base * modificador de vida
        self.resistencia = self.tamanho * self.forca * cd.get("mod_vida", 1.0)

    def get_vida_max(self):
        """Retorna vida máxima calculada"""
        base = 100.0 + (self.resistencia * 10)
        return base * self.class_data.get("mod_vida", 1.0)
    
    def get_mana_max(self):
        """Retorna mana máxima calculada"""
        base = 50.0 + (self.mana * 10)
        return base * self.class_data.get("mod_mana", 1.0)
    
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
