"""Gate de consistencia entre dados de armas e a implementacao de hitboxes.

Erros representam contrato estrutural ou geometria impossivel. Avisos indicam
valores ainda executaveis, mas fora de limites operacionais muito amplos; eles
so bloqueiam com ``--strict``. Informacoes documentam campos aceitos que nao
participam do alcance da hitbox.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

# Mantem a saida de CLI (especialmente JSON) livre do banner de importacao.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from data import database
from models.constants import LISTA_TIPOS_ARMA, TIPOS_ARMA


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEAPONS = Path(database.ARQUIVO_ARMAS).resolve()
DEFAULT_HITBOX_SOURCE = PROJECT_ROOT / "core" / "hitbox.py"

INTEGER_GEOMETRY_FIELDS = {"quantidade", "quantidade_orbitais"}
OPERATIONAL_MAXIMUMS = {
    "quantidade": 64,
    "quantidade_orbitais": 64,
    "largura": 500.0,
    "largura_ponta": 500.0,
}
DEFAULT_OPERATIONAL_MAXIMUM = 1_000.0

HITBOX_PREDICATES = (
    "_eh_arma_corrente",
    "_eh_arma_lamina",
    "_eh_arma_ranged",
    "_eh_arma_area",
)
HITBOX_CALCULATORS = (
    "_calcular_hitbox_corrente",
    "_calcular_hitbox_lamina",
    "_calcular_hitbox_ranged",
    "_calcular_hitbox_area",
    "_calcular_hitbox_orbital",
)


@dataclass(frozen=True)
class DiagnosticoArma:
    nome: str
    tipo: str
    problema: str
    sugestao: str
    valores_relevantes: dict[str, Any]
    nivel: str = "error"
    codigo: str = "invalid-geometry"


@dataclass(frozen=True)
class HitboxGateReport:
    arquivo: str
    hitbox_source: str | None
    total: int
    por_tipo: dict[str, int]
    diagnosticos: tuple[DiagnosticoArma, ...]

    @property
    def errors(self) -> int:
        return sum(item.nivel == "error" for item in self.diagnosticos)

    @property
    def warnings(self) -> int:
        return sum(item.nivel == "warning" for item in self.diagnosticos)

    @property
    def infos(self) -> int:
        return sum(item.nivel == "info" for item in self.diagnosticos)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arquivo": self.arquivo,
            "hitbox_source": self.hitbox_source,
            "total": self.total,
            "por_tipo": self.por_tipo,
            "errors": self.errors,
            "warnings": self.warnings,
            "accepted_infos": self.infos,
            "diagnosticos": [asdict(item) for item in self.diagnosticos],
        }


def _diagnostico(
    *,
    nome: str,
    tipo: str,
    nivel: str,
    codigo: str,
    problema: str,
    sugestao: str,
    valores: Mapping[str, Any] | None = None,
) -> DiagnosticoArma:
    return DiagnosticoArma(
        nome=nome,
        tipo=tipo,
        problema=problema,
        sugestao=sugestao,
        valores_relevantes=dict(valores or {}),
        nivel=nivel,
        codigo=codigo,
    )


def carregar_armas(caminho: str | Path = DEFAULT_WEAPONS) -> list[dict[str, Any]]:
    path = Path(caminho)
    with path.open("r", encoding="utf-8") as stream:
        dados = json.load(stream)
    if not isinstance(dados, list):
        raise ValueError(f"Banco de armas precisa ser uma lista: {path}")
    if any(not isinstance(item, dict) for item in dados):
        raise ValueError(f"Todos os itens do banco precisam ser objetos JSON: {path}")
    return dados


def diagnosticar_arma(arma: dict[str, Any]) -> list[DiagnosticoArma]:
    """Analisa a geometria persistida de uma unica arma."""

    nome_bruto = arma.get("nome")
    nome = nome_bruto.strip() if isinstance(nome_bruto, str) and nome_bruto.strip() else "Sem nome"
    tipo = arma.get("tipo")
    if tipo not in TIPOS_ARMA:
        return [
            _diagnostico(
                nome=nome,
                tipo=str(tipo or "Desconhecido"),
                nivel="error",
                codigo="unknown-weapon-type",
                problema=f"Tipo de arma desconhecido: {tipo!r}",
                sugestao="Usar um tipo presente em LISTA_TIPOS_ARMA",
                valores={"tipos_aceitos": LISTA_TIPOS_ARMA},
            )
        ]

    diagnosticos: list[DiagnosticoArma] = []
    for campo in TIPOS_ARMA[tipo]["geometria"]:
        valor = arma.get(campo)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            diagnosticos.append(
                _diagnostico(
                    nome=nome,
                    tipo=tipo,
                    nivel="error",
                    codigo="invalid-geometry-number",
                    problema=f"{campo} deve ser numerico",
                    sugestao=f"Definir {campo} com valor finito e maior que zero",
                    valores={campo: valor},
                )
            )
            continue
        if not math.isfinite(float(valor)):
            diagnosticos.append(
                _diagnostico(
                    nome=nome,
                    tipo=tipo,
                    nivel="error",
                    codigo="non-finite-geometry",
                    problema=f"{campo} nao e finito",
                    sugestao=f"Definir {campo} com valor finito e maior que zero",
                    valores={campo: valor},
                )
            )
            continue
        if valor <= 0:
            diagnosticos.append(
                _diagnostico(
                    nome=nome,
                    tipo=tipo,
                    nivel="error",
                    codigo="non-positive-geometry",
                    problema=f"{campo} produz geometria nula ou invertida",
                    sugestao=f"Definir {campo} com valor maior que zero",
                    valores={campo: valor},
                )
            )
            continue
        if campo in INTEGER_GEOMETRY_FIELDS and not isinstance(valor, int):
            diagnosticos.append(
                _diagnostico(
                    nome=nome,
                    tipo=tipo,
                    nivel="error",
                    codigo="non-integer-count",
                    problema=f"{campo} deve ser uma contagem inteira",
                    sugestao=f"Definir {campo} como inteiro maior ou igual a 1",
                    valores={campo: valor},
                )
            )
            continue

        limite = OPERATIONAL_MAXIMUMS.get(campo, DEFAULT_OPERATIONAL_MAXIMUM)
        if valor > limite:
            diagnosticos.append(
                _diagnostico(
                    nome=nome,
                    tipo=tipo,
                    nivel="warning",
                    codigo="geometry-operational-outlier",
                    problema=f"{campo} esta fora do limite operacional amplo",
                    sugestao="Revisar balanceamento; o valor ainda e geometricamente executavel",
                    valores={campo: valor, "limite_operacional": limite},
                )
            )

    if tipo == "Corrente" and (arma.get("comp_cabo", 0) > 0 or arma.get("comp_lamina", 0) > 0):
        diagnosticos.append(
            _diagnostico(
                nome=nome,
                tipo=tipo,
                nivel="info",
                codigo="accepted-chain-visual-fallback",
                problema=(
                    "comp_cabo/comp_lamina sao aceitos como visual/fallback e nao "
                    "participam do alcance da hitbox de corrente"
                ),
                sugestao="Nenhuma alteracao necessaria",
                valores={
                    "comp_corrente": arma.get("comp_corrente"),
                    "comp_cabo": arma.get("comp_cabo"),
                    "comp_lamina": arma.get("comp_lamina"),
                },
            )
        )

    return diagnosticos


def _find_assignment(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"atribuicao literal ausente: {name}")


def diagnosticar_implementacao_hitbox(caminho: str | Path = DEFAULT_HITBOX_SOURCE) -> list[DiagnosticoArma]:
    """Confere perfis e roteamento por AST, sem executar o runtime de combate."""

    path = Path(caminho)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        profiles = _find_assignment(tree, "HITBOX_PROFILES")
    except (OSError, SyntaxError, TypeError, ValueError) as exc:
        return [
            _diagnostico(
                nome="Implementacao",
                tipo="Fonte",
                nivel="error",
                codigo="invalid-hitbox-source",
                problema=f"Nao foi possivel validar {path}: {exc}",
                sugestao="Restaurar uma fonte Python valida com HITBOX_PROFILES literal",
            )
        ]

    diagnosticos: list[DiagnosticoArma] = []
    if not isinstance(profiles, dict):
        return [
            _diagnostico(
                nome="Implementacao",
                tipo="Fonte",
                nivel="error",
                codigo="invalid-hitbox-profiles",
                problema="HITBOX_PROFILES precisa ser um dicionario literal",
                sugestao="Declarar um perfil literal para cada tipo canonico",
            )
        ]

    for tipo in LISTA_TIPOS_ARMA:
        profile = profiles.get(tipo)
        if not isinstance(profile, dict):
            diagnosticos.append(
                _diagnostico(
                    nome="Implementacao",
                    tipo=tipo,
                    nivel="error",
                    codigo="missing-hitbox-profile",
                    problema="Tipo canonico sem perfil de hitbox",
                    sugestao=f"Adicionar HITBOX_PROFILES[{tipo!r}]",
                )
            )
            continue

        for campo in ("shape", "idle_shape"):
            if not isinstance(profile.get(campo), str) or not profile[campo]:
                diagnosticos.append(
                    _diagnostico(
                        nome="Implementacao",
                        tipo=tipo,
                        nivel="error",
                        codigo="invalid-hitbox-profile",
                        problema=f"Perfil possui {campo} invalido",
                        sugestao=f"Definir {campo} como texto nao vazio",
                        valores={campo: profile.get(campo)},
                    )
                )

        for campo in ("range_mult", "attack_arc_mult"):
            valor = profile.get(campo)
            if (
                isinstance(valor, bool)
                or not isinstance(valor, (int, float))
                or not math.isfinite(float(valor))
                or valor <= 0
            ):
                diagnosticos.append(
                    _diagnostico(
                        nome="Implementacao",
                        tipo=tipo,
                        nivel="error",
                        codigo="invalid-hitbox-profile",
                        problema=f"Perfil possui {campo} nao positivo ou nao finito",
                        sugestao=f"Definir {campo} com numero finito maior que zero",
                        valores={campo: valor},
                    )
                )

        minimo = profile.get("min_range_ratio")
        if (
            isinstance(minimo, bool)
            or not isinstance(minimo, (int, float))
            or not math.isfinite(float(minimo))
            or not 0 <= minimo < 1
        ):
            diagnosticos.append(
                _diagnostico(
                    nome="Implementacao",
                    tipo=tipo,
                    nivel="error",
                    codigo="invalid-hitbox-profile",
                    problema="min_range_ratio deve estar no intervalo [0, 1)",
                    sugestao="Corrigir a zona morta do perfil",
                    valores={"min_range_ratio": minimo},
                )
            )

        inicio = profile.get("hit_window_start")
        fim = profile.get("hit_window_end")
        if not (
            isinstance(inicio, (int, float))
            and not isinstance(inicio, bool)
            and isinstance(fim, (int, float))
            and not isinstance(fim, bool)
            and 0 <= inicio <= fim <= 1
        ):
            diagnosticos.append(
                _diagnostico(
                    nome="Implementacao",
                    tipo=tipo,
                    nivel="error",
                    codigo="invalid-hit-window",
                    problema="Janela de hit deve satisfazer 0 <= inicio <= fim <= 1",
                    sugestao="Corrigir hit_window_start/hit_window_end",
                    valores={"inicio": inicio, "fim": fim},
                )
            )

    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SistemaHitbox"
    ]
    if len(classes) != 1:
        diagnosticos.append(
            _diagnostico(
                nome="Implementacao",
                tipo="Fonte",
                nivel="error",
                codigo="invalid-hitbox-class",
                problema="SistemaHitbox precisa existir exatamente uma vez",
                sugestao="Restaurar a classe canonica SistemaHitbox",
                valores={"ocorrencias": len(classes)},
            )
        )
        return diagnosticos

    methods = {
        node.name: node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for method_name in (*HITBOX_PREDICATES, *HITBOX_CALCULATORS, "calcular_hitbox_arma"):
        if method_name not in methods:
            diagnosticos.append(
                _diagnostico(
                    nome="Implementacao",
                    tipo="Fonte",
                    nivel="error",
                    codigo="missing-hitbox-method",
                    problema=f"Metodo ausente: SistemaHitbox.{method_name}",
                    sugestao="Restaurar o metodo referenciado pelo roteamento",
                )
            )

    predicate_types: dict[str, set[str]] = {}
    canonical_types = set(LISTA_TIPOS_ARMA)
    for method_name in HITBOX_PREDICATES:
        method = methods.get(method_name)
        predicate_types[method_name] = (
            {
                node.value
                for node in ast.walk(method)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in canonical_types
            }
            if method is not None
            else set()
        )

    dispatcher = methods.get("calcular_hitbox_arma")
    routed_by: dict[str, list[str]] = {tipo: [] for tipo in LISTA_TIPOS_ARMA}
    if dispatcher is not None and any(
        isinstance(node, ast.Constant) and node.value == "Orbital"
        for node in ast.walk(dispatcher)
    ):
        routed_by["Orbital"].append("direct-orbital-branch")
    for method_name, handled_types in predicate_types.items():
        for tipo in handled_types:
            routed_by[tipo].append(method_name)
    for tipo, handlers in routed_by.items():
        if len(handlers) != 1:
            diagnosticos.append(
                _diagnostico(
                    nome="Implementacao",
                    tipo=tipo,
                    nivel="error",
                    codigo="ambiguous-hitbox-routing" if handlers else "missing-hitbox-routing",
                    problema=(
                        "Tipo possui roteamento ambiguo de hitbox"
                        if handlers
                        else "Tipo nao possui roteamento explicito de hitbox"
                    ),
                    sugestao="Manter exatamente um predicado por tipo canonico",
                    valores={"handlers": handlers},
                )
            )

    if dispatcher is not None:
        called_methods = {
            node.func.attr
            for node in ast.walk(dispatcher)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        for method_name in HITBOX_CALCULATORS:
            if method_name not in called_methods:
                diagnosticos.append(
                    _diagnostico(
                        nome="Implementacao",
                        tipo="Fonte",
                        nivel="error",
                        codigo="unreferenced-hitbox-calculator",
                        problema=f"Calculador nao referenciado: {method_name}",
                        sugestao="Conectar o calculador ao dispatcher ou remover codigo morto",
                    )
                )

    return diagnosticos


def criar_relatorio(
    armas: list[dict[str, Any]],
    *,
    arquivo: str,
    hitbox_source: str | Path | None = DEFAULT_HITBOX_SOURCE,
) -> HitboxGateReport:
    diagnosticos: list[DiagnosticoArma] = []
    database_ok = True
    try:
        database.validar_armas(armas)
    except database.DataValidationError as exc:
        database_ok = False
        diagnosticos.extend(
            _diagnostico(
                nome="Banco",
                tipo="Contrato",
                nivel="error",
                codigo="database-contract",
                problema=erro,
                sugestao="Corrigir o registro sem remover armas ou referencias",
            )
            for erro in exc.erros
        )

    for arma in armas:
        for item in diagnosticar_arma(arma):
            if database_ok or item.nivel != "error":
                diagnosticos.append(item)

    if hitbox_source is not None:
        diagnosticos.extend(diagnosticar_implementacao_hitbox(hitbox_source))

    por_tipo = Counter(str(arma.get("tipo", "Desconhecido")) for arma in armas)
    return HitboxGateReport(
        arquivo=arquivo,
        hitbox_source=str(Path(hitbox_source).resolve()) if hitbox_source is not None else None,
        total=len(armas),
        por_tipo=dict(sorted(por_tipo.items())),
        diagnosticos=tuple(diagnosticos),
    )


def render_text(report: HitboxGateReport, *, title: str = "HITBOX / WEAPON GEOMETRY GATE") -> str:
    lines = [
        title,
        f"Weapons file: {report.arquivo}",
        f"Hitbox source: {report.hitbox_source or 'not checked'}",
        f"Weapons: {report.total}",
        f"Errors: {report.errors}",
        f"Warnings: {report.warnings}",
        f"Accepted informational findings: {report.infos}",
        "Types: " + ", ".join(f"{name}={count}" for name, count in report.por_tipo.items()),
    ]
    if report.diagnosticos:
        lines.append("Findings:")
        for item in report.diagnosticos:
            lines.append(
                f"- {item.nivel.upper()} {item.codigo} [{item.nome} / {item.tipo}]: "
                f"{item.problema} | {item.sugestao}"
            )
    else:
        lines.append("Findings: none")
    if report.errors:
        lines.append("Result: FAILED")
    elif report.warnings:
        lines.append("Result: ACCEPTED IN NORMAL MODE (strict mode rejects warnings)")
    else:
        lines.append("Result: PASSED (informational findings explicitly accepted)")
    return "\n".join(lines) + "\n"


def _write_output(text: str, stream: TextIO) -> None:
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        safe = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        stream.write(safe)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", type=Path, default=DEFAULT_WEAPONS)
    parser.add_argument("--hitbox-source", type=Path, default=DEFAULT_HITBOX_SOURCE)
    parser.add_argument("--json", action="store_true", help="emite JSON ASCII")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="retorna codigo 2 quando houver avisos de limite operacional",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)
    weapons_path = args.arquivo.resolve()
    hitbox_source = args.hitbox_source.resolve()
    try:
        armas = carregar_armas(weapons_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write_output(f"input error: {exc}\n", stderr)
        return 1

    report = criar_relatorio(
        armas,
        arquivo=str(weapons_path),
        hitbox_source=hitbox_source,
    )
    if args.json:
        _write_output(json.dumps(report.to_dict(), ensure_ascii=True, sort_keys=True) + "\n", stdout)
    else:
        _write_output(render_text(report), stdout)

    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
