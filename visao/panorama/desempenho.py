# -*- coding: utf-8 -*-
"""(b) DESEMPENHO DO PUBLICADO: o que foi ao ar e como se saiu.

SEM REDE. As metricas do YouTube (views, retencao, curva) sao buscadas pelo
comando `main.py metricas --atualizar` e ficam salvas em disco; aqui so se
LE o que ja foi salvo. Um agregador que chama API trava a interface quando a
internet cai, e sai caro em cota.

O que o `builds/publicar/metricas.py` ja calcula e ninguem via em widget
nenhum: a curva de retencao, e `quedas()`, que atribui cada tombo ao que
estava na tela naquele segundo ("queda de 12,3 pts aos 8,4 s: roleta PESO").
Isso e a coisa mais acionavel do projeto inteiro e vivia so como texto de
CLI despejado num log.
"""
from __future__ import annotations

from pathlib import Path


def _publicados_de(modulo) -> list:
    try:
        return list(modulo.publicados() or [])
    except Exception:
        return []


def _builds() -> list:
    try:
        from builds.publicar import metricas
        return _publicados_de(metricas)
    except Exception:
        return []


def _historias() -> list:
    """O registro das historias e SEPARADO de proposito.

    Sao canais diferentes com analytics diferente; junta-los daria uma media
    sem significado. O que faltava era UM caminho de codigo lendo os dois --
    ate aqui, nenhum leitor de metrica olhava o das historias.
    """
    try:
        from contos.publicar import serie
        return _publicados_de(serie)
    except Exception:
        return []


def _salvas() -> list:
    """As metricas ja baixadas do YouTube (arquivos em outputs/_metricas)."""
    try:
        from builds.publicar import metricas
        return list(metricas.carregar_salvas() or [])
    except Exception:
        return []


def _por_plataforma(linhas: list) -> dict:
    contagem: dict[str, int] = {}
    for linha in linhas:
        chave = str(linha.get("plataforma") or "youtube")
        contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def _piores_quedas(salvas: list, quantas: int = 5) -> list:
    """As maiores quedas de retencao, com o que estava na tela na hora."""
    from builds.publicar import metricas

    achados = []
    for dado in salvas:
        if dado.get("erro") or not dado.get("curva"):
            continue
        try:
            eventos = metricas.timeline_de(dado.get("fonte_id"),
                                           dado.get("origem"))
            for queda in metricas.quedas(dado, eventos, quantas=1):
                achados.append({**queda,
                                "youtube_id": dado.get("youtube_id"),
                                "titulo": dado.get("titulo", "")})
        except Exception:
            continue
    # A chave e "queda" (pontos percentuais perdidos), nao "perda":
    # ordenar pela chave errada devolveria a lista em ordem
    # arbitraria, sem erro nenhum.
    achados.sort(key=lambda q: q.get("queda", 0), reverse=True)
    return achados[:quantas]


def publicado() -> dict:
    """Quanto saiu, para onde, e como esta indo."""
    builds = _builds()
    historias = _historias()
    salvas = _salvas()

    com_numero = [d for d in salvas if not d.get("erro")]
    medias = [d.get("media_percentual") for d in com_numero
              if isinstance(d.get("media_percentual"), (int, float))]

    return {
        "builds": {"total": len(builds),
                   "por_plataforma": _por_plataforma(builds)},
        "historias": {"total": len(historias),
                      "por_plataforma": _por_plataforma(historias)},
        "total": len(builds) + len(historias),
        "com_metrica": len(com_numero),
        "views": sum(int(d.get("views") or 0) for d in com_numero),
        "likes": sum(int(d.get("likes") or 0) for d in com_numero),
        "retencao_media": (round(sum(medias) / len(medias), 1)
                           if medias else None),
        "piores_quedas": _piores_quedas(salvas) if com_numero else [],
        # Quando as metricas foram baixadas pela ultima vez: numero velho
        # apresentado como novo e pior do que numero nenhum.
        "atualizado_em": _quando_atualizou(),
    }


def _quando_atualizou() -> str:
    try:
        from builds.publicar import metricas
        pasta = Path(metricas.PASTA)
        arquivos = sorted(pasta.glob("*.json"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        if not arquivos:
            return ""
        from datetime import datetime
        return datetime.fromtimestamp(
            arquivos[0].stat().st_mtime).isoformat(timespec="minutes")
    except Exception:
        return ""
