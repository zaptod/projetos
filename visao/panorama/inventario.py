# -*- coding: utf-8 -*-
"""(c) ESTOQUE E PRODUCAO: quanto ha pronto, quanto ja saiu, quanto falta.

A pergunta que isto responde e "tenho material?". Ate aqui ela exigia abrir
tres telas e contar no olho — e a Vila respondia com uma contagem de LINHAS
de arquivo, que conta tambem o que falhou.
"""
from __future__ import annotations


def _videos_de_build() -> dict:
    try:
        from builds.publicar import catalogo
        videos = list(catalogo.listar() or [])
    except Exception:
        return {"prontos": 0, "erro": True}
    return {"prontos": len(videos)}


def _videos_de_historia() -> dict:
    try:
        from contos.publicar import catalogo
        videos = list(catalogo.resumo() or [])
    except Exception:
        return {"prontos": 0}
    return {"prontos": len(videos)}


def _historias_por_etapa() -> dict:
    """O que falta em cada historia, agrupado pelo PROXIMO PASSO.

    O pipeline de historias ja calcula `proximo_passo` por historia -- a
    frase que diz o que destrava aquela. Agrupar por ela responde "o que eu
    faco agora?" melhor do que qualquer contagem de etapa inventada aqui.
    """
    try:
        from contos.pipeline.controller import Pipeline
        linhas = [l for l in (Pipeline().listar() or []) if isinstance(l, dict)]
    except Exception:
        return {}

    passos: dict[str, int] = {}
    imagens = {"prontas": 0, "faltam": 0}
    videos = cenas = 0
    for linha in linhas:
        passo = str(linha.get("proximo_passo") or "pronta").strip()
        passos[passo] = passos.get(passo, 0) + 1
        cenas += int(linha.get("cenas") or 0)
        videos += int(linha.get("videos_prontos") or 0)
        das_imagens = linha.get("imagens") or {}
        imagens["prontas"] += int(das_imagens.get("prontas") or 0)
        imagens["faltam"] += int(das_imagens.get("faltam") or 0)

    return {"historias": len(linhas), "por_proximo_passo": passos,
            "cenas": cenas, "imagens": imagens, "videos_prontos": videos}


def _banco_do_jogo() -> dict:
    """Personagens e armas — o catalogo de onde as roletas tiram tudo."""
    try:
        from neural_fights.data import database
        armas, personagens = database.carregar_database()
        return {"personagens": len(personagens), "armas": len(armas)}
    except Exception:
        return {}


def _geracoes() -> dict:
    try:
        from builds.pipeline import fluxo
        dados = fluxo.snapshot(limite=1)
    except Exception:
        return {}
    chaves = dados.get("chaves") or {}
    return {"chaves": chaves, "arena": dados.get("arena") or {}}


def estoque() -> dict:
    builds = _videos_de_build()
    historias = _videos_de_historia()
    return {
        "videos_prontos": {"builds": builds.get("prontos", 0),
                           "historias": historias.get("prontos", 0),
                           "total": builds.get("prontos", 0)
                           + historias.get("prontos", 0)},
        "historias_por_etapa": _historias_por_etapa(),
        "banco": _banco_do_jogo(),
        **_geracoes(),
    }
