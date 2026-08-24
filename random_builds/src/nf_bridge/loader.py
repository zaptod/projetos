"""Ponte com o neural_fights: TODA categoria/caracteristica vem de la.

Nada e inventado aqui — este modulo apenas importa os catalogos canonicos
(classes, personalidades, tipos, estilos, raridades, encantamentos, skills)
e as fabricas oficiais (gerar_arma / gerar_personagem / salvar_database).
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

# random_builds mora ao lado do pacote neural_fights (e:\projetos)
_PROJETOS = Path(__file__).resolve().parents[3]
if str(_PROJETOS) not in sys.path:
    sys.path.insert(0, str(_PROJETOS))

from neural_fights.models.constants import (  # noqa: E402
    LISTA_CLASSES, LISTA_RARIDADES, LISTA_TIPOS_ARMA,
    LISTA_ENCANTAMENTOS, ENCANTAMENTOS,
)
from neural_fights.ai.personalities import PERSONALIDADES_PRESETS  # noqa: E402
from neural_fights.core.skills import SKILL_DB  # noqa: E402
from neural_fights.tools.gerador_database import (  # noqa: E402
    ESTILOS_ARMA, SKILLS_OFENSIVAS, gerar_arma, gerar_personagem,
    salvar_database, selecionar_arma_por_classe,
)
from neural_fights.data import database  # noqa: E402

# Curva de dano base por raridade do gerador oficial (gerar_arma)
DANO_BASE_POR_RARIDADE = {
    "Comum": 9, "Incomum": 12, "Raro": 16, "Épico": 20, "Lendário": 25, "Mítico": 31,
}

LISTA_PERSONALIDADES = list(PERSONALIDADES_PRESETS)


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def elemento_do_encantamento(encantamento: str) -> str:
    """Elemento (chave do grupo de skills) de um encantamento, como o gerador
    oficial resolve: nome do elemento normalizado; sem grupo -> FISICO."""
    elemento = ENCANTAMENTOS.get(encantamento, {}).get("elemento", "FISICO")
    chave = sem_acento(elemento).upper()
    return chave if chave in SKILLS_OFENSIVAS else "FISICO"


def classe_base(classe: str) -> str:
    return classe.split(" (")[0]


def classe_elemento(classe: str) -> str | None:
    """O rotulo entre parenteses da classe ('Piromante (Fogo)' -> 'Fogo')."""
    if "(" in classe and classe.endswith(")"):
        return classe[classe.index("(") + 1:-1]
    return None


def tipos_preferidos_da_classe(classe: str) -> list[str]:
    """Reusa a preferencia oficial classe->tipos de arma."""
    dummy = [{"tipo": t, "nome": t} for t in LISTA_TIPOS_ARMA]
    preferidas = selecionar_arma_por_classe(classe_base(classe), dummy)
    return [a["tipo"] for a in preferidas]


def variantes_do_tipo(tipo: str) -> list[dict]:
    return ESTILOS_ARMA.get(tipo, ESTILOS_ARMA["Reta"])["variantes"]


def skills_ofensivas_do_elemento(elemento: str) -> list[str]:
    return SKILLS_OFENSIVAS.get(elemento, SKILLS_OFENSIVAS["FISICO"])
