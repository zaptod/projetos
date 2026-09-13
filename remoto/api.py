# -*- coding: utf-8 -*-
"""Cliente minimo da API do Telegram — so `urllib`, nenhuma dependencia.

Poderia ser `python-telegram-bot`, mas isso traria um pacote (e as
atualizacoes dele) para dentro de um projeto que hoje roda com o que ja
existe na maquina. A API do bot e HTTP + JSON: cabe em cem linhas.

O que importa aqui:

  LONG POLLING. `getUpdates` fica pendurado ate `timeout` segundos esperando
  mensagem. E isso que faz o bot responder na hora sem ficar batendo no
  servidor — e, principalmente, e uma conexao de DENTRO para FORA: nenhuma
  porta aberta na maquina do Adrian, que guarda contas logadas.

  NUNCA LEVANTAR POR REDE. Wi-Fi cai, o Telegram tem instabilidade. Um erro
  de rede nao pode derrubar o bot; ele devolve vazio e a proxima volta tenta
  de novo.
"""
from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.telegram.org/bot{token}/{metodo}"
# O upload de bot para no meio dos 50 MB. Cortar antes e mais honesto do que
# tentar e receber um erro cru do servidor.
LIMITE_ARQUIVO_MB = 45


# O Telegram diz exatamente isto quando o Markdown nao fecha. Casar pela
# frase, e nao so pelo 400: um 400 tambem pode ser chat errado ou texto vazio,
# e reenviar sem formatacao nao conserta nenhum dos dois.
FALHAS_DE_FORMATACAO = ("can't parse entities", "can't find end of the entity",
                        "unsupported start tag")


def _e_erro_de_formatacao(resposta: dict) -> bool:
    motivo = str((resposta or {}).get("description") or "").lower()
    return any(sinal in motivo for sinal in FALHAS_DE_FORMATACAO)


class Telegram:
    def __init__(self, token: str, *, abrir=None):
        self.token = token
        # injetavel para o teste nao tocar a rede
        self._abrir = abrir or urllib.request.urlopen

    # ------------------------------------------------------------- interno
    def _url(self, metodo: str) -> str:
        return BASE.format(token=self.token, metodo=metodo)

    def chamar(self, metodo: str, **campos) -> dict:
        """POST simples (form-urlencoded). {} quando a rede falha.

        O CORPO DO 400 TAMBEM VOLTA. Ate 11/09/2026 qualquer erro virava `{}`,
        e o Telegram poe o motivo real no corpo de um 400 — foi assim que
        "can't parse entities" ficou meses invisivel.
        """
        dados = urllib.parse.urlencode(
            {k: v for k, v in campos.items() if v is not None}).encode()
        try:
            with self._abrir(self._url(metodo), data=dados, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            try:
                return json.loads(erro.read().decode("utf-8", "replace"))
            except Exception:                                  # noqa: BLE001
                return {"ok": False, "error_code": erro.code}
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return {}

    # -------------------------------------------------------------- enviar
    def mensagem(self, chat_id, texto: str, *, markdown: bool = False) -> dict:
        """Manda o texto. O CONTEUDO chega mesmo quando a formatacao nao dá.

        DEFEITO ACHADO EM 11/09/2026, e ele calava o canal inteiro: o bot
        manda tudo com `parse_mode=Markdown`, e o Markdown legado do Telegram
        trata `_` e `*` como formatacao. Todo id deste projeto tem underscore
        (`historia_00004`, `p04_cena_02`, `generation_00055`), entao os tres
        relatorios voltavam

            400 Bad Request: can't parse entities

        e nada era entregue. Nao havia erro no log, nao havia excecao: a
        funcao devolvia `{}` e quem chamou seguiu em frente. Os relatorios de
        metas e funcionamento — os que existem justamente para avisar quando
        algo quebra — eram os que mais escapavam, porque listam ids.

        Reenviar SEM formatacao e a escolha certa: negrito e enfeite, a lista
        de videos barrados nao. Escapar os `_` seria a outra saida, e ela e
        pior — depende de quem escreve o relatorio lembrar de escapar, e o
        proximo relatorio vai esquecer de novo.
        """
        # 4096 e o teto do Telegram; cortar aqui evita perder a mensagem
        # inteira por causa de uma lista longa.
        corpo = texto[:4000]
        resposta = self.chamar("sendMessage", chat_id=chat_id, text=corpo,
                               parse_mode="Markdown" if markdown else None,
                               disable_web_page_preview="true")
        if markdown and not resposta.get("ok") and _e_erro_de_formatacao(resposta):
            return self.chamar("sendMessage", chat_id=chat_id, text=corpo,
                               disable_web_page_preview="true")
        return resposta

    def arquivo(self, chat_id, caminho, *, legenda: str = "",
                como_video: bool = True) -> dict:
        """Manda o mp4 para o celular. E o que permite ASSISTIR antes de publicar."""
        caminho = Path(caminho)
        if not caminho.is_file():
            return {"ok": False, "description": "arquivo nao existe"}
        mb = caminho.stat().st_size / 1e6
        if mb > LIMITE_ARQUIVO_MB:
            return {"ok": False,
                    "description": f"{mb:.0f} MB — acima do limite de "
                                   f"{LIMITE_ARQUIVO_MB} MB do Telegram"}
        metodo = "sendVideo" if como_video else "sendDocument"
        campo = "video" if como_video else "document"
        corpo, tipo = _multipart({"chat_id": str(chat_id),
                                  "caption": legenda[:1000]},
                                 campo, caminho)
        pedido = urllib.request.Request(self._url(metodo), data=corpo,
                                        headers={"Content-Type": tipo})
        try:
            with self._abrir(pedido, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            return {"ok": False, "description": str(exc)}

    # -------------------------------------------------------------- receber
    def novidades(self, desde: int | None = None, timeout: int = 30) -> list:
        """As mensagens novas. Lista vazia quando nao ha (ou a rede caiu)."""
        resposta = self.chamar("getUpdates", offset=desde, timeout=timeout,
                               allowed_updates='["message"]')
        return resposta.get("result") or []

    def eu(self) -> dict:
        return (self.chamar("getMe") or {}).get("result") or {}


def _multipart(campos: dict, nome_arquivo: str, caminho: Path) -> tuple:
    """Corpo multipart/form-data na mao (sem `requests` no projeto)."""
    limite = "----neuralfights7b2c1f"
    partes = []
    for chave, valor in campos.items():
        partes.append(f"--{limite}\r\n"
                      f'Content-Disposition: form-data; name="{chave}"\r\n\r\n'
                      f"{valor}\r\n".encode("utf-8"))
    tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
    partes.append(
        f"--{limite}\r\n"
        f'Content-Disposition: form-data; name="{nome_arquivo}"; '
        f'filename="{caminho.name}"\r\n'
        f"Content-Type: {tipo}\r\n\r\n".encode("utf-8"))
    partes.append(caminho.read_bytes())
    partes.append(f"\r\n--{limite}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={limite}"
