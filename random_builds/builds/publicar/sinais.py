# -*- coding: utf-8 -*-
"""Sinais de vida: o que devia ter acontecido, e nao aconteceu.

Por que existe (28/09/2026). Todo alarme da casa reage a um EVENTO — e
ausencia nao escreve linha. Tres ausencias passaram dias sem ninguem ver:

  - a noite de 21/09 nao teve conferencia nenhuma, nem coleta de metrica, e
    nenhuma ficha disse "faltei";
  - o canal de builds passou 25 e 26/09 com ZERO eventos no diario, enquanto
    historias escrevia 467 e 824;
  - de 17 a 27/09 a reconciliacao morreu e as linhas novas de historias
    ficaram sem `youtube_id` (61 de 158 com id em 27/09). Sem id nao ha
    metrica nem formato.

Cada sinal responde "o que falta?" com um numero. E o caso vazio nunca vira
nota boa: sem linha para medir e "nao medi" (`None`), nunca 100%.

As contas sao PURAS: recebem listas e relogio. So `ler_diario` le disco.
Quem usa: a conferencia da noite (linha de erro no diario, que chega ao
celular) e `panorama.confiabilidade` (o relatorio das 22:30 e a pagina do
painel). Os dois chamam estas mesmas funcoes — dois leitores, uma conta.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from .. import grade

# Fabricas que OBSERVAM a maquina em vez de trabalhar para o canal. Contar o
# alarme como evento do canal faria um canal morto parecer vivo: a
# conferencia escreve justamente sobre ele duas linhas de erro por noite.
FABRICAS_QUE_OBSERVAM = frozenset({"conferencia", "metricas", "apurador"})
# `log` e conversa (2126 linhas do `estudio` de 25 a 28/09), nao trabalho.
STATUS_DE_TRABALHO = frozenset({"inicio", "ok", "erro"})
HORAS_DE_EVENTOS = 24
# Menos que isto de diario lido e evidencia fraca: logo depois de uma poda,
# ou num diario recem-criado, "nenhum evento em 3 h" nao diz que o canal
# parou. O diario real cobre uns dois dias (poda para 2000 linhas).
MINIMO_DE_HORAS_COBERTAS = 12

# A reconciliacao do `youtube_id` so roda de madrugada: linha com menos de um
# dia pode estar sem id sem nada de errado.
FOLGA_DO_ID = timedelta(hours=24)
DIAS_DE_COBERTURA = 7
# O numero do documento de metricas (27/09): abaixo disso, video demais fica
# fora da metrica e da comparacao por formato.
COBERTURA_MINIMA = 0.90


def _local(ts) -> datetime | None:
    """Carimbo do diario (UTC, com fuso) ou do ledger (local, sem fuso),
    sempre como hora LOCAL sem fuso — para poderem ser comparados."""
    try:
        quando = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if quando.tzinfo is not None:
        quando = quando.astimezone().replace(tzinfo=None)
    return quando


# ------------------------------------------------------------------ a noite
def noite_esperada(agora: datetime | None = None) -> date:
    """A ultima noite que ja devia ter deixado ficha de conferencia.

    A noite do dia D roda de madrugada (01:28 a 05:20 em 27/09/2026) e acaba
    quando o dia de grade de D abre (06:37, o horario depois do maior buraco
    da grade). Antes disso, a ultima noite que ja acabou e a de D-1.
    """
    from . import conferencia
    agora = agora or datetime.now()
    abertura, _ = conferencia.abertura_e_fechamento("youtube")
    abre = agora.replace(hour=int(abertura), minute=grade.minuto(abertura),
                         second=0, microsecond=0)
    return agora.date() if agora >= abre else agora.date() - timedelta(days=1)


def _dia(ficha) -> date | None:
    try:
        return date.fromisoformat(str((ficha or {}).get("dia"))[:10])
    except (TypeError, ValueError, AttributeError):
        return None


def noite_rodou(ficha) -> bool | None:
    """A ficha do dia teve rodada DE MADRUGADA, antes de o dia de grade abrir?

    A ficha do dia e regravada por qualquer rodada, inclusive a do botao do
    painel as 14:00; sem isto, ela apagaria o rastro da noite que faltou.
    Ficha de antes de 28/09/2026 nao tem `rodadas`: `None`, nao sei.
    """
    from . import conferencia
    rodadas = (ficha or {}).get("rodadas") if isinstance(ficha, dict) else None
    if not isinstance(rodadas, list):
        return None
    abertura, _ = conferencia.abertura_e_fechamento("youtube")
    limite = grade.horario(abertura)
    return any(str(r)[:5] < limite for r in rodadas)


def noites_sem_conferencia(ficha, agora: datetime | None = None
                           ) -> dict | None:
    """`None` quando a ultima noite esperada tem ficha; senao, o buraco.

    `ficha` e a mais recente do canal (a de erro conta: rodou e falhou e
    outra pergunta, com alerta proprio). Sem ficha nenhuma, `ultima` e
    `None` — nunca rodou tambem e noite sem conferencia.
    """
    esperada = noite_esperada(agora)
    ultima = _dia(ficha)
    if ultima is not None and ultima > esperada:
        return None
    if ultima == esperada and noite_rodou(ficha) is not False:
        return None
    feita = ultima if ultima is not None and ultima < esperada else None
    if ultima == esperada:
        # So houve rodada feita a mao nesse dia: a noite dele faltou.
        feita = esperada - timedelta(days=1)
    return {"esperada": esperada.isoformat(),
            "ultima": ultima.isoformat() if ultima else None,
            "noites": (esperada - feita).days if feita else None}


def noites_puladas(anterior, hoje: date) -> list:
    """As noites ENTRE a ficha anterior e hoje que nao deixaram ficha.

    E o que a conferencia pergunta na primeira rodada da noite: se a ficha
    anterior e de anteontem, a noite de ontem nao rodou. E se a de ontem so
    tem rodada feita a mao, a noite de ontem tambem nao. Sem ficha anterior
    nao ha o que dizer (e a primeira vez).
    """
    dia = _dia(anterior)
    if dia is None or dia >= hoje:
        return []
    puladas = [(dia + timedelta(days=n)).isoformat()
               for n in range(1, (hoje - dia).days)]
    if noite_rodou(anterior) is False:
        puladas.insert(0, dia.isoformat())
    return puladas


# ---------------------------------------------------------------- o diario
def ler_diario(caminho=None) -> list | None:
    """O diario INTEIRO (ele e podado acima de 4000 linhas). `None` = nao li.

    `atividade.recentes()` le so as ultimas 1200 linhas. Em 27/09/2026
    historias escreveu 1103 eventos num dia so: uma janela de 24 h lida por
    ali podia ter sido cortada sem aviso nenhum.
    """
    try:
        if caminho is None:
            from .. import atividade
            caminho = atividade._arquivo()
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            brutas = fh.readlines()
    except OSError:
        return None
    saida = []
    for bruta in brutas:
        bruta = bruta.strip()
        if not bruta:
            continue
        try:
            evento = json.loads(bruta)
        except ValueError:
            continue
        if isinstance(evento, dict):
            saida.append(evento)
    return saida


def horarios_entre(de: datetime, ate: datetime,
                   plataforma: str = "youtube") -> int:
    """Quantos horarios da grade cairam em `(de, ate]`."""
    total, dia = 0, de.date()
    while dia <= ate.date():
        for hora in grade.horas_da_plataforma(plataforma):
            instante = datetime(dia.year, dia.month, dia.day, int(hora),
                                grade.minuto(hora))
            if de < instante <= ate:
                total += 1
        dia += timedelta(days=1)
    return total


def eventos_por_canal(eventos, agora: datetime | None = None, *,
                      horas: float = HORAS_DE_EVENTOS,
                      canais=grade.CANAIS) -> dict:
    """`{canal: {eventos, minimo, horas_cobertas, poucos}}` nas ultimas horas.

    Conta so TRABALHO: status `inicio`/`ok`/`erro`, fora das fabricas que
    observam. O `minimo` e o numero de horarios da grade (YouTube) que
    cairam na janela COBERTA pelo diario: cada horario tenta publicar e
    escreve pelo menos um `inicio`. Em 24 h cobertas, 10.

    Diario podado cobre menos que a janela as vezes; ai o minimo encolhe
    junto, em vez de acusar ausencia num trecho que nao foi lido. Com menos
    de `MINIMO_DE_HORAS_COBERTAS` lidas, ou diario vazio, `poucos` fica
    `None` (nao medi), e nao `False`.
    """
    agora = agora or datetime.now()
    inicio = agora - timedelta(hours=float(horas))
    instantes = []
    for evento in eventos or ():
        if not isinstance(evento, dict):
            continue
        quando = _local(evento.get("ts"))
        if quando is not None and quando <= agora:
            instantes.append((quando, evento))
    if instantes:
        mais_velho = min(q for q, _e in instantes)
        coberto_desde = max(inicio, mais_velho)
    else:
        coberto_desde = agora
    horas_cobertas = round((agora - coberto_desde).total_seconds() / 3600, 1)
    minimo = horarios_entre(coberto_desde, agora)
    saida = {}
    for canal in canais:
        do_canal = [e for q, e in instantes
                    if q >= coberto_desde and e.get("canal") == canal
                    and e.get("status") in STATUS_DE_TRABALHO
                    and e.get("fabrica") not in FABRICAS_QUE_OBSERVAM]
        medido = minimo and horas_cobertas >= MINIMO_DE_HORAS_COBERTAS
        saida[canal] = {
            "eventos": len(do_canal), "minimo": minimo,
            "horas_cobertas": horas_cobertas,
            "poucos": (len(do_canal) < minimo) if medido else None,
        }
    return saida


# -------------------------------------------------------- youtube_id no ledger
def cobertura_de_ids(linhas, agora: datetime | None = None, *,
                     dias: int = DIAS_DE_COBERTURA,
                     folga: timedelta = FOLGA_DO_ID) -> dict:
    """Quantas publicacoes RECENTES do YouTube ja tem `youtube_id`.

    Janela: de `dias` atras ate `folga` atras — a linha de hoje ainda nao
    passou por uma noite de reconciliacao. O acervo antigo fica de fora de
    proposito: medir o ledger inteiro daria um numero que nunca muda.
    Sem linha na janela, `cobertura` e `None`: nao medi, nao e 100%.
    """
    from .metricas import publicado
    agora = agora or datetime.now()
    de, ate = agora - timedelta(days=dias), agora - folga
    medidas = []
    for linha in linhas or ():
        if not isinstance(linha, dict) or not publicado(linha):
            continue
        if (linha.get("plataforma") or "youtube") != "youtube":
            continue
        quando = _local(linha.get("quando"))
        if quando is not None and de <= quando <= ate:
            medidas.append(linha)
    com_id = sum(1 for l in medidas if l.get("youtube_id"))
    cobertura = (com_id / len(medidas)) if medidas else None
    return {"linhas": len(medidas), "com_id": com_id,
            "cobertura": None if cobertura is None else round(cobertura, 3),
            "baixa": None if cobertura is None
            else cobertura < COBERTURA_MINIMA,
            "de": de.isoformat(timespec="minutes"),
            "ate": ate.isoformat(timespec="minutes")}


__all__ = ["COBERTURA_MINIMA", "DIAS_DE_COBERTURA", "FABRICAS_QUE_OBSERVAM",
           "FOLGA_DO_ID", "HORAS_DE_EVENTOS", "MINIMO_DE_HORAS_COBERTAS",
           "STATUS_DE_TRABALHO",
           "cobertura_de_ids", "eventos_por_canal", "horarios_entre",
           "ler_diario", "noite_esperada", "noite_rodou", "noites_puladas",
           "noites_sem_conferencia"]
