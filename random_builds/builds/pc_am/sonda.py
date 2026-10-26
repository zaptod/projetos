# -*- coding: utf-8 -*-
"""A SONDA do PC am: "ele esta disponivel agora?" — barata, com cache.

Ponto 9 do pedido de 26/10/2026: o sistema tem de perceber SOZINHO se o am
esta de pe, e mandar o pesado para la; desligado, tudo roda aqui sem erro e
sem alarme (so uma linha de log). Quem decide e esta sonda; ninguem mais
precisa pagar o timeout de um SSH para um PC desligado.

Tres estados:

  disponivel    o SSH responde e nao ha trabalho no limite de vagas (`paralelo.maximo`, 1)
  ocupado       o SSH responde, mas o am ja esta no limite de trabalhos
  indisponivel  nao conectou (desligado, sem rede, Tailscale fora, chave recusada)

O custo: UMA chamada `ssh` com `BatchMode=yes` e `ConnectTimeout` curto
(`sonda.connect_s`, 4 s) que roda um `echo` e lista a pasta `ativos` do am
(nenhum Python la). So se aparecer trabalho ativo e que se pergunta ao agente
(`saude`) se o pid esta vivo — o arquivo pode ter sobrado de uma queda.

O cache (`%LOCALAPPDATA%\\neural-fights\\pc_am\\sonda.json`) vale
`sonda.validade_s` (45 s) para disponivel/ocupado e `sonda.validade_fora_s`
(90 s) para indisponivel: o am desligado custa uma sonda a cada 90 s, nao um
timeout por trabalho; o am que liga e notado em ate 90 s.

    python -m builds.pc_am sonda            # sonda (usa o cache)
    python -m builds.pc_am sonda --agora    # ignora o cache
    python -m builds.pc_am sonda --curto    # uma linha, so le o cache se estiver fresco
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import maquina

DISPONIVEL, OCUPADO, INDISPONIVEL = "disponivel", "ocupado", "indisponivel"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PADRAO = {"connect_s": 4, "prazo_s": 12, "validade_s": 45, "validade_fora_s": 90}
_ROTULO = {DISPONIVEL: "disponível", OCUPADO: "ocupado", INDISPONIVEL: "indisponível"}


def config(cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else maquina.carregar_config()
    dados = dict(PADRAO)
    if isinstance(cfg.get("sonda"), dict):
        dados.update({k: v for k, v in cfg["sonda"].items() if not str(k).startswith("_")})
    return dados


def arquivo() -> Path:
    return maquina.runtime() / "sonda.json"


def _ler() -> dict:
    try:
        dados = json.loads(arquivo().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados: dict) -> None:
    caminho = arquivo()
    temporario = caminho.with_suffix(f".{uuid.uuid4().hex[:6]}.tmp")
    try:
        temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        os.replace(temporario, caminho)
    except OSError:
        pass                                  # cache e conforto, nunca motivo de erro


def _fresco(dados: dict, cfg: dict, agora: float) -> bool:
    estado = dados.get("estado")
    if estado not in _ROTULO or not isinstance(dados.get("em"), (int, float)):
        return False
    validade = cfg["validade_fora_s"] if estado == INDISPONIVEL else cfg["validade_s"]
    return 0 <= agora - dados["em"] < float(validade)


def ssh_barato(cfg_am: dict, sonda: dict) -> tuple[bool, str, int]:
    """(conectou, motivo, trabalhos_ativos_vistos). Uma chamada ssh, sem Python la."""
    base = str(cfg_am.get("pasta") or "C:/nf").replace("/", "\\").rstrip("\\")
    comando = (f"echo PCAM_OK& if exist {base}\\ativos\\*.json echo ATIVOS"
               f"& if exist {base}\\ativo.json echo ATIVOS")
    alvo = f"{cfg_am['usuario']}@{cfg_am['host']}"
    opcoes = ["-i", os.path.expanduser(cfg_am["chave_ssh"]), "-o", "BatchMode=yes", "-o", "LogLevel=ERROR",
              "-o", f"ConnectTimeout={int(sonda['connect_s'])}", "-o", "ServerAliveInterval=5",
              "-o", "ServerAliveCountMax=2", "-o", "StrictHostKeyChecking=accept-new"]
    try:
        proc = subprocess.run(["ssh", *opcoes, alvo, comando], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=float(sonda["prazo_s"]),
                              creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"o SSH nao respondeu em {sonda['prazo_s']} s", 0
    except OSError as exc:
        return False, f"sem ssh neste PC: {exc}", 0
    saida = proc.stdout or ""
    if proc.returncode != 0 or "PCAM_OK" not in saida:
        resto = ((proc.stderr or "") + saida).strip().splitlines()
        return False, (resto[-1][:160] if resto else f"ssh rc {proc.returncode}"), 0
    return True, "", saida.count("ATIVOS")


def _ativos_de_verdade(cfg_am: dict) -> int:
    """Quantos trabalhos estao VIVOS no am (o agente confere o pid)."""
    t = maquina.TransporteSsh(cfg_am)
    saude = t.chamar("saude", {"cpu_s": 0}, prazo=float(cfg_am.get("prazo_ssh_s") or 25) + 10)
    vivos = saude.get("ativos")
    if isinstance(vivos, list):
        return len(vivos)
    return 1 if saude.get("ativo") else 0


def sondar(cfg: dict | None = None, *, forcar: bool = False, ssh: Callable | None = None,
           confirmar: Callable | None = None, agora: Callable = time.time) -> dict:
    """{estado, motivo, em, idade_s, do_cache}. Nunca levanta."""
    cfg_am = cfg if cfg is not None else maquina.carregar_config()
    s = config(cfg_am)
    t0 = agora()
    antigo = _ler()
    if not forcar and _fresco(antigo, s, t0):
        return {**antigo, "idade_s": round(t0 - antigo["em"], 1), "do_cache": True}
    try:
        conectou, motivo, vistos = (ssh or ssh_barato)(cfg_am, s)
        estado = INDISPONIVEL
        if conectou:
            estado, motivo = DISPONIVEL, ""
            if vistos:
                try:
                    vivos = (confirmar or _ativos_de_verdade)(cfg_am)
                except Exception:                              # noqa: BLE001
                    vivos = vistos                 # nao deu para conferir: confia no arquivo
                if vivos >= int(maquina.paralelo(cfg_am)["maximo"]):
                    estado, motivo = OCUPADO, f"{vivos} trabalho(s) rodando no am"
    except Exception as exc:                                   # noqa: BLE001
        estado, motivo = INDISPONIVEL, f"{type(exc).__name__}: {exc}"[:160]
    dados = {"estado": estado, "motivo": motivo, "em": t0,
             "quando": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
             "antes": antigo.get("estado")}
    _gravar(dados)
    return {**dados, "idade_s": 0.0, "do_cache": False}


def marcar(estado: str, motivo: str = "", agora: Callable = time.time) -> None:
    """Quem descobriu o estado de outro jeito (o SSH caiu no meio de um
    trabalho) corrige o cache: o proximo trabalho nao paga o mesmo timeout."""
    if estado not in _ROTULO:
        return
    antigo = _ler()
    t0 = agora()
    _gravar({"estado": estado, "motivo": motivo[:160], "em": t0,
             "quando": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
             "antes": antigo.get("estado")})


def ultima() -> dict:
    """O ultimo estado gravado, SEM sondar (para tela e retrato). Vazio = nunca."""
    dados = _ler()
    if dados.get("estado") not in _ROTULO:
        return {}
    return {**dados, "idade_s": round(max(0.0, time.time() - float(dados.get("em") or 0)), 1)}


def texto(r: dict) -> str:
    """A linha para humanos (retrato do handoff, status do coordenador)."""
    if not r:
        return "PC am: sem sonda ainda"
    estado = r.get("estado")
    idade = r.get("idade_s")
    quando = ""
    if isinstance(idade, (int, float)):
        quando = (f" (sonda há {int(idade)} s)" if idade < 600 else
                  f" (sonda VELHA, há {int(idade // 60)} min: rode `python -m builds.pc_am sonda`)")
    extra = f" — {r['motivo']}" if r.get("motivo") else ""
    destino = {DISPONIVEL: "o pesado elegível vai para lá",
               OCUPADO: "o pesado espera a vez ou roda aqui",
               INDISPONIVEL: "o pesado roda neste PC"}.get(estado, "")
    return f"PC am: {_ROTULO.get(estado, '?')}{quando}{extra}; {destino}"
