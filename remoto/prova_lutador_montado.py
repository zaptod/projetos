"""Junta a captura da previa e o quadro exportado pelo Godot para conferencia."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, type=Path, help="PNG do canvas do Atelie")
    parser.add_argument("--godot", required=True, type=Path, help="PNG do mesmo quadro no Godot")
    parser.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args()
    app, godot = (Image.open(p).convert("RGBA") for p in (args.app, args.godot))
    altura = max(app.height, godot.height)
    lado_a_lado = Image.new("RGBA", (app.width + godot.width, altura), "#303038")
    lado_a_lado.alpha_composite(app, (0, 0)); lado_a_lado.alpha_composite(godot, (app.width, 0))
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    lado_a_lado.save(args.saida)


if __name__ == "__main__":
    main()
