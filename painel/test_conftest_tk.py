# -*- coding: utf-8 -*-
"""O conftest do painel pula (nao falha) quando o Tcl nao acha a biblioteca.

05/10/2026: a variante `invalid command name "tcl_findLibrary"` nao era
reconhecida e virava teste vermelho a toa (o vigia pedia correcao ao Codex).
"""
import tkinter as tk

from painel.conftest import _falha_ao_iniciar_tk


def test_tcl_sem_biblioteca_nas_duas_variantes_e_ambiente():
    assert _falha_ao_iniciar_tk(tk.TclError("Can't find a usable init.tcl in the following"))
    assert _falha_ao_iniciar_tk(tk.TclError('invalid command name "tcl_findLibrary"'))


def test_erro_tcl_de_verdade_continua_falha():
    assert not _falha_ao_iniciar_tk(tk.TclError('bad window path name ".x"'))
    assert not _falha_ao_iniciar_tk(ValueError("tcl_findLibrary"))
