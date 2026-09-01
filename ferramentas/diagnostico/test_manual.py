"""Wrapper de desenvolvimento para o simulador manual."""

from neural_fights.simulation.manual import SimuladorManual, main

__all__ = ["SimuladorManual", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
