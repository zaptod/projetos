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
# Pausa que "zera" a conta do TikTok. Medido em 19/10/2026 nos dois perfis:
# depois de 10 h ou mais sem postar, os posts 1 a 6 tem mediana de 86-111
# views; do 7o em diante, 1-2. Com pausa de 6,5 h (a da grade de 10 por dia,
# 00:37 -> 06:37) a separacao some.
PAUSA_TIKTOK_H = 10.0
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
        "quando": quando.isoformat(timespec="minutes"),
        "hora": quando.hour, "dia_semana": quando.weekday(),
        "idade_dias": round((agora - quando).total_seconds() / 86400.0, 2),
        "duracao_s": _numero(d.get("duracao")),
        "views": views, "likes": int(d.get("likes") or 0),
        "comentarios": int(d.get("comentarios") or 0),
        "compartilhamentos": int(d.get("compartilhamentos") or 0),
        "retencao": round(retencao, 1) if retencao is not None else None,
        "segundos_vistos": _numero(d.get("media_segundos")),
        "publico": publico,
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
    return entrada


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
            "marca_completa": bool((entrada.get("marca") or {}).get("completa"))}


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


def achado_pausa_tiktok(regs: list, agora: datetime, canal: str) -> tuple:
    """O TikTok so entrega os primeiros posts depois de uma pausa longa."""
    tk = sorted((r for r in regs if r["plataforma"] == "tiktok"),
                key=lambda r: r["quando"])
    if len(tk) < 2 * MIN_N:
        return None, "TikTok: poucos posts para medir o efeito da pausa"
    posicao = []
    anterior = None
    k = 0
    for r in tk:
        quando = datetime.fromisoformat(r["quando"])
        if anterior is None or (quando - anterior).total_seconds() / 3600.0 >= PAUSA_TIKTOK_H:
            k = 1
        else:
            k += 1
        anterior = quando
        if r["idade_dias"] >= MADURO_DIAS:
            posicao.append((k, r["views"]))
    por_pos = defaultdict(list)
    for k, v in posicao:
        por_pos[k].append(v)
    primeiros = por_pos.get(1, []) + por_pos.get(2, []) + por_pos.get(3, [])
    ref = mediana(primeiros)
    if not ref or len(primeiros) < MIN_N:
        return None, (f"TikTok de {canal}: só {len(primeiros)} post(s) logo depois de "
                      f"uma pausa de {round(PAUSA_TIKTOK_H)} h — pouco para medir")
    corte = 0
    for k in range(1, 15):
        m = mediana(por_pos.get(k, []))
        if m is None or len(por_pos.get(k, [])) < 3 or m < 0.2 * ref:
            break
        corte = k
    if corte < 1:
        return None, None
    bons = [v for k, v in posicao if k <= corte]
    resto = [v for k, v in posicao if k > corte]
    conf = confianca(bons, resto)
    mb, mr = mediana(bons), mediana(resto)
    if conf == "incerto" or not mb or (mr or 0) * 5 > mb:
        return None, (f"TikTok de {canal}: posts logo depois de uma pausa "
                      f"({_fmt(mb)}) e os seguintes ({_fmt(mr)}) — diferença não "
                      f"se sustenta com a amostra")
    janela = _na_janela(tk, agora)
    por_dia = _views_do_dia(janela)
    hoje_por_dia = mediana(por_dia.values()) or 0
    posts_por_dia = len(janela) / _dias_efetivos(janela) if janela else 0
    previsto = corte * mb
    parte = nome_da_parte(canal, "tiktok")
    try:
        sugeridos = horarios_sugeridos(corte)
    except Exception:                                         # noqa: BLE001
        sugeridos = []
    exemplo = (f"nos horários {', '.join(sugeridos)}" if sugeridos else
               "todos dentro de uma janela de 14 horas")
    return _achado(
        f"pausa-tiktok:{canal}", parte, "erro",
        f"TikTok de {NOME_DO_CANAL[canal].split(' (')[0].lower()}: postar demais está apagando o perfil",
        (f"Depois de {round(PAUSA_TIKTOK_H)} horas ou mais sem postar, os {corte} primeiros "
         f"posts têm mediana de {_fmt(mb)} views ({len(bons)} posts medidos). Do "
         f"{corte + 1}º em diante, {_fmt(mr)} ({len(resto)} posts). Hoje sai uma média de "
         f"{_fmt(posts_por_dia)} posts por dia sem nenhuma pausa longa, e o perfil faz "
         f"cerca de {_fmt(hoje_por_dia)} views por dia."),
        (f"Poste no máximo {corte} vídeos por dia no TikTok, {exemplo}, deixando "
         f"{round(PAUSA_TIKTOK_H)} horas ou mais sem postar de uma noite para o dia "
         f"seguinte."),
        (f"Se o padrão se repetir: de ~{_fmt(hoje_por_dia)} para ~{_fmt(previsto)} views "
         f"por dia neste perfil ({corte} × {_fmt(mb)})."),
        conf, max(previsto - hoje_por_dia, 0),
        corte=corte, mediana_primeiros=mb, mediana_resto=mr, n_primeiros=len(bons),
        n_resto=len(resto), views_por_dia_hoje=hoje_por_dia,
        posts_por_dia=round(posts_por_dia, 1), horarios=sugeridos), None


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
        return None, (f"{rotulo}: {NOME_DO_FORMATO.get(melhor, melhor)} ({_fmt(mm)} views) × "
                      f"{NOME_DO_FORMATO.get(pior, pior)} ({_fmt(mp)}) — diferença dentro do acaso")
    def ret(f):
        return mediana(r["retencao"] for r in grupos[f])
    linhas = []
    for f in reversed(ordem):
        linhas.append(f"{NOME_DO_FORMATO.get(f, f)}: {_fmt(mediana(r['views'] for r in grupos[f]))} "
                      f"views e as pessoas veem {_pct(ret(f))} do vídeo ({len(grupos[f])} vídeos)")
    por_dia_pior = len(grupos[pior]) / _dias_efetivos(janela)
    ganho = por_dia_pior * (mm - mp)
    return _achado(
        f"formato:{canal}:{plataforma}", nome_da_parte(canal, plataforma),
        "acerto",
        f"{rotulo}: {o_(melhor)} é o que funciona; {o_(pior)} é o que menos rende",
        f"Mediana por vídeo nos últimos {JANELA_DIAS} dias — " + "; ".join(linhas) + ".",
        (f"Troque os vídeos de {NOME_DO_FORMATO.get(pior, pior)} por "
         f"{NOME_DO_FORMATO.get(melhor, melhor)} (hoje sai {_fmt(por_dia_pior)} "
         f"{NOME_DO_FORMATO.get(pior, pior)} por dia)."),
        f"Cerca de +{_fmt(ganho)} views por dia neste canal.",
        conf, ganho, melhor=melhor, pior=pior, mediana_melhor=mm, mediana_pior=mp,
        n_melhor=len(vm), n_pior=len(vp)), None


def achado_concentracao(regs: list, agora: datetime, canal: str, plataforma: str) -> tuple:
    """Um video so leva quase todas as views do dia?"""
    janela = _na_janela([r for r in regs if r["canal"] == canal
                         and r["plataforma"] == plataforma], agora)
    dias = defaultdict(list)
    for r in janela:
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
    hora, vezes = horas.most_common(1)[0]
    da_hora = [r["views"] for r in janela if r["hora"] == hora]
    outras = [r["views"] for r in janela if r["hora"] != hora]
    conf = confianca(da_hora, outras)
    posts_por_dia = len(janela) / _dias_efetivos(janela)
    rotulo = rotulo_da_parte(canal, plataforma)
    # A vitrine ficou VAZIA? Dia sem video naquele horario e o dia que o
    # canal perde. Ultimos 7 dias completos (hoje ainda nao acabou).
    postados = {r["quando"][:10] for r in regs if r["canal"] == canal
                and r["plataforma"] == plataforma and r["hora"] == hora
                and r.get("publico") is True}
    semana = [(agora.date() - timedelta(days=i)).isoformat() for i in range(1, 8)]
    vazios = [d for d in semana if d not in postados]
    falta = ""
    if len(vazios) >= 2:
        falta = (f" Nos últimos 7 dias, o horário das {hora}h ficou vazio em "
                 f"{len(vazios)} ({', '.join(_data_br(d) for d in sorted(vazios))}).")
    return _achado(
        f"concentracao:{canal}:{plataforma}", nome_da_parte(canal, plataforma),
        "atencao",
        f"{rotulo}: o dia é decidido por um vídeo só, quase sempre o das {hora}h",
        (f"Em {len(fatias)} dias medidos, o vídeo mais visto levou {_pct(fatia * 100)} das "
         f"views do dia (mediana). Em {vezes} desses dias foi o das {hora}h: mediana de "
         f"{_fmt(mediana(da_hora))} views, contra {_fmt(mediana(outras))} dos outros horários. "
         f"Os outros ~{_fmt(posts_por_dia - 1)} vídeos do dia somam ~{_fmt(mediana(resto))} "
         f"views." + falta),
        ((f"Nunca deixe o horário das {hora}h vazio. " if falta else "")
         + f"Trate o vídeo das {hora}h como a vitrine do dia: é ali que entra o melhor "
           f"vídeo pronto. Os outros horários rendem pouco; dá para postar menos neles "
           f"e guardar estoque."),
        (f"Postar menos nos outros horários mexe pouco nas views (~{_fmt(mediana(resto))} "
         f"por dia) e economiza vídeo. O ganho de verdade está em o vídeo das {hora}h ser bom."),
        conf, (mediana(da_hora) or 0) * 0.2, hora=hora, dias=len(fatias), vezes=vezes,
        fatia_mediana=round(fatia, 3), mediana_hora=mediana(da_hora),
        mediana_outras=mediana(outras), resto_por_dia=mediana(resto),
        dias_sem_a_vitrine=vazios), None


def achado_seguimento(regs: list, agora: datetime, canal: str, plataforma: str) -> tuple:
    """Quem ve uma parte que foi bem vai atras da parte seguinte?"""
    proprios = [r for r in regs if r["canal"] == canal and r["plataforma"] == plataforma
                and r.get("publico") is not False and r.get("parte")]
    por_serie = defaultdict(dict)
    for r in proprios:
        por_serie[r.get("fonte_id")].setdefault(int(r["parte"]), r)
    razoes = []
    for partes in por_serie.values():
        for n, r in partes.items():
            seguinte = partes.get(n + 1)
            if r["views"] >= 100 and seguinte and seguinte["idade_dias"] >= MADURO_DIAS:
                razoes.append(seguinte["views"] / r["views"])
    if len(razoes) < 5:
        return None, None
    razao = mediana(razoes)
    if razao is None or razao >= 0.25:
        return None, None
    rotulo = rotulo_da_parte(canal, plataforma)
    return _achado(
        f"seguimento:{canal}:{plataforma}", nome_da_parte(canal, plataforma), "erro",
        f"{rotulo}: quem vê uma parte não vai atrás da próxima",
        (f"Em {len(razoes)} partes que passaram de 100 views, a parte seguinte da mesma "
         f"história teve, na mediana, {_fmt(razao * 100)} views para cada 100 da anterior."),
        ("Ligue cada parte à seguinte dentro do próprio Shorts (o \"vídeo relacionado\" "
         "embaixo do vídeo) e termine a fala com \"a parte seguinte já está no canal\"."),
        (f"Não dá para estimar antes de testar. Meta de 2 semanas: passar de "
         f"{_fmt(razao * 100)} para 10 em cada 100."),
        "claro" if len(razoes) >= 10 else "provavel", 40,
        razao_mediana=round(razao, 3), pares=len(razoes)), None


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
        prefixo = (f"fora o das {', '.join(f'{h}h' for h in fora)}, nenhum outro horário"
                   if fora else "nenhum horário")
        return None, f"{rotulo}: {prefixo} se destaca dos outros (diferenças dentro do acaso)"
    mh, mo = mediana(vs), mediana(outras)
    bom = (mh or 0) > (mo or 0)
    return _achado(
        f"horario:{canal}:{plataforma}:{hora}", nome_da_parte(canal, plataforma),
        "acerto" if bom else "atencao",
        f"{rotulo}: o horário das {hora}h {'rende mais' if bom else 'rende menos'} que os outros",
        (f"Vídeos das {hora}h: mediana de {_fmt(mh)} views ({len(vs)} vídeos); os outros "
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
            incertos.append(f"{rotulo}: duração {do_(formato)} (até {_fmt(corte)} s: {_fmt(mc)} "
                            f"views; mais longo: {_fmt(ml)}) — não muda as views de forma clara")
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
            (f"{nome.capitalize()} de até {_fmt(corte)} s: mediana de {_fmt(mc)} views "
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
             historico: dict | None = None, falhas: list | None = None) -> dict:
    """A analise inteira, sem disco e sem rede. `regs` vazio = `sem_dados`."""
    series = series or {}
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
            avisos.append(f"{p['rotulo']}: {p['linhas_no_ledger']} vídeos postados e "
                          f"NENHUM com número medido.")
        if p.get("sem_arquivo"):
            avisos.append(f"{p['rotulo']}: {p['sem_arquivo']} vídeos do ledger sem número.")
        if p.get("sem_par"):
            avisos.append(f"{p['rotulo']}: {p['sem_par']} envios que o Studio não lista "
                          f"(sem número).")
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
            ditas = {a["numeros"].get("hora") for a in achados[antes:]
                     if a["id"].startswith("concentracao")}
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
    # Do que mais mexe para o que menos: `peso` e o ganho estimado em views
    # por dia. Achado incerto nem chega aqui (vai para `nao_da`).
    achados.sort(key=lambda a: -a["peso"])
    return {"gerado_em": agora.isoformat(timespec="minutes"), "estado": estado,
            "avisos": avisos, "achados": achados, "nao_da": nao_da,
            "partes": partes, "cobertura": cob,
            "regras": {"janela_dias": JANELA_DIAS, "maduro_dias": MADURO_DIAS,
                       "min_views_retencao": MIN_VIEWS_RETENCAO, "min_n": MIN_N,
                       "pausa_tiktok_h": PAUSA_TIKTOK_H}}


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
                           f"{metricas.motivo_da_recusa(resposta)}")
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


def fotografia(regs: list, cob: dict) -> dict:
    """Views de cada video hoje, para amanha saber quanto o canal GANHOU.
    Os arquivos de metrica guardam so o total da vida do video."""
    saida: dict = {"estado_da_coleta": cob.get("estado"),
                   "coleta_mais_velha": cob.get("coleta_mais_velha")}
    for r in regs:
        nome = nome_da_parte(r["canal"], r["plataforma"])
        saida.setdefault(nome, {})[r["id"]] = [r["views"], r["likes"], r["retencao"]]
    return saida


def gravar(analise: dict, regs: list, agora: datetime) -> Path:
    destino = pasta()
    _gravar(destino / "analise.json", json.dumps(analise, ensure_ascii=False, indent=1,
                                                 default=str))
    _gravar(destino / "index.html", pagina(analise))
    _gravar(destino / "historico" / f"{agora.date().isoformat()}.json",
            json.dumps(fotografia(regs, analise["cobertura"]), ensure_ascii=False))
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
                       entrada["falhas"])
    caminho = gravar(analise, regs, agora)
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
th.n,td.n{width:4.6em}table.cob{font-size:12px}table.cob th.n,table.cob td.n{width:4.2em}table.cob th{font-size:11px}
th{color:var(--tinta2);font-weight:600}td.n{text-align:right;white-space:nowrap}
details{margin:8px 0}summary{cursor:pointer;color:var(--tinta2)}
svg .b{fill:var(--barra)}svg .b:hover{opacity:.75}svg text{fill:var(--tinta2);font-size:10px}
svg .eixo{stroke:var(--linha)}
ul{padding-left:18px}li{margin:4px 0}
"""

TIPO = {"erro": ("✖", "Está errando"), "acerto": ("✔", "Está acertando"),
        "atencao": ("!", "Preste atenção")}
CONF = {"claro": "Certeza: clara (muitos vídeos, diferença grande)",
        "provavel": "Certeza: provável (vale testar)",
        "incerto": "Certeza: ainda não dá para dizer"}
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
                      f"height='{h:.1f}' rx='2'><title>{_e(_data_br(d))}: {_fmt(v)} views</title></rect>")
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
    return ("<table><tr><th>vídeo</th><th class='n'>views</th><th class='n'>veem</th></tr>"
            + "".join(_linha_video(r) for r in lista) + "</table>")


def _tabela_grupos(linhas: list, nome, rotulo: str) -> str:
    if not linhas:
        return ""
    corpo = "".join(
        f"<tr><td>{_e(nome(x['grupo']))}</td><td class='n'>{x['n']}</td>"
        f"<td class='n'>{_fmt(x['views'])}</td><td class='n'>{_pct(x['retencao'])}"
        f"{'' if x['n_retencao'] >= MIN_N else ' <span class=sub>(poucos)</span>'}</td></tr>"
        for x in linhas)
    return (f"<table><tr><th>{_e(rotulo)}</th><th class='n'>vídeos</th><th class='n'>views"
            f"</th><th class='n'>veem</th></tr>{corpo}</table>")


def _parte_html(p: dict) -> str:
    if not p["videos"]:
        return (f"<div class='cartao'><h3>{_e(p['rotulo'])}</h3><div class='faixa ruim'>"
                f"Sem nenhum vídeo medido. Isso não é zero views: é falta de dado.</div></div>")
    t = p["tendencia"]
    if t.get("fonte") == "canal":
        trend = (f"{SENTIDO[t['sentido']]}: {_fmt(t['ultimos_7'])} views no canal nos 7 dias "
                 f"até {_data_br(t['ate'])}, contra {_fmt(t['anteriores_7'])} nos 7 anteriores")
    elif t.get("mediana_recente") is not None and t.get("mediana_antes") is not None:
        trend = (f"{SENTIDO[t['sentido']]}: mediana de {_fmt(t['mediana_recente'])} views por "
                 f"vídeo nas 2 últimas semanas, contra {_fmt(t['mediana_antes'])} nas 2 anteriores"
                 + (" (diferença dentro do acaso)" if t.get("confianca") == "incerto" else ""))
    else:
        trend = "sem dados suficientes para dizer se sobe ou cai"
    numeros = [
        (_fmt(p["mediana_views"]), "views por vídeo (mediana, 28 dias)"),
        (_pct(p["mediana_retencao"]) if p["n_retencao"] >= MIN_N else "—",
         f"do vídeo que as pessoas veem ({p['n_retencao']} vídeos com 20+ views)"),
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
        formatos = ("<h3>Formato × formato</h3>"
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


def _cobertura_html(cob: dict) -> str:
    linhas = []
    for p in cob.get("partes", {}).values():
        falta = []
        if p.get("sem_id"):
            falta.append(f"{p['sem_id']} sem id")
        if p.get("sem_arquivo"):
            falta.append(f"{p['sem_arquivo']} sem número")
        if p.get("sem_par"):
            falta.append(f"{p['sem_par']} sem par no Studio")
        if p.get("parados"):
            falta.append(f"{p['parados']} parados")
        if p.get("privados"):
            falta.append(f"{p['privados']} privados")
        if p.get("sem_status"):
            falta.append(f"{p['sem_status']} sem status")
        coleta = {"ok": "✔ ok", "vazio": "vazia", "erro": "✖ falhou",
                  "nunca": "✖ nunca"}.get(p["coleta"], p["coleta"])
        linhas.append(
            f"<tr><td>{_e(p['rotulo'])}<br><span class='sub'>desde {_e(_data_br(p['desde']))}"
            f"</span></td><td class='n'>{p['linhas_no_ledger']}</td><td class='n'>{p['medidos']}"
            f"</td><td class='n'>{p['com_retencao']}</td><td>{_e(coleta)}<br><span class='sub'>"
            f"{_e(_data_br(p['ultimo_ok']))}</span></td><td>{_e(', '.join(falta) or '—')}</td></tr>")
    return ("<table class='cob'><tr><th>parte</th><th class='n'>saíram</th><th class='n'>com nº</th>"
            "<th class='n'>com %</th><th>coleta</th><th>falta</th></tr>"
            + "".join(linhas) + "</table>")


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
            comparacao = (f"<p class='sub'>O mesmo vídeo nos dois lugares ({par['pares']} pares, "
                          f"28 dias): mediana de {_fmt(par['youtube'])} views no YouTube e "
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
{''.join(secoes)}
<h2>Ainda não dá para dizer</h2>
{f'<ul>{nao_da}</ul>' if nao_da else '<p class="sub">Nada pendente.</p>'}
<h2>Como a coleta está</h2>
<div class="cartao">{_cobertura_html(analise.get('cobertura', {}))}</div>
<p class="sub">Como se lê: "views" é a mediana por vídeo (o vídeo do meio da fila), nunca a
média — um vídeo que bomba não esconde os outros. Só entram vídeos com {regras.get('maduro_dias')}
dias ou mais no ar, dos últimos {regras.get('janela_dias')} dias. "Veem" é quanto do vídeo as pessoas
assistem, em média, e só conta vídeo com {regras.get('min_views_retencao')} views ou mais.
Cada diferença passa por um teste: "clara" e "provável" passaram; o resto está em "ainda não dá
para dizer". "Veem" acima de 100% quer dizer que muita gente assistiu mais de uma vez.
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
    linhas += ["Ainda não dá para dizer:"] + [f"  - {x}" for x in analise["nao_da"]]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ver", action="store_true", help="só mostra; não grava nada")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--rede", action="store_true",
                        help="busca a série diária do canal (Analytics)")
    parser.add_argument("--biblioteca", action="store_true",
                        help="põe a página na Biblioteca do app")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    agora = datetime.now()
    if args.ver:
        entrada = carregar(agora)
        regs = registros(entrada)
        analise = analisar(regs, cobertura(entrada), agora, entrada["series"],
                           entrada["historico"], entrada["falhas"])
    else:
        analise = do_dia(agora=agora, rede=args.rede, biblioteca=args.biblioteca)
    print(json.dumps(analise, ensure_ascii=False, indent=1, default=str)
          if args.json else _texto(analise))
    return 1 if analise["estado"] in ("sem_dados", "velha") else 0


if __name__ == "__main__":
    raise SystemExit(main())
