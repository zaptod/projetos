"""
NEURAL FIGHTS - Sistema de Personagens
Classe Personagem e funções relacionadas
"""

from neural_fights.models.constants import get_class_data


BASE_VIDA = 80.0
VIDA_POR_RESISTENCIA = 5.0

# Onda 4: escala global de TTK, varrida no harness. A medicao mostrou que
# cadencia sozinha nao alcanca o corredor de 20-40s: com ~4-5 acertos para
# matar, nem um Arco a 2,5s de cooldown chegaria la — o dial real de pacing
# e acertos-para-matar. Knob GLOBAL e neutro por classe (nao contamina a
# atribuicao da O5); a O6 faz o ajuste por classe/tipo em cima desta escala.
ESCALA_VIDA_GLOBAL = 2.8
BASE_MANA = 50.0
MANA_POR_PONTO = 10.0
# Onda 10B: a velocidade e IDENTIDADE DE CLASSE. A base por classe ja e em
# m/s (CLASSES_DATA[...]["velocidade_base_ms"]); peso da arma e forca so
# modulam +-30%. A escala global fica como knob do harness (era 3.0 quando a
# base era forca*2/massa — um Ninja de kunai andava a 6,3 m/s, igual a um
# Cavaleiro, porque mod_forca entrava no numerador e o peso dominava).
ESCALA_VELOCIDADE_MOVIMENTO = 1.0
VELOCIDADE_BASE_PADRAO_MS = 7.0
PESO_ARMA_FATOR_MIN = 0.70


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
        
        # Onda 10B: base por classe (m/s) x fator de peso da arma (0,70-1,05)
        # x fator de forca (0,90-1,10). Garantia de identidade: o Ninja mais
        # pesado e fraco (11,0 x 0,70 x 0,90 = 6,93) anda mais que o Cavaleiro
        # mais leve e forte (5,0 x 1,05 x 1,10 = 5,78).
        base_ms = float(cd.get("velocidade_base_ms", VELOCIDADE_BASE_PADRAO_MS))
        fator_peso = max(PESO_ARMA_FATOR_MIN, min(1.05, 1.10 - 0.05 * self.peso_arma))
        fator_forca = max(0.90, min(1.10, 0.90 + 0.02 * self.forca))
        self.velocidade = base_ms * fator_peso * fator_forca
        
        # Resistência base * modificador de vida
        self.resistencia_base = self.tamanho * self.forca
        self.resistencia = self.resistencia_base * cd.get("mod_vida", 1.0)

    def get_vida_max(self):
        """Retorna vida máxima calculada"""
        base = BASE_VIDA + (self.resistencia_base * VIDA_POR_RESISTENCIA)
        return base * self.class_data.get("mod_vida", 1.0) * ESCALA_VIDA_GLOBAL
    
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
        dados = {
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
        # Onda 11C: kit sorteado na criação viaja com o registro.
        kit = getattr(self, "kit_skills", None)
        if kit:
            dados["kit_skills"] = list(kit)
        return dados
