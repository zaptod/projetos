# -*- coding: utf-8 -*-
"""A OFICINA da Vila: importar folhas, fatiar, atribuir papeis e pintar o mapa.

E a ferramenta que o Adrian pediu para "atribuir tudo": ele gera a arte
(PicassoIA ou qualquer coisa), importa o PNG aqui, ajusta a grade, clica nas
celulas e diz "isso e o predio do Digen", "isso e grama", "isso e o bot
andando para baixo". Depois pinta o mapa como num editor de tile: chao com
arrasto, decoracao e predios com clique. Salvou, a Vila do painel recompoe.

Abre de dois jeitos:
    painel -> pagina Vila -> 🎨 Oficina
    python -m vila.editor              (standalone, para mexer sem o painel)

Fluxo tipico com arte de IA:
    1. ➕ Importar folha (PNG). IA nao gera transparencia: poe "auto" na
       chave que a cor do canto vira transparente.
    2. Ajustar a grade (tile, margem, espaco) ate as linhas casarem.
    3. Clicar na celula (Ctrl+clique junta varios frames, em ordem),
       escolher o papel e 🎯 Atribuir.
    4. Na direita, pintar: chao arrastando, decoracao/predio clicando.
    5. 💾 Salvar tudo.
"""
from __future__ import annotations

import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import motor

BG = "#14121f"
CARD = "#232040"
TEXTO = "#f0edfa"
DIM = "#9a93b8"
ACENTO = "#9b59ff"
SEL = "#ff5c5c"
FONTE = ("Segoe UI", 9)
FONTE_B = ("Segoe UI", 9, "bold")

ESCALA_FOLHA = 2


class Oficina(tk.Toplevel):
    def __init__(self, master=None, ao_salvar=None):
        super().__init__(master)
        self.title("🎨 Oficina da Vila — folhas, papéis e mapa")
        self.configure(bg=BG)
        self.geometry("1330x700")
        self.minsize(1100, 620)

        self.cfg = motor.carregar()
        self.atlas = motor.Atlas(self.cfg)
        self.ao_salvar = ao_salvar
        self.folha_sel: str | None = next(iter(self.cfg["folhas"]), None)
        self.selecao: list[int] = []
        self._anim_id = None
        self._mapa_sujo = False

        self._montar()
        self._listar_folhas()
        self._mostrar_folha()
        self._listar_papeis()
        self._pintar_mapa()

    # ------------------------------------------------------------ moldura
    def _rotulo(self, pai, texto):
        tk.Label(pai, text=texto, bg=BG, fg=ACENTO,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 2))

    def _botao(self, pai, texto, comando):
        return tk.Button(pai, text=texto, command=comando, bg=CARD, fg=TEXTO,
                         activebackground=ACENTO, bd=0, font=FONTE,
                         padx=8, pady=3, cursor="hand2")

    def _montar(self):
        raiz = tk.Frame(self, bg=BG)
        raiz.pack(fill="both", expand=True, padx=10, pady=6)
        self.col_folha = tk.Frame(raiz, bg=BG)
        self.col_folha.pack(side="left", fill="y", padx=(0, 10))
        self.col_papel = tk.Frame(raiz, bg=BG)
        self.col_papel.pack(side="left", fill="y", padx=(0, 10))
        self.col_mapa = tk.Frame(raiz, bg=BG)
        self.col_mapa.pack(side="left", fill="both", expand=True)
        self._montar_folhas()
        self._montar_papeis()
        self._montar_mapa()

    # ------------------------------------------------------------- folhas
    def _montar_folhas(self):
        pai = self.col_folha
        self._rotulo(pai, "1 · FOLHAS DE SPRITES")
        alto = tk.Frame(pai, bg=BG)
        alto.pack(fill="x")
        self.lista_folhas = tk.Listbox(alto, height=3, width=24, bg=CARD,
                                       fg=TEXTO, bd=0, font=FONTE,
                                       selectbackground=ACENTO,
                                       exportselection=False)
        self.lista_folhas.pack(side="left", fill="x", expand=True)
        self.lista_folhas.bind("<<ListboxSelect>>", self._trocar_folha)
        self._botao(alto, "➕", self._importar_folha).pack(side="left",
                                                          padx=(6, 0))

        grade = tk.Frame(pai, bg=BG)
        grade.pack(fill="x", pady=(6, 0))
        self.var_grade = {}
        for i, (chave, rotulo, largura) in enumerate((
                ("tile_w", "tile L", 4), ("tile_h", "tile A", 4),
                ("margem", "margem", 4), ("espaco", "espaço", 4))):
            tk.Label(grade, text=rotulo, bg=BG, fg=DIM,
                     font=FONTE).grid(row=0, column=i * 2, sticky="w")
            var = tk.StringVar(value="16" if chave.startswith("tile") else "0")
            self.var_grade[chave] = var
            tk.Entry(grade, textvariable=var, width=largura, bg=CARD, fg=TEXTO,
                     bd=0, insertbackground=TEXTO,
                     font=FONTE).grid(row=0, column=i * 2 + 1, padx=(2, 8))
        linha2 = tk.Frame(pai, bg=BG)
        linha2.pack(fill="x", pady=(4, 0))
        tk.Label(linha2, text="chave", bg=BG, fg=DIM, font=FONTE).pack(side="left")
        self.var_chave = tk.StringVar(value="")
        tk.Entry(linha2, textvariable=self.var_chave, width=8, bg=CARD,
                 fg=TEXTO, bd=0, insertbackground=TEXTO,
                 font=FONTE).pack(side="left", padx=(2, 4))
        tk.Label(linha2, text='("auto" p/ arte de IA)', bg=BG, fg=DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        self._botao(linha2, "Aplicar grade",
                    self._aplicar_grade).pack(side="right")

        quadro = tk.Frame(pai, bg=CARD)
        quadro.pack(pady=(6, 0))
        self.canvas_folha = tk.Canvas(quadro, width=350, height=330, bg="#0e0c18",
                                      highlightthickness=0)
        barra_y = tk.Scrollbar(quadro, orient="vertical",
                               command=self.canvas_folha.yview)
        barra_x = tk.Scrollbar(quadro, orient="horizontal",
                               command=self.canvas_folha.xview)
        self.canvas_folha.configure(yscrollcommand=barra_y.set,
                                    xscrollcommand=barra_x.set)
        self.canvas_folha.grid(row=0, column=0)
        barra_y.grid(row=0, column=1, sticky="ns")
        barra_x.grid(row=1, column=0, sticky="ew")
        self.canvas_folha.bind("<Button-1>", self._clicar_celula)
        self.canvas_folha.bind("<Control-Button-1>",
                               lambda e: self._clicar_celula(e, juntar=True))
        tk.Label(pai, text="clique = escolhe a célula · Ctrl+clique = junta "
                           "frames (na ordem)", bg=BG, fg=DIM,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))

    def _listar_folhas(self):
        self.lista_folhas.delete(0, "end")
        for nome in self.cfg["folhas"]:
            self.lista_folhas.insert("end", nome)
        if self.folha_sel and self.folha_sel in self.cfg["folhas"]:
            i = list(self.cfg["folhas"]).index(self.folha_sel)
            self.lista_folhas.selection_set(i)
            self._carregar_grade()

    def _carregar_grade(self):
        dados = self.cfg["folhas"].get(self.folha_sel) or {}
        for chave, var in self.var_grade.items():
            padrao = self.cfg["tile"] if chave.startswith("tile") else 0
            var.set(str(dados.get(chave, padrao)))
        self.var_chave.set(dados.get("chave") or "")

    def _trocar_folha(self, _evento=None):
        sel = self.lista_folhas.curselection()
        if sel:
            self.folha_sel = self.lista_folhas.get(sel[0])
            self.selecao = []
            self._carregar_grade()
            self._mostrar_folha()

    def _importar_folha(self):
        caminho = filedialog.askopenfilename(
            parent=self, title="Folha de sprites (PNG)",
            filetypes=[("Imagens", "*.png;*.webp;*.jpg;*.jpeg")])
        if not caminho:
            return
        motor.SPRITES.mkdir(parents=True, exist_ok=True)
        nome = motor.Path(caminho).stem.lower().replace(" ", "_")
        destino = motor.SPRITES / f"{nome}.png"
        Image.open(caminho).convert("RGBA").save(destino)
        if caminho != str(destino):
            del caminho
        self.cfg["folhas"][nome] = {
            "arquivo": f"sprites/{destino.name}", "tile_w": self.cfg["tile"],
            "tile_h": self.cfg["tile"], "margem": 0, "espaco": 0, "chave": None}
        self.folha_sel = nome
        self.atlas.limpar()
        self._listar_folhas()
        self._mostrar_folha()

    def _aplicar_grade(self):
        if not self.folha_sel:
            return
        dados = self.cfg["folhas"][self.folha_sel]
        try:
            for chave, var in self.var_grade.items():
                dados[chave] = max(0, int(var.get()))
            for lado in ("tile_w", "tile_h"):
                dados[lado] = max(2, dados[lado])
        except ValueError:
            messagebox.showwarning("Grade", "A grade precisa de números.",
                                   parent=self)
            return
        chave = self.var_chave.get().strip()
        dados["chave"] = chave if chave in ("auto",) or chave.startswith("#") \
            else None
        self.atlas.limpar()
        self.selecao = []
        self._mostrar_folha()
        self._pintar_mapa(agora=True)

    def _mostrar_folha(self):
        c = self.canvas_folha
        c.delete("all")
        if not self.folha_sel:
            c.create_text(175, 160, text="importe uma folha (➕)", fill=DIM,
                          font=FONTE)
            return
        try:
            img = self.atlas.folha(self.folha_sel)
        except Exception as erro:
            c.create_text(175, 160, text=f"não li a folha:\n{erro}", fill=SEL,
                          font=FONTE)
            return
        grande = img.resize((img.width * ESCALA_FOLHA,
                             img.height * ESCALA_FOLHA), Image.NEAREST)
        self._ph_folha = ImageTk.PhotoImage(grande)
        c.create_image(0, 0, anchor="nw", image=self._ph_folha)
        c.configure(scrollregion=(0, 0, grande.width, grande.height))

        tw, th, margem, espaco = motor.grade(self.cfg, self.folha_sel)
        cols, rows = motor.celulas(self.cfg, self.folha_sel, img.size)
        e = ESCALA_FOLHA
        for col in range(cols):
            for row in range(rows):
                x0 = (margem + col * (tw + espaco)) * e
                y0 = (margem + row * (th + espaco)) * e
                c.create_rectangle(x0, y0, x0 + tw * e, y0 + th * e,
                                   outline="#3a3560")
        for ordem, indice in enumerate(self.selecao):
            col, row = indice % cols, indice // cols
            x0 = (margem + col * (tw + espaco)) * e
            y0 = (margem + row * (th + espaco)) * e
            c.create_rectangle(x0, y0, x0 + tw * e, y0 + th * e,
                               outline=SEL, width=2)
            c.create_text(x0 + 6, y0 + 6, text=str(ordem + 1), fill=SEL,
                          font=("Segoe UI", 7, "bold"))

    def _clicar_celula(self, evento, juntar=False):
        if not self.folha_sel:
            return
        img = self.atlas.folha(self.folha_sel)
        tw, th, margem, espaco = motor.grade(self.cfg, self.folha_sel)
        cols, rows = motor.celulas(self.cfg, self.folha_sel, img.size)
        e = ESCALA_FOLHA
        cx = self.canvas_folha.canvasx(evento.x) / e - margem
        cy = self.canvas_folha.canvasy(evento.y) / e - margem
        col = int(cx // (tw + espaco))
        row = int(cy // (th + espaco))
        if not (0 <= col < cols and 0 <= row < rows):
            return
        indice = row * cols + col
        if juntar:
            if indice in self.selecao:
                self.selecao.remove(indice)
            else:
                self.selecao.append(indice)
        else:
            self.selecao = [indice]
        self._mostrar_folha()

    # ------------------------------------------------------------- papeis
    def _montar_papeis(self):
        pai = self.col_papel
        self._rotulo(pai, "2 · PAPÉIS (o que cada sprite É)")
        self.combo_papel = ttk.Combobox(pai, width=24, font=FONTE)
        self.combo_papel.pack(fill="x")
        campos = tk.Frame(pai, bg=BG)
        campos.pack(fill="x", pady=(6, 0))
        self.var_papel = {}
        for i, (chave, rotulo) in enumerate((("larg", "larg (tiles)"),
                                             ("alt", "alt (tiles)"),
                                             ("fps", "fps"))):
            tk.Label(campos, text=rotulo, bg=BG, fg=DIM,
                     font=FONTE).grid(row=i, column=0, sticky="w")
            var = tk.StringVar(value="1" if chave != "fps" else "0")
            self.var_papel[chave] = var
            tk.Spinbox(campos, from_=0 if chave == "fps" else 1, to=12,
                       textvariable=var, width=4, bg=CARD, fg=TEXTO, bd=0,
                       font=FONTE).grid(row=i, column=1, padx=6, pady=1)
        self.var_variar = tk.BooleanVar(value=False)
        tk.Checkbutton(campos, text="variar por posição (chão)",
                       variable=self.var_variar, bg=BG, fg=TEXTO,
                       selectcolor=CARD, activebackground=BG,
                       font=FONTE).grid(row=3, column=0, columnspan=2,
                                        sticky="w")
        self._botao(pai, "🎯 Atribuir seleção ao papel",
                    self._atribuir).pack(fill="x", pady=(8, 0))

        self._rotulo(pai, "PRÉVIA")
        self.canvas_previa = tk.Canvas(pai, width=120, height=120,
                                       bg="#0e0c18", highlightthickness=0)
        self.canvas_previa.pack()

        self._rotulo(pai, "JÁ ATRIBUÍDOS")
        self.lista_papeis = tk.Listbox(pai, height=12, width=30, bg=CARD,
                                       fg=TEXTO, bd=0, font=("Consolas", 8),
                                       selectbackground=ACENTO,
                                       exportselection=False)
        self.lista_papeis.pack(fill="both", expand=True)
        self.lista_papeis.bind("<<ListboxSelect>>", self._escolher_papel)

    def _valores_de_papeis(self):
        todos = sorted(set(motor.PAPEIS_SUGERIDOS) | set(self.cfg["papeis"]))
        self.combo_papel.configure(values=todos)

    def _listar_papeis(self):
        self._valores_de_papeis()
        self.lista_papeis.delete(0, "end")
        for nome, dados in sorted(self.cfg["papeis"].items()):
            marca = "✓" if dados.get("folha") in self.cfg["folhas"] else "?"
            self.lista_papeis.insert(
                "end", f"{marca} {nome} ← {dados.get('folha')}"
                       f"[{len(dados.get('frames') or [])}]")
        self._combo_pintura()

    def _escolher_papel(self, _evento=None):
        sel = self.lista_papeis.curselection()
        if not sel:
            return
        nome = self.lista_papeis.get(sel[0]).split()[1]
        dados = self.cfg["papeis"].get(nome) or {}
        self.combo_papel.set(nome)
        self.var_papel["larg"].set(str(dados.get("larg", 1)))
        self.var_papel["alt"].set(str(dados.get("alt", 1)))
        self.var_papel["fps"].set(str(dados.get("fps", 0)))
        self.var_variar.set(bool(dados.get("variar")))
        if dados.get("folha") == self.folha_sel:
            self.selecao = list(dados.get("frames") or [])
            self._mostrar_folha()
        self._previa(nome)

    def _atribuir(self):
        papel = self.combo_papel.get().strip()
        if not papel:
            messagebox.showwarning("Papel", "Escolha (ou invente) o nome do "
                                   "papel primeiro.", parent=self)
            return
        if not self.folha_sel or not self.selecao:
            messagebox.showwarning("Papel", "Clique nas células da folha que "
                                   "formam este papel.", parent=self)
            return
        try:
            dados = {"folha": self.folha_sel, "frames": list(self.selecao),
                     "larg": max(1, int(self.var_papel["larg"].get())),
                     "alt": max(1, int(self.var_papel["alt"].get())),
                     "fps": max(0, int(self.var_papel["fps"].get()))}
        except ValueError:
            messagebox.showwarning("Papel", "larg/alt/fps precisam de números.",
                                   parent=self)
            return
        if self.var_variar.get():
            dados["variar"] = True
        self.cfg["papeis"][papel] = dados
        self.atlas.limpar()
        self._listar_papeis()
        self._previa(papel)
        self._pintar_mapa(agora=True)

    def _previa(self, papel):
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None
        c = self.canvas_previa
        c.delete("all")
        dados = self.cfg["papeis"].get(papel)
        if not dados:
            return
        quadros = len(dados.get("frames") or [])
        fps = int(dados.get("fps") or 0)
        estado = {"i": 0}

        def mostrar():
            try:
                img = self.atlas.sprite(papel, estado["i"])
            except Exception:
                return
            fator = max(1, min(6, 110 // max(img.size)))
            grande = img.resize((img.width * fator, img.height * fator),
                                Image.NEAREST)
            self._ph_previa = ImageTk.PhotoImage(grande)
            c.delete("all")
            c.create_image(60, 60, image=self._ph_previa)
            if quadros > 1 and fps > 0:
                estado["i"] = (estado["i"] + 1) % quadros
                self._anim_id = self.after(int(1000 / fps), mostrar)

        mostrar()

    # --------------------------------------------------------------- mapa
    def _montar_mapa(self):
        pai = self.col_mapa
        self._rotulo(pai, "3 · MAPA (pinte o mundo)")
        barra = tk.Frame(pai, bg=BG)
        barra.pack(fill="x")
        self.var_modo = tk.StringVar(value="chao")
        for valor, rotulo in (("chao", "🖌 chão (arraste)"),
                              ("decor", "🌳 decoração"),
                              ("predio", "🏭 prédio"),
                              ("apagar", "🧽 apagar")):
            tk.Radiobutton(barra, text=rotulo, value=valor,
                           variable=self.var_modo, command=self._combo_pintura,
                           bg=BG, fg=TEXTO, selectcolor=CARD,
                           activebackground=BG,
                           font=FONTE).pack(side="left", padx=(0, 6))
        self.combo_pintura = ttk.Combobox(barra, width=18, state="readonly",
                                          font=FONTE)
        self.combo_pintura.pack(side="left")

        barra2 = tk.Frame(pai, bg=BG)
        barra2.pack(fill="x", pady=(4, 0))
        self._botao(barra2, "🧺 Preencher chão",
                    self._preencher).pack(side="left")
        tk.Label(barra2, text="   novo mapa:", bg=BG, fg=DIM,
                 font=FONTE).pack(side="left")
        self.var_larg = tk.StringVar(value="44")
        self.var_alt = tk.StringVar(value="26")
        for var in (self.var_larg, self.var_alt):
            tk.Entry(barra2, textvariable=var, width=4, bg=CARD, fg=TEXTO,
                     bd=0, insertbackground=TEXTO,
                     font=FONTE).pack(side="left", padx=2)
        self._botao(barra2, "criar", self._novo_mapa).pack(side="left",
                                                           padx=(4, 0))
        self._botao(barra2, "💾 Salvar tudo", self._salvar).pack(side="right")
        self.lbl_estado = tk.Label(barra2, text="", bg=BG, fg=DIM, font=FONTE)
        self.lbl_estado.pack(side="right", padx=8)

        quadro = tk.Frame(pai, bg=CARD)
        quadro.pack(fill="both", expand=True, pady=(6, 0))
        self.canvas_mapa = tk.Canvas(quadro, bg="#0e0c18",
                                     highlightthickness=0)
        barra_y = tk.Scrollbar(quadro, orient="vertical",
                               command=self.canvas_mapa.yview)
        barra_x = tk.Scrollbar(quadro, orient="horizontal",
                               command=self.canvas_mapa.xview)
        self.canvas_mapa.configure(yscrollcommand=barra_y.set,
                                   xscrollcommand=barra_x.set)
        self.canvas_mapa.grid(row=0, column=0, sticky="nsew")
        barra_y.grid(row=0, column=1, sticky="ns")
        barra_x.grid(row=1, column=0, sticky="ew")
        quadro.rowconfigure(0, weight=1)
        quadro.columnconfigure(0, weight=1)
        self.canvas_mapa.bind("<ButtonPress-1>", self._mapa_clique)
        self.canvas_mapa.bind("<B1-Motion>",
                              lambda e: self._mapa_clique(e, arrasto=True))
        self.canvas_mapa.bind("<ButtonPress-3>",
                              lambda e: self.canvas_mapa.scan_mark(e.x, e.y))
        self.canvas_mapa.bind("<B3-Motion>",
                              lambda e: self.canvas_mapa.scan_dragto(e.x, e.y,
                                                                     gain=1))
        tk.Label(pai, text="botão direito arrasta o mapa · prédios e casa: um "
                           "de cada, o clique muda de lugar",
                 bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(anchor="w")

    def _combo_pintura(self):
        modo = self.var_modo.get()
        if modo == "chao":
            valores = sorted(p for p in self.cfg["papeis"]
                             if p.startswith("chao."))
        elif modo == "decor":
            valores = sorted(p for p in self.cfg["papeis"]
                             if p.startswith("decor."))
        elif modo == "predio":
            valores = motor.FABRICAS + ["casa"]
        else:
            valores = []
        self.combo_pintura.configure(values=valores)
        if valores and self.combo_pintura.get() not in valores:
            self.combo_pintura.set(valores[0])

    def _novo_mapa(self):
        try:
            larg, alt = int(self.var_larg.get()), int(self.var_alt.get())
        except ValueError:
            return
        chaos = sorted(p for p in self.cfg["papeis"] if p.startswith("chao."))
        if not chaos:
            messagebox.showwarning("Mapa", "Atribua ao menos um papel chao.* "
                                   "antes de criar o mapa.", parent=self)
            return
        if self.cfg.get("mapa") and not messagebox.askyesno(
                "Novo mapa", "Jogar fora o mapa atual e começar um vazio?",
                parent=self):
            return
        self.cfg["mapa"] = motor.mapa_novo(larg, alt, [chaos[0]])
        self._pintar_mapa(agora=True)

    def _preencher(self):
        mapa = self.cfg.get("mapa")
        papel = self.combo_pintura.get()
        if not mapa or not papel.startswith("chao."):
            return
        i = self._indice_na_paleta(papel)
        mapa["chao"] = [[i] * mapa["larg"] for _ in range(mapa["alt"])]
        self._pintar_mapa(agora=True)

    def _indice_na_paleta(self, papel):
        paleta = self.cfg["mapa"]["paleta"]
        if papel not in paleta:
            paleta.append(papel)
        return paleta.index(papel)

    def _mapa_clique(self, evento, arrasto=False):
        mapa = self.cfg.get("mapa")
        if not mapa:
            return
        ts = self.cfg["tile"]
        x = int(self.canvas_mapa.canvasx(evento.x) // ts)
        y = int(self.canvas_mapa.canvasy(evento.y) // ts)
        if not (0 <= x < mapa["larg"] and 0 <= y < mapa["alt"]):
            return
        modo = self.var_modo.get()
        papel = self.combo_pintura.get()
        if modo == "chao" and papel.startswith("chao."):
            mapa["chao"][y][x] = self._indice_na_paleta(papel)
        elif modo == "decor" and papel and not arrasto:
            mapa["decor"] = [d for d in mapa["decor"]
                             if (d["x"], d["y"]) != (x, y)]
            mapa["decor"].append({"x": x, "y": y, "papel": papel})
        elif modo == "predio" and papel and not arrasto:
            if papel == "casa":
                mapa["casa"] = {"x": x, "y": y}
            else:
                mapa.setdefault("predios", {})[papel] = {"x": x, "y": y}
        elif modo == "apagar":
            antes = len(mapa["decor"])
            mapa["decor"] = [d for d in mapa["decor"]
                             if (d["x"], d["y"]) != (x, y)]
            if len(mapa["decor"]) == antes:
                for nome, pos in list((mapa.get("predios") or {}).items()):
                    larg, alt = motor.tamanho(self.cfg, f"predio.{nome}")
                    if (pos["x"] <= x < pos["x"] + larg
                            and pos["y"] <= y < pos["y"] + alt):
                        del mapa["predios"][nome]
                        break
                else:
                    mapa["chao"][y][x] = 0
        else:
            return
        self._pintar_mapa()

    def _pintar_mapa(self, agora=False):
        """Recompoe com folga (throttle): pintar arrastando fica fluido."""
        if agora:
            self._mapa_sujo = False
            self._pintar_mapa_agora()
            return
        if not self._mapa_sujo:
            self._mapa_sujo = True
            self.after(70, self._pintar_mapa_de_verdade)

    def _pintar_mapa_de_verdade(self):
        self._mapa_sujo = False
        self._pintar_mapa_agora()

    def _pintar_mapa_agora(self):
        c = self.canvas_mapa
        c.delete("all")
        mapa = self.cfg.get("mapa")
        if not mapa:
            c.create_text(300, 180, text="sem mapa ainda — defina o tamanho "
                          "e clique em criar", fill=DIM, font=FONTE)
            return
        try:
            img = motor.compor_mundo(self.cfg, self.atlas, escala=1)
        except Exception as erro:
            c.create_text(300, 180, text=f"não compus o mapa:\n{erro}",
                          fill=SEL, font=FONTE)
            return
        self._ph_mapa = ImageTk.PhotoImage(img)
        c.create_image(0, 0, anchor="nw", image=self._ph_mapa)
        c.configure(scrollregion=(0, 0, img.width, img.height))
        ts = self.cfg["tile"]
        for nome, pos in (mapa.get("predios") or {}).items():
            larg, alt = motor.tamanho(self.cfg, f"predio.{nome}")
            c.create_text((pos["x"] + larg / 2) * ts, (pos["y"] + alt) * ts + 6,
                          text=nome, fill="#ffe9a8", font=("Segoe UI", 7, "bold"))
        if mapa.get("casa"):
            larg, alt = motor.tamanho(self.cfg, "predio.casa")
            c.create_text((mapa["casa"]["x"] + larg / 2) * ts,
                          (mapa["casa"]["y"] + alt) * ts + 6, text="casa",
                          fill="#ffe9a8", font=("Segoe UI", 7, "bold"))

    # -------------------------------------------------------------- salvar
    def _salvar(self):
        import time
        motor.salvar(self.cfg)
        self.lbl_estado.configure(text=f"salvo {time.strftime('%H:%M:%S')}")
        if self.ao_salvar:
            try:
                self.ao_salvar()
            except Exception:
                pass


def main():
    raiz = tk.Tk()
    raiz.withdraw()
    oficina = Oficina(raiz)
    oficina.protocol("WM_DELETE_WINDOW", raiz.destroy)
    raiz.mainloop()


if __name__ == "__main__":
    main()
