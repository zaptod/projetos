# -*- coding: utf-8 -*-
"""A mesa de pedidos nao chama Claude/Codex de verdade (dubles)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from coordenador import pedidos

AGORA = datetime(2026, 10, 3, 10, 20)


class ClaudeFalso:
    def __init__(self, motivo=""):
        self.motivo = motivo

    def motivo_proibido(self):
        return self.motivo


class DespachanteFalso:
    """O `remoto.delegar` de mentira: grava o que pediram, nao abre processo."""

    def __init__(self, pasta):
        self.raiz = pasta
        self.estados, self.criados, self.fundos, self.parados = {}, [], [], []

    def pasta_da(self, ident):
        return self.raiz / ident

    def prompt_do_cargo(self, cargo):
        return f"[cargo {cargo}]"

    def criar(self, ident, arquivo, _permitidos, **kw):
        self.criados.append((ident, kw, arquivo.read_text(encoding="utf-8")))
        ficha = {"id": ident, "situacao": "criado", "atualizado_em": "2026-10-03T10:19:00",
                 "ia": kw.get("ia"), "thread_id": None}
        self.estados[ident] = ficha
        return ficha

    def no_fundo(self, argv, ident):
        self.fundos.append(list(argv))
        self.estados[ident].update(situacao="rodando", atualizado_em="2026-10-03T10:19:30")
        return 1

    def ler_estado(self, ident):
        if ident not in self.estados:
            raise KeyError(ident)
        return self.estados[ident]

    def ler_eventos(self, ident, desde=-1):
        return {"eventos": [{"tipo": "testa", "texto": "python -m pytest remoto -q"}],
                "offset": 10}

    def parar(self, ident):
        self.parados.append(ident)

    def terminar(self, ident, *, arquivos=1, resposta="feito", aplicado=True):
        self.estados[ident].update(situacao="terminou", diff={"arquivos": arquivos},
                                   aplicado={"arquivos": ["remoto/x.py"]} if aplicado else None)
        (self.raiz / ident).mkdir(parents=True, exist_ok=True)
        (self.raiz / ident / "resposta.md").write_text(resposta, encoding="utf-8")


class Relogio:
    def __init__(self):
        self.agora = AGORA

    def __call__(self):
        return self.agora

    def andar(self, **kw):
        self.agora += timedelta(**kw)


@pytest.fixture
def mesa(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path / "coord"))
    avisos = []
    m = pedidos.MesaPedidos(despachante=DespachanteFalso(tmp_path / "delegados"),
                            claude=ClaudeFalso(), relogio=Relogio(),
                            avisar=avisos.append, uso=lambda: {"passou_teto": False})
    m.avisos = avisos
    return m


def _pedido(mesa, ident=None):
    lista = mesa.para_o_app()["pedidos"]
    return next(p for p in lista if p["id"] == ident) if ident else lista[0]


def test_pedido_cria_orquestrador_com_o_texto(mesa):
    p = mesa.registrar("corrija a tela do Agora")
    assert p["situacao"] == "recebido" and mesa.despachante.criados == []   # nada na hora
    mesa.passo()
    ident, kw, tarefa = mesa.despachante.criados[0]
    assert ident == p["id"] and kw["ia"] == "claude" and kw["cargo"] == "orquestrador"
    assert "corrija a tela do Agora" in tarefa
    assert mesa.despachante.fundos == [["rodar", "--id", p["id"]]]
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_continuacao_vai_ao_mesmo_e_novo_assunto_abre_outro(mesa):
    primeiro = mesa.registrar("corrija a tela")
    mesa.passo()
    mesmo = mesa.registrar("e confira no celular")
    assert mesmo["id"] == primeiro["id"] and mesmo["continuacao"] is True
    # rodando: a continuacao espera a rodada acabar (nunca roda no processo)
    mesa.passo()
    assert mesa.despachante.fundos == [["rodar", "--id", primeiro["id"]]]
    mesa.despachante.estados[primeiro["id"]].update(situacao="parado", thread_id="t1")
    mesa.passo()
    ultimo = mesa.despachante.fundos[-1]
    assert ultimo[:3] == ["corrigir", "--id", primeiro["id"]]
    texto = (mesa.despachante.pasta_da(primeiro["id"]) / "continuacao.md").read_text(encoding="utf-8")
    assert "corrija a tela" in texto and "e confira no celular" in texto
    mesa.novo_assunto("telegram")
    outro = mesa.registrar("construa outra coisa")
    assert outro["id"] != primeiro["id"] and outro["continuacao"] is False
    mesa.passo()
    assert [c[0] for c in mesa.despachante.criados] == [primeiro["id"], outro["id"]]


def test_travado_espera_e_e_retomado(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    mesa.relogio.andar(minutes=11)               # nenhum evento desde 10:19:30
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "esperando"
    assert "10 min" in _pedido(mesa)["motivo"]
    assert mesa.despachante.parados == [p["id"]]
    mesa.despachante.estados[p["id"]]["situacao"] = "parado"
    mesa.passo()                                 # ainda dentro do intervalo de retomada
    assert _pedido(mesa)["situacao"] == "esperando"
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "trabalhando"
    assert mesa.despachante.fundos[-1] == ["rodar", "--id", p["id"]]


def test_trabalhador_que_cai_sempre_vira_falhou(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    for _ in range(pedidos.MAX_RETOMADAS + 2):
        mesa.despachante.estados[p["id"]].update(situacao="falhou", motivo="saiu com 1")
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
        mesa.passo()                  # trabalhando -> esperando
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
        mesa.passo()                  # esperando -> retomado (ou falhou)
    assert _pedido(mesa)["situacao"] == "falhou"
    assert mesa.despachante.fundos.count(["rodar", "--id", p["id"]]) == 1 + pedidos.MAX_RETOMADAS
    assert "caiu" in mesa.avisos[-1]


def test_espera_nao_repete_a_linha_a_cada_pulso(mesa):
    mesa.claude.motivo = "Claude proibido pelo Adrian"
    mesa.registrar("me explique o vigia")
    for _ in range(5):
        mesa.passo()
        mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    linhas = [c for c in mesa.para_o_app()["conversa"] if "em espera" in c["texto"]]
    assert len(linhas) == 1


def test_claude_proibido_deixa_pedido_em_espera_e_volta_sozinho(mesa):
    mesa.claude.motivo = "Claude proibido pelo Adrian"
    mesa.registrar("me explique o vigia")
    mesa.passo()
    p = _pedido(mesa)
    assert p["situacao"] == "esperando" and "proibido" in p["motivo"]
    assert mesa.despachante.criados == []
    mesa.claude.motivo = ""
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_teto_do_claude_tambem_espera(mesa):
    mesa.uso = lambda: {"passou_teto": True}
    mesa.registrar("me explique o vigia")
    mesa.passo()
    assert "teto" in _pedido(mesa)["motivo"]


def test_construir_com_claude_proibido_vai_para_codex(mesa):
    mesa.claude.motivo = "Claude proibido"
    p = mesa.registrar("construa a tela X")
    mesa.passo()
    ident, kw, tarefa = mesa.despachante.criados[0]
    assert ident == p["id"] and kw["ia"] == "codex"
    assert tarefa.startswith("[cargo orquestrador]")       # o Codex nao le o cargo sozinho
    assert _pedido(mesa)["situacao"] == "trabalhando"


def test_claude_proibido_no_meio_de_construir_passa_ao_codex(mesa):
    p = mesa.registrar("construa a tela X")
    mesa.passo()
    mesa.despachante.estados[p["id"]].update(situacao="parado", motivo="Claude proibido")
    mesa.claude.motivo = "Claude proibido"
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()                     # parado -> esperando
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()                     # o Codex assume com um trabalhador novo
    mesa.relogio.andar(seconds=pedidos.RETOMAR_S)
    mesa.passo()
    assert [(c[0], c[1]["ia"]) for c in mesa.despachante.criados] == [
        (p["id"], "claude"), (p["id"] + "-1", "codex")]


def test_entrega_aplicada_vai_ao_conferente_e_o_final_chega_ao_telegram(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    mesa.despachante.terminar(p["id"], aplicado=False, resposta="consertei X")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "entregue"
    mesa.passo()
    assert len(mesa.despachante.criados) == 1           # espera o vigia aplicar
    mesa.despachante.estados[p["id"]]["aplicado"] = {"arquivos": ["remoto/x.py"]}
    mesa.passo()
    conf, kw, tarefa = mesa.despachante.criados[1]
    assert conf == "mesa-conf-" + p["id"] and kw["cargo"] == "conferente"
    assert "corrija X" in tarefa and "consertei X" in tarefa
    mesa.despachante.terminar(conf, resposta="APROVADO: testes ok")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "conferido"
    assert mesa.avisos and "consertei X" in mesa.avisos[-1]


def test_conferente_com_defeitos_falha(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    mesa.despachante.terminar(p["id"])
    mesa.passo()
    mesa.passo()
    mesa.despachante.terminar("mesa-conf-" + p["id"], resposta="DEFEITOS: quebrou Y")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "falhou"
    assert "quebrou Y" in mesa.avisos[-1]


def test_so_resposta_sem_codigo_fica_respondido(mesa):
    p = mesa.registrar("por que o vigia parou ontem?")
    mesa.passo()
    mesa.despachante.terminar(p["id"], arquivos=0, aplicado=False, resposta="faltou disco")
    mesa.passo()
    assert _pedido(mesa)["situacao"] == "respondido"
    assert "faltou disco" in mesa.avisos[-1]
    # um pedido encerrado nao recebe continuacao: o proximo texto abre outro
    assert mesa.registrar("outra coisa")["id"] != p["id"]


def test_continuacao_depois_de_aplicado_vai_a_um_orquestrador_novo(mesa):
    p = mesa.registrar("corrija X")
    mesa.passo()
    mesa.despachante.terminar(p["id"], resposta="consertei X")      # o vigia ja aplicou
    mesa.passo()
    mesa.registrar("agora faça Y também")
    mesa.passo()                       # o mesmo nao pode: o aplicar nao reaplica
    mesa.passo()
    novo, kw, tarefa = mesa.despachante.criados[-1]
    assert novo == p["id"] + "-1" and kw["cargo"] == "orquestrador"
    assert "corrija X" in tarefa and "agora faça Y também" in tarefa


def test_veredito_e_a_primeira_palavra():
    assert pedidos._aprovado("APROVADO, nenhum defeito")
    assert not pedidos._aprovado("DEFEITOS: X. Depois de corrigir fica APROVADO")
    assert not pedidos._aprovado("")


def test_progresso_ao_vivo_resumido(mesa):
    mesa.registrar("corrija X")
    mesa.passo()
    mesa.passo()
    textos = [c["texto"] for c in mesa.para_o_app()["conversa"]]
    assert "rodando testes: python -m pytest remoto -q" in textos


def test_pergunta_de_estado_fica_com_o_cerebro():
    assert pedidos.e_de_estado("o app está no ar?")
    assert pedidos.e_de_estado("status")
    assert not pedidos.e_de_estado("corrija o app que não está no ar?")
    assert not pedidos.e_de_estado("faça a aba de pedidos mostrar o status de cada um, com "
                                   "progresso ao vivo e a resposta final do conferente " * 3)
