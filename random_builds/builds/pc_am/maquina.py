# -*- coding: utf-8 -*-
"""O lado DESTE PC: manda um trabalho ao am, espera e traz o produto.

O fluxo de `executar(trabalho, local=...)`:

  1. chave do trabalho desligada em `config/pc_am.json` -> `local()`, como
     sempre (o padrao);
  2. a fila: a trava `pc_am` daqui (um trabalho pesado por vez no am, que
     tem 8 GB) e o `ativo.json` de la (recusa um segundo);
  3. a saude: SSH responde, disco e memoria acima do minimo, ninguem
     rodando la;
  4. o codigo: o clone do am vai ao COMMIT EXATO daqui por `git bundle`
     via scp (o am NAO tem login do GitHub e o Blue Lock e privado) e recebe as mudancas
     NAO commitadas daqui (`git diff --binary HEAD`), para rodar o mesmo
     codigo que rodaria aqui;
  5. as entradas (banco de personagens, ledger, musica...) vao por scp, so
     as que mudaram (sha256 dos dois lados);
  6. o comando roda la DESANEXADO (WMI; a queda do SSH nao o mata), sem
     janela, com prazo e log;
  7. o produto volta para uma pasta TEMPORARIA ao lado do destino, cada
     arquivo conferido por tamanho e sha256 contra o do am, e so entao vai
     ao lugar com `os.replace`. Nada pela metade no disco daqui.

Queda segura: am fora (SSH, saude, fila) = `local()` com aviso. Falha DO
TRABALHO la (rc, produto faltando, hash diferente) = `FalhaNoAm` com o
motivo e o fim do log; quem chama decide (a geracao cai para `local()`
tambem: o canal nao para por causa do am).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import lado_am, sonda as sonda_mod
from . import relogio as janela_das_postagens

RAIZ_RB = Path(__file__).resolve().parents[2]       # random_builds/
RAIZ = RAIZ_RB.parent                                # o repositorio
CONFIG = RAIZ_RB / "config" / "pc_am.json"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

PADRAO = {
    "host": "100.118.115.9", "usuario": "alvo", "chave_ssh": "~/.ssh/id_ed25519_am",
    "pasta": "C:/nf", "python": "C:/Python314/python.exe",
    "trabalhos": {}, "disco_minimo_gb": 10, "memoria_minima_mb": 1200, "prazo_ssh_s": 25,
    "espera_da_fila_s": {}, "prazo_s": {},
}
URL_PROJETOS = "https://github.com/zaptod/projetos.git"
URL_BLUE_LOCK = "https://github.com/zaptod/BLUE-Lock-project.git"


class AmFora(RuntimeError):
    """O am nao da para usar agora (SSH, saude). O trabalho roda aqui."""


class AmOcupado(AmFora):
    """Outro trabalho esta rodando no am."""


class NaJanela(RuntimeError):
    """Dentro da janela das postagens (`relogio.liberado`): nada pesado, nem
    mandar para o am (o envio usa a rede por onde sobe o video). Tentar de novo
    fora da janela."""


class FalhaNoAm(RuntimeError):
    """O trabalho rodou no am e falhou, ou o produto nao conferiu."""


# ------------------------------------------------------------------ config
def carregar_config(caminho: Path | None = None) -> dict:
    """O config com os padroes por baixo. Ilegivel = tudo desligado."""
    cfg = json.loads(json.dumps(PADRAO))
    try:
        dados = json.loads(Path(caminho or CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(dados, dict):
        cfg.update({k: v for k, v in dados.items() if not k.startswith("_")})
    return cfg


def ligado(tipo: str, cfg: dict | None = None) -> bool:
    """So `true` liga; qualquer outra coisa (falta, texto, config ruim) e nao."""
    cfg = cfg if cfg is not None else carregar_config()
    trabalhos = cfg.get("trabalhos")
    return isinstance(trabalhos, dict) and trabalhos.get(tipo) is True


def mudar_chave(tipo: str, valor: bool, caminho: Path | None = None) -> None:
    caminho = Path(caminho or CONFIG)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados.setdefault("trabalhos", {})[tipo] = bool(valor)
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)


def runtime() -> Path:
    from ..contas import runtime_dir
    pasta = runtime_dir() / "pc_am"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# -------------------------------------------------------------- transporte
class TransporteSsh:
    """SSH + scp ate o am (Tailscale, so chave). Toda chamada vai ao
    `lado_am.py` de la; a resposta e a linha `@@PCAM@@{json}`."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.alvo = f"{cfg['usuario']}@{cfg['host']}"
        self.base = str(cfg["pasta"]).replace("\\", "/").rstrip("/")
        self.chave = os.path.expanduser(cfg["chave_ssh"])
        self.prazo = float(cfg.get("prazo_ssh_s") or 25)
        self.opcoes = ["-i", self.chave, "-o", "BatchMode=yes", "-o", "LogLevel=ERROR",
                       "-o", f"ConnectTimeout={int(min(self.prazo, 12))}",
                       "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4"]
        self._versao = lado_am.versao()

    # --- baixo nivel
    def _ssh(self, comando: str, prazo: float | None = None) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["ssh", *self.opcoes, self.alvo, comando], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=prazo or self.prazo, creationflags=NO_WINDOW,
                                  stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise AmFora(f"o SSH nao respondeu em {prazo or self.prazo:.0f} s") from exc
        except OSError as exc:
            raise AmFora(f"sem ssh neste PC: {exc}") from exc

    def _scp(self, argumentos: list[str], prazo: float) -> None:
        try:
            proc = subprocess.run(["scp", *self.opcoes, "-q", *argumentos], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=prazo,
                                  creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise AmFora(f"o scp nao terminou em {prazo:.0f} s") from exc
        if proc.returncode != 0:
            raise AmFora(f"scp falhou (rc {proc.returncode}): {(proc.stderr or '').strip()[:300]}")

    def _remoto(self, rel: str) -> str:
        return f"{self.alvo}:{self.base}/{rel.lstrip('/')}"

    @property
    def _nome_do_agente(self) -> str:
        """Um arquivo POR VERSAO (20/10/2026): dois clientes daqui com versoes
        diferentes (a fila nova e um lote manual no commit de antes) nao
        trocam o agente um do outro no meio do trabalho."""
        return f"lado_am-{self._versao[:12]}.py"

    def _instalar_agente(self) -> None:
        pasta = self.base.replace("/", "\\") + "\\agente"
        self._ssh(f"if not exist {pasta} mkdir {pasta}")
        self._scp([str(Path(lado_am.__file__)), self._remoto(f"agente/{self._nome_do_agente}")], prazo=60)

    # --- o que o resto usa
    def chamar(self, acao: str, parametros: dict | None = None, prazo: float | None = None,
               _de_novo: bool = True) -> dict:
        dados = dict(parametros or {})
        dados["_versao"] = self._versao
        texto = json.dumps(dados, ensure_ascii=False)
        argumento = base64.b64encode(texto.encode("utf-8")).decode("ascii")
        if len(argumento) > 6000:
            # a linha do cmd do am tem 8191: o parametro vai por arquivo
            nome = f"tmp/param-{uuid.uuid4().hex[:10]}.json"
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
                fh.write(texto)
            try:
                self.chamar("pastas", {"pastas": ["tmp"]})
                self._scp([fh.name, self._remoto(nome)], prazo=120)
            finally:
                os.unlink(fh.name)
            argumento = "@" + nome
        python = str(self.cfg["python"]).replace("/", "\\")
        agente = self.base.replace("/", "\\") + "\\agente\\" + self._nome_do_agente
        proc = self._ssh(f'"{python}" -X utf8 {agente} {acao} {argumento}', prazo=prazo)
        if proc.returncode == 255:
            raise AmFora(f"SSH sem conexao: {(proc.stderr or '').strip()[:200]}")
        linha = next((l for l in reversed((proc.stdout or "").splitlines())
                      if l.startswith(lado_am.MARCA)), None)
        if linha is None:
            if _de_novo and ("lado_am" in (proc.stderr or "") or "No such file" in (proc.stderr or "")
                             or "can't open file" in (proc.stderr or "")):
                self._instalar_agente()
                return self.chamar(acao, parametros, prazo, _de_novo=False)
            raise AmFora(f"o agente do am nao respondeu (rc {proc.returncode}): "
                         f"{((proc.stderr or '') + (proc.stdout or '')).strip()[-300:]}")
        resposta = json.loads(linha[len(lado_am.MARCA):])
        if resposta.get("versao_errada") and _de_novo:
            self._instalar_agente()
            return self.chamar(acao, parametros, prazo, _de_novo=False)
        return resposta

    def enviar(self, pares: list[tuple[Path, str]], prazo: float = 900) -> None:
        """Copia (arquivo daqui, caminho relativo no am), agrupando por pasta."""
        por_pasta: dict[str, list[str]] = {}
        for local, rel in pares:
            pasta, nome = rel.rsplit("/", 1) if "/" in rel else ("", rel)
            if Path(local).name != nome:
                # nome diferente: scp um a um
                self.chamar("pastas", {"pastas": [pasta]} if pasta else {"pastas": []})
                self._scp([str(local), self._remoto(rel)], prazo=prazo)
                continue
            por_pasta.setdefault(pasta, []).append(str(local))
        if por_pasta:
            self.chamar("pastas", {"pastas": [p for p in por_pasta if p]})
        for pasta, arquivos in por_pasta.items():
            for i in range(0, len(arquivos), 40):
                self._scp([*arquivos[i:i + 40], self._remoto(pasta + "/" if pasta else "")], prazo=prazo)

    def receber(self, rel: str, pasta_local: Path, prazo: float = 1800) -> None:
        pasta_local.mkdir(parents=True, exist_ok=True)
        self._scp(["-r", self._remoto(rel), str(pasta_local)], prazo=prazo)


# ---------------------------------------------------------------- trabalho
@dataclass
class Trabalho:
    """O que vai ao am. Caminhos remotos sao RELATIVOS a `C:/nf`."""
    tipo: str                                  # testes | duelo | bluelock
    comando: list[str]                         # "{PY}" e "{BASE}" trocados la
    cwd: str = "projetos"
    entradas: list[tuple[Path, str]] = field(default_factory=list)
    limpar_antes: list[str] = field(default_factory=list)          # globs apagados la
    limpar_depois: list[str] = field(default_factory=list)         # apagados la depois de trazer
    espelhar: list[tuple[str, list[str]]] = field(default_factory=list)  # (glob, manter)
    saida: str | None = None                   # glob remoto do produto (1 achado)
    destino: Path | None = None
    modo_destino: str = "item"                 # item (o achado vira o destino) | arquivos
    instalar: Callable | None = None           # instalar(achado_local, trabalho) -> Path
    env: dict = field(default_factory=dict)
    prazo_s: float = 1800
    aceitar_rc: tuple = (0,)
    repos: list[dict] = field(default_factory=list)
    fabrica: str = "pc_am"
    canal: str = "builds"
    rotulo: str = ""
    sessao_interativa: bool = False            # precisa da GPU: roda na sessao do console do am
    perfil: str = ""                           # a estimativa de CPU/memoria (padrao: o tipo)
    saida_pelo_log: tuple | None = None        # (regex, modelo): o produto e o que o log diz
    recursos: list[str] = field(default_factory=list)   # exclusivos no am (ex.: "perfil:chatgpt__historias")
    id: str = ""

    def __post_init__(self):
        self.perfil = self.perfil or self.tipo
        if not self.id:
            self.id = f"{self.tipo}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"


@dataclass
class Resultado:
    onde: str                                   # am | aqui
    ok: bool = True
    rc: int | None = 0
    segundos: float = 0.0
    log: str = ""
    destino: Path | None = None
    motivo: str = ""                            # por que rodou aqui
    valor: object = None                        # o retorno do local()
    sincronia: list = field(default_factory=list)
    trabalho_id: str = ""
    etapas: dict = field(default_factory=dict)  # segundos de cada etapa no am


# -------------------------------------------------------------- codigo/git
def _git(raiz: Path, *args, binario: bool = False):
    proc = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True,
                          creationflags=NO_WINDOW, timeout=300)
    if binario:
        return proc.returncode, proc.stdout
    return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()


def estado_do_codigo(raiz: Path) -> dict:
    """{commit, diff (bytes), arquivos, nao_rastreados} do repositorio daqui."""
    rc, commit = _git(raiz, "rev-parse", "HEAD")
    if rc != 0:
        raise FalhaNoAm(f"{raiz} nao e um repositorio git")
    _, diff = _git(raiz, "diff", "--binary", "HEAD", binario=True)
    _, nomes = _git(raiz, "-c", "core.quotepath=false", "diff", "--name-only", "HEAD")
    _, soltos = _git(raiz, "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard")
    return {"commit": commit, "diff": diff or b"", "arquivos": [n for n in nomes.splitlines() if n],
            "nao_rastreados": [n for n in soltos.splitlines() if n]}


def _bundle(raiz: Path, head_do_am: str, commit: str = "") -> Path:
    """O `git bundle` do commit daqui (HEAD, ou `commit`) so com o que o am nao
    tem (`^head_do_am`, se ele e ancestral). O am nao tem login do GitHub: e
    por aqui que o codigo chega (26/10/2026)."""
    destino = Path(tempfile.mkdtemp(prefix="pc_am_")) / "codigo.bundle"
    if not commit:
        rc, commit = _git(raiz, "rev-parse", "HEAD")
        if rc != 0:
            raise FalhaNoAm(f"{raiz} nao e um repositorio git")
    # o am busca `refs/pcam/*` (nunca o HEAD do bundle): uma ref temporaria, apagada no fim
    ref_temporaria = f"refs/pcam/{commit[:12]}"
    ref = ref_temporaria
    rc, saida = _git(raiz, "update-ref", ref_temporaria, commit)
    if rc != 0:
        raise FalhaNoAm(f"o commit {commit[:10]} nao existe em {raiz}: {saida[-200:]}")
    base = []
    if head_do_am and _git(raiz, "merge-base", "--is-ancestor", head_do_am, commit)[0] == 0:
        base = [f"^{head_do_am}"]
    try:
        rc, saida = _git(raiz, "bundle", "create", str(destino), ref, *base)
    finally:
        if ref_temporaria:
            _git(raiz, "update-ref", "-d", ref_temporaria)
    if rc != 0:
        raise FalhaNoAm(f"git bundle falhou: {saida[-300:]}")
    return destino


def sincronizar(t, repo: dict) -> dict:
    """Poe o clone `repo["nome"]` do am no commit daqui (+ mudancas).

    `repo["commit"]` manda num commit EXPLICITO (o ramo do Blue Lock que o
    vigia quer testar): sem diff; o commit tem de existir no clone daqui
    (`raiz`) e vai por bundle, nunca pelo GitHub (o am nao tem login)."""
    raiz = Path(repo["raiz"])
    if repo.get("commit"):
        codigo = {"commit": repo["commit"], "diff": b"", "arquivos": [], "nao_rastreados": []}
    else:
        codigo = estado_do_codigo(raiz)
    parametros = {"repo": repo["nome"], "commit": codigo["commit"],
                  "instalar": repo.get("instalar", True)}
    temporarios = []
    try:
        if repo.get("mudancas", True) and codigo["diff"]:
            fd, caminho = tempfile.mkstemp(suffix=".diff", prefix="pc_am_")
            with os.fdopen(fd, "wb") as fh:
                fh.write(codigo["diff"])
            temporarios.append(Path(caminho))
            # o nome leva o hash do diff: dois clientes daqui com mudancas
            # diferentes nao se sobrescrevem
            rel = (f"tmp/{repo['nome']}-{codigo['commit'][:10]}-"
                   f"{hashlib.sha256(codigo['diff']).hexdigest()[:12]}.diff")
            t.enviar([(Path(caminho), rel)])
            parametros.update(diff=rel, arquivos_do_diff=codigo["arquivos"])
        resposta = t.chamar("sincronizar", parametros, prazo=2400)
        if resposta.get("ocupado"):
            raise AmOcupado(f"o am esta cheio: {resposta.get('erro')}")
        if resposta.get("falta_commit"):
            bundle = _bundle(raiz, resposta.get("head", ""), repo.get("commit") or "")
            temporarios.append(bundle)
            rel = f"tmp/{repo['nome']}.bundle"
            t.enviar([(bundle, rel)], prazo=1800)
            resposta = t.chamar("sincronizar", {**parametros, "bundle": rel}, prazo=2400)
            if resposta.get("ocupado"):
                raise AmOcupado(f"o am esta cheio: {resposta.get('erro')}")
        if not resposta.get("ok"):
            raise FalhaNoAm(f"sincronizar {repo['nome']}: {resposta.get('erro') or resposta}")
        resposta["nao_rastreados"] = codigo["nao_rastreados"]
        return resposta
    finally:
        for caminho in temporarios:
            try:
                caminho.unlink()
                if caminho.parent.name.startswith("pc_am_"):
                    caminho.parent.rmdir()
            except OSError:
                pass


# ------------------------------------------------------ recursos do am
# Desde 20/10/2026 o am roda VARIOS trabalhos ao mesmo tempo, por recurso
# (pedido do Adrian: "quero que fique em 90%"): entra mais um enquanto a CPU
# media de 30 s estiver abaixo de `cpu_alvo` e sobrar memoria para ele (a
# estimativa do tipo + a reserva). A estimativa comeca nestes numeros e
# aprende com o medidor do am (pico de memoria e nucleos de cada trabalho
# que termina, `pc_am/perfis.json`).
PERFIS_PADRAO = {
    "duelo": {"memoria_mb": 900, "cpu_nucleos": 1.5},
    "testes": {"memoria_mb": 800, "cpu_nucleos": 1.0},
    "npm": {"memoria_mb": 1800, "cpu_nucleos": 3.0},
    "bluelock": {"memoria_mb": 1500, "cpu_nucleos": 2.0},
    "voz": {"memoria_mb": 1200, "cpu_nucleos": 1.5},
    # o que vai vir (o Adrian quer este PC inteiro no am): navegador logado
    # (historias, carteiro, publicacao). Chrome aberto e o que enche os 8 GB.
    "navegador": {"memoria_mb": 1600, "cpu_nucleos": 1.0},
}
PARALELO_PADRAO = {"maximo": 1, "cpu_alvo": 80, "memoria_reserva_mb": 1500, "janela_cpu_s": 30}


def paralelo(cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else carregar_config()
    dados = dict(PARALELO_PADRAO)
    if isinstance(cfg.get("paralelo"), dict):
        dados.update({k: v for k, v in cfg["paralelo"].items() if not str(k).startswith("_")})
    return dados


def perfis() -> dict:
    aprendidos = {}
    try:
        aprendidos = json.loads((runtime() / "perfis.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    saida = json.loads(json.dumps(PERFIS_PADRAO))
    for nome, valor in (aprendidos or {}).items():
        if isinstance(valor, dict):
            saida.setdefault(nome, {}).update({k: v for k, v in valor.items() if isinstance(v, (int, float))})
    return saida


def estimativa(perfil: str) -> dict:
    todos = perfis()
    return todos.get(perfil) or todos["testes"]


def aprender(perfil: str, fim: dict) -> None:
    """O medidor do am disse quanto o trabalho usou: a estimativa anda para la
    (memoria: nunca menos que 80% do maior visto; CPU: media movel)."""
    memoria, nucleos = fim.get("pico_memoria_mb"), fim.get("cpu_nucleos")
    if not memoria and not nucleos:
        return
    caminho = runtime() / "perfis.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    atual = dados.get(perfil) or dict(PERFIS_PADRAO.get(perfil) or PERFIS_PADRAO["testes"])
    if memoria:
        atual["memoria_mb"] = int(max(memoria, 0.8 * float(atual.get("memoria_mb", memoria)),
                                      0.5 * float(atual.get("memoria_mb", memoria)) + 0.5 * memoria))
    if nucleos:
        atual["cpu_nucleos"] = round(0.5 * float(atual.get("cpu_nucleos", nucleos)) + 0.5 * nucleos, 2)
    atual["medidos"] = int(atual.get("medidos", 0)) + 1
    dados[perfil] = atual
    temporario = caminho.with_suffix(f".{uuid.uuid4().hex[:6]}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporario, caminho)


def registrar_cpu(cpu, agora: float | None = None) -> None:
    """Guarda uma amostra de CPU do am (a fila e quem chama `executar` usam a
    mesma janela)."""
    if cpu is None:
        return
    agora = time.time() if agora is None else agora
    caminho = runtime() / "cpu.json"
    try:
        amostras = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        amostras = []
    amostras = [a for a in amostras if agora - a[0] < 600] + [[agora, float(cpu)]]
    temporario = caminho.with_suffix(f".{uuid.uuid4().hex[:6]}.tmp")
    temporario.write_text(json.dumps(amostras), encoding="utf-8")
    os.replace(temporario, caminho)


def cpu_media(janela_s: float = 30, agora: float | None = None) -> float | None:
    agora = time.time() if agora is None else agora
    try:
        amostras = json.loads((runtime() / "cpu.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    dentro = [c for t, c in amostras if agora - t <= janela_s]
    return round(sum(dentro) / len(dentro), 1) if dentro else None


def cabe(saude: dict, perfil: str, cfg: dict, *, cpu: float | None = None,
         recentes_mb: float = 0) -> tuple[bool, str]:
    """Mais um trabalho de `perfil` cabe no am agora? (cabe, motivo)."""
    par = paralelo(cfg)
    vivos = saude.get("ativos")
    vivos = vivos if isinstance(vivos, list) else ([saude["ativo"]] if saude.get("ativo") else [])
    if len(vivos) >= int(par["maximo"]):
        return False, f"{len(vivos)} trabalhos rodando (maximo {par['maximo']})"
    est = estimativa(perfil)
    livre = saude.get("memoria_livre_mb")
    if livre is not None and livre - recentes_mb - float(est["memoria_mb"]) < float(par["memoria_reserva_mb"]):
        return False, (f"memoria: {livre} MB livres, {perfil} pede ~{int(est['memoria_mb'])} MB"
                       + (f" (+{int(recentes_mb)} de quem acabou de entrar)" if recentes_mb else "")
                       + f", reserva {par['memoria_reserva_mb']}")
    if vivos and cpu is not None and cpu >= float(par["cpu_alvo"]):
        return False, f"CPU {cpu:.0f}% na media de {par['janela_cpu_s']} s (alvo {par['cpu_alvo']}%)"
    return True, ""


# --------------------------------------------------------------- execucao
def checar_saude(t, cfg: dict, *, perfil: str | None = None, admitir: bool = True) -> dict:
    saude = t.chamar("saude", {"cpu_s": 3}, prazo=float(cfg.get("prazo_ssh_s") or 25) + 10)
    if not saude.get("ok"):
        raise AmFora(f"saude: {saude.get('erro') or saude}")
    registrar_cpu(saude.get("cpu"))
    disco = saude.get("disco_livre_gb")
    if disco is not None and disco < float(cfg.get("disco_minimo_gb") or 0):
        raise AmFora(f"o am tem so {disco} GB livres (minimo {cfg.get('disco_minimo_gb')})")
    if admitir:
        par = paralelo(cfg)
        ok, motivo = cabe(saude, perfil or "testes", cfg, cpu=cpu_media(float(par["janela_cpu_s"])))
        if not ok:
            raise AmOcupado(f"o am esta cheio: {motivo}")
    return saude


def _enviar_entradas(t, trabalho: Trabalho) -> int:
    if not trabalho.entradas:
        return 0
    la = t.chamar("listar", {"caminhos": [rel for _, rel in trabalho.entradas]}, prazo=300)
    if not la.get("ok"):
        raise FalhaNoAm(f"listar as entradas: {la.get('erro')}")
    remotos = la.get("arquivos", {})
    faltam = [(local, rel) for local, rel in trabalho.entradas
              if remotos.get(rel, {}).get("sha256") != sha256(Path(local))]
    if not faltam:
        return 0
    # UM zip, UM scp: pelo relay do Tailscale cada conexao custa segundos (a
    # 1a prova do duelo, 19/10/2026, gastou 6,5 min mandando pasta a pasta)
    fd, caminho = tempfile.mkstemp(suffix=".zip", prefix="pc_am_")
    os.close(fd)
    try:
        with zipfile.ZipFile(caminho, "w") as zf:
            for local, rel in faltam:
                guardar = Path(local).suffix.lower() in (".mp4", ".png", ".jpg", ".mp3", ".zip")
                zf.write(local, rel, compress_type=zipfile.ZIP_STORED if guardar else zipfile.ZIP_DEFLATED)
        rel_zip = f"tmp/entradas-{trabalho.id}.zip"
        t.enviar([(Path(caminho), rel_zip)], prazo=1800)
        resposta = t.chamar("desempacotar", {"zip": rel_zip}, prazo=600)
        if not resposta.get("ok"):
            raise FalhaNoAm(f"desempacotar as entradas: {resposta.get('erro')}")
    finally:
        os.unlink(caminho)
    return len(faltam)


def _paciente(fazer: Callable, o_que: str, limite: float, dorme: Callable, relogio: Callable,
              erro: type = None):
    """Depois de LANCADO, uma queda do SSH nao vira "am fora": o trabalho
    continua la. Tenta de novo ate `limite`; so entao e falha. (19/10/2026:
    um piscar do relay no meio do 1o duelo fez o duelo rodar AQUI tambem,
    dentro da janela das postagens, com o do am terminando em 173 s.)"""
    while True:
        try:
            return fazer()
        except AmOcupado:
            raise
        except AmFora as exc:
            if relogio() > limite:
                if erro is AmFora:
                    raise
                raise FalhaNoAm(f"o am sumiu depois de lancado ({o_que}): {exc}") from exc
            print(f"[pc_am] {o_que}: sem conexao com o am ({exc}); tentando de novo")
            dorme(15)


def _esperar(t, trabalho: Trabalho, dorme: Callable, relogio: Callable) -> dict:
    limite = relogio() + trabalho.prazo_s + 180
    intervalo = 2.0
    # ESPERA LONGA: o agente do am segura a pergunta ate 90 s e responde assim
    # que o fim.json aparece. Menos conexoes = menos chance de cair numa das
    # que falham (19/10/2026: o connect do SSH dava timeout de vez em quando,
    # e um trabalho de 57 s levou 367 s ponta a ponta esperando reconexao).
    while True:
        estado = _paciente(lambda: t.chamar("estado", {"id": trabalho.id, "ate_s": 90}, prazo=130),
                           "esperando o fim", limite, dorme, relogio)
        if estado.get("fim"):
            return estado["fim"]
        if relogio() > limite:
            try:
                t.chamar("matar", {"id": trabalho.id})
            except AmFora:
                pass
            raise FalhaNoAm(f"{trabalho.id}: passou do prazo ({trabalho.prazo_s:.0f} s) e foi morto")
        dorme(intervalo)
        intervalo = min(intervalo * 1.5, 15.0)


def _conferir_e_mover(t, trabalho: Trabalho, achado: str) -> Path:
    """Traz `achado` (relativo a C:/nf) para um temporario ao lado do destino,
    confere cada arquivo e so entao instala. Erro = nada fica aqui."""
    lista = t.chamar("listar", {"caminhos": [achado]}, prazo=600)
    esperados = lista.get("arquivos") or {}
    if not lista.get("ok") or not esperados:
        raise FalhaNoAm(f"o produto {achado} esta vazio no am")
    destino = Path(trabalho.destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporaria = destino.parent / f".pc_am-{trabalho.id}"
    shutil.rmtree(temporaria, ignore_errors=True)
    try:
        t.receber(achado, temporaria)
        nome = achado.rstrip("/").rsplit("/", 1)[-1]
        local = temporaria / nome
        for rel, info in esperados.items():
            sufixo = rel[len(achado):].lstrip("/") if rel != achado else ""
            arquivo = local / sufixo if sufixo else local
            if not arquivo.is_file():
                raise FalhaNoAm(f"veio sem {rel}")
            if arquivo.stat().st_size != info["tamanho"] or sha256(arquivo) != info["sha256"]:
                raise FalhaNoAm(f"{rel} chegou diferente do am (tamanho/sha256)")
        if trabalho.instalar:
            return Path(trabalho.instalar(local, trabalho))
        if trabalho.modo_destino == "arquivos":
            destino.mkdir(parents=True, exist_ok=True)
            fontes = [local] if local.is_file() else sorted(p for p in local.rglob("*") if p.is_file())
            for fonte in fontes:
                alvo = destino / (fonte.relative_to(local) if fonte != local else fonte.name)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                os.replace(fonte, alvo)
            return destino
        if destino.exists() and destino.is_dir():
            raise FalhaNoAm(f"o destino {destino} ja existe")
        os.replace(local, destino)
        return destino
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


def rodar_no_am(trabalho: Trabalho, t, cfg: dict, *, dorme=time.sleep, relogio=time.monotonic,
                admitir: bool = True) -> Resultado:
    """`admitir=False`: quem chama ja decidiu que cabe (a fila, que olha a CPU
    na janela dela); as travas duras do am (maximo, recursos, clone) valem."""
    inicio = relogio()
    etapas: dict[str, float] = {}
    marca = [inicio]

    def etapa(nome: str) -> None:
        agora = relogio()
        etapas[nome] = round(agora - marca[0], 1)
        marca[0] = agora

    # Antes de lancar, um piscar da rede (visto varias vezes em 19/10/2026,
    # 20-40 s de "connect timed out") ganha nova tentativa; o am de fato fora
    # continua AmFora e o trabalho roda aqui. A saude espera pouco (45 s, ou
    # nada se a queda ja e conhecida): a geracao tem relogio.
    paciencia = 0 if _fora_conhecido() else 45
    _paciente(lambda: checar_saude(t, cfg, perfil=trabalho.perfil, admitir=admitir), "saude",
              relogio() + paciencia, dorme, relogio, erro=AmFora)
    etapa("saude")
    antes = relogio() + 120
    sincronia = [_paciente(lambda r=repo: sincronizar(t, r), f"codigo {repo['nome']}", antes, dorme, relogio,
                           erro=AmFora) for repo in trabalho.repos]
    etapa("codigo")

    def preparar():
        for padrao, manter in trabalho.espelhar:
            t.chamar("apagar", {"caminhos": [padrao], "manter": manter}, prazo=300)
        if trabalho.limpar_antes:
            t.chamar("apagar", {"caminhos": trabalho.limpar_antes}, prazo=300)
        return _enviar_entradas(t, trabalho)
    _paciente(preparar, "entradas", relogio() + 120, dorme, relogio, erro=AmFora)
    etapa("entradas")
    try:
        lancado = t.chamar("lancar", {"id": trabalho.id, "tipo": trabalho.tipo, "comando": trabalho.comando,
                                      "cwd": trabalho.cwd, "env": trabalho.env, "prazo_s": trabalho.prazo_s,
                                      "sessao_interativa": trabalho.sessao_interativa,
                                      "max_paralelo": int(paralelo(cfg)["maximo"]),
                                      "recursos": list(trabalho.recursos),
                                      "memoria_mb": int(estimativa(trabalho.perfil)["memoria_mb"])})
    except AmFora:
        # a conexao caiu NO lancar: pode ter lancado. Rodar aqui tambem
        # duplicaria o trabalho; pergunta ao am (com paciencia) antes.
        estado = _paciente(lambda: t.chamar("estado", {"id": trabalho.id}), "conferindo o lancamento",
                           relogio() + 180, dorme, relogio)
        if not (estado.get("fim") or estado.get("rodando")):
            raise
        lancado = {"ok": True}
    if lancado.get("ocupado"):
        raise AmOcupado(f"o am esta cheio: {lancado.get('motivo') or (lancado.get('ativo') or {}).get('id')}")
    if not lancado.get("ok"):
        raise FalhaNoAm(f"nao lancou no am: {lancado.get('erro')}")
    fim = _esperar(t, trabalho, dorme, relogio)
    etapa("rodando")
    etapas["no_am"] = fim.get("segundos")
    for chave in ("pico_memoria_mb", "cpu_nucleos"):
        if fim.get(chave) is not None:
            etapas[chave] = fim[chave]
    try:
        aprender(trabalho.perfil, fim)
    except OSError:
        pass
    depois = relogio() + 900
    log = _paciente(lambda: t.chamar("log", {"id": trabalho.id, "bytes": 8000}), "lendo o log", depois,
                    dorme, relogio).get("log", "")
    rc = fim.get("rc")
    if rc not in trabalho.aceitar_rc:
        cauda = "\n".join(log.strip().splitlines()[-15:])
        raise FalhaNoAm(f"{trabalho.id} falhou no am (rc {rc}{', ' + fim['motivo'] if fim.get('motivo') else ''})"
                        f"\n{cauda}")
    destino = None
    if trabalho.saida_pelo_log:
        # varios trabalhos do mesmo tipo ao mesmo tempo: o produto e o que o
        # log DESTE trabalho diz (ex.: "[duelo] duelo_00003 seed=...")
        import re
        padrao, modelo = trabalho.saida_pelo_log
        achados_no_log = re.findall(padrao, log)
        if not achados_no_log:
            raise FalhaNoAm(f"{trabalho.id}: o log nao diz qual foi o produto ({padrao})")
        trabalho.saida = modelo.format(achados_no_log[-1])
    if trabalho.saida:
        achados = _paciente(lambda: t.chamar("achar", {"glob": trabalho.saida}), "achando o produto",
                            depois, dorme, relogio).get("achados") or []
        if len(achados) != 1:
            raise FalhaNoAm(f"{trabalho.id}: esperava 1 produto em {trabalho.saida}, achei {len(achados)}")
        destino = _paciente(lambda: _conferir_e_mover(t, trabalho, achados[0]), "trazendo o produto",
                            depois, dorme, relogio)
        # o que ja voltou (e foi conferido) nao ocupa mais o C: do am
        try:
            t.chamar("apagar", {"caminhos": [achados[0], *trabalho.limpar_depois]}, prazo=300)
        except AmFora:
            pass
    etapa("trazendo")
    return Resultado(onde="am", ok=rc == 0, rc=rc, segundos=round(relogio() - inicio, 1), log=log,
                     destino=destino, sincronia=sincronia, trabalho_id=trabalho.id, etapas=etapas)


# ------------------------------------------------------------- avisos/diario
def registrar(trabalho: Trabalho, status: str, detalhe: str, dur_s: float | None = None) -> None:
    try:
        from .. import atividade
        atividade.registrar(trabalho.fabrica, status, detalhe, trabalho.canal, etapa="pc_am",
                            ref=trabalho.id, dur_s=dur_s)
    except Exception:                                          # noqa: BLE001
        pass


def avisar_real(texto: str) -> bool:
    """O porteiro de sempre (`python -m remoto --avisar`), da raiz do repo."""
    try:
        proc = subprocess.run([os.environ.get("PYTHON") or "python", "-X", "utf8", "-m", "remoto",
                               "--avisar", texto], cwd=str(RAIZ), capture_output=True,
                              timeout=60, creationflags=NO_WINDOW)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _avisar_queda(motivo: str, avisar: Callable) -> None:
    """Um aviso por QUEDA (nao por trabalho): o estado guarda desde quando."""
    caminho = runtime() / "estado.json"
    try:
        estado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}
    if estado.get("fora_desde"):
        return
    estado = {"fora_desde": datetime.now().isoformat(timespec="seconds"), "motivo": motivo}
    caminho.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    avisar(f"🖥 PC am fora ({motivo}). O trabalho pesado roda neste PC até ele voltar.")


def _fora_conhecido() -> bool:
    try:
        return bool(json.loads((runtime() / "estado.json").read_text(encoding="utf-8")).get("fora_desde"))
    except (OSError, ValueError):
        return False


def _am_voltou() -> None:
    caminho = runtime() / "estado.json"
    try:
        if json.loads(caminho.read_text(encoding="utf-8")).get("fora_desde"):
            caminho.write_text("{}", encoding="utf-8")
    except (OSError, ValueError):
        pass


# ------------------------------------------------------------------ porta
@contextmanager
def _vaga(cfg: dict, limite: float, dorme: Callable, relogio: Callable):
    """Uma das `paralelo.maximo` vagas daqui (`pc_am_vaga_N`). Espera ate
    `limite`; True se pegou."""
    from .. import travas
    maximo = max(1, int(paralelo(cfg)["maximo"]))
    while True:
        for i in range(maximo):
            with ExitStack() as pilha:
                minha = pilha.enter_context(travas.trava(f"pc_am_vaga_{i}"))
                if minha:
                    yield True
                    return
        if relogio() >= limite:
            yield False
            return
        dorme(5)


def executar(trabalho: Trabalho, local: Callable, *, cfg: dict | None = None, transporte=None,
             forcar: bool = False, cair_na_falha: bool = True, cair_para_aqui: bool = True,
             avisar: Callable | None = None, dorme=time.sleep, relogio=time.monotonic,
             admitir: bool = True, espera: float | None = None, sonda=None,
             ignorar_janela: bool = False) -> Resultado:
    """A porta unica: am se a chave mandar e ele puder; senao `local()`.

    `forcar`: ignora a chave (o orquestrador medindo antes de ligar).
    `cair_na_falha`: falha DO TRABALHO no am tambem cai para `local()`
    (padrao, para a producao nao parar); False levanta `FalhaNoAm`.
    `cair_para_aqui`: False = am fora levanta `AmFora` e am cheio levanta
    `AmOcupado`, em vez de rodar aqui (a medicao e a fila: nada pesado AQUI).
    `admitir`: False = quem chama ja decidiu que cabe (a fila).
    `espera`: quanto esperar a VEZ quando o am esta cheio (padrao: o
    `espera_da_fila_s` do tipo; o duelo da geracao nao espera).
    `sonda`: funcao `cfg -> {estado, motivo}` (a `sonda.sondar`; padrao: a
    real quando o transporte e o SSH de verdade, nenhuma com transporte de
    teste, a menos que ele tenha `sondar`). `indisponivel` = roda aqui NA
    HORA, sem tentar SSH, sem aviso, so uma linha de log (ponto 9, 26/10).
    `ignorar_janela`: so para quem ja respondeu pela janela (a fila)."""
    cfg = cfg if cfg is not None else carregar_config()
    avisar = avisar or avisar_real

    def aqui(motivo: str) -> Resultado:
        inicio = relogio()
        valor = local()
        return Resultado(onde="aqui", motivo=motivo, valor=valor, segundos=round(relogio() - inicio, 1),
                         trabalho_id=trabalho.id)

    if not (forcar or ligado(trabalho.tipo, cfg)):
        return aqui("chave desligada")
    if not ignorar_janela:
        liberado, porque = janela_das_postagens.liberado()
        if not liberado:
            raise NaJanela(f"{trabalho.tipo} adiado: {porque}")
    if sonda is None:
        sonda = sonda_mod.sondar if transporte is None else getattr(transporte, "sondar", None)
    estado_da_sonda = ""
    if espera is None:
        espera = float((cfg.get("espera_da_fila_s") or {}).get(trabalho.tipo, 0) or 0)
    limite = relogio() + espera
    motivo = ""
    ocupado = False
    if sonda is not None:
        # A SONDA (26/10/2026): um SSH barato e com cache diz se o am esta de pe
        # ANTES de qualquer outra coisa. Desligado: aqui, sem erro e sem alarme.
        try:
            lida = sonda(cfg) or {}
        except Exception:                                      # noqa: BLE001
            lida = {}
        estado_da_sonda = str(lida.get("estado") or "")
        if estado_da_sonda == sonda_mod.INDISPONIVEL or (
                estado_da_sonda == sonda_mod.OCUPADO and espera <= 0):
            ocupado = estado_da_sonda == sonda_mod.OCUPADO
            motivo = (f"am {estado_da_sonda} (sonda: {lida.get('motivo') or 'sem resposta'})")
            if not cair_para_aqui:
                raise (AmOcupado if ocupado else AmFora)(motivo)
            registrar(trabalho, "log", f"rodou neste PC: {motivo}"[:300])
            print(f"[pc_am] {trabalho.tipo}: rodando neste PC — {motivo}")
            return aqui(motivo)
    # A VAGA daqui (20/10/2026): eram uma trava exclusiva — "fila do am cheia
    # (outro trabalho daqui esta nele)" mesmo com o am a 13% de CPU. Agora sao
    # `paralelo.maximo` vagas; quem nao acha uma ESPERA a vez ate `limite`.
    with _vaga(cfg, limite, dorme, relogio) as minha:
        if not minha:
            ocupado = True
            motivo = f"am cheio: as {paralelo(cfg)['maximo']} vagas daqui estao em uso"
        else:
            t = transporte or TransporteSsh(cfg)
            registrar(trabalho, "inicio", f"no PC am: {trabalho.rotulo or trabalho.tipo}")
            while True:
                try:
                    resultado = rodar_no_am(trabalho, t, cfg, dorme=dorme, relogio=relogio, admitir=admitir)
                except AmOcupado as exc:
                    if relogio() < limite:
                        dorme(20)
                        continue
                    ocupado = True
                    motivo = f"am cheio ({exc})"
                except AmFora as exc:
                    motivo = f"am fora: {exc}"
                    if sonda is not None:               # o proximo nem tenta o SSH
                        sonda_mod.marcar(sonda_mod.INDISPONIVEL, str(exc))
                    if cair_para_aqui:
                        # o aviso e da PRODUCAO caindo para ca; a medicao so erra
                        _avisar_queda(str(exc), avisar)
                except FalhaNoAm as exc:
                    registrar(trabalho, "log", f"falhou no PC am: {str(exc)[:240]}")
                    if not cair_na_falha:
                        raise
                    motivo = f"falhou no am: {str(exc).splitlines()[0]}"
                else:
                    _am_voltou()
                    registrar(trabalho, "ok", f"feito no PC am em {resultado.segundos:.0f} s"
                              + (f" -> {resultado.destino}" if resultado.destino else ""),
                              dur_s=resultado.segundos)
                    return resultado
                break
    if not cair_para_aqui:
        raise (AmOcupado if ocupado else AmFora)(motivo)
    registrar(trabalho, "log", f"rodou neste PC: {motivo}"[:300])
    print(f"[pc_am] {trabalho.tipo}: rodando neste PC — {motivo}")
    return aqui(motivo)
