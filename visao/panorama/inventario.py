# -*- coding: utf-8 -*-
"""(c) ESTOQUE E PRODUCAO: quanto ha pronto, quanto ja saiu, quanto falta.

A pergunta que isto responde e "tenho material?". Ate aqui ela exigia abrir
tres telas e contar no olho — e a Vila respondia com uma contagem de LINHAS
de arquivo, que conta tambem o que falhou.
"""
from __future__ import annotations


def _videos_de_build() -> dict:
    # CATALOGO QUEBRADO NAO E "0 PRONTOS" (SCR-P8, 14/10/2026): estoque zero
    # e "nao consegui contar" eram o mesmo numero na Vila e na Auditoria.
    try:
        from builds.publicar import catalogo
        videos = list(catalogo.listar() or [])
    except Exception as exc:                                   # noqa: BLE001
        return {"prontos": None, "erro": f"builds: {type(exc).__name__}: {exc}"}
    return {"prontos": len(videos)}


def _videos_de_historia() -> dict:
    try:
        from contos.publicar import catalogo
        videos = list(catalogo.resumo() or [])
    except Exception as exc:                                   # noqa: BLE001
        return {"prontos": None,
                "erro": f"historias: {type(exc).__name__}: {exc}"}
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
    contagens = (builds.get("prontos"), historias.get("prontos"))
    erros = [lado["erro"] for lado in (builds, historias) if lado.get("erro")]
    prontos = {"builds": contagens[0], "historias": contagens[1],
               # um lado que nao contou deixa o total sem resposta (None):
               # metade do estoque somada como se fosse tudo seria outra
               # mentira
               "total": (None if None in contagens else sum(contagens))}
    if erros:
        prontos["erros"] = erros
    return {
        "videos_prontos": prontos,
        "historias_por_etapa": _historias_por_etapa(),
        "banco": _banco_do_jogo(),
        **_geracoes(),
    }
