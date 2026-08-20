# -*- coding: utf-8 -*-
"""Paleta central do Neural Fights (Passe 2 do programa de arte).

Antes dela existiam 8-10 tabelas de cor concorrentes: ELEMENT_PALETTES no
magic_vfx (a melhor, 60% desligada), CORES_CLASSE/CORES_RARIDADE em hex no
tema Tkinter (inacessíveis ao jogo), duas heurísticas de substring
re-derivando elemento e IGNORANDO o campo ``elemento`` que 90/109 skills
carregam, dicts locais redigitados em desenhar_arma, e três cópias
divergentes de cores de efeito. Este módulo é a fonte única; os antigos
importam daqui.

Sem dependência de pygame: importável pelo Tkinter e por ferramentas.
"""

from __future__ import annotations

# =============================================================================
# ELEMENTOS — 12/12 do catálogo de skills (TEMPO e GRAVITACAO faltavam:
# caíam no DEFAULT cinza).
# Estrutura: core (centro quente), mid[3], outer[3], spark, glow (RGBA).
# =============================================================================

ELEMENT_PALETTES = {
    "FOGO": {
        "core": (255, 255, 200),
        "mid": [(255, 180, 50), (255, 120, 0), (255, 80, 0)],
        "outer": [(255, 50, 0), (200, 30, 0), (150, 20, 0)],
        "spark": (255, 255, 100),
        "glow": (255, 100, 0, 100),
    },
    "GELO": {
        "core": (255, 255, 255),
        "mid": [(200, 240, 255), (150, 220, 255), (100, 200, 255)],
        "outer": [(80, 180, 255), (50, 150, 220), (30, 120, 200)],
        "spark": (220, 250, 255),
        "glow": (100, 200, 255, 100),
    },
    "RAIO": {
        "core": (255, 255, 255),
        "mid": [(255, 255, 150), (255, 255, 100), (200, 200, 255)],
        "outer": [(150, 150, 255), (100, 100, 255), (80, 80, 200)],
        "spark": (255, 255, 255),
        "glow": (150, 150, 255, 120),
    },
    "TREVAS": {
        "core": (150, 100, 200),
        "mid": [(100, 0, 150), (80, 0, 120), (60, 0, 100)],
        "outer": [(40, 0, 80), (30, 0, 60), (20, 0, 40)],
        "spark": (200, 150, 255),
        "glow": (100, 0, 150, 80),
    },
    "LUZ": {
        "core": (255, 255, 255),
        "mid": [(255, 255, 220), (255, 255, 180), (255, 240, 150)],
        "outer": [(255, 220, 100), (255, 200, 50), (255, 180, 0)],
        "spark": (255, 255, 255),
        "glow": (255, 255, 200, 150),
    },
    "NATUREZA": {
        "core": (200, 255, 200),
        "mid": [(100, 255, 100), (80, 220, 80), (60, 200, 60)],
        "outer": [(50, 180, 50), (40, 150, 40), (30, 120, 30)],
        "spark": (180, 255, 180),
        "glow": (100, 255, 100, 100),
    },
    "ARCANO": {
        "core": (255, 200, 255),
        "mid": [(220, 150, 255), (200, 100, 255), (180, 80, 255)],
        "outer": [(150, 50, 200), (120, 30, 180), (100, 20, 150)],
        "spark": (255, 200, 255),
        "glow": (200, 100, 255, 100),
    },
    "CAOS": {
        "core": (255, 255, 255),
        "mid": [(255, 100, 100), (100, 255, 100), (100, 100, 255)],
        "outer": [(255, 50, 200), (200, 50, 255), (50, 200, 255)],
        "spark": (255, 255, 255),
        "glow": (255, 100, 255, 100),
    },
    "SANGUE": {
        "core": (255, 200, 200),
        "mid": [(220, 50, 50), (200, 30, 30), (180, 20, 20)],
        "outer": [(150, 0, 0), (120, 0, 0), (100, 0, 0)],
        "spark": (255, 150, 150),
        "glow": (200, 0, 0, 100),
    },
    "VOID": {
        "core": (100, 50, 150),
        "mid": [(50, 0, 100), (30, 0, 80), (20, 0, 60)],
        "outer": [(10, 0, 40), (5, 0, 30), (0, 0, 20)],
        "spark": (150, 100, 200),
        "glow": (50, 0, 100, 80),
    },
    # Novos (Passe 2): fechavam os 12 elementos do catálogo.
    "TEMPO": {
        # Relojoaria etérea: prata-violeta, ponteiros de luz.
        "core": (240, 235, 255),
        "mid": [(210, 195, 255), (180, 165, 240), (150, 140, 220)],
        "outer": [(120, 110, 190), (95, 85, 160), (70, 60, 130)],
        "spark": (230, 220, 255),
        "glow": (180, 160, 255, 110),
    },
    "GRAVITACAO": {
        # Índigo denso puxando para o centro: peso, não brilho.
        "core": (200, 190, 255),
        "mid": [(140, 110, 255), (110, 80, 230), (90, 60, 200)],
        "outer": [(60, 40, 150), (45, 30, 120), (30, 20, 90)],
        "spark": (170, 150, 255),
        "glow": (110, 80, 230, 110),
    },
    "DEFAULT": {
        "core": (255, 255, 255),
        "mid": [(200, 200, 200), (180, 180, 180), (150, 150, 150)],
        "outer": [(120, 120, 120), (100, 100, 100), (80, 80, 80)],
        "spark": (255, 255, 255),
        "glow": (200, 200, 200, 100),
    },
}


def element_palette(elemento: str | None) -> dict:
    """Paleta do elemento, com fallback seguro para DEFAULT."""
    if not elemento:
        return ELEMENT_PALETTES["DEFAULT"]
    return ELEMENT_PALETTES.get(str(elemento).upper(), ELEMENT_PALETTES["DEFAULT"])


def get_element_from_skill(skill_nome: str, skill_data: dict) -> str:
    """Elemento de uma skill: campo do catálogo primeiro, heurística depois.

    (Movida do magic_vfx no Passe 2 — era a heurística mais completa do
    projeto e não tinha nenhum chamador; as vivas eram duas cópias de
    substring com 4 e 6 casos.)
    """
    if skill_data and "elemento" in skill_data:
        return str(skill_data["elemento"]).upper()

    nome_lower = (skill_nome or "").lower()
    if any(w in nome_lower for w in ["fogo", "fire", "chama", "meteoro", "inferno", "brasas"]):
        return "FOGO"
    if any(w in nome_lower for w in ["gelo", "ice", "glacial", "nevasca", "congelar"]):
        return "GELO"
    if any(w in nome_lower for w in ["raio", "lightning", "thunder", "relâmpago", "elétric"]):
        return "RAIO"
    if any(w in nome_lower for w in ["trevas", "shadow", "dark", "sombr", "necro"]):
        return "TREVAS"
    if any(w in nome_lower for w in ["luz", "light", "holy", "sagrado", "divino", "celestial"]):
        return "LUZ"
    if any(w in nome_lower for w in ["natureza", "nature", "veneno", "poison", "planta", "espin"]):
        return "NATUREZA"
    if any(w in nome_lower for w in ["arcano", "arcane", "mana", "magia"]):
        return "ARCANO"
    if any(w in nome_lower for w in ["caos", "chaos", "random"]):
        return "CAOS"
    if any(w in nome_lower for w in ["sangue", "blood", "vampir"]):
        return "SANGUE"
    if any(w in nome_lower for w in ["void", "vazio", "tentáculo"]):
        return "VOID"
    if any(w in nome_lower for w in ["tempo", "temporal", "slow", "eco "]):
        return "TEMPO"
    if any(w in nome_lower for w in ["gravita", "buraco negro", "colapso", "órbita"]):
        return "GRAVITACAO"
    return "DEFAULT"


def resolver_elemento(objeto=None, skill_nome: str = "", skill_data: dict | None = None) -> str:
    """Resolvedor ÚNICO de elemento (Passe 2).

    Ordem de verdade: o campo ``elemento`` que o próprio objeto de combate
    já carrega (Projetil/AreaEffect etc.) > o campo do catálogo > a
    heurística de nome. Substitui as duas heurísticas de substring que
    ignoravam ``proj.elemento`` e jogavam Relâmpago/Nevasca/Buraco Negro
    no cinza.
    """
    elemento = getattr(objeto, "elemento", None) if objeto is not None else None
    if elemento:
        return str(elemento).upper()
    return get_element_from_skill(skill_nome, skill_data or {})


# =============================================================================
# CLASSES e RARIDADES — fonte única em RGB; o tema Tkinter reexporta em hex.
# =============================================================================

def hex_to_rgb(valor: str) -> tuple[int, int, int]:
    v = valor.lstrip("#")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def rgb_to_hex(cor: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % (int(cor[0]), int(cor[1]), int(cor[2]))


CORES_CLASSE = {
    # Físicos
    "Guerreiro (Força Bruta)": (205, 127, 50),
    "Berserker (Fúria)": (255, 68, 68),
    "Gladiador (Combate)": (184, 134, 11),
    "Cavaleiro (Defesa)": (70, 130, 180),
    # Ágeis
    "Assassino (Crítico)": (128, 0, 128),
    "Ladino (Evasão)": (80, 80, 80),
    "Ninja (Velocidade)": (47, 47, 47),
    "Duelista (Precisão)": (255, 215, 0),
    # Mágicos
    "Mago (Arcano)": (100, 149, 237),
    "Piromante (Fogo)": (255, 102, 0),
    "Criomante (Gelo)": (135, 206, 235),
    "Necromante (Trevas)": (75, 0, 130),
    # Híbridos
    "Paladino (Sagrado)": (255, 204, 0),
    "Druida (Natureza)": (34, 139, 34),
    "Feiticeiro (Caos)": (153, 50, 204),
    "Monge (Chi)": (245, 245, 220),
}

CORES_RARIDADE = {
    "Comum": (180, 180, 180),
    "Incomum": (100, 200, 100),
    "Raro": (80, 140, 255),
    "Épico": (180, 80, 220),
    "Lendário": (255, 180, 50),
    "Mítico": (255, 100, 100),
}


def cor_classe(nome_classe: str) -> tuple[int, int, int]:
    """Cor da classe por nome (aceita nome parcial, ex. 'Cavaleiro')."""
    if nome_classe in CORES_CLASSE:
        return CORES_CLASSE[nome_classe]
    for chave, cor in CORES_CLASSE.items():
        if nome_classe and nome_classe.split(" ")[0] in chave:
            return cor
    return (200, 200, 200)


def cor_raridade(raridade: str) -> tuple[int, int, int]:
    return CORES_RARIDADE.get(raridade, CORES_RARIDADE["Comum"])
