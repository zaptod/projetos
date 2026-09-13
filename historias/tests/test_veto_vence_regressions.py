# -*- coding: utf-8 -*-
"""Tres rodadas de conserto e o video sai (13/09/2026).

Pedido dele: "ela tem que ter apenas 3 rounds pra consertar as coisas, caso
nao conserte o video tem que sair de qualquer forma". Medido no mesmo dia: os
seis primeiros da fila eram os seis barrados, o publicador so examinava seis,
e onze videos aprovados logo atras nunca eram vistos. Nenhuma historia saiu
nos horarios das 10h e das 12h.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import reparo
from contos.publicar import parecer, qualidade

POSTAR = Path(__file__).resolve().parents[2] / "ferramentas" / "postar.py"


def _postar():
    spec = importlib.util.spec_from_file_location("postar_veto", POSTAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _V:
    id = "historia_00099:celular:p02"
    fonte_id = "historia_00099"
    parte = 2
    caminho = "x.mp4"
    titulo = "t"


REPROVADO = {"aprovado": False, "numeracao": "cena",
             "vista": "video inteiro (2:00)",
             "motivos": ["cena 3: a imagem nao mostra a narracao"]}


class _Base(unittest.TestCase):
    """Isola o registro de consertos e dubla o veredito e a vistoria."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        originais = {
            (reparo, "REGISTRO"): reparo.REGISTRO,
            (parecer, "lembrado"): parecer.lembrado,
            (qualidade, "vistoriar_parte"): qualidade.vistoriar_parte,
        }
        for (modulo, nome), valor in originais.items():
            self.addCleanup(setattr, modulo, nome, valor)
        reparo.REGISTRO = Path(self._tmp.name) / "_reparos.json"
        parecer.lembrado = lambda _v: dict(REPROVADO)
        qualidade.vistoriar_parte = lambda *_a, **_k: {
            "ok": True, "erros": [], "avisos": []}

    def _esgotar(self):
        for _ in range(reparo.TETO_DE_TENTATIVAS):
            reparo._anotar(_V.id, "a IA reprova", "refiz")


class VetoVenceTests(_Base):

    def test_antes_das_tres_rodadas_o_veto_barra(self):
        reparo._anotar(_V.id, "a IA reprova", "refiz")
        veredito = qualidade.liberado(_V(), roteiro={})
        self.assertFalse(veredito["ok"])
        self.assertIn("a IA reprovou", veredito["erros"][0])

    def test_depois_das_tres_rodadas_o_video_sai(self):
        self._esgotar()
        veredito = qualidade.liberado(_V(), roteiro={})
        self.assertTrue(veredito["ok"])
        self.assertEqual("veto vencido", veredito["fonte"])
        self.assertTrue(any("rodadas de conserto acabaram" in a
                            for a in veredito["avisos"]))

    def test_defeito_de_arquivo_continua_barrando(self):
        """Video mudo ou sem imagem nao e opiniao da IA: e arquivo quebrado."""
        self._esgotar()
        qualidade.vistoriar_parte = lambda *_a, **_k: {
            "ok": False, "erros": ["video sem audio"], "avisos": []}
        self.assertFalse(qualidade.liberado(_V(), roteiro={})["ok"])


class RodadaSemConsertoContaTests(_Base):

    def test_ia_reprova_sem_conserto_automatico_gasta_tentativa(self):
        """Sem isto o video nunca chegaria ao teto e ficaria barrado sempre."""
        antes = reparo._plano_pelo_veto_da_ia
        self.addCleanup(setattr, reparo, "_plano_pelo_veto_da_ia", antes)
        reparo._plano_pelo_veto_da_ia = lambda *_a, **_k: {
            "parar": {"acao": "nada", "ok": False, "detalhe": "sem conserto"}}

        class _Pipeline:
            pass

        saida = reparo.reparar(_V(), ["a IA reprovou: cena 3: x"],
                               pipeline=_Pipeline(), log=lambda *_a: None)
        self.assertEqual("nada", saida["acao"])
        self.assertEqual(1, reparo.tentativas(_V.id))


class RodadaNaoEsqueceVetoVencidoTests(_Base):

    def test_veto_vencido_nao_volta_a_ser_barrado(self):
        """O video some dos barrados porque o veto venceu, nao porque passou.

        A rodada zerava a conta de todo video que deixava de ser barrado, e
        com a conta zerada o veto deixava de estar vencido: os quatro
        liberados na primeira rodada real voltaram a travar a fila.
        """
        from contos.pipeline import agenda, controller
        self._esgotar()
        chamadas = []

        def barrados():
            chamadas.append(1)
            if len(chamadas) == 1:
                return [(_V(), ["a IA reprovou: cena 3: x"])]
            return []

        for modulo, nome, valor in ((agenda, "barrados_no_estoque", barrados),
                                    (controller, "Pipeline", lambda: object())):
            self.addCleanup(setattr, modulo, nome, getattr(modulo, nome))
            setattr(modulo, nome, valor)
        reparo.rodada(limite=5, log=lambda *_a: None)
        self.assertEqual(reparo.TETO_DE_TENTATIVAS, reparo.tentativas(_V.id))


class PublicadorTests(_Base):

    def setUp(self):
        super().setUp()
        self.postar = _postar()

    def test_veto_gravado_nao_gasta_tentativa(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def proxima_historia("):]
        corpo = corpo[:corpo.index("\ndef ")]
        self.assertLess(corpo.index("_veto_lembrado("),
                        corpo.index("vistoriar_parte("))
        self.assertNotIn("[:TENTATIVAS]", corpo)

    def test_o_veto_lembrado_vale_ate_vencer(self):
        self.assertIn("REPROVOU", self.postar._veto_lembrado(_V()))
        self._esgotar()
        self.assertEqual("", self.postar._veto_lembrado(_V()))

    def test_veto_vencido_publica_sem_perguntar_de_novo(self):
        self._esgotar()
        antes = parecer.pedir
        self.addCleanup(setattr, parecer, "pedir", antes)

        def nao_pode(*_a, **_k):
            raise AssertionError("perguntou de novo a quem ja venceu")
        parecer.pedir = nao_pode
        self.assertEqual("", self.postar._parecer_da_ia(_V(), {}, {}))

    def test_o_aviso_diz_que_saiu_com_veto(self):
        fonte = POSTAR.read_text(encoding="utf-8")
        aviso = fonte[fonte.index("def avisar("):]
        aviso = aviso[:aviso.index("\ndef ")]
        self.assertIn("veto_vencido", aviso)
        self.assertIn("veto_ignorado", aviso)

    def test_sem_video_limpo_sai_o_vetado_com_arquivo_inteiro(self):
        """"A prioridade e nao ficar sem video.\""""
        from contos.roteiro import roteiro as R
        antes = R.carregar
        self.addCleanup(setattr, R, "carregar", antes)
        R.carregar = lambda _hid: {}
        self.postar.fila_de_historias = lambda: [_V()]
        alvo, recusados = self.postar.proxima_historia()
        self.assertEqual(_V.id, alvo.id)
        self.assertTrue(recusados)

    def test_vetado_com_arquivo_quebrado_nao_sai_nem_assim(self):
        from contos.roteiro import roteiro as R
        antes = R.carregar
        self.addCleanup(setattr, R, "carregar", antes)
        R.carregar = lambda _hid: {}
        qualidade.vistoriar_parte = lambda *_a, **_k: {
            "ok": False, "erros": ["video sem audio"], "avisos": []}
        self.postar.fila_de_historias = lambda: [_V()]
        alvo, _recusados = self.postar.proxima_historia()
        self.assertIsNone(alvo)


if __name__ == "__main__":
    unittest.main()
