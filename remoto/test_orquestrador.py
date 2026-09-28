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


# ======================================= a capacidade vira regra (Grimorio)
# Decisao do Adrian `geral/capacidade-pelo-app` = "substitui": o que ele muda
# na Mesa (ou manda no chat) vira a regra, e o no do Grimorio e respondido
# sozinho, com commit. Os nos sao COPIAS dos reais, num repositorio temporario.
REAIS_GERAL = D.RAIZ / "decisoes" / "geral"
NOS_DA_CAPACIDADE = ("modo-de-trabalho", "teto-de-uso", "forca-total-ainda-vale",
                     "capacidade-pelo-app")


def _grimorio_geral(mundo, *, dependencia_antiga=False):
    destino = mundo.repo / "decisoes" / "geral"
    destino.mkdir(parents=True, exist_ok=True)
    for no in NOS_DA_CAPACIDADE:
        item = json.loads((REAIS_GERAL / f"{no}.json").read_text(encoding="utf-8"))
        if dependencia_antiga and no == "capacidade-pelo-app":
            item["depende_de"] = [{"decisao": "modo-de-trabalho", "opcao": "*"}]
        if dependencia_antiga and no == "forca-total-ainda-vale":
            item["depende_de"] = [{"decisao": "teto-de-uso", "opcao": "*"}]
        (destino / f"{no}.json").write_bytes(D._canonico(item))
    _git(mundo.repo, "add", "--", "decisoes")
    _git(mundo.repo, "commit", "-q", "-m", "grimorio")
    return D.carregar()


def _ultimo_commit(repo):
    return _git(repo, "log", "-1", "--format=%s").stdout.strip()


def test_os_nos_reais_da_capacidade_nao_dependem_do_modo_nem_do_teto():
    # 28/09 20:29: responder o modo (paralelo) mandou `capacidade-pelo-app`
    # para "a rever", porque ela dependia de modo-de-trabalho. A regra vale em
    # qualquer modo; a forca total, com qualquer teto.
    for no, pai in (("capacidade-pelo-app", "modo-de-trabalho"),
                    ("forca-total-ainda-vale", "teto-de-uso")):
        item = json.loads((REAIS_GERAL / f"{no}.json").read_text(encoding="utf-8"))
        assert pai not in {d["decisao"] for d in item.get("depende_de") or []}, no


def test_mudar_o_paralelo_pela_mesa_responde_o_modo_de_trabalho(mundo):
    _grimorio_geral(mundo)
    O.mudar_modo("paralelo")                 # operacional: nao responde nada
    O.aplicado(O.gravar_comando("max_paralelo", 3, "614c026b")["id"])
    linha = O.comandos_com_situacao()[0][-1]
    assert "Grimório: modo-de-trabalho → Vários projetos em paralelo" in linha["nota"]
    item = D.carregar()["modo-de-trabalho"]
    assert item["vigente"]["opcao"] == "paralelo"
    assert "pela Mesa de comando: paralelo, até 3 agentes" in item["vigente"]["comentario"]
    ultimo = item["historico"][-1]
    assert ultimo["origem"] == "mesa" and ultimo["aparelho"] == "614c026b"
    assert _ultimo_commit(mundo.repo).startswith("decisão(geral): Modo de trabalho")
    # e a regra da Mesa nao foi para "a rever"
    assert D.carregar()["capacidade-pelo-app"]["situacao"] == "decidida"


def test_voltar_a_um_por_vez_responde_um(mundo):
    _grimorio_geral(mundo)
    O.mudar_modo("paralelo")
    O.aplicado(O.gravar_comando("modo", "um_por_vez")["id"])
    item = D.carregar()["modo-de-trabalho"]
    assert item["vigente"]["opcao"] == "um"
    assert O.ler_estado()["modo"] == "um_por_vez"
    # e o `capacidade-pelo-app` continua valendo (a aresta que o derrubava saiu)
    assert D.carregar()["capacidade-pelo-app"]["situacao"] == "decidida"


def test_a_dependencia_antiga_derrubava_a_regra(mundo):
    # o defeito, reproduzido: com a aresta antiga, trocar o modo manda a regra
    # da Mesa para "a rever"; a nota do `aplicado` diz isso na tela.
    _grimorio_geral(mundo, dependencia_antiga=True)
    O.mudar_modo("paralelo")
    O.aplicado(O.gravar_comando("modo", "um_por_vez")["id"])
    assert D.carregar()["capacidade-pelo-app"]["situacao"] == "a_rever"
    assert "a rever" in O.comandos_com_situacao()[0][-1]["nota"]


def test_teto_e_forca_total_pela_mesa(mundo):
    _grimorio_geral(mundo)
    O.aplicado(O.gravar_comando("teto_uso", 60)["id"])
    teto = D.carregar()["teto-de-uso"]
    assert teto["vigente"]["opcao"] == "outro"
    assert "passou de 60% da sessão" in teto["vigente"]["comentario"]
    O.aplicado(O.gravar_comando("teto_uso", 50)["id"])
    assert D.carregar()["teto-de-uso"]["vigente"]["opcao"] == "cinquenta"
    # a forca total nao foi para "a rever" com a troca do teto
    assert D.carregar()["forca-total-ainda-vale"]["situacao"] == "decidida"
    O.aplicado(O.gravar_comando("forca_total", False)["id"])
    assert D.carregar()["forca-total-ainda-vale"]["vigente"]["opcao"] == "so-quando-eu-pedir"
    O.aplicado(O.gravar_comando("forca_total", True)["id"])
    assert D.carregar()["forca-total-ainda-vale"]["vigente"]["opcao"] == "ligada"


def test_sem_mudanca_nao_mexe_no_grimorio(mundo):
    _grimorio_geral(mundo)
    antes = len(D.carregar()["teto-de-uso"]["historico"])
    O.aplicado(O.gravar_comando("teto_uso", 50)["id"])          # ja era 50
    assert O.comandos_com_situacao()[0][-1]["nota"] == "já estava assim"
    assert len(D.carregar()["teto-de-uso"]["historico"]) == antes


def test_grimorio_sem_o_no_nao_impede_a_config(mundo):
    # repositorio vazio: a config vale, e a nota diz o que faltou
    O.aplicado(O.gravar_comando("max_paralelo", 2)["id"])
    assert O.ler_config()["max_paralelo"] == 2
    assert "não existe o nó modo-de-trabalho" in O.comandos_com_situacao()[0][-1]["nota"]


def test_o_modo_operacional_nao_vira_regra(mundo):
    _grimorio_geral(mundo)
    antes = json.dumps(D.carregar()["modo-de-trabalho"], sort_keys=True)
    O.mudar_modo("forca_total")
    assert json.dumps(D.carregar()["modo-de-trabalho"], sort_keys=True) == antes
    assert "modo operacional" in O.ler_estado()["principal"]["movimento"]


def test_capacidade_pelo_chat_vira_regra_igual_a_mesa(mundo, capsys):
    _grimorio_geral(mundo)
    O.mudar_modo("um_por_vez")               # operacional: o Grimorio segue "paralelo"
    respostas_antes = len(D.carregar()["modo-de-trabalho"]["historico"])
    assert O.main(["capacidade", "--max-paralelo", "3", "--modo", "paralelo",
                   "--fonte", "chat", "--porque", "trabalhe em duas tarefas"]) == 0
    saida = capsys.readouterr().out
    assert "max_paralelo=3" in saida and "Grimório: modo-de-trabalho" in saida
    assert O.ler_config()["max_paralelo"] == 3
    # nunca aparece como pendente (o `esperar` nao acorda por isso)
    assert O.pendentes() == []
    lista = O.comandos_com_situacao()[0]
    feito = [c for c in lista if c["comando"] == "max_paralelo"][-1]
    assert feito["situacao"] == "aplicado" and feito["fonte"] == "chat"
    assert "trabalhe em duas tarefas" in feito["nota"]
    historico = [json.loads(linha) for linha in (mundo.tmp / "orquestrador" /
                 "config_historico.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(h["chave"], h["para"], h["origem"]) for h in historico[-2:]] == [
        ("max_paralelo", 3, "chat"), ("modo", "paralelo", "chat")]
    item = D.carregar()["modo-de-trabalho"]
    # UMA resposta, com a config final: nada de "um por vez" no meio (o max
    # mudou antes do modo, que ainda era "um por vez")
    assert len(item["historico"]) == respostas_antes + 1
    assert item["historico"][-1]["origem"] == "chat"
    assert "no chat: paralelo, até 3 agentes" in item["vigente"]["comentario"]
    assert "nas palavras dele: trabalhe em duas tarefas" in item["vigente"]["comentario"]
    # a tela mostra a fonte, e o Grimorio bate com a Mesa
    tela = O.para_o_app()
    assert tela["historico_config"][0]["origem"] == "chat"
    assert all(g["bate"] for g in tela["grimorio"]), tela["grimorio"]


def test_capacidade_recusa_valor_ruim_e_nada_muda(mundo, capsys):
    assert O.main(["capacidade", "--max-paralelo", "9"]) == 3
    assert O.main(["capacidade"]) == 3
    assert "diga o que muda" in capsys.readouterr().err
    assert not (mundo.tmp / "orquestrador" / "config.json").exists()


def test_a_tela_mostra_quando_o_grimorio_diverge(mundo):
    _grimorio_geral(mundo)
    O.capacidade([("teto_uso", 70)])
    # alguem responde o no a mao com outra coisa: a Mesa avisa
    D.responder("teto-de-uso", "cinquenta", commitar=False)
    teto = next(g for g in O.para_o_app()["grimorio"] if g["no"] == "teto-de-uso")
    assert teto["bate"] is False and "70%" in teto["esperado"]


# ============================================= a sessao principal, na tela
def test_eu_e_os_movimentos_da_sessao_principal(mundo, capsys):
    assert O.para_o_app()["principal"]["relato"] is None          # caso ZERO
    assert O.main(["eu", "lendo o desenho da Mesa"]) == 0
    capsys.readouterr()
    agente = O.agente_inicio("app-e-bot", "Mesa")["id"]
    principal = O.para_o_app()["principal"]
    assert principal["relato"] == "lendo o desenho da Mesa"
    assert principal["movimento"] == "disparou [app-e-bot] Mesa"
    O.agente_fim(agente)
    tela = O.para_o_app()["principal"]
    assert tela["movimento"] == "fechou [app-e-bot] Mesa: concluido"
    # a linha do tempo vem da mais nova para a mais velha, e tem teto
    assert [x["tipo"] for x in tela["linha"]] == ["acao", "acao", "relato"]
    for n in range(O.LINHA_DO_TEMPO_MAX + 5):
        O.eu(f"passo {n}")
    assert len(O.para_o_app()["principal"]["linha"]) == O.LINHA_DO_TEMPO_MAX
    assert O.main(["estado"]) == 0
    assert "SESSÃO PRINCIPAL" in capsys.readouterr().out
    assert O.main(["eu", "  "]) == 3


def test_aplicar_entra_na_linha_do_tempo(mundo):
    c = O.gravar_comando("mensagem", "oi")
    O.aplicado(c["id"], recusado="só teste")
    assert O.ler_estado()["principal"]["movimento"].startswith("recusou mensagem")


# ==================================================== a fila, pelo app
def test_por_e_tirar_da_fila_pelo_app(servidor, mundo):
    token = _parear(servidor)
    status, _ = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": "adicionar_a_fila",
                        "valor": {"parte": "builds", "item": "olhar a 00085"}}, token)
    assert status == 200
    O.aplicado(O.pendentes()[0]["id"])
    fila = O.ler_estado()["fila"]
    assert [(f["parte"], f["item"], f["pedido"]) for f in fila] == \
        [("builds", "olhar a 00085", "Adrian")]
    status, _ = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": "tirar_da_fila", "valor": fila[0]["id"]}, token)
    assert status == 200
    O.aplicado(O.pendentes()[0]["id"])
    assert O.ler_estado()["fila"] == []
    assert O.ler_estado()["principal"]["movimento"] ==         "aplicou tirar da fila: [builds] olhar a 00085"
    # tirar o que nao existe: o `aplicado` recusa, e o orquestrador registra
    fantasma = O.gravar_comando("tirar_da_fila", "nao-existe")
    with pytest.raises(O.Recusa):
        O.aplicado(fantasma["id"])
    status, _ = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": "adicionar_a_fila", "valor": {"parte": "x"}}, token)
    assert status == 409


# ============================================ decisoes: tirar uma aresta
def test_tirar_dependencia_devolve_a_resposta_que_ele_tinha(mundo, capsys):
    _grimorio_geral(mundo, dependencia_antiga=True)
    D.responder("modo-de-trabalho", "um", commitar=False)       # derruba a regra
    item = D.carregar()["capacidade-pelo-app"]
    assert item["situacao"] == "a_rever"
    vigente, historico = dict(item["vigente"]), list(item["historico"])
    assert D.main(["tirar-dependencia", "capacidade-pelo-app", "modo-de-trabalho",
                   "--nota", "vale em qualquer modo"]) == 0
    assert "voltou a valer" in capsys.readouterr().out
    depois = D.carregar()["capacidade-pelo-app"]
    assert depois["situacao"] == "decidida" and depois["depende_de"] == []
    assert depois["vigente"] == vigente                        # a MESMA resposta
    assert depois["historico"][:-1] == historico               # o historico so cresce
    assert depois["historico"][-1]["origem"] == "correcao"
    assert depois["historico"][-1]["nota"] == "vale em qualquer modo"
    assert "capacidade-pelo-app" not in [
        x for o in D.carregar()["modo-de-trabalho"]["opcoes"] for x in o["desbloqueia"]]
    assert "deixa de depender" in _ultimo_commit(mundo.repo)
    # sem a aresta, ou sem nota: recusa
    assert D.main(["tirar-dependencia", "capacidade-pelo-app", "modo-de-trabalho",
                   "--nota", "x"]) == 2
    with pytest.raises(D.Recusa):
        D.tirar_dependencia("forca-total-ainda-vale", "teto-de-uso", "  ")


def test_sem_config_a_mesa_nasce_como_o_grimorio_diz(mundo):
    # caso ZERO com o Grimorio de verdade: nada de "um por vez" contra um
    # Grimorio que diz "paralelo" (28/09 20:29, max_paralelo 2)
    _grimorio_geral(mundo)
    config = O.ler_config()
    assert config["modo"] == "paralelo" and config["max_paralelo"] == 2
    assert config["teto_sessao_pct"] == 50 and config["forca_total_antes_min"] == 20
    assert all(g["bate"] for g in O.para_o_app()["grimorio"])
    # a config gravada manda sobre o padrao
    O.capacidade([("teto_uso", 60)])
    assert O.ler_config()["teto_sessao_pct"] == 60
    (mundo.tmp / "orquestrador" / "config.json").unlink()
    assert O.ler_config()["teto_sessao_pct"] == 60        # agora o Grimorio diz 60

