# -*- coding: utf-8 -*-
"""A fila de postagem em RODIZIO DE TIPO (favela, normal, babaca).

Decisao do Adrian (17/09/2026): tres tipos de historia saindo todo dia, uma
serie de cada no ar ao mesmo tempo, e os horarios em rodizio entre eles.

So ORDENA; nao tira nem poe ninguem na fila. As guardas que ja existem
(ordem das partes, vistoria, titulo repetido, um por horario) continuam
decidindo QUEM pode sair — este modulo decide a VEZ de cada tipo:

  - vai primeiro o tipo que esta ha mais tempo sem publicar (nunca publicado
    antes de todos);
  - dentro do tipo, a ordem que a fila ja trazia (a serie comecada antes da
    nova, a parte N antes da N+1) e preservada.

Funcao pura: quem chama passa a fila, os tipos das ultimas publicacoes e
como descobrir o tipo de um video. Sem disco, sem rede.
"""
from __future__ import annotations


def ordenar_por_tipo(fila, ultimos, tipo_de) -> list:
    """A fila reordenada pela vez de cada tipo.

    `ultimos`: tipos das publicacoes, da MAIS NOVA para a mais velha (pode
    repetir). `tipo_de(video)`: o tipo daquele video (`""` se nao tem).
    Video sem tipo fica no fim, na ordem em que veio.
    """
    fila = list(fila or [])
    ultimos = [str(t) for t in (ultimos or []) if t]
    grupos: dict = {}
    sem_tipo = []
    for video in fila:
        tipo = str(tipo_de(video) or "")
        if tipo:
            grupos.setdefault(tipo, []).append(video)
        else:
            sem_tipo.append(video)

    def espera(tipo: str):
        # Nunca publicado = espera infinita; senao, quanto MAIOR o indice da
        # ultima vez, mais tempo sem sair. Empate: a ordem em que o tipo
        # apareceu na fila.
        idade = ultimos.index(tipo) if tipo in ultimos else len(ultimos) + 1
        return (-idade, list(grupos).index(tipo))

    ordem = sorted(grupos, key=espera)
    saida = []
    # Intercalado, e nao em blocos: a fila inteira ja sai na ordem certa para
    # varios horarios seguidos (quem olha o `--ver` ve o rodizio).
    while any(grupos[t] for t in ordem):
        for tipo in ordem:
            if grupos[tipo]:
                saida.append(grupos[tipo].pop(0))
    return saida + sem_tipo


def tipos_das_ultimas(linhas, tipo_da_fonte, plataforma: str = "youtube",
                      publicado=None) -> list:
    """Tipos das publicacoes do ledger, da mais nova para a mais velha.

    `linhas`: o ledger das historias. `tipo_da_fonte(fonte_id)`: o tipo da
    historia. So conta a linha que saiu de verdade (`publicado`) naquele
    destino — o rodizio e da grade, e a grade e a do YouTube.
    """
    if publicado is None:
        def publicado(linha):
            return bool(linha.get("url"))
    saida = []
    for linha in sorted((l for l in (linhas or []) if isinstance(l, dict)),
                        key=lambda l: str(l.get("quando") or ""),
                        reverse=True):
        if (linha.get("plataforma") or "youtube") != plataforma:
            continue
        if not publicado(linha):
            continue
        fonte = linha.get("fonte_id") or str(linha.get("video_id") or "") \
            .split(":", 1)[0]
        tipo = tipo_da_fonte(fonte) if fonte else ""
        if tipo:
            saida.append(tipo)
    return saida
