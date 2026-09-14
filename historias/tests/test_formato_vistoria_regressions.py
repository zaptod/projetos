# -*- coding: utf-8 -*-
"""A vistoria entende o video acelerado (14/09/2026).

A faixa de palavras por segundo e de fala humana. Com a historia acelerada
1,7x de proposito, uma parte boa (2,5 palavras/s) mediria 4,3 e seria barrada
como "audio cortado" — a vistoria travaria todo video novo.

Rode de dentro de historias/:
    python -m unittest tests.test_formato_vistoria_regressions -v
"""
from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path

from contos.pipeline import conferir
from contos.publicar import qualidade
from contos.roteiro import roteiro as R


class RitmoTests(unittest.TestCase):

    def test_parte_boa_acelerada_passa(self):
        """400 palavras em 82 s a 1,7x = 2,9 palavras/s na fala natural."""
        ritmo = qualidade.avaliar_ritmo(400, 82.0, 1.7)
        self.assertEqual([], ritmo["erros"])
        self.assertAlmostEqual(4.88, ritmo["palavras_por_s"], places=2)
        self.assertAlmostEqual(2.87, ritmo["palavras_por_s_natural"], places=2)

    def test_a_mesma_parte_sem_aceleracao_e_audio_cortado(self):
        ritmo = qualidade.avaliar_ritmo(400, 82.0, 1.0)
        self.assertEqual(1, len(ritmo["erros"]))
        self.assertIn("(4.9 palavras/s)", ritmo["erros"][0])

    def test_o_defeito_da_historia_8_continua_sendo_pego_acelerado(self):
        ritmo = qualidade.avaliar_ritmo(417, 21.84 / 1.7, 1.7)
        self.assertTrue(ritmo["erros"])
        self.assertIn("19.1 na fala natural", ritmo["erros"][0])

    def test_na_velocidade_normal_a_mensagem_nao_muda(self):
        ritmo = qualidade.avaliar_ritmo(417, 21.84, 1.0)
        self.assertIn("417 palavras em 22s (19.1 palavras/s): a narracao nao "
                      "cabe no video", ritmo["erros"][0])

    def test_arrastado_e_so_aviso(self):
        ritmo = qualidade.avaliar_ritmo(100, 100.0, 1.0)
        self.assertEqual([], ritmo["erros"])
        self.assertTrue(ritmo["avisos"])

    def test_sem_palavras_ou_duracao_nao_julga(self):
        self.assertIsNone(qualidade.avaliar_ritmo(0, 80.0)["palavras_por_s"])
        self.assertIsNone(qualidade.avaliar_ritmo(300, 0.0)["palavras_por_s"])


class FormatoDoArquivoTests(unittest.TestCase):

    def test_a_etiqueta_do_mp4_responde_primeiro(self):
        dados = {"format": {"tags": {
            "comment": "contos:velocidade=1.700;layout=dividido"}}}
        self.assertEqual({"velocidade": 1.7, "layout": "dividido"},
                         qualidade.formato_de(dados, "historia_x", 1))

    def test_sem_etiqueta_vale_o_plano_da_parte(self):
        with tempfile.TemporaryDirectory() as tmp:
            antes = R.OUTPUTS
            self.addCleanup(setattr, R, "OUTPUTS", antes)
            R.OUTPUTS = Path(tmp)
            pasta = Path(tmp) / "historia_x" / "partes" / "p02"
            pasta.mkdir(parents=True)
            (pasta / "edit_plan.json").write_text(json.dumps({
                "formato": {"velocidade": 1.7, "layout": "dividido"},
                "formato_efetivo": {"velocidade": 1.7, "layout": "vertical"}}),
                encoding="utf-8")
            achado = qualidade.formato_de({}, "historia_x", 2)
        # O que SAIU vale mais que o que foi pedido.
        self.assertEqual({"velocidade": 1.7, "layout": "vertical"}, achado)

    def test_video_antigo_e_normal_e_tela_inteira(self):
        self.assertEqual({"velocidade": 1.0, "layout": "vertical"},
                         qualidade.formato_de({}, None, None))

    def test_o_ffprobe_pede_a_etiqueta(self):
        self.assertIn("format_tags=comment",
                      inspect.getsource(qualidade._ffprobe))


class UmaRegraSoTests(unittest.TestCase):
    """As duas vistorias usam a mesma conta, e nenhuma compara na mao."""

    def test_vistoria_de_publicar_usa_a_regra(self):
        fonte = inspect.getsource(qualidade.vistoriar_parte)
        self.assertIn("avaliar_ritmo(", fonte)
        self.assertNotIn("> PALAVRAS_POR_S_MAX", fonte)

    def test_conferir_usa_a_regra(self):
        fonte = inspect.getsource(conferir.partes_da_historia)
        self.assertIn("qualidade.avaliar_ritmo(", fonte)
        self.assertIn("qualidade.formato_de(", fonte)
        self.assertNotIn("> qualidade.PALAVRAS_POR_S_MAX", fonte)


if __name__ == "__main__":
    unittest.main()
