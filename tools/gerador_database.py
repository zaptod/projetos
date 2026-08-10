"""
NEURAL FIGHTS - Gerador de Personagens e Armas v2.0 DIVERSITY EDITION
=====================================================================
Gera personagens e armas com MÁXIMA DIVERSIDADE:
- 16 Classes com estilos únicos
- 6 Raridades com diferenças visuais
- 8 Tipos de Arma com variações de estilo
- 12 Encantamentos elementais
- 30+ Personalidades distintas
- 100+ Skills variadas
- Cores vibrantes e únicas
- Nomes gerados proceduralmente
"""

import random
import logging

from models.constants import (
    LISTA_CLASSES, LISTA_RARIDADES, LISTA_TIPOS_ARMA, 
    LISTA_ENCANTAMENTOS, ENCANTAMENTOS
)
from ai.personalities import PERSONALIDADES_PRESETS
from core.skills import SKILL_DB
from data import database


logger = logging.getLogger(__name__)

# =============================================================================
# CATALOGOS CANONICOS
# =============================================================================


def _agrupar_skills(filtro):
    """Cria visoes do catalogo sem manter uma segunda lista de nomes."""

    grupos = {}
    for nome, dados in SKILL_DB.items():
        if nome == "Nenhuma" or not filtro(dados):
            continue
        elemento = dados.get("elemento", "FISICO")
        grupos.setdefault(elemento, []).append(nome)
    return {elemento: sorted(nomes) for elemento, nomes in grupos.items()}


SKILLS_OFENSIVAS = _agrupar_skills(
    lambda dados: dados.get("tipo")
    in {"PROJETIL", "AREA", "BEAM", "DASH", "CHANNEL", "TRAP", "SUMMON"}
)
SKILLS_DEFENSIVAS = _agrupar_skills(lambda dados: dados.get("tipo") == "BUFF")
SKILLS_UTILIDADE = _agrupar_skills(
    lambda dados: dados.get("tipo") in {"TRANSFORM"}
)
TODAS_SKILLS = sorted(nome for nome in SKILL_DB if nome != "Nenhuma")

# =============================================================================
# ESTILOS E VARIAÇÕES POR TIPO DE ARMA
# =============================================================================

ESTILOS_ARMA = {
    "Reta": {
        "variantes": [
            {"nome": "Espada Longa", "cabo": (20, 30), "lamina": (60, 90), "peso": (3, 5)},
            {"nome": "Espada Curta", "cabo": (15, 20), "lamina": (35, 50), "peso": (2, 3)},
            {"nome": "Montante", "cabo": (35, 45), "lamina": (100, 130), "peso": (6, 9)},
            {"nome": "Katana", "cabo": (25, 30), "lamina": (70, 85), "peso": (2.5, 3.5)},
            {"nome": "Sabre", "cabo": (20, 25), "lamina": (55, 70), "peso": (2, 3)},
            {"nome": "Lança", "cabo": (80, 120), "lamina": (30, 45), "peso": (3, 5)},
            {"nome": "Alabarda", "cabo": (100, 140), "lamina": (40, 55), "peso": (5, 7)},
            {"nome": "Machado", "cabo": (30, 50), "lamina": (25, 40), "peso": (4, 7)},
            {"nome": "Martelo", "cabo": (40, 60), "lamina": (20, 35), "peso": (5, 8)},
            {"nome": "Maça", "cabo": (35, 50), "lamina": (15, 25), "peso": (4, 6)},
            {"nome": "Foice", "cabo": (60, 90), "lamina": (45, 65), "peso": (3, 5)},
            {"nome": "Claymore", "cabo": (30, 40), "lamina": (90, 120), "peso": (5, 8)},
        ],
    },
    "Dupla": {
        "variantes": [
            {"nome": "Adagas Gêmeas", "cabo": (10, 15), "lamina": (25, 35), "peso": (1, 2), "sep": (12, 18)},
            {"nome": "Sai", "cabo": (12, 18), "lamina": (30, 40), "peso": (1.5, 2.5), "sep": (15, 20)},
            {"nome": "Kamas", "cabo": (15, 20), "lamina": (20, 30), "peso": (1, 2), "sep": (18, 25)},
            {"nome": "Garras", "cabo": (5, 10), "lamina": (15, 25), "peso": (0.5, 1.5), "sep": (8, 12)},
            {"nome": "Tonfas", "cabo": (20, 30), "lamina": (10, 15), "peso": (1.5, 2.5), "sep": (20, 28)},
            {"nome": "Facas Táticas", "cabo": (8, 12), "lamina": (18, 28), "peso": (0.8, 1.5), "sep": (10, 15)},
        ],
    },
    "Corrente": {
        "variantes": [
            {"nome": "Kusarigama", "corrente": (70, 100), "ponta": (15, 25), "peso": (3, 5)},
            {"nome": "Mangual", "corrente": (40, 60), "ponta": (20, 35), "peso": (4, 7)},
            {"nome": "Chicote", "corrente": (100, 150), "ponta": (5, 10), "peso": (1.5, 3)},
            {"nome": "Corrente com Peso", "corrente": (60, 90), "ponta": (25, 40), "peso": (5, 8)},
            {"nome": "Meteor Hammer", "corrente": (80, 120), "ponta": (30, 45), "peso": (4, 6)},
            {"nome": "Rope Dart", "corrente": (90, 130), "ponta": (10, 18), "peso": (2, 3)},
        ],
    },
    "Arremesso": {
        "variantes": [
            {"nome": "Facas de Arremesso", "tam": (3, 6), "qtd": (3, 5), "vel": 16, "tipo": "faca"},
            {"nome": "Shuriken", "tam": (4, 7), "qtd": (4, 6), "vel": 18, "tipo": "shuriken"},
            {"nome": "Chakram", "tam": (6, 10), "qtd": (2, 3), "vel": 14, "tipo": "chakram"},
            {"nome": "Machados de Arremesso", "tam": (5, 8), "qtd": (2, 4), "vel": 12, "tipo": "faca"},
            {"nome": "Kunai", "tam": (3, 5), "qtd": (4, 6), "vel": 17, "tipo": "faca"},
            {"nome": "Bumerangue", "tam": (8, 12), "qtd": (1, 2), "vel": 10, "tipo": "chakram"},
        ],
    },
    "Arco": {
        "variantes": [
            {"nome": "Arco Curto", "tamanho": (30, 45), "forca": (15, 30), "flecha": (30, 40)},
            {"nome": "Arco Longo", "tamanho": (50, 70), "forca": (35, 55), "flecha": (45, 60)},
            {"nome": "Arco Composto", "tamanho": (40, 55), "forca": (40, 60), "flecha": (35, 50)},
            {"nome": "Besta Leve", "tamanho": (35, 45), "forca": (50, 70), "flecha": (25, 35)},
            {"nome": "Besta Pesada", "tamanho": (45, 60), "forca": (70, 100), "flecha": (30, 40)},
            {"nome": "Arco Élfico", "tamanho": (55, 75), "forca": (25, 45), "flecha": (50, 65)},
        ],
    },
    "Orbital": {
        "variantes": [
            {"nome": "Escudo Orbital", "dist": (20, 30), "qtd": (1, 2), "largura": 60, "tipo": "escudo"},
            {"nome": "Drones de Combate", "dist": (25, 35), "qtd": (2, 4), "largura": 15, "tipo": "drone"},
            {"nome": "Orbes Místicos", "dist": (20, 28), "qtd": (3, 5), "largura": 10, "tipo": "orbe"},
            {"nome": "Lâminas Orbitais", "dist": (22, 32), "qtd": (2, 4), "largura": 25, "tipo": "lamina"},
            {"nome": "Cristais Flutuantes", "dist": (18, 26), "qtd": (4, 6), "largura": 8, "tipo": "cristal"},
            {"nome": "Sentinelas", "dist": (30, 40), "qtd": (1, 3), "largura": 40, "tipo": "sentinela"},
        ],
    },
    "Mágica": {
        "variantes": [
            {"nome": "Espadas Espectrais", "tam": (10, 18), "qtd": (2, 4), "dist": (35, 50)},
            {"nome": "Runas Flutuantes", "tam": (8, 14), "qtd": (3, 5), "dist": (30, 45)},
            {"nome": "Tentáculos Sombrios", "tam": (15, 25), "qtd": (2, 4), "dist": (40, 60)},
            {"nome": "Cristais Arcanos", "tam": (6, 12), "qtd": (4, 6), "dist": (25, 40)},
            {"nome": "Lanças de Mana", "tam": (12, 20), "qtd": (2, 3), "dist": (45, 65)},
            {"nome": "Chamas Espirituais", "tam": (10, 16), "qtd": (3, 5), "dist": (30, 50)},
        ],
    },
    "Transformável": {
        "variantes": [
            {"nome": "Espada-Lança", "f1_cabo": (20, 30), "f1_lam": (50, 70), "f2_cabo": (60, 90), "f2_lam": (30, 45)},
            {"nome": "Espada Extensível", "f1_cabo": (15, 25), "f1_lam": (40, 55), "f2_cabo": (25, 35), "f2_lam": (70, 100)},
            {"nome": "Chicote-Espada", "f1_cabo": (20, 30), "f1_lam": (55, 75), "f2_cabo": (10, 20), "f2_lam": (100, 140)},
            {"nome": "Arco-Lâminas", "f1_cabo": (30, 40), "f1_lam": (45, 60), "f2_cabo": (15, 25), "f2_lam": (35, 50)},
            {"nome": "Bastão Segmentado", "f1_cabo": (40, 60), "f1_lam": (20, 30), "f2_cabo": (10, 20), "f2_lam": (80, 120)},
            {"nome": "Machado-Martelo", "f1_cabo": (35, 50), "f1_lam": (30, 45), "f2_cabo": (45, 60), "f2_lam": (25, 35)},
        ],
    },
}

# =============================================================================
# NOMES PROCEDURAIS
# =============================================================================

PREFIXOS_MATERIAL = [
    "Aço", "Ferro", "Mithril", "Adamantino", "Obsidiana", "Cristal", "Osso", "Madeira",
    "Prata", "Ouro", "Bronze", "Titânio", "Ébano", "Marfim", "Jade", "Rubi",
]

PREFIXOS_ORIGEM = [
    "Antigo", "Élfico", "Anão", "Orc", "Demoníaco", "Celestial", "Draconico",
    "Imperial", "Tribal", "Real", "Sagrado", "Profano", "Arcano", "Primal",
]

PREFIXOS_QUALIDADE = [
    "Refinado", "Brutal", "Elegante", "Sombrio", "Radiante", "Devastador",
    "Sublime", "Feroz", "Místico", "Letal", "Gracioso", "Implacável",
]

SUFIXOS_ELEMENTO = {
    "Fogo": ["das Chamas", "Flamejante", "do Inferno", "da Pira", "do Magma"],
    "Gelo": ["do Gelo", "Congelante", "do Inverno", "da Nevasca", "do Frio Eterno"],
    "Raio": ["do Trovão", "Elétrico", "da Tempestade", "do Relâmpago", "do Céu Furioso"],
    "Trevas": ["das Sombras", "Sombrio", "do Abismo", "da Escuridão", "do Vazio"],
    "Luz": ["da Luz", "Sagrado", "Divino", "Celestial", "da Aurora"],
    "Natureza": ["da Natureza", "Selvagem", "Venenoso", "Primordial", "da Floresta"],
    "Arcano": ["Arcano", "Místico", "Etéreo", "Dimensional", "do Caos"],
}

SUFIXOS_LENDARIOS = [
    "do Destruidor", "do Protetor", "do Conquistador", "do Herói",
    "da Perdição", "da Salvação", "do Fim", "do Começo",
    "dos Deuses", "dos Titãs", "dos Dragões", "dos Demônios",
    "do Apocalipse", "da Criação", "do Destino", "da Eternidade",
    "do Campeão", "do Vencedor", "do Imortal", "do Lendário",
]

NOMES_MASCULINOS = [
    "Bjorn", "Erik", "Ragnar", "Odin", "Thor", "Fenrir", "Baldur", "Loki", "Freyr", "Tyr",
    "Ares", "Perseus", "Theron", "Icarus", "Orion", "Atlas", "Hector", "Achilles", "Ajax", "Leonidas",
    "Aldric", "Cedric", "Gareth", "Leoric", "Magnus", "Viktor", "Wolfgang", "Roland", "Tristan", "Galahad",
    "Kuro", "Ryu", "Kenji", "Takeshi", "Hiro", "Akira", "Jin", "Kai", "Ren", "Shin",
    "Zephyr", "Phoenix", "Raven", "Draven", "Kael", "Vex", "Silas", "Nero", "Dante", "Vergil",
    "Maximus", "Aurelius", "Cassius", "Brutus", "Marcus", "Lucius", "Titus", "Crixus", "Spartacus", "Caesar",
]

NOMES_FEMININOS = [
    "Freya", "Valkyrie", "Sigrid", "Astrid", "Ingrid", "Helga", "Brunhilde", "Solveig", "Thyra", "Eira",
    "Athena", "Artemis", "Hera", "Circe", "Medusa", "Nyx", "Selene", "Pandora", "Elektra", "Helena",
    "Isolde", "Morgana", "Gwen", "Rowena", "Elara", "Vivienne", "Genevieve", "Adelaide", "Constance", "Beatrix",
    "Yuki", "Sakura", "Akemi", "Mei", "Lin", "Rin", "Hana", "Suki", "Kimiko", "Ayame",
    "Luna", "Nova", "Aria", "Seraphina", "Lyra", "Celeste", "Raven", "Phoenix", "Winter", "Tempest",
    "Aurora", "Diana", "Flora", "Terra", "Victoria", "Gloria", "Lucia", "Julia", "Octavia", "Livia",
]

TITULOS = [
    "o Bravo", "a Valente", "o Nobre", "a Justa", "o Sábio", "a Sábia",
    "o Protetor", "a Protetora", "o Invicto", "a Invicta", "o Lendário", "a Lendária",
    "o Cruel", "a Impiedosa", "o Sombrio", "a Sombria", "o Louco", "a Furiosa",
    "o Destruidor", "a Destruidora", "o Implacável", "a Implacável",
    "das Chamas", "do Gelo", "do Trovão", "das Sombras", "da Luz",
    "o Imortal", "a Eterna", "o Amaldiçoado", "a Abençoada", "o Profeta", "a Vidente",
    "", "", "", "", "", "",
]

# Mantido como alias publico por compatibilidade com scripts antigos. A fonte
# continua sendo PERSONALIDADES_PRESETS; nenhuma personalidade e inventada aqui.
LISTA_PERSONALIDADES = list(PERSONALIDADES_PRESETS)

# =============================================================================
# FUNÇÕES DE GERAÇÃO
# =============================================================================

def gerar_cor_por_raridade(raridade):
    """Gera cor baseada na raridade"""
    paletas = {
        "Comum": [(150, 150, 150), (180, 170, 160), (160, 160, 170)],
        "Incomum": [(50, 200, 50), (80, 220, 80), (40, 180, 100)],
        "Raro": [(50, 100, 220), (70, 130, 255), (100, 150, 230)],
        "Épico": [(160, 50, 220), (180, 80, 255), (140, 60, 200)],
        "Lendário": [(255, 150, 0), (255, 180, 50), (255, 120, 30)],
        "Mítico": [(255, 50, 150), (255, 100, 180), (220, 50, 130)],
    }
    
    base = random.choice(paletas.get(raridade, paletas["Comum"]))
    return tuple(max(0, min(255, c + random.randint(-20, 20))) for c in base)


def gerar_cor_personagem():
    """Gera cor vibrante para personagem"""
    h = random.randint(0, 360)
    s = random.randint(70, 100)
    v = random.randint(80, 100)
    
    c = v * s / 10000
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v / 100 - c
    
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def gerar_nome_arma(tipo, raridade, variante_nome, encantamento=None):
    """Gera nome único para arma"""
    
    if raridade == "Mítico":
        prefixo = random.choice(PREFIXOS_ORIGEM)
        sufixo = random.choice(SUFIXOS_LENDARIOS)
        return f"{prefixo} {variante_nome} {sufixo}"
    
    elif raridade == "Lendário":
        prefixo = random.choice(PREFIXOS_QUALIDADE + PREFIXOS_ORIGEM)
        if encantamento and encantamento in SUFIXOS_ELEMENTO:
            sufixo = random.choice(SUFIXOS_ELEMENTO[encantamento])
        else:
            sufixo = random.choice(SUFIXOS_LENDARIOS)
        return f"{prefixo} {variante_nome} {sufixo}"
    
    elif raridade == "Épico":
        prefixo = random.choice(PREFIXOS_QUALIDADE)
        if encantamento and encantamento in SUFIXOS_ELEMENTO:
            sufixo = random.choice(SUFIXOS_ELEMENTO[encantamento])
        else:
            sufixo = random.choice(["Superior", "Excelso", "Supremo", "Magnífico"])
        return f"{prefixo} {variante_nome} {sufixo}"
    
    elif raridade == "Raro":
        prefixo = random.choice(PREFIXOS_MATERIAL)
        return f"{prefixo} {variante_nome} Refinado"
    
    elif raridade == "Incomum":
        prefixo = random.choice(PREFIXOS_MATERIAL)
        return f"{prefixo} {variante_nome}"
    
    else:
        return f"{variante_nome} Comum"


def gerar_nome_personagem():
    """Gera nome único para personagem"""
    if random.random() < 0.5:
        nome = random.choice(NOMES_MASCULINOS)
    else:
        nome = random.choice(NOMES_FEMININOS)
    
    titulo = random.choice(TITULOS)
    if titulo:
        return f"{nome} {titulo}"
    return nome


def valor_range(r):
    """Retorna valor aleatório de uma tupla (min, max)"""
    return random.uniform(r[0], r[1])


def gerar_arma(tipo, raridade, variante_idx=None, encantamento=None, skill=None):
    """Gera uma arma usando apenas valores presentes nos catalogos canonicos."""

    if tipo not in LISTA_TIPOS_ARMA:
        raise ValueError(f"Tipo de arma desconhecido: {tipo!r}")
    if raridade not in LISTA_RARIDADES:
        raise ValueError(f"Raridade desconhecida: {raridade!r}")
    if encantamento is not None and encantamento not in LISTA_ENCANTAMENTOS:
        raise ValueError(f"Encantamento desconhecido: {encantamento!r}")
    if skill is not None and skill not in SKILL_DB:
        raise ValueError(f"Skill inexistente: {skill!r}")
    
    estilos = ESTILOS_ARMA.get(tipo, ESTILOS_ARMA["Reta"])
    variantes = estilos["variantes"]
    
    if variante_idx is not None:
        variante = variantes[variante_idx % len(variantes)]
    else:
        variante = random.choice(variantes)
    
    nome = gerar_nome_arma(tipo, raridade, variante["nome"], encantamento)
    cor = gerar_cor_por_raridade(raridade)
    
    dano_base = {"Comum": 5, "Incomum": 7, "Raro": 10, "Épico": 13, "Lendário": 17, "Mítico": 22}
    dano = dano_base.get(raridade, 5) + random.uniform(-1, 2)
    
    critico = 2.0 + random.uniform(0, 3) + (1.0 if raridade in ["Épico", "Lendário", "Mítico"] else 0)
    velocidade = 0.8 + random.uniform(0, 0.4)
    
    arma = {
        "nome": nome,
        "tipo": tipo,
        "estilo": variante["nome"],
        "dano": round(dano, 1),
        "peso": round(valor_range(variante.get("peso", (3, 5))), 1),
        "raridade": raridade,
        "r": cor[0],
        "g": cor[1],
        "b": cor[2],
        "critico": round(critico, 1),
        "velocidade_ataque": round(velocidade, 2),
        "encantamentos": [encantamento] if encantamento else [],
        "habilidade": skill if skill else "Nenhuma",
        "habilidades": [skill] if skill else [],
        "custo_mana": random.uniform(10, 25) if skill else 0,
        "cabo_dano": random.choice([True, False]),
        "passiva": None,
        "afinidade_elemento": encantamento,
        "durabilidade": 100.0,
        "durabilidade_max": 100.0,
    }
    
    # Geometria específica por tipo
    if tipo == "Reta":
        arma["comp_cabo"] = valor_range(variante.get("cabo", (20, 30)))
        arma["comp_lamina"] = valor_range(variante.get("lamina", (50, 70)))
        arma["largura"] = random.uniform(5, 12)
        arma["distancia"] = random.uniform(15, 30)
        
    elif tipo == "Dupla":
        arma["comp_cabo"] = valor_range(variante.get("cabo", (10, 15)))
        arma["comp_lamina"] = valor_range(variante.get("lamina", (25, 35)))
        arma["separacao"] = valor_range(variante.get("sep", (12, 18)))
        arma["largura"] = random.uniform(4, 8)
        
    elif tipo == "Corrente":
        arma["comp_corrente"] = valor_range(variante.get("corrente", (60, 100)))
        arma["comp_ponta"] = valor_range(variante.get("ponta", (15, 25)))
        arma["largura_ponta"] = random.uniform(5, 12)
        arma["comp_cabo"] = 15
        arma["comp_lamina"] = 20
        
    elif tipo == "Arremesso":
        arma["tamanho_projetil"] = valor_range(variante.get("tam", (4, 7)))
        arma["largura"] = arma["tamanho_projetil"]
        arma["quantidade"] = random.randint(*variante.get("qtd", (2, 4)))
        arma["velocidade_projetil"] = variante.get("vel", 15)
        arma["tipo_projetil"] = variante.get("tipo", "faca")
        arma["comp_cabo"] = 10
        arma["comp_lamina"] = 20
        
    elif tipo == "Arco":
        arma["tamanho_arco"] = valor_range(variante.get("tamanho", (40, 60)))
        arma["forca_arco"] = valor_range(variante.get("forca", (30, 50)))
        arma["tamanho_flecha"] = valor_range(variante.get("flecha", (35, 50)))
        arma["comp_cabo"] = 20
        arma["comp_lamina"] = 40
        
    elif tipo == "Orbital":
        arma["distancia"] = valor_range(variante.get("dist", (20, 30)))
        arma["quantidade_orbitais"] = random.randint(*variante.get("qtd", (2, 4)))
        arma["largura"] = variante.get("largura", 20)
        arma["tipo_orbital"] = variante.get("tipo", "orbe")
        arma["comp_cabo"] = 10
        arma["comp_lamina"] = 15
        
    elif tipo == "Mágica":
        arma["tamanho"] = valor_range(variante.get("tam", (10, 15)))
        arma["quantidade"] = random.randint(*variante.get("qtd", (2, 4)))
        arma["distancia_max"] = valor_range(variante.get("dist", (30, 50)))
        arma["comp_cabo"] = 10
        arma["comp_lamina"] = 20
        
    elif tipo == "Transformável":
        arma["forma1_cabo"] = valor_range(variante.get("f1_cabo", (20, 30)))
        arma["forma1_lamina"] = valor_range(variante.get("f1_lam", (50, 70)))
        arma["forma2_cabo"] = valor_range(variante.get("f2_cabo", (30, 50)))
        arma["forma2_lamina"] = valor_range(variante.get("f2_lam", (70, 100)))
        arma["comp_cabo"] = arma["forma1_cabo"]
        arma["comp_lamina"] = arma["forma1_lamina"]
        arma["largura"] = 5.0
    
    # Valores padrão para campos ausentes
    for campo in ["comp_cabo", "comp_lamina", "largura", "distancia", "comp_corrente", 
                  "comp_ponta", "largura_ponta", "tamanho_projetil", "quantidade",
                  "tamanho_arco", "forca_arco", "tamanho_flecha", "quantidade_orbitais",
                  "tamanho", "distancia_max", "separacao", "forma1_cabo", "forma1_lamina",
                  "forma2_cabo", "forma2_lamina"]:
        if campo not in arma:
            arma[campo] = 0
    
    return arma


def gerar_personagem(classe, personalidade, arma_nome, cor=None):
    """Gera um personagem compativel com o contrato persistido."""

    if classe not in LISTA_CLASSES:
        raise ValueError(f"Classe desconhecida: {classe!r}")
    if personalidade not in PERSONALIDADES_PRESETS:
        raise ValueError(f"Personalidade inexistente: {personalidade!r}")
    if not isinstance(arma_nome, str) or not arma_nome.strip():
        raise ValueError("arma_nome deve ser uma string nao vazia")
    nome = gerar_nome_personagem()
    
    if cor is None:
        cor = gerar_cor_personagem()
    
    forca_base = 5.0 + random.uniform(-2, 3)
    mana_base = 5.0 + random.uniform(-2, 3)
    
    if "Mago" in classe or "Feiticeiro" in classe or "Bruxo" in classe:
        mana_base += 3
        forca_base -= 1
    elif "Guerreiro" in classe or "Berserker" in classe or "Gladiador" in classe:
        forca_base += 3
        mana_base -= 1
    elif "Assassino" in classe or "Ninja" in classe or "Ladino" in classe:
        forca_base += 1
        mana_base += 1
    elif "Paladino" in classe or "Cavaleiro" in classe:
        forca_base += 2
        mana_base += 1
    elif "Arqueiro" in classe or "Caçador" in classe:
        forca_base += 2
    elif "Monge" in classe:
        forca_base += 2
        mana_base += 2
    
    tamanho = random.uniform(1.4, 2.2)
    personagem = {
        "nome": nome,
        "tamanho": round(tamanho, 2),
        "forca": round(forca_base, 1),
        "mana": round(mana_base, 1),
        "nome_arma": arma_nome,
        "cor_r": cor[0],
        "cor_g": cor[1],
        "cor_b": cor[2],
        "classe": classe,
        "personalidade": personalidade
    }
    
    return personagem


def selecionar_arma_por_classe(classe, armas):
    """Seleciona armas apropriadas para uma classe"""
    preferencias = {
        "Guerreiro": ["Reta", "Transformável"],
        "Mago": ["Mágica", "Orbital"],
        "Assassino": ["Dupla", "Arremesso"],
        "Arqueiro": ["Arco"],
        "Berserker": ["Reta", "Corrente"],
        "Paladino": ["Reta", "Orbital"],
        "Ladino": ["Dupla", "Arremesso"],
        "Monge": ["Corrente", "Dupla"],
        "Ninja": ["Dupla", "Arremesso"],
        "Caçador": ["Arco", "Arremesso"],
        "Cavaleiro": ["Reta"],
        "Samurai": ["Reta", "Transformável"],
        "Feiticeiro": ["Mágica"],
        "Druida": ["Mágica", "Corrente"],
        "Bárbaro": ["Reta", "Corrente"],
        "Necromante": ["Mágica"],
    }
    
    tipos_preferidos = preferencias.get(classe, LISTA_TIPOS_ARMA)
    return [a for a in armas if a["tipo"] in tipos_preferidos]


def _reservar_nome_unico(registro, nomes_usados):
    """Resolve colisoes de nomes de forma deterministica e sem descartar dados."""

    base = registro["nome"].strip()
    nome = base
    sufixo = 2
    while nome in nomes_usados:
        nome = f"{base} #{sufixo}"
        sufixo += 1
    registro["nome"] = nome
    nomes_usados.add(nome)


def gerar_database_diversa(num_personagens=64):
    """Gera database com MÁXIMA DIVERSIDADE"""

    if isinstance(num_personagens, bool) or not isinstance(num_personagens, int):
        raise TypeError("num_personagens deve ser inteiro")
    if num_personagens < 1:
        raise ValueError("num_personagens deve ser maior que zero")
    
    armas = []
    personagens = []
    nomes_armas_usados = set()
    nomes_personagens_usados = set()
    
    logger.debug("Gerando armas diversas")
    
    for tipo in LISTA_TIPOS_ARMA:
        variantes = ESTILOS_ARMA.get(tipo, ESTILOS_ARMA["Reta"])["variantes"]
        
        for var_idx, variante in enumerate(variantes):
            raridade = LISTA_RARIDADES[var_idx % len(LISTA_RARIDADES)]
            enc_idx = (var_idx + LISTA_TIPOS_ARMA.index(tipo)) % len(LISTA_ENCANTAMENTOS)
            encantamento = LISTA_ENCANTAMENTOS[enc_idx]
            
            elemento = ENCANTAMENTOS.get(encantamento, {}).get("elemento", "FISICO")
            skills_elem = SKILLS_OFENSIVAS.get(elemento, SKILLS_OFENSIVAS["FISICO"])
            skill = random.choice(skills_elem)
            
            arma = gerar_arma(tipo, raridade, var_idx, encantamento, skill)
            
            _reservar_nome_unico(arma, nomes_armas_usados)
            armas.append(arma)
    
    for raridade in ["Épico", "Lendário", "Mítico"]:
        for tipo in LISTA_TIPOS_ARMA:
            enc = random.choice(LISTA_ENCANTAMENTOS)
            elemento = ENCANTAMENTOS.get(enc, {}).get("elemento", "ARCANO")
            skill = random.choice(SKILLS_OFENSIVAS.get(elemento, TODAS_SKILLS))
            
            arma = gerar_arma(tipo, raridade, None, enc, skill)
            
            _reservar_nome_unico(arma, nomes_armas_usados)
            armas.append(arma)
    
    logger.debug("%d armas geradas", len(armas))
    logger.debug("Gerando personagens diversos")
    
    for classe_idx, classe in enumerate(LISTA_CLASSES[:num_personagens]):
        personalidade = LISTA_PERSONALIDADES[classe_idx % len(LISTA_PERSONALIDADES)]
        armas_apropriadas = selecionar_arma_por_classe(classe, armas)
        arma = random.choice(armas_apropriadas) if armas_apropriadas else random.choice(armas)
        
        personagem = gerar_personagem(classe, personalidade, arma["nome"])
        
        _reservar_nome_unico(personagem, nomes_personagens_usados)
        personagens.append(personagem)
    
    while len(personagens) < num_personagens:
        classe = random.choice(LISTA_CLASSES)
        personalidade = random.choice(LISTA_PERSONALIDADES)
        arma = random.choice(armas)
        
        personagem = gerar_personagem(classe, personalidade, arma["nome"])
        
        _reservar_nome_unico(personagem, nomes_personagens_usados)
        personagens.append(personagem)
    
    logger.debug("%d personagens gerados", len(personagens))
    
    return armas, personagens


def gerar_database_completa(num_personagens=64, estrategia="balanceada", *, seed=None):
    """API publica do gerador usada pela UI e pelos scripts de torneio.

    ``balanceada`` e ``representativa`` compartilham o mesmo contrato de dados;
    o segundo nome e mantido para compatibilidade com os entrypoints antigos.
    A funcao somente gera e valida: persistir continua sendo uma decisao
    explicita do chamador.
    """

    estrategias = {"balanceada", "representativa", "diversa"}
    if estrategia not in estrategias:
        raise ValueError(
            f"Estrategia desconhecida: {estrategia!r}. "
            f"Use uma de: {', '.join(sorted(estrategias))}"
        )
    estado_random = random.getstate()
    if seed is not None:
        random.seed(seed)
    try:
        armas, personagens = gerar_database_diversa(num_personagens)
        database.validar_database(armas, personagens)
        return armas, personagens
    finally:
        if seed is not None:
            random.setstate(estado_random)


def salvar_database(
    armas,
    personagens,
    substituir=True,
    *,
    arquivo_armas=None,
    arquivo_personagens=None,
):
    """Valida e persiste armas/personagens como uma unidade coerente."""

    armas_file = arquivo_armas or database.ARQUIVO_ARMAS
    personagens_file = arquivo_personagens or database.ARQUIVO_CHARS

    armas_novas = [dict(arma) for arma in armas]
    personagens_novos = [dict(personagem) for personagem in personagens]

    if substituir:
        armas_final = armas_novas
        personagens_final = personagens_novos
    else:
        armas_existentes = database.carregar_json(armas_file)
        personagens_existentes = database.carregar_json(personagens_file)
        database.validar_database(armas_existentes, personagens_existentes)

        nomes_armas = {arma["nome"] for arma in armas_existentes}
        nomes_personagens = {personagem["nome"] for personagem in personagens_existentes}
        conflitos_armas = nomes_armas & {arma.get("nome") for arma in armas_novas}
        conflitos_personagens = nomes_personagens & {
            personagem.get("nome") for personagem in personagens_novos
        }
        conflitos = sorted(conflitos_armas | conflitos_personagens)
        if conflitos:
            raise database.DataValidationError(
                "nomes ja existentes no banco: " + ", ".join(conflitos)
            )

        armas_final = [*armas_existentes, *armas_novas]
        personagens_final = [*personagens_existentes, *personagens_novos]

    database.salvar_database(
        armas_final,
        personagens_final,
        arquivo_armas=armas_file,
        arquivo_personagens=personagens_file,
    )

    logger.info(
        "Database salva: %d armas em %s; %d personagens em %s",
        len(armas_final),
        armas_file,
        len(personagens_final),
        personagens_file,
    )
    
    return armas_final, personagens_final


if __name__ == "__main__":
    print("=" * 60)
    print("NEURAL FIGHTS - Gerador de Database v2.0 DIVERSITY EDITION")
    print("=" * 60)
    
    armas, personagens = gerar_database_diversa(64)
    
    print("\nEstatisticas:")
    
    tipos_count = {}
    for a in armas:
        t = a["tipo"]
        tipos_count[t] = tipos_count.get(t, 0) + 1
    print("  Armas por tipo:")
    for t, c in sorted(tipos_count.items()):
        print(f"    - {t}: {c}")
    
    rar_count = {}
    for a in armas:
        r = a["raridade"]
        rar_count[r] = rar_count.get(r, 0) + 1
    print("  Armas por raridade:")
    for r, c in sorted(rar_count.items(), key=lambda x: LISTA_RARIDADES.index(x[0])):
        print(f"    - {r}: {c}")
    
    classe_count = {}
    for p in personagens:
        c = p["classe"]
        classe_count[c] = classe_count.get(c, 0) + 1
    print("  Personagens por classe:")
    for c, n in sorted(classe_count.items()):
        print(f"    - {c}: {n}")
    
    salvar_database(armas, personagens, substituir=True)
    
    print("\nDatabase gerada com sucesso!")
