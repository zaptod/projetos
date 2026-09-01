"""Wrapper de compatibilidade para o runner headless do checkout."""

from neural_fights.cli.headless import (
    HeadlessBattle,
    executar_luta,
    executar_teste_rapido,
    executar_teste_stress,
    main,
)

__all__ = [
    "HeadlessBattle",
    "executar_luta",
    "executar_teste_rapido",
    "executar_teste_stress",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
