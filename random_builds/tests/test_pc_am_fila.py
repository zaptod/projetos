# -*- coding: utf-8 -*-
"""A fila sem descanso do PC am (builds/pc_am/fila.py).

O am e um duble de `chamar("saude")`; os trabalhos sao trocados por dubles
que contam quem rodou. Os casos que o pedido de 20/10/2026 cobra:

  - ZERO: nada a fazer -> roda as suites (e, com tudo em dia, "nada util"
    sem alarme);
  - am fora -> a fila espera e avisa UMA vez (e nada roda aqui);
  - teto atingido -> nao produz;
  - disco cheio no am -> para e avisa; disco cheio aqui -> so o que nao traz
    arquivo;
  - prioridade: pedido explicito antes de tudo; parado sem motivo avisa uma
    vez depois de 15 min; tipo que falha 3 vezes descansa.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from builds.pc_am import fila as F
from builds.pc_am import maquina, relogio, trabalhos
from builds.pc_am.maquina import AmFora, Resultado


class AmDuble:
    def __init__(self, disco=60.0):
        self.fora = False
        self.disco = disco
        self.cpu = 10
        self.memoria = 4000
        self.ativos = []

    def chamar(self, acao, parametros=None, prazo=None):
        if self.fora:
            raise AmFora("duble: sem conexao")
        assert acao == "saude"
        return {"ok": True, "disco_livre_gb": self.disco, "memoria_livre_mb": self.memoria, "cpu": self.cpu,
                "temperatura_c": None, "ativos": list(self.ativos),
                "ativo": self.ativos[0] if self.ativos else None, "agora": "2026-10-20T10:00:00"}


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 10, 20, 10, 0, 0)

    def __call__(self):
        return self.agora

    def anda(self, minutos):
        self.agora += timedelta(minutes=minutos)


@pytest.fixture(autouse=True)
def runtime_isolado(tmp_path, monkeypatch):
    pasta = tmp_path / "pc_am"
    pasta.mkdir()
    monkeypatch.setattr(maquina, "runtime", lambda: pasta)
    # a janela das postagens depende da HORA: o teste nao pode (ver test_pc_am_sonda.py)
    monkeypatch.setattr(relogio, "liberado", lambda *a, **k: (True, ""))
    return pasta


@pytest.fixture
def cfg():
    config = maquina.carregar_config(Path("nao-existe.json"))
    config["fila"] = dict(F.PADRAO_FILA, ligada=True)
    return config


@pytest.fixture
def mundo(cfg, monkeypatch):
    """Fila com os trabalhos trocados por dubles que anotam quem rodou."""
    rodou = []

    def suite(pasta, extras=None, **kw):
        assert kw["cair_para_aqui"] is False                   # a fila nunca roda aqui
        rodou.append(("suite", pasta))
        return Resultado(onde="am", rc=0, log=f"== 3 passed in 1.0s ({pasta})")

    def npm(sha=None, **kw):
        rodou.append(("npm", sha))
        return Resultado(onde="am", rc=0, log="Tests  10 passed (10)")

    def duelo(**kw):
        assert kw["cair_para_aqui"] is False
        rodou.append(("duelo", None))
        return Path("duelo_00099")

    monkeypatch.setattr(trabalhos, "testar_no_am", suite)
    monkeypatch.setattr(trabalhos, "testar_blue_lock_no_am", npm)
    monkeypatch.setattr(trabalhos, "duelo", duelo)
    monkeypatch.setattr(trabalhos, "roletas_da_voz", lambda: [])
    monkeypatch.setattr(F.Fila, "suites", lambda self: ["coordenador", "remoto"])
    monkeypatch.setattr(F.Fila, "fonte_ramos", lambda self: (None, "ramos olhados ha pouco"))
    monkeypatch.setattr(F.Fila, "fonte_bluelock", lambda self: (None, "a fabrica do Blue Lock nao esta no ramo"))
    am, relogio, avisos = AmDuble(), Relogio(), []

    def nova(estoque=200, disco_aqui=100.0):
        laco = F.Fila(cfg, transporte=am, avisar=avisos.append, relogio=relogio, dorme=lambda s: None,
                      disco_aqui=lambda: disco_aqui, log=lambda t: None, sincrono=True)
        laco.contar_duelos = lambda: estoque
        return laco
    return {"rodou": rodou, "am": am, "relogio": relogio, "avisos": avisos, "nova": nova}


# ------------------------------------------------------------- caso ZERO
def test_caso_zero_nada_a_fazer_roda_as_suites_e_depois_descansa_sem_alarme(mundo):
    laco = mundo["nova"]()
    for _ in range(3):
        assert laco.passo()["rodou"] is True
    assert mundo["rodou"] == [("suite", "coordenador"), ("suite", "remoto"), ("npm", None)]
    registro = json.loads(F.arquivo("suites.json").read_text(encoding="utf-8"))
    assert set(registro["suites"]) == {"coordenador", "remoto", "npm:blue-lock"}
    assert registro["suites"]["coordenador"]["placar"] == "3 passed"
    # tudo em dia: para, com motivo justo — nem depois de 1 h avisa
    resultado = laco.passo()
    assert resultado["rodou"] is False and resultado["motivo"].startswith("nada util")
    mundo["relogio"].anda(60)
    laco.passo()
    assert mundo["avisos"] == []
    # passadas as horas de repetir, roda de novo
    mundo["relogio"].anda(12 * 60)
    assert laco.passo()["rodou"] is True


def test_fila_desligada_nao_toca_no_am(mundo, cfg):
    cfg["fila"]["ligada"] = False
    mundo["am"].fora = True                                   # nem pergunta a saude
    resultado = mundo["nova"]().passo()
    assert resultado["rodou"] is False and resultado["motivo"].startswith("fila desligada")
    assert mundo["rodou"] == [] and mundo["avisos"] == []


def test_config_do_repositorio_nasce_com_a_fila_desligada():
    assert maquina.carregar_config()["fila"]["ligada"] is False
    assert F.teto_de_duelos(maquina.carregar_config()) == 88          # 14 dias x 6,25


# ---------------------------------------------------------------- am fora
def test_am_fora_a_fila_espera_e_avisa_uma_vez(mundo):
    laco = mundo["nova"]()
    mundo["am"].fora = True
    for _ in range(4):
        resultado = laco.passo()
        assert resultado["rodou"] is False and resultado["motivo"].startswith("am fora")
        mundo["relogio"].anda(10)
    assert len(mundo["avisos"]) == 1 and "PC am fora" in mundo["avisos"][0]
    assert mundo["rodou"] == []
    mundo["am"].fora = False
    assert laco.passo()["rodou"] is True
    mundo["am"].fora = True
    laco.passo()
    assert len(mundo["avisos"]) == 2                           # a queda nova avisa de novo


# ------------------------------------------------------------------- teto
def test_teto_de_duelos_atingido_nao_produz(mundo):
    laco = mundo["nova"](estoque=88)
    laco.passo()
    assert ("duelo", None) not in mundo["rodou"]
    assert laco.estado["contas"]["duelos"] == {"estoque": 88, "teto": 88}


def test_abaixo_do_teto_o_duelo_vem_antes_das_suites(mundo):
    laco = mundo["nova"](estoque=20)
    laco.passo()
    assert mundo["rodou"] == [("duelo", None)]
    assert "duelo para o estoque (21/88)" in F.estado_para_painel()["ultimo"]["descricao"]


# ------------------------------------------------------------------ disco
def test_disco_do_am_cheio_para_e_avisa_uma_vez(mundo):
    mundo["am"].disco = 9.0
    laco = mundo["nova"](estoque=0)
    for _ in range(3):
        resultado = laco.passo()
        assert resultado["rodou"] is False and "disco do am" in resultado["motivo"]
    assert mundo["rodou"] == [] and len(mundo["avisos"]) == 1 and "disco" in mundo["avisos"][0]


def test_disco_daqui_cheio_so_roda_o_que_nao_traz_arquivo(mundo):
    laco = mundo["nova"](estoque=0, disco_aqui=3.0)
    laco.passo()
    assert mundo["rodou"] == [("suite", "coordenador")]          # o duelo ficou de fora
    assert any("disco daqui cheio" in m for m in laco.estado["motivos"])
    assert len(mundo["avisos"]) == 1


# --------------------------------------------------------------- pedidos
def test_pedido_explicito_vem_antes_de_tudo(mundo):
    F.pedir("testar", pasta="historias", extras=["-k", "voz"])
    laco = mundo["nova"](estoque=0)
    laco.passo()
    assert mundo["rodou"] == [("suite", "historias")]
    assert F.pedidos_na_fila() == []
    laco.passo()
    assert mundo["rodou"][-1] == ("duelo", None)


def test_pedido_de_tipo_desconhecido_e_recusado():
    with pytest.raises(ValueError):
        F.pedir("publicar")


# ------------------------------------------------------ parado e falhas
def test_parado_sem_motivo_avisa_uma_vez_depois_de_15_min(mundo):
    def quebrada():
        raise RuntimeError("fonte quebrada")
    laco = mundo["nova"]()
    laco.fontes = [("duelo", quebrada)]
    laco.passo()
    mundo["relogio"].anda(10)
    laco.passo()
    assert mundo["avisos"] == []
    mundo["relogio"].anda(6)
    laco.passo()
    laco.passo()
    assert len(mundo["avisos"]) == 1 and "parado" in mundo["avisos"][0]


def test_tipo_que_falha_tres_vezes_descansa(mundo, monkeypatch):
    def falha(**kw):
        raise maquina.FalhaNoAm("o render caiu")
    monkeypatch.setattr(trabalhos, "duelo", falha)
    laco = mundo["nova"](estoque=0)
    for _ in range(3):
        ficha = laco.passo()["ficha"]
        assert ficha["tipo"] == "duelo" and ficha["ok"] is False
    laco.passo()
    assert mundo["rodou"] == [("suite", "coordenador")]          # o duelo descansa; a suite anda


def test_o_estado_diz_o_que_o_am_esta_fazendo(mundo):
    laco = mundo["nova"]()
    vistos = []
    original = trabalhos.testar_no_am

    def espiando(pasta, extras=None, **kw):
        vistos.append(F.estado_para_painel()["texto"])
        return original(pasta, extras, **kw)
    trabalhos.testar_no_am = espiando
    try:
        laco.passo()
    finally:
        trabalhos.testar_no_am = original
    assert vistos[0].startswith("o am está fazendo suite coordenador")
    assert "desde 10:00" in vistos[0]


# --------------------------------------------- paralelo por recurso
def _fila_com_threads(cfg, am, relogio, *, liberar):
    """Fila de verdade (threads), com fontes que entregam trabalhos que so
    terminam quando o teste mandar (`liberar`)."""
    cfg["paralelo"] = {"maximo": 3, "cpu_alvo": 80, "memoria_reserva_mb": 1500, "janela_cpu_s": 0}
    contador = {"n": 0}

    def fonte():
        contador["n"] += 1
        return F.Tarefa("suite", f"suite {contador['n']}", lambda: liberar.wait(10), chave=str(contador["n"]),
                        grupo=f"g{contador['n']}"), ""
    return F.Fila(cfg, transporte=am, avisar=lambda t: None, relogio=relogio, dorme=lambda s: None,
                  disco_aqui=lambda: 100.0, log=lambda t: None, fontes=[("suite", fonte)])


def test_com_cpu_e_memoria_sobrando_entra_mais_um_ate_o_maximo(mundo, cfg):
    import threading
    liberar = threading.Event()
    am = mundo["am"]
    am.memoria = 8000
    laco = _fila_com_threads(cfg, am, mundo["relogio"], liberar=liberar)
    try:
        for _ in range(3):
            assert laco.passo()["rodou"] is True
        resultado = laco.passo()
        assert resultado["rodou"] is False and "am cheio" in resultado["motivo"] and len(laco.rodando) == 3
        assert "o am está fazendo suite 1" in F.estado_para_painel()["texto"]
    finally:
        liberar.set()
        laco.esperar_todos()
    assert laco.rodando == {}


def test_cpu_no_alvo_nao_entra_mais_ninguem(mundo, cfg):
    import threading
    liberar = threading.Event()
    am = mundo["am"]
    am.memoria = 8000
    laco = _fila_com_threads(cfg, am, mundo["relogio"], liberar=liberar)
    try:
        assert laco.passo()["rodou"] is True
        am.cpu = 95
        am.ativos = [{"id": "x"}]
        # (26/10/2026) com `janela_cpu_s: 0` a media nunca via amostra e o teste
        # passava a ser "entra": a janela volta a 30 s, e o "espera o ultimo
        # mostrar a CPU" e zerado para o que se prova ser o `cabe` com a CPU alta
        cfg["paralelo"]["janela_cpu_s"] = 30
        laco.ultimo_lancamento = None
        for _ in range(12):                                    # a janela de 30 s enche de 95%
            maquina.registrar_cpu(95)
        resultado = laco.passo()
        assert resultado["rodou"] is False and "na media de 30 s" in resultado["motivo"]
    finally:
        liberar.set()
        laco.esperar_todos()


def test_sem_memoria_para_o_proximo_nao_entra(mundo, cfg):
    import threading
    liberar = threading.Event()
    am = mundo["am"]
    am.memoria = 2500
    laco = _fila_com_threads(cfg, am, mundo["relogio"], liberar=liberar)
    try:
        assert laco.passo()["rodou"] is True
        am.memoria = 2000                                     # o que entrou ja pesa: 2000 - 800 < 1500
        resultado = laco.passo()
        assert resultado["rodou"] is False and "memoria" in resultado["motivo"]
    finally:
        liberar.set()
        laco.esperar_todos()


def test_cpu_ociosa_por_10_min_puxa_as_suites_mesmo_em_dia(mundo):
    laco = mundo["nova"]()
    for _ in range(3):
        laco.passo()                                           # as 3 suites do commit
    assert laco.passo()["motivo"].startswith("nada util")     # CPU 10%: comeca a contar
    mundo["relogio"].anda(5)
    assert laco.passo()["rodou"] is False
    mundo["relogio"].anda(6)                                   # 11 min abaixo de 70%
    assert laco.passo()["rodou"] is True
    assert mundo["rodou"][-1] == ("suite", "coordenador")      # a feita ha mais tempo


def test_cpu_alta_nao_puxa_suite_repetida(mundo):
    laco = mundo["nova"]()
    for _ in range(3):
        laco.passo()
    mundo["am"].cpu = 90
    for _ in range(12):
        maquina.registrar_cpu(90)
    laco.passo()
    mundo["relogio"].anda(30)
    assert laco.passo()["rodou"] is False


def test_pedido_que_nao_cabe_volta_para_a_frente_da_fila(mundo, cfg):
    F.pedir("testar", pasta="historias")
    mundo["am"].memoria = 1000                                 # nada cabe
    laco = mundo["nova"]()
    resultado = laco.passo()
    assert resultado["rodou"] is False and "memoria" in resultado["motivo"]
    assert [p["argumentos"]["pasta"] for p in F.pedidos_na_fila()] == ["historias"]


# ------------------------------------------------ a noite deixa para o am
def test_a_noite_so_deixa_os_duelos_para_o_am_com_a_fila_viva(cfg, mundo):
    cfg["trabalhos"]["duelo"] = True
    assert F.cuida_dos_duelos(cfg) is False                    # nunca rodou
    laco = F.Fila(cfg, transporte=mundo["am"], avisar=lambda t: None, dorme=lambda s: None,
                  disco_aqui=lambda: 100.0, log=lambda t: None, sincrono=True)
    laco.contar_duelos = lambda: 0
    laco.passo()
    assert F.cuida_dos_duelos(cfg) is True
    mundo["am"].fora = True
    laco.passo()
    assert F.cuida_dos_duelos(cfg) is False                    # am fora = a noite gera aqui
    cfg["trabalhos"]["duelo"] = False
    assert F.cuida_dos_duelos(cfg) is False


# ------------------------------------------------------- voz das roletas
def test_roletas_da_voz_pula_publicadas_feitas_e_fora_da_janela(tmp_path, monkeypatch):
    monkeypatch.setattr(trabalhos, "OUTPUTS", tmp_path)
    dentro = datetime(2026, 10, 15, 3, 0).timestamp()
    fora = datetime(2026, 10, 10, 3, 0).timestamp()
    for numero, quando in ((126, dentro), (127, dentro), (128, fora), (129, dentro), (130, dentro)):
        pasta = tmp_path / f"generation_{numero:05d}"
        pasta.mkdir()
        (pasta / "voz.wav").write_bytes(b"x")
        (pasta / "final_celular.mp4").write_bytes(b"x")
        os.utime(pasta / "voz.wav", (quando, quando))
    (tmp_path / "generation_00129" / trabalhos.MARCA_DA_VOZ).write_text('{"feita": true}')
    (tmp_path / "generation_00130" / trabalhos.MARCA_DA_VOZ).write_text('{"tentativas": 2}')
    assert trabalhos.roletas_da_voz(publicadas={"generation_00127"}) == ["generation_00126"]


def test_voz_refeita_entra_na_pasta_com_os_caminhos_daqui(tmp_path, monkeypatch):
    monkeypatch.setattr(trabalhos, "OUTPUTS", tmp_path / "outputs")
    destino = tmp_path / "outputs" / "generation_00150"
    destino.mkdir(parents=True)
    (destino / "final_celular.mp4").write_bytes(b"velho")
    (destino / "generation.json").write_text("{}")
    veio = tmp_path / "veio" / "generation_00150"
    veio.mkdir(parents=True)
    (veio / "final_celular.mp4").write_bytes(b"novo")
    (veio / "edit_plan.json").write_text(json.dumps(
        {"clip": r"C:\nf\projetos\random_builds\assets\reactions\0004.mp4"}), encoding="utf-8")
    trabalhos.instalar_voz(veio, None)
    assert (destino / "final_celular.mp4").read_bytes() == b"novo"
    plano = json.loads((destino / "edit_plan.json").read_text(encoding="utf-8"))
    assert plano["clip"] == str(trabalhos.RAIZ / "random_builds" / "assets" / "reactions" / "0004.mp4")
    assert (destino / "generation.json").read_text() == "{}"         # o resto fica


def test_refazer_voz_aceita_so_o_edge(tmp_path, monkeypatch):
    """O SAPI e a reserva do sintetizador: voz refeita com `.wav` novo no
    cache e recusada (rc 7) e nada volta."""
    from builds.content import voz
    from builds.pc_am import refazer_voz
    from builds.pipeline import controller
    outputs = tmp_path / "outputs"
    (outputs / "generation_00150").mkdir(parents=True)
    (outputs / "generation_00150" / "generation.json").write_text("{}")
    cache = tmp_path / "cache"
    monkeypatch.setattr(controller, "OUTPUTS", outputs)
    monkeypatch.setattr(voz, "CACHE_PADRAO", cache)

    class Controlador:
        def __init__(self, sapi):
            self.sapi = sapi

        def rerender(self, gid, refazer_edicao=False):
            assert refazer_edicao is True
            (outputs / gid / "voz.wav").write_bytes(b"v")
            (outputs / gid / "final_celular.mp4").write_bytes(b"f")
            if self.sapi:
                (cache / "fala.wav").write_bytes(b"s")
    monkeypatch.setattr(controller, "PipelineController", lambda: Controlador(True))
    assert refazer_voz.refazer("generation_00150", tmp_path / "saida") == refazer_voz.RC_SAPI
    assert not (tmp_path / "saida").exists()
    monkeypatch.setattr(controller, "PipelineController", lambda: Controlador(False))
    time.sleep(0.01)
    assert refazer_voz.refazer("generation_00150", tmp_path / "saida") == 0
    assert {p.name for p in (tmp_path / "saida" / "generation_00150").iterdir()} >= {"voz.wav",
                                                                                   "final_celular.mp4"}
