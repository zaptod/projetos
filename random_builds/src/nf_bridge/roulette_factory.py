"""Fabrica de roletas: monta as definicoes de roleta A PARTIR dos catalogos
do neural_fights. Se o neural_fights ganhar uma classe, estilo ou skill nova,
as roletas mudam junto — nenhuma opcao vive duplicada aqui.

Valores numericos rolam como inteiros escalados (x10/x100) e os builders
convertem para os floats do contrato do NF.
"""
from __future__ import annotations

from . import loader as nf


def character_roulettes() -> dict:
    return {
        "entity": "character",
        "roulettes": [
            {
                "id": "classe",
                "display_name": "CLASSE",
                "target": "classe",
                "type": "categorical",
                "evaluation": {"method": "neutral"},
                "options": [{"value": c, "label": c, "weight": 1} for c in nf.LISTA_CLASSES],
            },
            {
                "id": "personalidade",
                "display_name": "PERSONALIDADE",
                "target": "personalidade",
                "type": "categorical",
                "evaluation": {"method": "neutral"},
                "options": [{"value": p, "label": p, "weight": 1}
                            for p in nf.LISTA_PERSONALIDADES],
            },
            {
                # gerar_personagem sorteia tamanho em uniform(1.4, 2.2)
                "id": "tamanho",
                "display_name": "TAMANHO",
                "target": "tamanho_cm",
                "type": "numeric_range",
                "min": 140, "max": 220,
                "unit": "cm", "display_format": "meters",
                "distribution": {"kind": "normal", "mean_pct": 0.5, "std_pct": 0.22},
                "evaluation": {"method": "neutral"},
            },
            {
                # base 5.0 +/- (-2..3) + bonus de classe ate +3 no gerador oficial
                "id": "forca",
                "display_name": "FORCA",
                "target": "forca_x10",
                "type": "numeric_range",
                "min": 30, "max": 90,
                "display_format": "decimal10",
                "distribution": "stat_default",
                "evaluation": {"method": "higher_is_better"},
            },
            {
                "id": "mana",
                "display_name": "MANA",
                "target": "mana_x10",
                "type": "numeric_range",
                "min": 30, "max": 90,
                "display_format": "decimal10",
                "distribution": "stat_default",
                "evaluation": {"method": "higher_is_better"},
            },
        ],
    }


def weapon_roulettes() -> dict:
    estilo_options = []
    for tipo in nf.LISTA_TIPOS_ARMA:
        for idx, variante in enumerate(nf.variantes_do_tipo(tipo)):
            estilo_options.append({
                "value": variante["nome"], "label": variante["nome"],
                "weight": 1, "tipos": [tipo], "variante_idx": idx,
            })

    raridade_pesos = {"Comum": 30, "Incomum": 24, "Raro": 19,
                      "Épico": 14, "Lendário": 9, "Mítico": 4}
    raridade_scores = {"Comum": 22, "Incomum": 38, "Raro": 55,
                       "Épico": 72, "Lendário": 86, "Mítico": 97}

    skill_options = []
    for elemento, skills in nf.SKILLS_OFENSIVAS.items():
        encs = [enc for enc in nf.LISTA_ENCANTAMENTOS
                if nf.elemento_do_encantamento(enc) == elemento]
        if elemento == "FISICO":
            encs = list(nf.LISTA_ENCANTAMENTOS)  # fallback oficial: FISICO serve a todos
        for skill in skills:
            dados = nf.SKILL_DB[skill]
            skill_options.append({
                "value": skill, "label": skill, "weight": 1, "encs": encs,
                "score": max(30, min(95, round(30 + dados.get("dano", 0) * 0.6))),
            })

    return {
        "entity": "weapon",
        "roulettes": [
            {
                "id": "tipo",
                "display_name": "TIPO DE ARMA",
                "target": "tipo",
                "type": "categorical",
                "evaluation": {"method": "neutral"},
                "options": [{"value": t, "label": t, "weight": 1}
                            for t in nf.LISTA_TIPOS_ARMA],
            },
            {
                "id": "estilo",
                "display_name": "ESTILO",
                "target": "estilo",
                "type": "categorical",
                "evaluation": {"method": "neutral"},
                "options": estilo_options,
            },
            {
                "id": "raridade",
                "display_name": "RARIDADE",
                "target": "raridade",
                "type": "categorical",
                "evaluation": {"method": "categorical"},
                "options": [{"value": r, "label": r,
                             "weight": raridade_pesos[r], "score": raridade_scores[r]}
                            for r in nf.LISTA_RARIDADES],
            },
            {
                "id": "encantamento",
                "display_name": "ENCANTAMENTO",
                "target": "encantamento",
                "type": "categorical",
                "evaluation": {"method": "categorical"},
                "options": [{
                    "value": e, "label": e, "weight": 1,
                    "score": max(35, min(90, round(
                        45 + nf.ENCANTAMENTOS.get(e, {}).get("dano_bonus", 0) * 6))),
                } for e in nf.LISTA_ENCANTAMENTOS],
            },
            {
                "id": "habilidade",
                "display_name": "HABILIDADE",
                "target": "habilidade",
                "type": "categorical",
                "evaluation": {"method": "categorical"},
                "options": skill_options,
            },
            {
                # curva oficial: dano_base(raridade) + uniform(-1.5, 2.5)
                "id": "dano",
                "display_name": "DANO",
                "target": "dano",
                "type": "numeric_range",
                "min": 6, "max": 34,
                "eval_min": 6, "eval_max": 34,
                "distribution": {"kind": "uniform"},
                "evaluation": {"method": "higher_is_better"},
            },
            {
                "id": "peso",
                "display_name": "PESO",
                "target": "peso_x10",
                "type": "numeric_range",
                "min": 5, "max": 90,
                "unit": "kg", "display_format": "decimal10",
                "distribution": {"kind": "uniform"},
                "evaluation": {"method": "contextual", "context_fn": "peso_vs_forca"},
            },
            {
                # oficial: 2.0 + uniform(0,3) (+1.0 em Epico/Lendario/Mitico)
                "id": "critico",
                "display_name": "CRITICO",
                "target": "critico_x10",
                "type": "numeric_range",
                "min": 20, "max": 60,
                "eval_min": 20, "eval_max": 70,
                "display_format": "decimal10",
                "distribution": {"kind": "uniform"},
                "evaluation": {"method": "higher_is_better"},
            },
            {
                # oficial: 0.8 + uniform(0, 0.4)
                "id": "velocidade_ataque",
                "display_name": "VELOCIDADE DE ATAQUE",
                "target": "velocidade_x100",
                "type": "numeric_range",
                "min": 80, "max": 120,
                "display_format": "decimal100",
                "distribution": {"kind": "uniform"},
                "evaluation": {"method": "higher_is_better"},
            },
        ],
    }


def generated_rules() -> list[dict]:
    """Regras de dependencia derivadas dos catalogos oficiais."""
    rules: list[dict] = [
        {
            "id": "estilo_do_tipo",
            "description": "So estilos do tipo de arma sorteado.",
            "when": {"roulette": "estilo"},
            "then": [{"action": "restrict_options_by_tag",
                      "tag_field": "tipos", "source_path": "tipo"}],
        },
        {
            "id": "habilidade_do_encantamento",
            "description": "Skills do elemento do encantamento (+fisicas), como no gerador oficial.",
            "when": {"roulette": "habilidade"},
            "then": [{"action": "restrict_options_by_tag",
                      "tag_field": "encs", "source_path": "encantamento"}],
        },
        {
            "id": "critico_raridade_alta",
            "description": "Epico+ ganha +1.0 de critico (curva oficial).",
            "when": {"roulette": "critico", "path": "raridade", "op": "in",
                     "value": ["Épico", "Lendário", "Mítico"]},
            "then": [{"action": "clamp_range", "min": 30},
                     {"action": "set_distribution", "distribution": {"kind": "uniform"}}],
        },
    ]
    for raridade, base in nf.DANO_BASE_POR_RARIDADE.items():
        rules.append({
            "id": f"dano_{nf.sem_acento(raridade).lower()}",
            "description": f"Dano segue a curva oficial de {raridade}.",
            "when": {"roulette": "dano", "path": "raridade", "op": "eq", "value": raridade},
            "then": [{"action": "clamp_range", "min": base - 2, "max": base + 3}],
        })
    for tipo in nf.LISTA_TIPOS_ARMA:
        for variante in nf.variantes_do_tipo(tipo):
            peso_lo, peso_hi = variante.get("peso", (3, 5))
            rules.append({
                "id": f"peso_{nf.sem_acento(variante['nome']).lower().replace(' ', '_')}",
                "description": f"Peso dentro do range oficial de {variante['nome']}.",
                "when": {"roulette": "peso", "path": "estilo", "op": "eq",
                         "value": variante["nome"]},
                "then": [{"action": "clamp_range",
                          "min": max(1, round(peso_lo * 10)),
                          "max": round(peso_hi * 10)}],
            })
    return rules
