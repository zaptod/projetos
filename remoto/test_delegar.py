# -*- coding: utf-8 -*-
"""O despachante do Codex (remoto/delegar.py), de ponta a ponta, com dublê.

NENHUM teste chama o Codex de verdade: `delegar.CODEX` aponta sempre para
`remoto/duble_codex.py` (fixture autouse), e o `~/.codex` e uma pasta do
teste. O repositorio e um git de brinquedo em `tmp_path`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from remoto import claude_estado, delegar

DUBLE = Path(__file__).with_name("duble_codex.py")
AGORA = datetime(2026, 10, 1, 18, 10, 0)          # :10 = fora das duas janelas


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True,
                          text=True).stdout


def _rollout(home: Path, pct: float, renova: float, nome="rollout-x.jsonl") -> Path:
    pasta = home / "sessions" / "2026" / "10" / "01"
    pasta.mkdir(parents=True, exist_ok=True)
    ev = {"timestamp": "2026-10-01T19:24:30.460Z", "type": "event_msg",
          "payload": {"type": "token_count", "info": {},
                      "rate_limits": {"limit_id": "codex", "plan_type": "plus",
                                      "primary": {"used_percent": pct, "window_minutes": 300,
                                                  "resets_at": renova},
                                      "secondary": {"used_percent": 6.0,
                                                    "window_minutes": 10080,
                                                    "resets_at": renova + 9999}}}}
    alvo = pasta / nome
    alvo.write_text('{"type":"session_meta","payload":{}}\n' + json.dumps(ev) + "\n",
                    encoding="utf-8")
    return alvo


@pytest.fixture(autouse=True)
def mundo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "remoto").mkdir()
    (repo / "remoto" / "existente.py").write_bytes(b"A = 0\r\n")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    home = tmp_path / "codexhome"
    _rollout(home, 10.0, time.time() + 3600)
    monkeypatch.setattr(delegar, "PASTA", tmp_path / "delegados")
    monkeypatch.setattr(delegar, "REPO", repo)
    monkeypatch.setattr(delegar, "WT_RAIZ", tmp_path / "wt")
    monkeypatch.setattr(delegar, "TEMP_TESTES", tmp_path / "temp")
    monkeypatch.setattr(delegar, "CODEX", [sys.executable, str(DUBLE)])
    monkeypatch.setattr(delegar, "CODEX_HOME", home)
    monkeypatch.setattr(delegar, "_agora", lambda: AGORA)
    monkeypatch.setattr(delegar, "GUARDA_S", 0.1)
    monkeypatch.setattr(delegar, "modelo_configurado", lambda: None)
    monkeypatch.setenv("NF_DUBLE_SAIDA", str(tmp_path / "duble"))
    monkeypatch.setenv("NF_DUBLE_MODO", "ok")
    monkeypatch.setenv("NF_SEGREDO_TOKEN", "nao-pode-chegar-no-codex")
    tarefa = tmp_path / "tarefa.md"
    tarefa.write_text("# Conserte o X\n\nFaça Y.\n", encoding="utf-8")

    class M:
        pass
    m = M()
    m.tmp, m.repo, m.home, m.tarefa = tmp_path, repo, home, tarefa
    m.duble = tmp_path / "duble"
    return m


def _chamadas(mundo):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(mundo.duble.glob("chamada_*.json"))]


def _eventos(tarefa_id):
    caminho = delegar.pasta_da(tarefa_id) / "eventos.jsonl"
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines()]


def _criar(mundo, tid="t01", permitidos=("remoto/**",), **kw):
    return delegar.criar(tid, mundo.tarefa, list(permitidos), **kw)


def test_claude_monta_stream_cargo_e_worktree_presa(mundo, monkeypatch):
    _criar(mundo, ia="claude", cargo="conferente")
    visto = {}

    class Rodada:
        def __init__(self, estado, config, args, prompt):
            self.n, self.motivo_parada, self.args = 0, "", args
            visto["args"] = args

        def rodar(self):
            return 0

    monkeypatch.setattr(delegar, "comando_claude", lambda: ["claude-falso"])
    monkeypatch.setattr(delegar, "_Rodada", Rodada)
    delegar._rodada("t01", "rodar", "tarefa", forcar=True)
    args = visto["args"]
    assert args[:2] == ["claude-falso", "-p"]
    assert "--append-system-prompt" in args and "--output-format" in args
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert args[args.index("--permission-mode") + 1] == "dontAsk"
    assert args[args.index("--add-dir") + 1] == str(delegar.worktree_de("t01"))


# ---------------------------------------------- varredura 05/10/2026 (item 7)
def test_log_nao_cai_com_stdout_cp1252(mundo, monkeypatch):
    # O despachante no fundo escreve num arquivo em cp1252; a seta do prompt
    # do cargo historias derrubava a rodada antes de o Claude abrir.
    import io
    delegar.pasta_da("t01").mkdir(parents=True)
    bruto = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(bruto, encoding="cp1252"))
    delegar._log("t01", "roteiro → LLM → imagens")
    sys.stdout.flush()
    assert b"roteiro ? LLM" in bruto.getvalue()
    texto = (delegar.pasta_da("t01") / "log.txt").read_text(encoding="utf-8")
    assert "roteiro → LLM → imagens" in texto


def test_no_fundo_abre_o_despachante_em_utf8(mundo, monkeypatch):
    # O _imprimir do fim da rodada tambem caia com a seta no titulo/motivo, e
    # o app lia o fundo.txt em utf-8 com o acento estragado.
    delegar.pasta_da("t01").mkdir(parents=True)
    visto = {}

    class Proc:
        pid = 4321

    def popen(args, **kw):
        visto.update(kw)
        return Proc()

    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.setattr(delegar.subprocess, "Popen", popen)
    assert delegar.no_fundo(["rodar", "--id", "t01"], "t01") == 4321
    assert visto["env"]["PYTHONIOENCODING"] == "utf-8"
    assert visto["env"]["PATH"] == os.environ["PATH"]


def test_criar_a_partir_de_worktree_grava_o_repo_principal(mundo, monkeypatch):
    # 04/10: o conf-log-cp1252 nasceu de dentro da worktree do pedido-66e4ba54,
    # gravou a worktree como "repo" e o vigia esperou para sempre.
    outra = mundo.tmp / "outra-wt"
    _git(mundo.repo, "worktree", "add", "-q", str(outra), "-b", "lado")
    e = _criar(mundo, repo_tarefa=outra)
    assert Path(e["repo"]).resolve() == mundo.repo.resolve()
    # e o padrao (RAIZ do __file__) rodando de dentro da worktree tambem
    monkeypatch.setattr(delegar, "REPO", None)
    monkeypatch.setattr(delegar, "RAIZ", outra)
    monkeypatch.setattr(delegar, "_PRINCIPAL", {})
    assert delegar.repo().resolve() == mundo.repo.resolve()


def test_estado_antigo_com_worktree_como_repo_limpa_no_principal(mundo):
    # 05/10: conf-log-cp1252 e conf-som-real-15 tinham `repo` = a worktree do
    # pedido-66e4ba54; limpa ela, o `limpar` deles caia com WinError 267.
    outra = mundo.tmp / "outra-wt"
    _git(mundo.repo, "worktree", "add", "-q", str(outra), "-b", "lado")
    e = _criar(mundo)
    assert delegar.repo_da({"repo": str(outra)}).resolve() == mundo.repo.resolve()
    delegar._mudar_estado("t01", repo=str(mundo.tmp / "worktree-que-sumiu"))
    assert delegar.repo_da(delegar.ler_estado("t01")) == delegar.repo()
    r = delegar.limpar("t01")
    assert r["sobrou"] is None and not Path(e["worktree"]).exists()
    assert "delegar/codex-t01" not in _git(mundo.repo, "branch")


def test_log_da_rodada_nao_registra_o_prompt_inteiro():
    args = ["claude", "-p", "regra\n\n" + "x" * 50_000, "--model", "m"]
    linha = delegar._args_para_log(args)
    assert len(linha) < 600 and "+" in linha and "caracteres" in linha
    assert "--model m" in linha


def test_mensagens_dizem_a_ia_de_verdade(mundo, monkeypatch):
    _criar(mundo, ia="claude", cargo="conferente")

    class Rodada:
        def __init__(self, estado, config, args, prompt):
            self.n, self.motivo_parada, self.estado = 0, "", estado

        def rodar(self):
            return 1

    monkeypatch.setattr(delegar, "comando_claude", lambda: ["claude-falso"])
    monkeypatch.setattr(delegar, "_Rodada", Rodada)
    estado = delegar._rodada("t01", "rodar", "tarefa", forcar=True)
    assert estado["motivo"] == "o Claude saiu com o código 1"
    log = (delegar.pasta_da("t01") / "log.txt").read_text(encoding="utf-8")
    assert "o Claude falhou" in log and "Codex falhou" not in log


# --------------------------------------- varredura 05/10/2026 (item 12/21c)
def test_conferente_no_codex_roda_so_leitura(mundo, monkeypatch):
    _criar(mundo, ia="codex", cargo="conferente")
    vistos = []

    class Rodada:
        def __init__(self, estado, config, args, prompt):
            self.n, self.motivo_parada, self.estado = 0, "", estado
            vistos.append(args)

        def rodar(self):
            return 0

    monkeypatch.setattr(delegar, "_Rodada", Rodada)
    delegar._rodada("t01", "rodar", "tarefa", forcar=True)
    assert vistos[0][vistos[0].index("--sandbox") + 1] == "read-only"
    delegar._mudar_estado("t01", thread_id="th1")
    delegar._rodada("t01", "corrigir", "de novo", forcar=True)
    assert 'sandbox_mode="read-only"' in vistos[1]
    assert "workspace-write" not in " ".join(vistos[0] + vistos[1])


def test_rascunhos_de_agente_na_raiz_nao_entram_no_diff(mundo):
    e = _criar(mundo)
    delegar.rodar("t01")
    wt = Path(e["worktree"])
    for nome in ("resposta.md", ".conf_som_real.md", ".tarefa_imagens_heranca.md"):
        (wt / nome).write_text("rascunho\n", encoding="utf-8")
    caminhos = [a["caminho"] for a in delegar.coletar("t01")["arquivos"]]
    assert not {"resposta.md", ".conf_som_real.md", ".tarefa_imagens_heranca.md"} & set(caminhos)
    assert "remoto/novo.py" in caminhos


def test_rascunho_que_ja_estava_no_indice_sai_do_diff(mundo):
    # 05/10: o pedido-cb44cd52-1 nasceu quando resposta.md ainda era rastreado;
    # o resposta.md ficou no indice da worktree, o `exclude` do add nao o
    # tirou, o diff levou so ele e o commit do vigia caiu no .gitignore.
    (mundo.repo / "resposta.md").write_text("antiga\n", encoding="utf-8")
    _git(mundo.repo, "add", "resposta.md")
    _git(mundo.repo, "commit", "-qm", "resposta rastreada")
    e = _criar(mundo)
    delegar.rodar("t01")
    wt = Path(e["worktree"])
    (wt / "resposta.md").write_text("nova\n", encoding="utf-8")
    (wt / "remoto" / "_tmp_x").mkdir()
    (wt / "remoto" / "_tmp_x" / "lixo.txt").write_text("x\n", encoding="utf-8")
    _git(wt, "add", "-A")
    caminhos = [a["caminho"] for a in delegar.coletar("t01")["arquivos"]]
    assert "resposta.md" not in caminhos
    assert "remoto/_tmp_x/lixo.txt" not in caminhos
    assert "remoto/novo.py" in caminhos


def test_ruido_tem_a_ancora_do_git():
    assert delegar._e_ruido("resposta.md") and delegar._e_ruido(".codex_tarefa.md")
    assert delegar._e_ruido("remoto/__pycache__/x.pyc") and delegar._e_ruido("_tmp_tela/a.png")
    # padrao sem `**/` e so da raiz; `**/_tmp*` nao pega pasta que so contem "_tmp"
    assert not delegar._e_ruido("docs/resposta.md")
    assert not delegar._e_ruido("remoto/meu_tmp_x/a.py")


def test_gravar_json_tenta_de_novo_quando_o_windows_segura_o_arquivo(mundo, monkeypatch):
    real = os.replace
    falhas = []

    def replace(a, b):
        if len(falhas) < 2:
            falhas.append(1)
            raise PermissionError(5, "Acesso negado")
        return real(a, b)

    monkeypatch.setattr(delegar.os, "replace", replace)
    monkeypatch.setattr(delegar, "ESPERA_REPLACE_S", 0)
    alvo = mundo.tmp / "x" / "estado.json"
    delegar._gravar_json(alvo, {"a": 1})
    assert json.loads(alvo.read_text(encoding="utf-8")) == {"a": 1} and len(falhas) == 2
    # preso de vez: levanta, sem deixar o .tmp para tras
    monkeypatch.setattr(delegar.os, "replace",
                        lambda a, b: (_ for _ in ()).throw(PermissionError(5, "x")))
    with pytest.raises(PermissionError):
        delegar._gravar_json(alvo, {"a": 2})
    assert not list(alvo.parent.glob(".*.tmp"))


def test_testar_usa_uma_pasta_por_rodada_fora_da_worktree(mundo):
    e = _criar(mundo)
    delegar.rodar("t01")
    cmd = f'"{sys.executable}" -c "import os; print(os.environ[\'TEMP\'])"'
    um = delegar.testar("t01", cmd)["resumo"]
    dois = delegar.testar("t01", cmd)["resumo"]
    assert um != dois
    for t in (um, dois):
        assert Path(t).is_relative_to(mundo.tmp / "temp" / "delegados" / "t01")
        assert not Path(t).is_relative_to(Path(e["worktree"]))
    # so a ultima rodada fica no disco (as velhas sao apagadas)
    assert not Path(um).exists() and Path(dois).exists()


def test_testar_com_a_trava_ocupada_e_recusa_passageira(mundo, monkeypatch):
    """Conferente 05/10: a 2a rodada dava Recusa comum em 15 s e o vigia
    mandava a entrega para `olho` com integrador contratado."""
    from remoto import api_http
    _criar(mundo)
    delegar.rodar("t01")

    def ocupada(caminho, *a, **kw):
        raise OSError(f"trava ocupada ha mais de 15 s: {Path(caminho).name}")
    monkeypatch.setattr(api_http, "trava_arquivo", ocupada)
    with pytest.raises(delegar.Ocupado) as erro:
        delegar.testar("t01", f'"{sys.executable}" -c "print(1)"')
    assert isinstance(erro.value, delegar.Recusa) and erro.value.passageira
    assert "testar.lock" in str(erro.value) and "em andamento" in str(erro.value)


def test_reconciliar_fantasma_fecha_pid_morto_depois_do_prazo(monkeypatch):
    agora = datetime(2026, 10, 8, 10, 0)
    mudancas = []
    monkeypatch.setattr(delegar, "_agora", lambda: agora)
    monkeypatch.setattr(delegar, "listar", lambda: [{"id": "fantasma", "situacao": "rodando",
                                                       "pid": 12, "inicio": "2026-10-08T09:49:00"}])
    monkeypatch.setattr(delegar, "_pid_vivo", lambda _pid: False)
    monkeypatch.setattr(delegar, "_mudar_estado", lambda ident, **kw: mudancas.append((ident, kw)))
    assert delegar.reconciliar_fantasmas() == ["fantasma"]
    assert mudancas[0][1]["situacao"] == "parado"
    assert mudancas[0][1]["motivo"] == "processo morreu"


def test_testar_pytest_acrescenta_faulthandler(mundo):
    _criar(mundo)
    delegar.rodar("t01")
    resultado = delegar.testar("t01", f'"{sys.executable}" -m pytest --version')
    assert "-o faulthandler_timeout=180" in resultado["cmd"]


def test_ia_ainda_rodando_e_ocupado_com_o_nome_certo(mundo):
    _criar(mundo)
    delegar.rodar("t01")
    delegar._mudar_estado("t01", situacao="rodando", pid=os.getpid(), ia="claude")
    for chamada in (lambda: delegar.testar("t01", "echo 1"),
                    lambda: delegar.aplicar("t01", processos=[]),
                    lambda: delegar.limpar("t01")):
        with pytest.raises(delegar.Ocupado) as erro:
            chamada()
        assert "o Claude ainda está rodando" in str(erro.value), erro.value
    delegar._mudar_estado("t01", situacao="terminou")


def test_validador_diz_qual_ia_nao_mudou_nada():
    config = dict(delegar.PADRAO_CONFIG)
    assert delegar.validar_diff([], ["**"], config, ia="Claude") == ["o Claude não mudou nada"]
    # o vigia casa este trecho para "nada a aplicar"
    assert "não mudou nada" in delegar.validar_diff([], ["**"], config)[0]


def test_commits_a_frente(mundo):
    e = _criar(mundo)
    assert delegar.commits_a_frente(e) == 0
    wt = Path(e["worktree"])
    (wt / "remoto" / "c.py").write_text("C = 1\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")
    assert delegar.commits_a_frente(e) == 1
    assert delegar.commits_a_frente({"base": None}) is None


# ------------------------------------------------------------------ criar
def test_criar_faz_worktree_branch_e_tarefa_com_as_regras(mundo):
    e = _criar(mundo, modelo="gpt-6-luna")
    wt = Path(e["worktree"])
    assert wt == mundo.tmp / "wt" / "codex-t01" and wt.is_dir()
    assert e["situacao"] == "criado" and e["modelo"] == "gpt-6-luna"
    assert "delegar/codex-t01" in _git(mundo.repo, "branch")
    prompt = (wt / ".codex_tarefa.md").read_text(encoding="utf-8")
    assert "Não commite" in prompt and "Conserte o X" in prompt and "`remoto/**`" in prompt
    assert "no:cacheprovider" in prompt
    assert e["titulo"] == "Conserte o X"
    with pytest.raises(delegar.Recusa, match="já existe"):
        _criar(mundo)


def test_criar_sem_esforco_usa_o_medio_decidido_e_nao_o_ultra_do_codex(mundo, monkeypatch):
    # geral/codex-esforco (01/10): medio por padrao, alto nas dificeis; o
    # `ultra` do ~/.codex/config.toml nao vale para o despachante
    monkeypatch.setattr(delegar, "esforco_configurado", lambda: delegar.ESFORCO_PADRAO)
    e = _criar(mundo)
    assert e["esforco"] == "medium"


def test_criar_com_esforco_explicito_vence_o_padrao(mundo):
    e = _criar(mundo, esforco="high")
    assert e["esforco"] == "high"


def test_criar_recusa_sem_lista_id_torto_e_caminho_que_sobe(mundo):
    with pytest.raises(delegar.Recusa, match="caminhos"):
        _criar(mundo, permitidos=())
    with pytest.raises(delegar.Recusa, match="id"):
        _criar(mundo, tid="X Y")
    with pytest.raises(delegar.Recusa, match="inválido"):
        _criar(mundo, permitidos=("../fora/**",))
    with pytest.raises(delegar.Recusa, match="modelo"):
        _criar(mundo, modelo="gpt 6; rm")
    assert not (mundo.tmp / "wt").exists() or not list((mundo.tmp / "wt").iterdir())


def test_criar_guarda_o_repo_explicito_e_o_padrao_do_cargo(mundo, monkeypatch):
    outro = mundo.tmp / "zombie"
    outro.mkdir()
    _git(outro, "init", "-q")
    _git(outro, "config", "user.email", "t@t")
    _git(outro, "config", "user.name", "t")
    (outro / "src").mkdir()
    (outro / "src" / "jogo.ts").write_text("export {}\n", encoding="utf-8")
    _git(outro, "add", "-A")
    _git(outro, "commit", "-qm", "base")
    e = delegar.criar("repo-explicito", mundo.tarefa, ["src/**"], repo_tarefa=outro)
    assert Path(e["repo"]) == outro and Path(e["worktree"]).parent == mundo.tmp / "wt"
    monkeypatch.setattr(delegar, "dados_do_cargo", lambda cargo: {
        "repo": str(outro), "testes": "npx vitest run"} if cargo == "jogo-zombie" else {})
    e = delegar.criar("zombie-padrao", mundo.tarefa, ["src/**"], cargo="jogo-zombie")
    assert Path(e["repo"]) == outro and e["testes_cmd"] == "npx vitest run"


# ------------------------------------------------------------------ rodar
def test_rodar_grava_eventos_ao_vivo_tokens_resposta_e_diff(mundo):
    _criar(mundo, modelo="gpt-6-luna")
    e = delegar.rodar("t01")
    assert e["situacao"] == "terminou", e
    assert e["thread_id"] == "01a0f92a-17e1-7a60-bc18-093e93057408"
    assert e["tokens"] == {"entrada": 1000, "cache": 800, "saida": 50, "raciocinio": 10}
    assert e["rodadas"][0]["codigo"] == 0 and e["pid"] is None
    evs = _eventos("t01")
    assert [x["n"] for x in evs] == list(range(1, len(evs) + 1))
    tipos = [x["ev"]["type"] for x in evs]
    assert tipos[0] == "delegar.inicio" and tipos[-1] == "delegar.fim"
    assert "thread.started" in tipos and "turn.completed" in tipos
    assert (delegar.pasta_da("t01") / "resposta.md").read_text(encoding="utf-8").startswith(
        "Feito (ok)")
    # o diff sai sozinho no fim, e passa
    assert e["diff"]["ok"] and e["diff"]["arquivos"] == 2
    # a chamada: prompt por STDIN, --json, sandbox, -C, -o, o modelo, e "-" no fim
    ch = _chamadas(mundo)[0]
    assert ch["argv"][0] == "exec" and ch["argv"][-1] == "-"
    assert "--json" in ch["argv"] and ch["argv"][ch["argv"].index("--sandbox") + 1] \
        == "workspace-write"
    assert ch["argv"][ch["argv"].index("-m") + 1] == "gpt-6-luna"
    assert "Conserte o X" in ch["stdin"] and "Caminhos permitidos" in ch["stdin"]
    # o ambiente: sem segredo, sem cache do pytest
    assert ch["env"]["NF_SEGREDO_TOKEN"] is None
    assert ch["env"]["PYTEST_ADDOPTS"] == "-p no:cacheprovider"
    assert ch["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_corrigir_retoma_a_mesma_conversa_sem_sandbox_flag(mundo):
    _criar(mundo)
    texto = mundo.tmp / "corr.md"
    texto.write_text("Faltou o teste.", encoding="utf-8")
    with pytest.raises(delegar.Recusa, match="rode primeiro"):
        delegar.corrigir("t01", texto)
    delegar.rodar("t01")
    e = delegar.corrigir("t01", texto)
    assert e["situacao"] == "terminou" and len(e["rodadas"]) == 2
    ch = _chamadas(mundo)[-1]
    assert ch["argv"][:3] == ["exec", "resume", "01a0f92a-17e1-7a60-bc18-093e93057408"]
    assert "--sandbox" not in ch["argv"]
    assert 'sandbox_mode="workspace-write"' in ch["argv"] and ch["stdin"] == "Faltou o teste."
    assert e["tokens"]["entrada"] == 2000
    assert (delegar.pasta_da("t01") / "correcao_1.md").exists()


def test_falha_do_codex_fica_falhou_com_o_codigo(mundo, monkeypatch):
    monkeypatch.setenv("NF_DUBLE_MODO", "falha")
    _criar(mundo)
    e = delegar.rodar("t01")
    assert e["situacao"] == "falhou" and "código 2" in e["motivo"]
    resumo = [delegar.resumir(x) for x in _eventos("t01")]
    assert any(r["tipo"] == "erro" and "limite de uso" in r["texto"] for r in resumo)


# ---------------------------------------------------------- permissao
@pytest.mark.parametrize("modo", ["permissao", "escopo"])
def test_pedido_de_permissao_ou_desistencia_por_escopo_para_a_tarefa(mundo, monkeypatch, modo):
    monkeypatch.setenv("NF_DUBLE_MODO", modo)
    _criar(mundo)
    e = delegar.rodar("t01")
    assert e["situacao"] == "aguardando_permissao"
    pedido = e["pedido_permissao"]
    assert pedido["categoria"] in delegar.CATEGORIAS_PERMISSAO
    if modo == "permissao":
        assert pedido["alvo"] == r"E:\jogo_ZOMBIE"
    else:
        assert pedido["categoria"] == "caminho_protegido"


def test_decidir_permissao_retomada_politica_e_conta_negada(mundo, monkeypatch):
    monkeypatch.setenv("NF_DUBLE_MODO", "permissao")
    _criar(mundo)
    delegar.rodar("t01")
    # O alvo do dublê não existe; a permissão de outro tipo retoma a mesma conversa.
    estado = delegar.ler_estado("t01")
    estado["pedido_permissao"].update(categoria="rede", alvo="localhost")
    delegar._gravar_estado(estado)
    e = delegar.decidir_permissao("t01", True, sempre=True)
    assert e["situacao"] == "criado"
    assert delegar.ler_permissoes()["cargos"][""]["rede"] == "gerente_aceita"
    monkeypatch.setenv("NF_DUBLE_MODO", "ok")
    assert delegar.retomar_permissao("t01")["situacao"] == "terminou"
    delegar._mudar_estado("t01", situacao="aguardando_permissao", pedido_permissao={
        "o_que": "entrar numa conta", "categoria": "conta", "por_que": "x", "alvo": "x"})
    assert delegar.decidir_permissao("t01", True)["situacao"] == "negado"


# ------------------------------------------------------------- guardas
def test_claude_proibido_barra_o_trabalhador_claude_sem_parar_o_codex(mundo):
    _criar(mundo, ia="claude", cargo="conferente")
    claude_estado.mudar(False, por="teste")
    with pytest.raises(delegar.Recusa, match="proibido"):
        delegar.rodar("t01")
    assert _chamadas(mundo) == []
    assert delegar.ler_estado("t01")["situacao"] == "criado"


def _rodar_em_thread(tid):
    saida = {}
    fio = threading.Thread(target=lambda: saida.update(e=delegar.rodar(tid)), daemon=True)
    fio.start()
    return fio, saida


def _esperar(condicao, prazo=60.0):
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.05)
    return False


def test_claude_proibido_no_meio_nao_mata_o_codex(mundo, monkeypatch):
    monkeypatch.setenv("NF_DUBLE_MODO", "lento")
    _criar(mundo)
    fio, saida = _rodar_em_thread("t01")
    assert _esperar(lambda: delegar.ler_estado("t01").get("pid_codex"))
    assert _esperar(lambda: len(_chamadas(mundo)) == 1)
    pid = _chamadas(mundo)[0]["pid"]
    claude_estado.mudar(False, por="teste")
    # O interruptor e do Claude: o Codex segue ate o servidor pedir parada.
    assert _esperar(fio.is_alive, prazo=3)
    assert pid and "pedido" in delegar.parar("t01")
    fio.join(20)
    assert not fio.is_alive()
    assert saida["e"]["situacao"] == "parado"


def test_parar_pelo_pedido(mundo, monkeypatch):
    monkeypatch.setenv("NF_DUBLE_MODO", "lento")
    _criar(mundo)
    with pytest.raises(delegar.Recusa, match="não está rodando"):
        delegar.parar("t01")
    fio, saida = _rodar_em_thread("t01")
    assert _esperar(lambda: delegar.ler_estado("t01").get("pid_codex"))
    assert "pedido" in delegar.parar("t01")
    assert _esperar(lambda: not fio.is_alive(), prazo=60)
    assert saida["e"]["situacao"] == "parado" and "pedido" in saida["e"]["motivo"]


def test_teto_do_codex(mundo):
    _criar(mundo)
    for p in (mundo.home / "sessions").rglob("*.jsonl"):
        p.unlink()
    _rollout(mundo.home, 50.0, time.time() + 3600)
    with pytest.raises(delegar.Recusa, match="50% da janela"):
        delegar.rodar("t01")
    assert _chamadas(mundo) == []
    # a janela renovou depois da medicao: 0%, pode
    _rollout(mundo.home, 90.0, time.time() - 60)
    u = delegar.uso_codex()
    assert u["situacao"] == "renovou" and u["pct"] == 0.0
    # o --forcar passa por cima (so se o Adrian mandou)
    _rollout(mundo.home, 99.0, time.time() + 3600)
    assert delegar.rodar("t01", forcar=True)["situacao"] == "terminou"


def test_sessoes_caidas_nao_escondem_a_medicao(mundo):
    """09/10: 6 sessoes sem rede, sem `rate_limits`, travaram o despachante."""
    for p in (mundo.home / "sessions").rglob("*.jsonl"):
        p.unlink()
    medida = _rollout(mundo.home, 20.0, time.time() + 3600, nome="rollout-medida.jsonl")
    os.utime(medida, (time.time() - 3600, time.time() - 3600))
    for n in range(8):
        caida = medida.with_name(f"rollout-caida-{n}.jsonl")
        caida.write_text('{"type":"session_meta","payload":{}}\n', encoding="utf-8")
    u = delegar.uso_codex()
    assert u["situacao"] == "medido" and u["pct"] == 20.0
    assert u["fonte"] == "rollout-medida.jsonl"


def test_sem_medicao_recusa_a_nao_ser_pela_contagem(mundo):
    _criar(mundo)
    for p in (mundo.home / "sessions").rglob("*.jsonl"):
        p.unlink()
    assert delegar.uso_codex()["situacao"] == "desconhecido"
    with pytest.raises(delegar.Recusa, match="não consegui ler o uso"):
        delegar.rodar("t01")
    (delegar.pasta() / "config.json").write_text(json.dumps({"tokens_janela_max": 5000}),
                                                 encoding="utf-8")
    assert delegar.rodar("t01")["situacao"] == "terminou"
    assert delegar.tokens_na_janela() == 1050
    (delegar.pasta() / "config.json").write_text(json.dumps({"tokens_janela_max": 1000}),
                                                 encoding="utf-8")
    with pytest.raises(delegar.Recusa, match="1050 tokens"):
        delegar.rodar("t01")


def test_horario_sem_comecar_so_se_configurado(mundo, monkeypatch):
    """03/10/2026: sem janela de relogio por padrao ("NAO FICA ESPERANDO HORARIO")."""
    _criar(mundo)
    monkeypatch.setattr(delegar, "_agora", lambda: datetime(2026, 10, 1, 18, 35))
    assert delegar.PADRAO_CONFIG["janela_sem_comecar"] is None
    monkeypatch.setitem(delegar.PADRAO_CONFIG, "janela_sem_comecar", [30, 45])
    with pytest.raises(delegar.Recusa, match=":30 e :45"):
        delegar.rodar("t01")


def test_um_delegado_por_vez(mundo):
    _criar(mundo, tid="t01")
    _criar(mundo, tid="t02")
    delegar._mudar_estado("t01", situacao="rodando", pid=os.getpid())
    with pytest.raises(delegar.Recusa, match=r"no máximo 1 delegado\(s\) ao mesmo tempo: t01"):
        delegar.rodar("t02")
    with pytest.raises(delegar.Recusa, match="já está rodando"):
        delegar.rodar("t01")
    # o pid que sumiu nao segura ninguem (e a tela diz "sumiu")
    delegar._mudar_estado("t01", pid=999999)
    assert delegar.rodar("t02")["situacao"] == "terminou"
    assert next(d for d in delegar.para_o_app()["delegados"]
                if d["id"] == "t01")["situacao"] == "sumiu"


# ------------------------------------------------------------------ diff
def test_validador_so_recusa_entrega_vazia(mundo, monkeypatch):
    monkeypatch.setenv("NF_DUBLE_MODO", "nada")
    _criar(mundo)
    e = delegar.rodar("t01")
    assert e["diff"]["ok"] is False
    assert any("não mudou nada" in m for m in e["diff"]["motivos"]), e["diff"]


@pytest.mark.parametrize("modo,aviso", [("fora", "fora da lista (entrou): outro/fora.py"),
                                        ("binario", "binário (entrou): remoto/foto.png")])
def test_fora_da_lista_e_binario_entram_com_aviso(mundo, monkeypatch, modo, aviso):
    """02/10/2026, o Adrian: recusar por 'fora da lista' jogava trabalho fora."""
    monkeypatch.setenv("NF_DUBLE_MODO", modo)
    _criar(mundo)
    e = delegar.rodar("t01")
    assert e["diff"]["ok"] is True, e["diff"]
    assert aviso in e["diff"]["avisos"], e["diff"]


def test_validador_nao_recusa_por_tamanho_nem_lista():
    config = dict(delegar.PADRAO_CONFIG, diff_max_linhas=10, diff_max_arquivos=1)
    arquivos = [{"caminho": "remoto/a.py", "mais": 1, "menos": 0, "binario": False},
                {"caminho": "ias/b.py", "mais": 20, "menos": 0, "binario": False}]
    assert delegar.validar_diff(arquivos, ["historias/**"], config) == []
    avisos = delegar.avisos_do_diff(arquivos, ["historias/**"], config)
    assert "fora da lista (entrou): remoto/a.py" in avisos
    assert any("diff grande: 21" in a for a in avisos)
    assert any("muitos arquivos: 2" in a for a in avisos)
    assert delegar.validar_diff([], ["**"], config) == ["o Codex não mudou nada"]


def test_arquivo_do_adrian_sai_do_diff_e_o_resto_entra(mundo):
    e = _criar(mundo)
    delegar.rodar("t01")
    wt = Path(e["worktree"])
    (wt / "palco" / "biblioteca").mkdir(parents=True, exist_ok=True)
    (wt / "palco" / "biblioteca" / "LICENCAS.md").write_text("mexido pelo Codex", encoding="utf-8")
    resumo = delegar.coletar("t01")
    caminhos = [a["caminho"] for a in resumo["arquivos"]]
    assert "palco/biblioteca/LICENCAS.md" not in caminhos
    assert resumo["ok"] and any("LICENCAS.md" in d for d in resumo["deixados"])
    assert "remoto/novo.py" in caminhos


def test_diff_ignora_sobras_de_teste_e_fim_de_linha(mundo):
    # 01/10: toda entrega saia "RECUSADO" por travas do pytest em .teste_tmp e
    # pelo editing.json que a worktree mostra mudado so no fim de linha.
    e = _criar(mundo)
    delegar.rodar("t01")
    wt = Path(e["worktree"])
    (wt / ".teste_tmp" / "locks").mkdir(parents=True)
    (wt / ".teste_tmp" / "locks" / "x.lock").write_bytes(b"\x00\x01")
    (wt / "README.md").write_bytes(b"x\r\n")                 # so o fim de linha
    # 02/10: as capturas do teste de tela e o basetemp sem barra
    (wt / "_tmp_tela" / "tela_app").mkdir(parents=True)
    (wt / "_tmp_tela" / "tela_app" / "a.png").write_bytes(b"\x89PNG")
    (wt / "tmp_pytestdelegadost01bt").mkdir()
    (wt / "tmp_pytestdelegadost01bt" / "x.json").write_text("{}")
    resumo = delegar.coletar("t01")
    caminhos = [a["caminho"] for a in resumo["arquivos"]]
    assert "README.md" not in caminhos
    assert not any(".teste_tmp" in c or "_tmp_tela" in c or "tmp_pytest" in c for c in caminhos)
    assert "remoto/novo.py" in caminhos and resumo["ok"], resumo["motivos"]


# ------------------------------------------------------- testar e aplicar
def test_testar_aplicar_e_limpar(mundo, monkeypatch):
    _criar(mundo)
    delegar.rodar("t01")
    with pytest.raises(delegar.Recusa, match="rode os testes"):
        delegar.aplicar("t01", processos=[])
    # o basetemp vai com barra normal: com barra invertida o shlex do pytest a comia
    # e a pasta caia dentro da worktree (02/10/2026)
    cmd = f'"{sys.executable}" -c "import os,shlex; print(shlex.split(os.environ[\'PYTEST_ADDOPTS\'])[-1])"'
    r = delegar.testar("t01", cmd)
    prefixo = "--basetemp=" + (mundo.tmp / "temp" / "delegados" / "t01").as_posix() + "/r"
    assert r["resumo"].startswith(prefixo) and r["resumo"].endswith("/bt")
    cmd = f'"{sys.executable}" -c "import os,sys; print(os.environ[\'TEMP\']); sys.exit(1)"'
    r = delegar.testar("t01", cmd)
    assert r["ok"] is False and r["codigo"] == 1
    assert str(mundo.tmp / "temp") in r["resumo"]               # TEMP no lugar certo
    with pytest.raises(delegar.Recusa, match="falharam"):
        delegar.aplicar("t01", processos=[])
    r = delegar.testar("t01", f'"{sys.executable}" -c "print(\'2 passed\')"')
    assert r["ok"] and r["resumo"] == "2 passed"
    # a publicacao EM VOO barra; o relogio nao (03/10/2026)
    with pytest.raises(delegar.Recusa, match="publicação em voo"):
        delegar.aplicar("t01", processos=["python -m remoto.publicacao_filha x"])
    with pytest.raises(delegar.Recusa, match="publicação em voo"):
        delegar.aplicar("t01", processos=["python main.py publicar --id 3"])
    feito = delegar.aplicar("t01", processos=["python -m remoto.api_http --porta 8931"])
    assert sorted(feito["arquivos"]) == ["remoto/existente.py", "remoto/novo.py"]
    assert (mundo.repo / "remoto" / "existente.py").read_bytes() == b"A = 0\r\nY = 2\r\n"
    assert (mundo.repo / "remoto" / "novo.py").exists()
    with pytest.raises(delegar.Recusa, match="já aplicado"):
        delegar.aplicar("t01", processos=[])
    # limpar: worktree e branch saem; o estado fica (a Oficina mostra)
    r = delegar.limpar("t01")
    assert r["sobrou"] is None and not (mundo.tmp / "wt" / "codex-t01").exists()
    assert "delegar/codex-t01" not in _git(mundo.repo, "branch")
    assert delegar.ler_estado("t01")["limpo"]


def test_diff_que_mudou_depois_dos_testes_recusa(mundo):
    _criar(mundo)
    delegar.rodar("t01")
    delegar.testar("t01", f'"{sys.executable}" -c "pass"')
    wt = Path(delegar.ler_estado("t01")["worktree"])
    (wt / "remoto" / "novo.py").write_text("X = 99\n", encoding="utf-8")
    with pytest.raises(delegar.Recusa, match="mudou depois dos testes"):
        delegar.aplicar("t01", processos=[])


def test_apply_check_recusa_quando_a_arvore_principal_divergiu(mundo):
    _criar(mundo)
    delegar.rodar("t01")
    delegar.testar("t01", f'"{sys.executable}" -c "pass"')
    (mundo.repo / "remoto" / "existente.py").write_bytes(b"OUTRA COISA\r\n")
    with pytest.raises(delegar.Recusa, match="apply --check"):
        delegar.aplicar("t01", processos=[])
    assert not (mundo.repo / "remoto" / "novo.py").exists()      # nada pela metade


def test_limpar_o_que_o_sandbox_tranca_vai_para_o_lixo(mundo, monkeypatch):
    _criar(mundo)
    delegar.rodar("t01")
    wt = mundo.tmp / "wt" / "codex-t01"
    (wt / ".pytest_cache").mkdir()
    def trancado(alvo):
        """Como o sandbox deixa: tudo sai, menos o .pytest_cache (ACL do dono)."""
        for p in sorted(Path(alvo).rglob("*"), reverse=True):
            if ".pytest_cache" not in p.parts:
                (p.unlink if p.is_file() else p.rmdir)()
        return [str(Path(alvo) / ".pytest_cache")]
    monkeypatch.setattr(delegar, "_apagar_o_que_der", trancado)
    monkeypatch.setattr(delegar, "_git", _git_que_falha_no_remove(delegar._git))
    r = delegar.limpar("t01")
    assert r["sobrou"] and "_lixo_codex" in r["sobrou"] and "takeown" in r["como_apagar"]
    assert not wt.exists()
    assert "delegar/codex-t01" not in _git(mundo.repo, "branch")


def _git_que_falha_no_remove(real):
    def git(*args, **kw):
        if args[:2] == ("worktree", "remove"):
            return subprocess.CompletedProcess(args, 1, "", "Directory not empty")
        return real(*args, **kw)
    return git


def test_limpar_orfas_so_as_que_o_git_nao_conhece(mundo):
    _criar(mundo)
    orfa = mundo.tmp / "wt" / "codex-velha"
    (orfa / "x").mkdir(parents=True)
    feitos = delegar.limpar_orfas()
    assert [Path(f["pasta"]).name for f in feitos] == ["codex-velha"]
    assert not orfa.exists() and (mundo.tmp / "wt" / "codex-t01").is_dir()


# --------------------------------------------------------- leitura da tela
def test_ler_eventos_por_offset_so_linhas_inteiras(mundo):
    _criar(mundo)
    delegar.rodar("t01")
    tudo = delegar.ler_eventos("t01", 0)
    assert tudo["eventos"] and tudo["offset"] == tudo["tamanho"] and not tudo["mais"]
    assert delegar.ler_eventos("t01", tudo["offset"])["eventos"] == []
    caminho = delegar.pasta_da("t01") / "eventos.jsonl"
    with open(caminho, "a", encoding="utf-8") as fh:
        fh.write('{"n": 99, "em": "x", "ev": {"type": "turn.sta')     # meia linha
    meio = delegar.ler_eventos("t01", tudo["offset"])
    assert meio["eventos"] == [] and meio["offset"] == tudo["offset"]
    with open(caminho, "a", encoding="utf-8") as fh:
        fh.write('rted"}}\nlixo\n')
    fim = delegar.ler_eventos("t01", tudo["offset"])
    assert [e["texto"] for e in fim["eventos"]] == ["pensando…", "linha ilegível no eventos.jsonl"]
    # a cauda (primeira carga) comeca numa linha inteira
    cauda = delegar.ler_eventos("t01", -1, maximo_bytes=300)
    assert cauda["eventos"] and all(e["texto"] for e in cauda["eventos"])
    pedaco = delegar.ler_eventos("t01", 0, maximo_bytes=300)
    assert pedaco["mais"] and pedaco["offset"] <= 300


def test_resumir_o_que_ele_le_roda_testa_e_muda():
    def r(item, tipo="item.completed"):
        return delegar.resumir({"n": 1, "em": "2026-10-01T18:00:00",
                                "ev": {"type": tipo, "item": item}})
    ps = ('"C:\\\\WINDOWS\\\\System32\\\\WindowsPowerShell\\\\v1.0\\\\powershell.exe" '
          "-NoProfile -Command 'Get-Content ''a b.py'''")
    x = r({"type": "command_execution", "command": ps, "exit_code": 0,
           "aggregated_output": "ok"})
    assert x["tipo"] == "le" and x["texto"] == "Get-Content 'a b.py'" and x["ok"]
    x = r({"type": "command_execution", "command": "python -m pytest remoto -q",
           "exit_code": 1, "aggregated_output": "1 failed"})
    assert x["tipo"] == "testa" and x["ok"] is False and "código 1" in x["texto"]
    assert r({"type": "command_execution", "command": "git diff"})["tipo"] == "le"
    assert r({"type": "command_execution", "command": "python x.py"})["tipo"] == "roda"
    x = r({"type": "file_change", "changes": [{"path": "a.py", "kind": "update"}],
           "status": "completed"})
    assert x["tipo"] == "muda" and x["texto"] == "update a.py"
    x = r({"type": "todo_list", "items": [{"text": "ler", "completed": True},
                                          {"text": "testar", "completed": False}]},
          "item.updated")
    assert x["tipo"] == "plano" and x["texto"] == "☑ ler\n☐ testar"
    assert r({"type": "agent_message", "text": "pronto"})["texto"] == "pronto"
    assert r({"type": "reasoning", "text": "hm"})["tipo"] == "pensa"
    # formato que ainda nao existe nao derruba a tela
    assert delegar.resumir({"ev": {"type": "coisa.nova"}})["texto"] == "coisa.nova"
    assert delegar.resumir({"ev": "lixo"})["tipo"] == "outro"


def test_uso_le_o_rollout_em_hora_local(mundo):
    u = delegar.uso_codex()
    assert u["situacao"] == "medido" and u["pct"] == 10.0 and u["plano"] == "plus"
    esperado = datetime.fromisoformat("2026-10-01T19:24:30+00:00").astimezone().replace(
        tzinfo=None).isoformat(timespec="seconds")
    assert u["medido_em"] == esperado


def test_modelos_do_cache_e_a_lista_de_reserva(mundo):
    m = delegar.modelos_codex()
    assert m["modelos"][0]["id"] == "gpt-6-astra" and "medida" in m["fonte"]
    (mundo.home / "models_cache.json").write_text(json.dumps({
        "fetched_at": "2026-10-01T20:25:40Z",
        "models": [{"slug": "gpt-x", "display_name": "GPT-X", "visibility": "list",
                    "description": "d", "supported_reasoning_levels": [{"effort": "low"}]},
                   {"slug": "escondido", "visibility": "hide"}]}), encoding="utf-8")
    (mundo.home / "config.toml").write_text('model = "gpt-x"\nmodel_reasoning_effort = "low"\n',
                                            encoding="utf-8")
    m = delegar.modelos_codex()
    assert [x["id"] for x in m["modelos"]] == ["gpt-x"] and m["fonte"].endswith("(2026-10-01)")
    assert m["padrao"] == {"modelo": "gpt-x", "esforco": "low"}
    assert delegar.validar_modelo("") is None and delegar.validar_modelo("GPT-6-Sol") == "gpt-6-sol"


def test_detalhe_para_o_app_pesado_so_na_primeira_carga(mundo):
    _criar(mundo)
    delegar.rodar("t01")
    d = delegar.detalhe_para_o_app("t01", -1)
    assert d["tarefa"]["situacao"] == "terminou" and "remoto/novo.py" in d["diff_texto"]
    assert d["pedido"].startswith("# Conserte") and d["resposta"].startswith("Feito")
    assert "worktree" not in d["tarefa"]                         # sem caminho de disco
    leve = delegar.detalhe_para_o_app("t01", d["offset"])
    assert "diff_texto" not in leve and leve["eventos"] == []
    assert delegar.detalhe_para_o_app("t01", d["offset"], completo=True)["diff_texto"]
    assert delegar.detalhe_para_o_app("naoexiste", -1) is None


def test_caso_zero(mundo):
    d = delegar.para_o_app()
    assert d["delegados"] == [] and d["rodando"] == 0 and d["uso"]["pct"] == 10.0
    assert delegar.listar() == []


def test_fundo_reabre_o_mesmo_comando_desligado(mundo, monkeypatch):
    _criar(mundo)
    pedidos = []

    class Falso:
        pid = 4242

    def popen(args, **kw):
        pedidos.append((args, kw))
        return Falso()
    monkeypatch.setattr(delegar.subprocess, "Popen", popen)
    assert delegar.main(["rodar", "--id", "t01", "--fundo"]) == 0
    args, kw = pedidos[0]
    assert args[1:] == ["-m", "remoto.delegar", "rodar", "--id", "t01"]
    assert kw["creationflags"] & getattr(subprocess, "DETACHED_PROCESS", 0) == getattr(
        subprocess, "DETACHED_PROCESS", 0)


def test_nenhum_teste_resolve_o_codex_de_verdade():
    assert delegar.comando_codex() == [sys.executable, str(DUBLE)]


def test_cli_recusa_com_codigo_3(mundo, capsys):
    assert delegar.main(["rodar", "--id", "naoexiste"]) == 3
    assert "recusado" in capsys.readouterr().err


def test_aplicar_resolve_sozinho_o_conflito_da_casca(mundo):
    """03/10/2026: as permissoes pararam no `--check` por causa da versao da casca."""
    sw = mundo.repo / "remoto" / "sw.js"
    sw.write_text('const CASCA = "painel-casca-v10";\nconst X = 1;\n', encoding="utf-8")
    _git(mundo.repo, "add", "-A")
    _git(mundo.repo, "commit", "-qm", "casca v10")
    e = _criar(mundo)
    delegar.rodar("t01")
    wt = Path(e["worktree"])
    (wt / "remoto" / "sw.js").write_text('const CASCA = "painel-casca-v11";\nconst X = 1;\nconst NOVO = 2;\n',
                                         encoding="utf-8")
    # enquanto isso, a arvore principal tambem subiu a casca
    sw.write_text('const CASCA = "painel-casca-v12";\nconst X = 1;\n', encoding="utf-8")
    _git(mundo.repo, "commit", "-qam", "casca v12 na principal")
    delegar.testar("t01", f'"{sys.executable}" -c "print(1)"')
    feito = delegar.aplicar("t01", processos=[])
    texto = sw.read_text(encoding="utf-8")
    assert "<<<<<<<" not in texto and "const NOVO = 2;" in texto
    assert "painel-casca-v13" in texto           # a maior (12) + 1
    assert "remoto/sw.js" in feito["arquivos"]


def test_aplicar_com_conflito_de_verdade_devolve_a_arvore_limpa(mundo):
    e = _criar(mundo)
    delegar.rodar("t01")
    wt = Path(e["worktree"])
    (wt / "remoto" / "existente.py").write_bytes(b"A = 1\r\n")
    (mundo.repo / "remoto" / "existente.py").write_bytes(b"A = 2\r\n")
    _git(mundo.repo, "commit", "-qam", "outro lado")
    delegar.testar("t01", f'"{sys.executable}" -c "print(1)"')
    with pytest.raises(delegar.Recusa, match="conflito de merge"):
        delegar.aplicar("t01", processos=[])
    assert (mundo.repo / "remoto" / "existente.py").read_bytes() == b"A = 2\r\n"
    assert not (mundo.repo / "remoto" / "novo.py").exists()
    assert _git(mundo.repo, "status", "--short").strip() == ""
