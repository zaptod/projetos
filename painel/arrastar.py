# -*- coding: utf-8 -*-
"""Soltar arquivo do Explorer numa janela Tk (Windows), sem pacote extra.

O Tk nao tem arrastar-e-soltar de arquivo, e nem o `tkinterdnd2` nem o
`windnd` estao instalados. O Windows faz o servico sozinho: a janela que
chama `DragAcceptFiles` recebe WM_DROPFILES com a lista. Aqui a janela do Tk
ganha um procedimento de janela na frente do dela (subclasse), que so pega
esse recado e passa todo o resto adiante.

A ENTREGA NAO E NA HORA. O procedimento roda dentro do laco de mensagens do
Tk; mexer em widget dali e pedir para reentrar. Os caminhos vao para uma
lista, e quem desenha le a lista no proprio relogio (`pegar()`).

Fora do Windows, `aceitar` devolve None e nada acontece.
"""
from __future__ import annotations

import sys

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4


class Soltura:
    """A subclasse viva de uma janela. Guarde a referencia: sem ela, o
    callback do ctypes e coletado e o Windows chama memoria solta."""

    def __init__(self, hwnd: int):
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self.hwnd = int(hwnd)
        self.caminhos: list = []
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32")
        resultado = ctypes.c_ssize_t
        self._WNDPROC = ctypes.WINFUNCTYPE(resultado, wintypes.HWND,
                                           wintypes.UINT, wintypes.WPARAM,
                                           wintypes.LPARAM)
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int,
                                             ctypes.c_void_p]
        user32.CallWindowProcW.restype = resultado
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND,
                                           wintypes.UINT, wintypes.WPARAM,
                                           wintypes.LPARAM]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                           wintypes.LPWSTR, wintypes.UINT]
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        self._user32, self._shell32 = user32, shell32
        self._proc = self._WNDPROC(self._procedimento)
        self._antigo = user32.SetWindowLongPtrW(
            self.hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p))
        shell32.DragAcceptFiles(self.hwnd, True)

    def _procedimento(self, hwnd, mensagem, wparam, lparam):
        if mensagem == WM_DROPFILES:
            try:
                self.caminhos.extend(self._ler(wparam))
            finally:
                self._shell32.DragFinish(wparam)
            return 0
        return self._user32.CallWindowProcW(self._antigo, hwnd, mensagem,
                                            wparam, lparam)

    def _ler(self, hdrop) -> list:
        ctypes = self._ctypes
        total = self._shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        saida = []
        for i in range(total):
            tamanho = self._shell32.DragQueryFileW(hdrop, i, None, 0) + 1
            buffer = ctypes.create_unicode_buffer(tamanho)
            self._shell32.DragQueryFileW(hdrop, i, buffer, tamanho)
            saida.append(buffer.value)
        return saida

    def pegar(self) -> list:
        """Os caminhos soltos desde a ultima vez (e esvazia)."""
        saida, self.caminhos = self.caminhos, []
        return saida

    def soltar(self) -> None:
        """Devolve o procedimento original (antes de destruir a janela)."""
        if self._antigo:
            self._shell32.DragAcceptFiles(self.hwnd, False)
            self._user32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC,
                                           self._antigo)
            self._antigo = None


def aceitar(janela) -> Soltura | None:
    """Liga o soltar-arquivo na janela Tk de nivel mais alto de `janela`."""
    if sys.platform != "win32":
        return None
    try:
        raiz = janela.winfo_toplevel()
        raiz.update_idletasks()
        return Soltura(int(raiz.wm_frame(), 16))
    except Exception:                                        # noqa: BLE001
        return None


def simular_soltura(hwnd: int, caminhos: list) -> bool:
    """Posta um WM_DROPFILES de verdade (para teste): monta o DROPFILES em
    memoria global, como o Explorer faz."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32")
    user32 = ctypes.WinDLL("user32")
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                    wintypes.WPARAM, wintypes.LPARAM]

    class DROPFILES(ctypes.Structure):
        _fields_ = [("pFiles", wintypes.DWORD), ("x", wintypes.LONG),
                    ("y", wintypes.LONG), ("fNC", wintypes.BOOL),
                    ("fWide", wintypes.BOOL)]

    lista = ("\0".join(str(c) for c in caminhos) + "\0\0").encode("utf-16-le")
    tamanho = ctypes.sizeof(DROPFILES) + len(lista)
    GHND = 0x0042
    memoria = kernel32.GlobalAlloc(GHND, tamanho)
    ponteiro = kernel32.GlobalLock(memoria)
    cabeca = DROPFILES(ctypes.sizeof(DROPFILES), 10, 10, False, True)
    ctypes.memmove(ponteiro, ctypes.byref(cabeca), ctypes.sizeof(DROPFILES))
    ctypes.memmove(ponteiro + ctypes.sizeof(DROPFILES), lista, len(lista))
    kernel32.GlobalUnlock(memoria)
    return bool(user32.PostMessageW(hwnd, WM_DROPFILES, memoria, 0))


__all__ = ["Soltura", "aceitar", "simular_soltura"]
