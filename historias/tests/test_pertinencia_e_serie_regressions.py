# -*- coding: utf-8 -*-
"""O texto e mesmo desta historia, e o titulo diz que ha mais (11/09/2026).

DOIS DEFEITOS ACHADOS NO MESMO DIA, os dois com video ja publico.

1. CONTAMINACAO. As partes 3 a 6 da `historia_00005` — um desabafo sobre um
   homem que esconde da esposa quem paga o apartamento — foram para o disco
   com 56 cenas assim:

       "Gameplay de parkour no Minecraft, pulando entre blocos de areia."
       "O jogador entra numa caverna escura e acende uma tocha."

   A parte 3 tinha ate a narracao de outra historia (uma mulher achando uma
   arma enrolada numa toalha). O unico criterio para aceitar uma parte era
   CONTAR CENAS: 14 cenas de Minecraft passavam. Virou video e foi ao ar no
   YouTube e no TikTok as 15:08.

2. SERIE SEM IDENTIDADE. As seis partes saiam com titulos soltos — "O limite
   do desespero", "O Trofeu de Aluguel", "PARTE 3 - A PASSAGEM E A TOALHA" —
   tres formatos diferentes na MESMA serie e nada ligando um ao outro. Quem
   gostou de uma parte nao tinha como achar as outras: a identidade da serie
   so existia na DESCRICAO, que ninguem abre num Short.

    cd e:\\projetos\\historias
    python -m pytest tests/test_coerencia_e_serie_regressions.py -q
"""
from __future__ import annotations

import unittest

from contos.roteiro import pertinencia
from contos.roteiro.roteiro import (limpar_titulo_de_parte, titulo_da_parte,
                                    TITULO_MAXIMO)


def _cenas(imagens, narracao="Ele entrou em casa e viu o papel na mesa."):
    return [{"n": i + 1, "imagem": img, "narracao": narracao}
            for i, img in enumerate(imagens)]


MINECRAFT = [
    "Gameplay de parkour no Minecraft, pulando entre blocos de areia.",
    "O jogador quase cai, mas consegue pular para o proximo bloco.",
    "O jogador entra numa caverna escura e acende uma tocha.",
    "O jogador acha um bau escondido na caverna.",
    "O jogador abre o bau e pega os itens rapidamente.",
]
INGLES = [
    "A 30s man with tired eyes standing in a dim living room at night",
    "Close up of a plane ticket on a wooden table with warm lamp light",
    "A woman in a cozy sweater looking at her phone by the window",
    "The man sitting on the floor of the bedroom holding a folded towel",
    "A modern upscale apartment living room at night with dim lighting",
]


class CoerenciaTests(unittest.TestCase):

    def test_as_56_cenas_de_minecraft_seriam_recusadas(self):
        problemas = pertinencia.problemas(_cenas(MINECRAFT))
        self.assertTrue(problemas)
        self.assertIn("ingles", problemas[0])

    def test_a_parte_legitima_passa(self):
        self.assertEqual([], pertinencia.problemas(_cenas(INGLES)))

    def test_uma_cena_em_portugues_nao_derruba_a_parte(self):
        """Nome proprio brasileiro numa cena e normal. Recusar a parte
        inteira por causa de uma seria pior do que o problema."""
        misto = INGLES + ["O homem atravessa a Marginal Tiete de madrugada"]
        self.assertEqual([], pertinencia.problemas(_cenas(misto)))

    def test_cena_sem_imagem_e_apontada(self):
        cenas = _cenas(INGLES)
        cenas[2]["imagem"] = ""
        self.assertTrue(any("sem prompt de imagem" in p
                            for p in pertinencia.problemas(cenas)))

    def test_cena_sem_narracao_e_apontada(self):
        cenas = _cenas(INGLES)
        cenas[1]["narracao"] = "  "
        self.assertTrue(any("sem narracao" in p
                            for p in pertinencia.problemas(cenas)))

    def test_parte_vazia_nao_passa(self):
        self.assertTrue(pertinencia.problemas([]))

    def test_a_fracao_e_um_numero_e_nao_um_palpite(self):
        """O rotulo precisa ser conferivel: e ele que bloqueia publicacao."""
        self.assertEqual(0.0, pertinencia.fracao_em_ingles(_cenas(MINECRAFT)))
        self.assertEqual(1.0, pertinencia.fracao_em_ingles(_cenas(INGLES)))

    def test_sem_amostra_nao_inventa_veredito(self):
        self.assertIsNone(pertinencia.fracao_em_ingles(
            [{"n": 1, "imagem": "ok", "narracao": "x"}]))


class TituloDaSerieTests(unittest.TestCase):

    @staticmethod
    def _roteiro(**extra):
        base = {
            "serie": True,
            "titulo": "Faz quatro anos que minha esposa acha que fui "
                      "promovido, mas nosso apartamento e pago por duas "
                      "mulheres que disputam minha atencao.",
            "partes": [{"n": n, "titulo": t} for n, t in enumerate(
                ("O limite do desespero (Parte 1)",
                 "O Troféu de Aluguel (Parte 2)",
                 "PARTE 3 - A PASSAGEM E A TOALHA"), 1)],
        }
        base.update(extra)
        return base

    def test_o_prefixo_escrito_pelo_modelo_sai(self):
        self.assertEqual("A passagem e a toalha",
                         limpar_titulo_de_parte("PARTE 3 - A PASSAGEM E A TOALHA"))

    def test_o_sufixo_de_parte_sai(self):
        self.assertEqual("O Troféu de Aluguel",
                         limpar_titulo_de_parte("O Troféu de Aluguel (Parte 2)"))

    def test_caixa_alta_inteira_vira_titulo_normal(self):
        self.assertEqual("A passagem e a toalha",
                         limpar_titulo_de_parte("A PASSAGEM E A TOALHA"))

    def test_titulo_normal_fica_como_esta(self):
        self.assertEqual("O Celta na minha vaga",
                         limpar_titulo_de_parte("O Celta na minha vaga"))

    def test_as_tres_partes_passam_a_dizer_que_sao_serie(self):
        roteiro = self._roteiro()
        for n in (1, 2, 3):
            self.assertIn("/3", titulo_da_parte(roteiro, n),
                          "o titulo nao diz quantas partes existem")

    def test_a_marca_da_serie_entra_quando_existe(self):
        roteiro = self._roteiro(serie_nome="O Apartamento das Duas")
        titulo = titulo_da_parte(roteiro, 2)
        self.assertTrue(titulo.startswith("O Apartamento das Duas"),
                        f"a marca tem que vir primeiro: {titulo!r}")
        self.assertIn("O Troféu de Aluguel", titulo)
        self.assertIn("(Parte 2/3)", titulo)

    def test_sem_marca_ainda_sai_um_titulo_util(self):
        """As historias anteriores a 11/09/2026 nao tem `serie_nome`."""
        self.assertEqual("O limite do desespero (Parte 1/3)",
                         titulo_da_parte(self._roteiro(), 1))

    def test_o_titulo_cabe_no_limite_do_youtube(self):
        roteiro = self._roteiro(serie_nome="O Apartamento das Duas")
        roteiro["partes"][0]["titulo"] = "A " + ("noite " * 40)
        titulo = titulo_da_parte(roteiro, 1)
        self.assertLessEqual(len(titulo), TITULO_MAXIMO)

    def test_o_que_cede_e_a_parte_nunca_a_marca_nem_a_ordem(self):
        roteiro = self._roteiro(serie_nome="O Apartamento das Duas")
        roteiro["partes"][0]["titulo"] = "A " + ("noite " * 40)
        titulo = titulo_da_parte(roteiro, 1)
        self.assertIn("O Apartamento das Duas", titulo)
        self.assertIn("(Parte 1/3)", titulo)

    def test_historia_de_uma_parte_nao_ganha_numero(self):
        solta = {"serie": False, "titulo": "A carta na gaveta",
                 "partes": [{"n": 1, "titulo": "A carta na gaveta"}]}
        self.assertEqual("A carta na gaveta", titulo_da_parte(solta, 1))


if __name__ == "__main__":
    unittest.main()
