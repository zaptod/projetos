"""
NEURAL FIGHTS - Sistema de Armas
Classe Arma e funções de validação/sugestão
"""

import random
from .constants import (
    RARIDADES, TIPOS_ARMA, ENCANTAMENTOS, PASSIVAS_ARMA,
    get_raridade_data, get_tipo_arma_data
)


def gerar_passiva_arma(raridade):
    """Gera uma passiva aleatória baseada na raridade"""
    rar_data = get_raridade_data(raridade)
    tipo_passiva = rar_data.get("passiva")
    if tipo_passiva and tipo_passiva in PASSIVAS_ARMA:
        return random.choice(PASSIVAS_ARMA[tipo_passiva])
    return None


class Arma:
    """
    Classe de Arma expandida com sistema completo de:
    - Raridade (Comum → Mítico)
    - Múltiplos tipos (8 tipos)
    - Múltiplas habilidades (baseado em raridade)
    - Encantamentos empilháveis
    - Passivas únicas
    - Crítico e velocidade de ataque
    - Afinidade elemental
    """
    def __init__(self, nome, tipo, dano, peso, 
                 comp_cabo=0, comp_lamina=0, largura=0, distancia=0,
                 r=200, g=200, b=200, 
                 estilo="Padrao", cabo_dano=False, 
                 habilidade="Nenhuma", custo_mana=0,
                 # === NOVOS CAMPOS ===
                 raridade="Comum",
                 habilidades=None,
                 encantamentos=None,
                 passiva=None,
                 critico=0.0,
                 velocidade_ataque=1.0,
                 afinidade_elemento=None,
                 durabilidade=100.0,
                 durabilidade_max=100.0,
                 # Geometria extra para novos tipos
                 comp_corrente=0, comp_ponta=0, largura_ponta=0,
                 tamanho_projetil=0, quantidade=1,
                 tamanho_arco=0, forca_arco=0, tamanho_flecha=0,
                 quantidade_orbitais=1,
                 forma1_cabo=0, forma1_lamina=0, forma2_cabo=0, forma2_lamina=0,
                 tamanho=0, distancia_max=0, separacao=0,
                 **kwargs): 
        
        self.nome = nome
        self.tipo = tipo
        self.raridade = raridade
        self.dano_base = float(dano)
        self.peso_base = float(peso)
        
        # Aplica modificadores de raridade
        rar_data = get_raridade_data(raridade)
        self.dano = self.dano_base * rar_data["mod_dano"]
        self.peso = self.peso_base * rar_data["mod_peso"]
        
        # Geometria básica (Reta/Orbital)
        self.comp_cabo = float(comp_cabo)
        self.comp_lamina = float(comp_lamina)
        self.largura = float(largura)
        self.distancia = float(distancia)
        
        # Geometria Corrente
        self.comp_corrente = float(comp_corrente)
        self.comp_ponta = float(comp_ponta)
        self.largura_ponta = float(largura_ponta)
        
        # Geometria Arremesso
        self.tamanho_projetil = float(tamanho_projetil)
        self.quantidade = int(quantidade)
        
        # Geometria Arco
        self.tamanho_arco = float(tamanho_arco)
        self.forca_arco = float(forca_arco)
        self.tamanho_flecha = float(tamanho_flecha)
        
        # Geometria Orbital
        self.quantidade_orbitais = int(quantidade_orbitais)
        
        # Geometria Mágica
        self.tamanho = float(tamanho) if tamanho else float(largura)
        self.distancia_max = float(distancia_max)
        
        # Geometria Dupla
        self.separacao = float(separacao)
        
        # Geometria Transformável
        self.forma1_cabo = float(forma1_cabo)
        self.forma1_lamina = float(forma1_lamina)
        self.forma2_cabo = float(forma2_cabo)
        self.forma2_lamina = float(forma2_lamina)
        self.forma_atual = 1

        # Comportamento
        self.estilo = estilo
        self.cabo_dano = bool(cabo_dano)
        
        # === SISTEMA DE HABILIDADES MÚLTIPLAS ===
        if habilidades is None:
            if habilidade != "Nenhuma":
                self.habilidades = [{"nome": habilidade, "custo": float(custo_mana)}]
            else:
                self.habilidades = []
        else:
            self.habilidades = habilidades
        
        # Mantém compatibilidade com código antigo
        if self.habilidades:
            first_hab = self.habilidades[0]
            if isinstance(first_hab, dict):
                self.habilidade = first_hab.get("nome", "Nenhuma")
                self.custo_mana = first_hab.get("custo", custo_mana)
            else:
                self.habilidade = str(first_hab)
                self.custo_mana = float(custo_mana)
        else:
            self.habilidade = "Nenhuma"
            self.custo_mana = float(custo_mana)
        
        # === SISTEMA DE ENCANTAMENTOS ===
        self.encantamentos = encantamentos or []
        
        # === PASSIVA ===
        if passiva is None and rar_data.get("passiva"):
            self.passiva = gerar_passiva_arma(raridade)
        else:
            self.passiva = passiva
        
        # === STATS EXTRAS ===
        self.critico = float(critico) + rar_data["mod_critico"]
        self.velocidade_ataque = float(velocidade_ataque) * rar_data["mod_velocidade_ataque"]
        self.afinidade_elemento = afinidade_elemento
        
        # === DURABILIDADE ===
        self.durabilidade_max = float(durabilidade_max) * rar_data["mod_durabilidade"]
        self.durabilidade = min(float(durabilidade), self.durabilidade_max)

        # Cores
        self.r = int(r); self.g = int(g); self.b = int(b)
        
        # Cor da raridade
        self.cor_raridade = rar_data["cor"]
        self.efeito_visual = rar_data.get("efeito_visual")
        
        # Migração de dados antigos
        tamanho_antigo = float(kwargs.get('tamanho', 0))
        if self.comp_cabo == 0 and tamanho_antigo > 0:
            if "Reta" in tipo:
                self.comp_cabo = tamanho_antigo * 0.3
                self.comp_lamina = tamanho_antigo * 0.7
                self.largura = 5
            else:
                self.largura = tamanho_antigo
                self.distancia = 30

    def get_dano_total(self):
        """Calcula dano total incluindo encantamentos"""
        dano = self.dano
        for enc_nome in self.encantamentos:
            if enc_nome in ENCANTAMENTOS:
                dano += ENCANTAMENTOS[enc_nome].get("dano_bonus", 0)
        return dano
    
    def get_slots_disponiveis(self):
        """Retorna quantos slots de habilidade ainda estão livres"""
        max_slots = get_raridade_data(self.raridade)["slots_habilidade"]
        return max_slots - len(self.habilidades)
    
    def adicionar_habilidade(self, nome_skill, custo):
        """Adiciona uma habilidade se houver slot"""
        if self.get_slots_disponiveis() > 0:
            self.habilidades.append({"nome": nome_skill, "custo": float(custo)})
            if len(self.habilidades) == 1:
                self.habilidade = nome_skill
                self.custo_mana = float(custo)
            return True
        return False
    
    def adicionar_encantamento(self, nome_enc):
        """Adiciona um encantamento se possível"""
        max_enc = get_raridade_data(self.raridade)["max_encantamentos"]
        if len(self.encantamentos) < max_enc and nome_enc in ENCANTAMENTOS:
            self.encantamentos.append(nome_enc)
            return True
        return False
    
    def trocar_forma(self):
        """Troca a forma (apenas para armas Transformáveis)"""
        if self.tipo == "Transformável":
            if self.forma_atual == 1:
                self.forma_atual = 2
                self.comp_cabo, self.comp_lamina = self.forma2_cabo, self.forma2_lamina
            else:
                self.forma_atual = 1
                self.comp_cabo, self.comp_lamina = self.forma1_cabo, self.forma1_lamina

    def to_dict(self):
        return {
            "nome": self.nome,
            "tipo": self.tipo,
            "dano": self.dano_base,
            "peso": self.peso_base,
            "raridade": self.raridade,
            "comp_cabo": self.comp_cabo,
            "comp_lamina": self.comp_lamina,
            "largura": self.largura,
            "distancia": self.distancia,
            "comp_corrente": self.comp_corrente,
            "comp_ponta": self.comp_ponta,
            "largura_ponta": self.largura_ponta,
            "tamanho_projetil": self.tamanho_projetil,
            "quantidade": self.quantidade,
            "tamanho_arco": self.tamanho_arco,
            "forca_arco": self.forca_arco,
            "tamanho_flecha": self.tamanho_flecha,
            "quantidade_orbitais": self.quantidade_orbitais,
            "tamanho": self.tamanho,
            "distancia_max": self.distancia_max,
            "separacao": self.separacao,
            "forma1_cabo": self.forma1_cabo,
            "forma1_lamina": self.forma1_lamina,
            "forma2_cabo": self.forma2_cabo,
            "forma2_lamina": self.forma2_lamina,
            "r": self.r, "g": self.g, "b": self.b,
            "estilo": self.estilo,
            "cabo_dano": self.cabo_dano,
            "habilidades": self.habilidades,
            "encantamentos": self.encantamentos,
            "passiva": self.passiva,
            "critico": self.critico - get_raridade_data(self.raridade)["mod_critico"],
            "velocidade_ataque": self.velocidade_ataque / get_raridade_data(self.raridade)["mod_velocidade_ataque"],
            "afinidade_elemento": self.afinidade_elemento,
            "durabilidade": self.durabilidade,
            "durabilidade_max": self.durabilidade_max / get_raridade_data(self.raridade)["mod_durabilidade"],
            "habilidade": self.habilidade,
            "custo_mana": self.custo_mana,
        }


# ============================================================================
# SISTEMA DE VALIDAÇÃO DE TAMANHO ARMA vs PERSONAGEM
# ============================================================================

def calcular_tamanho_arma(arma):
    """
    Calcula o tamanho total efetivo da arma baseado no tipo.
    Retorna o tamanho em unidades do jogo.
    """
    if arma is None:
        return 0
    
    tipo = arma.tipo
    
    if tipo == "Reta":
        return (arma.comp_cabo + arma.comp_lamina) / 100.0
    elif tipo == "Dupla":
        return (arma.comp_cabo + arma.comp_lamina) / 100.0 * 0.7
    elif tipo == "Corrente":
        return (arma.comp_corrente + arma.comp_ponta) / 100.0
    elif tipo == "Arremesso":
        return arma.tamanho_projetil / 100.0 * 0.5
    elif tipo == "Arco":
        return arma.tamanho_arco / 100.0
    elif tipo == "Orbital":
        return (arma.distancia + arma.largura) / 100.0
    elif tipo == "Mágica":
        return arma.distancia_max / 100.0 if arma.distancia_max > 0 else 1.0
    elif tipo == "Transformável":
        forma1 = (arma.forma1_cabo + arma.forma1_lamina) / 100.0
        forma2 = (arma.forma2_cabo + arma.forma2_lamina) / 100.0
        return max(forma1, forma2)
    
    return (arma.comp_cabo + arma.comp_lamina + arma.largura) / 100.0


def validar_arma_personagem(arma, personagem):
    """
    Valida se a arma é apropriada para o tamanho do personagem.
    """
    if arma is None or personagem is None:
        return {
            "valido": True,
            "mensagem": "Sem arma equipada",
            "sugestao": None,
            "proporcao": 0
        }
    
    tamanho_arma = calcular_tamanho_arma(arma)
    tamanho_char = personagem.tamanho / 10.0
    
    if tamanho_char <= 0:
        tamanho_char = 1.0
    
    proporcao = tamanho_arma / tamanho_char
    
    MIN_PROPORCAO = 0.2
    MAX_PROPORCAO = 3.0
    IDEAL_MIN = 0.4
    IDEAL_MAX = 1.5
    
    resultado = {
        "proporcao": proporcao,
        "tamanho_arma": tamanho_arma,
        "tamanho_char": tamanho_char
    }
    
    if proporcao < MIN_PROPORCAO:
        resultado["valido"] = False
        resultado["mensagem"] = f"⚠️ Arma MUITO PEQUENA ({proporcao:.1%} do personagem)"
        resultado["sugestao"] = f"Aumente o tamanho da arma ou use personagem menor"
        resultado["nivel"] = "critico"
    elif proporcao < IDEAL_MIN:
        resultado["valido"] = True
        resultado["mensagem"] = f"⚡ Arma pequena ({proporcao:.1%} do personagem)"
        resultado["sugestao"] = "Arma funcional, mas pode parecer pequena visualmente"
        resultado["nivel"] = "aviso"
    elif proporcao > MAX_PROPORCAO:
        resultado["valido"] = False
        resultado["mensagem"] = f"⚠️ Arma MUITO GRANDE ({proporcao:.1%} do personagem)"
        resultado["sugestao"] = f"Diminua o tamanho da arma ou use personagem maior"
        resultado["nivel"] = "critico"
    elif proporcao > IDEAL_MAX:
        resultado["valido"] = True
        resultado["mensagem"] = f"⚡ Arma grande ({proporcao:.1%} do personagem)"
        resultado["sugestao"] = "Arma funcional, pode parecer exagerada"
        resultado["nivel"] = "aviso"
    else:
        resultado["valido"] = True
        resultado["mensagem"] = f"✓ Proporção ideal ({proporcao:.1%} do personagem)"
        resultado["sugestao"] = None
        resultado["nivel"] = "ok"
    
    return resultado


def sugerir_tamanho_arma(personagem, tipo_arma="Reta"):
    """
    Sugere tamanhos ideais para uma arma baseado no personagem.
    """
    if personagem is None:
        tamanho_base = 10.0
    else:
        tamanho_base = personagem.tamanho / 10.0
    
    sugestoes = {}
    
    if tipo_arma == "Reta":
        sugestoes = {
            "comp_cabo": int(tamanho_base * 30),
            "comp_lamina": int(tamanho_base * 70),
            "largura": int(tamanho_base * 8),
        }
    elif tipo_arma == "Dupla":
        sugestoes = {
            "comp_cabo": int(tamanho_base * 15),
            "comp_lamina": int(tamanho_base * 35),
            "largura": int(tamanho_base * 5),
            "separacao": int(tamanho_base * 20),
        }
    elif tipo_arma == "Corrente":
        sugestoes = {
            "comp_corrente": int(tamanho_base * 150),
            "comp_ponta": int(tamanho_base * 20),
            "largura_ponta": int(tamanho_base * 10),
        }
    elif tipo_arma == "Arremesso":
        sugestoes = {
            "tamanho_projetil": int(tamanho_base * 15),
            "largura": int(tamanho_base * 10),
            "quantidade": 3,
        }
    elif tipo_arma == "Arco":
        sugestoes = {
            "tamanho_arco": int(tamanho_base * 80),
            "forca_arco": int(tamanho_base * 5),
            "tamanho_flecha": int(tamanho_base * 40),
        }
    elif tipo_arma == "Orbital":
        sugestoes = {
            "largura": int(tamanho_base * 40),
            "distancia": int(tamanho_base * 30),
            "quantidade_orbitais": 1,
        }
    elif tipo_arma == "Mágica":
        sugestoes = {
            "quantidade": 3,
            "tamanho": int(tamanho_base * 15),
            "distancia_max": int(tamanho_base * 60),
        }
    elif tipo_arma == "Transformável":
        sugestoes = {
            "forma1_cabo": int(tamanho_base * 20),
            "forma1_lamina": int(tamanho_base * 50),
            "forma2_cabo": int(tamanho_base * 80),
            "forma2_lamina": int(tamanho_base * 30),
            "largura": int(tamanho_base * 6),
        }
    
    return sugestoes


def get_escala_visual_arma(arma, personagem):
    """
    Retorna um fator de escala para renderização visual da arma.
    """
    if arma is None or personagem is None:
        return 1.0
    
    validacao = validar_arma_personagem(arma, personagem)
    proporcao = validacao["proporcao"]
    
    if proporcao < 0.4:
        return 0.4 / proporcao
    elif proporcao > 1.5:
        return 1.5 / proporcao
    
    return 1.0
