# -*- coding: utf-8 -*-
"""As versoes do jogo fora do espelho: clone nosso, uma pasta por commit,
node_modules dividido por junction, o jogo num HTML so."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from bluelock import versoes as mod


def test_preparar_main_faz_pasta_sem_artifacts_dependencias_e_html(versoes, github, npm):
    ficha = versoes.preparar("main")
    sha = github.sha("main")
    assert ficha["sha"] == sha and ficha["modo"] == "html"
    pasta = versoes.pasta(sha)
    assert (pasta / "src" / "simulation.ts").is_file()
    assert not (pasta / "artifacts").exists()                  # 403 MB que ninguem le
    assert mod.e_link(pasta / "node_modules")                  # junction, nao copia
    assert (pasta / "node_modules" / "vite" / "bin" / "vite.js").is_file()
    html = Path(ficha["html"]).read_text(encoding="utf-8")
    assert "console.log('jogo')" in html and "background:#101815" in html
    assert 'src="/assets' not in html and "<\\/script" in html  # embutido como o bundle.mjs
    assert [c[0] for c in npm.chamadas] == ["ci", "run"]


def test_mesmo_lock_reaproveita_node_modules_e_lock_novo_instala_de_novo(versoes, github, npm):
    versoes.preparar("main")
    github.ramo("feat/um")
    github.commit("src/a.ts", "a\n", "feat: a")
    github.empurrar()
    versoes.preparar("feat/um")
    assert [c[0] for c in npm.chamadas].count("ci") == 1       # lock igual: sem npm ci
    github.commit("package-lock.json", '{"lockfileVersion": 3, "v": 2}\n', "build: deps")
    github.empurrar()
    versoes.preparar("feat/um")
    assert [c[0] for c in npm.chamadas].count("ci") == 2
    assert len(list((versoes.raiz / "modulos").iterdir())) == 2


def test_versao_pronta_nao_reconstroi(versoes, npm):
    versoes.preparar("main")
    antes = len(npm.chamadas)
    passos = []
    versoes.preparar("main", progresso=lambda n, total, texto: passos.append(texto))
    assert len(npm.chamadas) == antes and passos[-1] == "já estava pronta"


def test_resolver_ramo_sha_curto_e_desconhecido(versoes, github):
    github.ramo("fix/x")
    sha = github.commit("src/x.ts", "x\n", "fix: x")
    github.empurrar()
    versoes.buscar()
    assert versoes.resolver("fix/x") == sha
    assert versoes.resolver("origin/fix/x") == sha
    assert versoes.resolver(sha[:8]) == sha
    with pytest.raises(mod.ErroDeVersao, match="não achei"):
        versoes.resolver("nao-existe")
    with pytest.raises(mod.ErroDeVersao):
        versoes.resolver("")


def test_commit_de_ramo_apagado_vem_pelo_sha(versoes, github):
    github.ramo("tmp/sumiu")
    sha = github.commit("src/s.ts", "s\n", "feat: s")
    github.empurrar()
    versoes.buscar()
    github.apagar_remoto("tmp/sumiu")
    versoes.buscar()                                           # --prune: o ramo some do clone
    assert versoes.resolver(sha) == sha                        # mas o objeto ficou


def test_build_com_pedacos_extras_vira_modo_servidor(versoes, npm):
    npm.pedacos_extras = True
    ficha = versoes.preparar("main")
    assert ficha["modo"] == "servidor" and ficha["html"] is None


def test_tsc_quebrado_ainda_constroi_pelo_vite_e_avisa(versoes, npm, monkeypatch):
    npm.build_falha = True
    original = mod.rodar_processo

    def vite_direto(args, cwd=None, prazo=0, linha=None, env=None):
        if args[0] == "git":
            return original(args, cwd=cwd, prazo=prazo, linha=linha, env=env)
        dist = Path(cwd) / "dist" / "assets"
        dist.mkdir(parents=True, exist_ok=True)
        (Path(cwd) / "dist" / "index.html").write_text(
            '<script type="module" src="/assets/i.js"></script>', encoding="utf-8")
        (dist / "i.js").write_text("1", encoding="utf-8")
        return 0, ""
    monkeypatch.setattr(mod, "rodar_processo", vite_direto)
    ficha = versoes.preparar("main")
    assert ficha["modo"] == "html" and "tsc" in ficha["aviso_do_build"]


def test_build_quebrado_de_vez_e_erro_legivel(versoes, npm, monkeypatch):
    npm.build_falha = True
    original = mod.rodar_processo
    monkeypatch.setattr(mod, "rodar_processo", lambda args, **k: original(args, **k) if args[0] == "git"
                        else (1, "boom"))
    with pytest.raises(mod.ErroDeVersao, match="build"):
        versoes.preparar("main")


def test_limpar_mantem_recentes_e_fixadas_e_nunca_segue_a_junction(versoes, github):
    import itertools
    from datetime import datetime, timedelta
    minutos = itertools.count()
    versoes.relogio = lambda: datetime(2026, 10, 19, 10, 0) + timedelta(minutes=next(minutos))
    shas = []
    for n in range(3):
        github.ramo(f"r{n}", "main")
        github.commit(f"src/r{n}.ts", f"{n}\n", f"feat: r{n}")
        github.empurrar()
        shas.append(versoes.preparar(f"r{n}", construir=False)["sha"])
    versoes.fixar(shas[0])                                     # a mais velha, fixada
    modulos = versoes.raiz / "modulos"
    alvo = next(modulos.iterdir()) / "node_modules" / "vite" / "bin" / "vite.js"
    resultado = versoes.limpar(manter=1)
    assert resultado["apagadas"] == [shas[1]]
    assert not versoes.pasta(shas[1]).exists()
    assert versoes.pasta(shas[0]).exists() and versoes.pasta(shas[2]).exists()
    assert alvo.is_file()                                      # o node_modules dividido continua
    restantes = versoes.ler()["versoes"]
    assert set(restantes) == {shas[0], shas[2]}


def test_limpar_apaga_node_modules_sem_dono_e_pula_versao_em_uso(versoes, github):
    sha = versoes.preparar("main", construir=False)["sha"]
    github.commit("package-lock.json", '{"v": 9}\n', "build: deps")
    github.empurrar("main")
    novo = versoes.preparar("main", construir=False)["sha"]
    assert novo != sha

    ocupadas = {f"bluelock_versao_{novo[:12]}"}

    @contextmanager
    def trava(nome):
        yield nome not in ocupadas
    versoes.trava = trava
    resultado = versoes.limpar(manter=0)
    assert resultado["apagadas"] == [sha] and resultado["puladas"] == [novo]
    assert len(resultado["modulos_apagados"]) == 1             # o lock velho ficou sem dono
    assert versoes.pasta(novo).exists()


def test_so_usa_git_de_leitura_e_de_pasta_nunca_push_merge_commit(versoes, github, chamadas_git):
    versoes.preparar("main")
    github.ramo("feat/z")
    github.commit("src/z.ts", "z\n", "feat: z")
    github.empurrar()
    versoes.preparar("feat/z")
    versoes.limpar(manter=0)
    usados = {c[0] for c in chamadas_git}
    assert usados <= mod.GIT_PERMITIDOS, usados - mod.GIT_PERMITIDOS
    assert not usados & mod.GIT_PROIBIDOS
    # e o proprio guarda recusa o que nao e de leitura
    for proibido in ("push", "merge", "commit", "reset", "rebase"):
        with pytest.raises(AssertionError):
            versoes._git(proibido, "origin", "main")
    # e o GitHub de mentira continua so com o que o Adrian empurrou
    assert github.sha("main") == mod.git_real("rev-parse", "main", cwd=github.origin)[1].strip()


def test_abrir_html_usa_o_arquivo_direto(versoes):
    ficha = versoes.preparar("main")
    abertos = []
    resultado = versoes.abrir(ficha["sha"], abrir_url=lambda url: abertos.append(url) or {"como": "teste"})
    assert resultado["servidor"] is None
    assert abertos == [Path(ficha["html"]).resolve().as_uri()] and abertos[0].startswith("file:///")


def test_embutir_html_sem_script_ou_com_sobra_devolve_none(tmp_path):
    assert mod.embutir_html(tmp_path) is None
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    assert mod.embutir_html(tmp_path) is None


def test_apagar_pasta_com_junction_nao_apaga_o_alvo(tmp_path):
    alvo = tmp_path / "alvo"
    (alvo / "dentro").mkdir(parents=True)
    (alvo / "dentro" / "f.txt").write_text("fica", encoding="utf-8")
    pasta = tmp_path / "versao"
    pasta.mkdir()
    mod.criar_junction(alvo, pasta / "node_modules")
    mod.apagar_pasta(pasta)
    assert not pasta.exists()
    assert (alvo / "dentro" / "f.txt").read_text(encoding="utf-8") == "fica"


def test_icone_e_atalho(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(mod, "caminho_do_icone", lambda: tmp_path / "bl.ico")
    icone = mod.desenhar_icone()
    assert Image.open(icone).format == "ICO"
    rodados = []

    class Feito:
        returncode, stdout, stderr = 0, "", ""

    def rodar(args, **kw):
        rodados.append(args)
        (tmp_path / f"{mod.NOME_DO_ATALHO}.lnk").write_bytes(b"lnk")
        return Feito()
    ficha = mod.criar_atalho(tmp_path, rodar=rodar)
    assert ficha["ok"] and ficha["alvo"].lower().endswith(("pythonw.exe", "python.exe"))
    script = rodados[0][-1]
    assert "WScript.Shell" in script and "-m bluelock.versoes janela" in script
    assert "bl.ico" in script and str(mod.RAIZ) in script


def test_script_do_atalho_escapa_aspas():
    script = mod.script_do_atalho(Path("C:/a'b.lnk"), "x", "y", "z", "w")
    assert "'C:\\a''b.lnk'" in script or "a''b.lnk" in script


def test_matar_arvore_e_so_para_pid_nosso_e_navegador_tem_perfil_proprio(versoes):
    perfil = versoes.perfil_do_navegador()
    assert perfil.parent == versoes.raiz                       # nunca o perfil do Adrian
    if os.name == "nt":
        assert versoes.pids_do_nosso_navegador() == []          # nada aberto com o perfil de teste


def test_teste_que_importa_replay_de_artifacts_leva_so_esse_arquivo(versoes, github, npm):
    """26/10: 10 arquivos de teste do 0c200a0 importam `../artifacts/*.replay.json?raw`
    e nem carregavam na pasta sem `artifacts/`. Leva so o que o codigo cita."""
    github.commit("artifacts/lance.replay.json", '{"replay": 1}\n', "docs: replay")
    github.commit("artifacts/outro.json", '{"nao": "citado"}\n', "docs: outro")
    github.commit("src/lance.test.ts",
                  "import lance from '../artifacts/lance.replay.json?raw';\n"
                  "// pasta solta: ../artifacts/ nao conta\n", "test: lance")
    github.empurrar("main")
    ficha = versoes.preparar("main")
    pasta = versoes.pasta(ficha["sha"])
    assert (pasta / "artifacts" / "lance.replay.json").is_file()
    assert not (pasta / "artifacts" / "outro.json").exists()
    assert not (pasta / "artifacts" / "relatorio.json").exists()
    assert versoes.arquivos_de_artifacts(ficha["sha"]) == ["/artifacts/lance.replay.json"]


def test_pasta_antiga_ja_pronta_ganha_o_artifact_que_faltava(versoes, github, npm):
    sha = versoes.preparar("main")["sha"]
    pasta = versoes.pasta(sha)
    assert not (pasta / "artifacts").exists()
    novo = github.commit("src/x.test.ts", "import r from '../artifacts/relatorio.json';\n", "test: x")
    github.empurrar("main")
    # a mesma pasta (mesmo sha) preparada de novo completa o que o codigo cita
    mod_sha = versoes.preparar(novo)["sha"]
    assert (versoes.pasta(mod_sha) / "artifacts" / "relatorio.json").is_file()
