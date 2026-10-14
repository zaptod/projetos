# -*- coding: utf-8 -*-
"""Base Tk unica para os testes do painel."""
import tkinter as tk

import pytest


@pytest.fixture(scope="session", autouse=True)
def raiz_tk():
    """Inicializa o Tcl uma vez e o mantem vivo durante a suite."""
    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        pytest.skip(f"Tk nao iniciou: {erro}")
    raiz.withdraw()
    tk._default_root = None
    yield raiz
    raiz.destroy()


# 14/10/2026: a terceira variante, o `tk.tcl` lido pela metade ("This
# probably means that tk wasn't installed properly"), apareceu no meio da
# suite com outros pytest rodando na maquina — mesmo ambiente, mesma causa.
TK_SEM_BIBLIOTECA = ("init.tcl", "tcl_findLibrary",
                     "tk wasn't installed properly")


def _falha_ao_iniciar_tk(erro):
    """O Tcl nao achou a propria biblioteca: e o ambiente, nao o painel.
    05/10/2026: a variante `invalid command name "tcl_findLibrary"` (Tcl
    carregado pela metade com varios pytest juntos) caia como falha."""
    return (isinstance(erro, tk.TclError)
            and any(trecho in str(erro) for trecho in TK_SEM_BIBLIOTECA))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    relatorio = resultado.get_result()
    erro = call.excinfo.value if call.excinfo else None
    if relatorio.failed and _falha_ao_iniciar_tk(erro):
        caminho, linha, _ = item.location
        relatorio.outcome = "skipped"
        relatorio.longrepr = (caminho, linha,
                              f"Skipped: Tk nao iniciou: {erro}")


@pytest.fixture(autouse=True)
def atelie_vazio(tmp_path, monkeypatch):
    """A arte de verdade do Adrian no Atelie (palco/biblioteca/animacoes) nao
    entra nos testes do painel: as fotos de referencia da Vila sao do desenho
    de codigo. 08/10/2026: a arvore dele quebrou `test_nada_fora_do_grok_mudou`.
    Quem testa o Atelie aponta para a pasta dele mesmo."""
    from neural_fights.tools import atelie_animacoes
    from painel.flutuante import arte_pronta
    monkeypatch.setattr(atelie_animacoes, "ANIMACOES", tmp_path / "atelie_animacoes_vazio")
    arte_pronta._PECAS_ATELIE.clear()
    arte_pronta._FOLHAS_ATELIE.clear()
    arte_pronta._limpar()
    yield
    arte_pronta._PECAS_ATELIE.clear()
    arte_pronta._FOLHAS_ATELIE.clear()
    arte_pronta._limpar()
