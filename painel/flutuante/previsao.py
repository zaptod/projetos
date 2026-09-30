# -*- coding: utf-8 -*-
"""O que sai no proximo horario — em SUBPROCESSO, e so lendo.

    python -m painel.flutuante.previsao --raiz E:/projetos

Imprime um JSON na ultima linha. Roda fora da janela por dois motivos: o
`ferramentas/postar.py` puxa meio projeto na importacao (nao cabe na thread
da interface nem no processo dela), e ele e de outra sessao — daqui ele e so
LIDO, nunca editado.

POR QUE NAO `postar.py --ver`: medido em 17/09/2026, o `--ver` roda a
vistoria da parte escolhida (decodifica o mp4) e grava uma linha no
`atividade.jsonl` a cada chamada. A janela chamando isso de tempos em tempos
encheria o diario de vistorias que ninguem pediu. Aqui entram so as funcoes
de FILA, que leem catalogo e ledger:

  historias  `fila_de_historias()` — a ordem de verdade, sem vistoria. A
             vistoria na hora do post pode pular a primeira; por isso a tela
             diz "provável".
  builds     `proximo_build()` — o funil inteiro (pendencia, titulo repetido,
             cota por formato, audio mudo). Mede o audio do escolhido, que e
             leitura.
  lote       `remoto.lote.resumo()` — o estoque contra o lote da semana
             (`postar.estoque_do_lote`: o funil da escolha, o piso de
             `piso_de_alerta` e o alvo ate segunda), a janela e o proximo
             lote. O mesmo resumo do /lote do bot e do relatorio de metas;
             a janela e o app so mostram o `texto` de cada canal.
  gordura    os dias inteiros do mesmo lote, so para a janela que ainda nao
             reiniciou desde 30/09/2026 (ela le `gordura`). Nao e outra conta.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path


def _carregar_postar(raiz: Path):
    caminho = raiz / "ferramentas" / "postar.py"
    spec = importlib.util.spec_from_file_location("_postar_previsao", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _video(v) -> dict | None:
    if v is None:
        return None
    return {"id": str(getattr(v, "id", "")),
            "titulo": str(getattr(v, "titulo", "") or ""),
            "parte": getattr(v, "parte", None),
            "partes": getattr(v, "partes", None)}


def prever(raiz: Path) -> dict:
    saida: dict = {"historias": None, "builds": None, "fila_historias": [],
                   "gordura": {}, "atrasados_tiktok": {}, "erros": []}
    postar = _carregar_postar(raiz)
    try:
        fila = postar.fila_de_historias()
        saida["historias"] = _video(fila[0]) if fila else None
        saida["fila_historias"] = [_video(v) for v in fila[1:4]]
    except Exception as exc:                                 # noqa: BLE001
        saida["erros"].append(f"historias: {type(exc).__name__}: {exc}")
    try:
        saida["builds"] = _video(postar.proximo_build())
    except Exception as exc:                                 # noqa: BLE001
        saida["erros"].append(f"builds: {type(exc).__name__}: {exc}")
    try:
        from remoto import lote
        saida["lote"] = lote.resumo(postar=postar)
        saida["erros"] += [f"lote: {e}" for e in saida["lote"]["erros"]]
        saida["gordura"] = {
            canal: (int(f["dias"]) if f["contou"] else -1)
            for canal, f in saida["lote"]["canais"].items()}
    except Exception as exc:                                 # noqa: BLE001
        saida["erros"].append(f"lote: {type(exc).__name__}: {exc}")
    for canal in ("historias", "builds"):
        try:
            saida["atrasados_tiktok"][canal] = len(
                postar.atrasados_no_tiktok(canal=canal))
        except Exception:                                    # noqa: BLE001
            pass
    return saida


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", required=True)
    args = parser.parse_args(argv)
    # O postar imprime o que vai decidindo; aqui so o JSON interessa. E ele
    # escreve em `sys.stdout.buffer`, entao o desvio precisa TER buffer —
    # um StringIO faz o `proximo_build` estourar com AttributeError.
    bruto = io.BytesIO()
    ruido = io.TextIOWrapper(bruto, encoding="utf-8", errors="replace",
                             write_through=True)
    try:
        with contextlib.redirect_stdout(ruido):
            dados = prever(Path(args.raiz))
    except Exception as exc:                                 # noqa: BLE001
        dados = {"falhou": f"{type(exc).__name__}: {exc}"}
    ruido.flush()
    texto = bruto.getvalue().decode("utf-8", errors="replace")
    dados["avisos"] = [l.strip() for l in texto.splitlines() if l.strip()][-8:]
    sys.stdout.write(json.dumps(dados, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
