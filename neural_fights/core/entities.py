"""
NEURAL FIGHTS - Entidade Lutador
Classe principal do lutador com sistema de combate.
"""

import math
import random
from dataclasses import dataclass, field
from neural_fights.core.status_runtime import (
    DEBUFF_FAMILY_ORDER,
    STATUS_TIMER_ATTRS,
    StatusTimers,
    efeito_bloqueado_por_imunidade,
    get_duracao_padrao,
    get_status_runtime,
    normalizar_efeito,
)
from neural_fights.utils.config import PPM, GRAVIDADE_Z, ATRITO, ALTURA_PADRAO


@dataclass(frozen=True)
class ImpactResult:
    """Resultado explícito de uma tentativa de impacto no runtime."""

    atingiu: bool
    dano: float = 0.0
    efeito_aplicado: bool = False
    morreu: bool = False
    bloqueado_por: str | None = None


@dataclass
class DamageContext:
    """Ownership carried by one damage chain until a terminal death.

    The same instance is reused when damage is split by Soul Link or emitted by
    a DoT.  That makes terminal-death callbacks idempotent without relying on
    transient HP flags or on the order in which effects are resolved.
    """

    atacante: object | None = None
    fonte: object | None = None
    nome_skill: str | None = None
    metadata: dict = field(default_factory=dict)
    _vitimas_creditadas: set[int] = field(default_factory=set, repr=False)

    @classmethod
    def de_impacto(cls, atacante=None, fonte=None, metadata=None):
        metadata = dict(metadata or {})
        fonte_credito = metadata.get("fonte_dano")
        if fonte_credito is None:
            fonte_credito = fonte
        nome_skill = metadata.get("nome_skill") or getattr(
            fonte_credito,
            "nome",
            None,
        )
        return cls(
            atacante=atacante,
            fonte=fonte_credito,
            nome_skill=nome_skill,
            metadata=metadata,
        )

    def creditar_morte(self, vitima):
        """Return ``True`` exactly once for a victim in this damage chain."""

        chave = id(vitima)
        if chave in self._vitimas_creditadas:
            return False
        self._vitimas_creditadas.add(chave)
        return True


# Familia de debuff -> atributo de timer usado na limpeza. O bloco vive aqui
# porque ``PROVOCADO`` e mecanica de aggro, nao um status do catalogo; as demais
# familias resolvem pelo container em ``status_timers``.
_TIMERS_POR_FAMILIA = {
    "FRACO": "fraco_timer",
    "VULNERAVEL": "vulneravel_timer",
    "MALDITO": "maldito_timer",
    "CORROENDO": "corroendo_timer",
    "EXPOSTO": "exposto_timer",
    "ENRAIZADO": "enraizado_timer",
    "SILENCIADO": "silenciado_timer",
    "EXAUSTO": "exausto_timer",
    "CEGO": "cego_timer",
    "MEDO": "medo_timer",
    "CHARME": "charme_timer",
    "POSSESSO": "possesso_timer",
    "LINK_ALMA": "link_alma_timer",
    "BOMBA_RELOGIO": "bomba_relogio_timer",
    "PROVOCADO": "provocacao_timer",
}


# Debuffs que so alteram numeros: expiram sem efeito colateral no runtime.
_DEBUFFS_NUMERICOS = ("FRACO", "VULNERAVEL", "MALDITO", "CORROENDO", "EXPOSTO")


class _StatusTimerAttr:
    """Expoe um status do container como o atributo ``*_timer`` historico."""

    __slots__ = ("status_id",)

    def __init__(self, status_id: str) -> None:
        self.status_id = status_id

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj.status_timers.get(self.status_id)

    def __set__(self, obj, valor):
        obj.status_timers.set(self.status_id, valor)


class Lutador:
    """
    Classe principal do lutador com suporte completo a:
    - Sistema de classes expandido
    - Novos tipos de skills (DASH, BUFF, AREA, BEAM, SUMMON)
    - Efeitos de status (DoT, buffs, debuffs)
    """
    def __init__(self, dados_char, pos_x, pos_y):
        # Importações tardias para evitar circular imports
        from neural_fights.ai import AIBrain
        from neural_fights.core.skills import get_skill_data
        from neural_fights.models import get_class_data
        
        self.dados = dados_char
        self.pos = [pos_x, pos_y]
        self.vel = [0.0, 0.0]
        self.z = 0.0
        self.vel_z = 0.0
        self.pulo_bloqueado_timer = 0.0
        self.raio_fisico = (self.dados.tamanho / 4.0)
        
        # Carrega dados da classe
        self.classe_nome = getattr(self.dados, 'classe', "Guerreiro (Força Bruta)")
        self.class_data = get_class_data(self.classe_nome)
        
        # Status calculados com modificadores de classe
        self.vida_max = self._calcular_vida_max()
        self.vida = self.vida_max
        self.estamina = 100.0
        self.estamina_max = 100.0
        self.mana_max = self._calcular_mana_max()
        self.mana = self.mana_max
        self.velocidade_movimento_base = self._calcular_velocidade_movimento()
        self.mod_velocidade_transformacao = 1.0
        self.resistencia = float(getattr(self.dados, "resistencia", 0.0))
        self.intangivel = False
        self.transformacao_ativa = None
        
        # Regeneração baseada na classe
        get_regen_mana = getattr(self.dados, "get_regen_mana", None)
        self.regen_mana_base = (
            float(get_regen_mana())
            if callable(get_regen_mana)
            else self.class_data.get("regen_mana", 3.0)
        )
        self.regen_mana_base_normal = self.regen_mana_base
        
        # Modificadores de classe
        self.mod_dano = self.class_data.get("mod_forca", 1.0)
        # Mantido como metadado público legado. O modificador de classe já
        # está incorporado em ``velocidade_movimento_base`` e não é reaplicado.
        self.mod_velocidade = self.class_data.get("mod_velocidade", 1.0)
        self.mod_defesa = 1.0
        
        # Cor de aura da classe
        self.cor_aura = self.class_data.get("cor_aura", (200, 200, 200))
        
        # === SISTEMA DE SKILLS EXPANDIDO ===
        self.skills_arma = []
        self.skills_classe = []
        self.skill_atual_idx = 0
        self.cd_skills = {}
        
        # Carrega skills da arma
        arma = getattr(self.dados, 'arma_obj', None)
        if arma:
            habilidades = getattr(arma, 'habilidades', [])
            if habilidades:
                for hab in habilidades:
                    if isinstance(hab, dict):
                        nome_hab = hab.get("nome", "Nenhuma")
                        custo_hab = hab.get("custo", 0)
                    else:
                        nome_hab = str(hab)
                        custo_hab = getattr(arma, 'custo_mana', 0)
                    
                    skill_data = get_skill_data(nome_hab)
                    if skill_data["tipo"] != "NADA":
                        self.skills_arma.append({
                            "nome": nome_hab,
                            "custo": custo_hab,
                            "data": skill_data
                        })
                        self.cd_skills[nome_hab] = 0.0
            else:
                nome_raw = getattr(arma, 'habilidade', "Nenhuma")
                skill_data = get_skill_data(nome_raw)
                if skill_data["tipo"] != "NADA":
                    custo = getattr(arma, 'custo_mana', skill_data["custo"])
                    self.skills_arma.append({
                        "nome": nome_raw,
                        "custo": custo,
                        "data": skill_data
                    })
                    self.cd_skills[nome_raw] = 0.0
            
            # Carrega dados de raridade da arma
            self.arma_raridade = getattr(arma, 'raridade', 'Comum')
            self.arma_critico = getattr(arma, 'critico', 0.0)
            self.arma_vel_ataque = getattr(arma, 'velocidade_ataque', 1.0)
            self.arma_encantamentos = getattr(arma, 'encantamentos', [])
            self.arma_passiva = getattr(arma, 'passiva', None)
            self.arma_tipo = arma.tipo
        else:
            self.arma_raridade = 'Comum'
            self.arma_critico = 0.0
            self.arma_vel_ataque = 1.0
            self.arma_encantamentos = []
            self.arma_passiva = None
            self.arma_tipo = None
        
        # Carrega skills de afinidade da classe
        for skill_nome in self.class_data.get("skills_afinidade", []):
            skill_data = get_skill_data(skill_nome)
            if skill_data["tipo"] != "NADA":
                self.skills_classe.append({
                    "nome": skill_nome,
                    "custo": skill_data.get("custo", 15),
                    "data": skill_data
                })
                self.cd_skills[skill_nome] = 0.0
        
        # Compatibilidade com código antigo
        self.skill_arma_nome = self.skills_arma[0]["nome"] if self.skills_arma else "Nenhuma"
        self.custo_skill_arma = self.skills_arma[0]["custo"] if self.skills_arma else 0
        self.cd_skill_arma = 0.0
        
        # Buffers para objetos criados
        self.buffer_projeteis = []
        self.buffer_areas = []
        self.buffer_beams = []
        self.buffer_orbes = []
        self.buffer_portais = []
        
        # Efeitos ativos
        self.buffs_ativos = []
        self.dots_ativos = []

        # Estado de combate
        self.morto = False
        # Todo status do catálogo vive neste container; os atributos ``*_timer``
        # continuam disponíveis como visão sobre ele.
        self.status_timers = StatusTimers()
        # Colaboradores da partida, injetados pelo dono do combate. Enquanto
        # ninguém injeta, as properties abaixo caem no singleton histórico.
        self._audio = None
        self._arena = None
        self._choreographer = None
        self.invencivel_timer = 0.0
        # Invulnerabilidade concedida por uma skill é diferente do curto
        # intervalo anti-hit gerado por impactos. Fontes multi-hit podem
        # ignorar apenas o segundo, nunca atravessar a primeira.
        self.invulnerabilidade_skill_timer = 0.0
        self.flash_timer = 0.0
        self.flash_cor = (255, 255, 255)  # Cor do flash de dano
        self.slow_fator = 1.0
        self.congelado = False
        self.tempo_parado = False
        self.dormindo = False
        self.marcado = False
        self.marcado_multiplicador = get_status_runtime("MARCADO").get(
            "mod_proximo_dano_recebido",
            1.5,
        )
        self.cura_bloqueada_timer = 0.0
        self.imune_debuffs_timer = 0.0
        self.charme_origem = None
        self.possesso_origem = None
        self.bomba_relogio_dano = 0.0
        self.bomba_relogio_raio = 0.0
        self.bomba_relogio_origem = None
        self.link_alma_alvo = None
        self.link_alma_percentual = 0.0
        self.provocacao_timer = 0.0
        self.provocacao_origem = None
        self._fontes_impacto_recentes = {}
        self.ultimo_dano_recebido = 0.0
        self.ultimo_resultado_impacto = ImpactResult(False, bloqueado_por="inicial")
        self._slow_fator_antes_enraizado = 1.0
        self._slow_fator_antes_congelado = 1.0
        self._slow_fator_antes_tempo_parado = 1.0
        self.modo_adrenalina = False
        
        # === SISTEMA DE CHANNELING v8.0 (Para Magos) ===
        self.canalizando = False
        self.skill_canalizando = None
        self.tempo_canalizacao = 0.0
        self.channel_ativo = None
        self.usando_skill = False  # Flag para skills em geral
        
        # Animação e visual
        self.angulo_olhar = 0.0
        self.angulo_arma_visual = 0.0
        self.cooldown_ataque = 0.0
        self.timer_animacao = 0.0
        self.atacando = False
        self.modo_ataque_aereo = False
        
        # === SISTEMA DE PREVENÇÃO DE MULTI-HIT v10.1 ===
        # Cada ataque recebe um ID único para evitar múltiplos hits no mesmo swing
        self.ataque_id = 0  # Incrementa a cada novo ataque
        self.alvos_atingidos_neste_ataque = set()  # IDs dos alvos já atingidos neste ataque
        
        # === SISTEMA DE ANIMAÇÃO DE ARMAS v2.0 ===
        self.weapon_anim_scale = 1.0      # Escala da arma (squash/stretch)
        self.weapon_anim_shake = (0, 0)   # Offset de shake no impacto
        self.weapon_trail_positions = []  # Posições do trail da arma
        self.arma_droppada_pos = None
        self.arma_droppada_ang = 0
        self.fator_escala = self.dados.tamanho / ALTURA_PADRAO
        self.alcance_ideal = 1.5
        
        # Efeitos visuais temporários
        self.dash_trail = []
        self.aura_pulso = 0.0
        
        # Sistema de dash evasivo v7.0
        self.dash_timer = 0.0
        self._transicao_sombria = None
        self.pos_historico = []
        # RNG injetavel para efeitos aleatorios do runtime. Por padrao ele
        # continua usando o gerador global semeado pelo Simulador.
        self.rng_runtime = random
        self._tempo_runtime = 0.0
        self._historico_estado = []
        self._registrar_estado_historico()

        # IA
        self.brain = AIBrain(self)
        self._inimigo_atual = None

    def configurar_rng_runtime(self, rng):
        """Injeta o fluxo pseudoaleatorio exclusivo deste lutador e de sua IA."""

        self.rng_runtime = rng
        brain = getattr(self, "brain", None)
        if brain is not None:
            brain.rng = rng
            strategy = getattr(brain, "skill_strategy", None)
            if strategy is not None:
                strategy.rng = rng

    def _calcular_vida_max(self):
        """Usa o contrato canônico do modelo, preservando fixtures legadas."""
        calcular = getattr(self.dados, "get_vida_max", None)
        if callable(calcular):
            try:
                valor = float(calcular())
            except (TypeError, ValueError):
                valor = 0.0
            if valor > 0.0:
                return valor
        base = 80.0 + (self.dados.resistencia * 5)  # Vida reduzida para lutas mais rápidas
        return base * self.class_data.get("mod_vida", 1.0)
    
    def _calcular_mana_max(self):
        """Usa o contrato canônico do modelo, preservando fixtures legadas."""
        calcular = getattr(self.dados, "get_mana_max", None)
        if callable(calcular):
            try:
                valor = float(calcular())
            except (TypeError, ValueError):
                valor = 0.0
            if valor > 0.0:
                return valor
        base = 50.0 + (getattr(self.dados, 'mana', 0) * 10.0)
        return base * self.class_data.get("mod_mana", 1.0)

    def _calcular_velocidade_movimento(self):
        """Retorna velocidade planar já consolidada pelo modelo de domínio."""
        calcular = getattr(self.dados, "get_velocidade_movimento", None)
        if callable(calcular):
            try:
                valor = float(calcular())
            except (TypeError, ValueError):
                valor = -1.0
            if valor >= 0.0:
                return valor
        return max(0.0, float(getattr(self.dados, "velocidade", 5.0)))

    def get_velocidade_movimento(self):
        """Velocidade-alvo atual, incluindo apenas modificadores temporários."""
        velocidade = self.velocidade_movimento_base * self.mod_velocidade_transformacao
        for buff in self._buffs_validos():
            velocidade *= max(0.0, getattr(buff, "buff_velocidade", 1.0))
        return max(0.0, velocidade)

    def _get_aceleracao_movimento(self, fator=1.0):
        """Converte velocidade-alvo em aceleração compatível com o atrito."""
        return self.get_velocidade_movimento() * ATRITO * max(0.0, fator)

    def trocar_skill(self):
        """Troca para a próxima skill disponível"""
        if len(self.skills_arma) <= 1:
            return
        
        self.skill_atual_idx = (self.skill_atual_idx + 1) % len(self.skills_arma)
        skill = self.skills_arma[self.skill_atual_idx]
        self.skill_arma_nome = skill["nome"]
        self.custo_skill_arma = skill["custo"]
    
    def get_skill_atual(self):
        """Retorna dados da skill atualmente selecionada"""
        if not self.skills_arma:
            return None
        return self.skills_arma[self.skill_atual_idx]

    def _buffs_validos(self):
        """Itera apenas buffs ainda ativos, inclusive entre dois updates."""
        return (buff for buff in self.buffs_ativos if getattr(buff, "ativo", True))

    def _consumir_buffs_de_proximo_dano(self):
        """Consome apenas gatilhos one-shot depois de dano realmente aceito."""

        consumidos = 0
        for buff in tuple(self._buffs_validos()):
            if not getattr(buff, "consome_ao_causar_dano", False):
                continue
            buff.ativo = False
            consumidos += 1
        if consumidos:
            self.buffs_ativos = [
                buff
                for buff in self.buffs_ativos
                if getattr(buff, "ativo", True)
            ]
        return consumidos

    def _registrar_estado_historico(self):
        """Guarda o estado reversivel sem incluir recursos ou cooldowns."""
        snapshot = {
            "tempo": float(self._tempo_runtime),
            "vida": float(self.vida),
            "pos": (float(self.pos[0]), float(self.pos[1])),
            "z": float(self.z),
        }
        if self._historico_estado and self._historico_estado[-1]["tempo"] == snapshot["tempo"]:
            self._historico_estado[-1] = snapshot
        else:
            self._historico_estado.append(snapshot)

        limite = self._tempo_runtime - 6.0
        while (
            len(self._historico_estado) > 1
            and self._historico_estado[1]["tempo"] <= limite
        ):
            self._historico_estado.pop(0)

    def _estado_historico_para(self, segundos):
        segundos = max(0.0, float(segundos))
        if self.morto or not self._historico_estado:
            return None
        alvo_tempo = self._tempo_runtime - segundos
        if self._historico_estado[0]["tempo"] > alvo_tempo + 1e-9:
            return None
        elegiveis = [
            estado
            for estado in self._historico_estado
            if estado["tempo"] <= alvo_tempo + 1e-9
        ]
        return elegiveis[-1] if elegiveis else None

    def pode_reverter_estado(self, segundos):
        """Reverter so pode ser pago quando existe um snapshot completo."""
        return self._estado_historico_para(segundos) is not None

    def reverter_estado(self, segundos):
        """Restaura HP/posicao historicos, sem ressuscitar ou resetar recursos."""
        estado = self._estado_historico_para(segundos)
        if estado is None:
            return False
        x, y = estado["pos"]
        vida = estado["vida"]
        z = estado["z"]
        if not all(math.isfinite(valor) for valor in (x, y, vida, z)):
            return False
        self.pos[0], self.pos[1] = x, y
        self.z = max(0.0, z)
        self.vida = min(self.vida_max, max(1.0, vida))
        self.vel[0] = 0.0
        self.vel[1] = 0.0
        self.vel_z = 0.0
        return True

    def esta_voando(self):
        return any(bool(getattr(buff, "voo", False)) for buff in self._buffs_validos())

    def esta_imune_ground(self):
        return any(
            bool(getattr(buff, "imune_ground", False))
            for buff in self._buffs_validos()
        )

    def impedir_pulo(self, duracao):
        """Bloqueia novas impulsões verticais enquanto o campo estiver ativo."""

        duracao = max(0.0, float(duracao))
        self.pulo_bloqueado_timer = max(self.pulo_bloqueado_timer, duracao)
        self.vel_z = min(self.vel_z, 0.0)

    def pode_pular(self):
        return self.z == 0 and self.pulo_bloqueado_timer <= 0.0

    def _altura_voo_ativa(self):
        alturas = [
            max(0.1, float(getattr(buff, "altura_voo", 1.5)))
            for buff in self._buffs_validos()
            if getattr(buff, "voo", False)
        ]
        return max(alturas, default=0.0)

    def tentar_refletir_projetil(self, projetil):
        """Reflete uma fonte fisica antes do impacto enquanto o buff durar."""
        if not any(
            bool(getattr(buff, "reflete_projeteis", False))
            for buff in self._buffs_validos()
        ):
            return False
        from neural_fights.core.combat import refletir_projetil

        return refletir_projetil(projetil, self)

    def _consumir_reflexao_skill(self):
        for buff in self._buffs_validos():
            consumir = getattr(buff, "consumir_reflexao_skill", None)
            if callable(consumir) and consumir():
                return True
        return False

    def _consumir_esquiva_prevista(self):
        for buff in self._buffs_validos():
            consumir = getattr(buff, "consumir_esquiva_prevista", None)
            if callable(consumir) and consumir():
                return True
        return False

    def ve_ataques_hostis(self):
        """Indica percepção antecipada enquanto Previsão estiver ativa."""

        return any(
            bool(getattr(buff, "ve_ataques", False))
            for buff in self._buffs_validos()
        )

    def _roubar_buff_do_alvo(self, alvo):
        """Transfere um buff elegivel preservando seu tempo restante."""
        candidatos = [
            buff
            for buff in getattr(alvo, "buffs_ativos", ())
            if (
                getattr(buff, "ativo", True)
                and getattr(buff, "persistente", True)
                and getattr(buff, "roubavel", True)
            )
        ]
        if not candidatos:
            return None
        escolher = getattr(self.rng_runtime, "choice", random.choice)
        original = escolher(candidatos)
        clonar = getattr(original, "clonar_para", None)
        if not callable(clonar):
            return None
        clone = clonar(self)
        original.ativo = False
        original.vida = 0.0
        if original in alvo.buffs_ativos:
            alvo.buffs_ativos.remove(original)
        self.buffs_ativos.append(clone)
        return clone

    def _get_modificador_cooldown_buff(self):
        modificador = 1.0
        for buff in self._buffs_validos():
            modificador *= max(0.0, getattr(buff, "mod_cooldown", 1.0))
        return modificador

    def _get_modificador_mana_custo_buff(self):
        modificador = 1.0
        for buff in self._buffs_validos():
            modificador *= max(0.0, getattr(buff, "mod_mana_custo", 1.0))
        return modificador

    def _get_modificador_velocidade_ataque_buff(self):
        modificador = 1.0
        for buff in self._buffs_validos():
            modificador *= max(0.01, getattr(buff, "buff_velocidade_ataque", 1.0))
        return modificador

    def esta_imune_a_debuffs(self):
        return self.imune_debuffs_timer > 0.0

    def _tipos_dot_ativos(self):
        return {
            normalizar_efeito(dot.tipo)
            for dot in self.dots_ativos
            if getattr(dot, "ativo", True) and getattr(dot, "vida", 0.0) > 0.0
        }

    def _get_modificador_cura_recebida(self):
        """Usa o debuff mais forte uma vez e o melhor bônus de cura ativo."""
        tipos_dot = self._tipos_dot_ativos()
        modificadores_debuff = [1.0]

        bloqueio_legado = self.cura_bloqueada_timer
        if bloqueio_legado > 0.0:
            modificadores_debuff.append(0.0)

        for efeito in ("ENVENENADO", "MALDITO", "NECROSE"):
            ativo = efeito in tipos_dot
            if efeito == "MALDITO":
                ativo = ativo or self.maldito_timer > 0.0
            if efeito == "NECROSE":
                ativo = ativo or bloqueio_legado > 0.0
            if ativo:
                modificadores_debuff.append(
                    get_status_runtime(efeito).get("mod_cura_recebida", 1.0)
                )

        bonus_buff = 1.0
        for buff in self._buffs_validos():
            bonus_buff = max(
                bonus_buff,
                max(0.0, getattr(buff, "mod_cura_recebida", 1.0)),
            )
        return min(modificadores_debuff) * bonus_buff

    def receber_cura(self, quantidade):
        """Aplica cura pelo ponto único do runtime e retorna a cura real."""
        if self.morto or quantidade <= 0.0:
            return 0.0

        cura_modificada = quantidade * self._get_modificador_cura_recebida()
        if cura_modificada <= 0.0:
            return 0.0

        vida_antes = self.vida
        self.vida = min(self.vida_max, self.vida + cura_modificada)
        return max(0.0, self.vida - vida_antes)

    def curar(self, quantidade):
        """Alias semântico para integrações que usam o verbo curto."""
        return self.receber_cura(quantidade)

    @staticmethod
    def _skill_eh_passiva_de_morte(data):
        """Death-triggered skills are runtime passives, never active buffs."""

        if not isinstance(data, dict):
            return False
        if data.get("ativa_ao_morrer"):
            return True
        try:
            return float(data.get("revive_hp_percent", 0.0)) > 0.0
        except (TypeError, ValueError):
            return False

    def _iterar_skills_equipadas(self):
        """Yield equipped skill records without duplicating the same entry."""

        vistos = set()
        for origem, atributo in (
            ("arma", "skills_arma"),
            ("classe", "skills_classe"),
        ):
            for info in getattr(self, atributo, ()):
                if not isinstance(info, dict):
                    continue
                nome = info.get("nome")
                data = info.get("data")
                if not nome or not isinstance(data, dict):
                    continue
                chave = (origem, nome)
                if chave in vistos:
                    continue
                vistos.add(chave)
                yield origem, info, data

    def _recursos_passiva_morte(self, info, data):
        """Calculate mana cost while preserving the canonical death cooldown."""

        custo = max(0.0, float(info.get("custo", data.get("custo", 0.0))))
        if "Mago" in self.classe_nome:
            custo *= 0.8
        custo *= self._get_modificador_mana_custo_buff()
        cooldown = max(0.0, float(data.get("cooldown", 0.0)))
        return custo, cooldown

    def _tentar_passiva_de_morte(self):
        """Resolve Last Breath first, then self Resurrection as a fallback."""

        prioridades = (
            ("ativa_ao_morrer", "cura_percent"),
            ("revive_hp_percent", "revive_hp_percent"),
        )
        skills = tuple(self._iterar_skills_equipadas())
        for campo_ativacao, campo_vida in prioridades:
            for origem, info, data in skills:
                if not data.get(campo_ativacao):
                    continue
                nome = info["nome"]
                if self.cd_skills.get(nome, 0.0) > 0.0:
                    continue
                try:
                    percentual_vida = min(
                        1.0,
                        max(0.0, float(data.get(campo_vida, 0.0))),
                    )
                    custo, cooldown = self._recursos_passiva_morte(info, data)
                except (TypeError, ValueError):
                    continue
                if percentual_vida <= 0.0 or self.mana + 1e-9 < custo:
                    continue

                self.mana = max(0.0, self.mana - custo)
                self.cd_skills[nome] = cooldown
                if origem == "arma" and nome == self.skill_arma_nome:
                    self.cd_skill_arma = cooldown
                self.vida = min(self.vida_max, self.vida_max * percentual_vida)
                self.morto = False
                return True
        return False

    def _notificar_morte_causada(self, vitima, contexto_dano):
        """Apply source-owned, terminal-kill rewards exactly once."""

        if contexto_dano is None or contexto_dano.atacante is not self:
            return 0.0
        if contexto_dano.nome_skill != "Colheita de Almas":
            return 0.0

        fonte = contexto_dano.fonte
        if (
            fonte is None
            or getattr(fonte, "dono", None) is not self
            or getattr(fonte, "tipo_fonte", None) != "area_skill"
            or getattr(fonte, "nome", None) != "Colheita de Almas"
        ):
            return 0.0

        from neural_fights.core.skills import get_skill_data

        cura = max(
            0.0,
            float(get_skill_data("Colheita de Almas").get("cura_por_morte", 0.0)),
        )
        return self.receber_cura(cura)

    def _limitar_dano_letal_por_imortalidade(self, dano):
        """Consome a primeira proteção disponível e preserva exatamente 1 HP."""
        dano = max(0.0, dano)
        if self.vida - dano > 0.0:
            return dano
        for buff in self._buffs_validos():
            consumir = getattr(buff, "consumir_imortalidade", None)
            if callable(consumir) and consumir():
                return max(0.0, self.vida - 1.0)
        return dano

    def _familia_debuff_ativa(self, familia, tipos_dot):
        if familia in tipos_dot:
            return True
        if familia == "NECROSE":
            return self.cura_bloqueada_timer > 0.0
        if familia == "CONGELADO":
            return self.congelado_timer > 0.0 or self.congelado
        if familia == "TEMPO_PARADO":
            return self.tempo_parado_timer > 0.0 or self.tempo_parado
        if familia == "SONO":
            return self.sono_timer > 0.0 or self.dormindo
        if familia == "ATORDOADO":
            return (
                self.stun_timer > 0.0
                and not self.congelado
                and not self.tempo_parado
            )
        if familia == "LENTO":
            return (
                self.slow_timer > 0.0
                and self.enraizado_timer <= 0.0
                and not self.congelado
                and not self.tempo_parado
            )
        if familia == "MARCADO":
            return self.marcado_timer > 0.0 or self.marcado
        timer = _TIMERS_POR_FAMILIA.get(familia)
        return bool(timer and getattr(self, timer, 0.0) > 0.0)

    def _recalcular_movimento_apos_limpeza(self):
        if self.tempo_parado_timer > 0.0 or self.enraizado_timer > 0.0:
            self.slow_fator = 0.0
        elif self.congelado_timer > 0.0:
            self.slow_fator = min(self._slow_fator_antes_congelado, 0.3)
        elif self.slow_timer > 0.0:
            candidatos = [
                valor
                for valor in (
                    self.slow_fator,
                    self._slow_fator_antes_enraizado,
                    self._slow_fator_antes_congelado,
                    self._slow_fator_antes_tempo_parado,
                )
                if 0.0 < valor < 1.0
            ]
            self.slow_fator = min(candidatos, default=0.5)
        else:
            self.slow_fator = 1.0

    def _remover_familia_debuff(self, familia):
        self.dots_ativos = [
            dot
            for dot in self.dots_ativos
            if normalizar_efeito(getattr(dot, "tipo", "")) != familia
        ]

        timer = _TIMERS_POR_FAMILIA.get(familia)
        if timer:
            setattr(self, timer, 0.0)
        if familia == "NECROSE":
            self.cura_bloqueada_timer = 0.0
        elif familia == "CONGELADO":
            self.congelado_timer = 0.0
            self.congelado = False
            self.stun_timer = 0.0
        elif familia == "TEMPO_PARADO":
            self.tempo_parado_timer = 0.0
            self.tempo_parado = False
            self.stun_timer = 0.0
        elif familia == "SONO":
            self._quebrar_sono()
        elif familia == "ATORDOADO":
            self.stun_timer = 0.0
        elif familia == "LENTO":
            self.slow_timer = 0.0
        elif familia == "MARCADO":
            self.marcado = False
            self.marcado_timer = 0.0
        elif familia == "EXAUSTO":
            self.regen_mana_base = self.regen_mana_base_normal
        elif familia == "BOMBA_RELOGIO":
            self.bomba_relogio_dano = 0.0
            self.bomba_relogio_raio = 0.0
            self.bomba_relogio_origem = None
        elif familia == "LINK_ALMA":
            self.link_alma_alvo = None
            self.link_alma_percentual = 0.0
        elif familia == "CHARME":
            self.charme_origem = None
        elif familia == "POSSESSO":
            self.possesso_origem = None
        elif familia == "PROVOCADO":
            self.provocacao_origem = None

    def remover_debuffs(self, limite=None):
        """Remove famílias lógicas; DoTs repetidos contam como um debuff."""
        if limite is not None:
            limite = max(0, int(limite))
        tipos_dot = self._tipos_dot_ativos()
        familias_ativas = [
            familia
            for familia in (*DEBUFF_FAMILY_ORDER, "PROVOCADO")
            if self._familia_debuff_ativa(familia, tipos_dot)
        ]
        selecionadas = familias_ativas if limite is None else familias_ativas[:limite]
        for familia in selecionadas:
            self._remover_familia_debuff(familia)

        self._recalcular_movimento_apos_limpeza()
        return selecionadas

    def _aplicar_buff_skill(self, nome_skill, data, classe_buff):
        """Aplica a parte instantânea e registra a parte persistente do buff."""
        if self._skill_eh_passiva_de_morte(data):
            return False

        if data.get("remove_todos_debuffs"):
            self.remover_debuffs()
        elif data.get("remove_debuffs"):
            self.remover_debuffs(data["remove_debuffs"])

        if data.get("imune_debuffs"):
            self.imune_debuffs_timer = max(
                self.imune_debuffs_timer,
                float(data["imune_debuffs"]),
            )
        if data.get("cura"):
            self.receber_cura(data["cura"])

        if data.get("reverte_estado") is not None:
            return self.reverter_estado(data["reverte_estado"])

        buff = classe_buff(nome_skill, self, rng=self.rng_runtime)
        if getattr(buff, "persistente", False):
            self.buffs_ativos.append(buff)
        return True
    
    def tem_afinidade_trevas(self):
        """Retorna afinidade sombria explícita da classe ou da arma."""

        if "trevas" in str(self.classe_nome).casefold():
            return True
        arma = getattr(self.dados, "arma_obj", None)
        afinidade = getattr(arma, "afinidade_elemento", "") if arma else ""
        if str(afinidade).casefold() == "trevas":
            return True
        return any(
            str(nome).casefold() == "trevas"
            for nome in getattr(self, "arma_encantamentos", ())
        )

    def calcular_dano_ataque(self, dano_base, alvo=None):
        """Calcula dano final com crítico e encantamentos"""
        from neural_fights.models import ENCANTAMENTOS
        
        dano = dano_base * self.mod_dano
        for buff in self._buffs_validos():
            dano *= getattr(buff, "buff_dano", 1.0)
        
        critico_chance = self.arma_critico
        if "Assassino" in self.classe_nome:
            critico_chance += 0.20  # Reduzido de 0.25
        
        is_critico = self.rng_runtime.random() < critico_chance
        if is_critico:
            dano *= 1.5  # Reduzido de 2.0
        
        for enc_nome in self.arma_encantamentos:
            if enc_nome in ENCANTAMENTOS:
                enc = ENCANTAMENTOS[enc_nome]
                dano += enc.get("dano_bonus", 0)
                if (
                    enc_nome == "Sagrado"
                    and alvo is not None
                    and callable(getattr(alvo, "tem_afinidade_trevas", None))
                    and alvo.tem_afinidade_trevas()
                ):
                    dano *= 1.0 + max(
                        0.0,
                        float(enc.get("bonus_vs_trevas", 0.0)),
                    ) / 100.0
        
        return dano, is_critico
    
    def aplicar_efeitos_encantamento(self, alvo):
        """Aplica efeitos de encantamentos no alvo"""
        from neural_fights.models import ENCANTAMENTOS
        from neural_fights.core.combat import DotEffect
        
        for enc_nome in self.arma_encantamentos:
            if enc_nome not in ENCANTAMENTOS:
                continue
            
            enc = ENCANTAMENTOS[enc_nome]
            efeito = enc.get("efeito")
            contexto_encantamento = DamageContext(
                atacante=self,
                fonte=("encantamento", enc_nome),
                nome_skill=enc_nome,
                metadata={"tipo_fonte": "encantamento"},
            )
            
            if self.rng_runtime.random() > 0.5:
                continue
            
            if efeito == "burn":
                if not alvo.esta_imune_a_debuffs():
                    dot = DotEffect(
                        "QUEIMANDO",
                        alvo,
                        dano_por_tick=5,
                        duracao=3.0,
                        cor=(255, 100, 0),
                        contexto_dano=contexto_encantamento,
                    )
                    alvo.dots_ativos.append(dot)
            elif efeito == "slow":
                alvo._aplicar_efeito_status("LENTO", duracao=2.0)
            elif efeito == "poison":
                if not alvo.esta_imune_a_debuffs():
                    dot = DotEffect(
                        "ENVENENADO",
                        alvo,
                        dano_por_tick=enc.get("dot_dano", 3),
                        duracao=enc.get("dot_duracao", 5.0),
                        cor=(100, 255, 100),
                        contexto_dano=contexto_encantamento,
                    )
                    alvo.dots_ativos.append(dot)
            elif efeito == "lifesteal":
                percent = enc.get("lifesteal_percent", 10) / 100.0
                cura = alvo.vida * 0.1 * percent
                self.receber_cura(cura)

    def esta_sob_controle_mental(self):
        """Indica se o lutador perdeu temporariamente o controle ofensivo."""
        return self.charme_timer > 0.0 or self.possesso_timer > 0.0

    def esta_canalizando(self):
        channel = getattr(self, "channel_ativo", None)
        return bool(
            (channel is not None and getattr(channel, "ativo", False))
            or getattr(self, "canalizando", False)
        )

    def canalizacao_imobiliza(self):
        """Separa bloqueio de acoes do bloqueio opcional de movimento."""

        channel = getattr(self, "channel_ativo", None)
        return bool(
            channel is not None
            and getattr(channel, "ativo", False)
            and getattr(channel, "imobiliza", False)
        )

    def pode_iniciar_acao(self, *, permitir_medo=False):
        """Contrato único para movimento, ataques e novos casts."""
        return not (
            self.morto
            or self.dormindo
            or (self.medo_timer > 0.0 and not permitir_medo)
            or self.esta_sob_controle_mental()
            or self.esta_canalizando()
            or self.em_transicao_sombria()
        )

    def get_angulo_mira(self, angulo_real):
        """Aplica cegueira de forma fixa e reproduzível, sem RNG por frame."""
        if self.cego_timer <= 0.0:
            return float(angulo_real)
        desvio = get_status_runtime("CEGO").get("desvio_mira_graus", 35.0)
        return (float(angulo_real) + float(desvio) + 180.0) % 360.0 - 180.0

    def _quebrar_sono(self):
        if not self.dormindo and self.sono_timer <= 0.0:
            return False
        self.dormindo = False
        self.sono_timer = 0.0
        return True

    def _consumir_marca(self):
        if not self.marcado or self.marcado_timer <= 0.0:
            return False
        self.marcado = False
        self.marcado_timer = 0.0
        return True

    def pode_causar_dano(self, alvo=None):
        """Contrato comum para toda fonte ofensiva pertencente ao lutador."""
        if self.morto or self.esta_sob_controle_mental():
            return False
        if self.provocacao_timer > 0.0 and self.provocacao_origem is not None:
            if getattr(self.provocacao_origem, "morto", False):
                self.provocacao_timer = 0.0
                self.provocacao_origem = None
            elif alvo is not None and alvo is not self.provocacao_origem:
                return False
        return True

    def aplicar_provocacao(self, origem, duracao):
        """Força as fontes ofensivas do lutador a respeitarem o provocador."""
        if (
            origem is None
            or origem is self
            or self.morto
            or getattr(origem, "morto", False)
            or self.esta_imune_a_debuffs()
        ):
            return False
        self.provocacao_origem = origem
        self.provocacao_timer = max(self.provocacao_timer, max(0.0, float(duracao)))
        return self.provocacao_timer > 0.0

    def remover_congelamento(self):
        """Consome CONGELADO e restaura o slow herdado com segurança."""
        estava_congelado = self.congelado or self.congelado_timer > 0.0
        if not estava_congelado:
            return False
        self.congelado = False
        self.congelado_timer = 0.0
        self._recalcular_movimento_apos_limpeza()
        return True

    def _interromper_acoes_ofensivas(self):
        """Cancela ações em curso ao entrar em controle mental."""
        self.atacando = False
        self.usando_skill = False
        channel = getattr(self, "channel_ativo", None)
        if channel is not None:
            interromper = getattr(channel, "interromper", None)
            if callable(interromper):
                interromper()
            self.channel_ativo = None
        self.interromper_canalizacao()

    def _resolver_alvo_troca(self, alvo=None):
        """Retorna um alvo vivo e distinto para a Troca de Almas."""
        alvo = alvo or self._inimigo_atual
        if alvo is None or alvo is self or self.morto or getattr(alvo, "morto", True):
            return None
        if not hasattr(alvo, "pos") or len(alvo.pos) < 2:
            return None
        return alvo

    def _trocar_posicoes(self, alvo):
        """Troca somente a posição planar, preservando velocidade e altura."""
        pos_self = list(self.pos)
        pos_alvo = list(alvo.pos)
        self.pos[0], self.pos[1] = pos_alvo[0], pos_alvo[1]
        alvo.pos[0], alvo.pos[1] = pos_self[0], pos_self[1]
        self.dash_timer = 0.25
        return True

    def em_transicao_sombria(self):
        transicao = self._transicao_sombria
        return bool(transicao and transicao.get("restante", 0.0) > 0.0)

    def _finalizar_dash_skill(self, nome_skill, data, inicio, destino, rad):
        """Materializa um dash uma única vez e cria seus efeitos derivados."""

        from neural_fights.core.combat import (
            AreaEffect,
            PortalPair,
            capturar_modificadores_magicos,
        )

        self.pos[0], self.pos[1] = destino
        distancia = math.hypot(destino[0] - inicio[0], destino[1] - inicio[1])
        if data.get("cria_portal"):
            self.buffer_portais.append(
                PortalPair(
                    nome_skill,
                    inicio,
                    destino,
                    self,
                    duracao=data.get("duracao_portal"),
                )
            )

        self.dash_timer = max(self.dash_timer, 0.25)
        for indice in range(5):
            self.dash_trail.append(
                (
                    destino[0] - math.cos(rad) * distancia * (indice / 5),
                    destino[1] - math.sin(rad) * distancia * (indice / 5),
                    1.0 - indice * 0.2,
                )
            )

        dano = data.get("dano_chegada", data.get("dano", 0))
        if dano > 0:
            mod_dano_magico, mod_area_magica = capturar_modificadores_magicos(
                self,
                data,
            )
            area = AreaEffect(nome_skill, destino[0], destino[1], self)
            area.dano = dano * mod_dano_magico
            area.raio = 1.5 * mod_area_magica
            area.raio_atual = area.raio
            if nome_skill == "Avanço Brutal":
                area.segmento_impacto = (inicio, destino)
                area.raio_segmento = max(0.5, self.raio_fisico)
            self.buffer_areas.append(area)
        if data.get("invencivel"):
            self.invencivel_timer = max(self.invencivel_timer, 0.3)
            self.invulnerabilidade_skill_timer = max(
                self.invulnerabilidade_skill_timer,
                0.3,
            )

    def _executar_dash_skill(self, nome_skill, data, efeito, alvo_troca, rad):
        if efeito == "TROCAR_POS":
            return self._trocar_posicoes(alvo_troca)

        inicio = tuple(self.pos[:2])
        distancia = float(data.get("distancia", 4.0))
        destino = (
            inicio[0] + math.cos(rad) * distancia,
            inicio[1] + math.sin(rad) * distancia,
        )
        delay_saida = max(0.0, float(data.get("delay_saida", 0.0)))
        if data.get("invisivel_durante") and delay_saida > 0.0:
            self._interromper_acoes_ofensivas()
            self.vel[0] = 0.0
            self.vel[1] = 0.0
            self.dash_timer = max(self.dash_timer, delay_saida)
            self._transicao_sombria = {
                "nome": nome_skill,
                "data": dict(data),
                "inicio": inicio,
                "destino": destino,
                "rad": rad,
                "restante": delay_saida,
            }
            return True

        self._finalizar_dash_skill(nome_skill, data, inicio, destino, rad)
        return True

    def _atualizar_transicao_sombria(self, dt):
        transicao = self._transicao_sombria
        if not transicao:
            return False
        if self.morto:
            self._transicao_sombria = None
            return False
        transicao["restante"] = max(0.0, transicao["restante"] - dt)
        if transicao["restante"] > 0.0:
            self.vel[0] = 0.0
            self.vel[1] = 0.0
            return True

        self._transicao_sombria = None
        self._finalizar_dash_skill(
            transicao["nome"],
            transicao["data"],
            transicao["inicio"],
            transicao["destino"],
            transicao["rad"],
        )
        return False

    def usar_skill_arma(self, skill_idx=None, alvo=None):
        """Usa a skill equipada na arma"""
        if self.silenciado_timer > 0:
            return False

        from neural_fights.core.combat import (
            AreaEffect,
            Beam,
            Buff,
            Channel,
            Projetil,
            Summon,
            Trap,
            Transform,
        )
        
        if skill_idx is not None and skill_idx < len(self.skills_arma):
            skill_info = self.skills_arma[skill_idx]
        elif self.skills_arma:
            skill_info = self.skills_arma[self.skill_atual_idx]
        else:
            return False
        
        nome_skill = skill_info["nome"]
        if nome_skill == "Nenhuma":
            return False
        
        if self.cd_skills.get(nome_skill, 0) > 0:
            return False
        
        data = skill_info["data"]
        if not self.pode_iniciar_acao(
            permitir_medo=bool(data.get("remove_todos_debuffs", False)),
        ):
            return False
        if self._skill_eh_passiva_de_morte(data):
            return False
        if data.get("reverte_estado") is not None and not self.pode_reverter_estado(
            data["reverte_estado"]
        ):
            return False
        tipo = data.get("tipo", "NADA")
        efeito = normalizar_efeito(data.get("efeito"))
        alvo_troca = None
        if efeito == "TROCAR_POS":
            alvo_troca = self._resolver_alvo_troca(alvo)
            if alvo_troca is None:
                return False
        
        custo_real = skill_info["custo"]
        if "Mago" in self.classe_nome:
            custo_real *= 0.8
        custo_real *= self._get_modificador_mana_custo_buff()
        
        if self.arma_passiva and self.arma_passiva.get("efeito") == "no_mana_cost":
            chance = self.arma_passiva.get("valor", 0) / 100.0
            if self.rng_runtime.random() < chance:
                custo_real = 0
        
        custo_vida = data.get("custo_vida", 0) or data.get("custo_vida_percent", 0) * self.vida_max
        if self.mana < custo_real or (custo_vida > 0 and self.vida <= custo_vida):
            return False
        
        if custo_vida > 0:
            self.vida -= custo_vida
        self.mana -= custo_real
        
        cd = data["cooldown"] * self._get_modificador_cooldown_buff()
        if self.arma_passiva and self.arma_passiva.get("efeito") == "cooldown":
            cd *= (1 - self.arma_passiva.get("valor", 0) / 100.0)
        
        self.cd_skills[nome_skill] = cd
        self.cd_skill_arma = cd
        
        rad = math.radians(self.angulo_olhar)
        spawn_x = self.pos[0] + math.cos(rad) * 0.6
        spawn_y = self.pos[1] + math.sin(rad) * 0.6
        
        if tipo == "PROJETIL":
            # === ÁUDIO v10.0 - SOM DE CAST DE PROJÉTIL ===
            audio = self.audio
            if audio:
                audio.play_skill("PROJETIL", nome_skill, self.pos[0], phase="cast")
            
            multi = data.get("multi_shot", 1)
            if multi > 1:
                spread = 30
                for i in range(multi):
                    ang_offset = -spread/2 + (spread / (multi-1)) * i
                    p = Projetil(nome_skill, spawn_x, spawn_y, self.angulo_olhar + ang_offset, self)
                    self.buffer_projeteis.append(p)
            else:
                p = Projetil(nome_skill, spawn_x, spawn_y, self.angulo_olhar, self)
                self.buffer_projeteis.append(p)
            
            if data["dano"] > 20:
                self.vel[0] -= math.cos(rad) * 5.0
                self.vel[1] -= math.sin(rad) * 5.0
        
        elif tipo == "AREA":
            # === ÁUDIO v10.0 - SOM DE ÁREA ===
            audio = self.audio
            if audio:
                audio.play_skill("AREA", nome_skill, self.pos[0], phase="cast")
            
            area = AreaEffect(nome_skill, self.pos[0], self.pos[1], self)
            self.buffer_areas.append(area)
        
        elif tipo == "DASH":
            # === ÁUDIO v10.0 - SOM DE DASH ===
            audio = self.audio
            if audio:
                audio.play_skill("DASH", nome_skill, self.pos[0], phase="cast")
            
            self._executar_dash_skill(
                nome_skill,
                data,
                efeito,
                alvo_troca,
                rad,
            )
        
        elif tipo == "BUFF":
            # === ÁUDIO v10.0 - SOM DE BUFF ===
            audio = self.audio
            if audio:
                audio.play_skill("BUFF", nome_skill, self.pos[0], phase="cast")
            
            self._aplicar_buff_skill(nome_skill, data, Buff)
        
        elif tipo == "BEAM":
            # === ÁUDIO v10.0 - SOM DE BEAM ===
            audio = self.audio
            if audio:
                audio.play_skill("BEAM", nome_skill, self.pos[0], phase="cast")
            
            if data.get("canalizavel", False):
                Channel(nome_skill, self)
            else:
                alcance = data.get("alcance", 8.0)
                end_x = self.pos[0] + math.cos(rad) * alcance
                end_y = self.pos[1] + math.sin(rad) * alcance

                beam = Beam(nome_skill, self.pos[0], self.pos[1], end_x, end_y, self)
                self.buffer_beams.append(beam)
        
        # === TIPOS ADICIONAIS (v2.0) ===
        elif tipo == "SUMMON":
            audio = self.audio
            if audio:
                audio.play_skill("SUMMON", nome_skill, self.pos[0], phase="cast")
            
            summon_x = self.pos[0] + math.cos(rad) * 1.5
            summon_y = self.pos[1] + math.sin(rad) * 1.5
            
            summon = Summon(nome_skill, summon_x, summon_y, self)
            if not hasattr(self, 'buffer_summons'):
                self.buffer_summons = []
            self.buffer_summons.append(summon)
        
        elif tipo == "TRAP":
            audio = self.audio
            if audio:
                audio.play_skill("TRAP", nome_skill, self.pos[0], phase="cast")
            
            trap_x = self.pos[0] + math.cos(rad) * 2.0
            trap_y = self.pos[1] + math.sin(rad) * 2.0
            
            trap = Trap(nome_skill, trap_x, trap_y, self)
            if not hasattr(self, 'buffer_traps'):
                self.buffer_traps = []
            self.buffer_traps.append(trap)
        
        elif tipo == "TRANSFORM":
            audio = self.audio
            if audio:
                audio.play_skill("TRANSFORM", nome_skill, self.pos[0], phase="cast")
            
            Transform(nome_skill, self)
        
        elif tipo == "CHANNEL":
            audio = self.audio
            if audio:
                audio.play_skill("CHANNEL", nome_skill, self.pos[0], phase="cast")
            
            Channel(nome_skill, self)
        
        return True

    def usar_skill_classe(self, skill_nome, alvo=None):
        """Usa uma skill de classe específica"""
        if self.silenciado_timer > 0:
            return False

        from neural_fights.core.combat import (
            AreaEffect,
            Beam,
            Buff,
            Channel,
            Projetil,
            Summon,
            Trap,
            Transform,
        )
        
        skill_info = None
        for sk in self.skills_classe:
            if sk["nome"] == skill_nome:
                skill_info = sk
                break
        
        if not skill_info:
            return False
        
        if self.cd_skills.get(skill_nome, 0) > 0:
            return False
        
        data = skill_info["data"]
        if self._skill_eh_passiva_de_morte(data):
            return False
        if data.get("reverte_estado") is not None and not self.pode_reverter_estado(
            data["reverte_estado"]
        ):
            return False
        if not self.pode_iniciar_acao(
            permitir_medo=bool(data.get("remove_todos_debuffs", False)),
        ):
            return False
        tipo = data.get("tipo", "NADA")
        efeito = normalizar_efeito(data.get("efeito"))
        alvo_troca = None
        if efeito == "TROCAR_POS":
            alvo_troca = self._resolver_alvo_troca(alvo)
            if alvo_troca is None:
                return False
        custo = skill_info["custo"]
        
        if "Mago" in self.classe_nome:
            custo *= 0.8
        custo *= self._get_modificador_mana_custo_buff()
        
        # Custo em vida (Pacto de Sangue, Sacrifício)
        custo_vida = data.get("custo_vida", 0) or data.get("custo_vida_percent", 0) * self.vida_max
        if self.mana < custo or (custo_vida > 0 and self.vida <= custo_vida):
            return False
        
        if custo_vida > 0:
            self.vida -= custo_vida
        self.mana -= custo
        
        cd = data.get("cooldown", 5.0) * self._get_modificador_cooldown_buff()
        self.cd_skills[skill_nome] = cd
        
        rad = math.radians(self.angulo_olhar)
        spawn_x = self.pos[0] + math.cos(rad) * 0.6
        spawn_y = self.pos[1] + math.sin(rad) * 0.6
        
        if tipo == "PROJETIL":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = self.audio
            if audio:
                audio.play_skill("PROJETIL", skill_nome, self.pos[0], phase="cast")
            
            multi = data.get("multi_shot", 1)
            if multi > 1:
                spread = 30
                for i in range(multi):
                    ang_offset = -spread/2 + (spread / (multi-1)) * i
                    p = Projetil(skill_nome, spawn_x, spawn_y, self.angulo_olhar + ang_offset, self)
                    self.buffer_projeteis.append(p)
            else:
                p = Projetil(skill_nome, spawn_x, spawn_y, self.angulo_olhar, self)
                self.buffer_projeteis.append(p)
        
        elif tipo == "AREA":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = self.audio
            if audio:
                audio.play_skill("AREA", skill_nome, self.pos[0], phase="cast")
            
            area = AreaEffect(skill_nome, self.pos[0], self.pos[1], self)
            self.buffer_areas.append(area)
        
        elif tipo == "DASH":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = self.audio
            if audio:
                audio.play_skill("DASH", skill_nome, self.pos[0], phase="cast")
            
            self._executar_dash_skill(
                skill_nome,
                data,
                efeito,
                alvo_troca,
                rad,
            )
        
        elif tipo == "BUFF":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = self.audio
            if audio:
                audio.play_skill("BUFF", skill_nome, self.pos[0], phase="cast")
            
            self._aplicar_buff_skill(skill_nome, data, Buff)
        
        elif tipo == "BEAM":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = self.audio
            if audio:
                audio.play_skill("BEAM", skill_nome, self.pos[0], phase="cast")
            
            if data.get("canalizavel", False):
                Channel(skill_nome, self)
            else:
                alcance = data.get("alcance", 8.0)
                end_x = self.pos[0] + math.cos(rad) * alcance
                end_y = self.pos[1] + math.sin(rad) * alcance

                beam = Beam(skill_nome, self.pos[0], self.pos[1], end_x, end_y, self)
                self.buffer_beams.append(beam)
        
        # === NOVOS TIPOS v2.0 ===
        elif tipo == "SUMMON":
            audio = self.audio
            if audio:
                audio.play_skill("SUMMON", skill_nome, self.pos[0], phase="cast")
            
            # Spawn na frente do caster
            summon_x = self.pos[0] + math.cos(rad) * 1.5
            summon_y = self.pos[1] + math.sin(rad) * 1.5
            
            summon = Summon(skill_nome, summon_x, summon_y, self)
            if not hasattr(self, 'buffer_summons'):
                self.buffer_summons = []
            self.buffer_summons.append(summon)
        
        elif tipo == "TRAP":
            audio = self.audio
            if audio:
                audio.play_skill("TRAP", skill_nome, self.pos[0], phase="cast")
            
            # Spawn na frente do caster
            trap_x = self.pos[0] + math.cos(rad) * 2.0
            trap_y = self.pos[1] + math.sin(rad) * 2.0
            
            trap = Trap(skill_nome, trap_x, trap_y, self)
            if not hasattr(self, 'buffer_traps'):
                self.buffer_traps = []
            self.buffer_traps.append(trap)
        
        elif tipo == "TRANSFORM":
            audio = self.audio
            if audio:
                audio.play_skill("TRANSFORM", skill_nome, self.pos[0], phase="cast")
            
            Transform(skill_nome, self)
        
        elif tipo == "CHANNEL":
            audio = self.audio
            if audio:
                audio.play_skill("CHANNEL", skill_nome, self.pos[0], phase="cast")
            
            Channel(skill_nome, self)
        
        return True

    def _atualizar_efeitos_especiais(self, dt):
        """Atualiza vínculos/status que precisam de origem e ação na expiração."""
        dt = max(0.0, dt)
        if self.morto:
            self.charme_timer = 0.0
            self.charme_origem = None
            self.possesso_timer = 0.0
            self.possesso_origem = None
            self.bomba_relogio_timer = 0.0
            self.bomba_relogio_dano = 0.0
            self.bomba_relogio_raio = 0.0
            self.bomba_relogio_origem = None
            self.link_alma_timer = 0.0
            self.link_alma_alvo = None
            self.link_alma_percentual = 0.0
            return

        if self.charme_timer <= 0.0:
            self.charme_timer = 0.0
            self.charme_origem = None
        else:
            origem = self.charme_origem
            if origem is None or origem is self or getattr(origem, "morto", True):
                self.charme_timer = 0.0
                self.charme_origem = None
            else:
                self.charme_timer = max(0.0, self.charme_timer - dt)
                if self.charme_timer <= 0.0:
                    self.charme_origem = None

        if self.possesso_timer <= 0.0:
            self.possesso_timer = 0.0
            self.possesso_origem = None
        else:
            origem = self.possesso_origem
            if origem is None or origem is self or getattr(origem, "morto", True):
                self.possesso_timer = 0.0
                self.possesso_origem = None
            else:
                self.possesso_timer = max(0.0, self.possesso_timer - dt)
                if self.possesso_timer <= 0.0:
                    self.possesso_origem = None

        if self.link_alma_timer <= 0.0:
            self.link_alma_timer = 0.0
            self.link_alma_alvo = None
            self.link_alma_percentual = 0.0
        else:
            parceiro = self.link_alma_alvo
            if parceiro is None or parceiro is self or getattr(parceiro, "morto", True):
                self.link_alma_timer = 0.0
                self.link_alma_alvo = None
                self.link_alma_percentual = 0.0
            else:
                self.link_alma_timer = max(0.0, self.link_alma_timer - dt)
                if self.link_alma_timer <= 0.0:
                    self.link_alma_alvo = None
                    self.link_alma_percentual = 0.0

        if self.bomba_relogio_timer > 0.0:
            self.bomba_relogio_timer = max(0.0, self.bomba_relogio_timer - dt)
            if self.bomba_relogio_timer <= 0.0:
                from neural_fights.core.combat import AreaEffect

                dano = self.bomba_relogio_dano
                raio = self.bomba_relogio_raio
                origem = self.bomba_relogio_origem
                self.bomba_relogio_dano = 0.0
                self.bomba_relogio_raio = 0.0
                self.bomba_relogio_origem = None
                if dano > 0.0 and origem is not None and origem is not self:
                    explosao = AreaEffect(
                        "Bomba Relógio",
                        self.pos[0],
                        self.pos[1],
                        origem,
                    )
                    explosao.delay = 0.0
                    explosao.ativado = True
                    explosao.raio = raio
                    explosao.dano = dano
                    explosao.dano_precalculado = True
                    explosao.tipo_efeito = "EXPLOSAO"
                    self.buffer_areas.append(explosao)
        elif self.bomba_relogio_origem is not None:
            self.bomba_relogio_timer = 0.0
            self.bomba_relogio_dano = 0.0
            self.bomba_relogio_raio = 0.0
            self.bomba_relogio_origem = None

    def _executar_charme(self, dt, origem, distancia):
        """Segue o conjurador sem entregar o controle permanente à IA."""
        distancia_seguir = (
            self.raio_fisico
            + getattr(origem, "raio_fisico", 0.5)
            + 0.35
        )
        if distancia <= distancia_seguir:
            return

        aceleracao = self._get_aceleracao_movimento(35.0 / 45.0)
        rad = math.radians(self.angulo_olhar)
        self.vel[0] += math.cos(rad) * aceleracao * dt
        self.vel[1] += math.sin(rad) * aceleracao * dt

    def _executar_medo(self, dt, origem):
        """Foge diretamente da ameaça enquanto o timer explícito estiver ativo."""
        dx = self.pos[0] - origem.pos[0]
        dy = self.pos[1] - origem.pos[1]
        distancia = math.hypot(dx, dy) or 1.0
        aceleracao = self._get_aceleracao_movimento(1.3)
        self.vel[0] += (dx / distancia) * aceleracao * dt
        self.vel[1] += (dy / distancia) * aceleracao * dt
        if self.brain is not None:
            self.brain.acao_atual = "FUGIR"

    def update(self, dt, inimigo):
        """Atualiza estado do lutador"""
        from neural_fights.core.physics import normalizar_angulo

        dt = max(0.0, float(dt))
        self._tempo_runtime += dt
        self._inimigo_atual = inimigo
        
        if self.invencivel_timer > 0:
            self.invencivel_timer -= dt
        if self.invulnerabilidade_skill_timer > 0:
            self.invulnerabilidade_skill_timer = max(
                0.0,
                self.invulnerabilidade_skill_timer - dt,
            )
        if self._fontes_impacto_recentes:
            self._fontes_impacto_recentes = {
                fonte: restante - dt
                for fonte, restante in self._fontes_impacto_recentes.items()
                if restante - dt > 0.0
            }
        if self.provocacao_timer > 0.0:
            self.provocacao_timer = max(0.0, self.provocacao_timer - dt)
            if (
                self.provocacao_timer <= 0.0
                or self.provocacao_origem is None
                or getattr(self.provocacao_origem, "morto", False)
            ):
                self.provocacao_origem = None
        if self.flash_timer > 0:
            self.flash_timer -= dt
        if self.cura_bloqueada_timer > 0.0:
            self.cura_bloqueada_timer = max(0.0, self.cura_bloqueada_timer - dt)
        if self.imune_debuffs_timer > 0.0:
            self.imune_debuffs_timer = max(0.0, self.imune_debuffs_timer - dt)
        if self.stun_timer > 0:
            self.stun_timer -= dt
        if self.cd_skill_arma > 0:
            self.cd_skill_arma -= dt
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_timer = 0.0
                if (self.enraizado_timer <= 0 and self.congelado_timer <= 0
                        and self.tempo_parado_timer <= 0):
                    self.slow_fator = 1.0

        if self.enraizado_timer > 0:
            self.enraizado_timer = max(0.0, self.enraizado_timer - dt)
            if self.enraizado_timer <= 0:
                if self.tempo_parado_timer > 0:
                    self.slow_fator = 0.0
                elif self.congelado_timer > 0:
                    self.slow_fator = min(self._slow_fator_antes_enraizado, 0.3)
                elif self.slow_timer > 0:
                    self.slow_fator = self._slow_fator_antes_enraizado
                else:
                    self.slow_fator = 1.0

        if self.congelado_timer > 0:
            self.congelado_timer = max(0.0, self.congelado_timer - dt)
            if self.congelado_timer <= 0:
                self.congelado = False
                if self.enraizado_timer > 0 or self.tempo_parado_timer > 0:
                    self.slow_fator = 0.0
                elif self.slow_timer > 0:
                    self.slow_fator = self._slow_fator_antes_congelado
                else:
                    self.slow_fator = 1.0

        if self.tempo_parado_timer > 0:
            self.tempo_parado_timer = max(0.0, self.tempo_parado_timer - dt)
            if self.tempo_parado_timer <= 0:
                self.tempo_parado = False
                if self.enraizado_timer > 0:
                    self.slow_fator = 0.0
                elif self.congelado_timer > 0:
                    self.slow_fator = min(self._slow_fator_antes_tempo_parado, 0.3)
                elif self.slow_timer > 0:
                    self.slow_fator = self._slow_fator_antes_tempo_parado
                else:
                    self.slow_fator = 1.0

        if self.silenciado_timer > 0:
            self.silenciado_timer = max(0.0, self.silenciado_timer - dt)

        self.cego_timer = max(0.0, self.cego_timer - dt)
        self.medo_timer = max(0.0, self.medo_timer - dt)
        if self.sono_timer > 0.0:
            self.sono_timer = max(0.0, self.sono_timer - dt)
            if self.sono_timer <= 0.0:
                self.dormindo = False
        elif self.dormindo:
            self.dormindo = False
        if self.marcado_timer > 0.0:
            self.marcado_timer = max(0.0, self.marcado_timer - dt)
            if self.marcado_timer <= 0.0:
                self.marcado = False
        elif self.marcado:
            self.marcado = False

        if self.exausto_timer > 0:
            self.exausto_timer = max(0.0, self.exausto_timer - dt)
            if self.exausto_timer <= 0:
                self.regen_mana_base = self.regen_mana_base_normal

        # Debuffs puramente numéricos expiram sem efeito colateral.
        for status_numerico in _DEBUFFS_NUMERICOS:
            restante = self.status_timers.get(status_numerico)
            if restante > 0.0:
                self.status_timers.set(status_numerico, restante - dt)
        if self.pulo_bloqueado_timer > 0.0:
            self.pulo_bloqueado_timer = max(
                0.0,
                self.pulo_bloqueado_timer - dt,
            )
        self._atualizar_efeitos_especiais(dt)
        
        for skill_nome in list(self.cd_skills.keys()):
            if self.cd_skills[skill_nome] > 0:
                self.cd_skills[skill_nome] -= dt

        self._atualizar_buffs(dt)
        self._atualizar_dots(dt)
        self._atualizar_dash_trail(dt)
        self._atualizar_orbes(dt)
        transicao_sombria_ativa = self._atualizar_transicao_sombria(dt)
        
        if self.dash_timer > 0:
            self.dash_timer -= dt
        
        self.pos_historico.append((self.pos[0], self.pos[1]))
        if len(self.pos_historico) > 15:
            self.pos_historico.pop(0)
        self._registrar_estado_historico()
        
        self.aura_pulso += dt * 3
        if self.aura_pulso > math.pi * 2:
            self.aura_pulso = 0

        if self.morto:
            self.aplicar_fisica(dt)
            return

        if transicao_sombria_ativa:
            # A saída do Portal Sombrio é uma transição real: o lutador
            # continua processando timers, buffs e DoTs, mas não ocupa o mundo
            # físico nem recebe uma nova decisão da IA até reaparecer.
            self.vel[0] = 0.0
            self.vel[1] = 0.0
            return

        mana_regen = self.regen_mana_base
        if "Mago" in self.classe_nome:
            mana_regen *= 1.5
        self.mana = min(self.mana_max, self.mana + mana_regen * dt)
        
        if "Paladino" in self.classe_nome:
            self.receber_cura(self.vida_max * 0.005 * dt)  # Reduzido de 2% para 0.5%
        
        origem_charme = (
            self.charme_origem
            if self.charme_timer > 0.0
            else None
        )
        origem_possesso = (
            self.possesso_origem
            if self.possesso_timer > 0.0
            else None
        )
        alvo_comportamento = origem_charme or origem_possesso or inimigo
        dx = alvo_comportamento.pos[0] - self.pos[0]
        dy = alvo_comportamento.pos[1] - self.pos[1]
        distancia = math.hypot(dx, dy)
        angulo_alvo = self.get_angulo_mira(math.degrees(math.atan2(dy, dx)))
        diff = normalizar_angulo(angulo_alvo - self.angulo_olhar)
        
        vel_giro = 20.0 if "Assassino" in self.classe_nome or "Ninja" in self.classe_nome else 10.0
        self.angulo_olhar += diff * vel_giro * dt

        if self.dormindo or self.canalizacao_imobiliza():
            self.vel[0] = 0.0
            self.vel[1] = 0.0
        elif self.stun_timer <= 0:
            if origem_possesso is not None:
                # Em uma luta autônoma 1x1 não existe um segundo canal de
                # comandos: possessão suspende movimento e iniciativa.
                self.vel[0] = 0.0
                self.vel[1] = 0.0
            elif origem_charme is not None:
                self._executar_charme(dt, origem_charme, distancia)
            elif self.medo_timer > 0.0 and not inimigo.morto:
                self._executar_medo(dt, inimigo)
            # Só processa IA se tiver brain (não em modo manual)
            elif not inimigo.morto and self.brain is not None:
                self.brain.processar(dt, distancia, inimigo)
                self.executar_movimento(dt, distancia)
                self.executar_ataques(dt, distancia, inimigo)

        self.aplicar_fisica(dt)

    def _atualizar_buffs(self, dt):
        """Atualiza buffs ativos"""
        for buff in self.buffs_ativos[:]:
            buff.atualizar(dt)
            if not buff.ativo:
                self.buffs_ativos.remove(buff)
    
    def _atualizar_dots(self, dt):
        """Atualiza DoTs ativos"""
        for dot in self.dots_ativos[:]:
            dot.atualizar(dt)
            if not dot.ativo:
                self.dots_ativos.remove(dot)

    def _renovar_dot(
        self,
        tipo,
        dano_por_tick,
        duracao,
        cor,
        contexto_dano=None,
    ):
        """Adiciona um DoT ou renova a instância ativa do mesmo tipo."""
        from neural_fights.core.combat import DotEffect

        for dot in self.dots_ativos:
            if dot.ativo and dot.tipo == tipo:
                dot.vida = max(dot.vida, duracao)
                dot.duracao = max(dot.duracao, duracao)
                dot.dano_por_tick = max(dot.dano_por_tick, dano_por_tick * 0.5)
                if contexto_dano is not None:
                    dot.contexto_dano = contexto_dano
                return dot

        dot = DotEffect(
            tipo,
            self,
            dano_por_tick,
            duracao,
            cor,
            contexto_dano=contexto_dano,
        )
        self.dots_ativos.append(dot)
        return dot

    def _get_modificador_dano_causado_debuff(self):
        """Retorna apenas o modificador temporário de dano causado."""
        return self.status_timers.modificador("mod_dano_causado", combinar=min)

    def _get_modificador_dano_recebido_debuff(self):
        """Debuffs recebidos não multiplicam entre si; prevalece o maior."""
        return self.status_timers.modificador("mod_dano_recebido", combinar=max)

    def configurar_contexto_partida(self, *, audio=None, arena=None, choreographer=None):
        """Injeta os colaboradores que antes eram lidos de singletons globais.

        O dono da partida (``Simulador``) chama isto ao montar cada round, de
        modo que o lutador nunca precise alcançar estado de módulo.
        """
        self._audio = audio
        self._arena = arena
        self._choreographer = choreographer

    @property
    def audio(self):
        """Canal de áudio da partida; cai no singleton se ninguém injetou."""
        if self._audio is not None:
            return self._audio
        from neural_fights.effects.audio import AudioManager

        return AudioManager.get_instance()

    @property
    def arena(self):
        """Arena da partida; cai na instância de módulo se ninguém injetou."""
        if self._arena is not None:
            return self._arena
        from neural_fights.core.arena import get_arena

        return get_arena()

    @property
    def choreographer(self):
        """Coreógrafo da partida; cai no singleton se ninguém injetou."""
        if self._choreographer is not None:
            return self._choreographer
        from neural_fights.ai.choreographer import CombatChoreographer

        return CombatChoreographer.get_instance()

    @property
    def dano_reduzido(self):
        """Modificador de dano causado, derivado dos debuffs ativos."""
        return self._get_modificador_dano_causado_debuff()

    @property
    def vulnerabilidade(self):
        """Modificador de dano recebido, derivado dos debuffs ativos."""
        return self._get_modificador_dano_recebido_debuff()

    @property
    def cura_bloqueada(self):
        """Alias histórico: espelha ``cura_bloqueada_timer``."""
        return self.cura_bloqueada_timer

    @cura_bloqueada.setter
    def cura_bloqueada(self, valor):
        try:
            restante = float(valor)
        except (TypeError, ValueError):
            restante = 0.0
        self.cura_bloqueada_timer = max(0.0, restante)

    def _atualizar_dash_trail(self, dt):
        """Fade do trail de dash"""
        for i, (x, y, alpha) in enumerate(self.dash_trail):
            self.dash_trail[i] = (x, y, alpha - dt * 3)
        self.dash_trail = [(x, y, a) for x, y, a in self.dash_trail if a > 0]

    def _atualizar_orbes(self, dt):
        """Atualiza orbes mágicos e remove os inativos"""
        for orbe in self.buffer_orbes:
            orbe.atualizar(dt)
        self.buffer_orbes = [o for o in self.buffer_orbes if o.ativo]

    def aplicar_fisica(self, dt):
        """Aplica física de movimento"""
        vel_mult = self.slow_fator
        
        altura_voo = self._altura_voo_ativa()
        if altura_voo > 0.0:
            self.z = max(self.z, altura_voo)
            self.vel_z = 0.0
        elif self.z > 0 or self.vel_z > 0:
            self.vel_z -= GRAVIDADE_Z * dt
            self.z += self.vel_z * dt
            if self.z < 0:
                self.z = 0
                self.vel_z = 0
        
        fr = ATRITO if self.z == 0 else ATRITO * 0.2
        self.vel[0] -= self.vel[0] * fr * dt
        self.vel[1] -= self.vel[1] * fr * dt
        self.pos[0] += self.vel[0] * vel_mult * dt
        self.pos[1] += self.vel[1] * vel_mult * dt

    def executar_movimento(self, dt, distancia):
        """Executa movimento baseado na ação da IA - v8.0 com comportamento humano"""
        if self.dormindo or self.canalizacao_imobiliza():
            self.vel[0] = 0.0
            self.vel[1] = 0.0
            return
        acao = self.brain.acao_atual
        acc = self._get_aceleracao_movimento()
        if self.modo_adrenalina:
            acc *= 70.0 / 45.0
        
        # v8.0: Aplica variação humana na aceleração
        if hasattr(self.brain, 'ritmo_combate'):
            acc *= self.brain.ritmo_combate
        
        # v8.0: Momentum afeta velocidade
        if hasattr(self.brain, 'momentum'):
            if self.brain.momentum > 0.3:
                acc *= 1.0 + self.brain.momentum * 0.15
            elif self.brain.momentum < -0.3:
                acc *= 1.0 + self.brain.momentum * 0.1  # Diminui menos quando perdendo
        
        mx, my = 0, 0
        rad = math.radians(self.angulo_olhar)
        
        if acao in ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "APROXIMAR", "CONTRA_ATAQUE", "PRESSIONAR"]:
            mx = math.cos(rad)
            my = math.sin(rad)
            mult = {
                "MATAR": 1.0, "ESMAGAR": 0.85, "ATAQUE_RAPIDO": 1.25,
                "APROXIMAR": 1.0, "CONTRA_ATAQUE": 1.4, "PRESSIONAR": 1.1
            }.get(acao, 1.0)
            mx *= mult
            my *= mult
            
            # v8.0: Micro-ajustes durante ataques para parecer mais humano
            if hasattr(self.brain, 'micro_ajustes'):
                mx += self.rng_runtime.uniform(-0.05, 0.05)
                my += self.rng_runtime.uniform(-0.05, 0.05)
            
        elif acao == "COMBATE":
            mx = math.cos(rad) * 0.6
            my = math.sin(rad) * 0.6
            # v8.0: Mais variação no combate
            chance_strafe = 0.35 if "ESPACAMENTO_MESTRE" in self.brain.tracos else 0.3
            if self.rng_runtime.random() < chance_strafe:
                strafe_rad = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
                strafe_mult = self.rng_runtime.uniform(0.25, 0.4)
                mx += math.cos(strafe_rad) * strafe_mult
                my += math.sin(strafe_rad) * strafe_mult
                
        elif acao in ["RECUAR", "FUGIR"]:
            mx = -math.cos(rad)
            my = -math.sin(rad)
            if acao == "FUGIR":
                mx *= 1.3
                my *= 1.3
            # v8.0: Desvio diagonal ao fugir para parecer mais esperto
            if self.rng_runtime.random() < 0.3:
                lateral = self.rng_runtime.choice([-1, 1]) * self.brain.dir_circular
                rad_lat = math.radians(self.angulo_olhar + (30 * lateral))
                mx += math.cos(rad_lat) * 0.3
                my += math.sin(rad_lat) * 0.3
        
        elif acao == "DESVIO":
            # v8.0: Nova ação de desvio mais dinâmica
            rad_lat = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
            mx = math.cos(rad_lat) * 1.2
            my = math.sin(rad_lat) * 1.2
            # Adiciona um pouco de recuo
            mx -= math.cos(rad) * 0.3
            my -= math.sin(rad) * 0.3
                
        elif acao == "CIRCULAR":
            rad_lat = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
            mx = math.cos(rad_lat) * 0.85
            my = math.sin(rad_lat) * 0.85
            # v8.0: Ajuste de distância enquanto circula
            if distancia < 2.5:
                mx -= math.cos(rad) * 0.3  # Afasta um pouco
                my -= math.sin(rad) * 0.3
            elif distancia > 4.0:
                mx += math.cos(rad) * 0.2  # Aproxima um pouco
                my += math.sin(rad) * 0.2
            else:
                mx += math.cos(rad) * 0.25
                my += math.sin(rad) * 0.25
            
        elif acao == "FLANQUEAR":
            # v8.0: Flanqueio mais dinâmico
            angulo_flank = 50 + self.rng_runtime.uniform(-10, 10)
            rad_f = math.radians(self.angulo_olhar + (angulo_flank * self.brain.dir_circular))
            mx = math.cos(rad_f)
            my = math.sin(rad_f)
            
        elif acao == "APROXIMAR_LENTO":
            mx = math.cos(rad) * 0.55
            my = math.sin(rad) * 0.55
            # v8.0: Pequenos movimentos laterais ao aproximar
            if self.rng_runtime.random() < 0.2:
                rad_lat = math.radians(
                    self.angulo_olhar + (90 * self.rng_runtime.choice([-1, 1]))
                )
                mx += math.cos(rad_lat) * 0.15
                my += math.sin(rad_lat) * 0.15
            
        elif acao == "POKE":
            # v8.0: Poke mais inteligente
            if self.rng_runtime.random() < 0.6:
                mx = math.cos(rad) * 0.8
                my = math.sin(rad) * 0.8
            else:
                # Recua depois do poke
                mx = -math.cos(rad) * 0.4
                my = -math.sin(rad) * 0.4
                
        elif acao == "BLOQUEAR":
            if self.rng_runtime.random() < 0.4 and distancia > 2.5:
                strafe_rad = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
                mx = math.cos(strafe_rad) * 0.2
                my = math.sin(strafe_rad) * 0.2
        
        elif acao == "ATAQUE_AEREO":
            mx = math.cos(rad) * 0.8
            my = math.sin(rad) * 0.8
        
        # v8.0: Nova ação - pressionar continuamente
        elif acao == "PRESSIONAR_CONTINUO":
            mx = math.cos(rad) * 1.1
            my = math.sin(rad) * 1.1
            # Pequenos ajustes laterais
            if self.rng_runtime.random() < 0.25:
                rad_lat = math.radians(self.angulo_olhar + (30 * self.brain.dir_circular))
                mx += math.cos(rad_lat) * 0.2
                my += math.sin(rad_lat) * 0.2
            
        # Sistema de pulos
        if "SALTADOR" in self.brain.tracos and self.pode_pular():
            chance_pulo = 0.08
            if distancia < 3.0:
                chance_pulo = 0.12
            if acao in ["RECUAR", "FUGIR"]:
                chance_pulo = 0.15
            if self.rng_runtime.random() < chance_pulo:
                self.vel_z = self.rng_runtime.uniform(10.0, 14.0)
        
        elif acao in ["RECUAR", "FUGIR"] and self.pode_pular():
            chance = 0.03
            if self.brain is not None and self.brain.medo > 0.5:
                chance = 0.06
            if self.rng_runtime.random() < chance:
                self.vel_z = self.rng_runtime.uniform(9.0, 12.0)
        
        # v8.0: Pulo ofensivo mais inteligente
        ofensivos = ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "CONTRA_ATAQUE"]
        if acao in ofensivos and 3.5 < distancia < 7.0 and self.pode_pular():
            chance = 0.025
            if "ACROBATA" in self.brain.tracos:
                chance = 0.05
            if self.rng_runtime.random() < chance:
                self.vel_z = self.rng_runtime.uniform(12.0, 15.0)
                self.modo_ataque_aereo = True
        
        if (
            self.pode_pular()
            and distancia < 5.0
            and self.rng_runtime.random() < 0.005
        ):
            self.vel_z = self.rng_runtime.uniform(8.0, 11.0)

        self.vel[0] += mx * acc * dt
        self.vel[1] += my * acc * dt

    def executar_ataques(self, dt, distancia, inimigo):
        """Executa ataques físicos com sistema de animação aprimorado v2.0"""
        if not self.pode_iniciar_acao():
            self.atacando = False
            return
        from neural_fights.effects.weapon_animations import (
            WEAPON_PROFILES,
            get_weapon_animation_manager,
        )
        
        self.cooldown_ataque -= dt
        
        arma_tipo = self.dados.arma_obj.tipo if self.dados.arma_obj else "Reta"
        is_orbital = self.dados.arma_obj and "Orbital" in arma_tipo
        
        # Obtém gerenciador de animações
        anim_manager = get_weapon_animation_manager()
        
        # Calcula posição da ponta da arma para trail
        rad = math.radians(self.angulo_olhar)
        tip_dist = self.raio_fisico * 2.5
        weapon_tip = (
            self.pos[0] + math.cos(rad) * tip_dist,
            self.pos[1] + math.sin(rad) * tip_dist
        )
        
        # Atualiza animação
        transform = anim_manager.get_weapon_transform(
            id(self), arma_tipo, self.angulo_olhar, weapon_tip, dt
        )
        
        # Aplica transformações
        self.weapon_anim_scale = transform["scale"]
        self.weapon_anim_shake = transform["shake"]
        self.weapon_trail_positions = transform["trail_positions"]
        
        # Orbital: sempre gira
        if is_orbital:
            spd = 200
            if self.brain.acao_atual in ["MATAR", "BLOQUEAR", "COMBATE"] or distancia < 2.5:
                spd = 1000
            self.angulo_arma_visual += spd * dt
        elif self.atacando:
            # Usa novo sistema de animação
            self.timer_animacao -= dt
            
            # Obtém perfil da arma
            profile = WEAPON_PROFILES.get(arma_tipo, WEAPON_PROFILES["Reta"])
            
            if self.timer_animacao <= 0:
                self.atacando = False
                self.angulo_arma_visual = self.angulo_olhar
            else:
                # Aplica offset do animador
                self.angulo_arma_visual = self.angulo_olhar + transform["angle_offset"]
        else:
            # Animação idle
            self.angulo_arma_visual = self.angulo_olhar + transform["angle_offset"]

        if not self.atacando and not is_orbital and self.cooldown_ataque <= 0:
            acoes_ofensivas = ["MATAR", "ESMAGAR", "COMBATE", "ATAQUE_RAPIDO", "FLANQUEAR", "POKE", "PRESSIONAR", "CONTRA_ATAQUE"]
            deve_atacar = False
            
            # Calcula alcance de ataque usando mesmo método que brain.py
            try:
                from neural_fights.core.hitbox import HITBOX_PROFILES
                from neural_fights.utils.config import PPM
                profile_hitbox = HITBOX_PROFILES.get(arma_tipo, HITBOX_PROFILES.get("Reta", {}))
                range_mult = profile_hitbox.get("range_mult", 2.0)
                alcance_base = self.raio_fisico * range_mult
                
                # Adiciona componente da arma como brain.py faz
                arma = self.dados.arma_obj if self.dados else None
                if arma_tipo == "Dupla":
                    comp = getattr(arma, 'comp_lamina', 55) / PPM if arma else 1.1
                    alcance_ataque = alcance_base + comp * 0.4
                elif arma_tipo == "Reta":
                    comp_total = (getattr(arma, 'comp_cabo', 20) + getattr(arma, 'comp_lamina', 40)) / PPM if arma else 1.2
                    alcance_ataque = alcance_base + comp_total * 0.3
                else:
                    alcance_ataque = alcance_base
                
                # Margem de 30% para garantir ataque quando IA decide
                alcance_ataque *= 1.3
            except (ImportError, AttributeError, KeyError, TypeError, ValueError, ZeroDivisionError):
                alcance_ataque = self.raio_fisico * 3.0  # Fallback generoso
            
            # Ajustes APENAS para armas ranged (não sobrescreve corpo-a-corpo!)
            if arma_tipo == "Arco":
                alcance_ataque = 20.0  # Arco: MUITO alcance (20 metros!)
            elif arma_tipo == "Arremesso":
                alcance_ataque = 12.0  # Arremesso: alcance médio
            elif arma_tipo == "Mágica":
                alcance_ataque = 8.0
            # Para armas corpo-a-corpo (incluindo Dupla), usa o cálculo baseado no profile
            
            # Verifica se deve atacar
            if self.brain.acao_atual in acoes_ofensivas and distancia < alcance_ataque:
                deve_atacar = True
            if self.brain.acao_atual == "POKE" and abs(distancia - self.alcance_ideal) < 1.5:
                deve_atacar = True
            if self.modo_ataque_aereo and distancia < 2.0:
                deve_atacar = True
            
            # === ARMAS RANGED: atacam mesmo recuando/fugindo! ===
            if arma_tipo in ["Arremesso", "Arco"] and distancia < alcance_ataque:
                # Arqueiros atiram mesmo fugindo (desde que não esteja em cooldown)
                if self.brain.acao_atual in ["RECUAR", "FUGIR", "APROXIMAR"]:
                    if self.rng_runtime.random() < 0.7:  # 70% chance de atirar mesmo recuando
                        deve_atacar = True

            if deve_atacar and abs(self.z - inimigo.z) < 1.5:
                self.atacando = True
                
                # === v10.1: Novo ataque = novo ID, limpa alvos atingidos ===
                self.ataque_id += 1
                self.alvos_atingidos_neste_ataque.clear()
                
                # Usa duração do perfil da arma
                profile = WEAPON_PROFILES.get(arma_tipo, WEAPON_PROFILES["Reta"])
                self.timer_animacao = profile.total_time
                
                # Inicia animação no gerenciador
                anim_manager.start_attack(id(self), arma_tipo, tuple(self.pos), self.angulo_olhar)
                
                if arma_tipo == "Arremesso":
                    self._disparar_arremesso(inimigo)
                elif arma_tipo == "Arco":
                    self._disparar_flecha(inimigo)
                elif arma_tipo == "Mágica":
                    self._disparar_orbes(inimigo)
                
                base_cd = 0.5 + self.rng_runtime.random() * 0.5
                if arma_tipo in ["Arremesso", "Arco"]:
                    base_cd = 0.8 + self.rng_runtime.random() * 0.4
                elif arma_tipo == "Mágica":
                    base_cd = 1.0 + self.rng_runtime.random() * 0.5
                if "Assassino" in self.classe_nome or "Ninja" in self.classe_nome:
                    base_cd *= 0.7
                elif "Colosso" in self.brain.arquetipo:
                    base_cd *= 1.3
                self.cooldown_ataque = (
                    base_cd / self._get_modificador_velocidade_ataque_buff()
                )
    
    def _disparar_arremesso(self, alvo):
        """Dispara projéteis de arma de arremesso"""
        from neural_fights.core.combat import ArmaProjetil
        
        arma = self.dados.arma_obj
        if not arma:
            return
        
        qtd = int(getattr(arma, 'quantidade', 3))
        tam = getattr(arma, 'tamanho_projetil', 15) / PPM
        dano_por_proj = arma.dano / max(qtd, 1)
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (200, 200, 200)
        
        nome_lower = arma.nome.lower()
        if "shuriken" in nome_lower:
            tipo_proj = "shuriken"
            vel = 18.0
        elif "chakram" in nome_lower:
            tipo_proj = "chakram"
            vel = 14.0
        else:
            tipo_proj = "faca"
            vel = 16.0
        
        spread = 25 if qtd > 1 else 0
        
        for i in range(qtd):
            if qtd > 1:
                offset = -spread/2 + (spread / (qtd-1)) * i
            else:
                offset = 0
            
            ang = self.angulo_olhar + offset
            # Spawn BEM FORA do corpo do lutador
            spawn_dist = self.raio_fisico + 0.5
            spawn_x = self.pos[0] + math.cos(math.radians(ang)) * spawn_dist
            spawn_y = self.pos[1] + math.sin(math.radians(ang)) * spawn_dist
            
            proj = ArmaProjetil(
                tipo=tipo_proj,
                x=spawn_x, y=spawn_y,
                angulo=ang,
                dono=self,
                dano=dano_por_proj * (self.dados.forca / 2.0),
                velocidade=vel,
                tamanho=tam,
                cor=cor
            )
            self.buffer_projeteis.append(proj)
    
    def _disparar_flecha(self, alvo):
        """Dispara flecha do arco - DIRETA E PRECISA"""
        from neural_fights.core.combat import FlechaProjetil
        
        arma = self.dados.arma_obj
        if not arma:
            return
        
        dano = arma.dano * (self.dados.forca / 2.0 + 0.5)  # Dano base melhor
        forca = getattr(arma, 'forca_arco', 1.0)
        # Normaliza força do arco (valores no JSON são 5-50, queremos 0.5-2.0)
        forca_normalizada = max(0.5, min(2.0, forca / 25.0))
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (139, 90, 43)
        
        # === MIRA DIRETA NO ALVO (sem gravidade, sem complicação) ===
        dx = alvo.pos[0] - self.pos[0]
        dy = alvo.pos[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        
        if dist > 0.1:
            # Velocidade da flecha
            vel_flecha = 35.0 + forca_normalizada * 20.0
            tempo_voo = dist / vel_flecha
            
            # Predição simples: 70% da velocidade do alvo
            alvo_futuro_x = alvo.pos[0] + alvo.vel[0] * tempo_voo * 0.7
            alvo_futuro_y = alvo.pos[1] + alvo.vel[1] * tempo_voo * 0.7
            
            # Mira direto no alvo (sem compensação de gravidade - flecha voa reta!)
            dx_mira = alvo_futuro_x - self.pos[0]
            dy_mira = alvo_futuro_y - self.pos[1]
            angulo_mira = math.degrees(math.atan2(dy_mira, dx_mira))
        else:
            angulo_mira = self.angulo_olhar

        angulo_mira = self.get_angulo_mira(angulo_mira)
        
        # Imprecisão pequena (arqueiro é preciso!)
        angulo_mira += self.rng_runtime.uniform(-2, 2)
        
        # === SPAWN DA FLECHA: Sai do CORPO do arqueiro (não do range!) ===
        # A flecha nasce na beirada do corpo do arqueiro, na direção da mira
        rad = math.radians(angulo_mira)
        spawn_dist = self.raio_fisico + 0.3  # Logo na borda do corpo + pequena folga
        spawn_x = self.pos[0] + math.cos(rad) * spawn_dist
        spawn_y = self.pos[1] + math.sin(rad) * spawn_dist
        
        flecha = FlechaProjetil(
            x=spawn_x, y=spawn_y,
            angulo=angulo_mira,
            dono=self,
            dano=dano,
            forca=forca_normalizada,
            cor=cor
        )
        self.buffer_projeteis.append(flecha)

    def _disparar_orbes(self, alvo):
        """Dispara orbes mágicos"""
        from neural_fights.core.combat import OrbeMagico
        
        arma = self.dados.arma_obj
        if not arma:
            return
        
        qtd = int(getattr(arma, 'quantidade', 2))
        dano_por_orbe = arma.dano / max(qtd, 1)
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (100, 100, 255)
        
        orbes_orbitando = [o for o in self.buffer_orbes if o.ativo and o.estado == "orbitando"]
        
        if orbes_orbitando:
            for orbe in orbes_orbitando[:qtd]:
                orbe.iniciar_carga(alvo)
        else:
            for i in range(qtd):
                orbe = OrbeMagico(
                    x=self.pos[0], y=self.pos[1],
                    dono=self,
                    dano=dano_por_orbe * (self.dados.forca / 2.0 + self.dados.mana / 2.0),
                    indice=i,
                    total=qtd,
                    cor=cor
                )
                orbe.iniciar_carga(alvo)
                self.buffer_orbes.append(orbe)

    def _obter_partilha_link(self, dano):
        """Divide dano final de HP, sem aplicar novamente defesa ou status."""
        dano = max(0.0, dano)
        if self.link_alma_timer <= 0.0:
            return dano, None, 0.0

        parceiro = self.link_alma_alvo
        if parceiro is None or parceiro is self or getattr(parceiro, "morto", True):
            self.link_alma_timer = 0.0
            self.link_alma_alvo = None
            self.link_alma_percentual = 0.0
            return dano, None, 0.0

        percentual = min(1.0, max(0.0, self.link_alma_percentual))
        compartilhado = dano * percentual
        return dano - compartilhado, parceiro, compartilhado

    def aplicar_dano_direto(
        self,
        dano,
        *,
        compartilhar_link=True,
        flash_cor=(255, 100, 255),
        contexto_dano=None,
        ignorar_invulnerabilidade_skill=False,
    ):
        """Reduz HP sem defesa/recovery; invulnerabilidade segue absoluta."""
        if (
            self.morto
            or dano <= 0.0
            or (
                self.invulnerabilidade_skill_timer > 0.0
                and not ignorar_invulnerabilidade_skill
            )
        ):
            self.ultimo_dano_recebido = 0.0
            return 0.0

        dano_proprio = max(0.0, dano)
        parceiro = None
        dano_parceiro = 0.0
        if compartilhar_link:
            dano_proprio, parceiro, dano_parceiro = self._obter_partilha_link(dano_proprio)

        dano_proprio = self._limitar_dano_letal_por_imortalidade(dano_proprio)
        self.vida -= dano_proprio
        self.ultimo_dano_recebido = dano_proprio
        if dano_proprio > 0.0:
            self._quebrar_sono()
        self.flash_timer = min(0.25, 0.1 + dano_proprio * 0.005)
        self.flash_cor = flash_cor

        if parceiro is not None and dano_parceiro > 0.0:
            parceiro.aplicar_dano_direto(
                dano_parceiro,
                compartilhar_link=False,
                flash_cor=(255, 100, 255),
                contexto_dano=contexto_dano,
            )

        if self.vida <= 0.0:
            self.morrer(contexto_dano=contexto_dano)
        return dano_proprio

    def _receber_dano_link(self, dano):
        """Compatibilidade: recebe a parcela compartilhada sem nova partilha."""
        return self.aplicar_dano_direto(dano, compartilhar_link=False)

    def resolver_impacto(
        self,
        dano,
        empurrao_x,
        empurrao_y,
        tipo_efeito="NORMAL",
        atacante=None,
        aplicar_modificadores_debuff=True,
        duracao_efeito=None,
        raio_efeito=None,
        percentual_efeito=None,
        fonte_impacto=None,
        ignorar_invencibilidade=False,
        gerar_invencibilidade=True,
        ignorar_escudo=False,
        metadata_impacto=None,
        ignorar_recuperacao_impacto=None,
        gerar_recuperacao_impacto=None,
    ):
        """Aplica um impacto e retorna seu resultado sem depender de timers."""
        if ignorar_recuperacao_impacto is None:
            ignorar_recuperacao_impacto = ignorar_invencibilidade
        if gerar_recuperacao_impacto is None:
            gerar_recuperacao_impacto = gerar_invencibilidade
        self.tomar_dano(
            dano,
            empurrao_x,
            empurrao_y,
            tipo_efeito,
            atacante=atacante,
            aplicar_modificadores_debuff=aplicar_modificadores_debuff,
            duracao_efeito=duracao_efeito,
            raio_efeito=raio_efeito,
            percentual_efeito=percentual_efeito,
            fonte_impacto=fonte_impacto,
            ignorar_invencibilidade=ignorar_invencibilidade,
            gerar_invencibilidade=gerar_invencibilidade,
            ignorar_escudo=ignorar_escudo,
            metadata_impacto=metadata_impacto,
            ignorar_recuperacao_impacto=ignorar_recuperacao_impacto,
            gerar_recuperacao_impacto=gerar_recuperacao_impacto,
        )
        return self.ultimo_resultado_impacto

    def tomar_dano(
        self,
        dano,
        empurrao_x,
        empurrao_y,
        tipo_efeito="NORMAL",
        atacante=None,
        aplicar_modificadores_debuff=True,
        duracao_efeito=None,
        raio_efeito=None,
        percentual_efeito=None,
        fonte_impacto=None,
        ignorar_invencibilidade=False,
        gerar_invencibilidade=True,
        ignorar_escudo=False,
        metadata_impacto=None,
        ignorar_recuperacao_impacto=None,
        gerar_recuperacao_impacto=None,
    ):
        """Recebe dano com suporte a efeitos e reflexão"""

        if ignorar_recuperacao_impacto is None:
            ignorar_recuperacao_impacto = ignorar_invencibilidade
        if gerar_recuperacao_impacto is None:
            gerar_recuperacao_impacto = gerar_invencibilidade

        metadata_impacto = dict(metadata_impacto or {})
        contexto_dano = DamageContext.de_impacto(
            atacante,
            fonte_impacto,
            metadata_impacto,
        )
        self.ultimo_dano_recebido = 0.0
        if self.morto:
            self.ultimo_resultado_impacto = ImpactResult(False, bloqueado_por="morto")
            return False
        if self.intangivel or self.em_transicao_sombria():
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="intangibilidade",
            )
            return False
        if metadata_impacto.get("ground") and self.esta_imune_ground():
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="imunidade_ground",
            )
            return False
        chave_fonte = fonte_impacto
        if chave_fonte is not None:
            try:
                hash(chave_fonte)
            except TypeError:
                chave_fonte = ("id", id(chave_fonte))
        if chave_fonte is not None and chave_fonte in self._fontes_impacto_recentes:
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="fonte_duplicada",
            )
            return False
        if self.invulnerabilidade_skill_timer > 0:
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="invulnerabilidade_skill",
            )
            return False
        if self.invencivel_timer > 0 and not ignorar_recuperacao_impacto:
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="invencibilidade",
            )
            return False
        pode_atacar = getattr(atacante, "pode_causar_dano", None)
        if atacante is not None and atacante is not self and callable(pode_atacar):
            if not pode_atacar(self):
                self.ultimo_resultado_impacto = ImpactResult(
                    False,
                    bloqueado_por="controle_mental_atacante",
                )
                return False
        if (
            metadata_impacto.get("eh_skill")
            and not metadata_impacto.get("refletido")
            and atacante is not None
            and atacante is not self
            and not getattr(atacante, "morto", False)
            and self._consumir_reflexao_skill()
        ):
            metadata_refletida = dict(metadata_impacto)
            metadata_refletida["refletido"] = True
            resolver_reflexo = getattr(atacante, "resolver_impacto", None)
            if callable(resolver_reflexo):
                resolver_reflexo(
                    dano,
                    -empurrao_x,
                    -empurrao_y,
                    tipo_efeito,
                    atacante=self,
                    aplicar_modificadores_debuff=aplicar_modificadores_debuff,
                    duracao_efeito=duracao_efeito,
                    raio_efeito=raio_efeito,
                    percentual_efeito=percentual_efeito,
                    fonte_impacto=object(),
                    metadata_impacto=metadata_refletida,
                    ignorar_recuperacao_impacto=ignorar_recuperacao_impacto,
                    gerar_recuperacao_impacto=gerar_recuperacao_impacto,
                )
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="skill_refletida",
            )
            return False
        if chave_fonte is not None:
            self._fontes_impacto_recentes[chave_fonte] = 1.0

        bonus_vs_trevas = max(
            1.0,
            float(metadata_impacto.get("bonus_vs_trevas", 1.0)),
        )
        if bonus_vs_trevas > 1.0 and self.tem_afinidade_trevas():
            dano *= bonus_vs_trevas

        efeito_normalizado = normalizar_efeito(tipo_efeito)
        if efeito_normalizado == "BOMBA_RELOGIO":
            aplicado = self._aplicar_efeito_status(
                efeito_normalizado,
                duracao=duracao_efeito,
                origem=atacante,
                dano_efeito=dano,
                raio_efeito=raio_efeito,
                contexto_dano=contexto_dano,
            )
            self.ultimo_resultado_impacto = ImpactResult(
                atingiu=aplicado,
                efeito_aplicado=aplicado,
                bloqueado_por=None if aplicado else "efeito_rejeitado",
            )
            if aplicado:
                self.flash_timer = 0.2
                self.flash_cor = (255, 150, 0)
            return False

        if dano <= 0.0:
            aplicado = self._aplicar_efeito_status(
                efeito_normalizado,
                duracao=duracao_efeito,
                origem=atacante,
                percentual_efeito=percentual_efeito,
                contexto_dano=contexto_dano,
            )
            self.ultimo_resultado_impacto = ImpactResult(
                atingiu=True,
                efeito_aplicado=aplicado,
            )
            if aplicado:
                self.flash_timer = 0.15
            return False

        if (
            atacante is not None
            and atacante is not self
            and self._consumir_esquiva_prevista()
        ):
            self.ultimo_resultado_impacto = ImpactResult(
                False,
                bloqueado_por="previsao",
            )
            return False
        
        dano_final = dano

        # O dano recebido é o ponto comum entre golpes básicos e skills.
        # Modificadores de classe/buff já vieram calculados no valor de dano.
        if aplicar_modificadores_debuff:
            if atacante is not None:
                get_mod_causado = getattr(atacante, '_get_modificador_dano_causado_debuff', None)
                if callable(get_mod_causado):
                    dano_final *= get_mod_causado()
                elif getattr(atacante, 'fraco_timer', 0.0) > 0:
                    dano_final *= 0.7
            dano_final *= self._get_modificador_dano_recebido_debuff()

        for buff in self._buffs_validos():
            dano_final *= max(0.0, getattr(buff, "mod_dano_recebido", 1.0))
        
        if "Cavaleiro" in self.classe_nome:
            dano_final *= 0.75

        dano_final *= max(0.0, float(getattr(self, "mod_defesa", 1.0)))
        
        if "Ladino" in self.classe_nome and self.rng_runtime.random() < 0.2:
            self.ultimo_resultado_impacto = ImpactResult(False, bloqueado_por="esquiva")
            return False
        
        if not ignorar_escudo:
            for buff in self._buffs_validos():
                if buff.escudo_atual > 0:
                    dano_final = buff.absorver_dano(dano_final)

        if (
            metadata_impacto.get("eh_corpo_a_corpo")
            and atacante is not None
            and atacante is not self
            and not getattr(atacante, "morto", False)
        ):
            contato = sum(
                max(0.0, float(getattr(buff, "dano_contato", 0.0)))
                for buff in self._buffs_validos()
            )
            if contato > 0.0:
                contexto_contato = DamageContext(
                    atacante=self,
                    fonte=self,
                    metadata={"tipo_fonte": "retaliacao_corpo_a_corpo"},
                )
                aplicar_contato = getattr(atacante, "aplicar_dano_direto", None)
                if callable(aplicar_contato):
                    aplicar_contato(
                        contato,
                        compartilhar_link=True,
                        flash_cor=(255, 100, 50),
                        contexto_dano=contexto_contato,
                    )

        marca_ativa = bool(
            dano_final > 0.0
            and self.marcado
            and self.marcado_timer > 0.0
        )
        if marca_ativa:
            dano_final *= max(0.0, float(self.marcado_multiplicador))

        dano_final = self.aplicar_dano_direto(
            dano_final,
            compartilhar_link=True,
            flash_cor=(255, 255, 255),
            contexto_dano=contexto_dano,
        )
        if dano_final > 0.0 and atacante is not None and atacante is not self:
            consumir_buff = getattr(
                atacante,
                "_consumir_buffs_de_proximo_dano",
                None,
            )
            if callable(consumir_buff):
                consumir_buff()
        if marca_ativa and dano_final > 0.0:
            self._consumir_marca()
        
        # Reflexo de dano (Reflexo Espelhado)
        dano_refletido = 0
        for buff in self._buffs_validos():
            if hasattr(buff, 'refletir') and buff.refletir > 0:
                dano_refletido += dano_final * buff.refletir
        
        # Aplica dano refletido ao atacante pelo mesmo caminho de perda direta.
        if dano_refletido > 0 and atacante is not None and not atacante.morto:
            contexto_reflexo = DamageContext(
                atacante=self,
                fonte=self,
                metadata={"refletido": True, "tipo_fonte": "reflexo_dano"},
            )
            aplicar_reflexo = getattr(atacante, "aplicar_dano_direto", None)
            if callable(aplicar_reflexo):
                aplicar_reflexo(
                    dano_refletido,
                    compartilhar_link=True,
                    flash_cor=(200, 200, 255),
                    contexto_dano=contexto_reflexo,
                )
            else:
                atacante.vida -= dano_refletido
            atacante.flash_timer = 0.15
            atacante.flash_cor = (200, 200, 255)  # Flash azulado para reflexo
            if atacante.vida <= 0:
                atacante.morrer(contexto_dano=contexto_reflexo)

        if gerar_recuperacao_impacto:
            self.invencivel_timer = 0.3

        if atacante is not None and dano_final > 0.0 and not atacante.morto:
            get_buffs_atacante = getattr(atacante, "_buffs_validos", None)
            receber_cura_atacante = getattr(atacante, "receber_cura", None)
            if callable(get_buffs_atacante) and callable(receber_cura_atacante):
                lifesteal = sum(
                    max(0.0, getattr(buff, "lifesteal", 0.0))
                    for buff in get_buffs_atacante()
                )
                if lifesteal > 0.0:
                    receber_cura_atacante(dano_final * lifesteal)
        if (
            atacante is not None
            and not atacante.morto
            and metadata_impacto.get("rouba_buff")
        ):
            roubar = getattr(atacante, "_roubar_buff_do_alvo", None)
            if callable(roubar):
                roubar(self)
        
        # Flash de dano mais longo e visível (proporcional ao dano)
        self.flash_timer = min(0.25, 0.1 + dano_final * 0.005)
        
        # Cor do flash baseada no tipo de efeito
        self.flash_cor = {
            "NORMAL": (255, 255, 255),
            # Fogo
            "FOGO": (255, 150, 50),
            "QUEIMAR": (255, 100, 0),
            "QUEIMANDO": (255, 120, 20),
            # Gelo
            "GELO": (150, 220, 255),
            "CONGELAR": (100, 200, 255),
            "CONGELADO": (180, 230, 255),
            "LENTO": (150, 200, 255),
            # Natureza/Veneno
            "VENENO": (100, 255, 100),
            "ENVENENADO": (80, 220, 80),
            "NATUREZA": (100, 200, 50),
            # Sangue
            "SANGRAMENTO": (255, 50, 50),
            "SANGRANDO": (200, 30, 30),
            "SANGUE": (180, 0, 50),
            # Raio
            "RAIO": (255, 255, 100),
            "PARALISIA": (255, 255, 150),
            # Trevas
            "TREVAS": (150, 50, 200),
            "MALDITO": (100, 0, 150),
            "NECROSE": (50, 50, 50),
            "DRENAR": (120, 0, 150),
            # Luz
            "LUZ": (255, 255, 220),
            "CEGO": (255, 255, 200),
            # Arcano
            "ARCANO": (150, 100, 255),
            "SILENCIADO": (180, 150, 255),
            # Tempo
            "TEMPO": (200, 180, 255),
            "TEMPO_PARADO": (220, 200, 255),
            # Gravitação
            "GRAVITACAO": (100, 50, 150),
            "PUXADO": (120, 70, 180),
            "VORTEX": (80, 30, 130),
            # Caos
            "CAOS": (255, 100, 200),
            # CC
            "ATORDOAR": (255, 255, 100),
            "ATORDOADO": (255, 255, 100),
            "ENRAIZADO": (139, 90, 43),
            "MEDO": (150, 0, 150),
            "CHARME": (255, 150, 200),
            "SONO": (100, 100, 200),
            "KNOCK_UP": (200, 200, 255),
            # Debuffs
            "FRACO": (150, 150, 150),
            "VULNERAVEL": (255, 150, 150),
            "EXAUSTO": (100, 100, 100),
            "MARCADO": (255, 200, 50),
            "EXPOSTO": (255, 180, 100),
            "CORROENDO": (150, 100, 50),
            # Especiais
            "EXPLOSAO": (255, 200, 100),
            "EMPURRAO": (200, 200, 200),
            "BOMBA_RELOGIO": (255, 150, 0),
            "POSSESSO": (100, 0, 100),
        }.get(tipo_efeito, (255, 255, 255))
        
        if self.brain is not None:
            self.brain.raiva += 0.2
        
        # Knockback proporcional ao dano e vida restante
        kb = 15.0 + (1.0 - (self.vida/self.vida_max)) * 10.0
        kb += dano_final * 0.2  # Dano alto = mais knockback
        self.vel[0] += empurrao_x * kb
        self.vel[1] += empurrao_y * kb
        
        efeito_aplicado = False
        if not self.morto:
            efeito_aplicado = self._aplicar_efeito_status(
                tipo_efeito,
                duracao=duracao_efeito,
                origem=atacante,
                percentual_efeito=percentual_efeito,
                contexto_dano=contexto_dano,
            )
        
        if self.vida < self.vida_max * 0.3:
            self.modo_adrenalina = True
        
        morreu = self.morto or self.vida <= 0.0
        if morreu and not self.morto:
            self.morrer()
        self.ultimo_resultado_impacto = ImpactResult(
            atingiu=True,
            dano=dano_final,
            efeito_aplicado=efeito_aplicado,
            morreu=morreu,
        )
        return morreu

    def _aplicar_efeito_status(
        self,
        efeito,
        duracao=None,
        intensidade=1.0,
        origem=None,
        dano_efeito=None,
        raio_efeito=None,
        percentual_efeito=None,
        contexto_dano=None,
    ):
        """
        Aplica efeitos de status do dano - Sistema v2.0 COLOSSAL
        
        Args:
            efeito: Nome do efeito a aplicar
            duracao: Duração customizada (opcional)
            intensidade: Multiplicador de intensidade (default 1.0)
            origem: Lutador que originou efeitos que dependem de vínculo
            dano_efeito: Payload de dano para efeitos temporizados
            raio_efeito: Raio configurado pela fonte do efeito
            percentual_efeito: Fração configurada pela fonte do efeito
        """
        from neural_fights.core.combat import DotEffect

        if contexto_dano is None and origem is not None:
            contexto_dano = DamageContext(
                atacante=origem,
                metadata={"tipo_fonte": "status_direto"},
            )
        efeito = normalizar_efeito(efeito)
        if self.esta_imune_a_debuffs() and efeito_bloqueado_por_imunidade(efeito):
            return False
        definicao = get_status_runtime(efeito)
        duracao_padrao = get_duracao_padrao(efeito, 0.0)
        
        # =================================================================
        # DANOS AO LONGO DO TEMPO (DoT)
        # =================================================================
        if efeito == "ENVENENADO":
            dot = DotEffect(
                "ENVENENADO",
                self,
                definicao.get("dano_base", 1.5) * intensidade,
                duracao or duracao_padrao,
                (100, 255, 100),
                contexto_dano=contexto_dano,
            )
            self.dots_ativos.append(dot)
            
        elif efeito == "SANGRANDO":
            dot = DotEffect(
                "SANGRANDO",
                self,
                definicao.get("dano_base", 2.0) * intensidade,
                duracao or duracao_padrao,
                (180, 0, 30),
                contexto_dano=contexto_dano,
            )
            self.dots_ativos.append(dot)
            
        elif efeito == "QUEIMANDO":
            dot = DotEffect(
                "QUEIMANDO",
                self,
                definicao.get("dano_base", 2.5) * intensidade,
                duracao or duracao_padrao,
                (255, 100, 0),
                contexto_dano=contexto_dano,
            )
            self.dots_ativos.append(dot)
            
        elif efeito == "CORROENDO":
            # Corrosão: Dano + reduz defesa
            duracao_corrosao = duracao or duracao_padrao
            self._renovar_dot(
                "CORROENDO",
                definicao.get("dano_base", 1.5) * intensidade,
                duracao_corrosao,
                (150, 100, 50),
                contexto_dano=contexto_dano,
            )
            self.corroendo_timer = max(self.corroendo_timer, duracao_corrosao)
                
        elif efeito == "NECROSE":
            # Necrose: DoT que impede cura
            duracao_necrose = duracao or duracao_padrao
            self._renovar_dot(
                "NECROSE",
                definicao.get("dano_base", 3.0) * intensidade,
                duracao_necrose,
                (50, 50, 50),
                contexto_dano=contexto_dano,
            )
            self.cura_bloqueada_timer = max(
                self.cura_bloqueada_timer,
                duracao_necrose,
            )
            
        elif efeito == "MALDITO":
            # Maldição: DoT + dano recebido aumentado
            duracao_maldicao = duracao or duracao_padrao
            self._renovar_dot(
                "MALDITO",
                definicao.get("dano_base", 1.0) * intensidade,
                duracao_maldicao,
                (100, 0, 100),
                contexto_dano=contexto_dano,
            )
            self.maldito_timer = max(self.maldito_timer, duracao_maldicao)
            
        # =================================================================
        # CONTROLE DE GRUPO (CC)
        # =================================================================
        elif efeito == "CONGELADO":
            duracao_congelamento = duracao or duracao_padrao
            duracao_lentidao = duracao_congelamento + 1.0
            if self.congelado_timer <= 0:
                self._slow_fator_antes_congelado = self.slow_fator
            self.stun_timer = max(self.stun_timer, duracao_congelamento)
            self.slow_timer = max(self.slow_timer, duracao_lentidao)
            self.congelado_timer = max(self.congelado_timer, duracao_lentidao)
            self.slow_fator = min(self.slow_fator, 0.3)
            self.congelado = True
            
        elif efeito == "LENTO":
            self.slow_timer = max(self.slow_timer, duracao or duracao_padrao)
            self.slow_fator = min(self.slow_fator, 0.5 / intensidade)
            
        elif efeito == "ATORDOADO":
            self.stun_timer = max(self.stun_timer, (duracao or duracao_padrao) * intensidade)
            
        elif efeito == "PARALISIA":
            # Paralisia: Stun mais curto mas frequente
            self.stun_timer = max(self.stun_timer, (duracao or duracao_padrao) * intensidade)
            self.flash_cor = (255, 255, 100)
            self.flash_timer = 0.3
            
        elif efeito == "ENRAIZADO":
            # Enraizado: Não pode mover mas pode atacar
            if self.enraizado_timer <= 0:
                self._slow_fator_antes_enraizado = self.slow_fator
            self.enraizado_timer = max(self.enraizado_timer, duracao or duracao_padrao)
            self.slow_fator = 0.0  # Velocidade zero
            
        elif efeito == "SILENCIADO":
            # Silenciado: Não pode usar skills
            self.silenciado_timer = max(self.silenciado_timer, duracao or duracao_padrao)
            
        elif efeito == "CEGO":
            duracao_cegueira = duracao if duracao is not None else duracao_padrao
            if duracao_cegueira <= 0.0:
                return False
            self.cego_timer = max(self.cego_timer, duracao_cegueira)
            self.flash_cor = (255, 255, 200)
            self.flash_timer = 0.5
            
        elif efeito == "MEDO":
            duracao_medo = duracao if duracao is not None else duracao_padrao
            if duracao_medo <= 0.0:
                return False
            self.medo_timer = max(self.medo_timer, duracao_medo)
            self._interromper_acoes_ofensivas()
            
        elif efeito == "CHARME":
            # Charme: segue a origem e não a ataca enquanto durar.
            if (
                origem is None
                or origem is self
                or getattr(origem, "morto", True)
            ):
                return False
            duracao_charme = duracao if duracao is not None else duracao_padrao
            if duracao_charme <= 0.0:
                return False
            if self.charme_origem is origem:
                self.charme_timer = max(self.charme_timer, duracao_charme)
            else:
                self.charme_timer = duracao_charme
            self.charme_origem = origem
            self._interromper_acoes_ofensivas()
            
        elif efeito == "SONO":
            duracao_sono = duracao if duracao is not None else duracao_padrao
            if duracao_sono <= 0.0:
                return False
            self.dormindo = True
            self.sono_timer = max(self.sono_timer, duracao_sono)
            self._interromper_acoes_ofensivas()
            
        elif efeito == "KNOCK_UP":
            # Knock Up: Joga no ar
            self.vel_z = 12.0 * intensidade
            self.stun_timer = max(self.stun_timer, 0.5)
            
        elif efeito == "PUXADO":
            # Puxado: Atração gravitacional (implementado no efeito de área)
            if not hasattr(self, 'sendo_puxado'):
                self.sendo_puxado = False
            self.sendo_puxado = True
            
        elif efeito == "TEMPO_PARADO":
            # Tempo parado: Completamente imobilizado
            duracao_tempo_parado = duracao or duracao_padrao
            if self.tempo_parado_timer <= 0:
                self._slow_fator_antes_tempo_parado = self.slow_fator
            self.stun_timer = max(self.stun_timer, duracao_tempo_parado)
            self.tempo_parado_timer = max(self.tempo_parado_timer, duracao_tempo_parado)
            self.slow_fator = 0.0
            self.tempo_parado = True
            
        elif efeito == "VORTEX":
            # Vortex: Sendo puxado continuamente
            if not hasattr(self, 'em_vortex'):
                self.em_vortex = False
            self.em_vortex = True
        
        # =================================================================
        # DEBUFFS
        # =================================================================
        elif efeito == "FRACO":
            # Fraco: Dano reduzido
            self.fraco_timer = max(self.fraco_timer, duracao or duracao_padrao)
                
        elif efeito == "VULNERAVEL":
            # Vulnerável: Dano recebido aumentado
            self.vulneravel_timer = max(self.vulneravel_timer, duracao or duracao_padrao)
                
        elif efeito == "EXAUSTO":
            duracao_exaustao = duracao if duracao is not None else duracao_padrao
            if duracao_exaustao <= 0.0:
                return False
            self.exausto_timer = max(self.exausto_timer, duracao_exaustao)
            self.regen_mana_base = self.regen_mana_base_normal * definicao.get(
                "mod_regen_mana",
                0.3,
            )
            
        elif efeito == "MARCADO":
            duracao_marca = duracao if duracao is not None else duracao_padrao
            if duracao_marca <= 0.0:
                return False
            self.marcado = True
            self.marcado_timer = max(self.marcado_timer, duracao_marca)
            self.marcado_multiplicador = definicao.get(
                "mod_proximo_dano_recebido",
                1.5,
            )
            
        elif efeito == "EXPOSTO":
            # Exposto: Ignora parte da defesa
            self.exposto_timer = max(self.exposto_timer, duracao or duracao_padrao)
            
        # =================================================================
        # EFEITOS DE EMPURRÃO/MOVIMENTO
        # =================================================================
        elif efeito == "EMPURRAO":
            # Já tratado pelo knockback normal
            pass
            
        elif efeito == "EXPLOSAO":
            # Explosão já causa o knockback
            pass
        
        # =================================================================
        # EFEITOS ESPECIAIS
        # =================================================================
        elif efeito == "DRENAR":
            # Drenar: Já é tratado pelo lifesteal da skill
            pass
            
        elif efeito == "BOMBA_RELOGIO":
            # A aplicação apenas arma a marca; o dano nasce na expiração.
            if origem is None or origem is self:
                return False
            duracao_bomba = duracao if duracao is not None else duracao_padrao
            if duracao_bomba <= 0.0:
                return False
            self.bomba_relogio_timer = duracao_bomba
            self.bomba_relogio_dano = max(
                0.0,
                (80.0 if dano_efeito is None else dano_efeito) * intensidade,
            )
            self.bomba_relogio_raio = max(
                0.0,
                raio_efeito
                if raio_efeito is not None
                else definicao.get("raio_explosao", 2.5),
            )
            self.bomba_relogio_origem = origem
            
        elif efeito == "LINK_ALMA":
            # O alvo divide dano recebido pelo caminho central com a origem.
            if (
                origem is None
                or origem is self
                or getattr(origem, "morto", True)
            ):
                return False
            duracao_link = duracao if duracao is not None else duracao_padrao
            if duracao_link <= 0.0:
                return False
            if self.link_alma_alvo is origem:
                self.link_alma_timer = max(self.link_alma_timer, duracao_link)
            else:
                self.link_alma_timer = duracao_link
            self.link_alma_alvo = origem
            self.link_alma_percentual = min(
                1.0,
                max(
                    0.0,
                    (
                        percentual_efeito
                        if percentual_efeito is not None
                        else definicao.get("percentual_compartilhado", 0.5)
                    )
                    * intensidade,
                ),
            )
                
        elif efeito == "POSSESSO":
            # Em duelos autônomos, possessão suspende toda iniciativa do alvo.
            if (
                origem is None
                or origem is self
                or getattr(origem, "morto", True)
            ):
                return False
            duracao_possesso = duracao if duracao is not None else duracao_padrao
            if duracao_possesso <= 0.0:
                return False
            if self.possesso_origem is origem:
                self.possesso_timer = max(self.possesso_timer, duracao_possesso)
            else:
                self.possesso_timer = duracao_possesso
            self.possesso_origem = origem
            self._interromper_acoes_ofensivas()

        else:
            return False

        return True

    def tomar_clash(self, ex, ey):
        """Recebe impacto de clash de armas"""
        self.stun_timer = 0.5
        self.atacando = False
        self.vel[0] += ex * 25
        self.vel[1] += ey * 25

    def morrer(self, *, contexto_dano=None):
        """Processa morte do lutador"""
        if self.morto:
            return False
        if self._tentar_passiva_de_morte():
            return False

        transformacao = getattr(self, "transformacao_ativa", None)
        if transformacao is not None:
            encerrar = getattr(transformacao, "encerrar", None)
            if callable(encerrar):
                encerrar()
        self.transformacao_ativa = None
        self.interromper_canalizacao()
        self._transicao_sombria = None
        self.morto = True
        self.vida = 0
        self.cego_timer = 0.0
        self.medo_timer = 0.0
        self._quebrar_sono()
        self.marcado_timer = 0.0
        self.marcado = False
        self.exausto_timer = 0.0
        self.regen_mana_base = self.regen_mana_base_normal
        self.charme_timer = 0.0
        self.charme_origem = None
        self.possesso_timer = 0.0
        self.possesso_origem = None
        self.bomba_relogio_timer = 0.0
        self.bomba_relogio_dano = 0.0
        self.bomba_relogio_raio = 0.0
        self.bomba_relogio_origem = None
        self.link_alma_timer = 0.0
        self.link_alma_alvo = None
        self.link_alma_percentual = 0.0
        self.arma_droppada_pos = list(self.pos)
        self.arma_droppada_ang = self.angulo_arma_visual

        if contexto_dano is not None and contexto_dano.creditar_morte(self):
            atacante = contexto_dano.atacante
            notificar = getattr(atacante, "_notificar_morte_causada", None)
            if callable(notificar):
                notificar(self, contexto_dano)
        return True

    def get_pos_ponteira_arma(self):
        """Retorna posição da ponta da arma"""
        arma = getattr(self.dados, 'arma_obj', None)
        if not arma:
            return None
        
        if any(t in arma.tipo for t in ["Orbital", "Arremesso", "Mágica"]):
            return None
        
        rad = math.radians(self.angulo_arma_visual)
        ax, ay = int(self.pos[0] * PPM), int(self.pos[1] * PPM)
        
        if "Transformável" in arma.tipo:
            forma = getattr(arma, 'forma_atual', 1)
            if forma == 1:
                cabo_v = getattr(arma, 'forma1_cabo', arma.comp_cabo)
                lamina_v = getattr(arma, 'forma1_lamina', arma.comp_lamina)
            else:
                cabo_v = getattr(arma, 'forma2_cabo', arma.comp_cabo)
                lamina_v = getattr(arma, 'forma2_lamina', arma.comp_lamina)
            cabo_px = int(((cabo_v/100)*PPM) * self.fator_escala)
            lamina_px = int(((lamina_v/100)*PPM) * self.fator_escala)
        elif "Corrente" in arma.tipo:
            cabo_px = 0
            lamina_px = int(((getattr(arma, 'comp_corrente', 80)/100)*PPM) * self.fator_escala)
        else:
            cabo_px = int(((arma.comp_cabo/100)*PPM) * self.fator_escala)
            lamina_px = int(((arma.comp_lamina/100)*PPM) * self.fator_escala)
        
        xi = ax + math.cos(rad) * cabo_px
        yi = ay + math.sin(rad) * cabo_px
        xf = ax + math.cos(rad) * (cabo_px + lamina_px)
        yf = ay + math.sin(rad) * (cabo_px + lamina_px)
        return (xi, yi), (xf, yf)

    def get_escudo_info(self):
        """Retorna info do escudo orbital"""
        arma = getattr(self.dados, 'arma_obj', None)
        if not arma or "Orbital" not in arma.tipo:
            return None
        cx, cy = int(self.pos[0] * PPM), int(self.pos[1] * PPM)
        dist_base_px = int(((arma.distancia/100)*PPM)*self.fator_escala)
        raio_char_px = int((self.dados.tamanho/2)*PPM)
        return (cx, cy), dist_base_px + raio_char_px, self.angulo_arma_visual, arma.largura
    
    def get_dano_modificado(self, dano_base):
        """Retorna dano com todos os modificadores"""
        dano = dano_base * self.mod_dano
        
        for buff in self._buffs_validos():
            dano *= buff.buff_dano
        
        if "Berserker" in self.classe_nome:
            hp_pct = self.vida / self.vida_max
            dano *= 1.0 + (1.0 - hp_pct) * 0.5
        
        if "Assassino" in self.classe_nome and self.rng_runtime.random() < 0.25:
            dano *= 2.0
        
        return dano

    # =========================================================================
    # SISTEMA DE CHANNELING v8.0 (Para Classes Mágicas)
    # =========================================================================
    
    def pode_canalizar_magia(self) -> bool:
        """
        Verifica se o personagem pode canalizar magias.
        Apenas classes mágicas têm acesso ao channeling.
        """
        classes_magicas = ["Mago", "Piromante", "Criomante", "Necromante", "Feiticeiro"]
        return any(c in self.classe_nome for c in classes_magicas)
    
    def iniciar_canalizacao(self, skill_nome: str, skill_data: dict) -> bool:
        """
        Inicia a canalização de uma magia poderosa.
        
        Args:
            skill_nome: Nome da skill a ser canalizada
            skill_data: Dados da skill
            
        Returns:
            True se a canalização iniciou com sucesso
            
        Nota:
            O GameFeelManager gerencia o estado real da canalização.
            Este método apenas marca o lutador como "canalizando".
        """
        if not self.pode_canalizar_magia():
            return False
        
        # Marca estado de canalização no lutador
        self.canalizando = True
        self.skill_canalizando = skill_nome
        self.tempo_canalizacao = 0.0
        
        # O resto é gerenciado pelo GameFeelManager
        return True
    
    def interromper_canalizacao(self):
        """Interrompe a canalização atual"""
        channel = getattr(self, "channel_ativo", None)
        if channel is not None:
            interromper = getattr(channel, "interromper", None)
            if callable(interromper):
                interromper()
            self.channel_ativo = None
        self.canalizando = False
        self.skill_canalizando = None
        self.tempo_canalizacao = 0.0
    
    def atualizar_canalizacao(self, dt: float) -> dict:
        """
        Atualiza o estado de canalização.
        
        Returns:
            Dict com resultado se a magia foi liberada, None caso contrário
        """
        if not getattr(self, 'canalizando', False):
            return None
        
        self.tempo_canalizacao += dt
        
        # O GameFeelManager processa a lógica real
        # Este método apenas rastreia o tempo no lutador
        return None
    
    def get_progresso_canalizacao(self) -> float:
        """Retorna o progresso da canalização (0.0 a 1.0)"""
        if not getattr(self, 'canalizando', False):
            return 0.0
        
        # Tempo padrão de canalização varia por classe
        tempo_base = {
            "Mago (Arcano)": 1.5,
            "Piromante (Fogo)": 2.0,
            "Criomante (Gelo)": 1.2,
            "Necromante (Trevas)": 2.5,
            "Feiticeiro (Caos)": 1.0,
        }.get(self.classe_nome, 1.5)
        
        return min(1.0, getattr(self, 'tempo_canalizacao', 0.0) / tempo_base)


# Os atributos ``*_timer`` historicos sao uma visao sobre ``status_timers``.
# Instalar por descritor evita 20 pares de property manuais e garante que
# leitura e escrita passem sempre pelo container.
for _timer_attr, _status_id in STATUS_TIMER_ATTRS.items():
    setattr(Lutador, _timer_attr, _StatusTimerAttr(_status_id))
del _timer_attr, _status_id
