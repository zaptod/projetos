"""Regressoes da sessao de live de longa duracao.

A propriedade central destes testes e a que sustenta a monetizacao: a janela do
sistema precisa ser criada **uma unica vez** e sobreviver a todas as partidas da
transmissao. O OBS prende a captura numa janela especifica; se o processo
destruir e recriar a janela a cada luta, o operador perde a fonte no meio da
live e precisa reconfigurar na mao.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from neural_fights.data import database
from neural_fights.live.events import EventKind, ViewerEvent
from neural_fights.live.session import LiveSession, Matchmaker, SessionStats
from neural_fights.live.sources.replay import ScriptedEventSource
from neural_fights.simulation.simulacao import Simulador


def _roster(minimo: int = 3) -> list[str]:
    nomes = [personagem.nome for personagem in database.carregar_personagens()]
    if len(nomes) < minimo:
        raise unittest.SkipTest(f"roster com menos de {minimo} personagens")
    return nomes


@contextmanager
def sessao_de_teste(**opcoes):
    """Sessao real com display dummy; conta as chamadas a ``set_mode``."""
    nomes = _roster()
    config = {
        "p1_nome": nomes[0],
        "p2_nome": nomes[1],
        "cenario": "Arena",
        "best_of": 1,
    }
    set_mode_original = pygame.display.set_mode
    chamadas: list[tuple] = []

    def set_mode_contado(*args, **kwargs):
        chamadas.append(args)
        return set_mode_original(*args, **kwargs)

    with (
        patch.object(pygame.display, "set_mode", side_effect=set_mode_contado),
        patch.object(pygame.display, "flip"),
    ):
        simulador = Simulador(match_config=config, seed=11)
        try:
            sessao = LiveSession(
                simulador,
                Matchmaker(nomes[:3]),
                pausa_entre_partidas=0.0,
                **opcoes,
            )
            yield sessao, chamadas
        finally:
            simulador.close()


class JanelaEstavelTests(unittest.TestCase):
    def test_varias_partidas_usam_uma_unica_janela(self) -> None:
        """A propriedade que mantem a fonte de captura do OBS valida."""
        with sessao_de_teste() as (sessao, chamadas):
            self.assertEqual(len(chamadas), 1, "janela criada mais de uma vez")
            for _ in range(4):
                sessao.proxima_partida()
            self.assertEqual(
                len(chamadas),
                1,
                "troca de partida recriou a janela e quebraria a captura",
            )

    def test_troca_de_partida_nao_encerra_o_pygame(self) -> None:
        with sessao_de_teste() as (sessao, _chamadas):
            with patch.object(pygame, "quit") as quit_mock:
                sessao.proxima_partida()
                sessao.proxima_partida()
            quit_mock.assert_not_called()
            self.assertTrue(pygame.display.get_init())

    def test_titulo_da_janela_nunca_muda(self) -> None:
        """Captura de janela costuma casar por titulo; mudar quebra a fonte."""
        with sessao_de_teste() as (sessao, _chamadas):
            titulo = pygame.display.get_caption()
            sessao.proxima_partida()
            self.assertEqual(pygame.display.get_caption(), titulo)


class TrocaDePartidaTests(unittest.TestCase):
    def test_lutadores_e_cenario_sao_trocados(self) -> None:
        with sessao_de_teste() as (sessao, _chamadas):
            antes = (sessao.sim.p1.dados.nome, sessao.sim.p2.dados.nome)
            sessao.proxima_partida()
            depois = (sessao.sim.p1.dados.nome, sessao.sim.p2.dados.nome)
            self.assertNotEqual(antes, depois)
            self.assertEqual(sessao.sim.match_config["p1_nome"], depois[0])

    def test_serie_e_reiniciada_a_cada_partida(self) -> None:
        with sessao_de_teste() as (sessao, _chamadas):
            sessao.sim.best_of_series.record_win("p1")
            sessao.proxima_partida()
            self.assertIsNone(sessao.sim.best_of_series.winner)
            self.assertEqual(sessao.sim.best_of_series.wins["p1"], 0)

    def test_estado_de_round_e_limpo_apos_a_troca(self) -> None:
        with sessao_de_teste() as (sessao, _chamadas):
            sessao.sim.round_finalizado = True
            sessao.proxima_partida()
            self.assertFalse(sessao.sim.round_finalizado)
            self.assertIsNone(sessao.sim.vencedor)

    def test_sessao_para_ao_atingir_o_limite_de_partidas(self) -> None:
        with sessao_de_teste(max_partidas=2) as (sessao, _chamadas):
            sessao.rodando = True
            for _ in range(2):
                sessao.sim.round_finalizado = True
                sessao._avaliar_fim_de_partida()  # registra
                sessao._avaliar_fim_de_partida()  # decide
            self.assertFalse(sessao.rodando)
            self.assertEqual(sessao.stats.partidas, 2)


class EventosNoFrameTests(unittest.TestCase):
    def test_evento_e_aplicado_antes_do_update(self) -> None:
        """A ordem e o que torna um gift indistinguivel de uma skill."""
        ordem: list[str] = []

        def aplicar(_sessao, _evento) -> bool:
            ordem.append("evento")
            return True

        with sessao_de_teste(aplicar_evento=aplicar) as (sessao, _chamadas):
            fonte = ScriptedEventSource()
            fonte.start()
            sessao.fontes = (fonte,)
            fonte.push(
                ViewerEvent(
                    platform="youtube",
                    viewer_id="UC-1",
                    viewer_name="Ana",
                    kind=EventKind.GIFT,
                    value_units=10,
                )
            )
            update_original = sessao.sim.update
            with patch.object(
                sessao.sim,
                "update",
                side_effect=lambda dt: (ordem.append("update"), update_original(dt))[1],
            ):
                sessao.passo(1.0 / 60.0)
            fonte.stop()

        self.assertEqual(ordem, ["evento", "update"])

    def test_evento_sem_handler_e_contabilizado_como_ignorado(self) -> None:
        with sessao_de_teste() as (sessao, _chamadas):
            fonte = ScriptedEventSource()
            fonte.start()
            sessao.fontes = (fonte,)
            fonte.push(
                ViewerEvent(
                    platform="youtube",
                    viewer_id="UC-1",
                    viewer_name="Ana",
                    kind=EventKind.CHAT,
                )
            )
            sessao.drenar_eventos()
            fonte.stop()

        self.assertEqual(sessao.stats.eventos_recebidos, 1)
        self.assertEqual(sessao.stats.eventos_aplicados, 0)
        self.assertEqual(sessao.stats.eventos_ignorados, 1)

    def test_handler_que_explode_nao_derruba_a_sessao(self) -> None:
        def aplicar(_sessao, _evento) -> bool:
            raise RuntimeError("comando malformado")

        with sessao_de_teste(aplicar_evento=aplicar) as (sessao, _chamadas):
            fonte = ScriptedEventSource()
            fonte.start()
            sessao.fontes = (fonte,)
            fonte.push(
                ViewerEvent(
                    platform="youtube",
                    viewer_id="UC-1",
                    viewer_name="Ana",
                    kind=EventKind.GIFT,
                    value_units=5,
                )
            )
            with self.assertLogs("neural_fights.live.session", level="ERROR"):
                sessao.drenar_eventos()
            fonte.stop()

        self.assertEqual(sessao.stats.eventos_ignorados, 1)

    def test_rajada_respeita_o_orcamento_do_frame(self) -> None:
        aplicados: list[str] = []

        def aplicar(_sessao, evento) -> bool:
            aplicados.append(evento.event_id)
            return True

        with sessao_de_teste(aplicar_evento=aplicar) as (sessao, _chamadas):
            fonte = ScriptedEventSource(capacidade=500)
            fonte.start()
            sessao.fontes = (fonte,)
            fonte.push(
                *[
                    ViewerEvent(
                        platform="youtube",
                        viewer_id=f"UC-{i}",
                        viewer_name="A",
                        kind=EventKind.GIFT,
                        value_units=1,
                        sequence=i,
                    )
                    for i in range(200)
                ]
            )
            sessao.drenar_eventos(limite=32)
            fonte.stop()

        self.assertEqual(len(aplicados), 32)


class SessionStatsTests(unittest.TestCase):
    def test_vitorias_sao_acumuladas_por_nome(self) -> None:
        stats = SessionStats()
        stats.registrar_vitoria("Ana")
        stats.registrar_vitoria("Ana")
        stats.registrar_vitoria("Beto")
        self.assertEqual(stats.vitorias_por_lutador, {"Ana": 2, "Beto": 1})


class SessionGuardTests(unittest.TestCase):
    def test_matchmaker_exige_dois_lutadores(self) -> None:
        with self.assertRaisesRegex(ValueError, "ao menos dois"):
            Matchmaker(["so_um"])

    def test_matchmaker_faz_rodizio(self) -> None:
        matchmaker = Matchmaker(["A", "B", "C"])
        self.assertEqual(matchmaker.proximo()[:2], ("A", "B"))
        self.assertEqual(matchmaker.proximo()[:2], ("B", "C"))
        self.assertEqual(matchmaker.proximo()[:2], ("C", "A"))

    def test_matchmaker_pula_o_confronto_que_acabou_de_acontecer(self) -> None:
        """Repetir a mesma luta em seguida e a falha mais visivel na tela."""
        matchmaker = Matchmaker(["A", "B", "C"])
        self.assertEqual(matchmaker.proximo(evitar=frozenset({"A", "B"}))[:2], ("B", "C"))

    def test_roster_de_dois_repete_por_falta_de_alternativa(self) -> None:
        matchmaker = Matchmaker(["A", "B"])
        p1, p2, _ = matchmaker.proximo(evitar=frozenset({"A", "B"}))
        self.assertEqual({p1, p2}, {"A", "B"})

    def test_sessao_recusa_simulador_headless(self) -> None:
        nomes = _roster(2)
        config = {"p1_nome": nomes[0], "p2_nome": nomes[1], "best_of": 1}
        simulador = Simulador(match_config=config, headless=True, seed=3)
        try:
            with self.assertRaisesRegex(RuntimeError, "HeadlessMatchRunner"):
                LiveSession(simulador, Matchmaker(nomes[:2]))
        finally:
            simulador.close()


if __name__ == "__main__":
    unittest.main()
