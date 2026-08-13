"""Ponto de entrada da interface de torneio do Neural Fights."""

from __future__ import annotations

import sys

from neural_fights.utils.console import safe_print as _console_print


def mostrar_ajuda() -> None:
    """Mostra o uso sem depender de uma UI ou de um console UTF-8."""

    print(
        "NEURAL FIGHTS - MODO TORNEIO\n"
        "Uso:\n"
        "  python -m neural_fights.cli.tournament          Inicia a interface de torneio\n"
        "  python -m neural_fights.cli.tournament --help   Mostra esta ajuda"
    )


def main(argv: list[str] | None = None) -> int:
    """Inicia o torneio e devolve um codigo apropriado para automacao."""

    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos:
        if len(argumentos) == 1 and argumentos[0].lower() in {"--help", "-h", "/?"}:
            mostrar_ajuda()
            return 0

        _console_print(
            f"Argumento desconhecido: {' '.join(argumentos)}",
            file=sys.stderr,
        )
        mostrar_ajuda()
        return 2

    try:
        import customtkinter as ctk
    except ImportError:
        print("=" * 60)
        print("  ERRO: CustomTkinter nao instalado!")
        print("=" * 60)
        print("\n  Execute: pip install customtkinter")
        print("\n  Depois execute este script novamente.")
        return 2

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    from neural_fights.ui.view_torneio import TournamentWindow

    print("=" * 60)
    print("  NEURAL FIGHTS - MODO TORNEIO")
    print("=" * 60)
    print("\n  Iniciando janela do torneio...")

    root = ctk.CTk()
    root.withdraw()

    window = TournamentWindow(root)
    window.protocol("WM_DELETE_WINDOW", root.destroy)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
