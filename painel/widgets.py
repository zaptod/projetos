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

# O botao cuja acao esta rodando agora (ou None). So a thread da interface
# mexe nisto: e quem clica e quem desenha.
_EM_CURSO = None


def botao_em_curso():
    """O botao do painel que esta sendo clicado neste instante, se houver."""
    return _EM_CURSO


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

        # O TITULO FICA FORA DO CORPO de proposito. Enquanto ele era
        # empacotado dentro, `corpo` ficava "gerenciado por pack" e qualquer
        # pagina que quisesse `grid()` ali estourava com "cannot use geometry
        # manager grid ... which already has slaves managed by pack". O corpo
        # tem que chegar limpo para quem for usar.
        if titulo:
            faixa = tk.Frame(dentro, bg=self.tema.superficie)
            faixa.pack(fill="x", padx=ESPACO["normal"],
                       pady=(ESPACO["normal"], 0))
            self.secao(faixa, titulo).pack(anchor="w")

        corpo = tk.Frame(dentro, bg=self.tema.superficie)
        corpo.pack(fill="both", expand=True, padx=ESPACO["normal"],
                   pady=(ESPACO["meio"] if titulo else ESPACO["normal"],
                         ESPACO["normal"]))
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
        alvo = None

        def invocar():
            # Marca QUEM esta sendo clicado enquanto a acao roda: o
            # `Supervisor.rodar` desliga esse botao ate o processo acabar
            # (PNL-1). Tudo na thread da interface, entao basta um global.
            global _EM_CURSO
            anterior, _EM_CURSO = _EM_CURSO, alvo
            try:
                return acao()
            finally:
                _EM_CURSO = anterior

        alvo = tk.Button(
            pai, text=texto, command=invocar if acao else None,
            bg=fundo, fg=frente,
            activebackground=realce, activeforeground=frente,
            font=self.tema.letra("corpo", "bold" if tipo == "primario"
                                 else "normal"),
            relief="flat", bd=0,
            padx=ESPACO["meio"] if compacto else ESPACO["normal"],
            pady=2 if compacto else ESPACO["meio"],
            cursor="hand2", highlightthickness=0)
        # O <Leave> devolve a cor que o botao tinha ANTES do hover, e nao a
        # da criacao: a vista ativa da Oficina e pintada com `acento_fundo`
        # e perdia o destaque so de passar o mouse (PNL-18). Se alguem
        # repintou o botao durante o hover (o clique que ativa a vista), a
        # cor nova fica.
        def entrar(_e):
            atual = alvo.cget("bg")
            if atual != realce:
                alvo._bg_antes = atual                      # noqa: SLF001
            alvo.configure(bg=realce)

        def sair(_e):
            if alvo.cget("bg") == realce:
                alvo.configure(bg=getattr(alvo, "_bg_antes", fundo))

        alvo.bind("<Enter>", entrar)
        alvo.bind("<Leave>", sair)
        return alvo

    # ------------------------------------------------------ rolagem
    def rolavel(self, pai):
        """Uma pagina que ROLA quando nao cabe. Devolve o quadro de dentro.

        O `pack` corta em silencio: na tela dele (1366x768, ~650 px de
        conteudo) a Videos de Build perdia a tabela de VIDEOS PRONTOS sem
        erro nenhum (PNL-5). Aqui o quadro de dentro tem a largura da tela
        e, de altura, o MAIOR entre o que ele pede e o que a tela tem: com
        espaco sobrando, quem tem `expand` continua esticando; sem espaco,
        aparece a barra e a roda do mouse rola.
        """
        fundo = pai.cget("bg")
        moldura = tk.Frame(pai, bg=fundo)
        moldura.pack(fill="both", expand=True)
        tela = tk.Canvas(moldura, bg=fundo, highlightthickness=0, bd=0)
        barra = ttk.Scrollbar(moldura, orient="vertical", command=tela.yview)
        corpo = tk.Frame(tela, bg=fundo)
        janela = tela.create_window((0, 0), window=corpo, anchor="nw")
        tela.configure(yscrollcommand=barra.set)
        tela.pack(side="left", fill="both", expand=True)

        def ajustar(_e=None):
            largura, altura = tela.winfo_width(), tela.winfo_height()
            if largura <= 1:
                return
            pedida = corpo.winfo_reqheight()
            tela.itemconfigure(janela, width=largura,
                               height=max(altura, pedida))
            tela.configure(scrollregion=(0, 0, largura, max(altura, pedida)))
            if pedida > altura:
                if not barra.winfo_ismapped():
                    barra.pack(side="right", fill="y", before=tela)
            elif barra.winfo_ismapped():
                barra.pack_forget()
                tela.yview_moveto(0)

        tela.bind("<Configure>", ajustar, add="+")
        corpo.bind("<Configure>", ajustar, add="+")

        def rolar(evento):
            try:
                if not tela.winfo_exists() or not tela.winfo_ismapped():
                    return
                alvo = evento.widget
                caminho = str(alvo)
                if not caminho.startswith(str(tela)):
                    return
                # Tabela, texto e lista rolam a si mesmos.
                if hasattr(alvo, "winfo_class") and alvo.winfo_class() in (
                        "Treeview", "Text", "Listbox", "TCombobox"):
                    return
                if corpo.winfo_reqheight() <= tela.winfo_height():
                    return
                tela.yview_scroll(int(-evento.delta / 120) or
                                  (-1 if evento.delta > 0 else 1), "units")
            except tk.TclError:
                pass

        tela.bind_all("<MouseWheel>", rolar, add="+")
        corpo.tela = tela            # noqa: SLF001 — o teste mede a rolagem
        corpo.ajustar = ajustar      # noqa: SLF001
        return corpo

    # ------------------------------------------------------ entrada
    def campo(self, pai, rotulo: str, largura: int = 12):
        """Rotulo + caixa de texto. Devolve (moldura, variavel)."""
        fundo = pai.cget("bg")
        moldura = tk.Frame(pai, bg=fundo)
        self.rotulo(moldura, rotulo, cor="texto_fraco", bg=fundo).pack(
            side="left", padx=(0, ESPACO["meio"]))
        variavel = tk.StringVar()
        tk.Entry(moldura, textvariable=variavel, width=largura,
                 bg=self.tema.superficie_alta, fg=self.tema.texto,
                 insertbackground=self.tema.texto, relief="flat",
                 font=self.tema.letra("corpo"),
                 highlightthickness=1, highlightbackground=self.tema.borda,
                 highlightcolor=self.tema.acento).pack(side="left", ipady=3)
        return moldura, variavel

    def combo(self, pai, valores: list, inicial: str = "", largura: int = 12):
        alvo = ttk.Combobox(pai, values=list(valores), width=largura,
                            state="readonly", font=self.tema.letra("corpo"))
        alvo.set(inicial or (valores[0] if valores else ""))
        return alvo

    def marcador(self, pai, texto: str):
        """Caixa de marcar. Devolve (widget, variavel)."""
        fundo = pai.cget("bg")
        variavel = tk.BooleanVar()
        alvo = tk.Checkbutton(
            pai, text=texto, variable=variavel, bg=fundo, fg=self.tema.texto,
            selectcolor=self.tema.superficie_alta,
            activebackground=fundo, activeforeground=self.tema.texto,
            font=self.tema.letra("corpo"), relief="flat", bd=0,
            highlightthickness=0, cursor="hand2")
        return alvo, variavel

    def zona_de_perigo(self, pai, aviso: str):
        """Bloco vermelho para o que NAO tem volta.

        Cor propria, e nao so um botao vermelho no meio dos outros: apagar o
        banco do jogo perde os personagens que os videos criaram, e isso
        merece uma area que se le como area, nao como mais um botao.
        """
        fora = tk.Frame(pai, bg=self.tema.erro)
        dentro = tk.Frame(fora, bg=self.tema.erro_fundo)
        dentro.pack(fill="both", expand=True, padx=BORDA, pady=BORDA)
        corpo = tk.Frame(dentro, bg=self.tema.erro_fundo)
        corpo.pack(fill="both", expand=True, padx=ESPACO["normal"],
                   pady=ESPACO["normal"])
        self.rotulo(corpo, "ZONA DE PERIGO", papel="secao", peso="bold",
                    cor="erro", bg=self.tema.erro_fundo).pack(anchor="w")
        self.rotulo(corpo, aviso, cor="texto_fraco",
                    bg=self.tema.erro_fundo, wraplength=760,
                    justify="left").pack(anchor="w",
                                         pady=(ESPACO["pouco"],
                                               ESPACO["meio"]))
        fora.corpo = corpo          # noqa: SLF001
        return fora

    # ---------------------------------------------------------- tabela
    def tabela(self, pai, colunas: list, altura: int = 12,
               estica: str | None = None):
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
        # UMA coluna absorve a sobra de espaco, senao ela vira faixa morta a
        # direita. Qual delas e escolha de quem monta: na lista de publicar a
        # que precisa e o TITULO, e deixar a ultima esticando truncava o
        # nome do video enquanto sobrava espaco na coluna do TikTok.
        if colunas:
            alvo.column(estica or colunas[-1][0], stretch=True)
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


__all__ = ["Oficina", "botao_em_curso"]
