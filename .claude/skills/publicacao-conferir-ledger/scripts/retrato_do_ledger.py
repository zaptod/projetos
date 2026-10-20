# -*- coding: utf-8 -*-
"""O que o canal de builds (duelos) publicou, horario por horario. SO LE.

    cd E:\\projetos
    python .claude/skills/publicacao-conferir-ledger/scripts/retrato_do_ledger.py --dias 3

Usa as respostas UNICAS da publicacao — nunca um criterio novo:
  publicado?        builds.publicar.metricas.publicado(linha)
  que horario?      builds.publicar.conferencia.chave_do_horario(quando, plataforma)
  titulo igual?     builds.publicar.titulos.chave(titulo)
  bloqueado?        builds.publicar.desfecho.marcas(canal, plataforma)
Nao abre navegador, nao vai a rede, nao grava nada (nem no atividade.jsonl).
Rode de E:\\projetos para ler o ledger REAL (o pacote `builds` instalado aponta
para la; numa worktree, `outputs/` esta vazio).
"""
from __future__ import annotations

import argparse
import collections
import sys
from datetime import datetime, timedelta


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--canal", default="builds", choices=("builds", "historias"))
    p.add_argument("--dias", type=int, default=3, help="dias de grade para tras")
    p.add_argument("--formato", default="", help="so este formato (duelo, build, estreia)")
    a = p.parse_args(argv)

    from builds import grade
    from builds.publicar import conferencia, desfecho, metricas, titulos

    linhas = metricas.publicados(a.canal)
    print(f"ledger: {metricas.registro_do_canal(a.canal)}  ({len(linhas)} linhas)")
    hoje = datetime.now().date()
    inicio = hoje - timedelta(days=a.dias)
    por_horario: dict = collections.defaultdict(list)
    nao_publicadas = 0
    for linha in linhas:
        if a.formato and linha.get("origem") != a.formato:
            continue
        plat = linha.get("plataforma") or "?"
        chave = conferencia.chave_do_horario(linha.get("quando"), plat)
        if not chave:
            continue
        dia, hora = chave
        dia_d = dia if hasattr(dia, "year") else datetime.fromisoformat(str(dia)).date()
        if dia_d < inicio:
            continue
        if not metricas.publicado(linha):
            nao_publicadas += 1
            continue
        por_horario[(str(dia_d), hora, plat)].append(linha)

    dias = sorted({k[0] for k in por_horario} | {str(inicio + timedelta(days=i))
                                                 for i in range(a.dias + 1)})
    agora = datetime.now()
    for dia in dias:
        print(f"\n== dia de grade {dia}")
        for plat in grade.PLATAFORMAS:
            horas = grade.horas_da_plataforma(plat)
            abre = conferencia.abertura_e_fechamento(plat)[0]
            cheios, vazios, por_vir = [], [], []
            for h in horas:
                saiu = por_horario.get((dia, h, plat), [])
                # o dia de grade abre em `abre`: horas antes dela sao do dia seguinte
                quando = datetime.fromisoformat(dia).replace(hour=h, minute=grade.minuto(h))
                if h < abre:
                    quando += timedelta(days=1)
                if saiu:
                    cheios.append(grade.horario(h))
                elif quando > agora:
                    por_vir.append(grade.horario(h))
                else:
                    vazios.append(grade.horario(h))
                for l in saiu:
                    print(f"  {plat:7} {grade.horario(h)}  {str(l.get('quando'))[11:16]}  "
                          f"{l.get('origem', '?'):8} {l.get('video_id', '?'):34} "
                          f"{str(l.get('titulo'))[:50]}")
                if len(saiu) > 1:
                    # Pode ser de proposito (divida do YouTube dos builds sobe junto
                    # com o novo; reposicao no mesmo slot). Repetido de verdade e o
                    # MESMO video_id duas vezes.
                    ids = [l.get("video_id") for l in saiu]
                    tipo = "MESMO VIDEO 2x" if len(set(ids)) < len(ids) else "videos diferentes"
                    print(f"  !! {plat} {grade.horario(h)}: {len(saiu)} linhas ({tipo})")
            print(f"  {plat}: {len(cheios)}/{len(horas) - len(por_vir)} horarios vencidos"
                  + (f"; VAZIOS: {', '.join(vazios)}" if vazios else "")
                  + (f"; por vir: {len(por_vir)}" if por_vir else ""))
    print(f"\nlinhas que NAO contam como publicadas na janela: {nao_publicadas}")

    vistos = collections.Counter(titulos.chave(l.get("titulo") or "") for l in linhas
                                 if metricas.publicado(l) and l.get("plataforma") == "youtube")
    repetidos = {k: n for k, n in vistos.items() if n > 1 and k}
    print(f"titulos repetidos no YouTube (vida toda): {len(repetidos)}"
          + (f" — ex.: {list(repetidos)[:3]}" if repetidos else ""))
    for plat in grade.PLATAFORMAS:
        try:
            m = desfecho.marcas(a.canal, plat)
        except Exception as exc:  # noqa: BLE001  (lista ilegivel = guarda fechada)
            print(f"a conferir {plat}: ILEGIVEL ({exc}) — a fila desse destino esta fechada")
            continue
        print(f"a conferir {plat}: {len(m)}"
              + "".join(f"\n   {k}: {v.get('estado')}" for k, v in list(m.items())[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
