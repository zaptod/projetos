# -*- coding: utf-8 -*-
"""Ponte para o que ja existe e funciona em `random_builds`.

Este projeto e separado (outra pasta, outro CLI, outra saida), mas tres
pecas dali sao maduras e testadas, e refazer qualquer uma seria copiar bug
junto: o NARRADOR (edge-tts com voz do Windows de reserva, cache por hash,
limites de palavra para a legenda karaoke), a TRILHA sintetizada (sem custo,
sem biblioteca de audio) e o cliente do PICASSOIA (browser furtivo, prova de
origem em conta compartilhada, seletores mapeados).

Ate 01/09/2026 havia um problema de importar: os dois projetos tinham um
pacote chamado `src`, e o daqui ganhava sempre. A volta era registrar o de la
com OUTRO nome (`rb`), como pacote de namespace. Os pacotes foram renomeados
para `builds` e `contos`, o nome ficou unico, e a giria acabou: aqui so se
garante que a pasta vizinha esta no caminho e se importa `builds.*` direto.

Nada aqui escreve em `random_builds`: as saidas, a fila e a config deste
projeto sao locais. O que e compartilhado de proposito e o PERFIL do Chrome
do PicassoIA (mesma conta, mesmo login) e, por isso, a TRAVA de instancia
unica: os dois workers nunca podem abrir o mesmo perfil ao mesmo tempo.
"""
from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RANDOM_BUILDS = RAIZ.parent / "random_builds"
ALIAS = "builds"   # o nome de verdade do pacote, desde que ele ficou unico


class FaltaRandomBuilds(RuntimeError):
    """`random_builds` nao esta ao lado — sem narrador, trilha ou PicassoIA."""


def _registrar_pacote() -> None:
    """Garante que o pacote `builds` do projeto vizinho seja importavel."""
    if ALIAS in sys.modules:
        return
    origem = RANDOM_BUILDS / ALIAS
    if not origem.is_dir():
        raise FaltaRandomBuilds(
            f"nao achei {origem}. Este projeto usa o narrador, a trilha e o "
            "cliente do PicassoIA do random_builds, que precisa estar na "
            "pasta ao lado (e:/projetos/random_builds).")
    if str(RANDOM_BUILDS) not in sys.path:
        sys.path.append(str(RANDOM_BUILDS))


def modulo(caminho: str):
    """`modulo("content.voz")` -> `builds.content.voz` do projeto vizinho."""
    _registrar_pacote()
    return importlib.import_module(f"{ALIAS}.{caminho}")


def voz():
    """O narrador: `sintetizar`, `medir`, `montar`, `falavel`, `config`."""
    return modulo("content.voz")


def trilha():
    """Trilha e efeitos sintetizados (numpy), sem arquivo de audio."""
    return modulo("video.trilha")


def desenho():
    """Helpers de desenho (fontes, gradiente, hex_rgb) do renderer de la."""
    return modulo("visualization.draw_common")


def picasso():
    """(PicassoClient, contexto_persistente, pagina, ensure_logged_in, cfg)."""
    cliente = modulo("identity.picasso_client")
    browser = modulo("identity.browser")
    sessao = modulo("identity.session")
    config = modulo("identity.config")
    return (cliente.PicassoClient, browser.contexto_persistente, browser.pagina,
            sessao.ensure_logged_in, config)


def trava_do_browser():
    """A MESMA trava do worker de random_builds.

    Os dois projetos usam o perfil de Chrome do PicassoIA (uma conta, um
    login). Dois processos no mesmo `user_data_dir` = Chrome recusando abrir
    ou perfil corrompido. Compartilhar a trava e o que impede isso — e e por
    isso que ela vem de la, e nao uma nova aqui.
    """
    return modulo("identity.queue").instancia_unica


def controle():
    """Interruptor pausar/retomar/parar, compartilhado com a outra pipeline."""
    return modulo("identity.controle")


def disponivel() -> bool:
    return (RANDOM_BUILDS / ALIAS).is_dir()
