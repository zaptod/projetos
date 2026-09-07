# -*- coding: utf-8 -*-
"""Onde ficam as coisas, e o que a configuracao diz.

Duas responsabilidades pequenas que todo modulo daqui precisa: achar a pasta
de saida de um canal, e ler um `config/*.json` sem repetir tratamento de erro
em sete lugares.

As chaves comecadas por `_` nos JSON sao comentarios para quem abre o arquivo
na mao. Elas atravessam o `carregar` sem incomodar ninguem, e e de proposito:
JSON nao tem comentario, e config sem explicacao vira config que ninguem mexe.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config"
OUTPUTS = RAIZ / "outputs"

# `canal_00001`: o mesmo formato de `generation_00002` e `historia_00003` nos
# projetos vizinhos. Cinco digitos porque quatro ja apertaram uma vez la.
PADRAO_ID = re.compile(r"^canal_(\d{5})$")


class NaoAchou(RuntimeError):
    """Erro humano: o que se procurou, e o que fazer para resolver."""


def carregar(nome: str) -> dict:
    """O `config/<nome>.json`, ja lido. Levanta com o caminho quando falta."""
    caminho = CONFIG / f"{nome}.json"
    if not caminho.is_file():
        raise NaoAchou(f"falta o arquivo de configuracao {caminho}")
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise NaoAchou(
            f"{caminho} nao e JSON valido (linha {exc.lineno}): {exc.msg}"
        ) from exc


def pasta_do_canal(canal_id: str) -> Path:
    """A pasta daquele canal. Levanta se o id nao existir em disco."""
    if not PADRAO_ID.match(str(canal_id)):
        raise NaoAchou(
            f"{canal_id!r} nao parece um id de canal (esperado: canal_00001). "
            "Veja os que existem com: python main.py status")
    pasta = OUTPUTS / str(canal_id)
    if not pasta.is_dir():
        raise NaoAchou(
            f"nao ha canal {canal_id} em {OUTPUTS}. "
            "Comece com: python main.py canal <url>")
    return pasta


def canais() -> list:
    """Os ids de canal ja catalogados, em ordem."""
    if not OUTPUTS.is_dir():
        return []
    return sorted(p.name for p in OUTPUTS.iterdir()
                  if p.is_dir() and PADRAO_ID.match(p.name))


def proximo_id() -> str:
    """O proximo `canal_000NN` livre.

    Le a pasta em vez de guardar um contador: contador em arquivo desanda
    quando alguem apaga uma pasta na mao, e ai duas coletas gravam por cima
    uma da outra.
    """
    usados = [int(PADRAO_ID.match(nome).group(1)) for nome in canais()]
    return f"canal_{max(usados, default=0) + 1:05d}"


def criar_canal() -> tuple:
    """Reserva a proxima pasta de canal. Devolve (canal_id, pasta)."""
    canal_id = proximo_id()
    pasta = OUTPUTS / canal_id
    pasta.mkdir(parents=True, exist_ok=False)
    return canal_id, pasta
