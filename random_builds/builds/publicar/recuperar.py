# -*- coding: utf-8 -*-
"""Devolver ao ar o que ja esta no canal e ficou privado por defeito nosso.

MEDIDO EM 17/09/2026, canal de builds: 134 videos na playlist de envios, 51
privados. Separando por titulo contra os publicos:

  29  tem gemeo publico com o MESMO titulo — sao os rascunhos da fabrica que
      fechou em 811cf5a (clique sem confirmacao nao gravava linha, o video
      voltava na fila e subia de novo). Publicar estes DUPLICA o canal.
  16  sao conteudo distinto que nunca foi ao ar. Todos inteiros: 53 s a
      1 m 42 s, descricao de 156 a 267 caracteres, capa presente. O mais
      velho esperava desde 31/08.
   2  sao envios de teste meus, sem descricao nenhuma.
   4  restantes sao dois pares que repetem titulo entre si (principal e
      variante do mesmo build).

O canal de historias nao tem este problema: 88 publicos, 6 privados, e dois
deles sao builds que cairam no canal errado — esses ficam privados mesmo.

POR QUE UM MODULO SEPARADO do `youtube.py`: aquele modulo SOBE video, e o
caminho de subida e o mais exercitado do projeto. Recuperacao le o canal e
muda visibilidade — nao toca em arquivo, nao gasta cota de upload, e erra de
outros jeitos. Misturar os dois faria um `--recuperar` quebrado derrubar a
publicacao normal.

O ESCOPO E OUTRO, e esta e a razao de isto nao existir antes: `videos.update`
exige `https://www.googleapis.com/auth/youtube`, e a credencial tinha so
`youtube.readonly` + `youtube.upload` + `yt-analytics.readonly`. Sem ele a
resposta e 403, e a mensagem daqui diz exatamente qual comando corrige. NAO
existe plano B pelo Studio: automacao de navegador para mudar visibilidade em
lote e frágil do mesmo jeito que vem quebrando, e o erro dela seria silencioso.
"""
from __future__ import annotations

import json

from . import titulos
from .youtube import (Credenciais, PublicacaoFalhou, caminho_credenciais,
                      carregar_credenciais, token_de_acesso)

API = "https://www.googleapis.com/youtube/v3/"
ESCOPO_EDICAO = "https://www.googleapis.com/auth/youtube"

COMO_AUTORIZAR = (
    "falta o escopo de edicao ({escopo}).\n"
    "A credencial atual so le e sobe; mudar a visibilidade de um video ja\n"
    "enviado e outra permissao, e ela se pede uma vez no navegador:\n"
    "\n"
    "    python -m neural_fights.tools.youtube_oauth \\\n"
    "        --conta {conta} --com-upload --com-analytics --com-edicao\n"
    "\n"
    "Enquanto isso NAO tento pelo Studio: automacao de navegador para mudar\n"
    "visibilidade em lote erra em silencio, e este e o tipo de erro que so\n"
    "aparece depois, no canal."
)


class FaltaEscopo(PublicacaoFalhou):
    """A credencial nao autoriza `videos.update`. Erro proprio porque a
    resposta nao e "tentar de novo": e uma autorizacao que so o dono da conta
    consegue dar, uma vez, no navegador."""


def pode_editar(credenciais: Credenciais | None) -> bool:
    """A credencial autoriza mudar visibilidade?

    PELO NOME INTEIRO DO ESCOPO, e nunca por trecho. `.../auth/youtube` esta
    DENTRO de `.../auth/youtube.readonly` e de `.../auth/youtube.upload`:
    escrito com `in`, este guarda daria positivo para a credencial de hoje —
    que so le e sobe — e o 403 apareceria no meio do lote, com metade dos
    videos recuperados e nenhuma mensagem util. `contas.tem_escopo` ja
    responde esta pergunta separando por espaco; e a mesma pergunta, entao e
    a mesma funcao.

    Credencial sem o campo `escopo` (as antigas) devolve False: pedir a
    reautorizacao de graca e melhor que descobrir com 403 no meio do lote.
    """
    from ..contas import tem_escopo
    return bool(credenciais) and tem_escopo(credenciais.escopo, ESCOPO_EDICAO)


def _token(canal: str, *, editar: bool = True) -> str:
    """O token, exigindo o escopo de edicao SO quando se vai editar.

    LER NAO PRECISA DO ESCOPO DE ESCRITA, e cobrar isso era um defeito de
    desenho que so apareceu rodando: `--ver` existe exatamente para alguem
    olhar a lista ANTES de autorizar qualquer coisa, e ele recusava a
    listagem pedindo a autorizacao que a listagem ia ajudar a decidir.
    """
    cred = carregar_credenciais(caminho_credenciais(canal), canal)
    if cred is None:
        raise PublicacaoFalhou(f"sem credencial da API para o canal {canal}.")
    if editar and not pode_editar(cred):
        try:
            from ..contas import ativa
            conta = ativa("youtube", canal)
        except Exception:                                      # noqa: BLE001
            conta = canal
        raise FaltaEscopo(COMO_AUTORIZAR.format(escopo=ESCOPO_EDICAO,
                                                conta=conta))
    return token_de_acesso(cred)


def _get(token: str, caminho: str, **params) -> dict:
    import requests
    r = requests.get(API + caminho, timeout=60, params=params,
                     headers={"Authorization": f"Bearer {token}"})
    if not r.ok:
        raise PublicacaoFalhou(
            f"o YouTube recusou {caminho} ({r.status_code}): {r.text[:200]}")
    return r.json()


class CanalErrado(PublicacaoFalhou):
    """A credencial abriu um canal que nao e o esperado. Erro proprio porque
    a reacao e parar tudo: recuperar aqui mexeria em video de outro canal."""


def conferir_o_canal(canal: str, aberto: dict) -> str:
    """O canal que a credencial abriu e o que este projeto espera?

    O LOGIN E REFEITO POR UMA PESSOA, numa tela do Google que lista todos os
    canais dela, e escolher o errado ali e um clique — aconteceu em
    17/09/2026. Depois disso a credencial funciona perfeitamente: autentica,
    lista, pagina. So que lista OUTRO canal. E a recuperacao, que so olha
    "privado sem gemeo publico", acharia dezenas de candidatos no canal
    pessoal dele e os tornaria publicos.

    A comparacao e contra a IDENTIDADE JA GRAVADA (`contas.identidade`), e
    nao contra um id escrito aqui: o registro cobre todos os canais, e e o
    mesmo que a auditoria de contas mantem. Sem id gravado nao da para
    afirmar nada, e ai a resposta e parar — "nao sei em que canal estou" nao
    pode virar "deve ser o certo".
    """
    from ..contas import ativa, identidade
    try:
        conta = ativa("youtube", canal)
    except Exception:                                          # noqa: BLE001
        conta = ""
    esperado = str((identidade("youtube", conta) or {}).get("id") or "")
    achado = str(aberto.get("id") or "")
    if not esperado:
        raise CanalErrado(
            f"nao sei qual e o canal da conta '{conta or canal}': nao ha "
            f"identidade gravada. Rode `python -m ferramentas.auditoria_contas`"
            f" para conferir e gravar antes de mexer em video nenhum.")
    if achado != esperado:
        rotulo = (aberto.get("snippet") or {}).get("title", "?")
        raise CanalErrado(
            f"a credencial da conta '{conta}' abriu o canal {achado} "
            f"('{rotulo}'), e este projeto espera {esperado}. NAO mexo em "
            f"nada: o login provavelmente escolheu o canal errado na tela do "
            f"Google. Refaca com `youtube_oauth --conta {conta}` e escolha o "
            f"canal certo.")
    return achado


def videos_do_canal(canal: str = "builds", token: str | None = None) -> list:
    """Tudo o que esta na playlist de envios, com estado. So leitura.

    Paginado de verdade: o canal passou de 50 faz tempo, e uma primeira
    pagina lida como "o canal inteiro" faria a recuperacao achar que os
    videos antigos nao existem.
    """
    token = token or _token(canal, editar=False)
    canais = _get(token, "channels", part="contentDetails,snippet",
                  mine="true")
    itens = canais.get("items") or []
    if not itens:
        raise PublicacaoFalhou("a credencial nao controla canal nenhum.")
    conferir_o_canal(canal, itens[0])
    lista = itens[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, pagina = [], None
    while True:
        extra = {"pageToken": pagina} if pagina else {}
        p = _get(token, "playlistItems", part="contentDetails",
                 playlistId=lista, maxResults=50, **extra)
        ids += [i["contentDetails"]["videoId"] for i in p.get("items", [])]
        pagina = p.get("nextPageToken")
        if not pagina:
            break

    fora = []
    for i in range(0, len(ids), 50):
        lote = _get(token, "videos", part="status,snippet,contentDetails",
                    id=",".join(ids[i:i + 50]), maxResults=50)
        for v in lote.get("items", []):
            fora.append({
                "id": v["id"],
                "titulo": v["snippet"].get("title", ""),
                "descricao": v["snippet"].get("description", "") or "",
                "quando": v["snippet"].get("publishedAt", "")[:19],
                "privacidade": v["status"].get("privacyStatus", ""),
                "upload": v["status"].get("uploadStatus", ""),
                "duracao": v["contentDetails"].get("duration", ""),
            })
    return fora


def recuperaveis(canal: str = "builds", token: str | None = None,
                 conhecidos=None) -> list:
    """Os privados que DEVEM voltar ao ar, na ordem em que foram enviados.

    Cada crivo aqui existe por um caso medido, e a ordem importa:

    1. so `private`. `unlisted` foi escolha de alguem, nao defeito nosso.
    2. so `processed`. Publicar o que ainda processa foi o defeito de ontem
       (98e3737); repeti-lo na recuperacao seria comico.
    3. descricao vazia sai. Sao envios de teste — video de produto nunca sai
       daqui sem descricao, e os dois casos no canal eram meus.
    4. titulo que JA tem irmao publico sai. Sao os 29 rascunhos gemeos, e
       publica-los duplicaria o canal — o oposto do que isto conserta.
    5. titulo repetido DENTRO dos privados sai, ficando UM. Sao os pares
       principal/variante do mesmo build: a variante existe para assumir
       quando o principal cai, e aqui o principal nao caiu.

    `conhecidos` sao os ids do YouTube que quem chama consegue identificar no
    ledger. No desempate do item 5 eles vem primeiro, e nao o mais antigo:
    dos dois pares que existem no canal, um tem a variante no ledger e o
    principal fora dele — escolher pela data pegaria justamente o video de
    que nao da para escrever linha coerente, e a recuperacao ficaria sem
    registro do que fez. Sem a lista, vale o mais antigo: ele espera ha mais
    tempo.
    """
    todos = videos_do_canal(canal, token)
    conhecidos = set(conhecidos or ())
    publicos = {titulos.chave(v["titulo"]) for v in todos
                if v["privacidade"] == "public" and v["titulo"]}
    validos = []
    for v in todos:
        if v["privacidade"] != "private" or v["upload"] != "processed":
            continue
        if not v["descricao"].strip() or not v["titulo"].strip():
            continue
        chave = titulos.chave(v["titulo"])
        if not chave or chave in publicos:
            continue
        validos.append((chave, v))

    escolhido = {}
    for chave, v in sorted(validos,
                           key=lambda cv: (cv[1]["id"] not in conhecidos,
                                           cv[1]["quando"])):
        escolhido.setdefault(chave, v)
    return sorted(escolhido.values(), key=lambda v: v["quando"])


def tornar_publico(video_id: str, canal: str = "builds",
                   token: str | None = None) -> dict:
    """Privado -> publico, e CONFERE no canal que ficou.

    `videos.update` SUBSTITUI a parte inteira que se manda. Mandar apenas
    `{"privacyStatus": "public"}` apagaria `selfDeclaredMadeForKids`,
    `license`, `embeddable` e `publicStatsViewable` — o video voltaria ao ar
    com a declaracao de publico infantil zerada, que e uma questao legal, nao
    um detalhe. Entao: le o `status` atual, troca UM campo e devolve o resto
    igual.

    E confere depois. "A API respondeu 200" e a mesma classe de prova que
    "o botao estava habilitado": diz que o pedido foi aceito, nao que o
    estado mudou. A unica resposta que vale e reler o video.
    """
    import requests
    token = token or _token(canal)
    # A CONFERENCIA DO CANAL SE REFAZ AQUI, e nao so na listagem: esta e a
    # chamada que muda alguma coisa, e ela pode ser feita direto (pelo app,
    # por um `-c`, por uma rodada futura) sem passar por `recuperaveis`.
    # Guarda que depende de outra funcao ter sido chamada antes nao e guarda.
    meu = _get(token, "channels", part="snippet", mine="true")
    conferir_o_canal(canal, (meu.get("items") or [{}])[0])
    atual = _get(token, "videos", part="status", id=video_id)
    itens = atual.get("items") or []
    if not itens:
        raise PublicacaoFalhou(f"{video_id}: o canal nao tem esse video.")
    status = dict(itens[0]["status"])
    antes = status.get("privacyStatus", "")
    if antes == "public":
        return {"id": video_id, "antes": antes, "depois": "public",
                "mudou": False, "motivo": "ja estava publico"}
    status["privacyStatus"] = "public"
    # `status` do GET traz campos que o PUT recusa; mandar de volta o que ele
    # nao aceita da 400 e nao muda nada.
    for campo in ("uploadStatus", "privacyStatusReason", "rejectionReason",
                  "failureReason", "publishAt"):
        status.pop(campo, None)

    r = requests.put(API + "videos", timeout=60, params={"part": "status"},
                     headers={"Authorization": f"Bearer {token}",
                              "Content-Type": "application/json"},
                     data=json.dumps({"id": video_id,
                                      "status": status}).encode("utf-8"))
    if r.status_code == 403:
        raise FaltaEscopo(COMO_AUTORIZAR.format(escopo=ESCOPO_EDICAO,
                                                conta=canal)
                          + f"\n\nO YouTube respondeu: {r.text[:200]}")
    if not r.ok:
        raise PublicacaoFalhou(
            f"{video_id}: o YouTube recusou ({r.status_code}): {r.text[:200]}")

    confere = _get(token, "videos", part="status", id=video_id)
    itens = confere.get("items") or []
    depois = (itens[0]["status"].get("privacyStatus", "")
              if itens else "nao consegui reler")
    return {"id": video_id, "antes": antes, "depois": depois,
            "mudou": depois == "public",
            "motivo": "" if depois == "public" else
                      f"pedi publico e o canal diz '{depois}'"}
