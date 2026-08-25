"""Exporter: converte o resultado das roletas em registros CANONICOS do
neural_fights (via gerar_arma/gerar_personagem oficiais) e insere no banco.

As fabricas oficiais cuidam de cor, geometria por estilo e passiva; os campos
que as roletas decidiram (dano, peso, critico, velocidade, tamanho, forca,
mana) sao aplicados por cima. A insercao usa salvar_database
(substituir=False), o mesmo caminho validado da UI do jogo.

O NOME nao vem mais das fabricas: elas colam adjetivo no fim ("Katana Comum",
"Lucius a Sombria") e nao sabem do nome pedido no comentario. O nome oficial e
gerado, depois sobrescrito pela camada src.character.nomes -- o jogo continua
recebendo um registro identico em estrutura, so com outro texto na chave.
"""
from __future__ import annotations

import random

from . import loader as nf
from ..character import nomes


def _variante_do_tipo(weapon_entity: dict) -> int:
    """Indice da variante DENTRO do tipo sorteado, nao do primeiro que a ofereceu.

    estilo_options() junta dois tipos que oferecem o mesmo nome de estilo numa
    opcao so (senao a roda destaca o segmento errado), e o `variante_idx` dessa
    opcao e o do PRIMEIRO tipo. Se o sorteio caiu no segundo, gerar_arma
    receberia o indice do outro catalogo e gravaria outro estilo. O mapa por
    tipo existe justamente para isso.
    """
    meta = weapon_entity.get("estilo_meta") or {}
    por_tipo = meta.get("variante_idx_por_tipo") or {}
    idx = por_tipo.get(weapon_entity["tipo"])
    return meta.get("variante_idx", 0) if idx is None else idx


def build_records(char_entity: dict, weapon_entity: dict,
                  rng: random.Random,
                  nome_pedido: str | None = None) -> tuple[dict, dict, dict]:
    """Devolve (arma, personagem, naming).

    naming carrega a procedencia do nome do personagem para o generation.json:
    quem viu o video precisa saber que aquele nome veio de um comentario.
    """
    estado = random.getstate()
    random.seed(rng.randrange(2**31))
    try:
        arma = nf.gerar_arma(
            weapon_entity["tipo"],
            weapon_entity["raridade"],
            variante_idx=_variante_do_tipo(weapon_entity),
            encantamento=weapon_entity["encantamento"],
            skill=weapon_entity["habilidade"],
        )
        # gerar_arma cai em ESTILOS_ARMA["Reta"] quando o tipo nao tem
        # catalogo proprio (gerador_database.py:330), entao um tipo novo no
        # banco sairia da roleta como "Escudo" e chegaria ao registro, ao
        # prompt e a placa como "Espada Longa". O estilo e o que a roleta
        # mostrou; a geometria continua sendo a que a fabrica soube montar.
        estilo_rolado = weapon_entity.get("estilo")
        if estilo_rolado:
            arma["estilo"] = estilo_rolado

        arma["dano"] = round(float(weapon_entity["dano"]), 1)
        arma["peso"] = round(weapon_entity["peso_x10"] / 10, 1)
        arma["critico"] = round(weapon_entity["critico_x10"] / 10, 1)
        arma["velocidade_ataque"] = round(weapon_entity["velocidade_x100"] / 100, 2)

        elemento = nf.elemento_do_encantamento(weapon_entity["encantamento"])
        nome_oficial_arma = arma["nome"]
        arma["nome"] = nomes.gerar_nome_arma(
            rng,
            tipo=weapon_entity["tipo"],
            encantamento=weapon_entity["encantamento"],
            elemento=elemento,
            raridade=weapon_entity["raridade"],
        )

        # gerar_personagem grava nome_arma; chamar DEPOIS de renomear a arma
        # mantem o vinculo apontando para o nome que o video mostra.
        personagem = nf.gerar_personagem(
            char_entity["classe"],
            char_entity["personalidade"],
            arma["nome"],
        )
        procedencia = nomes.resolver_nome_personagem(
            rng,
            classe=char_entity["classe"],
            personalidade=char_entity["personalidade"],
            encantamento=weapon_entity["encantamento"],
            elemento=elemento,
            raridade=weapon_entity["raridade"],
            nome_pedido=nome_pedido,
        )
        nome_oficial_personagem = personagem["nome"]
        personagem["nome"] = procedencia["name"]
        # O genero sai do sorteio do NOME (o pool masculino/feminino) e precisa
        # chegar ao prompt: sem ele o modelo de imagem inventa, e uma "Lyra"
        # saia cavaleiro barbudo. Nao e roleta na tela, e coerencia do desenho.
        personagem["genero"] = procedencia["gender"]

        personagem["tamanho"] = round(char_entity["tamanho_cm"] / 100, 2)
        personagem["forca"] = round(char_entity["forca_x10"] / 10, 1)
        personagem["mana"] = round(char_entity["mana_x10"] / 10, 1)
    finally:
        random.setstate(estado)

    naming = {
        "character_name": personagem["nome"],
        "character_name_origin": procedencia["origin"],
        "character_gender": procedencia["gender"],
        "generated_character_name": procedencia["generated_name"],
        "requested_name": procedencia["requested_name"],
        "requested_name_accepted": procedencia["requested_accepted"],
        "requested_name_reason": procedencia["requested_reason"],
        "weapon_name": arma["nome"],
        "weapon_name_origin": "generated",
        # o que as fabricas do jogo teriam batizado, para quem quiser comparar
        "legacy_character_name": nome_oficial_personagem,
        "legacy_weapon_name": nome_oficial_arma,
    }
    return arma, personagem, naming


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
