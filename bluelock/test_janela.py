# -*- coding: utf-8 -*-
"""A janela de versoes: as linhas (puro) e a montagem no Tk com dubles."""
from __future__ import annotations

import tkinter as tk

import pytest

from bluelock import janela

RAMOS = [{"ramo": "main", "sha": "a" * 40, "data": "2026-10-19T20:18:00+00:00", "assunto": "Merge"},
         {"ramo": "fix/c", "sha": "c" * 40, "data": "2026-10-19T17:27:00+00:00", "assunto": "fix: c"},
         {"ramo": "feat/a", "sha": "b" * 40, "data": "2026-10-19T16:00:00+00:00", "assunto": "feat: a"},
         {"ramo": "feat/velho", "sha": "d" * 40, "data": "2026-10-18T10:00:00+00:00", "assunto": "feat: v"}]
TABELA = {"olhado_em": "2026-10-19T19:00:00", "main": {"sha": "a" * 40},
          "ramos": [{"ramo": "fix/c", "sha": "c" * 40, "a_frente": 2, "atras": 0, "ff": True,
                     "contem": ["feat/a"], "ci": {"conclusao": "success"},
                     "testes": {"rodou": True, "ok": True, "testes": {"passou": 1684, "total": 1684}},
                     "veredito": {"tipo": "vale", "codigo": "vale", "texto": "vale o merge: ff"},
                     "comando": "git push origin origin/fix/c:main", "areas": {"IA": 3},
                     "commits": [{"hash": "ccccccc", "assunto": "fix: c"}]},
                    {"ramo": "feat/a", "sha": "b" * 40, "a_frente": 1, "atras": 0, "ff": True,
                     "ci": {"conclusao": "success"}, "testes": {"rodou": False},
                     "veredito": {"tipo": "espere", "texto": "espere: o ramo `fix/c` já contém este"}},
                    {"ramo": "feat/velho", "sha": "d" * 40, "a_frente": 0, "atras": 5, "ff": False,
                     "veredito": {"tipo": "na_main", "texto": "já está na main — nada a fazer"}}]}
REGISTRO = {"versoes": {"a" * 40: {"sha": "a" * 40, "modo": "html", "fixada": True, "usada_em": "x"},
                        "e" * 40: {"sha": "e" * 40, "modo": "html", "assunto": "colado", "ref": "eeeeeee",
                                   "usada_em": "y"}}}


def test_linhas_main_primeiro_decisoes_depois_na_main_e_colados_por_ultimo():
    linhas = janela.linhas(RAMOS, TABELA, REGISTRO)
    assert [linha["ref"] for linha in linhas] == ["main", "fix/c", "feat/a", "feat/velho", "e" * 40]
    main, fix = linhas[0], linhas[1]
    assert main["valores"][6] == "★ sim"                            # fixada e pronta
    assert fix["valores"][3].startswith("✅ vale o merge") and fix["valores"][4] == "verde"
    assert fix["valores"][5] == "ok 1684/1684"
    assert "`" not in linhas[2]["valores"][3]
    assert linhas[3]["tipo"] == "na_main" and linhas[3]["valores"][4] == "—"


def test_cabeca_que_o_vigia_nao_viu_nao_herda_veredito_velho():
    ramos = [dict(RAMOS[1], sha="f" * 40)]
    linha = janela.linhas(ramos, TABELA, {"versoes": {}})[0]
    assert "ainda não olhou" in linha["valores"][3]


def test_detalhe_traz_comando_e_commits():
    linhas = janela.linhas(RAMOS, TABELA, REGISTRO)
    texto = janela.detalhe(linhas[1])
    assert "git push origin origin/fix/c:main" in texto and "ccccccc" in texto and "feat/a" in texto
    assert "PR:" in janela.detalhe(linhas[2])
    assert "Escolha" in janela.detalhe(None)


class VersoesDeMentira:
    def __init__(self):
        from pathlib import Path
        self.raiz = Path(".")
        self.log = None
        self.preparados = []

    def tem_clone(self):
        return True

    def ramos(self):
        return RAMOS

    def ler(self):
        return REGISTRO

    def fixar(self, sha, valor=True):
        REGISTRO["versoes"].setdefault(sha, {"sha": sha})["fixada"] = valor


class VigiaDeMentira:
    def ler(self):
        return TABELA


def test_janela_monta_com_a_cara_do_painel_e_lista_tudo():
    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        pytest.skip(f"Tk não iniciou: {erro}")
    raiz.withdraw()
    try:
        j = janela.Janela(raiz, versoes=VersoesDeMentira(), vigia=VigiaDeMentira(), atualizar_ao_abrir=False)
        raiz.update_idletasks()
        assert len(j.tabela.get_children()) == 5
        assert j.tabela.selection() == ("ramo:main",)
        assert "main aaaaaaa" in j.resumo.cget("text") and "2 ramo(s) fora da main" in j.resumo.cget("text")
        assert raiz.cget("bg") == j.tema.fundo
        j.tabela.selection_set("ramo:fix/c")
        j._escolheu()
        assert "git push origin origin/fix/c:main" in j.texto.get("1.0", "end")
        j.copiar_comando()
        assert raiz.clipboard_get() == "git push origin origin/fix/c:main"
    finally:
        raiz.destroy()
