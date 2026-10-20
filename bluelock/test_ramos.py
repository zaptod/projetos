# -*- coding: utf-8 -*-
"""O vigia dos ramos, contra repositorios git DE VERDADE (conftest.GitHub).
Dublados: o `gh` (CI), o Telegram e o `npm test` do ramo."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bluelock import ramos as mod
from bluelock import versoes as mod_versoes
from bluelock.conftest import trava_livre

VERDE = {"rodou": True, "ok": True, "testes": {"passou": 1684, "falhou": 0, "pulou": 0, "total": 1684},
         "duracao_s": 143.2}


class Cena:
    def __init__(self, tmp_path, github, versoes):
        self.tmp, self.github, self.versoes = tmp_path, github, versoes
        self.avisos, self.gh_chamadas, self.testados = [], [], []
        self.ci: dict[str, dict] = {}          # sha -> {"status", "conclusion", "jobs"}
        self.pode = (True, "")
        self.agora = datetime(2026, 10, 19, 10, 0)
        self.resultado_do_teste = dict(VERDE)

    def gh(self, *args, prazo=60):
        self.gh_chamadas.append(args)
        assert tuple(args[:2]) in mod.GH_PERMITIDOS, args
        if args[:2] == ("run", "list"):
            runs = [{"headSha": sha, "headBranch": "?", "status": c.get("status", "completed"),
                     "conclusion": c.get("conclusion", ""), "url": f"https://ci/{sha[:7]}",
                     "databaseId": n + 1, "createdAt": "2026-10-19T12:00:00Z", "name": "Validate"}
                    for n, (sha, c) in enumerate(self.ci.items())]
            return 0, json.dumps(runs)
        if args[:2] == ("run", "view"):
            sha = list(self.ci)[int(args[2]) - 1]
            return 0, json.dumps({"jobs": self.ci[sha].get("jobs", [])})
        return 1, ""

    def testar(self, sha, ramo):
        self.testados.append(ramo)
        return dict(self.resultado_do_teste)

    def vigia(self):
        return mod.VigiaDeRamos(self.versoes, gh=self.gh, avisar=lambda t: self.avisos.append(t) or True,
                                pode_pesado=lambda agora: self.pode, testar=self.testar,
                                relogio=lambda: self.agora, estado=self.tmp / "estado" / "ramos.json",
                                trava=trava_livre, log=lambda _t: None)

    def verde(self, sha):
        self.ci[sha] = {"status": "completed", "conclusion": "success"}

    def ramo(self, nome, de="main", arquivo=None, ci="success"):
        self.github.ramo(nome, de)
        sha = self.github.commit(arquivo or f"src/{nome.replace('/', '-')}.ts", f"{nome}\n", f"feat: {nome}")
        self.github.empurrar()
        if ci:
            self.ci[sha] = {"status": "completed", "conclusion": ci}
        return sha


@pytest.fixture
def cena(tmp_path, github, versoes):
    return Cena(tmp_path, github, versoes)


def _por_nome(resultado):
    return {r["ramo"]: r for r in resultado["tabela"]["ramos"]}


def test_caso_zero_sem_ramo_novo_nao_faz_nada(cena):
    resultado = cena.vigia().olhar()
    assert resultado["acao"] == "olhou" and resultado["ramos"] == 0
    assert cena.avisos == [] and cena.testados == []
    assert json.loads((cena.tmp / "estado" / "ramos.json").read_text(encoding="utf-8"))["ramos"] == []
    assert cena.vigia().olhar()["acao"] == "olhou" and cena.avisos == []


def test_ramo_ja_na_main_nao_vira_aviso(cena, github):
    github.ramo("fix/velho")
    github.commit("src/v.ts", "v\n", "fix: velho")
    github.empurrar()
    github.ramo("main", "fix/velho")                   # ele juntou (ff) e empurrou a main
    github.empurrar("main")
    resultado = cena.vigia().olhar()
    r = _por_nome(resultado)["fix/velho"]
    assert r["veredito"]["codigo"] == "na_main" and r["a_frente"] == 0
    assert cena.avisos == [] and cena.testados == []


def test_pilha_aponta_a_ponta_e_so_a_ponta_e_testada(cena):
    cena.ramo("feat/a")
    cena.ramo("feat/b", de="feat/a")
    ponta = cena.ramo("fix/c", de="feat/b")
    resultado = cena.vigia().olhar()
    tabela = _por_nome(resultado)
    assert tabela["feat/a"]["veredito"]["codigo"] == "contido"
    assert "fix/c" in tabela["feat/a"]["veredito"]["texto"]           # a ponta, nao o do meio
    assert tabela["feat/b"]["pontas"] == ["fix/c"]
    assert set(tabela["fix/c"]["contem"]) == {"feat/a", "feat/b"}
    assert cena.testados == ["fix/c"]
    assert tabela["fix/c"]["veredito"]["codigo"] == "vale"
    assert tabela["fix/c"]["comando"] == "git push origin origin/fix/c:main"
    assert tabela["fix/c"]["sha"] == ponta
    assert len(cena.avisos) == 1
    aviso = cena.avisos[0]
    assert "vale o merge" in aviso and "git push origin origin/fix/c:main" in aviso
    assert "espere: o ramo `fix/c` já contém este" in aviso
    # a mesma cabeca nao vira outro aviso
    assert cena.vigia().olhar()["acao"] == "olhou" and len(cena.avisos) == 1
    assert cena.testados == ["fix/c"]                                  # nem outro teste


def test_ponta_vermelha_nao_prende_o_ramo_de_baixo(cena):
    """19/10 21:55, real: fix/isagi-reception (CI vermelho) continha
    fix/bachira-air-contact (CI verde). O de baixo e julgado sozinho."""
    cena.ramo("fix/air", ci="success")
    cena.ramo("feat/meio", de="fix/air", ci="success")
    cena.ramo("fix/isagi", de="feat/meio", ci="failure")
    tabela = _por_nome(cena.vigia().olhar())
    assert tabela["fix/isagi"]["veredito"]["codigo"] == "ci_vermelho"
    assert tabela["fix/air"]["pontas"] == ["feat/meio"]                 # a ponta BOA mais alta
    assert "CI vermelho" not in tabela["fix/air"]["veredito"]["texto"]
    assert tabela["feat/meio"]["pontas"] == [] and cena.testados == ["feat/meio"]
    meio = tabela["feat/meio"]["veredito"]
    assert meio["codigo"] == "vale" and "fix/isagi" in meio["texto"] and "vermelho" in meio["texto"]


def test_cabeca_nova_vira_aviso_so_daquele_ramo(cena, github):
    cena.ramo("feat/a")
    cena.vigia().olhar()
    sha = github.commit("src/mais.ts", "+\n", "feat: mais")
    github.empurrar("feat/a")
    cena.verde(sha)
    resultado = cena.vigia().olhar()
    assert resultado["novos"] == ["feat/a"] and len(cena.avisos) == 2
    assert cena.testados == ["feat/a", "feat/a"]


def test_ci_vermelho_nao_vale_e_diz_qual_job_sem_testar(cena):
    sha = cena.ramo("feat/quebra", ci="failure")
    cena.ci[sha]["jobs"] = [{"name": "core", "conclusion": "failure",
                             "steps": [{"name": "npm test", "conclusion": "failure"}]},
                            {"name": "browser", "conclusion": "success"}]
    resultado = cena.vigia().olhar()
    r = _por_nome(resultado)["feat/quebra"]
    assert r["veredito"]["codigo"] == "ci_vermelho" and "core: npm test" in r["veredito"]["texto"]
    assert cena.testados == [] and "não vale" in cena.avisos[0]


def test_nao_ff_precisa_de_olho_e_conflito_lista_o_arquivo(cena, github):
    cena.ramo("feat/livre", arquivo="src/livre.ts")
    cena.ramo("feat/briga", arquivo="src/simulation.ts")
    github.ramo("main", "main")
    github.commit("src/simulation.ts", "export class Simulation { x = 1 }\n", "fix: main andou")
    github.empurrar("main")
    tabela = _por_nome(cena.vigia().olhar())
    livre, briga = tabela["feat/livre"], tabela["feat/briga"]
    assert not livre["ff"] and livre["atras"] == 1 and livre["veredito"]["codigo"] == "nao_ff"
    assert briga["veredito"]["codigo"] == "conflito" and briga["conflitos"] == ["src/simulation.ts"]
    assert cena.testados == []
    assert "abrir PR: https://github.com/zaptod/BLUE-Lock-project/compare/main...feat/briga" in cena.avisos[0]


def test_testes_vermelhos_aqui_nao_vale(cena):
    cena.ramo("feat/vermelho")
    cena.resultado_do_teste = {"rodou": True, "ok": False,
                               "testes": {"passou": 1680, "falhou": 4, "pulou": 0, "total": 1684},
                               "falhas": ["FAIL src/pass.test.ts > perde a bola"]}
    r = _por_nome(cena.vigia().olhar())["feat/vermelho"]
    assert r["veredito"]["codigo"] == "teste_vermelho" and "4 teste(s)" in r["veredito"]["texto"]


def test_pesado_proibido_espera_e_avisa_depois_do_prazo(cena):
    cena.pode = (False, "League of Legends aberto")
    cena.ramo("feat/espera")
    r = _por_nome(cena.vigia().olhar())["feat/espera"]
    assert r["veredito"]["codigo"] == "sem_teste" and "League" in r["veredito"]["texto"]
    assert cena.avisos == [] and cena.testados == []
    cena.agora += timedelta(hours=mod.PRAZO_H, minutes=1)
    cena.vigia().olhar()
    assert len(cena.avisos) == 1 and "ainda não testei" in cena.avisos[0]
    # o jogo fechou: testa, e a cabeca ja avisada nao repete
    cena.pode = (True, "")
    cena.agora += timedelta(minutes=30)
    r = _por_nome(cena.vigia().olhar())["feat/espera"]
    assert cena.testados == ["feat/espera"] and r["veredito"]["codigo"] == "vale"
    assert len(cena.avisos) == 1


def test_ci_rodando_espera_sem_avisar(cena):
    sha = cena.ramo("feat/ci")
    cena.ci[sha] = {"status": "in_progress", "conclusion": ""}
    r = _por_nome(cena.vigia().olhar())["feat/ci"]
    assert r["veredito"]["codigo"] == "ci_rodando" and cena.avisos == []


def test_teste_so_por_tempo_nao_e_guardado_e_repete(cena):
    cena.ramo("feat/lento")
    cena.resultado_do_teste = {"rodou": True, "ok": False, "por_tempo": 2,
                               "testes": {"passou": 1682, "falhou": 2, "total": 1684}}
    cena.vigia().olhar()
    cena.resultado_do_teste = dict(VERDE)
    cena.agora += timedelta(minutes=30)
    r = _por_nome(cena.vigia().olhar())["feat/lento"]
    assert cena.testados == ["feat/lento", "feat/lento"] and r["veredito"]["codigo"] == "vale"


def test_no_maximo_n_testes_por_olhada(cena):
    for n in range(3):
        cena.ramo(f"feat/p{n}")
    v = cena.vigia()
    v.testes_por_olhada = 2
    v.olhar()
    assert len(cena.testados) == 2


def test_nunca_escreve_no_github(cena, github, chamadas_git):
    cena.ramo("feat/a")
    cena.ramo("feat/b", de="feat/a")
    cena.ramo("feat/x", ci="failure")
    cena.vigia().olhar()
    usados = {c[0] for c in chamadas_git}
    assert usados <= mod_versoes.GIT_PERMITIDOS and not usados & mod_versoes.GIT_PROIBIDOS
    assert all(tuple(c[:2]) in mod.GH_PERMITIDOS for c in cena.gh_chamadas)
    # o GitHub de mentira: os ramos do Adrian continuam onde ele deixou
    refs = mod_versoes.git_real("for-each-ref", "--format=%(refname)", cwd=github.origin)[1].split()
    assert sorted(refs) == ["refs/heads/feat/a", "refs/heads/feat/b", "refs/heads/feat/x", "refs/heads/main"]
    # o guarda do gh recusa escrita mesmo se alguem tentar
    for proibido in (("pr", "create"), ("api", "-X", "PATCH", "repos/x"), ("run", "rerun", "1"),
                     ("run", "list", "--method", "POST")):
        with pytest.raises(AssertionError):
            mod.gh_real(*proibido)


def test_o_fonte_nao_tem_push_nem_merge_como_comando():
    """Varre o fonte: nenhum `"push"`/`"merge"` vira argumento de processo
    (o texto do aviso pode CITAR o comando que o Adrian roda)."""
    import re
    escrita = "push|merge|commit|reset|rebase|pull|stash"
    padroes = [re.compile(rf'git\w*\(\s*"({escrita})"'),                # self._git("push", ...)
               re.compile(rf'\[\s*"git"\s*,\s*"({escrita})"'),           # ["git", "push", ...]
               re.compile(r'\[\s*"gh"\s*,\s*"(pr|api|repo|release)"'),   # ["gh", "pr", ...]
               re.compile(r'gh\w*\(\s*"(pr|api|repo|release)"'),
               re.compile(r'"(PATCH|POST|PUT|DELETE)"')]
    for nome in ("ramos.py", "versoes.py", "janela.py"):
        texto = (Path(mod.__file__).with_name(nome)).read_text(encoding="utf-8")
        for padrao in padroes:
            assert not padrao.search(texto), (nome, padrao.pattern, padrao.search(texto).group(0))
    # e o padrao pega o que deve pegar
    assert padroes[0].search('self._git("push", "origin")') and padroes[1].search('["git", "merge", "x"]')


def test_veredito_puro_ordem_das_regras():
    base = {"a_frente": 2, "atras": 0, "ff": True, "pontas": [], "ci": {"conclusao": "success"},
            "testes": dict(VERDE)}
    assert mod.veredito(base)["codigo"] == "vale"
    assert mod.veredito(dict(base, a_frente=0))["codigo"] == "na_main"
    assert mod.veredito(dict(base, pontas=["x"]))["codigo"] == "contido"
    assert mod.veredito(dict(base, ci={"conclusao": "failure"}))["codigo"] == "ci_vermelho"
    assert mod.veredito(dict(base, ff=False, atras=3))["codigo"] == "nao_ff"
    assert mod.veredito(dict(base, ci={"estado": "queued"}))["final"] is False
    assert mod.veredito(dict(base, ci={"conclusao": "cancelled"}))["codigo"] == "ci_estranho"
    sem_ci = mod.veredito(dict(base, ci={"conclusao": None}))
    assert sem_ci["codigo"] == "vale" and "não rodou" in sem_ci["texto"]


def test_areas_do_diff():
    assert mod.area("src/pass-diagnostics.test.ts") == "testes"
    assert mod.area("Docs/PLANO.md") == "docs"
    assert mod.area("src/character-art.ts") == "gráficos"
    assert mod.area("src/bachira.ts") == "personagens"
    assert mod.area("src/cognition.ts") == "IA"
    assert mod.area("scripts/audit-gesture-exit.mjs") == "auditorias"
    assert mod.area("package-lock.json") == "dependências"
    assert mod.area(".github/workflows/validate.yml") == "CI"


def test_lancador_roda_a_main_e_os_ramos(tmp_path, monkeypatch):
    from bluelock import vigia
    monkeypatch.setattr(vigia, "RAIZ", tmp_path)
    texto = vigia.escrever_lancador(python=r"C:\Python314\python.exe").read_text(encoding="utf-8")
    assert texto.index("-m bluelock.vigia olhar") < texto.index("-m bluelock.ramos olhar --saida")
    assert ">>" not in texto
