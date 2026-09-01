# -*- coding: utf-8 -*-
"""Quando o gerador de imagens RECUSA o prompt: detectar, suavizar, seguir.

O PicassoIA (como todo gerador) tem um filtro de conteudo. Uma cena de
historia com "faca", "sangue" ou uma crianca em situacao tensa volta
recusada — e ate 31/08/2026 isso custava CARO de tres jeitos:

  1. a recusa nao era detectada: `wait_for_render` esperava os 300 s inteiros
     e morria com "a imagem nao ficou pronta", escondendo o motivo real;
  2. a cena ficava sem imagem para sempre, porque a proxima tentativa
     mandava EXATAMENTE o mesmo prompt;
  3. na pratica a geracao parava — cada cena problematica queimava 5 minutos.

Este modulo e a contramedida, e ela e so texto (nenhum browser): uma tabela
de trocas por NIVEL, que o worker escalona sozinho.

  nivel 1  troca o notorio ("blood" -> "dark red stains"). Quase sempre
           resolve, e a imagem continua sendo a cena que o roteiro pediu.
  nivel 2  troca tambem o sensivel por contexto (menores, armas, autolesao)
           e APAGA a clausula que ainda tiver termo de risco.
  nivel 3  desiste da acao e fica com o AMBIENTE: mesmo lugar, mesma luz,
           mesmo estilo, sem gente. Feia como cena, mas o video nao fica com
           buraco — e o fallback tipografico e pior.

Prevencao vem de graca: quem chama pode pedir o nivel 1 ANTES do primeiro
envio (`escalonar(..., preventivo=True)`), gastando zero recusa no que ja
se sabe que seria barrado.

Regra de ouro: suavizar NUNCA pode inventar outra cena. Por isso as trocas
sao conservadoras e preservam o resto da frase — melhor uma imagem parecida
do que uma imagem errada.
"""
from __future__ import annotations

import re

# ------------------------------------------------------------------ recusa
# Frases que so aparecem quando o site recusou. Deliberadamente compridas: um
# "blocked" solto pega menu, rodape e ate o proprio prompt na tela. Falso
# positivo aqui e pior que falso negativo — ele faria o worker desistir de
# uma imagem que estava so demorando.
SINAIS_DE_RECUSA = (
    "conteudo inapropriado", "conteúdo inapropriado",
    "conteudo sensivel", "conteúdo sensível",
    "prompt inapropriado", "imagem inapropriada",
    "nao e permitido", "não é permitido",
    "viola nossas", "violacao de politica", "violação de política",
    "conteudo proibido", "conteúdo proibido",
    "inappropriate content", "inappropriate prompt",
    "content policy", "policy violation", "violates our",
    "not allowed", "prompt was blocked", "request was blocked",
    "blocked by our", "sensitive content", "safety system",
    "flagged as", "nsfw",
)


def parece_recusa(texto: str) -> str | None:
    """Devolve o sinal encontrado no texto da pagina (ou None)."""
    baixo = (texto or "").lower()
    for sinal in SINAIS_DE_RECUSA:
        if sinal in baixo:
            # devolve um pedaco em volta: e o que vira o motivo no log
            i = baixo.index(sinal)
            return " ".join((texto[max(0, i - 60):i + len(sinal) + 60]).split())
    return None


# ------------------------------------------------------------------ trocas
# (nivel, padrao, substituto, rotulo). O padrao roda com \b e IGNORECASE.
# NIVEL 1: o notorio — o que o filtro barra sozinho, sem contexto.
# NIVEL 2: o que so incomoda combinado (menores, armas, autolesao). Trocar
#          isso no nivel 1 estragaria cenas legitimas a toa.
TROCAS = (
    # --- sangue e ferimento
    (1, r"bleeding|sangrando|bleeds", "lying still", "sangue"),
    (1, r"blood(y|ied)?|sangue", "dark red stains", "sangue"),
    (1, r"gore|gory|mutilat\w*|dismember\w*|decapitat\w*", "damaged", "gore"),
    (1, r"corpse|dead body|cadaver|cadáver", "still figure lying down", "cadaver"),
    (1, r"wound(ed|s)?|injur(y|ies|ed)|ferimento|ferido",
     "bandaged", "ferimento"),
    (2, r"scar(s|red)?|bruise(s|d)?|cicatriz|hematoma", "mark", "marca"),
    # --- violencia
    (1, r"murder\w*|killing|kill(s|ed)?|assassinat\w*|matando|assassin\w*",
     "confronting", "morte"),
    (1, r"stab(bing|bed)?|esfaquea\w*", "threatening", "facada"),
    (1, r"tortur\w*", "tense interrogation", "tortura"),
    (2, r"violen\w*|assault(ing|ed)?|attack(ing|ed)?|agress\w*",
     "tense confrontation", "violencia"),
    (2, r"fight(ing)?|beating|briga|apanhando", "heated argument", "briga"),
    # --- armas
    (2, r"knife|knives|dagger|blade|faca|punhal|lamina|lâmina",
     "metal tool", "faca"),
    (2, r"gun|pistol|rifle|shotgun|firearm|weapon|arma de fogo|revolver",
     "metal object", "arma"),
    # --- corpo / sexualizacao
    (1, r"nude|naked|nudity|topless|nua?\b|pelad[ao]", "fully clothed", "nudez"),
    (1, r"erotic|sexual\w*|seductive|lingerie|sensual|erotic\w*",
     "elegant", "sexualizacao"),
    (2, r"underwear|bikini|roupa intima|roupa íntima", "casual clothes",
     "roupa intima"),
    # --- menores (a causa numero 1 de recusa em cena tensa)
    (2, r"child(ren)?|kid(s)?|toddler|baby|babies|infant|little (girl|boy)"
        r"|crianc\w*|criança|menin[ao]|bebê|bebe",
     "young adult", "menor"),
    (2, r"teen\w*|adolescent\w*|adolescente|jovem de \d+", "young adult",
     "menor"),
    # --- autolesao e substancias
    (1, r"suicid\w*|self.?harm|hanging|enforcad\w*|suicíd\w*|suicid\w*",
     "person in distress", "autolesao"),
    (1, r"overdose|cocaine|heroin|syringe|drugs?|drogas?|seringa",
     "small objects", "drogas"),
    # --- outros gatilhos frequentes
    (2, r"nazi|swastika|terrorist|terrorista", "historical", "extremismo"),
    (2, r"burning (person|body)|queimad[ao] viv[ao]", "smoke", "fogo"),
)

_COMPILADAS = tuple(
    (nivel, re.compile(rf"\b(?:{padrao})\b", re.IGNORECASE), sub, rotulo)
    for nivel, padrao, sub, rotulo in TROCAS)

# Quem e "gente" numa clausula. O nivel 3 promete "sem pessoas": deixar
# passar "a woman standing" so porque ela nao tem termo de risco entregaria
# um prompt que se contradiz — e o gerador obedece a metade errada.
PESSOA = re.compile(
    r"\b(?:man|men|woman|women|girl|boy|person|people|figure|child|kid|adult"
    r"|guy|lady|father|mother|dad|mom|son|daughter|brother|sister|wife"
    r"|husband|stepfather|stepmother|friend|stranger|crowd|face|hands?|eyes"
    r"|arms?|legs?|body|silhouette|portrait|selfie|homem|mulher|menin[ao]"
    r"|pessoa|rosto|maos?|corpo)\b", re.IGNORECASE)

# "in the kitchen" -> "kitchen": o que salva o nivel 3 de virar so estilo.
LUGAR = re.compile(
    r"\b(?:in|at|on|inside|outside|near|by)\s+(?:the|a|an)\s+"
    r"([a-z][a-z\s\-]{2,38})", re.IGNORECASE)


def _lugar_da(clausula: str) -> str | None:
    achado = LUGAR.search(clausula or "")
    if not achado:
        return None
    lugar = " ".join(achado.group(1).split()).strip()
    return lugar or None


# Cauda de seguranca: dita o tom sem mudar a cena.
CAUDA_SEGURA = "safe for work, non graphic, tasteful, no violence"
CAUDA_AMBIENTE = "atmospheric establishing shot, empty scene, no people"


def arriscado(prompt: str, nivel: int = 3) -> list:
    """Rotulos dos termos de risco presentes ate `nivel` (para log/prevencao)."""
    achados = []
    for n, padrao, _sub, rotulo in _COMPILADAS:
        if n <= nivel and padrao.search(prompt or ""):
            achados.append(rotulo)
    return sorted(set(achados))


def _clausulas(prompt: str) -> list:
    return [c.strip() for c in (prompt or "").split(",") if c.strip()]


def suavizar(prompt: str, nivel: int) -> tuple:
    """(prompt_novo, mudancas). `nivel` 0 devolve o original intocado."""
    if nivel <= 0:
        return prompt, []
    texto, mudancas = prompt or "", []
    for n, padrao, sub, rotulo in _COMPILADAS:
        if n > nivel:
            continue
        texto, trocas = padrao.subn(sub, texto)
        if trocas:
            mudancas.append(rotulo)

    if nivel >= 2:
        # O que sobrou de risco sai inteiro: uma clausula a menos e melhor do
        # que uma recusa. As clausulas de ESTILO nunca tem termo de risco,
        # entao o visual do filme sobrevive.
        restantes = [c for c in _clausulas(texto) if not arriscado(c)]
        if restantes and len(restantes) < len(_clausulas(texto)):
            mudancas.append("clausula removida")
        texto = ", ".join(restantes or _clausulas(texto))
        if CAUDA_SEGURA not in texto:
            texto = f"{texto}, {CAUDA_SEGURA}"

    if nivel >= 3:
        # Ultimo recurso: fica o AMBIENTE. Sem gente nao ha o que moderar, e
        # a cena mantem lugar, luz e estilo — da para montar o video.
        # A clausula com gente sai, mas o LUGAR dela e resgatado ("a girl in
        # the kitchen" -> "empty kitchen"): sem isso o nivel 3 viraria so
        # estilo, igual para toda cena da historia.
        limpas, lugares = [], []
        for clausula in _clausulas(texto):
            if clausula in (CAUDA_SEGURA, CAUDA_AMBIENTE):
                continue
            if PESSOA.search(clausula) or arriscado(clausula):
                lugar = _lugar_da(clausula)
                if lugar and not PESSOA.search(lugar):
                    lugares.append(f"empty {lugar}")
                continue
            limpas.append(clausula)
        texto = ", ".join([CAUDA_AMBIENTE] + lugares + limpas)
        mudancas.append("so o ambiente")

    return texto.strip().strip(","), sorted(set(mudancas))


def escalonar(prompt: str, max_nivel: int = 3, preventivo: bool = True):
    """Sequencia de tentativas: (nivel, prompt, mudancas).

    Com `preventivo`, um prompt que JA tem termo notorio nao gasta uma recusa
    para descobrir o obvio: a primeira tentativa ja sai suavizada.
    """
    inicio = 1 if (preventivo and arriscado(prompt, nivel=1)) else 0
    for nivel in range(inicio, max(inicio, int(max_nivel)) + 1):
        novo, mudancas = suavizar(prompt, nivel)
        yield nivel, novo, mudancas
