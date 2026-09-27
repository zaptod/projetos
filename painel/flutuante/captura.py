# -*- coding: utf-8 -*-
"""Foto de UMA janela, e so dela: `PrintWindow` com PW_RENDERFULLCONTENT.

NUNCA captura de tela ou de regiao. `ImageGrab.grab(bbox=...)` fotografa o
que estiver NAQUELE PEDACO DA TELA — com a janela coberta, vai para o disco
o que estiver na frente dela. Ja aconteceu: o que foi salvo foi a conversa
pessoal do Adrian. `PrintWindow` pede a propria janela que se desenhe num
bitmap, entao nao ha como sair outra coisa.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

PW_RENDERFULLCONTENT = 0x2


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def hwnd_da_janela(raiz) -> int:
    """O HWND de nivel mais alto da janela Tk."""
    raiz.update_idletasks()
    try:
        return int(raiz.wm_frame(), 16)
    except (ValueError, TypeError):
        return ctypes.windll.user32.GetParent(raiz.winfo_id())


def fotografar(raiz, destino) -> tuple:
    """Salva a janela em `destino` (PNG). Devolve (largura, altura)."""
    imagem = capturar(raiz)
    imagem.save(destino)
    return imagem.size


def capturar(raiz):
    """A janela como imagem PIL (RGB)."""
    from PIL import Image

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = hwnd_da_janela(raiz)
    caixa = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(caixa))
    largura = caixa.right - caixa.left
    altura = caixa.bottom - caixa.top
    tela = user32.GetDC(hwnd)
    memoria = gdi32.CreateCompatibleDC(tela)
    bitmap = gdi32.CreateCompatibleBitmap(tela, largura, altura)
    antigo = gdi32.SelectObject(memoria, bitmap)
    try:
        user32.PrintWindow(hwnd, memoria, PW_RENDERFULLCONTENT)
        cabeca = _BITMAPINFOHEADER()
        cabeca.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        cabeca.biWidth = largura
        cabeca.biHeight = -altura
        cabeca.biPlanes = 1
        cabeca.biBitCount = 32
        buffer = ctypes.create_string_buffer(largura * altura * 4)
        gdi32.GetDIBits(memoria, bitmap, 0, altura, buffer,
                        ctypes.byref(cabeca), 0)
        imagem = Image.frombuffer("RGBA", (largura, altura), buffer.raw,
                                  "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32.SelectObject(memoria, antigo)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memoria)
        user32.ReleaseDC(hwnd, tela)
    return imagem


__all__ = ["capturar", "fotografar", "hwnd_da_janela"]
