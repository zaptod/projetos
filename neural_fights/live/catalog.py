"""Vocabulario de comandos que espectadores podem disparar.

Este arquivo e **dados**, nao logica. Ele existe separado de ``effects.py`` pelo
mesmo motivo que ``SKILL_DB`` existe separado de ``combat.py``: um catalogo
declarativo pode ser auditado por AST, sem importar o jogo, e e exatamente isso
que ``neural_fights.tools.auditoria_comandos`` faz.

Todo campo aqui pertence a um inventario fechado. Chave nao declarada e **erro**
de auditoria, nunca aviso -- e a propriedade que impede o vocabulario de crescer
em silencio para dentro do runtime.

Categorias
----------
``ASSIST``
    Ajuda o lutador que o espectador escolheu. Escopo ``ALVO``.
``CAOS``
    Atinge os dois lutadores. Escopo ``GLOBAL``: a area e instanciada uma vez
    por lutador, cada uma pertencendo a um deles. Como ``AreaEffect`` ja exclui
    o proprio dono por padrao, o resultado e simetrico sem precisar de campo
    novo no catalogo de skills e sem dar credito de abate a quem nao lutou.
``PROXIMO_ROUND``
    Nunca altera o round em andamento; entra na fila e vale para a proxima
    partida. Escopo ``ROUND``.
"""

from __future__ import annotations


# --------------------------------------------------------------- inventarios

CATEGORIAS = ("ASSIST", "CAOS", "PROXIMO_ROUND")

ESCOPOS = ("ALVO", "GLOBAL", "ROUND")

MOMENTOS = ("ROUND_ATIVO", "ENTRE_ROUNDS")

# Verbos que ``effects.py`` sabe executar. Cada um mapeia para uma chamada de
# dominio que o motor ja usa; nenhum inventa mecanica de combate nova.
EFEITOS = (
    "BUFF_SKILL",      # Lutador._aplicar_buff_skill
    "LIMPAR_DEBUFF",   # Lutador.remover_debuffs
    "AREA_SKILL",      # AreaEffect -> buffer_areas
    "PROJETIL_SKILL",  # Projetil -> buffer_projeteis
    "TROCAR_ARENA",    # match_config["cenario"] da proxima partida
)

CAMPOS_OBRIGATORIOS = (
    "categoria",
    "escopo",
    "efeito",
    "custo_units",
    "cooldown_viewer",
    "max_por_round",
    "aplicavel_em",
    "descricao",
)

CAMPOS_OPCIONAIS = (
    "gatilho",
    "skill",
    "arenas",
    "cooldown_global",
    "somente_moderador",
)

CAMPOS_ACEITOS = frozenset(CAMPOS_OBRIGATORIOS + CAMPOS_OPCIONAIS)

# Campos de skill que dao vantagem ao dono da area. Num comando de escopo
# GLOBAL o dono e um dos lutadores por acidente de instanciacao, entao permitir
# qualquer um deles distribuiria beneficio a quem o espectador nao escolheu.
CAMPOS_INJUSTOS_EM_GLOBAL = (
    "lifesteal",
    "cura_por_morte",
    "rouba_buff",
    "executa",
)

# Verbos que exigem uma skill do catalogo canonico.
EFEITOS_COM_SKILL = ("BUFF_SKILL", "AREA_SKILL", "PROJETIL_SKILL")


# ------------------------------------------------------------------ catalogo

COMMAND_DB = {
    # === ASSIST: ajuda o lutador escolhido ==============================
    "curar": {
        "categoria": "ASSIST",
        "gatilho": "!curar",
        "escopo": "ALVO",
        "efeito": "BUFF_SKILL",
        "skill": "Cura Menor",
        "custo_units": 30,
        "cooldown_viewer": 45.0,
        "cooldown_global": 6.0,
        "max_por_round": 6,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Restaura vida do lutador escolhido.",
    },
    "curar_forte": {
        "categoria": "ASSIST",
        "gatilho": "!curargrande",
        "escopo": "ALVO",
        "efeito": "BUFF_SKILL",
        "skill": "Cura Maior",
        "custo_units": 90,
        "cooldown_viewer": 90.0,
        "cooldown_global": 15.0,
        "max_por_round": 3,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Cura forte e remove parte dos debuffs.",
    },
    "purificar": {
        "categoria": "ASSIST",
        "gatilho": "!purificar",
        "escopo": "ALVO",
        "efeito": "BUFF_SKILL",
        "skill": "Purificar",
        "custo_units": 70,
        "cooldown_viewer": 90.0,
        "cooldown_global": 12.0,
        "max_por_round": 3,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Limpa todos os debuffs e concede imunidade breve.",
    },
    "acelerar": {
        "categoria": "ASSIST",
        "gatilho": "!acelerar",
        "escopo": "ALVO",
        "efeito": "BUFF_SKILL",
        "skill": "Acelerar",
        "custo_units": 50,
        "cooldown_viewer": 60.0,
        "cooldown_global": 10.0,
        "max_por_round": 4,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Aumenta a velocidade do lutador escolhido.",
    },
    "fuma": {
        "categoria": "ASSIST",
        "gatilho": "!furia",
        "escopo": "ALVO",
        "efeito": "BUFF_SKILL",
        "skill": "Grito de Guerra",
        "custo_units": 60,
        "cooldown_viewer": 75.0,
        "cooldown_global": 12.0,
        "max_por_round": 3,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Aumenta o dano, ao custo de receber mais.",
    },
    "livrar": {
        "categoria": "ASSIST",
        "gatilho": "!livrar",
        "escopo": "ALVO",
        "efeito": "LIMPAR_DEBUFF",
        "custo_units": 25,
        "cooldown_viewer": 40.0,
        "cooldown_global": 5.0,
        "max_por_round": 6,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Remove os debuffs ativos do lutador escolhido.",
    },
    # === CAOS: atinge os dois ===========================================
    "meteoro": {
        "categoria": "CAOS",
        "gatilho": "!meteoro",
        "escopo": "GLOBAL",
        "efeito": "AREA_SKILL",
        "skill": "Explosão Nova",
        "custo_units": 120,
        "cooldown_viewer": 120.0,
        "cooldown_global": 25.0,
        "max_por_round": 2,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Explosao no centro da arena; empurra os dois lutadores.",
    },
    "nevasca": {
        "categoria": "CAOS",
        "gatilho": "!nevasca",
        "escopo": "GLOBAL",
        "efeito": "AREA_SKILL",
        "skill": "Nevasca",
        "custo_units": 80,
        "cooldown_viewer": 100.0,
        "cooldown_global": 20.0,
        "max_por_round": 2,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Deixa os dois lutadores lentos.",
    },
    "tempestade": {
        "categoria": "CAOS",
        "gatilho": "!tempestade",
        "escopo": "GLOBAL",
        "efeito": "AREA_SKILL",
        "skill": "Tempestade",
        "custo_units": 200,
        "cooldown_viewer": 180.0,
        "cooldown_global": 40.0,
        "max_por_round": 1,
        "aplicavel_em": ("ROUND_ATIVO",),
        "descricao": "Tempestade ampla que paralisa os dois lutadores.",
    },
    # === PROXIMO_ROUND: vale para a partida seguinte ====================
    "arena": {
        "categoria": "PROXIMO_ROUND",
        "gatilho": "!arena",
        "escopo": "ROUND",
        "efeito": "TROCAR_ARENA",
        "arenas": (
            "Arena",
            "Arena Pequena",
            "Coliseu",
            "Vulcao",
            "Gelo",
            "Cemiterio",
            "Espacial",
            "Inferno",
            "Cyberpunk",
            "Labirinto",
        ),
        "custo_units": 150,
        "cooldown_viewer": 300.0,
        "max_por_round": 1,
        "aplicavel_em": ("ROUND_ATIVO", "ENTRE_ROUNDS"),
        "descricao": "Define a arena da proxima partida.",
    },
}


GATILHOS = {
    dados["gatilho"]: command_id
    for command_id, dados in COMMAND_DB.items()
    if dados.get("gatilho")
}


def get_command(command_id: str) -> dict:
    """Devolve uma copia rasa; o catalogo nunca e mutado em runtime."""
    dados = COMMAND_DB.get(command_id)
    if dados is None:
        raise KeyError(f"comando desconhecido: {command_id!r}")
    return dict(dados)


def command_por_gatilho(gatilho: str) -> str | None:
    return GATILHOS.get(str(gatilho or "").strip().lower())


__all__ = [
    "CAMPOS_ACEITOS",
    "CAMPOS_INJUSTOS_EM_GLOBAL",
    "CAMPOS_OBRIGATORIOS",
    "CAMPOS_OPCIONAIS",
    "CATEGORIAS",
    "COMMAND_DB",
    "EFEITOS",
    "EFEITOS_COM_SKILL",
    "ESCOPOS",
    "GATILHOS",
    "MOMENTOS",
    "command_por_gatilho",
    "get_command",
]
