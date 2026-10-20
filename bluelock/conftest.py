# -*- coding: utf-8 -*-
"""O GitHub de mentira dos testes de versoes e ramos: repositorios git DE
VERDADE numa pasta temporaria. So o npm, o `gh`, o Telegram e o teste do
jogo sao dublados.

    origin.git   o GitHub dele (nu)
    adrian/      o clone onde ele commita e empurra ramos
"""
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

DIST_HTML = ('<!doctype html><html><head><title>Blue Lock</title>'
             '<script type="module" crossorigin src="/assets/index-a.js"></script>'
             '<link rel="stylesheet" crossorigin href="/assets/index-b.css"></head>'
             '<body><div id="app"></div></body></html>')


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=Adrian", "-c", "user.email=a@a", "-c",
                           "core.autocrlf=false", "-c", "init.defaultBranch=main", *args],
                          cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


class GitHub:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        self.adrian = tmp / "adrian"
        git(tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(tmp, "clone", "-q", str(self.origin), str(self.adrian))
        self.commit("package.json", '{"name": "blue-lock", "version": "0.12.0"}\n', "feat: base")
        self.commit("package-lock.json", '{"lockfileVersion": 3, "v": 1}\n', "build: lock")
        self.commit("src/simulation.ts", "export class Simulation {}\n", "feat: simulacao")
        self.commit("artifacts/relatorio.json", '{"pesado": true}\n', "docs: relatorio")
        git(self.adrian, "push", "-q", "origin", "main")

    def commit(self, caminho, conteudo, mensagem):
        alvo = self.adrian / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
        git(self.adrian, "add", caminho)
        git(self.adrian, "commit", "-q", "-m", mensagem)
        return git(self.adrian, "rev-parse", "HEAD")

    def ramo(self, nome, de="main"):
        git(self.adrian, "checkout", "-q", "-B", nome, de)

    def empurrar(self, nome=None):
        nome = nome or git(self.adrian, "rev-parse", "--abbrev-ref", "HEAD")
        git(self.adrian, "push", "-q", "--force", "origin", f"{nome}:{nome}")

    def apagar_remoto(self, nome):
        git(self.adrian, "push", "-q", "origin", "--delete", nome)

    def sha(self, ref):
        return git(self.adrian, "rev-parse", ref)


class NpmDeMentira:
    """`npm ci` cria um node_modules com o vite; `npm run build` escreve um
    dist/ como o do Vite (um JS e um CSS)."""

    def __init__(self):
        self.chamadas = []
        self.build_falha = False
        self.pedacos_extras = False

    def __call__(self, *args, cwd=None, prazo=0, linha=None):
        cwd = Path(cwd)
        self.chamadas.append((args[0], cwd))
        if args[0] in ("ci", "install"):
            (cwd / "node_modules" / "vite" / "bin").mkdir(parents=True, exist_ok=True)
            (cwd / "node_modules" / "vite" / "bin" / "vite.js").write_text("// vite\n", encoding="utf-8")
            if linha:
                linha("added 44 packages")
            return 0, "added 44 packages"
        if args[:2] == ("run", "build"):
            if self.build_falha:
                return 1, "error TS2322: Type 'x' is not assignable"
            dist = cwd / "dist" / "assets"
            dist.mkdir(parents=True, exist_ok=True)
            (cwd / "dist" / "index.html").write_text(DIST_HTML, encoding="utf-8")
            (dist / "index-a.js").write_text("console.log('jogo');const s='</script>';\n", encoding="utf-8")
            (dist / "index-b.css").write_text("body{background:#101815}\n", encoding="utf-8")
            if self.pedacos_extras:
                (dist / "chunk-c.js").write_text("export default 1\n", encoding="utf-8")
            return 0, "built in 691ms"
        return 0, ""


@contextmanager
def trava_livre(_nome=None):
    yield True


@pytest.fixture
def github(tmp_path):
    return GitHub(tmp_path)


@pytest.fixture
def npm():
    return NpmDeMentira()


@pytest.fixture
def chamadas_git():
    return []


@pytest.fixture
def versoes(tmp_path, github, npm, chamadas_git):
    from bluelock import versoes as mod

    def git_gravado(*args, cwd=None, prazo=60):
        chamadas_git.append(args)
        return mod.git_real(*args, cwd=cwd, prazo=prazo)
    return mod.Versoes(tmp_path / "versoes", url=str(github.origin), git=git_gravado, npm=npm,
                       trava=trava_livre)
