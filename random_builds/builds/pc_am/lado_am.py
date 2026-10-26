# -*- coding: utf-8 -*-
"""O lado do am: o pequeno agente que roda NO OUTRO PC, chamado pelo SSH.

    C:\\Python314\\python.exe C:\\nf\\agente\\lado_am.py <acao> <json em base64>

So biblioteca padrao e nenhum import do repositorio, de proposito: ele
precisa funcionar ANTES de o repositorio do am estar no commit certo (e quem
poe o repositorio no commit certo e ele, em `sincronizar`). O lado daqui
(`maquina.py`) manda o sha256 deste arquivo em toda chamada; se o do am for
outro, a resposta e `versao_errada` e o lado daqui reenvia o arquivo.

A ultima linha da saida e sempre `@@PCAM@@{json}`. Qualquer outra coisa
impressa antes (aviso do git, do pip) e so log.

As pastas, todas debaixo de BASE (`C:\\nf`, ou `PC_AM_BASE`):

    agente/              este arquivo
    projetos/            o clone do github.com/zaptod/projetos
    BLUE-Lock-project/   o clone do Blue Lock (NUNCA empurra nada)
    runtime/             o NEURAL_FIGHTS_RUNTIME_DIR dos trabalhos
    trabalhos/<id>/      job.json, log.txt, fim.json (e o que o job gravar)
    estado/              marcas de instalacao (hash do pyproject, do lock)
    ativo.json           o trabalho que esta rodando agora (um por vez)

Nos testes, o mesmo arquivo roda numa pasta temporaria (`PC_AM_BASE`) e
lanca o trabalho com Popen em vez de WMI (`PC_AM_LANCAR=popen`).
"""
from __future__ import annotations

import base64
import ctypes
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MARCA = "@@PCAM@@"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Onde os programas ficam no am (instalados pelo winget em 19/10/2026).
GIT = r"C:\Program Files\Git\cmd\git.exe"
NPM = r"C:\Program Files\nodejs\npm.cmd"
CAMINHOS_EXTRAS = (
    r"C:\Python314", r"C:\Python314\Scripts", r"C:\Program Files\Git\cmd",
    r"C:\Program Files\nodejs",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"),
)

# O workspace, igual ao CI (.github/workflows/ci.yml, workspace-windows).
EDITAVEIS = [".[dev]", "./random_builds", "./historias", "./mimetizar", "./visao", "./painel"]
PYPROJECTS = ["pyproject.toml", "random_builds/pyproject.toml", "historias/pyproject.toml",
              "mimetizar/pyproject.toml", "visao/pyproject.toml", "painel/pyproject.toml"]
EXTRAS_PIP = ["playwright", "edge-tts"]


def base() -> Path:
    return Path(os.environ.get("PC_AM_BASE") or r"C:\nf")


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def versao() -> str:
    return _sha256(Path(__file__))


def _dentro(rel: str) -> Path:
    """Caminho relativo a BASE, recusando sair dela (`..`, absoluto)."""
    raiz = base().resolve()
    alvo = (raiz / rel).resolve()
    if alvo != raiz and raiz not in alvo.parents:
        raise ValueError(f"fora da pasta de trabalho: {rel}")
    return alvo


def _ambiente(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    caminhos = [c for c in CAMINHOS_EXTRAS if c and os.path.isdir(c)]
    env["PATH"] = os.pathsep.join(caminhos + [env.get("PATH", "")])
    env["PYTHONUTF8"] = "1"
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    for chave, valor in (extra or {}).items():
        env[str(chave)] = str(valor).replace("{BASE}", str(base()))
    return env


def _rodar(comando: list, cwd: Path | None = None, prazo: float = 600, env=None) -> tuple[int, str]:
    try:
        proc = subprocess.run(comando, cwd=str(cwd) if cwd else None, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=prazo,
                              creationflags=NO_WINDOW, env=env or _ambiente())
    except subprocess.TimeoutExpired:
        return 124, f"prazo de {prazo:.0f} s estourado: {comando[:3]}"
    except OSError as exc:
        return 127, f"nao rodou {comando[:2]}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _git() -> str:
    return GIT if os.path.isfile(GIT) else (shutil.which("git") or "git")


# ------------------------------------------------------------------ saude
def _pid_vivo(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel = ctypes.windll.kernel32
    alca = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not alca:
        return False
    try:
        codigo = ctypes.c_ulong()
        kernel.GetExitCodeProcess(alca, ctypes.byref(codigo))
        return codigo.value == 259  # STILL_ACTIVE
    finally:
        kernel.CloseHandle(alca)


def _memoria_livre_mb() -> int | None:
    if os.name != "nt":
        return None

    class Estado(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    estado = Estado()
    estado.dwLength = ctypes.sizeof(Estado)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        return None
    return int(estado.ullAvailPhys // (1024 * 1024))


def _carga_cpu(intervalo: float = 0.5) -> int | None:
    """% de CPU ocupada, medida por GetSystemTimes em `intervalo` segundos."""
    if os.name != "nt":
        return None
    tempo = ctypes.c_ulonglong

    def amostra():
        ocioso, kernel, usuario = tempo(), tempo(), tempo()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(ocioso), ctypes.byref(kernel),
                                              ctypes.byref(usuario))
        return ocioso.value, kernel.value + usuario.value

    o1, t1 = amostra()
    time.sleep(intervalo)
    o2, t2 = amostra()
    total = t2 - t1
    return int(round(100 * (1 - (o2 - o1) / total))) if total > 0 else None


def ativos() -> list[dict]:
    """Os trabalhos rodando agora (`ativos/<id>.json` com o pid vivo).

    Desde 20/10/2026 sao VARIOS ao mesmo tempo (o am roda por recurso: quem
    decide quantos e o lado daqui, pela CPU e pela memoria). O `ativo.json`
    antigo (um so) ainda conta, para conviver com um cliente de antes."""
    vivos = []
    pasta = base() / "ativos"
    candidatos = sorted(pasta.glob("*.json")) if pasta.is_dir() else []
    candidatos.append(base() / "ativo.json")
    for marca in candidatos:
        try:
            dados = json.loads(marca.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        nascendo = dados.get("pid") is None and marca.parent == pasta and \
            time.time() - marca.stat().st_mtime < 180      # a tarefa /IT ainda vai nascer
        if nascendo or _pid_vivo(dados.get("pid")):
            dados.setdefault("repo", "projetos")
            vivos.append(dados)
        elif marca.parent == pasta:
            try:
                marca.unlink()
            except OSError:
                pass
    return vivos


def ativo() -> dict | None:
    """O primeiro trabalho rodando, ou None (o formato de antes)."""
    lista = ativos()
    return lista[0] if lista else None


class _Trava:
    """Trava de arquivo entre os processos do agente (dois clientes daqui
    sincronizando ou lancando ao mesmo tempo)."""

    def __init__(self, nome: str, prazo: float = 120):
        self.caminho = base() / "estado" / f"{nome}.lock"
        self.prazo = prazo
        self.fh = None

    def __enter__(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.caminho, "a+b")
        fim = time.monotonic() + self.prazo
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() > fim:
                    self.fh.close()
                    raise TimeoutError(f"trava {self.caminho.name} ocupada")
                time.sleep(0.3)

    def __exit__(self, *_):
        try:
            if os.name == "nt":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.fh.close()


# ------------------------------------------------- medidor de recursos
def _arvore(raiz: int) -> list[int]:
    """O pid e todos os descendentes (Toolhelp32)."""
    if os.name != "nt":
        return [raiz]
    from ctypes import wintypes

    class Entrada(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    kernel = ctypes.windll.kernel32
    foto = kernel.CreateToolhelp32Snapshot(0x2, 0)
    if foto in (0, -1, ctypes.c_void_p(-1).value):
        return [raiz]
    pais: dict[int, list[int]] = {}
    try:
        entrada = Entrada()
        entrada.dwSize = ctypes.sizeof(Entrada)
        ok = kernel.Process32FirstW(foto, ctypes.byref(entrada))
        while ok:
            pais.setdefault(int(entrada.th32ParentProcessID), []).append(int(entrada.th32ProcessID))
            ok = kernel.Process32NextW(foto, ctypes.byref(entrada))
    finally:
        kernel.CloseHandle(foto)
    vistos, fila = [], [raiz]
    while fila:
        pid = fila.pop()
        if pid in vistos:
            continue
        vistos.append(pid)
        fila.extend(f for f in pais.get(pid, []) if f != pid)
    return vistos


def _uso_do_processo(pid: int) -> tuple[int, int] | None:
    """(memoria em uso em bytes, CPU em centenas de ns) de um processo."""
    if os.name != "nt":
        return None

    class Memoria(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    kernel = ctypes.windll.kernel32
    alca = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
    if not alca:
        return None
    try:
        memoria = Memoria()
        memoria.cb = ctypes.sizeof(Memoria)
        if not kernel.K32GetProcessMemoryInfo(alca, ctypes.byref(memoria), memoria.cb):
            return None
        tempos = [ctypes.c_ulonglong() for _ in range(4)]
        kernel.GetProcessTimes(alca, *[ctypes.byref(x) for x in tempos])
        return int(memoria.WorkingSetSize), int(tempos[2].value + tempos[3].value)
    finally:
        kernel.CloseHandle(alca)


class Medidor:
    """Mede a arvore de um trabalho a cada `passo` s: pico de memoria e CPU
    media (em nucleos). E o que o lado daqui usa para decidir quantos cabem."""

    def __init__(self, pid: int, passo: float = 3.0):
        import threading
        self.pid, self.passo = pid, passo
        self.pico_mb, self.cpu_100ns = 0, 0
        self._ultimo: dict[int, int] = {}
        self._parar = threading.Event()
        self._inicio = time.monotonic()
        self._fio = threading.Thread(target=self._medir, daemon=True)
        self._fio.start()

    def _medir(self):
        while not self._parar.is_set():
            total = 0
            for pid in _arvore(self.pid):
                uso = _uso_do_processo(pid)
                if uso is None:
                    continue
                total += uso[0]
                antes = self._ultimo.get(pid, 0)
                self.cpu_100ns += max(0, uso[1] - antes)
                self._ultimo[pid] = uso[1]
            self.pico_mb = max(self.pico_mb, total // (1024 * 1024))
            self._parar.wait(self.passo)

    def fim(self) -> dict:
        self._parar.set()
        self._fio.join(timeout=10)
        segundos = max(0.001, time.monotonic() - self._inicio)
        return {"pico_memoria_mb": int(self.pico_mb), "cpu_nucleos": round(self.cpu_100ns / 1e7 / segundos, 2)}


def _temperatura_c() -> float | None:
    """A da zona termica do ACPI, se a placa-mae informa (muitas nao)."""
    if os.name != "nt":
        return None
    rc, saida = _rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
                        "-ErrorAction SilentlyContinue | Select-Object -First 1).CurrentTemperature"], prazo=20)
    try:
        return round(int(saida.strip().splitlines()[-1]) / 10 - 273.15, 1) if rc == 0 and saida.strip() else None
    except (ValueError, IndexError):
        return None


def acao_saude(p: dict) -> dict:
    raiz = base()
    raiz.mkdir(parents=True, exist_ok=True)
    uso = shutil.disk_usage(raiz)
    lista = ativos()
    saude = {"ok": True, "disco_livre_gb": round(uso.free / 1024 ** 3, 1),
             "memoria_livre_mb": _memoria_livre_mb(),
             "cpu": _carga_cpu(min(float(p.get("cpu_s") or 0.5), 10.0)),
             "ativo": lista[0] if lista else None, "ativos": lista, "nucleos": os.cpu_count(),
             "python": sys.version.split()[0], "agora": datetime.now().isoformat(timespec="seconds")}
    if p.get("temperatura"):
        saude["temperatura_c"] = _temperatura_c()
    return saude


# ------------------------------------------------------------- sincronizar
def _hash_de(repo: Path, arquivos: list[str]) -> str:
    h = hashlib.sha256()
    for rel in arquivos:
        caminho = repo / rel
        h.update(rel.encode())
        if caminho.is_file():
            h.update(caminho.read_bytes())
    return h.hexdigest()


def _pos_instalacao(nome: str, repo: Path, log: list) -> dict:
    """pip install do workspace se um pyproject mudou; npm ci se o lock mudou."""
    estado = base() / "estado"
    estado.mkdir(parents=True, exist_ok=True)
    if nome == "projetos":
        assinatura = _hash_de(repo, PYPROJECTS)
        marca = estado / "pip.txt"
        if marca.is_file() and marca.read_text().strip() == assinatura:
            return {"instalou": False}
        comando = [sys.executable, "-m", "pip", "install", "-q"]
        restricoes = base() / "tmp" / "restricoes.txt"
        if restricoes.is_file():
            comando += ["-c", str(restricoes)]
        for item in EDITAVEIS:
            comando += ["-e", item]
        comando += EXTRAS_PIP
        rc, saida = _rodar(comando, cwd=repo, prazo=1800)
        log.append(saida[-3000:])
        if rc != 0:
            return {"instalou": False, "erro": f"pip install falhou (rc {rc})"}
        marca.write_text(assinatura)
        return {"instalou": True}
    if nome == "BLUE-Lock-project":
        assinatura = _hash_de(repo, ["package-lock.json", "package.json"])
        marca = estado / "npm.txt"
        if (repo / "node_modules").is_dir() and marca.is_file() and marca.read_text().strip() == assinatura:
            return {"instalou": False}
        rc, saida = _rodar([NPM if os.path.isfile(NPM) else "npm", "ci", "--no-audit", "--no-fund"],
                           cwd=repo, prazo=1800)
        log.append(saida[-3000:])
        if rc != 0:
            return {"instalou": False, "erro": f"npm ci falhou (rc {rc})"}
        marca.write_text(assinatura)
        return {"instalou": True}
    return {"instalou": False}


def acao_sincronizar(p: dict) -> dict:
    """Poe o clone `p["repo"]` no commit `p["commit"]` e aplica o diff.

    O am NAO TEM login do GitHub e o Blue Lock e PRIVADO (26/10/2026): este
    lado nunca fala com o GitHub. Ordem para achar o commit: ja existe -> o
    bundle enviado por scp (`git fetch <bundle>`; sem clone ainda, `git clone
    <bundle>`). Sem o commit e sem bundle, devolve `falta_commit` com o HEAD
    daqui ('' se nem clone ha): o lado de la monta o bundle a partir dele.

    Com VARIOS trabalhos ao mesmo tempo (20/10/2026): o clone que ja esta no
    estado pedido (commit + diff) nao e tocado; o que precisa mudar so muda
    se NENHUM trabalho vivo roda dele — senao `ocupado` (o lado daqui espera a
    vez). Mexer no clone com um trabalho lendo dele e o defeito da rodada
    viva que importa arquivo pela metade."""
    nome = p["repo"]
    try:
        with _Trava(f"sinc_{nome}", prazo=900):
            return _sincronizar(p, nome)
    except TimeoutError as exc:
        return {"ok": False, "ocupado": True, "erro": str(exc)}


def _sincronizar(p: dict, nome: str) -> dict:
    repo = _dentro(nome)
    git = _git()
    log: list = []
    diff_sha = _sha256(_dentro(p["diff"])) if p.get("diff") else "-"
    chave = f"{p['commit']}:{diff_sha}"
    marca = base() / "estado" / f"clone_{nome}.json"
    try:
        estado = json.loads(marca.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}
    if estado.get("chave") == chave and (repo / ".git").exists():
        head = _rodar([git, "rev-parse", "HEAD"], cwd=repo, prazo=60)[1].strip()
        # e ninguem mexeu por fora (um cliente antigo nao grava esta marca):
        # os arquivos mudados sao exatamente os do diff
        _, sujo = _rodar([git, "-c", "core.quotepath=false", "status", "--porcelain", "--untracked-files=all"],
                         cwd=repo, prazo=120)
        mudados = {linha[3:].strip().strip('"') for linha in sujo.splitlines() if linha.strip()}
        if head == p["commit"] and mudados == set(p.get("arquivos_do_diff") or []):
            return {"ok": True, "commit": p["commit"], "diff": p.get("arquivos_do_diff") or [],
                    "instalou": False, "ja_estava": True}
    em_uso = [a.get("id") for a in ativos() if a.get("repo") == nome]
    if em_uso:
        return {"ok": False, "ocupado": True, "erro": f"o clone {nome} esta em uso por {', '.join(em_uso)}"}
    try:
        marca.unlink()
    except OSError:
        pass
    if not (repo / ".git").exists():
        if not p.get("bundle"):
            return {"ok": False, "falta_commit": True, "head": "", "log": ["sem clone: preciso do bundle inteiro"]}
        # o bundle so tem refs/pcam/* (sem HEAD): `git clone` nao serve; init + fetch
        rc, saida = _rodar([git, "init", "--quiet", str(repo)], prazo=300)
        log.append(saida)
        if rc != 0:
            return {"ok": False, "erro": f"git init falhou (rc {rc})", "log": log}
    commit = p["commit"]

    def tem() -> bool:
        return _rodar([git, "cat-file", "-e", f"{commit}^{{commit}}"], cwd=repo, prazo=60)[0] == 0

    if not tem() and p.get("bundle"):
        rc, saida = _rodar([git, "fetch", "--quiet", str(_dentro(p["bundle"])), "+refs/pcam/*:refs/pcam/*"],
                           cwd=repo, prazo=600)
        log.append(saida[-1500:])
    if not tem():
        head = _rodar([git, "rev-parse", "HEAD"], cwd=repo, prazo=60)[1].strip()
        return {"ok": False, "falta_commit": True, "head": head, "log": log}
    for comando in ([git, "reset", "--quiet", "--hard", commit], [git, "clean", "-fdq"]):
        rc, saida = _rodar(comando, cwd=repo, prazo=300)
        if rc != 0:
            return {"ok": False, "erro": f"{' '.join(comando[1:3])} falhou: {saida[-800:]}"}
    aplicado = []
    if p.get("diff"):
        caminho = _dentro(p["diff"])
        rc, saida = _rodar([git, "apply", "--whitespace=nowarn", str(caminho)], cwd=repo, prazo=300)
        if rc != 0:
            return {"ok": False, "erro": f"git apply das mudancas nao commitadas falhou: {saida[-800:]}"}
        aplicado = p.get("arquivos_do_diff") or []
    pos = _pos_instalacao(nome, repo, log) if p.get("instalar", True) else {"instalou": False}
    if pos.get("erro"):
        return {"ok": False, "erro": pos["erro"], "log": log[-2:]}
    marca.parent.mkdir(parents=True, exist_ok=True)
    marca.write_text(json.dumps({"chave": chave, "em": datetime.now().isoformat(timespec="seconds")}),
                     encoding="utf-8")
    return {"ok": True, "commit": commit, "diff": aplicado, "instalou": pos.get("instalou", False)}


# --------------------------------------------------------------- arquivos
def acao_listar(p: dict) -> dict:
    """Arquivos (tamanho e sha256) debaixo de cada caminho/glob pedido."""
    raiz = base().resolve()
    arquivos = {}
    for rel in p.get("caminhos", []):
        for achado in glob.glob(str(_dentro(rel)), recursive=True):
            alvo = Path(achado)
            candidatos = [alvo] if alvo.is_file() else [f for f in alvo.rglob("*") if f.is_file()]
            for arquivo in candidatos:
                chave = arquivo.resolve().relative_to(raiz).as_posix()
                arquivos[chave] = {"tamanho": arquivo.stat().st_size,
                                   "sha256": _sha256(arquivo) if p.get("hash", True) else None}
    return {"ok": True, "arquivos": arquivos}


def acao_pastas(p: dict) -> dict:
    """Cria as pastas (o scp nao cria a pasta de destino)."""
    for rel in p.get("pastas", []):
        _dentro(rel).mkdir(parents=True, exist_ok=True)
    return {"ok": True}


def acao_desempacotar(p: dict) -> dict:
    """Abre o zip das entradas (um scp so, em vez de um por pasta: pelo relay
    do Tailscale cada conexao custa segundos — a 1a prova do duelo gastou 6,5
    min mandando 150 arquivos pasta a pasta)."""
    import zipfile
    arquivo = _dentro(p["zip"])
    with zipfile.ZipFile(arquivo) as zf:
        nomes = zf.namelist()
        for nome in nomes:
            alvo = _dentro(nome)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            temporario = alvo.with_name(alvo.name + ".pcam_tmp")
            with zf.open(nome) as origem, open(temporario, "wb") as destino:
                shutil.copyfileobj(origem, destino)
            os.replace(temporario, alvo)
    try:
        arquivo.unlink()
    except OSError:
        pass
    return {"ok": True, "arquivos": len(nomes)}


def acao_achar(p: dict) -> dict:
    """O que casa com o glob, relativo a BASE (pasta ou arquivo)."""
    raiz = base().resolve()
    achados = sorted(Path(a).resolve().relative_to(raiz).as_posix()
                     for a in glob.glob(str(_dentro(p["glob"]))))
    return {"ok": True, "achados": achados}


def acao_apagar(p: dict) -> dict:
    """Apaga o que casar com os globs, menos o que estiver em `manter`."""
    manter = {str(_dentro(m)) for m in p.get("manter", [])}
    apagados = []
    for rel in p.get("caminhos", []):
        for achado in glob.glob(str(_dentro(rel))):
            alvo = Path(achado)
            if str(alvo.resolve()) in manter or alvo.resolve() == base().resolve():
                continue
            if alvo.is_dir():
                shutil.rmtree(alvo, ignore_errors=True)
            else:
                try:
                    alvo.unlink()
                except OSError:
                    continue
            apagados.append(achado)
    return {"ok": True, "apagados": len(apagados)}


# ------------------------------------------------------------- trabalhos
def _pasta_do(id_: str) -> Path:
    if not id_ or any(c in id_ for c in "\\/:.") :
        raise ValueError(f"id de trabalho invalido: {id_!r}")
    return base() / "trabalhos" / id_


def acao_lancar(p: dict) -> dict:
    """Grava job.json e lanca `executar` DESANEXADO (sobrevive ao SSH cair).

    Quantos ao mesmo tempo quem decide e o lado daqui (pela CPU e pela
    memoria); aqui so as travas duras: `max_paralelo` trabalhos vivos e os
    `recursos` exclusivos (um perfil de navegador, por exemplo: dois Chromes
    no mesmo perfil se trancam) — ocupado = `ocupado`, e o lado daqui espera."""
    try:
        with _Trava("lancar", prazo=60):
            vivos = ativos()
            limite = int(p.get("max_paralelo") or 1)
            if len(vivos) >= limite:
                return {"ok": False, "ocupado": True, "ativo": vivos[0], "ativos": vivos,
                        "motivo": f"{len(vivos)} trabalho(s) rodando (limite {limite})"}
            meus = set(p.get("recursos") or [])
            for vivo in vivos:
                comum = meus & set(vivo.get("recursos") or [])
                if comum:
                    return {"ok": False, "ocupado": True, "ativo": vivo, "ativos": vivos,
                            "motivo": f"{', '.join(sorted(comum))} em uso por {vivo.get('id')}"}
            resposta = _lancar(p)
            if resposta.get("ok"):
                _marcar_ativo(p, resposta.get("pid"))
            return resposta
    except TimeoutError as exc:
        return {"ok": False, "ocupado": True, "motivo": str(exc)}


def _repo_do(cwd: str) -> str:
    return (cwd or ".").replace("\\", "/").split("/", 1)[0]


def _marcar_ativo(job: dict, pid) -> None:
    pasta = base() / "ativos"
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {"id": job["id"], "pid": pid, "tipo": job.get("tipo"), "repo": _repo_do(job.get("cwd")),
             "recursos": list(job.get("recursos") or []), "memoria_mb": job.get("memoria_mb"),
             "desde": datetime.now().isoformat(timespec="seconds")}
    temporario = pasta / f"{job['id']}.tmp"
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, pasta / f"{job['id']}.json")


def _lancar(p: dict) -> dict:
    pasta = _pasta_do(p["id"])
    pasta.mkdir(parents=True, exist_ok=True)
    # a pasta de trabalho guarda a saida (o mp4 do Blue Lock) ate ser trazida:
    # as de mais de 3 dias saem, para o C: do am (o unico disco) nao encher
    for antiga in (base() / "trabalhos").iterdir():
        try:
            if antiga.is_dir() and antiga != pasta and time.time() - antiga.stat().st_mtime > 3 * 86400:
                shutil.rmtree(antiga, ignore_errors=True)
        except OSError:
            pass
    for velho in ("fim.json", "log.txt"):
        try:
            (pasta / velho).unlink()
        except OSError:
            pass
    (pasta / "job.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    comando = [sys.executable, str(Path(__file__).resolve()), "executar", p["id"]]
    if p.get("sessao_interativa") and os.environ.get("PC_AM_LANCAR") != "popen" and os.name == "nt":
        return _lancar_na_sessao(p["id"], pasta)
    if os.environ.get("PC_AM_LANCAR") == "popen" or os.name != "nt":
        proc = subprocess.Popen(comando, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "pid": proc.pid}
    # WMI: o processo nasce filho do WmiPrvSE, fora do job object do sshd,
    # entao a queda da conexao nao o mata. Nasce na sessao 0 (a do SSH), que
    # nao tem tela: nenhuma janela aparece para quem estiver usando o am.
    # python.exe e nao pythonw.exe: sem console, o pythonw nao tem handles de
    # stdin/stdout, e todo subprocess que os herda morre com WinError 6
    # (2 testes do coordenador cairam assim na 1a prova, 19/10/2026).
    linha = subprocess.list2cmdline(comando)
    script = ("$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
              "@{CommandLine=$env:PCAM_LINHA; CurrentDirectory=$env:PCAM_CWD}; "
              "\"$($r.ReturnValue) $($r.ProcessId)\"")
    env = _ambiente({"PCAM_LINHA": linha, "PCAM_CWD": str(pasta)})
    rc, saida = _rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], prazo=60, env=env)
    partes = saida.strip().split()
    if rc != 0 or len(partes) < 2 or partes[-2] != "0":
        return {"ok": False, "erro": f"WMI nao lancou o trabalho: {saida[-500:]}"}
    return {"ok": True, "pid": int(partes[-1])}


def sessao_de_console() -> bool:
    """Alguem (o `alvo`) esta logado no console do am? `query user` lista."""
    rc, saida = _rodar(["query", "user"], prazo=30)
    return any("console" in linha.lower() and ("ativo" in linha.lower() or "active" in linha.lower())
               for linha in saida.splitlines())


def _lancar_na_sessao(id_: str, pasta: Path) -> dict:
    """O trabalho que precisa da PLACA DE VIDEO (o WebGL do Blue Lock): a
    sessao 0 do SSH/WMI nao tem GPU — o Chrome dela so tem SwiftShader, e 10 s
    de partida levaram 913 s (19/10/2026). Uma tarefa "so interativa" (/IT)
    roda na sessao do console, com a GPU, e o pythonw nao abre janela.
    Ninguem logado no console = recusa (quem chamou roda neste PC)."""
    if not sessao_de_console():
        return {"ok": False, "erro": "ninguem logado no console do am (a GPU so existe la)"}
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    linha = subprocess.list2cmdline([str(pythonw if pythonw.is_file() else sys.executable),
                                     str(Path(__file__).resolve()), "executar", id_])
    nome = f"pcam_{id_}"
    usuario = os.environ.get("USERNAME") or "alvo"
    rc, saida = _rodar(["schtasks", "/Create", "/F", "/TN", nome, "/TR", linha, "/SC", "ONCE",
                        "/ST", "23:59", "/RU", usuario, "/IT"], prazo=60)
    if rc != 0:
        return {"ok": False, "erro": f"schtasks /Create falhou: {saida[-300:]}"}
    rc, saida = _rodar(["schtasks", "/Run", "/TN", nome], prazo=60)
    if rc != 0:
        return {"ok": False, "erro": f"schtasks /Run falhou: {saida[-300:]}"}
    (pasta / "tarefa.txt").write_text(nome)
    return {"ok": True, "pid": None, "sessao": "console"}


def _matar_arvore(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True,
                       creationflags=NO_WINDOW)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def executar(id_: str) -> int:
    """O que roda desanexado: o comando do job, com prazo, log e fim.json."""
    pasta = _pasta_do(id_)
    job = json.loads((pasta / "job.json").read_text(encoding="utf-8"))
    _marcar_ativo(job, os.getpid())
    marca = base() / "ativos" / f"{id_}.json"
    inicio = time.monotonic()
    rc, motivo = None, ""
    medidor = None
    try:
        # {PY} e o python.exe mesmo quando o executor e o pythonw (sessao do
        # console): filho de pythonw sem handles derruba subprocess (WinError 6)
        console = Path(sys.executable).with_name("python.exe")
        py = str(console if console.is_file() else sys.executable)
        comando = [str(c).replace("{PY}", py).replace("{BASE}", str(base()))
                   for c in job["comando"]]
        cwd = _dentro(job.get("cwd") or ".")
        with open(pasta / "log.txt", "wb") as log:
            try:
                # Prioridade ABAIXO DO NORMAL (os filhos herdam): com o i3 a
                # 100%, o tailscaled e o sshd do am paravam de responder e o
                # SSH daqui dava "Connection timed out" no meio do trabalho
                # (19/10/2026, no duelo e na gravacao do Blue Lock).
                prioridade = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
                proc = subprocess.Popen(comando, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW | prioridade,
                                        env=_ambiente(job.get("env")))
            except OSError as exc:
                rc, motivo = 127, f"nao rodou: {exc}"
            else:
                (pasta / "pid.txt").write_text(str(proc.pid))
                medidor = Medidor(proc.pid)
                try:
                    rc = proc.wait(timeout=float(job.get("prazo_s") or 3600))
                except subprocess.TimeoutExpired:
                    _matar_arvore(proc.pid)
                    proc.wait(timeout=60)
                    rc, motivo = 124, f"prazo de {job.get('prazo_s')} s estourado no am"
    except Exception as exc:                                   # noqa: BLE001
        rc, motivo = 1, f"{type(exc).__name__}: {exc}"
    finally:
        fim = {"rc": rc, "motivo": motivo, "segundos": round(time.monotonic() - inicio, 1),
               "fim": datetime.now().isoformat(timespec="seconds"), "tipo": job.get("tipo")}
        if medidor is not None:
            try:
                fim.update(medidor.fim())
            except Exception:                                  # noqa: BLE001
                pass
        temporario = pasta / "fim.json.tmp"
        temporario.write_text(json.dumps(fim), encoding="utf-8")
        os.replace(temporario, pasta / "fim.json")
        try:
            marca.unlink()
        except OSError:
            pass
    return 0


def _apagar_tarefa(pasta: Path) -> None:
    """A tarefa /IT da sessao do console. Quem a apaga e o lado do SSH (com o
    token de administrador que a criou): o executor, na sessao do console,
    roda com o token filtrado do UAC e nao consegue (19/10/2026)."""
    tarefa = pasta / "tarefa.txt"
    if tarefa.is_file():
        rc, _ = _rodar(["schtasks", "/Delete", "/F", "/TN", tarefa.read_text().strip()], prazo=60)
        if rc == 0:
            tarefa.unlink()


def acao_estado(p: dict) -> dict:
    """O fim do trabalho, se ja houver. Com `ate_s`, ESPERA ate la (uma
    conexao so no lugar de dezenas de perguntas)."""
    pasta = _pasta_do(p["id"])
    fim = pasta / "fim.json"
    prazo = time.monotonic() + min(float(p.get("ate_s") or 0), 110)
    def vivo() -> bool:
        return any(a.get("id") == p["id"] for a in ativos())

    while not fim.is_file() and time.monotonic() < prazo:
        if not vivo() and time.time() - (pasta / "job.json").stat().st_mtime > 120:
            break
        time.sleep(1)
    if fim.is_file():
        try:
            dados = json.loads(fim.read_text(encoding="utf-8"))
        except ValueError:
            dados = None
        if dados is not None:
            _apagar_tarefa(pasta)
            return {"ok": True, "fim": dados}
    rodando = vivo()
    if not rodando and (pasta / "job.json").is_file():
        # o executor ainda nao escreveu o ativo.json (acabou de nascer) ou morreu
        idade = time.time() - (pasta / "job.json").stat().st_mtime
        if idade > 120:
            return {"ok": True, "fim": {"rc": 1, "motivo": "o executor do am morreu sem fim.json"}}
        rodando = True
    return {"ok": True, "fim": None, "rodando": rodando}


def acao_log(p: dict) -> dict:
    caminho = _pasta_do(p["id"]) / "log.txt"
    try:
        dados = caminho.read_bytes()
    except OSError:
        return {"ok": True, "log": ""}
    return {"ok": True, "log": dados[-int(p.get("bytes", 6000)):].decode("utf-8", "replace")}


def acao_matar(p: dict) -> dict:
    pasta = _pasta_do(p["id"])
    try:
        pid = int((pasta / "pid.txt").read_text())
    except (OSError, ValueError):
        return {"ok": True, "matou": False}
    _matar_arvore(pid)
    return {"ok": True, "matou": True}


ACOES = {"saude": acao_saude, "sincronizar": acao_sincronizar, "listar": acao_listar,
         "apagar": acao_apagar, "pastas": acao_pastas, "achar": acao_achar,
         "desempacotar": acao_desempacotar, "lancar": acao_lancar, "estado": acao_estado, "log": acao_log,
         "matar": acao_matar}


def chamar(acao: str, parametros: dict) -> dict:
    """Ponto de entrada comum (o SSH e o duble dos testes passam por aqui)."""
    esperada = parametros.pop("_versao", None)
    if esperada and esperada != versao():
        return {"ok": False, "versao_errada": True, "versao": versao()}
    try:
        return ACOES[acao](parametros)
    except KeyError as exc:
        if acao not in ACOES:
            return {"ok": False, "erro": f"acao desconhecida: {acao}"}
        return {"ok": False, "erro": f"faltou o parametro {exc}"}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "executar":
        return executar(argv[1])
    acao = argv[0] if argv else ""
    bruto = argv[1] if len(argv) > 1 else ""
    if bruto.startswith("@"):
        # parametro grande demais para a linha do cmd (8191): veio por arquivo
        arquivo = _dentro(bruto[1:])
        parametros = json.loads(arquivo.read_text(encoding="utf-8"))
        try:
            arquivo.unlink()
        except OSError:
            pass
    else:
        parametros = json.loads(base64.b64decode(bruto).decode("utf-8")) if bruto else {}
    resposta = chamar(acao, parametros)
    sys.stdout.write("\n" + MARCA + json.dumps(resposta, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
