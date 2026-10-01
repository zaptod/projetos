# -*- coding: utf-8 -*-
"""Timeline v1: o contrato entre a simulacao e o palco (Onda 16C).

O palco (Godot, Onda 16D) desenha a luta SO a partir deste arquivo. A
simulacao nunca depende dele e ele nunca decide nada da luta: tudo o que o
motor sabia em cada passo de 60 Hz sai daqui, em metros, graus e segundos.
O schema completo, com a justificativa de cada escolha, esta em
``docs/palco/timeline.md``; a leitura e a gravacao em disco (JSON e o
container comprimido que o Godot abre nativo) em ``timeline_arquivo.py``.

Resumo do documento (``SondaTimeline.documento()``):

- ``trilhas.lutadores.p1/p2``  um canal por campo e um valor por PASSO do
                               motor: posicao, altura, angulo, hp, expressao
                               (as 24), acao da IA, plano, golpe (fase,
                               progresso e duracao pelo RELOGIO DO MOTOR) e a
                               geometria honesta da arma (empunhadura e ponta
                               com o mesmo alcance da hitbox).
- ``trilhas.objetos``          projeteis, orbes, areas, beams, summons, traps
                               e portais: cada um vive num intervalo [i0, i1]
                               de passos e traz os canais so nesse intervalo.
- ``trilhas.efeitos``          status, buffs, canalizacao e transformacao, no
                               mesmo formato de intervalo.
- ``trilhas.camera``           a camera (DIRETOR no video): centro e largura
                               visivel em metros.
- ``trilhas.global``           tempo de jogo, escala (slow-mo), hit-stop,
                               letterbox.
- ``eventos``                  acerto (com tier), bloqueio, parry, esquiva,
                               agarrao e desfecho, parede, KO, skill, combo,
                               virada... e, na revisao 3, o que o render
                               acendia: fim de projetil com o motivo,
                               explosao, choque, reflexao, texto flutuante,
                               movimento e o ponto do acerto por projetil
                               (lidos das listas de VFX, por identidade).
- ``sons``                     o formato da Onda 16A (``docs/palco/sons.md``),
                               preenchida pelo anotador de som quando a luta
                               roda com ele (gravador e ``gravar_timeline``).
- ``remapeamento``             corte de tedio e camera lenta, em trechos
                               ``[inicio, duracao, velocidade]``.

A sonda so LE
-------------
``SondaTimeline`` segue a doutrina das sondas do projeto (``probes.py``,
``fight_recorder.SondaNarrativa``) e vai alem delas:

- nunca chama ``desenhar()``, ``arena.limpar_colisoes()``,
  ``get_weapon_transform()``, ``animator.get_state()`` (que cria entrada) nem
  a property ``brain.humor`` num cerebro sem motor emocional (que o CRIA);
- nunca instala nada no jogo: o ``registro_eventos_dano`` do lutador e da
  ``SondaDeDano`` do gravador. Os eventos daqui saem por TRANSICAO (contador
  que subiu, vida que caiu, cooldown que saltou), com a lembranca guardada na
  propria sonda;
- ``getattr`` tolerante em tudo: fakes de contrato (``object.__new__``,
  ``SimpleNamespace``) nao derrubam a sonda, e campo ausente vira valor
  neutro.

O teste que sustenta isso compara um HASH DE ESTADO POR PASSO (``hash_estado``)
com e sem a sonda: ``tests/test_timeline_palco_regressions.py``.

Ordem no laco de quem grava: ``on_frame`` logo depois de ``sim.update()`` e
ANTES de ``sim.desenhar()``. O ``desenhar()`` esvazia
``arena.colisoes_recentes``; chamada depois dele, a sonda perde os impactos de
parede comuns (os wall-splats continuam, porque vem de contador).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import weakref
from pathlib import Path

FORMATO = "neural-fights/timeline"
VERSAO = 1
# Revisao ADITIVA dentro da v1: leitor da v1 continua valendo (o palco recusa
# versao != 1). 2 = cada som traz o passo exato ``i`` (28/09/2026). 3 = os
# eventos que o render acendia e a v1 nao dizia: fim de projetil com o motivo,
# explosao, choque, reflexao, texto flutuante e movimento, e o PONTO do
# impacto no acerto por projetil (28/09/2026). 4 = a bola da corrente nova
# (CORRENTE_V2): canais ``bola_*`` e o cabecalho ``arma.corrente`` de quem
# luta com ela (01/10/2026).
REVISAO = 4
# O motor pensa a 60 Hz (utils.config.FPS). A timeline guarda TODO passo:
# o quadro k do video de 30 fps e o passo 2k, e o palco ainda tem o dobro de
# amostras para camera lenta sem inventar quadro. Ver docs/palco/timeline.md.
HZ = 60
# Pixels do motor por metro (utils.config.PPM). Tudo na timeline sai em
# metros; o numero fica no cabecalho so para quem quiser conferir a conversao.
PPM = 50

# Indice 0 = sem golpe; os demais sao os valores de
# effects.weapon_animations.AttackPhase, na ordem em que acontecem.
FASES = ("", "anticipation", "attack", "impact", "follow", "recovery")

# Bit n do canal ``flags`` = FLAGS[n]. Acrescentar no FIM nao muda a versao.
FLAGS = (
    "atacando",      # 0  golpe em curso (lutador.atacando)
    "morto",         # 1
    "atordoado",     # 2  stun_timer > 0
    "congelado",     # 3
    "invencivel",    # 4  i-frames pos-impacto ou invulnerabilidade de skill
    "canalizando",   # 5
    "adrenalina",    # 6  modo_adrenalina (contorno pulsando no render atual)
    "agarrado",      # 7  agarrao_timer > 0 (lock do agarrao, os dois lados)
    "dash",          # 8  dash_timer > 0
    "intangivel",    # 9
    "super_armor",   # 10 game_feel.super_armor_systems[l].data.ativo
    "bloqueando",    # 11 acao da IA == BLOQUEAR
    "tempo_parado",  # 12
    "dormindo",      # 13
    "transformado",  # 14 transformacao_ativa viva
    "lancado",       # 15 lancado_timer > 0 (bater na parede agora estatela)
    "oculto",        # 16 em transicao sombria (portal): o render nao desenha
    "no_ar",         # 17 z > 1 cm
)

# As 24 expressoes de effects/character_flair.EXPRESSOES, na ordem de la. O
# canal ``expr`` e um indice aqui. Ha teste cobrando que a lista e a do jogo.
EXPRESSOES = (
    "neutro", "focado", "glacial", "determinado", "furia", "berserk",
    "confiante", "animado", "euforico", "extase", "panico", "nervoso",
    "desespero", "tedio", "tristeza", "morto", "tonto", "dor", "esforco",
    "firmeza", "alerta", "confuso", "limite", "concentrado",
)

ESTADOS_ORBE = ("orbitando", "carregando", "disparando")

# Tier de impacto do atacante (effects/attack.py: LIMIARES_FORCA). E o tier
# que o render usa para o tamanho da onda de choque do corpo-a-corpo.
TIERS = ("light", "medium", "heavy", "colossal")

# Virada de lideranca: os MESMOS numeros e a mesma cadencia da SondaNarrativa
# do gravador, para a legenda publicada e o palco contarem a mesma historia.
IGNORAR_LIDERANCA_ATE = 3.0
HISTERESE_LIDERANCA = 0.05
PASSO_LIDERANCA = 0.25

# Categorias de dano que nao sao golpe (DoT, encanto, retaliacao...). Mesmo
# criterio do contador ``hits_sofridos`` do Lutador (entities.py).
_CATEGORIAS_SEM_GOLPE = ("dot", "encant", "retaliacao")

# ---------------------------------------------------------------- revisao 3
# Por que um projetil (ou orbe) deixou de existir. A ORDEM e a da decisao:
# o primeiro sinal que bate vence (ver SondaTimeline._motivo_do_fim).
MOTIVOS_FIM = ("choque", "explodiu", "expirou", "voltou", "trap", "acerto",
               "bloqueado", "sumiu")
DEFESAS = ("escudo", "parry", "dash")
# O que disparou os VFX de movimento de um lutador num passo
# (simulacao._detectar_eventos_movimento e o knockback dos golpes).
GATILHOS_MOVIMENTO = ("dash", "knockback", "recuperacao", "aterrissagem", "pulo",
                      "corrida", "poeira")
VFX_MOVIMENTO = ("afterimage", "blur", "linhas", "poeira", "recuperacao")
ESTILOS_TEXTO = ("dano", "execucao", "fatal", "cura", "clash", "outro")
# Cores que o motor usa como SINAL (simulacao.py): o numero roxo da execucao
# (bonus de condicao >= 5), o FATAL! da execucao e as linhas do knockback.
COR_EXECUCAO = (200, 110, 255)
COR_FATAL_EXECUCAO = (190, 90, 255)
COR_LINHAS_KNOCKBACK = (255, 200, 150)
# Folga de distancia (m) ao casar um VFX com o projetil que o causou: o VFX
# nasce onde o projetil estava DEPOIS de andar neste passo, e a sonda so tem
# a amostra do passo anterior quando o objeto ja morreu.
FOLGA_M = 0.35
# As listas de VFX lidas por identidade: (nome, caminho a partir do sim).
_LISTAS_VFX = (
    ("flash", ("impact_flashes",)),
    ("choque", ("magic_clashes",)),
    ("bloqueio", ("block_effects",)),
    ("explosao", ("magic_vfx", "explosions")),
    ("afterimage", ("movement_anims", "afterimage_trails")),
    ("blur", ("movement_anims", "motion_blurs")),
    ("linhas", ("movement_anims", "speed_lines")),
    ("poeira", ("movement_anims", "dust_clouds")),
    ("recuperacao", ("movement_anims", "recovery_flashes")),
)
# Campos obrigatorios dos eventos da revisao 3 (o schema em codigo; o palco
# confere os mesmos em nucleo/timeline.gd).
CAMPOS_EVENTOS_R3 = {
    "projetil_fim": ("id", "objeto", "motivo", "x", "y"),
    "explosao": ("x", "y", "origem"),
    "choque": ("x", "y", "origem"),
    "refletido": ("id", "de", "para", "x", "y"),
    "texto": ("texto_id", "texto", "estilo", "x", "y"),
    "movimento": ("gatilho", "vfx", "x", "y"),
}

# Canais por lutador: (nome, unidade, significado). A ORDEM e a do documento.
CANAIS_LUTADOR = (
    ("x", "m", "posicao no chao; x cresce para a direita"),
    ("y", "m", "posicao no chao; y cresce para baixo, como no motor"),
    ("z", "m", "altura do pulo; o render desenha o corpo em (x, y - z)"),
    ("ang", "graus", "para onde o lutador olha (angulo_olhar)"),
    ("vx", "m/s", "velocidade no chao"),
    ("vy", "m/s", "velocidade no chao"),
    ("hp", "0..1", "vida / vida_max"),
    ("mp", "0..1", "mana / mana_max"),
    ("est", "0..1", "estamina / estamina_max"),
    ("expr", "indice", "tabelas.expressoes (as 24)"),
    ("acao", "indice", "tabelas.acoes: brain.acao_atual"),
    ("plano", "indice", "tabelas.planos: plano de luta vivo; -1 sem plano"),
    ("plano_p", "0..1", "progresso do plano"),
    ("tell", "indice", "tabelas.tells: sinal publico ativo; -1 nenhum"),
    ("flags", "bits", "bit n = tabelas.flags[n]"),
    ("golpe_fase", "indice", "tabelas.fases pelo RELOGIO DO MOTOR; 0 = sem golpe"),
    ("golpe_p", "0..1", "progresso dentro da fase"),
    ("golpe_d", "s", "duracao da fase atual"),
    ("golpe_id", "int", "ataque_id: muda a cada golpe novo"),
    ("golpe_janela", "0/1", "o golpe pode conectar agora (janela da hitbox)"),
    ("anim_fase", "indice", "fase do ANIMADOR visual (perfil do estilo)"),
    ("anim_p", "0..1", "progresso na fase do animador"),
    ("arma_ang", "graus", "angulo da arma (angulo_arma_visual) = o da hitbox"),
    ("arma_lunge", "raios", "avanco da empunhadura, em fracoes do raio do corpo"),
    ("arma_gx", "m", "empunhadura (onde a arma nasce)"),
    ("arma_gy", "m", "empunhadura"),
    ("arma_px", "m", "ponta: grip + comprimento honesto (= alcance da hitbox)"),
    ("arma_py", "m", "ponta"),
    ("arma_puxada", "0..1", "corda do arco puxada"),
    ("hb_on", "0/1", "hitbox ativa (calcular_hitbox_arma.ativo)"),
    ("hb_ang", "graus", "centro angular da hitbox"),
    ("hb_larg", "graus", "abertura angular da hitbox"),
    ("escudo", "0..1", "escudo restante / escudo total dos buffs; 0 sem escudo"),
    ("combo", "int", "combo SOFRIDO em curso (2, 3...); 0 fora de combo"),
    ("flash", "s", "flash de dano restante (o render mistura com flash_cor)"),
    ("flash_cor", "0xRRGGBB", "cor do flash de dano"),
    ("esc_x", "fator", "squash/stretch do corpo (aterrissagem, dash)"),
    ("esc_y", "fator", "squash/stretch do corpo"),
)
NOMES_CANAIS_LUTADOR = tuple(nome for nome, _u, _d in CANAIS_LUTADOR)

# Revisao 4: a bola da corrente nova (core/corrente.py, chave CORRENTE_V2).
# So existem no lutador cuja arma tem bola NESTA luta (``arma.corrente`` no
# cabecalho); a mao e derivavel (x, y, ang e a ``empunhadura`` do cabecalho:
# a mesma conta de ``corrente.mao``). No chao, como a hitbox: quem desenha o
# lutador levantado por ``z`` sobe a bola junto.
CANAIS_BOLA = (
    ("bola_x", "m", "centro da bola (cabeca da corrente)"),
    ("bola_y", "m", "centro da bola"),
    ("bola_vx", "m/s", "velocidade da bola (a do motor, no fim do passo)"),
    ("bola_vy", "m/s", "velocidade da bola"),
)
NOMES_CANAIS_BOLA = tuple(nome for nome, _u, _d in CANAIS_BOLA)
# Cabeca da corrente por estilo (o palco escolhe o desenho por ela) e o
# material do que liga a mao a cabeca. Estilo novo: bola de espinhos e elos.
CABECA_POR_ESTILO = {
    "Mangual": "bola_espinhos", "Flail (Mangual)": "bola_espinhos",
    "Meteor Hammer": "martelo", "Corrente com Peso": "peso",
    "Chicote": "ponta", "Kusarigama": "foice", "Rope Dart": "dardo",
}
MATERIAL_POR_ESTILO = {"Chicote": "couro", "Rope Dart": "corda", "Meteor Hammer": "corda"}
# Um elo a cada 0,16 raio do corpo (o desenho; a fisica do palco usa menos
# segmentos e distribui os elos ao longo da curva).
ELO_R = 0.16

CANAIS_CAMERA = (
    ("x", "m", "centro da camera"),
    ("y", "m", "centro da camera"),
    ("zoom", "fator", "zoom do motor (px da tela de referencia por px de mundo)"),
    ("lv", "m", "largura visivel = tela_referencia[0] / (zoom * ppm)"),
    ("av", "m", "altura visivel"),
    ("ox", "m", "tremor horizontal (0 no DIRETOR e no ARENA)"),
    ("oy", "m", "tremor vertical"),
)
NOMES_CANAIS_CAMERA = tuple(nome for nome, _u, _d in CANAIS_CAMERA)

CANAIS_GLOBAIS = (
    ("tj", "s", "tempo de JOGO acumulado (anda menos no slow-mo)"),
    ("escala", "fator", "time_scale do motor (0,25 no slow-mo do KO)"),
    ("hitstop", "s", "hit-stop restante: o mundo esta congelado se > 0"),
    ("letterbox", "s", "barras cinematograficas do golpe letal (restante)"),
    ("fim", "0/1", "round terminado (KO); o resto e a cauda do video"),
)
NOMES_CANAIS_GLOBAIS = tuple(nome for nome, _u, _d in CANAIS_GLOBAIS)

# Canais por tipo de objeto (alem de i0/i1 e dos campos fixos).
CANAIS_OBJETO = {
    "projetil": ("x", "y", "r", "ang", "prog"),
    "projetil_arma": ("x", "y", "r", "ang", "prog"),
    "orbe": ("x", "y", "r", "estado"),
    "area": ("x", "y", "r", "ativ", "prog"),
    "beam": ("larg", "prog"),
    "summon": ("x", "y", "ang", "hp", "prog"),
    "trap": ("x", "y", "hp", "prog"),
    "portal": ("prog",),
}
CANAIS_EFEITO = {
    "status": ("rest",),
    "buff": ("rest", "escudo"),
    "canal": ("prog", "ang"),
    "transformacao": ("prog",),
}


# ---------------------------------------------------------------- leitura
def _real(valor, padrao: float = 0.0) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return numero if math.isfinite(numero) else padrao


def _r(valor, casas: int = 3) -> float:
    return round(_real(valor), casas)


def _num(obj, nome: str, padrao: float = 0.0) -> float:
    return _real(getattr(obj, nome, padrao), padrao)


def _frac(valor: float, maximo: float) -> float:
    if maximo <= 0.0:
        return 0.0
    return max(0.0, min(1.0, valor / maximo))


def _xy(par) -> tuple[float, float]:
    try:
        return _real(par[0]), _real(par[1])
    except (TypeError, IndexError, KeyError):
        return 0.0, 0.0


def _cor(cor, padrao: int = 0xFFFFFF) -> int:
    """(r, g, b[, a]) -> 0xRRGGBB. Tolera tupla curta, None e lixo."""
    try:
        r, g, b = (max(0, min(255, int(c))) for c in tuple(cor)[:3])
    except (TypeError, ValueError):
        return padrao
    return (r << 16) | (g << 8) | b


def _dict_de(obj) -> dict:
    """``__dict__`` sem disparar nada (fakes com __slots__ devolvem {})."""
    try:
        return vars(obj)
    except TypeError:
        return {}


def _referencia(obj):
    """``weakref`` do objeto; se ele nao aceita (SimpleNamespace, tupla), o
    proprio objeto. So a sonda guarda isto: o jogo nao ve diferenca."""
    try:
        return weakref.ref(obj)
    except TypeError:
        return obj


def _referido(referencia):
    return referencia() if isinstance(referencia, weakref.ref) else referencia


def _perguntar(obj, metodo: str, padrao=False):
    """Chama um metodo PURO de consulta, tolerando fake sem os atributos dele
    (``object.__new__(Lutador)`` nao tem ``_transicao_sombria``)."""
    funcao = getattr(obj, metodo, None)
    if not callable(funcao):
        return padrao
    try:
        return funcao()
    except Exception:
        return padrao


def _lista(valor) -> list:
    """Copia rasa de uma lista do jogo, tolerando None e fake sem lista."""
    try:
        return list(valor or ())
    except TypeError:
        return []


def _em_metros(obj) -> tuple[float, float]:
    """(x, y) de um VFX do motor (que vive em PIXELS do mundo) em metros."""
    return _real(getattr(obj, "x", 0.0)) / PPM, _real(getattr(obj, "y", 0.0)) / PPM


def _slot_do_dono(sim, dono) -> str | None:
    if dono is None:
        return None
    if dono is getattr(sim, "p1", None):
        return "p1"
    if dono is getattr(sim, "p2", None):
        return "p2"
    return None


def _tier_por_forca(forca: float) -> str:
    try:
        from neural_fights.effects.attack import LIMIARES_FORCA
    except Exception:  # pragma: no cover - fallback de fake sem pygame
        LIMIARES_FORCA = {"colossal": 7.5, "heavy": 7.0, "medium": 5.5}
    if forca >= LIMIARES_FORCA["colossal"]:
        return "colossal"
    if forca >= LIMIARES_FORCA["heavy"]:
        return "heavy"
    if forca >= LIMIARES_FORCA["medium"]:
        return "medium"
    return "light"


def fases_do_perfil(perfil) -> tuple[tuple[str, float], ...]:
    """As cinco fases de um ``WeaponAnimationProfile``, com a duracao de cada."""
    return (
        ("anticipation", _num(perfil, "anticipation_time")),
        ("attack", _num(perfil, "attack_time")),
        ("impact", _num(perfil, "impact_time")),
        ("follow", _num(perfil, "follow_through_time")),
        ("recovery", _num(perfil, "recovery_time")),
    )


def fase_no_tempo(decorrido: float, perfil) -> tuple[int, float, float]:
    """(indice em FASES, progresso 0..1, duracao da fase) apos ``decorrido`` s.

    A MESMA conta de ``WeaponAnimator._get_phase``: fase de duracao zero e
    pulada, e depois da ultima fase o golpe fica em recovery com progresso 1.
    """
    acumulado = 0.0
    fases = fases_do_perfil(perfil)
    for indice, (_nome, duracao) in enumerate(fases, start=1):
        if decorrido < acumulado + duracao:
            progresso = (decorrido - acumulado) / max(duracao, 0.001)
            return indice, max(0.0, min(1.0, progresso)), duracao
        acumulado += duracao
    return len(FASES) - 1, 1.0, fases[-1][1]


def geometria_da_arma(x: float, y: float, angulo: float, raio: float, tipo: str,
                      grip_profiles: dict, range_mult: float, *,
                      lunge: float = 0.0, no_chao: bool = False
                      ) -> tuple[float, float, float, float, float]:
    """Empunhadura e ponta da arma, em metros: ``(gx, gy, px, py, comprimento)``.

    Espelha ``Simulador.desenhar_arma`` (simulacao.py, "geometria honesta"):
    a arma nasce na mao (``GRIP_PROFILES``: avanco e lateral em fracoes do
    raio do corpo, mais o ``lunge`` do golpe) e ``grip + comprimento`` e o
    ``raio * range_mult`` da hitbox. A ponta esta no PLANO DO CHAO, como a
    hitbox: quem desenha o lutador levantado por ``z`` sobe a arma junto.
    """
    rad = math.radians(angulo)
    grip = None if no_chao else grip_profiles.get(tipo)
    distancia_grip = 0.0
    gx, gy = x, y
    if grip:
        distancia_grip = raio * _real(grip.get("offset_r"))
        deslocamento = distancia_grip + lunge * raio
        gx += math.cos(rad) * deslocamento
        gy += math.sin(rad) * deslocamento
        lateral = raio * _real(grip.get("lateral_r"))
        if lateral:
            gx += math.cos(rad + math.pi / 2) * lateral
            gy += math.sin(rad + math.pi / 2) * lateral
    if tipo == "Arco":
        comprimento = raio * 1.15
    elif tipo in ("Arremesso", "Orbital", "Mágica"):
        comprimento = raio
    else:
        comprimento = max(raio * 0.35, raio * range_mult - distancia_grip)
    return (gx, gy, gx + math.cos(rad) * comprimento,
            gy + math.sin(rad) * comprimento, comprimento)


# Copia de Simulador.GRIP_PROFILES para quando nao ha Simulador (fakes). A
# sonda le a do Simulador vivo; ha teste cobrando que as duas batem.
GRIP_PROFILES_PADRAO = {
    "Reta": {"offset_r": 0.90, "lateral_r": 0.0},
    "Dupla": {"offset_r": 0.62, "lateral_r": 0.0},
    "Corrente": {"offset_r": 0.90, "lateral_r": 0.15},
    "Arco": {"offset_r": 1.05, "lateral_r": 0.0},
    "Transformável": {"offset_r": 0.90, "lateral_r": 0.0},
    "Transformavel": {"offset_r": 0.90, "lateral_r": 0.0},
}


class _Tabela:
    """Tabela de strings: o canal guarda o indice, o documento a lista."""

    def __init__(self, iniciais=()):
        self.itens: list = list(iniciais)
        self._indices = {valor: i for i, valor in enumerate(self.itens)}

    def indice(self, valor) -> int:
        if valor is None or valor == "":
            return -1
        indice = self._indices.get(valor)
        if indice is None:
            indice = len(self.itens)
            self.itens.append(valor)
            self._indices[valor] = indice
        return indice


class _Trilha:
    """Algo que vive num intervalo contiguo de passos [i0, i1]."""

    __slots__ = ("id", "fixos", "canais", "i0", "i1")

    def __init__(self, ident: int, i0: int, fixos: dict, canais: tuple[str, ...]):
        self.id = ident
        self.fixos = fixos
        self.canais = {nome: [] for nome in canais}
        self.i0 = i0
        self.i1 = i0 - 1

    def amostrar(self, i: int, valores) -> None:
        for lista, valor in zip(self.canais.values(), valores):
            lista.append(valor)
        self.i1 = i

    def documento(self) -> dict:
        return {"id": self.id, **self.fixos, "i0": self.i0, "i1": self.i1,
                **self.canais}


class SondaTimeline:
    """Amostra a luta a cada passo do motor, sem mudar nada nela.

    Uso (o mesmo contrato das sondas do gravador)::

        sonda = SondaTimeline()
        sonda.on_inicio(sim)                 # antes do primeiro passo
        while ...:
            dt = sim.avancar_relogio(passo); sim.update(dt)
            sonda.on_frame(sim, t_jogo=t_jogo)   # ANTES de sim.desenhar()
            sim.desenhar()
        sonda.anexar_sons(resultado["sons"])     # quando houver (Onda 16A)
        doc = sonda.documento(resultado={...})

    ``on_frame`` deve ser chamado a CADA passo: o relogio da timeline e o
    numero do passo (``t = i / hz``), nao o ``t_video`` quantizado do gravador.
    """

    def __init__(self, *, hz: int = HZ):
        self.hz = int(hz)
        self.i = -1
        self._iniciada = False
        self.cabecalho: dict = {}
        self.tabelas = {
            "expressoes": _Tabela(EXPRESSOES),
            "acoes": _Tabela(),
            "planos": _Tabela(),
            "tells": _Tabela(),
            "estados_orbe": _Tabela(ESTADOS_ORBE),
        }
        self._planos_tipo: dict[int, str] = {}
        self.lutadores = {slot: {nome: [] for nome in NOMES_CANAIS_LUTADOR}
                          for slot in ("p1", "p2")}
        self.camera = {nome: [] for nome in NOMES_CANAIS_CAMERA}
        self.globais = {nome: [] for nome in NOMES_CANAIS_GLOBAIS}
        self.objetos: list[_Trilha] = []
        self.efeitos: list[_Trilha] = []
        self.eventos: list[dict] = []
        self.sons: dict | None = None
        self.remapeamento: dict | None = None
        self._proximo_id = 1
        # chave -> (trilha, weakref do objeto): ver _trilha.
        self._vivas: dict = {}
        self._mem: dict = {}
        self._t_jogo = 0.0
        self._dt = 1.0 / self.hz
        # Revisao 3. Projeteis e orbes em voo: id da trilha -> o ultimo estado
        # (so numeros e a referencia fraca), do passo anterior e deste.
        self._voando: dict = {}
        self._voando_agora: dict = {}
        self._reflexoes: list = []
        # nome da lista de VFX -> {id(obj): weakref}: o que a sonda ja viu.
        self._vfx_vistos: dict = {}
        # id(texto) -> (weakref, texto_id, valor): textos flutuantes vivos.
        self._textos: dict = {}
        self._proximo_texto = 1
        # slot atingido por projetil neste passo -> {ponto, projetil}
        self._impactos: dict = {}
        # Revisao 4: slot -> a arma tem bola (corrente nova) nesta luta.
        self._com_bola: dict = {}

    # ------------------------------------------------------------ inicio
    def on_inicio(self, sim, **luta) -> None:
        """Cabecalho estatico (arena, lutadores, armas, tela) e o marco zero
        dos contadores. Chame ANTES do primeiro passo: sem isso, o que
        acontecer no passo 0 vira linha de base e nao evento."""
        self._iniciada = True
        config = getattr(sim, "match_config", None) or {}
        cam = getattr(sim, "cam", None)
        tela = [int(_num(cam, "screen_width", 0)), int(_num(cam, "screen_height", 0))]
        info_luta = {
            "seed": getattr(sim, "seed", None),
            "p1": config.get("p1_nome"),
            "p2": config.get("p2_nome"),
            "cenario": config.get("cenario"),
            "camera_modo": str(getattr(cam, "modo", config.get("camera_modo") or "")),
            "camera_largura_min_m": _r(getattr(cam, "diretor_largura_min_m", 0.0), 3),
            "camera_espera_zoom_in": _r(getattr(cam, "diretor_espera_zoom_in", 0.0), 3),
        }
        info_luta.update({k: v for k, v in luta.items() if v is not None})
        # Revisao 4: a chave da corrente nova DESTA luta (ausente no
        # match_config = a padrao do motor, hoje desligada).
        info_luta["corrente_v2"] = self._chave_corrente(config)
        self._com_bola = {slot: self._tem_bola(getattr(sim, slot, None)) for slot in ("p1", "p2")}
        for slot, tem in self._com_bola.items():
            if tem:
                for nome in NOMES_CANAIS_BOLA:
                    self.lutadores[slot][nome] = []
        self.cabecalho = {
            "luta": info_luta,
            "tela_referencia": tela,
            "arena": self._cabecalho_arena(sim),
            "lutadores": [self._cabecalho_lutador(sim, slot) for slot in ("p1", "p2")],
        }
        self._mem = self._memoria_inicial(sim)
        # o que ja existe antes do primeiro passo e linha de base, nao evento
        self._vfx_novos(sim)
        self._eventos_de_texto(sim, {}, base=True)

    @staticmethod
    def _chave_corrente(config) -> bool:
        try:
            from neural_fights.core import corrente
            return bool(corrente.chave_ligada(config))
        except Exception:  # pragma: no cover
            return bool((config or {}).get("corrente_v2", False))

    @staticmethod
    def _tem_bola(lutador) -> bool:
        """A arma deste lutador tem bola NESTA luta? (so le: ``v2_ativa``
        olha o atributo que o Simulador poe com a chave e o catalogo)."""
        if lutador is None:
            return False
        try:
            from neural_fights.core import corrente
            return bool(corrente.v2_ativa(lutador))
        except Exception:
            return False

    def _cabecalho_corrente(self, lutador) -> dict | None:
        """``arma.corrente`` (revisao 4): o que o palco precisa para desenhar a
        corrente presa na mao e na bola. Numeros do motor, nada inventado."""
        if not self._tem_bola(lutador):
            return None
        from neural_fights.core import corrente

        arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
        estilo = str(getattr(arma, "estilo", "") or "")
        raio = corrente.raio_corpo(lutador)
        comp = corrente.comprimento(arma, raio)
        return {
            "comp_m": _r(comp),
            "n_elos": int(max(8, min(40, round(comp / max(raio * ELO_R, 1e-6))))),
            "cabeca": CABECA_POR_ESTILO.get(estilo, "bola_espinhos"),
            "material": MATERIAL_POR_ESTILO.get(estilo, "elos"),
            "familia": corrente.familia(arma),
            "raio_bola_m": _r(corrente.raio_bola(arma, raio)),
            "v_ref_ms": _r(corrente.velocidade_nominal(lutador), 2),
            # a MAO da corrente (corrente.mao): no olhar, sem o avanco do golpe
            "mao": {"avanco_r": corrente.GRIP_OFFSET_R, "lateral_r": corrente.GRIP_LATERAL_R},
        }

    def _cabecalho_arena(self, sim) -> dict | None:
        arena = getattr(sim, "arena", None)
        if arena is None:
            return None
        cfg = getattr(arena, "config", None)
        obstaculos = []
        for obs in getattr(arena, "obstaculos", None) or ():
            obstaculos.append({
                "tipo": str(getattr(obs, "tipo", "")),
                "x": _r(getattr(obs, "x", 0.0)), "y": _r(getattr(obs, "y", 0.0)),
                "largura": _r(getattr(obs, "largura", 0.0)),
                "altura": _r(getattr(obs, "altura", 0.0)),
                "cor": _cor(getattr(obs, "cor", None)),
                "solido": bool(getattr(obs, "solido", True)),
                "destrutivel": bool(getattr(obs, "destrutivel", False)),
                "hp": _r(getattr(obs, "hp", 0), 1),
            })
        raio = getattr(arena, "raio", None)
        return {
            "nome": str(getattr(cfg, "nome", "")),
            "formato": str(getattr(cfg, "formato", "retangular")),
            "largura": _r(getattr(arena, "largura", 0.0)),
            "altura": _r(getattr(arena, "altura", 0.0)),
            "min": [_r(getattr(arena, "min_x", 0.0)), _r(getattr(arena, "min_y", 0.0))],
            "max": [_r(getattr(arena, "max_x", 0.0)), _r(getattr(arena, "max_y", 0.0))],
            "centro": [_r(getattr(arena, "centro_x", 0.0)), _r(getattr(arena, "centro_y", 0.0))],
            "raio": None if raio is None else _r(raio),
            "tem_paredes": bool(getattr(cfg, "tem_paredes", True)),
            "espessura_parede": _r(getattr(cfg, "espessura_parede", 0.0)),
            "cor_chao": _cor(getattr(cfg, "cor_chao", None)),
            "cor_parede": _cor(getattr(cfg, "cor_parede", None)),
            "cor_borda": _cor(getattr(cfg, "cor_borda", None)),
            "cor_ambiente": _cor(getattr(cfg, "cor_ambiente", None), 0),
            "tema": str(getattr(cfg, "tema", "")),
            "efeitos": [str(e) for e in getattr(cfg, "efeitos_especiais", None) or ()],
            "obstaculos": obstaculos,
        }

    def _cabecalho_lutador(self, sim, slot: str) -> dict | None:
        lutador = getattr(sim, slot, None)
        if lutador is None:
            return None
        dados = getattr(lutador, "dados", None)
        nome = str(getattr(dados, "nome", slot))
        rotulos = (getattr(sim, "match_config", None) or {}).get("nomes_exibicao") or {}
        tamanho = _num(dados, "tamanho", 1.7)
        classe_data = getattr(lutador, "class_data", None)
        cor_aura = classe_data.get("cor_aura") if isinstance(classe_data, dict) else None
        try:
            from neural_fights.utils.config import COR_P1, COR_P2
        except Exception:  # pragma: no cover
            COR_P1, COR_P2 = (52, 152, 219), (231, 76, 60)
        skills = [str(s.get("nome")) for s in (getattr(lutador, "skills_arma", None) or ())
                  if isinstance(s, dict)]
        skills += [str(s.get("nome")) for s in (getattr(lutador, "skills_classe", None) or ())
                   if isinstance(s, dict)]
        cor_corpo = (
            getattr(dados, "cor_r", 200) or 200,
            getattr(dados, "cor_g", 50) or 50,
            getattr(dados, "cor_b", 50) or 50,
        )
        forca = _num(dados, "forca", 5.0)
        return {
            "slot": slot,
            "nome": nome,
            "rotulo": str(rotulos.get(nome, nome)),
            "classe": str(getattr(lutador, "classe_nome", "")),
            "cor": _cor(cor_corpo),
            "cor_lado": _cor(COR_P1 if slot == "p1" else COR_P2),
            "cor_aura_classe": _cor(cor_aura, 0xC8C8C8),
            "tamanho": _r(tamanho),
            # O circulo DESENHADO tem raio tamanho/2; o de colisao, tamanho/4.
            "raio_corpo": _r(tamanho / 2.0),
            "raio_fisico": _r(getattr(lutador, "raio_fisico", tamanho / 4.0)),
            "vida_max": _r(getattr(lutador, "vida_max", 0.0), 2),
            "mana_max": _r(getattr(lutador, "mana_max", 0.0), 2),
            "estamina_max": _r(getattr(lutador, "estamina_max", 100.0), 2),
            "forca": _r(forca, 2),
            "tier_impacto": _tier_por_forca(forca),
            "skills": skills,
            "arma": self._cabecalho_arma(sim, lutador),
        }

    def _cabecalho_arma(self, sim, lutador) -> dict | None:
        dados = getattr(lutador, "dados", None)
        arma = getattr(dados, "arma_obj", None)
        if arma is None:
            return None
        tipo = str(getattr(arma, "tipo", "Reta") or "Reta")
        estilo = str(getattr(arma, "estilo", "") or "")
        raio = _num(dados, "tamanho", 1.7) / 2.0
        grip_profiles = self._grip_profiles(sim)
        grip = grip_profiles.get(tipo)
        mult = self._range_mult(tipo)
        _gx, _gy, _px, _py, comprimento = geometria_da_arma(
            0.0, 0.0, 0.0, raio, tipo, grip_profiles, mult)
        hitbox = self._hitbox(lutador)
        perfil_hb = {}
        try:
            from neural_fights.core.hitbox import get_hitbox_profile
            perfil_hb = dict(get_hitbox_profile(tipo))
        except Exception:
            pass
        perfil_golpe, perfil_anim, arquetipo = self._perfis(tipo, estilo)
        documento = {
            "nome": str(getattr(arma, "nome", "")),
            "tipo": tipo,
            "estilo": estilo,
            "raridade": str(getattr(arma, "raridade", "") or ""),
            "cor": _cor((getattr(arma, "r", 255), getattr(arma, "g", 255),
                         getattr(arma, "b", 255))),
            "efeito_visual": getattr(arma, "efeito_visual", None),
            "empunhadura": None if not grip else {
                "avanco_r": _r(grip.get("offset_r"), 3),
                "lateral_r": _r(grip.get("lateral_r"), 3),
            },
            "comprimento_m": _r(comprimento),
            "alcance_m": None if hitbox is None else _r(_num(hitbox, "alcance") / PPM),
            "alcance_min_m": None if hitbox is None else _r(_num(hitbox, "alcance_minimo") / PPM),
            "hitbox": {
                "forma_ataque": perfil_hb.get("shape"),
                "forma_parada": perfil_hb.get("idle_shape"),
                "range_mult": perfil_hb.get("range_mult", mult),
            },
            "perfil_golpe": perfil_golpe,
            "perfil_animacao": perfil_anim,
            "arquetipo_animacao": arquetipo,
        }
        if tipo == "Dupla":
            # desenhar_arma espelha a lamina nos dois "ombros": +-sep na
            # perpendicular, +-10 graus, e cada uma um pouco mais curta.
            separacao = raio * 0.55
            distancia_grip = raio * _real((grip or {}).get("offset_r"))
            documento["duas_laminas"] = {
                "separacao_r": 0.55,
                "abertura_graus": 10.0,
                "comprimento_m": _r(max(raio * 0.3, raio * mult - distancia_grip - separacao * 0.3)),
            }
        bloco_corrente = self._cabecalho_corrente(lutador)
        if bloco_corrente is not None:
            documento["corrente"] = bloco_corrente
        return documento

    @staticmethod
    def _perfis(tipo: str, estilo: str) -> tuple[dict, dict, str]:
        try:
            from neural_fights.effects.weapon_animations import (
                WEAPON_PROFILES,
                WeaponAnimator,
                get_animation_profile,
            )
        except Exception:  # pragma: no cover
            return {}, {}, "corte"
        golpe = WEAPON_PROFILES.get(tipo, WEAPON_PROFILES["Reta"])
        anim = get_animation_profile(tipo, estilo)
        fases_golpe = fases_do_perfil(golpe)
        antecipacao = golpe.anticipation_time
        janela = [
            _r(antecipacao * 0.5, 4),
            _r(antecipacao + golpe.attack_time + golpe.impact_time
               + golpe.follow_through_time * 0.9, 4),
        ]
        perfil_golpe = {
            "fonte": "WEAPON_PROFILES[tipo]: o relogio do motor (timer_animacao)",
            **{nome: _r(duracao, 4) for nome, duracao in fases_golpe},
            "total": _r(golpe.total_time, 4),
            "janela_hit": janela,
        }
        perfil_anim = {
            "fonte": "get_animation_profile(tipo, estilo): o animador visual",
            **{nome: _r(duracao, 4) for nome, duracao in fases_do_perfil(anim)},
            "total": _r(anim.total_time, 4),
            "angulos": {
                "anticipation": _r(anim.anticipation_angle, 2),
                "attack": _r(anim.attack_angle, 2),
                "follow": _r(anim.follow_through_angle, 2),
            },
            "easing": {
                "anticipation": anim.anticipation_easing,
                "attack": anim.attack_easing,
                "recovery": anim.recovery_easing,
            },
        }
        arquetipo = WeaponAnimator.ARQUETIPO_POR_ESTILO.get(estilo, "corte")
        return perfil_golpe, perfil_anim, arquetipo

    @staticmethod
    def _grip_profiles(sim) -> dict:
        perfis = getattr(type(sim), "GRIP_PROFILES", None)
        return perfis if isinstance(perfis, dict) else GRIP_PROFILES_PADRAO

    @staticmethod
    def _range_mult(tipo: str) -> float:
        try:
            from neural_fights.core.hitbox import get_hitbox_profile
            return _real(get_hitbox_profile(tipo).get("range_mult"), 2.0)
        except Exception:
            return 2.0

    @staticmethod
    def _hitbox(lutador):
        """A hitbox REAL do motor (calculo puro de core/hitbox.py)."""
        if getattr(getattr(lutador, "dados", None), "arma_obj", None) is None:
            return None
        try:
            from neural_fights.core.hitbox import sistema_hitbox
            return sistema_hitbox.calcular_hitbox_arma(lutador)
        except Exception:
            return None

    # ------------------------------------------------------------ memoria
    def _memoria_inicial(self, sim) -> dict:
        memoria = {"lutadores": {}, "round_fim": bool(getattr(sim, "round_finalizado", False)),
                   "primeiro_sangue": False, "lider": None,
                   "proxima_lideranca": 0.0, "hitstops": self._total_hitstops(sim),
                   "agarrao": None, "colisoes": {}, "obstaculos": self._obstaculos_solidos(sim)}
        for slot in ("p1", "p2"):
            memoria["lutadores"][slot] = self._memoria_lutador(getattr(sim, slot, None))
        return memoria

    def _memoria_lutador(self, lutador) -> dict:
        brain = getattr(lutador, "brain", None)
        return {
            "vida": _num(lutador, "vida"),
            "contadores": dict(getattr(lutador, "contadores_luta", None) or {}),
            "esquivas": int(_num(lutador, "esquivas_visuais")),
            "cd": dict(getattr(lutador, "cd_skills", None) or {}),
            "combo": 0,
            "tell": (),
            "plano": _dict_de(brain).get("plano") if brain is not None else None,
            "escudo": self._escudo(lutador)[0],
        }

    @staticmethod
    def _total_hitstops(sim) -> int:
        hitstop = getattr(getattr(sim, "game_feel", None), "hit_stop", None)
        return int(_num(hitstop, "total_hitstops"))

    @staticmethod
    def _obstaculos_solidos(sim) -> tuple:
        arena = getattr(sim, "arena", None)
        return tuple(bool(getattr(obs, "solido", True))
                     for obs in (getattr(arena, "obstaculos", None) or ()))

    # ------------------------------------------------------------ passo
    def on_frame(self, sim, t_video: float | None = None, t_jogo: float | None = None) -> None:
        """Amostra UM passo do motor. ``t_video`` e aceito pelo contrato das
        sondas do gravador e nao e usado: o relogio e ``i / hz``."""
        if not self._iniciada:
            self.on_inicio(sim)
        self.i += 1
        i = self.i
        escala = _num(sim, "time_scale", 1.0)
        if t_jogo is None:
            t_jogo = self._t_jogo + escala / self.hz
        novo_t = _real(t_jogo)
        # o dt de JOGO deste passo: e o que o motor descontou da vida de
        # cada projetil (a regra do "expirou")
        self._dt = max(0.0, novo_t - self._t_jogo)
        self._t_jogo = novo_t
        self._voando_agora = {}
        self._reflexoes = []
        self._amostrar_globais(sim)
        self._amostrar_camera(sim)
        for slot in ("p1", "p2"):
            self._amostrar_lutador(sim, slot, getattr(sim, slot, None))
        self._amostrar_objetos(sim, i)
        self._amostrar_efeitos(sim, i)
        self._detectar_eventos(sim, i)
        self._voando = self._voando_agora

    def _amostrar_globais(self, sim) -> None:
        hitstop = getattr(getattr(sim, "game_feel", None), "hit_stop", None)
        valores = (
            _r(self._t_jogo, 4),
            _r(_num(sim, "time_scale", 1.0), 3),
            _r(max(0.0, _num(hitstop, "timer_ativo")), 3),
            _r(max(0.0, _num(sim, "letterbox_timer")), 3),
            1 if getattr(sim, "round_finalizado", False) else 0,
        )
        for lista, valor in zip(self.globais.values(), valores):
            lista.append(valor)

    def _amostrar_camera(self, sim) -> None:
        cam = getattr(sim, "cam", None)
        zoom = _num(cam, "zoom", 1.0) or 1.0
        escala = zoom * PPM
        largura = _num(cam, "screen_width", 0.0)
        altura = _num(cam, "screen_height", 0.0)
        valores = (
            _r(_num(cam, "x") / PPM),
            _r(_num(cam, "y") / PPM),
            _r(zoom, 4),
            _r(largura / escala),
            _r(altura / escala),
            _r(_num(cam, "offset_x") / escala, 4),
            _r(_num(cam, "offset_y") / escala, 4),
        )
        for lista, valor in zip(self.camera.values(), valores):
            lista.append(valor)

    def _escudo(self, lutador) -> tuple[float, float]:
        buffs = self._buffs(lutador)
        atual = sum(_num(b, "escudo_atual") for b in buffs)
        total = sum(_num(b, "escudo") for b in buffs if _num(b, "escudo") > 0)
        return atual, total

    @staticmethod
    def _buffs(lutador) -> list:
        return [b for b in (getattr(lutador, "buffs_ativos", None) or ())
                if getattr(b, "ativo", True)]

    @staticmethod
    def _expressao(lutador) -> str:
        brain = getattr(lutador, "brain", None)
        if (brain is not None and "emocoes" not in _dict_de(brain)
                and isinstance(getattr(type(brain), "humor", None), property)):
            # Ler brain.humor aqui CRIARIA o motor emocional (a property e
            # preguicosa): so acontece em fake de contrato. Sem ler, neutro.
            return "neutro"
        try:
            from neural_fights.effects.character_flair import resolver_expressao
            return str(resolver_expressao(lutador, 0.0))
        except Exception:
            return "neutro"

    @staticmethod
    def _estado_animador(lutador):
        """Estado do animador visual SEM criar entrada (get_state criaria)."""
        try:
            from neural_fights.effects import weapon_animations
        except Exception:  # pragma: no cover
            return None
        gerente = getattr(weapon_animations, "_weapon_animation_manager", None)
        animador = getattr(gerente, "animator", None)
        estados = getattr(animador, "states", None)
        if not isinstance(estados, dict):
            return None
        return estados.get(id(lutador))

    def _amostrar_lutador(self, sim, slot: str, lutador) -> None:
        canais = self.lutadores[slot]
        if lutador is None:
            for lista in canais.values():
                lista.append(lista[-1] if lista else 0)
            return
        dados = getattr(lutador, "dados", None)
        brain = getattr(lutador, "brain", None)
        x, y = _xy(getattr(lutador, "pos", None))
        vx, vy = _xy(getattr(lutador, "vel", None))
        z = _num(lutador, "z")
        vida_max = _num(lutador, "vida_max", 1.0)
        raio = _num(dados, "tamanho", 1.7) / 2.0

        # --- mente (so o que o motor ja expoe para o render) ---
        acao = str(getattr(brain, "acao_atual", "") or "") if brain is not None else ""
        plano = _dict_de(brain).get("plano") if brain is not None else None
        indice_plano = -1
        progresso_plano = 0.0
        if plano is not None:
            tipo_plano = str(getattr(plano, "tipo", "") or "")
            rotulo = str(getattr(plano, "rotulo", "") or tipo_plano)
            indice_plano = self.tabelas["planos"].indice((tipo_plano, rotulo))
            self._planos_tipo[indice_plano] = tipo_plano
            progresso_plano = _real(getattr(plano, "progresso", 0.0))
        tell = getattr(brain, "tell_atual", None) if brain is not None else None
        indice_tell = -1
        if isinstance(tell, dict) and _num(brain, "tempo_combate") < _real(tell.get("ate")):
            indice_tell = self.tabelas["tells"].indice(str(tell.get("tipo", "")))

        # --- flags ---
        timers = getattr(lutador, "status_timers", None)
        congelado = bool(getattr(lutador, "congelado", False))
        tempo_parado = bool(getattr(lutador, "tempo_parado", False))
        if timers is not None:
            try:
                congelado = congelado or timers.get("CONGELADO") > 0.0
                tempo_parado = tempo_parado or timers.get("TEMPO_PARADO") > 0.0
            except Exception:
                pass
        transformacao = getattr(lutador, "transformacao_ativa", None)
        armadura = None
        systems = getattr(getattr(sim, "game_feel", None), "super_armor_systems", None)
        if isinstance(systems, dict):
            armadura = systems.get(lutador)
        ligados = (
            bool(getattr(lutador, "atacando", False)),
            bool(getattr(lutador, "morto", False)),
            _num(lutador, "stun_timer") > 0.0,
            congelado,
            _num(lutador, "invencivel_timer") > 0.0
            or _num(lutador, "invulnerabilidade_skill_timer") > 0.0,
            bool(getattr(lutador, "canalizando", False)),
            bool(getattr(lutador, "modo_adrenalina", False)),
            _num(lutador, "agarrao_timer") > 0.0,
            _num(lutador, "dash_timer") > 0.0,
            bool(getattr(lutador, "intangivel", False)),
            bool(getattr(getattr(armadura, "data", None), "ativo", False)),
            acao == "BLOQUEAR",
            tempo_parado,
            bool(getattr(lutador, "dormindo", False)),
            transformacao is not None and bool(getattr(transformacao, "ativo", True)),
            _num(lutador, "lancado_timer") > 0.0,
            bool(_perguntar(lutador, "em_transicao_sombria")),
            z > 0.01,
        )
        flags = 0
        for bit, ligado in enumerate(ligados):
            if ligado:
                flags |= 1 << bit

        # --- golpe pelo RELOGIO DO MOTOR (timer_animacao + WEAPON_PROFILES) ---
        arma = getattr(dados, "arma_obj", None)
        tipo = str(getattr(arma, "tipo", "Reta") or "Reta") if arma is not None else "Reta"
        estilo = str(getattr(arma, "estilo", "") or "") if arma is not None else ""
        fase = 0
        progresso = 0.0
        duracao = 0.0
        janela = 0
        atacando = bool(getattr(lutador, "atacando", False))
        if atacando and arma is not None and "Orbital" not in tipo:
            try:
                from neural_fights.effects.weapon_animations import WEAPON_PROFILES
                perfil = WEAPON_PROFILES.get(tipo, WEAPON_PROFILES["Reta"])
                decorrido = perfil.total_time - max(0.0, _num(lutador, "timer_animacao"))
                fase, progresso, duracao = fase_no_tempo(decorrido, perfil)
            except Exception:
                pass
            try:
                from neural_fights.core.hitbox import sistema_hitbox
                janela = 1 if sistema_hitbox._verificar_janela_hit(lutador, tipo) else 0
            except Exception:
                janela = 0

        # --- o animador visual (perfil do estilo): outro relogio ---
        anim_fase = 0
        anim_p = 0.0
        estado = self._estado_animador(lutador)
        if estado is not None and getattr(estado, "is_attacking", False):
            try:
                from neural_fights.effects.weapon_animations import get_animation_profile
                anim_fase, anim_p, _dur = fase_no_tempo(
                    _num(estado, "attack_timer"), get_animation_profile(tipo, estilo))
            except Exception:
                pass

        # --- geometria honesta da arma e a hitbox real ---
        morto = bool(getattr(lutador, "morto", False))
        lunge = _num(lutador, "weapon_anim_lunge")
        angulo_arma = _num(lutador, "angulo_arma_visual")
        gx = gy = px = py = 0.0
        if arma is not None:
            origem_x, origem_y = x, y
            no_chao = False
            caida = getattr(lutador, "arma_droppada_pos", None)
            if morto and caida is not None:
                origem_x, origem_y = _xy(caida)
                angulo_arma = _num(lutador, "arma_droppada_ang")
                lunge = 0.0
                no_chao = True
            gx, gy, px, py, _comprimento = geometria_da_arma(
                origem_x, origem_y, angulo_arma, raio, tipo, self._grip_profiles(sim),
                self._range_mult(tipo), lunge=lunge, no_chao=no_chao)
        hitbox = self._hitbox(lutador)

        # --- defesa e leitura ---
        escudo_atual, escudo_total = self._escudo(lutador)
        combo = int(_num(lutador, "combo_contra"))
        if combo < 2 or _num(lutador, "combo_contra_timer") <= 0.0:
            combo = 0
        escalas = None
        movimento = getattr(sim, "movement_anims", None)
        obter = getattr(movimento, "get_squash_stretch", None)
        if callable(obter):
            try:
                escalas = obter(lutador)
            except Exception:
                escalas = None
        esc_x, esc_y = _xy(escalas) if escalas else (1.0, 1.0)

        valores = (
            _r(x), _r(y), _r(z), _r(_num(lutador, "angulo_olhar"), 1),
            _r(vx, 2), _r(vy, 2),
            _r(_frac(_num(lutador, "vida"), vida_max)),
            _r(_frac(_num(lutador, "mana"), _num(lutador, "mana_max", 1.0))),
            _r(_frac(_num(lutador, "estamina"), _num(lutador, "estamina_max", 100.0))),
            self.tabelas["expressoes"].indice(self._expressao(lutador)),
            self.tabelas["acoes"].indice(acao),
            indice_plano, _r(progresso_plano), indice_tell, flags,
            fase, _r(progresso), _r(duracao, 4), int(_num(lutador, "ataque_id")), janela,
            anim_fase, _r(anim_p),
            _r(angulo_arma, 1), _r(lunge), _r(gx), _r(gy), _r(px), _r(py),
            _r(_num(lutador, "weapon_draw_amount")),
            1 if hitbox is not None and getattr(hitbox, "ativo", False) else 0,
            _r(_num(hitbox, "angulo"), 1) if hitbox is not None else 0.0,
            _r(_num(hitbox, "largura_angular"), 1) if hitbox is not None else 0.0,
            _r(escudo_atual / escudo_total if escudo_total > 0 and escudo_atual > 0 else 0.0),
            combo,
            _r(max(0.0, _num(lutador, "flash_timer"))),
            _cor(getattr(lutador, "flash_cor", None)),
            _r(esc_x), _r(esc_y),
        )
        for lista, valor in zip(canais.values(), valores):
            lista.append(valor)
        if getattr(self, "_com_bola", {}).get(slot):
            self._amostrar_bola(canais, lutador)

    @staticmethod
    def _amostrar_bola(canais: dict, lutador) -> None:
        """Revisao 4: onde a bola esta no FIM do passo. Le ``corrente_bola``
        sem cria-la (``corrente.bola_de`` criaria); antes de o motor cria-la,
        a bola esta na mao, parada."""
        bola = getattr(lutador, "corrente_bola", None)
        if bola is not None:
            x, y = _real(getattr(bola, "x", 0.0)), _real(getattr(bola, "y", 0.0))
            vx, vy = _real(getattr(bola, "vx", 0.0)), _real(getattr(bola, "vy", 0.0))
        else:
            try:
                from neural_fights.core import corrente
                x, y = corrente.mao(lutador)
            except Exception:
                x, y = _xy(getattr(lutador, "pos", None))
            vx = vy = 0.0
        for nome, valor in zip(NOMES_CANAIS_BOLA, (_r(x), _r(y), _r(vx, 2), _r(vy, 2))):
            canais[nome].append(valor)

    # ------------------------------------------------------------ objetos
    def _trilha(self, colecao: list, chave, objeto, i: int, fixos, canais) -> _Trilha:
        """A trilha viva desta chave, ou uma nova se houve lacuna.

        ``objeto`` e o objeto do jogo, lembrado por ``weakref``: a sonda nao
        prolonga a vida de nada, e um ``id`` reciclado (objeto novo no
        endereco de um morto) nao emenda duas trilhas, porque a referencia
        fraca do morto devolve None. ``None`` para chaves que nao sao objeto
        (status do container, por nome).
        """
        registro = self._vivas.get(chave)
        if (registro is not None and registro[0].i1 == i - 1
                and (objeto is None or _referido(registro[1]) is objeto)):
            return registro[0]
        trilha = _Trilha(self._proximo_id, i, fixos() if callable(fixos) else fixos, canais)
        self._proximo_id += 1
        colecao.append(trilha)
        self._vivas[chave] = (trilha, None if objeto is None else _referencia(objeto))
        return trilha

    def _elemento(self, objeto) -> str:
        try:
            from neural_fights.utils.palette import resolver_elemento
            return str(resolver_elemento(objeto, str(getattr(objeto, "nome", "") or ""), None))
        except Exception:
            return str(getattr(objeto, "elemento", "") or "")

    def _fixos_basicos(self, sim, objeto, tipo: str) -> dict:
        return {
            "tipo": tipo,
            "nome": str(getattr(objeto, "nome", "") or ""),
            "dono": _slot_do_dono(sim, getattr(objeto, "dono", None)),
            "elemento": self._elemento(objeto),
            "cor": _cor(getattr(objeto, "cor", None)),
        }

    def _amostrar_objetos(self, sim, i: int) -> None:
        for proj in list(getattr(sim, "projeteis", None) or ()):
            if not getattr(proj, "ativo", True):
                continue
            skill = bool(getattr(proj, "eh_skill", False))
            tipo = "projetil" if skill else "projetil_arma"

            def fixos(proj=proj, tipo=tipo, skill=skill):
                base = self._fixos_basicos(sim, proj, tipo)
                base["efeito"] = str(getattr(proj, "tipo_efeito", "") or "")
                if not skill:
                    base["forma"] = str(getattr(proj, "tipo", "") or "")
                base["vida0"] = _r(getattr(proj, "vida_max", getattr(proj, "vida", 0.0)), 3)
                if getattr(proj, "cone", False):
                    base["cone"] = {
                        "angulo": _r(getattr(proj, "angulo_cone", 60.0), 1),
                        "alcance": _r(getattr(proj, "alcance_cone", 0.0)),
                        "origem": [_r(c) for c in _xy(getattr(proj, "origem_cone", None))],
                    }
                return base
            trilha = self._trilha(self.objetos, ("obj", id(proj)), proj, i, fixos,
                                  CANAIS_OBJETO[tipo])
            vida0 = _real(trilha.fixos.get("vida0")) or 1.0
            angulo = getattr(proj, "angulo_visual", getattr(proj, "angulo", 0.0))
            trilha.amostrar(i, (
                _r(getattr(proj, "x", 0.0)), _r(getattr(proj, "y", 0.0)),
                _r(getattr(proj, "raio", 0.0)), _r(angulo, 1),
                _r(1.0 - _frac(_num(proj, "vida"), vida0)),
            ))
            self._lembrar_voo(sim, trilha, proj, ("obj", id(proj)))

        for slot in ("p1", "p2"):
            lutador = getattr(sim, slot, None)
            for orbe in list(getattr(lutador, "buffer_orbes", None) or ()):
                if not getattr(orbe, "ativo", True):
                    continue
                trilha = self._trilha(
                    self.objetos, ("obj", id(orbe)), orbe, i,
                    lambda orbe=orbe: self._fixos_basicos(sim, orbe, "orbe"),
                    CANAIS_OBJETO["orbe"])
                trilha.amostrar(i, (
                    _r(getattr(orbe, "x", 0.0)), _r(getattr(orbe, "y", 0.0)),
                    _r(getattr(orbe, "raio_visual", getattr(orbe, "raio", 0.0))),
                    self.tabelas["estados_orbe"].indice(str(getattr(orbe, "estado", "") or "")),
                ))
                self._lembrar_voo(sim, trilha, orbe, ("obj", id(orbe)))

        for area in list(getattr(sim, "areas", None) or ()):
            if not getattr(area, "ativo", True):
                continue

            def fixos(area=area):
                base = self._fixos_basicos(sim, area, "area")
                base["efeito"] = str(getattr(area, "tipo_efeito", "") or "")
                base["raio_max"] = _r(getattr(area, "raio", 0.0))
                pilares = getattr(area, "posicoes_pilares", None) or ()
                if pilares:
                    base["pilares"] = [[_r(p[0]), _r(p[1])] for p in pilares]
                    base["raio_pilar"] = _r(getattr(area, "raio_pilar", 0.0))
                segmento = getattr(area, "segmento_impacto", None)
                if segmento:
                    base["segmento"] = [[_r(c) for c in _xy(ponto)] for ponto in segmento[:2]]
                return base
            trilha = self._trilha(self.objetos, ("obj", id(area)), area, i, fixos,
                                  CANAIS_OBJETO["area"])
            raio_visual = 0.0
            obter = getattr(area, "get_avisos_visuais", None)
            if callable(obter):
                try:
                    volumes = obter()
                    raio_visual = max((_real(v[2]) for v in volumes), default=0.0)
                except Exception:
                    raio_visual = _num(area, "raio_atual")
            else:
                raio_visual = _num(area, "raio_atual")
            duracao = _num(area, "duracao", 1.0) or 1.0
            trilha.amostrar(i, (
                _r(getattr(area, "x", 0.0)), _r(getattr(area, "y", 0.0)),
                _r(raio_visual), 1 if getattr(area, "ativado", True) else 0,
                _r(1.0 - _frac(_num(area, "vida"), duracao)),
            ))

        for beam in list(getattr(sim, "beams", None) or ()):
            if not getattr(beam, "ativo", True):
                continue

            def fixos(beam=beam):
                base = self._fixos_basicos(sim, beam, "beam")
                base["efeito"] = str(getattr(beam, "tipo_efeito", "") or "")
                base["de"] = [_r(getattr(beam, "x1", 0.0)), _r(getattr(beam, "y1", 0.0))]
                base["ate"] = [_r(getattr(beam, "x2", 0.0)), _r(getattr(beam, "y2", 0.0))]
                # O zigue-zague sai do rng do lutador na criacao: e ESTADO de
                # jogo, nao enfeite do render, e por isso vai inteiro.
                base["pontos"] = [[_r(c) for c in _xy(p)]
                                  for p in (getattr(beam, "segments", None) or ())]
                base["vida0"] = _r(getattr(beam, "vida", 0.15), 3)
                return base
            trilha = self._trilha(self.objetos, ("obj", id(beam)), beam, i, fixos,
                                  CANAIS_OBJETO["beam"])
            vida0 = _real(trilha.fixos.get("vida0")) or 0.15
            trilha.amostrar(i, (
                _r(getattr(beam, "largura", 0.0), 2),
                _r(1.0 - _frac(_num(beam, "vida"), vida0)),
            ))

        for summon in list(getattr(sim, "summons", None) or ()):
            if not getattr(summon, "ativo", True):
                continue

            def fixos(summon=summon):
                base = self._fixos_basicos(sim, summon, "summon")
                base["forma"] = str(getattr(summon, "summon_tipo", "") or "")
                base["raio"] = _r(getattr(summon, "raio", 0.8) or 0.8)
                base["raio_ataque"] = _r(getattr(summon, "raio_ataque", 1.5))
                base["raio_protecao"] = _r(getattr(summon, "raio_protecao", 0.0))
                return base
            trilha = self._trilha(self.objetos, ("obj", id(summon)), summon, i, fixos,
                                  CANAIS_OBJETO["summon"])
            duracao = _num(summon, "duracao", 1.0) or 1.0
            trilha.amostrar(i, (
                _r(getattr(summon, "x", 0.0)), _r(getattr(summon, "y", 0.0)),
                _r(getattr(summon, "angulo", 0.0), 1),
                _r(_frac(_num(summon, "vida"), _num(summon, "vida_max", 1.0))),
                _r(1.0 - _frac(_num(summon, "vida_timer"), duracao)),
            ))

        for trap in list(getattr(sim, "traps", None) or ()):
            if not getattr(trap, "ativo", True):
                continue

            def fixos(trap=trap):
                base = self._fixos_basicos(sim, trap, "trap")
                base["largura"] = _r(getattr(trap, "largura", 1.0))
                base["altura"] = _r(getattr(trap, "altura", 1.0))
                base["angulo"] = _r(getattr(trap, "angulo", 0.0), 1)
                base["bloqueia_movimento"] = bool(getattr(trap, "bloqueia_movimento", False))
                return base
            trilha = self._trilha(self.objetos, ("obj", id(trap)), trap, i, fixos,
                                  CANAIS_OBJETO["trap"])
            duracao = _num(trap, "duracao", 1.0) or 1.0
            trilha.amostrar(i, (
                _r(getattr(trap, "x", 0.0)), _r(getattr(trap, "y", 0.0)),
                _r(_frac(_num(trap, "vida"), _num(trap, "vida_max", 1.0))),
                _r(1.0 - _frac(_num(trap, "vida_timer"), duracao)),
            ))

        for portal in list(getattr(sim, "portais", None) or ()):
            if not getattr(portal, "ativo", True):
                continue

            def fixos(portal=portal):
                base = self._fixos_basicos(sim, portal, "portal")
                base["a"] = [_r(c) for c in _xy(getattr(portal, "ponto_a", None))]
                base["b"] = [_r(c) for c in _xy(getattr(portal, "ponto_b", None))]
                base["raio"] = _r(getattr(portal, "raio", 0.65))
                return base
            trilha = self._trilha(self.objetos, ("obj", id(portal)), portal, i, fixos,
                                  CANAIS_OBJETO["portal"])
            duracao = _num(portal, "duracao", 1.0) or 1.0
            trilha.amostrar(i, (_r(1.0 - _frac(_num(portal, "vida"), duracao)),))

    def _amostrar_efeitos(self, sim, i: int) -> None:
        try:
            from neural_fights.core.status_runtime import STATUS_RUNTIME, normalizar_efeito
        except Exception:  # pragma: no cover
            STATUS_RUNTIME, normalizar_efeito = {}, (lambda e: str(e or "").upper())

        def fixos_status(slot, status, duracao_padrao=None):
            visual = (STATUS_RUNTIME.get(status) or {}).get("visual") or {}
            duracao = duracao_padrao
            if duracao is None:
                duracao = (STATUS_RUNTIME.get(status) or {}).get("duracao")
            return {"tipo": "status", "alvo": slot, "status": status,
                    "cor": _cor(visual.get("cor"), 0xFFFFFF),
                    "glifo": visual.get("glifo"), "estilo": visual.get("estilo"),
                    "prioridade": visual.get("prioridade"),
                    "duracao": None if duracao is None else _r(duracao, 3)}

        for slot in ("p1", "p2"):
            lutador = getattr(sim, slot, None)
            if lutador is None:
                continue
            timers = getattr(lutador, "status_timers", None)
            ativos = ()
            if timers is not None:
                try:
                    ativos = sorted(timers.ativos())
                except Exception:
                    ativos = ()
            for status in ativos:
                restante = _real(timers.get(status))
                if restante <= 0.0:
                    continue
                trilha = self._trilha(
                    self.efeitos, ("status", slot, status), None, i,
                    lambda slot=slot, status=status: fixos_status(slot, status),
                    CANAIS_EFEITO["status"])
                trilha.amostrar(i, (_r(restante, 3),))
            for dot in list(getattr(lutador, "dots_ativos", None) or ()):
                if not getattr(dot, "ativo", True):
                    continue
                status = normalizar_efeito(getattr(dot, "tipo", ""))
                trilha = self._trilha(
                    self.efeitos, ("dot", id(dot)), dot, i,
                    lambda slot=slot, status=status, dot=dot: fixos_status(
                        slot, status, _num(dot, "duracao")),
                    CANAIS_EFEITO["status"])
                trilha.amostrar(i, (_r(_num(dot, "vida"), 3),))
            for buff in self._buffs(lutador):

                def fixos(buff=buff, slot=slot):
                    return {"tipo": "buff", "alvo": slot,
                            "nome": str(getattr(buff, "nome", "") or ""),
                            "efeito": getattr(buff, "efeito", None),
                            "cor": _cor(getattr(buff, "cor", None)),
                            "duracao": _r(getattr(buff, "duracao", 0.0), 3),
                            "escudo_max": _r(getattr(buff, "escudo", 0.0), 2)}
                trilha = self._trilha(self.efeitos, ("buff", id(buff)), buff, i, fixos,
                                      CANAIS_EFEITO["buff"])
                trilha.amostrar(i, (_r(_num(buff, "vida"), 3), _r(_num(buff, "escudo_atual"), 2)))
            canal = getattr(lutador, "channel_ativo", None)
            if (canal is not None and getattr(lutador, "canalizando", False)
                    and getattr(canal, "ativo", True)):

                def fixos(canal=canal, slot=slot):
                    return {"tipo": "canal", "alvo": slot,
                            "nome": str(getattr(canal, "nome", "") or ""),
                            "elemento": self._elemento(canal),
                            "cor": _cor(getattr(canal, "cor", None)),
                            "duracao": _r(getattr(canal, "duracao_max", 0.0), 3),
                            "alcance": _r(getattr(canal, "alcance", 0.0))}
                trilha = self._trilha(self.efeitos, ("canal", id(canal)), canal, i, fixos,
                                      CANAIS_EFEITO["canal"])
                duracao = _num(canal, "duracao_max", 1.0) or 1.0
                trilha.amostrar(i, (_r(1.0 - _frac(_num(canal, "vida"), duracao)),
                                    _r(_num(canal, "angulo"), 1)))
            transformacao = getattr(lutador, "transformacao_ativa", None)
            if transformacao is not None and getattr(transformacao, "ativo", True):

                def fixos(trans=transformacao, slot=slot):
                    return {"tipo": "transformacao", "alvo": slot,
                            "nome": str(getattr(trans, "nome", "") or ""),
                            "elemento": self._elemento(trans),
                            "cor": _cor(getattr(trans, "cor", None)),
                            "cor_aura": _cor(getattr(lutador, "cor_aura", None)),
                            "duracao": _r(getattr(trans, "duracao", 0.0), 3)}
                trilha = self._trilha(self.efeitos, ("transformacao", id(transformacao)),
                                      transformacao, i, fixos, CANAIS_EFEITO["transformacao"])
                duracao = _num(transformacao, "duracao", 1.0) or 1.0
                trilha.amostrar(i, (_r(1.0 - _frac(_num(transformacao, "vida"), duracao)),))

    # ------------------------------------------------------------ eventos
    def _evento(self, i: int, tipo: str, **campos) -> None:
        evento = {"i": i, "t": round(i / self.hz, 4), "tipo": tipo}
        evento.update({k: v for k, v in campos.items() if v is not None})
        self.eventos.append(evento)

    def _detectar_eventos(self, sim, i: int) -> None:
        mem = self._mem
        hitstop = getattr(getattr(sim, "game_feel", None), "hit_stop", None)
        total_hitstops = int(_num(hitstop, "total_hitstops"))
        novo_hitstop = None
        if total_hitstops > mem["hitstops"]:
            atual = getattr(hitstop, "evento_atual", None)
            if atual is not None:
                novo_hitstop = atual
        mem["hitstops"] = total_hitstops

        lutadores = {slot: getattr(sim, slot, None) for slot in ("p1", "p2")}
        # Fotografia dos contadores dos DOIS antes de processar qualquer um: o
        # critico do acerto em p2 le o contador do autor (p1), e a memoria de
        # p1 ja teria sido atualizada neste passo.
        agora = {slot: dict(getattr(l, "contadores_luta", None) or {})
                 for slot, l in lutadores.items() if l is not None}
        antes_de = {slot: dict(mem["lutadores"].get(slot, {}).get("contadores") or {})
                    for slot in lutadores}
        # Revisao 3: o que nasceu nas listas de VFX e por que cada projetil
        # que voava sumiu. ANTES do laco: o acerto por projetil leva o ponto.
        novos = self._vfx_novos(sim)
        feridos = {}
        for slot, lutador in lutadores.items():
            if lutador is None:
                continue
            memoria = mem["lutadores"].get(slot) or {}
            queda = _real(memoria.get("vida"), _num(lutador, "vida")) - _num(lutador, "vida")
            golpes = (int(agora.get(slot, {}).get("hits_sofridos", 0) or 0)
                      - int((antes_de.get(slot) or {}).get("hits_sofridos", 0) or 0))
            feridos[slot] = queda > 1e-6 and golpes > 0
        eventos_r3 = self._analisar_voos(sim, lutadores, novos, feridos)
        for slot, lutador in lutadores.items():
            if lutador is None:
                continue
            outro_slot = "p2" if slot == "p1" else "p1"
            outro = lutadores.get(outro_slot)
            memoria = mem["lutadores"].get(slot)
            if memoria is None:
                memoria = mem["lutadores"][slot] = self._memoria_lutador(lutador)
            contadores = agora[slot]
            antes = antes_de.get(slot) or {}

            def subiu(chave, contadores=contadores, antes=antes):
                return int(contadores.get(chave, 0) or 0) - int(antes.get(chave, 0) or 0)

            x, y = _xy(getattr(lutador, "pos", None))
            vida = _num(lutador, "vida")
            queda = memoria["vida"] - vida
            golpes = subiu("hits_sofridos")
            if queda > 1e-6:
                categoria = str(getattr(lutador, "ultimo_tipo_fonte_dano", "") or "")
                vida_max = _num(lutador, "vida_max", 1.0) or 1.0
                if golpes > 0:
                    autor_x, autor_y = _xy(getattr(outro, "pos", None)) if outro is not None else (x, y)
                    extra = {}
                    if (novo_hitstop is not None
                            and getattr(novo_hitstop, "alvo", None) is lutador):
                        extra["golpe"] = str(getattr(novo_hitstop, "tipo_golpe", "") or "")
                        extra["hitstop"] = _r(getattr(novo_hitstop, "duracao", 0.0), 3)
                    critico = None
                    if outro is not None and categoria == "ataque_corpo_a_corpo":
                        critico = (int(agora.get(outro_slot, {}).get("criticos_melee", 0) or 0)
                                   > int(antes_de.get(outro_slot, {}).get("criticos_melee", 0)
                                         or 0))
                    self._evento(
                        i, "acerto", alvo=slot, autor=outro_slot, dano=_r(queda, 2),
                        dano_pct=_r(queda / vida_max, 4), golpes=golpes,
                        categoria=categoria or None,
                        tier=self._tier_do(outro), critico=critico,
                        x=_r(x), y=_r(y), z=_r(_num(lutador, "z")),
                        dir=_r(math.degrees(math.atan2(y - autor_y, x - autor_x)), 1),
                        **extra, **self._impactos.get(slot, {}))
                    if not mem["primeiro_sangue"]:
                        mem["primeiro_sangue"] = True
                        self._evento(i, "primeiro_sangue", slot=outro_slot)
                else:
                    self._evento(i, "dano", alvo=slot, dano=_r(queda, 2),
                                 categoria=categoria or None, x=_r(x), y=_r(y))
            elif queda < -0.5:
                self._evento(i, "cura", alvo=slot, valor=_r(-queda, 2), x=_r(x), y=_r(y))
            memoria["vida"] = vida

            if subiu("bloqueios") > 0:
                self._evento(i, "bloqueio", slot=slot, x=_r(x), y=_r(y),
                             ang=_r(_num(lutador, "angulo_olhar"), 1))
            if subiu("parries") > 0:
                self._evento(i, "parry", slot=slot, x=_r(x), y=_r(y),
                             ang=_r(_num(lutador, "angulo_olhar"), 1))
            esquivas = int(_num(lutador, "esquivas_visuais"))
            if esquivas > memoria["esquivas"]:
                self._evento(i, "esquiva", slot=slot, x=_r(x), y=_r(y))
            memoria["esquivas"] = esquivas
            if subiu("desvios_ia") > 0:
                self._evento(i, "desvio", slot=slot, x=_r(x), y=_r(y))
            if subiu("dashes") > 0:
                vx, vy = _xy(getattr(lutador, "vel", None))
                self._evento(i, "dash", slot=slot, x=_r(x), y=_r(y), vx=_r(vx, 2), vy=_r(vy, 2))
            if subiu("agarroes") > 0:
                agarrao = _dict_de(sim).get("_agarrao")
                origem = agarrao.get("origem") if isinstance(agarrao, dict) else None
                self._evento(i, "agarrao", iniciador=slot, alvo=outro_slot,
                             origem=None if origem is None else str(origem))
            modos = [chave[len("agarrao_"):].upper() for chave in contadores
                     if chave.startswith("agarrao_") and chave != "agarrao_reversao"
                     and subiu(chave) > 0]
            for modo in modos:
                self._evento(i, "agarrao_desfecho", iniciador=slot, alvo=outro_slot,
                             modo=modo, revertido=subiu("agarrao_reversao") > 0)
            if subiu("wall_splats") > 0:
                alvo_x, alvo_y = _xy(getattr(outro, "pos", None)) if outro is not None else (x, y)
                self._evento(i, "wall_splat", autor=slot, alvo=outro_slot,
                             x=_r(alvo_x), y=_r(alvo_y))

            cooldowns = dict(getattr(lutador, "cd_skills", None) or {})
            for nome, cd in cooldowns.items():
                if _real(cd) > _real(memoria["cd"].get(nome, 0.0)) + 1e-6:
                    self._evento(i, "skill", slot=slot, nome=str(nome),
                                 **self._dados_skill(str(nome)))
            memoria["cd"] = cooldowns

            combo = int(_num(lutador, "combo_contra"))
            ativo = combo >= 2 and _num(lutador, "combo_contra_timer") > 0.0
            if ativo and combo > memoria["combo"]:
                self._evento(i, "combo", slot=slot, n=combo)
            memoria["combo"] = combo if ativo else 0

            escudo_atual = self._escudo(lutador)[0]
            if memoria["escudo"] > 0.0 and escudo_atual <= 0.0:
                self._evento(i, "escudo_quebrou", slot=slot, x=_r(x), y=_r(y))
            memoria["escudo"] = escudo_atual

            brain = getattr(lutador, "brain", None)
            tell = getattr(brain, "tell_atual", None) if brain is not None else None
            if isinstance(tell, dict) and _num(brain, "tempo_combate") < _real(tell.get("ate")):
                chave = (str(tell.get("tipo", "")), tell.get("ate"), tell.get("modo"))
                if chave != memoria["tell"]:
                    memoria["tell"] = chave
                    detalhes = {k: tell.get(k) for k in
                                ("modo", "papel", "revertido", "plano", "rotulo", "adaptativo")
                                if tell.get(k) not in (None, "")}
                    self._evento(i, "tell", slot=slot, tell=chave[0], **detalhes)
            plano = _dict_de(brain).get("plano") if brain is not None else None
            if plano is not None and plano is not memoria["plano"]:
                self._evento(i, "plano", slot=slot,
                             plano=str(getattr(plano, "tipo", "") or ""),
                             rotulo=str(getattr(plano, "rotulo", "") or "") or None)
            memoria["plano"] = plano
            memoria["contadores"] = contadores

        if novo_hitstop is not None:
            hx, hy = _xy(getattr(novo_hitstop, "posicao", None))
            self._evento(i, "hitstop", dur=_r(getattr(novo_hitstop, "duracao", 0.0), 3),
                         golpe=str(getattr(novo_hitstop, "tipo_golpe", "") or "") or None,
                         alvo=_slot_do_dono(sim, getattr(novo_hitstop, "alvo", None)),
                         x=_r(hx / PPM), y=_r(hy / PPM))

        self._detectar_paredes(sim, i, lutadores)
        self._detectar_obstaculos(sim, i)
        for evento in (eventos_r3 + self._eventos_de_texto(sim, lutadores)
                       + self._eventos_de_movimento(sim, novos, lutadores)):
            self._evento(i, evento.pop("tipo"), **evento)

        fim = bool(getattr(sim, "round_finalizado", False))
        if fim and not mem["round_fim"]:
            vencedor = getattr(sim, "vencedor_round_side", None)
            perdedor = None
            if vencedor in ("p1", "p2"):
                perdedor = "p2" if vencedor == "p1" else "p1"
            caido = lutadores.get(perdedor) if perdedor else None
            cx, cy = _xy(getattr(caido, "pos", None)) if caido is not None else (0.0, 0.0)
            self._evento(i, "ko", vencedor=vencedor, perdedor=perdedor,
                         empate=bool(getattr(sim, "empate_round", False)) or vencedor is None,
                         x=_r(cx), y=_r(cy))
        mem["round_fim"] = fim

        # Virada de lideranca: mesma cadencia (0,25 s de JOGO) e histerese da
        # SondaNarrativa, para a legenda do video e o palco concordarem.
        if self._t_jogo >= mem["proxima_lideranca"]:
            mem["proxima_lideranca"] = self._t_jogo + PASSO_LIDERANCA
            self._amostrar_lideranca(i, lutadores)

    def _amostrar_lideranca(self, i: int, lutadores: dict) -> None:
        if self._t_jogo < IGNORAR_LIDERANCA_ATE:
            return
        p1, p2 = lutadores.get("p1"), lutadores.get("p2")
        if p1 is None or p2 is None:
            return
        r1 = max(0.0, _num(p1, "vida")) / max(1e-9, _num(p1, "vida_max", 1.0))
        r2 = max(0.0, _num(p2, "vida")) / max(1e-9, _num(p2, "vida_max", 1.0))
        diferenca = r1 - r2
        if diferenca > HISTERESE_LIDERANCA:
            candidato = "p1"
        elif diferenca < -HISTERESE_LIDERANCA:
            candidato = "p2"
        else:
            return
        if self._mem["lider"] is not None and candidato != self._mem["lider"]:
            self._evento(i, "virada", slot=candidato)
        self._mem["lider"] = candidato

    def _detectar_paredes(self, sim, i: int, lutadores: dict) -> None:
        """Impactos de parede comuns (``arena.colisoes_recentes``).

        A lista cresce sem parar no headless e e esvaziada pelo ``desenhar()``
        no gravador: a sonda reconhece o que ja viu pela IDENTIDADE da tupla
        (guardando a referencia, para o id nao ser reciclado).
        """
        colisoes = getattr(getattr(sim, "arena", None), "colisoes_recentes", None)
        if not colisoes:
            self._mem["colisoes"] = {}
            return
        vistas = self._mem["colisoes"]
        atuais = {}
        for entrada in list(colisoes):
            atuais[id(entrada)] = entrada
            if id(entrada) in vistas:
                continue
            try:
                cx, cy, intensidade = _real(entrada[0]), _real(entrada[1]), _real(entrada[2])
            except (TypeError, IndexError):
                continue
            slot = None
            melhor = None
            for nome, lutador in lutadores.items():
                if lutador is None:
                    continue
                lx, ly = _xy(getattr(lutador, "pos", None))
                distancia = math.hypot(lx - cx, ly - cy)
                if melhor is None or distancia < melhor:
                    melhor, slot = distancia, nome
            self._evento(i, "parede", slot=slot, x=_r(cx), y=_r(cy),
                         intensidade=_r(intensidade, 2))
        self._mem["colisoes"] = atuais

    def _detectar_obstaculos(self, sim, i: int) -> None:
        agora = self._obstaculos_solidos(sim)
        antes = self._mem["obstaculos"]
        if len(agora) == len(antes):
            obstaculos = getattr(getattr(sim, "arena", None), "obstaculos", None) or ()
            for indice, (era, e) in enumerate(zip(antes, agora)):
                if era and not e:
                    obs = obstaculos[indice]
                    self._evento(i, "obstaculo", indice=indice,
                                 obstaculo=str(getattr(obs, "tipo", "") or ""))
        self._mem["obstaculos"] = agora

    # ------------------------------------------------------------ revisao 3
    # O que o render acende e a v1 nao dizia, tirado das listas de VFX que o
    # motor cria (so LIDAS, reconhecidas por identidade) e do ultimo estado de
    # cada projetil. Ver docs/palco/timeline.md, "Eventos da revisao 3".
    def _lembrar_voo(self, sim, trilha: _Trilha, obj, chave) -> None:
        """Guarda o estado de voo de um projetil/orbe vivo NESTE passo: e o
        que a sonda tem para dizer por que ele sumiu, no passo em que sumir
        (o objeto quase sempre ja morreu entao). So numeros e a referencia
        fraca que ``_trilha`` ja guardou. O dono que muda entre dois passos da
        MESMA trilha e a reflexao (``combat.refletir_projetil``)."""
        dono = _slot_do_dono(sim, getattr(obj, "dono", None))
        x, y = _real(getattr(obj, "x", 0.0)), _real(getattr(obj, "y", 0.0))
        antes = self._voando.get(trilha.id)
        if (antes is not None and dono is not None and antes["dono"] is not None
                and dono != antes["dono"]):
            self._reflexoes.append({"tipo": "refletido", "id": trilha.id,
                                    "de": antes["dono"], "para": dono,
                                    "x": _r(x), "y": _r(y)})
        registro = self._vivas.get(chave)
        timer = getattr(obj, "explosion_timer", None)
        self._voando_agora[trilha.id] = {
            "id": trilha.id,
            "objeto": trilha.fixos.get("tipo"),
            "elemento": trilha.fixos.get("elemento") or None,
            "ref": registro[1] if registro is not None else None,
            "x": x, "y": y,
            # o deslocamento do ultimo passo: onde ele estaria DEPOIS de andar
            # no passo em que sumiu (o motor move antes de colidir)
            "dx": 0.0 if antes is None else x - antes["x"],
            "dy": 0.0 if antes is None else y - antes["y"],
            "r": max(0.0, _num(obj, "raio", _num(obj, "raio_visual"))),
            "vel": abs(_num(obj, "vel")),
            "vida": _num(obj, "vida", 1.0),
            "retornando": bool(getattr(obj, "retornando", False)),
            "timer": None if timer is None else _real(timer),
            "explodiu": bool(getattr(obj, "explodiu", False)),
            "dono": dono,
        }

    def _vfx_novos(self, sim) -> dict:
        """Os objetos de VFX que NASCERAM desde o passo anterior, lista a lista
        (``_LISTAS_VFX``). A sonda reconhece o que ja viu pela identidade,
        lembrada por ``weakref``: nao prolonga a vida de nada, e um ``id``
        reciclado (objeto novo no endereco de um morto) conta como novo."""
        novos = {}
        for nome, caminho in _LISTAS_VFX:
            dono = sim
            for parte in caminho[:-1]:
                dono = getattr(dono, parte, None)
            itens = _lista(getattr(dono, caminho[-1], None)) if dono is not None else []
            vistos = self._vfx_vistos.get(nome, {})
            atuais = {}
            nascidos = []
            for obj in itens:
                ref = vistos.get(id(obj))
                if ref is None or _referido(ref) is not obj:
                    ref = _referencia(obj)
                    nascidos.append(obj)
                atuais[id(obj)] = ref
            self._vfx_vistos[nome] = atuais
            novos[nome] = nascidos
        return novos

    def _distancia(self, slot: str, lutador, x: float, y: float) -> float:
        """Distancia do ponto ao lutador AGORA ou no passo anterior (a menor):
        o golpe acontece no meio do passo, e o knockback do mesmo passo ja
        levou o corpo para longe (1,2 m num passo, medido no duelo_00014)."""
        lx, ly = _xy(getattr(lutador, "pos", None))
        d = math.hypot(lx - x, ly - y)
        canais = self.lutadores.get(slot) if isinstance(slot, str) else None
        if canais and len(canais["x"]) >= 2:
            d = min(d, math.hypot(_real(canais["x"][-2]) - x, _real(canais["y"][-2]) - y))
        return d

    def _mais_perto(self, lutadores: dict, x: float, y: float, *, exceto=None,
                    limite: float | None = None) -> str | None:
        melhor, distancia = None, None
        for slot, lutador in lutadores.items():
            if lutador is None or slot == exceto:
                continue
            d = self._distancia(slot, lutador, x, y)
            if (limite is None or d <= limite) and (distancia is None or d < distancia):
                melhor, distancia = slot, d
        return melhor

    def _danificados(self, tipo: str, i: int) -> list[tuple]:
        """Traps/summons que perderam vida NESTE passo ou deixaram de existir
        nele: ``(id, x, y, raio, dono)``. Sao os alvos que um projetil pode ter
        encontrado antes de um lutador."""
        saida = []
        for trilha in self.objetos:
            if trilha.fixos.get("tipo") != tipo or trilha.i1 not in (i, i - 1):
                continue
            hp = trilha.canais.get("hp") or []
            if trilha.i1 == i and not (len(hp) >= 2 and hp[-1] < hp[-2] - 1e-9):
                continue
            if tipo == "trap":
                raio = math.hypot(_real(trilha.fixos.get("largura")),
                                  _real(trilha.fixos.get("altura"))) / 2.0
            else:
                raio = _real(trilha.fixos.get("raio"), 0.8)
            saida.append((trilha.id, _real(trilha.canais["x"][-1]),
                          _real(trilha.canais["y"][-1]), raio, trilha.fixos.get("dono")))
        return saida

    def _analisar_voos(self, sim, lutadores: dict, novos: dict, feridos: dict) -> list[dict]:
        """Por que cada projetil/orbe que voava no passo anterior sumiu neste,
        onde cada impacto de projetil aconteceu, explosoes e choques.

        Devolve os eventos ``refletido``, ``choque``, ``projetil_fim`` e
        ``explosao`` (nesta ordem) e deixa em ``self._impactos`` o ponto do
        impacto por lutador atingido, para o ``acerto`` do mesmo passo.
        """
        self._impactos = {}
        dt = self._dt
        eventos: list[dict] = list(self._reflexoes)

        def candidato(m: dict, acabou: bool) -> dict:
            obj = _referido(m["ref"]) if (acabou and m["ref"] is not None) else None
            x, y = m["x"], m["y"]
            if obj is not None:
                # ainda vivo (a fonte de impacto fica lembrada pelo alvo por
                # ~1 s): o ponto FINAL exato, e nao a amostra do passo anterior
                x, y = _real(getattr(obj, "x", x), x), _real(getattr(obj, "y", y), y)
            elif acabou:
                # morto: a ultima amostra MAIS o ultimo deslocamento (o motor
                # anda antes de colidir; so o choque acontece antes de andar)
                x, y = x + m["dx"], y + m["dy"]
            return {"m": m, "obj": obj, "x": x, "y": y, "antes": (m["x"], m["y"]),
                    "tol": m["r"] + m["vel"] * dt + FOLGA_M}

        fins = [candidato(m, True) for tid, m in self._voando.items()
                if tid not in self._voando_agora]
        todos = fins + [candidato(m, False) for m in self._voando_agora.values()]

        def perto(x: float, y: float, lista: list, extra: float = 0.0):
            melhor, distancia = None, None
            for c in lista:
                cx, cy = c.get("ponto", (c["x"], c["y"]))
                d = math.hypot(cx - x, cy - y)
                if d <= c["tol"] + extra and (distancia is None or d < distancia):
                    melhor, distancia = c, d
            return melhor

        # 1. o ponto de impacto: o flash "magic" nasce na posicao do projetil
        #    no instante do acerto (simulacao._atualizar_projeteis). Orbe nao
        #    acende flash (um orbe orbitando ao lado do alvo roubava o flash
        #    do projetil que acertou); e quem sumiu vem antes de quem continua
        #    voando (so o perfurante acerta e segue).
        def sem_orbe(lista):
            return [c for c in lista if c["m"]["objeto"] != "orbe" and "ponto" not in c]

        orfaos = []
        for flash in novos.get("flash", ()):
            if str(getattr(flash, "tipo", "")) != "magic":
                continue
            px, py = _em_metros(flash)
            c = perto(px, py, sem_orbe(fins)) or perto(px, py, sem_orbe(todos[len(fins):]))
            if c is not None:
                c["ponto"] = (px, py)
            else:
                # projetil que nasceu e acertou no MESMO passo: nunca teve
                # trilha (medido: a flecha de 93 de dano do Orion, passo 105)
                orfaos.append((px, py))
        # 2. choque no ar: MagicClash no ponto medio dos dois, que somem juntos
        for clash in novos.get("choque", ()):
            cx, cy = _em_metros(clash)
            pares = [c for c in fins if "motivo" not in c
                     and math.hypot(c["antes"][0] - cx, c["antes"][1] - cy) <= c["tol"] + 0.5]
            for c in pares:
                c["motivo"] = "choque"
                if c["obj"] is None:
                    c["x"], c["y"] = c["antes"]
            eventos.append({
                "tipo": "choque", "x": _r(cx), "y": _r(cy),
                "origem": "projeteis" if pares else "armas",
                "cor1": _cor(getattr(clash, "cor1", None)),
                "cor2": _cor(getattr(clash, "cor2", None)),
                "projeteis": [c["m"]["id"] for c in pares] or None,
            })
        # 3. o motivo de cada fim
        traps = self._danificados("trap", self.i)
        summons = self._danificados("summon", self.i)
        for c in fins:
            m = c["m"]
            motivo, extra = c.get("motivo"), {}
            if motivo is None:
                motivo, extra = self._motivo_do_fim(c, lutadores, novos, feridos,
                                                    traps, summons, dt)
            if motivo == "acerto" and extra.get("alvo") in ("p1", "p2"):
                self._impactos.setdefault(extra["alvo"], {
                    "ponto": [_r(c.get("ponto", (c["x"], c["y"]))[0]),
                              _r(c.get("ponto", (c["x"], c["y"]))[1])],
                    "projetil": m["id"]})
            ponto = c.get("ponto")
            eventos.append({
                "tipo": "projetil_fim", "id": m["id"], "objeto": m["objeto"],
                "dono": m["dono"], "motivo": motivo,
                "x": _r(ponto[0] if ponto else c["x"]), "y": _r(ponto[1] if ponto else c["y"]),
                "elemento": m["elemento"], **extra,
            })
        for px, py in orfaos:
            alvo = self._alvo_do_impacto(lutadores, feridos, px, py, None, FOLGA_M)
            if alvo is not None:
                self._impactos.setdefault(alvo, {"ponto": [_r(px), _r(py)]})
        # o perfurante acerta e continua voando: o ponto vale do mesmo jeito
        for c in todos[len(fins):]:
            if "ponto" in c:
                alvo = self._alvo_do_impacto(lutadores, feridos, *c["ponto"],
                                             c["m"]["dono"], c["tol"])
                if alvo is not None:
                    self._impactos.setdefault(alvo, {
                        "ponto": [_r(c["ponto"][0]), _r(c["ponto"][1])],
                        "projetil": c["m"]["id"]})
        # 4. explosoes: a DramaticExplosion do acerto de projetil (elemento) e
        #    o flash "explosion" das areas (timer, raio de explosao, meteoro)
        for explosao in novos.get("explosao", ()):
            ex, ey = _em_metros(explosao)
            c = self._casar(ex, ey, fins, todos[len(fins):], perto)
            eventos.append({
                "tipo": "explosao", "origem": "impacto", "x": _r(ex), "y": _r(ey),
                "elemento": str(getattr(explosao, "elemento", "") or "") or None,
                "tamanho": _r(getattr(explosao, "tamanho", 1.0), 2),
                "projetil": None if c is None else c["m"]["id"],
            })
        for flash in novos.get("flash", ()):
            if str(getattr(flash, "tipo", "")) != "explosion":
                continue
            ex, ey = _em_metros(flash)
            c = self._casar(ex, ey, fins, todos[len(fins):], perto)
            eventos.append({
                "tipo": "explosao", "origem": "area", "x": _r(ex), "y": _r(ey),
                "elemento": None if c is None else c["m"]["elemento"],
                "cor": _cor(getattr(flash, "cor", None)),
                "tamanho": _r(_num(flash, "tamanho_base", 30.0) / 30.0, 2),
                "projetil": None if c is None else c["m"]["id"],
            })
        return eventos

    @staticmethod
    def _casar(x: float, y: float, fins: list, voando: list, perto):
        """O projetil (nao orbe) de uma explosao: quem sumiu neste passo antes
        de quem continua voando, com meio metro a mais de folga."""
        for lista in (fins, voando):
            c = perto(x, y, [c for c in lista if c["m"]["objeto"] != "orbe"], 0.5)
            if c is not None:
                return c
        return None

    def _alvo_do_impacto(self, lutadores: dict, feridos: dict, x: float, y: float,
                         dono, tol: float) -> str | None:
        """Quem o projetil acertou: o lutador (que nao e o dono) que APANHOU
        neste passo com o ponto ao alcance; senao o mais perto ao alcance
        (o acerto que o escudo ou a esquiva zeraram tambem acende o flash)."""
        limite = self._alcance_do_corpo(lutadores) + tol
        for slot, lutador in lutadores.items():
            if (lutador is not None and slot != dono and feridos.get(slot)
                    and self._distancia(slot, lutador, x, y) <= limite + 1.0):
                return slot
        return self._mais_perto(lutadores, x, y, exceto=dono, limite=limite)

    @staticmethod
    def _alcance_do_corpo(lutadores: dict) -> float:
        """O maior raio DESENHADO dos dois (o projetil acerta o raio fisico
        x 1,2, sempre menor que isso): a folga para achar quem foi atingido."""
        return max((_num(getattr(l, "dados", None), "tamanho", 1.7) / 2.0
                    for l in lutadores.values() if l is not None), default=0.85)

    def _motivo_do_fim(self, c: dict, lutadores: dict, novos: dict, feridos: dict,
                       traps: list, summons: list, dt: float) -> tuple[str, dict]:
        """O motivo de UM fim de voo, na ordem em que o motor decide
        (``simulacao._atualizar_projeteis``): o choque ja veio; o proprio
        ``atualizar`` do projetil (timer de explosao, vida, retorno) roda antes
        de qualquer colisao; depois trap, bloqueio/desvio e o alvo."""
        m, obj = c["m"], c["obj"]
        fx, fy = c["x"], c["y"]
        folga = 1e-6
        if obj is not None:
            explodiu = bool(getattr(obj, "explodiu", False)) and not m["explodiu"]
            vida_acabou = _num(obj, "vida", 1.0) <= 1e-9
        else:
            explodiu = m["timer"] is not None and not m["explodiu"] and m["timer"] <= dt + folga
            vida_acabou = m["vida"] <= dt + folga
        if explodiu:
            return "explodiu", {}
        if vida_acabou:
            return "expirou", {}
        dono = lutadores.get(m["dono"]) if m["dono"] else None
        if m["retornando"] and dono is not None:
            dx, dy = _xy(getattr(dono, "pos", None))
            if math.hypot(dx - fx, dy - fy) <= max(0.5, m["vel"] * dt) + c["tol"]:
                return "voltou", {}
        for ident, tx, ty, raio, dono_trap in traps:
            if dono_trap != m["dono"] and math.hypot(tx - fx, ty - fy) <= raio + c["tol"]:
                return "trap", {"alvo_objeto": ident}
        if m["objeto"] == "orbe":
            # o orbe so acaba por vida, choque, trap ou colisao com o alvo
            # (simulacao._atualizar_orbes_magicos; nao ha bloqueio de orbe):
            # o que sobrou e acerto, mesmo quando o dano foi zero
            alvo = self._alvo_do_impacto(lutadores, feridos, fx, fy, m["dono"], c["tol"])
            if alvo is None:
                alvo = next((s for s, l in lutadores.items()
                             if l is not None and s != m["dono"]), None)
            return "acerto", {"alvo": alvo}
        if "ponto" in c:
            px, py = c["ponto"]
            alvo = self._alvo_do_impacto(lutadores, feridos, px, py, m["dono"], c["tol"])
            if alvo is not None:
                return "acerto", {"alvo": alvo}
            for ident, sx, sy, raio, _dono in summons:
                if math.hypot(sx - px, sy - py) <= raio + c["tol"]:
                    return "acerto", {"alvo_objeto": ident}
            return "acerto", {}
        for bloqueio in novos.get("bloqueio", ()):
            bx, by = _em_metros(bloqueio)
            if math.hypot(bx - fx, by - fy) <= c["tol"] + 0.5:
                return "bloqueado", {"defesa": "escudo",
                                     "alvo": self._mais_perto(lutadores, bx, by)}
        for flash in novos.get("flash", ()):
            if str(getattr(flash, "tipo", "")) != "clash":
                continue
            px, py = _em_metros(flash)
            if math.hypot(px - fx, py - fy) <= c["tol"]:
                return "bloqueado", {"defesa": "parry",
                                     "alvo": self._mais_perto(lutadores, px, py,
                                                              exceto=m["dono"])}
        for slot, lutador in lutadores.items():
            if lutador is None or slot == m["dono"]:
                continue
            flags = self.lutadores[slot]["flags"][-2:]
            em_dash = any(int(v) & (1 << FLAGS.index("dash")) for v in flags)
            alcance = _num(lutador, "raio_fisico", 0.425) + 0.5 + c["tol"]
            if em_dash and self._distancia(slot, lutador, fx, fy) <= alcance:
                return "bloqueado", {"defesa": "dash", "alvo": slot}
        # rede de seguranca: o flash do acerto nao casou (o teto de VFX, por
        # exemplo), mas o alvo apanhou neste passo com o projetil ao alcance
        for slot, lutador in lutadores.items():
            if lutador is None or slot == m["dono"] or not feridos.get(slot):
                continue
            if (self._distancia(slot, lutador, fx, fy)
                    <= _num(lutador, "raio_fisico", 0.425) * 1.2 + c["tol"]):
                return "acerto", {"alvo": slot}
        for ident, sx, sy, raio, _dono in summons:
            if math.hypot(sx - fx, sy - fy) <= raio + c["tol"]:
                return "acerto", {"alvo_objeto": ident}
        return "sumiu", {}

    @staticmethod
    def _estilo_do_texto(texto: str, valor, cor_base) -> str:
        if texto == "FATAL!":
            return "fatal"
        if valor is not None:
            return "execucao" if cor_base == COR_EXECUCAO else "dano"
        if texto.startswith("+"):
            return "cura"
        if texto == "CLASH!":
            return "clash"
        return "outro"

    def _eventos_de_texto(self, sim, lutadores: dict, *, base: bool = False) -> list[dict]:
        """Texto flutuante novo (numero de dano com a cor do efeito, a
        execucao em roxo, "FATAL!", cura, "CLASH!") e o numero que ACUMULOU
        (``FloatingText.acumular``: hit no mesmo alvo em < 0,35 s soma no
        texto que ja esta na tela). ``texto_id`` liga os dois."""
        eventos = []
        atuais = {}
        for txt in _lista(getattr(sim, "textos", None)):
            valor = getattr(txt, "valor", None)
            registro = self._textos.get(id(txt))
            if registro is not None and _referido(registro[0]) is txt:
                atuais[id(txt)] = (registro[0], registro[1], valor)
                if (not base and valor is not None and registro[2] is not None
                        and _real(valor) != _real(registro[2])):
                    eventos.append(self._texto(txt, registro[1], lutadores, acumulado=True))
                continue
            ident = self._proximo_texto
            self._proximo_texto += 1
            atuais[id(txt)] = (_referencia(txt), ident, valor)
            if not base:
                eventos.append(self._texto(txt, ident, lutadores))
        self._textos = atuais
        return eventos

    def _texto(self, txt, ident: int, lutadores: dict, *, acumulado: bool = False) -> dict:
        texto = str(getattr(txt, "texto", "") or "")
        valor = getattr(txt, "valor", None)
        cor = getattr(txt, "cor", None)
        cor_base = getattr(txt, "cor_base", cor)
        try:
            base = tuple(int(v) for v in tuple(cor_base)[:3])
        except (TypeError, ValueError):
            base = None
        x, y = _em_metros(txt)
        estilo = self._estilo_do_texto(texto, valor, base)
        # o texto nasce acima do alvo (30 a 50 px): o dono e quem esta perto
        slot = None if estilo == "clash" else self._mais_perto(lutadores, x, y + 0.8, limite=3.0)
        return {
            "tipo": "texto", "texto_id": ident, "texto": texto,
            "valor": None if valor is None else _r(valor, 2),
            "estilo": estilo, "cor": _cor(cor),
            "cor_base": None if _cor(cor_base) == _cor(cor) else _cor(cor_base),
            "execucao": True if (estilo == "fatal" and base == COR_FATAL_EXECUCAO) else None,
            "acumulado": True if acumulado else None,
            "slot": slot, "x": _r(x), "y": _r(y),
        }

    def _eventos_de_movimento(self, sim, novos: dict, lutadores: dict) -> list[dict]:
        """Os VFX de movimento que nasceram neste passo, um evento por
        lutador: afterimage (dash), motion blur (knockback), linhas de
        velocidade, poeira e o flash de recuperacao do
        ``MovementAnimationManager``. Poeira e linhas nao dizem o dono nem o
        tipo; o dono e o lutador mais perto (nascem na posicao dele) e o
        gatilho sai do conjunto e da altura (``z``) do lutador."""
        grupos: dict = {}

        def grupo(slot) -> dict:
            return grupos.setdefault(slot, {"vfx": []})

        for obj in novos.get("afterimage", ()):
            g = grupo(_slot_do_dono(sim, getattr(obj, "lutador", None)))
            g["vfx"].append("afterimage")
            tipo = getattr(getattr(obj, "movimento_tipo", None), "name", None)
            if tipo:
                g["tipo"] = str(tipo).lower()
        for obj in novos.get("blur", ()):
            g = grupo(_slot_do_dono(sim, getattr(obj, "lutador", None)))
            g["vfx"].append("blur")
            g["dir"] = _r(math.degrees(_num(obj, "direcao")), 1)
            g["intensidade"] = _r(_num(obj, "intensidade", 1.0), 2)
        for nome in ("linhas", "poeira", "recuperacao"):
            for obj in novos.get(nome, ()):
                g = grupo(self._mais_perto(lutadores, *_em_metros(obj)))
                g["vfx"].append(nome)
                if nome == "linhas":
                    g.setdefault("dir", _r(math.degrees(_num(obj, "direcao")), 1))
                    linhas = _lista(getattr(obj, "lines", None))
                    cor = getattr(linhas[0], "cor", None) if linhas else None
                    try:
                        cor = tuple(int(v) for v in tuple(cor)[:3])
                    except (TypeError, ValueError):
                        cor = None
                    if cor == COR_LINHAS_KNOCKBACK:
                        g["linhas_knockback"] = True
                g.setdefault("xy", _em_metros(obj))
        eventos = []
        for slot in ("p1", "p2", None):
            g = grupos.get(slot)
            if not g:
                continue
            vfx = [nome for nome in VFX_MOVIMENTO if nome in g["vfx"]]
            z = self.lutadores[slot]["z"][-2:] if slot in self.lutadores else []
            if "afterimage" in vfx:
                gatilho = "dash"
            elif "blur" in vfx or g.get("linhas_knockback"):
                gatilho = "knockback"
            elif "recuperacao" in vfx:
                gatilho = "recuperacao"
            elif len(z) == 2 and z[0] > 0.15 and z[1] <= 0.05:
                gatilho = "aterrissagem"
            elif len(z) == 2 and z[0] <= 0.05 and z[1] > 0.1:
                gatilho = "pulo"
            elif "linhas" in vfx:
                gatilho = "corrida"
            else:
                gatilho = "poeira"
            lutador = lutadores.get(slot) if slot else None
            x, y = _xy(getattr(lutador, "pos", None)) if lutador is not None else g.get("xy", (0.0, 0.0))
            eventos.append({
                "tipo": "movimento", "slot": slot, "gatilho": gatilho, "vfx": vfx,
                "x": _r(x), "y": _r(y), "dir": g.get("dir"),
                "intensidade": g.get("intensidade"), "dash": g.get("tipo"),
            })
        return eventos

    @staticmethod
    def _tier_do(lutador) -> str | None:
        if lutador is None:
            return None
        return _tier_por_forca(_num(getattr(lutador, "dados", None), "forca", 5.0))

    def _dados_skill(self, nome: str) -> dict:
        try:
            from neural_fights.core.skills import get_skill_data
            data = get_skill_data(nome) or {}
        except Exception:
            data = {}
        try:
            from neural_fights.utils.palette import get_element_from_skill
            elemento = get_element_from_skill(nome, data)
        except Exception:
            elemento = str(data.get("elemento", "") or "")
        return {"tipo_skill": data.get("tipo"), "elemento": elemento}

    # ------------------------------------------------------------ anexos
    def anexar_sons(self, sons, versao_sons: int = 1) -> None:
        """A secao ``sons`` e a lista da Onda 16A, sem traducao nenhuma.

        Formato e relogio em ``docs/palco/sons.md``: ``t`` e o relogio do video
        do gravador (quantizado ao quadro de 1/30 s). Um som pedido num passo
        impar aparece no passo par seguinte, o primeiro quadro de 30 fps que
        mostra o resultado daquele passo.
        """
        self.sons = {"versao": int(versao_sons), "relogio": "video",
                     "itens": [dict(item) for item in (sons or ())]}

    def definir_remapeamento(self, trechos) -> None:
        """Trechos ``(inicio, duracao[, velocidade])`` no relogio da gravacao.

        ``(inicio, duracao)`` e exatamente o que ``highlights.planejar_corte_tedio``
        devolve (corte de tedio). ``velocidade`` < 1 e camera lenta do PALCO
        (0,5 = metade da velocidade); ausente vale 1.
        """
        lista = []
        for trecho in trechos or ():
            inicio, duracao = _real(trecho[0]), _real(trecho[1])
            velocidade = _real(trecho[2], 1.0) if len(trecho) > 2 else 1.0
            if duracao <= 0.0 or velocidade <= 0.0:
                continue
            lista.append([round(inicio, 4), round(duracao, 4), round(velocidade, 4)])
        self.remapeamento = {"relogio": "gravacao", "trechos": lista}

    # ------------------------------------------------------------ saida
    def documento(self, resultado: dict | None = None) -> dict:
        n = self.i + 1
        tabelas = {nome: list(tabela.itens) for nome, tabela in self.tabelas.items()}
        tabelas["planos"] = [rotulo for (_tipo, rotulo) in self.tabelas["planos"].itens]
        tabelas["planos_tipo"] = [tipo for (tipo, _rotulo) in self.tabelas["planos"].itens]
        tabelas["fases"] = list(FASES)
        tabelas["flags"] = list(FLAGS)
        return {
            "formato": FORMATO,
            "versao": VERSAO,
            "revisao": REVISAO,
            "hz": self.hz,
            "n": n,
            "duracao": round(n / self.hz, 4),
            "unidades": {"distancia": "m", "angulo": "graus (0 = +x, horario na tela)",
                         "tempo": "s", "cor": "0xRRGGBB"},
            "ppm_motor": PPM,
            **self.cabecalho,
            "tabelas": tabelas,
            "trilhas": {
                "global": self.globais,
                "camera": self.camera,
                "lutadores": self.lutadores,
                "objetos": [trilha.documento() for trilha in self.objetos],
                "efeitos": [trilha.documento() for trilha in self.efeitos],
            },
            "eventos": self.eventos,
            "sons": self.sons,
            "remapeamento": self.remapeamento,
            "resultado": resultado,
        }


# ------------------------------------------------------------ hash de estado
def _estado_rng(rng):
    """Impressao do estado de um gerador. ``hash`` de tupla de inteiros e
    deterministico entre processos (so str/bytes usam PYTHONHASHSEED) e custa
    uma fracao do ``repr`` dos 625 inteiros do Mersenne Twister."""
    obter = getattr(rng, "getstate", None)
    return hash(obter()) if callable(obter) else None


def _itens(dicionario) -> tuple:
    if not isinstance(dicionario, dict):
        return ()
    return tuple(sorted((str(k), repr(v)) for k, v in dicionario.items()))


def _estado_lutador(lutador) -> tuple:
    if lutador is None:
        return ()
    brain = getattr(lutador, "brain", None)
    timers = getattr(lutador, "status_timers", None)
    try:
        status = tuple(sorted((s, timers.get(s)) for s in timers.ativos())) if timers else ()
    except Exception:
        status = ()
    plano = _dict_de(brain).get("plano") if brain is not None else None
    emocoes = _dict_de(brain).get("emocoes") if brain is not None else None
    tell = getattr(brain, "tell_atual", None) if brain is not None else None
    return (
        tuple(getattr(lutador, "pos", ()) or ()), tuple(getattr(lutador, "vel", ()) or ()),
        getattr(lutador, "z", None), getattr(lutador, "vel_z", None),
        getattr(lutador, "vida", None), getattr(lutador, "mana", None),
        getattr(lutador, "estamina", None), getattr(lutador, "angulo_olhar", None),
        getattr(lutador, "angulo_arma_visual", None), getattr(lutador, "atacando", None),
        getattr(lutador, "timer_animacao", None), getattr(lutador, "cooldown_ataque", None),
        getattr(lutador, "ataque_id", None), getattr(lutador, "morto", None),
        getattr(lutador, "combo_contra", None), getattr(lutador, "combo_contra_timer", None),
        getattr(lutador, "flash_timer", None), getattr(lutador, "invencivel_timer", None),
        getattr(lutador, "dash_timer", None), getattr(lutador, "agarrao_timer", None),
        getattr(lutador, "canalizando", None), getattr(lutador, "weapon_anim_lunge", None),
        len(getattr(lutador, "pos_historico", None) or ()),
        status,
        tuple((type(d).__name__, getattr(d, "tipo", None), getattr(d, "vida", None),
               getattr(d, "tick_timer", None)) for d in getattr(lutador, "dots_ativos", None) or ()),
        tuple((getattr(b, "nome", None), getattr(b, "vida", None), getattr(b, "escudo_atual", None),
               getattr(b, "ativo", None)) for b in getattr(lutador, "buffs_ativos", None) or ()),
        _itens(getattr(lutador, "contadores_luta", None)),
        _itens(getattr(lutador, "cd_skills", None)),
        _estado_rng(getattr(lutador, "rng_runtime", None)),
        None if brain is None else (
            _dict_de(brain).get("_acao_atual"), getattr(brain, "tempo_combate", None),
            _itens(tell) if isinstance(tell, dict) else repr(tell),
            None if plano is None else (getattr(plano, "tipo", None),
                                        getattr(plano, "progresso", None),
                                        getattr(plano, "expira_em", None)),
            None if emocoes is None else getattr(emocoes, "humor", None),
        ),
    )


def _estado_mundo(sim) -> tuple:
    listas = []
    for nome in ("projeteis", "areas", "beams", "summons", "traps", "portais"):
        listas.append(tuple(
            (type(o).__name__, getattr(o, "x", None), getattr(o, "y", None),
             getattr(o, "vida", None), getattr(o, "ativo", None))
            for o in getattr(sim, nome, None) or ()))
    for slot in ("p1", "p2"):
        lutador = getattr(sim, slot, None)
        listas.append(tuple(
            (getattr(o, "x", None), getattr(o, "y", None), getattr(o, "estado", None),
             getattr(o, "ativo", None))
            for o in getattr(lutador, "buffer_orbes", None) or ()))
    hitstop = getattr(getattr(sim, "game_feel", None), "hit_stop", None)
    agarrao = _dict_de(sim).get("_agarrao")
    arena = getattr(sim, "arena", None)
    return (
        getattr(sim, "time_scale", None), getattr(sim, "slow_mo_timer", None),
        getattr(sim, "letterbox_timer", None), getattr(sim, "round_finalizado", None),
        getattr(sim, "vencedor", None), getattr(sim, "vencedor_round_side", None),
        getattr(hitstop, "timer_ativo", None), getattr(hitstop, "total_hitstops", None),
        None if not isinstance(agarrao, dict) else (agarrao.get("restante"),
                                                    agarrao.get("desfecho")),
        tuple(listas),
        tuple((getattr(o, "solido", None), getattr(o, "hp", None))
              for o in getattr(arena, "obstaculos", None) or ()),
        tuple((e.get("restante"), e.get("dano")) for e in _dict_de(sim).get("hits_ecoados") or ()
              if isinstance(e, dict)),
    )


def _estado_camera(sim) -> tuple:
    cam = getattr(sim, "cam", None)
    if cam is None:
        return ()
    return tuple(getattr(cam, nome, None) for nome in (
        "x", "y", "zoom", "target_zoom", "offset_x", "offset_y", "shake_timer",
        "_diretor_zoom_suave", "_diretor_estavel_desde", "_diretor_movendo", "modo"))


def _estado_visual(sim) -> tuple:
    try:
        from neural_fights.effects import weapon_animations
        gerente = getattr(weapon_animations, "_weapon_animation_manager", None)
    except Exception:  # pragma: no cover
        gerente = None
    estados = getattr(getattr(gerente, "animator", None), "states", None) or {}
    animador = []
    for slot in ("p1", "p2"):
        estado = estados.get(id(getattr(sim, slot, None)))
        animador.append(None if estado is None else (
            estado.is_attacking, estado.attack_timer, estado.current_phase.value,
            estado.angle_offset, estado.lunge, estado.attack_pattern))
    arena = getattr(sim, "arena", None)
    # revisao 3: a sonda passou a LER estas listas; se um dia mexer nelas
    # (esvaziar, reordenar, somar num texto), e aqui que aparece
    movimento = getattr(sim, "movement_anims", None)
    magia = getattr(sim, "magic_vfx", None)
    return (
        tuple(len(getattr(sim, nome, None) or ()) for nome in (
            "particulas", "textos", "shockwaves", "impact_flashes", "hit_sparks",
            "decals", "block_effects", "dash_trails", "magic_clashes")),
        tuple(len(getattr(movimento, nome, None) or ()) for nome in (
            "afterimage_trails", "dust_clouds", "speed_lines", "motion_blurs",
            "recovery_flashes")),
        len(getattr(magia, "explosions", None) or ()),
        tuple((getattr(t, "texto", None), getattr(t, "vida", None))
              for t in getattr(sim, "textos", None) or ()),
        len(getattr(arena, "colisoes_recentes", None) or ()),
        getattr(sim, "tempo_visual", None),
        tuple(animador),
    )


def hash_estado(sim) -> tuple[str, str]:
    """Dois hashes do estado DESTE passo, sem mudar nada: ``(luta, tudo)``.

    - ``luta``: lutadores (corpo, timers, status, contadores, cooldowns, o RNG
      de cada um, a mente), o mundo (projeteis, areas, obstaculos, agarrao,
      hit-stop) e a camera. E o que decide a luta e o enquadramento.
    - ``tudo``: ``luta`` + o ``random`` GLOBAL (de onde saem particulas,
      tremor e a variante do som), as listas de VFX, o relogio visual e o
      animador de arma. Se uma sonda consumir um numero aleatorio que seja,
      ou tocar num efeito, e aqui que aparece.
    """
    luta = (tuple(_estado_lutador(getattr(sim, s, None)) for s in ("p1", "p2")),
            _estado_mundo(sim), _estado_camera(sim))
    h_luta = hashlib.blake2b(repr(luta).encode("utf-8"), digest_size=12).hexdigest()
    extra = (_estado_rng(random), _estado_visual(sim))
    h_tudo = hashlib.blake2b((h_luta + repr(extra)).encode("utf-8"),
                             digest_size=12).hexdigest()
    return h_luta, h_tudo


# ------------------------------------------------------------ o laco
def _zerar_animador_de_arma() -> None:
    """Estado de PROCESSO NOVO para o animador de arma.

    ``effects.weapon_animations`` guarda o gerenciador num global de modulo que
    o ``Simulador.close()`` nao zera, e os estados sao chaveados por
    ``id(lutador)``: se o id de um lutador morto for reciclado, um segundo
    Simulador no mesmo processo herdaria o estado dele. E PRECAUCAO, nao
    defeito visto: em 28/09/2026, duas lutas iguais no mesmo processo SEM
    zerar deram o mesmo hash nos 2670 passos. O gravador roda uma luta por
    processo; este laco e os testes comecam do mesmo ponto que ele.
    """
    try:
        from neural_fights.effects import weapon_animations
    except Exception:  # pragma: no cover
        return
    weapon_animations._weapon_animation_manager = None


def gravar_timeline(*, p1: str, p2: str, seed: int = 0, cenario: str = "Arena Pequena",
                    resolucao=(1080, 1920), camera_modo: str | None = "DIRETOR",
                    camera_largura_min_m: float | None = None,
                    camera_espera_zoom_in: float | None = None,
                    nomes_exibicao: dict | None = None, hud: bool = False,
                    fps_video: int = 30, max_duracao: float = 120.0,
                    cauda_pos_ko: float = 3.5, headless: bool = False,
                    desenhar: bool = False, sonda: bool = True, hashes: bool = False,
                    roster_provider=None, anotar_som: bool | None = None,
                    corrente_v2: bool | None = None) -> dict:
    """Roda a luta com o MESMO laco do gravador e devolve a timeline.

    Os mesmos numeros de ``fight_recorder.gravar_luta`` (60 Hz, captura a cada
    ``60 / fps_video`` passos, ``avancar_relogio`` com o slow-mo do KO, cauda
    de ``cauda_pos_ko`` s no relogio do video): a timeline tem exatamente os
    passos que o video teria, e o quadro k do video e o passo ``k * 60 /
    fps_video``.

    - ``desenhar=True`` chama ``sim.desenhar()`` a cada passo, como o gravador
      (a sonda roda ANTES dele). ``False`` pula o desenho, que e 90% do custo.
    - ``headless=True`` usa o modo headless do motor (sem display, VFX
      degradado e sem som); so para medir.
    - ``sonda=False`` roda sem a sonda (o lado "sem" do teste de determinismo).
    - ``hashes=True`` devolve ``hash_estado`` de cada passo.
    - ``anotar_som`` (padrao: sim, fora do headless) poe o ``AnotadorDeAudio``
      da Onda 16A no lugar do AudioManager, como o gravador, e a secao
      ``sons`` sai preenchida com o som REAL da luta.
    - ``corrente_v2`` carimba a chave da corrente nova no match_config
      (``None`` = nao carimba = a corrente antiga, como toda luta gravada).

    Devolve ``{"resultado", "timeline" (dict ou None), "hashes" (lista ou None)}``.
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if desenhar and headless:
        raise ValueError("desenhar exige headless=False (o headless nao tem display)")
    import pygame

    from neural_fights.simulation.simulacao import Simulador
    from neural_fights.utils.config import FPS

    largura, altura = (int(resolucao[0]) // 2 * 2, int(resolucao[1]) // 2 * 2)
    match_config = {
        "p1_nome": p1, "p2_nome": p2, "cenario": cenario, "best_of": 1,
        "portrait_mode": altura > largura, "modo_live": True,
        "overlays": {"hud": bool(hud), "analise": False, "hitbox_debug": False},
        "resolucao": [largura, altura],
    }
    if camera_modo:
        match_config["camera_modo"] = str(camera_modo).upper()
    if camera_largura_min_m:
        match_config["camera_largura_min_m"] = float(camera_largura_min_m)
    if camera_espera_zoom_in:
        match_config["camera_espera_zoom_in"] = float(camera_espera_zoom_in)
    if nomes_exibicao:
        match_config["nomes_exibicao"] = dict(nomes_exibicao)
    if corrente_v2 is not None:
        # Chave da corrente nova (core/corrente.py). Ausente = a antiga.
        match_config["corrente_v2"] = bool(corrente_v2)
    extras = {}
    if roster_provider is not None:
        extras["roster_provider"] = roster_provider
    if anotar_som is None:
        anotar_som = not headless
    anotador = None
    versao_sons = None
    if anotar_som:
        # O mesmo par do gravador (Onda 16A): a seed da luta semeia o pitch.
        from neural_fights.effects.audio_anotador import VERSAO_SONS, AnotadorDeAudio
        anotador = AnotadorDeAudio(seed=seed)
        anotador.passo = 0
        versao_sons = VERSAO_SONS
        extras["audio"] = anotador

    _zerar_animador_de_arma()
    sim = Simulador(match_config=match_config, headless=headless, seed=seed, **extras)
    sonda_tl = SondaTimeline() if sonda else None
    lista_hashes = [] if hashes else None
    try:
        if sonda_tl is not None:
            sonda_tl.on_inicio(sim, seed=seed, p1=p1, p2=p2, cenario=cenario)
        passo = 1.0 / FPS
        a_cada = max(1, round(FPS / fps_video))
        indice = 0
        capturados = 0
        t_jogo = 0.0
        t_ko_video = None
        duracao_luta = None
        while True:
            t_video = capturados / fps_video
            if t_video >= max_duracao:
                break
            if anotador is not None:
                # o relogio do som e o do gravador: o quadro que captura o passo
                anotador.t_video = t_video
                anotador.passo = indice
            if not headless:
                pygame.event.pump()
            dt = sim.avancar_relogio(passo)
            sim.update(dt)
            t_jogo += dt
            if sonda_tl is not None:
                sonda_tl.on_frame(sim, t_video, t_jogo=t_jogo)
            if desenhar:
                sim.desenhar()
            if lista_hashes is not None:
                lista_hashes.append(hash_estado(sim))
            if indice % a_cada == 0:
                capturados += 1
            indice += 1
            if sim.round_finalizado:
                if t_ko_video is None:
                    t_ko_video = t_video
                    duracao_luta = t_jogo
                elif t_video - t_ko_video >= cauda_pos_ko:
                    break

        def razao(lutador) -> float:
            return max(0.0, float(lutador.vida)) / max(1e-9, float(lutador.vida_max))

        vencedor = getattr(sim, "vencedor", None)
        empate = vencedor in (None, "", "EMPATE")
        resultado = {
            "vencedor": None if empate else vencedor,
            "vencedor_slot": getattr(sim, "vencedor_round_side", None),
            "empate": empate,
            "motivo": "knockout" if t_ko_video is not None else "time_limit",
            "duracao_jogo": round(duracao_luta if duracao_luta is not None else t_jogo, 4),
            "duracao_video": round(capturados / fps_video, 4),
            "ko_em_video": None if t_ko_video is None else round(t_ko_video, 4),
            "passos": indice,
            "quadros_video": capturados,
            "passos_por_quadro": a_cada,
            "hp_final": {"p1": round(razao(sim.p1) * 100, 2), "p2": round(razao(sim.p2) * 100, 2)},
            "seed": seed,
        }
        if anotador is not None:
            resultado["sons"] = len(anotador.sons)
        timeline = None
        if sonda_tl is not None:
            if anotador is not None:
                sonda_tl.anexar_sons(anotador.sons, versao_sons)
            timeline = sonda_tl.documento(resultado=resultado)
        return {"resultado": resultado, "timeline": timeline, "hashes": lista_hashes}
    finally:
        sim.close()


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="Grava a timeline v1 de uma luta (o contrato do palco), sem video")
    parser.add_argument("--p1", required=True)
    parser.add_argument("--p2", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cenario", default="Arena Pequena")
    parser.add_argument("--resolucao", default="1080x1920", metavar="LxA")
    parser.add_argument("--camera", default="DIRETOR")
    parser.add_argument("--camera-largura-min", type=float, default=None)
    parser.add_argument("--camera-espera-zoom", type=float, default=None)
    parser.add_argument("--desenhar", action="store_true",
                        help="chama desenhar() a cada passo, como o gravador")
    parser.add_argument("--saida", required=True, help="arquivo .json da timeline")
    parser.add_argument("--compacto", default=None, choices=("zstd", "deflate", "gzip"),
                        help="grava tambem o container GCPF que o Godot abre nativo")
    return parser


def main(argv=None) -> int:
    from neural_fights.recording import timeline_arquivo

    args = build_parser().parse_args(argv)
    largura, altura = (int(p) for p in args.resolucao.lower().split("x"))
    saida = gravar_timeline(
        p1=args.p1, p2=args.p2, seed=args.seed, cenario=args.cenario,
        resolucao=(largura, altura), camera_modo=args.camera,
        camera_largura_min_m=args.camera_largura_min,
        camera_espera_zoom_in=args.camera_espera_zoom, desenhar=args.desenhar)
    doc = saida["timeline"]
    destino = Path(args.saida)
    tamanhos = {"json": timeline_arquivo.salvar(doc, destino)}
    if args.compacto:
        compacto = destino.with_suffix(f".{args.compacto}.gcpf")
        tamanhos[args.compacto] = timeline_arquivo.salvar(doc, compacto, compressao=args.compacto)
    print(json.dumps({"resultado": saida["resultado"], "bytes": tamanhos,
                      "problemas": timeline_arquivo.validar(doc)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
