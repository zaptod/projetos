"""Dois jeitos de a valvula fechada causar FOME, e as duas travas.

A valvula de titulo repetido fechou em 17/09/2026 (repetir e pior que nao
postar). Fechar uma valvula muda o que "barrado" significa: antes era "sai
com aviso", agora e "nao sai nunca". Duas coisas que conviviam com a versao
antiga viraram fome silenciosa — horario vazio sem nenhum erro aparecer.

**1. Estoque cheio de video que nunca sai.**
`aprovados_no_estoque` conta o que passou na vistoria, e o freio da producao
usa esse numero. Uma parte com titulo repetido continuava contando. Com 20
aprovados e 3 repetidos: o freio ve 20 (teto 20) e nao cria; a fila entrega
17 e esvazia; o freio continua vendo 3 e continua sem criar. E o numero
parece saudavel o tempo todo.

**2. Partes da mesma serie com a MESMA chave de titulo.**
`titulos.chave` corta em 60 caracteres. Medido em 17/09: ainda nao colidia
por sorte — a diferenca entre as partes cai antes do limite em 13 das 14
series, e a 14a estava a 3 caracteres do corte. Com o titulo-pergunta longo
que esta chegando ("Eu sou o babaca por nao deixar minha irma usar o vestido
de noiva da nossa mae?"), as SEIS partes davam a mesma chave — e a serie
PARARIA na parte 1, com o sintoma sendo um horario vazio, nao um erro.

Isso era inofensivo enquanto a valvula so avisava. As duas coisas so viraram
defeito por causa do meu proprio conserto anterior, o que e o padrao do dia:
fechar uma saida faz o resto do sistema descobrir que dependia dela.
"""
import unittest


class ChaveMantemAParteTests(unittest.TestCase):
    """O corte come o corpo do titulo, nunca o "(Parte N/M)"."""

    def setUp(self):
        from builds.publicar import titulos
        self.titulos = titulos
        self.longo = ("Eu sou o babaca por não deixar minha irmã usar o "
                      "vestido de noiva da nossa mãe?")

    def test_seis_partes_de_titulo_longo_dao_seis_chaves(self):
        chaves = {self.titulos.chave(f"{self.longo} (Parte {n}/6)")
                  for n in range(1, 7)}
        self.assertEqual(6, len(chaves),
                         "com uma chave so, a serie para na parte 1")

    def test_a_chave_respeita_o_tamanho(self):
        k = self.titulos.chave(f"{self.longo} (Parte 3/6)")
        self.assertLessEqual(len(k), self.titulos.TAMANHO)

    def test_o_sufixo_sobrevive_ao_corte(self):
        k = self.titulos.chave(f"{self.longo} (Parte 3/6)")
        self.assertTrue(k.endswith("parte 3 de 6"), k)

    def test_as_formas_de_escrever_a_parte_dao_a_mesma_chave(self):
        """"(Parte 3/6)" e "Parte 3 de 6" sao o mesmo video."""
        self.assertEqual(self.titulos.chave("Titulo (Parte 3/6)"),
                         self.titulos.chave("Titulo Parte 3 de 6"))

    def test_titulo_SEM_parte_continua_como_antes(self):
        """As variantes A/B de build nao tem sufixo e DEVEM colidir: mesmo
        conteudo, mesmo titulo, dois ids."""
        t = "Ylva Brumalok, Berserker (Fúria) — build 56/100 BUILD MEDIANA"
        self.assertEqual(self.titulos.chave(t), self.titulos.chave(t))
        self.assertNotIn("parte", self.titulos.chave(t))

    def test_series_curtas_nao_mudaram_de_comportamento(self):
        a = self.titulos.chave("A Panela da Discórdia — O Molho (Parte 2/6)")
        b = self.titulos.chave("A Panela da Discórdia — O Molho (Parte 3/6)")
        self.assertNotEqual(a, b)


class EstoqueNaoContaOQueNaoSaiTests(unittest.TestCase):
    def setUp(self):
        from contos.pipeline import agenda
        self.agenda = agenda

    class _V:
        def __init__(self, vid, titulo):
            self.id, self.titulo = vid, titulo

    def _com_ledger(self, no_ar):
        from contos.publicar import serie
        self.addCleanup(setattr, serie, "publicados", serie.publicados)
        serie.publicados = lambda *_a, **_k: [
            {"video_id": "outro", "plataforma": "youtube", "titulo": t,
             "url": "http://x"} for t in no_ar]

    def test_o_repetido_sai_da_conta_do_estoque(self):
        self._com_ledger(["Ja no ar"])
        estoque = [self._V("a", "Ja no ar"), self._V("b", "Inedito")]
        self.assertEqual(
            ["b"], [v.id for v in self.agenda._sem_titulo_barrado(estoque)])

    def test_sem_nada_no_ar_conta_tudo(self):
        self._com_ledger([])
        estoque = [self._V("a", "Um"), self._V("b", "Dois")]
        self.assertEqual(2, len(self.agenda._sem_titulo_barrado(estoque)))

    def test_ledger_ilegivel_conta_TUDO(self):
        """Aqui "nao sei" conta a MAIS de proposito: criar de menos por um
        ledger ilegivel e melhor que criar sem parar."""
        from contos.publicar import serie
        self.addCleanup(setattr, serie, "publicados", serie.publicados)

        def explode(*_a, **_k):
            raise OSError("ledger ilegivel")
        serie.publicados = explode
        estoque = [self._V("a", "Um"), self._V("b", "Dois")]
        self.assertEqual(2, len(self.agenda._sem_titulo_barrado(estoque)))


if __name__ == "__main__":
    unittest.main()
