# -*- coding: utf-8 -*-
"""ROSTOS — toda a expressividade do lutador em olhos + boca.

Direção do dono: círculo CHAPADO (sem props, sem luz 3D); a alma
inteira vive nas reações dos olhos e da boca, grandes e impecáveis.

GEOMETRIA (a lição da v1): o rosto vive num QUADRO DE REFERÊNCIA único —
`f` = "queixo" do rosto (direção do olhar), `p` = "direita" do rosto.
Todos os traços são compostos nesse quadro e giram JUNTOS, perfeitos em
qualquer ângulo. (A v1 dava a cada olho um "para cima" radial próprio e
as sobrancelhas abriam em leque conforme o ângulo — o defeito apontado.)

Layout (frações do raio R do corpo):    testa (−f)
    sobrancelhas ~ −0.10R                 ▁▁   ▁▁
    olhos em +0.26R, ±0.40R, raio 0.30R  (o)   (o)
    boca em +0.74R                          ‿
                                          queixo (+f)

Duas camadas de estado:
- REAÇÕES (transitórias): morto, atordoado, dor, golpe, bloqueio,
  canalização, tells de instinto/hesitação, adrenalina.
- HUMOR da IA (base): os 15 humores, cada um com rosto próprio.

Tudo pygame.draw direto, zero Surface por frame.
"""
import math

import pygame

COR_TRACO = (16, 16, 26)
COR_ESCLERA = (248, 248, 252)
COR_PUPILA = (20, 20, 34)

# layout do rosto (frações do raio do corpo)
OLHO_AVANCO = 0.26      # centro dos olhos ao longo do olhar
OLHO_LATERAL = 0.40     # separação lateral de cada olho
OLHO_RAIO = 0.30        # raio do olho (GRANDES — pedido do dono)
BOCA_AVANCO = 0.70      # centro da boca ao longo do olhar
SOBR_RECUO = 1.28       # sobrancelha: recuo além da borda do olho (×r_olho)


def resolver_expressao(l, tempo_s):
    """Prioridade: reação de combate > tell > humor."""
    if getattr(l, "morto", False):
        return "morto"
    if getattr(l, "stun_timer", 0.0) > 0:
        return "tonto"
    if getattr(l, "flash_timer", 0.0) > 0.12:
        return "dor"
    if getattr(l, "canalizando", False):
        return "concentrado"
    brain = getattr(l, "brain", None)
    tell = getattr(brain, "tell_atual", None)
    if tell and getattr(brain, "tempo_combate", 0.0) < tell.get("ate", 0.0):
        if tell.get("tipo") == "instinto":
            return "alerta"
        if tell.get("tipo") == "hesitacao":
            return "confuso"
    if getattr(l, "atacando", False):
        return "esforco"
    if getattr(brain, "acao_atual", "") == "BLOQUEAR":
        return "firmeza"
    if getattr(l, "modo_adrenalina", False):
        return "limite"
    humor = getattr(brain, "humor", "CALMO") or "CALMO"
    return HUMOR_EXPRESSAO.get(humor, "neutro")


HUMOR_EXPRESSAO = {
    "FURIOSO": "furia",
    "BERSERK": "berserk",
    "DETERMINADO": "determinado",
    "CONFIANTE": "confiante",
    "ANIMADO": "animado",
    "EUFORICO": "euforico",
    "EXTASE": "extase",
    "ASSUSTADO": "panico",
    "NERVOSO": "nervoso",
    "DESESPERADO": "desespero",
    "CALMO": "neutro",
    "FOCADO": "focado",
    "GLACIAL": "glacial",
    "ENTEDIADO": "tedio",
    "MELANCOLICO": "tristeza",
}


class _Rosto:
    """Quadro de referência facial + primitivas compostas."""

    def __init__(self, tela, centro, raio, ang_rad, esc_x, esc_y, t, seed,
                 cor_corpo=(200, 60, 70)):
        self.tela = tela
        self.cor_corpo = cor_corpo
        self.cx, self.cy = centro
        self.R = raio
        self.t = t
        self.seed = seed
        # quadro do rosto: f = queixo (olhar), p = direita do rosto
        self.fx, self.fy = math.cos(ang_rad), math.sin(ang_rad)
        self.px, self.py = -math.sin(ang_rad), math.cos(ang_rad)
        self.esc = (esc_x, esc_y)
        # LOD pelo raio EFETIVO em tela (eixo mais apertado do squash):
        # mínimos ABSOLUTOS de traço estouravam o corpo quando a câmera
        # afastava — a auditoria pegou 1474 combinações assim.
        self.Rf = raio * min(esc_x, esc_y)
        # Piso medido pela auditoria: abaixo de ~7px de raio efetivo o
        # rosto vira 3 pixels de ruído e o arredondamento de sub-pixel
        # empurra traço para fora do corpo. Corpo pequeno = ponto limpo.
        self.invisivel = self.Rf < 7.0
        self.simples = self.Rf < 11.0      # só pupilas + boca
        self.r_olho = raio * OLHO_RAIO
        # deslocamentos dos olhos NO QUADRO NÃO-DEFORMADO (o squash é
        # aplicado no fim, por _pt — igual ao corpo).
        self.olho_d = [
            (self.fx * OLHO_AVANCO * raio + self.px * OLHO_LATERAL * lado * raio,
             self.fy * OLHO_AVANCO * raio + self.py * OLHO_LATERAL * lado * raio)
            for lado in (-1, 1)
        ]
        self.olho_c = [self._pt(dx, dy) for dx, dy in self.olho_d]

    # ---------------- quadro ----------------

    def _pt(self, dx, dy):
        """Offset (não-deformado) a partir do centro → ponto de tela.

        O squash entra AQUI, nos eixos de tela, exatamente como na
        elipse do corpo. Aplicá-lo dentro do quadro rotacionado (v4)
        cisalhava o rosto: olhos e sobrancelhas deformavam por eixos
        diferentes e o rosto se desmontava em qualquer aterrissagem.
        """
        ex, ey = self.esc
        return (self.cx + dx * ex, self.cy + dy * ey)

    def F(self, avanco, lateral=0.0):
        """Ponto no quadro do rosto, em frações do raio do corpo."""
        return self._pt((self.fx * avanco + self.px * lateral) * self.R,
                        (self.fy * avanco + self.py * lateral) * self.R)

    def O(self, i, frente=0.0, direita=0.0):
        """Ponto relativo ao CENTRO do olho i, em múltiplos de r_olho."""
        dx, dy = self.olho_d[i]
        return self._pt(
            dx + (self.fx * frente + self.px * direita) * self.r_olho,
            dy + (self.fy * frente + self.py * direita) * self.r_olho,
        )

    def _linha(self, a, b, w=2, cor=COR_TRACO):
        pygame.draw.line(self.tela, cor, (int(a[0]), int(a[1])),
                         (int(b[0]), int(b[1])), max(1, int(w)))

    def _circ(self, c, r, cor, w=0):
        pygame.draw.circle(self.tela, cor, (int(c[0]), int(c[1])),
                           max(1, int(r)), w)

    def _tri(self, a, b, c, cor):
        pygame.draw.polygon(self.tela, cor, [(int(a[0]), int(a[1])),
                                             (int(b[0]), int(b[1])),
                                             (int(c[0]), int(c[1]))])

    def _ro(self):
        """Raio do olho EM TELA (segue o squash do corpo)."""
        return max(1.0, self.r_olho * min(self.esc))

    def _w(self):
        """Espessura de traço proporcional (nunca um mínimo absoluto:
        num corpo pequeno, 2px de traço já vazam para fora)."""
        return max(1, int(round(self._ro() * 0.24)))

    # ---------------- olhos ----------------

    def olho_aberto(self, i, r_mult=1.0, pupila_mult=1.0, olhar=1.0,
                    tremor=0.0):
        """Esclera + pupila mirando o oponente (para onde f aponta)."""
        c = self.olho_c[i]
        ro = self._ro()
        jit = math.sin(self.t * 24 + i * 2.1) * tremor if tremor else 0.0
        if self.simples:
            # LOD distante: só a pupila (a esclera vira ruído de 1px)
            self._circ(c, max(1.0, ro * 0.62), COR_PUPILA)
            return
        r = max(1.0, ro * r_mult)
        self._circ(c, r, COR_ESCLERA)
        pr = max(1.0, ro * 0.46 * pupila_mult)
        alcance = max(0.0, r - pr - 1)
        self._circ((c[0] + (self.fx + self.px * jit) * alcance * olhar,
                    c[1] + (self.fy + self.py * jit) * alcance * olhar),
                   pr, COR_PUPILA)

    def olho_fechado(self, i, curva=0.0, w=None):
        """Pálpebra fechada: traço lateral; curva>0 = arco feliz (^)."""
        w = w or self._w()
        a = self.O(i, 0, -0.85)
        b = self.O(i, 0, 0.85)
        if abs(curva) < 0.01:
            self._linha(a, b, w)
        else:
            m = self.O(i, -curva, 0)  # arqueia para a TESTA (feliz)
            self._linha(a, m, w)
            self._linha(m, b, w)

    def olho_x(self, i):
        w = self._w()
        self._linha(self.O(i, -0.75, -0.75), self.O(i, 0.75, 0.75), w)
        self._linha(self.O(i, 0.75, -0.75), self.O(i, -0.75, 0.75), w)

    def olho_espiral(self, i):
        c = self.olho_c[i]
        ro = self._ro()
        self._circ(c, ro, COR_ESCLERA)
        if self.simples:
            self._circ(c, ro * 0.45, COR_PUPILA)
            return
        pts = []
        for k in range(11):
            fr = k / 10.0
            a = self.t * 7 + fr * math.pi * 3.4 + i * math.pi
            d = ro * 0.78 * fr
            pts.append((c[0] + math.cos(a) * d, c[1] + math.sin(a) * d))
        for k in range(1, 11):
            self._linha(pts[k - 1], pts[k], max(1, self._w() - 1))

    def olho_apertado(self, i):
        """>.< — chevron com a ponta para o QUEIXO (dor)."""
        w = self._w()
        ponta = self.O(i, 0.55, 0)
        self._linha(self.O(i, -0.55, -0.8), ponta, w)
        self._linha(self.O(i, -0.55, 0.8), ponta, w)

    def palpebra(self, i, quanto=0.4):
        """Semicerrado: recorte da TESTA (−f) na cor do corpo + traço."""
        if self.simples:
            return  # no LOD distante a pupila sozinha já é a leitura
        quanto = max(0.05, min(0.75, quanto))
        # cortador: círculo do MESMO raio deslocado para a testa — cobre
        # exatamente a fração `quanto` do olho (offsets pelo helper O,
        # então segue rotação e squash junto com todo o resto).
        cortador = self.O(i, -(2.0 - 2.0 * quanto), 0)
        self._circ(cortador, self._ro() + 1, self.cor_corpo)
        prof = 1.0 - 2.0 * quanto  # posição da borda do corte (−f)
        corda = math.sqrt(max(0.0, 1.0 - prof * prof)) + 0.12
        self._linha(self.O(i, -prof, -corda), self.O(i, -prof, corda),
                    self._w())

    # ---------------- sobrancelhas ----------------

    def sobrancelha(self, i, incl=0.0, subir=0.0, w=None):
        """No quadro do rosto, SEMPRE acima do olho (lado da testa).

        incl > 0: ponta INTERNA desce em direção ao olho (raiva);
        incl < 0: ponta interna sobe (preocupação/tristeza);
        subir  : levanta a sobrancelha inteira (surpresa).
        """
        if self.simples:
            return
        w = w or self._w()
        lado = -1 if i == 0 else 1  # lateral do olho no quadro do rosto
        base_f = -(SOBR_RECUO + subir)  # acima do olho = lado da testa
        externa = self.O(i, base_f - incl * 0.15, 0.85 * lado)
        interna = self.O(i, base_f + incl * 0.62, -0.62 * lado)
        self._linha(externa, interna, w)

    # ---------------- bocas ----------------

    def B(self, frente=0.0, direita=0.0):
        """Ponto relativo ao centro da BOCA, em múltiplos de r_olho."""
        return self._pt(
            self.fx * BOCA_AVANCO * self.R
            + (self.fx * frente + self.px * direita) * self.r_olho,
            self.fy * BOCA_AVANCO * self.R
            + (self.fy * frente + self.py * direita) * self.r_olho,
        )

    def boca_linha(self, larg=0.7, w=None):
        self._linha(self.B(0, -larg), self.B(0, larg), w or self._w())

    def boca_sorriso(self, larg=1.0, prof=0.5, w=None):
        """Sorriso: canto -> queixo -> canto (abre para o oponente)."""
        w = w or self._w()
        a = self.B(-prof * 0.6, -larg)
        m = self.B(prof * 0.5, 0)
        b = self.B(-prof * 0.6, larg)
        self._linha(a, m, w)
        self._linha(m, b, w)

    def boca_triste(self, larg=0.85, w=None):
        """Arco invertido: o meio recua para a testa."""
        w = w or self._w()
        a = self.B(0.18, -larg)
        m = self.B(-0.45, 0)
        b = self.B(0.18, larg)
        self._linha(a, m, w)
        self._linha(m, b, w)

    def boca_aberta(self, r_mult=0.55, grito=False):
        c = self.B(0.15 if grito else 0.0, 0)
        r = self._ro() * r_mult
        self._circ(c, r, COR_TRACO)
        if grito:
            self._circ(c, r * 0.55, (128, 42, 52))

    def boca_dentes(self, larg=1.0):
        """Dentes cerrados: faixa branca com divisões e contorno."""
        if self.simples:
            self.boca_linha(larg * 0.8)
            return
        w_faixa = max(2, int(round(self._ro() * 0.6)))
        w_fino = max(1, self._w() - 1)
        a = self.B(0, -larg)
        b = self.B(0, larg)
        self._linha(a, b, w_faixa, COR_ESCLERA)
        half = w_faixa / 2.0
        # contorno superior/inferior + laterais
        for ff in (-1, 1):
            self._linha((a[0] + self.fx * half * ff, a[1] + self.fy * half * ff),
                        (b[0] + self.fx * half * ff, b[1] + self.fy * half * ff),
                        w_fino)
        for ponta in (a, b):
            self._linha((ponta[0] - self.fx * half, ponta[1] - self.fy * half),
                        (ponta[0] + self.fx * half, ponta[1] + self.fy * half),
                        w_fino)
        # divisões dos dentes
        for fr in (-0.5, 0.0, 0.5):
            c = self.B(0, larg * fr)
            self._linha((c[0] - self.fx * half, c[1] - self.fy * half),
                        (c[0] + self.fx * half, c[1] + self.fy * half), 1)

    def boca_onda(self, larg=0.9, w=None):
        if self.simples:
            self.boca_linha(larg * 0.7)
            return
        w = w or self._w()
        pts = []
        for k in range(7):
            fr = k / 6.0 - 0.5
            onda = math.sin(fr * math.pi * 3 + self.t * 10) * 0.28
            pts.append(self.B(onda, larg * 2 * fr))
        for k in range(1, 7):
            self._linha(pts[k - 1], pts[k], w)

    def boca_smirk(self):
        """Sorriso de canto: só metade sobe."""
        w = self._w()
        a = self.B(0, -0.75)
        m = self.B(0.1, 0.25)
        b = self.B(-0.45, 0.85)
        self._linha(a, m, w)
        self._linha(m, b, w)

    # ---------------- extras ----------------

    def gota_suor(self):
        """Gota na TÊMPORA direita, escorrendo para o queixo."""
        if self.simples:
            return
        # trilho DENTRO do corpo: |(avanco, lateral)| <= ~0.86R sempre
        queda = ((self.t * 2.0 + self.seed * 0.13) % 1.0) * 0.42
        g = self.F(0.05 + queda, 0.72)
        r = max(1.0, self._ro() * 0.3)
        cor = (140, 208, 248)
        self._circ(g, r, cor)
        self._tri((g[0] - self.px * r, g[1] - self.py * r),
                  (g[0] + self.px * r, g[1] + self.py * r),
                  (g[0] - self.fx * r * 1.7, g[1] - self.fy * r * 1.7), cor)

    def lagrima(self, i=1):
        """Lágrima nascendo no canto do olho e escorrendo ao queixo."""
        if self.simples:
            return
        queda = ((self.t * 1.4 + self.seed * 0.29) % 1.0)
        c = self.O(i, 0.85 + queda * 0.35, 0.25)
        r = max(1.0, self._ro() * 0.24)
        self._circ(c, r, (150, 205, 250))

    def veia_raiva(self):
        """Cruz de veia na NUCA (lado oposto ao olhar) — nunca colide."""
        if self.simples:
            return
        p = self.F(-0.52, 0.42)
        r = self._ro() * (0.5 + 0.09 * math.sin(self.t * 10))
        cor = (235, 76, 76)
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            self._linha((p[0] + math.cos(a) * r * 0.3, p[1] + math.sin(a) * r * 0.3),
                        (p[0] + math.cos(a) * r, p[1] + math.sin(a) * r),
                        max(1, self._w() - 1), cor)

    def brilho_pupila(self, i):
        """Pupila-ESTRELA (êxtase): losango dourado girando sobre a
        pupila, com centro claro — não confunde com o X do morto."""
        if self.simples:
            return
        c = self.O(i, 0.28, 0)
        r = self._ro() * 0.42
        a0 = self.t * 1.5
        pts = []
        for k in range(8):
            a = a0 + k * math.pi / 4
            d = r if k % 2 == 0 else r * 0.42
            pts.append((c[0] + math.cos(a) * d, c[1] + math.sin(a) * d))
        pygame.draw.polygon(self.tela, (255, 214, 90),
                            [(int(x), int(y)) for x, y in pts])
        self._circ(c, max(1, r * 0.3), (255, 250, 220))

    def faiscas_alerta(self):
        """Tracinhos de sobressalto saindo da testa."""
        if self.simples:
            return
        for k in (-1, 0, 1):
            a = self.F(-0.55 - 0.06 * abs(k), 0.26 * k)
            b = self.F(-0.78 - 0.08 * abs(k), 0.38 * k)
            self._linha(a, b, max(1, self._w() - 1))


# ===========================================================================
# CATÁLOGO DE EXPRESSÕES
# ===========================================================================

def _expr_neutro(f, t):
    f.olho_aberto(0)
    f.olho_aberto(1)
    f.boca_linha(0.7)


def _expr_focado(f, t):
    f.olho_aberto(0)
    f.olho_aberto(1)
    f.palpebra(0, 0.34)
    f.palpebra(1, 0.34)
    f.sobrancelha(0, incl=0.45)
    f.sobrancelha(1, incl=0.45)
    f.boca_linha(0.6)


def _expr_glacial(f, t):
    f.olho_aberto(0, pupila_mult=0.8)
    f.olho_aberto(1, pupila_mult=0.8)
    f.palpebra(0, 0.46)
    f.palpebra(1, 0.46)
    f.boca_linha(0.9)


def _expr_determinado(f, t):
    f.olho_aberto(0)
    f.olho_aberto(1)
    f.sobrancelha(0, incl=0.7)
    f.sobrancelha(1, incl=0.7)
    f.boca_linha(0.8, w=None)


def _expr_furia(f, t):
    f.olho_aberto(0, r_mult=0.94, pupila_mult=0.68)
    f.olho_aberto(1, r_mult=0.94, pupila_mult=0.68)
    f.sobrancelha(0, incl=1.0, w=None)
    f.sobrancelha(1, incl=1.0, w=None)
    f.boca_dentes(1.0)
    f.veia_raiva()


def _expr_berserk(f, t):
    f.olho_aberto(0, r_mult=1.12, pupila_mult=0.4)
    f.olho_aberto(1, r_mult=0.9, pupila_mult=1.25)
    f.sobrancelha(0, incl=1.0)
    f.sobrancelha(1, incl=0.55)
    f.boca_sorriso(1.25, 0.75, w=None)
    f.veia_raiva()


def _expr_confiante(f, t):
    f.olho_aberto(0)
    f.olho_aberto(1)
    f.palpebra(0, 0.3)
    f.palpebra(1, 0.3)
    f.boca_smirk()


def _expr_animado(f, t):
    f.olho_aberto(0, r_mult=1.08)
    f.olho_aberto(1, r_mult=1.08)
    f.sobrancelha(0, subir=0.35)
    f.sobrancelha(1, subir=0.35)
    f.boca_sorriso(1.0, 0.5)


def _expr_euforico(f, t):
    f.olho_fechado(0, curva=0.6)
    f.olho_fechado(1, curva=0.6)
    f.boca_aberta(0.75)


def _expr_extase(f, t):
    f.olho_aberto(0, r_mult=1.1, pupila_mult=1.35)
    f.olho_aberto(1, r_mult=1.1, pupila_mult=1.35)
    f.brilho_pupila(0)
    f.brilho_pupila(1)
    f.boca_aberta(0.5)


def _expr_panico(f, t):
    f.olho_aberto(0, r_mult=1.28, pupila_mult=0.42)
    f.olho_aberto(1, r_mult=1.28, pupila_mult=0.42)
    f.sobrancelha(0, incl=-0.7, subir=0.5)
    f.sobrancelha(1, incl=-0.7, subir=0.5)
    f.boca_onda(0.85)
    f.gota_suor()


def _expr_nervoso(f, t):
    f.olho_aberto(0, tremor=0.35)
    f.olho_aberto(1, tremor=0.35)
    f.sobrancelha(0, incl=-0.5)
    f.sobrancelha(1, incl=-0.5)
    f.boca_onda(0.7)
    f.gota_suor()


def _expr_desespero(f, t):
    f.olho_aberto(0, r_mult=1.22, pupila_mult=0.5)
    f.olho_aberto(1, r_mult=1.22, pupila_mult=0.5)
    f.sobrancelha(0, incl=-1.0, subir=0.4)
    f.sobrancelha(1, incl=-1.0, subir=0.4)
    f.boca_aberta(0.62, grito=True)
    f.gota_suor()


def _expr_tedio(f, t):
    f.olho_aberto(0)
    f.olho_aberto(1)
    f.palpebra(0, 0.58)
    f.palpebra(1, 0.58)
    f.boca_triste(0.55)


def _expr_tristeza(f, t):
    f.olho_aberto(0, pupila_mult=0.85, olhar=0.45)
    f.olho_aberto(1, pupila_mult=0.85, olhar=0.45)
    f.sobrancelha(0, incl=-0.9)
    f.sobrancelha(1, incl=-0.9)
    f.boca_triste(0.8)
    f.lagrima()


def _expr_morto(f, t):
    f.olho_x(0)
    f.olho_x(1)
    f.boca_linha(0.6)


def _expr_tonto(f, t):
    f.olho_espiral(0)
    f.olho_espiral(1)
    f.boca_onda(0.75)


def _expr_dor(f, t):
    f.olho_apertado(0)
    f.olho_apertado(1)
    f.boca_aberta(0.55, grito=True)


def _expr_esforco(f, t):
    f.olho_aberto(0, r_mult=0.85)
    f.olho_aberto(1, r_mult=0.85)
    f.sobrancelha(0, incl=0.85)
    f.sobrancelha(1, incl=0.85)
    f.boca_dentes(0.9)


def _expr_firmeza(f, t):
    f.olho_aberto(0, r_mult=0.85)
    f.olho_aberto(1, r_mult=0.85)
    f.palpebra(0, 0.4)
    f.palpebra(1, 0.4)
    f.sobrancelha(0, incl=0.6)
    f.sobrancelha(1, incl=0.6)
    f.boca_linha(0.9)


def _expr_alerta(f, t):
    f.olho_aberto(0, r_mult=1.28, pupila_mult=0.55)
    f.olho_aberto(1, r_mult=1.28, pupila_mult=0.55)
    f.sobrancelha(0, subir=0.65)
    f.sobrancelha(1, subir=0.65)
    f.boca_aberta(0.4)
    f.faiscas_alerta()


def _expr_confuso(f, t):
    f.olho_aberto(0, r_mult=1.18)
    f.olho_aberto(1, r_mult=0.86)
    f.palpebra(1, 0.42)
    f.sobrancelha(0, subir=0.6)
    f.sobrancelha(1, incl=0.5)
    f.boca_onda(0.55)


def _expr_limite(f, t):
    f.olho_aberto(0, r_mult=0.9, pupila_mult=1.2)
    f.olho_aberto(1, r_mult=0.9, pupila_mult=1.2)
    f.sobrancelha(0, incl=-0.6)
    f.sobrancelha(1, incl=-0.6)
    f.boca_dentes(0.8)
    f.gota_suor()


def _expr_concentrado(f, t):
    f.olho_fechado(0)
    f.olho_fechado(1)
    f.sobrancelha(0, incl=0.3)
    f.sobrancelha(1, incl=0.3)
    f.boca_linha(0.5)


EXPRESSOES = {
    "neutro": _expr_neutro,
    "focado": _expr_focado,
    "glacial": _expr_glacial,
    "determinado": _expr_determinado,
    "furia": _expr_furia,
    "berserk": _expr_berserk,
    "confiante": _expr_confiante,
    "animado": _expr_animado,
    "euforico": _expr_euforico,
    "extase": _expr_extase,
    "panico": _expr_panico,
    "nervoso": _expr_nervoso,
    "desespero": _expr_desespero,
    "tedio": _expr_tedio,
    "tristeza": _expr_tristeza,
    "morto": _expr_morto,
    "tonto": _expr_tonto,
    "dor": _expr_dor,
    "esforco": _expr_esforco,
    "firmeza": _expr_firmeza,
    "alerta": _expr_alerta,
    "confuso": _expr_confuso,
    "limite": _expr_limite,
    "concentrado": _expr_concentrado,
}

# expressões com olhos já fechados/especiais: piscar não se aplica
SEM_PISCADA = {"morto", "tonto", "dor", "euforico", "concentrado"}


def desenhar_rosto(tela, centro, raio, ang_olhar_deg, esc_x, esc_y,
                   expressao, t, seed, cor_corpo=(200, 60, 70)):
    """Desenha o rosto completo para a expressão dada."""
    f = _Rosto(tela, centro, raio, math.radians(ang_olhar_deg),
               esc_x, esc_y, t, seed, cor_corpo=cor_corpo)
    if f.invisivel:
        return
    EXPRESSOES.get(expressao, _expr_neutro)(f, t)
    # Piscada como OVERLAY: cobre os olhos com a cor do corpo por cima
    # de qualquer expressão (boca/sobrancelhas/extras ficam).
    piscando = (
        expressao not in SEM_PISCADA
        and ((t + (seed % 10) * 0.37) % 3.4) < 0.12
    )
    if piscando:
        for i in range(2):
            f._circ(f.olho_c[i], f.r_olho * 1.5, cor_corpo)
            f.olho_fechado(i)
