# -*- coding: utf-8 -*-
"""Prova de tela das janelas do painel, SEM roubar o foco de quem usa.

Medido em 28/09/2026: um `tk.Tk()` aberto por um processo filho do VS Code
vira a janela da frente no primeiro `update_idletasks`, mesmo retirada
(`withdraw`) -- o foco sai do que o Adrian estava fazendo. Criar a janela
fora da tela nao serve: o Tk nao pinta o que esta fora do monitor e a foto
sai branca.

O que funciona (medido: 13 ms): deixar o Tk criar a janela, DEVOLVER o foco
para a janela que o tinha e mandar a nossa para o FUNDO da pilha. No fundo,
coberta, ela continua sendo desenhada pelo DWM, e o `PrintWindow` fotografa
so ela (nunca `ImageGrab`: ver `flutuante/captura.py`).
"""
from __future__ import annotations

import sys


def janela_da_frente() -> int:
    if sys.platform != "win32":
        return 0
    import ctypes
    return int(ctypes.windll.user32.GetForegroundWindow() or 0)


def discreta(raiz, antes: int) -> None:
    """Devolve o foco a `antes` e poe `raiz` no fundo, sem ativa-la."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    wintypes.UINT]
    raiz.update_idletasks()
    try:
        nossa = int(raiz.wm_frame(), 16)
    except (ValueError, TypeError):
        return
    if antes and user32.GetForegroundWindow() == nossa:
        user32.SetForegroundWindow(antes)
    HWND_BOTTOM, SEM_ATIVAR, SEM_TAMANHO, SEM_MOVER = 1, 0x10, 0x1, 0x2
    user32.SetWindowPos(nossa, HWND_BOTTOM, 0, 0, 0, 0,
                        SEM_ATIVAR | SEM_TAMANHO | SEM_MOVER)


def fotografar(raiz, destino) -> tuple:
    from .flutuante.captura import fotografar as _foto
    return _foto(raiz, destino)


__all__ = ["discreta", "fotografar", "janela_da_frente"]
