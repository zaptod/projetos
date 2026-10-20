# -*- coding: utf-8 -*-
"""O vigia dos RAMOS do Blue Lock: vale a pena dar merge?

POR QUE EXISTE. Pedido do Adrian (19/10/2026): "quero que voce vigie todas as
ramificacoes para ver se vale a pena dar merge". O repositorio dele recebe
varios ramos por dia, EMPILHADOS (o `fix/bachira-gesture-exit-20261019`
continha os cinco anteriores), e nao ha PR: ele precisava abrir um por um para
saber qual era a ponta, se o CI passou e se os testes passam.

O QUE ELE FAZ, uma olhada por vez (a mesma tarefa de 30 min do vigia da main
chama, logo depois dele):

  1. `git fetch --prune origin` no clone NOSSO (`E:\\BLUE-Lock-versoes\\repo`),
     nunca no espelho.
  2. Para cada ramo: commits a frente/atras da main, se e fast-forward, se
     algum OUTRO ramo novo o contem (empilhado) e qual e a ponta da pilha;
     se nao e ff, se o merge conflitaria (`git merge-tree`, que nao mexe em
     ramo nenhum).
  3. O CI dele: `gh run list` (so leitura) — e `gh run view` para dizer QUAL
     job caiu.
  4. `npm test -- --testTimeout=60000` na pasta da versao (bluelock.versoes),
     so nos ramos em que o resultado decide o veredito (a ponta ff com CI nao
     vermelho). PESADO: so com `comum.pode_pesado()`, no maximo
     `TESTES_POR_OLHADA` por vez; senao fica para a proxima.
  5. O diff resumido contra a main (arquivos e AREAS: IA, personagens,
     graficos, testes, docs) e as mensagens dos commits.
  6. O VEREDITO em portugues simples (`veredito()`).
  7. UM aviso no Telegram por olhada, com uma linha por ramo/cabeca ainda nao
     avisado, e o comando que ELE roda. Grava tudo em
     `%LOCALAPPDATA%\\neural-fights\\bluelock\\ramos.json` (o lancador e o
     painel leem).

O QUE ELE NUNCA FAZ: push, merge, PR, comentario — nada que escreva no
GitHub dele (o `gh` esta logado na conta dele, entao a guarda e nossa: so
`run list` e `run view` passam, e ha teste). O merge e ELE quem faz.

    python -m bluelock.ramos olhar          uma olhada (o que a tarefa roda)
    python -m bluelock.ramos olhar --seco   analisa e grava, sem avisar
    python -m bluelock.ramos status         a tabela do ultimo ramos.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from . import comum
from .versoes import NO_WINDOW, ErroDeVersao, Versoes

REPO_GH = "zaptod/BLUE-Lock-project"
TESTES_POR_OLHADA = 2
PRAZO_H = 3                     # depois disso, avisa com o que tiver
GH_PRAZO_S = 60
# O `gh` desta maquina esta logado na conta DELE (zaptod), com escrita. So
# estes subcomandos passam — e nenhum argumento que mude metodo HTTP.
GH_PERMITIDOS = frozenset({("run", "list"), ("run", "view")})
GH_PROIBIDOS = ("--method", "-X", "api", "--json-body", "-f", "-F", "rerun", "cancel", "delete")

ICONES = {"vale": "✅", "espere": "⏸", "nao_vale": "❌", "olho": "👀", "na_main": "✔️"}


# ------------------------------------------------------------- executores
def gh_real(*args, prazo=GH_PRAZO_S):
    if tuple(args[:2]) not in GH_PERMITIDOS or any(a in GH_PROIBIDOS for a in args):
        raise AssertionError(f"gh {' '.join(args[:3])} não é permitido: só leitura")
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, timeout=prazo, creationflags=NO_WINDOW,
                              env=dict(os.environ, GH_PROMPT_DISABLED="1", NO_COLOR="1"))
    except (OSError, subprocess.SubprocessError) as exc:
        return 99, f"{type(exc).__name__}: {exc}"
    saida = proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)
    return proc.returncode, (saida or b"").decode("utf-8", "replace")


def avisar_real(texto: str) -> bool:
    from remoto.__main__ import avisar
    return bool(avisar(texto))


@contextmanager
def trava_real(nome: str):
    from builds import travas
    with travas.trava(nome) as minha:
        yield minha


# ------------------------------------------------------------- areas
_GRAFICOS = ("art", "animation", "field", "pitch", "keeper-art", "presentation", "visual", "render",
             "camera", "scene", "frame-clock", "locomotion", "gesture", "style")
_PERSONAGENS = ("characters", "isagi", "bachira", "kunigami", "chigiri", "nagi", "reo", "barou", "rin",
                "character-profiles", "roster")
_IA = ("cognition", "policy", "team-play", "cooperation", "simulation", "pass", "reception", "possession",
       "dribble", "shot", "support", "tactic", "decision", "percept", "memory", "assist", "one-two",
       "third-man", "running", "corridor", "learning", "finishing", "control")


def area(caminho: str) -> str:
    """De que parte do jogo e o arquivo — para o resumo dizer 'mexe na IA'."""
    baixo = caminho.lower()
    nome = baixo.rsplit("/", 1)[-1]
    if ".test." in nome or ".spec." in nome:
        return "testes"
    if baixo.startswith("docs/") or nome.endswith(".md"):
        return "docs"
    if baixo.startswith(".github/"):
        return "CI"
    if nome in ("package.json", "package-lock.json", ".npmrc", "tsconfig.json"):
        return "dependências"
    if baixo.startswith("artifacts/"):
        return "artefatos"
    if baixo.startswith("scripts/"):
        return "auditorias"
    if baixo.startswith("src/"):
        if any(p in nome for p in _GRAFICOS):
            return "gráficos"
        if any(nome.startswith(p) or f"-{p}" in nome for p in _PERSONAGENS):
            return "personagens"
        if any(p in nome for p in _IA):
            return "IA"
        if nome in ("main.ts", "style.css") or nome.endswith(".css"):
            return "interface"
        return "jogo (outros)"
    return "outros"


# ------------------------------------------------------------- veredito
def veredito(r: dict) -> dict:
    """O veredito de UM ramo, a partir do que a olhada mediu. Puro: o teste
    passa o dicionario na mao. Devolve {codigo, tipo, texto, final}.

    `final` = pode ir para o aviso (nao depende de algo que ainda vai mudar
    sozinho, como o CI rodando ou o teste adiado)."""
    if r.get("a_frente", 0) == 0:
        return {"codigo": "na_main", "tipo": "na_main", "final": True,
                "texto": "já está na main — nada a fazer"}
    ci = r.get("ci") or {}
    if r.get("pontas"):
        ponta = r["pontas"][0]
        vermelho = " (este, sozinho, tem o CI vermelho)" if ci.get("conclusao") == "failure" else ""
        return {"codigo": "contido", "tipo": "espere", "final": True,
                "texto": f"espere: o ramo `{ponta}` já contém este e vai além{vermelho}"}
    if ci.get("conclusao") == "failure":
        jobs = ", ".join(ci.get("jobs_falhos") or []) or "ver o link"
        return {"codigo": "ci_vermelho", "tipo": "nao_vale", "final": True,
                "texto": f"não vale: o CI dele quebra ({jobs})"}
    if not r.get("ff"):
        if r.get("conflitos"):
            arquivos = ", ".join(f"`{c}`" for c in r["conflitos"][:4])
            return {"codigo": "conflito", "tipo": "olho", "final": True,
                    "texto": f"precisa de olho: não é fast-forward e conflita com a main em {arquivos}"}
        return {"codigo": "nao_ff", "tipo": "olho", "final": True,
                "texto": (f"precisa de olho: não é fast-forward (a main andou {r.get('atras', '?')} "
                          "commit(s) depois que o ramo saiu); não conflita, mas o merge vira um commit "
                          "novo — melhor abrir PR")}
    if ci.get("indisponivel"):
        return {"codigo": "ci_ilegivel", "tipo": "espere", "final": False,
                "texto": "espere: não consegui ler o CI dele agora (sem rede?); olho de novo na próxima"}
    if ci.get("estado") in ("queued", "in_progress", "waiting", "pending", "requested"):
        return {"codigo": "ci_rodando", "tipo": "espere", "final": False,
                "texto": "espere: o CI dele ainda está rodando"}
    if ci.get("conclusao") not in (None, "success"):
        return {"codigo": "ci_estranho", "tipo": "olho", "final": True,
                "texto": f"precisa de olho: o CI terminou como `{ci.get('conclusao')}`"}
    testes = r.get("testes") or {}
    if not testes.get("rodou"):
        return {"codigo": "sem_teste", "tipo": "espere", "final": False,
                "texto": f"espere: ainda não testei aqui ({testes.get('motivo') or 'na fila'})"}
    if testes.get("npm_ci") is False:
        return {"codigo": "npm_ci", "tipo": "nao_vale", "final": True,
                "texto": "não vale: o `npm ci` deste ramo falha"}
    if not testes.get("ok"):
        contas = testes.get("testes") or {}
        nomes = "; ".join(testes.get("falhas") or [])[:160]
        return {"codigo": "teste_vermelho", "tipo": "nao_vale", "final": True,
                "texto": f"não vale: {contas.get('falhou', '?')} teste(s) quebram aqui ({nomes or 'ver o log'})"}
    contas = testes.get("testes") or {}
    sem_ci = "" if ci.get("conclusao") == "success" else " (o CI dele não rodou neste commit)"
    vermelhos = r.get("contido_por_vermelho") or []
    alem = (f"; o `{vermelhos[0]}`, que vai além deste, tem o CI vermelho" if vermelhos else "")
    return {"codigo": "vale", "tipo": "vale", "final": True,
            "texto": (f"vale o merge: fast-forward, CI verde, {contas.get('passou', '?')}/"
                      f"{contas.get('total', '?')} testes verdes aqui, é a ponta boa{sem_ci}{alem}")}


def comando_de_merge(ramo: str) -> str:
    """O que ELE roda, no clone dele, depois de um `git fetch`."""
    return f"git push origin origin/{ramo}:main"


def link_de_pr(ramo: str) -> str:
    return f"https://github.com/{REPO_GH}/compare/main...{ramo}?expand=1"


# ---------------------------------------------------------------- vigia
class VigiaDeRamos:
    def __init__(self, versoes: Versoes | None = None, *, gh=None, avisar=None, pode_pesado=None,
                 testar=None, relogio=datetime.now, estado=None, trava=None, log=None,
                 testes_por_olhada: int = TESTES_POR_OLHADA):
        self.versoes = versoes or Versoes()
        self.gh = gh or gh_real
        self.avisar = avisar or avisar_real
        self.pode_pesado = pode_pesado or comum.pode_pesado
        self.testar = testar or self._testar_real
        self.relogio = relogio
        self.arquivo = Path(estado) if estado else comum.pasta() / "ramos.json"
        self.trava = trava or trava_real
        self.log = log or (lambda texto: print(texto, flush=True))
        self.testes_por_olhada = testes_por_olhada

    # --- estado -----------------------------------------------------
    def ler(self) -> dict:
        try:
            with open(self.arquivo, encoding="utf-8") as fh:
                dados = json.load(fh)
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar(self, dados: dict) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".tmp")
        with open(temporario, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
        os.replace(temporario, self.arquivo)

    def _git(self, *args) -> tuple[int, str]:
        return self.versoes._git(*args, cwd=self.versoes.clone)

    def _git_ok(self, *args) -> str | None:
        codigo, saida = self._git(*args)
        return saida.strip() if codigo == 0 else None

    # --- a olhada ---------------------------------------------------
    def olhar(self, *, testar: bool = True, avisar: bool = True, gravar: bool = True,
              buscar: bool = True) -> dict:
        with self.trava("bluelock_ramos") as minha:
            if not minha:
                return {"acao": "ocupado", "motivo": "outra olhada nos ramos está rodando"}
            return self._olhar(testar=testar, avisar=avisar, gravar=gravar, buscar=buscar)

    def _olhar(self, *, testar, avisar, gravar, buscar) -> dict:
        agora = self.relogio()
        dados = self.ler()
        memoria = dados.get("memoria") or {}
        memoria.setdefault("avisados", {})
        memoria.setdefault("testes", {})
        memoria.setdefault("visto_em", {})
        if buscar:
            ok, erro = self.versoes.buscar()
            if not ok:
                return {"acao": "fetch_falhou", "erro": erro}
        ramos = self.versoes.ramos()
        main = next((r for r in ramos if r["ramo"] == "main"), None)
        if not main:
            return {"acao": "sem_main", "motivo": "o clone não tem origin/main"}
        outros = [dict(r) for r in ramos if r["ramo"] != "main"]
        for r in outros:
            self._relacao(main["sha"], r)
            chave = f"{r['ramo']}@{r['sha']}"
            memoria["visto_em"].setdefault(chave, agora.isoformat(timespec="seconds"))
        memoria.setdefault("ci", {})
        self._ci(outros, memoria["ci"])
        self._pilhas(outros)
        for r in outros:
            if r["a_frente"]:
                self._resumo(main["sha"], r)
            if r["a_frente"] and not r["ff"]:
                r["conflitos"] = self._conflitos(main["sha"], r["sha"])
        # Testes: so onde decidem o veredito.
        pode, motivo = self.pode_pesado(agora) if testar else (False, "olhada sem testes")
        feitos = 0
        for r in sorted(outros, key=lambda x: x.get("data") or "", reverse=True):
            precisa, porque = self._precisa_testar(r)
            if not precisa:
                r["testes"] = memoria["testes"].get(r["sha"]) or {"rodou": False, "motivo": porque}
                continue
            if r["sha"] in memoria["testes"]:
                r["testes"] = memoria["testes"][r["sha"]]
                continue
            if not pode or feitos >= self.testes_por_olhada:
                r["testes"] = {"rodou": False, "motivo": motivo if not pode else "na fila: outros ramos antes"}
                continue
            self.log(f"[bluelock-ramos] testando {r['ramo']} ({r['sha'][:7]})…")
            ficha = self.testar(r["sha"], r["ramo"])
            feitos += 1
            r["testes"] = ficha
            so_tempo = ficha.get("rodou") and not ficha.get("ok") and ficha.get("por_tempo") and \
                (ficha.get("testes") or {}).get("falhou", 0) <= ficha["por_tempo"]
            if not so_tempo:
                memoria["testes"][r["sha"]] = ficha
        for r in outros:
            r["veredito"] = veredito(r)
            r["comando"] = comando_de_merge(r["ramo"]) if r["veredito"]["codigo"] == "vale" else None
            r["pr"] = link_de_pr(r["ramo"]) if r["a_frente"] else None
        # O aviso: uma linha por ramo/cabeca nova e com veredito final (ou
        # parada alem do prazo).
        novos = []
        for r in outros:
            if memoria["avisados"].get(r["ramo"]) == r["sha"]:
                continue
            if r["veredito"]["codigo"] == "na_main":
                if avisar:
                    memoria["avisados"][r["ramo"]] = r["sha"]
                continue
            desde = memoria["visto_em"].get(f"{r['ramo']}@{r['sha']}")
            velho = bool(desde) and agora - datetime.fromisoformat(desde) >= timedelta(hours=PRAZO_H)
            if r["veredito"]["final"] or velho:
                novos.append(r)
        entregue = None
        if novos and avisar:
            entregue = bool(self.avisar(self.texto_do_aviso(novos)))
            if entregue:
                for r in novos:
                    memoria["avisados"][r["ramo"]] = r["sha"]
        vivos = {r["ramo"] for r in outros}
        memoria["avisados"] = {k: v for k, v in memoria["avisados"].items() if k in vivos}
        shas_vivos = {r["sha"] for r in outros}
        memoria["testes"] = {k: v for k, v in memoria["testes"].items() if k in shas_vivos}
        memoria["visto_em"] = {k: v for k, v in memoria["visto_em"].items() if k.rsplit("@", 1)[-1] in shas_vivos}
        resultado = {
            "olhado_em": agora.isoformat(timespec="seconds"),
            "main": {"sha": main["sha"], "data": main["data"], "assunto": main["assunto"]},
            "ramos": outros,
            "pesado": motivo if not pode else "",
            "testados_agora": feitos,
            "memoria": memoria,
        }
        if gravar:
            self._gravar(resultado)
        if feitos:
            try:
                self.versoes.limpar()
            except (OSError, ErroDeVersao) as exc:
                self.log(f"[bluelock-ramos] limpeza falhou: {exc}")
        acao = ("avisou" if entregue else "olhou" if not novos else
                "seco" if not avisar else "aviso_falhou")
        return {"acao": acao,
                "ramos": len(outros), "novos": [r["ramo"] for r in novos], "testados": feitos,
                "tabela": resultado}

    # --- medidas ----------------------------------------------------
    def _relacao(self, main: str, r: dict) -> None:
        contas = self._git_ok("rev-list", "--left-right", "--count", f"{main}...{r['sha']}") or "0\t0"
        atras, a_frente = (int(x) for x in contas.split())
        r["atras"], r["a_frente"] = atras, a_frente
        r["ff"] = atras == 0

    def _pilhas(self, ramos: list[dict]) -> None:
        abertos = [r for r in ramos if r["a_frente"]]
        for r in ramos:
            r["contido_por"], r["contem"], r["pontas"], r["mesma_cabeca"] = [], [], [], []
            r["contido_por_vermelho"] = []
        for a in abertos:
            for b in abertos:
                if a is b:
                    continue
                if a["sha"] == b["sha"]:
                    a["mesma_cabeca"].append(b["ramo"])
                    continue
                codigo, _ = self._git("merge-base", "--is-ancestor", a["sha"], b["sha"])
                if codigo == 0:
                    a["contido_por"].append(b["ramo"])
                    b["contem"].append(a["ramo"])
        # A PONTA que conta e a mais alta da pilha que NAO tem o CI vermelho.
        # 19/10, 21:55, caso real: `fix/isagi-reception-20261020` (CI
        # vermelho) continha `fix/bachira-air-contact-20261019` (CI verde); o
        # "espere pela ponta" mandaria esperar um ramo que quebra. Se todos os
        # que contem este estao vermelhos, ele e julgado sozinho.
        por_nome = {r["ramo"]: r for r in abertos}
        bons = {r["ramo"] for r in abertos if (r.get("ci") or {}).get("conclusao") != "failure"}
        for r in abertos:
            candidatos = [n for n in r["contido_por"] if n in bons]
            pontas = [n for n in candidatos if not any(m in bons for m in por_nome[n]["contido_por"])]
            r["pontas"] = sorted(pontas, key=lambda n: por_nome[n].get("data") or "", reverse=True)
            r["contido_por_vermelho"] = [n for n in r["contido_por"] if n not in bons]

    def _ci(self, ramos: list[dict], guardado: dict | None = None) -> None:
        """Um `gh run list` so para todos (100 ultimas rodadas); por ramo so
        quem nao apareceu.

        SEM REDE NAO E "SEM CI". 19/10, 22:48, real: o `gh` levou "TLS
        handshake timeout" e todos os ramos viraram "sem CI" — e o off-ball
        continuou "vale o merge" sem ninguem ter lido o CI dele. Agora: o
        ultimo CI TERMINADO de cada commit fica guardado (`guardado`, por sha)
        e e usado quando o `gh` falha; sem nem isso, o CI fica `indisponivel`
        e o veredito espera."""
        guardado = guardado if guardado is not None else {}
        self._ci_do_gh(ramos)
        for r in ramos:
            ci = r.get("ci")
            if not ci:
                continue
            if ci.get("indisponivel") and r["sha"] in guardado:
                r["ci"] = dict(guardado[r["sha"]], do_cache=True)
            elif ci.get("estado") == "completed" and ci.get("conclusao"):
                guardado[r["sha"]] = {k: v for k, v in ci.items() if k != "do_cache"}
        vivos = {r["sha"] for r in ramos}
        for sha in [s for s in guardado if s not in vivos]:
            guardado.pop(sha, None)

    def _ci_do_gh(self, ramos: list[dict]) -> None:
        por_sha: dict[str, dict] = {}
        codigo, saida = self.gh("run", "list", "--repo", REPO_GH, "--limit", "100", "--json",
                                "headBranch,headSha,status,conclusion,url,databaseId,createdAt,name")
        if codigo == 0:
            for run in _json_lista(saida):
                atual = por_sha.get(run.get("headSha"))
                if not atual or (run.get("createdAt") or "") > (atual.get("createdAt") or ""):
                    por_sha[run.get("headSha")] = run
        for r in ramos:
            if not r["a_frente"]:
                r["ci"] = None
                continue
            run = por_sha.get(r["sha"])
            if run is None and codigo == 0:
                c2, s2 = self.gh("run", "list", "--repo", REPO_GH, "--branch", r["ramo"], "--limit", "5",
                                 "--json", "headBranch,headSha,status,conclusion,url,databaseId,createdAt,name")
                if c2 == 0:
                    run = next((x for x in _json_lista(s2) if x.get("headSha") == r["sha"]), None)
            if run is None:
                if codigo != 0:
                    r["ci"] = {"estado": None, "conclusao": None, "url": None, "indisponivel": True,
                               "motivo": f"não consegui ler o CI ({saida.strip()[:120]})"}
                else:
                    r["ci"] = {"estado": None, "conclusao": None, "url": None,
                               "motivo": "sem rodada do CI para este commit"}
                continue
            r["ci"] = {"estado": run.get("status"), "conclusao": run.get("conclusion") or None,
                       "url": run.get("url"), "id": run.get("databaseId"), "em": run.get("createdAt")}
            if r["ci"]["conclusao"] == "failure" and run.get("databaseId"):
                c3, s3 = self.gh("run", "view", str(run["databaseId"]), "--repo", REPO_GH, "--json", "jobs")
                if c3 == 0:
                    try:
                        jobs = json.loads(s3).get("jobs") or []
                    except ValueError:
                        jobs = []
                    falhos = []
                    for job in jobs:
                        if job.get("conclusion") == "failure":
                            passo = next((s.get("name") for s in job.get("steps") or []
                                          if s.get("conclusion") == "failure"), None)
                            falhos.append(f"{job.get('name')}: {passo}" if passo else str(job.get("name")))
                    r["ci"]["jobs_falhos"] = falhos

    def _resumo(self, main: str, r: dict) -> None:
        bruto = self._git_ok("diff", "--name-status", "--no-renames", f"{main}...{r['sha']}") or ""
        arquivos, areas = [], {}
        for linha in bruto.splitlines():
            partes = linha.split("\t", 1)
            if len(partes) != 2:
                continue
            arquivos.append({"estado": partes[0][:1], "caminho": partes[1]})
            nome = area(partes[1])
            areas[nome] = areas.get(nome, 0) + 1
        r["arquivos"] = len(arquivos)
        r["lista_de_arquivos"] = [a["caminho"] for a in arquivos[:60]]
        r["areas"] = dict(sorted(areas.items(), key=lambda par: -par[1]))
        log = self._git_ok("log", "--format=%h%x09%cI%x09%s", f"{main}..{r['sha']}") or ""
        r["commits"] = [dict(zip(("hash", "data", "assunto"), linha.split("\t", 2)))
                        for linha in log.splitlines()[:30] if linha.count("\t") >= 2]

    def _conflitos(self, main: str, sha: str) -> list[str]:
        """`git merge-tree --write-tree`: simula o merge SEM ramo nem working
        tree (so escreve objetos soltos no clone nosso)."""
        codigo, saida = self._git("merge-tree", "--write-tree", "--name-only", "--no-messages", main, sha)
        if codigo == 0:
            return []
        if codigo == 1:
            return [linha.strip() for linha in saida.splitlines()[1:] if linha.strip()]
        return ["(não consegui simular o merge)"]

    @staticmethod
    def _precisa_testar(r: dict) -> tuple[bool, str]:
        if not r["a_frente"]:
            return False, "já está na main"
        if r.get("pontas"):
            return False, f"o ramo {r['pontas'][0]} contém este: testo a ponta"
        if (r.get("ci") or {}).get("conclusao") == "failure":
            return False, "o CI dele já está vermelho"
        if not r["ff"]:
            return False, "não é fast-forward: o teste do ramo não diria como fica o merge"
        return True, ""

    def _testar_real(self, sha: str, ramo: str) -> dict:
        from . import vigia
        try:
            ficha = self.versoes.preparar(sha, construir=False, rotulo=f"ramo {ramo}", buscar=False)
        except ErroDeVersao as exc:
            texto = str(exc)
            return {"rodou": True, "ok": False, "npm_ci": False if "npm" in texto else None, "erro": texto[-400:]}
        pasta = self.versoes.pasta(ficha["sha"])
        with self.versoes.trava(f"bluelock_versao_{sha[:12]}"):
            inicio = datetime.now()
            codigo, saida, erro = vigia.npm_real(pasta)("test", "--", f"--testTimeout={vigia.TEMPO_POR_TESTE_MS}",
                                                        prazo=vigia.NPM_TEST_PRAZO_S)
        texto = saida + "\n" + erro
        resultado = {"rodou": True, "ok": codigo == 0, "em": self.relogio().isoformat(timespec="seconds")}
        resultado.update(vigia.resumo_de_testes(texto))
        resultado.setdefault("duracao_s", round((datetime.now() - inicio).total_seconds(), 1))
        estouros = texto.count("Test timed out")
        if estouros:
            resultado["por_tempo"] = estouros
        if codigo != 0:
            resultado["falhas"] = [linha.strip() for linha in vigia._ANSI.sub("", texto).splitlines()
                                   if linha.strip().startswith(("FAIL", "×"))][:8]
        return resultado

    # --- textos -----------------------------------------------------
    def texto_do_aviso(self, ramos: list[dict]) -> str:
        linhas = [f"🔵 *Blue Lock* — {len(ramos)} ramo(s) novo(s) no GitHub"]
        for r in ramos:
            v = r["veredito"]
            quando = _hora_local(r.get("data"))
            linhas.append(f"{ICONES.get(v['tipo'], '•')} `{r['ramo']}` ({r['sha'][:7]}, {quando}, "
                          f"+{r['a_frente']}/-{r['atras']}) — {v['texto']}")
            if r.get("areas"):
                linhas.append("   mexe em: " + ", ".join(f"{a} {n}" for a, n in list(r["areas"].items())[:5]))
            if r.get("comando"):
                linhas.append(f"   para dar merge (no seu clone, depois de `git fetch`): `{r['comando']}`")
            elif v["tipo"] == "olho" and r.get("pr"):
                linhas.append(f"   abrir PR: {r['pr']}")
        linhas.append("Nada foi empurrado: o merge é seu. Detalhes no lançador 'Blue Lock — versões'.")
        return "\n".join(linhas)


def _json_lista(texto: str) -> list[dict]:
    try:
        dados = json.loads(texto or "[]")
    except ValueError:
        return []
    return [d for d in dados if isinstance(d, dict)] if isinstance(dados, list) else []


def _hora_local(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m %H:%M")
    except ValueError:
        return iso[:16]


def tabela(dados: dict) -> str:
    """A tabela em texto (o `status` e o relatorio)."""
    linhas = [f"main {dados.get('main', {}).get('sha', '?')[:7]} — olhado em {dados.get('olhado_em', '?')}",
              f"{'ramo':44} {'cabeça':8} {'+/-':>8} {'ff':3} {'CI':9} {'testes':12} veredito"]
    for r in dados.get("ramos") or []:
        ci = (r.get("ci") or {})
        ci_txt = ci.get("conclusao") or ci.get("estado") or ("—" if not r.get("a_frente") else "sem CI")
        ff = "—" if not r.get("a_frente") else ("sim" if r.get("ff") else "não")
        t = r.get("testes") or {}
        contas = t.get("testes") or {}
        t_txt = (f"{contas.get('passou', '?')}/{contas.get('total', '?')}" if t.get("rodou") and contas
                 else ("rodou" if t.get("rodou") else "—"))
        linhas.append(f"{r['ramo'][:44]:44} {r['sha'][:7]:8} {'+' + str(r['a_frente']) + '/-' + str(r['atras']):>8} "
                      f"{ff:3} {ci_txt[:9]:9} {t_txt:12} {r['veredito']['texto']}")
    return "\n".join(linhas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bluelock.ramos", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="acao", required=True)
    olhar = sub.add_parser("olhar", help="uma olhada nos ramos (o que a tarefa roda)")
    olhar.add_argument("--seco", action="store_true", help="analisa e grava ramos.json, sem Telegram")
    olhar.add_argument("--sem-testes", action="store_true", help="não roda npm test")
    olhar.add_argument("--saida", help="arquivo de log (acrescenta)")
    sub.add_parser("status", help="a tabela do último ramos.json")
    args = parser.parse_args(argv)
    if args.acao == "status":
        dados = VigiaDeRamos().ler()
        print(tabela(dados) if dados.get("ramos") is not None else "ainda não olhei os ramos")
        return 0
    log = None
    if args.saida:
        def log(texto, _caminho=args.saida):
            with open(_caminho, "a", encoding="utf-8") as fh:
                fh.write(texto + "\n")
    vigia = VigiaDeRamos(log=log)
    resultado = vigia.olhar(testar=not args.sem_testes, avisar=not args.seco)
    resumo = {k: v for k, v in resultado.items() if k != "tabela"}
    if log:
        log(f"[bluelock-ramos] {datetime.now():%d/%m %H:%M} {json.dumps(resumo, ensure_ascii=False)}")
    else:
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        if resultado.get("tabela"):
            print(tabela(resultado["tabela"]))
    return 0 if resultado.get("acao") not in ("fetch_falhou", "sem_main") else 1


if __name__ == "__main__":
    raise SystemExit(main())
