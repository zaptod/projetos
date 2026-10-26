# -*- coding: utf-8 -*-
"""26/10/2026: o 1o upload da conta zombie_surviv0rs abre o dialogo "Ativar
verificacoes automaticas de conteudo?" sobre o formulario; a legenda estourou
TimeoutError 3x (tela 20261026_102335). `_fechar_aviso` o fecha com Cancelar
antes de escrever; sem aviso na tela (caso ZERO) nao clica em nada."""
import unittest

from builds.publicar import tiktok


class _Alvo:
    def __init__(self, pagina, seletor):
        self.p, self.s = pagina, seletor

    @property
    def first(self):
        return self

    def wait_for(self, state=None, timeout=0):
        if self.s not in self.p.botoes:
            raise TimeoutError

    def click(self, timeout=0):
        self.p.cliques.append(self.s)


class _Pagina:
    def __init__(self, texto, botoes=()):
        self.texto, self.botoes, self.cliques = texto, set(botoes), []

    def evaluate(self, _js):
        return self.texto

    def locator(self, seletor):
        return _Alvo(self, seletor)


class AvisoTests(unittest.TestCase):
    def test_fecha_com_cancelar(self):
        pg = _Pagina("Ativar verificações automáticas de conteúdo?",
                     {tiktok.BOTOES_DO_AVISO[0]})
        self.assertTrue(tiktok._fechar_aviso(pg, lambda t: None))
        self.assertEqual(pg.cliques, [tiktok.BOTOES_DO_AVISO[0]])

    def test_sem_aviso_nao_clica(self):
        pg = _Pagina("Descricao Hashtags", set(tiktok.BOTOES_DO_AVISO))
        self.assertEqual(tiktok._fechar_aviso(pg, lambda t: None), "")
        self.assertEqual(pg.cliques, [])

    def test_aviso_sem_botao_nao_levanta(self):
        pg = _Pagina("verificacoes automaticas de conteudo")
        self.assertEqual(tiktok._fechar_aviso(pg, lambda t: None), "")


if __name__ == "__main__":
    unittest.main()
