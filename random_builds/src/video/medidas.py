# -*- coding: utf-8 -*-
"""Conferir arquivo de video ANTES de confiar nele.

Existe por causa de um bug caro (31/08/2026): um segmento de um video de
historia ficou sem o `moov atom` (o ffmpeg que o escrevia morreu no meio) e
o `concat` seguinte simplesmente PAROU nele — imprimindo "Error during
demuxing" no stderr e saindo com codigo **0**. Como o pipeline so olhava o
codigo de saida, a parte 1 da historia virou um mp4 de 11,8 s no lugar dos
193 s do plano, o log disse "pronto", e ninguem soube.

A licao: `returncode == 0` do ffmpeg NAO prova que o arquivo esta inteiro.
Quem escreve video confere a duracao do que escreveu.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def duracao(caminho) -> float | None:
    """Segundos do arquivo, ou None se o ffprobe nao consegue ler.

    None e a resposta certa para "arquivo truncado": nao levanta, porque
    quem chama quase sempre quer DECIDIR o que fazer (refazer, pular, avisar).
    """
    caminho = Path(caminho)
    if not caminho.is_file() or caminho.stat().st_size == 0:
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(caminho)],
            capture_output=True, text=True, creationflags=NO_WINDOW,
            timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        valor = float((r.stdout or "").strip().splitlines()[0])
    except (ValueError, IndexError):
        return None
    return valor if valor > 0 else None


def intacto(caminho) -> bool:
    return duracao(caminho) is not None


def quebrados(caminhos) -> list:
    """Os arquivos que o ffprobe nao consegue ler (na ordem recebida)."""
    return [Path(c) for c in caminhos if duracao(c) is None]
