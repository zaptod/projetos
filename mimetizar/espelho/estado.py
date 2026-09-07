# -*- coding: utf-8 -*-
"""`_estado.json`: o que ja foi feito neste canal, e quando.

A retomada de verdade e o DISCO: se `medidas/<id>.json` existe, aquele video
ja foi medido, ponto. Este arquivo nao manda em nada disso — ele guarda o
resumo grosso (quando cada etapa rodou, quantos itens sairam, o que falhou)
para que `status` responda sem varrer milhares de arquivos, e para que o
painel tenha o que desenhar.

Duas regras, e as duas nasceram de defeito:

  NAO LEVANTA NA LEITURA. Um `_estado.json` truncado (processo morto no meio
  da escrita) nao pode impedir a ferramenta de rodar — o pior caso e recomecar
  a contagem, e isso e barato.

  ESCRITA ATOMICA. Grava num temporario e troca por `os.replace`. Sem isso,
  Ctrl+C na hora errada deixa meio JSON no lugar do arquivo bom.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ARQUIVO = "_estado.json"


def _agora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def caminho(pasta: Path) -> Path:
    return Path(pasta) / ARQUIVO


def ler(pasta: Path) -> dict:
    """O estado gravado, ou um estado vazio. Nunca levanta."""
    try:
        dados = json.loads(caminho(pasta).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"etapas": {}}
    if not isinstance(dados, dict):
        return {"etapas": {}}
    dados.setdefault("etapas", {})
    return dados


def gravar(pasta: Path, dados: dict) -> None:
    """Grava por troca atomica: ou o arquivo velho, ou o novo inteiro."""
    destino = caminho(pasta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    os.replace(temporario, destino)


def marcar(pasta: Path, etapa: str, **campos) -> dict:
    """Anota que `etapa` rodou agora, com o que ela quiser registrar."""
    dados = ler(pasta)
    registro = dados["etapas"].get(etapa, {})
    registro.update(campos)
    registro["em"] = _agora()
    dados["etapas"][etapa] = registro
    gravar(pasta, dados)
    return dados


def etapa(pasta: Path, nome: str) -> dict:
    """O que ficou registrado daquela etapa (vazio se nunca rodou)."""
    return ler(pasta)["etapas"].get(nome, {})
