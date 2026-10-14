# -*- coding: utf-8 -*-
"""SCR-PT: `tiktok.postar_automatico` dos builds era ignorado pela grade.

Medido em 14/10/2026: `random_builds/config/publicacao.json` dizia
`"postar_automatico": false`, mas a grade passa `postar=True` explicito
(`postar._tiktok_dos_builds`) e posta em todo horario ha semanas. A chave so
valia para o botao do painel, e mudar ela nao mudava o que o Adrian achava
que mudava. Decisao `publicacao/tiktok-postar-automatico` (14/10): "a grade
posta; a chave sai" — do config e do codigo que a lia.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


class ChaveSaiuTests(unittest.TestCase):
    def test_config_dos_builds_sem_a_chave(self):
        config = json.loads((RAIZ / "random_builds" / "config" /
                             "publicacao.json").read_text(encoding="utf-8"))
        self.assertNotIn("postar_automatico", config.get("tiktok") or {})

    def test_nenhum_codigo_le_a_chave_do_tiktok(self):
        fonte = (RAIZ / "random_builds" / "builds" / "publicar" /
                 "tiktok.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"get\(\s*[\"']postar_automatico", fonte))

    def test_a_grade_continua_mandando_postar(self):
        fonte = (RAIZ / "ferramentas" / "postar.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _tiktok_dos_builds("):]
        corpo = corpo[:corpo.index("\ndef ", 10)]
        self.assertIn("postar=True", corpo)


if __name__ == "__main__":
    unittest.main()
