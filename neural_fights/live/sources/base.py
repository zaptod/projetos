"""Fronteira entre a thread de rede e a thread do jogo.

Regra invariante desta camada: **o loop do jogo nunca bloqueia numa fonte**. Um
adaptador produz eventos numa thread propria e so os publica numa fila limitada;
o jogo drena o que houver e segue o frame. Se a fila enche, o evento mais antigo
e descartado e contabilizado -- perder uma interacao e aceitavel, travar a
transmissao nao e.
"""

from __future__ import annotations

import abc
import logging
import queue
import threading
from dataclasses import dataclass, replace

from neural_fights.live.events import ViewerEvent

logger = logging.getLogger(__name__)

CAPACIDADE_PADRAO = 2000


@dataclass(frozen=True)
class SourceStats:
    """Contabilidade de uma fonte; util para diagnostico durante a live."""

    recebidos: int = 0
    publicados: int = 0
    descartados: int = 0
    invalidos: int = 0
    erros_conexao: int = 0

    @property
    def saudavel(self) -> bool:
        return self.descartados == 0 and self.erros_conexao == 0


class EventSource(abc.ABC):
    """Base das fontes de evento.

    Subclasses implementam ``_executar``, que roda numa thread daemon e chama
    ``_publicar`` para cada evento produzido. ``_executar`` deve observar
    ``self._parar`` e retornar quando ele estiver setado.
    """

    #: Identificador curto da plataforma; usado em log e diagnostico.
    nome: str = "base"

    def __init__(self, *, capacidade: int = CAPACIDADE_PADRAO) -> None:
        if capacidade <= 0:
            raise ValueError("capacidade precisa ser positiva")
        self._fila: queue.Queue[ViewerEvent] = queue.Queue(maxsize=capacidade)
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stats = SourceStats()

    # ------------------------------------------------------------------ ciclo

    def start(self) -> None:
        """Sobe a thread produtora. Chamar duas vezes e um erro de uso."""
        if self._thread is not None:
            raise RuntimeError(f"fonte {self.nome!r} ja foi iniciada")
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop_produtor,
            name=f"live-source-{self.nome}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        """Sinaliza parada e aguarda a thread. Seguro chamar mais de uma vez."""
        self._parar.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("fonte %s nao encerrou em %.1fs", self.nome, timeout)

    @property
    def ativa(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def __enter__(self) -> "EventSource":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()

    # ----------------------------------------------------------------- consumo

    def drenar(self, limite: int | None = None) -> list[ViewerEvent]:
        """Retira ate ``limite`` eventos sem bloquear.

        Chamado pela thread do jogo, uma vez por frame. O limite existe para que
        uma rajada de interacoes nao gaste o orcamento de um frame inteiro.
        """
        coletados: list[ViewerEvent] = []
        while limite is None or len(coletados) < limite:
            try:
                coletados.append(self._fila.get_nowait())
            except queue.Empty:
                break
        return coletados

    @property
    def stats(self) -> SourceStats:
        with self._lock:
            return self._stats

    # ---------------------------------------------------------------- producao

    def _publicar(self, evento: ViewerEvent) -> bool:
        """Enfileira um evento. Retorna ``False`` se teve de descartar."""
        if not isinstance(evento, ViewerEvent):
            self._contabilizar(invalidos=1)
            raise TypeError("fonte precisa publicar ViewerEvent")
        self._contabilizar(recebidos=1)
        try:
            self._fila.put_nowait(evento)
        except queue.Full:
            # Fila cheia significa que o jogo nao esta drenando no ritmo da
            # plataforma. Abrir espaco descartando o mais antigo mantem a live
            # respondendo ao que acabou de acontecer no chat.
            try:
                self._fila.get_nowait()
                self._fila.put_nowait(evento)
            except (queue.Empty, queue.Full):
                self._contabilizar(descartados=1)
                return False
            self._contabilizar(descartados=1, publicados=1)
            return False
        self._contabilizar(publicados=1)
        return True

    def _contabilizar(self, **incrementos: int) -> None:
        with self._lock:
            self._stats = replace(
                self._stats,
                **{
                    campo: getattr(self._stats, campo) + valor
                    for campo, valor in incrementos.items()
                },
            )

    def _loop_produtor(self) -> None:
        try:
            self._executar()
        except Exception:
            # Uma fonte que morre nao pode derrubar a transmissao: o jogo segue
            # sem interacao e o operador ve o erro no log.
            logger.exception("fonte %s encerrou com erro", self.nome)
            self._contabilizar(erros_conexao=1)

    @abc.abstractmethod
    def _executar(self) -> None:
        """Produz eventos ate ``self._parar`` ser setado."""


__all__ = ["CAPACIDADE_PADRAO", "EventSource", "SourceStats"]
