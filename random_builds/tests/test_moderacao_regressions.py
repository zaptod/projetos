# -*- coding: utf-8 -*-
"""Contratos da contramedida de moderacao (prompt recusado pelo gerador).

O caso real (31/08/2026): a geracao de imagens de uma historia PAROU porque
o PicassoIA julgou uma imagem inapropriada. Custava tres coisas — a recusa
nao era detectada (esperava os 300 s do timeout), a cena nunca gerava
(reenviava o mesmo texto) e a historia inteira ficava parada.

O que este arquivo trava:

1. DETECCAO. Frase de recusa na tela e reconhecida; texto comum NAO e
   (falso positivo faria o worker desistir de imagem que so demorava).
2. ESCALONAMENTO. Cada nivel e mais suave que o anterior, o nivel 3 tira as
   pessoas da cena, e o prompt NUNCA vira outra coisa (o estilo sobrevive).
3. PREVENCAO. Prompt com termo notorio ja sai suavizado na 1a tentativa, sem
   gastar uma recusa.

Rode de dentro de random_builds/:
    python -m unittest tests.test_moderacao_regressions -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

from builds.identity import moderacao                             # noqa: E402

ESTILO = ("cinematic photography, shot on 35mm film, shallow depth of field, "
          "moody volumetric lighting, film grain, photorealistic")


class DeteccaoTests(unittest.TestCase):
    def test_reconhece_a_recusa_em_portugues_e_ingles(self):
        for texto in ("Ops! Este conteúdo inapropriado não pode ser gerado",
                      "Your prompt was blocked by our safety system",
                      "This request violates our content policy",
                      "Imagem inapropriada detectada"):
            self.assertIsNotNone(moderacao.parece_recusa(texto), texto)

    def test_devolve_o_trecho_como_motivo(self):
        motivo = moderacao.parece_recusa(
            "Erro: o prompt was blocked por conter violencia explicita.")
        self.assertIn("blocked", motivo.lower())

    def test_pagina_normal_nao_e_recusa(self):
        """Falso positivo faria desistir de imagem que so estava demorando."""
        for texto in ("Gerando sua imagem... 45s",
                      "Minhas criações  Histórico  Créditos: 12",
                      "a woman walking down a dark street, cinematic",
                      "", "Download  Compartilhar  Editar"):
            self.assertIsNone(moderacao.parece_recusa(texto), repr(texto))


class PaginaFalsa:
    """So o que `_recusou` usa: `evaluate` e `is_closed`."""

    def __init__(self, bloqueio=None, texto=""):
        self._bloqueio, self._texto = bloqueio, texto

    def evaluate(self, js):
        from builds.identity import picasso_selectors as sel
        if js is sel.JS_BLOQUEIO:
            return self._bloqueio
        return self._texto

    @staticmethod
    def is_closed():
        return False


def _cliente(pagina):
    from builds.identity.picasso_client import PicassoClient
    cli = PicassoClient.__new__(PicassoClient)
    cli.page = pagina
    return cli


class DeteccaoNaPaginaTests(unittest.TestCase):
    """O site avisa por ICONE (escudo lucide), nao por frase.

    Foi assim que um bloqueio passou batido em 31/08/2026 mesmo com a
    deteccao por texto ja instalada: a tela so mostrava o escudo vermelho.
    """

    def test_o_escudo_sozinho_ja_e_recusa(self):
        pagina = PaginaFalsa(bloqueio={"escudo": True, "texto": ""})
        self.assertIsNotNone(_cliente(pagina)._recusou())

    def test_o_escudo_usa_o_texto_perto_como_motivo(self):
        pagina = PaginaFalsa(bloqueio={"escudo": True,
                                       "texto": "Conteudo bloqueado\nTente outro prompt"})
        motivo = _cliente(pagina)._recusou()
        self.assertIn("bloqueado", motivo)
        self.assertNotIn("\n", motivo, "o motivo vai para uma linha de log")

    def test_erro_vermelho_sem_escudo_nao_e_recusa_de_conteudo(self):
        """`text-destructive` tambem pinta 'sem credito' — reescrever nao ajuda."""
        pagina = PaginaFalsa(bloqueio={"escudo": False,
                                       "texto": "Creditos insuficientes"})
        self.assertIsNone(_cliente(pagina)._recusou())

    def test_erro_vermelho_com_frase_de_recusa_vale(self):
        pagina = PaginaFalsa(bloqueio={"escudo": False,
                                       "texto": "This request violates our content policy"})
        self.assertIsNotNone(_cliente(pagina)._recusou())

    def test_tela_limpa_nao_e_recusa(self):
        self.assertIsNone(_cliente(PaginaFalsa(None, "Gerando... 20s"))._recusou())

    def test_frase_na_pagina_sem_icone_ainda_vale(self):
        pagina = PaginaFalsa(None, "Ops: conteudo inapropriado")
        self.assertIsNotNone(_cliente(pagina)._recusou())


class SuavizacaoTests(unittest.TestCase):
    def test_nivel_zero_nao_toca_no_prompt(self):
        p = "a man crying in the rain, " + ESTILO
        self.assertEqual((p, []), moderacao.suavizar(p, 0))

    def test_nivel_1_troca_o_notorio_e_preserva_a_cena(self):
        novo, mudancas = moderacao.suavizar(
            "a woman with blood on her hands in a kitchen, " + ESTILO, 1)
        self.assertNotIn("blood", novo.lower())
        self.assertIn("kitchen", novo, "a cena tem que continuar sendo a cena")
        self.assertIn("35mm", novo, "o estilo nao pode se perder")
        self.assertIn("sangue", mudancas)

    def test_nivel_1_nao_mexe_no_que_e_so_sensivel_por_contexto(self):
        """Trocar 'child' no nivel 1 estragaria cena legitima a toa."""
        novo, _ = moderacao.suavizar("a child reading a book, " + ESTILO, 1)
        self.assertIn("child", novo)

    def test_nivel_2_troca_menores_e_armas(self):
        novo, mudancas = moderacao.suavizar(
            "a child holding a knife in a dark room, " + ESTILO, 2)
        baixo = novo.lower()
        self.assertNotIn("child", baixo)
        self.assertNotIn("knife", baixo)
        self.assertIn("menor", mudancas)
        self.assertIn(moderacao.CAUDA_SEGURA, novo)

    def test_nivel_3_tira_as_pessoas_e_mantem_o_lugar(self):
        novo, mudancas = moderacao.suavizar(
            "a bleeding man lying on the floor, empty warehouse at night, "
            + ESTILO, 3)
        self.assertIn(moderacao.CAUDA_AMBIENTE, novo)
        self.assertIn("warehouse", novo, "o lugar e o que sobra")
        self.assertIn("35mm", novo)
        self.assertIn("so o ambiente", mudancas)

    def test_cada_nivel_e_no_maximo_tao_arriscado_quanto_o_anterior(self):
        base = ("a teenager with a gun and blood, naked figure, suicide note, "
                + ESTILO)
        riscos = [len(moderacao.arriscado(moderacao.suavizar(base, n)[0]))
                  for n in range(4)]
        self.assertEqual(riscos, sorted(riscos, reverse=True), riscos)
        self.assertEqual(0, riscos[-1], "o ultimo nivel tem que zerar o risco")

    def test_prompt_limpo_sai_intocado_em_qualquer_nivel(self):
        p = "an empty bus stop at dawn, " + ESTILO
        self.assertEqual(p, moderacao.suavizar(p, 1)[0])

    def test_arriscado_lista_os_rotulos(self):
        achados = moderacao.arriscado("blood and a knife", nivel=2)
        self.assertIn("sangue", achados)
        self.assertIn("faca", achados)
        self.assertEqual([], moderacao.arriscado("a quiet library"))


class EscalonarTests(unittest.TestCase):
    def test_prompt_limpo_comeca_no_original(self):
        passos = list(moderacao.escalonar("a quiet library, " + ESTILO))
        self.assertEqual(0, passos[0][0], "sem risco, tenta o original antes")
        self.assertEqual([0, 1, 2, 3], [n for n, _p, _m in passos])

    def test_prompt_notorio_ja_comeca_suavizado(self):
        """Prevencao: nao gasta uma recusa para descobrir o obvio."""
        passos = list(moderacao.escalonar("a bloody corpse, " + ESTILO))
        self.assertEqual(1, passos[0][0])
        self.assertNotIn("blood", passos[0][1].lower())

    def test_preventivo_desligado_sempre_tenta_o_original(self):
        passos = list(moderacao.escalonar("a bloody corpse", preventivo=False))
        self.assertEqual(0, passos[0][0])

    def test_max_nivel_limita_as_tentativas(self):
        passos = list(moderacao.escalonar("a quiet library", max_nivel=1))
        self.assertEqual([0, 1], [n for n, _p, _m in passos])

    def test_toda_tentativa_devolve_texto_util(self):
        for _n, prompt, _m in moderacao.escalonar(
                "a naked child holding a knife covered in blood"):
            self.assertTrue(prompt.strip())
            self.assertNotIn(",,", prompt)


if __name__ == "__main__":
    unittest.main()
