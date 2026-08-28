"""
NEURAL FIGHTS - Constantes do Sistema
Raridades, Tipos de Armas, Encantamentos, Classes, Passivas
"""

# ============================================================================
# SISTEMA DE RARIDADE
# ============================================================================

RARIDADES = {
    "Comum": {
        "cor": (180, 180, 180),
        "cor_hex": "#B4B4B4",
        "slots_habilidade": 1,
        "mod_dano": 0.6,
        "mod_peso": 1.0,
        "mod_durabilidade": 1.0,
        "mod_critico": 0.0,
        "mod_velocidade_ataque": 1.0,
        "passiva": None,
        "efeito_visual": None,
        "chance_encantamento": 0,
        "max_encantamentos": 0,
        "descricao": "Arma comum sem atributos especiais"
    },
    "Incomum": {
        "cor": (100, 200, 100),
        "cor_hex": "#64C864",
        "slots_habilidade": 1,
        "mod_dano": 0.7,
        "mod_peso": 0.95,
        "mod_durabilidade": 1.15,
        "mod_critico": 0.03,
        "mod_velocidade_ataque": 1.05,
        "passiva": None,
        "efeito_visual": "brilho_leve",
        "chance_encantamento": 10,
        "max_encantamentos": 1,
        "descricao": "Arma de qualidade superior"
    },
    "Raro": {
        "cor": (80, 140, 255),
        "cor_hex": "#508CFF",
        "slots_habilidade": 2,
        "mod_dano": 0.8,
        "mod_peso": 0.9,
        "mod_durabilidade": 1.3,
        "mod_critico": 0.05,
        "mod_velocidade_ataque": 1.1,
        "passiva": "random_minor",
        "efeito_visual": "brilho_medio",
        "chance_encantamento": 25,
        "max_encantamentos": 2,
        "descricao": "Arma rara com propriedades mágicas"
    },
    "Épico": {
        "cor": (180, 80, 220),
        "cor_hex": "#B450DC",
        "slots_habilidade": 2,
        "mod_dano": 0.9,
        "mod_peso": 0.85,
        "mod_durabilidade": 1.5,
        "mod_critico": 0.08,
        "mod_velocidade_ataque": 1.15,
        "passiva": "random_major",
        "efeito_visual": "particulas",
        "chance_encantamento": 50,
        "max_encantamentos": 3,
        "descricao": "Arma épica forjada com magia antiga"
    },
    "Lendário": {
        "cor": (255, 180, 50),
        "cor_hex": "#FFB432",
        "slots_habilidade": 3,
        "mod_dano": 1.0,
        "mod_peso": 0.8,
        "mod_durabilidade": 2.0,
        "mod_critico": 0.12,
        "mod_velocidade_ataque": 1.2,
        "passiva": "unique",
        "efeito_visual": "aura_dourada",
        "chance_encantamento": 75,
        "max_encantamentos": 4,
        "descricao": "Arma lendária de poder imenso"
    },
    "Mítico": {
        "cor": (255, 100, 100),
        "cor_hex": "#FF6464",
        "glow": (255, 50, 50),
        "slots_habilidade": 4,
        "mod_dano": 1.2,
        "mod_peso": 0.7,
        "mod_durabilidade": 3.0,
        "mod_critico": 0.15,
        "mod_velocidade_ataque": 1.3,
        "passiva": "mythic",
        "efeito_visual": "chamas_miticas",
        "chance_encantamento": 100,
        "max_encantamentos": 5,
        "descricao": "Arma mítica - poder além da compreensão"
    }
}

LISTA_RARIDADES = ["Comum", "Incomum", "Raro", "Épico", "Lendário", "Mítico"]


# ============================================================================
# SISTEMA DE TIPOS DE ARMAS
# ============================================================================

TIPOS_ARMA = {
    "Reta": {
        "categoria": "Melee",
        "descricao": "Arma linear tradicional (espadas, lanças)",
        "estilos": ["Corte (Espada)", "Estocada (Lança)", "Contusão (Maça)", "Misto"],
        "geometria": ["comp_cabo", "comp_lamina", "largura"],
        "mod_dano": 1.0,
        "mod_velocidade": 1.0,
        "alcance_base": 1.5,
        "cadencia_base_s": 1.2,
    },
    "Dupla": {
        "categoria": "Melee",
        "descricao": "Par de armas que alternam ataques",
        "estilos": ["Adagas Gêmeas", "Kamas", "Sai", "Garras"],
        "geometria": ["comp_cabo", "comp_lamina", "largura", "separacao"],
        "mod_dano": 0.7,
        "mod_velocidade": 1.5,
        "alcance_base": 1.0,
        # Onda 10B: adagas atacam mais rapido que a espada pesada (era 1.2, igual
        # a Reta) — a identidade "entra e sai" vem da cadencia + dash barato.
        "cadencia_base_s": 0.85,
        "hits_por_ataque": 2,
    },
    "Corrente": {
        "categoria": "Melee",
        "descricao": "Arma com física de corda/corrente",
        "estilos": ["Kusarigama", "Flail (Mangual)", "Chicote", "Corrente com Peso"],
        "geometria": ["comp_corrente", "comp_ponta", "largura_ponta"],
        "mod_dano": 1.1,
        "mod_velocidade": 0.8,
        "alcance_base": 3.0,
        "cadencia_base_s": 1.2,
        "physics": "chain",
    },
    "Arremesso": {
        "categoria": "Ranged",
        "descricao": "Projéteis que podem retornar",
        "estilos": ["Machado (Não Retorna)", "Faca (Rápida)", "Chakram (Retorna)", "Bumerangue"],
        "geometria": ["tamanho_projetil", "largura", "quantidade"],
        "mod_dano": 0.9,
        "mod_velocidade": 1.2,
        "alcance_base": 10.0,
        "cadencia_base_s": 1.35,
        "retorna": False,
    },
    "Arco": {
        "categoria": "Ranged",
        "descricao": "Dispara flechas/virotes à distância",
        "estilos": ["Arco Curto", "Arco Longo", "Besta", "Besta de Repetição"],
        "geometria": ["tamanho_arco", "forca_arco", "tamanho_flecha"],
        "mod_dano": 1.2,
        "mod_velocidade": 0.7,
        "alcance_base": 14.0,
        "cadencia_base_s": 1.7,
        "requer_municao": True,
    },
    "Orbital": {
        "categoria": "Defensive",
        "descricao": "Escudos e drones orbitais",
        "estilos": ["Defensivo (Escudo)", "Ofensivo (Drone)", "Mágico (Orbe)", "Lâminas Orbitais"],
        "geometria": ["largura", "distancia", "quantidade_orbitais"],
        "mod_dano": 0.5,
        "mod_velocidade": 1.0,
        "alcance_base": 2.0,
        "cadencia_base_s": 1.2,
        "bloqueia_projeteis": True,
    },
    "Mágica": {
        "categoria": "Magic",
        "descricao": "Armas conjuradas/espectrais",
        "estilos": ["Espadas Espectrais", "Runas Flutuantes", "Tentáculos Sombrios", "Cristais Arcanos"],
        "geometria": ["quantidade", "tamanho", "distancia_max"],
        "mod_dano": 1.3,
        "mod_velocidade": 1.1,
        "alcance_base": 8.0,
        "cadencia_base_s": 1.6,
        "usa_mana": True,
        "escala_com_mana": True,
    },
    "Transformável": {
        "categoria": "Special",
        "descricao": "Muda de forma durante combate",
        "estilos": ["Espada↔Lança", "Compacta↔Estendida", "Chicote↔Espada", "Arco↔Lâminas"],
        "geometria": ["forma1_cabo", "forma1_lamina", "forma2_cabo", "forma2_lamina", "largura"],
        "mod_dano": 1.15,
        "mod_velocidade": 1.0,
        "alcance_base": 2.0,
        "cadencia_base_s": 1.2,
        "formas": 2,
    },
}

LISTA_TIPOS_ARMA = list(TIPOS_ARMA.keys())


def alcance_ranged_m(tipo_arma):
    """Fonte única (Onda 4) do alcance máximo absoluto, em metros, dos
    tipos de arma que atacam à distância. Retorna None para tipos melee —
    o alcance melee é geométrico (perfil de hitbox + comprimento da arma).

    Antes da Onda 4 havia três verdades divergentes: o motor disparava de
    20/12/8m hard-coded, a IA se posicionava por raio*range_mult (~8,5m
    para Arco) e a percepção estimava pelo tamanho do sprite. O arqueiro
    mirava ficar a ~5m podendo atirar de 20m.
    """
    dados = TIPOS_ARMA.get(tipo_arma) or {}
    if dados.get("categoria") not in ("Ranged", "Magic"):
        return None
    return float(dados["alcance_base"])


def cadencia_base_s(tipo_arma):
    """Cadência-base do golpe básico por tipo, em segundos (Onda 4).

    O cooldown real é ``cadencia / velocidade_ataque`` da arma (runtime
    0,81–1,56, raridade já composta em weapons.py) — o knob existia em
    100% das armas do catálogo e nunca tinha sido lido.
    """
    return float((TIPOS_ARMA.get(tipo_arma) or {}).get("cadencia_base_s", 1.0))


# ============================================================================
# SISTEMA DE ENCANTAMENTOS
# ============================================================================

ENCANTAMENTOS = {
    # === ELEMENTAIS ===
    "Chamas": {
        "elemento": "Fogo",
        "cor": (255, 100, 50),
        "efeito": "burn",
        "dano_bonus": 2,
        "duracao": 3.0,
        "descricao": "+2 dano de fogo, chance de queimar"
    },
    "Gelo": {
        "elemento": "Gelo",
        "cor": (100, 200, 255),
        "efeito": "slow",
        "dano_bonus": 1,
        "slow_percent": 25,
        "descricao": "+1 dano de gelo, chance de slow"
    },
    "Relâmpago": {
        "elemento": "Raio",
        "cor": (255, 255, 100),
        "efeito": "chain",
        "dano_bonus": 2,
        "chain_targets": 2,
        "descricao": "+2 dano de raio, pode atingir alvos próximos"
    },
    "Veneno": {
        "elemento": "Natureza",
        "cor": (100, 255, 100),
        "efeito": "poison",
        "dano_bonus": 1,
        "dot_dano": 1.5,
        "dot_duracao": 5.0,
        "descricao": "+1 dano, aplica veneno (1.5 dano/s por 5s)"
    },
    "Trevas": {
        "elemento": "Trevas",
        "cor": (100, 50, 150),
        "efeito": "lifesteal",
        "dano_bonus": 2,
        "lifesteal_percent": 8,
        "descricao": "+2 dano sombrio, 8% roubo de vida"
    },
    "Sagrado": {
        "elemento": "Luz",
        "cor": (255, 255, 200),
        "efeito": "holy",
        "dano_bonus": 3,
        "bonus_vs_trevas": 35,
        "descricao": "+3 dano sagrado, +35% vs inimigos sombrios"
    },
    # === UTILITÁRIOS ===
    "Velocidade": {
        "elemento": "Vento",
        "cor": (200, 255, 200),
        "efeito": "speed",
        "ataque_speed_bonus": 20,
        "descricao": "+20% velocidade de ataque"
    },
    "Vampirismo": {
        "elemento": "Sangue",
        "cor": (200, 50, 50),
        "efeito": "lifesteal",
        "lifesteal_percent": 15,
        "descricao": "15% do dano causado vira vida"
    },
    "Crítico": {
        "elemento": "Precisão",
        "cor": (255, 200, 50),
        "efeito": "crit",
        "crit_chance_bonus": 15,
        "crit_damage_bonus": 25,
        "descricao": "+15% chance crítico, +25% dano crítico"
    },
    "Penetração": {
        "elemento": "Força",
        "cor": (150, 150, 150),
        "efeito": "armor_pen",
        "armor_ignore": 30,
        "descricao": "Ignora 30% da defesa inimiga"
    },
    # === RAROS ===
    "Execução": {
        "elemento": "Morte",
        "cor": (50, 0, 0),
        "efeito": "execute",
        "execute_threshold": 20,
        "descricao": "Executa inimigos abaixo de 20% HP"
    },
    "Espelhamento": {
        "elemento": "Arcano",
        "cor": (200, 200, 255),
        "efeito": "reflect",
        "reflect_percent": 25,
        "descricao": "Reflete 25% do dano recebido"
    },
}

# Onda 6 (fase 2): mesma correcao de escala do mundo dos skills — os DoTs
# e bonus flat dos encantamentos (Veneno 1,5/s; Chamas +2) eram
# microscopicos contra pools 2,8x. Escala uma vez no import.
_ESCALA_DOT_ENCANTO = 2.0
for _enc in ENCANTAMENTOS.values():
    for _campo in ("dot_dano", "dano_bonus"):
        if _campo in _enc and isinstance(_enc[_campo], (int, float)):
            _enc[_campo] = _enc[_campo] * _ESCALA_DOT_ENCANTO

LISTA_ENCANTAMENTOS = list(ENCANTAMENTOS.keys())


# ============================================================================
# PASSIVAS DE ARMAS
# ============================================================================

PASSIVAS_ARMA = {
    "random_minor": [
        {"nome": "Afiada", "efeito": "crit_chance", "valor": 5, "descricao": "+5% chance crítico"},
        {"nome": "Leve", "efeito": "peso_reduzido", "valor": 15, "descricao": "-15% peso"},
        {"nome": "Equilibrada", "efeito": "velocidade", "valor": 10, "descricao": "+10% velocidade de ataque"},
        {"nome": "Resistente", "efeito": "durabilidade", "valor": 20, "descricao": "+20% durabilidade"},
        {"nome": "Vampírica", "efeito": "lifesteal", "valor": 5, "descricao": "5% roubo de vida"},
    ],
    "random_major": [
        {"nome": "Devastadora", "efeito": "dano_bonus", "valor": 15, "descricao": "+15% dano"},
        {"nome": "Veloz", "efeito": "velocidade", "valor": 25, "descricao": "+25% velocidade de ataque"},
        {"nome": "Sanguinária", "efeito": "lifesteal", "valor": 12, "descricao": "12% roubo de vida"},
        {"nome": "Precisa", "efeito": "crit_chance", "valor": 15, "descricao": "+15% chance crítico"},
        {"nome": "Brutal", "efeito": "crit_damage", "valor": 35, "descricao": "+35% dano crítico"},
    ],
    "unique": [
        {"nome": "Executora", "efeito": "execute", "valor": 15, "descricao": "Executa inimigos abaixo de 15% HP"},
        {"nome": "Imortal", "efeito": "sobreviver", "valor": 1, "descricao": "Uma vez por luta, sobrevive com 1 HP"},
        {"nome": "Berserker", "efeito": "berserk", "valor": 50, "descricao": "+50% dano quando abaixo de 30% HP"},
        {"nome": "Eco", "efeito": "double_hit", "valor": 20, "descricao": "20% chance de atacar duas vezes"},
        {"nome": "Infinita", "efeito": "no_mana_cost", "valor": 50, "descricao": "50% chance de skill sem custo de mana"},
    ],
    "mythic": [
        {"nome": "Divina", "efeito": "all_stats", "valor": 20, "descricao": "+20% em todos os atributos"},
        {"nome": "Apocalíptica", "efeito": "aoe_damage", "valor": 30, "descricao": "Ataques causam 30% do dano em área"},
        {"nome": "Temporal", "efeito": "cooldown", "valor": 40, "descricao": "-40% cooldown de habilidades"},
        {"nome": "Dimensional", "efeito": "teleport", "valor": 25, "descricao": "25% chance de teleportar atrás do inimigo"},
        {"nome": "Caótica", "efeito": "random_element", "valor": 100, "descricao": "Cada ataque tem elemento aleatório"},
    ],
}


# ============================================================================
# SISTEMA DE CLASSES
# ============================================================================

LISTA_CLASSES = [
    # === FÍSICOS ===
# Onda 6 (fase 3): knobs de classe — rodada 1 da varredura B1 medida no
# harness (piso 0,35 / teto 0,65): porao sobe (Feiticeiro/Piromante/Monge/
# Duelista/Necromante — poder bruto 0,63-0,83 num mundo onde Berserker tem
# 1,80), teto apara por vida/sustain (Cavaleiro 2,5->2,05; Druida; Paladino
# — o poço e a postura ja limitam por contrato). Centro intocado.
    "Guerreiro (Força Bruta)",
    "Berserker (Fúria)",
    "Gladiador (Combate)",
    "Cavaleiro (Defesa)",
    # === ÁGEIS ===
    "Assassino (Crítico)",
    "Ladino (Evasão)",
    "Ninja (Velocidade)",
    "Duelista (Precisão)",
    # === MÁGICOS ===
    "Mago (Arcano)",
    "Piromante (Fogo)",
    "Criomante (Gelo)",
    "Necromante (Trevas)",
    # === HÍBRIDOS ===
    "Paladino (Sagrado)",
    "Druida (Natureza)",
    "Feiticeiro (Caos)",
    "Monge (Chi)",
]

# Onda 10D: todo kit de classe segue a ordem KIT_PAPEIS — 1 CONTROLE (status/
# CC), 1 ZONA/TERRENO (campo, estrutura, invocacao), 1 MOBILIDADE (dash/buff de
# velocidade), 1 PICO (burst/finisher/sustain). Os kits antigos deixavam 70 das
# 108 skills fora do jogo (TRAP/CHANNEL/TRANSFORM/portal/cadeia nunca equipadas).
KIT_PAPEIS = ("CONTROLE", "ZONA", "MOBILIDADE", "PICO")

# Onda 11C: cada papel virou um POOL por classe — o personagem sorteia 1 opção
# por papel NA CRIAÇÃO e persiste ``kit_skills`` no registro (dois lutadores da
# mesma classe deixam de ser idênticos). A PRIMEIRA opção de cada papel é a
# skill do kit fixo da Onda 10 (``skills_afinidade``), o default de
# compatibilidade para registros antigos. Toda opção respeita a regra do papel
# (CONTROLE = efeito de CC/taunt/chain; ZONA = AREA/TRAP/SUMMON; MOBILIDADE =
# DASH/velocidade/voo; PICO = livre) — o contrato vive em
# tests/test_catalog_reachability.py.
KIT_POOLS = {
    "Guerreiro (Força Bruta)": {
        "CONTROLE": ["Impacto Sônico", "Mjolnir"],
        "ZONA": ["Terremoto", "Sacrifício"],
        "MOBILIDADE": ["Avanço Brutal"],
        "PICO": ["Golpe do Executor", "Determinação"],
    },
    "Berserker (Fúria)": {
        "CONTROLE": ["Impacto Sônico", "Mjolnir"],
        "ZONA": ["Explosão Nova", "Sacrifício", "Ritual Carmesim"],
        "MOBILIDADE": ["Avanço Brutal"],
        "PICO": [
            "Grito de Guerra", "Pacto de Sangue", "Estilhaço Vermelho",
            "Forma Sanguinária",
        ],
    },
    "Gladiador (Combate)": {
        "CONTROLE": ["Repulsão", "Impacto Sônico"],
        "ZONA": ["Fúria Giratória", "Terremoto"],
        "MOBILIDADE": ["Velocidade Arcana", "Avanço Brutal"],
        "PICO": ["Golpe do Executor", "Determinação"],
    },
    "Cavaleiro (Defesa)": {
        "CONTROLE": ["Provocar", "Impacto Sônico"],
        "ZONA": ["Terremoto", "Sacrifício"],
        "MOBILIDADE": ["Avanço Brutal"],
        "PICO": ["Reflexo Espelhado", "Barreira Divina", "Determinação"],
    },
    "Assassino (Crítico)": {
        "CONTROLE": ["Medo Profundo", "Fenda do Vazio"],
        "ZONA": ["Tentáculos do Vazio", "Colheita de Almas", "Cópia Sombria"],
        "MOBILIDADE": ["Portal Sombrio", "Passo do Vazio"],
        "PICO": ["Execução", "Esfera Sombria", "Maldição", "Lança do Vazio"],
    },
    "Ladino (Evasão)": {
        "CONTROLE": ["Esporos Alucinógenos"],
        "ZONA": ["Nuvem Tóxica"],
        "MOBILIDADE": ["Teleporte Relâmpago"],
        "PICO": [
            "Lâmina de Sangue", "Dardo Venenoso", "Espinhos", "Praga",
            "Bomba Relógio",
        ],
    },
    "Ninja (Velocidade)": {
        "CONTROLE": ["Corrente em Cadeia", "Relâmpago"],
        "ZONA": ["Campo Elétrico", "Tempestade", "Julgamento de Thor"],
        "MOBILIDADE": ["Teleporte Relâmpago"],
        "PICO": [
            "Forma Relâmpago", "Corrente Elétrica", "Sobrecarga",
            "Fúria do Trovão",
        ],
    },
    "Duelista (Precisão)": {
        "CONTROLE": ["Idade Acelerada"],
        "ZONA": ["Slow Motion"],
        "MOBILIDADE": ["Velocidade Arcana"],
        "PICO": ["Golpe do Executor", "Eco Temporal", "Previsão", "Reverter"],
    },
    "Mago (Arcano)": {
        "CONTROLE": ["Explosão Arcana"],
        "ZONA": ["Buraco Negro"],
        "MOBILIDADE": ["Portal Arcano"],
        "PICO": [
            "Desintegrar", "Mísseis Arcanos", "Escudo Arcano",
            "Amplificar Magia", "Contrafeitiço",
        ],
    },
    "Piromante (Fogo)": {
        "CONTROLE": ["Pilar de Fogo"],
        "ZONA": ["Inferno", "Muro Ardente"],
        "MOBILIDADE": ["Avanço Brutal"],
        "PICO": [
            "Fênix", "Combustão Espontânea", "Meteoro", "Bola de Fogo",
            "Lança de Fogo",
        ],
    },
    "Criomante (Gelo)": {
        "CONTROLE": ["Zero Absoluto", "Prisão de Gelo"],
        "ZONA": ["Muralha de Gelo", "Nevasca"],
        "MOBILIDADE": ["Velocidade Arcana"],
        "PICO": [
            "Shatter", "Morte Glacial", "Lança de Gelo", "Cone de Gelo",
            "Avatar de Gelo",
        ],
    },
    "Necromante (Trevas)": {
        "CONTROLE": ["Possessão"],
        "ZONA": ["Invocação: Espírito", "Explosão Necrótica", "Colheita de Almas"],
        "MOBILIDADE": ["Portal Sombrio"],
        "PICO": [
            "Necrose", "Esfera Sombria", "Maldição", "Último Suspiro",
            "Transfusão",
        ],
    },
    "Paladino (Sagrado)": {
        "CONTROLE": ["Raio Sagrado"],
        "ZONA": ["Julgamento Celestial"],
        "MOBILIDADE": ["Avanço Brutal"],
        "PICO": [
            "Smite", "Cura Maior", "Barreira Divina", "Anjo Guardião",
            "Ressurreição",
        ],
    },
    "Druida (Natureza)": {
        "CONTROLE": ["Raízes"],
        "ZONA": ["Ira da Floresta", "Barreira de Espinhos"],
        "MOBILIDADE": ["Levitar"],
        "PICO": [
            "Wrath of Nature", "Regeneração", "Dardo Venenoso", "Praga",
            "Espinhos",
        ],
    },
    "Feiticeiro (Caos)": {
        "CONTROLE": ["Parar o Tempo"],
        "ZONA": ["Explosão do Caos", "Apocalipse"],
        "MOBILIDADE": ["Troca de Almas"],
        "PICO": [
            "Roleta Russa", "Chama Caótica", "Instabilidade", "Mutação",
            "Eco Temporal",
        ],
    },
    "Monge (Chi)": {
        "CONTROLE": ["Pulso Gravitacional", "Colapso"],
        "ZONA": ["Campo de Gravidade"],
        "MOBILIDADE": ["Acelerar"],
        "PICO": ["Fotossíntese", "Link de Vida"],
    },
}

# Skills do catálogo conscientemente SEM slot de kit nesta onda (nenhum pool
# as sorteia; seguem cobertas pela checagem 1-a-1 e disponíveis para armas).
# Candidatas naturais aos pools de ondas futuras.
SKILLS_FORA_DE_ROTACAO = frozenset({
    "Benção",            # Cura Maior ocupa o slot de sustain do Paladino
    "Chamas do Dragão",  # canal de fogo; Piromante já tem 5 picos
    "Conjuração Perfeita",
    "Cura Menor",        # substituída pela Cura Maior
    "Disparo de Mana",
    "Escudo de Brasas",
    "Estilhaço de Gelo",  # Cone de Gelo cobre o nicho no pool do Criomante
    "Purificar",
    "Roubar Magia",
})


def sortear_kit(classe, rng=None):
    """Sorteia 1 skill por papel do ``KIT_POOLS`` da classe (Onda 11C).

    Usado na CRIAÇÃO do personagem (gerador, UI, roleta) — nunca por luta:
    o kit sorteado persiste em ``kit_skills`` no registro para que ficha,
    vídeo e harness vejam o mesmo lutador.
    """
    import random as _random

    sorteador = rng if rng is not None else _random
    pools = KIT_POOLS.get(classe)
    if not pools:
        dados = CLASSES_DATA.get(classe, {})
        return list(dados.get("skills_afinidade", []))
    return [sorteador.choice(pools[papel]) for papel in KIT_PAPEIS]

# Onda 10B: velocidade_base_ms (m/s), mod_cadencia (multiplica o cooldown do
# golpe basico; 1,0 = neutro) e vel_giro (velocidade de giro do olhar, 1/s)
# sao a identidade de movimento de cada classe. mod_velocidade fica so como
# rotulo legado da UI (view_chars) — o runtime nao o le mais.
CLASSES_DATA = {
    # === FÍSICOS ===
    "Guerreiro (Força Bruta)": {
        "descricao": "Mestre do combate corpo-a-corpo tradicional",
        "passiva": "Golpes físicos causam 10% mais dano",
        "mod_forca": 0.85,
        "mod_mana": 0.6,
        "mod_vida": 1.8,
        "mod_velocidade": 1.0,
        "velocidade_base_ms": 7.0,
        "mod_cadencia": 1.0,
        "vel_giro": 10.0,
        "regen_mana": 2.0,
        "skills_afinidade": ["Impacto Sônico", "Terremoto", "Avanço Brutal", "Golpe do Executor"],
        "cor_aura": (200, 150, 100),
    },
    "Berserker (Fúria)": {
        "descricao": "Quanto mais ferido, mais perigoso",
        "passiva": "Dano aumenta conforme perde vida (até +30%)",
        "mod_forca": 0.9,
        "mod_mana": 0.4,
        "mod_vida": 2.0,
        "mod_velocidade": 1.1,
        "velocidade_base_ms": 7.5,
        "mod_cadencia": 0.95,
        "vel_giro": 12.0,
        "regen_mana": 1.5,
        "skills_afinidade": ["Impacto Sônico", "Explosão Nova", "Avanço Brutal", "Grito de Guerra"],
        "cor_aura": (255, 50, 50),
    },
    "Gladiador (Combate)": {
        "descricao": "Especialista em duelos prolongados",
        "passiva": "Regenera estamina 30% mais rápido",
        "mod_forca": 0.8,
        "mod_mana": 0.7,
        "mod_vida": 1.9,
        "mod_velocidade": 1.05,
        "velocidade_base_ms": 7.5,
        "mod_cadencia": 1.0,
        "vel_giro": 12.0,
        "regen_mana": 2.5,
        "skills_afinidade": ["Repulsão", "Fúria Giratória", "Velocidade Arcana", "Golpe do Executor"],
        "cor_aura": (180, 130, 80),
    },
    "Cavaleiro (Defesa)": {
        "descricao": "Tanque impenetrável com escudo",
        "passiva": "Recebe 30% menos dano",
        "mod_forca": 0.7,
        "mod_mana": 0.8,
        "mod_vida": 1.65,
        "mod_velocidade": 0.85,
        "velocidade_base_ms": 5.0,
        "mod_cadencia": 1.2,
        "vel_giro": 8.0,
        "regen_mana": 3.0,
        "skills_afinidade": ["Provocar", "Terremoto", "Avanço Brutal", "Reflexo Espelhado"],
        "cor_aura": (150, 150, 200),
    },
    # === ÁGEIS ===
    "Assassino (Crítico)": {
        "descricao": "Mestre dos golpes fatais",
        "passiva": "20% chance de crítico (1.5x dano)",
        "mod_forca": 0.75,
        "mod_mana": 0.8,
        "mod_vida": 1.4,
        "mod_velocidade": 1.3,
        "velocidade_base_ms": 10.0,
        "mod_cadencia": 0.75,
        "vel_giro": 20.0,
        "regen_mana": 3.0,
        "skills_afinidade": ["Medo Profundo", "Tentáculos do Vazio", "Portal Sombrio", "Execução"],
        "cor_aura": (100, 0, 100),
    },
    "Ladino (Evasão)": {
        "descricao": "Impossível de acertar",
        "passiva": "20% chance de esquivar ataques",
        "mod_forca": 0.7,
        "mod_mana": 0.9,
        "mod_vida": 1.5,
        "mod_velocidade": 1.25,
        "velocidade_base_ms": 9.5,
        "mod_cadencia": 0.9,
        "vel_giro": 18.0,
        "regen_mana": 3.5,
        "skills_afinidade": ["Esporos Alucinógenos", "Nuvem Tóxica", "Teleporte Relâmpago", "Lâmina de Sangue"],
        "cor_aura": (80, 80, 80),
    },
    "Ninja (Velocidade)": {
        "descricao": "Velocidade sobre-humana",
        "passiva": "Move 30% mais rápido, ataca 15% mais rápido",
        "mod_forca": 0.65,
        "mod_mana": 0.9,
        "mod_vida": 1.3,
        "mod_velocidade": 1.4,
        "velocidade_base_ms": 11.0,
        "mod_cadencia": 0.7,
        "vel_giro": 20.0,
        "regen_mana": 4.0,
        "skills_afinidade": ["Corrente em Cadeia", "Campo Elétrico", "Teleporte Relâmpago", "Forma Relâmpago"],
        "cor_aura": (50, 50, 50),
    },
    "Duelista (Precisão)": {
        "descricao": "Cada golpe conta",
        "passiva": "Ataques nunca erram, +10% dano em 1v1",
        "mod_forca": 0.9,
        "mod_mana": 0.85,
        "mod_vida": 1.6,
        "mod_velocidade": 1.15,
        "velocidade_base_ms": 8.0,
        "mod_cadencia": 0.9,
        "vel_giro": 14.0,
        "regen_mana": 3.0,
        "skills_afinidade": ["Idade Acelerada", "Slow Motion", "Velocidade Arcana", "Golpe do Executor"],
        "cor_aura": (255, 215, 0),
    },
    # === MÁGICOS ===
    "Mago (Arcano)": {
        "descricao": "Mestre de todas as magias",
        "passiva": "Magias custam 20% menos mana",
        "mod_forca": 0.5,
        "mod_mana": 1.5,
        "mod_vida": 1.3,
        "mod_velocidade": 0.9,
        "velocidade_base_ms": 6.0,
        "mod_cadencia": 1.0,
        "vel_giro": 10.0,
        "regen_mana": 8.0,
        "skills_afinidade": ["Explosão Arcana", "Buraco Negro", "Portal Arcano", "Desintegrar"],
        "cor_aura": (100, 150, 255),
    },
    "Piromante (Fogo)": {
        "descricao": "Destruição pelo fogo",
        "passiva": "Magias de fogo causam 15% mais dano",
        "mod_forca": 0.9,
        "mod_mana": 1.4,
        "mod_vida": 1.6,
        "mod_velocidade": 0.95,
        "velocidade_base_ms": 6.5,
        "mod_cadencia": 1.0,
        "vel_giro": 10.0,
        "regen_mana": 6.0,
        "skills_afinidade": ["Pilar de Fogo", "Inferno", "Avanço Brutal", "Fênix"],
        "cor_aura": (255, 100, 0),
    },
    "Criomante (Gelo)": {
        "descricao": "Controle através do frio",
        "passiva": "Magias de gelo sempre aplicam slow",
        "mod_forca": 0.5,
        "mod_mana": 1.35,
        "mod_vida": 1.4,
        "mod_velocidade": 0.9,
        "velocidade_base_ms": 6.0,
        "mod_cadencia": 1.05,
        "vel_giro": 10.0,
        "regen_mana": 6.5,
        "skills_afinidade": ["Zero Absoluto", "Muralha de Gelo", "Velocidade Arcana", "Shatter"],
        "cor_aura": (150, 220, 255),
    },
    "Necromante (Trevas)": {
        "descricao": "Poder sobre vida e morte",
        "passiva": "Drena 10% do dano causado como vida",
        "mod_forca": 0.65,
        "mod_mana": 1.4,
        "mod_vida": 1.5,
        "mod_velocidade": 0.85,
        "velocidade_base_ms": 5.5,
        "mod_cadencia": 1.05,
        "vel_giro": 10.0,
        "regen_mana": 5.0,
        "skills_afinidade": ["Possessão", "Invocação: Espírito", "Portal Sombrio", "Necrose"],
        "cor_aura": (80, 0, 120),
    },
    # === HÍBRIDOS ===
    "Paladino (Sagrado)": {
        "descricao": "Guerreiro sagrado equilibrado",
        "passiva": "Cura 1% da vida máxima por segundo",
        "mod_forca": 0.7,
        "mod_mana": 1.0,
        "mod_vida": 1.65,
        "mod_velocidade": 0.95,
        "velocidade_base_ms": 6.0,
        "mod_cadencia": 1.0,
        "vel_giro": 10.0,
        "regen_mana": 4.0,
        "skills_afinidade": ["Raio Sagrado", "Julgamento Celestial", "Avanço Brutal", "Smite"],
        "cor_aura": (255, 215, 100),
    },
    "Druida (Natureza)": {
        "descricao": "Poder da natureza selvagem",
        "passiva": "Venenos duram 50% mais",
        "mod_forca": 0.65,
        "mod_mana": 1.2,
        "mod_vida": 1.45,
        "mod_velocidade": 1.0,
        "velocidade_base_ms": 6.5,
        "mod_cadencia": 1.0,
        "vel_giro": 10.0,
        "regen_mana": 4.5,
        "skills_afinidade": ["Raízes", "Ira da Floresta", "Levitar", "Wrath of Nature"],
        "cor_aura": (100, 200, 50),
    },
    "Feiticeiro (Caos)": {
        "descricao": "Magia imprevisível e poderosa",
        "passiva": "Magias têm 15% chance de lançar duas vezes",
        "mod_forca": 0.9,
        "mod_mana": 1.6,
        "mod_vida": 1.6,
        "mod_velocidade": 0.95,
        "velocidade_base_ms": 6.5,
        "mod_cadencia": 1.0,
        "vel_giro": 10.0,
        "regen_mana": 7.0,
        "skills_afinidade": ["Parar o Tempo", "Explosão do Caos", "Troca de Almas", "Roleta Russa"],
        "cor_aura": (200, 50, 200),
    },
    "Monge (Chi)": {
        "descricao": "Artes marciais místicas",
        "passiva": "Ataques desarmados causam dano mágico",
        "mod_forca": 0.85,
        "mod_mana": 1.1,
        "mod_vida": 1.75,
        "mod_velocidade": 1.2,
        "velocidade_base_ms": 9.5,
        "mod_cadencia": 0.8,
        "vel_giro": 16.0,
        "regen_mana": 6.0,
        "skills_afinidade": ["Pulso Gravitacional", "Campo de Gravidade", "Acelerar", "Fotossíntese"],
        "cor_aura": (255, 255, 200),
    },
}


# ============================================================================
# FUNÇÕES HELPERS
# ============================================================================

def get_raridade_data(raridade):
    """Retorna os dados de uma raridade"""
    return RARIDADES.get(raridade, RARIDADES["Comum"])


def get_tipo_arma_data(tipo):
    """Retorna os dados de um tipo de arma"""
    return TIPOS_ARMA.get(tipo, TIPOS_ARMA["Reta"])


def get_class_data(nome_classe):
    """Retorna os dados de uma classe"""
    return CLASSES_DATA.get(nome_classe, CLASSES_DATA["Guerreiro (Força Bruta)"])
