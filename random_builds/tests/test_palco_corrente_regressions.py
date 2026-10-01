# -*- coding: utf-8 -*-
"""Corrente nova no palco (rework de 01/10/2026, F2 + F3).

F2: a timeline revisao 4 leva a BOLA do motor (`bola_x/bola_y/bola_vx/bola_vy`
por lutador com corrente e o cabecalho `arma.corrente`), e toda luta nova
carimba `corrente_v2` no fight.json; quem re-simula (som-da-luta, palco, A/B)
repassa o carimbo, e luta sem o campo e a corrente ANTIGA.

F3: a peca `armas/tipos/corrente` reintegra a corrente a cada quadro, sem
estado. A paridade Python x Godot confere que o palco le os mesmos numeros
que o Python escreveu (canais interpolados, mao, bola) e que a corrente que
ele desenha tem as pontas presas na mao e na bola e nunca passa do
comprimento. Os testes de Godot pulam com motivo quando ele nao esta na
maquina.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from builds.palco import config, godot

GODOT = config.godot_disponivel()
precisa_godot = pytest.mark.skipif(GODOT is None, reason="Godot nao encontrado (config/palco.json ou NF_GODOT)")

# Mangual x Chicote do banco de fixture (as duas familias): a mesma luta dos
# testes da corrente V2 no neural_fights.
P1, P2, SEED = "Octavia o Lendário", "Nyx a Impiedosa", 30010


@lru_cache(maxsize=None)
def _timeline(corrente_v2: bool | None, segundos: float = 8.0) -> dict:
    from neural_fights.recording import timeline
    from neural_fights.tools import qualidade_luta as ql

    saida = timeline.gravar_timeline(
        p1=P1, p2=P2, seed=SEED, cenario="Arena", resolucao=(540, 960),
        roster_provider=ql.FonteDeDados("engine").provider(), corrente_v2=corrente_v2,
        max_duracao=segundos)
    return saida["timeline"]


def _mao(canais: dict, cab: dict, k: int) -> tuple[float, float]:
    """A mao da corrente pelos canais (a conta de `corrente.mao`)."""
    raio = float(cab["raio_corpo"])
    mao = cab["arma"]["corrente"]["mao"]
    a = math.radians(canais["ang"][k])
    x = canais["x"][k] + math.cos(a) * raio * mao["avanco_r"] + math.cos(a + math.pi / 2) * raio * mao["lateral_r"]
    y = canais["y"][k] + math.sin(a) * raio * mao["avanco_r"] + math.sin(a + math.pi / 2) * raio * mao["lateral_r"]
    return x, y - canais["z"][k]


# ------------------------------------------------------------ F2: a timeline
def test_revisao_4_leva_a_bola_de_quem_tem_corrente():
    from neural_fights.recording import timeline_arquivo

    doc = _timeline(True)
    assert doc["revisao"] == 4 and doc["luta"]["corrente_v2"] is True
    assert timeline_arquivo.validar(doc) == []
    for cab in doc["lutadores"]:
        corr = cab["arma"]["corrente"]
        assert corr["comp_m"] > 0 and corr["n_elos"] >= 8 and corr["cabeca"]
        canais = doc["trilhas"]["lutadores"][cab["slot"]]
        for nome in ("bola_x", "bola_y", "bola_vx", "bola_vy"):
            assert len(canais[nome]) == doc["n"], nome
    estilos = {c["arma"]["estilo"]: c["arma"]["corrente"] for c in doc["lutadores"]}
    assert estilos["Mangual"]["familia"] == "pesada" and estilos["Mangual"]["cabeca"] == "bola_espinhos"
    assert estilos["Chicote"]["familia"] == "leve" and estilos["Chicote"]["material"] == "couro"


def test_a_bola_fica_presa_a_mao_que_o_palco_calcula():
    """A mao do palco (x, y, ang + `arma.corrente.mao`) e a do motor: a bola
    nunca fica mais longe dela que o comprimento da corrente."""
    doc = _timeline(True)
    for cab in doc["lutadores"]:
        canais = doc["trilhas"]["lutadores"][cab["slot"]]
        comp = cab["arma"]["corrente"]["comp_m"]
        vivos = [k for k in range(doc["n"]) if not canais["flags"][k] & 2]
        excesso = max(math.hypot(canais["bola_x"][k] - _mao(canais, cab, k)[0],
                                 canais["bola_y"][k] - canais["z"][k] - _mao(canais, cab, k)[1]) - comp
                      for k in vivos)
        # a amostra e de depois do passo inteiro (o corpo ainda anda depois
        # de a bola ser integrada): alguns cm, nunca a corrente esticada
        assert excesso < 0.12, (cab["slot"], excesso)
        rapidos = sum(1 for k in vivos if math.hypot(canais["bola_vx"][k], canais["bola_vy"][k])
                      > cab["arma"]["corrente"]["v_ref_ms"] * 0.5)
        assert rapidos > 10, "a luta tem de ter golpe com a bola rapida para provar algo"


def test_sem_a_chave_nada_muda_na_timeline():
    from neural_fights.recording import timeline_arquivo

    doc = _timeline(None, 4.0)
    assert doc["luta"]["corrente_v2"] is False
    assert all("corrente" not in (c["arma"] or {}) for c in doc["lutadores"])
    assert all(not any(n.startswith("bola_") for n in doc["trilhas"]["lutadores"][s]) for s in ("p1", "p2"))
    assert timeline_arquivo.validar(doc) == []


def test_validador_cobra_cabecalho_e_canais_juntos():
    import copy

    from neural_fights.recording import timeline_arquivo

    base = _timeline(True, 2.0)
    casos = {
        "canal faltando": lambda d: d["trilhas"]["lutadores"]["p1"].pop("bola_vy"),
        "canal curto": lambda d: d["trilhas"]["lutadores"]["p2"]["bola_x"].pop(),
        "canais sem cabecalho": lambda d: d["lutadores"][0]["arma"].pop("corrente"),
        "comp zero": lambda d: d["lutadores"][1]["arma"]["corrente"].update(comp_m=0),
    }
    for nome, estragar in casos.items():
        doc = copy.deepcopy(base)
        estragar(doc)
        assert timeline_arquivo.validar(doc), nome


# ------------------------------------------------------------ F2: o carimbo
def test_luta_nova_carimba_a_chave_e_cada_round_tambem():
    from builds.tournament import runner

    bruto = {"vencedor": P1, "duracao": 12.0, "motivo": "knockout", "seed": 7,
             "hp_vencedor": 40.0, "corrente_v2": False}
    chamadas = []

    def falso(*args, **kw):
        chamadas.append(kw.get("corrente_v2"))
        return dict(bruto, corrente_v2=kw.get("corrente_v2"))

    fichas = {P1: {"forca": 5, "mana": 5}, P2: {"forca": 5, "mana": 5}}
    with mock.patch.object(runner, "gravar_confronto", side_effect=falso), \
            mock.patch.object(runner, "fichas_do_banco", return_value=fichas), \
            mock.patch.object(runner, "personagens_gerados", return_value=[]):
        from builds.generation.session_generator import load_config
        sessao = runner.FightSession(load_config("scoring.json"))
        fight = sessao.gerar(p1=P1, p2=P2, seed=7, cenario="Arena", gravar_em=Path("x"), melhor_de=3)
        assert fight["corrente_v2"] is False and chamadas and set(chamadas) == {False}
        assert all(r["corrente_v2"] is False for r in fight["lutas"])
        chamadas.clear()
        nova = sessao.gerar(p1=P1, p2=P2, seed=7, cenario="Arena", gravar_em=Path("x"), corrente_v2=True)
        assert nova["corrente_v2"] is True and set(chamadas) == {True}
        assert nova["luta"]["corrente_v2"] is True


def test_padrao_de_hoje_e_desligado_e_luta_antiga_e_false():
    from builds.tournament import runner

    assert runner.chave_corrente_padrao() is False, "ligar em producao e decisao do Adrian"
    assert runner.corrente_da_luta({"seed": 1}) is False
    assert runner.corrente_da_luta({}, {"corrente_v2": True}) is True
    assert runner.corrente_da_luta({"corrente_v2": False}, {"corrente_v2": True}) is False


def test_gravador_recebe_o_carimbo_pela_linha_de_comando():
    from builds.tournament import capture

    vistos = []

    def rodar(comando, **_kw):
        vistos.append(comando)
        return SimpleNamespace(stdout='{"sucesso": true}', stderr="", returncode=0)

    with mock.patch.object(capture.subprocess, "run", side_effect=rodar):
        for chave in (None, True, False):
            capture.gravar_uma(p1="a", p2="b", seed=1, saida=None, cenario="Arena", corrente_v2=chave)
    assert not any("corrente" in a for a in vistos[0])
    assert "--corrente-v2" in vistos[1] and "--sem-corrente-v2" not in vistos[1]
    assert "--sem-corrente-v2" in vistos[2]

    from neural_fights.recording import fight_recorder
    parser = fight_recorder.build_parser()
    base = ["--p1", "a", "--p2", "b", "--sem-video"]
    assert parser.parse_args(base).corrente_v2 is None
    assert parser.parse_args(base + ["--corrente-v2"]).corrente_v2 is True
    assert parser.parse_args(base + ["--sem-corrente-v2"]).corrente_v2 is False


def test_som_da_luta_resimula_com_o_carimbo_e_antiga_com_false():
    from builds.tournament import som_real

    luta = {"p1": "a", "p2": "b", "seed": 3, "cenario": "Arena", "vencedor": "a", "duracao": 1.0,
            "clipes": {"celular": {"trechos": [[0.0, 1.0]], "resolucao": [1080, 1920]}}}
    pedidos = []

    def gravar(**kw):
        pedidos.append(kw["corrente_v2"])
        return {"sucesso": True, "vencedor": "a", "duracao_jogo": 1.0, "sons": [], "eventos_dano": [],
                "duracao_video": 1.0, "ko_em_video": None}

    with mock.patch.object(som_real.capture, "gravar_uma", side_effect=gravar):
        som_real.anotar_luta(dict(luta), {}, "duelo")
        som_real.anotar_luta(dict(luta, corrente_v2=True), {}, "duelo")
        som_real.anotar_luta(dict(luta), {}, "duelo", fight={"corrente_v2": True})
    assert pedidos == [False, True, True]


def test_palco_resimula_a_luta_gravada_com_o_carimbo():
    from builds.palco import fonte

    vistos = []

    def gravar(**kw):
        vistos.append(kw.get("corrente_v2"))
        return {"timeline": {"n": 1, "hz": 60}, "resultado": {"empate": False}}

    with mock.patch("neural_fights.recording.timeline.gravar_timeline", side_effect=gravar):
        fonte.timeline_da_luta(p1="a", p2="b", seed=1, cenario="Arena", tentativas=1)
        fonte.timeline_da_luta(p1="a", p2="b", seed=1, cenario="Arena", tentativas=1, corrente_v2=False)
        fonte.timeline_da_luta(p1="a", p2="b", seed=1, cenario="Arena", tentativas=1, corrente_v2=True)
    assert vistos == [None, False, True]


# ------------------------------------------------------------ paridade com o Godot
@pytest.fixture
def pasta_e(tmp_path):
    base = Path("E:/projetos/palco/_saida/_testes") if Path("E:/").exists() else tmp_path
    pasta = base / f"corrente{os.getpid()}_{time.time_ns()}"
    pasta.mkdir(parents=True, exist_ok=True)
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def _interp(canal: list, p: float) -> float:
    i = min(int(math.floor(p)), len(canal) - 1)
    j = min(i + 1, len(canal) - 1)
    w = p - math.floor(p)
    return canal[i] if w < 1e-4 or i == j else canal[i] + (canal[j] - canal[i]) * w


@precisa_godot
def test_paridade_python_godot_dos_canais_e_da_corrente(pasta_e):
    from neural_fights.recording import timeline_arquivo

    doc = _timeline(True)
    arquivo = pasta_e / "t.gcpf"
    timeline_arquivo.salvar(doc, arquivo, compressao="zstd")
    n = doc["n"]
    # passos inteiros, fracionarios (camera lenta) e o ultimo
    passos = [0.0, 1.0, 37.5, 120.25, 200.0, 287.75, float(n // 2), float(n - 1)]
    saida = pasta_e / "paridade.json"
    rc, log = godot.rodar_script("res://ferramentas/paridade_corrente.gd",
                                 [f"--timeline={arquivo}", f"--saida={saida}",
                                  "--passos=" + ",".join(f"{p:g}" for p in passos)])
    assert rc == 0, log[-2000:]
    res = json.loads(saida.read_text(encoding="utf-8"))
    assert res["erros"] == [] and int(res["revisao"]) == 4
    assert set(res["lutadores"]) == {"p1", "p2"}
    for cab in doc["lutadores"]:
        slot = cab["slot"]
        canais = doc["trilhas"]["lutadores"][slot]
        lado = res["lutadores"][slot]
        assert lado["corrente"]["comp_m"] == pytest.approx(cab["arma"]["corrente"]["comp_m"])
        assert int(lado["corrente"]["n_elos"]) == cab["arma"]["corrente"]["n_elos"]
        comp = cab["arma"]["corrente"]["comp_m"]
        for am in lado["amostras"]:
            p = am["p"]
            for nome in ("bola_x", "bola_y", "bola_vx", "bola_vy"):
                assert am[nome] == pytest.approx(_interp(canais[nome], p), abs=1e-9), (slot, p, nome)
            k = int(math.floor(p))
            mx, my = _mao(canais, cab, k) if not canais["flags"][k] & 2 else (canais["arma_gx"][k], canais["arma_gy"][k])
            # Vector2 do Godot e float32: 0,1 mm de folga
            assert am["mao_k"] == pytest.approx([mx, my], abs=1e-4), (slot, p)
            assert am["ativo"] is True
            pts = am["pontos"]
            # a corrente: presa na mao e na bola do passo (no passo fracionario,
            # entre o passo e o seguinte) e nunca mais longa que o comprimento
            if p == math.floor(p):
                assert pts[0] == pytest.approx(am["mao_k"], abs=1e-4)
                assert pts[-1] == pytest.approx(am["bola_k"], abs=1e-4)
            total = sum(math.dist(pts[j], pts[j - 1]) for j in range(1, len(pts)))
            assert total <= comp * 1.03, (slot, p, total, comp)
            assert k - int(am["inicio"]) <= 60
        assert lado["us_por_quadro"] < 50_000, "a corrente nao pode custar mais que 50 ms por quadro"


@precisa_godot
def test_testes_do_nucleo_cobrem_a_revisao_4():
    rc, log = godot.rodar_script("res://ferramentas/testes.gd")
    assert rc == 0, "\n".join(linha for linha in log.splitlines() if "FALHOU" in linha)[-2000:]
    assert "falha" in log
