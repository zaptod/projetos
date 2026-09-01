# -*- coding: utf-8 -*-
"""(a) SAUDE DA PRODUCAO AGORA: o que roda, o que espera, o que travou.

Puro leitura. Nao abre navegador, nao chama rede, nao escreve nada — um
agregador que escreve e um agregador que corrompe estado quando o painel
abre.
"""
from __future__ import annotations

from builds import atividade, travas


def _fluxo() -> dict:
    """O snapshot da pipeline de builds, ou vazio se nao der para ler."""
    try:
        from builds.pipeline import fluxo
        return fluxo.snapshot(limite=8)
    except Exception as erro:
        return {"erro": f"{type(erro).__name__}: {erro}"}


def _historias() -> list:
    """As historias em andamento. Ausente nao e erro: o projeto e opcional."""
    try:
        from contos.pipeline.controller import Pipeline
        return list(Pipeline().listar() or [])
    except Exception:
        return []


def _paralelismo() -> dict:
    """Quem divide pasta com quem — a serializacao que ninguem ve.

    Uma trava usada por DOIS canais e um lugar onde o paralelismo prometido
    nao acontece: a segunda coisa espera a primeira. Isso e configuracao, nao
    codigo, entao o valor de mostrar aqui e o dono poder agir.
    """
    try:
        linhas = travas.estado()
    except Exception:
        return {"travas": [], "divididas": [], "ocupadas": 0}
    divididas = [linha for linha in linhas if len(linha.get("canais") or []) > 1]
    return {
        "travas": linhas,
        "divididas": [{"servico": linha["servico"],
                       "canais": linha["canais"],
                       "perfil": linha.get("perfil", "")}
                      for linha in divididas],
        "ocupadas": sum(1 for linha in linhas if linha.get("ocupada")),
    }


def agora() -> dict:
    """O estado deste minuto."""
    fluxo = _fluxo()
    fabricas = atividade.estado_das_fabricas()
    por_canal = atividade.estado_por_canal()
    historias = _historias()

    trabalhando = [f for f, d in fabricas.items() if d["status"] == "trabalhando"]
    com_erro = [f for f, d in fabricas.items() if d["status"] == "erro"]

    return {
        "fabricas": fabricas,
        # Por (fabrica, canal): dois canais no mesmo provedor sao dois
        # trabalhos, e a visao por fabrica sozinha os fundia num so.
        "por_canal": {f"{f}/{c}": d for (f, c), d in por_canal.items()},
        "trabalhando": trabalhando,
        "com_erro": com_erro,
        "fila": fluxo.get("fila") or fluxo.get("contagem") or {},
        "alertas": list(fluxo.get("alertas") or []),
        "silencio_s": fluxo.get("silencio_s"),
        "historias_em_andamento": len(historias),
        "paralelismo": _paralelismo(),
    }
