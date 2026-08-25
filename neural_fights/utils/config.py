# config.py

# FÍSICA
PPM = 50
GRAVIDADE_Z = 35.0
ATRITO = 8.0
ALTURA_PADRAO = 1.70

# === ONDA 8B: MECÂNICAS DEFENSIVAS ===
# Estamina é o recurso defensivo: dash e bloqueio consomem, o tempo
# devolve. Segurar a guarda quase congela a regen — guarda permanente
# não é grátis.
ESTAMINA_REGEN_S = 12.0
ESTAMINA_REGEN_GUARDA_S = 4.0
CUSTO_ESTAMINA_DASH = 25.0
CUSTO_ESTAMINA_BLOQUEIO = 15.0
CUSTO_ESTAMINA_PARRY = 10.0
COOLDOWN_DASH_S = 1.6
# Bloqueio direcional: só cobre o arco frontal; parry é o bloqueio
# recém-erguido (timing, não sorteio).
ARCO_BLOQUEIO_RAD = 1.0472          # ±60°
JANELA_PARRY_S = 0.18
FATOR_DANO_BLOQUEIO = 0.35          # bloqueio reduz 65% do dano
FATOR_DANO_BLOQUEIO_CAVALEIRO = 0.20
FATOR_KNOCKBACK_BLOQUEIO = 0.5
STAGGER_PARRY_S = 0.4

# VISUAL
LARGURA, ALTURA = 1200, 800
LARGURA_PORTRAIT, ALTURA_PORTRAIT = 540, 960  # 9:16 para filmagem vertical
FPS = 60

# CORES
PRETO = (0, 0, 0)
BRANCO = (255, 255, 255)
CHAO_COR = (30, 30, 30)
COR_FUNDO = (25, 25, 30)
COR_GRID = (35, 35, 45)
VERMELHO_SANGUE = (180, 0, 0)
SANGUE_ESCURO = (100, 0, 0)
AMARELO_FAISCA = (255, 230, 100) 
VERDE_VIDA = (46, 204, 113)
VERMELHO_VIDA = (231, 76, 60)
AZUL_MANA = (52, 152, 219)
COR_CORPO = (20, 20, 20)
COR_P1 = (52, 152, 219) 
COR_P2 = (231, 76, 60)
COR_UI_BG = (0, 0, 0, 150)
COR_TEXTO_TITULO = (255, 215, 0)
COR_TEXTO_INFO = (200, 200, 200)