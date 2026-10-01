# -*- coding: utf-8 -*-
"""A Oficina do Codex e os Modelos no app (01/10/2026, tarefa 52dc403c).

- `/api/delegados` e `/api/delegado/<id>`: so leitura, com token, leitura
  incremental por offset (o pesado so na primeira carga ou com `completo`);
- os tres seletores de modelo na Mesa: viram COMANDO (pendente ate o
  orquestrador aplicar); o `aplicado` grava `modelo_agentes`/`modelo_codex` no
  `config.json` e o do Gemini no `config/llm.json` (o do teste);
- o `llm.json` regravado sai com a MESMA forma (listas numa linha so): mudar o
  modelo nao pode virar um diff do arquivo inteiro.

Nada chama o Codex, o Claude ou o navegador; tudo em `tmp_path`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from remoto import delegar, orquestrador as O
from remoto.test_orquestrador import _parear, _pedir, mundo, servidor  # noqa: F401

LLM_REAL = Path(__file__).resolve().parents[1] / "historias" / "config" / "llm.json"


@pytest.fixture
def oficina(mundo, monkeypatch):                                  # noqa: F811
    monkeypatch.setattr(delegar, "PASTA", mundo.tmp / "delegados")
    monkeypatch.setattr(delegar, "CODEX_HOME", mundo.tmp / "codexhome")
    monkeypatch.setattr(delegar, "CODEX", ["nao-existe-codex-de-verdade"])
    llm = mundo.tmp / "llm.json"
    llm.write_text(LLM_REAL.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(O, "LLM_JSON", llm)
    mundo.llm = llm
    return mundo


def _tarefa(mundo, tid="t01", situacao="rodando", eventos=3):
    pasta = mundo.tmp / "delegados" / tid
    pasta.mkdir(parents=True, exist_ok=True)
    estado = {"id": tid, "ia": "codex", "situacao": situacao, "criado_em": "2026-10-01T18:00:00",
              "titulo": "Conserte o X", "modelo": "gpt-6-luna", "worktree": r"E:\segredo\wt",
              "branch": "delegar/codex-t01", "base": "abc", "permitidos": ["remoto/**"],
              "pid": 999999, "inicio": "2026-10-01T18:00:05", "tokens": {"entrada": 1000},
              "rodadas": [{}], "diff": None, "testes": None}
    (pasta / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    with open(pasta / "eventos.jsonl", "w", encoding="utf-8") as fh:
        for n in range(1, eventos + 1):
            fh.write(json.dumps({"n": n, "em": "2026-10-01T18:00:0%d" % n, "ev": {
                "type": "item.completed", "item": {"type": "agent_message",
                                                   "text": f"passo {n}"}}}) + "\n")
    (pasta / "diff.patch").write_text("diff --git a/remoto/x.py b/remoto/x.py\n+X = 1\n",
                                      encoding="utf-8")
    (pasta / "tarefa.md").write_text("# Conserte o X\n", encoding="utf-8")
    return pasta


# ================================================================ Oficina
def test_oficina_sem_token_e_caso_zero(servidor, oficina):        # noqa: F811
    assert _pedir(servidor, "GET", "/api/delegados")[0] == 401
    assert _pedir(servidor, "GET", "/api/delegado/t01")[0] == 401
    token = _parear(servidor)
    status, d = _pedir(servidor, "GET", "/api/delegados", token=token)
    assert status == 200 and d["delegados"] == [] and d["rodando"] == 0
    assert d["uso"]["situacao"] == "desconhecido" and d["uso"]["pct"] is None


def test_oficina_lista_e_eventos_por_offset(servidor, oficina):   # noqa: F811
    pasta = _tarefa(oficina)
    token = _parear(servidor)
    status, d = _pedir(servidor, "GET", "/api/delegados", token=token)
    assert status == 200
    t = d["delegados"][0]
    # o pid 999999 nao existe: a tela diz que o processo sumiu, nao "rodando"
    assert t["id"] == "t01" and t["situacao"] == "sumiu" and t["modelo"] == "gpt-6-luna"
    assert "worktree" not in t and "segredo" not in json.dumps(d)
    status, d = _pedir(servidor, "GET", "/api/delegado/t01?desde=-1", token=token)
    assert status == 200
    assert [e["texto"] for e in d["eventos"]] == ["passo 1", "passo 2", "passo 3"]
    assert d["diff_texto"].startswith("diff --git") and d["pedido"].startswith("# Conserte")
    offset = d["offset"]
    status, d = _pedir(servidor, "GET", f"/api/delegado/t01?desde={offset}", token=token)
    assert d["eventos"] == [] and "diff_texto" not in d
    with open(pasta / "eventos.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"n": 4, "em": "2026-10-01T18:00:09", "ev": {
            "type": "item.started", "item": {"type": "command_execution",
                                             "command": "python -m pytest remoto -q"}}}) + "\n")
    status, d = _pedir(servidor, "GET", f"/api/delegado/t01?desde={offset}", token=token)
    assert [(e["tipo"], e["texto"]) for e in d["eventos"]] == [("testa",
                                                                "python -m pytest remoto -q")]
    status, d = _pedir(servidor, "GET", f"/api/delegado/t01?desde={d['offset']}&completo=1",
                       token=token)
    assert d["diff_texto"]


def test_oficina_id_desconhecido_ou_torto(servidor, oficina):     # noqa: F811
    token = _parear(servidor)
    assert _pedir(servidor, "GET", "/api/delegado/naoexiste", token=token)[0] == 404
    assert _pedir(servidor, "GET", "/api/delegado/..%2Fx", token=token)[0] == 404
    assert _pedir(servidor, "GET", "/api/delegado/A", token=token)[0] == 404


def test_oficina_nao_tem_rota_de_escrita(servidor, oficina):      # noqa: F811
    _tarefa(oficina)
    token = _parear(servidor)
    for rota in ("/api/delegado/t01", "/api/delegados", "/api/delegado/t01/aplicar"):
        assert _pedir(servidor, "POST", rota, {"x": 1}, token=token)[0] == 404


def test_mesa_mostra_o_resumo_dos_delegados(servidor, oficina):   # noqa: F811
    _tarefa(oficina, situacao="terminou")
    token = _parear(servidor)
    status, d = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert status == 200
    assert d["delegados"]["total"] == 1 and d["delegados"]["ultimas"][0]["id"] == "t01"


# ================================================================ Modelos
def test_modelos_para_a_mesa_mostram_o_que_vale_e_as_opcoes(servidor, oficina):   # noqa: F811
    token = _parear(servidor)
    status, d = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    m = d["modelos"]
    assert [o["id"] for o in m["claude"]["opcoes"]] == ["opus", "sonnet", "haiku", "fable"]
    assert m["claude"]["vigente"] is None and "/model" in m["claude"]["nota"]
    assert m["codex"]["vigente"] is None and m["codex"]["opcoes"]
    assert [o["id"] for o in m["gemini"]["opcoes"]] == ["pro", "raciocinio", "flash", "flash-lite"]
    assert m["gemini"]["vigente"] is None


def test_modelo_vira_comando_e_so_vale_no_aplicado(servidor, oficina):   # noqa: F811
    token = _parear(servidor)
    for comando, valor in (("modelo_agentes", "opus"), ("modelo_codex", "GPT-6-Luna"),
                           ("modelo_gemini", "flash")):
        status, d = _pedir(servidor, "POST", "/api/orquestrador/comando",
                           {"comando": comando, "valor": valor}, token=token)
        assert status == 200, d
    assert O.ler_config()["modelo_agentes"] is None                # ainda pendente
    pend = {c["comando"]: c for c in O.pendentes()}
    assert pend["modelo_codex"]["valor"] == "gpt-6-luna"
    for c in O.pendentes():
        O.aplicado(c["id"])
    config = O.ler_config()
    assert config["modelo_agentes"] == "opus" and config["modelo_codex"] == "gpt-6-luna"
    llm = json.loads(oficina.llm.read_text(encoding="utf-8"))
    assert llm["gemini"]["modelo_preferido"] == ["3.6 flash", "flash"]
    assert llm["papeis"] == json.loads(LLM_REAL.read_text(encoding="utf-8"))["papeis"]
    status, d = _pedir(servidor, "GET", "/api/orquestrador", token=token)
    assert d["modelos"]["claude"]["vigente"] == "opus"
    assert d["modelos"]["codex"]["vigente"] == "gpt-6-luna"
    assert d["modelos"]["gemini"]["vigente"] == "flash"
    # o despachante usa o da Mesa quando a tarefa nao diz
    assert delegar.modelo_configurado() == "gpt-6-luna"
    hist = [h["chave"] for h in O.historico_da_config(20)]
    assert "modelo_agentes" in hist and "modelo_codex" in hist and "modelo_gemini" in hist


def test_modelo_padrao_desfaz(oficina):
    O.gravar_comando("modelo_gemini", "flash")
    O.gravar_comando("modelo_agentes", "haiku")
    for c in O.pendentes():
        O.aplicado(c["id"])
    O.gravar_comando("modelo_gemini", None)
    O.gravar_comando("modelo_agentes", None)
    for c in O.pendentes():
        O.aplicado(c["id"])
    assert O.ler_config()["modelo_agentes"] is None
    assert oficina.llm.read_text(encoding="utf-8") == LLM_REAL.read_text(encoding="utf-8")


@pytest.mark.parametrize("comando,valor", [("modelo_agentes", "gpt-4"),
                                           ("modelo_agentes", 3),
                                           ("modelo_codex", "gpt 6; rm -rf"),
                                           ("modelo_gemini", "ultra")])
def test_modelo_invalido_e_recusado_na_entrada(servidor, oficina, comando, valor):   # noqa: F811
    token = _parear(servidor)
    status, d = _pedir(servidor, "POST", "/api/orquestrador/comando",
                       {"comando": comando, "valor": valor}, token=token)
    assert status == 409, d
    assert O.pendentes() == []


def test_llm_json_regravado_tem_a_mesma_forma():
    """Ida e volta no arquivo real: nenhum byte muda."""
    texto = LLM_REAL.read_text(encoding="utf-8")
    assert O._json_do_llm(json.loads(texto)) == texto


def test_config_velha_sem_as_chaves_de_modelo_nao_relê_o_grimorio(oficina, monkeypatch):
    (O.pasta()).mkdir(parents=True, exist_ok=True)
    O.arquivo("config.json").write_text(json.dumps(
        {"max_paralelo": 3, "modo": "paralelo", "teto_sessao_pct": 50,
         "forca_total_antes_min": None, "fila_pausada": False, "sonda_min": 10}),
        encoding="utf-8")

    def nao(*_a, **_k):
        raise AssertionError("leu o Grimório a cada ler_config")
    monkeypatch.setattr(O, "padrao_do_grimorio", nao)
    config = O.ler_config()
    assert config["max_paralelo"] == 3 and config["modelo_agentes"] is None
