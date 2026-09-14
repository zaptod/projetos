# -*- coding: utf-8 -*-
"""O parecer reprova contradicao, nao detalhe (13/09/2026, 23h50).

A primeira revisao da madrugada mandou 11 videos do estoque ao Gemini e ele
aprovou zero. Das 34 cenas apontadas, 25 eram "a imagem nao mostra o que a
narracao conta", e quase todas por detalhe: o tique de cocar a sobrancelha, o
clique no botao verde, a impressora, o reitor na plateia. Uma imagem gerada
por cena nunca acerta isso. A regra passa a reprovar so contradicao, e cada
veredito grava com qual criterio foi dado, para o veto antigo ser perguntado
de novo.
"""
from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import agenda, reparo
from contos.pipeline import conserto_de_cena as C
from contos.publicar import parecer

ROTEIRO = {"partes": [{"n": 1, "cenas": [
    {"n": 1, "tempo": 5, "imagem": "y",
     "narracao": "Ela imprimiu a ordem e guardou no bolso."}]}]}


class _Video:
    titulo = "O e-mail oficial (Parte 3/6)"
    caminho = "x.mp4"


class CriterioTests(unittest.TestCase):

    def test_veto_com_regua_velha_nao_e_atual(self):
        self.assertFalse(C.atual({"numeracao": "cena"}))
        self.assertFalse(C.atual({"numeracao": "cena",
                                  "criterio": parecer.CRITERIO - 1}))
        self.assertTrue(C.atual({"numeracao": "cena",
                                 "criterio": parecer.CRITERIO}))
        self.assertFalse(C.atual({"numeracao": "quadro",
                                  "criterio": parecer.CRITERIO}))

    def test_detalhe_que_falta_nao_reprova(self):
        texto = parecer.prompt(_Video(), ROTEIRO, 1, {})
        self.assertIn("nao mostrar um DETALHE da narracao", texto)
        self.assertIn("CONTRADIZ a narracao daquela cena", texto)

    def test_a_revisao_da_madrugada_pergunta_de_novo_o_veto_velho(self):
        self.assertIn("C.atual(", inspect.getsource(agenda.revisar_estoque))

    def test_o_reparo_pergunta_de_novo_o_veto_velho(self):
        self.assertIn("C.atual(",
                      inspect.getsource(reparo._plano_pelo_veto_da_ia))


class ReguaNovaSubstituiVelhaTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        pasta = Path(self._tmp.name)
        antes = parecer.LEMBRETES
        parecer.LEMBRETES = pasta / "_pareceres.json"
        self.addCleanup(lambda: setattr(parecer, "LEMBRETES", antes))
        mp4 = pasta / "final_celular_p03.mp4"
        mp4.write_bytes(b"um video")

        class _V:
            id = "historia_00010:celular:p03"
        self.video = _V()
        self.video.caminho = mp4

    def test_folha_com_regua_nova_entra_no_lugar_do_video_com_regua_velha(self):
        parecer.lembrar(self.video, {
            "aprovado": False, "vista": "video inteiro (2:30)",
            "numeracao": "cena", "criterio": 1,
            "motivos": ["cena 12: nao mostra a impressora"]})
        parecer.lembrar(self.video, {
            "aprovado": True, "vista": "folha de contato",
            "numeracao": "cena", "criterio": parecer.CRITERIO,
            "motivos": []})
        ficha = parecer.lembrado(self.video)
        self.assertTrue(ficha["aprovado"])
        self.assertEqual(parecer.CRITERIO, ficha["criterio"])


if __name__ == "__main__":
    unittest.main()
