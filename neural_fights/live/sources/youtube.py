"""Adaptador do chat ao vivo do YouTube.

Este e o **unico** modulo da camada de live que conhece HTTP, OAuth ou o formato
de payload de uma plataforma. Tudo mais conversa em ``ViewerEvent``; um teste de
AST trava essa fronteira.

Feito sobre ``urllib`` da biblioteca padrao, de proposito. O que a integracao
precisa e um GET REST com bearer token e um POST de refresh -- adicionar
``google-api-python-client`` traria uma arvore de dependencias inteira para
economizar cerca de cem linhas, e o CI trava o conteudo da wheel e roda
``pip check``. Se um dia o custo se inverter, a troca fica confinada aqui.

Tres invariantes valem mais que qualquer funcionalidade:

1. **A luta nunca para.** Toda excecao de rede vira backoff e reconexao dentro
   da thread; a transmissao continua sem interacao e o operador ve no log.
2. **Nada e reprocessado.** O ``id`` da mensagem vira ``event_id``, que e chave
   primaria no journal: a reentrega apos reconexao e idempotente por
   construcao.
3. **Quota degrada, nao morre.** Ao se aproximar do teto diario o intervalo de
   polling cresce, em vez de a live terminar com um 403.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from neural_fights.live.events import EventKind, ViewerEvent
from neural_fights.live.sources.base import EventSource

logger = logging.getLogger(__name__)

API_BASE = "https://www.googleapis.com/youtube/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Nome do arquivo de credenciais dentro do diretorio de runtime. Nunca no
# pacote: credencial nao entra em wheel nem em controle de versao.
ARQUIVO_CREDENCIAIS = "youtube_credentials.json"
CREDENCIAIS_ENV = "NEURAL_FIGHTS_YOUTUBE_CREDENTIALS"

# Piso de polling. A resposta traz ``pollingIntervalMillis`` e ele e respeitado,
# mas um piso proprio protege contra um valor baixo demais gastar a quota.
INTERVALO_MINIMO = 2.0
INTERVALO_MAXIMO = 60.0

# Custo em unidades de quota por chamada, conforme a tabela da API.
CUSTO_LISTAR_MENSAGENS = 5
CUSTO_LISTAR_VIDEO = 1
QUOTA_DIARIA_PADRAO = 10_000

# Conversao de dinheiro para creditos de jogo. ``amountMicros`` vem em
# milionesimos da moeda, entao dividir por 10.000 da centesimos: R$ 1,00 vira
# 100 creditos. A paridade entre moedas NAO e resolvida aqui -- um super chat de
# 10 em duas moedas diferentes rende o mesmo. Quem opera a live calibra os
# custos do catalogo contra a moeda predominante da propria audiencia.
MICROS_POR_CREDITO = 10_000
CREDITOS_POR_MEMBRO = 500

_TIPOS_SUPORTADOS = {
    "textMessageEvent": EventKind.CHAT,
    "superChatEvent": EventKind.SUPERCHAT,
    "superStickerEvent": EventKind.SUPERCHAT,
    "newSponsorEvent": EventKind.MEMBERSHIP,
    "memberMilestoneChatEvent": EventKind.MEMBERSHIP,
}


class ErroDeAutenticacao(RuntimeError):
    """Credencial ausente, invalida ou recusada pelo provedor."""


class ErroDeTransporte(RuntimeError):
    """Falha de rede ou resposta inesperada; sempre recuperavel por backoff."""


# ------------------------------------------------------------------ credencial


@dataclass(frozen=True)
class Credenciais:
    client_id: str
    client_secret: str
    refresh_token: str
    video_id: str = ""

    @classmethod
    def de_arquivo(cls, caminho: str | Path | None = None) -> "Credenciais":
        caminho = Path(caminho) if caminho else caminho_credenciais()
        try:
            dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ErroDeAutenticacao(
                f"credenciais nao encontradas em {caminho}. Crie o arquivo com "
                "client_id, client_secret e refresh_token."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ErroDeAutenticacao(f"credenciais ilegiveis em {caminho}: {exc}") from exc
        return cls.de_dict(dados)

    @classmethod
    def de_dict(cls, dados: Mapping[str, Any]) -> "Credenciais":
        faltando = [
            campo
            for campo in ("client_id", "client_secret", "refresh_token")
            if not str(dados.get(campo, "")).strip()
        ]
        if faltando:
            raise ErroDeAutenticacao("credenciais incompletas: " + ", ".join(faltando))
        return cls(
            client_id=str(dados["client_id"]).strip(),
            client_secret=str(dados["client_secret"]).strip(),
            refresh_token=str(dados["refresh_token"]).strip(),
            video_id=str(dados.get("video_id", "")).strip(),
        )


def caminho_credenciais() -> str:
    override = os.environ.get(CREDENCIAIS_ENV)
    if override:
        return override
    from neural_fights.data import database

    return os.path.join(database.resolver_runtime_data_dir(), ARQUIVO_CREDENCIAIS)


# -------------------------------------------------------------------- parsing


def _micros_para_creditos(valor: object) -> int:
    try:
        micros = int(valor)
    except (TypeError, ValueError):
        return 0
    return max(0, micros // MICROS_POR_CREDITO)


def _texto_da_mensagem(snippet: Mapping[str, Any]) -> str:
    detalhes = snippet.get("textMessageDetails")
    if isinstance(detalhes, Mapping) and detalhes.get("messageText"):
        return str(detalhes["messageText"])
    for chave in ("superChatDetails", "superStickerDetails"):
        detalhes = snippet.get(chave)
        if isinstance(detalhes, Mapping) and detalhes.get("userComment"):
            return str(detalhes["userComment"])
    return str(snippet.get("displayMessage") or "")


def _valor_da_mensagem(tipo: str, snippet: Mapping[str, Any]) -> tuple[int, float, str]:
    for chave in ("superChatDetails", "superStickerDetails"):
        detalhes = snippet.get(chave)
        if isinstance(detalhes, Mapping):
            micros = detalhes.get("amountMicros", 0)
            creditos = _micros_para_creditos(micros)
            try:
                bruto = float(int(micros)) / 1_000_000.0
            except (TypeError, ValueError):
                bruto = 0.0
            return creditos, bruto, str(detalhes.get("currency") or "")
    if tipo in {"newSponsorEvent", "memberMilestoneChatEvent"}:
        return CREDITOS_POR_MEMBRO, 0.0, ""
    return 0, 0.0, ""


def converter_mensagem(item: Mapping[str, Any], *, sequence: int = 0) -> ViewerEvent | None:
    """Traduz uma mensagem da API para ``ViewerEvent``.

    Funcao pura: e o que os testes exercitam contra payloads gravados. Devolve
    ``None`` para tipos que o jogo nao interpreta (entrar/sair de membro, avisos
    do sistema) -- ignorar e melhor que inventar semantica.
    """
    if not isinstance(item, Mapping):
        return None
    snippet = item.get("snippet")
    autor = item.get("authorDetails")
    if not isinstance(snippet, Mapping) or not isinstance(autor, Mapping):
        return None

    tipo = str(snippet.get("type") or "")
    kind = _TIPOS_SUPORTADOS.get(tipo)
    if kind is None:
        return None

    canal = str(autor.get("channelId") or "").strip()
    if not canal:
        # Sem identidade estavel nao ha como aplicar cooldown nem posse.
        return None

    creditos, bruto, moeda = _valor_da_mensagem(tipo, snippet)
    return ViewerEvent(
        platform="youtube",
        viewer_id=canal,
        viewer_name=str(autor.get("displayName") or "")[:200],
        kind=kind,
        event_id=str(item.get("id") or ""),
        sequence=sequence,
        text=_texto_da_mensagem(snippet)[:2000],
        value_units=creditos,
        is_moderator=bool(autor.get("isChatModerator")),
        is_owner=bool(autor.get("isChatOwner")),
        raw_amount=bruto,
        raw_currency=moeda[:10],
        timestamp=_instante(snippet.get("publishedAt")),
    )


def _instante(publicado_em: object) -> float:
    """Converte o ISO-8601 da API em epoch; falha vira 0, nunca excecao."""
    texto = str(publicado_em or "").strip()
    if not texto:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp()
    except (ValueError, OSError):
        return 0.0


# -------------------------------------------------------------------- backoff


@dataclass
class Backoff:
    """Espera crescente com jitter, para reconexao que nao martela o provedor.

    Deterministico sob RNG injetado, o que permite testar a curva inteira sem
    dormir de verdade.
    """

    inicial: float = 2.0
    maximo: float = INTERVALO_MAXIMO
    fator: float = 2.0
    rng: random.Random = field(default_factory=random.Random)
    tentativas: int = 0

    def proxima(self) -> float:
        espera = min(self.inicial * (self.fator**self.tentativas), self.maximo)
        self.tentativas += 1
        # Jitter de +-25% evita que varios clientes voltem em uniao. O teto e
        # reaplicado depois do jitter: caso contrario o maximo documentado nao
        # seria maximo de verdade, e a espera passaria dele em 25%.
        return max(0.0, min(espera * (0.75 + self.rng.random() * 0.5), self.maximo))

    def reiniciar(self) -> None:
        self.tentativas = 0


# ---------------------------------------------------------------------- quota


@dataclass
class Quota:
    """Contabilidade das unidades diarias da API.

    Perto do teto o intervalo de polling cresce em vez de a live morrer com 403:
    responder devagar e melhor que nao responder.
    """

    limite: int = QUOTA_DIARIA_PADRAO
    gastas: int = 0

    @property
    def restantes(self) -> int:
        return max(0, self.limite - self.gastas)

    @property
    def fracao_usada(self) -> float:
        return min(1.0, self.gastas / self.limite) if self.limite > 0 else 1.0

    def gastar(self, unidades: int) -> None:
        self.gastas += max(0, int(unidades))

    def intervalo_ajustado(self, intervalo: float) -> float:
        """Estica o intervalo conforme a quota se esgota."""
        usada = self.fracao_usada
        if usada < 0.5:
            return intervalo
        if usada < 0.8:
            return intervalo * 2.0
        if usada < 0.95:
            return intervalo * 4.0
        return INTERVALO_MAXIMO


# ------------------------------------------------------------------ transporte


def _transporte_urllib(url: str, *, dados: bytes | None = None, cabecalhos: Mapping[str, str] | None = None, timeout: float = 20.0) -> dict:
    """Unico ponto do projeto que abre conexao. Levanta apenas erros proprios."""
    requisicao = urllib.request.Request(url, data=dados, headers=dict(cabecalhos or {}))
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            corpo = resposta.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code in (401, 403):
            raise ErroDeAutenticacao(f"HTTP {exc.code}: {detalhe}") from exc
        raise ErroDeTransporte(f"HTTP {exc.code}: {detalhe}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ErroDeTransporte(f"falha de rede: {exc}") from exc
    try:
        return json.loads(corpo)
    except json.JSONDecodeError as exc:
        raise ErroDeTransporte(f"resposta nao e JSON: {exc}") from exc


# ------------------------------------------------------------------- adaptador


class YouTubeChatSource(EventSource):
    """Le o chat ao vivo e publica ``ViewerEvent``.

    O transporte e injetavel para que os testes exercitem toda a maquina --
    parsing, backoff, quota, retomada por token -- sem tocar a rede.
    """

    nome = "youtube"

    def __init__(
        self,
        credenciais: Credenciais,
        *,
        video_id: str = "",
        transporte: Callable[..., dict] = _transporte_urllib,
        relogio: Callable[[], float] = time.monotonic,
        quota: Quota | None = None,
        backoff: Backoff | None = None,
        capacidade: int | None = None,
    ) -> None:
        super().__init__(capacidade=capacidade or 2000)
        self.credenciais = credenciais
        self.video_id = video_id or credenciais.video_id
        self._transporte = transporte
        self._relogio = relogio
        self.quota = quota if quota is not None else Quota()
        self.backoff = backoff if backoff is not None else Backoff()
        self._token: str = ""
        self._token_expira: float = 0.0
        self._live_chat_id: str = ""
        self._page_token: str = ""
        self._sequence = 0
        self.conectado = False
        self.intervalo = INTERVALO_MINIMO

    # ------------------------------------------------------------------ auth

    def _access_token(self) -> str:
        if self._token and self._relogio() < self._token_expira:
            return self._token
        corpo = urllib.parse.urlencode(
            {
                "client_id": self.credenciais.client_id,
                "client_secret": self.credenciais.client_secret,
                "refresh_token": self.credenciais.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        resposta = self._transporte(
            TOKEN_URL,
            dados=corpo,
            cabecalhos={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = str(resposta.get("access_token") or "")
        if not token:
            raise ErroDeAutenticacao("provedor nao devolveu access_token")
        try:
            validade = float(resposta.get("expires_in", 3600))
        except (TypeError, ValueError):
            validade = 3600.0
        self._token = token
        # Margem de 60s evita usar um token que expira no meio da chamada.
        self._token_expira = self._relogio() + max(0.0, validade - 60.0)
        return token

    def _get(self, caminho: str, parametros: Mapping[str, str], custo: int) -> dict:
        url = f"{API_BASE}/{caminho}?{urllib.parse.urlencode(parametros)}"
        resposta = self._transporte(
            url, cabecalhos={"Authorization": f"Bearer {self._access_token()}"}
        )
        self.quota.gastar(custo)
        return resposta

    # --------------------------------------------------------------- resolucao

    def resolver_live_chat_id(self) -> str:
        """Descobre o chat ativo. Refeito quando o token de pagina e recusado."""
        if self.video_id:
            resposta = self._get(
                "videos",
                {"part": "liveStreamingDetails", "id": self.video_id},
                CUSTO_LISTAR_VIDEO,
            )
            itens = resposta.get("items") or []
            if not itens:
                raise ErroDeTransporte(f"video sem transmissao ativa: {self.video_id}")
            detalhes = itens[0].get("liveStreamingDetails") or {}
            chat_id = str(detalhes.get("activeLiveChatId") or "")
        else:
            resposta = self._get(
                "liveBroadcasts",
                {"part": "snippet", "broadcastStatus": "active", "broadcastType": "all"},
                CUSTO_LISTAR_VIDEO,
            )
            itens = resposta.get("items") or []
            if not itens:
                raise ErroDeTransporte("nenhuma transmissao ativa na conta")
            chat_id = str((itens[0].get("snippet") or {}).get("liveChatId") or "")

        if not chat_id:
            raise ErroDeTransporte("transmissao encontrada, mas sem chat ativo")
        return chat_id

    # ------------------------------------------------------------------ ciclo

    def buscar_pagina(self) -> tuple[list[ViewerEvent], float]:
        """Uma chamada de polling. Devolve os eventos e o proximo intervalo."""
        if not self._live_chat_id:
            self._live_chat_id = self.resolver_live_chat_id()

        parametros = {
            "liveChatId": self._live_chat_id,
            "part": "snippet,authorDetails",
            "maxResults": "2000",
        }
        if self._page_token:
            parametros["pageToken"] = self._page_token

        resposta = self._get("liveChat/messages", parametros, CUSTO_LISTAR_MENSAGENS)
        self._page_token = str(resposta.get("nextPageToken") or "")

        eventos: list[ViewerEvent] = []
        for item in resposta.get("items") or []:
            self._sequence += 1
            try:
                evento = converter_mensagem(item, sequence=self._sequence)
            except (TypeError, ValueError):
                # Payload fora do contrato nunca derruba a leitura da pagina.
                logger.warning("mensagem ignorada por payload invalido", exc_info=True)
                continue
            if evento is not None:
                eventos.append(evento)

        try:
            intervalo = float(resposta.get("pollingIntervalMillis", 0)) / 1000.0
        except (TypeError, ValueError):
            intervalo = 0.0
        intervalo = max(intervalo, INTERVALO_MINIMO)
        return eventos, self.quota.intervalo_ajustado(intervalo)

    def _executar(self) -> None:
        while not self._parar.is_set():
            try:
                eventos, self.intervalo = self.buscar_pagina()
            except ErroDeAutenticacao:
                # Credencial ruim nao melhora com espera: sair e honesto.
                logger.exception("autenticacao do YouTube falhou; fonte encerrada")
                self.conectado = False
                return
            except ErroDeTransporte as exc:
                self.conectado = False
                self._contabilizar(erros_conexao=1)
                espera = self.backoff.proxima()
                logger.warning(
                    "chat do YouTube indisponivel (%s); nova tentativa em %.1fs",
                    exc,
                    espera,
                )
                # O token de pagina e preservado: ao voltar, retoma de onde parou.
                if self._parar.wait(espera):
                    return
                continue

            self.conectado = True
            self.backoff.reiniciar()
            for evento in eventos:
                self._publicar(evento)
            if self._parar.wait(self.intervalo):
                return

    # ------------------------------------------------------------ diagnostico

    def diagnostico(self) -> dict[str, Any]:
        """Resumo para overlay e log; nao faz chamada de rede."""
        return {
            "conectado": self.conectado,
            "intervalo": round(self.intervalo, 2),
            "quota_usada": self.quota.gastas,
            "quota_restante": self.quota.restantes,
            "tentativas_de_reconexao": self.backoff.tentativas,
            "stats": self.stats,
        }


def criar_fonte(
    *,
    caminho_credenciais_json: str | Path | None = None,
    video_id: str = "",
    **opcoes,
) -> YouTubeChatSource:
    """Monta a fonte a partir do arquivo de credenciais do diretorio de runtime."""
    return YouTubeChatSource(
        Credenciais.de_arquivo(caminho_credenciais_json), video_id=video_id, **opcoes
    )


__all__ = [
    "ARQUIVO_CREDENCIAIS",
    "CREDITOS_POR_MEMBRO",
    "CUSTO_LISTAR_MENSAGENS",
    "INTERVALO_MAXIMO",
    "INTERVALO_MINIMO",
    "MICROS_POR_CREDITO",
    "QUOTA_DIARIA_PADRAO",
    "Backoff",
    "Credenciais",
    "ErroDeAutenticacao",
    "ErroDeTransporte",
    "Quota",
    "YouTubeChatSource",
    "caminho_credenciais",
    "converter_mensagem",
    "criar_fonte",
]
