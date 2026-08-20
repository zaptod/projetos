"""Sessao de live: o dono do loop de longa duracao.

O motor nao sabe que esta numa transmissao. Quem dirige o relogio aqui e a
``LiveSession``, que embute **um** ``Simulador`` e o alimenta -- o mesmo padrao
que ``HeadlessMatchRunner`` ja usa no caminho headless, so que com render.

Duas regras estruturam tudo:

1. **Um ``Simulador`` por sessao, criado uma vez.** ``close()`` chama
   ``pygame.quit()``, o que destroi a janela do sistema. Numa live isso mataria
   a fonte de captura do OBS no meio da transmissao. A troca de partida usa
   ``recarregar_tudo()``, que nunca toca no display.

2. **Eventos entram entre frames, nunca durante.** ``aplicar`` roda antes de
   ``sim.update(dt)``, entao o que um comando escreve nos buffers do lutador e
   drenado pela primeira fase do frame -- o mesmo codigo, na mesma ordem, que
   drena o que uma skill produziu. Um gift fica indistinguivel de uma skill.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence

import pygame

from neural_fights.live.events import ViewerEvent
from neural_fights.live.sources.base import EventSource
from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.config import FPS

logger = logging.getLogger(__name__)

# Teto de eventos processados por frame. Uma rajada de gifts nao pode gastar o
# orcamento de 16,6 ms; o excedente espera na fila da fonte.
EVENTOS_POR_FRAME = 32

# Tempo que o resultado fica na tela antes de montar a proxima partida.
PAUSA_ENTRE_PARTIDAS = 6.0


@dataclass
class SessionStats:
    """Contabilidade da sessao, exibivel em overlay e util em post-mortem."""

    frames: int = 0
    partidas: int = 0
    eventos_recebidos: int = 0
    eventos_aplicados: int = 0
    eventos_ignorados: int = 0
    vitorias_por_lutador: dict[str, int] = field(default_factory=dict)

    def registrar_vitoria(self, nome: str) -> None:
        self.vitorias_por_lutador[nome] = self.vitorias_por_lutador.get(nome, 0) + 1


class Matchmaker:
    """Decide quem luta a proxima partida.

    Nesta fase e um rodizio simples sobre o roster. A Fase 5 substitui isto por
    uma politica que le vitorias/derrotas do registro de espectadores, sem que a
    sessao precise mudar: o contrato e apenas ``proximo() -> (p1, p2, cenario)``.
    """

    def __init__(self, nomes: Sequence[str], cenarios: Sequence[str] = ("Arena",)) -> None:
        nomes = [str(nome) for nome in nomes if str(nome).strip()]
        if len(nomes) < 2:
            raise ValueError("matchmaking precisa de ao menos dois lutadores")
        self._nomes = nomes
        self._cenarios = tuple(cenarios) or ("Arena",)
        self._indice = 0

    def __len__(self) -> int:
        return len(self._nomes)

    def proximo(self, evitar: frozenset[str] | None = None) -> tuple[str, str, str]:
        """Devolve o proximo confronto do rodizio.

        ``evitar`` recusa um par especifico -- na pratica, o confronto que
        acabou de acontecer. Repetir a mesma luta logo em seguida e a falha mais
        visivel possivel para quem esta assistindo, entao a politica mora aqui e
        nao na sessao.
        """
        for _ in range(len(self._nomes)):
            p1 = self._nomes[self._indice % len(self._nomes)]
            p2 = self._nomes[(self._indice + 1) % len(self._nomes)]
            cenario = self._cenarios[self._indice % len(self._cenarios)]
            self._indice += 1
            if evitar is None or {p1, p2} != evitar:
                return p1, p2, cenario
        # Roster de dois: nao ha outro confronto possivel. Repetir e o correto.
        return p1, p2, cenario


class LiveSession:
    """Roda partidas encadeadas numa janela estavel, alimentada por eventos."""

    def __init__(
        self,
        simulador: Simulador,
        matchmaker: Matchmaker,
        *,
        fontes: Sequence[EventSource] = (),
        aplicar_evento: Callable[["LiveSession", ViewerEvent], bool] | None = None,
        preparar_partida: Callable[["LiveSession"], dict] | None = None,
        ao_terminar_partida: Callable[..., None] | None = None,
        pausa_entre_partidas: float = PAUSA_ENTRE_PARTIDAS,
        max_partidas: int | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        if simulador.headless:
            raise RuntimeError(
                "LiveSession renderiza; use HeadlessMatchRunner para execucao headless"
            )
        self.sim = simulador
        self.matchmaker = matchmaker
        self.fontes = tuple(fontes)
        self._aplicar_evento = aplicar_evento
        self._preparar_partida = preparar_partida
        self._ao_terminar_partida = ao_terminar_partida
        self.pausa_entre_partidas = max(0.0, float(pausa_entre_partidas))
        self.max_partidas = max_partidas
        self._relogio = relogio
        self.stats = SessionStats()
        self._fim_de_partida: float | None = None
        self.rodando = False
        # Passe 3 (arte): camada de broadcast e o "peek" do proximo
        # confronto (para a VS screen durante a pausa). O cache garante
        # que o rodizio do matchmaker avanca UMA vez por partida.
        self.overlay = None
        self._confronto_cache: tuple[str, str, str] | None = None

    # ------------------------------------------------------------------ ciclo

    def iniciar_fontes(self) -> None:
        for fonte in self.fontes:
            fonte.start()

    def parar_fontes(self) -> None:
        for fonte in self.fontes:
            try:
                fonte.stop()
            except Exception:
                logger.exception("falha ao parar fonte %s", fonte.nome)

    def run(self) -> SessionStats:
        """Loop principal. Nunca fecha o ``Simulador`` entre partidas."""
        self.rodando = True
        self.iniciar_fontes()
        try:
            while self.rodando and self.sim.rodando:
                dt = self.sim.clock.tick(FPS) / 1000.0
                self.passo(dt)
        finally:
            self.parar_fontes()
        return self.stats

    def passo(self, dt: float) -> None:
        """Um frame completo, na ordem que mantem o motor coerente."""
        self.sim.processar_inputs()
        self.drenar_eventos()
        # Passe 2 (arte): o relógio de drama TICA na live. Antes, um dodge
        # setava time_scale=0.5 e nada restaurava — a transmissão inteira
        # ficava em câmera lenta até a próxima partida.
        self.sim.update(self.sim.avancar_relogio(dt))
        self.sim.desenhar()
        if self.overlay is not None:
            try:
                self.overlay.desenhar(self.sim.tela)
            except Exception:
                # O show nunca cai por causa de um overlay.
                logger.exception("overlay de broadcast falhou")
        pygame.display.flip()
        self.stats.frames += 1
        self._avaliar_fim_de_partida()

    @property
    def tempo_na_pausa(self) -> float | None:
        """Segundos desde o fim da partida (None durante a luta)."""
        if self._fim_de_partida is None:
            return None
        return self._relogio() - self._fim_de_partida

    @property
    def proximo_confronto(self) -> tuple[str, str, str] | None:
        return self._confronto_cache

    # --------------------------------------------------------------- eventos

    def drenar_eventos(self, limite: int = EVENTOS_POR_FRAME) -> list[ViewerEvent]:
        """Tira eventos das fontes e aplica, sem nunca bloquear o frame."""
        aplicados: list[ViewerEvent] = []
        restante = limite
        for fonte in self.fontes:
            if restante <= 0:
                break
            for evento in fonte.drenar(limite=restante):
                restante -= 1
                self.stats.eventos_recebidos += 1
                if self._aplicar(evento):
                    self.stats.eventos_aplicados += 1
                    aplicados.append(evento)
                else:
                    self.stats.eventos_ignorados += 1
        return aplicados

    def _aplicar(self, evento: ViewerEvent) -> bool:
        if self._aplicar_evento is None:
            return False
        try:
            return bool(self._aplicar_evento(self, evento))
        except Exception:
            # Um comando malformado nunca pode derrubar a transmissao.
            logger.exception("falha ao aplicar evento %s", evento.event_id)
            return False

    # -------------------------------------------------------------- partidas

    def _avaliar_fim_de_partida(self) -> None:
        if not getattr(self.sim, "round_finalizado", False):
            self._fim_de_partida = None
            return

        agora = self._relogio()
        if self._fim_de_partida is None:
            self._fim_de_partida = agora
            self._registrar_resultado()
            # Peek do proximo confronto: a VS screen precisa saber quem
            # vem AGORA, nao no ultimo frame da pausa.
            atual = {
                str(self.sim.match_config.get("p1_nome") or ""),
                str(self.sim.match_config.get("p2_nome") or ""),
            }
            try:
                self._confronto_cache = self.matchmaker.proximo(
                    evitar=frozenset(atual)
                )
            except Exception:
                logger.exception("peek do proximo confronto falhou")
                self._confronto_cache = None
            return

        if agora - self._fim_de_partida < self.pausa_entre_partidas:
            return

        if self.max_partidas is not None and self.stats.partidas >= self.max_partidas:
            self.rodando = False
            return

        self.proxima_partida()

    def _registrar_resultado(self) -> None:
        self.stats.partidas += 1
        vencedor = getattr(self.sim, "vencedor", None)
        nome = getattr(getattr(vencedor, "dados", None), "nome", None)
        if nome:
            self.stats.registrar_vitoria(str(nome))

        if self._ao_terminar_partida is None:
            return
        try:
            self._ao_terminar_partida(self, *self._desfecho(nome))
        except Exception:
            # Perder a contabilidade de uma luta nunca derruba a transmissao.
            logger.exception("falha no gancho de fim de partida")

    def _desfecho(self, nome_vencedor: str | None) -> tuple[str | None, str | None, bool]:
        """Resolve vencedor e perdedor pelos nomes que o motor usa."""
        p1 = getattr(getattr(self.sim.p1, "dados", None), "nome", None)
        p2 = getattr(getattr(self.sim.p2, "dados", None), "nome", None)
        if not nome_vencedor:
            return p1, p2, True
        perdedor = p2 if nome_vencedor == p1 else p1
        return nome_vencedor, perdedor, False

    def proxima_partida(self) -> None:
        """Troca os lutadores sem recriar a janela.

        ``recarregar_tudo`` reconstroi lutadores, arena e managers, mas nao toca
        em ``pygame.display``: a fonte de captura do OBS permanece valida.
        """
        if self._confronto_cache is not None:
            p1, p2, cenario = self._confronto_cache
            self._confronto_cache = None
        else:
            atual = {
                str(self.sim.match_config.get("p1_nome") or ""),
                str(self.sim.match_config.get("p2_nome") or ""),
            }
            p1, p2, cenario = self.matchmaker.proximo(evitar=frozenset(atual))
        self.sim.match_config["p1_nome"] = p1
        self.sim.match_config["p2_nome"] = p2
        self.sim.match_config["cenario"] = cenario

        # O que espectadores compraram para a proxima partida entra aqui, antes
        # do reload -- e o unico momento em que alterar a config tem efeito.
        for chave, valor in self._plano_da_proxima().items():
            self.sim.match_config[chave] = valor
        # A serie e sempre de um round; o formato do show e contado aqui, nao no
        # motor, porque ``best_of`` so e lido na construcao do ``Simulador``.
        self.sim.best_of_series.reset_series()
        self.sim.recarregar_tudo()
        self._fim_de_partida = None

    def _plano_da_proxima(self) -> dict:
        """Overrides comprados para a proxima partida; falhar aqui nao para o show."""
        if self._preparar_partida is None:
            return {}
        try:
            plano = self._preparar_partida(self)
        except Exception:
            logger.exception("falha ao montar o plano da proxima partida")
            return {}
        return plano if isinstance(plano, dict) else {}


__all__ = [
    "EVENTOS_POR_FRAME",
    "PAUSA_ENTRE_PARTIDAS",
    "LiveSession",
    "Matchmaker",
    "SessionStats",
]
