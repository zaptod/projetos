"""Auditoria estrutural, import-safe, do catalogo de skills.

A ferramenta valida somente contratos que podem ser demonstrados pelos arquivos
fonte. Ela nao instancia objetos de combate e nao classifica uma skill como
"funcional" sem um teste de runtime correspondente.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TextIO


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT.parent
DEFAULT_CATALOG = PACKAGE_ROOT / "core" / "skills.py"
DEFAULT_STATUS_CONTRACT = PACKAGE_ROOT / "core" / "status_runtime.py"
DEFAULT_EVIDENCE_MANIFEST = PACKAGE_ROOT / "tools" / "skill_runtime_evidence.py"

SUPPORTED_TYPES = {
    "NADA",
    "PROJETIL",
    "AREA",
    "DASH",
    "BUFF",
    "BEAM",
    "SUMMON",
    "TRAP",
    "TRANSFORM",
    "CHANNEL",
}

COMMON_REQUIRED = {"tipo", "custo", "cooldown"}
TYPE_REQUIRED = {
    "NADA": set(),
    "PROJETIL": {"descricao", "cor", "dano", "velocidade", "raio", "vida"},
    "AREA": {"descricao", "cor", "dano", "raio_area"},
    "DASH": {"descricao", "cor", "distancia"},
    "BUFF": {"descricao", "cor"},
    "BEAM": {"descricao", "cor", "dano", "alcance"},
    "SUMMON": {"descricao", "cor", "duracao"},
    "TRAP": {"descricao", "cor", "dano", "duracao", "vida_estrutura"},
    "TRANSFORM": {"descricao", "cor", "duracao"},
    "CHANNEL": {"descricao", "cor", "duracao_max"},
}

NUMERIC_NON_NEGATIVE = {
    "bonus_area",
    "bonus_dano_magico",
    "bonus_vs_trevas",
    "cura_por_morte",
    "custo",
    "cooldown",
    "dano",
    "velocidade",
    "raio",
    "vida",
    "raio_area",
    "distancia",
    "alcance",
    "duracao",
    "duracao_max",
    "vida_estrutura",
    "delay_saida",
    "duracao_stop",
    "dano_contato",
    "forca_empurrao",
    "raio_pilar",
    "stacks_por_segundo",
}

POSITIVE_NUMBER_FIELDS = {
    "bonus_area",
    "bonus_dano_magico",
    "bonus_vs_trevas",
    "cura_por_morte",
    "dano_contato",
    "delay_saida",
    "duracao_stop",
    "forca_empurrao",
    "raio_pilar",
    "vida_estrutura",
}

MULTIPLIER_FIELDS = {
    "bonus_area",
    "bonus_dano_magico",
    "bonus_vs_trevas",
}

ADVANCED_FIELD_ALLOWED_TYPES = {
    "afeta_caster": {"AREA"},
    "ativa_ao_morrer": {"BUFF"},
    "bloqueia_projeteis": {"TRAP"},
    "bonus_area": {"BUFF"},
    "bonus_dano_magico": {"BUFF"},
    "bonus_vs_trevas": {"AREA", "BEAM", "CHANNEL", "PROJETIL"},
    "cura_percent": {"BUFF"},
    "cura_por_morte": {"AREA"},
    "dano_contato": {"BUFF", "TRANSFORM"},
    "delay_saida": {"DASH"},
    "duracao_stop": {"AREA"},
    "esquiva_garantida": {"BUFF"},
    "forca_empurrao": {"AREA"},
    "invisivel_durante": {"DASH"},
    "pilares": {"AREA"},
    "raio_pilar": {"AREA"},
    "revive_hp_percent": {"BUFF"},
    "stacks_por_segundo": {"AREA"},
    "ve_ataques": {"BUFF"},
    "vida_estrutura": {"TRAP"},
}

PERSISTENT_BUFF_FIELDS = {
    "bonus_area",
    "bonus_dano_magico",
    "dano_contato",
    "esquiva_garantida",
    "ve_ataques",
}

BOOLEAN_CONTRACT_FIELDS = {
    "afeta_caster",
    "ativa_ao_morrer",
    "bloqueia_projeteis",
    "invisivel_durante",
    "ve_ataques",
}

FRACTION_FIELDS = {
    "cura_percent",
    "revive_hp_percent",
}

# Estes campos sao validos estruturalmente, mas sua presenca nao prova que a
# mecanica tenha paridade entre simulador visual, headless e torneio.
RUNTIME_EVIDENCE_FIELDS = {
    "afeta_caster",
    "ativa_ao_morrer",
    "bloqueia_projeteis",
    "bonus_area",
    "bonus_dano_magico",
    "bonus_vs_trevas",
    "chain",
    "cone",
    "contagioso",
    "copia_caster",
    "cria_portal",
    "cura_percent",
    "cura_por_morte",
    "dano_contato",
    "dano_chegada",
    "delay_saida",
    "duplica_apos",
    "duracao_stop",
    "esquiva_garantida",
    "forca_empurrao",
    "invisivel_durante",
    "pilares",
    "raio_pilar",
    "reflete_projeteis",
    "reflete_skills",
    "remove_congelamento",
    "revive_hp_percent",
    "reverte_estado",
    "rouba_buff",
    "sem_cooldown",
    "stats_aleatorios",
    "stacks_por_segundo",
    "vida_estrutura",
    "ve_ataques",
    "voo",
}


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    skill: str | None = None


@dataclass(frozen=True)
class AuditReport:
    catalog: str
    evidence_manifest: str
    total: int
    by_type: dict[str, int]
    evidence_sources_verified: bool
    verified_runtime_evidence: dict[str, tuple[str, ...]]
    findings: tuple[Finding, ...]

    @property
    def errors(self) -> int:
        return sum(item.level == "error" for item in self.findings)

    @property
    def warnings(self) -> int:
        return sum(item.level == "warning" for item in self.findings)

    @property
    def structurally_valid(self) -> int:
        invalid = {item.skill for item in self.findings if item.level == "error" and item.skill}
        return max(0, self.total - len(invalid))

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog": self.catalog,
            "evidence_manifest": self.evidence_manifest,
            "total": self.total,
            "by_type": self.by_type,
            "evidence_sources_verified": self.evidence_sources_verified,
            "verified_runtime_evidence": {
                field_name: list(references)
                for field_name, references in self.verified_runtime_evidence.items()
            },
            "structurally_valid": self.structurally_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": [asdict(item) for item in self.findings],
        }


class AuditInputError(RuntimeError):
    """Erro operacional ao carregar uma fonte da auditoria."""


def _literal_assignments(path: Path, names: Iterable[str]) -> dict[str, Any]:
    """Le atribuicoes literais sem importar o pacote do jogo."""
    requested = set(names)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditInputError(f"nao foi possivel ler {path}: {exc}") from exc

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise AuditInputError(f"fonte Python invalida em {path}:{exc.lineno}: {exc.msg}") from exc

    found: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id in requested:
                try:
                    found[target.id] = ast.literal_eval(value)
                except (TypeError, ValueError) as exc:
                    raise AuditInputError(
                        f"{target.id} em {path} precisa ser uma estrutura literal"
                    ) from exc

    missing = requested - found.keys()
    if missing:
        raise AuditInputError(f"atribuicoes ausentes em {path}: {', '.join(sorted(missing))}")
    return found


def load_sources(
    catalog_path: Path,
    status_path: Path,
    evidence_path: Path,
) -> tuple[Mapping[str, Any], dict[str, Any], Mapping[str, Any]]:
    catalog = _literal_assignments(catalog_path, {"SKILL_DB"})["SKILL_DB"]
    contracts = _literal_assignments(
        status_path,
        {
            "STATUS_ALIASES",
            "STATUS_RUNTIME",
            "BUFF_EFFECT_RUNTIME",
            "EFEITOS_TRATADOS_FORA_DO_STATUS",
        },
    )
    evidence = _literal_assignments(
        evidence_path,
        {"SKILL_RUNTIME_EVIDENCE"},
    )["SKILL_RUNTIME_EVIDENCE"]
    if not isinstance(catalog, dict):
        raise AuditInputError("SKILL_DB precisa ser um dicionario")
    if not isinstance(evidence, dict):
        raise AuditInputError("SKILL_RUNTIME_EVIDENCE precisa ser um dicionario")
    return catalog, contracts, evidence


def _finding(level: str, code: str, message: str, skill: str | None = None) -> Finding:
    return Finding(level=level, code=code, message=message, skill=skill)


def _evidence_reference_label(module: str, class_name: str, method_name: str) -> str:
    return f"{module}:{class_name}.{method_name}"


def _module_source_path(module: str, project_root: Path) -> Path | None:
    parts = module.split(".")
    if not parts or parts[0] != "tests" or any(not part.isidentifier() for part in parts):
        return None
    return project_root.joinpath(*parts).with_suffix(".py")


def _validate_test_reference(
    module: str,
    class_name: str,
    method_name: str,
    *,
    project_root: Path,
    parsed_modules: dict[str, tuple[Path, ast.Module] | str],
) -> str | None:
    """Valida uma referencia de teste somente pela arvore sintatica."""
    module_path = _module_source_path(module, project_root)
    if module_path is None:
        return "modulo deve apontar para tests e conter apenas identificadores Python"

    cached = parsed_modules.get(module)
    if cached is None:
        try:
            source = module_path.read_text(encoding="utf-8")
        except OSError as exc:
            cached = f"nao foi possivel ler modulo {module_path}: {exc}"
        else:
            try:
                cached = (module_path, ast.parse(source, filename=str(module_path)))
            except SyntaxError as exc:
                cached = (
                    f"modulo de teste Python invalido em "
                    f"{module_path}:{exc.lineno}: {exc.msg}"
                )
        parsed_modules[module] = cached

    if isinstance(cached, str):
        return cached

    module_path, tree = cached
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if not classes:
        return f"classe {class_name!r} nao existe em {module_path}"
    if len(classes) > 1:
        return f"classe {class_name!r} e ambigua em {module_path}"
    if not method_name.startswith("test_"):
        return f"metodo {method_name!r} nao possui prefixo test_"

    methods = [
        node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    ]
    if not methods:
        return f"metodo {class_name}.{method_name} nao existe em {module_path}"
    if len(methods) > 1:
        return f"metodo {class_name}.{method_name} e ambiguo em {module_path}"
    return None


def validate_runtime_evidence(
    evidence: Mapping[str, Any],
    *,
    project_root: Path = SOURCE_ROOT,
) -> tuple[dict[str, tuple[str, ...]], tuple[Finding, ...]]:
    """Retorna apenas evidencias cujo modulo, classe e metodo existem."""
    findings: list[Finding] = []
    verified: dict[str, tuple[str, ...]] = {}
    parsed_modules: dict[str, tuple[Path, ast.Module] | str] = {}

    provided_fields = set(evidence)
    for field_name in sorted(RUNTIME_EVIDENCE_FIELDS - provided_fields):
        findings.append(
            _finding(
                "error",
                "evidence-field-missing",
                f"manifesto nao mapeia o campo avancado: {field_name}",
            )
        )
    for field_name in sorted(provided_fields - RUNTIME_EVIDENCE_FIELDS, key=str):
        findings.append(
            _finding(
                "error",
                "unknown-evidence-field",
                f"manifesto mapeia campo avancado desconhecido: {field_name!r}",
            )
        )

    for field_name in sorted(RUNTIME_EVIDENCE_FIELDS & provided_fields):
        raw_references = evidence[field_name]
        if not isinstance(raw_references, (tuple, list)):
            findings.append(
                _finding(
                    "error",
                    "invalid-evidence-list",
                    f"evidencias de {field_name} devem ser uma lista ou tupla",
                )
            )
            continue

        valid_references: list[str] = []
        seen_references: set[tuple[str, str, str]] = set()
        for index, raw_reference in enumerate(raw_references):
            if (
                not isinstance(raw_reference, (tuple, list))
                or len(raw_reference) != 3
                or any(not isinstance(part, str) or not part for part in raw_reference)
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-evidence-reference",
                        (
                            f"evidencia {index} de {field_name} deve conter "
                            "(modulo, classe, metodo)"
                        ),
                    )
                )
                continue

            module, class_name, method_name = raw_reference
            reference = (module, class_name, method_name)
            label = _evidence_reference_label(*reference)
            if reference in seen_references:
                findings.append(
                    _finding(
                        "error",
                        "duplicate-evidence-reference",
                        f"evidencia duplicada para {field_name}: {label}",
                    )
                )
                continue
            seen_references.add(reference)

            problem = _validate_test_reference(
                *reference,
                project_root=project_root,
                parsed_modules=parsed_modules,
            )
            if problem:
                findings.append(
                    _finding(
                        "error",
                        "invalid-evidence-target",
                        f"evidencia invalida para {field_name} ({label}): {problem}",
                    )
                )
                continue
            valid_references.append(label)

        if valid_references:
            verified[field_name] = tuple(valid_references)

    return dict(sorted(verified.items())), tuple(findings)


def audit_catalog(
    catalog: Mapping[str, Any],
    contracts: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    catalog_label: str = "SKILL_DB",
    evidence_label: str = "SKILL_RUNTIME_EVIDENCE",
    project_root: Path = SOURCE_ROOT,
    verify_evidence_sources: bool = False,
) -> AuditReport:
    if verify_evidence_sources:
        verified_evidence, evidence_findings = validate_runtime_evidence(
            evidence,
            project_root=project_root,
        )
    else:
        verified_evidence, evidence_findings = {}, ()
    findings: list[Finding] = list(evidence_findings)
    by_type: Counter[str] = Counter()

    status_runtime = contracts.get("STATUS_RUNTIME", {})
    status_aliases = contracts.get("STATUS_ALIASES", {})
    buff_runtime = contracts.get("BUFF_EFFECT_RUNTIME", {})
    external_effects = set(contracts.get("EFEITOS_TRATADOS_FORA_DO_STATUS", set()))
    known_effects = set(status_runtime) | set(status_aliases) | external_effects

    sentinel = catalog.get("Nenhuma")
    if not isinstance(sentinel, dict) or sentinel.get("tipo") != "NADA":
        findings.append(
            _finding("error", "invalid-sentinel", "'Nenhuma' deve existir com tipo NADA", "Nenhuma")
        )

    for name, raw in catalog.items():
        skill_name = name if isinstance(name, str) else repr(name)
        if not isinstance(name, str) or not name.strip():
            findings.append(_finding("error", "invalid-name", "nome deve ser texto nao vazio", skill_name))
        if not isinstance(raw, dict):
            findings.append(_finding("error", "invalid-record", "registro deve ser um dicionario", skill_name))
            continue

        skill_type = raw.get("tipo")
        by_type[str(skill_type or "AUSENTE")] += 1
        if skill_type not in SUPPORTED_TYPES:
            findings.append(
                _finding("error", "unsupported-type", f"tipo ausente ou desconhecido: {skill_type!r}", skill_name)
            )
            continue

        required = COMMON_REQUIRED | TYPE_REQUIRED[skill_type]
        for field_name in sorted(required - raw.keys()):
            findings.append(
                _finding("error", "missing-field", f"campo obrigatorio ausente: {field_name}", skill_name)
            )

        for field_name in sorted(NUMERIC_NON_NEGATIVE & raw.keys()):
            value = raw[field_name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                findings.append(
                    _finding("error", "invalid-number", f"{field_name} deve ser numerico", skill_name)
                )
            elif value < 0:
                findings.append(
                    _finding("error", "negative-number", f"{field_name} nao pode ser negativo", skill_name)
                )

        for field_name in sorted(
            (POSITIVE_NUMBER_FIELDS - MULTIPLIER_FIELDS) & raw.keys()
        ):
            value = raw[field_name]
            if (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and value <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "non-positive-number",
                        f"{field_name} deve ser maior que zero",
                        skill_name,
                    )
                )

        for field_name in sorted(MULTIPLIER_FIELDS & raw.keys()):
            value = raw[field_name]
            if (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and value <= 1
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-multiplier",
                        f"{field_name} deve ser multiplicador maior que 1",
                        skill_name,
                    )
                )

        for field_name in sorted(ADVANCED_FIELD_ALLOWED_TYPES & raw.keys()):
            allowed_types = ADVANCED_FIELD_ALLOWED_TYPES[field_name]
            if skill_type not in allowed_types:
                findings.append(
                    _finding(
                        "error",
                        "invalid-advanced-field-type",
                        (
                            f"{field_name} nao e valido para {skill_type}; "
                            f"tipos aceitos: {', '.join(sorted(allowed_types))}"
                        ),
                        skill_name,
                    )
                )

        for field_name in sorted(BOOLEAN_CONTRACT_FIELDS & raw.keys()):
            if not isinstance(raw[field_name], bool):
                findings.append(
                    _finding(
                        "error",
                        "invalid-boolean",
                        f"{field_name} deve ser booleano",
                        skill_name,
                    )
                )

        for field_name in sorted(FRACTION_FIELDS & raw.keys()):
            value = raw[field_name]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0.0 < value <= 1.0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-fraction",
                        f"{field_name} deve estar no intervalo (0, 1]",
                        skill_name,
                    )
                )

        if raw.get("ativa_ao_morrer") is True:
            if "cura_percent" not in raw:
                findings.append(
                    _finding(
                        "error",
                        "incomplete-death-trigger",
                        "ativa_ao_morrer exige cura_percent",
                        skill_name,
                    )
                )
            cooldown = raw.get("cooldown")
            if not isinstance(cooldown, (int, float)) or isinstance(cooldown, bool) or cooldown <= 0:
                findings.append(
                    _finding(
                        "error",
                        "unsafe-death-trigger-cooldown",
                        "gatilho automatico de morte exige cooldown positivo",
                        skill_name,
                    )
                )
        elif "cura_percent" in raw:
            findings.append(
                _finding(
                    "error",
                    "orphan-death-heal",
                    "cura_percent exige ativa_ao_morrer=True",
                    skill_name,
                )
            )

        if "revive_hp_percent" in raw:
            cooldown = raw.get("cooldown")
            if (
                isinstance(cooldown, bool)
                or not isinstance(cooldown, (int, float))
                or cooldown <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "unsafe-revive-cooldown",
                        "revive_hp_percent exige cooldown positivo",
                        skill_name,
                    )
                )

        if "cura_por_morte" in raw:
            damage = raw.get("dano")
            if (
                isinstance(damage, bool)
                or not isinstance(damage, (int, float))
                or damage <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "kill-heal-without-damage",
                        "cura_por_morte exige uma fonte com dano positivo",
                        skill_name,
                    )
                )

        if skill_type == "BUFF" and PERSISTENT_BUFF_FIELDS & raw.keys():
            duration = raw.get("duracao")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or duration <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "missing-persistent-buff-duration",
                        (
                            "campos de buff persistente exigem duracao positiva: "
                            + ", ".join(sorted(PERSISTENT_BUFF_FIELDS & raw.keys()))
                        ),
                        skill_name,
                    )
                )

        if "bonus_vs_trevas" in raw:
            damage = raw.get("dano")
            if (
                isinstance(damage, bool)
                or not isinstance(damage, (int, float))
                or damage <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "dark-bonus-without-damage",
                        "bonus_vs_trevas exige dano positivo",
                        skill_name,
                    )
                )

        if "pilares" in raw:
            pilares = raw["pilares"]
            if isinstance(pilares, bool) or not isinstance(pilares, int) or pilares <= 0:
                findings.append(
                    _finding(
                        "error",
                        "invalid-pillar-count",
                        "pilares deve ser inteiro positivo",
                        skill_name,
                    )
                )
            raio_pilar = raw.get("raio_pilar")
            if (
                isinstance(raio_pilar, bool)
                or not isinstance(raio_pilar, (int, float))
                or raio_pilar <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-pillar-radius",
                        "pilares exige raio_pilar positivo",
                        skill_name,
                    )
                )
        elif "raio_pilar" in raw:
            findings.append(
                _finding(
                    "error",
                    "orphan-pillar-radius",
                    "raio_pilar exige pilares",
                    skill_name,
                )
            )

        if raw.get("invisivel_durante") is True:
            delay_saida = raw.get("delay_saida")
            if (
                isinstance(delay_saida, bool)
                or not isinstance(delay_saida, (int, float))
                or delay_saida <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-invisible-exit-delay",
                        "invisivel_durante exige delay_saida positivo",
                        skill_name,
                    )
                )
        elif "delay_saida" in raw:
            findings.append(
                _finding(
                    "error",
                    "orphan-invisible-exit-delay",
                    "delay_saida exige invisivel_durante=True",
                    skill_name,
                )
            )

        if "esquiva_garantida" in raw:
            charges = raw["esquiva_garantida"]
            if isinstance(charges, bool) or not isinstance(charges, int) or charges <= 0:
                findings.append(
                    _finding(
                        "error",
                        "invalid-dodge-charges",
                        "esquiva_garantida deve ser inteiro positivo",
                        skill_name,
                    )
                )

        if "stacks_por_segundo" in raw:
            stacks = raw["stacks_por_segundo"]
            if isinstance(stacks, bool) or not isinstance(stacks, int) or stacks <= 0:
                findings.append(
                    _finding(
                        "error",
                        "invalid-stack-rate",
                        "stacks_por_segundo deve ser inteiro positivo",
                        skill_name,
                    )
                )
            duration = raw.get("duracao")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or duration <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "missing-stacking-area-duration",
                        "stacks_por_segundo exige duracao positiva",
                        skill_name,
                    )
                )

        if "descricao" in raw and not isinstance(raw["descricao"], str):
            findings.append(_finding("error", "invalid-description", "descricao deve ser texto", skill_name))

        if "cor" in raw:
            color = raw["cor"]
            valid_color = (
                isinstance(color, (tuple, list))
                and len(color) == 3
                and all(isinstance(channel, int) and not isinstance(channel, bool) and 0 <= channel <= 255 for channel in color)
            )
            if not valid_color:
                findings.append(
                    _finding("error", "invalid-color", "cor deve conter tres inteiros entre 0 e 255", skill_name)
                )

        effect = raw.get("efeito")
        if effect:
            canonical_effect = status_aliases.get(str(effect).upper(), str(effect).upper())
            if canonical_effect not in known_effects:
                findings.append(
                    _finding(
                        "warning",
                        "effect-without-contract",
                        f"efeito sem contrato estrutural conhecido: {effect}",
                        skill_name,
                    )
                )
            category = status_runtime.get(canonical_effect, {}).get("categoria", "")
            if category == "pendente" or str(category).endswith("_parcial"):
                findings.append(
                    _finding(
                        "warning",
                        "partial-status-contract",
                        f"efeito possui contrato parcial ou pendente: {canonical_effect}",
                        skill_name,
                    )
                )

        buff_effect = raw.get("efeito_buff")
        if buff_effect and buff_effect not in buff_runtime:
            findings.append(
                _finding(
                    "warning",
                    "buff-without-contract",
                    f"efeito_buff sem contrato conhecido: {buff_effect}",
                    skill_name,
                )
            )

        evidence_fields = sorted(
            (RUNTIME_EVIDENCE_FIELDS & raw.keys()) - verified_evidence.keys()
        )
        if verify_evidence_sources and evidence_fields:
            findings.append(
                _finding(
                    "warning",
                    "runtime-evidence-required",
                    "campos exigem teste de runtime/paridade: " + ", ".join(evidence_fields),
                    skill_name,
                )
            )

    return AuditReport(
        catalog=catalog_label,
        evidence_manifest=evidence_label,
        total=len(catalog),
        by_type=dict(sorted(by_type.items())),
        evidence_sources_verified=verify_evidence_sources,
        verified_runtime_evidence=verified_evidence,
        findings=tuple(findings),
    )


def render_text(report: AuditReport) -> str:
    lines = [
        "SKILL CATALOG STRUCTURAL AUDIT",
        f"Catalog: {report.catalog}",
        f"Evidence manifest: {report.evidence_manifest}",
        f"Total records: {report.total}",
        f"Structurally valid records: {report.structurally_valid}",
        f"Errors: {report.errors}",
        f"Warnings: {report.warnings}",
        "Types: " + ", ".join(f"{name}={count}" for name, count in report.by_type.items()),
    ]
    if not report.evidence_sources_verified:
        lines.append("Runtime evidence source verification: not requested")
    elif report.verified_runtime_evidence:
        lines.append("Verified runtime evidence:")
        for field_name, references in report.verified_runtime_evidence.items():
            lines.append(f"- {field_name}: " + ", ".join(references))
    else:
        lines.append("Verified runtime evidence: none")
    if report.findings:
        lines.append("Findings:")
        for item in report.findings:
            location = f" [{item.skill}]" if item.skill else ""
            lines.append(f"- {item.level.upper()} {item.code}{location}: {item.message}")
    else:
        lines.append("Findings: none")
    lines.append(
        "Scope: structural contracts only; this report does not claim runtime functionality."
    )
    return "\n".join(lines) + "\n"


def _write_output(text: str, stream: TextIO) -> None:
    """Escreve sem falhar em consoles Windows com encoding limitado."""
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        stream.write(safe_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="retorna codigo 2 quando houver warnings (erros sempre retornam 1)",
    )
    parser.add_argument("--json", action="store_true", help="emite o relatorio como JSON ASCII")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="arquivo Python com SKILL_DB",
    )
    parser.add_argument(
        "--status-contract",
        type=Path,
        default=DEFAULT_STATUS_CONTRACT,
        help="arquivo Python com os contratos de status",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=DEFAULT_EVIDENCE_MANIFEST,
        help="arquivo Python literal com SKILL_RUNTIME_EVIDENCE",
    )
    parser.add_argument(
        "--verify-evidence-sources",
        action="store_true",
        help=(
            "confere via AST se cada evidencia aponta para um teste do checkout; "
            "nao use esta opcao em uma instalacao sem tests/"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    args = build_parser().parse_args(argv)
    catalog_path = args.catalog.resolve()
    status_path = args.status_contract.resolve()
    evidence_path = args.evidence_manifest.resolve()
    try:
        catalog, contracts, evidence = load_sources(
            catalog_path,
            status_path,
            evidence_path,
        )
        report = audit_catalog(
            catalog,
            contracts,
            evidence,
            catalog_label=str(catalog_path),
            evidence_label=str(evidence_path),
            project_root=SOURCE_ROOT,
            verify_evidence_sources=args.verify_evidence_sources,
        )
    except AuditInputError as exc:
        _write_output(f"audit input error: {exc}\n", stderr)
        return 1

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
