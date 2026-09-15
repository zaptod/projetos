"""Card RECUSADO no historico do PicassoIA e recusa, nao "sem prova" (14/09/2026).

Visto na tela as 23:25 (historia_00012 p02_cena_01): o card do nosso prompt
mostrava "CONTEUDO ILEGAL - Este conteudo e ilegal e proibido na nossa
plataforma. Nao pode ser processado." no lugar da imagem. A prova de origem
nao casava o prompt (o primeiro <p> do card era o aviso), esperava os 240 s e
devolvia "sem prova" — erro TECNICO, que reenvia o mesmo texto para sempre.
Com a recusa reconhecida, a cena vai para a escalada que reescreve o prompt.

Rode de dentro de random_builds/:
    python -m unittest tests.test_recusa_no_historico_regressions -v
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from builds.identity import picasso_client as pc
from builds.identity import picasso_selectors, proveniencia
from builds.identity.client import ConteudoRecusado

NOSSO = ("A striking cinematic portrait of **Suelen Unha de Gel**, a light-skinned "
         "Latina in her early 30s, platinum blonde hair, kicking a plastic bucket of "
         "dirty water across a tiled floor, square composition, no text, no logo.")
ALHEIO = ("A very beautiful woman with tanned skin and a seductive gaze, long light "
          "blonde curly hair, loose surf shirt and tied sarong, small shell necklace, "
          "sitting at a cafe table outdoors holding a cup of coffee, smiling.")
AVISO = ("CONTEÚDO ILEGAL\nEste conteúdo é ilegal e proibido na nossa plataforma. "
         "Não pode ser processado.")
BUCKET = "https://pub-7388517e4cb848f899900623842f083b.r2.dev/text-to-image/uid/picassoia-image/"


def _recusado(indice, prompt, data="14 DE SET. DE 2026, 23:25", aviso_primeiro=True):
    paragrafos = ([AVISO, prompt] if aviso_primeiro else [prompt, AVISO])
    return {"indice": indice, "prompt": paragrafos[0], "paragrafos": paragrafos,
            "texto": f"{AVISO}\nIMAGE\nPICASSOIA IMAGE\n{prompt}\nVer mais\n"
                     f"Copiar prompt\n1:1\njpg\n{data}",
            "imagens": [], "recusado": True}


def _pronto(indice, prompt, url, data="14 DE SET. DE 2026, 23:25"):
    return {"indice": indice, "prompt": prompt, "paragrafos": [prompt],
            "texto": f"{prompt}\nVer mais\nCopiar prompt\n1:1\njpg\n{data}",
            "imagens": [url], "recusado": False}


class CasamentoPorParagrafoTests(unittest.TestCase):

    def test_prompt_no_segundo_paragrafo_casa(self):
        """Era o defeito: so o primeiro <p> (o aviso) era comparado."""
        escolha = proveniencia.escolher_card([_recusado(0, NOSSO)], NOSSO)
        self.assertIsNotNone(escolha["card"])

    def test_card_de_outro_prompt_continua_sem_casar(self):
        escolha = proveniencia.escolher_card([_recusado(0, ALHEIO)], NOSSO)
        self.assertIsNone(escolha["card"])

    def test_card_sem_paragrafos_segue_funcionando(self):
        card = {"indice": 0, "prompt": NOSSO, "texto": NOSSO, "imagens": []}
        self.assertTrue(proveniencia.card_traz_prompt(card, NOSSO))


class RecusaNoHistoricoTests(unittest.TestCase):

    def test_card_do_nosso_prompt_recusado_e_recusa(self):
        cards = [_recusado(0, NOSSO)]
        escolha = proveniencia.escolher_card(cards, NOSSO)
        motivo = proveniencia.recusa_no_historico(cards, escolha, NOSSO)
        self.assertIn("ILEGAL", motivo.upper())

    def test_recusa_de_outra_pessoa_nao_e_nossa(self):
        """Conta compartilhada: o card recusado de outro prompt nao conta."""
        cards = [_recusado(0, ALHEIO), _pronto(1, "outra coisa " * 20, BUCKET + "x.jpg")]
        escolha = proveniencia.escolher_card(cards, NOSSO)
        self.assertEqual("", proveniencia.recusa_no_historico(cards, escolha, NOSSO))

    def test_card_nosso_com_imagem_nao_e_recusa(self):
        cards = [_pronto(0, NOSSO, BUCKET + "nossa.jpg")]
        escolha = proveniencia.escolher_card(cards, NOSSO)
        self.assertEqual("", proveniencia.recusa_no_historico(cards, escolha, NOSSO))

    def test_sem_escolha_o_prefixo_no_texto_liga_o_card(self):
        """Quando o texto do card nao separa o paragrafo do prompt."""
        card = {"indice": 0, "prompt": "", "paragrafos": [],
                "texto": f"{AVISO}\n{NOSSO}", "imagens": [], "recusado": True}
        motivo = proveniencia.recusa_no_historico([card], {"card": None}, NOSSO)
        self.assertTrue(motivo)

    def test_recusa_anterior_ao_envio_nao_conta(self):
        """O mesmo prompt recusado ONTEM nao e a resposta deste envio."""
        cards = [_recusado(0, NOSSO, data="13 DE SET. DE 2026, 10:00")]
        envio = datetime(2026, 9, 14, 23, 25).astimezone()
        escolha = proveniencia.escolher_card(cards, NOSSO, envio, 3)
        self.assertIsNone(escolha["card"])
        self.assertEqual("", proveniencia.recusa_no_historico(
            cards, escolha, NOSSO, envio, 3))


class SeletorDoCardTests(unittest.TestCase):

    def test_cards_do_historico_devolve_paragrafos_e_recusa(self):
        class Pagina:
            def evaluate(self, js, arg=None):
                return [{"indice": 0, "prompt": AVISO, "paragrafos": [AVISO, NOSSO],
                         "texto": AVISO, "imagens": [], "recusado": True}]
        card = picasso_selectors.cards_do_historico(Pagina())[0]
        self.assertTrue(card["recusado"])
        self.assertEqual([AVISO, NOSSO], card["paragrafos"])

    def test_o_js_procura_o_aviso_e_o_escudo_no_card(self):
        js = picasso_selectors.JS_CARDS_HISTORICO
        self.assertIn("paragrafos", js)
        self.assertIn("recusado", js)
        self.assertIn("ilegal", js)
        self.assertIn("shield", js)


class FormaDaImagemPedidaTests(unittest.TestCase):
    """A espera aceita a forma PEDIDA, e nao so retrato (14/09/2026 23:33)."""

    def test_pedido_quadrado_aceita_quadrada_e_recusa_retrato(self):
        self.assertTrue(pc.forma_confere("1:1", 1024, 1024))
        self.assertFalse(pc.forma_confere("1:1", 1088, 1920))
        self.assertFalse(pc.forma_confere("1:1", 1920, 1088))

    def test_pedido_vertical_segue_a_regra_de_sempre(self):
        self.assertTrue(pc.forma_confere("9:16", 1088, 1920))
        self.assertFalse(pc.forma_confere("9:16", 1024, 1024))
        self.assertFalse(pc.forma_confere("9:16", 1920, 1088))

    def test_imagem_sem_medida_nao_confere(self):
        self.assertFalse(pc.forma_confere("1:1", 0, 0))

    def test_a_espera_usa_a_forma_do_ultimo_envio(self):
        import inspect
        self.assertIn("forma_confere(", inspect.getsource(pc.PicassoClient.wait_for_render))
        self.assertIn("self.aspecto_pedido = str(aspect",
                      inspect.getsource(pc.PicassoClient.submit_prompt))


class VigiaDoHistoricoTests(unittest.TestCase):
    """O loop da prova levanta `ConteudoRecusado` em vez de esperar 240 s."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        antes = proveniencia.ARQUIVO_ORIGENS
        proveniencia.ARQUIVO_ORIGENS = Path(self._tmp.name) / "origens.jsonl"
        self.addCleanup(setattr, proveniencia, "ARQUIVO_ORIGENS", antes)

    def _cliente(self, cards):
        class Aberta:
            def is_closed(self):
                return False
        cliente = object.__new__(pc.PicassoClient)
        cliente.page = Aberta()
        cliente.ajustes = {}
        original = pc.selectors.cards_do_historico
        pc.selectors.cards_do_historico = lambda *a, **k: cards
        self.addCleanup(setattr, pc.selectors, "cards_do_historico", original)
        return cliente, Aberta()

    def test_card_recusado_levanta_na_hora(self):
        cliente, aba = self._cliente([_recusado(0, NOSSO)])
        ajustes = proveniencia.ajustes({})
        with self.assertRaises(ConteudoRecusado):
            cliente._vigiar_historico(aba, ajustes, 12, 3.0, 0.01, None, NOSSO, None)

    def test_card_pronto_continua_dando_prova(self):
        cliente, aba = self._cliente([_pronto(0, NOSSO, BUCKET + "nossa.jpg")])
        prova = cliente._vigiar_historico(aba, proveniencia.ajustes({}), 12, 3.0,
                                          0.01, None, NOSSO, None)
        self.assertTrue(prova["comprovada"])


if __name__ == "__main__":
    unittest.main()
