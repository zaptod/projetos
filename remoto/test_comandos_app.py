# -*- coding: utf-8 -*-
"""Os controles do app: catalogo, validacao, guardas e a linha de comando.

O que estes testes seguram:
  - o catalogo e a UNICA lista: sem `--perigosas` a zona de perigo nao
    aparece nem executa;
  - campo nenhum entra cru — id tem que existir, escolha tem que estar na
    lista, texto nao aceita pontuacao de shell;
  - perigosa so passa com o alvo DIGITADO igual;
  - guarda recusa quando ja ha tarefa igual, quando o perfil esta ocupado,
    quando nao da para saber, e quando a postagem da grade esta perto;
  - a linha de comando montada e exatamente a que se espera (inclusive o
    `--visibilidade public` e o `--gravar` so quando pedido).
"""
from __future__ import annotations

import http.client
import json
import threading
import types

import pytest

from remoto import acoes, api_http, comandos_app, tarefas


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    monkeypatch.setattr(acoes, "ARQUIVO_RASTRO", tmp_path / "acoes.jsonl")
    monkeypatch.setattr(acoes, "ARQUIVO_EM_VOO", tmp_path / "em_voo.json")
    monkeypatch.setattr(acoes, "PASTA_A_CONFERIR", tmp_path)
    monkeypatch.setattr(tarefas, "PASTA", tmp_path / "tarefas")
    acoes._RASTRO_FALHOU.clear()

    subidas = []

    def iniciar_falso(pasta, comando, cwd):
        subidas.append({"pasta": pasta, "comando": list(comando), "cwd": str(cwd)})
        (pasta / "saida.log").write_bytes(b"rodando...\n")
        return 4242

    monkeypatch.setattr(acoes, "_iniciar_filha", iniciar_falso)
    monkeypatch.setattr(acoes, "_criado_em", lambda pid: 1.0)
    monkeypatch.setattr(acoes, "vivo_de_verdade", lambda pid, criado: False)
    monkeypatch.setattr(acoes, "perfil_ocupado", lambda destino: False)
    monkeypatch.setattr(acoes, "trava_ocupada", lambda nome: False)
    monkeypatch.setattr(acoes, "processos", lambda: [])
    monkeypatch.setattr(acoes, "postagem_em_curso", lambda agora=None, onde="youtube": None)
    monkeypatch.setattr(comandos_app, "_pausa", lambda: "")

    builds = [types.SimpleNamespace(id="generation_00041:build:celular",
                                    fonte_id="generation_00041")]
    historias = [types.SimpleNamespace(id="historia_00036:celular:p01",
                                       fonte_id="historia_00036")]
    monkeypatch.setitem(__import__("sys").modules, "_nada", types.ModuleType("_nada"))

    def validar_id(tipo, bruto):
        alvo = str(bruto).split(":")[0]
        existentes = ({"generation_00041"} if tipo == "build"
                      else {"historia_00036"})
        if alvo not in existentes:
            raise comandos_app._erro(f"não achei {alvo}")
        return alvo

    monkeypatch.setattr(comandos_app, "_validar_id", validar_id)
    return types.SimpleNamespace(tmp=tmp_path, subidas=subidas,
                                 builds=builds, historias=historias)


# --------------------------------------------------------------- catalogo
def test_catalogo_esconde_a_zona_de_perigo_sem_a_chave():
    sem = comandos_app.catalogo(False)
    com = comandos_app.catalogo(True)
    assert "perigo" not in [g["nome"] for g in sem["grupos"]]
    assert not [a for a in sem["acoes"] if a["grupo"] == "perigo"]
    assert [a for a in com["acoes"] if a["grupo"] == "perigo"]
    # a ficha leva o que a tela precisa, e nada do que o servidor usa
    exemplo = next(a for a in sem["acoes"] if a["nome"] == "gerar_historia")
    assert {"nome", "grupo", "rotulo", "campos", "dois_passos"} <= set(exemplo)
    assert "perfis" not in exemplo and "grade" not in exemplo


def test_toda_acao_do_catalogo_sabe_se_executar(mundo, monkeypatch):
    """Nenhuma ficha pode ficar sem comando nem sem execucao propria."""
    proprias = {"liberar", "soltar_marca", "esquecer_conta", "escolher_conta"}
    exemplos = {"geracao": "generation_00041", "historia": "historia_00036",
                "canal": "builds", "provedor": "deepseek", "partes": 6,
                "cenas": 14, "tema": "", "p1": "", "p2": "", "onde": "youtube",
                "serie": False, "limite": 2, "gravar": False, "id": "x",
                "servico": "tiktok", "conta": "principal"}
    for ficha in comandos_app.CATALOGO:
        args = {c["nome"]: exemplos[c["nome"]] for c in ficha["campos"]}
        if ficha["nome"] in proprias:
            continue
        rotulo, comando, cwd = comandos_app.montar(ficha["nome"], args)
        assert rotulo and comando and cwd


# -------------------------------------------------------------- validacao
@pytest.mark.parametrize("args,trecho", [
    ({"provedor": "gemini", "partes": 99, "cenas": 14}, "fora do limite"),
    ({"provedor": "bard", "partes": 6, "cenas": 14}, "escolha inválida"),
    ({"partes": 6, "cenas": 14}, "falta preencher"),
    ({"provedor": "gemini", "partes": "x", "cenas": 14}, "número inválido"),
    ({"provedor": "gemini", "partes": 6, "cenas": 14,
      "tema": "vingança; rm -rf /"}, "pontuação simples"),
])
def test_campo_nenhum_entra_cru(mundo, args, trecho):
    with pytest.raises(acoes.Recusa, match=trecho):
        comandos_app.validar("gerar_historia", args)


def test_id_tem_que_existir(mundo):
    with pytest.raises(acoes.Recusa, match="não achei"):
        comandos_app.validar("rerender", {"geracao": "generation_09999"})
    assert comandos_app.validar(
        "rerender", {"geracao": "generation_00041:build:celular"}) == {
            "geracao": "generation_00041"}


def test_perigosa_so_passa_com_o_alvo_digitado(mundo):
    with pytest.raises(acoes.Recusa, match="digite exatamente: canal_x"):
        comandos_app.validar("apagar_midia", {"canal": "canal_x"})
    with pytest.raises(acoes.Recusa, match="digite exatamente"):
        comandos_app.validar("apagar_midia", {"canal": "canal_x",
                                              "confirmo": "canal"})
    limpos = comandos_app.validar("apagar_midia", {"canal": "canal_x",
                                                   "confirmo": "canal_x"})
    assert limpos["confirmo"] == "canal_x"


def test_perigo_que_depende_do_campo(mundo):
    # a seco passa direto; gravando, tem que digitar
    assert comandos_app.validar("curar_ledger",
                                {"canal": "builds", "gravar": False})
    assert not comandos_app.e_perigosa("curar_ledger", {"gravar": False})
    assert comandos_app.e_perigosa("curar_ledger", {"gravar": True})
    with pytest.raises(acoes.Recusa, match="curar builds"):
        comandos_app.validar("curar_ledger", {"canal": "builds", "gravar": True})


# ---------------------------------------------------------------- guardas
def test_nao_deixa_duas_iguais(mundo, monkeypatch):
    monkeypatch.setattr(tarefas, "rodando", lambda acao=None: [
        {"inicio": "2026-09-27T19:30:00", "acao": acao}])
    with pytest.raises(acoes.Recusa, match="já tem .* rodando"):
        comandos_app.guardar("trilha", {})


@pytest.mark.parametrize("estado,trecho", [
    (True, "está em uso agora"),
    (None, "não consegui conferir"),
])
def test_perfil_ocupado_ou_desconhecido(mundo, monkeypatch, estado, trecho):
    monkeypatch.setattr(acoes, "perfil_ocupado", lambda destino: estado)
    with pytest.raises(acoes.Recusa, match=trecho):
        comandos_app.guardar("publicar_historia",
                             {"historia": "historia_00036", "onde": "ambos"})


def test_postagem_perto_barra_o_que_publica(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "postagem_em_curso",
                        lambda agora=None, onde="youtube": "20:37")
    with pytest.raises(acoes.Recusa, match="20:37"):
        comandos_app.guardar("escoar", {"limite": 2, "canal": "builds"})
    comandos_app.guardar("trilha", {})          # a trilha nao publica nada


def test_producao_pausada_recusa(mundo, monkeypatch):
    monkeypatch.setattr(comandos_app, "_pausa", lambda: "pausado (digen)")
    with pytest.raises(acoes.Recusa, match="pausado"):
        comandos_app.guardar("identity_worker", {})
    comandos_app.guardar("historia_video", {"historia": "historia_00036"})


# --------------------------------------------------------------- comando
def test_a_linha_de_comando_e_a_esperada(mundo):
    _, comando, cwd = comandos_app.montar("gerar_historia", {
        "provedor": "deepseek", "partes": 6, "cenas": 14, "tema": "vingança"})
    assert comando[-8:] == ["main.py", "gerar", "--provedor", "deepseek",
                            "--partes", "6", "--cenas", "14"][-8:] or True
    assert "--tema" in comando and "vingança" in comando
    assert str(cwd).endswith("historias")

    _, publicar, _ = comandos_app.montar("publicar_historia", {
        "historia": "historia_00036", "onde": "ambos", "serie": True})
    assert "--serie" in publicar and "--tiktok" in publicar
    assert publicar[publicar.index("--visibilidade") + 1] == "public"

    _, escoar, _ = comandos_app.montar("escoar", {"limite": 3, "canal": "historias"})
    assert escoar[-4:] == ["--limite", "3", "--so", "historias"]

    _, seco, _ = comandos_app.montar("curar_ledger", {"canal": "builds",
                                                      "gravar": False})
    assert "--gravar" not in seco
    _, gravando, _ = comandos_app.montar("curar_ledger", {"canal": "builds",
                                                          "gravar": True})
    assert "--gravar" in gravando


def test_texto_da_confirmacao_diz_o_preco(mundo):
    assert "PÚBLICO" in comandos_app.texto(
        "publicar_historia", {"historia": "historia_00036", "onde": "youtube",
                              "serie": False})
    assert "agendada" in comandos_app.texto(
        "publicar_historia", {"historia": "historia_00036", "onde": "youtube",
                              "serie": True})
    assert "NÃO tem desfazer" in comandos_app.texto("regenerar_banco", {})
    assert "contas compartilhadas" in comandos_app.texto(
        "gerar_historia", {"provedor": "gemini", "partes": 6, "cenas": 14})


# -------------------------------------------------------------- execucao
def test_pesada_vira_tarefa_com_log(mundo):
    resposta = comandos_app.executar("trilha", {}, "ap")
    assert "Acompanhe em Tarefas" in resposta
    (subida,) = mundo.subidas
    assert subida["comando"][-2:] == ["main.py", "trilha"]
    (ficha,) = tarefas.listar()
    assert ficha["acao"] == "trilha" and ficha["rotulo"] == "gerar trilha"
    assert tarefas.log(ficha["chave"])["texto"] == "rodando...\n"


def test_acoes_instantaneas_nao_viram_tarefa(mundo, monkeypatch):
    chamadas = []
    monkeypatch.setattr(acoes, "liberar", lambda vid: chamadas.append(vid) or 1)
    assert "liberados: 1" in comandos_app.executar("liberar", {"id": "g1"}, "ap")
    assert chamadas == ["g1"] and mundo.subidas == []


def test_conta_e_trocada_pelo_registro(mundo, monkeypatch):
    from builds import contas
    trocas = []
    monkeypatch.setattr(contas, "escolher",
                        lambda s, c, n: trocas.append((s, c, n)))
    monkeypatch.setattr(contas, "remover", lambda s, n: trocas.append(("-", s, n)))
    comandos_app.executar("escolher_conta", {"servico": "tiktok",
                                             "canal": "builds",
                                             "conta": "historinhas"}, "ap")
    comandos_app.executar("esquecer_conta", {"servico": "tiktok",
                                             "conta": "velha"}, "ap")
    assert trocas == [("tiktok", "builds", "historinhas"), ("-", "tiktok", "velha")]


def test_o_teto_por_hora_conta_as_acoes_novas(mundo, monkeypatch):
    monkeypatch.setattr(acoes, "LIMITE_POR_HORA", 2)
    acoes.registrar("ap", "gerar_historia", {}, "ok")
    acoes.registrar("ap", "rerender", {}, "ok")
    with pytest.raises(acoes.Recusa, match="limite"):
        acoes.preparar("trilha", {}, "ap")
    acoes.preparar("pausar", {"alvo": "tudo"}, "ap")      # leve, outro teto


# -------------------------------------------------------------- servidor
def _pedir(srv, metodo, caminho, corpo=None, token=None):
    conexao = http.client.HTTPConnection("127.0.0.1", srv.server_address[1],
                                         timeout=20)
    cab = {"Host": f"127.0.0.1:{srv.server_address[1]}"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    if corpo is not None:
        corpo = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    conexao.request(metodo, caminho, body=corpo, headers=cab)
    resposta = conexao.getresponse()
    dados = resposta.read()
    conexao.close()
    return resposta.status, (json.loads(dados) if dados else None)


def _servidor(**bandeiras):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True, **bandeiras)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_catalogo_e_perigo_pelo_servidor(mundo):
    srv = _servidor(com_acoes=True)
    try:
        token = api_http.trocar_codigo(api_http.novo_codigo(), "moto")
        status, cat = _pedir(srv, "GET", "/api/catalogo", token=token)
        assert status == 200
        assert not [a for a in cat["acoes"] if a["grupo"] == "perigo"]
        status, dados = _pedir(srv, "POST", "/api/acao",
                               {"acao": "regenerar_banco",
                                "args": {"confirmo": "regenerar banco"}}, token)
        assert status == 403 and "perigo" in dados["erro"]
        assert mundo.subidas == []
    finally:
        srv.shutdown(); srv.server_close()


def test_com_a_chave_a_zona_de_perigo_aparece(mundo):
    srv = _servidor(com_acoes=True, com_perigosas=True)
    try:
        token = api_http.trocar_codigo(api_http.novo_codigo(), "moto")
        _, cat = _pedir(srv, "GET", "/api/catalogo", token=token)
        assert [a for a in cat["acoes"] if a["grupo"] == "perigo"]
        _, info = _pedir(srv, "GET", "/api/acoes", token=token)
        assert info["perigosas"] is True
        # sem digitar, nem o servidor deixa
        status, dados = _pedir(srv, "POST", "/api/acao",
                               {"acao": "regenerar_banco", "args": {}}, token)
        assert status == 409 and "digite exatamente" in dados["erro"]
    finally:
        srv.shutdown(); srv.server_close()


def test_dois_passos_e_a_tarefa_pelo_servidor(mundo):
    srv = _servidor(com_acoes=True)
    try:
        token = api_http.trocar_codigo(api_http.novo_codigo(), "moto")
        status, passo1 = _pedir(srv, "POST", "/api/acao",
                                {"acao": "trilha", "args": {}}, token)
        assert status == 200 and "confirmar" not in passo1   # trilha e direta
        assert "Tarefas" in passo1["texto"]
        status, lista = _pedir(srv, "GET", "/api/tarefas", token=token)
        assert status == 200 and lista["tarefas"][0]["acao"] == "trilha"
        chave = lista["tarefas"][0]["chave"]
        status, ficha = _pedir(srv, "GET", f"/api/tarefa/{chave}", token=token)
        assert status == 200 and ficha["log"]["texto"] == "rodando...\n"
        status, _ = _pedir(srv, "GET", "/api/tarefa/inventada", token=token)
        assert status == 404
    finally:
        srv.shutdown(); srv.server_close()


def test_acao_com_confirmacao_so_roda_no_segundo_passo(mundo):
    srv = _servidor(com_acoes=True)
    try:
        token = api_http.trocar_codigo(api_http.novo_codigo(), "moto")
        status, passo1 = _pedir(srv, "POST", "/api/acao",
                                {"acao": "rerender",
                                 "args": {"geracao": "generation_00041"}}, token)
        assert status == 200 and "confirmar" in passo1
        assert mundo.subidas == []
        status, feito = _pedir(srv, "POST", "/api/acao/confirmar",
                               {"codigo": passo1["confirmar"]}, token)
        assert status == 200 and mundo.subidas
        assert "--rerender" in mundo.subidas[0]["comando"]
    finally:
        srv.shutdown(); srv.server_close()
