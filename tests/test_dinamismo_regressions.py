# -*- coding: utf-8 -*-
"""Dinamismo (21/10/2026): colado longo vira choque e afastamento.

Pedido do Adrian: "não quero os personagens colados um no outro muito
tempo; quero movimento e dinamismo nas lutas". Linha de base medida no lote
pré-registrado de 60 lutas (os 31 duelos da fila de 21/10 + 29 pares
sorteados com seed fixa), motor de ``8f51d7bd``: ver
``docs/sessoes/builds.md`` §14 e ``neural_fights/tools/dinamismo_luta.py``.

Grupos:
- as contas puras (``core/dinamismo.py``): relógio, saída da parede, quem
  pode ser empurrado;
- a chave da LUTA: ausente = o motor de antes, sem um atributo novo (luta
  gravada antes re-simula igual — decisão ``corrente-seeds-antigas``, o
  mesmo desenho);
- as metas num lote pequeno das piores lutas da linha de base, com o caso
  zero (chave desligada acusa).
"""

from __future__ import annotations

import math
import statistics
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from neural_fights.core import dinamismo
from neural_fights.utils import config

RAIZ = Path(__file__).resolve().parents[1]
FIXTURE = RAIZ / "tests" / "fixtures" / "dinamismo"
DT = 1.0 / 60.0


def _corpo(x, y, r=0.45, **extra):
    base = dict(pos=[x, y], vel=[0.0, 0.0], raio_fisico=r, z=0.0, morto=False,
                dormindo=False, slow_fator=1.0, brain=None)
    base.update(extra)
    return SimpleNamespace(**base)


ARENA = SimpleNamespace(min_x=0.0, max_x=10.125, min_y=0.0, max_y=18.0,
                        centro_x=5.0625, centro_y=9.0)


class ContasPurasTests(unittest.TestCase):
    def test_relogio_sobe_colado_e_esquece_no_dobro_solto(self):
        t = 0.0
        for _ in range(30):
            t = dinamismo.acumular(t, True, DT)
        self.assertAlmostEqual(t, 0.5, places=6)
        for _ in range(6):            # 0,1 s solto tira 0,2 s
            t = dinamismo.acumular(t, False, DT)
        self.assertAlmostEqual(t, 0.3, places=6)
        for _ in range(60):
            t = dinamismo.acumular(t, False, DT)
        self.assertEqual(t, 0.0)

    def test_colados_pelo_disco_desenhado(self):
        # tamanho 1,8: a física tem raio 0,45 e o vídeo desenha 0,9
        a = _corpo(0.0, 0.0, dados=SimpleNamespace(tamanho=1.8))
        limite = config.DINAMISMO_COLADO_FRACAO_RAIO * 0.9

        def outro(x, **kw):
            return _corpo(x, 0.0, dados=SimpleNamespace(tamanho=1.8), **kw)

        self.assertTrue(dinamismo.colados(a, outro(1.8 + limite - 0.01)))
        self.assertFalse(dinamismo.colados(a, outro(1.8 + limite + 0.01)))
        # caso zero: pelo raio da física (0,45) 1,5 m de centro a centro
        # estaria "solto", mas os discos desenhados se cobrem
        self.assertLess(dinamismo.borda(a, outro(1.5)), 0.0)
        self.assertTrue(dinamismo.colados(a, outro(1.5)))
        # o disco de quem voa é desenhado z acima: conta a posição na tela
        # (duelo_00162: voando a 1,5 m por cima do outro por 6 s)
        self.assertTrue(dinamismo.colados(a, _corpo(0.0, 1.5, z=1.5,
                                                    dados=SimpleNamespace(tamanho=1.8))))
        self.assertFalse(dinamismo.colados(a, outro(1.8 + limite - 0.01, z=1.5)))
        # sem ``dados``: o dobro do raio da física
        self.assertAlmostEqual(dinamismo.raio_desenhado(_corpo(0, 0)), 0.9)

    def test_saida_livre_e_para_longe_do_outro(self):
        corpo = _corpo(5.0, 9.0)
        dx, dy = dinamismo.direcao_de_saida(corpo, -1.0, 0.0, ARENA)
        self.assertAlmostEqual(dx, -1.0)
        self.assertAlmostEqual(dy, 0.0)

    def test_na_parede_desliza_em_vez_de_empurrar_contra_ela(self):
        corpo = _corpo(0.5, 9.0)            # encostado na parede da esquerda
        dx, dy = dinamismo.direcao_de_saida(corpo, -1.0, 1.0, ARENA)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, 1.0)
        # caso zero: sem a arena, o empurrão iria para dentro da parede
        dx0, _ = dinamismo.direcao_de_saida(corpo, -1.0, 1.0, None)
        self.assertLess(dx0, 0.0)

    def test_no_canto_ou_de_frente_para_a_parede_sai_para_o_centro(self):
        canto = _corpo(0.5, 0.5)
        dx, dy = dinamismo.direcao_de_saida(canto, -1.0, -1.0, ARENA)
        self.assertGreater(dx, 0.0)
        self.assertGreater(dy, 0.0)
        frente = _corpo(0.5, 9.0)
        dx, dy = dinamismo.direcao_de_saida(frente, -1.0, 0.0, ARENA)
        self.assertGreater(dx, 0.9)

    def test_quem_nao_pode_mexer_cede_o_impulso_ao_outro(self):
        a = _corpo(5.0, 9.0)
        b = _corpo(5.9, 9.0, dormindo=True)
        (v1x, v1y), (v2x, v2y) = dinamismo.impulsos(a, b, ARENA)
        self.assertEqual((v2x, v2y), (0.0, 0.0))
        self.assertAlmostEqual(math.hypot(v1x, v1y), 2 * config.DINAMISMO_EMPURRAO)
        self.assertLess(v1x, 0.0)            # a sai para longe de b

    def test_verbo_de_saida_sem_sorteio(self):
        agil = SimpleNamespace(brain=SimpleNamespace(perfil={"mobilidade": 0.8}))
        pesado = SimpleNamespace(brain=SimpleNamespace(perfil={"mobilidade": 0.1}))
        self.assertEqual(dinamismo.verbo_de_saida(agil), "CIRCULAR")
        self.assertEqual(dinamismo.verbo_de_saida(pesado), "RECUAR")
        self.assertEqual(dinamismo.verbo_de_saida(SimpleNamespace()), "RECUAR")


class BateESaiTests(unittest.TestCase):
    """Quem acerta colado sai (``Simulador._sair_depois_do_choque``)."""

    def _atacante(self, mobilidade):
        pedidos = []
        brain = SimpleNamespace(perfil={"mobilidade": mobilidade},
                                _definir_acao=lambda *a, **kw: pedidos.append((a, kw)))
        return SimpleNamespace(brain=brain), pedidos

    def test_quem_acerta_colado_recua_ou_circula_com_prioridade_0(self):
        from neural_fights.simulation.simulacao import Simulador

        for mob, verbo in ((0.1, "RECUAR"), (0.8, "CIRCULAR")):
            atacante, pedidos = self._atacante(mob)
            Simulador._sair_depois_do_choque(None, atacante, -9.0, 0.0)
            self.assertEqual(len(pedidos), 1)
            (acao,), kw = pedidos[0]
            self.assertEqual(acao, verbo)
            self.assertEqual(kw["prioridade"], 0)
            self.assertEqual(kw["hold_s"], config.DINAMISMO_CHOQUE_SAIDA_S)

    def test_caso_zero_sem_recuo_ou_desligado_nao_mexe_na_ia(self):
        from neural_fights.simulation.simulacao import Simulador

        atacante, pedidos = self._atacante(0.1)
        # sem recuo (o atacante não pode ser empurrado): a IA segue a dela
        Simulador._sair_depois_do_choque(None, atacante, 0.0, 0.0)
        with mock.patch.object(config, "DINAMISMO_CHOQUE_SAIDA_S", 0.0):
            Simulador._sair_depois_do_choque(None, atacante, -9.0, 0.0)
        self.assertEqual(pedidos, [])
        # sem cérebro (boneco de treino): nada quebra
        Simulador._sair_depois_do_choque(None, SimpleNamespace(), -9.0, 0.0)


class ChavesDoAjusteTests(unittest.TestCase):
    """Desfecho, solto, colado sem golpe e alcance (21/10, conferente)."""

    def test_desfecho_pela_vida_e_pelo_plano_acabar(self):
        vivo = SimpleNamespace(vida=80.0, vida_max=100.0, brain=None)
        quase = SimpleNamespace(vida=10.0, vida_max=100.0, brain=None)
        acabando = SimpleNamespace(vida=80.0, vida_max=100.0,
                                   brain=SimpleNamespace(plano={"tipo": "ACABAR"}))
        # caso zero: as chaves desligadas (o padrão) não mudam nada
        self.assertFalse(dinamismo.fase_final(vivo, quase))
        self.assertFalse(dinamismo.fase_final(vivo, acabando))
        with mock.patch.object(config, "DINAMISMO_HP_FIM", 0.12):
            self.assertTrue(dinamismo.fase_final(vivo, quase))
            self.assertFalse(dinamismo.fase_final(vivo, vivo))
        with mock.patch.object(config, "DINAMISMO_FIM_NO_ACABAR", True):
            self.assertTrue(dinamismo.fase_final(acabando, vivo))

    def test_solto_pela_borda_desenhada(self):
        a = _corpo(0.0, 0.0, dados=SimpleNamespace(tamanho=1.8))
        perto = _corpo(1.8 + 0.5, 0.0, dados=SimpleNamespace(tamanho=1.8))
        longe = _corpo(1.8 + 1.5, 0.0, dados=SimpleNamespace(tamanho=1.8))
        self.assertFalse(dinamismo.soltos(a, longe))         # desligado
        with mock.patch.object(config, "DINAMISMO_SOLTO_FRACAO_RAIO", 1.5):
            self.assertFalse(dinamismo.soltos(a, perto))      # borda 0,5 < 1,35
            self.assertTrue(dinamismo.soltos(a, longe))       # borda 1,5 > 1,35

    def test_respiro_so_no_colado_sem_golpe(self):
        self.assertTrue(dinamismo.parado_sem_golpe({"t": 5.0, "t_golpe": 4.9}))
        with mock.patch.object(config, "DINAMISMO_SEM_GOLPE_S", 0.6):
            self.assertFalse(dinamismo.parado_sem_golpe({"t": 5.0, "t_golpe": 4.9}))
            self.assertTrue(dinamismo.parado_sem_golpe({"t": 5.0, "t_golpe": 4.0}))
            self.assertTrue(dinamismo.parado_sem_golpe({"t": 5.0}))

    def test_alcance_desigual_troca_o_verbo(self):
        arco = SimpleNamespace(dados=SimpleNamespace(arma_obj="arco"),
                               brain=SimpleNamespace(perfil={"mobilidade": 0.1}))
        espada = SimpleNamespace(dados=SimpleNamespace(arma_obj="espada"),
                                 brain=SimpleNamespace(perfil={"mobilidade": 0.1}))
        alcances = {"arco": 14.0, "espada": 2.0}
        with mock.patch.object(dinamismo, "alcance_da_arma",
                               side_effect=lambda l: alcances[l.dados.arma_obj]):
            self.assertIsNone(dinamismo.papel_de_alcance(espada, arco))   # desligado
            self.assertEqual(dinamismo.verbo_de_saida(espada, arco), "RECUAR")
            with mock.patch.object(config, "DINAMISMO_ALCANCE_DIFERENCA_M", 4.0), \
                    mock.patch.object(config, "DINAMISMO_ASSIM_VERBO_CURTO", "APROXIMAR"), \
                    mock.patch.object(config, "DINAMISMO_ASSIM_VERBO_LONGO", "nenhum"):
                self.assertEqual(dinamismo.papel_de_alcance(espada, arco), "curto")
                self.assertEqual(dinamismo.papel_de_alcance(arco, espada), "longo")
                self.assertEqual(dinamismo.verbo_de_saida(espada, arco), "APROXIMAR")
                self.assertIsNone(dinamismo.verbo_de_saida(arco, espada))


class ChaveDaLutaTests(unittest.TestCase):
    def test_ausente_vale_o_padrao_desligado(self):
        self.assertFalse(config.DINAMISMO)
        self.assertFalse(dinamismo.chave_ligada({}))
        self.assertFalse(dinamismo.chave_ligada(None))
        self.assertTrue(dinamismo.chave_ligada({"dinamismo": True}))
        self.assertFalse(dinamismo.chave_ligada({"dinamismo": False}))
        with mock.patch.object(config, "DINAMISMO", True):
            self.assertTrue(dinamismo.chave_ligada({}))
            self.assertFalse(dinamismo.chave_ligada({"dinamismo": False}))


@unittest.skipUnless((FIXTURE / "personagens.json").is_file(), "fixture do dinamismo ausente")
class SimuladorTests(unittest.TestCase):
    def _estado(self, extra):
        from neural_fights.simulation.headless import HeadlessMatchRunner

        visto = {}

        class Sonda:
            def on_inicio(self, sim):
                visto["inicio"] = "_dinamismo" in sim.__dict__

            def on_frame(self, sim, dt):
                visto["frame"] = sim.__dict__.get("_dinamismo")

        HeadlessMatchRunner({"p1_nome": LOTE[0]["p1"], "p2_nome": LOTE[0]["p2"],
                             "cenario": "Poco", "best_of": 1, **extra},
                            max_duration=0.5, seed=1, probe=Sonda(),
                            roster_provider=_fonte().provider()).run()
        return visto

    def test_desligada_nao_cria_nem_um_atributo(self):
        for extra in ({}, {"dinamismo": False}):
            visto = self._estado(extra)
            self.assertFalse(visto["inicio"], extra)
            self.assertIsNone(visto["frame"], extra)

    def test_ligada_tem_o_relogio(self):
        visto = self._estado({"dinamismo": True})
        self.assertTrue(visto["inicio"])
        self.assertEqual(set(visto["frame"]), {"colado_t", "recarga", "t"})


def _fonte():
    from neural_fights.tools import qualidade_luta as ql

    with mock.patch.object(ql, "FIXTURE_ENGINE", FIXTURE):
        return ql.FonteDeDados("engine")


# As 6 piores lutas da linha de base (maior trecho colado pelo disco
# desenhado, motor de 8f51d7bd), com as fichas congeladas em
# tests/fixtures/dinamismo (banco vivo de 21/10/2026). O maior trecho de cada
# uma ANTES vai no comentário: 9,6 / 7,6 / 6,9 / 5,0 / 5,0 / 4,8 s.
LOTE = [
    {"p1": "Tiberio Vhormeden", "p2": "Cassiel Fletekollen", "seed": 1384799492, "cenario": "Poco"},
    {"p1": "Gunnar Vexevok", "p2": "Aurelia Telmard", "seed": 105716205, "cenario": "Poco"},
    {"p1": "Vesper Aerjabor", "p2": "Vesper Fynvalum", "seed": 1644011416, "cenario": "Torre"},
    {"p1": "Mirel Umbrusilmirn", "p2": "Vex Fylermar", "seed": 1820350793, "cenario": "Poco"},
    {"p1": "Vanya Kraxadusrugan", "p2": "Orion Drusuplith", "seed": 623982435, "cenario": "Poco"},
    {"p1": "Hiro Zynhjal", "p2": "Flora do Trovão", "seed": 2034825489, "cenario": "Duto"},
]
# A digital de cada uma no motor de antes (vencedor, duração, passos): a
# chave desligada tem de dar exatamente isto.
DIGITAL_ANTES = [
    ("p1", 27.05, 1622), ("p1", 33.183, 1990), ("p1", 32.783, 1966),
    ("p1", 17.667, 1059), ("p2", 18.4, 1103), ("p1", 22.05, 1322),
]


@unittest.skipUnless((FIXTURE / "personagens.json").is_file(), "fixture do dinamismo ausente")
class MetasNoLoteTests(unittest.TestCase):
    """As metas do pedido, travadas nas lutas que mais colavam."""

    @classmethod
    def setUpClass(cls):
        from neural_fights.tools.dinamismo_luta import medir_luta

        fonte = _fonte()
        cls.medidas = {}
        for chave in (False, True):
            cls.medidas[chave] = [
                medir_luta(i["p1"], i["p2"], i["seed"], i["cenario"],
                           extra_config={"dinamismo": chave},
                           roster_provider=fonte.provider())
                for i in LOTE
            ]

    def test_lote_roda(self):
        self.assertTrue(LOTE)
        for m in self.medidas[False] + self.medidas[True]:
            self.assertTrue(m["sucesso"], m.get("erro"))

    def test_chave_desligada_e_a_luta_de_antes(self):
        digitais = [(m["vencedor_slot"], m["duracao"], m["frames"]) for m in self.medidas[False]]
        self.assertEqual(digitais, DIGITAL_ANTES)
        self.assertTrue(all(m["respiros"] == 0 and m["choques"] == 0
                            for m in self.medidas[False]))

    def test_mesma_seed_mesma_luta_duas_vezes(self):
        # O afastamento e o bate e sai não sorteiam: a mesma seed refaz a
        # mesma luta, medida inteira (vencedor, HP, golpes, colado, passos).
        from neural_fights.tools.dinamismo_luta import medir_luta

        fonte = _fonte()
        for indice in (0, 3):
            item = LOTE[indice]
            de_novo = medir_luta(item["p1"], item["p2"], item["seed"], item["cenario"],
                                 extra_config={"dinamismo": True},
                                 roster_provider=fonte.provider())
            self.assertEqual(de_novo, self.medidas[True][indice])
        # caso zero: a chave mudou a luta (a medida compara algo de verdade)
        self.assertNotEqual(self.medidas[True][0], self.medidas[False][0])

    def test_chave_ligada_afasta_e_choca(self):
        self.assertTrue(all(m["respiros"] > 0 for m in self.medidas[True]))
        self.assertTrue(any(m["choques"] > 0 for m in self.medidas[True]))

    def test_caso_zero_sem_a_chave_cola_muito(self):
        antes = self.medidas[False]
        self.assertGreater(max(m["maior_colado_s"] for m in antes), 3.0)

    def test_maior_trecho_colado(self):
        depois = self.medidas[True]
        maiores = [m["maior_colado_s"] for m in depois]
        self.assertLessEqual(statistics.median(maiores), 1.5, maiores)
        self.assertLessEqual(max(maiores), 3.0, maiores)

    def test_tempo_colado_cai_pela_metade(self):
        antes = sum(m["pct_colado"] * m["frames"] for m in self.medidas[False])
        depois = sum(m["pct_colado"] * m["frames"] for m in self.medidas[True])
        self.assertLessEqual(depois, 0.5 * antes, (antes, depois))

    def test_sem_luta_parada_nem_longa(self):
        for m in self.medidas[True]:
            self.assertEqual(m["motivo"], "knockout", m)
            self.assertLessEqual(m["duracao"], 90.0, m)


if __name__ == "__main__":
    unittest.main()
