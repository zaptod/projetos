# -*- coding: utf-8 -*-
"""O leitor de decisoes tomadas (pedido do Adrian pela Mesa, 28/09 21:50).

"Quero que voce crie um leitor de decisoes tomadas, para saber se isso gera
mais ramificacoes ainda." Cada resposta do `_eventos.jsonl` e lida pelo
orquestrador, que registra o que ela gerou (tarefa, ramo ou nada) no proprio
no. Tudo roda num repositorio git TEMPORARIO apontado por `NF_DECISOES_REPO`,
com a pasta do orquestrador em `tmp_path`: nada toca o repositorio real, o
`%LOCALAPPDATA%` real, a rede ou o Telegram.
"""
from __future__ import annotations

import http.client
import json
import subprocess
import threading
from datetime import datetime, timedelta

import pytest

from remoto import acoes, api_http, decisoes as D, orquestrador as O


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, encoding="utf-8", check=False)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "docs" / "sessoes").mkdir(parents=True)
    (repo / "docs" / "sessoes" / "builds.md").write_text("# Builds\n\nTexto.\n",
                                                        encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "teste@exemplo")
    _git(repo, "config", "user.name", "teste")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", "--", "docs")
    _git(repo, "commit", "-q", "-m", "inicio")
    # o mesmo caminho da instancia de teste: o clone vem pela variavel
    monkeypatch.setenv("NF_DECISOES_REPO", str(repo))
    for nome in ("REPO", "PASTA", "SESSOES", "TRAVA"):
        monkeypatch.setattr(D, nome, None)
    monkeypatch.setattr(D, "MIDIA_LOCAL", tmp_path / "midia")
    monkeypatch.setattr(O, "PASTA", tmp_path / "orquestrador")
    monkeypatch.setattr(O, "USO_EXTRA", tmp_path / "uso_sessao.json")
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    avisos = []
    monkeypatch.setattr(acoes, "_entregar", avisos.append)
    yield type("Mundo", (), {"tmp": tmp_path, "repo": repo, "avisos": avisos})
    acoes._FILA_AVISOS.join()


def _arvore():
    """Ferramenta -> Palco -> Chao, sem commit (quem testa o commit e o marcar)."""
    D.adicionar("builds", "Ferramenta do visual", "Qual?",
                ["godot=Godot 4", "unity=Unity"], id="ferramenta")
    D.adicionar("builds", "Palco: seguir?", "Seguir?",
                ["seguir=Seguir", "ajustar=Seguir, com ajustes (comente)"], id="palco",
                depende_de=["ferramenta=godot"])
    D.adicionar("builds", "Chão da arena", "Qual chão?", ["pedra=Pedra", "ia=IA"],
                id="chao", depende_de=["palco=seguir"])


def _commits(repo):
    return _git(repo, "log", "--format=%s").stdout.splitlines()


def _no_disco(mundo, projeto, item_id):
    return json.loads((mundo.repo / "decisoes" / projeto / f"{item_id}.json")
                      .read_text(encoding="utf-8"))


# ================================================================ caso ZERO
def test_caso_zero_sem_eventos_o_leitor_nao_inventa(mundo, capsys):
    assert D.ler_eventos() == []
    assert D.leitor() == [] and D.leitor(todos=True) == []
    assert D.main(["leitor"]) == 0
    assert "todas as respostas foram lidas" in capsys.readouterr().out
    assert D.main(["leitor", "--todos"]) == 0
    assert "nenhuma resposta ainda" in capsys.readouterr().out
    tela = D.para_o_app()
    assert tela["leitor"] == {"nao_lidas": 0, "eventos_ilegiveis": 0, "erro_da_mesa": ""}
    assert all(p["contagem"]["nao_lidas"] == 0 for p in tela["projetos"])
    # nem o `esperar` acorda com o nada
    assert O.decisoes_novas() == ([], 0)
    # com a arvore, mas sem resposta nenhuma, continua zero
    _arvore()
    assert D.leitor() == [] and D.nao_lidas_por_no() == {}
    assert D.para_o_app()["itens"]["palco"]["consequencias"] == []
    with pytest.raises(D.Recusa, match="nenhuma resposta de palco"):
        D.marcar("palco", ["nada"])


# ========================================================== os tres sinais
def test_comentario_livre_precisa_de_leitura(mundo, capsys):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "ajustar", "mais elaborado: planos, habilidades, animações",
                commitar=False)
    lista = D.leitor()
    assert [e["id"] for e in lista] == ["ferramenta", "palco"]
    assert lista[0]["precisa_de_leitura"] is False
    assert lista[1]["precisa_de_leitura"] is True
    assert lista[1]["comentario"].startswith("mais elaborado")
    assert D.main(["leitor"]) == 0
    saida = capsys.readouterr().out
    assert "(c) COMENTÁRIO — precisa de leitura: “mais elaborado" in saida
    assert "(c) sem comentário" in saida and "2 não lida(s)" in saida


def test_o_que_a_opcao_desbloqueia(mundo, capsys):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    ferramenta, palco = D.leitor()
    assert [n["id"] for n in ferramenta["desbloqueia"]] == ["palco"]
    assert [(n["id"], n["situacao"]) for n in palco["desbloqueia"]] == [("chao", "pendente")]
    assert palco["a_rever"] == [] and palco["precisa_de_leitura"] is False
    D.main(["leitor"])
    assert "(a) desbloqueia: builds/chao [pendente]" in capsys.readouterr().out


def test_o_que_foi_para_a_rever(mundo, capsys):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    D.responder("chao", "pedra", commitar=False)
    D.responder("ferramenta", "unity", commitar=False)       # ele voltou e trocou
    ultima = D.leitor()[-1]
    assert ultima["anterior"] == "godot"
    assert [(n["id"], n["situacao"]) for n in ultima["a_rever"]] == [
        ("palco", "a_rever"), ("chao", "a_rever")]
    # a primeira resposta da ferramenta nao vale mais, e o leitor diz
    assert D.leitor()[0]["ainda_vale"] is False and ultima["ainda_vale"] is True
    D.main(["leitor"])
    saida = capsys.readouterr().out
    assert "(b) a rever: builds/palco [a_rever], builds/chao [a_rever]" in saida
    assert "(antes: godot)" in saida and "já foi trocada por outra" in saida


def test_linha_ilegivel_aparece_e_nao_some(mundo, capsys):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    with open(D.caminho_eventos(), "ab") as fh:
        fh.write(b"{meio json\n")
    lista = D.leitor()
    assert lista[-1] == {"n": 2, "ilegivel": True, "lida": False}
    D.main(["leitor"])
    assert "#2  LINHA ILEGÍVEL" in capsys.readouterr().out
    assert D.para_o_app()["leitor"]["eventos_ilegiveis"] == 1
    with pytest.raises(D.Recusa, match="ilegível"):
        D.marcar("2", ["nada"])


# ================================================================ marcar
def test_marcar_grava_no_no_commita_e_some_do_leitor(mundo, capsys):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "ajustar", "quero mais", commitar=False)
    D.adicionar("builds", "Palco: quais ajustes?", "Quais?", ["a=A", "b=B"],
                id="palco-ajustes")
    antes = len(_commits(mundo.repo))
    assert D.main(["leitor", "marcar", "builds/palco", "--gerou", "tarefa:ec0e8556",
                   "--gerou", "no:builds/palco-ajustes", "--nota", "16E no palco"]) == 0
    saida = capsys.readouterr().out
    assert "#2 builds/palco lida · 2 consequência(s) nova(s)" in saida
    assert "ramos ligados: palco-ajustes" in saida and "commit: ok" in saida
    assert len(_commits(mundo.repo)) == antes + 1
    assert _commits(mundo.repo)[0] == ("decisão(builds): lida — Palco: seguir? gerou "
                                       "tarefa ec0e8556, nó builds/palco-ajustes")
    no = _no_disco(mundo, "builds", "palco")
    em = D.ler_eventos()[1]["em"]
    tarefa, ramo = no["consequencias"]
    assert set(tarefa) == {"alvo", "em", "evento", "linha", "nota", "opcao", "origem",
                           "tipo"}
    assert tarefa["linha"] == 2
    assert (tarefa["tipo"], tarefa["alvo"], tarefa["evento"], tarefa["opcao"]) == (
        "tarefa", "ec0e8556", em, "ajustar")
    assert tarefa["nota"] == "16E no palco" and tarefa["origem"] == "leitor"
    assert (ramo["tipo"], ramo["alvo"]) == ("no", "builds/palco-ajustes")
    # o ramo novo nasce ligado a resposta que o gerou
    filho = _no_disco(mundo, "builds", "palco-ajustes")
    assert filho["depende_de"] == [{"decisao": "palco", "opcao": "ajustar"}]
    assert filho["situacao"] == "pendente"
    assert "palco-ajustes" in next(o for o in no["opcoes"]
                                   if o["id"] == "ajustar")["desbloqueia"]
    # tudo no commit, nada fora dele
    assert _git(mundo.repo, "status", "--porcelain", "--", "decisoes").stdout == ""
    # lida: some do leitor; a outra continua
    assert [e["id"] for e in D.leitor()] == ["ferramenta"]
    assert D.leitor(todos=True)[1]["lida"] is True
    # repetir nao duplica nem commita
    feito = D.marcar("builds/palco", ["tarefa:ec0e8556"])
    assert feito["novas"] == [] and feito["commit"] == "nada"
    assert len(_no_disco(mundo, "builds", "palco")["consequencias"]) == 2
    # nada
    assert D.main(["leitor", "marcar", "1", "--gerou", "nada",
                   "--nota", "aplicada na Mesa"]) == 0
    assert D.leitor() == []
    assert _no_disco(mundo, "builds", "ferramenta")["consequencias"][0]["tipo"] == "nada"


def test_trocar_o_ramo_de_resposta_manda_o_ramo_para_a_rever(mundo):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "ajustar", "x", commitar=False)
    D.adicionar("builds", "Ajustes", "?", ["a=A"], id="ajustes")
    D.marcar("palco", ["no:ajustes"], commitar=False)
    D.responder("ajustes", "a", commitar=False)
    evento = D.responder("palco", "seguir", commitar=False)
    assert "ajustes" in evento["a_rever"]
    # a resposta nova (seguir) ainda nao foi lida; a antiga continua lida
    assert [e["opcao"] for e in D.leitor() if e["id"] == "palco"] == ["seguir"]


def test_marcar_a_ultima_cobre_as_anteriores(mundo):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("ferramenta", "godot", "de novo", commitar=False)   # toque duplo
    assert D.nao_lidas_por_no() == {"ferramenta": 2}
    D.marcar("ferramenta", ["nada"], commitar=False)
    assert D.nao_lidas_por_no() == {}
    # mas marcar a PRIMEIRA nao le a segunda
    D.responder("ferramenta", "unity", commitar=False)
    D.responder("ferramenta", "godot", commitar=False)
    D.marcar("3", ["nada"], commitar=False)
    assert [e["n"] for e in D.leitor()] == [4]


@pytest.mark.parametrize("gerou, trecho", [
    (["nada", "tarefa:abc"], "não combina"),
    (["tarefa:"], "--gerou inválido"),
    (["tarefa:../x"], "--gerou inválido"),
    (["outra:coisa"], "--gerou inválido"),
    (["no:builds/nao-existe"], "não existe"),
    (["no:historias/chao"], "não existe"),
    (["no:palco"], "não gera ela mesma"),
])
def test_marcar_recusa_o_que_nao_faz_sentido(mundo, gerou, trecho):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    antes = _no_disco(mundo, "builds", "palco")
    with pytest.raises(D.Recusa, match=trecho):
        D.marcar("palco", gerou)
    assert _no_disco(mundo, "builds", "palco") == antes
    assert [e["id"] for e in D.leitor()] == ["ferramenta", "palco"]


def test_ramo_nao_liga_a_resposta_que_nao_vale_mais(mundo):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("ferramenta", "unity", commitar=False)
    D.adicionar("builds", "Solto", "?", ["a=A"], id="solto")
    with pytest.raises(D.Recusa, match="não vale mais"):
        D.marcar("1", ["no:solto"])
    assert D.carregar()["solto"]["depende_de"] == []
    # a tarefa (ou nada) de uma resposta velha pode ser registrada
    D.marcar("1", ["tarefa:abc123"], commitar=False)


def test_ciclo_pelo_ramo_e_recusado(mundo):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    with pytest.raises(D.Recusa, match="ciclo"):
        D.marcar("palco", ["no:ferramenta"])
    assert D.carregar()["ferramenta"]["depende_de"] == []


# ============================================================ para o app
def _agente(parte, titulo, **kw):
    return O.agente_inicio(parte, titulo, forcar=True, **kw)["id"]


def test_o_app_ve_o_que_gerou_com_o_estado_da_mesa(mundo, monkeypatch):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    D.responder("chao", "pedra", "tanto faz", commitar=False)
    feita = _agente("builds", "16E: rostos")
    O.agente_fim(feita, commits=["515284b"])
    rodando = _agente("builds", "som real")
    na_fila = O.fila_adicionar("builds", "16C: eventos")["id"]
    D.marcar("ferramenta", [f"tarefa:{feita}", f"tarefa:{rodando}", f"tarefa:{na_fila}",
                            "tarefa:ninguem", "no:builds/palco"], commitar=False)
    tela = D.para_o_app()
    item = tela["itens"]["ferramenta"]
    assert item["nao_lidas"] == 0
    tarefas = {c["alvo"]: c["tarefa"] for c in item["consequencias"] if c["tipo"] == "tarefa"}
    assert tarefas[feita]["situacao"] == "concluida" and tarefas[feita]["commits"] == ["515284b"]
    assert tarefas[rodando]["situacao"] == "andamento"
    assert tarefas[na_fila]["situacao"] == "fila"
    assert tarefas[na_fila]["titulo"] == "16C: eventos"
    assert tarefas["ninguem"]["situacao"] == "desconhecida"
    (ramo,) = [c for c in item["consequencias"] if c["tipo"] == "no"]
    assert ramo["no"] == {"id": "palco", "titulo": "Palco: seguir?", "projeto": "builds",
                          "situacao": "decidida", "existe": True}
    # a raiz do projeto conta as nao lidas: palco e chao
    builds = next(p for p in tela["projetos"] if p["id"] == "builds")
    assert builds["contagem"]["nao_lidas"] == 2 and tela["leitor"]["nao_lidas"] == 2
    assert tela["itens"]["chao"]["nao_lidas"] == 1
    # o item da fila vira agente: a decisao acompanha pelo id antigo
    novo = O.agente_inicio("", "", da_fila=na_fila, forcar=True)["id"]
    assert novo != na_fila
    tarefa = next(c for c in D.para_o_app()["itens"]["ferramenta"]["consequencias"]
                  if c["alvo"] == na_fila)["tarefa"]
    assert tarefa["situacao"] == "andamento"
    # a Mesa ilegivel nao vira "fora da Mesa": vira "ilegivel"
    O.arquivo("estado.json").write_text("{nao", encoding="utf-8")
    tela = D.para_o_app()
    assert tela["leitor"]["erro_da_mesa"]
    assert {c["tarefa"]["situacao"] for c in tela["itens"]["ferramenta"]["consequencias"]
            if c["tipo"] == "tarefa"} == {"sem_leitura"}


def test_tarefa_concluida_ontem_continua_concluida(mundo):
    feita = _agente("builds", "ontem")
    O.agente_fim(feita)
    estado = json.loads(O.arquivo("estado.json").read_text(encoding="utf-8"))
    ontem = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    estado["concluidos_hoje"][0]["fim"] = ontem
    O.arquivo("estado.json").write_text(json.dumps(estado), encoding="utf-8")
    O.pulso()                              # o proximo dia reescreve o estado
    assert O.ler_estado()["concluidos_hoje"] == []
    assert O.situacao_das_tarefas()[feita]["situacao"] == "concluida"
    historico, _ = O._ler_jsonl(O.arquivo("tarefas_historico.jsonl"))
    assert [t["id"] for t in historico] == [feita]          # uma vez so


@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, caminho, token=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=15)
    cab = {"Host": f"127.0.0.1:{porta}"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    conexao.request("GET", caminho, headers=cab)
    resposta = conexao.getresponse()
    dados = resposta.read()
    conexao.close()
    return resposta.status, dados


def test_a_rota_e_a_tela(servidor, mundo):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    porta = servidor.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=15)
    conexao.request("POST", "/api/parear",
                    body=json.dumps({"codigo": api_http.novo_codigo(),
                                     "nome": "moto"}).encode(),
                    headers={"Host": f"127.0.0.1:{porta}",
                             "Content-Type": "application/json"})
    token = json.loads(conexao.getresponse().read())["token"]
    conexao.close()
    status, dados = _pedir(servidor, "/api/decisoes", token)
    assert status == 200
    tela = json.loads(dados)
    assert tela["itens"]["ferramenta"]["nao_lidas"] == 1
    assert tela["leitor"]["nao_lidas"] == 1
    assert _pedir(servidor, "/api/decisoes")[0] == 401
    status, corpo = _pedir(servidor, "/decisoes.js")
    assert status == 200
    for trecho in (b"O que isto gerou", b"n\xc3\xa3o lida ainda", b"nao-lidas-n",
                   b"decisoesGerou"):
        assert trecho in corpo
    assert b"style:" not in corpo


# ========================================================== o `esperar`
def test_esperar_acorda_com_resposta_nova(mundo, capsys):
    _arvore()
    D.responder("ferramenta", "godot", commitar=False)
    # sem cursor, o passado e do leitor: o esperar nasce no fim
    assert O.decisoes_novas() == ([], 1)
    D.responder("palco", "ajustar", "mais elaborado", commitar=False)
    novas, ultima = O.decisoes_novas()
    assert ultima == 2 and [(e["tipo"], e["id"]) for e in novas] == [("decisao_nova", "palco")]
    assert novas[0]["precisa_de_leitura"] is True
    # o esperar da CLI sai na hora, com o evento, e avanca o cursor
    assert O.main(["esperar", "--json", "--intervalo", "1"]) == 0
    saida = json.loads(capsys.readouterr().out)
    assert [(e["tipo"], e["id"], e["n"]) for e in saida] == [("decisao_nova", "palco", 2)]
    assert O.decisoes_novas() == ([], 2)
    # comando e resposta juntos: os dois saem, cada um com o tipo
    O.gravar_comando("pausar_fila")
    D.responder("ferramenta", "godot", "confirmo", commitar=False)
    assert O.main(["esperar", "--intervalo", "1"]) == 0
    texto = capsys.readouterr().out
    assert "pausar_fila" in texto and "decisao_nova  #3" in texto
    assert "leia com: python -m remoto.decisoes leitor" in texto


def test_esperar_nao_acorda_com_resposta_ja_lida(mundo):
    _arvore()
    assert O.decisoes_novas() == ([], 0)
    D.responder("ferramenta", "godot", commitar=False)
    D.marcar("ferramenta", ["nada"], commitar=False)
    assert O.decisoes_novas() == ([], 1)


def test_capacidade_pela_mesa_nasce_lida_e_num_commit_so(mundo):
    destino = mundo.repo / "decisoes" / "geral"
    destino.mkdir(parents=True)
    D.adicionar("geral", "Modo de trabalho dos agentes", "?",
                ["um=Um projeto por vez", "paralelo=Vários projetos em paralelo"],
                id="modo-de-trabalho")
    _git(mundo.repo, "add", "--", "decisoes")
    _git(mundo.repo, "commit", "-q", "-m", "grimorio")
    antes = len(_commits(mundo.repo))
    O.mudar_modo("paralelo")                 # operacional: nao responde nada
    O.aplicado(O.gravar_comando("max_paralelo", 3, "614c026b")["id"])
    assert D.carregar()["modo-de-trabalho"]["vigente"]["opcao"] == "paralelo"
    assert D.leitor() == []                      # a config ja vale: nada a ler
    (marca,) = D.carregar()["modo-de-trabalho"]["consequencias"]
    assert marca["tipo"] == "nada" and marca["origem"] == "mesa"
    assert len(_commits(mundo.repo)) == antes + 1
    assert _commits(mundo.repo)[0] == ("decisão(geral): Modo de trabalho dos agentes → "
                                       "Vários projetos em paralelo")
    assert _git(mundo.repo, "status", "--porcelain", "--", "decisoes").stdout == ""


def test_marca_antiga_sem_linha_ainda_vale(mundo):
    # As duas primeiras marcas automaticas da Mesa (28/09 22:26 e 22:30) foram
    # gravadas antes de a consequencia ganhar a `linha`: continuam lendo o evento.
    _arvore()
    evento = D.responder("ferramenta", "godot", commitar=False)
    item = D.carregar()["ferramenta"]
    item["consequencias"] = [{"alvo": "", "em": evento["em"], "evento": evento["em"],
                              "nota": "", "opcao": "godot", "origem": "mesa",
                              "tipo": "nada"}]
    D._gravar_bytes(D.caminho_item("builds", "ferramenta"), D._canonico(item))
    assert D.leitor() == []
    (lida,) = D.leitor(todos=True)
    assert [c["origem"] for c in lida["consequencias"]] == ["mesa"]
