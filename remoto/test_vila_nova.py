# -*- coding: utf-8 -*-
"""A Vila nova servida ao celular: arte, mundo e o motor da vida.

O que estes testes seguram:
  - o ATLAS tem toda combinacao que o retrato pode pedir (se faltar uma, o
    habitante some da tela em vez de aparecer errado);
  - o fundo de DIA e o de NOITE sao imagens diferentes, e cada um e composto
    UMA vez (compor custa ~0,5 s; fazer isso a cada pedido derrubaria o app);
  - o motor aplica o ESTADO REAL (o diario) na vida, e uma leitura que falha
    nao derruba o retrato;
  - o motor DORME quando ninguem esta olhando: nada de queimar CPU do PC
    para um celular que foi guardado no bolso.
"""
from __future__ import annotations

import threading
import time
import types

import pytest

from remoto import vila_nova


# --------------------------------------------------------------- a arte
def test_atlas_cobre_toda_combinacao_que_o_retrato_pede():
    folha = vila_nova.atlas()
    assert folha["png"][:4] == b"\x89PNG"
    from painel.flutuante import arte
    esperadas = {f"{nome}|{pose}|{olho}|{direcao}"
                 for nome in arte.LOTES for pose in vila_nova.POSES
                 for olho in vila_nova.OLHOS for direcao in vila_nova.DIRECOES}
    assert esperadas <= set(folha["mapa"])
    larg, alt = folha["larg"], folha["alt"]
    for chave, (x, y) in folha["mapa"].items():
        assert 0 <= x <= folha["tamanho"][0] - larg, chave
        assert 0 <= y <= folha["tamanho"][1] - alt, chave


def test_atlas_e_composto_uma_vez_so():
    vila_nova.atlas()
    inicio = time.monotonic()
    vila_nova.atlas()
    assert time.monotonic() - inicio < 0.05


def test_fundo_de_dia_e_de_noite_sao_diferentes_e_ficam_guardados():
    dia = vila_nova.png_do_fundo(False)
    noite = vila_nova.png_do_fundo(True)
    assert dia[:4] == b"\x89PNG" and noite[:4] == b"\x89PNG"
    assert dia != noite
    inicio = time.monotonic()
    assert vila_nova.png_do_fundo(False) is dia
    assert time.monotonic() - inicio < 0.05


def test_mundo_leva_o_que_o_app_precisa():
    m = vila_nova.mundo()
    assert m["tamanho"] == [704, 240]
    assert "estudio" in m["lotes"] and "casa" in m["portas"]
    assert m["predios"]["picasso"]["rotulo"] and m["predios"]["picasso"]["emoji"]
    assert m["atlas"]["larg"] > 0 and m["atlas"]["mapa"]
    assert m["versao"] and m["versao"] != "0"


# -------------------------------------------------------------- o motor
class _Vida:
    """A vida de mentira: dois habitantes parados, e um diario de chamadas."""

    DESCRICAO = {"sentado": "sentado no banco"}

    def __init__(self, nomes, *a, **k):
        self.habitantes = {
            nome: types.SimpleNamespace(
                nome=nome, pos=[10.0 * i, 20.0], emote="✨",
                emote_ate=time.monotonic() + 60, balao="fazendo algo",
                modo="passeio", atividade="sentado")
            for i, nome in enumerate(nomes)}
        self.aplicados = []
        self.ticks = 0

    def aplicar(self, predios, agora):
        self.aplicados.append(predios)

    def tick(self, dt, agora):
        self.ticks += 1

    def pose(self, h, agora):
        return ("parado", "abertos", "dir", 0.0)

    def posicao_de_desenho(self, h):
        return (h.pos[0], h.pos[1])


@pytest.fixture
def motor(monkeypatch):
    lido = {"vezes": 0}
    vida_falsa = types.SimpleNamespace(Vida=_Vida, DESCRICAO=_Vida.DESCRICAO)
    dados_falsos = types.SimpleNamespace(PREDIOS={"estudio": {}, "picasso": {}})
    monkeypatch.setattr(vila_nova, "_vida", lambda: vida_falsa)
    monkeypatch.setattr(vila_nova, "_dados", lambda: dados_falsos)
    monkeypatch.setattr(vila_nova, "_noite", lambda: False)
    monkeypatch.setattr(vila_nova, "TICK_S", 0.02)
    monkeypatch.setattr(vila_nova, "LEITURA_S", 0.05)
    m = vila_nova.Motor()
    estado = {"estudio": {"status": "trabalhando", "balao": "render",
                          "trabalhos": [{"detalhe": "h36"}], "contas": [],
                          "erro": None},
              "picasso": {"status": "ocioso"}}

    def ler():
        lido["vezes"] += 1
        return dict(estado)
    monkeypatch.setattr(m, "_ler_estado", ler)
    yield types.SimpleNamespace(motor=m, lido=lido, estado=estado)
    m._ultimo_pedido = 0                       # deixa a thread dormir


def _esperar(condicao, prazo=5.0):
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.02)
    return False


def test_retrato_traz_cada_habitante_pronto_para_desenhar(motor):
    r = motor.motor.retrato()
    assert {h["nome"] for h in r["habitantes"]} == {"estudio", "picasso"}
    h = r["habitantes"][0]
    assert h["pose"] == "parado" and h["olhos"] == "abertos"
    assert h["emote"] == "✨" and h["balao"] == "fazendo algo"
    assert h["descricao"] == "sentado no banco"
    assert r["noite"] is False and r["erro_de_leitura"] == ""


def test_o_estado_real_do_diario_entra_na_vida(motor):
    motor.motor.retrato()
    assert _esperar(lambda: motor.motor._vida and motor.motor._vida.aplicados)
    assert motor.motor._vida.aplicados[0]["estudio"]["status"] == "trabalhando"
    r = motor.motor.retrato()
    assert r["predios"]["estudio"]["status"] == "trabalhando"
    assert r["predios"]["estudio"]["trabalhos"] == ["h36"]


def test_a_vida_anda_sozinha_enquanto_alguem_olha(motor):
    motor.motor.retrato()
    assert _esperar(lambda: motor.motor._vida and motor.motor._vida.ticks > 3)


def test_leitura_que_falha_nao_derruba_o_retrato(motor, monkeypatch):
    def quebra():
        raise OSError("diario sumiu")
    monkeypatch.setattr(motor.motor, "_ler_estado", quebra)
    motor.motor.retrato()
    assert _esperar(lambda: motor.motor.retrato()["erro_de_leitura"] == "OSError")
    assert motor.motor.retrato()["habitantes"]        # continua desenhavel


def test_o_motor_dorme_quando_ninguem_olha(motor, monkeypatch):
    monkeypatch.setattr(vila_nova, "PARAR_SEM_PEDIDO_S", 0.1)
    motor.motor.retrato()
    assert _esperar(lambda: motor.motor._vida and motor.motor._vida.ticks > 2)
    vivo = [f for f in threading.enumerate() if f.name == "vila-nova"]
    assert vivo, "a thread da vila deveria estar de pe enquanto olham"
    assert _esperar(lambda: not any(f.name == "vila-nova" and f.is_alive()
                                    for f in threading.enumerate()), 5)
    parou = motor.motor._vida.ticks
    time.sleep(0.2)
    assert motor.motor._vida.ticks == parou       # parou de andar mesmo


def test_olhar_de_novo_acorda_o_motor(motor, monkeypatch):
    monkeypatch.setattr(vila_nova, "PARAR_SEM_PEDIDO_S", 0.1)
    motor.motor.retrato()
    assert _esperar(lambda: not any(f.name == "vila-nova" and f.is_alive()
                                    for f in threading.enumerate()), 5)
    parou = motor.motor._vida.ticks
    motor.motor.retrato()
    assert _esperar(lambda: motor.motor._vida.ticks > parou + 2)


def test_leitura_usa_a_sonda_que_nao_pega_trava(monkeypatch):
    """`_ler_estado` de verdade: ele NAO pode segurar trava de perfil."""
    from builds import travas
    monkeypatch.setattr(travas, "ocupada", lambda nome: pytest.fail(
        "a Vila nao pode chamar travas.ocupada: ela PEGA a trava"))
    monkeypatch.setattr(travas, "trava", lambda *a, **k: pytest.fail(
        "a Vila nao pode pegar trava nenhuma"))
    estado = vila_nova.Motor()._ler_estado()
    assert isinstance(estado, dict) and estado
