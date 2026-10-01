# -*- coding: utf-8 -*-
"""O despachante: tarefas de codigo delegadas ao Codex (F1 do plano 2595b531).

Pedido do Adrian (01/10/2026 13:30): "Comprei o Gemini Pro e o ChatGPT Plus.
Agora nos iremos delegar algumas das suas tarefas a eles para que voce nao
queime todos os tokens." Plano: `~/.claude/plans/delegar-codex-gemini.md`;
decisoes `geral/delegar-o-que-primeiro`, `quem-confere-delegado`,
`codex-commita` (so propoe o diff), `teto-dos-delegados` (50% da janela de 5 h).

O CAMINHO de uma tarefa, cada passo um subcomando:

    criar    worktree propria (E:\\projetos-wt\\codex-<id>, branch delegar/codex-<id>)
             + a tarefa (`.codex_tarefa.md`, com as regras de `delegar_prompt.md`)
    rodar    `codex exec --json` com o prompt por STDIN (o PowerShell quebra texto
             longo em argumento); cada evento vai AO VIVO para `eventos.jsonl`
    corrigir `codex exec resume <thread>` na mesma conversa, com o texto novo
    diff     o patch + o validador: caminho fora da lista, binario ou diff grande
             = recusa
    testar   roda os testes na worktree, com TEMP no E:
    aplicar  `git apply --check` e `git apply` na arvore principal; recusa entre
             :25 e :55 (a postagem) e com publicacao em voo. O commit e do
             orquestrador, por caminho.
    limpar   tira a worktree e a branch

Tudo de uma tarefa mora em `%LOCALAPPDATA%\\neural-fights\\delegados\\<id>\\`:
`estado.json`, `eventos.jsonl` (um evento do Codex por linha, com a hora),
`resposta.md`, `diff.patch` + `diff.json`, `testes.log`, `log.txt`. O app (a
Oficina do Codex) le esses arquivos; ninguem mais escreve neles.

O INTERRUPTOR DO CLAUDE vale aqui tambem: proibido, nada comeca, e o Codex que
esta rodando e morto na hora (checado a cada 2 s). O TETO e o da janela de 5 h
do Codex, lido dos `rollout-*.jsonl` que ele mesmo grava em `~/.codex/sessions`
(`rate_limits.primary.used_percent`); passou do teto, nao comeca, e quem ja
roda para. Sem medicao, recusa (falha fechado), a nao ser que o
`tokens_janela_max` do config diga um teto por contagem de tokens.

POR QUE O `-p no:cacheprovider`: o sandbox "elevated" do Codex roda os
comandos com outro usuario do Windows, e o Python 3.13+ cria pasta temporaria
(`mkdtemp`) com ACL so do dono. O `.pytest_cache` que o pytest dele deixou nas
worktrees de 01/10 nao abre nem para ler (`icacls`: acesso negado), e foi isso
que fez o `git worktree remove` falhar duas vezes com "Directory not empty".
O `PYTEST_ADDOPTS` do ambiente e a regra do prompt evitam a pasta; o `limpar`
move o que sobrar para `_lixo_codex` e diz o comando de administrador.

CLI:

    python -m remoto.delegar criar --id X --tarefa arq.md --permitido "remoto/**" [--permitido ...]
                                   [--modelo M] [--esforco E]
    python -m remoto.delegar rodar --id X [--fundo] [--forcar]
    python -m remoto.delegar corrigir --id X --texto arq.md [--fundo] [--forcar]
    python -m remoto.delegar diff --id X
    python -m remoto.delegar testar --id X --cmd "python -m pytest remoto/test_x.py -q"
    python -m remoto.delegar aplicar --id X [--sem-testes]
    python -m remoto.delegar limpar --id X | --orfas
    python -m remoto.delegar parar --id X
    python -m remoto.delegar listar | ver --id X | uso | modelos | onde
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from . import claude_estado
from .config import runtime_dir

RAIZ = Path(__file__).resolve().parents[1]
PROMPT_PADRAO = Path(__file__).with_name("delegar_prompt.md")

# Os testes apontam tudo para outro lugar.
PASTA = None                  # %LOCALAPPDATA%\neural-fights\delegados
REPO = None                   # a arvore principal (E:\projetos)
WT_RAIZ = None                # E:\projetos-wt
TEMP_TESTES = None            # E:\tmp_pytest
CODEX = None                  # [executavel, ...] do codex; None = achar no PATH
CODEX_HOME = None             # ~/.codex (so leitura: sessions, models_cache, config.toml)

IA = "codex"
_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,39}")
_MODELO_LIVRE = re.compile(r"[a-z0-9][a-z0-9._-]{1,48}")
ESFORCOS = ("low", "medium", "high", "xhigh", "max", "ultra")
SITUACOES = ("criado", "rodando", "terminou", "falhou", "parado")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TAREFA_MAX = 100_000          # bytes do .md da tarefa
GUARDA_S = 2.0                # de quanto em quanto o interruptor e olhado
TETO_A_CADA_S = 30.0          # e o teto (le o rollout)

# Os arquivos do despachante na worktree: nunca entram no diff.
NOSSOS = (".codex_tarefa.md", ".codex_resposta.md", ".codex_correcao.md")
# O que o Codex nunca mexe, qualquer que seja a lista da tarefa.
PROIBIDOS = ("ias/config.json", "random_builds/config/identity.json", "palco/**",
             "decisoes/**", ".claude/**", ".github/**", "*.png", "*.jpg", "*.jpeg",
             "*.webp", "*.gif", "*.mp4", "*.mp3", "*.wav", "*.sqlite*", "*.exe",
             "*.dll", "*auth.json", ".env*", "*credentials*", ".codex*", "piriri.py")

PADRAO_CONFIG = {
    "teto_codex_pct": 50,         # decisao geral/teto-dos-delegados (01/10)
    "tokens_janela_max": None,    # teto por contagem, so quando o uso nao e medido
    "diff_max_linhas": 800,
    "diff_max_arquivos": 20,
    "janela_sem_comecar": [30, 45],   # minutos da hora em que nada comeca
    "janela_sem_aplicar": [25, 55],   # a janela da postagem
    "rodar_timeout_s": 3600,
    "testes_timeout_s": 1800,
}

# Medidos em 01/10/2026 no `~/.codex/models_cache.json` (visibility "list"),
# para quando o cache nao existir. O campo livre aceita outro nome valido.
MODELOS_DOCUMENTADOS = ["gpt-6-astra", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol",
                        "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"]

# Comandos de leitura: a Oficina mostra "le" em vez de "roda".
LEITURA = {"get-content", "gc", "cat", "type", "rg", "select-string", "findstr",
           "ls", "dir", "get-childitem", "gci", "head", "tail", "sed", "more", "grep",
           "find", "tree", "wc", "get-item", "test-path", "resolve-path"}


class Recusa(Exception):
    """Nao vai acontecer; a mensagem e para quem pediu."""


# ================================================================ lugares
def pasta() -> Path:
    if PASTA:
        return Path(PASTA)
    if os.environ.get("NF_DELEGADOS_PASTA"):
        return Path(os.environ["NF_DELEGADOS_PASTA"])
    return runtime_dir() / "delegados"


def repo() -> Path:
    return Path(REPO) if REPO else RAIZ


def wt_raiz() -> Path:
    return Path(WT_RAIZ) if WT_RAIZ else Path(r"E:\projetos-wt")


def temp_testes() -> Path:
    return Path(TEMP_TESTES) if TEMP_TESTES else Path(r"E:\tmp_pytest")


def codex_home() -> Path:
    if CODEX_HOME:
        return Path(CODEX_HOME)
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def validar_id(tarefa_id: str) -> str:
    tarefa_id = str(tarefa_id or "").strip().lower()
    if not _ID.fullmatch(tarefa_id):
        raise Recusa("o id tem 3 a 40 letras minúsculas, números ou hífen")
    return tarefa_id


def pasta_da(tarefa_id: str) -> Path:
    return pasta() / validar_id(tarefa_id)


def worktree_de(tarefa_id: str) -> Path:
    return wt_raiz() / f"codex-{validar_id(tarefa_id)}"


def branch_de(tarefa_id: str) -> str:
    return f"delegar/codex-{validar_id(tarefa_id)}"


def _agora() -> datetime:
    return datetime.now()


def _agora_iso() -> str:
    return _agora().isoformat(timespec="seconds")


# ================================================================== disco
def _trava():
    from .api_http import trava_arquivo
    pasta().mkdir(parents=True, exist_ok=True)
    return trava_arquivo(pasta() / "delegar.lock")


def _ler_json(caminho: Path, padrao):
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return padrao
    except OSError as exc:
        raise Recusa(f"{caminho.name} não pôde ser lido: {exc}") from exc
    try:
        return json.loads(texto)
    except ValueError as exc:
        raise Recusa(f"{caminho.name} está ilegível") from exc


def _gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f".{caminho.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, caminho)


def ler_config() -> dict:
    dados = _ler_json(pasta() / "config.json", {})
    if not isinstance(dados, dict):
        raise Recusa("config.json dos delegados está ilegível")
    return {**PADRAO_CONFIG, **{k: v for k, v in dados.items() if k in PADRAO_CONFIG}}


def ler_estado(tarefa_id: str) -> dict:
    estado = _ler_json(pasta_da(tarefa_id) / "estado.json", None)
    if estado is None:
        raise Recusa(f"não existe a tarefa delegada {tarefa_id}")
    if not isinstance(estado, dict):
        raise Recusa(f"o estado de {tarefa_id} está ilegível")
    return estado


def _gravar_estado(estado: dict) -> None:
    estado["atualizado_em"] = _agora_iso()
    _gravar_json(pasta_da(estado["id"]) / "estado.json", estado)


def _mudar_estado(tarefa_id: str, **campos) -> dict:
    with _trava():
        estado = ler_estado(tarefa_id)
        estado.update(campos)
        _gravar_estado(estado)
    return estado


def _log(tarefa_id: str, texto: str) -> None:
    linha = f"{_agora().strftime('%d/%m %H:%M:%S')} {texto}"
    try:
        with open(pasta_da(tarefa_id) / "log.txt", "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
    except OSError:
        pass
    print(linha, flush=True)


def listar() -> list[dict]:
    """Todas as tarefas, da mais nova para a mais velha. Ilegivel aparece, com erro."""
    saida = []
    try:
        pastas = [p for p in pasta().iterdir() if p.is_dir() and _ID.fullmatch(p.name)]
    except FileNotFoundError:
        return []
    for p in pastas:
        try:
            estado = ler_estado(p.name)
        except Recusa as exc:
            estado = {"id": p.name, "situacao": "ilegivel", "erro": str(exc)}
        saida.append(estado)
    saida.sort(key=lambda e: str(e.get("criado_em") or ""), reverse=True)
    return saida


# ================================================================== git
def _git(*args, cwd: Path | None = None, verificar: bool = True,
         env: dict | None = None) -> subprocess.CompletedProcess:
    feito = subprocess.run(["git", *args], cwd=str(cwd or repo()), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           creationflags=NO_WINDOW, env=env)
    if verificar and feito.returncode != 0:
        raise Recusa(f"git {' '.join(args[:2])} falhou: "
                     f"{(feito.stderr or feito.stdout).strip()[:400]}")
    return feito


# ============================================================== o Codex
def comando_codex() -> list[str]:
    """O codex como lista de argumentos, sem passar pelo cmd.exe.

    O `codex.cmd` do npm passa os argumentos pelo cmd, que estraga aspas (o
    `-c sandbox_mode="workspace-write"`). Indo direto ao node + codex.js, a
    lista chega inteira.
    """
    if CODEX:
        return list(CODEX)
    achado = shutil.which("codex")
    if not achado:
        raise Recusa("o codex não está instalado (npm i -g @openai/codex)")
    pasta_npm = Path(achado).parent
    js = pasta_npm / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    if js.is_file():
        node = pasta_npm / "node.exe"
        node = str(node) if node.is_file() else (shutil.which("node") or "node")
        return [node, str(js)]
    return [achado]


def _ambiente(tarefa_id: str) -> dict:
    """O ambiente do Codex: sem segredo, sem cache do pytest, sem .pyc."""
    env = {k: v for k, v in os.environ.items()
           if not re.search(r"TOKEN|SECRET|PASSWORD|SENHA|API_?KEY|CREDENTIAL|COOKIE",
                            k, re.I)}
    env["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NF_DELEGADO"] = validar_id(tarefa_id)
    return env


def modelos_codex() -> dict:
    """{"modelos": [...], "fonte": ..., "padrao": {modelo, esforco}}. Nunca levanta."""
    saida = {"modelos": [], "fonte": "", "padrao": padrao_do_codex()}
    try:
        dados = json.loads((codex_home() / "models_cache.json").read_text(encoding="utf-8"))
        for m in dados.get("models") or []:
            if m.get("visibility") != "list" or not m.get("slug"):
                continue
            saida["modelos"].append({
                "id": m["slug"], "nome": m.get("display_name") or m["slug"],
                "descricao": m.get("description") or "",
                "esforcos": [n.get("effort") for n in m.get("supported_reasoning_levels") or []
                             if n.get("effort")],
                "esforco_padrao": m.get("default_reasoning_level") or ""})
        saida["fonte"] = f"models_cache.json do Codex ({str(dados.get('fetched_at', ''))[:10]})"
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    if not saida["modelos"]:
        saida["modelos"] = [{"id": m, "nome": m, "descricao": "", "esforcos": list(ESFORCOS),
                             "esforco_padrao": ""} for m in MODELOS_DOCUMENTADOS]
        saida["fonte"] = "lista medida em 01/10/2026 (sem o models_cache.json)"
    return saida


def padrao_do_codex() -> dict:
    """O modelo e o esforco do `~/.codex/config.toml` (so leitura)."""
    try:
        import tomllib
        with open(codex_home() / "config.toml", "rb") as fh:
            dados = tomllib.load(fh)
        return {"modelo": str(dados.get("model") or ""),
                "esforco": str(dados.get("model_reasoning_effort") or "")}
    except Exception:                                        # noqa: BLE001
        return {"modelo": "", "esforco": ""}


def validar_modelo(modelo) -> str | None:
    """None = o padrao do config.toml do Codex. Senao, um nome valido."""
    if modelo in (None, ""):
        return None
    modelo = str(modelo).strip().lower()
    if not _MODELO_LIVRE.fullmatch(modelo):
        raise Recusa("modelo do Codex: letras minúsculas, números, ponto e hífen")
    return modelo


# ===================================================================== uso
def _cauda(caminho: Path, nbytes: int = 262_144) -> list[str]:
    with open(caminho, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        tamanho = fh.tell()
        fh.seek(max(0, tamanho - nbytes))
        bruto = fh.read()
    linhas = bruto.decode("utf-8", errors="replace").splitlines()
    return linhas[1:] if tamanho > nbytes else linhas


def _hora_local(iso) -> str | None:
    """O `timestamp` do rollout vem em UTC ("...Z"); a tela fala a hora do PC."""
    try:
        quando = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if quando.tzinfo is not None:
        quando = quando.astimezone().replace(tzinfo=None)
    return quando.isoformat(timespec="seconds")


def uso_codex(agora: float | None = None, *, rollout: Path | None = None) -> dict:
    """A janela de 5 h do Codex, pelo ultimo `token_count` com `rate_limits`.

    O `codex exec --json` nao traz o uso; o rollout que ele grava em
    `~/.codex/sessions/AAAA/MM/DD/` traz (medido em 01/10: 16% as 15:24, 36%
    as 16:24, plano "plus"). Janela que ja renovou depois da medicao = 0%.
    Nunca levanta: sem medicao, `situacao: "desconhecido"`.
    """
    agora = time.time() if agora is None else agora
    vazio = {"situacao": "desconhecido", "pct": None, "janela_min": None,
             "renova_em": None, "semana_pct": None, "semana_renova_em": None,
             "medido_em": None, "plano": None, "fonte": None}
    try:
        if rollout is not None:
            arquivos = [rollout]
        else:
            base = codex_home() / "sessions"
            arquivos = sorted(base.glob("*/*/*/rollout-*.jsonl"),
                              key=lambda p: p.stat().st_mtime, reverse=True)[:6]
    except OSError:
        return vazio
    for arquivo in arquivos:
        try:
            linhas = _cauda(arquivo)
        except OSError:
            continue
        for bruta in reversed(linhas):
            if '"rate_limits"' not in bruta:
                continue
            try:
                ev = json.loads(bruta)
                limites = (ev.get("payload") or {}).get("rate_limits") or {}
                primario = limites.get("primary") or {}
                pct = float(primario["used_percent"])
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            segundo = limites.get("secondary") or {}
            renova = primario.get("resets_at")
            saida = {**vazio, "situacao": "medido", "pct": pct,
                     "janela_min": primario.get("window_minutes"), "renova_em": renova,
                     "semana_pct": segundo.get("used_percent"),
                     "semana_renova_em": segundo.get("resets_at"),
                     "medido_em": _hora_local(ev.get("timestamp")),
                     "plano": limites.get("plan_type"), "fonte": arquivo.name}
            if isinstance(renova, (int, float)) and renova <= agora:
                saida["situacao"], saida["pct"] = "renovou", 0.0
            return saida
    return vazio


def tokens_na_janela(agora: float | None = None, janela_s: float = 5 * 3600) -> int:
    """Tokens que os delegados gastaram nas ultimas 5 h (o teto de reserva)."""
    agora = time.time() if agora is None else agora
    total = 0
    for estado in listar():
        for rodada in estado.get("rodadas") or []:
            try:
                inicio = datetime.fromisoformat(rodada.get("inicio")).timestamp()
            except (TypeError, ValueError):
                continue
            if agora - inicio <= janela_s:
                t = rodada.get("tokens") or {}
                total += int(t.get("entrada", 0)) + int(t.get("saida", 0))
    return total


def conferir_teto(config: dict, agora: float | None = None) -> dict:
    """O uso, e Recusa se passou do teto (ou se nao da para saber)."""
    uso = uso_codex(agora)
    teto = config["teto_codex_pct"]
    if uso["pct"] is not None:
        if uso["pct"] >= teto:
            raise Recusa(f"o Codex está em {uso['pct']:.0f}% da janela de 5 h "
                         f"(teto {teto}%, decisão geral/teto-dos-delegados)")
        return uso
    maximo = config.get("tokens_janela_max")
    if maximo:
        gasto = tokens_na_janela(agora)
        if gasto >= int(maximo):
            raise Recusa(f"os delegados gastaram {gasto} tokens nas últimas 5 h "
                         f"(teto por contagem: {maximo})")
        return {**uso, "situacao": "contagem", "tokens_janela": gasto}
    raise Recusa("não consegui ler o uso do Codex (nenhum rollout com rate_limits em "
                 "~/.codex/sessions); ponha tokens_janela_max no config.json dos "
                 "delegados, ou use --forcar só se o Adrian mandou")


# ============================================================== eventos
def _limpar_comando(cmd) -> str:
    """O comando que ele digitou, sem o `powershell.exe -NoProfile -Command '...'`."""
    if isinstance(cmd, list):
        cmd = cmd[-1] if cmd else ""
    texto = str(cmd or "")
    achado = re.search(r"-(?:Command|c|lc)\s+(['\"])(.*)\1\s*$", texto, re.S)
    if achado:
        texto = achado.group(2)
        if achado.group(1) == "'":
            texto = texto.replace("''", "'")
    return texto.strip()


def _tipo_do_comando(cmd: str) -> str:
    primeiro = (cmd.split() or [""])[0].lower().strip("&'\"")
    if re.search(r"\bpytest\b|testar\.py|\bunittest\b", cmd):
        return "testa"
    if primeiro in LEITURA or (primeiro == "git" and re.match(
            r"git\s+(show|diff|log|status|grep|ls-files|blame)\b", cmd)):
        return "le"
    return "roda"


def _cortar(texto, limite: int) -> str:
    texto = str(texto or "")
    return texto if len(texto) <= limite else texto[:limite] + "…"


def resumir(linha: dict) -> dict:
    """Um evento gravado como a Oficina mostra: {n, em, tipo, texto, detalhe, ok}."""
    ev = linha.get("ev") if isinstance(linha.get("ev"), dict) else {}
    base = {"n": linha.get("n"), "em": linha.get("em"), "tipo": "outro",
            "texto": "", "detalhe": "", "ok": None}
    tipo = str(ev.get("type") or "")
    item = ev.get("item") if isinstance(ev.get("item"), dict) else {}
    qual = re.sub(r"[^a-z]", "", str(item.get("type") or "").lower())
    if tipo.startswith("delegar."):
        return {**base, "tipo": "despachante", "texto": _cortar(ev.get("texto"), 600),
                "ok": ev.get("ok")}
    if tipo == "thread.started":
        return {**base, "tipo": "sessao", "texto": "sessão do Codex começou"}
    if tipo == "turn.started":
        return {**base, "tipo": "sessao", "texto": "pensando…"}
    if tipo == "turn.completed":
        u = ev.get("usage") or {}
        return {**base, "tipo": "sessao", "ok": True,
                "texto": f"rodada terminou · {u.get('input_tokens', 0)} tokens de entrada "
                         f"({u.get('cached_input_tokens', 0)} do cache), "
                         f"{u.get('output_tokens', 0)} de saída"}
    if tipo in ("turn.failed", "error"):
        erro = ev.get("error") if isinstance(ev.get("error"), dict) else {}
        return {**base, "tipo": "erro", "ok": False,
                "texto": _cortar(erro.get("message") or ev.get("message") or tipo, 600)}
    if tipo.startswith("item."):
        fase = tipo.split(".", 1)[1]
        if qual == "commandexecution":
            cmd = _limpar_comando(item.get("command"))
            jeito = _tipo_do_comando(cmd)
            if fase == "started":
                return {**base, "tipo": jeito, "texto": _cortar(cmd, 400)}
            codigo = item.get("exit_code")
            return {**base, "tipo": jeito, "ok": codigo == 0,
                    "texto": _cortar(cmd, 400) + (f"  → código {codigo}"
                                                  if codigo not in (None, 0) else ""),
                    "detalhe": _cortar(str(item.get("aggregated_output") or "")[-1500:], 1600)}
        if qual == "agentmessage":
            return {**base, "tipo": "mensagem", "texto": _cortar(item.get("text"), 4000)}
        if qual == "reasoning":
            return {**base, "tipo": "pensa", "texto": _cortar(item.get("text"), 1500)}
        if qual == "filechange":
            mudancas = [f"{c.get('kind', '?')} {c.get('path', '?')}"
                        for c in item.get("changes") or [] if isinstance(c, dict)]
            return {**base, "tipo": "muda", "ok": item.get("status") != "failed",
                    "texto": _cortar("; ".join(mudancas) or "arquivos", 800)}
        if qual == "todolist":
            linhas = [("☑ " if t.get("completed") else "☐ ") + str(t.get("text", ""))
                      for t in item.get("items") or [] if isinstance(t, dict)]
            return {**base, "tipo": "plano", "texto": _cortar("\n".join(linhas), 1500)}
        if qual == "websearch":
            return {**base, "tipo": "le", "texto": "busca: " + _cortar(item.get("query"), 300)}
        if qual == "mcptoolcall":
            return {**base, "tipo": "roda",
                    "texto": f"ferramenta {item.get('server', '')}.{item.get('tool', '')}"}
        if qual == "error":
            return {**base, "tipo": "erro", "ok": False,
                    "texto": _cortar(item.get("message"), 600)}
        if fase == "started":
            return {**base, "texto": f"{qual or 'item'} começou"}
        return {**base, "texto": qual or tipo}
    if tipo == "texto":
        return {**base, "texto": _cortar(ev.get("texto"), 600)}
    return {**base, "texto": tipo or "evento"}


def ler_eventos(tarefa_id: str, desde: int = -1, maximo_bytes: int = 393_216) -> dict:
    """Os eventos novos desde o byte `desde` (so linhas inteiras).

    `desde` < 0: os ultimos (a cauda), para a primeira carga da tela. Leitura
    por offset: a tela pede de 3 em 3 s sem reler o arquivo inteiro, e o
    servidor nunca le mais que `maximo_bytes` por pedido.
    """
    caminho = pasta_da(tarefa_id) / "eventos.jsonl"
    try:
        tamanho = caminho.stat().st_size
    except FileNotFoundError:
        return {"eventos": [], "offset": 0, "tamanho": 0, "mais": False}
    inicio = max(0, tamanho - maximo_bytes) if desde < 0 else min(int(desde), tamanho)
    if desde >= 0 and desde > tamanho:
        inicio = 0
    with open(caminho, "rb") as fh:
        fh.seek(inicio)
        bruto = fh.read(maximo_bytes)
    fim_util = bruto.rfind(b"\n") + 1
    pedaco = bruto[:fim_util]
    if desde < 0 and inicio > 0:
        corte = pedaco.find(b"\n") + 1            # a primeira linha veio pela metade
        pedaco, inicio = pedaco[corte:], inicio + corte
    eventos = []
    for bruta in pedaco.decode("utf-8", errors="replace").splitlines():
        if not bruta.strip():
            continue
        try:
            linha = json.loads(bruta)
        except ValueError:
            eventos.append({"n": None, "em": None, "tipo": "erro", "ok": False,
                            "texto": "linha ilegível no eventos.jsonl", "detalhe": ""})
            continue
        if isinstance(linha, dict):
            eventos.append(resumir(linha))
    offset = inicio + len(pedaco)
    return {"eventos": eventos, "offset": offset, "tamanho": tamanho,
            "mais": offset < tamanho}


# ================================================================= criar
def compor_prompt(tarefa: str, permitidos: list[str]) -> str:
    try:
        regras = PROMPT_PADRAO.read_text(encoding="utf-8")
    except OSError:
        regras = ""
    lista = "\n".join(f"- `{p}`" for p in permitidos)
    return (f"{regras.strip()}\n\n# A tarefa\n\n{tarefa.strip()}\n\n"
            f"# Caminhos permitidos\n\n{lista}\n")


def _validar_permitidos(permitidos) -> list[str]:
    saida = []
    for p in permitidos or []:
        p = re.sub(r"^(\./)+", "", str(p or "").strip().replace("\\", "/"))
        if not p or ".." in p.split("/") or ":" in p or p.startswith("/"):
            raise Recusa(f"caminho permitido inválido: {p!r}")
        if p not in saida:
            saida.append(p)
    if not saida:
        raise Recusa("diga os caminhos que ele pode mexer (--permitido \"remoto/**\")")
    return saida


def criar(tarefa_id: str, arquivo_tarefa: Path, permitidos, *, modelo=None,
          esforco: str | None = None, titulo: str = "") -> dict:
    tarefa_id = validar_id(tarefa_id)
    permitidos = _validar_permitidos(permitidos)
    modelo = validar_modelo(modelo) if modelo is not None else modelo_configurado()
    if esforco is not None and esforco not in ESFORCOS:
        raise Recusa(f"esforço é {', '.join(ESFORCOS)}")
    try:
        bruto = Path(arquivo_tarefa).read_bytes()
    except OSError as exc:
        raise Recusa(f"não li a tarefa: {exc}") from exc
    if not bruto.strip() or len(bruto) > TAREFA_MAX:
        raise Recusa("a tarefa está vazia ou passa de 100 KB")
    tarefa = bruto.decode("utf-8-sig", errors="replace")
    destino = pasta_da(tarefa_id)
    wt = worktree_de(tarefa_id)
    with _trava():
        if (destino / "estado.json").exists():
            raise Recusa(f"a tarefa {tarefa_id} já existe")
        if wt.exists():
            raise Recusa(f"a pasta {wt} já existe (limpe antes: limpar --orfas)")
        base = _git("rev-parse", "HEAD").stdout.strip()
        _git("worktree", "add", str(wt), "-b", branch_de(tarefa_id), base)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "tarefa.md").write_text(tarefa, encoding="utf-8")
        (wt / ".codex_tarefa.md").write_text(compor_prompt(tarefa, permitidos),
                                             encoding="utf-8")
        primeira = next((l.strip("# ").strip() for l in tarefa.splitlines() if l.strip()), "")
        estado = {"id": tarefa_id, "ia": IA, "situacao": "criado", "criado_em": _agora_iso(),
                  "titulo": _cortar(titulo or primeira, 160), "modelo": modelo,
                  "esforco": esforco, "worktree": str(wt), "branch": branch_de(tarefa_id),
                  "base": base, "permitidos": permitidos, "thread_id": None, "pid": None,
                  "pid_codex": None, "inicio": None, "fim": None, "motivo": "",
                  "tokens": {"entrada": 0, "cache": 0, "saida": 0, "raciocinio": 0},
                  "rodadas": [], "eventos_n": 0, "diff": None, "testes": None,
                  "aplicado": None, "limpo": None}
        _gravar_estado(estado)
    _log(tarefa_id, f"criada: worktree {wt} (base {base[:8]}), modelo {modelo or 'padrão'}")
    return estado


def modelo_configurado() -> str | None:
    """O `modelo_codex` da Mesa (config.json do orquestrador); None = padrao."""
    try:
        from . import orquestrador
        return orquestrador.ler_config().get("modelo_codex") or None
    except Exception:                                        # noqa: BLE001
        return None


# ================================================================= rodar
def _pid_vivo(pid) -> bool | None:
    try:
        from .orquestrador import _pid_vivo as vivo
        return vivo(pid)
    except Exception:                                        # noqa: BLE001
        return None


def _rodando(estado: dict) -> bool:
    return estado.get("situacao") == "rodando" and _pid_vivo(estado.get("pid")) is not False


def _janela(minutos, agora: datetime) -> bool:
    try:
        de, ate = int(minutos[0]), int(minutos[1])
    except (TypeError, ValueError, IndexError):
        return False
    return de <= agora.minute < ate


def _matar(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                       creationflags=NO_WINDOW)
    try:
        proc.kill()
    except OSError:
        pass


def _preparar_rodada(tarefa_id: str, tipo: str, forcar: bool) -> tuple[dict, dict]:
    """As guardas, e marca `rodando` (sob a trava: um delegado por vez)."""
    motivo = claude_estado.motivo_proibido()
    if motivo:
        raise Recusa(motivo + " (vale para o Codex também)")
    config = ler_config()
    agora = _agora()
    if _janela(config["janela_sem_comecar"], agora) and not forcar:
        de, ate = config["janela_sem_comecar"]
        raise Recusa(f"nada começa entre :{de:02d} e :{ate:02d} (agora {agora:%H:%M})")
    uso = uso_codex()
    if not forcar:
        uso = conferir_teto(config)
    with _trava():
        estado = ler_estado(tarefa_id)
        if estado.get("limpo"):
            raise Recusa(f"a tarefa {tarefa_id} já foi limpa")
        if _rodando(estado):
            raise Recusa(f"a tarefa {tarefa_id} já está rodando (pid {estado.get('pid')})")
        if tipo == "corrigir" and not estado.get("thread_id"):
            raise Recusa("não há conversa para corrigir: rode primeiro")
        outro = next((e for e in listar() if e.get("id") != tarefa_id and _rodando(e)), None)
        if outro:
            raise Recusa(f"um delegado por vez: {outro['id']} está rodando")
        if not Path(estado["worktree"]).is_dir():
            raise Recusa(f"a worktree sumiu: {estado['worktree']}")
        estado.update(situacao="rodando", pid=os.getpid(), pid_codex=None,
                      inicio=_agora_iso(), fim=None, motivo="")
        estado["rodadas"] = list(estado.get("rodadas") or []) + [
            {"tipo": tipo, "inicio": estado["inicio"], "fim": None, "codigo": None,
             "tokens": {"entrada": 0, "cache": 0, "saida": 0, "raciocinio": 0},
             "uso_antes": uso.get("pct")}]
        _gravar_estado(estado)
    return estado, config


class _Rodada:
    """Um `codex exec` (ou `resume`) com os eventos indo para o disco ao vivo."""

    def __init__(self, estado: dict, config: dict, args: list[str], prompt: str):
        self.id = estado["id"]
        self.estado = estado
        self.config = config
        self.args = args
        self.prompt = prompt
        self.n = int(estado.get("eventos_n") or 0)
        self.motivo_parada = ""
        self.proc: subprocess.Popen | None = None
        self.fim = threading.Event()
        self.trava_ev = threading.Lock()
        self.eventos = open(pasta_da(self.id) / "eventos.jsonl", "a", encoding="utf-8")

    def anotar(self, ev: dict) -> None:
        with self.trava_ev:
            if self.eventos.closed:
                self.eventos = open(pasta_da(self.id) / "eventos.jsonl", "a",
                                    encoding="utf-8")
            self.n += 1
            self.eventos.write(json.dumps({"n": self.n, "em": _agora_iso(), "ev": ev},
                                          ensure_ascii=False) + "\n")
            self.eventos.flush()

    def parar(self, motivo: str) -> None:
        if self.motivo_parada:
            return
        self.motivo_parada = motivo
        self.anotar({"type": "delegar.parado", "texto": f"parei o Codex: {motivo}",
                     "ok": False})
        _log(self.id, f"parei o Codex: {motivo}")
        if self.proc is not None:
            _matar(self.proc)

    def guarda(self) -> None:
        """Interruptor a cada 2 s, teto a cada 30 s, prazo e o pedido de parar."""
        limite = time.monotonic() + float(self.config["rodar_timeout_s"])
        proximo_teto = time.monotonic() + TETO_A_CADA_S
        teto = self.config["teto_codex_pct"]
        while not self.fim.wait(GUARDA_S):
            motivo = claude_estado.motivo_proibido()
            if motivo:
                self.parar(motivo)
                return
            if (pasta_da(self.id) / "parar.pedido").exists():
                self.parar("pedido de parar (delegar parar)")
                return
            if time.monotonic() > limite:
                self.parar(f"passou de {self.config['rodar_timeout_s']} s")
                return
            if time.monotonic() > proximo_teto:
                proximo_teto = time.monotonic() + TETO_A_CADA_S
                uso = uso_codex()
                if uso["pct"] is not None and uso["pct"] >= teto:
                    self.parar(f"o Codex passou do teto: {uso['pct']:.0f}% da janela "
                               f"de 5 h (teto {teto}%)")
                    return

    def contar(self, ev: dict) -> None:
        tipo = ev.get("type")
        if tipo == "thread.started" and ev.get("thread_id"):
            self.estado["thread_id"] = str(ev["thread_id"])[:80]
            _mudar_estado(self.id, thread_id=self.estado["thread_id"])
        elif tipo == "turn.completed":
            u = ev.get("usage") or {}
            soma = {"entrada": int(u.get("input_tokens") or 0),
                    "cache": int(u.get("cached_input_tokens") or 0),
                    "saida": int(u.get("output_tokens") or 0),
                    "raciocinio": int(u.get("reasoning_output_tokens") or 0)}
            with _trava():
                estado = ler_estado(self.id)
                total = dict(estado.get("tokens") or {})
                rodada = estado["rodadas"][-1]
                for k, v in soma.items():
                    total[k] = int(total.get(k, 0)) + v
                    rodada["tokens"][k] = int(rodada["tokens"].get(k, 0)) + v
                estado["tokens"], estado["eventos_n"] = total, self.n
                _gravar_estado(estado)

    def rodar(self) -> int:
        _log(self.id, "codex: " + " ".join(a if " " not in a else repr(a)
                                           for a in self.args[-12:]))
        erro = open(pasta_da(self.id) / "codex_stderr.log", "ab")
        try:
            self.proc = subprocess.Popen(
                self.args, cwd=self.estado["worktree"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=erro, env=_ambiente(self.id),
                creationflags=NO_WINDOW)
        except OSError as exc:
            erro.close()
            self.anotar({"type": "delegar.erro", "texto": f"o codex não abriu: {exc}",
                         "ok": False})
            return 127
        _mudar_estado(self.id, pid_codex=self.proc.pid)
        self.anotar({"type": "delegar.inicio", "ok": True,
                     "texto": f"Codex {self.estado.get('modelo') or 'modelo padrão'} começou "
                              f"(pid {self.proc.pid})"})
        vigia = threading.Thread(target=self.guarda, daemon=True)
        vigia.start()
        try:
            try:
                self.proc.stdin.write(self.prompt.encode("utf-8"))
                self.proc.stdin.close()
            except OSError:
                pass
            for bruta in self.proc.stdout:
                texto = bruta.decode("utf-8", errors="replace").strip()
                if not texto:
                    continue
                try:
                    ev = json.loads(texto)
                    if not isinstance(ev, dict):
                        raise ValueError
                except ValueError:
                    ev = {"type": "texto", "texto": texto[:2000]}
                self.anotar(ev)
                try:
                    self.contar(ev)
                except Recusa:
                    pass
            codigo = self.proc.wait()
        finally:
            self.fim.set()
            erro.close()
            with self.trava_ev:
                self.eventos.close()
        return codigo


def _rodada(tarefa_id: str, tipo: str, prompt: str, *, forcar: bool = False) -> dict:
    estado, config = _preparar_rodada(tarefa_id, tipo, forcar)
    wt = Path(estado["worktree"])
    resposta = pasta_da(tarefa_id) / "resposta.md"
    base = comando_codex() + ["exec"]
    modelo = ["-m", estado["modelo"]] if estado.get("modelo") else []
    esforco = (["-c", f'model_reasoning_effort="{estado["esforco"]}"']
               if estado.get("esforco") else [])
    if tipo == "rodar":
        args = base + ["--json", "--sandbox", "workspace-write", "-C", str(wt), "-o",
                       str(resposta), *modelo, *esforco, "-"]
    else:
        # `resume` NAO aceita --sandbox (medido em 01/10): vai por -c
        args = base + ["resume", estado["thread_id"], "--json", "-o", str(resposta),
                       "-c", 'sandbox_mode="workspace-write"', *modelo, *esforco, "-"]
    rodada = _Rodada(estado, config, args, prompt)
    codigo = -1
    try:
        codigo = rodada.rodar()
    except BaseException as exc:                             # Ctrl+C, erro de leitura
        # Publicacao (aqui: rodada) que nao terminou tem de aparecer, nunca
        # sumir: o estado sai de "rodando" com o motivo, e o Codex morre.
        rodada.parar(f"o despachante caiu ({type(exc).__name__}: {_cortar(exc, 120)})")
        _encerrar(tarefa_id, rodada, codigo)
        if not isinstance(exc, Exception):
            raise
        return ler_estado(tarefa_id)
    _encerrar(tarefa_id, rodada, codigo)
    return ler_estado(tarefa_id)


def _encerrar(tarefa_id: str, rodada: _Rodada, codigo) -> None:
    if rodada.motivo_parada:
        situacao, motivo = "parado", rodada.motivo_parada
    elif codigo == 0:
        situacao, motivo = "terminou", ""
    else:
        situacao, motivo = "falhou", f"o codex saiu com o código {codigo}"
    with _trava():
        estado = ler_estado(tarefa_id)
        estado.update(situacao=situacao, motivo=motivo, fim=_agora_iso(), pid=None,
                      pid_codex=None, eventos_n=rodada.n)
        if estado.get("rodadas"):
            estado["rodadas"][-1].update(fim=estado["fim"], codigo=codigo,
                                         situacao=situacao)
        _gravar_estado(estado)
    try:
        (pasta_da(tarefa_id) / "parar.pedido").unlink()
    except OSError:
        pass
    texto = {"terminou": "o Codex terminou", "falhou": "o Codex falhou: " + motivo,
             "parado": "parado: " + motivo}[situacao]
    with open(pasta_da(tarefa_id) / "eventos.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"n": rodada.n + 1, "em": _agora_iso(),
                             "ev": {"type": "delegar.fim", "texto": texto,
                                    "ok": situacao == "terminou"}},
                            ensure_ascii=False) + "\n")
    _mudar_estado(tarefa_id, eventos_n=rodada.n + 1)
    _log(tarefa_id, texto)
    try:
        coletar(tarefa_id)
    except Recusa as exc:
        _log(tarefa_id, f"diff: {exc}")


def rodar(tarefa_id: str, *, forcar: bool = False) -> dict:
    wt = worktree_de(tarefa_id)
    try:
        tarefa = (wt / ".codex_tarefa.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise Recusa(f"a tarefa não está na worktree: {exc}") from exc
    return _rodada(tarefa_id, "rodar", tarefa, forcar=forcar)


def corrigir(tarefa_id: str, arquivo_texto: Path, *, forcar: bool = False) -> dict:
    try:
        texto = Path(arquivo_texto).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise Recusa(f"não li a correção: {exc}") from exc
    if not texto.strip() or len(texto.encode("utf-8")) > TAREFA_MAX:
        raise Recusa("a correção está vazia ou passa de 100 KB")
    destino = pasta_da(tarefa_id)
    n = len([p for p in destino.glob("correcao_*.md")]) + 1
    (destino / f"correcao_{n}.md").write_text(texto, encoding="utf-8")
    return _rodada(tarefa_id, "corrigir", texto, forcar=forcar)


def parar(tarefa_id: str) -> str:
    """Pede para o despachante que roda aquela tarefa parar o Codex."""
    estado = ler_estado(tarefa_id)
    if not _rodando(estado):
        raise Recusa(f"a tarefa {tarefa_id} não está rodando")
    (pasta_da(tarefa_id) / "parar.pedido").write_text(_agora_iso(), encoding="utf-8")
    return f"pedido de parar gravado; o despachante (pid {estado.get('pid')}) para em ~2 s"


def no_fundo(argv: list[str], tarefa_id: str) -> int:
    """O mesmo comando em processo desligado (sobrevive a quem chamou)."""
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | NO_WINDOW)
    saida = open(pasta_da(tarefa_id) / "fundo.txt", "ab")
    args = [sys.executable, "-m", "remoto.delegar", *argv]
    for extra in (getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0), 0):
        try:
            proc = subprocess.Popen(args, cwd=str(RAIZ), stdout=saida, stderr=saida,
                                    stdin=subprocess.DEVNULL, creationflags=flags | extra)
            return proc.pid
        except OSError:
            continue
    raise Recusa("não consegui abrir o despachante em segundo plano")


# ================================================================== diff
def _casa(caminho: str, padrao: str) -> bool:
    if padrao.endswith("/**"):
        return caminho == padrao[:-3] or caminho.startswith(padrao[:-2])
    if "/" not in padrao and not padrao.startswith("**"):
        return fnmatch.fnmatchcase(caminho.rsplit("/", 1)[-1], padrao) or \
            fnmatch.fnmatchcase(caminho, padrao)
    return fnmatch.fnmatchcase(caminho, padrao.replace("**/", "*"))


def validar_diff(arquivos: list[dict], permitidos: list[str], config: dict) -> list[str]:
    """Os motivos de recusa (vazio = passa)."""
    motivos = []
    if not arquivos:
        return ["o Codex não mudou nada"]
    for a in arquivos:
        c = a["caminho"]
        if any(_casa(c, p) for p in PROIBIDOS):
            motivos.append(f"caminho proibido: {c}")
        elif not any(_casa(c, p) for p in permitidos):
            motivos.append(f"fora da lista permitida: {c}")
        if a.get("binario"):
            motivos.append(f"arquivo binário: {c}")
    linhas = sum(a["mais"] + a["menos"] for a in arquivos)
    if linhas > int(config["diff_max_linhas"]):
        motivos.append(f"diff grande: {linhas} linhas (máximo {config['diff_max_linhas']})")
    if len(arquivos) > int(config["diff_max_arquivos"]):
        motivos.append(f"arquivos demais: {len(arquivos)} (máximo "
                       f"{config['diff_max_arquivos']})")
    return motivos


def coletar(tarefa_id: str) -> dict:
    """O patch da worktree contra a base, e o validador. Grava diff.patch/json."""
    estado = ler_estado(tarefa_id)
    wt = Path(estado["worktree"])
    if not wt.is_dir():
        raise Recusa(f"a worktree sumiu: {wt}")
    excluir = [f":(exclude){n}" for n in NOSSOS]
    _git("add", "-A", "--", ".", *excluir, cwd=wt)
    numstat = _git("diff", "--cached", "--no-renames", "--numstat", estado["base"],
                   cwd=wt).stdout
    arquivos = []
    for linha in numstat.splitlines():
        partes = linha.split("\t")
        if len(partes) < 3:
            continue
        binario = partes[0] == "-" or partes[1] == "-"
        arquivos.append({"caminho": partes[2].strip().replace("\\", "/"),
                         "mais": 0 if binario else int(partes[0]),
                         "menos": 0 if binario else int(partes[1]),
                         "binario": binario})
    # Em BYTES: com `text=True` o \r\n de um arquivo CRLF viraria \n e o
    # patch nao aplicaria (ou aplicaria trocando o fim de linha do arquivo).
    feito = subprocess.run(["git", "diff", "--cached", "--no-renames", "--binary",
                            estado["base"]], cwd=str(wt), capture_output=True,
                           creationflags=NO_WINDOW)
    if feito.returncode != 0:
        raise Recusa("git diff falhou: " + feito.stderr.decode("utf-8", "replace")[:400])
    patch = feito.stdout
    config = ler_config()
    motivos = validar_diff(arquivos, estado.get("permitidos") or [], config)
    sha = hashlib.sha1(patch).hexdigest()[:12]
    resumo = {"em": _agora_iso(), "sha": sha, "arquivos": arquivos,
              "linhas": sum(a["mais"] + a["menos"] for a in arquivos),
              "ok": not motivos, "motivos": motivos, "bytes": len(patch)}
    destino = pasta_da(tarefa_id)
    (destino / "diff.patch").write_bytes(patch)
    _gravar_json(destino / "diff.json", resumo)
    _mudar_estado(tarefa_id, diff={k: resumo[k] for k in ("em", "sha", "linhas", "ok",
                                                          "motivos")}
                  | {"arquivos": len(arquivos)})
    return resumo


# ================================================================ testar
def testar(tarefa_id: str, cmd: str, *, timeout_s: float | None = None) -> dict:
    estado = ler_estado(tarefa_id)
    if _rodando(estado):
        raise Recusa("o Codex ainda está rodando nessa worktree")
    cmd = str(cmd or "").strip()
    if not cmd:
        raise Recusa("diga o comando dos testes (--cmd)")
    resumo = coletar(tarefa_id)
    config = ler_config()
    temp = temp_testes() / "delegados" / validar_id(tarefa_id)
    temp.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TEMP": str(temp), "TMP": str(temp),
           "PYTEST_ADDOPTS": f"-p no:cacheprovider --basetemp={temp / 'bt'}"}
    inicio = time.monotonic()
    log = pasta_da(tarefa_id) / "testes.log"
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        fh.write(f"$ {cmd}\n(cwd {estado['worktree']}, TEMP {temp}, diff {resumo['sha']})\n\n")
        fh.flush()
        try:
            feito = subprocess.run(cmd, shell=True, cwd=estado["worktree"], stdout=fh,
                                   stderr=subprocess.STDOUT, env=env, creationflags=NO_WINDOW,
                                   timeout=timeout_s or float(config["testes_timeout_s"]))
            codigo = feito.returncode
        except subprocess.TimeoutExpired:
            codigo = None
            fh.write("\n[estourou o tempo]\n")
    try:
        cauda = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()
                 if l.strip()]
    except OSError:
        cauda = []
    resultado = {"cmd": _cortar(cmd, 400), "codigo": codigo, "ok": codigo == 0,
                 "em": _agora_iso(), "dur_s": round(time.monotonic() - inicio, 1),
                 "diff_sha": resumo["sha"], "resumo": _cortar(cauda[-1] if cauda else "", 300)}
    _mudar_estado(tarefa_id, testes=resultado)
    return resultado


# =============================================================== aplicar
def _processos() -> list[str]:
    """As linhas de comando dos pythons vivos (para achar publicacao em voo)."""
    feito = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\""
         " | ForEach-Object { $_.CommandLine }"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        creationflags=NO_WINDOW)
    if feito.returncode != 0:
        raise Recusa("não consegui ver se há publicação em voo")
    return [l for l in feito.stdout.splitlines() if l.strip()]


def publicacao_em_voo(processos=None) -> list[str]:
    """As linhas de quem esta publicando agora (as mesmas do reiniciar_app.ps1)."""
    linhas = _processos() if processos is None else processos
    return [l for l in linhas if "publicacao_filha" in l or "postar.py" in l
            or (re.search(r"main\.py", l) and re.search(r"\bpublicar\b", l))]


def aplicar(tarefa_id: str, *, sem_testes: bool = False, processos=None) -> dict:
    config = ler_config()
    agora = _agora()
    if _janela(config["janela_sem_aplicar"], agora):
        de, ate = config["janela_sem_aplicar"]
        raise Recusa(f"aplicar só fora de :{de:02d}–:{ate:02d}, a janela da postagem "
                     f"(agora {agora:%H:%M})")
    voando = publicacao_em_voo(processos)
    if voando:
        raise Recusa("publicação em voo: " + _cortar(voando[0], 200))
    estado = ler_estado(tarefa_id)
    if _rodando(estado):
        raise Recusa("o Codex ainda está rodando")
    if estado.get("aplicado"):
        raise Recusa(f"já aplicado em {estado['aplicado'].get('em')}")
    resumo = coletar(tarefa_id)
    if not resumo["ok"]:
        raise Recusa("o diff não passa: " + "; ".join(resumo["motivos"]))
    testes = estado.get("testes") or {}
    if not sem_testes:
        if not testes:
            raise Recusa("rode os testes antes (testar --cmd ...)")
        if testes.get("diff_sha") != resumo["sha"]:
            raise Recusa("o diff mudou depois dos testes: rode de novo")
        if not testes.get("ok"):
            raise Recusa(f"os testes falharam (código {testes.get('codigo')})")
    patch = pasta_da(tarefa_id) / "diff.patch"
    feito = _git("apply", "--check", str(patch), verificar=False)
    if feito.returncode != 0:
        raise Recusa("git apply --check recusou: " + (feito.stderr or feito.stdout).strip()[:400])
    _git("apply", str(patch))
    arquivos = [a["caminho"] for a in resumo["arquivos"]]
    aplicado = {"em": _agora_iso(), "sha": resumo["sha"], "arquivos": arquivos,
                "sem_testes": sem_testes}
    _mudar_estado(tarefa_id, aplicado=aplicado)
    _log(tarefa_id, f"aplicado na árvore principal: {', '.join(arquivos)}")
    return aplicado


# ================================================================ limpar
def _apagar_o_que_der(alvo: Path) -> list[str]:
    presos = []

    def falhou(_funcao, caminho, _exc):
        presos.append(str(caminho))
    if sys.version_info >= (3, 12):
        shutil.rmtree(alvo, onexc=falhou)
    else:                                                    # pragma: no cover
        shutil.rmtree(alvo, onerror=lambda f, c, e: falhou(f, c, e))
    return presos


def _mover_para_o_lixo(alvo: Path, nome: str) -> dict:
    """Apaga o que der; o que sobrar (dono: o sandbox do Codex) vai para o lixo."""
    _apagar_o_que_der(alvo)
    if not alvo.exists():
        return {"sobrou": None}
    lixo = wt_raiz() / "_lixo_codex"
    lixo.mkdir(parents=True, exist_ok=True)
    destino = lixo / f"{nome}-{_agora():%Y%m%d%H%M%S}"
    try:
        os.replace(alvo, destino)
    except OSError:
        destino = alvo
    return {"sobrou": str(destino),
            "como_apagar": (f'como administrador: takeown /F "{destino}" /R /D Y; '
                            f'icacls "{destino}" /grant "%USERNAME%":F /T; '
                            f'rmdir /S /Q "{destino}"')}


def limpar(tarefa_id: str) -> dict:
    estado = ler_estado(tarefa_id)
    if _rodando(estado):
        raise Recusa("o Codex ainda está rodando; pare antes (delegar parar)")
    wt = Path(estado["worktree"])
    saida = {"worktree": str(wt), "sobrou": None}
    feito = _git("worktree", "remove", "--force", str(wt), verificar=False)
    if feito.returncode != 0 or wt.exists():
        saida["git"] = (feito.stderr or feito.stdout).strip()[:300]
        if wt.exists():
            saida.update(_mover_para_o_lixo(wt, wt.name))
        _git("worktree", "prune", verificar=False)
    _git("branch", "-D", estado["branch"], verificar=False)
    _mudar_estado(tarefa_id, limpo={"em": _agora_iso(), **{k: v for k, v in saida.items()
                                                          if k != "worktree"}})
    _log(tarefa_id, "limpa" + (f"; sobrou {saida['sobrou']}" if saida.get("sobrou") else ""))
    return saida


def limpar_orfas() -> list[dict]:
    """As pastas `codex-*` que o git nao conhece mais (as de 01/10, a mao)."""
    registradas = {os.path.normcase(os.path.abspath(l.split(" ", 1)[1].strip()))
                   for l in _git("worktree", "list", "--porcelain").stdout.splitlines()
                   if l.startswith("worktree ")}
    saida = []
    for p in sorted(wt_raiz().glob("codex-*")):
        if not p.is_dir() or os.path.normcase(os.path.abspath(p)) in registradas:
            continue
        saida.append({"pasta": str(p), **_mover_para_o_lixo(p, p.name)})
    return saida


# ============================================================ para o app
def _vivo_para_tela(estado: dict) -> dict:
    """O estado como a Oficina mostra (sem caminho de disco)."""
    situacao = estado.get("situacao")
    if situacao == "rodando" and _pid_vivo(estado.get("pid")) is False:
        situacao = "sumiu"
    eventos = pasta_da(estado["id"]) / "eventos.jsonl" if _ID.fullmatch(
        str(estado.get("id") or "")) else None
    try:
        mexido = datetime.fromtimestamp(eventos.stat().st_mtime).isoformat(
            timespec="seconds") if eventos else None
    except OSError:
        mexido = None
    return {"id": estado.get("id"), "ia": estado.get("ia", IA), "situacao": situacao,
            "titulo": estado.get("titulo", ""), "modelo": estado.get("modelo"),
            "esforco": estado.get("esforco"), "criado_em": estado.get("criado_em"),
            "inicio": estado.get("inicio"), "fim": estado.get("fim"),
            "motivo": estado.get("motivo", ""), "tokens": estado.get("tokens") or {},
            "rodadas": len(estado.get("rodadas") or []), "diff": estado.get("diff"),
            "testes": estado.get("testes"), "aplicado": estado.get("aplicado"),
            "limpo": bool(estado.get("limpo")), "ultimo_evento_em": mexido,
            "permitidos": estado.get("permitidos") or [], "erro": estado.get("erro")}


def para_o_app(n: int = 30) -> dict:
    erros = []
    try:
        config = ler_config()
    except Recusa as exc:
        erros.append(str(exc))
        config = dict(PADRAO_CONFIG)
    lista = [_vivo_para_tela(e) for e in listar()[:n]]
    return {"delegados": lista, "uso": uso_codex(), "config": config,
            "rodando": sum(1 for d in lista if d["situacao"] == "rodando"),
            "claude": claude_estado.ler().get("liberado"), "erros": erros}


def detalhe_para_o_app(tarefa_id: str, desde: int = -1, completo: bool = False) -> dict | None:
    """A tarefa e os eventos novos. O pesado (pedido, resposta, diff, testes)
    so vai na primeira carga (`desde` < 0) ou com `completo`: a tela pede de
    3 em 3 s e nao pode receber 200 KB de diff a cada vez."""
    try:
        estado = ler_estado(tarefa_id)
    except Recusa:
        return None
    destino = pasta_da(tarefa_id)
    saida = {"tarefa": _vivo_para_tela(estado), **ler_eventos(tarefa_id, desde)}
    if desde < 0 or completo:
        def ler(nome, limite):
            try:
                texto = (destino / nome).read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
            return texto if len(texto) <= limite else texto[:limite] + "\n…(cortado)"
        saida["pedido"] = ler("tarefa.md", 20_000)
        saida["resposta"] = ler("resposta.md", 20_000)
        saida["diff_texto"] = ler("diff.patch", 200_000)
        saida["diff_arquivos"] = (_ler_json(destino / "diff.json", {}) or {}).get("arquivos")
        log = ler("testes.log", 400_000)
        saida["testes_cauda"] = "\n".join(log.splitlines()[-40:]) if log else None
    return saida


# =================================================================== CLI
def _imprimir(estado: dict) -> None:
    t = estado.get("tokens") or {}
    print(f"{estado['id']}  {estado.get('situacao')}  modelo {estado.get('modelo') or 'padrão'}"
          f"  tokens in {t.get('entrada', 0)} (cache {t.get('cache', 0)}) out {t.get('saida', 0)}")
    print(f"  {estado.get('titulo', '')}")
    for chave in ("inicio", "fim", "motivo", "thread_id", "worktree"):
        if estado.get(chave):
            print(f"  {chave}: {estado[chave]}")
    if estado.get("diff"):
        d = estado["diff"]
        print(f"  diff {d.get('sha')}: {d.get('arquivos')} arquivo(s), {d.get('linhas')} linhas, "
              + ("passa" if d.get("ok") else "RECUSADO: " + "; ".join(d.get("motivos") or [])))
    if estado.get("testes"):
        x = estado["testes"]
        print(f"  testes: {'ok' if x.get('ok') else 'FALHARAM'} (código {x.get('codigo')}, "
              f"{x.get('dur_s')} s) {x.get('resumo', '')}")
    if estado.get("aplicado"):
        print(f"  aplicado {estado['aplicado'].get('em')}: "
              + " ".join(estado["aplicado"].get("arquivos") or []))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="python -m remoto.delegar",
                                description="Tarefas de código delegadas ao Codex.")
    sub = p.add_subparsers(dest="acao", required=True)
    c = sub.add_parser("criar")
    c.add_argument("--id", required=True)
    c.add_argument("--tarefa", required=True)
    c.add_argument("--permitido", action="append", default=[])
    c.add_argument("--modelo")
    c.add_argument("--esforco", choices=ESFORCOS)
    c.add_argument("--titulo", default="")
    for nome in ("rodar", "corrigir"):
        r = sub.add_parser(nome)
        r.add_argument("--id", required=True)
        r.add_argument("--fundo", action="store_true")
        r.add_argument("--forcar", action="store_true",
                       help="passa por cima do horário e do teto (só se o Adrian mandou)")
        if nome == "corrigir":
            r.add_argument("--texto", required=True)
    for nome in ("diff", "ver", "parar"):
        sub.add_parser(nome).add_argument("--id", required=True)
    t = sub.add_parser("testar")
    t.add_argument("--id", required=True)
    t.add_argument("--cmd", required=True)
    a = sub.add_parser("aplicar")
    a.add_argument("--id", required=True)
    a.add_argument("--sem-testes", action="store_true")
    li = sub.add_parser("limpar")
    li.add_argument("--id")
    li.add_argument("--orfas", action="store_true")
    for nome in ("listar", "uso", "modelos", "onde"):
        sub.add_parser(nome)
    args = p.parse_args(argv)
    try:
        if args.acao == "criar":
            _imprimir(criar(args.id, Path(args.tarefa), args.permitido, modelo=args.modelo,
                            esforco=args.esforco, titulo=args.titulo))
        elif args.acao in ("rodar", "corrigir"):
            if args.fundo:
                resto = [x for x in argv if x != "--fundo"]
                print(f"despachante no fundo: pid {no_fundo(resto, validar_id(args.id))}")
            elif args.acao == "rodar":
                _imprimir(rodar(args.id, forcar=args.forcar))
            else:
                _imprimir(corrigir(args.id, Path(args.texto), forcar=args.forcar))
        elif args.acao == "diff":
            r = coletar(args.id)
            print(f"diff {r['sha']}: {len(r['arquivos'])} arquivo(s), {r['linhas']} linhas")
            for x in r["arquivos"]:
                conta = "BIN" if x["binario"] else "+{} -{}".format(x["mais"], x["menos"])
                print(f"  {conta}  {x['caminho']}")
            print("passa" if r["ok"] else "RECUSADO: " + "; ".join(r["motivos"]))
            print(f"patch: {pasta_da(args.id) / 'diff.patch'}")
            return 0 if r["ok"] else 4
        elif args.acao == "testar":
            r = testar(args.id, args.cmd)
            print(f"testes {'ok' if r['ok'] else 'FALHARAM'} (código {r['codigo']}, "
                  f"{r['dur_s']} s): {r['resumo']}")
            return 0 if r["ok"] else 5
        elif args.acao == "aplicar":
            r = aplicar(args.id, sem_testes=args.sem_testes)
            print("aplicado. Commite por caminho: git commit -- " + " ".join(r["arquivos"]))
        elif args.acao == "limpar":
            if args.orfas:
                for r in limpar_orfas():
                    print(f"{r['pasta']}: " + (f"sobrou {r['sobrou']} ({r['como_apagar']})"
                                               if r.get("sobrou") else "apagada"))
            elif args.id:
                r = limpar(args.id)
                print(f"limpa: {r['worktree']}"
                      + (f"\nsobrou {r['sobrou']}\n{r['como_apagar']}" if r.get("sobrou")
                         else ""))
            else:
                raise Recusa("diga --id X ou --orfas")
        elif args.acao == "parar":
            print(parar(args.id))
        elif args.acao == "ver":
            _imprimir(ler_estado(args.id))
        elif args.acao == "listar":
            lista = listar()
            if not lista:
                print("nenhuma tarefa delegada")
            for e in lista:
                _imprimir(e)
        elif args.acao == "uso":
            u = uso_codex()
            print(json.dumps(u, ensure_ascii=False, indent=1))
        elif args.acao == "modelos":
            m = modelos_codex()
            print(f"fonte: {m['fonte']}; padrão do config.toml: {m['padrao']}")
            for x in m["modelos"]:
                print(f"  {x['id']:16} {x['descricao']}")
        elif args.acao == "onde":
            print(f"estado: {pasta()}\nworktrees: {wt_raiz()}\nrepo: {repo()}\n"
                  f"codex home: {codex_home()}")
    except Recusa as exc:
        print(f"recusado: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
