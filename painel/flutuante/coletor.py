# -*- coding: utf-8 -*-
"""Quem le o disco. Uma thread, uma fila, e nenhum widget.

A REGRA DO PAINEL, repetida aqui porque e ela que mantem a janela viva:
a thread trabalhadora so PUBLICA na fila; quem desenha le a fila na thread
da interface, com `after()`. `after()` chamado de outra thread quebra o Tk.

Quatro ritmos, porque as fontes custam diferente:

  rapido     diario, travas, ledgers, logs          2-4 s (so leitura local)
  processos  quem esta rodando (Get-CimInstance)    15 s  (um powershell)
  previsao   o que sai no proximo horario           10 min, ou quando pedem
             (subprocesso `painel.flutuante.previsao`, ~2 s)
  tarefas    o Agendador ainda abre console?        5 min (Get-ScheduledTask)
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import dados, tarefas
from .caminhos import Caminhos

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PRIORIDADE_BAIXA = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)

RITMO_S = 3.0
RITMO_ESCONDIDO_S = 10.0
PROCESSOS_S = 15.0
PREVISAO_S = 600.0
TAREFAS_S = 300.0
LINHAS_DE_TERMINAL = 220

_PS_PROCESSOS = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
    "Select-Object ProcessId,ParentProcessId,CommandLine,"
    "@{n='Inicio';e={$_.CreationDate.ToString('s')}} | "
    "ConvertTo-Json -Compress")


def listar_processos(timeout: float = 60.0) -> list[dict] | None:
    """Os pythons vivos, com linha de comando. None se nao deu para ver."""
    if os.name != "nt":
        return None
    try:
        feito = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             _PS_PROCESSOS],
            capture_output=True, timeout=timeout,
            creationflags=SEM_JANELA | PRIORIDADE_BAIXA)
    except (OSError, subprocess.SubprocessError):
        return None
    texto = feito.stdout.decode("utf-8", errors="replace").strip()
    return dados.ler_processos_json(texto) if texto else []


def pasta_do_pacote() -> Path:
    """A pasta que CONTEM o pacote `painel` (o cwd do subprocesso)."""
    import painel
    return Path(painel.__file__).resolve().parent.parent


def rodar_previsao(raiz: Path, timeout: float = 180.0) -> dict:
    try:
        feito = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "painel.flutuante.previsao",
             "--raiz", str(raiz)],
            cwd=str(pasta_do_pacote()), capture_output=True, timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=SEM_JANELA | PRIORIDADE_BAIXA)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"falhou": f"{type(exc).__name__}: {exc}"}
    linhas = feito.stdout.decode("utf-8", errors="replace").strip().splitlines()
    for linha in reversed(linhas):
        if linha.startswith("{"):
            try:
                return json.loads(linha)
            except ValueError:
                break
    erro = feito.stderr.decode("utf-8", errors="replace").strip()
    return {"falhou": (erro.splitlines() or ["sem resposta"])[-1][:200]}


class _PorData:
    """Le um arquivo so quando ele mudou (mtime + tamanho)."""

    def __init__(self, ler):
        self._ler = ler
        self._marca: dict = {}
        self._valor: dict = {}

    def __call__(self, caminho: Path, padrao=None):
        try:
            info = caminho.stat()
            marca = (info.st_mtime_ns, info.st_size)
        except OSError:
            self._marca.pop(caminho, None)
            self._valor.pop(caminho, None)
            return padrao
        if self._marca.get(caminho) != marca:
            self._valor[caminho] = self._ler(caminho)
            self._marca[caminho] = marca
        return self._valor[caminho]

    def mtime(self, caminho: Path) -> float | None:
        marca = self._marca.get(caminho)
        return marca[0] / 1e9 if marca else None


class Coletor:
    """Monta o ESTADO inteiro e entrega pela fila. Nunca toca em widget."""

    def __init__(self, caminhos: Caminhos | None = None,
                 fila: queue.Queue | None = None, *, processos=None,
                 previsao=None, agendador=None):
        self.caminhos = caminhos or Caminhos()
        self.fila = fila or queue.Queue()
        self._listar = processos or listar_processos
        self._prever = previsao or (lambda: rodar_previsao(self.caminhos.raiz))
        self._ler_agendador = agendador or tarefas.ler_tarefas
        self._tarefas: dict | None = None
        self._tarefas_em = -TAREFAS_S
        self._parar = threading.Event()
        self._acordar = threading.Event()
        self._ritmo = RITMO_S
        self._processos: list | None = None
        self._processos_em = 0.0
        self._previsao: dict = {}
        self._previsao_em: datetime | None = None
        self._previsao_rodando = False
        self._previsao_ultima = -PREVISAO_S
        self._ledgers = _PorData(dados.ler_ledger)
        self._terminais = _PorData(self._ler_terminal)
        self._thread: threading.Thread | None = None
        self._rodando: set = set()

    # ------------------------------------------------------------ ciclo
    def iniciar(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._laco, daemon=True,
                                            name="flutuante-coletor")
            self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        self._acordar.set()

    def ritmo(self, escondido: bool) -> None:
        self._ritmo = RITMO_ESCONDIDO_S if escondido else RITMO_S

    def agora(self) -> None:
        """Le de novo ja (depois de trocar de tamanho, por exemplo)."""
        self._acordar.set()

    def pedir_previsao(self) -> None:
        self._previsao_ultima = -PREVISAO_S
        self._acordar.set()

    def _laco(self) -> None:
        while not self._parar.is_set():
            self._talvez_processos()
            self._talvez_tarefas()
            self._talvez_previsao()
            try:
                self.fila.put(("estado", self.coletar()))
            except Exception as exc:                         # noqa: BLE001
                self.fila.put(("falha", f"{type(exc).__name__}: {exc}"))
            self._acordar.wait(self._ritmo)
            self._acordar.clear()

    # OS POWERSHELL RODAM A PARTE. Medido em 17/09/2026 com a maquina
    # ocupada: o Get-CimInstance levou 19 s. Enquanto ele rodava dentro do
    # laco, a janela abria VAZIA (nem diario, nem Vila) ate ele voltar.
    def _em_paralelo(self, nome: str, trabalho) -> None:
        if nome in self._rodando:
            return
        self._rodando.add(nome)

        def rodar():
            try:
                trabalho()
            except Exception:                                # noqa: BLE001
                pass
            finally:
                self._rodando.discard(nome)
                self._acordar.set()

        threading.Thread(target=rodar, daemon=True,
                         name=f"flutuante-{nome}").start()

    def _talvez_processos(self, esperar: bool = False) -> None:
        if time.monotonic() - self._processos_em < PROCESSOS_S \
                and self._processos is not None:
            return
        self._processos_em = time.monotonic()

        def ler():
            lista = self._listar()
            if lista is not None:
                self._processos = lista

        if esperar:
            ler()
        else:
            self._em_paralelo("processos", ler)

    def _talvez_tarefas(self, esperar: bool = False) -> None:
        if time.monotonic() - self._tarefas_em < TAREFAS_S:
            return
        self._tarefas_em = time.monotonic()

        def ler():
            try:
                self._tarefas = tarefas.examinar(self._ler_agendador())
            except Exception:                                # noqa: BLE001
                self._tarefas = tarefas.examinar(None)

        if esperar:
            ler()
        else:
            self._em_paralelo("tarefas", ler)

    def _talvez_previsao(self) -> None:
        if self._previsao_rodando:
            return
        if time.monotonic() - self._previsao_ultima < PREVISAO_S:
            return
        self._previsao_rodando = True
        self._previsao_ultima = time.monotonic()

        def trabalho():
            try:
                resultado = self._prever()
            except Exception as exc:                         # noqa: BLE001
                resultado = {"falhou": f"{type(exc).__name__}: {exc}"}
            self._previsao = resultado or {}
            self._previsao_em = datetime.now()
            self._previsao_rodando = False
            self._acordar.set()

        threading.Thread(target=trabalho, daemon=True,
                         name="flutuante-previsao").start()

    # ---------------------------------------------------------- leitura
    @staticmethod
    def _ler_terminal(caminho: Path) -> list:
        linhas = dados.ler_cauda(caminho, 64_000)[-LINHAS_DE_TERMINAL:]
        return [(l, dados.classificar_linha(l)) for l in linhas]

    def coletar(self, agora: datetime | None = None,
                agora_utc: datetime | None = None) -> dict:
        agora = agora or datetime.now()
        agora_utc = agora_utc or datetime.now(timezone.utc)
        c = self.caminhos
        eventos = dados.ler_diario(c.diario)
        ocupadas = dados.travas_ocupadas(c.travas)
        processos = self._processos or []
        # Quem esta na lista de processos esta vivo, sem perguntar de novo.
        pids = {p["pid"] for p in processos}

        def vivo(pid):
            try:
                if int(pid) in pids:
                    return True
            except (TypeError, ValueError):
                pass
            return dados._pid_vivo(pid)

        abertos = dados.trabalhos_abertos(eventos, agora_utc, vivo=vivo)
        erros = dados.erros_recentes(eventos, agora_utc)
        recentes = dados.atividade_recente(eventos, agora_utc, vivo=vivo)
        por_canal = {canal: self._ledgers(caminho, [])
                     for canal, caminho in c.ledgers.items()}
        terminais = {nome: self._terminais(caminho, [])
                     for nome, caminho in c.terminais.items()}

        relatorios = dados.ler_json(c.relatorios, {}) or {}
        bot_txt = c.terminais["bot"]
        bot_vivo = "remoto__bot" in ocupadas or any(
            (dados.classificar_processo(p["cmd"]) or {}).get("tipo") == "bot"
            for p in processos)
        linhas_bot = [l for l, _m in terminais.get("bot") or [] if l.strip()]
        try:
            bot_mexeu = datetime.fromtimestamp(bot_txt.stat().st_mtime)
        except OSError:
            bot_mexeu = None
        bot_proc = next((p for p in processos
                         if (dados.classificar_processo(p["cmd"]) or {})
                         .get("tipo") == "bot"), None)

        estado = {
            "agora": agora,
            "diario_ok": c.diario.is_file(),
            "feed": [dados.linha_do_diario(e) for e in eventos[-90:]],
            "abertos": abertos,
            "erros": erros,
            "ocupadas": ocupadas,
            "travas": [t for t in (dados.ler_trava(n) for n in ocupadas) if t],
            "predios": dados.estado_dos_predios(
                abertos, erros, ocupadas, recentes,
                dados.ultimo_status_por_predio(eventos)),
            "processos_conhecidos": self._processos is not None,
            "vivos": dados.linhas_vivas(processos, abertos, agora,
                                        os.getpid(), eventos, agora_utc),
            "publicados": dados.ultimos_publicados(por_canal, 5),
            "publicados_hoje": dados.publicados_no_dia(
                por_canal, agora.date().isoformat()),
            "terminais": terminais,
            "bot": {
                "vivo": bot_vivo,
                "desde": (bot_proc or {}).get("inicio"),
                "relatorios": relatorios,
                "ultima_linha": linhas_bot[-1] if linhas_bot else "",
                "mexeu": bot_mexeu,
            },
            "previsao": dict(self._previsao),
            "previsao_em": self._previsao_em,
            "previsao_rodando": self._previsao_rodando,
            "proximo": dados.proximo_horario(agora),
            "tarefas": self._tarefas,
        }
        estado["resumo"] = dados.resumo(estado)
        return estado


__all__ = ["Coletor", "listar_processos", "rodar_previsao"]
