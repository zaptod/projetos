# -*- coding: utf-8 -*-
"""O clique no botao de publicar do TikTok (11/09/2026).

O que aconteceu, medido: no horario das 12:07, `duelo_00001` subiu no YouTube
e ficou fora do TikTok. O erro dizia `Timeout 30000ms exceeded` esperando
`button[data-e2e="post_video_button"]` — 30 s que nao eram de ninguem: o
orcamento de processamento e de 300 s e estava intacto.

A causa: `SINAIS_PRONTO` era uma lista de tres, e `_primeiro` devolve o
PRIMEIRO seletor que casa. O ultimo da lista era `video`, que existe assim
que o arquivo chega — muito antes de o TikTok terminar de processar. A
espera saia em segundos, o clique caia num botao ainda desabilitado, e o
Playwright entao usava o timeout PADRAO de 30 s.

Dois erros somados, e nenhum dos dois aparecia no numero do erro.

    cd e:\\projetos\\random_builds
    python -m pytest tests/test_tiktok_botao_desabilitado_regressions.py -q
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from builds.publicar import tiktok


class ProvaDeProntoTests(unittest.TestCase):

    def test_a_prova_exige_o_botao_habilitado(self):
        self.assertIn(":not([disabled])", tiktok.PROVA_DE_PRONTO)
        self.assertIn("post_video_button", tiktok.PROVA_DE_PRONTO)

    def test_um_video_na_tela_nao_conta_como_pronto(self):
        """`video` casa assim que o arquivo chega. Como prova de pronto, ele
        fazia a espera de 300 s terminar em segundos."""
        self.assertNotIn("video", (tiktok.PROVA_DE_PRONTO,))
        self.assertIn("video", tiktok.SINAIS_DE_PROGRESSO)

    def test_progresso_e_prova_sao_listas_diferentes(self):
        self.assertNotIn(tiktok.PROVA_DE_PRONTO, tiktok.SINAIS_DE_PROGRESSO)

    def test_a_prova_e_um_seletor_so(self):
        """Se voltar a ser tupla, `_primeiro` volta a aceitar o mais fraco."""
        self.assertIsInstance(tiktok.PROVA_DE_PRONTO, str)


class TimeoutDoCliqueTests(unittest.TestCase):
    """O numero tem que ser DITO, senao o Playwright usa 30 s."""

    def setUp(self):
        self.fonte = Path(tiktok.__file__).read_text(encoding="utf-8")
        # Ha DOIS `botao.click()` no arquivo: o do modal de confirmacao
        # ("Publicar agora"), que ja aparece habilitado, e o de publicar, que
        # e o que espera o processamento. Mirar no primeiro que o regex achar
        # testa o botao errado — foi o que este teste fez na primeira versao.
        self.publicar = self.fonte[
            self.fonte.index("_primeiro(page, BOTAO_POSTAR"):]

    def test_o_clique_de_publicar_diz_o_timeout(self):
        achado = re.search(r"botao\.click\(([^\n]*)\)", self.publicar)
        self.assertIsNotNone(achado, "o clique de publicar sumiu do fonte")
        self.assertIn("timeout", achado.group(1),
                      "sem timeout explicito o Playwright espera so 30 s pelo "
                      "botao habilitar, e o TikTok passa disso processando")

    def test_a_espera_de_habilitar_cabe_no_processamento(self):
        self.assertGreaterEqual(tiktok.ESPERA_HABILITAR_S, 60.0)
        self.assertLessEqual(tiktok.ESPERA_HABILITAR_S,
                             tiktok.ESPERA_PROCESSAR_S)

    def test_o_estouro_vira_erro_legivel_e_nao_traceback(self):
        """O painel e o Telegram mostram a FRASE. `TimeoutError` cru nao diz
        o que fazer; `TikTokFalhou` diz que a janela segue aberta."""
        self.assertIn("TikTokFalhou(", self.publicar)
        self.assertIn("não ficou clicável", self.publicar)


class EsperaDeProcessamentoTests(unittest.TestCase):

    def setUp(self):
        self.fonte = Path(tiktok.__file__).read_text(encoding="utf-8")

    def test_o_laco_de_espera_usa_a_prova_e_nao_o_progresso(self):
        laco = self.fonte[self.fonte.index("limite = time.time() + ESPERA_PROCESSAR_S"):]
        laco = laco[:600]
        self.assertIn("PROVA_DE_PRONTO", laco)

    def test_arquivo_na_tela_sem_botao_ainda_tenta_publicar(self):
        """Se o TikTok trocar o `data-e2e`, exigir so a prova travaria tudo
        por 300 s e desistiria. Com o arquivo na tela, vale tentar."""
        trecho = self.fonte[self.fonte.index("pronto = chegou = None"):]
        trecho = trecho[:900]
        self.assertIn("pronto is None and chegou is None", trecho,
                      "a desistencia tem que exigir que NENHUM dos dois "
                      "tenha aparecido")


if __name__ == "__main__":
    unittest.main()
