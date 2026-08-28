# -*- coding: utf-8 -*-
"""Inspetor de skills (Onda 11A) — a interface humana do "MCP interno".

Consulta os CONTRATOS derivados (core/skill_contract): listar, filtrar,
explicar, exportar JSON, medir cobertura e rodar a checagem 1-a-1.

O módulo é import-safe (sem pygame): só os subcomandos ``checar`` e ``demos``
importam o jogo, e o fazem tarde — são dev-tools que rodam cenário.

Uso:
    python -m neural_fights.tools.skill_inspector listar [--tipo AREA] ...
    python -m neural_fights.tools.skill_inspector explicar "Julgamento Celestial"
    python -m neural_fights.tools.skill_inspector exportar [--saida skills.json]
    python -m neural_fights.tools.skill_inspector cobertura
    python -m neural_fights.tools.skill_inspector checar --todas [--relatorio r.json]
    python -m neural_fights.tools.skill_inspector demos --todas
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List

from neural_fights.core.skill_contract import (
    SkillContract,
    catalogo_de_contratos,
)


def _safe_print(texto: str) -> None:
    try:
        print(texto)
    except UnicodeEncodeError:  # consoles cp1252
        print(texto.encode("ascii", "replace").decode("ascii"))


# ------------------------------------------------------------------ filtros

def _filtrar(contratos: Dict[str, SkillContract], args) -> List[SkillContract]:
    saida = []
    for contrato in contratos.values():
        if args.tipo and contrato.tipo != args.tipo.upper():
            continue
        if args.elemento and contrato.elemento.upper() != args.elemento.upper():
            continue
        if args.classe and not any(
            args.classe.lower() in fonte.lower() for fonte in contrato.fontes
        ):
            continue
        if args.papel and not any(
            fonte.endswith(f":{args.papel.upper()}") for fonte in contrato.fontes
        ):
            continue
        saida.append(contrato)
    return sorted(saida, key=lambda c: (c.tipo, c.nome))


# ---------------------------------------------------------------- comandos

def cmd_listar(args) -> int:
    contratos = _filtrar(catalogo_de_contratos(), args)
    _safe_print(
        f"{'SKILL':<26} {'TIPO':<9} {'ELEM':<10} {'CUSTO':>5} {'CD':>5} "
        f"{'ALCANCE':>7} CONSEQUÊNCIAS"
    )
    for c in contratos:
        _safe_print(
            f"{c.nome:<26} {c.tipo:<9} {(c.elemento or '-'):<10} "
            f"{c.custo_mana:>5.0f} {c.cooldown:>5.0f} {c.alcance_perigo:>7.1f} "
            f"{', '.join(sorted(c.consequencias))}"
        )
    _safe_print(f"\n{len(contratos)} skills")
    return 0


def cmd_explicar(args) -> int:
    contratos = catalogo_de_contratos()
    contrato = contratos.get(args.skill)
    if contrato is None:
        _safe_print(f"skill desconhecida: {args.skill!r}")
        candidatos = [n for n in contratos if args.skill.lower() in n.lower()]
        if candidatos:
            _safe_print("você quis dizer: " + ", ".join(candidatos[:6]))
        return 1
    c = contrato
    linhas = [
        "=" * 62,
        f"{c.nome}  [{c.tipo}{' / ' + c.elemento if c.elemento else ''}]",
        "=" * 62,
        f"  {c.descricao}",
        "",
        f"  Custo: {c.custo_mana:.0f} mana"
        + (f" + {c.custo_vida:.0f} vida" if c.custo_vida else "")
        + (
            f" + {c.custo_vida_percent:.0%} da vida"
            if c.custo_vida_percent
            else ""
        )
        + f" | Cooldown: {c.cooldown:.0f}s",
        "  Geometria: "
        + (
            "self-cast"
            if c.alcance_lancamento <= 0
            else f"lança até {c.alcance_lancamento:.1f}m"
        )
        + (f", raio de efeito {c.raio_efeito:.1f}m" if c.raio_efeito else "")
        + (" (cai no alvo previsto)" if c.ancorado_no_alvo else "")
        + (" (centrado no conjurador)" if c.centrado_no_caster else ""),
    ]
    if c.pilares:
        linhas.append(
            f"  Pilares: {c.pilares} de raio {c.raio_pilar:.2f}m "
            "(o primeiro cai na âncora do cast)"
        )
    if c.delay:
        linhas.append(
            f"  Telegraph: {c.delay:.1f}s de aviso"
            + (" visível" if c.aviso_visual else "")
        )
    if c.duracao:
        linhas.append(f"  Duração: {c.duracao:.1f}s")
    if c.efeito:
        chance = "" if c.chance_efeito >= 1.0 else f" ({c.chance_efeito:.0%})"
        linhas.append(
            f"  Efeito: {c.efeito} [{c.categoria_efeito or 'fora do status'}]"
            + chance
        )
    if c.efeito2:
        linhas.append(f"  Efeito 2: {c.efeito2} [{c.categoria_efeito2}]")
    if c.condicao:
        limiar = (
            f" (vida < {c.condicao_limiar:.0%})"
            if c.condicao == "ALVO_BAIXA_VIDA"
            else ""
        )
        linhas.append(f"  Condição: {c.condicao}{limiar}")
    if c.combo_apos:
        linhas.append("  Combo após: " + ", ".join(c.combo_apos))
    if c.condicao_status:
        linhas.append(f"  Preparada por: skills que aplicam {c.condicao_status}")
    linhas.append(
        "  Consequências: " + (", ".join(sorted(c.consequencias)) or "-")
    )
    linhas.append(f"  Dano estimado: {c.dano_estimado:.0f}")
    if c.fontes:
        linhas.append("  Alcançável via:")
        for fonte in c.fontes:
            linhas.append(f"    - {fonte}")
    else:
        linhas.append("  Alcançável via: (nenhum kit de classe)")
    for linha in linhas:
        _safe_print(linha)
    return 0


def cmd_exportar(args) -> int:
    dump = {
        nome: contrato.to_dict()
        for nome, contrato in sorted(catalogo_de_contratos().items())
    }
    texto = json.dumps(dump, ensure_ascii=True, sort_keys=True, indent=2)
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        _safe_print(f"{len(dump)} contratos exportados para {args.saida}")
    else:
        print(texto)
    return 0


def _skills_de_armas() -> Dict[str, List[str]]:
    """Skill -> armas que a carregam (leitura tardia do banco)."""
    from neural_fights.data import database

    por_skill: Dict[str, List[str]] = {}
    try:
        armas_raw, _ = database.carregar_database()
    except Exception:
        return por_skill
    for arma in armas_raw:
        nomes = []
        habilidade = arma.get("habilidade")
        if habilidade:
            nomes.append(habilidade)
        for item in arma.get("habilidades") or ():
            nomes.append(item.get("nome") if isinstance(item, dict) else item)
        for nome in nomes:
            if nome and nome != "Nenhuma":
                por_skill.setdefault(nome, []).append(arma.get("nome", "?"))
    return por_skill


def cmd_cobertura(args) -> int:
    contratos = catalogo_de_contratos()
    por_arma = _skills_de_armas()
    alcancaveis = []
    fora = []
    for nome, contrato in sorted(contratos.items()):
        vias = list(contrato.fontes)
        if nome in por_arma:
            vias.append(f"armas:{len(por_arma[nome])}")
        (alcancaveis if vias else fora).append((nome, contrato.tipo, vias))

    _safe_print(f"ALCANÇÁVEIS ({len(alcancaveis)}):")
    for nome, tipo, vias in alcancaveis:
        _safe_print(f"  {nome:<26} [{tipo:<8}] {', '.join(vias)}")
    _safe_print(f"\nFORA DE CIRCULAÇÃO ({len(fora)}):")
    por_tipo: Dict[str, int] = {}
    for nome, tipo, _ in fora:
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        _safe_print(f"  {nome:<26} [{tipo}]")
    if fora:
        resumo = ", ".join(f"{t}={n}" for t, n in sorted(por_tipo.items()))
        _safe_print(f"\nFora por tipo: {resumo}")
    return 0


def cmd_checar(args) -> int:
    from neural_fights.tools.skill_check import checar_skill, checar_todas

    if args.todas:
        resultados = checar_todas(seed=args.seed)
    elif args.skill:
        resultados = [checar_skill(args.skill, seed=args.seed)]
    else:
        _safe_print("informe uma skill ou --todas")
        return 2

    falhas = [r for r in resultados if not r["ok"]]
    for r in resultados:
        marca = "OK   " if r["ok"] else "FALHA"
        detalhe = ""
        if r["faltando"]:
            detalhe = " | faltando: " + ", ".join(r["faltando"])
        if r["erro"]:
            detalhe += f" | erro: {r['erro']}"
        _safe_print(f"{marca} [{r['tipo']:<8}] {r['skill']}{detalhe}")
    _safe_print(
        f"\n{len(resultados) - len(falhas)}/{len(resultados)} skills com a "
        "consequência declarada observada no motor"
    )
    if args.relatorio:
        with open(args.relatorio, "w", encoding="utf-8") as arquivo:
            json.dump(resultados, arquivo, ensure_ascii=True, indent=2)
        _safe_print(f"relatório gravado em {args.relatorio}")
    return 1 if falhas else 0


def cmd_demos(args) -> int:
    try:
        from neural_fights.recording.skill_demo import main as demo_main
    except ImportError:
        _safe_print(
            "gerador de demos indisponível (neural_fights.recording.skill_demo)"
        )
        return 2
    argv = ["--todas"] if args.todas else (["--skill", args.skill] if args.skill else [])
    return demo_main(argv)


# ------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m neural_fights.tools.skill_inspector",
        description="Inspetor dos contratos de skill (o MCP interno).",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    listar = sub.add_parser("listar", help="lista skills com filtros")
    listar.add_argument("--tipo")
    listar.add_argument("--elemento")
    listar.add_argument("--classe")
    listar.add_argument("--papel", help="CONTROLE|ZONA|MOBILIDADE|PICO")
    listar.set_defaults(func=cmd_listar)

    explicar = sub.add_parser("explicar", help="contrato completo de uma skill")
    explicar.add_argument("skill")
    explicar.set_defaults(func=cmd_explicar)

    exportar = sub.add_parser("exportar", help="dump JSON de todos os contratos")
    exportar.add_argument("--saida")
    exportar.set_defaults(func=cmd_exportar)

    cobertura = sub.add_parser("cobertura", help="quem alcança cada skill")
    cobertura.set_defaults(func=cmd_cobertura)

    checar = sub.add_parser(
        "checar", help="roda o cenário 1-a-1 no motor real (dev-tool)"
    )
    checar.add_argument("skill", nargs="?")
    checar.add_argument("--todas", action="store_true")
    checar.add_argument("--seed", type=int, default=101)
    checar.add_argument("--relatorio")
    checar.set_defaults(func=cmd_checar)

    demos = sub.add_parser("demos", help="gera clipes de demonstração (11D)")
    demos.add_argument("skill", nargs="?")
    demos.add_argument("--todas", action="store_true")
    demos.set_defaults(func=cmd_demos)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
