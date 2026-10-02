# -*- coding: utf-8 -*-
"""Registro pequeno de artefatos que o app do celular pode consultar."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

PASTA = Path(os.environ.get("LOCALAPPDATA", ".")) / "neural-fights" / "biblioteca"
ARQUIVO = None                       # os testes apontam para outro lugar
RAIZ = Path(__file__).resolve().parents[1]
PLANOS = Path(r"C:\Users\adrian\.claude\plans")
PALCO = RAIZ / "docs" / "palco"
SESSOES = RAIZ / "docs" / "sessoes"
DOCS_REPOSITORIO = Path(r"E:\projetos\docs")
TIPOS = {"pagina", "documento", "relatorio", "video", "imagem"}
LIMITE_DOCUMENTO = 512 * 1024


def arquivo() -> Path:
    return Path(ARQUIVO) if ARQUIVO else PASTA / "itens.json"


def raizes_permitidas() -> tuple[Path, ...]:
    return (PLANOS, PALCO, SESSOES, DOCS_REPOSITORIO)


def _dentro(caminho: Path, raiz: Path) -> bool:
    try:
        caminho.relative_to(raiz.resolve())
        return True
    except (ValueError, OSError):
        return False


def caminho_permitido(caminho: str | Path, existe: bool = True) -> Path | None:
    """O caminho resolvido, somente se continua dentro de uma raiz permitida."""
    try:
        achado = Path(caminho).resolve(strict=existe)
    except OSError:
        return None
    if existe and not achado.is_file():
        return None
    if any(_dentro(achado, raiz) for raiz in raizes_permitidas()):
        return achado
    return None


def _url_permitida(url: str) -> bool:
    try:
        partes = urlsplit(url)
    except ValueError:
        return False
    return (partes.scheme == "https" and bool(partes.netloc)
            and not any(c.isspace() for c in url))


def _ler_registro() -> list[dict]:
    try:
        dados = json.loads(arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return dados if isinstance(dados, list) else []


def _gravar_registro(itens: list[dict]) -> None:
    destino = arquivo()
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix="itens-", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as saida:
            json.dump(itens, saida, ensure_ascii=False, indent=2)
            saida.write("\n")
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def adicionar(titulo: str, tipo: str, url: str | None = None,
              caminho: str | Path | None = None, descricao: str = "",
              tags: list[str] | None = None) -> dict:
    """Acrescenta um item manual depois de conferir o destino dele."""
    titulo = str(titulo).strip()
    if not titulo or tipo not in TIPOS:
        raise ValueError("titulo ou tipo invalido")
    if bool(url) == bool(caminho):
        raise ValueError("informe url ou caminho")
    item = {"id": uuid.uuid4().hex, "titulo": titulo, "tipo": tipo,
            "descricao": str(descricao or "").strip(),
            "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
            "em": datetime.now().isoformat(timespec="seconds")}
    if url:
        if not _url_permitida(url):
            raise ValueError("url precisa ser https")
        item["url"] = url
    else:
        permitido = caminho_permitido(caminho)
        if permitido is None:
            raise ValueError("caminho fora das raizes permitidas")
        item["caminho"] = str(permitido)
    registro = _ler_registro()
    registro.append(item)
    _gravar_registro(registro)
    return item


def remover(id_: str) -> bool:
    registro = _ler_registro()
    novo = [item for item in registro if item.get("id") != id_]
    if len(novo) == len(registro):
        return False
    _gravar_registro(novo)
    return True


def _titulo_do_arquivo(caminho: Path) -> str:
    try:
        with caminho.open("r", encoding="utf-8") as entrada:
            for numero, linha in enumerate(entrada):
                if numero >= 1000:
                    break
                if linha.startswith("# "):
                    return linha[2:].strip() or caminho.stem
    except (OSError, UnicodeDecodeError):
        pass
    return caminho.stem


def _automaticos(raiz: Path, tipo: str, tag: str) -> list[dict]:
    try:
        caminhos = raiz.glob("*.md")
    except OSError:
        return []
    itens = []
    for caminho in caminhos:
        permitido = caminho_permitido(caminho)
        if permitido is None:
            continue
        try:
            em = datetime.fromtimestamp(permitido.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            continue
        chave = hashlib.sha256(str(permitido).encode("utf-8")).hexdigest()[:20]
        itens.append({"id": "auto-" + chave, "titulo": _titulo_do_arquivo(permitido),
                      "tipo": tipo, "caminho": str(permitido), "descricao": "",
                      "tags": [tag], "em": em})
    return itens


def listar() -> list[dict]:
    """Registro manual e fontes automaticas, mais recentes primeiro."""
    manuais = []
    for item in _ler_registro():
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        if item.get("tipo") not in TIPOS or not isinstance(item.get("titulo"), str):
            continue
        if item.get("url") and not _url_permitida(item["url"]):
            continue
        if item.get("caminho") and caminho_permitido(item["caminho"]) is None:
            continue
        manuais.append(item)
    itens = manuais + _automaticos(PLANOS, "documento", "plano") \
        + _automaticos(PALCO, "relatorio", "palco") \
        + _automaticos(SESSOES, "documento", "sessão")
    return sorted(itens, key=lambda item: str(item.get("em", "")), reverse=True)


def ler_documento(id_: str) -> str | None:
    """Le um Markdown registrado, sem seguir links para fora das raizes."""
    item = next((item for item in listar() if item.get("id") == id_), None)
    if item is None or not item.get("caminho"):
        return None
    permitido = caminho_permitido(item["caminho"])
    if permitido is None or permitido.suffix.lower() != ".md":
        return None
    try:
        if permitido.stat().st_size > LIMITE_DOCUMENTO:
            return None
        return permitido.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def para_o_app() -> dict:
    itens = listar()
    publico = [{chave: valor for chave, valor in item.items() if chave != "caminho"}
               for item in itens]
    return {"itens": publico, "grupos": {
        "paginas": [item for item in publico if item.get("tipo") == "pagina"],
        "planos": [item for item in publico if "plano" in item.get("tags", [])],
        "relatorios": [item for item in publico if item.get("tipo") == "relatorio"],
        "tudo": publico,
    }}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Biblioteca de artefatos do app")
    comandos = parser.add_subparsers(dest="comando", required=True)
    add = comandos.add_parser("adicionar")
    add.add_argument("--titulo", required=True)
    destino = add.add_mutually_exclusive_group(required=True)
    destino.add_argument("--url")
    destino.add_argument("--caminho")
    add.add_argument("--tipo", required=True, choices=sorted(TIPOS))
    add.add_argument("--descricao", default="")
    add.add_argument("--tag", action="append", default=[])
    ls = comandos.add_parser("listar")
    ls.add_argument("--json", action="store_true")
    rem = comandos.add_parser("remover")
    rem.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.comando == "adicionar":
            print(adicionar(args.titulo, args.tipo, args.url, args.caminho,
                            args.descricao, args.tag)["id"])
        elif args.comando == "listar":
            itens = listar()
            if args.json:
                print(json.dumps(itens, ensure_ascii=False, indent=2))
            else:
                for item in itens:
                    print(f'{item["id"]}  {item["titulo"]}')
        elif not remover(args.id):
            parser.error("id nao encontrado")
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
