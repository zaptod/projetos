"""Classifica cada rolagem para a EDICAO decidir onde o video reage.

O `RollEvaluator` responde "quao boa foi a rolagem" (score 0-100 -> tier). Isso
serve para a NOTA, mas nao para o corte: um resultado mediano que era
improvavel rende mais tela que um GOOD comum, e uma arma pesada demais para a
forca do personagem e engracada justamente por ser contraditoria, nao por ser
ruim.

Por isso a classificacao editorial e outra dimensao, com as classes da secao 11:

    BAD  NORMAL  GOOD  VERY_GOOD  ABSURD  FUNNY  CONTRADICTORY  RARE

Ela sai dos dados que a rolagem JA carrega (`score`, `rarity`, `surprise` e o
metodo de avaliacao), nunca de texto escrito a mao, e alimenta duas decisoes:
se entra um REACTION_CLIP e de que categoria ele e.
"""
from __future__ import annotations

BAD = "BAD"
NORMAL = "NORMAL"
GOOD = "GOOD"
VERY_GOOD = "VERY_GOOD"
ABSURD = "ABSURD"
FUNNY = "FUNNY"
CONTRADICTORY = "CONTRADICTORY"
RARE = "RARE"

CLASSES = (BAD, NORMAL, GOOD, VERY_GOOD, ABSURD, FUNNY, CONTRADICTORY, RARE)

# Classe -> pasta da biblioteca de reacoes. As classes que dependem do lado da
# escala (um ABSURD pode ser absurdamente bom OU absurdamente ruim) escolhem
# pelo sentimento; as outras tem pasta propria.
CATEGORIA_POR_CLASSE = {
    ABSURD: {"positive": "insane", "negative": "terrible", "neutral": "insane"},
    VERY_GOOD: {"positive": "great", "negative": "great", "neutral": "great"},
    GOOD: {"positive": "good", "negative": "good", "neutral": "good"},
    NORMAL: {"positive": "neutral", "negative": "neutral", "neutral": "neutral"},
    BAD: {"positive": "bad", "negative": "bad", "neutral": "bad"},
    # Raro tem lado: 5 de forca com surpresa 90 e raro E desastre, e quem
    # assiste reage ao desastre, nao a raridade. A pasta `rare` fica para o
    # improvavel que deu certo.
    RARE: {"positive": "rare", "negative": "terrible", "neutral": "rare"},
    FUNNY: "funny",
    CONTRADICTORY: "contradictory",
}

# Peso editorial: quanto aquela classe MERECE tela. Usado pelo diretor para
# ordenar quem fica com as reacoes quando o orcamento de reacoes acaba.
PESO = {ABSURD: 100, CONTRADICTORY: 85, RARE: 78, FUNNY: 72,
        VERY_GOOD: 60, BAD: 45, GOOD: 25, NORMAL: 0}

PADRAO = {
    "absurd_high": 95,
    "absurd_low": 4,
    "bad_max": 20,
    "normal_max": 59,
    "good_max": 79,
    "rare_probability": 0.07,
    "rare_surprise": 88,
    "contradictory_score": 22,
    "funny": {},
}


def _ajustes(editing_config: dict | None) -> dict:
    cfg = dict(PADRAO)
    cfg.update((editing_config or {}).get("classification", {}))
    return cfg


def _metodo(roll: dict) -> str:
    ev = roll.get("evaluation")
    if isinstance(ev, dict):
        return ev.get("method", "")
    return ev or ""


def _e_contraditorio(roll: dict, cfg: dict) -> bool:
    """Rolagem que BRIGA com o que ja foi sorteado, nao que so foi ruim.

    Hoje o unico eixo contextual do gerador e peso-da-arma contra forca-do-
    personagem (`RollEvaluator.peso_vs_forca`): score no chao ali significa
    literalmente "ele nao levanta a propria arma", que e piada, nao fraqueza.
    Metodo contextual e a marca desse tipo de rolagem, entao a regra pega
    qualquer eixo novo que apareca depois sem precisar ser reescrita.
    """
    return (_metodo(roll) == "contextual"
            and roll.get("score", 50) <= cfg["contradictory_score"])


def _e_raro(roll: dict, cfg: dict) -> bool:
    """Improvavel de sair, independente de ser bom.

    `rarity` e a probabilidade da opcao sorteada (0-1); `surprise` mede o
    quanto o resultado destoa do resto da build. Qualquer um dos dois estourando
    ja e motivo de tela.
    """
    rarity = roll.get("rarity")
    if rarity is not None and rarity <= cfg["rare_probability"]:
        return True
    return roll.get("surprise", 0) >= cfg["rare_surprise"]


def _e_engracado(roll: dict, cfg: dict) -> tuple[bool, str | None]:
    """Faixas declaradas em config como comicas por natureza.

    Formato em editing.json:
        "funny": {"tamanho": {"below": 8, "above": 96, "motivo": "..."}}

    Sem entrada para a roleta, nada e engracado por acidente.
    """
    regra = (cfg.get("funny") or {}).get(roll.get("roulette_id"))
    if not regra:
        return False, None
    score = roll.get("score", 50)
    if "below" in regra and score <= regra["below"]:
        return True, regra.get("motivo_baixo") or regra.get("motivo")
    if "above" in regra and score >= regra["above"]:
        return True, regra.get("motivo_alto") or regra.get("motivo")
    return False, None


def classify(roll: dict, editing_config: dict | None = None) -> dict:
    """{'classification', 'reason', 'weight', 'reaction_category'} de uma rolagem.

    A ordem de precedencia e narrativa, nao numerica: o que da mais assunto
    ganha. Um 97 de dano numa arma que o personagem nao levanta e
    CONTRADICTORY antes de ser ABSURD, porque a piada e a contradicao.
    """
    cfg = _ajustes(editing_config)
    score = roll.get("score", 50)
    sentimento = roll.get("sentiment", "neutral")

    if _e_contraditorio(roll, cfg):
        classe, motivo = CONTRADICTORY, "resultado briga com o que ja foi sorteado"
    elif score >= cfg["absurd_high"] or score <= cfg["absurd_low"]:
        classe, motivo = ABSURD, f"score {score} no extremo da escala"
    elif _e_raro(roll, cfg):
        classe = RARE
        motivo = (f"probabilidade {roll.get('rarity')}"
                  if (roll.get("rarity") is not None
                      and roll["rarity"] <= cfg["rare_probability"])
                  else f"surpresa {roll.get('surprise')}")
    else:
        engracado, motivo_engracado = _e_engracado(roll, cfg)
        if engracado:
            classe, motivo = FUNNY, motivo_engracado or "faixa comica"
        elif score >= cfg["absurd_high"] - 15:
            classe, motivo = VERY_GOOD, f"score {score}"
        elif score <= cfg["bad_max"]:
            classe, motivo = BAD, f"score {score}"
        elif score <= cfg["normal_max"]:
            classe, motivo = NORMAL, f"score {score}"
        elif score <= cfg["good_max"]:
            classe, motivo = GOOD, f"score {score}"
        else:
            classe, motivo = VERY_GOOD, f"score {score}"

    destino = CATEGORIA_POR_CLASSE[classe]
    categoria = destino if isinstance(destino, str) else destino.get(
        sentimento, "neutral")
    return {
        "classification": classe,
        "reason": motivo,
        "weight": PESO[classe],
        "reaction_category": categoria,
    }


def classify_all(rolls: list[dict], editing_config: dict | None = None) -> list[dict]:
    """Uma linha por rolagem, na ordem em que elas acontecem no video."""
    saida = []
    for roll in rolls:
        linha = classify(roll, editing_config)
        linha.update({
            # `index` e o numero da rolagem DENTRO da entidade: character e
            # weapon tem, cada um, um 0. `position` e o lugar no video, e e
            # ele que identifica a rolagem sem ambiguidade.
            "position": len(saida),
            "index": roll.get("index"),
            "entity": roll.get("entity"),
            "roulette_id": roll.get("roulette_id"),
            "category": roll.get("category"),
            "result": roll.get("display_value"),
            "score": roll.get("score"),
            "tier": roll.get("tier"),
        })
        saida.append(linha)
    return saida
