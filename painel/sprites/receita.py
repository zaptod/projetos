# -*- coding: utf-8 -*-
"""A receita: todos os parametros da limpeza ao alinhamento, num lugar so.

Ela e o estado da pagina. "Desfazer" e voltar para a receita anterior (a
imagem de origem nunca muda), e o LOTE e aplicar a mesma receita a varias
folhas -- menos o ajuste a mao da grade, que e de uma folha so.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

import numpy as np

from . import alinhar as _alinhar
from . import fatiar as _fatiar
from . import limpeza

FUNDOS = ("auto", "nenhum", "bordas", "cor")


@dataclass
class Receita:
    # ---- fundo
    fundo: str = "auto"              # auto | nenhum | bordas | cor
    cor_fundo: list | None = None    # None = a estimada (borda ou fantasma)
    tolerancia: float = 24.0
    suavidade: float = 16.0
    descontaminar: bool = True
    alfa_minimo: int = 8
    # ---- despill
    despill: float = 1.0
    cor_franja: list | None = None   # None = a do fundo
    tolerancia_franja: float = 40.0
    # ---- sanear
    apagar_linhas: bool = True
    ilha_min: int = 12
    # ---- fatiar
    fatiar: str = "auto"
    colunas: int = 0
    linhas: int = 0
    juntar: int = 16
    ignorar_vazias: bool = True
    quadro_min_px: int = 50
    xs: list | None = None           # grade ajustada a mao
    ys: list | None = None
    excluidas: list = field(default_factory=list)
    # ---- alinhar
    ancora: str = "massa"            # massa | caixa | pe
    margem: int = 4
    largura_max: int = 512
    espelhar: bool = False
    colunas_saida: int = 0           # 0 = as colunas da grade

    def mudar(self, **kw) -> "Receita":
        return replace(self, **kw)

    def para_lote(self) -> "Receita":
        """A mesma receita sem o que e de UMA folha (a grade feita a mao)."""
        return replace(self, xs=None, ys=None, excluidas=[])

    def para_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, dados: dict) -> "Receita":
        conhecidos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (dados or {}).items()
                      if k in conhecidos})

    def salvar(self, caminho) -> Path:
        caminho = Path(caminho)
        caminho.write_text(json.dumps(self.para_dict(), ensure_ascii=False,
                                      indent=2), encoding="utf-8")
        return caminho

    @classmethod
    def ler(cls, caminho) -> "Receita":
        return cls.de_dict(json.loads(Path(caminho).read_text(
            encoding="utf-8")))


@dataclass
class Resultado:
    original: np.ndarray
    limpo: np.ndarray
    fundo: dict                      # {"metodo", "cor", "transparente"}
    franja: tuple | None
    linhas_h: list
    linhas_v: list
    grade: object                    # fatiar.Grade ou None (componentes)
    modo_fatiar: str
    caixas: list
    alinhado: object                 # alinhar.Alinhado
    folha: np.ndarray
    colunas: int
    linhas: int
    ilhas_tiradas: int = 0


def mascara_bruta(arr: np.ndarray, fundo: dict, tolerancia: float):
    """O que NAO e fundo, antes de limpar: e nela que a grade aparece.
    Folha transparente: alfa > 0 (o fantasma da grade incluso). Folha opaca:
    o que foge da cor do fundo."""
    if fundo.get("transparente") or fundo.get("cor") is None:
        return arr[..., 3] > 0
    return limpeza.distancia(arr[..., :3], fundo["cor"]) > tolerancia


def processar(origem, receita: Receita | None = None) -> Resultado:
    """Da folha de origem ate a folha final, sem tocar na origem."""
    r = receita or Receita()
    arr = limpeza.para_array(origem)
    info = limpeza.estimar_fundo(arr)
    metodo = r.fundo
    if metodo == "auto":
        metodo = "nenhum" if info["transparente"] else "bordas"
    cor = tuple(r.cor_fundo) if r.cor_fundo else info["cor"]
    fundo = {"metodo": metodo, "cor": cor,
             "transparente": info["transparente"]}

    bruta = mascara_bruta(arr, {"transparente": metodo == "nenhum",
                                "cor": cor}, r.tolerancia)
    linhas_h = limpeza.detectar_linhas(bruta)
    linhas_v = limpeza.detectar_linhas(bruta.T)

    limpo = limpeza.remover_fundo(arr, metodo, cor, r.tolerancia,
                                  r.suavidade, r.descontaminar)
    limpo = limpeza.alfa_minimo(limpo, r.alfa_minimo)
    if r.apagar_linhas and (linhas_h or linhas_v):
        limpo = limpeza.apagar_linhas(limpo, linhas_h, linhas_v)
    franja = tuple(r.cor_franja) if r.cor_franja else cor
    if r.despill > 0 and franja is not None:
        limpo = limpeza.despill(limpo, franja, r.despill, r.tolerancia_franja)
    limpo, ilhas = limpeza.tirar_ilhas(limpo, r.ilha_min,
                                       alfa=max(1, r.alfa_minimo))

    alfa = limpo[..., 3]
    if r.xs and r.ys and len(r.xs) >= 2 and len(r.ys) >= 2:
        grade = _fatiar.Grade(sorted(int(x) for x in r.xs),
                              sorted(int(y) for y in r.ys), origem="manual")
        modo = "manual"
    else:
        grade, modo = _fatiar.achar(alfa, bruta, r.fatiar, linhas_h, linhas_v,
                                    r.colunas, r.linhas, juntar=r.juntar)
    if grade is not None:
        grade.excluidas = set(int(i) for i in r.excluidas)
        caixas = _fatiar.quadros_da_grade(alfa, grade, r.ignorar_vazias,
                                          minimo_px=r.quadro_min_px)
    else:
        caixas = _fatiar.por_componentes(alfa >= 16, r.juntar,
                                         r.quadro_min_px)
        caixas = [c for i, c in enumerate(caixas) if i not in set(r.excluidas)]

    alinhado = _alinhar.alinhar(limpo, caixas, r.ancora, r.margem,
                                largura_max=r.largura_max,
                                espelhar=r.espelhar)
    colunas_saida = r.colunas_saida or (grade.colunas if grade else 0)
    folha, colunas, linhas = _alinhar.montar_folha(alinhado.quadros,
                                                   colunas_saida)
    return Resultado(arr, limpo, fundo, franja, linhas_h, linhas_v, grade,
                     modo, caixas, alinhado, folha, colunas, linhas, ilhas)


__all__ = ["FUNDOS", "Receita", "Resultado", "mascara_bruta", "processar"]
