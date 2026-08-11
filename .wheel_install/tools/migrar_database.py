"""Migra referencias legadas do banco sem descartar armas ou personagens.

Por seguranca, o comando apenas mostra o plano. Use ``--apply`` para gravar o
par de JSONs por meio da transacao atomica de :mod:`data.database`.
"""

from __future__ import annotations

import argparse
import copy
from collections.abc import Mapping
from typing import Any

from ai.personalities import PERSONALIDADES_PRESETS
from core.skills import SKILL_DB
from data import database


SKILL_ALIASES = {
    "Avalanche": "Nevasca",
    "Drenar Vida": "Esfera Sombria",
    "Enxame": "Espinhos",
    "Explosão Divina": "Julgamento Celestial",
    "Fúria Bestial": "Grito de Guerra",
    "Garras da Terra": "Raízes",
    "Golpe Devastador": "Avanço Brutal",
    "Lança Celestial": "Raio Sagrado",
    "Onda de Choque": "Repulsão",
    "Perfurar": "Lança de Gelo",
    "Tempestade de Granizo": "Nevasca",
    "Tempestade de Pétalas": "Wrath of Nature",
}

PERSONALIDADE_ALIASES = {
    "Calculista": "Tático",
    "Caçador": "Perseguidor",
    "Dominador": "Predador Alfa",
    "Duelista": "Samurai",
    "Evasivo": "Acrobático",
    "Guardião": "Protetor",
    "Impulsivo": "Agressivo",
    "Oportunista": "Assassino",
    "Paciente": "Contemplativo",
    "Predador": "Predador Alfa",
    "Provocador": "Showman",
    "Sobrevivente": "Defensivo",
    "Vingador": "Berserker",
}

ARMA_ALIASES = {
    "espada comum": "Espada Longa Comum",
}


def _migrar_habilidade(
    habilidade: Any,
    alteracoes: list[str],
    caminho: str,
) -> Any:
    if isinstance(habilidade, str):
        nome = habilidade
        estrutura: dict[str, Any] | None = None
    elif isinstance(habilidade, Mapping):
        estrutura = dict(habilidade)
        nome = estrutura.get("nome")
    else:
        return habilidade

    if nome in SKILL_DB:
        return habilidade
    novo_nome = SKILL_ALIASES.get(nome)
    if not novo_nome:
        return habilidade

    alteracoes.append(f"{caminho}: skill {nome!r} -> {novo_nome!r}")
    if estrutura is None:
        return novo_nome
    estrutura["nome"] = novo_nome
    estrutura["custo"] = SKILL_DB[novo_nome].get("custo", estrutura.get("custo", 0))
    return estrutura


def migrar_documentos(
    armas: list[dict[str, Any]],
    personagens: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Devolve copias migradas e uma trilha textual de todas as alteracoes."""

    armas_novas = copy.deepcopy(armas)
    personagens_novos = copy.deepcopy(personagens)
    alteracoes: list[str] = []

    for indice, arma in enumerate(armas_novas):
        if "habilidade" in arma:
            arma["habilidade"] = _migrar_habilidade(
                arma["habilidade"], alteracoes, f"armas[{indice}].habilidade"
            )
        habilidades = arma.get("habilidades")
        if isinstance(habilidades, list):
            arma["habilidades"] = [
                _migrar_habilidade(
                    habilidade,
                    alteracoes,
                    f"armas[{indice}].habilidades[{habilidade_indice}]",
                )
                for habilidade_indice, habilidade in enumerate(habilidades)
            ]

    for indice, personagem in enumerate(personagens_novos):
        personalidade = personagem.get("personalidade", "Aleatório")
        if personalidade not in PERSONALIDADES_PRESETS:
            nova_personalidade = PERSONALIDADE_ALIASES.get(personalidade)
            if nova_personalidade:
                personagem["personalidade"] = nova_personalidade
                alteracoes.append(
                    f"personagens[{indice}].personalidade: "
                    f"{personalidade!r} -> {nova_personalidade!r}"
                )

        nome_arma = personagem.get("nome_arma")
        nova_arma = ARMA_ALIASES.get(nome_arma)
        if nova_arma:
            personagem["nome_arma"] = nova_arma
            alteracoes.append(
                f"personagens[{indice}].nome_arma: {nome_arma!r} -> {nova_arma!r}"
            )

    database.validar_database(armas_novas, personagens_novos)
    return armas_novas, personagens_novos, alteracoes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="grava o resultado validado")
    args = parser.parse_args(argv)

    try:
        armas = database.carregar_json(database.ARQUIVO_ARMAS)
        personagens = database.carregar_json(database.ARQUIVO_CHARS)
        armas_novas, personagens_novos, alteracoes = migrar_documentos(armas, personagens)
    except (OSError, database.DataValidationError, TypeError, ValueError) as exc:
        print(f"ERRO: {exc}")
        return 1

    if not alteracoes:
        print("Banco ja esta no contrato atual; nenhuma migracao necessaria.")
        return 0

    print(f"Alteracoes validadas: {len(alteracoes)}")
    for alteracao in alteracoes:
        print(f"  - {alteracao}")

    if not args.apply:
        print("Dry-run concluido. Execute novamente com --apply para gravar.")
        return 0

    database.salvar_database(armas_novas, personagens_novos)
    print("Migracao aplicada atomicamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
