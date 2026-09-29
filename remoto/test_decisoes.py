# -*- coding: utf-8 -*-
"""A arvore de decisoes: git, bloqueio, respec, sessoes, midia por Range.

Tudo roda num repositorio git TEMPORARIO (no E:, pelo --basetemp), com a
pasta de decisoes, os docs das sessoes e a midia dele. Nada toca o
repositorio real, o registro real, a rede ou o Telegram.
"""
from __future__ import annotations

import http.client
import json
import subprocess
import threading

import pytest

from remoto import acoes, api_http, decisoes as D

VIDEO = bytes(range(256)) * 400            # 102.400 bytes; o conteudo nao importa
IMAGEM = b"\x89PNG\r\n\x1a\n" + b"x" * 5000
DOC = "# Sessão {nome}\n\nDocumento de passagem.\n\n## 1. O que é\n\nTexto.\n"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, encoding="utf-8", check=False)


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "docs" / "sessoes").mkdir(parents=True)
    for parte in ("builds", "app-e-bot"):
        (repo / "docs" / "sessoes" / f"{parte}.md").write_bytes(
            DOC.format(nome=parte).encode())
    (repo / "sujo.md").write_text("original\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "teste@exemplo")
    _git(repo, "config", "user.name", "teste")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", "--", "docs", "sujo.md")
    _git(repo, "commit", "-q", "-m", "inicio")
    monkeypatch.setattr(D, "REPO", repo)
    monkeypatch.setattr(D, "PASTA", repo / "decisoes")
    monkeypatch.setattr(D, "SESSOES", repo / "docs" / "sessoes")
    monkeypatch.setattr(D, "TRAVA", tmp_path / "decisoes.lock")
    monkeypatch.setattr(D, "MIDIA_LOCAL", tmp_path / "local" / "decisoes_midia")
    monkeypatch.setattr(api_http, "ARQUIVO", tmp_path / "app_celular.json")
    avisos = []
    monkeypatch.setattr(acoes, "_entregar", avisos.append)
    midia = tmp_path / "midia"
    midia.mkdir()
    (midia / "duelo_ANTES.mp4").write_bytes(VIDEO)
    (midia / "duelo_DEPOIS.mp4").write_bytes(VIDEO[::-1])
    (midia / "quadro.png").write_bytes(IMAGEM)
    (midia / "segredo.txt").write_text("nao", encoding="utf-8")
    yield type("Mundo", (), {"tmp": tmp_path, "repo": repo, "midia": midia,
                             "avisos": avisos})
    acoes._FILA_AVISOS.join()


def _arvore(mundo):
    """Ferramenta (decidida pela escolha) -> Palco -> Chao, e o Som ao lado."""
    D.adicionar("builds", "Ferramenta do visual", "Qual ferramenta?",
                ["godot=Godot 4", "unity=Unity"], id="ferramenta")
    D.adicionar("builds", "Palco: seguir?", "Seguir com o palco?",
                ["seguir=Seguir", "ajustar=Seguir, com ajustes (comente)",
                 "nao=Não seguir"], id="palco",
                midias=[(mundo.midia / "duelo_ANTES.mp4", "ANTES"),
                        (mundo.midia / "duelo_DEPOIS.mp4", "DEPOIS"),
                        (mundo.midia / "quadro.png", "QUADRO")],
                depende_de=["ferramenta=godot"])
    D.adicionar("builds", "Chão da arena", "Qual chão?",
                ["pedra=Pedra CC0", "ia=Pintada pela IA"], id="chao",
                depende_de=[{"decisao": "palco", "opcao": "seguir"}])


def _commits(repo):
    return _git(repo, "log", "--format=%s").stdout.splitlines()


def _no_commit(repo, ref="HEAD"):
    return set(_git(repo, "show", "--name-only", "--format=", ref).stdout.split())


# ============================================================ o arquivo
def test_um_arquivo_por_decisao_com_diff_limpo(mundo):
    _arvore(mundo)
    alvo = mundo.repo / "decisoes" / "builds" / "palco.json"
    bruto = alvo.read_bytes()
    dados = json.loads(bruto)
    assert bruto == (json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True)
                     + "\n").encode("utf-8")
    assert b"\r" not in bruto and bruto.endswith(b"}\n")
    assert list(dados) == sorted(dados)
    assert dados["situacao"] == "bloqueada" and dados["vigente"] is None
    assert dados["historico"] == []
    assert dados["depende_de"] == [{"decisao": "ferramenta", "opcao": "godot"}]
    assert [o["id"] for o in dados["opcoes"]] == ["seguir", "ajustar", "nao"]
    assert dados["opcoes"][1]["pede_comentario"] is True


def test_midia_aponta_e_nao_vai_para_o_git(mundo, monkeypatch):
    dentro = mundo.repo / "random_builds" / "outputs" / "_ouvir"
    dentro.mkdir(parents=True)
    (dentro / "a.mp4").write_bytes(VIDEO)
    local = mundo.tmp / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    item = D.adicionar("geral", "Teste", "?", ["sim"], id="teste",
                       midias=[(dentro / "a.mp4", "REPO"),
                               (mundo.midia / "quadro.png", "LOCAL")],
                       copiar=False)
    assert item["midias"][0]["caminho"] == "random_builds/outputs/_ouvir/a.mp4"
    assert item["midias"][1]["caminho"] == str((mundo.midia / "quadro.png").resolve())
    copiado = D.adicionar("geral", "Teste 2", "?", ["sim"], id="teste-2",
                          midias=[(mundo.midia / "quadro.png", "X")], copiar=True)
    guardado = copiado["midias"][0]["caminho"]
    assert D.resolver_caminho(guardado).read_bytes() == IMAGEM
    assert D.pasta_midia_local() in D.resolver_caminho(guardado).parents
    for m in item["midias"] + copiado["midias"]:
        assert D.resolver_caminho(m["caminho"]).is_file()


@pytest.mark.parametrize("midia,trecho", [("nao_existe.mp4", "não existe"),
                                          ("segredo.txt", "não toca")])
def test_midia_que_nao_existe_ou_nao_toca_nao_entra(mundo, midia, trecho):
    with pytest.raises(D.Recusa, match=trecho):
        D.adicionar("builds", "X", "?", ["a"], midias=[(mundo.midia / midia, "")])
    assert not list((mundo.repo / "decisoes").glob("*/*.json"))


# ============================================================ a arvore
def test_bloqueia_ate_o_pre_requisito_e_desbloqueia(mundo):
    _arvore(mundo)
    itens = D.carregar()
    assert itens["ferramenta"]["situacao"] == "pendente"
    assert itens["palco"]["situacao"] == "bloqueada"
    assert itens["chao"]["situacao"] == "bloqueada"
    assert itens["ferramenta"]["opcoes"][0]["desbloqueia"] == ["palco"]
    with pytest.raises(D.Recusa, match="bloqueada"):
        D.responder("palco", "seguir", commitar=False)
    D.responder("ferramenta", "godot", commitar=False)
    itens = D.carregar()
    assert itens["palco"]["situacao"] == "pendente"
    assert itens["chao"]["situacao"] == "bloqueada"         # dois niveis
    D.responder("palco", "seguir", commitar=False)
    assert D.carregar()["chao"]["situacao"] == "pendente"


def test_opcao_errada_do_pre_requisito_nao_desbloqueia(mundo):
    _arvore(mundo)
    D.responder("ferramenta", "unity", commitar=False)
    assert D.carregar()["palco"]["situacao"] == "bloqueada"


def test_voltar_e_trocar_manda_para_a_rever_em_todos_os_niveis(mundo):
    _arvore(mundo)
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    D.responder("chao", "pedra", commitar=False)
    assert D.a_rever_se_mudar(D.carregar(), "ferramenta") == ["palco", "chao"]

    evento = D.responder("ferramenta", "unity", "mudei de ideia", commitar=False)
    assert evento["a_rever"] == ["palco", "chao"] and evento["anterior"] == "godot"
    itens = D.carregar()
    assert itens["palco"]["situacao"] == itens["chao"]["situacao"] == "a_rever"
    # nada se apaga: o historico so cresce
    assert [h["opcao"] for h in itens["ferramenta"]["historico"]] == ["godot", "unity"]
    assert itens["palco"]["vigente"]["opcao"] == "seguir"
    with pytest.raises(D.Recusa, match="bloqueada"):
        D.responder("palco", "seguir", commitar=False)

    D.responder("ferramenta", "godot", commitar=False)       # voltou atras
    assert D.carregar()["palco"]["situacao"] == "a_rever"    # pegajoso
    D.responder("palco", "seguir", commitar=False)           # ele confirma
    itens = D.carregar()
    assert itens["palco"]["situacao"] == "decidida"
    assert itens["chao"]["situacao"] == "a_rever"            # esse ainda nao


def test_confirmar_a_mesma_opcao_nao_manda_ninguem_para_a_rever(mundo):
    _arvore(mundo)
    D.responder("ferramenta", "godot", commitar=False)
    D.responder("palco", "seguir", commitar=False)
    assert D.responder("ferramenta", "godot", commitar=False)["a_rever"] == []
    assert D.carregar()["palco"]["situacao"] == "decidida"


def test_depende_de_qualquer_opcao(mundo):
    """"generation_00077 depende do Som real", sem dizer qual opcao."""
    _arvore(mundo)
    D.adicionar("builds", "Refazer a 00077", "?", ["refazer", "descartar"],
                id="g77", depende_de=["ferramenta=*"])
    itens = D.carregar()
    assert itens["g77"]["situacao"] == "bloqueada"
    assert all("g77" in o["desbloqueia"] for o in itens["ferramenta"]["opcoes"])
    D.responder("ferramenta", "unity", commitar=False)
    assert D.carregar()["g77"]["situacao"] == "pendente"
    D.responder("g77", "refazer", commitar=False)
    assert D.responder("ferramenta", "godot", commitar=False)["a_rever"] == ["g77"]


def test_opcao_que_pede_comentario(mundo):
    _arvore(mundo)
    D.responder("ferramenta", "godot", commitar=False)
    with pytest.raises(D.Recusa, match="pede um comentário"):
        D.responder("palco", "ajustar", "  ", commitar=False)
    assert D.responder("palco", "ajustar", "mais contraste", commitar=False)


def test_ciclo_escrito_a_mao_e_recusado(mundo):
    _arvore(mundo)
    alvo = mundo.repo / "decisoes" / "builds" / "ferramenta.json"
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    dados["depende_de"] = [{"decisao": "chao", "opcao": "pedra"}]
    alvo.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(D.Recusa, match="ciclo"):
        D.responder("ferramenta", "godot", commitar=False)


def test_arquivo_ilegivel_recusa(mundo):
    _arvore(mundo)
    (mundo.repo / "decisoes" / "builds" / "chao.json").write_text("{", encoding="utf-8")
    with pytest.raises(D.Recusa, match="ilegível"):
        D.carregar()


def test_eventos_uma_linha_por_resposta(mundo):
    _arvore(mundo)
    D.responder("ferramenta", "godot", "ok", commitar=False)
    D.responder("ferramenta", "unity", commitar=False)
    linhas = [json.loads(l) for l in
              D.caminho_eventos().read_text(encoding="utf-8").splitlines()]
    assert [(l["projeto"], l["id"], l["opcao"]) for l in linhas] == [
        ("builds", "ferramenta", "godot"), ("builds", "ferramenta", "unity")]
    assert linhas[0]["comentario"] == "ok" and linhas[0]["em"]
    assert D.caminho_eventos() == mundo.repo / "decisoes" / "_eventos.jsonl"


# ============================================================ os textos
def test_bloco_da_sessao_e_regenerado_sem_mexer_no_resto(mundo):
    D.adicionar("geral", "Modo de trabalho", "?", ["um=Um projeto por vez"], id="modo")
    D.semear("modo", "um", "2026-09-28")
    _arvore(mundo)
    doc = mundo.repo / "docs" / "sessoes" / "builds.md"
    texto = doc.read_text(encoding="utf-8")
    assert texto.count(D.INICIO) == 1 and texto.count(D.FIM) == 1
    assert texto.startswith("# Sessão builds\n")
    assert "Documento de passagem." in texto and "## 1. O que é" in texto
    bloco = texto.split(D.INICIO)[1].split(D.FIM)[0]
    assert "Modo de trabalho** — Um projeto por vez (28/09/2026)" in bloco
    assert "⏳ **Ferramenta do visual**" in bloco
    assert "2 bloqueada(s)" in bloco
    D.responder("ferramenta", "godot", commitar=False)
    bloco = doc.read_text(encoding="utf-8").split(D.INICIO)[1].split(D.FIM)[0]
    assert "✅ **Ferramenta do visual** — Godot 4" in bloco
    assert "⏳ **Palco: seguir?**" in bloco
    antes = doc.read_bytes()
    D.gerar_textos()
    assert doc.read_bytes() == antes                        # idempotente
    readme = (mundo.repo / "decisoes" / "builds" / "README.md").read_text(encoding="utf-8")
    assert "- ✅ **Ferramenta do visual**" in readme
    assert "  - ⏳ **Palco: seguir?**" in readme
    assert "    - 🔒 **Chão da arena**" in readme


# ============================================================== o commit
def test_commit_so_por_caminho_e_deixa_o_stage_dos_outros(mundo):
    _arvore(mundo)
    (mundo.repo / "outro.txt").write_text("de outro agente\n", encoding="utf-8")
    _git(mundo.repo, "add", "--", "outro.txt")
    (mundo.repo / "sujo.md").write_text("mudanca de outro agente\n", encoding="utf-8")
    evento = D.responder("ferramenta", "godot")
    assert evento["commit"] == "ok"
    assert _commits(mundo.repo)[0] == "decisão(builds): Ferramenta do visual → Godot 4"
    no_commit = _no_commit(mundo.repo)
    assert "decisoes/builds/ferramenta.json" in no_commit
    assert "decisoes/_eventos.jsonl" in no_commit
    assert "decisoes/builds/README.md" in no_commit
    assert "docs/sessoes/builds.md" in no_commit
    assert "outro.txt" not in no_commit and "sujo.md" not in no_commit
    assert "outro.txt" in _git(mundo.repo, "diff", "--cached", "--name-only").stdout
    assert "sujo.md" in _git(mundo.repo, "diff", "--name-only").stdout
    # a seguinte so leva o que mudou
    evento = D.responder("palco", "seguir")
    assert evento["commit"] == "ok"
    assert "decisoes/builds/ferramenta.json" not in _no_commit(mundo.repo)


def test_doc_da_sessao_com_mudanca_de_outro_fica_fora_do_commit(mundo):
    _arvore(mundo)
    D.responder("ferramenta", "godot")                       # os blocos entram
    outro = mundo.repo / "docs" / "sessoes" / "app-e-bot.md"
    outro.write_text(outro.read_text(encoding="utf-8") + "\nlinha de outro agente\n",
                     encoding="utf-8")
    D.adicionar("geral", "Modo", "?", ["um=Um projeto por vez", "varios=Vários"],
                id="modo")
    evento = D.responder("modo", "um")                       # geral: todas as sessoes
    assert evento["commit"].startswith("ok (sem o bloco de: docs/sessoes/app-e-bot.md")
    no_commit = _no_commit(mundo.repo)
    assert "docs/sessoes/builds.md" in no_commit
    assert "docs/sessoes/app-e-bot.md" not in no_commit
    assert "linha de outro agente" in outro.read_text(encoding="utf-8")
    assert "Modo** — Um projeto por vez" in outro.read_text(encoding="utf-8")


def test_index_lock_tenta_de_novo(mundo, monkeypatch):
    _arvore(mundo)
    trava = mundo.repo / ".git" / "index.lock"
    trava.write_text("", encoding="utf-8")
    threading.Timer(1.5, trava.unlink).start()
    evento = D.responder("ferramenta", "godot")
    assert evento["commit"] == "ok"


def test_commit_que_falha_nao_desfaz_a_decisao(mundo, monkeypatch):
    _arvore(mundo)
    monkeypatch.setattr(D, "TENTATIVAS_DE_COMMIT", 2)
    trava = mundo.repo / ".git" / "index.lock"
    trava.write_text("", encoding="utf-8")
    evento = D.responder("ferramenta", "godot")
    assert evento["commit"].startswith("falhou") and "index.lock" in evento["commit"]
    assert D.carregar()["ferramenta"]["vigente"]["opcao"] == "godot"
    assert D.caminho_eventos().is_file()
    assert "commit ficou para depois" in D.texto_do_aviso(evento)
    trava.unlink()
    # a proxima resposta leva o que tinha ficado
    D.responder("palco", "seguir")
    assert "decisoes/builds/ferramenta.json" in _no_commit(mundo.repo)


# ============================================================ o servidor
@pytest.fixture
def servidor(mundo):
    srv = api_http.criar_servidor("127.0.0.1", 0, local=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, caminho, corpo=None, token=None, cabecalhos=None):
    porta = srv.server_address[1]
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
    cab = {"Host": f"127.0.0.1:{porta}", **(cabecalhos or {})}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    if corpo is not None:
        corpo = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    conexao.request(metodo, caminho, body=corpo, headers=cab)
    resp = conexao.getresponse()
    dados = resp.read()
    conexao.close()
    return resp, dados


def _token():
    return api_http.trocar_codigo(api_http.novo_codigo(), "moto")


def _url(srv, item_id, indice, token):
    resp, dados = _pedir(srv, "GET", f"/api/decisao/{item_id}/midia/{indice}",
                         token=token)
    assert resp.status == 200, dados
    return json.loads(dados)


def test_sem_token_nada_sai(servidor, mundo):
    _arvore(mundo)
    assert _pedir(servidor, "GET", "/api/decisoes")[0].status == 401
    assert _pedir(servidor, "GET", "/api/decisao/palco/midia/0")[0].status == 401
    resp, _ = _pedir(servidor, "POST", "/api/decisao/responder",
                     {"id": "ferramenta", "opcao": "godot"})
    assert resp.status == 401
    assert not D.caminho_eventos().exists()


def test_a_arvore_vai_ao_app_sem_caminho(servidor, mundo):
    _arvore(mundo)
    resp, dados = _pedir(servidor, "GET", "/api/decisoes", token=_token())
    assert resp.status == 200
    corpo = json.loads(dados)
    assert str(mundo.midia) not in dados.decode("utf-8") and "caminho" not in corpo["itens"]["palco"]["midias"][0]
    assert [n["id"] for n in corpo["arvores"]["builds"]] == ["ferramenta", "palco", "chao"]
    assert [n["nivel"] for n in corpo["arvores"]["builds"]] == [0, 1, 2]
    palco = corpo["itens"]["palco"]
    assert palco["situacao"] == "bloqueada"
    assert palco["depende_de"][0] == {"decisao": "ferramenta", "opcao": "godot",
                                      "titulo": "Ferramenta do visual",
                                      "opcao_rotulo": "Godot 4", "ok": False}
    builds = next(p for p in corpo["projetos"] if p["id"] == "builds")
    assert builds["contagem"] == {"bloqueada": 2, "pendente": 1, "decidida": 0,
                                  "a_rever": 0, "nao_lidas": 0}


def test_video_toca_por_range(servidor, mundo):
    _arvore(mundo)
    ficha = _url(servidor, "palco", 0, _token())
    assert ficha["url"].startswith("/v/") and ficha["tipo"] == "video/mp4"
    total = len(VIDEO)
    resp, corpo = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": "bytes=0-9"})
    assert resp.status == 206 and corpo == VIDEO[:10]
    assert resp.getheader("Content-Range") == f"bytes 0-9/{total}"
    assert resp.getheader("Content-Type") == "video/mp4"
    assert resp.getheader("Accept-Ranges") == "bytes"
    resp, corpo = _pedir(servidor, "GET", ficha["url"],
                         cabecalhos={"Range": f"bytes=50000-{total - 1}"})
    assert resp.status == 206 and corpo == VIDEO[50000:]
    resp, _ = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": f"bytes={total}-"})
    assert resp.status == 416 and resp.getheader("Content-Range") == f"bytes */{total}"
    resp, _ = _pedir(servidor, "GET", ficha["url"], cabecalhos={"Range": "linhas=0-9"})
    assert resp.status == 416


def test_imagem_vem_inteira_com_o_tipo_certo(servidor, mundo):
    _arvore(mundo)
    ficha = _url(servidor, "palco", 2, _token())
    resp, corpo = _pedir(servidor, "GET", ficha["url"])
    assert resp.status == 200 and corpo == IMAGEM
    assert resp.getheader("Content-Type") == "image/png"


@pytest.mark.parametrize("caminho", [
    "/api/decisao/palco/midia/3",
    "/api/decisao/nao-existe/midia/0",
    "/api/decisao/..%2F..%2Fsegredo/midia/0",
    "/api/decisao/palco/midia/-1",
    "/api/decisao/palco/midia/0/../../segredo.txt",
])
def test_midia_fora_do_registro_e_recusada(servidor, mundo, caminho):
    _arvore(mundo)
    resp, _ = _pedir(servidor, "GET", caminho, token=_token())
    assert resp.status == 404


def test_midia_que_sumiu_avisa(servidor, mundo):
    _arvore(mundo)
    (mundo.midia / "duelo_ANTES.mp4").unlink()
    token = _token()
    resp, dados = _pedir(servidor, "GET", "/api/decisao/palco/midia/0", token=token)
    assert resp.status == 404 and "não existe mais" in json.loads(dados)["erro"]
    resp, dados = _pedir(servidor, "GET", "/api/decisoes", token=token)
    midias = json.loads(dados)["itens"]["palco"]["midias"]
    assert [m["existe"] for m in midias] == [False, True, True]


def test_responder_pelo_app_grava_commita_e_avisa(servidor, mundo):
    _arvore(mundo)
    token = _token()
    resp, dados = _pedir(servidor, "POST", "/api/decisao/responder",
                         {"id": "palco", "opcao": "seguir"}, token=token)
    assert resp.status == 409 and "bloqueada" in json.loads(dados)["erro"]
    resp, dados = _pedir(servidor, "POST", "/api/decisao/responder",
                         {"id": "ferramenta", "opcao": "godot", "comentario": "vai"},
                         token=token)
    assert resp.status == 200, dados
    evento = json.loads(dados)["evento"]
    assert evento["commit"] == "ok" and evento["opcao_rotulo"] == "Godot 4"
    assert _commits(mundo.repo)[0] == "decisão(builds): Ferramenta do visual → Godot 4"
    acoes._FILA_AVISOS.join()
    (aviso,) = mundo.avisos
    assert "Adrian decidiu: Ferramenta do visual → Godot 4" in aviso and "vai" in aviso
    resp, _ = _pedir(servidor, "POST", "/api/decisao/responder",
                     {"id": "nao-existe", "opcao": "x"}, token=token)
    assert resp.status == 404


def test_a_tela_e_servida(servidor, mundo):
    resp, corpo = _pedir(servidor, "GET", "/decisoes.js")
    assert resp.status == 200 and b"decisoesMostrar" in corpo and b"a_rever_se_mudar" in corpo
    assert b"style:" not in corpo                  # a CSP nao deixa estilo inline
    resp, corpo = _pedir(servidor, "GET", "/")
    assert b'data-tela="decisoes"' in corpo and b'src="decisoes.js"' in corpo


# ================================================================== cli
def test_cli(mundo, capsys):
    assert D.main(["adicionar", "--projeto", "builds", "--titulo", "Ferramenta",
                   "--pergunta", "Qual?", "--opcao", "godot=Godot 4",
                   "--opcao", "unity=Unity|a outra", "--id", "ferramenta"]) == 0
    assert D.main(["adicionar", "--projeto", "builds", "--titulo", "Palco",
                   "--opcao", "seguir=Seguir", "--depende", "ferramenta=godot",
                   "--midia", f"{mundo.midia / 'quadro.png'}|QUADRO", "--copiar",
                   "--commit"]) == 0
    saida = capsys.readouterr().out
    assert "registrada: builds/palco [bloqueada]" in saida and "commit: ok" in saida
    assert D.main(["listar", "--situacao", "bloqueada"]) == 0
    assert "palco" in capsys.readouterr().out
    assert D.main(["responder", "ferramenta", "godot", "--sem-commit"]) == 0
    assert "commit: desligado" in capsys.readouterr().out
    assert D.main(["arvore", "--projeto", "builds"]) == 0
    saida = capsys.readouterr().out
    assert "- ✅ **Ferramenta** — Godot 4" in saida and "  - ⏳ **Palco**" in saida
    assert D.main(["responder", "palco", "nao-existe", "--sem-commit"]) == 2
    assert D.main(["onde"]) == 0
    assert str(D.caminho_eventos()) in capsys.readouterr().out
    with pytest.raises(SystemExit):
        D.main(["adicionar", "--projeto", "nenhum", "--titulo", "x"])


def test_cli_acrescenta_midia_sem_mudar_os_indices(mundo, capsys):
    _arvore(mundo)
    antes = [m["caminho"] for m in D.carregar()["palco"]["midias"]]
    (mundo.midia / "lote2.mp4").write_bytes(VIDEO)
    assert D.main(["midia", "palco", "--midia", f"{mundo.midia / 'lote2.mp4'}|lote 2",
                   "--commit"]) == 0
    saida = capsys.readouterr().out
    assert "builds/palco: 4 mídia(s)" in saida and "commit: ok" in saida
    item = D.carregar()["palco"]
    assert [m["caminho"] for m in item["midias"][:3]] == antes
    assert item["midias"][3]["rotulo"] == "lote 2"
    assert item["situacao"] == "bloqueada" and item["historico"] == []
    with pytest.raises(D.Recusa, match="não existe"):
        D.acrescentar_midias("palco", [(mundo.midia / "sumiu.mp4", "")])
    with pytest.raises(KeyError):
        D.acrescentar_midias("nao-existe", [(mundo.midia / "lote2.mp4", "")])


def test_nao_ha_projeto_fora_da_lista(mundo):
    with pytest.raises(D.Recusa, match="projeto desconhecido"):
        D.adicionar("zombie", "X", "?", ["a"])
    assert set(D.PROJETOS) == {"geral", "builds", "historias", "publicacao", "metricas",
                               "app-e-bot", "painel-e-vila", "jogo-zombie"}
