# -*- coding: utf-8 -*-
"""Consertos da auditoria profunda de 11/10 no supervisor (14/10/2026).

COO-9 (claude.json trancado por um instante), COO-12 (pedir_reinicio do
proprio coordenador), COO-13 (suspender olhando o render), COO-14 (trava
unica com pid reaproveitado). Nada toca processo real: o mundo de processos
e o dublê do `test_um_gerente_so`.
"""
import json
import os

import pytest

from coordenador import __main__ as cli
from coordenador import acoes_pc
from coordenador import supervisor as mod
from coordenador.supervisor import TravaUnica
from coordenador.test_um_gerente_so import Mundo, montar
from remoto import orquestrador


# ------------------------------------------------------------ COO-12
def test_pedir_reinicio_coordenador_sai_do_laco(monkeypatch):
    monkeypatch.setattr(mod, "PULSO_S", 0)
    s, _ = montar(Mundo({"pid": 10, "comando": "app"}))
    pulsos = []
    s.pulso = lambda: pulsos.append(1)
    s.pedir_reinicio("coordenador")
    assert s.rodar(parar=lambda: len(pulsos) > 5) == 0
    assert len(pulsos) < 5
    assert any(e["tipo"] == "reinicio_pedido" and "coordenador" in e["texto"]
               for e in s.eventos)


def test_reinicio_do_coordenador_espera_o_momento_seguro(monkeypatch):
    monkeypatch.setattr(mod, "PULSO_S", 0)
    dentro = [True]
    s, _ = montar(Mundo({"pid": 10, "comando": "app"}),
                  janela=lambda _agora: (dentro[0], "janela das postagens (17:07)"))
    pulsos = []

    def pulso():
        pulsos.append(1)
        if len(pulsos) == 3:
            dentro[0] = False
    s.pulso = pulso
    s.pedir_reinicio("coordenador")
    assert s.rodar(parar=lambda: len(pulsos) > 10) == 0
    assert len(pulsos) == 3


def test_reinicio_do_coordenador_espera_a_thread_de_fundo(monkeypatch):
    import threading
    monkeypatch.setattr(mod, "PULSO_S", 0)
    s, _ = montar(Mundo())
    solta = threading.Event()
    s.fundos["vigia"] = threading.Thread(target=solta.wait, daemon=True)
    s.fundos["vigia"].start()
    pulsos = []

    def pulso():
        pulsos.append(1)
        if len(pulsos) == 2:
            solta.set()
            s.fundos["vigia"].join(5)
    s.pulso = pulso
    s.pedir_reinicio("coordenador")
    assert s.rodar(parar=lambda: len(pulsos) > 10) == 0
    assert len(pulsos) == 2


def test_status_curto_diz_codigo_velho(capsys):
    # a outra metade do COO-12 (feita na etapa 2): lia `codigo_velho` na raiz
    from coordenador import estado as estado_mod
    estado_mod.gravar_estado({"servicos": {"app": {"codigo_velho": True}, "bot": {}}})
    cli.main(["status", "--curto"])
    saida = capsys.readouterr().out
    assert "velho" in saida and "app" in saida


# ------------------------------------------------------------ COO-13
@pytest.mark.parametrize("comando", [
    "godot.exe --headless --path E:/projetos/palco --script res://render.gd",
    r"C:\Godot\godot.exe --path palco --fixed-fps 30 --write-movie E:\tmp\luta.avi",
    "ffmpeg -v error -y -i a.avi -c:v libx264 saida.mp4",
    r"python E:\projetos\random_builds\main.py noite",
    r"python E:\projetos\historias\main.py auto",
])
def test_suspender_recusa_com_render(monkeypatch, comando):
    rodou = []
    real = acoes_pc.executar
    monkeypatch.setattr(mod.acoes_pc, "executar",
                        lambda acao, **kw: real(acao, **kw, rodar=lambda *a, **k: rodou.append(a)))
    s, _ = montar(Mundo({"pid": 77, "comando": comando}))
    with pytest.raises(ValueError, match="render"):
        s._executar_acao("suspender")
    assert rodou == []


def test_suspender_sem_render_segue(monkeypatch):
    rodou = []
    real = acoes_pc.executar
    monkeypatch.setattr(mod.acoes_pc, "executar",
                        lambda acao, **kw: real(acao, **kw, rodar=lambda *a, **k: rodou.append(a)))
    s, _ = montar(Mundo({"pid": 77, "comando": "python -m remoto --servidor"},
                        {"pid": 78, "comando": "godot.exe -e --path palco"}))
    assert s._executar_acao("suspender")["ok"] and len(rodou) == 1


# ------------------------------------------------------------ COO-14
def test_trava_com_pid_de_outro_programa_e_retomada(tmp_path):
    caminho = tmp_path / "coordenador.lock"
    criado = orquestrador.hora_de_criacao(os.getpid())
    caminho.write_text(json.dumps({"pid": os.getpid(), "criado": criado - 5000}),
                       encoding="utf-8")
    trava = TravaUnica(caminho)
    assert trava.adquirir() is True
    gravado = json.loads(caminho.read_text(encoding="utf-8"))
    assert gravado["pid"] == os.getpid() and abs(gravado["criado"] - criado) < 1
    trava.soltar()


def test_trava_do_mesmo_processo_e_respeitada(tmp_path):
    caminho = tmp_path / "coordenador.lock"
    primeira = TravaUnica(caminho)
    assert primeira.adquirir()
    segunda = TravaUnica(caminho)
    assert segunda.adquirir() is False and segunda.dono == os.getpid()
    primeira.soltar()


def test_lock_antigo_de_outro_programa_e_retomado(tmp_path):
    caminho = tmp_path / "coordenador.lock"
    caminho.write_text("4242", encoding="utf-8")
    assert TravaUnica(caminho).adquirir(vivo=lambda pid: True,
                                        comando=lambda pid: r"C:\Windows\notepad.exe")


def test_nao_subir_avisa_no_maximo_uma_vez_por_hora(tmp_path, monkeypatch):
    logs = []
    s, _ = montar(Mundo(), log=logs.append)
    monkeypatch.setattr(mod.TravaUnica, "adquirir", lambda self, **k: setattr(self, "dono", 4242))
    assert s.rodar() == 1
    assert s.rodar() == 1
    assert logs == ["[coordenador] trava de 4242 ativa; não subi"]


# ------------------------------------------------------------ COO-9
def test_pulso_nao_para_delegados_por_ilegivel_unico(monkeypatch):
    from remoto import claude_estado
    leituras = iter(["ilegivel", "arquivo"])
    monkeypatch.setattr(claude_estado, "ler", lambda: {
        "liberado": False, "origem": next(leituras), "em": None,
        "motivo": "trancado", "por": "", "texto": ""})
    monkeypatch.setattr(mod, "_LEMBRANCA_CLAUDE", {})
    assert mod.Supervisor._claude_proibido() == ""          # ilegivel uma vez: nao para
    assert "proibido" in mod.Supervisor._claude_proibido().lower()   # proibido de verdade
