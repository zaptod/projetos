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

import contextlib
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"

# QUANTAS VEZES A TROCA DO ARQUIVO E TENTADA quando o Windows a recusa
# (`PermissionError`: o painel, o postar ou um antivirus com o arquivo aberto
# para leitura). O mesmo numero do ledger (`metricas.reescrever_ledger`).
TENTATIVAS_DE_TROCA = 3


def _gravar_json_atomico(caminho, dados) -> Path:
    """Grava `dados` em `caminho` SEM nunca deixar meio arquivo no lugar dele.

    Auditoria de 11/10/2026 (HIS-1, critico): `roteiro.json` e `biblia.json`
    eram gravados com `open(..., "w")` direto no arquivo final, e o
    `roteiro.json` e regravado a CADA parte pronta. Um processo que morre no
    meio (queda de luz, a tarefa do Windows encerrada, um `json.dump` que
    levanta na metade) deixava o JSON truncado: `listar()` pulava a pasta
    calado (some do rodizio, das incompletas e do painel), `carregar`
    levantava e a queda de provedor tratava a historia como "nova" — e
    escrevia OUTRA biblia na mesma pasta, por cima das cenas da antiga.

    Agora: escreve num temporario ao lado (nome com pid e thread, para dois
    gravadores nunca dividirem o mesmo), `flush` + `fsync`, e so entao troca
    com `os.replace` — que no mesmo disco e atomico: quem le ve o arquivo
    velho inteiro ou o novo inteiro. `PermissionError` na troca (leitor com o
    arquivo aberto no Windows) espera um pouco e tenta de novo, ate
    `TENTATIVAS_DE_TROCA`; depois levanta, e o arquivo de antes fica intacto.
    O temporario nunca sobra.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(
        f"{caminho.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(temporario, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        for tentativa in range(TENTATIVAS_DE_TROCA):
            try:
                os.replace(temporario, caminho)
                break
            except PermissionError:
                if tentativa >= TENTATIVAS_DE_TROCA - 1:
                    raise
                time.sleep(0.2 * (tentativa + 1))
    finally:
        with contextlib.suppress(OSError):
            if temporario.exists():
                temporario.unlink()
    return caminho


# O ROTEIRO ILEGIVEL VAI AO DIARIO, uma vez por pasta e por dia (HIS-1). Sem
# isso a historia sumia de `listar()` sem rastro nenhum. A marca do dia mora
# em disco porque `listar()` roda em varios processos (agenda, postar,
# painel); o conjunto em memoria so poupa reler a marca no mesmo processo.
MARCA_DOS_ILEGIVEIS = "_roteiros_ilegiveis.json"
_ILEGIVEIS_AVISADOS: set = set()


def _avisar_ilegivel(pasta: Path, exc: BaseException) -> None:
    """Um `aviso` no diario (etapa `roteiro.ilegivel`). Nunca levanta."""
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
        chave = (str(pasta), hoje)
        if chave in _ILEGIVEIS_AVISADOS:
            return
        _ILEGIVEIS_AVISADOS.add(chave)
        marca = Path(pasta).parent / MARCA_DOS_ILEGIVEIS
        try:
            with open(marca, encoding="utf-8-sig") as fh:
                vistos = json.load(fh)
            if not isinstance(vistos, dict):
                vistos = {}
        except (OSError, ValueError):
            vistos = {}
        if vistos.get(Path(pasta).name) == hoje:
            return
        vistos = {k: v for k, v in vistos.items() if v == hoje}
        vistos[Path(pasta).name] = hoje
        with contextlib.suppress(Exception):
            _gravar_json_atomico(marca, vistos)
        from builds import atividade
        atividade.registrar(
            "estudio", "aviso",
            f"{Path(pasta).name}: o roteiro.json nao le "
            f"({type(exc).__name__}: {str(exc)[:120]}); a historia fica fora "
            "do rodizio, das incompletas e do painel ate o arquivo ser "
            "consertado", "historias", etapa="roteiro.ilegivel",
            ref=Path(pasta).name)
    except Exception:                                          # noqa: BLE001
        pass

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

        # O rotulo e casado SEM ACENTO ("TÍTULO", como o DeepSeek escreve), e
        # o valor sai da linha ORIGINAL, que e onde os acentos do texto estao.
        if not cenas:
            if LINHA_TITULO.match(_sem_acento(linha)):
                titulo = _valor_do_rotulo(linha).strip('"')
                campo_aberto = None
                continue

        if (LINHA_CTA.match(_sem_acento(linha))
                and _chave_da_linha(linha) is None):
            cta = _valor_do_rotulo(linha)
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


def _valor_do_rotulo(linha: str) -> str:
    """O que vem depois do primeiro `:` ou `-` de "ROTULO: valor"."""
    partes = re.split(r"\s*[:\-]\s*", linha, maxsplit=1)
    return (partes[1] if len(partes) > 1 else "").strip()


def _tempo(valor, padrao: float = 4.0) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    achado = re.search(r"(\d+(?:[.,]\d+)?)", str(valor or ""))
    return float(achado.group(1).replace(",", ".")) if achado else padrao


_ROTULO_FINAL = re.compile(r"^\s*\**\s*final\s*\**\s*[-–—:]\s*", re.IGNORECASE)


def sem_rotulo_final(texto: str) -> str:
    """Tira o "FINAL -" que o modelo copia do molde para o texto falado.

    14/09/2026: a narradora dizia "FINAL" na ultima cena das historias 9 e
    10. O molde da biblia pedia "CLIFFHANGER: FINAL - <...>" e o modelo
    levou o rotulo para o gancho e dali para a fala.
    """
    return _ROTULO_FINAL.sub("", str(texto or ""), count=1)


def parse(texto: str) -> dict:
    """Texto do LLM -> {titulo, cta, cenas:[{n, imagem, tempo, narracao}]}."""
    dados = _do_json(texto) or _dos_blocos(texto)
    cenas = []
    for i, bruta in enumerate(dados.get("cenas") or [], 1):
        narracao = sem_rotulo_final(
            " ".join(str(bruta.get("narracao") or "").split()))
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


TITULO_MAXIMO = 100

# O "Parte N" que o LLM escreve: com algarismo ou por extenso ("Vila Bela —
# Parte Um: O Forasteiro", achado do conferente em 05/10/2026). O `\b` depois
# da palavra e o que impede "Parte Umbigo" de virar "bigo".
_NUMERO_DA_PARTE = (r"(?:\s*\d+|\s+(?:um|uma|dois|duas|tr[eê]s|quatro|cinco"
                    r"|seis|sete|oito|nove|dez)\b)(?:\s*(?:/|de)\s*\d+)?")


def _caixa_normal(texto: str) -> str:
    """CAIXA ALTA INTEIRA vira capitalizacao normal; o resto fica como veio."""
    letras = [c for c in texto if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        return texto.capitalize()
    return texto


def limpar_titulo_de_parte(texto: str, *, caixa: bool = True) -> str:
    """Tira o que o LLM escreveu por conta propria e nao e titulo.

    Medido em 11/09/2026: a parte 3 da `historia_00005` foi ao ar como
    `PARTE 3 - A PASSAGEM E A TOALHA` — prefixo e caixa alta escritos pelo
    modelo e aceitos crus, enquanto as outras cinco partes da MESMA serie
    saiam como `O Recibo da Ruina (Parte 4)`. Seis videos da mesma historia
    com seis formatos de titulo diferentes.

    O numero da parte sai daqui porque quem o escreve e `titulo_da_parte`,
    sempre do mesmo jeito, e nao o modelo.

    `caixa=False` deixa a CAIXA ALTA como veio: numa serie, `titulo_da_parte`
    so normaliza DEPOIS de cortar a marca (05/10/2026: normalizar antes fazia
    `AS TRÊS COMPORTAS — A CHEIA` virar `As Três Comportas — a cheia`).
    """
    limpo = " ".join(str(texto or "").split())
    # "Parte 1: ...", "Parte 1/6 - ...", e "Parte 1" sozinho (05/10/2026: o
    # `As Três Comportas — Parte 1` sobrava assim depois de tirar a marca).
    limpo = re.sub(r"^\s*parte" + _NUMERO_DA_PARTE + r"\s*(?:[-–—:.]\s*|$)",
                   "", limpo, flags=re.I)
    limpo = re.sub(r"\s*[\(\[]\s*parte" + _NUMERO_DA_PARTE
                   + r"\s*[\)\]]\s*$", "", limpo, flags=re.I)
    # " - Parte 1", ": Parte 1" e a virgula colada (`Vila Bela, Parte 1`,
    # 05/10/2026), que nao tem espaco antes.
    limpo = re.sub(r"(?:\s+[-–—:,]|\s*[,–—:])\s*parte" + _NUMERO_DA_PARTE
                   + r"\s*$", "", limpo, flags=re.I)
    # CAIXA ALTA INTEIRA vira capitalizacao normal. Em titulo de video ela le
    # como grito, e so uma das seis partes vinha assim.
    if caixa:
        limpo = _caixa_normal(limpo)
    return limpo.strip(" -–—:")


def nome_da_serie(roteiro: dict) -> str:
    """A marca curta que liga as partes. `""` quando a historia nao tem."""
    return " ".join(str(roteiro.get("serie_nome") or "").split())


_ARTIGOS = {"o", "a", "os", "as", "um", "uma"}
# Entre a marca e o resto: travessao, meia-risca ou hifen COM espaco (o de
# "Alto-Falante" nao separa nada), ou dois-pontos.
_SEPARADOR_DA_MARCA = re.compile(r"\s+[—–-]\s+|\s*[—–]\s*|\s*:\s*")


def _comparavel(texto: str) -> str:
    """Sem acento, sem caixa, sem pontuacao e sem o artigo do comeco."""
    sem = unicodedata.normalize("NFKD", str(texto or ""))
    sem = "".join(c for c in sem if not unicodedata.combining(c))
    palavras = re.sub(r"[^\w]+", " ", sem.lower()).split()
    if len(palavras) > 1 and palavras[0] in _ARTIGOS:
        palavras = palavras[1:]
    return " ".join(palavras)


def _sem_a_marca(proprio: str, marca: str) -> str:
    """O titulo da parte sem a marca da serie que o LLM pos nele.

    Medido em 05/10/2026: 30 de 294 titulos do catalogo saiam com a serie
    duas vezes (`Rua das Acácias — Rua das Acácias — As 22 Pastas`,
    `Bom Dia, Vizinhos — Bom Dia, Vizinhos`, `As Três Comportas — As Três
    Comportas — Parte 1: A Represa Aguenta (Parte 1/6)`). Tira a marca do
    comeco (seguida de separador) e o "Parte N" que vier depois; se o que
    sobra e a propria marca, devolve "" e quem chama usa so a marca.
    """
    alvo = _comparavel(marca)
    if not alvo:
        return proprio
    for _ in range(3):                  # "Marca — Parte 1: Marca — X" e raro
        if _comparavel(proprio) == alvo:
            return ""
        cortado = proprio
        for sep in _SEPARADOR_DA_MARCA.finditer(proprio):
            if _comparavel(proprio[:sep.start()]) == alvo:
                cortado = limpar_titulo_de_parte(proprio[sep.end():],
                                                 caixa=False)
                break
        if cortado == proprio:
            break
        proprio = cortado
    return proprio


def _marca_dentro(proprio: str, marca: str) -> bool:
    """A marca da serie aparece, palavra por palavra, no titulo da parte?

    Mesma comparacao de `_sem_a_marca` (sem acento, caixa, pontuacao e artigo
    do comeco), em qualquer lugar do titulo e com borda de palavra: `Rua
    Sete` casa com `A Noite em que a Rua Sete Entendeu`, `Rua Setembro` nao.
    """
    alvo = _comparavel(marca)
    return bool(alvo) and f" {alvo} " in f" {_comparavel(proprio)} "


def titulo_da_parte(roteiro: dict, numero: int = 1) -> str:
    """O que vai na tela e no YouTube.

    O TITULO PRECISA DIZER QUE HA MAIS. Ate 11/09/2026 ele era so o titulo da
    parte, cru: `O limite do desespero`, `O Trofeu de Aluguel`,
    `PARTE 3 - A PASSAGEM E A TOALHA`. Sao tres partes da MESMA serie, e quem
    assistiu uma nao tinha como descobrir que existiam as outras — nem pelo
    titulo, nem pela ordem, nem por nada. A identidade da serie so existia na
    DESCRICAO, que ninguem abre num Short.

    Defensivo de proposito: e chamado durante a montagem do plano, e um
    roteiro sem `partes` (montado a mao, ou de um teste) nao pode derrubar o
    render por causa de um titulo.
    """
    base = roteiro.get("titulo") or ""
    try:
        parte = parte_de(roteiro, numero)
    except KeyError:
        return base
    total = len(roteiro.get("partes") or []) or roteiro.get("partes_esperadas")
    serie = bool(roteiro.get("serie"))
    proprio = limpar_titulo_de_parte(parte.get("titulo") or "", caixa=not serie)
    if not serie:
        return proprio or base

    marca = nome_da_serie(roteiro)
    # UM marcador de parte so, o "(Parte n/N)" do fim, e a marca uma vez so:
    # o LLM escreve o titulo da parte ja com a serie e o "Parte N:" na frente
    # (05/10/2026, 30 de 294 titulos — ver `_sem_a_marca`).
    cortado = _sem_a_marca(proprio, marca)
    # A CAIXA DEPOIS DO CORTE, e o resto comeca com maiuscula (05/10/2026):
    # `Vila Bela: o forasteiro` sobrava `o forasteiro`, que no titulo virava
    # `Vila Bela — o forasteiro`. Sem corte, o titulo fica como o LLM o fez.
    houve_corte = cortado != proprio
    proprio = _caixa_normal(cortado).strip(" -–—:")
    if houve_corte and proprio:
        proprio = proprio[0].upper() + proprio[1:]
    ordem = f"Parte {numero}" + (f"/{total}" if total else "")
    # A MARCA NO MEIO SAI DA FRENTE (decisao `historias/titulo-marca-no-meio`
    # = "Tirar a marca da frente", 06/10/2026): quando o titulo da parte ja
    # traz o nome da serie no meio, a marca na frente o repetia
    # (`TÚMULO 214 — A Mulher do Túmulo 214 (Parte 1/5)`, 5 de 312 partes de
    # serie medidas em 06/10). Fica `A Mulher do Túmulo 214 (Parte 1/5)`; o
    # "(Parte n/N)" do fim continua sendo o unico marcador de parte.
    if marca and proprio and _marca_dentro(proprio, marca):
        marca = ""
    # A marca vem PRIMEIRO: e ela que se repete, e o olho a encontra no fim
    # de uma fileira de miniaturas. O titulo da parte vem depois, porque e o
    # que muda.
    pedacos = [p for p in (marca, proprio) if p]
    titulo = " — ".join(pedacos) if pedacos else base
    titulo = f"{titulo} ({ordem})" if titulo else f"{base} ({ordem})"
    if len(titulo) > TITULO_MAXIMO:
        # O que cede e o titulo da parte, nunca a marca nem a ordem: sem elas
        # o video volta a parecer solto, que e o defeito que isto conserta.
        folga = TITULO_MAXIMO - len(marca) - len(ordem) - 8
        curto = proprio[:max(0, folga)].rstrip(" ,;–—-")
        titulo = " — ".join(p for p in (marca, curto) if p) + f" ({ordem})"
    return titulo


# A RECUSA DO LLM NO LUGAR DO TEXTO (05/10/2026). A `historia_00059` p06 tinha
# como titulo "Não consigo te ajudar com isso. Sou só um modelo de linguagem
# e não tenho capacidade de entender e responder a essa questão." — a retomada
# das 09:06 voltou com a recusa, o parser a leu como titulo e as cenas vieram
# da continuacao. O catalogo listava "Vila Bela — Não consigo te ajudar...
# (Parte 6/6)", e a capa e o mp4 traziam a frase. Medido no acervo inteiro
# com `e_recusa_enlatada`: 1 titulo em 294 partes, 0 narracoes em 4110 cenas.
TITULO_RECUSADO = "o titulo da parte e uma recusa do LLM"

# O DETECTOR DE TRECHO (06/10/2026). `llm.texto.e_recusa_enlatada` foi feito
# para a RESPOSTA INTEIRA do LLM (frase curta + lista de frases) e, aplicado a
# cada narracao, marcava fala de personagem: "Eu fui criado pela minha avo em
# Vila Bela.", "— Nao consigo ajudar voce, Clara — disse ele", "Nao tenho
# como te ajudar agora, filho." (achados do conferente). Narracao marcada vira
# erro "roteiro:" sem conserto — parte barrada para sempre — e, na geracao,
# `RecusaEnlatada` = reescrita. Sao duas perguntas, com custos opostos, e o
# corpus fixo delas mora em `tests/dados/recusa_no_trecho_corpus.json`.
#
# TITULO (`titulo=True`): UNIAO PURA, SEM EXCECAO NENHUMA (decisao do
# coordenador, 06/10/2026, depois de quatro rodadas do conferente):
#     e_recusa_enlatada(texto)  OU  _novo_no_titulo(texto)
# Falso positivo no titulo so troca o titulo pelo do plano (custa pouco, e o
# acervo tem 0); falso negativo leva a recusa ao ar. Toda excecao posta no
# ramo da producao deixou recusa real passar ("Como disse antes, nao posso
# ajudar com isso.", "Ola, Adrian, nao posso ajudar com isso.", 124 em Title
# Case). O NOVO soma o que a producao nao pega: a identidade + uma negativa,
# ou a 1a frase do titulo (depois da marca, de "Parte N:", de interjeicao e de
# enfeite — "**", emoji) ser uma recusa COMPLETA, ancorada no comeco e no fim
# dela ("Peco desculpas, mas nao posso escrever isso.", "I cannot create
# content that depicts violence.").
#
# NARRACAO (`titulo=False`): ALTA PRECISAO — o custo do falso positivo e a
# parte barrada, e o caminho real da recusa (a resposta inteira) ja e pego
# pelo `gerar._perguntar_sem_recusa` com o detector antigo. Nao consulta a
# producao. Marca so a recusa DIRIGIDA A QUEM PEDIU, com as duas coisas:
#   - a IDENTIDADE de assistente em 1a pessoa, numa frase que nao e pergunta
#     ("sou (so) um modelo de linguagem", "sou uma IA", "Como uma IA, ...",
#     "sou o Gemini"; sem "claude", que e nome de gente); "nao sou uma IA"
#     nunca conta;
#   - e a RECUSA DO PEDIDO: "nao posso/consigo ajudar com isso / esse pedido /
#     esse conteudo", "alem das minhas capacidades", "can't help with that".
# As EXCECOES moram so aqui: FALA (travessao, aspas, verbo de fala na 3a
# pessoa — "como (eu|ja) disse", "o que disse", "as I (have) said" sao o
# proprio assistente), VOCATIVO (", Pedro,", "Doutor, ...") — que a identidade
# de LLM vence ("Sinto muito, Adrian. Sou apenas um modelo de linguagem e nao
# posso ajudar com isso.") — e o teto de 300 caracteres.
_IA = (r"(?:modelo(?:s)? de linguagem(?: grande)?|"
       r"modelo(?:s)? de (?:ia|inteligencia artificial)|"
       r"ia (?:com )?base(?:ada)? em texto|ia de (?:texto|linguagem)|"
       r"ia|inteligencia artificial|chatbot|"
       r"assistente (?:de|com) (?:ia|inteligencia artificial)|"
       r"programa de computador)")
# So o que e LLM, sem ambiguidade: e o que vence o vocativo na narracao.
_IA_LLM = (r"(?:modelo(?:s)? de linguagem(?: grande)?|"
           r"modelo(?:s)? de (?:ia|inteligencia artificial)|"
           r"ia (?:com )?base(?:ada)? em texto|ia de (?:texto|linguagem))")
_IA_EN = (r"(?:ai|a\.i\.|language model|large language model|"
          r"ai language model|text-based ai|chatbot|ai assistant|assistant)")
_IA_EN_LLM = (r"(?:language model|large language model|ai language model|"
              r"text-based ai)")
# Sem "claude": e nome de gente ("Eu sou o Claude que ela abandonou").
_PROVEDORES = r"(?:gemini|chatgpt|deepseek|grok|bard|copilot|gpt-?\d)"
_NAO_ANTES = r"(?<!nao )(?<!nunca )(?<!nem )"
_INTERJEICAO = (r"(?:(?:ola|oi|hmm+|hum+|ok|okay|certo|bem|entendo|entendi|"
                r"ah|olha|hello|hi)\b[!.,\s]*)*")
_DESCULPA = (r"(?:(?:desculpe|desculpa|me desculpe|peco desculpas|"
             r"pedimos desculpas|perdao|sinto muito|lamento|infelizmente|"
             r"ainda estou aprendendo(?: sobre isso)?|i'?m sorry|i am sorry|"
             r"sorry|unfortunately|i apologize)"
             r"[,.!]?\s+(?:(?:e|mas|but)\s+)?)*")


def _padroes_de_identidade(ia: str, ia_en: str) -> tuple:
    return tuple(re.compile(p) for p in (
        _NAO_ANTES + r"\bsou (?:apenas |so |somente |simplesmente |mais |o |"
                     r"a )?(?:um |uma )?(?:mero |mera )?" + ia + r"\b",
        # "Como uma IA, nao posso..." (tambem depois de "Desculpe, mas");
        # "Como um modelo de IA poderia saber?" nao (sem virgula; pergunta).
        r"^" + _DESCULPA + r"como (?:um |uma )?" + ia + r"\s*,",
        _NAO_ANTES + r"\bsou o " + _PROVEDORES + r"\b",
        r"\b" + _PROVEDORES + r", (?:um|uma) (?:modelo|ia|assistente)\b",
        r"\b(?:i'?m|i am) (?:just |only |simply )?(?:an? )?" + ia_en + r"\b",
        r"^as an? " + ia_en + r"\b",
    ))


_IDENTIDADE = _padroes_de_identidade(_IA, _IA_EN) + tuple(
    re.compile(p) for p in (
        r"\bfui (?:criad|programad|treinad|projetad|desenvolvid)[oa] "
        r"(?:apenas |somente |so |unicamente )?para (?:processar|gerar|"
        r"entender)(?: e (?:processar|gerar|entender))? (?:texto|conteudo|"
        r"respostas)\b",
        r"\bso (?:consigo|posso|sei) (?:processar e )?gerar texto\b",
    ))
_IDENTIDADE_DE_LLM = _padroes_de_identidade(_IA_LLM, _IA_EN_LLM)
_OBJETO_DO_PEDIDO = (r"(?:com |em |a |para )?(?:isso|isto|nisso|nisto|"
                     r"(?:esse|essa|este|esta|o seu|a sua|seu|sua) "
                     r"(?:pedido|solicitacao|conteudo|questao|pergunta|tarefa|"
                     r"material|tipo de \w+))\b")
_RECUSA_DIRIGIDA = re.compile(
    r"\bnao (?:posso|consigo|sou capaz de|tenho como) (?:te |lhe |o |a |voce )?"
    r"(?:ajudar|auxiliar|atender|responder|gerar|criar|produzir|escrever|"
    r"fornecer|cumprir)(?: voce)? " + _OBJETO_DO_PEDIDO +
    # "Gemini nao pode ajudar com isso." (o assistente pelo proprio nome)
    r"|\b" + _PROVEDORES + r" nao (?:pode|consegue) (?:te |lhe )?"
    r"(?:ajudar|auxiliar|atender|responder|gerar|criar|produzir|escrever)"
    r"(?: voce)? " + _OBJETO_DO_PEDIDO +
    r"|\b(?:alem|fora) d[ao]s? minhas? (?:capacidades|habilidades|habiliades|"
    r"funcoes)"
    r"|\bnao tenho (?:a )?capacidade de (?:entender|processar|responder|"
    r"ajudar|gerar|ver|assistir)"
    r"|\bnao fui (?:programad|criad|treinad|projetad)[oa] para (?:fazer )?"
    r"(?:isso|essas coisas|esse tipo)"
    r"|\bnao consegui entender o que voce (?:esta )?pedi"
    r"|\b(?:can'?t|cannot|unable to) (?:help|assist)(?: you)? with "
    r"(?:that|this|your request)"
    r"|\boutside (?:of )?my capabilities|\bbeyond my capabilities")
# No titulo a identidade basta com uma negativa mais larga: a frase de
# assistente ("nao tenho opinioes pessoais", "treinado pelo Google").
_NEGATIVA_DE_ASSISTENTE = re.compile(
    _RECUSA_DIRIGIDA.pattern +
    r"|\bnao (?:posso|consigo|sou capaz de|tenho como) (?:te |lhe |o |a )?"
    r"(?:ajudar|auxiliar|atender|responder|gerar|criar|produzir|escrever)"
    r"|\bnao tenho (?:opinioes|opiniao|sentimentos|emocoes|crencas|"
    r"preferencias)\b"
    r"|\b(?:treinad|desenvolvid|criad)[oa] (?:pelo|pela) (?:google|openai|"
    r"deepseek|anthropic|meta|xai)\b"
    r"|\bcan'?t (?:help|assist)|\bcannot (?:help|assist|fulfill)"
    r"|\bunable to (?:help|assist)|\btrained by (?:google|openai)\b")
# Fala de personagem (so na narracao): travessao, aspas ou verbo de fala na
# 3a pessoa. "Como eu disse", "como ja te disse", "como disse antes", "o que
# disse", "conforme disse" e "as I (have|already) said" sao o proprio
# assistente (conferente7 e conferente8).
_MARCAS_DE_FALA = ("—", "–", "\"", "“", "”", "«",
                   "»")
_VERBO_DE_FALA = re.compile(
    r"\b(?:(?<!eu )(?<!te )(?<!ja )(?<!lhe )(?<!me )(?<!como )(?<!que )"
    r"(?<!conforme )disse|"
    r"diz(?! respeito)|dizia(?! respeito)|dizendo|falou|falava|"
    r"respondeu|responde|respondia|perguntou|perguntava|brincou|brincava|"
    r"riu|ria|rindo|imitando|imitou|imitava|repetia|repetiu|repete|gritou|"
    r"gritava|debochou|zombou|jurou|jura|sussurrou|murmurou|explicou|"
    r"contou|retrucou|rebateu|completou|(?<!i )(?<!i've )(?<!have )"
    r"(?<!already )(?<!as )said|says|asked|replied|laughed|joked)\b")
# Vocativo (so na narracao): quem fala chama alguem pelo nome ou parentesco.
_VOCATIVOS = (r"(?:filho|filha|filhinho|filhinha|mae|pai|irmao|irma|vo|vovo|"
              r"avo|amor|querido|querida|tia|tio|mano|mana|moca|moco|senhora|"
              r"senhor|cara|doutor|doutora|dr|dra|delegado|delegada|"
              r"professor|professora|chefe|patrao|patroa|menina|menino|"
              r"garoto|garota|benzinho|bebe|meu bem|meu amor|minha filha|"
              r"meu filho)")
_VOCATIVO_DA_LISTA = re.compile(
    r"(?:^(?:(?:desculpe|desculpa|me desculpe|sinto muito|lamento|perdao|"
    r"infelizmente)[,.!]?\s+)?|,\s*)(?:meu |minha )?" + _VOCATIVOS
    + r"\s*(?=[,.!?]|$)")
# Nome proprio entre virgulas ou no fim: ", Rafael", ", Dona Cida,". So no
# texto com a caixa original; as palavras da propria recusa nao contam.
_NOME_VOCATIVO = re.compile(
    r",\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*(?=[,.!?]|$)")
_NAO_SAO_NOME = {"nao", "mas", "eu", "posso", "consigo", "sou", "isso", "com",
                 "ajudar", "desculpe", "infelizmente", "lamento", "sinto",
                 "muito", "apenas", "so", "um", "uma", "e", "o", "a", "ela",
                 "ele", "voltou", "parte", "google", "openai", "but", "i",
                 "sorry", "me", "te", "the", "that", "this"}

# A frase de recusa (modo titulo, pergunta nova).
_NOME_DO_PEDIDO = (r"(?:conteudo|conteudos|video|videos|imagem|imagens|texto|"
                   r"textos|pedido|pedidos|solicitacao|material|cena|cenas|"
                   r"historia|historias)")
_OBJETO_TITULO = (
    r"(?:com |em |a |para )?(?:isso|isto|nisso|nisto|"
    r"(?:esse|essa|este|esta|o seu|a sua|seu|sua) (?:pedido|solicitacao|"
    r"conteudo|tarefa|material|historia|cena|texto|parte|continuacao|"
    r"narrativa|tipo de " + _NOME_DO_PEDIDO + r")"
    r"|conteudos? (?:que|onde) (?:envolva|envolvam|contenha|contenham|"
    r"inclua|incluam|retrate|retratem|mostre|mostrem|descreva|descrevam|"
    r"promova|promovam|incentive|incentivem)[^.!?]*)")
_VERBO_DE_RECUSA = (r"(?:ajudar|auxiliar|atender|gerar|criar|produzir|"
                    r"escrever|fornecer|cumprir|continuar)")
_OBJETO_EN = (r"(?:that|this|it|your request|that request|this request|"
              r"(?:this|that) (?:story|scene|content|text|request)|"
              r"content (?:that|which) [^.!?]*)")
_NUCLEO_DA_RECUSA = (
    r"(?:(?:eu )?nao (?:posso|consigo|sou capaz de|tenho como|"
    r"estou autorizad[oa] a|tenho permissao para) (?:te |lhe |o |a |voce )?"
    r"(?:" + _VERBO_DE_RECUSA + r"(?: voce)? " + _OBJETO_TITULO
    # "fazer isso" so com o ponto: "Desculpe, mas eu nao posso fazer isso"
    # sem ponto e titulo de gente; "Desculpe, nao posso fazer isso." e recusa.
    + r"|fazer (?:isso|isto)(?=[.!]))"
    # "Desculpe, ChatGPT nao pode ajudar com isso." (pelo proprio nome)
    r"|" + _PROVEDORES + r" nao (?:pode|consegue) (?:te |lhe |o |a |voce )?"
    + _VERBO_DE_RECUSA + r"(?: voce)? " + _OBJETO_TITULO +
    r"|nao e possivel " + _VERBO_DE_RECUSA + r" " + _OBJETO_TITULO +
    r"|nao me sinto confortavel (?:em |para |a )?" + _VERBO_DE_RECUSA + r" "
    + _OBJETO_TITULO +
    r"|(?:esse|este) tipo de " + _NOME_DO_PEDIDO
    + r" nao pode ser (?:gerado|gerada|criado|criada|produzido|produzida|"
    r"escrito|escrita|feito|feita)"
    r"|i(?: can'?t| cannot| can not|'m unable to| am unable to|"
    r"'m not able to| am not able to| won'?t be able to| won'?t) "
    r"(?:(?:help|assist)(?: you)?(?: with)? " + _OBJETO_EN +
    r"|(?:fulfill|comply with|create|generate|provide|do|write|continue|"
    r"continue with) " + _OBJETO_EN + r"))")
# "Desculpe, nao posso continuar." / "Sorry, I can't continue.": sem objeto,
# so com a desculpa na frente ("Nao Posso Continuar" e titulo de gente).
_DESCULPA_OBRIGATORIA = (r"(?:(?:desculpe|desculpa|me desculpe|peco desculpas|"
                         r"perdao|sinto muito|lamento|infelizmente|i'?m sorry|"
                         r"i am sorry|sorry|unfortunately)[,.!]?\s+"
                         r"(?:(?:e|mas|but)\s+)?)+")
_CONTINUAR_SEM_OBJETO = (r"(?:(?:eu )?nao (?:posso|consigo) continuar|"
                         r"i(?: can'?t| cannot|'m unable to| am unable to) "
                         r"continue)")
_JUSTIFICATIVA = (r"(?:,\s*|\s+)(?:pois|porque|ja que|uma vez que|since|"
                  r"because|as) [^.!?]*\b(?:diretrizes|politicas?|conteudo|"
                  r"violencia|viola|seguranca|inadequad\w*|impropri\w*|"
                  r"apropriad\w*|ofensiv\w*|nociv\w*|prejudicia\w*|sexual|"
                  r"odio|guidelines|polic\w*|harmful|violen\w*|"
                  r"explicit\w*)[^.!?]*")
# "Como (eu) disse antes, ...", "As I've said, ...": o assistente se repete.
_ABERTURA_DO_ASSISTENTE = (
    r"(?:(?:como (?:eu )?(?:ja )?(?:te )?(?:disse|expliquei|mencionei|falei)"
    r"|conforme (?:eu )?(?:ja )?disse|repito o que disse|repito"
    r"|as i(?:'ve| have| already)? (?:said|mentioned)|as said)"
    r"(?: antes| anteriormente| before)?[,:]?\s+)?")
# "Desculpe, Adrian, mas ..." / "Sorry, Adrian, ...": no titulo o nome de
# quem pediu nao livra a recusa (decisao de 06/10: titulo nao tem excecao).
_NOME_APOS_DESCULPA = r"(?:[^\W\d_]+,\s+(?:(?:e|mas|but)\s+)?)?"
_FECHO_DE_DESCULPA = (r"(?:,\s*(?:infelizmente|desculpe|desculpa|sorry|"
                      r"lamento|sinto muito))?")
_FRASE_DE_RECUSA = re.compile(
    r"^" + _INTERJEICAO + _ABERTURA_DO_ASSISTENTE + r"(?:" + _DESCULPA
    + _NOME_APOS_DESCULPA + _NUCLEO_DA_RECUSA
    + r"(?:" + _JUSTIFICATIVA + r")?" + _FECHO_DE_DESCULPA + r"|"
    + _DESCULPA_OBRIGATORIA + _CONTINUAR_SEM_OBJETO + r")[.!]*$")
# Recusa e frase curta; acima disto a narracao e texto de historia.
RECUSA_NO_TRECHO_MAXIMO = 300


def _sem_enfeite(texto) -> str:
    """Tira markdown ("**", "_", "#", "`") e emoji/simbolo; mantem a caixa."""
    sem = "".join(c for c in str(texto or "")
                  if c not in "*_#`~" and unicodedata.category(c)
                  not in ("So", "Cs", "Co"))
    sem = sem.replace("️", "").replace("‍", "")
    return " ".join(sem.split())


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in base if not unicodedata.combining(c))


def _trecho_comparavel(texto) -> str:
    """Sem enfeite, caixa baixa, sem acento, aspas retas e espaco unico."""
    sem = _sem_acento(_sem_enfeite(texto))
    sem = sem.replace("’", "'").replace("‘", "'")
    return " ".join(sem.lower().split())


def _frases_afirmativas(limpo: str) -> list[str]:
    """As frases do trecho que nao sao pergunta ("Sou uma IA? Nao.")."""
    return [f.strip() for f in re.findall(r"[^.!?]+[.!?]*", limpo)
            if f.strip() and not f.strip().endswith("?")]


def _tem_identidade(limpo: str, padroes=None) -> bool:
    return any(m.search(frase) for frase in _frases_afirmativas(limpo)
               for m in (padroes or _IDENTIDADE))


def _tem_vocativo(texto: str) -> bool:
    """O trecho chama alguem: ", filho", "Doutor, ...", ", Dona Cida,"."""
    limpo = _trecho_comparavel(texto)
    if _VOCATIVO_DA_LISTA.search(limpo):
        return True
    caixa = _sem_acento(_sem_enfeite(texto))
    for achado in _NOME_VOCATIVO.finditer(caixa):
        palavras = achado.group(1).lower().split()
        if not any(p in _NAO_SAO_NOME for p in palavras):
            return True
    return False


def _frase_de_recusa_inteira(limpo: str) -> bool:
    """A 1a frase do titulo (ou do que vem depois da marca) E uma recusa
    completa? (ancorada no comeco e no fim DELA; o que vem depois nao importa:
    "Desculpe, nao posso gerar esse conteudo. Ele viola as politicas.")"""
    candidatos = [limpo] + re.split(r"\s[—–-]\s|:\s", limpo)[1:]
    for candidato in candidatos:
        frases = [f.strip() for f in re.findall(r"[^.!?]+[.!?]*",
                                                  candidato.strip())]
        # "Hmm..." e "Ola!" sao frases soltas antes da recusa.
        while frases and re.fullmatch(_INTERJEICAO, frases[0]):
            frases.pop(0)
        # `search` de proposito: quem ancora sao o ^ e o $ da expressao.
        if frases and _FRASE_DE_RECUSA.search(frases[0]):
            return True
    return False


def _novo_no_titulo(texto) -> bool:
    """O que a producao nao pega. Sem excecao: titulo nao tem."""
    limpo = _trecho_comparavel(texto)
    if not limpo:
        return False
    if _frase_de_recusa_inteira(limpo):
        return True
    return _tem_identidade(limpo) and bool(_NEGATIVA_DE_ASSISTENTE.search(limpo))


def _titulo_e_recusa(texto) -> bool:
    """Modo titulo = PRODUCAO OU NOVO, uniao pura (decisao de 06/10/2026)."""
    from ..llm.texto import e_recusa_enlatada
    return bool(e_recusa_enlatada(texto)) or _novo_no_titulo(texto)


def _narracao_e_recusa(texto) -> bool:
    limpo = _trecho_comparavel(texto)
    if not limpo or len(limpo) > RECUSA_NO_TRECHO_MAXIMO:
        return False
    if _VERBO_DE_FALA.search(limpo):
        return False
    if any(m in limpo for m in _MARCAS_DE_FALA):
        return False
    if _tem_vocativo(texto) and not _tem_identidade(limpo,
                                                    _IDENTIDADE_DE_LLM):
        return False
    return _tem_identidade(limpo) and bool(_RECUSA_DIRIGIDA.search(limpo))


def e_recusa_no_trecho(texto, *, titulo: bool = False) -> bool:
    """O titulo (`titulo=True`) ou a narracao e a recusa de um assistente?

    A pergunta de TRECHO; a da resposta inteira continua sendo
    `llm.texto.e_recusa_enlatada`, sem mudanca. Ver as regras acima e o
    corpus `tests/dados/recusa_no_trecho_corpus.json`.
    """
    if not str(texto or "").strip():
        return False
    return _titulo_e_recusa(texto) if titulo else _narracao_e_recusa(texto)


def recusa_no_titulo(roteiro: dict, numero: int) -> str:
    """O titulo cru da parte, se ele e a recusa do LLM; senao `""`."""
    try:
        titulo = str(parte_de(roteiro, numero).get("titulo") or "")
    except (KeyError, TypeError, ValueError, AttributeError):
        return ""
    return titulo if e_recusa_no_trecho(titulo, titulo=True) else ""


def cenas_recusadas(cenas) -> list[int]:
    """Os numeros das cenas cuja narracao e a recusa do LLM."""
    return [int(c.get("n") or i) for i, c in enumerate(cenas or [], 1)
            if isinstance(c, dict) and e_recusa_no_trecho(c.get("narracao"))]


def cenas_com_recusa(roteiro: dict, numero: int) -> list[int]:
    """As cenas DESTA parte cuja narracao e a recusa enlatada."""
    try:
        cenas = parte_de(roteiro, numero).get("cenas")
    except (KeyError, TypeError, ValueError, AttributeError):
        return []
    return cenas_recusadas(cenas)


def titulo_do_plano(historia_id: str, numero: int) -> str:
    """O titulo que a biblia planejou para a parte, se nao for recusa.

    E o que entra no lugar do titulo recusado (reparo): foi o mesmo LLM que
    o escreveu, na biblia, para esta parte. `""` (so a marca) sem biblia.
    """
    try:
        with open(OUTPUTS / historia_id / "biblia.json",
                  encoding="utf-8-sig") as fh:
            biblia = json.load(fh)
        plano = next((p for p in biblia.get("partes") or []
                      if int(p.get("n") or 0) == int(numero)), {})
    except (OSError, ValueError, TypeError, AttributeError):
        return ""
    titulo = str(plano.get("titulo") or "").strip()
    return "" if e_recusa_no_trecho(titulo, titulo=True) else titulo


def salvar_serie(biblia: dict, partes: list, historia_id: str | None = None, *,
                 tema: str = "", provedor: str = "",
                 estrutura: str = "", modelo_llm: str = "",
                 ganchos: list | None = None, narrador: str = "",
                 quedas: list | None = None, tipo: str = "") -> Path:
    """Grava a serie inteira (biblia + partes) em roteiro.json.

    Chamado a CADA parte pronta: uma serie longa leva minutos e o disco tem
    que estar sempre um passo a frente do que pode dar errado.

    `quedas` (provedores que falharam e quem assumiu) e ACUMULADO: sem
    `quedas`, o que ja estava gravado continua — a regravacao de cada parte
    nao pode apagar a historia de quem tentou escrever.
    """
    historia_id = historia_id or proximo_id()
    pasta = OUTPUTS / historia_id
    pasta.mkdir(parents=True, exist_ok=True)
    if quedas is None:
        quedas = []
        try:
            with open(pasta / "roteiro.json", encoding="utf-8-sig") as fh:
                quedas = list(json.load(fh).get("quedas") or [])
        except (OSError, ValueError, AttributeError):
            quedas = []
    dados = {
        "historia_id": historia_id,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": "serie", "tema": tema, "provedor": provedor,
        # O molde usado. Guardado para o RODIZIO ter memoria: sem ele a
        # escolha do proximo viraria sorteio, e sorteio repete.
        "estrutura": estrutura,
        # O TIPO (favela, normal, babaca): a fila de postagem alterna por
        # ele, e a criacao escolhe o tipo com menos estoque.
        "tipo": tipo or biblia.get("tipo") or "",
        # AS ALAVANCAS, PELO NOME, e quem narrou. Pelo mesmo motivo do molde:
        # sem memoria nao ha rodizio. Ate 09/09/2026 elas so existiam em
        # `biblia.json`, que `listar()` nao le — e o resultado foi cinco
        # historias seguidas com o MESMO par.
        #
        # Guardar o NOME normalizado, e nao a string livre que o LLM devolve,
        # porque a string varia: `TRAICAO` e `TRAIÇÃO` ja aparecem as duas no
        # disco, e nenhum rodizio casa com isso.
        # QUANTAS PARTES A BIBLIA PLANEJOU — nao quantas foram escritas.
        # Sem este numero o roteiro nao sabe que esta pela metade: em
        # 10/09/2026 as 06:15 o Gemini bateu no limite de uso no meio da parte
        # 3 e a `historia_00005` ficou com 2 de 6. Como `incompletas()` so
        # olha as partes que EXISTEM, ela seria "terminada" como uma serie de
        # duas partes — 28 imagens, 2 videos, publicada — e quem assistisse a
        # parte 2 nunca receberia a 3. E o pior resultado possivel, pior que
        # qualquer atraso.
        "partes_esperadas": int(biblia.get("partes_esperadas")
                                or len(biblia.get("partes") or [])
                                or len(partes)),
        "ganchos": [str(g) for g in (ganchos or [])],
        "narrador": (narrador or biblia.get("narrador") or "").strip().lower(),
        # O modelo que escreveu. Distingue o que saiu do jeito NOVO (3.1 Pro,
        # com molde, revisao e alavancas) do estoque antigo feito no Flash.
        "modelo_llm": modelo_llm,
        "titulo": biblia.get("titulo") or "",
        # A MARCA CURTA que liga as partes no titulo do video. O `titulo`
        # acima e uma frase de gancho inteira e nao cabe ali junto com o
        # numero da parte — foi por isso que seis partes da mesma serie
        # foram ao ar parecendo seis videos sem relacao nenhuma.
        "serie_nome": biblia.get("serie_nome") or "",
        "premissa": biblia.get("premissa") or "",
        # A VIRADA que a IA escolheu: com o `narrador` e a `premissa`, e o
        # resumo que a proxima historia livre recebe para nao repetir o
        # desenho (17/09/2026).
        "virada": biblia.get("virada") or "",
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
        "quedas": [dict(q) for q in quedas],
    }
    normalizar(dados)
    # Atomico (HIS-1): regravado a cada parte, um corte aqui truncava a serie.
    return _gravar_json_atomico(pasta / "roteiro.json", dados)


def registrar_queda(historia_id: str, queda: dict) -> None:
    """Acrescenta `queda` ao roteiro.json existente. Nunca levanta."""
    caminho = OUTPUTS / historia_id / "roteiro.json"
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        dados["quedas"] = list(dados.get("quedas") or []) + [dict(queda)]
        _gravar_json_atomico(caminho, dados)
    except (OSError, ValueError, TypeError, AttributeError):
        pass


def resumos_recentes(quantos: int = 3) -> list:
    """`["narrador; premissa; virada", ...]` das ultimas historias.

    E a memoria do MODO LIVRE: sem rodizio de alavanca e de narrador, o
    modelo converge para o mesmo desenho (em 09/09/2026, cinco historias
    seguidas com o mesmo par de alavancas). Uma linha por historia basta
    para ele fugir do que acabou de fazer, sem virar molde.
    """
    saida = []
    for dados in listar():
        if str(dados.get("provedor") or "").lower() == "fake":
            continue
        pedacos = [str(dados.get(campo) or "").strip()
                   for campo in ("narrador", "premissa", "virada")]
        if any(pedacos[1:]):
            saida.append("; ".join(p for p in pedacos if p)[:240])
        if len(saida) >= quantos:
            break
    return saida


def titulos_recentes(quantos: int = 12) -> list:
    """Os titulos das historias ja feitas, da mais nova para a mais velha.

    E o que vai no prompt da biblia para o modelo nao repetir assunto. So o
    TITULO: ele ja carrega o gancho, e mandar a premissa inteira de doze
    historias gastaria contexto que a biblia precisa para si.
    """
    saida = []
    for dados in listar():
        if str(dados.get("provedor") or "").lower() == "fake":
            continue
        titulo = (dados.get("titulo") or "").strip()
        if titulo:
            saida.append(titulo)
        if len(saida) >= quantos:
            break
    return saida


def estruturas_recentes(quantos: int = 12) -> list:
    """Os moldes usados, do mais novo para o mais velho.

    E o que faz o rodizio funcionar: sem saber o que veio antes, a escolha
    seria sorteio — e sorteio repete.
    """
    saida = []
    for dados in listar():
        if str(dados.get("provedor") or "").lower() == "fake":
            continue
        nome = (dados.get("estrutura") or "").strip()
        if nome:
            saida.append(nome)
        if len(saida) >= quantos:
            break
    return saida


def partes_que_faltam(roteiro: dict) -> list:
    """Os numeros das partes que a biblia planejou e o texto nao tem.

    Uma serie truncada e o pior resultado possivel do canal — pior que atraso,
    pior que video fraco: quem assistiu a parte 2 e nunca recebe a 3 nao
    volta. E ela acontece de graca, porque a escrita salva a cada parte: basta
    o LLM parar no meio (limite de uso, rede) e sobra um roteiro que PARECE
    inteiro, so que menor.

    Roteiro antigo, sem `partes_esperadas`, devolve lista vazia: nao da para
    afirmar que falta alguma coisa, e inventar falta faria a pipeline
    reprocessar historias que estao boas.
    """
    esperadas = int(roteiro.get("partes_esperadas") or 0)
    if esperadas <= 0:
        return []
    tem = {int(p.get("n") or 0) for p in (roteiro.get("partes") or [])}
    return [n for n in range(1, esperadas + 1) if n not in tem]


def ganchos_recentes(quantos: int = 24) -> list:
    """As alavancas usadas, da mais nova para a mais velha.

    A janela e maior que a dos moldes (24 contra 12) porque sao duas por
    historia e o catalogo tem 35: com 12 o rodizio esqueceria rapido demais e
    voltaria a repetir.
    """
    saida = []
    for dados in listar():
        if str(dados.get("provedor") or "").lower() == "fake":
            continue
        for nome in (dados.get("ganchos") or []):
            nome = str(nome).strip()
            if nome:
                saida.append(nome)
        if len(saida) >= quantos:
            break
    return saida


def narradores_recentes(quantos: int = 8) -> list:
    """Quem narrou, do mais novo para o mais velho.

    Existe porque o narrador derivava quando quem escolhia era o modelo: as
    historias 12, 13, 14 e 15 sairam todas com narrador homem, quatro seguidas.
    """
    saida = []
    for dados in listar():
        if str(dados.get("provedor") or "").lower() == "fake":
            continue
        # O campo proprio veio em 09/09/2026; antes disso o unico registro era
        # o texto da biblia, que nem sempre esta aqui. Historia velha sem o
        # campo simplesmente nao conta para o rodizio.
        nome = str(dados.get("narrador") or "").strip().lower()
        if nome:
            saida.append(nome)
        if len(saida) >= quantos:
            break
    return saida


def proximo_id() -> str:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    existentes = [int(p.name.split("_")[1]) for p in OUTPUTS.glob("historia_*")
                  if p.name.split("_")[-1].isdigit()]
    return f"historia_{(max(existentes) + 1 if existentes else 1):05d}"


def reservar_id() -> str:
    """O proximo id com a pasta JA criada, sem corrida entre processos.

    `proximo_id` + `mkdir(exist_ok=True)` dava o MESMO id a duas rodadas cujas
    biblias chegassem juntas, e as duas escreveriam na mesma pasta. Com as
    duas historias em paralelo (decisao `historias/imagens-dois-geradores-
    juntos`, 06/10/2026) isso deixou de ser teorico. O `mkdir` sem
    `exist_ok` e atomico: quem perde a corrida tenta o id seguinte.
    """
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    for _ in range(1000):
        historia_id = proximo_id()
        try:
            (OUTPUTS / historia_id).mkdir()
        except FileExistsError:
            continue
        return historia_id
    raise RuntimeError("nao consegui reservar um id de historia novo")


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
    _gravar_json_atomico(pasta / "roteiro.json", dados)
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
        except ValueError as exc:
            # Truncado ou corrompido: continua fora da lista (nao ha o que
            # mostrar), mas agora deixa rastro no diario (HIS-1).
            _avisar_ilegivel(pasta, exc)
            continue
        except OSError:
            continue
        dados["pasta"] = str(pasta)
        saida.append(normalizar(dados))
    return saida
