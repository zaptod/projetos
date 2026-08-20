"""Camada de live interativa.

Este pacote e a fronteira entre plataformas de transmissao (YouTube, TikTok) e o
motor de combate. O motor nao conhece esta camada: quem dirige o loop de uma
sessao ao vivo e ``neural_fights.live.session``, que embute um ``Simulador`` e o
alimenta, exatamente como ``HeadlessMatchRunner`` ja faz no caminho headless.

A ordem das dependencias e sempre a mesma:

    sources.* -> events.ViewerEvent -> session -> Simulador

Nenhum modulo do motor importa deste pacote.
"""

from __future__ import annotations

from neural_fights.live.events import EventKind, ViewerEvent
from neural_fights.live.registry import Fighter, LiveRegistry, Viewer

__all__ = ["EventKind", "Fighter", "LiveRegistry", "Viewer", "ViewerEvent"]
