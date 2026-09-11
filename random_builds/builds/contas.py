# -*- coding: utf-8 -*-
"""Quais CONTAS cada canal usa, e onde ficam as credenciais de cada uma.

O ecossistema tem dois canais (a roleta de builds e as historias) e seis
servicos com login (YouTube, TikTok, ChatGPT, Gemini, PicassoIA, Digen). Ate
aqui cada servico tinha UMA conta, no caminho fixo: um perfil de Chrome, um
arquivo de credencial. Isso quebra na hora em que os canais deixam de
compartilhar conta — publicar a historia no canal de builds e irreversivel.

Este modulo e o registro: por servico, quais contas existem; e, por canal,
qual delas esta ativa. Quem precisa de perfil ou credencial pergunta aqui em
vez de montar o caminho na mao.

    perfil("tiktok", "historias")      -> pasta do Chrome daquela conta
    credencial_youtube("historias")    -> youtube_credentials_<conta>.json

Duas decisoes que evitam estrago:

  COMPATIBILIDADE. A conta `principal` continua usando os caminhos ANTIGOS
  (`random_builds/.browser_profile/tiktok`, `youtube_credentials.json`)
  quando eles ja existem. Nenhum login feito ate hoje se perde.
  FORA DO REPOSITORIO. O registro e as credenciais novas vivem em
  `%LOCALAPPDATA%/neural-fights/`, junto do que ja estava la — nao no
  diretorio versionado.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PADRAO = "principal"

# Canal = produto. Cada um pode ter conta propria em cada servico.
CANAIS = {
    "builds": "Vídeos de build (roleta)",
    "historias": "Histórias por IA",
    "geral": "Vale para tudo (quando o canal não tem conta própria)",
}

# Servicos com login. `tipo` diz o que e a credencial:
#   perfil    -> uma pasta de Chrome (o login mora no cookie)
#   oauth     -> um arquivo de credencial (client_id/secret/refresh_token)
SERVICOS = {
    "youtube": {"rotulo": "YouTube", "tipo": "oauth",
                "publica": True,
                "ajuda": "OAuth do Google Cloud Console; o mesmo token serve "
                         "para o chat da live e para publicar."},
    "tiktok": {"rotulo": "TikTok", "tipo": "perfil", "publica": True,
               "legado": RAIZ / ".browser_profile" / "tiktok",
               "ajuda": "Login no navegador; o perfil guarda a sessao."},
    "chatgpt": {"rotulo": "ChatGPT", "tipo": "perfil", "publica": False,
                "ajuda": "Usado para escrever os roteiros das historias."},
    "gemini": {"rotulo": "Gemini", "tipo": "perfil", "publica": False,
               "ajuda": "Alternativa ao ChatGPT para os roteiros."},
    "picasso": {"rotulo": "PicassoIA", "tipo": "perfil", "publica": False,
                "legado": RAIZ / ".browser_profile" / "picasso",
                "ajuda": "Imagens das cenas e das builds."},
    "digen": {"rotulo": "Digen", "tipo": "perfil", "publica": False,
              "legado": RAIZ / ".browser_profile" / "digen",
              "ajuda": "Video do payoff das builds."},
    # O YouTube aparece DUAS vezes de proposito: `youtube` e o token da API
    # (OAuth) e `youtube_web` e o login do navegador. Medido em 01/09/2026:
    # sao baldes de cota separados — a API recusou por teto enquanto o Studio
    # continuava aceitando —, e podem ate ser contas diferentes.
    "youtube_web": {"rotulo": "YouTube (navegador)", "tipo": "perfil",
                    "publica": True,
                    "legado": RAIZ / ".browser_profile" / "youtube_web",
                    # Os canais do Adrian sao todos da MESMA conta Google:
                    # uma sessao ja enxerga os tres. Dar uma pasta de Chrome
                    # por conta o obrigaria a logar tres vezes para trocar de
                    # destino — e o destino nem depende do login.
                    "sessao_unica": True,
                    "ajuda": "Sobe pelo YouTube Studio. Login manual UMA vez; "
                             "o canal de destino e escolhido pelo id, nao "
                             "por um login novo."},
    "dreamface": {"rotulo": "DreamFace", "tipo": "perfil", "publica": False,
                  "legado": RAIZ / ".browser_profile" / "dreamface",
                  "ajuda": "Segundo gerador de imagem: divide a fila de "
                           "cenas com o PicassoIA."},
}


def runtime_dir() -> Path:
    """Onde as credenciais vivem — fora do repositorio, como as do YouTube."""
    try:
        from neural_fights.data.database import RUNTIME_DIR
        base = Path(RUNTIME_DIR)
    except Exception:
        import os
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "neural-fights"
    base.mkdir(parents=True, exist_ok=True)
    return base


ARQUIVO = None  # resolvido tarde, para os testes poderem trocar runtime_dir


def _caminho_registro() -> Path:
    return Path(ARQUIVO) if ARQUIVO else runtime_dir() / "contas.json"


def _ler() -> dict:
    try:
        with open(_caminho_registro(), encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados: dict) -> None:
    caminho = _caminho_registro()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)


def _limpar_nome(nome: str) -> str:
    """Nome de conta vira nome de pasta: sem acento, sem espaco, sem surpresa."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(nome or "")).encode(
        "ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9_-]+", "_", texto).strip("_").lower()
    return texto[:40] or PADRAO


def estado() -> dict:
    """O registro inteiro, ja com os servicos e a conta padrao garantidos."""
    dados = _ler()
    servicos = dados.setdefault("servicos", {})
    for servico in SERVICOS:
        bloco = servicos.setdefault(servico, {})
        contas = bloco.setdefault("contas", [])
        if PADRAO not in contas:
            contas.insert(0, PADRAO)
        bloco.setdefault("ativa", {})
    return dados


def contas(servico: str) -> list:
    return list(estado()["servicos"].get(servico, {}).get("contas") or [PADRAO])


def ativa(servico: str, canal: str = "geral") -> str:
    """A conta em uso naquele canal.

    Cai para `geral` e depois para `principal`: um canal que nunca escolheu
    conta continua funcionando como sempre funcionou.
    """
    bloco = estado()["servicos"].get(servico, {})
    escolhas = bloco.get("ativa") or {}
    nome = escolhas.get(canal) or escolhas.get("geral") or PADRAO
    disponiveis = bloco.get("contas") or [PADRAO]
    return nome if nome in disponiveis else PADRAO


def adicionar(servico: str, nome: str) -> str:
    """Cria uma conta (so o nome; o login vem depois). Devolve o nome limpo."""
    if servico not in SERVICOS:
        raise KeyError(f"servico desconhecido: {servico!r}")
    limpo = _limpar_nome(nome)
    dados = estado()
    bloco = dados["servicos"][servico]
    if limpo not in bloco["contas"]:
        bloco["contas"].append(limpo)
    _gravar(dados)
    return limpo


# ------------------------------------------------------------------- padrao
# O NOME DA CONTA E O DESTINO. Nao a pessoa, nao a ordem em que foi criada.
#
# Como o registro estava em 08/09/2026, antes desta regra existir:
#
#   `principal`             significava TRES coisas — o canal pessoal (no
#                           youtube_web), o historinhas (no youtube da API) e
#                           a conta de builds (no tiktok)
#   `bem_facil_d_verdade`   e `historinhas` eram o MESMO canal
#                           (UC2S8Z85XCotBNFdstIXpeJw) com dois nomes
#   `canal2`                nao dizia nada
#
# Com nomes assim, "para onde isso vai?" so se responde abrindo o navegador —
# e publicar no canal errado nao tem desfazer. As regras:
#
#   1. UM DESTINO, UM NOME. O mesmo canal real tem o mesmo nome de conta em
#      todos os servicos.
#   2. O NOME E O CANAL REAL, em slug: `neural_fights`, `historinhas`,
#      `pessoal`. Nunca posicao (`principal`, `canal2`) nem arroba.
#   3. `principal` E RESERVADO ao login legado — e o unico que mora nos
#      caminhos antigos, e renomea-lo perderia os logins ja feitos. Ele nao e
#      um destino: canal de projeto caindo nele significa "nao configurado".
#   4. TODO CANAL QUE PUBLICA ESCOLHE EXPLICITAMENTE. Queda padrao e alerta.
#
# `conformidade()` responde se isso esta valendo agora.
NOMES_SEM_SENTIDO = re.compile(r"^(principal|conta\d*|canal\d*|nova?|teste)$")


def renomear(servico: str, antigo: str, novo: str) -> dict:
    """Troca o nome de uma conta LEVANDO o login junto.

    Renomear nao e cosmetico: o nome e a pasta do Chrome
    (`browser_profiles/<servico>__<nome>`) e o arquivo de credencial
    (`youtube_credentials_<nome>.json`). Mudar so o registro deixaria a conta
    apontando para um login que nao existe, e o proximo upload pediria login
    de novo — no meio de uma fila agendada.

    `principal` nao se renomeia: ele mora nos caminhos ANTIGOS
    (`random_builds/.browser_profile/<servico>`, `youtube_credentials.json`),
    que outras partes do projeto ainda leem. Ha teste travando isso.
    """
    if servico not in SERVICOS:
        raise KeyError(f"servico desconhecido: {servico!r}")
    if antigo == PADRAO:
        raise ValueError(
            "`principal` nao pode ser renomeada: ela e o login legado, e "
            "mover a pasta dela perderia as sessoes ja feitas.")
    limpo = _limpar_nome(novo)
    if limpo == PADRAO:
        raise ValueError("nenhuma conta pode se chamar `principal`.")
    dados = estado()
    bloco = dados["servicos"][servico]
    if antigo not in bloco["contas"]:
        raise KeyError(f"{servico} nao tem a conta {antigo!r}")
    if limpo in bloco["contas"] and limpo != antigo:
        raise ValueError(f"{servico} ja tem uma conta chamada {limpo!r}")

    movidos = []
    if SERVICOS[servico].get("tipo") == "oauth":
        origem = runtime_dir() / f"youtube_credentials_{antigo}.json"
        alvo = runtime_dir() / f"youtube_credentials_{limpo}.json"
    else:
        origem = runtime_dir() / "browser_profiles" / f"{servico}__{antigo}"
        alvo = runtime_dir() / "browser_profiles" / f"{servico}__{limpo}"
    if origem.exists() and not alvo.exists():
        alvo.parent.mkdir(parents=True, exist_ok=True)
        origem.rename(alvo)
        movidos.append(str(alvo))

    bloco["contas"] = [limpo if c == antigo else c for c in bloco["contas"]]
    for canal, escolhida in list((bloco.get("ativa") or {}).items()):
        if escolhida == antigo:
            bloco["ativa"][canal] = limpo
    identidades = dados.setdefault("identidades", {}).setdefault(servico, {})
    if antigo in identidades:
        identidades[limpo] = identidades.pop(antigo)
    _gravar(dados)
    return {"servico": servico, "de": antigo, "para": limpo, "movidos": movidos}


def conformidade() -> list[dict]:
    """O que foge do padrao de nomes, com o motivo. Lista vazia = tudo certo."""
    achados = []
    for servico, ficha in SERVICOS.items():
        if not ficha.get("publica"):
            continue                    # login sem destino nao tem o que nomear
        # 1. mesmo destino com dois nomes. `principal` fica de fora: a regra 3
        #    ja diz que ela e o login legado e nao um destino, e ela nao pode
        #    ser renomeada — acusa-la aqui seria um alerta que nunca apaga.
        for identificador, nomes in colisoes(servico).items():
            proprios = [n for n in nomes if n != PADRAO]
            if len(proprios) > 1:
                achados.append({
                    "servico": servico, "tipo": "dois nomes para um destino",
                    "detalhe": f"{identificador} atende por "
                               f"{', '.join(proprios)}"})
        # 2. dois canais do PRODUTO no mesmo lugar. `geral` nao entra: ele nao
        #    e um canal, e a queda de quem nao escolheu — some sozinho quando
        #    builds e historias escolhem, e ate la repetiria o alerta da regra 3.
        for identificador, canais in destinos_repetidos(servico).items():
            produtos = [c for c in canais if c != "geral"]
            if len(produtos) > 1:
                achados.append({
                    "servico": servico, "tipo": "canais no mesmo destino",
                    "detalhe": f"{', '.join(produtos)} publicam em "
                               f"{identificador}"})
        for canal in CANAIS:
            if canal == "geral":
                continue
            nome = ativa(servico, canal)
            # 3. canal que publica caindo na queda padrao
            if not explicita(servico, canal):
                achados.append({
                    "servico": servico, "tipo": "canal sem conta propria",
                    "detalhe": f"{canal} cai em {nome} por falta de escolha"})
            # 4. ninguem consegue dizer PARA ONDE isso vai. O nome e a
            #    primeira resposta; a identidade gravada e a segunda. Sem
            #    nenhuma das duas, so abrindo o navegador — e ai ja e tarde.
            elif (NOMES_SEM_SENTIDO.match(nome)
                  and not identidade(servico, nome).get("rotulo")):
                achados.append({
                    "servico": servico, "tipo": "destino desconhecido",
                    "detalhe": f"{canal} usa a conta {nome!r} e nada registra "
                               "para onde ela publica"})
    return achados


def remover(servico: str, nome: str) -> bool:
    """Tira a conta do registro. NAO apaga perfil nem credencial em disco:
    esquecer e reversivel, apagar login nao."""
    if nome == PADRAO:
        return False
    dados = estado()
    bloco = dados["servicos"].get(servico) or {}
    if nome not in (bloco.get("contas") or []):
        return False
    bloco["contas"].remove(nome)
    for canal, escolhida in list((bloco.get("ativa") or {}).items()):
        if escolhida == nome:
            bloco["ativa"][canal] = PADRAO
    _gravar(dados)
    return True


def escolher(servico: str, canal: str, nome: str) -> None:
    """Define a conta ATIVA daquele servico naquele canal."""
    if servico not in SERVICOS:
        raise KeyError(f"servico desconhecido: {servico!r}")
    if canal not in CANAIS:
        raise KeyError(f"canal desconhecido: {canal!r}")
    dados = estado()
    bloco = dados["servicos"][servico]
    if nome not in bloco["contas"]:
        bloco["contas"].append(nome)
    bloco.setdefault("ativa", {})[canal] = nome
    _gravar(dados)


# ------------------------------------------------------------- resolucao
def perfil(servico: str, canal: str = "geral", conta: str | None = None) -> Path:
    """A pasta de Chrome daquela conta (criada se nao existir).

    A conta `principal` fica no caminho ANTIGO quando ele existe: e o que
    preserva os logins de Digen, PicassoIA e TikTok ja feitos.
    """
    nome = conta or ativa(servico, canal)
    # `sessao_unica`: um login do Google cobre TODOS os canais dele. Aqui a
    # conta nao troca a sessao, so o destino — entao todas compartilham a
    # mesma pasta, e o login e feito uma vez so.
    if (SERVICOS.get(servico) or {}).get("sessao_unica"):
        nome = PADRAO
    legado = (SERVICOS.get(servico) or {}).get("legado")
    if nome == PADRAO and legado is not None:
        caminho = Path(legado)
        if caminho.is_dir() or not _tem_perfil_novo(servico, nome):
            caminho.mkdir(parents=True, exist_ok=True)
            return caminho
    caminho = runtime_dir() / "browser_profiles" / f"{servico}__{nome}"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def _tem_perfil_novo(servico: str, nome: str) -> bool:
    return (runtime_dir() / "browser_profiles" / f"{servico}__{nome}").is_dir()


def credencial_youtube(canal: str = "geral", conta: str | None = None) -> Path:
    """O arquivo de credencial do YouTube daquela conta.

    `principal` continua em `youtube_credentials.json` — o mesmo arquivo que
    a live ja usa. Conta nova ganha sufixo.
    """
    nome = conta or ativa("youtube", canal)
    base = runtime_dir()
    if nome == PADRAO:
        return base / "youtube_credentials.json"
    return base / f"youtube_credentials_{nome}.json"


def tem_login(servico: str, canal: str = "geral", conta: str | None = None) -> bool:
    """Ja existe login/credencial dessa conta? (leitura pura, sem browser)."""
    nome = conta or ativa(servico, canal)
    if SERVICOS.get(servico, {}).get("tipo") == "oauth":
        caminho = credencial_youtube(canal, nome)
        if not caminho.is_file():
            return False
        try:
            with open(caminho, encoding="utf-8-sig") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            return False
        return all(dados.get(c) for c in ("client_id", "client_secret",
                                          "refresh_token"))
    pasta = perfil(servico, canal, nome)
    # Um perfil de Chrome com sessao tem o BANCO DE COOKIES gravado. O teste
    # antigo aceitava "a pasta tem mais de 3 arquivos", e isso e verdade em
    # qualquer perfil que o Chrome abriu uma vez, logado ou nao — foi assim
    # que o painel disse "TikTok pronto" para um canal que nunca logou.
    return (pasta / "Default" / "Network" / "Cookies").is_file() or \
        (pasta / "Default" / "Cookies").is_file()


def explicita(servico: str, canal: str) -> bool:
    """Este CANAL tem conta propria escolhida, ou esta herdando a de outro?

    `ativa()` cai para `geral` e depois para `principal` — otimo para nao
    travar nada, perigoso na hora de PUBLICAR: sem conta propria, o video de
    historias sobe no canal de builds e ninguem percebe. Quem publica
    pergunta isto antes.
    """
    ativa_do_canal = (estado()["servicos"].get(servico, {}) or {}).get("ativa") or {}
    return bool(ativa_do_canal.get(canal))


def destino(servico: str, canal: str) -> dict:
    """Para onde ISTO vai, e se o dono escolheu esse lugar de proposito."""
    nome = ativa(servico, canal)
    quem = identidade(servico, nome)
    return {"conta": nome, "explicita": explicita(servico, canal),
            "tem_login": tem_login(servico, canal),
            # `quem` responde a pergunta que o nome nao responde: para qual
            # canal isto publica de verdade.
            "identidade": quem.get("rotulo") or "",
            "id": quem.get("id") or "",
            "conferido": quem.get("conferido") or "",
            "onde": str(credencial_youtube(canal) if
                        SERVICOS.get(servico, {}).get("tipo") == "oauth"
                        else perfil(servico, canal))}


# --------------------------------------------------------------- identidade
# O problema que isto resolve, em uma frase: ate 01/09/2026 uma "conta" era
# so um NOME com uma pasta de Chrome, e nada dizia para onde ela publicava.
# Duas contas de YouTube com nomes diferentes (`principal` e
# `bem_facil_d_verdade`) apontavam para o MESMO canal `historinhas` — e nao
# havia como perceber isso sem abrir o navegador.
#
# Isto vale mais ainda no caso real do Adrian: os canais dele sao TODOS da
# mesma conta Google. O que separa um do outro nao e o login — e o CANAL. Sem
# guardar qual, "conta" vira um apelido sem significado.
def identidade(servico: str, conta: str) -> dict:
    """O que esta conta e DE VERDADE (rotulo, id, quando foi conferido)."""
    bloco = (_ler().get("identidades") or {}).get(servico) or {}
    return dict(bloco.get(conta) or {})


def identificar(servico: str, conta: str, *, rotulo: str = "",
                identificador: str = "", extra: dict | None = None) -> dict:
    """Grava quem e a conta. Chamado por quem CONSEGUE perguntar ao site."""
    from datetime import datetime

    dados = _ler()
    bloco = dados.setdefault("identidades", {}).setdefault(servico, {})
    registro = {
        "rotulo": rotulo or bloco.get(conta, {}).get("rotulo", ""),
        "id": identificador or bloco.get(conta, {}).get("id", ""),
        "conferido": datetime.now().isoformat(timespec="seconds"),
    }
    registro.update(extra or {})
    bloco[conta] = registro
    _gravar(dados)
    return registro


def destinos_repetidos(servico: str) -> dict:
    """{id: [canais do projeto]} quando dois canais publicam no MESMO lugar.

    Diferente de `colisoes`, que olha duas CONTAS apontando para o mesmo id.
    A pergunta aqui e a que importa na hora de publicar: 'builds' e
    'historias' vao parar no mesmo canal do YouTube? Foi o estado real em
    01/09/2026 — os dois caiam no canal PESSOAL do Adrian, porque nenhum dos
    dois tinha escolhido canal e a queda padrao leva os dois ao mesmo lugar.
    """
    por_id = {}
    for canal in CANAIS:
        quem = identidade(servico, ativa(servico, canal))
        identificador = quem.get("id") or ""
        if identificador:
            por_id.setdefault(identificador, []).append(canal)
    return {i: c for i, c in por_id.items() if len(c) > 1}


def colisoes(servico: str) -> dict:
    """{id: [contas]} para os ids com MAIS DE UMA conta apontando.

    E a pergunta "essas duas contas sao a mesma coisa?" respondida com dado
    em vez de memoria.
    """
    porid: dict = {}
    for conta, dados in ((_ler().get("identidades") or {})
                         .get(servico) or {}).items():
        chave = dados.get("id")
        if chave:
            porid.setdefault(chave, []).append(conta)
    return {k: sorted(v) for k, v in porid.items() if len(v) > 1}


def escopo_youtube(canal: str = "geral", conta: str | None = None) -> str:
    try:
        with open(credencial_youtube(canal, conta), encoding="utf-8-sig") as fh:
            return str(json.load(fh).get("escopo") or "")
    except (OSError, ValueError):
        return ""


def oauth_vivo(canal: str = "geral", conta: str | None = None) -> dict:
    """A credencial OAuth AINDA FUNCIONA? Pergunta ao Google (usa rede).

    `tem_login` responde outra coisa: se o ARQUIVO existe e tem os campos. Isso
    e leitura pura, e e o certo para desenhar uma tela — mas mente quando o
    refresh_token foi revogado ou expirou. Medido em 08/09/2026: a auditoria
    dizia "login ok" para uma credencial que o Google recusava com
    `invalid_grant`, e as metricas estavam paradas havia seis dias sem que
    nada avisasse.

    Fica separada de proposito: quem desenha tela nao deve chamar rede, e quem
    audita deve.
    """
    caminho = credencial_youtube(canal, conta)
    if not caminho.is_file():
        return {"ok": False, "motivo": "nao existe arquivo de credencial"}
    try:
        from .publicar.youtube import carregar_credenciais, token_de_acesso
        credenciais = carregar_credenciais(caminho)
        if credenciais is None:
            return {"ok": False,
                    "motivo": "o arquivo existe mas nao tem client_id, "
                              "client_secret e refresh_token"}
        token_de_acesso(credenciais)
    except Exception as exc:                                   # noqa: BLE001
        texto = str(exc)
        if "invalid_grant" in texto:
            return {"ok": False, "motivo": "o Google revogou ou expirou o "
                                           "refresh_token: precisa autorizar "
                                           "de novo"}
        return {"ok": False, "motivo": texto[:180]}
    faltando = [e for e in ("yt-analytics.readonly",)
                if e not in escopo_youtube(canal, conta)]
    if faltando:
        return {"ok": True, "motivo": "funciona, mas sem o escopo "
                                      + ", ".join(faltando)
                                      + " (retencao nao vem)"}
    return {"ok": True, "motivo": ""}


def resumo() -> list:
    """Uma linha por servico x canal: o que a tela do painel desenha."""
    saida = []
    for servico, dados in SERVICOS.items():
        for canal in ("builds", "historias"):
            nome = ativa(servico, canal)
            saida.append({
                "servico": servico, "rotulo": dados["rotulo"],
                "tipo": dados["tipo"], "publica": dados.get("publica", False),
                "canal": canal, "conta": nome,
                "contas": contas(servico),
                "logado": tem_login(servico, canal),
                "onde": str(credencial_youtube(canal) if dados["tipo"] == "oauth"
                            else perfil(servico, canal)),
            })
    return saida


__all__ = ["CANAIS", "PADRAO", "SERVICOS", "adicionar", "ativa", "contas",
           "credencial_youtube", "escolher", "escopo_youtube", "estado",
           "perfil", "remover", "resumo", "runtime_dir", "tem_login"]
