# -*- coding: utf-8 -*-
"""O termo que derruba o video — achado antes de virar video.

O YouTube e o TikTok nao leem a historia: eles pegam PALAVRA e IMAGEM. Uma
boa historia perder a monetizacao por causa de um substantivo e desperdicio
puro — e o prejuizo nao aparece em lugar nenhum: o video sobe, fica no ar, e
so nao entrega. Descobrir isso pelas metricas leva semanas.

O prompt ja pede a linguagem certa (`config/roteiro.json -> linguagem`). Isto
aqui e a REDE: o modelo escorrega, e uma cena com o termo cru custa 2h de
imagem e render antes de alguem notar.

DUAS FAIXAS, e a diferenca importa:

    RISCO      palavra que costuma custar monetizacao ou alcance. Some
               reescrevendo a frase; a cena continua igual.
    PARE       assunto que a plataforma derruba pelo ASSUNTO, nao pelo termo —
               menor em situacao sexual. Nao ha reescrita que resolva: trocar
               a palavra so esconde de quem le, nao de quem revisa, e o preco
               do erro e o canal inteiro. Historia assim se descarta.
"""
from __future__ import annotations

import re
import unicodedata

# Palavras que costumam custar monetizacao ou alcance. A cena fica; o termo
# sai. A lista e curta de proposito: alarme demais vira alarme ignorado.
RISCO = {
    "morte": ("matou", "matei", "assassinou", "assassinato", "cadaver",
              "esfaqueou", "estrangulou", "enforcou"),
    "suicidio": ("suicidio", "suicidou", "se matou", "tirou a propria vida"),
    "sexo": ("transamos", "transei", "fizemos sexo", "nua", "nu", "pelada",
             "pelado", "orgasmo"),
    "violencia sexual": ("estupro", "estuprou", "estuprada", "abusou dela",
                         "abusou de mim"),
    "droga": ("cocaina", "maconha", "crack", "heroina", "seringa"),
    "palavrao": ("porra", "caralho", "foda", "fodido", "merda", "puta que",
                 "filho da puta", "viado", "buceta"),
}

# Assunto que nao tem versao publicavel. Aqui nao se reescreve: se descarta.
PARE = (
    "virgindade", "virgem",
    "menor de idade", "menor de 18", "de 12 anos", "de 13 anos", "de 14 anos",
    "de 15 anos", "de 16 anos", "de 17 anos",
    "crianca", "adolescente", "colegial",
)
# Estes so acendem quando aparecem PERTO de algo sexual — "minha filha de 14
# anos chorou" e uma frase normal de desabafo, e marcar isso seria ruido.
SEXUAL = ("sexo", "sexual", "cama", "transou", "transei", "beijo", "nua",
          "nu", "amante", "virgindade", "virgem", "comprou a minha",
          "dormiu comigo", "dormi com")
JANELA = 120          # caracteres de distancia que contam como "perto"


def _limpo(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                  if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sem).lower()


def _acha(texto: str, termos) -> list:
    """Os termos presentes como PALAVRA INTEIRA.

    A borda dos DOIS lados nao e detalhe: ancorando so o comeco, "nu" casava
    dentro de "nunca" e "num" — 24 alarmes falsos numa historia so, e alarme
    falso e o que faz o alarme de verdade ser ignorado.
    """
    achados = []
    for termo in termos:
        if re.search(rf"\b{re.escape(termo)}\b", texto):
            achados.append(termo)
    return achados


def conferir_texto(texto: str) -> dict:
    """{'risco': {categoria: [termos]}, 'pare': [termos]} de UMA narracao."""
    limpo = _limpo(texto)
    risco = {}
    for categoria, termos in RISCO.items():
        achados = _acha(limpo, termos)
        if achados:
            risco[categoria] = achados

    pare = []
    for termo in _acha(limpo, PARE):
        # so conta se houver contexto sexual por perto
        for m in re.finditer(re.escape(termo), limpo):
            trecho = limpo[max(0, m.start() - JANELA):m.end() + JANELA]
            if any(s in trecho for s in SEXUAL):
                pare.append(termo)
                break
    return {"risco": risco, "pare": sorted(set(pare))}


def conferir(roteiro: dict) -> dict:
    """A historia inteira. `pare` nao vazio = essa historia nao vai ao ar."""
    achados = {"risco": [], "pare": []}
    campos = [("titulo", roteiro.get("titulo") or ""),
              ("premissa", roteiro.get("premissa") or "")]
    for parte in roteiro.get("partes") or []:
        for cena in parte.get("cenas") or []:
            campos.append((f"p{int(parte['n']):02d}c{int(cena['n']):02d}",
                           cena.get("narracao") or ""))
    for onde, texto in campos:
        laudo = conferir_texto(texto)
        for categoria, termos in laudo["risco"].items():
            achados["risco"].append(
                {"onde": onde, "tipo": categoria, "termos": termos})
        if laudo["pare"]:
            achados["pare"].append({"onde": onde, "termos": laudo["pare"]})
    return achados


def conferir_biblia(biblia: dict) -> dict:
    """O plano da historia, ANTES de escrever qualquer cena.

    Este e o lugar barato de descobrir. Depois da biblia vem seis turnos de
    escrita, 84 imagens (~40 min de PicassoIA) e ~1h de render — e a premissa
    que a plataforma derruba ja estava inteira aqui, em duas frases.

    Achar aqui tambem e o unico ponto em que da para CONSERTAR: o molde, as
    alavancas e o elenco continuam valendo; o que muda e de onde vem a
    pressao. Ver `serie.prompt_trocar_premissa`.
    """
    achados = {"risco": [], "pare": []}
    campos = [("titulo", biblia.get("titulo") or ""),
              ("premissa", biblia.get("premissa") or ""),
              ("virada", biblia.get("virada") or ""),
              ("alavancas", biblia.get("alavancas") or "")]
    for parte in biblia.get("partes") or []:
        onde = f"parte {parte.get('n')}"
        for campo in ("titulo", "resumo", "gancho", "cliffhanger"):
            campos.append((f"{onde} {campo}", parte.get(campo) or ""))
    for onde, texto in campos:
        laudo = conferir_texto(texto)
        for categoria, termos in laudo["risco"].items():
            achados["risco"].append(
                {"onde": onde, "tipo": categoria, "termos": termos})
        if laudo["pare"]:
            achados["pare"].append({"onde": onde, "termos": laudo["pare"]})
    return achados


def termos_de_pare(achados: dict) -> list[str]:
    """So os termos, sem repetir — e o que o pedido de troca precisa dizer."""
    termos = []
    for item in achados.get("pare") or []:
        for termo in item.get("termos") or []:
            if termo not in termos:
                termos.append(termo)
    return termos


def resumo(achados: dict) -> list[str]:
    """Linhas prontas para o log e para o Telegram."""
    linhas = []
    for item in achados.get("pare") or []:
        linhas.append(
            f"PARE — {item['onde']}: {', '.join(item['termos'])}. Este assunto "
            "a plataforma derruba pelo que ELE E, nao pela palavra; trocar o "
            "termo so esconde de quem le. A historia nao vai ao ar.")
    for item in achados.get("risco") or []:
        linhas.append(
            f"risco ({item['tipo']}) — {item['onde']}: "
            f"{', '.join(item['termos'])}. Reescreva a frase: a cena fica, a "
            "palavra sai.")
    return linhas
