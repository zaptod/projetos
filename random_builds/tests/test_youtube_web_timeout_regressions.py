# -*- coding: utf-8 -*-
"""Regressões de timeout na publicação pelo YouTube Studio (navegador).

O que estes testes protegem:

1. O clique em "não é conteúdo para crianças" usa timeout de 10s em vez de 30s
   (timeout padrão do Playwright), para falhar rápido se o elemento não ficar
   clicável (por exemplo, coberto por overlay ou diálogo).

2. Se o clique falhar por timeout, a publicação não trava — apenas avisa e
   deixa a janela aberta para o usuário corrigir manualmente.

3. O comportamento é resiliente: se o elemento não existir, continua; se
   existir mas não ficar clicável, avisa mas não para a publicação.

Rode de dentro de random_builds/:
    python -m unittest tests.test_youtube_web_timeout_regressions -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from builds.publicar import youtube_web


class ClickTimeoutTests(unittest.TestCase):
    """O clique em 'feito para crianças' é resiliente a timeouts."""

    def test_primeiro_tenta_com_timeout_especificado(self):
        """_primeiro deveria tentar esperar cada seletor com o timeout dado."""
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value.first = locator

        # Simula elemento visível
        locator.wait_for.return_value = None

        resultado = youtube_web._primeiro(page, ["selector1"], timeout=5.0)

        # Deve ter esperado com 5 segundos (5000 ms)
        locator.wait_for.assert_called_with(state="visible", timeout=5000)
        self.assertIsNotNone(resultado)

    def test_click_timeout_menor_que_padrao_playwright(self):
        """O clique tem timeout menor que 30s para falhar rápido."""
        # Este teste valida que a chamada de clique no código usa timeout
        # reduzido. Lê o fonte para verificar.
        fonte = __import__("inspect").getsource(youtube_web.publicar)
        # Procura pela seção de "não é para crianças"
        trecho = fonte[fonte.index("NAO_E_PARA_CRIANCAS"):]
        trecho = trecho[:trecho.index("BOTAO_PROXIMO")]

        # Deve ter criancas.click(timeout=10000) em vez de criancas.click()
        self.assertIn("timeout=10000", trecho,
                      "clique em 'feito para crianças' deve ter timeout=10000")

    def test_falha_no_click_nao_para_publicacao(self):
        """Se o clique falhar, continua — a janela fica aberta."""
        # Este teste valida que o código trata exceção do clique
        fonte = __import__("inspect").getsource(youtube_web.publicar)
        trecho = fonte[fonte.index("NAO_E_PARA_CRIANCAS"):]
        trecho = trecho[:trecho.index("BOTAO_PROXIMO")]

        # Deve ter try/except em torno do clique
        self.assertIn("try:", trecho, "deve ter try em torno do clique")
        self.assertIn("except", trecho, "deve ter except para tratamento de erro")

    def test_aviso_se_nao_conseguir_clicar(self):
        """Se o clique falhar, deve avisar ao usuário."""
        fonte = __import__("inspect").getsource(youtube_web.publicar)
        trecho = fonte[fonte.index("NAO_E_PARA_CRIANCAS"):]
        trecho = trecho[:trecho.index("BOTAO_PROXIMO")]

        # Deve mencionar a falha ao usuário
        self.assertIn("AVISO", trecho)
        self.assertIn("dialogo", trecho,
                      "deve mencionar que pode haver diálogo cobrindo")


class ResilienciaTests(unittest.TestCase):
    """O código de publicação é resiliente a falhas de UI."""

    def test_elemento_nao_encontrado_nao_para(self):
        """Se 'feito para crianças' não existe, continua publicando."""
        fonte = __import__("inspect").getsource(youtube_web.publicar)
        trecho = fonte[fonte.index("NAO_E_PARA_CRIANCAS"):]
        trecho = trecho[:trecho.index("BOTAO_PROXIMO")]

        # Se criancas é None, deve apenas avisar, não levantar exceção
        self.assertIn("if criancas is None:", trecho)
        self.assertNotIn("raise", trecho.split("if criancas is None:")[1]
                         .split("else:")[0],
                         "não deve levantar exceção se elemento não existe")

    def test_sequence_nao_quebra_com_falha_intermediaria(self):
        """A sequência de cliques continua mesmo com uma falha no meio."""
        fonte = __import__("inspect").getsource(youtube_web.publicar)

        # Procura por "cheguei na visibilidade" após o bloco de criancas
        inicio = fonte.index("NAO_E_PARA_CRIANCAS")
        fim_criancas = fonte.index("BOTAO_PROXIMO", inicio)
        fim_loop = fonte.index("cheguei na visibilidade", fim_criancas)

        # Deve haver loop de "Próximo" depois de tentar "criancas"
        self.assertGreater(fim_loop, fim_criancas,
                           "'cheguei na visibilidade' deve estar após o bloco "
                           "de 'criancas'")


if __name__ == "__main__":
    unittest.main()
