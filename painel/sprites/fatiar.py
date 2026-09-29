# -*- coding: utf-8 -*-
"""Achar os quadros da folha sozinho, e deixar ajustar a mao.

Tres jeitos, do mais confiavel ao mais geral:

  linhas       a grade DESENHADA (a IA desenha): as linhas viram as bordas
               das celulas. Na 11243 sao 4 horizontais e 5 verticais.
  vaos         sem linha, mas com vao vazio entre os quadros: as fileiras e
               colunas vazias viram as bordas.
  uniforme     colunas x linhas iguais, contadas por quem esta olhando.
  componentes  nem grade nem vao: cada desenho (com as gotas que estao perto
               dele) vira um quadro, em ordem de leitura.

Celula vazia (a IA deixa o fim da grade em branco) nao vira quadro.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .rotulos import rotular

MODOS = ("auto", "linhas", "vaos", "uniforme", "componentes")


@dataclass
class Grade:
    """As bordas das celulas. `xs` e `ys` incluem 0 e o tamanho."""
    xs: list
    ys: list
    origem: str = ""
    excluidas: set = field(default_factory=set)

    @property
    def colunas(self) -> int:
        return max(0, len(self.xs) - 1)

    @property
    def linhas(self) -> int:
        return max(0, len(self.ys) - 1)

    def celulas(self) -> list:
        """(x0, y0, x1, y1) de cada celula, da esquerda para a direita e de
        cima para baixo."""
        saida = []
        for j in range(self.linhas):
            for i in range(self.colunas):
                saida.append((int(self.xs[i]), int(self.ys[j]),
                              int(self.xs[i + 1]), int(self.ys[j + 1])))
        return saida

    def para_dict(self) -> dict:
        return {"xs": [int(x) for x in self.xs], "ys": [int(y) for y in self.ys],
                "origem": self.origem, "excluidas": sorted(self.excluidas)}


def _centro(faixa) -> int:
    return int(round((faixa[0] + faixa[1]) / 2))


def grade_por_linhas(horizontais: list, verticais: list, largura: int,
                     altura: int, borda: float = 0.03):
    """As linhas desenhadas viram bordas. As que colam na moldura (menos de
    3% dela) sao a moldura, nao divisao. None se nao ha linha nenhuma."""
    xs = [_centro(f) for f in verticais
          if borda * largura < _centro(f) < (1 - borda) * largura]
    ys = [_centro(f) for f in horizontais
          if borda * altura < _centro(f) < (1 - borda) * altura]
    if not xs and not ys:
        return None
    return Grade([0] + sorted(xs) + [largura], [0] + sorted(ys) + [altura],
                 origem="linhas")


def _vaos(ocupado: np.ndarray, vao_min: int) -> list:
    """Bordas no meio de cada vao interno (sequencia de vazios)."""
    n = len(ocupado)
    cheios = np.nonzero(ocupado)[0]
    if not len(cheios):
        return []
    primeiro, ultimo = int(cheios[0]), int(cheios[-1])
    bordas = []
    i = primeiro
    while i <= ultimo:
        if not ocupado[i]:
            j = i
            while j <= ultimo and not ocupado[j]:
                j += 1
            if j - i >= vao_min:
                bordas.append((i, j))
            i = j
        else:
            i += 1
    # segmentos estreitos demais (uma gota separada da bola por um vao)
    # nao sao quadro: o vao mais estreito ao lado dele deixa de ser borda
    while len(bordas) >= 1:
        cortes = [primeiro] + [(a + b) // 2 for a, b in bordas] + [ultimo + 1]
        larguras = np.diff(cortes)
        mediana = float(np.median(larguras))
        k = int(np.argmin(larguras))
        if larguras[k] >= 0.5 * mediana:
            break
        vizinhos = [v for v in (k - 1, k) if 0 <= v < len(bordas)]
        tirar = min(vizinhos, key=lambda v: bordas[v][1] - bordas[v][0])
        bordas.pop(tirar)
    return [0] + [(a + b) // 2 for a, b in bordas] + [n]


def grade_por_vaos(mascara: np.ndarray, vao_min: int = 3):
    """Fileiras e colunas totalmente vazias viram bordas. None se nao ha."""
    altura, largura = mascara.shape
    ys = _vaos(mascara.any(1), vao_min)
    xs = _vaos(mascara.any(0), vao_min)
    if len(xs) <= 2 and len(ys) <= 2:
        return None
    return Grade(xs or [0, largura], ys or [0, altura], origem="vaos")


def grade_uniforme(largura: int, altura: int, colunas: int, linhas: int):
    colunas, linhas = max(1, int(colunas)), max(1, int(linhas))
    xs = [int(round(i * largura / colunas)) for i in range(colunas + 1)]
    ys = [int(round(j * altura / linhas)) for j in range(linhas + 1)]
    return Grade(xs, ys, origem="uniforme")


def por_componentes(mascara: np.ndarray, juntar: int = 16,
                    area_min: int = 50) -> list:
    """Cada desenho vira um quadro. Caixas a menos de `juntar` px uma da
    outra sao do mesmo quadro (as gotas que acompanham a bola)."""
    comps = rotular(mascara)
    if not comps.n:
        return []
    caixas = comps.caixas.astype(np.int64)
    pai = np.arange(comps.n)

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    x0, y0, x1, y1 = caixas.T
    # distancia entre retangulos (0 se se tocam), todos contra todos
    dx = np.maximum(0, np.maximum(x0[:, None] - x1[None, :],
                                  x0[None, :] - x1[:, None]))
    dy = np.maximum(0, np.maximum(y0[:, None] - y1[None, :],
                                  y0[None, :] - y1[:, None]))
    perto = np.argwhere((np.maximum(dx, dy) <= juntar)
                        & (np.arange(comps.n)[:, None]
                           < np.arange(comps.n)[None, :]))
    for a, b in perto:
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            pai[max(ra, rb)] = min(ra, rb)
    grupos: dict = {}
    for i in range(comps.n):
        grupos.setdefault(raiz(i), []).append(i)
    quadros = []
    for membros in grupos.values():
        area = int(comps.areas[membros].sum())
        if area < area_min:
            continue
        c = caixas[membros]
        quadros.append((int(c[:, 0].min()), int(c[:, 1].min()),
                        int(c[:, 2].max()), int(c[:, 3].max())))
    return ordem_de_leitura(quadros)


def ordem_de_leitura(caixas: list) -> list:
    """De cima para baixo em fileiras, e da esquerda para a direita."""
    if not caixas:
        return []
    alturas = [c[3] - c[1] for c in caixas]
    tolerancia = 0.5 * float(np.median(alturas))
    restantes = sorted(caixas, key=lambda c: (c[1] + c[3]) / 2)
    fileiras = []
    for c in restantes:
        meio = (c[1] + c[3]) / 2
        if fileiras and abs(meio - fileiras[-1][0]) <= tolerancia:
            fileiras[-1][1].append(c)
        else:
            fileiras.append([meio, [c]])
    return [c for _m, fila in fileiras for c in sorted(fila)]


def conteudo(alfa: np.ndarray, caixa, limite: int = 16) -> int:
    x0, y0, x1, y1 = caixa
    return int((alfa[y0:y1, x0:x1] >= limite).sum())


def quadros_da_grade(alfa: np.ndarray, grade: Grade, ignorar_vazias=True,
                     limite: int = 16, minimo_px: int = 50) -> list:
    """As celulas que valem: sem as excluidas a mao e, se pedido, sem as
    vazias (menos de `minimo_px` pixels visiveis)."""
    saida = []
    for i, celula in enumerate(grade.celulas()):
        if i in grade.excluidas:
            continue
        if ignorar_vazias and conteudo(alfa, celula, limite) < minimo_px:
            continue
        saida.append(celula)
    return saida


def achar(alfa: np.ndarray, mascara_bruta: np.ndarray, modo: str = "auto",
          linhas_h=(), linhas_v=(), colunas: int = 0, linhas: int = 0,
          limite: int = 16, juntar: int = 16):
    """(grade ou None, modo usado). `componentes` nao tem grade."""
    altura, largura = alfa.shape
    visivel = alfa >= limite
    if modo in ("auto", "linhas"):
        grade = grade_por_linhas(list(linhas_h), list(linhas_v), largura,
                                 altura)
        if grade is not None or modo == "linhas":
            return grade, "linhas"
    if modo in ("auto", "vaos"):
        grade = grade_por_vaos(visivel)
        if grade is not None or modo == "vaos":
            return grade, "vaos"
    if modo == "uniforme":
        return grade_uniforme(largura, altura, colunas or 1, linhas or 1), \
            "uniforme"
    return None, "componentes"


__all__ = ["Grade", "MODOS", "achar", "conteudo", "grade_por_linhas",
           "grade_por_vaos", "grade_uniforme", "ordem_de_leitura",
           "por_componentes", "quadros_da_grade"]
