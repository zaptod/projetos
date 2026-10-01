# -*- coding: utf-8 -*-
"""Corrente V2 — bola física com momento (rework da corrente, 01/10/2026).

Antes daqui a corrente não tinha mecânica própria: o golpe era um setor
instantâneo centrado no olhar, igual ao da espada, e conectava no primeiro
tick da janela com a bola a 3,4–3,7 m do alvo (duelo_00030). Decisões do
Adrian (Grimório, 01/10): ``corrente-mecanica`` = bola física com momento;
``corrente-estilos`` = duas famílias (PESADAS com momento, LEVES com
enlace); ``corrente-seeds-antigas`` = chave só para lutas novas.

O que este módulo faz, com a chave ``CORRENTE_V2`` ligada:

* a bola tem posição e velocidade PRÓPRIAS, integradas em subpassos fixos
  (≤ 1/120 s) dentro do tick do motor, presa à mão pelo comprimento da
  corrente (restrição inextensível, inelástica);
* o braço guia a bola por um servo de ângulo (preparo → golpe → follow),
  com aceleração limitada — a bola atrasa, carrega momento e estica a
  corrente sozinha pela força centrífuga;
* acerto = o caminho que a bola VARREU no tick cruza o corpo do alvo, com
  velocidade mínima, dentro da fase de golpe do relógio do MOTOR
  (``timer_animacao``). Nada é lido do animador de arma;
* dano ∝ v² (normalizado pela velocidade nominal da própria arma, clamp
  0,6–1,4), empurrão na direção da bola, zona morta natural (perto demais
  a bola passa por fora do corpo);
* LEVES (Chicote, Kusarigama, Rope Dart) enlaçam: o alvo fica preso
  0,4–0,6 s e é puxado (``core/agarrao.py``).

Doutrina: sem RNG nenhum (nem do motor), estado só no lutador
(``corrente_bola``) e no Simulador (enlaces). Com a chave desligada nada
aqui é chamado — a luta antiga é idêntica bit a bit (há teste).

Campos do catálogo que eram mortos (``models/constants.py`` →
``TIPOS_ARMA["Corrente"]``): ``physics: "chain"`` é quem diz que a arma usa
esta bola (``eh_corrente``); ``mod_velocidade`` (0,8) escala a aceleração
do braço (``aceleracao_maxima``); ``mod_dano`` (1,1) segue SEM uso — o dano
da corrente já vem do ``dano`` da arma × v²; ligá-lo seria um buff de 10%
sem medida que o peça (ver ``docs/sessoes/builds.md``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

# ---------------------------------------------------------------- famílias

# Estilos com momento (bola pesada; o empurrão vai na direção da bola).
ESTILOS_PESADOS = ("Mangual", "Flail (Mangual)", "Meteor Hammer", "Corrente com Peso")
# Estilos com enlace (ponta leve; prende e puxa em vez de empurrar).
ESTILOS_LEVES = ("Chicote", "Kusarigama", "Rope Dart")

# Empunhadura da corrente — a MESMA de ``Simulador.GRIP_PROFILES["Corrente"]``
# e de ``recording.timeline.GRIP_PROFILES_PADRAO`` (há teste cobrando).
GRIP_OFFSET_R = 0.90
GRIP_LATERAL_R = 0.15
# Alcance do desenho/hitbox antigo, em raios do corpo (perfil "Corrente").
ALCANCE_LEGADO_R = 4.0

# ---------------------------------------------------------------- física

SUBPASSO_MAX_S = 1.0 / 120.0      # integração estável a qualquer dt do motor
ACEL_BASE = 1100.0                # m/s² do braço (antes de massa/mod_velocidade)
SERVO_KP = 900.0                  # rigidez do servo de ângulo (1/s²)
SERVO_KD = 55.0                   # amortecimento do servo (1/s)
RECOLHE_K = 260.0                 # mola radial quando o braço recolhe a corrente
RECOLHE_C = 22.0                  # amortecimento radial
ARRASTO = 1.2                     # atrito da bola com o ar/mão (1/s)
OMEGA_OCIOSO = 3.5                # giro de guarda (rad/s), sentido anti-horário
RAIO_OCIOSO_FRAC = 0.45           # corrente recolhida na guarda (fração de L)
RAIO_PREPARO_FRAC = 0.60          # no preparo
RAIO_BRACO_FRAC = 0.35            # alavanca mínima do braço (fração de L)
ENCURTA_MIN_FRAC = 0.50           # o braço encurta a corrente até 50% de L
ANG_PREPARO = math.radians(105.0) # a bola vai para trás do ombro
ANG_GOLPE = math.radians(125.0)   # e varre até passar da frente
V_REF_FRAC = 0.55                 # referência do v² (medida no corpus; ver velocidade_nominal)
V_MIN_FRAC = 0.45                 # fração da velocidade de referência para valer golpe
MULT_DANO_MIN = 0.6
MULT_DANO_MAX = 1.4


def chave_ligada(match_config=None) -> bool:
    """A chave da luta: ``match_config["corrente_v2"]`` vale sobre o padrão.

    O padrão é ``utils.config.CORRENTE_V2`` (False). Luta que não carimba a
    chave — todas as gravadas antes de 01/10/2026 — roda na corrente antiga.
    """
    if isinstance(match_config, Mapping) and "corrente_v2" in match_config:
        return bool(match_config.get("corrente_v2"))
    from neural_fights.utils.config import CORRENTE_V2

    return bool(CORRENTE_V2)


def eh_corrente(arma) -> bool:
    """A arma usa a bola? Lido do catálogo (``physics: "chain"``)."""
    if arma is None:
        return False
    from neural_fights.models.constants import TIPOS_ARMA

    tipo = str(getattr(arma, "tipo", "") or "")
    return (TIPOS_ARMA.get(tipo) or {}).get("physics") == "chain"


def familia(arma) -> str:
    """``"leve"`` (enlace) ou ``"pesada"`` (momento). Estilo novo cai em pesada."""
    estilo = str(getattr(arma, "estilo", "") or "")
    return "leve" if estilo in ESTILOS_LEVES else "pesada"


def v2_ativa(lutador) -> bool:
    return bool(getattr(lutador, "corrente_v2", False)) and eh_corrente(
        getattr(getattr(lutador, "dados", None), "arma_obj", None)
    )


# ---------------------------------------------------------------- geometria


def _real(valor, padrao: float) -> float:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return padrao
    return v if math.isfinite(v) else padrao


def raio_corpo(lutador) -> float:
    """Raio do círculo DESENHADO (tamanho/2) — o que o espectador vê."""
    return _real(getattr(getattr(lutador, "dados", None), "tamanho", 1.7), 1.7) / 2.0


def comprimento(arma, raio: float) -> float:
    """Corrente da mão ao centro da bola, em metros.

    Vem do banco (``comp_corrente + comp_ponta``, em cm), mapeado para
    2,6–3,6 raios: com a mão a 0,9 raio do centro, o alcance fica em
    3,5–4,5 raios (o desenho antigo era 4 raios fixos para toda corrente).
    """
    total = _real(getattr(arma, "comp_corrente", 80.0), 80.0) + _real(
        getattr(arma, "comp_ponta", 20.0), 20.0
    )
    frac = min(1.0, max(0.0, (total - 60.0) / 80.0))
    return raio * (2.6 + 1.0 * frac)


def raio_bola(arma, raio: float) -> float:
    """Raio da cabeça (bola/peso/ponta), pelo ``comp_ponta`` do banco."""
    ponta = _real(getattr(arma, "comp_ponta", 20.0), 20.0)
    return raio * min(0.38, max(0.12, 0.10 + ponta / 150.0))


def massa_relativa(arma) -> float:
    return min(1.6, max(0.4, _real(getattr(arma, "peso", 5.0), 5.0) / 5.0))


def aceleracao_maxima(lutador) -> float:
    """Força do braço: ``mod_velocidade`` do tipo, massa da cabeça e força."""
    from neural_fights.models.constants import TIPOS_ARMA

    dados = getattr(lutador, "dados", None)
    arma = getattr(dados, "arma_obj", None)
    mod_vel = _real((TIPOS_ARMA.get("Corrente") or {}).get("mod_velocidade", 1.0), 1.0)
    forca = _real(getattr(dados, "forca", 6.5), 6.5)
    return (
        ACEL_BASE * mod_vel
        * math.sqrt(max(0.3, forca / 6.5))
        / math.sqrt(massa_relativa(arma))
    )


def mao(lutador, angulo_graus: float | None = None) -> tuple[float, float]:
    """Ponto da empunhadura em metros (mesma conta do desenho da arma)."""
    raio = raio_corpo(lutador)
    ang = math.radians(
        _real(getattr(lutador, "angulo_olhar", 0.0), 0.0)
        if angulo_graus is None else angulo_graus
    )
    x = _real(lutador.pos[0], 0.0) + math.cos(ang) * raio * GRIP_OFFSET_R
    y = _real(lutador.pos[1], 0.0) + math.sin(ang) * raio * GRIP_OFFSET_R
    x += math.cos(ang + math.pi / 2) * raio * GRIP_LATERAL_R
    y += math.sin(ang + math.pi / 2) * raio * GRIP_LATERAL_R
    return x, y


def ponta_legada(lutador) -> tuple[float, float]:
    """Onde a corrente ANTIGA desenha a bola (``timeline.geometria_da_arma``).

    Só para MEDIR a linha de base: o golpe antigo não usa esta posição.
    """
    raio = raio_corpo(lutador)
    ang = math.radians(_real(getattr(lutador, "angulo_arma_visual", 0.0), 0.0))
    lunge = _real(getattr(lutador, "weapon_anim_lunge", 0.0), 0.0)
    distancia_grip = raio * GRIP_OFFSET_R
    desloc = distancia_grip + lunge * raio
    gx = _real(lutador.pos[0], 0.0) + math.cos(ang) * desloc
    gy = _real(lutador.pos[1], 0.0) + math.sin(ang) * desloc
    gx += math.cos(ang + math.pi / 2) * raio * GRIP_LATERAL_R
    gy += math.sin(ang + math.pi / 2) * raio * GRIP_LATERAL_R
    comp = max(raio * 0.35, raio * ALCANCE_LEGADO_R - distancia_grip)
    return gx + math.cos(ang) * comp, gy + math.sin(ang) * comp


def distancia_ponto_segmento(px, py, ax, ay, bx, by) -> tuple[float, float]:
    """(distância, t) do ponto P ao segmento AB; t ∈ [0, 1]."""
    dx, dy = bx - ax, by - ay
    comp2 = dx * dx + dy * dy
    if comp2 <= 1e-18:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / comp2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t


# ---------------------------------------------------------------- alcances


def alcances(lutador) -> dict[str, float]:
    """Distâncias centro-a-centro da corrente V2 (para a IA e o gatilho).

    ``morta``: abaixo disto a bola passa por fora do corpo (encurtada ao
    máximo); ``max``: o mais longe que a bola chega a tocar um corpo do
    mesmo tamanho; ``ideal``: o meio do anel, onde o golpe sai com a
    corrente quase toda.
    """
    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    raio = raio_corpo(lutador)
    comp = comprimento(arma, raio)
    rb = raio_bola(arma, raio)
    mao_d = raio * GRIP_OFFSET_R
    toque = raio + rb  # um corpo do mesmo tamanho
    morta = max(0.0, mao_d + comp * ENCURTA_MIN_FRAC - toque)
    maximo = mao_d + comp + toque * 0.85
    ideal = mao_d + comp * 0.85
    return {"morta": morta, "ideal": ideal, "max": maximo, "comprimento": comp}


def preparar_lutador(lutador) -> None:
    """Liga a corrente V2 no lutador (chamado pelo Simulador, com a chave).

    A IA passa a querer ficar no meio do anel que a bola alcança; o alcance
    antigo (raio físico × 4) deixava a corrente lutando dentro da zona morta.
    """
    lutador.corrente_v2 = True
    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    if not eh_corrente(arma):
        return
    alc = alcances(lutador)
    lutador.alcance_ideal = alc["ideal"]
    if "zona_morta_mangual" in getattr(lutador, "__dict__", {}):
        lutador.zona_morta_mangual = alc["morta"]


# ---------------------------------------------------------------- relógio


def _fases():
    """(preparo, golpe, follow, total) do relógio do MOTOR para a corrente.

    São as durações do perfil "Corrente" — as mesmas que o motor usa para
    ``timer_animacao`` (entities.executar_ataques). Constantes de dados; o
    estado do animador (transformações, shake) nunca é lido.
    """
    from neural_fights.effects.weapon_animations import WEAPON_PROFILES

    p = WEAPON_PROFILES["Corrente"]
    preparo = float(p.anticipation_time)
    golpe = float(p.attack_time + p.impact_time)
    follow = float(p.follow_through_time)
    return preparo, golpe, follow, float(p.total_time)


def velocidade_nominal(lutador) -> float:
    """Velocidade de referência do ``v²`` (m/s): o pico de um golpe limpo
    com a corrente em ``V_REF_FRAC`` do comprimento.

    Golpe nessa velocidade vale 1,0. A referência é MEDIDA, não escolhida:
    no corpus completo as lutas acontecem mais perto do que o meio do anel
    (o oponente fecha a distância), e com a referência em 85% o acerto
    mediano saía a 0,62 dela — 77% dos golpes no piso de 0,6 e a corrente
    caía para 38% de vitórias. Em 55%, o acerto mediano vale ~1,0: a
    corrente esticada bate até 1,4 e a encurtada, colada no alvo, 0,6
    (``ANG`` em ``golpe`` s, perfil suave: pico 1,5× a média).
    """
    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    comp = comprimento(arma, raio_corpo(lutador))
    _, golpe, _, _ = _fases()
    return 1.5 * (ANG_PREPARO + ANG_GOLPE) / max(golpe, 1e-6) * comp * V_REF_FRAC


def _suave(u: float) -> tuple[float, float]:
    """smoothstep e a derivada (em u)."""
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u), 6.0 * u * (1.0 - u)


def _wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


# ---------------------------------------------------------------- a bola


class BolaCorrente:
    """Estado da bola: posição, velocidade e o caminho varrido no tick."""

    __slots__ = (
        "x", "y", "vx", "vy", "trilha", "ataque_id", "sentido",
        "offset_inicial", "comprimento_ef", "ultimo_contato", "mao_ant",
    )

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.trilha: list[tuple[float, float, float, float]] = []
        self.ataque_id = None
        self.sentido = 1.0
        self.offset_inicial = 0.0
        self.comprimento_ef = None
        self.ultimo_contato = None
        self.mao_ant = None

    def velocidade(self) -> float:
        return math.hypot(self.vx, self.vy)


def bola_de(lutador):
    """A bola do lutador (criada na guarda, ao lado da mão), ou None."""
    bola = lutador.__dict__.get("corrente_bola") if hasattr(lutador, "__dict__") else None
    if bola is None:
        arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
        raio = raio_corpo(lutador)
        comp = comprimento(arma, raio)
        hx, hy = mao(lutador)
        ang = math.radians(_real(getattr(lutador, "angulo_olhar", 0.0), 0.0)) - math.pi / 2
        bola = BolaCorrente(
            hx + math.cos(ang) * comp * RAIO_OCIOSO_FRAC,
            hy + math.sin(ang) * comp * RAIO_OCIOSO_FRAC,
        )
        bola.mao_ant = (hx, hy)
        lutador.corrente_bola = bola
    return bola


def _decorrido(lutador, total: float) -> float | None:
    if not getattr(lutador, "atacando", False):
        return None
    return total - _real(getattr(lutador, "timer_animacao", 0.0), 0.0)


def atualizar_bola(lutador, inimigo, dt: float) -> BolaCorrente | None:
    """Avança a bola um tick do motor (subpassos fixos). Puro: sem RNG."""
    dt = _real(dt, 0.0)
    bola = bola_de(lutador)
    bola.trilha = []
    bola.ultimo_contato = None
    if dt <= 0.0:
        return bola

    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    raio = raio_corpo(lutador)
    comp = comprimento(arma, raio)
    a_max = aceleracao_maxima(lutador)
    preparo, golpe, follow, total = _fases()
    phi = math.radians(_real(getattr(lutador, "angulo_olhar", 0.0), 0.0))
    hx1, hy1 = mao(lutador)
    hx0, hy0 = bola.mao_ant if bola.mao_ant is not None else (hx1, hy1)

    decorrido = _decorrido(lutador, total)
    ataque_id = getattr(lutador, "ataque_id", 0)
    if decorrido is not None and ataque_id != bola.ataque_id:
        # Golpe novo: forehand/backhand alternam (estado do motor, sem RNG);
        # o preparo parte de onde a bola está, relativo ao olhar.
        bola.ataque_id = ataque_id
        bola.sentido = 1.0 if int(ataque_id) % 2 else -1.0
        bola.offset_inicial = _wrap(math.atan2(bola.y - hy0, bola.x - hx0) - phi)
        bola.comprimento_ef = None

    # O braço encurta a corrente para o alvo que está perto (até 50%).
    comp_ef = comp
    if decorrido is not None and decorrido < preparo + golpe and inimigo is not None:
        d_alvo = math.hypot(inimigo.pos[0] - hx1, inimigo.pos[1] - hy1)
        comp_ef = min(comp, max(comp * ENCURTA_MIN_FRAC, d_alvo))
        bola.comprimento_ef = comp_ef
    elif decorrido is not None and bola.comprimento_ef is not None:
        comp_ef = bola.comprimento_ef

    passos = max(1, int(math.ceil(dt / SUBPASSO_MAX_S - 1e-9)))
    h = dt / passos
    vhx, vhy = (hx1 - hx0) / dt, (hy1 - hy0) / dt
    s = bola.sentido
    for k in range(1, passos + 1):
        f = k / passos
        hx, hy = hx0 + (hx1 - hx0) * f, hy0 + (hy1 - hy0) * f
        e = None if decorrido is None else decorrido - dt + h * k
        rx, ry = bola.x - hx, bola.y - hy
        r = math.hypot(rx, ry)
        if r < 1e-6:
            rx, ry, r = math.cos(phi), math.sin(phi), 1e-6
        erx, ery = rx / r, ry / r
        etx, ety = -ery, erx
        relx, rely = bola.vx - vhx, bola.vy - vhy
        v_t = relx * etx + rely * ety
        v_r = relx * erx + rely * ery
        theta = math.atan2(ry, rx)

        alvo_ang = None
        if e is None or e >= preparo + golpe + follow:
            omega_alvo, r_alvo = OMEGA_OCIOSO, comp * RAIO_OCIOSO_FRAC
            if e is not None:  # recuperação: freia até a guarda
                omega_alvo = 0.0
        elif e < preparo:
            u = max(0.0, e) / max(preparo, 1e-6)
            sv, dsv = _suave(u)
            inicio = phi + bola.offset_inicial
            fim = phi - s * ANG_PREPARO
            delta = _wrap(fim - inicio)
            alvo_ang = inicio + delta * sv
            omega_alvo = delta * dsv / max(preparo, 1e-6)
            r_alvo = comp * RAIO_PREPARO_FRAC
        elif e < preparo + golpe:
            u = (e - preparo) / max(golpe, 1e-6)
            sv, dsv = _suave(u)
            arco = ANG_PREPARO + ANG_GOLPE
            alvo_ang = phi - s * ANG_PREPARO + s * arco * sv
            omega_alvo = s * arco * dsv / max(golpe, 1e-6)
            r_alvo = comp_ef  # solta: a centrífuga estica a corrente
        else:  # follow: a bola segue no embalo e o braço recolhe
            omega_alvo = s * OMEGA_OCIOSO
            r_alvo = comp * RAIO_OCIOSO_FRAC

        # O braço gira a bola com a mão: mesmo com a corrente recolhida ele
        # dá velocidade tangencial (braço de alavanca mínimo), e a centrífuga
        # leva a bola para fora sozinha.
        r_braco = max(r, comp * RAIO_BRACO_FRAC)
        a_t = SERVO_KD * (omega_alvo * r_braco - v_t)
        if alvo_ang is not None:
            a_t += SERVO_KP * _wrap(alvo_ang - theta) * r_braco
        a_t = max(-a_max, min(a_max, a_t))
        if r > r_alvo:
            # recolhe: puxa a corrente (só puxa; corrente não empurra)
            a_r = -RECOLHE_K * (r - r_alvo) - RECOLHE_C * v_r
        else:
            # folga: a mão vai tomando a folga, a bola não cai na mão
            a_r = -RECOLHE_C * min(0.0, v_r)
        a_r = max(-a_max, min(a_max, a_r))
        ax = a_t * etx + a_r * erx - ARRASTO * relx
        ay = a_t * ety + a_r * ery - ARRASTO * rely

        x0, y0 = bola.x, bola.y
        bola.vx += ax * h
        bola.vy += ay * h
        bola.x += bola.vx * h
        bola.y += bola.vy * h

        # Corrente inextensível no comprimento em uso: segura e mata a
        # componente radial para fora (corrente não estica nem quica).
        limite = comp_ef if e is not None and e < preparo + golpe else comp
        rx, ry = bola.x - hx, bola.y - hy
        r = math.hypot(rx, ry)
        if r > limite:
            erx, ery = rx / r, ry / r
            bola.x, bola.y = hx + erx * limite, hy + ery * limite
            relx, rely = bola.vx - vhx, bola.vy - vhy
            v_r = relx * erx + rely * ery
            if v_r > 0.0:
                bola.vx -= v_r * erx
                bola.vy -= v_r * ery
        bola.trilha.append((x0, y0, bola.x, bola.y))

    bola.mao_ant = (hx1, hy1)
    # O olhar da arma aponta para a bola: o desenho/timeline de hoje passa
    # a mostrar onde ela está (estado de exibição; o golpe não o lê).
    lutador.angulo_arma_visual = math.degrees(math.atan2(bola.y - hy1, bola.x - hx1))
    return bola


def janela_de_golpe(lutador) -> bool:
    """O relógio do MOTOR está na fase de golpe (fim do preparo ao follow)?"""
    preparo, golpe, follow, total = _fases()
    e = _decorrido(lutador, total)
    return e is not None and preparo <= e <= preparo + golpe + follow


def verificar_golpe(atacante, defensor) -> tuple[bool, str]:
    """Acerto V2: a bola varreu o corpo do alvo neste tick, rápida o bastante.

    Guarda o contato em ``bola.ultimo_contato`` (ponto, velocidade e
    multiplicador de dano) para o Simulador aplicar dano e empurrão.
    """
    if not getattr(atacante, "atacando", False):
        return False, "não está atacando"
    if not janela_de_golpe(atacante):
        return False, "fora da fase de golpe"
    bola = atacante.__dict__.get("corrente_bola")
    if bola is None or not bola.trilha:
        return False, "bola sem trajetória neste tick"
    arma = getattr(getattr(atacante, "dados", None), "arma_obj", None)
    alcance_toque = raio_corpo(defensor) + raio_bola(arma, raio_corpo(atacante))
    px, py = float(defensor.pos[0]), float(defensor.pos[1])
    melhor = None
    for ax, ay, bx, by in bola.trilha:
        dist, t = distancia_ponto_segmento(px, py, ax, ay, bx, by)
        if dist <= alcance_toque and (melhor is None or dist < melhor[0]):
            melhor = (dist, ax + (bx - ax) * t, ay + (by - ay) * t)
    if melhor is None:
        return False, "a bola não passou pelo corpo"
    dvx = bola.vx - _real(defensor.vel[0], 0.0)
    dvy = bola.vy - _real(defensor.vel[1], 0.0)
    v_rel = math.hypot(dvx, dvy)
    v_ref = velocidade_nominal(atacante)
    if v_rel < V_MIN_FRAC * v_ref:
        return False, f"bola lenta (v={v_rel:.1f} < {V_MIN_FRAC * v_ref:.1f} m/s)"
    mult = min(MULT_DANO_MAX, max(MULT_DANO_MIN, (v_rel / max(v_ref, 1e-6)) ** 2))
    vb = bola.velocidade()
    direcao = math.atan2(bola.vy, bola.vx) if vb > 1e-6 else math.atan2(
        py - atacante.pos[1], px - atacante.pos[0])
    bola.ultimo_contato = {
        "ponto": (melhor[1], melhor[2]),
        "folga_m": melhor[0] - alcance_toque,
        "v": v_rel,
        "v_ref": v_ref,
        "mult": mult,
        "direcao": direcao,
        "familia": familia(arma),
    }
    return True, f"bola acertou (v={v_rel:.1f} m/s, x{mult:.2f})"


def contato_do_golpe(atacante):
    bola = atacante.__dict__.get("corrente_bola") if hasattr(atacante, "__dict__") else None
    return None if bola is None else bola.ultimo_contato


# ---------------------------------------------------------------- medida


def medir_contato(atacante, defensor) -> dict:
    """No acerto: a bola/ponta estava encostada no corpo do alvo?

    V2: o caminho varrido no tick (o mesmo do acerto). Antiga: a ponta que
    o desenho mostra (``ponta_legada``). ``folga_m`` > 0 = longe do corpo.
    Só lê estado — a sonda pode chamar sem mudar a luta.
    """
    arma = getattr(getattr(atacante, "dados", None), "arma_obj", None)
    toque = raio_corpo(defensor) + raio_bola(arma, raio_corpo(atacante))
    px, py = float(defensor.pos[0]), float(defensor.pos[1])
    contato = contato_do_golpe(atacante) if v2_ativa(atacante) else None
    mult = v_ref = None
    if contato is not None:
        folga = float(contato["folga_m"])
        v = float(contato["v"])
        mult = float(contato["mult"])
        v_ref = float(contato["v_ref"])
    else:
        bx, by = ponta_legada(atacante)
        folga = math.hypot(px - bx, py - by) - toque
        v = None
    return {"contato": folga <= 1e-6, "folga_m": folga, "v": v, "mult": mult, "v_ref": v_ref,
            "distancia_m": math.hypot(px - atacante.pos[0], py - atacante.pos[1]),
            "v2": contato is not None}


__all__ = [
    "BolaCorrente",
    "ESTILOS_LEVES",
    "ESTILOS_PESADOS",
    "alcances",
    "atualizar_bola",
    "bola_de",
    "chave_ligada",
    "comprimento",
    "contato_do_golpe",
    "eh_corrente",
    "familia",
    "janela_de_golpe",
    "medir_contato",
    "ponta_legada",
    "preparar_lutador",
    "raio_bola",
    "velocidade_nominal",
    "verificar_golpe",
    "v2_ativa",
]
