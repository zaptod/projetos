"""Sobe as capas das historias que sairam sem capa (05/10/2026).

Ate 05/10 o canal "historinhas" nao tinha a verificacao que libera capa
personalizada: ~220 videos de historias foram publicados e a capa voltou com
403. As capas estao no disco (historias/outputs/<historia>/capa_pNN.jpg); isto
as sobe pela API oficial (`thumbnails.set`), do video mais NOVO para o mais
velho.

E de graca: a cota da API e um limite diario gratuito (10.000 unidades; cada
capa custa 50). Os uploads das historias saem pelo navegador, entao a cota
sobra; mesmo assim o lote para com folga (`--limite`) e para NA HORA no
primeiro aviso de cota. O progresso fica em `_capas_atrasadas.json`: rodar de
novo continua de onde parou.

    python -X utf8 ferramentas/capas_atrasadas.py --ver
    python -X utf8 ferramentas/capas_atrasadas.py --limite 120
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "random_builds"))

PUBLICAR = RAIZ / "historias" / "outputs" / "_publicar"
LEDGER = PUBLICAR / "publicados.jsonl"
FEITAS = PUBLICAR / "_capas_atrasadas.json"
OUTPUTS = RAIZ / "historias" / "outputs"
LIMITE_PADRAO = 120          # 120 x 50 = 6.000 de 10.000: sobra para metricas e capas do dia


def pendentes(ledger: Path = LEDGER, feitas: dict | None = None) -> list[dict]:
    """Videos de historias no YouTube ainda sem capa, do mais novo ao mais velho."""
    feitas = feitas or {}
    por_id: dict[str, dict] = {}
    for linha in ledger.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(linha)
        except ValueError:
            continue
        yid = item.get("youtube_id") or ""
        if item.get("plataforma") != "youtube" or not re.fullmatch(r"[\w-]{11}", yid):
            continue
        achado = re.fullmatch(r"(historia_\d+):[^:]+:p(\d+)", item.get("video_id") or "")
        if not achado:
            continue
        capa = OUTPUTS / achado.group(1) / f"capa_p{int(achado.group(2)):02d}.jpg"
        por_id[yid] = {"youtube_id": yid, "video_id": item["video_id"],
                       "quando": item.get("quando") or "", "capa": capa}
    fila = [v for k, v in por_id.items() if k not in feitas]
    return sorted(fila, key=lambda v: v["quando"], reverse=True)


def _ler_feitas() -> dict:
    try:
        return json.loads(FEITAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_feitas(feitas: dict) -> None:
    tmp = FEITAS.with_suffix(".tmp")
    tmp.write_text(json.dumps(feitas, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FEITAS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limite", type=int, default=LIMITE_PADRAO)
    ap.add_argument("--ver", action="store_true", help="so lista, nao sobe nada")
    args = ap.parse_args(argv)

    from builds.publicar import youtube

    feitas = _ler_feitas()
    fila = pendentes(feitas=feitas)
    sem_arquivo = [v for v in fila if not v["capa"].exists()]
    fila = [v for v in fila if v["capa"].exists()]
    print(f"{len(fila)} video(s) sem capa com a capa no disco; "
          f"{len(sem_arquivo)} sem arquivo de capa; {len(feitas)} ja feitas antes")
    if args.ver:
        for v in fila[:10]:
            print(f"  {v['quando']}  {v['video_id']}  {v['youtube_id']}")
        return 0

    enviadas = 0
    for v in fila[:max(0, args.limite)]:
        falas: list[str] = []
        ok = youtube.definir_capa(v["youtube_id"], v["capa"], canal="historias",
                                  log=falas.append)
        texto = " ".join(falas)
        if ok:
            enviadas += 1
            feitas[v["youtube_id"]] = {"video_id": v["video_id"],
                                       "em": time.strftime("%Y-%m-%dT%H:%M:%S")}
            _gravar_feitas(feitas)
            print(f"  ok  {v['video_id']}  {v['youtube_id']}")
            continue
        print(f"  NAO {v['video_id']}  {v['youtube_id']}: {texto[:300]}")
        if "quota" in texto.lower():
            print("cota do dia acabou; amanha continua de onde parou")
            break
        if "(404)" in texto:      # video apagado do canal: nao ha o que capar
            feitas[v["youtube_id"]] = {"video_id": v["video_id"], "sumiu": True}
            _gravar_feitas(feitas)
    print(f"{enviadas} capa(s) enviada(s); faltam {len(fila) - enviadas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
