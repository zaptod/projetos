"""Contratos semânticos compartilhados pela decisão de habilidades da IA."""

import math

from neural_fights.core.status_runtime import normalizar_efeito


_EFEITOS_BUFF_DANO = frozenset({"FURIA"})
_EFEITOS_BUFF_CURA = frozenset({"ABENCOADO", "ABENÇOADO", "REGENERANDO"})
_EFEITOS_BUFF_DEFENSIVOS = frozenset({"IMORTAL"})
_EFEITOS_BUFF_VELOCIDADE = frozenset({"ACELERADO"})


def numero_finito(valor, padrao=0.0):
    """Converte valores declarativos sem deixar NaN/Infinity contaminar scores."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return float(padrao)
    return numero if math.isfinite(numero) else float(padrao)


def valor_positivo(data, *campos):
    return any(numero_finito(data.get(campo)) > 0.0 for campo in campos)


def multiplicador_ativo(data, *campos):
    return any(numero_finito(data.get(campo), 1.0) > 1.0 for campo in campos)


def efeito_buff(data):
    return str(data.get("efeito_buff") or "").strip().upper()


def tem_cura(data):
    return (
        valor_positivo(
            data,
            "cura",
            "cura_por_segundo",
            "cura_tick",
            "regen",
            "cura_percent",
        )
        or efeito_buff(data) in _EFEITOS_BUFF_CURA
    )


def tem_buff_dano(data):
    return (
        multiplicador_ativo(
            data,
            "buff_dano",
            "bonus_dano",
            "bonus_dano_magico",
        )
        or efeito_buff(data) in _EFEITOS_BUFF_DANO
    )


def tem_buff_velocidade(data):
    return (
        multiplicador_ativo(
            data,
            "buff_velocidade",
            "bonus_velocidade",
            "bonus_velocidade_movimento",
            "bonus_velocidade_ataque",
        )
        or efeito_buff(data) in _EFEITOS_BUFF_VELOCIDADE
    )


def tem_reflexao(data):
    return valor_positivo(data, "refletir", "reflete_dano") or any(
        bool(data.get(campo)) for campo in ("reflete_projeteis", "reflete_skills")
    )


def tem_defesa(data):
    return (
        valor_positivo(data, "escudo", "imune_debuffs", "esquiva_garantida")
        or tem_reflexao(data)
        or bool(data.get("remove_todos_debuffs"))
        or efeito_buff(data) in _EFEITOS_BUFF_DEFENSIVOS
    )


def calcular_custo_vida(data, vida_max):
    """Replica a precedência do runtime: custo absoluto antes do percentual."""
    custo_absoluto = max(0.0, numero_finito(data.get("custo_vida")))
    if custo_absoluto > 0.0:
        return custo_absoluto
    percentual = max(0.0, numero_finito(data.get("custo_vida_percent")))
    return percentual * max(0.0, numero_finito(vida_max))


def alvo_tem_efeito(alvo, efeito):
    """Consulta os estados canônicos relevantes sem confundir debuffs distintos."""
    if alvo is None:
        return False
    efeito = normalizar_efeito(efeito)
    if efeito == "CONGELADO" and (
        bool(getattr(alvo, "congelado", False))
        or getattr(alvo, "congelado_timer", 0.0) > 0.0
    ):
        return True
    return any(
        normalizar_efeito(getattr(dot, "tipo", "")) == efeito
        and getattr(dot, "ativo", True)
        and getattr(dot, "vida", 1.0) > 0.0
        for dot in getattr(alvo, "dots_ativos", ())
    )
