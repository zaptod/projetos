"""Headless regression tests for weapon editing round-trips."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models import Arma
import ui.view_armas as view_armas
from ui.view_armas import TelaArmas


class WeaponEditRegressionTests(unittest.TestCase):
    def _edit_without_tk(self, original):
        editor = object.__new__(TelaArmas)
        editor.controller = SimpleNamespace(lista_armas=[original])
        editor.tree = SimpleNamespace(
            selection=lambda: ("row",),
            index=lambda _row: 0,
        )
        editor.mostrar_passo = lambda _step: None
        editor.atualizar_lista = lambda: None
        editor.nova_arma = lambda: None

        editor.selecionar_arma(None)

        with (
            patch.object(view_armas, "salvar_lista_armas") as salvar,
            patch.object(view_armas.messagebox, "showinfo"),
            patch.object(view_armas.messagebox, "showerror") as mostrar_erro,
        ):
            editor.salvar_arma()

        mostrar_erro.assert_not_called()
        salvar.assert_called_once()
        return editor.controller.lista_armas[0]

    def test_edit_round_trip_preserves_advanced_attributes(self):
        original = Arma(
            nome="Relic",
            tipo="Transformável",
            dano=17.0,
            peso=8.0,
            raridade="Lendário",
            estilo="Duas Formas",
            habilidades=[{"nome": "Fireball", "custo": 23.0}],
            encantamentos=["Flamejante"],
            passiva={"nome": "Legado", "efeito": "teste", "valor": 7},
            critico=0.27,
            velocidade_ataque=1.45,
            afinidade_elemento="FOGO",
            durabilidade=31.0,
            durabilidade_max=240.0,
            forma1_cabo=25.0,
            forma1_lamina=70.0,
            forma2_cabo=90.0,
            forma2_lamina=35.0,
            largura=9.0,
        )

        reconstruida = self._edit_without_tk(original)

        self.assertEqual(reconstruida.to_dict(), original.to_dict())
        self.assertEqual(reconstruida.passiva, original.passiva)
        self.assertEqual(reconstruida.critico, original.critico)
        self.assertEqual(reconstruida.velocidade_ataque, original.velocidade_ataque)
        self.assertEqual(reconstruida.durabilidade, original.durabilidade)
        self.assertEqual(reconstruida.durabilidade_max, original.durabilidade_max)

    def test_edit_preserves_explicitly_absent_passive(self):
        original = Arma(
            nome="Sem Passiva",
            tipo="Reta",
            dano=10.0,
            peso=4.0,
            raridade="Lendário",
            passiva={"nome": "Temporaria"},
        )
        original.passiva = None

        reconstruida = self._edit_without_tk(original)

        self.assertIsNone(reconstruida.passiva)


if __name__ == "__main__":
    unittest.main()
