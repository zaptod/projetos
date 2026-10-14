# -*- coding: utf-8 -*-
"""O apurador entrega diagnosticos a Mesa, sem criar remendo proprio."""
from coordenador import pedidos
from remoto import apurador


def test_mesmo_erro_do_apurador_abre_um_pedido(tmp_path, monkeypatch):
    monkeypatch.setattr(pedidos, "_arquivo", lambda: tmp_path / "pedidos.json")
    mesa = pedidos.MesaPedidos()
    monkeypatch.setattr(pedidos, "MESA", mesa)
    erros = [{"ts": "2026-10-07T20:00:00", "fabrica": "app", "detalhe": "tela caiu"}]
    primeiro = apurador.abrir_pedido(erros, "A tela falha ao abrir.")
    repetido = apurador.abrir_pedido(erros, "Diagnostico refeito.")
    assert primeiro["id"] == repetido["id"] and repetido["duplicado"]
    item = pedidos._ler()["pedidos"]
    assert len(item) == 1 and item[0]["origem"] == "apurador"
    assert "Diagnostico do apurador" in item[0]["texto"]


# ================================ auditoria profunda 11/10 (consertos 14/10)
def _apurador_isolado(tmp_path, monkeypatch):
    import contextlib

    from builds import travas

    @contextlib.contextmanager
    def trava(_nome, esperar=0.0):
        yield True
    monkeypatch.setattr(travas, "trava", trava)
    monkeypatch.setattr(travas, "ocupada", lambda _nome: False)
    monkeypatch.setattr(apurador, "_estado_path", lambda: tmp_path / "apuracoes.json")
    monkeypatch.setattr(apurador, "_alarmar", lambda *_a, **_k: None)


def test_mesa_indisponivel_guarda_a_investigacao(tmp_path, monkeypatch):
    # COO-15: abrir_pedido levantando (trava da Mesa ocupada) subia de
    # uma_volta ("Nunca levanta") com os erros ja marcados: o diagnostico,
    # ja pago, se perdia
    _apurador_isolado(tmp_path, monkeypatch)
    erros = [{"ts": "2026-10-14T10:00:00", "fabrica": "app", "detalhe": "tela caiu"}]
    monkeypatch.setattr(apurador, "pendentes", lambda *a, **k: list(erros))
    monkeypatch.setattr(apurador, "claude_proibido", lambda: "")
    monkeypatch.setattr(apurador, "apurar", lambda erros, log=print: "A tela cai porque X.")

    def mesa_fora(_erros, _texto):
        raise OSError("trava ocupada ha mais de 60 s: pedidos.lock")
    monkeypatch.setattr(apurador, "abrir_pedido", mesa_fora)
    saida = apurador.uma_volta(log=lambda *_a: None)
    assert saida["feito"] is False and "Mesa indisponível" in saida["motivo"]
    pendentes = apurador._ler_estado()["investigacoes_pendentes"]
    assert len(pendentes) == 1 and pendentes[0]["diagnostico"] == "A tela cai porque X."
    # a pendente, de novo com a Mesa fora: continua guardada
    saida = apurador.uma_volta(log=lambda *_a: None)
    assert saida["feito"] is False and len(apurador._ler_estado()["investigacoes_pendentes"]) == 1
    # a Mesa voltou: abre e tira
    monkeypatch.setattr(apurador, "abrir_pedido",
                        lambda _e, _t: {"id": "pedido-x", "recibo": "ok"})
    saida = apurador.uma_volta(log=lambda *_a: None)
    assert saida["feito"] is True and apurador._ler_estado()["investigacoes_pendentes"] == []


def test_estado_corrompido_esgota_apuracoes(tmp_path, monkeypatch):
    # COO-24: o ramo do arquivo ilegivel esgotava os consertos, mas o teto das
    # apuracoes (`por_dia`) recomecava do zero
    _apurador_isolado(tmp_path, monkeypatch)
    (tmp_path / "apuracoes.json").write_text("{corrompido", encoding="utf-8")
    apurador._somar_uma(apurador._ler_estado())
    assert apurador._contagem_de_hoje(apurador._ler_estado()) >= apurador.TETO_DIARIO
