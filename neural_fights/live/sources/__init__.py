"""Adaptadores de plataforma.

Cada modulo aqui traduz o formato bruto de uma plataforma para ``ViewerEvent``.
Nada fora deste subpacote conhece o payload de nenhuma plataforma.
"""

from __future__ import annotations

from neural_fights.live.sources.base import EventSource, SourceStats

__all__ = ["EventSource", "SourceStats"]
