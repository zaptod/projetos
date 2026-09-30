# -*- coding: utf-8 -*-
"""Quantas imagens as historias pediram ao PicassoIA hoje, e o teto do dia.

POR QUE EXISTE (30/09/2026). O trabalho pesado passou para o dia, em lote de
segunda a quarta (decisao do Adrian no Grimorio, `geral/lote-*`). O lote pede
~330 imagens por dia, contra 90 a 191 "prontas" por dia medidas nos logs de
20 a 30/09. A conta do PicassoIA e COMPARTILHADA com outras pessoas: uma
rodada que entrasse em laco (reenvio, refeita, recusa em cadeia) nao pode
esgotar a conta de quem mais usa. Entao ha um teto por dia, no config
(`config/imagens.json` -> `teto_de_imagens_por_dia`), e ao bater a geracao
PARA e avisa.

O QUE CONTA E O ENVIO, e nao a imagem aproveitada: cada envio gera uma imagem
do lado do site, mesmo a que a gente descarta (sem prova de origem, colagem
refeita, estouro de espera reenviado). Medido nos logs de 20-30/09: envios =
prontas + 10 a 30 % (recusas, reenvios, refeitas, sem prova).

Modulo LEVE de proposito: a agenda consulta o teto antes de decidir se cria,
e nao pode importar o navegador para isso.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONTADOR = RAIZ / "outputs" / "_picasso_por_dia.json"
CONFIG = RAIZ / "config" / "imagens.json"
# Quantos dias o contador guarda. So serve para conferir a semana do lote.
DIAS_GUARDADOS = 14


class TetoDoDia(RuntimeError):
    """O teto diario de envios ao PicassoIA foi atingido."""


def _hoje(agora: datetime | None = None) -> str:
    return (agora or datetime.now()).strftime("%Y-%m-%d")


def _ler() -> dict:
    try:
        with open(CONTADOR, encoding="utf-8") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def teto(config: dict | None = None) -> int:
    """O teto do dia. `0` = sem teto. Sem config legivel, sem teto.

    Um config que nao abre NAO pode parar a producao: o teto e protecao da
    conta, e ler errado o arquivo de protecao nao e motivo para o canal
    ficar sem video.
    """
    if config is None:
        try:
            with open(CONFIG, encoding="utf-8-sig") as fh:
                config = json.load(fh)
        except (OSError, ValueError):
            return 0
    try:
        return max(0, int(config.get("teto_de_imagens_por_dia") or 0))
    except (TypeError, ValueError):
        return 0


def usadas(agora: datetime | None = None) -> int:
    """Envios de hoje."""
    try:
        return int(_ler().get(_hoje(agora), 0))
    except (TypeError, ValueError):
        return 0


def batido(config: dict | None = None, agora: datetime | None = None) -> bool:
    limite = teto(config)
    return bool(limite) and usadas(agora) >= limite


def motivo(config: dict | None = None,
           agora: datetime | None = None) -> str | None:
    """Texto humano quando o teto esta batido; senao None."""
    limite = teto(config)
    if not limite:
        return None
    feitas = usadas(agora)
    if feitas < limite:
        return None
    return (f"teto diario do PicassoIA batido ({feitas} de {limite} envios "
            "hoje); a geracao volta amanha")


def contar(agora: datetime | None = None) -> int:
    """Soma um envio no dia. Nunca levanta: contar e protecao, nao trabalho."""
    agora = agora or datetime.now()
    dados = _ler()
    chave = _hoje(agora)
    try:
        dados[chave] = int(dados.get(chave, 0)) + 1
    except (TypeError, ValueError):
        dados[chave] = 1
    limite = (agora - timedelta(days=DIAS_GUARDADOS)).strftime("%Y-%m-%d")
    dados = {k: v for k, v in dados.items() if k >= limite}
    try:
        CONTADOR.parent.mkdir(parents=True, exist_ok=True)
        temporario = CONTADOR.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, indent=1, sort_keys=True),
                              encoding="utf-8")
        temporario.replace(CONTADOR)
    except OSError:
        pass
    return int(dados.get(chave, 0))


def conferir_antes_de_enviar(config: dict | None = None,
                             agora: datetime | None = None) -> None:
    """Levanta `TetoDoDia` se o proximo envio passaria do teto."""
    texto = motivo(config, agora)
    if texto:
        raise TetoDoDia(texto)
