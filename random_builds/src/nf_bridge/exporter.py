"""Exporter: converte o resultado das roletas em registros CANONICOS do
neural_fights (via gerar_arma/gerar_personagem oficiais) e insere no banco.

As fabricas oficiais cuidam de nome, cor, geometria por estilo e passiva;
os campos que as roletas decidiram (dano, peso, critico, velocidade, tamanho,
forca, mana) sao aplicados por cima. A insercao usa salvar_database
(substituir=False), o mesmo caminho validado da UI do jogo.
"""
from __future__ import annotations

import random

from . import loader as nf


def build_records(char_entity: dict, weapon_entity: dict,
                  rng: random.Random) -> tuple[dict, dict]:
    estado = random.getstate()
    random.seed(rng.randrange(2**31))
    try:
        arma = nf.gerar_arma(
            weapon_entity["tipo"],
            weapon_entity["raridade"],
            variante_idx=weapon_entity["estilo_meta"]["variante_idx"],
            encantamento=weapon_entity["encantamento"],
            skill=weapon_entity["habilidade"],
        )
        arma["dano"] = round(float(weapon_entity["dano"]), 1)
        arma["peso"] = round(weapon_entity["peso_x10"] / 10, 1)
        arma["critico"] = round(weapon_entity["critico_x10"] / 10, 1)
        arma["velocidade_ataque"] = round(weapon_entity["velocidade_x100"] / 100, 2)

        personagem = nf.gerar_personagem(
            char_entity["classe"],
            char_entity["personalidade"],
            arma["nome"],
        )
        personagem["tamanho"] = round(char_entity["tamanho_cm"] / 100, 2)
        personagem["forca"] = round(char_entity["forca_x10"] / 10, 1)
        personagem["mana"] = round(char_entity["mana_x10"] / 10, 1)
    finally:
        random.setstate(estado)
    return arma, personagem


def _nome_unico(base: str, usados: set[str]) -> str:
    nome, sufixo = base, 2
    while nome in usados:
        nome = f"{base} #{sufixo}"
        sufixo += 1
    return nome


def insert_into_database(arma: dict, personagem: dict) -> dict:
    """Anexa arma+personagem ao banco vivo do neural_fights."""
    armas_existentes, personagens_existentes = nf.database.carregar_database()
    nomes_armas = {a["nome"] for a in armas_existentes}
    nomes_pers = {p["nome"] for p in personagens_existentes}

    arma = dict(arma)
    personagem = dict(personagem)
    arma["nome"] = _nome_unico(arma["nome"], nomes_armas)
    personagem["nome"] = _nome_unico(personagem["nome"], nomes_pers)
    personagem["nome_arma"] = arma["nome"]

    nf.salvar_database([arma], [personagem], substituir=False)
    caminho_armas, caminho_pers = nf.database.resolver_database_paths(para_escrita=False)
    return {
        "arma": arma["nome"],
        "personagem": personagem["nome"],
        "arquivo_armas": str(caminho_armas),
        "arquivo_personagens": str(caminho_pers),
    }
