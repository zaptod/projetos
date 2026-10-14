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

import math
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


def _cobertura_do_rosto(tela, fundo, centro, raio):
    """Fracao do disco do rosto (centro, raio) que nao e mais o fundo."""
    cx, cy = centro
    total = cobertos = 0
    for y in range(int(cy - raio), int(cy + raio) + 1):
        for x in range(int(cx - raio), int(cx + raio) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 > raio * raio:
                continue
            if not (0 <= x < tela.get_width() and 0 <= y < tela.get_height()):
                continue
            total += 1
            if tuple(tela.get_at((x, y))[:3]) != tuple(fundo):
                cobertos += 1
    return cobertos / max(1, total)


class ConfeteForaDoRostoTests(unittest.TestCase):
    """Achado do conferente (14/10): o confete cobria 18% do rosto do
    vencedor no ultimo quadro, em TODA luta (nascia no centro do rosto)."""

    DURA = 1.51          # fanfarra 1,41 + 0,1 s: a festa medida na seed 4242
    FESTA_DESDE = 1.2

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _quadro(self, fase):
        sim = _sim_pos_ko(self.FESTA_DESDE + fase, festa_desde=self.FESTA_DESDE,
                          largura=600, altura=600)
        sim._festa_dura_s = self.DURA
        simulacao.Simulador._desenhar_festa_da_vitoria(sim)
        sx, sy = sim.cam.converter(sim.p2.pos[0] * PPM, sim.p2.pos[1] * PPM)
        raio = max(4, sim.cam.converter_tam((sim.p2.dados.tamanho / 2) * PPM))
        salto = simulacao.Simulador._salto_da_comemoracao(sim, sim.p2, raio) or 0
        return sim.tela, (sx, sy - salto), raio

    def test_o_medidor_acusa_confete_no_rosto(self):
        # caso ZERO: o medidor nao pode passar vazio
        tela = pygame.Surface((100, 100))
        tela.fill(COR_FUNDO)
        pygame.draw.rect(tela, (255, 0, 0), (40, 40, 20, 10))
        self.assertGreater(_cobertura_do_rosto(tela, COR_FUNDO, (50, 50), 20), 0.05)

    def test_nenhum_quadro_da_cauda_cobre_o_rosto(self):
        quadros_com_confete = 0
        pior = 0.0
        for k in range(int(self.DURA * 30) + 1):
            tela, centro, raio = self._quadro(k / 30)
            pior = max(pior, _cobertura_do_rosto(tela, COR_FUNDO, centro, raio))
            fora = sum(1 for x in range(0, 600, 3) for y in range(0, 600, 3)
                       if tuple(tela.get_at((x, y))[:3]) != tuple(COR_FUNDO))
            quadros_com_confete += fora > 0
        self.assertLess(pior, 0.05)
        # e o confete existe (o teste nao passa porque nada foi desenhado)
        self.assertGreater(quadros_com_confete, int(self.DURA * 30) - 2)

    def test_ultimo_quadro_nao_cai_numa_rajada_recem_nascida(self):
        sim = _sim_pos_ko(self.FESTA_DESDE + self.DURA, festa_desde=self.FESTA_DESDE)
        sim._festa_dura_s = self.DURA
        vivas = simulacao.Simulador._rajadas_vivas(sim, self.DURA)
        self.assertTrue(vivas)
        self.assertGreaterEqual(min(tau for _r, tau in vivas),
                                simulacao.Simulador.FESTA_RAJADA_ANTES_DO_FIM_S - 1e-9)
        # sem saber o fim (jogo ao vivo), as rajadas seguem a cada 0,7 s
        sim._festa_dura_s = None
        self.assertIn(2, [r for r, _tau in simulacao.Simulador._rajadas_vivas(sim, 1.45)])

    def test_gravador_anuncia_quanto_a_festa_dura(self):
        sim = SimpleNamespace(slow_mo_timer=1.2)
        fight_recorder.anunciar_fim_da_festa(sim, 2.71)
        self.assertAlmostEqual(sim._festa_dura_s, 1.51, places=6)


class RotuloDoPlanoTests(unittest.TestCase):
    """O "ACABAR" (Onda 10C) ficava sob o vencedor depois do K.O."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _sim_com_plano(self, finalizado):
        sim = _sim_pos_ko(2.0)
        sim.round_finalizado = finalizado
        sim.p2.brain = SimpleNamespace(plano=SimpleNamespace(rotulo="ACABAR", progresso=0.5),
                                       _plano_trocado_em=0.0, tempo_combate=5.0)
        return sim

    def test_rotulo_aparece_na_luta_e_some_no_ko(self):
        for finalizado, esperado in ((False, True), (True, False)):
            sim = self._sim_com_plano(finalizado)
            sim.tela.fill(COR_FUNDO)
            desenhou = simulacao.Simulador._desenhar_rotulo_do_plano(
                sim, sim.p2, (200, 200), 25, (255, 0, 0))
            self.assertEqual(desenhou, esperado)
            sujo = pygame.image.tobytes(sim.tela, "RGB") != bytes(COR_FUNDO) * (400 * 400)
            self.assertEqual(sujo, esperado)


class ObjetosSomemNoKoTests(unittest.TestCase):
    """Projetil/orbe/invocacao vivo no K.O. ficava parado no ar a festa toda."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_fade_em_ate_0_3_s_de_tempo_real(self):
        fade = simulacao.Simulador._fade_objetos_pos_ko
        self.assertEqual(fade(_sim_pos_ko(0.0)), 1.0)
        self.assertAlmostEqual(fade(_sim_pos_ko(0.15)), 0.5, places=6)
        self.assertEqual(fade(_sim_pos_ko(0.3)), 0.0)
        self.assertEqual(fade(_sim_pos_ko(2.0)), 0.0)
        antes = _sim_pos_ko(0.0)
        antes.round_finalizado = False
        self.assertEqual(fade(antes), 1.0)            # na luta, nada muda
        self.assertLessEqual(simulacao.Simulador.FADE_OBJETOS_POS_KO_S, 0.3)

    def _desenhar_objeto(self, t, ha=True):
        sim = _sim_pos_ko(t)
        guardado = simulacao.Simulador._abrir_fade_pos_ko(sim, ha)
        pygame.draw.circle(sim.tela, (255, 255, 255), (100, 100), 20)
        simulacao.Simulador._fechar_fade_pos_ko(sim, guardado)
        return tuple(sim.tela.get_at((100, 100))[:3])

    def test_o_objeto_some_e_antes_do_ko_fica_inteiro(self):
        self.assertEqual(self._desenhar_objeto(0.0), (255, 255, 255))   # quadro do K.O.
        meio = self._desenhar_objeto(0.15)
        self.assertTrue(all(abs(m - (c + 255) / 2) <= 2 for m, c in zip(meio, COR_FUNDO)), meio)
        self.assertEqual(self._desenhar_objeto(0.31), tuple(COR_FUNDO))
        # nada para apagar: nao copia a tela
        sim = _sim_pos_ko(1.0)
        self.assertIsNone(simulacao.Simulador._abrir_fade_pos_ko(sim, False))


def _lutador_cam(x, y, morto=False, tamanho=1.0):
    return SimpleNamespace(pos=[x, y], z=0.0, morto=morto, raio_fisico=tamanho / 4.0,
                           dados=SimpleNamespace(tamanho=tamanho))


class CameraPosKoTests(unittest.TestCase):
    """A camera DIRETOR na cauda: vencedor com 7% da largura, nome no topo e
    confete cortado (os dois em cantos opostos)."""

    def _cauda(self, vencedor, perdedor, largura=1080, altura=1920):
        from neural_fights.effects.camera import Câmera

        cam = Câmera(largura, altura)
        cam.modo = "DIRETOR"
        cam.diretor_largura_min_m = 5.5
        # quadro de antes do K.O.: os dois enquadrados
        cam.zoom = cam._calcular_zoom_necessario(vencedor, perdedor,
                                                  zoom_max=cam._diretor_teto_zoom())
        cam.x, cam.y = cam._calcular_centro_ideal(vencedor, perdedor)
        historico = []
        # slow-mo (1,2 s de parede a 0,25x) e a festa (1,51 s), passos de 60 Hz
        for dt in [0.25 / 60] * 72 + [1 / 60] * 91:
            cam.atualizar(dt, vencedor, perdedor)
            historico.append((cam.zoom, cam.x, cam.y))
        return cam, historico

    def _caixa_na_tela(self, cam, caixa):
        x0, y0 = cam.converter(caixa[0], caixa[1])
        x1, y1 = cam.converter(caixa[2], caixa[3])
        return x0, y0, x1, y1

    def _sem_salto(self, cam, historico):
        for (z0, x0, y0), (z1, x1, y1) in zip(historico, historico[1:]):
            self.assertLess(abs(z1 - z0) / z0, 0.08)
            self.assertLess(math.hypot((x1 - x0) * z1, (y1 - y0) * z1), 0.05 * cam.screen_width)

    def test_longe_um_do_outro_enquadra_o_vencedor_inteiro(self):
        vencedor = _lutador_cam(3.0, 3.0)
        perdedor = _lutador_cam(14.0, 24.0, morto=True)
        cam, historico = self._cauda(vencedor, perdedor)
        self.assertEqual(cam._pos_ko_modo, "vencedor")
        fracao = 2 * cam._raio_desenhado(vencedor) * cam.zoom / cam.screen_width
        self.assertGreaterEqual(fracao, 0.15)
        x0, y0, x1, y1 = self._caixa_na_tela(cam, cam._caixa_da_festa(vencedor, cam.zoom))
        self.assertGreaterEqual(x0, -2)
        self.assertGreaterEqual(y0, -2)          # o nome no alto do pulo cabe
        self.assertLessEqual(x1, cam.screen_width + 2)
        self.assertLessEqual(y1, cam.diretor_pos_ko_area[3] * cam.screen_height + 2)
        self._sem_salto(cam, historico)
        # antes: o vencedor ficava com ~7% da largura
        self.assertLess(2 * cam._raio_desenhado(vencedor) * historico[0][0] / cam.screen_width,
                        0.15)

    def test_perto_enquadra_os_dois(self):
        vencedor = _lutador_cam(8.0, 10.0)
        perdedor = _lutador_cam(9.3, 10.2, morto=True)
        cam, historico = self._cauda(vencedor, perdedor)
        self.assertEqual(cam._pos_ko_modo, "dois")
        fracao = 2 * cam._raio_desenhado(vencedor) * cam.zoom / cam.screen_width
        self.assertGreaterEqual(fracao, 0.149)
        for caixa in (cam._caixa_da_festa(vencedor, cam.zoom),
                      cam._caixa_do_caido(perdedor, cam.zoom)):
            x0, y0, x1, y1 = self._caixa_na_tela(cam, caixa)
            self.assertGreaterEqual(min(x0, y0), -2)
            self.assertLessEqual(x1, cam.screen_width + 2)
            self.assertLessEqual(y1, cam.diretor_pos_ko_area[3] * cam.screen_height + 2)
        self._sem_salto(cam, historico)

    def test_antes_do_ko_o_diretor_nao_muda(self):
        from neural_fights.effects.camera import Câmera

        a, b = _lutador_cam(3.0, 3.0), _lutador_cam(8.0, 9.0)
        cam = Câmera(1080, 1920)
        cam.modo = "DIRETOR"
        cam.atualizar(1 / 60, a, b)
        self.assertFalse(hasattr(cam, "_pos_ko_modo"))


if __name__ == "__main__":
    unittest.main()
