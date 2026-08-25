"""Percepção honesta da IA (Onda 8A).

Dois problemas históricos moram aqui:

1. O brain lia ``inimigo.buffer_projeteis`` para detectar perigo, mas o
   Simulador DRENA esses buffers para as listas do mundo antes do tick
   dos lutadores — a IA olhava para uma lista vazia. ``PercepcaoMundo``
   é uma janela estreita e somente-leitura sobre as listas vivas do
   Simulador, compartilhada pelos dois lutadores (mesma visão de mundo,
   sem assimetria p1/p2).

2. O brain lia ``inimigo.brain.acao_atual`` — telepatia. ``ObservacaoInimigo``
   é o que um espectador humano teria: posição, velocidade e a fase da
   animação de ataque (o telegraph público que sempre existiu em
   ``timer_animacao`` + ``WEAPON_PROFILES`` e nunca foi lido).

Este módulo é puro: sem RNG, sem mutação de estado do jogo. Latência e
má-leitura (a parte "humana" da percepção) são aplicadas pelo brain,
que possui o stream aleatório do lutador.
"""

import math
from dataclasses import dataclass


class PercepcaoMundo:
    """Janela somente-leitura sobre o mundo físico do Simulador.

    ``fonte`` é qualquer objeto com atributos ``projeteis``/``areas``/
    ``beams``/``arena`` (o Simulador real, ou um ``SimpleNamespace`` em
    teste). Ler via property elimina staleness: se o Simulador trocar a
    identidade de uma lista, a próxima leitura já vê a nova.
    """

    __slots__ = ("_fonte",)

    def __init__(self, fonte):
        self._fonte = fonte

    @property
    def projeteis(self):
        return getattr(self._fonte, "projeteis", None) or ()

    @property
    def areas(self):
        return getattr(self._fonte, "areas", None) or ()

    @property
    def beams(self):
        return getattr(self._fonte, "beams", None) or ()

    @property
    def arena(self):
        return getattr(self._fonte, "arena", None)

    def projeteis_hostis(self, lutador):
        """Projéteis ativos que não pertencem ao próprio lutador."""
        return [
            pr for pr in self.projeteis
            if getattr(pr, "ativo", True) and getattr(pr, "dono", None) is not lutador
        ]

    def areas_hostis(self, lutador):
        return [
            ar for ar in self.areas
            if getattr(ar, "ativo", True) and getattr(ar, "dono", None) is not lutador
        ]

    def beams_hostis(self, lutador):
        return [
            bm for bm in self.beams
            if getattr(bm, "ativo", True) and getattr(bm, "dono", None) is not lutador
        ]


# Fases observáveis de um golpe. Espelha exatamente a janela de hit do
# motor (core/hitbox.py:_verificar_janela_hit): antes da janela o golpe
# ainda NÃO conecta (dá para reagir), dentro conecta, depois é recovery.
FASE_PREPARANDO = "preparando"
FASE_GOLPEANDO = "golpeando"
FASE_RECUPERANDO = "recuperando"


def classificar_fase_ataque(alvo, arma_tipo):
    """Classifica a fase do golpe do alvo a partir do estado público.

    Retorna ``(fase, tempo_para_impacto, tempo_para_fim)`` — ou
    ``(None, None, None)`` se o alvo não está atacando. Tudo derivado de
    ``timer_animacao`` (conta de total_time até 0) e do perfil da arma.
    """
    if not getattr(alvo, "atacando", False):
        return None, None, None
    try:
        from neural_fights.effects.weapon_animations import WEAPON_PROFILES
        profile = WEAPON_PROFILES.get(arma_tipo, WEAPON_PROFILES.get("Reta"))
    except ImportError:
        profile = None
    timer = max(0.0, float(getattr(alvo, "timer_animacao", 0.0)))
    if profile is None or profile.total_time <= 0:
        return FASE_GOLPEANDO, 0.0, timer

    tempo_passado = max(0.0, profile.total_time - timer)
    janela_inicio = profile.anticipation_time * 0.5
    janela_fim = (
        profile.anticipation_time + profile.attack_time + profile.impact_time
        + profile.follow_through_time * 0.9
    )
    centro_impacto = (
        profile.anticipation_time + profile.attack_time + profile.impact_time * 0.5
    )
    tempo_para_impacto = max(0.0, centro_impacto - tempo_passado)
    if tempo_passado < janela_inicio:
        fase = FASE_PREPARANDO
    elif tempo_passado <= janela_fim:
        fase = FASE_GOLPEANDO
    else:
        fase = FASE_RECUPERANDO
    return fase, tempo_para_impacto, timer


@dataclass
class ObservacaoInimigo:
    """Leitura de um oponente feita só com estado fisicamente observável."""

    pos: tuple = (0.0, 0.0)
    vel: tuple = (0.0, 0.0)
    z: float = 0.0
    distancia: float = 999.0
    arma_tipo: str = None
    atacando: bool = False
    fase_ataque: str = None       # preparando | golpeando | recuperando | None
    tempo_para_impacto: float = None
    tempo_para_fim: float = None  # segundos até a animação acabar
    intencao: str = "parado"      # avancando|recuando|circulando|parado|armando_golpe|recuperando
    lado_circular: int = 0        # -1/+1: direção lateral observada (0 = sem strafe claro)
    vida_pct: float = 1.0
    estamina: float = 100.0
    stun_timer: float = 0.0
    canalizando: bool = False
    ataque_id: int = 0

    @property
    def agressivo(self):
        """Avançando ou com golpe em curso — o que 'pressão' significa a olho nu."""
        return self.atacando or self.intencao in ("avancando", "armando_golpe")


def construir_observacao(observador, inimigo, atraso_frames=0):
    """Monta a observação do ``inimigo`` do ponto de vista do ``observador``.

    ``atraso_frames`` simula latência de leitura: posição e velocidade
    são amostradas ``pos_historico`` frames atrás (o lutador reage ao que
    VIU, não ao que É). A fase de ataque não sofre atraso aqui — o brain
    aplica má-leitura por cima quando a habilidade de leitura é baixa.
    """
    obs = ObservacaoInimigo()
    # Fakes de contrato sem corpo físico: observação neutra, sem crash.
    if inimigo is None or not hasattr(inimigo, "pos") or observador is None \
            or not hasattr(observador, "pos"):
        return obs

    pos_x, pos_y = inimigo.pos[0], inimigo.pos[1]
    vel_ini = getattr(inimigo, "vel", (0.0, 0.0))
    vel_x, vel_y = vel_ini[0], vel_ini[1]
    if atraso_frames > 0:
        historico = getattr(inimigo, "pos_historico", None)
        if historico and len(historico) > atraso_frames + 1:
            pos_x, pos_y = historico[-1 - atraso_frames]
            ax, ay = historico[-2 - atraso_frames]
            # Velocidade aparente por diferença finita (historico é 1/frame).
            vel_x, vel_y = (pos_x - ax) * 60.0, (pos_y - ay) * 60.0

    obs.pos = (pos_x, pos_y)
    obs.vel = (vel_x, vel_y)
    obs.z = getattr(inimigo, "z", 0.0)
    obs.vida_pct = inimigo.vida / inimigo.vida_max if getattr(inimigo, "vida_max", 0) else 1.0
    obs.estamina = getattr(inimigo, "estamina", 100.0)
    obs.stun_timer = getattr(inimigo, "stun_timer", 0.0)
    obs.canalizando = bool(getattr(inimigo, "canalizando", False))
    obs.ataque_id = getattr(inimigo, "ataque_id", 0)
    obs.atacando = bool(getattr(inimigo, "atacando", False))

    arma = getattr(getattr(inimigo, "dados", None), "arma_obj", None)
    obs.arma_tipo = getattr(arma, "tipo", None)

    fase, t_impacto, t_fim = classificar_fase_ataque(inimigo, obs.arma_tipo)
    obs.fase_ataque = fase
    obs.tempo_para_impacto = t_impacto
    obs.tempo_para_fim = t_fim

    # --- Intenção aparente: velocidade decomposta na linha até o observador ---
    dx = observador.pos[0] - pos_x
    dy = observador.pos[1] - pos_y
    dist = math.hypot(dx, dy)
    obs.distancia = dist
    if dist > 1e-6:
        ux, uy = dx / dist, dy / dist
        aproximacao = vel_x * ux + vel_y * uy          # m/s na minha direção
        lateral = vel_x * (-uy) + vel_y * ux           # m/s perpendicular
        velocidade = math.hypot(vel_x, vel_y)
        if abs(lateral) > 0.5:
            obs.lado_circular = 1 if lateral > 0 else -1
        if fase == FASE_PREPARANDO:
            obs.intencao = "armando_golpe"
        elif fase == FASE_RECUPERANDO:
            obs.intencao = "recuperando"
        elif velocidade < 0.8:
            obs.intencao = "parado"
        elif aproximacao > 0.5 * velocidade:
            obs.intencao = "avancando"
        elif aproximacao < -0.5 * velocidade:
            obs.intencao = "recuando"
        else:
            obs.intencao = "circulando"
    return obs
