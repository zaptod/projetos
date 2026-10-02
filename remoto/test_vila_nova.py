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
    # o Grok (29/09): predio, lote e porta, para o balao da resposta dele
    assert m["predios"]["grok"]["rotulo"] == "Grok"
    assert "grok" in m["lotes"] and "grok" in m["portas"]
    assert m["atlas"]["larg"] > 0 and m["atlas"]["mapa"]
    assert m["versao"] and m["versao"] != "0"


def test_celular_recebe_a_vila_dobrada_em_3x_e_o_atlas_em_3x():
    """Nitidez (28/09): nada de ampliar a arte de 1x no celular."""
    from painel.flutuante import retrato
    e = vila_nova.ESCALA_CELULAR
    img = vila_nova.imagem_do_retrato(False)
    assert img[:4] == b"RIFF" and img[8:12] == b"WEBP"
    assert vila_nova.imagem_do_retrato(False) is img          # guardada
    assert vila_nova.imagem_do_retrato(True) != img
    from io import BytesIO

    from PIL import Image
    assert Image.open(BytesIO(img)).size == (retrato.LARGURA * e,
                                             retrato.ALTURA * e)
    folha = vila_nova.atlas(e)
    assert folha["larg"] == 26 * e and folha["escala"] == e
    # os patos do lago vao junto, nos dois lados
    assert {"pato|0|dir", "pato|1|esq"} <= set(folha["mapa"])
    m = vila_nova.mundo()["retrato"]
    assert m["escala"] == e and m["dobra"] == retrato.DOBRA
    assert m["atlas"]["larg"] == 26 * e
    assert m["enquadramento"] in vila_nova.ENQUADRAMENTOS


def test_celular_deitado_recebe_o_mundo_inteiro_numa_fileira():
    """Celular deitado (28/09, vila-zoom-celular): arranjo proprio, em 3x.

    O app converte o mundo pela lista `fileiras` nos dois arranjos; em pe
    sao duas (a dobra), deitado uma so, e o atlas e o mesmo.
    """
    from io import BytesIO

    from PIL import Image

    from painel.flutuante import arte, paisagem
    e = vila_nova.ESCALA_CELULAR
    img = vila_nova.imagem_da_paisagem(False)
    assert img[:4] == b"RIFF" and img[8:12] == b"WEBP"
    assert vila_nova.imagem_da_paisagem(False) is img         # guardada
    assert vila_nova.imagem_da_paisagem(True) != img
    assert Image.open(BytesIO(img)).size == (arte.LARGURA * e,
                                             paisagem.ALTURA * e)
    m = vila_nova.mundo()
    assert m["paisagem"]["fileiras"] == [[0, paisagem.CEU]]
    assert m["paisagem"]["largura"] == arte.LARGURA
    assert m["paisagem"]["escala"] == e
    assert len(m["retrato"]["fileiras"]) == 2


def test_rota_da_vila_deitada_serve_webp(monkeypatch):
    from remoto import api_http
    monkeypatch.setattr(vila_nova, "imagem_da_paisagem", lambda noite: b"RIFFxxxxWEBP")
    corpo = []

    class Falso:
        path = "/vilanova-paisagem.webp?noite=1"
        send_response = send_header = end_headers = (lambda self, *a: None)
        wfile = type("W", (), {"write": lambda self, b: corpo.append(b)})()
        _erro = (lambda self, *a: corpo.append(("erro",) + a))

    api_http.Manipulador._imagem_da_vila(Falso(), "/vilanova-paisagem.webp")
    assert corpo == [b"RIFFxxxxWEBP"]


def test_enquadramento_segue_a_decisao_e_pendente_fica_como_era(
        tmp_path, monkeypatch):
    import json

    from remoto import decisoes
    arquivo = tmp_path / "vila-zoom-celular.json"
    monkeypatch.setattr(decisoes, "caminho_item", lambda p, i: arquivo)
    assert vila_nova.enquadramento() == "perto"                # nao existe
    arquivo.write_text(json.dumps({"vigente": None}), encoding="utf-8")
    assert vila_nova.enquadramento() == "perto"                # pendente
    arquivo.write_text(json.dumps({"vigente": {"opcao": "longe"}}),
                       encoding="utf-8")
    assert vila_nova.enquadramento() == "longe"
    arquivo.write_text("{quebrado", encoding="utf-8")
    assert vila_nova.enquadramento() == "perto"                # ilegivel


# -------------------------------------------------------------- o motor
class _Vida:
    """A vida de mentira: dois habitantes parados, e um diario de chamadas."""

    DESCRICAO = {"sentado": "sentado no banco"}

    def __init__(self, nomes, *a, **k):
        self.habitantes = {
            nome: types.SimpleNamespace(
                nome=nome, pos=[10.0 * i, 20.0], emote="✨",
                emote_ate=time.monotonic() + 60, balao="fazendo algo",
                modo="passeio", atividade="sentado", fase=1.5 * i)
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


def test_thread_acordada_tarde_ainda_da_o_primeiro_tick(motor, monkeypatch):
    """Uma thread que ficou na fila nao pode morrer antes de comecar."""
    m = motor.motor
    m._ultimo_pedido = time.monotonic() - 10
    monkeypatch.setattr(vila_nova, "PARAR_SEM_PEDIDO_S", 1.0)
    monkeypatch.setattr(m, "_ler_estado", lambda: {})
    monkeypatch.setattr(vila_nova.time, "sleep", lambda s: setattr(
        m, "_ultimo_pedido", time.monotonic() - 2))
    m._girar()
    assert m._vida.ticks == 1


def test_leitura_usa_a_sonda_que_nao_pega_trava(monkeypatch):
    """`_ler_estado` de verdade: ele NAO pode segurar trava de perfil."""
    from builds import travas
    monkeypatch.setattr(travas, "ocupada", lambda nome: pytest.fail(
        "a Vila nao pode chamar travas.ocupada: ela PEGA a trava"))
    monkeypatch.setattr(travas, "trava", lambda *a, **k: pytest.fail(
        "a Vila nao pode pegar trava nenhuma"))
    estado = vila_nova.Motor()._ler_estado()
    assert isinstance(estado, dict) and estado

def test_acordar_depois_de_dormir_le_antes_de_responder(motor, monkeypatch):
    # 29/09: depois de horas sem ninguem olhar, o primeiro retrato mostrava os
    # predios de quando o motor dormiu (em 00:55, de 39 min antes)
    m = motor.motor
    m._predios = {"estudio": {"status": "trabalhando", "balao": "render"}}
    m._lido_em = time.monotonic() - 39 * 60
    motor.estado["estudio"] = {"status": "ocioso", "balao": ""}
    monkeypatch.setattr(m, "_acordar", lambda: None)     # so a leitura do pedido
    assert m.retrato()["predios"]["estudio"]["status"] == "ocioso"
    lidas = motor.lido["vezes"]
    m.retrato()                                           # leitura nova: nao rele
    assert motor.lido["vezes"] == lidas


def test_acordar_com_leitura_que_falha_nao_mostra_o_velho(motor, monkeypatch):
    m = motor.motor
    m._predios = {"estudio": {"status": "trabalhando"}}
    m._lido_em = time.monotonic() - 39 * 60

    def quebra():
        raise OSError("diario sumiu")
    monkeypatch.setattr(m, "_ler_estado", quebra)
    monkeypatch.setattr(m, "_acordar", lambda: None)
    r = m.retrato()
    assert r["predios"] == {} and r["erro_de_leitura"] == "OSError"


# ------------------------------------------- a arte da esteira (02/10/2026)
@pytest.fixture
def arte_de_teste(tmp_path):
    """Uma pasta de arte aprovada e um inventario so do teste."""
    import json

    from PIL import Image

    from painel.flutuante import arte_pronta
    pasta = tmp_path / "arte_vila"
    pasta.mkdir()
    anim = {"grade": [4, 4], "ciclos": [
        {"nome": n, "quadros": list(range(4 * i, 4 * i + 4)), "fps": 4, "loop": True}
        for i, n in enumerate(("frente", "esquerda", "direita", "costas"))]}
    itens = [{"nome_arquivo": "predios/casa.png", "tamanho": "no mundo 72x64"},
             {"nome_arquivo": "habitantes/estudio/parado.png",
              "tamanho": "no mundo 26x32", "animacao": anim}]
    inventario = tmp_path / "inventario.json"
    inventario.write_text(json.dumps({"itens": itens}), encoding="utf-8")
    arte_pronta.usar(pasta, inventario)

    def aprovar(nome, tamanho=(256, 256), cor=(200, 40, 40, 255)):
        destino = pasta / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGBA", tamanho, (0, 0, 0, 0))
        img.paste(Image.new("RGBA", (tamanho[0] // 2, tamanho[1] // 2), cor),
                  (tamanho[0] // 4, tamanho[1] // 4))
        img.save(destino)
    yield aprovar
    arte_pronta.usar(None)


def test_peca_aprovada_com_o_servidor_no_ar_troca_o_fundo_e_a_versao(arte_de_teste):
    versao = vila_nova.versao()
    fundo = vila_nova.png_do_fundo(False)
    retrato = vila_nova.imagem_do_retrato(False)
    assert vila_nova.png_do_fundo(False) is fundo           # guardado
    arte_de_teste("predios/casa.png")
    assert vila_nova.versao() != versao                     # o celular rebaixa
    assert vila_nova.png_do_fundo(False) != fundo           # sem reiniciar
    assert vila_nova.imagem_do_retrato(False) != retrato


def test_retrato_e_mundo_dizem_qual_folha_e_qual_ciclo(motor, arte_de_teste):
    arte_de_teste("habitantes/estudio/parado.png")
    r = motor.motor.retrato()
    por_nome = {h["nome"]: h for h in r["habitantes"]}
    assert por_nome["estudio"]["arte"] == {"animacao": "parado", "ciclo": "direita",
                                           "fase": 0.0}
    assert por_nome["picasso"]["arte"] is None              # cai no atlas
    folhas = vila_nova.mundo()["arte"]["habitantes"]
    assert folhas["estudio"]["parado"]["url"].startswith("/arte-vila/habitantes/estudio/parado.png")
    assert folhas["estudio"]["parado"]["ciclos"]["direita"]["quadros"] == [8, 9, 10, 11]
