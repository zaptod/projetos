# -*- coding: utf-8 -*-
"""A Vila do celular: geometria, paralelismo sem pegar trava, e placar.

O que estes testes seguram, e por que:
  - a geometria tem que ser a MESMA do painel (porta no meio da base), senao
    o bot do celular anda para um lugar que no PC e outro;
  - `paralelismo()` NAO pode chamar `travas.ocupada()`: aquela funcao responde
    PEGANDO a trava, e o dono de verdade ouviria "ocupado";
  - o placar (`panorama.resumo`, ~159 s) nunca pode ser calculado dentro do
    pedido;
  - fabrica sem predio (deepseek, mimetizar) continua aparecendo.
"""
from __future__ import annotations

import threading
import time
import types

import pytest

from remoto import vila_dados


class _Motor:
    """O mundo de mentira: dois predios, uma casa, tiles de 16."""

    FABRICAS = {}

    @staticmethod
    def carregar():
        return {
            "tile": 16, "escala": 2,
            "folhas": {"base": {"arquivo": "sprites/base.png", "tile_w": 16}},
            "papeis": {"bot.baixo": {"frames": [144, 145], "fps": 6},
                       "fx.erro": {"frames": [162, 163], "fps": 2},
                       "predio.casa": {"frames": [108], "larg": 4, "alt": 3},
                       "chao.grama": {"frames": [0]}},
            "mapa": {"larg": 40, "alt": 20, "fundo": "#101010",
                     "predios": {"estudio": {"x": 4, "y": 10}},
                     "casa": {"x": 20, "y": 14}},
        }

    @staticmethod
    def tamanho(cfg, papel):
        return (4, 3)

    @staticmethod
    def pronto(cfg):
        return True


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
    # o modulo de verdade tem __file__ (e ao lado dele mora o config.json)
    monkeypatch.setattr(_Motor, "__file__", str(tmp_path / "motor.py"), raising=False)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(vila_dados, "_motor", lambda: _Motor)
    monkeypatch.setattr(vila_dados, "_atividade", lambda: atividade)
    monkeypatch.setattr(vila_dados, "_MUNDO", None)
    monkeypatch.setattr(vila_dados, "caminho_sprites", lambda: tmp_path / "base.png")
    (tmp_path / "base.png").write_bytes(b"png")
    return types.SimpleNamespace(atividade=atividade, tmp=tmp_path)


# ---------------------------------------------------------------- mundo
def test_geometria_e_a_mesma_do_painel(mundo_falso):
    m = vila_dados.mundo(forcar=True)
    assert m["tamanho"] == [40 * 32, 20 * 32] and m["lado"] == 32
    # porta = meio da base do predio, +4 px, como em painel/paginas/vila.py
    assert m["predios"]["estudio"]["porta"] == [(4 + 2) * 32, (10 + 3) * 32 + 4]
    assert m["predios"]["estudio"]["larg"] == 4 * 32
    assert m["casa"]["porta"] == [(20 + 2) * 32, (14 + 3) * 32 + 4]


def test_fabrica_sem_predio_ganha_lugar_na_fila(mundo_falso):
    m = vila_dados.mundo(forcar=True)
    assert "deepseek" not in m["predios"]
    lugar = m["lugares"]["deepseek"]
    assert lugar["tem_predio"] is False
    # anda ate a propria casa: o trabalho dela e o lugar dela na fila
    assert lugar["trabalho"] == lugar["casa"]
    assert vila_dados.mundo()["lugares"]["estudio"]["tem_predio"] is True


def test_mundo_leva_so_os_sprites_animados(mundo_falso):
    sprites = vila_dados.mundo(forcar=True)["sprites"]
    assert set(sprites) == {"bot.baixo", "fx.erro"}      # nada de chao/predio
    assert sprites["fx.erro"]["fps"] == 2


def test_versao_muda_quando_o_cenario_muda(mundo_falso, monkeypatch, tmp_path):
    antes = vila_dados.versao_do_mundo()
    time.sleep(0.01)
    (tmp_path / "base.png").write_bytes(b"png diferente")
    assert vila_dados.versao_do_mundo() != antes


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
