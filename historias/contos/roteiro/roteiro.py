# -*- coding: utf-8 -*-
"""O roteiro: ler a resposta do LLM, validar e guardar.

O parser e TOLERANTE de proposito. O contrato pede blocos
`CENA n / IMAGEM: / TEMPO: / NARRACAO:`, mas todo LLM enfeita: poe `**`,
`##`, numera com `1.`, troca `NARRACAO` por `NARRAÇÃO`, ou devolve JSON
mesmo tendo sido pedido texto. Recusar por causa disso faria voce editar
texto a mao — que e exatamente o trabalho que este projeto existe para tirar.

O que NAO e tolerado (e vira erro com o motivo): roteiro sem cena, cena sem
narracao, cena sem prompt de imagem. Sem isso nao existe video.

`validar` devolve `problemas` (o que esta no limite) e `erros` (o que impede
de continuar). O CLI e o painel mostram os dois.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"

# Rotulos aceitos para cada campo, sem acento e em caixa baixa.
CHAVES = {
    "imagem": ("imagem", "image", "prompt", "prompt de imagem", "img", "visual",
               "cena visual"),
    "tempo": ("tempo", "time", "duracao", "duration", "segundos", "seg"),
    "narracao": ("narracao", "narration", "texto", "fala", "voz", "roteiro",
                 "narrador", "legenda"),
}
CABECALHO_CENA = re.compile(r"^\s*(?:#{1,4}\s*)?(?:cena|scene)\s*[:\-#]?\s*(\d+)",
                            re.IGNORECASE)
LINHA_TITULO = re.compile(r"^\s*(?:#{1,4}\s*)?(?:titulo|title)\s*[:\-]\s*(.+)$",
                          re.IGNORECASE)
LINHA_CTA = re.compile(r"^\s*(?:#{1,4}\s*)?(?:cta|chamada)\s*[:\-]\s*(.+)$",
                       re.IGNORECASE)

# A cerca de codigo do markdown, montada sem escrever o caractere: um bloco
# ```json e o jeito mais comum de um LLM devolver JSON "puro".
_CERCA = chr(96) * 3


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def _limpar(linha: str) -> str:
    """Tira o enfeite de markdown sem tocar no conteudo."""
    texto = linha.replace("\t", " ").rstrip()
    texto = re.sub(r"^\s*[-*+]\s+", "", texto)
    texto = re.sub(r"^\s*\d+[.)]\s+(?=[A-Za-zÀ-ÿ])", "", texto)
    texto = texto.replace("**", "").replace("__", "")
    return texto.strip()


def _chave_da_linha(linha: str):
    """('narracao', 'texto...') se a linha abre um campo conhecido."""
    if ":" not in linha:
        return None
    rotulo, _, valor = linha.partition(":")
    rotulo = _sem_acento(rotulo).strip().lower().lstrip("#").strip()
    rotulo = re.sub(r"^\d+[.)]\s*", "", rotulo)
    for campo, aceitos in CHAVES.items():
        if rotulo in aceitos:
            return campo, valor.strip()
    return None


def _do_json(texto: str):
    """O LLM devolveu JSON? Aceita cru ou dentro de uma cerca de codigo."""
    bruto = texto.strip()
    cerca = re.search(_CERCA + r"(?:json)?\s*(.+?)" + _CERCA, bruto, re.DOTALL)
    if cerca:
        bruto = cerca.group(1).strip()
    if not bruto.startswith("{") and not bruto.startswith("["):
        return None
    try:
        dados = json.loads(bruto)
    except ValueError:
        return None
    if isinstance(dados, list):
        dados = {"cenas": dados}
    if not isinstance(dados, dict):
        return None
    cenas_brutas = (dados.get("cenas") or dados.get("scenes")
                    or dados.get("roteiro") or [])
    cenas = []
    for bruta in cenas_brutas:
        if not isinstance(bruta, dict):
            continue
        procurar = {_sem_acento(str(k)).lower(): v for k, v in bruta.items()}
        cena = {}
        for campo, aceitos in CHAVES.items():
            for aceito in aceitos:
                if aceito in procurar:
                    cena[campo] = procurar[aceito]
                    break
        if cena:
            cenas.append(cena)
    if not cenas:
        return None
    return {"titulo": str(dados.get("titulo") or dados.get("title") or "").strip(),
            "cta": str(dados.get("cta") or "").strip(), "cenas": cenas}


def _dos_blocos(texto: str) -> dict:
    """O formato do contrato: TITULO + blocos CENA/IMAGEM/TEMPO/NARRACAO."""
    titulo, cta = "", ""
    cenas = []
    atual = None
    campo_aberto = None

    for linha_bruta in texto.splitlines():
        linha = _limpar(linha_bruta)
        if not linha:
            campo_aberto = None
            continue

        cabecalho = CABECALHO_CENA.match(linha)
        if cabecalho and _chave_da_linha(linha) is None:
            atual = {"n": int(cabecalho.group(1))}
            cenas.append(atual)
            campo_aberto = None
            # "CENA 3: texto" - o que vem depois dos dois pontos e narracao
            resto = linha.split(":", 1)[1].strip() if ":" in linha else ""
            if resto:
                atual["narracao"] = resto
                campo_aberto = "narracao"
            continue

        if not cenas:
            achado = LINHA_TITULO.match(linha)
            if achado:
                titulo = achado.group(1).strip().strip('"')
                campo_aberto = None
                continue

        achado_cta = LINHA_CTA.match(linha)
        if achado_cta and _chave_da_linha(linha) is None:
            cta = achado_cta.group(1).strip()
            campo_aberto = None
            continue

        par = _chave_da_linha(linha)
        if par is not None:
            campo, valor = par
            if atual is None:
                # Campos soltos antes de qualquer "CENA": vira a cena 1.
                atual = {"n": 1}
                cenas.append(atual)
            atual[campo] = valor
            campo_aberto = campo if campo == "narracao" else None
            continue

        if campo_aberto and atual is not None:
            # Continuacao de uma narracao que quebrou em varias linhas.
            atual[campo_aberto] = f"{atual.get(campo_aberto, '')} {linha}".strip()
        elif atual is None and not titulo:
            # Primeira linha util sem rotulo nenhum: e o titulo.
            titulo = linha.strip().strip('"')

    return {"titulo": titulo, "cta": cta, "cenas": cenas}


def _tempo(valor, padrao: float = 4.0) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    achado = re.search(r"(\d+(?:[.,]\d+)?)", str(valor or ""))
    return float(achado.group(1).replace(",", ".")) if achado else padrao


def parse(texto: str) -> dict:
    """Texto do LLM -> {titulo, cta, cenas:[{n, imagem, tempo, narracao}]}."""
    dados = _do_json(texto) or _dos_blocos(texto)
    cenas = []
    for i, bruta in enumerate(dados.get("cenas") or [], 1):
        narracao = " ".join(str(bruta.get("narracao") or "").split())
        imagem = " ".join(str(bruta.get("imagem") or "").split())
        if not narracao and not imagem:
            continue
        cenas.append({"n": int(bruta.get("n") or i),
                      "imagem": imagem,
                      "tempo": round(_tempo(bruta.get("tempo")), 2),
                      "narracao": narracao})
    for ordem, cena in enumerate(cenas, 1):
        cena["n"] = ordem
    return {"titulo": " ".join(str(dados.get("titulo") or "").split()),
            "cta": " ".join(str(dados.get("cta") or "").split()),
            "cenas": cenas}


def validar(roteiro: dict, config: dict | None = None):
    """(problemas, erros). Erro impede o video; problema so avisa."""
    if config is None:
        from .modelo import carregar_config
        config = carregar_config()
    limites = config["limites"]
    problemas = []
    erros = []
    cenas = roteiro.get("cenas") or []

    if not roteiro.get("titulo"):
        problemas.append("sem TITULO: vou usar a primeira narracao como titulo.")
    elif len(roteiro["titulo"]) > limites["titulo_max_chars"]:
        # ERRO, nao aviso: o YouTube corta em 100 caracteres (`youtube_web`
        # manda `titulo[:100]`), entao um titulo de 130 sobe truncado no meio
        # da frase — e o titulo e metade da decisao de clicar. Aconteceu com as
        # historias 4 (136) e 8 (130), as duas com o aviso impresso e ignorado.
        erros.append(
            f"titulo com {len(roteiro['titulo'])} chars (limite "
            f"{limites['titulo_max_chars']}): o YouTube corta em 100 e ele "
            "subiria pela metade. Peca ao LLM um titulo mais curto.")

    if len(cenas) < limites["cenas_min"]:
        erros.append(f"so {len(cenas)} cena(s); o minimo e {limites['cenas_min']}. "
                     "A resposta do LLM provavelmente veio cortada.")
    if len(cenas) > limites["cenas_max"]:
        problemas.append(f"{len(cenas)} cenas e muito para um vertical; "
                         f"considere cortar para {limites['cenas_max']}.")

    for cena in cenas:
        onde = f"cena {cena['n']}"
        if not cena["narracao"]:
            erros.append(f"{onde}: sem NARRACAO.")
        elif len(cena["narracao"]) > limites["narracao_max_chars"]:
            problemas.append(f"{onde}: narracao longa "
                             f"({len(cena['narracao'])} chars) - a cena vai esticar.")
        if not cena["imagem"]:
            erros.append(f"{onde}: sem IMAGEM (prompt).")
        elif len(cena["imagem"]) < limites["imagem_min_chars"]:
            problemas.append(f"{onde}: prompt de imagem curto "
                             f"({len(cena['imagem'])} chars) - a imagem sai generica.")
    return problemas, erros


def normalizar(dados: dict) -> dict:
    """Todo roteiro tem `partes`. Um video unico e uma serie de UMA parte.

    Uniformizar aqui e o que permite o resto da pipeline (imagens, plano,
    render, publicacao) ter um caminho so: nada precisa saber se a historia
    e curta ou uma serie de oito videos.
    """
    if not dados.get("partes"):
        dados["partes"] = [{"n": 1, "titulo": dados.get("titulo", ""),
                            "cliffhanger": "", "cta": dados.get("cta", ""),
                            "cenas": dados.get("cenas") or []}]
    for ordem, parte in enumerate(dados["partes"], 1):
        parte["n"] = ordem
        parte.setdefault("cenas", [])
        for indice, cena in enumerate(parte["cenas"], 1):
            cena["n"] = indice
    dados["serie"] = len(dados["partes"]) > 1
    dados["total_cenas"] = sum(len(p["cenas"]) for p in dados["partes"])
    return dados


def parte_de(roteiro: dict, numero: int) -> dict:
    for parte in roteiro.get("partes") or []:
        if int(parte["n"]) == int(numero):
            return parte
    raise KeyError(f"a historia nao tem a parte {numero}")


def titulo_da_parte(roteiro: dict, numero: int = 1) -> str:
    """O que vai na tela: na serie, o titulo da parte; senao, o da historia.

    Defensivo de proposito: e chamado durante a montagem do plano, e um
    roteiro sem `partes` (montado a mao, ou de um teste) nao pode derrubar o
    render por causa de um titulo.
    """
    base = roteiro.get("titulo") or ""
    try:
        parte = parte_de(roteiro, numero)
    except KeyError:
        return base
    if parte.get("titulo"):
        return parte["titulo"]
    return f"{base} (Parte {numero})" if roteiro.get("serie") else base


def salvar_serie(biblia: dict, partes: list, historia_id: str | None = None, *,
                 tema: str = "", provedor: str = "") -> Path:
    """Grava a serie inteira (biblia + partes) em roteiro.json.

    Chamado a CADA parte pronta: uma serie longa leva minutos e o disco tem
    que estar sempre um passo a frente do que pode dar errado.
    """
    historia_id = historia_id or proximo_id()
    pasta = OUTPUTS / historia_id
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {
        "historia_id": historia_id,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": "serie", "tema": tema, "provedor": provedor,
        "titulo": biblia.get("titulo") or "",
        "premissa": biblia.get("premissa") or "",
        # A descricao fisica do protagonista entra em TODA imagem de TODAS as
        # partes: e o que faz 80 imagens parecerem a mesma pessoa.
        "protagonista": biblia.get("protagonista") or "",
        "protagonista_nome": biblia.get("protagonista_nome") or "",
        "elenco": biblia.get("elenco") or "",
        "cenario": biblia.get("cenario") or "",
        # O gemeo factual do campo acima: os numeros e datas que a historia
        # fixou. Sem ele nao ha contra o que conferir a narracao depois.
        "fatos": biblia.get("fatos") or "",
        "cta": "",
        "partes": [dict(p) for p in partes],
    }
    normalizar(dados)
    with open(pasta / "roteiro.json", "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
    return pasta / "roteiro.json"


def proximo_id() -> str:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    existentes = [int(p.name.split("_")[1]) for p in OUTPUTS.glob("historia_*")
                  if p.name.split("_")[-1].isdigit()]
    return f"historia_{(max(existentes) + 1 if existentes else 1):05d}"


def salvar(roteiro: dict, historia_id: str | None = None, *,
           modelo: str = "", tema: str = "", bruto: str = "") -> Path:
    """Grava `outputs/<id>/roteiro.json` (e o texto original ao lado)."""
    historia_id = historia_id or proximo_id()
    pasta = OUTPUTS / historia_id
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {
        "historia_id": historia_id,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": modelo, "tema": tema,
        "titulo": roteiro.get("titulo") or "",
        "cta": roteiro.get("cta") or "",
        "cenas": roteiro.get("cenas") or [],
    }
    if not dados["titulo"] and dados["cenas"]:
        dados["titulo"] = dados["cenas"][0]["narracao"][:100]
    with open(pasta / "roteiro.json", "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
    if bruto:
        (pasta / "roteiro_bruto.txt").write_text(bruto, encoding="utf-8")
    return pasta / "roteiro.json"


def carregar(historia_id: str) -> dict:
    caminho = OUTPUTS / historia_id / "roteiro.json"
    with open(caminho, encoding="utf-8-sig") as fh:
        return normalizar(json.load(fh))


def listar():
    """Todas as historias, da mais nova para a mais velha."""
    saida = []
    if not OUTPUTS.is_dir():
        return saida
    for pasta in sorted(OUTPUTS.glob("historia_*"), reverse=True):
        caminho = pasta / "roteiro.json"
        if not caminho.is_file():
            continue
        try:
            with open(caminho, encoding="utf-8-sig") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            continue
        dados["pasta"] = str(pasta)
        saida.append(normalizar(dados))
    return saida
