# -*- coding: utf-8 -*-
"""O trabalho desligado da Arena: timeline do manual e mp4 do palco."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def executar(p1: str, p2: str, mapa: str, semente: int, pasta: Path) -> None:
    """Grava uma luta reproduzivel sem abrir janela no PC."""
    from neural_fights.recording import timeline_arquivo
    from random_builds.builds.palco.render import renderizar

    pasta.mkdir(parents=True, exist_ok=True)
    timeline = pasta / "timeline.gcpf"
    mp4 = pasta / "luta.mp4"
    comando = [
        sys.executable, "-m", "neural_fights.simulation.manual", "--exportar-palco",
        "--p1", p1, "--p2", p2, "--cenario", mapa, "--seed", str(semente),
        "--palco-saida", str(timeline),
    ]
    subprocess.run(comando, check=True)
    documento = timeline_arquivo.carregar(timeline)
    resultado = documento.get("resultado") if isinstance(documento, dict) else {}
    try:
        ficha = json.loads((pasta / "luta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ficha = {}
    ficha.update({"p1": p1, "p2": p2, "mapa": mapa, "semente": semente,
                  "vencedor": (resultado or {}).get("vencedor")})
    (pasta / "luta.json").write_text(json.dumps(ficha, ensure_ascii=False), encoding="utf-8")
    renderizar(documento, mp4)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p1", required=True)
    parser.add_argument("--p2", required=True)
    parser.add_argument("--mapa", required=True)
    parser.add_argument("--semente", required=True, type=int)
    parser.add_argument("--pasta", required=True)
    args = parser.parse_args(argv)
    executar(args.p1, args.p2, args.mapa, args.semente, Path(args.pasta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
