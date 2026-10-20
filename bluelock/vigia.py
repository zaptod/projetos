# -*- coding: utf-8 -*-
"""O vigia da main do Blue Lock: o Adrian commitou? A gente acompanha.

POR QUE EXISTE. Pedido do Adrian (19/10/2026): "leia o projeto da main e
verifique sempre que a main for atualizada para atualizarmos o projeto
junto". Ele commita varias vezes por dia (cinco commits so em 18/10), e a
nossa parte — o gravador, o doc da sessao, o formato do video — depende de
`src/field.ts`, `src/simulation.ts` e `src/characters.ts` continuarem como
estavam quando a gente leu.

O QUE ELE FAZ, uma olhada por vez (a tarefa do Agendador chama a cada 30 min):

  1. `git fetch origin main` no espelho (`E:\\BLUE-Lock-project`).
  2. Confere que o espelho continua espelho: no ramo `main` e LIMPO. Sujo ou
     fora da main = alguem escreveu la; avisa e PARA (nunca limpa nada).
  3. `origin/main` igual ao HEAD: nada (ou termina um teste adiado).
  4. `origin/main` andou mas o HEAD nao e ancestral dele (a main foi
     reescrita): avisa UMA vez por commit remoto e PARA, sem puxar.
  5. Fast-forward (`git merge --ff-only origin/main`, o mesmo que o
     `git pull --ff-only` faria depois do fetch); registra commits e arquivos
     em `mudancas.jsonl`.
  6. `npm ci` se o `package-lock.json` mudou (ou nao ha `node_modules`) e
     `npm test`. PESADO: so fora da janela das postagens e sem o League of
     Legends aberto (`comum.pode_pesado`). Se nao pode, adia; depois de
     `PRAZO_ADIADO_H` horas avisa mesmo sem teste.
  7. Avisa no Telegram e abre UM pedido na Mesa do coordenador (o mesmo
     `alvo` junta mudancas seguidas no pedido que ainda estiver aberto).

O QUE ELE NUNCA FAZ: commit, push, checkout, reset, clean, stash, editar
arquivo — nada no espelho alem do fetch e do avanco fast-forward. O
`node_modules/` e o `.npm-cache/` que o `npm ci` escreve sao ignorados pelo
`.gitignore` do proprio repositorio.

    python -m bluelock.vigia olhar        uma olhada (o que a tarefa roda)
    python -m bluelock.vigia status       o estado guardado
    python -m bluelock.vigia instalar     cria a tarefa (30 min) — so o orquestrador
    python -m bluelock.vigia remover      apaga a tarefa
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from . import comum

TAREFA = "NeuralFights_bluelock_main"
INTERVALO_MIN = 30
# 45 min bastavam para a main sozinha; com os ramos (ate 2 `npm test` de
# ~2,5 min com a maquina livre, 19/10, e prazo de 25 min cada) vai a 90. A
# tarefa nao abre outra instancia enquanto uma roda (IgnoreNew).
LIMITE_DA_TAREFA = "PT90M"
PRAZO_ADIADO_H = 3
FALHAS_PARA_AVISAR = 6          # 6 olhadas sem rede = 3 h
ALVO_DO_PEDIDO = "bluelock-main"
NPM_CI_PRAZO_S = 900
NPM_TEST_PRAZO_S = 1500
# MEDIDO em 19/10/2026, 09:56: com a maquina a 100% (gravacao de luta e
# historias rodando), `npm test` deu 1369 de 1378 — os 9 que cairam eram TODOS
# "Test timed out in 5000ms" em `src/pass-diagnostics.test.ts` (o padrao do
# vitest). Esta maquina divide a CPU com a fabrica; o vigia quer saber se o
# codigo quebrou, nao se o PC estava ocupado. Por isso 60 s por teste — e o
# aviso conta a parte, ainda assim, quantos estouraram o tempo.
TEMPO_POR_TESTE_MS = 60000
GIT_PRAZO_S = 180
# O que a NOSSA parte usa do repositorio dele. Mudou um destes = o gravador
# pode ter quebrado; o aviso diz isso em destaque.
PONTOS_DE_CONTATO = ("src/field.ts", "src/simulation.ts", "src/characters.ts",
                     "src/visual-state.ts", "src/replay.ts", "src/main.ts",
                     "index.html", "package.json", "package-lock.json")
RAIZ = Path(__file__).resolve().parent.parent
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


# ------------------------------------------------------------- executores
def git_real(espelho: Path):
    def rodar(*args, prazo=GIT_PRAZO_S):
        try:
            proc = subprocess.run(["git", "-C", str(espelho), *args], capture_output=True,
                                  timeout=prazo, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as exc:
            return 99, "", f"{type(exc).__name__}: {exc}"
        return (proc.returncode, (proc.stdout or b"").decode("utf-8", "replace"),
                (proc.stderr or b"").decode("utf-8", "replace"))
    return rodar


def npm_real(espelho: Path):
    exe = shutil.which("npm") or "npm"

    def rodar(*args, prazo=NPM_TEST_PRAZO_S):
        ambiente = dict(os.environ, NO_COLOR="1", FORCE_COLOR="0", CI="1")
        try:
            proc = subprocess.run([exe, *args], cwd=str(espelho), capture_output=True,
                                  timeout=prazo, env=ambiente, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            return 124, "", f"estourou {prazo} s"
        except (OSError, subprocess.SubprocessError) as exc:
            return 99, "", f"{type(exc).__name__}: {exc}"
        return (proc.returncode, (proc.stdout or b"").decode("utf-8", "replace"),
                (proc.stderr or b"").decode("utf-8", "replace"))
    return rodar


def avisar_real(texto: str) -> bool:
    from remoto.__main__ import avisar
    return bool(avisar(texto))


def pedir_real(texto: str, alvo: str) -> dict:
    from coordenador import pedidos
    return pedidos.contratar(texto, "chat", cargo="executor", ia="codex",
                             titulo="Blue Lock: a main mudou", alvo=alvo,
                             permitidos=["docs/**", "bluelock/**", ".claude/agents/blue-lock.md"])


@contextmanager
def trava_real():
    """A mesma trava do gravador: puxar a main com o Vite servindo o espelho
    recarregaria a pagina no meio da gravacao."""
    from builds import travas
    with travas.trava("bluelock_espelho") as minha:
        yield minha


def resumo_de_testes(saida: str) -> dict:
    """Le o rodape do vitest: `Tests  2 failed | 1376 passed (1378)`."""
    texto = _ANSI.sub("", saida or "")
    ficha = {}
    for rotulo, chave in (("Test Files", "arquivos"), ("Tests", "testes")):
        achado = re.search(rf"^\s*{rotulo}\s+(.+?)\s*$", texto, re.MULTILINE)
        if not achado:
            continue
        linha = achado.group(1)
        contas = {nome: int(n) for n, nome in re.findall(r"(\d+)\s+(passed|failed|skipped|todo)", linha)}
        total = re.search(r"\((\d+)\)", linha)
        ficha[chave] = {"passou": contas.get("passed", 0), "falhou": contas.get("failed", 0),
                        "pulou": contas.get("skipped", 0) + contas.get("todo", 0),
                        "total": int(total.group(1)) if total else None}
    duracao = re.search(r"^\s*Duration\s+([\d.]+)\s*(ms|s)\b", texto, re.MULTILINE)
    if duracao:
        valor = float(duracao.group(1))
        ficha["duracao_s"] = round(valor / 1000 if duracao.group(2) == "ms" else valor, 1)
    return ficha


# ------------------------------------------------------------------ vigia
class Vigia:
    def __init__(self, *, espelho: Path | None = None, git=None, npm=None, avisar=None, pedir=None,
                 pode_pesado=None, relogio=datetime.now, estado=None, trava=None, log=None):
        self.espelho = Path(espelho or comum.ESPELHO)
        self.git = git or git_real(self.espelho)
        self.npm = npm or npm_real(self.espelho)
        self.avisar = avisar or avisar_real
        self.pedir = pedir or pedir_real
        self.pode_pesado = pode_pesado or comum.pode_pesado
        self.relogio = relogio
        self.arquivo = Path(estado) if estado else comum.pasta() / "vigia.json"
        self.mudancas = self.arquivo.with_name("mudancas.jsonl")
        self.trava = trava or trava_real
        self.log = log or (lambda texto: print(texto, flush=True))

    # --- estado ---------------------------------------------------------
    def _ler(self) -> dict:
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

    def _agora(self) -> datetime:
        return self.relogio()

    def _texto(self, rotulo: str) -> str:
        return f"🔵 *Blue Lock* — {rotulo}"

    def _git_ok(self, *args, prazo=GIT_PRAZO_S) -> str | None:
        codigo, saida, _erro = self.git(*args, prazo=prazo)
        return saida.strip() if codigo == 0 else None

    # --- a olhada -------------------------------------------------------
    def olhar(self, *, sem_testes: bool = False) -> dict:
        with self.trava() as minha:
            if not minha:
                return self._fim({"acao": "ocupado", "motivo": "o gravador está usando o espelho"})
            return self._olhar(sem_testes=sem_testes)

    def _fim(self, resultado: dict) -> dict:
        self.log(f"[bluelock-vigia] {self._agora():%d/%m %H:%M} {json.dumps(resultado, ensure_ascii=False)}")
        return resultado

    def _problema(self, est: dict, chave: str, texto: str) -> dict:
        """Avisa UMA vez por problema (o mesmo problema a cada 30 min nao e
        noticia) e para sem tocar em nada."""
        if est.get("problema") != chave:
            self.avisar(self._texto(texto))
            est["problema"] = chave
        self._gravar(est)
        return self._fim({"acao": "problema", "problema": chave, "motivo": texto})

    def _olhar(self, *, sem_testes: bool) -> dict:
        est = self._ler()
        if not (self.espelho / ".git").exists():
            return self._problema(est, "sem_espelho",
                                  f"o espelho `{self.espelho}` não existe ou não é um clone git. "
                                  f"Para refazer: `git clone {comum.URL} {self.espelho}`")
        codigo, _saida, erro = self.git("fetch", "--quiet", comum.REMOTO, comum.RAMO, prazo=GIT_PRAZO_S)
        if codigo != 0:
            est["fetch_falhas"] = int(est.get("fetch_falhas") or 0) + 1
            if est["fetch_falhas"] == FALHAS_PARA_AVISAR:
                self.avisar(self._texto(f"{FALHAS_PARA_AVISAR} olhadas seguidas sem conseguir o "
                                        f"`git fetch` da main ({erro.strip()[:200]}). Sem rede? "
                                        "Continuo tentando a cada 30 min."))
            self._gravar(est)
            return self._fim({"acao": "fetch_falhou", "vezes": est["fetch_falhas"], "erro": erro.strip()[:300]})
        est["fetch_falhas"] = 0
        est["olhado_em"] = self._agora().isoformat(timespec="seconds")

        ramo = self._git_ok("rev-parse", "--abbrev-ref", "HEAD")
        if ramo != comum.RAMO:
            return self._problema(est, f"ramo:{ramo}",
                                  f"o espelho saiu da `{comum.RAMO}` (está em `{ramo}`). Ele é só "
                                  "leitura: ninguém devia ter trocado de ramo lá. Não puxei nada.")
        sujeira = self._git_ok("status", "--porcelain")
        if sujeira is None:
            return self._problema(est, "status", "não consegui ler o `git status` do espelho.")
        if sujeira:
            arquivos = [linha[3:] for linha in sujeira.splitlines() if linha.strip()]
            return self._problema(est, "sujo:" + "|".join(arquivos[:20]),
                                  f"o espelho tem {len(arquivos)} arquivo(s) mexido(s) "
                                  f"(`{'`, `'.join(arquivos[:5])}`). Ele é só leitura: alguém "
                                  "escreveu lá. Não puxei nem limpei nada — confira e desfaça à mão.")
        head = self._git_ok("rev-parse", "HEAD")
        remoto = self._git_ok("rev-parse", f"{comum.REMOTO}/{comum.RAMO}")
        if not head or not remoto:
            return self._problema(est, "rev-parse", "não consegui ler o HEAD ou a origin/main do espelho.")
        est.pop("problema", None)

        if head == remoto:
            est["visto"] = head
            if est.get("pendente"):
                return self._concluir(est, sem_testes=sem_testes)
            self._gravar(est)
            return self._fim({"acao": "nada", "head": head[:7]})

        codigo, _s, _e = self.git("merge-base", "--is-ancestor", head, remoto)
        if codigo != 0:
            if est.get("divergiu") != remoto:
                self.avisar(self._texto(
                    f"a main do GitHub foi reescrita: o espelho está em `{head[:7]}` e a "
                    f"origin/main em `{remoto[:7]}`, que não descende dele (force-push ou "
                    "rebase). NÃO puxei: o pull não seria fast-forward. Para alinhar, à mão: "
                    f"`git -C {self.espelho} reset --hard origin/main` (o espelho não tem "
                    "trabalho nosso)."))
                est["divergiu"] = remoto
            self._gravar(est)
            return self._fim({"acao": "divergiu", "head": head[:7], "remoto": remoto[:7]})

        codigo, _s, erro = self.git("merge", "--ff-only", f"{comum.REMOTO}/{comum.RAMO}")
        novo = self._git_ok("rev-parse", "HEAD")
        if codigo != 0 or novo != remoto:
            return self._problema(est, f"merge:{remoto}",
                                  f"o avanço fast-forward para `{remoto[:7]}` falhou "
                                  f"({erro.strip()[:200]}). O espelho ficou em `{head[:7]}`.")
        est.pop("divergiu", None)
        mudanca = self.descrever(head, novo)
        self._registrar_mudanca(mudanca)
        pendente = est.get("pendente") or {"de": head, "desde": self._agora().isoformat(timespec="seconds")}
        pendente["para"] = novo
        est["pendente"] = pendente
        est["visto"] = novo
        self._gravar(est)
        self.log(f"[bluelock-vigia] puxei {head[:7]}..{novo[:7]}: {len(mudanca['commits'])} commit(s)")
        return self._concluir(est, sem_testes=sem_testes)

    # --- o que mudou ----------------------------------------------------
    def descrever(self, de: str, para: str) -> dict:
        intervalo = f"{de}..{para}"
        bruto = self._git_ok("log", "--reverse", "--format=%h%x09%ad%x09%an%x09%s",
                             "--date=format-local:%d/%m %H:%M", intervalo) or ""
        commits = []
        for linha in bruto.splitlines():
            partes = linha.split("\t", 3)
            if len(partes) == 4:
                commits.append({"hash": partes[0], "quando": partes[1], "autor": partes[2],
                                "assunto": partes[3]})
        nomes = self._git_ok("diff", "--name-status", "--no-renames", de, para) or ""
        arquivos = []
        for linha in nomes.splitlines():
            partes = linha.split("\t", 1)
            if len(partes) == 2:
                arquivos.append({"estado": partes[0][:1], "caminho": partes[1]})
        caminhos = [a["caminho"] for a in arquivos]
        pastas = {}
        for caminho in caminhos:
            topo = caminho.split("/", 1)[0] if "/" in caminho else "(raiz)"
            pastas[topo] = pastas.get(topo, 0) + 1
        versao = None
        pacote = self._git_ok("show", f"{para}:package.json")
        if pacote:
            try:
                versao = json.loads(pacote).get("version")
            except ValueError:
                versao = None
        return {"de": de, "para": para, "commits": commits, "arquivos": arquivos,
                "pastas": dict(sorted(pastas.items(), key=lambda par: -par[1])),
                "lock": "package-lock.json" in caminhos,
                "contato": [c for c in caminhos if c in PONTOS_DE_CONTATO],
                "versao": versao}

    def _registrar_mudanca(self, mudanca: dict) -> None:
        linha = dict(mudanca, em=self._agora().isoformat(timespec="seconds"),
                     arquivos=len(mudanca["arquivos"]))
        self.mudancas.parent.mkdir(parents=True, exist_ok=True)
        with open(self.mudancas, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")

    # --- testes, aviso e pedido ----------------------------------------
    def _concluir(self, est: dict, *, sem_testes: bool) -> dict:
        pendente = est["pendente"]
        agora = self._agora()
        try:
            desde = datetime.fromisoformat(pendente.get("desde") or "")
        except ValueError:
            desde = agora
        pode, motivo = (False, "pedido sem testes (--sem-testes)") if sem_testes else self.pode_pesado(agora)
        if not pode and agora - desde < timedelta(hours=PRAZO_ADIADO_H) and not sem_testes:
            pendente["adiado"] = motivo
            self._gravar(est)
            return self._fim({"acao": "adiado", "motivo": motivo, "para": pendente["para"][:7]})
        mudanca = self.descrever(pendente["de"], pendente["para"])
        testes = self._testar(mudanca) if pode else {"rodou": False, "motivo": motivo}
        texto = self.texto_do_aviso(mudanca, testes)
        entregue = self.avisar(texto)
        pedido = None
        try:
            pedido = self.pedir(self.texto_do_pedido(mudanca, testes), ALVO_DO_PEDIDO)
        except Exception as exc:                                # noqa: BLE001
            self.avisar(self._texto(f"não consegui abrir o pedido na Mesa ({type(exc).__name__}: "
                                    f"{exc}). Abra à mão: `python -m coordenador pedir \"Blue Lock "
                                    f"main mudou {mudanca['de'][:7]}..{mudanca['para'][:7]} — rever "
                                    "a integração\"`"))
        ident = (pedido or {}).get("id")
        est["ultimo"] = {"de": mudanca["de"], "para": mudanca["para"],
                         "commits": len(mudanca["commits"]), "testes": testes,
                         "avisado": bool(entregue), "pedido": ident,
                         "pedido_juntado": bool((pedido or {}).get("duplicado")),
                         "em": agora.isoformat(timespec="seconds")}
        est.pop("pendente", None)
        self._gravar(est)
        return self._fim({"acao": "avisou", "de": mudanca["de"][:7], "para": mudanca["para"][:7],
                          "commits": len(mudanca["commits"]), "testes": testes, "pedido": ident})

    def _testar(self, mudanca: dict) -> dict:
        ficha = {"rodou": True}
        if mudanca["lock"] or not (self.espelho / "node_modules").is_dir():
            codigo, saida, erro = self.npm("ci", "--no-audit", "--no-fund", prazo=NPM_CI_PRAZO_S)
            ficha["npm_ci"] = codigo == 0
            if codigo != 0:
                ficha["ok"] = False
                ficha["erro"] = _ANSI.sub("", (erro or saida)).strip()[-400:]
                return ficha
        inicio = datetime.now()
        codigo, saida, erro = self.npm("test", "--", f"--testTimeout={TEMPO_POR_TESTE_MS}",
                                       prazo=NPM_TEST_PRAZO_S)
        ficha.update(resumo_de_testes(saida + "\n" + erro))
        estouros = (saida + erro).count("Test timed out")
        if estouros:
            ficha["por_tempo"] = estouros
        ficha.setdefault("duracao_s", round((datetime.now() - inicio).total_seconds(), 1))
        ficha["ok"] = codigo == 0
        if codigo != 0:
            linhas = [linha for linha in _ANSI.sub("", saida + "\n" + erro).splitlines()
                      if "FAIL" in linha or "×" in linha or "Error" in linha]
            ficha["falhas"] = linhas[:8]
        sujeira = self._git_ok("status", "--porcelain")
        if sujeira:
            ficha["sujou"] = [linha[3:] for linha in sujeira.splitlines()][:10]
        return ficha

    def texto_do_aviso(self, mudanca: dict, testes: dict) -> str:
        commits = mudanca["commits"]
        linhas = [self._texto(f"a main andou `{mudanca['de'][:7]}` → `{mudanca['para'][:7]}`"
                              + (f" (v{mudanca['versao']})" if mudanca.get("versao") else "")),
                  f"{len(commits)} commit(s), {len(mudanca['arquivos'])} arquivo(s):"]
        for commit in commits[-8:]:
            linhas.append(f"• `{commit['hash']}` {commit['quando']} — {commit['assunto'][:90]}")
        if len(commits) > 8:
            linhas.append(f"• … e mais {len(commits) - 8} antes")
        if mudanca["pastas"]:
            linhas.append("Pastas: " + ", ".join(f"{p} {n}" for p, n in list(mudanca["pastas"].items())[:6]))
        if mudanca["contato"]:
            linhas.append("⚠️ Mexeu no que a nossa gravação usa: "
                          + ", ".join(f"`{c}`" for c in mudanca["contato"]))
        linhas.append(self._linha_de_testes(testes))
        linhas.append("Abri um pedido na Mesa para rever a nossa parte (docs/sessoes/blue-lock.md).")
        return "\n".join(linhas)

    @staticmethod
    def _linha_de_testes(testes: dict) -> str:
        if not testes.get("rodou"):
            return f"Testes: não rodei ({testes.get('motivo') or 'sem motivo'})."
        if testes.get("npm_ci") is False:
            return f"Testes: ❌ o `npm ci` falhou ({testes.get('erro', '')[:160]})."
        contas = testes.get("testes") or {}
        texto = (f"{contas.get('passou', '?')} passaram, {contas.get('falhou', 0)} falharam"
                 if contas else "sem rodapé do vitest")
        marca = "✅" if testes.get("ok") else "❌"
        extra = f" em {testes['duracao_s']} s" if testes.get("duracao_s") is not None else ""
        if testes.get("npm_ci"):
            extra += " (com `npm ci`: o package-lock mudou)"
        if testes.get("por_tempo"):
            extra += (f"; {testes['por_tempo']} estouraram o tempo ({TEMPO_POR_TESTE_MS // 1000} s "
                      "por teste) — máquina ocupada? rode de novo antes de culpar a main")
        if testes.get("sujou"):
            extra += f"; o teste deixou {len(testes['sujou'])} arquivo(s) mexido(s) no espelho"
        return f"Testes: {marca} `npm test` — {texto}{extra}."

    def texto_do_pedido(self, mudanca: dict, testes: dict) -> str:
        commits = "\n".join(f"- {c['hash']} ({c['quando']}) {c['assunto']}" for c in mudanca["commits"][-30:])
        arquivos = "\n".join(f"- {a['estado']} {a['caminho']}" for a in mudanca["arquivos"][:60])
        if len(mudanca["arquivos"]) > 60:
            arquivos += f"\n- … e mais {len(mudanca['arquivos']) - 60}"
        return (
            f"Blue Lock main mudou: {mudanca['de'][:7]}..{mudanca['para'][:7]} "
            f"({len(mudanca['commits'])} commit(s)) — rever a integração\n\n"
            "O Adrian atualizou a main do simulador Blue Lock (repositório dele, "
            "https://github.com/zaptod/BLUE-Lock-project). O vigia já puxou para o espelho "
            f"de leitura `{self.espelho}`. Tarefa: ler `docs/sessoes/blue-lock.md`, ver o que "
            "mudou (git log/diff no espelho) e atualizar a NOSSA parte junto: o doc da sessão "
            "(seção 'Estado da main conferido', com o hash novo), o gravador `bluelock/gravar.py` "
            "se algum ponto de contato mudou (Field, Simulation, characters, visual-state) e o "
            "formato de vídeo proposto se o jogo ganhou algo que aparece bem em vídeo.\n\n"
            "PROIBIDO: commitar, empurrar ou editar qualquer coisa em E:\\BLUE-Lock-project. "
            "Se precisarmos de algo lá dentro, escreva a proposta para o Adrian.\n\n"
            f"Pontos de contato que mudaram: {', '.join(mudanca['contato']) or 'nenhum'}\n"
            f"{self._linha_de_testes(testes)}\n\nCommits:\n{commits}\n\nArquivos:\n{arquivos}\n")

    def status(self) -> dict:
        return self._ler()


# --------------------------------------------------------------- a tarefa
def caminho_do_lancador() -> Path:
    return RAIZ / "bluelock_vigia.cmd"


def escrever_lancador(python: str | None = None) -> Path:
    """O .cmd da tarefa. A saida vai por `--saida` (aberta pelo Python): o
    `>>` do cmd tranca o arquivo e a proxima rodada morre (memoria
    agendador-arquivo-trancado)."""
    destino = caminho_do_lancador()
    python = python or sys.executable
    saida = RAIZ / "outputs" / "bluelock_vigia.txt"
    saida.parent.mkdir(parents=True, exist_ok=True)
    # 19/10/2026: a mesma tarefa olha tambem os RAMOS (bluelock.ramos), logo
    # depois da main e no mesmo log. Os dois em sequencia: nunca dois `npm
    # test` ao mesmo tempo na maquina.
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        fh.write("@echo off\r\n"
                 "rem Vigia da main e dos ramos do Blue Lock (a cada 30 min).\r\n"
                 "rem Gerado por: python -m bluelock.vigia instalar\r\n"
                 f'cd /d "{RAIZ}"\r\n'
                 f'"{python}" -u -X utf8 -m bluelock.vigia olhar --saida "{saida}" > NUL 2>&1\r\n'
                 f'"{python}" -u -X utf8 -m bluelock.ramos olhar --saida "{saida}" > NUL 2>&1\r\n')
    return destino


def instalar(rodar=subprocess.run) -> dict:
    from builds import tarefas_windows
    lancador = escrever_lancador()
    proc = rodar(["schtasks", "/Create", "/TN", TAREFA, "/TR", tarefas_windows.acao_oculta(lancador),
                  "/SC", "MINUTE", "/MO", str(INTERVALO_MIN), "/RL", "LIMITED", "/F"],
                 capture_output=True, timeout=60, creationflags=NO_WINDOW)
    ficha = {"tarefa": TAREFA, "ok": proc.returncode == 0, "lancador": str(lancador),
             "mensagem": ((proc.stdout or b"") + (proc.stderr or b"")).decode("oem", "replace").strip()}
    if ficha["ok"]:
        ficha["ajustes"] = tarefas_windows.endurecer(TAREFA)
        ficha["limite"] = tarefas_windows.limitar_execucao(TAREFA, LIMITE_DA_TAREFA)
    return ficha


def remover(rodar=subprocess.run) -> dict:
    proc = rodar(["schtasks", "/Delete", "/TN", TAREFA, "/F"], capture_output=True, timeout=60,
                 creationflags=NO_WINDOW)
    return {"tarefa": TAREFA, "ok": proc.returncode == 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bluelock.vigia", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="acao", required=True)
    olhar = sub.add_parser("olhar", help="uma olhada na main (o que a tarefa roda)")
    olhar.add_argument("--sem-testes", action="store_true", help="avisa e pede sem rodar npm")
    olhar.add_argument("--saida", help="arquivo de log (acrescenta)")
    sub.add_parser("status")
    sub.add_parser("instalar", help="cria a tarefa do Agendador (30 min)")
    sub.add_parser("remover")
    args = parser.parse_args(argv)
    if args.acao == "olhar":
        log = None
        if args.saida:
            def log(texto, _caminho=args.saida):
                with open(_caminho, "a", encoding="utf-8") as fh:
                    fh.write(texto + "\n")
        resultado = Vigia(log=log).olhar(sem_testes=args.sem_testes)
        if not args.saida:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0 if resultado.get("acao") not in ("problema",) else 1
    if args.acao == "status":
        print(json.dumps(Vigia().status(), ensure_ascii=False, indent=2))
        return 0
    ficha = instalar() if args.acao == "instalar" else remover()
    print(json.dumps(ficha, ensure_ascii=False, indent=2))
    return 0 if ficha.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
