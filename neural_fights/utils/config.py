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
HITSTUN_SCALING_COMBO = 0.80        # hit N do combo atordoa 20% menos (Onda 10A: era 15%; a órbita
                                    # que segue reto sobre alvo atordoado levou o maior combo ao teto C2)
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
# === ONDA 10A: AGARRÃO, STANDOFF E WALL-SPLAT ===
# O cara-a-cara sem golpe é o assassino do ritmo. O motor detecta o
# standoff (em alcance, ninguém ataca), força iniciativa e, se nada
# acontece, os corpos se AGARRAM: 0,25s travados e um desfecho rápido
# (arremesso/joelhada/empurrão/reversão/escape). Corpo lançado que bate
# na parede estatela (wall-splat).
AGARRAO_LOCK_S = 0.25
AGARRAO_COOLDOWN_S = 3.0
CUSTO_ESTAMINA_AGARRAO = 15.0
FORCA_ARREMESSO = 30.0               # com ATRITO 8 → ~3,75 m de deslize
DANO_ARREMESSO_PCT = (0.04, 0.08)    # fração da vida_max, escala com força
AGARRAO_DIST_MAX = 2.4               # distância máxima para agarrar (lunge durante o lock)
STANDOFF_JANELA_S = 1.5              # na faixa de confronto sem HIT → iniciativa
STANDOFF_ESCALADA_S = 1.0            # ainda sem hit → agarrão / 2ª dose
STANDOFF_COOLDOWN_S = 3.0
WALL_SPLAT_INTENSIDADE_MIN = 8.0     # velocidade perpendicular mínima
WALL_SPLAT_DANO_MAX = 0.08           # fração da vida_max
WALL_SPLAT_STUN_S = (0.3, 0.5)
LANCADO_KNOCKBACK_MIN = 24.0         # knockback que arma o estado "lançado" (golpe forte)

# === KNOCKBACK DO CORPO A CORPO ===
# A formula de `calcular_knockback_com_forca` foi escrita para uma escala de
# forca 10-20; o banco tem forca 4,5-7,7 (mediana 6,5). Medido em 3 lutas
# reais, o melee saia com mediana 8,3 contra 19,5 dos projeteis: um soco
# empurrava menos da metade de uma flecha, ~52 px numa arena de 1200. Estes
# fatores recolocam o golpe na escala do resto do jogo.
KNOCKBACK_MELEE_ESCALA = 5.0   # era 3.0 embutido na formula
KNOCKBACK_MELEE_MIN = 8.0      # piso: ate o golpe fraco move o corpo (~1 m)
KNOCKBACK_MELEE_MAX = 40.0     # teto: mesmo do caminho de projetil/skill

# === ONDA 10B: MOBILIDADE NO MOTOR ===
# O eixo 'mobilidade' da personalidade (0-1) passa a existir no corpo: dash
# mais barato/frequente/forte, giro mais rapido, um pouco mais de velocidade.
DASH_MOB_CD_FATOR = 0.47      # cd 1,6 s -> 1,0 s em mob 0,8
DASH_MOB_CUSTO_FATOR = 0.35   # custo 25 -> 18 em mob 0,8
DASH_MOB_FORCA_FATOR = 0.31   # forca 16 -> 20 em mob 0,8
VEL_MOB_FATOR = 0.08          # +8% de velocidade em mob 1,0
CD_DASH_TATICO_S = 2.5        # cooldown do dash tatico da IA (menos mob)

# === ONDA 10D: HABILIDADES COM CONSEQUÊNCIA ===
# Área cai no ALVO (posição prevista, até ALCANCE_CAST_PADRAO); EMPURRAO
# empurra de verdade; PUXADO/VORTEX puxam; obstáculos destrutíveis quebram.
FORCA_EMPURRAO_PADRAO = 14.0
FORCA_PUXAO = 20.0
PUXAO_DURACAO_S = 0.3
ALCANCE_CAST_PADRAO = 6.0
OBSTACULO_DANO_ARREMESSO = 999.0

# === ONDA 10 (ajuste de fluxo): HIT-STOP SO PARA PANCADA GRANDE ===
# O congelamento por hit em TODO golpe (2-18 frames x multiplicador de
# classe ate 1,8) quebrava o fluxo da luta no ritmo novo. So congela quando
# o dano e GRANDE relativo a vida do alvo; o feedback dos golpes comuns
# fica com shake, particulas e knockback. O slow-motion de KO nao muda.
# Varredura em 6 lutas: 5% = 3,7 congelamentos/luta; 6% = 1,5; 8% = 0,5;
# 10% = 0,3. Sem portao eram ~44/luta (~4,3 s de tela parada por luta).
HITSTOP_DANO_MIN_PCT = 0.06   # fracao da vida_max do ALVO

# ============================================================
# ONDA 11B: qualidade 1-a-1 das skills
# ============================================================
# Multiplicador de um EXECUTE bem-sucedido (condicao ALVO_BAIXA_VIDA com
# ``executa``). Era 10.0 literal duplicado em Projetil/AreaEffect.
EXECUTA_MULTIPLICADOR = 10.0
