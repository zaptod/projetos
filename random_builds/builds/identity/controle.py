# -*- coding: utf-8 -*-
"""Controle da pipeline: pausar, retomar e parar SEM matar processo.

As ferramentas de video (Digen, PicassoIA) sao contas COMPARTILHADAS. Quando
outra pessoa esta usando, a pipeline precisa parar de pegar trabalho — e
matar o processo no meio de um job e a pior forma de fazer isso: perde a
geracao que ja foi paga, deixa o job `running` orfao e o Chrome segurando o
perfil (foi assim que a generation_00075 ficou pela metade em 29/08/2026).

Este modulo e o interruptor que faltava, com tres estados:

    PAUSADO   o worker nao PEGA job novo; o que esta em andamento termina.
              Pode valer para tudo ou so para um provedor ("o Digen esta
              ocupado, mas as imagens do Picasso podem continuar"), e pode
              ter prazo ("pausa por 2h") — vencido o prazo, volta sozinho.

    PARANDO   alguem pediu que o worker ENCERRE. Ele termina o job atual,
              fecha o browser e sai. Nada de processo morto no meio.

    RODANDO   o normal.

O estado vive em `outputs/_identity/controle.json` — um arquivo, para que a
CLI, o painel e o worker (processos diferentes) leiam o mesmo interruptor.
Quem escreve e a CLI/painel; quem obedece e a fila (`queue.claim`) e o
worker.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import config

ARQUIVO = config.IDENTITY_DIR / "controle.json"

# Provedores que podem ser pausados separadamente. "tudo" pausa a pipeline.
TUDO = "tudo"

RODANDO, PAUSADO, PARANDO = "rodando", "pausado", "parando"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _ler() -> dict:
    try:
        with open(ARQUIVO, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados: dict) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def _vencida(pausa: dict) -> bool:
    """A pausa tinha prazo e ele passou?"""
    ate = pausa.get("ate")
    if not ate:
        return False
    try:
        prazo = datetime.fromisoformat(str(ate))
    except ValueError:
        return False
    if prazo.tzinfo is None:
        prazo = prazo.replace(tzinfo=timezone.utc)
    return _agora() >= prazo


def estado() -> dict:
    """O estado atual, ja com as pausas vencidas descartadas.

    Devolve sempre as mesmas chaves — quem desenha a tela nao precisa de
    defensiva: `situacao` (rodando/pausado/parando), `pausas` (por alvo),
    `parada` (pedido de encerramento) e `resumo` (uma linha em portugues).
    """
    dados = _ler()
    pausas = {alvo: pausa for alvo, pausa in (dados.get("pausas") or {}).items()
              if not _vencida(pausa)}
    if pausas != (dados.get("pausas") or {}):
        # Limpa o vencido no disco: assim o painel nao fica mostrando uma
        # pausa que ja expirou so porque ninguem tocou no arquivo.
        dados["pausas"] = pausas
        _gravar(dados)
    parada = dados.get("parada") or None
    if parada:
        situacao = PARANDO
    elif pausas:
        situacao = PAUSADO
    else:
        situacao = RODANDO
    return {"situacao": situacao, "pausas": pausas, "parada": parada,
            "resumo": _resumo(situacao, pausas, parada)}


def _resumo(situacao: str, pausas: dict, parada: dict | None) -> str:
    if situacao == PARANDO:
        motivo = (parada or {}).get("motivo") or ""
        return "parando: o worker encerra depois do job atual" + (
            f" ({motivo})" if motivo else "")
    if situacao == RODANDO:
        return "rodando normalmente"
    partes = []
    for alvo, pausa in sorted(pausas.items()):
        nome = "tudo" if alvo == TUDO else alvo
        detalhe = pausa.get("motivo") or "sem motivo anotado"
        if pausa.get("ate"):
            detalhe += f", volta {_quando(pausa['ate'])}"
        partes.append(f"{nome} ({detalhe})")
    return "pausado: " + "; ".join(partes)


def _quando(iso: str) -> str:
    try:
        prazo = datetime.fromisoformat(str(iso))
    except ValueError:
        return "?"
    if prazo.tzinfo is None:
        prazo = prazo.replace(tzinfo=timezone.utc)
    faltam = (prazo - _agora()).total_seconds()
    if faltam <= 0:
        return "agora"
    if faltam < 3600:
        return f"em {faltam / 60:.0f}min"
    return f"em {faltam / 3600:.1f}h"


# ------------------------------------------------------------------ pausar
def pausar(alvo: str = TUDO, motivo: str = "", minutos: float | None = None) -> dict:
    """Para de PEGAR trabalho. O job em andamento termina normalmente.

    `alvo` e "tudo" ou o nome do provedor (digen, picasso). `minutos` faz a
    pausa expirar sozinha — o caso comum de conta compartilhada ("empresta
    por uma hora") sem depender de alguem lembrar de retomar.
    """
    dados = _ler()
    pausas = dados.get("pausas") or {}
    pausa = {"desde": _agora().isoformat(timespec="seconds"),
             "motivo": str(motivo or "").strip()}
    if minutos:
        pausa["ate"] = (_agora() + timedelta(minutes=float(minutos))
                        ).isoformat(timespec="seconds")
    pausas[str(alvo)] = pausa
    dados["pausas"] = pausas
    _gravar(dados)
    return estado()


def retomar(alvo: str | None = None) -> dict:
    """Tira a pausa de `alvo` (ou todas, sem argumento) e cancela a parada."""
    dados = _ler()
    pausas = dados.get("pausas") or {}
    if alvo is None:
        pausas = {}
    else:
        pausas.pop(str(alvo), None)
        if str(alvo) == TUDO:
            pausas = {}
    dados["pausas"] = pausas
    dados["parada"] = None
    _gravar(dados)
    return estado()


def pausado_para(provedor: str | None = None) -> bool:
    """A pipeline esta impedida de pegar trabalho DESTE provedor?"""
    atual = estado()
    if atual["situacao"] == PARANDO:
        return True
    pausas = atual["pausas"]
    if TUDO in pausas:
        return True
    return bool(provedor and provedor in pausas)


# ------------------------------------------------------------------- parar
def pedir_parada(motivo: str = "") -> dict:
    """Pede que o worker ENCERRE depois do job atual (parada limpa)."""
    dados = _ler()
    dados["parada"] = {"desde": _agora().isoformat(timespec="seconds"),
                       "motivo": str(motivo or "").strip()}
    _gravar(dados)
    return estado()


def parada_pedida() -> bool:
    return estado()["situacao"] == PARANDO


def limpar_parada() -> dict:
    """Chamado pelo worker ao sair: o pedido foi cumprido."""
    dados = _ler()
    dados["parada"] = None
    _gravar(dados)
    return estado()


__all__ = ["ARQUIVO", "PARANDO", "PAUSADO", "RODANDO", "TUDO", "estado",
           "limpar_parada", "parada_pedida", "pausado_para", "pausar",
           "pedir_parada", "retomar"]
