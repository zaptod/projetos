# -*- coding: utf-8 -*-
"""python -m remoto — liga o bot de Telegram.

    python -m remoto                  liga (ou explica o que falta)
    python -m remoto --token <token>  guarda o token e liga
    python -m remoto --status         quem esta autorizado, sem ligar nada
    python -m remoto --esquecer <id>  tira um celular da lista
"""
from __future__ import annotations

import argparse
import sys

from . import config
from .bot import Bot

COMO_CRIAR = """
Como criar o bot (uma vez, de graça):

  1. no celular, abra o Telegram e fale com  @BotFather
  2. mande  /newbot  e escolha um nome
  3. ele devolve um token parecido com  8123456:AAH...
  4. aqui no PC rode:

     python -m remoto --token 8123456:AAH...

  Depois ele imprime um código de 6 dígitos; mande  /parear <código>
  para o seu bot no Telegram e pronto.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="remoto",
                                     description="bot de Telegram do painel")
    parser.add_argument("--token", help="guarda o token do @BotFather")
    parser.add_argument("--status", action="store_true",
                        help="mostra a configuracao e sai")
    parser.add_argument("--esquecer", metavar="CHAT_ID",
                        help="remove um celular da lista branca")
    args = parser.parse_args(argv)

    if args.token:
        atual = config.carregar()
        atual["token"] = args.token.strip()
        destino = config.salvar(atual)
        print(f"[remoto] token guardado em {destino}")

    if args.esquecer:
        config.esquecer(args.esquecer)
        print(f"[remoto] {args.esquecer} saiu da lista.")
        return 0

    atual = config.carregar()
    if args.status:
        print(f"arquivo ....: {config.caminho()}")
        print(f"token ......: {'sim' if config.token() else 'NAO'}")
        print(f"autorizados : {atual['autorizados'] or 'ninguem ainda'}")
        print(f"alertas ....: {'ligados' if atual['alertas'] else 'desligados'}")
        return 0

    if not config.token():
        print("[remoto] falta o token do bot." + COMO_CRIAR)
        return 1

    Bot().rodar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
