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


def fonte_do_video(video) -> str:
    """`historia_00003:celular:p04` -> `historia_00003`."""
    return str(getattr(video, "fonte_id", "") or
               str(getattr(video, "id", "")).split(":")[0])


# A historia sem tipo (feita antes de os tipos existirem) tambem tem vez no
# rodizio, com este nome interno. Ver `ordenar_por_tipo`.
SEM_TIPO = "_sem_tipo"


def ordenar_por_tipo(fila, ultimos, tipo_da_fonte, cheias=(),
                     fonte_de=fonte_do_video) -> list:
    """A fila reordenada pela vez de cada tipo.

    `ultimos`: tipos das publicacoes, da MAIS NOVA para a mais velha (pode
    repetir). `tipo_da_fonte(fonte_id)`: o tipo daquela HISTORIA — a MESMA
    funcao que `tipos_das_ultimas` recebe.

    O CALLBACK E O MESMO DAS DUAS FUNCOES de proposito (17/09/2026). Ate
    aqui esta pedia o tipo do VIDEO e a outra o tipo da FONTE: quem passou a
    mesma funcao nos dois — o caminho obvio — teve a fila inteira caindo no
    balde "sem tipo", o rodizio virando no-op sem excecao, sem log e com a
    suite verde. Duas perguntas iguais nao podem ter assinaturas diferentes.

    `cheias`: fontes que ja bateram o TETO DO DIA (2 partes da mesma
    historia, decisao do Adrian em 17/09/2026, valendo para tudo). Os videos
    delas saem daqui, e e isso que impede o rodizio de contradizer o teto: o
    tipo da vez sem serie elegivel simplesmente nao aparece, e a vez passa
    para o proximo tipo.
    """
    cheias = set(cheias or ())
    fila = [v for v in (fila or []) if fonte_de(v) not in cheias]
    ultimos = [str(t) for t in (ultimos or []) if t]
    grupos: dict = {}
    for video in fila:
        # SEM TIPO E UM TIPO A MAIS, e nao o rabo da fila (17/09/2026). Antes
        # ele ia para o fim: com a fila cheia de historias tipadas, uma serie
        # antiga sem tipo so sairia quando o resto acabasse — e antes do
        # rodizio ela saia na ordem normal. Perder a vez nao pode ser efeito
        # colateral de uma melhoria de ORDEM.
        grupos.setdefault(str(tipo_da_fonte(fonte_de(video)) or "")
                          or SEM_TIPO, []).append(video)
    if fila and ultimos and list(grupos) == [SEM_TIPO]:
        # O ledger sabe classificar (ha tipos em `ultimos`) e a fila inteira
        # voltou sem tipo: isso e contradicao, nao dado. Levantar deixa quem
        # chama cair na ordem anterior COM LOG, em vez de reordenar por um
        # criterio que nao existe — foi assim que o no-op passou calado.
        raise ValueError(
            "o rodizio recebeu a fila inteira sem tipo, mas o ledger tem "
            "tipos: confira o callback (ele recebe o fonte_id, nao o video)")

    def espera(tipo: str):
        # Nunca publicado = espera infinita; senao, quanto MAIOR o indice da
        # ultima vez, mais tempo sem sair. Empate: a ordem em que o tipo
        # apareceu na fila. O `_sem_tipo` nunca aparece em `ultimos` (o
        # ledger guarda tipo, nao a falta dele), entao ele fica SEMPRE no fim
        # da volta: tem vez, e nao a primeira.
        if tipo == SEM_TIPO:
            return (1, list(grupos).index(tipo))
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
    return saida


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
