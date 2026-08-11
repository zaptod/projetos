"""Contratos de dados, geracao e persistencia coerente."""

from __future__ import annotations

import io
import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ai.personalities import PERSONALIDADES_PRESETS
from core.skills import SKILL_DB
from data import database
from tools import gerador_database
from tournament.tournament_mode import Tournament, TournamentState


def arma_valida(nome="Arma de teste"):
    return {
        "nome": nome,
        "tipo": "Reta",
        "dano": 10.0,
        "peso": 2.0,
        "comp_cabo": 20.0,
        "comp_lamina": 50.0,
        "largura": 5.0,
        "raridade": "Comum",
        "habilidade": "Bola de Fogo",
        "habilidades": ["Bola de Fogo"],
    }


def personagem_valido(nome="Ada", nome_arma="Arma de teste"):
    return {
        "nome": nome,
        "tamanho": 1.8,
        "forca": 6.0,
        "mana": 5.0,
        "nome_arma": nome_arma,
        "classe": "Guerreiro (Força Bruta)",
        "personalidade": "Tático",
    }


class DataContractTests(unittest.TestCase):
    def test_json_corrompido_nao_e_convertido_em_lista_vazia(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "corrompido.json"
            path.write_text('{"incompleto":', encoding="utf-8")

            with self.assertRaises(database.DataValidationError) as raised:
                database.carregar_json(str(path))

        self.assertIn("linha", str(raised.exception))
        self.assertIn(str(path), str(raised.exception))

    def test_referencias_e_nomes_invalidos_sao_relacionados(self):
        armas = [arma_valida(), arma_valida()]
        armas[0]["habilidades"] = ["Skill que nao existe"]
        personagens = [personagem_valido(nome_arma="arma ausente")]
        personagens[0]["personalidade"] = "Personalidade inventada"

        with self.assertRaises(database.DataValidationError) as raised:
            database.validar_database(armas, personagens)

        mensagem = str(raised.exception)
        self.assertIn("nome de arma duplicado", mensagem)
        self.assertIn("Skill que nao existe", mensagem)

        # A validacao de personagens e independente da validacao de armas, de
        # modo que seus erros tambem podem ser apresentados com contexto.
        with self.assertRaises(database.DataValidationError) as raised:
            database.validar_personagens(
                personagens,
                nomes_armas={"Arma de teste"},
                personalidades_validas=set(PERSONALIDADES_PRESETS),
            )
        self.assertIn("nome_arma inexistente", str(raised.exception))
        self.assertIn("personalidade inexistente", str(raised.exception))

    def test_catalogos_publicos_do_gerador_sao_os_canonicos(self):
        self.assertEqual(set(SKILL_DB) - {"Nenhuma"}, set(gerador_database.TODAS_SKILLS))
        self.assertEqual(
            set(PERSONALIDADES_PRESETS),
            set(gerador_database.LISTA_PERSONALIDADES),
        )

    def test_gerador_completo_entrega_quantidade_exata_e_referencias_validas(self):
        random.seed(12345)
        with redirect_stdout(io.StringIO()):
            armas, personagens = gerador_database.gerar_database_completa(
                16, "representativa"
            )

        self.assertEqual(16, len(personagens))
        self.assertEqual(len(armas), len({arma["nome"] for arma in armas}))
        self.assertEqual(
            len(personagens), len({personagem["nome"] for personagem in personagens})
        )
        self.assertFalse(
            any("resistencia" in personagem or "agilidade" in personagem for personagem in personagens)
        )
        database.validar_database(armas, personagens)

    def test_transacao_de_dois_jsons_reverte_primeiro_replace_se_segundo_falhar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            armas_path = Path(temp_dir) / "armas.json"
            chars_path = Path(temp_dir) / "personagens.json"
            armas_path.write_text(json.dumps([{"versao": "anterior"}]), encoding="utf-8")
            chars_path.write_text(json.dumps([{"versao": "anterior"}]), encoding="utf-8")
            replace_real = os.replace

            def replace_com_falha(origem, destino):
                if Path(destino) == chars_path and str(origem).endswith(".tmp"):
                    raise OSError("falha simulada no segundo replace")
                return replace_real(origem, destino)

            with patch.object(database.os, "replace", side_effect=replace_com_falha):
                with self.assertRaises(OSError):
                    database.salvar_jsons_coerentes(
                        {
                            str(armas_path): [{"versao": "nova"}],
                            str(chars_path): [{"versao": "nova"}],
                        }
                    )

            self.assertEqual([{"versao": "anterior"}], json.loads(armas_path.read_text("utf-8")))
            self.assertEqual([{"versao": "anterior"}], json.loads(chars_path.read_text("utf-8")))
            self.assertEqual([], list(Path(temp_dir).glob("*.tmp")))
            self.assertEqual([], list(Path(temp_dir).glob("*.bak")))

    def test_match_config_pode_ser_isolado_por_variavel_de_ambiente(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "processo" / "match.json"
            with patch.dict(os.environ, {database.MATCH_CONFIG_ENV: str(path)}):
                resolved = database.salvar_match_config(
                    {"p1_nome": "Ada", "p2_nome": "Grace"},
                    preservar_existente=False,
                )
                loaded = database.carregar_match_config()

            self.assertEqual(str(path.resolve()), resolved)
            self.assertEqual({"p1_nome": "Ada", "p2_nome": "Grace"}, loaded)

    def test_rename_de_arma_atualiza_personagens_na_mesma_transacao(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            armas_path = Path(temp_dir) / "armas.json"
            chars_path = Path(temp_dir) / "personagens.json"
            database.salvar_database(
                [arma_valida()],
                [personagem_valido()],
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )

            afetados = database.renomear_arma(
                "Arma de teste",
                "Arma renomeada",
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )

            armas, personagens = database.carregar_database(
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )
            self.assertEqual(1, afetados)
            self.assertEqual("Arma renomeada", armas[0]["nome"])
            self.assertEqual("Arma renomeada", personagens[0]["nome_arma"])

    def test_edicao_de_arma_atualiza_campos_e_referencias_na_mesma_transacao(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            armas_path = Path(temp_dir) / "armas.json"
            chars_path = Path(temp_dir) / "personagens.json"
            database.salvar_database(
                [arma_valida()],
                [personagem_valido()],
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )
            atualizada = arma_valida("Arma revisada")
            atualizada["dano"] = 37.0

            afetados = database.atualizar_arma(
                "Arma de teste",
                atualizada,
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )

            armas, personagens = database.carregar_database(
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )
            self.assertEqual(1, afetados)
            self.assertEqual("Arma revisada", armas[0]["nome"])
            self.assertEqual(37.0, armas[0]["dano"])
            self.assertEqual("Arma revisada", personagens[0]["nome_arma"])

    def test_remocao_de_arma_referenciada_exige_substituta(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            armas_path = Path(temp_dir) / "armas.json"
            chars_path = Path(temp_dir) / "personagens.json"
            database.salvar_database(
                [arma_valida(), arma_valida("Reserva")],
                [personagem_valido()],
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )

            with self.assertRaises(database.DataValidationError):
                database.remover_arma(
                    "Arma de teste",
                    arquivo_armas=str(armas_path),
                    arquivo_personagens=str(chars_path),
                )

            afetados = database.remover_arma(
                "Arma de teste",
                substituir_por="Reserva",
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )
            armas, personagens = database.carregar_database(
                arquivo_armas=str(armas_path),
                arquivo_personagens=str(chars_path),
            )
            self.assertEqual(1, afetados)
            self.assertEqual(["Reserva"], [arma["nome"] for arma in armas])
            self.assertEqual("Reserva", personagens[0]["nome_arma"])

    def test_fixture_e_usado_sem_criar_estado_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir) / "runtime" / "match.json"
            fixture = Path(temp_dir) / "fixture.json"
            fixture.write_text(json.dumps({"best_of": 3}), encoding="utf-8")
            with (
                patch.object(database, "ARQUIVO_MATCH", str(runtime)),
                patch.object(database, "ARQUIVO_MATCH_DEFAULT", str(fixture)),
                patch.dict(os.environ, {}, clear=True),
            ):
                self.assertEqual({"best_of": 3}, database.carregar_match_config())
            self.assertFalse(runtime.exists())


class TournamentStateContractTests(unittest.TestCase):
    def test_save_invalido_nao_muda_estado_em_memoria(self):
        tournament = Tournament("Original")
        tournament.participants = ["A", "B"]
        tournament.state = TournamentState.WAITING
        snapshot = (
            tournament.name,
            list(tournament.participants),
            tournament.state,
            tournament.bracket,
        )
        invalido = {
            "name": "Corrompido",
            "participants": ["Duplicado", "Duplicado"],
            "state": "finished",
            "champion": "Duplicado",
            "current_round": 0,
            "current_match": 0,
            "stats": {},
            "bracket": [],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text(json.dumps(invalido), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertFalse(tournament.load_state(str(path)))

        self.assertEqual(snapshot[0], tournament.name)
        self.assertEqual(snapshot[1], tournament.participants)
        self.assertEqual(snapshot[2], tournament.state)
        self.assertIs(snapshot[3], tournament.bracket)


if __name__ == "__main__":
    unittest.main()
