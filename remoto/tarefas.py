# -*- coding: utf-8 -*-
"""Trabalho pesado pedido pelo celular: um processo por tarefa, com log.

O app ja fazia isso para publicar, e a forma provou-se: `publicacao_filha`
sobe o comando DESLIGADO do servidor (outro grupo, fora do job quando o
Windows deixa), manda a saida para um ARQUIVO e grava `fim.json` com o
codigo. O servidor pode cair, reiniciar ou ser fechado no meio — o trabalho
continua, e quem sobe depois le o mesmo arquivo.

Aqui isso vira geral: gerar historia, re-renderizar, processar fila,
escoar a grade. Cada tarefa e uma pasta:

    app_celular_tarefas/<chave>/
        tarefa.json   o que foi pedido, por quem, quando (e o PID)
        saida.log     tudo que o comando imprimiu
        filho.json    o PID do comando (a filha escreve)
        fim.json      o codigo de saida (a filha escreve no fim)

O app le `listar()` e `log(chave, desde)` — e e assim que da para acompanhar
uma geracao de 40 minutos do celular, em vez de ficar no escuro.

NAO EXISTE MATAR daqui: um `kill` no meio de um upload ou de uma geracao
deixa estado pela metade (foi o motivo de existir a parada limpa do
`controle`). Quem precisa parar usa Pausar/Parar, que o worker obedece.
"""
from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import runtime_dir

PASTA = None                       # os testes apontam para outro lugar
GUARDAR_DIAS = 7
LOG_MAX = 20000                    # bytes por leitura (o celular nao le mais)


def pasta_das_tarefas() -> Path:
    return Path(PASTA) if PASTA else runtime_dir() / "app_celular_tarefas"


def _ler_json(caminho: Path):
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    try:
        return json.loads(texto) if texto.strip() else None
    except ValueError:
        return None


def iniciar(acao: str, rotulo: str, comando: list, cwd, aparelho: str = "",
            args: dict | None = None) -> str:
    """Sobe a tarefa e devolve a chave. Levanta OSError se nao subir."""
    import secrets

    from . import acoes

    chave = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    pasta = pasta_das_tarefas() / chave
    pasta.mkdir(parents=True, exist_ok=True)
    ficha = {"chave": chave, "acao": acao, "rotulo": rotulo,
             "comando": [str(x) for x in comando], "cwd": str(cwd),
             "aparelho": aparelho, "args": args or {},
             "inicio": datetime.now().isoformat(timespec="seconds")}
    (pasta / "tarefa.json").write_text(json.dumps(ficha, ensure_ascii=False),
                                       encoding="utf-8")
    pid = acoes._iniciar_filha(pasta, comando, cwd)
    ficha["pid"] = pid
    ficha["criado"] = acoes._criado_em(pid)
    (pasta / "tarefa.json").write_text(json.dumps(ficha, ensure_ascii=False),
                                       encoding="utf-8")
    return chave


def _estado(pasta: Path, ficha: dict) -> dict:
    from . import acoes

    fim = _ler_json(pasta / "fim.json")
    filho = _ler_json(pasta / "filho.json") or {}
    vivo = acoes.vivo_de_verdade(ficha.get("pid"), ficha.get("criado"))
    if fim is not None:
        situacao = "terminou"
    elif vivo is False and acoes.vivo_de_verdade(filho.get("pid"),
                                                filho.get("criado")) is False:
        situacao = "sumiu"          # morreu sem escrever o fim
    else:
        situacao = "rodando"
    return {"situacao": situacao, "codigo": (fim or {}).get("codigo"),
            "erro": (fim or {}).get("erro") or "", "fim": (fim or {}).get("fim") or ""}


def uma(chave: str) -> dict | None:
    pasta = pasta_das_tarefas() / str(chave or "")
    ficha = _ler_json(pasta / "tarefa.json")
    if not isinstance(ficha, dict):
        return None
    ficha.update(_estado(pasta, ficha))
    try:
        ficha["bytes"] = (pasta / "saida.log").stat().st_size
    except OSError:
        ficha["bytes"] = 0
    return ficha


def listar(n: int = 20) -> list[dict]:
    """As tarefas mais novas primeiro. Rodando sempre aparece."""
    base = pasta_das_tarefas()
    try:
        pastas = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    except OSError:
        return []
    saida = []
    for pasta in pastas[:max(1, min(int(n), 100))]:
        ficha = uma(pasta.name)
        if ficha:
            saida.append(ficha)
    return saida


def rodando(acao: str | None = None) -> list[dict]:
    """O que ainda esta de pe (opcionalmente so de uma acao)."""
    return [t for t in listar(40)
            if t["situacao"] == "rodando" and (acao is None or t["acao"] == acao)]


def log(chave: str, desde: int = 0) -> dict:
    """Um pedaco do log a partir de `desde` bytes, ja limpo.

    O app pede o resto a cada poucos segundos: e o "acompanhar de longe".
    """
    from .painel_dados import limpar

    pasta = pasta_das_tarefas() / str(chave or "")
    caminho = pasta / "saida.log"
    try:
        tamanho = caminho.stat().st_size
    except OSError:
        return {"texto": "", "ate": 0, "tamanho": 0}
    desde = max(0, min(int(desde or 0), tamanho))
    if tamanho - desde > LOG_MAX:      # pulou muito: manda o fim
        desde = tamanho - LOG_MAX
    try:
        with open(caminho, "rb") as fh:
            fh.seek(desde)
            bruto = fh.read(LOG_MAX)
    except OSError:
        return {"texto": "", "ate": desde, "tamanho": tamanho}
    texto = bruto.decode("utf-8", errors="replace")
    return {"texto": limpar(texto), "ate": desde + len(bruto), "tamanho": tamanho}


def limpar_velhas(dias: int = GUARDAR_DIAS) -> int:
    """Apaga pastas de tarefas velhas E terminadas. Nunca as que rodam."""
    limite = datetime.now() - timedelta(days=dias)
    apagadas = 0
    for ficha in listar(100):
        if ficha["situacao"] == "rodando":
            continue
        try:
            quando = datetime.fromisoformat(ficha.get("inicio", ""))
        except ValueError:
            continue
        if quando >= limite:
            continue
        alvo = pasta_das_tarefas() / ficha["chave"]
        try:
            shutil.rmtree(alvo)
            apagadas += 1
        except OSError:
            pass
    return apagadas


def _idade(ficha: dict) -> float:
    try:
        return time.time() - datetime.fromisoformat(ficha["inicio"]).timestamp()
    except (KeyError, ValueError):
        return 0.0


def resumo() -> dict:
    """Quantas rodam, e ha quanto tempo a mais velha — para a tela inicial."""
    vivas = rodando()
    return {"rodando": len(vivas),
            "mais_velha_s": round(max((_idade(t) for t in vivas), default=0))}


__all__ = ["iniciar", "limpar_velhas", "listar", "log", "pasta_das_tarefas",
           "resumo", "rodando", "uma"]


if __name__ == "__main__":       # pragma: no cover
    for t in listar():
        print(f"{t['chave']}  {t['situacao']:9} {t['acao']:18} {t['rotulo'][:50]}")
