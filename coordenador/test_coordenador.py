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
