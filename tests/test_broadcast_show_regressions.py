# -*- coding: utf-8 -*-
"""Contratos da camada de broadcast (Passe 3 do programa de arte).

O que se trava aqui: o peek do próximo confronto avança o rodízio UMA
única vez por partida; o ResultadoComando completo chega ao overlay (era
reduzido a bool e jogado fora); um overlay quebrado nunca derruba o
frame da transmissão; e o mapa catalog→display existe no registry.
"""

import unittest
from types import SimpleNamespace

from neural_fights.live.broadcast import BroadcastOverlay
from neural_fights.live.commands import criar_handler
from neural_fights.live.registry import LiveRegistry
from neural_fights.live.session import LiveSession, Matchmaker


class RelogioFake:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def sessao_fake(pausa=6.0):
    sim = SimpleNamespace(
        headless=False,
        rodando=True,
        match_config={"p1_nome": "A", "p2_nome": "B", "nomes_exibicao": {}},
        vencedor=None,
        round_finalizado=False,
        tela=None,
    )
    relogio = RelogioFake()
    sessao = LiveSession(
        sim,
        Matchmaker(["A", "B", "C", "D"], ("Arena",)),
        pausa_entre_partidas=pausa,
        relogio=relogio,
    )
    return sessao, sim, relogio


class PeekDoConfrontoTests(unittest.TestCase):
    def test_rodizio_avanca_uma_vez_por_partida(self) -> None:
        """O peek (para a VS screen) usa cache; proxima_partida consome o
        MESMO confronto em vez de sortear outro."""
        sessao, sim, relogio = sessao_fake()
        sim.round_finalizado = True
        sim.vencedor = SimpleNamespace(dados=SimpleNamespace(nome="A"))
        sessao._avaliar_fim_de_partida()  # registra + faz o peek

        confronto_peek = sessao.proximo_confronto
        self.assertIsNotNone(confronto_peek)

        # consumo: recarregar_tudo/reset sao fakes
        sim.recarregar_tudo = lambda: None
        sim.best_of_series = SimpleNamespace(reset_series=lambda: None)
        sessao.proxima_partida()
        self.assertEqual(
            (sim.match_config["p1_nome"], sim.match_config["p2_nome"]),
            confronto_peek[:2],
        )
        self.assertIsNone(sessao.proximo_confronto)  # cache consumido

    def test_tempo_na_pausa_segue_o_relogio_da_sessao(self) -> None:
        sessao, sim, relogio = sessao_fake()
        self.assertIsNone(sessao.tempo_na_pausa)
        sim.round_finalizado = True
        sim.vencedor = SimpleNamespace(dados=SimpleNamespace(nome="A"))
        sessao._avaliar_fim_de_partida()
        relogio.t = 2.5
        self.assertAlmostEqual(sessao.tempo_na_pausa, 2.5)


class ResultadoCompletoTests(unittest.TestCase):
    def test_ao_aplicar_recebe_o_resultado_completo(self) -> None:
        """O hook do Passe 3: nada de reduzir a bool."""
        registry = LiveRegistry(":memory:")
        recebidos = []
        handler = criar_handler(
            registry, ao_aplicar=lambda res, ev: recebidos.append((res, ev))
        )
        evento = SimpleNamespace(
            event_id="t:1", kind=SimpleNamespace(value="chat"), platform="t",
            viewer_id="v1", viewer_name="Ana", texto="!entrar",
            value_units=0, is_moderator=False, is_owner=False,
            gift_id="", raw_amount=0.0, raw_currency="", sequence=1,
            timestamp=0.0,
        )
        handler(SimpleNamespace(sim=None), evento)
        self.assertEqual(len(recebidos), 1)
        resultado, ev = recebidos[0]
        self.assertTrue(hasattr(resultado, "status"))
        self.assertIs(ev, evento)

    def test_callback_quebrado_nao_derruba_o_comando(self) -> None:
        registry = LiveRegistry(":memory:")

        def bomba(res, ev):
            raise RuntimeError("overlay morreu")

        handler = criar_handler(registry, ao_aplicar=bomba)
        evento = SimpleNamespace(
            event_id="t:2", kind=SimpleNamespace(value="chat"), platform="t",
            viewer_id="v1", viewer_name="Ana", texto="oi",
            value_units=0, is_moderator=False, is_owner=False,
            gift_id="", raw_amount=0.0, raw_currency="", sequence=2,
            timestamp=0.0,
        )
        # não explode; conversa é ignorada normalmente
        self.assertFalse(handler(SimpleNamespace(sim=None), evento))


class OverlayDefensivoTests(unittest.TestCase):
    def test_lower_third_e_expiracao(self) -> None:
        sessao, sim, relogio = sessao_fake()
        overlay = BroadcastOverlay(sessao)
        resultado = SimpleNamespace(aplicado=True, status="APLICADO", detalhe="")
        evento = SimpleNamespace(viewer_name="Ana_Gamer", texto="!meteoro", value_units=300)
        overlay.notificar_comando(resultado, evento)
        self.assertEqual(len(overlay._lower_thirds), 1)
        self.assertEqual(overlay._lower_thirds[0]["nome"], "Ana_Gamer")
        self.assertEqual(overlay._lower_thirds[0]["verbo"], "!meteoro")

    def test_overlay_quebrado_nao_derruba_o_passo(self) -> None:
        """A sessão engole a exceção do overlay: o show nunca cai."""
        sessao, sim, relogio = sessao_fake()
        sim.processar_inputs = lambda: None
        sim.avancar_relogio = lambda dt: dt
        sim.update = lambda dt: None
        sim.desenhar = lambda: None

        class OverlayBomba:
            def desenhar(self, tela):
                raise RuntimeError("boom")

        sessao.overlay = OverlayBomba()
        import unittest.mock as mock

        with mock.patch("neural_fights.live.session.pygame") as pg:
            pg.display.flip = lambda: None
            sessao.passo(1 / 60)  # não levanta
        self.assertEqual(sessao.stats.frames, 1)


class MapaDeNomesTests(unittest.TestCase):
    def test_registry_expoe_catalog_para_display(self) -> None:
        registry = LiveRegistry(":memory:")
        mapa = registry.mapa_nomes_exibicao()
        self.assertIsInstance(mapa, dict)


if __name__ == "__main__":
    unittest.main()
