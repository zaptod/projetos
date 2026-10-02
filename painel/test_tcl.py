# -*- coding: utf-8 -*-
"""Contrato da base Tcl compartilhada pelos testes de interface."""
import tkinter as tk

from painel.conftest import _falha_ao_iniciar_tk


def test_raiz_tk_da_sessao_permanece_disponivel(raiz_tk):
    janela = tk.Toplevel(raiz_tk)
    janela.destroy()
    assert raiz_tk.tk.call("info", "patchlevel")


def test_falha_de_init_tcl_e_reconhecida():
    assert _falha_ao_iniciar_tk(tk.TclError("nao achei init.tcl"))
    assert not _falha_ao_iniciar_tk(tk.TclError("widget invalido"))
