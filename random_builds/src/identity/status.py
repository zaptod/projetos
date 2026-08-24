"""Visao operacional: onde cada geracao esta no caminho ate o video final.

A fila responde "o que falta fazer"; o disco responde "o que ficou pronto".
Os dois podem discordar, e e justamente a discordancia que interessa:

  - clipe no disco mas SEM o evento dele no edit_plan -> o re-render nao
    aconteceu (worker morto entre o download e o render, ou `--no-rerender`).
  - evento no plano mas o mp4 final mais VELHO que o clipe -> o plano foi
    remontado e a renderizacao nao terminou; o video que voce publicaria ainda
    e o antigo, sem o personagem.

Nenhum dos dois levanta erro em lugar nenhum - por isso precisam ser olhados.

Sao TRES clipes por geracao (personagem, arma, personagem+arma), entao tudo
aqui e por slot: uma geracao pode estar completa no personagem e devendo o
payoff final.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import artefato, config, history, queue, slots

PERFIS = ("celular", "normal")

# Margem antes de chamar um mp4 final de "desatualizado". O clipe e baixado e
# o re-render comeca em seguida, entao os mtimes ficam a segundos de distancia;
# comparar sem tolerancia acusaria granularidade de filesystem como problema.
# Um re-render que de fato nao rodou fica minutos ou horas para tras.
TOLERANCIA_MTIME = 5.0

# Abaixo disto o mp4 nao e video de verdade: download truncado ou pagina de
# erro salva como arquivo.
BYTES_MINIMOS = 10_000


def _slots_no_plano(out_dir: Path) -> dict | None:
    """{slot: True} para cada clipe que o edit_plan realmente usa."""
    caminho = out_dir / "edit_plan.json"
    if not caminho.is_file():
        return None
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            plano = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    presentes = {}
    for evento in plano.get("events", []):
        if evento.get("type") == "identity":
            presentes[evento.get("slot", slots.CHARACTER)] = True
    return presentes


def inventario() -> list[dict]:
    """Uma linha por geracao existente em outputs/."""
    fila = {}
    for job in queue.listar():
        fila.setdefault(job["generation_id"], {})[job["slot"]] = job["status"]

    linhas = []
    for out_dir in sorted(config.OUTPUTS.glob("generation_*")):
        gid = out_dir.name
        no_plano = _slots_no_plano(out_dir)

        clipes, bytes_por_slot = {}, {}
        mais_novo = 0.0
        for slot in slots.SLOTS:
            caminho = artefato.caminho(gid, slot)
            existe = caminho.is_file()
            clipes[slot] = existe
            bytes_por_slot[slot] = caminho.stat().st_size if existe else 0
            if existe:
                mais_novo = max(mais_novo, caminho.stat().st_mtime)

        finais, desatualizado = {}, False
        for perfil in PERFIS:
            final = out_dir / f"final_{perfil}.mp4"
            finais[perfil] = final.is_file()
            if mais_novo and final.is_file():
                if mais_novo - final.stat().st_mtime > TOLERANCIA_MTIME:
                    desatualizado = True

        linhas.append({
            "generation_id": gid,
            "fila": fila.get(gid, {}),
            "clipes": clipes,
            "bytes": bytes_por_slot,
            "no_plano": no_plano,
            "finais": finais,
            "final_desatualizado": desatualizado,
        })
    return linhas


def da_geracao(generation_id: str) -> dict | None:
    """A linha do inventario de uma geracao, ou None se ela nao existe."""
    for linha in inventario():
        if linha["generation_id"] == generation_id:
            return linha
    return None


def clipe_utilizavel(generation_id: str, slot: str = slots.CHARACTER) -> bool:
    """Ja existe um mp4 daquele slot que presta?

    O worker consulta ANTES de gerar. Sem isso, um job que ficou `pending` por
    acidente (worker morto depois do download, fila roubada por outro worker)
    manda gerar de novo um video que ja esta no disco - foi o que aconteceu com
    `generation_00014`, baixado duas vezes.
    """
    linha = da_geracao(generation_id)
    return bool(linha and linha["clipes"].get(slot)
                and linha["bytes"].get(slot, 0) >= BYTES_MINIMOS)


def esta_completo(generation_id: str, slot: str = slots.CHARACTER) -> bool:
    """Clipe no disco, dentro do edit_plan e refletido nos dois mp4 finais."""
    linha = da_geracao(generation_id)
    if not linha or not clipe_utilizavel(generation_id, slot):
        return False
    return bool((linha["no_plano"] or {}).get(slot)
                and all(linha["finais"].values())
                and not linha["final_desatualizado"])


def slots_faltando(generation_id: str) -> list[str]:
    """Slots sem clipe utilizavel - o que ainda falta gerar."""
    return [slot for slot in slots.SLOTS
            if not clipe_utilizavel(generation_id, slot)]


def inconsistencias(linhas: list[dict] | None = None) -> list[str]:
    """Os casos que ninguem reporta sozinho."""
    linhas = inventario() if linhas is None else linhas
    problemas = []
    for linha in linhas:
        gid = linha["generation_id"]
        tem_clipe = any(linha["clipes"].values())
        for slot in slots.SLOTS:
            if not linha["clipes"][slot]:
                continue
            if linha["bytes"][slot] < BYTES_MINIMOS:
                problemas.append(
                    f"{gid}[{slot}]: clipe suspeito ({linha['bytes'][slot]} "
                    "bytes) - download truncado")
            if linha["no_plano"] is not None and not linha["no_plano"].get(slot):
                problemas.append(
                    f"{gid}[{slot}]: clipe baixado mas fora do edit_plan - rode "
                    f"`python main.py generate-video --rerender {gid} "
                    "--refazer-edicao`")
        if linha["final_desatualizado"]:
            problemas.append(
                f"{gid}: mp4 final mais velho que o clipe - o re-render nao "
                f"terminou; rode `--rerender {gid} --refazer-edicao`")
        if tem_clipe and linha["no_plano"] and not all(linha["finais"].values()):
            faltam = [p for p, existe in linha["finais"].items() if not existe]
            problemas.append(f"{gid}: sem final_{'/'.join(faltam)}.mp4")
    return problemas


def _idade(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        quando = datetime.fromisoformat(iso)
    except ValueError:
        return "?"
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    segundos = (datetime.now(timezone.utc) - quando).total_seconds()
    if segundos < 90:
        return f"{segundos:.0f}s"
    if segundos < 5400:
        return f"{segundos / 60:.0f}min"
    if segundos < 172800:
        return f"{segundos / 3600:.1f}h"
    return f"{segundos / 86400:.1f}d"


def _marca(valor: bool) -> str:
    return "sim" if valor else "NAO"


def _coluna_clipes(linha: dict) -> str:
    """Uma letra por slot; minuscula quando o clipe ainda nao existe."""
    letras = {slots.CHARACTER: "P", slots.WEAPON: "A",
              slots.CHARACTER_WEAPON: "PA"}
    return " ".join(letras[s] if linha["clipes"][s] else letras[s].lower()
                    for s in slots.SLOTS)


def imprimir() -> int:
    """Relatorio completo. Devolve quantas inconsistencias encontrou."""
    jobs = queue.listar()
    print("\nFILA")
    print("----")
    if not jobs:
        print("  vazia")
    for job in jobs:
        erro = f"  {str(job.get('error'))[:52]}" if job.get("error") else ""
        espaco = " [retomavel]" if job.get("space_url") else ""
        print(f"  {job['generation_id']:<18} {job['slot']:<17} "
              f"{job['status']:<8} tent={job.get('attempts', 0)} "
              f"ha {_idade(job.get('updated_at')):>6}{espaco}{erro}")

    linhas = inventario()
    completas = [ln for ln in linhas if all(ln["clipes"].values())]
    print(f"\nGERACOES ({len(completas)} de {len(linhas)} com os tres clipes)")
    print("-" * 62)
    print(f"  {'geracao':<18} {'clipes':<9} {'no plano':<9} "
          f"{'celular':<8} {'normal':<7}")
    for linha in linhas:
        alerta = "  <-- final desatualizado" if linha["final_desatualizado"] else ""
        # Sem clipe nenhum nao ha o que esperar do plano: "-" em vez de "NAO",
        # senao toda geracao anterior a esta feature parece quebrada.
        if not any(linha["clipes"].values()) or linha["no_plano"] is None:
            plano = "-"
        else:
            usados = sum(1 for s in slots.SLOTS if linha["no_plano"].get(s))
            plano = f"{usados}/{sum(linha['clipes'].values())}"
        print(f"  {linha['generation_id']:<18} {_coluna_clipes(linha):<9} "
              f"{plano:<9} {_marca(linha['finais']['celular']):<8} "
              f"{_marca(linha['finais']['normal']):<7}{alerta}")
    print("  (clipes: P personagem, A arma, PA os dois; minuscula = faltando)")

    resumo = history.resumo()
    print("\nHISTORICO")
    print("---------")
    if not resumo["eventos"]:
        print("  sem eventos ainda (o worker grava a partir da proxima rodada)")
    else:
        mediana = resumo["espera_mediana_s"]
        taxa = resumo["taxa_sucesso"]
        print(f"  eventos: {resumo['eventos']} | tentativas fechadas: "
              f"{resumo['tentativas_fechadas']} | concluidas: {resumo['concluidos']}")
        if taxa is not None:
            print(f"  taxa de sucesso: {taxa * 100:.0f}%")
        if mediana is not None:
            print(f"  espera do Digen: mediana {mediana:.0f}s | "
                  f"maior {resumo['espera_max_s']:.0f}s "
                  f"({resumo['espera_amostras']} amostra(s))")
        print(f"  ultimo evento: ha {_idade(resumo['ultimo_evento_em'])}")

    problemas = inconsistencias(linhas)
    print("\nINCONSISTENCIAS")
    print("---------------")
    if not problemas:
        print("  nenhuma")
    for problema in problemas:
        print(f"  ! {problema}")
    return len(problemas)
