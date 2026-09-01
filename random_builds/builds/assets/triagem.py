"""Sessao de triagem da biblioteca de reacoes (o motor da janela do painel).

A janela "Categorizar assistindo" do painel toca os videos de um pack um a
um; cada clique importa o video na categoria escolhida. Esta classe e a
logica da sessao — fila, importacao, desfazer — separada do Tkinter para
ser testavel de contrato.

Contratos:
  - importar passa SEMPRE por `importer.import_reactions` (ID sequencial,
    duracao via ffprobe, registro no catalog.json) — nunca um caminho
    paralelo de escrita;
  - video cujo nome ja consta como `source` no catalogo nao entra na fila,
    entao recarregar o mesmo pack nunca importa duas vezes;
  - desfazer desfaz de verdade: remove do catalogo e, se o arquivo foi
    movido, devolve a origem.

A triagem aceita mais extensoes que o catalogo (EXTENSOES_TRIAGEM): o
importador nao filtra extensao de arquivo unico e o renderer normaliza tudo
via FFmpeg, entao um .avi do pack vira um clipe valido da biblioteca.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
from collections import Counter
from pathlib import Path

from .catalog import CATEGORIES, VIDEO_EXT
from .importer import import_reactions, list_reactions, remove_reaction

EXTENSOES_TRIAGEM = VIDEO_EXT | {".avi", ".m4v", ".wmv", ".flv", ".ts",
                                 ".mpg", ".mpeg", ".ogv"}


def limpar_caminho(texto: str) -> Path:
    """Aceita caminho colado com aspas ("Copiar como caminho" do Windows)."""
    return Path(str(texto).strip().strip('"').strip("'").strip())


def _repetir_se_travado(func, tentativas: int = 15, espera: float = 0.2):
    """No Windows, mover um arquivo que o player acabou de soltar da
    PermissionError por alguns ms enquanto o handle morre."""
    for i in range(tentativas):
        try:
            return func()
        except PermissionError:
            if i == tentativas - 1:
                raise
            time.sleep(espera)


class SessaoTriagem:
    def __init__(self, assets_dir: Path):
        self.assets_dir = Path(assets_dir)
        self.raiz: Path | None = None
        self._desfazer: list[dict] = []
        self._trava = threading.Lock()
        self._estado_path = self.assets_dir.parent / "outputs" / "_triagem.json"

    # ------------------------------------------------------------- estado
    def _ler_estado(self) -> dict:
        try:
            with open(self._estado_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _gravar_estado(self, **valores) -> None:
        estado = self._ler_estado()
        estado.update(valores)
        self._estado_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._estado_path, "w", encoding="utf-8") as fh:
            json.dump(estado, fh, ensure_ascii=False, indent=2)

    def ultima_pasta(self) -> str:
        return self._ler_estado().get("ultima_pasta", "")

    def contagens(self) -> dict:
        contagem = Counter(e["category"] for e in list_reactions(self.assets_dir))
        return {cat: contagem.get(cat, 0) for cat in CATEGORIES}

    # --------------------------------------------------------------- fila
    def carregar_pasta(self, pasta) -> dict:
        raiz = limpar_caminho(pasta).expanduser()
        if not raiz.is_dir():
            raise ValueError(f"Pasta nao encontrada: {raiz}")
        arquivos = sorted(
            (f for f in raiz.iterdir() if f.suffix.lower() in EXTENSOES_TRIAGEM),
            key=lambda f: f.name.lower())
        ja_na_biblioteca = {e.get("source") for e in list_reactions(self.assets_dir)}
        fila = [f.name for f in arquivos if f.name not in ja_na_biblioteca]
        with self._trava:
            self.raiz = raiz.resolve()
            self._desfazer.clear()
        self._gravar_estado(ultima_pasta=str(raiz))
        return {"raiz": str(raiz), "fila": fila,
                "ja_importados": len(arquivos) - len(fila)}

    def resolver(self, nome: str) -> Path:
        with self._trava:
            raiz = self.raiz
        if raiz is None:
            raise ValueError("Nenhuma pasta carregada.")
        caminho = (raiz / nome).resolve()
        if raiz != caminho and raiz not in caminho.parents:
            raise ValueError("Caminho fora da pasta carregada.")
        return caminho

    # -------------------------------------------------------------- acoes
    def categorizar(self, nome: str, categoria: str, mover: bool) -> dict:
        caminho = self.resolver(nome)
        if not caminho.is_file():
            raise ValueError(f"Arquivo nao existe mais: {nome}")
        entrada = _repetir_se_travado(
            lambda: import_reactions(caminho, categoria, self.assets_dir,
                                     move=mover))[0]
        with self._trava:
            self._desfazer.append({"id": entrada["id"], "file": entrada["file"],
                                   "origem": str(caminho), "movido": mover})
        return {"entrada": entrada, "contagens": self.contagens()}

    def desfazer(self) -> dict:
        with self._trava:
            if not self._desfazer:
                raise ValueError("Nada para desfazer.")
            acao = self._desfazer.pop()
        if acao["movido"]:
            biblioteca = self.assets_dir / "reactions" / acao["file"]
            if biblioteca.is_file():
                _repetir_se_travado(
                    lambda: shutil.move(str(biblioteca), acao["origem"]))
        remove_reaction(acao["id"], self.assets_dir)
        return {"arquivo": Path(acao["origem"]).name,
                "contagens": self.contagens()}
