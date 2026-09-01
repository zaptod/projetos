# -*- coding: utf-8 -*-
"""Os componentes. Um lugar so para cada coisa que aparece na tela.

O QUE ISTO SUBSTITUI, contado no painel antigo: 9 construcoes de `Treeview`
com 9 lacos de coluna identicos, 19 `Combobox`, 74 `tk.Label` com estilo
escrito na linha, 6 implementacoes byte-a-byte iguais de "pega a linha
selecionada ou avisa", 5 variantes de "abrir a pasta" e 4 de "assistir o
video com reserva celular/normal".

Nao e so repeticao: e onde os defeitos se escondem. A tabela do Fluxo nasceu
com dois ids de coluna REPETIDOS e por isso duas colunas ficavam sem titulo e
com 200px de largura padrao, empurrando o cabecalho para fora do lugar. Isso
sobreviveu meses porque cada tabela era montada na mao. `tabela()` recusa
id repetido na cara, com o nome do repetido na mensagem.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .estilo import BORDA, ESPACO, Tema


class Oficina:
    """Fabrica de widgets amarrada a UM tema.

    Existe como objeto, e nao como funcoes soltas, porque o tema tem que
    viajar junto: a Vila e as janelas de trabalho tem caras diferentes e
    nenhum widget deve precisar saber qual das duas esta em uso.
    """

    def __init__(self, tema: Tema):
        self.tema = tema

    # ------------------------------------------------------------ texto
    def rotulo(self, pai, texto: str, *, papel: str = "corpo",
               cor: str = "texto", peso: str = "normal", **kw):
        """Um texto. `papel` diz o TAMANHO, `cor` diz o SIGNIFICADO."""
        fundo = kw.pop("bg", None) or pai.cget("bg")
        return tk.Label(pai, text=texto, bg=fundo,
                        fg=getattr(self.tema, cor),
                        font=self.tema.letra(papel, peso),
                        anchor=kw.pop("anchor", "w"), **kw)

    def titulo(self, pai, texto: str):
        etiqueta = self.rotulo(pai, texto, papel="titulo", peso="bold")
        etiqueta.pack(anchor="w", padx=ESPACO["secao"],
                      pady=(ESPACO["muito"], ESPACO["normal"]))
        return etiqueta

    def secao(self, pai, texto: str):
        """O rotulo de um grupo: maiusculas pequenas, cor DISCRETA.

        Nao usa o acento de proposito. A regra do tema e que o acento marca
        o que e clicavel ou esta ativo; se todo titulo de cartao tambem for
        roxo, tres cartoes passam a competir com o item de menu ativo e o
        acento deixa de querer dizer alguma coisa. O que separa o rotulo do
        conteudo aqui e a CAIXA ALTA e o peso, nao a cor.
        """
        return self.rotulo(pai, texto.upper(), papel="secao", peso="bold",
                           cor="texto_fraco")

    def legenda(self, pai, texto: str, cor: str = "texto_fraco"):
        return self.rotulo(pai, texto, papel="legenda", cor=cor)

    # ---------------------------------------------------------- cartao
    def cartao(self, pai, titulo: str = ""):
        """Superficie com BORDA, nao com bloco de cor mais clara.

        Quatro tons empilhados viram uma mancha de longe; uma borda de 1px
        sobre o mesmo fundo separa sem pesar. Foi a mudanca isolada que mais
        limpou a tela.
        """
        fora = tk.Frame(pai, bg=self.tema.borda)
        dentro = tk.Frame(fora, bg=self.tema.superficie)
        dentro.pack(fill="both", expand=True, padx=BORDA, pady=BORDA)
        corpo = tk.Frame(dentro, bg=self.tema.superficie)
        corpo.pack(fill="both", expand=True, padx=ESPACO["normal"],
                   pady=ESPACO["normal"])
        if titulo:
            self.secao(corpo, titulo).pack(anchor="w",
                                           pady=(0, ESPACO["meio"]))
        fora.corpo = corpo          # noqa: SLF001 — quem empacota usa isto
        return fora

    # ---------------------------------------------------------- botoes
    def botao(self, pai, texto: str, acao=None, *, tipo: str = "normal",
              compacto: bool = False):
        """`tipo`: normal | primario | perigo. Um so por tela e primario.

        `compacto` e para botao que vive dentro de uma faixa (a do console),
        onde cada pixel de altura sai do conteudo.
        """
        cores = {
            "normal": (self.tema.superficie_alta, self.tema.texto,
                       self.tema.borda_forte),
            "primario": (self.tema.acento, "#15121d", self.tema.acento_forte),
            "perigo": (self.tema.erro_fundo, self.tema.erro, self.tema.erro),
        }[tipo]
        fundo, frente, realce = cores
        alvo = tk.Button(
            pai, text=texto, command=acao, bg=fundo, fg=frente,
            activebackground=realce, activeforeground=frente,
            font=self.tema.letra("corpo", "bold" if tipo == "primario"
                                 else "normal"),
            relief="flat", bd=0,
            padx=ESPACO["meio"] if compacto else ESPACO["normal"],
            pady=2 if compacto else ESPACO["meio"],
            cursor="hand2", highlightthickness=0)
        alvo.bind("<Enter>", lambda _e: alvo.configure(bg=realce))
        alvo.bind("<Leave>", lambda _e: alvo.configure(bg=fundo))
        return alvo

    # ---------------------------------------------------------- tabela
    def tabela(self, pai, colunas: list, altura: int = 12):
        """Treeview a partir de [(id, titulo, largura, alinhamento)].

        RECUSA ID REPETIDO. O Tk nao reclama: ele cria as colunas e depois
        resolve `heading("x")` pela PRIMEIRA com aquele nome, deixando a
        segunda sem titulo e com 200px de largura padrao. O sintoma e um
        cabecalho deslocado e a ultima coluna cortada -- exatamente o que a
        tabela do Fluxo fazia, sem erro nenhum, ate 01/09/2026.
        """
        ids = [c[0] for c in colunas]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            raise ValueError(
                f"id de coluna repetido: {', '.join(repetidos)}. O Tk aceita "
                "e depois desalinha o cabecalho em silencio — use ids "
                "distintos (ex.: 'id' e 'nome' em vez de repetir 'build').")

        alvo = ttk.Treeview(pai, columns=ids, show="headings", height=altura)
        for identificador, titulo, largura, alinhamento in colunas:
            alvo.heading(identificador, text=titulo, anchor=alinhamento)
            alvo.column(identificador, width=largura, anchor=alinhamento,
                        stretch=False)
        # A ultima estica: sobra de espaco vai para ela em vez de virar uma
        # faixa morta a direita.
        if colunas:
            alvo.column(colunas[-1][0], stretch=True)
        return alvo

    def largura_cabe(self, colunas: list, disponivel: int) -> bool:
        """As colunas cabem? Chamado pelo teste, para o estouro nao voltar."""
        return sum(c[2] for c in colunas) <= disponivel

    # ------------------------------------------------------- selecao
    def selecionado(self, tabela, aviso: str):
        """A linha selecionada, ou None depois de avisar.

        Eram seis copias byte-a-byte iguais disto, uma por pagina.
        """
        escolha = tabela.selection()
        if not escolha:
            messagebox.showinfo("Escolha uma linha", aviso)
            return None
        return escolha[0]

    # ------------------------------------------------------ aparencia ttk
    def aplicar_ttk(self, raiz) -> None:
        """Combobox, Treeview e barras seguindo o tema."""
        t = self.tema
        estilo = ttk.Style(raiz)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        estilo.configure("TCombobox", fieldbackground=t.superficie_alta,
                         background=t.superficie_alta, foreground=t.texto,
                         arrowcolor=t.texto_fraco, bordercolor=t.borda,
                         lightcolor=t.borda, darkcolor=t.borda)
        estilo.map("TCombobox", fieldbackground=[("readonly",
                                                  t.superficie_alta)])

        estilo.configure("Treeview", background=t.superficie,
                         fieldbackground=t.superficie, foreground=t.texto,
                         bordercolor=t.borda, borderwidth=0,
                         rowheight=t.densidade, font=t.letra("corpo"))
        estilo.configure("Treeview.Heading", background=t.fundo,
                         foreground=t.texto_fraco, relief="flat",
                         font=t.letra("legenda", "bold"))
        estilo.map("Treeview.Heading",
                   background=[("active", t.superficie_alta)])
        estilo.map("Treeview", background=[("selected", t.acento_fundo)],
                   foreground=[("selected", t.texto)])

        estilo.configure("Vertical.TScrollbar", background=t.superficie_alta,
                         troughcolor=t.fundo, bordercolor=t.fundo,
                         arrowcolor=t.texto_apagado)
        estilo.configure("Horizontal.TProgressbar", background=t.acento,
                         troughcolor=t.superficie, bordercolor=t.fundo,
                         lightcolor=t.acento, darkcolor=t.acento)


__all__ = ["Oficina"]
