# -*- coding: utf-8 -*-
"""Regressões dos pools de kit (Onda 11C).

Toda skill do catálogo tem um slot em algum ``KIT_POOLS`` OU está declarada
em ``SKILLS_FORA_DE_ROTACAO`` — o censo "53/109 inalcançáveis" morre por
construção. Cada opção respeita a regra do papel (a mesma do teste de kits
da Onda 10D) e a primeira opção é o kit fixo (default de compatibilidade).
"""

from __future__ import annotations

import random
import unittest

from neural_fights.core.skills import SKILL_DB
from neural_fights.models.constants import (
    CLASSES_DATA,
    KIT_PAPEIS,
    KIT_POOLS,
    SKILLS_FORA_DE_ROTACAO,
    sortear_kit,
)

CC = {"PARALISIA", "LENTO", "CONGELADO", "ENRAIZADO", "MEDO", "CHARME", "SILENCIADO",
      "EXAUSTO", "TEMPO_PARADO", "POSSESSO", "PUXADO", "VORTEX", "CEGO", "KNOCK_UP",
      "EMPURRAO", "SONO"}


class KitPoolsTests(unittest.TestCase):
    def test_pools_para_as_16_classes_com_default_compativel(self):
        self.assertEqual(set(KIT_POOLS), set(CLASSES_DATA))
        for classe, pools in KIT_POOLS.items():
            self.assertEqual(tuple(pools), KIT_PAPEIS, classe)
            kit_fixo = CLASSES_DATA[classe]["skills_afinidade"]
            for idx, papel in enumerate(KIT_PAPEIS):
                opcoes = pools[papel]
                self.assertTrue(opcoes, (classe, papel))
                # A primeira opção É o kit fixo da Onda 10 — registros
                # antigos sem kit_skills continuam lutando igual.
                self.assertEqual(opcoes[0], kit_fixo[idx], (classe, papel))
                self.assertEqual(len(set(opcoes)), len(opcoes), (classe, papel))
                for nome in opcoes:
                    self.assertIn(nome, SKILL_DB, (classe, papel, nome))

    def test_toda_opcao_respeita_a_regra_do_papel(self):
        for classe, pools in KIT_POOLS.items():
            for nome in pools["CONTROLE"]:
                dados = SKILL_DB[nome]
                self.assertTrue(
                    dados.get("efeito") in CC
                    or dados.get("taunt")
                    or dados.get("chain"),
                    (classe, "CONTROLE", nome),
                )
            for nome in pools["ZONA"]:
                self.assertIn(
                    SKILL_DB[nome].get("tipo"),
                    ("AREA", "TRAP", "SUMMON"),
                    (classe, "ZONA", nome),
                )
            for nome in pools["MOBILIDADE"]:
                dados = SKILL_DB[nome]
                self.assertTrue(
                    dados.get("tipo") == "DASH"
                    or dados.get("buff_velocidade")
                    or dados.get("bonus_velocidade")
                    or dados.get("voo"),
                    (classe, "MOBILIDADE", nome),
                )

    def test_sorteio_e_deterministico_e_cai_no_pool(self):
        kit1 = sortear_kit("Criomante (Gelo)", random.Random(5))
        kit2 = sortear_kit("Criomante (Gelo)", random.Random(5))
        self.assertEqual(kit1, kit2)
        self.assertEqual(len(kit1), len(KIT_PAPEIS))
        for papel, nome in zip(KIT_PAPEIS, kit1):
            self.assertIn(nome, KIT_POOLS["Criomante (Gelo)"][papel])
        # Classe desconhecida cai no kit fixo (vazio quando nem isso há).
        self.assertEqual(sortear_kit("Classe Fantasma"), [])

    def test_todo_o_catalogo_tem_slot_ou_esta_declarado_fora(self):
        em_pool = {
            nome
            for pools in KIT_POOLS.values()
            for opcoes in pools.values()
            for nome in opcoes
        }
        fora = set(SKILL_DB) - {"Nenhuma"} - em_pool
        self.assertEqual(fora, set(SKILLS_FORA_DE_ROTACAO), fora)
        # A lista declarada não pode conter skill que na verdade tem slot.
        self.assertFalse(set(SKILLS_FORA_DE_ROTACAO) & em_pool)


if __name__ == "__main__":
    unittest.main()
