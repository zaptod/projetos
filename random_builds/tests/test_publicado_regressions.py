# -*- coding: utf-8 -*-
"""`metricas.publicado(linha)`: a resposta unica para "o video saiu?".

Ate 16/09/2026 cada leitor do ledger respondia com `bool(linha["url"])`, e o
`url` guardava tres coisas: o link, a frase de estado e, no TikTok, sempre a
frase. A frase contava como "saiu" — e por isso rascunho e publicacao de
verdade eram identicos para todo filtro do projeto.

Passo 1 do contrato: o campo `publicado` manda quando existe; linha antiga
sem ele cai no criterio de antes, para nenhum leitor mudar de resposta sem o
ledger ter sido migrado.
"""
import unittest

from builds.publicar import metricas as M
from builds.publicar import titulos


class OContrato(unittest.TestCase):

    def test_o_campo_novo_manda(self):
        self.assertFalse(M.publicado({"publicado": False,
                                      "url": "publicado no YouTube"}))
        self.assertTrue(M.publicado({"publicado": True, "url": ""}))

    def test_linha_antiga_cai_no_criterio_de_antes(self):
        # Nenhum leitor pode mudar de resposta antes da migracao.
        self.assertTrue(M.publicado({"url": "https://youtu.be/x"}))
        self.assertTrue(M.publicado({"url": "publicado no TikTok"}))
        self.assertFalse(M.publicado({"url": ""}))
        self.assertFalse(M.publicado({}))

    def test_entrada_torta_e_nao(self):
        for torta in (None, "texto", 3, []):
            self.assertFalse(M.publicado(torta))


class OsLeitoresUsamAFuncao(unittest.TestCase):
    """Uma linha com frase no `url` e `publicado: false` e o caso que a cura
    vai produzir para os rascunhos. Cada leitor tem de enxerga-la como NAO
    publicada — se algum ainda olhar o `url`, ela volta a contar."""

    RASCUNHO = {"video_id": "g1:build:celular", "titulo": "O MAGO",
                "plataforma": "youtube", "quando": "2026-09-16T09:40:00",
                "url": "publicado no YouTube (com a confirmacao extra)",
                "publicado": False}

    def test_titulos_nao_conta_rascunho_como_titulo_no_ar(self):
        self.assertEqual(set(), titulos.ja_publicados([self.RASCUNHO]))

    def test_serie_nao_da_rascunho_como_ja_publicado(self):
        from contos.publicar import serie
        real = serie.publicados
        serie.publicados = lambda: [dict(self.RASCUNHO,
                                         video_id="h1:celular:p01")]
        self.addCleanup(lambda: setattr(serie, "publicados", real))
        self.assertIsNone(serie.ja_publicado("h1:celular:p01"))

    def test_a_confiabilidade_nao_conta_rascunho(self):
        from panorama import confiabilidade as C
        ficha = C.hoje("2026-09-16", builds=[self.RASCUNHO], historias=[],
                       eventos=[], conferencias={})
        self.assertEqual(0, ficha["prometido"])

    def test_a_auditoria_nao_conta_rascunho(self):
        from panorama import auditoria as A
        self.assertFalse(A._publicado(self.RASCUNHO))
        self.assertTrue(A._publicado(dict(self.RASCUNHO, publicado=True)))

    def test_nenhum_leitor_liberado_voltou_a_olhar_o_url(self):
        # Os leitores do passo 1. `ferramentas/postar.py` fica para depois,
        # por decisao da coordenacao (a outra sessao esta nele).
        from pathlib import Path
        raiz = Path(__file__).resolve().parents[2]
        for relativo in ("historias/contos/pipeline/agenda.py",
                         "random_builds/builds/publicar/titulos.py",
                         "visao/panorama/confiabilidade.py",
                         "painel/paginas/publicar.py"):
            texto = (raiz / relativo).read_text(encoding="utf-8")
            self.assertNotIn('.get("url")', texto, relativo)


if __name__ == "__main__":
    unittest.main()
