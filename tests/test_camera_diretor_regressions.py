"""Contratos da Onda 9: camera DIRETOR, resolucao nativa e sondas de video.

O que este arquivo trava:

1. A camera DIRETOR nunca perde um lutador, nao treme, nao faz punch, ignora
   oscilacao dentro da zona morta e fecha o quadro em METROS (o lutador
   ocupa >= 10% da largura no 9:16) — sem nunca tocar no combate.
2. `resolucao` do match_config e parseada com as mesmas regras do yuv420p.
3. As sondas do gravador (narrativa e camera) leem estado que o motor ja
   expoe e emitem cada momento UMA vez — testadas com fakes de contrato,
   sem abrir o Simulador (mesmo padrao dos demais testes de IA).

Gravacoes reais (caras) ficam em test_fight_recording_regressions.py.
"""

from __future__ import annotations

import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from neural_fights.effects.camera import Câmera  # noqa: E402
from neural_fights.recording.fight_recorder import (  # noqa: E402
    SondaCamera,
    SondaNarrativa,
    parse_resolucao,
)
from neural_fights.simulation.simulacao import Simulador  # noqa: E402
from neural_fights.utils.config import PPM  # noqa: E402

DT = 1.0 / 60.0


class _Lutador:
    """Fake de contrato: so o que a camera e as sondas leem."""

    def __init__(self, x: float, y: float) -> None:
        self.pos = [float(x), float(y)]
        self.z = 0.0
        self.raio_fisico = 0.425
        self.vida = 100.0
        self.vida_max = 100.0
        self.morto = False
        self.brain = _Brain()
        self.combo_contra = 0
        self.combo_contra_timer = 0.0


class _Brain:
    def __init__(self) -> None:
        self.tell_atual = None
        self.tempo_combate = 0.0


class _Sim:
    def __init__(self, cam=None) -> None:
        self.p1 = _Lutador(4.0, 5.0)
        self.p2 = _Lutador(10.0, 6.0)
        self.cam = cam
        self.round_finalizado = False
        self.vencedor_round_side = None


def _camera(largura: int = 1080, altura: int = 1920) -> Câmera:
    cam = Câmera(largura, altura)
    cam.set_arena_bounds(8.0, 5.5, 16.0, 11.0)   # Arena Pequena, aproximada
    cam.modo = "DIRETOR"
    return cam


def _assentar(cam: Câmera, a: _Lutador, b: _Lutador, segundos: float = 6.0) -> None:
    for _ in range(int(segundos / DT)):
        cam.atualizar(DT, a, b)


class CameraDiretorTests(unittest.TestCase):
    def test_nunca_perde_os_lutadores(self) -> None:
        """Herda a garantia bulletproof: um lutador corre e volta, os dois ficam."""
        cam = _camera()
        a, b = _Lutador(3.0, 3.0), _Lutador(6.0, 5.0)
        for i in range(900):
            t = i * DT
            b.pos[0] = 6.0 + 7.0 * math.sin(t * 1.7)
            b.pos[1] = 5.0 + 4.5 * math.sin(t * 2.3)
            a.pos[0] = 3.0 + 2.0 * math.sin(t * 0.9)
            cam.atualizar(DT, a, b)
            self.assertTrue(cam._lutador_visivel(a), f"p1 saiu do quadro no frame {i}")
            self.assertTrue(cam._lutador_visivel(b), f"p2 saiu do quadro no frame {i}")

    def test_sem_tremor_nem_punch(self) -> None:
        cam = _camera()
        a, b = _Lutador(6.0, 5.0), _Lutador(8.0, 6.0)
        _assentar(cam, a, b, 2.0)
        zoom_antes = cam.zoom
        cam.aplicar_shake(60.0, 1.0)
        cam.zoom_punch(0.6, 0.2)
        cam.atualizar(DT, a, b)
        self.assertEqual((0, 0), (cam.offset_x, cam.offset_y))
        self.assertEqual(0.0, getattr(cam, "_punch_mag", 0.0))
        self.assertLess(abs(cam.zoom - zoom_antes), 0.05, "punch vazou para o zoom")

    def test_zona_morta_ignora_oscilacao(self) -> None:
        """Passos curtos nao movem a camera: e a diferenca para o AUTO."""
        cam = _camera()
        a, b = _Lutador(6.0, 5.0), _Lutador(8.5, 6.0)
        _assentar(cam, a, b, 8.0)
        x, y = cam.x, cam.y
        for i in range(120):
            desloc = 0.04 * math.sin(i * 0.7)
            a.pos[0] = 6.0 + desloc
            b.pos[1] = 6.0 - desloc
            cam.atualizar(DT, a, b)
        self.assertAlmostEqual(x, cam.x, delta=1e-6)
        self.assertAlmostEqual(y, cam.y, delta=1e-6)

    def test_fecha_o_quadro_em_metros(self) -> None:
        """Dois lutadores proximos: o lutador ocupa >= 10% da largura do 9:16."""
        cam = _camera()
        a, b = _Lutador(7.0, 5.0), _Lutador(9.0, 5.5)
        _assentar(cam, a, b, 8.0)
        diametro = 2 * a.raio_fisico * PPM * cam.zoom
        self.assertGreaterEqual(diametro / cam.screen_width, 0.10)
        # ...e nunca alem do teto em metros (lado menor >= 7 m)
        self.assertLessEqual(cam.zoom, cam._diretor_teto_zoom() + 1e-9)
        self.assertGreaterEqual(cam.screen_width / cam.zoom / PPM, 7.0 - 1e-6)

    def test_pan_e_lento_e_converge(self) -> None:
        """Um deslocamento dentro da zona segura e seguido devagar, sem pulo."""
        cam = _camera()
        a, b = _Lutador(7.0, 5.0), _Lutador(9.0, 5.5)
        _assentar(cam, a, b, 8.0)
        a.pos[0] += 1.5
        b.pos[0] += 1.5
        maior_salto = 0.0
        for _ in range(300):
            x0, y0 = cam.x, cam.y
            cam.atualizar(DT, a, b)
            salto = math.hypot((cam.x - x0) * cam.zoom, (cam.y - y0) * cam.zoom)
            maior_salto = max(maior_salto, salto)
        self.assertLess(maior_salto, 0.03 * cam.screen_width, "pan deu solavanco")
        cx, cy = cam._calcular_centro_ideal(a, b)
        cx, cy = cam._limitar_centro_a_arena(cx, cy)
        distancia = math.hypot((cx - cam.x) * cam.zoom, (cy - cam.y) * cam.zoom)
        zona = cam.diretor_deadzone * min(cam.screen_width, cam.screen_height)
        self.assertLessEqual(distancia, zona + 1.0, "nao convergiu para a zona morta")

    def test_nocaute_fecha_um_pouco(self) -> None:
        cam = _camera()
        a, b = _Lutador(5.0, 5.0), _Lutador(11.0, 6.0)
        _assentar(cam, a, b, 6.0)
        antes = cam.zoom
        b.morto = True
        _assentar(cam, a, b, 3.0)
        self.assertGreater(cam.zoom, antes * 1.05)
        self.assertLessEqual(cam.zoom, cam._diretor_teto_zoom() + 1e-9)

    def test_clamp_macio_centra_a_luta_e_nao_a_arena(self) -> None:
        """Lutadores encostados na parede de cima ficam a ~1/3 do topo, nao colados."""
        cam = _camera()
        a, b = _Lutador(7.0, 0.6), _Lutador(9.0, 0.8)
        _assentar(cam, a, b, 8.0)
        _, sy = cam._get_posicao_tela(a)
        self.assertGreater(sy / cam.screen_height, 0.2)
        self.assertLess(sy / cam.screen_height, 0.5)

    def test_resolucao_do_match_config(self) -> None:
        self.assertEqual((1080, 1920), Simulador._resolver_resolucao("1080x1920"))
        self.assertEqual((1080, 1920), Simulador._resolver_resolucao([1081, 1921]))
        self.assertIsNone(Simulador._resolver_resolucao("abc"))
        self.assertIsNone(Simulador._resolver_resolucao((10, 10)))
        self.assertIsNone(Simulador._resolver_resolucao(None))
        self.assertEqual(Simulador._resolver_resolucao("1920X1080"), parse_resolucao("1920x1080"))


class SondaNarrativaTests(unittest.TestCase):
    def test_tell_vira_um_evento_por_ocorrencia(self) -> None:
        sim = _Sim()
        sonda = SondaNarrativa()
        sim.p1.brain.tell_atual = {"tipo": "parry", "ate": 0.5}
        for i in range(10):
            sim.p1.brain.tempo_combate = i * DT
            sonda.on_frame(sim, i * DT, i * DT)
        parries = [e for e in sonda.eventos if e["tipo"] == "parry"]
        self.assertEqual(1, len(parries))
        self.assertEqual("p1", parries[0]["slot"])
        # novo parry (outro `ate`) = novo evento
        sim.p1.brain.tell_atual = {"tipo": "parry", "ate": 2.0}
        sim.p1.brain.tempo_combate = 1.0
        sonda.on_frame(sim, 1.0, 1.0)
        self.assertEqual(2, len([e for e in sonda.eventos if e["tipo"] == "parry"]))

    def test_hesitacao_nao_vira_evento_e_plano_vira_com_throttle(self) -> None:
        """Onda 10C: o plano e sinal PUBLICO (rotulo sob o lutador) — a troca
        vira evento com rotulo, no maximo uma a cada PLANO_GAP_MIN_S por
        lutador. Hesitacao continua interna."""
        sim = _Sim()
        sonda = SondaNarrativa()
        sim.p2.brain.tell_atual = {"tipo": "hesitacao", "ate": 9.0}
        sonda.on_frame(sim, 0.1, 0.1)
        self.assertEqual([], [e for e in sonda.eventos if e["tipo"] == "hesitacao"])

        sim.p2.brain.tell_atual = {"tipo": "plano", "plano": "PRESSIONAR",
                                   "rotulo": "PRESSÃO", "ate": 9.0}
        sonda.on_frame(sim, 0.2, 0.2)
        planos = [e for e in sonda.eventos if e["tipo"] == "plano"]
        self.assertEqual(1, len(planos))
        self.assertEqual("PRESSÃO", planos[0]["rotulo"])
        self.assertEqual("p2", planos[0]["slot"])
        # Troca logo em seguida: dentro do throttle, nada.
        sim.p2.brain.tell_atual = {"tipo": "plano", "plano": "ACABAR",
                                   "rotulo": "ACABAR", "ate": 9.5}
        sonda.on_frame(sim, 1.5, 1.5)
        self.assertEqual(1, len([e for e in sonda.eventos if e["tipo"] == "plano"]))
        # Depois do intervalo, a nova troca vira evento.
        sim.p2.brain.tell_atual = {"tipo": "plano", "plano": "ACABAR",
                                   "rotulo": "ACABAR", "ate": 9.9}
        sonda.on_frame(sim, 5.0, 5.0)
        self.assertEqual(2, len([e for e in sonda.eventos if e["tipo"] == "plano"]))

    def test_combo_crescente_emite_cada_degrau_uma_vez(self) -> None:
        sim = _Sim()
        sonda = SondaNarrativa()
        sim.p2.combo_contra_timer = 1.0
        for n in (2, 2, 3, 3, 4):
            sim.p2.combo_contra = n
            sonda.on_frame(sim, 0.1, 0.1)
        combos = [e["n"] for e in sonda.eventos if e["tipo"] == "combo"]
        self.assertEqual([2, 3, 4], combos)
        # o combo acaba e outro comeca: conta de novo
        sim.p2.combo_contra_timer = 0.0
        sim.p2.combo_contra = 0
        sonda.on_frame(sim, 0.2, 0.2)
        sim.p2.combo_contra_timer = 1.0
        sim.p2.combo_contra = 2
        sonda.on_frame(sim, 0.3, 0.3)
        self.assertEqual([2, 3, 4, 2], [e["n"] for e in sonda.eventos if e["tipo"] == "combo"])

    def test_primeiro_sangue_credita_quem_bateu(self) -> None:
        sim = _Sim()
        sonda = SondaNarrativa()
        sonda.on_frame(sim, 2.0, 2.0, [(2.0, "p2", 12.0, "ataque_corpo_a_corpo")])
        sonda.on_frame(sim, 2.1, 2.1, [(2.1, "p1", 5.0, "ataque_corpo_a_corpo")])
        sangue = [e for e in sonda.eventos if e["tipo"] == "primeiro_sangue"]
        self.assertEqual(1, len(sangue))
        self.assertEqual("p1", sangue[0]["slot"])

    def test_virada_de_lideranca_e_ko(self) -> None:
        sim = _Sim()
        sonda = SondaNarrativa()
        t = 0.0
        # p1 lidera apos a aproximacao...
        sim.p2.vida = 60.0
        while t < 5.0:
            sonda.on_frame(sim, t, t)
            t += 0.25
        # ...e p2 vira
        sim.p1.vida = 20.0
        sim.p2.vida = 60.0
        while t < 8.0:
            sonda.on_frame(sim, t, t)
            t += 0.25
        viradas = [e for e in sonda.eventos if e["tipo"] == "virada"]
        self.assertEqual(1, len(viradas))
        self.assertEqual("p2", viradas[0]["slot"])
        sim.round_finalizado = True
        sim.vencedor_round_side = "p2"
        sonda.on_frame(sim, t, t)
        sonda.on_frame(sim, t + 0.1, t + 0.1)
        kos = [e for e in sonda.eventos if e["tipo"] == "ko"]
        self.assertEqual(1, len(kos))
        self.assertEqual("p2", kos[0]["slot"])


class SondaCameraTests(unittest.TestCase):
    def test_resumo_mede_pan_tamanho_e_visibilidade(self) -> None:
        cam = _camera()
        sim = _Sim(cam)
        sonda = SondaCamera()
        for i in range(300):
            sim.p2.pos[0] = 10.0 + 2.0 * math.sin(i * DT)
            cam.atualizar(DT, sim.p1, sim.p2)
            sonda.on_frame(sim, 1 / 30)
        resumo = sonda.resumo(10.0)
        self.assertEqual(300, resumo["frames"])
        self.assertEqual(1.0, resumo["pct_frames_visiveis"])
        self.assertGreater(resumo["tamanho_lutador_p50"], 0.05)
        self.assertIsNotNone(resumo["pan_p90_larguras_s"])
        self.assertLess(resumo["pan_p90_larguras_s"], 0.6)
        self.assertLessEqual(resumo["zoom_trocas_por_min"], 8.0)


if __name__ == "__main__":
    unittest.main()
