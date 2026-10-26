# -*- coding: utf-8 -*-
"""Refaz a voz de UMA roleta que saiu com a voz do Windows (SAPI).

    python -m builds.pc_am.refazer_voz generation_00150 --saida <pasta>

Contexto: de 12/10 01:07 a 19/10 o edge-tts levava 403 e as falas novas de
51 roletas (generation_00126..00185) sairam na voz SAPI. Decisao do Grimorio
`builds/voz-do-windows-12-a-19-10` = "refazer-estoque": refazer so o que AINDA
NAO FOI PUBLICADO (quem escolhe as roletas e `trabalhos.roletas_da_voz`).

Roda NO AM (ou aqui): apaga a voz velha (`voz.wav`, `voz.hash`,
`voz_palavras.json`), remonta o plano (`rerender(refazer_edicao=True)`: as
falas sao medidas de novo e o plano cresce ate a voz nova caber) e
re-renderiza. **So aceita a voz do edge**: o cache de voz e esvaziado de
`.wav` antes e, se aparecer `.wav` novo depois (o SAPI e a reserva do
`voz.sintetizar`), sai com rc 7 e NADA volta — melhor ficar com o video
antigo do que trocar SAPI por SAPI.

Com `--saida`, copia para la os arquivos da raiz da geracao que mudaram (o
que o lado daqui instala), menos as pastas de segmento.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

APAGAR = ("voz.wav", "voz.hash", "voz_palavras.json")
RC_SAPI = 7


def refazer(gid: str, saida: Path | None = None) -> int:
    from ..content import voz
    from ..pipeline.controller import OUTPUTS, PipelineController
    pasta = OUTPUTS / gid
    if not (pasta / "generation.json").is_file():
        print(f"[voz] {gid}: sem generation.json")
        return 2
    cache = Path(voz.CACHE_PADRAO)
    cache.mkdir(parents=True, exist_ok=True)
    for velho in cache.glob("*.wav"):
        velho.unlink(missing_ok=True)
    for nome in APAGAR:
        (pasta / nome).unlink(missing_ok=True)
    inicio = time.time()
    PipelineController().rerender(gid, refazer_edicao=True)
    sapi = [p.name for p in cache.glob("*.wav")]
    if sapi or not (pasta / "voz.wav").is_file():
        print(f"[voz] {gid}: a voz NAO saiu do edge ({len(sapi)} fala(s) no SAPI"
              + ("" if (pasta / "voz.wav").is_file() else ", sem voz.wav") + "); nada volta")
        return RC_SAPI
    if saida is not None:
        destino = Path(saida) / gid
        destino.mkdir(parents=True, exist_ok=True)
        for arquivo in pasta.iterdir():
            if arquivo.is_file() and arquivo.stat().st_mtime >= inicio - 1:
                shutil.copy2(arquivo, destino / arquivo.name)
        print(f"[voz] {gid}: {len(list(destino.iterdir()))} arquivo(s) para voltar")
    print(f"[voz] {gid}: voz do edge refeita em {time.time() - inicio:.0f} s")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m builds.pc_am.refazer_voz")
    parser.add_argument("generation")
    parser.add_argument("--saida")
    args = parser.parse_args(argv)
    return refazer(args.generation, Path(args.saida) if args.saida else None)


if __name__ == "__main__":
    sys.exit(main())
