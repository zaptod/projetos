# -*- coding: utf-8 -*-
"""python -m builds.pc_am <comando> (ver `builds/pc_am/__init__.py`)."""
from __future__ import annotations

import argparse
import json
import sys

from . import maquina, sonda, trabalhos


def _imprimir(resultado: maquina.Resultado) -> None:
    onde = "PC am" if resultado.onde == "am" else f"ESTE PC ({resultado.motivo})"
    print(f"[pc_am] onde: {onde} | rc {resultado.rc} | {resultado.segundos:.0f} s"
          + (f" | {resultado.destino}" if resultado.destino else ""))
    if resultado.etapas:
        print("[pc_am] etapas (s): " + ", ".join(f"{k} {v}" for k, v in resultado.etapas.items()))
    for item in resultado.sincronia:
        print(f"[pc_am] codigo: {item.get('commit', '')[:10]}"
              + (f" + {len(item.get('diff') or [])} arquivo(s) nao commitado(s)" if item.get("diff") else "")
              + (" (reinstalou)" if item.get("instalou") else ""))
        if item.get("nao_rastreados"):
            print(f"[pc_am] AVISO: {len(item['nao_rastreados'])} arquivo(s) novo(s) sem git add NAO foram: "
                  + ", ".join(item["nao_rastreados"][:5]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m builds.pc_am",
                                     description="O PC am roda o trabalho pesado (docs/sessoes/pc-am.md).")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("saude", help="o am responde? disco, memoria, cpu, quem esta rodando")
    sub.add_parser("chaves", help="quais trabalhos estao ligados")
    son = sub.add_parser("sonda", help="o am esta disponivel/ocupado/indisponivel? (SSH barato, com cache)")
    son.add_argument("--agora", action="store_true", help="ignora o cache")
    son.add_argument("--curto", action="store_true", help="uma linha, para o retrato e o status")
    son.add_argument("--json", action="store_true")
    for nome in ("ligar", "desligar"):
        p = sub.add_parser(nome, help=f"{nome} um trabalho no config/pc_am.json")
        p.add_argument("tipo", choices=("testes", "duelo", "bluelock"))
    pre = sub.add_parser("preparar", help="poe os dois clones do am no commit daqui (e instala)")
    pre.add_argument("--sem-blue-lock", action="store_true")
    tes = sub.add_parser("testar-no-am", help="roda uma suite do pytest no am")
    tes.add_argument("pasta", help="coordenador, remoto, tests, random_builds, bluelock/test_vigia.py...")
    tes.add_argument("--forcar-am", action="store_true", help="ignora a chave (medir antes de ligar)")
    due = sub.add_parser("duelo", help="o duelo da geracao, no am")
    due.add_argument("--p1")
    due.add_argument("--p2")
    due.add_argument("--seed", type=int)
    due.add_argument("--arena")
    due.add_argument("--preview", action="store_true")
    due.add_argument("--forcar-am", action="store_true")
    blu = sub.add_parser("bluelock-gravar", help="python -m bluelock.gravar no am")
    blu.add_argument("--forcar-am", action="store_true")
    fil = sub.add_parser("fila", help="a fila sem descanso do am (o servico `am` do coordenador)")
    fil.add_argument("acao", choices=("rodar", "passo", "status", "ligar", "desligar"))
    ped = sub.add_parser("pedir", help="poe um trabalho na fila do am (prioridade 1)")
    ped.add_argument("tipo", choices=("duelo", "bluelock", "testar", "voz"))
    ped.add_argument("alvo", nargs="?", help="testar: a pasta; voz: generation_XXXXX")
    ped.add_argument("--p1")
    ped.add_argument("--p2")
    ped.add_argument("--seed", type=int)
    ped.add_argument("--arena")
    # Tudo depois de `--` vai cru ao pytest / ao bluelock.gravar, na ordem.
    argv = list(sys.argv[1:] if argv is None else argv)
    sobra = []
    if "--" in argv:
        corte = argv.index("--")
        argv, sobra = argv[:corte], argv[corte + 1:]
    args = parser.parse_args(argv)
    if sobra and args.comando not in ("testar-no-am", "bluelock-gravar", "pedir"):
        parser.error(f"argumentos depois de -- so valem para testar-no-am e bluelock-gravar: {sobra}")

    # --forcar-am e MEDIR no am: sem queda para este PC (nada pesado aqui por acidente)
    # e, com o am cheio, ESPERA a vez (ate 30 min) em vez de desistir
    medir = ({"cair_para_aqui": False, "cair_na_falha": False, "espera": 1800}
             if getattr(args, "forcar_am", False) else {})
    if args.comando == "saude":
        cfg = maquina.carregar_config()
        try:
            saude = maquina.TransporteSsh(cfg).chamar("saude")
        except maquina.AmFora as exc:
            print(f"am FORA: {exc}")
            return 2
        print(json.dumps(saude, ensure_ascii=False, indent=2))
        return 0 if saude.get("ok") else 2
    if args.comando == "sonda":
        lida = sonda.sondar(forcar=args.agora)
        if args.json:
            print(json.dumps(lida, ensure_ascii=False))
        else:
            print(sonda.texto(lida))
        return 0 if lida.get("estado") != sonda.INDISPONIVEL else 2
    if args.comando == "chaves":
        print(json.dumps(maquina.carregar_config().get("trabalhos"), indent=2))
        return 0
    if args.comando in ("ligar", "desligar"):
        maquina.mudar_chave(args.tipo, args.comando == "ligar")
        print(f"{args.tipo}: {args.comando}")
        return 0
    if args.comando == "preparar":
        cfg = maquina.carregar_config()
        t = maquina.TransporteSsh(cfg)
        repos = [dict(trabalhos.REPO_PROJETOS)]
        if not args.sem_blue_lock:
            repos.append({"nome": "BLUE-Lock-project", "raiz": trabalhos._espelho_blue_lock(),
                          "url": maquina.URL_BLUE_LOCK, "mudancas": False})
        for repo in repos:
            print(json.dumps(maquina.sincronizar(t, repo), ensure_ascii=False))
        return 0
    if args.comando == "testar-no-am":
        resultado = trabalhos.testar_no_am(args.pasta, sobra, forcar=args.forcar_am, **medir)
        print("\n".join(resultado.log.strip().splitlines()[-25:]))
        _imprimir(resultado)
        print(f"[pc_am] placar: {trabalhos.placar(resultado.log) or '?'}")
        return int(resultado.rc or 0)
    if args.comando == "duelo":
        pasta = trabalhos.duelo(p1=args.p1, p2=args.p2, seed=args.seed, cenario=args.arena,
                                preview=args.preview, forcar=args.forcar_am, **medir)
        print(f"[pc_am] duelo em {pasta}")
        return 0
    if args.comando == "bluelock-gravar":
        resultado = trabalhos.bluelock_gravar(sobra, forcar=args.forcar_am, **medir)
        _imprimir(resultado)
        return int(resultado.rc or 0)
    if args.comando == "fila":
        from . import fila
        if args.acao in ("ligar", "desligar"):
            _mudar_fila(args.acao == "ligar")
            print(f"fila do am: {args.acao}")
            return 0
        if args.acao == "status":
            estado = fila.estado_para_painel()
            print(estado.get("texto", ""))
            print(json.dumps({k: estado.get(k) for k in ("ligada", "atualizado", "fazendo", "ultimo", "pedidos",
                                                           "contas", "am", "motivos")},
                             ensure_ascii=False, indent=2))
            return 0
        laco = fila.Fila()
        if args.acao == "passo":
            print(json.dumps(laco.passo(), ensure_ascii=False, indent=2, default=str))
            return 0
        laco.rodar()
        return 0
    if args.comando == "pedir":
        from . import fila
        if args.tipo == "duelo":
            pedido = fila.pedir("duelo", p1=args.p1, p2=args.p2, seed=args.seed, arena=args.arena)
        elif args.tipo == "bluelock":
            pedido = fila.pedir("bluelock", argumentos=sobra)
        elif args.tipo == "testar":
            pedido = fila.pedir("testar", pasta=args.alvo, extras=sobra)
        else:
            pedido = fila.pedir("voz", generation=args.alvo)
        print(f"na fila do am: {pedido['id']} ({pedido['tipo']})")
        return 0
    return 1


def _mudar_fila(valor: bool) -> None:
    import os
    caminho = maquina.CONFIG
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados.setdefault("fila", {})["ligada"] = bool(valor)
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)


def _principal() -> int:
    try:
        return main()
    except maquina.NaJanela as exc:
        print(f"[pc_am] {exc}. Tente de novo fora da janela das postagens.")
        return 5
    except maquina.AmOcupado as exc:
        print(f"[pc_am] am CHEIO, esperei a vez e nao abriu (nada rodou neste PC): {exc}")
        return 4
    except maquina.AmFora as exc:
        print(f"[pc_am] am FORA (nada rodou neste PC): {exc}")
        return 2
    except maquina.FalhaNoAm as exc:
        print(f"[pc_am] FALHOU no am (nada ficou pela metade aqui): {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(_principal())
