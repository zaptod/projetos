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
    parser.add_argument("--instalar", action="store_true",
                        help="poe o bot para subir junto com o Windows")
    parser.add_argument("--desinstalar", action="store_true",
                        help="tira a tarefa que sobe o bot no logon")
    parser.add_argument("--apurar", action="store_true",
                        help="le os erros novos do ledger, manda o Claude "
                             "investigar e avisa o diagnostico no Telegram")
    parser.add_argument("--avisar", metavar="TEXTO",
                        help="manda UMA mensagem para quem esta autorizado e "
                             "sai (nao liga o bot)")
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

    if args.instalar or args.desinstalar:
        from . import tarefa
        r = tarefa.instalar() if args.instalar else tarefa.desinstalar()
        print(f"[remoto] {r['tarefa']}: {r['mensagem'][:120]}")
        if args.instalar and r["ok"]:
            print(f"[remoto] lancador: {r['lancador']}")
            print("[remoto] a tarefa bate de 10 em 10 minutos e sobe o bot se "
                  "ele nao estiver no ar (se cair, ele volta sozinho).")
        return 0 if r["ok"] else 1

    atual = config.carregar()
    if args.status:
        print(f"arquivo ....: {config.caminho()}")
        print(f"token ......: {'sim' if config.token() else 'NAO'}")
        print(f"autorizados : {atual['autorizados'] or 'ninguem ainda'}")
        print(f"alertas ....: {'ligados' if atual['alertas'] else 'desligados'}")
        print(f"apurar .....: {'sim' if atual.get('apurar', True) else 'nao'}"
              "  (o Claude le os arquivos e diz o que houve)")
        print(f"consertar ..: "
              f"{'SIM' if atual.get('consertar', True) else 'nao'}"
              "  (e MEXE no codigo; so fica se a suite passar)")
        return 0

    if not config.token():
        print("[remoto] falta o token do bot." + COMO_CRIAR)
        return 1

    if args.apurar:
        from .apurador import uma_volta
        resultado = uma_volta()
        if not resultado["feito"]:
            print(f"[apurador] {resultado['motivo']}")
            return 0
        cabeca = ("🔎 *apuracao automatica* "
                  f"({resultado['erros']} erro(s) novo(s))" + chr(10) * 2)
        avisar(cabeca + resultado["diagnostico"][:3000]
               + _conserto_em_texto(resultado.get("conserto")))
        print(resultado["diagnostico"])
        return 0

    if args.avisar:
        # Aviso AVULSO, sem ligar o bot — e sem trava, porque manda e sai. E o
        # que uma tarefa agendada precisa: ela roda por conta propria, termina,
        # e quer contar o que aconteceu. Depender do bot estar no ar seria
        # fragil pelo motivo mais bobo — em 08/09/2026 ele NAO estava, e nem os
        # alertas de erro que ja existiam chegavam a lugar nenhum.
        return 0 if avisar(args.avisar) else 1

    return ligar()


def ligar() -> int:
    """Liga o bot, se ja nao houver um no ar.

    A trava e de INSTANCIA UNICA e existe por dois motivos que se somam: a
    tarefa do Agendador bate de 10 em 10 minutos (e sem trava subiria seis
    bots por hora), e dois bots no MESMO token brigam pelo `getUpdates` —
    cada um recebe metade das mensagens e nenhum dos dois funciona direito.
    """
    try:
        from builds import travas
    except ImportError:              # sem o monorepo instalado, segue sozinho
        Bot().rodar()
        return 0
    with travas.trava("remoto__bot", esperar=0.0) as minha:
        if not minha:
            print("[remoto] ja tem um bot no ar; este sai sem fazer nada.")
            return 0
        Bot().rodar()
    return 0


def _conserto_em_texto(conserto: dict | None) -> str:
    """O que o conserto automatico fez, para caber no fim do aviso.

    O que ele precisa saber sem abrir o PC: mexeu ou nao, em que arquivos, e
    onde esta o remendo para desfazer se nao gostar. Codigo mudado sozinho tem
    que ser visivel — o contrario e acordar com o repositorio diferente.
    """
    if not conserto:
        return ""
    nl = chr(10)
    if not conserto.get("mexeu"):
        if conserto.get("desfeito"):
            return (nl * 2 + "🔧 tentei consertar e *desfiz*: "
                    + str(conserto.get("motivo", ""))[:200])
        return nl * 2 + "🔧 " + str(conserto.get("motivo", ""))[:200]
    from pathlib import Path as _P
    nomes = ", ".join(_P(a).name for a in (conserto.get("arquivos") or [])[:6])
    return (nl * 2 + "🔧 *consertei e a suite passou*" + nl
            + f"arquivos: {nomes}" + nl
            + f"remendo: {_P(conserto.get('remendo', '')).name}" + nl
            + str(conserto.get("resumo", ""))[-400:])


def avisar(texto: str) -> bool:
    """Manda `texto` para todo mundo da lista branca. True se alguem recebeu."""
    from .api import Telegram

    destinos = config.carregar()["autorizados"]
    if not destinos:
        print("[remoto] ninguem autorizado ainda; nada a avisar.")
        return False
    tg = Telegram(config.token())
    entregues = 0
    for chat in destinos:
        try:
            tg.mensagem(chat, texto, markdown=True)
            entregues += 1
        except Exception as exc:                               # noqa: BLE001
            print(f"[remoto] nao consegui avisar {chat}: {exc}")
    return entregues > 0


if __name__ == "__main__":
    sys.exit(main())
