"""Regressoes da progressao: lutador de espectador entra na arena e acumula ficha.

Ate aqui o ``!entrar`` era oco -- o lutador existia no SQLite mas o motor so
resolvia nomes do catalogo JSON, entao ele nunca poderia lutar. Estes testes
fixam a costura que fecha esse buraco e a contabilidade que a torna util.

Tambem travam duas propriedades de desempenho medidas neste projeto, porque as
duas sao visiveis numa transmissao continua: a resolucao de roster nao pode
crescer com a audiencia, e os assets de audio nao podem ser relidos do disco a
cada partida.
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
from neural_fights.live.registry import LiveRegistry
from neural_fights.live.roster import LiveRoster
from neural_fights.live.session import LiveSession
from neural_fights.live.standings import (
    RankedMatchmaker,
    criar_registrador,
    registrar_resultado,
)
from neural_fights.simulation.simulacao import Simulador


class RegistroBase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LiveRegistry(":memory:")
        self.addCleanup(self.registry.close)
        self.roster = LiveRoster(self.registry)

    def _fighter(self, sufixo: str = "1", nome: str = "Ana"):
        viewer = self.registry.registrar_viewer(
            platform="youtube",
            platform_user_id=f"UC-{sufixo}",
            display_name_bruto=nome,
        )
        return self.registry.criar_lutador(viewer)


@contextmanager
def simulador(config, **opcoes):
    with (
        patch.object(pygame.display, "set_mode", side_effect=lambda *a, **k: pygame.Surface(a[0])),
        patch.object(pygame.display, "flip"),
    ):
        sim = Simulador(match_config=config, seed=5, **opcoes)
    try:
        yield sim
    finally:
        sim.close()


class RosterProviderTests(RegistroBase):
    def test_provider_ausente_preserva_o_comportamento_historico(self) -> None:
        nomes = [p.nome for p in database.carregar_personagens()][:2]
        config = {"p1_nome": nomes[0], "p2_nome": nomes[1], "best_of": 1}
        with simulador(config) as sim:
            self.assertIsNone(sim.roster_provider)
            self.assertEqual(sim.p1.dados.nome, nomes[0])

    def test_lutador_de_espectador_entra_na_partida(self) -> None:
        """A propriedade que torna o ``!entrar`` mais que um registro."""
        fighter = self._fighter()
        curado = self.roster.nomes_curados[0]
        config = {"p1_nome": fighter.catalog_name, "p2_nome": curado, "best_of": 1}

        with simulador(config, roster_provider=self.roster) as sim:
            self.assertEqual(sim.p1.dados.nome, fighter.catalog_name)
            self.assertEqual(sim.p2.dados.nome, curado)

    def test_lutador_de_espectador_recebe_a_arma(self) -> None:
        fighter = self._fighter()
        config = {
            "p1_nome": fighter.catalog_name,
            "p2_nome": self.roster.nomes_curados[0],
            "best_of": 1,
        }
        with simulador(config, roster_provider=self.roster) as sim:
            self.assertIsNotNone(sim.p1.dados.arma_obj)
            self.assertEqual(sim.p1.dados.arma_obj.nome, fighter.weapon_name)

    def test_peso_da_arma_e_aplicado_como_no_catalogo_curado(self) -> None:
        """Omitir o peso daria ao espectador atributos impossiveis de obter."""
        fighter = self._fighter()
        personagem = self.roster.resolver(fighter.catalog_name)
        self.assertGreater(personagem.peso_arma, 0.0)
        self.assertAlmostEqual(personagem.peso_arma, personagem.arma_obj.peso, places=6)

    def test_nome_desconhecido_falha_com_a_mesma_mensagem(self) -> None:
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            self.roster.resolver("@nao_existe")
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            self.roster.resolver("Fulano Inexistente")

    def test_roster_sem_registro_so_resolve_o_catalogo(self) -> None:
        roster = LiveRoster(None)
        self.assertEqual(roster.nomes_de_espectadores(), ())
        self.assertTrue(roster.nomes_curados)
        with self.assertRaises(ValueError):
            roster.resolver("@qualquer")


class RosterCacheTests(RegistroBase):
    def test_catalogo_e_lido_uma_vez_e_reusado(self) -> None:
        """Resolucao nao pode crescer com a audiencia: e por partida."""
        roster = LiveRoster(self.registry)  # a leitura acontece na construcao
        curado = roster.nomes_curados[0]

        with (
            patch.object(database, "carregar_personagens") as espiao_chars,
            patch.object(database, "carregar_armas") as espiao_armas,
        ):
            for _ in range(50):
                roster.resolver(curado)

        self.assertEqual(espiao_chars.call_count, 0, "catalogo relido a cada resolucao")
        self.assertEqual(espiao_armas.call_count, 0, "armas relidas a cada resolucao")

    def test_recarregar_catalogo_reabsorve_edicoes(self) -> None:
        roster = LiveRoster(self.registry)
        with patch.object(
            database, "carregar_personagens", wraps=database.carregar_personagens
        ) as espiao:
            roster.recarregar_catalogo()
        self.assertEqual(espiao.call_count, 1)

    def test_espectador_novo_aparece_sem_recarregar_o_catalogo(self) -> None:
        antes = len(self.roster.nomes_de_espectadores())
        self._fighter("novo", "Novato")
        self.assertEqual(len(self.roster.nomes_de_espectadores()), antes + 1)

    def test_todos_os_nomes_junta_os_dois_espacos(self) -> None:
        fighter = self._fighter()
        todos = self.roster.todos_os_nomes()
        self.assertIn(fighter.catalog_name, todos)
        self.assertIn(self.roster.nomes_curados[0], todos)


class AudioCacheTests(unittest.TestCase):
    """A troca de partida reseta o AudioManager; relere do disco custaria ~1s."""

    def setUp(self) -> None:
        from neural_fights.effects.audio import AudioManager

        self.AudioManager = AudioManager
        pygame.init()
        pygame.mixer.init()
        self.addCleanup(AudioManager.descartar_cache)
        self.addCleanup(AudioManager.reset)

    def test_assets_sao_compartilhados_entre_instancias(self) -> None:
        from neural_fights.effects.audio import _CACHE_DE_SONS

        primeira = self.AudioManager.get_instance()
        if not primeira.enabled or not primeira.sounds:
            self.skipTest("audio indisponivel neste ambiente")
        nome = next(iter(primeira.sounds))
        carregados = len(_CACHE_DE_SONS)

        self.AudioManager.reset()
        segunda = self.AudioManager.get_instance()

        self.assertIsNot(segunda, primeira)
        self.assertIs(segunda.sounds[nome], primeira.sounds[nome])
        self.assertEqual(len(_CACHE_DE_SONS), carregados, "asset relido do disco")

    def test_reset_preserva_o_conjunto_de_sons(self) -> None:
        primeira = self.AudioManager.get_instance()
        if not primeira.enabled or not primeira.sounds:
            self.skipTest("audio indisponivel neste ambiente")
        antes = set(primeira.sounds)
        self.AudioManager.reset()
        self.assertEqual(set(self.AudioManager.get_instance().sounds), antes)

    def test_descartar_cache_esvazia(self) -> None:
        from neural_fights.effects.audio import _CACHE_DE_SONS

        self.AudioManager.get_instance()
        self.AudioManager.descartar_cache()
        self.assertEqual(len(_CACHE_DE_SONS), 0)

    def test_cache_e_descartado_ao_fechar_o_simulador(self) -> None:
        """Um ``Sound`` nao sobrevive a ``pygame.mixer.quit()``."""
        from neural_fights.effects import audio as modulo_audio

        nomes = [p.nome for p in database.carregar_personagens()][:2]
        config = {"p1_nome": nomes[0], "p2_nome": nomes[1], "best_of": 1}
        with simulador(config):
            pass
        self.assertEqual(len(modulo_audio._CACHE_DE_SONS), 0)


class ClassificacaoTests(RegistroBase):
    def test_vitoria_e_derrota_sao_contabilizadas(self) -> None:
        a = self._fighter("a", "Ana")
        b = self._fighter("b", "Beto")

        registrar_resultado(self.registry, vencedor=a.catalog_name, perdedor=b.catalog_name)

        self.assertEqual(self.registry.stats_do_lutador(a.fighter_id)["wins"], 1)
        self.assertEqual(self.registry.stats_do_lutador(b.fighter_id)["losses"], 1)

    def test_empate_conta_para_os_dois(self) -> None:
        a = self._fighter("a", "Ana")
        b = self._fighter("b", "Beto")

        registrar_resultado(
            self.registry, vencedor=a.catalog_name, perdedor=b.catalog_name, empate=True
        )

        self.assertEqual(self.registry.stats_do_lutador(a.fighter_id)["draws"], 1)
        self.assertEqual(self.registry.stats_do_lutador(b.fighter_id)["draws"], 1)

    def test_nome_curado_e_ignorado_sem_erro(self) -> None:
        """O roster curado e cenario, nao competidor: nao tem ficha."""
        a = self._fighter("a", "Ana")
        curado = self.roster.nomes_curados[0]

        atualizadas = registrar_resultado(
            self.registry, vencedor=a.catalog_name, perdedor=curado
        )

        self.assertEqual(atualizadas, 1)
        self.assertFalse(self.registry.registrar_resultado_por_catalogo(curado, "vitoria"))

    def test_classificacao_ordena_por_vitorias_e_saldo(self) -> None:
        a = self._fighter("a", "Ana")
        b = self._fighter("b", "Beto")
        c = self._fighter("c", "Caio")

        registrar_resultado(self.registry, vencedor=a.catalog_name, perdedor=c.catalog_name)
        registrar_resultado(self.registry, vencedor=a.catalog_name, perdedor=b.catalog_name)
        registrar_resultado(self.registry, vencedor=b.catalog_name, perdedor=c.catalog_name)

        tabela = self.registry.classificacao(10)
        self.assertEqual([linha["display_name"] for linha in tabela], ["Ana", "Beto", "Caio"])
        self.assertEqual(tabela[0]["saldo"], 2)
        self.assertEqual(tabela[-1]["saldo"], -2)

    def test_lutador_sem_luta_aparece_zerado(self) -> None:
        self._fighter("a", "Ana")
        tabela = self.registry.classificacao(10)
        self.assertEqual(tabela[0]["wins"], 0)
        self.assertEqual(tabela[0]["saldo"], 0)

    def test_aposentado_sai_da_classificacao(self) -> None:
        a = self._fighter("a", "Ana")
        self.registry.aposentar_lutador(a.fighter_id)
        self.assertEqual(self.registry.classificacao(10), [])

    def test_falha_ao_registrar_nao_propaga(self) -> None:
        """Perder a ficha de uma luta nunca pode derrubar a transmissao."""
        with patch.object(
            self.registry,
            "registrar_resultado_por_catalogo",
            side_effect=RuntimeError("banco indisponivel"),
        ):
            with self.assertLogs("neural_fights.live.standings", level="ERROR"):
                atualizadas = registrar_resultado(
                    self.registry, vencedor="@x", perdedor="@y"
                )
        self.assertEqual(atualizadas, 0)


class RankedMatchmakerTests(RegistroBase):
    def test_espectadores_vem_antes_do_catalogo(self) -> None:
        """Quem gastou para entrar precisa aparecer na arena."""
        fighter = self._fighter()
        matchmaker = RankedMatchmaker(self.roster)
        p1, _p2, _cenario = matchmaker.proximo()
        self.assertEqual(p1, fighter.catalog_name)

    def test_catalogo_preenche_quando_nao_ha_espectadores(self) -> None:
        matchmaker = RankedMatchmaker(self.roster)
        p1, p2, _cenario = matchmaker.proximo()
        self.assertIn(p1, self.roster.nomes_curados)
        self.assertIn(p2, self.roster.nomes_curados)

    def test_quem_entra_durante_o_round_luta_no_proximo(self) -> None:
        matchmaker = RankedMatchmaker(self.roster)
        tamanho = len(matchmaker)

        self._fighter("tardio", "Tardio")
        matchmaker.proximo()

        self.assertEqual(len(matchmaker), tamanho + 1)

    def test_limite_de_espectadores_e_respeitado(self) -> None:
        for indice in range(5):
            self._fighter(str(indice), f"V{indice}")
        matchmaker = RankedMatchmaker(self.roster, limite_espectadores=2)
        fila_espectadores = [
            nome for nome in matchmaker._nomes if nome.startswith("@")
        ]
        self.assertEqual(len(fila_espectadores), 2)


class GanchoDeFimDePartidaTests(RegistroBase):
    def _sessao(self, registrador):
        nomes = [p.nome for p in database.carregar_personagens()][:2]
        config = {"p1_nome": nomes[0], "p2_nome": nomes[1], "best_of": 1}
        with (
            patch.object(pygame.display, "set_mode", side_effect=lambda *a, **k: pygame.Surface(a[0])),
            patch.object(pygame.display, "flip"),
        ):
            sim = Simulador(match_config=config, seed=5, roster_provider=self.roster)
        sessao = LiveSession(
            sim,
            RankedMatchmaker(self.roster),
            pausa_entre_partidas=0.0,
            ao_terminar_partida=registrador,
        )
        return sim, sessao

    def test_desfecho_identifica_vencedor_e_perdedor(self) -> None:
        chamadas = []
        sim, sessao = self._sessao(
            lambda _s, v, p, e: chamadas.append((v, p, e))
        )
        try:
            sim.vencedor = sim.p1
            sim.round_finalizado = True
            sessao._registrar_resultado()
        finally:
            sim.close()

        vencedor, perdedor, empate = chamadas[0]
        self.assertEqual(vencedor, sim.p1.dados.nome)
        self.assertEqual(perdedor, sim.p2.dados.nome)
        self.assertFalse(empate)

    def test_sem_vencedor_e_tratado_como_empate(self) -> None:
        chamadas = []
        sim, sessao = self._sessao(
            lambda _s, v, p, e: chamadas.append((v, p, e))
        )
        try:
            sim.vencedor = None
            sessao._registrar_resultado()
        finally:
            sim.close()

        self.assertTrue(chamadas[0][2], "partida sem vencedor deveria ser empate")

    def test_gancho_que_explode_nao_derruba_a_sessao(self) -> None:
        sim, sessao = self._sessao(lambda *_a: 1 / 0)
        try:
            with self.assertLogs("neural_fights.live.session", level="ERROR"):
                sessao._registrar_resultado()
            self.assertEqual(sessao.stats.partidas, 1)
        finally:
            sim.close()

    def test_registrador_grava_no_banco(self) -> None:
        fighter = self._fighter()
        registrador = criar_registrador(self.registry)
        registrador(None, fighter.catalog_name, "Curado Qualquer", False)
        self.assertEqual(self.registry.stats_do_lutador(fighter.fighter_id)["wins"], 1)


if __name__ == "__main__":
    unittest.main()
