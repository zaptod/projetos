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
    janela = Janela(modo=args.modo,
                    topo=False if args.sem_topo else None,
                    persistir=not args.prova)
    if args.aba and janela.modo == "medio":
        janela.aba(args.aba)
    if args.gaveta and not janela.prefs.get("gaveta"):
        janela.prefs["gaveta"] = True
        janela.trocar(janela.modo)

    if args.prova:
        def fotografar():
            from .captura import fotografar as foto
            janela.update()
            tamanho = foto(janela, args.prova)
            print(f"prova: {args.prova} {tamanho[0]}x{tamanho[1]} "
                  f"modo={janela.modo}")
            janela.sair()

        esperar = int(args.espera * 1000)
        janela.after(esperar, fotografar)
    try:
        janela.mainloop()
    except KeyboardInterrupt:
        janela.sair()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
