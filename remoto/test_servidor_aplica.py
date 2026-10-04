# -*- coding: utf-8 -*-
"""Os comandos do app aplicados pelo SERVIDOR, sem a sessao do VS Code (04/10/2026).

O Adrian: "tá com um aviso de sessão fechada em relação ao orquestrador,
resolva tudo". Medido as 13:16: o app dizia "Sessao fechada: sem sinal do
orquestrador desde 07:12 (ha 5 h 59 min)" com o selo vermelho, o coordenador
pulsava a cada 5 s, e os comandos do app (capacidade, fila, parar, modelos,
mensagem) so saiam quando a sessao do VS Code rodasse `esperar`/`aplicado`.

Aqui: o pulso do coordenador aplica cada um (com o VS Code fechado), a
mensagem vira pedido, a capacidade vale tambem no despachante, o parar vai ao
despachante, e o que ja foi resolvido por outro nao e aplicado duas vezes.
Tudo em `tmp_path`; nada toca o coordenador, os delegados ou o Telegram reais.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from coordenador import pedidos
from coordenador.supervisor import Supervisor
from remoto import delegar, orquestrador as O
from remoto.test_orquestrador import mundo  # noqa: F401


def _pulso_do_coordenador(**mais):
    """Um supervisor de verdade, so com o que o pulso de comandos usa."""
    # um servico de mentira: vazio, o supervisor leria o servicos.json real
    opcoes = {"servicos": {"app": {"assinatura": "nada"}}, "processos": lambda: [{"pid": 1, "comando": "x"}],
              "avisar": lambda *_: None, "gravar": lambda _: None, "log": lambda _: None,
              "comandos": O.pendentes, "aplicar": O.aplicado,
              "aplicar_app": O.aplicar_pelo_servidor}
    opcoes.update(mais)
    return Supervisor(**opcoes)


def _situacao(cid):
    return next(c for c in O.comandos_com_situacao()[0] if c["id"] == cid)


def test_o_vs_code_esta_fechado_nos_testes(mundo):  # noqa: F811
    # a premissa de todos os testes abaixo: ninguem roda o `esperar`
    assert O.situacao_do_vigia()["situacao"] == "fechada"
    assert O.situacao_do_vscode()["aberto"] is False


def test_capacidade_aplicada_pelo_pulso_sem_sessao_e_no_despachante(mundo):  # noqa: F811
    modo = O.gravar_comando("modo", "paralelo", "614c026b")
    maximo = O.gravar_comando("max_paralelo", 3, "614c026b")
    s = _pulso_do_coordenador()
    s.processar_comandos()
    assert O.pendentes() == []
    config = O.ler_config()
    assert config["modo"] == "paralelo" and config["max_paralelo"] == 3
    # o despachante (os trabalhadores do servidor) segue a mesma capacidade
    assert delegar.ler_config()["delegados_paralelo"] == 3
    linha = _situacao(maximo["id"])
    assert linha["situacao"] == "aplicado"
    assert "despachante: até 3 trabalhador(es) ao mesmo tempo" in linha["nota"]
    assert _situacao(modo["id"])["situacao"] == "aplicado"
    # a linha do tempo diz quem aplicou
    movimento = O.ler_estado()["principal"]["movimento"]
    assert movimento.startswith("o servidor aplicou agentes em paralelo: 3")
    # um evento por comando no coordenador
    assert [e["tipo"] for e in s.eventos].count("comando") == 2


def test_fila_e_modelos_aplicados_pelo_pulso(mundo):  # noqa: F811
    O.gravar_comando("pausar_fila", None, "614c026b")
    O.gravar_comando("modelo_codex", None, "614c026b")
    O.gravar_comando("modelo_agentes", "sonnet", "614c026b")
    _pulso_do_coordenador().processar_comandos()
    config = O.ler_config()
    assert O.pendentes() == [] and config["fila_pausada"] is True
    assert config["modelo_agentes"] == "sonnet"
    assert delegar.ler_config()["modelo_claude"] == "sonnet"
    O.gravar_comando("retomar_fila", None, "614c026b")
    _pulso_do_coordenador().processar_comandos()
    assert O.ler_config()["fila_pausada"] is False


def test_mensagem_para_o_orquestrador_vira_pedido(mundo):  # noqa: F811
    c = O.gravar_comando("mensagem", "conserte o relatório das 21h", "614c026b")
    _pulso_do_coordenador().processar_comandos()
    linha = _situacao(c["id"])
    assert linha["situacao"] == "aplicado"
    vivos = [p for p in pedidos.para_o_app()["pedidos"] if p["situacao"] == "recebido"]
    assert len(vivos) == 1 and vivos[0]["texto"] == "conserte o relatório das 21h"
    assert vivos[0]["origem"] == "app"
    assert f"virou o pedido {vivos[0]['id']}" in linha["nota"]
    # a segunda mensagem continua o mesmo pedido (como o Pedir do app)
    c2 = O.gravar_comando("mensagem", "e mande no Telegram", "614c026b")
    _pulso_do_coordenador().processar_comandos()
    assert "continuação" in _situacao(c2["id"])["nota"]
    assert len(pedidos.para_o_app()["pedidos"]) == 1
    # nada disso precisou do VS Code nem do Claude
    assert O.situacao_do_vigia()["situacao"] == "fechada"


def test_mensagem_com_o_claude_proibido_tambem_vira_pedido(mundo):  # noqa: F811
    from remoto import claude_estado
    claude_estado.mudar(False, por="teste")
    c = O.gravar_comando("mensagem", "olhe o carteiro", "614c026b")
    _pulso_do_coordenador().processar_comandos()
    assert _situacao(c["id"])["situacao"] == "aplicado"
    assert pedidos.para_o_app()["pedidos"][0]["texto"] == "olhe o carteiro"


class _Despachante:
    def __init__(self, rodando=("pedido-cd2e5e0c",)):
        self.rodando, self.parados = set(rodando), []

    def ler_estado(self, ident):
        if ident not in self.rodando:
            raise delegar.Recusa(f"não existe a tarefa delegada {ident}")
        return {"id": ident, "situacao": "rodando"}

    def parar(self, ident):
        self.parados.append(ident)
        return f"pedido de parar gravado; o despachante para {ident} em ~2 s"

    def ler_config(self):
        return {"delegados_paralelo": 1}

    def gravar_config(self, mudancas):
        return mudancas


def test_parar_trabalhador_do_servidor(mundo):  # noqa: F811
    c = O.gravar_comando("parar_agente", "pedido-cd2e5e0c", "614c026b")
    d = _Despachante()
    linha = O.aplicar_pelo_servidor(_situacao(c["id"]), despachante=d)
    assert d.parados == ["pedido-cd2e5e0c"]
    assert linha["resultado"] == "aplicado" and "pedido de parar gravado" in linha["nota"]


def test_parar_agente_da_mesa_com_o_vs_code_fechado_fecha_como_parado(mundo):  # noqa: F811
    agente = O.agente_inicio("builds", "re-render da 00077", forcar=True)
    c = O.gravar_comando("parar_agente", agente["id"], "614c026b")
    linha = O.aplicar_pelo_servidor(_situacao(c["id"]), despachante=_Despachante(()))
    assert linha["resultado"] == "aplicado" and "fechado como parado" in linha["nota"]
    estado = O.ler_estado()
    assert estado["agora"] == []
    assert estado["concluidos_hoje"][-1]["situacao"] == "parado"


def test_parar_agente_da_mesa_com_o_vs_code_aberto_fica_parando(mundo):  # noqa: F811
    agente = O.agente_inicio("builds", "re-render da 00077", forcar=True)
    c = O.gravar_comando("parar_agente", agente["id"], "614c026b")
    linha = O.aplicar_pelo_servidor(_situacao(c["id"]), despachante=_Despachante(()),
                                    vscode_aberto=True)
    assert "parando" in linha["nota"]
    assert O.ler_estado()["agora"][0]["situacao"] == "parando"


def test_parar_quem_nao_existe_e_recusado_com_o_motivo(mundo):  # noqa: F811
    c = O.gravar_comando("parar_agente", "ninguem", "614c026b")
    linha = O.aplicar_pelo_servidor(_situacao(c["id"]), despachante=_Despachante(()))
    assert linha["resultado"] == "recusado"
    assert _situacao(c["id"])["motivo"] == "nenhum trabalhador nem agente com o id ninguem"


def test_o_que_ja_foi_resolvido_nao_e_aplicado_de_novo(mundo):  # noqa: F811
    c = O.gravar_comando("pausar_fila", None, "614c026b")
    O.aplicado(c["id"], nota="pela CLI")              # o VS Code aplicou antes
    assert O.aplicar_pelo_servidor(dict(c, situacao="pendente")) is None
    aplicados = O._ler_jsonl(O.arquivo("comandos_aplicados.jsonl"))[0]
    assert [a["id"] for a in aplicados] == [c["id"]]


def test_servico_e_acao_do_pc_ficam_com_o_supervisor(mundo):  # noqa: F811
    c = O.gravar_comando("servico_reiniciar", "app", "614c026b")
    assert O.aplicar_pelo_servidor(_situacao(c["id"])) is None
    assert _situacao(c["id"])["situacao"] == "pendente"


def test_erro_de_disco_deixa_pendente_e_avisa_uma_vez(mundo, monkeypatch):  # noqa: F811
    c = O.gravar_comando("mensagem", "oi", "614c026b")

    def disco_cheio(_texto, *_a, **_k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(pedidos, "registrar", disco_cheio)
    s = _pulso_do_coordenador()
    s.processar_comandos()
    s.processar_comandos()
    assert _situacao(c["id"])["situacao"] == "pendente"
    erros = [e for e in s.eventos if e["tipo"] == "comando_erro"]
    assert len(erros) == 1 and "No space left" in erros[0]["texto"]


# ================================================= o que a tela mostra
def _coordenador(mundo, segundos_atras):
    pasta = mundo.tmp / "coordenador"
    pasta.mkdir(parents=True, exist_ok=True)
    pulso = datetime.fromtimestamp(datetime.now().timestamp() - segundos_atras)
    (pasta / "estado.json").write_text(json.dumps(
        {"pid": 11840, "pulso_em": pulso.isoformat(timespec="seconds")}), encoding="utf-8")


def test_coordenador_vivo_sem_aviso_de_sessao_fechada(mundo):  # noqa: F811
    _coordenador(mundo, 4)
    pedidos.registrar("um pedido em andamento", "app")
    tela = O.para_o_app()
    s = tela["servidor"]
    assert s["situacao"] == "ok" and s["alarmes"] == [] and tela["fora_do_ar"] is False
    assert s["pedidos"] == 1 and s["trabalhadores"] == 0
    assert s["resumo"] == ("1 pedido(s) em andamento · 0 trabalhador(es) rodando · "
                           "comandos: todos aplicados")
    assert s["vscode"]["texto"].startswith("VS Code: fechado")
    assert "Sessão fechada" not in json.dumps(tela, ensure_ascii=False)


def test_coordenador_sem_pulso_ha_mais_de_2_min_e_alarme(mundo):  # noqa: F811
    _coordenador(mundo, 121)
    s = O.situacao_do_servidor()
    assert s["situacao"] == "sem_pulso" and s["alarmes"] == [s["texto"]]
    _coordenador(mundo, 100)
    assert O.situacao_do_servidor()["alarmes"] == []


def test_trabalhador_travado_e_teto_sao_alarme(mundo):  # noqa: F811
    _coordenador(mundo, 2)
    travado = {"id": "pedido-x", "titulo": "o relatório", "situacao": "sumiu",
               "motivo_travado": "o processo sumiu sem desfecho"}
    s = O.situacao_do_servidor(trabalhadores=([], [travado]),
                               uso={"passou_teto": True, "teto": 50,
                                    "medicao": {"sessao_pct": 62}})
    assert s["situacao"] == "ok" and s["travados"][0]["id"] == "pedido-x"
    assert any("Trabalhador travado: pedido-x" in a for a in s["alarmes"])
    assert any("passou do teto de uso (62% da sessão, teto 50%)" in a for a in s["alarmes"])


def test_trabalhador_rodando_sem_evento_ha_15_min_e_travado(mundo, monkeypatch):  # noqa: F811
    antigo = datetime.fromtimestamp(datetime.now().timestamp() - 16 * 60)
    lista = [{"id": "a1", "situacao": "rodando", "titulo": "t",
              "ultimo_evento_em": antigo.isoformat(timespec="seconds")},
             {"id": "a2", "situacao": "rodando", "titulo": "t",
              "ultimo_evento_em": datetime.now().isoformat(timespec="seconds")}]
    monkeypatch.setattr(delegar, "listar", lambda: lista)
    monkeypatch.setattr(delegar, "_vivo_para_tela", lambda e: e)
    rodando, travados = O._trabalhadores_do_servidor(datetime.now().timestamp())
    assert [t["id"] for t in rodando] == ["a1", "a2"]
    assert [t["id"] for t in travados] == ["a1"]
    assert travados[0]["motivo_travado"].startswith("sem evento há 16 min")


def test_vs_code_aberto_aparece_sem_alarme(mundo, monkeypatch):  # noqa: F811
    _coordenador(mundo, 2)
    O.eu("conferindo a Arena")
    vscode = O.situacao_do_vscode()
    assert vscode["aberto"] is True and vscode["relato"] == "conferindo a Arena"
    assert O.situacao_do_servidor()["alarmes"] == []


def test_vs_code_fechado_ha_dias_diz_a_data_do_ultimo_sinal(mundo):  # noqa: F811
    # medido em 04/10: o ultimo relato da sessao era de 03/10 16:06, e a linha
    # dizia so "16:06" (parecia hoje)
    vigia = {"situacao": "fechada", "pulso_em": "2026-10-02T12:19:03"}
    estado = {"principal": {"relato_em": "2026-10-03T16:06:25"}}
    agora = datetime(2026, 10, 4, 13, 16).timestamp()
    v = O.situacao_do_vscode(agora, estado, vigia)
    assert v["aberto"] is False and v["texto"] == "VS Code: fechado (último sinal 03/10 16:06)"


def test_cli_servidor(mundo, capsys):  # noqa: F811
    assert O.main(["servidor"]) == 1
    assert "nunca" in capsys.readouterr().out
    _coordenador(mundo, 1)
    assert O.main(["servidor"]) == 0
    saida = capsys.readouterr().out
    assert saida.startswith("ok: Servidor no ar") and "VS Code: fechado" in saida


@pytest.mark.parametrize("arquivo", ["orquestrador.js", "decisoes.js", "app.js", "index.html"])
def test_a_casca_nao_fala_mais_da_sessao_como_o_orquestrador(arquivo):
    texto = (O.RAIZ / "remoto" / "app" / arquivo).read_text(encoding="utf-8")
    for velho in ("sessão fechada", "voltar a ouvir", "orquestrador voltar",
                  "Ninguém está ouvindo", "o orquestrador não está ouvindo",
                  "ficam guardados", "esperando o orquestrador"):
        assert velho not in texto, f"{arquivo} ainda diz «{velho}»"
