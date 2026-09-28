# -*- coding: utf-8 -*-
"""Decisoes pendentes do Adrian, com a midia para ele olhar no celular.

Pedido dele em 28/09/2026: "quero no app esses testes para que eu possa tomar
essas decisoes". Cada decisao e um item com pergunta, midia (videos e
imagens, cada um com um rotulo, como ANTES e DEPOIS) e opcoes. Ele responde
pela tela Decisoes do app; a resposta vai para `respostas.jsonl`, que o
orquestrador vigia, e para o Telegram.

    python -m remoto.decisoes adicionar --titulo "..." --pergunta "..." \\
        --opcao "Rotulo" --opcao "Rotulo|descricao" \\
        --midia "E:\\caminho\\x.mp4|ANTES" [--copiar] [--contexto "..."] \\
        [--sem-comentario] [--id meu-id]
    python -m remoto.decisoes listar [--todas | --respondidas]
    python -m remoto.decisoes mostrar <id>
    python -m remoto.decisoes onde

A MIDIA NUNCA E PEDIDA POR CAMINHO. O app pede pelo id do item e pelo indice
da midia; o caminho so existe aqui, no registro, e so arquivo que esta no
registro (e de um tipo da lista) e servido. `--copiar` traz o arquivo para a
pasta do registro: use para o que mora em pasta temporaria.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from .config import runtime_dir

PASTA = None                             # os testes apontam para outro lugar
COMENTARIO_MAX = 2000
# O que o celular sabe tocar ou mostrar, e com que Content-Type.
TIPOS = {".mp4": "video/mp4", ".webm": "video/webm", ".png": "image/png",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
# Opcao que pede comentario (o "(comente)" / "(diga quais)" do rotulo).
_PEDE_COMENTARIO = re.compile(r"\((?:comente|diga)", re.IGNORECASE)


class Recusa(Exception):
    """A operacao nao vai acontecer; a mensagem e para a tela."""


# ------------------------------------------------------------------ disco
def pasta() -> Path:
    return Path(PASTA) if PASTA else runtime_dir() / "decisoes"


def caminho_registro() -> Path:
    return pasta() / "registro.json"


def caminho_respostas() -> Path:
    return pasta() / "respostas.jsonl"


def _trava():
    """Entre threads e entre processos (o servidor e a CLI)."""
    from .api_http import trava_arquivo
    return trava_arquivo(pasta() / "registro.lock")


def _ler() -> dict:
    """O registro. Ausente = vazio; ilegivel = Recusa (nunca "vazio").

    Tratar ilegivel como vazio faria o proximo `adicionar` gravar por cima
    e apagar todas as decisoes.
    """
    try:
        texto = caminho_registro().read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"itens": []}
    except OSError as exc:
        raise Recusa(f"não consegui ler o registro ({type(exc).__name__})") from exc
    try:
        dados = json.loads(texto) if texto.strip() else {"itens": []}
    except ValueError as exc:
        raise Recusa("o registro de decisões está ilegível") from exc
    if not isinstance(dados, dict) or not isinstance(dados.get("itens"), list):
        raise Recusa("o registro de decisões está ilegível")
    return dados


def _gravar(dados: dict) -> None:
    alvo = caminho_registro()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name(f"{alvo.name}.{os.getpid()}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    os.replace(temporario, alvo)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- itens
def tipo_da_midia(caminho) -> str | None:
    return TIPOS.get(Path(str(caminho)).suffix.lower())


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore")
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.decode().lower()).strip("-")
    return slug[:40].strip("-") or "decisao"


def _opcao(bruta) -> dict:
    if isinstance(bruta, dict):
        rotulo, descricao = bruta.get("rotulo", ""), bruta.get("descricao", "")
    else:
        rotulo, _, descricao = str(bruta).partition("|")
    rotulo, descricao = rotulo.strip(), descricao.strip()
    if not rotulo:
        raise Recusa("opção sem rótulo")
    return {"rotulo": rotulo, "descricao": descricao,
            "pede_comentario": bool(_PEDE_COMENTARIO.search(rotulo))}


def _midia(bruta) -> tuple:
    if isinstance(bruta, (tuple, list)):
        caminho, rotulo = bruta[0], (bruta[1] if len(bruta) > 1 else "")
    else:
        caminho, _, rotulo = str(bruta).partition("|")
    caminho = Path(str(caminho).strip().strip('"'))
    if not caminho.is_file():
        raise Recusa(f"a mídia não existe: {caminho}")
    if tipo_da_midia(caminho) is None:
        raise Recusa(f"tipo de mídia que o celular não toca: {caminho.suffix} "
                     f"(aceito: {', '.join(sorted(TIPOS))})")
    return caminho.resolve(), str(rotulo).strip()


def adicionar(titulo: str, pergunta: str, opcoes, midias=(), *,
              contexto: str = "", comentario: bool = True, id: str | None = None,
              copiar: bool = False) -> dict:
    """Registra um item novo, pendente. Devolve o item."""
    titulo, pergunta = str(titulo or "").strip(), str(pergunta or "").strip()
    if not titulo:
        raise Recusa("a decisão precisa de um título")
    opcoes = [_opcao(o) for o in (opcoes or [])]
    if not opcoes:
        raise Recusa("a decisão precisa de pelo menos uma opção")
    arquivos = [_midia(m) for m in (midias or [])]
    with _trava():
        dados = _ler()
        existentes = {str(i.get("id")) for i in dados["itens"]}
        base = _slug(id or titulo)
        novo, n = base, 2
        while novo in existentes:
            if id:
                raise Recusa(f"já existe uma decisão com o id {id}")
            novo, n = f"{base}-{n}", n + 1
        guardadas = []
        for caminho, rotulo in arquivos:
            if copiar:
                destino = pasta() / "midias" / novo / caminho.name
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(caminho, destino)
                caminho = destino.resolve()
            guardadas.append({"arquivo": str(caminho), "rotulo": rotulo,
                              "tipo": tipo_da_midia(caminho),
                              "bytes": caminho.stat().st_size})
        item = {"id": novo, "titulo": titulo, "pergunta": pergunta,
                "contexto": str(contexto or "").strip(), "midias": guardadas,
                "opcoes": opcoes, "comentario": bool(comentario),
                "situacao": "pendente", "criado": _agora()}
        dados["itens"].append(item)
        _gravar(dados)
    return item


def _publico(item: dict) -> dict:
    """O item como o celular o ve: SEM caminho de arquivo."""
    return {"id": item.get("id"), "titulo": item.get("titulo"),
            "pergunta": item.get("pergunta", ""),
            "contexto": item.get("contexto", ""),
            "midias": [{"indice": n, "rotulo": m.get("rotulo", ""),
                        "tipo": m.get("tipo"), "nome": Path(m.get("arquivo", "")).name,
                        "bytes": m.get("bytes")}
                       for n, m in enumerate(item.get("midias") or [])],
            "opcoes": item.get("opcoes") or [],
            "comentario": bool(item.get("comentario", True)),
            "situacao": item.get("situacao", "pendente"),
            "criado": item.get("criado"),
            "resposta": item.get("resposta")}


def listar(situacao: str | None = None, *, publico: bool = True) -> list[dict]:
    itens = [i for i in _ler()["itens"]
             if situacao is None or i.get("situacao", "pendente") == situacao]
    return [_publico(i) for i in itens] if publico else itens


def midia(item_id: str, indice: int) -> tuple | None:
    """(caminho, tipo) da midia `indice` do item, ou None.

    Conferido de novo a cada pedido: o arquivo tem de estar no registro,
    existir e ser de um tipo da lista.
    """
    try:
        itens = _ler()["itens"]
    except Recusa:
        return None
    item = next((i for i in itens if i.get("id") == item_id), None)
    if item is None:
        return None
    midias = item.get("midias") or []
    if not isinstance(indice, int) or not 0 <= indice < len(midias):
        return None
    caminho = Path(str(midias[indice].get("arquivo") or ""))
    tipo = tipo_da_midia(caminho)
    if tipo is None or not caminho.is_file():
        return None
    return caminho, tipo


def responder(item_id: str, opcao, comentario: str = "",
              aparelho: str = "") -> dict:
    """Grava a resposta (append no `respostas.jsonl`) e marca o item.

    A linha do `respostas.jsonl` vai PRIMEIRO: e ela que o orquestrador le.
    Se o registro nao gravar depois, a resposta nao se perde (no maximo o
    item continua na lista de pendentes).
    """
    comentario = str(comentario or "").strip()[:COMENTARIO_MAX]
    with _trava():
        dados = _ler()
        item = next((i for i in dados["itens"] if i.get("id") == item_id), None)
        if item is None:
            raise KeyError(item_id)
        if item.get("situacao") == "respondida":
            raise Recusa("essa decisão já foi respondida")
        opcoes = item.get("opcoes") or []
        if isinstance(opcao, bool) or not isinstance(opcao, int) \
                or not 0 <= opcao < len(opcoes):
            raise Recusa("escolha uma das opções")
        escolhida = opcoes[opcao]
        if escolhida.get("pede_comentario") and not comentario:
            raise Recusa("essa opção pede um comentário")
        resposta = {"id": item_id, "titulo": item.get("titulo"),
                    "opcao": opcao, "opcao_rotulo": escolhida.get("rotulo"),
                    "comentario": comentario, "em": _agora(),
                    "aparelho": aparelho}
        caminho_respostas().parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_respostas(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(resposta, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        item["situacao"] = "respondida"
        item["resposta"] = {k: resposta[k] for k in
                            ("opcao", "opcao_rotulo", "comentario", "em")}
        _gravar(dados)
    return resposta


def texto_do_aviso(resposta: dict) -> str:
    """O que vai ao Telegram quando ele responde."""
    texto = f"🗳 Adrian decidiu: {resposta['titulo']} → {resposta['opcao_rotulo']}"
    if resposta.get("comentario"):
        texto += f"\n“{resposta['comentario'][:500]}”"
    return texto


# -------------------------------------------------------------------- cli
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m remoto.decisoes",
                                     description="decisões pendentes do app")
    sub = parser.add_subparsers(dest="comando", required=True)
    add = sub.add_parser("adicionar", help="registra uma decisão pendente")
    add.add_argument("--titulo", required=True)
    add.add_argument("--pergunta", default="")
    add.add_argument("--contexto", default="")
    add.add_argument("--opcao", action="append", default=[],
                     help='"rótulo" ou "rótulo|descrição" (repita)')
    add.add_argument("--midia", action="append", default=[],
                     help='"caminho" ou "caminho|RÓTULO" (repita)')
    add.add_argument("--copiar", action="store_true",
                     help="copia a mídia para a pasta do registro")
    add.add_argument("--sem-comentario", action="store_true")
    add.add_argument("--id", default=None)
    lista = sub.add_parser("listar", help="as pendentes (ou todas)")
    lista.add_argument("--todas", action="store_true")
    lista.add_argument("--respondidas", action="store_true")
    mostra = sub.add_parser("mostrar", help="um item inteiro, com caminhos")
    mostra.add_argument("id")
    sub.add_parser("onde", help="os caminhos do registro e das respostas")
    args = parser.parse_args(argv)

    try:
        if args.comando == "adicionar":
            item = adicionar(args.titulo, args.pergunta, args.opcao, args.midia,
                             contexto=args.contexto, copiar=args.copiar,
                             comentario=not args.sem_comentario, id=args.id)
            print(f"registrada: {item['id']} ({len(item['midias'])} mídia(s), "
                  f"{len(item['opcoes'])} opção(ões))")
            return 0
        if args.comando == "listar":
            situacao = (None if args.todas else
                        "respondida" if args.respondidas else "pendente")
            itens = listar(situacao)
            for item in itens:
                linha = f"{item['id']}  [{item['situacao']}]  {item['titulo']}"
                if item.get("resposta"):
                    linha += f"  → {item['resposta'].get('opcao_rotulo')}"
                print(linha)
            if not itens:
                print("nada aqui")
            return 0
        if args.comando == "mostrar":
            item = next((i for i in listar(None, publico=False)
                         if i.get("id") == args.id), None)
            if item is None:
                print(f"não achei {args.id}", file=sys.stderr)
                return 1
            print(json.dumps(item, ensure_ascii=False, indent=1))
            return 0
        print(f"registro:  {caminho_registro()}")
        print(f"respostas: {caminho_respostas()}")
        return 0
    except Recusa as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
