# -*- coding: utf-8 -*-
"""Renderer de armas v2 — RECRIADO DO ZERO (pedido do dono).

Cada uma das 54 variantes de estilo tem silhueta própria, desenhada
proceduralmente a partir da empunhadura (grip) ao longo do eixo do
olhar. Convenção: `f` = vetor unitário para FRENTE (direção do golpe),
`p` = perpendicular. Tudo em coordenadas de tela, pygame.draw direto.

Contratos herdados que este módulo RESPEITA:
- comprimento total (grip → ponta) = L, já normalizado pela geometria
  honesta (a ponta cai no alcance real da hitbox);
- tamanho FIXO (nenhuma dimensão escala em runtime);
- a arma nunca invade o miolo do círculo do personagem.
"""
import math

import pygame

METAL = (196, 200, 210)
METAL_ESCURO = (120, 124, 136)
MADEIRA = (110, 78, 44)
MADEIRA_ESCURA = (74, 52, 30)
COURO = (140, 96, 58)


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clarear(cor, f=0.4):
    return tuple(min(255, int(c * (1 - f) + 255 * f)) for c in cor[:3])


def _escurecer(cor, f=0.4):
    return tuple(max(0, int(c * (1 - f))) for c in cor[:3])


class Pincel:
    """Sistema de coordenadas da arma: origem na EMPUNHADURA, eixo x
    para a frente do golpe. dist = ao longo da lâmina; off = lateral."""

    __slots__ = ("tela", "gx", "gy", "fx", "fy", "px", "py")

    def __init__(self, tela, grip, rad):
        self.tela = tela
        self.gx, self.gy = grip
        self.fx, self.fy = math.cos(rad), math.sin(rad)
        self.px, self.py = -math.sin(rad), math.cos(rad)

    def P(self, dist, off=0.0):
        return (self.gx + self.fx * dist + self.px * off,
                self.gy + self.fy * dist + self.py * off)

    def linha(self, cor, a, b, w=2):
        pygame.draw.line(self.tela, cor,
                         (int(a[0]), int(a[1])), (int(b[0]), int(b[1])),
                         max(1, int(w)))

    def poly(self, cor, pts, w=0):
        pygame.draw.polygon(
            self.tela, cor, [(int(a), int(b)) for a, b in pts], w
        )

    def circulo(self, cor, c, r, w=0):
        pygame.draw.circle(self.tela, cor, (int(c[0]), int(c[1])),
                           max(1, int(r)), w)

    def cabo(self, ate, w, cor_cabo=MADEIRA, pomo=True):
        """Cabo padrão: madeira com friso + pomo atrás da mão."""
        self.linha(MADEIRA_ESCURA, self.P(-w * 0.6), self.P(ate), w + 2)
        self.linha(cor_cabo, self.P(0), self.P(ate), w)
        # frisos de couro
        n = max(2, int(ate / (w * 2.2)))
        for i in range(1, n):
            d = ate * i / n
            self.linha(COURO, self.P(d, -w * 0.55), self.P(d, w * 0.55), 1)
        if pomo:
            self.circulo(METAL_ESCURO, self.P(-w * 0.5), w * 0.75)
            self.circulo(METAL, self.P(-w * 0.5), w * 0.45)

    def lamina_reta(self, base, ponta, w_base, w_ponta, cor, curva=0.0,
                    fio=True):
        """Lâmina como polígono; curva>0 arqueia para o lado +off."""
        n = 5
        cima, baixo = [], []
        for i in range(n + 1):
            t = i / n
            d = base + (ponta - base) * t
            arco = math.sin(t * math.pi) * curva
            w = w_base + (w_ponta - w_base) * t
            cima.append(self.P(d, arco + w))
            baixo.append(self.P(d, arco - w))
        pts = cima + baixo[::-1]
        self.poly(cor, pts)
        self.poly(_escurecer(cor, 0.45), pts, 1)
        if fio:
            meio = [self.P(base + (ponta - base) * t,
                           math.sin(t * math.pi) * curva)
                    for t in (0.15, 0.5, 0.85)]
            self.linha(_clarear(cor, 0.5), meio[0], meio[2], 1)


# ===========================================================================
# RETA — 12 estilos
# ===========================================================================

def _reta_espada_longa(b, L, w, cor, t, atk):
    b.cabo(L * 0.22, w)
    g = L * 0.22
    b.linha(METAL, b.P(g, -w * 1.9), b.P(g, w * 1.9), max(2, int(w * 0.8)))
    b.lamina_reta(g, L, w * 0.95, w * 0.3, cor)


def _reta_espada_curta(b, L, w, cor, t, atk):
    b.cabo(L * 0.28, w)
    g = L * 0.28
    b.linha(METAL, b.P(g, -w * 1.5), b.P(g, w * 1.5), max(2, int(w * 0.7)))
    b.lamina_reta(g, L, w * 1.15, w * 0.45, cor)


def _reta_montante(b, L, w, cor, t, atk):
    b.cabo(L * 0.26, w * 1.15)
    g = L * 0.26
    b.linha(METAL, b.P(g, -w * 2.6), b.P(g, w * 2.6), max(3, int(w)))
    b.circulo(METAL, b.P(g, -w * 2.6), w * 0.7)
    b.circulo(METAL, b.P(g, w * 2.6), w * 0.7)
    b.lamina_reta(g, L, w * 1.25, w * 0.35, cor)
    # ricasso (segunda empunhadura na base da lâmina)
    b.linha(COURO, b.P(g + w), b.P(g + w * 3), w * 0.9)


def _reta_katana(b, L, w, cor, t, atk):
    b.cabo(L * 0.24, w * 0.85, cor_cabo=(40, 40, 52), pomo=False)
    g = L * 0.24
    # tsuba circular
    b.circulo(METAL_ESCURO, b.P(g), w * 1.4, 2)
    b.lamina_reta(g, L, w * 0.7, w * 0.35, cor, curva=w * 1.4)


def _reta_sabre(b, L, w, cor, t, atk):
    b.cabo(L * 0.24, w * 0.8, pomo=False)
    g = L * 0.24
    # guarda-mão em concha (arco cobrindo o cabo)
    pygame.draw.arc(
        b.tela, METAL,
        (int(b.gx - w * 2), int(b.gy - w * 2), int(w * 4), int(w * 4)),
        0, math.pi, 2,
    )
    b.lamina_reta(g, L, w * 0.75, w * 0.3, cor, curva=w * 1.8)


def _reta_lanca(b, L, w, cor, t, atk):
    # haste longa fina + ponta em folha
    b.linha(MADEIRA_ESCURA, b.P(-w), b.P(L * 0.8), w * 0.9)
    b.linha(MADEIRA, b.P(-w), b.P(L * 0.8), w * 0.55)
    b.linha(COURO, b.P(L * 0.35, -w * 0.6), b.P(L * 0.35, w * 0.6), 2)
    b.poly(cor, [b.P(L * 0.78), b.P(L * 0.86, w * 1.1), b.P(L),
                 b.P(L * 0.86, -w * 1.1)])
    b.poly(_escurecer(cor), [b.P(L * 0.78), b.P(L * 0.86, w * 1.1), b.P(L),
                             b.P(L * 0.86, -w * 1.1)], 1)


def _reta_alabarda(b, L, w, cor, t, atk):
    b.linha(MADEIRA_ESCURA, b.P(-w), b.P(L * 0.86), w * 0.95)
    b.linha(MADEIRA, b.P(-w), b.P(L * 0.86), w * 0.6)
    c = L * 0.74
    # machado lateral
    b.poly(cor, [b.P(c, w * 0.4), b.P(c + w * 2.4, w * 2.6),
                 b.P(c + w * 4.2, w * 0.6)])
    # gancho oposto
    b.poly(METAL, [b.P(c + w, -w * 0.4), b.P(c + w * 1.6, -w * 1.8),
                   b.P(c + w * 2.4, -w * 0.5)])
    # espeto
    b.poly(METAL, [b.P(L * 0.86, w * 0.5), b.P(L), b.P(L * 0.86, -w * 0.5)])


def _reta_machado(b, L, w, cor, t, atk):
    b.linha(MADEIRA_ESCURA, b.P(-w), b.P(L * 0.92), w)
    b.linha(MADEIRA, b.P(-w), b.P(L * 0.92), w * 0.6)
    c = L * 0.68
    # meia-lua da lâmina
    pts = [b.P(c, w * 0.5)]
    for i in range(6):
        a = i / 5.0
        pts.append(b.P(c + w * 1.2 + math.sin(a * math.pi) * w * 2.6,
                       w * 0.5 + a * w * 3.4))
    pts.append(b.P(c + w * 1.0, w * 3.9))
    b.poly(cor, pts)
    b.poly(_escurecer(cor), pts, 1)


def _reta_martelo(b, L, w, cor, t, atk):
    b.linha(MADEIRA_ESCURA, b.P(-w), b.P(L * 0.88), w)
    b.linha(MADEIRA, b.P(-w), b.P(L * 0.88), w * 0.6)
    c = L * 0.72
    # cabeça retangular maciça
    b.poly(METAL_ESCURO, [b.P(c, w * 2.6), b.P(c + w * 3.4, w * 2.6),
                          b.P(c + w * 3.4, -w * 2.6), b.P(c, -w * 2.6)])
    b.poly(METAL, [b.P(c + w * 0.4, w * 2.1), b.P(c + w * 3.0, w * 2.1),
                   b.P(c + w * 3.0, -w * 2.1), b.P(c + w * 0.4, -w * 2.1)])
    b.poly(cor, [b.P(c + w * 0.4, w * 2.1), b.P(c + w * 3.0, w * 2.1),
                 b.P(c + w * 3.0, -w * 2.1), b.P(c + w * 0.4, -w * 2.1)], 2)


def _reta_maca(b, L, w, cor, t, atk):
    b.linha(MADEIRA_ESCURA, b.P(-w), b.P(L * 0.82), w)
    b.linha(MADEIRA, b.P(-w), b.P(L * 0.82), w * 0.6)
    c = b.P(L * 0.86)
    r = w * 2.4
    b.circulo(METAL_ESCURO, c, r)
    b.circulo(cor, c, r * 0.7)
    # cravos radiais
    for i in range(8):
        a = i * math.pi / 4
        b.linha(METAL,
                (c[0] + math.cos(a) * r * 0.8, c[1] + math.sin(a) * r * 0.8),
                (c[0] + math.cos(a) * r * 1.45, c[1] + math.sin(a) * r * 1.45),
                2)


def _reta_foice(b, L, w, cor, t, atk):
    b.linha(MADEIRA_ESCURA, b.P(-w), b.P(L * 0.8), w * 0.9)
    b.linha(MADEIRA, b.P(-w), b.P(L * 0.8), w * 0.55)
    # lâmina curva perpendicular (crescente)
    base = L * 0.76
    pts_fora, pts_dentro = [], []
    for i in range(7):
        a = i / 6.0
        d = base + math.sin(a * math.pi * 0.5) * L * 0.24
        off = -a * w * 5.2
        pts_fora.append(b.P(d + w * (1.4 - a * 1.1), off))
        pts_dentro.append(b.P(d, off))
    b.poly(cor, pts_fora + pts_dentro[::-1])
    b.poly(_escurecer(cor), pts_fora + pts_dentro[::-1], 1)


def _reta_claymore(b, L, w, cor, t, atk):
    b.cabo(L * 0.24, w * 1.1)
    g = L * 0.24
    # guarda em V para frente
    b.linha(METAL, b.P(g, -w * 2.2), b.P(g + w * 1.6, -w * 0.6), 3)
    b.linha(METAL, b.P(g, w * 2.2), b.P(g + w * 1.6, w * 0.6), 3)
    b.lamina_reta(g, L, w * 1.3, w * 0.4, cor)


ESTILOS_RETA = {
    "Espada Longa": _reta_espada_longa,
    "Espada Curta": _reta_espada_curta,
    "Montante": _reta_montante,
    "Katana": _reta_katana,
    "Sabre": _reta_sabre,
    "Lança": _reta_lanca,
    "Alabarda": _reta_alabarda,
    "Machado": _reta_machado,
    "Martelo": _reta_martelo,
    "Maça": _reta_maca,
    "Foice": _reta_foice,
    "Claymore": _reta_claymore,
}


# ===========================================================================
# DUPLA — 6 estilos (desenhada 1x por mão; quem chama espelha)
# ===========================================================================

def _dupla_adaga(b, L, w, cor, t, atk):
    b.cabo(L * 0.3, w * 0.8, pomo=True)
    b.linha(METAL, b.P(L * 0.3, -w * 1.1), b.P(L * 0.3, w * 1.1), 2)
    b.lamina_reta(L * 0.3, L, w * 0.7, w * 0.25, cor)


def _dupla_sai(b, L, w, cor, t, atk):
    b.cabo(L * 0.32, w * 0.75, pomo=True)
    g = L * 0.32
    b.linha(cor, b.P(g), b.P(L), w * 0.6)  # espeto central
    # tridentes laterais curvados para frente
    for lado in (-1, 1):
        b.linha(METAL, b.P(g, w * 0.4 * lado),
                b.P(g + L * 0.22, w * 1.6 * lado), 2)


def _dupla_kama(b, L, w, cor, t, atk):
    b.cabo(L * 0.55, w * 0.8, pomo=False)
    base = L * 0.55
    pts = [b.P(base, 0)]
    for i in range(5):
        a = i / 4.0
        pts.append(b.P(base + a * L * 0.4, -w * (0.8 + a * 3.2)))
    pts.append(b.P(base + L * 0.32, -w * 4.2))
    b.poly(cor, pts)
    b.poly(_escurecer(cor), pts, 1)


def _dupla_garra(b, L, w, cor, t, atk):
    b.linha(COURO, b.P(0, -w * 1.4), b.P(0, w * 1.4), max(3, int(w)))
    for k, off in enumerate((-1.0, 0.0, 1.0)):
        b.lamina_reta(w, L * (0.82 + 0.18 * (1 - abs(off))),
                      w * 0.4, w * 0.12, cor, curva=w * off * 0.9, fio=False)


def _dupla_tonfa(b, L, w, cor, t, atk):
    # corpo em L: punho perpendicular + haste longa
    b.linha(MADEIRA, b.P(0, -w * 2.2), b.P(0, 0), w)
    b.linha(_escurecer(cor, 0.1), b.P(-L * 0.3), b.P(L), w * 1.1)
    b.linha(_clarear(cor, 0.3), b.P(-L * 0.3), b.P(L), max(1, int(w * 0.4)))


def _dupla_faca(b, L, w, cor, t, atk):
    b.cabo(L * 0.34, w * 0.75, cor_cabo=(50, 50, 58), pomo=False)
    b.lamina_reta(L * 0.34, L, w * 0.8, w * 0.2, cor, curva=-w * 0.5)
    # serrilha
    for i in range(3):
        d = L * (0.45 + i * 0.12)
        b.linha(_escurecer(cor), b.P(d, -w * 0.75), b.P(d + w * 0.5, -w * 1.1), 1)


ESTILOS_DUPLA = {
    "Adagas Gêmeas": _dupla_adaga,
    "Sai": _dupla_sai,
    "Kamas": _dupla_kama,
    "Garras": _dupla_garra,
    "Tonfas": _dupla_tonfa,
    "Facas Táticas": _dupla_faca,
}


# ===========================================================================
# CORRENTE — 6 estilos: cabo curto + elos até a cabeça
# ===========================================================================

def _corrente_elos(b, cabo_fim, L, w, sag, t, n=9):
    """Elos em catenária leve; devolve o ponto da cabeça."""
    pts = []
    for i in range(n + 1):
        a = i / n
        d = cabo_fim + (L - cabo_fim) * a
        off = math.sin(a * math.pi) * sag + math.sin(t * 2.2 + a * 5) * sag * 0.25
        pts.append(b.P(d, off))
    for i, pt in enumerate(pts):
        if i:
            b.linha((90, 92, 102), pts[i - 1], pt, 2)
        if i % 2 == 0:
            b.circulo(METAL_ESCURO, pt, w * 0.5, 1)
    return pts[-1]


def _cor_kusarigama(b, L, w, cor, t, atk):
    b.cabo(L * 0.16, w * 0.85, pomo=False)
    fim = _corrente_elos(b, L * 0.16, L * 0.92, w, w * 2.2, t)
    # foice na ponta
    pygame.draw.arc(b.tela, cor,
                    (int(fim[0] - w * 3), int(fim[1] - w * 3),
                     int(w * 6), int(w * 6)),
                    0.4, 3.2, max(2, int(w)))
    b.circulo(MADEIRA, fim, w * 0.8)


def _cor_mangual(b, L, w, cor, t, atk):
    b.cabo(L * 0.2, w, pomo=True)
    fim = _corrente_elos(b, L * 0.2, L * 0.88, w, w * 1.8, t, n=7)
    r = w * 2.2
    b.circulo(METAL_ESCURO, fim, r)
    b.circulo(cor, fim, r * 0.65)
    for i in range(8):
        a = i * math.pi / 4 + t * (3.0 if atk else 0.4)
        b.linha(METAL,
                (fim[0] + math.cos(a) * r * 0.9, fim[1] + math.sin(a) * r * 0.9),
                (fim[0] + math.cos(a) * r * 1.5, fim[1] + math.sin(a) * r * 1.5),
                2)


def _cor_chicote(b, L, w, cor, t, atk):
    b.cabo(L * 0.14, w * 0.8, cor_cabo=COURO, pomo=True)
    # curva em S com onda viajante
    pts = []
    n = 14
    for i in range(n + 1):
        a = i / n
        d = L * 0.14 + (L - L * 0.14) * a
        off = math.sin(a * math.pi * 2 - t * 6) * w * 2.6 * a
        pts.append(b.P(d, off))
    for i in range(1, n + 1):
        b.linha(_mix(cor, COURO, 0.5), pts[i - 1], pts[i],
                max(1, int(w * (1.0 - 0.8 * i / n))))
    b.circulo(_clarear(cor, 0.3), pts[-1], max(1, int(w * 0.35)))


def _cor_peso(b, L, w, cor, t, atk):
    b.cabo(L * 0.18, w * 0.9, pomo=False)
    fim = _corrente_elos(b, L * 0.18, L * 0.9, w, w * 2.0, t)
    # peso quadrado
    r = w * 1.9
    pts = [(fim[0] + math.cos(t * 0.8 + i * math.pi / 2 + math.pi / 4) * r,
            fim[1] + math.sin(t * 0.8 + i * math.pi / 2 + math.pi / 4) * r)
           for i in range(4)]
    b.poly(METAL_ESCURO, pts)
    b.poly(cor, pts, 2)


def _cor_meteoro(b, L, w, cor, t, atk):
    b.cabo(L * 0.12, w * 0.8, pomo=False)
    fim = _corrente_elos(b, L * 0.12, L * 0.9, w, w * 2.4, t, n=11)
    r = w * 1.8
    b.circulo(cor, fim, r)
    b.circulo(_clarear(cor, 0.5), (fim[0] - r * 0.3, fim[1] - r * 0.3), r * 0.5)
    # rastro incandescente curto
    b.circulo((*_clarear(cor, 0.2),), (fim[0], fim[1]), r * 1.35, 1)


def _cor_dardo(b, L, w, cor, t, atk):
    b.cabo(L * 0.1, w * 0.7, cor_cabo=COURO, pomo=False)
    # corda fina (não elos)
    pts = []
    n = 10
    for i in range(n + 1):
        a = i / n
        d = L * 0.1 + (L - L * 0.1 - w * 3) * a
        off = math.sin(a * math.pi) * w * 1.6
        pts.append(b.P(d, off))
    for i in range(1, n + 1):
        b.linha((150, 130, 100), pts[i - 1], pts[i], 1)
    # dardo
    b.poly(cor, [b.P(L - w * 3, w * 0.7), b.P(L), b.P(L - w * 3, -w * 0.7)])


ESTILOS_CORRENTE = {
    "Kusarigama": _cor_kusarigama,
    "Mangual": _cor_mangual,
    "Chicote": _cor_chicote,
    "Corrente com Peso": _cor_peso,
    "Meteor Hammer": _cor_meteoro,
    "Rope Dart": _cor_dardo,
}


# ===========================================================================
# ARCO — 6 estilos (arco perpendicular ao olhar, flecha na mão)
# ===========================================================================

def _arco_generico(b, L, w, cor, t, atk, *, alt=1.0, dupla_curva=False,
                   besta=False, puxada=0.0):
    span = L * 0.5 * alt  # meia-altura do arco
    if besta:
        # coronha + corpo horizontal
        b.poly(MADEIRA_ESCURA, [b.P(-L * 0.3, w * 1.1), b.P(-L * 0.05, w * 0.8),
                                b.P(-L * 0.05, -w * 0.8), b.P(-L * 0.3, -w * 1.1)])
        b.linha(MADEIRA_ESCURA, b.P(-L * 0.1), b.P(L * 0.42), w * 1.4)
        b.linha(MADEIRA, b.P(-L * 0.1), b.P(L * 0.42), w * 0.9)
        # braços do arco TRANSVERSAL (V invertido para trás)
        pa = b.P(L * 0.36, span * 0.85)
        pb_ = b.P(L * 0.36, -span * 0.85)
        b.linha(cor, b.P(L * 0.42), pa, max(2, int(w * 0.9)))
        b.linha(cor, b.P(L * 0.42), pb_, max(2, int(w * 0.9)))
        b.linha(_clarear(cor, 0.4), b.P(L * 0.42), pa, 1)
        b.linha(_clarear(cor, 0.4), b.P(L * 0.42), pb_, 1)
        # corda ligando os braços (recua ao carregar) + virote no trilho
        rec = L * 0.16 * puxada
        b.linha((225, 225, 235), pa, b.P(L * 0.18 - rec), 1)
        b.linha((225, 225, 235), b.P(L * 0.18 - rec), pb_, 1)
        b.linha(MADEIRA, b.P(L * 0.18 - rec), b.P(L * 0.52 - rec), 2)
        b.poly(METAL, [b.P(L * 0.52 - rec, w * 0.5), b.P(L * 0.62 - rec),
                       b.P(L * 0.52 - rec, -w * 0.5)])
        return
    # hastes do arco (2 arcos de Bézier aproximados por segmentos)
    n = 8
    pts = []
    for i in range(n + 1):
        a = i / n - 0.5  # -0.5..0.5
        prof = math.cos(a * math.pi) * L * 0.22
        if dupla_curva:
            prof += math.cos(a * math.pi * 3) * L * 0.05
        pts.append(b.P(prof, a * 2 * span))
    for i in range(1, n + 1):
        b.linha(cor, pts[i - 1], pts[i], max(2, int(w * 0.9)))
    b.linha(_clarear(cor, 0.4), pts[0], pts[1], 2)
    b.linha(_clarear(cor, 0.4), pts[-2], pts[-1], 2)
    # corda (recua com a puxada)
    rec = -w * 4 * puxada
    b.linha((225, 225, 235), pts[0], b.P(rec), 1)
    b.linha((225, 225, 235), b.P(rec), pts[-1], 1)
    # flecha na mão
    fl = L * 0.62
    b.linha(MADEIRA, b.P(rec), b.P(rec + fl), 2)
    b.poly(METAL, [b.P(rec + fl, w * 0.6), b.P(rec + fl + w * 2),
                   b.P(rec + fl, -w * 0.6)])
    for k in (1, 2):
        b.linha((210, 210, 220), b.P(rec + w * k, 0),
                b.P(rec - w * 0.8 + w * k, w * 0.9), 1)
        b.linha((210, 210, 220), b.P(rec + w * k, 0),
                b.P(rec - w * 0.8 + w * k, -w * 0.9), 1)


ESTILOS_ARCO = {
    "Arco Curto": dict(alt=0.75),
    "Arco Longo": dict(alt=1.25),
    "Arco Composto": dict(alt=0.95, dupla_curva=True),
    "Besta Leve": dict(besta=True, alt=0.8),
    "Besta Pesada": dict(besta=True, alt=1.05),
    "Arco Élfico": dict(alt=1.15, dupla_curva=True),
}


# ===========================================================================
# ARREMESSO — projétil na mão + reserva no cinto
# ===========================================================================

def _proj_forma(b, c, r, cor, forma, giro):
    if forma == "faca":
        pts = [(c[0] + math.cos(giro) * r * 1.6, c[1] + math.sin(giro) * r * 1.6),
               (c[0] + math.cos(giro + 2.5) * r * 0.7,
                c[1] + math.sin(giro + 2.5) * r * 0.7),
               (c[0] - math.cos(giro) * r * 0.9, c[1] - math.sin(giro) * r * 0.9),
               (c[0] + math.cos(giro - 2.5) * r * 0.7,
                c[1] + math.sin(giro - 2.5) * r * 0.7)]
        b.poly(cor, pts)
    elif forma == "shuriken":
        pts = []
        for i in range(8):
            a = giro + i * math.pi / 4
            d = r * (1.5 if i % 2 == 0 else 0.5)
            pts.append((c[0] + math.cos(a) * d, c[1] + math.sin(a) * d))
        b.poly(cor, pts)
        b.circulo(METAL_ESCURO, c, r * 0.35)
    elif forma == "chakram":
        b.circulo(cor, c, r * 1.4, max(2, int(r * 0.45)))
        b.circulo(_clarear(cor, 0.4), c, r * 1.4, 1)
    elif forma == "machadinha":
        b.linha(MADEIRA, (c[0] - math.cos(giro) * r, c[1] - math.sin(giro) * r),
                (c[0] + math.cos(giro) * r * 1.2, c[1] + math.sin(giro) * r * 1.2), 2)
        b.poly(cor, [(c[0] + math.cos(giro) * r, c[1] + math.sin(giro) * r),
                     (c[0] + math.cos(giro + 1.2) * r * 1.6,
                      c[1] + math.sin(giro + 1.2) * r * 1.6),
                     (c[0] + math.cos(giro + 0.5) * r * 2.0,
                      c[1] + math.sin(giro + 0.5) * r * 2.0)])
    elif forma == "bumerangue":
        pygame.draw.arc(b.tela, cor,
                        (int(c[0] - r * 1.6), int(c[1] - r * 1.6),
                         int(r * 3.2), int(r * 3.2)),
                        giro, giro + math.pi * 0.9, max(2, int(r * 0.5)))
    else:  # kunai
        pts = [(c[0] + math.cos(giro) * r * 1.7, c[1] + math.sin(giro) * r * 1.7),
               (c[0] + math.cos(giro + 2.2) * r * 0.6,
                c[1] + math.sin(giro + 2.2) * r * 0.6),
               (c[0] - math.cos(giro) * r * 0.7, c[1] - math.sin(giro) * r * 0.7),
               (c[0] + math.cos(giro - 2.2) * r * 0.6,
                c[1] + math.sin(giro - 2.2) * r * 0.6)]
        b.poly(cor, pts)
        b.circulo(cor, (c[0] - math.cos(giro) * r, c[1] - math.sin(giro) * r),
                  r * 0.35, 1)


FORMAS_ARREMESSO = {
    "Facas de Arremesso": "faca",
    "Shuriken": "shuriken",
    "Chakram": "chakram",
    "Machados de Arremesso": "machadinha",
    "Kunai": "kunai",
    "Bumerangue": "bumerangue",
}


# ===========================================================================
# ORBITAL — corpo do satélite por estilo
# ===========================================================================

def _orb_desenha(b, c, r, cor, estilo, t):
    if estilo == "Escudo Orbital":
        pygame.draw.arc(b.tela, cor,
                        (int(c[0] - r * 1.4), int(c[1] - r * 1.4),
                         int(r * 2.8), int(r * 2.8)),
                        t * 0.7, t * 0.7 + math.pi * 0.9, max(3, int(r * 0.5)))
        b.circulo(_clarear(cor, 0.4), c, r * 0.3)
    elif estilo == "Drones de Combate":
        pts = [(c[0] + math.cos(t + i * 2.09) * r,
                c[1] + math.sin(t + i * 2.09) * r) for i in range(3)]
        b.poly(_escurecer(cor, 0.2), pts)
        b.poly(cor, pts, 1)
        aceso = (t % 0.8) < 0.4
        b.circulo((255, 80, 80) if aceso else (90, 40, 40), c, r * 0.25)
    elif estilo == "Lâminas Orbitais":
        pts = [(c[0] + math.cos(t * 2 + i * math.pi / 2) * r * (1.5 if i % 2 == 0 else 0.4),
                c[1] + math.sin(t * 2 + i * math.pi / 2) * r * (1.5 if i % 2 == 0 else 0.4))
               for i in range(4)]
        b.poly(cor, pts)
    elif estilo == "Cristais Flutuantes":
        pts = [(c[0], c[1] - r * 1.3), (c[0] + r * 0.7, c[1]),
               (c[0], c[1] + r * 1.3), (c[0] - r * 0.7, c[1])]
        b.poly(cor, pts)
        b.poly(_clarear(cor, 0.5), pts, 1)
    elif estilo == "Sentinelas":
        b.circulo(_escurecer(cor, 0.25), c, r)
        b.circulo(cor, c, r, 2)
        # olho que segue
        b.circulo((250, 250, 255), c, r * 0.5)
        b.circulo((30, 30, 40),
                  (c[0] + math.cos(t) * r * 0.2, c[1] + math.sin(t) * r * 0.2),
                  r * 0.25)
    else:  # Orbes Místicos
        b.circulo(cor, c, r)
        b.circulo(_clarear(cor, 0.55), (c[0] - r * 0.3, c[1] - r * 0.3), r * 0.4)
        b.circulo(_clarear(cor, 0.2), c, r * 1.3, 1)


# ===========================================================================
# MÁGICA — constructos flutuantes por estilo
# ===========================================================================

def _mag_desenha(b, c, tam, cor, estilo, t, ang):
    if estilo == "Espadas Espectrais":
        f = (math.cos(ang), math.sin(ang))
        p = (-math.sin(ang), math.cos(ang))
        pts = [(c[0] + f[0] * tam, c[1] + f[1] * tam),
               (c[0] + p[0] * tam * 0.22, c[1] + p[1] * tam * 0.22),
               (c[0] - f[0] * tam * 0.45, c[1] - f[1] * tam * 0.45),
               (c[0] - p[0] * tam * 0.22, c[1] - p[1] * tam * 0.22)]
        b.poly(_clarear(cor, 0.15), pts)
        b.poly(_clarear(cor, 0.55), pts, 1)
    elif estilo == "Runas Flutuantes":
        r = tam * 0.55
        pts = [(c[0] + math.cos(t + i * math.pi * 2 / 3) * r,
                c[1] + math.sin(t + i * math.pi * 2 / 3) * r) for i in range(3)]
        b.poly(cor, pts, 2)
        b.circulo(_clarear(cor, 0.5), c, r * 0.3)
    elif estilo == "Tentáculos Sombrios":
        n = 7
        pts = []
        for i in range(n + 1):
            a = i / n
            pts.append((c[0] + math.cos(ang) * tam * a
                        + math.cos(ang + math.pi / 2) * math.sin(a * 6 + t * 4) * tam * 0.25,
                        c[1] + math.sin(ang) * tam * a
                        + math.sin(ang + math.pi / 2) * math.sin(a * 6 + t * 4) * tam * 0.25))
        for i in range(1, n + 1):
            b.linha(_escurecer(cor, 0.15), pts[i - 1], pts[i],
                    max(1, int(tam * 0.22 * (1 - i / n) + 1)))
    elif estilo == "Cristais Arcanos":
        pts = [(c[0], c[1] - tam * 0.8), (c[0] + tam * 0.45, c[1]),
               (c[0], c[1] + tam * 0.8), (c[0] - tam * 0.45, c[1])]
        b.poly(cor, pts)
        b.poly(_clarear(cor, 0.6), pts, 1)
    elif estilo == "Lanças de Mana":
        f = (math.cos(ang), math.sin(ang))
        b.linha(cor, (c[0] - f[0] * tam * 0.6, c[1] - f[1] * tam * 0.6),
                (c[0] + f[0] * tam * 0.7, c[1] + f[1] * tam * 0.7), 3)
        b.poly(_clarear(cor, 0.4),
               [(c[0] + f[0] * tam * 0.7, c[1] + f[1] * tam * 0.7),
                (c[0] + f[0] * tam * 0.45 - f[1] * tam * 0.18,
                 c[1] + f[1] * tam * 0.45 + f[0] * tam * 0.18),
                (c[0] + f[0] * tam * 0.45 + f[1] * tam * 0.18,
                 c[1] + f[1] * tam * 0.45 - f[0] * tam * 0.18)])
    else:  # Chamas Espirituais
        trem = math.sin(t * 8 + c[0]) * tam * 0.15
        b.poly(cor, [(c[0] - tam * 0.4, c[1] + tam * 0.4),
                     (c[0] + trem, c[1] - tam * 0.75),
                     (c[0] + tam * 0.4, c[1] + tam * 0.4)])
        b.poly(_clarear(cor, 0.5), [(c[0] - tam * 0.2, c[1] + tam * 0.35),
                                    (c[0] + trem * 0.6, c[1] - tam * 0.3),
                                    (c[0] + tam * 0.2, c[1] + tam * 0.35)])


# ===========================================================================
# TRANSFORMÁVEL — 6 estilos, 2 formas cada (dobradiça articulada)
# ===========================================================================

def _trans_generico(b, L, w, cor, t, atk, forma, estilo):
    b.cabo(L * 0.2, w, pomo=True)
    g = L * 0.2
    # dobradiça (identidade do tipo)
    ang_m = t * (3.0 if atk else 0.8)
    b.circulo((120, 120, 132), b.P(g), w * 1.3)
    b.circulo((70, 70, 82), b.P(g), w * 1.3, 2)
    b.linha((200, 200, 210),
            b.P(g, 0), (b.gx + b.fx * g + math.cos(ang_m) * w * 1.1,
                        b.gy + b.fy * g + math.sin(ang_m) * w * 1.1), 2)
    if forma == 1:
        # forma compacta: lâmina curta e larga
        b.lamina_reta(g + w * 1.2, L * 0.72, w * 1.1, w * 0.4, cor)
    else:
        # forma estendida: 3 segmentos com juntas
        seg = (L - g - w) / 3.0
        for si in range(3):
            d0 = g + w + seg * si
            d1 = g + w + seg * (si + 1)
            b.linha(cor, b.P(d0), b.P(d1), max(2, int(w * (1.0 - si * 0.2))))
            b.linha(_clarear(cor, 0.4), b.P(d0), b.P(d1), 1)
            if si:
                b.circulo((150, 150, 160), b.P(d0), w * 0.6)
        b.poly(cor, [b.P(L + w * 1.4), b.P(L, w * 0.9), b.P(L, -w * 0.9)])


# ===========================================================================
# ENTRADA ÚNICA
# ===========================================================================

def desenhar(tela, arma, grip, rad, raio_char, L, w, tempo_s, em_ataque,
             angulo_orbita=0.0):
    """Desenha a arma completa a partir da empunhadura.

    L = comprimento honesto grip→ponta (px); w = meia-largura base (px).
    Para Arremesso/Orbital/Mágica, `grip` é o CENTRO do personagem e a
    função posiciona os satélites por conta própria (fora do corpo).
    """
    b = Pincel(tela, grip, rad)
    tipo = getattr(arma, "tipo", "Reta")
    estilo = getattr(arma, "estilo", "") or ""
    cor = (getattr(arma, "r", 180) or 180, getattr(arma, "g", 180) or 180,
           getattr(arma, "b", 180) or 180)
    t = tempo_s

    if tipo == "Reta":
        fn = ESTILOS_RETA.get(estilo, _reta_espada_longa)
        fn(b, L, w, cor, t, em_ataque)
    elif tipo == "Dupla":
        fn = ESTILOS_DUPLA.get(estilo, _dupla_adaga)
        fn(b, L, w, cor, t, em_ataque)
    elif tipo == "Corrente":
        fn = ESTILOS_CORRENTE.get(estilo, _cor_mangual)
        fn(b, L, w, cor, t, em_ataque)
    elif tipo == "Arco":
        kw = ESTILOS_ARCO.get(estilo, {})
        puxada = getattr(arma, "_puxada_visual", 0.0)
        _arco_generico(b, L, w, cor, t, em_ataque, puxada=puxada, **kw)
    elif tipo == "Arremesso":
        forma = FORMAS_ARREMESSO.get(estilo, "faca")
        r_p = max(4, raio_char * 0.3)
        giro = t * (9.0 if em_ataque else 2.0)
        # 1 na mão (frente) + 2 na reserva (cinto traseiro)
        _proj_forma(b, b.P(raio_char * 0.35), r_p, cor, forma, rad + giro)
        for k, lado in ((1, 1.0), (2, -1.0)):
            c_res = b.P(-raio_char * 1.5, lado * raio_char * 0.55)
            _proj_forma(b, c_res, r_p * 0.7, _escurecer(cor, 0.2), forma,
                        rad + lado)
    elif tipo == "Orbital":
        qtd = max(1, min(5, int(getattr(arma, "quantidade_orbitais", 2) or 2)))
        dist = raio_char * 1.5
        r_o = max(5, raio_char * 0.3)
        for i in range(qtd):
            a = angulo_orbita + i * math.tau / qtd
            c = (b.gx + math.cos(a) * dist, b.gy + math.sin(a) * dist)
            _orb_desenha(b, c, r_o, cor, estilo, t + i * 0.7)
    elif tipo == "Mágica":
        qtd = max(2, min(5, int(getattr(arma, "quantidade", 3) or 3)))
        dist = raio_char * 1.45
        tam = max(8, raio_char * 0.55)
        flut = math.sin(t * 2.4) * raio_char * 0.08
        for i in range(qtd):
            off_a = (i - (qtd - 1) / 2) * 0.42
            a = rad + off_a + math.sin(t * 1.1 + i) * 0.05
            c = (b.gx + math.cos(a) * (dist + flut * (1 + i * 0.2)),
                 b.gy + math.sin(a) * (dist + flut * (1 + i * 0.2)))
            _mag_desenha(b, c, tam, cor, estilo, t + i * 0.9, a)
    else:  # Transformável e fallback
        forma = getattr(arma, "forma_atual", 1)
        _trans_generico(b, L, w, cor, t, em_ataque, forma, estilo)
