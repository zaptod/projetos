# -*- coding: utf-8 -*-
"""YouTube Analytics do canal de duelos SEM gravar nada em disco (so le a API).

    cd E:\\projetos
    python .claude/skills/metricas-youtube-analytics/scripts/analytics_direto.py dia --dias 14
    python .claude/skills/metricas-youtube-analytics/scripts/analytics_direto.py formato --de 2026-10-13 --ate 2026-10-19
    python .claude/skills/metricas-youtube-analytics/scripts/analytics_direto.py trafego --dias 28

dia      views, minutos, % assistido e inscritos ganhos/perdidos do CANAL por dia
formato  mediana de views e de % assistido por formato (duelo/build/estreia),
         casando o video da Analytics com o `origem` do ledger pelo youtube_id
trafego  de onde vem a view (SHORTS, YT_SEARCH...)

Diferente de `main.py metricas --atualizar` (que grava em outputs/_metricas e e o
servico do dia), aqui nada e gravado: serve para OLHAR. A Analytics atrasa ~3
dias: o ultimo dia completo costuma ser hoje-3.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, timedelta


def _consultar(canal: str, **params) -> dict:
    import requests
    from builds.publicar import metricas
    token = metricas._token(canal)[0]
    r = requests.get(metricas.API_ANALYTICS, timeout=60,
                     headers={"Authorization": f"Bearer {token}"},
                     params={"ids": "channel==MINE", **params})
    if not r.ok:
        # 403 com "escopo" ja foi a API DESLIGADA no projeto do Google Cloud (11/09).
        raise SystemExit(f"Analytics {r.status_code}: {r.text[:300]}")
    return r.json()


def _janela(a) -> tuple[str, str]:
    ate = date.fromisoformat(a.ate) if a.ate else date.today() - timedelta(days=3)
    de = date.fromisoformat(a.de) if a.de else ate - timedelta(days=a.dias - 1)
    return de.isoformat(), ate.isoformat()


def por_dia(a) -> None:
    de, ate = _janela(a)
    j = _consultar(a.canal, startDate=de, endDate=ate, dimensions="day", sort="day",
                   metrics="views,estimatedMinutesWatched,averageViewPercentage,"
                           "subscribersGained,subscribersLost")
    linhas = j.get("rows") or []
    print(f"canal {a.canal}, {de} a {ate} ({len(linhas)} dias com linha)")
    print("dia         views  minutos  %assist  +insc  -insc")
    for d, v, m, p, g, l in linhas:
        print(f"{d}  {v:6}  {m:7}  {p:6.1f}  {g:5}  {l:5}")
    if linhas:
        views = [r[1] for r in linhas]
        print(f"media {statistics.mean(views):.0f}/dia, mediana {statistics.median(views):.0f}, "
              f"inscritos liquidos {sum(r[4] - r[5] for r in linhas):+d}")
    else:
        print("ZERO linhas: nao e 'zero views' — confira a janela (atraso de ~3 dias) e o token.")


def por_formato(a) -> None:
    from builds.publicar import metricas
    de, ate = _janela(a)
    j = _consultar(a.canal, startDate=de, endDate=ate, dimensions="video", sort="-views",
                   maxResults=200, metrics="views,averageViewPercentage")
    origem = {l.get("youtube_id"): l.get("origem") for l in metricas.publicados(a.canal)
              if l.get("youtube_id")}
    grupos: dict = {}
    sem_formato = 0
    for vid, views, pct in j.get("rows") or []:
        f = origem.get(vid)
        if not f:
            sem_formato += 1
            continue
        grupos.setdefault(f, []).append((views, pct))
    print(f"canal {a.canal}, {de} a {ate}: views e % assistido POR VIDEO (mediana)")
    for f, vals in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
        views = [v for v, _ in vals]
        pcts = [p for v, p in vals if v >= 20]       # % de video com <20 views nao diz nada
        print(f"  {f:8} n={len(vals):3}  views {statistics.median(views):7.1f}  "
              f"% assistido {statistics.median(pcts) if pcts else float('nan'):5.1f} "
              f"(n={len(pcts)} com 20+ views)")
    print(f"  sem formato (sem youtube_id no ledger): {sem_formato}")
    print("  So vem linha de video VISTO na janela; privado/0 view nao entra (e nao e 0%).")


def trafego(a) -> None:
    de, ate = _janela(a)
    j = _consultar(a.canal, startDate=de, endDate=ate, dimensions="insightTrafficSourceType",
                   metrics="views", sort="-views")
    total = sum(r[1] for r in j.get("rows") or []) or 1
    print(f"canal {a.canal}, {de} a {ate}")
    for fonte, v in j.get("rows") or []:
        print(f"  {fonte:22} {v:7}  {100 * v / total:5.1f}%")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("modo", choices=("dia", "formato", "trafego"))
    p.add_argument("--canal", default="builds")
    p.add_argument("--dias", type=int, default=14)
    p.add_argument("--de", default="")
    p.add_argument("--ate", default="")
    a = p.parse_args(argv)
    {"dia": por_dia, "formato": por_formato, "trafego": trafego}[a.modo](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
