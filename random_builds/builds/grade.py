# -*- coding: utf-8 -*-
"""A grade do dia: a que horas sai video, e quantos.

UM lugar so. Ate 11/09/2026 a mesma tupla `(6, 7, 8, 10, 12, 15, 17, 20)`
estava escrita em `ferramentas/postar.py` e em `remoto/relatorios.py`, e a
auditoria ia escrever a terceira. Duas copias ja bastam para o relatorio dizer
"bateu a meta" enquanto a postagem trabalha com outro horario — e quem ler as
duas telas nao tem como saber qual esta certa.

Mora em `builds` porque e o pacote que todos importam (`contos` inclusive), e
porque a grade nao e de um canal: os dois publicam nos mesmos horarios.

A GRADE E DAS HORAS VAGAS DAS PESSOAS (pedido dele em 15/09/2026): indo para
o trabalho, cafe, almoco, lanche, ida embora e a noite ociosa ate quase de
madrugada. Ate entao eram oito horarios densos de manha (6, 7, 8), e o TikTok
pulava 7h e 8h — o que deixava buracos na serie la. Agora sao dez, com minuto
proprio em cada um. O YouTube posta nos dez; o TikTok, desde 19/10/2026, em
seis deles, so de dia (`HORAS_DO_TIKTOK`), com fila propria.

Desde 20/10/2026 um canal pode ter grade PROPRIA dentro da da plataforma
(`HORAS_POR_CANAL`, `horas_do_canal`): o de builds posta 3 por dia no
YouTube e 1 no TikTok — 09:37, 17:57, 21:37 / TikTok 21:37 ate 31/10/2026;
e, desde 27/10/2026 (`HORAS_POR_CANAL_DESDE`, decisao `publicacao/semana-2-
volume`), OITO por dia no YouTube (06:37 09:37 12:07 15:37 17:57 21:37 22:37
23:37) e o TikTok seguindo em 21:37; essa tabela SUBSTITUI a de 01/11 (12:07,
20:37, 22:37 / TikTok 20:37), que nao chegou a valer. `python -m builds.grade
[AAAA-MM-DD]` imprime quem posta o que em cada horario.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

# (hora, minuto), na ordem do calendario. O 00:37 e o ultimo da noite, mas no
# calendario e o primeiro do dia — e assim que `vencidos` e `proximo` contam.
GRADE = (
    (0, 37),    # madrugada, quem ainda esta acordado
    (6, 37),    # indo para o trabalho
    (9, 37),    # cafe da manha
    (12, 7),    # almoco
    (15, 37),   # lanche da tarde
    (17, 57),   # ida embora
    (20, 37),   # noite
    (21, 37),   # noite
    (22, 37),   # noite
    (23, 37),   # noite
)
HORAS = tuple(h for h, _m in GRADE)
MINUTOS = {h: m for h, m in GRADE}
# O minuto "tipico", para quem so precisa de um numero (o das 12h e :07 para
# cair no comeco do almoco). Fora do minuto cheio, em que todo agendador do
# mundo dispara.
MINUTO = 37

CANAIS = ("historias", "builds")
PLATAFORMAS = ("youtube", "tiktok")

# O TIKTOK POSTA SEIS POR DIA, SO DE DIA (decisao `publicacao/tiktok-seis-
# por-dia`, 19/10/2026, TESTE de uma semana). Historia da regra:
#   13/09  o TikTok pulava 7h e 8h (do 7o post do dia em diante a
#          distribuicao caia);
#   15/09  voltou aos dez ("tapar os buracos"): a fila andava com o YouTube e
#          a parte publicada nos horarios pulados nunca chegava ao TikTok;
#   19/10  a analise dos videos mediu o que a de 13/09 suspeitava — o perfil so
#          aparece depois de descansar (blocos depois de 22 h+ sem postar: 6 de
#          6 no builds, 3 de 3 nas historias; depois de 5 a 10 h: 4 de 32 e 3 de
#          33). Seis horarios, de 09:37 a 21:37, deixam ~12 h sem postar a
#          noite.
# O buraco de 15/09 nao volta porque o TikTok agora tem FILA PROPRIA
# (`postar._vez_do_tiktok`): a parte que saiu num horario so do YouTube e a
# primeira da fila do TikTok, na ordem da serie — nunca pulada.
#
# QUANDO O TESTE ACABA A GRADE NAO VOLTA SOZINHA A DEZ: ela continua em seis,
# e a analise mostra o resultado (`teste_do_tiktok`, `analise.
# resultado_do_teste_tiktok`). Voltar e decisao dele.
HORAS_DO_TIKTOK = (9, 12, 15, 17, 20, 21)
HORAS_POR_PLATAFORMA = {
    "youtube": HORAS,
    "tiktok": HORAS_DO_TIKTOK,
}

# O CANAL DE BUILDS (o Neural Fights, canal de DUELOS, EM INGLES desde
# 20/10/2026 — decisao `geral/canal-em-ingles`) POSTA TRES POR DIA NO YOUTUBE
# E UM NO TIKTOK, em horario fixo (`docs/PLANO.md`, semana 1: "YouTube 3/dia
# em horario fixo, so confrontos diferentes"; os horarios, decisao do
# orquestrador). As HISTORIAS nao mudam: dez no YouTube, seis no TikTok, em
# portugues.
#
# OS HORARIOS SAO DO PUBLICO DOS EUA (`docs/pesquisa/som-ganchos-e-musica.md`,
# recomendacao 7, e o orquestrador em 20/10): ~10h, ~19h e ~22h de Brasilia
# ate 31/10, e 1 h MAIS TARDE a partir de 01/11/2026 (fim do horario de verao
# nos EUA: Brasilia passa de ET+1 a ET+2), "usando os minutos proprios da
# grade" — o horario mais perto de cada alvo, entre os dez que ja tem tarefa
# no Agendador (horario novo pediria `postar.py --instalar`, que nao se roda
# sem o Adrian):
#   ate 31/10   09:37 (~10h = 08:37 ET)  17:57 (~19h = 16:57 ET)
#               21:37 (~22h = 20:37 ET)
#   desde 01/11 12:07 (~11h = 10:07 ET)  20:37 (~20h = 18:37 ET)
#               22:37 (~23h = 20:37 ET)
# (A troca de 01/11 foi SUBSTITUIDA em 24/10 pela de oito duelos por dia, abaixo.)
# A troca e POR DATA, no proprio codigo (`HORAS_POR_CANAL_DESDE`): ninguem
# precisa lembrar de mexer. Coincidem com o dado do publico
# BRASILEIRO ate 31/10 (ledger + `_metricas` do YouTube de builds, 15/09 a
# 17/10, views de cada video / mediana do dia de grade dele, 23 dias): 09:37
# 1,41, 17:57 1,23, 21:37 1,19 eram os tres melhores (12:07 0,97). A Analise
# da semana 1 mede os novos.
#
# O TIKTOK DE DUELOS POSTA UM POR DIA (orquestrador, 20/10, dado da parte
# metricas: com ~10 posts por dia, 28 de 36 posts de 12 a 15/10 ficaram em 0
# views; so pegaram, 100-200, os que vieram depois de uma PAUSA — 24/09,
# 27/09, 09-10/10; "no maximo 2, com 8 h ou mais entre eles"): 21:37 (~22h)
# ate 31/10 e 20:37 (~20h) desde 01/11 — a grade do TikTok termina as 21:37,
# entao o ~23h nao existe la. Sempre um dos horarios do YouTube dos builds:
# o TikTok leva o duelo que o YouTube acabou de subir.
#
# Um canal sem linha aqui posta em todos os horarios da plataforma. A grade
# de um canal e sempre um SUBCONJUNTO da da plataforma (`horas_do_canal`):
# um horario que o TikTok nao tem nao vira TikTok so porque o canal o pede.
HORAS_DOS_BUILDS = (9, 17, 21)

# OITO DUELOS POR DIA NO YOUTUBE DESDE 27/10/2026 (decisao `publicacao/semana-2-
# volume`, 24/10: views/dia caiu de ~760 para ~310 quando o volume foi de ~10
# para 3 por dia, com as mesmas ~90-100 views por video; a conta que limita e
# videos x views). O TikTok SEGUE UM POR DIA, 21:37 (a comparacao dele: mediana
# de 1 para 175 views com 1 post/dia). Esta tabela SUBSTITUI a de 01/11 (12:07,
# 20:37, 22:37; TikTok 20:37), que nunca chegou a valer: com oito horarios
# espalhados o dia inteiro o "1 h mais tarde" do fim do horario de verao dos
# EUA nao muda nada que importe, e o TikTok nao muda (decisao dele).
# Os oito sao dos dez da grade, tirando 00:37 e 20:37, os dois piores no dado
# (views de cada video / mediana do dia de grade, builds no YouTube, 15/09 a
# 24/10, videos com 3+ dias: 20:37 0,68 (24 videos), 00:37 0,75 (25); os outros
# 0,82 a 1,40, com 09:37 1,40, 21:37 1,24 e 06:37 1,08). Ficam 06:37 09:37
# 12:07 15:37 17:57 21:37 22:37 23:37: o dia todo de 06:37 a 17:57 (4 em 11 h)
# e a noite dos EUA (21:37 a 23:37 = 19:37 a 21:37 ET). O 21:37 fica por ser
# o do TikTok (o canal e subconjunto da plataforma e o TikTok leva o duelo que
# o YouTube acabou de subir).
INICIO_DOS_OITO_DUELOS = date(2026, 10, 27)
HORAS_DOS_BUILDS_OITO = (6, 9, 12, 15, 17, 21, 22, 23)
HORAS_DO_TIKTOK_DOS_BUILDS = (21,)
HORAS_POR_CANAL = {
    "builds": {"youtube": HORAS_DOS_BUILDS,
               "tiktok": HORAS_DO_TIKTOK_DOS_BUILDS},
}
# ANTES DESTA DATA nenhum canal tinha grade propria: o de builds postava nos
# dez horarios do YouTube (e nos do TikTok). Contar um dia de setembro pela
# grade de tres daria a conferencia, o placar e a analise de dias passados
# errados — a tabela vale do dia em que entrou.
INICIO_DA_GRADE_DO_CANAL = date(2026, 10, 20)
# A partir de cada data (do calendario de Brasilia), a tabela que vale. Em
# ordem; a ultima cuja data ja chegou ganha.
HORAS_POR_CANAL_DESDE = (
    (INICIO_DOS_OITO_DUELOS, {"builds": {"youtube": HORAS_DOS_BUILDS_OITO,
                                         "tiktok": HORAS_DO_TIKTOK_DOS_BUILDS}}),
)


def tabela_do_canal(quando=None) -> dict:
    """`HORAS_POR_CANAL` que vale no dia de `quando` (datetime ou date;
    `None` = agora). Pura com `quando`."""
    if quando is None:
        dia = datetime.now().date()
    elif isinstance(quando, datetime):
        dia = quando.date()
    else:
        dia = quando
    if dia < INICIO_DA_GRADE_DO_CANAL:
        return {}
    tabela = HORAS_POR_CANAL
    for desde, outra in HORAS_POR_CANAL_DESDE:
        if dia >= desde:
            tabela = outra
    return tabela

# Quantos videos cada canal deve por no ar por dia, POR PLATAFORMA (a grade
# da plataforma; o de cada canal e `meta_diaria(canal, plataforma)`).
META_DIARIA_POR_PLATAFORMA = {p: len(h) for p, h in HORAS_POR_PLATAFORMA.items()}
# Os horarios da grade de um canal: um video por horario no YouTube, que e o
# destino que usa todos.
META_DIARIA_POR_CANAL = len(HORAS)


def _meta_total() -> int:
    return sum(len(horas_do_canal(c, p)) for c in CANAIS for p in PLATAFORMAS)


# AS DATAS DO TESTE moram no config da publicacao (o Adrian edita sem tocar
# em codigo): `random_builds/config/publicacao.json` -> `testes` ->
# `tiktok_6_por_dia` = {"inicio": "AAAA-MM-DD", "fim": "AAAA-MM-DD"}, os dois
# inclusive. Elas NAO ligam nem desligam a grade (a grade e a constante
# acima, e vale desde que o codigo entra): servem para a analise saber que
# dias comparar. Ausente ou ilegivel = `None` ("nao sei" nao inventa teste).
CONFIG_DA_PUBLICACAO = (Path(__file__).resolve().parents[1] / "config"
                        / "publicacao.json")


def teste(nome: str, config: dict | None = None) -> dict | None:
    """`{"inicio": date, "fim": date}` do teste `nome`, ou `None`.

    Data torta, fim antes do inicio, ou bloco ausente: `None`. Nunca levanta.
    """
    import json
    from datetime import date
    if config is None:
        try:
            config = json.loads(CONFIG_DA_PUBLICACAO.read_text(
                encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None
    bloco = ((config or {}).get("testes") or {}).get(nome)
    if not isinstance(bloco, dict):
        return None
    try:
        inicio = date.fromisoformat(str(bloco.get("inicio"))[:10])
        fim = date.fromisoformat(str(bloco.get("fim"))[:10])
    except ValueError:
        return None
    if fim < inicio:
        return None
    return {"inicio": inicio, "fim": fim}


def teste_do_tiktok(config: dict | None = None) -> dict | None:
    """As datas do teste de seis por dia no TikTok (ver `HORAS_DO_TIKTOK`)."""
    return teste("tiktok_6_por_dia", config)


def minuto(hora: int) -> int:
    """O minuto em que a grade publica naquela hora."""
    return int(MINUTOS.get(int(hora), MINUTO))


def horario(hora: int) -> str:
    """`'06:37'` — a hora da grade como ela aparece nas telas e no schtasks."""
    return f"{int(hora):02d}:{minuto(hora):02d}"


def horas_da_plataforma(plataforma: str = "youtube") -> tuple:
    """Os horarios em que ESSA plataforma recebe video."""
    return HORAS_POR_PLATAFORMA.get(str(plataforma).lower(), HORAS)


def publica_em(plataforma: str, hora: int) -> bool:
    """Essa plataforma posta no horario `hora`?"""
    return int(hora) in horas_da_plataforma(plataforma)


def horas_do_canal(canal: str | None, plataforma: str = "youtube",
                   quando=None) -> tuple:
    """Os horarios em que ESSE canal posta NESSA plataforma, no dia de
    `quando` (`tabela_do_canal`; `None` = hoje).

    A tabela quando o canal tem grade propria (builds: YouTube 09:37, 17:57
    e 21:37 e TikTok 21:37 ate 26/10/2026; YouTube 06:37, 09:37, 12:07,
    15:37, 17:57, 21:37, 22:37 e 23:37 e TikTok 21:37 desde 27/10), sempre DENTRO da grade da plataforma; senao a
    da plataforma inteira (historias). `canal` vazio ou desconhecido = a da
    plataforma.
    """
    da_plataforma = horas_da_plataforma(plataforma)
    proprias = (tabela_do_canal(quando).get(str(canal or "").lower())
                or {}).get(str(plataforma).lower())
    if proprias is None:
        return da_plataforma
    return tuple(h for h in da_plataforma if h in set(proprias))


def publica_no_canal(canal: str | None, plataforma: str, hora: int,
                     quando=None) -> bool:
    """Esse canal posta nessa plataforma no horario `hora` (no dia de
    `quando`)?"""
    return int(hora) in horas_do_canal(canal, plataforma, quando)


def meta_diaria(canal: str | None, plataforma: str = "youtube",
                quando=None) -> int:
    """Quantos videos ESSE canal deve por no ar por dia NESSA plataforma
    (um por horario de `horas_do_canal`): historias 10 e 6, builds 3 e 1 (8 e 1 desde 27/10/2026)."""
    return len(horas_do_canal(canal, plataforma, quando))


def horarios(plataforma: str | None = None,
             canal: str | None = None, quando=None) -> list[str]:
    """`['00:37', '06:37', ...]` — a grade como ela aparece nas telas."""
    if plataforma is None:
        horas = HORAS
    elif canal is None:
        horas = horas_da_plataforma(plataforma)
    else:
        horas = horas_do_canal(canal, plataforma, quando)
    return [horario(h) for h in horas]


def vencidos(agora: datetime | None = None,
             plataforma: str | None = None,
             canal: str | None = None) -> list[int]:
    """As horas da grade que JA passaram hoje.

    E contra esta lista que se mede o dia. Comparar com a grade inteira o dia
    todo faria o relatorio das 09:00 acusar horarios perdidos que ainda nem
    chegaram. Com `plataforma`, so os horarios dela; com `canal` tambem, so
    os daquele canal nela (`horas_do_canal`).
    """
    agora = agora or datetime.now()
    agora_min = agora.hour * 60 + agora.minute
    if plataforma is None:
        horas = HORAS
    elif canal is None:
        horas = horas_da_plataforma(plataforma)
    else:
        horas = horas_do_canal(canal, plataforma, agora)
    return [h for h in horas if h * 60 + minuto(h) <= agora_min]


def grade_do_dia(quando=None) -> list[dict]:
    """O dia de `quando` inteiro, na ordem do relogio: `[{"horario":
    "09:37", "historias": ["youtube", "tiktok"], "builds": ["youtube"]},
    ...]` — quem posta o que em cada horario. Pura com `quando`."""
    saida = []
    for h in HORAS:
        linha = {"horario": horario(h)}
        for canal in CANAIS:
            linha[canal] = [p for p in PLATAFORMAS
                            if publica_no_canal(canal, p, h, quando)]
        saida.append(linha)
    return saida


def texto_da_grade_do_dia(quando=None) -> str:
    """`grade_do_dia` como tabela, para o terminal (`python -m builds.grade
    [AAAA-MM-DD]`)."""
    dia = quando if quando is not None else datetime.now().date()
    linhas = [f"dia {dia}", "horario  historias          builds"]
    for linha in grade_do_dia(quando):
        celulas = []
        for canal in CANAIS:
            destinos = linha[canal]
            celulas.append(" + ".join(destinos) if destinos else "-")
        linhas.append(f"{linha['horario']}    {celulas[0]:<18} {celulas[1]}")
    linhas.append("por dia: " + "; ".join(
        f"{c} " + ", ".join(f"{p} {meta_diaria(c, p, quando)}"
                            for p in PLATAFORMAS)
        for c in CANAIS))
    return "\n".join(linhas)


def slot(agora: datetime | None = None) -> int:
    """A hora da grade a que ESTE momento pertence.

    Uma rodada tem UM horario, e nao um por minuto em que ela olha o relogio.
    Em 15/09/2026 o disparo das 17:57 publicou a historia as 17:59 (hora 17,
    dentro da grade) e o build as 18:01 — e a hora 18 nao esta na grade, entao
    o TikTok do build foi cortado com "fora da grade do TikTok neste horario".
    A mesma rodada, dois veredictos. E acontecia TODO DIA nesse horario: :57
    mais os ~4 min de upload cruzam a hora.

    O horario e o ultimo que ja venceu: quem roda as 18:01 pertence ao das
    17:57, e a tarefa recuperada que so rodou as 19:30 tambem — ela e aquele
    disparo, atrasado. Antes do primeiro horario do dia (00:37) o momento
    ainda pertence ao ultimo de ontem.
    """
    passados = vencidos(agora or datetime.now())
    return passados[-1] if passados else HORAS[-1]


def proximo(agora: datetime | None = None) -> str:
    """O proximo horario da grade, com a marca de amanha quando virou o dia."""
    agora = agora or datetime.now()
    agora_min = agora.hour * 60 + agora.minute
    for h in HORAS:
        if h * 60 + minuto(h) > agora_min:
            return horario(h)
    return f"{horario(HORAS[0])} (amanha)"


def proximo_em(agora: datetime | None = None) -> datetime:
    """O instante do proximo horario da grade, estritamente depois de `agora`.

    `proximo` devolve texto para mostrar; quem precisa MEDIR quanto falta
    (a reposicao da rodada nao comeca perto do horario seguinte) usa este.
    Atravessa a meia-noite: depois das 23:37 o proximo e o 00:37 de amanha;
    entre 00:00 e 00:37, o 00:37 de hoje.
    """
    agora = agora or datetime.now()
    for dias in (0, 1):
        base = agora + timedelta(days=dias)
        for h in HORAS:
            quando = base.replace(hour=h, minute=minuto(h), second=0,
                                  microsecond=0)
            if quando > agora:
                return quando
    raise ValueError("grade vazia")                      # pragma: no cover


# A conta cheia do dia: cada canal, cada plataforma, com a grade de cada um
# (hoje: historias 10 + 6, builds 3 + 1; 8 + 1 desde 27/10/2026).
META_DIARIA_TOTAL = _meta_total()


__all__ = ["GRADE", "HORAS", "MINUTOS", "MINUTO", "META_DIARIA_POR_CANAL",
           "META_DIARIA_TOTAL", "META_DIARIA_POR_PLATAFORMA",
           "HORAS_POR_PLATAFORMA", "HORAS_DO_TIKTOK", "HORAS_DOS_BUILDS",
           "HORAS_DO_TIKTOK_DOS_BUILDS", "HORAS_DOS_BUILDS_OITO",
           "INICIO_DOS_OITO_DUELOS", "HORAS_POR_CANAL",
           "HORAS_POR_CANAL_DESDE", "tabela_do_canal", "CANAIS",
           "PLATAFORMAS",
           "teste", "teste_do_tiktok", "minuto",
           "horario", "horarios", "horas_da_plataforma", "publica_em",
           "horas_do_canal", "publica_no_canal", "meta_diaria",
           "grade_do_dia", "texto_da_grade_do_dia",
           "vencidos", "proximo", "proximo_em", "slot"]


if __name__ == "__main__":                               # pragma: no cover
    import sys
    print(texto_da_grade_do_dia(date.fromisoformat(sys.argv[1])
                                if len(sys.argv) > 1 else None))
