# -*- coding: utf-8 -*-
"""O carimbo do dinamismo (21/10/2026) em toda luta nova do canal.

O afastamento do colado longo (neural_fights/core/dinamismo.py) e chave da
LUTA, como a corrente nova: o motor sem o carimbo e o de antes. O canal liga
a chave em toda luta nova (duelo, estreia, torneio) e grava `dinamismo` no
fight.json; quem re-simula uma luta gravada (som-da-luta, palco, A/B)
repassa o carimbo, e luta sem o campo (todas as de antes de 21/10) sai com
False — a mesma luta que foi ao ar.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

P1, P2 = "Lutador Um", "Lutador Dois"


def test_luta_nova_liga_e_luta_antiga_e_false():
    from builds.tournament import runner

    assert runner.chave_dinamismo_padrao() is True
    assert runner.dinamismo_da_luta({"seed": 1}) is False
    assert runner.dinamismo_da_luta({}, {"dinamismo": True}) is True
    assert runner.dinamismo_da_luta({"dinamismo": False}, {"dinamismo": True}) is False


def test_duelo_novo_carimba_no_fight_json_e_em_cada_round():
    from builds.tournament import runner

    bruto = {"vencedor": P1, "duracao": 12.0, "motivo": "knockout", "seed": 7,
             "hp_vencedor": 40.0, "corrente_v2": False}
    chamadas = []

    def falso(*args, **kw):
        chamadas.append(kw.get("dinamismo"))
        return dict(bruto, dinamismo=runner.chave_dinamismo_padrao()
                    if kw.get("dinamismo") is None else kw["dinamismo"])

    fichas = {P1: {"forca": 5, "mana": 5}, P2: {"forca": 5, "mana": 5}}
    with mock.patch.object(runner, "gravar_confronto", side_effect=falso), \
            mock.patch.object(runner, "fichas_do_banco", return_value=fichas), \
            mock.patch.object(runner, "personagens_gerados", return_value=[]):
        from builds.generation.session_generator import load_config
        sessao = runner.FightSession(load_config("scoring.json"))
        fight = sessao.gerar(p1=P1, p2=P2, seed=7, cenario="Arena", gravar_em=Path("x"),
                             melhor_de=3, origem="duelo")
        assert fight["dinamismo"] is True and chamadas and set(chamadas) == {True}
        assert all(r["dinamismo"] is True for r in fight["lutas"])
        chamadas.clear()
        velha = sessao.gerar(p1=P1, p2=P2, seed=7, cenario="Arena", gravar_em=Path("x"),
                             dinamismo=False)
        assert velha["dinamismo"] is False and set(chamadas) == {False}
        assert velha["luta"]["dinamismo"] is False


def test_gravar_confronto_manda_a_chave_ao_gravador_e_devolve_no_bruto(tmp_path):
    from builds.tournament import runner

    pedidos = []

    def gravar(tarefas, **_kw):
        pedidos.extend(t["dinamismo"] for t in tarefas)
        return [{"sucesso": True, "vencedor": P1, "arquivo": str(tmp_path / "x.mp4"),
                 "eventos_dano": [], "serie_hp": [], "eventos_narrativos": [],
                 "duracao_video": 5.0, "ko_em_video": 4.0, "duracao_jogo": 4.0,
                 "dinamismo": t["dinamismo"]} for t in tarefas]

    with mock.patch.object(runner.capture, "gravar_em_paralelo", side_effect=gravar), \
            mock.patch.object(runner.highlights, "planejar_corte_tedio", return_value=[(0.0, 5.0)]), \
            mock.patch.object(runner.highlights, "remapear_gravacao",
                              return_value={"serie_hp": [], "eventos_narrativos": [],
                                            "eventos_dano": [], "ko_em_video": 4.0, "duracao": 5.0}), \
            mock.patch.object(runner.highlights, "extrair", return_value=0.0):
        bruto = runner.gravar_confronto(P1, P2, "Torre", 1, tmp_path, "00", ("celular",))
        assert bruto["dinamismo"] is True
        velho = runner.gravar_confronto(P1, P2, "Torre", 1, tmp_path, "00", ("celular",),
                                        dinamismo=False)
        assert velho["dinamismo"] is False
    assert pedidos == [True, False]


def test_gravador_recebe_o_carimbo_pela_linha_de_comando():
    from builds.tournament import capture

    vistos = []

    def rodar(comando, **_kw):
        vistos.append(comando)
        return SimpleNamespace(stdout='{"sucesso": true}', stderr="", returncode=0)

    with mock.patch.object(capture.subprocess, "run", side_effect=rodar):
        for chave in (None, True, False):
            capture.gravar_uma(p1="a", p2="b", seed=1, saida=None, cenario="Arena", dinamismo=chave)
    assert not any("dinamismo" in a for a in vistos[0])
    assert "--dinamismo" in vistos[1] and "--sem-dinamismo" not in vistos[1]
    assert "--sem-dinamismo" in vistos[2]

    from neural_fights.recording import fight_recorder
    parser = fight_recorder.build_parser()
    base = ["--p1", "a", "--p2", "b", "--sem-video"]
    assert parser.parse_args(base).dinamismo is None
    assert parser.parse_args(base + ["--dinamismo"]).dinamismo is True
    assert parser.parse_args(base + ["--sem-dinamismo"]).dinamismo is False


def test_som_da_luta_resimula_com_o_carimbo_e_antiga_com_false():
    from builds.tournament import som_real

    luta = {"p1": "a", "p2": "b", "seed": 3, "cenario": "Arena", "vencedor": "a", "duracao": 1.0,
            "clipes": {"celular": {"trechos": [[0.0, 1.0]], "resolucao": [1080, 1920]}}}
    pedidos = []

    def gravar(**kw):
        pedidos.append(kw["dinamismo"])
        return {"sucesso": True, "vencedor": "a", "duracao_jogo": 1.0, "sons": [], "eventos_dano": [],
                "duracao_video": 1.0, "ko_em_video": None}

    with mock.patch.object(som_real.capture, "gravar_uma", side_effect=gravar):
        som_real.anotar_luta(dict(luta), {}, "duelo")
        som_real.anotar_luta(dict(luta, dinamismo=True), {}, "duelo")
        som_real.anotar_luta(dict(luta), {}, "duelo", fight={"dinamismo": True})
    assert pedidos == [False, True, True]


def test_palco_resimula_a_luta_gravada_com_o_carimbo():
    from builds.palco import fonte

    vistos = []

    def gravar(**kw):
        vistos.append(kw.get("dinamismo"))
        return {"timeline": {"n": 1, "hz": 60}, "resultado": {"empate": False}}

    with mock.patch("neural_fights.recording.timeline.gravar_timeline", side_effect=gravar):
        fonte.timeline_da_luta(p1="a", p2="b", seed=1, cenario="Arena", tentativas=1)
        fonte.timeline_da_luta(p1="a", p2="b", seed=1, cenario="Arena", tentativas=1, dinamismo=False)
        fonte.timeline_da_luta(p1="a", p2="b", seed=1, cenario="Arena", tentativas=1, dinamismo=True)
    assert vistos == [None, False, True]
