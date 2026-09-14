# -*- coding: utf-8 -*-
"""O PROMPT-MESTRE: modelo de roteiro + regras de retencao + contrato.

O fluxo do canal comeca aqui. Voce entrega um MODELO — uma estrutura, sem
ideia nenhuma: "gancho, situacao, escalada, virada, payoff, CTA". Este
modulo junta esse modelo com:

  1. as REGRAS de escrita que fazem o video prender (config/roteiro.json),
  2. as regras de imagem (uma frase em ingles por cena, estilo consistente),
  3. o CONTRATO de saida — o formato exato que `parser.py` sabe ler.

O resultado e um texto pronto para colar em qualquer LLM. A ideia central da
historia e do LLM; o modelo so dita o que tem que sair.

Modelo proprio: um .txt em `modelos/` (uma linha por bloco da estrutura) ou
`--arquivo qualquer/coisa.txt`. O arquivo substitui a estrutura, nunca as
regras nem o contrato — sao eles que garantem que o roteiro vira video.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELOS_DIR = RAIZ / "modelos"


def carregar_config() -> dict:
    import json
    with open(RAIZ / "config" / "roteiro.json", encoding="utf-8-sig") as fh:
        return json.load(fh)


def listar(config: dict | None = None) -> list[dict]:
    """Modelos do config + os .txt que voce largou em `modelos/`."""
    config = config or carregar_config()
    # COMENTARIO NAO E MODELO. O config explica cada molde numa chave
    # `_comment_*` ao lado dele, e em 14/09/2026 a listagem quebrou em
    # `'str' object has no attribute 'get'` por tratar esse texto como molde.
    saida = [{"nome": nome, "rotulo": dados.get("rotulo", nome),
              "cenas": dados.get("cenas_alvo"), "origem": "config"}
             for nome, dados in config["modelos"].items()
             if not str(nome).startswith("_") and isinstance(dados, dict)]
    if MODELOS_DIR.is_dir():
        for arquivo in sorted(MODELOS_DIR.glob("*.txt")):
            saida.append({"nome": arquivo.stem, "rotulo": f"{arquivo.stem} (arquivo)",
                          "cenas": None, "origem": str(arquivo)})
    return saida


def _estrutura(modelo: str | None, arquivo: str | Path | None,
               config: dict) -> tuple[str, list[str], dict]:
    """(nome, linhas da estrutura, dados do modelo)."""
    if arquivo:
        caminho = Path(arquivo)
        if not caminho.is_file():
            candidato = MODELOS_DIR / f"{arquivo}.txt"
            if candidato.is_file():
                caminho = candidato
            else:
                raise FileNotFoundError(f"modelo nao encontrado: {arquivo}")
        linhas = [l.strip() for l in
                  caminho.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        return caminho.stem, linhas, {}
    nome = modelo or config.get("modelo_padrao", "reddit")
    if nome not in config["modelos"]:
        candidato = MODELOS_DIR / f"{nome}.txt"
        if candidato.is_file():
            return _estrutura(None, candidato, config)
        disponiveis = ", ".join(config["modelos"])
        raise KeyError(f"modelo desconhecido: {nome!r}. Existem: {disponiveis}")
    dados = config["modelos"][nome]
    return nome, list(dados["estrutura"]), dados


def prompt_mestre(modelo: str | None = None, *, tema: str | None = None,
                  cenas: int | None = None, duracao: float | None = None,
                  arquivo: str | Path | None = None,
                  config: dict | None = None) -> dict:
    """O texto para colar no LLM, e os metadados de quem o gerou.

    `tema` e opcional de proposito: sem ele o LLM inventa a historia inteira,
    que e o modo normal do canal. Com ele, voce guia o assunto sem escrever o
    roteiro ("uma historia sobre um casamento").
    """
    config = config or carregar_config()
    nome, estrutura, dados = _estrutura(modelo, arquivo, config)
    regras = config["regras"]
    alvo_cenas = cenas or dados.get("cenas_alvo") or 12
    alvo_duracao = duracao or dados.get("duracao_alvo") or 70

    linhas: list[str] = []
    add = linhas.append

    add("Voce e roteirista de um canal de historias narradas, vertical, para "
        "TikTok/Shorts/Reels. Escreva UM roteiro completo, original e ficticio.")
    add("")
    add(f"OBJETIVO: prender quem assiste do primeiro ao ultimo segundo. "
        f"Alvo: {alvo_cenas} cenas, cerca de {alvo_duracao:.0f} segundos de narracao no total.")
    if tema:
        add(f"TEMA (ponto de partida, o resto voce inventa): {tema}")
    else:
        add("TEMA: voce escolhe. Invente uma situacao especifica e incomum - "
            "nada generico, nada que ja parece conhecido.")
    add("")
    add(f"ESTRUTURA OBRIGATORIA (modelo '{nome}'):")
    for i, bloco in enumerate(estrutura, 1):
        add(f"  {i}. {bloco}")
    add("")
    add("COMO ESCREVER A NARRACAO:")
    for regra in regras["narracao"]:
        add(f"  - {regra}")
    add("")
    add("COMO ESCREVER O PROMPT DE IMAGEM DE CADA CENA:")
    for regra in regras["imagem"]:
        add(f"  - {regra}")
    add("")
    add("SOBRE O TEMPO DE CADA CENA:")
    for regra in regras["tempo"]:
        add(f"  - {regra}")
    add("")
    add("FORMATO DA RESPOSTA (exatamente assim, sem nada em volta):")
    for linha in config["contrato"]:
        add(f"  {linha}" if linha else "")
    add("")
    add("EXEMPLO DE UM BLOCO (nao copie o conteudo, so o formato):")
    add("")
    add("CENA 1")
    add("IMAGEM: a woman in her thirties, dark curly hair, grey hoodie, frozen "
        "in a doorway at night, hallway light behind her, hand still on the "
        "door handle, " + "shocked expression")
    add("TEMPO: 4")
    add("NARRACAO: Eu abri a porta e o meu marido estava sentado com a minha irma.")

    texto = "\n".join(linhas)
    return {
        "modelo": nome, "tema": tema or "", "cenas_alvo": alvo_cenas,
        "duracao_alvo": alvo_duracao, "prompt": texto,
        "estrutura": estrutura,
    }


def salvar(prompt: dict, destino: Path | None = None) -> Path:
    """Grava o prompt-mestre em disco (para copiar sem passar pelo console)."""
    destino = Path(destino or (RAIZ / "outputs" / "_prompt_mestre.txt"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(prompt["prompt"] + "\n", encoding="utf-8")
    return destino
