# -*- coding: utf-8 -*-
"""Regressões do gerador de demos de skill (Onda 11D).

Modo ``sem_video``: a cena é montada, o cast roteirizado acontece e a
consequência do contrato é observada — sem ffmpeg, sem mp4. A demo que sai
"muda" é um bug de skill, exatamente o que queremos ver quebrar.
"""

from __future__ import annotations

import unittest

from neural_fights.recording import skill_demo


class SkillDemoGeneratorTests(unittest.TestCase):
    def test_slug_e_estavel_e_ascii(self):
        self.assertEqual(
            skill_demo.slug_da_skill("Julgamento Celestial"),
            "julgamento-celestial",
        )
        self.assertEqual(
            skill_demo.slug_da_skill("Fúria do Trovão"), "furia-do-trovao"
        )

    def test_hash_do_contrato_muda_com_o_contrato(self):
        h1 = skill_demo.hash_do_contrato("Bola de Fogo")
        h2 = skill_demo.hash_do_contrato("Inferno")
        self.assertNotEqual(h1, h2)
        self.assertEqual(h1, skill_demo.hash_do_contrato("Bola de Fogo"))

    def test_cena_encenada_produz_consequencia_sem_video(self):
        for nome in ("Bola de Fogo", "Muralha de Gelo", "Fotossíntese"):
            with self.subTest(skill=nome):
                resultado = skill_demo.gravar_demo(nome, sem_video=True)
                self.assertTrue(resultado["ok"], resultado)
                self.assertTrue(resultado["consequencia_observada"], resultado)
                self.assertIsNone(resultado["arquivo"])  # sem_video não grava

    def test_passiva_de_morte_nao_vira_demo(self):
        resultado = skill_demo.gravar_demo("Ressurreição", sem_video=True)
        self.assertFalse(resultado["ok"])
        self.assertIn("passiva", str(resultado["erro"]))


if __name__ == "__main__":
    unittest.main()
