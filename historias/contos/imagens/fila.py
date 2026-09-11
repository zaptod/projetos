# -*- coding: utf-8 -*-
"""Quais cenas ainda precisam de imagem, e com que prompt.

Nao existe fila em arquivo aqui: o ESTADO E O DISCO. Uma cena esta pronta
quando `outputs/<id>/cenas/cena_03.png` existe e tem tamanho de imagem. Isso
e de proposito — a fila do outro projeto precisa de arquivo porque um job
pode estar "gerando" num site por 12 minutos; aqui a geracao de imagem dura
segundos e o worker roda do comeco ao fim numa passada. Menos estado, menos
mentira possivel.

`imagens.json` guarda o que o disco nao sabe dizer: o prompt exato enviado e
a PROVA de origem daquela imagem (conta compartilhada — a mesma doutrina do
random_builds: nada entra sem prova de que a imagem e nossa).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"

# Abaixo disto nao e imagem: download truncado ou pagina de erro salva.
BYTES_MINIMOS = 10_000


def carregar_config() -> dict:
    with open(RAIZ / "config" / "imagens.json", encoding="utf-8-sig") as fh:
        return json.load(fh)


def pasta_da_historia(historia_id: str) -> Path:
    return OUTPUTS / historia_id


def caminho_da_cena(historia_id: str, n: int, parte: int | None = None) -> Path:
    """O arquivo daquela cena.

    Numa serie o nome carrega a parte (`p03_cena_07.png`), senao a cena 7 da
    parte 3 sobrescreveria a cena 7 da parte 1. Historia de uma parte so
    mantem o nome curto — e assim as que ja existiam continuam validas.
    """
    cenas = pasta_da_historia(historia_id) / "cenas"
    if not parte or int(parte) <= 1:
        curto = cenas / f"cena_{int(n):02d}.png"
        if int(parte or 1) <= 1 and (curto.is_file() or not parte):
            return curto
    return cenas / f"p{int(parte or 1):02d}_cena_{int(n):02d}.png"


def utilizavel(caminho: Path) -> bool:
    return caminho.is_file() and caminho.stat().st_size >= BYTES_MINIMOS


def prompt_da_cena(cena: dict, config: dict | None = None,
                   protagonista: str = "") -> str:
    """O prompt que vai para o PicassoIA: cena + estilo + proibicoes.

    O estilo entra em TODAS as cenas: e ele que faz doze imagens parecerem do
    mesmo filme. `protagonista` e a descricao fisica curta repetida quando a
    cena esqueceu de repeti-la (a consistencia da pessoa vem do texto, porque
    este modelo nao aceita imagem de referencia).
    """
    config = config or carregar_config()
    partes = [str(cena.get("imagem") or "").strip().rstrip(".")]
    if protagonista and config.get("reforco_consistencia", True):
        alvo = protagonista.strip().rstrip(".")
        if alvo and alvo.lower() not in partes[0].lower():
            partes.append(alvo)
    partes.append(str(config.get("estilo") or "").strip().rstrip("."))
    negativo = str(config.get("negativo") or "").strip()
    if negativo:
        partes.append(negativo.rstrip("."))
    texto = ", ".join(p for p in partes if p)
    teto = int(config.get("prompt_max_chars", 900))
    if len(texto) > teto:
        # Corta na virgula anterior ao teto: cortar no meio de uma clausula
        # deixa o prompt com metade de uma ideia.
        corte = texto.rfind(",", 0, teto)
        texto = texto[:corte if corte > teto * 0.5 else teto].strip().rstrip(",")
    return texto


def _meta(historia_id: str) -> dict:
    caminho = pasta_da_historia(historia_id) / "imagens.json"
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def registrar(historia_id: str, n: int, *, prompt: str, arquivo: Path,
              prova: dict | None = None, url: str = "",
              parte: int = 1, nivel: int | str = 0) -> None:
    """Anota prompt e prova daquela cena (append idempotente por cena).

    `nivel` registra qual foi o tratamento: 0 (original), 1-3 (suavizacao
    mecanica), ou "llm 1"/"llm 2" (reescrita com LLM). Importa saber qual
    dos dois passou a cena, porque muda o que a imagem mostra.
    """
    caminho = pasta_da_historia(historia_id) / "imagens.json"
    dados = _meta(historia_id)
    chave = f"{int(parte)}:{int(n)}"
    # `nivel` pode ser int ou str ("llm 1", etc). Se for 0 ou falsy, vira None.
    nivel_para_salvar = nivel if nivel else None
    dados.setdefault("cenas", {})[chave] = {
        "prompt": prompt,
        "arquivo": Path(arquivo).name,
        "url": url,
        "suavizacao": nivel_para_salvar,
        "prova": {"comprovada": bool((prova or {}).get("comprovada")),
                  "forca": (prova or {}).get("forca"),
                  "motivo": (prova or {}).get("motivo")} if prova else None,
    }
    # A cena passou: se estava marcada como recusada, deixa de estar.
    (dados.get("recusadas") or {}).pop(chave, None)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def registrar_recusa(historia_id: str, n: int, *, parte: int = 1,
                     motivo: str = "", prompt: str = "",
                     ultima_tentativa: str = "") -> None:
    """Marca a cena que o filtro de conteudo barrou ate o ultimo nivel.

    Fica no mesmo arquivo das cenas boas para o painel poder mostrar "esta
    aqui falta imagem, e o motivo foi este" — sem isso a cena reaparece como
    simples pendencia e ninguem descobre por que nunca gera.
    """
    caminho = pasta_da_historia(historia_id) / "imagens.json"
    dados = _meta(historia_id)
    dados.setdefault("recusadas", {})[f"{int(parte)}:{int(n)}"] = {
        "motivo": str(motivo)[:400], "prompt": prompt,
        # A ultima versao tentada (a reescrita do LLM, quando houve): serve
        # para voce ver o que ja foi tentado antes de mexer no roteiro.
        "ultima_tentativa": ultima_tentativa or prompt,
        "quando": datetime.now().isoformat(timespec="seconds"),
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def recusadas(historia_id: str) -> dict:
    """Cenas barradas pelo filtro: {"parte:cena": {motivo, prompt, quando}}."""
    return dict((_meta(historia_id).get("recusadas") or {}))


def estado(historia_id: str, roteiro: dict | None = None,
           parte: int | None = None) -> list[dict]:
    """Uma linha por cena (de toda a historia, ou so de uma parte)."""
    if roteiro is None:
        from ..roteiro import roteiro as R
        roteiro = R.carregar(historia_id)
    else:
        from ..roteiro import roteiro as R
        roteiro = R.normalizar(dict(roteiro))
    meta = _meta(historia_id).get("cenas", {})
    serie = bool(roteiro.get("serie"))
    saida = []
    for bloco in roteiro["partes"]:
        if parte is not None and int(bloco["n"]) != int(parte):
            continue
        for cena in bloco["cenas"]:
            numero_parte = bloco["n"] if serie else None
            caminho = caminho_da_cena(historia_id, cena["n"], numero_parte)
            registro = meta.get(f"{bloco['n']}:{cena['n']}") or \
                (meta.get(str(cena["n"])) if bloco["n"] == 1 else None) or {}
            saida.append({
                "parte": bloco["n"],
                "n": cena["n"],
                "imagem": cena.get("imagem", ""),
                "arquivo": caminho,
                "pronta": utilizavel(caminho),
                "prompt_enviado": registro.get("prompt", ""),
                "prova": registro.get("prova"),
            })
    return saida


def pendentes(historia_id: str, roteiro: dict | None = None,
              parte: int | None = None) -> list[dict]:
    return [l for l in estado(historia_id, roteiro, parte) if not l["pronta"]]


def resumo(historia_id: str, roteiro: dict | None = None,
           parte: int | None = None) -> dict:
    linhas = estado(historia_id, roteiro, parte)
    prontas = [l for l in linhas if l["pronta"]]
    return {"total": len(linhas), "prontas": len(prontas),
            "faltam": len(linhas) - len(prontas),
            "completa": bool(linhas) and len(prontas) == len(linhas)}


def resumo_por_parte(historia_id: str, roteiro: dict | None = None) -> list[dict]:
    """Uma linha por parte: quantas imagens dela ja existem."""
    if roteiro is None:
        from ..roteiro import roteiro as R
        roteiro = R.carregar(historia_id)
    saida = []
    for bloco in roteiro.get("partes") or []:
        dados = resumo(historia_id, roteiro, bloco["n"])
        dados["parte"] = bloco["n"]
        saida.append(dados)
    return saida
