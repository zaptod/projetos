"""Regressoes do vocabulario de comandos pagos.

Aqui dinheiro vira efeito na luta, entao as propriedades testadas sao as que
protegem o espectador e a transmissao:

* o efeito de um gift entra pelos **mesmos** buffers que uma skill, e e drenado
  pela mesma fase do frame;
* caos e simetrico -- ninguem recebe vantagem que nao comprou;
* recusa por regra nunca cobra, e intencao paga que nao coube vira credito do
  proximo round em vez de sumir;
* comando de proxima partida jamais altera o round em andamento.
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
from neural_fights.live import effects
from neural_fights.live.catalog import COMMAND_DB, command_por_gatilho, get_command
from neural_fights.live.commands import (
    STATUS_ADIADO,
    STATUS_APLICADO,
    STATUS_RECUSADO,
    CommandRouter,
)
from neural_fights.live.events import ViewerEvent
from neural_fights.live.policy import Decisao, PolicyEngine
from neural_fights.live.registry import LiveRegistry


class RelogioFalso:
    """Relogio controlado pelo teste: cooldown vira assercao deterministica."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


def evento(texto: str, **overrides) -> ViewerEvent:
    base = {
        "platform": "youtube",
        "viewer_id": "UC-ana",
        "viewer_name": "Ana",
        "kind": "gift",
        "text": texto,
        "value_units": 10_000,
    }
    base.update(overrides)
    return ViewerEvent(**base)


@contextmanager
def cenario():
    """Simulador real com display dummy, registro em memoria e relogio falso."""
    nomes = [p.nome for p in database.carregar_personagens()][:2]
    if len(nomes) < 2:
        raise unittest.SkipTest("roster insuficiente")
    config = {"p1_nome": nomes[0], "p2_nome": nomes[1], "cenario": "Arena", "best_of": 1}

    from neural_fights.simulation.simulacao import Simulador

    with (
        patch.object(pygame.display, "set_mode", side_effect=lambda *a, **k: pygame.Surface(a[0])),
        patch.object(pygame.display, "flip"),
    ):
        sim = Simulador(match_config=config, seed=17)
    registry = LiveRegistry(":memory:")
    relogio = RelogioFalso()
    router = CommandRouter(
        registry, simulador=sim, policy=PolicyEngine(relogio=relogio)
    )
    try:
        yield sim, router, relogio, registry
    finally:
        registry.close()
        sim.close()


class CatalogoTests(unittest.TestCase):
    def test_todo_comando_tem_gatilho_resolvivel(self) -> None:
        for command_id, dados in COMMAND_DB.items():
            gatilho = dados.get("gatilho")
            if gatilho:
                with self.subTest(command_id=command_id):
                    self.assertEqual(command_por_gatilho(gatilho), command_id)

    def test_get_command_devolve_copia(self) -> None:
        copia = get_command("curar")
        copia["custo_units"] = 1
        self.assertNotEqual(COMMAND_DB["curar"]["custo_units"], 1)

    def test_comando_desconhecido_levanta(self) -> None:
        with self.assertRaises(KeyError):
            get_command("nao_existe")

    def test_as_tres_categorias_estao_cobertas(self) -> None:
        categorias = {dados["categoria"] for dados in COMMAND_DB.values()}
        self.assertEqual(categorias, {"ASSIST", "CAOS", "PROXIMO_ROUND"})


class EfeitoAssistTests(unittest.TestCase):
    def test_curar_restaura_vida_do_alvo_escolhido(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p1.vida = sim.p1.vida_max - 60
            sim.p2.vida = sim.p2.vida_max - 60
            vida_p2_antes = sim.p2.vida

            resultado = router.processar(evento("!curar p1"))

            self.assertEqual(resultado.status, STATUS_APLICADO)
            self.assertGreater(sim.p1.vida, sim.p1.vida_max - 60)
            self.assertEqual(sim.p2.vida, vida_p2_antes, "assist vazou para o outro lado")

    def test_cura_forte_tambem_remove_debuffs(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p1.vida = sim.p1.vida_max - 80
            sim.p1._aplicar_efeito_status("QUEIMANDO")
            self.assertTrue(sim.p1._tipos_dot_ativos())

            self.assertEqual(router.processar(evento("!curargrande p1")).status, STATUS_APLICADO)
            self.assertGreater(sim.p1.vida, sim.p1.vida_max - 80)

    def test_purificar_limpa_debuffs_e_concede_imunidade(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p1._aplicar_efeito_status("ENVENENADO")
            sim.p1._aplicar_efeito_status("LENTO")

            self.assertEqual(router.processar(evento("!purificar p1")).status, STATUS_APLICADO)

            self.assertFalse(sim.p1._tipos_dot_ativos())
            self.assertGreater(sim.p1.imune_debuffs_timer, 0.0)

    def test_buff_persistente_entra_na_lista_do_lutador(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            antes = len(sim.p1.buffs_ativos)
            self.assertEqual(router.processar(evento("!acelerar p1")).status, STATUS_APLICADO)
            self.assertGreater(len(sim.p1.buffs_ativos), antes)

            antes_furia = len(sim.p2.buffs_ativos)
            self.assertEqual(
                router.processar(evento("!furia p2", viewer_id="UC-b")).status,
                STATUS_APLICADO,
            )
            self.assertGreater(len(sim.p2.buffs_ativos), antes_furia)

    def test_livrar_remove_os_debuffs_ativos(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p1._aplicar_efeito_status("ENVENENADO")
            sim.p1._aplicar_efeito_status("CEGO")

            resultado = router.processar(evento("!livrar p1"))

            self.assertEqual(resultado.status, STATUS_APLICADO)
            self.assertFalse(sim.p1._tipos_dot_ativos())
            self.assertEqual(sim.p1.cego_timer, 0.0)

    def test_alvo_ausente_e_recusado_sem_cobrar(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            resultado = router.processar(evento("!curar"))
            self.assertEqual(resultado.status, STATUS_RECUSADO)
            self.assertIn("alvo", resultado.detalhe)

    def test_alvo_morto_adia_em_vez_de_cobrar(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p1.morto = True
            resultado = router.processar(evento("!curar p1"))
            self.assertEqual(resultado.status, STATUS_ADIADO)
            self.assertEqual(router.policy.round.usos_por_comando.get("curar", 0), 0)


class EfeitoCaosTests(unittest.TestCase):
    def test_caos_instancia_uma_area_por_lutador(self) -> None:
        """Duas areas espelhadas: cada lutador e atingido pela do outro."""
        with cenario() as (sim, router, _relogio, _reg):
            resultado = router.processar(evento("!meteoro"))

            self.assertEqual(resultado.status, STATUS_APLICADO)
            self.assertEqual(len(sim.p1.buffer_areas), 1)
            self.assertEqual(len(sim.p2.buffer_areas), 1)
            self.assertIs(sim.p1.buffer_areas[0].dono, sim.p1)
            self.assertIs(sim.p2.buffer_areas[0].dono, sim.p2)

    def test_caos_atinge_os_dois_lutadores(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            router.processar(evento("!nevasca"))
            areas = sim.p1.buffer_areas + sim.p2.buffer_areas
            donos = {id(area.dono) for area in areas}
            self.assertEqual(donos, {id(sim.p1), id(sim.p2)})
            for area in areas:
                self.assertFalse(area.afeta_caster, "area atingiria o proprio dono em dobro")

    def test_area_de_caos_e_drenada_pelo_frame_como_uma_skill(self) -> None:
        """A propriedade central: gift e skill percorrem o mesmo caminho."""
        with cenario() as (sim, router, _relogio, _reg):
            self.assertEqual(len(sim.areas), 0)
            router.processar(evento("!meteoro"))

            sim.update(1.0 / 60.0)

            self.assertEqual(len(sim.p1.buffer_areas), 0, "buffer nao foi drenado")
            self.assertEqual(len(sim.p2.buffer_areas), 0)
            self.assertEqual(len(sim.areas), 2)

    def test_caos_exige_os_dois_lutadores_vivos(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p2.morto = True
            resultado = router.processar(evento("!tempestade"))
            self.assertEqual(resultado.status, STATUS_ADIADO)
            self.assertEqual(len(sim.p1.buffer_areas), 0)

    def test_caos_nunca_usa_skill_que_beneficia_o_dono(self) -> None:
        """Contrato de justica, tambem travado pela auditoria."""
        from neural_fights.core.skills import SKILL_DB
        from neural_fights.live.catalog import CAMPOS_INJUSTOS_EM_GLOBAL

        for command_id, dados in COMMAND_DB.items():
            if dados["escopo"] != "GLOBAL":
                continue
            with self.subTest(command_id=command_id):
                skill = SKILL_DB[dados["skill"]]
                for campo in CAMPOS_INJUSTOS_EM_GLOBAL:
                    self.assertNotIn(campo, skill)


class ProximoRoundTests(unittest.TestCase):
    def test_arena_valida_entra_na_fila_do_proximo_round(self) -> None:
        with cenario() as (sim, router, _relogio, registry):
            cenario_antes = sim.match_config["cenario"]

            resultado = router.processar(evento("!arena Vulcao"))

            self.assertEqual(resultado.status, STATUS_APLICADO)
            self.assertEqual(registry.fila_pendente(), 1)
            self.assertEqual(
                sim.match_config["cenario"],
                cenario_antes,
                "comando de proximo round alterou o round em andamento",
            )

    def test_arena_desconhecida_e_recusada(self) -> None:
        with cenario() as (sim, router, _relogio, registry):
            resultado = router.processar(evento("!arena Planeta Marte"))
            self.assertEqual(resultado.status, STATUS_RECUSADO)
            self.assertEqual(registry.fila_pendente(), 0)

    def test_arena_sem_argumento_e_recusada(self) -> None:
        with cenario() as (_sim, router, _relogio, registry):
            self.assertEqual(router.processar(evento("!arena")).status, STATUS_RECUSADO)
            self.assertEqual(registry.fila_pendente(), 0)

    def test_fila_e_consumida_em_ordem_e_so_uma_vez(self) -> None:
        with cenario() as (_sim, router, relogio, registry):
            router.processar(evento("!arena Vulcao", event_id="a"))
            relogio.avancar(400.0)
            router.processar(evento("!arena Gelo", event_id="b", viewer_id="UC-b"))

            fila = registry.consumir_fila_do_round()

            self.assertEqual([item["payload"] for item in fila], ["Vulcao", "Gelo"])
            self.assertEqual(registry.consumir_fila_do_round(), [])


class PoliticaTests(unittest.TestCase):
    def test_cooldown_global_adia_repeticao_imediata(self) -> None:
        with cenario() as (_sim, router, relogio, _reg):
            self.assertEqual(router.processar(evento("!curar p1", event_id="1")).status, STATUS_APLICADO)
            segundo = router.processar(evento("!curar p1", event_id="2", viewer_id="UC-b"))
            self.assertEqual(segundo.status, STATUS_ADIADO)
            self.assertIn("cooldown_global", segundo.detalhe)

            relogio.avancar(get_command("curar")["cooldown_global"] + 0.1)
            terceiro = router.processar(evento("!curar p1", event_id="3", viewer_id="UC-c"))
            self.assertEqual(terceiro.status, STATUS_APLICADO)

    def test_cooldown_do_espectador_impede_monopolio(self) -> None:
        with cenario() as (_sim, router, relogio, _reg):
            router.processar(evento("!curar p1", event_id="1"))
            relogio.avancar(get_command("curar")["cooldown_global"] + 0.1)

            repetido = router.processar(evento("!curar p1", event_id="2"))

            self.assertEqual(repetido.status, STATUS_RECUSADO)
            self.assertIn("cooldown_viewer", repetido.detalhe)

    def test_creditos_insuficientes_recusam_sem_aplicar(self) -> None:
        with cenario() as (sim, router, _relogio, _reg):
            sim.p1.vida = sim.p1.vida_max - 50
            antes = sim.p1.vida

            resultado = router.processar(evento("!curar p1", value_units=1))

            self.assertEqual(resultado.status, STATUS_RECUSADO)
            self.assertIn("creditos_insuficientes", resultado.detalhe)
            self.assertEqual(sim.p1.vida, antes)

    def test_moderador_escapa_de_cooldown_mas_e_journalizado(self) -> None:
        with cenario() as (_sim, router, _relogio, registry):
            router.processar(evento("!curar p1", event_id="1", is_moderator=True))
            segundo = router.processar(
                evento("!curar p1", event_id="2", is_moderator=True)
            )
            self.assertEqual(segundo.status, STATUS_APLICADO)
            self.assertEqual(registry.status_do_evento("2")[0], STATUS_APLICADO)

    def test_teto_por_round_adia_e_zera_na_proxima_partida(self) -> None:
        relogio = RelogioFalso()
        policy = PolicyEngine(relogio=relogio)
        maximo = get_command("meteoro")["max_por_round"]

        for indice in range(maximo):
            veredito = policy.avaliar(
                "meteoro", viewer_id=f"v{indice}", value_units=10_000
            )
            self.assertTrue(veredito.aplicar)
            policy.registrar_uso("meteoro", f"v{indice}")
            relogio.avancar(100.0)

        estourado = policy.avaliar("meteoro", viewer_id="vx", value_units=10_000)
        self.assertTrue(estourado.adiar)
        self.assertEqual(estourado.motivo, "teto_do_round")

        policy.novo_round()
        self.assertTrue(policy.avaliar("meteoro", viewer_id="vx", value_units=10_000).aplicar)

    def test_banido_e_recusado_antes_de_qualquer_economia(self) -> None:
        policy = PolicyEngine(relogio=RelogioFalso())
        veredito = policy.avaliar(
            "curar", viewer_id="v", value_units=0, banido=True
        )
        self.assertEqual(veredito.decisao, Decisao.RECUSAR)
        self.assertEqual(veredito.motivo, "banido")

    def test_saturacao_protege_o_frame(self) -> None:
        policy = PolicyEngine(relogio=RelogioFalso(), saturacao_max=2)
        veredito = policy.avaliar(
            "meteoro", viewer_id="v", value_units=10_000, estado_mundo={"areas": 5}
        )
        self.assertTrue(veredito.adiar)
        self.assertEqual(veredito.motivo, "saturacao")

    def test_historico_do_espectador_sobrevive_a_troca_de_round(self) -> None:
        relogio = RelogioFalso()
        policy = PolicyEngine(relogio=relogio)
        policy.avaliar("curar", viewer_id="v", value_units=10_000)
        policy.registrar_uso("curar", "v", custo=30)

        policy.novo_round()

        veredito = policy.avaliar("curar", viewer_id="v", value_units=10_000)
        self.assertEqual(veredito.motivo, "cooldown_viewer")
        self.assertEqual(policy.estado_viewer("v").creditos_gastos, 30)


class MomentoTests(unittest.TestCase):
    def test_assist_fora_do_round_e_recusado(self) -> None:
        policy = PolicyEngine(relogio=RelogioFalso())
        veredito = policy.avaliar(
            "curar", viewer_id="v", value_units=10_000, round_ativo=False
        )
        self.assertEqual(veredito.decisao, Decisao.RECUSAR)
        self.assertEqual(veredito.motivo, "fora_do_momento")

    def test_comando_de_proximo_round_vale_entre_rounds(self) -> None:
        policy = PolicyEngine(relogio=RelogioFalso())
        veredito = policy.avaliar(
            "arena", viewer_id="v", value_units=10_000, round_ativo=False
        )
        self.assertTrue(veredito.aplicar)


class EffectsGuardTests(unittest.TestCase):
    def test_resolver_alvo_aceita_apenas_slots_conhecidos(self) -> None:
        with cenario() as (sim, _router, _relogio, _reg):
            self.assertIs(effects.resolver_alvo(sim, "p1"), sim.p1)
            self.assertIs(effects.resolver_alvo(sim, "P2"), sim.p2)
            self.assertIsNone(effects.resolver_alvo(sim, "p3"))
            self.assertIsNone(effects.resolver_alvo(sim, ""))

    def test_slot_de_faz_o_caminho_inverso(self) -> None:
        with cenario() as (sim, _router, _relogio, _reg):
            self.assertEqual(effects.slot_de(sim, sim.p1), "p1")
            self.assertEqual(effects.slot_de(sim, sim.p2), "p2")
            self.assertIsNone(effects.slot_de(sim, object()))

    def test_escopo_round_nunca_e_aplicado_no_frame(self) -> None:
        with cenario() as (sim, _router, _relogio, _reg):
            with self.assertRaises(effects.EfeitoIndisponivel):
                effects.aplicar(sim, "arena")


if __name__ == "__main__":
    unittest.main()
