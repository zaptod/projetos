"""A falha de publicacao diz DE QUAL DESTINO ela veio.

`atividade.fabrica` sempre aceitou `etapa` e `ref`, e os dois publicadores
nunca passavam nenhum dos dois. Consequencia: uma excecao crua — um
`TimeoutError` no `goto`, o Chrome que nao abriu — entrava no diario como
"publicacao" e nada mais. O /confiabilidade somava YouTube e TikTok no mesmo
balde, e "o TikTok nao abriu" ficava indistinguivel de "o YouTube recusou",
que tem consertos diferentes.

`ref` importa pelo mesmo motivo, um nivel abaixo: sem saber A QUE VIDEO a
falha pertence, nao da para separar "este video e ruim" de "este passo esta
quebrado" — que foi exatamente a pergunta que ninguem conseguiu responder
sobre os 8 builds perdidos no TikTok.

Este teste NAO abre navegador: ele confere o contrato no ponto em que ele e
declarado.
"""
import inspect
import unittest

from builds.publicar import tiktok, youtube_web


class EtapaNaPublicacaoTests(unittest.TestCase):
    def _fonte(self, funcao) -> str:
        """O codigo, sem os comentarios — eles citam as mesmas palavras."""
        return "\n".join(l for l in inspect.getsource(funcao).splitlines()
                         if not l.strip().startswith("#"))

    def test_tiktok_marca_a_etapa_e_o_video(self):
        fonte = self._fonte(tiktok.publicar)
        self.assertIn('etapa="publicar.tiktok"', fonte)
        self.assertIn("ref=getattr(video", fonte)

    def test_youtube_marca_a_etapa_e_o_video(self):
        fonte = self._fonte(youtube_web.publicar)
        self.assertIn('etapa="publicar.youtube"', fonte)
        self.assertIn("ref=getattr(video", fonte)

    def test_as_duas_etapas_sao_DIFERENTES(self):
        """O ponto inteiro: se as duas dissessem a mesma coisa, o relatorio
        continuaria com um balde so e o trabalho teria sido decorativo."""
        self.assertNotEqual(
            [l for l in self._fonte(tiktok.publicar).splitlines()
             if "etapa=" in l],
            [l for l in self._fonte(youtube_web.publicar).splitlines()
             if "etapa=" in l])


class AFabricaAceitaEssesCamposTests(unittest.TestCase):
    """Se a assinatura mudar, os testes acima viram letra morta: eles conferem
    o texto do fonte, nao o efeito."""

    def test_fabrica_recebe_etapa_e_ref(self):
        from builds import atividade
        parametros = inspect.signature(atividade.fabrica).parameters
        self.assertIn("etapa", parametros)
        self.assertIn("ref", parametros)

    def test_o_que_a_fabrica_recebe_chega_ao_diario(self):
        from builds import atividade
        gravadas = []
        original = atividade.registrar
        try:
            atividade.registrar = lambda *a, **k: gravadas.append(k)
            with atividade.fabrica("publicacao", "x", canal="builds",
                                   etapa="publicar.tiktok", ref="g1:build"):
                pass
        finally:
            atividade.registrar = original
        self.assertTrue(gravadas)
        for kwargs in gravadas:
            self.assertEqual("publicar.tiktok", kwargs.get("etapa"))
            self.assertEqual("g1:build", kwargs.get("ref"))


if __name__ == "__main__":
    unittest.main()
