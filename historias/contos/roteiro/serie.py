# -*- coding: utf-8 -*-
"""Historia LONGA, dividida em partes: a biblia primeiro, depois cada parte.

Pedir "uma historia de 80 cenas" num prompt so nao funciona: o modelo perde
o fio, repete informacao e resolve o conflito no meio. O que funciona e o
que um roteirista faz — primeiro a BIBLIA (premissa, elenco, a virada
central e o arco de cada parte), depois cada parte escrita com a biblia
inteira em contexto.

E por isso que a automacao do browser importa: as duas etapas acontecem no
MESMO chat, entao a parte 7 e escrita com a biblia e as seis partes
anteriores ainda no contexto. Copiar e colar isso a mao seria inviavel.

A biblia tambem resolve o problema visual: ela fixa a descricao FISICA do
protagonista em ingles, e essa mesma frase entra em toda cena de todas as
partes. E o que faz 80 imagens parecerem a mesma pessoa.
"""
from __future__ import annotations

import re
import unicodedata

from .modelo import carregar_config

# Uma parte = um video. Estes numeros sao o alvo que vai no prompt.
CENAS_POR_PARTE = 14
PARTES_PADRAO = 6


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def _limpar(linha: str) -> str:
    texto = str(linha).replace("**", "").replace("__", "").strip()
    texto = re.sub(r"^\s*[-*+]\s+", "", texto)
    return re.sub(r"^#{1,4}\s*", "", texto).strip()


# --------------------------------------------------------------- 1. biblia
def proxima_estrutura(usadas: list, config: dict | None = None) -> str:
    """Qual molde usar agora: o que ficou mais tempo sem aparecer.

    O fluxo automatico NUNCA usou os moldes. `config/roteiro.json` tem tres
    (`reddit`, `confissao`, `vinganca`) e so o caminho manual os lia; a serie
    pedia "6 partes de 14 cenas" e deixava a forma por conta do modelo — que
    converge sempre para a mesma. Foi assim que as historias 9 e 10 sairam
    quase iguais ("conta de luz paga no meu nome").

    Rodizio pelo menos usado, e nao sorteio: sorteio repete.
    """
    config = config or carregar_config()
    return _menos_usado(moldes_disponiveis(config), usadas)


def moldes_disponiveis(config: dict | None = None) -> list:
    """Os moldes que o rodizio pode sortear.

    Fora as chaves `_comment_*`. O resto do arquivo documenta cada bloco com
    um comentario IRMAO (`_comment_ganchos` ao lado de `ganchos`), e dentro de
    `modelos` esse mesmo habito criaria um molde fantasma: o rodizio o
    escolheria, `prompt_biblia` acharia uma string onde espera um dicionario e
    a historia sairia sem molde nenhum — em silencio, que e o pior jeito.
    """
    config = config or carregar_config()
    return [nome for nome in (config.get("modelos") or {})
            if not nome.startswith("_")]


def _menos_usado(disponiveis: list, usadas: list) -> str:
    """O que ficou MAIS TEMPO sem aparecer. `""` quando nao ha candidato.

    `usadas` vem do mais NOVO para o mais velho, entao o indice e a idade:
    indice 0 = usado agora, indice maior = visto ha mais tempo.

    DUAS FASES. Primeiro quem nunca apareceu na janela — comecar pelo virgem
    e o que espalha mais rapido. Depois, entre os que ja apareceram, o de
    MAIOR indice.

    A segunda fase estava errada e o erro era visivel no disco. Ela fazia
    `for nome in reversed(usadas)`, o que pega a ocorrencia mais ANTIGA da
    JANELA — e como a janela tem 12 e a entrada velha continua nela, o mesmo
    nome voltava sempre: `reddit` saiu nas historias 11, 14 e 15 de cinco.
    O que importa nao e onde o nome apareceu pela ultima vez na lista, e ha
    quanto tempo ele foi usado pela ULTIMA vez — que e o menor indice dele.
    """
    disponiveis = [n for n in disponiveis if n]
    if not disponiveis:
        return ""
    for nome in disponiveis:
        if nome not in usadas:
            return nome
    # `usadas.index(nome)` e a ultima vez que ele foi usado (a lista vem do
    # mais novo para o mais velho); o maior indice e o mais esquecido.
    return max(disponiveis, key=usadas.index)


def _fichas_dos_ganchos(nomes, narrador: str, config: dict | None) -> list:
    """[(nome, ficha)] das alavancas pedidas, ignorando nome que nao existe.

    Nome desconhecido nao levanta: um catalogo editado a mao nao pode derrubar
    a geracao da noite. Ele so nao entra no prompt, e a historia sai com uma
    alavanca em vez de duas — pior, mas viva.
    """
    catalogo = catalogo_de_ganchos(narrador, config)
    saida = []
    for nome in (nomes or []):
        ficha = catalogo.get(str(nome))
        if ficha:
            saida.append((str(nome), ficha))
    return saida


NARRADORES = ("mulher", "homem")


def proximo_narrador(usados: list) -> str:
    """Quem conta a proxima historia — em rodizio, nao ao gosto do modelo.

    Ate 09/09/2026 o narrador era decidido pelo LLM DENTRO da biblia, e ele
    derivava: as historias 12, 13, 14 e 15 sairam todas com narrador homem,
    quatro seguidas.

    Escolher aqui resolve tambem uma ordem impossivel: as alavancas sao de
    GENERO ("marido que nao cresce" so funciona na boca dela), entao e preciso
    saber quem narra ANTES de montar o prompt — e nao depois de ler a resposta.
    """
    return _menos_usado(list(NARRADORES), usados) or NARRADORES[0]


def catalogo_de_ganchos(narrador: str = "",
                        config: dict | None = None) -> dict:
    """As alavancas que servem para quem narra: as dele mais as universais."""
    config = config or carregar_config()
    todos = config.get("ganchos") or {}
    if not isinstance(todos, dict):
        return {}
    # AS ESPECIFICAS PRIMEIRO, e a ordem nao e cosmetica: `_menos_usado`
    # estreia na ordem do catalogo, e as universais sao as MENOS especificas
    # do conjunto. Montando ao contrario, as tres primeiras historias saiam
    # com CULPA, SEGREDO e DIVIDA MORAL — exatamente o generico que este
    # catalogo existe para substituir, enquanto MARIDO QUE NAO CRESCE so
    # apareceria na quinta.
    saida = dict(todos.get(str(narrador).strip().lower()) or {})
    for nome, ficha in (todos.get("qualquer") or {}).items():
        saida.setdefault(nome, ficha)
    return saida


def proximos_ganchos(usados: list, narrador: str = "",
                     config: dict | None = None) -> list:
    """As DUAS alavancas desta historia: uma de medo, uma de fantasia.

    UMA DE CADA REGISTRO de proposito. A historia segura pelo medo e recompensa
    pela fantasia; duas do mesmo lado dao um video que so aperta (e cansa) ou
    so afaga (e nao prende).

    QUEM ESCOLHE E O RODIZIO, e essa e a mudanca que importa. Antes o prompt
    mandava as nove e pedia "escolha DUAS" — e o modelo, com escolha livre,
    convergia sempre: as cinco historias que nasceram com alavancas ligadas
    (11 a 15) escolheram TODAS o mesmo par, TRAICAO + DINHEIRO E STATUS, e
    seis das nove alavancas nunca foram usadas uma vez sequer.
    """
    catalogo = catalogo_de_ganchos(narrador, config)
    if not catalogo:
        return []
    escolhidos = []
    for registro in ("medo", "fantasia"):
        candidatos = [nome for nome, ficha in catalogo.items()
                      if (ficha or {}).get("registro") == registro]
        nome = _menos_usado(candidatos, usados)
        if nome:
            escolhidos.append(nome)
    return escolhidos


def prompt_biblia(*, partes: int = PARTES_PADRAO,
                  cenas_por_parte: int = CENAS_POR_PARTE,
                  tema: str | None = None, config: dict | None = None,
                  evitar: list | None = None, estrutura: str = "",
                  ganchos: list | None = None, narrador: str = "") -> str:
    """Etapa 1: a historia inteira planejada, sem escrever nenhuma cena.

    `evitar` sao as historias que o canal JA tem. Sem elas o modelo se repete:
    com o tema livre e um chat novo, o mesmo prompt converge para a mesma
    ideia. Medido em 08/09/2026, duas rodadas seguidas da agenda automatica:

        historia_00009  "conta de luz paga no meu CPF em um endereco
                         onde nunca pisei na vida"
        historia_00010  "conta de luz paga no meu nome numa casa
                         onde nunca pisei na vida"

    A virada de cada uma era diferente, mas o gancho era o mesmo — e num canal
    que publica 4 a 6 por dia isso vira um so assunto repetido. O chat nao tem
    memoria entre rodadas; a lista e a memoria.
    """
    config = config or carregar_config()
    regras = config["regras"]
    total_cenas = partes * cenas_por_parte
    duracao = total_cenas * 5

    linhas = []
    add = linhas.append
    add("Voce e roteirista-chefe de um canal de historias narradas em video "
        "vertical (TikTok/Shorts/Reels). Vamos trabalhar em DUAS etapas.")
    add("")
    add("ETAPA 1 (agora): a BIBLIA da historia. Nao escreva nenhuma cena "
        "ainda, nao escreva narracao, nao escreva prompt de imagem.")
    add("")
    add(f"A historia sera longa: {partes} PARTES de {cenas_por_parte} cenas "
        f"cada ({total_cenas} cenas, cerca de {duracao // 60} minutos no total). "
        "Cada parte vira um video proprio, publicado em sequencia.")
    if tema:
        add(f"TEMA (ponto de partida; o resto voce inventa): {tema}")
    else:
        add("TEMA: voce escolhe. Uma situacao especifica e incomum, que a "
            "pessoa nao consegue prever pelo titulo.")
    add("")
    if evitar:
        add("O CANAL JA TEM ESTAS HISTORIAS. Nao repita nenhuma delas — nem o "
            "assunto, nem o gancho, nem o tipo de descoberta. Se a sua ideia "
            "se parecer com alguma, troque de ideia antes de escrever:")
        for anterior in evitar:
            add(f"  - {str(anterior).strip()[:160]}")
        add("")
    molde = (config.get("modelos") or {}).get(estrutura or "") or {}
    if molde:
        # O MOLDE ENTRA AQUI. Sem ele a serie so pedia "N partes de M cenas" e
        # a forma ficava por conta do modelo — que escolhe sempre a mesma.
        add(f"MOLDE DESTA HISTORIA: {molde.get('rotulo', estrutura)}.")
        add("A historia INTEIRA segue esta forma, distribuida entre as partes "
            "(cada bloco abaixo pode ocupar mais de uma parte):")
        for passo in molde.get("estrutura") or []:
            add(f"  - {passo}")
        add("Nao troque de forma no meio, e nao use a forma de outra historia "
            "que voce ja tenha escrito.")
        add("")
    # O QUE PRENDE NAO E A TRAMA, e o que ela mexe em quem assiste. Sem isto o
    # modelo escreve um acontecimento bem contado e a pessoa sai no meio,
    # porque nada nela estava em jogo.
    terceira = (molde.get("pessoa") or "primeira") == "terceira"
    if terceira:
        # A CATEGORIA CARICATA NAO E RELATO. Mandar "primeira pessoa de uma
        # mulher adulta" aqui e, tres blocos abaixo, "sem magia, relato
        # pessoal" matava o genero na primeira linha do prompt: nao existe
        # novela de fruta em primeira pessoa realista.
        voz = narrador or "quem conhece todo mundo na rua"
        add(f"QUEM CONTA: um narrador de fora, voz de {voz}. Ele nao e "
            "personagem: ele assiste, comenta e toma partido.")
        add("")
    elif narrador:
        # QUEM NARRA VEM DECIDIDO. Antes o modelo escolhia, e derivava: as
        # historias 12 a 15 sairam todas com narrador homem, quatro seguidas.
        add(f"QUEM CONTA: {narrador}. A historia inteira e na primeira pessoa "
            f"de uma {'mulher' if narrador == 'mulher' else 'homem'} adulta"
            f"{'' if narrador == 'mulher' else ' adulto'}.")
        add("")

    # AS DUAS JA VEM ESCOLHIDAS, e essa e a mudanca que importa. O prompt
    # antigo mandava as nove e pedia "escolha DUAS" — e o modelo, com escolha
    # livre, convergia sempre: as cinco historias geradas com alavancas (11 a
    # 15) escolheram TODAS o mesmo par, e seis das nove nunca foram usadas.
    # Mandar o catalogo inteiro junto empurraria de volta para a media, que e
    # justamente a doenca.
    escolhidos = _fichas_dos_ganchos(ganchos, narrador, config)
    if escolhidos:
        add("ALAVANCAS DESTA HISTORIA (sao estas DUAS, nao escolha outras):")
        for nome, ficha in escolhidos:
            add(f"  - {nome.replace('_', ' ')} [{ficha.get('registro', '')}]")
            add(f"      o que mexe em quem assiste: {ficha.get('mexe', '')}")
            add(f"      como isso APARECE (mostre, nao diga): "
                f"{ficha.get('cena', '')}")
        add("  - Uma delas e MEDO e a outra e FANTASIA de proposito: a "
            "historia segura pelo medo e recompensa pela fantasia. As duas "
            "valem do comeco ao fim — trocar no meio e recomecar a historia.")
        add("  - A alavanca e sobre QUEM ASSISTE, nao enfeite da trama. Toda "
            "parte fecha com pelo menos uma ABERTA: a pessoa continua porque "
            "precisa saber, nao porque foi pedido.")
        add("  - NUNCA NOMEIE a alavanca no texto. Nao escreva 'ela tinha "
            "medo de ter escolhido errado' — mostre a cena que faz quem "
            "assiste pensar isso sozinho.")
        add("")

    # FORA DO `if` junto com o LIMITE, e pelo mesmo motivo: isto vale para a
    # historia inteira, tenha ela alavanca escolhida ou nao. Deixar aqui
    # dentro fazia a regra sumir do prompt quando o catalogo nao respondesse.
    add("  - A tensao mora no que a pessoa SENTE, nao no que a camera "
        "mostra: sugerir prende mais do que mostrar, e e o que passa no "
        "filtro de conteudo das imagens e das plataformas.")
    add("")

    # LIMITE DURO, e FORA de qualquer `if`. Medido em 08/09/2026, na primeira
    # historia gerada com as alavancas ligadas: o modelo foi de "desejo e
    # vergonha" direto para a virgindade de uma menina de 17 anos comprada por
    # R$ 50 mil. Isso nao e questao de gosto — o YouTube remove mesmo sendo
    # ficcao, o PicassoIA recusa as imagens, e o canal publica sozinho e
    # PUBLICO. Ate 09/09 este bloco morava DENTRO do `if ganchos:`: um
    # catalogo vazio ou com outro formato levava o guarda-corpo junto, em
    # silencio. Ele agora e incondicional, e com alavancas mais carnais
    # (DESEJADA PELO PROIBIDO, DESEJADO POR VARIAS) ele importa mais.
    add("LIMITE, e ele nao se negocia:")
    add("  - NINGUEM menor de 18 anos em situacao sexual ou romantica — nem "
        "agora, nem no passado da historia, nem sugerido.")
    add("  - Nada de teste de paternidade, filiacao, adocao ou qualquer duvida "
        "sobre quem e o pai/mae de uma crianca. A plataforma derruba conteudo "
        "sobre crianca em contextos como este, independente da palavra usada.")
    add("  - Nada de sexo explicito, de violencia sexual, de autolesao como "
        "cena, nem de pessoa, marca ou crime reais.")
    add("  - Uma historia que a plataforma derruba nao serve para nada, por "
        "melhor que seja. Se a ideia so funciona passando desse limite, ela e "
        "a ideia errada: troque, nao suavize.")
    add("")
    add("REGRAS DA HISTORIA (valem para o planejamento inteiro):")
    if molde.get("regras"):
        # O MOLDE MANDA. Um genero caricato nao cabe nas regras do relato
        # confessional — "desabafo de gente real, sem final de novela" e o
        # oposto exato do que faz uma novela de fruta funcionar. Sobrepor a
        # lista inteira, e nao acrescentar, e o que evita o prompt pedir as
        # duas coisas e o modelo entregar nenhuma.
        for regra in molde["regras"]:
            add(f"  - {str(regra).strip()}")
    else:
        add("  - Historia ficticia em primeira pessoa, com nomes inventados.")
        add("  - O texto final vai soar como um DESABAFO que uma pessoa real "
            "postou num forum, nao como roteiro. Planeje so acontecimentos que "
            "alguem contaria de memoria, com detalhe mundano e ponta solta.")
        add("  - UMA pergunta central atravessa as {n} partes e so e respondida "
            "na ultima.".replace("{n}", str(partes)))
        add("  - Cada parte entrega um FATO NOVO que muda o que se sabia ate "
            "ali — nao basta 'avancar a acao'. Se a parte pode ser resumida sem "
            "perder nada, ela nao existe.")
        add("  - Cada parte tem a propria mini-virada, alem da virada central.")
        add("  - Nada de enrolacao: se um acontecimento nao muda a situacao do "
            "protagonista, ele nao existe.")
        add("  - A historia precisa caber num relato pessoal: sem magia, sem "
            "conspiracao mundial, sem final de novela.")
    add("")
    add("CONSISTENCIA VISUAL (isto e obrigatorio):")
    add("  - Descreva o protagonista FISICAMENTE em ingles, em uma frase "
        "curta e fixa. Ela PRECISA ter, nesta ordem: etnia ou tom de pele, "
        "idade aparente, cabelo (cor e corte), UM traco marcante do rosto, "
        "e a roupa recorrente.")
    add("  - Nada de adjetivo vago no lugar de um traco: 'tired eyes' e "
        "'kind face' nao descrevem ninguem e cada imagem inventa uma pessoa "
        "diferente. Vale 'a thin scar on the left eyebrow', 'round "
        "wire-frame glasses', 'a wide gap between the front teeth'.")
    add("  - Essa frase sera repetida em TODAS as imagens de TODAS as partes, "
        "entao nao pode mudar depois. Nada de nome dentro dela.")
    add("  - Faca o mesmo para cada personagem que aparece mais de uma vez.")
    add("")
    # O gemeo FACTUAL da consistencia visual. A descricao fisica ja e repetida
    # em toda imagem — mas repetir uma descricao VAGA nao fixa ninguem: em
    # 12/09/2026 o Gemini reprovou tres videos porque o protagonista trocava
    # de rosto entre as cenas, e o motivo estava aqui. A frase era "a 30s man,
    # short dark hair, tired eyes, wearing a simple gray button-down shirt",
    # que serve tanto a um homem asiatico quanto a um branco — e o modelo
    # escolhia um diferente a cada imagem. Dai a exigencia de etnia e de UM
    # traco concreto acima. Nada fazia o mesmo pelos NUMEROS, e eles
    # derraparam: na historia 8 o aluguel era
    # "tres mil e oitocentos" nas partes 1 e 6 e "cinco mil" na 2, e o casal se
    # conheceu em 2020 na parte 2 e em 2018 na parte 4. Quem escreve a parte 4
    # nao lembra do que disse na 2 — entao a ficha vai junto em toda pergunta.
    add("CONSISTENCIA DE FATOS (isto e obrigatorio):")
    add("  - Liste os numeros e datas que a historia vai citar mais de uma "
        "vez: valores em reais, anos, idades, ha quanto tempo cada coisa dura.")
    add("  - Escolha UM valor para cada um agora. Eles serao repetidos nas "
        "partes exatamente como voce escrever aqui, e nao podem mudar.")
    add("  - Confira se eles fecham entre si antes de responder (se o primeiro "
        "pagamento foi em 2018 e faz oito anos, o presente e 2026).")
    add("")
    add("FORMATO DA RESPOSTA (exatamente assim, sem nada em volta):")
    add("")
    add("TITULO DA SERIE: <uma linha "
        + ("de escandalo, com o apelido de quem aprontou, do jeito que a "
           "vizinha contaria gritando" if terceira
           else "em primeira pessoa")
        + ", que ja entrega o conflito e provoca curiosidade>")
    # A MARCA, e ela nao e o titulo. O titulo da serie e uma FRASE de gancho
    # ("Faz quatro anos que minha esposa acha que fui promovido, mas...") e
    # nao cabe no titulo de um video junto com o numero da parte. Sem uma
    # marca curta, as seis partes foram ao ar como seis videos sem relacao
    # nenhuma e quem gostou de uma nao tinha como achar as outras.
    add("NOME DA SERIE: <2 a 4 palavras, como nome de novela. E a MARCA que "
        "vai no titulo de TODAS as partes, entao precisa ser curta, "
        "especifica desta historia e facil de reconhecer numa lista. Nao "
        "repita a frase do titulo>")
    add("PREMISSA: <2 frases: a situacao e a pergunta central>")
    add("PROTAGONISTA: <nome> | <descricao fisica em ingles, uma frase>")
    # Continua sendo pedido de volta mesmo quando ja foi ditado: e assim que
    # `parse_biblia` o captura, e e a confirmacao de que o modelo obedeceu.
    add("NARRADOR: " + (f"{narrador} (ja definido acima; repita exatamente "
                        "isto)" if narrador
                        else "<homem ou mulher — quem esta contando em "
                             "primeira pessoa>"))
    add("ELENCO: <nome> | <descricao fisica em ingles>; <nome> | <descricao>")
    add("CENARIO: <onde a historia acontece, em ingles, uma frase>")
    add("ALAVANCAS: <as DUAS escolhidas> | <o que exatamente esta em jogo "
        "para quem assiste, em uma frase>")
    add("FATOS: <nome do fato> = <valor>; <nome do fato> = <valor>  "
        "(ex.: aluguel = R$ 3.800 por mes; primeiro pagamento = 2018; "
        "ano em que se conheceram = 2020; idade dela = 34)")
    add("VIRADA CENTRAL: <a informacao que muda tudo, e em que parte ela sai>")
    add("")
    for i in range(1, partes + 1):
        add(f"PARTE {i}")
        add("TITULO: <titulo da parte>")
        add("RESUMO: <o que acontece nesta parte, 2 frases>")
        add("GANCHO: <a primeira frase da parte, a mais forte que ela tem>")
        if i < partes:
            add("CLIFFHANGER: <a pergunta que fica no ar para a parte seguinte>")
        else:
            add("CLIFFHANGER: FINAL - <como a pergunta central e respondida>")
        add("")
    add("Regras de escrita que valerao na etapa 2 (para voce ja planejar "
        "pensando nelas):")
    for regra in regras["narracao"][:6]:
        add(f"  - {regra}")
    return "\n".join(linhas)


def parse_biblia(texto: str, partes_esperadas: int = PARTES_PADRAO) -> dict:
    """Texto da etapa 1 -> {titulo, premissa, protagonista, elenco, partes}."""
    campos = {"titulo": "", "premissa": "", "protagonista": "", "elenco": "",
              "cenario": "", "virada": "", "narrador": "", "fatos": "",
              "alavancas": "", "serie_nome": ""}
    rotulos = {
        "titulo da serie": "titulo", "titulo": "titulo", "premissa": "premissa",
        "protagonista": "protagonista", "elenco": "elenco", "cenario": "cenario",
        "virada central": "virada", "narrador": "narrador", "fatos": "fatos",
        "alavancas": "alavancas", "nome da serie": "serie_nome",
    }
    partes = []
    atual = None
    for bruta in texto.splitlines():
        linha = _limpar(bruta)
        if not linha:
            continue
        cabecalho = re.match(r"^parte\s*(\d+)", _sem_acento(linha).lower())
        if cabecalho and ":" not in linha:
            atual = {"n": int(cabecalho.group(1)), "titulo": "", "resumo": "",
                     "gancho": "", "cliffhanger": ""}
            partes.append(atual)
            continue
        if ":" not in linha:
            continue
        rotulo, _, valor = linha.partition(":")
        chave = _sem_acento(rotulo).strip().lower()
        valor = valor.strip()
        if atual is not None and chave in ("titulo", "resumo", "gancho",
                                           "cliffhanger"):
            atual[chave] = valor
            continue
        if chave in rotulos and not atual:
            campos[rotulos[chave]] = valor

    nome, _, fisico = campos["protagonista"].partition("|")
    for parte in partes:
        parte["n"] = int(parte["n"])
    partes.sort(key=lambda p: p["n"])
    for ordem, parte in enumerate(partes, 1):
        parte["n"] = ordem

    return {
        "titulo": campos["titulo"],
        # A marca curta que liga as partes no titulo do video. Vazia nas
        # historias anteriores a 11/09/2026, e `titulo_da_parte` sabe viver
        # sem ela — cai em "(Parte 3/6)", que ja diz que ha mais.
        "serie_nome": campos["serie_nome"],
        "premissa": campos["premissa"],
        "protagonista_nome": nome.strip(),
        "protagonista": fisico.strip() or campos["protagonista"].strip(),
        "narrador": campos["narrador"],
        "elenco": campos["elenco"],
        "cenario": campos["cenario"],
        "fatos": campos["fatos"],
        "alavancas": campos["alavancas"],
        "virada": campos["virada"],
        "partes": partes,
        "partes_esperadas": partes_esperadas,
        "bruto": texto,
    }


def problemas_da_biblia(biblia: dict) -> list:
    """O que impede a etapa 2 de sair boa."""
    faltando = []
    if not biblia.get("titulo"):
        faltando.append("sem TITULO DA SERIE")
    if not biblia.get("protagonista"):
        faltando.append("sem descricao fisica do protagonista "
                        "(as imagens vao sair de pessoas diferentes)")
    if not biblia.get("partes"):
        faltando.append("nenhuma PARTE foi planejada")
    elif len(biblia["partes"]) < biblia.get("partes_esperadas", 0):
        faltando.append(f"so {len(biblia['partes'])} parte(s) planejadas de "
                        f"{biblia['partes_esperadas']}")
    sem_gancho = [p["n"] for p in biblia.get("partes", []) if not p.get("gancho")]
    if sem_gancho:
        faltando.append(f"partes sem GANCHO: {sem_gancho}")
    return faltando


def prompt_trocar_premissa(termos: list, partes: int = PARTES_PADRAO) -> str:
    """A premissa nao pode ir ao ar: troque a PRESSAO, guarde o resto.

    Descartar a historia inteira aqui era jogar fora um plano que estava bom
    em tudo menos num ponto — e, pior, deixar a agenda parada esperando a
    proxima rodada. Mas o conserto tambem nao e trocar a PALAVRA: a revisao da
    plataforma olha do que a historia TRATA, e um termo mais educado esconde
    de quem le, nao de quem revisa. O preco de errar e o canal, nao o video.

    O conserto que funciona e outro, e ele nem custa forca da historia: o que
    prendia nunca foi a premissa proibida — era a DIVIDA, o PODER de um sobre
    o outro, a VERGONHA de ter aceitado, e o sujeito reaparecendo com poder.
    Tudo isso existe inteiro entre adultos, e fica mais dificil de adivinhar.

    Um turno de chat contra uma historia perdida.
    """
    termos = [str(t) for t in (termos or []) if str(t).strip()]
    citados = ", ".join(f'"{t}"' for t in termos) or "o ponto marcado"

    linhas = [
        "PARE — essa biblia nao pode virar video, e o motivo nao e a palavra.",
        "",
        f"O que aparece no seu plano ({citados}) coloca a historia numa "
        "categoria que a plataforma remove mesmo sendo ficcao: menor de 18 "
        "anos em situacao sexual ou romantica, inclusive no passado do "
        "personagem e inclusive apenas sugerido.",
        "",
        "NAO tente resolver trocando o termo, censurando letra, escrevendo de "
        "outro jeito ou deixando a idade implicita. Quem revisa le do que a "
        "historia TRATA, nao como esta escrito — e o que esta em jogo aqui "
        "nao e este video, e o canal inteiro.",
        "",
        "O CONSERTO, e ele nao enfraquece nada: o que prendia na sua ideia "
        "nunca foi esse ponto. Era a DIVIDA, o PODER de uma pessoa sobre a "
        "outra, a VERGONHA de ter aceitado, o segredo guardado por anos e o "
        "sujeito reaparecendo por cima. Isso tudo funciona inteiro entre "
        "ADULTOS — e funciona melhor, porque a pessoa escolheu, e ter "
        "escolhido e o que corroi.",
        "",
        "Trocas que mantem a mesma pressao:",
        "  - o que foi comprado deixa de ser o corpo de alguem e passa a ser "
        "um ACORDO que a pessoa assinou adulta: divida da familia paga, "
        "cirurgia, faculdade, o negocio do pai salvo da falencia.",
        "  - o poder deixa de vir da idade e passa a vir do lugar: ele e "
        "credor, chefe, dono, socio, quem tem o documento assinado.",
        "  - a vergonha deixa de ser do que fizeram com ela e passa a ser de "
        "ter aceitado — e de nunca ter contado a ninguem.",
        "  - o reencontro continua igual e ainda melhor: dez anos depois, ele "
        "e apresentado como o novo chefe dela.",
        "",
        "MANTENHA (isto ja estava certo): o molde, as DUAS alavancas "
        "psicologicas, o tipo de virada, o protagonista, o elenco, o cenario "
        "e o ritmo. Ninguem com menos de 23 anos em nada disso.",
        "",
        f"Agora reescreva a BIBLIA INTEIRA das {partes} partes, no mesmo "
        "formato de antes, do TITULO DA SERIE ate a ultima PARTE. Nao comente "
        "a mudanca, nao explique, nao escreva nada fora do formato.",
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------- 2. parte
def prompt_parte(biblia: dict, numero: int, *,
                 cenas: int = CENAS_POR_PARTE,
                 config: dict | None = None) -> str:
    """Etapa 2: escreve UMA parte, em cenas, no formato do contrato."""
    config = config or carregar_config()
    regras = config["regras"]
    total = len(biblia.get("partes") or []) or biblia.get("partes_esperadas", 1)
    plano = next((p for p in biblia.get("partes") or [] if p["n"] == numero), {})
    primeira = numero == 1
    ultima = numero >= total

    linhas = []
    add = linhas.append
    add(f"ETAPA 2 - escreva agora a PARTE {numero} de {total}, e SO ela.")
    add("")
    if plano:
        add(f"O que esta parte tem que entregar (do seu proprio plano): "
            f"{plano.get('resumo') or plano.get('titulo')}")
        if plano.get("gancho"):
            add(f"Gancho planejado: {plano['gancho']}")
        if plano.get("cliffhanger"):
            add(f"Ela termina em: {plano['cliffhanger']}")
        add("")
    add(f"Escreva exatamente {cenas} cenas.")
    add("")
    if primeira:
        add("ABERTURA (parte 1): a primeira cena e o momento mais chocante da "
            "HISTORIA INTEIRA, dito no meio da acao, antes de qualquer "
            "contexto. Nao apresente ninguem antes disso.")
        # O GANCHO E O SEGUNDO EM QUE A PESSOA DECIDE FICAR. Aceitar a
        # primeira frase que vier e deixar isso na sorte; pedir tres e
        # escolher custa o mesmo turno e melhora o unico segundo que importa.
        add("  - Antes de escrever, pense em TRES aberturas diferentes para a "
            "cena 1 e use a mais forte. Nao mostre as descartadas.")
        add("  - A mais forte e a que faz quem ouve PRECISAR saber o que "
            "aconteceu — nao a mais dramatica, nem a mais bem escrita.")
    else:
        add(f"ABERTURA (parte {numero}): a cena 1 recapitula o essencial em "
            "UMA frase que funciona como gancho novo para quem cai aqui "
            "primeiro - nunca 'no episodio anterior'. A cena 2 ja avanca.")
    if ultima:
        add("FECHAMENTO (ultima parte): responda a pergunta central de forma "
            "concreta. Depois, a ultima cena faz uma pergunta direta para "
            "quem assiste. Nao deixe nada em aberto.")
    else:
        add(f"FECHAMENTO (parte {numero}): as duas ultimas cenas montam o "
            "cliffhanger e a ULTIMA FRASE e a pergunta que fica no ar.")
        add("  - NUNCA escreva 'a historia continua na proxima parte' (nem "
            "nada parecido). Medido em 01/09/2026: 9 de 10 partes de uma "
            "serie terminavam com essa frase literal, no pior lugar possivel "
            "— a ultima coisa que a pessoa ouve. Repetida dez vezes, ela "
            "denuncia que o texto saiu de um molde.")
        add("  - A continuacao se PROMETE pela pergunta, nao se anuncia. Se "
            "a pergunta final for boa, ninguem precisa ser avisado de que "
            "existe uma proxima parte.")
    add("")
    add("CONSISTENCIA VISUAL (obrigatorio em todas as cenas):")
    if biblia.get("protagonista"):
        add(f"  - Sempre que o protagonista aparecer, comece o prompt de "
            f"imagem com: {biblia['protagonista']}")
    if biblia.get("elenco"):
        add(f"  - Outros personagens: {biblia['elenco']}")
    if biblia.get("cenario"):
        add(f"  - Cenario: {biblia['cenario']}")
    add("")
    # A ficha vai junto em TODA parte, pelo mesmo motivo que a descricao fisica
    # vai: o modelo nao lembra do numero que ele mesmo escreveu quatro partes
    # atras. Sem ela, o aluguel muda de valor no meio da serie.
    if biblia.get("alavancas"):
        # As mesmas DUAS do comeco ao fim. Sem repetir aqui, a parte 4 escreve
        # uma historia bem contada que nao mexe em nada de quem assiste.
        add(f"ALAVANCAS DESTA HISTORIA (mantenha as duas vivas nesta parte): "
            f"{biblia['alavancas']}")
        add("  - Feche esta parte com pelo menos uma delas ABERTA.")
        add("")
    if biblia.get("fatos"):
        add("FATOS DA HISTORIA (numeros e datas ja fixados - use EXATAMENTE "
            "estes, nunca invente outro valor nem arredonde):")
        for fato in [f.strip() for f in str(biblia["fatos"]).split(";")]:
            if fato:
                add(f"  - {fato}")
        add("  - Se esta parte precisar de um numero ou data que nao esta "
            "acima, escolha um que nao contradiga nenhum destes.")
        add("")
    # COMO DIZER O DURO SEM PERDER O VIDEO. O YouTube nao le a historia: ele
    # pega PALAVRA e IMAGEM. Uma boa historia morrer por causa de um termo cru
    # e desperdicio — a coisa acontece, so nao e nomeada.
    linguagem = config.get("linguagem") or []
    if linguagem:
        add("COMO DIZER O QUE E PESADO (a historia nao suaviza; a PALAVRA sim):")
        for regra in linguagem:
            add(f"  - {regra}")
        add("")
    add("COMO ESCREVER A NARRACAO (a parte mais importante):")
    add("  Isto NAO e uma historia narrada: e um desabafo que uma pessoa real "
        "esta digitando de madrugada. Quem ouvir tem que pensar 'isso "
        "aconteceu mesmo'. As imagens ja entregam que o video e artificial - "
        "o texto e a unica chance de parecer gente. As regras:")
    for regra in regras["narracao"]:
        add(f"  - {regra}")
    add("")
    add("COMO ESCREVER O PROMPT DE IMAGEM:")
    for regra in regras["imagem"]:
        add(f"  - {regra}")
    add("")
    add("SOBRE O TEMPO:")
    for regra in regras["tempo"]:
        add(f"  - {regra}")
    add("")
    add("FORMATO DA RESPOSTA (exatamente assim, sem nada em volta):")
    add("")
    add(f"TITULO: <titulo desta parte, terminando com ' (Parte {numero})'>")
    add("")
    add("CENA 1")
    add("IMAGEM: <prompt em ingles>")
    add("TEMPO: <segundos, so o numero>")
    add("NARRACAO: <o que o narrador fala>")
    add("")
    add(f"... ate a CENA {cenas}. Nao escreva mais nada depois da ultima cena.")
    return "\n".join(linhas)


def prompt_revisao(numero: int, cenas: int, config: dict | None = None) -> str:
    """Pede ao modelo que critique o proprio texto e reescreva.

    E a mudanca que mais levanta qualidade de texto de LLM, e a razao e
    simples: a primeira versao e a media do que ele ja viu — clichê, frase de
    efeito, todas as cenas do mesmo tamanho. Ele SABE reconhecer isso quando
    perguntado; so nao faz de gratis.

    Custa um turno por parte. Numa serie de 6, seis turnos — contra as ~4h que
    a historia leva depois, e barato.
    """
    config = config or carregar_config()
    regras = (config.get("regras") or {}).get("narracao") or []
    linhas = [
        f"Agora RELEIA a parte {numero} que voce acabou de escrever, como se "
        "fosse outra pessoa, e reescreva ela inteira melhor.",
        "",
        "Procure especificamente por:",
        "  - Frase de efeito, metafora literaria e fechamento redondo. Pessoa "
        "real nao termina paragrafo com punchline.",
        "  - Duas cenas que comecam parecido, ou que tem o mesmo tamanho. "
        "Gente conta desigual: uma corrida, outra de tres palavras.",
        "  - Cena que nao entrega informacao NOVA. Se der para cortar sem "
        "perder nada, o problema nao e a cena — e o que ela devia contar.",
        "  - Explicacao do que ja se entendeu. Repetir e o que faz rolar o feed.",
        "  - Palavra que essa pessoa nao usaria falando.",
        "  - TERMO QUE DERRUBA O VIDEO. Toda vez que o texto NOMEIA a coisa "
        "pesada em vez de mostrar, troque: a cena fica, a palavra sai. O "
        "video nao pode morrer por causa de um substantivo.",
        "",
        "As regras que valem continuam as mesmas:",
    ]
    for regra in regras[:8]:
        linhas.append(f"  - {regra}")
    linhas += [
        "",
        f"Devolva a parte {numero} INTEIRA reescrita, as {cenas} cenas, no "
        "mesmo formato de antes (TITULO, e CENA n com IMAGEM/TEMPO/NARRACAO). "
        "Nao comente o que mudou, nao escreva nada fora do formato.",
        "Se uma cena ja estava boa, devolva ela igual — reescrever o que estava "
        "bom so para parecer trabalho piora.",
    ]
    return "\n".join(linhas)


def prompt_continuar(numero: int, ultima_cena: int, cenas: int) -> str:
    """Quando a resposta veio cortada (limite de mensagem do site)."""
    return (f"A parte {numero} veio incompleta: a ultima cena que chegou foi a "
            f"CENA {ultima_cena}. Continue exatamente de onde parou, escrevendo "
            f"da CENA {ultima_cena + 1} ate a CENA {cenas}, no mesmo formato "
            "(CENA / IMAGEM / TEMPO / NARRACAO). Nao repita as cenas "
            "anteriores e nao escreva nenhum texto fora do formato.")
