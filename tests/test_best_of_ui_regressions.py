"""Headless regression tests for the best-of fight setting."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import neural_fights.ui.view_luta as view_luta
from neural_fights.ui.view_luta import TelaLuta


class BestOfUIRegressionTests(unittest.TestCase):
    def test_initial_value_uses_persisted_supported_best_of_without_saving(self):
        for persisted, expected in ((1, "1"), (3, "3"), (5, "5"), ("3", "3")):
            with (
                self.subTest(persisted=persisted),
                patch.object(
                    view_luta,
                    "carregar_match_config",
                    return_value={"best_of": persisted},
                ) as carregar,
                patch.object(view_luta, "salvar_match_config") as salvar,
            ):
                self.assertEqual(view_luta.carregar_best_of_inicial(), expected)
                carregar.assert_called_once_with()
                salvar.assert_not_called()

    def test_initial_value_falls_back_for_missing_or_invalid_best_of(self):
        for persisted in (None, 0, 2, 7, True, 3.0, "invalid"):
            with self.subTest(persisted=persisted), patch.object(
                view_luta,
                "carregar_match_config",
                return_value={"best_of": persisted},
            ):
                self.assertEqual(view_luta.carregar_best_of_inicial(), "1")

        with patch.object(
            view_luta,
            "carregar_match_config",
            side_effect=ValueError("config invalida"),
        ):
            self.assertEqual(view_luta.carregar_best_of_inicial(), "1")

    def test_starting_fight_saves_the_selected_best_of(self):
        events = []
        screen = object.__new__(TelaLuta)
        screen.personagem_p1 = SimpleNamespace(nome="A")
        screen.personagem_p2 = SimpleNamespace(nome="B")
        screen.var_cenario = SimpleNamespace(get=lambda: "Arena")
        screen.var_best_of = SimpleNamespace(get=lambda: "5")
        screen.var_portrait = SimpleNamespace(get=lambda: False)
        screen.controller = SimpleNamespace(
            withdraw=lambda: events.append("withdraw"),
            deiconify=lambda: events.append("deiconify"),
        )

        class FakeSimulator:
            def __init__(self, *, match_config):
                events.append(("config", match_config))

            def run(self):
                events.append("run")

        with (
            patch.object(view_luta, "salvar_match_config") as salvar,
            patch.object(view_luta.simulacao, "Simulador", FakeSimulator),
        ):
            screen.iniciar_luta()

        salvar.assert_called_once()
        self.assertEqual(salvar.call_args.args[0]["best_of"], 5)
        self.assertEqual(events[0], "withdraw")
        self.assertEqual(events[1][0], "config")
        self.assertEqual(events[1][1]["best_of"], 5)
        self.assertEqual(events[2:], ["run", "deiconify"])


if __name__ == "__main__":
    unittest.main()
