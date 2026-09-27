# -*- coding: utf-8 -*-
"""O texto da Vila: fabricas por canal, paralelismo e placar.

O que estes testes seguram, e por que:
  - `paralelismo()` NAO pode chamar `travas.ocupada()`: aquela funcao responde
    PEGANDO a trava, e o dono de verdade ouviria "ocupado";
  - o placar (`panorama.resumo`, ~159 s) nunca pode ser calculado dentro do
    pedido;
  - fonte quebrada nao derruba a tela, e o detalhe sai limpo.

O DESENHO da Vila tem testes proprios em `test_vila_nova.py`.
"""
from __future__ import annotations

import threading
import time
import types

import pytest

from remoto import vila_dados


class _Atividade:
    FABRICAS = {
        "estudio": {"rotulo": "Estúdio", "emoji": "🎬", "faz": "render"},
        "deepseek": {"rotulo": "DeepSeek", "emoji": "🐋", "faz": "roteiro"},
    }

    def __init__(self):
        self.fabricas = {"estudio": {"status": "trabalhando", "detalhe": "h36",
                                     "canal": "historias", "ha_s": 4.0},
                         "deepseek": {"status": "ocioso", "detalhe": "",
                                      "canal": "", "ha_s": 900.0}}
        self.canais = {("estudio", "historias"): {"status": "trabalhando",
                                                  "detalhe": "parte 2", "ha_s": 4.0},
                       ("estudio", "builds"): {"status": "ocioso",
                                               "detalhe": "antigo", "ha_s": 900.0}}

    def estado_das_fabricas(self):
        return dict(self.fabricas)

    def estado_por_canal(self):
        return dict(self.canais)


@pytest.fixture
def mundo_falso(monkeypatch, tmp_path):
    atividade = _Atividade()
    monkeypatch.setattr(vila_dados, "_atividade", lambda: atividade)
    return types.SimpleNamespace(atividade=atividade, tmp=tmp_path)


# ---------------------------------------------------------------- estado
def test_estado_traz_trabalhos_por_canal_sem_os_ociosos(mundo_falso, monkeypatch):
    monkeypatch.setattr(vila_dados, "paralelismo", list)
    monkeypatch.setattr(vila_dados.PLACAR, "ler", lambda: None)
    e = vila_dados.estado()
    estudio = next(f for f in e["fabricas"] if f["nome"] == "estudio")
    assert estudio["status"] == "trabalhando"
    assert [t["canal"] for t in estudio["trabalhos"]] == ["historias"]
    deepseek = next(f for f in e["fabricas"] if f["nome"] == "deepseek")
    assert deepseek["trabalhos"] == [] and deepseek["status"] == "ocioso"


def test_fonte_quebrada_nao_derruba_a_tela(mundo_falso, monkeypatch):
    def quebra():
        raise OSError("diario sumiu")
    monkeypatch.setattr(mundo_falso.atividade, "estado_das_fabricas", quebra)
    monkeypatch.setattr(vila_dados, "paralelismo", list)
    monkeypatch.setattr(vila_dados.PLACAR, "ler", lambda: None)
    e = vila_dados.estado()
    assert e["erros_de_leitura"] and all(f["status"] == "ocioso"
                                        for f in e["fabricas"])


def test_detalhe_sai_limpo(mundo_falso, monkeypatch):
    mundo_falso.atividade.fabricas["estudio"]["detalhe"] = \
        "erro em C:\\Users\\adrian\\x https://youtu.be/abc"
    monkeypatch.setattr(vila_dados, "paralelismo", list)
    monkeypatch.setattr(vila_dados.PLACAR, "ler", lambda: None)
    estudio = next(f for f in vila_dados.estado()["fabricas"]
                   if f["nome"] == "estudio")
    assert "adrian" not in estudio["detalhe"] and "[link]" in estudio["detalhe"]


# ----------------------------------------------------------- paralelismo
def test_paralelismo_nao_pega_a_trava(monkeypatch):
    from builds import travas
    monkeypatch.setattr(travas, "ocupada", lambda nome: pytest.fail(
        "paralelismo() nao pode chamar travas.ocupada: ela PEGA a trava"))
    monkeypatch.setattr(travas, "trava", lambda *a, **k: pytest.fail(
        "paralelismo() nao pode pegar trava nenhuma"))
    monkeypatch.setattr(travas, "do_perfil",
                        lambda servico, canal: f"perfil__{servico}")
    sondadas = []
    monkeypatch.setattr(vila_dados, "_trava_ocupada",
                        lambda nome: sondadas.append(nome) or False)
    linhas = vila_dados.paralelismo()
    assert linhas and sondadas
    # uma linha por pasta, com os dois canais que a dividem
    assert all(linha["canais"] == ["builds", "historias"] for linha in linhas)
    assert all(linha["dividida"] for linha in linhas)
    assert len({linha["trava"] for linha in linhas}) == len(linhas)


def test_paralelismo_diz_nao_sei_quando_nao_sabe(monkeypatch):
    from builds import travas
    monkeypatch.setattr(travas, "do_perfil", lambda s, c: f"perfil__{s}__{c}")
    monkeypatch.setattr(vila_dados, "_trava_ocupada", lambda nome: None)
    linhas = vila_dados.paralelismo()
    assert linhas and all(linha["ocupada"] is None for linha in linhas)
    assert all(not linha["dividida"] for linha in linhas)    # pastas diferentes


# ---------------------------------------------------------------- placar
def test_placar_nunca_calcula_dentro_do_pedido(monkeypatch):
    placar = vila_dados._Placar()
    comecou = threading.Event()
    solta = threading.Event()

    def demorado():
        comecou.set()
        solta.wait(5)
        return {"desempenho": {"total": 7}, "inventario": {"videos_prontos": {"total": 3}},
                "saude": {"trabalhando": ["x"]}, "qualidade": {"total_erros": 2}}
    import sys
    falso = types.ModuleType("visao")
    falso.panorama = types.SimpleNamespace(resumo=lambda forcar=False: demorado())
    monkeypatch.setitem(sys.modules, "visao", falso)
    inicio = time.monotonic()
    assert placar.ler() == {"calculando": True}
    assert time.monotonic() - inicio < 1.0          # nao esperou o calculo
    assert comecou.wait(5)
    solta.set()
    for _ in range(100):
        valor = placar.ler()
        if valor and not valor.get("calculando"):
            break
        time.sleep(0.05)
    assert valor["publicados"] == 7 and valor["prontos"] == 3
    assert valor["trabalhando"] == 1 and valor["problemas"] == 2
    assert valor["idade_s"] >= 0


def test_placar_que_falha_nao_derruba(monkeypatch):
    placar = vila_dados._Placar()
    import sys
    falso = types.ModuleType("visao")

    def quebra(forcar=False):
        raise RuntimeError("ledger ilegivel")
    falso.panorama = types.SimpleNamespace(resumo=quebra)
    monkeypatch.setitem(sys.modules, "visao", falso)
    placar.ler()
    for _ in range(100):
        valor = placar.ler()
        if valor and not valor.get("calculando"):
            break
        time.sleep(0.05)
    assert valor["falhou"] == "RuntimeError"
