"""
=============================================================================
NEURAL FIGHTS - Cérebro da IA v11.0 WEAPON REWORK EDITION
=============================================================================
CHANGELOG v11.0:
- Reformulação da IA para Mangual: spin acumulativo, distância de zona de spin,
  detecção de zona morta expandida, arquétipo BERSERKER
- Reformulação da IA para Adagas Gêmeas: alcance ideal reduzido (0.50x),
  modo combo colado, dash agressivo para manter combo ativo
- Percepção de armas inimigas: lógica contra Mangual (entrar na zona morta)
  e contra Adagas Gêmeas (manter distância, punir aproximação)
- Bugfix: lógica de fallback para estilo de arma None/vazio
- Bugfix: detecção de alcance_agressao para Adagas Gêmeas
- Compatível com novos campos anim_* em armas.json
=============================================================================
Sistema de inteligência artificial com comportamento humano realista,
consciência espacial avançada e percepção de armas.

NOVIDADES v10.0:
- Percepção de armas inimigas (tipo, alcance, perigo)
- Cálculo de zonas de ameaça baseado na arma do oponente
- Adaptação de distância ideal baseado em matchup de armas
- Análise de vantagens/desvantagens de arma
- Comportamentos específicos contra cada tipo de arma
- Sweet spots e zonas mortas de armas

SISTEMAS v9.0 (mantidos):
- Sistema de reconhecimento de paredes e obstáculos
- Consciência espacial tática (encurralado, vantagem, cobertura)
- Uso inteligente de obstáculos (cobertura, flanqueamento)
- Detecção de quando oponente está contra parede
- Evita recuar para obstáculos
- Ajuste automático de trajetória para evitar colisões
- Análise de caminhos livres em todas direções
- Comportamentos especiais quando encurralado

SISTEMAS v8.0 (mantidos):
- Sistema de antecipação de ataques (lê o oponente)
- Desvios inteligentes com timing humano
- Baiting e fintas (engana o oponente)
- Janelas de oportunidade (ataca nos momentos certos)
- Pressão psicológica e momentum
- Hesitação realista e impulsos
- Leitura de padrões do oponente
- Combos e follow-ups inteligentes

Combinações possíveis:
- 50+ traços × 5 slots = milhares de combinações de traços
- 25+ arquétipos
- 15+ estilos de luta
- 20+ quirks
- 10+ filosofias
- 10 humores dinâmicos

Total: CENTENAS DE MILHARES de personalidades únicas!
=============================================================================
"""

import logging
import random
import math

from neural_fights.utils.config import PPM
from neural_fights.core.physics import normalizar_angulo
from neural_fights.core.skills import get_skill_data
from neural_fights.models import get_class_data
from neural_fights.ai.contracts import obter_brain as _obter_brain
from neural_fights.ai.percepcao import (
    FASE_GOLPEANDO,
    FASE_PREPARANDO,
    FASE_RECUPERANDO,
    construir_observacao,
)
from neural_fights.ai.skill_contracts import (
    alvo_tem_efeito,
    calcular_custo_vida,
    tem_buff_velocidade,
    tem_cura,
)
from neural_fights.ai.personalities import (
    TODOS_TRACOS, TRACOS_AGRESSIVIDADE, TRACOS_DEFENSIVO, TRACOS_MOBILIDADE,
    TRACOS_SKILLS, TRACOS_MENTAL, TRACOS_ESPECIAIS,
    ARQUETIPO_DATA, ESTILOS_LUTA, QUIRKS, FILOSOFIAS, HUMORES,
    PERSONALIDADES_PRESETS, INSTINTOS, RITMOS, RITMO_MODIFICADORES,
    perfil_de_tracos
)


LOGGER = logging.getLogger(__name__)

# Importação do sistema de análise de armas v10.0
try:
    from neural_fights.core.weapon_analysis import (
        get_weapon_profile, compare_weapons,
        get_safe_distance, evaluate_combat_position
    )
    WEAPON_ANALYSIS_AVAILABLE = True
except ImportError:
    WEAPON_ANALYSIS_AVAILABLE = False

# Importação do sistema de estratégia de skills v1.0
try:
    from neural_fights.ai.skill_strategy import CombatSituation, SkillStrategySystem
    SKILL_STRATEGY_AVAILABLE = True
except ImportError:
    SKILL_STRATEGY_AVAILABLE = False


def _delegado_emocional(nome):
    """Property que delega um campo emocional ao EmotionSystem (Onda 5C)."""

    def fget(self):
        return getattr(self._motor_emocional(), nome)

    def fset(self, valor):
        setattr(self._motor_emocional(), nome, valor)

    return property(fget, fset)


class AIBrain:
    """
    Cérebro da IA v10.0 WEAPON PERCEPTION EDITION - Sistema de personalidade procedural com
    comportamento humano realista, inteligência de combate avançada e percepção de armas.
    """
    
    def __init__(self, parent, rng=None):
        self.parent = parent
        # O módulo continua como fallback, preservando integrações que aplicam
        # patch em ``neural_fights.ai.brain.random``. Testes e simulações reproduzíveis podem
        # injetar uma instância de ``random.Random``.
        self.rng = rng if rng is not None else random
        self._dt_atual = 1.0 / 60.0
        self.timer_decisao = 0.0
        # Onda 5B: acao_atual e property; o rascunho fica em _acao_atual e
        # TODA escrita passa pelo escritor unico (_definir_acao) com min-hold.
        self._acao_atual = "NEUTRO"
        self._acao_fonte = "init"
        self._acao_hold_ate = 0.0
        self._acao_hold_prio = 9
        self._modo_proposta = False
        self._contexto_escrita = 2
        self.tell_atual = None
        self.dir_circular = self.rng.choice([-1, 1])
        
        # === EMOÇÕES: MOTOR ÚNICO (Onda 5C) ===
        # O estado emocional vive no EmotionSystem; o brain delega
        # leitura/escrita via properties, então os escritores
        # espalhados (quirks, presets, reações) seguem funcionando.
        from neural_fights.ai.emotions import EmotionSystem
        self.emocoes = EmotionSystem(self)
        self.humor_timer = 0.0
        
        # === MEMÓRIA DE COMBATE (estado do brain, não-emocional) ===
        self.ultimo_dano_recebido = 0.0  # Valor do último dano recebido
        self.vezes_que_fugiu = 0
        self.ultimo_hp = parent.vida
        self.tempo_combate = 0.0
        
        # === PERSONALIDADE GERADA ===
        self.arquetipo = "GUERREIRO"
        self.estilo_luta = "BALANCED"
        self.filosofia = "EQUILIBRIO"
        self.tracos = []
        self.quirks = []
        self._perfil_chave = None
        self._perfil_cache = {}
        self._direcao_avaliada = None
        self._direcao_aceita = True
        # Telemetria: quantas decisoes de movimento aconteceram e em
        # quantas a pilha de personalidade chegou a rodar (alvo V1).
        self.contadores = {"decisoes": 0, "pilha_completa": 0, "escritas_aceitas": 0, "escritas_seguradas": 0}
        self.agressividade_base = 0.5
        
        # === NOVOS SISTEMAS v11.0 ===
        self.instintos = []  # Lista de instintos ativos
        self.cd_instintos = {}  # Onda 5D: cooldown POR instinto (tempo abs)
        self.cd_hesitacao = 0.0  # portao de hesitacao tambem paga cooldown
        self.ultimo_bloqueio = 99.0  # s desde o ultimo hit absorvido em guarda
        self.ritmo = None    # Ritmo de batalha atual
        self.ritmo_fase_atual = 0  # Índice da fase atual
        self.ritmo_timer = 0.0     # Timer para mudança de fase
        self._ritmo_aleatorio_atual = None
        self.ritmo_modificadores = {"agressividade": 0, "defesa": 0, "mobilidade": 0}
        
        # === COOLDOWNS INTERNOS ===
        self.cd_dash = 0.0
        self.cd_pulo = 0.0
        self.cd_desvio = 0.0   # Onda 8C: gate do desvio inteligente
        self.cd_punicao = 0.0  # Onda 8D: gate da punição de whiff
        self.cd_mudanca_direcao = 0.0
        self.cd_reagir = 0.0
        self.cd_buff = 0.0
        self.cd_quirk = 0.0
        self.cd_mudanca_humor = 0.0
        
        # === CACHE DE SKILLS ===
        self.skills_por_tipo = {
            "PROJETIL": [],
            "BEAM": [],
            "AREA": [],
            "DASH": [],
            "BUFF": [],
            "SUMMON": [],
            "TRAP": [],
            "TRANSFORM": [],
            "CHANNEL": []
        }
        
        # === SISTEMA DE ESTRATÉGIA DE SKILLS v1.0 ===
        self.skill_strategy = None  # Inicializado após gerar personalidade
        
        # === ESTADO ESPECIAL ===
        self.modo_berserk = False
        self.modo_defensivo = False
        self.modo_burst = False
        self.executando_quirk = False
        
        # === SISTEMA DE COREOGRAFIA v5.0 ===
        self.momento_cinematografico = None
        self.acao_sincronizada = None
        self.respondendo_a_oponente = False
        self.memoria_oponente = {
            "ultima_acao": None,
            "padrao_detectado": None,
            "vezes_fugiu": 0,
            "vezes_atacou": 0,
            "estilo_percebido": None,
            "ameaca_nivel": 0.5,
        }
        self.reacao_pendente = None
        self.tempo_reacao = 0.0
        
        # === SISTEMA HUMANO v8.0 - NOVIDADES ===
        
        # Antecipação e leitura do oponente
        self.leitura_oponente = {
            "ataque_iminente": False,
            "direcao_provavel": 0.0,
            "tempo_para_ataque": 0.0,
            "padrao_movimento": [],  # Últimos 10 movimentos
            "padrao_ataque": [],     # Últimos 10 ataques
            "tendencia_esquerda": 0.5,
            "frequencia_pulo": 0.0,
            "agressividade_percebida": 0.5,
            "previsibilidade": 0.5,  # Quão previsível é o oponente
        }
        
        # Sistema de janelas de oportunidade
        self.janela_ataque = {
            "aberta": False,
            "tipo": None,  # "pos_ataque", "recuperando", "fora_alcance", "pulo"
            "duracao": 0.0,
            "qualidade": 0.0,  # 0-1, quão boa é a janela
        }
        
        # Sistema de baiting (isca/finta)
        self.bait_state = {
            "ativo": False,
            "tipo": None,  # "recuo_falso", "abertura_falsa", "skill_falsa"
            "timer": 0.0,
            "sucesso_count": 0,
            "falha_count": 0,
        }
        
        # Momentum e pressão
        self.momentum = 0.0  # -1 (perdendo) a 1 (ganhando)
        self.pressao_aplicada = 0.0  # Quanto está pressionando
        self.pressao_recebida = 0.0  # Quanto está sendo pressionado
        
        # Hesitação e impulso humano
        self.hesitacao = 0.0  # Probabilidade de hesitar
        self.impulso = 0.0    # Probabilidade de agir impulsivamente
        self.congelamento = 0.0  # "Freeze" sob pressão
        
        # Timing humano
        self.tempo_reacao_base = self.rng.uniform(0.12, 0.25)  # Varia por personalidade
        self.variacao_timing = self.rng.uniform(0.05, 0.15)    # Inconsistência humana
        self.micro_ajustes = 0  # Pequenos ajustes de posição

        # === ONDA 8A: OBSERVAÇÃO HONESTA ===
        # Substitui a telepatia (ler inimigo.brain.acao_atual). A leitura
        # do oponente vira habilidade: latência, má-leitura e memória
        # escalam com habilidade_leitura (derivada dos eixos no
        # _aplicar_modificadores_iniciais).
        self.habilidade_leitura = 0.5
        self.disciplina_tatica = 0.5     # consumida pela Onda 8E (planos)
        self._obs_cache = None
        self._obs_cache_tempo = -1.0
        self._obs_ataque_id_visto = -1
        self._obs_ataque_mal_lido = False

        # === ONDA 8C: SISTEMA ESPACIAL REAL ===
        # SpatialAwarenessSystem (arena circular, LOS, rotas) substitui a
        # cópia retangular inline. Criação preguiçosa via _sistema_espacial.
        self._espacial = None
        self._timer_taticas = 0.0
        self.mult_janela_parry = 1.0  # FRAME_PERFECT amplia (ver 8B)
        self.chance_burst_combo = 0.35  # Onda 8H: o motor consulta no 3º hit
        self._ataque_id_avaliado_desvio = -1   # um desvio avaliado por swing
        self._ataque_id_avaliado_punicao = -1  # uma punição avaliada por swing

        # === ONDA 8E: PLANO DE LUTA ===
        # Intenção tática persistente (2-6s). NÃO substitui a pilha de
        # personalidade: entra como viés logo após a proposta e os
        # estágios seguintes continuam perturbando. dict simples:
        # {"tipo", "expira_em", "compromisso"}.
        self.plano = None
        self._plano_hp_inicial = 1.0
        
        # Sistema de combos e follow-ups
        self.combo_state = {
            "em_combo": False,
            "hits_combo": 0,
            "ultimo_tipo_ataque": None,
            "pode_followup": False,
            "timer_followup": 0.0,
        }
        
        # Respiração e ritmo
        self.ritmo_combate = self.rng.uniform(0.8, 1.2)  # Personalidade do ritmo
        self.burst_counter = 0  # Conta explosões de ação
        self.descanso_timer = 0.0  # Micro-pausas naturais
        
        # Histórico de ações para não repetir muito
        self.historico_acoes = []
        self.repeticao_contador = {}
        
        # === SISTEMA DE RECONHECIMENTO ESPACIAL v9.0 ===
        # Awareness de paredes e obstáculos
        self.consciencia_espacial = {
            "parede_proxima": None,  # None, "norte", "sul", "leste", "oeste"
            "distancia_parede": 999.0,
            "obstaculo_proxima": None,  # Obstáculo mais próximo
            "distancia_obstaculo": 999.0,
            "encurralado": False,
            "oponente_contra_parede": False,
            "caminho_livre": {"frente": True, "tras": True, "esquerda": True, "direita": True},
            "posicao_tatica": "centro",  # "centro", "perto_parede", "encurralado", "vantagem"
        }
        
        # Uso tático de obstáculos
        self.tatica_espacial = {
            "usando_cobertura": False,
            "tipo_cobertura": None,  # "pilar", "obstaculo", "parede"
            "forcar_canto": False,  # Tentando encurralar oponente
            "recuar_para_obstaculo": False,  # Recuando de costas pra obstáculo (perigoso)
            "flanquear_obstaculo": False,  # Usando obstáculo pra flanquear
            "last_check_time": 0.0,  # Otimização - não checa todo frame
        }
        
        # === SISTEMA DE PERCEPÇÃO DE ARMAS v10.0 ===
        self.percepcao_arma = {
            # Análise da minha arma
            "minha_arma_perfil": None,          # WeaponProfile da minha arma
            "meu_alcance_efetivo": 2.0,         # Alcance real da minha arma
            "minha_velocidade_ataque": 0.5,    # Velocidade de ataque
            "meu_arco_cobertura": 90.0,         # Arco que minha arma cobre
            
            # Análise da arma inimiga
            "arma_inimigo_tipo": None,          # Tipo da arma do inimigo
            "arma_inimigo_perfil": None,        # WeaponProfile da arma inimiga
            "alcance_inimigo": 2.0,             # Alcance do inimigo
            "zona_perigo_inimigo": 2.5,         # Distância perigosa
            "ponto_cego_inimigo": None,         # Ângulo do ponto cego
            "velocidade_inimigo": 0.5,          # Velocidade de ataque
            
            # Análise de matchup
            "vantagem_alcance": 0.0,            # >0 = meu alcance maior
            "vantagem_velocidade": 0.0,         # >0 = sou mais rápido
            "vantagem_cobertura": 0.0,          # >0 = cubro mais área
            "matchup_favoravel": 0.0,           # -1 a 1, geral
            
            # Estado tático baseado em armas
            "distancia_segura": 3.0,            # Distância segura contra inimigo
            "distancia_ataque": 1.5,            # Distância ideal para atacar
            "estrategia_recomendada": "neutro", # "aproximar", "afastar", "flanquear", "trocar"
            
            # Timing
            "last_analysis_time": 0.0,          # Quando última análise foi feita
            "enemy_weapon_changed": False,      # Se arma do inimigo mudou
        }
        
        # Gera personalidade única
        self._gerar_personalidade()

    @property
    def rng(self):
        """Fonte aleatória da IA, com fallback legado seguro."""
        return getattr(self, "_rng", random)

    @rng.setter
    def rng(self, value):
        self._rng = value if value is not None else random

    @property
    def perfil(self):
        """Posição do lutador nos eixos de comportamento, derivada dos traços.

        O código de decisão consulta o eixo, não o nome do traço. É o que faz
        os 162 traços declarados valerem por construção, em vez de só os que
        alguém lembrou de citar num ``in self.tracos``.

        Recalcula quando a lista muda: o cérebro adiciona traços durante a luta
        ao evoluir, e o perfil precisa acompanhar.
        """
        chave = tuple(self.tracos)
        if chave != self._perfil_chave:
            self._perfil_chave = chave
            self._perfil_cache = perfil_de_tracos(chave)
        return self._perfil_cache

    def _chance_temporal(self, chance_60fps, dt=None):
        """Sorteia um evento preservando sua taxa por segundo entre FPS distintos.

        ``chance_60fps`` é a probabilidade histórica por frame a 60 FPS. A
        conversão exponencial evita que reduzir ou aumentar o FPS altere a
        frequência temporal do comportamento.
        """
        chance = max(0.0, min(1.0, float(chance_60fps)))
        if dt is None:
            intervalo = getattr(self, "_dt_atual", 1.0 / 60.0)
        else:
            intervalo = max(0.0, float(dt))
        if chance <= 0.0 or intervalo <= 0.0:
            return False
        if chance >= 1.0:
            return True
        chance_ajustada = 1.0 - ((1.0 - chance) ** (intervalo * 60.0))
        return self.rng.random() < chance_ajustada

    # =========================================================================
    # GERAÇÃO DE PERSONALIDADE
    # =========================================================================
    
    def _gerar_personalidade(self):
        """Gera uma personalidade - usa preset se definido, ou aleatório"""
        # Verifica se o personagem tem uma personalidade preset definida
        preset_nome = getattr(self.parent.dados, 'personalidade', 'Aleatório')
        
        if preset_nome and preset_nome != 'Aleatório' and preset_nome in PERSONALIDADES_PRESETS:
            # Usa o preset definido
            self._aplicar_preset(preset_nome)
        else:
            # Gera aleatoriamente como antes
            self._gerar_personalidade_aleatoria()
    
    def _aplicar_preset(self, preset_nome):
        """Aplica um preset de personalidade"""
        preset = PERSONALIDADES_PRESETS[preset_nome]
        
        # Define arquétipo baseado na classe primeiro
        self._definir_arquetipo()
        
        # Aplica estilo fixo se definido
        if preset["estilo_fixo"]:
            self.estilo_luta = preset["estilo_fixo"]
        else:
            self._selecionar_estilo()
        
        # Aplica filosofia fixa se definida
        if preset["filosofia_fixa"]:
            self.filosofia = preset["filosofia_fixa"]
        else:
            self._selecionar_filosofia()
        
        # Aplica traços fixos + alguns aleatórios
        self.tracos = list(preset["tracos_fixos"])
        # Adiciona 1-2 traços aleatórios para variedade
        tracos_extras = self.rng.randint(1, 2)
        tracos_disponiveis = [t for t in TODOS_TRACOS if t not in self.tracos]
        self.tracos.extend(self.rng.sample(tracos_disponiveis, min(tracos_extras, len(tracos_disponiveis))))
        
        # Aplica quirks fixos + chance de um extra aleatório
        self.quirks = list(preset["quirks_fixos"])
        if self.rng.random() < 0.3 and len(self.quirks) < 3:
            quirks_disponiveis = [q for q in QUIRKS.keys() if q not in self.quirks]
            if quirks_disponiveis:
                self.quirks.append(self.rng.choice(quirks_disponiveis))
        
        # === NOVOS SISTEMAS v11.0 ===
        # Aplica instintos do preset + alguns aleatórios
        self.instintos = list(preset.get("instintos_fixos", []))
        if self.rng.random() < 0.4:
            instintos_disponiveis = [i for i in INSTINTOS.keys() if i not in self.instintos]
            if instintos_disponiveis:
                self.instintos.append(self.rng.choice(instintos_disponiveis))
        self._garantir_instinto_evasivo()  # Onda 8F
        
        # Aplica ritmo do preset ou seleciona aleatoriamente
        ritmo_fixo = preset.get("ritmo_fixo")
        if ritmo_fixo and ritmo_fixo in RITMOS:
            self.ritmo = ritmo_fixo
        else:
            self.ritmo = self.rng.choice(list(RITMOS.keys()))
        self.ritmo_fase_atual = 0
        self.ritmo_timer = 0.0
        
        # Calcula agressividade com modificador do preset
        self._calcular_agressividade()
        self.agressividade_base = max(0.0, min(1.0, self.agressividade_base + preset["agressividade_mod"]))
        
        # Categoriza skills e aplica modificadores
        self._categorizar_skills()
        self._aplicar_modificadores_iniciais()
        self._inicializar_skill_strategy()
    
    def _gerar_personalidade_aleatoria(self):
        """Gera uma personalidade completamente aleatória (comportamento original)"""
        self._definir_arquetipo()
        self._selecionar_estilo()
        self._selecionar_filosofia()
        self._gerar_tracos()
        self._gerar_quirks()
        self._gerar_instintos()
        self._gerar_ritmo()
        self._calcular_agressividade()
        self._categorizar_skills()
        self._aplicar_modificadores_iniciais()
        self._inicializar_skill_strategy()
    
    def _inicializar_skill_strategy(self):
        """Inicializa o sistema de estratégia de skills"""
        if SKILL_STRATEGY_AVAILABLE:
            self.skill_strategy = SkillStrategySystem(self.parent, self, rng=self.rng)
            
            # Ajusta estratégia baseado na arma
            if hasattr(self.parent.dados, 'arma_obj') and self.parent.dados.arma_obj:
                arma = self.parent.dados.arma_obj
                # Onda 8A: Arma nunca teve atributo `alcance` — o getattr
                # devolvia 2.0 para TODA arma e a estratégia de skills era
                # ajustada como se tudo fosse espada curta. Usa o mesmo
                # modelo de alcance do resto do brain.
                alcance_arma = self._calcular_alcance_efetivo()
                vel_arma = getattr(arma, 'velocidade_ataque', 1.0)
                self.skill_strategy.ajustar_para_arma(alcance_arma, vel_arma)
                
                LOGGER.debug(
                    "IA %s: role=%s skills=%d combos=%d",
                    self.parent.dados.nome,
                    self.skill_strategy.role_principal.value,
                    len(self.skill_strategy.todas_skills),
                    len(self.skill_strategy.combos_disponiveis),
                )
        else:
            self.skill_strategy = None
    
    # Onda 8F: todo lutador precisa de pelo menos UM reflexo evasivo —
    # antes, o sorteio de 2-4 entre 15 deixava a maioria sem nenhum e a
    # cadeia de desvio por instinto órfã na prática.
    _INSTINTOS_EVASIVOS = (
        "PULO_PERIGO", "AGACHAR_REFLEXO", "ESQUIVA_SOMBRA", "EVASAO_COMBO",
    )

    def _garantir_instinto_evasivo(self):
        disponiveis = [i for i in self._INSTINTOS_EVASIVOS if i in INSTINTOS]
        if disponiveis and not any(i in self.instintos for i in disponiveis):
            self.instintos.append(self.rng.choice(disponiveis))

    def _gerar_instintos(self):
        """Gera instintos aleatórios para a IA"""
        num_instintos = self.rng.randint(2, 4)
        self.instintos = self.rng.sample(list(INSTINTOS.keys()), min(num_instintos, len(INSTINTOS)))
        self._garantir_instinto_evasivo()
    
    def _gerar_ritmo(self):
        """Seleciona um ritmo de batalha aleatório"""
        # Alguns ritmos são mais raros
        ritmos_comuns = ["ONDAS", "RESPIRACAO", "CONSTANTE", "PREDADOR"]
        ritmos_raros = ["TEMPESTADE", "BERSERKER", "CAOTICO", "ESCALADA"]
        
        if self.rng.random() < 0.3:
            self.ritmo = self.rng.choice(ritmos_raros)
        else:
            self.ritmo = self.rng.choice(ritmos_comuns)
        
        self.ritmo_fase_atual = 0
        self.ritmo_timer = 0.0

    def _definir_arquetipo(self):
        """Define arquétipo baseado na classe"""
        p = self.parent
        classe = p.classe_nome.lower() if p.classe_nome else ""
        
        # Onda 8E (bug #2): "duelista" não existia (só "espadachim") —
        # "Duelista (Precisão)" caía no fallback por arma e era a classe
        # de pior winrate do ledger (14,8%). "necromante" apontava para
        # INVOCADOR e "feiticeiro" para MAGO, sombreando os arquétipos
        # NECROMANTE/ARCANO que existiam sem produtor.
        arquetipo_map = {
            "mago": "MAGO", "piromante": "PIROMANTE", "criomante": "CRIOMANTE",
            "eletromante": "ELETROMANTE", "necromante": "NECROMANTE",
            "feiticeiro": "ARCANO",
            "bruxo": "MAGO_CONTROLE", "assassino": "ASSASSINO", "ninja": "NINJA",
            "sombra": "SOMBRA", "berserker": "BERSERKER", "bárbaro": "BERSERKER",
            "cavaleiro": "SENTINELA", "paladino": "PALADINO", "ladino": "LADINO",
            "druida": "DRUIDA", "monge": "MONGE", "arqueiro": "ARQUEIRO",
            "caçador": "ARQUEIRO", "guerreiro": "GUERREIRO", "samurai": "SAMURAI",
            "ronin": "RONIN", "espadachim": "DUELISTA", "duelista": "DUELISTA",
            "gladiador": "GLADIADOR",
            "guardião": "GUARDIAO", "templário": "TEMPLARIO",
        }

        arquetipo_via_arma = False
        for key, arq in arquetipo_map.items():
            if key in classe:
                self.arquetipo = arq
                break
        else:
            self._definir_arquetipo_por_arma()
            arquetipo_via_arma = True

        if self.arquetipo in ARQUETIPO_DATA:
            data = ARQUETIPO_DATA[self.arquetipo]
            self.estilo_luta = data["estilo"]
            self.agressividade_base = data["agressividade"]
            # Onda 8E (bug #1): o caminho por arma calcula alcance_ideal
            # afinado por tipo/estilo/peso — a constante do arquétipo o
            # sobrescrevia e ~120 linhas de tuning eram letra morta.
            if not arquetipo_via_arma:
                p.alcance_ideal = data["alcance"]

    def _definir_arquetipo_por_arma(self):
        """Define arquétipo pela arma se classe não mapeada - v12.2 CORRIGIDO"""
        p = self.parent
        arma = p.dados.arma_obj if hasattr(p.dados, 'arma_obj') else None
        
        if not arma:
            self.arquetipo = "MONGE"
            p.alcance_ideal = 1.5
            return

        tipo = getattr(arma, 'tipo', '')
        peso = getattr(arma, 'peso', 5.0)
        
        # Importa perfis de hitbox para alcance preciso
        try:
            from neural_fights.core.hitbox import HITBOX_PROFILES
            perfil = HITBOX_PROFILES.get(tipo, HITBOX_PROFILES.get("Reta", {}))
            range_mult = perfil.get("range_mult", 2.0)
        except Exception:
            LOGGER.debug("Falha ao carregar perfil de hitbox da arma", exc_info=True)
            perfil = {}
            range_mult = 2.0
        
        # Calcula alcance REAL em metros: raio do personagem * multiplicador da arma
        raio = p.raio_fisico if hasattr(p, 'raio_fisico') else 0.4
        alcance_max = raio * range_mult

        # Onda 4: ranged usa a fonte única do catálogo — a MESMA distância
        # de onde o motor dispara. Antes a IA se posicionava por
        # raio*range_mult (~8,5m para Arco) enquanto o motor atirava de 20m.
        from neural_fights.models.constants import alcance_ranged_m
        _alcance_cat = alcance_ranged_m(tipo)
        if _alcance_cat is not None:
            alcance_max = _alcance_cat
        
        # Define arquétipo e alcance IDEAL (onde a IA quer ficar)
        if "Orbital" in tipo:
            self.arquetipo = "SENTINELA"
            # Orbitais: fica bem perto para os orbes acertarem
            p.alcance_ideal = alcance_max * 0.8
            
        elif "Arco" in tipo:
            self.arquetipo = "ARQUEIRO"
            # Onda 4: alcance_max = 14m (catálogo, mesmo valor do motor).
            # Arqueiro quer ficar BEM LONGE - 60% do máximo (~8,4m)
            p.alcance_ideal = alcance_max * 0.6
            p.alcance_efetivo = alcance_max  # Pode acertar em todo o alcance
            
        elif "Mágica" in tipo or "Cajado" in tipo:
            self.arquetipo = "MAGO"
            # Mago: distância média para skills
            p.alcance_ideal = alcance_max * 0.7
            
        elif "Corrente" in tipo:
            estilo_arma = getattr(arma, 'estilo', '')
            min_range_ratio = perfil.get("min_range_ratio", 0.25)
            zona_morta = alcance_max * min_range_ratio
            
            if estilo_arma == "Mangual":
                # v3.0 Mangual: zona morta 40%, spin zone 40-72% do alcance
                # Zona morta grande, mas tem bônus quando acumula momentum
                self.arquetipo = "BERSERKER"  # Mangual é um Berserker de corrente
                # Alcance ideal = ponto de spin máximo (55% do alcance máximo)
                p.alcance_ideal = alcance_max * 0.55
                p.zona_morta_mangual = zona_morta  # Salva para uso na IA
                p.mangual_momentum = 0.0            # Estado de momentum acumulado
            else:
                self.arquetipo = "ACROBATA"
                # Outras correntes: meio termo entre zona morta e máximo
                p.alcance_ideal = (alcance_max + zona_morta) / 2
            
        elif "Arremesso" in tipo:
            self.arquetipo = "LANCEIRO"
            # Arremesso: mantém distância segura mas não muito longe
            p.alcance_ideal = alcance_max * 0.5
            
        elif "Dupla" in tipo:
            self.arquetipo = "ASSASSINO"
            estilo_arma = getattr(arma, 'estilo', '')
            if estilo_arma == "Adagas Gêmeas":
                # v3.1: Adagas têm lâminas longas — combate próximo mas não colado
                # Range ideal é 70% do alcance max: perto suficiente para o combo,
                # longe suficiente para ter tempo de reagir/esquivar
                p.alcance_ideal = alcance_max * 0.70
                p.alcance_agressao = alcance_max * 0.85  # começa a pressionar aqui
            else:
                # Outras armas duplas: perto mas não tão colado
                p.alcance_ideal = alcance_max * 0.70
            
        elif "Transformável" in tipo:
            self.arquetipo = "GUERREIRO"
            # Transformável: distância média (adapta-se)
            p.alcance_ideal = alcance_max * 0.8
            
        elif "Reta" in tipo:
            # Define arquétipo pelo peso
            if peso > 10.0:
                self.arquetipo = "COLOSSO"
                p.alcance_ideal = alcance_max * 0.9  # Pesadas = mais perto
            elif peso < 2.5:
                self.arquetipo = "DUELISTA"
                p.alcance_ideal = alcance_max * 0.75
            elif peso > 6.0:
                self.arquetipo = "GUERREIRO_PESADO"
                p.alcance_ideal = alcance_max * 0.85
            else:
                self.arquetipo = "GUERREIRO"
                p.alcance_ideal = alcance_max * 0.8
        else:
            # Fallback
            if peso > 10.0:
                self.arquetipo = "COLOSSO"
            elif peso < 2.5:
                self.arquetipo = "DUELISTA"
            elif peso > 6.0:
                self.arquetipo = "GUERREIRO_PESADO"
            else:
                self.arquetipo = "GUERREIRO"
            p.alcance_ideal = alcance_max * 0.8
        
        # Garante alcance mínimo razoável
        p.alcance_ideal = max(0.8, p.alcance_ideal)

    def _selecionar_estilo(self):
        """Seleciona estilo de luta"""
        if self.rng.random() < 0.7:
            return
        
        estilos_alternativos = {
            "MAGO": ["BURST", "CONTROL", "KITE"],
            "ASSASSINO": ["AMBUSH", "COMBO", "OPPORTUNIST"],
            "GUERREIRO": ["AGGRO", "COUNTER", "TANK"],
            "ARQUEIRO": ["RANGED", "MOBILE", "POKE"],
            "BERSERKER": ["AGGRO", "BURST", "BERSERK"],
        }
        
        if self.arquetipo in estilos_alternativos:
            self.estilo_luta = self.rng.choice(estilos_alternativos[self.arquetipo])
        else:
            self.estilo_luta = self.rng.choice(list(ESTILOS_LUTA.keys()))

    def _selecionar_filosofia(self):
        """Seleciona filosofia de combate"""
        filosofias_por_estilo = {
            "BERSERK": ["DOMINACAO", "PRESSAO", "EXECUCAO"],
            "TANK": ["RESISTENCIA", "SOBREVIVENCIA", "EQUILIBRIO"],
            "KITE": ["SOBREVIVENCIA", "PACIENCIA", "OPORTUNISMO"],
            "BURST": ["EXECUCAO", "OPORTUNISMO", "DOMINACAO"],
            "COUNTER": ["PACIENCIA", "OPORTUNISMO", "EQUILIBRIO"],
        }
        
        if self.estilo_luta in filosofias_por_estilo:
            self.filosofia = self.rng.choice(filosofias_por_estilo[self.estilo_luta])
        else:
            self.filosofia = self.rng.choice(list(FILOSOFIAS.keys()))

    def _gerar_tracos(self):
        """Gera combinação única de traços"""
        num_tracos = self.rng.randint(5, 7)
        
        categorias = [
            TRACOS_AGRESSIVIDADE, TRACOS_DEFENSIVO, TRACOS_MOBILIDADE,
            TRACOS_SKILLS, TRACOS_MENTAL,
        ]
        
        self.tracos = []
        
        for cat in categorias:
            self.tracos.append(self.rng.choice(cat))
        
        extras_needed = num_tracos - len(self.tracos)
        todos_restantes = [t for t in TODOS_TRACOS if t not in self.tracos]
        
        if self.rng.random() < 0.4:
            especial = self.rng.choice(TRACOS_ESPECIAIS)
            if especial not in self.tracos:
                self.tracos.append(especial)
                extras_needed -= 1
        
        if extras_needed > 0:
            extras = self.rng.sample(todos_restantes, min(extras_needed, len(todos_restantes)))
            self.tracos.extend(extras)
        
        self._resolver_conflitos_tracos()

    def _resolver_conflitos_tracos(self):
        """Remove traços que conflitam"""
        conflitos = [
            ("COVARDE", "BERSERKER"), ("MEDROSO", "IMPLACAVEL"),
            ("ESTATICO", "VELOZ"), ("CALCULISTA", "IMPRUDENTE"),
            ("PACIENTE", "FURIOSO"), ("FRIO", "EMOTIVO"),
            ("TEIMOSO", "ADAPTAVEL"),
        ]
        
        for t1, t2 in conflitos:
            if t1 in self.tracos and t2 in self.tracos:
                self.tracos.remove(self.rng.choice([t1, t2]))

    def _gerar_quirks(self):
        """Gera quirks únicos"""
        num_quirks = self.rng.randint(1, 3)
        
        quirks_por_traco = {
            "BERSERKER": ["FURIA_CEGA", "GRITO_GUERRA"],
            "VINGATIVO": ["OLHO_VERMELHO", "PERSISTENTE"],
            "ASSASSINO_NATO": ["FINALIZADOR", "CONTRA_ATAQUE_PERFEITO"],
            "PHOENIX": ["SEGUNDO_FOLEGO", "EXPLOSAO_FINAL"],
            "VAMPIRO": ["VAMPIRICO", "SEDE_SANGUE"],
            "SHOWMAN": ["PROVOCADOR", "DANCA_MORTE"],
            "EVASIVO": ["ESQUIVA_REFLEXA", "INSTINTO_ANIMAL"],
            "PACIENTE": ["PACIENCIA_INFINITA", "CALCULISTA_FRIO"],
        }
        
        self.quirks = []
        
        for traco in self.tracos:
            if traco in quirks_por_traco and self.rng.random() < 0.5:
                quirk = self.rng.choice(quirks_por_traco[traco])
                if quirk not in self.quirks:
                    self.quirks.append(quirk)
        
        while len(self.quirks) < num_quirks:
            quirk = self.rng.choice(list(QUIRKS.keys()))
            if quirk not in self.quirks:
                self.quirks.append(quirk)

    def _calcular_agressividade(self):
        """Calcula agressividade final"""
        agg = self.agressividade_base
        
        if self.filosofia in FILOSOFIAS:
            agg += FILOSOFIAS[self.filosofia]["mod_agressividade"]
        
        tracos_agressivos = ["IMPRUDENTE", "AGRESSIVO", "BERSERKER", "SANGUINARIO", 
                           "PREDADOR", "SELVAGEM", "IMPLACAVEL", "FURIOSO", "BRUTAL"]
        tracos_defensivos = ["COVARDE", "CAUTELOSO", "PACIENTE", "PARANOICO", 
                           "MEDROSO", "PRUDENTE", "EVASIVO"]
        
        for traco in self.tracos:
            if traco in tracos_agressivos:
                agg += 0.08
            elif traco in tracos_defensivos:
                agg -= 0.06
        
        self.agressividade_base = max(0.1, min(0.95, agg))

    def _categorizar_skills(self):
        """Categoriza todas as skills disponíveis (expandido para todos os tipos)"""
        p = self.parent
        
        # Skills da arma (legado)
        if hasattr(p, 'skill_arma_nome') and p.skill_arma_nome and p.skill_arma_nome != "Nenhuma":
            data = get_skill_data(p.skill_arma_nome)
            self._adicionar_skill(p.skill_arma_nome, data, "arma")
        
        # Skills da arma (novo sistema com lista)
        for skill_info in getattr(p, 'skills_arma', []):
            nome = skill_info.get("nome", "Nenhuma")
            if nome != "Nenhuma" and nome != p.skill_arma_nome:  # Evita duplicata
                data = skill_info.get("data", get_skill_data(nome))
                self._adicionar_skill(nome, data, "arma")
        
        # Skills da classe
        if hasattr(p, 'classe_nome') and p.classe_nome:
            class_data = get_class_data(p.classe_nome)
            for skill_nome in class_data.get("skills_afinidade", []):
                data = get_skill_data(skill_nome)
                self._adicionar_skill(skill_nome, data, "classe")
        
        # Skills da classe (novo sistema com lista)
        for skill_info in getattr(p, 'skills_classe', []):
            nome = skill_info.get("nome", "Nenhuma")
            if nome != "Nenhuma":
                data = skill_info.get("data", get_skill_data(nome))
                # Evita duplicatas
                ja_existe = any(s["nome"] == nome for skills in self.skills_por_tipo.values() for s in skills)
                if not ja_existe:
                    self._adicionar_skill(nome, data, "classe")

    def _adicionar_skill(self, nome, data, fonte):
        """Adiciona skill à lista categorizada"""
        tipo = data.get("tipo", "NADA")
        if data.get("ativa_ao_morrer") or data.get("revive_hp_percent"):
            return
        if tipo == "NADA" or tipo not in self.skills_por_tipo:
            return
        
        info = {
            "nome": nome, "data": data, "fonte": fonte,
            "tipo": tipo, "custo": data.get("custo", 15),
        }
        self.skills_por_tipo[tipo].append(info)

    def _aplicar_modificadores_iniciais(self):
        """Define espaçamento e emoção inicial a partir do perfil.

        Era uma sequência de ``if "NOME" in self.tracos`` com multiplicadores
        fixos, o que fazia apenas sete traços terem efeito e tornava dois traços
        opostos aplicarem os dois multiplicadores em sequência. Lendo os eixos,
        todo traço contribui na proporção da sua intensidade e opostos se
        cancelam antes de virar número.

        Os coeficientes estão calibrados para reproduzir os valores antigos nos
        traços que já funcionavam: IMPRUDENTE mantinha alcance ~0,8, AGRESSIVO
        ~0,85, COVARDE ~1,35 e CAUTELOSO ~1,20.
        """
        p = self.parent
        perfil = self.perfil

        espacamento = (
            1.0
            - perfil["agressao"] * 0.25
            + perfil["cautela"] * 0.20
            + perfil["medo"] * 0.25
        )
        p.alcance_ideal *= max(0.5, espacamento)

        # Frieza é o freio das duas emoções: quem é frio não entra quente.
        self.raiva = max(0.0, perfil["agressao"] * 0.35 - perfil["frieza"] * 0.35)
        # Frieza so *suprime* medo; ser esquentado (frieza negativa) nao cria
        # medo do nada -- criaria covardia em quem e furioso.
        self.medo = max(
            0.0, perfil["medo"] * 0.25 - max(0.0, perfil["frieza"]) * 0.25
        )
        self.confianca = min(
            1.0,
            max(0.0, 0.5 + perfil["agressao"] * 0.30 - perfil["medo"] * 0.30),
        )

        # === ONDA 8A: habilidade de leitura e disciplina tática ===
        # Frieza e cautela leem melhor; caos e medo leem pior. Traços e
        # quirks de leitura (que eram strings inertes) agora pagam aqui.
        hab = (
            0.5
            + perfil["frieza"] * 0.25
            + perfil["cautela"] * 0.15
            - perfil["caos"] * 0.20
            - max(0.0, perfil["medo"]) * 0.10
        )
        for traco_leitura in ("LEITURA_PERFEITA", "PREVISOR", "TIMING_PRECISO"):
            if traco_leitura in self.tracos:
                hab += 0.15
        if "LEITURA_CORPORAL" in self.quirks:
            hab += 0.20
        self.habilidade_leitura = max(0.05, min(0.95, hab))

        self.disciplina_tatica = max(0.05, min(0.95, (
            0.5
            + perfil["frieza"] * 0.30
            + perfil["cautela"] * 0.20
            - perfil["caos"] * 0.35
        )))

        # Quem lê bem reage mais rápido: escala o sorteio base (0.12-0.25s)
        # em ±30% mantendo a variância individual já sorteada.
        self.tempo_reacao_base *= 1.3 - self.habilidade_leitura * 0.6

        # Onda 8C: quirks de reflexo saem da lista de strings inertes e
        # viram parâmetros — FRAME_PERFECT amplia a janela de parry que o
        # motor (8B) consulta via mult_janela_parry.
        if "FRAME_PERFECT" in self.quirks:
            self.mult_janela_parry = 1.6

        # Onda 8H: chance de BURST de escape quando comboado (o motor
        # consulta no 3º hit). Cauteloso/medroso compra a saída; teimoso
        # e berserker tankam por orgulho.
        burst = (
            0.35
            + max(0.0, perfil["cautela"]) * 0.3
            + max(0.0, perfil["medo"]) * 0.2
            - max(0.0, perfil["agressao"]) * 0.15
        )
        if "TEIMOSO" in self.tracos:
            burst -= 0.2
        if "BERSERKER" in self.tracos or "KAMIKAZE" in self.tracos:
            burst -= 0.25
        if "EVASIVO" in self.tracos or "REATIVO" in self.tracos:
            burst += 0.15
        self.chance_burst_combo = max(0.05, min(0.9, burst))

    # =========================================================================
    # PROCESSAMENTO PRINCIPAL v10.0
    # =========================================================================
    
    def processar(self, dt, distancia, inimigo):
        """Processa decisões da IA a cada frame com comportamento humano"""
        p = self.parent
        dt = max(0.0, float(dt))
        self._dt_atual = dt
        self.tempo_combate += dt
        
        self._atualizar_cooldowns(dt)
        if self.skill_strategy is not None:
            # O cooldown estratégico acompanha o relógio do combate mesmo
            # quando outro ramo (ataque, reação ou instinto) encerra o frame.
            self.skill_strategy.atualizar(dt)
        self._detectar_dano()
        self._atualizar_emocoes(dt, distancia, inimigo)
        self._atualizar_humor(dt)
        self._processar_modos_especiais(dt, distancia, inimigo)
        
        # === NOVOS SISTEMAS v8.0 ===
        self._atualizar_leitura_oponente(dt, distancia, inimigo)
        self._atualizar_janelas_oportunidade(dt, distancia, inimigo)
        self._atualizar_momentum(dt, distancia, inimigo)
        self._atualizar_estados_humanos(dt, distancia, inimigo)
        self._atualizar_combo_state(dt)
        
        # === SISTEMA ESPACIAL v9.0 ===
        self._atualizar_consciencia_espacial(dt, distancia, inimigo)
        
        # === SISTEMA DE PERCEPÇÃO DE ARMAS v10.0 ===
        self._atualizar_percepcao_armas(dt, distancia, inimigo)
        
        # === NOVOS SISTEMAS v11.0 ===
        self._atualizar_ritmo(dt)

        # === ONDA 8E: PLANO DE LUTA ===
        self._atualizar_plano(dt, distancia, inimigo)
        # Onda 5B: instinto escreve com prioridade 1 (interrompe qualquer
        # hold) e emite tell — dado puro que o renderer consome.
        self._contexto_escrita = 1
        try:
            if self._processar_instintos(dt, distancia, inimigo):
                self.tell_atual = {"tipo": "instinto",
                                   "ate": self.tempo_combate + 0.4}
                return  # Instinto tomou controle

            # === ONDA 8C: DESVIO INTELIGENTE (religado) ===
            # O subsistema v8.0 completo (trajetória+ETA, direção
            # perpendicular, timing humano) existia morto desde a v8.
            # Roda ANTES do coreógrafo: desviar de uma bola de fogo
            # vence qualquer momento cinematográfico. O cooldown por
            # personalidade (0.8-2.0s) protege o alvo V2 — desvio é
            # evento de urgência, não opção por tick.
            if self.cd_desvio <= 0 and self._processar_desvio_inteligente(
                dt, distancia, inimigo
            ):
                mob = max(0.0, self.perfil.get("mobilidade", 0.0))
                cd = 2.0 - 0.6 * mob - 0.6 * self.habilidade_leitura
                if "ESQUIVA_REFLEXA" in self.quirks:
                    cd *= 0.7  # quirk inerte ativado: reflexo de esquiva
                self.cd_desvio = max(0.8, cd)
                contadores_luta = getattr(p, "contadores_luta", None)
                if contadores_luta is not None:
                    contadores_luta["desvios_ia"] = (
                        contadores_luta.get("desvios_ia", 0) + 1
                    )
                    # Onda 8D: desvio iniciado no WIND-UP do oponente —
                    # o momento visível "ela leu o golpe" (alvo A3).
                    if self._observar(inimigo).fase_ataque == FASE_PREPARANDO:
                        contadores_luta["desvios_antecipados"] = (
                            contadores_luta.get("desvios_antecipados", 0) + 1
                        )
                self.tell_atual = {"tipo": "desvio",
                                   "ate": self.tempo_combate + 0.4}
                return

            # === ONDA 8D: PUNIÇÃO DE WHIFF ===
            # Recovery lido no corpo do oponente (ou janela pós-esquiva/
            # pós-parry) → castigo deliberado. Prioridade logo abaixo do
            # desvio: primeiro não morrer, depois punir.
            if self.cd_punicao <= 0 and self._processar_punicao_whiff(
                dt, distancia, inimigo
            ):
                self.cd_punicao = 2.5
                contadores_luta = getattr(p, "contadores_luta", None)
                if contadores_luta is not None:
                    contadores_luta["punicoes"] = (
                        contadores_luta.get("punicoes", 0) + 1
                    )
                self.tell_atual = {"tipo": "punicao",
                                   "ate": self.tempo_combate + 0.4}
                return
        finally:
            self._contexto_escrita = 2

        # Hesitação humana - às vezes congela brevemente
        if self._verificar_hesitacao(dt, distancia, inimigo):
            self.tell_atual = {"tipo": "hesitacao",
                               "ate": self.tempo_combate + 0.35}
            return
        
        # Sistema de Coreografia
        self._observar_oponente(inimigo, distancia)
        
        choreographer = p.choreographer
        acao_sync = choreographer.get_acao_sincronizada(p)
        
        if acao_sync and self._aceita_direcao(acao_sync):
            if self._executar_acao_sincronizada(acao_sync, distancia, inimigo):
                return
        
        # Processa baiting (fintas)
        if self._processar_baiting(dt, distancia, inimigo):
            return
        
        if self._processar_reacao_oponente(dt, distancia, inimigo):
            return
        
        # === PRIORIZAÇÃO DE SKILLS PARA MAGOS ===
        # Se o personagem é um caster (role de mago), prioriza skills sobre ataques básicos
        usa_skills_primeiro = False
        if self.skill_strategy is not None:
            role = self.skill_strategy.role_principal.value
            if role in ["artillery", "burst_mage", "control_mage", "summoner", "buffer", "channeler"]:
                usa_skills_primeiro = True
        
        if usa_skills_primeiro:
            # Magos: Skills primeiro, depois ataque básico
            if self._processar_skills(dt, distancia, inimigo):
                return
            if self._avaliar_e_executar_ataque(dt, distancia, inimigo):
                return
        else:
            # Melee: Ataque primeiro, skills como suporte
            if self._avaliar_e_executar_ataque(dt, distancia, inimigo):
                return
            if self._processar_skills(dt, distancia, inimigo):
                return
        
        self.timer_decisao -= dt
        if self.timer_decisao <= 0:
            self._decidir_movimento(distancia, inimigo)
            self._calcular_timer_decisao()
            self._registrar_acao()

    # =========================================================================
    # SISTEMA DE LEITURA DO OPONENTE v8.0
    # =========================================================================
    
    def _observar(self, inimigo):
        """Funil único de observação HONESTA do oponente (Onda 8A).

        Substitui a telepatia (ler ``inimigo.brain.acao_atual``): tudo
        aqui vem de estado fisicamente observável — posição, velocidade
        e a fase da animação de ataque. A habilidade de leitura da
        personalidade paga em dois lugares:

        - latência: amostra o histórico 0-3 frames atrás;
        - má-leitura: um sorteio POR GOLPE (``ataque_id`` é público e
          incrementa a cada swing) — quem lê mal não enxerga o wind-up
          e só percebe o golpe quando ele já está ativo.

        Cache por frame: vários subsistemas consultam no mesmo tick.
        Fakes de contrato (object.__new__ sem __init__) são tolerados
        via acesso preguiçoso — mesmo padrão do motor emocional.
        """
        tempo = getattr(self, "tempo_combate", 0.0)
        if (
            self.__dict__.get("_obs_cache") is not None
            and self.__dict__.get("_obs_cache_tempo") == tempo
        ):
            return self._obs_cache
        habilidade = getattr(self, "habilidade_leitura", 0.5)
        atraso = int(round((1.0 - habilidade) * 3.0))
        obs = construir_observacao(
            getattr(self, "parent", None), inimigo, atraso_frames=atraso
        )
        if obs.atacando and obs.ataque_id != self.__dict__.get("_obs_ataque_id_visto", -1):
            self._obs_ataque_id_visto = obs.ataque_id
            self._obs_ataque_mal_lido = (
                self.rng.random() < (1.0 - habilidade) * 0.35
            )
        if self.__dict__.get("_obs_ataque_mal_lido") and obs.fase_ataque == FASE_PREPARANDO:
            obs.fase_ataque = None
            obs.tempo_para_impacto = None
            obs.intencao = (
                "parado" if math.hypot(obs.vel[0], obs.vel[1]) < 0.8 else "avancando"
            )
        self._obs_cache = obs
        self._obs_cache_tempo = tempo
        return obs

    def _atualizar_leitura_oponente(self, dt, distancia, inimigo):
        """Lê e antecipa os movimentos do oponente como um humano faria"""
        leitura = self.leitura_oponente
        obs = self._observar(inimigo)

        # Onda 8A: "ataque iminente" agora é o telegraph REAL da animação
        # (wind-up/golpe ativo), não mais o proxy cooldown_ataque < 0.2
        # que era verdadeiro quase sempre, nem a intenção telepática.
        leitura["ataque_iminente"] = obs.fase_ataque in (
            FASE_PREPARANDO, FASE_GOLPEANDO
        )
        # Campo declarado desde a v8.0 e nunca escrito: segundos até o
        # centro da janela de impacto do golpe em curso (0.0 sem golpe).
        leitura["tempo_para_ataque"] = obs.tempo_para_impacto or 0.0
        
        # Calcula direção provável do ataque
        if inimigo.vel[0] != 0 or inimigo.vel[1] != 0:
            leitura["direcao_provavel"] = math.degrees(math.atan2(inimigo.vel[1], inimigo.vel[0]))
        
        # Registra padrão de movimento
        mov_atual = (inimigo.vel[0], inimigo.vel[1], inimigo.z)
        leitura["padrao_movimento"].append(mov_atual)
        if len(leitura["padrao_movimento"]) > 15:
            leitura["padrao_movimento"].pop(0)
        
        # Analisa tendência lateral
        if len(leitura["padrao_movimento"]) >= 5:
            lateral_sum = sum(m[0] for m in leitura["padrao_movimento"][-5:])
            if lateral_sum > 0:
                leitura["tendencia_esquerda"] = max(0.2, leitura["tendencia_esquerda"] - 0.02)
            else:
                leitura["tendencia_esquerda"] = min(0.8, leitura["tendencia_esquerda"] + 0.02)
        
        # Detecta frequência de pulos
        pulos_recentes = sum(1 for m in leitura["padrao_movimento"] if m[2] > 0)
        leitura["frequencia_pulo"] = pulos_recentes / max(1, len(leitura["padrao_movimento"]))
        
        # Calcula previsibilidade do oponente
        if len(leitura["padrao_movimento"]) >= 8:
            # Compara movimentos consecutivos - mais similares = mais previsível
            variacoes = []
            for i in range(1, min(8, len(leitura["padrao_movimento"]))):
                m1 = leitura["padrao_movimento"][-i]
                m2 = leitura["padrao_movimento"][-i-1]
                var = abs(m1[0] - m2[0]) + abs(m1[1] - m2[1])
                variacoes.append(var)
            media_var = sum(variacoes) / len(variacoes) if variacoes else 1.0
            leitura["previsibilidade"] = max(0.1, min(0.9, 1.0 - (media_var / 20.0)))
        
        # Percebe agressividade do oponente pelo que ele FAZ (Onda 8A):
        # avanço/golpe sobe o medidor, recuo desce.
        if obs.agressivo:
            leitura["agressividade_percebida"] = min(1.0, leitura["agressividade_percebida"] + 0.03)
        elif obs.intencao == "recuando":
            leitura["agressividade_percebida"] = max(0.0, leitura["agressividade_percebida"] - 0.02)

        # Onda 8D: ritmo de golpes por EMA de intervalos entre swings
        # (evento: ataque_id incrementa por golpe — nada por frame).
        # Alimenta memoria_oponente["padrao_detectado"], escrito desde a
        # v8 e nunca preenchido: oponente rítmico é oponente punível.
        if obs.atacando and obs.ataque_id != leitura.get("_ultimo_swing_id"):
            leitura["_ultimo_swing_id"] = obs.ataque_id
            t_anterior = leitura.get("_t_ultimo_swing")
            leitura["_t_ultimo_swing"] = self.tempo_combate
            if t_anterior is not None:
                intervalo = self.tempo_combate - t_anterior
                ema = leitura.get("ritmo_golpes_s")
                if ema is None:
                    leitura["ritmo_golpes_s"] = intervalo
                else:
                    leitura["ritmo_golpes_s"] = ema * 0.7 + intervalo * 0.3
                    self.memoria_oponente["padrao_detectado"] = (
                        "ritmico" if abs(intervalo - ema) < 0.3 else "erratico"
                    )
    
    # =========================================================================
    # SISTEMA DE DESVIO INTELIGENTE v8.0
    # =========================================================================
    
    def _processar_desvio_inteligente(self, dt, distancia, inimigo):
        """Sistema de desvio avançado com antecipação e timing humano"""
        leitura = self.leitura_oponente
        
        # Não desvia se estiver em berserk ou muito confiante
        if self.modo_berserk:
            return False
        if self.confianca > 0.85 and "IMPRUDENTE" in self.tracos:
            return False
        
        # Detecta necessidade de desvio
        desvio_necessario = False
        tipo_desvio = None
        urgencia = 0.0

        # 1. Ataque físico iminente — Onda 8C: UMA avaliação por golpe
        # inimigo (ataque_id é público e incrementa por swing). Sem isso
        # o gate rolava todo frame do wind-up e o desvio virava spam
        # (~21/luta no smoke) em vez de reação pontual ao golpe.
        if leitura["ataque_iminente"] and distancia < 3.5:
            ataque_id = getattr(inimigo, "ataque_id", 0)
            if ataque_id != getattr(self, "_ataque_id_avaliado_desvio", -1):
                self._ataque_id_avaliado_desvio = ataque_id
                desvio_necessario = True
                tipo_desvio = "ATAQUE_FISICO"
                urgencia = 1.0 - (distancia / 3.5)
        
        # 2. Projéteis vindo
        projetil_info = self._analisar_projeteis_vindo(inimigo)
        if projetil_info["vindo"]:
            desvio_necessario = True
            tipo_desvio = "PROJETIL"
            urgencia = max(urgencia, projetil_info["urgencia"])
        
        # 3. Área de dano
        area_info = self._analisar_areas_perigo(inimigo)
        if area_info["perigo"]:
            desvio_necessario = True
            tipo_desvio = "AREA"
            urgencia = max(urgencia, area_info["urgencia"])
        
        if not desvio_necessario:
            return False
        
        ve_ataques = getattr(self.parent, "ve_ataques_hostis", None)
        previsao_ativa = callable(ve_ataques) and bool(ve_ataques())

        if not previsao_ativa:
            # Sem Previsão, preserva o timing humano e a chance de hesitar.
            tempo_reacao = self.tempo_reacao_base + self.rng.uniform(
                -self.variacao_timing,
                self.variacao_timing,
            )

            # Traços afetam tempo de reação
            if "REATIVO" in self.tracos or "EVASIVO" in self.tracos:
                tempo_reacao *= 0.7
            if "ESTATICO" in self.tracos:
                tempo_reacao *= 1.5
            if "REFLEXOS_DIVINOS" in self.quirks:
                # Onda 8C: quirk inerte ativado — reflexo sobre-humano.
                tempo_reacao *= 0.4
            if self.adrenalina > 0.6:
                tempo_reacao *= 0.8
            if self.medo > 0.5:
                tempo_reacao *= 0.85  # Medo aumenta reflexos
            if self.congelamento > 0.3:
                tempo_reacao *= 1.5  # Congela sob pressão

            # Chance de reagir baseado na urgência vs tempo de reação
            chance_reagir = urgencia * (1.0 - tempo_reacao)

            # Personalidade afeta chance
            if "ACROBATA" in self.tracos:
                chance_reagir += 0.2
            if "PACIENTE" in self.tracos:
                chance_reagir += 0.1
            if "IMPRUDENTE" in self.tracos:
                chance_reagir -= 0.15

            # Onda 8C: normalizado por dt (norma do projeto) — o roll era
            # por frame no código morto e ficaria mais frequente em FPS
            # maior.
            if not self._chance_temporal(chance_reagir):
                return False
        
        # Decide direção do desvio
        direcao_desvio = self._calcular_direcao_desvio(tipo_desvio, distancia, inimigo, projetil_info)
        
        # Executa o desvio
        return self._executar_desvio(tipo_desvio, direcao_desvio, urgencia, distancia, inimigo)
    
    def _processar_punicao_whiff(self, dt, distancia, inimigo):
        """Onda 8D: pune o golpe errado — antecipação virando ofensa.

        Duas fontes de oportunidade, ambas OBSERVÁVEIS:
        - o oponente está na fase de recovery do próprio golpe (lido do
          corpo via timer_animacao + perfil da arma, nunca da mente);
        - a janela pós-esquiva/pós-parry aberta pelos eventos do motor.

        A chance escala com habilidade_leitura e ativa os quirks de
        punição que eram strings inertes (WHIFF_PUNISHER,
        LEITURA_CORPORAL, MESTRE_DISTANCIA). Oponente rítmico
        (padrao_detectado da 8D) é mais punível.
        """
        obs = self._observar(inimigo)
        janela = self.janela_ataque
        janela_boa = bool(janela.get("aberta")) and janela.get("tipo") in (
            "pos_esquiva", "pos_parry"
        )
        # Recovery punível = golpe que NÃO me acertou (whiff de verdade,
        # tempo_desde_dano guarda isso) com tempo restante para o step-in.
        # UMA avaliação por swing (ataque_id), como no gate de desvio —
        # sem isso a punição rolava todo frame do recovery e virava spam
        # (12/luta no smoke, V2 no limite).
        # 0.12s é o mínimo humano para o step-in: pune espadas/correntes/
        # arcos; adagas (recovery 0.065s) seguem seguras por design.
        recovery_lido = (
            obs.fase_ataque == FASE_RECUPERANDO
            and (obs.tempo_para_fim or 0.0) > 0.12
            and self.tempo_desde_dano > 0.5
        )
        if recovery_lido:
            if obs.ataque_id == getattr(self, "_ataque_id_avaliado_punicao", -1):
                recovery_lido = False
            else:
                self._ataque_id_avaliado_punicao = obs.ataque_id
        if not (janela_boa or recovery_lido):
            return False

        alcance = self._calcular_alcance_efetivo()
        if distancia > alcance * 1.2 + 1.0:
            return False  # longe demais para chegar dentro da janela

        chance = 0.15 + 0.35 * self.habilidade_leitura
        if "WHIFF_PUNISHER" in self.quirks or "LEITURA_CORPORAL" in self.quirks:
            chance += 0.2
        if "MESTRE_DISTANCIA" in self.quirks:
            chance += 0.1
        if self.memoria_oponente.get("padrao_detectado") == "ritmico":
            chance += 0.1
        if self.medo > 0.7:
            chance *= 0.5  # apavorado não dá step-in

        # Recovery é avaliado uma vez por swing (roll seco); a janela
        # pós-esquiva/parry persiste frames (roll normalizado por dt).
        if recovery_lido:
            passou = self.rng.random() < min(0.95, chance)
        else:
            passou = self._chance_temporal(min(0.95, chance))
        if not passou:
            return False

        self.acao_atual = "CONTRA_ATAQUE"
        return True

    def _analisar_projeteis_vindo(self, inimigo):
        """Analisa projéteis vindo em direção ao lutador.

        Onda 8A: lia os buffers do inimigo (drenados pelo Simulador antes
        do tick das IAs — sempre vazios). Agora lê a janela de mundo
        compartilhada (``percepcao``); orbes seguem no lutador porque o
        buffer deles não é drenado.
        """
        p = self.parent
        resultado = {"vindo": False, "urgencia": 0.0, "direcao": 0.0, "tempo_impacto": 999.0}
        percepcao = getattr(p, "percepcao", None)

        # Verifica projéteis
        if percepcao is not None:
            for proj in percepcao.projeteis_hostis(p):
                dx = p.pos[0] - proj.x
                dy = p.pos[1] - proj.y
                dist = math.hypot(dx, dy)
                
                if dist > 8.0:
                    continue
                
                # Calcula se está vindo na minha direção
                ang_para_mim = math.degrees(math.atan2(dy, dx))
                ang_proj = getattr(proj, 'angulo', 0)
                diff_ang = abs(normalizar_angulo(ang_para_mim - ang_proj))
                
                if diff_ang < 45:  # Vindo na minha direção
                    vel_proj = getattr(proj, 'vel', 10.0)
                    tempo_impacto = dist / vel_proj
                    
                    if tempo_impacto < resultado["tempo_impacto"]:
                        resultado["vindo"] = True
                        resultado["tempo_impacto"] = tempo_impacto
                        resultado["urgencia"] = max(0.3, 1.0 - tempo_impacto / 1.0)
                        resultado["direcao"] = ang_proj
        
        # Verifica orbes
        if hasattr(inimigo, 'buffer_orbes'):
            for orbe in inimigo.buffer_orbes:
                if not orbe.ativo or orbe.estado != "disparando":
                    continue
                
                dx = p.pos[0] - orbe.x
                dy = p.pos[1] - orbe.y
                dist = math.hypot(dx, dy)
                
                if dist < 5.0:
                    resultado["vindo"] = True
                    resultado["urgencia"] = max(resultado["urgencia"], 0.8)
                    resultado["direcao"] = math.degrees(math.atan2(-dy, -dx))
        
        # Verifica beams
        if percepcao is not None:
            for beam in percepcao.beams_hostis(p):
                # Simplificação: se beam está ativo e perto, é perigo
                dist = math.hypot(p.pos[0] - beam.x1, p.pos[1] - beam.y1)
                alcance = math.hypot(beam.x2 - beam.x1, beam.y2 - beam.y1)
                if dist < alcance + 1.0:
                    resultado["vindo"] = True
                    resultado["urgencia"] = max(resultado["urgencia"], 0.9)

        return resultado

    def _analisar_areas_perigo(self, inimigo):
        """Analisa áreas de dano próximas (Onda 8A: via percepção de mundo)."""
        p = self.parent
        resultado = {"perigo": False, "urgencia": 0.0}
        percepcao = getattr(p, "percepcao", None)

        if percepcao is not None:
            for area in percepcao.areas_hostis(p):
                dist = math.hypot(p.pos[0] - area.x, p.pos[1] - area.y)
                raio = getattr(area, 'raio', 2.0)
                
                if dist < raio + 1.5:  # Dentro ou perto da área
                    resultado["perigo"] = True
                    resultado["urgencia"] = max(resultado["urgencia"], 1.0 - dist / (raio + 1.5))
        
        return resultado
    
    def _calcular_direcao_desvio(self, tipo_desvio, distancia, inimigo, projetil_info):
        """Calcula a melhor direção para desviar"""
        p = self.parent
        leitura = self.leitura_oponente
        
        # Direção base: perpendicular ao ataque
        if tipo_desvio == "PROJETIL" and projetil_info.get("direcao"):
            ang_ataque = projetil_info["direcao"]
        else:
            ang_ataque = math.degrees(math.atan2(
                p.pos[1] - inimigo.pos[1], 
                p.pos[0] - inimigo.pos[0]
            )) + 180
        
        # Perpendicular: +90 ou -90
        opcao1 = ang_ataque + 90
        opcao2 = ang_ataque - 90

        # Onda 8C: ordem consertada — na versão morta o dir_circular
        # SEMPRE sobrescrevia a leitura do oponente (o código acima dele
        # era letra morta). Agora o hábito próprio é o ponto de partida
        # e a LEITURA (para onde o oponente tende a ir) o corrige.
        escolha = opcao1 if self.dir_circular > 0 else opcao2
        if leitura["tendencia_esquerda"] > 0.6:
            escolha = opcao2  # Oponente tende à esquerda: vou pra direita
        elif leitura["tendencia_esquerda"] < 0.4:
            escolha = opcao1

        # Adiciona variação humana
        escolha += self.rng.uniform(-20, 20)

        # Se HP baixo, prioriza recuar
        hp_pct = p.vida / p.vida_max
        if hp_pct < 0.3:
            # Mistura desvio com recuo
            ang_recuo = math.degrees(math.atan2(
                p.pos[1] - inimigo.pos[1],
                p.pos[0] - inimigo.pos[0]
            ))
            escolha = (escolha + ang_recuo) / 2

        # Onda 8C: ninguém desvia para DENTRO da parede — o sistema
        # espacial testa a direção e busca alternativa (12 ângulos).
        espacial = self._sistema_espacial()
        if espacial is not None:
            escolha = espacial.ajustar_direcao(escolha, self.tracos)

        return escolha
    
    def _executar_desvio(self, tipo_desvio, direcao, urgencia, distancia, inimigo):
        """Executa o desvio escolhido.

        Onda 8C: além dos caminhos originais (skill de dash, pulo,
        impulso lateral), o desvio agora escolhe entre as mecânicas da
        Onda 8B — ERGUER A GUARDA contra golpe físico (arma pesada e
        personalidade cautelosa preferem bloquear; o motor decide se o
        timing valeu um parry) e o DASH UNIVERSAL como escape rápido.
        """
        p = self.parent

        # Guarda como desvio: ameaça física de frente + estilo defensivo.
        if tipo_desvio == "ATAQUE_FISICO":
            arma = getattr(getattr(p, "dados", None), "arma_obj", None)
            peso_arma = float(getattr(arma, "peso", 3.0) or 3.0)
            prefere_guarda = (
                peso_arma >= 5.0
                or self.perfil.get("cautela", 0.0) > 0.15
                or self.perfil.get("agressao", 0.0) < -0.2
                or "FRAME_PERFECT" in self.quirks
            )
            if (
                prefere_guarda
                and getattr(p, "estamina", 0.0) >= 20.0
                and self.rng.random() < 0.75
            ):
                self.acao_atual = "BLOQUEAR"
                return True

        # Tipo de desvio baseado na urgência e situação
        if urgencia > 0.8 or tipo_desvio == "AREA":
            # Desvio urgente - dash se disponível
            if self.cd_dash <= 0:
                dash_skills = self.skills_por_tipo.get("DASH", [])
                for skill in dash_skills:
                    # Ajusta ângulo de olhar temporariamente para dash
                    ang_original = p.angulo_olhar
                    p.angulo_olhar = direcao
                    if self._usar_skill(skill):
                        p.angulo_olhar = ang_original
                        self.cd_dash = 2.0
                        self.acao_atual = "DESVIO"
                        return True
                    p.angulo_olhar = ang_original

            # Onda 8C: dash universal (8B) — o escape de todo lutador.
            iniciar_dash = getattr(p, "iniciar_dash", None)
            if callable(iniciar_dash) and iniciar_dash(math.radians(direcao)):
                self.acao_atual = "DESVIO"
                return True

            # Sem dash, tenta pulo
            if p.z == 0 and self.cd_pulo <= 0:
                p.vel_z = self.rng.uniform(10.0, 14.0)
                self.cd_pulo = 1.0
                # Move lateralmente também
                rad = math.radians(direcao)
                p.vel[0] += math.cos(rad) * 15.0
                p.vel[1] += math.sin(rad) * 15.0
                self.acao_atual = "DESVIO"
                return True
        
        # Desvio normal - movimento lateral
        if urgencia > 0.4:
            rad = math.radians(direcao)
            impulso = 20.0 * urgencia
            p.vel[0] += math.cos(rad) * impulso
            p.vel[1] += math.sin(rad) * impulso
            
            # Define ação
            if distancia > 4.0:
                self.acao_atual = "CIRCULAR"
            else:
                self.acao_atual = "FLANQUEAR"
            
            return True
        
        # Desvio sutil - apenas ajuste de posição (normalizado por dt, 8C)
        if self._chance_temporal(urgencia):
            self.acao_atual = "CIRCULAR"
            return True

        return False
    
    # =========================================================================
    # SISTEMA DE JANELAS DE OPORTUNIDADE v8.0
    # =========================================================================
    
    def _atualizar_janelas_oportunidade(self, dt, distancia, inimigo):
        """Detecta janelas de oportunidade para atacar"""
        janela = self.janela_ataque
        
        # Decrementa duração da janela atual
        if janela["aberta"]:
            janela["duracao"] -= dt
            if janela["duracao"] <= 0:
                janela["aberta"] = False
                janela["tipo"] = None
                # Sem zerar a qualidade, uma janela boa (stun, 1.0) travava
                # para sempre todas as janelas futuras de qualidade menor: o
                # filtro compara com a MELHOR qualidade ja vista.
                janela["qualidade"] = 0.0
        
        # Detecta novas janelas
        nova_janela = False
        tipo_janela = None
        qualidade = 0.0
        duracao = 0.0
        
        # 1. Pós-ataque do oponente (recovery)
        if hasattr(inimigo, 'atacando') and not inimigo.atacando:
            if hasattr(inimigo, 'cooldown_ataque') and 0.1 < inimigo.cooldown_ataque < 0.6:
                nova_janela = True
                tipo_janela = "pos_ataque"
                qualidade = 0.8
                duracao = inimigo.cooldown_ataque
        
        # 2. Oponente usando skill (channeling)
        if hasattr(inimigo, 'canalizando') and inimigo.canalizando:
            nova_janela = True
            tipo_janela = "canalizando"
            qualidade = 0.9
            duracao = 1.0
        
        # 3. Oponente no ar (menos mobilidade)
        if hasattr(inimigo, 'z') and inimigo.z > 0.5:
            nova_janela = True
            tipo_janela = "aereo"
            qualidade = 0.6
            duracao = 0.5
        
        # 4. Oponente stunado ou lento
        if hasattr(inimigo, 'stun_timer') and inimigo.stun_timer > 0:
            nova_janela = True
            tipo_janela = "stunado"
            qualidade = 1.0
            duracao = inimigo.stun_timer
        
        # 5. Oponente com estamina baixa
        if hasattr(inimigo, 'estamina') and inimigo.estamina < 20:
            nova_janela = True
            tipo_janela = "exausto"
            qualidade = 0.7
            duracao = 1.5
        
        # 6. Oponente recuando (costas viradas parcialmente) — Onda 8A:
        # observado pela velocidade real, não pela intenção telepática.
        if self._observar(inimigo).intencao == "recuando":
            nova_janela = True
            tipo_janela = "recuando"
            qualidade = 0.75
            duracao = 0.8
        
        # 7. Oponente usou skill de mana alta (esperando cooldown)
        if hasattr(inimigo, 'cd_skill_arma') and inimigo.cd_skill_arma > 2.0:
            nova_janela = True
            tipo_janela = "skill_cd"
            qualidade = 0.65
            duracao = min(2.0, inimigo.cd_skill_arma)
        
        # Atualiza janela se encontrou uma melhor
        if nova_janela and qualidade > janela.get("qualidade", 0):
            janela["aberta"] = True
            janela["tipo"] = tipo_janela
            janela["qualidade"] = qualidade
            janela["duracao"] = duracao
    
    # =========================================================================
    # SISTEMA DE ATAQUE INTELIGENTE v8.0
    # =========================================================================
    
    def _avaliar_e_executar_ataque(self, dt, distancia, inimigo):
        """Avalia se deve atacar e como - v12.2 MELHORADO"""
        p = self.parent
        janela = self.janela_ataque
        combo = self.combo_state
        
        # Calcula alcance efetivo baseado na arma
        alcance_efetivo = self._calcular_alcance_efetivo()
        no_alcance = distancia <= alcance_efetivo * 1.1  # 10% de margem
        
        # Se está em combo, tenta continuar
        if combo["em_combo"] and combo["pode_followup"]:
            if self._tentar_followup(distancia, inimigo):
                return True
        
        # === ATAQUE DIRETO SE NO ALCANCE E NÃO ATACANDO ===
        if no_alcance and not p.atacando:
            # Chance base de atacar quando no alcance
            chance_base = 0.6
            
            # Aumenta chance se inimigo com pouca vida
            if inimigo.vida / inimigo.vida_max < 0.3:
                chance_base = 0.85
                # Onda 8F: CALCULO_MORTAL sai da lista de quirks inertes —
                # quem calcula o abate não deixa a janela letal passar.
                if "CALCULO_MORTAL" in self.quirks:
                    chance_base = 0.98
            
            # Modificadores de personalidade
            if "AGRESSIVO" in self.tracos or "BERSERKER" in self.tracos:
                chance_base += 0.2
            if "CAUTELOSO" in self.tracos:
                chance_base -= 0.15
            if "OPORTUNISTA" in self.tracos:
                chance_base += 0.1
            
            # Momentum
            chance_base += self.momentum * 0.15

            # Onda 8H: alvo em HITSTUN é a janela de combo — pressiona.
            # (stun é estado físico visível, não telepatia.)
            if getattr(inimigo, "stun_timer", 0.0) > 0.0:
                chance_base = max(chance_base, 0.95)

            if self.rng.random() < chance_base:
                self._executar_ataque(distancia, inimigo)
                # Onda 8E (fix do melee): consome o frame só quando o
                # golpe pode DE FATO sair agora. Com o cooldown rolando,
                # a intenção ofensiva fica escrita (o motor golpeia
                # quando ela abrir) mas a decisão de movimento continua
                # viva — antes, este return incondicional congelava a
                # pilha de personalidade durante TODO o tempo em range
                # de melee, e o lutador virava um loop de rolagem de
                # ataque sem espaçamento, flanco ou recuo.
                if p.cooldown_ataque <= 0 and not p.atacando:
                    return True
                return False
        
        # Verifica se tem janela de oportunidade
        if janela["aberta"]:
            # Calcula se vale a pena atacar
            chance_ataque = janela["qualidade"]
            
            # Modificadores de distância
            if distancia > alcance_efetivo * 1.5:
                chance_ataque *= 0.3  # Longe demais
            elif distancia > alcance_efetivo:
                chance_ataque *= 0.7  # Um pouco longe
            elif distancia < p.alcance_ideal * 0.5:
                chance_ataque *= 1.3  # Muito perto, aproveita
            
            # Personalidade
            if "OPORTUNISTA" in self.tracos:
                chance_ataque *= 1.3
            if "CALCULISTA" in self.tracos:
                chance_ataque *= 1.2 if janela["qualidade"] > 0.7 else 0.8
            if "PACIENTE" in self.tracos:
                chance_ataque *= 0.9 if janela["qualidade"] < 0.8 else 1.1
            
            # Momentum
            chance_ataque += self.momentum * 0.2
            
            # Emoções
            if self.raiva > 0.5:
                chance_ataque *= 1.2
            if self.medo > 0.6:
                chance_ataque *= 0.7
            
            if self.rng.random() < chance_ataque:
                # Decide tipo de ataque baseado na janela
                return self._executar_ataque_oportunidade(janela, distancia, inimigo)
        
        return False
    
    def _executar_ataque_oportunidade(self, janela, distancia, inimigo):
        """Executa ataque aproveitando janela de oportunidade"""
        tipo = janela["tipo"]
        # Escolhe ação baseado no tipo de janela
        if tipo == "pos_ataque":
            # Contra-ataque rápido
            self.acao_atual = "CONTRA_ATAQUE"
            self.excitacao = min(1.0, self.excitacao + 0.2)
            return True
        
        elif tipo == "canalizando":
            # Interrompe com ataque pesado
            self.acao_atual = "ESMAGAR"
            return True
        
        elif tipo == "aereo":
            # Anti-air
            self.acao_atual = "ATAQUE_RAPIDO"
            return True
        
        elif tipo == "stunado":
            # Combo pesado
            self.acao_atual = "MATAR"
            self.modo_burst = True
            return True
        
        elif tipo == "exausto":
            # Pressiona
            self.acao_atual = "PRESSIONAR"
            return True
        
        elif tipo == "recuando":
            # Persegue
            self.acao_atual = "APROXIMAR"
            self.confianca = min(1.0, self.confianca + 0.1)
            return True
        
        elif tipo == "skill_cd":
            # Aproveita cooldown
            self.acao_atual = "MATAR"
            return True
        
        return False
    
    def _executar_ataque(self, distancia, inimigo):
        """Executa um ataque baseado na distância e situação - v12.2"""
        # Usa alcance efetivo calculado
        alcance_efetivo = self._calcular_alcance_efetivo()
        
        # Escolhe tipo de ataque baseado na distância relativa ao alcance
        if distancia <= alcance_efetivo * 0.5:
            # Muito perto - ataque rápido
            self.acao_atual = "ATAQUE_RAPIDO"
        elif distancia <= alcance_efetivo:
            # Dentro do alcance - ataque normal
            if self.rng.random() < 0.6:
                self.acao_atual = "MATAR"
            else:
                self.acao_atual = "ATAQUE_RAPIDO"
        elif distancia <= alcance_efetivo * 1.3:
            # Quase no alcance - pressiona
            if self.rng.random() < 0.5:
                self.acao_atual = "PRESSIONAR"
            else:
                self.acao_atual = "APROXIMAR"
        else:
            # Longe - aproxima
            self.acao_atual = "APROXIMAR"
        
        # Seta flag de ataque diretamente (não existe método iniciar_ataque)
        if distancia <= alcance_efetivo * 1.1:
            # O ataque é executado via executar_ataques() em entities.py
            # Basta garantir que a ação seja ofensiva
            if self.acao_atual not in ["MATAR", "ESMAGAR", "COMBATE", "ATAQUE_RAPIDO", "PRESSIONAR", "CONTRA_ATAQUE", "POKE"]:
                self.acao_atual = "MATAR"
    
    def _tentar_followup(self, distancia, inimigo):
        """Tenta continuar combo"""
        combo = self.combo_state
        
        if combo["timer_followup"] <= 0:
            combo["em_combo"] = False
            combo["pode_followup"] = False
            return False
        
        # Onda 8H: a string agora LÊ o estado mecânico — alvo em hitstun
        # ou com o MEU combo ativo nele é alvo vulnerável de verdade
        # (antes o followup era uma cadeia de Markov cega).
        p = self.parent
        alvo_vulneravel = (
            getattr(inimigo, "stun_timer", 0.0) > 0.0
            or (
                getattr(inimigo, "combo_contra_autor", None) is p
                and getattr(inimigo, "combo_contra_timer", 0.0) > 0.0
            )
        )

        # Determina próximo ataque do combo
        ultimo = combo["ultimo_tipo_ataque"]
        proximo = None

        arma = getattr(getattr(p, "dados", None), "arma_obj", None)
        peso_arma = float(getattr(arma, "peso", 3.0) or 3.0)
        if peso_arma >= 6.0 and combo["hits_combo"] >= 2 and alvo_vulneravel:
            # Arma pesada fecha a string com o finisher — identidade de
            # classe: o bruto não emenda quatro golpes, ele TERMINA.
            proximo = "ESMAGAR"
        elif ultimo == "ATAQUE_RAPIDO":
            proximo = self.rng.choice(["ATAQUE_RAPIDO", "MATAR"])
        elif ultimo == "MATAR":
            proximo = self.rng.choice(["ESMAGAR", "ATAQUE_RAPIDO"])
        elif ultimo == "ESMAGAR":
            proximo = self.rng.choice(["MATAR", "FLANQUEAR"])
        else:
            proximo = "ATAQUE_RAPIDO"

        # Verifica distância
        if distancia > p.alcance_ideal + 1.5:
            combo["em_combo"] = False
            return False

        self.acao_atual = proximo
        combo["hits_combo"] += 1
        combo["ultimo_tipo_ataque"] = proximo
        # Janela para o próximo hit: maior quando o alvo está de fato
        # sem resposta (hitstun/combo ativo).
        combo["timer_followup"] = 0.4 + (0.25 if alvo_vulneravel else 0.0)
        
        return True
    
    def _atualizar_combo_state(self, dt):
        """Atualiza estado do combo"""
        combo = self.combo_state
        if combo["timer_followup"] > 0:
            combo["timer_followup"] -= dt
        if combo["timer_followup"] <= 0 and combo["em_combo"]:
            combo["em_combo"] = False
            combo["hits_combo"] = 0
            combo["pode_followup"] = False
    
    # =========================================================================
    # SISTEMA DE BAITING (FINTAS) v8.0
    # =========================================================================
    
    def _processar_baiting(self, dt, distancia, inimigo):
        """Processa sistema de baiting/fintas"""
        bait = self.bait_state
        
        # Atualiza timer
        if bait["ativo"]:
            bait["timer"] -= dt
            if bait["timer"] <= 0:
                return self._executar_contra_bait(distancia, inimigo)
        
        # Decide se inicia bait
        if not bait["ativo"]:
            chance_bait = 0.0
            
            # Fatores que aumentam chance de bait
            if "TRICKSTER" in self.tracos:
                chance_bait += 0.15
            if "CALCULISTA" in self.tracos:
                chance_bait += 0.08
            if "OPORTUNISTA" in self.tracos:
                chance_bait += 0.05
            
            # Situacionais
            if self.momentum < -0.3:  # Perdendo, tenta enganar
                chance_bait += 0.1
            if self.leitura_oponente["agressividade_percebida"] > 0.7:
                chance_bait += 0.1  # Oponente agressivo, fácil de baitar

            # Onda 8D: o bait aprende — sucesso_count/falha_count eram
            # incrementados desde a v8 e nunca lidos. Quem cai no truque
            # vê mais truques; quem lê a finta faz o lutador parar de
            # repeti-la.
            bait_saldo = bait["sucesso_count"] - bait["falha_count"]
            chance_bait *= max(0.3, min(1.8, 1.0 + 0.2 * bait_saldo))

            if 3.0 < distancia < 6.0 and self._chance_temporal(chance_bait):
                tipo_bait = self.rng.choice(["recuo_falso", "abertura_falsa", "hesitacao_falsa"])
                bait["ativo"] = True
                bait["tipo"] = tipo_bait
                bait["timer"] = self.rng.uniform(0.3, 0.6)
                
                # Executa início do bait
                if tipo_bait == "recuo_falso":
                    self.acao_atual = "RECUAR"
                elif tipo_bait == "abertura_falsa":
                    self.acao_atual = "BLOQUEAR"
                elif tipo_bait == "hesitacao_falsa":
                    self.acao_atual = "CIRCULAR"
                
                return True
        
        return False
    
    def _executar_contra_bait(self, distancia, inimigo):
        """Executa contra-ataque após bait bem sucedido"""
        bait = self.bait_state
        bait["ativo"] = False
        
        # Verifica se oponente caiu no bait — Onda 8A: caiu se está
        # visivelmente vindo pra cima (avanço/golpe), não pela intenção.
        oponente_caiu = self._observar(inimigo).agressivo
        
        if oponente_caiu and distancia < 5.0:
            bait["sucesso_count"] += 1
            self.confianca = min(1.0, self.confianca + 0.15)
            self.excitacao = min(1.0, self.excitacao + 0.2)
            
            # Contra-ataque devastador
            if bait["tipo"] == "recuo_falso":
                self.acao_atual = "CONTRA_ATAQUE"
            elif bait["tipo"] == "abertura_falsa":
                self.acao_atual = "MATAR"
            else:
                self.acao_atual = "FLANQUEAR"
            
            return True
        else:
            bait["falha_count"] += 1
            return False
    
    # =========================================================================
    # SISTEMA DE MOMENTUM E PRESSÃO v8.0
    # =========================================================================
    
    def _atualizar_momentum(self, dt, distancia, inimigo):
        """Atualiza momentum da luta"""
        # Momentum aumenta quando:
        # - Dá hits
        # - Oponente recua
        # - HP do oponente cai
        # Momentum diminui quando:
        # - Recebe hits
        # - Você recua
        # - Seu HP cai
        
        # === ONDA 5C: momentum com dt e meia-vida ~4s ===
        # Antes: decay POR FRAME (x0.995) e bombas POR FRAME (diff_hits
        # x0.05 = -6/s com déficit de 2; hp_diff x0.02) — saturava em -1
        # em 70% dos frames. Agora: derivas por SEGUNDO; os empurrões de
        # EVENTO (+0.15 ao acertar / -0.1 ao apanhar) continuam.
        self.momentum *= 0.5 ** (dt / 4.0)

        diff_hits = self.hits_dados_recente - self.hits_recebidos_recente
        # 0,05/s por hit de vantagem: equilibrio ~0,6 com deficit de 2 e
        # ~0,87 em dominacao total com os empurroes de evento — o medidor
        # so crava no teto em blowout de verdade (alvo: <=10% dos frames;
        # com 0,15 o equilibrio passava de 1,7 e cravava em 42%).
        self.momentum += diff_hits * 0.05 * dt

        p = self.parent
        meu_hp = p.vida / p.vida_max
        ini_hp = inimigo.vida / inimigo.vida_max
        hp_diff = meu_hp - ini_hp
        self.momentum += hp_diff * 0.06 * dt
        
        # Baseado em pressão
        if distancia < 3.0:
            if self.acao_atual in ["MATAR", "PRESSIONAR", "ESMAGAR"]:
                self.pressao_aplicada = min(1.0, self.pressao_aplicada + dt * 0.5)
            else:
                self.pressao_aplicada = max(0.0, self.pressao_aplicada - dt * 0.3)
        else:
            self.pressao_aplicada = max(0.0, self.pressao_aplicada - dt * 0.5)
        
        # Pressão recebida — Onda 8A: pressão é o que se SENTE (oponente
        # perto avançando/golpeando), não a intenção interna dele.
        if distancia < 3.0 and self._observar(inimigo).agressivo:
            self.pressao_recebida = min(1.0, self.pressao_recebida + dt * 0.5)
        else:
            self.pressao_recebida = max(0.0, self.pressao_recebida - dt * 0.3)
        
        # Clamp momentum
        self.momentum = max(-1.0, min(1.0, self.momentum))
    
    # =========================================================================
    # SISTEMA DE RECONHECIMENTO ESPACIAL v9.0
    # =========================================================================
    
    def _sistema_espacial(self):
        """Onda 8C: SpatialAwarenessSystem com criação preguiçosa.

        As 521 linhas de spatial.py (arena CIRCULAR, line-of-sight,
        rotas alternativas, steering, predição de colisão) existiam
        prontas desde a v10 e nunca foram instanciadas — a cópia inline
        do brain só entendia retângulos. Ao criar, os dicts
        ``consciencia_espacial``/``tatica_espacial`` passam a SER os do
        sistema espacial, então todos os consumidores existentes seguem
        lendo os mesmos objetos (agora alimentados pelo produtor bom).
        """
        if self._espacial is None:
            try:
                from neural_fights.ai.spatial import SpatialAwarenessSystem
            except ImportError:
                return None
            self._espacial = SpatialAwarenessSystem(self.parent, rng=self.rng)
            self.consciencia_espacial = self._espacial.consciencia
            self.tatica_espacial = self._espacial.tatica
        return self._espacial

    def _atualizar_consciencia_espacial(self, dt, distancia, inimigo):
        """
        Atualiza awareness de paredes, obstáculos e posicionamento tático.
        Chamado no processar() principal. Onda 8C: delega ao
        SpatialAwarenessSystem (que se auto-limita a 0.08-0.15s); a
        análise tática de traços mantém o throttle próprio de 0.2s para
        não amplificar os empurrões emocionais por frame.
        """
        espacial = self._sistema_espacial()
        if espacial is None:
            return
        try:
            espacial.atualizar(dt, distancia, inimigo)
        except Exception:
            LOGGER.debug(
                "Falha na consciência espacial", exc_info=True
            )
            return

        self._timer_taticas += dt
        if self._timer_taticas >= 0.2:
            self._timer_taticas = 0.0
            self._avaliar_taticas_espaciais(distancia, inimigo)
    
    def _avaliar_taticas_espaciais(self, distancia, inimigo):
        """
        Avalia e define táticas espaciais baseadas na situação.
        VERSÃO MELHORADA v10.0 - mais inteligente e baseada em traços.
        """
        esp = self.consciencia_espacial
        tatica = self.tatica_espacial
        p = self.parent
        hp_pct = p.vida / p.vida_max
        
        # Reset táticas
        tatica["usando_cobertura"] = False
        tatica["forcar_canto"] = False
        tatica["recuar_para_obstaculo"] = False
        tatica["flanquear_obstaculo"] = False
        
        # === SE ENCURRALADO ===
        if esp["encurralado"]:
            # Reação depende da personalidade
            if "BERSERKER" in self.tracos or "KAMIKAZE" in self.tracos:
                # Berserkers ficam mais perigosos quando encurralados
                self.raiva = min(1.0, self.raiva + 0.4)
                self.medo = max(0, self.medo - 0.2)
                self.hesitacao = 0
            elif "COVARDE" in self.tracos or "MEDROSO" in self.tracos:
                # Covardes entram em pânico
                self.medo = min(1.0, self.medo + 0.4)
                self.hesitacao = min(0.8, self.hesitacao + 0.3)
            elif "FRIO" in self.tracos or "CALCULISTA" in self.tracos:
                # Calculistas mantêm a calma e planejam escape
                self.hesitacao = max(0.0, self.hesitacao - 0.2)
            else:
                # Padrão: stress moderado
                self.medo = min(1.0, self.medo + 0.2)
                self.hesitacao = max(0.0, self.hesitacao - 0.1)
            
            # Determina melhor rota de escape baseado em traços
            if esp["caminho_livre"]["esquerda"] and esp["caminho_livre"]["direita"]:
                # Escolhe baseado em tendência ou aleatoriedade
                if "ERRATICO" in self.tracos or "CAOTICO" in self.tracos:
                    self.dir_circular = self.rng.choice([-1, 1])
                else:
                    # Vai pro lado oposto do oponente
                    ang_inimigo = math.atan2(inimigo.pos[1] - p.pos[1], inimigo.pos[0] - p.pos[0])
                    self.dir_circular = 1 if math.sin(ang_inimigo) > 0 else -1
            elif esp["caminho_livre"]["esquerda"]:
                self.dir_circular = 1
            elif esp["caminho_livre"]["direita"]:
                self.dir_circular = -1
        
        # === OPONENTE CONTRA PAREDE/OBSTÁCULO ===
        oponente_vulneravel = esp.get("oponente_contra_parede", False) or esp.get("oponente_perto_obstaculo", False)
        if oponente_vulneravel and distancia < 6.0:
            tatica["forcar_canto"] = True
            self.confianca = min(1.0, self.confianca + 0.15)
            
            # Pressão extra baseada em traços
            if "PREDADOR" in self.tracos:
                self.agressividade_base = min(1.0, self.agressividade_base + 0.25)
            if "SANGUINARIO" in self.tracos or "IMPLACAVEL" in self.tracos:
                self.agressividade_base = min(1.0, self.agressividade_base + 0.2)
            if "OPORTUNISTA" in self.tracos:
                self.agressividade_base = min(1.0, self.agressividade_base + 0.15)
        
        # === USO DE COBERTURA ===
        obs_proximo = esp.get("obstaculo_proximo") or esp.get("obstaculo_proxima")
        dist_obs = esp.get("distancia_obstaculo", 999)
        
        if obs_proximo and dist_obs < 2.5:
            # Decide se usa cobertura baseado em personalidade
            usa_cobertura = False
            
            if "CAUTELOSO" in self.tracos or "TATICO" in self.tracos:
                usa_cobertura = True
            elif hp_pct < 0.35:
                usa_cobertura = True
            elif self.medo > 0.6:
                usa_cobertura = True
            elif "COVARDE" in self.tracos and distancia > 4.0:
                usa_cobertura = True
            
            # Berserkers e kamikazes não usam cobertura
            if "BERSERKER" in self.tracos or "KAMIKAZE" in self.tracos or "IMPLACAVEL" in self.tracos:
                usa_cobertura = False
            
            if usa_cobertura:
                tatica["usando_cobertura"] = True
                tatica["tipo_cobertura"] = getattr(obs_proximo, 'tipo', 'obstaculo')
        
        # === FLANQUEAMENTO COM OBSTÁCULOS ===
        if obs_proximo and 3.0 < distancia < 8.0 and dist_obs < 4.0:
            # Flanqueio é mais provável com certos traços
            flanqueia = False
            
            if "FLANQUEADOR" in self.tracos:
                flanqueia = self.rng.random() < 0.6
            elif "TATICO" in self.tracos or "CALCULISTA" in self.tracos:
                flanqueia = self.rng.random() < 0.4
            elif "ASSASSINO_NATO" in self.tracos or "NINJA" in self.arquetipo:
                flanqueia = self.rng.random() < 0.5
            else:
                flanqueia = self.rng.random() < 0.2
            
            if flanqueia:
                tatica["flanquear_obstaculo"] = True
        
        # === EVITA RECUAR PARA OBSTÁCULO ===
        if not esp["caminho_livre"]["tras"] and distancia < 4.0:
            tatica["recuar_para_obstaculo"] = True
            
            # Ajusta ação se estava tentando recuar
            if self.acao_atual in ["RECUAR", "FUGIR"]:
                if "BERSERKER" in self.tracos:
                    self.acao_atual = "MATAR"  # Não foge, ataca!
                elif self.rng.random() < 0.7:
                    self.acao_atual = "CIRCULAR"
                else:
                    self.acao_atual = "FLANQUEAR"
    
    def _aplicar_modificadores_espaciais(self, distancia, inimigo):
        """
        Aplica modificadores de comportamento baseados no ambiente.
        VERSÃO MELHORADA v10.0 - decisões mais inteligentes.
        """
        esp = self.consciencia_espacial
        tatica = self.tatica_espacial
        # === MODIFICADORES POR SITUAÇÃO ===
        
        # Se encurralado
        if esp["encurralado"]:
            # Escolha depende do balanço medo/raiva e traços
            escape_roll = self.rng.random()
            
            if "BERSERKER" in self.tracos or self.raiva > self.medo * 1.5:
                # Ataca com tudo
                if escape_roll < 0.7:
                    self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "CONTRA_ATAQUE"])
            elif "EVASIVO" in self.tracos or "ACROBATA" in self.tracos:
                # Tenta escapar com estilo
                if escape_roll < 0.5:
                    self.acao_atual = "FLANQUEAR"
                else:
                    self.acao_atual = "CIRCULAR"
            else:
                # Padrão: mistura de escape e contra-ataque
                if self.medo > self.raiva:
                    if escape_roll < 0.5:
                        self.acao_atual = "CIRCULAR"
                    elif escape_roll < 0.8:
                        self.acao_atual = "FLANQUEAR"
                    else:
                        self.acao_atual = "CONTRA_ATAQUE"
                else:
                    if escape_roll < 0.4:
                        self.acao_atual = self.rng.choice(["MATAR", "CONTRA_ATAQUE"])
                    else:
                        self.acao_atual = "CIRCULAR"
        
        # Se oponente contra parede
        if tatica["forcar_canto"]:
            if self.rng.random() < 0.35:
                self.acao_atual = self.rng.choice(["PRESSIONAR", "MATAR", "ESMAGAR"])
        
        # Se usando cobertura
        if tatica["usando_cobertura"]:
            if self.rng.random() < 0.25:
                # Fica atrás do obstáculo
                self.acao_atual = self.rng.choice(["CIRCULAR", "COMBATE", "BLOQUEAR"])
        
        # Se flanqueando com obstáculo
        if tatica["flanquear_obstaculo"]:
            if self.rng.random() < 0.2:
                self.acao_atual = "FLANQUEAR"
        
        # Se recuando pra obstáculo
        if tatica["recuar_para_obstaculo"]:
            # NUNCA recua
            if self.acao_atual in ["RECUAR", "FUGIR"]:
                self.acao_atual = self.rng.choice(["CIRCULAR", "COMBATE", "FLANQUEAR"])
        
        # === MODIFICADORES POR DIREÇÃO ===
        
        # Se caminho da frente bloqueado
        if not esp["caminho_livre"]["frente"]:
            if self.acao_atual in ["APROXIMAR", "MATAR", "PRESSIONAR"]:
                # Circula ao invés de ir direto
                if self.rng.random() < 0.4:
                    self.acao_atual = "FLANQUEAR"
        
        # Se perto de parede
        if esp["distancia_parede"] < 2.0:
            # Ajusta direção circular pra não bater na parede
            if esp["parede_proxima"] in ["oeste", "leste"]:
                # Parede lateral - ajusta se necessário
                if esp["parede_proxima"] == "oeste" and self.dir_circular < 0:
                    self.dir_circular = 1
                elif esp["parede_proxima"] == "leste" and self.dir_circular > 0:
                    self.dir_circular = -1
    
    def _ajustar_direcao_por_ambiente(self, direcao_alvo):
        """
        Ajusta uma direção de movimento para evitar obstáculos.
        Retorna nova direção segura.
        """
        p = self.parent
        
        # Converte direção pra radianos
        ang_rad = math.radians(direcao_alvo)
        
        # Verifica se a direção está bloqueada
        try:
            arena = p.arena
            
            # Testa ponto à frente
            test_dist = 1.5
            test_x = p.pos[0] + math.cos(ang_rad) * test_dist
            test_y = p.pos[1] + math.sin(ang_rad) * test_dist
            
            if arena.colide_obstaculo(test_x, test_y, p.raio_fisico):
                # Bloqueado! Tenta alternativas
                alternativas = [
                    direcao_alvo + 45,
                    direcao_alvo - 45,
                    direcao_alvo + 90,
                    direcao_alvo - 90,
                    direcao_alvo + 135,
                    direcao_alvo - 135,
                ]
                
                for alt_ang in alternativas:
                    alt_rad = math.radians(alt_ang)
                    alt_x = p.pos[0] + math.cos(alt_rad) * test_dist
                    alt_y = p.pos[1] + math.sin(alt_rad) * test_dist
                    
                    if not arena.colide_obstaculo(alt_x, alt_y, p.raio_fisico):
                        return alt_ang
                
                # Se tudo bloqueado, fica parado (retorna direção atual)
                return direcao_alvo
        except Exception:
            LOGGER.debug("Falha ao ajustar direção para evitar obstáculo", exc_info=True)
        
        return direcao_alvo
    
    # =========================================================================
    # SISTEMA DE PERCEPÇÃO DE ARMAS v10.0
    # =========================================================================
    
    def _atualizar_percepcao_armas(self, dt, distancia, inimigo):
        """
        Atualiza percepção da arma inimiga e calcula estratégias.
        Chamado no processar() principal.
        """
        if not WEAPON_ANALYSIS_AVAILABLE:
            return
        
        perc = self.percepcao_arma
        p = self.parent
        
        # Otimização: só analisa a cada 0.5s ou quando mudou
        perc["last_analysis_time"] += dt
        if perc["last_analysis_time"] < 0.5:
            return
        perc["last_analysis_time"] = 0.0
        
        # === ANÁLISE DA MINHA ARMA ===
        minha_arma = p.dados.arma_obj if hasattr(p.dados, 'arma_obj') else None
        meu_perfil = get_weapon_profile(minha_arma)
        
        if meu_perfil:
            perc["minha_arma_perfil"] = meu_perfil
            perc["meu_alcance_efetivo"] = meu_perfil.alcance_maximo
            perc["minha_velocidade_ataque"] = meu_perfil.velocidade_rating
            perc["meu_arco_cobertura"] = meu_perfil.arco_ataque
        
        # === ANÁLISE DA ARMA INIMIGA ===
        arma_inimigo = None
        if hasattr(inimigo, 'dados') and hasattr(inimigo.dados, 'arma_obj'):
            arma_inimigo = inimigo.dados.arma_obj
        
        perfil_inimigo = get_weapon_profile(arma_inimigo)
        
        # Verifica se arma do inimigo mudou
        tipo_atual = arma_inimigo.tipo if arma_inimigo else None
        if tipo_atual != perc["arma_inimigo_tipo"]:
            perc["enemy_weapon_changed"] = True
            perc["arma_inimigo_tipo"] = tipo_atual
        else:
            perc["enemy_weapon_changed"] = False
        
        if perfil_inimigo:
            perc["arma_inimigo_perfil"] = perfil_inimigo
            perc["alcance_inimigo"] = perfil_inimigo.alcance_maximo
            perc["zona_perigo_inimigo"] = perfil_inimigo.alcance_maximo * 1.2
            perc["velocidade_inimigo"] = perfil_inimigo.velocidade_rating
            
            # Calcula ponto cego do inimigo
            if perfil_inimigo.pontos_cegos:
                # Pega o primeiro ponto cego significativo
                for _, _, arco_cego in perfil_inimigo.pontos_cegos:
                    if arco_cego >= 90:
                        perc["ponto_cego_inimigo"] = 180  # Atrás
                        break
        
        # === ANÁLISE DE MATCHUP ===
        if meu_perfil and perfil_inimigo:
            # Vantagem de alcance
            perc["vantagem_alcance"] = (meu_perfil.alcance_maximo - perfil_inimigo.alcance_maximo) / 2.0
            
            # Vantagem de velocidade
            perc["vantagem_velocidade"] = meu_perfil.velocidade_rating - perfil_inimigo.velocidade_rating
            
            # Vantagem de cobertura
            perc["vantagem_cobertura"] = (meu_perfil.arco_ataque - perfil_inimigo.arco_ataque) / 90.0
            
            # Matchup geral
            comparacao = compare_weapons(minha_arma, arma_inimigo)
            if comparacao["vencedor"] == 1:
                perc["matchup_favoravel"] = comparacao["diferenca"] * 0.5
            elif comparacao["vencedor"] == 2:
                perc["matchup_favoravel"] = -comparacao["diferenca"] * 0.5
            else:
                perc["matchup_favoravel"] = 0.0
            
            # Limita entre -1 e 1
            perc["matchup_favoravel"] = max(-1.0, min(1.0, perc["matchup_favoravel"]))
            
            # Calcula distâncias táticas
            perc["distancia_segura"] = get_safe_distance(minha_arma, arma_inimigo)
            if meu_perfil.alcance_ideal:
                perc["distancia_ataque"] = meu_perfil.alcance_ideal
            
            # Define estratégia recomendada
            self._calcular_estrategia_armas(distancia, inimigo)
    
    def _calcular_estrategia_armas(self, distancia, inimigo):
        """
        Calcula estratégia recomendada baseada no matchup de armas.
        """
        perc = self.percepcao_arma
        p = self.parent
        
        # Avalia posição de combate
        ang_relativo = 0.0
        if hasattr(inimigo, 'angulo_olhar'):
            # Calcula ângulo entre direção que inimigo olha e minha posição
            dx = p.pos[0] - inimigo.pos[0]
            dy = p.pos[1] - inimigo.pos[1]
            ang_para_mim = math.degrees(math.atan2(dy, dx))
            ang_relativo = ang_para_mim - inimigo.angulo_olhar
        
        # Usa o sistema de avaliação de posição
        avaliacao = evaluate_combat_position(
            p.dados.arma_obj if hasattr(p.dados, 'arma_obj') else None,
            inimigo.dados.arma_obj if hasattr(inimigo.dados, 'arma_obj') else None,
            distancia,
            ang_relativo
        )
        
        perc["estrategia_recomendada"] = avaliacao["recomendacao"]
        
        # Ajusta alcance ideal baseado no matchup
        if perc["matchup_favoravel"] > 0.3:
            # Matchup favorável - fico na minha distância ideal
            p.alcance_ideal = perc.get("distancia_ataque", 2.0)
        elif perc["matchup_favoravel"] < -0.3:
            # Matchup desfavorável - ajusto baseado no estilo
            perfil_ini = perc.get("arma_inimigo_perfil")
            if perfil_ini:
                # Se inimigo tem mais alcance, aproximo; se menos, afasto
                if perc["vantagem_alcance"] < -0.5:
                    # Preciso aproximar pra atacar
                    p.alcance_ideal = max(1.0, perfil_ini.zona_morta * 0.8)
                elif perc["vantagem_alcance"] > 0.5:
                    # Mantenho distância segura
                    p.alcance_ideal = perc["distancia_segura"] * 0.9
    
    def _aplicar_modificadores_armas(self, distancia, inimigo):
        """
        Aplica modificadores de comportamento baseados na percepção de armas.
        Chamado em _decidir_movimento().
        """
        if not WEAPON_ANALYSIS_AVAILABLE:
            return
        
        perc = self.percepcao_arma
        estrategia = perc.get("estrategia_recomendada", "neutro")
        matchup = perc.get("matchup_favoravel", 0.0)
        
        # Ajustes de confiança baseados no matchup
        if matchup > 0.3:
            self.confianca = min(1.0, self.confianca + 0.1)
        elif matchup < -0.3:
            self.confianca = max(0.0, self.confianca - 0.1)
        
        # Aplica estratégia recomendada (com chance de ignorar baseado em personalidade)
        segue_estrategia = self.rng.random() < 0.7  # 70% de chance base
        
        if "ERRATICO" in self.tracos or "CAOTICO" in self.tracos:
            segue_estrategia = self.rng.random() < 0.3
        elif "CALCULISTA" in self.tracos or "TATICO" in self.tracos:
            segue_estrategia = self.rng.random() < 0.9
        elif "BERSERKER" in self.tracos:
            segue_estrategia = False  # Ignora estratégia, só ataca
        
        if not segue_estrategia:
            return
        
        # Aplica estratégia
        if estrategia == "atacar":
            if self.rng.random() < 0.4:
                self.acao_atual = self.rng.choice(["MATAR", "APROXIMAR", "PRESSIONAR"])
        
        elif estrategia == "recuar":
            if self.rng.random() < 0.5:
                self.acao_atual = self.rng.choice(["RECUAR", "CIRCULAR", "FLANQUEAR"])
        
        elif estrategia == "atacar_rapido":
            if self.rng.random() < 0.5:
                self.acao_atual = self.rng.choice(["ATAQUE_RAPIDO", "CONTRA_ATAQUE"])
        
        elif estrategia == "esperar":
            if self.rng.random() < 0.4:
                self.acao_atual = self.rng.choice(["COMBATE", "CIRCULAR", "BLOQUEAR"])
        
        elif estrategia == "aproximar":
            if self.rng.random() < 0.3:
                self.acao_atual = self.rng.choice(["APROXIMAR", "CIRCULAR"])
        
        # === COMPORTAMENTOS ESPECÍFICOS POR TIPO DE ARMA INIMIGA ===
        # v2.0: inclui lógica contra Mangual e Adagas Gêmeas reformulados
        tipo_ini = perc.get("arma_inimigo_tipo", "")
        arma_inimigo_estilo = ""
        # Define arma_inimigo from inimigo object
        arma_inimigo = getattr(getattr(inimigo, 'dados', None), 'arma_obj', None)
        if arma_inimigo and hasattr(arma_inimigo, 'estilo'):
            arma_inimigo_estilo = arma_inimigo.estilo
        
        # Contra Adagas Gêmeas: são muito rápidas, não deixar entrar no combo
        if tipo_ini == "Dupla" and arma_inimigo_estilo == "Adagas Gêmeas":
            # Adagas Gêmeas são letais de perto mas frágeis
            # Manter distância e punir a aproximação
            arma_personagem = getattr(getattr(self.parent, 'dados', None), 'arma_obj', None)
            alcance_efetivo = getattr(arma_personagem, 'distancia', 3.0) if arma_personagem else 3.0
            dist_segura = alcance_efetivo * 1.2  # Fica além do alcance das adagas
            roll_adagas = self.rng.random()
            if distancia < dist_segura and roll_adagas < 0.45:
                self.acao_atual = self.rng.choice(["RECUAR", "ESQUIVAR", "CIRCULAR"])
        
        if tipo_ini == "Corrente":
            arma_ini_estilo = arma_inimigo.estilo if arma_inimigo and hasattr(arma_inimigo, 'estilo') else ''
            
            if arma_ini_estilo == "Mangual":
                # v2.0 CONTRA MANGUAL: o Mangual tem zona morta enorme
                # Estratégia: entrar NA ZONA MORTA (muito perto) para anular o spin
                # OU ficar MUITO LONGE fora do alcance total
                # Onda 8A: a chave era "arma_inimigo_alcance", que nunca
                # foi escrita — o anti-Mangual usava sempre o fallback 4.0.
                alcance_mangual = perc.get("alcance_inimigo", 4.0)
                zona_morta_estimada = alcance_mangual * 0.40  # v3.0: zona morta 40%
                
                if distancia > alcance_mangual * 0.9:
                    pass  # Fora do alcance: mantém distância segura
                elif distancia > zona_morta_estimada * 2:
                    # Na zona de perigo: tenta entrar na zona morta para anular
                    self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR", "FLANQUEAR"])
                # Se dentro da zona morta: o Mangual é ineficaz → ataca!
            # Contra correntes normais: entrar na zona morta ou manter distância
            if distancia < perc.get("distancia_segura", 3.0) * 0.5:
                # Estou na zona morta - vantagem!
                if self.rng.random() < 0.6:
                    self.acao_atual = self.rng.choice(["MATAR", "PRESSIONAR"])
            elif distancia < perc.get("zona_perigo_inimigo", 4.0):
                # Zona perigosa da corrente - sai rápido
                if self.rng.random() < 0.5:
                    self.acao_atual = self.rng.choice(["APROXIMAR", "RECUAR"])  # Uma ou outra
        
        elif tipo_ini == "Arco":
            # Contra arcos: flanqueia e aproxima
            if distancia > 5.0:
                if self.rng.random() < 0.6:
                    self.acao_atual = self.rng.choice(["APROXIMAR", "FLANQUEAR"])
        
        elif tipo_ini == "Mágica":
            # Contra mágica: pressiona para não deixar canalizar
            if self.rng.random() < 0.4:
                self.acao_atual = self.rng.choice(["PRESSIONAR", "APROXIMAR"])
        
        elif tipo_ini == "Orbital":
            # Contra orbital: cuidado com o escudo
            if self.rng.random() < 0.4:
                self.acao_atual = self.rng.choice(["CIRCULAR", "FLANQUEAR"])
    
    # =========================================================================
    # SISTEMA DE ESTADOS HUMANOS v8.0
    # =========================================================================
    
    def _atualizar_estados_humanos(self, dt, distancia, inimigo):
        """Atualiza hesitação, impulso e outros estados humanos"""
        p = self.parent
        hp_pct = p.vida / p.vida_max
        
        # === HESITAÇÃO ===
        # Aumenta quando: 
        # - Situação desfavorável
        # - Oponente muito agressivo
        # - Tomou muito dano recentemente
        
        base_hesitacao = 0.1
        if hp_pct < 0.3:
            base_hesitacao += 0.2
        if self.momentum < -0.5:
            base_hesitacao += 0.15
        if self.hits_recebidos_recente >= 3:
            base_hesitacao += 0.2
        if self.pressao_recebida > 0.7:
            base_hesitacao += 0.15
        
        # Personalidade
        if "DETERMINADO" in self.tracos:
            base_hesitacao *= 0.5
        if "FRIO" in self.tracos:
            base_hesitacao *= 0.6
        if "COVARDE" in self.tracos:
            base_hesitacao *= 1.5
        if "BERSERKER" in self.tracos:
            base_hesitacao *= 0.3
        
        self.hesitacao = max(0.0, min(0.8, base_hesitacao))
        
        # === IMPULSO ===
        # Aumenta quando:
        # - Raiva alta
        # - Oponente com HP baixo
        # - Momento favorável
        
        base_impulso = 0.1
        if self.raiva > 0.6:
            base_impulso += 0.3
        if inimigo.vida / inimigo.vida_max < 0.25:
            base_impulso += 0.25
        if self.momentum > 0.5:
            base_impulso += 0.2
        if self.excitacao > 0.7:
            base_impulso += 0.15
        
        # Personalidade
        if "IMPRUDENTE" in self.tracos:
            base_impulso *= 1.5
        if "CALCULISTA" in self.tracos:
            base_impulso *= 0.5
        if "PACIENTE" in self.tracos:
            base_impulso *= 0.6
        
        self.impulso = max(0.0, min(0.9, base_impulso))
        
        # === CONGELAMENTO ===
        # Ocorre sob pressão extrema
        
        base_congela = 0.0
        if self.pressao_recebida > 0.8:
            base_congela = 0.3
        if self.hits_recebidos_recente >= 4 and self.tempo_desde_dano < 1.0:
            base_congela += 0.4
        
        if "FRIO" in self.tracos:
            base_congela *= 0.2
        if "MEDROSO" in self.tracos:
            base_congela *= 1.5
        
        self.congelamento = max(0.0, min(0.6, base_congela))
        
        # === DESCANSO ===
        # Micro-pausas após bursts de ação
        self.burst_counter = max(0, self.burst_counter - dt * 2)
        if self.burst_counter > 5:
            self.descanso_timer = self.rng.uniform(0.3, 0.8)
            self.burst_counter = 0
    
    def _verificar_hesitacao(self, dt, distancia, inimigo):
        """Verifica se a IA hesita neste frame"""
        # Onda 5B: hesitação é PORTÃO (como instinto) — escreve com
        # prioridade 1 e interrompe qualquer hold; o momento humano não
        # pode ser engolido pelo min-hold de uma decisão anterior.
        # Descanso forçado
        if self.descanso_timer > 0:
            self.descanso_timer = max(0.0, self.descanso_timer - dt)
            self._definir_acao("CIRCULAR", fonte="hesitacao", prioridade=1)
            return True

        # Fechamento da O5: o portão rolava QUATRO chances POR FRAME sem
        # cooldown — a sonda de segmentos mostrou impulso+hesitação
        # iniciando 44% dos segmentos de ação (a decisão iniciava 6%: os
        # commits P3 morriam nos holds P1 da metralhadora). Hesitar a cada
        # segundo não é humano; mesmo remédio dos instintos da 5D.
        if self.tempo_combate < getattr(self, "cd_hesitacao", 0.0):
            return False
        
        # Congelamento sob pressão
        if self._chance_temporal(self.congelamento * 0.1, dt):
            self._definir_acao("BLOQUEAR", fonte="hesitacao", prioridade=1)
            self.cd_hesitacao = self.tempo_combate + self.rng.uniform(2.5, 5.0)
            return True
        
        # Hesitação
        if self._chance_temporal(self.hesitacao * 0.05, dt):
            # Hesita - faz algo defensivo
            self._definir_acao(
                self.rng.choice(["CIRCULAR", "BLOQUEAR", "RECUAR"]),
                fonte="hesitacao", prioridade=1,
            )
            self.cd_hesitacao = self.tempo_combate + self.rng.uniform(2.5, 5.0)
            return True
        
        # Impulso pode cancelar hesitação
        if self._chance_temporal(self.impulso * 0.1, dt):
            self._definir_acao(
                self.rng.choice(["MATAR", "APROXIMAR", "PRESSIONAR"]),
                fonte="impulso", prioridade=1,
            )
            self.burst_counter += 1
            self.cd_hesitacao = self.tempo_combate + self.rng.uniform(2.5, 5.0)
            return True
        
        return False
    
    def _registrar_acao(self):
        """Registra ação para evitar repetição excessiva"""
        self.historico_acoes.append(self.acao_atual)
        if len(self.historico_acoes) > 10:
            self.historico_acoes.pop(0)
        
        # Conta repetições
        if self.acao_atual in self.repeticao_contador:
            self.repeticao_contador[self.acao_atual] += 1
        else:
            self.repeticao_contador[self.acao_atual] = 1
        
        # Decay das contagens
        for key in list(self.repeticao_contador.keys()):
            if key != self.acao_atual:
                self.repeticao_contador[key] = max(0, self.repeticao_contador[key] - 0.5)

    # =========================================================================
    # SISTEMA DE COREOGRAFIA
    # =========================================================================
    
    def _observar_oponente(self, inimigo, distancia):
        """Observa o que o oponente está fazendo (Onda 8A: sem telepatia).

        A memória agora conta TRANSIÇÕES de intenção aparente — o que um
        espectador registraria ("ele partiu pra cima de novo") — em vez
        de transições do acao_atual interno do brain adversário.
        """
        obs = self._observar(inimigo)
        mem = self.memoria_oponente

        intencao = obs.intencao
        if intencao != mem["ultima_acao"]:
            mem["ultima_acao"] = intencao

            if intencao in ("avancando", "armando_golpe"):
                mem["vezes_atacou"] += 1
            elif intencao == "recuando":
                mem["vezes_fugiu"] += 1

        if mem["vezes_atacou"] > mem["vezes_fugiu"] * 2:
            mem["estilo_percebido"] = "AGRESSIVO"
            mem["ameaca_nivel"] = min(1.0, mem["ameaca_nivel"] + 0.02)
        elif mem["vezes_fugiu"] > mem["vezes_atacou"] * 2:
            mem["estilo_percebido"] = "DEFENSIVO"
            mem["ameaca_nivel"] = max(0.2, mem["ameaca_nivel"] - 0.01)
        else:
            mem["estilo_percebido"] = "EQUILIBRADO"

        self._gerar_reacao_inteligente(obs, distancia, inimigo)

    def _gerar_reacao_inteligente(self, obs, distancia, inimigo):
        """Gera uma reação inteligente ao que se VÊ do oponente (Onda 8A)."""
        if obs.intencao == "armando_golpe" and distancia < 4.0:
            # Wind-up real detectado perto: a reação clássica ao MATAR.
            if "REATIVO" in self.tracos or "OPORTUNISTA" in self.tracos:
                self.reacao_pendente = "CONTRA_ATAQUE"
            elif "COVARDE" in self.tracos or self.medo > 0.6:
                self.reacao_pendente = "RECUAR"
            elif "BERSERKER" in self.tracos or self.raiva > 0.7:
                self.reacao_pendente = "CONTRA_MATAR"
            elif self.rng.random() < 0.3:
                self.reacao_pendente = "ESQUIVAR"

        elif obs.intencao == "recuando":
            if "PERSEGUIDOR" in self.tracos or "PREDADOR" in self.tracos:
                self.reacao_pendente = "PERSEGUIR"
                self.confianca = min(1.0, self.confianca + 0.1)
            elif "PACIENTE" in self.tracos:
                self.reacao_pendente = "ESPERAR"
            elif self.rng.random() < 0.4:
                self.reacao_pendente = "PRESSIONAR"

        elif obs.intencao == "circulando":
            if "FLANQUEADOR" in self.tracos:
                self.reacao_pendente = "CONTRA_CIRCULAR"
            elif self.rng.random() < 0.3:
                self.reacao_pendente = "INTERCEPTAR"

        elif obs.intencao == "parado" and distancia < 4.0:
            # Parado em guarda a curta distância: postura defensiva visível.
            if "CALCULISTA" in self.tracos:
                self.reacao_pendente = "ESPERAR_ABERTURA"
            elif "IMPRUDENTE" in self.tracos or "AGRESSIVO" in self.tracos:
                self.reacao_pendente = "FURAR_GUARDA"
            elif self.filosofia == "PACIENCIA":
                self.reacao_pendente = "ESPERAR"
    
    def _processar_reacao_oponente(self, dt, distancia, inimigo):
        """Processa reação pendente ao oponente"""
        if not self.reacao_pendente:
            return False
        
        reacao = self.reacao_pendente
        self.reacao_pendente = None
        
        chance = 0.6
        if "ADAPTAVEL" in self.tracos:
            chance = 0.8
        if "TEIMOSO" in self.tracos:
            chance = 0.3
        if "FRIO" in self.tracos:
            chance = 0.7
        
        if self.rng.random() > chance:
            return False
        
        acoes = {
            "CONTRA_ATAQUE": ("CONTRA_ATAQUE", lambda: setattr(self, 'excitacao', min(1.0, self.excitacao + 0.2))),
            "CONTRA_MATAR": ("MATAR", lambda: (setattr(self, 'raiva', min(1.0, self.raiva + 0.15)),
                                               setattr(self, 'adrenalina', min(1.0, self.adrenalina + 0.2)))),
            "RECUAR": ("RECUAR", None),
            "PERSEGUIR": ("APROXIMAR", lambda: setattr(self, 'excitacao', min(1.0, self.excitacao + 0.15))),
            "PRESSIONAR": ("APROXIMAR", None),
            "INTERCEPTAR": ("FLANQUEAR", None),
            "ESPERAR": ("BLOQUEAR", None),
            "ESPERAR_ABERTURA": ("CIRCULAR", None),
            "FURAR_GUARDA": ("MATAR", None),
        }
        
        if reacao == "ESQUIVAR":
            if self.parent.z == 0 and self.cd_pulo <= 0:
                self.parent.vel_z = 12.0
                self.cd_pulo = 1.0
            self.acao_atual = "CIRCULAR"
            return True
        
        if reacao == "CONTRA_CIRCULAR":
            # Onda 8A: circula CONTRA o lado que o oponente visivelmente
            # está estrafando, não contra o dir_circular interno dele.
            lado = self._observar(inimigo).lado_circular
            if lado:
                self.dir_circular = -lado
            self.acao_atual = "CIRCULAR"
            return True
        
        if reacao in acoes:
            self.acao_atual, callback = acoes[reacao]
            if callback:
                callback()
            return True
        
        return False
    
    #: Natureza de cada marcação do diretor, para saber o que a contraria.
    NATUREZA_DA_DIRECAO = {
        "CIRCULAR_LENTO": "passiva",
        "CIRCULAR_SINCRONIZADO": "passiva",
        "ENCARAR": "passiva",
        "PREPARAR_ATAQUE": "passiva",
        "RESISTIR_PRESSAO": "passiva",
        "SEPARAR": "recuo",
        "RECUPERAR": "recuo",
        "FUGIR_DRAMATICO": "recuo",
        "CLASH": "agressiva",
        "ATAQUE_FINAL": "agressiva",
        "TROCAR_GOLPES": "agressiva",
        "TROCAR_RAPIDO": "agressiva",
        "PRESSIONAR_CONTINUO": "agressiva",
        "PERSEGUIR": "agressiva",
    }

    def _aceita_direcao(self, acao):
        """Decide se o lutador segue a marcação do diretor nesta batida.

        O ``CombatChoreographer`` existe para dar ritmo cinematográfico à luta, e
        isso é desejável -- mas até aqui a marcação dele era um override
        incondicional: em 53% dos frames a personalidade do lutador não era
        sequer consultada. Por mais rica que a personalidade fique, metade da
        luta continuaria igual para todo mundo.

        Aqui o perfil decide se o lutador *obedece*. Quem quebra da marcação é
        quem tem motivo para quebrar: um berserker não circula devagar, um
        cauteloso não entra num clash, e um caótico improvisa em qualquer beat.

        A decisão é tomada **uma vez por batida** e mantida. Sortear a cada frame
        faria o lutador oscilar entre roteiro e improviso dezenas de vezes por
        segundo, o que na tela vira tremor, não personalidade.
        """
        if acao != self._direcao_avaliada:
            self._direcao_avaliada = acao
            self._direcao_aceita = self._sortear_aceitacao(acao)
        return self._direcao_aceita

    def _sortear_aceitacao(self, acao):
        """Chance de obedecer, reduzida pelo que contraria a natureza do lutador."""
        perfil = self.perfil
        natureza = self.NATUREZA_DA_DIRECAO.get(acao, "neutra")

        # Base alta: o padrão continua sendo seguir o diretor.
        aceitacao = 0.85

        if natureza == "passiva":
            # Esperar contraria quem só sabe avançar.
            aceitacao -= max(0.0, perfil["agressao"]) * 0.55
        elif natureza == "recuo":
            aceitacao -= max(0.0, perfil["agressao"]) * 0.45
            # Quem não sente medo não recua de forma convincente.
            aceitacao -= max(0.0, -perfil["medo"]) * 0.30
        elif natureza == "agressiva":
            aceitacao -= max(0.0, perfil["cautela"]) * 0.40
            aceitacao -= max(0.0, perfil["medo"]) * 0.35

        # Caos improvisa em qualquer marcação; frieza segura o plano.
        aceitacao -= max(0.0, perfil["caos"]) * 0.25
        aceitacao += max(0.0, perfil["frieza"]) * 0.15

        # Piso e teto: o diretor nunca perde a luta inteira, e nunca a controla
        # por completo.
        aceitacao = max(0.15, min(0.98, aceitacao))
        return self.rng.random() < aceitacao

    def _executar_acao_sincronizada(self, acao, distancia, inimigo):
        """Executa ação sincronizada de momento cinematográfico v8.0"""
        acoes = {
            "CIRCULAR_LENTO": lambda: setattr(self, 'timer_decisao', 0.5) or "CIRCULAR",
            "ENCARAR": lambda: "BLOQUEAR",
            "TROCAR_GOLPES": lambda: self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "COMBATE"]),
            "RECUPERAR": lambda: setattr(self, 'timer_decisao', 0.8) or "RECUAR",
            "PERSEGUIR": lambda: "APROXIMAR",
        }
        
        if acao == "PREPARAR_ATAQUE":
            self.modo_burst = True
            self.adrenalina = min(1.0, self.adrenalina + 0.05)
            self.acao_atual = "APROXIMAR_LENTO" if distancia > 4.0 else "BLOQUEAR"
            return True
        
        if acao == "FUGIR_DRAMATICO":
            if self.raiva > 0.7 or self.rng.random() < 0.2:
                self.acao_atual = "MATAR"
            else:
                self.acao_atual = "FUGIR"
            return True
        
        if acao == "CIRCULAR_SINCRONIZADO":
            # Onda 8A: acompanha o lado observado do strafe do oponente.
            lado = self._observar(inimigo).lado_circular
            if lado:
                self.dir_circular = lado
            self.acao_atual = "CIRCULAR"
            return True
        
        if acao == "CLASH":
            self.acao_atual = "MATAR"
            self.excitacao = 1.0
            self.adrenalina = min(1.0, self.adrenalina + 0.3)
            return True
        
        if acao == "ATAQUE_FINAL":
            self.modo_burst = True
            self.modo_berserk = True
            self.acao_atual = "MATAR"
            self._usar_tudo()
            return True
        
        # === NOVAS AÇÕES v8.0 ===
        if acao == "TROCAR_RAPIDO":
            # Troca rápida de golpes - alterna entre ataque e defesa
            if self.rng.random() < 0.6:
                self.acao_atual = self.rng.choice(["ATAQUE_RAPIDO", "MATAR"])
            else:
                self.acao_atual = self.rng.choice(["CONTRA_ATAQUE", "FLANQUEAR"])
            self.excitacao = min(1.0, self.excitacao + 0.15)
            return True
        
        if acao == "REAGIR_ESQUIVA":
            # Reage a uma esquiva próxima
            if self.rng.random() < 0.5:
                self.acao_atual = "CONTRA_ATAQUE"
            else:
                self.acao_atual = "CIRCULAR"
            return True
        
        if acao == "PRESSIONAR_CONTINUO":
            # Mantém pressão sobre o oponente
            self.acao_atual = self.rng.choice(["PRESSIONAR", "MATAR", "APROXIMAR"])
            self.pressao_aplicada = min(1.0, self.pressao_aplicada + 0.1)
            return True
        
        if acao == "RESISTIR_PRESSAO":
            # Resiste à pressão do oponente
            if self.raiva > 0.6 or self.rng.random() < 0.3:
                self.acao_atual = "CONTRA_ATAQUE"
            else:
                self.acao_atual = self.rng.choice(["CIRCULAR", "FLANQUEAR", "COMBATE"])
            return True
        
        if acao == "SEPARAR":
            # Ambos se afastam brevemente
            self.acao_atual = "RECUAR"
            self.timer_decisao = 0.5
            return True
        
        if acao == "FINTA":
            # Executa uma finta
            if not self.bait_state["ativo"]:
                self.bait_state["ativo"] = True
                self.bait_state["tipo"] = "finta_coreografada"
                self.bait_state["timer"] = 0.4
            self.acao_atual = self.rng.choice(["APROXIMAR_LENTO", "CIRCULAR", "COMBATE"])
            return True
        
        if acao in acoes:
            result = acoes[acao]()
            if isinstance(result, str):
                self.acao_atual = result
            return True
        
        return False
    
    def _usar_tudo(self):
        """Usa todas as skills disponíveis"""
        for tipo in ["BUFF", "DASH", "AREA", "BEAM", "PROJETIL"]:
            for skill in self.skills_por_tipo.get(tipo, []):
                self._usar_skill(skill)
    
    def on_momento_cinematografico(self, tipo, iniciando, duracao):
        """Callback quando momento cinematográfico começa/termina"""
        self.momento_cinematografico = tipo if iniciando else None
        
        if iniciando:
            if tipo == "CLASH":
                self.excitacao = 1.0
                self.adrenalina = min(1.0, self.adrenalina + 0.3)
            elif tipo == "STANDOFF":
                self.confianca = 0.5
            elif tipo == "FINAL_SHOWDOWN":
                self.adrenalina = 1.0
                self.excitacao = 1.0
                self.medo = 0.0
            elif tipo == "FACE_OFF":
                self.excitacao = min(1.0, self.excitacao + 0.2)
            elif tipo == "CLIMAX_CHARGE":
                self.modo_burst = True
    
    def on_hit_recebido_de(self, atacante):
        """Callback quando recebe hit de um atacante específico"""
        self.memoria_oponente["ameaca_nivel"] = min(1.0, 
            self.memoria_oponente["ameaca_nivel"] + 0.15)
        
        if "VINGATIVO" in self.tracos:
            self.reacao_pendente = "CONTRA_MATAR"
        elif "COVARDE" in self.tracos and self.medo > 0.4:
            self.reacao_pendente = "FUGIR"
        elif "REATIVO" in self.tracos:
            self.reacao_pendente = "CONTRA_ATAQUE"

    # =========================================================================
    # ATUALIZAÇÃO DE ESTADOS
    # =========================================================================

    def _atualizar_cooldowns(self, dt):
        """Atualiza cooldowns"""
        self.cd_dash = max(0, self.cd_dash - dt)
        self.cd_pulo = max(0, self.cd_pulo - dt)
        self.cd_desvio = max(0, self.cd_desvio - dt)
        self.cd_punicao = max(0, self.cd_punicao - dt)
        self.cd_mudanca_direcao = max(0, self.cd_mudanca_direcao - dt)
        self.cd_reagir = max(0, self.cd_reagir - dt)
        self.cd_buff = max(0, self.cd_buff - dt)
        self.cd_quirk = max(0, self.cd_quirk - dt)
        self.cd_mudanca_humor = max(0, self.cd_mudanca_humor - dt)
        self.tempo_desde_dano += dt
        self.tempo_desde_hit += dt
        self.ultimo_bloqueio = min(99.0, self.ultimo_bloqueio + dt)

    def _detectar_dano(self):
        """Detecta dano recebido pelo delta de vida.

        Onda 5C: tick de DoT não é "ser acertado" — queimar não quebra
        combo, não alimenta susto/medo nem o momentum (os ticks poluíam
        os contadores e ajudavam a saturar o momentum em -1). O motor
        carimba ``ultimo_tipo_fonte_dano`` no ponto de aplicação; os
        contadores agora vivem em ``EmotionSystem.reagir_ao_dano``.
        """
        p = self.parent

        if p.vida < self.ultimo_hp:
            dano = self.ultimo_hp - p.vida
            self.ultimo_dano_recebido = dano  # Salva o valor do dano
            if getattr(p, "ultimo_tipo_fonte_dano", None) != "dot_encanto":
                if getattr(self, "_acao_atual", None) == "BLOQUEAR":
                    # Sinal real para CONTRA_REFLEXO (Onda 5D): levou o
                    # golpe de guarda fechada — a janela de contra abre.
                    self.ultimo_bloqueio = 0.0
                self._reagir_ao_dano(dano)

        self.ultimo_hp = p.vida

    def _reagir_ao_dano(self, dano):
        """Reações emocionais ao dano (motor único — 5C, por eixos)."""
        self._motor_emocional().reagir_ao_dano(dano)

    def _atualizar_emocoes(self, dt, distancia, inimigo):
        """Física emocional no motor único (5C); troca de direção é
        movimento e fica no brain. Timers/cds ticam no passo de cooldowns."""
        self._motor_emocional().atualizar(dt, distancia, inimigo, self.tempo_combate)

        # Mudança de direção
        if self.cd_mudanca_direcao <= 0:
            chance = 0.15 if "ERRATICO" in self.tracos or "CAOTICO" in self.tracos else 0.08
            if self._chance_temporal(chance, dt):
                self.dir_circular *= -1
                self.cd_mudanca_direcao = self.rng.uniform(0.5, 2.0)

    def _atualizar_humor(self, dt):
        """Escada de humor no motor único (5C): DESESPERADO no topo,
        BERSERK/EUFORICO/GLACIAL com produtores reais."""
        self._motor_emocional().atualizar_humor()

    def _processar_modos_especiais(self, dt, distancia, inimigo):
        """Processa modos especiais de combate"""
        p = self.parent
        hp_pct = p.vida / p.vida_max
        
        if "BERSERKER" in self.tracos or "BERSERKER_RAGE" in self.tracos:
            if hp_pct < 0.4 and self.raiva > 0.5:
                self.modo_berserk = True
            elif hp_pct > 0.6 or self.raiva < 0.2:
                self.modo_berserk = False
        
        if "PRUDENTE" in self.tracos or "CAUTELOSO" in self.tracos:
            if hp_pct < 0.3 or self.medo > 0.6:
                self.modo_defensivo = True
            elif hp_pct > 0.5 and self.medo < 0.3:
                self.modo_defensivo = False
        
        if "EXPLOSIVO" in self.tracos or self.estilo_luta == "BURST":
            inimigo_hp_pct = inimigo.vida / inimigo.vida_max
            if inimigo_hp_pct < 0.4 or (p.mana > p.mana_max * 0.8 and distancia < 5.0):
                self.modo_burst = True
            elif inimigo_hp_pct > 0.6 or p.mana < p.mana_max * 0.3:
                self.modo_burst = False

    # =========================================================================
    # QUIRKS
    # =========================================================================
    
    def _detectar_projetil_vindo(self, inimigo):
        """Detecta projéteis REALMENTE vindo na minha direção (Onda 8A).

        A versão antiga lia ``inimigo.buffer_projeteis`` — que o Simulador
        drena para as listas do mundo ANTES do tick das IAs (a lista
        estava sempre vazia) — e, quando via algo, era um teste de raio
        4m sem direção (disparava para projétil se AFASTANDO). Agora lê
        a janela de mundo (``percepcao``) com o teste de ângulo + tempo
        de impacto que existia pronto no subsistema de desvio morto.
        """
        p = self.parent

        percepcao = getattr(p, "percepcao", None)
        if percepcao is not None:
            for proj in percepcao.projeteis_hostis(p):
                dx = p.pos[0] - proj.x
                dy = p.pos[1] - proj.y
                dist = math.hypot(dx, dy)
                if dist > 8.0:
                    continue
                ang_para_mim = math.degrees(math.atan2(dy, dx))
                ang_proj = getattr(proj, 'angulo', 0)
                if abs(normalizar_angulo(ang_para_mim - ang_proj)) < 45:
                    vel_proj = max(1.0, getattr(proj, 'vel', 10.0))
                    if dist / vel_proj < 1.0:  # impacto em < 1s
                        return True

        # Orbes moram no próprio lutador (buffer NÃO é drenado) e só
        # ameaçam quando mudam para o estado de disparo.
        if hasattr(inimigo, 'buffer_orbes'):
            for orbe in inimigo.buffer_orbes:
                if not orbe.ativo or orbe.estado != "disparando":
                    continue
                dx = p.pos[0] - orbe.x
                dy = p.pos[1] - orbe.y
                dist = math.hypot(dx, dy)
                if dist < 5.0:
                    return True
        
        return False

    def _tentar_cura_emergencia(self, hp_pct):
        """Cura de emergência"""
        skills_cura = [
            *self.skills_por_tipo.get("BUFF", []),
            *self.skills_por_tipo.get("CHANNEL", []),
        ]
        
        for skill in skills_cura:
            data = skill["data"]
            if tem_cura(data):
                threshold = 0.5 if "CAUTELOSO" in self.tracos else 0.35
                if "IMPRUDENTE" in self.tracos:
                    threshold = 0.2
                
                if hp_pct < threshold:
                    if self._usar_skill(skill):
                        self.cd_reagir = 0.3
                        return True
        
        return False

    def _tentar_contra_ataque(self, distancia, inimigo):
        """Contra-ataque"""
        pode_contra = False
        if "REATIVO" in self.tracos or "OPORTUNISTA" in self.tracos:
            pode_contra = True
        if self.estilo_luta == "COUNTER" or self.filosofia == "OPORTUNISMO":
            pode_contra = True
        
        if not pode_contra:
            return False
        
        vulneravel = False
        if hasattr(inimigo, 'cooldown_ataque') and inimigo.cooldown_ataque > 0.3:
            vulneravel = True
        if hasattr(inimigo, 'atacando') and not inimigo.atacando:
            vulneravel = True
        
        if vulneravel and distancia < self.parent.alcance_ideal + 1.5:
            self.acao_atual = "CONTRA_ATAQUE"
            self.raiva = min(1.0, self.raiva + 0.1)
            self.cd_reagir = 0.4
            return True
        
        return False

    # =========================================================================
    # SKILLS - SISTEMA INTELIGENTE v1.0
    # =========================================================================
    
    def _processar_skills(self, dt, distancia, inimigo):
        """Processa uso de skills com sistema de estratégia inteligente"""
        p = self.parent
        
        # Verifica cooldown global
        if hasattr(p, 'cd_skill_arma') and p.cd_skill_arma > 0:
            return False
        
        # Traço CONSERVADOR reduz uso de skills
        if "CONSERVADOR" in self.tracos and p.mana < p.mana_max * 0.4:
            if not self._chance_temporal(0.2, dt):
                return False
        
        # === USA SISTEMA DE ESTRATÉGIA SE DISPONÍVEL ===
        if self.skill_strategy is not None:
            return self._processar_skills_estrategico(dt, distancia, inimigo)

        # Onda 5E: o "sistema legado" de skills morreu (6 metodos _tentar_*
        # + 2 orfaos, ~400 linhas inalcancaveis com a estrategia ativa).
        # Sem estrategia (falha de init, coberta por teste), nao ha skills.
        return False
    
    def _processar_skills_estrategico(self, dt, distancia, inimigo):
        """Processa skills usando o sistema de estratégia inteligente"""
        p = self.parent
        strategy = self.skill_strategy
        
        # Cria situação de combate atual
        situacao = CombatSituation(
            distancia=distancia,
            meu_hp_percent=p.vida / p.vida_max if p.vida_max > 0 else 1.0,
            inimigo_hp_percent=inimigo.vida / inimigo.vida_max if inimigo.vida_max > 0 else 1.0,
            meu_mana_percent=p.mana / p.mana_max if p.mana_max > 0 else 1.0,
            estou_encurralado=self.consciencia_espacial.get("encurralado", False),
            inimigo_encurralado=self.consciencia_espacial.get("oponente_contra_parede", False),
            inimigo_atacando=self.leitura_oponente.get("ataque_iminente", False),
            tenho_summons_ativos=self._contar_summons_ativos(),
            tenho_traps_ativos=self._contar_traps_ativos(),
            tenho_buffs_ativos=len(getattr(p, 'buffs_ativos', [])),
            inimigo_debuffado=self._verificar_inimigo_debuffado(inimigo),
            inimigo_queimando=alvo_tem_efeito(inimigo, "QUEIMANDO"),
            inimigo_congelado=alvo_tem_efeito(inimigo, "CONGELADO"),
            momentum=self.momentum,
            tempo_combate=self.tempo_combate
        )
        
        # Obtém melhor skill para a situação
        resultado = strategy.obter_melhor_skill(situacao, dt=dt)
        
        if resultado:
            skill_profile, razao = resultado
            
            LOGGER.debug(
                "Estratégia %s: fase=%s skill=%s razão=%s mana=%.0f",
                p.dados.nome,
                strategy.fase_atual.value,
                skill_profile.nome,
                razao,
                p.mana,
            )
            
            # Chance baseada no role - magos usam skills muito mais frequentemente
            role = strategy.role_principal.value
            if role in ["artillery", "burst_mage", "control_mage", "summoner", "buffer", "channeler"]:
                chance_usar = 0.85  # Magos: 85% de chance base
            else:
                chance_usar = 0.6   # Melee: 60% de chance base
            # Onda 5A: o eixo skill_uso (órfão desde a migração dos 162
            # traços) modula o portão — antes era só o hard-code por role.
            chance_usar *= 1.0 + 0.35 * self.perfil.get("skill_uso", 0.0)
            chance_usar = max(0.25, min(0.98, chance_usar))
            
            # Modificadores de personalidade
            if "SPAMMER" in self.tracos:
                chance_usar = min(0.95, chance_usar + 0.15)
            if "CALCULISTA" in self.tracos:
                chance_usar *= 0.85
            if self.modo_burst:
                chance_usar = 0.95

            # Onda 8E: o plano decide QUANDO a rotação dispara, não só o
            # quê — caçar janela de skill escancara o portão; baitar
            # segura a mão (skill entrega a finta).
            plano = self.plano
            if plano is not None:
                if plano["tipo"] == "CACAR_JANELA_SKILL":
                    chance_usar = max(chance_usar, 0.95)
                elif plano["tipo"] == "BAITAR_E_PUNIR":
                    chance_usar *= 0.7
            
            # Summons/Traps são mais estratégicos
            if skill_profile.tipo in ["SUMMON", "TRAP", "TRANSFORM"]:
                chance_usar *= 0.9  # Menos redução que antes
            
            if self._chance_temporal(chance_usar, dt):
                if self._executar_skill_por_nome(skill_profile.nome):
                    # Registra uso
                    strategy.registrar_uso_skill(skill_profile.nome)
                    
                    # Ação pós-skill baseada no tipo
                    self._pos_uso_skill_estrategica(skill_profile)
                    return True
        else:
            if LOGGER.isEnabledFor(logging.DEBUG):
                cds = {k: f"{v:.1f}" for k, v in p.cd_skills.items() if v > 0}
                LOGGER.debug(
                    "Estratégia %s sem skill: mana=%.0f distância=%.1f cooldowns=%s",
                    p.dados.nome,
                    p.mana,
                    distancia,
                    cds,
                )
        
        return False
    
    def _executar_skill_por_nome(self, nome_skill):
        """Executa uma skill pelo nome"""
        p = self.parent
        
        # Verifica nas skills da arma (COM ÍNDICE!)
        for idx, skill_info in enumerate(getattr(p, 'skills_arma', [])):
            if skill_info.get("nome") == nome_skill:
                if hasattr(p, 'usar_skill_arma'):
                    resultado = p.usar_skill_arma(skill_idx=idx)
                    if resultado:
                        LOGGER.debug("%s usou skill de arma: %s", p.dados.nome, nome_skill)
                    return resultado
        
        # Verifica nas skills da classe
        for skill_info in getattr(p, 'skills_classe', []):
            if skill_info.get("nome") == nome_skill:
                if hasattr(p, 'usar_skill_classe'):
                    resultado = p.usar_skill_classe(nome_skill)
                    if resultado:
                        LOGGER.debug("%s usou skill de classe: %s", p.dados.nome, nome_skill)
                    return resultado
        
        # Tenta usar como skill de arma legado (índice 0)
        if nome_skill == getattr(p, 'skill_arma_nome', None):
            if hasattr(p, 'usar_skill_arma'):
                resultado = p.usar_skill_arma(skill_idx=0)
                if resultado:
                    LOGGER.debug("%s usou skill legada: %s", p.dados.nome, nome_skill)
                return resultado
        
        return False
    
    def _pos_uso_skill_estrategica(self, skill_profile):
        """Define ação após usar uma skill baseada na estratégia"""
        tipo = skill_profile.tipo
        
        if tipo == "DASH":
            if skill_profile.data.get("dano_chegada", 0) > 0:
                self.acao_atual = "MATAR"
            else:
                self.acao_atual = "CIRCULAR"
        elif tipo == "SUMMON":
            # Após invocar, recuar para deixar o summon lutar
            if self.skill_strategy.preferencias.get("estilo_kite"):
                self.acao_atual = "RECUAR"
            else:
                self.acao_atual = "PRESSIONAR"
        elif tipo == "TRAP":
            # Após colocar trap, tenta atrair inimigo
            self.acao_atual = "RECUAR"
        elif tipo == "TRANSFORM":
            # Transformado = agressivo
            self.acao_atual = "MATAR"
        elif tipo == "BUFF":
            if tem_buff_velocidade(skill_profile.data):
                # Com velocidade, pode aproximar ou fugir
                if self.medo > 0.4:
                    self.acao_atual = "FUGIR"
                else:
                    self.acao_atual = "APROXIMAR"
            elif tem_cura(skill_profile.data):
                # Após cura, manter distância
                self.acao_atual = "CIRCULAR"
            else:
                self.acao_atual = "PRESSIONAR"
        elif tipo == "CHANNEL" and tem_cura(skill_profile.data):
            self.acao_atual = "CIRCULAR"
        elif tipo in ["PROJETIL", "BEAM"]:
            # Skills de distância, manter range
            if self.estilo_luta in ["KITE", "RANGED", "HIT_RUN"]:
                self.acao_atual = "RECUAR"
            else:
                self.acao_atual = "CIRCULAR"
        elif tipo == "AREA":
            # Após área, pode seguir agressivo
            self.acao_atual = "MATAR"
    
    def _contar_summons_ativos(self):
        """Conta quantos summons estão ativos"""
        p = self.parent
        # Verifica buffer de summons se existir
        if hasattr(p, 'buffer_summons'):
            return len([s for s in p.buffer_summons if hasattr(s, 'vida') and s.vida > 0])
        return 0
    
    def _contar_traps_ativos(self):
        """Conta quantas traps estão ativas"""
        p = self.parent
        if hasattr(p, 'buffer_traps'):
            return len(p.buffer_traps)
        return 0
    
    def _verificar_inimigo_debuffado(self, inimigo):
        """Verifica se o inimigo tem debuffs ativos"""
        if hasattr(inimigo, 'dots_ativos') and len(inimigo.dots_ativos) > 0:
            return True
        if hasattr(inimigo, 'slow_timer') and inimigo.slow_timer > 0:
            return True
        if hasattr(inimigo, 'stun_timer') and inimigo.stun_timer > 0:
            return True
        return False

    def _usar_skill(self, skill_info):
        """Usa uma skill"""
        p = self.parent
        data = skill_info["data"]
        if data.get("ativa_ao_morrer") or data.get("revive_hp_percent"):
            return False
        custo = skill_info.get("custo", data.get("custo", 15))
        
        if p.mana < custo:
            return False
        custo_vida = calcular_custo_vida(data, getattr(p, "vida_max", 0.0))
        if custo_vida > 0.0 and getattr(p, "vida", 0.0) <= custo_vida:
            return False
        
        if skill_info["fonte"] == "arma":
            if hasattr(p, 'usar_skill_arma'):
                return p.usar_skill_arma()
        elif skill_info["fonte"] == "classe":
            if hasattr(p, 'usar_skill_classe'):
                return p.usar_skill_classe(skill_info["nome"])
        
        return False

    def _propor_movimento(self, distancia, inimigo, roll, hp_pct, inimigo_hp_pct):
        """Blocos por arma/zona/traço geram a PROPOSTA de movimento.

        Onda 5A: antes cada bloco escrevia acao_atual e dava return,
        pulando a pilha de personalidade — que rodava em 0,04-0,9% das
        decisões. Agora todo bloco devolve True (propôs) e a pilha roda
        em 100% das decisões, em _decidir_movimento.
        """
        p = self.parent
        
        # Calcula alcance real baseado no hitbox
        alcance_efetivo = self._calcular_alcance_efetivo()
        alcance_ideal = p.alcance_ideal
        
        # Zonas de distância relativas ao alcance
        muito_perto = distancia < alcance_ideal * 0.5
        no_alcance = distancia <= alcance_efetivo
        quase_no_alcance = distancia <= alcance_efetivo * 1.3
        longe = distancia > alcance_efetivo * 1.5
        muito_longe = distancia > alcance_efetivo * 2.5
        
        # Condições especiais de alta prioridade
        if hasattr(p, 'modo_adrenalina') and p.modo_adrenalina:
            self.acao_atual = "MATAR"
            return True
        if hasattr(p, 'estamina') and p.estamina < 15:
            if no_alcance and roll < 0.4:
                self.acao_atual = "ATAQUE_RAPIDO"
            else:
                self.acao_atual = "RECUAR"
            return True
        if self.modo_berserk:
            self.acao_atual = "MATAR"
            return True
        if self.modo_defensivo:
            if no_alcance and roll < 0.3:
                self.acao_atual = "CONTRA_ATAQUE"
            elif muito_perto:
                self.acao_atual = "RECUAR"
            else:
                self.acao_atual = "COMBATE"
            return True
        if self.medo > 0.75 and "DETERMINADO" not in self.tracos and "FRIO" not in self.tracos:
            if no_alcance and roll < 0.25:
                self.acao_atual = "ATAQUE_RAPIDO"
            else:
                self.acao_atual = "FUGIR"
            return True
        # === COMPORTAMENTO POR TIPO DE ARMA ===
        arma = p.dados.arma_obj if hasattr(p.dados, 'arma_obj') else None
        arma_tipo = arma.tipo if arma else ""
        
        # ARMAS RANGED (Arco, Arremesso)
        if arma_tipo in ["Arco", "Arremesso"]:
            # Para armas ranged, o alcance é muito maior
            # Recalcula zonas especificamente para ranged
            alcance_ranged = alcance_efetivo  # Já é o alcance total
            perigosamente_perto = distancia < alcance_ideal * 0.4
            perto_demais = distancia < alcance_ideal * 0.7
            distancia_boa = distancia >= alcance_ideal * 0.7 and distancia <= alcance_ranged
            longe_demais = distancia > alcance_ranged
            
            if perigosamente_perto:
                # Muito perto - FOGE!
                self.acao_atual = "FUGIR"
            elif perto_demais:
                # Perto demais - recua enquanto atira
                if roll < 0.3:
                    self.acao_atual = "ATAQUE_RAPIDO"  # Atira enquanto recua
                else:
                    self.acao_atual = "RECUAR"
            elif distancia_boa:
                # Distância perfeita - ATACA COM TUDO!
                self.acao_atual = self.rng.choice(["MATAR", "MATAR", "PRESSIONAR", "ATAQUE_RAPIDO"])
            elif longe_demais:
                # Longe demais - aproxima até entrar no alcance
                self.acao_atual = "APROXIMAR"
            else:
                # Fallback
                self.acao_atual = "MATAR"
            return True
        # ── CORRENTE / MANGUAL (zona morta!) ──
        # v2.0: lógica separada para Mangual vs outras correntes
        if arma_tipo == "Corrente":
            arma_estilo = getattr(arma, 'estilo', '') if arma else ''
            try:
                from neural_fights.core.hitbox import HITBOX_PROFILES
                perfil_hb = HITBOX_PROFILES.get("Corrente", {})
                zona_morta_ratio = perfil_hb.get("min_range_ratio", 0.25)
            except Exception:
                LOGGER.debug("Falha ao carregar perfil de hitbox do mangual", exc_info=True)
                zona_morta_ratio = 0.25
            zona_morta = alcance_efetivo * zona_morta_ratio
            
            # MANGUAL v3.0: Heavy Flail Momentum AI
            # Três zonas de combate com comportamento distinto:
            #   ZONA MORTA  (0 → 40% alcance): corrente enrolada, ineficaz → RECUAR
            #   ZONA DE SPIN (40% → 70%): distância ideal para girar → ACUMULAR + ATACAR
            #   ZONA LONGA  (70% → 100%): bola no limite da corrente → ATACAR ou APROXIMAR
            if arma_estilo == "Mangual":
                # ─────────────────────────────────────────────────────────
                # MANGUAL v3.1 — HEAVY SLAM & COMBO AI
                # Mecânica central: GOLPES PESADOS que tremem o chão.
                # Sem ficar rodando. 3 padrões de golpe em ciclo:
                #   OVERHEAD SLAM  → levanta alto e desce com tudo
                #   SIDE SWEEP     → arco lateral largo
                #   GROUND POUND   → diagonal para baixo, ricochete
                #
                # ZONAS:
                #   ZONA MORTA   (0→30%): corrente enrolada → RECUA
                #   ZONA IDEAL   (30→75%): distância de slam → ATACAR
                #   ZONA LONGA   (75→110%): bola no limite → SWEEP
                #   FORA         (>110%): APROXIMAR circulando

                zona_morta     = alcance_efetivo * 0.30
                zona_ideal_max = alcance_efetivo * 0.75
                zona_longa_max = alcance_efetivo * 1.10

                em_zona_morta = distancia < zona_morta
                em_zona_ideal = zona_morta <= distancia <= zona_ideal_max
                em_zona_longa = zona_ideal_max < distancia <= zona_longa_max
                slam_combo = getattr(self.parent, 'mangual_slam_combo', 0)
                em_combo   = slam_combo >= 2

                if em_zona_morta:
                    # Zona morta: bola enrolada — recua imediatamente
                    urgencia = 1.0 - (distancia / zona_morta)
                    if urgencia > 0.4 or roll < 0.88:
                        self.acao_atual = "RECUAR"
                    else:
                        self.acao_atual = self.rng.choice(["RECUAR", "COMBATE", "RECUAR"])
                    if hasattr(self.parent, 'mangual_slam_combo'):
                        self.parent.mangual_slam_combo = 0

                elif em_zona_ideal:
                    # ZONA IDEAL: golpes pesados
                    if inimigo_hp_pct < 0.20:
                        self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "MATAR"])
                    elif em_combo:
                        if roll < 0.70:
                            self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "ESMAGAR"])
                        else:
                            # Pausa tática: muda ângulo antes do próximo slam
                            self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR"])
                        if hasattr(self.parent, 'mangual_slam_combo'):
                            self.parent.mangual_slam_combo = min(5, slam_combo + 1)
                    else:
                        if roll < 0.55:
                            self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "COMBATE"])
                        elif roll < 0.80:
                            self.acao_atual = self.rng.choice(["FLANQUEAR", "ESMAGAR"])
                        else:
                            self.acao_atual = self.rng.choice(["PRESSIONAR", "ESMAGAR"])
                        if hasattr(self.parent, 'mangual_slam_combo'):
                            self.parent.mangual_slam_combo = 1

                elif em_zona_longa:
                    # ZONA LONGA: sweep lateral eficaz, avança para entrar na ideal
                    if roll < 0.55:
                        self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR"])
                    elif roll < 0.80:
                        self.acao_atual = self.rng.choice(["PRESSIONAR", "MATAR"])
                    else:
                        self.acao_atual = self.rng.choice(["CIRCULAR", "FLANQUEAR"])

                else:  # fora_alcance
                    # FORA: aproxima circulando (nunca em linha reta)
                    if roll < 0.60:
                        self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR", "APROXIMAR"])
                    else:
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR", "APROXIMAR"])

            else:
                # Outras correntes (Chicote, Meteor Hammer, etc.)
                if distancia < zona_morta:
                    self.acao_atual = "RECUAR"
                elif distancia < alcance_ideal:
                    self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "FLANQUEAR"])
                elif no_alcance:
                    if inimigo_hp_pct < 0.3:
                        self.acao_atual = "MATAR"
                    elif roll < 0.7:
                        self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "MATAR"])
                    else:
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR"])
                else:
                    self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR"])
            return True
        # ── ADAGAS GÊMEAS (Dupla) - combo agressivo ──
        # v2.0: IA adaptada para o sistema de combo L/R das Adagas
        if arma_tipo == "Dupla":
            arma_estilo = getattr(arma, 'estilo', '') if arma else ''
            
            if arma_estilo == "Adagas Gêmeas":
                # ───────────────────────────────────────────────────────────
                # ADAGAS GÊAMEAS v3.1 — IA repaginada para alcance real
                # ───────────────────────────────────────────────────────────
                # Com lâminas mais longas (alcance ~70% do max), a IA tem
                # QUATRO faixas comportamentais claras:
                #
                #   ENGAJAMENTO  (≤ alcance_ideal):    ATACAR E COMBINAR
                #   PRESSÃO      (ideal → 130%):     MANTER PRESSÃO, não deixar respirar
                #   APROXIMAÇÃO  (130% → 220%):     DASH LATERAL (não frontal)
                #   REPOSICIONAMENTO (> 220%):         CÍRCULO + FLANQUEAR
                #
                # Princípio: nunca recua a menos que HP crítico. Sabe que
                # precisa estar perto, então investe no approach com cuidado.

                engajamento = alcance_ideal           # alcance real de combate
                pressao     = alcance_ideal * 1.30    # quasi-alcance: um passo
                dash_curto  = alcance_ideal * 2.20    # dash normal alcança aqui

                em_engajamento = distancia <= engajamento
                em_pressao     = engajamento < distancia <= pressao
                em_dash        = pressao < distancia <= dash_curto
                muito_longe    = distancia > dash_curto

                # Onda 8E (bug #5): combo_atual vive no BRAIN (delegado ao
                # EmotionSystem) — lido no Lutador era sempre 0 e os
                # ramos de frenesi das Adagas eram inalcançáveis.
                combo_hits = getattr(self, 'combo_atual', 0)
                combo_ativo  = combo_hits > 2
                combo_frenzy = combo_hits > 5

                if em_engajamento:
                    # ── No alcance: agressividade e variação de ângulo ──
                    if hp_pct < 0.20 and roll < 0.50:
                        # HP crítico: saída lateral antes de morrer
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "RECUAR", "FLANQUEAR"])
                    elif inimigo_hp_pct < 0.25:
                        # Inimigo quase morto: finalizador direto
                        self.acao_atual = self.rng.choice(["MATAR", "MATAR", "ATAQUE_RAPIDO"])
                    elif combo_frenzy:
                        # Frenzy: rotação rápida, não deixa reagir
                        self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO",
                                                          "ATAQUE_RAPIDO", "MATAR",
                                                          "COMBATE"])
                    elif combo_ativo:
                        if roll < 0.65:
                            self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "ESMAGAR"])
                        else:
                            # Muda ângulo para confundir bloqueio
                            self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR"])
                    else:
                        if roll < 0.60:
                            self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "COMBATE"])
                        else:
                            self.acao_atual = self.rng.choice(["ATAQUE_RAPIDO", "FLANQUEAR"])

                elif em_pressao:
                    # ── Zona de pressão: um passo do alcance ──
                    # Prefere PRESSIONAR ou FLANQUEAR (não APROXIMAR passivo)
                    if inimigo_hp_pct < 0.30:
                        self.acao_atual = self.rng.choice(["PRESSIONAR", "MATAR", "PRESSIONAR"])
                    elif roll < 0.55:
                        self.acao_atual = self.rng.choice(["PRESSIONAR", "ATAQUE_RAPIDO"])
                    elif roll < 0.80:
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "PRESSIONAR"])
                    else:
                        self.acao_atual = self.rng.choice(["CIRCULAR", "FLANQUEAR"])

                elif em_dash:
                    # ── Zona de dash: fecha distância com movimento lateral ──
                    # Nunca corre em linha reta — chega pelo flanco
                    if roll < 0.45:
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "PRESSIONAR"])
                    elif roll < 0.75:
                        self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR"])
                    else:
                        self.acao_atual = self.rng.choice(["CIRCULAR", "APROXIMAR"])

                else:
                    # ── Muito longe: flankeia antes do dash longo ──
                    if roll < 0.40:
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR"])
                    else:
                        self.acao_atual = self.rng.choice(["APROXIMAR", "FLANQUEAR"])

            else:
                # Outras armas duplas (Garras, Tonfas, etc.)
                if muito_longe:
                    self.acao_atual = "APROXIMAR"
                elif longe:
                    self.acao_atual = self.rng.choice(["APROXIMAR", "FLANQUEAR", "PRESSIONAR"])
                elif no_alcance:
                    if inimigo_hp_pct < 0.3:
                        self.acao_atual = "MATAR"
                    elif roll < 0.7:
                        self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "MATAR"])
                    else:
                        self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR"])
                else:
                    self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR"])
            return True
        # === LÓGICA PADRÃO PARA OUTRAS ARMAS ===
        
        # Finalização de inimigo com pouca vida
        if inimigo_hp_pct < 0.25 and no_alcance:
            self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "MATAR"])
            return True
        # Dentro do alcance - ataca
        if no_alcance:
            if inimigo_hp_pct < 0.3:
                self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "MATAR"])
            elif roll < 0.55:
                self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "COMBATE"])
            elif roll < 0.8:
                self.acao_atual = self.rng.choice(["FLANQUEAR", "CIRCULAR", "PRESSIONAR"])
            else:
                self.acao_atual = "CONTRA_ATAQUE"
            return True
        # Quase no alcance - pressiona
        if quase_no_alcance:
            if roll < 0.65:
                self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR", "FLANQUEAR"])
            else:
                self.acao_atual = self.rng.choice(["COMBATE", "POKE", "CIRCULAR"])
            return True
        # Longe - aproxima
        if longe or muito_longe:
            self.acao_atual = self.rng.choice(["APROXIMAR", "PRESSIONAR", "APROXIMAR"])
            return True
        # Traços especiais
        if "COVARDE" in self.tracos and hp_pct < 0.35:
            self.vezes_que_fugiu += 1
            if self.vezes_que_fugiu > 4:
                self.acao_atual = "MATAR"
                self.raiva = 0.9
            else:
                self.acao_atual = "FUGIR"
            return True
        if "BERSERKER" in self.tracos and hp_pct < 0.45:
            self.acao_atual = "MATAR"
            return True
        if "SANGUINARIO" in self.tracos and inimigo_hp_pct < 0.3:
            self.acao_atual = "MATAR"
            return True
        if "PREDADOR" in self.tracos and inimigo_hp_pct < 0.4:
            self.acao_atual = "APROXIMAR"
            return True
        if "PERSEGUIDOR" in self.tracos and distancia > 5.0:
            self.acao_atual = "APROXIMAR"
            return True
        if "KAMIKAZE" in self.tracos:
            self.acao_atual = "MATAR"
            return True

        return False

    # =========================================================================
    # PLANO DE LUTA (Onda 8E)
    # =========================================================================

    def _atualizar_plano(self, dt, distancia, inimigo):
        """Mantém a intenção tática viva: escolhe na expiração e
        interrompe em spike de dano (>12% do HP desde a escolha, com o
        compromisso da personalidade decidindo se o plano sobrevive)."""
        p = self.parent
        hp = p.vida / p.vida_max if p.vida_max else 1.0
        plano = self.plano

        if plano is not None:
            spike = (
                self._plano_hp_inicial - hp > 0.12
                and self.tempo_desde_dano < 0.3
            )
            if spike and self.rng.random() > plano["compromisso"]:
                plano = None  # o soco mudou a conversa
            elif self.tempo_combate >= plano["expira_em"]:
                plano = None

        if plano is None:
            anterior = self.plano["tipo"] if self.plano else None
            self.plano = self._escolher_plano(distancia, inimigo)
            self._plano_hp_inicial = hp
            self.contadores["planos"] = self.contadores.get("planos", 0) + 1
            # Onda 8F: troca de plano é legível — tell só quando o TIPO
            # muda (renovar o mesmo plano não é notícia).
            if self.plano["tipo"] != anterior:
                self.tell_atual = {"tipo": "plano",
                                   "plano": self.plano["tipo"],
                                   "ate": self.tempo_combate + 0.6}

    def _escolher_plano(self, distancia, inimigo):
        """Escolhe a intenção tática pelo que o lutador TEM: eixos de
        personalidade × arma (própria e do oponente, via os campos do
        WeaponProfile que eram calculados e nunca lidos) × leitura do
        oponente × contexto espacial."""
        p = self.parent
        perfil = self.perfil
        hp = p.vida / p.vida_max if p.vida_max else 1.0
        esp = self.consciencia_espacial
        percep = self.percepcao_arma
        perfil_inimigo = percep.get("arma_inimigo_perfil")
        recovery_inimigo = getattr(perfil_inimigo, "tempo_recovery", 0.0) or 0.0
        zona_morta_inimigo = getattr(perfil_inimigo, "zona_morta", 0.0) or 0.0

        agress = self.agressividade_efetiva()
        scores = {
            "PRESSIONAR": 0.3 + agress * 0.6 + max(0.0, self.momentum) * 0.3,
            "BAITAR_E_PUNIR": (
                0.15
                + max(0.0, perfil.get("cautela", 0.0)) * 0.3
                + self.habilidade_leitura * 0.35
                + (0.25 if recovery_inimigo > 0.18 else 0.0)
            ),
            "MANTER_ZONA_MORTA": (
                0.5 + max(0.0, perfil.get("frieza", 0.0)) * 0.2
                if zona_morta_inimigo > 0.8
                else 0.0
            ),
            "LEVAR_PARA_PAREDE": (
                0.2
                + max(0.0, perfil.get("perseguicao", 0.0)) * 0.4
                + (0.35 if esp.get("oponente_contra_parede") else 0.0)
            ),
            "CACAR_JANELA_SKILL": 0.0,
            "RECUPERAR": (
                0.0
                if hp > 0.55
                else (0.75 - hp) + max(0.0, perfil.get("medo", 0.0)) * 0.4
                + self.medo * 0.3
            ),
        }
        if self.skill_strategy is not None:
            role = self.skill_strategy.role_principal.value
            if role in ("artillery", "burst_mage", "control_mage",
                        "summoner", "buffer", "channeler"):
                scores["CACAR_JANELA_SKILL"] = (
                    0.4 + max(0.0, perfil.get("skill_uso", 0.0)) * 0.3
                )

        # Ruído de personalidade: caos alarga a loteria, frieza estreita.
        ruido = 0.25 * (1.0 + max(0.0, perfil.get("caos", 0.0)))
        for tipo in scores:
            scores[tipo] += self.rng.uniform(0.0, ruido)

        escolhido = max(scores, key=scores.get)
        disciplina = getattr(self, "disciplina_tatica", 0.5)
        duracao = self.rng.uniform(2.0, 4.0) + disciplina * 2.0
        return {
            "tipo": escolhido,
            "expira_em": self.tempo_combate + duracao,
            "compromisso": 0.4 + disciplina * 0.5,
        }

    def _aplicar_plano_de_luta(self, distancia, inimigo):
        """Estágio 0 da pilha: o plano enviesa a proposta; os estágios de
        personalidade seguintes continuam perturbando (plano ≠ script)."""
        plano = self.plano
        if plano is None:
            return
        if self.rng.random() > plano["compromisso"]:
            return  # hoje a personalidade fala mais alto que o plano

        tipo = plano["tipo"]
        acao = self.acao_atual
        if tipo == "PRESSIONAR":
            if acao in ("COMBATE", "CIRCULAR", "POKE", "APROXIMAR_LENTO",
                        "BLOQUEAR"):
                self.acao_atual = self.rng.choice(
                    ["PRESSIONAR", "APROXIMAR", "MATAR"]
                )
        elif tipo == "BAITAR_E_PUNIR":
            # Fica na borda do alcance convidando o whiff — a punição em
            # si vem do gate da 8D quando o recovery aparecer.
            if distancia < 4.5 and acao in ("MATAR", "ESMAGAR",
                                            "ATAQUE_RAPIDO", "PRESSIONAR"):
                self.acao_atual = self.rng.choice(["POKE", "CIRCULAR", "RECUAR"])
        elif tipo == "MANTER_ZONA_MORTA":
            zona = getattr(
                self.percepcao_arma.get("arma_inimigo_perfil"),
                "zona_morta", 0.0,
            ) or 0.0
            if zona > 0.0:
                if distancia > zona * 0.9:
                    self.acao_atual = self.rng.choice(
                        ["APROXIMAR", "PRESSIONAR"]
                    )
                else:
                    self.acao_atual = self.rng.choice(["MATAR", "COMBATE"])
        elif tipo == "LEVAR_PARA_PAREDE":
            if acao in ("COMBATE", "CIRCULAR", "POKE"):
                self.acao_atual = self.rng.choice(["PRESSIONAR", "FLANQUEAR"])
        elif tipo == "CACAR_JANELA_SKILL":
            # Caster: mantém a distância da rotação, sem trocação à toa.
            if distancia < self.parent.alcance_ideal * 0.7:
                self.acao_atual = self.rng.choice(["RECUAR", "CIRCULAR"])
            elif acao in ("MATAR", "ESMAGAR"):
                self.acao_atual = "COMBATE"
        elif tipo == "RECUPERAR":
            hp = self.parent.vida / self.parent.vida_max
            if hp < 0.25 and self.medo > 0.4:
                self.acao_atual = "FUGIR"
            elif acao in ("MATAR", "ESMAGAR", "PRESSIONAR", "APROXIMAR",
                          "COMBATE"):
                self.acao_atual = self.rng.choice(["RECUAR", "CIRCULAR"])

    def _decidir_movimento(self, distancia, inimigo):
        self.contadores["decisoes"] += 1
        # Onda 8E (alvo A6): decisões tomadas em range de melee — o fix
        # do early-return de ataque existe para esta fração não ser ~0.
        if distancia <= self._calcular_alcance_efetivo() * 1.3:
            self.contadores["decisoes_melee"] = (
                self.contadores.get("decisoes_melee", 0) + 1
            )
        """Proposta + pipeline (Onda 5A): a pilha roda em TODA decisão."""
        p = self.parent
        roll = self.rng.random()
        hp_pct = p.vida / p.vida_max
        inimigo_hp_pct = inimigo.vida / inimigo.vida_max if inimigo.vida_max > 0 else 1.0

        acao_antes = self._acao_atual
        self._modo_proposta = True
        try:
            if not self._propor_movimento(distancia, inimigo, roll, hp_pct, inimigo_hp_pct):
                # Sem proposta de bloco: o estilo de luta é a base.
                self._comportamento_estilo(distancia, roll, hp_pct, inimigo_hp_pct)

            # === A PILHA (roda sempre — era o coração morto da IA) ===
            self.contadores["pilha_completa"] += 1
            # Estágio 0 (Onda 8E): o plano de luta enviesa a proposta;
            # todos os estágios de personalidade abaixo seguem valendo.
            self._aplicar_plano_de_luta(distancia, inimigo)
            self._aplicar_agressividade_efetiva()
            self._aplicar_eixos_orfaos(distancia, inimigo)
            self._aplicar_modificadores_movimento(distancia, roll)
            self._aplicar_modificadores_humor()
            self._aplicar_modificadores_filosofia()
            self._aplicar_modificadores_momentum(distancia, inimigo_hp_pct)
            self._aplicar_modificadores_leitura(distancia, inimigo)
            self._evitar_repeticao_excessiva()
            self._aplicar_modificadores_espaciais(distancia, inimigo)
            self._aplicar_modificadores_armas(distancia, inimigo)
            # ÚLTIMO estágio de propósito: sobreviver vence qualquer
            # preferência de arma/estilo quando o perigo é real.
            self._aplicar_instinto_sobrevivencia(distancia, hp_pct)
        finally:
            proposta = self._acao_atual
            self._acao_atual = acao_antes
            self._modo_proposta = False

        # Persistência de intenção (fechamento da O5): churn sem urgência
        # não é decisão — 25% das trocas propostas mantêm a intenção
        # corrente. Instintos (P1) e reações seguem interrompendo na hora,
        # e o próximo tick re-avalia de qualquer forma. Com tick base 0,5,
        # a mediana de ação era matematicamente limitada a ~0,43s se toda
        # decisão trocasse de ação; é isto que separa "mudou de ideia" de
        # "tremeu" (V2: intenção legível >= 0,5s).
        if proposta != acao_antes and self.rng.random() < 0.25:
            proposta = acao_antes

        # Commit único da decisão: prioridade 3, segura até o próximo tick.
        self._definir_acao(proposta, fonte="decisao", prioridade=3)

    def agressividade_efetiva(self):
        """f(agressividade_base, eixo agressao, humor) — Onda 5A.

        É aqui que agressividade_base (e o agressividade_mod dos 26
        presets, no-op até agora) ganha leitor vivo, somado ao eixo dos
        162 traços e ao humor do momento.
        """
        base = self.agressividade_base
        eixo = self.perfil.get("agressao", 0.0) * 0.25
        humor = {
            "FURIOSO": 0.2, "ANIMADO": 0.1, "CONFIANTE": 0.1,
            "DESESPERADO": 0.15, "CAUTELOSO": -0.15, "ENTEDIADO": -0.05,
            "ASSUSTADO": -0.25, "BERSERK": 0.3, "EUFORICO": 0.15,
            "GLACIAL": -0.1,
        }.get(self.humor, 0.0)
        # Onda 5E: o ritmo de batalha VIVE — o plano previa deletar
        # ritmo_modificadores se D6 fechasse sem ele (fechou, 0,895), mas
        # D1 nao fecha: fases ciclicas de agressao (+-0,3 a cada 4-5s) sao
        # variancia MECANICA de meio de luta — exatamente o que troca
        # lideranca. O leitor antigo (get_agressividade_efetiva) era morto;
        # este e o consumidor real.
        ritmo = getattr(self, "ritmo_modificadores", {}).get("agressividade", 0)
        return max(0.05, min(0.98, base + eixo + humor + ritmo * 0.6))

    def _aplicar_agressividade_efetiva(self):
        """Estágio da pilha: a proposta escala/desescala pela agressividade."""
        agg = self.agressividade_efetiva()
        r = self.rng.random()
        if agg > 0.6 and self.acao_atual in ("COMBATE", "POKE", "CIRCULAR", "RECUAR"):
            if r < (agg - 0.6) * 0.9:
                self.acao_atual = self.rng.choice(["PRESSIONAR", "MATAR", "APROXIMAR"])
        elif agg < 0.4 and self.acao_atual in ("MATAR", "ESMAGAR", "PRESSIONAR"):
            if r < (0.4 - agg) * 0.9:
                self.acao_atual = self.rng.choice(["COMBATE", "POKE", "FLANQUEAR"])

    def _aplicar_instinto_sobrevivencia(self, distancia, hp_pct):
        """O medo tem CONSEQUÊNCIA de movimento (pedido do dono: 'quero
        que o personagem tenha medo de tomar os danos e realmente queira
        sobreviver, não ficar colado').

        perigo = medo (contínuo do motor emocional, já modulado pela
        coragem/frieza do lutador) + ferida real. Acima do limiar, as
        intenções de risco viram RECUAR/CIRCULAR/FUGIR com probabilidade
        crescente — corajoso ferido ainda avança; covarde ferido corre.
        Último estágio da pilha: sobreviver não é preferência, é veto.
        """
        # Dial medido (sonda de 6 lutas): medo p50 quando ferido é ~0,29
        # — com limiar 0,5 o estágio disparava só ~20%/decisão e MATAR
        # seguia dominando a agonia. Ferida pesa mais que pânico puro; o
        # meio de luta saudável (hp 0,5, medo 0,3 → 0,42) continua
        # abaixo do limiar.
        perigo = self.medo * 0.55 + (1.0 - hp_pct) * 0.5
        if hp_pct < 0.3:
            perigo += 0.2
        if perigo < 0.45:
            return
        acoes_de_risco = (
            "MATAR", "ESMAGAR", "PRESSIONAR", "APROXIMAR",
            "COMBATE", "POKE", "BLOQUEAR",
        )
        if self.acao_atual not in acoes_de_risco:
            return
        if self.rng.random() >= (perigo - 0.45) * 1.6:
            return
        if hp_pct < 0.25 and self.medo > 0.35:
            self.acao_atual = "FUGIR"
        elif distancia < 3.0:
            # colado no perigo: abre distância AGORA (2/3) ou sai de
            # linha (1/3) — o "desviar" que o espectador lê.
            self.acao_atual = self.rng.choice(["RECUAR", "RECUAR", "CIRCULAR"])
        else:
            self.acao_atual = self.rng.choice(["CIRCULAR", "POKE", "RECUAR"])

    def _aplicar_eixos_orfaos(self, distancia, inimigo):
        """Consumidores dos eixos órfãos (Onda 5A): mobilidade e perseguicao.

        Os 162 traços declaram posições nesses eixos desde a migração e
        nenhum código as lia. mobilidade pesa reposicionamento; perseguicao
        decide a resposta a um inimigo fugindo. (skill_uso vive no portão
        de skills.)
        """
        mob = self.perfil.get("mobilidade", 0.0)
        if mob > 0.2 and self.acao_atual in ("COMBATE", "POKE", "BLOQUEAR"):
            if self.rng.random() < mob * 0.35:
                self.acao_atual = self.rng.choice(["CIRCULAR", "FLANQUEAR"])

        pers = self.perfil.get("perseguicao", 0.0)
        # Onda 8A: "inimigo fugindo" é a velocidade observada, não o verbo
        # interno do brain adversário.
        if self._observar(inimigo).intencao == "recuando":
            if pers > 0.0 and self.rng.random() < 0.3 + pers * 0.5:
                self.acao_atual = self.rng.choice(["PRESSIONAR", "APROXIMAR"])
            elif pers < -0.3 and self.rng.random() < -pers * 0.4:
                self.acao_atual = self.rng.choice(["POKE", "COMBATE"])

    def _motor_emocional(self):
        """Motor emocional, com criação preguiçosa para fakes de contrato
        (object.__new__ sem __init__ — mesmo padrão do escritor único)."""
        motor = self.__dict__.get("emocoes")
        if motor is None:
            from neural_fights.ai.emotions import EmotionSystem

            motor = EmotionSystem(self)
            self.emocoes = motor
        return motor

    medo = _delegado_emocional("medo")
    raiva = _delegado_emocional("raiva")
    confianca = _delegado_emocional("confianca")
    frustracao = _delegado_emocional("frustracao")
    adrenalina = _delegado_emocional("adrenalina")
    excitacao = _delegado_emocional("excitacao")
    tedio = _delegado_emocional("tedio")
    humor = _delegado_emocional("humor")
    cd_mudanca_humor = _delegado_emocional("cd_mudanca_humor")
    hits_recebidos_total = _delegado_emocional("hits_recebidos_total")
    hits_dados_total = _delegado_emocional("hits_dados_total")
    hits_recebidos_recente = _delegado_emocional("hits_recebidos_recente")
    hits_dados_recente = _delegado_emocional("hits_dados_recente")
    tempo_desde_dano = _delegado_emocional("tempo_desde_dano")
    tempo_desde_hit = _delegado_emocional("tempo_desde_hit")
    combo_atual = _delegado_emocional("combo_atual")
    max_combo = _delegado_emocional("max_combo")

    @property
    def acao_atual(self):
        return self._acao_atual

    @acao_atual.setter
    def acao_atual(self, valor):
        # Onda 5B: os ~214 escritores legados passam TODOS por aqui. Durante
        # a proposta (_decidir_movimento) o rascunho é livre; fora dela, a
        # escrita respeita o min-hold do escritor único.
        # getattr defensivo: testes de contrato constroem AIBrain via
        # object.__new__ sem __init__ (mesmo padrao de hits_ecoados na O3).
        if getattr(self, "_modo_proposta", False):
            self._acao_atual = valor
            return
        self._definir_acao(valor, fonte="legado",
                           prioridade=getattr(self, "_contexto_escrita", 2))

    def _definir_acao(self, acao, fonte="legado", prioridade=2, hold_s=None):
        """Escritor único de acao_atual com min-hold por prioridade (5B).

        P1 instinto (segura 0,3-0,5s), P2 reação/legado (0,4s), P3 decisão
        (segura até o próximo tick). Escrita da mesma ação é no-op — não
        renova hold nem conta troca. Prioridade mais forte (menor) sempre
        interrompe; a decisão agendada (P3) pode substituir a própria P3.
        A ação mediana era 16,7ms com 66% das trocas em <=2 frames — tremor,
        não intenção.
        """
        if acao == getattr(self, "_acao_atual", None):
            return True
        agora = getattr(self, "tempo_combate", 0.0)
        hold_prio = getattr(self, "_acao_hold_prio", 9)
        segurando = agora < getattr(self, "_acao_hold_ate", 0.0)
        if segurando and prioridade >= hold_prio and not (
            prioridade == 3 and hold_prio == 3
        ):
            contadores = getattr(self, "contadores", None)
            if contadores is not None:
                contadores["escritas_seguradas"] = contadores.get(
                    "escritas_seguradas", 0) + 1
            return False
        self._acao_atual = acao
        self._acao_fonte = fonte
        if hold_s is None:
            if prioridade == 1:
                rng = getattr(self, "rng", None)
                hold_s = rng.uniform(0.3, 0.5) if rng is not None else 0.4
            elif prioridade == 3:
                hold_s = 0.55
            else:
                # P2 e a restricao vinculante da mediana de acao: reacoes/
                # coreografo commitam na cadencia do proprio hold (V2).
                hold_s = 0.55
        self._acao_hold_ate = agora + hold_s
        self._acao_hold_prio = prioridade
        contadores = getattr(self, "contadores", None)
        if contadores is not None:
            contadores["escritas_aceitas"] = contadores.get(
                "escritas_aceitas", 0) + 1
        return True

    def _aplicar_modificadores_momentum(self, distancia, inimigo_hp_pct):
        """Aplica modificadores baseados no momentum da luta"""
        # Momentum positivo = mais agressivo
        if self.momentum > 0.3:
            if self.acao_atual in ["CIRCULAR", "RECUAR", "BLOQUEAR", "FLANQUEAR"]:
                if self.rng.random() < self.momentum * 0.5:
                    self.acao_atual = self.rng.choice(["PRESSIONAR", "MATAR", "APROXIMAR"])
        
        # Momentum negativo = mais cauteloso (mas não covarde)
        elif self.momentum < -0.3:
            if self.acao_atual in ["MATAR", "ESMAGAR"]:
                if self.rng.random() < abs(self.momentum) * 0.3:
                    self.acao_atual = self.rng.choice(["COMBATE", "FLANQUEAR", "CIRCULAR"])
        
        # Pressão alta = decisões mais extremas
        if self.pressao_aplicada > 0.7:
            if self.rng.random() < 0.3:
                self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "PRESSIONAR"])
        
        if self.pressao_recebida > 0.7:
            if self.rng.random() < 0.25:
                # Ou contra-ataca ou recua - decisão de momento
                if self.raiva > self.medo:
                    self.acao_atual = self.rng.choice(["CONTRA_ATAQUE", "MATAR"])
                else:
                    self.acao_atual = self.rng.choice(["RECUAR", "CIRCULAR", "FLANQUEAR"])
    
    def _aplicar_modificadores_leitura(self, distancia, inimigo):
        """Aplica modificadores baseados na leitura do oponente"""
        leitura = self.leitura_oponente
        
        # Se oponente é previsível, aproveita
        if leitura["previsibilidade"] > 0.7:
            if self.rng.random() < 0.2:
                # Antecipa e contra
                if leitura["agressividade_percebida"] > 0.6:
                    self.acao_atual = "CONTRA_ATAQUE"
                else:
                    self.acao_atual = "PRESSIONAR"
        
        # Se oponente é muito agressivo
        if leitura["agressividade_percebida"] > 0.8:
            if "REATIVO" in self.tracos or "OPORTUNISTA" in self.tracos:
                if self.rng.random() < 0.3:
                    self.acao_atual = "CONTRA_ATAQUE"
        
        # Se oponente pula muito, posiciona melhor
        if leitura["frequencia_pulo"] > 0.4:
            if self.rng.random() < 0.2:
                self.acao_atual = "COMBATE"  # Espera ele cair
        
        # Adapta à tendência lateral do oponente
        if distancia < 4.0:
            if leitura["tendencia_esquerda"] > 0.65:
                if self.rng.random() < 0.15:
                    self.dir_circular = 1  # Vai pro outro lado
            elif leitura["tendencia_esquerda"] < 0.35:
                if self.rng.random() < 0.15:
                    self.dir_circular = -1
    
    # Onda 8E (bug #6): a variação anti-repetição escolhe entre ações que
    # SERVEM ao plano atual — antes era um sorteio uniforme sobre 7 verbos
    # que sabotava qualquer estratégia em curso (ruído anti-estratégia).
    _VARIACOES_POR_PLANO = {
        "PRESSIONAR": ["MATAR", "PRESSIONAR", "FLANQUEAR", "ATAQUE_RAPIDO"],
        "BAITAR_E_PUNIR": ["POKE", "CIRCULAR", "COMBATE", "RECUAR"],
        "MANTER_ZONA_MORTA": ["COMBATE", "MATAR", "PRESSIONAR", "CIRCULAR"],
        "LEVAR_PARA_PAREDE": ["PRESSIONAR", "FLANQUEAR", "APROXIMAR"],
        "CACAR_JANELA_SKILL": ["CIRCULAR", "COMBATE", "RECUAR", "POKE"],
        "RECUPERAR": ["RECUAR", "CIRCULAR", "POKE", "BLOQUEAR"],
    }

    def _evitar_repeticao_excessiva(self):
        """Evita repetir a mesma ação muitas vezes seguidas"""
        if len(self.historico_acoes) < 3:
            return

        # Verifica repetição
        ultimas_3 = self.historico_acoes[-3:]
        if ultimas_3.count(self.acao_atual) >= 2:
            # Está repetindo muito, varia — dentro do plano em curso.
            if self.rng.random() < 0.4:
                plano = self.plano
                acoes_alternativas = self._VARIACOES_POR_PLANO.get(
                    plano["tipo"] if plano else None,
                    ["MATAR", "CIRCULAR", "FLANQUEAR", "COMBATE",
                     "APROXIMAR", "ATAQUE_RAPIDO", "PRESSIONAR"],
                )
                # Remove a ação atual das alternativas
                acoes_alternativas = [
                    a for a in acoes_alternativas if a != self.acao_atual
                ]
                if acoes_alternativas:
                    self.acao_atual = self.rng.choice(acoes_alternativas)
    
    def _calcular_alcance_efetivo(self):
        """Calcula alcance real de ataque baseado na arma e hitbox profile v12.2"""
        p = self.parent
        
        arma = p.dados.arma_obj if p.dados else None
        if not arma:
            return 2.0  # Fallback sem arma
        
        tipo = arma.tipo
        raio = p.raio_fisico if hasattr(p, 'raio_fisico') else 0.4
        
        # Importa perfis de hitbox para cálculo preciso
        try:
            from neural_fights.core.hitbox import HITBOX_PROFILES
            profile = HITBOX_PROFILES.get(tipo, HITBOX_PROFILES.get("Reta", {}))
            range_mult = profile.get("range_mult", 2.0)
        except Exception:
            LOGGER.debug("Falha ao calcular alcance pelo perfil de hitbox", exc_info=True)
            range_mult = 2.0
        
        # Alcance base = raio do personagem * multiplicador do tipo de arma
        alcance_base = raio * range_mult
        
        # Ajustes específicos por tipo
        if tipo == "Reta":
            # Lâminas: considera tamanho real da arma
            comp_total = (getattr(arma, 'comp_cabo', 20) + getattr(arma, 'comp_lamina', 40)) / PPM
            return alcance_base + comp_total * 0.3
        
        elif tipo == "Dupla":
            # Adagas: alcance generoso (lâminas rápidas + extensão do braço)
            # v3.1: aumentado comp * 0.75 para a IA ter espaço real de combate
            comp = getattr(arma, 'comp_lamina', 55) / PPM
            return alcance_base + comp * 0.75
        
        elif tipo == "Corrente":
            # Corrente: alcance longo mas zona morta grande
            comp = getattr(arma, 'comp_corrente', 80) / PPM
            zona_morta = alcance_base * profile.get("min_range_ratio", 0.25)
            # Retorna distância ideal (entre zona morta e máximo)
            return (alcance_base + zona_morta) / 2 + comp * 0.2
        
        elif tipo in ("Arremesso", "Arco", "Mágica"):
            # Onda 4: o alcance de DECISÃO é o mesmo alcance de DISPARO do
            # motor (fonte única no catálogo). Os fatores 0,7/1,0 daqui
            # compensavam a estimativa raio*range_mult, que divergia do motor.
            from neural_fights.models.constants import alcance_ranged_m
            return alcance_ranged_m(tipo)
        
        elif tipo == "Orbital":
            # Orbitais: fica perto
            dist_orbe = getattr(arma, 'distancia', 50) / PPM
            return raio + dist_orbe * 0.8
        
        elif tipo == "Transformável":
            # Transformável: depende da forma atual
            forma = getattr(arma, 'forma_atual', 1)
            if forma == 1:
                comp = getattr(arma, 'forma1_lamina', 40) / PPM
            else:
                comp = getattr(arma, 'forma2_lamina', 60) / PPM
            return alcance_base + comp * 0.3
        
        return alcance_base

    def _comportamento_estilo(self, distancia, roll, hp_pct, inimigo_hp_pct):
        """Comportamento baseado no estilo de luta - v12.2"""
        # Usa alcance efetivo calculado, não o ideal
        alcance = self._calcular_alcance_efetivo()
        alcance_ideal = self.parent.alcance_ideal
        
        estilo_data = ESTILOS_LUTA.get(self.estilo_luta, ESTILOS_LUTA["BALANCED"])
        agressividade = estilo_data.get("agressividade_base", 0.6)
        
        tempo_boost = min(0.2, self.tempo_combate / 60.0)
        agressividade += tempo_boost
        
        if inimigo_hp_pct < 0.3:
            agressividade += 0.25
        elif inimigo_hp_pct < 0.5:
            agressividade += 0.1
            
        hp_diff = hp_pct - inimigo_hp_pct
        if hp_diff > 0.2:
            agressividade += hp_diff * 0.3
            
        if hp_pct < 0.25 and "BERSERKER" not in self.tracos:
            agressividade -= 0.1
        
        agressividade = max(0.3, min(1.0, agressividade))
        
        # Zonas baseadas no alcance efetivo
        if distancia < alcance_ideal * 0.7:
            zona = "perto"
        elif distancia > alcance * 1.3:
            zona = "longe"
        else:
            zona = "medio"
        
        if zona == "perto":
            self.acao_atual = estilo_data["acao_perto"]
        elif zona == "longe":
            self.acao_atual = estilo_data["acao_longe"]
        else:
            self.acao_atual = estilo_data["acao_medio"]
        
        if roll < agressividade * 0.25:
            acoes_agressivas = ["MATAR", "ATAQUE_RAPIDO", "PRESSIONAR", "ESMAGAR", "FLANQUEAR"]
            self.acao_atual = self.rng.choice(acoes_agressivas)
        elif roll < 0.12:
            acoes_variadas = ["CIRCULAR", "FLANQUEAR", "COMBATE", "POKE"]
            self.acao_atual = self.rng.choice(acoes_variadas)
        
        # Se muito longe, aproxima
        if distancia > alcance * 2.0 and self.acao_atual not in ["APROXIMAR", "MATAR", "PRESSIONAR"]:
            if self.rng.random() < 0.8:
                self.acao_atual = "APROXIMAR"
        
        # Se no alcance de ataque, ataca
        if distancia <= alcance and self.acao_atual not in ["MATAR", "ATAQUE_RAPIDO", "ESMAGAR", "CONTRA_ATAQUE", "PRESSIONAR"]:
            if self.rng.random() < agressividade * 0.6:
                self.acao_atual = self.rng.choice(["MATAR", "ATAQUE_RAPIDO", "COMBATE", "PRESSIONAR"])

    def _aplicar_modificadores_movimento(self, distancia, roll):
        """Modifica ação baseado nos traços"""
        if "AGRESSIVO" in self.tracos:
            if self.acao_atual in ["CIRCULAR", "BLOQUEAR", "RECUAR", "COMBATE"]:
                if self.rng.random() < 0.55:
                    self.acao_atual = self.rng.choice(["MATAR", "APROXIMAR", "PRESSIONAR"])
        
        if "CALCULISTA" in self.tracos:
            if self.acao_atual == "MATAR" and distancia > 4.0:
                if self.rng.random() < 0.25:
                    self.acao_atual = "FLANQUEAR"
        
        if "PACIENTE" in self.tracos:
            if self.acao_atual in ["APROXIMAR", "MATAR"]:
                if self.rng.random() < 0.2:
                    self.acao_atual = "COMBATE"
        
        if "IMPRUDENTE" in self.tracos:
            if self.acao_atual in ["BLOQUEAR", "RECUAR", "FUGIR", "CIRCULAR", "COMBATE"]:
                if self.rng.random() < 0.6:
                    self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR"])
        
        if "ERRATICO" in self.tracos or "CAOTICO" in self.tracos:
            if self.rng.random() < 0.25:
                acoes = ["FLANQUEAR", "APROXIMAR", "ATAQUE_RAPIDO", "MATAR", "ESMAGAR", "POKE"]
                self.acao_atual = self.rng.choice(acoes)
        
        if "ADAPTAVEL" in self.tracos:
            if self.frustracao > 0.5:
                acoes = ["FLANQUEAR", "MATAR", "ESMAGAR", "PRESSIONAR"]
                self.acao_atual = self.rng.choice(acoes)
                self.frustracao *= 0.5
        
        if "FLANQUEADOR" in self.tracos:
            if self.acao_atual in ["APROXIMAR", "COMBATE", "CIRCULAR", "BLOQUEAR"]:
                if self.rng.random() < 0.5:
                    self.acao_atual = "FLANQUEAR"
        
        if "VELOZ" in self.tracos:
            if self.acao_atual in ["BLOQUEAR", "COMBATE"]:
                if self.rng.random() < 0.6:
                    self.acao_atual = self.rng.choice(["FLANQUEAR", "ATAQUE_RAPIDO"])
        
        if "ESTATICO" in self.tracos:
            if self.acao_atual in ["CIRCULAR", "FLANQUEAR", "RECUAR"]:
                if self.rng.random() < 0.4:
                    self.acao_atual = self.rng.choice(["COMBATE", "MATAR"])
        
        if "SELVAGEM" in self.tracos:
            if self.rng.random() < 0.25:
                self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR", "ATAQUE_RAPIDO"])
        
        if "TEIMOSO" in self.tracos:
            if self.acao_atual not in ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO"]:
                if self.rng.random() < 0.3:
                    self.acao_atual = "MATAR"
        elif "FRIO" not in self.tracos:
            if self.raiva > 0.6:
                if self.acao_atual in ["RECUAR", "BLOQUEAR", "CIRCULAR", "FUGIR"]:
                    if self.rng.random() < 0.5:
                        self.acao_atual = self.rng.choice(["MATAR", "ESMAGAR"])

    def _aplicar_modificadores_humor(self):
        """Aplica modificadores do humor atual"""
        humor_data = HUMORES.get(self.humor, HUMORES["CALMO"])
        
        if humor_data["mod_agressividade"] > 0.15:
            if self.acao_atual in ["RECUAR", "BLOQUEAR", "CIRCULAR", "FUGIR"]:
                if self.rng.random() < 0.45:
                    self.acao_atual = self.rng.choice(["MATAR", "APROXIMAR", "PRESSIONAR"])
        elif humor_data["mod_agressividade"] < -0.25:
            if self.acao_atual in ["MATAR", "ESMAGAR"]:
                if self.rng.random() < 0.2:
                    self.acao_atual = "COMBATE"

    def _aplicar_modificadores_filosofia(self):
        """Aplica modificadores da filosofia"""
        filosofia_data = FILOSOFIAS.get(self.filosofia, FILOSOFIAS["EQUILIBRIO"])
        preferencias = filosofia_data["preferencia_acao"]
        
        if self.rng.random() < 0.2:
            self.acao_atual = self.rng.choice(preferencias)

    def _calcular_timer_decisao(self):
        """Calcula timer para próxima decisão.

        Onda 5B: escada reescalada ~x1,67 (base 0,3->0,5). A 0,3 com humores
        rápidos o tick caía a 60-140ms — intenção ilegível por construção.
        """
        base = 0.5

        if "ERRATICO" in self.tracos or "CAOTICO" in self.tracos:
            base = 0.25
        if "PACIENTE" in self.tracos:
            base = 0.75
        if "METODICO" in self.tracos:
            base = 0.65
        if self.modo_berserk:
            base = 0.22
        if self.humor == "ENTEDIADO":
            base = 0.8
        if self.humor == "ANIMADO":
            base = 0.38
        if self.humor == "FURIOSO":
            base = 0.3
        if self.humor == "DESESPERADO":
            base = 0.32

        self.timer_decisao = self.rng.uniform(base * 0.5, base * 1.2)

    # =========================================================================
    # CALLBACKS v8.0
    # =========================================================================
    
    def on_hit_dado(self):
        """Quando acerta um golpe - integrado com sistema de combos"""
        # Contadores e emoções no motor único (5C): acertar alivia
        # frustração (-0,25) e tédio (-0,3) — a seca ofensiva é que os cria.
        self._motor_emocional().on_hit_dado()

        # Sistema de combo — Onda 8H: a janela de followup agora tem base
        # MECÂNICA: cobre o hitstun real que o golpe causou no alvo (o
        # tempo em que ele não responde) mais o tempo de emendar.
        combo = self.combo_state
        combo["em_combo"] = True
        combo["hits_combo"] += 1
        combo["ultimo_tipo_ataque"] = self.acao_atual
        combo["pode_followup"] = True
        inimigo_atual = getattr(self.parent, "_inimigo_atual", None)
        stun_alvo = min(0.4, getattr(inimigo_atual, "stun_timer", 0.0) or 0.0)
        combo["timer_followup"] = 0.5 + stun_alvo

        # Momentum positivo (empurrao de evento, calibrado com a meia-vida
        # de 4s para nao cravar o medidor em sequencias normais)
        self.momentum = min(1.0, self.momentum + 0.06)
        self.burst_counter += 1

        if "SEDE_SANGUE" in self.quirks:
            self.adrenalina = min(1.0, self.adrenalina + 0.2)

        # Combo master continua pressionando
        if "COMBO_MASTER" in self.tracos or "MESTRE_COMBO" in self.quirks:
            combo["timer_followup"] = 0.7 + stun_alvo
    
    def on_hit_recebido(self, dano):
        """Quando recebe dano"""
        # Momentum negativo
        self.momentum = max(-1.0, self.momentum - 0.05)
        
        # Quebra combo
        self.combo_state["em_combo"] = False
        self.combo_state["hits_combo"] = 0
    
    def on_skill_usada(self, skill_nome, sucesso):
        """Quando usa skill"""
        if not sucesso:
            self.frustracao = min(1.0, self.frustracao + 0.1)
        else:
            self.burst_counter += 2  # Skills contam mais pro burst
    
    def on_inimigo_fugiu(self):
        """Quando inimigo foge"""
        # Ganha momentum
        self.momentum = min(1.0, self.momentum + 0.1)
        
        if "PERSEGUIDOR" in self.tracos:
            self.raiva = min(1.0, self.raiva + 0.2)
            self.acao_atual = "APROXIMAR"
        if "PREDADOR" in self.tracos:
            self.excitacao = min(1.0, self.excitacao + 0.2)
        
        # Marca como oportunidade
        self.janela_ataque["aberta"] = True
        self.janela_ataque["tipo"] = "fugindo"
        self.janela_ataque["qualidade"] = 0.6
        self.janela_ataque["duracao"] = 1.0
    
    def on_esquiva_sucesso(self):
        """Quando desvia com sucesso de um ataque"""
        self.confianca = min(1.0, self.confianca + 0.1)
        self.excitacao = min(1.0, self.excitacao + 0.15)
        
        # Abre janela de contra-ataque
        self.janela_ataque["aberta"] = True
        self.janela_ataque["tipo"] = "pos_esquiva"
        self.janela_ataque["qualidade"] = 0.85
        self.janela_ataque["duracao"] = 0.5
        
        if "CONTRA_ATAQUE_PERFEITO" in self.quirks:
            self.reacao_pendente = "CONTRA_MATAR"

    def on_parry_sucesso(self):
        """Onda 8B: parry conectou — o atacante está cambaleando.

        A melhor janela de punição do motor: qualidade acima da esquiva
        (o oponente está em stagger de 0.4s, não só recuperando o swing).
        """
        self.confianca = min(1.0, self.confianca + 0.15)
        self.excitacao = min(1.0, self.excitacao + 0.2)

        self.janela_ataque["aberta"] = True
        self.janela_ataque["tipo"] = "pos_parry"
        self.janela_ataque["qualidade"] = 0.95
        self.janela_ataque["duracao"] = 0.9
        # Onda 8F: tell do parry — o renderer mostra a leitura do momento.
        self.tell_atual = {"tipo": "parry",
                           "ate": getattr(self, "tempo_combate", 0.0) + 0.5}

        if "CONTRA_ATAQUE_PERFEITO" in self.quirks:
            self.reacao_pendente = "CONTRA_MATAR"
        else:
            self.reacao_pendente = "CONTRA_ATAQUE"

    # =========================================================================
    # NOVOS SISTEMAS v11.0 - RITMOS E INSTINTOS
    # =========================================================================
    
    def _atualizar_ritmo(self, dt):
        """Atualiza o sistema de ritmo de batalha"""
        if not self.ritmo or self.ritmo not in RITMOS:
            return
        
        ritmo_data = RITMOS[self.ritmo]
        fases = ritmo_data["fases"]
        duracao = ritmo_data["duracao_fase"]
        
        # Atualiza timer
        self.ritmo_timer += dt
        
        # Verifica mudança de fase
        if self.ritmo_timer >= duracao:
            self.ritmo_timer %= duracao
            self.ritmo_fase_atual = (self.ritmo_fase_atual + 1) % len(fases)
            self._ritmo_aleatorio_atual = None
        
        # Aplica modificadores da fase atual
        fase_atual = fases[self.ritmo_fase_atual]
        
        # Fase ALEATORIO do ritmo caótico
        if fase_atual == "ALEATORIO":
            if self._ritmo_aleatorio_atual is None:
                self._ritmo_aleatorio_atual = self.rng.choice(list(RITMO_MODIFICADORES.keys()))
            fase_atual = self._ritmo_aleatorio_atual
        
        if fase_atual in RITMO_MODIFICADORES:
            mods = RITMO_MODIFICADORES[fase_atual]
            self.ritmo_modificadores = mods.copy()
        else:
            self.ritmo_modificadores = {"agressividade": 0, "defesa": 0, "mobilidade": 0}
    
    def _processar_instintos(self, dt, distancia, inimigo):
        """Reações automáticas (Onda 5D: sinais reais + prioridade + cd).

        Antes: 8/15 triggers referenciavam sinais que não existiam (o
        catálogo prometia reflexos mortos) e as condições de nível sem
        cooldown faziam RECUAR ser 98,7% dos disparos — o primeiro da
        lista vencia todo frame. Agora: candidatos são coletados, o de
        prioridade mais forte rola a chance, e quem dispara paga cooldown.
        """
        if not self.instintos:
            return False

        p = self.parent
        hp_pct = p.vida / p.vida_max if p.vida_max > 0 else 1.0
        inimigo_hp_pct = (
            inimigo.vida / inimigo.vida_max if inimigo.vida_max > 0 else 1.0
        )

        candidatos = []
        for nome in self.instintos:
            dados = INSTINTOS.get(nome)
            if not dados:
                continue
            if self.tempo_combate < self.cd_instintos.get(nome, 0.0):
                continue
            if self._avaliar_trigger_instinto(
                dados["trigger"], distancia, inimigo, hp_pct, inimigo_hp_pct
            ):
                candidatos.append((dados.get("prioridade", 2), nome, dados))

        if not candidatos:
            return False

        candidatos.sort(key=lambda item: item[0])
        prioridade, nome, dados = candidatos[0]
        chance = dados["chance"]
        if prioridade == 1:
            # Adrenalina: o medo AFIA os reflexos de sobrevivência
            # (esquiva de projétil, reação a golpe iminente) — quem está
            # assustado desvia MAIS, não menos. Só prioridade 1: punição
            # e postura não ganham nada com pânico.
            chance = min(0.98, chance * (1.0 + self.medo))
        if not self._chance_temporal(chance, dt):
            return False

        self.cd_instintos[nome] = self.tempo_combate + dados.get("cooldown", 3.0)
        return self._executar_instinto(dados["acao"], distancia, inimigo)

    def _avaliar_trigger_instinto(
        self, trigger, distancia, inimigo, hp_pct, inimigo_hp_pct
    ):
        """Um trigger, um sinal REAL do runtime (auditado por AST nos dois
        sentidos pela auditoria_personalidades)."""
        p = self.parent

        if trigger == "hp_critico":
            return hp_pct < 0.2
        if trigger == "hp_baixo":
            return hp_pct < 0.4
        if trigger == "oponente_fraco":
            return inimigo_hp_pct < 0.3
        if trigger == "vantagem_hp":
            return hp_pct > inimigo_hp_pct + 0.2
        if trigger == "dano_alto":
            return (
                self.tempo_desde_dano < 0.3
                and self.ultimo_dano_recebido > p.vida_max * 0.15
            )
        if trigger == "pos_combo":
            return 0.3 < self.tempo_desde_dano < 0.5
        if trigger == "perdendo_trocas":
            return self.hits_recebidos_recente > self.hits_dados_recente + 2
        if trigger == "sendo_comboado":
            # Onda 8H: o combo sofrido agora é ESTADO MECÂNICO do motor
            # (combo_contra), não inferência por contadores de hits.
            if (
                getattr(p, "combo_contra", 0) >= 2
                and getattr(p, "combo_contra_timer", 0.0) > 0.0
            ):
                return True
            return self.hits_recebidos_recente >= 3 and self.tempo_desde_dano < 0.8
        if trigger == "bloqueio_sucesso":
            return self.ultimo_bloqueio < 0.4
        if trigger == "janela_punicao":
            # Era "oponente_whiff" comparado com tipo "whiff", que não
            # existe no vocabulário de janelas do runtime.
            return bool(self.janela_ataque.get("aberta")) and self.janela_ataque.get(
                "tipo"
            ) in ("pos_ataque", "recuperando", "pos_esquiva", "pos_parry")
        if trigger == "oponente_recuando":
            # Onda 8A: recuo OBSERVADO (velocidade se afastando), não o
            # acao_atual telepático do brain adversário.
            return self._observar(inimigo).intencao == "recuando"
        if trigger == "oponente_previsivel":
            return self.leitura_oponente.get("previsibilidade", 0.0) > 0.7
        if trigger == "ataque_iminente_perto":
            return (
                bool(self.leitura_oponente.get("ataque_iminente"))
                and distancia < 3.5
            )
        if trigger == "projetil_vindo":
            return bool(self._detectar_projetil_vindo(inimigo))
        if trigger == "ataque_traseiro":
            # Onda 8A: o teste geométrico puro era inalcançável — o motor
            # gira angulo_olhar para o inimigo a 10-20 rad/s todo frame,
            # então nunca há "costas viradas" em condição normal. O
            # sentido honesto de "golpe que não vi chegar": atacado
            # enquanto atordoado/canalizando (mira travada), ou no caso
            # geométrico raro que sobrou (transições, CC).
            if not getattr(inimigo, "atacando", False):
                return False
            if getattr(p, "stun_timer", 0.0) > 0 or getattr(p, "canalizando", False):
                return True
            ang_para_inimigo = math.atan2(
                inimigo.pos[1] - p.pos[1], inimigo.pos[0] - p.pos[0]
            )
            # Onda 8: angulo_olhar é em GRAUS — a versão antiga comparava
            # em radianos e o teste geométrico era ruído.
            delta = abs(
                (ang_para_inimigo - math.radians(p.angulo_olhar) + math.pi)
                % (2 * math.pi)
                - math.pi
            )
            return delta > 2.2
        return False

    def _executar_instinto(self, acao, distancia, inimigo):
        """Executa uma ação instintiva com verbos REAIS do motor.

        Onda 5D: as versões antigas escreviam ``p.movimento_x`` (que o
        motor nunca leu) e chamavam métodos inexistentes — o instinto
        "disparava" e nada acontecia na tela. O poder do instinto é o
        commit P1 do escritor único: a ação interrompe qualquer hold e
        gruda. (Onda 8B criou ``p.iniciar_dash`` de verdade; o desvio
        físico deliberado vive no gate de desvio inteligente da 8C.)
        """
        if acao == "panic_dash":
            self.acao_atual = "FUGIR"
            return True
        if acao in ("dodge_back", "dodge_projetil", "combo_break"):
            self.acao_atual = "DESVIO"
            return True
        if acao in ("guarda_reflexa", "auto_block"):
            self.acao_atual = "BLOQUEAR"
            return True
        if acao == "instant_counter":
            self.acao_atual = "CONTRA_ATAQUE"
            return True
        if acao == "auto_chase":
            self.acao_atual = "PRESSIONAR"
            return True
        if acao == "punish_attack":
            self.acao_atual = "MATAR"
            return True
        if acao == "execute_mode":
            self.acao_atual = "ESMAGAR"
            self.agressividade_base = min(1.0, self.agressividade_base + 0.2)
            return True
        if acao == "tactical_retreat":
            self.acao_atual = "RECUAR"
            return True
        if acao == "defensive_mode":
            self.acao_atual = "RECUAR"
            self.agressividade_base = max(0.1, self.agressividade_base - 0.2)
            return True
        if acao == "rage_trigger":
            self.raiva = min(1.0, self.raiva + 0.5)
            self.medo = max(0.0, self.medo - 0.3)
            self.agressividade_base = min(1.0, self.agressividade_base + 0.3)
            return False  # estado, não consome o frame
        if acao == "pressure_increase":
            self.agressividade_base = min(1.0, self.agressividade_base + 0.15)
            self.pressao_aplicada = min(1.0, self.pressao_aplicada + 0.2)
            return False
        if acao == "style_switch":
            alternativos = [
                e
                for e in ("AGGRO", "DEFENSIVE", "MOBILE", "COUNTER")
                if e != self.estilo_luta
            ]
            self.estilo_luta = self.rng.choice(alternativos)
            return False
        return False
