# -*- coding: utf-8 -*-
"""Pagina OFICINA DE SPRITES: da folha do ChatGPT a peca do palco.

Pedido do Adrian (28/09/2026, `builds/sprites-animados` = "limpar depois"):
"Eu consegui gerar alguns spritesheet bons, veja o arquivo piriri.py [...]
mas como o processo e moroso quero apenas uma interface grafica que facilite
ao maximo esse processo, como essa limpeza de fundo, saneamento e auto
fatiamento de frames, identificacao e outras coisas uteis."

Fica no lugar da Oficina da Vila em pixel (aposentada no mesmo dia,
`painel-e-vila/aposentar-vila-pixel`), numa janela propria: processar uma
folha de 1942x809 e trabalho de meio segundo, e a Vila nao deve engasgar
por isso. A cara e a quente (`painel-e-vila/cara-da-oficina` = "quente").

COMO SE USA, de cima para baixo na coluna da esquerda: abrir (ou soltar o
arquivo na janela), conferir o fundo, o despill, o saneamento e a grade
achada, identificar a peca e exportar. Cada mudanca refaz a previa sozinha
(meio segundo depois do ultimo ajuste), e Ctrl+Z desfaz.

Na folha: arraste uma linha da grade para ajusta-la; clique numa celula
para ignorar (ou voltar) o quadro; o conta-gotas pega a cor do fundo ou da
franja. Na animacao: clique para escolher a ancora do palco.

Nada daqui escreve fora da biblioteca do palco, e so quando se aperta
EXPORTAR. As contas estao em `painel/sprites/` (sem Tk), com teste.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import arrastar, estilo
from ..processos import Periodico, agora_ms
from ..sprites import exportar, limpeza, medidas
from ..sprites.receita import Receita, processar

ESPERA_MS = 350          # ultimo ajuste -> previa
RELOGIO_MS = 60
HISTORICO_MAX = 100
LARGURA_CONTROLES = 312
LARGURA_DIREITA = 284

ROTULOS_FUNDO = {"auto": "automático", "nenhum": "já transparente",
                 "bordas": "preencher das bordas", "cor": "cor-chave"}
ROTULOS_FATIAR = {"auto": "automático", "linhas": "linhas desenhadas",
                  "vaos": "vãos vazios", "uniforme": "colunas × linhas",
                  "componentes": "por desenho"}
ROTULOS_ANCORA = {"massa": "centro de massa", "caixa": "centro da caixa",
                  "pe": "pé (base)"}
VISTAS = {"limpa": "Limpa + grade", "original": "Original",
          "folha": "Folha final"}
FUNDOS_PREVIA = {"xadrez": "xadrez", "escuro": "escuro", "claro": "claro"}
PERTO_PX = 6             # distancia da linha da grade que vira "pegar"

# campo da receita -> tipo (as variaveis da tela sao texto/numero do Tk)
CAMPOS = {"fundo": str, "tolerancia": float, "suavidade": float,
          "descontaminar": bool, "alfa_minimo": int, "despill": float,
          "tolerancia_franja": float, "apagar_linhas": bool, "ilha_min": int,
          "fatiar": str, "colunas": int, "linhas": int, "juntar": int,
          "ignorar_vazias": bool, "ancora": str, "margem": int,
          "largura_max": int, "espelhar": bool, "colunas_saida": int}
MUDAM_A_GRADE = {"fatiar", "colunas", "linhas", "juntar"}


class Pagina:
    chave = "oficina"
    rotulo = "Oficina de sprites"
    icone = "🎨"

    def __init__(self, casca):
        self.casca = casca
        self.o = casca.oficina
        self.t = casca.tema
        self.caminho: Path | None = None
        self.original = None
        self.receita = Receita()
        self.historico = [self.receita]
        self.posicao = 0
        self.resultado = None
        self.medidas = None
        self.vista = "limpa"
        self.fundo_previa = "xadrez"
        self._vars = {}
        self._ident = {}
        self._fotos = {}
        self._carregando = False
        self._rodando = False
        self._pendente = False
        self._prazo = None
        self._prazo_desenho = None
        self._gotas = None           # "fundo" | "franja" quando o conta-gotas
        self._arrasto = None
        self._mapa = None            # (escala, dx, dy) folha -> tela
        self._grade_tela = None      # xs, ys que estao na tela
        self._quadro = 0
        self._tocando = True
        self._animacao = None
        self._relogio = None
        self._soltura = None
        self._visivel = False
        self._ancora_palco = None    # (x, y) na celula; None = a do alinhamento

    # ================================================================ montar
    def construir(self, pai) -> None:
        pai.grid_columnconfigure(1, weight=1)
        pai.grid_rowconfigure(1, weight=1)
        self._barra(pai)

        esquerda = tk.Frame(pai, bg=self.t.fundo, width=LARGURA_CONTROLES)
        esquerda.grid(row=1, column=0, sticky="ns",
                      padx=(estilo.ESPACO["normal"], 0),
                      pady=(0, estilo.ESPACO["meio"]))
        esquerda.grid_propagate(False)
        esquerda.pack_propagate(False)
        corpo = self._rolavel(esquerda)
        self._controles(corpo)

        centro = tk.Frame(pai, bg=self.t.fundo)
        centro.grid(row=1, column=1, sticky="nsew",
                    padx=estilo.ESPACO["normal"],
                    pady=(0, estilo.ESPACO["meio"]))
        self._area_da_folha(centro)

        direita = tk.Frame(pai, bg=self.t.fundo, width=LARGURA_DIREITA)
        direita.grid(row=1, column=2, sticky="ns",
                     padx=(0, estilo.ESPACO["normal"]),
                     pady=(0, estilo.ESPACO["meio"]))
        direita.pack_propagate(False)
        corpo_d = self._rolavel(direita)
        self._coluna_direita(corpo_d)

        self._carregar_campos(self.receita)
        self._relogio = Periodico(self.casca, RELOGIO_MS, self._bater)
        raiz = pai.winfo_toplevel()
        raiz.bind("<Control-z>", lambda _e: self.desfazer(), add="+")
        raiz.bind("<Control-y>", lambda _e: self.refazer(), add="+")
        self._soltura = arrastar.aceitar(pai)

    def _rolavel(self, pai):
        """Coluna com barra: o `pack` corta em silencio o que nao cabe, e na
        tela de 768 px as secoes da esquerda nao cabem todas."""
        tela = tk.Canvas(pai, bg=self.t.fundo, highlightthickness=0, bd=0)
        barra = ttk.Scrollbar(pai, orient="vertical", command=tela.yview)
        corpo = tk.Frame(tela, bg=self.t.fundo)
        janela = tela.create_window((0, 0), window=corpo, anchor="nw")
        corpo.bind("<Configure>", lambda _e: tela.configure(
            scrollregion=tela.bbox("all")))
        tela.bind("<Configure>", lambda e: tela.itemconfigure(
            janela, width=e.width))
        tela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        tela.pack(side="left", fill="both", expand=True)

        def rolar(evento):
            tela.yview_scroll(int(-evento.delta / 120), "units")
        for alvo in (tela, corpo):
            alvo.bind("<Enter>", lambda _e: tela.bind_all("<MouseWheel>",
                                                          rolar))
            alvo.bind("<Leave>", lambda _e: tela.unbind_all("<MouseWheel>"))
        corpo.tela = tela            # noqa: SLF001 — o teste mede a rolagem
        return corpo

    def _barra(self, pai) -> None:
        barra = tk.Frame(pai, bg=self.t.fundo)
        barra.grid(row=0, column=0, columnspan=3, sticky="ew",
                   padx=estilo.ESPACO["normal"],
                   pady=(estilo.ESPACO["normal"], estilo.ESPACO["meio"]))
        self.o.botao(barra, "📂  Abrir…", self.escolher).pack(side="left")
        self.o.botao(barra, "Lote…", self.lote).pack(
            side="left", padx=(estilo.ESPACO["meio"], 0))
        self.btn_desfazer = self.o.botao(barra, "↶", self.desfazer,
                                         compacto=True)
        self.btn_desfazer.pack(side="left", padx=(estilo.ESPACO["muito"], 0))
        self.btn_refazer = self.o.botao(barra, "↷", self.refazer,
                                        compacto=True)
        self.btn_refazer.pack(side="left", padx=(estilo.ESPACO["pouco"], 0))
        self.o.botao(barra, "Receita…", self.abrir_receita,
                     compacto=True).pack(side="right")
        self.o.botao(barra, "Salvar receita", self.salvar_receita,
                     compacto=True).pack(side="right",
                                         padx=(0, estilo.ESPACO["meio"]))
        self.lbl_arquivo = self.o.legenda(
            barra, "solte um PNG ou JPG aqui, ou use Abrir")
        self.lbl_arquivo.pack(side="left", padx=estilo.ESPACO["muito"],
                              fill="x", expand=True)

    # -------------------------------------------------------- controles
    def _secao(self, pai, titulo: str, dica: str = "", largura: int = 260):
        cartao = self.o.cartao(pai, titulo)
        cartao.pack(fill="x", pady=(0, estilo.ESPACO["meio"]),
                    padx=(0, estilo.ESPACO["pouco"]))
        if dica:
            self.o.rotulo(cartao.corpo, dica, papel="legenda",
                          cor="texto_fraco", wraplength=largura,
                          justify="left").pack(anchor="w",
                                               pady=(0, estilo.ESPACO["pouco"]))
        return cartao.corpo

    def _linha(self, pai, rotulo: str):
        linha = tk.Frame(pai, bg=pai.cget("bg"))
        linha.pack(fill="x", pady=1)
        self.o.rotulo(linha, rotulo, papel="legenda", cor="texto_fraco",
                      width=13).pack(side="left")
        return linha

    def _escala(self, pai, rotulo: str, chave: str, de, ate, passo=1):
        linha = self._linha(pai, rotulo)
        variavel = tk.DoubleVar()
        tk.Scale(linha, variable=variavel, from_=de, to=ate, resolution=passo,
                 orient="horizontal", showvalue=True, length=150,
                 bg=pai.cget("bg"), fg=self.t.texto,
                 troughcolor=self.t.superficie_alta,
                 activebackground=self.t.acento, highlightthickness=0, bd=0,
                 sliderlength=14, width=10, font=self.t.letra("legenda"),
                 command=lambda _v: self._mudou(chave)).pack(
            side="left", fill="x", expand=True)
        self._vars[chave] = variavel

    def _combo(self, pai, rotulo: str, chave: str, rotulos: dict, alvo=None):
        linha = self._linha(pai, rotulo)
        caixa = self.o.combo(linha, list(rotulos.values()), largura=18)
        caixa.pack(side="left", fill="x", expand=True)
        variavel = tk.StringVar()
        de_rotulo = {v: k for k, v in rotulos.items()}

        def escolheu(_e=None):
            variavel.set(de_rotulo.get(caixa.get(), caixa.get()))
            if alvo is None:
                self._mudou(chave)
            else:
                alvo()

        caixa.bind("<<ComboboxSelected>>", escolheu)
        variavel.trace_add("write", lambda *_: caixa.set(
            rotulos.get(variavel.get(), variavel.get())))
        (self._vars if alvo is None else self._ident)[chave] = variavel
        return caixa

    def _marca(self, pai, texto: str, chave: str, alvo=None):
        widget, variavel = self.o.marcador(pai, texto)
        widget.configure(font=self.t.letra("legenda"),
                         command=(lambda: self._mudou(chave)) if alvo is None
                         else alvo)
        widget.pack(anchor="w")
        (self._vars if alvo is None else self._ident)[chave] = variavel

    def _numero(self, pai, rotulo: str, chave: str, de: int, ate: int):
        linha = self._linha(pai, rotulo)
        variavel = tk.StringVar()
        tk.Spinbox(linha, from_=de, to=ate, textvariable=variavel, width=6,
                   bg=self.t.superficie_alta, fg=self.t.texto,
                   buttonbackground=self.t.superficie_alta,
                   insertbackground=self.t.texto, relief="flat",
                   font=self.t.letra("corpo"), highlightthickness=1,
                   highlightbackground=self.t.borda,
                   command=lambda: self._mudou(chave)).pack(side="left")
        variavel.trace_add("write", lambda *_: self._mudou(chave))
        self._vars[chave] = variavel

    def _texto(self, pai, rotulo: str, chave: str, largura: int = 20):
        linha = self._linha(pai, rotulo)
        variavel = tk.StringVar()
        tk.Entry(linha, textvariable=variavel, width=largura,
                 bg=self.t.superficie_alta, fg=self.t.texto,
                 insertbackground=self.t.texto, relief="flat",
                 font=self.t.letra("corpo"), highlightthickness=1,
                 highlightbackground=self.t.borda,
                 highlightcolor=self.t.acento).pack(side="left", fill="x",
                                                    expand=True, ipady=2)
        variavel.trace_add("write", lambda *_: self._identidade_mudou())
        self._ident[chave] = variavel

    def _amostra(self, pai, rotulo: str, alvo: str):
        """Quadradinho da cor + conta-gotas + voltar ao automatico."""
        linha = self._linha(pai, rotulo)
        amostra = tk.Label(linha, text="", width=3, bg=self.t.superficie_alta,
                           relief="flat", bd=0, highlightthickness=1,
                           highlightbackground=self.t.borda)
        amostra.pack(side="left", padx=(0, estilo.ESPACO["meio"]), ipady=2)
        texto = self.o.legenda(linha, "auto")
        texto.pack(side="left")
        self.o.botao(linha, "auto", lambda: self._cor_automatica(alvo),
                     compacto=True).pack(side="right")
        self.o.botao(linha, "💧", lambda: self._conta_gotas(alvo),
                     compacto=True).pack(side="right",
                                         padx=(0, estilo.ESPACO["pouco"]))
        setattr(self, f"_amostra_{alvo}", (amostra, texto))

    def _controles(self, corpo) -> None:
        s = self._secao(corpo, "1 · Fundo",
                        "preencher das bordas não fura o brilho branco de "
                        "dentro do desenho")
        self._combo(s, "método", "fundo", ROTULOS_FUNDO)
        self._amostra(s, "cor do fundo", "fundo")
        self._escala(s, "tolerância", "tolerancia", 0, 128)
        self._escala(s, "suavidade", "suavidade", 0, 64)
        self._escala(s, "alfa mínimo", "alfa_minimo", 0, 64)
        self._marca(s, "descontaminar a borda (sem halo)", "descontaminar")

        s = self._secao(corpo, "2 · Despill",
                        "tira a franja da cor do fundo; o pixel ganha a cor "
                        "do desenho em volta")
        self._amostra(s, "cor da franja", "franja")
        self._escala(s, "força", "despill", 0, 1, 0.05)
        self._escala(s, "alcance", "tolerancia_franja", 0, 100)

        s = self._secao(corpo, "3 · Sanear")
        self._marca(s, "apagar as linhas de grade desenhadas", "apagar_linhas")
        self._escala(s, "ilha mínima px", "ilha_min", 0, 400)

        s = self._secao(corpo, "4 · Fatiar",
                        "na folha: arraste uma linha da grade; clique numa "
                        "célula para ignorar o quadro")
        self._combo(s, "como", "fatiar", ROTULOS_FATIAR)
        self._numero(s, "colunas", "colunas", 0, 64)
        self._numero(s, "linhas", "linhas", 0, 64)
        self._escala(s, "juntar px", "juntar", 0, 64)
        self._marca(s, "ignorar célula vazia", "ignorar_vazias")
        self.o.botao(s, "↺ Achar a grade de novo", self.redetectar,
                     compacto=True).pack(anchor="w",
                                         pady=(estilo.ESPACO["pouco"], 0))

        s = self._secao(corpo, "5 · Alinhar")
        self._combo(s, "âncora", "ancora", ROTULOS_ANCORA)
        self._numero(s, "margem px", "margem", 0, 64)
        self._numero(s, "largura máx", "largura_max", 0, 2048)
        self._numero(s, "colunas da folha", "colunas_saida", 0, 64)
        self._marca(s, "espelhar (o palco quer ➜ direita)", "espelhar")

        s = self._secao(corpo, "6 · Identificar",
                        "o nome vira o arquivo; tipo e elemento dizem ao "
                        "palco quando usar")
        self._texto(s, "nome", "nome")
        self._combo(s, "tipo", "tipo", {t: exportar.ROTULOS_DE_TIPO.get(t, t)
                                        for t in exportar.TIPOS},
                    alvo=self._identidade_mudou)
        self._combo(s, "elemento", "elemento",
                    {"": "—", **{e: e.capitalize()
                                 for e in exportar.elementos()}},
                    alvo=self._identidade_mudou)
        self._texto(s, "skill (opcional)", "skill")
        self._combo(s, "tier (evento)", "tier",
                    {t: (t or "—") for t in exportar.TIERS},
                    alvo=self._identidade_mudou)
        self._texto(s, "escala do raio", "escala_raio", 6)
        self._texto(s, "largura (m)", "tamanho_m", 6)
        self._marca(s, "luz somada (aditivo)", "aditivo",
                    alvo=self._identidade_mudou)
        self._marca(s, "girar com o objeto", "girar",
                    alvo=self._identidade_mudou)
        self._texto(s, "origem", "origem")
        self._texto(s, "autor", "autor")
        self._texto(s, "licença", "licenca")
        self._texto(s, "prova", "prova")
        padrao = exportar.Identidade()
        for chave in ("tipo", "elemento", "tier", "origem", "autor",
                      "licenca", "escala_raio", "tamanho_m"):
            self._ident[chave].set(str(getattr(padrao, chave)))
        self._ident["girar"].set(True)

    # ----------------------------------------------------- centro e direita
    def _area_da_folha(self, pai) -> None:
        topo = tk.Frame(pai, bg=self.t.fundo)
        topo.pack(fill="x", pady=(0, estilo.ESPACO["pouco"]))
        self._botoes_vista = {}
        for chave, texto in VISTAS.items():
            botao = self.o.botao(topo, texto,
                                 lambda c=chave: self.mostrar_vista(c),
                                 compacto=True)
            botao.pack(side="left", padx=(0, estilo.ESPACO["pouco"]))
            self._botoes_vista[chave] = botao
        self.cmb_fundo = self.o.combo(topo, list(FUNDOS_PREVIA.values()),
                                      "xadrez", largura=7)
        self.cmb_fundo.pack(side="right")
        self.cmb_fundo.bind("<<ComboboxSelected>>",
                            lambda _e: self._trocar_fundo_da_previa())
        self.lbl_cursor = self.o.legenda(topo, "")
        self.lbl_cursor.pack(side="right", padx=estilo.ESPACO["meio"])

        self.canvas = tk.Canvas(pai, bg=self.t.superficie,
                                highlightthickness=1,
                                highlightbackground=self.t.borda, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._pedir_desenho())
        self.canvas.bind("<Motion>", self._mover)
        self.canvas.bind("<ButtonPress-1>", self._apertar)
        self.canvas.bind("<B1-Motion>", self._arrastar)
        self.canvas.bind("<ButtonRelease-1>", self._soltar)
        self.lbl_estado = self.o.legenda(pai, "")
        self.lbl_estado.pack(fill="x", pady=(estilo.ESPACO["pouco"], 0))
        self._pintar_vista()

    def _coluna_direita(self, corpo) -> None:
        # A ordem e a de uso: ver tocar, exportar. As medidas vem por
        # ultimo -- na tela de 768 px o botao de exportar tem de caber sem
        # rolar, e as medidas podem ficar abaixo da dobra.
        s = self._secao(corpo, "Animação", "clique: âncora do palco · "
                        "botão direito: a automática", largura=224)
        self.anim = tk.Canvas(s, width=228, height=150,
                              bg=self.t.superficie_alta, highlightthickness=0,
                              bd=0, cursor="crosshair")
        self.anim.pack()
        self.anim.bind("<Button-1>", self._escolher_ancora)
        self.anim.bind("<Button-3>", lambda _e: self._ancora_automatica())
        controles = tk.Frame(s, bg=s.cget("bg"))
        controles.pack(fill="x", pady=(estilo.ESPACO["pouco"], 0))
        self.o.botao(controles, "◀", lambda: self._passo_manual(-1),
                     compacto=True).pack(side="left")
        self.btn_tocar = self.o.botao(controles, "⏸", self._alternar,
                                      compacto=True)
        self.btn_tocar.pack(side="left", padx=estilo.ESPACO["pouco"])
        self.o.botao(controles, "▶", lambda: self._passo_manual(1),
                     compacto=True).pack(side="left")
        self.lbl_quadro = self.o.legenda(controles, "—")
        self.lbl_quadro.pack(side="right")
        self._escala_fps(s)
        self._marca(s, "em laço (projétil, aura)", "laco",
                    alvo=self._identidade_mudou)
        self._ident["laco"].set(True)

        s = self._secao(corpo, "7 · Exportar para o palco")
        self.lbl_destino = self.o.rotulo(s, "", papel="legenda",
                                         cor="texto_fraco", justify="left",
                                         wraplength=224)
        self.lbl_destino.pack(anchor="w")
        self.lbl_problemas = self.o.rotulo(s, "", papel="legenda",
                                           cor="erro", justify="left",
                                           wraplength=224)
        self.lbl_problemas.pack(anchor="w", pady=(estilo.ESPACO["pouco"], 0))
        self.btn_exportar = self.o.botao(s, "Exportar para o palco",
                                         self.exportar, tipo="primario")
        self.btn_exportar.pack(fill="x", pady=(estilo.ESPACO["meio"], 0))

        s = self._secao(corpo, "Medidas", "antes → depois, contadas "
                        "(não é olho)", largura=224)
        self.lbl_medidas = self.o.rotulo(s, "abra uma folha", papel="legenda",
                                         cor="texto_fraco", justify="left",
                                         wraplength=224)
        self.lbl_medidas.pack(anchor="w")

    def _escala_fps(self, pai) -> None:
        linha = self._linha(pai, "fps")
        variavel = tk.DoubleVar(value=24)
        tk.Scale(linha, variable=variavel, from_=1, to=60, resolution=1,
                 orient="horizontal", length=140, bg=pai.cget("bg"),
                 fg=self.t.texto, troughcolor=self.t.superficie_alta,
                 activebackground=self.t.acento, highlightthickness=0, bd=0,
                 sliderlength=14, width=10, font=self.t.letra("legenda"),
                 command=lambda _v: self._fps_mudou()).pack(
            side="left", fill="x", expand=True)
        self._ident["fps"] = variavel

    # ============================================================== estado
    def ao_mostrar(self) -> None:
        self._visivel = True
        if self._relogio is not None:
            self._relogio.ligar()
        self._ligar_animacao()

    def ao_esconder(self) -> None:
        self._visivel = False
        for pulso in (self._relogio, self._animacao):
            if pulso is not None:
                pulso.desligar()

    def ocupada(self) -> bool:
        """Ha previa sendo feita ou esperando? (a prova de tela espera)"""
        return bool(self._rodando or self._pendente or self._prazo)

    def _bater(self) -> None:
        """O relogio da pagina (60 ms): arquivos soltos, previa e desenho
        que estavam esperando a hora. So a thread da interface passa aqui."""
        if self._soltura is not None:
            soltos = self._soltura.pegar()
            if soltos:
                self.abrir(soltos[0])
                if len(soltos) > 1:
                    self.casca._registrar(
                        f"[oficina] soltei {len(soltos)} arquivos: abri o "
                        "primeiro. Para os outros, use Lote…", "saida")
        agora = agora_ms()
        if self._prazo is not None and agora >= self._prazo:
            self._prazo = None
            self._confirmar()
        if self._prazo_desenho is not None and agora >= self._prazo_desenho:
            self._prazo_desenho = None
            self._desenhar_folha()

    # ------------------------------------------------------------ receita
    def _carregar_campos(self, receita: Receita) -> None:
        self._carregando = True
        try:
            for chave, variavel in self._vars.items():
                valor = getattr(receita, chave)
                variavel.set(valor if not isinstance(variavel, tk.StringVar)
                             else str(valor))
        finally:
            self._carregando = False
        self._pintar_cores()

    def _receita_dos_campos(self, chave: str | None = None) -> Receita:
        mudancas = {}
        for nome, tipo in CAMPOS.items():
            variavel = self._vars.get(nome)
            if variavel is None:
                continue
            try:
                bruto = variavel.get()
                valor = tipo(round(float(bruto))) if tipo is int else \
                    tipo(bruto)
            except (ValueError, tk.TclError):
                valor = getattr(self.receita, nome)
            mudancas[nome] = valor
        if chave in MUDAM_A_GRADE:
            mudancas.update(xs=None, ys=None, excluidas=[])
        return self.receita.mudar(**mudancas)

    def _mudou(self, chave: str) -> None:
        if self._carregando:
            return
        self.receita = self._receita_dos_campos(chave)
        self._agendar()

    def _agendar(self) -> None:
        self._prazo = agora_ms() + ESPERA_MS
        self._pintar_estado("ajustando…")

    def _confirmar(self) -> None:
        """A mudanca assentou: vai para o historico e vira previa."""
        if self.receita != self.historico[self.posicao]:
            del self.historico[self.posicao + 1:]
            self.historico.append(self.receita)
            if len(self.historico) > HISTORICO_MAX:
                self.historico.pop(0)
            self.posicao = len(self.historico) - 1
        self._pintar_historico()
        self._processar()

    def _trocar_receita(self, receita: Receita, *, historico=True) -> None:
        self.receita = receita
        self._carregar_campos(receita)
        if historico:
            self._confirmar()
        else:
            self._processar()

    def desfazer(self) -> None:
        if self.posicao > 0:
            self.posicao -= 1
            self._trocar_receita(self.historico[self.posicao],
                                 historico=False)
            self._pintar_historico()

    def refazer(self) -> None:
        if self.posicao < len(self.historico) - 1:
            self.posicao += 1
            self._trocar_receita(self.historico[self.posicao],
                                 historico=False)
            self._pintar_historico()

    def redetectar(self) -> None:
        self._trocar_receita(self.receita.mudar(xs=None, ys=None,
                                                excluidas=[]))

    def _pintar_historico(self) -> None:
        pode_voltar = self.posicao > 0
        pode_ir = self.posicao < len(self.historico) - 1
        self.btn_desfazer.configure(
            fg=self.t.texto if pode_voltar else self.t.texto_apagado)
        self.btn_refazer.configure(
            fg=self.t.texto if pode_ir else self.t.texto_apagado)

    # ----------------------------------------------------------- cores
    def _conta_gotas(self, alvo: str) -> None:
        if self.original is None:
            return
        self._gotas = alvo
        self.canvas.configure(cursor="crosshair")
        if self.vista != "original":
            self.mostrar_vista("original")
        self._pintar_estado(f"conta-gotas: clique na cor {'do fundo' if alvo == 'fundo' else 'da franja'}")

    def _cor_automatica(self, alvo: str) -> None:
        chave = "cor_fundo" if alvo == "fundo" else "cor_franja"
        self._trocar_receita(self.receita.mudar(**{chave: None}))

    def _pintar_cores(self) -> None:
        estimada = self.resultado.fundo["cor"] if self.resultado else None
        franja = self.resultado.franja if self.resultado else None
        for alvo, escolhida, auto in (
                ("fundo", self.receita.cor_fundo, estimada),
                ("franja", self.receita.cor_franja, franja)):
            pares = getattr(self, f"_amostra_{alvo}", None)
            if not pares:
                continue
            amostra, texto = pares
            cor = escolhida or auto
            if cor:
                amostra.configure(bg="#%02x%02x%02x" % tuple(int(c) for c in
                                                              cor[:3]))
                texto.configure(text=("escolhida " if escolhida else "auto ")
                                + "(%d, %d, %d)" % tuple(cor[:3]))
            else:
                amostra.configure(bg=self.t.superficie_alta)
                texto.configure(text="auto")

    # ------------------------------------------------------------ arquivos
    def escolher(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Abrir folha de sprites",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp"),
                       ("Todos", "*.*")])
        if caminho:
            self.abrir(caminho)

    def abrir(self, caminho) -> bool:
        caminho = Path(caminho)
        try:
            imagem = limpeza.abrir(caminho)
        except Exception as erro:                            # noqa: BLE001
            self.casca._registrar(f"[oficina] não abri {caminho.name}: "
                                  f"{erro}", "erro")
            return False
        self.caminho = caminho
        self.original = limpeza.para_array(imagem)
        self.resultado = None
        self.medidas = None
        self._ancora_palco = None
        self._quadro = 0
        self.lbl_arquivo.configure(
            text=f"{caminho.name}  ·  {imagem.width}×{imagem.height}",
            fg=self.t.texto)
        if not self._ident["nome"].get().strip():
            self._ident["nome"].set(exportar.slug(caminho.stem))
        self._trocar_receita(self.receita.mudar(xs=None, ys=None,
                                                excluidas=[]))
        return True

    def salvar_receita(self) -> None:
        caminho = filedialog.asksaveasfilename(
            title="Salvar receita", defaultextension=".json",
            filetypes=[("Receita", "*.json")])
        if caminho:
            self.receita.salvar(caminho)
            self.casca._registrar(f"[oficina] receita salva em {caminho}",
                                  "fim")

    def abrir_receita(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Abrir receita", filetypes=[("Receita", "*.json")])
        if not caminho:
            return
        try:
            receita = Receita.ler(caminho)
        except (OSError, ValueError) as erro:
            self.casca._registrar(f"[oficina] receita ruim: {erro}", "erro")
            return
        self._trocar_receita(receita)

    def lote(self) -> None:
        """A MESMA receita (sem a grade feita a mao) em varias folhas. Cada
        uma sai limpa numa pasta, com as medidas ao lado -- o palco so
        recebe o que foi identificado e exportado uma a uma."""
        arquivos = filedialog.askopenfilenames(
            title="Folhas para o lote",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")])
        if not arquivos:
            return
        pasta = filedialog.askdirectory(
            title="Onde salvar as folhas limpas",
            initialdir=str(Path(arquivos[0]).parent))
        if not pasta:
            return
        receita = self.receita.para_lote()
        self.casca._registrar(f">>> lote: {len(arquivos)} folha(s) → {pasta}",
                              "cmd")

        def trabalho():
            from ..sprites.lote import limpar_lote
            return limpar_lote(arquivos, receita, pasta)

        self.casca.supervisor.tarefa(trabalho, self._lote_pronto,
                                     rotulo="lote de sprites")

    def _lote_pronto(self, valor) -> None:
        if isinstance(valor, dict) and valor.get("erro"):
            self.casca._registrar(f"[oficina] lote falhou: {valor['erro']}",
                                  "erro")
            return
        for linha in valor:
            self.casca._registrar(
                f"[oficina] {linha['arquivo']}: {linha['resumo']}",
                "erro" if linha.get("erro") else "saida")
        self.casca._registrar("[oficina] lote pronto.", "fim")

    # ---------------------------------------------------------- previa
    def _processar(self) -> None:
        if self.original is None:
            self._pintar_estado("")
            return
        if self._rodando:
            self._pendente = True
            return
        self._rodando = True
        self._pendente = False
        original, receita = self.original, self.receita
        self._pintar_estado("processando…")

        def trabalho():
            res = processar(original, receita)
            return {"res": res, "medidas": medidas.medir(res, receita),
                    "receita": receita}

        self.casca.supervisor.tarefa(trabalho, self._pronto,
                                     rotulo="oficina de sprites")

    def _pronto(self, valor) -> None:
        self._rodando = False
        if isinstance(valor, dict) and valor.get("erro"):
            self._pintar_estado(f"erro: {valor['erro']}", "erro")
            self.casca._registrar(f"[oficina] {valor['erro']}", "erro")
        else:
            self.resultado = valor["res"]
            self.medidas = valor["medidas"]
            self._fotos.clear()
            self._quadro = min(self._quadro,
                               max(0, len(self.resultado.caixas) - 1))
            self._pintar_cores()
            self._pintar_medidas()
            self._desenhar_folha()
            self._desenhar_quadro()
            self._identidade_mudou()
            self._pintar_estado(self._descricao())
        if self._pendente:
            self._processar()

    def _descricao(self) -> str:
        r = self.resultado
        if r is None:
            return ""
        grade = (f"grade {r.grade.colunas}×{r.grade.linhas} ({r.modo_fatiar})"
                 if r.grade else "por desenho")
        return (f"fundo: {ROTULOS_FUNDO.get(r.fundo['metodo'])} · {grade} · "
                f"{len(r.caixas)} quadros · célula {r.alinhado.celula[0]}×"
                f"{r.alinhado.celula[1]} · folha {r.folha.shape[1]}×"
                f"{r.folha.shape[0]}")

    def _pintar_estado(self, texto: str, cor: str = "texto_fraco") -> None:
        self.lbl_estado.configure(text=texto, fg=getattr(self.t, cor))

    def _pintar_medidas(self) -> None:
        m = self.medidas
        if not m:
            self.lbl_medidas.configure(text="abra uma folha")
            return
        f = m["franja"]
        linhas = [
            f"quadros: {m['quadros']}",
            f"linhas de grade: {m['linhas_de_grade']['antes']} → "
            f"{m['linhas_de_grade']['folha']}",
            f"px nas faixas da grade: {m['px_nas_faixas']['antes']} → "
            f"{m['px_nas_faixas']['depois']}",
            f"franja forte: {f['antes']['visivel'] + f['antes']['oculta']} → "
            f"{f['folha']['visivel'] + f['folha']['oculta']} px",
            f"pontinhos: {m['pontinhos']['antes']} → "
            f"{m['pontinhos']['folha']}",
            f"buracos no desenho: {m['buracos']}",
            f"âncoras: ±{m['ancoras_desvio_px']:.1f} px",
        ]
        self.lbl_medidas.configure(text="\n".join(linhas), fg=self.t.texto)

    # ------------------------------------------------------ desenho: folha
    def mostrar_vista(self, vista: str) -> None:
        self.vista = vista
        self._pintar_vista()
        self._desenhar_folha()

    def _pintar_vista(self) -> None:
        for chave, botao in self._botoes_vista.items():
            ativo = chave == self.vista
            botao.configure(bg=self.t.acento_fundo if ativo
                            else self.t.superficie_alta,
                            fg=self.t.acento_forte if ativo else self.t.texto)

    def _trocar_fundo_da_previa(self) -> None:
        de_rotulo = {v: k for k, v in FUNDOS_PREVIA.items()}
        self.fundo_previa = de_rotulo.get(self.cmb_fundo.get(), "xadrez")
        self._fotos.clear()
        self._desenhar_folha()
        self._desenhar_quadro()

    def _pedir_desenho(self) -> None:
        self._prazo_desenho = agora_ms() + 80

    def _imagem_da_vista(self):
        r = self.resultado
        if r is None:
            return self.original
        return {"limpa": r.limpo, "original": r.original,
                "folha": r.folha}[self.vista]

    def _fundo(self, tamanho):
        from PIL import Image, ImageDraw
        t = self.t
        if self.fundo_previa == "escuro":
            return Image.new("RGBA", tamanho, _rgb(t.console_fundo))
        if self.fundo_previa == "claro":
            return Image.new("RGBA", tamanho, _rgb(t.texto))
        img = Image.new("RGBA", tamanho, _rgb(t.superficie))
        d = ImageDraw.Draw(img)
        lado = 8
        cor = _rgb(t.superficie_alta)
        for y in range(0, tamanho[1], lado):
            for x in range((y // lado) % 2 * lado, tamanho[0], lado * 2):
                d.rectangle([x, y, x + lado - 1, y + lado - 1], fill=cor)
        return img

    def _composto(self, arr, tamanho):
        from PIL import Image
        img = limpeza.para_imagem(arr)
        if img.size != tamanho:
            img = img.resize(tamanho, Image.LANCZOS if tamanho[0] < img.width
                             else Image.NEAREST)
        fundo = self._fundo(tamanho)
        fundo.alpha_composite(img)
        return fundo

    def _desenhar_folha(self) -> None:
        from PIL import ImageTk
        c = self.canvas
        c.delete("all")
        arr = self._imagem_da_vista()
        largura = max(1, c.winfo_width() - 2)
        altura = max(1, c.winfo_height() - 2)
        if arr is None:
            c.create_text(largura // 2, altura // 2,
                          text="Solte aqui uma folha de sprites (PNG ou JPG)"
                               "\nou use 📂 Abrir…",
                          fill=self.t.texto_fraco, justify="center",
                          font=self.t.letra("corpo"))
            self._mapa = None
            return
        h, w = arr.shape[:2]
        escala = min(largura / w, altura / h, 4.0)
        tamanho = (max(1, int(w * escala)), max(1, int(h * escala)))
        dx = (largura - tamanho[0]) // 2 + 1
        dy = (altura - tamanho[1]) // 2 + 1
        self._mapa = (escala, dx, dy)
        foto = ImageTk.PhotoImage(self._composto(arr, tamanho))
        self._fotos["folha"] = foto
        c.create_image(dx, dy, anchor="nw", image=foto)
        if self.resultado is not None:
            self._sobrepor()

    def _tela(self, x, y):
        escala, dx, dy = self._mapa
        return dx + x * escala, dy + y * escala

    def _folha(self, sx, sy):
        escala, dx, dy = self._mapa
        return (sx - dx) / escala, (sy - dy) / escala

    def _sobrepor(self) -> None:
        """A grade achada (ou as caixas), por cima da imagem."""
        r, c = self.resultado, self.canvas
        if self.vista == "original":
            for y0, y1 in r.linhas_h:
                a, b = self._tela(0, y0), self._tela(r.original.shape[1], y1)
                c.create_rectangle(*a, *b, outline="", fill=self.t.aviso,
                                   stipple="gray50")
            for x0, x1 in r.linhas_v:
                a, b = self._tela(x0, 0), self._tela(x1, r.original.shape[0])
                c.create_rectangle(*a, *b, outline="", fill=self.t.aviso,
                                   stipple="gray50")
            return
        if self.vista == "folha":
            cw, ch = r.alinhado.celula
            ax, ay = self._ancora_palco or r.alinhado.ancora
            for i in range(len(r.alinhado.quadros)):
                j, k = divmod(i, r.colunas)
                x0, y0 = self._tela(k * cw, j * ch)
                x1, y1 = self._tela((k + 1) * cw, (j + 1) * ch)
                c.create_rectangle(x0, y0, x1, y1, outline=self.t.borda_forte)
                px, py = self._tela(k * cw + ax, j * ch + ay)
                c.create_line(px - 5, py, px + 6, py, fill=self.t.info)
                c.create_line(px, py - 5, px, py + 6, fill=self.t.info)
            return
        usadas = set(r.caixas)
        if r.grade is not None:
            self._grade_tela = (list(r.grade.xs), list(r.grade.ys))
            for i, cel in enumerate(r.grade.celulas()):
                x0, y0 = self._tela(cel[0], cel[1])
                x1, y1 = self._tela(cel[2], cel[3])
                if cel in usadas:
                    n = r.caixas.index(cel) + 1
                    c.create_text(x0 + 4, y0 + 3, anchor="nw", text=str(n),
                                  fill=self.t.texto, font=self.t.letra("legenda"))
                elif i in r.grade.excluidas:
                    c.create_rectangle(x0, y0, x1, y1, outline="",
                                       fill=self.t.erro, stipple="gray25")
                    c.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                                  text="ignorada", fill=self.t.erro,
                                  font=self.t.letra("legenda"))
                else:
                    c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="vazia",
                                  fill=self.t.texto_apagado,
                                  font=self.t.letra("legenda"))
            altura, largura = r.limpo.shape[:2]
            for x in r.grade.xs[1:-1]:
                a, b = self._tela(x, 0), self._tela(x, altura)
                c.create_line(*a, *b, fill=self.t.acento, width=2,
                              tags=("linha",))
            for y in r.grade.ys[1:-1]:
                a, b = self._tela(0, y), self._tela(largura, y)
                c.create_line(*a, *b, fill=self.t.acento, width=2,
                              tags=("linha",))
        else:
            self._grade_tela = None
            for n, cel in enumerate(r.caixas, 1):
                x0, y0 = self._tela(cel[0], cel[1])
                x1, y1 = self._tela(cel[2], cel[3])
                c.create_rectangle(x0, y0, x1, y1, outline=self.t.acento)
                c.create_text(x0 + 3, y0 + 2, anchor="nw", text=str(n),
                              fill=self.t.texto, font=self.t.letra("legenda"))

    # --------------------------------------------------- mouse na folha
    def _linha_perto(self, sx, sy):
        if self._grade_tela is None or self._mapa is None or \
                self.vista != "limpa":
            return None
        xs, ys = self._grade_tela
        for i in range(1, len(xs) - 1):
            if abs(self._tela(xs[i], 0)[0] - sx) <= PERTO_PX:
                return ("x", i)
        for i in range(1, len(ys) - 1):
            if abs(self._tela(0, ys[i])[1] - sy) <= PERTO_PX:
                return ("y", i)
        return None

    def _mover(self, evento) -> None:
        if self._mapa is None:
            return
        x, y = self._folha(evento.x, evento.y)
        arr = self._imagem_da_vista()
        if arr is not None and 0 <= x < arr.shape[1] and 0 <= y < arr.shape[0]:
            px = arr[int(y), int(x)]
            self.lbl_cursor.configure(
                text=f"x {int(x)} · y {int(y)} · rgba{tuple(int(v) for v in px)}")
        if self._gotas:
            return
        perto = self._linha_perto(evento.x, evento.y)
        self.canvas.configure(cursor="sb_h_double_arrow" if perto and
                              perto[0] == "x" else "sb_v_double_arrow"
                              if perto else "")

    def _apertar(self, evento) -> None:
        if self._mapa is None:
            return
        x, y = self._folha(evento.x, evento.y)
        if self._gotas:
            self._pegar_cor(x, y)
            return
        perto = self._linha_perto(evento.x, evento.y)
        if perto:
            self._arrasto = perto
            return
        self._alternar_celula(x, y)

    def _pegar_cor(self, x, y) -> None:
        alvo, self._gotas = self._gotas, None
        self.canvas.configure(cursor="")
        if self.original is None:
            return
        h, w = self.original.shape[:2]
        xi, yi = int(min(max(x, 0), w - 1)), int(min(max(y, 0), h - 1))
        cor = [int(v) for v in self.original[yi, xi, :3]]
        if alvo == "fundo":
            fundo = self.receita.fundo
            if fundo in ("auto", "nenhum"):
                fundo = "bordas"
            nova = self.receita.mudar(cor_fundo=cor, fundo=fundo)
        else:
            nova = self.receita.mudar(cor_franja=cor)
        self._trocar_receita(nova)
        self.mostrar_vista("limpa")

    def _arrastar(self, evento) -> None:
        if not self._arrasto or self._grade_tela is None:
            return
        eixo, i = self._arrasto
        xs, ys = self._grade_tela
        x, y = self._folha(evento.x, evento.y)
        linhas = xs if eixo == "x" else ys
        valor = x if eixo == "x" else y
        linhas[i] = int(round(min(max(valor, linhas[i - 1] + 2),
                                  linhas[i + 1] - 2)))
        self.canvas.delete("linha")
        altura, largura = self.resultado.limpo.shape[:2]
        for xx in xs[1:-1]:
            a, b = self._tela(xx, 0), self._tela(xx, altura)
            self.canvas.create_line(*a, *b, fill=self.t.acento_forte,
                                    width=2, tags=("linha",))
        for yy in ys[1:-1]:
            a, b = self._tela(0, yy), self._tela(largura, yy)
            self.canvas.create_line(*a, *b, fill=self.t.acento_forte,
                                    width=2, tags=("linha",))

    def _soltar(self, _evento) -> None:
        if not self._arrasto or self._grade_tela is None:
            self._arrasto = None
            return
        self._arrasto = None
        xs, ys = self._grade_tela
        excluidas = sorted(self.resultado.grade.excluidas) \
            if self.resultado and self.resultado.grade else []
        self._trocar_receita(self.receita.mudar(xs=list(xs), ys=list(ys),
                                                excluidas=excluidas))

    def _alternar_celula(self, x, y) -> None:
        r = self.resultado
        if r is None or self.vista != "limpa":
            return
        if r.grade is not None:
            celulas = r.grade.celulas()
            excluidas = set(r.grade.excluidas)
            fixa = dict(xs=list(r.grade.xs), ys=list(r.grade.ys))
        else:
            celulas = r.caixas
            excluidas = set(self.receita.excluidas)
            fixa = {}
        for i, (x0, y0, x1, y1) in enumerate(celulas):
            if x0 <= x < x1 and y0 <= y < y1:
                excluidas ^= {i}
                self._trocar_receita(self.receita.mudar(
                    excluidas=sorted(excluidas), **fixa))
                return

    # --------------------------------------------------------- animacao
    def _ligar_animacao(self) -> None:
        if self._animacao is not None:
            self._animacao.desligar()
        fps = self._fps()
        self._animacao = Periodico(self.casca, max(16, int(1000 / fps)),
                                   self._tique)
        if self._visivel and self._tocando:
            self._animacao.ligar()

    def _fps(self) -> float:
        try:
            return min(60.0, max(1.0, float(self._ident["fps"].get())))
        except (KeyError, ValueError, tk.TclError):
            return 24.0

    def _fps_mudou(self) -> None:
        self._ligar_animacao()
        self._identidade_mudou()

    def _alternar(self) -> None:
        self._tocando = not self._tocando
        self.btn_tocar.configure(text="⏸" if self._tocando else "▶")
        self._ligar_animacao()

    def _passo_manual(self, passo: int) -> None:
        if self._tocando:
            self._alternar()
        self._avancar(passo)

    def _tique(self) -> None:
        self._avancar(1)

    def _avancar(self, passo: int) -> None:
        r = self.resultado
        if r is None or not r.alinhado.quadros:
            return
        n = len(r.alinhado.quadros)
        self._quadro = (self._quadro + passo) % n
        self._desenhar_quadro()

    def _mapa_anim(self):
        r = self.resultado
        cw, ch = r.alinhado.celula
        largura = int(self.anim.cget("width"))
        altura = int(self.anim.cget("height"))
        escala = min(largura / max(1, cw), altura / max(1, ch), 3.0)
        tamanho = (max(1, int(cw * escala)), max(1, int(ch * escala)))
        return escala, tamanho, ((largura - tamanho[0]) // 2,
                                 (altura - tamanho[1]) // 2)

    def _desenhar_quadro(self) -> None:
        from PIL import ImageTk
        a = self.anim
        a.delete("all")
        r = self.resultado
        if r is None or not r.alinhado.quadros:
            self.lbl_quadro.configure(text="—")
            return
        escala, tamanho, (dx, dy) = self._mapa_anim()
        chave = ("q", self._quadro, tamanho, self.fundo_previa)
        foto = self._fotos.get(chave)
        if foto is None:
            foto = ImageTk.PhotoImage(self._composto(
                r.alinhado.quadros[self._quadro], tamanho))
            self._fotos[chave] = foto
        a.create_image(dx, dy, anchor="nw", image=foto)
        ax, ay = self._ancora_palco or r.alinhado.ancora
        px, py = dx + ax * escala, dy + ay * escala
        a.create_line(px - 6, py, px + 7, py, fill=self.t.info)
        a.create_line(px, py - 6, px, py + 7, fill=self.t.info)
        self.lbl_quadro.configure(
            text=f"{self._quadro + 1}/{len(r.alinhado.quadros)}")

    def _escolher_ancora(self, evento) -> None:
        if self.resultado is None or not self.resultado.alinhado.quadros:
            return
        escala, tamanho, (dx, dy) = self._mapa_anim()
        x = (evento.x - dx) / escala
        y = (evento.y - dy) / escala
        cw, ch = self.resultado.alinhado.celula
        self._ancora_palco = (int(round(min(max(x, 0), cw))),
                              int(round(min(max(y, 0), ch))))
        self._desenhar_quadro()
        self._identidade_mudou()

    def _ancora_automatica(self) -> None:
        self._ancora_palco = None
        self._desenhar_quadro()
        self._identidade_mudou()

    # -------------------------------------------------------- identidade
    def identidade(self) -> exportar.Identidade:
        dados = {}
        for chave, variavel in self._ident.items():
            try:
                dados[chave] = variavel.get()
            except tk.TclError:
                continue
        for chave in ("fps", "escala_raio", "tamanho_m"):
            try:
                dados[chave] = float(str(dados.get(chave, "0")).replace(",",
                                                                        "."))
            except ValueError:
                dados[chave] = 0.0
        dados["ancora"] = list(self._ancora_palco) if self._ancora_palco \
            else None
        dados["fonte"] = str(self.caminho) if self.caminho else ""
        return exportar.Identidade.de_dict(dados)

    def _identidade_mudou(self) -> None:
        if not hasattr(self, "lbl_destino"):
            return
        ident = self.identidade()
        # a exportacao diz para onde vai (arma vai para armas/estilos/<slug>)
        self.lbl_destino.configure(text=exportar.rotulo_dos_arquivos(ident))
        quadros = len(self.resultado.alinhado.quadros) if self.resultado else 0
        celula = self.resultado.alinhado.celula if self.resultado else (0, 0)
        problemas = exportar.problemas(ident, quadros, celula)
        avisos = exportar.avisos(ident, celula)
        self.lbl_problemas.configure(
            text="\n".join([f"• {p}" for p in problemas]
                           + [f"· {a}" for a in avisos]),
            fg=self.t.erro if problemas else self.t.aviso)

    def exportar(self) -> None:
        if self.resultado is None:
            self.casca._registrar("[oficina] abra uma folha primeiro.", "erro")
            return
        ident = self.identidade()
        problemas = exportar.problemas(ident, len(self.resultado.caixas),
                                       self.resultado.alinhado.celula)
        if problemas:
            messagebox.showwarning("Falta coisa", "\n".join(problemas))
            return
        biblioteca = exportar.biblioteca_padrao()
        existentes = exportar.ja_existem(ident, biblioteca)
        if existentes and not messagebox.askyesno(
                "Já existe", "Estes arquivos já existem e serão "
                "substituídos:\n\n" + "\n".join(existentes)):
            return
        res, receita, med = self.resultado, self.receita, self.medidas
        self.casca._registrar(f">>> exportar {exportar.slug(ident.nome)} "
                              "para o palco", "cmd")

        def trabalho():
            return exportar.exportar(res, ident, receita, med, biblioteca,
                                     substituir=True)

        self.casca.supervisor.tarefa(trabalho, self._exportado,
                                     rotulo="exportar sprite")

    def _exportado(self, valor) -> None:
        if isinstance(valor, dict) and valor.get("erro"):
            self.casca._registrar(f"[oficina] não exportei: {valor['erro']}",
                                  "erro")
            return
        for chave, caminho in valor.items():
            self.casca._registrar(f"[oficina] {chave}: {caminho}", "saida")
        self.casca._registrar("[oficina] exportado. Confira com: python "
                              "main.py palco vitrine --so folhas", "fim")


def _rgb(cor: str) -> tuple:
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


__all__ = ["Pagina"]
