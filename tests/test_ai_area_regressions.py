"""Regression tests for weapon-aware AI and multi-wave area effects."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import neural_fights.ai.brain as brain_module
from neural_fights.ai.brain import AIBrain
from neural_fights.core.combat import AreaEffect
from neural_fights.simulation.simulacao import Simulador


class TwinDaggersAIRegressionTests(unittest.TestCase):
    def test_ai_can_react_to_enemy_twin_daggers(self):
        """The Twin Daggers counterplay branch must use the brain's real state."""
        own_weapon = SimpleNamespace(distancia=4.0)
        parent = SimpleNamespace(dados=SimpleNamespace(arma_obj=own_weapon))
        enemy = SimpleNamespace(
            dados=SimpleNamespace(
                arma_obj=SimpleNamespace(tipo="Dupla", estilo="Adagas Gêmeas")
            )
        )

        # Construct only the state used by the weapon modifier.  In particular,
        # this avoids creating a fighter, pygame display, or full simulation.
        brain = object.__new__(AIBrain)
        brain.parent = parent
        brain.percepcao_arma = {
            "estrategia_recomendada": "neutro",
            "matchup_favoravel": 0.0,
            "arma_inimigo_tipo": "Dupla",
        }
        brain.confianca = 0.5
        brain.tracos = []
        # Re-pino Onda 5B: _aplicar_modificadores_armas é um ESTÁGIO da
        # pilha — em produção roda dentro do modo-proposta de
        # _decidir_movimento (rascunho livre, sem min-hold). O scaffold
        # reproduz esse contexto.
        brain._modo_proposta = True
        brain.acao_atual = "COMBATE"

        with (
            patch.object(brain_module, "WEAPON_ANALYSIS_AVAILABLE", True),
            patch.object(brain_module.random, "random", return_value=0.0),
            patch.object(brain_module.random, "choice", side_effect=lambda options: options[0]),
        ):
            brain._aplicar_modificadores_armas(distancia=1.0, inimigo=enemy)

        self.assertEqual(brain.acao_atual, "RECUAR")


class MultiWaveAreaRegressionTests(unittest.TestCase):
    @staticmethod
    def _fighter():
        return SimpleNamespace(
            pos=[0.0, 0.0],
            morto=False,
            raio_fisico=0.5,
            buffer_projeteis=[],
            buffer_orbes=[],
            buffer_areas=[],
            buffer_beams=[],
            buffer_summons=[],
            buffer_traps=[],
        )

    def test_wrath_of_nature_wave_is_consumed_by_simulation(self):
        """AreaEffect's wave event must satisfy Simulador.update's contract."""
        owner = self._fighter()
        target = self._fighter()
        area = AreaEffect("Wrath of Nature", 7.5, 3.25, owner)

        self.assertEqual(area.ondas, 3)
        self.assertEqual(area.atualizar(area.delay, [owner, target]), [])

        # Bypass Simulador.__init__ so pygame/display/audio are never initialized,
        # while still exercising the real producer and the real update consumer.
        simulation = object.__new__(Simulador)
        simulation.cam = SimpleNamespace(atualizar=lambda _dt, _p1, _p2: None)
        simulation.p1 = owner
        simulation.p2 = target
        simulation.paused = False
        simulation.textos = []
        simulation.shockwaves = []
        simulation.game_feel = None
        simulation.hit_stop_timer = 0.0
        simulation.impact_flashes = []
        simulation.magic_clashes = []
        simulation.block_effects = []
        simulation.dash_trails = []
        simulation.hit_sparks = []
        simulation.magic_vfx = None
        simulation.projeteis = []
        simulation.areas = [area]
        simulation._verificar_clash_projeteis = lambda: None
        simulation.audio = None
        simulation.vencedor = "fixture-already-finished"
        simulation.movement_anims = None
        simulation.attack_anims = None
        simulation.particulas = []
        simulation.decals = []

        simulation.update(area.intervalo_onda)

        spawned_waves = [candidate for candidate in simulation.areas if candidate is not area]
        self.assertEqual(len(spawned_waves), 1)
        spawned_wave = spawned_waves[0]
        self.assertEqual((spawned_wave.x, spawned_wave.y), (area.x, area.y))
        self.assertGreater(
            spawned_wave.raio,
            area.raio,
            "a nova onda precisa ampliar o raio efetivo, nao apenas um atributo auxiliar",
        )


if __name__ == "__main__":
    unittest.main()
