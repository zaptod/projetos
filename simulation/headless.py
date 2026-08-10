"""Execução determinística do motor real sem janela ou arquivo de configuração."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .simulacao import Simulador


@dataclass(frozen=True)
class HeadlessMatchResult:
    """Resultado serializável de uma execução do motor de combate."""

    success: bool
    winner: str | None
    winner_slot: str | None
    reason: str
    duration: float
    frames: int
    seed: int
    p1_name: str
    p2_name: str
    p1_hp: float
    p2_hp: float
    p1_hp_ratio: float
    p2_hp_ratio: float
    error: str | None = None

    @property
    def is_draw(self) -> bool:
        return self.success and self.winner_slot is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HeadlessMatchRunner:
    """Controla somente relógio/seed; todas as regras vivem em Simulador.update."""

    def __init__(
        self,
        match_config: Mapping[str, Any],
        *,
        fixed_dt: float = 1.0 / 60.0,
        max_frames: int | None = None,
        max_duration: float = 120.0,
        seed: int = 0,
    ) -> None:
        if not isinstance(match_config, Mapping):
            raise TypeError("match_config precisa ser um mapeamento")
        if fixed_dt <= 0.0:
            raise ValueError("fixed_dt precisa ser positivo")
        if max_duration <= 0.0:
            raise ValueError("max_duration precisa ser positivo")
        if max_frames is None:
            max_frames = math.ceil(max_duration / fixed_dt)
        if max_frames <= 0:
            raise ValueError("max_frames precisa ser positivo")

        self.match_config = dict(match_config)
        self.match_config["best_of"] = 1
        self.fixed_dt = float(fixed_dt)
        self.max_frames = int(max_frames)
        self.seed = int(seed)

    @staticmethod
    def _fighter_snapshot(fighter) -> tuple[str, float, float]:
        name = str(fighter.dados.nome)
        hp = max(0.0, float(fighter.vida))
        hp_max = max(1e-9, float(fighter.vida_max))
        return name, hp, hp / hp_max

    def _result_from_simulator(
        self,
        simulator: Simulador,
        *,
        frames: int,
        reason: str,
        winner_slot: str | None,
    ) -> HeadlessMatchResult:
        p1_name, p1_hp, p1_ratio = self._fighter_snapshot(simulator.p1)
        p2_name, p2_hp, p2_ratio = self._fighter_snapshot(simulator.p2)
        winner = (
            p1_name if winner_slot == "p1"
            else p2_name if winner_slot == "p2"
            else None
        )
        return HeadlessMatchResult(
            success=True,
            winner=winner,
            winner_slot=winner_slot,
            reason=reason,
            duration=frames * self.fixed_dt,
            frames=frames,
            seed=self.seed,
            p1_name=p1_name,
            p2_name=p2_name,
            p1_hp=p1_hp,
            p2_hp=p2_hp,
            p1_hp_ratio=p1_ratio,
            p2_hp_ratio=p2_ratio,
        )

    def _time_limit_result(self, simulator: Simulador) -> HeadlessMatchResult:
        _, _, p1_ratio = self._fighter_snapshot(simulator.p1)
        _, _, p2_ratio = self._fighter_snapshot(simulator.p2)
        tolerance = 1e-9
        if p1_ratio > p2_ratio + tolerance:
            winner_slot = "p1"
            reason = "time_limit_decision"
        elif p2_ratio > p1_ratio + tolerance:
            winner_slot = "p2"
            reason = "time_limit_decision"
        else:
            winner_slot = None
            reason = "time_limit_draw"
        return self._result_from_simulator(
            simulator,
            frames=self.max_frames,
            reason=reason,
            winner_slot=winner_slot,
        )

    def run(self) -> HeadlessMatchResult:
        """Executa exatamente ``Simulador.update(fixed_dt)`` até um terminal."""
        random_state = random.getstate()
        simulator = None
        frames = 0
        try:
            random.seed(self.seed)
            simulator = Simulador(
                match_config=self.match_config,
                headless=True,
                seed=self.seed,
            )
            for frames in range(1, self.max_frames + 1):
                simulator.update(self.fixed_dt)
                if simulator.round_finalizado:
                    if simulator.p1.morto and simulator.p2.morto:
                        reason = "double_ko"
                    else:
                        reason = "knockout"
                    return self._result_from_simulator(
                        simulator,
                        frames=frames,
                        reason=reason,
                        winner_slot=simulator.vencedor_round_side,
                    )
            return self._time_limit_result(simulator)
        except Exception as exc:
            p1_name = str(self.match_config.get("p1_nome") or "")
            p2_name = str(self.match_config.get("p2_nome") or "")
            return HeadlessMatchResult(
                success=False,
                winner=None,
                winner_slot=None,
                reason="error",
                duration=frames * self.fixed_dt,
                frames=frames,
                seed=self.seed,
                p1_name=p1_name,
                p2_name=p2_name,
                p1_hp=0.0,
                p2_hp=0.0,
                p1_hp_ratio=0.0,
                p2_hp_ratio=0.0,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if simulator is not None:
                simulator.close()
            random.setstate(random_state)


def run_headless_match(
    match_config: Mapping[str, Any],
    **runner_options: Any,
) -> HeadlessMatchResult:
    """Atalho funcional usado por CLI e torneio."""
    return HeadlessMatchRunner(match_config, **runner_options).run()


__all__ = [
    "HeadlessMatchResult",
    "HeadlessMatchRunner",
    "run_headless_match",
]
