"""Fonte de eventos gravados, para desenvolver e testar sem estar ao vivo.

Existe por dois motivos praticos:

* o CI nao pode depender de rede nem de credencial de plataforma;
* ajustar balanceamento de gift exige repetir exatamente a mesma sequencia de
  interacoes, o que uma live nunca reproduz.

O formato e JSON Lines: um ``ViewerEvent`` serializado por linha, na ordem em
que aconteceram. Linhas vazias e comentarios ``#`` sao ignorados.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Sequence

from neural_fights.live.events import ViewerEvent
from neural_fights.live.sources.base import EventSource

logger = logging.getLogger(__name__)


class ReplayEventSource(EventSource):
    """Reproduz uma sequencia gravada de eventos.

    Com ``velocidade=0`` (padrao) publica tudo de uma vez, que e o modo usado em
    teste. Com ``velocidade>0`` respeita os intervalos de ``timestamp``
    divididos por esse fator, aproximando o ritmo real de um chat.
    """

    nome = "replay"

    def __init__(
        self,
        eventos: Sequence[ViewerEvent],
        *,
        velocidade: float = 0.0,
        repetir: bool = False,
        capacidade: int | None = None,
    ) -> None:
        eventos = tuple(eventos)
        if any(not isinstance(evento, ViewerEvent) for evento in eventos):
            raise TypeError("replay aceita apenas ViewerEvent")
        if velocidade < 0.0:
            raise ValueError("velocidade nao pode ser negativa")
        if repetir and not eventos:
            raise ValueError("nao ha o que repetir: sequencia vazia")
        super().__init__(capacidade=capacidade or max(len(eventos), 1))
        self._eventos = eventos
        self._velocidade = float(velocidade)
        self._repetir = bool(repetir)

    @property
    def eventos(self) -> tuple[ViewerEvent, ...]:
        return self._eventos

    @classmethod
    def de_arquivo(cls, caminho: str | Path, **opcoes) -> "ReplayEventSource":
        """Carrega um arquivo JSON Lines de eventos."""
        return cls(carregar_eventos(caminho), **opcoes)

    def _executar(self) -> None:
        while True:
            anterior: float | None = None
            for evento in self._eventos:
                if self._parar.is_set():
                    return
                if self._velocidade > 0.0 and anterior is not None:
                    espera = (evento.timestamp - anterior) / self._velocidade
                    if espera > 0.0 and self._parar.wait(espera):
                        return
                anterior = evento.timestamp
                self._publicar(evento)
            if not self._repetir:
                return
            if self._parar.is_set():
                return


def carregar_eventos(caminho: str | Path) -> tuple[ViewerEvent, ...]:
    """Le um arquivo JSON Lines e devolve os eventos validados.

    Uma linha invalida aborta a carga com o numero da linha: uma gravacao de
    replay e insumo de teste, entao silenciar erro aqui esconderia o problema
    justamente onde ele deveria aparecer.
    """
    caminho = Path(caminho)
    eventos: list[ViewerEvent] = []
    with caminho.open("r", encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            texto = linha.strip()
            if not texto or texto.startswith("#"):
                continue
            try:
                eventos.append(ViewerEvent.from_dict(json.loads(texto)))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"{caminho}:{numero}: evento invalido: {exc}") from exc
    return tuple(eventos)


def gravar_eventos(caminho: str | Path, eventos: Iterable[ViewerEvent]) -> int:
    """Grava eventos em JSON Lines; devolve quantos foram escritos.

    Serve para capturar uma live real e depois repetir a sessao offline.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with caminho.open("w", encoding="utf-8", newline="\n") as arquivo:
        for evento in eventos:
            if not isinstance(evento, ViewerEvent):
                raise TypeError("so e possivel gravar ViewerEvent")
            arquivo.write(json.dumps(evento.to_dict(), ensure_ascii=False, sort_keys=True))
            arquivo.write("\n")
            total += 1
    return total


class RecordingSource(EventSource):
    """Envolve qualquer fonte e grava tudo que passa por ela.

    Uma live real produz, de graca, o arquivo de replay que reproduz aquela
    sessao offline. E o caminho mais barato para transformar um incidente ao
    vivo em teste de regressao.

    A gravacao acontece na thread produtora, antes de publicar: se o jogo
    descartar o evento por backpressure, ele continua no arquivo.
    """

    nome = "recording"

    def __init__(
        self,
        interna: EventSource,
        caminho: str | Path,
        *,
        capacidade: int | None = None,
    ) -> None:
        if not isinstance(interna, EventSource):
            raise TypeError("RecordingSource envolve uma EventSource")
        super().__init__(capacidade=capacidade or interna._fila.maxsize or 1)
        self._interna = interna
        self._caminho = Path(caminho)
        self._arquivo = None
        self.nome = f"recording:{interna.nome}"

    @property
    def caminho(self) -> Path:
        return self._caminho

    def start(self) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo = self._caminho.open("a", encoding="utf-8", newline="\n")
        self._interna.start()
        super().start()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._interna.stop(timeout=timeout)
        super().stop(timeout=timeout)
        arquivo, self._arquivo = self._arquivo, None
        if arquivo is not None:
            arquivo.close()

    def _executar(self) -> None:
        while not self._parar.is_set():
            eventos = self._interna.drenar()
            if not eventos:
                # A fonte interna e quem dita o ritmo; este laco so repassa.
                if self._parar.wait(0.05):
                    return
                continue
            for evento in eventos:
                self._gravar(evento)
                self._publicar(evento)

    def _gravar(self, evento: ViewerEvent) -> None:
        arquivo = self._arquivo
        if arquivo is None:
            return
        try:
            arquivo.write(json.dumps(evento.to_dict(), ensure_ascii=False, sort_keys=True))
            arquivo.write("\n")
            arquivo.flush()
        except OSError:
            # Perder a gravacao nunca pode derrubar a transmissao.
            logger.exception("falha ao gravar evento em %s", self._caminho)


class ScriptedEventSource(EventSource):
    """Fonte controlada pelo teste: nada e publicado sem um push explicito.

    Diferente do replay, nao ha thread produtora -- o teste decide o instante
    exato de cada evento, o que torna deterministica a assercao sobre o frame em
    que um comando foi aplicado.
    """

    nome = "scripted"

    def start(self) -> None:  # sem thread: a producao e manual
        self._parar.clear()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._parar.set()

    @property
    def ativa(self) -> bool:
        return not self._parar.is_set()

    def push(self, *eventos: ViewerEvent) -> int:
        """Publica eventos imediatamente; devolve quantos entraram na fila."""
        return sum(1 for evento in eventos if self._publicar(evento))

    def _executar(self) -> None:  # pragma: no cover - nunca roda
        raise AssertionError("ScriptedEventSource nao usa thread produtora")


__all__ = [
    "RecordingSource",
    "ReplayEventSource",
    "ScriptedEventSource",
    "carregar_eventos",
    "gravar_eventos",
]
