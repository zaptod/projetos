# -*- coding: ascii -*-
"""Camada de nomes do random_builds: nome de personagem e de arma.

Existe separada do neural_fights por tres motivos concretos:
1. o banco do jogo ja tem dezenas de registros no formato antigo; mudar a
   fabrica oficial nao conserta os antigos e cria duas convencoes no mesmo
   arquivo;
2. o jogo e name-keyed (p1_nome, nome_arma, saves de torneio), entao nome la
   e chave, nao enfeite -- mexer nele muda comportamento do jogo;
3. o video precisa de um parametro que o jogo nao tem: o nome pedido no
   comentario.

Nada aqui importa neural_fights, src.identity ou src.editing. As chaves de
consulta chegam prontas de quem chamou (o que a roleta sorteou) e TODA
consulta cai num fallback, entao classe/encantamento/raridade nova no banco
nao quebra nada -- so nao ganha sabor ate ser mapeada aqui (pedido 2).

Regra do pedido 4, testavel em termina_bem(): a ultima palavra do nome nunca
e qualidade nem adjetivo. Um epiteto com preposicao ("das Chamas") continua
sendo rotulo pendurado, entao a casa e fundida numa palavra so ("Sombracorvo"):
nao da para arrancar sem destruir a palavra.
"""
from __future__ import annotations

import unicodedata
from . import moderacao

# O '@' e reservado pelo neural_fights (live/identity.PREFIXO_CATALOGO) para
# lutador de espectador; nome nenhum daqui pode comecar com ele.
PREFIXO_RESERVADO = "@"

MAX_PALAVRAS_PEDIDO = 4
MAX_CHARS_PEDIDO = 28


# Os geradores e o lexico vivem em lexico.py; aqui fica a GUARDA (o que um
# nome nao pode ser) e o nome que vem do comentario.
from .lexico import (  # noqa: F401  (re-exportados: a suite usa nomes.X)
    CLASSIFICADOR_POR_TIPO, CULTURA_POR_CLASSE, DEGRAUS, DEGRAU_PADRAO,
    DESINENCIA_POR_TIPO, NOMES_POR_CULTURA, NUCLEO_POR_PERSONALIDADE,
    RAIZES_ARMA, RAIZES_CASA, RAIZES_SECUNDARIAS, chave,
    gerar_nome_arma, gerar_nome_personagem, sortear_genero)

def _fundir(a: str, b: str) -> str:
    """Cola duas raizes evitando letra dobrada na emenda."""
    if not a:
        return b
    if not b:
        return a
    if a[-1].lower() == b[0].lower():
        return a + b[1:]
    return a + b

# Vocabulario LEGADO. O gerador de hoje nao produz epiteto nem honorifico,
# mas eles continuam proibidos no fim de um nome: a regra do usuario vale
# para o que o jogo antigo escrevia e para o que outra pessoa escrever depois.
EPITETOS = {
    "EPICO": [("Alto", "Alta"), ("Grande", "Grande"), ("Nobre", "Nobre"),
              ("Velho", "Velha")],
    "LENDARIO": [("Primeiro", "Primeira"), ("Ultimo", "Ultima"),
                 ("Supremo", "Suprema"), ("Invicto", "Invicta")],
    "MITICO": [("Unico", "Unica"), ("Eterno", "Eterna"),
               ("Primordial", "Primordial"), ("Imortal", "Imortal")],
}

# "Ser/Sera" e "Titan/Titania" foram descartados: leem como nome proprio e o
# personagem passa a ter tres nomes ("Sera Mirel Breuprova").
HONORIFICOS = {
    "LENDARIO": [("Dom", "Dona"), ("Arconte", "Arconte"),
                 ("Marechal", "Marechal"), ("Mestre", "Mestra")],
    "MITICO": [("Alto-Rei", "Alta-Rainha"), ("Arquimestre", "Arquimestra"),
               ("Primarca", "Primarca"), ("Grao-Mestre", "Grao-Mestra")],
}

# (raizes no nome da arma, usa "de", faixa de epiteto/honorifico)

# Palavras que nao podem fechar um nome: o adjetivo colado no fim de que o
# usuario reclamou. Cobre os TITULOS e os sufixos de qualidade do gerador
# antigo do neural_fights, mais os epitetos/honorificos daqui.
PROIBIDO_NO_FIM = {
    "COMUM", "INCOMUM", "RARO", "EPICO", "LENDARIO", "MITICO",
    "REFINADO", "SUPERIOR", "SUPREMO", "MAGNIFICO", "EXCELSO",
    "BRAVO", "VALENTE", "NOBRE", "JUSTO", "SABIO",
    "PROTETOR", "INVICTO", "CRUEL", "IMPIEDOSO",
    "SOMBRIO", "LOUCO", "FURIOSO", "DESTRUIDOR",
    "IMPLACAVEL", "IMORTAL", "ETERNO", "AMALDICOADO", "ABENCOADO",
    "PROFETA", "VIDENTE", "CHAMAS", "SOMBRAS", "TROVAO", "LUZ", "GELO",
    # Vocabulario de qualidade do gerador antigo do jogo (TITULOS,
    # SUFIXOS_ELEMENTO, SUFIXOS_LENDARIOS, PREFIXOS_QUALIDADE). Copiado e nao
    # importado porque este modulo nao pode depender do neural_fights; quem
    # cobra a lista contra o vocabulario vivo e a suite de testes.
    "BRUTAL", "CELESTIAL", "CONGELANTE", "CONQUISTADOR", "DEVASTADOR",
    "DIMENSIONAL", "DIVINO", "ELEGANTE", "ELETRICO", "ETEREO", "FEROZ",
    "FLAMEJANTE", "GRACIOSO", "HEROI", "INVENCIVEL", "LETAL", "MISTICO",
    "MORTAL", "OBSCURO", "PERFEITO", "PRECISO", "RADIANTE", "SAGRADO",
    "SANGRENTO", "SELVAGEM", "SILENCIOSO", "SOMBRO", "TEMIVEL", "VELOZ",
    "VENENOSO", "VINGADOR", "VITORIOSO", "ANAO", "ANTIGO", "CAMPEAO",
    "ABISMO", "APOCALIPSE", "ARCANO", "AURORA", "CAOS", "CEU", "COMECO",
    "CRIACAO", "DEMONIOS", "DESTINO", "DEUSES", "DRAGOES", "ESCURIDAO",
    "ETERNIDADE", "FIM", "FLORESTA", "FRIO", "INFERNO", "INVERNO",
    "MAGMA", "NATUREZA", "NEVASCA", "PERDICAO", "PIRA", "RELAMPAGO",
    "SALVACAO", "SUBLIME", "TEMPESTADE", "TITAS", "VAZIO", "VENCEDOR",
}
# Toda palavra proibida vale nos DOIS generos e nos dois numeros: "FURIOSA"
# ficava livre so porque a lista trazia "FURIOSO". Meia lista e pior que lista
# nenhuma - ela da a impressao de que a regra fecha.
for _palavra in list(PROIBIDO_NO_FIM):
    if _palavra.endswith("O"):
        PROIBIDO_NO_FIM.add(_palavra[:-1] + "A")
    elif _palavra.endswith("A"):
        PROIBIDO_NO_FIM.add(_palavra[:-1] + "O")
    elif _palavra.endswith("OR"):
        PROIBIDO_NO_FIM.add(_palavra + "A")
for _grupo in list(EPITETOS.values()) + list(HONORIFICOS.values()):
    for _masc, _fem in _grupo:
        PROIBIDO_NO_FIM.add(chave(_masc))
        PROIBIDO_NO_FIM.add(chave(_fem))
for _palavra in list(PROIBIDO_NO_FIM):
    PROIBIDO_NO_FIM.add(_palavra + "S")
    if _palavra.endswith(("R", "Z", "L")):
        PROIBIDO_NO_FIM.add(_palavra + "ES")

# "de" nao entra: "Salva de Ferielen" termina em nome proprio inventado, nao em
# rotulo. Ja "o Sombrio" e "das Chamas" sao exatamente o que se quer barrar.
ARTIGOS_PENDURADOS = {"o", "a", "os", "as", "do", "da", "dos", "das"}


def _pluralizar(palavra: str) -> str:
    """Classificador plural ("Garras") exige epiteto plural ("Ultimas")."""
    if palavra.endswith(("al", "el", "il", "ol", "ul")):
        return palavra[:-1] + "is"
    return palavra + "s"


def termina_bem(nome: str) -> bool:
    """Guarda do pedido 4: a ultima palavra e identidade, nao qualidade."""
    partes = str(nome).split()
    if not partes:
        return False
    if chave(partes[-1]) in PROIBIDO_NO_FIM:
        return False
    if len(partes) >= 2 and partes[-2].lower() in ARTIGOS_PENDURADOS:
        return False
    return True

# -------------------------------------------------- nome vindo do comentario
_PERMITIDOS = " -'"


def _latino(c: str) -> bool:
    """A letra sobrevive ate a tela?

    A placa desenha com Arial Black e a legenda joga fora tudo que nao e ASCII.
    Cirilico, grego, CJK e hangul passam por isalnum(), viram quadradinho na
    placa e SOMEM da legenda: o video mostrava o nome do comentarista na placa
    e ao mesmo tempo pedia "SEU NOME NOS COMENTARIOS" como se ninguem tivesse
    pedido. Recusar na entrada mantem o video coerente - nome gerado e convite
    neutro. O acento fica: "Nicolas" desenha e a legenda so tira o acento.
    """
    base = "".join(x for x in unicodedata.normalize("NFD", c)
                   if unicodedata.category(x) != "Mn")
    return bool(base) and all(ord(x) < 128 and x.isalnum() for x in base)


def sanitizar_nome_pedido(texto):
    """Limpa o nome que veio do comentario; devolve (nome, motivo_recusa).

    Nome de comentario e texto de estranho: pode vir com @, emoji, caixa
    aleatoria e um paragrafo inteiro. Aqui ele vira algo que cabe na placa e
    que o banco name-keyed do jogo aceita como chave.
    """
    if not isinstance(texto, str):
        return None, "nao textual"
    bruto = texto.strip().lstrip(PREFIXO_RESERVADO).strip()
    if not bruto:
        return None, "vazio"
    # Antes de limpar: a limpeza quebra o termo em pedacos e esconde a ofensa.
    if moderacao.ofensivo(bruto):
        return None, moderacao.MOTIVO

    limpo = "".join(c for c in bruto
                    if (c.isalnum() and _latino(c)) or c in _PERMITIDOS)
    if not any(c.isalpha() for c in limpo) and any(c.isalpha() for c in bruto):
        return None, "fora do alfabeto latino"
    # Palavra sem letra nenhuma e sobra de emoji/pontuacao ("<3" vira "3");
    # como nome ela so suja a placa.
    palavras = [p for p in limpo.split() if any(c.isalpha() for c in p)]
    if not palavras:
        return None, "sem caracteres validos"
    palavras = palavras[:MAX_PALAVRAS_PEDIDO]
    palavras = [p[0].upper() + p[1:] for p in palavras]

    nome = " ".join(palavras)
    while len(nome) > MAX_CHARS_PEDIDO and len(palavras) > 1:
        palavras.pop()
        nome = " ".join(palavras)
    nome = nome[:MAX_CHARS_PEDIDO].strip()
    if len(nome) < 2:
        return None, "curto demais"
    if not any(c.isalpha() for c in nome):
        return None, "sem letras"
    # De novo no fim: cortar palavras pode formar um termo que o bruto nao tinha.
    if moderacao.ofensivo(nome):
        return None, moderacao.MOTIVO
    return nome, None


def resolver_nome_personagem(rng, classe=None, personalidade=None,
                             encantamento=None, elemento=None, raridade=None,
                             genero=None, nome_pedido=None) -> dict:
    """Decide o nome final e registra de onde ele veio.

    O nome gerado sai SEMPRE, mesmo quando o comentario manda um: assim a
    mesma seed produz a mesma build com ou sem pedido, e o generation.json
    guarda o que teria saido.

    `genero` fixado tambem NAO pula o sorteio: o mesmo rng batiza a arma e
    alimenta as fabricas do jogo logo depois, entao economizar um `choice`
    aqui deslocaria a corrente e escolher o genero mudaria a arma e a cor do
    personagem -- coisas que ninguem pediu para mudar.
    """
    genero_sorteado = sortear_genero(rng)
    genero = genero or genero_sorteado
    gerado = gerar_nome_personagem(
        rng, classe=classe, personalidade=personalidade,
        encantamento=encantamento, elemento=elemento, raridade=raridade,
        genero=genero)

    pedido_bruto = nome_pedido if isinstance(nome_pedido, str) else None
    escolhido, motivo = (None, None)
    if nome_pedido is not None:
        escolhido, motivo = sanitizar_nome_pedido(nome_pedido)
    if motivo == moderacao.MOTIVO:
        # A pasta da geracao e o que o dono abre e compartilha. Guardar o
        # xingamento cru de um estranho ali nao ajuda em nada: o motivo ja
        # explica a recusa, e o texto so espalha a ofensa para outro arquivo.
        pedido_bruto = None

    return {
        "name": escolhido or gerado,
        "origin": "comment" if escolhido else "generated",
        "generated_name": gerado,
        "gender": genero,
        "generated_gender": genero_sorteado,
        "requested_name": pedido_bruto,
        "requested_accepted": bool(escolhido),
        "requested_reason": motivo,
    }
