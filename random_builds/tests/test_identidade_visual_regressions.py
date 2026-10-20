"""A cor de um lutador e dele — e e a mesma no corpo e no HUD (Onda 15C, 20/10/2026).

Duas cores que caem quase iguais (dois verdes) tornam o video ilegivel, e
algum desempate e inevitavel. Na 15C o desempate deixou de ser o laranja do
ecossistema (uma cor sem relacao com o personagem, que mudava conforme o
adversario) e virou o giro do PROPRIO matiz do lado 2, por um valor derivado
do nome dele: toda cor que um lutador exibe e funcao SO DELE.

O defeito de 20/10/2026 (conferente, `duelo_00122`): o giro era so do
renderer. Sigrid (magenta 234,0,226) x Vesperia (violeta 169,35,237): a faixa
e o HUD mostravam o lado 2 VERDE e o lutador na arena continuava VIOLETA. Quem
assiste procura o verde e nao acha. Agora o desempate e decidido antes da
gravacao (`video/cores.py`), o jogo pinta o corpo com ele
(`match_config["cores_da_tela"]`, so exibicao) e o renderer pinta o HUD com a
cor que o gravador devolveu (`cores_na_tela`). Estes testes travam:

- faixa/HUD == corpo, sempre (clipe novo: a cor desempatada nos dois; clipe
  antigo, sem `cores_na_tela`: a cor do banco nos dois, sem giro);
- o desempate continua estavel, deterministico e vivo;
- na luta de verdade (o par/seed/arena do `duelo_00122`, fichas num fixture),
  o corpo do lado 2 e pintado com a cor desempatada, a luta e a mesma, e o
  vencedor termina a cauda pos-K.O. na cor dele — nao BRANCO (o flash do
  ultimo golpe ficava congelado: 0,233 s de flash = 93% branco a cauda toda).
"""
from __future__ import annotations

import colorsys
import os
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from builds.generation.session_generator import load_config  # noqa: E402
from builds.video import cores  # noqa: E402
from builds.video.renderer import VideoRenderer, cor_legivel  # noqa: E402

VERDE = {"cor_r": 60, "cor_g": 200, "cor_b": 90}
VERDE_PARECIDO = {"cor_r": 70, "cor_g": 195, "cor_b": 100}
VERMELHO = {"cor_r": 210, "cor_g": 60, "cor_b": 55}
VERDE_PARECIDO_T = (70, 195, 100)

# o par do duelo_00122 (banco vivo, 20/10/2026)
SIGRID = {"cor_r": 234, "cor_g": 0, "cor_b": 226}
VESPERIA = {"cor_r": 169, "cor_g": 35, "cor_b": 237}


def _renderer() -> VideoRenderer:
    return VideoRenderer(load_config("render.json"), "celular", True)


def _luta(p1_ficha, p2_ficha, p1="Kael", p2="Lyra", **extra) -> dict:
    return {"p1": p1, "p2": p2, "p1_ficha": p1_ficha, "p2_ficha": p2_ficha, **extra}


def _matiz(cor) -> float:
    return colorsys.rgb_to_hls(*[c / 255.0 for c in cor])[0]


class DesempateDaGravacaoTests(unittest.TestCase):
    """`cores.cores_da_gravacao`: o que o gravador recebe (e o HUD mostra)."""

    def test_cores_distantes_passam_intactas(self):
        c = cores.cores_da_gravacao(VERDE, VERMELHO, "Lyra")
        self.assertEqual({"p1": [60, 200, 90], "p2": [210, 60, 55]}, c)

    def test_cores_parecidas_ganham_contraste(self):
        c = cores.cores_da_gravacao(VERDE, VERDE_PARECIDO, "Lyra")
        self.assertGreaterEqual(cores.distancia(c["p1"], c["p2"]),
                                cores.DISTANCIA_MINIMA_DE_COR)
        self.assertEqual([60, 200, 90], c["p1"], "o lado 1 nao muda")

    def test_o_par_do_duelo_00122_desempata(self):
        """Magenta x violeta: L1 111 < 140. O lado 2 gira."""
        self.assertLess(cores.distancia(cores.cor_da_ficha(SIGRID),
                                        cores.cor_da_ficha(VESPERIA)),
                        cores.DISTANCIA_MINIMA_DE_COR)
        c = cores.cores_da_gravacao(SIGRID, VESPERIA, "Vesperia Vharquiel")
        # o canal 0 o jogo pinta como 50 (``x or 50``): o corpo da Sigrid e
        # 234,50,226 na arena, e e esse o numero que vale para os dois
        self.assertEqual([234, 50, 226], c["p1"])
        self.assertNotEqual([169, 35, 237], c["p2"])
        self.assertGreaterEqual(cores.distancia(c["p1"], c["p2"]),
                                cores.DISTANCIA_MINIMA_DE_COR)

    def test_a_cor_da_gravacao_e_a_que_o_jogo_pinta(self):
        """Nenhum canal 0 sai do desempate: o jogo o pintaria como o padrao
        e o corpo deixaria de ser o numero do HUD."""
        from neural_fights.simulation.simulacao import Simulador
        from types import SimpleNamespace

        for nome in ("Lyra", "Varo", "Selene", "Morgana", "Aldric", "Vesperia Vharquiel"):
            for f1, f2 in ((SIGRID, VESPERIA), (VERDE, VERDE_PARECIDO),
                           ({"cor_r": 255, "cor_g": 0, "cor_b": 0},
                            {"cor_r": 250, "cor_g": 10, "cor_b": 0})):
                c = cores.cores_da_gravacao(f1, f2, nome)
                for lado in ("p1", "p2"):
                    dados = SimpleNamespace(cor_r=c[lado][0], cor_g=c[lado][1], cor_b=c[lado][2])
                    with self.subTest(nome=nome, lado=lado, cor=c[lado]):
                        self.assertEqual(tuple(c[lado]),
                                         Simulador.cor_base_do_corpo(SimpleNamespace(dados=dados)))

    def test_o_desempate_sai_do_proprio_lutador_e_nao_do_ecossistema(self):
        """O laranja do ecossistema nao diz nada sobre quem esta lutando."""
        from builds.visualization.draw_common import hex_rgb

        r = _renderer()
        c2 = tuple(cores.cores_da_gravacao(VERDE, VERDE_PARECIDO, "Lyra")["p2"])
        self.assertNotEqual(hex_rgb(r.colors["accent_weapon"]), c2)
        self.assertNotEqual(hex_rgb(r.colors["accent_character"]), c2)

    def test_a_cor_desempatada_e_a_mesma_contra_qualquer_adversario(self):
        """Duas aparencias no maximo, e as duas sempre as mesmas: o giro
        deriva do NOME de quem gira."""
        vistas = {tuple(cores.cores_da_gravacao(dict(VERDE_PARECIDO), VERDE, "Lyra")["p2"])
                  for _adversario in ("Kael", "Varo", "Pandora", "Raven", "Selene")}
        self.assertEqual(1, len(vistas), f"a cor de Lyra oscilou: {vistas}")

    def test_lutadores_diferentes_giram_para_lugares_diferentes(self):
        """Senao o desempate vira uma cor unica de 'segundo lugar'."""
        giradas = {cores.girar_matiz(VERDE_PARECIDO_T, nome)
                   for nome in ("Lyra", "Varo", "Selene", "Morgana")}
        self.assertGreater(len(giradas), 1)

    def test_o_giro_e_deterministico_entre_processos(self):
        """`hash()` de str e randomizado por PYTHONHASHSEED: a cor mudaria
        a cada gravacao. O giro usa crc32, como `identity/prompt.py`."""
        import zlib
        esperado = 0.28 + (zlib.crc32(b"Lyra") % 1000) / 1000.0 * 0.44
        self.assertGreater(esperado, 0.27)
        primeira = cores.girar_matiz(VERDE_PARECIDO_T, "Lyra")
        self.assertEqual(primeira, cores.girar_matiz(VERDE_PARECIDO_T, "Lyra"))
        # o renderer ainda expoe o mesmo giro (quem o chamava continua igual)
        self.assertEqual(primeira, VideoRenderer._girar_matiz(VERDE_PARECIDO_T, "Lyra"))

    def test_a_cor_girada_continua_viva(self):
        """Girar o matiz nao pode produzir um cinza sem vida."""
        for nome in ("Lyra", "Varo", "Selene", "Morgana", "Aldric"):
            cor = cores.girar_matiz((60, 60, 62), nome)
            with self.subTest(nome=nome):
                self.assertGreater(max(cor) - min(cor), 30, f"{cor} e cinza")


class FaixaIgualAoCorpoTests(unittest.TestCase):
    """O renderer pinta HUD/faixa/identidade/veredito com a cor do CORPO."""

    @classmethod
    def setUpClass(cls):
        cls.r = _renderer()

    def test_clipe_novo_o_hud_e_a_cor_que_o_gravador_pintou(self):
        gravada = cores.cores_da_gravacao(SIGRID, VESPERIA, "Vesperia Vharquiel")
        luta = _luta(SIGRID, VESPERIA, "Sigrid Argavelth", "Vesperia Vharquiel",
                     cores_na_tela=gravada)
        c1, c2 = self.r._cores_do_confronto(luta)
        self.assertEqual(tuple(gravada["p1"]), c1)
        self.assertEqual(tuple(gravada["p2"]), c2)

    def test_clipe_antigo_o_hud_e_a_cor_do_banco_sem_giro(self):
        """CASO ZERO do defeito: antes, o par parecido saia GIRADO no HUD e
        com a cor do banco no corpo. Clipe sem `cores_na_tela` tem o corpo da
        cor do banco — e e ela que o HUD mostra."""
        luta = _luta(SIGRID, VESPERIA, "Sigrid Argavelth", "Vesperia Vharquiel")
        self.assertEqual(((234, 50, 226), (169, 35, 237)), self.r._cores_do_confronto(luta))

    def test_cores_na_tela_invalidas_caem_no_banco(self):
        for ruim in ({"p1": [1, 2]}, {"p1": "x", "p2": [1, 2, 3]},
                     {"p1": [1, 2, 300], "p2": [1, 2, 3]}, [1, 2, 3]):
            with self.subTest(ruim=ruim):
                luta = _luta(SIGRID, VESPERIA, cores_na_tela=ruim)
                self.assertEqual(((234, 50, 226), (169, 35, 237)),
                                 self.r._cores_do_confronto(luta))

    def test_a_faixa_tem_o_matiz_do_corpo(self):
        """A faixa so CLAREIA a cor (contraste 4,5:1 sobre a pilula): o matiz
        e o do corpo. No 00122 a faixa era verde (33,245,14) e o corpo violeta."""
        gravada = cores.cores_da_gravacao(SIGRID, VESPERIA, "Vesperia Vharquiel")
        luta = _luta(SIGRID, VESPERIA, cores_na_tela=gravada)
        for corpo in self.r._cores_do_confronto(luta):
            faixa = cor_legivel(corpo)
            with self.subTest(corpo=corpo, faixa=faixa):
                diferenca = abs(_matiz(faixa) - _matiz(corpo))
                self.assertLess(min(diferenca, 1 - diferenca), 0.02)


class CorpoNaArenaDoDuelo00122Tests(unittest.TestCase):
    """A luta de verdade: Sigrid Argavelth x Vesperia Vharquiel, seed
    1141090978, Duto, pelo gravador (o par/seed/arena do `duelo_00122`), com
    as duas fichas do banco vivo num fixture (``fixtures/duelo_00122``).

    Medido antes do conserto (20/10/2026): o corpo do lado 2 era VIOLETA com
    a faixa VERDE, e o vencedor tinha ``flash_timer`` 0,233 congelado do K.O.
    ao fim (flash branco a 93%)."""

    FIXTURE = Path(__file__).resolve().parent / "fixtures" / "duelo_00122"
    P1, P2 = "Sigrid Argavelth", "Vesperia Vharquiel"
    # o que a gravacao de antes do conserto deu (vencedor, K.O. no video, video)
    BASE = ("Sigrid Argavelth", 18.73, 21.47)

    @classmethod
    def setUpClass(cls):
        import pygame

        from neural_fights.recording import fight_recorder
        from neural_fights.simulation import simulacao as sim_mod
        from neural_fights.tools import qualidade_luta as ql

        with mock.patch.object(ql, "FIXTURE_ENGINE", cls.FIXTURE):
            fonte = ql.FonteDeDados("engine")
        cls.gravada = cores.cores_da_gravacao(
            {"cor_r": 234, "cor_g": 0, "cor_b": 226},
            {"cor_r": 169, "cor_g": 35, "cor_b": 237}, cls.P2)
        corpos = []          # (lado, t_pos_ko ou None, cor do corpo pintada)
        original = sim_mod.Simulador.desenhar_lutador
        elipse = pygame.draw.ellipse

        def desenhar_lutador(self, l):
            if l.morto:
                return original(self, l)
            pintadas = []

            def espia(superficie, cor, *a, **k):
                if superficie is self.tela:
                    pintadas.append(tuple(cor)[:3])
                return elipse(superficie, cor, *a, **k)

            with mock.patch.object(pygame.draw, "ellipse", espia):
                saida = original(self, l)
            if pintadas:                 # a 1a elipse na tela e o corpo
                corpos.append(("p1" if l is self.p1 else "p2",
                               sim_mod.Simulador._tempo_pos_ko(self), pintadas[0]))
            return saida

        with mock.patch.object(sim_mod.Simulador, "desenhar_lutador", desenhar_lutador):
            cls.resultado = fight_recorder.gravar_luta(
                p1=cls.P1, p2=cls.P2, saida=None, seed=1141090978, cenario="Duto",
                resolucao=(540, 960), camera_modo="DIRETOR", hud=False,
                som_no_video=False, anotar_som=False,
                roster_provider=fonte.provider(None), cores_da_tela=cls.gravada)
        cls.corpos = corpos

    def test_a_luta_e_a_mesma(self):
        r = self.resultado
        self.assertTrue(r["sucesso"], r.get("erro"))
        self.assertEqual(self.BASE, (r["vencedor"], r["ko_em_video"], r["duracao_video"]))

    def test_o_gravador_devolve_a_cor_que_pintou(self):
        self.assertEqual(self.gravada, self.resultado["cores_na_tela"])

    def test_o_corpo_e_a_cor_do_hud(self):
        """Cor mais pintada no corpo de cada lado, na luta = a do HUD."""
        renderer = _renderer()
        luta = _luta(dict(SIGRID), dict(VESPERIA), self.P1, self.P2,
                     cores_na_tela=self.resultado["cores_na_tela"])
        hud = dict(zip(("p1", "p2"), renderer._cores_do_confronto(luta)))
        for lado in ("p1", "p2"):
            pintadas = Counter(c for la, t, c in self.corpos if la == lado and t is None)
            with self.subTest(lado=lado):
                self.assertTrue(pintadas)
                self.assertEqual(hud[lado], pintadas.most_common(1)[0][0])
        self.assertNotEqual((169, 35, 237), hud["p2"], "o par parecido desempata")

    def test_o_vencedor_termina_na_cor_dele(self):
        """CASO ZERO do 2o defeito: da 0,3 s do K.O. em diante o corpo do
        vencedor e a cor dele em TODO quadro (antes: 93% branco a cauda toda)."""
        cauda = [c for la, t, c in self.corpos if la == "p1" and t is not None and t >= 0.3]
        self.assertGreater(len(cauda), 30)
        self.assertEqual({tuple(self.gravada["p1"])}, set(cauda))


class ComCorDaTelaTests(unittest.TestCase):
    """`simulacao._com_cor_da_tela`: troca numa copia, nunca no banco."""

    def test_troca_numa_copia(self):
        from neural_fights.models.characters import Personagem
        from neural_fights.simulation.simulacao import _com_cor_da_tela

        p = Personagem("Kael", 1.7, 5, 5, r=169, g=35, b=237)
        copia = _com_cor_da_tela(p, {"p2": [33, 245, 14]}, "p2")
        self.assertEqual((33, 245, 14), (copia.cor_r, copia.cor_g, copia.cor_b))
        self.assertEqual((169, 35, 237), (p.cor_r, p.cor_g, p.cor_b))
        self.assertIs(p, _com_cor_da_tela(p, {"p2": [1, 2, 3]}, "p1"))
        self.assertIs(p, _com_cor_da_tela(p, None, "p1"))
        self.assertIs(p, _com_cor_da_tela(p, {"p1": [1, 2]}, "p1"))

    def test_flash_se_apaga_depois_do_ko(self):
        from types import SimpleNamespace

        from neural_fights.simulation.simulacao import Simulador

        sim = object.__new__(Simulador)
        lutador = SimpleNamespace(flash_timer=0.233)
        sim.round_finalizado = False
        self.assertAlmostEqual(0.233, Simulador._flash_na_tela(sim, lutador))
        sim.round_finalizado, sim._ko_tempo_real = True, 0.1
        self.assertAlmostEqual(0.133, Simulador._flash_na_tela(sim, lutador))
        sim._ko_tempo_real = 0.3
        self.assertEqual(0.0, Simulador._flash_na_tela(sim, lutador))


if __name__ == "__main__":
    unittest.main()
