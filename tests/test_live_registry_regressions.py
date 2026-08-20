"""Regressoes do registro de espectadores e do comando ``!entrar``.

Tres propriedades sustentam o resto da camada de live:

* **idempotencia** -- reconexao reentrega eventos ja lidos, e reprocessar um
  evento pago cobraria a pessoa duas vezes;
* **isolamento do RNG** -- gerar um lutador nao pode perturbar o stream global
  que o ``Simulador`` semeia para reproduzir partidas;
* **separacao de espacos de nome** -- o lutador de espectador nunca colide com o
  roster curado nem entra no catalogo JSON empacotado.
"""

from __future__ import annotations

import json
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from neural_fights.data import database
from neural_fights.live.commands import (
    STATUS_APLICADO,
    STATUS_DUPLICADO,
    STATUS_IGNORADO,
    CommandRouter,
    criar_handler,
    extrair_comando,
)
from neural_fights.live.events import EventKind, ViewerEvent
from neural_fights.live.identity import eh_lutador_de_espectador
from neural_fights.live.registry import (
    LiveRegistry,
    fighter_id_de,
    viewer_id_de,
)


def evento(**overrides) -> ViewerEvent:
    base = {
        "platform": "youtube",
        "viewer_id": "UC-ana",
        "viewer_name": "Ana",
        "kind": EventKind.CHAT,
        "text": "!entrar",
    }
    base.update(overrides)
    return ViewerEvent(**base)


class RegistryBase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LiveRegistry(":memory:")
        self.addCleanup(self.registry.close)

    def _viewer(self, user_id: str = "UC-ana", nome: str = "Ana"):
        return self.registry.registrar_viewer(
            platform="youtube",
            platform_user_id=user_id,
            display_name_bruto=nome,
        )


class IdentidadeTests(RegistryBase):
    def test_viewer_id_e_estavel_e_separa_plataformas(self) -> None:
        self.assertEqual(viewer_id_de("youtube", "UC-1"), viewer_id_de("youtube", "UC-1"))
        self.assertNotEqual(viewer_id_de("youtube", "UC-1"), viewer_id_de("tiktok", "UC-1"))

    def test_viewer_id_ignora_caixa_da_plataforma(self) -> None:
        self.assertEqual(viewer_id_de("YouTube", "UC-1"), viewer_id_de("youtube", "UC-1"))

    def test_viewer_id_exige_identidade(self) -> None:
        for platform, user in (("", "UC-1"), ("youtube", ""), ("youtube", "  ")):
            with self.subTest(platform=platform, user=user):
                with self.assertRaises(ValueError):
                    viewer_id_de(platform, user)

    def test_registrar_e_idempotente_por_identidade(self) -> None:
        primeiro = self._viewer()
        segundo = self._viewer()
        self.assertEqual(primeiro.viewer_id, segundo.viewer_id)

    def test_renome_atualiza_exibicao_sem_trocar_identidade(self) -> None:
        antes = self._viewer(nome="Ana")
        depois = self._viewer(nome="Ana Nova")
        self.assertEqual(antes.viewer_id, depois.viewer_id)
        self.assertEqual(depois.display_name, "Ana Nova")

    def test_nome_abusivo_e_sanitizado_na_entrada(self) -> None:
        viewer = self._viewer(nome="Ana​‮Clara")
        self.assertNotIn("​", viewer.display_name)
        self.assertNotIn("‮", viewer.display_name)


class LutadorTests(RegistryBase):
    def test_entrar_cria_um_lutador_valido(self) -> None:
        fighter = self.registry.criar_lutador(self._viewer())
        self.assertTrue(eh_lutador_de_espectador(fighter.catalog_name))
        self.assertEqual(fighter.spec["nome"], fighter.catalog_name)
        self.assertIn("classe", fighter.spec)
        self.assertTrue(fighter.weapon_name)

    def test_arma_referenciada_existe_no_catalogo(self) -> None:
        fighter = self.registry.criar_lutador(self._viewer())
        nomes = {arma.nome for arma in database.carregar_armas()}
        self.assertIn(fighter.weapon_name, nomes)

    def test_criar_duas_vezes_devolve_o_mesmo_lutador(self) -> None:
        viewer = self._viewer()
        primeiro = self.registry.criar_lutador(viewer)
        segundo = self.registry.criar_lutador(viewer)
        self.assertEqual(primeiro.fighter_id, segundo.fighter_id)
        self.assertEqual(len(self.registry.listar_lutadores_ativos()), 1)

    def test_geracao_e_deterministica_por_espectador(self) -> None:
        """O mesmo espectador recebe sempre o mesmo lutador."""
        with LiveRegistry(":memory:") as outro:
            viewer_a = self._viewer()
            viewer_b = outro.registrar_viewer(
                platform="youtube", platform_user_id="UC-ana", display_name_bruto="Ana"
            )
            spec_a = self.registry.criar_lutador(viewer_a).spec
            spec_b = outro.criar_lutador(viewer_b).spec
        self.assertEqual(spec_a, spec_b)

    def test_espectadores_diferentes_recebem_lutadores_diferentes(self) -> None:
        a = self.registry.criar_lutador(self._viewer("UC-ana", "Ana"))
        b = self.registry.criar_lutador(self._viewer("UC-beto", "Beto"))
        self.assertNotEqual(a.catalog_name, b.catalog_name)
        self.assertNotEqual(a.fighter_id, b.fighter_id)

    def test_geracao_nao_perturba_o_rng_global_do_jogo(self) -> None:
        """O Simulador semeia o mesmo stream para reproduzir partidas."""
        random.seed(4242)
        esperado = [random.random() for _ in range(5)]

        random.seed(4242)
        self.registry.criar_lutador(self._viewer())
        obtido = [random.random() for _ in range(5)]

        self.assertEqual(esperado, obtido)

    def test_espectador_banido_nao_ganha_lutador(self) -> None:
        viewer = self._viewer()
        self.registry.definir_banimento(viewer.viewer_id, True)
        banido = self.registry.obter_viewer(viewer.viewer_id)
        with self.assertRaises(PermissionError):
            self.registry.criar_lutador(banido)

    def test_aposentar_libera_a_vaga_de_lutador_ativo(self) -> None:
        viewer = self._viewer()
        primeiro = self.registry.criar_lutador(viewer)
        self.assertTrue(self.registry.aposentar_lutador(primeiro.fighter_id))
        self.assertIsNone(self.registry.obter_lutador_ativo(viewer.viewer_id))
        self.assertFalse(self.registry.aposentar_lutador(primeiro.fighter_id))

    def test_um_lutador_ativo_por_espectador_e_garantido_pelo_banco(self) -> None:
        viewer = self._viewer()
        self.registry.criar_lutador(viewer)
        with self.assertRaises(sqlite3.IntegrityError):
            self.registry._conexao.execute(
                """
                INSERT INTO fighter (fighter_id, viewer_id, catalog_name, display_name,
                                     spec_json, weapon_name, created_at)
                VALUES ('outro', ?, '@outro', 'X', '{}', 'arma', 0)
                """,
                (viewer.viewer_id,),
            )

    def test_busca_por_nome_de_catalogo(self) -> None:
        fighter = self.registry.criar_lutador(self._viewer())
        achado = self.registry.obter_lutador_por_catalogo(fighter.catalog_name)
        self.assertEqual(achado.fighter_id, fighter.fighter_id)


class CatalogoIntactoTests(RegistryBase):
    def test_entrar_nao_escreve_no_catalogo_json(self) -> None:
        """O JSON empacotado e curado; conteudo de espectador nao vai nele."""
        caminho = Path(database.ARQUIVO_CHARS)
        antes = caminho.read_bytes()
        self.registry.criar_lutador(self._viewer())
        self.assertEqual(caminho.read_bytes(), antes)

    def test_registro_vive_em_arquivo_proprio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "sub" / "live.sqlite3"
            with LiveRegistry(caminho) as reg:
                reg.criar_lutador(
                    reg.registrar_viewer(
                        platform="youtube",
                        platform_user_id="UC-x",
                        display_name_bruto="X",
                    )
                )
            self.assertTrue(caminho.is_file())


class EstatisticaTests(RegistryBase):
    def test_resultados_sao_acumulados(self) -> None:
        fighter = self.registry.criar_lutador(self._viewer())
        self.registry.registrar_resultado(fighter.fighter_id, "vitoria")
        self.registry.registrar_resultado(fighter.fighter_id, "vitoria")
        self.registry.registrar_resultado(fighter.fighter_id, "derrota")
        self.registry.registrar_resultado(fighter.fighter_id, "empate")
        self.assertEqual(
            self.registry.stats_do_lutador(fighter.fighter_id),
            {"wins": 2, "losses": 1, "draws": 1},
        )

    def test_lutador_sem_historico_tem_zeros(self) -> None:
        self.assertEqual(
            self.registry.stats_do_lutador("inexistente"),
            {"wins": 0, "losses": 0, "draws": 0},
        )

    def test_resultado_desconhecido_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.registrar_resultado("x", "quase_ganhou")


class BlocklistTests(RegistryBase):
    def test_termo_bloqueado_derruba_o_nome_para_o_handle(self) -> None:
        self.registry.bloquear_termo("Golpista")
        viewer = self._viewer(nome="Ana Golpista")
        self.assertNotIn("golpista", viewer.display_name.casefold())

    def test_blocklist_e_editavel_durante_a_transmissao(self) -> None:
        antes = self._viewer(nome="Ana Xyz").display_name
        self.assertEqual(antes, "Ana Xyz")
        self.registry.bloquear_termo("xyz")
        depois = self._viewer(nome="Ana Xyz").display_name
        self.assertNotEqual(depois, "Ana Xyz")

    def test_termo_vazio_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.bloquear_termo("   ")


class ComandoTests(RegistryBase):
    def setUp(self) -> None:
        super().setUp()
        self.router = CommandRouter(self.registry)

    def test_parser_separa_verbo_e_argumentos(self) -> None:
        self.assertEqual(extrair_comando("!entrar"), ("entrar", ()))
        self.assertEqual(extrair_comando("!ARENA Vulcao"), ("arena", ("Vulcao",)))
        self.assertEqual(extrair_comando("  !entrar  "), ("entrar", ()))

    def test_conversa_nao_e_comando(self) -> None:
        for texto in ("boa luta!", "", "!", "   "):
            with self.subTest(texto=texto):
                self.assertEqual(extrair_comando(texto), ("", ()))

    def test_entrar_registra_espectador_e_lutador(self) -> None:
        resultado = self.router.processar(evento())
        self.assertTrue(resultado)
        self.assertEqual(resultado.status, STATUS_APLICADO)
        self.assertIsNotNone(resultado.fighter)
        self.assertEqual(len(self.registry.listar_lutadores_ativos()), 1)

    def test_evento_repetido_e_recusado_por_idempotencia(self) -> None:
        """Reconexao reentrega o que ja foi lido."""
        alvo = evento(event_id="LCC.1")
        self.assertTrue(self.router.processar(alvo))
        repetido = self.router.processar(alvo)
        self.assertFalse(repetido)
        self.assertEqual(repetido.status, STATUS_DUPLICADO)
        self.assertEqual(len(self.registry.listar_lutadores_ativos()), 1)

    def test_entrar_duas_vezes_com_eventos_distintos_nao_duplica_lutador(self) -> None:
        self.router.processar(evento(event_id="LCC.1"))
        segundo = self.router.processar(evento(event_id="LCC.2"))
        self.assertTrue(segundo)
        self.assertEqual(segundo.detalhe, "ja_registrado")
        self.assertEqual(len(self.registry.listar_lutadores_ativos()), 1)

    def test_conversa_e_ignorada_mas_journalizada(self) -> None:
        resultado = self.router.processar(evento(text="boa luta!", event_id="LCC.9"))
        self.assertFalse(resultado)
        self.assertEqual(resultado.status, STATUS_IGNORADO)
        self.assertEqual(self.registry.status_do_evento("LCC.9")[0], STATUS_IGNORADO)

    def test_verbo_desconhecido_e_ignorado_com_detalhe(self) -> None:
        resultado = self.router.processar(evento(text="!explodir", event_id="LCC.8"))
        self.assertEqual(resultado.status, STATUS_IGNORADO)
        self.assertIn("explodir", resultado.detalhe)

    def test_gift_sem_comando_no_texto_e_ignorado(self) -> None:
        """Presente sem instrucao nao vira efeito; o valor sozinho nao comanda."""
        resultado = self.router.processar(
            evento(kind=EventKind.GIFT, text="obrigado!", value_units=100, event_id="LCC.7")
        )
        self.assertFalse(resultado)
        self.assertEqual(resultado.status, STATUS_IGNORADO)

    def test_comando_vale_em_qualquer_tipo_de_evento(self) -> None:
        """Um superchat com ``!entrar`` conta tanto quanto uma mensagem comum."""
        resultado = self.router.processar(
            evento(kind=EventKind.SUPERCHAT, value_units=100, event_id="LCC.6")
        )
        self.assertTrue(resultado)
        self.assertEqual(resultado.status, STATUS_APLICADO)

    def test_desfecho_de_todo_evento_fica_no_journal(self) -> None:
        self.router.processar(evento(event_id="LCC.5"))
        status, detalhe = self.registry.status_do_evento("LCC.5")
        self.assertEqual(status, STATUS_APLICADO)
        self.assertTrue(detalhe)

    def test_handler_adapta_a_assinatura_da_sessao(self) -> None:
        handler = criar_handler(self.registry)
        self.assertTrue(handler(None, evento()))
        self.assertEqual(len(self.registry.listar_lutadores_ativos()), 1)


class SpecTests(RegistryBase):
    def test_spec_persistida_faz_round_trip(self) -> None:
        fighter = self.registry.criar_lutador(self._viewer())
        recarregado = self.registry.obter_lutador_por_catalogo(fighter.catalog_name)
        self.assertEqual(recarregado.spec, fighter.spec)
        self.assertEqual(json.loads(json.dumps(fighter.spec)), fighter.spec)

    def test_spec_passa_no_validador_do_projeto(self) -> None:
        """Reusa o mesmo validador da persistencia principal."""
        fighter = self.registry.criar_lutador(self._viewer())
        nomes = {arma.nome for arma in database.carregar_armas()}
        database.validar_personagens([fighter.spec], nomes_armas=nomes)

    def test_fighter_id_e_deterministico(self) -> None:
        self.assertEqual(fighter_id_de("v1"), fighter_id_de("v1"))
        self.assertNotEqual(fighter_id_de("v1"), fighter_id_de("v2"))
        self.assertNotEqual(fighter_id_de("v1", 0), fighter_id_de("v1", 1))


if __name__ == "__main__":
    unittest.main()
