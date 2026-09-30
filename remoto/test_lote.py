# -*- coding: utf-8 -*-
"""O lote da semana (`remoto.lote`): um calculo para o bot, o painel e o app.

O caso ZERO manda aqui (memoria "relatorio verde que mente"): estoque zero e
abaixo do piso, e canal que ninguem contou diz "nao deu para contar" — nunca
"cobre", nunca some.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from remoto import lote

RAIZ = Path(__file__).resolve().parents[1]
FIM = datetime(2026, 10, 5, 7, 0)
AGORA = datetime(2026, 9, 30, 12, 0)


def _ficha(videos, *, piso=20, horarios=49, mais_o_piso=True):
    contou = videos is not None and videos >= 0
    alvo = horarios + (piso if mais_o_piso else 0)
    return {"videos": videos, "dias": videos / 10 if contou else -1,
            "piso": piso, "magro": bool(contou and videos < piso),
            "fim": FIM, "horarios": horarios, "alvo": alvo,
            "faltam": max(0, alvo - videos) if contou else None}


def _postar(**canais):
    return SimpleNamespace(estoque_do_lote=lambda agora=None: dict(canais))


@pytest.fixture(autouse=True)
def _configs(monkeypatch):
    """A agenda e a geracao do jeito decidido em 30/09, sem ler o disco."""
    from contos.pipeline import agenda
    config = {"janela_pesada": {"inicio": 7, "fim": 22},
              "dias_de_lote": [0, 1, 2], "lote_a_partir_de": "2026-10-05",
              "alvo_do_lote": {"cobrir_ate_o_dia": 0, "cobrir_ate_a_hora": 7,
                               "mais_o_piso": True},
              "piso_de_reposicao": 20}
    monkeypatch.setattr(lote, "_agenda", lambda: (agenda, config))
    monkeypatch.setattr(lote, "_geracao", lambda: {
        "janela_pesada": {"inicio": 7, "fim": 22}, "dias_de_lote": [0, 1]})
    return config


# ------------------------------------------------------------ os numeros
def test_linha_por_canal_com_lote_piso_e_janela():
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(6),
                                          builds=_ficha(17)))
    h, b = r["canais"]["historias"], r["canais"]["builds"]
    assert h["texto"] == ("lote 6/69 (0,6 dia) · piso 20 · janela 07–22h "
                          "seg–qua ⚠ abaixo do piso")
    assert b["texto"] == ("lote 17/69 (1,7 dia) · piso 20 · janela 07–22h "
                          "seg–ter ⚠ abaixo do piso")
    assert r["cobertura"] == "alvo = 49 horário(s) até seg 05/10 07h + piso"
    assert r["erros"] == []


def test_acima_do_piso_mas_sem_chegar_ao_alvo_diz_quanto_falta():
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(30),
                                          builds=_ficha(69)))
    assert r["canais"]["historias"]["situacao"] == "falta"
    assert r["canais"]["historias"]["texto"].endswith("faltam 39")
    assert r["canais"]["builds"]["situacao"] == "cobre"
    assert r["canais"]["builds"]["texto"].endswith("✓ cobre")


def test_o_piso_e_o_do_postar_e_nao_uma_copia():
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(8, piso=7),
                                          builds=_ficha(8, piso=9)))
    assert "piso 7" in r["canais"]["historias"]["texto"]
    assert r["canais"]["historias"]["situacao"] == "falta"
    assert r["canais"]["builds"]["situacao"] == "abaixo_do_piso"


# ------------------------------------------------------------ caso ZERO
def test_estoque_zero_e_abaixo_do_piso_e_nunca_cobre():
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(0),
                                          builds=_ficha(0)))
    for ficha in r["canais"].values():
        assert ficha["contou"] and ficha["magro"]
        assert ficha["situacao"] == "abaixo_do_piso"
        assert ficha["texto"].startswith("lote 0/69 (0,0 dia)")
        assert "cobre" not in ficha["texto"]


def test_canal_que_nao_deu_para_contar_diz_isso():
    """`-1` e o "nao contei" do `postar`; um canal ausente, tambem."""
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(-1)))
    for canal in ("historias", "builds"):
        ficha = r["canais"][canal]
        assert not ficha["contou"] and not ficha["magro"]
        assert ficha["situacao"] == "sem_conta"
        assert ficha["texto"].startswith("não deu para contar o estoque")
        assert "✓" not in ficha["texto"]
    assert "alvo 69" in r["canais"]["historias"]["texto"]


def test_postar_que_explode_nao_derruba_e_nao_vira_ok():
    def explode(agora=None):
        raise RuntimeError("catalogo ilegivel")
    r = lote.resumo(AGORA, postar=SimpleNamespace(estoque_do_lote=explode))
    assert set(r["canais"]) == {"historias", "builds"}
    assert all(f["situacao"] == "sem_conta" for f in r["canais"].values())
    assert any("catalogo ilegivel" in e for e in r["erros"])
    texto = "\n".join(lote.linhas(r))
    assert texto.count("não deu para contar") == 2
    assert "✓" not in texto
    assert "não consegui ler estoque" in texto


def test_linhas_de_resumo_vazio_nao_somem():
    texto = lote.linhas({})
    assert texto[0] == "*Lote da semana*"
    assert sum("não deu para contar" in l for l in texto) == 2


def test_erro_com_sublinhado_nao_quebra_o_markdown():
    texto = "\n".join(lote.linhas({"erros": ["historia_00012 sem _meta"]}))
    assert "historia\\_00012" in texto


def test_o_resumo_vai_para_json():
    import json
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(6),
                                          builds=_ficha(-1)))
    assert json.loads(json.dumps(r, ensure_ascii=False)) == r


# ------------------------------------------------------------ o calendario
@pytest.mark.parametrize("agora, esperado", [
    (datetime(2026, 9, 30, 12, 0), "próximo lote: seg 05/10"),   # transicao
    (datetime(2026, 10, 5, 6, 30), "próximo lote: seg 05/10"),   # antes das 7h
    (datetime(2026, 10, 5, 9, 30), "lote em curso até qua 07/10 22h"),
    (datetime(2026, 10, 7, 21, 59), "lote em curso até qua 07/10 22h"),
    (datetime(2026, 10, 7, 22, 0), "próximo lote: seg 12/10"),
    (datetime(2026, 10, 9, 15, 0), "próximo lote: seg 12/10"),
])
def test_calendario_pela_agenda(agora, esperado):
    r = lote.resumo(agora, postar=_postar(historias=_ficha(6)))
    assert r["calendario"] == esperado


def test_agenda_ilegivel_nao_inventa_calendario(monkeypatch):
    def explode():
        raise ValueError("agenda.json torto")
    monkeypatch.setattr(lote, "_agenda", explode)
    r = lote.resumo(AGORA, postar=_postar(historias=_ficha(6)))
    assert r["calendario"] is None
    assert r["canais"]["historias"]["janela"] is None
    assert any("agenda.json torto" in e for e in r["erros"])


# ------------------------------------------------ com o `postar` de verdade
def _postar_real():
    caminho = RAIZ / "ferramentas" / "postar.py"
    spec = importlib.util.spec_from_file_location("postar_teste_lote", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_caso_zero_pelo_estoque_do_lote_de_verdade():
    """O `estoque_do_lote` e o `piso_de_alerta` reais, com a contagem dada:
    historias com ZERO e builds sem contagem."""
    real = _postar_real()
    postar = SimpleNamespace(estoque_do_lote=lambda agora=None: (
        real.estoque_do_lote(agora, pendentes={"historias": 0,
                                               "builds": -1})))
    r = lote.resumo(AGORA, postar=postar)
    h, b = r["canais"]["historias"], r["canais"]["builds"]
    assert h["piso"] == real.piso_de_alerta("historias") > 1
    assert h["situacao"] == "abaixo_do_piso" and h["videos"] == 0
    assert b["situacao"] == "sem_conta"
    assert b["texto"].startswith("não deu para contar o estoque")
