"""Regressoes da ponte entre o simulador manual e o palco."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from neural_fights.recording import timeline_arquivo
from neural_fights.simulation.manual import exportar_timeline_do_manual


def test_exportacao_manual_grava_a_mesma_timeline_da_producao(tmp_path):
    documento_da_producao = {
        "formato": "neural-fights/timeline",
        "seed": 9182,
        "resultado": {"vencedor": "Astra"},
    }
    simulador = SimpleNamespace(
        p1=SimpleNamespace(dados=SimpleNamespace(nome="Astra")),
        p2=SimpleNamespace(dados=SimpleNamespace(nome="Bram")),
        seed=9182,
        match_config={"cenario": "Arena"},
        corrente_v2=False,
    )
    destino = Path(tmp_path) / "manual.gcpf"

    with patch(
        "random_builds.builds.palco.fonte.timeline_da_luta",
        return_value=(documento_da_producao, 9182),
    ) as producao:
        arquivo, exportada = exportar_timeline_do_manual(simulador, destino)

    producao.assert_called_once_with(
        p1="Astra", p2="Bram", seed=9182, cenario="Arena", tentativas=1,
        corrente_v2=False,
    )
    assert arquivo == destino
    assert exportada == documento_da_producao
    assert timeline_arquivo.carregar(arquivo) == documento_da_producao


def test_exportacao_manual_tem_o_mesmo_resultado_da_producao(tmp_path):
    """A exportacao nao pode trocar seed, lutadores ou o resultado da luta."""
    from neural_fights.data import database
    simulador = SimpleNamespace(
        p1=SimpleNamespace(dados=SimpleNamespace(nome=database.carregar_personagens()[0].nome)),
        p2=SimpleNamespace(dados=SimpleNamespace(nome=database.carregar_personagens()[1].nome)),
        seed=9182,
        match_config={"cenario": "Arena"},
        corrente_v2=False,
    )
    from random_builds.builds.palco import fonte

    arquivo, manual = exportar_timeline_do_manual(simulador, Path(tmp_path) / "manual.gcpf")
    producao, seed_usada = fonte.timeline_da_luta(
        p1=simulador.p1.dados.nome, p2=simulador.p2.dados.nome, seed=9182, cenario="Arena",
        tentativas=1, corrente_v2=False,
    )

    assert seed_usada == 9182
    assert timeline_arquivo.carregar(arquivo) == producao == manual
    assert manual["resultado"] == producao["resultado"]
