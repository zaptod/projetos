# -*- coding: utf-8 -*-
"""    python -m painel.flutuante.guia              abre a janela do guia
    python -m painel.flutuante.guia --ia grok    ja com a IA escolhida a mao
    python -m painel.flutuante.guia --sem-topo   nao fica por cima
    python -m painel.flutuante.guia --prova f.png [--demo] [--colar TEXTO]
                                                 fotografa SO a janela e sai,
                                                 sem tocar nas preferencias

Uma instancia so (mutex `Local\\NeuralFights_GuiaIAs`): a segunda chamada
pede para a viva aparecer e sai. Abrir NAO rouba o foco do navegador: se a
janela nova virou a da frente, o foco volta para quem o tinha.
"""
from __future__ import annotations

import argparse
import sys

DEMO_HTML = ('<textarea class="w-full px-2 prose !max-w-none leading-7 '
             'bg-transparent" aria-label="Pergunte ao Grok qualquer coisa" '
             'dir="auto" style="height: 28px;"></textarea>')


def _uma_so():
    if sys.platform != "win32":
        return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    alca = kernel32.CreateMutexW(None, False, "Local\\NeuralFights_GuiaIAs")
    if kernel32.GetLastError() == 183:          # ERROR_ALREADY_EXISTS
        return None
    return alca


def _itens_demo(ia: str) -> list:
    from datetime import datetime, timedelta

    from . import colado
    agora = datetime.now().astimezone()
    demo = []
    for minutos, papel, conteudo, seletor in (
            (9, "campo_texto", DEMO_HTML,
             "textarea[aria-label='Pergunte ao Grok qualquer coisa']"),
            (7, "enviar", '<button type="submit" aria-label="Enviar" '
                          'class="css-1x2y"><svg></svg></button>',
             "button[aria-label='Enviar']"),
            (4, "erro_cota", "Você atingiu o limite. Tente novamente em 2 "
                             "horas ou faça upgrade para o SuperGrok.", None),
            (2, "mensagem", "não achei o botão de anexo", None),
            (1, "proximo", "", None)):
        demo.append(colado.item_novo(ia, papel, conteudo, passo="onde escreve",
                                     seletor=seletor,
                                     agora=agora - timedelta(minutes=minutos)))
    return demo


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="painel.flutuante.guia")
    parser.add_argument("--ia", help="IA escolhida a mao (grok, gemini…)")
    parser.add_argument("--sem-topo", action="store_true")
    parser.add_argument("--prova", metavar="PNG",
                        help="fotografa a janela (PrintWindow) e sai")
    parser.add_argument("--espera", type=float, default=1.5,
                        help="com --prova: segundos antes da foto")
    parser.add_argument("--demo", action="store_true",
                        help="itens de DEMONSTRACAO (nada vai para o disco)")
    parser.add_argument("--colar", metavar="TEXTO",
                        help="com --prova: cola este texto na caixa "
                             "('demo' = o textarea do Grok)")
    args = parser.parse_args(argv)

    alca = _uma_so() if not args.prova else True
    if alca is None:
        from ..caminhos import Caminhos
        from ..sinal import pedir_para_mostrar
        if pedir_para_mostrar(Caminhos().guia_sinal):
            print("o guia ja estava aberto: trouxe para a frente.")
        else:
            print("o guia ja esta aberto, mas nao respondeu.")
        return 0

    from ...prova import janela_da_frente
    from .janela import JanelaGuia

    frente = janela_da_frente()
    janela = JanelaGuia(ia=args.ia, topo=False if args.sem_topo else None,
                        persistir=not args.prova, demo=args.demo)
    if args.demo:
        janela._itens_demo = _itens_demo(janela.ia)          # noqa: SLF001
        janela._ler_itens(forcar=True)                        # noqa: SLF001
        janela._atualizar_cabecalho()                         # noqa: SLF001
        janela._desenhar_lista()                              # noqa: SLF001
    if args.colar:
        janela.colar(DEMO_HTML if args.colar == "demo" else args.colar)

    if args.prova:
        from ...prova import discreta
        from ..captura import capturar
        janela.attributes("-topmost", False)
        discreta(janela, frente)

        def fotografar():
            janela.update()
            imagem = capturar(janela)
            imagem.save(args.prova)
            print(f"prova: {args.prova} {imagem.width}x{imagem.height} "
                  f"ia={janela.ia}")
            janela.sair()

        janela.after(int(args.espera * 1000), fotografar)
    else:
        # Aberta por cima do navegador dele, sem tirar o foco de la.
        janela.after(50, lambda: janela.devolver_foco(frente))
    try:
        janela.mainloop()
    except KeyboardInterrupt:
        janela.sair()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
