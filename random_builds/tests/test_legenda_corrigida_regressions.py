"""A legenda corrigida so conta quando o TikTok devolve o texto INTEIRO.

Decisao `legenda-h31-p06` (28/09/2026). A legenda da
`historia_00031:celular:p06` (post 7690426388284771592) saiu com 109 de 230
caracteres; o `desc` do Studio, lido pelas metricas, era:

    "A Casa 42 Parte 6 de 6 — as outras estão no canal, na ordem.
     #historias #relatos #reddit #storytime #shorts"

sem "Eu escrevo e conto essas histórias aqui..." e "O que você faria no
lugar dele?". A prova da correcao e `mesma_legenda(desc, catalogo)`: o texto
inteiro, so com o espaco normalizado — o Studio devolve os paragrafos com
espaco simples, e o catalogo os escreve com linha em branco.
"""
import unittest

from builds.publicar import tiktok

CATALOGO = ("A Casa 42\n\nParte 6 de 6 — as outras estão no canal, na "
            "ordem.\n\nEu escrevo e conto essas histórias aqui. Os "
            "personagens e os nomes são invenção minha.\n\nO que você faria "
            "no lugar dele?\n\n#historias #relatos #reddit #storytime #shorts")
NO_AR_ANTES = ("A Casa 42 Parte 6 de 6 — as outras estão no canal, na "
               "ordem. #historias #relatos #reddit #storytime #shorts")


class MesmaLegendaTests(unittest.TestCase):
    def test_a_legenda_de_hoje_NAO_confere(self):
        self.assertEqual(230, len(CATALOGO))
        self.assertFalse(tiktok.mesma_legenda(NO_AR_ANTES, CATALOGO))

    def test_o_texto_inteiro_com_outro_espacamento_confere(self):
        no_ar = " ".join(CATALOGO.split())
        self.assertTrue(tiktok.mesma_legenda(no_ar, CATALOGO))

    def test_sem_leitura_nunca_confere(self):
        """`None` e "nao consegui ler": nao pode virar "esta certo"."""
        self.assertFalse(tiktok.mesma_legenda(None, CATALOGO))

    def test_falta_so_a_ultima_hashtag_NAO_confere(self):
        self.assertFalse(tiktok.mesma_legenda(
            CATALOGO.replace(" #shorts", ""), CATALOGO))

    def test_o_editor_e_o_do_post(self):
        self.assertIn("/upload/post/7690426388284771592",
                      tiktok.URL_EDITAR.format(id="7690426388284771592"))


if __name__ == "__main__":
    unittest.main()
