"""Progressao: resultados alimentam quem entra na proxima partida.

Duas pecas, ambas pequenas de proposito:

``registrar_resultado``
    Grava vitoria e derrota do que acabou de acontecer. So lutadores de
    espectador tem ficha -- o roster curado e cenario, nao competidor.

``RankedMatchmaker``
    Substitui o rodizio simples respeitando o mesmo contrato
    (``proximo(evitar)``), entao ``LiveSession`` nao muda. Prioriza quem tem
    lutador na casa: a graca da feature e ver o proprio nome na arena.
"""

from __future__ import annotations

import logging
from typing import Sequence

from neural_fights.live.registry import LiveRegistry
from neural_fights.live.roster import LiveRoster
from neural_fights.live.session import Matchmaker

logger = logging.getLogger(__name__)

# Quantos lutadores de espectador entram no sorteio. Um teto existe para que a
# consulta e o rodizio nao cresçam com uma audiencia grande.
ESPECTADORES_NA_FILA = 32


def registrar_resultado(
    registry: LiveRegistry,
    *,
    vencedor: str | None,
    perdedor: str | None,
    empate: bool = False,
) -> int:
    """Contabiliza o resultado; devolve quantas fichas foram atualizadas.

    Nomes do roster curado sao ignorados em silencio -- eles nao tem ficha, e
    isso e a regra, nao uma falha.
    """
    atualizadas = 0
    try:
        if empate:
            for nome in (vencedor, perdedor):
                if nome and registry.registrar_resultado_por_catalogo(nome, "empate"):
                    atualizadas += 1
            return atualizadas
        if vencedor and registry.registrar_resultado_por_catalogo(vencedor, "vitoria"):
            atualizadas += 1
        if perdedor and registry.registrar_resultado_por_catalogo(perdedor, "derrota"):
            atualizadas += 1
    except Exception:
        # Perder a contabilidade de uma luta nunca pode derrubar a transmissao.
        logger.exception("falha ao registrar resultado da partida")
    return atualizadas


class RankedMatchmaker(Matchmaker):
    """Rodizio que inclui lutadores de espectador e respeita a classificacao.

    A ordem de montagem e deliberada: espectadores primeiro, depois o roster
    curado como preenchimento. Quem gastou para entrar precisa aparecer; o
    catalogo existe para que o show nunca fique sem adversario.
    """

    def __init__(
        self,
        roster: LiveRoster,
        *,
        cenarios: Sequence[str] = ("Arena",),
        limite_espectadores: int = ESPECTADORES_NA_FILA,
    ) -> None:
        self.roster = roster
        self.limite_espectadores = int(limite_espectadores)
        super().__init__(self._montar_fila(), cenarios)

    def _montar_fila(self) -> list[str]:
        espectadores = list(self.roster.nomes_de_espectadores(self.limite_espectadores))
        curados = list(self.roster.nomes_curados)
        fila = espectadores + curados
        if len(fila) < 2:
            # Sem espectadores e sem catalogo nao ha show; o erro vem do super.
            fila = curados
        return fila

    def atualizar_fila(self) -> int:
        """Reabsorve quem entrou desde a ultima partida. Devolve o tamanho."""
        nova = self._montar_fila()
        if len(nova) >= 2:
            self._nomes = nova
        return len(self._nomes)

    def proximo(self, evitar: frozenset[str] | None = None) -> tuple[str, str, str]:
        # Quem entrou por ``!entrar`` durante o round precisa poder lutar no
        # proximo, sem esperar a sessao reiniciar.
        self.atualizar_fila()
        return super().proximo(evitar)


def criar_registrador(registry: LiveRegistry):
    """Adapta ``registrar_resultado`` ao gancho de fim de partida da sessao."""

    def registrar(_sessao, vencedor: str | None, perdedor: str | None, empate: bool) -> None:
        registrar_resultado(
            registry, vencedor=vencedor, perdedor=perdedor, empate=empate
        )

    return registrar


__all__ = [
    "ESPECTADORES_NA_FILA",
    "RankedMatchmaker",
    "criar_registrador",
    "registrar_resultado",
]
