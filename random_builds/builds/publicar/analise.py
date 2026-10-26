# -*- coding: utf-8 -*-
"""Analise dos videos: onde o canal acerta, onde erra, e o que mudar.

Pedido do Adrian (19/10/2026): "quero poder ver onde estou acertando,
errando, o que mudar". Este modulo LE o que a coleta da manha ja gravou
(`metricas` e `tiktok_metricas`), liga cada video ao que ele E (canal,
formato, arena, parte da historia, duracao, hora, dia da semana) e escreve
uma pagina em portugues simples, com UMA recomendacao por achado e o
tamanho esperado do efeito.

Regras que valem para cada numero daqui (a lei da parte de metricas):

- ZERO NAO E NOTA BOA. Sem video nenhum o estado e `sem_dados` e a pagina
  diz isso em vermelho; nunca "tudo bem". Parte com ledger e sem arquivo e
  aviso, nao "0 views".
- AMOSTRA PEQUENA NAO VIRA CONCLUSAO. Cada comparacao passa por um teste de
  postos (Mann-Whitney) e vira `claro` (p < 0,01 e 10+ de cada lado),
  `provavel` (p < 0,05 e 8+) ou vai para "ainda nao da para dizer".
- MEDIANA, NAO MEDIA. Um video de 12.572 views faz a media de um canal de
  1 view por video parecer 50.
- SO VIDEO MADURO ENTRA NA COMPARACAO (3+ dias no ar): o de ontem ainda
  esta juntando view e perderia de qualquer um.
- RETENCAO SO COM 20+ VIEWS. "Quanto do video as pessoas veem" com dois
  espectadores e sorteio.
- JANELA DE 28 DIAS. O canal de agosto (video mudo, sem duelo) nao explica
  o de outubro.
- EXCECAO VIRA AVISO. O que falhar ao ler (arquivo, metadado, rede) entra
  em `falhas` e aparece na pagina; no servico do dia vira linha de erro no
  diario, que chega ao Telegram.

Comandos (de qualquer pasta; `builds` e instalavel):

    python -m builds.publicar.analise --ver        so mostra; nao grava nada
    python -m builds.publicar.analise              grava analise.json + index.html
    python -m builds.publicar.analise --rede --biblioteca
        + busca a serie diaria do canal na Analytics (2 chamadas por canal)
        + poe a pagina na Biblioteca do app ("Analise dos videos")

O servico do dia das historias roda o ultimo (`do_dia`), depois da coleta.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from . import metricas

PLATAFORMAS = ("youtube", "tiktok")
NOME_DA_PLATAFORMA = {"youtube": "YouTube", "tiktok": "TikTok"}
NOME_DO_CANAL = {"builds": "Builds (Neural Fights)", "historias": "Histórias"}
NOME_DO_FORMATO = {"duelo": "duelo", "build": "build (roleta)",
                   "estreia": "estreia", "torneio": "torneio",
                   "historia": "história"}
FEMININOS = {"estreia", "historia"}


def o_(formato: str) -> str:
    """"o duelo" / "a estreia"."""
    return ("a " if formato in FEMININOS else "o ") + NOME_DO_FORMATO.get(formato, formato)


def do_(formato: str) -> str:
    """"do duelo" / "da estreia"."""
    return ("da " if formato in FEMININOS else "do ") + NOME_DO_FORMATO.get(formato, formato)


DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado",
                  "domingo")

JANELA_DIAS = 28
MADURO_DIAS = 3
MIN_VIEWS_RETENCAO = 20
MIN_N = 8
# O TikTok e a pausa. A UNIDADE e o BLOCO (os posts depois de uma pausa de
# `BLOCO_H` ou mais), nao o post: dez posts de um bloco so contam uma vez.
# Cada bloco cai numa FAIXA FIXA de pausa, escolhida antes de olhar o
# resultado e nunca ajustada nele (conferente, 19/10/2026: o corte "6
# primeiros" e o limiar de 10 h tinham sido tirados dos mesmos dados que
# testavam). "Deu certo" = mediana dos primeiros `POSTS_POR_BLOCO` posts do
# bloco com `VIEWS_DE_BLOCO_BOM` views ou mais (dez vezes o 1-2 de sempre).
PAUSA_TIKTOK_H = 10.0          # o que a grade sugerida deixa de pausa, no minimo
BLOCO_H = 5.0
FAIXAS_DE_PAUSA = ((22.0, None, "22 h ou mais"), (16.0, 22.0, "16 a 22 h"),
                   (10.0, 16.0, "10 a 16 h"), (5.0, 10.0, "5 a 10 h"))
POSTS_POR_BLOCO = 6
VIEWS_DE_BLOCO_BOM = 20
# O que JA ACONTECEU quando o TikTok postava 6 por dia: a decisao de
# 13/09/2026 (o TikTok pulava 7h e 8h da grade de 8, `grade.py`) valeu de 13/09
# ate a grade de 10, no dia 15/09. Dias INTEIROS nesse regime: so 13 e 14/09.
# A 1a versao usava 11 a 15/09, e o conferente mediu os posts por dia:
# builds 8, 4, 6, 6, 9 e historias 8, 1, 6, 6, 9 — o "piso" de 18 views (11/09,
# 8 posts) e os 12.821 (15/09, 9 posts) nao eram dia de 6. E a base da
# projecao — nao "corte x mediana", que so repete o melhor caso.
POSTS_DO_TESTE = 6
SEMANA_DE_6_POR_DIA = (date(2026, 9, 13), date(2026, 9, 14))
# A noite das historias no YouTube: o video que leva o dia sai entre 21h e
# 23h (medido em 19/10: 13/10 22:30, 15/10 23:38, nao so as 21h).
NOITE = (21, 22, 23)
# Idade da coleta a partir da qual a pagina avisa que o numero e velho.
COLETA_VELHA_DIAS = 2
TAG_DA_BIBLIOTECA = "analise-dos-videos"
TITULO_DA_PAGINA = "Análise dos vídeos"

# Os testes apontam para um tmpdir; `None` = `<outputs de builds>/_analise`.
PASTA = None


def pasta() -> Path:
    return Path(PASTA) if PASTA else Path(metricas.OUTPUTS) / "_analise"


def nome_da_parte(canal: str, plataforma: str) -> str:
    return metricas.nome_da_parte(canal, plataforma)


def rotulo_da_parte(canal: str, plataforma: str) -> str:
    return f"{NOME_DO_CANAL.get(canal, canal)} · {NOME_DA_PLATAFORMA.get(plataforma, plataforma)}"


# ------------------------------------------------------------- estatistica
def mediana(valores) -> float | None:
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    meio = len(v) // 2
    return float(v[meio]) if len(v) % 2 else (v[meio - 1] + v[meio]) / 2.0


def p_valor(a: list, b: list) -> float:
    """Mann-Whitney bilateral, aproximacao normal com correcao de empate.

    Sem scipy de proposito: o servico do dia roda no Python do Agendador.
    Lista vazia ou sem variacao = 1,0 (nada provado), nunca 0.
    """
    n1, n2 = len(a), len(b)
    if not n1 or not n2:
        return 1.0
    todos = sorted([(float(v), 0) for v in a] + [(float(v), 1) for v in b])
    n = n1 + n2
    postos = [0.0] * n
    empates = 0.0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and todos[j + 1][0] == todos[i][0]:
            j += 1
        posto = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            postos[k] = posto
        t = j - i + 1
        empates += t ** 3 - t
        i = j + 1
    r1 = sum(p for p, (_v, g) in zip(postos, todos) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    media = n1 * n2 / 2.0
    variancia = n1 * n2 / 12.0 * ((n + 1) - empates / (n * (n - 1)))
    if variancia <= 0:
        return 1.0
    z = max(abs(u1 - media) - 0.5, 0.0) / math.sqrt(variancia)
    return math.erfc(z / math.sqrt(2.0))


def confianca(a: list, b: list) -> str:
    """`claro`, `provavel` ou `incerto` — o rotulo que a pagina mostra."""
    if len(a) < MIN_N or len(b) < MIN_N:
        return "incerto"
    p = p_valor(a, b)
    if p < 0.01 and min(len(a), len(b)) >= 10:
        return "claro"
    if p < 0.05:
        return "provavel"
    return "incerto"


# --------------------------------------------------------------- leitura
def _instante_local(d: dict, plataforma: str) -> datetime | None:
    """Hora LOCAL da postagem. O ledger grava local; o YouTube grava UTC."""
    if plataforma == "tiktok" and d.get("post_time"):
        try:
            return datetime.fromtimestamp(int(d["post_time"]))
        except (TypeError, ValueError, OSError):
            pass
    try:
        return datetime.fromisoformat(str(d.get("quando"))[:19])
    except (TypeError, ValueError):
        pass
    bruto = d.get("publicado_em")
    if bruto:
        try:
            utc = datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
            return utc.astimezone().replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _formato(d: dict, canal: str) -> str:
    if canal == "historias":
        return "historia"
    origem = d.get("origem")
    if origem:
        return str(origem)
    partes = str(d.get("video_id") or "").split(":")
    return partes[1] if len(partes) > 1 and partes[1] else "?"


def _numero(valor) -> float | None:
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(
        valor, bool) else None


def registro(d: dict, canal: str, plataforma: str, agora: datetime,
             meta: dict | None = None) -> dict | None:
    """Um video, com o que ele E e como se saiu. `None` = sem data."""
    quando = _instante_local(d, plataforma)
    if quando is None:
        return None
    views = int(d.get("views") or 0)
    base = d.get("views_analytics")
    base = int(base) if isinstance(base, (int, float)) else views
    bruta = _numero(d.get("media_percentual"))
    retencao = (bruta if bruta is not None and not d.get("erro")
                and base >= MIN_VIEWS_RETENCAO else None)
    if plataforma == "youtube":
        priv = d.get("privacidade")
        publico = None if priv is None else str(priv).lower() == "public"
        vid = d.get("youtube_id")
    else:
        publico = True
        vid = d.get("tiktok_id")
    meta = meta or {}
    return {
        "id": str(vid or ""), "canal": canal, "plataforma": plataforma,
        "video_id": d.get("video_id"), "fonte_id": d.get("fonte_id"),
        "titulo": str(d.get("titulo") or ""), "formato": _formato(d, canal),
        "parte": d.get("parte"), "partes": d.get("partes"),
        # SEGUNDOS, nao minutos: cortado no minuto, 9 h 59 min 52 s (14 -> 15/09,
        # TikTok de builds) virava 10 h e abria uma "pausa longa" que nao houve
        # (conferente, 19/10/2026).
        "quando": quando.isoformat(timespec="seconds"),
        "hora": quando.hour, "dia_semana": quando.weekday(),
        "idade_dias": round((agora - quando).total_seconds() / 86400.0, 2),
        "duracao_s": _numero(d.get("duracao")),
        "views": views, "likes": int(d.get("likes") or 0),
        "comentarios": int(d.get("comentarios") or 0),
        "compartilhamentos": int(d.get("compartilhamentos") or 0),
        "retencao": round(retencao, 1) if retencao is not None else None,
        "segundos_vistos": _numero(d.get("media_segundos")),
        "publico": publico,
        # A HORA do numero de views (21/10/2026): a comparacao na mesma idade
        # e a fotografia diaria precisam dela. Arquivo antigo: `atualizado`.
        "medido_em": str(d.get("views_medidas_em") or d.get("atualizado") or "") or None,
        # A situacao do post no TikTok (crua; sem ela = nao medi).
        "situacao": d.get("situacao") if isinstance(d.get("situacao"), dict) else None,
        # Engaged views: so o que a Analytics deu; sem o campo = nao medido.
        "engaged_views": (int(d["engaged_views"]) if isinstance(d.get("engaged_views"), (int, float))
                          and not isinstance(d.get("engaged_views"), bool) else None),
        **{k: v for k, v in meta.items() if v is not None},
    }


def _ler_json(caminho: Path) -> dict:
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dado if isinstance(dado, dict) else {}


def metadados(canal: str, fonte_id: str | None, formato: str) -> dict:
    """O que a geracao sabe de si: arena e zebra do duelo, nota do build,
    estrutura e narrador da historia. Falta de arquivo = `{}`, nunca erro."""
    if not fonte_id or "/" in str(fonte_id) or "\\" in str(fonte_id):
        return {}
    if canal == "historias":
        raiz = metricas.OUTRAS_RAIZES["historias"] / "outputs" / str(fonte_id)
        r = _ler_json(raiz / "roteiro.json")
        return {"estrutura": r.get("estrutura") or r.get("tipo"),
                "narrador": r.get("narrador"),
                "serie": r.get("serie_nome") or r.get("titulo")}
    raiz = Path(metricas.OUTPUTS) / str(fonte_id)
    if formato == "duelo":
        f = _ler_json(raiz / "fight.json")
        luta = f.get("luta") if isinstance(f.get("luta"), dict) else {}
        return {"arena": f.get("cenario") or luta.get("cenario"),
                "zebra": luta.get("zebra"), "tier": luta.get("tier")}
    if formato == "build":
        e = _ler_json(raiz / "evaluation.json")
        return {"nota": e.get("final_score"), "veredito": e.get("verdict")}
    return {}


def carregar(agora: datetime | None = None) -> dict:
    """Tudo o que a analise usa, lido do disco. Nada de rede.

    Cada leitura que falha entra em `falhas` com o motivo: a pagina mostra,
    e o servico do dia escreve no diario.
    """
    from . import tiktok_metricas

    agora = agora or datetime.now()
    entrada = {"agora": agora, "salvas": {}, "ledger": {}, "falhas": [],
               "marca": None, "series": {}, "historico": {}}
    try:
        entrada["marca"] = metricas.ler_marca()
    except Exception as exc:                                  # noqa: BLE001
        entrada["falhas"].append(f"marca da coleta ilegível: {type(exc).__name__}: {exc}")
    for canal in metricas.CANAIS:
        try:
            entrada["ledger"][canal] = [l for l in metricas.publicados(canal)
                                        if metricas.publicado(l)]
        except Exception as exc:                              # noqa: BLE001
            entrada["ledger"][canal] = []
            entrada["falhas"].append(f"ledger de {canal} ilegível: {type(exc).__name__}: {exc}")
        for plataforma, leitor in (("youtube", metricas.carregar_salvas),
                                   ("tiktok", tiktok_metricas.carregar_salvas)):
            try:
                entrada["salvas"][(canal, plataforma)] = list(leitor(canal) or [])
            except Exception as exc:                          # noqa: BLE001
                entrada["salvas"][(canal, plataforma)] = []
                entrada["falhas"].append(
                    f"métricas de {rotulo_da_parte(canal, plataforma)} ilegíveis: "
                    f"{type(exc).__name__}: {exc}")
        serie = _ler_json(pasta() / f"canal_{canal}.json")
        if serie:
            entrada["series"][canal] = serie
    ontem = (agora.date() - timedelta(days=1)).isoformat()
    entrada["historico"] = _ler_json(pasta() / "historico" / f"{ontem}.json")
    entrada["fotos"] = _fotos()
    _carregar_a_semana(entrada, agora)
    try:
        from .. import grade
        entrada["testes"] = {TESTE_DO_TIKTOK: grade.teste(TESTE_DO_TIKTOK),
                             TESTE_DA_PARTE_SEGUINTE: grade.teste(TESTE_DA_PARTE_SEGUINTE)}
    except Exception as exc:                                  # noqa: BLE001
        entrada["testes"] = {}
        entrada["falhas"].append(f"datas dos testes ilegíveis: {type(exc).__name__}: {exc}")
    try:
        entrada["dias_de_coleta"] = dias_de_coleta(agora)
    except Exception as exc:                                  # noqa: BLE001
        entrada["dias_de_coleta"] = []
        entrada["falhas"].append(f"histórico da coleta ilegível: {type(exc).__name__}: {exc}")
    return entrada


def _carregar_a_semana(entrada: dict, agora: datetime) -> None:
    """O que a medida da semana na mesma idade le do disco: a semana do
    config, as leituras de hora em hora, a hora das fotografias antigas (pelo
    log) e as fichas da conta do TikTok. Cada falha vira `falhas`."""
    from . import hora_a_hora, mesma_idade, tiktok_metricas

    try:
        entrada["semana"], erro = mesma_idade.semana_vigente(agora)
        entrada["erro_da_semana"] = erro
        if erro:
            entrada["falhas"].append(erro)
    except Exception as exc:                                  # noqa: BLE001
        entrada["semana"], entrada["erro_da_semana"] = None, f"{type(exc).__name__}: {exc}"
        entrada["falhas"].append(f"medida da semana ilegível: {entrada['erro_da_semana']}")
    try:
        entrada["leituras_hora"] = hora_a_hora.carregar(dias=16, hoje=agora.date())
    except Exception as exc:                                  # noqa: BLE001
        entrada["leituras_hora"] = []
        entrada["falhas"].append(f"leituras de hora em hora ilegíveis: {type(exc).__name__}: {exc}")
    try:
        # So as fotografias que nasceram sem a hora (19 a 21/10/2026).
        sem_hora = [dia for dia, foto in (entrada.get("fotos") or {}).items()
                    if not foto.get("quando_das_partes")]
        limites = {}
        for dia in sem_hora:
            try:
                limites[dia] = datetime.fromtimestamp(
                    (pasta() / "historico" / f"{dia}.json").stat().st_mtime
                ).isoformat(timespec="seconds")
            except OSError:
                pass
        entrada["horas_das_fotos"] = mesma_idade.horas_pelo_log(sem_hora, limites)
    except Exception as exc:                                  # noqa: BLE001
        entrada["horas_das_fotos"] = {}
        entrada["falhas"].append(f"hora das fotografias ilegível: {type(exc).__name__}: {exc}")
    entrada["contas_tiktok"] = {}
    for canal in metricas.CANAIS:
        try:
            entrada["contas_tiktok"][canal] = tiktok_metricas.carregar_contas(canal)
        except Exception as exc:                              # noqa: BLE001
            entrada["falhas"].append(f"fichas da conta do TikTok de {canal} ilegíveis: "
                                     f"{type(exc).__name__}: {exc}")


def registros(entrada: dict, meta=metadados) -> list[dict]:
    agora = entrada["agora"]
    saida = []
    cache: dict = {}
    for (canal, plataforma), salvas in entrada["salvas"].items():
        for d in salvas:
            if not isinstance(d, dict):
                continue
            formato = _formato(d, canal)
            chave = (canal, d.get("fonte_id"), formato)
            if chave not in cache:
                try:
                    cache[chave] = meta(canal, d.get("fonte_id"), formato) if meta else {}
                except Exception:                             # noqa: BLE001
                    cache[chave] = {}
            r = registro(d, canal, plataforma, agora, cache[chave])
            if r is not None:
                saida.append(r)
    return saida


# --------------------------------------------------------------- cobertura
def cobertura(entrada: dict) -> dict:
    """O que a coleta tem, parte por parte, e o que falta. Numero exato."""
    agora = entrada["agora"]
    fichas = {}
    try:
        fichas = metricas.partes_da_marca(entrada.get("marca"))
    except Exception:                                         # noqa: BLE001
        fichas = {}
    partes = {}
    for canal in metricas.CANAIS:
        ledger = entrada["ledger"].get(canal) or []
        for plataforma in PLATAFORMAS:
            nome = nome_da_parte(canal, plataforma)
            linhas = [l for l in ledger
                      if str(l.get("plataforma") or "youtube") == plataforma]
            salvas = [d for d in entrada["salvas"].get((canal, plataforma)) or []
                      if isinstance(d, dict)]
            ficha = fichas.get(nome) if isinstance(fichas.get(nome), dict) else {}
            atualizados = sorted(str(d.get("atualizado") or "")[:10] for d in salvas)
            dia_da_coleta = str(ficha.get("ultimo_ok") or "")[:10]
            velhos = [d for d in salvas if dia_da_coleta
                      and str(d.get("atualizado") or "")[:10] < dia_da_coleta]
            ids_velhos = {id(d) for d in velhos}
            item = {
                "parte": nome, "canal": canal, "plataforma": plataforma,
                "rotulo": rotulo_da_parte(canal, plataforma),
                "linhas_no_ledger": len(linhas),
                "medidos": len(salvas),
                "com_views": sum(1 for d in salvas if int(d.get("views") or 0) > 0),
                "com_retencao": sum(1 for d in salvas
                                    if _numero(d.get("media_percentual")) is not None
                                    and not d.get("erro")),
                "parados": len(velhos),
                # Com numero DESTA coleta: o "parado" tem numero, mas velho.
                "medidos_hoje": len(salvas) - len(velhos),
                # A retencao DOS MESMOS videos de `medidos_hoje`: a pagina dizia
                # "336 com numero desta coleta; em 338 da para saber quanto
                # assistem" (a 2a conta incluia os 3 parados).
                "com_retencao_hoje": sum(1 for d in salvas if id(d) not in ids_velhos
                                         and _numero(d.get("media_percentual")) is not None
                                         and not d.get("erro")),
                "parados_desde": sorted({str(d.get("atualizado") or "")[:10] for d in velhos}),
                "desde": min((str(l.get("quando"))[:10] for l in linhas), default=""),
                "ate": max((str(l.get("quando"))[:10] for l in linhas), default=""),
                "coleta": ficha.get("estado") or "nunca",
                "ultimo_ok": str(ficha.get("ultimo_ok") or ""),
                "erro": ficha.get("erro") or "",
                "atualizado_mais_velho": atualizados[0] if atualizados else "",
            }
            if plataforma == "youtube":
                ids = {l.get("youtube_id") for l in linhas if l.get("youtube_id")}
                medidos = {d.get("youtube_id") for d in salvas}
                # Video postado DEPOIS da ultima coleta boa nao e buraco: e a
                # proxima coleta (medido em 19/10 09:56: os 2 "sem numero"
                # eram das 09:37, a coleta foi as 07:24).
                corte = str(ficha.get("ultimo_ok") or "9999")
                antigos = {l.get("youtube_id") for l in linhas if l.get("youtube_id")
                           and str(l.get("quando") or "") < corte}
                item["ids_no_ledger"] = len(ids)
                item["sem_id"] = sum(1 for l in linhas if not l.get("youtube_id"))
                # VIDEO, nao linha: o ledger repete linha do mesmo video
                # (318 linhas = 313 videos em 19/10).
                item["videos_postados"] = len(ids) + item["sem_id"]
                item["linhas_repetidas"] = len(linhas) - item["videos_postados"]
                item["sem_arquivo"] = len(antigos - medidos)
                item["depois_da_coleta"] = len((ids - antigos) - medidos)
                item["publicos"] = sum(1 for d in salvas if d.get("privacidade") == "public")
                item["privados"] = sum(1 for d in salvas if d.get("privacidade") == "private")
                item["sem_status"] = sum(1 for d in salvas if d.get("privacidade") is None)
                item["sem_retencao_por_poucas_views"] = sum(
                    1 for d in salvas if d.get("erro"))
            else:
                envios = ficha.get("envios")
                casados = ficha.get("casados")
                item["envios"] = envios if isinstance(envios, int) else len(linhas)
                item["casados"] = casados if isinstance(casados, int) else len(salvas)
                item["sem_par"] = max(0, item["envios"] - item["casados"])
                # O ledger do TikTok nao guarda id: cada linha e um envio.
                item["videos_postados"] = len(linhas)
                item["linhas_repetidas"] = 0
                corte = str(ficha.get("ultimo_ok") or "9999")
                antes = sum(1 for l in linhas if str(l.get("quando") or "") < corte)
                item["depois_da_coleta"] = len(linhas) - antes
                item["nunca_medidos"] = max(0, antes - len(salvas))
                limite = (agora - timedelta(days=7)).isoformat()
                item["retencao_relida_ha_mais_de_7_dias"] = sum(
                    1 for d in salvas if str(d.get("analisado_em") or "") < limite)
            partes[nome] = item
    ultimos = [p["ultimo_ok"] for p in partes.values()]
    nunca = [p["rotulo"] for p in partes.values() if not p["ultimo_ok"]]
    mais_velha = min(ultimos) if ultimos and not nunca else ""
    idade = None
    if mais_velha:
        try:
            idade = (agora - datetime.fromisoformat(mais_velha[:19])).total_seconds() / 86400.0
        except ValueError:
            idade = None
    total = sum(p["medidos"] for p in partes.values())
    if total == 0:
        estado = "sem_dados"
    elif nunca or idade is None or idade > COLETA_VELHA_DIAS:
        estado = "velha"
    elif any(p["coleta"] == "erro" for p in partes.values()):
        estado = "incompleta"
    else:
        estado = "ok"
    return {"partes": partes, "estado": estado, "videos_medidos": total,
            "coleta_mais_velha": mais_velha, "idade_dias": (round(idade, 1)
                                                           if idade is not None else None),
            "partes_que_nunca_coletaram": nunca,
            "marca_completa": bool((entrada.get("marca") or {}).get("completa")),
            "dias_de_coleta": list(entrada.get("dias_de_coleta") or [])}


def dias_de_coleta(agora: datetime, dias: int = 21, pasta_dos_logs: Path | None = None) -> list:
    """Como foi a coleta em cada um dos ultimos `dias`, pela linha
    `[metricas] dia-AAAA-MM-DD: ...` que a coleta escreve no log das historias
    (`auto_AAAAMMDD.txt`). A ULTIMA linha do dia manda.

    `completa` (as 4 partes ok), `parcial` (alguma falhou), `falhou` (todas),
    `nao_rodou` (nenhuma linha no dia), `nao_medido` (antes da primeira linha
    desse tipo em qualquer log — o formato nasceu em 01/10/2026)."""
    import re as _re

    pasta_dos_logs = pasta_dos_logs or (metricas.OUTRAS_RAIZES["historias"] / "outputs" / "_logs")
    padrao = _re.compile(r"\[metricas\] dia-(\d{4}-\d{2}-\d{2}): (.*)$")
    achados: dict[str, str] = {}
    try:
        arquivos = sorted(Path(pasta_dos_logs).glob("auto_*.txt"))
    except OSError:
        arquivos = []
    for arquivo in arquivos:
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linha in texto.splitlines():
            m = padrao.search(linha)
            if m:
                achados[m.group(1)] = m.group(2)
    primeiro = min(achados) if achados else None
    saida = []
    for i in range(dias - 1, -1, -1):
        dia = (agora.date() - timedelta(days=i)).isoformat()
        resumo = achados.get(dia)
        if resumo is None:
            estado = "nao_medido" if primeiro is None or dia < primeiro else "nao_rodou"
        else:
            pedacos = [p.split(" (")[0] for p in resumo.split(" — ")[0].split(" · ")]
            boas = sum(1 for p in pedacos if " ok " in f" {p} ")
            estado = ("completa" if boas == len(pedacos) and boas else
                      "falhou" if boas == 0 else "parcial")
        saida.append({"dia": dia, "estado": estado})
    return saida


# ---------------------------------------------------------------- achados
def _na_janela(regs: list, agora: datetime, maduros: bool = True) -> list:
    inicio = agora - timedelta(days=JANELA_DIAS)
    saida = []
    for r in regs:
        # So video PUBLICO e amostra: rascunho e video sem status (o YouTube
        # nao disse a privacidade) ficam de fora — ninguem pode te-los visto.
        if r.get("publico") is not True:
            continue
        quando = datetime.fromisoformat(r["quando"])
        if quando < inicio:
            continue
        if maduros and r["idade_dias"] < MADURO_DIAS:
            continue
        saida.append(r)
    return saida


def _fmt(n) -> str:
    if n is None:
        return "—"
    if abs(n) >= 100 or float(n).is_integer():
        return f"{round(n):,}".replace(",", ".")
    return f"{n:.1f}".replace(".", ",")


def _pct(n) -> str:
    return "—" if n is None else f"{round(n)}%"


def _qtd(n: int, um: str, varios: str) -> str:
    """"1 vídeo postado", "3 vídeos postados"."""
    return f"{n} {um if n == 1 else varios}"


def _v(n) -> str:
    """"1 view", "2 views", "0,5 view" — nunca "1 views"."""
    if n is None:
        return "— views"
    return f"{_fmt(n)} {'view' if 0 < abs(float(n)) < 2 else 'views'}"


def _dias_efetivos(regs: list) -> int:
    return max(1, len({r["quando"][:10] for r in regs}))


def _achado(id_, parte, tipo, titulo, vimos, mudar, quanto, conf, peso, **numeros) -> dict:
    return {"id": id_, "parte": parte, "tipo": tipo, "titulo": titulo,
            "vimos": vimos, "mudar": mudar, "quanto": quanto,
            "confianca": conf, "peso": round(float(peso), 1), "numeros": numeros}


def _views_do_dia(regs: list) -> dict:
    por_dia = defaultdict(int)
    for r in regs:
        por_dia[r["quando"][:10]] += r["views"]
    return por_dia


def horarios_sugeridos(k: int, grade=None, margem_h: float = 1.5) -> list[str]:
    """`k` horarios SEGUIDOS da grade que deixam a maior folga util: a pausa
    depois do ultimo ate o primeiro do dia seguinte e de `PAUSA_TIKTOK_H` +
    `margem_h` ou mais, e entre as que passam, a mais justa (a que cobre mais
    do dia). Lista vazia se nenhuma janela da grade passa."""
    if grade is None:
        from .. import grade as modulo
        grade = modulo.GRADE
    minutos = sorted(h * 60 + m for h, m in grade)
    n = len(minutos)
    if k < 1 or k >= n:
        return []
    melhor = None
    for i in range(n):
        janela = [minutos[(i + j) % n] for j in range(k)]
        if any(janela[j + 1] < janela[j] for j in range(k - 1)):
            continue                                  # janela que vira a meia-noite
        # So se posta nos horarios da janela: a pausa vai do ultimo dela ate
        # o PRIMEIRO dela no dia seguinte.
        pausa = (janela[0] - janela[-1]) % (24 * 60)
        if pausa >= (PAUSA_TIKTOK_H + margem_h) * 60 and (melhor is None or pausa < melhor[0]):
            melhor = (pausa, janela)
    if melhor is None:
        return []
    return [f"{x // 60:02d}:{x % 60:02d}" for x in melhor[1]]


def _quando(r: dict) -> datetime:
    return datetime.fromisoformat(r["quando"])


def blocos_do_tiktok(tk: list) -> list[dict]:
    """Os posts do TikTok em BLOCOS: um bloco comeca depois de `BLOCO_H` ou
    mais sem postar. `pausa` = horas antes do bloco (em segundos exatos, nao
    no minuto); `None` no primeiro de todos (nao se sabe a pausa)."""
    blocos: list[dict] = []
    anterior = None
    for r in sorted(tk, key=_quando):
        quando = _quando(r)
        pausa = None if anterior is None else (quando - anterior).total_seconds() / 3600.0
        if pausa is None or pausa >= BLOCO_H:
            blocos.append({"pausa": pausa, "inicio": r["quando"], "posts": []})
        blocos[-1]["posts"].append(r)
        anterior = quando
    for b in blocos:
        primeiros = b["posts"][:POSTS_POR_BLOCO]
        # Bloco com post de menos de 3 dias ainda esta juntando view: fora.
        maduro = all(r["idade_dias"] >= MADURO_DIAS for r in primeiros)
        b["mediana"] = mediana(r["views"] for r in primeiros) if maduro else None
        b["deu_certo"] = None if b["mediana"] is None else b["mediana"] >= VIEWS_DE_BLOCO_BOM
    return blocos


def _faixa(pausa) -> str | None:
    if pausa is None:
        return None
    for minimo, maximo, nome in FAIXAS_DE_PAUSA:
        if pausa >= minimo and (maximo is None or pausa < maximo):
            return nome
    return None


def _nome_curto(canal: str) -> str:
    return NOME_DO_CANAL.get(canal, canal).split(" (")[0].lower()


def achado_pausa_tiktok(regs: list, agora: datetime, canal: str) -> tuple:
    """O TikTok entrega quando o perfil descansou? Por BLOCO, por faixa fixa
    de pausa, e a projecao sai do que ja aconteceu (a semana de 6 por dia)."""
    tk = [r for r in regs if r["plataforma"] == "tiktok" and r["canal"] == canal]
    nome = _nome_curto(canal)
    blocos = [b for b in blocos_do_tiktok(tk) if b["deu_certo"] is not None
              and _faixa(b["pausa"])]
    if len(blocos) < 4:
        return None, (f"TikTok de {nome}: só {len(blocos)} bloco(s) de posts com 3+ dias "
                      f"— pouco para medir o efeito da pausa")
    faixas = []
    for _minimo, _maximo, rotulo in FAIXAS_DE_PAUSA:
        g = [b for b in blocos if _faixa(b["pausa"]) == rotulo]
        if g:
            faixas.append({"faixa": rotulo, "blocos": len(g),
                           "deram_certo": sum(1 for b in g if b["deu_certo"]),
                           "mediana": mediana(b["mediana"] for b in g)})
    longos = [b["mediana"] for b in blocos if b["pausa"] >= FAIXAS_DE_PAUSA[0][0]]
    curtos = [b["mediana"] for b in blocos if b["pausa"] < FAIXAS_DE_PAUSA[-1][1]]
    p = p_valor(longos, curtos)
    # Certeza por BLOCO (~10 de cada lado no maximo): nunca "clara".
    conf = "provavel" if min(len(longos), len(curtos)) >= 3 and p < 0.05 else "incerto"
    descricao = "; ".join(f"pausa de {f['faixa']}: {f['deram_certo']} de {f['blocos']}"
                          for f in faixas)
    if conf == "incerto":
        return None, (f"TikTok de {nome}: blocos que deram certo por pausa antes ({descricao}) "
                      f"— ainda não separa do acaso")
    # O que ja aconteceu: os dias em que postava 6 por dia. So dia DENTRO do
    # regime e com no maximo 6 posts; o grupo "9 ou mais" nunca divide dia com
    # ele (na 1a versao o 15/09, 9 posts, estava nos dois).
    por_dia = defaultdict(list)
    for r in tk:
        por_dia[r["quando"][:10]].append(r)
    ini, fim = SEMANA_DE_6_POR_DIA
    # Dia maduro pela IDADE de cada video (agora - postado), nao pela data: o
    # dia de 3 dias atras no calendario tem video da noite com 2,5 dias.
    maduros = {d: lista for d, lista in por_dia.items()
               if all(r["idade_dias"] >= MADURO_DIAS for r in lista)}
    dias_de_6 = sorted((d, sum(r["views"] for r in lista)) for d, lista in maduros.items()
                       if ini.isoformat() <= d <= fim.isoformat()
                       and len(lista) <= POSTS_DO_TESTE)
    semana = [v for _d, v in dias_de_6]
    muitos = [sum(r["views"] for r in lista) for d, lista in maduros.items()
              if len(lista) >= 9 and d not in dict(dias_de_6)]
    hoje = mediana(muitos)
    # A pausa que o teste deixa (do ultimo horario ate o primeiro do dia
    # seguinte) e como a faixa dela se saiu, contra a de um dia inteiro parado.
    try:
        sugeridos = horarios_sugeridos(POSTS_DO_TESTE)
    except Exception:                                         # noqa: BLE001
        sugeridos = []
    pausa_do_teste = None
    if sugeridos:
        primeiro, ultimo = (int(x[:2]) * 60 + int(x[3:]) for x in (sugeridos[0], sugeridos[-1]))
        pausa_do_teste = ((primeiro - ultimo) % (24 * 60)) / 60.0
    faixa_do_teste = _faixa(pausa_do_teste)
    # Bloco da faixa do teste que ainda nao tem 3 dias: nao conta, e e dito.
    juntando = [b for b in blocos_do_tiktok(tk) if b["deu_certo"] is None
                and faixa_do_teste and _faixa(b["pausa"]) == faixa_do_teste]
    pausa_txt = _frase_da_pausa(pausa_do_teste, faixas, juntando)
    # O maior sucesso do perfil: em que posicao do dia ele saiu?
    topo = max(tk, key=lambda r: r["views"])
    do_dia = sorted(por_dia[topo["quando"][:10]], key=_quando)
    posicao = do_dia.index(topo) + 1
    excecao = (f" Mas a regra não é absoluta: o vídeo mais visto do perfil "
               f"({_v(topo['views'])}, {_data_br(topo['quando'])}) foi o {posicao}º post do dia."
               if posicao > POSTS_DO_TESTE else "")
    exemplo = (f" ({', '.join(sugeridos)})" if sugeridos else "")
    if semana:
        n_dias = len(dias_de_6)
        valores = " e ".join(f"{_v(v) if i == 0 else _fmt(v)} em {_data_br(d)}"
                             for i, (d, v) in enumerate(dias_de_6))
        comparado = (f" Nos dias com 9 ou mais posts, o dia do meio somou {_v(hoje)}."
                     if hoje is not None else "")
        faixa_txt = (f"entre ~{_fmt(min(semana))} e ~{_fmt(max(semana))}"
                     if len(semana) > 1 else f"~{_fmt(semana[0])}")
        quanto = (f"O TikTok postou {POSTS_DO_TESTE} por dia em só "
                  f"{_qtd(n_dias, 'dia inteiro', 'dias inteiros')} (a regra de "
                  f"{POSTS_DO_TESTE} por dia valeu de {_data_br(ini.isoformat())} até a grade "
                  f"de 10, que entrou em {_data_br((fim + timedelta(days=1)).isoformat())}): os "
                  f"vídeos de cada dia somaram {valores}.{comparado} Se o teste repetir "
                  f"aqueles dias: {faixa_txt} views por dia neste perfil (somando os vídeos "
                  f"postados no dia; não é medida do perfil inteiro). Com só "
                  f"{_qtd(n_dias, 'dia', 'dias')}, é um sinal, não uma medida firme.")
        ganho = max(min(semana) - (hoje or 0), 0) / 2
    else:
        quanto = ("Não dá para estimar: não há dia com só "
                  f"{POSTS_DO_TESTE} posts para comparar.")
        ganho = 0
    return _achado(
        f"pausa-tiktok:{canal}", nome_da_parte(canal, "tiktok"), "erro",
        f"TikTok de {nome}: o perfil só aparece depois de descansar",
        (f"Separando os posts em blocos pelo tempo sem postar antes de cada um (o bloco "
         f"deu certo quando os primeiros posts tiveram {VIEWS_DE_BLOCO_BOM} views ou mais): "
         f"{descricao}. Com a grade de 10 por dia, a maior pausa é a da madrugada (6 h), "
         f"então quase todo bloco é de 5 a 10 h." + pausa_txt + excecao),
        (f"Testar por 1 semana no máximo {POSTS_DO_TESTE} vídeos por dia no TikTok, todos "
         f"de dia{exemplo}, com 10 horas ou mais sem postar à noite, e medir aqui."),
        quanto, conf, ganho,
        faixas=faixas, p=round(p, 4), semana_de_6=semana,
        dias_de_6=[d for d, _v in dias_de_6], dias_com_9_ou_mais=hoje,
        pausa_do_teste=pausa_do_teste, faixa_do_teste=faixa_do_teste,
        blocos_do_teste_juntando=[b["inicio"] for b in juntando],
        posicao_do_maior=posicao, horarios=sugeridos), None


def _taxa(f: dict | None) -> float | None:
    return f["deram_certo"] / f["blocos"] if f and f.get("blocos") else None


def _frase_da_pausa(pausa_do_teste, faixas: list, juntando: list) -> str:
    """A pausa que o teste deixa contra a de um dia inteiro parado, com os
    numeros de cada faixa. Na 1a versao a frase era "pausa longa nao
    garante", e os proprios exemplos a desmentiam (conferente, 19/10/2026):
    as de 30,1 h e 22,2 h deram certo, e a de 12,1 h ainda nao tinha 3 dias."""
    if pausa_do_teste is None:
        return ""
    faixa_do_teste = _faixa(pausa_do_teste)
    do_teste = next((f for f in faixas if f["faixa"] == faixa_do_teste), None)
    dia_inteiro = next((f for f in faixas if f["faixa"] == FAIXAS_DE_PAUSA[0][2]), None)
    # "A que menos se provou" so quando e verdade entre as pausas de 10 h ou
    # mais (a de 5 a 10 h e a grade de hoje, nao o teste).
    longas = [_taxa(f) for f in faixas
              if any(f["faixa"] == nome and minimo >= PAUSA_TIKTOK_H
                     for minimo, _maximo, nome in FAIXAS_DE_PAUSA)]
    menor = bool(do_teste is not None and longas and _taxa(do_teste) <= min(longas))
    horas = _fmt(round(pausa_do_teste))
    pendentes = ""
    if juntando:
        datas = " e ".join(f"{_fmt(round(b['pausa'], 1))} h de {_data_br(b['inicio'])}"
                           for b in juntando)
        um = len(juntando) == 1
        pendentes = (f"; {'o bloco' if um else 'os blocos'} de {datas} ainda "
                     f"{'não tem' if um else 'não têm'} 3 dias e não "
                     f"{'entra' if um else 'entram'} na conta")
    if not do_teste:
        return (f" A pausa de ~{horas} h que o teste deixa ainda não foi medida: nenhum bloco "
                f"com 3+ dias depois de uma pausa assim{pendentes}.")
    teste = (f"deu certo {do_teste['deram_certo']} de {do_teste['blocos']} "
             f"{'vez' if do_teste['blocos'] == 1 else 'vezes'}")
    if (menor and dia_inteiro and do_teste is not dia_inteiro
            and _taxa(do_teste) < _taxa(dia_inteiro)):
        return (f" A pausa de ~{horas} h do teste é a que menos se provou ({teste}{pendentes}); "
                f"a de um dia inteiro parado ({dia_inteiro['faixa']}) deu certo "
                f"{dia_inteiro['deram_certo']} de {dia_inteiro['blocos']} — se a semana de "
                f"teste não mostrar efeito, o próximo teste é um dia inteiro sem postar.")
    return f" A pausa de ~{horas} h do teste {teste}{pendentes}."


# ------------------------------------------------------------------ testes
# OS TESTES EM ANDAMENTO (decisoes de 19/10/2026). As datas moram no config
# da publicacao (`grade.teste`), e nenhuma delas liga ou desliga nada: a
# grade de seis do TikTok vale desde que o codigo entra e NAO volta a dez
# sozinha quando o teste acaba. Aqui so se mede o antes e o durante.
TESTE_DO_TIKTOK = "tiktok_6_por_dia"
TESTE_DA_PARTE_SEGUINTE = "parte_seguinte"
# Views de cada video aos `IDADE_DA_MEDIDA` dias (pela fotografia diaria):
# o video de antes do teste tem mais dias no ar, e comparar o total de hoje
# daria vantagem a ele so pela idade.
IDADE_DA_MEDIDA = MADURO_DIAS


def _fotos(pasta_do_historico: Path | None = None) -> dict:
    """{'AAAA-MM-DD': fotografia} de todas as fotografias diarias gravadas."""
    pasta_h = pasta_do_historico or (pasta() / "historico")
    saida = {}
    try:
        arquivos = sorted(Path(pasta_h).glob("*.json"))
    except OSError:
        return saida
    for arquivo in arquivos:
        dado = _ler_json(arquivo)
        if dado:
            saida[arquivo.stem] = dado
    return saida


def _views_na_idade(r: dict, fotos: dict, dias: int = IDADE_DA_MEDIDA):
    """Views do video na fotografia do dia em que ele fez `dias` dias; `None`
    sem essa fotografia."""
    try:
        postado = date.fromisoformat(r["quando"][:10])
    except (KeyError, ValueError):
        return None
    foto = (fotos or {}).get((postado + timedelta(days=dias)).isoformat()) or {}
    valor = (foto.get(nome_da_parte(r["canal"], r["plataforma"])) or {}).get(r["id"])
    if isinstance(valor, list) and valor and isinstance(valor[0], (int, float)):
        return int(valor[0])
    return None


def _dias(inicio: date, fim: date) -> list:
    return [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]


def _janela_do_tiktok(tk: list, ledger: list, dias: list, fotos: dict,
                      hoje: date) -> dict:
    """Um lado do teste: por dia, posts (do ledger), views somadas dos videos
    postados no dia e se o dia ja tem todos os videos com 3+ dias."""
    por_dia = []
    for d in dias:
        dia = d.isoformat()
        medidos = [r for r in tk if r["quando"][:10] == dia]
        postados = sum(1 for l in ledger
                       if str(l.get("plataforma") or "youtube") == "tiktok"
                       and str(l.get("quando") or "")[:10] == dia)
        na_idade = [_views_na_idade(r, fotos) for r in medidos]
        pela_foto = bool(medidos) and all(v is not None for v in na_idade)
        views = [v if pela_foto else r["views"] for v, r in zip(na_idade, medidos)]
        por_dia.append({"dia": dia, "posts": max(postados, len(medidos)),
                        "medidos": len(medidos), "views": sum(views),
                        "por_post": views, "pela_foto": pela_foto,
                        # Dia que ainda nao fez 3 dias (ou nem chegou) nao e
                        # um dia de ZERO views: e um dia que ainda nao conta.
                        "maduro": (d + timedelta(days=MADURO_DIAS) <= hoje
                                   and all(r["idade_dias"] >= MADURO_DIAS
                                           for r in medidos))})
    maduros = [d for d in por_dia if d["maduro"]]
    return {"dias": por_dia, "dias_maduros": len(maduros),
            "views_por_dia": mediana(d["views"] for d in maduros),
            "por_post": mediana(v for d in maduros for v in d["por_post"]),
            "posts_por_dia": mediana(d["posts"] for d in maduros),
            "dias_sem_post": sum(1 for d in maduros if not d["posts"]),
            "sem_numero": sum(d["posts"] - d["medidos"] for d in por_dia
                              if d["posts"] > d["medidos"])}


def resultado_do_teste_tiktok(regs: list, agora: datetime, teste: dict | None,
                              ledger: dict | None = None,
                              fotos: dict | None = None) -> dict:
    """O teste de seis por dia no TikTok: ANTES x DURANTE, por perfil.

    ANTES = os mesmos tantos dias logo antes do inicio. Por dia: as views
    somadas dos videos POSTADOS naquele dia (nao e views do perfil por dia), aos
    3 dias de idade quando ha fotografia, e a mediana por post. So dia com
    todos os videos com 3+ dias entra nas medianas — o fim do teste so fecha 3
    dias depois do ultimo dia.

    Veredito por perfil, so com os dois lados inteiros: "efeito" quando a
    mediana do durante passa a do antes e o teste de postos (dia contra dia)
    da p < 0,05; senao "sem efeito claro" e a recomendacao (so recomendacao)
    e o teste seguinte: um dia inteiro sem postar. ZERO nao e efeito: perfil
    sem nenhum video medido nos dois lados e "sem dados".
    """
    if not teste:
        return {"estado": "sem_teste"}
    inicio, fim = teste["inicio"], teste["fim"]
    n = (fim - inicio).days + 1
    antes = _dias(inicio - timedelta(days=n), inicio - timedelta(days=1))
    durante = _dias(inicio, fim)
    hoje = agora.date()
    saida = {"inicio": inicio.isoformat(), "fim": fim.isoformat(),
             "antes_de": antes[0].isoformat(), "posts_no_teste": POSTS_DO_TESTE,
             "perfis": {}}
    if hoje < inicio:
        saida["estado"] = "nao_comecou"
    elif hoje <= fim + timedelta(days=MADURO_DIAS):
        saida["estado"] = "em_andamento"
    else:
        saida["estado"] = "terminado"
    for canal in metricas.CANAIS:
        tk = [r for r in regs if r["canal"] == canal and r["plataforma"] == "tiktok"]
        linhas = list((ledger or {}).get(canal) or [])
        a = _janela_do_tiktok(tk, linhas, antes, fotos or {}, hoje)
        b = _janela_do_tiktok(tk, linhas, durante, fotos or {}, hoje)
        # A MESMA MEDIDA NOS DOIS LADOS: aos 3 dias so se TODO dia com video
        # tem a fotografia; senao o total de hoje dos dois (o de antes tem mais
        # dias no ar — vies CONTRA o teste, e e dito).
        pela_foto = all(d["pela_foto"] for d in a["dias"] + b["dias"] if d["medidos"])
        if not pela_foto:
            a = _janela_do_tiktok(tk, linhas, antes, {}, hoje)
            b = _janela_do_tiktok(tk, linhas, durante, {}, hoje)
        fora = [d["dia"] for d in b["dias"] if d["posts"] > POSTS_DO_TESTE]
        perfil = {"antes": a, "durante": b, "dias_fora_do_regime": fora,
                  "medida": ("views aos 3 dias" if pela_foto else
                             "views de hoje (os vídeos de antes têm mais dias no ar)")}
        if not any(d["medidos"] for d in a["dias"] + b["dias"]):
            perfil["veredito"] = "sem_dados"
        elif a["dias_maduros"] < n or b["dias_maduros"] < n:
            perfil["veredito"] = "juntando"
        else:
            va = [d["views"] for d in a["dias"]]
            vb = [d["views"] for d in b["dias"]]
            p = p_valor(vb, va)
            perfil["p"] = round(p, 4)
            perfil["veredito"] = ("efeito" if (b["views_por_dia"] or 0)
                                  > (a["views_por_dia"] or 0) and p < 0.05
                                  else "sem_efeito")
        if perfil["veredito"] == "sem_efeito":
            perfil["proximo_teste"] = ("um dia inteiro sem postar no TikTok (as "
                                       "pausas de 22 h ou mais deram certo 6 de 6 "
                                       "no builds e 3 de 3 nas histórias)")
        saida["perfis"][canal] = perfil
    return saida


def resultado_da_parte_seguinte(regs: list, agora: datetime,
                                teste: dict | None) -> dict:
    """Quantos seguem da parte N para a N+1 no YouTube das historias, com a
    parte N postada ANTES do teste x DURANTE (o texto "a parte seguinte ja esta
    no canal" no fim da descricao). Mesmo criterio do `achado_seguimento`:
    N com 100+ views, N+1 com 3+ dias e postada depois; a medida e a mediana
    de views da N+1 para cada 100 da N."""
    if not teste:
        return {"estado": "sem_teste"}
    inicio, fim = teste["inicio"], teste["fim"]
    proprios = [r for r in regs if r["canal"] == "historias"
                and r["plataforma"] == "youtube" and r.get("publico") is True
                and r.get("parte")]
    por_serie = defaultdict(dict)
    for r in proprios:
        por_serie[r.get("fonte_id")].setdefault(int(r["parte"]), r)
    lados = {"antes": [], "durante": []}
    for partes in por_serie.values():
        for n_, r in partes.items():
            seguinte = partes.get(n_ + 1)
            if not (r["views"] >= 100 and seguinte
                    and seguinte["idade_dias"] >= MADURO_DIAS
                    and _quando(seguinte) > _quando(r)):
                continue
            dia = date.fromisoformat(r["quando"][:10])
            lado = ("durante" if inicio <= dia <= fim else
                    "antes" if dia < inicio else None)
            if lado:
                lados[lado].append(seguinte["views"] / r["views"] * 100)
    estado = ("nao_comecou" if agora.date() < inicio else
              "em_andamento" if agora.date() <= fim + timedelta(days=MADURO_DIAS)
              else "terminado")
    return {"estado": estado, "inicio": inicio.isoformat(), "fim": fim.isoformat(),
            "pares_antes": len(lados["antes"]), "pares_durante": len(lados["durante"]),
            "por_100_antes": mediana(lados["antes"]),
            "por_100_durante": mediana(lados["durante"])}


def achado_formato(regs: list, agora: datetime, canal: str, plataforma: str) -> tuple:
    janela = _na_janela([r for r in regs if r["canal"] == canal
                         and r["plataforma"] == plataforma], agora)
    grupos = defaultdict(list)
    for r in janela:
        grupos[r["formato"]].append(r)
    grupos = {f: g for f, g in grupos.items() if len(g) >= MIN_N}
    if len(grupos) < 2:
        return None, None
    ordem = sorted(grupos, key=lambda f: mediana(r["views"] for r in grupos[f]) or 0)
    pior, melhor = ordem[0], ordem[-1]
    vm = [r["views"] for r in grupos[melhor]]
    vp = [r["views"] for r in grupos[pior]]
    conf = confianca(vm, vp)
    mm, mp = mediana(vm), mediana(vp)
    rotulo = rotulo_da_parte(canal, plataforma)
    if conf == "incerto" or not mm or (mp or 0) * 1.5 > mm:
        return None, (f"{rotulo}: {NOME_DO_FORMATO.get(melhor, melhor)} ({_v(mm)}) × "
                      f"{NOME_DO_FORMATO.get(pior, pior)} ({_v(mp)}) — diferença dentro do acaso")
    def ret(f):
        return mediana(r["retencao"] for r in grupos[f])

    def n_ret(f):
        return sum(1 for r in grupos[f] if r["retencao"] is not None)
    linhas = []
    for f in reversed(ordem):
        linhas.append(f"{NOME_DO_FORMATO.get(f, f)}: {_v(mediana(r['views'] for r in grupos[f]))} "
                      f"({len(grupos[f])} vídeos; assistem {_pct(ret(f))}, medido em {n_ret(f)})")
    # O melhor formato semana a semana (segunda a domingo, so semana com 5+
    # videos): se ele vem caindo, o ganho e uma FAIXA, nao um numero.
    semanas = defaultdict(list)
    for r in grupos[melhor]:
        d = _quando(r).date()
        semanas[(d - timedelta(days=d.weekday())).isoformat()].append(r["views"])
    serie = [mediana(v) for _k, v in sorted(semanas.items()) if len(v) >= 5]
    caindo = len(serie) >= 3 and all(b < a for a, b in zip(serie, serie[1:]))
    por_dia_pior = len(grupos[pior]) / _dias_efetivos(janela)
    baixo = por_dia_pior * max(min(serie + [mm]) - mp, 0)
    alto = por_dia_pior * max(max(serie + [mm]) - mp, 0)
    texto_serie = ""
    if caindo:
        texto_serie = (f" Atenção: {o_(melhor)} vem caindo semana a semana ("
                       + " → ".join(_fmt(x) for x in serie) + " views por vídeo).")
    return _achado(
        f"formato:{canal}:{plataforma}", nome_da_parte(canal, plataforma),
        "acerto",
        f"{rotulo}: {o_(melhor)} é o que mais rende views; {o_(pior)} é o que menos rende",
        (f"Views por vídeo (o do meio da fila) nos últimos {JANELA_DIAS} dias — "
         + "; ".join(linhas) + ". Quanto as pessoas assistem não se compara direto entre "
         "vídeos de duração diferente (vídeo curto tem porcentagem maior sozinho)."
         + texto_serie),
        (f"Troque os vídeos de {NOME_DO_FORMATO.get(pior, pior)} por "
         f"{NOME_DO_FORMATO.get(melhor, melhor)} (hoje sai {_fmt(por_dia_pior)} "
         f"{NOME_DO_FORMATO.get(pior, pior)} por dia)."),
        (f"Entre +{_fmt(baixo)} e +{_fmt(alto)} views por dia neste canal (a faixa sai das "
         f"semanas {do_(melhor)})."),
        conf, (baixo + alto) / 2, melhor=melhor, pior=pior, mediana_melhor=mm,
        mediana_pior=mp, n_melhor=len(vm), n_pior=len(vp), semanas_do_melhor=serie,
        caindo=caindo, n_retencao={f: n_ret(f) for f in ordem}), None


def achado_concentracao(regs: list, agora: datetime, canal: str, plataforma: str) -> tuple:
    """Um video so leva quase todas as views do dia?"""
    janela = _na_janela([r for r in regs if r["canal"] == canal
                         and r["plataforma"] == plataforma], agora)
    # So DIA INTEIRO maduro: o dia de 3 dias atras tem a manha com 3+ dias e
    # a noite ainda nao. Em 19/10 o 16/10 entrava com 3 de 8 videos e o
    # "vencedor" dele era um video da manha com 3 views.
    imaturos = {r["quando"][:10] for r in _na_janela(
        [r for r in regs if r["canal"] == canal and r["plataforma"] == plataforma],
        agora, maduros=False) if r["idade_dias"] < MADURO_DIAS}
    dias = defaultdict(list)
    for r in janela:
        if r["quando"][:10] not in imaturos:
            dias[r["quando"][:10]].append(r)
    fatias, horas, resto = [], Counter(), []
    for lista in dias.values():
        total = sum(r["views"] for r in lista)
        if len(lista) < 3 or total < 30:
            continue
        top = max(lista, key=lambda r: r["views"])
        fatias.append(top["views"] / total)
        horas[top["hora"]] += 1
        resto.append(total - top["views"])
    if len(fatias) < MIN_N:
        return None, None
    fatia = mediana(fatias)
    if fatia is None or fatia < 0.6:
        return None, None
    na_noite = sum(n for h, n in horas.items() if h in NOITE)
    if na_noite * 2 < len(fatias):
        # O vencedor do dia nao e da noite: o achado e outro (horario), nao este.
        return None, None
    hora, _vezes = max(((h, n) for h, n in horas.items() if h in NOITE), key=lambda x: x[1])
    da_noite = [r["views"] for r in janela if r["hora"] in NOITE]
    outras = [r["views"] for r in janela if r["hora"] not in NOITE]
    conf = confianca(da_noite, outras)
    posts_por_dia = len(janela) / _dias_efetivos(janela)
    rotulo = rotulo_da_parte(canal, plataforma)
    # Os ultimos 7 dias, um por um: qual video da noite levou o dia. Os de
    # menos de 3 dias ainda estao juntando view e sao ditos como tal.
    publicos = [r for r in regs if r["canal"] == canal and r["plataforma"] == plataforma
                and r.get("publico") is True]
    dias_recentes = []
    for i in range(1, 8):
        dia = (agora.date() - timedelta(days=i)).isoformat()
        noite = [r for r in publicos if r["quando"][:10] == dia and r["hora"] in NOITE]
        topo = max(noite, key=lambda r: r["views"]) if noite else None
        # Maduro pela IDADE DO VIDEO (agora - postado), nao pela distancia do
        # dia no calendario: "16/10 23:42 = 5" tinha 2,5 dias no ar em 19/10 e
        # saia sem "(ainda juntando views)", contado como dia perdido. Noite
        # sem video nenhum e perdida de qualquer jeito: a noite ja passou.
        dias_recentes.append({"dia": dia, "hora": topo["quando"][11:16] if topo else None,
                              "views": topo["views"] if topo else None,
                              "idade_dias": topo["idade_dias"] if topo else None,
                              "maduro": topo["idade_dias"] >= MADURO_DIAS if topo else True})
    def _dia_txt(d):
        if d["views"] is None:
            return f"{_data_br(d['dia'])}: nenhum vídeo à noite"
        extra = "" if d["maduro"] else " (ainda juntando views)"
        return f"{_data_br(d['dia'])} {d['hora']} = {_fmt(d['views'])}{extra}"
    perdidos = [d for d in dias_recentes if d["maduro"]
                and (d["views"] is None or d["views"] < 30)]
    # O vencedor do dia rendeu menos? Ultimos 7 dias medidos contra os 7 antes.
    vencedores = []
    for dia, lista in sorted(dias.items()):
        if len(lista) >= 3:
            vencedores.append(max(r["views"] for r in lista))
    ultimos, antes = vencedores[-7:], vencedores[-14:-7]
    comparacao = ""
    if len(ultimos) >= 5 and len(antes) >= 5:
        comparacao = (f" O vídeo que leva o dia também rendeu menos: mediana de "
                      f"{_v(mediana(ultimos))} nos últimos 7 dias medidos, contra "
                      f"{_v(mediana(antes))} nos 7 anteriores.")
    return _achado(
        f"concentracao:{canal}:{plataforma}", nome_da_parte(canal, plataforma),
        "atencao",
        f"{rotulo}: um vídeo da noite (21h às 23h) leva o dia inteiro",
        (f"Em {len(fatias)} dias medidos, o vídeo mais visto levou {_pct(fatia * 100)} das "
         f"views do dia (mediana), e em {na_noite} desses dias ele saiu à noite, entre 21h e "
         f"23h (mais vezes às {hora}h). Vídeos da noite: {_v(mediana(da_noite))} por vídeo; "
         f"dos outros horários: {_v(mediana(outras))}. Os outros ~{_fmt(posts_por_dia - 1)} "
         f"vídeos do dia somam ~{_v(mediana(resto))}. Últimos 7 dias, o melhor da noite: "
         + "; ".join(_dia_txt(d) for d in dias_recentes) + "." + comparacao),
        (f"Ponha o melhor vídeo pronto no primeiro horário da noite ({hora}h) e nunca deixe "
         f"a noite sem vídeo. Os outros horários rendem pouco; dá para postar menos neles "
         f"e guardar estoque."),
        (f"Postar menos nos outros horários mexe pouco nas views (~{_fmt(mediana(resto))} "
         f"por dia) e economiza vídeo. O ganho de verdade está em o vídeo da noite ser bom."),
        conf, (mediana(da_noite) or 0) * 0.2, hora=hora, dias=len(fatias),
        dias_na_noite=na_noite, fatia_mediana=round(fatia, 3),
        mediana_noite=mediana(da_noite), mediana_outras=mediana(outras),
        resto_por_dia=mediana(resto), ultimos_7_dias=dias_recentes,
        dias_perdidos=[d["dia"] for d in perdidos],
        vencedor_ultimos_7=mediana(ultimos), vencedor_7_antes=mediana(antes)), None


def achado_seguimento(regs: list, agora: datetime, canal: str, plataforma: str) -> tuple:
    """Quem ve uma parte que foi bem vai atras da parte seguinte?"""
    # So PUBLICO (com status): video sem status ou rascunho nao tem view que
    # se compare. E a seguinte tem de ter saido DEPOIS da anterior (historia
    # republicada fora de ordem nao mede "seguir").
    proprios = [r for r in regs if r["canal"] == canal and r["plataforma"] == plataforma
                and r.get("publico") is True and r.get("parte")]
    por_serie = defaultdict(dict)
    for r in proprios:
        por_serie[r.get("fonte_id")].setdefault(int(r["parte"]), r)
    pares = []
    for partes in por_serie.values():
        for n, r in partes.items():
            seguinte = partes.get(n + 1)
            if (r["views"] >= 100 and seguinte and seguinte["idade_dias"] >= MADURO_DIAS
                    and _quando(seguinte) > _quando(r)):
                pares.append((r, seguinte))
    if len(pares) < 5:
        return None, None
    razao = mediana(s["views"] / r["views"] for r, s in pares)
    if razao is None or razao >= 0.25:
        return None, None
    na_noite = sum(1 for r, _s in pares if r["hora"] in NOITE)
    comuns = [x["views"] for x in _na_janela(proprios, agora) if x["hora"] not in NOITE]
    rotulo = rotulo_da_parte(canal, plataforma)
    # Vies que impede a conclusao: a parte que passou de 100 e quase sempre a
    # da noite (a que leva o dia) e a seguinte cai num horario comum, que
    # rende pouco por si so. "Nao seguem" e "o horario nao ajuda" se misturam.
    return _achado(
        f"seguimento:{canal}:{plataforma}", nome_da_parte(canal, plataforma), "atencao",
        f"{rotulo}: quase ninguém vai da parte que bombou para a seguinte — mas ainda "
        f"não dá para separar isso do horário",
        (f"Em {len(pares)} partes que passaram de 100 views, a parte seguinte teve "
         f"{_fmt(razao * 100)} views para cada 100 da anterior. Só que {na_noite} dessas "
         f"{len(pares)} eram o vídeo da noite, e a seguinte saiu num horário comum, que "
         f"rende ~{_v(mediana(comuns))} por si só. Então o número mistura \"não seguem\" "
         f"com \"o horário não ajuda\"."),
        ("Testar por 1 semana: ligar cada parte à seguinte dentro do próprio Shorts (o "
         "\"vídeo relacionado\" embaixo do vídeo) e terminar a fala com \"a parte seguinte "
         "já está no canal\". Depois medir aqui quantos seguem."),
        "Não dá para estimar antes do teste.",
        "incerto", 5, razao_mediana=round(razao, 4), pares=len(pares),
        pares_da_noite=na_noite, mediana_horario_comum=mediana(comuns)), None


def achado_horario(regs: list, agora: datetime, canal: str, plataforma: str,
                   ja_dito: set) -> tuple:
    janela = _na_janela([r for r in regs if r["canal"] == canal
                         and r["plataforma"] == plataforma], agora)
    horas = defaultdict(list)
    for r in janela:
        horas[r["hora"]].append(r["views"])
    melhor = None
    for hora, vs in horas.items():
        outras = [r["views"] for r in janela if r["hora"] != hora]
        if len(vs) < MIN_N or len(outras) < MIN_N or hora in ja_dito:
            continue
        p = p_valor(vs, outras)
        if melhor is None or p < melhor[1]:
            melhor = (hora, p, vs, outras)
    rotulo = rotulo_da_parte(canal, plataforma)
    if melhor is None:
        return None, None
    hora, p, vs, outras = melhor
    if p >= 0.005:
        fora = sorted(h for h in ja_dito if h is not None)
        prefixo = ("fora os da noite (21h a 23h), nenhum outro horário"
                   if set(fora) == set(NOITE) else
                   f"fora o das {', '.join(f'{h}h' for h in fora)}, nenhum outro horário"
                   if fora else "nenhum horário")
        return None, f"{rotulo}: {prefixo} se destaca dos outros (diferenças dentro do acaso)"
    mh, mo = mediana(vs), mediana(outras)
    bom = (mh or 0) > (mo or 0)
    return _achado(
        f"horario:{canal}:{plataforma}:{hora}", nome_da_parte(canal, plataforma),
        "acerto" if bom else "atencao",
        f"{rotulo}: o horário das {hora}h {'rende mais' if bom else 'rende menos'} que os outros",
        (f"Vídeos das {hora}h: {_v(mh)} por vídeo ({len(vs)} vídeos); os outros "
         f"horários, {_fmt(mo)} ({len(outras)})."),
        (f"Ponha às {hora}h o vídeo mais forte do dia." if bom else
         f"Não ponha às {hora}h o vídeo mais forte do dia."),
        f"Diferença de ~{_fmt(abs((mh or 0) - (mo or 0)))} views por vídeo nesse horário.",
        "claro" if min(len(vs), len(outras)) >= 10 else "provavel",
        abs((mh or 0) - (mo or 0)) * 0.5, hora=hora, mediana_hora=mh, mediana_outras=mo), None


def achado_duracao(regs: list, agora: datetime, canal: str, plataforma: str) -> list:
    """Dentro do MESMO formato, o mais curto rende mais views?

    So views: retencao em porcentagem sobe sozinha em video curto, e isso
    nao e achado nenhum.
    """
    janela = _na_janela([r for r in regs if r["canal"] == canal
                         and r["plataforma"] == plataforma], agora)
    saida, incertos = [], []
    grupos = defaultdict(list)
    for r in janela:
        if r.get("duracao_s"):
            grupos[r["formato"]].append(r)
    rotulo = rotulo_da_parte(canal, plataforma)
    for formato, lista in grupos.items():
        if len(lista) < 2 * MIN_N:
            continue
        corte = mediana(r["duracao_s"] for r in lista)
        curtos = [r["views"] for r in lista if r["duracao_s"] <= corte]
        longos = [r["views"] for r in lista if r["duracao_s"] > corte]
        conf = confianca(curtos, longos)
        mc, ml = mediana(curtos), mediana(longos)
        nome = NOME_DO_FORMATO.get(formato, formato)
        if conf == "incerto" or not mc or not ml or max(mc, ml) < 1.3 * min(mc, ml):
            incertos.append(f"{rotulo}: duração {do_(formato)} (até {_fmt(corte)} s: {_v(mc)}; "
                            f"mais longo: {_v(ml)}) — não muda as views de forma clara")
            continue
        curto_ganha = mc > ml
        por_dia = len(lista) / _dias_efetivos(janela)
        ganho = por_dia * abs(mc - ml) / 2
        saida.append(_achado(
            f"duracao:{canal}:{plataforma}:{formato}", nome_da_parte(canal, plataforma),
            "acerto",
            f"{rotulo}: {o_(formato)} mais "
            f"{('curt' if curto_ganha else 'long') + ('a' if formato in FEMININOS else 'o')} "
            f"rende mais",
            (f"{nome.capitalize()} de até {_fmt(corte)} s: {_v(mc)} por vídeo "
             f"({len(curtos)}); acima disso, {_fmt(ml)} ({len(longos)})."),
            (f"Mire {o_(formato)} em {'até' if curto_ganha else 'mais de'} {_fmt(corte)} segundos."),
            f"Cerca de +{_fmt(ganho)} views por dia.", conf, ganho,
            corte_s=corte, mediana_curtos=mc, mediana_longos=ml))
    return saida, incertos


def tendencia(regs: list, agora: datetime, serie: dict | None = None) -> dict:
    """Subindo ou caindo? Pela serie diaria do canal quando ela existe
    (views de verdade por dia, de todos os videos); senao pela mediana por
    video das duas ultimas semanas contra as duas anteriores."""
    dias = {}
    if serie and isinstance(serie.get("dias"), list):
        dias = {str(d[0]): int(d[1] or 0) for d in serie["dias"]
                if isinstance(d, (list, tuple)) and len(d) >= 2}
    if len(dias) >= 14:
        fim = max(dias)
        ultimo = date.fromisoformat(fim)
        sete = [dias.get((ultimo - timedelta(days=i)).isoformat(), 0) for i in range(7)]
        antes = [dias.get((ultimo - timedelta(days=i)).isoformat(), 0) for i in range(7, 14)]
        a, b = sum(sete), sum(antes)
        variacao = (a - b) / b if b else None
        # Zero contra zero NAO e "sem dados" nem "estavel": e canal parado.
        sentido = ("parado" if a == 0 and b == 0 else
                   "subindo" if b == 0 else _sentido(variacao, True))
        return {"fonte": "canal", "ultimos_7": a, "anteriores_7": b, "ate": fim,
                "variacao": round(variacao, 3) if variacao is not None else None,
                "sentido": sentido}
    maduros = [r for r in regs if r.get("publico") is True
               and r["idade_dias"] >= MADURO_DIAS]
    fim = agora - timedelta(days=MADURO_DIAS)
    recentes = [r["views"] for r in maduros
                if fim - timedelta(days=14) <= datetime.fromisoformat(r["quando"]) < fim]
    antes = [r["views"] for r in maduros
             if fim - timedelta(days=28) <= datetime.fromisoformat(r["quando"]) < fim - timedelta(days=14)]
    ma, mb = mediana(recentes), mediana(antes)
    variacao = (ma - mb) / mb if ma is not None and mb else None
    conf = confianca(recentes, antes)
    # Mediana abaixo de 3 views nas duas metades: "caiu de 2 para 1" e
    # verdade e nao diz nada — o perfil esta parado.
    parado = ma is not None and mb is not None and max(ma, mb) < 3
    return {"fonte": "por_video", "mediana_recente": ma, "mediana_antes": mb,
            "n_recente": len(recentes), "n_antes": len(antes),
            "variacao": round(variacao, 3) if variacao is not None else None,
            "sentido": "parado" if parado else _sentido(variacao, conf != "incerto"),
            "confianca": conf}


def _sentido(variacao, firme: bool) -> str:
    if variacao is None:
        return "sem_dados"
    if not firme or abs(variacao) < 0.15:
        return "estavel"
    return "subindo" if variacao > 0 else "caindo"


def extremos(regs: list, agora: datetime, quantos: int = 5) -> dict:
    janela = _na_janela(regs, agora)
    if not janela:
        return {"melhores": [], "piores": [], "em_comum": ""}
    ordem = sorted(janela, key=lambda r: (r["views"], r["quando"]), reverse=True)
    melhores, piores = ordem[:quantos], ordem[-quantos:][::-1]
    dez_mais, dez_menos = ordem[:10], ordem[-10:]

    def perfil(lista):
        formatos = Counter(NOME_DO_FORMATO.get(r["formato"], r["formato"]) for r in lista)
        f, n = formatos.most_common(1)[0]
        dur = mediana(r.get("duracao_s") for r in lista)
        horas = Counter(r["hora"] for r in lista).most_common(1)[0]
        return (f"{n} de {len(lista)} são {f}, duração mediana {_fmt(dur)} s, "
                f"hora mais comum {horas[0]}h")
    em_comum = ""
    if len(ordem) >= 20:
        em_comum = f"Os 10 melhores: {perfil(dez_mais)}. Os 10 piores: {perfil(dez_menos)}."
    return {"melhores": melhores, "piores": piores, "em_comum": em_comum}


def tabela(regs: list, agora: datetime, chave) -> list:
    janela = _na_janela(regs, agora)
    grupos = defaultdict(list)
    for r in janela:
        grupos[chave(r)].append(r)
    linhas = []
    for k, lista in grupos.items():
        linhas.append({"grupo": k, "n": len(lista),
                       "views": mediana(r["views"] for r in lista),
                       "retencao": mediana(r["retencao"] for r in lista),
                       "n_retencao": sum(1 for r in lista if r["retencao"] is not None)})
    return sorted(linhas, key=lambda x: -(x["views"] or 0))


def _par_youtube_tiktok(regs: list, agora: datetime, canal: str) -> dict:
    yt = {r["video_id"]: r for r in _na_janela(regs, agora)
          if r["canal"] == canal and r["plataforma"] == "youtube" and r.get("video_id")}
    pares = [(yt[r["video_id"]]["views"], r["views"]) for r in _na_janela(regs, agora)
             if r["canal"] == canal and r["plataforma"] == "tiktok"
             and r.get("video_id") in yt]
    return {"pares": len(pares),
            "youtube": mediana(a for a, _b in pares),
            "tiktok": mediana(b for _a, b in pares)}


_TIPO = {"builds": "arena", "historias": "estrutura"}
_NOME_DO_TIPO = {"builds": "arena do duelo", "historias": "tipo de história"}


def analisar(regs: list, cob: dict, agora: datetime, series: dict | None = None,
             historico: dict | None = None, falhas: list | None = None, *,
             testes: dict | None = None, ledger: dict | None = None,
             fotos: dict | None = None, semana: dict | None = None,
             leituras: list | None = None, horas_das_fotos: dict | None = None,
             erro_da_semana: str = "", contas_tiktok: dict | None = None) -> dict:
    """A analise inteira, sem disco e sem rede. `regs` vazio = `sem_dados`.

    `testes`: {nome: {"inicio", "fim"}} (`grade.teste`); `ledger` (por canal)
    e `fotos` (fotografias diarias) servem ao resultado deles.

    `semana` (`mesma_idade.semana_vigente`), `leituras` (de hora em hora) e
    `horas_das_fotos` servem a MEDIDA DA SEMANA na mesma idade
    (`analise["mesma_idade"]`); `contas_tiktok` ({canal: {dia: ficha}}) a
    situacao da conta no TikTok (`analise["conta_tiktok"]`).
    """
    from . import mesma_idade

    series = series or {}
    testes = testes or {}
    avisos = list(falhas or [])
    estado = cob.get("estado", "sem_dados")
    if not regs:
        estado = "sem_dados"
    if estado == "sem_dados":
        avisos.insert(0, "Nenhum vídeo com número medido. Sem dado, esta página não "
                         "pode dizer que nada vai bem — a coleta precisa voltar.")
    elif estado == "velha":
        avisos.insert(0, f"A coleta mais velha é de {cob.get('coleta_mais_velha') or 'nunca'}: "
                         f"os números abaixo podem estar parados.")
    elif estado == "incompleta":
        avisos.insert(0, "A coleta de hoje falhou em parte: algumas partes estão com o "
                         "número da última coleta boa.")
    for p in cob.get("partes", {}).values():
        if p["linhas_no_ledger"] and not p["medidos"]:
            avisos.append(f"{p['rotulo']}: "
                          f"{_qtd(p['linhas_no_ledger'], 'vídeo postado', 'vídeos postados')} e "
                          f"NENHUM com número medido.")
        if p.get("sem_arquivo"):
            avisos.append(f"{p['rotulo']}: "
                          f"{_qtd(p['sem_arquivo'], 'vídeo postado', 'vídeos postados')} antes "
                          f"da coleta ficaram sem número.")
        if p.get("parados"):
            # O mesmo video, dito UMA vez: o TikTok parou de mostra-lo, entao
            # o arquivo dele nao e mais renovado ("sem par" e "parado" sao ele).
            datas = ", ".join(_data_br(d) for d in p.get("parados_desde") or []) or "antes"
            avisos.append(f"{p['rotulo']}: {_qtd(p['parados'], 'vídeo', 'vídeos')} que o "
                          f"{NOME_DA_PLATAFORMA[p['plataforma']]} não mostra mais; o número "
                          f"deles parou em {datas}.")
        if p.get("nunca_medidos"):
            avisos.append(f"{p['rotulo']}: {_qtd(p['nunca_medidos'], 'vídeo postado', 'vídeos postados')} "
                          f"antes da coleta que nunca tiveram número.")
    achados, nao_da = [], []

    def junta(resultado):
        a, incerto = resultado
        if isinstance(a, list):
            achados.extend(x for x in a if x)
        elif a:
            achados.append(a)
        if isinstance(incerto, list):
            nao_da.extend(incerto)
        elif incerto:
            nao_da.append(incerto)

    partes = {}
    for canal in metricas.CANAIS:
        canal_regs = [r for r in regs if r["canal"] == canal]
        junta(achado_pausa_tiktok(canal_regs, agora, canal))
        for plataforma in PLATAFORMAS:
            proprios = [r for r in canal_regs if r["plataforma"] == plataforma]
            nome = nome_da_parte(canal, plataforma)
            antes = len(achados)
            junta(achado_formato(canal_regs, agora, canal, plataforma))
            junta(achado_concentracao(canal_regs, agora, canal, plataforma))
            # A noite ja foi dita pelo achado da concentracao: o de horario
            # olha os outros.
            ditas = (set(NOITE) if any(a["id"].startswith("concentracao")
                                        for a in achados[antes:]) else set())
            junta(achado_horario(canal_regs, agora, canal, plataforma, ditas))
            junta(achado_duracao(canal_regs, agora, canal, plataforma))
            if canal == "historias":
                junta(achado_seguimento(canal_regs, agora, canal, plataforma))
            serie = series.get(canal) if plataforma == "youtube" else None
            janela = _na_janela(proprios, agora)
            ontem = (historico or {}).get(nome) or {}
            ganho = None
            if ontem:
                atual = {r["id"]: r["views"] for r in proprios}
                ganho = sum(v - int(ontem.get(i, [0])[0] or 0) for i, v in atual.items()
                            if i in ontem)
            partes[nome] = {
                "canal": canal, "plataforma": plataforma,
                "rotulo": rotulo_da_parte(canal, plataforma),
                "videos": len(proprios),
                "views_total": sum(r["views"] for r in proprios),
                "na_janela": len(janela),
                "mediana_views": mediana(r["views"] for r in janela),
                "mediana_retencao": mediana(r["retencao"] for r in janela),
                "n_retencao": sum(1 for r in janela if r["retencao"] is not None),
                "tendencia": tendencia(proprios, agora, serie),
                "extremos": extremos(proprios, agora),
                "formatos": tabela(proprios, agora, lambda r: r["formato"]),
                "horas": sorted(tabela(proprios, agora, lambda r: r["hora"]),
                                key=lambda x: x["grupo"]),
                "dias_da_semana": sorted(tabela(proprios, agora, lambda r: r["dia_semana"]),
                                         key=lambda x: x["grupo"]),
                # O que o video E alem do formato: a arena do duelo, a
                # estrutura da historia.
                "por_tipo": tabela([r for r in proprios if r.get(_TIPO[canal])], agora,
                                   lambda r, c=canal: str(r.get(_TIPO[c]))),
                "nome_do_tipo": _NOME_DO_TIPO[canal],
                "serie": (serie or {}).get("dias") if serie else None,
                "inscritos": (serie or {}).get("inscritos") if serie else None,
                "views_por_dia_de_postagem": sorted(_views_do_dia(
                    [r for r in proprios if r.get("publico") is not False]).items())[-JANELA_DIAS:],
                "ganho_desde_ontem": ganho,
            }
        partes[f"{canal}_par"] = _par_youtube_tiktok(canal_regs, agora, canal)
    # Os firmes primeiro, do que mais mexe para o que menos (`peso` = ganho
    # estimado em views por dia); depois os que so pedem TESTE (incertos com
    # recomendacao de testar — o resto dos incertos vai para `nao_da`).
    achados.sort(key=lambda a: (a["confianca"] == "incerto", -a["peso"]))
    resultado_dos_testes = {
        TESTE_DO_TIKTOK: resultado_do_teste_tiktok(
            regs, agora, testes.get(TESTE_DO_TIKTOK), ledger, fotos),
        TESTE_DA_PARTE_SEGUINTE: resultado_da_parte_seguinte(
            regs, agora, testes.get(TESTE_DA_PARTE_SEGUINTE)),
    }
    # Com o teste marcado, a recomendacao "testar" vira "esta em teste".
    marcados = {TESTE_DO_TIKTOK: "pausa-tiktok:", TESTE_DA_PARTE_SEGUINTE: "seguimento:"}
    for nome, prefixo in marcados.items():
        r = resultado_dos_testes[nome]
        if r.get("estado") in ("nao_comecou", "em_andamento", "terminado"):
            for a in achados:
                if a["id"].startswith(prefixo):
                    a["mudar"] = (f"Em teste de {_data_br(r['inicio'])} a {_data_br(r['fim'])} "
                                  f"({ESTADO_DO_TESTE[r['estado']]}): o resultado está em "
                                  f"\"Testes\".")
    # A MEDIDA DA SEMANA na mesma idade (21/10/2026) e a conta do TikTok.
    try:
        semana_na_idade = mesma_idade.comparar(
            regs, agora, semana, fotos=fotos, leituras=leituras,
            horas_das_fotos=horas_das_fotos, series=series,
            erro_do_config=erro_da_semana)
    except Exception as exc:                                  # noqa: BLE001
        semana_na_idade = {"estado": "erro", "erro": f"{type(exc).__name__}: {exc}",
                           "texto": f"Medida da semana FALHOU: {type(exc).__name__}: {exc}",
                           "avisos": [f"medida da semana falhou: {type(exc).__name__}: {exc}"]}
    avisos.extend(semana_na_idade.get("avisos") or [])
    conta = conta_tiktok(contas_tiktok, regs, agora)
    avisos.extend(conta.get("avisos") or [])
    return {"gerado_em": agora.isoformat(timespec="minutes"), "estado": estado,
            "avisos": avisos, "achados": achados, "nao_da": nao_da,
            "testes": resultado_dos_testes,
            "mesma_idade": semana_na_idade, "conta_tiktok": conta,
            "partes": partes, "cobertura": cob,
            "regras": {"janela_dias": JANELA_DIAS, "maduro_dias": MADURO_DIAS,
                       "min_views_retencao": MIN_VIEWS_RETENCAO, "min_n": MIN_N,
                       "pausa_tiktok_h": PAUSA_TIKTOK_H}}


def conta_tiktok(contas: dict | None, regs: list, agora: datetime) -> dict:
    """A conta de cada perfil do TikTok: a ultima ficha do coletor (serie
    diaria de views, seguidores, punicao, qualidade) e quantos posts recentes
    trazem a situacao (`status`/`visibility`/`in_review`/`permissions`).

    `contas=None` (quem chama nao carregou) = nada a dizer. Ficha que nao
    existe ou nao leu a punicao NAO e "sem punicao": e aviso de "nao medi".
    """
    if contas is None:
        return {"estado": "nao_carregado"}
    saida = {"estado": "ok", "perfis": {}, "avisos": []}
    for canal in metricas.CANAIS:
        fichas = (contas or {}).get(canal) or {}
        dia = max(fichas) if fichas else None
        ficha = fichas.get(dia) or {}
        recentes = [r for r in regs if r["canal"] == canal and r["plataforma"] == "tiktok"
                    and r["idade_dias"] <= JANELA_DIAS]
        com = [r for r in recentes if isinstance(r.get("situacao"), dict)]
        vv = ficha.get("vv_history")
        sem_datas = isinstance(vv, list) and bool(vv) and any(
            not (isinstance(p, list) and p and p[0]) for p in vv)
        perfil = {"dia": dia, "seguidores": ficha.get("seguidores"),
                  "vv_history": vv if isinstance(vv, list) else None,
                  # "sem" = a serie veio sem data: N PONTOS, nunca "N dias".
                  "serie_datas": (None if not isinstance(vv, list) else "sem" if sem_datas
                                  else ficha.get("vv_history_datas") or "dos_pontos"),
                  "regra_das_datas": ficha.get("vv_history_regra_das_datas") or "",
                  "punicao_por_que": (ficha.get("punicao") or {}).get("por_que") or "",
                  "punicao_lida": bool((ficha.get("punicao") or {}).get("lida")),
                  "qualidade_lida": bool((ficha.get("qualidade") or {}).get("lida")),
                  "erro": ficha.get("erro") or "",
                  "posts_recentes": len(recentes), "com_situacao": len(com),
                  "em_revisao": sum(1 for r in com if r["situacao"].get("in_review") is True)}
        saida["perfis"][canal] = perfil
        rotulo = f"TikTok de {NOME_DO_CANAL.get(canal, canal)}"
        if not dia:
            saida["avisos"].append(f"{rotulo}: a situação da conta (punição, série diária, "
                                   "seguidores) nunca foi lida pelo coletor — não medi.")
            continue
        falta = [nome for nome, ok in (("punição", perfil["punicao_lida"]),
                                       ("conselho de qualidade", perfil["qualidade_lida"]),
                                       ("série diária de views", perfil["vv_history"] is not None),
                                       ("seguidores", perfil["seguidores"] is not None)) if not ok]
        if falta:
            saida["avisos"].append(f"{rotulo}: não li {', '.join(falta)} em {_data_br(dia)} "
                                   "(não medi — não quer dizer que está tudo bem)"
                                   + (f": {perfil['punicao_por_que']}"
                                      if perfil["punicao_por_que"] and not (
                                          perfil["punicao_lida"] and perfil["qualidade_lida"])
                                      else "") + ".")
        if perfil["serie_datas"] == "sem":
            saida["avisos"].append(f"{rotulo}: a série de views da conta veio SEM datas "
                                   f"({len(vv)} pontos) — não dá para dizer de que dias são"
                                   + (f" ({perfil['regra_das_datas']})"
                                      if perfil["regra_das_datas"] else "") + ".")
        if recentes and not com:
            saida["avisos"].append(f"{rotulo}: nenhum dos {len(recentes)} posts recentes trouxe a "
                                   "situação (revisão/visibilidade) — não medi.")
    return saida


# ------------------------------------------------------------------- rede
def buscar_serie_do_canal(canal: str, dias: int = 56, hoje: date | None = None) -> dict:
    """Views por dia do CANAL (todos os videos) e inscritos: 1 chamada na
    Analytics + 1 na Data API (1 unidade). Levanta se falhar — quem chama
    decide o aviso."""
    hoje = hoje or date.today()
    token, _cred = metricas._token(canal)
    cabeca = {"Authorization": f"Bearer {token}"}
    inicio = hoje - timedelta(days=dias)
    resposta = metricas._get("analytics", metricas.API_ANALYTICS, headers=cabeca, params={
        "ids": "channel==MINE", "startDate": inicio.isoformat(),
        "endDate": hoje.isoformat(), "dimensions": "day", "sort": "day",
        "metrics": "views,estimatedMinutesWatched,subscribersGained,subscribersLost",
    }, timeout=30)
    if resposta.status_code != 200:
        raise RuntimeError(f"a Analytics recusou a série do canal ({resposta.status_code}): "
                           f"{metricas.motivo_da_recusa(resposta, api='analytics')}")
    linhas = (resposta.json() or {}).get("rows") or []
    canal_resp = metricas._get("data", metricas.API_CANAIS, headers=cabeca, params={
        "part": "statistics", "mine": "true"}, timeout=30)
    estat = {}
    if canal_resp.status_code == 200:
        itens = (canal_resp.json() or {}).get("items") or []
        estat = (itens[0].get("statistics") or {}) if itens else {}
    def inteiro(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return {"canal": canal, "buscado_em": datetime.now().isoformat(timespec="seconds"),
            "dias": [[str(l[0]), int(l[1] or 0), int(l[2] or 0), int(l[3] or 0),
                      int(l[4] or 0)] for l in linhas if len(l) >= 5],
            "colunas": ["dia", "views", "minutos", "inscritos_ganhos", "inscritos_perdidos"],
            "inscritos": inteiro(estat.get("subscriberCount")),
            "views_do_canal": inteiro(estat.get("viewCount")),
            "videos_do_canal": inteiro(estat.get("videoCount"))}


# ----------------------------------------------------------------- disco
def _gravar(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix=caminho.name + ".", suffix=".tmp",
                                             dir=caminho.parent)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as saida:
            saida.write(texto)
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


COLUNAS_DA_FOTOGRAFIA = ["views", "likes", "retencao", "medido_em", "engaged_views"]


def fotografia(regs: list, cob: dict, series: dict | None = None,
               agora: datetime | None = None) -> dict:
    """Views de cada video hoje, para amanha saber quanto o canal GANHOU.
    Os arquivos de metrica guardam so o total da vida do video.

    Desde 21/10/2026 com a HORA: `quando_das_partes` (a ultima coleta boa de
    cada parte) e, por video, `medido_em` (a hora em que AQUELAS views foram
    lidas) — sem ela a comparacao na mesma idade teria de adivinhar. A lista
    de cada video so CRESCE no fim (`COLUNAS_DA_FOTOGRAFIA`): quem le `[0]`
    continua lendo views. E a serie de inscritos do canal (`canal`): o total
    de hoje (Data API, na hora) e os ganhos/perdidos por dia (Analytics,
    ~3 dias de atraso).
    """
    saida: dict = {"estado_da_coleta": cob.get("estado"),
                   "coleta_mais_velha": cob.get("coleta_mais_velha"),
                   "colunas": COLUNAS_DA_FOTOGRAFIA,
                   "gravada_em": (agora or datetime.now()).isoformat(timespec="seconds"),
                   "quando_das_partes": {nome: p.get("ultimo_ok") or None
                                         for nome, p in (cob.get("partes") or {}).items()}}
    for r in regs:
        nome = nome_da_parte(r["canal"], r["plataforma"])
        saida.setdefault(nome, {})[r["id"]] = [r["views"], r["likes"], r["retencao"],
                                               r.get("medido_em"), r.get("engaged_views")]
    canal_ = {}
    for canal, serie in (series or {}).items():
        if not isinstance(serie, dict):
            continue
        canal_[canal] = {
            "inscritos": serie.get("inscritos"), "views_do_canal": serie.get("views_do_canal"),
            "videos_do_canal": serie.get("videos_do_canal"), "buscado_em": serie.get("buscado_em"),
            "colunas_dos_dias": ["dia", "inscritos_ganhos", "inscritos_perdidos"],
            "dias": [[l[0], l[3], l[4]] for l in serie.get("dias") or []
                     if isinstance(l, list) and len(l) >= 5]}
    if canal_:
        saida["canal"] = canal_
    return saida


def gravar(analise: dict, regs: list, agora: datetime, series: dict | None = None) -> Path:
    destino = pasta()
    _gravar(destino / "analise.json", json.dumps(analise, ensure_ascii=False, indent=1,
                                                 default=str))
    _gravar(destino / "index.html", pagina(analise))
    _gravar(destino / "historico" / f"{agora.date().isoformat()}.json",
            json.dumps(fotografia(regs, analise["cobertura"], series, agora),
                       ensure_ascii=False))
    return destino / "index.html"


def _biblioteca(argumentos: list[str]) -> subprocess.CompletedProcess:
    """`python -m remoto.biblioteca ...` a partir da raiz do repositorio.

    Por processo, e nao por import: `remoto` so e importavel da raiz, e
    `builds` (o nucleo) nao pode depender do app.
    """
    raiz = Path(metricas.RAIZ).parent
    # UTF-8 no filho: no console do Windows ele imprimiria em cp1252, e um
    # titulo com emoji na Biblioteca derrubaria o `listar` com
    # UnicodeEncodeError.
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, "-m", "remoto.biblioteca", *argumentos],
                          cwd=str(raiz), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60,
                          env=ambiente,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def publicar_na_biblioteca(html_path: Path, executar=_biblioteca) -> str:
    """Poe (ou troca) a pagina "Analise dos videos" na Biblioteca do app.
    Devolve o id do item. Levanta se a Biblioteca recusar."""
    lista = executar(["listar", "--json"])
    if lista.returncode != 0:
        raise RuntimeError(f"a Biblioteca não listou: {lista.stderr.strip()[:200]}")
    try:
        itens = json.loads(lista.stdout or "[]")
    except ValueError as exc:
        raise RuntimeError("a Biblioteca devolveu lista ilegível") from exc
    meu = next((i for i in itens if isinstance(i, dict) and i.get("tipo") == "pagina"
                and TAG_DA_BIBLIOTECA in (i.get("tags") or [])), None)
    if meu:
        feito = executar(["guardar", "--id", str(meu["id"]), "--html", str(html_path)])
        id_ = str(meu["id"])
    else:
        feito = executar(["adicionar", "--titulo", TITULO_DA_PAGINA, "--tipo", "pagina",
                          "--html", str(html_path), "--tag", TAG_DA_BIBLIOTECA,
                          "--descricao", "Onde os vídeos acertam, onde erram e o que mudar. "
                                         "Atualiza todo dia depois da coleta."])
        id_ = (feito.stdout or "").strip()
    if feito.returncode != 0:
        raise RuntimeError(f"a Biblioteca recusou a página: {feito.stderr.strip()[:200]}")
    return id_


def _extras(entrada: dict) -> dict:
    """Os argumentos nomeados de `analisar` que saem do `carregar`."""
    return {"testes": entrada.get("testes"), "ledger": entrada.get("ledger"),
            "fotos": entrada.get("fotos"), "semana": entrada.get("semana"),
            "leituras": entrada.get("leituras_hora"),
            "horas_das_fotos": entrada.get("horas_das_fotos"),
            "erro_da_semana": entrada.get("erro_da_semana") or "",
            "contas_tiktok": entrada.get("contas_tiktok")}


def do_dia(log=print, agora: datetime | None = None, rede: bool = True,
           biblioteca: bool = True) -> dict:
    """O passo do servico do dia: serie do canal (rede), analise, pagina,
    Biblioteca. O que falhar vira UMA linha de erro `metricas` no diario."""
    agora = agora or datetime.now()
    falhas: list[str] = []
    if rede:
        for canal in metricas.CANAIS:
            try:
                serie = buscar_serie_do_canal(canal, hoje=agora.date())
                _gravar(pasta() / f"canal_{canal}.json",
                        json.dumps(serie, ensure_ascii=False))
            except Exception as exc:                          # noqa: BLE001
                falhas.append(f"série diária do canal {canal} não veio: "
                              f"{type(exc).__name__}: {str(exc)[:160]}")
    entrada = carregar(agora)
    entrada["falhas"].extend(falhas)
    regs = registros(entrada)
    cob = cobertura(entrada)
    analise = analisar(regs, cob, agora, entrada["series"], entrada["historico"],
                       entrada["falhas"], **_extras(entrada))
    analise["serie_bluelock"] = _bloco_da_serie(agora)
    caminho = gravar(analise, regs, agora, entrada["series"])
    if biblioteca:
        try:
            publicar_na_biblioteca(caminho)
        except Exception as exc:                              # noqa: BLE001
            entrada["falhas"].append(f"página não entrou na Biblioteca: "
                                     f"{type(exc).__name__}: {str(exc)[:160]}")
    log(f"[analise] {len(regs)} vídeos, {len(analise['achados'])} achado(s), estado "
        f"{analise['estado']} -> {caminho}")
    problemas = list(entrada["falhas"])
    if analise["estado"] in ("sem_dados", "velha"):
        problemas.insert(0, analise["avisos"][0])
    # A leitura de hora em hora parada e a medida da semana sem chao: vao ao
    # diario (e dali ao Telegram), nao so a pagina.
    problemas.extend((analise.get("mesma_idade") or {}).get("avisos") or [])
    if problemas:
        try:
            from .. import atividade
            atividade.registrar("metricas", atividade.ERRO,
                                "[analise] " + " | ".join(problemas)[:280])
        except Exception:                                     # noqa: BLE001
            pass
        log("[analise] avisos: " + " | ".join(problemas))
    return analise


# ----------------------------------------------------------------- pagina
CSS = """
:root{--fundo:#fcfcfb;--cartao:#ffffff;--tinta:#1d1d1b;--tinta2:#55554f;--linha:#e4e3df;
--barra:#2a78d6;--bom:#0a7d0a;--ruim:#c03030;--alerta:#a86400;}
@media (prefers-color-scheme:dark){:root{--fundo:#1a1a19;--cartao:#232321;--tinta:#f1f0ec;
--tinta2:#b5b4ae;--linha:#3a3a37;--barra:#3987e5;--bom:#3cc23c;--ruim:#ff6b6b;--alerta:#f0a530;}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--tinta);
font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:720px;margin:0 auto;padding:14px}
h1{font-size:22px;margin:4px 0}h2{font-size:18px;margin:26px 0 8px}h3{font-size:15px;margin:14px 0 6px}
.sub{color:var(--tinta2);font-size:13px}
.cartao{background:var(--cartao);border:1px solid var(--linha);border-radius:12px;padding:12px;margin:10px 0}
.faixa{border-radius:10px;padding:10px 12px;margin:10px 0;font-weight:600}
.faixa.ruim{background:rgba(208,59,59,.12);border:1px solid var(--ruim)}
.faixa.alerta{background:rgba(240,165,48,.12);border:1px solid var(--alerta)}
.faixa.ok{background:rgba(12,163,12,.10);border:1px solid var(--bom)}
.cartao.ruim{border-color:var(--ruim)}.cartao.alerta{border-color:var(--alerta)}
.cartao p{margin:5px 0}
.selo{display:inline-block;font-size:12px;font-weight:700;border-radius:999px;padding:1px 8px;
border:1px solid currentColor;margin-right:6px}
.erro{color:var(--ruim)}.acerto{color:var(--bom)}.atencao{color:var(--alerta)}
.conf{color:var(--tinta2);font-size:12px}
.achado p{margin:6px 0}.mudar{font-weight:700}
.numeros{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:8px 0}
.numero{border:1px solid var(--linha);border-radius:10px;padding:8px}
.numero b{display:block;font-size:20px}.numero span{color:var(--tinta2);font-size:12px}
main,p,h3,li,.faixa{overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;font-size:13px;table-layout:fixed}
th,td{text-align:left;padding:5px 4px;border-bottom:1px solid var(--linha);vertical-align:top;
overflow-wrap:anywhere}
th.n,td.n{width:4.8em}
th{color:var(--tinta2);font-weight:600}td.n{text-align:right}
.poucos{display:block;color:var(--tinta2);font-size:11px;line-height:1.2}
.coleta-dias{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0}
.coleta-dias span{border:1px solid var(--linha);border-radius:6px;padding:2px 5px;font-size:12px;
min-width:3.2em;text-align:center}
.coleta-dias .ruim{color:var(--ruim);border-color:var(--ruim)}
.coleta-dias .meio{color:var(--alerta);border-color:var(--alerta)}
.parte-coleta{border-top:1px solid var(--linha);padding:8px 0}.parte-coleta:first-child{border-top:0}
details{margin:8px 0}summary{cursor:pointer;color:var(--tinta2)}
svg .b{fill:var(--barra)}svg .b:hover{opacity:.75}svg text{fill:var(--tinta2);font-size:10px}
svg .eixo{stroke:var(--linha)}
ul{padding-left:18px}li{margin:4px 0}
.semana-plataforma h3{margin:2px 0 8px}
.cartao p.video{margin:6px 0 6px 6px;padding-left:8px;border-left:2px solid var(--linha)}
"""

TIPO = {"erro": ("✖", "Está errando"), "acerto": ("✔", "Está acertando"),
        "atencao": ("!", "Preste atenção")}
CONF = {"claro": "Certeza: clara (muitos vídeos, diferença grande)",
        "provavel": "Certeza: provável (vale testar)",
        "incerto": "Certeza: ainda não dá para dizer — vale testar"}
SENTIDO = {"subindo": "▲ subindo", "caindo": "▼ caindo", "estavel": "● estável",
           "parado": "■ parado (quase nenhuma view)", "sem_dados": "sem dados"}


def _e(texto) -> str:
    return html.escape(str(texto if texto is not None else ""))


def _data_br(texto: str) -> str:
    try:
        d = datetime.fromisoformat(str(texto)[:19])
    except ValueError:
        return str(texto or "nunca")
    return d.strftime("%d/%m %H:%M") if len(str(texto)) > 10 else d.strftime("%d/%m")


def _barras(pontos: list, titulo: str) -> str:
    """Barras de uma serie so (sem legenda: o titulo diz o que e)."""
    pontos = [(str(d), int(v or 0)) for d, v in pontos]
    if not pontos:
        return "<p class='sub'>Sem dados para o gráfico.</p>"
    largura, altura, base = 340, 110, 92
    maior = max(v for _d, v in pontos) or 1
    passo = largura / len(pontos)
    barras = []
    for i, (d, v) in enumerate(pontos):
        h = max(1.0, (v / maior) * (base - 8)) if v else 0.0
        x = i * passo + 1
        barras.append(f"<rect class='b' x='{x:.1f}' y='{base - h:.1f}' width='{max(passo - 2, 1):.1f}' "
                      f"height='{h:.1f}' rx='2'><title>{_e(_data_br(d))}: {_v(v)}</title></rect>")
    return (f"<figure style='margin:6px 0'><figcaption class='sub'>{_e(titulo)} — maior "
            f"dia: {_fmt(maior)}</figcaption>"
            f"<svg viewBox='0 0 {largura} {altura}' width='100%' role='img' aria-label='{_e(titulo)}'>"
            f"<line class='eixo' x1='0' x2='{largura}' y1='{base}' y2='{base}'/>"
            + "".join(barras) +
            f"<text x='0' y='{altura - 4}'>{_e(_data_br(pontos[0][0]))}</text>"
            f"<text x='{largura}' y='{altura - 4}' text-anchor='end'>{_e(_data_br(pontos[-1][0]))}</text>"
            f"</svg></figure>")


def _linha_video(r: dict) -> str:
    extra = []
    if r.get("arena"):
        extra.append(f"arena {r['arena']}")
    if r.get("parte"):
        extra.append(f"parte {r['parte']}/{r.get('partes') or '?'}")
    if r.get("estrutura"):
        extra.append(str(r["estrutura"]))
    o_que = " · ".join([NOME_DO_FORMATO.get(r["formato"], r["formato"]),
                        f"{_fmt(r.get('duracao_s'))} s",
                        f"{DIAS_DA_SEMANA[r['dia_semana']]} {r['hora']}h", *extra])
    return (f"<tr><td>{_e(r['titulo'][:70])}<br><span class='sub'>{_e(_data_br(r['quando']))} · "
            f"{_e(o_que)}</span></td><td class='n'>{_fmt(r['views'])}</td>"
            f"<td class='n'>{_pct(r['retencao'])}</td></tr>")


def _tabela_videos(lista: list) -> str:
    if not lista:
        return "<p class='sub'>Nenhum vídeo com 3+ dias nos últimos 28 dias.</p>"
    return ("<table><tr><th>vídeo</th><th class='n'>views</th><th class='n'>assistem</th></tr>"
            + "".join(_linha_video(r) for r in lista) + "</table>")


def _tabela_grupos(linhas: list, nome, rotulo: str) -> str:
    if not linhas:
        return ""
    # "poucos" em LINHA PROPRIA, menor: ao lado da porcentagem ela atravessava
    # a borda do cartao em 56 de 73 celulas (conferente, 19/10/2026).
    corpo = "".join(
        f"<tr><td>{_e(nome(x['grupo']))}</td><td class='n'>{x['n']}</td>"
        f"<td class='n'>{_fmt(x['views'])}</td><td class='n'>{_pct(x['retencao'])}"
        f"{'' if x['n_retencao'] >= MIN_N else '<br><span class=poucos>poucos</span>'}</td></tr>"
        for x in linhas)
    return (f"<table><tr><th>{_e(rotulo)}</th><th class='n'>vídeos</th><th class='n'>views"
            f"</th><th class='n'>assistem</th></tr>{corpo}</table>")


def _parte_html(p: dict) -> str:
    if not p["videos"]:
        return (f"<div class='cartao'><h3>{_e(p['rotulo'])}</h3><div class='faixa ruim'>"
                f"Sem nenhum vídeo medido. Isso não é zero views: é falta de dado.</div></div>")
    t = p["tendencia"]
    if t.get("fonte") == "canal":
        trend = (f"{SENTIDO[t['sentido']]}: {_v(t['ultimos_7'])} no canal nos 7 dias "
                 f"até {_data_br(t['ate'])}, contra {_fmt(t['anteriores_7'])} nos 7 anteriores")
    elif t.get("mediana_recente") is not None and t.get("mediana_antes") is not None:
        trend = (f"{SENTIDO[t['sentido']]}: o vídeo do meio da fila fez {_v(t['mediana_recente'])} "
                 f"nas 2 últimas semanas, contra {_fmt(t['mediana_antes'])} nas 2 anteriores"
                 + (" (diferença dentro do acaso)" if t.get("confianca") == "incerto" else ""))
    else:
        trend = "sem dados suficientes para dizer se sobe ou cai"
    numeros = [
        (_fmt(p["mediana_views"]), "views do vídeo do meio da fila (28 dias)"),
        (_pct(p["mediana_retencao"]) if p["n_retencao"] >= MIN_N else "—",
         f"do vídeo que as pessoas assistem ({p['n_retencao']} vídeos com 20+ views)"),
        (_fmt(p["views_total"]), f"views somadas de {p['videos']} vídeos"),
    ]
    if p.get("inscritos") is not None:
        numeros.append((_fmt(p["inscritos"]), "inscritos no canal"))
    elif p.get("ganho_desde_ontem") is not None:
        numeros.append((_fmt(p["ganho_desde_ontem"]), "views ganhas desde ontem"))
    else:
        numeros.append(("—", "views ganhas desde ontem (sem fotografia de ontem)"))
    caixas = "".join(f"<div class='numero'><b>{_e(a)}</b><span>{_e(b)}</span></div>"
                     for a, b in numeros)
    if p.get("serie"):
        grafico = _barras([(d[0], d[1]) for d in p["serie"]][-JANELA_DIAS:],
                          "Views por dia no canal inteiro (YouTube Analytics)")
    else:
        grafico = _barras(p["views_por_dia_de_postagem"],
                          "Views somadas dos vídeos postados em cada dia (não é views por dia)")
    ext = p["extremos"]
    formatos = ""
    if len(p["formatos"]) > 1:
        formatos = ("<h3>Qual tipo de vídeo rende mais</h3>"
                    + _tabela_grupos(p["formatos"], lambda g: NOME_DO_FORMATO.get(g, g), "formato"))
    return (f"<div class='cartao'><h3>{_e(p['rotulo'])}</h3><p>{_e(trend)}.</p>"
            f"<div class='numeros'>{caixas}</div>{grafico}{formatos}"
            f"<h3>Os 5 melhores</h3>{_tabela_videos(ext['melhores'])}"
            f"<h3>Os 5 piores</h3>{_tabela_videos(ext['piores'])}"
            + (f"<p class='sub'>{_e(ext['em_comum'])}</p>" if ext.get("em_comum") else "")
            + (f"<details><summary>Por {_e(p['nome_do_tipo'])}</summary>"
               + _tabela_grupos(p["por_tipo"], str, p["nome_do_tipo"]) + "</details>"
               if p.get("por_tipo") else "")
            + "<details><summary>Por horário e dia da semana</summary>"
            + _tabela_grupos(p["horas"], lambda g: f"{g}h", "horário")
            + _tabela_grupos(p["dias_da_semana"], lambda g: DIAS_DA_SEMANA[g], "dia")
            + "</details></div>")


def _achado_html(i: int, a: dict) -> str:
    icone, nome = TIPO.get(a["tipo"], ("•", ""))
    return (f"<div class='cartao achado'><div><span class='selo {a['tipo']}'>{icone} {nome}</span>"
            f"<span class='conf'>{_e(CONF.get(a['confianca'], ''))}</span></div>"
            f"<h3>{i}. {_e(a['titulo'])}</h3><p>{_e(a['vimos'])}</p>"
            f"<p class='mudar'>O que mudar: {_e(a['mudar'])}</p>"
            f"<p class='sub'>Quanto deve mexer: {_e(a['quanto'])}</p></div>")


ESTADO_DO_TESTE = {"nao_comecou": "ainda não começou", "em_andamento": "em andamento",
                   "terminado": "terminou", "sem_teste": "sem datas no config"}
VEREDITO = {"efeito": ("ok", "deu efeito"),
            "sem_efeito": ("ruim", "sem efeito claro"),
            "juntando": ("alerta", "ainda juntando (dia com vídeo de menos de 3 dias não conta)"),
            "sem_dados": ("ruim", "sem dados: nenhum vídeo medido nos dois lados")}


def frases_dos_testes(testes: dict) -> list:
    """Os testes em frases curtas (a pagina e o `--ver` usam as mesmas)."""
    linhas = []
    t = (testes or {}).get(TESTE_DO_TIKTOK) or {}
    if t.get("estado") and t["estado"] != "sem_teste":
        linhas.append(f"TikTok com {t.get('posts_no_teste')} por dia, de "
                      f"{_data_br(t['inicio'])} a {_data_br(t['fim'])} "
                      f"({ESTADO_DO_TESTE.get(t['estado'], t['estado'])}); antes = "
                      f"{_data_br(t['antes_de'])} em diante.")
        for canal, p in (t.get("perfis") or {}).items():
            a, b = p["antes"], p["durante"]
            texto = (f"  {NOME_DO_CANAL.get(canal, canal)}: views por dia (somando os vídeos "
                     f"postados no dia) {_fmt(a['views_por_dia'])} antes x "
                     f"{_fmt(b['views_por_dia'])} durante; por post {_fmt(a['por_post'])} x "
                     f"{_fmt(b['por_post'])}; posts por dia {_fmt(a['posts_por_dia'])} x "
                     f"{_fmt(b['posts_por_dia'])}; dias contados {a['dias_maduros']} x "
                     f"{b['dias_maduros']} — {VEREDITO.get(p['veredito'], ('', p['veredito']))[1]}")
            if p.get("p") is not None:
                texto += f" (p = {_fmt(p['p'])})"
            if p.get("medida"):
                texto += f"; medida: {p['medida']}"
            if p.get("dias_fora_do_regime"):
                texto += (f"; dias com mais de {t.get('posts_no_teste')} posts: "
                          + ", ".join(_data_br(d) for d in p["dias_fora_do_regime"]))
            if p.get("proximo_teste"):
                texto += f". Próximo teste recomendado: {p['proximo_teste']}"
            linhas.append(texto + ".")
    s = (testes or {}).get(TESTE_DA_PARTE_SEGUINTE) or {}
    if s.get("estado") and s["estado"] != "sem_teste":
        linhas.append(f"Parte seguinte ligada (YouTube, histórias), de {_data_br(s['inicio'])} "
                      f"a {_data_br(s['fim'])} ({ESTADO_DO_TESTE.get(s['estado'], s['estado'])}): "
                      f"a seguinte teve {_fmt(s['por_100_antes'])} views a cada 100 da anterior "
                      f"antes ({s['pares_antes']} pares) x {_fmt(s['por_100_durante'])} durante "
                      f"({s['pares_durante']} pares).")
    return linhas


def _testes_html(testes: dict) -> str:
    linhas = frases_dos_testes(testes)
    if not linhas:
        return ""
    return ("<h2>Testes</h2><div class='cartao'>"
            + "".join(f"<p>{_e(x.strip())}</p>" for x in linhas) + "</div>")


def _cobertura_html(cob: dict) -> str:
    """Em FRASES, uma parte por bloco (a tabela de 6 colunas nao cabia em
    390 px e falava "sem par no Studio", "sem status")."""
    blocos = []
    for p in cob.get("partes", {}).values():
        falta = []
        if p.get("depois_da_coleta"):
            n = p["depois_da_coleta"]
            falta.append(f"{_qtd(n, 'postado', 'postados')} depois da coleta "
                         f"({'entra' if n == 1 else 'entram'} na próxima)")
        if p.get("sem_id"):
            falta.append(f"{p['sem_id']} sem o código do vídeo no registro (não dá para medir)")
        if p.get("sem_arquivo"):
            falta.append(f"{_qtd(p['sem_arquivo'], 'postado', 'postados')} antes da coleta e "
                         f"sem número")
        if p.get("parados"):
            datas = ", ".join(_data_br(d) for d in p.get("parados_desde") or [])
            falta.append(f"{p['parados']} que o {NOME_DA_PLATAFORMA[p['plataforma']]} não mostra "
                         f"mais (número parado em {datas})")
        if p.get("privados"):
            falta.append(f"{_qtd(p['privados'], 'privado (rascunho', 'privados (rascunhos')}: "
                         f"ninguém vê)")
        if p.get("sem_status"):
            falta.append(f"{p['sem_status']} sem a informação de público ou privado (ficam fora "
                         f"das comparações)")
        repetidas = (f" (o registro tem {p['linhas_no_ledger']} linhas: "
                     f"{p['linhas_repetidas']} repetidas)" if p.get("linhas_repetidas") else "")
        coleta = {"ok": "✔ deu certo", "vazio": "✖ veio vazia", "erro": "✖ falhou",
                  "nunca": "✖ nunca rodou"}.get(p["coleta"], p["coleta"])
        quando = f" ({_data_br(p['ultimo_ok'])})" if p.get("ultimo_ok") else ""
        # As duas contas falam dos MESMOS videos: "em N deles" e subconjunto
        # dos que tem numero desta coleta; o parado e dito a parte.
        hoje = p["medidos_hoje"]
        retencao = p.get("com_retencao_hoje", p["com_retencao"])
        n_parados = p.get("parados") or 0
        parados = ((f" Outro vídeo tem só o número antigo: o "
                    f"{NOME_DA_PLATAFORMA[p['plataforma']]} parou de mostrá-lo."
                    if n_parados == 1 else
                    f" Outros {n_parados} têm só o número antigo: o "
                    f"{NOME_DA_PLATAFORMA[p['plataforma']]} parou de mostrá-los.")
                   if n_parados else "")
        blocos.append(
            f"<div class='parte-coleta'><b>{_e(p['rotulo'])}</b><br>"
            f"{p.get('videos_postados', p['linhas_no_ledger'])} vídeos postados desde "
            f"{_e(_data_br(p['desde']))}{_e(repetidas)}. "
            f"{_qtd(hoje, 'vídeo tem', 'vídeos têm')} número desta coleta; em {retencao} "
            f"{'dele' if hoje == 1 else 'deles'} dá para saber quanto as pessoas "
            f"assistem.{_e(parados)}<br>"
            f"Última coleta boa: {_e(coleta)}{_e(quando)}.<br>"
            f"<span class='sub'>Falta: {_e('; '.join(falta) or 'nada')}.</span></div>")
    simbolo = {"completa": ("✔", ""), "parcial": ("◐", "meio"), "falhou": ("✖", "ruim"),
               "nao_rodou": ("○", "ruim"), "nao_medido": ("?", "")}
    dias = cob.get("dias_de_coleta") or []
    fila = "".join(f"<span class='{simbolo.get(d['estado'], ('?', ''))[1]}' "
                   f"title='{_e(d['estado'])}'>{_e(d['dia'][8:10])}/{_e(d['dia'][5:7])}<br>"
                   f"{simbolo.get(d['estado'], ('?', ''))[0]}</span>" for d in dias)
    ruins = [d for d in dias if d["estado"] in ("falhou", "nao_rodou", "parcial")]
    resumo = ""
    if dias:
        resumo = ("<p class='sub'>✔ completa · ◐ só uma parte · ✖ falhou · ○ não rodou · ? sem "
                  "registro (antes de 01/10 a coleta não escrevia o resumo do dia). "
                  + (f"Nos últimos {len(dias)} dias: {sum(1 for d in dias if d['estado'] == 'completa')} "
                     f"completos, {len(ruins)} com problema"
                     + (" (" + ", ".join(f"{_data_br(d['dia'])}" for d in ruins) + ")" if ruins else "")
                     + ". Um dia sem coleta não apaga número: o total de cada vídeo vem completo "
                       "na coleta seguinte.") + "</p>")
    return ((f"<h3>Dia a dia</h3><div class='coleta-dias'>{fila}</div>{resumo}" if dias else "")
            + "<h3>Hoje, parte por parte</h3>" + "".join(blocos))


def _semana_html(c: dict) -> str:
    """A medida da semana: o mesmo texto do Telegram, uma linha por paragrafo
    (cabe em 390 px; numero com rotulo, nunca so a seta)."""
    if not c.get("texto"):
        return ""
    from . import mesma_idade

    classe = {"ok": "", "sem_semana": "alerta", "sem_novos": "ruim",
              "sem_antigos": "ruim", "erro": "ruim"}.get(c.get("estado"), "alerta")
    try:
        partes = mesma_idade.linhas(c)
    except (KeyError, TypeError, ValueError):
        # json de outra versao: o texto pronto, linha por linha (sem perder o
        # recuo, que e o que separa o video da idade).
        partes = [("sub" if l.startswith("    ") else "idade" if l.startswith("  ") else "item",
                   l.strip()) for l in c["texto"].splitlines()]
    # Cabeca (titulo, avisos, leituras) num cartao; cada PLATAFORMA no seu,
    # com titulo proprio — no celular, sem recuo, YouTube e TikTok viravam
    # uma lista so (conferente, 21/10).
    cabeca, plataformas = [], []
    for tipo, t in partes:
        if tipo == "plataforma":
            plataformas.append((t, []))
        elif plataformas and tipo in ("idade", "item", "video"):
            plataformas[-1][1].append((tipo, t))
        else:
            cabeca.append((tipo, t))
    estilo = {"titulo": "<p><b>{}</b></p>", "aviso": "<p class='erro'><b>{}</b></p>",
              "video": "<p class='sub video'>{}</p>", "sub": "<p class='sub'>{}</p>",
              "detalhe": "<p class='sub'>{}</p>"}
    html_ = "".join(estilo.get(tipo, "<p>{}</p>").format(_e(t)) for tipo, t in cabeca)
    if c.get("criterio"):
        html_ += f"<p class='sub'>{_e(c['criterio'])}</p>"
    blocos = ""
    for titulo, itens in plataformas:
        blocos += (f"<div class='cartao semana-plataforma'><h3>{_e(titulo)}</h3>"
                   + "".join(estilo.get(tipo, "<p>{}</p>").format(_e(t)) for tipo, t in itens)
                   + "</div>")
    return (f"<h2>Medida da semana (mesma idade)</h2>"
            f"<div class='cartao {classe}'>{html_}</div>{blocos}")


def _conta_html(conta: dict) -> str:
    perfis = conta.get("perfis") or {}
    if not perfis:
        return ""
    blocos = []
    for canal, p in perfis.items():
        vv = p.get("vv_history")
        if not isinstance(vv, list):
            serie = "série não lida"
        elif p.get("serie_datas") == "sem" or (p.get("serie_datas") is None and any(
                not (isinstance(x, list) and x and x[0]) for x in vv)):
            serie = f"série sem datas ({len(vv)} pontos; não sei de que dias)"
        else:
            datas = [x[0] for x in vv if isinstance(x, list) and x and x[0]]
            serie = (f"série de {len(vv)} dia(s)"
                     + (f", {_data_br(min(datas))} a {_data_br(max(datas))}" if datas else "")
                     + (" (datas deduzidas do pedido)" if p.get("serie_datas") == "deduzidas"
                        else ""))
        blocos.append(
            f"<p><b>{_e(NOME_DO_CANAL.get(canal, canal))}</b> — "
            + (f"ficha de {_e(_data_br(p['dia']))}: " if p.get("dia") else "nunca lida: ")
            + _e(f"seguidores {p['seguidores'] if p.get('seguidores') is not None else 'não medidos'}; "
                 f"{serie}; punição {'lida' if p.get('punicao_lida') else 'NÃO lida'}"
                 + (f" ({p['punicao_por_que']})" if p.get("punicao_por_que")
                    and not p.get("punicao_lida") else "") + "; "
                 f"qualidade {'lida' if p.get('qualidade_lida') else 'NÃO lida'}; "
                 f"situação em {p.get('com_situacao', 0)} de {p.get('posts_recentes', 0)} posts "
                 f"recentes ({p.get('em_revisao', 0)} em revisão)")
            + "</p>")
    return "<h2>Conta do TikTok</h2><div class='cartao'>" + "".join(blocos) + "</div>"


def _bloco_da_serie(agora: datetime) -> dict:
    """A serie "Como eu criei um Blue Lock" (26/10/2026): as mesmas linhas do
    relatorio do Telegram e o resumo dos comentarios (sem marcar nada como
    avisado). Nunca levanta; falha vira `erro`, que a pagina mostra."""
    try:
        from . import serie_comentarios, serie_metricas
        return {"linhas": serie_metricas.linhas_do_relatorio(agora),
                "comentarios": serie_comentarios.resumo(agora, marcar=False)}
    except Exception as exc:                                   # noqa: BLE001
        return {"erro": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _serie_html(bloco: dict) -> str:
    if not bloco:
        return ""
    if bloco.get("erro"):
        return ("<h2>Série Blue Lock</h2><div class='cartao ruim'><p>NÃO consegui "
                f"montar a série: {_e(bloco['erro'])}</p></div>")
    linhas = "".join(f"<p>{_e(l.strip().replace('*', ''))}</p>"
                     for l in bloco.get("linhas") or [])
    comentarios = "".join(f"<p>{_e(l.replace('*', ''))}</p>"
                          for l in str(bloco.get("comentarios") or "").splitlines())
    return ("<h2>Série Blue Lock</h2><div class='cartao'>" + linhas
            + "<p class='sub'>Cada plataforma por si, nunca somadas. “24 h: ainda não” "
              "quer dizer que não houve leitura perto das 24 h — não é zero. O YouTube "
              "só entrega o % assistido uns 2–3 dias depois do episódio.</p></div>"
            "<div class='cartao'>" + comentarios + "</div>")


def pagina(analise: dict) -> str:
    estado = analise.get("estado")
    faixa = {"sem_dados": ("ruim", "Sem dados: a coleta não trouxe nenhum vídeo. Nada aqui "
                                   "quer dizer que está tudo bem."),
             "velha": ("ruim", "Atenção: a coleta está parada — números velhos."),
             "incompleta": ("alerta", "A coleta de hoje falhou em parte."),
             "ok": ("ok", "Coleta de hoje completa nas 4 partes.")}
    classe, texto = faixa.get(estado, ("ruim", "Estado desconhecido."))
    avisos = "".join(f"<li>{_e(a)}</li>" for a in analise.get("avisos", []))
    achados = analise.get("achados", [])
    corpo_achados = ("".join(_achado_html(i + 1, a) for i, a in enumerate(achados))
                     if achados else
                     "<div class='faixa alerta'>Nenhum achado firme: com os dados de agora, "
                     "nenhuma diferença passa do acaso. Isso não quer dizer que está tudo bem.</div>")
    partes = analise.get("partes", {})
    secoes = []
    for canal in metricas.CANAIS:
        par = partes.get(f"{canal}_par") or {}
        comparacao = ""
        if par.get("pares"):
            comparacao = (f"<p class='sub'>O mesmo vídeo nos dois lugares ({par['pares']} vídeos postados nos dois, "
                          f"28 dias): o vídeo do meio da fila fez {_v(par['youtube'])} no YouTube e "
                          f"{_fmt(par['tiktok'])} no TikTok.</p>")
        secoes.append(f"<h2>{_e(NOME_DO_CANAL.get(canal, canal))}</h2>{comparacao}"
                      + "".join(_parte_html(partes[nome_da_parte(canal, p)])
                                for p in PLATAFORMAS if nome_da_parte(canal, p) in partes))
    nao_da = "".join(f"<li>{_e(x)}</li>" for x in analise.get("nao_da", []))
    regras = analise.get("regras", {})
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{_e(TITULO_DA_PAGINA)}</title><style>{CSS}</style></head><body><main>
<h1>{_e(TITULO_DA_PAGINA)}</h1>
<div class="sub">Feita em {_e(_data_br(analise.get('gerado_em', '')))} · coleta mais velha:
{_e(_data_br(analise.get('cobertura', {}).get('coleta_mais_velha') or 'nunca'))}</div>
<div class="faixa {classe}">{_e(texto)}</div>
{f'<ul>{avisos}</ul>' if avisos else ''}
<h2>O que mudar, do mais importante para o menos</h2>
{corpo_achados}
{_testes_html(analise.get('testes') or {})}
{_semana_html(analise.get('mesma_idade') or {})}
{_conta_html(analise.get('conta_tiktok') or {})}
{_serie_html(analise.get('serie_bluelock') or {})}
{''.join(secoes)}
<h2>Ainda não dá para dizer</h2>
{f'<ul>{nao_da}</ul>' if nao_da else '<p class="sub">Nada pendente.</p>'}
<h2>Como a coleta está</h2>
<div class="cartao">{_cobertura_html(analise.get('cobertura', {}))}</div>
<p class="sub">Como se lê: "views" é a mediana por vídeo (o vídeo do meio da fila), nunca a
média — um vídeo que bomba não esconde os outros. Só entram vídeos com {regras.get('maduro_dias')}
dias ou mais no ar, dos últimos {regras.get('janela_dias')} dias. "Assistem" é quanto do vídeo as pessoas
assistem, em média, e só conta vídeo com {regras.get('min_views_retencao')} views ou mais.
Cada diferença passa por um teste: "clara" e "provável" passaram; o resto está em "ainda não dá
para dizer". "Assistem" acima de 100% quer dizer que muita gente assistiu mais de uma vez.
Nas tabelas, "views" é sempre a mediana. O TikTok não informa inscritos por aqui.</p>
</main></body></html>
"""


# ------------------------------------------------------------------- cli
def _texto(analise: dict) -> str:
    linhas = [f"Análise dos vídeos — {analise['gerado_em']} — estado {analise['estado']}"]
    linhas += [f"  ! {a}" for a in analise["avisos"]]
    for i, a in enumerate(analise["achados"], 1):
        linhas += [f"{i}. [{a['tipo']}/{a['confianca']}] {a['titulo']}",
                   f"   {a['vimos']}", f"   MUDAR: {a['mudar']}", f"   QUANTO: {a['quanto']}"]
    testes = frases_dos_testes(analise.get("testes") or {})
    if testes:
        linhas += ["Testes:"] + [f"  {x}" for x in testes]
    semana = (analise.get("mesma_idade") or {}).get("texto")
    if semana:
        linhas += [""] + semana.splitlines()
    linhas += ["Ainda não dá para dizer:"] + [f"  - {x}" for x in analise["nao_da"]]
    return "\n".join(linhas)


def medida_da_semana(agora: datetime | None = None) -> dict:
    """A comparacao na mesma idade feita AGORA, so com o disco (a coleta do
    dia + as leituras de hora em hora ate este minuto). E o que o relatorio
    do Telegram e o `--semana` mostram; a pagina usa a da manha."""
    from . import mesma_idade

    agora = agora or datetime.now()
    entrada = carregar(agora)
    regs = registros(entrada, meta=None)
    c = mesma_idade.comparar(regs, agora, entrada.get("semana"), fotos=entrada.get("fotos"),
                             leituras=entrada.get("leituras_hora"),
                             horas_das_fotos=entrada.get("horas_das_fotos"),
                             series=entrada.get("series"),
                             erro_do_config=entrada.get("erro_da_semana") or "")
    if entrada["falhas"]:
        # A falha de leitura do disco vai para os AVISOS, que o texto poe no
        # topo (no fim, era a primeira coisa que o corte do Telegram comia).
        c["falhas"] = list(entrada["falhas"])
        if c.get("estado") != "sem_semana":
            c["avisos"] = list(c["falhas"]) + list(c.get("avisos") or [])
            c["texto"] = mesma_idade.texto(c)
        else:
            c["texto"] += "\n" + "\n".join(f"! {f}" for f in entrada["falhas"])
    c["texto_curto"] = (mesma_idade.texto(c, por_video=False)
                        if c.get("estado") != "sem_semana" else c["texto"])
    return c


def texto_da_semana(agora: datetime | None = None, *, por_video: bool = False) -> str:
    """O texto da medida da semana, feito agora. Nunca levanta.

    Padrao = o do TELEGRAM (`por_video=False`): avisos no topo e sem a linha
    de cada video — a semana cheia (21 duelos no YouTube + 7 no TikTok) dava
    8.398 caracteres e o envio corta em 4.000. O detalhe esta na pagina e no
    `--semana`."""
    try:
        c = medida_da_semana(agora)
        return c["texto"] if por_video else c["texto_curto"]
    except Exception as exc:                                  # noqa: BLE001
        return (f"Medida da semana FALHOU: {type(exc).__name__}: {exc}. "
                "Sem ela não há comparação — não quer dizer que está tudo bem.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ver", action="store_true", help="só mostra; não grava nada")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--rede", action="store_true",
                        help="busca a série diária do canal (Analytics)")
    parser.add_argument("--biblioteca", action="store_true",
                        help="põe a página na Biblioteca do app")
    parser.add_argument("--semana", action="store_true",
                        help="só a medida da semana na mesma idade, feita agora (só lê)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    agora = datetime.now()
    if args.semana:
        c = medida_da_semana(agora)
        print(json.dumps(c, ensure_ascii=False, indent=1, default=str)
              if args.json else c["texto"])
        return 0 if c.get("estado") == "ok" else 1
    if args.ver:
        entrada = carregar(agora)
        regs = registros(entrada)
        analise = analisar(regs, cobertura(entrada), agora, entrada["series"],
                           entrada["historico"], entrada["falhas"], **_extras(entrada))
    else:
        analise = do_dia(agora=agora, rede=args.rede, biblioteca=args.biblioteca)
    print(json.dumps(analise, ensure_ascii=False, indent=1, default=str)
          if args.json else _texto(analise))
    return 1 if analise["estado"] in ("sem_dados", "velha") else 0


if __name__ == "__main__":
    raise SystemExit(main())
