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

# === ONDA 8H: HITSTUN E COMBOS ===
# Quem apanha perde a resposta por um instante — a fundação de combo do
# gênero. O stun escala com o dano, DECRESCE a cada hit do mesmo combo
# (anti-stunlock) e tanques resistem. Golpe BLOQUEADO não atordoa: a
# guarda é o quebra-combo universal.
HITSTUN_BASE_S = 0.14
HITSTUN_POR_DANO = 0.004            # +4ms por ponto de dano final
HITSTUN_MAX_S = 0.40
HITSTUN_SCALING_COMBO = 0.85        # hit N do combo atordoa 15% menos
HITSTUN_MIN_S = 0.08
JANELA_COMBO_S = 1.2                # sem novo hit nessa janela, combo morre
# Combo flow: o próximo swing sai mais rápido sobre alvo em hitstun —
# é o que transforma hits soltos em strings de 2-4 golpes.
COMBO_FLOW_CADENCIA = 0.8
# Burst de escape: no 3º hit do combo, o defensor pode gastar fôlego num
# empurrão com invulnerabilidade curta (a chance vem da personalidade).
CUSTO_ESTAMINA_BURST = 40.0
BURST_PUSHBACK = 14.0
BURST_INVULN_S = 0.25

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