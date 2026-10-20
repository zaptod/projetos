# -*- coding: utf-8 -*-
"""O que o PUBLICO le no duelo, em ingles, por mapa explicito (pt -> en).

Decisao `geral/canal-em-ingles` (20/10/2026): titulo, legenda, hashtags,
texto na tela e voz do duelo em ingles; codigo, comentarios e docs seguem em
portugues. Nada aqui passa por LLM: cada termo tem a sua traducao escrita, e
`tests/test_ingles_do_duelo_regressions.py` FALHA se aparecer arma, classe,
elemento, plano ou callout sem traducao (catalogo do motor, config e banco
vivo quando legivel).

Em tempo de execucao a traducao que falta nao derruba o duelo (uma arma
nova na roleta pararia a geracao inteira): `rotulo_da_arma` devolve None e o
confronto cai na classe; o resto devolve o original. O teste e a guarda.
"""
from __future__ import annotations

import re

# Estilos de arma (`neural_fights.models.constants.TIPOS_ARMA[*]["estilos"]`):
# o termo comum em ingles.
ARMAS = {
    "Espada Longa": "Longsword", "Espada Curta": "Shortsword",
    "Montante": "Greatsword", "Katana": "Katana", "Sabre": "Saber",
    "Lança": "Spear", "Alabarda": "Halberd", "Machado": "Axe",
    "Martelo": "Hammer", "Maça": "Mace", "Foice": "Scythe",
    "Claymore": "Claymore",
    "Adagas Gêmeas": "Twin Daggers", "Sai": "Sai", "Kamas": "Kamas",
    "Garras": "Claws", "Tonfas": "Tonfas", "Facas Táticas": "Tactical Knives",
    "Kusarigama": "Kusarigama", "Mangual": "Flail", "Chicote": "Whip",
    "Corrente com Peso": "Weighted Chain", "Meteor Hammer": "Meteor Hammer",
    "Rope Dart": "Rope Dart",
    "Facas de Arremesso": "Throwing Knives", "Shuriken": "Shuriken",
    "Chakram": "Chakram", "Machados de Arremesso": "Throwing Axes",
    "Kunai": "Kunai", "Bumerangue": "Boomerang",
    "Arco Curto": "Shortbow", "Arco Longo": "Longbow",
    "Arco Composto": "Composite Bow", "Besta Leve": "Light Crossbow",
    "Besta Pesada": "Heavy Crossbow", "Arco Élfico": "Elven Bow",
    "Escudo Orbital": "Orbital Shield", "Drones de Combate": "Combat Drones",
    "Orbes Místicos": "Mystic Orbs", "Lâminas Orbitais": "Orbital Blades",
    "Cristais Flutuantes": "Floating Crystals", "Sentinelas": "Sentinels",
    "Espadas Espectrais": "Spectral Swords", "Runas Flutuantes": "Floating Runes",
    "Tentáculos Sombrios": "Shadow Tentacles", "Cristais Arcanos": "Arcane Crystals",
    "Lanças de Mana": "Mana Lances", "Chamas Espirituais": "Spirit Flames",
    "Espada-Lança": "Sword-Spear", "Espada Extensível": "Extending Sword",
    "Chicote-Espada": "Whip Sword", "Arco-Lâminas": "Blade Bow",
    "Bastão Segmentado": "Three-Section Staff", "Machado-Martelo": "Axe-Hammer",
}

# Classes (`CLASSES_DATA`), pela parte antes do parenteses.
CLASSES = {
    "Guerreiro": "Warrior", "Berserker": "Berserker", "Gladiador": "Gladiator",
    "Cavaleiro": "Knight", "Assassino": "Assassin", "Ladino": "Rogue",
    "Ninja": "Ninja", "Duelista": "Duelist", "Mago": "Mage",
    "Piromante": "Pyromancer", "Criomante": "Cryomancer",
    "Necromante": "Necromancer", "Paladino": "Paladin", "Druida": "Druid",
    "Feiticeiro": "Sorcerer", "Monge": "Monk",
}

# Afinidade da arma (`ENCANTAMENTOS`), como adjetivo antes da arma
# ("Flame Longsword"): so aparece no desempate.
ELEMENTOS = {
    "Chamas": "Flame", "Gelo": "Frost", "Relâmpago": "Lightning",
    "Veneno": "Poison", "Trevas": "Shadow", "Sagrado": "Holy",
    "Velocidade": "Swift", "Vampirismo": "Vampiric", "Crítico": "Keen",
    "Penetração": "Piercing", "Execução": "Executioner's", "Espelhamento": "Mirror",
}

# Rotulos do plano da IA (`neural_fights.ai.plano_de_luta.DEFINICOES`): o HUD
# do video os desenha sob a barra e o jogo, sob o lutador.
PLANOS = {
    "PRESSÃO": "PRESSURE", "ISCA": "BAIT", "ZONA MORTA": "DEAD ZONE",
    "PRA PAREDE": "PIN TO WALL", "JANELA": "OPENING", "RECUPERAR": "RECOVER",
    "QUEBRAR GUARDA": "GUARD BREAK", "CORTAR FUGA": "CUT OFF",
    "TROCAÇÃO": "SLUGFEST", "ACABAR": "FINISH", "ESMAGAR": "CRUSH",
}

# Callouts (`editing.json -> fight_callouts.textos`), MESMA ordem do config:
# a traducao acha o modelo portugues que gerou o texto e usa o de mesmo indice.
# Revisados como fala de narrador de luta em ingles (conferente, 20/10/2026:
# "ATE THE WALL" era traducao literal de "COMEU PAREDE").
CALLOUTS = {
    "ko": ["K.O.", "KNOCKOUT!", "IT'S OVER!"],
    "virada": ["COMEBACK!", "WHAT A TURNAROUND!", "TAKES THE LEAD!"],
    "combo": ["COMBO x{N}", "x{N} COMBO", "{N} HITS"],
    "parry": ["PARRY!", "PERFECT PARRY!", "SAW IT COMING"],
    "punicao": ["PUNISHED!", "WHIFF PUNISHED", "MAKES THEM PAY"],
    "primeiro_sangue": ["FIRST BLOOD", "DRAWS FIRST BLOOD"],
    "instinto": ["PURE INSTINCT!", "REFLEXES!"],
    "desvio": ["DODGED!", "SLIPS IT!"],
    "clinch": ["BREAKS FREE!", "CLINCH BROKEN"],
    "wall_splat": ["INTO THE WALL!", "WALL SPLAT!", "SLAMMED INTO THE WALL"],
    "agarrao": ["GRABBED!", "THROWN!", "SENT FLYING!"],
    "iniciativa": ["TAKES THE INITIATIVE", "ON THE ATTACK!"],
    "plano": ["{ROTULO}", "PLAN: {ROTULO}"],
    "obstaculo": ["SMASHED!", "WRECKS THE ARENA"],
}

# `runner._ko_type`
KO = {"KO": "KO", "DUPLO KO": "DOUBLE KO", "Decisao por HP": "HP DECISION"}

# Epitetos do nome do personagem (`neural_fights/tools/gerador_database.py:
# TITULOS`, mais o outro genero de cada um): "Helga o Protetor" -> "Helga the
# Protector". So na EXIBICAO (decisao do orquestrador, 20/10/2026): o banco
# guarda o nome em portugues e nada aqui o reescreve. O nome proprio fica.
EPITETOS = {
    "o Bravo": "the Brave", "a Brava": "the Brave",
    "o Valente": "the Valiant", "a Valente": "the Valiant",
    "o Nobre": "the Noble", "a Nobre": "the Noble",
    "o Justo": "the Just", "a Justa": "the Just",
    "o Sábio": "the Wise", "a Sábia": "the Wise",
    "o Protetor": "the Protector", "a Protetora": "the Protector",
    "o Invicto": "the Undefeated", "a Invicta": "the Undefeated",
    "o Lendário": "the Legendary", "a Lendária": "the Legendary",
    "o Cruel": "the Cruel", "a Cruel": "the Cruel",
    "o Impiedoso": "the Merciless", "a Impiedosa": "the Merciless",
    "o Sombrio": "the Dark", "a Sombria": "the Dark",
    "o Louco": "the Mad", "a Louca": "the Mad",
    "o Furioso": "the Furious", "a Furiosa": "the Furious",
    "o Destruidor": "the Destroyer", "a Destruidora": "the Destroyer",
    "o Implacável": "the Relentless", "a Implacável": "the Relentless",
    "o Imortal": "the Immortal", "a Imortal": "the Immortal",
    "o Eterno": "the Eternal", "a Eterna": "the Eternal",
    "o Amaldiçoado": "the Cursed", "a Amaldiçoada": "the Cursed",
    "o Abençoado": "the Blessed", "a Abençoada": "the Blessed",
    "o Profeta": "the Prophet", "a Profetisa": "the Prophet",
    "o Vidente": "the Seer", "a Vidente": "the Seer",
    "das Chamas": "of the Flames", "do Gelo": "of the Ice",
    "do Trovão": "of the Thunder", "das Sombras": "of the Shadows",
    "da Luz": "of the Light",
}
_EPITETOS_POR_TAMANHO = sorted(EPITETOS, key=len, reverse=True)


def nome(nome_pt: str | None) -> str:
    """"Helga o Protetor" -> "Helga the Protector"; "Kuro #2" fica; o
    desempate "#N" do banco sobrevive ("Helga o Protetor #2" -> "Helga the
    Protector #2"). Sem epiteto conhecido, o nome como veio."""
    texto = str(nome_pt or "")
    sufixo = ""
    achado = re.search(r"\s+#\d+$", texto)
    if achado:
        texto, sufixo = texto[:achado.start()], achado.group(0)
    for epiteto in _EPITETOS_POR_TAMANHO:
        if texto.endswith(" " + epiteto):
            return texto[: -len(epiteto)] + EPITETOS[epiteto] + sufixo
    return texto + sufixo

# Texto que o JOGO desenha dentro do clipe gravado (match_config
# "textos_da_tela", lido em `Simulador._texto_da_tela`): o plano sob o
# lutador e os textos flutuantes em portugues. FATAL!, CLASH!, SHATTER! e
# REVIVE! ja sao ingles.
# O agarrao que o jogo escreve sobre o lutador (`Simulador`, tell de agarrao;
# 66 de 139 duelos do disco tem um, conferente 20/10).
AGARRAO = {"ARREMESSO!": "THROW!", "JOELHADA": "KNEE!", "EMPURRÃO": "SHOVE!",
           "ESCAPOU": "ESCAPED!", "REVERSÃO!": "REVERSAL!"}
# O nome que o jogo escreve sobre a invocacao e o da skill SUMMON
# (`neural_fights.core.skills.SKILL_DB`, tipo SUMMON).
INVOCACOES = {"Fênix": "Phoenix", "Ira da Floresta": "Forest's Wrath",
              "Invocação: Espírito": "Spirit Summon", "Cópia Sombria": "Shadow Clone"}
TELA_DO_JOGO = {**PLANOS, **AGARRAO, **INVOCACOES, "CRÍTICO!": "CRIT!"}

PERGUNTA = "WHO WINS?"


def rotulo_da_arma(estilo: str | None) -> str | None:
    return ARMAS.get(str(estilo or "").strip()) if estilo else None


def classe(classe_pt: str | None) -> str:
    """"Necromante (Trevas)" ou "Necromante" -> "Necromancer"; sem traducao,
    o original sem o parenteses."""
    base = str(classe_pt or "").split("(")[0].strip()
    return CLASSES.get(base, base)


def elemento(elemento_pt: str | None) -> str:
    base = str(elemento_pt or "").strip()
    return ELEMENTOS.get(base, base)


def plano(rotulo: str | None) -> str:
    texto = str(rotulo or "")
    return PLANOS.get(texto.strip(), texto)


def ko(tipo: str | None) -> str:
    texto = str(tipo or "")
    return KO.get(texto.strip(), texto)


def cartel(texto: str | None) -> str:
    """"4V-2D" -> "4W-2L" (vitorias/derrotas)."""
    return re.sub(r"(\d+)V-(\d+)D", r"\1W-\2L", str(texto or ""))


def selo(selo_pt: str | None, nome: str = "", seq: int = 0) -> str:
    """Os tres selos do duelo (`DueloTimelineBuilder._selo`)."""
    texto = str(selo_pt or "").strip()
    if not texto:
        return ""
    if texto == "TITULO EM JOGO":
        return "TITLE ON THE LINE"
    if texto == "REVANCHE":
        return "REMATCH"
    if seq:
        return f"{nome} IS ON A {int(seq)}-WIN STREAK".strip()
    return texto


def callout(texto_pt: str, tipo: str, modelos_pt: list | None,
            n=None, rotulo_pt: str | None = None) -> str:
    """O callout em ingles: acha qual modelo portugues gerou ``texto_pt``
    (``CaptionGenerator.callout``: {N} e {ROTULO} preenchidos) e devolve o
    modelo ingles de mesmo indice, preenchido igual. Sem par, o original."""
    alvos = CALLOUTS.get(tipo) or []
    for indice, modelo in enumerate(modelos_pt or []):
        feito = (str(modelo).replace("{N}", str(n if n is not None else ""))
                 .replace("{ROTULO}", str(rotulo_pt or "PLANO")))
        if feito == texto_pt and indice < len(alvos):
            return (alvos[indice].replace("{N}", str(n if n is not None else ""))
                    .replace("{ROTULO}", plano(rotulo_pt) if rotulo_pt else "PLAN"))
    return texto_pt


def vence(rotulo: str) -> str:
    """"SHURIKEN WINS!" / "TACTICAL KNIVES WIN!": a concordancia pelo rotulo.
    Plural = a ultima palavra termina em "s" (e nao em "ss"): "Sentinels",
    "Twin Daggers", "Throwing Axes", "Claws". "SENTINELS WINS!" saiu no 1o
    render (20/10) e nenhum falante de ingles escreveria assim."""
    texto = str(rotulo or "").strip()
    ultima = (texto.split() or [""])[-1].lower()
    plural = ultima.endswith("s") and not ultima.endswith("ss")
    return f"{texto.upper()} {'WIN' if plural else 'WINS'}!"


def tela_do_jogo(*nomes: str) -> dict:
    """O mapa do que o JOGO desenha no clipe de UM duelo: o fixo
    (`TELA_DO_JOGO`) mais o nome de cada lutador com o epiteto traduzido (o
    rotulo sobre o lutador e o do caido)."""
    mapa = dict(TELA_DO_JOGO)
    for original in nomes:
        traduzido = nome(original)
        if original and traduzido != original:
            mapa[str(original)] = traduzido
    return mapa


__all__ = ["ARMAS", "CALLOUTS", "CLASSES", "ELEMENTOS", "EPITETOS", "KO", "PERGUNTA",
           "PLANOS", "TELA_DO_JOGO", "callout", "cartel", "classe", "elemento", "ko",
           "nome", "plano", "rotulo_da_arma", "selo", "tela_do_jogo"]
