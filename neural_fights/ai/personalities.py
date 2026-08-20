"""
=============================================================================
NEURAL FIGHTS - Personalidades da IA v11.0 ULTRA EXPANDED EDITION
=============================================================================
Sistema de personalidade procedural com MILHÕES de combinações:
- 120+ Traços de personalidade
- 30+ Arquétipos de combate  
- 25+ Estilos de luta
- 50+ Quirks (comportamentos únicos)
- 20+ Filosofias de combate
- Sistema de humor dinâmico
- NOVO: Sistema de Instintos de Combate (reflexos automáticos)
- NOVO: Sistema de Ritmos de Batalha (padrões cíclicos)

NOVIDADES v11.0:
- 50+ novos traços de personalidade
- 15+ novos quirks
- 10+ novos estilos de luta
- Sistema de INSTINTOS - reações automáticas
- Sistema de RITMOS - ciclos de comportamento
- Mais presets de personalidade
=============================================================================
"""

# =============================================================================
# TRAÇOS DE PERSONALIDADE (120+)
# =============================================================================

TRACOS_AGRESSIVIDADE = [
    # === ORIGINAIS ===
    "IMPRUDENTE",        # Ignora defesa completamente
    "AGRESSIVO",         # Prefere sempre atacar
    "BERSERKER",         # Mais forte com menos HP
    "OPORTUNISTA",       # Ataca quando inimigo erra
    "SANGUINARIO",       # Não para até matar
    "PREDADOR",          # Persegue alvos feridos
    "SELVAGEM",          # Ataques frenéticos
    "IMPLACAVEL",        # Nunca recua voluntariamente
    "FURIOSO",           # Raiva constante
    "BRUTAL",            # Prefere golpes pesados
    "PRESSAO_CONSTANTE", # Mantém pressão sempre
    "FINALIZADOR_NATO",  # Sabe quando dar o golpe final
    "ENCURRALADOR",      # Especialista em encurralar oponentes
    # === NOVOS v11.0 ===
    "DOMINADOR",         # Quer controlar cada momento da luta
    "CARRASCO",          # Prolonga a dor do oponente antes de finalizar
    "DESTRUIDOR",        # Foca em causar dano máximo
    "INCANSAVEL",        # Nunca para de atacar, stamina infinita mental
    "EXPLOSIVO",         # Bursts de agressividade extrema
    "ALPHA",             # Sempre quer ser o dominante
    "SEDENTO",           # Sede insaciável por combate
    "PROVOCADOR",        # Provoca para tirar do sério
    "TOURO",             # Avança direto sem pensar
    "MARTELO",           # Golpes pesados repetidos
    "TRITURADOR",        # Quer esmagar completamente
    "DEVORADOR",         # Consome a vontade do oponente
]

TRACOS_DEFENSIVO = [
    # === ORIGINAIS ===
    "COVARDE",           # Foge com HP baixo
    "CAUTELOSO",         # Mantém distância segura
    "PACIENTE",          # Espera oportunidades
    "REATIVO",           # Contra-ataca
    "TANQUE",            # Absorve dano
    "PROTETOR",          # Defende área
    "EVASIVO",           # Esquiva muito
    "PARANOICO",         # Sempre esperando ataque
    "MEDROSO",           # Medo constante
    "PRUDENTE",          # Calcula riscos
    "LEITURA_PERFEITA",  # Lê movimentos do oponente
    "TIMING_PRECISO",    # Timing de desvio perfeito
    "COBERTURA_MESTRE",  # Usa obstáculos para proteção
    # === NOVOS v11.0 ===
    "BLINDADO",          # Ignora dano pequeno mentalmente
    "INABALAVEL",        # Não é afetado por pressão
    "MURALHA",           # Posição firme, não recua
    "TARTARUGA",         # Extremamente defensivo
    "ABSORVEDOR",        # Deixa levar hits para contra-atacar
    "PREVISOR",          # Antecipa ataques antes de acontecerem
    "FANTASMA",          # Parece estar lá mas escapa sempre
    "RESILIENTE",        # Recupera compostura rapidamente
    "ESPELHO",           # Reflete o estilo do oponente
    "SENTINEL",          # Guarda uma posição específica
    "ARMADILHEIRO",      # Prepara armadilhas posicionais
    "SOBREVIVENTE",      # Faz qualquer coisa para sobreviver
]

TRACOS_MOBILIDADE = [
    # === ORIGINAIS ===
    "SALTADOR",          # Pula frequentemente
    "ACROBATA",          # Usa dash muito
    "ERRATICO",          # Movimentos imprevisíveis
    "FLANQUEADOR",       # Ataca pelos lados
    "PERSEGUIDOR",       # Não deixa fugir
    "VELOZ",             # Sempre se movendo
    "ESTATICO",          # Prefere ficar parado
    "DESLIZANTE",        # Move suavemente
    "TELEGRAFICO",       # Movimentos previsíveis
    "CAOTICO",           # Direções aleatórias
    "ESPACAMENTO_MESTRE",# Controla distância perfeitamente
    "MICRO_AJUSTES",     # Pequenos ajustes constantes
    "NAVEGADOR",         # Navega bem entre obstáculos
    "ARENA_MASTER",      # Usa toda a arena estrategicamente
    # === NOVOS v11.0 ===
    "DANÇARINO",         # Movimentos fluidos como dança
    "RELAMPAGO",         # Explosões de velocidade
    "BORBOLETA",         # Flutua pelo campo, difícil de pegar
    "SERPENTE",          # Movimentos sinuosos
    "TELEPORTER",        # Parece se teletransportar de tão rápido
    "ORBITA",            # Orbita ao redor do oponente
    "ZIGZAG",            # Nunca anda em linha reta
    "PIVOTADOR",         # Mestre em pivots e giros
    "RASTREADOR",        # Segue passos do oponente
    "KITER",             # Mantém distância enquanto ataca
    "COLADO",            # Gruda no oponente
    "IOIO",              # Vai e volta constantemente
]

TRACOS_SKILLS = [
    # === ORIGINAIS ===
    "SPAMMER",           # Usa skills frequentemente
    "CALCULISTA",        # Usa skills estrategicamente
    "CONSERVADOR",       # Economiza mana
    "EXPLOSIVO_SKILLS",  # Salva skills para burst
    "COMBO_MASTER",      # Encadeia skills
    "SNIPER",            # Skills de longa distância
    "CLOSE_RANGE",       # Skills corpo a corpo
    "AREA_DENIAL",       # Controla espaço
    "DEBUFFER",          # Foca em status
    "SUPPORT",           # Buffs próprios
    "SETUP_ARTIST",      # Prepara armadilhas e setups
    "ZONE_CONTROLLER",   # Controla zonas da arena com skills
    # === NOVOS v11.0 ===
    "TECNICO",           # Usa skills com precisão cirúrgica
    "DESPERDICADOR",     # Usa skills sem pensar, só pra ver o efeito
    "CANALIZADOR",       # Prefere skills que canalizam
    "INSTANT_CAST",      # Ama skills instantâneas
    "CHAIN_CASTER",      # Encadeia skill após skill
    "FINISHER",          # Guarda skills pra finalizar
    "OPENER",            # Sempre abre com skill
    "MANA_BURNER",       # Queima toda mana de uma vez
    "COOLDOWN_WATCHER",  # Ataca quando skill do inimigo está em cooldown
    "SKILL_BAITER",      # Faz o inimigo gastar skills
    "CANCELADOR",        # Tenta cancelar skills inimigas
    "ZONER",             # Usa skills para criar zonas de controle
]

TRACOS_MENTAL = [
    # === ORIGINAIS ===
    "VINGATIVO",         # Raiva aumenta com dano
    "DETERMINADO",       # Não desiste nunca
    "ADAPTAVEL",         # Muda estratégia
    "FRIO",              # Emoções não afetam
    "EMOTIVO",           # Emoções extremas
    "FOCADO",            # Ignora distrações
    "DISPERSO",          # Muda alvo facilmente
    "TEIMOSO",           # Mantém estratégia
    "CRIATIVO",          # Tenta coisas novas
    "METODICO",          # Padrões repetitivos
    "CLUTCH_PLAYER",     # Melhor sob pressão
    "TILTER",            # Fica pior quando perde
    "AWARENESS_ALTO",    # Alta consciência do ambiente
    # === NOVOS v11.0 ===
    "PSICOPATA",         # Zero empatia, zero medo
    "ANALITICO",         # Analisa tudo constantemente
    "INSTINTIVO",        # Age por instinto puro
    "CEREBRAL",          # Pensa demais às vezes
    "IMPULSIVO",         # Age antes de pensar
    "RESILIENTE_MENTAL", # Não deixa derrotas afetarem
    "TRAUMATIZADO",      # Carrega traumas de derrotas passadas
    "CONFIANTE",         # Sempre acredita que vai ganhar
    "INSEGURO",          # Duvida de si mesmo
    "ZEN",               # Paz interior inabalável
    "CAOS_MENTAL",       # Mente é um turbilhão
    "PREDITOR",          # Tenta prever o futuro
    "REATIVO_MENTAL",    # Só reage, nunca planeja
    "OBSESSIVO",         # Obsecado com um aspecto da luta
]

TRACOS_ESPECIAIS = [
    # === ORIGINAIS ===
    "SHOWMAN",           # Faz poses dramáticas
    "ASSASSINO_NATO",    # Executa com precisão
    "BERSERKER_RAGE",    # Modo fúria quando crítico
    "PHOENIX",           # Mais forte perto da morte
    "VAMPIRO",           # Foca em drenar vida
    "KAMIKAZE",          # Ignora própria vida
    "TRICKSTER",         # Engana o oponente
    "HONORAVEL",         # Luta "justo"
    "COVARDE_TATICO",    # Foge estrategicamente
    "ULTIMO_SUSPIRO",    # Burst final quando morrendo
    "MOMENTUM_RIDER",    # Melhor quando ganhando
    "UNDERDOG",          # Melhor quando perdendo
    "BAITER_NATO",       # Mestre em fintas
    "WALL_FIGHTER",      # Luta bem perto de paredes
    "PILLAR_DANCER",     # Usa pilares/obstáculos como parceiro
    # === NOVOS v11.0 ===
    "METAMORFO",         # Muda completamente de estilo durante a luta
    "DUPLA_PERSONALIDADE",# Alterna entre duas personalidades
    "GLUTTON",           # Quer mais e mais combate
    "PERFECCIONISTA",    # Só aceita vitórias perfeitas
    "STYLIST",           # Prioriza estilo sobre eficiência
    "EFICIENTE",         # Mínimo esforço, máximo resultado
    "CAÇADOR_GLORIA",    # Quer momentos épicos
    "MINIMALISTA",       # Faz o mínimo necessário
    "MAXIMALISTA",       # Sempre dá 110%
    "SÁDICO",            # Gosta de ver o oponente sofrer
    "MASOQUISTA",        # Gosta de levar dano
    "APOSTADOR",         # Faz jogadas arriscadas
    "SEGURO",            # Nunca arrisca
    "LENDARIO",          # Tenta criar momentos lendários
    "PRÁTICO",           # Só quer a vitória, não importa como
    "ARTISTA_MARCIAL",   # Vê a luta como arte
    "GLADIADOR",         # Luta para a plateia (mesmo inexistente)
    "SAMURAI",           # Código de honra rígido
    "VIKING",            # Valhalla espera, sem medo da morte
    "NINJA_MENTAL",      # Ataca a mente do oponente
]

# Todos os traços combinados
TODOS_TRACOS = (TRACOS_AGRESSIVIDADE + TRACOS_DEFENSIVO + TRACOS_MOBILIDADE + 
                TRACOS_SKILLS + TRACOS_MENTAL + TRACOS_ESPECIAIS)


# =============================================================================
# EIXOS DE COMPORTAMENTO
# =============================================================================
# Um traço sozinho não faz nada: ele declara *para onde puxa* o comportamento.
# Quem lê é o código de decisão, que consulta o eixo e não o nome.
#
# Antes disto, um traço só existia se alguém tivesse escrito
# ``"NOME" in self.tracos`` em algum ponto do ``brain.py``. Como consequência,
# 107 dos 162 traços declarados não tinham nenhum consumidor: um lutador
# "Artista Marcial, Criativo, Dançarino, Stylist, Zen" se comportava exatamente
# como um lutador sem traço algum.
#
# Declarando por eixo, todo traço passa a valer por construção, e combinações se
# somam em vez de se anularem: BERSERKER + CAUTELOSO produz um meio-termo, e não
# só o primeiro ramo de um ``elif``.
#
# Faixa: [-1, 1]. Eixo ausente = o traço não opina sobre ele.

EIXOS_COMPORTAMENTO = (
    "agressao",     # avança e troca golpes em vez de esperar
    "cautela",      # mantém espaçamento, usa cobertura, escolhe a hora
    "medo",         # recua e foge quando a vida cai
    "frieza",       # resiste a tilt; segue o plano sob pressão
    "caos",         # imprevisibilidade de movimento e decisão
    "mobilidade",   # reposiciona, corre, muda de ângulo
    "perseguicao",  # persegue quem recua em vez de deixar ir
    "skill_uso",    # gasta mana em habilidade em vez de guardar
)


TRACO_EIXOS = {
    # --- TRACOS_AGRESSIVIDADE ---
    'IMPRUDENTE': {"agressao": 0.8, "cautela": -0.7, "medo": -0.4},
    'AGRESSIVO': {"agressao": 0.7, "cautela": -0.3},
    'BERSERKER': {"agressao": 0.9, "cautela": -0.6, "medo": -0.5},
    'OPORTUNISTA': {"agressao": 0.4, "frieza": 0.3},
    'SANGUINARIO': {"agressao": 0.7, "perseguicao": 0.5},
    'PREDADOR': {"agressao": 0.5, "perseguicao": 0.8},
    'SELVAGEM': {"agressao": 0.7, "cautela": -0.4, "caos": 0.4},
    'IMPLACAVEL': {"agressao": 0.8, "medo": -0.4, "perseguicao": 0.6},
    'FURIOSO': {"agressao": 0.7, "frieza": -0.5},
    'BRUTAL': {"agressao": 0.6, "cautela": -0.3},
    'PRESSAO_CONSTANTE': {"agressao": 0.6, "perseguicao": 0.4},
    'FINALIZADOR_NATO': {"agressao": 0.5, "perseguicao": 0.5},
    'ENCURRALADOR': {"agressao": 0.5, "mobilidade": 0.3, "perseguicao": 0.6},
    'DOMINADOR': {"agressao": 0.6, "medo": -0.3},
    'CARRASCO': {"agressao": 0.6, "perseguicao": 0.5},
    'DESTRUIDOR': {"agressao": 0.7, "cautela": -0.4},
    'INCANSAVEL': {"agressao": 0.5, "perseguicao": 0.4},
    'EXPLOSIVO': {"agressao": 0.6, "caos": 0.3},
    'ALPHA': {"agressao": 0.5, "medo": -0.5},
    'SEDENTO': {"agressao": 0.6, "perseguicao": 0.4},
    'PROVOCADOR': {"agressao": 0.4, "caos": 0.3},
    'TOURO': {"agressao": 0.7, "cautela": -0.5, "mobilidade": -0.2},
    'MARTELO': {"agressao": 0.6, "mobilidade": -0.3},
    'TRITURADOR': {"agressao": 0.7, "cautela": -0.3},
    'DEVORADOR': {"agressao": 0.6, "perseguicao": 0.4},
    # --- TRACOS_DEFENSIVO ---
    'COVARDE': {"agressao": -0.6, "medo": 0.8},
    'CAUTELOSO': {"agressao": -0.3, "cautela": 0.7},
    'PACIENTE': {"agressao": -0.2, "cautela": 0.6, "frieza": 0.4},
    'REATIVO': {"cautela": 0.4, "frieza": 0.3},
    'TANQUE': {"cautela": 0.3, "medo": -0.4, "mobilidade": -0.3},
    'PROTETOR': {"cautela": 0.5},
    'EVASIVO': {"agressao": -0.2, "cautela": 0.4, "mobilidade": 0.6},
    'PARANOICO': {"cautela": 0.6, "medo": 0.5},
    'MEDROSO': {"agressao": -0.5, "medo": 0.8},
    'PRUDENTE': {"cautela": 0.7, "frieza": 0.3},
    'LEITURA_PERFEITA': {"cautela": 0.3, "frieza": 0.5},
    'TIMING_PRECISO': {"frieza": 0.5},
    'COBERTURA_MESTRE': {"cautela": 0.7},
    'BLINDADO': {"medo": -0.4, "mobilidade": -0.3},
    'INABALAVEL': {"medo": -0.5, "frieza": 0.7},
    'MURALHA': {"cautela": 0.5, "medo": -0.3, "mobilidade": -0.5},
    'TARTARUGA': {"agressao": -0.5, "cautela": 0.8, "mobilidade": -0.4},
    'ABSORVEDOR': {"cautela": 0.3, "medo": -0.3},
    'PREVISOR': {"cautela": 0.4, "frieza": 0.5},
    'FANTASMA': {"cautela": 0.4, "mobilidade": 0.6},
    'RESILIENTE': {"medo": -0.4, "frieza": 0.4},
    'ESPELHO': {"cautela": 0.3, "frieza": 0.4},
    'SENTINEL': {"cautela": 0.6, "mobilidade": -0.4},
    'ARMADILHEIRO': {"cautela": 0.5, "frieza": 0.3},
    'SOBREVIVENTE': {"cautela": 0.5, "medo": 0.3},
    # --- TRACOS_MOBILIDADE ---
    'SALTADOR': {"mobilidade": 0.6},
    'ACROBATA': {"cautela": 0.2, "mobilidade": 0.8},
    'ERRATICO': {"caos": 0.8, "mobilidade": 0.4},
    'FLANQUEADOR': {"mobilidade": 0.6, "perseguicao": 0.3},
    'PERSEGUIDOR': {"mobilidade": 0.4, "perseguicao": 0.8},
    'VELOZ': {"mobilidade": 0.7},
    'ESTATICO': {"mobilidade": -0.8},
    'DESLIZANTE': {"mobilidade": 0.6},
    'TELEGRAFICO': {"caos": -0.5, "mobilidade": -0.2},
    'CAOTICO': {"caos": 0.8},
    'ESPACAMENTO_MESTRE': {"cautela": 0.5, "mobilidade": 0.4},
    'MICRO_AJUSTES': {"frieza": 0.3, "mobilidade": 0.4},
    'NAVEGADOR': {"mobilidade": 0.5},
    'ARENA_MASTER': {"frieza": 0.4, "mobilidade": 0.4},
    'DANÇARINO': {"caos": 0.3, "mobilidade": 0.7},
    'RELAMPAGO': {"mobilidade": 0.8},
    'BORBOLETA': {"caos": 0.3, "mobilidade": 0.7},
    'SERPENTE': {"caos": 0.2, "mobilidade": 0.6},
    'TELEPORTER': {"mobilidade": 0.8},
    'ORBITA': {"mobilidade": 0.5},
    'ZIGZAG': {"caos": 0.4, "mobilidade": 0.5},
    'PIVOTADOR': {"mobilidade": 0.4},
    'RASTREADOR': {"perseguicao": 0.7},
    'KITER': {"agressao": -0.3, "cautela": 0.5, "mobilidade": 0.6},
    'COLADO': {"agressao": 0.4, "cautela": -0.4, "perseguicao": 0.5},
    'IOIO': {"caos": 0.3, "mobilidade": 0.5},
    # --- TRACOS_SKILLS ---
    'SPAMMER': {"frieza": -0.3, "skill_uso": 0.8},
    'CALCULISTA': {"frieza": 0.7, "skill_uso": 0.3},
    'CONSERVADOR': {"cautela": 0.4, "skill_uso": -0.6},
    'EXPLOSIVO_SKILLS': {"caos": 0.3, "skill_uso": 0.6},
    'COMBO_MASTER': {"frieza": 0.4, "skill_uso": 0.5},
    'SNIPER': {"agressao": -0.2, "cautela": 0.5, "skill_uso": 0.4},
    'CLOSE_RANGE': {"agressao": 0.4, "cautela": -0.4},
    'AREA_DENIAL': {"cautela": 0.3, "skill_uso": 0.5},
    'DEBUFFER': {"skill_uso": 0.5},
    'SUPPORT': {"agressao": -0.3, "skill_uso": 0.5},
    'SETUP_ARTIST': {"frieza": 0.4, "skill_uso": 0.4},
    'ZONE_CONTROLLER': {"cautela": 0.4, "skill_uso": 0.5},
    'TECNICO': {"frieza": 0.5, "skill_uso": 0.3},
    'DESPERDICADOR': {"frieza": -0.4, "skill_uso": 0.7},
    'CANALIZADOR': {"cautela": 0.2, "skill_uso": 0.5},
    'INSTANT_CAST': {"mobilidade": 0.2, "skill_uso": 0.5},
    'CHAIN_CASTER': {"skill_uso": 0.7},
    'FINISHER': {"perseguicao": 0.5, "skill_uso": 0.4},
    'OPENER': {"agressao": 0.4, "skill_uso": 0.4},
    'MANA_BURNER': {"skill_uso": 0.8},
    'COOLDOWN_WATCHER': {"frieza": 0.5, "skill_uso": 0.3},
    'SKILL_BAITER': {"frieza": 0.4, "caos": 0.3},
    'CANCELADOR': {"frieza": 0.4, "mobilidade": 0.3},
    'ZONER': {"agressao": -0.2, "cautela": 0.5, "skill_uso": 0.4},
    # --- TRACOS_MENTAL ---
    'VINGATIVO': {"agressao": 0.5, "frieza": -0.4, "perseguicao": 0.4},
    'DETERMINADO': {"medo": -0.4, "frieza": 0.7},
    'ADAPTAVEL': {"frieza": 0.4, "caos": 0.2},
    'FRIO': {"frieza": 0.8},
    'EMOTIVO': {"frieza": -0.6},
    'FOCADO': {"frieza": 0.6, "caos": -0.4},
    'DISPERSO': {"frieza": -0.4, "caos": 0.4},
    'TEIMOSO': {"frieza": 0.3, "caos": -0.5},
    'CRIATIVO': {"caos": 0.5, "mobilidade": 0.3},
    'METODICO': {"frieza": 0.6, "caos": -0.5},
    'CLUTCH_PLAYER': {"medo": -0.5, "frieza": 0.5},
    'TILTER': {"agressao": 0.3, "frieza": -0.7},
    'AWARENESS_ALTO': {"cautela": 0.4, "frieza": 0.4},
    'PSICOPATA': {"agressao": 0.4, "medo": -0.6, "frieza": 0.6},
    'ANALITICO': {"cautela": 0.3, "frieza": 0.6},
    'INSTINTIVO': {"frieza": -0.2, "caos": 0.4},
    'CEREBRAL': {"cautela": 0.3, "frieza": 0.6},
    'IMPULSIVO': {"agressao": 0.4, "frieza": -0.5, "caos": 0.5},
    'RESILIENTE_MENTAL': {"medo": -0.4, "frieza": 0.6},
    'TRAUMATIZADO': {"medo": 0.6, "frieza": -0.4},
    'CONFIANTE': {"agressao": 0.3, "medo": -0.5},
    'INSEGURO': {"agressao": -0.3, "medo": 0.5},
    'ZEN': {"frieza": 0.8, "caos": -0.3},
    'CAOS_MENTAL': {"frieza": -0.5, "caos": 0.7},
    'PREDITOR': {"cautela": 0.4, "frieza": 0.5},
    'REATIVO_MENTAL': {"cautela": 0.3, "frieza": 0.3},
    'OBSESSIVO': {"frieza": -0.2, "perseguicao": 0.6},
    # --- TRACOS_ESPECIAIS ---
    'SHOWMAN': {"agressao": 0.3, "caos": 0.4},
    'ASSASSINO_NATO': {"agressao": 0.5, "mobilidade": 0.3, "perseguicao": 0.5},
    'BERSERKER_RAGE': {"agressao": 0.9, "cautela": -0.6, "frieza": -0.4},
    'PHOENIX': {"medo": -0.5, "frieza": 0.4},
    'VAMPIRO': {"agressao": 0.5, "perseguicao": 0.3},
    'KAMIKAZE': {"agressao": 0.9, "cautela": -0.8, "medo": -0.7},
    'TRICKSTER': {"caos": 0.6, "mobilidade": 0.4},
    'HONORAVEL': {"frieza": 0.4, "caos": -0.4},
    'COVARDE_TATICO': {"cautela": 0.6, "medo": 0.5, "frieza": 0.3},
    'ULTIMO_SUSPIRO': {"agressao": 0.4, "medo": -0.4},
    'MOMENTUM_RIDER': {"agressao": 0.3, "frieza": -0.3},
    'UNDERDOG': {"medo": -0.3, "frieza": 0.4},
    'BAITER_NATO': {"frieza": 0.5, "caos": 0.3},
    'WALL_FIGHTER': {"cautela": 0.4, "mobilidade": -0.2},
    'PILLAR_DANCER': {"cautela": 0.3, "mobilidade": 0.6},
    'METAMORFO': {"caos": 0.5, "mobilidade": 0.3},
    'DUPLA_PERSONALIDADE': {"frieza": -0.4, "caos": 0.7},
    'GLUTTON': {"agressao": 0.4, "skill_uso": 0.4},
    'PERFECCIONISTA': {"frieza": 0.6, "caos": -0.4},
    'STYLIST': {"caos": 0.4, "mobilidade": 0.4},
    'EFICIENTE': {"frieza": 0.5, "skill_uso": -0.3},
    'CAÇADOR_GLORIA': {"agressao": 0.5, "medo": -0.3, "perseguicao": 0.4},
    'MINIMALISTA': {"frieza": 0.4, "skill_uso": -0.5},
    'MAXIMALISTA': {"agressao": 0.3, "skill_uso": 0.7},
    'SÁDICO': {"agressao": 0.5, "perseguicao": 0.5},
    'MASOQUISTA': {"cautela": -0.4, "medo": -0.6},
    'APOSTADOR': {"cautela": -0.4, "caos": 0.6},
    'SEGURO': {"cautela": 0.6, "caos": -0.4},
    'LENDARIO': {"medo": -0.4, "frieza": 0.5},
    'PRÁTICO': {"frieza": 0.5, "caos": -0.3},
    'ARTISTA_MARCIAL': {"frieza": 0.5, "mobilidade": 0.4},
    'GLADIADOR': {"agressao": 0.5, "caos": 0.3},
    'SAMURAI': {"frieza": 0.7, "caos": -0.4},
    'VIKING': {"agressao": 0.7, "medo": -0.4},
    'NINJA_MENTAL': {"frieza": 0.5, "caos": 0.3, "mobilidade": 0.5},
}


def perfil_de_tracos(tracos):
    """Soma as contribuições dos traços e limita cada eixo a [-1, 1].

    Traço desconhecido é ignorado em silêncio: o perfil é consultado no caminho
    quente do combate, e uma personalidade malformada não pode derrubar a luta.
    A auditoria de catálogo é quem recusa traço sem eixo, fora do runtime.
    """
    perfil = dict.fromkeys(EIXOS_COMPORTAMENTO, 0.0)
    for traco in tracos or ():
        for eixo, valor in TRACO_EIXOS.get(traco, {}).items():
            perfil[eixo] += valor
    return {eixo: max(-1.0, min(1.0, valor)) for eixo, valor in perfil.items()}


# =============================================================================
# ARQUÉTIPOS DE COMBATE (35+)
# =============================================================================

ARQUETIPO_DATA = {
    # === MAGOS === (Mágica: range_mult 2.5, mas ficam mais longe)
    "MAGO": {"alcance": 2.5, "estilo": "RANGED", "agressividade": 0.3},
    "MAGO_AGRESSIVO": {"alcance": 2.0, "estilo": "RANGED", "agressividade": 0.7},
    "MAGO_CONTROLE": {"alcance": 2.5, "estilo": "RANGED", "agressividade": 0.4},
    "INVOCADOR": {"alcance": 2.5, "estilo": "SUMMON", "agressividade": 0.3},
    "PIROMANTE": {"alcance": 2.0, "estilo": "BURST", "agressividade": 0.8},
    "CRIOMANTE": {"alcance": 2.5, "estilo": "CONTROL", "agressividade": 0.4},
    "ELETROMANTE": {"alcance": 2.2, "estilo": "COMBO", "agressividade": 0.6},
    "NECROMANTE": {"alcance": 2.5, "estilo": "DRAIN", "agressividade": 0.5},
    "ARCANO": {"alcance": 2.5, "estilo": "CHAOS_MAGIC", "agressividade": 0.6},
    
    # === ASSASSINOS === (Dupla: range_mult 1.5)
    "ASSASSINO": {"alcance": 1.5, "estilo": "BURST", "agressividade": 0.8},
    "NINJA": {"alcance": 1.5, "estilo": "HIT_RUN", "agressividade": 0.7},
    "LADINO": {"alcance": 1.5, "estilo": "OPPORTUNIST", "agressividade": 0.6},
    "SOMBRA": {"alcance": 1.5, "estilo": "AMBUSH", "agressividade": 0.9},
    "SICARIO": {"alcance": 1.5, "estilo": "EXECUTE", "agressividade": 0.85},
    "PHANTOM": {"alcance": 1.5, "estilo": "GHOST", "agressividade": 0.7},
    
    # === GUERREIROS === (Reta: range_mult 2.0)
    "GUERREIRO": {"alcance": 2.0, "estilo": "BALANCED", "agressividade": 0.5},
    "GUERREIRO_PESADO": {"alcance": 2.0, "estilo": "TANK", "agressividade": 0.4},
    "BERSERKER": {"alcance": 1.8, "estilo": "BERSERK", "agressividade": 0.9},
    "DUELISTA": {"alcance": 1.5, "estilo": "COUNTER", "agressividade": 0.5},
    "GLADIADOR": {"alcance": 2.0, "estilo": "SHOWMAN", "agressividade": 0.6},
    "ESPARTANO": {"alcance": 2.0, "estilo": "PHALANX", "agressividade": 0.55},
    "VIKING": {"alcance": 2.0, "estilo": "RAIDER", "agressividade": 0.85},
    "CONQUISTADOR": {"alcance": 2.0, "estilo": "CONQUEROR", "agressividade": 0.75},
    
    # === DEFENSIVOS === (Orbital: range_mult 1.5)
    "SENTINELA": {"alcance": 1.5, "estilo": "TANK", "agressividade": 0.3},
    "PALADINO": {"alcance": 2.0, "estilo": "BALANCED", "agressividade": 0.4},
    "COLOSSO": {"alcance": 2.0, "estilo": "TANK", "agressividade": 0.5},
    "GUARDIAO": {"alcance": 1.5, "estilo": "DEFENSIVE", "agressividade": 0.2},
    "MURALHA": {"alcance": 1.5, "estilo": "FORTRESS", "agressividade": 0.25},
    "TEMPLARIO": {"alcance": 2.0, "estilo": "HOLY_WARRIOR", "agressividade": 0.45},
    
    # === HÍBRIDOS ===
    "LANCEIRO": {"alcance": 5.0, "estilo": "POKE", "agressividade": 0.5},  # Arremesso: 5.0
    "ARQUEIRO": {"alcance": 8.0, "estilo": "KITE", "agressividade": 0.4},  # Arco: 8.0
    "ACROBATA": {"alcance": 2.5, "estilo": "MOBILE", "agressividade": 0.6},  # Corrente: ponto médio de 4.0
    "MONGE": {"alcance": 1.5, "estilo": "COMBO", "agressividade": 0.6},
    "DRUIDA": {"alcance": 2.5, "estilo": "ADAPTIVE", "agressividade": 0.4},
    "SAMURAI": {"alcance": 2.0, "estilo": "IAIDO", "agressividade": 0.5},
    "RONIN": {"alcance": 2.0, "estilo": "AGGRO", "agressividade": 0.7},
    "CAPOEIRISTA": {"alcance": 1.5, "estilo": "GINGA", "agressividade": 0.65},
    "PUGILISTA": {"alcance": 1.5, "estilo": "BOXER", "agressividade": 0.7},
    "PREDADOR": {"alcance": 2.5, "estilo": "HUNTER", "agressividade": 0.75},
}


# =============================================================================
# ESTILOS DE LUTA (25+)
# =============================================================================

ESTILOS_LUTA = {
    # === ESTILOS AGRESSIVOS ===
    "RANGED": {
        "descricao": "Mantém distância, dispara projéteis",
        "acao_perto": "RECUAR",
        "acao_longe": "PRESSIONAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.5,
    },
    "BURST": {
        "descricao": "Salva recursos para dano explosivo",
        "acao_perto": "MATAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.7,
    },
    "TANK": {
        "descricao": "Absorve dano, avança constantemente",
        "acao_perto": "COMBATE",
        "acao_longe": "APROXIMAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.6,
    },
    "HIT_RUN": {
        "descricao": "Ataca e recua rapidamente",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "APROXIMAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.7,
    },
    "BERSERK": {
        "descricao": "Ataque constante sem defesa",
        "acao_perto": "MATAR",
        "acao_longe": "MATAR",
        "acao_medio": "MATAR",
        "agressividade_base": 1.0,
    },
    "COUNTER": {
        "descricao": "Espera e contra-ataca agressivamente",
        "acao_perto": "CONTRA_ATAQUE",
        "acao_longe": "APROXIMAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.55,
    },
    "POKE": {
        "descricao": "Ataques rápidos de média distância",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "APROXIMAR",
        "acao_medio": "POKE",
        "agressividade_base": 0.65,
    },
    "KITE": {
        "descricao": "Mantém distância enquanto ataca",
        "acao_perto": "RECUAR",  # Arqueiros recuam quando inimigo chega perto
        "acao_longe": "PRESSIONAR",  # Ataca de longe
        "acao_medio": "PRESSIONAR",  # Continua atacando em média distância
        "agressividade_base": 0.6,
    },
    "MOBILE": {
        "descricao": "Movimento constante e agressivo",
        "acao_perto": "FLANQUEAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.75,
    },
    "COMBO": {
        "descricao": "Encadeia ataques",
        "acao_perto": "MATAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "MATAR",
        "agressividade_base": 0.85,
    },
    "OPPORTUNIST": {
        "descricao": "Ataca em toda abertura",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "APROXIMAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.65,
    },
    "AMBUSH": {
        "descricao": "Espera pouco e ataca de surpresa",
        "acao_perto": "ESMAGAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.7,
    },
    "CONTROL": {
        "descricao": "Controla o espaço agressivamente",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "PRESSIONAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.6,
    },
    "DEFENSIVE": {
        "descricao": "Defensivo mas contra-ataca",
        "acao_perto": "CONTRA_ATAQUE",
        "acao_longe": "COMBATE",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.4,
    },
    "ADAPTIVE": {
        "descricao": "Muda baseado na situação",
        "acao_perto": "COMBATE",
        "acao_longe": "APROXIMAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.6,
    },
    "SHOWMAN": {
        "descricao": "Luta para impressionar",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "APROXIMAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.8,
    },
    "AGGRO": {
        "descricao": "Agressão constante",
        "acao_perto": "ESMAGAR",
        "acao_longe": "MATAR",
        "acao_medio": "MATAR",
        "agressividade_base": 0.95,
    },
    "SUMMON": {
        "descricao": "Posiciona enquanto invocações lutam",
        "acao_perto": "COMBATE",
        "acao_longe": "PRESSIONAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.45,
    },
    "BALANCED": {
        "descricao": "Equilíbrio com tendência agressiva",
        "acao_perto": "COMBATE",
        "acao_longe": "APROXIMAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.65,
    },
    # === NOVOS ESTILOS v11.0 ===
    "EXECUTE": {
        "descricao": "Especialista em finalizar oponentes",
        "acao_perto": "ESMAGAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.8,
    },
    "GHOST": {
        "descricao": "Aparece e desaparece, difícil de rastrear",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "CIRCULAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.6,
    },
    "DRAIN": {
        "descricao": "Suga a vida do oponente lentamente",
        "acao_perto": "COMBATE",
        "acao_longe": "APROXIMAR",
        "acao_medio": "POKE",
        "agressividade_base": 0.55,
    },
    "CHAOS_MAGIC": {
        "descricao": "Imprevisível, muda de tática constantemente",
        "acao_perto": "MATAR",
        "acao_longe": "PRESSIONAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.7,
    },
    "PHALANX": {
        "descricao": "Avança lentamente mas implacavelmente",
        "acao_perto": "ESMAGAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "APROXIMAR",
        "agressividade_base": 0.6,
    },
    "RAIDER": {
        "descricao": "Ataques devastadores e rápidos",
        "acao_perto": "ESMAGAR",
        "acao_longe": "MATAR",
        "acao_medio": "MATAR",
        "agressividade_base": 0.9,
    },
    "CONQUEROR": {
        "descricao": "Domina o espaço e esmaga resistência",
        "acao_perto": "ESMAGAR",
        "acao_longe": "PRESSIONAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.8,
    },
    "FORTRESS": {
        "descricao": "Imóvel como fortaleza, contra-ataca",
        "acao_perto": "CONTRA_ATAQUE",
        "acao_longe": "COMBATE",
        "acao_medio": "CONTRA_ATAQUE",
        "agressividade_base": 0.35,
    },
    "HOLY_WARRIOR": {
        "descricao": "Justiça divina, ataques poderosos",
        "acao_perto": "MATAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.6,
    },
    "IAIDO": {
        "descricao": "Um corte perfeito, espera o momento",
        "acao_perto": "ESMAGAR",
        "acao_longe": "COMBATE",
        "acao_medio": "CONTRA_ATAQUE",
        "agressividade_base": 0.5,
    },
    "GINGA": {
        "descricao": "Dança constante, ataques de todos ângulos",
        "acao_perto": "FLANQUEAR",
        "acao_longe": "CIRCULAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.7,
    },
    "BOXER": {
        "descricao": "Jabs rápidos, esquiva, gancho devastador",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "APROXIMAR",
        "acao_medio": "POKE",
        "agressividade_base": 0.75,
    },
    "HUNTER": {
        "descricao": "Rastrea, encurrala, elimina",
        "acao_perto": "MATAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.8,
    },
    "BERSERKER_RAGE": {
        "descricao": "Fúria total, ignora dor",
        "acao_perto": "ESMAGAR",
        "acao_longe": "MATAR",
        "acao_medio": "MATAR",
        "agressividade_base": 1.0,
    },
    "MATADOR": {
        "descricao": "Elegância letal, golpes precisos",
        "acao_perto": "ATAQUE_RAPIDO",
        "acao_longe": "CIRCULAR",
        "acao_medio": "FLANQUEAR",
        "agressividade_base": 0.65,
    },
    "PREDATOR": {
        "descricao": "Caça a presa, não deixa escapar",
        "acao_perto": "MATAR",
        "acao_longe": "APROXIMAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.85,
    },
    "TACTICIAN": {
        "descricao": "Cada movimento é calculado",
        "acao_perto": "CONTRA_ATAQUE",
        "acao_longe": "COMBATE",
        "acao_medio": "COMBATE",
        "agressividade_base": 0.5,
    },
    "PRESSURE": {
        "descricao": "Pressão constante e sufocante",
        "acao_perto": "PRESSIONAR",
        "acao_longe": "PRESSIONAR",
        "acao_medio": "PRESSIONAR",
        "agressividade_base": 0.85,
    },
}


# =============================================================================
# QUIRKS (20+)
# =============================================================================

QUIRKS = {
    "GRITO_GUERRA": {
        "descricao": "Grita antes de atacar",
        "trigger": "pre_ataque",
        "efeito": "buff_dano_temporario",
    },
    "DANCA_MORTE": {
        "descricao": "Gira ao redor do inimigo",
        "trigger": "combate_longo",
        "efeito": "circular_rapido",
    },
    "OLHO_VERMELHO": {
        "descricao": "Fica mais forte com raiva",
        "trigger": "raiva_alta",
        "efeito": "buff_velocidade",
    },
    "SEGUNDO_FOLEGO": {
        "descricao": "Recupera energia com HP crítico",
        "trigger": "hp_critico",
        "efeito": "regen_stamina",
    },
    "SEDE_SANGUE": {
        "descricao": "Fica mais rápido após matar",
        "trigger": "kill",
        "efeito": "buff_velocidade",
    },
    "PROVOCADOR": {
        "descricao": "Para para provocar o inimigo",
        "trigger": "random",
        "efeito": "pausa_dramatica",
    },
    "FINALIZADOR": {
        "descricao": "Ataque especial quando inimigo está fraco",
        "trigger": "inimigo_fraco",
        "efeito": "burst_damage",
    },
    "ESQUIVA_REFLEXA": {
        "descricao": "Pula automaticamente quando atacado",
        "trigger": "tomando_dano",
        "efeito": "auto_jump",
    },
    "FURIA_CEGA": {
        "descricao": "Ignora tudo quando com raiva",
        "trigger": "raiva_maxima",
        "efeito": "ignore_defense",
    },
    "PERSISTENTE": {
        "descricao": "Continua atacando mesmo atordoado",
        "trigger": "stunned",
        "efeito": "resist_stun",
    },
    "CALCULISTA_FRIO": {
        "descricao": "Fica mais preciso com o tempo",
        "trigger": "combate_longo",
        "efeito": "buff_precisao",
    },
    "EXPLOSAO_FINAL": {
        "descricao": "Usa todas skills antes de morrer",
        "trigger": "pre_morte",
        "efeito": "spam_skills",
    },
    "CONTRA_ATAQUE_PERFEITO": {
        "descricao": "Contra-ataque devastador",
        "trigger": "esquiva_sucesso",
        "efeito": "counter_damage",
    },
    "AURA_INTIMIDANTE": {
        "descricao": "Inimigo fica mais cauteloso",
        "trigger": "sempre",
        "efeito": "debuff_inimigo",
    },
    "REGENERADOR": {
        "descricao": "Regenera HP lentamente",
        "trigger": "sempre",
        "efeito": "regen_hp",
    },
    "VAMPIRICO": {
        "descricao": "Rouba vida com ataques",
        "trigger": "hit_sucesso",
        "efeito": "lifesteal",
    },
    "ESPELHO": {
        "descricao": "Copia movimentos do inimigo",
        "trigger": "sempre",
        "efeito": "mirror_behavior",
    },
    "MESTRE_COMBO": {
        "descricao": "Combos mais longos e rápidos",
        "trigger": "combo_ativo",
        "efeito": "extended_combo",
    },
    "INSTINTO_ANIMAL": {
        "descricao": "Reage instantaneamente a perigo",
        "trigger": "perigo",
        "efeito": "instant_react",
    },
    "PACIENCIA_INFINITA": {
        "descricao": "Espera o momento perfeito",
        "trigger": "sempre",
        "efeito": "perfect_timing",
    },
    # === NOVOS QUIRKS v8.0 (Comportamento Humano) ===
    "ADAPTACAO_RAPIDA": {
        "descricao": "Aprende padrões do oponente rapidamente",
        "trigger": "sempre",
        "efeito": "leitura_melhorada",
    },
    "CLUTCH_MASTER": {
        "descricao": "Extremamente perigoso quando em desvantagem",
        "trigger": "hp_baixo",
        "efeito": "buff_geral_critico",
    },
    "TILT_REVERSAL": {
        "descricao": "Usa frustração como combustível",
        "trigger": "frustrado",
        "efeito": "raiva_para_poder",
    },
    "MOMENTUM_SURFER": {
        "descricao": "Aproveita momentum positivo ao máximo",
        "trigger": "ganhando",
        "efeito": "buff_agressividade",
    },
    "MIND_GAMES": {
        "descricao": "Mestre em jogos mentais e fintas",
        "trigger": "combate_medio",
        "efeito": "baiting_melhorado",
    },
    "RESET_MASTER": {
        "descricao": "Sabe quando recuar e resetar a situação",
        "trigger": "pressao_alta",
        "efeito": "escape_melhorado",
    },
    "WHIFF_PUNISHER": {
        "descricao": "Pune ataques errados do oponente",
        "trigger": "oponente_whiff",
        "efeito": "contra_ataque_rapido",
    },
    "SPACE_CONTROL": {
        "descricao": "Controla o espaço de luta perfeitamente",
        "trigger": "sempre",
        "efeito": "posicionamento_ideal",
    },
    "FRAME_PERFECT": {
        "descricao": "Timing de ações quase perfeito",
        "trigger": "sempre",
        "efeito": "timing_melhorado",
    },
    "OPTION_SELECT": {
        "descricao": "Escolhe a melhor opção baseado na reação do oponente",
        "trigger": "pre_acao",
        "efeito": "decisao_adaptativa",
    },
    # === NOVOS QUIRKS v11.0 ===
    "SOMBRA_MORTAL": {
        "descricao": "Ataques por trás causam dano dobrado",
        "trigger": "ataque_traseiro",
        "efeito": "backstab_bonus",
    },
    "ADRENALINE_JUNKIE": {
        "descricao": "Quanto mais caótica a luta, melhor",
        "trigger": "combate_intenso",
        "efeito": "buff_caos",
    },
    "CALCULO_MORTAL": {
        "descricao": "Sabe exatamente quanto dano falta para matar",
        "trigger": "sempre",
        "efeito": "execute_threshold",
    },
    "ZONE_MASTER": {
        "descricao": "Controla áreas específicas da arena",
        "trigger": "posicao_estrategica",
        "efeito": "buff_zona",
    },
    "DESESPERO_LETAL": {
        "descricao": "Último HP desbloqueia poder oculto",
        "trigger": "hp_minimo",
        "efeito": "last_stand",
    },
    "RESPIRO_TATICO": {
        "descricao": "Pequenas pausas para recuperar",
        "trigger": "stamina_baixa",
        "efeito": "micro_regen",
    },
    "OLHOS_DE_AGUIA": {
        "descricao": "Detecta fraquezas no oponente",
        "trigger": "observacao",
        "efeito": "weakness_scan",
    },
    "REFLEXOS_DIVINOS": {
        "descricao": "Reação sobre-humana a ataques",
        "trigger": "ataque_iminente",
        "efeito": "perfect_dodge",
    },
    "PROVOCADOR_NATO": {
        "descricao": "Provoca o oponente para errar",
        "trigger": "vantagem",
        "efeito": "taunt_debuff",
    },
    "ACUMULADOR": {
        "descricao": "Acumula poder para um golpe devastador",
        "trigger": "sem_ataque_recente",
        "efeito": "charged_attack",
    },
    "CAÇADOR_FERIDAS": {
        "descricao": "Mira em partes já feridas",
        "trigger": "dano_anterior",
        "efeito": "wound_focus",
    },
    "PERFECCIONISTA_COMBO": {
        "descricao": "Combos aumentam de poder",
        "trigger": "combo_longo",
        "efeito": "combo_scaling",
    },
    "IMORTAL": {
        "descricao": "Sobrevive a golpes fatais uma vez",
        "trigger": "golpe_fatal",
        "efeito": "death_deny",
    },
    "ECO_GUERRA": {
        "descricao": "Repete o último golpe que acertou",
        "trigger": "hit_sucesso",
        "efeito": "echo_attack",
    },
    "MESTRE_DISTANCIA": {
        "descricao": "Sempre na distância ideal",
        "trigger": "sempre",
        "efeito": "perfect_spacing",
    },
    "BURST_MODE": {
        "descricao": "Explosões periódicas de velocidade",
        "trigger": "tempo_combate",
        "efeito": "speed_burst",
    },
    "LEITURA_CORPORAL": {
        "descricao": "Lê intenções pelo movimento",
        "trigger": "observacao",
        "efeito": "intent_read",
    },
    "CONTRA_MOMENTUM": {
        "descricao": "Mais forte quando perdendo momentum",
        "trigger": "momentum_negativo",
        "efeito": "reversal_power",
    },
    "EXECUTION_INSTINCT": {
        "descricao": "Sabe o momento exato de finalizar",
        "trigger": "inimigo_vulneravel",
        "efeito": "execute_trigger",
    },
    "TACTICAL_RETREAT": {
        "descricao": "Recuos estratégicos que preparam ataques",
        "trigger": "recuo",
        "efeito": "retreat_buff",
    },
    "BERSERKER_SOUL": {
        "descricao": "Quanto mais ferido, mais perigoso",
        "trigger": "hp_perdido",
        "efeito": "damage_scaling",
    },
    "GRAVIDADE_PROPRIA": {
        "descricao": "Atrai o oponente para perto",
        "trigger": "distancia_media",
        "efeito": "pull_effect",
    },
    "REPULSOR": {
        "descricao": "Empurra oponentes para longe",
        "trigger": "distancia_curta",
        "efeito": "push_effect",
    },
}


# =============================================================================
# FILOSOFIAS DE COMBATE (12+)
# =============================================================================

FILOSOFIAS = {
    "DOMINACAO": {
        "objetivo": "Controlar a luta completamente",
        "preferencia_acao": ["ESMAGAR", "MATAR", "PRESSIONAR"],
        "mod_agressividade": 0.4,
    },
    "SOBREVIVENCIA": {
        "objetivo": "Sobreviver mas contra-atacar",
        "preferencia_acao": ["CONTRA_ATAQUE", "COMBATE", "RECUAR"],
        "mod_agressividade": -0.1,
    },
    "EQUILIBRIO": {
        "objetivo": "Balancear com foco em ataque",
        "preferencia_acao": ["COMBATE", "MATAR", "FLANQUEAR"],
        "mod_agressividade": 0.1,
    },
    "OPORTUNISMO": {
        "objetivo": "Explorar fraquezas do inimigo",
        "preferencia_acao": ["MATAR", "FLANQUEAR", "ATAQUE_RAPIDO"],
        "mod_agressividade": 0.2,
    },
    "PRESSAO": {
        "objetivo": "Pressionar constantemente",
        "preferencia_acao": ["PRESSIONAR", "MATAR", "ESMAGAR"],
        "mod_agressividade": 0.35,
    },
    "PACIENCIA": {
        "objetivo": "Esperar e então atacar",
        "preferencia_acao": ["COMBATE", "CONTRA_ATAQUE", "FLANQUEAR"],
        "mod_agressividade": 0.0,
    },
    "CAOS": {
        "objetivo": "Ser imprevisível e agressivo",
        "preferencia_acao": ["MATAR", "FLANQUEAR", "ATAQUE_RAPIDO"],
        "mod_agressividade": 0.25,
    },
    "HONRA": {
        "objetivo": "Lutar com honra - combate direto",
        "preferencia_acao": ["COMBATE", "MATAR", "APROXIMAR"],
        "mod_agressividade": 0.15,
    },
    "EXECUCAO": {
        "objetivo": "Terminar rápido",
        "preferencia_acao": ["MATAR", "ESMAGAR", "PRESSIONAR"],
        "mod_agressividade": 0.4,
    },
    "RESISTENCIA": {
        "objetivo": "Vencer por attrition - atacando",
        "preferencia_acao": ["COMBATE", "CONTRA_ATAQUE", "POKE"],
        "mod_agressividade": 0.0,
    },
    "ESPETACULO": {
        "objetivo": "Dar um show agressivo",
        "preferencia_acao": ["FLANQUEAR", "MATAR", "ATAQUE_RAPIDO"],
        "mod_agressividade": 0.2,
    },
    "ADAPTACAO": {
        "objetivo": "Mudar conforme necessário",
        "preferencia_acao": ["COMBATE", "MATAR", "FLANQUEAR"],
        "mod_agressividade": 0.1,
    },
    "LEITURA": {
        "objetivo": "Ler e punir o oponente",
        "preferencia_acao": ["CONTRA_ATAQUE", "CIRCULAR", "COMBATE"],
        "mod_agressividade": 0.05,
    },
    "MOMENTUM": {
        "objetivo": "Construir e manter momentum",
        "preferencia_acao": ["PRESSIONAR", "MATAR", "APROXIMAR"],
        "mod_agressividade": 0.25,
    },
    # === NOVAS FILOSOFIAS v11.0 ===
    "ANIQUILACAO": {
        "objetivo": "Destruição total do oponente",
        "preferencia_acao": ["ESMAGAR", "MATAR", "MATAR"],
        "mod_agressividade": 0.5,
    },
    "ARTE_GUERRA": {
        "objetivo": "Vencer sem lutar - eficiência máxima",
        "preferencia_acao": ["COMBATE", "CONTRA_ATAQUE", "PRESSIONAR"],
        "mod_agressividade": 0.15,
    },
    "PREDACAO": {
        "objetivo": "Caçar como predador - sem escapatória",
        "preferencia_acao": ["APROXIMAR", "PRESSIONAR", "MATAR"],
        "mod_agressividade": 0.35,
    },
    "CONTROLE_TOTAL": {
        "objetivo": "Ditar cada momento da luta",
        "preferencia_acao": ["PRESSIONAR", "COMBATE", "CIRCULAR"],
        "mod_agressividade": 0.2,
    },
    "SACRIFICIO": {
        "objetivo": "Trocar dano por dano maior",
        "preferencia_acao": ["MATAR", "ESMAGAR", "MATAR"],
        "mod_agressividade": 0.45,
    },
    "EROSAO": {
        "objetivo": "Desgastar lentamente até a vitória",
        "preferencia_acao": ["POKE", "COMBATE", "CIRCULAR"],
        "mod_agressividade": 0.1,
    },
    "EXPLOSAO": {
        "objetivo": "Um único momento devastador",
        "preferencia_acao": ["COMBATE", "COMBATE", "ESMAGAR"],
        "mod_agressividade": 0.3,
    },
    "TORMENTO": {
        "objetivo": "Torturar antes de finalizar",
        "preferencia_acao": ["POKE", "FLANQUEAR", "PRESSIONAR"],
        "mod_agressividade": 0.25,
    },
}


# =============================================================================
# HUMORES DINÂMICOS (15)
# =============================================================================

HUMORES = {
    "CONFIANTE": {"mod_agressividade": 0.2, "mod_defesa": -0.1},
    "NERVOSO": {"mod_agressividade": -0.1, "mod_defesa": 0.1},
    "FURIOSO": {"mod_agressividade": 0.4, "mod_defesa": -0.2},
    "CALMO": {"mod_agressividade": 0.0, "mod_defesa": 0.0},
    "DESESPERADO": {"mod_agressividade": 0.3, "mod_defesa": -0.3},
    "FOCADO": {"mod_agressividade": 0.1, "mod_defesa": 0.1},
    "ENTEDIADO": {"mod_agressividade": -0.2, "mod_defesa": -0.1},
    "ANIMADO": {"mod_agressividade": 0.15, "mod_defesa": 0.0},
    "ASSUSTADO": {"mod_agressividade": -0.3, "mod_defesa": 0.2},
    "DETERMINADO": {"mod_agressividade": 0.1, "mod_defesa": 0.15},
    # === NOVOS HUMORES v11.0 ===
    "EUFORICO": {"mod_agressividade": 0.35, "mod_defesa": -0.15},
    "MELANCOLICO": {"mod_agressividade": -0.15, "mod_defesa": 0.05},
    "EXTASE": {"mod_agressividade": 0.5, "mod_defesa": -0.3},
    "GLACIAL": {"mod_agressividade": 0.05, "mod_defesa": 0.2},
    "BERSERK": {"mod_agressividade": 0.6, "mod_defesa": -0.4},
}


# =============================================================================
# NOVO SISTEMA: INSTINTOS DE COMBATE (Reações Automáticas)
# =============================================================================

INSTINTOS = {
    # Onda 5D: TODO trigger e TODA acao referenciam sinais/verbos REAIS do
    # runtime (a auditoria AST cobra isso nos dois sentidos). Antes, 8/15
    # instintos apontavam para coisas inexistentes (ataque_baixo/alto num
    # jogo top-down, p.iniciar_dash/p.pular que nunca existiram,
    # combo_state["sendo_combo"] com a chave errada).
    #
    # prioridade: 1 = reflexo de sobrevivência (interrompe qualquer hold),
    # 2 = punição/oportunidade, 3 = postura. cooldown em segundos — sem
    # ele, condições de NÍVEL (hp_baixo é verdadeiro por metade da luta)
    # monopolizavam o loop: RECUAR era 98,7% dos disparos.
    "ESQUIVA_SOMBRA": {
        "descricao": "Esquiva reflexa de ataque vindo das costas",
        "trigger": "ataque_traseiro",
        "chance": 0.7,
        "acao": "dodge_back",
        "prioridade": 1,
        "cooldown": 2.5,
    },
    "CONTRA_REFLEXO": {
        "descricao": "Contra-ataca logo após absorver um golpe na guarda",
        "trigger": "bloqueio_sucesso",
        "chance": 0.6,
        "acao": "instant_counter",
        "prioridade": 2,
        "cooldown": 3.0,
    },
    "PULO_PERIGO": {
        "descricao": "Esquiva reflexa de projétil vindo (era 'pulo', que não existe no motor)",
        "trigger": "projetil_vindo",
        "chance": 0.65,
        "acao": "dodge_projetil",
        "prioridade": 1,
        "cooldown": 2.0,
    },
    "AGACHAR_REFLEXO": {
        "descricao": "Fecha a guarda quando o ataque inimigo é iminente e perto",
        "trigger": "ataque_iminente_perto",
        "chance": 0.6,
        "acao": "guarda_reflexa",
        "prioridade": 1,
        "cooldown": 2.5,
    },
    "DASH_PANICO": {
        "descricao": "Fuga desesperada quando HP crítico",
        "trigger": "hp_critico",
        "chance": 0.8,
        "acao": "panic_dash",
        "prioridade": 1,
        "cooldown": 5.0,
    },
    "FURIA_INSTANTANEA": {
        "descricao": "Entra em fúria ao levar muito dano de uma vez",
        "trigger": "dano_alto",
        "chance": 0.5,
        "acao": "rage_trigger",
        "prioridade": 1,
        "cooldown": 4.0,
    },
    "PERSEGUICAO_AUTOMATICA": {
        "descricao": "Persegue automaticamente oponentes fugindo",
        "trigger": "oponente_recuando",
        "chance": 0.7,
        "acao": "auto_chase",
        "prioridade": 3,
        "cooldown": 3.0,
    },
    "DEFESA_FINAL": {
        "descricao": "Muda para modo defensivo com HP baixo",
        "trigger": "hp_baixo",
        "chance": 0.6,
        "acao": "defensive_mode",
        "prioridade": 2,
        "cooldown": 6.0,
    },
    "ATAQUE_OPORTUNIDADE": {
        "descricao": "Pune janelas reais (pós-ataque, recuperação, pós-esquiva)",
        "trigger": "janela_punicao",
        "chance": 0.75,
        "acao": "punish_attack",
        "prioridade": 2,
        "cooldown": 2.5,
    },
    "EVASAO_COMBO": {
        "descricao": "Tenta escapar quando está SENDO comboado",
        "trigger": "sendo_comboado",
        "chance": 0.4,
        "acao": "combo_break",
        "prioridade": 1,
        "cooldown": 3.0,
    },
    "INSTINTO_ASSASSINO": {
        "descricao": "Ataca agressivamente quando oponente está fraco",
        "trigger": "oponente_fraco",
        "chance": 0.85,
        "acao": "execute_mode",
        "prioridade": 2,
        "cooldown": 4.0,
    },
    "RECUO_ESTRATEGICO": {
        "descricao": "Recua automaticamente após receber combo",
        "trigger": "pos_combo",
        "chance": 0.7,
        "acao": "tactical_retreat",
        "prioridade": 2,
        "cooldown": 4.0,
    },
    "PRESSAO_INSTINTIVA": {
        "descricao": "Aumenta pressão quando ganhando",
        "trigger": "vantagem_hp",
        "chance": 0.65,
        "acao": "pressure_increase",
        "prioridade": 3,
        "cooldown": 5.0,
    },
    "ADAPTACAO_RAPIDA": {
        "descricao": "Muda tática após perder várias trocas",
        "trigger": "perdendo_trocas",
        "chance": 0.6,
        "acao": "style_switch",
        "prioridade": 3,
        "cooldown": 8.0,
    },
    "BLOQUEIO_INSTINTIVO": {
        "descricao": "Fecha a guarda contra oponente previsível",
        "trigger": "oponente_previsivel",
        "chance": 0.55,
        "acao": "auto_block",
        "prioridade": 2,
        "cooldown": 3.5,
    },
}


# =============================================================================
# NOVO SISTEMA: RITMOS DE BATALHA (Padrões Cíclicos)
# =============================================================================

RITMOS = {
    "ONDAS": {
        "descricao": "Alterna entre agressivo e passivo em ondas",
        "fases": ["AGRESSIVO", "PASSIVO", "AGRESSIVO", "PASSIVO"],
        "duracao_fase": 5.0,  # segundos
        "transicao": "suave",
    },
    "MAREMOTO": {
        "descricao": "Cresce lentamente até explodir",
        "fases": ["PASSIVO", "NEUTRO", "AGRESSIVO", "EXPLOSIVO"],
        "duracao_fase": 4.0,
        "transicao": "gradual",
    },
    "PULSO": {
        "descricao": "Bursts rápidos de agressividade",
        "fases": ["NEUTRO", "EXPLOSIVO", "NEUTRO", "EXPLOSIVO"],
        "duracao_fase": 2.5,
        "transicao": "abrupta",
    },
    "RESPIRACAO": {
        "descricao": "Inhala (passivo) e exhala (agressivo)",
        "fases": ["PASSIVO", "AGRESSIVO"],
        "duracao_fase": 6.0,
        "transicao": "suave",
    },
    "PREDADOR": {
        "descricao": "Observa, prepara, ataca, descansa",
        "fases": ["OBSERVAR", "PREPARAR", "ATACAR", "DESCANSAR"],
        "duracao_fase": 3.0,
        "transicao": "natural",
    },
    "TEMPESTADE": {
        "descricao": "Calmaria antes da tempestade",
        "fases": ["CALMO", "CALMO", "TEMPESTADE", "CALMO"],
        "duracao_fase": 4.0,
        "transicao": "explosiva",
    },
    "CONSTANTE": {
        "descricao": "Pressão constante sem variação",
        "fases": ["PRESSAO"],
        "duracao_fase": 999.0,
        "transicao": "nenhuma",
    },
    "CAOTICO": {
        "descricao": "Muda aleatoriamente sem padrão",
        "fases": ["ALEATORIO"],
        "duracao_fase": 2.0,
        "transicao": "caotica",
    },
    "ESCALADA": {
        "descricao": "Aumenta intensidade até o máximo",
        "fases": ["LEVE", "MEDIO", "FORTE", "MAXIMO"],
        "duracao_fase": 5.0,
        "transicao": "crescente",
    },
    "BERSERKER": {
        "descricao": "Começa controlado, termina em fúria",
        "fases": ["CALCULADO", "AGRESSIVO", "FURIOSO", "BERSERK"],
        "duracao_fase": 6.0,
        "transicao": "degenerativa",
    },
}

# Modificadores por fase do ritmo
RITMO_MODIFICADORES = {
    "PASSIVO": {"agressividade": -0.3, "defesa": 0.2, "mobilidade": -0.1},
    "NEUTRO": {"agressividade": 0.0, "defesa": 0.0, "mobilidade": 0.0},
    "AGRESSIVO": {"agressividade": 0.3, "defesa": -0.1, "mobilidade": 0.1},
    "EXPLOSIVO": {"agressividade": 0.5, "defesa": -0.3, "mobilidade": 0.2},
    "CALMO": {"agressividade": -0.2, "defesa": 0.1, "mobilidade": 0.0},
    "TEMPESTADE": {"agressividade": 0.6, "defesa": -0.2, "mobilidade": 0.3},
    "PRESSAO": {"agressividade": 0.25, "defesa": 0.0, "mobilidade": 0.1},
    "OBSERVAR": {"agressividade": -0.4, "defesa": 0.3, "mobilidade": -0.2},
    "PREPARAR": {"agressividade": 0.0, "defesa": 0.1, "mobilidade": 0.1},
    "ATACAR": {"agressividade": 0.4, "defesa": -0.2, "mobilidade": 0.2},
    "DESCANSAR": {"agressividade": -0.2, "defesa": 0.2, "mobilidade": -0.1},
    "LEVE": {"agressividade": 0.1, "defesa": 0.0, "mobilidade": 0.0},
    "MEDIO": {"agressividade": 0.25, "defesa": -0.1, "mobilidade": 0.1},
    "FORTE": {"agressividade": 0.4, "defesa": -0.15, "mobilidade": 0.15},
    "MAXIMO": {"agressividade": 0.6, "defesa": -0.25, "mobilidade": 0.25},
    "CALCULADO": {"agressividade": 0.1, "defesa": 0.15, "mobilidade": 0.05},
    "FURIOSO": {"agressividade": 0.5, "defesa": -0.2, "mobilidade": 0.2},
    "BERSERK": {"agressividade": 0.7, "defesa": -0.4, "mobilidade": 0.3},
    "ALEATORIO": {"agressividade": 0.0, "defesa": 0.0, "mobilidade": 0.0},  # Definido em runtime
}


# =============================================================================
# PRESETS DE PERSONALIDADE (para seleção pelo usuário)
# =============================================================================

PERSONALIDADES_PRESETS = {
    "Aleatório": {
        "descricao": "Personalidade gerada aleatoriamente a cada luta",
        "icone": "🎲",
        "cor": (150, 150, 150),
        "tracos_fixos": [],
        "estilo_fixo": None,
        "filosofia_fixa": None,
        "quirks_fixos": [],
        "agressividade_mod": 0.0,
    },
    "Agressivo": {
        "descricao": "Sempre ataca, nunca recua. Pressão constante.",
        "icone": "🔥",
        "cor": (255, 80, 80),
        "tracos_fixos": ["AGRESSIVO", "IMPLACAVEL", "PRESSAO_CONSTANTE", "FURIOSO"],
        "estilo_fixo": "AGGRO",
        "filosofia_fixa": "DOMINACAO",
        "quirks_fixos": ["GRITO_GUERRA", "FURIA_CEGA"],
        "agressividade_mod": 0.3,
    },
    "Defensivo": {
        "descricao": "Espera oportunidades, prioriza sobrevivência.",
        "icone": "🛡️",
        "cor": (80, 150, 255),
        "tracos_fixos": ["CAUTELOSO", "PACIENTE", "REATIVO", "TANQUE"],
        "estilo_fixo": "DEFENSIVE",
        "filosofia_fixa": "SOBREVIVENCIA",
        "quirks_fixos": ["CALCULISTA_FRIO", "CONTRA_ATAQUE_PERFEITO"],
        "agressividade_mod": -0.2,
    },
    "Berserker": {
        "descricao": "Fúria descontrolada. Mais forte quanto mais ferido.",
        "icone": "💀",
        "cor": (200, 50, 50),
        "tracos_fixos": ["BERSERKER", "SANGUINARIO", "BRUTAL", "BERSERKER_RAGE"],
        "estilo_fixo": "BERSERK",
        "filosofia_fixa": "EXECUCAO",
        "quirks_fixos": ["FURIA_CEGA", "SEGUNDO_FOLEGO"],
        "agressividade_mod": 0.4,
    },
    "Tático": {
        "descricao": "Analisa o oponente e explora fraquezas.",
        "icone": "🧠",
        "cor": (150, 100, 200),
        "tracos_fixos": ["CALCULISTA", "ADAPTAVEL", "OPORTUNISTA", "LEITURA_PERFEITA"],
        "estilo_fixo": "COUNTER",
        "filosofia_fixa": "LEITURA",
        "quirks_fixos": ["CALCULISTA_FRIO", "WHIFF_PUNISHER"],
        "agressividade_mod": 0.0,
    },
    "Assassino": {
        "descricao": "Ataca e recua. Golpes precisos e letais.",
        "icone": "🗡️",
        "cor": (100, 50, 150),
        "tracos_fixos": ["ASSASSINO_NATO", "FLANQUEADOR", "OPORTUNISTA", "FINALIZADOR_NATO"],
        "estilo_fixo": "HIT_RUN",
        "filosofia_fixa": "OPORTUNISMO",
        "quirks_fixos": ["FINALIZADOR", "SOMBRA_MORTAL"],
        "agressividade_mod": 0.1,
    },
    "Acrobático": {
        "descricao": "Movimento constante, difícil de acertar.",
        "icone": "🌀",
        "cor": (100, 200, 150),
        "tracos_fixos": ["SALTADOR", "ACROBATA", "ERRATICO", "VELOZ"],
        "estilo_fixo": "MOBILE",
        "filosofia_fixa": "CAOS",
        "quirks_fixos": ["ESQUIVA_REFLEXA", "DANCA_MORTE"],
        "agressividade_mod": 0.1,
    },
    "Equilibrado": {
        "descricao": "Balanceado entre ataque e defesa.",
        "icone": "⚖️",
        "cor": (200, 200, 100),
        "tracos_fixos": ["ADAPTAVEL", "FOCADO", "DETERMINADO"],
        "estilo_fixo": "BALANCED",
        "filosofia_fixa": "EQUILIBRIO",
        "quirks_fixos": [],
        "agressividade_mod": 0.0,
    },
    "Showman": {
        "descricao": "Luta para impressionar. Golpes dramáticos.",
        "icone": "🎭",
        "cor": (255, 200, 50),
        "tracos_fixos": ["SHOWMAN", "CRIATIVO", "EXPLOSIVO"],
        "estilo_fixo": "SHOWMAN",
        "filosofia_fixa": "ESPETACULO",
        "quirks_fixos": ["PROVOCADOR", "DANCA_MORTE"],
        "agressividade_mod": 0.15,
    },
    "Sombrio": {
        "descricao": "Silencioso e mortal. Espera e elimina.",
        "icone": "🌑",
        "cor": (50, 50, 80),
        "tracos_fixos": ["FRIO", "PACIENTE", "ASSASSINO_NATO", "PREDADOR"],
        "estilo_fixo": "AMBUSH",
        "filosofia_fixa": "PACIENCIA",
        "quirks_fixos": ["SOMBRA_MORTAL", "FINALIZADOR"],
        "agressividade_mod": -0.1,
    },
    "Perseguidor": {
        "descricao": "Nunca deixa a presa escapar. Pressão implacável.",
        "icone": "🐺",
        "cor": (150, 100, 50),
        "tracos_fixos": ["PERSEGUIDOR", "PREDADOR", "IMPLACAVEL", "ENCURRALADOR"],
        "estilo_fixo": "AGGRO",
        "filosofia_fixa": "PRESSAO",
        "quirks_fixos": ["SEDE_SANGUE", "INSTINTO_ANIMAL"],
        "agressividade_mod": 0.25,
    },
    "Protetor": {
        "descricao": "Inabalável. Resiste a tudo e contra-ataca.",
        "icone": "🏰",
        "cor": (100, 150, 200),
        "tracos_fixos": ["TANQUE", "PROTETOR", "DETERMINADO", "TIMING_PRECISO"],
        "estilo_fixo": "TANK",
        "filosofia_fixa": "RESISTENCIA",
        "quirks_fixos": ["PERSISTENTE", "CONTRA_ATAQUE_PERFEITO"],
        "instintos_fixos": ["DEFESA_FINAL", "BLOQUEIO_INSTINTIVO"],
        "ritmo_fixo": "RESPIRACAO",
        "agressividade_mod": -0.1,
    },
    # === NOVOS PRESETS v11.0 ===
    "Viking": {
        "descricao": "Guerreiro nórdico. Sem medo da morte, glória eterna.",
        "icone": "⚔️",
        "cor": (180, 140, 80),
        "tracos_fixos": ["VIKING", "BRUTAL", "DETERMINADO", "IMPLACAVEL", "SELVAGEM"],
        "estilo_fixo": "RAIDER",
        "filosofia_fixa": "SACRIFICIO",
        "quirks_fixos": ["GRITO_GUERRA", "BERSERKER_SOUL", "SEGUNDO_FOLEGO"],
        "instintos_fixos": ["FURIA_INSTANTANEA", "PERSEGUICAO_AUTOMATICA"],
        "ritmo_fixo": "BERSERKER",
        "agressividade_mod": 0.35,
    },
    "Samurai": {
        "descricao": "Um corte, uma vida. Precisão absoluta.",
        "icone": "🎌",
        "cor": (200, 80, 80),
        "tracos_fixos": ["SAMURAI", "HONORAVEL", "FOCADO", "PACIENTE", "TIMING_PRECISO"],
        "estilo_fixo": "IAIDO",
        "filosofia_fixa": "HONRA",
        "quirks_fixos": ["CALCULO_MORTAL", "FRAME_PERFECT", "PACIENCIA_INFINITA"],
        "instintos_fixos": ["CONTRA_REFLEXO", "ATAQUE_OPORTUNIDADE"],
        "ritmo_fixo": "PREDADOR",
        "agressividade_mod": 0.05,
    },
    "Capoeirista": {
        "descricao": "Dança mortal. Ginga hipnotizante.",
        "icone": "💃",
        "cor": (255, 200, 100),
        "tracos_fixos": ["DANÇARINO", "ACROBATA", "ERRATICO", "CRIATIVO", "VELOZ"],
        "estilo_fixo": "GINGA",
        "filosofia_fixa": "CAOS",
        "quirks_fixos": ["DANCA_MORTE", "ESQUIVA_REFLEXA", "ADRENALINE_JUNKIE"],
        "instintos_fixos": ["PULO_PERIGO", "AGACHAR_REFLEXO"],
        "ritmo_fixo": "ONDAS",
        "agressividade_mod": 0.15,
    },
    "Pugilista": {
        "descricao": "Boxeador de rua. Jabs e ganchos devastadores.",
        "icone": "🥊",
        "cor": (220, 180, 140),
        "tracos_fixos": ["TOURO", "BRUTAL", "DETERMINADO", "COLADO", "PRESSAO_CONSTANTE"],
        "estilo_fixo": "BOXER",
        "filosofia_fixa": "PRESSAO",
        "quirks_fixos": ["MESTRE_COMBO", "BURST_MODE", "WHIFF_PUNISHER"],
        "instintos_fixos": ["CONTRA_REFLEXO", "PERSEGUICAO_AUTOMATICA"],
        "ritmo_fixo": "PULSO",
        "agressividade_mod": 0.25,
    },
    "Psicopata": {
        "descricao": "Zero emoções. Eficiência fria e calculada.",
        "icone": "🔪",
        "cor": (80, 80, 100),
        "tracos_fixos": ["PSICOPATA", "FRIO", "CALCULISTA", "SÁDICO", "PREDADOR"],
        "estilo_fixo": "EXECUTE",
        "filosofia_fixa": "TORMENTO",
        "quirks_fixos": ["CALCULO_MORTAL", "OLHOS_DE_AGUIA", "EXECUTION_INSTINCT"],
        "instintos_fixos": ["INSTINTO_ASSASSINO", "ADAPTACAO_RAPIDA"],
        "ritmo_fixo": "MAREMOTO",
        "agressividade_mod": 0.2,
    },
    "Fantasma": {
        "descricao": "Você não pode acertar o que não pode ver.",
        "icone": "👻",
        "cor": (200, 200, 220),
        "tracos_fixos": ["FANTASMA", "EVASIVO", "ERRATICO", "BORBOLETA", "FRIO"],
        "estilo_fixo": "GHOST",
        "filosofia_fixa": "EROSAO",
        "quirks_fixos": ["REFLEXOS_DIVINOS", "TACTICAL_RETREAT", "MESTRE_DISTANCIA"],
        "instintos_fixos": ["ESQUIVA_SOMBRA", "RECUO_ESTRATEGICO", "DASH_PANICO"],
        "ritmo_fixo": "RESPIRACAO",
        "agressividade_mod": -0.15,
    },
    "Destruidor": {
        "descricao": "Força bruta pura. Esmaga tudo no caminho.",
        "icone": "💪",
        "cor": (150, 80, 50),
        "tracos_fixos": ["DESTRUIDOR", "BRUTAL", "TOURO", "MARTELO", "TRITURADOR"],
        "estilo_fixo": "CONQUEROR",
        "filosofia_fixa": "ANIQUILACAO",
        "quirks_fixos": ["ACUMULADOR", "BERSERKER_SOUL", "GRITO_GUERRA"],
        "instintos_fixos": ["FURIA_INSTANTANEA", "PERSEGUICAO_AUTOMATICA"],
        "ritmo_fixo": "ESCALADA",
        "agressividade_mod": 0.4,
    },
    "Tempestade": {
        "descricao": "Calmo... até explodir em fúria devastadora.",
        "icone": "⛈️",
        "cor": (100, 100, 180),
        "tracos_fixos": ["EXPLOSIVO", "PACIENTE", "DUPLA_PERSONALIDADE", "CLUTCH_PLAYER"],
        "estilo_fixo": "BURST",
        "filosofia_fixa": "EXPLOSAO",
        "quirks_fixos": ["BURST_MODE", "DESESPERO_LETAL", "CONTRA_MOMENTUM"],
        "instintos_fixos": ["FURIA_INSTANTANEA", "ATAQUE_OPORTUNIDADE"],
        "ritmo_fixo": "TEMPESTADE",
        "agressividade_mod": 0.1,
    },
    "Predador Alfa": {
        "descricao": "Caçador supremo. A presa não tem chance.",
        "icone": "🦁",
        "cor": (200, 150, 50),
        "tracos_fixos": ["ALPHA", "PREDADOR", "RASTREADOR", "ENCURRALADOR", "DOMINADOR"],
        "estilo_fixo": "HUNTER",
        "filosofia_fixa": "PREDACAO",
        "quirks_fixos": ["INSTINTO_ANIMAL", "CAÇADOR_FERIDAS", "EXECUTION_INSTINCT"],
        "instintos_fixos": ["INSTINTO_ASSASSINO", "PERSEGUICAO_AUTOMATICA", "PRESSAO_INSTINTIVA"],
        "ritmo_fixo": "PREDADOR",
        "agressividade_mod": 0.3,
    },
    "Masoquista": {
        "descricao": "Quanto mais sofre, mais forte fica.",
        "icone": "😈",
        "cor": (150, 50, 100),
        "tracos_fixos": ["MASOQUISTA", "PHOENIX", "UNDERDOG", "RESILIENTE", "DETERMINADO"],
        "estilo_fixo": "TANK",
        "filosofia_fixa": "SACRIFICIO",
        "quirks_fixos": ["BERSERKER_SOUL", "SEGUNDO_FOLEGO", "CLUTCH_MASTER"],
        "instintos_fixos": ["DEFESA_FINAL", "FURIA_INSTANTANEA"],
        "ritmo_fixo": "ESCALADA",
        "agressividade_mod": 0.15,
    },
    "Artista Marcial": {
        "descricao": "A luta é arte. Cada movimento é uma pincelada.",
        "icone": "🎨",
        "cor": (180, 100, 150),
        "tracos_fixos": ["ARTISTA_MARCIAL", "CRIATIVO", "STYLIST", "DANÇARINO", "ZEN"],
        "estilo_fixo": "MATADOR",
        "filosofia_fixa": "ESPETACULO",
        "quirks_fixos": ["DANCA_MORTE", "FRAME_PERFECT", "PERFECCIONISTA_COMBO"],
        "instintos_fixos": ["CONTRA_REFLEXO", "ATAQUE_OPORTUNIDADE"],
        "ritmo_fixo": "ONDAS",
        "agressividade_mod": 0.1,
    },
    "Zerg Rush": {
        "descricao": "Pressão infinita. Não para nunca.",
        "icone": "🐜",
        "cor": (100, 150, 100),
        "tracos_fixos": ["INCANSAVEL", "SEDENTO", "PRESSAO_CONSTANTE", "COLADO", "GLUTTON"],
        "estilo_fixo": "PRESSURE",
        "filosofia_fixa": "PRESSAO",
        "quirks_fixos": ["ADRENALINE_JUNKIE", "MOMENTUM_SURFER", "ECO_GUERRA"],
        "instintos_fixos": ["PERSEGUICAO_AUTOMATICA", "PRESSAO_INSTINTIVA"],
        "ritmo_fixo": "CONSTANTE",
        "agressividade_mod": 0.35,
    },
    "Contemplativo": {
        "descricao": "Observa, analisa, age no momento perfeito.",
        "icone": "🧘",
        "cor": (150, 180, 200),
        "tracos_fixos": ["ZEN", "ANALITICO", "PACIENTE", "PREVISOR", "CEREBRAL"],
        "estilo_fixo": "TACTICIAN",
        "filosofia_fixa": "ARTE_GUERRA",
        "quirks_fixos": ["LEITURA_CORPORAL", "OLHOS_DE_AGUIA", "PACIENCIA_INFINITA"],
        "instintos_fixos": ["ATAQUE_OPORTUNIDADE", "ADAPTACAO_RAPIDA"],
        "ritmo_fixo": "PREDADOR",
        "agressividade_mod": -0.1,
    },
    "Caótico": {
        "descricao": "Impossível de prever. Até ele não sabe o que vai fazer.",
        "icone": "🌪️",
        "cor": (255, 100, 255),
        "tracos_fixos": ["CAOS_MENTAL", "ERRATICO", "CAOTICO", "IMPULSIVO", "APOSTADOR"],
        "estilo_fixo": "CHAOS_MAGIC",
        "filosofia_fixa": "CAOS",
        "quirks_fixos": ["ADRENALINE_JUNKIE", "MIND_GAMES", "BURST_MODE"],
        "instintos_fixos": ["ADAPTACAO_RAPIDA", "DASH_PANICO"],
        "ritmo_fixo": "CAOTICO",
        "agressividade_mod": 0.2,
    },
}

# Lista ordenada para UI
LISTA_PERSONALIDADES = list(PERSONALIDADES_PRESETS.keys())
