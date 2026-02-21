"""
=============================================================================
NEURAL FIGHTS - Sistema de Skills v2.0 COLOSSAL EDITION
=============================================================================
Catálogo expandido de habilidades com:
- 100+ Skills únicas
- 12 Elementos diferentes
- Condições de ativação
- Magias carregáveis e canalizáveis
- Combos e sinergias
=============================================================================
"""

from utils.config import PPM

# ============================================================================
# CATÁLOGO MASTER DE HABILIDADES v2.0
# ============================================================================
# Tipos: PROJETIL, BUFF, AREA, DASH, SUMMON, BEAM, CHANNEL, TRAP, TRANSFORM
# Efeitos: Ver magic_system.py para lista completa de status effects
# Elementos: FOGO, GELO, RAIO, TREVAS, LUZ, NATUREZA, ARCANO, CAOS, VOID, 
#            SANGUE, TEMPO, GRAVITACAO
# ============================================================================

SKILL_DB = {
    "Nenhuma": {
        "custo": 0, "cooldown": 0, "tipo": "NADA"
    },
    
    # =========================================================================
    # 🔥 FOGO - Dano alto, queimaduras, explosões
    # =========================================================================
    "Bola de Fogo": {
        "tipo": "PROJETIL", "dano": 35.0, "velocidade": 11.0, "raio": 0.5,
        "vida": 2.0, "cor": (255, 100, 0), "custo": 25.0, "cooldown": 5.0,
        "efeito": "EXPLOSAO", "elemento": "FOGO",
        "descricao": "Esfera flamejante que explode no impacto"
    },
    "Meteoro": {
        "tipo": "PROJETIL", "dano": 60.0, "velocidade": 8.0, "raio": 0.8,
        "vida": 2.5, "cor": (255, 50, 0), "custo": 40.0, "cooldown": 10.0,
        "efeito": "EXPLOSAO", "elemento": "FOGO", "raio_explosao": 2.0,
        "descricao": "Rocha incandescente devastadora"
    },
    "Lança de Fogo": {
        "tipo": "PROJETIL", "dano": 20.0, "velocidade": 25.0, "raio": 0.25,
        "vida": 1.0, "cor": (255, 150, 50), "custo": 12.0, "cooldown": 2.5,
        "efeito": "QUEIMANDO", "elemento": "FOGO",
        "descricao": "Projétil rápido que causa queimadura"
    },
    "Explosão Nova": {
        "tipo": "AREA", "dano": 45.0, "raio_area": 3.0, "cor": (255, 200, 50),
        "custo": 35.0, "cooldown": 12.0, "efeito": "EMPURRAO", "elemento": "FOGO",
        "descricao": "Explosão ao redor do conjurador"
    },
    "Inferno": {
        "tipo": "AREA", "dano": 15.0, "raio_area": 4.0, "cor": (255, 80, 0),
        "custo": 45.0, "cooldown": 15.0, "efeito": "QUEIMANDO", "elemento": "FOGO",
        "duracao": 5.0, "dano_tick": 10.0,
        "descricao": "Campo de fogo persistente"
    },
    "Chamas do Dragão": {
        "tipo": "BEAM", "dano": 12.0, "alcance": 6.0, "cor": (255, 120, 0),
        "custo": 30.0, "cooldown": 8.0, "efeito": "QUEIMANDO", "elemento": "FOGO",
        "canalizavel": True, "dano_por_segundo": 40.0, "duracao_max": 3.0,
        "descricao": "Sopro de fogo contínuo"
    },
    "Pilar de Fogo": {
        "tipo": "AREA", "dano": 50.0, "raio_area": 1.5, "cor": (255, 150, 0),
        "custo": 28.0, "cooldown": 7.0, "efeito": "KNOCK_UP", "elemento": "FOGO",
        "delay": 0.8, "duracao": 1.0, "descricao": "Pilar de fogo que lança inimigos"
    },
    "Fênix": {
        "tipo": "SUMMON", "dano": 25.0, "cor": (255, 180, 50), 
        "custo": 60.0, "cooldown": 30.0, "elemento": "FOGO",
        "duracao": 15.0, "summon_vida": 80.0, "summon_dano": 15.0,
        "descricao": "Invoca uma fênix que ataca e revive uma vez"
    },
    "Combustão Espontânea": {
        "tipo": "PROJETIL", "dano": 80.0, "velocidade": 0, "raio": 0.3,
        "vida": 0.1, "cor": (255, 50, 50), "custo": 50.0, "cooldown": 20.0,
        "efeito": "EXPLOSAO", "elemento": "FOGO",
        "condicao": "ALVO_QUEIMANDO", "dano_bonus_condicao": 2.0,
        "descricao": "Detona queimaduras no alvo - dano massivo se queimando"
    },
    "Escudo de Brasas": {
        "tipo": "BUFF", "cor": (255, 100, 50), "custo": 25.0, "cooldown": 15.0,
        "duracao": 8.0, "elemento": "FOGO",
        "dano_contato": 10.0, "escudo": 25.0,
        "descricao": "Escudo que queima quem ataca corpo a corpo"
    },
    
    # =========================================================================
    # ❄️ GELO - Controle, slow, shatter
    # =========================================================================
    "Estilhaço de Gelo": {
        "tipo": "PROJETIL", "dano": 15.0, "velocidade": 18.0, "raio": 0.3,
        "vida": 1.8, "cor": (150, 220, 255), "custo": 10.0, "cooldown": 2.0,
        "efeito": "LENTO", "elemento": "GELO",
        "descricao": "Fragmento gélido que desacelera"
    },
    "Lança de Gelo": {
        "tipo": "PROJETIL", "dano": 28.0, "velocidade": 22.0, "raio": 0.35,
        "vida": 1.5, "cor": (100, 200, 255), "custo": 18.0, "cooldown": 4.0,
        "efeito": "PERFURAR", "elemento": "GELO", "perfura": True,
        "descricao": "Lança perfurante de gelo puro"
    },
    "Nevasca": {
        "tipo": "AREA", "dano": 8.0, "raio_area": 4.0, "cor": (200, 230, 255),
        "custo": 30.0, "cooldown": 15.0, "efeito": "LENTO", "elemento": "GELO",
        "duracao": 3.0, "slow_fator": 0.4,
        "descricao": "Área de gelo que causa slow contínuo"
    },
    "Prisão de Gelo": {
        "tipo": "PROJETIL", "dano": 5.0, "velocidade": 15.0, "raio": 0.4,
        "vida": 2.0, "cor": (180, 240, 255), "custo": 22.0, "cooldown": 8.0,
        "efeito": "CONGELADO", "elemento": "GELO",
        "descricao": "Aprisiona o alvo em gelo"
    },
    "Cone de Gelo": {
        "tipo": "PROJETIL", "dano": 20.0, "velocidade": 20.0, "raio": 0.5,
        "vida": 0.5, "cor": (150, 220, 255), "custo": 15.0, "cooldown": 4.0,
        "efeito": "LENTO", "elemento": "GELO", "cone": True, "angulo_cone": 60,
        "descricao": "Cone de gelo que atinge múltiplos alvos"
    },
    "Muralha de Gelo": {
        "tipo": "TRAP", "dano": 0.0, "cor": (180, 220, 255),
        "custo": 20.0, "cooldown": 12.0, "elemento": "GELO",
        "duracao": 6.0, "bloqueia_movimento": True, "vida_estrutura": 100.0,
        "descricao": "Cria uma parede de gelo bloqueadora"
    },
    "Shatter": {
        "tipo": "AREA", "dano": 60.0, "raio_area": 2.5, "cor": (200, 240, 255),
        "custo": 25.0, "cooldown": 10.0, "efeito": "VULNERAVEL", "elemento": "GELO",
        "condicao": "ALVO_CONGELADO", "remove_congelamento": True,
        "descricao": "Estilhaça alvos congelados - dano massivo"
    },
    "Zero Absoluto": {
        "tipo": "AREA", "dano": 30.0, "raio_area": 3.5, "cor": (220, 240, 255),
        "custo": 55.0, "cooldown": 25.0, "efeito": "CONGELADO", "elemento": "GELO",
        "duracao_stun": 3.0,
        "descricao": "Congela todos em grande área"
    },
    "Avatar de Gelo": {
        "tipo": "TRANSFORM", "cor": (150, 200, 255), "custo": 50.0, "cooldown": 45.0,
        "duracao": 12.0, "elemento": "GELO",
        "bonus_resistencia": 0.5, "aura_slow": 0.6, "aura_raio": 3.0,
        "descricao": "Transforma em elemental de gelo - aura de slow"
    },
    "Morte Glacial": {
        "tipo": "PROJETIL", "dano": 150.0, "velocidade": 10.0, "raio": 0.5,
        "vida": 2.0, "cor": (200, 230, 255), "custo": 70.0, "cooldown": 40.0,
        "efeito": "CONGELADO", "elemento": "GELO",
        "condicao": "ALVO_BAIXA_VIDA", "executa": True,
        "descricao": "Executa alvos com pouca vida - congela o cadáver"
    },
    
    # =========================================================================
    # ⚡ RAIO - Velocidade, chain, stun
    # =========================================================================
    "Relâmpago": {
        "tipo": "BEAM", "dano": 22.0, "alcance": 8.0, "cor": (255, 255, 100),
        "custo": 15.0, "cooldown": 3.0, "efeito": "PARALISIA", "elemento": "RAIO",
        "descricao": "Raio instantâneo que paralisa"
    },
    "Corrente Elétrica": {
        "tipo": "PROJETIL", "dano": 12.0, "velocidade": 30.0, "raio": 0.2,
        "vida": 0.8, "cor": (255, 255, 150), "custo": 8.0, "cooldown": 1.0,
        "efeito": "NORMAL", "elemento": "RAIO",
        "descricao": "Disparo elétrico ultra-rápido"
    },
    "Tempestade": {
        "tipo": "AREA", "dano": 40.0, "raio_area": 5.0, "cor": (200, 200, 255),
        "custo": 45.0, "cooldown": 18.0, "efeito": "PARALISIA", "elemento": "RAIO",
        "descricao": "Devastação elétrica em grande área"
    },
    "Teleporte Relâmpago": {
        "tipo": "DASH", "distancia": 5.0, "cor": (255, 255, 200),
        "custo": 20.0, "cooldown": 6.0, "efeito": "NORMAL", "elemento": "RAIO",
        "invencivel": True, "dano_chegada": 15.0,
        "descricao": "Teleporta instantaneamente, causa dano na chegada"
    },
    "Corrente em Cadeia": {
        "tipo": "BEAM", "dano": 18.0, "alcance": 10.0, "cor": (255, 255, 120),
        "custo": 25.0, "cooldown": 8.0, "efeito": "PARALISIA", "elemento": "RAIO",
        "chain": 4, "chain_decay": 0.8,
        "descricao": "Raio que salta entre até 4 alvos"
    },
    "Sobrecarga": {
        "tipo": "BUFF", "cor": (255, 255, 100), "custo": 20.0, "cooldown": 15.0,
        "duracao": 6.0, "elemento": "RAIO",
        "bonus_velocidade_ataque": 1.5, "bonus_velocidade_movimento": 1.3,
        "dano_recebido_bonus": 1.2,
        "descricao": "Acelera drasticamente mas recebe mais dano"
    },
    "Campo Elétrico": {
        "tipo": "AREA", "dano": 5.0, "raio_area": 3.0, "cor": (200, 200, 255),
        "custo": 30.0, "cooldown": 12.0, "efeito": "PARALISIA", "elemento": "RAIO",
        "duracao": 4.0, "chance_stun": 0.3,
        "descricao": "Campo que causa stun aleatório"
    },
    "Mjolnir": {
        "tipo": "PROJETIL", "dano": 70.0, "velocidade": 15.0, "raio": 0.6,
        "vida": 2.0, "cor": (255, 255, 150), "custo": 45.0, "cooldown": 15.0,
        "efeito": "KNOCK_UP", "elemento": "RAIO", "retorna": True,
        "descricao": "Martelo de raio que retorna"
    },
    "Julgamento de Thor": {
        "tipo": "AREA", "dano": 100.0, "raio_area": 2.0, "cor": (255, 255, 200),
        "custo": 60.0, "cooldown": 30.0, "efeito": "PARALISIA", "elemento": "RAIO",
        "delay": 1.5, "aviso_visual": True,
        "descricao": "Raio massivo do céu após 1.5s"
    },
    "Forma Relâmpago": {
        "tipo": "TRANSFORM", "cor": (255, 255, 150), "custo": 45.0, "cooldown": 40.0,
        "duracao": 8.0, "elemento": "RAIO",
        "bonus_velocidade": 2.0, "intangivel": True, "dano_contato": 20.0,
        "descricao": "Transforma em raio puro - atravessa inimigos"
    },
    
    # =========================================================================
    # 🌑 TREVAS - Drain, fear, debuffs
    # =========================================================================
    "Esfera Sombria": {
        "tipo": "PROJETIL", "dano": 18.0, "velocidade": 12.0, "raio": 0.45,
        "vida": 2.5, "cor": (80, 0, 120), "custo": 14.0, "cooldown": 3.0,
        "efeito": "DRENAR", "elemento": "TREVAS", "lifesteal": 0.3,
        "descricao": "Drena vida do alvo"
    },
    "Lâmina de Sangue": {
        "tipo": "PROJETIL", "dano": 25.0, "velocidade": 16.0, "raio": 0.4,
        "vida": 0.6, "cor": (180, 0, 30), "custo": 15.0, "cooldown": 4.5,
        "efeito": "SANGRANDO", "elemento": "SANGUE",
        "descricao": "Corte que causa sangramento"
    },
    "Maldição": {
        "tipo": "PROJETIL", "dano": 8.0, "velocidade": 10.0, "raio": 0.5,
        "vida": 3.0, "cor": (100, 0, 100), "custo": 20.0, "cooldown": 10.0,
        "efeito": "MALDITO", "elemento": "TREVAS",
        "descricao": "Maldição que enfraquece e causa DoT"
    },
    "Explosão Necrótica": {
        "tipo": "AREA", "dano": 30.0, "raio_area": 2.5, "cor": (60, 0, 80),
        "custo": 28.0, "cooldown": 9.0, "efeito": "DRENAR", "elemento": "TREVAS",
        "lifesteal": 0.25,
        "descricao": "Explosão que drena vida de todos ao redor"
    },
    "Medo Profundo": {
        "tipo": "AREA", "dano": 0.0, "raio_area": 4.0, "cor": (50, 0, 80),
        "custo": 22.0, "cooldown": 12.0, "efeito": "MEDO", "elemento": "TREVAS",
        "duracao_fear": 2.5,
        "descricao": "Causa medo em todos próximos"
    },
    "Tentáculos do Vazio": {
        "tipo": "AREA", "dano": 15.0, "raio_area": 3.0, "cor": (30, 0, 50),
        "custo": 30.0, "cooldown": 10.0, "efeito": "ENRAIZADO", "elemento": "VOID",
        "duracao": 3.0, "dano_tick": 8.0,
        "descricao": "Tentáculos que prendem e causam dano"
    },
    "Portal Sombrio": {
        "tipo": "DASH", "distancia": 8.0, "cor": (60, 0, 100),
        "custo": 25.0, "cooldown": 10.0, "elemento": "TREVAS",
        "invisivel_durante": True, "delay_saida": 0.5,
        "descricao": "Teleporta através das sombras, invisível durante"
    },
    "Pacto de Sangue": {
        "tipo": "BUFF", "cor": (150, 0, 50), "custo": 0, "cooldown": 30.0,
        "custo_vida": 30.0, "elemento": "SANGUE",
        "duracao": 10.0, "bonus_dano": 1.8, "lifesteal": 0.2,
        "descricao": "Sacrifica HP por poder - lifesteal e dano"
    },
    "Necrose": {
        "tipo": "PROJETIL", "dano": 20.0, "velocidade": 8.0, "raio": 0.5,
        "vida": 3.0, "cor": (30, 30, 30), "custo": 35.0, "cooldown": 15.0,
        "efeito": "NECROSE", "elemento": "TREVAS",
        "descricao": "Causa necrose - sem cura possível"
    },
    "Possessão": {
        "tipo": "PROJETIL", "dano": 0.0, "velocidade": 12.0, "raio": 0.4,
        "vida": 2.0, "cor": (100, 0, 100), "custo": 50.0, "cooldown": 35.0,
        "efeito": "POSSESSO", "elemento": "TREVAS",
        "duracao_controle": 3.0,
        "descricao": "Controla a mente do inimigo brevemente"
    },
    "Colheita de Almas": {
        "tipo": "AREA", "dano": 50.0, "raio_area": 5.0, "cor": (80, 0, 100),
        "custo": 60.0, "cooldown": 45.0, "efeito": "DRENAR", "elemento": "TREVAS",
        "cura_por_morte": 50.0,
        "descricao": "Dano em área - cura massiva se matar"
    },
    
    # =========================================================================
    # ✨ LUZ - Cura, purify, dano a mortos-vivos
    # =========================================================================
    "Raio Sagrado": {
        "tipo": "BEAM", "dano": 25.0, "alcance": 10.0, "cor": (255, 255, 220),
        "custo": 18.0, "cooldown": 5.0, "efeito": "CEGO", "elemento": "LUZ",
        "bonus_vs_trevas": 2.0,
        "descricao": "Raio de luz que cega"
    },
    "Cura Menor": {
        "tipo": "BUFF", "cor": (100, 255, 150), "custo": 25.0, "cooldown": 15.0,
        "cura": 25.0, "elemento": "LUZ",
        "descricao": "Recupera vida instantaneamente"
    },
    "Cura Maior": {
        "tipo": "BUFF", "cor": (150, 255, 200), "custo": 45.0, "cooldown": 25.0,
        "cura": 60.0, "remove_debuffs": 2, "elemento": "LUZ",
        "descricao": "Cura massiva + remove 2 debuffs"
    },
    "Benção": {
        "tipo": "BUFF", "cor": (255, 255, 200), "custo": 20.0, "cooldown": 20.0,
        "duracao": 10.0, "elemento": "LUZ",
        "efeito_buff": "ABENÇOADO",
        "descricao": "Bênção que aumenta cura e regenera"
    },
    "Purificar": {
        "tipo": "BUFF", "cor": (255, 255, 255), "custo": 30.0, "cooldown": 12.0,
        "elemento": "LUZ", "remove_todos_debuffs": True, "imune_debuffs": 3.0,
        "descricao": "Remove TODOS debuffs + imunidade"
    },
    "Barreira Divina": {
        "tipo": "BUFF", "cor": (255, 255, 180), "custo": 35.0, "cooldown": 18.0,
        "duracao": 5.0, "elemento": "LUZ",
        "escudo": 50.0, "reflete_dano": 0.3,
        "descricao": "Escudo que reflete 30% do dano"
    },
    "Smite": {
        "tipo": "PROJETIL", "dano": 40.0, "velocidade": 25.0, "raio": 0.3,
        "vida": 1.0, "cor": (255, 255, 150), "custo": 22.0, "cooldown": 6.0,
        "efeito": "EXPOSTO", "elemento": "LUZ",
        "bonus_vs_trevas": 1.5,
        "descricao": "Castigo divino - extra contra trevas"
    },
    "Anjo Guardião": {
        "tipo": "BUFF", "cor": (255, 255, 220), "custo": 60.0, "cooldown": 60.0,
        "duracao": 15.0, "elemento": "LUZ",
        "efeito_buff": "IMORTAL", "duracao_imortal": 3.0,
        "descricao": "Previne morte uma vez (HP mínimo 1)"
    },
    "Julgamento Celestial": {
        "tipo": "AREA", "dano": 80.0, "raio_area": 3.0, "cor": (255, 255, 200),
        "custo": 55.0, "cooldown": 30.0, "efeito": "CEGO", "elemento": "LUZ",
        "delay": 2.0, "pilares": 5,
        "descricao": "5 pilares de luz caem do céu"
    },
    "Ressurreição": {
        "tipo": "BUFF", "cor": (255, 255, 255), "custo": 80.0, "cooldown": 120.0,
        "elemento": "LUZ", "revive_hp_percent": 0.3,
        "descricao": "Revive aliado com 30% HP (ou self se morrer)"
    },
    
    # =========================================================================
    # 💚 NATUREZA - Veneno, heal, controle
    # =========================================================================
    "Dardo Venenoso": {
        "tipo": "PROJETIL", "dano": 5.0, "velocidade": 22.0, "raio": 0.15,
        "vida": 1.5, "cor": (100, 255, 100), "custo": 10.0, "cooldown": 2.0,
        "efeito": "ENVENENADO", "elemento": "NATUREZA",
        "descricao": "Dardo rápido com veneno potente"
    },
    "Nuvem Tóxica": {
        "tipo": "AREA", "dano": 5.0, "raio_area": 3.5, "cor": (150, 200, 50),
        "custo": 25.0, "cooldown": 12.0, "efeito": "ENVENENADO", "elemento": "NATUREZA",
        "duracao": 4.0, "stacks_por_segundo": 1,
        "descricao": "Nuvem persistente de veneno"
    },
    "Espinhos": {
        "tipo": "PROJETIL", "dano": 12.0, "velocidade": 20.0, "raio": 0.2,
        "vida": 1.2, "cor": (80, 150, 50), "custo": 8.0, "cooldown": 1.5,
        "efeito": "SANGRANDO", "elemento": "NATUREZA", "multi_shot": 3,
        "descricao": "Dispara 3 espinhos em leque"
    },
    "Raízes": {
        "tipo": "AREA", "dano": 0.0, "raio_area": 2.0, "cor": (100, 80, 50),
        "custo": 18.0, "cooldown": 8.0, "efeito": "ENRAIZADO", "elemento": "NATUREZA",
        "duracao": 2.5,
        "descricao": "Prende inimigos no lugar"
    },
    "Regeneração": {
        "tipo": "BUFF", "cor": (100, 255, 100), "custo": 20.0, "cooldown": 15.0,
        "duracao": 8.0, "elemento": "NATUREZA",
        "efeito_buff": "REGENERANDO", "cura_tick": 8.0,
        "descricao": "Regenera vida ao longo do tempo"
    },
    "Ira da Floresta": {
        "tipo": "SUMMON", "dano": 15.0, "cor": (80, 150, 50),
        "custo": 40.0, "cooldown": 25.0, "elemento": "NATUREZA",
        "duracao": 12.0, "summon_vida": 100.0, "summon_dano": 12.0,
        "summon_tipo": "TREANT",
        "descricao": "Invoca um treant protetor"
    },
    "Praga": {
        "tipo": "PROJETIL", "dano": 10.0, "velocidade": 8.0, "raio": 0.6,
        "vida": 4.0, "cor": (80, 100, 30), "custo": 35.0, "cooldown": 18.0,
        "efeito": "ENVENENADO", "elemento": "NATUREZA",
        "contagioso": True, "raio_contagio": 2.0,
        "descricao": "Veneno que se espalha entre inimigos"
    },
    "Esporos Alucinógenos": {
        "tipo": "AREA", "dano": 0.0, "raio_area": 3.0, "cor": (200, 150, 255),
        "custo": 28.0, "cooldown": 15.0, "efeito": "CHARME", "elemento": "NATUREZA",
        "duracao_charme": 2.0,
        "descricao": "Confunde inimigos - eles te seguem"
    },
    "Fotossíntese": {
        "tipo": "CHANNEL", "cor": (150, 255, 100), "custo": 0, "cooldown": 20.0,
        "elemento": "NATUREZA", "canalizavel": True, "duracao_max": 4.0,
        "cura_por_segundo": 15.0, "imobiliza": True,
        "descricao": "Canaliza para curar (não pode mover)"
    },
    "Wrath of Nature": {
        "tipo": "AREA", "dano": 60.0, "raio_area": 6.0, "cor": (100, 200, 50),
        "custo": 65.0, "cooldown": 40.0, "elemento": "NATUREZA",
        "efeito": "ENRAIZADO", "efeito2": "ENVENENADO",
        "delay": 1.0, "ondas": 3,
        "descricao": "3 ondas de natureza devastadora"
    },
    
    # =========================================================================
    # 💜 ARCANO - Puro, amplificação, manipulação
    # =========================================================================
    "Disparo de Mana": {
        "tipo": "PROJETIL", "dano": 10.0, "velocidade": 14.0, "raio": 0.3,
        "vida": 2.5, "cor": (50, 150, 255), "custo": 8.0, "cooldown": 1.5,
        "efeito": "NORMAL", "elemento": "ARCANO",
        "descricao": "Projétil básico de mana pura"
    },
    "Mísseis Arcanos": {
        "tipo": "PROJETIL", "dano": 8.0, "velocidade": 18.0, "raio": 0.2,
        "vida": 1.5, "cor": (100, 100, 255), "custo": 15.0, "cooldown": 3.0,
        "elemento": "ARCANO", "multi_shot": 5, "homing": True,
        "descricao": "5 mísseis teleguiados"
    },
    "Escudo Arcano": {
        "tipo": "BUFF", "cor": (100, 150, 255), "custo": 20.0, "cooldown": 12.0,
        "duracao": 5.0, "elemento": "ARCANO",
        "escudo": 40.0, "reflete_projeteis": True,
        "descricao": "Escudo que reflete projéteis"
    },
    "Explosão Arcana": {
        "tipo": "AREA", "dano": 35.0, "raio_area": 2.5, "cor": (150, 100, 255),
        "custo": 25.0, "cooldown": 8.0, "efeito": "SILENCIADO", "elemento": "ARCANO",
        "descricao": "Explosão que silencia"
    },
    "Amplificar Magia": {
        "tipo": "BUFF", "cor": (180, 100, 255), "custo": 15.0, "cooldown": 20.0,
        "duracao": 8.0, "elemento": "ARCANO",
        "bonus_dano_magico": 1.5, "bonus_area": 1.3,
        "descricao": "Próximas magias +50% dano e área"
    },
    "Roubar Magia": {
        "tipo": "PROJETIL", "dano": 15.0, "velocidade": 20.0, "raio": 0.3,
        "vida": 1.5, "cor": (200, 150, 255), "custo": 20.0, "cooldown": 10.0,
        "elemento": "ARCANO", "rouba_buff": True,
        "descricao": "Rouba um buff aleatório do alvo"
    },
    "Contrafeitiço": {
        "tipo": "BUFF", "cor": (150, 150, 255), "custo": 25.0, "cooldown": 15.0,
        "duracao": 2.0, "elemento": "ARCANO",
        "reflete_skills": True,
        "descricao": "Reflete a próxima skill inimiga"
    },
    "Portal Arcano": {
        "tipo": "DASH", "distancia": 10.0, "cor": (100, 100, 255),
        "custo": 30.0, "cooldown": 15.0, "elemento": "ARCANO",
        "cria_portal": True, "duracao_portal": 5.0,
        "descricao": "Cria portal de ida e volta"
    },
    "Desintegrar": {
        "tipo": "BEAM", "dano": 15.0, "alcance": 12.0, "cor": (200, 100, 255),
        "custo": 40.0, "cooldown": 12.0, "elemento": "ARCANO",
        "canalizavel": True, "dano_por_segundo": 50.0, "duracao_max": 3.0,
        "penetra_escudo": True,
        "descricao": "Raio que ignora escudos"
    },
    "Conjuração Perfeita": {
        "tipo": "BUFF", "cor": (255, 200, 255), "custo": 50.0, "cooldown": 60.0,
        "duracao": 10.0, "elemento": "ARCANO",
        "sem_cooldown": True, "custo_mana_metade": True,
        "descricao": "Skills sem cooldown por 10s"
    },
    
    # =========================================================================
    # 🌀 TEMPO - Slow, haste, reset
    # =========================================================================
    "Slow Motion": {
        "tipo": "AREA", "dano": 0.0, "raio_area": 4.0, "cor": (200, 180, 255),
        "custo": 25.0, "cooldown": 15.0, "efeito": "LENTO", "elemento": "TEMPO",
        "slow_fator": 0.3, "duracao": 3.0,
        "descricao": "Desacelera o tempo na área"
    },
    "Acelerar": {
        "tipo": "BUFF", "cor": (255, 200, 150), "custo": 20.0, "cooldown": 12.0,
        "duracao": 5.0, "elemento": "TEMPO",
        "efeito_buff": "ACELERADO", "bonus_velocidade": 1.8,
        "descricao": "Acelera muito o movimento"
    },
    "Reverter": {
        "tipo": "BUFF", "cor": (200, 150, 255), "custo": 40.0, "cooldown": 30.0,
        "elemento": "TEMPO", "reverte_estado": 3.0,
        "descricao": "Volta ao estado de 3s atrás (HP, posição)"
    },
    "Parar o Tempo": {
        "tipo": "AREA", "dano": 0.0, "raio_area": 5.0, "cor": (220, 200, 255),
        "custo": 50.0, "cooldown": 45.0, "efeito": "TEMPO_PARADO", "elemento": "TEMPO",
        "duracao_stop": 2.0, "afeta_caster": False,
        "descricao": "Para o tempo para inimigos"
    },
    "Previsão": {
        "tipo": "BUFF", "cor": (180, 180, 255), "custo": 15.0, "cooldown": 20.0,
        "duracao": 4.0, "elemento": "TEMPO",
        "esquiva_garantida": 2, "ve_ataques": True,
        "descricao": "Vê o futuro - esquiva 2 ataques"
    },
    "Eco Temporal": {
        "tipo": "PROJETIL", "dano": 25.0, "velocidade": 15.0, "raio": 0.4,
        "vida": 2.0, "cor": (200, 180, 255), "custo": 30.0, "cooldown": 10.0,
        "elemento": "TEMPO", "duplica_apos": 1.0,
        "descricao": "Projétil que duplica após 1s"
    },
    "Idade Acelerada": {
        "tipo": "PROJETIL", "dano": 30.0, "velocidade": 10.0, "raio": 0.5,
        "vida": 2.5, "cor": (150, 130, 200), "custo": 35.0, "cooldown": 15.0,
        "efeito": "EXAUSTO", "elemento": "TEMPO",
        "descricao": "Envelhece o alvo temporariamente"
    },
    
    # =========================================================================
    # 🌌 GRAVITAÇÃO - Pull, push, manipulação
    # =========================================================================
    "Pulso Gravitacional": {
        "tipo": "AREA", "dano": 20.0, "raio_area": 3.0, "cor": (100, 50, 150),
        "custo": 20.0, "cooldown": 8.0, "efeito": "PUXADO", "elemento": "GRAVITACAO",
        "puxa_para_centro": True,
        "descricao": "Puxa inimigos para o centro"
    },
    "Repulsão": {
        "tipo": "AREA", "dano": 15.0, "raio_area": 2.5, "cor": (150, 100, 200),
        "custo": 18.0, "cooldown": 6.0, "efeito": "EMPURRAO", "elemento": "GRAVITACAO",
        "forca_empurrao": 2.0,
        "descricao": "Empurra todos para longe"
    },
    "Campo de Gravidade": {
        "tipo": "AREA", "dano": 5.0, "raio_area": 4.0, "cor": (80, 40, 120),
        "custo": 30.0, "cooldown": 15.0, "efeito": "LENTO", "elemento": "GRAVITACAO",
        "duracao": 5.0, "gravidade_aumentada": 3.0,
        "descricao": "Área com gravidade tripla - slow e sem pulo"
    },
    "Levitar": {
        "tipo": "BUFF", "cor": (150, 100, 200), "custo": 15.0, "cooldown": 10.0,
        "duracao": 6.0, "elemento": "GRAVITACAO",
        "voo": True, "imune_ground": True,
        "descricao": "Flutua no ar - imune a efeitos terrestres"
    },
    "Buraco Negro": {
        "tipo": "AREA", "dano": 10.0, "raio_area": 4.0, "cor": (20, 0, 40),
        "custo": 50.0, "cooldown": 30.0, "efeito": "VORTEX", "elemento": "GRAVITACAO",
        "duracao": 3.0, "dano_por_segundo": 25.0, "puxa_continuo": True,
        "descricao": "Buraco negro que suga e causa dano"
    },
    "Colapso": {
        "tipo": "PROJETIL", "dano": 60.0, "velocidade": 8.0, "raio": 0.3,
        "vida": 3.0, "cor": (50, 20, 80), "custo": 40.0, "cooldown": 18.0,
        "efeito": "KNOCK_UP", "elemento": "GRAVITACAO",
        "delay_explosao": 2.0, "raio_explosao": 2.5,
        "descricao": "Esfera que implode após 2s"
    },
    
    # =========================================================================
    # 💀 CAOS - Aleatório, instável, poderoso
    # =========================================================================
    "Chama Caótica": {
        "tipo": "PROJETIL", "dano": 30.0, "velocidade": 12.0, "raio": 0.4,
        "vida": 2.0, "cor": (255, 50, 150), "custo": 22.0, "cooldown": 5.0,
        "elemento": "CAOS", "elemento_aleatorio": True, "dano_variavel": (0.5, 2.0),
        "descricao": "Dano e elemento aleatórios"
    },
    "Explosão do Caos": {
        "tipo": "AREA", "dano": 40.0, "raio_area": 3.0, "cor": (255, 100, 200),
        "custo": 35.0, "cooldown": 12.0, "elemento": "CAOS",
        "efeito_aleatorio": True, "efeitos_possiveis": [
            "QUEIMANDO", "CONGELADO", "PARALISIA", "ENVENENADO", "LENTO"
        ],
        "descricao": "Explosão com efeito aleatório"
    },
    "Roleta Russa": {
        "tipo": "PROJETIL", "dano": 100.0, "velocidade": 20.0, "raio": 0.3,
        "vida": 1.5, "cor": (255, 0, 100), "custo": 30.0, "cooldown": 15.0,
        "elemento": "CAOS", "chance_backfire": 0.2,
        "descricao": "Dano massivo mas 20% chance de acertar você"
    },
    "Mutação": {
        "tipo": "BUFF", "cor": (200, 50, 150), "custo": 25.0, "cooldown": 20.0,
        "duracao": 8.0, "elemento": "CAOS",
        "stats_aleatorios": True,
        "descricao": "Stats aleatórios (pode ser bom ou ruim)"
    },
    "Instabilidade": {
        "tipo": "PROJETIL", "dano": 20.0, "velocidade": 10.0, "raio": 0.5,
        "vida": 3.0, "cor": (255, 150, 200), "custo": 28.0, "cooldown": 8.0,
        "elemento": "CAOS", "split_aleatorio": True, "max_splits": 4,
        "descricao": "Divide aleatoriamente em mais projéteis"
    },
    "Apocalipse": {
        "tipo": "AREA", "dano": 80.0, "raio_area": 6.0, "cor": (255, 0, 150),
        "custo": 70.0, "cooldown": 60.0, "elemento": "CAOS",
        "delay": 3.0, "meteoros_aleatorios": 10,
        "descricao": "Chuva de meteoros caóticos"
    },
    
    # =========================================================================
    # ⚔️ FÍSICO/MARCIAL
    # =========================================================================
    "Impacto Sônico": {
        "tipo": "PROJETIL", "dano": 18.0, "velocidade": 20.0, "raio": 0.6,
        "vida": 0.35, "cor": (200, 200, 255), "custo": 12.0, "cooldown": 3.0,
        "efeito": "EMPURRAO", "descricao": "Onda de choque curta mas poderosa"
    },
    "Avanço Brutal": {
        "tipo": "DASH", "dano": 25.0, "distancia": 4.0, "cor": (255, 100, 100),
        "custo": 15.0, "cooldown": 5.0, "efeito": "EMPURRAO",
        "descricao": "Avança causando dano no caminho"
    },
    "Fúria Giratória": {
        "tipo": "AREA", "dano": 20.0, "raio_area": 2.0, "cor": (200, 150, 150),
        "custo": 18.0, "cooldown": 6.0, "efeito": "NORMAL",
        "descricao": "Gira a arma atingindo todos ao redor"
    },
    "Golpe do Executor": {
        "tipo": "BUFF", "cor": (150, 0, 0), "custo": 20.0, "cooldown": 15.0,
        "duracao": 3.0, "buff_dano": 2.0,
        "descricao": "Próximo ataque causa dano dobrado"
    },
    "Grito de Guerra": {
        "tipo": "BUFF", "cor": (255, 150, 100), "custo": 20.0, "cooldown": 20.0,
        "duracao": 8.0, "efeito_buff": "FURIA",
        "descricao": "Entra em fúria - mais dano, mais vulnerável"
    },
    "Execução": {
        "tipo": "PROJETIL", "dano": 100.0, "velocidade": 8.0, "raio": 0.3,
        "vida": 1.5, "cor": (255, 0, 0), "custo": 50.0, "cooldown": 30.0,
        "condicao": "ALVO_BAIXA_VIDA",
        "descricao": "Dano massivo contra alvos com pouca vida"
    },
    "Terremoto": {
        "tipo": "AREA", "dano": 45.0, "raio_area": 4.0, "cor": (150, 100, 50),
        "custo": 35.0, "cooldown": 15.0, "efeito": "KNOCK_UP",
        "descricao": "Abala o chão derrubando inimigos"
    },
    "Provocar": {
        "tipo": "AREA", "dano": 0.0, "raio_area": 5.0, "cor": (255, 50, 50),
        "custo": 10.0, "cooldown": 10.0,
        "taunt": True, "duracao_taunt": 3.0,
        "descricao": "Força inimigos a te atacarem"
    },
    
    # =========================================================================
    # 🛡️ DEFESA/SUPORTE
    # =========================================================================
    "Reflexo Espelhado": {
        "tipo": "BUFF", "cor": (200, 200, 255), "custo": 30.0, "cooldown": 20.0,
        "duracao": 3.0, "refletir": 0.5,
        "descricao": "Reflete 50% do dano recebido"
    },
    "Velocidade Arcana": {
        "tipo": "BUFF", "cor": (255, 255, 150), "custo": 15.0, "cooldown": 10.0,
        "duracao": 4.0, "buff_velocidade": 1.5,
        "descricao": "Aumenta velocidade de movimento"
    },
    "Determinação": {
        "tipo": "BUFF", "cor": (255, 200, 100), "custo": 25.0, "cooldown": 25.0,
        "duracao": 6.0, "efeito_buff": "DETERMINADO",
        "descricao": "Cooldowns reduzidos pela metade"
    },
    "Último Suspiro": {
        "tipo": "BUFF", "cor": (255, 100, 100), "custo": 0, "cooldown": 90.0,
        "ativa_ao_morrer": True, "cura_percent": 0.5,
        "descricao": "Ao morrer, revive com 50% HP (passivo)"
    },
    
    # =========================================================================
    # 💀 ESPECIAIS / ÚNICOS
    # =========================================================================
    "Invocação: Espírito": {
        "tipo": "SUMMON", "cor": (180, 180, 255), "custo": 35.0, "cooldown": 25.0,
        "duracao": 10.0, "summon_vida": 50.0, "summon_dano": 8.0,
        "descricao": "Invoca um espírito aliado"
    },
    "Troca de Almas": {
        "tipo": "DASH", "distancia": 0.0, "cor": (150, 0, 150),
        "custo": 40.0, "cooldown": 30.0, "efeito": "TROCAR_POS",
        "descricao": "Troca de posição com o alvo"
    },
    "Bomba Relógio": {
        "tipo": "PROJETIL", "dano": 80.0, "velocidade": 15.0, "raio": 0.4,
        "vida": 3.0, "cor": (255, 100, 0), "custo": 40.0, "cooldown": 20.0,
        "efeito": "BOMBA_RELOGIO", "delay_explosao": 3.0, "raio_explosao": 2.5,
        "descricao": "Marca o alvo - explode após 3s"
    },
    "Cópia Sombria": {
        "tipo": "SUMMON", "cor": (100, 100, 100), "custo": 45.0, "cooldown": 30.0,
        "duracao": 8.0, "copia_caster": True,
        "descricao": "Cria uma cópia que imita seus ataques"
    },
    "Link de Vida": {
        "tipo": "PROJETIL", "dano": 0.0, "velocidade": 20.0, "raio": 0.3,
        "vida": 2.0, "cor": (255, 100, 255), "custo": 30.0, "cooldown": 25.0,
        "efeito": "LINK_ALMA", "link_percent": 0.5,
        "descricao": "Conecta almas - dano dividido 50/50"
    },
    "Sacrifício": {
        "tipo": "AREA", "dano": 150.0, "raio_area": 3.0, "cor": (255, 0, 0),
        "custo": 0, "cooldown": 120.0, "custo_vida_percent": 0.5,
        "descricao": "Sacrifica 50% HP para dano massivo"
    },
}


def get_skill_data(nome):
    """Retorna os dados de uma skill pelo nome"""
    return SKILL_DB.get(nome, SKILL_DB["Nenhuma"])


def get_skills_by_tipo(tipo):
    """Retorna todas as skills de um determinado tipo"""
    return {k: v for k, v in SKILL_DB.items() if v.get("tipo") == tipo}


def get_skills_by_elemento(elemento):
    """Retorna skills por elemento"""
    return {k: v for k, v in SKILL_DB.items() if v.get("elemento") == elemento}


def get_skills_by_efeito(efeito):
    """Retorna skills que causam um determinado efeito"""
    return {k: v for k, v in SKILL_DB.items() if v.get("efeito") == efeito}


def listar_skills_para_ui():
    """Retorna lista formatada para ComboBox"""
    return list(SKILL_DB.keys())


def listar_elementos():
    """Retorna lista de elementos disponíveis"""
    elementos = set()
    for skill in SKILL_DB.values():
        if "elemento" in skill:
            elementos.add(skill["elemento"])
    return sorted(list(elementos))


def contar_skills():
    """Retorna contagem de skills por tipo"""
    contagem = {}
    for skill in SKILL_DB.values():
        tipo = skill.get("tipo", "DESCONHECIDO")
        contagem[tipo] = contagem.get(tipo, 0) + 1
    return contagem

