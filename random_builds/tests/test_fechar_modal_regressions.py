# -*- coding: utf-8 -*-
"""O fechador de dialogos do PicassoIA clica no X do DIALOGO.

17/09/2026: pop-up de paywall com o X `<svg class="lucide lucide-x size-5"
aria-hidden="true">`. Conferido num Chromium headless (sem perfil, sem rede):
com a lista antiga, um X em `[role=button]`, ou num `data-slot` sem role,
caia no generico `button:has(svg.lucide-x)` — e o primeiro que ele acha na
pagina e o X de LIMPAR O PROMPT. O pop-up ficava, e o prompt sumia.
"""
from __future__ import annotations

import unittest

from builds.identity import picasso_client as PC


class FecharModal(unittest.TestCase):

    def test_especificos_do_dialogo_antes_do_generico(self):
        generico = PC.FECHAR_MODAL.index("button:has(svg.lucide-x)")
        self.assertEqual(len(PC.FECHAR_MODAL) - 1, generico)
        for seletor in ("div[role='dialog'] button:has(svg.lucide-x)",
                        "[role='dialog'] [role='button']:has(svg.lucide-x)",
                        "[data-slot='dialog-content'] button:has(svg.lucide-x)",
                        "[data-slot='dialog-content'] "
                        "[role='button']:has(svg.lucide-x)"):
            self.assertLess(PC.FECHAR_MODAL.index(seletor), generico)

    def test_o_clique_vai_no_botao_e_nao_no_svg(self):
        # O svg e aria-hidden: clicar nele nao e clicar no botao.
        for seletor in PC.FECHAR_MODAL:
            if "lucide-x" in seletor:
                self.assertIn(":has(svg.lucide-x)", seletor)


if __name__ == "__main__":
    unittest.main()
