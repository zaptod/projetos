# -*- coding: utf-8 -*-
"""Regressões dos kits de classe (Onda 10D).

Cada classe tem 4 skills de afinidade na ordem KIT_PAPEIS: CONTROLE, ZONA/
TERRENO, MOBILIDADE, PICO. A união dos kits alcança os tipos e status que
os kits antigos deixavam fora do jogo (TRAP, CHANNEL, TRANSFORM, portal,
cadeia, Fênix/Treant e 12 status implementados sem fonte).
"""

from __future__ import annotations

import unittest

from neural_fights.core.skills import SKILL_DB
from neural_fights.models.constants import CLASSES_DATA, KIT_PAPEIS

CC = {"PARALISIA", "LENTO", "CONGELADO", "ENRAIZADO", "MEDO", "CHARME", "SILENCIADO",
      "EXAUSTO", "TEMPO_PARADO", "POSSESSO", "PUXADO", "VORTEX", "CEGO", "KNOCK_UP",
      "EMPURRAO", "SONO"}
STATUS_ORFAOS = {"CEGO", "CHARME", "EXAUSTO", "EXPOSTO", "MEDO", "NECROSE", "POSSESSO",
                 "PUXADO", "SILENCIADO", "TEMPO_PARADO", "VORTEX", "VULNERAVEL"}


class KitsDeClasseTests(unittest.TestCase):
    def _kits(self):
        return {c: d["skills_afinidade"] for c, d in CLASSES_DATA.items()}

    def test_16_classes_com_4_skills_existentes(self):
        kits = self._kits()
        self.assertEqual(len(kits), 16)
        self.assertEqual(KIT_PAPEIS, ("CONTROLE", "ZONA", "MOBILIDADE", "PICO"))
        for classe, kit in kits.items():
            self.assertEqual(len(kit), 4, classe)
            for nome in kit:
                self.assertIn(nome, SKILL_DB, (classe, nome))

    def test_papel_por_posicao(self):
        for classe, kit in self._kits().items():
            controle = SKILL_DB[kit[0]]
            self.assertTrue(
                controle.get("efeito") in CC or controle.get("taunt") or controle.get("chain"),
                (classe, kit[0]),
            )
            zona = SKILL_DB[kit[1]]
            self.assertIn(zona.get("tipo"), ("AREA", "TRAP", "SUMMON"), (classe, kit[1]))
            mob = SKILL_DB[kit[2]]
            self.assertTrue(
                mob.get("tipo") == "DASH"
                or mob.get("buff_velocidade") or mob.get("bonus_velocidade") or mob.get("voo"),
                (classe, kit[2]),
            )

    def test_uniao_alcanca_tipos_e_status_orfaos(self):
        skills = {n for kit in self._kits().values() for n in kit}
        tipos = {SKILL_DB[n].get("tipo") for n in skills}
        for tipo in ("TRAP", "CHANNEL", "TRANSFORM", "SUMMON", "BEAM", "DASH"):
            self.assertIn(tipo, tipos, tipo)
        self.assertTrue(any(SKILL_DB[n].get("cria_portal") for n in skills))
        self.assertTrue(any(SKILL_DB[n].get("chain") for n in skills))
        self.assertTrue(any(SKILL_DB[n].get("canalizavel") for n in skills))
        tipos_summon = {SKILL_DB[n].get("summon_tipo") for n in skills}
        self.assertTrue({"FENIX", "TREANT"} <= tipos_summon, tipos_summon)
        efeitos = {SKILL_DB[n].get("efeito") for n in skills}
        faltam = STATUS_ORFAOS - efeitos
        self.assertEqual(faltam, set(), faltam)

    def test_repulsao_empurra_de_verdade(self):
        self.assertGreaterEqual(SKILL_DB["Repulsão"].get("forca_empurrao", 0), 14.0)


if __name__ == "__main__":
    unittest.main()
