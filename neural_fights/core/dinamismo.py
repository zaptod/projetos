# -*- coding: utf-8 -*-
"""Dinamismo (21/10/2026): corpo colado demais vira choque e afastamento.

Pedido do Adrian: "não quero os personagens colados um no outro muito
tempo; quero movimento e dinamismo nas lutas". Medido no lote da fila de
duelos (``tools/dinamismo_luta.py``), o colado longo é o corpo-a-corpo
em que ninguém sai: o verbo ofensivo orbita a 0,1 de avanço, a repulsão
só empurra 1-2 cm por passo, e depois de um agarrão os dois esperam 3 s
de recarga sem nada que os separe.

O ciclo (relógio do contato, recarga, VFX) vive no ``Simulador``; aqui só
as contas, PURAS e sem sorteio (a luta continua determinística pela seed
e nenhum stream de RNG anda a mais):

- ``acumular``: o relógio do colado sobe com o contato e esquece no
  dobro da velocidade quando os corpos se soltam (um buraco de um quadro
  não zera a conta; o olho não vê a folga);
- ``direcao_de_saida``: para onde cada corpo sai sem entrar na parede — a
  componente que empurraria contra a parede vira deslize ao longo dela, e
  no canto o corpo sai para o centro da arena;
- ``impulsos``: quanto cada um anda; quem não pode se mexer (agarrado,
  dormindo, canalizando parado) deixa o impulso inteiro para o outro;
- ``impulso_do_choque``: golpe que acerta colado descola os dois, e quem
  acertou "bate e sai" (``Simulador._sair_depois_do_choque``: recua ou
  circula por ``DINAMISMO_CHOQUE_SAIDA_S``).

Medido no lote de 60 lutas (31 duelos da fila de 21/10 + 29 sorteados),
motor de ``8f51d7bd`` → chave ligada: maior trecho colado 2,19 → 0,61 s na
mediana e 9,63 → 1,92 s no pior; tempo colado total 608 → 293 s (−52%).
Ver ``docs/sessoes/builds.md`` §14 (inclui o efeito nas classes).

Chave da LUTA: ``match_config["dinamismo"]``. Ausente, vale
``utils.config.DINAMISMO`` (desligada): toda luta gravada antes sai
idêntica bit a bit quando re-simulada (o mesmo desenho da corrente nova,
decisão ``corrente-seeds-antigas``: chave só para lutas novas).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

CHAVE = "dinamismo"


def chave_ligada(match_config=None) -> bool:
    """``match_config["dinamismo"]`` vale sobre o padrão do motor."""
    if isinstance(match_config, Mapping) and CHAVE in match_config:
        return bool(match_config.get(CHAVE))
    from neural_fights.utils.config import DINAMISMO

    return bool(DINAMISMO)


def _raio(lutador) -> float:
    try:
        return max(0.05, float(getattr(lutador, "raio_fisico", 0.45) or 0.45))
    except (TypeError, ValueError):
        return 0.45


def raio_desenhado(lutador) -> float:
    """O raio do disco que o vídeo DESENHA (``Simulador.desenhar_lutador``:
    ``tamanho / 2``). O da física (``raio_fisico``) é ``tamanho / 4``: a
    colisão só separa os corpos com os discos desenhados já sobrepostos até
    a metade — medido, 30% da luta com os discos se cobrindo."""
    try:
        return max(0.05, float(lutador.dados.tamanho) / 2.0)
    except (AttributeError, TypeError, ValueError):
        return 2.0 * _raio(lutador)


def _z(lutador) -> float:
    try:
        return float(getattr(lutador, "z", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def borda(p1, p2) -> float:
    """Distância entre os discos DESENHADOS (m); negativa = sobrepostos.

    O disco de quem pula ou voa é desenhado ``z`` acima do chão (o
    ``off_y`` do ``desenhar_lutador``): é a posição dele NA TELA que conta.
    Medido no ``duelo_00162``: o Druida voando a 1,5 m passou 6 s por cima
    do outro, e um teste "na mesma altura" não via."""
    dx = p2.pos[0] - p1.pos[0]
    dy = (p2.pos[1] - _z(p2)) - (p1.pos[1] - _z(p1))
    return math.hypot(dx, dy) - raio_desenhado(p1) - raio_desenhado(p2)


def colados(p1, p2) -> bool:
    """Os corpos estão "colados" para quem assiste: os discos desenhados a
    menos de ``DINAMISMO_COLADO_FRACAO_RAIO`` do raio desenhado médio (o
    critério do medidor)."""
    from neural_fights.utils.config import DINAMISMO_COLADO_FRACAO_RAIO

    limite = DINAMISMO_COLADO_FRACAO_RAIO * (raio_desenhado(p1) + raio_desenhado(p2)) / 2.0
    return borda(p1, p2) < limite


def vale_agora(estado) -> bool:
    """O afastamento vale até ``DINAMISMO_ATE_S`` de luta (``None`` = sempre).

    Depois disso o corpo a corpo fecha a luta: sem o teto, no corpus de 546
    lutas, as acima de 90 s iam de 4 para 10 (quem se cura sobrevive ao
    ritmo de choque e afastamento)."""
    from neural_fights.utils.config import DINAMISMO_ATE_S

    if DINAMISMO_ATE_S is None:
        return True
    try:
        return float(estado.get("t", 0.0)) <= float(DINAMISMO_ATE_S)
    except (AttributeError, TypeError, ValueError):
        return True


def _hp_frac(lutador) -> float:
    try:
        return float(lutador.vida) / max(1e-9, float(lutador.vida_max))
    except (AttributeError, TypeError, ValueError):
        return 1.0


def fase_final(p1, p2) -> bool:
    """O desfecho não se interrompe: com um dos dois abaixo de
    ``DINAMISMO_HP_FIM`` da vida, ou com alguém no plano ACABAR (o "FINISH"
    da tela), nem respiro nem choque nem bate e sai. Medido pelo conferente
    nos vídeos de 21/10: sem isto o fim arrastava 13 s com o perdedor a 3 HP
    e os dois afastados."""
    from neural_fights.utils.config import DINAMISMO_FIM_NO_ACABAR, DINAMISMO_HP_FIM

    for lutador in (p1, p2):
        if DINAMISMO_HP_FIM is not None and _hp_frac(lutador) < DINAMISMO_HP_FIM:
            return True
        if not DINAMISMO_FIM_NO_ACABAR:
            continue
        plano = getattr(getattr(lutador, "brain", None), "__dict__", {}).get("plano")
        if isinstance(plano, Mapping) and plano.get("tipo") == "ACABAR":
            return True
    return False


def soltos(p1, p2) -> bool:
    """Já separados o bastante (borda > ``DINAMISMO_SOLTO_FRACAO_RAIO`` do
    raio desenhado médio): o verbo de saída acaba aqui e a IA volta à dela.
    O respiro separa para não grudar, não para fugir — com o recuo inteiro a
    câmera abria e o lutador encolhia 40% na tela (conferente, 21/10)."""
    from neural_fights.utils.config import DINAMISMO_SOLTO_FRACAO_RAIO

    if DINAMISMO_SOLTO_FRACAO_RAIO is None:
        return False
    limite = DINAMISMO_SOLTO_FRACAO_RAIO * (raio_desenhado(p1) + raio_desenhado(p2)) / 2.0
    return borda(p1, p2) > limite


def parado_sem_golpe(estado) -> bool:
    """O grude de verdade: colado SEM golpe corpo a corpo há
    ``DINAMISMO_SEM_GOLPE_S`` (``None`` = qualquer colado). Medido na base
    (8f51d7bd, 30 lutas): 51% dos golpes saem com os discos colados — o
    colado trocando golpes é luta, não grude."""
    from neural_fights.utils.config import DINAMISMO_SEM_GOLPE_S

    if DINAMISMO_SEM_GOLPE_S is None:
        return True
    try:
        return float(estado.get("t", 0.0)) - float(estado.get("t_golpe", -1e9)) >= DINAMISMO_SEM_GOLPE_S
    except (AttributeError, TypeError, ValueError):
        return True


def acumular(relogio: float, colado: bool, dt: float) -> float:
    """O relógio do colado: sobe com o contato, desce 2x mais rápido solto."""
    from neural_fights.utils.config import DINAMISMO_ESQUECE_FATOR

    if colado:
        return relogio + dt
    return max(0.0, relogio - dt * DINAMISMO_ESQUECE_FATOR)


def direcao_de_saida(lutador, dx: float, dy: float, arena) -> tuple[float, float]:
    """Direção unitária em que o corpo sai, sem entrar na parede.

    ``(dx, dy)`` é para onde ele seria empurrado (para longe do outro). Se
    a parede está a menos de ``DINAMISMO_PAREDE_M`` naquele lado, a
    componente contra ela vira zero e sobra o deslize; sem deslize (canto,
    ou empurrão de frente para a parede), o corpo sai para o centro da arena.
    """
    from neural_fights.utils.config import DINAMISMO_PAREDE_M

    n = math.hypot(dx, dy)
    if n < 1e-9:
        dx, dy, n = 1.0, 0.0, 1.0
    dx, dy = dx / n, dy / n
    if arena is None:
        return dx, dy
    r = _raio(lutador)
    x, y = float(lutador.pos[0]), float(lutador.pos[1])
    folga = DINAMISMO_PAREDE_M + r
    min_x = float(getattr(arena, "min_x", -1e9))
    max_x = float(getattr(arena, "max_x", 1e9))
    min_y = float(getattr(arena, "min_y", -1e9))
    max_y = float(getattr(arena, "max_y", 1e9))
    if (dx < 0.0 and x - min_x < folga) or (dx > 0.0 and max_x - x < folga):
        dx = 0.0
    if (dy < 0.0 and y - min_y < folga) or (dy > 0.0 and max_y - y < folga):
        dy = 0.0
    n = math.hypot(dx, dy)
    if n < 0.35:
        # Encurralado: sai para o centro (o deslize que sobrou é pequeno
        # demais para descolar).
        cx = float(getattr(arena, "centro_x", (min_x + max_x) / 2.0))
        cy = float(getattr(arena, "centro_y", (min_y + max_y) / 2.0))
        dx, dy = cx - x, cy - y
        n = math.hypot(dx, dy)
        if n < 1e-9:
            return 0.0, 0.0
    return dx / n, dy / n


def alcance_da_arma(lutador) -> float:
    """Alcance máximo da arma (m), pelo perfil que a própria IA usa
    (``weapon_analysis.get_weapon_profile``: o Arco 14, o Arremesso 10, a
    espada ~2). Sem arma ou sem perfil: 0 (não conta como longo)."""
    arma = getattr(getattr(lutador, "dados", None), "arma_obj", None)
    if arma is None:
        return 0.0
    try:
        from neural_fights.core.weapon_analysis import get_weapon_profile

        perfil = get_weapon_profile(arma)
        return float(getattr(perfil, "alcance_maximo", 0.0) or 0.0)
    except Exception:
        return 0.0


def papel_de_alcance(lutador, outro) -> str | None:
    """``"curto"``/``"longo"`` quando a diferença de alcance das armas passa
    de ``DINAMISMO_ALCANCE_DIFERENCA_M``; ``None`` no confronto parelho.

    É o que o afastamento não pode ignorar: separar os corpos dá distância
    DE GRAÇA a quem bate de longe. Medido no lote de 600 (21/10): o Mago
    (Arco/Arremesso em 33 das 56 lutas) foi de 27% a 49% de vitórias só com
    o empurrão, sem nenhum verbo da IA."""
    from neural_fights.utils.config import DINAMISMO_ALCANCE_DIFERENCA_M

    if DINAMISMO_ALCANCE_DIFERENCA_M is None:
        return None
    meu = alcance_da_arma(lutador)
    dele = alcance_da_arma(outro)
    if meu - dele >= DINAMISMO_ALCANCE_DIFERENCA_M:
        return "longo"
    if dele - meu >= DINAMISMO_ALCANCE_DIFERENCA_M:
        return "curto"
    return None


# --------------------------------------------------------------- a IA na borda
#
# A CAUSA do grude (21/10/2026, decisão ``builds/dinamismo-caminho`` = "ia"):
# o golpe corpo a corpo acerta pelo raio DESENHADO (``hitbox``: raio_char =
# tamanho/2 × range_mult, contra o disco desenhado do alvo), mas a IA mede o
# alcance pelo raio da FÍSICA (tamanho/4 × range_mult). Uma espada acerta com
# os centros a 2,7 m e a IA só armava o golpe abaixo de ~1,6 m e queria ficar
# a 0,7 m: com os discos desenhados se cobrindo. Com a chave, a IA mede como o
# golpe mede e fica na faixa em que os discos quase se tocam.

TIPOS_DE_PERTO = ("Reta", "Dupla", "Transformável", "Mágica", "Orbital")


def _tipo(lutador) -> str:
    return str(getattr(getattr(getattr(lutador, "dados", None), "arma_obj", None), "tipo", "") or "")


def _corrente_antiga(lutador) -> bool:
    return "Corrente" in _tipo(lutador) and not getattr(lutador, "corrente_v2", False)


def de_perto(lutador) -> bool:
    """Arma que acerta pela hitbox: as lâminas, a área, o orbital e a
    corrente antiga (a V2 tem o anel da bola, ``core/corrente.alcances``)."""
    tipo = _tipo(lutador)
    return any(t in tipo for t in TIPOS_DE_PERTO) or _corrente_antiga(lutador)


def alcance_do_golpe(lutador, alvo) -> float | None:
    """Distância entre CENTROS (m) até onde o golpe de perto acerta: a mesma
    conta do ``hitbox.is_in_hitbox`` (raio desenhado × range_mult + o raio
    desenhado do alvo). ``None`` para arma que não é de perto."""
    if not de_perto(lutador):
        return None
    tipo = lutador.dados.arma_obj.tipo
    try:
        from neural_fights.core.hitbox import HITBOX_PROFILES

        perfil = next((v for k, v in HITBOX_PROFILES.items() if k in tipo), HITBOX_PROFILES["Reta"])
        mult = float(perfil.get("range_mult", 2.0))
    except Exception:
        mult = 2.0
    if _corrente_antiga(lutador):
        # hitbox._colisao_arco: o anel vai até alcance + 1,5 raio do alvo
        return raio_desenhado(lutador) * mult + 1.5 * raio_desenhado(alvo)
    return raio_desenhado(lutador) * mult + raio_desenhado(alvo)


def faixa_da_borda(lutador, alvo) -> tuple[float, float, float] | None:
    """``(minimo, ideal, alcance)`` em distância entre centros para quem
    luta de perto: abaixo de ``minimo`` (borda < ``DINAMISMO_FAIXA_MIN_M``) a
    IA sai de dentro do outro; ``ideal`` = borda ``DINAMISMO_FAIXA_BORDA_M``,
    nunca além de ``DINAMISMO_FAIXA_FRACAO`` do que o golpe alcança."""
    from neural_fights.utils.config import (
        DINAMISMO_FAIXA_BORDA_M,
        DINAMISMO_FAIXA_FRACAO,
        DINAMISMO_FAIXA_MIN_M,
    )

    alcance = alcance_do_golpe(lutador, alvo)
    if alcance is None:
        return None
    from neural_fights.utils.config import DINAMISMO_FAIXA_BORDA_CORRENTE_M

    contato = raio_desenhado(lutador) + raio_desenhado(alvo)
    borda_max = max(0.0, alcance - contato)
    borda = DINAMISMO_FAIXA_BORDA_CORRENTE_M if _corrente_antiga(lutador) else DINAMISMO_FAIXA_BORDA_M
    ideal = contato + min(borda, borda_max * DINAMISMO_FAIXA_FRACAO)
    minimo = min(ideal, contato + DINAMISMO_FAIXA_MIN_M)
    return minimo, ideal, alcance


def preparar_ia(lutador, alvo) -> None:
    """Liga a IA na borda (chamado pelo Simulador com as duas chaves).

    Grava ``dinamismo_faixa`` = (minimo, ideal, alcance) e o ``alcance_ideal``
    de quem luta de perto; quem atira (Arco, Arremesso) e a corrente seguem
    como estão."""
    faixa = faixa_da_borda(lutador, alvo)
    if faixa is None:
        return
    lutador.dinamismo_faixa = faixa
    lutador.alcance_ideal = faixa[1]


def faixa_de(lutador):
    """A faixa da borda deste lutador, ou ``None`` (chave desligada / não é de perto)."""
    return getattr(lutador, "__dict__", {}).get("dinamismo_faixa")


def pode_ser_empurrado(lutador) -> bool:
    """Quem tem a velocidade zerada pelo próprio estado não sai do lugar."""
    if getattr(lutador, "morto", False):
        return False
    if float(lutador.__dict__.get("agarrao_timer", 0.0) or 0.0) > 0.0:
        return False
    if getattr(lutador, "dormindo", False):
        return False
    imobiliza = getattr(lutador, "canalizacao_imobiliza", None)
    if callable(imobiliza):
        try:
            if imobiliza():
                return False
        except Exception:
            return False
    try:
        if float(getattr(lutador, "slow_fator", 1.0)) <= 0.0:
            return False
    except (TypeError, ValueError):
        pass
    return True


def impulsos(p1, p2, arena) -> tuple[tuple[float, float], tuple[float, float]]:
    """Velocidade (m/s) somada a cada corpo no afastamento.

    Cada um recebe ``DINAMISMO_EMPURRAO`` para longe do outro, na direção
    de saída dele; quem não pode se mexer cede a parte dele ao outro.
    """
    from neural_fights.utils.config import DINAMISMO_ASSIM_EMPURRAO, DINAMISMO_EMPURRAO

    ex = p2.pos[0] - p1.pos[0]
    ey = p2.pos[1] - p1.pos[1]
    if math.hypot(ex, ey) < 1e-9:
        ex, ey = 1.0, 0.0
    d1 = direcao_de_saida(p1, -ex, -ey, arena)
    d2 = direcao_de_saida(p2, ex, ey, arena)
    m1 = pode_ser_empurrado(p1)
    m2 = pode_ser_empurrado(p2)
    # alcances desiguais: só descola, sem abrir a distância de quem bate de longe
    base = DINAMISMO_EMPURRAO * (
        DINAMISMO_ASSIM_EMPURRAO if papel_de_alcance(p1, p2) else 1.0)
    f1 = base * (1.0 if m1 else 0.0) * (1.0 if m2 else 2.0)
    f2 = base * (1.0 if m2 else 0.0) * (1.0 if m1 else 2.0)
    return (d1[0] * f1, d1[1] * f1), (d2[0] * f2, d2[1] * f2)


def impulso_do_choque(atacante, defensor, kb_x: float, kb_y: float, arena):
    """O golpe corpo a corpo que acerta com os discos colados é um CHOQUE:
    o defensor sai com pelo menos ``DINAMISMO_CHOQUE_KB_MIN`` (m/s) para
    longe do atacante, na direção de saída dele (sem entrar na parede), e o
    atacante recua ``DINAMISMO_CHOQUE_RECUO``. Devolve o que SOMAR à
    velocidade de cada um: ``((dvx_def, dvy_def), (dvx_atk, dvy_atk))``.

    O dano e o empurrão do golpe não mudam; só sobe o que falta para os
    discos descolarem (o golpe de hoje empurra 8-25 m/s, mas na direção
    da arma, e o atacante segue andando para dentro). Sem empurrão nenhum
    (super armor, enlace da corrente leve) não há choque: o motor já decidiu
    que aquele corpo não sai do lugar.
    """
    from neural_fights.utils.config import (
        DINAMISMO_ASSIM_CHOQUE,
        DINAMISMO_CHOQUE_KB_MIN,
        DINAMISMO_CHOQUE_RECUO,
    )

    nada = ((0.0, 0.0), (0.0, 0.0))
    if math.hypot(kb_x, kb_y) < 1e-9 or not colados(atacante, defensor):
        return nada
    # o curto que acerta o longo colado não o arremessa para a distância dele
    fator = DINAMISMO_ASSIM_CHOQUE if papel_de_alcance(atacante, defensor) == "curto" else 1.0
    ex = defensor.pos[0] - atacante.pos[0]
    ey = defensor.pos[1] - atacante.pos[1]
    if math.hypot(ex, ey) < 1e-9:
        ex, ey = kb_x, kb_y
    dx, dy = direcao_de_saida(defensor, ex, ey, arena)
    componente = kb_x * dx + kb_y * dy
    falta = max(0.0, DINAMISMO_CHOQUE_KB_MIN * fator - componente)
    defesa = (dx * falta, dy * falta) if pode_ser_empurrado(defensor) else (0.0, 0.0)
    ax, ay = direcao_de_saida(atacante, -ex, -ey, arena)
    recuo = DINAMISMO_CHOQUE_RECUO * fator if pode_ser_empurrado(atacante) else 0.0
    return defesa, (ax * recuo, ay * recuo)


def verbo_de_saida(lutador, outro=None) -> str | None:
    """O que a IA faz durante o respiro, sem sorteio: o ágil (mobilidade
    alta) circula (de lado e abrindo distância abaixo de 2,5 m), o resto
    recua — os dois verbos que o motor já anda (``Lutador.executar_movimento``).
    FLANQUEAR não serve: anda a 50° PARA o outro e cola de novo.

    Com alcances desiguais (``papel_de_alcance``) o verbo é o de
    ``DINAMISMO_ASSIM_VERBO_CURTO``/``_LONGO``: ``"padrao"`` (o de cima),
    ``"nenhum"`` (``None``: a IA segue a dela) ou um verbo do motor (o curto
    volta para a faixa dele)."""
    if outro is not None:
        from neural_fights.utils import config as _cfg

        papel = papel_de_alcance(lutador, outro)
        if papel is not None:
            escolha = (_cfg.DINAMISMO_ASSIM_VERBO_CURTO if papel == "curto"
                       else _cfg.DINAMISMO_ASSIM_VERBO_LONGO)
            if escolha == "nenhum":
                return None
            if escolha != "padrao":
                return escolha
    brain = getattr(lutador, "brain", None)
    perfil = getattr(brain, "perfil", None) if brain is not None else None
    try:
        mob = float((perfil or {}).get("mobilidade", 0.0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        mob = 0.0
    return "CIRCULAR" if mob >= 0.5 else "RECUAR"


__all__ = [
    "CHAVE",
    "acumular",
    "alcance_da_arma",
    "alcance_do_golpe",
    "de_perto",
    "faixa_da_borda",
    "faixa_de",
    "preparar_ia",
    "borda",
    "chave_ligada",
    "colados",
    "direcao_de_saida",
    "fase_final",
    "soltos",
    "impulso_do_choque",
    "impulsos",
    "papel_de_alcance",
    "parado_sem_golpe",
    "pode_ser_empurrado",
    "raio_desenhado",
    "vale_agora",
    "verbo_de_saida",
]
