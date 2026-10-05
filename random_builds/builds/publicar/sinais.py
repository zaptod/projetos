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
#
# "NOITE" FICOU NO NOME, MAS A CONFERENCIA E DE DIA. Ate 29/09/2026 ela
# rodava de madrugada (01:28 a 05:20); desde 30/09 (edccded, lote de dia)
# roda no SERVICO DO DIA das historias (`contos.pipeline.agenda.
# _servico_do_dia`), no 1o disparo da janela pesada — 07:02, e a conferencia
# em si as 07:04-07:35 depois da coleta de metricas. Estas contas seguiram
# exigindo uma rodada ANTES das 06:37, e o alarme "noite sem conferencia" foi
# ao celular todo dia de 02 a 05/10 por uma conferencia que tinha rodado
# (varredura de 05/10/2026, item 14). Agora quem diz que a conferencia do dia
# rodou e a ORIGEM da rodada (`servico`), gravada na ficha; o relogio so vale
# para a ficha de antes da origem existir.

# Quem conferiu. So a rodada do servico do dia cobre o dia; o botao do painel
# e a linha de comando sao conferencias feitas a mao.
ORIGEM_SERVICO = "servico"
ORIGEM_PAINEL = "painel"
ORIGEM_MANUAL = "manual"
ORIGENS = (ORIGEM_SERVICO, ORIGEM_PAINEL, ORIGEM_MANUAL)

# O 1o disparo da janela pesada, quando o config das historias nao abre.
# A fonte e `historias/config/agenda.json` (`horas` + `janela_pesada`).
PRIMEIRO_DISPARO_PADRAO = (7, 2)
# Quanto depois do 1o disparo a conferencia do dia ja devia ter rodado. O
# servico coleta metrica antes (YouTube ~7 min, TikTok ate 12 min por canal)
# e a conferencia saiu as 07:04-07:35 de 01 a 05/10. Na transicao, uma rodada
# da madrugada que emenda segura a trava e o disparo das 07:02 sai; o das
# 08:02 faz o servico. Tres horas cobrem isso sem acusar falta de verdade.
FOLGA_DO_SERVICO = timedelta(hours=3)


def _config_da_agenda():
    from pathlib import Path
    return (Path(__file__).resolve().parents[3] / "historias" / "config"
            / "agenda.json")


def primeiro_disparo(caminho=None) -> tuple:
    """`(hora, minuto)` do 1o disparo da janela pesada das historias.

    E ele que faz o servico do dia (metrica, tempos, conferencia). Lido do
    config, para a janela mudar sem o alarme voltar a mentir; config que nao
    abre ou sem disparo na janela: `PRIMEIRO_DISPARO_PADRAO`. Nunca levanta.
    """
    try:
        with open(caminho or _config_da_agenda(), encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        janela = dados.get("janela_pesada") or {}
        inicio = int(janela.get("inicio", 0)) % 24
        fim = int(janela.get("fim", 0)) % 24
        disparos = []
        for item in dados.get("horas") or []:
            texto = str(item).strip()
            hora, _, minuto = texto.partition(":")
            # Hora cheia dispara as :20 (`agenda.MINUTO_PADRAO`).
            hora, minuto = int(hora), int(minuto) if minuto else 20
            if not 0 <= hora < 24:
                continue
            if inicio == fim:
                dentro = True
            elif inicio < fim:
                dentro = inicio <= hora < fim
            else:
                dentro = hora >= inicio or hora < fim
            if dentro:
                # Ordem do DIA DA JANELA: a que atravessa a meia-noite
                # comeca no `inicio`, nao na hora 0.
                disparos.append(((hora - inicio) % 24, minuto, hora))
        if disparos:
            _ordem, minuto, hora = min(disparos)
            return hora, minuto
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return PRIMEIRO_DISPARO_PADRAO


def limite_do_servico(caminho=None) -> str:
    """`'HH:MM'`: a hora em que a conferencia do dia ja devia ter rodado."""
    hora, minuto = primeiro_disparo(caminho)
    limite = datetime(2000, 1, 1, hora, minuto) + FOLGA_DO_SERVICO
    if limite.day != 1:
        return "23:59"
    return limite.strftime("%H:%M")


def noite_esperada(agora: datetime | None = None, *,
                   limite: str | None = None) -> date:
    """O ultimo dia que ja devia ter deixado ficha de conferencia do servico.

    A conferencia do dia D roda no servico do dia (1o disparo da janela, as
    07:02) e tem `FOLGA_DO_SERVICO` para acabar: ate as 10:02 a ultima que
    ja devia existir e a de D-1; dali em diante, a de D. (Ate 30/09/2026 era
    a madrugada, e a virada era a abertura do dia de grade, 06:37.)
    """
    agora = agora or datetime.now()
    hora, minuto = (limite or limite_do_servico()).split(":")
    vira = agora.replace(hour=int(hora), minute=int(minuto), second=0,
                         microsecond=0)
    return agora.date() if agora >= vira else agora.date() - timedelta(days=1)


def _dia(ficha) -> date | None:
    try:
        return date.fromisoformat(str((ficha or {}).get("dia"))[:10])
    except (TypeError, ValueError, AttributeError):
        return None


def noite_rodou(ficha, *, limite: str | None = None) -> bool | None:
    """A ficha do dia teve a rodada do SERVICO DO DIA?

    A ficha do dia e regravada por qualquer rodada, inclusive a do botao do
    painel as 14:00; sem isto, ela apagaria o rastro do servico que faltou.

    - rodada com origem `servico` cobre o dia, a qualquer hora (servico que
      atrasou ainda e servico);
    - rodada com origem `painel`/`manual` NAO cobre, nem de madrugada;
    - rodada sem origem (ficha de antes de 05/10/2026) cobre se rodou antes
      de `limite_do_servico()` — as de 02 a 05/10 (07:04-07:35) e as da
      madrugada de setembro. Uma conferencia a mao antes das 10:02 nessas
      fichas passa por servico: nao ha como separar, e o erro e o do lado
      quieto so para fichas que ja passaram.
    - ficha sem `rodadas` (antes de 28/09/2026): `None`, nao sei;
    - `rodadas` vazia: `False`.
    """
    rodadas = (ficha or {}).get("rodadas") if isinstance(ficha, dict) else None
    if not isinstance(rodadas, list):
        return None
    origens = ficha.get("origens")
    if not isinstance(origens, list) or len(origens) != len(rodadas):
        origens = [None] * len(rodadas)
    corte = None
    for rodada, origem in zip(rodadas, origens):
        if origem == ORIGEM_SERVICO:
            return True
        if origem is None:
            corte = corte or limite or limite_do_servico()
            if str(rodada)[:5] < corte:
                return True
    return False


def noites_sem_conferencia(ficha, agora: datetime | None = None
                           ) -> dict | None:
    """`None` quando o ultimo dia esperado tem ficha do servico; senao, o buraco.

    `ficha` e a mais recente do canal (a de erro conta: rodou e falhou e
    outra pergunta, com alerta proprio). Sem ficha nenhuma, `ultima` e
    `None` — nunca rodou tambem e dia sem conferencia (CASO ZERO acende).
    """
    limite = limite_do_servico()
    esperada = noite_esperada(agora, limite=limite)
    ultima = _dia(ficha)
    if ultima is not None and ultima > esperada:
        # Ficha de hoje antes do limite: o servico de hoje ainda esta na
        # folga. So a ficha mais recente e lida, entao o dia de ontem nao da
        # para julgar daqui (a conferencia de hoje julga, em `noites_puladas`).
        return None
    if ultima == esperada and noite_rodou(ficha, limite=limite) is not False:
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
           "FOLGA_DO_ID", "FOLGA_DO_SERVICO", "HORAS_DE_EVENTOS",
           "MINIMO_DE_HORAS_COBERTAS", "ORIGEM_MANUAL", "ORIGEM_PAINEL",
           "ORIGEM_SERVICO", "ORIGENS", "PRIMEIRO_DISPARO_PADRAO",
           "STATUS_DE_TRABALHO",
           "cobertura_de_ids", "eventos_por_canal", "horarios_entre",
           "ler_diario", "limite_do_servico", "noite_esperada",
           "noite_rodou", "noites_puladas", "noites_sem_conferencia",
           "primeiro_disparo"]
