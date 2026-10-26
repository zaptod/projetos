# -*- coding: utf-8 -*-
"""As versoes do jogo do Adrian, prontas para rodar — FORA do espelho.

POR QUE EXISTE. Pedido do Adrian (19/10/2026): "crie um executavel no meu PC
que puxa isso, onde posso escolher a versao do jogo que quero rodar e ele roda
o html". Ele (ou o Codex na nuvem dele) empurra varios ramos por dia, e ver um
ramo rodando antes do merge era: clonar, trocar de ramo, `npm ci`, `npm run
dev`. Aqui isso vira um clique.

ONDE MORA (tudo nosso e apagavel; o espelho `E:\\BLUE-Lock-project` nem e
tocado):

    E:\\BLUE-Lock-versoes\\
      repo\\                 um clone PROPRIO do GitHub (`--no-checkout`)
      v\\<sha12>\\            uma pasta por versao: `git worktree` do clone,
                             SEM `artifacts/` (403 MB de JSON versionado que
                             nem o teste nem o jogo leem: a pasta fica com
                             ~7 MB em vez de ~500)
      modulos\\<lock16>\\     o `node_modules` de cada package-lock DIFERENTE;
                             cada versao aponta o seu por junction (19/10: um
                             `npm ci` sao 21 s e ~100 MB — com o lock igual,
                             a segunda versao sai sem nenhum dos dois)
      jogos\\<sha12>.html     o jogo num arquivo so: o `dist/` do `vite build`
                             com o JS e o CSS embutidos, exatamente o que o
                             `scripts/bundle.mjs` dele faz (abre direto, sem
                             servidor)
      navegador\\             o perfil do Chrome do lancador (para nunca
                             encostar no Chrome do Adrian)
      versoes.json           o registro: quando preparou, quando usou, fixada

O QUE NUNCA FAZ: push, merge, commit, reset, rebase — nem no clone nosso, e
muito menos no GitHub dele. O clone so faz `fetch`; cada pasta so faz
`worktree add`/`sparse-checkout`/`checkout` de um commit, e a limpeza so
`worktree remove`. Ha teste que confere os subcomandos.

    python -m bluelock.versoes listar          as versoes preparadas
    python -m bluelock.versoes rodar main      prepara (se precisar) e abre
    python -m bluelock.versoes rodar fix/bachira-gesture-exit-20261019
    python -m bluelock.versoes rodar 6902842   (um commit colado)
    python -m bluelock.versoes limpar          mantem as N mais recentes + fixadas
    python -m bluelock.versoes fixar <sha|ramo> / soltar <sha|ramo>
    python -m bluelock.versoes janela          a janela (o que o atalho abre)
    python -m bluelock.versoes atalho          cria o atalho na Area de Trabalho
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import comum

RAIZ_VERSOES = Path(os.environ.get("NF_BLUELOCK_VERSOES") or r"E:\BLUE-Lock-versoes")
RAIZ = Path(__file__).resolve().parent.parent
MANTER = 8
# O que nao entra na pasta da versao. `artifacts/` sao relatorios, PNG e o
# HTML antigo, versionados: 493 MB no espelho de 19/10 (403 MB so de JSON).
# Desde 23/10/2026 ALGUNS testes (`src/*.test.ts`) importam replays de la
# (`import x from '../artifacts/y.replay.json?raw'`): sem eles o arquivo de teste
# nem carrega. Por isso a pasta sai INTEIRA, menos os arquivos que o codigo
# da propria versao cita (`arquivos_de_artifacts`): ~16 arquivos, ~9 MB no
# `0c200a0`, em vez dos 1,5 GB.
FORA_DA_PASTA = ("!/artifacts/",)
CITA_ARTIFACTS = r"artifacts/[A-Za-z0-9_./-]*[A-Za-z0-9_]"
LIMITE_DE_CITADOS = 400
GIT_PRAZO_S = 300
NPM_CI_PRAZO_S = 900
BUILD_PRAZO_S = 600
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Os subcomandos do git que este modulo usa. Qualquer outro e erro de
# programacao (o teste confere): nada de push, merge, commit, reset, rebase.
# (`merge-tree` NAO e merge: simula o merge e so escreve objetos soltos no
# clone nosso, sem ramo nem arquivo — e o que diz "conflitaria".)
GIT_PERMITIDOS = frozenset({"clone", "fetch", "rev-parse", "worktree", "sparse-checkout", "checkout",
                            "log", "show", "for-each-ref", "cat-file", "rev-list", "merge-base",
                            "merge-tree", "diff", "grep"})
GIT_PROIBIDOS = frozenset({"push", "merge", "commit", "reset", "rebase", "pull", "stash", "clean",
                           "tag", "branch", "am", "cherry-pick", "revert", "remote", "config"})
_HEX = re.compile(r"^[0-9a-fA-F]{7,40}$")


class ErroDeVersao(RuntimeError):
    """Algo que o Adrian precisa ler: sem rede, commit que nao existe, build quebrado."""


# ------------------------------------------------------------- executores
def rodar_processo(args, *, cwd=None, prazo=GIT_PRAZO_S, linha=None, env=None):
    """Roda sem janela preta. Com `linha`, entrega cada linha da saida na hora
    (a janela mostra o progresso do npm). Devolve (codigo, saida)."""
    ambiente = dict(os.environ, **(env or {}))
    try:
        proc = subprocess.Popen([str(a) for a in args], cwd=str(cwd) if cwd else None,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=ambiente, creationflags=NO_WINDOW)
    except OSError as exc:
        return 99, f"{type(exc).__name__}: {exc}"
    estourou = threading.Event()

    def matar():
        estourou.set()
        matar_arvore(proc.pid)
    relogio = threading.Timer(prazo, matar)
    relogio.daemon = True
    relogio.start()
    pedacos = []
    try:
        for bruto in proc.stdout:
            texto = bruto.decode("utf-8", "replace").rstrip("\r\n")
            pedacos.append(texto)
            if linha:
                linha(texto)
        proc.wait()
    finally:
        relogio.cancel()
    saida = "\n".join(pedacos)
    if estourou.is_set():
        return 124, saida + f"\n(estourou {prazo} s)"
    return proc.returncode, saida


def matar_arvore(pid: int) -> None:
    """So o processo que ESTE modulo abriu (o servidor do preview, o npm)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                       creationflags=NO_WINDOW)
    else:                                                       # pragma: no cover
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def git_real(*args, cwd=None, prazo=GIT_PRAZO_S):
    codigo, saida = rodar_processo(["git", *args], cwd=cwd, prazo=prazo,
                                   env={"GIT_TERMINAL_PROMPT": "0"})
    return codigo, saida


def npm_real(*args, cwd=None, prazo=NPM_CI_PRAZO_S, linha=None):
    exe = shutil.which("npm") or "npm"
    return rodar_processo([exe, *args], cwd=cwd, prazo=prazo, linha=linha,
                          env={"NO_COLOR": "1", "FORCE_COLOR": "0", "CI": "1",
                               "npm_config_update_notifier": "false"})


@contextmanager
def trava_real(nome: str):
    from builds import travas
    with travas.trava(nome) as minha:
        yield minha


def criar_junction(alvo: Path, link: Path) -> None:
    """`link` -> `alvo` sem copiar nada (nem pedir administrador)."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(alvo), str(link))
    else:                                                       # pragma: no cover
        os.symlink(alvo, link, target_is_directory=True)


def e_link(caminho: Path) -> bool:
    try:
        return caminho.is_symlink() or bool(getattr(os.path, "isjunction", lambda _p: False)(caminho))
    except OSError:
        return False


def tirar_link(caminho: Path) -> None:
    """Desfaz a junction SEM apagar o que ela aponta (o node_modules dividido)."""
    if e_link(caminho):
        try:
            os.rmdir(caminho)          # numa junction, tira so o link
        except OSError:
            os.unlink(caminho)


def apagar_pasta(caminho: Path) -> None:
    """rmtree que nunca segue junction: tira os links primeiro."""
    if not caminho.exists() and not e_link(caminho):
        return
    if e_link(caminho):
        tirar_link(caminho)
        return
    for raiz, pastas, _arquivos in os.walk(caminho, topdown=True):
        for nome in list(pastas):
            sub = Path(raiz) / nome
            if e_link(sub):
                tirar_link(sub)
                pastas.remove(nome)

    def teimoso(funcao, alvo, _info):
        try:
            os.chmod(alvo, 0o700)
            funcao(alvo)
        except OSError:
            pass
    shutil.rmtree(caminho, onerror=teimoso)


def embutir_html(dist: Path) -> str | None:
    """O `scripts/bundle.mjs` dele, em Python: o `<script src>` e o `<link
    css>` do `dist/index.html` viram `<script type=module>` e `<style>`.
    None se o build tiver mais pedacos (chunk dinamico, imagem): ai so com
    servidor."""
    try:
        fonte = (dist / "index.html").read_text(encoding="utf-8")
    except OSError:
        return None
    script = re.search(r'<script[^>]+src="([^"]+)"[^>]*></script>', fonte)
    css = re.search(r'<link[^>]+href="([^"]+\.css)"[^>]*>', fonte)
    if not script:
        return None
    usados = {script.group(1).lstrip("/")}
    if css:
        usados.add(css.group(1).lstrip("/"))
    sobras = [p for p in dist.rglob("*") if p.is_file() and p.name != "index.html"
              and p.relative_to(dist).as_posix() not in usados]
    if sobras:
        return None
    js = (dist / script.group(1).lstrip("/")).read_text(encoding="utf-8")
    js = re.sub(r"</script", r"<\\/script", js, flags=re.IGNORECASE)
    html = fonte.replace(script.group(0), '<script type="module">' + js + "</script>", 1)
    if css:
        estilo = (dist / css.group(1).lstrip("/")).read_text(encoding="utf-8")
        html = html.replace(css.group(0), "<style>" + estilo + "</style>", 1)
    return html


def porta_livre(inicio: int = 4180) -> int:
    for porta in range(inicio, inicio + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", porta)) != 0:
                return porta
    raise ErroDeVersao("nenhuma porta livre entre 4180 e 4380")


def achar_chrome() -> str | None:
    candidatos = [Path(os.environ.get(base, "")) / "Google" / "Chrome" / "Application" / "chrome.exe"
                  for base in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    candidatos += [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")]
    for caminho in candidatos:
        if caminho.is_file():
            return str(caminho)
    return shutil.which("chrome")


# ---------------------------------------------------------------- versoes
class Versoes:
    def __init__(self, raiz: Path | None = None, *, url: str = comum.URL, git=None, npm=None,
                 trava=None, relogio=datetime.now, log=None):
        self.raiz = Path(raiz or RAIZ_VERSOES)
        self.url = url
        self.git = git or git_real
        self.npm = npm or npm_real
        self.trava = trava or trava_real
        self.relogio = relogio
        self.log = log or (lambda _texto: None)
        self.clone = self.raiz / "repo"
        self.registro = self.raiz / "versoes.json"

    # --- caminhos ---------------------------------------------------
    def pasta(self, sha: str) -> Path:
        return self.raiz / "v" / sha[:12]

    def html(self, sha: str) -> Path:
        return self.raiz / "jogos" / f"{sha[:12]}.html"

    def perfil_do_navegador(self) -> Path:
        return self.raiz / "navegador"

    # --- registro ---------------------------------------------------
    def ler(self) -> dict:
        try:
            with open(self.registro, encoding="utf-8") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            dados = {}
        if not isinstance(dados.get("versoes"), dict):
            dados["versoes"] = {}
        return dados

    def gravar(self, dados: dict) -> None:
        self.raiz.mkdir(parents=True, exist_ok=True)
        temporario = self.registro.with_suffix(".tmp")
        with open(temporario, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
        os.replace(temporario, self.registro)

    def _anotar(self, sha: str, **campos) -> dict:
        with self.trava("bluelock_versoes_registro"):
            dados = self.ler()
            ficha = dados["versoes"].setdefault(sha, {"sha": sha, "criada_em": self._agora()})
            ficha.update(campos)
            self.gravar(dados)
            return dict(ficha)

    def _agora(self) -> str:
        return self.relogio().isoformat(timespec="seconds")

    # --- git --------------------------------------------------------
    def _git(self, *args, cwd=None, prazo=GIT_PRAZO_S) -> tuple[int, str]:
        sub = args[0]
        if sub not in GIT_PERMITIDOS or sub in GIT_PROIBIDOS:
            raise AssertionError(f"git {sub} não é permitido aqui")
        return self.git(*args, cwd=cwd, prazo=prazo)

    def _git_ok(self, *args, cwd=None) -> str | None:
        codigo, saida = self._git(*args, cwd=cwd or self.clone)
        return saida.strip() if codigo == 0 else None

    def tem_clone(self) -> bool:
        return (self.clone / ".git").exists()

    def garantir_clone(self) -> None:
        if self.tem_clone():
            return
        self.raiz.mkdir(parents=True, exist_ok=True)
        if self.clone.exists():
            apagar_pasta(self.clone)
        self.log(f"clonando {self.url} (uma vez só, ~110 MB)…")
        codigo, saida = self._git("clone", "--no-checkout", self.url, str(self.clone), cwd=self.raiz,
                                  prazo=1800)
        if codigo != 0:
            raise ErroDeVersao(f"não consegui clonar {self.url}: {saida.strip()[-300:]}")

    def buscar(self) -> tuple[bool, str]:
        """`git fetch --prune origin` no clone NOSSO: todos os ramos."""
        with self.trava("bluelock_versoes") as minha:
            if not minha:
                return False, "outro processo está mexendo no clone; tente de novo em instantes"
            self.garantir_clone()
            codigo, saida = self._git("fetch", "--prune", "--quiet", "origin", cwd=self.clone)
        return codigo == 0, saida.strip()[-300:]

    def ramos(self) -> list[dict]:
        """Os ramos do GitHub (como o clone viu no ultimo fetch), main primeiro."""
        if not self.tem_clone():
            return []
        bruto = self._git_ok("for-each-ref", "--sort=-committerdate",
                             "--format=%(refname:short)%09%(objectname)%09%(committerdate:iso-strict)"
                             "%09%(authorname)%09%(subject)", "refs/remotes/origin") or ""
        lista = []
        for linha in bruto.splitlines():
            partes = linha.split("\t", 4)
            if len(partes) != 5 or partes[0] in ("origin", "origin/HEAD"):
                continue
            nome = partes[0].removeprefix("origin/")
            lista.append({"ramo": nome, "sha": partes[1], "data": partes[2], "autor": partes[3],
                          "assunto": partes[4]})
        lista.sort(key=lambda r: r["ramo"] != "main")
        return lista

    def resolver(self, ref: str) -> str:
        """main | nome do ramo | origin/<ramo> | sha (7 a 40) -> sha completo."""
        ref = (ref or "").strip()
        if not ref:
            raise ErroDeVersao("diga qual versão: main, um ramo ou um commit")
        self.garantir_clone()
        candidatos = [ref] if ref.startswith("origin/") else [f"origin/{ref}", ref]
        for candidato in candidatos:
            sha = self._git_ok("rev-parse", "--verify", "--quiet", f"{candidato}^{{commit}}")
            if sha:
                return sha
        if _HEX.match(ref):
            # Commit que o clone ainda nao tem (de outro ramo apagado, ou
            # recente): o GitHub entrega por sha completo.
            self._git("fetch", "--quiet", "origin", ref, cwd=self.clone)
            sha = self._git_ok("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
            if sha:
                return sha
        raise ErroDeVersao(f"não achei `{ref}` no GitHub dele (nem ramo, nem commit). "
                           "Clique em 'Atualizar lista' e tente de novo; um commit curto só "
                           "funciona se já estiver num ramo.")

    def descrever(self, sha: str) -> dict:
        bruto = self._git_ok("log", "-1", "--format=%h%x09%cI%x09%an%x09%s", sha) or ""
        partes = bruto.split("\t", 3)
        if len(partes) != 4:
            return {"curto": sha[:7]}
        return {"curto": partes[0], "data": partes[1], "autor": partes[2], "assunto": partes[3]}

    # --- preparar ---------------------------------------------------
    def preparar(self, ref: str, *, construir: bool = True, progresso=None, rotulo: str | None = None,
                 buscar: bool = True) -> dict:
        """Deixa a versao pronta: pasta, dependencias e (com `construir`) o
        jogo num HTML. Devolve a ficha do registro."""
        passo = progresso or (lambda _n, _total, _texto: None)
        total = 5 if construir else 3
        passo(1, total, "procurando a versão no GitHub…")
        with self.trava("bluelock_versoes") as minha:
            if not minha:
                raise ErroDeVersao("o vigia está mexendo no clone agora; tente de novo em um minuto")
            self.garantir_clone()
            if buscar:
                self._git("fetch", "--prune", "--quiet", "origin", cwd=self.clone)
            sha = self.resolver(ref)
            passo(2, total, f"separando a pasta de {sha[:7]}…")
            self._garantir_pasta(sha)
        info = self.descrever(sha)
        ficha = self._anotar(sha, ref=rotulo or ref, usada_em=self._agora(), **info)
        with self.trava(f"bluelock_versao_{sha[:12]}"):
            passo(3, total, "dependências (npm ci, ou o node_modules de outra versão igual)…")
            lock = self._garantir_modulos(sha)
            ficha = self._anotar(sha, lock=lock)
            if not construir:
                return ficha
            html = self.html(sha)
            if html.is_file() and ficha.get("modo") == "html":
                passo(5, total, "já estava pronta")
                return ficha
            passo(4, total, "construindo o jogo (npm run build)…")
            aviso = self._construir(sha)
            passo(5, total, "juntando num HTML só…")
            embutido = embutir_html(self.pasta(sha) / "dist")
            if embutido is not None:
                html.parent.mkdir(parents=True, exist_ok=True)
                html.write_text(embutido, encoding="utf-8")
                return self._anotar(sha, modo="html", html=str(html), construida_em=self._agora(),
                                    aviso_do_build=aviso)
            return self._anotar(sha, modo="servidor", html=None, construida_em=self._agora(),
                                aviso_do_build=aviso)

    def arquivos_de_artifacts(self, sha: str) -> list[str]:
        """Os arquivos de `artifacts/` que o codigo desta versao cita (testes e jogo).

        Sai como padroes do sparse-checkout (`/artifacts/x.json`). Citar so a
        pasta (`artifacts/`) nao conta: seria voltar aos 1,5 GB."""
        achados: set[str] = set()
        for pasta in ("src", "scripts"):
            codigo, saida = self._git("grep", "-h", "-o", "-E", CITA_ARTIFACTS, sha, "--", pasta,
                                      cwd=self.clone)
            if codigo not in (0, 1):
                continue
            for linha in saida.splitlines():
                linha = linha.strip()
                if linha and "." in linha.rsplit("/", 1)[-1]:
                    achados.add("/" + linha)
        return sorted(achados)[:LIMITE_DE_CITADOS]

    def _garantir_pasta(self, sha: str) -> None:
        pasta = self.pasta(sha)
        if (pasta / ".git").exists():
            atual = self._git_ok("rev-parse", "HEAD", cwd=pasta)
            if atual == sha:
                # Pasta antiga (de antes dos artifacts citados): completa so o que falta.
                self._git("sparse-checkout", "set", "--no-cone", "/*", *FORA_DA_PASTA,
                          *self.arquivos_de_artifacts(sha), cwd=pasta)
                return
            self._remover_pasta(pasta)
        elif pasta.exists():
            apagar_pasta(pasta)
        self._git("worktree", "prune", cwd=self.clone)
        pasta.parent.mkdir(parents=True, exist_ok=True)
        codigo, saida = self._git("worktree", "add", "--no-checkout", "--detach", str(pasta), sha,
                                  cwd=self.clone)
        if codigo != 0:
            raise ErroDeVersao(f"não consegui separar a pasta de {sha[:7]}: {saida.strip()[-300:]}")
        self._git("sparse-checkout", "set", "--no-cone", "/*", *FORA_DA_PASTA,
                  *self.arquivos_de_artifacts(sha), cwd=pasta)
        codigo, saida = self._git("checkout", "--quiet", "--detach", sha, cwd=pasta)
        if codigo != 0:
            raise ErroDeVersao(f"não consegui tirar os arquivos de {sha[:7]}: {saida.strip()[-300:]}")

    def _garantir_modulos(self, sha: str) -> str:
        pasta = self.pasta(sha)
        lock = pasta / "package-lock.json"
        base = lock if lock.is_file() else pasta / "package.json"
        chave = hashlib.sha256(base.read_bytes()).hexdigest()[:16]
        modulos = self.raiz / "modulos" / chave
        pronto = modulos / ".pronto"
        with self.trava(f"bluelock_modulos_{chave}"):
            if not pronto.is_file():
                if modulos.exists():
                    apagar_pasta(modulos)
                modulos.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pasta / "package.json", modulos / "package.json")
                if lock.is_file():
                    shutil.copy2(lock, modulos / "package-lock.json")
                    comando = ["ci"]
                else:
                    comando = ["install", "--no-package-lock"]
                codigo, saida = self.npm(*comando, "--no-audit", "--no-fund", "--cache",
                                         str(self.raiz / "npm-cache"), cwd=modulos,
                                         prazo=NPM_CI_PRAZO_S, linha=self.log)
                if codigo != 0:
                    raise ErroDeVersao(f"o `npm {comando[0]}` falhou: {saida.strip()[-400:]}")
                pronto.write_text(self._agora(), encoding="utf-8")
        link = pasta / "node_modules"
        if e_link(link) and Path(os.path.realpath(link)) != Path(os.path.realpath(modulos / "node_modules")):
            tirar_link(link)
        if not link.exists():
            criar_junction(modulos / "node_modules", link)
        return chave

    def _construir(self, sha: str) -> str | None:
        """`npm run build` (tsc + vite). Se so o tsc reclamar, o jogo ainda
        sai pelo `vite build` direto — e o aviso fica na ficha."""
        pasta = self.pasta(sha)
        codigo, saida = self.npm("run", "build", cwd=pasta, prazo=BUILD_PRAZO_S, linha=self.log)
        if codigo == 0 and (pasta / "dist" / "index.html").is_file():
            return None
        vite = pasta / "node_modules" / "vite" / "bin" / "vite.js"
        if vite.is_file():
            node = shutil.which("node") or "node"
            codigo2, saida2 = rodar_processo([node, str(vite), "build"], cwd=pasta, prazo=BUILD_PRAZO_S,
                                             linha=self.log)
            if codigo2 == 0 and (pasta / "dist" / "index.html").is_file():
                return "o `npm run build` falhou (provável erro de tipo no tsc); construí com `vite build` direto"
            saida = saida2
        raise ErroDeVersao(f"o build de {sha[:7]} falhou: {saida.strip()[-400:]}")

    # --- abrir --------------------------------------------------------
    def abrir(self, sha: str, *, abrir_url=None) -> dict:
        """Abre o jogo. Modo html: o arquivo direto. Modo servidor: sobe o
        `vite preview` numa porta livre e devolve o processo (quem chamou
        encerra ao fechar)."""
        ficha = self.ler()["versoes"].get(sha) or {}
        self._anotar(sha, usada_em=self._agora())
        abrir_url = abrir_url or self.abrir_no_navegador
        if ficha.get("modo") == "html" and ficha.get("html") and Path(ficha["html"]).is_file():
            url = Path(ficha["html"]).resolve().as_uri()
            return {"url": url, "navegador": abrir_url(url), "servidor": None}
        pasta = self.pasta(sha)
        vite = pasta / "node_modules" / "vite" / "bin" / "vite.js"
        if not vite.is_file():
            raise ErroDeVersao(f"a versão {sha[:7]} não está pronta (sem node_modules); rode de novo")
        porta = porta_livre()
        node = shutil.which("node") or "node"
        servidor = subprocess.Popen([node, str(vite), "preview", "--host", "127.0.0.1", "--port", str(porta),
                                     "--strictPort"], cwd=str(pasta), stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    creationflags=NO_WINDOW)
        url = f"http://127.0.0.1:{porta}/"
        prazo = time.monotonic() + 60
        import urllib.request
        while time.monotonic() < prazo:
            if servidor.poll() is not None:
                raise ErroDeVersao(f"o `vite preview` saiu com {servidor.returncode}")
            try:
                with urllib.request.urlopen(url, timeout=2):
                    break
            except OSError:
                time.sleep(0.4)
        return {"url": url, "navegador": abrir_url(url), "servidor": servidor}

    def abrir_no_navegador(self, url: str, extras=()) -> dict:
        """Uma janela VISIVEL do Chrome com perfil proprio (o Adrian quer ver o
        jogo; e o perfil separado garante que so fechamos o que abrimos).
        `extras`: flags a mais (a prova usa a porta de depuracao)."""
        chrome = achar_chrome()
        if not chrome:
            os.startfile(url)                                  # noqa: S606 — o navegador padrao
            return {"como": "navegador padrão"}
        perfil = self.perfil_do_navegador()
        perfil.mkdir(parents=True, exist_ok=True)
        self.esquecer_posicao()
        proc = subprocess.Popen([chrome, f"--user-data-dir={perfil}", "--no-first-run",
                                 "--no-default-browser-check", "--hide-crash-restore-bubble",
                                 "--start-maximized", *extras, "--new-window", url],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        return {"como": "chrome", "pid": proc.pid, "perfil": str(perfil)}

    def esquecer_posicao(self) -> bool:
        """Apaga a posicao/tamanho que o Chrome guardou no NOSSO perfil.
        19/10: o perfil guardou 1920x1106 numa tela de 1020 uteis e a janela
        abria maior que a tela; com isto + `--start-maximized` ela abre
        maximizada (do tamanho da tela, qualquer que seja)."""
        preferencias = self.perfil_do_navegador() / "Default" / "Preferences"
        try:
            dados = json.loads(preferencias.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        navegador = dados.get("browser") if isinstance(dados, dict) else None
        if not isinstance(navegador, dict) or "window_placement" not in navegador:
            return False
        navegador.pop("window_placement", None)
        try:
            temporario = preferencias.with_suffix(".tmp")
            temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            os.replace(temporario, preferencias)
        except OSError:
            return False
        return True

    def pids_do_nosso_navegador(self) -> list[int]:
        """Os chrome.exe cuja linha de comando tem o NOSSO perfil — nunca os do Adrian."""
        if os.name != "nt":                                     # pragma: no cover
            return []
        perfil = str(self.perfil_do_navegador()).replace("'", "''")
        script = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                  f"Where-Object {{ $_.CommandLine -like '*--user-data-dir={perfil}*' }} | "
                  "ForEach-Object { $_.ProcessId }")
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                              capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
        return [int(x) for x in proc.stdout.split() if x.strip().isdigit()]

    def fechar_nosso_navegador(self, espera_s: float = 6.0) -> list[int]:
        """Pede para fechar (sem /F: o Chrome sai limpo e nao pergunta
        "Restaurar paginas?" na proxima — visto em 19/10); so o que sobrar
        depois de `espera_s` e forcado. Sempre so os PIDs do NOSSO perfil."""
        pids = self.pids_do_nosso_navegador()
        for pid in pids:
            subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True, creationflags=NO_WINDOW)
        prazo = time.monotonic() + espera_s
        while pids and time.monotonic() < prazo and set(self.pids_do_nosso_navegador()) & set(pids):
            time.sleep(0.5)
        for pid in set(self.pids_do_nosso_navegador()) & set(pids):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                           creationflags=NO_WINDOW)
        return pids

    # --- fixar e limpar ---------------------------------------------
    def fixar(self, sha: str, valor: bool = True) -> dict:
        return self._anotar(sha, fixada=bool(valor))

    def limpar(self, manter: int = MANTER, protegidos=()) -> dict:
        """Mantem as `manter` usadas por ultimo + as fixadas + `protegidos`.
        Versao em uso (trava dela ocupada) nunca sai."""
        apagadas, puladas = [], []
        with self.trava("bluelock_versoes") as minha:
            if not minha:
                return {"apagadas": [], "puladas": [], "motivo": "clone ocupado"}
            dados = self.ler()
            fichas = sorted(dados["versoes"].values(), key=lambda f: f.get("usada_em") or "", reverse=True)
            ficam = {f["sha"] for f in fichas if f.get("fixada")} | {p for p in protegidos}
            ficam |= {f["sha"] for f in [f for f in fichas if not f.get("fixada")][:max(0, manter)]}
            for ficha in fichas:
                sha = ficha["sha"]
                if sha in ficam:
                    continue
                with self.trava(f"bluelock_versao_{sha[:12]}") as livre:
                    if not livre:
                        puladas.append(sha)
                        continue
                    self._remover_pasta(self.pasta(sha))
                    try:
                        self.html(sha).unlink()
                    except OSError:
                        pass
                with self.trava("bluelock_versoes_registro"):
                    atual = self.ler()
                    atual["versoes"].pop(sha, None)
                    self.gravar(atual)
                apagadas.append(sha)
            # Pasta em v/ que o registro nao conhece (sobra de queda).
            conhecidas = {sha[:12] for sha in self.ler()["versoes"]}
            for pasta in (self.raiz / "v").glob("*") if (self.raiz / "v").is_dir() else []:
                if pasta.name not in conhecidas:
                    self._remover_pasta(pasta)
                    apagadas.append(pasta.name)
            modulos = self._limpar_modulos()
            if self.tem_clone():
                self._git("worktree", "prune", cwd=self.clone)
        return {"apagadas": apagadas, "puladas": puladas, "modulos_apagados": modulos}

    def _limpar_modulos(self) -> list[str]:
        usados = {f.get("lock") for f in self.ler()["versoes"].values()}
        apagados = []
        base = self.raiz / "modulos"
        if not base.is_dir():
            return apagados
        for pasta in base.iterdir():
            if pasta.name in usados:
                continue
            with self.trava(f"bluelock_modulos_{pasta.name}") as livre:
                if livre:
                    apagar_pasta(pasta)
                    apagados.append(pasta.name)
        return apagados

    def _remover_pasta(self, pasta: Path) -> None:
        tirar_link(pasta / "node_modules")
        if self.tem_clone() and (pasta / ".git").exists():
            self._git("worktree", "remove", "--force", str(pasta), cwd=self.clone)
        apagar_pasta(pasta)


# ---------------------------------------------------------------- atalho
NOME_DO_ATALHO = "Blue Lock — versões"


def caminho_do_icone() -> Path:
    return comum.pasta() / "blue-lock.ico"


def desenhar_icone(destino: Path | None = None) -> Path:
    """Um cadeado azul com uma bola: desenhado aqui, sem arquivo binario no git."""
    from PIL import Image, ImageDraw
    destino = Path(destino or caminho_do_icone())
    lado = 256
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    azul, escuro, branco = (37, 99, 235, 255), (15, 23, 42, 255), (241, 245, 249, 255)
    d.rounded_rectangle((20, 20, 236, 236), radius=48, fill=escuro)
    d.arc((76, 34, 180, 150), start=180, end=360, fill=azul, width=22)
    d.line((87, 92, 87, 120), fill=azul, width=22)
    d.line((169, 92, 169, 120), fill=azul, width=22)
    d.rounded_rectangle((52, 110, 204, 220), radius=22, fill=azul)
    d.ellipse((98, 136, 158, 196), fill=branco)
    d.regular_polygon((128, 166, 13), 5, fill=escuro)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return destino


def script_do_atalho(lnk: Path, alvo: str, argumentos: str, pasta: str, icone: str) -> str:
    def q(texto):
        return "'" + str(texto).replace("'", "''") + "'"
    return ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut(" + q(lnk) + "); "
            f"$s.TargetPath = {q(alvo)}; $s.Arguments = {q(argumentos)}; "
            f"$s.WorkingDirectory = {q(pasta)}; $s.IconLocation = {q(icone)}; "
            "$s.Description = 'Escolhe a versão do jogo Blue Lock (main, ramos ou commit) e abre'; "
            "$s.Save()")


def area_de_trabalho() -> Path:
    proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           "[Environment]::GetFolderPath('Desktop')"], capture_output=True, text=True,
                          timeout=60, creationflags=NO_WINDOW)
    caminho = proc.stdout.strip()
    return Path(caminho) if caminho else Path.home() / "Desktop"


def criar_atalho(destino: Path | None = None, rodar=subprocess.run) -> dict:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    alvo = str(pythonw if pythonw.is_file() else sys.executable)
    icone = desenhar_icone()
    pasta = Path(destino) if destino else area_de_trabalho()
    lnk = pasta / f"{NOME_DO_ATALHO}.lnk"
    script = script_do_atalho(lnk, alvo, "-m bluelock.versoes janela", str(RAIZ), str(icone))
    proc = rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                 capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    return {"ok": proc.returncode == 0 and lnk.is_file(), "atalho": str(lnk), "alvo": alvo,
            "icone": str(icone), "erro": (proc.stderr or "").strip()[-300:]}


# ------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bluelock.versoes", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("listar", help="as versões preparadas e os ramos do GitHub")
    rodar = sub.add_parser("rodar", help="prepara (se precisar) e abre o jogo")
    rodar.add_argument("ref", help="main, um ramo ou um commit")
    preparar = sub.add_parser("preparar", help="só prepara, sem abrir")
    preparar.add_argument("ref")
    preparar.add_argument("--sem-build", action="store_true", help="só a pasta e as dependências")
    limpar = sub.add_parser("limpar", help="apaga as versões velhas")
    limpar.add_argument("--manter", type=int, default=MANTER)
    for nome in ("fixar", "soltar"):
        sub.add_parser(nome).add_argument("ref")
    sub.add_parser("janela", help="a janela de escolher a versão")
    atalho = sub.add_parser("atalho", help="cria o atalho na Área de Trabalho")
    atalho.add_argument("--destino", help="outra pasta (para testar)")
    sub.add_parser("fechar-navegador", help="fecha só o Chrome que o lançador abriu")
    args = parser.parse_args(argv)

    if args.acao == "janela":
        from .janela import abrir_janela
        return abrir_janela()
    if args.acao == "atalho":
        ficha = criar_atalho(args.destino)
        print(json.dumps(ficha, ensure_ascii=False, indent=2))
        return 0 if ficha["ok"] else 1
    v = Versoes(log=lambda texto: print(texto, flush=True))
    try:
        if args.acao == "listar":
            v.buscar()
            print(json.dumps({"ramos": v.ramos(), "versoes": v.ler()["versoes"]}, ensure_ascii=False, indent=2))
        elif args.acao in ("rodar", "preparar"):
            def mostrar(n, total, texto):
                print(f"[{n}/{total}] {texto}", flush=True)
            ficha = v.preparar(args.ref, construir=not getattr(args, "sem_build", False), progresso=mostrar)
            if args.acao == "rodar":
                aberto = v.abrir(ficha["sha"])
                print(json.dumps({"url": aberto["url"], "navegador": aberto["navegador"]}, ensure_ascii=False))
                if aberto.get("servidor"):
                    print("servidor do preview no ar; Ctrl+C encerra", flush=True)
                    try:
                        aberto["servidor"].wait()
                    except KeyboardInterrupt:
                        matar_arvore(aberto["servidor"].pid)
            else:
                print(json.dumps(ficha, ensure_ascii=False, indent=2))
        elif args.acao == "limpar":
            print(json.dumps(v.limpar(args.manter), ensure_ascii=False, indent=2))
        elif args.acao in ("fixar", "soltar"):
            sha = v.resolver(args.ref)
            print(json.dumps(v.fixar(sha, args.acao == "fixar"), ensure_ascii=False, indent=2))
        elif args.acao == "fechar-navegador":
            print(json.dumps({"fechados": v.fechar_nosso_navegador()}))
    except ErroDeVersao as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
