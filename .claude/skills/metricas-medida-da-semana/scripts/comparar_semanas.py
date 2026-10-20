# -*- coding: utf-8 -*-
"""A medida da semana do PLANO: duelos publicados numa semana x na anterior. So le o disco.

    cd E:\\projetos
    python .claude/skills/metricas-medida-da-semana/scripts/comparar_semanas.py --inicio 2026-10-20
    python .claude/skills/metricas-medida-da-semana/scripts/comparar_semanas.py --inicio 2026-10-20 --formato duelo --plataforma tiktok

Compara os videos PUBLICADOS em [inicio, inicio+7) contra [inicio-7, inicio), pela coleta
salva do servico do dia (YouTube: outputs/_metricas; TikTok: outputs/_metricas_tiktok).
So entra video com 3+ dias de IDADE na hora da coleta (antes disso ainda junta view).
Mediana por video (o viral nao puxa), % assistido so de video com 20+ views, e o rotulo
de certeza da analise (`analise.confianca`: claro / provavel / incerto, Mann-Whitney).
Inscritos por mil views (a medida da semana 3) vem do canal: rode o
`metricas-youtube-analytics/scripts/analytics_direto.py dia` na mesma janela.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, datetime, timedelta

MADURO_DIAS = 3
MIN_VIEWS_RETENCAO = 20


def _dt(texto) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--inicio", required=True, help="1o dia da semana medida (AAAA-MM-DD)")
    p.add_argument("--formato", default="duelo")
    p.add_argument("--plataforma", default="youtube", choices=("youtube", "tiktok"))
    p.add_argument("--canal", default="builds")
    a = p.parse_args(argv)

    from builds.publicar import analise, metricas, tiktok_metricas
    salvas = (metricas.carregar_salvas(a.canal) if a.plataforma == "youtube"
              else tiktok_metricas.carregar_salvas(a.canal))
    ini = datetime.combine(date.fromisoformat(a.inicio), datetime.min.time())
    janelas = {"anterior": (ini - timedelta(days=7), ini), "semana": (ini, ini + timedelta(days=7))}
    grupos: dict = {k: {"views": [], "pct": [], "imaturos": 0, "privados": 0} for k in janelas}
    for d in salvas:
        if d.get("origem") != a.formato:
            continue
        quando = _dt(d.get("quando"))
        if quando is None:
            continue
        for nome, (de, ate) in janelas.items():
            if not (de <= quando < ate):
                continue
            g = grupos[nome]
            if a.plataforma == "youtube" and str(d.get("privacidade") or d.get("visibilidade")
                                                  or "public") != "public":
                g["privados"] += 1
                continue
            coletado = _dt(d.get("atualizado")) or datetime.now()
            if (coletado - quando).days < MADURO_DIAS:
                g["imaturos"] += 1
                continue
            v = d.get("views") or 0
            g["views"].append(v)
            if v >= MIN_VIEWS_RETENCAO and d.get("media_percentual") is not None:
                g["pct"].append(float(d["media_percentual"]))

    print(f"{a.formato} no {a.plataforma} ({a.canal}), por video publicado na janela:")
    for nome, (de, ate) in janelas.items():
        g = grupos[nome]
        med = statistics.median(g["views"]) if g["views"] else None
        pct = statistics.median(g["pct"]) if g["pct"] else None
        print(f"  {nome:8} {de:%d/%m}–{(ate - timedelta(days=1)):%d/%m}: n={len(g['views']):3} "
              f"views/video {med if med is not None else '—'}  "
              f"% assistido {f'{pct:.1f}' if pct is not None else '—'} (n={len(g['pct'])})  "
              f"zeros={sum(1 for v in g['views'] if v == 0)}  "
              f"ainda juntando={g['imaturos']}  privados fora={g['privados']}")
    a_, b_ = grupos["anterior"]["views"], grupos["semana"]["views"]
    print(f"  certeza (views): {analise.confianca(a_, b_)}"
          + ("" if a_ and b_ else "  — um dos lados VAZIO: nao ha comparacao, nao e 'sem efeito'"))
    if grupos["semana"]["imaturos"]:
        print(f"  {grupos['semana']['imaturos']} video(s) da semana com < {MADURO_DIAS} dias: "
              "meça de novo depois.")
    return 0 if a_ and b_ else 1


if __name__ == "__main__":
    sys.exit(main())
