# -*- coding: utf-8 -*-
"""A Oficina da Vila (vila/editor.py) dentro do sistema visual e da tela dele.

O que este arquivo trava:

1. SEM COR NEM FONTE ESCRITA A MAO. Tudo vem do tema (`painel/estilo.py`):
   ate 28/09/2026 eram oito cores literais proprias e `("Segoe UI", 9)`
   repetido, a ultima tela fora do sistema.
2. CABE NA TELA DELE. 1366x768 com a barra do Windows: a janela de 1330x700
   fixos nascia com o rodape embaixo da barra.
3. NADA ESPREMIDO. O `pack` corta em silencio: um botao espremido a largura
   zero continua "dentro da janela" e nao existe para quem olha. Aqui cada
   botao, campo e rotulo tem que aparecer do tamanho que pediu.

Rode da raiz:  python -m pytest vila/test_editor.py -q
"""
from __future__ import annotations

import re
import tkinter as tk
import unittest
from pathlib import Path

from vila import editor

TELA_DELE = (1366, 768)
BARRA_REAL_DO_WINDOWS = 40
INTERATIVOS = {"Button", "Label", "Entry", "Radiobutton", "Checkbutton",
               "Spinbox", "TCombobox"}


class SistemaVisual(unittest.TestCase):
    def test_sem_cor_nem_fonte_literal(self):
        fonte = Path(editor.__file__).read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{6}\b", fonte), [])
        for literal in ('"Segoe UI"', '"Consolas"'):
            self.assertNotIn(literal, fonte)

    def test_geometria_cabe_na_tela_dele_e_nas_outras(self):
        for tela in (TELA_DELE, (1024, 600), (1920, 1080)):
            largura, altura, x, y = editor.geometria(tela)
            self.assertLessEqual(x + largura, tela[0], tela)
            self.assertLessEqual(y + editor.BARRA_DE_TITULO + altura,
                                 tela[1] - BARRA_REAL_DO_WINDOWS, tela)
            self.assertLessEqual((largura, altura), editor.DESEJADO)
        self.assertEqual(editor.geometria((1920, 1080))[:2], editor.DESEJADO)


class NaTelaDele(unittest.TestCase):
    """A Oficina de verdade, invisivel (alfa zero), no tamanho da tela dele."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError as erro:                    # sem tela (CI Linux)
            raise unittest.SkipTest(f"sem display: {erro}") from erro
        cls.raiz.withdraw()
        cls.oficina = editor.Oficina(cls.raiz)
        cls.oficina.attributes("-alpha", 0.0)
        largura, altura, x, y = editor.geometria(TELA_DELE)
        cls.oficina.geometry(f"{largura}x{altura}+{x}+{y}")
        cls.oficina.update()

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def _todos(self):
        pilha = list(self.oficina.winfo_children())
        while pilha:
            w = pilha.pop()
            pilha.extend(w.winfo_children())
            yield w

    def _visiveis(self):
        return (w for w in self._todos() if w.winfo_ismapped())

    def test_nada_sumiu_por_falta_de_espaco(self):
        """Sem espaco, o `pack` DESMAPEIA o que chegou por ultimo: o widget
        continua existindo e nao aparece em lugar nenhum."""
        sumidos = [(w.winfo_class(), str(w)) for w in self._todos()
                   if w.winfo_class() in INTERATIVOS and w.winfo_manager()
                   and w.master.winfo_ismapped() and not w.winfo_ismapped()]
        self.assertEqual(sumidos, [])

    def test_nada_espremido_nem_para_fora(self):
        janela = self.oficina
        base_x, base_y = janela.winfo_rootx(), janela.winfo_rooty()
        largura, altura = janela.winfo_width(), janela.winfo_height()
        problemas = []
        for w in self._visiveis():
            x, y = w.winfo_rootx() - base_x, w.winfo_rooty() - base_y
            if x + w.winfo_width() > largura + 1 or \
                    y + w.winfo_height() > altura + 1:
                problemas.append(("fora", w.winfo_class(), str(w)))
            if w.winfo_class() in INTERATIVOS and (
                    w.winfo_width() < w.winfo_reqwidth() - 1
                    or w.winfo_height() < w.winfo_reqheight() - 1):
                problemas.append(("espremido", w.winfo_class(), str(w)))
        self.assertEqual(problemas, [])

    def test_salvar_e_o_unico_primario(self):
        primarios = [w for w in self._visiveis()
                     if w.winfo_class() == "Button"
                     and w.cget("bg") == editor.estilo.VILA.acento]
        self.assertEqual([w.cget("text") for w in primarios],
                         ["💾 Salvar tudo"])

    def test_nao_encolhe_ate_espremer(self):
        """Mais estreita que o conteudo, o pack espremeria a direita."""
        minimo = int(self.oficina.wm_minsize()[0])
        self.assertGreaterEqual(minimo, min(self.oficina.winfo_reqwidth(),
                                            editor.geometria(TELA_DELE)[0]))


if __name__ == "__main__":
    unittest.main()
