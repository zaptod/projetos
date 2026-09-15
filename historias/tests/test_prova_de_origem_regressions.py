# -*- coding: utf-8 -*-
"""Imagem sem prova de origem nunca vai ao disco (14/09/2026).

As 20:26 o PicassoIA nao achou o card com o nosso prompt para a
historia_00011 p06_cena_07. O worker logou "Nada baixado." e, na linha
seguinte, baixou a imagem mesmo assim e gravou `prova` com comprovada: false.
A imagem era de outra pessoa da conta compartilhada (uma mulher se maquiando
no lugar de um rapaz preso num conteiner). O reparo aceitou o arquivo, a parte
foi renderizada com ela e a vistoria passou, porque contava a PRESENCA do dict
`prova`, nao o `comprovada`. So o Gemini barrou.

Rode de dentro de historias/:
    python -m unittest tests.test_prova_de_origem_regressions -v
"""
from __future__ import annotations

import inspect
import re
import unittest

from contos.imagens import worker
from contos.publicar import qualidade


class SemProvaNaoBaixaTests(unittest.TestCase):

    def _ramo_sem_prova(self) -> str:
        fonte = inspect.getsource(worker.gerar)
        inicio = fonte.index('not prova.get("comprovada")')
        fim = fonte.index("break", inicio)
        return fonte[inicio:fim]

    def test_o_ramo_sem_prova_nao_baixa(self):
        ramo = self._ramo_sem_prova()
        self.assertNotIn(".download(", ramo)

    def test_o_ramo_sem_prova_nao_registra_a_cena(self):
        """Registrar com arquivo faria a cena parecer pronta para o resto."""
        self.assertNotIn("fila.registrar(", self._ramo_sem_prova())

    def test_o_download_so_acontece_depois_da_prova(self):
        fonte = inspect.getsource(worker.gerar)
        prova = fonte.index("proveniencia.comprovar(")
        for achado in re.finditer(r"cliente\.download\(", fonte):
            self.assertGreater(achado.start(), fonte.index(
                'not prova.get("comprovada")'), "download antes da prova")
            self.assertGreater(achado.start(), prova)


class RefeitaPorColagemExigeProvaTests(unittest.TestCase):
    """Revisao de 15/09/2026: o laco que refaz colagem baixava
    `prova.get("url") or alvo` sem olhar `comprovada`."""

    def _laco(self) -> str:
        fonte = inspect.getsource(worker.gerar)
        inicio = fonte.index("for volta in range(1, TENTATIVAS_DE_COMPOSICAO)")
        return fonte[inicio:fonte.index("if not Path(destino).is_file()", inicio)]

    def test_a_refeita_confere_a_prova_antes_de_baixar(self):
        laco = self._laco()
        self.assertLess(laco.index('nova.get("comprovada")'),
                        laco.index("cliente.download("))

    def test_a_refeita_nunca_baixa_o_candidato_sem_prova(self):
        self.assertNotIn("or alvo", self._laco())


class VistoriaLeComprovadaTests(unittest.TestCase):

    def test_prova_falha_conta_como_sem_prova(self):
        fonte = inspect.getsource(qualidade.vistoriar_parte)
        self.assertIn('.get("comprovada")', fonte)
        self.assertNotIn('if not l.get("prova")]', fonte)


if __name__ == "__main__":
    unittest.main()
