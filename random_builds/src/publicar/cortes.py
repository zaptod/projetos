# -*- coding: utf-8 -*-
"""Vídeo comprido demais para Shorts: cortar em partes, nas cenas certas.

O YouTube só trata um vídeo vertical como **Short** até 3 minutos (180 s).
Passou disso, ele vira vídeo normal: sai da esteira de Shorts, perde o feed
vertical e o alcance despenca. Medido em 31/08/2026, as três partes prontas
da `historia_00003` tinham 206 s, 191 s e 189 s — todas fora, e nada avisava.

O que este módulo NÃO faz: cortar no relógio. Um corte em 180 s cravado cai
no meio de uma palavra, e a parte seguinte começa com meia frase. Como o
plano de edição (`edit_plan.json`) guarda o início de cada cena, o corte
acontece na FRONTEIRA DE CENA mais próxima do ponto ideal — a fala termina,
a imagem troca, e só então o vídeo corta.

E os pedaços saem EQUILIBRADOS, não "180 s + o resto": 206 s viram 100 s +
106 s, não 180 s + 26 s. Um rabinho de 26 segundos não segura ninguém.
"""
from __future__ import annotations

import copy
import json
import math
import re
import subprocess
from pathlib import Path

from ..video import medidas

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# 3 minutos: o teto do Shorts. A margem existe porque a duração real do mp4
# vem com alguns centésimos a mais que o plano, e ficar em 180,04 s custaria
# o formato inteiro.
LIMITE_PADRAO_S = 180.0
MARGEM_S = 2.0
# Nenhum pedaço menor que isto: um Short de 8 segundos no meio de uma série
# não conta história nenhuma.
MINIMO_S = 12.0
MAX_PEDACOS = 12
# Quanto o corte pode se afastar do ponto ideal para pegar uma cena que
# ABRE melhor (fracao da fatia). 25% de 100 s = 25 s de margem — o
# bastante para escolher entre duas ou tres cenas vizinhas.
TOLERANCIA_GANCHO = 0.25


def limite(config: dict | None = None) -> float:
    """O teto em segundos, do config. 0 (ou negativo) DESLIGA o corte."""
    if config is None:
        try:
            from . import catalogo
            config = catalogo.carregar_config()
        except Exception:
            config = {}
    youtube = (config or {}).get("youtube") or {}
    if not youtube.get("cortar_para_shorts", True):
        return 0.0
    return float(youtube.get("shorts_max_s", LIMITE_PADRAO_S))


# ------------------------------------------------------------- fronteiras
def fronteiras(caminho) -> list:
    """Os inícios de cena do vídeo, lidos do plano de edição.

    Procura o `edit_plan.json` em dois lugares: ao lado do mp4 (builds) e na
    pasta da parte (`partes/pNN/`, histórias). Sem plano, devolve vazio — e
    aí o corte cai no ponto ideal mesmo, que é pior, mas ainda funciona.
    """
    caminho = Path(caminho)
    candidatos = [caminho.parent / "edit_plan.json"]
    achado = re.search(r"_p(\d{2})\b", caminho.stem)
    if achado:
        candidatos.append(caminho.parent / "partes" / f"p{achado.group(1)}"
                          / "edit_plan.json")
    for alvo in candidatos:
        if not alvo.is_file():
            continue
        try:
            with open(alvo, encoding="utf-8") as fh:
                plano = json.load(fh)
        except (OSError, ValueError):
            continue
        pontos = [float(e.get("start", 0.0)) for e in plano.get("events") or []]
        if pontos:
            return sorted(set(pontos))
    return []


# Quando uma parte vira dois Shorts, o SEGUNDO comeca no meio da historia —
# sem titulo, sem contexto e, por padrao, sem gancho. No feed vertical isso e
# fatal: a pessoa entra numa frase pela metade e rola. Como as fronteiras
# candidatas sao inicios de CENA, e cada cena comeca com uma frase escrita
# para prender, da para escolher a fronteira que abre MELHOR — e nao apenas a
# mais proxima do ponto ideal.
def ganchos(caminho) -> dict:
    """{segundo_de_inicio: forca do gancho} lido do plano de edicao."""
    caminho = Path(caminho)
    candidatos = [caminho.parent / "edit_plan.json"]
    achado = re.search(r"_p(\d{2})", caminho.stem)
    if achado:
        candidatos.append(caminho.parent / "partes" / f"p{achado.group(1)}"
                          / "edit_plan.json")
    for alvo in candidatos:
        if not alvo.is_file():
            continue
        try:
            with open(alvo, encoding="utf-8") as fh:
                plano = json.load(fh)
        except (OSError, ValueError):
            continue
        saida = {}
        for evento in plano.get("events") or []:
            if evento.get("continuacao"):
                continue        # plano extra da mesma cena: nao abre nada
            texto = str(evento.get("narracao") or "")
            if texto:
                saida[float(evento.get("start", 0.0))] = forca_do_gancho(texto)
        if saida:
            return saida
    return {}


def forca_do_gancho(narracao: str) -> float:
    """Quanto essa frase segura quem acabou de chegar.

    Tres sinais, todos verificaveis no texto: pergunta (a pessoa fica para
    saber a resposta), frase curta (le-se num piscar) e detalhe concreto
    (numero, data, valor — e o que faz soar verdade).
    """
    texto = str(narracao or "").strip()
    if not texto:
        return 0.0
    primeira = re.split(r"(?<=[.!?])\s", texto)[0]
    nota = 0.0
    if primeira.rstrip().endswith("?"):
        nota += 2.0
    if len(primeira.split()) <= 9:
        nota += 1.0
    if re.search(r"\d", primeira):
        nota += 1.0
    return nota


def _mais_perto(pontos, ideal: float, minimo: float, maximo: float,
                notas: dict | None = None, tolerancia: float = 0.0):
    """A fronteira mais próxima do ideal que ainda cabe na janela."""
    cabem = [p for p in pontos if minimo <= p <= maximo]
    if not cabem:
        return None
    if notas and tolerancia > 0:
        # Entre as fronteiras que ficam PERTO do ponto ideal, vence a que
        # abre melhor. Trocar alguns segundos de equilibrio por um Short que
        # comeca numa pergunta e um bom negocio.
        perto = [p for p in cabem if abs(p - ideal) <= tolerancia]
        if perto:
            return max(perto, key=lambda p: (notas.get(p, 0.0),
                                             -abs(p - ideal)))
    return min(cabem, key=lambda p: abs(p - ideal))


def pedacos(duracao: float, limite: float = LIMITE_PADRAO_S,
            pontos=None, notas: dict | None = None) -> list:
    """[(início, fim)] — os cortes, equilibrados e em fronteira de cena."""
    duracao = float(duracao)
    limite = max(float(limite) - MARGEM_S, MINIMO_S * 2)
    if duracao <= limite + MARGEM_S:
        return [(0.0, duracao)]

    pontos = sorted(p for p in (pontos or []) if 0 < p < duracao)
    quantos = min(MAX_PEDACOS, max(2, math.ceil(duracao / limite)))
    while quantos <= MAX_PEDACOS:
        cortes, anterior = [], 0.0
        alvo = duracao / quantos
        for i in range(1, quantos):
            ideal = alvo * i
            escolha = _mais_perto(
                pontos, ideal,
                minimo=anterior + MINIMO_S,
                maximo=min(anterior + limite, duracao - MINIMO_S),
                notas=notas, tolerancia=alvo * TOLERANCIA_GANCHO)
            if escolha is None:
                # Sem fronteira utilizável (cena mais longa que o limite, ou
                # vídeo sem plano): corta no ponto ideal mesmo.
                escolha = min(ideal, anterior + limite, duracao - MINIMO_S)
            cortes.append(escolha)
            anterior = escolha
        marcos = [0.0] + cortes + [duracao]
        fatias = list(zip(marcos, marcos[1:]))
        if all(fim - ini <= limite + MARGEM_S for ini, fim in fatias):
            return fatias
        quantos += 1        # nenhuma fronteira serviu: mais pedaços, menores
    return fatias


# ------------------------------------------------------------------ cortar
def nome_do_pedaco(caminho: Path, indice: int) -> Path:
    return caminho.with_name(f"{caminho.stem}_corte{indice:02d}{caminho.suffix}")


def cortar(caminho, fatias, log=print) -> list:
    """Escreve um mp4 por fatia. Recodifica de propósito.

    `-c copy` cortaria no keyframe mais próximo — até 2 s longe do pedido,
    o suficiente para comer o começo de uma frase. Recodificar custa alguns
    segundos e entrega o corte no ponto exato.
    """
    caminho = Path(caminho)
    saidas = []
    for indice, (inicio, fim) in enumerate(fatias, 1):
        destino = nome_do_pedaco(caminho, indice)
        duracao = round(fim - inicio, 3)
        comando = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{inicio:.3f}", "-i", str(caminho), "-t", f"{duracao:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(destino)]
        resultado = subprocess.run(comando, capture_output=True, text=True,
                                   creationflags=NO_WINDOW)
        real = medidas.duracao(destino)
        if resultado.returncode != 0 or real is None:
            destino.unlink(missing_ok=True)
            raise RuntimeError(
                f"nao consegui cortar {caminho.name} em {inicio:.0f}s: "
                f"{(resultado.stderr or '')[-300:]}")
        log(f"[cortes] {destino.name}: {real:.1f}s "
            f"({inicio:.0f}s -> {fim:.0f}s)")
        saidas.append(destino)
    return saidas


# ------------------------------------------------------------------ porta
def precisa(video, limite: float = LIMITE_PADRAO_S):
    """(duração, True/False): este vídeo estoura o Shorts?

    Só vale para vertical: um 16:9 nunca seria Short, então cortá-lo não
    resolveria nada.
    """
    duracao = medidas.duracao(getattr(video, "caminho", video))
    if duracao is None or not getattr(video, "vertical", True):
        return duracao, False
    return duracao, duracao > float(limite)


def _copia(video, arquivo: Path, indice: int, total: int):
    """O mesmo vídeo, apontando para o pedaço, com o título dizendo a ordem."""
    novo = copy.copy(video)
    novo.caminho = arquivo
    novo.titulo = f"{video.titulo} ({indice} de {total})"
    try:
        novo.id = f"{video.id}:corte{indice:02d}"
    except (AttributeError, TypeError):
        pass
    try:
        novo.bytes = arquivo.stat().st_size
    except OSError:
        pass
    return novo


def preparar(video, *, limite: float = LIMITE_PADRAO_S, log=print) -> list:
    """O vídeo como ele vai ao YouTube: inteiro, ou já cortado em Shorts.

    Devolve sempre uma LISTA — quem publica percorre, e o caso normal é uma
    lista de um. Falhar em cortar não impede a publicação: o vídeo sobe
    inteiro (como vídeo normal) e o log diz o que aconteceu.
    """
    if not limite or limite <= 0:      # corte desligado no config
        return [video]
    duracao, estoura = precisa(video, limite)
    if not estoura:
        return [video]
    fatias = pedacos(duracao, limite, fronteiras(video.caminho),
                     notas=ganchos(video.caminho))
    log(f"[cortes] {Path(video.caminho).name}: {duracao:.0f}s passa do limite "
        f"de {limite:.0f}s do Shorts — cortando em {len(fatias)} parte(s) nas "
        "trocas de cena.")
    try:
        arquivos = cortar(video.caminho, fatias, log=log)
    except (RuntimeError, OSError) as exc:
        log(f"[cortes] nao consegui cortar ({exc}); vai inteiro, como video "
            "normal (fora do Shorts).")
        return [video]
    return [_copia(video, arquivo, i, len(arquivos))
            for i, arquivo in enumerate(arquivos, 1)]
