# -*- coding: utf-8 -*-
"""O interruptor do Claude (29/09/2026): liberado ou proibido.

Pedido do Adrian: "usar o Claude está proibido até segunda ordem, crie algo
no app para ligar e desligar isso". Quem obedece: a sonda de uso do servidor,
o apurador do bot, o `agente-inicio` e o `esperar` do orquestrador.

NENHUM teste chama o Claude de verdade: a sonda recebe um `rodar` que falha
o teste se for chamado, o apurador tem o `subprocess` trocado por bomba, e o
Telegram e o `acoes._entregar` do fixture `mundo`. O `claude.json` de cada
teste mora na pasta dele (`remoto/conftest.py`).
"""
from __future__ import annotations

import json
import types

import pytest

from remoto import acoes, apurador, claude_estado as C, orquestrador as O
from remoto.test_orquestrador import (_parear, _pedir, _saida_falsa, mundo,  # noqa: F401
                                      servidor)


def _bomba(*_a, **_k):
    pytest.fail("chamou o Claude com o Claude proibido")


def _proibir(motivo="até segunda ordem"):
    return C.mudar(False, por="teste", motivo=motivo)


# ================================================================ caso ZERO
def test_caso_zero_sem_arquivo_e_liberado_e_fica_registrado():
    assert not C.caminho().exists()
    estado = C.ler()
    assert estado["liberado"] is True and estado["origem"] == "sem_arquivo"
    assert estado["texto"] == "Claude liberado (nunca foi mudado)"
    assert C.motivo_proibido() == ""
    # "arquivo ausente = liberado, mas registre": uma linha no histórico
    historico = C.historico()
    assert len(historico) == 1 and "ausente" in historico[0]["motivo"]
    C.ler()
    assert len(C.historico()) == 1           # uma vez, não a cada leitura
    # e o caso ZERO não cria o claude.json
    assert not C.caminho().exists()
    tela = C.para_o_app()
    assert tela["liberado"] is True and tela["em"] is None and tela["desde_hhmm"] == ""


def test_ilegivel_e_proibido_falha_fechado():
    C.caminho().parent.mkdir(parents=True, exist_ok=True)
    for conteudo in ("{meio arquivo", '{"liberado": "sim"}', "[]"):
        C.caminho().write_text(conteudo, encoding="utf-8")
        estado = C.ler()
        assert estado["liberado"] is False and estado["origem"] == "ilegivel", conteudo
        assert C.motivo_proibido().startswith("Claude proibido:")


def test_proibir_e_liberar_gravam_atomico_e_com_historico():
    feito = _proibir()
    assert feito["mudou"] is True and feito["antes"] is True
    dados = json.loads(C.caminho().read_text(encoding="utf-8"))
    assert dados["liberado"] is False and dados["por"] == "teste"
    assert dados["motivo"] == "até segunda ordem" and dados["em"]
    hhmm = C.hhmm(dados["em"])
    assert C.motivo_proibido() == f"Claude proibido pelo Adrian desde {hhmm}"
    assert C.ler()["texto"].startswith(f"Claude proibido desde {hhmm} por teste")
    # o toque repetido não vira outra linha nem outro "em"
    de_novo = _proibir()
    assert de_novo["mudou"] is False
    assert json.loads(C.caminho().read_text(encoding="utf-8"))["em"] == dados["em"]
    volta = C.mudar(True, por="app")
    assert volta["mudou"] is True and C.liberado() is True
    linhas = C.historico()
    assert [l["liberado"] for l in linhas[:2]] == [True, False]
    assert not list(C.caminho().parent.glob(".*.tmp"))      # nada pela metade


def test_o_caminho_de_teste_da_instancia_8934(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "ARQUIVO", None)
    monkeypatch.setenv("NF_CLAUDE_ESTADO", str(tmp_path / "outro" / "claude.json"))
    assert C.caminho() == tmp_path / "outro" / "claude.json"
    assert C.caminho_historico() == tmp_path / "outro" / "claude_historico.jsonl"


# ================================================================ a sonda
def test_sonda_parada_nao_chama_o_claude_e_a_tela_nao_mostra_numero(mundo):  # noqa: F811
    O.sondar(_saida_falsa(0.34))              # uma medição de antes
    assert O.ler_uso()["situacao"] == "ok"
    _proibir()
    registro = O.sondar(_bomba)
    assert registro["parada"].startswith("sonda parada: Claude proibido pelo Adrian desde")
    uso = O.ler_uso()
    assert uso["situacao"] == "parada" and uso["medicao"] is None
    assert uso["motivo"] == f"sonda parada: Claude proibido desde {C.ler()['em'][11:16]}"
    assert uso["desde"] is not None and uso["passou_teto"] is False
    # a falha não foi gravada como falha da sonda: o uso.json é o de antes
    assert json.loads(O.arquivo("uso.json").read_text(encoding="utf-8"))["falhas_seguidas"] == 0
    tela = O.para_o_app()
    assert tela["uso"]["situacao"] == "parada" and tela["claude"]["liberado"] is False
    # liberou: volta a medir
    C.mudar(True, por="teste")
    assert O.sondar(_saida_falsa(0.40))["medicao"]["sessao_pct"] == 40.0
    assert O.ler_uso()["situacao"] == "ok"


def test_o_laco_da_sonda_pula_com_o_claude_proibido(mundo, monkeypatch):  # noqa: F811
    _proibir()
    monkeypatch.setattr(O, "sondar", _bomba)
    voltas = []

    class _Evento:
        def is_set(self):
            return len(voltas) >= 2

        def wait(self, _s):
            voltas.append(1)

    sonda = O._Sonda()
    sonda._parar = _Evento()
    sonda._laco()
    assert len(voltas) == 2                  # rodou o laço, e não sondou


def test_cli_sonda_com_o_claude_proibido(mundo, capsys, monkeypatch):  # noqa: F811
    _proibir()
    monkeypatch.setattr(O, "medir", _bomba)
    assert O.main(["sonda"]) == 2
    assert "sonda parada: Claude proibido" in capsys.readouterr().err


# ============================================================= o apurador
def _erro():
    return {"ts": "2026-09-29T13:00:00", "fabrica": "historias", "canal": "historias",
            "status": "erro", "detalhe": "quebrou"}


def test_apurador_pulado_registra_no_diario_e_nao_marca(monkeypatch):
    _proibir()
    registrados, marcados = [], []
    monkeypatch.setattr(apurador, "pendentes", lambda *a, **k: [_erro()])
    monkeypatch.setattr(apurador, "marcar", marcados.append)
    monkeypatch.setattr(apurador.subprocess, "run", _bomba)
    monkeypatch.setattr(apurador.subprocess, "Popen", _bomba)
    monkeypatch.setattr(apurador, "_rodar_claude", _bomba)
    from builds import atividade
    monkeypatch.setattr(atividade, "registrar",
                        lambda *a, **k: registrados.append(a))
    saida = apurador.uma_volta(log=lambda *_a: None)
    assert saida["feito"] is False and saida["pulada"] is True
    assert saida["motivo"].startswith("apuração pulada: Claude proibido pelo Adrian desde")
    assert registrados == [("apurador", "log", saida["motivo"], "builds")]
    assert marcados == []                    # os erros ficam para quando liberar
    # os dois pontos que chamam o Claude também recusam sozinhos
    assert apurador.apurar([_erro()], log=lambda *_a: None) is None
    conserto = apurador.consertar([_erro()], "diag", log=lambda *_a: None)
    assert conserto["mexeu"] is False and "Claude proibido" in conserto["motivo"]


def test_apurador_liberado_segue_como_antes(monkeypatch):
    chamou = []
    monkeypatch.setattr(apurador, "caminho_do_claude", lambda: "claude-falso.exe")
    monkeypatch.setattr(apurador, "_ler_estado", lambda: {})
    monkeypatch.setattr(apurador, "_somar_uma", lambda _e: None)
    monkeypatch.setattr(apurador.subprocess, "run", lambda *a, **k: chamou.append(a)
                        or types.SimpleNamespace(returncode=0, stdout="diagnóstico",
                                                 stderr=""))
    assert apurador.apurar([_erro()], log=lambda *_a: None) == "diagnóstico"
    assert len(chamou) == 1


# ========================================================== o orquestrador
def test_agente_inicio_recusado_com_e_sem_forcar(mundo, capsys):  # noqa: F811
    assert O.main(["agente-inicio", "--parte", "builds", "--titulo", "antes"]) == 0
    capsys.readouterr()
    _proibir()
    hhmm = C.ler()["em"][11:16]
    for extra in ([], ["--forcar"]):
        codigo = O.main(["agente-inicio", "--parte", "builds", "--titulo", "x", *extra])
        erro = capsys.readouterr().err
        assert codigo == 3, extra
        assert f"Claude proibido pelo Adrian desde {hhmm}" in erro, extra
    assert [a["titulo"] for a in O.ler_estado()["agora"]] == ["antes"]
    C.mudar(True, por="teste")
    # liberado, volta a valer só a capacidade (um por vez: já há um)
    assert O.main(["agente-inicio", "--parte", "builds", "--titulo", "depois"]) == 3
    assert "Claude" not in capsys.readouterr().err
    assert O.main(["agente-inicio", "--parte", "builds", "--titulo", "depois",
                   "--forcar"]) == 0


def test_esperar_segura_os_comandos_e_so_sai_no_liberar(mundo, capsys):  # noqa: F811
    O.gravar_comando("max_paralelo", 2, "celular")
    _proibir()
    voltas = []

    def dormir(_s):
        voltas.append(1)
        # enquanto proibido: o comando continua pendente, e o vigia diz
        # que está ouvindo mas segurando
        assert len(O.pendentes()) == (1 if len(voltas) <= 2 else 2)
        vigia = json.loads(O.arquivo("vigia.json").read_text(encoding="utf-8"))
        assert vigia["situacao"] == "ouvindo" and "Claude proibido" in vigia["segurando"]
        if len(voltas) == 2:
            O.gravar_comando("pausar_fila", None, "celular")   # chega outro
        if len(voltas) == 4:
            C.mudar(True, por="pelo app (moto)")

    relogio = iter(range(0, 10_000, 5))
    assert O.esperar(0, como_json=True, relogio=lambda: next(relogio),
                     dormir=dormir) == 0
    assert len(voltas) == 4
    saida = json.loads(capsys.readouterr().out)
    assert saida[0]["tipo"] == "claude_liberado" and saida[0]["por"] == "pelo app (moto)"
    assert [c["comando"] for c in saida[1:]] == ["max_paralelo", "pausar_fila"]
    assert all(c["tipo"] == "comando" for c in saida[1:])
    # os comandos continuam pendentes: quem aplica é o orquestrador acordado
    assert len(O.pendentes()) == 2
    vigia = json.loads(O.arquivo("vigia.json").read_text(encoding="utf-8"))
    assert vigia["situacao"] == "saiu" and vigia["motivo"] == "claude_liberado"


def test_esperar_proibido_no_meio_nao_acorda_com_comando(mundo, capsys):  # noqa: F811
    _proibir()
    voltas = []

    def dormir(_s):
        voltas.append(1)
        if len(voltas) == 1:
            O.gravar_comando("pausar_fila", None, "celular")
        if len(voltas) == 3:
            C.mudar(True, por="teste")

    relogio = iter(range(0, 10_000, 5))
    O.esperar(0, como_json=True, relogio=lambda: next(relogio), dormir=dormir)
    assert len(voltas) == 3                  # nem o comando da volta 1 acordou
    saida = json.loads(capsys.readouterr().out)
    assert [s["tipo"] for s in saida] == ["claude_liberado", "comando"]


def test_esperar_acorda_na_hora_quando_ele_proibe_no_meio(mundo, capsys):  # noqa: F811
    # 30/09: ele proibiu às 12:11 e os agentes seguiram até 12:57, porque o
    # `esperar` que começou liberado só segurava calado. A proibição é ordem
    # de parar: sai uma vez com claude_proibido, sem levar comando junto.
    voltas = []

    def dormir(_s):
        voltas.append(1)
        if len(voltas) == 2:
            O.gravar_comando("pausar_fila", None, "celular")
            _proibir()

    relogio = iter(range(0, 10_000, 5))
    assert O.esperar(0, como_json=True, relogio=lambda: next(relogio),
                     dormir=dormir) == 0
    assert len(voltas) == 2
    saida = json.loads(capsys.readouterr().out)
    assert [s["tipo"] for s in saida] == ["claude_proibido"]
    assert "proibido" in saida[0]["texto"].lower()
    assert len(O.pendentes()) == 1           # o comando fica para o liberar
    vigia = json.loads(O.arquivo("vigia.json").read_text(encoding="utf-8"))
    assert vigia["situacao"] == "saiu" and vigia["motivo"] == "claude_proibido"


def test_com_o_claude_proibido_o_servidor_aplica_os_comandos_mesmo_assim(mundo):  # noqa: F811
    """Desde 04/10 quem aplica e o pulso do servidor, que nao usa o Claude:
    nada fica "guardado" esperando liberar (antes o `esperar` segurava)."""
    comando = O.gravar_comando("pausar_fila", None, "celular")
    _proibir()
    linha = O.aplicar_pelo_servidor(dict(comando))
    assert linha["resultado"] == "aplicado"
    assert O.ler_config()["fila_pausada"] is True and O.pendentes() == []
    servidor = O.situacao_do_servidor(coordenador={"pulso_em": O._agora_iso()})
    assert servidor["comando_parado"] is None and servidor["alarmes"] == []
    assert O._AvisoSemOuvinte.verificar(O.time.time() + 600, avisar=pytest.fail,
                                        coordenador={"pulso_em": O._agora_iso()}) is None


def test_cli_claude_status_proibir_liberar(mundo, capsys):  # noqa: F811
    assert O.main(["claude"]) == 0
    assert "nunca foi mudado" in capsys.readouterr().out
    assert O.main(["claude", "proibir", "--motivo", "até segunda ordem"]) == 0
    assert "Claude proibido desde" in capsys.readouterr().out
    acoes._FILA_AVISOS.join()
    assert len(mundo.avisos) == 1 and "proibido por orquestrador (CLI)" in mundo.avisos[0]
    assert O.main(["claude", "status"]) == 1
    assert "até segunda ordem" in capsys.readouterr().out
    assert O.main(["claude", "proibir"]) == 0
    assert "já estava assim" in capsys.readouterr().out
    acoes._FILA_AVISOS.join()
    assert len(mundo.avisos) == 1            # sem mudança, sem aviso
    assert O.main(["claude", "liberar", "--sem-aviso"]) == 0
    acoes._FILA_AVISOS.join()
    assert len(mundo.avisos) == 1 and C.liberado() is True
    # a CLI não mexe no estado.json: não é sinal de vida da sessão
    assert not O.arquivo("estado.json").exists()


# ================================================================ o app
def test_rota_do_app_pede_token_alterna_e_avisa(mundo, servidor):  # noqa: F811
    assert _pedir(servidor, "GET", "/api/claude")[0] == 401
    assert _pedir(servidor, "POST", "/api/claude", {"liberar": False})[0] == 401
    assert C.caminho().exists() is False
    token = _parear(servidor)
    status, dados = _pedir(servidor, "GET", "/api/claude", token=token)
    assert status == 200 and dados["liberado"] is True and dados["origem"] == "sem_arquivo"
    assert _pedir(servidor, "POST", "/api/claude", {"liberar": "nao"}, token=token)[0] == 400
    assert _pedir(servidor, "POST", "/api/claude", {}, token=token)[0] == 400

    status, dados = _pedir(servidor, "POST", "/api/claude", {"liberar": False}, token=token)
    assert status == 200 and dados["mudou"] is True
    assert dados["claude"]["liberado"] is False
    assert dados["claude"]["por"] == "pelo app (moto)"
    assert C.liberado() is False
    acoes._FILA_AVISOS.join()
    assert len(mundo.avisos) == 1
    assert mundo.avisos[0].startswith("🤖 Claude proibido pelo app às ")
    # toque repetido: o alvo, não "inverter" — não volta a liberar
    status, dados = _pedir(servidor, "POST", "/api/claude", {"liberar": False}, token=token)
    assert status == 200 and dados["mudou"] is False and C.liberado() is False
    acoes._FILA_AVISOS.join()
    assert len(mundo.avisos) == 1
    # a Mesa leva o interruptor junto
    status, mesa = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert status == 200 and mesa["claude"]["liberado"] is False
    assert mesa["uso"]["situacao"] == "parada"
    status, dados = _pedir(servidor, "POST", "/api/claude", {"liberar": True}, token=token)
    assert status == 200 and dados["mudou"] is True and C.liberado() is True
    acoes._FILA_AVISOS.join()
    assert mundo.avisos[-1].startswith("🤖 Claude liberado pelo app às ")


def test_o_fonte_nao_chama_o_claude_sem_passar_pelo_interruptor():
    # os dois lugares do remoto que rodam o claude.exe: a sonda e o apurador
    from pathlib import Path
    raiz = Path(O.__file__).parent
    orq = (raiz / "orquestrador.py").read_text(encoding="utf-8")
    assert "claude_estado.motivo_proibido()" in orq.split("def sondar")[1][:600]
    assert "claude_estado.motivo_proibido()" in orq.split("def agente_inicio")[1][:600]
    apu = (raiz / "apurador.py").read_text(encoding="utf-8")
    assert "claude_proibido()" in apu.split("def apurar")[1][:300]
    assert "claude_proibido()" in apu.split("def consertar")[1][:700]
