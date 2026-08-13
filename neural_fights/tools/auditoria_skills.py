"""Auditoria estrutural, import-safe, do catalogo de skills.

A ferramenta valida somente contratos que podem ser demonstrados pelos arquivos
fonte. Ela nao instancia objetos de combate e nao classifica uma skill como
"funcional" sem um teste de runtime correspondente.
"""

from __future__ import annotations

import ast
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TextIO

try:
    from neural_fights.utils.console import SafeArgumentParser
except ModuleNotFoundError as exc:
    # A ferramenta tambem e executavel pelo caminho absoluto fora do checkout.
    if exc.name != "neural_fights":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from neural_fights.utils.console import SafeArgumentParser


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

# Inventario fechado do formato do catalogo. A lista nao e inferida do SKILL_DB:
# adicionar uma chave nova exige declarar aqui seu contrato antes que ela possa
# chegar silenciosamente ao runtime.
BASIC_FIELDS = {
    "alcance",
    "cooldown",
    "cor",
    "custo",
    "dano",
    "descricao",
    "distancia",
    "duracao",
    "duracao_max",
    "efeito",
    "elemento",
    "raio",
    "raio_area",
    "tipo",
    "velocidade",
    "vida",
}

MECHANICAL_FIELDS = {
    "afeta_caster",
    "alcance_cone",
    "angulo_cone",
    "ativa_ao_morrer",
    "aura_raio",
    "aura_slow",
    "aviso_visual",
    "bloqueia_movimento",
    "bloqueia_projeteis",
    "bonus_area",
    "bonus_dano",
    "bonus_dano_magico",
    "bonus_resistencia",
    "bonus_velocidade",
    "bonus_velocidade_ataque",
    "bonus_velocidade_movimento",
    "bonus_vs_trevas",
    "buff_dano",
    "buff_velocidade",
    "canalizavel",
    "chain",
    "chain_decay",
    "chain_range",
    "chance_backfire",
    "chance_stun",
    "condicao",
    "cone",
    "consome_ao_causar_dano",
    "contagioso",
    "copia_caster",
    "cria_portal",
    "cura",
    "cura_percent",
    "cura_por_morte",
    "cura_por_segundo",
    "cura_tick",
    "custo_mana_metade",
    "custo_vida",
    "custo_vida_percent",
    "dano_bonus_condicao",
    "dano_chegada",
    "dano_contato",
    "dano_meteoro",
    "dano_por_segundo",
    "dano_recebido_bonus",
    "dano_tick",
    "dano_variavel",
    "delay",
    "delay_explosao",
    "delay_saida",
    "duplica_apos",
    "duracao_charme",
    "duracao_controle",
    "duracao_fear",
    "duracao_imortal",
    "duracao_portal",
    "duracao_stop",
    "duracao_stun",
    "duracao_taunt",
    "efeito2",
    "efeito_aleatorio",
    "efeito_buff",
    "efeitos_possiveis",
    "elemento_aleatorio",
    "escudo",
    "esquiva_garantida",
    "executa",
    "forca_empurrao",
    "gravidade_aumentada",
    "ground",
    "homing",
    "imobiliza",
    "imune_debuffs",
    "imune_ground",
    "intangivel",
    "invencivel",
    "invisivel_durante",
    "lifesteal",
    "link_percent",
    "max_splits",
    "meteoros_aleatorios",
    "multi_shot",
    "ondas",
    "penetra_escudo",
    "perfura",
    "pilares",
    "puxa_continuo",
    "puxa_para_centro",
    "raio_contagio",
    "raio_explosao",
    "raio_meteoro",
    "raio_pilar",
    "reflete_dano",
    "reflete_projeteis",
    "reflete_skills",
    "refletir",
    "remove_congelamento",
    "remove_debuffs",
    "remove_todos_debuffs",
    "retorna",
    "reverte_estado",
    "revive_hp_percent",
    "rouba_buff",
    "sem_cooldown",
    "slow_fator",
    "split_aleatorio",
    "stacks_por_segundo",
    "stats_aleatorios",
    "summon_dano",
    "summon_tipo",
    "summon_vida",
    "taunt",
    "ve_ataques",
    "vida_estrutura",
    "voo",
}

KNOWN_FIELDS = BASIC_FIELDS | MECHANICAL_FIELDS

TYPE_ALLOWED_FIELDS = {
    "NADA": {"cooldown", "custo", "tipo"},
    "PROJETIL": {
        "alcance_cone", "angulo_cone", "bonus_vs_trevas", "chance_backfire",
        "condicao", "cone", "contagioso", "cooldown", "cor", "custo", "dano",
        "dano_bonus_condicao", "dano_variavel", "delay_explosao", "descricao",
        "duplica_apos", "duracao_controle", "efeito", "elemento",
        "elemento_aleatorio", "executa", "homing", "lifesteal", "link_percent",
        "max_splits", "multi_shot", "perfura", "raio", "raio_contagio",
        "raio_explosao", "retorna", "rouba_buff", "split_aleatorio", "tipo",
        "velocidade", "vida",
    },
    "AREA": {
        "afeta_caster", "aviso_visual", "chance_stun", "condicao", "cooldown",
        "cor", "cura_por_morte", "custo", "custo_vida_percent", "dano",
        "dano_bonus_condicao", "dano_meteoro", "dano_por_segundo", "dano_tick",
        "delay", "descricao", "duracao", "duracao_charme", "duracao_fear",
        "duracao_stop", "duracao_stun", "duracao_taunt", "efeito", "efeito2",
        "efeito_aleatorio", "efeitos_possiveis", "elemento", "forca_empurrao",
        "gravidade_aumentada", "ground", "lifesteal", "meteoros_aleatorios",
        "ondas", "pilares", "puxa_continuo", "puxa_para_centro", "raio_area",
        "raio_meteoro", "raio_pilar", "remove_congelamento", "slow_fator",
        "stacks_por_segundo", "taunt", "tipo",
    },
    "DASH": {
        "cooldown", "cor", "cria_portal", "custo", "dano", "dano_chegada",
        "delay_saida", "descricao", "distancia", "duracao_portal", "efeito",
        "elemento", "invencivel", "invisivel_durante", "tipo",
    },
    "BUFF": {
        "ativa_ao_morrer", "bonus_area", "bonus_dano", "bonus_dano_magico",
        "bonus_velocidade", "bonus_velocidade_ataque", "bonus_velocidade_movimento",
        "buff_dano", "buff_velocidade", "consome_ao_causar_dano", "cooldown",
        "cor", "cura", "cura_percent", "cura_tick", "custo", "custo_mana_metade",
        "custo_vida", "dano_contato", "dano_recebido_bonus", "descricao", "duracao",
        "duracao_imortal", "efeito_buff", "elemento", "escudo",
        "esquiva_garantida", "imune_debuffs", "imune_ground", "lifesteal",
        "reflete_dano", "reflete_projeteis", "reflete_skills", "refletir",
        "remove_debuffs", "remove_todos_debuffs", "reverte_estado",
        "revive_hp_percent", "sem_cooldown", "stats_aleatorios", "tipo",
        "ve_ataques", "voo",
    },
    "BEAM": {
        "alcance", "bonus_vs_trevas", "canalizavel", "chain", "chain_decay",
        "chain_range", "cooldown", "cor", "custo", "dano", "dano_por_segundo",
        "descricao", "duracao_max", "efeito", "elemento", "penetra_escudo", "tipo",
    },
    "SUMMON": {
        "cooldown", "copia_caster", "cor", "custo", "dano", "descricao",
        "duracao", "elemento", "summon_dano", "summon_tipo", "summon_vida", "tipo",
    },
    "TRAP": {
        "bloqueia_movimento", "bloqueia_projeteis", "cooldown", "cor", "custo",
        "dano", "dano_contato", "descricao", "duracao", "elemento", "tipo",
        "vida_estrutura",
    },
    "TRANSFORM": {
        "aura_raio", "aura_slow", "bonus_resistencia", "bonus_velocidade",
        "cooldown", "cor", "custo", "dano_contato", "descricao", "duracao",
        "elemento", "intangivel", "tipo",
    },
    "CHANNEL": {
        "canalizavel", "cooldown", "cor", "cura_por_segundo", "custo", "descricao",
        "duracao_max", "elemento", "imobiliza", "tipo",
    },
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

NUMERIC_FIELDS = {
    "alcance", "alcance_cone", "angulo_cone", "aura_raio", "aura_slow",
    "bonus_area", "bonus_dano", "bonus_dano_magico", "bonus_resistencia",
    "bonus_velocidade", "bonus_velocidade_ataque", "bonus_velocidade_movimento",
    "bonus_vs_trevas", "buff_dano", "buff_velocidade", "chain", "chain_decay",
    "chain_range", "chance_backfire", "chance_stun", "cooldown", "cura",
    "cura_percent", "cura_por_morte", "cura_por_segundo", "cura_tick", "custo",
    "custo_vida", "custo_vida_percent", "dano", "dano_bonus_condicao",
    "dano_chegada", "dano_contato", "dano_meteoro", "dano_por_segundo",
    "dano_recebido_bonus", "dano_tick", "delay", "delay_explosao", "delay_saida",
    "distancia", "duplica_apos", "duracao", "duracao_charme", "duracao_controle",
    "duracao_fear", "duracao_imortal", "duracao_max", "duracao_portal",
    "duracao_stop", "duracao_stun", "duracao_taunt", "escudo",
    "esquiva_garantida", "forca_empurrao", "gravidade_aumentada", "imune_debuffs",
    "lifesteal", "link_percent", "max_splits", "meteoros_aleatorios", "multi_shot",
    "ondas", "pilares", "raio", "raio_area", "raio_contagio", "raio_explosao",
    "raio_meteoro", "raio_pilar", "reflete_dano", "refletir", "remove_debuffs",
    "reverte_estado", "revive_hp_percent", "slow_fator", "stacks_por_segundo",
    "summon_dano", "summon_vida", "velocidade", "vida", "vida_estrutura",
}

ZERO_ALLOWED_NUMBER_FIELDS = {
    "cooldown",
    "custo",
    "dano",
    "distancia",
    "velocidade",
}

POSITIVE_NUMBER_FIELDS = NUMERIC_FIELDS - ZERO_ALLOWED_NUMBER_FIELDS

MULTIPLIER_FIELDS = {
    "bonus_area",
    "bonus_dano",
    "bonus_dano_magico",
    "bonus_velocidade",
    "bonus_velocidade_ataque",
    "bonus_velocidade_movimento",
    "bonus_vs_trevas",
    "buff_dano",
    "buff_velocidade",
    "dano_bonus_condicao",
    "dano_recebido_bonus",
}

PERSISTENT_BUFF_FIELDS = {
    "bonus_area",
    "bonus_dano",
    "bonus_dano_magico",
    "bonus_velocidade",
    "bonus_velocidade_ataque",
    "bonus_velocidade_movimento",
    "buff_dano",
    "buff_velocidade",
    "consome_ao_causar_dano",
    "custo_mana_metade",
    "dano_contato",
    "dano_recebido_bonus",
    "efeito_buff",
    "escudo",
    "esquiva_garantida",
    "imune_ground",
    "lifesteal",
    "reflete_dano",
    "reflete_projeteis",
    "reflete_skills",
    "refletir",
    "sem_cooldown",
    "stats_aleatorios",
    "ve_ataques",
    "voo",
}

BOOLEAN_CONTRACT_FIELDS = {
    "afeta_caster", "ativa_ao_morrer", "aviso_visual", "bloqueia_movimento",
    "bloqueia_projeteis", "canalizavel", "cone", "consome_ao_causar_dano",
    "contagioso", "copia_caster", "cria_portal", "custo_mana_metade",
    "efeito_aleatorio", "elemento_aleatorio", "executa", "ground", "homing",
    "imobiliza", "imune_ground", "intangivel", "invencivel", "invisivel_durante",
    "penetra_escudo", "perfura", "puxa_continuo", "puxa_para_centro",
    "reflete_projeteis", "reflete_skills", "remove_congelamento",
    "remove_todos_debuffs", "retorna", "rouba_buff", "sem_cooldown",
    "split_aleatorio", "stats_aleatorios", "taunt", "ve_ataques", "voo",
}

FRACTION_FIELDS = {
    "aura_slow",
    "bonus_resistencia",
    "chain_decay",
    "chance_backfire",
    "chance_stun",
    "cura_percent",
    "custo_vida_percent",
    "lifesteal",
    "link_percent",
    "reflete_dano",
    "refletir",
    "revive_hp_percent",
    "slow_fator",
}

INTEGER_FIELDS = {
    "angulo_cone",
    "chain",
    "esquiva_garantida",
    "max_splits",
    "meteoros_aleatorios",
    "multi_shot",
    "ondas",
    "pilares",
    "remove_debuffs",
    "stacks_por_segundo",
}

NON_EMPTY_TEXT_FIELDS = {
    "condicao",
    "descricao",
    "efeito",
    "efeito2",
    "efeito_buff",
    "elemento",
    "summon_tipo",
}

TRUE_ONLY_FIELDS = BOOLEAN_CONTRACT_FIELDS - {"afeta_caster"}

KNOWN_CONDITIONS = {
    "ALVO_BAIXA_VIDA",
    "ALVO_CONGELADO",
    "ALVO_QUEIMANDO",
}

# Estes campos sao validos estruturalmente, mas sua presenca nao prova que a
# mecanica tenha paridade entre simulador visual, headless e torneio.
RUNTIME_EVIDENCE_FIELDS = MECHANICAL_FIELDS

# Um mesmo nome pode alimentar caminhos de execucao diferentes. Nesses casos o
# manifesto prova cada combinacao separadamente e nao mascara um ramo inerte.
RUNTIME_EVIDENCE_VARIANTS = {
    "bonus_velocidade": {"BUFF", "TRANSFORM"},
    "bonus_vs_trevas": {"BEAM", "PROJETIL"},
    "canalizavel": {"BEAM", "CHANNEL"},
    "condicao": {"AREA", "PROJETIL"},
    "dano_bonus_condicao": {"AREA", "PROJETIL"},
    "dano_contato": {"BUFF", "TRAP", "TRANSFORM"},
    "dano_por_segundo": {"AREA", "BEAM"},
    "lifesteal": {"AREA", "BUFF", "PROJETIL"},
}

RUNTIME_EVIDENCE_KEYS = (
    (RUNTIME_EVIDENCE_FIELDS - RUNTIME_EVIDENCE_VARIANTS.keys())
    | {
        f"{field_name}@{skill_type}"
        for field_name, skill_types in RUNTIME_EVIDENCE_VARIANTS.items()
        for skill_type in skill_types
    }
)

if len(BASIC_FIELDS) != 16 or len(MECHANICAL_FIELDS) != 115:
    raise RuntimeError("inventario de campos do SKILL_DB ficou incompleto")
if BASIC_FIELDS & MECHANICAL_FIELDS:
    raise RuntimeError("campos basicos e mecanicos nao podem se sobrepor")
if set().union(*TYPE_ALLOWED_FIELDS.values()) != KNOWN_FIELDS:
    raise RuntimeError("campos conhecidos e contratos por tipo estao dessincronizados")


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


def _validate_no_duplicate_literal_keys(node: ast.AST, path: Path) -> None:
    """Impede que ``ast.literal_eval`` esconda uma chave sobrescrita."""

    for mapping in (item for item in ast.walk(node) if isinstance(item, ast.Dict)):
        seen: dict[Any, ast.AST] = {}
        for key_node in mapping.keys:
            if key_node is None:  # ``**mapping`` nao e aceito por literal_eval.
                continue
            try:
                key = ast.literal_eval(key_node)
                hash(key)
            except (TypeError, ValueError):
                continue
            if key in seen:
                raise AuditInputError(
                    f"chave literal duplicada em {path}:{key_node.lineno}: {key!r}"
                )
            seen[key] = key_node


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
                    _validate_no_duplicate_literal_keys(value, path)
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


def _runtime_evidence_key(field_name: str, skill_type: str) -> str:
    if skill_type in RUNTIME_EVIDENCE_VARIANTS.get(field_name, set()):
        return f"{field_name}@{skill_type}"
    return field_name


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
    for field_name in sorted(RUNTIME_EVIDENCE_KEYS - provided_fields):
        findings.append(
            _finding(
                "error",
                "evidence-field-missing",
                f"manifesto nao mapeia o contrato mecanico: {field_name}",
            )
        )
    for field_name in sorted(provided_fields - RUNTIME_EVIDENCE_KEYS, key=str):
        findings.append(
            _finding(
                "error",
                "unknown-evidence-field",
                f"manifesto mapeia contrato mecanico desconhecido: {field_name!r}",
            )
        )

    for field_name in sorted(RUNTIME_EVIDENCE_KEYS & provided_fields):
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

        for field_name in sorted(raw.keys() - KNOWN_FIELDS, key=str):
            findings.append(
                _finding(
                    "error",
                    "unknown-field",
                    f"campo nao declarado no inventario: {field_name!r}",
                    skill_name,
                )
            )

        skill_type = raw.get("tipo")
        by_type[str(skill_type or "AUSENTE")] += 1
        if skill_type not in SUPPORTED_TYPES:
            findings.append(
                _finding("error", "unsupported-type", f"tipo ausente ou desconhecido: {skill_type!r}", skill_name)
            )
            continue

        for field_name in sorted((raw.keys() & KNOWN_FIELDS) - TYPE_ALLOWED_FIELDS[skill_type]):
            findings.append(
                _finding(
                    "error",
                    "invalid-advanced-field-type",
                    f"{field_name} nao e valido para {skill_type}",
                    skill_name,
                )
            )

        required = COMMON_REQUIRED | TYPE_REQUIRED[skill_type]
        for field_name in sorted(required - raw.keys()):
            findings.append(
                _finding("error", "missing-field", f"campo obrigatorio ausente: {field_name}", skill_name)
            )

        for field_name in sorted(NUMERIC_FIELDS & raw.keys()):
            value = raw[field_name]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-number",
                        f"{field_name} deve ser numerico finito",
                        skill_name,
                    )
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

        for field_name in sorted(INTEGER_FIELDS & raw.keys()):
            value = raw[field_name]
            if isinstance(value, bool) or not isinstance(value, int):
                findings.append(
                    _finding(
                        "error",
                        "invalid-integer",
                        f"{field_name} deve ser inteiro",
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
            elif field_name in TRUE_ONLY_FIELDS and raw[field_name] is not True:
                findings.append(
                    _finding(
                        "error",
                        "inactive-mechanic-flag",
                        f"{field_name}, quando declarado, deve ser True",
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

        for field_name in sorted(NON_EMPTY_TEXT_FIELDS & raw.keys()):
            value = raw[field_name]
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    _finding(
                        "error",
                        "invalid-text",
                        f"{field_name} deve ser texto nao vazio",
                        skill_name,
                    )
                )

        if "condicao" in raw and raw["condicao"] not in KNOWN_CONDITIONS:
            findings.append(
                _finding(
                    "error",
                    "unknown-condition",
                    f"condicao sem avaliador de combate: {raw['condicao']!r}",
                    skill_name,
                )
            )

        if "angulo_cone" in raw:
            angle = raw["angulo_cone"]
            if (
                not isinstance(angle, bool)
                and isinstance(angle, (int, float))
                and math.isfinite(angle)
                and angle > 360
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-cone-angle",
                        "angulo_cone nao pode exceder 360 graus",
                        skill_name,
                    )
                )

        if "dano_variavel" in raw:
            damage_range = raw["dano_variavel"]
            valid_range = (
                isinstance(damage_range, (tuple, list))
                and len(damage_range) == 2
                and all(
                    not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(value)
                    and value > 0
                    for value in damage_range
                )
                and damage_range[0] <= damage_range[1]
            )
            if not valid_range:
                findings.append(
                    _finding(
                        "error",
                        "invalid-damage-range",
                        "dano_variavel deve ser (minimo, maximo) positivo e ordenado",
                        skill_name,
                    )
                )

        if "efeitos_possiveis" in raw:
            possible_effects = raw["efeitos_possiveis"]
            valid_effects = (
                isinstance(possible_effects, (tuple, list))
                and bool(possible_effects)
                and all(
                    isinstance(effect_name, str)
                    and effect_name.strip()
                    and status_aliases.get(effect_name.upper(), effect_name.upper())
                    in known_effects
                    for effect_name in possible_effects
                )
                and len(set(possible_effects)) == len(possible_effects)
            )
            if not valid_effects:
                findings.append(
                    _finding(
                        "error",
                        "invalid-effect-list",
                        "efeitos_possiveis deve listar efeitos conhecidos sem repeticao",
                        skill_name,
                    )
                )

        paired_contracts = (
            ("cone", {"alcance_cone", "angulo_cone"}, "incomplete-cone-contract"),
            ("chain", {"chain_decay", "chain_range"}, "incomplete-chain-contract"),
            ("aura_slow", {"aura_raio"}, "incomplete-aura-contract"),
            ("cria_portal", {"duracao_portal"}, "incomplete-portal-contract"),
            (
                "efeito_aleatorio",
                {"efeitos_possiveis"},
                "incomplete-random-effect-contract",
            ),
            ("split_aleatorio", {"max_splits"}, "incomplete-split-contract"),
            ("taunt", {"duracao_taunt"}, "incomplete-taunt-contract"),
        )
        for trigger, companions, finding_code in paired_contracts:
            group = {trigger} | companions
            present = group & raw.keys()
            trigger_active = raw.get(trigger) is True if trigger in BOOLEAN_CONTRACT_FIELDS else trigger in raw
            if present and (not trigger_active or not companions <= raw.keys()):
                findings.append(
                    _finding(
                        "error",
                        finding_code,
                        f"{trigger} exige: {', '.join(sorted(companions))}",
                        skill_name,
                    )
                )

        if "dano_bonus_condicao" in raw and "condicao" not in raw:
            findings.append(
                _finding(
                    "error",
                    "orphan-conditional-damage",
                    "dano_bonus_condicao exige condicao",
                    skill_name,
                )
            )

        if "delay_explosao" in raw and "raio_explosao" not in raw:
            findings.append(
                _finding(
                    "error",
                    "incomplete-delayed-explosion",
                    "delay_explosao exige raio_explosao",
                    skill_name,
                )
            )

        for field_name in ("custo_vida", "custo_vida_percent"):
            if field_name in raw and raw.get("custo") != 0:
                findings.append(
                    _finding(
                        "error",
                        "ambiguous-resource-cost",
                        f"{field_name} exige custo de mana igual a zero",
                        skill_name,
                    )
                )

        if skill_type == "SUMMON":
            missing_summon_fields = {"summon_dano", "summon_vida"} - raw.keys()
            if missing_summon_fields:
                findings.append(
                    _finding(
                        "error",
                        "incomplete-summon-contract",
                        "SUMMON exige: " + ", ".join(sorted(missing_summon_fields)),
                        skill_name,
                    )
                )

        if skill_type == "TRAP" and (
            raw.get("bloqueia_movimento") is True
            or raw.get("bloqueia_projeteis") is True
        ) and "vida_estrutura" not in raw:
            findings.append(
                _finding(
                    "error",
                    "blocking-trap-without-health",
                    "TRAP bloqueadora exige vida_estrutura",
                    skill_name,
                )
            )

        if "multi_shot" in raw:
            shots = raw["multi_shot"]
            if isinstance(shots, int) and not isinstance(shots, bool) and shots <= 1:
                findings.append(
                    _finding(
                        "error",
                        "invalid-multishot-count",
                        "multi_shot deve ser inteiro maior que um",
                        skill_name,
                    )
                )

        duration_requirements = {
            "cura_tick": "duracao",
            "dano_tick": "duracao",
            "ground": "duracao",
            "puxa_continuo": "duracao",
        }
        for trigger, duration_field in duration_requirements.items():
            if trigger not in raw or raw.get(trigger) is False:
                continue
            if duration_field not in raw:
                findings.append(
                    _finding(
                        "error",
                        "missing-mechanic-duration",
                        f"{trigger} exige {duration_field}",
                        skill_name,
                    )
                )

        if "dano_por_segundo" in raw:
            required_duration = "duracao_max" if skill_type == "BEAM" else "duracao"
            if required_duration not in raw:
                findings.append(
                    _finding(
                        "error",
                        "missing-periodic-damage-duration",
                        f"dano_por_segundo em {skill_type} exige {required_duration}",
                        skill_name,
                    )
                )
            if skill_type == "BEAM" and raw.get("canalizavel") is not True:
                findings.append(
                    _finding(
                        "error",
                        "non-channelled-beam-dps",
                        "dano_por_segundo em BEAM exige canalizavel=True",
                        skill_name,
                    )
                )

        if "cura_por_segundo" in raw and raw.get("canalizavel") is not True:
            findings.append(
                _finding(
                    "error",
                    "non-channelled-healing",
                    "cura_por_segundo exige canalizavel=True",
                    skill_name,
                )
            )

        expected_effects_by_duration = {
            "duracao_charme": "CHARME",
            "duracao_controle": "POSSESSO",
            "duracao_fear": "MEDO",
            "duracao_stop": "TEMPO_PARADO",
            "duracao_taunt": None,
        }
        for duration_field, expected_effect in expected_effects_by_duration.items():
            if duration_field not in raw or expected_effect is None:
                continue
            canonical = status_aliases.get(
                str(raw.get("efeito", "")).upper(),
                str(raw.get("efeito", "")).upper(),
            )
            if canonical != expected_effect:
                findings.append(
                    _finding(
                        "error",
                        "mismatched-control-duration",
                        f"{duration_field} exige efeito {expected_effect}",
                        skill_name,
                    )
                )

        if "duracao_imortal" in raw and raw.get("efeito_buff") != "IMORTAL":
            findings.append(
                _finding(
                    "error",
                    "mismatched-immortality-duration",
                    "duracao_imortal exige efeito_buff IMORTAL",
                    skill_name,
                )
            )

        if raw.get("imune_ground") is True and raw.get("voo") is not True:
            findings.append(
                _finding(
                    "error",
                    "ground-immunity-without-flight",
                    "imune_ground exige voo=True",
                    skill_name,
                )
            )

        if raw.get("remove_todos_debuffs") is True and "imune_debuffs" not in raw:
            findings.append(
                _finding(
                    "error",
                    "purge-without-immunity-window",
                    "remove_todos_debuffs exige imune_debuffs",
                    skill_name,
                )
            )

        if raw.get("executa") is True and "condicao" not in raw:
            findings.append(
                _finding(
                    "error",
                    "execute-without-condition",
                    "executa exige condicao",
                    skill_name,
                )
            )

        if raw.get("consome_ao_causar_dano") is True and "buff_dano" not in raw:
            findings.append(
                _finding(
                    "error",
                    "consumable-buff-without-damage",
                    "consome_ao_causar_dano exige buff_dano",
                    skill_name,
                )
            )

        contagion_fields = {"contagioso", "raio_contagio"}
        if contagion_fields & raw.keys() and not contagion_fields <= raw.keys():
            findings.append(
                _finding(
                    "error",
                    "incomplete-contagion-contract",
                    "contagioso e raio_contagio devem ser declarados juntos",
                    skill_name,
                )
            )

        if "lifesteal" in raw and skill_type != "BUFF":
            damage = raw.get("dano")
            if (
                isinstance(damage, bool)
                or not isinstance(damage, (int, float))
                or not math.isfinite(damage)
                or damage <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "lifesteal-without-damage",
                        "lifesteal ofensivo exige dano positivo",
                        skill_name,
                    )
                )

        for field_name in ("gravidade_aumentada", "slow_fator"):
            if field_name in raw and "duracao" not in raw:
                findings.append(
                    _finding(
                        "error",
                        "missing-mechanic-duration",
                        f"{field_name} exige duracao",
                        skill_name,
                    )
                )

        if "custo_vida_percent" in raw:
            damage = raw.get("dano")
            if (
                isinstance(damage, bool)
                or not isinstance(damage, (int, float))
                or not math.isfinite(damage)
                or damage <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "health-cost-without-payoff",
                        "custo_vida_percent exige dano positivo",
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

        if "ondas" in raw:
            wave_count = raw["ondas"]
            if (
                isinstance(wave_count, bool)
                or not isinstance(wave_count, int)
                or wave_count <= 1
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-wave-count",
                        "ondas deve ser inteiro maior que um",
                        skill_name,
                    )
                )
            wave_duration = raw.get("duracao", 1.0)
            if (
                isinstance(wave_duration, bool)
                or not isinstance(wave_duration, (int, float))
                or wave_duration <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-wave-duration",
                        "ondas exige duracao efetiva positiva",
                        skill_name,
                    )
                )

        meteor_payload_fields = {"dano_meteoro", "raio_meteoro"}
        if "meteoros_aleatorios" in raw:
            meteor_count = raw["meteoros_aleatorios"]
            if (
                isinstance(meteor_count, bool)
                or not isinstance(meteor_count, int)
                or meteor_count <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-meteor-count",
                        "meteoros_aleatorios deve ser inteiro positivo",
                        skill_name,
                    )
                )
            missing_payload = meteor_payload_fields - raw.keys()
            if missing_payload:
                findings.append(
                    _finding(
                        "error",
                        "incomplete-meteor-contract",
                        (
                            "meteoros_aleatorios exige payload explicito: "
                            + ", ".join(sorted(missing_payload))
                        ),
                        skill_name,
                    )
                )
            meteor_duration = raw.get("duracao", 1.0)
            if (
                isinstance(meteor_duration, bool)
                or not isinstance(meteor_duration, (int, float))
                or meteor_duration <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-meteor-duration",
                        "meteoros_aleatorios exige duracao efetiva positiva",
                        skill_name,
                    )
                )
        elif meteor_payload_fields & raw.keys():
            findings.append(
                _finding(
                    "error",
                    "orphan-meteor-payload",
                    "dano_meteoro e raio_meteoro exigem meteoros_aleatorios",
                    skill_name,
                )
            )

        if raw.get("aviso_visual") is True:
            warning_delay = raw.get("delay")
            if (
                isinstance(warning_delay, bool)
                or not isinstance(warning_delay, (int, float))
                or warning_delay <= 0
            ):
                findings.append(
                    _finding(
                        "error",
                        "invalid-area-warning-delay",
                        "aviso_visual=True exige delay positivo",
                        skill_name,
                    )
                )

        if "chance_stun" in raw:
            raw_effect = str(raw.get("efeito", "")).upper()
            canonical_stun_effect = status_aliases.get(raw_effect, raw_effect)
            if canonical_stun_effect not in {"ATORDOADO", "PARALISIA"}:
                findings.append(
                    _finding(
                        "error",
                        "invalid-stun-chance-effect",
                        (
                            "chance_stun exige efeito canonico "
                            "ATORDOADO ou PARALISIA"
                        ),
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

        secondary_effect = raw.get("efeito2")
        if secondary_effect:
            canonical_secondary = status_aliases.get(
                str(secondary_effect).upper(),
                str(secondary_effect).upper(),
            )
            if canonical_secondary not in known_effects:
                findings.append(
                    _finding(
                        "warning",
                        "secondary-effect-without-contract",
                        (
                            "efeito2 sem contrato estrutural conhecido: "
                            f"{secondary_effect}"
                        ),
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

        required_evidence = {
            _runtime_evidence_key(field_name, skill_type)
            for field_name in RUNTIME_EVIDENCE_FIELDS & raw.keys()
        }
        # O dano base de TRAP e dano de contato no runtime, embora o catalogo
        # historico ainda use a chave basica ``dano`` para esse ramo.
        if skill_type == "TRAP" and "dano" in raw:
            required_evidence.add("dano_contato@TRAP")
        evidence_fields = sorted(required_evidence - verified_evidence.keys())
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


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(description=__doc__)
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
