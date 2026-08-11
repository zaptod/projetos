"""Contrato canônico dos efeitos executados pelo runtime de combate.

``neural_fights.core.magic_system`` preserva o catálogo/engine experimental antigo para
compatibilidade. O estado real de uma luta, porém, vive em ``Lutador``. Este
módulo pequeno concentra apenas IDs, aliases e números que o runtime realmente
consome, evitando que os dois modelos sejam ligados em paralelo.
"""

from __future__ import annotations


STATUS_ALIASES = {
    "VENENO": "ENVENENADO",
    "SANGRAMENTO": "SANGRANDO",
    "QUEIMAR": "QUEIMANDO",
    "CONGELAR": "CONGELADO",
    "ATORDOAR": "ATORDOADO",
}


# ``dano_base`` é o valor entregue a DotEffect antes do redutor histórico de
# 50%. Mantê-lo aqui preserva exatamente o balanceamento já usado no runtime.
STATUS_RUNTIME = {
    "ENVENENADO": {
        "categoria": "dot",
        "duracao": 4.0,
        "dano_base": 1.5,
        "mod_cura_recebida": 0.5,
    },
    "SANGRANDO": {"categoria": "dot", "duracao": 3.0, "dano_base": 2.0},
    "QUEIMANDO": {"categoria": "dot", "duracao": 2.5, "dano_base": 2.5},
    "CORROENDO": {
        "categoria": "dot",
        "duracao": 4.0,
        "dano_base": 1.5,
        "mod_dano_recebido": 1.2,
    },
    "NECROSE": {
        "categoria": "dot",
        "duracao": 5.0,
        "dano_base": 3.0,
        "mod_cura_recebida": 0.0,
    },
    "MALDITO": {
        "categoria": "dot",
        "duracao": 6.0,
        "dano_base": 1.0,
        "mod_dano_recebido": 1.3,
        "mod_cura_recebida": 0.5,
    },
    "CONGELADO": {"categoria": "cc", "duracao": 2.0},
    "LENTO": {"categoria": "cc", "duracao": 2.0, "mod_velocidade": 0.5},
    "ATORDOADO": {"categoria": "cc", "duracao": 0.8},
    "PARALISIA": {"categoria": "cc", "duracao": 0.5},
    "ENRAIZADO": {"categoria": "cc", "duracao": 2.5},
    "SILENCIADO": {"categoria": "cc", "duracao": 3.0},
    "CEGO": {
        "categoria": "debuff",
        "duracao": 2.0,
        "desvio_mira_graus": 35.0,
    },
    "MEDO": {"categoria": "cc", "duracao": 2.5},
    "CHARME": {"categoria": "controle_mental", "duracao": 2.0},
    "SONO": {"categoria": "cc", "duracao": 4.0},
    "KNOCK_UP": {"categoria": "cc", "duracao": 0.5},
    "TEMPO_PARADO": {"categoria": "cc", "duracao": 2.0},
    "FRACO": {
        "categoria": "debuff",
        "duracao": 4.0,
        "mod_dano_causado": 0.7,
    },
    "VULNERAVEL": {
        "categoria": "debuff",
        "duracao": 4.0,
        "mod_dano_recebido": 1.5,
    },
    "EXAUSTO": {
        "categoria": "debuff",
        "duracao": 5.0,
        "mod_regen_mana": 0.3,
    },
    "MARCADO": {
        "categoria": "debuff",
        "duracao": 6.0,
        "mod_proximo_dano_recebido": 1.5,
    },
    "EXPOSTO": {
        "categoria": "debuff",
        "duracao": 4.0,
        "mod_dano_recebido": 2.0,
    },
    "BOMBA_RELOGIO": {
        "categoria": "especial",
        "duracao": 3.0,
        "raio_explosao": 2.5,
    },
    "LINK_ALMA": {
        "categoria": "especial",
        "duracao": 6.0,
        "percentual_compartilhado": 0.5,
    },
    "POSSESSO": {"categoria": "controle_mental", "duracao": 3.0},
    "TROCAR_POS": {"categoria": "transporte"},
    # O deslocamento real destes efeitos é processado fora do status. As flags
    # legadas ainda são aceitas, mas não são a fonte da força física.
    "PUXADO": {"categoria": "transporte"},
    "VORTEX": {"categoria": "transporte"},
}


BUFF_EFFECT_RUNTIME = {
    "ABENÇOADO": {
        "mod_cura_recebida": 1.5,
        "cura_por_segundo": 3.0,
    },
    "ACELERADO": {"buff_velocidade": 1.5},
    "DETERMINADO": {"mod_cooldown": 0.5},
    "FURIA": {
        "buff_dano": 1.8,
        "buff_velocidade": 1.2,
        "mod_dano_recebido": 1.3,
    },
    "IMORTAL": {"imortal": True},
    "REGENERANDO": {"cura_por_segundo": 8.0},
}


EFEITOS_TRATADOS_FORA_DO_STATUS = {
    "NORMAL",
    "PERFURAR",
    "DRENAR",
    "EMPURRAO",
    "EXPLOSAO",
}


DEBUFF_FAMILY_ORDER = (
    "NECROSE",
    "TEMPO_PARADO",
    "CONGELADO",
    "SONO",
    "ATORDOADO",
    "ENRAIZADO",
    "SILENCIADO",
    "EXPOSTO",
    "VULNERAVEL",
    "MALDITO",
    "CORROENDO",
    "ENVENENADO",
    "SANGRANDO",
    "QUEIMANDO",
    "FRACO",
    "EXAUSTO",
    "LENTO",
    "CEGO",
    "MEDO",
    "CHARME",
    "MARCADO",
    "POSSESSO",
    "LINK_ALMA",
    "BOMBA_RELOGIO",
)


def normalizar_efeito(efeito: object) -> str:
    """Converte aliases de transporte/catálogo no ID usado pelo runtime."""
    nome = str(efeito or "NORMAL").upper()
    return STATUS_ALIASES.get(nome, nome)


def get_status_runtime(efeito: object) -> dict:
    """Retorna a definição compartilhada, sem expor o dicionário mutável."""
    return STATUS_RUNTIME.get(normalizar_efeito(efeito), {}).copy()


def get_duracao_padrao(efeito: object, fallback: float) -> float:
    return float(get_status_runtime(efeito).get("duracao", fallback))


def efeito_bloqueado_por_imunidade(efeito: object) -> bool:
    """Dano/transporte físico continuam válidos durante imunidade a debuffs."""
    nome = normalizar_efeito(efeito)
    if nome in EFEITOS_TRATADOS_FORA_DO_STATUS:
        return False
    definicao = STATUS_RUNTIME.get(nome)
    return bool(definicao and definicao.get("categoria") != "transporte")


__all__ = [
    "BUFF_EFFECT_RUNTIME",
    "DEBUFF_FAMILY_ORDER",
    "EFEITOS_TRATADOS_FORA_DO_STATUS",
    "STATUS_ALIASES",
    "STATUS_RUNTIME",
    "efeito_bloqueado_por_imunidade",
    "get_duracao_padrao",
    "get_status_runtime",
    "normalizar_efeito",
]
