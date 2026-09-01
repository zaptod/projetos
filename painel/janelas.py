# -*- coding: utf-8 -*-
"""As janelas do sistema, e quem abre cada uma.

DECISAO DO ADRIAN (01/09/2026): janelas separadas por jogo e por criacao de
video, e cada uma em PROCESSO PROPRIO -- nao abas de um programa so. O motivo
que ele deu peso: uma travar nao pode derrubar as outras.

Com Tkinter isso e mais do que preferencia. Uma janela e um `mainloop`; duas
telas pesadas no mesmo processo disputam a mesma thread, e a animacao da Vila
engasgaria enquanto a galeria de videos varre o disco. Em processos
separados, cada uma tem o seu relogio.

    VILA      o hub. Cara quente, o pixel art e o protagonista.
    CRIACAO   fluxo, publicar, videos, historias, contas, reacoes.
    JOGO      simulacao, torneio, database, live, audio.

O estado e compartilhado por ARQUIVO (o registro de contas, o diario, as
travas), que ja era assim antes de existir uma segunda janela. Nenhuma
janela fala com a outra por memoria, e por isso nenhuma precisa da outra
viva.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PY = sys.executable


def _paginas_da_vila() -> list:
    from .paginas import vila
    return [vila.Pagina]


def _paginas_de_criacao() -> list:
    from .paginas import (contas, extras, fluxo, historias, publicar, videos)
    return [fluxo.Pagina, publicar.Pagina, videos.Pagina, historias.Pagina,
            contas.Pagina, extras.Reacoes]


def _paginas_do_jogo() -> list:
    from .paginas import extras, jogo
    return [extras.Torneio, jogo.Simulacao, jogo.Database, jogo.Live,
            extras.Audio]


JANELAS = {
    "vila": {"titulo": "Vila — Neural Fights", "tema": "vila",
             "paginas": _paginas_da_vila, "icone": "🏘",
             "descricao": "o mundo e o que está acontecendo nele"},
    "criacao": {"titulo": "Criação de vídeos — Neural Fights",
                "tema": "oficina", "paginas": _paginas_de_criacao,
                "icone": "🎬",
                "descricao": "builds, histórias, publicação e contas"},
    "jogo": {"titulo": "Jogo — Neural Fights", "tema": "oficina",
             "paginas": _paginas_do_jogo, "icone": "🎮",
             "descricao": "simulação, torneio, banco e live"},
}


def montar(chave: str):
    """A janela pronta, no processo ATUAL."""
    from .app import Casca

    receita = JANELAS.get(chave) or JANELAS["vila"]
    return Casca.criar(receita["paginas"](), tema=receita["tema"],
                       titulo=receita["titulo"])


def abrir(chave: str) -> subprocess.Popen | None:
    """Abre a janela em OUTRO processo. Devolve o processo, ou None.

    Sem console e destacado: fechar quem abriu nao pode fechar quem foi
    aberto -- e o ponto inteiro de serem processos separados.
    """
    if chave not in JANELAS:
        return None
    executavel = Path(PY)
    sem_console = executavel.with_name(
        executavel.name.replace("python.exe", "pythonw.exe"))
    interpretador = sem_console if sem_console.is_file() else executavel
    return subprocess.Popen(
        [str(interpretador), "-X", "utf8", "-m", "painel", "--janela", chave],
        cwd=str(RAIZ),
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


__all__ = ["JANELAS", "abrir", "montar"]
