"""CLI idempotente para o coordenador chamar periodicamente."""
from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

from ias import correio

from . import config, ficha
from .aprovar import aprovar, descartar, refazer
from .colher import colher
from .juiz import colher as colher_juiz
from .juiz import perguntar
from .limpar import limpar
from .pedir import pedir
from .portao import passar


def mestra() -> dict:
    texto = ("Imagem-mestra aprovada para sprites pixel-art de Neural Fights: "
             "bolinha com rosto, arma, projetil e impacto; contorno #14141A, "
             "cel de 2 tons, luz superior esquerda, fundo magenta #FF00FF.")
    return correio.pedir_imagem("chatgpt", texto, proporcao="1:1")


def mestra_aprovar(caminho: str) -> Path:
    origem = Path(caminho)
    if not origem.is_file():
        raise ValueError("imagem-mestra inexistente")
    destino = config.mestra()
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, destino)
    return destino


def lote(prioridade: str, n: int) -> list[str]:
    escolhidos = []
    itens = sorted(config.itens(), key=lambda i: (i.get("ordem") is None, i.get("ordem") or 999999))
    for item in itens:
        if item.get("prioridade") != prioridade or item.get("bloqueio") or item.get("opcional"):
            continue
        existente = ficha.ler(item["id"])
        if existente and existente.get("estado") in ("pedido", "gerado", "limpo", "medido", "julgado", "a_conferir", "aprovado", "na_biblioteca"):
            continue
        pedir(item["id"])
        escolhidos.append(item["id"])
        if len(escolhidos) >= n:
            break
    return escolhidos


def avancar() -> int:
    feitos = 0
    for item in config.itens():
        dados = ficha.ler(item["id"])
        if not dados:
            continue
        estado = dados.get("estado")
        if estado == "pedido":
            feitos += bool(colher(item["id"]))
        elif estado == "gerado":
            feitos += bool(limpar(item["id"]))
        elif estado == "limpo":
            feitos += bool(passar(item["id"]))
        elif estado == "medido":
            feitos += bool(perguntar(item["id"]))
        elif estado == "julgado":
            feitos += bool(colher_juiz(item["id"]))
    return feitos


def status() -> Counter:
    return Counter(d.get("estado", "sem_ficha") for i in config.itens()
                   if (d := ficha.ler(i["id"])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Esteira de sprites")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("mestra")
    mestre = sub.add_parser("mestra-aprovar")
    mestre.add_argument("caminho")
    p_pedir = sub.add_parser("pedir")
    p_pedir.add_argument("item")
    p_lote = sub.add_parser("lote")
    p_lote.add_argument("--prioridade", required=True)
    p_lote.add_argument("--n", type=int, default=5)
    sub.add_parser("avancar")
    sub.add_parser("status")
    p_aprovar = sub.add_parser("aprovar")
    p_aprovar.add_argument("item")
    p_refazer = sub.add_parser("refazer")
    p_refazer.add_argument("item")
    p_refazer.add_argument("--motivo", required=True)
    p_descartar = sub.add_parser("descartar")
    p_descartar.add_argument("item")
    args = parser.parse_args(argv)
    if args.comando == "mestra":
        print(mestra()["id"])
    elif args.comando == "mestra-aprovar":
        print(mestra_aprovar(args.caminho))
    elif args.comando == "pedir":
        pedir(args.item)
    elif args.comando == "lote":
        print("\n".join(lote(args.prioridade, args.n)))
    elif args.comando == "avancar":
        print(avancar())
    elif args.comando == "status":
        for estado, quantidade in sorted(status().items()):
            print(f"{estado}: {quantidade}")
    elif args.comando == "aprovar":
        aprovar(args.item)
    elif args.comando == "refazer":
        refazer(args.item, args.motivo)
    else:
        descartar(args.item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
