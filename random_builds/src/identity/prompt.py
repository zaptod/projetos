"""generation.json -> o texto dos prompts de video (um por slot).

Sao TRES prompts por geracao (secoes 4, 6 e 7): o personagem sozinho, a arma
sozinha e os dois juntos. Os tres saem dos MESMOS campos traduzidos, e e isso
que mantem o personagem do terceiro video igual ao do primeiro (secao 16) -
nenhum deles e escrito a partir de um resumo do outro.

Nenhuma categoria e inventada aqui: classe, personalidade, tipo de arma,
raridade e elemento vem dos catalogos canonicos do neural_fights, e a traducao
para ingles vive em config/identity.json (editavel sem tocar em codigo). O
elemento sai de `elemento_do_encantamento` do nf_bridge, que e o mesmo
resolvedor que o gerador oficial usa - `afinidade_elemento` guarda o nome do
ENCANTAMENTO ('Chamas'), nao o elemento ('FOGO').

TODA roleta chega ao texto. Numero de roleta nunca vai cru: dano, peso,
critico, velocidade e mana viram FAIXA (tabela [limite, rotulo] no config),
porque "22 de dano" nao e desenhavel e "a heavy, punishing edge that cracks
stone" e. O que o modelo nao consegue ver num still (velocidade de ataque e a
habilidade disparando) so entra nos prompts de VIDEO e nos de payoff.

A variacao entre builds mora numa MOLDURA (cenario, luz, clima, angulo)
sorteada de forma deterministica a partir do seed da geracao - nunca de
`random`, senao cada slot da mesma build cairia numa arena diferente e o
payoff mostraria outro lugar. Identidade (rosto, cabelo, cor, armadura, arma)
fica FORA da moldura: os templates colam os blocos de identidade literais de
`blocos_identidade`, sem reescrever a frase por slot. Foi reescrever a frase
que produziu o cabelo branco no clipe e preto no payoff do generation_00020.
"""
from __future__ import annotations

import colorsys
import re
import zlib

from ..nf_bridge.loader import elemento_do_encantamento
from . import config
from .slots import (CHARACTER, CHARACTER_WEAPON, IMAGEM, SLOTS,
                    WEAPON, midia, valido)

PLACEHOLDER = re.compile(r"\{[A-Z_]+\}")

# Contrato canonico do personagem (neural_fights/tools/gerador_database.py:487).
# Geracoes antigas (generation_00002/00003) usam um esquema anterior e nao tem
# esses campos - melhor dizer isso do que estourar um KeyError cru.
CAMPOS_PERSONAGEM = ("nome", "classe", "personalidade", "tamanho", "forca",
                     "mana", "cor_r", "cor_g", "cor_b")

# O que a arma tem que trazer para o prompt descrever a arma inteira. Sao os
# alvos das roletas numericas de arma; sem eles o texto sairia dizendo "0.0 kg"
# e "0 damage" para um modelo pago, que e pior do que nao sair.
CAMPOS_ARMA = ("dano", "peso", "critico", "velocidade_ataque")

# Degrade de catalogo novo: item sem traducao/VFX cadastrado ainda gera prompt,
# so que generico. Quem cobra o cadastro e o relatorio de cobertura, nao o
# render - travar aqui pararia a fila por causa de uma linha de JSON.
SEM_ENCANTAMENTO = "No"
SEM_HABILIDADE = "a plain killing strike"


class GeracaoIncompativel(ValueError):
    pass


def _validar(personagem: dict, generation: dict, arma: dict) -> None:
    gid = generation.get("generation_id", "a geracao")
    faltando = [c for c in CAMPOS_PERSONAGEM if c not in personagem]
    if faltando:
        raise GeracaoIncompativel(
            f"{gid} nao tem "
            f"{', '.join(faltando)} no personagem. Isso e esquema antigo, "
            "anterior ao contrato canonico do neural_fights; gere uma build "
            "nova com `python main.py generate-video`.")
    faltando = [c for c in CAMPOS_ARMA if c not in arma]
    if faltando:
        raise GeracaoIncompativel(
            f"{gid} nao tem {', '.join(faltando)} na arma. Isso e esquema "
            "antigo, anterior ao contrato canonico do neural_fights; gere uma "
            "build nova com `python main.py generate-video`.")


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


def encantamento_da_arma(arma: dict) -> str:
    """O encantamento GRAVADO na arma, em portugues, como o banco escreve.

    `afinidade_elemento` guarda o nome do encantamento ('Velocidade'), nao o
    elemento. Vale a pena ter os dois: quatro encantamentos diferentes
    (Velocidade, Critico, Penetracao, Execucao) colapsam no MESMO elemento
    FISICO, e sem o nome do encantamento essas quatro armas sairiam iguais.
    """
    encantamento = arma.get("afinidade_elemento")
    if not encantamento:
        encantamentos = arma.get("encantamentos") or []
        encantamento = encantamentos[0] if encantamentos else None
    return encantamento or ""


def elemento_da_arma(arma: dict) -> str:
    encantamento = encantamento_da_arma(arma)
    if not encantamento:
        return "FISICO"
    return elemento_do_encantamento(encantamento)


def moldura(generation: dict, ajustes: dict | None = None) -> dict:
    """{CENARIO, LUZ, CLIMA, ANGULO} daquela build. Deterministico pelo seed.

    Por que nao `random.choice`: sortear na hora daria uma moldura DIFERENTE
    por slot, e o payoff mostraria uma arena que os dois clipes anteriores nao
    mostraram. Por que nao hash do nome: builds de nome parecido cairiam na
    mesma moldura. O seed e o unico numero que ja identifica a build inteira e
    e o mesmo em toda chamada.

    Os eixos saem do config na ORDEM em que estao escritos, em radix misto:
    eixo novo em `moldura` vira placeholder novo sozinho, sem tocar em codigo.
    Eixo sem opcoes nao entra - ai o placeholder sobra e `build_prompt` grita,
    que e melhor do que mandar 'Setting: ;' para o modelo.
    """
    ajustes = ajustes if ajustes is not None else config.settings()
    tabelas = ajustes.get("moldura") or {}
    resto = semente(generation)
    escolhido = {}
    for eixo, opcoes in tabelas.items():
        if eixo.startswith("_") or not opcoes:
            continue
        escolhido[eixo.upper()] = opcoes[resto % len(opcoes)]
        resto //= len(opcoes)
    return escolhido


def semente(generation: dict) -> int:
    """O seed da geracao como inteiro nao negativo.

    Geracao sem seed (formato antigo) cai no CRC do generation_id: estavel
    entre processos, ao contrario de `hash()`, que muda a cada execucao e
    trocaria a arena do payoff no meio da build.
    """
    bruto = generation.get("seed")
    if bruto is None:
        gid = str(generation.get("generation_id") or "")
        return zlib.crc32(gid.encode("utf-8"))
    try:
        return abs(int(bruto))
    except (TypeError, ValueError):
        return zlib.crc32(str(bruto).encode("utf-8"))


def campos(generation: dict, ajustes: dict | None = None) -> dict:
    """Todo dado sorteado, ja traduzido, pronto para o template."""
    ajustes = ajustes if ajustes is not None else config.settings()
    traducoes = ajustes["traducoes"]
    personagem = generation["character"]
    arma = generation["weapon"]
    build = generation.get("build") or {}

    _validar(personagem, generation, arma)
    elemento = elemento_da_arma(arma)
    encantamento = encantamento_da_arma(arma)
    habilidade = arma.get("habilidade") or ""
    r, g, b = personagem["cor_r"], personagem["cor_g"], personagem["cor_b"]

    def traduz(grupo: str, chave, padrao=None):
        return traducoes.get(grupo, {}).get(chave, padrao if padrao is not None else chave)

    def vfx(grupo: str, chave: str, padrao: str) -> str:
        tabela = ajustes.get(grupo) or {}
        return tabela.get(chave) or tabela.get("DEFAULT") or padrao

    porte = _faixa(ajustes["porte"], personagem["tamanho"], "average-height")
    personalidade = traduz("personalidade", personagem["personalidade"])
    raridade = traduz("raridade", arma.get("raridade"))
    dano = float(arma["dano"])
    peso = float(arma["peso"])
    critico = float(arma["critico"])
    velocidade = float(arma["velocidade_ataque"])

    return {
        "NOME": personagem["nome"],
        # Geracao antiga nao tem o campo; "" faz o prompt so nao dizer o genero,
        # em vez de estourar num build que ja existe no disco.
        "GENERO": traduz("genero", personagem.get("genero"), ""),
        "ARTIGO": artigo(porte),
        "ARTIGO_PERS": artigo(personalidade),
        "CLASSE": traduz("classe", personagem["classe"]),
        "PERSONALIDADE": personalidade,
        "ALTURA": f"{personagem['tamanho']:.2f}",
        "PORTE": porte,
        "FORCA": f"{personagem['forca']:.1f}",
        "MANA": f"{personagem['mana']:.1f}",
        "FISICO": _faixa(ajustes["fisico"], personagem["forca"], "athletic"),
        "MANA_DESC": _faixa(ajustes.get("mana") or [], personagem["mana"],
                            "a steady arcane charge at the fingertips"),
        "COR": nome_da_cor(r, g, b, ajustes["cores"]),
        "COR_HEX": "#%02x%02x%02x" % (r, g, b),
        "ARMA": arma["nome"],
        "ARMA_TIPO": traduz("tipo_arma", arma.get("tipo")),
        # A forma fisica do tipo. Sem ela as tabelas numericas descreviam toda
        # arma como lamina com cabo, e uma sentinela orbital saiu adaga. Tipo
        # novo sem silhueta cadastrada degrada para um generico que nao
        # contradiz nada - e a cobertura acusa o que falta.
        "SILHUETA": traduz("silhueta", arma.get("tipo"),
                           "its full form clearly visible"),
        "ARMA_ESTILO": traduz("estilo", arma.get("estilo"),
                               traduz("tipo_arma", arma.get("tipo"), "")),
        "RARIDADE": raridade,
        # Artigo da RARIDADE, nao o do porte: "an epic-grade", "a mythic-grade".
        "ARTIGO_RARIDADE": artigo(raridade),
        # Numero de roleta vira desenho: a faixa e o que o modelo sabe pintar.
        "DANO": f"{dano:.0f}",
        "DANO_DESC": _faixa(ajustes.get("dano") or [], dano,
                            "a solid, dependable cutting edge"),
        "PESO": f"{peso:.1f}",
        "PESO_DESC": _faixa(ajustes.get("peso") or [], peso,
                            "solid and hefty, a firm two-hand grip"),
        "CRITICO_DESC": _faixa(ajustes.get("critico") or [], critico,
                               "a clean honed edge"),
        "VELOCIDADE": f"{velocidade:.2f}",
        "VELOCIDADE_DESC": _faixa(ajustes.get("velocidade") or [], velocidade,
                                  "steady and measured in the swing"),
        # Nome PT do banco (nameplate) e o desenho dele, separados: e o
        # ENCANTAMENTO que distingue as quatro armas que caem em FISICO.
        "HABILIDADE": habilidade,
        # Skill nova sem traducao sai com o nome PT no meio do ingles: feio,
        # mas especifico. Trocar por um rotulo generico apagaria a unica pista
        # de que ela existe - e o relatorio de cobertura ja cobra o cadastro.
        "HABILIDADE_EN": traduz("habilidade", habilidade) or SEM_HABILIDADE,
        "HABILIDADE_VFX": vfx("habilidade_vfx", habilidade,
                              "a decisive strike, the air torn open behind it"),
        "ENCANTAMENTO": traduz("encantamento", encantamento) or SEM_ENCANTAMENTO,
        "ENCANTAMENTO_VFX": vfx("encantamento_vfx", encantamento,
                                "clean unadorned metal, no enchant burning on it"),
        "ELEMENTO": traduz("elemento", elemento, "raw steel"),
        "AURA": ajustes["aura"].get(elemento, ajustes["aura"]["DEFAULT"]),
        "VEREDITO": build.get("verdict_label", ""),
        "SCORE": str(build.get("final_score", "")),
        **moldura(generation, ajustes),
    }


def midia_do_template(ajustes: dict, slot: str, tipo: str) -> str:
    """A midia do template que `template()` vai REALMENTE devolver.

    Existe porque as duas decisoes se separaram: `template()` cai no banco de
    video quando o slot nao tem texto de imagem, mas `limite_de_chars()`
    continuava aplicando o teto de imagem. O texto de video e maior por
    natureza, entao o corte comia o enquadramento e o negative prompt inteiro
    ("no watermark") - exatamente o que _cortar existe para nao comer.
    """
    if tipo != IMAGEM:
        return tipo
    if (ajustes.get("prompts_imagem") or {}).get(slot):
        return IMAGEM
    return "video"


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
    slot - o prompt de personagem+arma carrega as duas identidades inteiras e
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


def _cortar(texto: str, limite: int) -> str:
    """Corta em fronteira de FRASE, nunca no meio de uma.

    O que mora no fim do texto e o negative prompt ('No text, no watermark...'),
    entao estourar o limite nao e cosmetico: come justamente a parte que impede
    marca d'agua e legenda. Este corte e a ultima linha de defesa; o teto do
    config e que tem que ser grande o bastante para ele nunca disparar.
    """
    if len(texto) <= limite:
        return texto
    # rfind(".") sozinho nao distingue ponto final de ponto DECIMAL, e o texto
    # e cheio de "1.86 m tall" e "0.8 kg": o corte caia no meio do numero e
    # ainda passava por qualquer teste que so olhasse endswith("."). Fronteira
    # de frase de verdade e ponto seguido de espaco (ou fim do texto).
    corte = -1
    procura = texto.rfind(".", 0, limite)
    while procura > 0:
        depois = procura + 1
        if depois >= len(texto) or texto[depois].isspace():
            corte = procura
            break
        procura = texto.rfind(".", 0, procura)
    if corte > limite // 2:
        return texto[:corte + 1]
    # Sem fronteira de frase util, ainda assim nao se corta no meio de uma
    # PALAVRA: uma fatia crua pode parar logo depois do ponto de "1.86" e o
    # texto sai afirmando "1." para o modelo.
    espaco = texto.rfind(" ", 0, limite + 1)
    return texto[:espaco].rstrip() if espaco > limite // 2 else texto[:limite]


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

    # O teto acompanha o template que saiu, nao o que foi pedido.
    return _cortar(" ".join(texto.split()),
                   limite_de_chars(ajustes, slot,
                                   midia_do_template(ajustes, slot, tipo)))


def para_payoff(generation: dict, ajustes: dict | None = None,
                com_referencia=()) -> str:
    """O prompt do payoff para as referencias que DERAM CERTO de anexar.

    Escolhido no envio, e nao no enfileiramento, porque so ali se sabe quantas
    imagens existem e se o anexo funcionou. A regra que nao pode ser quebrada:
    o texto carrega em palavras o lado que a imagem nao carregou em pixels -
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
    # O payoff tambem tem teto. Antes nao tinha: crescer o catalogo aumentava
    # o texto sem ninguem notar, e o Digen simplesmente ignora o excesso.
    teto = (ajustes.get("prompt_max_chars") or {})
    teto = teto.get("payoff", 1600) if isinstance(teto, dict) else int(teto)
    return _cortar(" ".join(texto.split()), int(teto))


def build_prompts(generation: dict, ajustes: dict | None = None) -> dict:
    """{slot: prompt} de TODO job da geracao, inclusive o de juncao."""
    from .slots import JOBS
    ajustes = ajustes if ajustes is not None else config.settings()
    return {slot: build_prompt(generation, ajustes, slot) for slot in JOBS}
