"""generation.json -> o texto dos prompts de video (um por slot).

Sao TRES prompts por geracao (secoes 4, 6 e 7): o personagem sozinho, a arma
sozinha e os dois juntos. Os tres saem dos MESMOS campos traduzidos, e e isso
que mantem o personagem do terceiro video igual ao do primeiro (secao 16) —
nenhum deles e escrito a partir de um resumo do outro.

Nenhuma categoria e inventada aqui: classe, personalidade, tipo de arma,
raridade e elemento vem dos catalogos canonicos do neural_fights, e a traducao
para ingles vive em config/identity.json (editavel sem tocar em codigo). O
elemento sai de `elemento_do_encantamento` do nf_bridge, que e o mesmo
resolvedor que o gerador oficial usa — `afinidade_elemento` guarda o nome do
ENCANTAMENTO ('Chamas'), nao o elemento ('FOGO').
"""
from __future__ import annotations

import colorsys
import re

from ..nf_bridge.loader import elemento_do_encantamento
from . import config
from .slots import (CHARACTER, CHARACTER_WEAPON, IMAGEM, SLOTS,
                    WEAPON, midia, valido)

PLACEHOLDER = re.compile(r"\{[A-Z_]+\}")

# Contrato canonico do personagem (neural_fights/tools/gerador_database.py:487).
# Geracoes antigas (generation_00002/00003) usam um esquema anterior e nao tem
# esses campos — melhor dizer isso do que estourar um KeyError cru.
CAMPOS_PERSONAGEM = ("nome", "classe", "personalidade", "tamanho", "forca",
                     "mana", "cor_r", "cor_g", "cor_b")


class GeracaoIncompativel(ValueError):
    pass


def _validar(personagem: dict, generation: dict) -> None:
    faltando = [c for c in CAMPOS_PERSONAGEM if c not in personagem]
    if faltando:
        raise GeracaoIncompativel(
            f"{generation.get('generation_id', 'a geracao')} nao tem "
            f"{', '.join(faltando)} no personagem. Isso e esquema antigo, "
            "anterior ao contrato canonico do neural_fights; gere uma build "
            "nova com `python main.py generate-video`.")


def _faixa(tabela: list, valor: float, padrao: str) -> str:
    """Primeira faixa [limite, rotulo] cujo limite alcanca o valor."""
    for limite, rotulo in tabela:
        if valor <= float(limite):
            return rotulo
    return padrao


def nome_da_cor(r: int, g: int, b: int, tabela: list) -> str:
    """RGB -> nome de cor. Satura e brilho decidem antes do matiz.

    Sem isso um cinza (matiz instavel) vira 'crimson red' so porque o ruido do
    canal vermelho ganhou por 1.
    """
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if l <= 0.12:
        return "near-black"
    if l >= 0.92:
        return "bright white"
    if s <= 0.15:
        return "steel gray"
    return _faixa(tabela, h * 360, "crimson red")


def artigo(palavra: str) -> str:
    """'a' ou 'an'. Aproximacao por letra: os rotulos daqui sao todos ASCII e
    nenhum e do tipo 'an hour' / 'a unicorn'."""
    return "an" if palavra[:1].lower() in "aeiou" else "a"


def elemento_da_arma(arma: dict) -> str:
    encantamento = arma.get("afinidade_elemento")
    if not encantamento:
        encantamentos = arma.get("encantamentos") or []
        encantamento = encantamentos[0] if encantamentos else None
    if not encantamento:
        return "FISICO"
    return elemento_do_encantamento(encantamento)


def campos(generation: dict, ajustes: dict | None = None) -> dict:
    """Todo dado sorteado, ja traduzido, pronto para o template."""
    ajustes = ajustes if ajustes is not None else config.settings()
    traducoes = ajustes["traducoes"]
    personagem = generation["character"]
    arma = generation["weapon"]
    build = generation.get("build") or {}

    _validar(personagem, generation)
    elemento = elemento_da_arma(arma)
    r, g, b = personagem["cor_r"], personagem["cor_g"], personagem["cor_b"]

    def traduz(grupo: str, chave, padrao=None):
        return traducoes.get(grupo, {}).get(chave, padrao if padrao is not None else chave)

    porte = _faixa(ajustes["porte"], personagem["tamanho"], "average-height")
    personalidade = traduz("personalidade", personagem["personalidade"])
    raridade = traduz("raridade", arma.get("raridade"))

    return {
        "NOME": personagem["nome"],
        "ARTIGO": artigo(porte),
        "ARTIGO_PERS": artigo(personalidade),
        "CLASSE": traduz("classe", personagem["classe"]),
        "PERSONALIDADE": personalidade,
        "ALTURA": f"{personagem['tamanho']:.2f}",
        "PORTE": porte,
        "FORCA": f"{personagem['forca']:.1f}",
        "MANA": f"{personagem['mana']:.1f}",
        "FISICO": _faixa(ajustes["fisico"], personagem["forca"], "athletic"),
        "COR": nome_da_cor(r, g, b, ajustes["cores"]),
        "COR_HEX": "#%02x%02x%02x" % (r, g, b),
        "ARMA": arma["nome"],
        "ARMA_TIPO": traduz("tipo_arma", arma.get("tipo")),
        "ARMA_ESTILO": traduz("estilo", arma.get("estilo"),
                               traduz("tipo_arma", arma.get("tipo"), "")),
        "RARIDADE": raridade,
        # Artigo da RARIDADE, nao o do porte: "an epic-grade", "a mythic-grade".
        "ARTIGO_RARIDADE": artigo(raridade),
        "HABILIDADE": arma.get("habilidade") or "",
        "ELEMENTO": traduz("elemento", elemento, "raw steel"),
        "AURA": ajustes["aura"].get(elemento, ajustes["aura"]["DEFAULT"]),
        "VEREDITO": build.get("verdict_label", ""),
        "SCORE": str(build.get("final_score", "")),
    }


def template(ajustes: dict, slot: str, tipo: str = "video") -> str:
    """Template daquele slot e daquela MIDIA.

    Prompt de imagem nao e o de video sem movimento: sai a camera e entra
    composicao. Por isso sao bancos separados (`prompts_imagem` x `prompts`),
    e nao um texto so com adaptacao no meio.
    """
    valido(slot)
    if tipo == IMAGEM:
        modelo = (ajustes.get("prompts_imagem") or {}).get(slot)
        if modelo:
            return modelo
        # Sem banco de imagem, o de video ainda descreve o mesmo personagem:
        # pior enquadramento, nunca personagem errado.
    modelos = ajustes.get("prompts") or {}
    modelo = modelos.get(slot)
    if modelo:
        return modelo
    legado = ajustes.get("prompt_template")
    if legado:
        return legado
    raise KeyError(
        f"config/identity.json nao tem prompts[{slot!r}] nem prompt_template. "
        f"Slots esperados: {', '.join(SLOTS)}.")


def limite_de_chars(ajustes: dict, slot: str, tipo: str = "video") -> int:
    """Teto de caracteres do slot, por midia.

    `prompt_max_chars` aceita numero (mesmo teto para todos) ou objeto por
    slot — o prompt de personagem+arma carrega as duas identidades inteiras e
    e naturalmente o maior dos tres. Imagem tem teto proprio e menor: modelo
    de imagem dispersa quando a lista de exigencias fica longa.
    """
    limite = ajustes.get("prompt_max_chars", 1400)
    if not isinstance(limite, dict):
        return int(limite)
    if tipo == IMAGEM and isinstance(limite.get(IMAGEM), dict):
        por_imagem = limite[IMAGEM]
        return int(por_imagem.get(slot, por_imagem.get("default", 950)))
    return int(limite.get(slot, limite.get("default", 1400)))


def build_prompt(generation: dict, ajustes: dict | None = None,
                 slot: str = CHARACTER_WEAPON, tipo: str | None = None) -> str:
    """O prompt daquele slot. `tipo` omitido = o que o slot pede hoje."""
    ajustes = ajustes if ajustes is not None else config.settings()
    valores = campos(generation, ajustes)
    tipo = tipo or midia(slot)

    texto = template(ajustes, slot, tipo)
    for chave, valor in valores.items():
        texto = texto.replace("{" + chave + "}", str(valor))

    sobrando = PLACEHOLDER.findall(texto)
    if sobrando:
        raise KeyError(
            f"o prompt de '{slot}' usa placeholders que ninguem preenche: "
            f"{sorted(set(sobrando))}. Disponiveis: {sorted(valores)}")

    texto = " ".join(texto.split())
    limite = limite_de_chars(ajustes, slot, tipo)
    if len(texto) > limite:
        # corta em fronteira de frase para nao entregar um prompt truncado no meio
        corte = texto.rfind(".", 0, limite)
        texto = texto[:corte + 1] if corte > limite // 2 else texto[:limite]
    return texto


def para_payoff(generation: dict, ajustes: dict | None = None,
                com_referencia=()) -> str:
    """O prompt do payoff para as referencias que DERAM CERTO de anexar.

    Escolhido no envio, e nao no enfileiramento, porque so ali se sabe quantas
    imagens existem e se o anexo funcionou. A regra que nao pode ser quebrada:
    o texto carrega em palavras o lado que a imagem nao carregou em pixels —
    a variante parcial nunca encurta o lado sem imagem, e a variante de zero
    referencia e o texto completo de sempre.
    """
    ajustes = ajustes if ajustes is not None else config.settings()
    presentes = {s for s in com_referencia if s}
    variantes = ajustes.get("prompts_payoff") or {}
    tem_personagem = CHARACTER in presentes
    tem_arma = WEAPON in presentes

    if tem_personagem and tem_arma:
        chave = "ambas"
    elif tem_personagem:
        chave = "so_personagem"
    elif tem_arma:
        chave = "so_arma"
    else:
        # Sem imagem nenhuma: o texto de sempre, inteiro.
        return build_prompt(generation, ajustes, CHARACTER_WEAPON, tipo="video")

    modelo = variantes.get(chave)
    if not modelo:
        return build_prompt(generation, ajustes, CHARACTER_WEAPON, tipo="video")

    valores = campos(generation, ajustes)
    texto = modelo
    for chave_campo, valor in valores.items():
        texto = texto.replace("{" + chave_campo + "}", str(valor))
    sobrando = PLACEHOLDER.findall(texto)
    if sobrando:
        raise KeyError(
            f"a variante de payoff {chave!r} usa placeholders que ninguem "
            f"preenche: {sorted(set(sobrando))}. Disponiveis: {sorted(valores)}")
    return " ".join(texto.split())


def build_prompts(generation: dict, ajustes: dict | None = None) -> dict:
    """{slot: prompt} de TODO job da geracao, inclusive o de juncao."""
    from .slots import JOBS
    ajustes = ajustes if ajustes is not None else config.settings()
    return {slot: build_prompt(generation, ajustes, slot) for slot in JOBS}
