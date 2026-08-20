"""Politica de uso: quem pode disparar o que, e com que frequencia.

Funcoes puras com relogio injetado. Nao importa pygame, nao toca disco, nao
conhece o motor -- o que torna cada regra testavel isoladamente e mantem o CI
livre de rede e de janela.

A ordem de avaliacao e deliberada e vale a pena ler como uma lista de razoes:

1. **banimento** -- decisao de moderacao vem antes de qualquer economia;
2. **momento** -- comando de proximo round nunca e aplicado no meio de um round;
3. **cooldown do proprio comando** -- ritmo do show, global a todos;
4. **cooldown do espectador** -- impede que uma pessoa monopolize a luta;
5. **teto por round** -- limita quantas vezes o mesmo efeito aparece;
6. **saturacao** -- teto duro contra o estado vivo, para o motor nao derreter;
7. **pagamento** -- por ultimo, para que a recusa por regra nunca cobre nada.

Moderador escapa de cooldown e teto, nunca de journaling nem de banimento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from neural_fights.live.catalog import get_command

# Teto de efeitos de origem-espectador simultaneos no mundo. Rate limit e
# justica; isto e sobrevivencia do frame: cada area viva custa reflexao por
# frame no motor (``inspect.signature`` em ``_atualizar_areas``).
SATURACAO_MAX_AREAS = 6


class Decisao:
    """Vocabulario de desfecho. Poucos valores, cada um com resposta propria."""

    APLICAR = "APLICAR"
    ADIAR = "ADIAR"
    RECUSAR = "RECUSAR"


@dataclass(frozen=True)
class Veredito:
    decisao: str
    motivo: str = ""
    detalhe: str = ""

    @property
    def aplicar(self) -> bool:
        return self.decisao == Decisao.APLICAR

    @property
    def adiar(self) -> bool:
        return self.decisao == Decisao.ADIAR


@dataclass
class EstadoRound:
    """Contadores que zeram a cada partida."""

    usos_por_comando: dict[str, int] = field(default_factory=dict)
    ultimo_uso_global: dict[str, float] = field(default_factory=dict)
    areas_de_espectador: int = 0

    def reiniciar(self) -> None:
        self.usos_por_comando.clear()
        self.ultimo_uso_global.clear()
        self.areas_de_espectador = 0


@dataclass
class EstadoViewer:
    """Historico por espectador; sobrevive entre rounds da mesma sessao."""

    ultimo_uso: dict[str, float] = field(default_factory=dict)
    creditos_gastos: int = 0


class PolicyEngine:
    """Aplica a politica sem tocar em nada fora dos proprios contadores."""

    def __init__(
        self,
        *,
        relogio: Callable[[], float],
        saturacao_max: int = SATURACAO_MAX_AREAS,
    ) -> None:
        self._relogio = relogio
        self.saturacao_max = int(saturacao_max)
        self.round = EstadoRound()
        self.viewers: dict[str, EstadoViewer] = {}

    # ------------------------------------------------------------------ ciclo

    def novo_round(self) -> None:
        """Zera o que e por partida; o historico do espectador permanece."""
        self.round.reiniciar()

    def estado_viewer(self, viewer_id: str) -> EstadoViewer:
        return self.viewers.setdefault(viewer_id, EstadoViewer())

    # --------------------------------------------------------------- decisao

    def avaliar(
        self,
        command_id: str,
        *,
        viewer_id: str,
        value_units: int,
        banido: bool = False,
        privilegiado: bool = False,
        round_ativo: bool = True,
        estado_mundo: Mapping[str, int] | None = None,
    ) -> Veredito:
        dados = get_command(command_id)
        agora = self._relogio()

        if banido:
            return Veredito(Decisao.RECUSAR, "banido")

        momento = "ROUND_ATIVO" if round_ativo else "ENTRE_ROUNDS"
        if momento not in dados["aplicavel_em"]:
            # Comando de proxima partida disparado no meio do round nao e
            # recusa: e exatamente o caso de adiar, e o espectador pagou.
            if "ENTRE_ROUNDS" in dados["aplicavel_em"]:
                return Veredito(Decisao.ADIAR, "fora_do_momento", momento)
            return Veredito(Decisao.RECUSAR, "fora_do_momento", momento)

        if dados.get("somente_moderador") and not privilegiado:
            return Veredito(Decisao.RECUSAR, "somente_moderador")

        if not privilegiado:
            veredito = self._checar_limites(dados, command_id, viewer_id, agora)
            if veredito is not None:
                return veredito

        veredito = self._checar_saturacao(dados, estado_mundo or {})
        if veredito is not None:
            return veredito

        custo = int(dados["custo_units"])
        if not privilegiado and int(value_units) < custo:
            return Veredito(Decisao.RECUSAR, "creditos_insuficientes", f"{value_units}/{custo}")

        return Veredito(Decisao.APLICAR)

    def _checar_limites(
        self,
        dados: Mapping,
        command_id: str,
        viewer_id: str,
        agora: float,
    ) -> Veredito | None:
        cooldown_global = float(dados.get("cooldown_global") or 0.0)
        ultimo_global = self.round.ultimo_uso_global.get(command_id)
        if ultimo_global is not None and agora - ultimo_global < cooldown_global:
            restante = cooldown_global - (agora - ultimo_global)
            return Veredito(Decisao.ADIAR, "cooldown_global", f"{restante:.1f}s")

        estado = self.estado_viewer(viewer_id)
        cooldown_viewer = float(dados["cooldown_viewer"])
        ultimo = estado.ultimo_uso.get(command_id)
        if ultimo is not None and agora - ultimo < cooldown_viewer:
            restante = cooldown_viewer - (agora - ultimo)
            return Veredito(Decisao.RECUSAR, "cooldown_viewer", f"{restante:.1f}s")

        usos = self.round.usos_por_comando.get(command_id, 0)
        if usos >= int(dados["max_por_round"]):
            return Veredito(Decisao.ADIAR, "teto_do_round", f"{usos}")

        return None

    def _checar_saturacao(
        self,
        dados: Mapping,
        estado_mundo: Mapping[str, int],
    ) -> Veredito | None:
        if dados["efeito"] not in {"AREA_SKILL", "PROJETIL_SKILL"}:
            return None
        vivas = int(estado_mundo.get("areas", 0)) + self.round.areas_de_espectador
        if vivas >= self.saturacao_max:
            return Veredito(Decisao.ADIAR, "saturacao", f"{vivas}")
        return None

    # -------------------------------------------------------------- registro

    def registrar_uso(self, command_id: str, viewer_id: str, *, custo: int = 0) -> None:
        """Contabiliza um comando efetivamente aplicado."""
        agora = self._relogio()
        dados = get_command(command_id)
        self.round.ultimo_uso_global[command_id] = agora
        self.round.usos_por_comando[command_id] = (
            self.round.usos_por_comando.get(command_id, 0) + 1
        )
        estado = self.estado_viewer(viewer_id)
        estado.ultimo_uso[command_id] = agora
        estado.creditos_gastos += int(custo)
        if dados["efeito"] in {"AREA_SKILL", "PROJETIL_SKILL"}:
            self.round.areas_de_espectador += 1


__all__ = [
    "SATURACAO_MAX_AREAS",
    "Decisao",
    "EstadoRound",
    "EstadoViewer",
    "PolicyEngine",
    "Veredito",
]
