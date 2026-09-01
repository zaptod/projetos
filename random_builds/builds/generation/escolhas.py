"""Atributos ESCOLHIDOS em vez de sorteados.

A premissa do canal e a roleta decidir tudo, entao escolher e excecao: o
padrao continua sendo sortear, e quem escolhe precisa dizer explicitamente o
que fixou. Duas consequencias que este modulo garante:

1. **O sorteio roda igual.** Cada roleta tem seu proprio fork de RNG
   (`sha256(seed:nome)`), e a roleta fixada CONTINUA girando e consumindo o
   rng dela — o valor sorteado so e substituido depois. E a mesma doutrina do
   nome pedido no comentario: a mesma seed produz a mesma build, e o
   `generation.json` guarda o que TERIA saido.
2. **O video nao mente.** Havendo escolha, o gancho troca de pool e para de
   afirmar que tudo foi sorteado (ver `caption_generator.hook`).

O catalogo de atributos NAO e escrito aqui: sai das mesmas roletas que o
sorteio usa (`nf_bridge.roulette_factory`). Classe nova no neural_fights vira
opcao escolhivel sozinha, sem ninguem lembrar de atualizar duas listas.

O usuario digita no formato que VE na tela ("1,80" de altura, "7,4" de
forca), nao no inteiro escalado que o motor guarda (180, 74): a conversao
mora em `_para_interno`, guiada pelo `display_format` da propria roleta.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from ..nf_bridge import roulette_factory

GENERO = "genero"
GENEROS = {"m": "m", "f": "f", "masculino": "m", "feminino": "f",
           "homem": "m", "mulher": "f", "macho": "m", "femea": "f"}

# Quanto o valor de tela vale no inteiro que o motor guarda.
ESCALA = {"meters": 100, "decimal10": 10, "decimal100": 100}


def _sem_acento(texto: str) -> str:
    cru = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in cru if unicodedata.category(c) != "Mn").lower().strip()


def catalogo() -> dict[str, dict]:
    """O que da para escolher, na ordem em que a roleta gira.

    Cada entrada: entidade, rotulo, tipo, e (opcoes | faixa) ja no formato de
    TELA — e isso que a CLI lista e o painel desenha.
    """
    saida: dict[str, dict] = {}
    for config in (roulette_factory.character_roulettes(),
                   roulette_factory.weapon_roulettes()):
        for roleta in config["roulettes"]:
            entrada = {
                "id": roleta["id"],
                "entidade": config["entity"],
                "rotulo": roleta["display_name"],
                "tipo": roleta["type"],
            }
            if roleta["type"] == "categorical":
                entrada["opcoes"] = [o["label"] for o in roleta["options"]]
            else:
                formato = roleta.get("display_format")
                escala = ESCALA.get(formato, 1)
                entrada["minimo"] = roleta["min"] / escala
                entrada["maximo"] = roleta["max"] / escala
                entrada["escala"] = escala
                # A unidade da roleta e a INTERNA ("cm"); quem digita ve a de
                # tela ("1,80 m"). Dizer cm aqui pediria altura em 180.
                entrada["unidade"] = ("m" if formato == "meters"
                                      else roleta.get("unit", ""))
            saida[roleta["id"]] = entrada
    saida[GENERO] = {
        "id": GENERO, "entidade": "character", "rotulo": "GENERO",
        "tipo": "categorical", "opcoes": ["masculino", "feminino"],
        # Nao e roleta de tela: sai do sorteio do NOME (o pool masculino ou
        # feminino) e serve a coerencia do desenho, nao ao espetaculo.
        "fora_da_roleta": True,
    }
    return saida


def _para_interno(entrada: dict, texto: str) -> int:
    """"1,80" -> 180. O usuario digita o que ve, o motor guarda escalado."""
    try:
        numero = float(str(texto).replace(",", "."))
    except ValueError:
        raise ValueError(
            f"{entrada['id']}: '{texto}' nao e numero. "
            f"Esperado entre {entrada['minimo']:g} e {entrada['maximo']:g}"
        ) from None
    if not (entrada["minimo"] <= numero <= entrada["maximo"]):
        raise ValueError(
            f"{entrada['id']}: {numero:g} fora da faixa "
            f"{entrada['minimo']:g}..{entrada['maximo']:g}")
    return round(numero * entrada["escala"])


def _opcao_valida(entrada: dict, texto: str) -> str:
    """Casa o que foi digitado com a opcao real, ignorando acento e caixa."""
    alvo = _sem_acento(texto)
    for opcao in entrada["opcoes"]:
        if _sem_acento(opcao) == alvo:
            return opcao
    # prefixo unico tambem serve: "Cavaleiro" acha "Cavaleiro (Defesa)"
    parciais = [o for o in entrada["opcoes"] if _sem_acento(o).startswith(alvo)]
    if len(parciais) == 1:
        return parciais[0]
    dica = ", ".join(entrada["opcoes"][:12])
    if len(entrada["opcoes"]) > 12:
        dica += f", ... ({len(entrada['opcoes'])} no total)"
    if len(parciais) > 1:
        raise ValueError(f"{entrada['id']}: '{texto}' e ambiguo entre "
                         + ", ".join(parciais))
    raise ValueError(f"{entrada['id']}: '{texto}' nao existe. Opcoes: {dica}")


def interpretar(pares: list[str] | None) -> dict[str, Any]:
    """`["classe=Mago", "tamanho=1,80"]` -> escolhas prontas para o gerador.

    Devolve `{"genero": "m"|None, "roletas": {id: valor_interno},
    "tela": {id: texto_como_aparece}}`. Erra ALTO em atributo desconhecido ou
    valor invalido: uma escolha silenciosamente ignorada viraria um video
    sorteado que o dono acha que escolheu.
    """
    escolhas: dict[str, Any] = {"genero": None, "roletas": {}, "tela": {}}
    disponivel = catalogo()
    for par in pares or []:
        if "=" not in par:
            raise ValueError(
                f"escolha sem valor: '{par}'. Use atributo=valor, "
                "por exemplo classe=Mago")
        chave, _, valor = par.partition("=")
        chave, valor = _sem_acento(chave), valor.strip()
        if chave not in disponivel:
            raise ValueError(f"atributo desconhecido: '{chave}'. "
                             f"Conhecidos: {', '.join(sorted(disponivel))}")
        entrada = disponivel[chave]
        if chave == GENERO:
            genero = GENEROS.get(_sem_acento(valor))
            if genero is None:
                raise ValueError(
                    f"genero: '{valor}' nao serve. Use masculino ou feminino")
            escolhas["genero"] = genero
            escolhas["tela"][chave] = "masculino" if genero == "m" else "feminino"
        elif entrada["tipo"] == "categorical":
            opcao = _opcao_valida(entrada, valor)
            escolhas["roletas"][chave] = opcao
            escolhas["tela"][chave] = opcao
        else:
            escolhas["roletas"][chave] = _para_interno(entrada, valor)
            escolhas["tela"][chave] = valor.replace(".", ",")
    return escolhas


def por_entidade(escolhas: dict | None, entidade: str) -> dict:
    """So as roletas daquela entidade — o gerador de arma nao ve as do personagem."""
    if not escolhas:
        return {}
    disponivel = catalogo()
    return {chave: valor for chave, valor in (escolhas.get("roletas") or {}).items()
            if disponivel[chave]["entidade"] == entidade}


def houve(escolhas: dict | None) -> bool:
    """Alguma coisa foi escolhida? E o que decide se o video pode dizer
    'tudo sorteado'."""
    if not escolhas:
        return False
    return bool(escolhas.get("roletas")) or bool(escolhas.get("genero"))


def descrever() -> list[str]:
    """Linhas legiveis do catalogo, para a CLI (`--atributos`)."""
    linhas = []
    for entrada in catalogo().values():
        etiqueta = f"  {entrada['id']:<18} [{entrada['entidade']}]"
        if entrada["tipo"] == "categorical":
            opcoes = entrada["opcoes"]
            amostra = ", ".join(opcoes[:8])
            if len(opcoes) > 8:
                amostra += f", ... ({len(opcoes)} opcoes)"
            linhas.append(f"{etiqueta} {amostra}")
        else:
            unidade = f" {entrada['unidade']}" if entrada.get("unidade") else ""
            linhas.append(f"{etiqueta} {entrada['minimo']:g} a "
                          f"{entrada['maximo']:g}{unidade}")
    return linhas
