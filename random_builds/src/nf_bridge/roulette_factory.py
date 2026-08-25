"""Fabrica de roletas: monta as definicoes de roleta A PARTIR dos catalogos
do neural_fights. Se o neural_fights ganhar uma classe, estilo, raridade ou
skill nova, as roletas mudam junto - nenhuma opcao vive duplicada aqui.

Regra desta camada: NADA de conjunto fixo. Nao existe lista literal de
raridade, de tipo ou de elemento neste arquivo; peso, score e faixa saem da
posicao do item na lista canonica (ver loader). O que o banco novo ainda
precisa que ALGUEM cadastre (traducao de prompt, reacao) nao e problema da
roleta: sai no relatorio de cobertura.

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
                            for p in nf.lista_personalidades()],
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


def estilo_options() -> list[dict]:
    """Uma opcao POR NOME de estilo, nao por (tipo, variante).

    Dois tipos que oferecam o mesmo nome de estilo tem que virar UMA opcao com
    os dois tipos na tag: duas opcoes de mesmo value fariam a roda destacar o
    primeiro segmento e a regra de peso do segundo sobrescrever a do primeiro.
    """
    por_nome: dict[str, dict] = {}
    for tipo in nf.LISTA_TIPOS_ARMA:
        for idx, variante in enumerate(nf.variantes_do_tipo(tipo)):
            nome = variante["nome"]
            opcao = por_nome.get(nome)
            if opcao is None:
                opcao = {"value": nome, "label": nome, "weight": 1,
                         "tipos": [], "variante_idx": idx, "variante_idx_por_tipo": {}}
                por_nome[nome] = opcao
            if tipo not in opcao["tipos"]:
                opcao["tipos"].append(tipo)
            opcao["variante_idx_por_tipo"][tipo] = idx
    return list(por_nome.values())


def skill_options() -> list[dict]:
    """Skills ofensivas com a tag dos encantamentos que as liberam.

    Grupo que nenhum encantamento alcanca sai com encs vazio: a skill fica
    listada, mas a regra habilidade_do_encantamento nunca a mantem - e o
    relatorio de cobertura acusa o grupo orfao por nome.
    """
    por_skill: dict[str, dict] = {}
    for grupo, skills in nf.SKILLS_OFENSIVAS.items():
        encs = nf.encantamentos_do_grupo(grupo)
        for skill in skills:
            dados = nf.SKILL_DB.get(skill) or {}
            opcao = por_skill.get(skill)
            if opcao is None:
                opcao = {
                    "value": skill, "label": skill, "weight": 1, "encs": [],
                    "score": max(30, min(95, round(30 + dados.get("dano", 0) * 0.6))),
                }
                por_skill[skill] = opcao
            for enc in encs:
                if enc not in opcao["encs"]:
                    opcao["encs"].append(enc)
    return list(por_skill.values())


def weapon_roulettes() -> dict:
    dano_min, dano_max = nf.dano_envelope()
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
                "options": estilo_options(),
            },
            {
                "id": "raridade",
                "display_name": "RARIDADE",
                "target": "raridade",
                "type": "categorical",
                "evaluation": {"method": "categorical"},
                "options": [{"value": r, "label": r,
                             "weight": nf.raridade_peso(r),
                             "score": nf.raridade_score(r)}
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
                        45 + (nf.ENCANTAMENTOS.get(e) or {}).get("dano_bonus", 0) * 6))),
                } for e in nf.LISTA_ENCANTAMENTOS],
            },
            {
                "id": "habilidade",
                "display_name": "HABILIDADE",
                "target": "habilidade",
                "type": "categorical",
                "evaluation": {"method": "categorical"},
                "options": skill_options(),
            },
            {
                # curva oficial: dano_base(raridade) + uniform(-1.5, 2.5);
                # a faixa envolve a curva inteira, raridade nova inclusive
                "id": "dano",
                "display_name": "DANO",
                "target": "dano",
                "type": "numeric_range",
                "min": dano_min, "max": dano_max,
                "eval_min": dano_min, "eval_max": dano_max,
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
                # oficial: 2.0 + uniform(0,3) (+1.0 na metade rara)
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
    """Regras de dependencia derivadas dos catalogos oficiais.

    Toda regra daqui nasce de um item do catalogo, entao item novo ganha a sua
    regra sozinho. Os ids passam por um controle de unicidade porque id
    repetido nao levanta erro nenhum: a segunda regra so sobrescreve a
    primeira e o efeito some.
    """
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
    ]
    elite = nf.raridades_de_elite()
    if elite:
        rules.append({
            "id": "critico_raridade_alta",
            "description": "A metade rara da piramide ganha +1.0 de critico (curva oficial).",
            "when": {"roulette": "critico", "path": "raridade", "op": "in",
                     "value": elite},
            "then": [{"action": "clamp_range", "min": 30},
                     {"action": "set_distribution", "distribution": {"kind": "uniform"}}],
        })

    usados = {r["id"] for r in rules}

    def _id_unico(base: str) -> str:
        nome, sufixo = base, 2
        while nome in usados:
            nome = f"{base}_{sufixo}"
            sufixo += 1
        usados.add(nome)
        return nome

    for raridade in nf.LISTA_RARIDADES:
        base = nf.dano_base(raridade)
        rules.append({
            "id": _id_unico(f"dano_{nf.identificador(raridade)}"),
            "description": f"Dano segue a curva oficial de {raridade}.",
            "when": {"roulette": "dano", "path": "raridade", "op": "eq", "value": raridade},
            "then": [{"action": "clamp_range",
                      "min": round(base - 2), "max": round(base + 3)}],
        })

    # Um estilo pode ser oferecido por mais de um tipo: a faixa de peso da
    # regra e a UNIAO das faixas, senao o clamp de um tipo estrangula o outro.
    faixas: dict[str, tuple[float, float]] = {}
    for tipo in nf.LISTA_TIPOS_ARMA:
        for variante in nf.variantes_do_tipo(tipo):
            nome = variante["nome"]
            lo, hi = variante.get("peso", nf.PESO_VARIANTE_PADRAO)
            if nome in faixas:
                lo = min(lo, faixas[nome][0])
                hi = max(hi, faixas[nome][1])
            faixas[nome] = (lo, hi)
    for nome, (peso_lo, peso_hi) in faixas.items():
        rules.append({
            "id": _id_unico(f"peso_{nf.identificador(nome)}"),
            "description": f"Peso dentro do range oficial de {nome}.",
            "when": {"roulette": "peso", "path": "estilo", "op": "eq", "value": nome},
            "then": [{"action": "clamp_range",
                      "min": max(1, round(peso_lo * 10)),
                      "max": round(peso_hi * 10)}],
        })
    return rules
