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
"""
from __future__ import annotations

from datetime import datetime, timedelta
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

# Quantos videos cada canal deve por no ar por dia, POR PLATAFORMA.
META_DIARIA_POR_PLATAFORMA = {p: len(h) for p, h in HORAS_POR_PLATAFORMA.items()}
# Os horarios da grade de um canal: um video por horario no YouTube, que e o
# destino que usa todos.
META_DIARIA_POR_CANAL = len(HORAS)
# A conta cheia do dia: cada canal, cada plataforma, com a grade de cada uma.
META_DIARIA_TOTAL = len(CANAIS) * sum(META_DIARIA_POR_PLATAFORMA[p]
                                      for p in PLATAFORMAS)


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


def horarios(plataforma: str | None = None) -> list[str]:
    """`['00:37', '06:37', ...]` — a grade como ela aparece nas telas."""
    horas = HORAS if plataforma is None else horas_da_plataforma(plataforma)
    return [horario(h) for h in horas]


def vencidos(agora: datetime | None = None,
             plataforma: str | None = None) -> list[int]:
    """As horas da grade que JA passaram hoje.

    E contra esta lista que se mede o dia. Comparar com a grade inteira o dia
    todo faria o relatorio das 09:00 acusar horarios perdidos que ainda nem
    chegaram. Com `plataforma`, so os horarios dela.
    """
    agora = agora or datetime.now()
    agora_min = agora.hour * 60 + agora.minute
    horas = HORAS if plataforma is None else horas_da_plataforma(plataforma)
    return [h for h in horas if h * 60 + minuto(h) <= agora_min]


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


__all__ = ["GRADE", "HORAS", "MINUTOS", "MINUTO", "META_DIARIA_POR_CANAL",
           "META_DIARIA_TOTAL", "META_DIARIA_POR_PLATAFORMA",
           "HORAS_POR_PLATAFORMA", "HORAS_DO_TIKTOK", "CANAIS", "PLATAFORMAS",
           "teste", "teste_do_tiktok", "minuto",
           "horario", "horarios", "horas_da_plataforma", "publica_em",
           "vencidos", "proximo", "proximo_em", "slot"]
