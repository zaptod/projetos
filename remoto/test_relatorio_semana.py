# -*- coding: utf-8 -*-
"""/semana: o Telegram FORMATA a medida da semana, nao calcula (21/10/2026).

O numero mora em `builds.publicar.analise.medida_da_semana` (so disco). Aqui
o texto e dublado; nenhum caso toca ledger, rede ou Telegram de verdade.
"""
import unittest

from remoto import comandos, config, relatorios


class OTexto(unittest.TestCase):

    def setUp(self):
        from builds.publicar import analise
        real = analise.texto_da_semana
        self.addCleanup(setattr, analise, "texto_da_semana", real)
        self.analise = analise

    def test_formata_o_texto_da_analise(self):
        self.analise.texto_da_semana = lambda agora=None: "YouTube: 3 novo(s) × 19 antigo(s)"
        texto = relatorios.montar("semana")
        self.assertTrue(texto.startswith("📏 *Medida da semana*"))
        self.assertIn("3 novo(s) × 19 antigo(s)", texto)

    def test_falha_vira_texto_e_nao_derruba_o_bot(self):
        def quebra(agora=None):
            raise RuntimeError("disco")
        self.analise.texto_da_semana = quebra
        self.assertIn("falhou", relatorios.montar("semana"))


class OComando(unittest.TestCase):

    def test_esta_na_tabela_e_na_ajuda(self):
        self.assertIs(comandos.TABELA["semana"], comandos.semana)
        self.assertIn("/semana", comandos.ajuda())

    def test_nao_sai_sozinho_sem_horario(self):
        # Mandar mensagem todo dia e decisao; o padrao so tem os tres de antes.
        self.assertNotIn("semana", config.PADRAO["relatorios"])


if __name__ == "__main__":
    unittest.main()
