# -*- coding: utf-8 -*-
"""O fim do video de luta (14/10/2026, achado do conferente).

Gravando com o gravador de producao (seed 4242, Gunnar x Aurelia, Arena,
camera ARENA), o fim do video era o pior trecho dele:

1. depois do K.O. a imagem CONGELAVA ate o fim (freezedetect a partir de
   39,4 s num video de 42,9 s) e o perdedor SUMIA: o corpo caido era pintado
   em ``COR_CORPO`` (20, 20, 20) sobre o chao escuro;
2. depois da fanfarra sobravam ~0,9 s de silencio (cauda fixa de 3,5 s);
3. o true peak do mp4 dava -1,2 dBTP (0,2 dB de folga do -1);
4. a lava zerava o contador quando o lutador saia da poca: quem so
   atravessava nunca levava dano.

O que muda e so DESENHO (a cena pos-K.O.), a duracao da cauda, o teto de pico
da mistura e — este sim na simulacao — o contador da lava.
"""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from neural_fights.effects import mixagem  # noqa: E402
from neural_fights.recording import fight_recorder  # noqa: E402
from neural_fights.simulation import simulacao  # noqa: E402
from neural_fights.utils.config import COR_FUNDO, PPM  # noqa: E402


class _Camera:
    """O suficiente de ``Câmera`` para desenhar: mundo (px) -> tela, zoom 1."""

    def __init__(self, largura, altura):
        self.largura, self.altura = largura, altura

    def converter(self, x, y):
        return int(x - 5 * PPM + self.largura / 2), int(y - 5 * PPM + self.altura / 2)

    def converter_tam(self, tamanho):
        return int(tamanho)


def _lutador(nome, cor, x=5.0, y=5.0, morto=False):
    dados = SimpleNamespace(nome=nome, tamanho=1.0, cor_r=cor[0], cor_g=cor[1], cor_b=cor[2],
                            arma_obj=None)
    return SimpleNamespace(dados=dados, pos=[x, y], z=0.0, morto=morto, angulo_olhar=0.0)


def _sim_pos_ko(t_real, festa_desde=1.2, lado="p2", largura=400, altura=400):
    sim = object.__new__(simulacao.Simulador)
    sim.tela = pygame.Surface((largura, altura))
    sim.tela.fill(COR_FUNDO)
    sim.screen_width, sim.screen_height = largura, altura
    sim.cam = _Camera(largura, altura)
    sim.match_config = {}
    sim.p1 = _lutador("Caido", (220, 40, 120), morto=(lado == "p2"))
    sim.p2 = _lutador("Vencedor", (120, 220, 60), x=6.5, morto=(lado == "p1"))
    sim.round_finalizado = True
    sim.vencedor_round_side = lado
    sim._ko_tempo_real = t_real
    sim._festa_desde = festa_desde if t_real >= (festa_desde or 0.0) else None
    sim.slow_mo_timer = 0.0
    return sim


class CenaPosKoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_perdedor_caido_aparece_na_cor_dele_e_nao_some(self):
        sim = _sim_pos_ko(2.0)
        sx, sy = sim.cam.converter(sim.p1.pos[0] * PPM, sim.p1.pos[1] * PPM)
        raio = int(sim.p1.dados.tamanho / 2 * PPM)
        simulacao.Simulador._desenhar_nocauteado(sim, sim.p1, sx, sy, raio)
        # um ponto do corpo, longe do rosto (olhos/boca ficam no centro)
        cor = sim.tela.get_at((sx - int(raio * 0.85), sy))[:3]
        # antes: COR_CORPO (20, 20, 20), invisivel no chao escuro
        self.assertGreater(sum(cor), sum(COR_FUNDO) + 150, cor)
        # e ainda e ELE: o vermelho do lutador domina o verde
        self.assertGreater(cor[0], cor[1] + 20, cor)

    def test_cena_pos_ko_nao_congela(self):
        """Dois quadros 1/30 s um do outro, na festa, nao sao iguais."""
        quadros = []
        for t in (2.0, 2.0 + 1 / 30):
            sim = _sim_pos_ko(t)
            simulacao.Simulador._desenhar_onda_do_ko(sim)
            simulacao.Simulador._desenhar_festa_da_vitoria(sim, chao=True)
            simulacao.Simulador._desenhar_festa_da_vitoria(sim)
            sx, sy = sim.cam.converter(sim.p1.pos[0] * PPM, sim.p1.pos[1] * PPM)
            simulacao.Simulador._desenhar_nocauteado(sim, sim.p1, sx, sy, int(0.5 * PPM))
            quadros.append(pygame.image.tobytes(sim.tela, "RGB"))
        diferentes = sum(a != b for a, b in zip(quadros[0], quadros[1]))
        self.assertGreater(diferentes, 300)

    def test_slow_mo_tem_onda_de_choque(self):
        """O slow-mo (antes da fanfarra) tambem se mexe: ondas no relogio de parede."""
        quadros = []
        for t in (0.3, 0.3 + 1 / 30):
            sim = _sim_pos_ko(t)
            simulacao.Simulador._desenhar_onda_do_ko(sim)
            quadros.append(pygame.image.tobytes(sim.tela, "RGB"))
        self.assertNotEqual(quadros[0], quadros[1])

    def test_vencedor_pula_so_depois_da_fanfarra(self):
        raio = 25
        antes = _sim_pos_ko(0.6)   # ainda no slow-mo
        self.assertIsNone(simulacao.Simulador._salto_da_comemoracao(antes, antes.p2, raio))
        alturas = set()
        for k in range(12):
            sim = _sim_pos_ko(1.2 + 0.25 + k / 30)
            alturas.add(simulacao.Simulador._salto_da_comemoracao(sim, sim.p2, raio))
        self.assertGreater(len(alturas), 4)          # pula, nao fica parado
        self.assertLessEqual(max(alturas), raio)
        # o perdedor nunca comemora; empate, ninguem
        sim = _sim_pos_ko(2.0)
        self.assertIsNone(simulacao.Simulador._salto_da_comemoracao(sim, sim.p1, raio))
        sim.vencedor_round_side = None
        self.assertIsNone(simulacao.Simulador._vencedor_comemorando(sim))

    def test_relogio_pos_ko_anda_em_tempo_de_parede_e_a_festa_comeca_com_a_fanfarra(self):
        sim = object.__new__(simulacao.Simulador)
        sim.round_finalizado = True
        sim.vencedor = "Vencedor"
        sim.audio = None
        sim.letterbox_timer = 0.0
        sim._slow_mo_ended = False
        sim._ko_tempo_real = 0.0
        sim._festa_desde = None
        sim.time_scale = 0.25
        sim.slow_mo_timer = 1.2
        passos = 0
        while sim._festa_desde is None and passos < 200:
            dt = simulacao.Simulador.avancar_relogio(sim, 1 / 60)
            passos += 1
        self.assertAlmostEqual(sim._festa_desde, 1.2, delta=1 / 30)
        self.assertEqual(dt, 1 / 60)              # o slow-mo acabou
        self.assertAlmostEqual(sim._ko_tempo_real, passos / 60, places=6)

    def test_antes_do_ko_o_relogio_da_cena_nao_anda(self):
        sim = object.__new__(simulacao.Simulador)
        sim.round_finalizado = False
        sim.letterbox_timer = 0.0
        sim.slow_mo_timer = 0.0
        sim.time_scale = 1.0
        simulacao.Simulador.avancar_relogio(sim, 1 / 60)
        self.assertFalse(hasattr(sim, "_ko_tempo_real"))
        self.assertIsNone(simulacao.Simulador._tempo_pos_ko(sim))


class CaudaPosKoTests(unittest.TestCase):
    def test_cauda_termina_logo_depois_da_fanfarra(self):
        sim = SimpleNamespace(slow_mo_timer=1.2)
        with mock.patch.object(fight_recorder, "duracao_do_som",
                               side_effect=lambda i: 1.41 if i == "arena_victory" else None):
            cauda = fight_recorder.cauda_pos_ko_de(sim)
        self.assertAlmostEqual(cauda, 1.2 + 1.41 + fight_recorder.FOLGA_POS_FANFARRA, places=3)
        self.assertLess(cauda, fight_recorder.CAUDA_POS_KO)   # eram 3,5 s fixos

    def test_som_mais_longo_do_fim_estica_a_cauda(self):
        sim = SimpleNamespace(slow_mo_timer=1.2)
        with mock.patch.object(fight_recorder, "duracao_do_som",
                               side_effect=lambda i: {"arena_victory": 1.41, "slowmo_end": 2.0}.get(i)):
            self.assertAlmostEqual(fight_recorder.cauda_pos_ko_de(sim), 1.2 + 2.0 + 0.1, places=3)

    def test_sem_arquivo_da_fanfarra_vale_a_cauda_antiga(self):
        with mock.patch.object(fight_recorder, "duracao_do_som", return_value=None):
            self.assertEqual(fight_recorder.cauda_pos_ko_de(SimpleNamespace(slow_mo_timer=1.2)),
                             fight_recorder.CAUDA_POS_KO)

    def test_nunca_menos_que_o_slow_mo(self):
        with mock.patch.object(fight_recorder, "duracao_do_som", return_value=0.05):
            self.assertEqual(fight_recorder.cauda_pos_ko_de(SimpleNamespace(slow_mo_timer=0.0)),
                             fight_recorder.CAUDA_MIN_POS_KO)

    def test_fanfarra_do_pacote_e_medida(self):
        # o wav do pacote (sintetizar_fanfarra.py): 1,41 s
        self.assertAlmostEqual(fight_recorder.duracao_do_som("arena_victory"), 1.41, delta=0.02)


class TetoDePicoTests(unittest.TestCase):
    """``mixagem.com_teto_de_pico``: o aac passa do pico do wav."""

    def _rodar(self, roteiro):
        chamadas = []

        def tentar(pico_db, nivel_db, indice):
            chamadas.append((round(pico_db, 3), round(nivel_db, 3)))
            return f"t{indice}"

        def medir(caminho):
            lufs, tp = roteiro[int(caminho[1:])]
            return {"lufs": lufs, "tp": tp}

        escolhida, historico = mixagem.com_teto_de_pico(tentar, medir=medir)
        return escolhida, historico, chamadas

    def test_dentro_do_teto_na_primeira_nao_refaz(self):
        escolhida, historico, chamadas = self._rodar([(-16.1, -2.0)])
        self.assertEqual(chamadas, [(0.0, 0.0)])
        self.assertEqual(escolhida["caminho"], "t0")

    def test_passou_do_teto_desce_o_pico_e_devolve_o_nivel(self):
        # medido na seed 4242: -1,2 dBTP; descer o teto custou 0,3 LU
        escolhida, historico, chamadas = self._rodar(
            [(-16.1, -1.2), (-16.4, -2.5), (-16.15, -2.3)])
        self.assertEqual(chamadas[1], (-0.6, 0.0))      # 0,3 acima + 0,3 de folga
        self.assertEqual(chamadas[2], (-0.6, 0.3))      # devolve a perda
        self.assertEqual(escolhida["caminho"], "t2")
        self.assertLessEqual(escolhida["tp"], mixagem.TETO_TP_DBTP)

    def test_nenhuma_dentro_fica_a_ultima_e_respeita_o_limite_de_tentativas(self):
        roteiro = [(-16.0, -1.0)] * mixagem.TENTATIVAS_TP
        escolhida, historico, chamadas = self._rodar(roteiro)
        self.assertEqual(len(chamadas), mixagem.TENTATIVAS_TP)
        self.assertEqual(escolhida, historico[-1])

    def test_medida_ilegivel_nao_derruba(self):
        escolhida, historico = mixagem.com_teto_de_pico(
            lambda p, n, i: "x", medir=lambda c: {})
        self.assertEqual(escolhida["caminho"], "x")
        self.assertEqual(len(historico), 1)

    def test_le_o_resumo_do_ebur128(self):
        resumo = ("[Parsed_ebur128_0] Summary:\n\n  Integrated loudness:\n    I:         -16.1 LUFS\n"
                  "    Threshold: -26.9 LUFS\n\n  True peak:\n    Peak:       -1.2 dBFS\n")
        with mock.patch.object(mixagem.subprocess, "run",
                               return_value=SimpleNamespace(returncode=0, stderr="lixo\n" + resumo)):
            self.assertEqual(mixagem.medir_loudness("x.mp4"), {"lufs": -16.1, "tp": -1.2})
            self.assertEqual(mixagem.pico_verdadeiro_dbtp("x.mp4"), -1.2)


class LavaAcumulaTests(unittest.TestCase):
    """A lava soma o tempo na poca por lutador; so esquece apos 1 s fora."""

    @staticmethod
    def _lutador_real(nome, x, y):
        from neural_fights.core.entities import Lutador

        dados = SimpleNamespace(
            nome=nome, tamanho=1.7, forca=5.0, mana=5.0, resistencia=5.0, velocidade=5.0,
            classe="Guerreiro (Forca Bruta)", personalidade="Aleatorio", nome_arma="",
            arma_obj=None)
        with mock.patch("neural_fights.ai.AIBrain", return_value=None):
            lutador = Lutador(dados, x, y)
        lutador.vida_max = 1000.0
        lutador.vida = lutador.vida_max
        return lutador

    def _sim(self):
        from neural_fights.core.arena import ARENAS, Arena

        lutador_real = self._lutador_real
        arena = Arena(ARENAS["Vulcao"])
        poca = next(o for o in arena.obstaculos if o.tipo == "lava")
        sim = object.__new__(simulacao.Simulador)
        sim.arena = arena
        sim.p1 = lutador_real("Atravessa", x=poca.x, y=poca.y)
        sim.p1.z = 0.0
        sim.p2 = lutador_real("Fora", x=1.0, y=1.0)
        return sim, poca

    def _andar(self, sim, poca, segundos, dentro):
        sim.p1.pos[0], sim.p1.pos[1] = (poca.x, poca.y) if dentro else (1.5, 1.5)
        for _ in range(int(round(segundos * 60))):
            simulacao.Simulador._aplicar_perigo_do_chao(sim, 1 / 60)

    def test_atravessar_duas_vezes_perto_soma_e_queima(self):
        sim, poca = self._sim()
        self._andar(sim, poca, 0.3, True)
        self._andar(sim, poca, 0.5, False)
        self._andar(sim, poca, 0.3, True)
        # antes: 0,3 + 0,3 com o contador zerado no meio = nenhum dano
        self.assertLess(sim.p1.vida, sim.p1.vida_max)

    def test_um_segundo_fora_esquece(self):
        sim, poca = self._sim()
        self._andar(sim, poca, 0.3, True)
        self._andar(sim, poca, 1.1, False)
        self._andar(sim, poca, 0.3, True)
        self.assertEqual(sim.p1.vida, sim.p1.vida_max)

    def test_passagem_unica_curta_ainda_nao_queima(self):
        sim, poca = self._sim()
        self._andar(sim, poca, 0.4, True)
        self._andar(sim, poca, 2.0, False)
        self.assertEqual(sim.p1.vida, sim.p1.vida_max)
        self.assertEqual(sim.p2.vida, sim.p2.vida_max)


if __name__ == "__main__":
    unittest.main()
