# -*- coding: utf-8 -*-
"""Titulo comparavel — e a fila que nao repete titulo.

Por que existe (auditoria de 15/09/2026): 13 das 40 builds foram ao ar DUAS
vezes, com titulo identico, competindo entre si pelo mesmo termo de busca e
pela mesma recomendacao. Nao foi descuido de quem publicou: a deduplicacao
do projeto inteiro e por `video_id`, e a variante "gancho B" tem id com
sufixo `":B"` e o MESMO titulo. Para o codigo eram dois videos diferentes;
para o YouTube eram dois videos iguais.

A funcao `chave` nao e nova: ela morava em `metricas._chave_de_titulo`,
usada so para reconciliar id faltante. Ela foi MOVIDA para ca, e o nome
antigo ficou como apelido — inventar um segundo criterio de "titulo igual"
seria criar a proxima divergencia.

Este modulo nao le disco e nao sabe o que e um canal: recebe as linhas do
ledger e devolve conjuntos. E o que permite testa-lo sem tocar em nada.
"""
from __future__ import annotations

import re


def _publicado(linha) -> bool:
    # Import tardio: `metricas` importa este modulo.
    from .metricas import publicado
    return publicado(linha)


# O corte em 60 e o do criterio original: o Studio devolve o titulo que ele
# ACEITOU (corta em 100), e comparar o rabo de dois titulos longos gera mais
# falso negativo do que acerto.
TAMANHO = 60


# O "(Parte 3/6)" do fim do titulo, em qualquer das formas que o projeto usa.
# E a UNICA diferenca entre duas partes da mesma serie, e por isso ele nao
# pode ser o pedaco que o corte joga fora.
PARTE = re.compile(r"\(?\s*parte\s*(\d+)\s*[/de]{1,2}\s*(\d+)\s*\)?\s*$",
                   re.IGNORECASE)


# O "(1 de 2)" que o `cortes._copia` gruda quando uma parte longa vira dois
# Shorts. Ele identifica o ARQUIVO, e nao o CONTEUDO: os dois pedacos contam
# a mesma parte da mesma historia.
# O PARENTESE DE ABERTURA E OBRIGATORIO, e o teste pegou o porque: sem ele o
# regex casava o rabo de "(Parte 3 de 6)" — lendo a PARTE como se fosse um
# pedaco e apagando a unica coisa que distingue duas partes da mesma serie.
# Dentro dos parenteses so pode haver "N de M", nada mais.
CORTE = re.compile(r"\(\s*(\d+)\s+de\s+(\d+)\s*\)\s*$", re.IGNORECASE)


def corte(texto: str) -> tuple | None:
    """`(indice, total)` quando o titulo e de um PEDACO; `None` quando nao.

    Existe porque `chave` deixou de distinguir os dois pedacos, e em um lugar
    essa distincao e obrigatoria: ao escolher videos PRIVADOS para voltar ao
    ar, "(1 de 2)" e "(2 de 2)" sao dois arquivos e os dois precisam sair.
    Deduplicar por conteudo ali deixaria metade da parte privada para sempre.
    """
    achado = CORTE.search(re.sub(r"\s+", " ", str(texto or "")).strip())
    return (int(achado.group(1)), int(achado.group(2))) if achado else None


def chave(texto: str) -> str:
    """Titulo comparavel: sem acento de pontuacao, sem emoji, sem caixa.

    O SUFIXO DO CORTE SAI; o da PARTE fica. MEDIDO EM 17/09/2026, casando o
    ledger com o canal de historias: a `historia_00003` tem SEIS conteudos
    publicados em duplicata (as partes 1 a 3 com o video inteiro E os dois
    pedacos no ar, as partes 4 a 6 com dois pares de pedacos de rodadas
    diferentes). 96 videos no canal para 79 conteudos.

    A chave nao enxergava nada disso, porque o ledger guarda "(Parte 4)" e o
    canal guarda "(Parte 4) (1 de 2)" — chaves diferentes, comparacao sempre
    negativa. Eu mesma reportei os cinco como "publicacoes fantasma" por
    causa deste falso negativo.

    Tirar o "(N de M)" e seguro para as guardas porque NENHUMA delas roda por
    pedaco: `publicar_youtube` percorre `cortes.preparar` dentro de UMA
    publicacao, e o titulo repetido e o rodizio decidem sobre o item do
    catalogo, que e sempre inteiro. Quem precisa da distincao chama `corte`.

    O SUFIXO DA PARTE SOBREVIVE AO CORTE. Medido em 17/09/2026: o corte em 60
    caracteres ainda nao colidia por sorte — a diferenca entre as partes cai
    antes do limite em 13 das 14 series, e a 14a estava a 3 caracteres. Com o
    formato de titulo-pergunta que esta chegando ("Eu sou o babaca por nao
    deixar minha irma usar o vestido de noiva da nossa mae?"), as SEIS partes
    dao a MESMA chave.

    Isso era inofensivo enquanto a valvula de titulo repetido apenas avisava.
    Desde que ela fecha (17/09), duas partes com a mesma chave viram uma
    serie que PARA na parte 1 — e ninguem descobre, porque o sintoma e um
    horario vazio, nao um erro.

    Entao o corte passa a comer o corpo do titulo, nunca a parte.
    """
    limpo = re.sub(r"\s+", " ", str(texto or "")).strip().lower()
    # O CORTE SAI PRIMEIRO, senao o "(Parte 4)" deixa de estar no fim e o
    # regex da parte nao casa — e a parte e justamente o que nao pode sumir.
    limpo = CORTE.sub("", limpo).strip()
    achado = PARTE.search(limpo)
    sufixo = ""
    if achado:
        limpo = limpo[:achado.start()].strip()
        sufixo = f" parte {achado.group(1)} de {achado.group(2)}"
    limpo = "".join(c for c in limpo if c.isalnum() or c.isspace())
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return (limpo[:max(0, TAMANHO - len(sufixo))] + sufixo).strip()


def ja_publicados(linhas) -> set:
    """As chaves de titulo que ja foram ao ar, vindas do ledger.

    So conta linha que de fato saiu (`metricas.publicado`) — uma linha sem
    destino nao ocupou lugar nenhum no canal e nao deve barrar ninguem.
    """
    vistos = set()
    for linha in linhas or ():
        if not isinstance(linha, dict) or not _publicado(linha):
            continue
        k = chave(linha.get("titulo"))
        if k:
            vistos.add(k)
    return vistos


def repetido(titulo: str, ja: set) -> bool:
    """Este titulo ja esta no ar?

    Titulo vazio NUNCA e repetido: `chave("")` e `chave("   ")` dao a mesma
    string vazia, e trata-la como igual barraria todo video sem titulo
    contra todo outro video sem titulo.
    """
    k = chave(titulo)
    return bool(k) and k in (ja or set())


__all__ = ["TAMANHO", "chave", "corte", "ja_publicados", "repetido"]
