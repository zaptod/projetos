# -*- coding: utf-8 -*-
"""A TRAVA CENTRAL das postagens: UMA fonte da verdade para "agora pode?".

A lei (CLAUDE.md, secao 4): nada de reiniciar app/carteiro, aplicar entrega,
rodar suite ou render pesado de `post-12` a `post+18` min de uma postagem. Ate
26/10/2026 cada ferramenta tinha de "lembrar" da regra, e tres agentes rodaram
suites e renders dentro das janelas no mesmo dia. Havia ate TRES copias da
conta (`supervisor.janela_das_postagens`, `pedidos.na_janela_das_postagens`,
`bluelock.comum.janela_das_postagens`), as duas ultimas lendo a grade da
plataforma inteira em vez da de cada canal.

Agora ha esta. Ela olha as grades REAIS de quem publica no dia (por data, ver
`builds.grade.tabela_do_canal`: duelos 8/dia e historias 3+1 desde 27/10) mais
a serie do Blue Lock (20:37), e tambem a publicacao em voo (processo
`postar.py`/`publicar` vivo), que vale mesmo fora do relogio.

    python -m builds.janela agora            pode? ate quando?
    python -m builds.janela proxima          a proxima janela
    python -m builds.janela esperar --max 1800

Sai com 0 (pode) ou 2 (janela / publicando) — serve em script.

O QUE FICA DE FORA, DE PROPOSITO: o que e agendado PARA a postagem — o
`postar.py` e as tarefas do Agendador, a geracao da madrugada (`main.py noite`,
01h-06h) e o subir de um servico que CAIU (`seguro(janela=False)`). Bloquea-los
pararia a propria publicacao. Tambem fica fora o clique deliberado do Adrian
no app (botao "gravar duelo").
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta

ANTES_MIN = 12
DEPOIS_MIN = 18


def horarios_do_dia(dia) -> list[datetime]:
    """Todos os instantes de postagem do calendario de `dia` (date/datetime),
    sem repetir, em ordem: a grade real de cada canal em cada plataforma mais
    a serie do Blue Lock."""
    from random_builds.builds import grade
    base = datetime(dia.year, dia.month, dia.day)
    horas = set()
    for canal in grade.CANAIS:
        for plataforma in grade.PLATAFORMAS:
            horas.update(grade.horas_do_canal(canal, plataforma, base))
    for plataforma in grade.PLATAFORMAS:
        horas.update(grade.horas_da_serie(plataforma))
    return sorted(base.replace(hour=h, minute=grade.minuto(h)) for h in horas)


def _janelas_em_volta(agora: datetime, antes: int, depois: int):
    """[(inicio, fim, post)] ordenadas, dos dias -1, 0 e +1 (a virada da
    meia-noite). Fim exclusivo: `post+depois` ja esta livre."""
    janelas = []
    for d in (-1, 0, 1):
        for post in horarios_do_dia((agora + timedelta(days=d)).date()):
            janelas.append((post - timedelta(minutes=antes),
                            post + timedelta(minutes=depois), post))
    return sorted(janelas)


def publicacao_em_voo(processos=None) -> bool:
    """Ha publicacao rodando agora (processo do postar.py / publicar)?
    Lista vazia = nao consegui ler = nao acuso."""
    try:
        from coordenador.supervisor import processos_windows, publicacao_rodando
        lista = processos_windows() if processos is None else processos
        return publicacao_rodando(lista)
    except Exception:                                          # noqa: BLE001
        return False


def em_janela(agora: datetime | None = None, *, antes: int = ANTES_MIN,
              depois: int = DEPOIS_MIN, olhar_voo: bool = True,
              em_voo=publicacao_em_voo) -> tuple[bool, str, datetime | None]:
    """(dentro, motivo, ate_quando). Fora da janela: (False, "", None).

    `ate_quando` e o fim da janela (emendando as vizinhas que se tocam); com
    publicacao em voo e fora do relogio e `None` (nao se sabe). `antes` e
    `depois` em minutos: o padrao e a lei (12 e 18); quem dura mais pede mais
    `antes` (a suite inteira). `olhar_voo=False` so olha o relogio.
    """
    agora = agora or datetime.now()
    janelas = _janelas_em_volta(agora, antes, depois)
    atual = next(((i, f, p) for i, f, p in janelas if i <= agora < f), None)
    if atual is not None:
        _i, fim, post = atual
        for i2, f2, _p2 in janelas:                  # emenda as que se tocam
            if i2 <= fim < f2:
                fim = f2
        minutos = int(abs((post - agora).total_seconds()) // 60)
        quando = (f"em {minutos} min" if post > agora else f"há {minutos} min")
        return (True, f"janela das postagens ({post:%H:%M}, {quando}); "
                      f"livre às {fim:%H:%M}", fim)
    if olhar_voo and em_voo():
        return True, "publicação em andamento (postar.py vivo)", None
    return False, "", None


def proxima_janela(agora: datetime | None = None, *, antes: int = ANTES_MIN,
                   depois: int = DEPOIS_MIN):
    """(inicio, fim, post) da janela em curso ou da proxima a comecar."""
    agora = agora or datetime.now()
    for i, f, p in _janelas_em_volta(agora, antes, depois):
        if f > agora:
            return i, f, p
    raise ValueError("grade vazia")                         # pragma: no cover


def esperar_fora_da_janela(max_s: float = 1800, *, agora=datetime.now,
                           dormir=time.sleep, passo_s: float = 30,
                           antes: int = ANTES_MIN, depois: int = DEPOIS_MIN,
                           olhar_voo: bool = True,
                           em_voo=publicacao_em_voo) -> bool:
    """Espera ate estar livre. True = livre; False = nao ficou livre em
    `max_s` segundos (nao espera por uma janela que termina depois do prazo:
    devolve False na hora, sem dormir a toa)."""
    gasto = 0.0
    while True:
        dentro, _motivo, ate = em_janela(agora(), antes=antes, depois=depois,
                                         olhar_voo=olhar_voo, em_voo=em_voo)
        if not dentro:
            return True
        if ate is not None:
            falta = (ate - agora()).total_seconds() + 1
            if gasto + falta > max_s:                # nao vai ficar livre a tempo
                return False
            espera = min(falta, 60.0)
        else:                                        # em voo: nao se sabe quando acaba
            if gasto + passo_s > max_s:
                return False
            espera = passo_s
        dormir(espera)
        gasto += espera


def recusa(ferramenta: str, agora: datetime | None = None, **kw) -> str | None:
    """A frase de recusa de uma ferramenta pesada, ou `None` se pode."""
    dentro, motivo, ate = em_janela(agora, **kw)
    if not dentro:
        return None
    return (f"{ferramenta} recusado: {motivo}. Espere "
            f"(`python -m builds.janela esperar`) ou use --forcar "
            f"se for de propósito.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m builds.janela")
    sub = parser.add_subparsers(dest="acao", required=True)
    sub.add_parser("agora")
    sub.add_parser("proxima")
    esp = sub.add_parser("esperar")
    esp.add_argument("--max", type=float, default=1800, dest="maximo")
    args = parser.parse_args(argv)
    if args.acao == "agora":
        dentro, motivo, _ate = em_janela()
        print(f"NÃO PODE: {motivo}" if dentro else "pode (fora da janela)")
        i, f, p = proxima_janela()
        print(f"próxima janela: {i:%d/%m %H:%M} a {f:%H:%M} (postagem {p:%H:%M})")
        return 2 if dentro else 0
    if args.acao == "proxima":
        i, f, p = proxima_janela()
        print(f"{i:%d/%m %H:%M} a {f:%H:%M} (postagem {p:%H:%M})")
        return 0
    livre = esperar_fora_da_janela(args.maximo)
    print("livre" if livre else f"continua em janela depois de {args.maximo:.0f} s")
    return 0 if livre else 2


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(main())
