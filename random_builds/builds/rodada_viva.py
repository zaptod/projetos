# -*- coding: utf-8 -*-
"""A ficha de uma RODADA LONGA (criacao de historias, geracao de builds).

SCR-7 da auditoria profunda (14/10/2026). As rodadas `main.py auto` (historias)
e `main.py noite` (builds) seguram uma trava de arquivo da faixa
(`historias__auto`, `builds__gerar`) pelo tempo que trabalharem. Quando uma
delas PENDURA — a de 12/10, pid 4332, ficou presa no Gemini as 13:09:33 e
nao escreveu mais nada —, a trava fica com ela: os disparos seguintes saem
"ja tem uma rodada em andamento" e ninguem mata o Python. Aquela segurou a
trava 31 h, ate o PC cair.

Esta ficha e o que permite a alguem de FORA (o vigia do coordenador,
`coordenador/vigia_rodadas.py`) separar a rodada lenta da pendurada:

    <runtime>/rodadas/<pid>.json
    {"pid", "inicio" (epoch), "trava", "rotulo", "pulso" (epoch), "argv"}

A ficha nasce quando a rodada PEGA a trava (`with rodada(...)`) e some quando
ela solta. O PULSO e renovado por toda linha que a rodada escreve no seu log
(`pulsar()`, chamado pelos diarios `_SaidaNoDiario` das historias e
`_Diario` dos builds, e pelo laco do supervisor das faixas), no maximo a cada
`PULSO_MIN_S`. Rodada que fala nao morre, por mais longa que seja; a que
calou por `LIMITE_SEM_PULSO_MIN` morre.

Nunca levanta: a ficha e para o vigia, e uma ficha que nao grava nao pode
derrubar a rodada que ela vigia.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# Pulso gravado no maximo a cada tanto (o diario escreve muitas linhas).
PULSO_MIN_S = 30.0
# Quanto tempo CALADA uma rodada pode ficar antes de o vigia a encerrar.
# Medido em 14/10/2026 nos logs de setembro-outubro, trechos calados DENTRO
# de uma rodada que andava: historias ate 22,6 min (render), builds ate
# 43,4 min (som + render, 05/10). A pendurada de 12/10 calou 31 h; a de
# 20/09, 598 min. 120 min = 2,8x o pior saudavel medido.
LIMITE_SEM_PULSO_MIN = 120

_ativa: dict = {}
_trava = threading.Lock()


def pasta() -> Path:
    from .contas import runtime_dir
    return runtime_dir() / "rodadas"


def _arquivo(pid: int | None = None) -> Path:
    return pasta() / f"{int(pid or os.getpid())}.json"


def _gravar(ficha: dict) -> None:
    destino = _arquivo(ficha.get("pid"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(ficha, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, destino)


@contextmanager
def rodada(trava: str, rotulo: str = ""):
    """Marca ESTE processo como dono de uma rodada longa enquanto o bloco roda.

    Use logo depois de pegar a trava da faixa. Reentrante: o bloco de dentro
    nao troca a ficha de fora.
    """
    dono = False
    try:
        with _trava:
            if not _ativa:
                agora = time.time()
                _ativa.update({"pid": os.getpid(), "inicio": agora,
                               "trava": str(trava), "rotulo": str(rotulo or trava),
                               "pulso": agora, "argv": list(sys.argv)[:12]})
                dono = True
                _gravar(dict(_ativa))
    except Exception:                                          # noqa: BLE001
        pass
    try:
        yield
    finally:
        if dono:
            with _trava:
                _ativa.clear()
            try:
                _arquivo().unlink()
            except OSError:
                pass


def pulsar(agora: float | None = None) -> bool:
    """Renova o pulso da rodada deste processo (se houver). True se gravou."""
    if not _ativa:
        return False
    agora = time.time() if agora is None else float(agora)
    try:
        with _trava:
            if not _ativa or agora - float(_ativa.get("pulso") or 0) < PULSO_MIN_S:
                return False
            _ativa["pulso"] = agora
            copia = dict(_ativa)
        _gravar(copia)
        return True
    except Exception:                                          # noqa: BLE001
        return False


def fichas() -> list[dict]:
    """As fichas que estao no disco (as ilegiveis vem com `ilegivel`)."""
    saida = []
    try:
        arquivos = sorted(pasta().glob("*.json"))
    except OSError:
        return saida
    for arquivo in arquivos:
        try:
            ficha = json.loads(arquivo.read_text(encoding="utf-8"))
            if not isinstance(ficha, dict):
                raise ValueError("ficha nao e objeto")
        except (OSError, ValueError) as exc:
            ficha = {"ilegivel": f"{type(exc).__name__}: {exc}"[:120]}
        ficha["_arquivo"] = str(arquivo)
        saida.append(ficha)
    return saida


__all__ = ["LIMITE_SEM_PULSO_MIN", "PULSO_MIN_S", "fichas", "pasta", "pulsar",
           "rodada"]
