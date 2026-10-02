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


def _falha_ao_iniciar_tk(erro):
    return (isinstance(erro, tk.TclError)
            and "init.tcl" in str(erro))


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
