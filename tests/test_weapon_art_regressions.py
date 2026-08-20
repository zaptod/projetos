# -*- coding: utf-8 -*-
"""Contratos do Passe 4 do programa de arte (o golpe tem peso).

O que se trava aqui: a geometria honesta (ponta visual = alcance da
hitbox, mesma fórmula de core/hitbox.py); o zoom punch que sobrevive aos
clamps da câmera (somar no target_zoom era invisível); o telegraph que
só nasce para golpe pesado; a conversão mundo→tela das trilhas por
estilo; o letterbox do golpe letal escorrendo em relógio de parede; e o
dispatcher de tiers do efeito_visual que não explode para nenhum tier.
"""

import unittest
from types import SimpleNamespace

import pygame

from neural_fights.core.hitbox import get_hitbox_profile
from neural_fights.simulation.simulacao import Simulador
from neural_fights.utils.config import PPM


class GeometriaHonestaTests(unittest.TestCase):
    def test_ponta_visual_coincide_com_alcance_da_hitbox(self) -> None:
        """cabo+lamina desenhados = raio_char * range_mult do perfil —
        exatamente a fórmula de _calcular_hitbox_lamina."""
        fake = SimpleNamespace()
        raio_char = 40.0
        cabo, lamina = 20.0, 60.0
        c_px, l_px = Simulador._comprimentos_honestos(
            fake, "Reta", raio_char, cabo, lamina
        )
        alvo = raio_char * get_hitbox_profile("Reta")["range_mult"]
        self.assertAlmostEqual(c_px + l_px, alvo, places=6)
        # proporção cabo:lamina preservada
        self.assertAlmostEqual(c_px / l_px, cabo / lamina, places=6)

    def test_anim_scale_estica_apenas_a_lamina(self) -> None:
        fake = SimpleNamespace()
        c1, l1 = Simulador._comprimentos_honestos(fake, "Reta", 40.0, 20, 60)
        c2, l2 = Simulador._comprimentos_honestos(
            fake, "Reta", 40.0, 20, 60, anim_scale=1.5
        )
        self.assertAlmostEqual(c1, c2, places=6)
        self.assertAlmostEqual(l2, l1 * 1.5, places=6)


class ZoomPunchTests(unittest.TestCase):
    def test_punch_nao_escreve_mais_no_target_zoom(self) -> None:
        """O punch no target morria no clamp de segurança do frame
        seguinte; agora é bump decadente em campos próprios."""
        from neural_fights.effects.camera import Câmera

        cam = Câmera(800, 600)
        target_antes = cam.target_zoom
        cam.zoom_punch(0.25, 0.15)
        self.assertEqual(cam.target_zoom, target_antes)
        self.assertAlmostEqual(cam._punch_mag, 0.25)
        self.assertAlmostEqual(cam._punch_dur, 0.15)

    def test_punch_acumula_pegando_o_maior(self) -> None:
        from neural_fights.effects.camera import Câmera

        cam = Câmera(800, 600)
        cam.zoom_punch(0.25, 0.15)
        cam.zoom_punch(0.10, 0.15)
        self.assertAlmostEqual(cam._punch_mag, 0.25)


class TelegraphTests(unittest.TestCase):
    def test_anticipation_so_nasce_para_golpe_pesado(self) -> None:
        from neural_fights.effects.attack import AttackAnimationManager

        AttackAnimationManager.reset()
        try:
            manager = AttackAnimationManager()
            fraco = SimpleNamespace(
                dados=SimpleNamespace(forca=8), pos=[1.0, 1.0]
            )
            forte = SimpleNamespace(
                dados=SimpleNamespace(forca=18), pos=[1.0, 1.0]
            )
            self.assertIsNone(manager.criar_anticipation(fraco))
            self.assertEqual(len(manager.anticipations), 0)
            self.assertIsNotNone(manager.criar_anticipation(forte))
            self.assertEqual(len(manager.anticipations), 1)
        finally:
            AttackAnimationManager.reset()


class TrilhasPorEstiloTests(unittest.TestCase):
    def test_draw_trails_converte_metros_para_tela(self) -> None:
        """As posições da trilha vivem em METROS de mundo; o converter da
        câmera precisa ser aplicado antes dos renderers (pixel cru)."""
        from neural_fights.effects.weapon_animations import (
            WeaponAnimationManager,
        )

        manager = WeaponAnimationManager()
        fid = 12345
        state = manager.animator.get_state(fid)
        state.trail_positions = [(1.0, 2.0, 1.0), (3.0, 4.0, 0.5)]

        capturadas = []
        manager.trail_renderer.draw_trail = (
            lambda surface, positions, *a, **k: capturadas.append(positions)
        )
        manager.draw_trails(
            None, fid, (255, 255, 255), "Reta",
            converter=lambda x, y: (x + 7.0, y + 11.0),
        )
        self.assertEqual(len(capturadas), 1)
        x0, y0, a0 = capturadas[0][0]
        self.assertAlmostEqual(x0, 1.0 * PPM + 7.0)
        self.assertAlmostEqual(y0, 2.0 * PPM + 11.0)
        self.assertAlmostEqual(a0, 1.0)


class KillDramaTests(unittest.TestCase):
    def test_letterbox_escorre_em_relogio_de_parede(self) -> None:
        """avancar_relogio decrementa letterbox_timer com raw_dt — o
        letterbox some sozinho mesmo com slow-mo ativo."""
        fake = SimpleNamespace(
            slow_mo_timer=0.0,
            letterbox_timer=1.0,
            time_scale=1.0,
            vencedor=None,
            audio=None,
            _slow_mo_ended=False,
        )
        dt = Simulador.avancar_relogio(fake, 0.4)
        self.assertAlmostEqual(fake.letterbox_timer, 0.6)
        self.assertAlmostEqual(dt, 0.4)

    def test_epico_existe_no_vocabulario_do_game_feel(self) -> None:
        """O tier EPICO tem hit stop e shake próprios — o classificador
        do sim agora o emite (DEVASTADOR letal)."""
        from neural_fights.core.game_feel import HITSTOP_FRAMES

        self.assertIn("EPICO", HITSTOP_FRAMES)
        self.assertGreater(HITSTOP_FRAMES["EPICO"], HITSTOP_FRAMES["DEVASTADOR"])


class EfeitoVisualTests(unittest.TestCase):
    def test_todos_os_tiers_desenham_sem_explodir(self) -> None:
        fake = SimpleNamespace(tela=pygame.Surface((120, 120)))
        for efeito in (
            None, "brilho_leve", "brilho_medio", "particulas",
            "aura_dourada", "chamas_miticas",
        ):
            arma = SimpleNamespace(efeito_visual=efeito)
            Simulador._efeito_visual_raridade(
                fake, arma, (10, 60), (110, 60), (255, 165, 0), 5, 1234
            )


if __name__ == "__main__":
    unittest.main()
