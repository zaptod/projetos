# -*- coding: utf-8 -*-
"""Historia LONGA, dividida em partes: a biblia primeiro, depois cada parte.

Pedir "uma historia de 80 cenas" num prompt so nao funciona: o modelo perde
o fio, repete informacao e resolve o conflito no meio. O que funciona e o
que um roteirista faz — primeiro a BIBLIA (premissa, elenco, a virada
central e o arco de cada parte), depois cada parte escrita com a biblia
inteira em contexto.

E por isso que a automacao do browser importa: as duas etapas acontecem no
MESMO chat, entao a parte 7 e escrita com a biblia e as seis partes
anteriores ainda no contexto. Copiar e colar isso a mao seria inviavel.

A biblia tambem resolve o problema visual: ela fixa a descricao FISICA do
protagonista em ingles, e essa mesma frase entra em toda cena de todas as
partes. E o que faz 80 imagens parecerem a mesma pessoa.
"""
from __future__ import annotations

import re
import unicodedata

from .modelo import carregar_config

# Uma parte = um video. Estes numeros sao o alvo que vai no prompt.
CENAS_POR_PARTE = 14
PARTES_PADRAO = 6


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def _limpar(linha: str) -> str:
    texto = str(linha).replace("**", "").replace("__", "").strip()
    texto = re.sub(r"^\s*[-*+]\s+", "", texto)
    return re.sub(r"^#{1,4}\s*", "", texto).strip()


# --------------------------------------------------------------- 1. biblia
def prompt_biblia(*, partes: int = PARTES_PADRAO,
                  cenas_por_parte: int = CENAS_POR_PARTE,
                  tema: str | None = None, config: dict | None = None) -> str:
    """Etapa 1: a historia inteira planejada, sem escrever nenhuma cena."""
    config = config or carregar_config()
    regras = config["regras"]
    total_cenas = partes * cenas_por_parte
    duracao = total_cenas * 5

    linhas = []
    add = linhas.append
    add("Voce e roteirista-chefe de um canal de historias narradas em video "
        "vertical (TikTok/Shorts/Reels). Vamos trabalhar em DUAS etapas.")
    add("")
    add("ETAPA 1 (agora): a BIBLIA da historia. Nao escreva nenhuma cena "
        "ainda, nao escreva narracao, nao escreva prompt de imagem.")
    add("")
    add(f"A historia sera longa: {partes} PARTES de {cenas_por_parte} cenas "
        f"cada ({total_cenas} cenas, cerca de {duracao // 60} minutos no total). "
        "Cada parte vira um video proprio, publicado em sequencia.")
    if tema:
        add(f"TEMA (ponto de partida; o resto voce inventa): {tema}")
    else:
        add("TEMA: voce escolhe. Uma situacao especifica e incomum, que a "
            "pessoa nao consegue prever pelo titulo.")
    add("")
    add("REGRAS DA HISTORIA (valem para o planejamento inteiro):")
    add("  - Historia ficticia em primeira pessoa, com nomes inventados.")
    add("  - O texto final vai soar como um DESABAFO que uma pessoa real "
        "postou num forum, nao como roteiro. Planeje so acontecimentos que "
        "alguem contaria de memoria, com detalhe mundano e ponta solta.")
    add("  - UMA pergunta central atravessa as {n} partes e so e respondida "
        "na ultima.".replace("{n}", str(partes)))
    add("  - Cada parte tem a propria mini-virada, alem da virada central.")
    add("  - Nada de enrolacao: se um acontecimento nao muda a situacao do "
        "protagonista, ele nao existe.")
    add("  - A historia precisa caber num relato pessoal: sem magia, sem "
        "conspiracao mundial, sem final de novela.")
    add("")
    add("CONSISTENCIA VISUAL (isto e obrigatorio):")
    add("  - Descreva o protagonista FISICAMENTE em ingles, em uma frase "
        "curta e fixa (idade aparente, cabelo, rosto, roupa recorrente).")
    add("  - Essa frase sera repetida em TODAS as imagens de TODAS as partes, "
        "entao nao pode mudar depois. Nada de nome dentro dela.")
    add("  - Faca o mesmo para cada personagem que aparece mais de uma vez.")
    add("")
    add("FORMATO DA RESPOSTA (exatamente assim, sem nada em volta):")
    add("")
    add("TITULO DA SERIE: <uma linha, em primeira pessoa, que ja entrega o "
        "conflito e provoca curiosidade>")
    add("PREMISSA: <2 frases: a situacao e a pergunta central>")
    add("PROTAGONISTA: <nome> | <descricao fisica em ingles, uma frase>")
    add("NARRADOR: <homem ou mulher — quem esta contando em primeira pessoa>")
    add("ELENCO: <nome> | <descricao fisica em ingles>; <nome> | <descricao>")
    add("CENARIO: <onde a historia acontece, em ingles, uma frase>")
    add("VIRADA CENTRAL: <a informacao que muda tudo, e em que parte ela sai>")
    add("")
    for i in range(1, partes + 1):
        add(f"PARTE {i}")
        add("TITULO: <titulo da parte>")
        add("RESUMO: <o que acontece nesta parte, 2 frases>")
        add("GANCHO: <a primeira frase da parte, a mais forte que ela tem>")
        if i < partes:
            add("CLIFFHANGER: <a pergunta que fica no ar para a parte seguinte>")
        else:
            add("CLIFFHANGER: FINAL - <como a pergunta central e respondida>")
        add("")
    add("Regras de escrita que valerao na etapa 2 (para voce ja planejar "
        "pensando nelas):")
    for regra in regras["narracao"][:6]:
        add(f"  - {regra}")
    return "\n".join(linhas)


def parse_biblia(texto: str, partes_esperadas: int = PARTES_PADRAO) -> dict:
    """Texto da etapa 1 -> {titulo, premissa, protagonista, elenco, partes}."""
    campos = {"titulo": "", "premissa": "", "protagonista": "", "elenco": "",
              "cenario": "", "virada": "", "narrador": ""}
    rotulos = {
        "titulo da serie": "titulo", "titulo": "titulo", "premissa": "premissa",
        "protagonista": "protagonista", "elenco": "elenco", "cenario": "cenario",
        "virada central": "virada", "narrador": "narrador",
    }
    partes = []
    atual = None
    for bruta in texto.splitlines():
        linha = _limpar(bruta)
        if not linha:
            continue
        cabecalho = re.match(r"^parte\s*(\d+)", _sem_acento(linha).lower())
        if cabecalho and ":" not in linha:
            atual = {"n": int(cabecalho.group(1)), "titulo": "", "resumo": "",
                     "gancho": "", "cliffhanger": ""}
            partes.append(atual)
            continue
        if ":" not in linha:
            continue
        rotulo, _, valor = linha.partition(":")
        chave = _sem_acento(rotulo).strip().lower()
        valor = valor.strip()
        if atual is not None and chave in ("titulo", "resumo", "gancho",
                                           "cliffhanger"):
            atual[chave] = valor
            continue
        if chave in rotulos and not atual:
            campos[rotulos[chave]] = valor

    nome, _, fisico = campos["protagonista"].partition("|")
    for parte in partes:
        parte["n"] = int(parte["n"])
    partes.sort(key=lambda p: p["n"])
    for ordem, parte in enumerate(partes, 1):
        parte["n"] = ordem

    return {
        "titulo": campos["titulo"],
        "premissa": campos["premissa"],
        "protagonista_nome": nome.strip(),
        "protagonista": fisico.strip() or campos["protagonista"].strip(),
        "narrador": campos["narrador"],
        "elenco": campos["elenco"],
        "cenario": campos["cenario"],
        "virada": campos["virada"],
        "partes": partes,
        "partes_esperadas": partes_esperadas,
        "bruto": texto,
    }


def problemas_da_biblia(biblia: dict) -> list:
    """O que impede a etapa 2 de sair boa."""
    faltando = []
    if not biblia.get("titulo"):
        faltando.append("sem TITULO DA SERIE")
    if not biblia.get("protagonista"):
        faltando.append("sem descricao fisica do protagonista "
                        "(as imagens vao sair de pessoas diferentes)")
    if not biblia.get("partes"):
        faltando.append("nenhuma PARTE foi planejada")
    elif len(biblia["partes"]) < biblia.get("partes_esperadas", 0):
        faltando.append(f"so {len(biblia['partes'])} parte(s) planejadas de "
                        f"{biblia['partes_esperadas']}")
    sem_gancho = [p["n"] for p in biblia.get("partes", []) if not p.get("gancho")]
    if sem_gancho:
        faltando.append(f"partes sem GANCHO: {sem_gancho}")
    return faltando


# ---------------------------------------------------------------- 2. parte
def prompt_parte(biblia: dict, numero: int, *,
                 cenas: int = CENAS_POR_PARTE,
                 config: dict | None = None) -> str:
    """Etapa 2: escreve UMA parte, em cenas, no formato do contrato."""
    config = config or carregar_config()
    regras = config["regras"]
    total = len(biblia.get("partes") or []) or biblia.get("partes_esperadas", 1)
    plano = next((p for p in biblia.get("partes") or [] if p["n"] == numero), {})
    primeira = numero == 1
    ultima = numero >= total

    linhas = []
    add = linhas.append
    add(f"ETAPA 2 - escreva agora a PARTE {numero} de {total}, e SO ela.")
    add("")
    if plano:
        add(f"O que esta parte tem que entregar (do seu proprio plano): "
            f"{plano.get('resumo') or plano.get('titulo')}")
        if plano.get("gancho"):
            add(f"Gancho planejado: {plano['gancho']}")
        if plano.get("cliffhanger"):
            add(f"Ela termina em: {plano['cliffhanger']}")
        add("")
    add(f"Escreva exatamente {cenas} cenas.")
    add("")
    if primeira:
        add("ABERTURA (parte 1): a primeira cena e o momento mais chocante da "
            "HISTORIA INTEIRA, dito no meio da acao, antes de qualquer "
            "contexto. Nao apresente ninguem antes disso.")
    else:
        add(f"ABERTURA (parte {numero}): a cena 1 recapitula o essencial em "
            "UMA frase que funciona como gancho novo para quem cai aqui "
            "primeiro - nunca 'no episodio anterior'. A cena 2 ja avanca.")
    if ultima:
        add("FECHAMENTO (ultima parte): responda a pergunta central de forma "
            "concreta. Depois, a ultima cena faz uma pergunta direta para "
            "quem assiste. Nao deixe nada em aberto.")
    else:
        add(f"FECHAMENTO (parte {numero}): as duas ultimas cenas montam o "
            "cliffhanger e a ULTIMA FRASE e a pergunta que fica no ar.")
        add("  - NUNCA escreva 'a historia continua na proxima parte' (nem "
            "nada parecido). Medido em 01/09/2026: 9 de 10 partes de uma "
            "serie terminavam com essa frase literal, no pior lugar possivel "
            "— a ultima coisa que a pessoa ouve. Repetida dez vezes, ela "
            "denuncia que o texto saiu de um molde.")
        add("  - A continuacao se PROMETE pela pergunta, nao se anuncia. Se "
            "a pergunta final for boa, ninguem precisa ser avisado de que "
            "existe uma proxima parte.")
    add("")
    add("CONSISTENCIA VISUAL (obrigatorio em todas as cenas):")
    if biblia.get("protagonista"):
        add(f"  - Sempre que o protagonista aparecer, comece o prompt de "
            f"imagem com: {biblia['protagonista']}")
    if biblia.get("elenco"):
        add(f"  - Outros personagens: {biblia['elenco']}")
    if biblia.get("cenario"):
        add(f"  - Cenario: {biblia['cenario']}")
    add("")
    add("COMO ESCREVER A NARRACAO (a parte mais importante):")
    add("  Isto NAO e uma historia narrada: e um desabafo que uma pessoa real "
        "esta digitando de madrugada. Quem ouvir tem que pensar 'isso "
        "aconteceu mesmo'. As imagens ja entregam que o video e artificial - "
        "o texto e a unica chance de parecer gente. As regras:")
    for regra in regras["narracao"]:
        add(f"  - {regra}")
    add("")
    add("COMO ESCREVER O PROMPT DE IMAGEM:")
    for regra in regras["imagem"]:
        add(f"  - {regra}")
    add("")
    add("SOBRE O TEMPO:")
    for regra in regras["tempo"]:
        add(f"  - {regra}")
    add("")
    add("FORMATO DA RESPOSTA (exatamente assim, sem nada em volta):")
    add("")
    add(f"TITULO: <titulo desta parte, terminando com ' (Parte {numero})'>")
    add("")
    add("CENA 1")
    add("IMAGEM: <prompt em ingles>")
    add("TEMPO: <segundos, so o numero>")
    add("NARRACAO: <o que o narrador fala>")
    add("")
    add(f"... ate a CENA {cenas}. Nao escreva mais nada depois da ultima cena.")
    return "\n".join(linhas)


def prompt_continuar(numero: int, ultima_cena: int, cenas: int) -> str:
    """Quando a resposta veio cortada (limite de mensagem do site)."""
    return (f"A parte {numero} veio incompleta: a ultima cena que chegou foi a "
            f"CENA {ultima_cena}. Continue exatamente de onde parou, escrevendo "
            f"da CENA {ultima_cena + 1} ate a CENA {cenas}, no mesmo formato "
            "(CENA / IMAGEM / TEMPO / NARRACAO). Nao repita as cenas "
            "anteriores e nao escreva nenhum texto fora do formato.")
