"""Testes da migracao deterministica de referencias legadas."""

from __future__ import annotations

import unittest

from neural_fights.tools.migrar_database import migrar_documentos


class DatabaseMigrationTests(unittest.TestCase):
    def test_migrates_skill_personality_and_weapon_without_losing_fields(self) -> None:
        armas = [
            {
                "nome": "Espada Longa Comum",
                "tipo": "Reta",
                "raridade": "Comum",
                "dano": 10,
                "peso": 3,
                "comp_cabo": 20,
                "comp_lamina": 50,
                "largura": 5,
                "habilidades": [{"nome": "Golpe Devastador", "custo": 999}],
            }
        ]
        personagens = [
            {
                "nome": "Legado",
                "tamanho": 1.8,
                "forca": 5,
                "mana": 5,
                "nome_arma": "espada comum",
                "classe": "Guerreiro (Força Bruta)",
                "personalidade": "Calculista",
                "cor_r": 1,
                "cor_g": 2,
                "cor_b": 3,
            }
        ]

        armas_novas, personagens_novos, alteracoes = migrar_documentos(
            armas, personagens
        )

        self.assertEqual("Avanço Brutal", armas_novas[0]["habilidades"][0]["nome"])
        self.assertNotEqual(999, armas_novas[0]["habilidades"][0]["custo"])
        self.assertEqual("Tático", personagens_novos[0]["personalidade"])
        self.assertEqual("Espada Longa Comum", personagens_novos[0]["nome_arma"])
        self.assertEqual(1, personagens_novos[0]["cor_r"])
        self.assertEqual(3, len(alteracoes))

    def test_unknown_alias_is_rejected_by_the_domain_validator(self) -> None:
        armas = [
            {
                "nome": "Espada Longa Comum",
                "tipo": "Reta",
                "raridade": "Comum",
                "dano": 10,
                "peso": 3,
                "comp_cabo": 20,
                "comp_lamina": 50,
                "largura": 5,
                "habilidades": [{"nome": "Skill sem mapeamento", "custo": 1}],
            }
        ]
        personagens = [
            {
                "nome": "Teste",
                "tamanho": 1.8,
                "forca": 5,
                "mana": 5,
                "nome_arma": "Espada Longa Comum",
                "classe": "Guerreiro (Força Bruta)",
                "personalidade": "Tático",
            }
        ]

        with self.assertRaises(ValueError):
            migrar_documentos(armas, personagens)


if __name__ == "__main__":
    unittest.main()
