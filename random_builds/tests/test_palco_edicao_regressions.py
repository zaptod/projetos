# -*- coding: utf-8 -*-
"""16G: a edicao do duelo por cima do clipe do palco (builds/palco/edicao.py).

O B do A/B tem de ser o MESMO video do A com so o desenho da luta trocado.
O palco tem hitstop (decisao `hitstop`): a imagem para 1-4 quadros depois de
cada acerto forte, e tudo o que tem hora e vem DEPOIS anda o mesmo tanto. Se
isso nao for feito, a barra de vida cai antes do golpe e o som chega antes
da imagem, um pouco mais a cada acerto. Nada aqui abre o Godot.
"""
from __future__ import annotations

import copy

import pytest

from builds.palco import edicao, plano
from builds.palco.config import ErroPalco


def test_atraso_do_hitstop_comeca_depois_do_quadro_do_acerto():
    paradas = {10: 2, 20: 4}
    # o proprio acerto aparece no quadro dele; a imagem para DEPOIS
    assert plano.atraso_de_hitstop(paradas, 10 / 30) == 0
    assert plano.atraso_de_hitstop(paradas, 11 / 30) == pytest.approx(2 / 30)
    assert plano.atraso_de_hitstop(paradas, 20 / 30) == pytest.approx(2 / 30)
    assert plano.atraso_de_hitstop(paradas, 21 / 30) == pytest.approx(6 / 30)
    assert plano.atraso_de_hitstop({}, 5.0) == 0


def test_paradas_somam_o_mesmo_que_a_contagem_do_render():
    seg = {"light": 0.0, "medium": 0.03, "heavy": 0.07, "colossal": 0.13, "dano_min": 0.03}
    doc = {"hz": 60, "n": 600, "eventos": [
        {"i": 60, "tipo": "acerto", "tier": "heavy", "dano_pct": 0.05},
        {"i": 60, "tipo": "acerto", "tier": "colossal", "dano_pct": 0.2},
        {"i": 240, "tipo": "acerto", "tier": "medium", "dano_pct": 0.1},
    ]}
    paradas = plano.paradas_de_hitstop(doc, seg)
    assert paradas == {30: 4, 120: 1}
    assert sum(paradas.values()) == plano.quadros_de_hitstop(doc, seg)


def _plano_e_fight():
    luta = {
        "p1": "A", "p2": "B", "seed": 7, "vencedor": "A",
        "clipes": {"celular": {"path": "velho_cel.mp4", "duracao": 4.0, "trechos": [[0.0, 4.0]]},
                   "normal": {"path": "velho_nor.mp4", "duracao": 4.0, "trechos": [[0.0, 4.0]]}},
        "serie_hp": [[0.0, 100, 100], [0.5, 100, 90], [2.0, 60, 90]],
        "serie_plano": [[0.0, "PRESSAO", 0.1, "RECUAR", 0.0], [2.0, "PRESSAO", 0.5, "RECUAR", 0.2]],
        "sons": [{"t": 0.5, "id": "hit"}, {"t": 2.0, "id": "ko"}],
        "eventos_dano": [[0.5, "p2", 10.0, "golpe"], [2.0, "p1", 40.0, "golpe"]],
        "eventos_narrativos": [{"t": 2.0, "tipo": "combo"}],
        "ko_em_clipe": 2.0, "duracao_clipe": 4.0,
    }
    ev = {"type": "gameplay", "start": 0.0, "duration": 4.0,
          "asset": {"id": "gameplay_00", "synthetic": False, "path": "velho_cel.mp4",
                    "path_celular": "velho_cel.mp4", "path_normal": "velho_nor.mp4"},
          "crop_celular": None,
          "hud": {"p1": "A", "p2": "B", "serie_hp": copy.deepcopy(luta["serie_hp"]),
                  "serie_plano": copy.deepcopy(luta["serie_plano"])},
          "callouts": [{"t": 0.5, "duracao": 0.9, "texto": "x3 COMBO"}, {"t": 2.0, "duracao": 0.9, "texto": "ACABOU"}],
          "identidade": {"ate": 1.0}, "veredito": {"de": 2.8, "vencedor": "A"}, "luta": copy.deepcopy(luta)}
    plano_a = {"kind": "duelo", "seed": 7, "total_duration": 4.0, "events": [ev]}
    fight = {"seed": 7, "luta": copy.deepcopy(luta), "lutas": [copy.deepcopy(luta)]}
    return plano_a, fight


def test_edicao_leva_tudo_que_tem_hora_ao_relogio_do_palco():
    plano_a, fight = _plano_e_fight()
    intocado = copy.deepcopy((plano_a, fight))
    # acerto no quadro 15 (0,5 s) para 3 quadros: o que vem depois anda 0,1 s
    relogio = edicao.Relogio({15: 3})
    plano_b, fight_b = edicao.edicao_sobre_o_palco(plano_a, fight, clipe="palco.mp4", duracao=4.1,
                                                   relogio=relogio)
    assert (plano_a, fight) == intocado, "o plano e o fight do A nao podem mudar"
    ev = plano_b["events"][0]
    assert ev["duration"] == plano_b["total_duration"] == 4.1
    assert ev["asset"]["path_celular"] == ev["asset"]["path"] == "palco.mp4"
    assert "path_normal" not in ev["asset"] and not any(k.startswith("crop") for k in ev)
    # o golpe em 0,5 s aparece na hora (o quadro dele); o de 2,0 s anda 3 quadros
    assert [a[0] for a in ev["hud"]["serie_hp"]] == [0.0, 0.5, 2.1]
    assert [a[0] for a in ev["hud"]["serie_plano"]] == [0.0, 2.1]
    assert [c["t"] for c in ev["callouts"]] == [0.5, 2.1]
    luta = ev["luta"]
    assert [s["t"] for s in luta["sons"]] == [0.5, 2.1]
    assert [e[0] for e in luta["eventos_dano"]] == [0.5, 2.1]
    assert luta["eventos_narrativos"][0]["t"] == 2.1 and luta["ko_em_clipe"] == 2.1
    assert list(luta["clipes"]) == ["celular"] and luta["clipes"]["celular"]["duracao"] == 4.1
    # o veredito fica o mesmo tanto antes do fim (1,2 s)
    assert ev["veredito"]["de"] == pytest.approx(2.9)
    assert ev["identidade"] == {"ate": 1.0}
    assert fight_b["luta"] is luta and fight_b["lutas"][-1] is luta


def test_edicao_sobre_o_palco_e_so_a_do_duelo():
    plano_a, fight = _plano_e_fight()
    plano_a["events"].append({"type": "card", "duration": 1.0})
    with pytest.raises(ErroPalco):
        edicao.edicao_sobre_o_palco(plano_a, fight, clipe="p.mp4", duracao=4.0, relogio=edicao.Relogio())


def test_so_o_perfil_celular_por_enquanto():
    with pytest.raises(ErroPalco):
        edicao.ab_com_edicao("duelo_00001", perfil="normal")
