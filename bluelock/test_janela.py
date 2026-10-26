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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bluelock import estilo, janela

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


def test_nome_amigavel_tira_o_slug_cru():
    assert estilo.nome_amigavel("main") == ("Versão principal", "")
    assert estilo.nome_amigavel("fix/bachira-roulette-choreography-20261024") == (
        "Bachira · roulette choreography", "correção")
    assert estilo.nome_amigavel("docs/biblia-auditoria-personagens-20261026") == (
        "Biblia auditoria personagens", "documentação")
    assert estilo.nome_amigavel("a" * 40) == ("Commit aaaaaaa", "")


def test_data_relativa_e_de_hoje():
    agora = datetime(2026, 10, 26, 14, 0).astimezone()
    def iso(**delta):
        return (agora - timedelta(**delta)).isoformat()
    assert estilo.data_relativa(iso(minutes=1), agora) == "agora há pouco"
    assert estilo.data_relativa(iso(minutes=20), agora) == "há 20 min"
    assert estilo.data_relativa(iso(hours=2), agora) == "há 2 h"
    assert estilo.data_relativa(iso(days=1), agora) == "ontem"
    assert estilo.data_relativa(iso(days=3), agora) == "há 3 dias"
    assert estilo.data_relativa(iso(days=20), agora) == (agora - timedelta(days=20)).strftime("%d/%m")
    assert estilo.data_relativa(None) == "" and estilo.data_relativa("lixo") == ""
    assert estilo.e_de_hoje(iso(minutes=5), agora) and not estilo.e_de_hoje(iso(days=1), agora)


def test_filtrar_por_chip_e_busca():
    todas = janela.linhas(RAMOS, TABELA, REGISTRO)
    assert len(janela.filtrar(todas)) == len(todas)
    assert [linha["ref"] for linha in janela.filtrar(todas, "preparadas")] == ["main", "e" * 40]
    assert [linha["ref"] for linha in janela.filtrar(todas, "fixadas")] == ["main"]
    iso = {"c" * 40: "2026-10-26T08:00:00+00:00"}
    agora = datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc)
    assert [linha["ref"] for linha in janela.filtrar(todas, "novas", iso=iso, agora=agora)] == [OFF]
    assert [linha["ref"] for linha in janela.filtrar(todas, busca="ISAGI off")] == [OFF]
    assert janela.filtrar(todas, busca="zzz") == []


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
    assert len(j.visiveis) >= 19 and len(j._cartoes) == len(j.visiveis)
    # a janela cabe na tela dele (1280x680 uteis, com ~32 px de barra de titulo)
    assert tela.winfo_width() <= 1280 and tela.winfo_height() + 32 <= janela.ALTURA_UTIL
    fundo = tela.winfo_rooty() + tela.winfo_height()
    j.alternar_console()                    # o log tecnico e uma gaveta: recolhido por padrao
    tela.update()
    for widget in (j.b_rodar, j.b_limpar, j.b_atualizar, j.console, j.estado):
        assert widget.winfo_ismapped(), widget
        assert widget.winfo_rooty() + widget.winfo_height() <= fundo + 1, widget
    j.alternar_console()
    tela.update()
    assert not j.console.winfo_ismapped()
    # o Jogar fica a vista, sem rolar, e dentro da janela
    assert j.b_rodar.winfo_rooty() + j.b_rodar.winfo_height() <= fundo
    # a lista rola: a barra existe e o ultimo cartao chega ao fim
    assert j.lista.barra.winfo_ismapped() and j.lista.barra.winfo_width() >= 8
    assert j.lista.canvas.yview()[1] < 1.0
    j.lista.canvas.yview_moveto(1.0)
    tela.update()
    assert j.lista.canvas.yview()[1] == 1.0
    # nenhum cartao maior que a area da lista
    for cartao in j._cartoes.values():
        assert cartao["quadro"].winfo_width() <= j.lista.canvas.winfo_width()
    # o comando de merge, nos detalhes (recolhidos por padrao), logo abaixo do veredito
    assert not j.campo_merge.winfo_ismapped()
    j.selecionar(f"ramo:{OFF}")
    j.alternar_detalhes(True)
    tela.update()
    assert j.merge.get() == COMANDO and str(j.b_comando.cget("state")) == "normal"
    assert j.campo_merge.winfo_rooty() > j.det_veredito.winfo_rooty()
    j.copiar_comando()
    assert tela.clipboard_get() == COMANDO


def test_tela_cabe_em_900x600(tela):
    j = _montar(tela)
    tela.geometry("900x600+0+0")
    tela.update()
    fundo = tela.winfo_rooty() + tela.winfo_height()
    for widget in (j.b_rodar, j.b_limpar, j.estado, j.campo_busca):
        assert widget.winfo_ismapped() and widget.winfo_rooty() + widget.winfo_height() <= fundo + 1, widget
    # o selo e o nome do cartao nao passam do cartao
    for cartao in j._cartoes.values():
        assert cartao["quadro"].winfo_reqwidth() <= j.lista.canvas.winfo_width() + 2


def test_tela_espere_desliga_o_botao_de_merge(tela):
    j = _montar(tela, n_extras=0)
    j.selecionar("ramo:fix/bachira-air-contact-20261019")
    assert str(j.b_comando.cget("state")) == "disabled"
    assert f"dê o merge do {OFF}" in j.merge.get()


def test_tela_cartao_tem_nome_amigavel_e_selos(tela):
    j = _montar(tela, n_extras=0)
    main = j._cartoes["ramo:main"]["quadro"]
    textos = []

    def varrer(w):
        if isinstance(w, tk.Label):
            textos.append(w.cget("text"))
        for filho in w.winfo_children():
            varrer(filho)
    varrer(main)
    assert "Versão principal" in textos and "VERSÃO PRINCIPAL" in textos
    varrer(j._cartoes[f"ramo:{OFF}"]["quadro"])
    assert "Isagi · off ball" in textos


def test_tela_busca_filtra_e_vazio_tem_saida(tela):
    j = _montar(tela, n_extras=0)
    assert j._termo() == ""                                     # a dica nao conta como busca
    j.campo_busca.focus_force()
    j._dica(False)
    j.busca.set("bachira")
    tela.update()
    assert [linha["ref"] for linha in j.visiveis] == ["fix/bachira-air-contact-20261019"]
    j.busca.set("nada disso existe")
    tela.update()
    assert j.visiveis == [] and j._linha_escolhida() is not None   # a escolha nao some, so a lista
    j._limpar_busca()
    tela.update()
    assert len(j.visiveis) == len(j.linhas)


def test_tela_jogar_desligado_enquanto_prepara_e_aviso_no_erro(tela):
    j = _montar(tela, n_extras=0)
    j.ocupado, j._op = True, "jogar"
    j._terminou("erro", "ErroDeVersao: npm ci falhou\nresto")
    assert j.ocupado is False and str(j.b_rodar.cget("state")) == "normal"
    assert any("Não consegui preparar" in w.cget("text") for f in j.zona_aviso.winfo_children()
               for w in f.winfo_children() if isinstance(w, tk.Label))
    j.ocupado, j._op = True, "atualizar"
    j._terminou("erro", "sem rede")
    assert "sem conexão" in j.estado.cget("text")


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
