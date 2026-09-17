# -*- coding: utf-8 -*-
"""O botao de parar casa pelo COMECO do rotulo, nunca por trecho.

17/09/2026: `aria-label*='Parar' i` casava com o historico lateral do
ChatGPT ("Fixar COMPARAR defeitos do formato A", medido na tela), o cliente
achava que o modelo ainda escrevia, e o parecer ficou 8 minutos com a
resposta pronta ate desistir.

Rode de dentro de historias/:
    python -m unittest tests.test_botao_de_parar_regressions -v
"""
from __future__ import annotations

import re
import unittest

from contos.llm import seletores                                   # noqa: E402


class BotaoDeParar(unittest.TestCase):

    def _prefixos(self, provedor):
        return [m.group(1).lower()
                for s in seletores.do_provedor(provedor)["parar"]
                for m in [re.search(r"aria-label\^='([^']+)' i", s)] if m]

    def test_nunca_por_trecho(self):
        for provedor in seletores.PROVEDORES:
            for seletor in seletores.do_provedor(provedor)["parar"]:
                self.assertNotIn("aria-label*=", seletor, provedor)

    def test_rotulos_medidos_nao_casam_e_os_reais_casam(self):
        for provedor in seletores.PROVEDORES:
            prefixos = self._prefixos(provedor)

            def casa(rotulo):
                return any(rotulo.lower().startswith(p) for p in prefixos)

            for falso in ("Fixar Comparar defeitos do formato A",
                          "Abrir opções de conversa para Comparar defeitos",
                          "Baixar o app para desktop"):
                self.assertFalse(casa(falso), (provedor, falso))
            for real in ("Stop streaming", "Parar resposta",
                         "Interromper geração"):
                self.assertTrue(casa(real), (provedor, real))

    def test_o_chatgpt_mantem_o_seletor_por_testid(self):
        self.assertIn("button[data-testid='stop-button']",
                      seletores.do_provedor("chatgpt")["parar"])


if __name__ == "__main__":
    unittest.main()
