# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ias import assembleia, correio


@pytest.fixture(autouse=True)
def pasta_temporaria(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("NF_IAS_PASTA", str(Path(tmp) / "ias"))
        yield


CONTEXTO = "Esta decisao muda a forma de trabalhar no projeto e precisa explicar os riscos, " \
           "as alternativas consideradas e a consequencia concreta para as proximas entregas."


def _responder(ident, ia, texto):
    dados = assembleia.ver(ident)
    rodada = dados["rodada_1"] if dados["situacao"] == "rodada_1" else dados["rodada_2"]
    correio.atualizar(ia, rodada["mensagens"][ia], situacao="respondida", resposta=texto)


def test_abrir_manda_primeira_rodada_com_contexto_e_blocos():
    ident = assembleia.abrir("Qual caminho?", ["a=Fazer A|rapido"], ["gemini", "grok"], contexto=CONTEXTO)
    dados = assembleia.ver(ident)
    assert dados["situacao"] == "rodada_1"
    texto = correio.ler("gemini")[0]["texto"]
    for bloco in ("QUEM VOCE E AQUI", "O PROJETO", "A DECISAO", "AS OPCOES", "PARA QUE SERVE A SUA RESPOSTA"):
        assert bloco in texto
    with pytest.raises(assembleia.Recusa, match="80"):
        assembleia.abrir("x", contexto="curto")


def test_avancar_sem_resposta_nao_duplica():
    ident = assembleia.abrir("Qual caminho?", ["a=Fazer A"], ["gemini", "grok"], contexto=CONTEXTO)
    assembleia.avancar(); assembleia.avancar()
    assert assembleia.ver(ident)["situacao"] == "rodada_1"
    assert len(correio.ler("gemini")) == 1


def test_sem_opcoes_junta_propostas_parecidas_antes_do_voto():
    ident = assembleia.abrir("Qual caminho?", participantes=["gemini", "grok"], contexto=CONTEXTO)
    _responder(ident, "gemini", '{"voto":"","por_que":"a","risco":"b","propostas":[{"rotulo":"Fila unica","descricao":"central"}]}')
    _responder(ident, "grok", '{"voto":"","por_que":"a","risco":"b","propostas":[{"rotulo":"Fila unica","descricao":"igual"},{"rotulo":"Filas separadas","descricao":"paralelo"}]}')
    assembleia.avancar()
    assert [o["rotulo"] for o in assembleia.ver(ident)["opcoes"]] == ["Fila unica", "Filas separadas"]


def test_respostas_abrem_debate_anonimo_e_fecham_com_ata(monkeypatch):
    ident = assembleia.abrir("Qual caminho?", ["a=Fazer A", "b=Fazer B"], ["gemini", "grok"], contexto=CONTEXTO)
    _responder(ident, "gemini", '{"voto":"a","por_que":"melhor","risco":"custo","propostas":[]}')
    _responder(ident, "grok", '{"voto":"b","por_que":"seguro","risco":"lento","propostas":[]}')
    assembleia.avancar()
    dados = assembleia.ver(ident)
    assert dados["situacao"] == "rodada_2"
    debate = correio.ler("gemini")[-1]["texto"]
    assert "Participante A" in debate and "grok" not in debate
    _responder(ident, "gemini", '{"voto":"a","mudou":false,"por_que":"melhor","resposta_ao_mais_forte":"nao"}')
    _responder(ident, "grok", '{"voto":"a","mudou":true,"por_que":"concordo","resposta_ao_mais_forte":"nao"}')
    chamado = []
    monkeypatch.setattr("remoto.decisoes.adicionar_e_commitar", lambda *a, **k: (chamado.append((a, k)) or ({"id": "no"}, "ok")))
    monkeypatch.setattr(assembleia, "_registrar_evento", lambda dados: None)
    monkeypatch.setattr(assembleia, "_avisar", lambda dados: None)
    assembleia.avancar(); assembleia.avancar()
    dados = assembleia.ver(ident)
    assert dados["ata"]["consenso"] == "unanime"
    assert dados["ata"]["contagem"]["a"] == 2
    assert dados["decisao_id"] == "no" and len(chamado) == 1
    assert "assembleia 2 de 2" in chamado[0][0][3][0]["rotulo"]


def test_abstencao_e_ausencia_nao_travam_e_sem_quorum(monkeypatch):
    ident = assembleia.abrir("Qual caminho?", ["a=Fazer A"], ["gemini", "grok"], contexto=CONTEXTO)
    _responder(ident, "gemini", "nao consegui responder em json")
    dados = assembleia.ver(ident)
    dados["rodada_1"]["aberta_em"] = "2000-01-01T00:00:00"; assembleia._gravar(dados)
    monkeypatch.setattr(assembleia, "_registrar_evento", lambda dados: None)
    monkeypatch.setattr(assembleia, "_avisar", lambda dados: None)
    monkeypatch.setattr("remoto.decisoes.adicionar_e_commitar", lambda *a, **k: ({"id": "no"}, "ok"))
    assembleia.avancar()
    dados = assembleia.ver(ident)
    assert dados["rodada_1"]["respostas"]["gemini"]["situacao"] == "abstencao"
    assert assembleia.ver(ident)["ata"]["consenso"] == "sem quorum"
