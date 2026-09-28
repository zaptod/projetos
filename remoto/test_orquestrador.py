# -*- coding: utf-8 -*-
"""A Mesa de comando: o estado do orquestrador, os comandos do app, a sonda
de uso, os acessos e o "Contestar".

Tudo em `tmp_path` (no E:, pelo --basetemp): a pasta do orquestrador, o
arquivo extra do vigia, os agentes, o lancador e um repositorio git
temporario para o Contestar. Nada toca o `%LOCALAPPDATA%` real, o
repositorio real, a rede ou o Telegram. A sonda nunca chama o claude.exe:
recebe uma saida falsa.
"""
from __future__ import annotations

import http.client
import json
import subprocess
import threading
import time
import types
from datetime import datetime, timedelta

import pytest

from remoto import acoes, api_http, decisoes as D, orquestrador as O

EVENTO = {"type": "rate_limit_event", "rate_limit_info": {
    "status": "allowed", "unifiedWindows": {
        "five_hour": {"utilization": 0.34, "resetsAt": None},
        "seven_day": {"utilization": 0.13, "resetsAt": None}}}}


def _saida_falsa(utilizacao=0.34, renova_em=None):
    evento = json.loads(json.dumps(EVENTO))
    evento["rate_limit_info"]["unifiedWindows"]["five_hour"]["utilization"] = utilizacao
    evento["rate_limit_info"]["unifiedWindows"]["five_hour"]["resetsAt"] = (
        renova_em if renova_em is not None else int(time.time()) + 3 * 3600)
    evento["rate_limit_info"]["unifiedWindows"]["seven_day"]["resetsAt"] = \
        int(time.time()) + 4 * 86400
    linhas = [json.dumps({"type": "system", "subtype": "init"}), json.dumps(evento),
              json.dumps({"type": "result", "result": "ok"})]
    return lambda *a, **k: types.SimpleNamespace(stdout="\n".join(linhas), returncode=0)


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, encoding="utf-8", check=False)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "PASTA", tmp_path / "orquestrador")
    monkeypatch.setattr(O, "USO_EXTRA", tmp_path / "uso_sessao.json")
    monkeypatch.setattr(O, "PASTA_SONDA", tmp_path / "sonda")
    monkeypatch.setenv("CLAUDE_BIN", "claude-falso.exe")
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    avisos = []
    monkeypatch.setattr(acoes, "_entregar", avisos.append)
    # o Grimorio num repositorio git temporario (o Contestar commita)
    repo = tmp_path / "repo"
    (repo / "docs" / "sessoes").mkdir(parents=True)
    (repo / "docs" / "sessoes" / "app-e-bot.md").write_text("# App\n\nTexto.\n",
                                                           encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "teste@exemplo")
    _git(repo, "config", "user.name", "teste")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", "--", "docs")
    _git(repo, "commit", "-q", "-m", "inicio")
    monkeypatch.setattr(D, "REPO", repo)
    monkeypatch.setattr(D, "PASTA", repo / "decisoes")
    monkeypatch.setattr(D, "SESSOES", repo / "docs" / "sessoes")
    monkeypatch.setattr(D, "TRAVA", tmp_path / "decisoes.lock")
    monkeypatch.setattr(D, "MIDIA_LOCAL", tmp_path / "midia")
    yield types.SimpleNamespace(tmp=tmp_path, repo=repo, avisos=avisos)
    acoes._FILA_AVISOS.join()


@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=15)
    cab = {"Host": f"127.0.0.1:{porta}"}
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


def _parear(srv):
    codigo = api_http.novo_codigo()
    status, dados = _pedir(srv, "POST", "/api/parear", {"codigo": codigo, "nome": "moto"})
    assert status == 200
    return dados["token"]


# ================================================================ caso ZERO
def test_caso_zero_nada_existe_e_a_tela_nao_inventa(mundo, capsys):
    tela = O.para_o_app()
    assert tela["estado_existe"] is False
    assert tela["fora_do_ar"] is True
    assert tela["estado"]["agora"] == [] and tela["estado"]["fila"] == []
    assert tela["uso"]["situacao"] == "nunca" and tela["uso"]["medicao"] is None
    assert tela["decisoes"] == [] and tela["comandos"] == [] and tela["pendentes"] == 0
    assert tela["historico_uso"] == [] and tela["acessos"] is None
    assert tela["erros"] == []
    assert tela["config"] == O.PADRAO_CONFIG
    assert tela["paralelo_efetivo"] == 1
    assert O.main(["pendentes"]) == 0
    assert "nenhum comando pendente" in capsys.readouterr().out
    assert O.main(["estado"]) == 0
    saida = capsys.readouterr().out
    assert "ninguém trabalhando" in saida and "vazia" in saida
    # ler nao cria nada
    assert not (mundo.tmp / "orquestrador").exists()


def test_caso_zero_pela_rota(servidor):
    token = _parear(servidor)
    status, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert status == 200
    assert tela["fora_do_ar"] is True and tela["uso"]["medicao"] is None
    assert _pedir(servidor, "GET", "/api/orquestrador")[0] == 401


def test_estado_ilegivel_e_dito_nao_vira_vazio(mundo):
    (mundo.tmp / "orquestrador").mkdir()
    (mundo.tmp / "orquestrador" / "estado.json").write_text("{quebrado", encoding="utf-8")
    tela = O.para_o_app()
    assert any("estado.json" in e for e in tela["erros"])
    with pytest.raises(O.Recusa):
        O.fila_adicionar("builds", "x")          # nao escreve por cima do ilegivel


# ================================================== comando -> aplicado -> tela
def test_comando_gravado_pendente_aplicado_e_a_tela_mostra(servidor, mundo, capsys):
    token = _parear(servidor)
    status, r = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": "max_paralelo", "valor": 3}, token)
    assert status == 200
    cid = r["comando"]["id"]
    _, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert tela["pendentes"] == 1
    assert tela["comandos"][0]["situacao"] == "pendente"
    assert tela["config"]["max_paralelo"] == 1          # so muda quando aplicar

    assert O.main(["pendentes", "--json"]) == 0
    lista = json.loads(capsys.readouterr().out)
    assert [c["id"] for c in lista] == [cid] and lista[0]["valor"] == 3

    assert O.main(["aplicado", cid]) == 0
    _, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert tela["comandos"][0]["situacao"] == "aplicado"
    assert tela["config"]["max_paralelo"] == 3 and tela["pendentes"] == 0
    historico = (mundo.tmp / "orquestrador" / "config_historico.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert json.loads(historico[-1]) | {"em": 0} == {
        "em": 0, "chave": "max_paralelo", "de": 1, "para": 3, "origem": "app",
        "comando": cid}
    # aplicar duas vezes: recusa
    assert O.main(["aplicado", cid]) == 3


def test_comando_recusado_leva_o_motivo_ate_a_tela(servidor):
    token = _parear(servidor)
    _, r = _pedir(servidor, "POST", "/api/orquestrador/comando",
                  {"comando": "modo", "valor": "forca_total"}, token)
    O.aplicado(r["comando"]["id"], recusado="o uso está em 80%")
    _, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert tela["comandos"][0]["situacao"] == "recusado"
    assert tela["comandos"][0]["motivo"] == "o uso está em 80%"
    assert tela["config"]["modo"] == "um_por_vez"


@pytest.mark.parametrize("comando,valor", [
    ("max_paralelo", 9), ("max_paralelo", 0), ("max_paralelo", "2x"), ("max_paralelo", True),
    ("modo", "turbo"), ("teto_uso", 5), ("forca_total", "sim"), ("mensagem", "   "),
    ("mensagem", "x" * 1001), ("parar_agente", "../x"),
    ("priorizar", {"item": "a1", "direcao": "lado"}),
])
def test_comando_invalido_e_recusado(servidor, comando, valor):
    token = _parear(servidor)
    status, r = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": comando, "valor": valor}, token)
    assert status == 409 and r["erro"]
    assert O.pendentes() == []


def test_comando_fora_da_tabela_e_contestar_pela_rota_errada(servidor):
    token = _parear(servidor)
    for nome in ("rm_rf", "contestar"):
        status, _ = _pedir(servidor, "POST", "/api/orquestrador/comando",
                           {"comando": nome, "valor": {}}, token)
        assert status == 400
    assert _pedir(servidor, "POST", "/api/orquestrador/comando",
                  {"comando": "pausar_fila"})[0] == 401


def test_fila_priorizar_pausar_e_parar_agente_aplicados(mundo):
    a = O.fila_adicionar("builds", "Builds")["id"]
    b = O.fila_adicionar("builds", "Onda 16E")["id"]
    c = O.gravar_comando("priorizar", {"item": b, "direcao": "subir"})
    O.aplicado(c["id"])
    assert [f["id"] for f in O.ler_estado()["fila"]] == [b, a]
    assert [f["prioridade"] for f in O.ler_estado()["fila"]] == [1, 2]
    O.aplicado(O.gravar_comando("pausar_fila")["id"])
    assert O.ler_config()["fila_pausada"] is True
    # o comando que o orquestrador nao consegue cumprir: `aplicado` recusa, e
    # ele registra com --recusado
    fantasma = O.gravar_comando("parar_agente", "nao-existe")
    with pytest.raises(O.Recusa):
        O.aplicado(fantasma["id"])
    assert O.pendentes()[0]["id"] == fantasma["id"]
    O.aplicado(fantasma["id"], recusado="não existe esse agente")


def test_forca_total_ligar_e_desligar(mundo):
    O.aplicado(O.gravar_comando("forca_total", False)["id"])
    assert O.ler_config()["forca_total_antes_min"] is None
    O.aplicado(O.gravar_comando("forca_total", True)["id"])
    assert O.ler_config()["forca_total_antes_min"] == 20


def test_teto_de_comandos_por_janela(mundo, monkeypatch):
    monkeypatch.setattr(O, "COMANDOS_NA_JANELA_MAX", 3)
    for _ in range(3):
        O.gravar_comando("mensagem", "oi")
    with pytest.raises(O.Recusa):
        O.gravar_comando("mensagem", "oi")


# ================================================================== agentes
def test_capacidade_e_respeitada_na_cli(mundo, capsys):
    item = O.fila_adicionar("app-e-bot", "Orquestrador no app")["id"]
    depois = O.fila_adicionar("builds", "Builds")["id"]
    assert O.main(["agente-inicio", "--da-fila", item, "--relato", "começando"]) == 0
    agente = capsys.readouterr().out.strip()
    estado = O.ler_estado()
    assert estado["agora"][0]["titulo"] == "Orquestrador no app"
    # quem sai da fila leva a numeracao junto: o proximo vira o 1
    assert [(f["id"], f["prioridade"]) for f in estado["fila"]] == [(depois, 1)]
    # um por vez: o segundo recusa, e so passa com --forcar
    assert O.main(["agente-inicio", "--parte", "builds", "--titulo", "B"]) == 3
    assert "capacidade" in capsys.readouterr().err
    assert O.main(["agente-inicio", "--parte", "builds", "--titulo", "B", "--forcar"]) == 0
    capsys.readouterr()
    assert O.main(["relato", agente, "tela pronta"]) == 0
    assert O.main(["agente-fim", agente, "--commit", "abc1234def5678"]) == 0
    estado = O.ler_estado()
    assert len(estado["agora"]) == 1
    feito = estado["concluidos_hoje"][0]
    assert feito["commits"] == ["abc1234def56"] and feito["relato"] == "tela pronta"


def test_fila_pausada_e_teto_passado_barram_o_inicio(mundo):
    O.mudar_modo("paralelo")
    O.aplicado(O.gravar_comando("pausar_fila")["id"])
    with pytest.raises(O.Recusa, match="pausada"):
        O.agente_inicio("builds", "x")
    O.aplicado(O.gravar_comando("retomar_fila")["id"])
    O.sondar(_saida_falsa(0.61))
    with pytest.raises(O.Recusa, match="teto"):
        O.agente_inicio("builds", "x")
    O.mudar_modo("forca_total")
    assert O.agente_inicio("builds", "x")["situacao"] == "trabalhando"


def test_fora_do_ar_depois_de_15_min(mundo):
    O.pulso()
    assert O.para_o_app()["fora_do_ar"] is False
    daqui_a_16 = time.time() + 16 * 60
    assert O.para_o_app(daqui_a_16)["fora_do_ar"] is True


def test_concluidos_de_ontem_nao_aparecem_hoje(mundo):
    O.pulso()
    caminho = mundo.tmp / "orquestrador" / "estado.json"
    estado = json.loads(caminho.read_text(encoding="utf-8"))
    ontem = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    estado["concluidos_hoje"] = [{"id": "a", "parte": "x", "titulo": "velho", "fim": ontem}]
    caminho.write_text(json.dumps(estado), encoding="utf-8")
    assert O.ler_estado()["concluidos_hoje"] == []


# =================================================================== sonda
def test_sonda_com_saida_falsa_grava_uso_e_historico(mundo):
    registro = O.sondar(_saida_falsa(0.34))
    assert registro["medicao"]["sessao_pct"] == 34.0
    assert registro["medicao"]["semana_pct"] == 13.0
    uso = O.ler_uso()
    assert uso["situacao"] == "ok" and uso["medicao"]["sessao_pct"] == 34.0
    assert uso["passou_teto"] is False and uso["fonte"] == "sonda do app"
    assert [p["sessao_pct"] for p in O.historico_do_dia()] == [34.0]


def test_sonda_que_falha_apaga_o_numero_da_tela(mundo):
    O.sondar(_saida_falsa(0.34))
    medido = O.ler_uso()["desde"]

    def estourou(*a, **k):
        raise subprocess.TimeoutExpired("claude", 180)
    registro = O.sondar(estourou)
    assert registro["falhas_seguidas"] == 1 and "180" in registro["motivo"]
    uso = O.ler_uso()
    assert uso["situacao"] == "velha" and uso["medicao"] is None
    assert uso["desde"] == medido                       # "sem medição desde HH:MM"
    # saida sem o evento tambem e falha
    registro = O.sondar(lambda *a, **k: types.SimpleNamespace(stdout='{"type":"x"}'))
    assert registro["falhas_seguidas"] == 2 and "rate_limit_event" in registro["motivo"]
    # o historico so tem a medicao boa
    assert len(O.historico_do_dia()) == 1


def test_sonda_sem_binario_e_falha_dita(mundo, monkeypatch):
    monkeypatch.delenv("CLAUDE_BIN")
    monkeypatch.setattr(O, "binario_claude", lambda: None)
    assert "claude.exe" in O.sondar()["motivo"]
    assert O.ler_uso()["situacao"] == "nunca"


def test_medicao_velha_ou_de_janela_renovada_nao_vale(mundo):
    O.sondar(_saida_falsa(0.34))
    assert O.ler_uso(time.time() + 26 * 60)["situacao"] == "velha"
    O.sondar(_saida_falsa(0.34, renova_em=int(time.time()) + 60))
    uso = O.ler_uso(time.time() + 120)
    assert uso["situacao"] == "velha" and uso["medicao"] is None
    assert "renovou" in uso["motivo"]


def test_fonte_extra_do_vigia_quando_mais_nova(mundo):
    O.sondar(_saida_falsa(0.20))
    (mundo.tmp / "uso_sessao.json").write_text(json.dumps({
        "sessao_pct": 55.0, "sessao_renova_em": time.time() + 3600, "semana_pct": 14.0,
        "semana_renova_em": time.time() + 86400, "gravado_em": time.time() + 1}),
        encoding="utf-8")
    uso = O.ler_uso()
    assert uso["fonte"] == "vigia_uso.py" and uso["medicao"]["sessao_pct"] == 55.0
    assert uso["passou_teto"] is True


def test_janela_da_forca_total(mundo):
    O.sondar(_saida_falsa(0.40, renova_em=int(time.time()) + 15 * 60))
    assert O.ler_uso()["janela_forca_total"] is True
    O.aplicado(O.gravar_comando("forca_total", False)["id"])
    assert O.ler_uso()["janela_forca_total"] is False


def test_ler_rate_limit_ignora_lixo():
    assert O.ler_rate_limit("") is None
    assert O.ler_rate_limit("nao e json\n{\"type\":\"rate_limit_event\"}") is None


# ================================================================ acessos
def test_acessos_sem_segredo(mundo, monkeypatch):
    from builds import contas
    agentes = mundo.tmp / "agents"
    agentes.mkdir()
    (agentes / "builds.md").write_text(
        "---\nname: builds\ndescription: A roleta de builds.\ntools: Read, Bash\n---\n\ncorpo",
        encoding="utf-8")
    lancador = mundo.tmp / "app.cmd"
    lancador.write_text("rem --perigosas aqui não conta\n"
                        "python -m remoto.api_http --local --acoes --publicar\n",
                        encoding="utf-8")
    registro = mundo.tmp / "contas.json"
    registro.write_text(json.dumps({
        "servicos": {"youtube": {"contas": ["principal"], "ativa": {"builds": "principal"}}},
        "identidades": {"youtube": {"principal": {
            "rotulo": "Neural Fights", "id": "UCsegredo", "token": "ya29.SEGREDO"}}}}),
        encoding="utf-8")
    monkeypatch.setattr(contas, "ARQUIVO", registro)
    monkeypatch.setattr(O, "AGENTES", agentes)
    monkeypatch.setattr(O, "LANCADOR", lancador)
    monkeypatch.setattr(O, "CLAUDE_SETTINGS", mundo.tmp / "settings.json")
    (mundo.tmp / "settings.json").write_text('{"remoteControlAtStartup": false}',
                                             encoding="utf-8")
    dados = O.gerar_acessos(modo_permissao="auto")
    texto = (mundo.tmp / "orquestrador" / "acessos.json").read_text(encoding="utf-8")
    assert "SEGREDO" not in texto and "UCsegredo" not in texto
    assert "browser_profile" not in texto and "credentials" not in texto
    assert dados["agentes"] == [{"nome": "builds", "descricao": "A roleta de builds.",
                                 "ferramentas": "Read, Bash"}]
    youtube = next(s for s in dados["contas"] if s["servico"] == "youtube")
    assert youtube["canais"][0] == {"canal": "builds", "conta": "principal",
                                    "destino": "Neural Fights", "propria": True}
    assert dados["app"]["publicar"] is True and dados["app"]["perigosas"] is False
    assert dados["app"]["destino_padrao"] == "YouTube e TikTok"
    assert dados["conectores"] == O.CONECTORES_28_09
    assert dados["recursos"][0]["situacao"] == "desligado na inicialização"
    # sem dizer de novo, os conectores e o modo ficam os que estavam
    assert O.gerar_acessos()["modo_permissao"] == "auto"
    assert O.gerar_acessos(conectores=["Gmail"])["conectores"] == ["Gmail"]


# ============================================================== contestar
def test_contestar_cria_no_no_grimorio_com_commit(servidor, mundo):
    token = _parear(servidor)
    d = O.decisao("Freio de 92% na força total", "parar os agentes em 92%",
                  porque="o limite corta no meio", alternativa="freio em 85%")
    _, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert tela["decisoes"][0]["contestada"] is False
    status, r = _pedir(servidor, "POST", "/api/orquestrador/contestar",
                       {"id": d["id"], "comentario": "prefiro 85%"}, token)
    assert status == 200, r
    assert r["no"] == f"contestada-{d['id']}" and r["commit"].startswith("ok")
    item = json.loads((mundo.repo / "decisoes" / "geral" / f"{r['no']}.json").read_text(
        encoding="utf-8"))
    assert item["situacao"] == "pendente"
    assert [o["id"] for o in item["opcoes"]] == ["manter", "alternativa", "outro"]
    assert "prefiro 85%" in item["contexto"] and "92%" in item["pergunta"]
    ultimo = _git(mundo.repo, "log", "-1", "--format=%s").stdout.strip()
    assert ultimo == "decisão(geral): nova — Contestada: Freio de 92% na força total"
    # o orquestrador fica sabendo por um comando, e a tela marca
    assert O.pendentes()[0]["comando"] == "contestar"
    _, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert tela["decisoes"][0]["contestada"] is True
    # contestar de novo: o no ja existe
    status, _ = _pedir(servidor, "POST", "/api/orquestrador/contestar",
                       {"id": d["id"]}, token)
    assert status == 409
    assert _pedir(servidor, "POST", "/api/orquestrador/contestar",
                  {"id": "naoexiste"}, token)[0] == 409


def test_contestar_na_parte_certa(mundo):
    d = O.decisao("Palco toca os sons", "no Godot", parte="builds")
    assert O.contestar(d["id"])["projeto"] == "builds"
    d2 = O.decisao("Ordem da fila", "x", parte="orquestrador")
    assert O.contestar(d2["id"])["projeto"] == "geral"


def test_a_cli_do_grimorio_usa_a_mesma_funcao(mundo, capsys, monkeypatch):
    chamadas = []
    original = D.adicionar_e_commitar

    def espiao(*a, **k):
        chamadas.append(a[1])
        return original(*a, **k)
    monkeypatch.setattr(D, "adicionar_e_commitar", espiao)
    assert D.main(["adicionar", "--projeto", "geral", "--titulo", "Teste",
                   "--opcao", "Sim", "--commit"]) == 0
    assert chamadas == ["Teste"] and "commit: ok" in capsys.readouterr().out


# ================================================================== fluxo
def test_fluxo_pela_rota_em_segundo_plano(servidor, monkeypatch):
    from remoto import painel_dados
    monkeypatch.setattr(painel_dados, "_fluxo_calcular",
                        lambda: {"etapas": [], "geracoes": [], "alertas": ["x"]})
    monkeypatch.setattr(painel_dados, "FLUXO", painel_dados._Fluxo())
    token = _parear(servidor)
    for _ in range(50):
        status, f = _pedir(servidor, "GET", "/api/orquestrador/fluxo", token=token)
        assert status == 200
        if not f.get("calculando"):
            break
        time.sleep(0.05)
    assert f["alertas"] == ["x"]


def test_o_texto_que_vai_ao_celular_passa_pelo_filtro(servidor):
    token = _parear(servidor)
    O.decisao("Caminho", r"C:\Users\adrian\segredo e https://x.y/?t=abc")
    _, tela = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    escolha = tela["decisoes"][0]["escolha"]
    assert "adrian" not in escolha and "https://" not in escolha
