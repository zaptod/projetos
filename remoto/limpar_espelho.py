# -*- coding: utf-8 -*-
"""Apaga os mp4 baixados de um canal do Espelho. So o video sai.

    python -m remoto.limpar_espelho <canal_id>

Existe porque o `mimetizar` nao tem esse comando: o painel faz o laco
dentro da propria tela (`painel/paginas/mimetizar.py:_apagar`), e o app do
celular nao pode chamar codigo de interface. O laco e o MESMO — o derivado
(medidas, transcricao, fichas, mosaico) fica, e o video volta a ser baixado
se alguem pedir para analisa-lo de novo.
"""
from __future__ import annotations

import argparse
import sys


def apagar(canal_id: str, log=print) -> dict:
    from espelho import absorver, baixar, config

    pasta = config.pasta_do_canal(canal_id)
    if not pasta.is_dir():
        raise SystemExit(f"nao achei o canal {canal_id} em {pasta}")
    antes = absorver.em_disco(canal_id)
    log(f"[espelho] {canal_id}: {antes['videos_em_disco']} video(s), "
        f"{antes['mb']:.0f} MB em disco")
    midia = pasta / "midia"
    if not midia.is_dir():
        log("[espelho] nada a apagar (sem pasta de midia)")
        return {"mb": 0.0, "videos": 0}
    liberados = quantos = 0
    for item in sorted(midia.iterdir()):
        if not item.is_dir():
            continue
        bytes_ = baixar.apagar_midia(pasta, item.name)
        if bytes_:
            quantos += 1
            liberados += bytes_
            log(f"  apagado {item.name} ({bytes_ / 1e6:.0f} MB)")
    log(f"[espelho] {liberados / 1e6:.0f} MB apagados em {quantos} video(s); "
        "o derivado ficou.")
    return {"mb": liberados / 1e6, "videos": quantos}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m remoto.limpar_espelho")
    parser.add_argument("canal")
    args = parser.parse_args(argv)
    apagar(args.canal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
