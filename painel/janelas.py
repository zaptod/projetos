# -*- coding: utf-8 -*-
"""As janelas do sistema, e quem abre cada uma.

DECISAO DO ADRIAN (01/09/2026): janelas separadas por jogo e por criacao de
video, e cada uma em PROCESSO PROPRIO -- nao abas de um programa so. O motivo
que ele deu peso: uma travar nao pode derrubar as outras.

Com Tkinter isso e mais do que preferencia. Uma janela e um `mainloop`; duas
telas pesadas no mesmo processo disputam a mesma thread, e a animacao da Vila
engasgaria enquanto a galeria de videos varre o disco. Em processos
separados, cada uma tem o seu relogio.

    VILA      o hub: placar, diario, paralelismo e de onde se abrem as outras.
    CRIACAO   fluxo, publicar, videos, historias, contas, reacoes.
    JOGO      simulacao, torneio, database, live, audio.
    OFICINA   a Oficina de sprites: folha do ChatGPT -> peca do palco
              (28/09/2026, no lugar da Oficina da Vila em pixel, aposentada).

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
    from .paginas import (auditoria, confiabilidade, contas, experimentos,
                          extras, fluxo, historias, mimetizar, publicar,
                          videos)
    # `auditoria` vem PRIMEIRO de proposito: e a unica pagina que responde
    # "pode sair?", e ela abre com a janela. As outras contam o que ja foi.
    # `confiabilidade` vem logo depois: a auditoria responde "pode sair?", e
    # ela responde a pergunta seguinte — "o que saiu, saiu mesmo?".
    # `mimetizar` fica ao lado de `historias` porque e ela que ele alimenta:
    # o preset que sai de la vira o modelo de roteiro daqui.
    # `experimentos` vem logo depois de `publicar` porque le o que publicar
    # produziu: e a pagina onde a metrica vira decisao.
    return [auditoria.Pagina, confiabilidade.Pagina, fluxo.Pagina,
            publicar.Pagina,
            experimentos.Pagina, videos.Pagina, historias.Pagina,
            mimetizar.Pagina, contas.Pagina, extras.Reacoes]


def _paginas_da_oficina() -> list:
    from .paginas import oficina
    return [oficina.Pagina]


def _paginas_do_jogo() -> list:
    from .paginas import extras, jogo
    return [extras.Torneio, jogo.Simulacao, jogo.Database, jogo.Live,
            extras.Audio]


JANELAS = {
    "vila": {"titulo": "Vila — Neural Fights", "tema": "vila",
             "paginas": _paginas_da_vila, "icone": "🏘",
             "descricao": "o mundo e o que está acontecendo nele"},
    # `pipeline: True` so aqui: e esta janela que roda os workers de
    # identidade, e o freio de mao nao faz sentido na Vila nem no Jogo.
    "criacao": {"titulo": "Criação de vídeos — Neural Fights",
                "tema": "oficina", "paginas": _paginas_de_criacao,
                "icone": "🎬", "pipeline": True,
                "descricao": "builds, histórias, publicação e contas"},
    "jogo": {"titulo": "Jogo — Neural Fights", "tema": "oficina",
             "paginas": _paginas_do_jogo, "icone": "🎮",
             "descricao": "simulação, torneio, banco e live"},
    # A cara QUENTE: decisao do Adrian para a Oficina
    # (`painel-e-vila/cara-da-oficina` = "quente"). Trocar por "oficina"
    # (a sobria, roxa) e esta linha so.
    "oficina": {"titulo": "Oficina de sprites — Neural Fights",
                "tema": "vila", "paginas": _paginas_da_oficina, "icone": "🎨",
                "descricao": "limpar, fatiar e exportar folhas para o palco"},
}


def montar(chave: str):
    """A janela pronta, no processo ATUAL."""
    from .app import Casca

    receita = JANELAS.get(chave) or JANELAS["vila"]
    return Casca.criar(receita["paginas"](), tema=receita["tema"],
                       titulo=receita["titulo"],
                       pipeline=bool(receita.get("pipeline")))


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


def abrir_flutuante() -> subprocess.Popen:
    """A Vila flutuante (`python -m painel.flutuante`), sem console.

    Nao entra em JANELAS: ela nao e uma Casca com paginas, e a janela
    pequena que fica por cima de tudo. Se ja houver uma aberta, a nova sai
    sozinha (mutex dela).
    """
    executavel = Path(PY)
    sem_console = executavel.with_name(
        executavel.name.replace("python.exe", "pythonw.exe"))
    interpretador = sem_console if sem_console.is_file() else executavel
    return subprocess.Popen(
        [str(interpretador), "-X", "utf8", "-m", "painel.flutuante"],
        cwd=str(RAIZ),
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


def abrir_guia() -> subprocess.Popen:
    """A janela do guia das IAs (`python -m painel.flutuante.guia`), sem
    console. Se ja houver uma aberta, a nova pede para ela aparecer e sai."""
    executavel = Path(PY)
    sem_console = executavel.with_name(
        executavel.name.replace("python.exe", "pythonw.exe"))
    interpretador = sem_console if sem_console.is_file() else executavel
    return subprocess.Popen(
        [str(interpretador), "-X", "utf8", "-m", "painel.flutuante.guia"],
        cwd=str(RAIZ),
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


__all__ = ["JANELAS", "abrir", "abrir_flutuante", "abrir_guia", "montar"]
