# -*- coding: utf-8 -*-
"""Titulo repetido sai da fila.

Por que existe (auditoria de 15/09/2026): 13 das 40 builds foram ao ar DUAS
vezes com titulo identico, competindo entre si. A deduplicacao do projeto e
por `video_id`, e a variante "gancho B" tem id com sufixo `":B"` e o mesmo
titulo — para o codigo, dois videos; para o YouTube, dois videos iguais.

Nenhum teste aqui toca disco ou rede: as linhas do ledger sao injetadas.
"""
import unittest

from builds.publicar import metricas, titulos


class ChaveDeTitulo(unittest.TestCase):

    def test_a_variante_b_tem_a_mesma_chave_do_original(self):
        # O CASO. Mesmo titulo, ids diferentes (`...:B`), e nada comparava.
        a = "ELE ACERTOU 97/100 — build de mago"
        b = "ELE ACERTOU 97/100 — build de mago"
        self.assertEqual(titulos.chave(a), titulos.chave(b))

    def test_normaliza_caixa_espaco_e_emoji(self):
        self.assertEqual(titulos.chave("  O   MAGO 🔥 "),
                         titulos.chave("o mago"))

    def test_corta_no_tamanho_do_criterio_original(self):
        longo = "a" * 200
        self.assertEqual(len(titulos.chave(longo)), titulos.TAMANHO)

    def test_o_apelido_antigo_devolve_o_mesmo(self):
        # `metricas._chave_de_titulo` continua sendo usada por `reconciliar`.
        # Se as duas divergirem, a reconciliacao passa a casar por um
        # criterio e a fila a barrar por outro.
        for texto in ("O MAGO 🔥", "  dois   espacos ", "", "a" * 120):
            self.assertEqual(metricas._chave_de_titulo(texto),
                             titulos.chave(texto))


class FilaQueNaoRepete(unittest.TestCase):

    LEDGER = [
        {"titulo": "ELE ACERTOU 97/100", "url": "https://youtu.be/aaa"},
        {"titulo": "O DUELO DO SECULO", "url": "publicado no TikTok"},
        # Linha sem destino: tentou e nao saiu. Nao ocupou lugar no canal.
        {"titulo": "NUNCA FOI AO AR", "url": ""},
    ]

    def test_conta_as_duas_plataformas(self):
        ja = titulos.ja_publicados(self.LEDGER)
        self.assertIn(titulos.chave("ELE ACERTOU 97/100"), ja)
        self.assertIn(titulos.chave("O DUELO DO SECULO"), ja)

    def test_linha_sem_url_nao_barra_ninguem(self):
        ja = titulos.ja_publicados(self.LEDGER)
        self.assertFalse(titulos.repetido("NUNCA FOI AO AR", ja))

    def test_o_gancho_b_e_barrado(self):
        ja = titulos.ja_publicados(self.LEDGER)
        self.assertTrue(titulos.repetido("ELE ACERTOU 97/100", ja))

    def test_titulo_vazio_nunca_e_repetido(self):
        # `chave("")` e `chave("   ")` dao a mesma string vazia; trata-la
        # como igual barraria todo video sem titulo contra todo outro video
        # sem titulo — um empate de nada com nada.
        ja = titulos.ja_publicados([{"titulo": "", "url": "http://x"}])
        self.assertFalse(titulos.repetido("", ja))
        self.assertFalse(titulos.repetido("   ", ja))

    def test_ledger_vazio_ou_torto_nao_levanta(self):
        for entrada in (None, [], [None], ["texto solto"], [{}]):
            self.assertEqual(titulos.ja_publicados(entrada), set())


if __name__ == "__main__":
    unittest.main()
