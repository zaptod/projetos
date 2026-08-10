"""
NEURAL FIGHTS - Módulo Simulation
Gerenciador principal de simulação de combate.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .headless import HeadlessMatchResult, HeadlessMatchRunner
    from .simulacao import Simulador


def __getattr__(name):
    """Mantém os reexports sem pré-carregar simulacao antes de ``python -m``."""
    if name == "Simulador":
        from .simulacao import Simulador

        return Simulador
    if name in {"HeadlessMatchResult", "HeadlessMatchRunner", "run_headless_match"}:
        from .headless import HeadlessMatchResult, HeadlessMatchRunner, run_headless_match

        return {
            "HeadlessMatchResult": HeadlessMatchResult,
            "HeadlessMatchRunner": HeadlessMatchRunner,
            "run_headless_match": run_headless_match,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'Simulador',
    'HeadlessMatchResult',
    'HeadlessMatchRunner',
    'run_headless_match',
]
