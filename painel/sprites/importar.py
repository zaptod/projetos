# -*- coding: utf-8 -*-
"""Importacao de sprite do Atelie, sem Tk nem HTTP.

O modulo conserva o motor da Oficina: a diferenca e que recebe uma imagem
do Adrian, corta nos tres modos simples e grava no catalogo de usuario.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from esteira_sprites import animacao

from . import alinhar, fatiar, fundo_auto, limpeza, medidas

MAX_BYTES = 20 * 1024 * 1024
MODOS = ("auto", "grade", "tira")
_NOME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass
class Resultado:
    original: np.ndarray
    limpo: np.ndarray
    caixas: list
    alinhado: alinhar.Alinhado
    folha: np.ndarray
    colunas: int
    linhas: int
    fundo: dict
    ilhas_tiradas: int
    avisos: list


def abrir_bytes(conteudo: bytes) -> np.ndarray:
    """Abre PNG/JPEG/WebP ate 20 MB, sempre como RGBA."""
    if not 0 < len(conteudo) <= MAX_BYTES:
        raise ValueError("imagem deve ter ate 20 MB")
    try:
        with Image.open(io.BytesIO(conteudo)) as imagem:
            if imagem.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError("envie PNG, JPG ou WebP")
            imagem.load()
            return limpeza.para_array(imagem)
    except (OSError, ValueError) as exc:
        raise ValueError("imagem invalida") from exc


def _modo_ancora(ancora: str) -> str:
    return {"pes": "pe", "base": "pe", "centro": "caixa"}.get(ancora, "pe")


def processar(origem, *, tolerancia: float = 24, modo: str = "auto",
              colunas: int = 0, linhas: int = 0, ancora: str = "pes",
              ilha_min: int = 12, juntar: int = 16, margem: int = 4,
              excluir: list[int] | None = None, ordem: list[int] | None = None,
              espelhar: bool = False) -> Resultado:
    """Limpa, acha quadros e alinha. `origem` pode ser imagem ou array."""
    if modo not in MODOS:
        raise ValueError("modo de corte invalido")
    arr = limpeza.para_array(origem)
    # o mesmo fundo automatico da esteira (02/10/2026): liso, xadrez desenhado
    # (inclusive fechado dentro do desenho) ou ja transparente
    limpo, achado = fundo_auto.remover(arr, tolerancia=tolerancia)
    metodo = achado["tipo"]
    fundo = {"cor": achado["cores"][0] if achado["cores"] else None,
             "transparente": metodo == "transparente", "xadrez": metodo == "xadrez"}
    limpo = limpeza.alfa_minimo(limpo, 8)
    if achado["cores"]:
        limpo = limpeza.despill(limpo, achado["cores"][0], 1.0, 40)
    limpo, ilhas = limpeza.tirar_ilhas(limpo, ilha_min)
    alfa = limpo[..., 3]
    if modo == "grade":
        if int(colunas) < 1 or int(linhas) < 1:
            raise ValueError("informe colunas e linhas da grade")
        grade = fatiar.grade_uniforme(arr.shape[1], arr.shape[0], colunas, linhas)
        caixas = fatiar.quadros_da_grade(alfa, grade, minimo_px=1)
    elif modo == "tira":
        if int(colunas) < 1:
            raise ValueError("informe quantos quadros ha na tira")
        grade = fatiar.grade_uniforme(arr.shape[1], arr.shape[0], colunas, 1)
        caixas = fatiar.quadros_da_grade(alfa, grade, minimo_px=1)
    else:
        caixas = fatiar.por_componentes(alfa >= 16, juntar, 1)
    excluir = {int(i) for i in (excluir or [])}
    caixas = [caixa for i, caixa in enumerate(caixas) if i not in excluir]
    if ordem:
        try:
            caixas = [caixas[int(i)] for i in ordem]
        except (IndexError, ValueError) as exc:
            raise ValueError("ordem de quadros invalida") from exc
    alinhado = alinhar.alinhar(limpo, caixas, _modo_ancora(ancora), margem,
                               espelhar=espelhar)
    folha, cols, lins = alinhar.montar_folha(alinhado.quadros,
                                             colunas if modo == "grade" else 0)
    avisos = [medidas.resumo({"quadros": len(caixas), "linhas_de_grade": {"folha": 0},
                              "franja": {"folha": {"visivel": 0, "oculta": 0}},
                              "pontinhos": {"folha": 0}, "buracos": 0,
                              "ancoras_desvio_px": 0.0})]
    sobra = fundo_auto.sobra_de_fundo(limpo)
    if sobra > 0.02:
        avisos.append(f"o fundo não saiu inteiro: {sobra:.0%} da borda continua opaca "
                      "(ajuste a tolerância)")
    return Resultado(arr, limpo, caixas, alinhado, folha, cols, lins,
                     {"metodo": metodo, **fundo}, ilhas, avisos)


def espelhar(resultado: Resultado) -> Resultado:
    """Inverte cada quadro final, conservando a grade e a ancora."""
    quadros = [q[:, ::-1].copy() for q in resultado.alinhado.quadros]
    folha, cols, lins = alinhar.montar_folha(quadros, resultado.colunas)
    a = resultado.alinhado
    novo = alinhar.Alinhado(quadros, a.celula,
                            (a.celula[0] - a.ancora[0], a.ancora[1]),
                            a.escala, a.ancoras_de_origem)
    return Resultado(resultado.original, resultado.limpo, resultado.caixas, novo,
                     folha, cols, lins, resultado.fundo, resultado.ilhas_tiradas,
                     list(resultado.avisos))


def salvar(resultado: Resultado, pasta, slot: dict, fonte: str,
           *, substituir: bool = False) -> dict:
    """Grava folha, metadados e previa no diretorio do slot."""
    pasta = Path(pasta)
    arquivo = pasta / f"{slot['id']}.png"
    if arquivo.exists() and not substituir:
        raise FileExistsError(str(arquivo))
    pasta.mkdir(parents=True, exist_ok=True)
    limpeza.para_imagem(resultado.folha).save(arquivo, "PNG", optimize=True)
    item = {"grade": [resultado.colunas, resultado.linhas],
            "animacao": {"ancora": slot.get("ancora", "pes"), "escala": False,
                          "ciclos": [{"nome": slot["id"], "quadros": list(range(len(resultado.alinhado.quadros))),
                                      "fps": slot.get("fps", 8), "loop": bool(slot.get("laco", True))}]}}
    previas = animacao.previa(resultado.folha, item, arquivo.with_suffix(""))
    meta = {"slot": slot["id"], "quadros": len(resultado.alinhado.quadros),
            "grade": {"colunas": resultado.colunas, "linhas": resultado.linhas},
            "fps": slot.get("fps", 8), "laco": bool(slot.get("laco", True)),
            "ancora": slot.get("ancora", "pes"), "celula": list(resultado.alinhado.celula),
            "origem": {"arquivo": Path(fonte).name, "data": datetime.now().isoformat(timespec="seconds")},
            "avisos": resultado.avisos}
    arquivo.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"png": str(arquivo), "json": str(arquivo.with_suffix(".json")), **previas}


def catalogo(caminho=None) -> dict:
    caminho = Path(caminho) if caminho else Path(__file__).parents[2] / "palco" / "biblioteca" / "sprites_usuario" / "catalogo.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def slot_do_catalogo(sujeito: str, slot: str, caminho=None) -> dict:
    if not _NOME.fullmatch(sujeito) or not _NOME.fullmatch(slot):
        raise ValueError("sujeito ou slot invalido")
    try:
        slots = catalogo(caminho)["sujeitos"][sujeito]["slots"]
        return next(s for s in slots if s.get("id") == slot)
    except (KeyError, StopIteration) as exc:
        raise ValueError("slot inexistente") from exc


__all__ = ["MAX_BYTES", "MODOS", "Resultado", "abrir_bytes", "catalogo",
           "espelhar", "processar", "salvar", "slot_do_catalogo"]
