# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytest

from coordenador import acoes_pc
from coordenador.__main__ import xml_tarefa
from coordenador.estado import gravar_estado, ler_estado
from coordenador.supervisor import Supervisor, TravaUnica


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 10, 1, 3, 0)

    def __call__(self):
        return self.agora

    def andar(self, segundos):
        self.agora += timedelta(seconds=segundos)


def ficha(nome="app", seguro=False):
    return {nome: {"nome": nome, "assinatura": nome, "comando": [nome], "cwd": ".",
                   "log": "coordenador-teste.log", "janela": "oculta", "modulos": [],
                   "reinicio_seguro": seguro}}


def supervisor(**mais):
    relogio = mais.pop("relogio", Relogio())
    opcoes = {"porta": lambda: True, "carteiro": lambda: {"situacao": "ocioso"},
              "git": lambda *_: False, "avisar": lambda *_: None, "gravar": lambda _: None,
              "log": lambda _: None}
    opcoes.update(mais)
    return Supervisor(servicos=opcoes.pop("servicos", ficha()), relogio=relogio,
                      **opcoes), relogio


def test_adota_existente_sem_duplicar():
    iniciou = []
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                       iniciar=lambda _: iniciou.append(1) or 13)
    s.pulso()
    assert s.estado["app"]["pid"] == 12
    assert iniciou == []


def test_adotado_guarda_a_hora_em_que_o_processo_nasceu():
    # 01/10: adotar com a hora da adocao fez o bot (vivo desde 28/09) sair
    # "codigo em dia"; o codigo velho tem de ser medido contra o nascimento.
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja",
                                          "inicio": "2026-09-28T12:58:17"}])
    s.pulso()
    assert s.estado["app"]["desde"] == "2026-09-28T12:58:17"


def test_religa_com_espera_crescente_e_limite_avisa():
    iniciou, avisos = [], []
    def quebra(_):
        iniciou.append(1)
        raise OSError("nao subiu")
    s, relogio = supervisor(processos=lambda: [{"pid": 4, "comando": "System"}], iniciar=quebra, avisar=avisos.append)
    s.pulso()
    relogio.andar(4); s.pulso()
    assert len(iniciou) == 1
    relogio.andar(1); s.pulso()
    assert len(iniciou) == 2
    for _ in range(4):
        relogio.andar(301); s.pulso()
    assert s.estado["app"]["situacao"] == "falhou"
    assert avisos


def test_codigo_velho_espera_publicacao_e_depois_reinicia():
    processos = [[{"pid": 10, "comando": "app"}, {"pid": 20, "comando": "postar.py"}],
                 [{"pid": 10, "comando": "app"}]]
    parou, iniciou = [], []
    s, _ = supervisor(processos=lambda: processos.pop(0), git=lambda *_: True,
                      parar=parou.append, iniciar=lambda _: iniciou.append(11) or 11)
    s.pulso()
    assert s.estado["app"]["codigo_velho"]
    assert not parou
    s.pulso()
    assert parou == [10] and iniciou == [11]


def test_carteiro_entregando_adia_codigo_velho():
    parou = []
    s, _ = supervisor(servicos=ficha("carteiro", True), processos=lambda: [{"pid": 10, "comando": "carteiro"}],
                      git=lambda *_: True, carteiro=lambda: {"situacao": "entregando"}, parar=parou.append)
    s.pulso()
    assert s.estado["carteiro"]["motivo_espera"] == "carteiro entregando"
    assert not parou


def test_carteiro_entregando_espera_no_maximo_dez_minutos(monkeypatch):
    # 02/10 00:04: "ele nunca vai parar de rodar" - a espera tem teto.
    from coordenador import supervisor as mod
    monkeypatch.setattr(mod.Supervisor, "_interromper_entrega", lambda self: None)
    parou = []
    s, relogio = supervisor(servicos=ficha("carteiro", True), processos=lambda: [{"pid": 10, "comando": "carteiro"}],
                            git=lambda *_: True, carteiro=lambda: {"situacao": "entregando"}, parar=parou.append)
    s.pulso()
    assert not parou
    relogio.andar(mod.ESPERA_ENTREGA_S + 1); s.pulso()
    assert parou == [10]


def test_proibido_para_delegados_sem_parar_servico():
    delegados, parou = [], []
    s, _ = supervisor(processos=lambda: [{"pid": 7, "comando": "app"}], claude_proibido=lambda: "proibido",
                      delegados=lambda: ["a1"], parar_delegado=delegados.append, parar=parou.append)
    s.pulso()
    assert delegados == ["a1"] and parou == [] and s.estado["app"]["situacao"] == "rodando"


def test_comandos_so_os_novos_e_acao_fora_do_catalogo_recusada():
    feitos = []
    fila = [{"id": "1", "comando": "mensagem", "valor": "oi"},
            {"id": "2", "comando": "pc_acao", "valor": "nao-existe"}]
    s, _ = supervisor(processos=lambda: [{"pid": 4, "comando": "System"}], comandos=lambda: fila,
                      aplicar=lambda ident, **kw: feitos.append((ident, kw)))
    s.processar_comandos()
    assert feitos[0][0] == "2" and "recusado" in feitos[0][1]
    assert all(ident != "1" for ident, _ in feitos)


def test_rodar_tarefa_so_prefixos_permitidos():
    chamadas = []
    acoes_pc.executar("rodar_tarefa:NeuralFights_postar_06", rodar=lambda *a, **k: chamadas.append(a))
    assert chamadas
    with pytest.raises(ValueError):
        acoes_pc.executar("rodar_tarefa:Outra")


def test_trava_unica(tmp_path):
    primeira, segunda = TravaUnica(tmp_path / "coordenador.lock"), TravaUnica(tmp_path / "coordenador.lock")
    assert primeira.adquirir() and not segunda.adquirir()
    primeira.soltar()


def test_estado_contrato_atomico(tmp_path, monkeypatch):
    monkeypatch.setenv("NF_COORDENADOR_PASTA", str(tmp_path))
    dados = {"pid": 1, "desde": "x", "pulso_em": "x", "versao": "abc",
             "servicos": {}, "acoes_pc": [], "eventos": []}
    gravar_estado(dados)
    assert ler_estado() == dados


def test_xml_tem_logon_reinicio_e_bateria():
    xml = xml_tarefa("wscript.exe")
    assert "LogonTrigger" in xml and "RestartOnFailure" in xml and "PT1M" in xml
    assert "DisallowStartIfOnBatteries>false" in xml


def test_lista_de_processos_vazia_nao_derruba_nada():
    # 01/10 23:56: a consulta do Windows voltou vazia e o coordenador "religou" tudo.
    iniciou = []
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                      iniciar=lambda _: iniciou.append(1) or 13)
    s.pulso()
    s.processos = lambda: []
    s.pulso()
    assert iniciou == [] and s.estado["app"]["situacao"] == "rodando"


def test_uma_ausencia_so_nao_religa_a_segunda_religa():
    iniciou = []
    vivos = [{"pid": 12, "comando": "app --ja"}]
    s, relogio = supervisor(processos=lambda: list(vivos) + [{"pid": 4, "comando": "System"}],
                            iniciar=lambda _: iniciou.append(1) or 13)
    s.pulso()
    vivos.clear()
    relogio.andar(5); s.pulso()
    assert iniciou == []
    relogio.andar(5); s.pulso()
    relogio.andar(6); s.pulso()
    assert iniciou


def test_trava_de_processo_morto_e_retomada(tmp_path):
    # 02/10: o coordenador morto deixava o .lock e nenhum outro subia mais.
    from coordenador.supervisor import TravaUnica
    caminho = tmp_path / "c.lock"
    caminho.write_text("999999", encoding="utf-8")
    assert TravaUnica(caminho).adquirir(vivo=lambda pid: False)
    caminho.write_text("4242", encoding="utf-8")
    assert not TravaUnica(caminho).adquirir(vivo=lambda pid: True)


# ------------------------------------------------ a esteira de sprites (02/10)
def test_esteira_roda_no_pulso_no_maximo_uma_vez_a_cada_5_min():
    # 02/10: ninguem chamava a esteira e 10 imagens ficaram paradas
    rodadas = []
    s, relogio = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                            esteira=lambda: rodadas.append(1) or {},
                            em_fundo=lambda nome, f: f())
    s.pulso()
    assert rodadas == [1]
    relogio.andar(5); s.pulso()
    relogio.andar(289); s.pulso()
    assert rodadas == [1]
    relogio.andar(6); s.pulso()
    assert rodadas == [1, 1]
    assert s.resumo()["esteira"]["perfis"] == {}


def test_sem_esteira_ligada_o_pulso_nao_chama_nada():
    s, _ = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                      em_fundo=lambda nome, f: (_ for _ in ()).throw(AssertionError(nome)))
    s.pulso()                       # o cerebro e o vigia tambem estao desligados
    assert s.esteira is None and s.ultima_esteira == {}


def test_esteira_so_vira_evento_quando_anda_ou_quebra():
    parado = {"codigo": 0, "andou": 0, "novos": [], "em_voo": 4, "saida": "{}"}
    resultados = [{"palco": dict(parado), "vila": dict(parado)},
                  {"palco": {**parado, "andou": 2, "novos": ["fogo"]},
                   "vila": {**parado, "codigo": 1, "saida": "ValueError: x"}}]
    s, relogio = supervisor(processos=lambda: [{"pid": 12, "comando": "app --ja"}],
                            esteira=lambda: resultados.pop(0),
                            em_fundo=lambda nome, f: f())
    s.pulso()
    assert not [e for e in s.eventos if e["tipo"] == "esteira"]
    relogio.andar(300); s.pulso()
    evento = [e for e in s.eventos if e["tipo"] == "esteira"][-1]["texto"]
    assert "palco: 2 andou, 1 novo(s)" in evento
    assert "vila: 0 andou" in evento and "codigo 1" in evento


def test_ciclo_das_esteiras_chama_palco_e_vila_em_subprocesso():
    import json
    import subprocess

    from coordenador.supervisor import ESTEIRA_PERFIS, ciclo_das_esteiras
    chamadas = []

    def rodar(comando, **kw):
        chamadas.append((comando, kw))
        if "vila" in comando:
            raise subprocess.TimeoutExpired(comando, kw["timeout"])
        linha = json.dumps({"perfil": "palco", "andou": 3, "em_voo": 4, "novos": ["a"]})
        return subprocess.CompletedProcess(comando, 0, stdout="aviso\n" + linha + "\n",
                                           stderr="")

    saida = ciclo_das_esteiras(rodar=rodar, python="py.exe", raiz="E:/x")
    assert ESTEIRA_PERFIS == ("palco", "vila")
    assert [c[0] for c in chamadas] == [
        ["py.exe", "-X", "utf8", "-m", "esteira_sprites", "--perfil", p, "ciclo"]
        for p in ESTEIRA_PERFIS]
    assert all(kw["cwd"] == "E:/x" and kw["timeout"] for _, kw in chamadas)
    assert saida["palco"]["andou"] == 3 and saida["palco"]["novos"] == ["a"]
    assert saida["palco"]["codigo"] == 0 and saida["palco"]["em_voo"] == 4
    assert saida["vila"]["codigo"] is None and saida["vila"]["saida"] == "TimeoutExpired"


def test_ciclo_com_saida_que_nao_e_json_nao_derruba():
    import subprocess

    from coordenador.supervisor import ciclo_das_esteiras
    saida = ciclo_das_esteiras(
        rodar=lambda c, **kw: subprocess.CompletedProcess(c, 1, stdout="",
                                                           stderr="Traceback\nErro: x"),
        python="py.exe")
    assert saida["palco"] == {"codigo": 1, "andou": 0, "novos": [], "em_voo": None,
                              "saida": "Erro: x"}


def test_o_coordenador_de_producao_liga_a_esteira():
    import inspect

    from coordenador import __main__ as principal
    assert "esteira=ciclo_das_esteiras" in inspect.getsource(principal.montar)
