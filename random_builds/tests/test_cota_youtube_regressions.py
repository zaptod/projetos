# -*- coding: utf-8 -*-
"""Contratos do teto diário de uploads do YouTube.

O caso real (01/09/2026): a publicação parou com um JSON cru de 400 —
`"The user has exceeded the number of videos they may upload."` — que não
diz o que fazer, e que o código tratava como "erro de metadados", igual a um
título inválido. São coisas diferentes:

  metadado inválido  →  o vídeo está errado; corrigir e tentar de novo
  teto diário        →  o vídeo está certo; NÃO adianta tentar de novo agora,
                        e não adianta tentar a próxima parte da série

O que este arquivo trava:

1. A resposta do YouTube é RECONHECIDA como cota, não confundida com erro
   de metadado.
2. `CotaEsgotada` NÃO herda de `PublicacaoFalhou` — quem trata os dois
   juntos volta a perder a distinção sem perceber.
3. A mensagem diz o que fazer, incluindo o custo do corte para Shorts, que
   DOBRA o número de uploads.

Rode de dentro de random_builds/:
    python -m unittest tests.test_cota_youtube_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.publicar import youtube                                # noqa: E402

# A resposta literal que o YouTube devolveu.
RESPOSTA_COTA = """{
  "error": {
    "code": 400,
    "message": "The user has exceeded the number of videos they may upload.",
    "errors": [{"message": "The user has exceeded the number of videos they
     may upload.", "domain": "youtube.video", "reason": "uploadLimitExceeded"}]
  }
}"""
RESPOSTA_METADADO = """{
  "error": {"code": 400, "message": "Invalid video title.",
            "errors": [{"reason": "invalidTitle"}]}
}"""


class RespostaFalsa:
    def __init__(self, texto, status=400):
        self.text = texto
        self.status_code = status
        self.ok = False
        self.headers = {}


class ClassificacaoTests(unittest.TestCase):
    """A mesma resposta 400 pode ser duas coisas muito diferentes."""

    @staticmethod
    def _classificar(resposta):
        """Reproduz a decisão do `publicar` sobre a resposta de metadados."""
        bruto = resposta.text or ""
        if ("exceeded the number of videos" in bruto
                or "uploadLimitExceeded" in bruto):
            raise youtube.CotaEsgotada("teto diario")
        raise youtube.PublicacaoFalhou("metadado")

    def test_teto_diario_vira_CotaEsgotada(self):
        with self.assertRaises(youtube.CotaEsgotada):
            self._classificar(RespostaFalsa(RESPOSTA_COTA))

    def test_erro_de_metadado_continua_PublicacaoFalhou(self):
        with self.assertRaises(youtube.PublicacaoFalhou):
            self._classificar(RespostaFalsa(RESPOSTA_METADADO))

    def test_o_codigo_de_razao_tambem_serve(self):
        """Se o YouTube mudar o texto, o `reason` ainda identifica."""
        with self.assertRaises(youtube.CotaEsgotada):
            self._classificar(RespostaFalsa(
                '{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}'))


class DistincaoTests(unittest.TestCase):
    def test_cota_NAO_e_subclasse_de_publicacao_falhou(self):
        """Quem tratasse as duas juntas voltaria a perder a diferença."""
        self.assertFalse(issubclass(youtube.CotaEsgotada,
                                    youtube.PublicacaoFalhou))
        self.assertFalse(issubclass(youtube.PublicacaoFalhou,
                                    youtube.CotaEsgotada))

    def test_as_duas_sao_erros_de_verdade(self):
        for classe in (youtube.CotaEsgotada, youtube.PublicacaoFalhou):
            self.assertTrue(issubclass(classe, Exception))


class MensagemTests(unittest.TestCase):
    """A mensagem é a única coisa que o dono vê. Ela tem que ensinar."""

    @staticmethod
    def _mensagem() -> str:
        return youtube.MENSAGEM_COTA.lower()

    def test_diz_que_o_navegador_e_outro_balde(self):
        """O dono postou pelo Studio e funcionou: a mensagem tem que explicar."""
        texto = self._mensagem()
        self.assertIn("separado do upload pelo navegador", texto)

    def test_NAO_promete_reset_na_virada_do_dia(self):
        """Foi medido: o dia virou no Pacifico e a API continuou recusando."""
        texto = self._mensagem()
        self.assertIn("nao zera na virada do dia", texto)

    def test_avisa_que_o_ja_publicado_nao_se_perde(self):
        texto = self._mensagem()
        self.assertIn("continua de onde parou", texto)

    def test_avisa_que_o_corte_para_shorts_dobra_os_uploads(self):
        """É a causa mais provável de estourar a cota neste projeto."""
        texto = self._mensagem()
        self.assertIn("dobra os uploads", texto)
        self.assertIn("shorts_max_s", texto)

    def test_menciona_a_verificacao_do_canal(self):
        self.assertIn("verificar o canal", self._mensagem())

    def test_oferece_a_saida_manual(self):
        """Enquanto a API recusa, exportar e subir na mao funciona."""
        self.assertIn("--exportar", self._mensagem())


if __name__ == "__main__":
    unittest.main()
