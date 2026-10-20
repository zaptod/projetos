# -*- coding: utf-8 -*-
"""Quem luta no proximo duelo: rodizio, em vez de "o ultimo criado".

MEDIDO EM 27/09/2026: dos 8 duelos gerados a mao naquele dia, 5 tinham o
MESMO p1 (Wren Telgyll). Ninguem escolheu isso. Sem `--p1`, o duelo pegava o
personagem mais recente da roleta, e a ultima roleta era de 24/09 — entao
todo duelo sem argumento repetia o protagonista. O p2 tinha o defeito
espelhado: `escolher_adversario` devolve o GERADO mais recente que ainda nao
lutou com o p1, e esse gerado e o mesmo Wren para quem nunca o enfrentou.
Numa geracao automatica, que roda sem ninguem passar `--p1`, os dois defeitos
juntos fariam do canal "Wren contra todo mundo".

O criterio aqui e USO: quem apareceu menos nos ultimos duelos (como p1 ou
p2) luta primeiro. No empate, quem saiu da roleta vem antes (ele tem video de
build no canal, e o duelo continua a historia dele) e, entre esses, o mais
recente. O resto do empate e sorteado pela seed, para o banco nao ser
percorrido em ordem alfabetica.

E O PAR NAO PODE TER TITULO JA OCUPADO. O titulo do duelo era "{p1} x {p2}"
(desde 20/10/2026 e o confronto pela arma, "Katana VS Sai — quem vence?"), e
a guarda de titulo repetido da publicacao (fechada em 17/09/2026) barra um
video cujo titulo ja foi ao ar. Um duelo com par repetido seria gerado para
nunca sair — 4 minutos de maquina viram estoque morto, e o contador de
estoque ainda o contaria. "B x A" conta como ocupado quando "A x B" existe:
e revanche, e revanche com a mesma dupla e a mesma cara do video anterior.

E QUEM DERRUBA A GRAVACAO FICA DE FORA UMA SEMANA (19/10/2026). O duelo
que falha nao deixa `fight.json`, entao para o rodizio o nome continuava
"o menos usado" e voltava no proximo duelo. Medido no 19/10: Ardeth
Morturth x Zael Ossarvarn estourou os 600 s da gravacao as 16:23 e as 16:34
(a estreia de Zael ja tinha estourado as 10:17), e a rodada fechou com 0
duelos em 22 min — e a seguinte faria o mesmo. O controller grava
`falhou.json` na pasta do duelo que falhou; quem aparece em
`FALHAS_PARA_SUSPENDER` falhas em `DIAS_DE_SUSPENSAO` dias sai do rodizio
(`suspensos`). `--p1`/`--p2` explicitos passam por cima.

Leitura pura: nada aqui grava.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"

# Quantos duelos para tras contam como "recente". Com ~5 duelos por dia, sao
# uns 4 dias: longo o bastante para o mesmo nome nao voltar na mesma semana
# de posts, curto o bastante para o banco inteiro (82 personagens em 27/09)
# voltar a girar.
JANELA_DE_USO = 20

TITULO_PADRAO = "{p1} x {p2}"

# O arquivo que o controller deixa na pasta do duelo que falhou, e a regra
# da suspensao (ver o cabecalho).
FALHA = "falhou.json"
FALHAS_PARA_SUSPENDER = 2
DIAS_DE_SUSPENSAO = 7


def suspensos(outputs: Path | None = None, agora: datetime | None = None,
              dias: float = DIAS_DE_SUSPENSAO,
              limite: int = FALHAS_PARA_SUSPENDER) -> dict[str, int]:
    """`{nome: falhas}` de quem falhou `limite` vezes ou mais nos ultimos
    `dias` (como p1 ou p2). Arquivo ilegivel ou sem data nao conta."""
    pasta = Path(outputs) if outputs is not None else OUTPUTS
    corte = (agora or datetime.now()) - timedelta(days=float(dias))
    contagem: Counter = Counter()
    for arquivo in sorted(pasta.glob(f"duelo_*/{FALHA}")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            quando = datetime.fromisoformat(str(dados.get("em")))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if quando < corte:
            continue
        for chave in ("p1", "p2"):
            nome = dados.get(chave)
            if nome:
                contagem[str(nome)] += 1
    return {n: c for n, c in contagem.items() if c >= int(limite)}


def duelos_recentes(outputs: Path | None = None,
                    n: int | None = JANELA_DE_USO) -> list[tuple[str, str]]:
    """Os pares (p1, p2) dos duelos no disco, do mais antigo ao mais novo.

    A ordem e a do id (`duelo_00001` < `duelo_00002`), que e a de criacao:
    `_next_id` so anda para frente. `n=None` devolve todos.
    """
    pasta = Path(outputs) if outputs is not None else OUTPUTS
    pares: list[tuple[str, str]] = []
    for arquivo in sorted(pasta.glob("duelo_*/fight.json")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        luta = (dados or {}).get("luta") or {}
        p1, p2 = luta.get("p1"), luta.get("p2")
        if p1 and p2:
            pares.append((str(p1), str(p2)))
    return pares[-n:] if n else pares


def uso(pares) -> Counter:
    """Quantas vezes cada nome apareceu, como p1 OU p2."""
    contagem: Counter = Counter()
    for p1, p2 in pares or ():
        contagem[p1] += 1
        contagem[p2] += 1
    return contagem


def _config(config: dict | None) -> dict:
    """O `publicacao.json` UMA vez por escolha, e nao uma por par testado:
    `escolher_p2` testa o banco inteiro (82 nomes, nas duas ordens)."""
    if config is not None:
        return config
    from ..publicar import catalogo
    return catalogo.carregar_config()


def titulo_do_par(p1: str, p2: str, config: dict | None = None,
                  fichas=None) -> str:
    """O titulo que o catalogo dara a este duelo — pelo MESMO modelo dele.

    Ler o modelo do config (e nao escrever "A x B" aqui) e o que impede a
    divergencia: se o titulo do duelo mudar no `publicacao.json`, a checagem
    de par ocupado muda junto.

    Desde 20/10/2026 o titulo e o confronto pela ARMA ("Katana VS Sai — quem
    vence?", semana 1 do plano), e a arma vem da ficha: sem `fichas` (dict
    nome -> ficha do banco) o rotulo de cada lado cai no proprio nome, e a
    checagem deixaria passar um par cujo titulo de verdade ja esta tomado.
    Os campos sao montados pelo mesmo `catalogo.campos_do_confronto`.
    """
    from ..publicar import catalogo
    config = _config(config)
    modelo = ((config or {}).get("titulos") or {}).get("duelo") or TITULO_PADRAO
    banco = fichas if isinstance(fichas, dict) else {}
    luta = {"p1": p1, "p2": p2, "p1_ficha": banco.get(p1) or {},
            "p2_ficha": banco.get(p2) or {}}
    campos = catalogo.campos_do_confronto(luta)
    # FALHA ALTO: um campo sumido do modelo daria o MESMO titulo a todo par e
    # a checagem de par ocupado fecharia o banco inteiro em silencio.
    falta = catalogo.campos_faltando(modelo, campos)
    if falta:
        raise catalogo.TituloIncompleto(
            f"titulo do duelo sem {', '.join(falta)}: {modelo!r} ({p1} x {p2})")
    return catalogo._formatar(modelo, campos)


def titulos_do_disco(outputs: Path | None = None,
                     config: dict | None = None) -> list[str]:
    """O titulo de cada duelo no disco, como o catalogo o da (carimbo ou
    fichas do proprio `fight.json`)."""
    from ..publicar import catalogo
    config = _config(config)
    pasta = Path(outputs) if outputs is not None else OUTPUTS
    saida = []
    for arquivo in sorted(pasta.glob("duelo_*/fight.json")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        luta = (dados or {}).get("luta") or {}
        if luta.get("p1") and luta.get("p2"):
            saida.append(catalogo.titulo_do_duelo(luta, config))
    return saida


def titulos_ocupados(pares=None, publicados=None,
                     config: dict | None = None, fichas=None) -> set:
    """Chaves de titulo que um duelo NOVO nao pode repetir.

    Duas fontes: tudo o que o canal ja pos no ar (o ledger, pelo mesmo
    `titulos.ja_publicados` que a guarda da publicacao usa) e todo duelo que
    ja existe no disco, publicado ou nao — um duelo ainda na fila tambem
    ocupa o titulo, e dois iguais na fila so deixariam um sair.

    Sem `pares`, os duelos do disco entram pelo titulo EXATO do catalogo
    (`titulos_do_disco`). Com `pares` (nomes), pelo `titulo_do_par` com as
    `fichas` do banco.
    """
    from ..publicar import metricas, titulos
    config = _config(config)
    if pares is None:
        do_disco = titulos_do_disco(config=config)
    else:
        do_disco = [titulo_do_par(p1, p2, config, fichas) for p1, p2 in pares]
    if publicados is None:
        try:
            publicados = metricas.publicados()
        except Exception:                                      # noqa: BLE001
            publicados = []
    ocupados = set(titulos.ja_publicados(publicados))
    for titulo in do_disco:
        chave = titulos.chave(titulo)
        if chave:
            ocupados.add(chave)
    return ocupados


def par_ocupado(p1: str, p2: str, ocupados, config: dict | None = None,
                fichas=None) -> bool:
    """O titulo deste par (em qualquer ordem) ja esta tomado?"""
    from ..publicar import titulos
    if not ocupados:
        return False
    return any(titulos.chave(titulo_do_par(a, b, config, fichas)) in ocupados
               for a, b in ((p1, p2), (p2, p1)))


def _fila(nomes, gerados, contagem: Counter, rng) -> list[str]:
    """Os nomes na ordem do rodizio: menos usado, gerado, recente, sorteio."""
    recencia: dict[str, int] = {}
    for indice, nome in enumerate(gerados or ()):
        recencia[nome] = indice          # o ultimo indice e o mais recente
    ordenados = sorted(set(nomes))
    sorteio = {nome: rng.random() for nome in ordenados}
    return sorted(ordenados, key=lambda n: (
        contagem.get(n, 0),
        0 if n in recencia else 1,
        -recencia.get(n, -1),
        sorteio[n]))


def escolher_p2(p1: str, fichas, gerados, pares, rng, *, ledger=None,
                ocupados=None, config: dict | None = None) -> str | None:
    """O adversario de `p1`: entre os MENOS usados, a politica de sempre.

    Primeiro filtra quem forma par ocupado e fica so com os de menor uso;
    dentro disso, `escolher_adversario` decide como antes (continuidade com a
    roleta, senao poder proximo). Assim a regra antiga continua valendo — so
    deixa de poder escolher o mesmo nome em todo duelo.
    """
    from .ledger import escolher_adversario
    config = _config(config)
    contagem = uso(list(pares or ())[-JANELA_DE_USO:])
    livres = [n for n in sorted(fichas or ())
              if n != p1 and not par_ocupado(p1, n, ocupados, config, fichas)]
    if not livres:
        return None
    menor = min(contagem.get(n, 0) for n in livres)
    menos_usados = [n for n in livres if contagem.get(n, 0) == menor]
    fichas_dict = fichas if isinstance(fichas, dict) else None
    return escolher_adversario(p1, menos_usados, rng, gerados=list(gerados or ()),
                               fichas=fichas_dict, ledger=ledger)


def escolher_p1(fichas, gerados, pares, rng, *, ocupados=None,
                config: dict | None = None) -> str | None:
    """O protagonista do proximo duelo. `None` so com o banco vazio.

    Pula quem nao tem NENHUM adversario com titulo livre — ele entraria no
    duelo so para o duelo sair sem par.
    """
    nomes = list(fichas or ())
    if not nomes:
        return None
    config = _config(config)
    contagem = uso(list(pares or ())[-JANELA_DE_USO:])
    fila = _fila(nomes, gerados, contagem, rng)
    for candidato in fila:
        if any(outro != candidato
               and not par_ocupado(candidato, outro, ocupados, config, fichas)
               for outro in nomes):
            return candidato
    return None


def escolher_par(fichas, gerados, rng, *, pares=None, ledger=None,
                 ocupados=None, config: dict | None = None,
                 p1: str | None = None, p2: str | None = None,
                 fora=None):
    """(p1, p2) do proximo duelo; respeita quem ja veio escolhido.

    Quem chama com `--p1`/`--p2` manda: o rodizio so preenche o que faltou.
    `fora`: nomes que o rodizio nao escolhe (`suspensos`). Sem ele, a
    suspensao vem do disco SO quando os pares tambem vem (`pares=None`):
    quem passa os pares (os testes) passa o mundo inteiro.
    """
    config = _config(config)
    todas = fichas
    if fora is None and pares is None:
        try:
            fora = suspensos()
        except OSError:
            fora = {}
        if fora:
            print("[duelo] fora do rodizio por gravacao que falhou: "
                  + ", ".join(f"{n} ({c}x)" for n, c in sorted(fora.items())))
    if fora:
        if isinstance(fichas, dict):
            fichas = {n: f for n, f in fichas.items() if n not in fora}
        else:
            fichas = [n for n in (fichas or ()) if n not in fora]
    if ocupados is None:
        # sem `pares`: os duelos do disco pelo titulo exato do catalogo
        # (com TODAS as fichas: um suspenso ainda ocupa o titulo do disco)
        ocupados = titulos_ocupados(None if pares is None else pares,
                                    config=config, fichas=todas)
    if pares is None:
        pares = duelos_recentes(n=None)
    if not p1:
        p1 = escolher_p1(fichas, gerados, pares, rng, ocupados=ocupados,
                         config=config)
    if p1 and not p2:
        p2 = escolher_p2(p1, fichas, gerados, pares, rng, ledger=ledger,
                         ocupados=ocupados, config=config)
    return p1, p2


__all__ = ["DIAS_DE_SUSPENSAO", "FALHA", "FALHAS_PARA_SUSPENDER",
           "JANELA_DE_USO", "duelos_recentes", "escolher_p1", "escolher_p2",
           "escolher_par", "par_ocupado", "suspensos", "titulo_do_par",
           "titulos_do_disco",
           "titulos_ocupados", "uso"]
