# -*- coding: utf-8 -*-
"""Evidência de regressão do Passe 2 do programa de arte (fundação).

Os bugs aqui pinados existiram em produção: a live inteira ficava em
câmera lenta para sempre após um dodge (slow_mo_timer só decrementava no
run() que a LiveSession nunca chama), o manager de animação de arma
vazava efeitos sem limite, e as fontes eram recriadas a cada frame.
"""

import unittest
from types import SimpleNamespace

from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.palette import (
    ELEMENT_PALETTES,
    cor_classe,
    resolver_elemento,
)


class RelogioDeDramaTests(unittest.TestCase):
    def _sim_minimo(self) -> Simulador:
        sim = object.__new__(Simulador)
        sim.slow_mo_timer = 0.0
        sim.time_scale = 1.0
        sim.vencedor = None
        sim.audio = None
        sim._slow_mo_ended = False
        return sim

    def test_slow_mo_expira_e_restaura_time_scale(self) -> None:
        """O PIOR bug de show: dodge setava 0.5x e nada restaurava na
        live. avancar_relogio é o relógio único de drama."""
        sim = self._sim_minimo()
        sim.slow_mo_timer = 0.1
        sim.time_scale = 0.5
        dt = sim.avancar_relogio(0.2)
        self.assertEqual(sim.time_scale, 1.0)
        self.assertAlmostEqual(dt, 0.2)

    def test_sem_slow_mo_devolve_dt_escalado(self) -> None:
        sim = self._sim_minimo()
        sim.time_scale = 0.2  # KO recem-ativado
        sim.slow_mo_timer = 2.0
        dt = sim.avancar_relogio(1.0 / 60.0)
        self.assertAlmostEqual(dt, (1.0 / 60.0) * 0.2)
        self.assertGreater(sim.slow_mo_timer, 0)


class VazamentoDeEfeitosTests(unittest.TestCase):
    def test_active_effects_tem_teto(self) -> None:
        """O manager criava Slash/Thrust em cada ataque e nunca podava."""
        from neural_fights.effects.weapon_animations import (
            get_weapon_animation_manager,
        )

        manager = get_weapon_animation_manager()
        vivo = SimpleNamespace(update=lambda dt: True, draw=lambda *a: None)
        manager.active_effects = [vivo] * 200
        manager.update(1.0 / 60.0)
        self.assertLessEqual(len(manager.active_effects), 64)
        manager.active_effects = []


class PaletaCentralTests(unittest.TestCase):
    def test_doze_elementos_do_catalogo(self) -> None:
        """TEMPO e GRAVITACAO caíam no DEFAULT cinza."""
        for elemento in (
            "FOGO", "GELO", "RAIO", "TREVAS", "LUZ", "NATUREZA",
            "ARCANO", "CAOS", "SANGUE", "VOID", "TEMPO", "GRAVITACAO",
        ):
            self.assertIn(elemento, ELEMENT_PALETTES)
            self.assertIn("core", ELEMENT_PALETTES[elemento])

    def test_resolvedor_prefere_o_campo_do_objeto(self) -> None:
        """As heurísticas de substring IGNORAVAM proj.elemento."""
        proj = SimpleNamespace(elemento="GELO")
        self.assertEqual(resolver_elemento(proj, "Bola de Fogo", None), "GELO")
        self.assertEqual(resolver_elemento(None, "Buraco Negro", None), "GRAVITACAO")

    def test_cor_de_classe_acessivel_ao_jogo(self) -> None:
        """CORES_CLASSE vivia só no tema Tkinter, em hex."""
        self.assertEqual(cor_classe("Duelista (Precisão)"), (255, 215, 0))
        self.assertEqual(cor_classe("Cavaleiro"), (70, 130, 180))


class CacheDeFontesTests(unittest.TestCase):
    def test_sobrevive_a_quit_e_reinit_externo(self) -> None:
        """Testes fazem font.quit(); fontes da geração anterior morrem e
        o cache precisa detectar (sonda de geração)."""
        import pygame

        from neural_fights.utils.fonts import get_fonte

        pygame.font.init()
        f1 = get_fonte(16)
        pygame.font.quit()
        pygame.font.init()  # reinit por FORA do helper
        f2 = get_fonte(16)
        self.assertIsNot(f1, f2)
        f2.render("ok", True, (255, 255, 255))  # não explode


if __name__ == "__main__":
    unittest.main()
