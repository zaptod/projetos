# -*- coding: utf-8 -*-
"""    python -m painel                  abre a Vila (o hub)
    python -m painel --janela criacao    abre a janela de criação de vídeos
    python -m painel --janela jogo       abre a janela do jogo
    python -m painel --janela oficina    abre a Oficina de sprites
    python -m painel --smoke             monta TODAS as páginas e sai
    python -m painel --janela oficina --arquivo F.png --prova tela.png
                                         fotografa a janela (sem roubar o
                                         foco: ela vai para o fundo) e sai

O `--smoke` monta as três janelas, uma de cada vez, e passa por cada página.
É o que o `testar.py` roda: nenhuma suíte pega erro de layout, e o painel é
por onde tudo é operado.
"""
from __future__ import annotations

import argparse
import sys

from . import janelas


def _fumar_uma(chave: str) -> int:
    """Monta UMA janela e visita cada pagina dela."""
    app = janelas.montar(chave)
    vistas = []
    for pagina in list(app.paginas):
        app.mostrar(pagina)
        app.update()
        vistas.append(pagina)
    app.encerrar()
    app.destroy()
    print(f"{chave}: " + ", ".join(vistas))
    return 0


def _fumar() -> int:
    """Fuma as tres janelas, CADA UMA NO SEU PROCESSO.

    Nao e capricho: criar e destruir tres interpretadores Tk no mesmo
    processo deixa threads da janela anterior tocando um interpretador
    morto, e o Tcl reclama com "async handler deleted by the wrong thread".
    Rodar uma por processo tambem e mais fiel -- e assim que elas rodam de
    verdade.
    """
    import subprocess

    vistas = []
    for chave in janelas.JANELAS:
        resultado = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "painel", "--smoke",
             "--janela", chave], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        saida = (resultado.stdout or "").strip()
        if resultado.returncode != 0:
            print(f"FALHOU em {chave}:")
            print(saida or (resultado.stderr or "").strip()[-1500:])
            return 1
        for linha in saida.splitlines():
            if linha.startswith(f"{chave}: "):
                vistas += [p.strip() for p in
                           linha.split(": ", 1)[1].split(",")]
    print("smoke ok: " + ", ".join(vistas))
    return 0


def _prova(args) -> int:
    """Monta a janela no tamanho pedido, espera a pagina assentar e fotografa
    SO a janela (PrintWindow). Nao rouba o foco: `prova.discreta` devolve o
    foco a quem tinha e poe a janela no fundo da pilha."""
    import time

    from . import prova

    antes = prova.janela_da_frente()
    app = janelas.montar(args.janela)
    largura, altura = (int(v) for v in args.tamanho.lower().split("x"))
    app.geometry(f"{largura}x{altura}+0+0")
    prova.discreta(app, antes)
    if args.pagina:
        app.mostrar(args.pagina)
    pagina = app.paginas.get(app._atual or "")
    if args.arquivo and hasattr(pagina, "abrir"):
        pagina.abrir(args.arquivo)
    if args.vista and hasattr(pagina, "mostrar_vista"):
        pagina.mostrar_vista(args.vista)
    fim = time.monotonic() + args.espera
    calma = 0
    while time.monotonic() < fim:
        app.update()
        ocupada = getattr(pagina, "ocupada", lambda: False)()
        calma = 0 if ocupada else calma + 1
        if calma > 25:
            break
        time.sleep(0.04)
    for _ in range(10):
        app.update()
        time.sleep(0.03)
    prova.discreta(app, antes)
    tamanho = prova.fotografar(app, args.prova)
    print(f"prova: {args.prova} ({tamanho[0]}x{tamanho[1]})")
    app.encerrar()
    app.supervisor.aguardar(10)
    app.destroy()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="painel", description="o painel de controle do Neural Fights")
    parser.add_argument("--janela", default="vila",
                        choices=list(janelas.JANELAS),
                        help="qual janela abrir (padrão: vila)")
    parser.add_argument("--smoke", action="store_true",
                        help="monta todas as páginas e sai")
    parser.add_argument("--prova", metavar="PNG",
                        help="fotografa a janela e sai")
    parser.add_argument("--tamanho", default="1366x705",
                        help="com --prova: LARGURAxALTURA (padrão: a tela "
                             "dele, 1366x768, maximizada)")
    parser.add_argument("--pagina", help="com --prova: qual página mostrar")
    parser.add_argument("--arquivo", help="com --prova: arquivo que a "
                                          "página abre (Oficina)")
    parser.add_argument("--vista", help="com --prova: a vista da Oficina "
                                        "(limpa, original, folha)")
    parser.add_argument("--espera", type=float, default=20.0,
                        help="com --prova: segundos esperando a página")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.prova:
        return _prova(args)
    if args.smoke:
        # Com `--janela` explicito, fuma so aquela: e assim que o processo
        # filho e chamado. Sem, ele e o pai e dispara os tres.
        pediu_janela = any(a.startswith("--janela") for a in
                           (sys.argv[1:] if argv is None else argv))
        return _fumar_uma(args.janela) if pediu_janela else _fumar()

    app = janelas.montar(args.janela)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
