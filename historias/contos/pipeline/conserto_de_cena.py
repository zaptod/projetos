# -*- coding: utf-8 -*-
"""O que refazer quando a IA reprova um video, lido do que ela escreveu.

Tres defeitos, tres consertos:

    ROSTO       o protagonista muda de cara entre as cenas. A causa e a
                descricao fisica vaga no roteiro ("a 30s man, short dark
                hair, tired eyes"), que serve a mais de uma pessoa. O
                conserto fixa a descricao pela aparencia que a propria IA viu
                na MAIORIA das cenas e refaz so as cenas apontadas.
    NARRACAO    a imagem mostra outra coisa que a narracao daquela cena
                conta. Refazer com o mesmo prompt sortearia o mesmo erro, entao
                o prompt e reescrito a partir da narracao antes.
    IMAGEM      colagem, tela dividida, marca d'agua. O prompt esta certo;
                refazer basta.

Nada disto vale sem numero de CENA confiavel — ver `confiavel`.
"""
from __future__ import annotations

import re

NUMERO = re.compile(r"(?:cena|quadro)\s+(\d+)\s*:", re.I)

DIZ_ROSTO = ("muda de rosto", "muda para", "outra pessoa",
             "diferente do protagonista", "diferente da protagonista",
             "muda de aparencia", "muda de aparência", "rosto diferente",
             "identidade diferente")
DIZ_IMAGEM = ("colagem", "tela dividida", "grade de paine", "grade de painé",
              "paineis", "painéis", "marca d'agua", "marca d'água",
              "logotipo", "grade de linhas")
DIZ_NARRACAO = ("narracao", "narração", "nao mostra", "não mostra",
                "contradiz", "contrari", "nao corresponde", "não corresponde",
                "nao tem nada a ver", "não tem nada a ver", "nao faz sentido",
                "não faz sentido")


def confiavel(ficha: dict | None) -> bool:
    """O veredito numera por CENA? Sem isso, o numero nao aponta nada."""
    return bool(ficha) and ficha.get("numeracao") == "cena"


def atual(ficha: dict | None) -> bool:
    """Numerado por cena E dado com o criterio de hoje do parecer.

    O criterio muda quando o prompt muda. Em 13/09/2026 a regra de "imagem
    igual a narracao" saiu rigida demais e a IA reprovou 11 de 11 videos do
    estoque por detalhe. Veto dado com a regua velha e perguntado de novo em
    vez de guiar conserto: refazer cena por causa de um gesto que falta so
    gasta a conta do PicassoIA.
    """
    if not confiavel(ficha):
        return False
    from ..publicar import parecer
    return int(ficha.get("criterio") or 1) >= parecer.CRITERIO


def _pedacos(motivos) -> list:
    saida = []
    for motivo in motivos or []:
        saida.extend(p.strip() for p in str(motivo).split(";") if p.strip())
    return saida


# Frase fixa nao pega o jeito que o Gemini escreve. Em 13/09/2026 ele disse
# "o protagonista muda COMPLETAMENTE de aparencia (etnia, rosto e cabelo)", e
# "muda de aparencia" nao casou: a cena 13 ficou fora do conserto na primeira
# rodada real. Entao troca de rosto e reconhecida tambem por dois sinais
# juntos: a frase fala de rosto E fala de mudanca.
# ROUPA, CABELO E IDADE TAMBEM. O prompt do parecer reprova "o protagonista
# muda de rosto, idade, cabelo ou roupa", e na segunda rodada real o Gemini
# escreveu "cena 8: o protagonista muda de roupa, passando a usar uma blusa
# preta lisa". Sem estas palavras a cena caiu fora de todas as classes e nao
# foi refeita. E o mesmo defeito de continuidade, com o mesmo conserto: a
# descricao fixa do protagonista ja traz a roupa.
SINAIS_DE_ROSTO = ("rosto", "aparencia", "aparência", "etnia", "identidade",
                   "outra pessoa", "outro homem", "outra mulher", "roupa",
                   "cabelo", "idade")
SINAIS_DE_MUDANCA = ("muda", "mudou", "diferente", "troca", "trocou", "outra",
                     "outro", "nao e o mesmo", "não é o mesmo",
                     "nao e a mesma", "não é a mesma")


def _fala_de_rosto(texto: str) -> bool:
    if any(t in texto for t in DIZ_ROSTO):
        return True
    return (any(t in texto for t in SINAIS_DE_ROSTO)
            and any(t in texto for t in SINAIS_DE_MUDANCA))


def classificar(motivos) -> dict:
    """`{"rosto": [n], "narracao": [n], "imagem": [n]}` a partir dos motivos.

    Os motivos chegam como lista ou como uma frase so, separada por `;`.
    Cada pedaco vai para UMA classe, na ordem rosto, imagem, narracao: um
    pedaco que acusa troca de rosto e cita a narracao continua sendo rosto.
    """
    classes = {"rosto": set(), "narracao": set(), "imagem": set()}
    for pedaco in _pedacos(motivos):
        numeros = {int(m.group(1)) for m in NUMERO.finditer(pedaco)}
        if not numeros:
            continue
        texto = pedaco.lower()
        if _fala_de_rosto(texto):
            classes["rosto"] |= numeros
        elif any(t in texto for t in DIZ_IMAGEM):
            classes["imagem"] |= numeros
        elif any(t in texto for t in DIZ_NARRACAO):
            classes["narracao"] |= numeros
    return {k: sorted(v) for k, v in classes.items()}


def motivos_da_cena(motivos, n: int) -> str:
    """O que a IA disse sobre a cena `n`, junto."""
    saida = []
    for pedaco in _pedacos(motivos):
        if n in {int(m.group(1)) for m in NUMERO.finditer(pedaco)}:
            saida.append(pedaco)
    return "; ".join(saida)


def fixar_protagonista(roteiro: dict, nova: str) -> int:
    """Troca a descricao do protagonista no roteiro E dentro de cada prompt.

    Trocar so `roteiro["protagonista"]` nao muda imagem nenhuma: os prompts
    de cena ja trazem a descricao antiga escrita por extenso, e o gerador so
    acrescenta a do roteiro quando ela falta. Devolve quantos prompts mudaram.
    """
    antiga = str(roteiro.get("protagonista") or "").strip().rstrip(".")
    nova = str(nova or "").strip().rstrip(".")
    if not nova or nova.lower() == antiga.lower():
        return 0
    trocas = 0
    if antiga:
        for bloco in roteiro.get("partes") or []:
            for cena in bloco.get("cenas") or []:
                texto = str(cena.get("imagem") or "")
                posicao = texto.lower().find(antiga.lower())
                if posicao < 0:
                    continue
                cena["imagem"] = (texto[:posicao] + nova
                                  + texto[posicao + len(antiga):])
                trocas += 1
    roteiro["protagonista"] = nova
    return trocas


def pedido_de_prompt(cena: dict, protagonista: str, motivo: str) -> str:
    """O que se pede ao LLM para reescrever o prompt de UMA cena.

    PEDIDO DE TEXTO, E DITO NA PRIMEIRA LINHA. A primeira versao abria com
    "Voce escreve prompts de imagem para um gerador", e o Gemini entendia
    como pedido para DESENHAR: na madrugada de 14/09/2026 ele ficou 590 s
    "escrevendo" com zero caracteres de texto, e o mesmo ja tinha derrubado a
    reescrita duas vezes na tarde anterior. O conserto de narracao nunca
    chegava a acontecer.
    """
    linhas = [
        "PEDIDO DE TEXTO. Nao gere, nao desenhe e nao anexe imagem nenhuma: "
        "responda apenas com uma linha de texto.",
        "Reescreva, em ingles, a descricao usada para ilustrar a cena abaixo, "
        "para que ela descreva EXATAMENTE o que a narracao desta cena conta: "
        "as mesmas pessoas, o mesmo lugar, o mesmo momento.",
        "Regras da descricao: uma frase densa com virgulas; um instante so, "
        "sem transicao; sem colagem, sem tela dividida, sem texto; "
        "enquadramento cinematografico, com o assunto no centro.",
    ]
    if protagonista:
        linhas.append("Se o protagonista aparecer, use exatamente esta "
                      f"descricao dele: {protagonista}.")
    linhas += [
        "",
        f"NARRACAO DA CENA: {cena.get('narracao', '')}",
        f"PROMPT ATUAL: {cena.get('imagem', '')}",
        f"O QUE O REVISOR APONTOU: {motivo or 'a imagem nao bate com a narracao'}",
        "",
        "Responda SO o novo prompt, sem aspas e sem comentario.",
    ]
    return "\n".join(linhas)


def _cenas_da_parte(roteiro: dict, parte: int) -> dict:
    for bloco in roteiro.get("partes") or []:
        try:
            if int(bloco.get("n") or 0) == int(parte):
                return {int(c["n"]): c for c in bloco.get("cenas") or []
                        if str(c.get("n", "")).strip().isdigit()}
        except (TypeError, ValueError):
            continue
    return {}


def reescrever_prompts(roteiro: dict, parte: int, cenas: list, motivos, *,
                       provedor: str = "gemini", headless: bool = False,
                       log=print, perguntar=None, falhas=None) -> dict:
    """Reescreve NO ROTEIRO o prompt das cenas apontadas. `{n: prompt}`.

    Nao salva: quem chama decide, depois de ver o que mudou. `perguntar` e
    injetavel para o teste nao abrir navegador. `falhas`, se vier, recebe o
    texto da falha do provedor: quem chama precisa separar "o Gemini nao
    respondeu" de "respondeu e nao mudou nada".
    """
    from ..imagens.reescritor import limpar

    alvo = _cenas_da_parte(roteiro, parte)
    protagonista = str(roteiro.get("protagonista") or "")
    novos = {}

    def _rodar(pergunta):
        for n in cenas:
            cena = alvo.get(int(n))
            if cena is None:
                continue
            resposta = pergunta(pedido_de_prompt(
                cena, protagonista, motivos_da_cena(motivos, int(n))))
            novo = limpar(resposta)
            if novo and novo.lower() != str(cena.get("imagem") or "").lower():
                cena["imagem"] = novo
                novos[int(n)] = novo

    if perguntar is not None:
        _rodar(perguntar)
        return novos
    try:
        from ..llm.cliente import abrir_cliente
        with abrir_cliente(provedor, headless=headless, esperar=60.0,
                           log=log) as cliente:
            cliente.abrir(novo_chat=True)
            # SEM PRAZO PROPRIO: vale o do cliente, o mesmo da geracao de
            # roteiro. Com 180 s a reescrita falhou duas vezes seguidas na
            # primeira rodada de dia ("nao respondeu em 180s e nao ha texto na
            # tela") enquanto o mesmo Gemini respondia a revisao de video: o
            # modelo Pro ainda estava pensando quando o prazo acabou.
            _rodar(lambda texto: cliente.perguntar(texto))
    except Exception as exc:                                   # noqa: BLE001
        log(f"[reparo] nao consegui reescrever os prompts pelo {provedor} "
            f"({type(exc).__name__}: {exc}).")
        if falhas is not None:
            falhas.append(f"{provedor} falhou: {type(exc).__name__}")
    return novos


def gravar_roteiro(historia_id: str, roteiro: dict):
    """Grava o roteiro de volta INTEIRO, com copia do original ao lado.

    NAO usar `roteiro.salvar`: ele e o gravador do roteiro avulso e remonta o
    arquivo so com titulo, cta e cenas. Numa serie, apagaria as partes, a
    biblia e o protagonista. A guarda recusa gravar se alguma chave que
    estava no disco sumiu, e a copia so e feita na primeira vez, para guardar
    o roteiro de antes de qualquer conserto.
    """
    import json
    import shutil

    from ..roteiro import roteiro as R

    caminho = R.OUTPUTS / historia_id / "roteiro.json"
    with open(caminho, encoding="utf-8-sig") as fh:
        no_disco = json.load(fh)
    sumiram = set(no_disco) - set(roteiro)
    if sumiram:
        raise ValueError(f"o roteiro perderia {sorted(sumiram)}; nao gravei")
    reserva = caminho.with_name("roteiro.antes_do_reparo.json")
    if not reserva.exists():
        shutil.copy2(caminho, reserva)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(roteiro, fh, ensure_ascii=False, indent=2)
    return caminho


__all__ = ["classificar", "confiavel", "fixar_protagonista", "gravar_roteiro",
           "motivos_da_cena", "pedido_de_prompt", "reescrever_prompts"]
