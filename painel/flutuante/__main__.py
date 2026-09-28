# -*- coding: utf-8 -*-
"""    python -m painel.flutuante                 abre no ultimo tamanho usado
    python -m painel.flutuante --mini          abre na faixa
    python -m painel.flutuante --medio | --grande | --icone
    python -m painel.flutuante --sem-topo      nao fica por cima das outras
    python -m painel.flutuante --prova f.png   abre, espera os dados, fotografa
                                               SO a janela e sai

Para abrir sem console nenhum: dois cliques em `vila_flutuante.pyw` na raiz.

Uma instancia so: a segunda chamada sai na hora (a trava e de LEITURA de
preferencia, nao uma trava do sistema — nome proprio, pasta propria).
"""
from __future__ import annotations

import argparse
import sys


def _uma_so():
    """Mutex nomeado do Windows: None se ja ha outra janela aberta."""
    if sys.platform != "win32":
        return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    alca = kernel32.CreateMutexW(None, False, "Local\\NeuralFights_VilaFlutuante")
    if kernel32.GetLastError() == 183:          # ERROR_ALREADY_EXISTS
        return None
    return alca


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="painel.flutuante")
    grupo = parser.add_mutually_exclusive_group()
    for modo in ("mini", "medio", "grande", "icone"):
        grupo.add_argument(f"--{modo}", action="store_const", const=modo,
                           dest="modo")
    parser.add_argument("--sem-topo", action="store_true")
    parser.add_argument("--prova", metavar="PNG",
                        help="fotografa a janela (PrintWindow) e sai")
    parser.add_argument("--espera", type=float, default=6.0,
                        help="com --prova: segundos esperando os dados")
    parser.add_argument("--aba", choices=("diario", "postagem", "erros",
                                          "terminal"))
    parser.add_argument("--gaveta", action="store_true",
                        help="com --grande: abre com o terminal aberto")
    parser.add_argument("--hora", type=int, metavar="HH",
                        help="finge esta hora na arte (dia/noite), para provas")
    parser.add_argument("--demo", action="store_true",
                        help="dados de DEMONSTRACAO (so para provas e GIF)")
    parser.add_argument("--gif", metavar="GIF",
                        help="com --prova: grava tambem 5 s de animacao")
    parser.add_argument("--arte", choices=("fofa", "classico"))
    parser.add_argument("--medir-cpu", type=float, metavar="SEG",
                        help="com --prova: mede a CPU deste processo por SEG")
    args = parser.parse_args(argv)

    alca = _uma_so() if not args.prova else True
    if alca is None:
        # Ja ha uma aberta: em vez de sair calado (e a janela sumida nao
        # voltar nunca mais), pede para ELA aparecer.
        from .caminhos import Caminhos
        from .sinal import pedir_para_mostrar
        if pedir_para_mostrar(Caminhos().sinal):
            print("a Vila flutuante ja estava aberta: trouxe para a frente.")
        else:
            print("a Vila flutuante ja esta aberta, mas nao respondeu.")
        return 0

    from .janela import Janela

    # A prova nao pode mudar as preferencias de quem usa a janela.
    coletor = None
    if args.demo:
        from .demo import ColetorDemo
        coletor = ColetorDemo()
    janela = Janela(modo=args.modo,
                    topo=False if args.sem_topo else None,
                    persistir=not args.prova, coletor=coletor,
                    hora=args.hora)
    if args.arte and args.arte != janela.prefs.get("arte"):
        janela.prefs["arte"] = args.arte
        janela.trocar(janela.modo)
    if args.aba and janela.modo == "medio":
        janela.aba(args.aba)
    if args.gaveta and not janela.prefs.get("gaveta"):
        janela.prefs["gaveta"] = True
        janela.trocar(janela.modo)

    if args.prova:
        import time

        from .captura import capturar
        quadros = []
        cpu = {}

        def fotografar():
            janela.update()
            imagem = capturar(janela)
            imagem.save(args.prova)
            print(f"prova: {args.prova} {imagem.width}x{imagem.height} "
                  f"modo={janela.modo}")
            if args.gif:
                quadros.append(imagem)
                janela.after(80, gravar_gif)
            elif args.medir_cpu:
                cpu["ini"] = (time.process_time(), time.monotonic())
                janela.after(int(args.medir_cpu * 1000), medir)
            else:
                janela.sair()

        def gravar_gif():
            quadros.append(capturar(janela))
            if len(quadros) < 63:                  # ~5 s a 12,5 fps
                janela.after(80, gravar_gif)
                return
            quadros[0].save(args.gif, save_all=True,
                            append_images=quadros[1:], duration=80, loop=0,
                            optimize=True)
            print(f"gif: {args.gif} {len(quadros)} quadros")
            janela.sair()

        def medir():
            cpu_ini, relogio_ini = cpu["ini"]
            gasto = time.process_time() - cpu_ini
            parede = time.monotonic() - relogio_ini
            print(f"cpu: {100 * gasto / parede:.1f}% de um nucleo "
                  f"em {parede:.0f} s (modo {janela.modo})")
            janela.sair()

        esperar = int(args.espera * 1000)
        janela.after(esperar, fotografar)
    try:
        janela.mainloop()
    except KeyboardInterrupt:
        janela.sair("ctrl+c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
