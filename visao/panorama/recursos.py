# -*- coding: utf-8 -*-
"""O que a producao CONSOME — e quanto ainda ha.

A quinta familia. As outras quatro respondem "o que esta acontecendo"; esta
responde "com o que". E a pergunta que nao estava em lugar nenhum, e por isso
cada falta dela virou um dia perdido, sempre do mesmo jeito: nada avisa, a
pipeline roda, e o resultado sai errado ou nao sai.

O que ja custou caro, cada um uma vez:

    disco           chegou a 0,33 GB livres e o render passou a morrer no
                    meio sem mensagem que dissesse "acabou o disco"
    credencial      o refresh_token do canal de historias venceu em 31/08 e
                    ficou onze dias morto; a publicacao continuou (ela vai
                    pelo navegador) e so a MEDICAO parou, sem uma linha de
                    erro em lugar nenhum
    conta travada   PicassoIA e conta compartilhada; com a trava presa, o
                    worker nao gera imagem e a historia trava na fila
                    esperando um dono que ja foi embora
    freio de mao    a pipeline pausada e uma pausa esquecida sao a mesma
                    coisa vista de fora: nada acontece

REGRA DESTE ARQUIVO, herdada do pacote: so LE, nao levanta, e e BARATO. O
painel le o `resumo()` a cada 4 s; um `schtasks` ou uma ida ao Google aqui
dentro viraria dezenas de subprocessos por minuto. O que custa caro mora em
`completo()`, que e chamado de proposito e com o proprio ritmo.
"""
from __future__ import annotations

import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Abaixo disto o render comeca a falhar de formas que nao se parecem com
# falta de disco (ffmpeg morre no meio, JSON sai truncado). Medido em
# 10/09/2026, quando o disco chegou a 0,33 GB.
DISCO_CRITICO_GB = 2.0
DISCO_BAIXO_GB = 8.0

# As travas que, presas, param uma fabrica inteira.
TRAVAS_VITAIS = ("picasso", "instancia_unica", "historias_auto")


def _disco() -> dict:
    try:
        uso = shutil.disk_usage(RAIZ)
    except OSError as erro:
        return {"erro": str(erro)}
    livre = uso.free / (1024 ** 3)
    return {"livre_gb": round(livre, 2),
            "total_gb": round(uso.total / (1024 ** 3), 1),
            "situacao": ("critico" if livre < DISCO_CRITICO_GB
                         else "baixo" if livre < DISCO_BAIXO_GB else "ok")}


def _travas() -> dict:
    """Quais perfis estao em uso AGORA.

    `travas.estado()` lista TODOS os perfis conhecidos com um campo
    `ocupada`, e nao so os seguradas — a primeira versao daqui mostrou os
    sete perfis como se todos estivessem presos. Quem responde a pergunta e
    o campo, nao o tamanho da lista.
    """
    try:
        from builds import travas
        linhas = travas.estado() or []
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    ocupadas = [{"servico": L.get("servico") or "?",
                 "canais": L.get("canais") or [],
                 "trava": L.get("trava") or ""}
                for L in linhas if isinstance(L, dict) and L.get("ocupada")]
    return {"ocupadas": ocupadas, "quantas": len(ocupadas),
            "conhecidas": len(linhas)}


def _freio() -> dict:
    """A pipeline esta pausada? Pausa esquecida e igual a producao parada."""
    try:
        from builds.identity import controle
        estado = controle.estado() or {}
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    pausas = estado.get("pausas") or {}
    return {"situacao": estado.get("situacao") or "",
            "pausado": bool(pausas),
            "alvos": sorted(pausas),
            "resumo": estado.get("resumo") or ""}


def _credenciais() -> dict:
    """Os ARQUIVOS de credencial existem e tem os campos?

    Leitura pura de proposito. `contas.oauth_vivo` pergunta ao Google e
    responde melhor — ele pega o refresh_token revogado, que este aqui nao
    pega —, mas usa rede, e rede nao entra no agregador. Quem faz a pergunta
    cara e o relatorio das 09:00 e `completo()` aqui embaixo.
    """
    try:
        from builds import contas
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    saida = {}
    for canal in ("builds", "historias"):
        ficha = {}
        for servico in ("youtube", "picasso", "tiktok"):
            try:
                ficha[servico] = bool(contas.tem_login(servico, canal))
            except Exception:                                  # noqa: BLE001
                ficha[servico] = None
        saida[canal] = ficha
    return saida


def leves() -> dict:
    """Os recursos baratos de ler. Entra no `resumo()` do pacote."""
    return {"disco": _disco(), "travas": _travas(), "freio": _freio(),
            "credenciais": _credenciais(), "alertas": []}


def situacao() -> dict:
    """`leves()` com os alertas ja resolvidos em frases."""
    dados = leves()
    alertas = []

    disco = dados.get("disco") or {}
    if disco.get("situacao") == "critico":
        alertas.append(f"disco em {disco.get('livre_gb')} GB livres: o render "
                       "comeca a morrer no meio sem dizer por que")
    elif disco.get("situacao") == "baixo":
        alertas.append(f"disco em {disco.get('livre_gb')} GB livres")

    freio = dados.get("freio") or {}
    if freio.get("pausado"):
        alertas.append("a pipeline esta PAUSADA ("
                       + ", ".join(freio.get("alvos") or []) + ")")

    for canal, ficha in (dados.get("credenciais") or {}).items():
        if isinstance(ficha, dict):
            faltando = [s for s, ok in ficha.items() if ok is False]
            if faltando:
                alertas.append(f"{canal}: sem login de "
                               + ", ".join(sorted(faltando)))

    ocupadas = (dados.get("travas") or {}).get("ocupadas") or []
    if ocupadas:
        # Nao e alerta de ERRO: trava ocupada e o estado normal de quem esta
        # trabalhando. E informacao de por que a outra fabrica esta esperando.
        dados["em_uso"] = sorted({t["servico"] for t in ocupadas})

    dados["alertas"] = alertas
    return dados


def completo() -> dict:
    """`situacao()` mais o que custa caro: Agendador e OAuth de verdade.

    Fora do `resumo()` de proposito — cada uma destas respostas custa um
    subprocesso ou uma ida a rede, e o painel le o resumo a cada 4 s.
    """
    dados = situacao()
    dados["agendador"] = _agendador()
    dados["oauth"] = _oauth_vivo()
    for canal, ficha in (dados["oauth"] or {}).items():
        if isinstance(ficha, dict) and not ficha.get("ok"):
            dados["alertas"].append(f"{canal}: {ficha.get('motivo')}")
    faltando = (dados["agendador"] or {}).get("faltando") or []
    fracas = (dados["agendador"] or {}).get("fracas") or []
    if faltando:
        dados["alertas"].append(f"{len(faltando)} tarefa(s) do Windows nao "
                                "existem: " + ", ".join(faltando[:3]))
    if fracas:
        dados["alertas"].append(f"{len(fracas)} tarefa(s) somem na bateria ou "
                                "perdem horario: " + ", ".join(fracas[:3]))
    return dados


def _agendador() -> dict:
    try:
        from builds import tarefas_windows
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    nomes = ([f"Historias_auto_{h:02d}" for h in (6, 7, 8, 10, 12, 15, 17, 20)]
             + [f"NeuralFights_postar_{h:02d}"
                for h in (6, 7, 8, 10, 12, 15, 17, 20)]
             + ["NeuralFights_bot_telegram"])
    faltando, fracas = [], []
    for nome in nomes:
        try:
            ficha = tarefas_windows.conferir(nome)
        except Exception:                                      # noqa: BLE001
            continue
        if not ficha:
            faltando.append(nome)
        elif not ficha.get("confiavel"):
            fracas.append(nome)
    return {"total": len(nomes), "faltando": faltando, "fracas": fracas}


def _oauth_vivo() -> dict:
    try:
        from builds import contas
    except Exception as erro:                                  # noqa: BLE001
        return {"erro": f"{type(erro).__name__}: {erro}"}
    saida = {}
    for canal in ("builds", "historias"):
        try:
            saida[canal] = contas.oauth_vivo(canal)
        except Exception as erro:                              # noqa: BLE001
            saida[canal] = {"ok": False,
                            "motivo": f"nao deu para conferir ({erro})"}
    return saida


__all__ = ["leves", "situacao", "completo", "DISCO_CRITICO_GB",
           "DISCO_BAIXO_GB"]
