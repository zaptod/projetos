# -*- coding: utf-8 -*-
"""A janela de versoes: as linhas (puro) e a TELA no Tk, medida.

O teste de tela segue o que o conferente reprovou em 19/10 (tela dele:
1280x720 logicos, ~680 uteis): a lista tinha 11 de 19 linhas invisiveis e
sem barra, o comando de merge era a ultima linha de um texto de 4 linhas e
os vereditos estouravam a coluna.
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path

import pytest

from bluelock import janela

OFF = "fix/isagi-off-ball-20261020"
RAMOS = [{"ramo": "main", "sha": "a" * 40, "data": "2026-10-19T20:18:00+00:00", "assunto": "Merge"},
         {"ramo": OFF, "sha": "c" * 40, "data": "2026-10-19T21:57:00+00:00", "assunto": "fix: off-ball"},
         {"ramo": "fix/bachira-air-contact-20261019", "sha": "b" * 40, "data": "2026-10-19T19:36:00+00:00",
          "assunto": "feat: a"},
         {"ramo": "docs/blue-lock-ia-400-estrategias-v07-20261014", "sha": "f" * 40,
          "data": "2026-10-14T14:18:00+00:00", "assunto": "docs"},
         {"ramo": "feat/velho", "sha": "d" * 40, "data": "2026-10-18T10:00:00+00:00", "assunto": "feat: v"}]
COMANDO = f"git push origin origin/{OFF}:main"
TABELA = {"olhado_em": "2026-10-19T19:00:00", "main": {"sha": "a" * 40},
          "ramos": [{"ramo": OFF, "sha": "c" * 40, "a_frente": 5, "atras": 0, "ff": True,
                     "contem": ["fix/bachira-air-contact-20261019"], "ci": {"conclusao": "success"},
                     "testes": {"rodou": True, "ok": True, "testes": {"passou": 1770, "total": 1770}},
                     "veredito": {"tipo": "vale", "codigo": "vale",
                                  "texto": "vale o merge: fast-forward, CI verde, 1770/1770 testes verdes aqui, "
                                           "é a ponta boa"},
                     "comando": COMANDO, "areas": {"IA": 3},
                     "commits": [{"hash": f"c{n:06d}", "assunto": f"fix: passo {n}"} for n in range(12)]},
                    {"ramo": "fix/bachira-air-contact-20261019", "sha": "b" * 40, "a_frente": 3, "atras": 0,
                     "ff": True, "pontas": [OFF], "ci": {"conclusao": "success"}, "testes": {"rodou": False},
                     "veredito": {"tipo": "espere", "codigo": "contido",
                                  "texto": f"espere: o ramo `{OFF}` já contém este e vai além"}},
                    {"ramo": "docs/blue-lock-ia-400-estrategias-v07-20261014", "sha": "f" * 40, "a_frente": 6,
                     "atras": 53, "ff": False, "ci": None, "testes": {"rodou": False},
                     "veredito": {"tipo": "olho", "codigo": "nao_ff",
                                  "texto": "precisa de olho: não é fast-forward (a main andou 53 commit(s) "
                                           "depois que o ramo saiu); não conflita, mas o merge vira um commit "
                                           "novo — melhor abrir PR"}},
                    {"ramo": "feat/velho", "sha": "d" * 40, "a_frente": 0, "atras": 5, "ff": False,
                     "veredito": {"tipo": "na_main", "codigo": "na_main",
                                  "texto": "já está na main — nada a fazer"}}]}
REGISTRO = {"versoes": {"a" * 40: {"sha": "a" * 40, "modo": "html", "fixada": True, "usada_em": "x"},
                        "e" * 40: {"sha": "e" * 40, "modo": "html", "assunto": "colado", "ref": "eeeeeee",
                                   "usada_em": "y"}}}


def test_linhas_main_colados_decisoes_e_na_main_por_ultimo():
    linhas = janela.linhas(RAMOS, TABELA, REGISTRO)
    assert [linha["ref"] for linha in linhas] == ["main", "e" * 40, OFF, "fix/bachira-air-contact-20261019",
                                                    "docs/blue-lock-ia-400-estrategias-v07-20261014",
                                                    "feat/velho"]
    assert linhas[0]["valores"][6] == "★ sim"
    off = linhas[2]["valores"]
    assert off[3] == "✅ vale o merge" and off[4] == "verde" and off[5] == "ok 1770/1770"
    assert linhas[3]["valores"][3] == "⏳ espere (contido no isagi-off-ball)"
    assert linhas[4]["valores"][3] == "⚠ precisa de olho (não é ff)"
    assert linhas[5]["valores"][3] == "✔ já na main" and linhas[5]["valores"][4] == "—"


def test_todo_veredito_curto_cabe_no_limite():
    codigos = ["vale", "na_main", "contido", "ci_rodando", "ci_ilegivel", "sem_teste", "ci_vermelho", "teste_vermelho",
               "npm_ci", "nao_ff", "conflito", "ci_estranho", "desconhecido"]
    for codigo in codigos:
        a = {"pontas": ["feat/pressured-reception-continuation-20261019"],
             "veredito": {"codigo": codigo, "tipo": "espere", "texto": "x" * 200}}
        assert len(janela.veredito_curto(a)) <= janela.VEREDITO_MAX, codigo
    assert janela.apelido(OFF) == "isagi-off-ball"


def test_cabeca_que_o_vigia_nao_viu_nao_herda_veredito_velho():
    linha = janela.linhas([dict(RAMOS[1], sha="9" * 40)], TABELA, {"versoes": {}})[0]
    assert "ainda não olhou" in linha["valores"][3]


def test_acao_de_merge_so_copia_o_que_vale():
    linhas = {linha["ref"]: linha for linha in janela.linhas(RAMOS, TABELA, REGISTRO)}
    assert janela.acao_de_merge(linhas[OFF])["copiar"] == COMANDO
    contido = janela.acao_de_merge(linhas["fix/bachira-air-contact-20261019"])
    assert contido["copiar"] is None and f"dê o merge do {OFF}" in contido["texto"]
    olho = janela.acao_de_merge(linhas["docs/blue-lock-ia-400-estrategias-v07-20261014"])
    assert olho["copiar"].startswith("https://github.com/") and olho["rotulo"] == "Copiar link do PR"
    assert janela.acao_de_merge(linhas["feat/velho"])["copiar"] is None
    assert janela.acao_de_merge(linhas["main"])["copiar"] is None


def test_detalhe_tem_commits_e_veredito_por_extenso():
    linhas = janela.linhas(RAMOS, TABELA, REGISTRO)
    topo, veredito = janela.titulo_do_detalhe(linhas[2])
    assert OFF in topo and "1770/1770" in veredito
    assert "c000011" in janela.detalhe(linhas[2])


class VersoesDeMentira:
    def __init__(self, ramos):
        self.raiz = Path(".")
        self.log = None
        self._ramos = ramos
        self.limpezas = []

    def tem_clone(self):
        return True

    def ramos(self):
        return self._ramos

    def ler(self):
        return REGISTRO

    def fixar(self, sha, valor=True):
        pass

    def trava(self, _nome):
        from bluelock.conftest import trava_livre
        return trava_livre()

    def limpar(self, manter, protegidos=()):
        self.limpezas.append(set(protegidos))
        return {"apagadas": []}


class VigiaDeMentira:
    def ler(self):
        return TABELA


@pytest.fixture
def tela():
    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        pytest.skip(f"Tk não iniciou: {erro}")
    raiz.attributes("-alpha", 0.0)          # mapeada (para medir), mas invisivel
    yield raiz
    raiz.destroy()


def _montar(raiz, n_extras=15):
    extras = [{"ramo": f"feat/ramo-ja-juntado-numero-{n:02d}-20261019", "sha": f"{n:040x}",
               "data": "2026-10-19T08:00:00+00:00", "assunto": "x"} for n in range(n_extras)]
    j = janela.Janela(raiz, versoes=VersoesDeMentira(RAMOS + extras), vigia=VigiaDeMentira(),
                      atualizar_ao_abrir=False)
    raiz.update()
    return j


def test_tela_cabe_em_1280x680_lista_rola_e_comando_aparece(tela):
    j = _montar(tela)
    assert len(j.tabela.get_children()) >= 19
    # a janela cabe na tela dele (1280x680 uteis, com ~32 px de barra de titulo)
    assert tela.winfo_width() <= 1280 and tela.winfo_height() + 32 <= janela.ALTURA_UTIL
    fundo = tela.winfo_rooty() + tela.winfo_height()
    for widget in (j.b_rodar, j.b_limpar, j.console, j.campo_merge, j.texto):
        assert widget.winfo_ismapped(), widget
        assert widget.winfo_rooty() + widget.winfo_height() <= fundo + 1, widget
    # a barra de rolagem existe e a lista rola
    assert j.rolagem.winfo_ismapped() and j.rolagem.winfo_width() >= 8
    assert j.tabela.yview()[1] < 1.0
    j.tabela.yview_moveto(1.0)
    tela.update()
    assert j.tabela.yview()[1] == 1.0
    # nenhum veredito da lista maior que a coluna dele
    largura = int(j.tabela.column("veredito", "width"))
    for iid in j.tabela.get_children():
        texto = j.tabela.item(iid, "values")[3]
        assert j.letra.measure(texto) <= largura, (texto, j.letra.measure(texto), largura)
    # a tabela nao pede mais que o quadro (era o que comia a barra)
    soma = sum(int(j.tabela.column(c[0], "width")) for c in janela.COLUNAS)
    assert soma <= j.tabela.winfo_width() + 2
    # o comando de merge visivel SEM rolar, logo abaixo do veredito
    j.tabela.selection_set(f"ramo:{OFF}")
    j._escolheu()
    tela.update()
    assert j.merge.get() == COMANDO and str(j.b_comando.cget("state")) == "normal"
    assert j.campo_merge.winfo_rooty() > j.det_veredito.winfo_rooty()
    j.copiar_comando()
    assert tela.clipboard_get() == COMANDO


def test_tela_espere_desliga_o_botao_de_merge(tela):
    j = _montar(tela, n_extras=0)
    j.tabela.selection_set("ramo:fix/bachira-air-contact-20261019")
    j._escolheu()
    assert str(j.b_comando.cget("state")) == "disabled"
    assert f"dê o merge do {OFF}" in j.merge.get()


def test_tela_versao_aberta_e_protegida_na_limpeza(tela, monkeypatch):
    j = _montar(tela, n_extras=0)
    j._proteger("c" * 40)
    monkeypatch.setattr(janela.messagebox, "askyesno", lambda *a, **k: True)
    j.limpar()
    for _ in range(50):
        tela.update()
        if j.versoes.limpezas:
            break
        tela.after(20)
    assert j.versoes.limpezas == [{"c" * 40}]


def test_chrome_esquece_a_posicao_guardada(tmp_path):
    from bluelock.versoes import Versoes
    v = Versoes(tmp_path)
    preferencias = tmp_path / "navegador" / "Default" / "Preferences"
    preferencias.parent.mkdir(parents=True)
    preferencias.write_text(json.dumps({"browser": {"window_placement": {"bottom": 1106, "right": 1920},
                                                    "outra": 1}}), encoding="utf-8")
    assert v.esquecer_posicao() is True
    assert json.loads(preferencias.read_text(encoding="utf-8")) == {"browser": {"outra": 1}}
    assert v.esquecer_posicao() is False                       # nada mais a esquecer
