"""Regressoes para o consumo de Previsao pela IA defensiva."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from neural_fights.ai.brain import AIBrain
from neural_fights.core.combat import Buff
from tests import test_remaining_skill_regressions as _helpers


class PredictionAIRegressionTests(unittest.TestCase):
    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    @staticmethod
    def _brain(parent):
        brain = object.__new__(AIBrain)
        brain.parent = parent
        brain.modo_berserk = False
        brain.confianca = 0.5
        brain.tracos = ["IMPRUDENTE"]
        brain.quirks = []
        brain.leitura_oponente = {"ataque_iminente": True}
        brain.rng = Mock()
        brain.rng.uniform.return_value = 0.2
        brain.rng.random.return_value = 1.0
        brain.tempo_reacao_base = 0.2
        brain.variacao_timing = 0.1
        brain.adrenalina = 0.0
        brain.medo = 0.0
        brain.congelamento = 0.0
        return brain

    def test_prediction_bypasses_human_reaction_delay_and_probability(self):
        defender = self._fighter("Seer")
        attacker = self._fighter("Attacker", x=1.0)
        defender.buffs_ativos.append(Buff("Previsão", defender))
        brain = self._brain(defender)

        with (
            patch.object(
                brain,
                "_analisar_projeteis_vindo",
                return_value={"vindo": False, "urgencia": 0.0},
            ),
            patch.object(
                brain,
                "_analisar_areas_perigo",
                return_value={"perigo": False, "urgencia": 0.0},
            ),
            patch.object(brain, "_calcular_direcao_desvio", return_value=90.0),
            patch.object(brain, "_executar_desvio", return_value=True) as executar,
        ):
            reacted = brain._processar_desvio_inteligente(1.0 / 60.0, 1.0, attacker)

        self.assertTrue(reacted)
        brain.rng.uniform.assert_not_called()
        brain.rng.random.assert_not_called()
        executar.assert_called_once()

    def test_without_prediction_preserves_normal_reaction_gate(self):
        defender = self._fighter("Fighter")
        attacker = self._fighter("Attacker", x=1.0)
        brain = self._brain(defender)

        with (
            patch.object(
                brain,
                "_analisar_projeteis_vindo",
                return_value={"vindo": False, "urgencia": 0.0},
            ),
            patch.object(
                brain,
                "_analisar_areas_perigo",
                return_value={"perigo": False, "urgencia": 0.0},
            ),
            patch.object(brain, "_executar_desvio", return_value=True) as executar,
        ):
            reacted = brain._processar_desvio_inteligente(1.0 / 60.0, 1.0, attacker)

        self.assertFalse(reacted)
        brain.rng.uniform.assert_called_once()
        brain.rng.random.assert_called_once()
        executar.assert_not_called()


class _RngFixo:
    def __init__(self, valor=0.0):
        self.valor = valor

    def random(self):
        return self.valor

    def uniform(self, a, b):
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


class DesvioReligadoTests(unittest.TestCase):
    """Onda 8C: o subsistema de desvio saiu do limbo — evidência de runtime."""

    _fighter = staticmethod(_helpers.RemainingSkillRegressionTests._fighter)

    def _brain_vivo(self, parent):

        brain = object.__new__(AIBrain)
        brain.parent = parent
        brain.modo_berserk = False
        brain.confianca = 0.5
        brain.tracos = []
        brain.quirks = []
        brain.leitura_oponente = {
            "ataque_iminente": False,
            "tendencia_esquerda": 0.5,
        }
        brain.rng = _RngFixo(0.0)
        brain.tempo_reacao_base = 0.12
        brain.variacao_timing = 0.0
        brain.adrenalina = 0.0
        brain.medo = 0.0
        brain.congelamento = 0.0
        brain.dir_circular = 1
        brain.cd_dash = 5.0  # sem skill de dash neste cenário
        brain.cd_pulo = 5.0  # sem pulo: cai no impulso lateral
        brain.skills_por_tipo = {"DASH": []}
        brain._espacial = None
        brain._perfil_chave = ()
        brain._perfil_cache = {}
        # Escritor único (mesmo scaffold da suíte de instintos).
        brain._acao_atual = "COMBATE"
        brain._acao_fonte = "init"
        brain._acao_hold_ate = 0.0
        brain._acao_hold_prio = 9
        brain._modo_proposta = False
        brain._contexto_escrita = 1
        brain.tempo_combate = 10.0
        brain.contadores = {
            "decisoes": 0,
            "pilha_completa": 0,
            "escritas_aceitas": 0,
            "escritas_seguradas": 0,
        }
        return brain

    def test_projetil_em_rota_gera_desvio_fisico(self):
        from types import SimpleNamespace

        from neural_fights.ai.percepcao import PercepcaoMundo

        defensor = self._fighter("Alvo")
        atacante = self._fighter("Arqueiro", x=6.0)
        proj = SimpleNamespace(
            ativo=True, dono=atacante, x=4.0, y=5.0, angulo=180.0, vel=20.0
        )
        defensor.percepcao = PercepcaoMundo(SimpleNamespace(projeteis=[proj]))
        brain = self._brain_vivo(defensor)

        reagiu = brain._processar_desvio_inteligente(1 / 60, 6.0, atacante)

        self.assertTrue(reagiu)
        # O desvio é FÍSICO: impulso lateral real, não só rótulo.
        velocidade = (defensor.vel[0] ** 2 + defensor.vel[1] ** 2) ** 0.5
        self.assertGreater(velocidade, 5.0)
        self.assertIn(brain.acao_atual, ("CIRCULAR", "FLANQUEAR", "DESVIO"))

    def test_projetil_se_afastando_nao_gera_desvio(self):
        from types import SimpleNamespace

        from neural_fights.ai.percepcao import PercepcaoMundo

        defensor = self._fighter("Alvo")
        atacante = self._fighter("Arqueiro", x=6.0)
        proj = SimpleNamespace(
            ativo=True, dono=atacante, x=4.0, y=5.0, angulo=0.0, vel=20.0
        )
        defensor.percepcao = PercepcaoMundo(SimpleNamespace(projeteis=[proj]))
        brain = self._brain_vivo(defensor)

        self.assertFalse(
            brain._processar_desvio_inteligente(1 / 60, 6.0, atacante)
        )

    def test_direcao_de_desvio_evita_a_parede(self):
        from types import SimpleNamespace

        from neural_fights.ai.spatial import SpatialAwarenessSystem

        defensor = self._fighter("Alvo", x=5.0)
        defensor.pos = [5.0, 7.5]
        inimigo = self._fighter("Inimigo", x=0.0)
        inimigo.pos = [0.0, 7.5]
        brain = self._brain_vivo(defensor)
        brain.dir_circular = -1  # escolheria +y: direto contra a parede

        # Arena fake: parede em y >= 8 (ponto fora), sem obstáculos.
        arena = SimpleNamespace(
            colide_obstaculo=lambda x, y, r: False,
            ponto_dentro=lambda x, y: y < 8.0,
        )
        espacial = SpatialAwarenessSystem(defensor, rng=brain.rng)
        espacial._arena_cache = arena
        brain._espacial = espacial
        brain.consciencia_espacial = espacial.consciencia
        brain.tatica_espacial = espacial.tatica

        direcao = brain._calcular_direcao_desvio(
            "ATAQUE_FISICO", 5.0, inimigo, {}
        )
        import math as _math
        destino_y = defensor.pos[1] + _math.sin(_math.radians(direcao)) * 1.5
        self.assertLess(destino_y, 8.0)


if __name__ == "__main__":
    unittest.main()
