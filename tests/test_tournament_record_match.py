"""MOT-102 e MOT-124 (auditoria profunda de 11/10/2026).

- MOT-102: o resultado de "SIMULAR LUTA" de uma luta que nao era a corrente
  ia para a luta corrente e era descartado em silencio.
- MOT-124: chave sem seed (dois torneios iguais, chaves diferentes), seed do
  retry colidindo com a luta seguinte e estatisticas sempre ``None``.
"""
import os
import tempfile
import unittest
from unittest import mock

from neural_fights.tournament.tournament_mode import Tournament, TournamentRunner


def _torneio(n=4, seed=1):
    t = Tournament("T", seed=seed)
    for i in range(n):
        t.add_participant(f"L{i}")
    t.generate_bracket()
    t.start_tournament()
    return t


class RegistrarNaLutaSelecionadaTests(unittest.TestCase):
    def test_luta_que_nao_e_a_corrente_e_registrada(self):
        t = _torneio()
        corrente = t.get_current_match()
        segunda = t.bracket[0].matches[1]
        self.assertIsNot(corrente, segunda)
        ok = t.record_match_result(
            winner_name=segunda.fighter2_name, duration=12.0, match=segunda
        )
        self.assertTrue(ok)
        self.assertTrue(segunda.completed)
        self.assertEqual(segunda.winner_name, segunda.fighter2_name)
        # a corrente continua pendente e o ponteiro nao andou
        self.assertFalse(corrente.completed)
        self.assertIs(t.get_current_match(), corrente)
        # o vencedor foi para a final
        final = t.bracket[1].matches[0]
        self.assertEqual(final.fighter2_name, segunda.fighter2_name)

    def test_sem_match_continua_a_corrente(self):
        t = _torneio()
        corrente = t.get_current_match()
        segunda = t.bracket[0].matches[1]
        self.assertFalse(t.record_match_result(winner_name=segunda.fighter1_name))
        self.assertTrue(t.record_match_result(winner_name=corrente.fighter1_name))
        self.assertTrue(corrente.completed)

    def test_recusa_luta_concluida_e_luta_sem_lutadores(self):
        t = _torneio()
        primeira = t.bracket[0].matches[0]
        self.assertTrue(t.record_match_result(primeira.fighter1_name, match=primeira))
        self.assertFalse(t.record_match_result(primeira.fighter1_name, match=primeira))
        final = t.bracket[1].matches[0]
        self.assertIn("TBD", (final.fighter1_name, final.fighter2_name))
        self.assertFalse(t.record_match_result(final.fighter1_name, match=final))

    def test_fora_de_ordem_salva_e_recarrega(self):
        t = _torneio()
        segunda = t.bracket[0].matches[1]
        t.record_match_result(segunda.fighter1_name, duration=3.0, match=segunda)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "estado.json")
            t.save_state(caminho)
            outro = Tournament("x")
            self.assertTrue(outro.load_state(caminho))
            self.assertTrue(outro.bracket[0].matches[1].completed)
            self.assertEqual(outro.seed, t.seed)


class ChaveESeedsTests(unittest.TestCase):
    NOMES = [f"P{i}" for i in range(8)]

    def _chave(self, seed):
        t = Tournament("T", seed=seed)
        for nome in self.NOMES:
            t.add_participant(nome)
        t.generate_bracket()
        return [(m.fighter1_name, m.fighter2_name) for m in t.bracket[0].matches]

    def test_chave_reproduzivel_e_seeds_distintos(self):
        self.assertEqual(self._chave(7), self._chave(7))
        self.assertNotEqual(self._chave(7), self._chave(8))

        t = _torneio(8, seed=7)
        runner = TournamentRunner(t)
        runner.simulation_config["draw_retry_limit"] = 2
        vistos = []

        class _Empate:
            success = True
            winner = None
            reason = "time"

            def to_dict(self):
                return {}

        def falso(config, **kw):
            vistos.append(kw["seed"])
            return _Empate()

        with mock.patch("neural_fights.simulation.headless.run_headless_match", falso):
            for rodada in t.bracket:
                for luta in rodada.matches:
                    runner.run_single_match(luta)
        self.assertEqual(len(vistos), 7 * 3)
        self.assertEqual(len(set(vistos)), len(vistos))
        # a 1a tentativa continua seed + match_id (torneios antigos iguais)
        base = int(runner.simulation_config.get("seed", 0))
        self.assertEqual(vistos[0], base + 0)
        self.assertEqual(vistos[3], base + 1)

    def test_mesmo_sorteio_que_o_random_global_semeado(self):
        # o random_builds prendia o random global com random.seed(x); o
        # Random(x) do torneio tem de dar a mesma chave de antes.
        import random

        estado = random.getstate()
        try:
            random.seed(1234)
            antigo = list(self.NOMES)
            random.shuffle(antigo)
        finally:
            random.setstate(estado)
        t = Tournament("T", seed=1234)
        t.participants = list(self.NOMES)
        t.shuffle_participants()
        self.assertEqual(t.participants, antigo)


class EstatisticasTests(unittest.TestCase):
    def test_ko_mais_rapido_luta_mais_longa_e_mais_agressivo(self):
        t = _torneio(4)
        a = t.bracket[0].matches[0]
        b = t.bracket[0].matches[1]
        t.record_match_result(
            a.fighter1_name, duration=30.0, ko_type="KO", match=a,
            hp_ratios={a.fighter1_name: 0.5, a.fighter2_name: 0.0},
        )
        t.record_match_result(
            b.fighter2_name, duration=60.0, ko_type="Decisão por HP", match=b,
            hp_ratios={b.fighter1_name: 0.4, b.fighter2_name: 0.6},
        )
        self.assertEqual(t.stats["fastest_ko"], 30.0)
        self.assertEqual(t.stats["longest_fight"], 60.0)
        # a.fighter1 tirou 100% em 30 s (3,3%/s), o maior
        self.assertEqual(t.stats["most_aggressive"], a.fighter1_name)

    def test_vencedor_na_mao_nao_entra(self):
        t = _torneio(4)
        a = t.bracket[0].matches[0]
        t.record_match_result(a.fighter1_name, duration=0, ko_type="KO", match=a)
        self.assertIsNone(t.stats["fastest_ko"])
        self.assertIsNone(t.stats["longest_fight"])
        self.assertIsNone(t.stats["most_aggressive"])

    def test_estatisticas_sobrevivem_ao_save(self):
        t = _torneio(4)
        a = t.bracket[0].matches[0]
        t.record_match_result(
            a.fighter1_name, duration=20.0, match=a,
            hp_ratios={a.fighter1_name: 0.9, a.fighter2_name: 0.0},
        )
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "estado.json")
            t.save_state(caminho)
            outro = Tournament("x")
            self.assertTrue(outro.load_state(caminho))
        self.assertEqual(outro.stats["fastest_ko"], 20.0)
        self.assertEqual(outro.stats["most_aggressive"], a.fighter1_name)
        self.assertEqual(outro._agressao, t._agressao)


if __name__ == "__main__":
    unittest.main()

