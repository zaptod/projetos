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


def caminho_credenciais() -> Path:
    from neural_fights.data.database import RUNTIME_DIR

    return Path(RUNTIME_DIR) / "youtube_credentials.json"


def carregar_credenciais(caminho: Path | None = None) -> Credenciais | None:
    caminho = caminho or caminho_credenciais()
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


def _corpo(video, config: dict, visibilidade: str) -> dict:
    ajustes = config.get("youtube", {})
    return {
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


def publicar(video, *, visibilidade: str | None = None,
             config: dict | None = None, progresso=None) -> str:
    """Sobe o vídeo e devolve a URL. `progresso(enviado, total)` é opcional."""
    import requests

    from . import catalogo

    config = catalogo.carregar_config() if config is None else config
    visibilidade = (visibilidade
                    or config.get("youtube", {}).get("visibilidade", "private"))
    if visibilidade not in VISIBILIDADES:
        raise PublicacaoFalhou(
            f"visibilidade inválida: {visibilidade!r} "
            f"(use {', '.join(VISIBILIDADES)})")

    credenciais = carregar_credenciais()
    if credenciais is None:
        raise PublicacaoFalhou(
            "sem credenciais do YouTube. No painel: Live/YouTube -> "
            "Configurar OAuth (marque 'com upload').")
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
        data=json.dumps(_corpo(video, config, visibilidade)).encode("utf-8"))
    if not inicio.ok:
        raise PublicacaoFalhou(
            f"o YouTube recusou os metadados ({inicio.status_code}): "
            f"{inicio.text[:200]}")
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
                try:
                    from . import metricas
                    metricas.registrar_publicacao(video, url, "youtube",
                                                  {"visibilidade": visibilidade})
                except Exception as exc:  # pragma: no cover - so log
                    print(f"[publicar] registro falhou: {exc}")
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
