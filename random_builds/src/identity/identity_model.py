"""CHARACTER_IDENTITY e WEAPON_IDENTITY: o que os tres videos tem em comum.

Secao 16. O problema que isto resolve: o terceiro video precisa mostrar O MESMO
personagem segurando A MESMA arma dos dois primeiros. Se cada prompt for escrito
de novo a partir de um resumo, o modelo entrega outro rosto, outra roupa e outra
lamina — tres videos de tres builds diferentes.

Entao a identidade e gravada UMA vez, em disco, e os tres prompts sao montados
a partir dela. Nada aqui e inventado: todo campo vem de `prompt.campos()`, que
traduz o que as roletas sortearam.
"""
from __future__ import annotations

from . import config
from .prompt import campos

# Campos permanentes do personagem: tudo que precisa sair igual nos videos
# `character` e `character_weapon`.
CAMPOS_PERSONAGEM = ("NOME", "ARTIGO", "ARTIGO_PERS", "CLASSE", "PERSONALIDADE",
                     "ALTURA", "PORTE", "FISICO", "FORCA", "MANA", "COR", "COR_HEX")

# Campos permanentes da arma: iguais em `weapon` e `character_weapon`.
CAMPOS_ARMA = ("ARMA", "ARMA_TIPO", "ARMA_ESTILO", "RARIDADE", "HABILIDADE",
               "ELEMENTO", "AURA")


def identidades(generation: dict, ajustes: dict | None = None) -> tuple[dict, dict]:
    """(CHARACTER_IDENTITY, WEAPON_IDENTITY) da geracao."""
    ajustes = ajustes if ajustes is not None else config.settings()
    valores = campos(generation, ajustes)
    personagem = {chave: valores[chave] for chave in CAMPOS_PERSONAGEM}
    arma = {chave: valores[chave] for chave in CAMPOS_ARMA}
    return personagem, arma


def gravar(generation: dict, ajustes: dict | None = None) -> tuple[dict, dict]:
    """Grava as duas identidades em outputs/<gid>/identity/ e devolve as duas.

    Gravar em disco nao e conveniencia: e o que permite re-gerar o terceiro
    video meses depois, ou so ele, sem depender de nada que so existia em
    memoria na hora do sorteio.
    """
    import json

    personagem, arma = identidades(generation, ajustes)
    destino = config.identity_dir(generation["generation_id"])
    destino.mkdir(parents=True, exist_ok=True)
    for nome, dados in (("character_identity.json", personagem),
                        ("weapon_identity.json", arma)):
        with open(destino / nome, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
    return personagem, arma
