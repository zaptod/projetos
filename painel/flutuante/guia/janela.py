# -*- coding: utf-8 -*-
"""A janela do guia: sem borda, por cima, arrastavel, tamanho lembrado.

De cima para baixo (a ordem do `pack` e a ordem em que o espaco e
reservado — o rodape entra ANTES da lista, com `side=bottom`, para a lista
ficar com o que sobrar e nenhum botao cair fora da tela):

  barra      ◈ Guia das IAs · dica · 📌 − ✕
  cabecalho  a IA em mapeamento (do `_atual.json`, ou escolhida a mao no
             menu do nome) e o passo atual
  caixa      "colar aqui": Ctrl+V em qualquer lugar da janela cai aqui
  previa     tipo + uma linha (tag, id, aria, texto visivel)
  seletor    a sugestao robusta, EDITAVEL antes de gravar
  papeis     oito botoes, um por papel
  lista      o que ja foi colado para esta IA, com ✕ (dois cliques)
  rodape     mensagem curta ao agente · enviar · próximo ▶ · ◢ (redimensiona)

Regras herdadas da Vila flutuante: so esta classe chama `after`, e so na
thread do Tk (a escuta do `sinal` publica numa fila). O `−` recolhe para
uma faixa de uma linha — nunca `iconify`/`withdraw`, que somem para sempre
sem barra de tarefas. O `✕` aqui FECHA de verdade: diferente da Vila, nao
ha alerta que fechar esconderia, e o botao da Vila (ou o comando) reabre.
"""
from __future__ import annotations

import queue
import sys
import tkinter as tk
from pathlib import Path

from ... import estilo
from ...estilo import ESPACO
from .. import preferencias
from ..caminhos import Caminhos
from . import colado

TIQUE_MS = 1500
ANALISE_MS = 300
CONFIRMA_MS = 4000
ALTURA_BARRA = 30


class JanelaGuia(tk.Tk):
    def __init__(self, caminhos: Caminhos | None = None,
                 ia: str | None = None, topo: bool | None = None,
                 persistir: bool = True, demo: bool = False):
        super().__init__()
        self.t = estilo.VILA
        self.caminhos = caminhos or Caminhos()
        self.persistir = persistir
        self.demo = demo
        self.prefs = colado.ler_prefs(self.caminhos.guia_preferencias)
        if ia in colado.IAS:
            self.prefs["ia_manual"] = ia
        if topo is not None:
            self.prefs["topo"] = bool(topo)
        self.atual: dict | None = None          # o `_atual.json` lido
        self._mtime_atual = None
        self._mtime_colado = None
        self._itens: list = []
        self._itens_demo: list | None = [] if demo else None
        self._arrasto = None
        self._redimensiono = None
        self._analise = None
        self._confirmando = None
        self._confirma_timer = None
        self._seletor_sugerido = ""
        self._vivo = True
        self._escuta = None
        self.fila: queue.Queue = queue.Queue()
        self._botoes: dict = {}

        self.title("Guia das IAs — Neural Fights")
        self.configure(bg=self.t.borda_forte)
        self.overrideredirect(True)
        self.protocol("WM_DELETE_WINDOW", self.sair)
        self.attributes("-topmost", bool(self.prefs["topo"]))
        if not persistir:
            # A prova nao aparece na tela de ninguem (ver a Vila).
            self.attributes("-alpha", 0.0)
        self._ler_atual(forcar=True)
        self._montar()
        self._posicionar()
        if self.prefs.get("recolhida"):
            self.recolher(True)
        self.bind_all("<Control-v>", self._colar_atalho, add="+")
        self.bind_all("<Control-V>", self._colar_atalho, add="+")
        self.after(TIQUE_MS, self._tique)
        if persistir:
            self._escutar()

    # ------------------------------------------------------------ dados
    @property
    def ia(self) -> str:
        """A IA da vez: a escolhida a mao vence; senao a do agente; senao
        a primeira da lista (a janela nunca fica sem IA)."""
        if self.prefs.get("ia_manual") in colado.IAS:
            return self.prefs["ia_manual"]
        if self.atual and self.atual.get("ia"):
            return self.atual["ia"]
        return colado.IAS[0]

    @property
    def passo(self) -> str:
        if self.atual and self.atual.get("ia") == self.ia:
            return self.atual.get("passo") or ""
        return ""

    def _ler_atual(self, forcar: bool = False) -> bool:
        caminho = colado.caminho_atual(self.caminhos.ias)
        try:
            mtime = caminho.stat().st_mtime_ns
        except OSError:
            mtime = None
        if not forcar and mtime == self._mtime_atual:
            return False
        self._mtime_atual = mtime
        self.atual = colado.ler_atual(caminho)
        return True

    def _caminho_colado(self) -> Path:
        return colado.caminho_colado(self.caminhos.ias, self.ia)

    def _ler_itens(self, forcar: bool = False) -> bool:
        if self._itens_demo is not None:
            self._itens = [i for i in self._itens_demo if i.get("ia") == self.ia]
            return True
        caminho = self._caminho_colado()
        try:
            mtime = caminho.stat().st_mtime_ns
        except OSError:
            mtime = None
        if not forcar and mtime == self._mtime_colado:
            return False
        self._mtime_colado = mtime
        self._itens = colado.ler_itens(caminho)
        return True

    def _gravar(self, item: dict) -> bool:
        if self._itens_demo is not None:
            self._itens_demo.append(item)
            return True
        return colado.gravar_item(self._caminho_colado(), item)

    def _apagar(self, id_item: str) -> bool:
        if self._itens_demo is not None:
            antes = len(self._itens_demo)
            self._itens_demo = [i for i in self._itens_demo
                                if i.get("id") != id_item]
            return len(self._itens_demo) != antes
        return colado.apagar_item(self._caminho_colado(), id_item)

    # ------------------------------------------------------- montagem
    def _montar(self) -> None:
        t = self.t
        self.moldura = tk.Frame(self, bg=t.fundo)
        self.moldura.pack(fill="both", expand=True, padx=1, pady=1)
        self._barra_titulo(self.moldura)
        self.corpo = tk.Frame(self.moldura, bg=t.fundo)
        self.corpo.pack(fill="both", expand=True)
        self._cabecalho(self.corpo)
        self._caixa(self.corpo)
        self._previa(self.corpo)
        self._seletor(self.corpo)
        self._papeis(self.corpo)
        self._rodape(self.corpo)          # antes da lista: side=bottom
        self._lista(self.corpo)
        self._atualizar_cabecalho()
        self._ler_itens(forcar=True)
        self._desenhar_lista()

    def _rotulo(self, pai, texto: str, papel: str = "corpo",
                cor: str = "texto", peso: str = "normal", **kw) -> tk.Label:
        return tk.Label(pai, text=texto, bg=pai.cget("bg"),
                        fg=getattr(self.t, cor), font=self.t.letra(papel, peso),
                        anchor="w", **kw)

    def _botao_pequeno(self, pai, texto: str, acao, dica: str,
                       ativo: bool = False, nome: str = "") -> tk.Label:
        fundo = pai.cget("bg")
        cor = self.t.acento if ativo else self.t.texto_fraco
        botao = tk.Label(pai, text=texto, bg=fundo, fg=cor, cursor="hand2",
                         font=self.t.letra("corpo"), width=3, pady=2)
        botao.cor_normal = cor

        def entrar(_e):
            botao.configure(bg=self.t.superficie_alta, fg=self.t.acento_forte)
            self._dica(dica)

        def sair(_e):
            botao.configure(bg=fundo, fg=botao.cor_normal)
            self._dica(None)

        botao.bind("<Enter>", entrar)
        botao.bind("<Leave>", sair)
        botao.bind("<ButtonRelease-1>", lambda _e: (acao(), "break")[1])
        self._botoes[nome or texto] = botao
        return botao

    def _botao(self, pai, texto: str, acao, primario: bool = False,
               nome: str = "", **kw) -> tk.Button:
        t = self.t
        if primario:
            fundo, frente, realce = t.acento, "#1c150c", t.acento_forte
        else:
            fundo, frente, realce = t.superficie_alta, t.texto, t.borda_forte
        botao = tk.Button(pai, text=texto, command=acao, bg=fundo, fg=frente,
                          activebackground=realce, activeforeground=frente,
                          font=t.letra("legenda", "bold" if primario
                                       else "normal"),
                          relief="flat", bd=0, cursor="hand2",
                          highlightthickness=0, padx=ESPACO["meio"],
                          pady=ESPACO["pouco"], **kw)
        botao.bind("<Enter>", lambda _e: botao.configure(bg=realce))
        botao.bind("<Leave>", lambda _e: botao.configure(bg=fundo))
        self._botoes[nome or texto] = botao
        return botao

    def _barra_titulo(self, pai) -> None:
        t = self.t
        barra = tk.Frame(pai, bg=t.fundo, height=ALTURA_BARRA)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        # Botoes primeiro: quem chega antes reserva o espaco (Vila, 17/09).
        self._botao_pequeno(barra, "✕", self.sair,
                            "fechar o guia (o botão ◈ da Vila reabre)",
                            nome="fechar").pack(side="right", padx=(2, 2))
        self._btn_recolher = self._botao_pequeno(
            barra, "−", self.recolher, "recolher para uma faixa",
            nome="recolher")
        self._btn_recolher.pack(side="right", padx=(2, 0))
        self._btn_topo = self._botao_pequeno(
            barra, "📌", self.alternar_topo, "sempre por cima (liga/desliga)",
            ativo=bool(self.prefs["topo"]), nome="topo")
        self._btn_topo.pack(side="right", padx=(2, 0))
        # Simbolo do BMP de proposito: emoji fora dele (🧭) o Tk desenha
        # como um glifo estranho (visto na primeira prova de tela).
        marca = self._rotulo(barra, "◈ Guia das IAs", "secao", peso="bold",
                             padx=ESPACO["meio"])
        marca.pack(side="left")
        self._lbl_dica = self._rotulo(barra, "", "legenda", "texto_fraco",
                                      width=1)
        self._lbl_dica.pack(side="left", fill="x", expand=True)
        self._arrastavel(barra, marca, self._lbl_dica)
        for w in (barra, marca, self._lbl_dica):
            w.bind("<Double-Button-1>", lambda _e: self.recolher())
        tk.Frame(pai, bg=t.borda, height=1).pack(fill="x")

    def _cabecalho(self, pai) -> None:
        t = self.t
        quadro = tk.Frame(pai, bg=t.fundo)
        quadro.pack(fill="x", padx=ESPACO["normal"], pady=(ESPACO["meio"], 0))
        self._lbl_ia = tk.Label(quadro, text="…", bg=t.fundo, fg=t.acento,
                                font=t.letra("titulo", "bold"), cursor="hand2",
                                anchor="w")
        self._lbl_ia.pack(side="left")
        self._lbl_ia.bind("<Button-1>", self._menu_de_ia)
        self._lbl_passo = self._rotulo(quadro, "", "corpo", "texto_fraco",
                                       width=1)
        self._lbl_passo.pack(side="left", fill="x", expand=True,
                             padx=(ESPACO["meio"], 0))
        self._lbl_origem = self._rotulo(pai, "", "legenda", "texto_apagado")
        self._lbl_origem.pack(fill="x", padx=ESPACO["normal"])

    def _caixa(self, pai) -> None:
        t = self.t
        linha = tk.Frame(pai, bg=t.fundo)
        linha.pack(fill="x", padx=ESPACO["normal"], pady=(ESPACO["meio"], 2))
        self._rotulo(linha, "COLAR AQUI", "legenda", "texto_fraco",
                     peso="bold").pack(side="left")
        self._rotulo(linha, "Ctrl+V em qualquer lugar da janela", "legenda",
                     "texto_apagado").pack(side="left", padx=(ESPACO["meio"], 0))
        limpar = self._rotulo(linha, "limpar", "legenda", "texto_fraco",
                              cursor="hand2")
        limpar.pack(side="right")
        limpar.bind("<Button-1>", lambda _e: self.limpar())
        self.caixa = tk.Text(pai, height=6, bg=t.console_fundo,
                             fg=t.console_texto, insertbackground=t.acento,
                             font=t.letra("mono"), relief="flat", bd=0,
                             wrap="char", padx=ESPACO["meio"],
                             pady=ESPACO["pouco"], highlightthickness=1,
                             highlightbackground=t.borda,
                             highlightcolor=t.acento, undo=False)
        self.caixa.pack(fill="x", padx=ESPACO["normal"])
        # Na caixa, o Ctrl+V TROCA o conteudo (um item por colada) em vez
        # de emendar no cursor: o "break" segura a colagem padrao do Tk.
        self.caixa.bind("<Control-v>", self._colar_na_caixa)
        self.caixa.bind("<Control-V>", self._colar_na_caixa)
        self.caixa.bind("<<Modified>>", self._modificou)

    def _previa(self, pai) -> None:
        t = self.t
        quadro = tk.Frame(pai, bg=t.fundo)
        quadro.pack(fill="x", padx=ESPACO["normal"], pady=(ESPACO["pouco"], 0))
        self._lbl_tipo = tk.Label(quadro, text="", bg=t.fundo,
                                  fg=t.texto_apagado, font=t.letra("legenda",
                                                                   "bold"),
                                  width=7, anchor="w")
        self._lbl_tipo.pack(side="left")
        self._lbl_previa = self._rotulo(quadro, "cole o HTML do elemento, um "
                                        "seletor ou um texto", "legenda",
                                        "texto_fraco", justify="left", width=1)
        self._lbl_previa.pack(side="left", fill="x", expand=True)

    def _seletor(self, pai) -> None:
        t = self.t
        quadro = tk.Frame(pai, bg=t.fundo)
        quadro.pack(fill="x", padx=ESPACO["normal"], pady=(ESPACO["pouco"], 0))
        self._rotulo(quadro, "seletor", "legenda", "texto_fraco",
                     width=7).pack(side="left")
        self.entrada_seletor = tk.Entry(
            quadro, bg=t.superficie, fg=t.texto, insertbackground=t.acento,
            font=t.letra("mono"), relief="flat", bd=0, highlightthickness=1,
            highlightbackground=t.borda, highlightcolor=t.acento)
        self.entrada_seletor.pack(side="left", fill="x", expand=True, ipady=3)
        self._lbl_motivo = self._rotulo(pai, "", "legenda", "texto_apagado")
        self._lbl_motivo.pack(fill="x", padx=(ESPACO["normal"] + 56,
                                              ESPACO["normal"]))

    def _papeis(self, pai) -> None:
        quadro = tk.Frame(pai, bg=self.t.fundo)
        quadro.pack(fill="x", padx=ESPACO["normal"], pady=(ESPACO["meio"], 0))
        quadro.columnconfigure((0, 1), weight=1, uniform="papel")
        for indice, (papel, rotulo) in enumerate(colado.PAPEIS):
            botao = self._botao(quadro, rotulo,
                                lambda p=papel: self.gravar(p), nome=papel)
            botao.grid(row=indice // 2, column=indice % 2, sticky="ew",
                       padx=(0, ESPACO["pouco"]) if indice % 2 == 0 else 0,
                       pady=(0, ESPACO["pouco"]))

    def _lista(self, pai) -> None:
        t = self.t
        linha = tk.Frame(pai, bg=t.fundo)
        linha.pack(fill="x", padx=ESPACO["normal"], pady=(ESPACO["meio"], 2))
        self._lbl_lista = self._rotulo(linha, "COLADO", "legenda", "texto_fraco",
                                       peso="bold")
        self._lbl_lista.pack(side="left")
        quadro = tk.Frame(pai, bg=t.fundo)
        quadro.pack(fill="both", expand=True, padx=ESPACO["normal"],
                    pady=(0, ESPACO["meio"]))
        self.lista = tk.Text(quadro, bg=t.superficie, fg=t.texto,
                             font=t.letra("legenda"), relief="flat", bd=0,
                             wrap="none", state="disabled", cursor="arrow",
                             padx=ESPACO["meio"], pady=ESPACO["pouco"],
                             highlightthickness=1, highlightbackground=t.borda,
                             insertwidth=0, spacing1=2, spacing3=2)
        barra = tk.Scrollbar(quadro, command=self.lista.yview, width=10,
                             bg=t.superficie_alta, troughcolor=t.superficie,
                             relief="flat", bd=0)
        self.lista.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lista.pack(side="left", fill="both", expand=True)
        for marca, cor in (("hora", t.texto_apagado), ("papel", t.acento),
                           ("previa", t.texto_fraco), ("x", t.texto_apagado),
                           ("confirma", t.erro), ("vazio", t.texto_apagado),
                           ("marcador", t.info)):
            self.lista.tag_configure(marca, foreground=cor)
        self.lista.tag_configure("papel", font=t.letra("legenda", "bold"))
        self.lista.tag_configure("confirma", font=t.letra("legenda", "bold"))

    def _rodape(self, pai) -> None:
        t = self.t
        quadro = tk.Frame(pai, bg=t.fundo)
        quadro.pack(side="bottom", fill="x", padx=(ESPACO["normal"], 2),
                    pady=(0, 2))
        grip = tk.Label(quadro, text="◢", bg=t.fundo, fg=t.texto_apagado,
                        font=t.letra("legenda"), cursor="size_nw_se")
        grip.pack(side="right", anchor="s")
        grip.bind("<ButtonPress-1>", self._pegar_canto)
        grip.bind("<B1-Motion>", self._redimensionar)
        grip.bind("<ButtonRelease-1>", self._soltar_canto)
        self._btn_proximo = self._botao(quadro, "próximo ▶", self.proximo,
                                        primario=True, nome="proximo")
        self._btn_proximo.pack(side="right", padx=(ESPACO["pouco"],
                                                   ESPACO["meio"]))
        self._botao(quadro, "enviar", self.enviar_mensagem,
                    nome="enviar_mensagem").pack(side="right",
                                                 padx=(ESPACO["pouco"], 0))
        self.entrada_mensagem = tk.Entry(
            quadro, bg=t.superficie, fg=t.texto, insertbackground=t.acento,
            font=t.letra("legenda"), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=t.borda,
            highlightcolor=t.acento)
        self.entrada_mensagem.pack(side="left", fill="x", expand=True, ipady=4)
        self.entrada_mensagem.bind("<Return>", lambda _e: self.enviar_mensagem())
        self._dica_mensagem = "mensagem curta ao agente (\"não achei o botão\")"
        self._mostrar_dica_na_entrada()
        self.entrada_mensagem.bind("<FocusIn>", self._focou_mensagem)
        self.entrada_mensagem.bind("<FocusOut>", self._desfocou_mensagem)

    # ------------------------------------------------ dica da mensagem
    def _mostrar_dica_na_entrada(self) -> None:
        self.entrada_mensagem.delete(0, "end")
        self.entrada_mensagem.insert(0, self._dica_mensagem)
        self.entrada_mensagem.configure(fg=self.t.texto_apagado)
        self._mensagem_e_dica = True

    def _focou_mensagem(self, _e=None) -> None:
        if getattr(self, "_mensagem_e_dica", False):
            self.entrada_mensagem.delete(0, "end")
            self.entrada_mensagem.configure(fg=self.t.texto)
            self._mensagem_e_dica = False

    def _desfocou_mensagem(self, _e=None) -> None:
        if not self.entrada_mensagem.get().strip():
            self._mostrar_dica_na_entrada()

    def texto_da_mensagem(self) -> str:
        if getattr(self, "_mensagem_e_dica", False):
            return ""
        return self.entrada_mensagem.get().strip()

    # ---------------------------------------------------- cabecalho/IA
    def _atualizar_cabecalho(self) -> None:
        ia = self.ia
        self._lbl_ia.configure(text=f"{colado.ROTULOS.get(ia, ia)} ▾")
        passo = self.passo
        self._lbl_passo.configure(text=passo or ("aguardando o agente…"
                                                 if self.atual is None
                                                 else ""))
        if self.prefs.get("ia_manual"):
            origem = "escolhida a mão · clique no nome para voltar ao agente"
            if self.atual and self.atual.get("ia") != ia:
                origem = (f"escolhida a mão (o agente está em "
                          f"{colado.ROTULOS.get(self.atual['ia'], self.atual['ia'])})")
        elif self.atual is None:
            origem = "sem _atual.json: o agente ainda não disse qual IA"
        else:
            quando = colado.ha_quanto(self.atual.get("desde"))
            origem = "seguindo o agente" + (f" · {quando}" if quando else "")
        self._lbl_origem.configure(text=origem)
        self._lbl_lista.configure(
            text=f"COLADO PARA {colado.ROTULOS.get(ia, ia).upper()} "
                 f"({len(self._itens)})")

    def _menu_de_ia(self, evento) -> None:
        t = self.t
        menu = tk.Menu(self, tearoff=False, bg=t.superficie_alta, fg=t.texto,
                       activebackground=t.acento_fundo,
                       activeforeground=t.acento_forte, font=t.letra("corpo"),
                       bd=0)
        for ia in colado.IAS:
            marca = "● " if ia == self.ia else "   "
            menu.add_command(label=marca + colado.ROTULOS[ia],
                             command=lambda i=ia: self.escolher_ia(i))
        menu.add_separator()
        menu.add_command(label="seguir o agente (_atual.json)",
                         command=lambda: self.escolher_ia(None))
        try:
            menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            menu.grab_release()

    def escolher_ia(self, ia: str | None) -> None:
        self.prefs["ia_manual"] = ia if ia in colado.IAS else None
        self.guardar()
        self._ler_itens(forcar=True)
        self._atualizar_cabecalho()
        self._desenhar_lista()

    # ------------------------------------------------------- colar
    def _colar_atalho(self, evento):
        foco = self.focus_get()
        if foco in (self.entrada_mensagem, self.entrada_seletor):
            return None                     # colagem normal nas entradas
        if foco is self.caixa:
            return None                     # a caixa tem o binding proprio
        return self._colar_na_caixa(evento)

    def _colar_na_caixa(self, _evento=None):
        try:
            texto = self.clipboard_get()
        except tk.TclError:
            self._dica("a área de transferência não tem texto")
            return "break"
        self.colar(texto)
        return "break"

    def colar(self, texto: str) -> None:
        """Poe `texto` na caixa (trocando o que havia) e analisa."""
        self.caixa.delete("1.0", "end")
        self.caixa.insert("1.0", texto)
        self.caixa.edit_modified(False)
        self._analisar()

    def conteudo(self) -> str:
        return self.caixa.get("1.0", "end-1c")

    def limpar(self) -> None:
        self.caixa.delete("1.0", "end")
        self.caixa.edit_modified(False)
        self.entrada_seletor.delete(0, "end")
        self._seletor_sugerido = ""
        self._analisar()

    def _modificou(self, _e=None) -> None:
        if not self.caixa.edit_modified():
            return
        self.caixa.edit_modified(False)
        if self._analise is not None:
            self.after_cancel(self._analise)
        self._analise = self.after(ANALISE_MS, self._analisar)

    def _analisar(self) -> dict:
        self._analise = None
        texto = self.conteudo()
        tipo = colado.detectar(texto)
        info = colado.previa(texto, tipo)
        self._lbl_tipo.configure(
            text={"html": "HTML", "seletor": "SELETOR", "texto": "TEXTO"}
            .get(tipo, ""),
            fg={"html": self.t.info, "seletor": self.t.ok,
                "texto": self.t.aviso}.get(tipo, self.t.texto_apagado))
        self._lbl_previa.configure(
            text=info.get("resumo") or "cole o HTML do elemento, um seletor "
                                       "ou um texto")
        sugestao, motivo = "", ""
        if tipo == "html":
            sugestao, motivo = colado.seletor_robusto(texto)
        elif tipo == "seletor":
            sugestao, motivo = texto.strip(), "o próprio seletor colado"
        atual = self.entrada_seletor.get().strip()
        # So troca a sugestao se ele nao editou a anterior.
        if not atual or atual == self._seletor_sugerido:
            self.entrada_seletor.delete(0, "end")
            self.entrada_seletor.insert(0, sugestao)
        self._seletor_sugerido = sugestao
        self._lbl_motivo.configure(text=motivo)
        return {"tipo": tipo, "previa": info, "seletor": sugestao,
                "motivo": motivo}

    # ------------------------------------------------------- gravar
    def gravar(self, papel: str) -> dict | None:
        texto = self.conteudo().strip()
        if not texto:
            self._dica("cole algo na caixa antes (Ctrl+V)")
            return None
        tipo = colado.detectar(texto)
        seletor = self.entrada_seletor.get().strip() or None
        item = colado.item_novo(self.ia, papel, texto, passo=self.passo,
                                tipo=tipo, seletor=seletor)
        if not self._gravar(item):
            self._dica("não consegui gravar no colado.jsonl")
            return None
        self._dica(f"gravado: {colado.ROTULO_DO_PAPEL.get(papel, papel)}")
        self.caixa.delete("1.0", "end")
        self.caixa.edit_modified(False)
        self.entrada_seletor.delete(0, "end")
        self._seletor_sugerido = ""
        self._analisar()
        self._ler_itens(forcar=True)
        self._atualizar_cabecalho()
        self._desenhar_lista()
        return item

    def enviar_mensagem(self) -> dict | None:
        texto = self.texto_da_mensagem()
        if not texto:
            self._dica("escreva a mensagem antes de enviar")
            return None
        item = colado.item_novo(self.ia, colado.PAPEL_MENSAGEM, texto,
                                passo=self.passo, tipo="texto")
        if not self._gravar(item):
            self._dica("não consegui gravar a mensagem")
            return None
        self.entrada_mensagem.delete(0, "end")
        self._mensagem_e_dica = False
        self._desfocou_mensagem()
        self._dica("mensagem gravada para o agente")
        self._ler_itens(forcar=True)
        self._atualizar_cabecalho()
        self._desenhar_lista()
        return item

    def proximo(self) -> dict | None:
        """Grava o marcador `proximo` (antes, a mensagem, se houver)."""
        if self.texto_da_mensagem():
            self.enviar_mensagem()
        item = colado.item_novo(self.ia, colado.PAPEL_PROXIMO, "",
                                passo=self.passo, tipo="")
        if not self._gravar(item):
            self._dica("não consegui gravar o próximo")
            return None
        self._dica("próximo ▶ avisado ao agente")
        self._ler_itens(forcar=True)
        self._atualizar_cabecalho()
        self._desenhar_lista()
        return item

    def apagar(self, id_item: str) -> bool:
        """Primeiro clique pede confirmacao; o segundo apaga."""
        if self._confirmando != id_item:
            self._confirmando = id_item
            if self._confirma_timer is not None:
                self.after_cancel(self._confirma_timer)
            self._confirma_timer = self.after(CONFIRMA_MS,
                                              self._desconfirmar)
            self._desenhar_lista()
            self._dica("clique de novo em «apagar?» para confirmar")
            return False
        self._confirmando = None
        ok = self._apagar(id_item)
        self._dica("apagado" if ok else "não achei o item para apagar")
        self._ler_itens(forcar=True)
        self._atualizar_cabecalho()
        self._desenhar_lista()
        return ok

    def _desconfirmar(self) -> None:
        self._confirma_timer = None
        if self._confirmando is not None:
            self._confirmando = None
            self._desenhar_lista()

    # ------------------------------------------------------- lista
    def _desenhar_lista(self) -> None:
        caixa = self.lista
        topo = caixa.yview()[0]
        caixa.configure(state="normal")
        caixa.delete("1.0", "end")
        for marca in caixa.tag_names():
            if marca.startswith("x-"):
                caixa.tag_delete(marca)
        if not self._itens:
            caixa.insert("end", "nada colado ainda para esta IA.\n", ("vazio",))
        for item in reversed(self._itens):
            id_item = str(item.get("id") or "")
            papel = str(item.get("papel") or "")
            rotulo = colado.ROTULO_DO_PAPEL.get(papel, papel)
            marcador = papel in (colado.PAPEL_PROXIMO, colado.PAPEL_MENSAGEM)
            # O ✕ vem PRIMEIRO: a linha nao quebra, e no fim de uma previa
            # comprida ele ficaria fora da vista.
            if id_item:
                marca = f"x-{id_item}"
                if self._confirmando == id_item:
                    caixa.insert("end", "apagar? ", ("confirma", marca))
                else:
                    caixa.insert("end", "✕  ", ("x", marca))
                caixa.tag_bind(marca, "<Button-1>",
                               lambda _e, i=id_item: self.apagar(i))
                caixa.tag_bind(marca, "<Enter>",
                               lambda _e: caixa.configure(cursor="hand2"))
                caixa.tag_bind(marca, "<Leave>",
                               lambda _e: caixa.configure(cursor="arrow"))
            caixa.insert("end", colado.hora_curta(item.get("em")) + "  ",
                         ("hora",))
            caixa.insert("end", rotulo, ("marcador" if marcador else "papel",))
            previa = item.get("previa") or item.get("seletor_sugerido") or ""
            if previa:
                caixa.insert("end", "  " + previa, ("previa",))
            caixa.insert("end", "\n")
        caixa.configure(state="disabled")
        caixa.yview_moveto(topo)

    # ------------------------------------------------------- janela
    def _dica(self, texto) -> None:
        alvo = getattr(self, "_lbl_dica", None)
        if alvo is None or not alvo.winfo_exists():
            return
        alvo.configure(text=texto or "",
                       fg=self.t.acento_forte if texto else self.t.texto_fraco)

    def _posicionar(self) -> None:
        tela = (self.winfo_screenwidth(), self.winfo_screenheight())
        largura = min(int(self.prefs["largura"]), tela[0])
        altura = min(int(self.prefs["altura"]),
                     tela[1] - preferencias.BARRA_DO_WINDOWS)
        x, y = preferencias.encaixar(self.prefs.get("x"), self.prefs.get("y"),
                                     largura, altura, tela)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def guardar(self) -> None:
        if not self.persistir:
            return
        if self.winfo_exists():
            self.prefs["x"], self.prefs["y"] = self.winfo_x(), self.winfo_y()
            if not self.prefs.get("recolhida"):
                self.prefs["largura"] = self.winfo_width()
                self.prefs["altura"] = self.winfo_height()
        colado.gravar_prefs(self.caminhos.guia_preferencias, self.prefs)

    def alternar_topo(self) -> None:
        self.prefs["topo"] = not self.prefs["topo"]
        self.attributes("-topmost", bool(self.prefs["topo"]))
        cor = self.t.acento if self.prefs["topo"] else self.t.texto_fraco
        self._btn_topo.cor_normal = cor
        self._btn_topo.configure(fg=cor)
        self.guardar()

    def recolher(self, forcar: bool | None = None) -> None:
        """Vira uma faixa de uma linha (ou volta). Nunca `withdraw`."""
        recolher = (not self.prefs.get("recolhida")) if forcar is None \
            else bool(forcar)
        if recolher and not self.prefs.get("recolhida"):
            self.prefs["largura"] = self.winfo_width()
            self.prefs["altura"] = self.winfo_height()
        self.prefs["recolhida"] = recolher
        if recolher:
            self.corpo.pack_forget()
            self.geometry(f"{self.prefs['largura']}x{colado.ALTURA_RECOLHIDA}")
            self._btn_recolher.configure(text="▢")
            self._dica(f"{colado.ROTULOS.get(self.ia, self.ia)} · "
                       f"{self.passo or 'guia recolhido'}")
        else:
            self.corpo.pack(fill="both", expand=True)
            self.geometry(f"{self.prefs['largura']}x{self.prefs['altura']}")
            self._btn_recolher.configure(text="−")
            self._dica(None)
        self.guardar()

    def mostrar(self) -> None:
        if self.prefs.get("recolhida"):
            self.recolher(False)
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(1500, lambda: self.attributes("-topmost",
                                                 bool(self.prefs["topo"])))
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def devolver_foco(self, antes: int) -> None:
        """Abriu por cima do navegador sem tirar o foco dele: se a janela
        nova virou a da frente (acontece no primeiro desenho), devolve."""
        if sys.platform != "win32" or not antes:
            return
        import ctypes
        user32 = ctypes.windll.user32
        self.update_idletasks()
        try:
            nossa = int(self.wm_frame(), 16)
        except (ValueError, TypeError):
            return
        if user32.GetForegroundWindow() == nossa:
            user32.SetForegroundWindow(antes)

    # ---- arrastar e redimensionar
    def _arrastavel(self, *widgets) -> None:
        for w in widgets:
            w.bind("<ButtonPress-1>", self._agarrar, add="+")
            w.bind("<B1-Motion>", self._arrastar, add="+")
            w.bind("<ButtonRelease-1>", self._soltar, add="+")

    def _agarrar(self, evento) -> None:
        self._arrasto = (evento.x_root - self.winfo_x(),
                         evento.y_root - self.winfo_y())

    def _arrastar(self, evento) -> None:
        if self._arrasto:
            dx, dy = self._arrasto
            self.geometry(f"+{evento.x_root - dx}+{evento.y_root - dy}")

    def _soltar(self, _evento) -> None:
        if self._arrasto:
            self._arrasto = None
            tela = (self.winfo_screenwidth(), self.winfo_screenheight())
            x, y = preferencias.encaixar(self.winfo_x(), self.winfo_y(),
                                         self.winfo_width(),
                                         self.winfo_height(), tela)
            self.geometry(f"+{x}+{y}")
            self.guardar()

    def _pegar_canto(self, evento) -> None:
        self._redimensiono = (evento.x_root, evento.y_root,
                              self.winfo_width(), self.winfo_height())

    def _redimensionar(self, evento) -> None:
        if not self._redimensiono or self.prefs.get("recolhida"):
            return
        x0, y0, l0, a0 = self._redimensiono
        largura = max(colado.TAMANHO_MINIMO[0], l0 + evento.x_root - x0)
        altura = max(colado.TAMANHO_MINIMO[1], a0 + evento.y_root - y0)
        self.geometry(f"{largura}x{altura}")

    def _soltar_canto(self, _evento) -> None:
        if self._redimensiono:
            self._redimensiono = None
            self.guardar()

    # ---- ritmo
    def _tique(self) -> None:
        if not self._vivo:
            return
        try:
            while True:
                pedido = self.fila.get_nowait()
                if pedido == "mostrar":
                    self.mostrar()
        except queue.Empty:
            pass
        mudou_atual = self._ler_atual()
        mudou_itens = self._ler_itens()
        if mudou_atual or mudou_itens:
            self._atualizar_cabecalho()
            self._desenhar_lista()
            if self.prefs.get("recolhida"):
                self._dica(f"{colado.ROTULOS.get(self.ia, self.ia)} · "
                           f"{self.passo or 'guia recolhido'}")
        elif self.atual and not self.prefs.get("ia_manual"):
            self._atualizar_cabecalho()          # o "há N min" anda
        self.after(TIQUE_MS, self._tique)

    def _escutar(self) -> None:
        from .. import sinal
        try:
            self._escuta = sinal.Escuta(
                self.caminhos.guia_sinal,
                lambda: self.fila.put("mostrar")).iniciar()
        except OSError:
            self._escuta = None

    def sair(self) -> None:
        self._vivo = False
        if self._escuta is not None:
            self._escuta.parar()
        self.guardar()
        self.destroy()


__all__ = ["JanelaGuia"]
