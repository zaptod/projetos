# -*- coding: utf-8 -*-
"""Evidência de runtime do motor único de emoções (Onda 5C).

Os quatro consertos medidos pela investigação da Frente 2:
medo binário (0,00/1,00, zerado por nome de traço), frustração/tédio com
teto matemático abaixo dos thresholds de humor, momentum saturado em -1
em 70% dos frames (incrementos sem dt + DoT contando como hit), e
DESESPERADO inalcançável na escada de humor.
"""

import unittest
from types import SimpleNamespace

from neural_fights.ai.brain import AIBrain
from neural_fights.ai.emotions import EmotionSystem


class RngFixo:
    def __init__(self, valor: float = 0.0):
        self.valor = valor

    def random(self) -> float:
        return self.valor

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.valor

    def choice(self, opcoes):
        return opcoes[0]


def cerebro_fake(perfil=None, vida=100.0, vida_max=100.0, **extras):
    """Identidade mínima que o motor lê ao vivo do brain."""
    return SimpleNamespace(
        rng=RngFixo(0.0),
        tracos=[],
        perfil=perfil or {},
        parent=SimpleNamespace(vida=vida, vida_max=vida_max),
        momentum=0.0,
        modo_berserk=False,
        **extras,
    )


class MedoContinuoTests(unittest.TestCase):
    def test_frieza_multiplica_o_medo_mas_nunca_zera(self) -> None:
        """brain.py:2849 zerava o ganho de medo para DETERMINADO/FRIO.
        Agora coragem é multiplicador por eixo (frieza 1,0 -> x0,4)."""
        frio = EmotionSystem(cerebro_fake({"frieza": 1.0}, vida=20.0))
        covarde = EmotionSystem(cerebro_fake({"medo": 1.0}, vida=20.0))
        inimigo = SimpleNamespace(vida=100.0, vida_max=100.0)

        for _ in range(240):  # 4s a 60fps
            frio.atualizar(1 / 60, 5.0, inimigo, 10.0)
            covarde.atualizar(1 / 60, 5.0, inimigo, 10.0)

        self.assertGreater(frio.medo, 0.05)      # NUNCA zera
        self.assertLess(frio.medo, 0.30)         # mas a frieza segura
        self.assertGreater(covarde.medo, frio.medo * 2)

    def test_medo_e_gradiente_e_nao_interruptor(self) -> None:
        """Com 35% de vida o medo estabiliza no meio — antes era 0,00
        acima de 30% e saturado abaixo de 15%."""
        meio = EmotionSystem(cerebro_fake({}, vida=35.0))
        inimigo = SimpleNamespace(vida=100.0, vida_max=100.0)
        for _ in range(300):
            meio.atualizar(1 / 60, 5.0, inimigo, 10.0)
        self.assertGreater(meio.medo, 0.05)
        self.assertLess(meio.medo, 0.5)


class FrustracaoETedioTests(unittest.TestCase):
    def test_frustracao_e_seca_ofensiva_e_alcanca_o_threshold(self) -> None:
        """Frustração crescia só APANHANDO (+0,1/hit, teto ~0,27 < 0,5).
        Agora é não conseguir BATER: seca ofensiva cruza o threshold."""
        eng = EmotionSystem(cerebro_fake())
        eng.tempo_desde_hit = 10.0
        inimigo = SimpleNamespace(vida=100.0, vida_max=100.0)
        for _ in range(60):  # 1s de seca em pé de briga
            eng.atualizar(1 / 60, 5.0, inimigo, 20.0)
        self.assertGreaterEqual(eng.frustracao, 0.5)

    def test_acertar_alivia_frustracao(self) -> None:
        eng = EmotionSystem(cerebro_fake())
        eng.frustracao = 0.6
        eng.on_hit_dado()
        self.assertAlmostEqual(eng.frustracao, 0.35)

    def test_tedio_cresce_com_silencio_bilateral(self) -> None:
        """Ganho 0,6/s vs decay 0,6/s era empate eterno (teto matemático).
        O silêncio real agora vence o decay com folga."""
        eng = EmotionSystem(cerebro_fake())
        eng.tempo_desde_dano = 6.0
        eng.tempo_desde_hit = 6.0
        inimigo = SimpleNamespace(vida=100.0, vida_max=100.0)
        for _ in range(60):
            eng.atualizar(1 / 60, 10.0, inimigo, 30.0)
        self.assertGreaterEqual(eng.tedio, 0.5)


class EscadaDeHumorTests(unittest.TestCase):
    def test_desesperado_vence_no_fundo_do_poco(self) -> None:
        """DESESPERADO era penúltimo na escada e nunca aparecia."""
        eng = EmotionSystem(cerebro_fake(vida=12.0))
        eng.medo = 0.3
        eng.cd_mudanca_humor = 0.0
        eng.atualizar_humor()
        self.assertEqual(eng.humor, "DESESPERADO")

    def test_berserk_tem_produtor(self) -> None:
        """BERSERK existia no catálogo de HUMORES sem caminho até ele."""
        cerebro = cerebro_fake()
        cerebro.modo_berserk = True
        eng = EmotionSystem(cerebro)
        eng.cd_mudanca_humor = 0.0
        eng.atualizar_humor()
        self.assertEqual(eng.humor, "BERSERK")

    def test_euforico_precisa_de_excitacao_e_momentum(self) -> None:
        cerebro = cerebro_fake()
        cerebro.momentum = 0.6
        eng = EmotionSystem(cerebro)
        eng.excitacao = 0.9
        eng.confianca = 0.5
        eng.cd_mudanca_humor = 0.0
        eng.atualizar_humor()
        self.assertEqual(eng.humor, "EUFORICO")


class DotForaDaContagemTests(unittest.TestCase):
    def _brain(self, tipo_fonte):
        brain = object.__new__(AIBrain)
        brain.parent = SimpleNamespace(
            vida=90.0, vida_max=100.0, ultimo_tipo_fonte_dano=tipo_fonte
        )
        brain.ultimo_hp = 100.0
        brain.ultimo_dano_recebido = 0.0
        brain.rng = RngFixo(0.0)
        brain.tracos = []
        brain._perfil_chave = ()
        brain._perfil_cache = {}
        return brain

    def test_tick_de_dot_nao_conta_como_hit(self) -> None:
        """Queimar não é ser acertado: não quebra combo nem alimenta o
        susto/momentum — os ticks poluíam os contadores."""
        brain = self._brain("dot_encanto")
        brain._motor_emocional().combo_atual = 3
        brain._detectar_dano()
        self.assertEqual(brain.hits_recebidos_recente, 0)
        self.assertEqual(brain.combo_atual, 3)
        self.assertAlmostEqual(brain.ultimo_dano_recebido, 10.0)

    def test_golpe_real_conta(self) -> None:
        brain = self._brain("ataque_corpo_a_corpo")
        brain._detectar_dano()
        self.assertEqual(brain.hits_recebidos_recente, 1)
        self.assertEqual(brain.combo_atual, 0)


class MomentumTests(unittest.TestCase):
    def _brain(self):
        brain = object.__new__(AIBrain)
        brain.parent = SimpleNamespace(vida=100.0, vida_max=100.0)
        brain._acao_atual = "COMBATE"
        brain._acao_hold_ate = 0.0
        brain._acao_hold_prio = 9
        brain._modo_proposta = False
        brain.tempo_combate = 0.0
        brain.rng = RngFixo(0.0)
        brain.tracos = []
        brain._perfil_chave = ()
        brain._perfil_cache = {}
        brain.momentum = 0.0
        brain.pressao_aplicada = 0.0
        brain.pressao_recebida = 0.0
        return brain

    def test_meia_vida_de_4_segundos(self) -> None:
        """Decay era x0,995 POR FRAME; agora é meia-vida real de ~4s."""
        brain = self._brain()
        brain.momentum = 0.8
        inimigo = SimpleNamespace(vida=100.0, vida_max=100.0, brain=None)
        brain._atualizar_momentum(4.0, 10.0, inimigo)
        self.assertAlmostEqual(brain.momentum, 0.4, delta=0.02)

    def test_deriva_e_proporcional_ao_dt(self) -> None:
        """diff_hits x0,05 POR SEGUNDO — antes era por frame (-6/s com
        déficit de 2, saturava em -1 instantaneamente)."""
        brain = self._brain()
        brain._motor_emocional().hits_dados_recente = 2
        inimigo = SimpleNamespace(vida=100.0, vida_max=100.0, brain=None)
        brain._atualizar_momentum(1.0, 10.0, inimigo)
        self.assertAlmostEqual(brain.momentum, 0.1, delta=0.01)


if __name__ == "__main__":
    unittest.main()
