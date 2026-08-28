"""Historico append-only da geracao de identidade.

A fila (`queue.json`) diz o estado AGORA; ela e reescrita a cada transicao e
por isso nao serve para responder "isso piorou?". Este arquivo guarda o que
aconteceu, uma linha por evento, e e o que permite ver tendencia: a espera do
Digen dobrou? a taxa de sucesso caiu depois do ultimo deploy deles?

Formato JSONL de proposito: escrita e um append (nao ha read-modify-write, logo
nao precisa de lock nem pode corromper o que ja foi gravado), e uma linha
quebrada nao leva o arquivo inteiro junto.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone

from . import config

ARQUIVO = config.IDENTITY_DIR / "history.jsonl"

# Eventos gravados. `enviado`/`retomado` abrem uma tentativa; os outros fecham.
ENVIADO, RETOMADO = "enviado", "retomado"
PRONTO, BAIXADO, CONCLUIDO = "pronto", "baixado", "concluido"
ESTOUROU, FALHOU = "estourou", "falhou"
# Origem nao comprovada (nada baixado) e artefato tirado da build depois.
ORIGEM_RECUSADA, QUARENTENA = "origem_recusada", "quarentena"
APROVADO = "aprovado"

ABERTURA = (ENVIADO, RETOMADO)
FECHAMENTO = (CONCLUIDO, ESTOUROU, FALHOU)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registrar(generation_id: str, evento: str, **extra) -> dict:
    """Anexa um evento. Nunca levanta: monitoramento nao pode derrubar o worker."""
    linha = {"ts": _agora(), "generation_id": generation_id, "evento": evento}
    linha.update(extra)
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQUIVO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return linha


def ler(limite: int | None = None) -> list[dict]:
    """Eventos, do mais antigo para o mais novo. Linha corrompida e pulada."""
    if not ARQUIVO.is_file():
        return []
    eventos = []
    try:
        with open(ARQUIVO, encoding="utf-8-sig") as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    eventos.append(json.loads(linha))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return eventos[-limite:] if limite else eventos


def _quando(evento: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(evento["ts"])
    except (KeyError, ValueError):
        return None


def esperas(eventos: list[dict] | None = None) -> list[float]:
    """Segundos entre abrir a tentativa e o video ficar pronto.

    Pareado por generation_id: um `pronto` fecha a abertura mais recente
    daquele job. Abertura sem `pronto` (estouro, falha) nao entra - a mediana
    aqui e "quanto demora quando da certo".
    """
    eventos = ler() if eventos is None else eventos
    aberto: dict[str, datetime] = {}
    saida = []
    for evento in eventos:
        quando = _quando(evento)
        gid = evento.get("generation_id")
        if quando is None or not gid:
            continue
        if evento.get("evento") in ABERTURA:
            aberto[gid] = quando
        elif evento.get("evento") == PRONTO and gid in aberto:
            saida.append((quando - aberto.pop(gid)).total_seconds())
    return saida


def resumo(eventos: list[dict] | None = None) -> dict:
    eventos = ler() if eventos is None else eventos
    contagem: dict[str, int] = {}
    for evento in eventos:
        nome = evento.get("evento", "?")
        contagem[nome] = contagem.get(nome, 0) + 1

    tempos = esperas(eventos)
    fechados = sum(contagem.get(e, 0) for e in FECHAMENTO)
    concluidos = contagem.get(CONCLUIDO, 0)
    ultimo = _quando(eventos[-1]) if eventos else None

    return {
        "eventos": len(eventos),
        "contagem": contagem,
        "tentativas_fechadas": fechados,
        "concluidos": concluidos,
        "taxa_sucesso": round(concluidos / fechados, 3) if fechados else None,
        "espera_amostras": len(tempos),
        "espera_mediana_s": round(statistics.median(tempos), 1) if tempos else None,
        "espera_max_s": round(max(tempos), 1) if tempos else None,
        "ultimo_evento_em": ultimo.isoformat(timespec="seconds") if ultimo else None,
    }


def ultima_espera_por_slot(eventos: list[dict] | None = None) -> dict[tuple[str, str], float]:
    """{(generation_id, slot): espera_s do ULTIMO `pronto`}.

    O artefato no disco veio da ultima tentativa que ficou pronta, entao e a
    espera dela que diz se houve geracao de verdade ou so algo que ja estava
    na tela (auditoria de origem).
    """
    eventos = ler() if eventos is None else eventos
    saida: dict[tuple[str, str], float] = {}
    # Como a tentativa abriu. Depois de `retomado` o video ja podia estar
    # pronto no espaco: 4 s ali e retomada, nao geracao - e nao mede nada.
    abertura: dict[tuple[str, str], str] = {}
    for evento in eventos:
        gid, slot = evento.get("generation_id"), evento.get("slot")
        if not gid or not slot:
            continue
        chave = (gid, slot)
        nome = evento.get("evento")
        if nome in ABERTURA:
            abertura[chave] = nome
            continue
        if nome != PRONTO:
            continue
        espera = evento.get("espera_s")
        if abertura.get(chave) == RETOMADO or not isinstance(espera, (int, float)):
            # O ultimo `pronto` manda: sem medida valida, a anterior nao vale.
            saida.pop(chave, None)
            continue
        saida[chave] = float(espera)
    return saida
