# -*- coding: utf-8 -*-
"""Publicar no YouTube pela API oficial (Data API v3, upload resumable).

Por que API e não navegador: aqui existe caminho oficial e o projeto já tem
metade dele pronto — o OAuth do chat da live (`neural_fights.tools.
youtube_oauth`) guarda client_id/secret/refresh_token. Falta só o escopo de
upload, que é uma re-autorização de um clique (`--com-upload`). Automação de
navegador no YouTube seria mais frágil e sem motivo.

O upload é RESUMÁVEL de propósito: um mp4 de 30 MB numa conexão doméstica
falha no meio de vez em quando, e o protocolo resumable retoma de onde parou
em vez de recomeçar.

Padrão de visibilidade: PRIVADO. O vídeo sobe pronto e quem decide publicar
é o dono do canal, no Studio — publicar sozinho é irreversível e não é
decisão de ferramenta.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
ESCOPO_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"

# Pedaço de cada PUT do upload resumable. Múltiplo de 256 KiB (exigência da
# API); 8 MiB dá progresso visível sem transformar o upload em mil requests.
BLOCO = 8 * 1024 * 1024

VISIBILIDADES = ("private", "unlisted", "public")


def canais_da_conta(canal: str = "builds") -> list:
    """TODOS os canais que este login controla (id, nome, videos).

    Existe porque a pergunta "quais canais eu tenho?" nao tinha resposta
    dentro do projeto — e sem ela nao da para mapear canal do YouTube ->
    canal do projeto sem abrir o navegador e olhar.
    """
    import requests

    credenciais = carregar_credenciais(caminho_credenciais(canal), canal)
    token = token_de_acesso(credenciais)
    saida, pagina = [], None
    while True:
        resposta = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet,statistics", "mine": "true",
                    "maxResults": 50, "pageToken": pagina},
            headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if not resposta.ok:
            raise PublicacaoFalhou(
                f"nao consegui listar os canais ({resposta.status_code}): "
                f"{resposta.text[:200]}")
        dados = resposta.json()
        for item in dados.get("items") or []:
            saida.append({
                "id": item.get("id"),
                "nome": item.get("snippet", {}).get("title", ""),
                "criado": item.get("snippet", {}).get("publishedAt", "")[:10],
                "videos": item.get("statistics", {}).get("videoCount"),
                "inscritos": item.get("statistics", {}).get("subscriberCount"),
            })
        pagina = dados.get("nextPageToken")
        if not pagina:
            break
    return saida


def modo(config: dict | None = None) -> str:
    """"navegador" (padrao) ou "api" — como este projeto PUBLICA no YouTube.

    Decisao do Adrian em 01/09/2026, depois de a API recusar por cota
    enquanto o Studio aceitava: publicar e sempre por navegador. A API
    continua aqui, e continua util, mas so para LER — metricas de retencao,
    views e a identidade do canal, que o navegador nao entrega.
    """
    if config is None:
        try:
            from . import catalogo
            config = catalogo.carregar_config()
        except Exception:
            config = {}
    # O `or` antes do str() importa: `str(None)` e a string "none", que e
    # verdadeira e passaria como se fosse um modo valido.
    escolhido = ((config or {}).get("youtube") or {}).get("modo") or "navegador"
    return str(escolhido).strip().lower() or "navegador"


def publicar_como_configurado(video, *, log=None, config=None, **kw) -> str:
    """Publica pelo caminho escolhido no config. E a porta que todos usam.

    O que ela resolve, alem de escolher o caminho: os dois lados FALAM
    DIFERENTE. A API reporta bytes (`progresso(enviado, total)`) e o
    navegador reporta passos (`progresso(texto)`). Adaptar isso aqui e o
    que permite quem chama nao precisar saber por onde o video foi — ela
    recebe `log(texto)`, uma linha por vez, e pronto.
    """
    fala = log or (lambda _linha: None)
    caminho = modo(config)
    fala(f"[youtube] publicando por {caminho.upper()}")
    if caminho == "api":
        return publicar(
            video, config=config,
            progresso=lambda enviado, total: fala(
                f"  {enviado / 1e6:6.1f} / {total / 1e6:.1f} MB"),
            **kw)
    from . import youtube_web
    return youtube_web.publicar(
        video, config=config, postar=True,
        progresso=lambda texto: fala(f"  {texto}"), **kw)


def identificar_canal(canal: str = "builds") -> dict:
    """Pergunta ao YouTube QUAL canal este token controla, e grava.

    Sem isto, duas contas com nomes diferentes podem apontar para o mesmo
    canal por meses sem ninguem perceber — foi o que aconteceu.
    """
    import requests

    from .. import contas

    credenciais = carregar_credenciais(caminho_credenciais(canal), canal)
    token = token_de_acesso(credenciais)
    resposta = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet,statistics", "mine": "true"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if not resposta.ok:
        raise PublicacaoFalhou(
            f"nao consegui identificar o canal ({resposta.status_code}): "
            f"{resposta.text[:200]}")
    itens = resposta.json().get("items") or []
    if not itens:
        raise PublicacaoFalhou("este token nao controla canal nenhum.")
    canal_api = itens[0]
    nome = contas.ativa("youtube", canal)
    return contas.identificar(
        "youtube", nome,
        rotulo=canal_api.get("snippet", {}).get("title", ""),
        identificador=canal_api.get("id", ""),
        extra={"videos": canal_api.get("statistics", {}).get("videoCount")})


def cota_disponivel(canal: str = "builds", config: dict | None = None):
    """(True/False, motivo): da para subir video AGORA?

    Pergunta ao YouTube em vez de adivinhar. O 400 de cota chega na hora dos
    METADADOS, antes de qualquer byte — entao abrir uma sessao de upload e
    NAO enviar nada responde a pergunta sem criar video nenhum.

    Existe porque descobrir o teto no meio de uma serie e caro: a publicacao
    ja gastou minutos de vistoria e render, e as partes seguintes cairiam no
    mesmo erro uma a uma.
    """
    import requests

    try:
        credenciais = carregar_credenciais(caminho_credenciais(canal), canal)
        token = token_de_acesso(credenciais)
    except Exception as exc:
        return False, f"nao consegui autenticar: {exc}"

    corpo = {"snippet": {"title": "sonda de cota", "categoryId": "24"},
             "status": {"privacyStatus": "private",
                        "selfDeclaredMadeForKids": False}}
    try:
        r = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"part": "snippet,status", "uploadType": "resumable"},
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Length": "1048576",
                     "X-Upload-Content-Type": "video/mp4"},
            data=json.dumps(corpo).encode("utf-8"), timeout=60)
    except Exception as exc:
        return False, f"rede: {exc}"
    if r.ok:
        # A sessao aberta e abandonada: sem bytes, nenhum video nasce.
        return True, "ha cota"
    bruto = r.text or ""
    if "exceeded the number of videos" in bruto or "uploadLimitExceeded" in bruto:
        return False, MENSAGEM_COTA
    return False, f"o YouTube recusou ({r.status_code}): {bruto[:200]}"


class CotaEsgotada(RuntimeError):
    """A conta bateu o teto DIARIO de uploads do YouTube.

    Nao e defeito nem recusa do video: e um limite por conta, que zera
    sozinho em algumas horas. Merece excecao propria porque a resposta e
    diferente de qualquer outro erro — nao adianta tentar de novo agora, e
    NAO adianta tentar a proxima parte da serie (ela cairia no mesmo teto).
    """


# A unica coisa que o dono ve quando isso acontece. Fica aqui, e nao dentro
# da funcao, para ser lida por teste — e para nao virar duas mensagens
# diferentes no dia em que outro caminho precisar dela.
MENSAGEM_COTA = (
    "a conta bateu o teto de uploads POR API do YouTube.\n"
    "\n"
    "O que foi MEDIDO em 01/09/2026, e vale saber antes de tentar de novo:\n"
    "  - o teto da API e um balde SEPARADO do upload pelo navegador. Subir "
    "video pelo YouTube Studio continua funcionando enquanto a API recusa;\n"
    "  - ele NAO zera na virada do dia: o dia ja tinha virado no horario do "
    "Pacifico e a API continuava recusando;\n"
    "  - canal novo e o caso classico. O canal em uso tinha UM dia de vida e "
    "11 uploads por API quando o teto apareceu.\n"
    "\n"
    "O que fazer:\n"
    "  - verificar o canal (YouTube Studio > Configuracoes > Canal > "
    "Verificacao por telefone) — e o que mais aumenta o limite;\n"
    "  - esperar (horas, as vezes um dia) e rodar de novo: o que ja subiu "
    "esta registrado e a serie continua de onde parou, sem republicar;\n"
    "  - enquanto isso, `main.py publicar <id> --exportar` deixa o mp4 com "
    "nome legivel e o texto pronto para subir na mao;\n"
    "  - cortar para Shorts DOBRA os uploads (uma parte longa vira dois "
    "videos). `shorts_max_s: 0` em config/publicacao.json gasta metade."
)


class PublicacaoFalhou(RuntimeError):
    """Erro que o painel mostra como está: sem traceback, com o motivo."""


@dataclass
class Credenciais:
    client_id: str
    client_secret: str
    refresh_token: str
    escopo: str = ""

    @property
    def tem_upload(self) -> bool:
        """O token autoriza publicar?

        Credencial antiga (só leitura do chat) não tem o campo `escopo`: aí
        não dá para afirmar que tem upload — e é melhor pedir a
        re-autorização de graça do que descobrir com 403 no fim do envio.
        """
        return ESCOPO_UPLOAD in (self.escopo or "")


def caminho_credenciais(canal: str = "builds") -> Path:
    """O arquivo de credencial da conta de YouTube ATIVA naquele canal."""
    try:
        from ..contas import credencial_youtube
        return credencial_youtube(canal)
    except Exception:
        from neural_fights.data.database import RUNTIME_DIR
        return Path(RUNTIME_DIR) / "youtube_credentials.json"


def carregar_credenciais(caminho: Path | None = None,
                         canal: str = "builds") -> Credenciais | None:
    caminho = caminho or caminho_credenciais(canal)
    try:
        with open(caminho, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
    except (OSError, ValueError):
        return None
    if not all(dados.get(c) for c in ("client_id", "client_secret",
                                      "refresh_token")):
        return None
    return Credenciais(dados["client_id"], dados["client_secret"],
                       dados["refresh_token"], dados.get("escopo", ""))


def token_de_acesso(credenciais: Credenciais) -> str:
    import requests

    resposta = requests.post(TOKEN_URL, timeout=30, data={
        "client_id": credenciais.client_id,
        "client_secret": credenciais.client_secret,
        "refresh_token": credenciais.refresh_token,
        "grant_type": "refresh_token",
    })
    if not resposta.ok:
        raise PublicacaoFalhou(
            f"o Google recusou o refresh_token ({resposta.status_code}): "
            f"{resposta.text[:180]}")
    token = resposta.json().get("access_token")
    if not token:
        raise PublicacaoFalhou("o Google não devolveu access_token.")
    return token


def _corpo(video, config: dict, visibilidade: str,
           agendar_para: str | None = None) -> dict:
    ajustes = config.get("youtube", {})
    if agendar_para:
        # O YouTube so agenda o que esta privado: com qualquer outra
        # visibilidade ele ignora o publishAt em silencio.
        visibilidade = "private"
    corpo = {
        "snippet": {
            # 100 caracteres é o teto do YouTube; cortar aqui evita o 400.
            "title": video.titulo[:100],
            "description": video.descricao_completa[:4900],
            "tags": [t.lstrip("#") for t in video.hashtags][:15],
            "categoryId": str(ajustes.get("categoria", "20")),
        },
        "status": {
            "privacyStatus": visibilidade,
            "selfDeclaredMadeForKids": bool(ajustes.get("para_criancas", False)),
        },
    }
    if agendar_para:
        corpo["status"]["publishAt"] = agendar_para
    return corpo


def publicar(video, *, visibilidade: str | None = None,
             config: dict | None = None, progresso=None,
             canal: str = "builds", agendar_para: str | None = None) -> str:
    """Sobe o vídeo e devolve a URL. `progresso(enviado, total)` é opcional.

    `canal` escolhe a CONTA (o registro de contas guarda qual é a ativa).
    `agendar_para` (ISO 8601, UTC) publica sozinho naquele instante: numa
    série, soltar oito partes no mesmo minuto mata a sequência.
    """
    import requests

    from . import catalogo

    config = catalogo.carregar_config() if config is None else config
    visibilidade = (visibilidade
                    or config.get("youtube", {}).get("visibilidade", "private"))
    if visibilidade not in VISIBILIDADES:
        raise PublicacaoFalhou(
            f"visibilidade inválida: {visibilidade!r} "
            f"(use {', '.join(VISIBILIDADES)})")

    credenciais = carregar_credenciais(canal=canal)
    if credenciais is None:
        raise PublicacaoFalhou(
            f"sem credenciais do YouTube para o canal '{canal}'. No painel: "
            "pagina Contas -> escolha a conta e clique em Autorizar.")
    if not credenciais.tem_upload:
        raise PublicacaoFalhou(
            "as credenciais atuais são só de LEITURA (chat da live). Rode o "
            "OAuth de novo com --com-upload — o mesmo arquivo passa a servir "
            "para os dois.")

    caminho = Path(video.caminho)
    if not caminho.is_file():
        raise PublicacaoFalhou(f"arquivo sumiu: {caminho}")
    total = caminho.stat().st_size
    token = token_de_acesso(credenciais)

    # 1) abre a sessão resumable com os metadados
    inicio = requests.post(
        UPLOAD_URL, timeout=60,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(total),
                 "X-Upload-Content-Type": "video/mp4"},
        data=json.dumps(_corpo(video, config, visibilidade,
                               agendar_para)).encode("utf-8"))
    if not inicio.ok:
        bruto = inicio.text or ""
        if "exceeded the number of videos" in bruto or (
                "uploadLimitExceeded" in bruto):
            # O YouTube devolve isto como 400, junto de erros de metadado —
            # mas a causa e outra e a acao tambem. Sem separar, a mensagem
            # que chegava era um JSON cru de 200 caracteres.
            raise CotaEsgotada(MENSAGEM_COTA)
        raise PublicacaoFalhou(
            f"o YouTube recusou os metadados ({inicio.status_code}): "
            f"{bruto[:200]}")
    sessao = inicio.headers.get("Location")
    if not sessao:
        raise PublicacaoFalhou("o YouTube não devolveu a URL de upload.")

    # 2) manda o arquivo em blocos; um bloco que falha é reenviado, o resto
    #    já entregue permanece no servidor (é para isso que serve resumable).
    enviado = 0
    with open(caminho, "rb") as arquivo:
        while enviado < total:
            pedaco = arquivo.read(BLOCO)
            if not pedaco:
                break
            fim = enviado + len(pedaco) - 1
            resposta = requests.put(
                sessao, data=pedaco, timeout=600,
                headers={"Content-Length": str(len(pedaco)),
                         "Content-Range": f"bytes {enviado}-{fim}/{total}"})
            if resposta.status_code in (200, 201):
                dados = resposta.json()
                video_id = dados.get("id")
                if progresso:
                    progresso(total, total)
                if not video_id:
                    raise PublicacaoFalhou(
                        f"upload terminou sem id: {resposta.text[:180]}")
                url = f"https://youtu.be/{video_id}"
                # Registro do que subiu: e o que liga o mp4 a metrica depois
                # (`main.py metricas`). Falhar aqui nao desfaz o upload.
                if canal == "builds":
                    # So o canal de builds tem metrica aqui. Histórias reusa
                    # este módulo pela ponte `rb` e tem registro próprio — sem
                    # esta guarda, todo upload de história entrava no
                    # `publicados.jsonl` de builds e a métrica ia buscar
                    # retenção de um vídeo que não é deste canal.
                    try:
                        from . import metricas
                        metricas.registrar_publicacao(
                            video, url, "youtube",
                            {"visibilidade": visibilidade})
                    except Exception as exc:  # pragma: no cover - so log
                        print(f"[publicar] registro falhou: {exc}")
                try:
                    from .. import atividade
                    atividade.registrar("publicacao", "ok",
                                        f"YouTube: {video.titulo[:70]}", canal)
                except Exception:
                    pass
                return url
            if resposta.status_code != 308:  # 308 = continue
                raise PublicacaoFalhou(
                    f"falha no envio ({resposta.status_code}): "
                    f"{resposta.text[:200]}")
            # O servidor diz até onde recebeu; é dele que a retomada parte.
            faixa = resposta.headers.get("Range")
            enviado = int(faixa.split("-")[-1]) + 1 if faixa else fim + 1
            arquivo.seek(enviado)
            if progresso:
                progresso(enviado, total)
    raise PublicacaoFalhou("o arquivo acabou antes de o YouTube confirmar.")


def main(argv=None) -> int:
    """CLI: `python -m src.publicar.youtube <video_id> [--publico]`."""
    import argparse

    from . import catalogo

    parser = argparse.ArgumentParser(
        description="Publica um vídeo do catálogo no YouTube (privado por padrão)")
    parser.add_argument("video_id", help="id do catálogo (ver `main.py publicar --listar`)")
    parser.add_argument("--visibilidade", choices=VISIBILIDADES, default=None)
    args = parser.parse_args(argv)

    video = catalogo.por_id(args.video_id)
    if video is None:
        print(f"vídeo não encontrado: {args.video_id}")
        return 1
    print(f"enviando {video.caminho.name} ({video.bytes / 1e6:.1f} MB)...")

    def progresso(enviado, total):
        print(f"  {enviado / 1e6:6.1f} / {total / 1e6:.1f} MB", flush=True)

    try:
        url = publicar(video, visibilidade=args.visibilidade,
                       progresso=progresso)
    except PublicacaoFalhou as exc:
        print(f"FALHOU: {exc}")
        return 1
    print(f"pronto: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Credenciais", "PublicacaoFalhou", "VISIBILIDADES",
           "carregar_credenciais", "publicar"]
