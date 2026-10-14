"""O "Gerar Roster" do torneio grava num catalogo so dele; o banco fica intocado.

Decisao do Adrian de 14/10/2026 (Grimorio `builds/gerar-roster-do-torneio`:
"Gravar num catalogo so do torneio"). Ate aqui o botao gravava os 64
gerados POR CIMA de personagens.json/armas.json, sem confirmacao — a mesma
troca do banco inteiro que levou os personagens de agosto em 02/09/2026.

O contrato:
1. depois do "Gerar Roster", armas.json e personagens.json do banco ficam
   iguais byte a byte, e nenhuma copia de seguranca nasce la (nada saiu);
2. o roster vai para ``<runtime>/torneio/``;
3. o torneio le os participantes desse catalogo e o motor monta os lutadores
   dele (eles nao existem no banco).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from neural_fights.data import database
from neural_fights.tournament import tournament_mode
from neural_fights.tournament.tournament_mode import (
    Tournament,
    TournamentMatch,
    TournamentRunner,
)

PACOTE = Path(database.DATA_DIR)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    shutil.copyfile(PACOTE / "armas.json", tmp_path / "armas.json")
    shutil.copyfile(PACOTE / "personagens.json", tmp_path / "personagens.json")
    monkeypatch.setenv(database.RUNTIME_DATA_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(database, "ARQUIVO_ARMAS_RUNTIME", str(tmp_path / "armas.json"))
    monkeypatch.setattr(database, "ARQUIVO_CHARS_RUNTIME", str(tmp_path / "personagens.json"))
    return tmp_path


def _apertar_gerar_roster():
    """O botao de verdade (TournamentWindow.generate_roster), sem abrir janela."""
    from neural_fights.ui import view_torneio

    janela = object.__new__(view_torneio.TournamentWindow)
    janela.status_label = SimpleNamespace(configure=lambda **_: None)
    janela.update = lambda: None
    janela.new_tournament = lambda: None
    with patch.object(view_torneio.messagebox, "showerror") as erro:
        janela.generate_roster()
    erro.assert_not_called()


def test_gerar_roster_deixa_o_banco_principal_byte_a_byte_igual(runtime):
    armas_antes = (runtime / "armas.json").read_bytes()
    chars_antes = (runtime / "personagens.json").read_bytes()

    _apertar_gerar_roster()

    assert (runtime / "armas.json").read_bytes() == armas_antes
    assert (runtime / "personagens.json").read_bytes() == chars_antes
    assert not [d for d in runtime.iterdir() if d.name.startswith("_backup-")]

    roster = json.loads((runtime / "torneio" / "personagens.json").read_text("utf-8"))
    assert len(roster) == 64
    armas_torneio = json.loads((runtime / "torneio" / "armas.json").read_text("utf-8"))
    assert {p["nome_arma"] for p in roster} <= {a["nome"] for a in armas_torneio}


def test_o_torneio_le_os_participantes_do_catalogo_proprio(runtime):
    _apertar_gerar_roster()
    roster = {p["nome"] for p in
              json.loads((runtime / "torneio" / "personagens.json").read_text("utf-8"))}

    torneio = Tournament()
    assert torneio.load_participants_from_database(max_participants=64) >= 2
    reais = [n for n in torneio.participants if n in roster or n.startswith("BYE")]
    assert reais == torneio.participants


def test_sem_catalogo_do_torneio_le_o_banco_sem_gravar(runtime):
    banco = {p["nome"] for p in json.loads((runtime / "personagens.json").read_text("utf-8"))}
    antes = (runtime / "personagens.json").read_bytes()
    torneio = Tournament()
    assert torneio.load_participants_from_database(max_participants=8) >= 2
    assert set(torneio.participants) - {n for n in torneio.participants if n.startswith("BYE")} <= banco
    assert (runtime / "personagens.json").read_bytes() == antes


def test_a_luta_monta_os_lutadores_do_catalogo_do_torneio(runtime):
    _apertar_gerar_roster()
    # O gerador sorteia do mesmo repertorio de nomes do banco empacotado, entao
    # um nome pode coincidir. Os dois lutadores ganham nome que o banco NAO tem,
    # para a prova nao depender do sorteio.
    catalogo = tournament_mode.catalogo_do_torneio()
    armas, roster = database.carregar_database(**catalogo)
    roster[0]["nome"], roster[1]["nome"] = "So No Torneio Um", "So No Torneio Dois"
    database.salvar_database(armas, roster, **catalogo)
    p1, p2 = roster[0]["nome"], roster[1]["nome"]
    banco = {p["nome"] for p in json.loads((runtime / "personagens.json").read_text("utf-8"))}
    assert p1 not in banco and p2 not in banco, "o lutador do roster nao pode depender do banco"

    vistos = {}

    def motor(config, **kwargs):
        provedor = kwargs["roster_provider"]
        vistos["p1"] = provedor(config["p1_nome"])
        vistos["p2"] = provedor(config["p2_nome"])
        return SimpleNamespace(
            success=True, winner=config["p1_nome"], reason="knockout",
            duration=12.0, frames=720, seed=kwargs["seed"], error=None,
            p1_hp=10.0, p2_hp=0.0, p1_hp_ratio=0.1, p2_hp_ratio=0.0,
            to_dict=lambda: {},
        )

    with patch("neural_fights.simulation.headless.run_headless_match", side_effect=motor):
        resultado = TournamentRunner(Tournament()).run_single_match(
            TournamentMatch(1, 1, p1, p2)
        )

    assert resultado["success"], resultado
    assert vistos["p1"].nome == p1 and vistos["p2"].nome == p2
    assert vistos["p1"].arma_obj is not None
    assert vistos["p1"].arma_obj.nome == roster[0]["nome_arma"]


def test_catalogo_do_torneio_mora_no_runtime(runtime):
    assert tournament_mode.catalogo_do_torneio() is None
    armas, chars = tournament_mode.caminhos_catalogo_torneio()
    assert Path(armas).parent == runtime / "torneio"
    assert Path(chars).parent == runtime / "torneio"
