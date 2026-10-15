# -*- coding: utf-8 -*-
"""O vencedor nunca fica atras do letreiro do K.O. (15/10/2026, conferente).

No Vulcao, o limite vertical da camera pos-K.O. (05bf5f0) subiu o vencedor
para dentro do "ACABOU": o nome entrou atras do "BOU" aos ~16,3 s e a
cabeca aos ~16,5 s, ate o letreiro sumir. O letreiro e do renderer (callout
do K.O., ``fight_callouts``); a camera e do gravador. A ponte:

- ``runner.reserva_do_letreiro(perfil)`` mede a caixa REAL do letreiro (o
  renderer desenha cada texto de K.O. no pico do pop-in) e a duracao do
  callout, e o gravador passa isso a camera (``--reserva-pos-ko``);
- enquanto o letreiro esta na tela, o topo da area pos-K.O. fica abaixo dele
  (``Camera._area_pos_ko``) e o rosto e empurrado para fora no quadro de
  agora; quando ele some, a area volta suave.

O teste roda a camera da cauda nas arenas Vulcao e Torre, com o letreiro
medido a cada passo (o pop-in muda o tamanho) e compara com a caixa do
rosto + nome do vencedor. O caso zero (sem reserva) tem de acusar.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from types import SimpleNamespace  # noqa: E402

from builds.generation.session_generator import load_config  # noqa: E402
from builds.tournament.runner import reserva_do_letreiro  # noqa: E402
from builds.video.renderer import caixa_do_letreiro  # noqa: E402


def _lutador(x, y, morto=False, tamanho=1.0):
    return SimpleNamespace(pos=[x, y], z=0.0, morto=morto, raio_fisico=tamanho / 4.0,
                           dados=SimpleNamespace(tamanho=tamanho))


class LetreiroDoKoTests(unittest.TestCase):
    PERFIL = "celular"
    LARGURA, ALTURA = 1080, 1920
    TEXTO = "ACABOU"

    @classmethod
    def setUpClass(cls):
        cls.render = load_config("render.json")
        cls.duracao = float((load_config("editing.json").get("fight_callouts") or {})
                            .get("duracao", 0.9))
        # a caixa do letreiro em cada idade (o pop-in encolhe nos 0,12 s)
        cls.caixas = {}

    def _letreiro(self, idade):
        chave = round(idade, 3)
        if chave not in self.caixas:
            self.caixas[chave] = caixa_do_letreiro(self.render, self.PERFIL, self.TEXTO, idade)
        return self.caixas[chave]

    def _cauda(self, arena, vencedor, perdedor, reserva):
        from neural_fights.core.arena import ARENAS
        from neural_fights.effects.camera import Câmera
        from neural_fights.utils.config import PPM

        cfg = ARENAS[arena]
        cam = Câmera(self.LARGURA, self.ALTURA)
        cam.set_arena_bounds(cfg.largura / 2, cfg.altura / 2, cfg.largura, cfg.altura)
        cam.modo = "DIRETOR"
        cam.diretor_largura_min_m = 5.5
        cam.reserva_pos_ko = reserva
        # o letreiro (0,95 s) acaba antes da fanfarra (1,2 s): o pulo da festa
        # ainda nao comecou enquanto ele esta na tela, como no Simulador
        cam.pulo_pos_ko = 0.0
        # o quadro do fim da luta: os dois enquadrados, no limite da arena
        cam.zoom = cam._calcular_zoom_necessario(vencedor, perdedor,
                                                  zoom_max=cam._diretor_teto_zoom())
        cam.x, cam.y = cam._limitar_centro_a_arena(*cam._calcular_centro_ideal(vencedor, perdedor))
        colisoes, parede = [], 0.0
        self.degraus = []                         # px por quadro de 30 fps
        quadro_anterior = (cam.x, cam.y, cam.zoom)
        # slow-mo (1,2 s de parede a 0,25x) e a festa, passos de 60 Hz
        for k, dt in enumerate([0.25 / 60] * 72 + [1 / 60] * 91):
            t_parede = (k + 1) / 60
            cam.t_pos_ko = t_parede
            cam.atualizar(dt, vencedor, perdedor)
            if k % 2 == 1:                        # um quadro do video
                agora = (cam.x, cam.y, cam.zoom)
                self.degraus.append((round(t_parede, 3),
                                     cam._degrau_na_tela(quadro_anterior, agora)))
                quadro_anterior = agora
            if t_parede > self.duracao:          # alfa do letreiro = 0
                continue
            letreiro = self._letreiro(t_parede)
            x0, y0, x1, y1 = cam.caixa_do_rosto(vencedor, cam.zoom, cam.pulo_pos_ko)
            sx0, sy0 = cam.converter(x0, y0)
            sx1, sy1 = cam.converter(x1, y1)
            if letreiro and sx0 < letreiro[2] and sx1 > letreiro[0] \
                    and sy0 < letreiro[3] and sy1 > letreiro[1]:
                colisoes.append((round(t_parede, 3), sy0, letreiro[3]))
            parede = max(parede, (cam.x / PPM))
        return cam, colisoes

    CENAS = {
        # (arena, vencedor (x, y), perdedor (x, y)): longe (so o vencedor),
        # perto (os dois) e o vencedor encostado na parede
        "Vulcao": [((20.0, 8.0), (6.0, 20.0)), ((13.0, 10.0), (14.0, 10.5)),
                   ((24.6, 13.0), (12.0, 13.0))],
        "Torre": [((5.0, 4.0), (5.0, 14.0)), ((5.0, 9.0), (6.0, 9.3)),
                  ((9.6, 9.0), (3.0, 14.0))],
    }

    def test_rosto_e_nome_nunca_cruzam_o_letreiro(self):
        reserva = reserva_do_letreiro(self.PERFIL)
        self.assertIsNotNone(reserva)
        for arena, cenas in self.CENAS.items():
            for v, p in cenas:
                with self.subTest(arena=arena, vencedor=v, perdedor=p):
                    _cam, colisoes = self._cauda(arena, _lutador(*v), _lutador(*p, morto=True),
                                                 reserva)
                    self.assertEqual(colisoes, [], colisoes[:3])

    def test_nenhum_degrau_de_camera_passa_de_12_px_por_quadro_no_primeiro_segundo(self):
        """Vulcao (15/10): a garantia por quadro usava o pulo MAXIMO e
        empurrava a camera 34 px no 1o quadro com o ACABOU, sem o vencedor
        estar atras dele. Do K.O. ao K.O.+1 s, nenhum degrau > 12 px.

        Fora: a cena em que a luta ACABOU com o vencedor atras do letreiro
        (Torre, vencedor no alto): ali ele sai de uma vez, junto com o K.O."""
        reserva = reserva_do_letreiro(self.PERFIL)
        for arena, cenas in self.CENAS.items():
            for v, p in cenas:
                vencedor, perdedor = _lutador(*v), _lutador(*p, morto=True)
                if self._atras_no_ko(arena, vencedor, perdedor, reserva):
                    continue
                with self.subTest(arena=arena, vencedor=v, perdedor=p):
                    self._cauda(arena, vencedor, perdedor, reserva)
                    um_segundo = [d for t, d in self.degraus if t <= 1.0 + 1e-6]
                    self.assertLessEqual(max(um_segundo), 12.0, max(um_segundo))

    def test_caso_zero_o_pulo_maximo_empurraria(self):
        """Sem o pulo ATUAL (o maximo na garantia por quadro), a mesma cena do
        Vulcao leva um empurrao no 1o quadro."""
        from unittest import mock

        from neural_fights.effects.camera import Câmera

        reserva = reserva_do_letreiro(self.PERFIL)
        letreiro = reserva["topo"]

        def empurrao(pulo_atual):
            # a cena do Vulcao: zoom do duelo, o rosto (sem pulo) 44 px abaixo
            # do letreiro — livre — no 1o quadro com o ACABOU
            cam = Câmera(self.LARGURA, self.ALTURA)
            cam.zoom = 3.6
            cam.pulo_pos_ko = pulo_atual
            vencedor = _lutador(10.0, 10.0)
            _x0, y0, _x1, _y1 = cam.caixa_do_rosto(vencedor, cam.zoom, 0.0)
            alvo_tela = letreiro * self.ALTURA + 44
            cam.y = y0 - (alvo_tela - self.ALTURA / 2) / cam.zoom
            antes = cam.y
            cam._tirar_rosto_do_letreiro(vencedor, letreiro)
            return abs(cam.y - antes) * cam.zoom

        self.assertEqual(empurrao(0.0), 0.0)                 # o pulo de agora: nada
        with mock.patch.object(Câmera, "pulo_pos_ko", None, create=True):
            self.assertGreater(empurrao(None), 12.0)         # o maximo: o degrau

    def _atras_no_ko(self, arena, vencedor, perdedor, reserva):
        from neural_fights.core.arena import ARENAS
        from neural_fights.effects.camera import Câmera

        cfg = ARENAS[arena]
        cam = Câmera(self.LARGURA, self.ALTURA)
        cam.set_arena_bounds(cfg.largura / 2, cfg.altura / 2, cfg.largura, cfg.altura)
        cam.zoom = cam._calcular_zoom_necessario(vencedor, perdedor,
                                                  zoom_max=cam._diretor_teto_zoom())
        cam.x, cam.y = cam._limitar_centro_a_arena(*cam._calcular_centro_ideal(vencedor, perdedor))
        _x0, y0, _x1, _y1 = cam.caixa_do_rosto(vencedor, cam.zoom, 0.0)
        return cam.converter(0, y0)[1] < reserva["topo"] * self.ALTURA

    def test_caso_zero_sem_reserva_o_rosto_entra_no_letreiro(self):
        acusou = 0
        for arena, cenas in self.CENAS.items():
            for v, p in cenas:
                _cam, colisoes = self._cauda(arena, _lutador(*v), _lutador(*p, morto=True), None)
                acusou += bool(colisoes)
        self.assertGreater(acusou, 0)

    def test_reserva_le_a_caixa_real_do_letreiro(self):
        reserva = reserva_do_letreiro(self.PERFIL)
        maior = max(caixa_do_letreiro(self.render, self.PERFIL, t, 0.0)[3]
                    for t in ("K.O.", "NOCAUTE", "ACABOU"))
        self.assertAlmostEqual(reserva["topo"], maior / self.ALTURA, places=3)
        self.assertAlmostEqual(reserva["ate_s"], self.duracao + 0.05, places=3)

    def test_quando_o_letreiro_some_a_area_volta_suave(self):
        from neural_fights.effects.camera import Câmera

        cam = Câmera(self.LARGURA, self.ALTURA)
        cam.modo = "DIRETOR"
        cam.reserva_pos_ko = {"topo": 0.26, "ate_s": 0.5}
        v, p = _lutador(5.0, 5.0), _lutador(9.0, 12.0, morto=True)
        topos = []
        for k in range(120):
            cam.t_pos_ko = (k + 1) / 60
            cam.atualizar(1 / 60, v, p)
            topos.append(cam._area_pos_ko()[1])
        self.assertAlmostEqual(topos[10], 0.26)                 # segura
        depois = topos[31:]
        self.assertTrue(all(a >= b for a, b in zip(depois, depois[1:])))   # so desce
        self.assertTrue(all(a - b < 0.02 for a, b in zip(depois, depois[1:])))  # sem salto
        self.assertLess(depois[-1], 0.02)                      # e volta ao normal


if __name__ == "__main__":
    unittest.main()
