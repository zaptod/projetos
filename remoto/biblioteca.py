# -*- coding: utf-8 -*-
"""Registro pequeno de artefatos que o app do celular pode consultar."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
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
LIMITE_PAGINA = 16 * 1024 * 1024
ESTADOS = {"falta", "esteira", "pronto", "pular"}
DOC_ID_RE = re.compile(r"[A-Za-z0-9_\-.]{1,120}")
PAGINA_ID_RE = re.compile(r"[a-z0-9-]{1,64}")


def arquivo() -> Path:
    return Path(ARQUIVO) if ARQUIVO else PASTA / "itens.json"


def pasta() -> Path:
    """A pasta do registro; deriva de ARQUIVO para os testes."""
    return arquivo().parent


def pasta_paginas() -> Path:
    return pasta() / "paginas"


def pasta_estado() -> Path:
    return pasta() / "estado"


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
              tags: list[str] | None = None,
              html: str | Path | None = None) -> dict:
    """Acrescenta um item manual depois de conferir o destino dele."""
    titulo = str(titulo).strip()
    if not titulo or tipo not in TIPOS:
        raise ValueError("titulo ou tipo invalido")
    if caminho and (url or html):
        raise ValueError("informe url ou caminho")
    if not caminho and not url and not html:
        raise ValueError("informe url, caminho ou html")
    if tipo != "pagina" and html:
        raise ValueError("html so serve para pagina")
    if tipo == "pagina" and caminho:
        raise ValueError("pagina nao usa caminho")
    item = {"id": uuid.uuid4().hex, "titulo": titulo, "tipo": tipo,
            "descricao": str(descricao or "").strip(),
            "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
            "em": datetime.now().isoformat(timespec="seconds")}
    if url:
        if not _url_permitida(url):
            raise ValueError("url precisa ser https")
        item["url"] = url
    if caminho:
        permitido = caminho_permitido(caminho)
        if permitido is None:
            raise ValueError("caminho fora das raizes permitidas")
        item["caminho"] = str(permitido)
    if html:
        _guardar_html(item, html)
    registro = _ler_registro()
    registro.append(item)
    _gravar_registro(registro)
    return item


def _html_de_origem(caminho: str | Path) -> Path:
    try:
        origem = Path(caminho).resolve(strict=True)
        if not origem.is_file() or origem.stat().st_size > LIMITE_PAGINA:
            raise ValueError("html invalido ou maior que 16 MB")
    except OSError as exc:
        raise ValueError("html invalido ou maior que 16 MB") from exc
    return origem


def _guardar_html(item: dict, html: str | Path) -> None:
    origem = _html_de_origem(html)
    destino = pasta_paginas() / f'{item["id"]}.html'
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix="pagina-", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(descritor, "wb") as saida, origem.open("rb") as entrada:
            shutil.copyfileobj(entrada, saida)
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)
    # So o nome fica no registro: a pasta local nunca sai pela API.
    item["arquivo"] = destino.name


def guardar(id_: str, html: str | Path) -> dict:
    """Copia o HTML de uma pagina manual ja registrada."""
    registro = _ler_registro()
    item = next((item for item in registro if item.get("id") == id_), None)
    if item is None or item.get("tipo") != "pagina":
        raise ValueError("pagina nao encontrada")
    _guardar_html(item, html)
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
        if item.get("arquivo") and (not isinstance(item["arquivo"], str)
                                    or item["arquivo"] != f'{item["id"]}.html'):
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


def ler_pagina(id_: str) -> str | None:
    """Le a copia local de uma pagina, sempre dentro da pasta da Biblioteca."""
    if not PAGINA_ID_RE.fullmatch(id_):
        return None
    item = next((item for item in listar() if item.get("id") == id_), None)
    if item is None or item.get("tipo") != "pagina" or not item.get("arquivo"):
        return None
    caminho = pasta_paginas() / item["arquivo"]
    try:
        if not caminho.is_file() or caminho.stat().st_size > LIMITE_PAGINA:
            return None
        return caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _estado_pagina(pagina: str) -> Path:
    if not PAGINA_ID_RE.fullmatch(pagina):
        raise ValueError("pagina invalida")
    return pasta_estado() / f"{pagina}.json"


def ver_estado(pagina: str) -> dict:
    """As marcacoes de uma pagina, tolerando arquivo velho ou corrompido."""
    try:
        dados = json.loads(_estado_pagina(pagina).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {doc: valor for doc, valor in dados.items()
            if isinstance(doc, str) and DOC_ID_RE.fullmatch(doc)
            and isinstance(valor, dict) and valor.get("estado") in ESTADOS
            and isinstance(valor.get("em"), str)}


def marcar(pagina: str, doc: str, estado: str) -> dict:
    """Grava uma marcacao valida de forma atomica."""
    if not DOC_ID_RE.fullmatch(doc):
        raise ValueError("doc invalido")
    if estado not in ESTADOS:
        raise ValueError("estado invalido")
    destino = _estado_pagina(pagina)
    dados = ver_estado(pagina)
    dados[doc] = {"estado": estado,
                  "em": datetime.now().isoformat(timespec="seconds")}
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix="estado-", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as saida:
            json.dump(dados, saida, ensure_ascii=False, indent=2)
            saida.write("\n")
        os.replace(temporario, destino)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)
    return dados


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
    add.add_argument("--url")
    add.add_argument("--caminho")
    add.add_argument("--html")
    add.add_argument("--tipo", required=True, choices=sorted(TIPOS))
    add.add_argument("--descricao", default="")
    add.add_argument("--tag", action="append", default=[])
    ls = comandos.add_parser("listar")
    ls.add_argument("--json", action="store_true")
    rem = comandos.add_parser("remover")
    rem.add_argument("--id", required=True)
    guardar_cmd = comandos.add_parser("guardar")
    guardar_cmd.add_argument("--id", required=True)
    guardar_cmd.add_argument("--html", required=True)
    marcar_cmd = comandos.add_parser("marcar")
    marcar_cmd.add_argument("--pagina", required=True)
    marcar_cmd.add_argument("--doc", required=True)
    marcar_cmd.add_argument("--estado", required=True, choices=sorted(ESTADOS))
    ver = comandos.add_parser("ver-estado")
    ver.add_argument("--pagina", required=True)
    args = parser.parse_args(argv)
    try:
        if args.comando == "adicionar":
            print(adicionar(args.titulo, args.tipo, args.url, args.caminho,
                            args.descricao, args.tag, args.html)["id"])
        elif args.comando == "guardar":
            guardar(args.id, args.html)
        elif args.comando == "listar":
            itens = listar()
            if args.json:
                print(json.dumps(itens, ensure_ascii=False, indent=2))
            else:
                for item in itens:
                    print(f'{item["id"]}  {item["titulo"]}')
        elif args.comando == "marcar":
            marcar(args.pagina, args.doc, args.estado)
        elif args.comando == "ver-estado":
            print(json.dumps(ver_estado(args.pagina), ensure_ascii=False, indent=2))
        elif not remover(args.id):
            parser.error("id nao encontrado")
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
