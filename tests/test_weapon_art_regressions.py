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

    def test_grip_encurta_a_arma_mas_nao_move_a_ponta(self) -> None:
        """Rework Fase 1: a arma nasce na EMPUNHADURA — grip + cabo +
        lâmina = raio*range_mult. A ponta cai no mesmo alcance de antes;
        o que muda é onde a arma começa."""
        fake = SimpleNamespace()
        raio_char = 40.0
        grip = raio_char * 0.90
        c_px, l_px = Simulador._comprimentos_honestos(
            fake, "Reta", raio_char, 20, 60, grip_dist_px=grip
        )
        alvo = raio_char * get_hitbox_profile("Reta")["range_mult"]
        self.assertAlmostEqual(grip + c_px + l_px, alvo, places=6)

    def test_grip_profiles_cobrem_os_tipos_de_lamina(self) -> None:
        """Os tipos que nasciam no CENTRO do corpo têm grip; os que já
        orbitam fora (Arremesso/Orbital/Mágica) não ganham."""
        for tipo in ("Reta", "Dupla", "Corrente", "Arco", "Transformável"):
            self.assertIn(tipo, Simulador.GRIP_PROFILES)
        for tipo in ("Arremesso", "Orbital", "Mágica"):
            self.assertNotIn(tipo, Simulador.GRIP_PROFILES)


class AnimacaoRigidaTests(unittest.TestCase):
    def test_transform_nunca_escala_e_lunge_e_limitado(self) -> None:
        """Rework Fase 2: design FIXO — o transform exporta scale=1.0
        SEMPRE; o movimento é lunge da empunhadura, clampado."""
        from neural_fights.effects.weapon_animations import (
            WeaponAnimationManager,
        )

        mgr = WeaponAnimationManager()
        fid = 424242
        mgr.start_attack(fid, "Reta", (1.0, 1.0), 0.0, weapon_style="Martelo")
        for _ in range(40):  # varre todas as fases do golpe
            tf = mgr.get_weapon_transform(
                fid, "Reta", 0.0, (2.0, 1.0), 1 / 60, weapon_style="Martelo"
            )
            self.assertEqual(tf["scale"], 1.0)
            self.assertGreaterEqual(tf["lunge"], -0.30)
            self.assertLessEqual(tf["lunge"], 0.45)

    def test_conversao_escala_para_lunge(self) -> None:
        from neural_fights.effects.weapon_animations import WeaponAnimator

        self.assertAlmostEqual(WeaponAnimator._lunge_de(1.5), 0.35)
        self.assertAlmostEqual(WeaponAnimator._lunge_de(0.8), -0.14)
        self.assertAlmostEqual(WeaponAnimator._lunge_de(2.0), 0.45)  # clamp
        self.assertAlmostEqual(WeaponAnimator._lunge_de(0.3), -0.30)  # clamp


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
    """O telegraph de golpe pesado tem que separar lutadores QUE EXISTEM.

    Ate 11/09/2026 este teste usava forca 8 como "fraco" e 18 como "forte",
    e o corte no codigo era `forca < 12`. Tudo coerente entre si e sem
    relacao nenhuma com o jogo: o roster vai de 4,5 a 7,7, entao o corte
    nunca abria e o efeito NUNCA apareceu em video. O teste existia e
    passava — ele documentava a escala fantasma em vez de pega-la.

    Agora os dois lados vem do roster de verdade, e o corte de
    `LIMIARES_FORCA['heavy']`. Um teste de escala tem que estar ancorado no
    que a escala mede.
    """

    @staticmethod
    def _forcas_do_roster() -> list[float]:
        import json
        from pathlib import Path

        caminho = (Path(__file__).resolve().parents[1] / "neural_fights"
                   / "data" / "personagens.json")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        itens = dados if isinstance(dados, list) else list(dados.values())
        return sorted(float(p["forca"]) for p in itens
                      if isinstance(p, dict) and "forca" in p)

    def test_anticipation_so_nasce_para_golpe_pesado(self) -> None:
        from neural_fights.effects.attack import AttackAnimationManager

        forcas = self._forcas_do_roster()
        fraco_real, forte_real = forcas[0], forcas[-1]
        AttackAnimationManager.reset()
        try:
            manager = AttackAnimationManager()
            fraco = SimpleNamespace(
                dados=SimpleNamespace(forca=fraco_real), pos=[1.0, 1.0]
            )
            forte = SimpleNamespace(
                dados=SimpleNamespace(forca=forte_real), pos=[1.0, 1.0]
            )
            self.assertIsNone(manager.criar_anticipation(fraco))
            self.assertEqual(len(manager.anticipations), 0)
            self.assertIsNotNone(manager.criar_anticipation(forte))
            self.assertEqual(len(manager.anticipations), 1)
        finally:
            AttackAnimationManager.reset()

    def test_o_telegraph_tem_teto_como_toda_lista_de_vfx(self) -> None:
        """Sao dois lutadores: mais de dois telegraphs vivos e acumulo."""
        from neural_fights.effects.attack import AttackAnimationManager

        forte_real = self._forcas_do_roster()[-1]
        AttackAnimationManager.reset()
        try:
            manager = AttackAnimationManager()
            forte = SimpleNamespace(
                dados=SimpleNamespace(forca=forte_real), pos=[1.0, 1.0]
            )
            for _ in range(8):
                manager.criar_anticipation(forte)
            self.assertLessEqual(len(manager.anticipations),
                                 manager.MAX_ANTICIPATIONS)
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
