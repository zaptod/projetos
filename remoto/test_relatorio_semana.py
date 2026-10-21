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

    def test_sai_sozinho_as_21_05(self):
        # Grimorio metricas/semana-no-telegram (21/10/2026): "todo dia as
        # 21:05 pelo bot". Antes o padrao nao tinha `semana` (so por pedido).
        from datetime import datetime
        horarios = config.PADRAO["relatorios"]
        self.assertEqual("21:05", horarios["semana"])
        self.assertIn("semana", relatorios.devidos(
            horarios, datetime(2026, 10, 22, 21, 5), ja_enviados={}))
        self.assertNotIn("semana", relatorios.devidos(
            horarios, datetime(2026, 10, 22, 21, 4), ja_enviados={}))
        self.assertNotIn("semana", relatorios.devidos(
            horarios, datetime(2026, 10, 22, 21, 30),
            ja_enviados={"semana": "2026-10-22"}), "uma vez por dia")


class OEnvioLongo(unittest.TestCase):
    """O Telegram corta em 4096; ate 21/10 o envio cortava em 4000 e o fim
    sumia (a medida da semana cheia perdia o TikTok e os avisos "!")."""

    def _bot(self):
        from remoto import api
        enviados = []

        class _T(api.Telegram):
            def chamar(self, metodo, **campos):
                enviados.append(campos)
                return {"ok": True}
        return _T("x"), enviados

    def test_texto_longo_vai_inteiro_em_partes(self):
        texto = "\n".join(f"linha {i:04d} " + "x" * 80 for i in range(100))   # ~9 mil
        tg, enviados = self._bot()
        self.assertTrue(tg.mensagem(1, texto, markdown=True).get("ok"))
        self.assertGreater(len(enviados), 1)
        self.assertTrue(all(len(e["text"]) <= 4000 for e in enviados))
        self.assertEqual(texto, "\n".join(e["text"] for e in enviados), "nada se perde")

    def test_texto_curto_e_uma_mensagem_so(self):
        tg, enviados = self._bot()
        tg.mensagem(1, "oi")
        self.assertEqual(["oi"], [e["text"] for e in enviados])

    def test_linha_gigante_e_quebrada_sem_perder_nada(self):
        from remoto import api
        partes = api.partes_da_mensagem("a" * 9000)
        self.assertEqual([4000, 4000, 1000], [len(p) for p in partes])
        self.assertEqual(["oi"], api.partes_da_mensagem("oi"))
        self.assertEqual([""], api.partes_da_mensagem(""))

    def test_parte_que_falha_para_e_devolve_a_falha(self):
        from remoto import api
        vezes = []

        class _T(api.Telegram):
            def chamar(self, metodo, **campos):
                vezes.append(campos)
                return {"ok": len(vezes) == 1, "description": "rede"}
        resposta = _T("x").mensagem(1, "\n".join("y" * 900 for _ in range(10)))
        self.assertFalse(resposta.get("ok"), "o relatorio nao pode ser marcado como enviado")
        self.assertEqual(2, len(vezes))


if __name__ == "__main__":
    unittest.main()
