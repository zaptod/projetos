"""
FORJA DE ARMAS - NEURAL FIGHTS
Sistema de criação de armas com Wizard guiado
"""
import tkinter as tk
from tkinter import ttk, messagebox
import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    Arma, TIPOS_ARMA, LISTA_TIPOS_ARMA, RARIDADES, LISTA_RARIDADES,
    ENCANTAMENTOS, LISTA_ENCANTAMENTOS, get_raridade_data, get_tipo_arma_data,
    validar_arma_personagem, sugerir_tamanho_arma, calcular_tamanho_arma
)
from data import carregar_armas, salvar_lista_armas, carregar_personagens
from core import SKILL_DB
from ui.theme import COR_BG, COR_BG_SECUNDARIO, COR_HEADER, COR_ACCENT, COR_SUCCESS, COR_TEXTO, COR_TEXTO_DIM, CORES_RARIDADE

class TelaArmas(tk.Frame):
    """Tela principal da Forja de Armas com sistema Wizard"""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg=COR_BG)
        self.indice_em_edicao = None
        
        # Estado do Wizard
        self.passo_atual = 1
        self.total_passos = 6
        
        # Dados da arma sendo criada
        self.dados_arma = {
            "nome": "",
            "tipo": "Reta",
            "raridade": "Comum",
            "estilo": "",
            "dano": 10,
            "peso": 5,
            "geometria": {},
            "cores": {"r": 200, "g": 200, "b": 200},
            "habilidades": [],
            "encantamentos": [],
            "cabo_dano": False,
            "afinidade_elemento": None,
        }
        
        self.setup_ui()

    def setup_ui(self):
        """Configura a interface principal"""
        # Header
        self.criar_header()
        
        # Container principal dividido em 3 partes
        main = tk.Frame(self, bg=COR_BG)
        main.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Esquerda: Wizard Steps
        self.frame_wizard = tk.Frame(main, bg=COR_BG_SECUNDARIO, width=400)
        self.frame_wizard.pack(side="left", fill="y", padx=(0, 10))
        self.frame_wizard.pack_propagate(False)
        
        # Centro: Preview e controles
        self.frame_centro = tk.Frame(main, bg=COR_BG)
        self.frame_centro.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Direita: Lista de armas
        self.frame_lista = tk.Frame(main, bg=COR_BG_SECUNDARIO, width=300)
        self.frame_lista.pack(side="right", fill="y")
        self.frame_lista.pack_propagate(False)
        
        # Configura cada seção
        self.setup_wizard()
        self.setup_preview()
        self.setup_lista()
        
        # Inicia no passo 1
        self.mostrar_passo(1)

    def criar_header(self):
        """Cria o header com navegação"""
        header = tk.Frame(self, bg=COR_HEADER, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        # Botão voltar
        btn_voltar = tk.Button(
            header, text="< VOLTAR", bg=COR_ACCENT, fg=COR_TEXTO,
            font=("Arial", 10, "bold"), bd=0, padx=15,
            command=lambda: self.controller.show_frame("MenuPrincipal")
        )
        btn_voltar.pack(side="left", padx=10, pady=15)
        
        # Título
        tk.Label(
            header, text="FORJA DE ARMAS", 
            font=("Helvetica", 20, "bold"), bg=COR_HEADER, fg=COR_TEXTO
        ).pack(side="left", padx=20)
        
        # Indicador de progresso
        self.frame_progresso = tk.Frame(header, bg=COR_HEADER)
        self.frame_progresso.pack(side="right", padx=20)
        
        self.labels_progresso = []
        nomes_passos = ["Tipo", "Raridade", "Geometria", "Visual", "Habilidades", "Finalizar"]
        for i, nome in enumerate(nomes_passos, 1):
            cor = COR_SUCCESS if i == 1 else COR_TEXTO_DIM
            lbl = tk.Label(
                self.frame_progresso, text=f"{i}.{nome}",
                font=("Arial", 9), bg=COR_HEADER, fg=cor
            )
            lbl.pack(side="left", padx=5)
            self.labels_progresso.append(lbl)

    def atualizar_progresso(self):
        """Atualiza os indicadores de progresso"""
        for i, lbl in enumerate(self.labels_progresso, 1):
            if i < self.passo_atual:
                lbl.config(fg="#00ff88")  # Completo
            elif i == self.passo_atual:
                lbl.config(fg=COR_SUCCESS)  # Atual
            else:
                lbl.config(fg=COR_TEXTO_DIM)  # Futuro

    def setup_wizard(self):
        """Configura o frame do wizard"""
        # Título do passo
        self.lbl_passo_titulo = tk.Label(
            self.frame_wizard, text="", 
            font=("Helvetica", 14, "bold"), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        )
        self.lbl_passo_titulo.pack(pady=(15, 5))
        
        self.lbl_passo_desc = tk.Label(
            self.frame_wizard, text="", 
            font=("Arial", 10), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM,
            wraplength=380
        )
        self.lbl_passo_desc.pack(pady=(0, 15))
        
        # Container para conteúdo do passo
        self.frame_conteudo_passo = tk.Frame(self.frame_wizard, bg=COR_BG_SECUNDARIO)
        self.frame_conteudo_passo.pack(fill="both", expand=True, padx=15)
        
        # Botões de navegação
        frame_nav = tk.Frame(self.frame_wizard, bg=COR_BG_SECUNDARIO)
        frame_nav.pack(side="bottom", fill="x", pady=15, padx=15)
        
        self.btn_anterior = tk.Button(
            frame_nav, text="< Anterior", bg=COR_BG, fg=COR_TEXTO,
            font=("Arial", 10), bd=0, padx=20, pady=8,
            command=self.passo_anterior
        )
        self.btn_anterior.pack(side="left")
        
        self.btn_proximo = tk.Button(
            frame_nav, text="Proximo >", bg=COR_ACCENT, fg=COR_TEXTO,
            font=("Arial", 10, "bold"), bd=0, padx=20, pady=8,
            command=self.passo_proximo
        )
        self.btn_proximo.pack(side="right")

    def setup_preview(self):
        """Configura o preview da arma"""
        # Título
        tk.Label(
            self.frame_centro, text="PREVIEW", 
            font=("Arial", 12, "bold"), bg=COR_BG, fg=COR_TEXTO
        ).pack(pady=(10, 5))
        
        # Canvas do preview
        self.canvas_preview = tk.Canvas(
            self.frame_centro, bg=COR_BG_SECUNDARIO, 
            highlightthickness=2, highlightbackground=COR_ACCENT,
            height=300
        )
        self.canvas_preview.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Info da validação de tamanho
        self.frame_validacao = tk.Frame(self.frame_centro, bg=COR_BG)
        self.frame_validacao.pack(fill="x", padx=10, pady=5)
        
        self.lbl_validacao = tk.Label(
            self.frame_validacao, text="", 
            font=("Arial", 10), bg=COR_BG, fg=COR_TEXTO_DIM
        )
        self.lbl_validacao.pack()
        
        # Resumo dos stats
        self.frame_stats = tk.Frame(self.frame_centro, bg=COR_BG_SECUNDARIO)
        self.frame_stats.pack(fill="x", padx=10, pady=5)
        
        self.criar_resumo_stats()

    def criar_resumo_stats(self):
        """Cria o resumo de stats da arma"""
        for widget in self.frame_stats.winfo_children():
            widget.destroy()
        
        # Grid de stats
        stats = [
            ("Nome", self.dados_arma["nome"] or "???"),
            ("Tipo", self.dados_arma["tipo"]),
            ("Raridade", self.dados_arma["raridade"]),
            ("Dano", f"{self.dados_arma['dano']:.0f}"),
            ("Peso", f"{self.dados_arma['peso']:.1f} kg"),
            ("Skills", str(len(self.dados_arma["habilidades"]))),
        ]
        
        for i, (nome, valor) in enumerate(stats):
            row = i // 3
            col = i % 3
            
            frame = tk.Frame(self.frame_stats, bg=COR_BG_SECUNDARIO)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky="w")
            
            tk.Label(
                frame, text=f"{nome}:", 
                font=("Arial", 9), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM
            ).pack(side="left")
            
            cor = CORES_RARIDADE.get(valor, COR_TEXTO) if nome == "Raridade" else COR_TEXTO
            tk.Label(
                frame, text=valor, 
                font=("Arial", 9, "bold"), bg=COR_BG_SECUNDARIO, fg=cor
            ).pack(side="left", padx=5)

    def setup_lista(self):
        """Configura a lista de armas existentes"""
        tk.Label(
            self.frame_lista, text="ARSENAL", 
            font=("Arial", 12, "bold"), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        ).pack(pady=(15, 10))
        
        # Treeview com scroll
        frame_tree = tk.Frame(self.frame_lista, bg=COR_BG_SECUNDARIO)
        frame_tree.pack(fill="both", expand=True, padx=10)
        
        scroll = ttk.Scrollbar(frame_tree)
        scroll.pack(side="right", fill="y")
        
        cols = ("Nome", "Tipo", "Raridade")
        self.tree = ttk.Treeview(
            frame_tree, columns=cols, show="headings", height=15,
            yscrollcommand=scroll.set
        )
        scroll.config(command=self.tree.yview)
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=90)
        
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.selecionar_arma)
        
        # Botões
        frame_btns = tk.Frame(self.frame_lista, bg=COR_BG_SECUNDARIO)
        frame_btns.pack(fill="x", padx=10, pady=10)
        
        tk.Button(
            frame_btns, text="Deletar", bg="#cc3333", fg=COR_TEXTO,
            font=("Arial", 9), bd=0, padx=10, pady=5,
            command=self.deletar_arma
        ).pack(side="left")
        
        tk.Button(
            frame_btns, text="Editar", bg=COR_SUCCESS, fg=COR_BG,
            font=("Arial", 9, "bold"), bd=0, padx=10, pady=5,
            command=self.editar_arma
        ).pack(side="right")
        
        tk.Button(
            frame_btns, text="Nova", bg=COR_ACCENT, fg=COR_TEXTO,
            font=("Arial", 9), bd=0, padx=10, pady=5,
            command=self.nova_arma
        ).pack(side="right", padx=5)

    # =========================================================================
    # PASSOS DO WIZARD
    # =========================================================================
    
    def mostrar_passo(self, passo):
        """Mostra o passo especificado do wizard"""
        self.passo_atual = passo
        self.atualizar_progresso()
        
        # Limpa conteúdo anterior
        for widget in self.frame_conteudo_passo.winfo_children():
            widget.destroy()
        
        # Mostra passo apropriado
        if passo == 1:
            self.passo_tipo()
        elif passo == 2:
            self.passo_raridade()
        elif passo == 3:
            self.passo_geometria()
        elif passo == 4:
            self.passo_visual()
        elif passo == 5:
            self.passo_habilidades()
        elif passo == 6:
            self.passo_finalizar()
        
        # Atualiza botões
        self.btn_anterior.config(state="normal" if passo > 1 else "disabled")
        self.btn_proximo.config(
            text="FORJAR!" if passo == 6 else "Proximo >",
            bg="#00ff88" if passo == 6 else COR_ACCENT
        )
        
        self.atualizar_preview()
        self.criar_resumo_stats()

    def passo_anterior(self):
        """Volta ao passo anterior"""
        if self.passo_atual > 1:
            self.mostrar_passo(self.passo_atual - 1)

    def passo_proximo(self):
        """Avança para o próximo passo"""
        if self.passo_atual < 6:
            self.mostrar_passo(self.passo_atual + 1)
        else:
            self.salvar_arma()

    # -------------------------------------------------------------------------
    # PASSO 1: TIPO DA ARMA
    # -------------------------------------------------------------------------
    def passo_tipo(self):
        """Passo 1: Escolha do tipo de arma"""
        self.lbl_passo_titulo.config(text="1. TIPO DE ARMA")
        self.lbl_passo_desc.config(text="Escolha a categoria base da sua arma. Cada tipo tem comportamento unico em combate.")
        
        # Nome da arma
        frame_nome = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_nome.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            frame_nome, text="Nome da Arma:", 
            font=("Arial", 10), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        ).pack(anchor="w")
        
        self.entry_nome = tk.Entry(
            frame_nome, font=("Arial", 12), bg=COR_BG, fg=COR_TEXTO,
            insertbackground=COR_TEXTO
        )
        self.entry_nome.pack(fill="x", pady=5)
        self.entry_nome.insert(0, self.dados_arma["nome"])
        self.entry_nome.bind("<KeyRelease>", lambda e: self.atualizar_dado("nome", self.entry_nome.get()))
        
        # Grid de tipos
        tk.Label(
            self.frame_conteudo_passo, text="Categoria:", 
            font=("Arial", 10), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        ).pack(anchor="w", pady=(10, 5))
        
        frame_tipos = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_tipos.pack(fill="x")
        
        self.var_tipo = tk.StringVar(value=self.dados_arma["tipo"])
        
        # Organiza em grid 2x4
        for i, tipo in enumerate(LISTA_TIPOS_ARMA):
            dados = TIPOS_ARMA[tipo]
            row = i // 2
            col = i % 2
            
            frame = tk.Frame(frame_tipos, bg=COR_BG, bd=1, relief="solid")
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            rb = tk.Radiobutton(
                frame, text=tipo, variable=self.var_tipo, value=tipo,
                font=("Arial", 11, "bold"), bg=COR_BG, fg=COR_TEXTO,
                selectcolor=COR_BG_SECUNDARIO, activebackground=COR_BG,
                command=lambda t=tipo: self.selecionar_tipo(t)
            )
            rb.pack(anchor="w", padx=10, pady=(5, 0))
            
            tk.Label(
                frame, text=dados["descricao"],
                font=("Arial", 8), bg=COR_BG, fg=COR_TEXTO_DIM,
                wraplength=170
            ).pack(anchor="w", padx=10, pady=(0, 5))
        
        frame_tipos.columnconfigure(0, weight=1)
        frame_tipos.columnconfigure(1, weight=1)

    def selecionar_tipo(self, tipo):
        """Atualiza o tipo selecionado"""
        self.dados_arma["tipo"] = tipo
        dados_tipo = TIPOS_ARMA[tipo]
        self.dados_arma["estilo"] = dados_tipo["estilos"][0]
        self.atualizar_preview()
        self.criar_resumo_stats()

    # -------------------------------------------------------------------------
    # PASSO 2: RARIDADE
    # -------------------------------------------------------------------------
    def passo_raridade(self):
        """Passo 2: Escolha da raridade"""
        self.lbl_passo_titulo.config(text="2. RARIDADE")
        self.lbl_passo_desc.config(text="A raridade define o poder base, slots de habilidade e efeitos visuais da arma.")
        
        self.var_raridade = tk.StringVar(value=self.dados_arma["raridade"])
        
        for raridade in LISTA_RARIDADES:
            dados = RARIDADES[raridade]
            cor = CORES_RARIDADE[raridade]
            
            frame = tk.Frame(self.frame_conteudo_passo, bg=COR_BG, bd=2, relief="ridge")
            frame.pack(fill="x", pady=3)
            
            # Header com nome e cor
            header = tk.Frame(frame, bg=COR_BG)
            header.pack(fill="x", padx=10, pady=5)
            
            rb = tk.Radiobutton(
                header, text=raridade, variable=self.var_raridade, value=raridade,
                font=("Arial", 12, "bold"), bg=COR_BG, fg=cor,
                selectcolor=COR_BG_SECUNDARIO, activebackground=COR_BG,
                command=lambda r=raridade: self.selecionar_raridade(r)
            )
            rb.pack(side="left")
            
            # Stats
            stats_text = f"Dano:{dados['mod_dano']:.0%} Crit:{dados['mod_critico']:.0%} Vel:{dados['mod_velocidade_ataque']:.0%} Slots:{dados['slots_habilidade']}"
            tk.Label(
                header, text=stats_text,
                font=("Arial", 9), bg=COR_BG, fg=COR_TEXTO_DIM
            ).pack(side="right")
            
            # Descrição
            tk.Label(
                frame, text=dados["descricao"],
                font=("Arial", 9), bg=COR_BG, fg=COR_TEXTO_DIM
            ).pack(anchor="w", padx=10, pady=(0, 5))

    def selecionar_raridade(self, raridade):
        """Atualiza a raridade selecionada"""
        self.dados_arma["raridade"] = raridade
        # Aplica modificadores
        rar_data = RARIDADES[raridade]
        self.dados_arma["dano"] = 10 * rar_data["mod_dano"]
        self.atualizar_preview()
        self.criar_resumo_stats()

    # -------------------------------------------------------------------------
    # PASSO 3: GEOMETRIA
    # -------------------------------------------------------------------------
    def passo_geometria(self):
        """Passo 3: Configuração da geometria"""
        self.lbl_passo_titulo.config(text="3. GEOMETRIA")
        self.lbl_passo_desc.config(text="Configure as dimensoes fisicas da arma. Use o botao para sugestoes baseadas no personagem.")
        
        tipo = self.dados_arma["tipo"]
        dados_tipo = TIPOS_ARMA[tipo]
        
        # Estilo
        frame_estilo = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_estilo.pack(fill="x", pady=(0, 10))
        
        tk.Label(
            frame_estilo, text="Estilo:", 
            font=("Arial", 10), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        ).pack(anchor="w")
        
        self.combo_estilo = ttk.Combobox(
            frame_estilo, values=dados_tipo["estilos"], state="readonly"
        )
        self.combo_estilo.pack(fill="x", pady=5)
        self.combo_estilo.set(self.dados_arma.get("estilo") or dados_tipo["estilos"][0])
        self.combo_estilo.bind("<<ComboboxSelected>>", 
            lambda e: self.atualizar_dado("estilo", self.combo_estilo.get()))
        
        # Botão de sugestão
        btn_sugerir = tk.Button(
            self.frame_conteudo_passo, text="Sugerir Tamanhos (baseado no personagem)",
            bg=COR_SUCCESS, fg=COR_BG, font=("Arial", 9, "bold"),
            command=self.aplicar_sugestao_geometria
        )
        btn_sugerir.pack(fill="x", pady=10)
        
        # Stats base
        frame_stats = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_stats.pack(fill="x", pady=5)
        
        tk.Label(frame_stats, text="Dano Base:", bg=COR_BG_SECUNDARIO, fg=COR_TEXTO).grid(row=0, column=0, sticky="w", pady=2)
        self.scale_dano = tk.Scale(
            frame_stats, from_=1, to=50, orient="horizontal",
            bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, length=250,
            command=lambda v: self.atualizar_dado("dano", float(v))
        )
        self.scale_dano.set(self.dados_arma["dano"])
        self.scale_dano.grid(row=0, column=1, sticky="ew", pady=2)
        
        tk.Label(frame_stats, text="Peso (kg):", bg=COR_BG_SECUNDARIO, fg=COR_TEXTO).grid(row=1, column=0, sticky="w", pady=2)
        self.scale_peso = tk.Scale(
            frame_stats, from_=0.5, to=30, orient="horizontal", resolution=0.5,
            bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, length=250,
            command=lambda v: self.atualizar_dado("peso", float(v))
        )
        self.scale_peso.set(self.dados_arma["peso"])
        self.scale_peso.grid(row=1, column=1, sticky="ew", pady=2)
        
        frame_stats.columnconfigure(1, weight=1)
        
        # Sliders de geometria específicos do tipo
        self.sliders_geometria = {}
        self.criar_sliders_geometria(tipo)

    def criar_sliders_geometria(self, tipo):
        """Cria sliders específicos para o tipo de arma"""
        # Frame para os sliders
        frame_geo = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_geo.pack(fill="x", pady=10)
        
        configs = {
            "Reta": [
                ("comp_cabo", "Comp. Cabo", 1, 120),
                ("comp_lamina", "Comp. Lamina", 1, 150),
                ("largura", "Espessura", 1, 30),
            ],
            "Dupla": [
                ("comp_cabo", "Comp. Cabo", 1, 50),
                ("comp_lamina", "Comp. Lamina", 1, 80),
                ("largura", "Espessura", 1, 15),
                ("separacao", "Separacao", 5, 50),
            ],
            "Corrente": [
                ("comp_corrente", "Comp. Corrente", 50, 300),
                ("comp_ponta", "Comp. Ponta", 10, 50),
                ("largura_ponta", "Largura Ponta", 5, 30),
            ],
            "Arremesso": [
                ("tamanho_projetil", "Tamanho Projetil", 5, 40),
                ("largura", "Largura", 3, 20),
                ("quantidade", "Quantidade", 1, 8),
            ],
            "Arco": [
                ("tamanho_arco", "Tamanho Arco", 30, 120),
                ("forca_arco", "Forca", 1, 20),
                ("tamanho_flecha", "Tam. Flecha", 20, 80),
            ],
            "Orbital": [
                ("largura", "Tamanho", 10, 80),
                ("distancia", "Dist. Orbita", 15, 100),
                ("quantidade_orbitais", "Quantidade", 1, 6),
            ],
            "Mágica": [
                ("quantidade", "Quantidade", 1, 8),
                ("tamanho", "Tamanho", 5, 40),
                ("distancia_max", "Alcance", 30, 150),
            ],
            "Transformável": [
                ("forma1_cabo", "Forma1 Cabo", 10, 100),
                ("forma1_lamina", "Forma1 Lamina", 20, 120),
                ("forma2_cabo", "Forma2 Cabo", 10, 150),
                ("forma2_lamina", "Forma2 Lamina", 10, 80),
                ("largura", "Espessura", 2, 15),
            ],
        }
        
        for i, (key, label, minv, maxv) in enumerate(configs.get(tipo, [])):
            tk.Label(
                frame_geo, text=f"{label}:", 
                bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, font=("Arial", 9)
            ).grid(row=i, column=0, sticky="w", pady=2)
            
            val = self.dados_arma["geometria"].get(key, (minv + maxv) // 2)
            
            scale = tk.Scale(
                frame_geo, from_=minv, to=maxv, orient="horizontal",
                bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, length=250,
                command=lambda v, k=key: self.atualizar_geometria(k, float(v))
            )
            scale.set(val)
            scale.grid(row=i, column=1, sticky="ew", pady=2)
            self.sliders_geometria[key] = scale
        
        frame_geo.columnconfigure(1, weight=1)
        
        # Checkbox cabo dano (para Reta)
        if tipo == "Reta":
            self.var_cabo_dano = tk.BooleanVar(value=self.dados_arma["cabo_dano"])
            chk = tk.Checkbutton(
                frame_geo, text="Cabo causa dano?", variable=self.var_cabo_dano,
                bg=COR_BG_SECUNDARIO, fg=COR_ACCENT, selectcolor=COR_BG,
                command=lambda: self.atualizar_dado("cabo_dano", self.var_cabo_dano.get())
            )
            chk.grid(row=len(configs.get(tipo, [])), column=0, columnspan=2, sticky="w", pady=5)

    def atualizar_geometria(self, key, valor):
        """Atualiza um valor de geometria"""
        self.dados_arma["geometria"][key] = valor
        self.atualizar_preview()

    def aplicar_sugestao_geometria(self):
        """Aplica sugestões de tamanho baseadas no personagem selecionado"""
        # Tenta pegar um personagem para referência
        personagem = None
        if hasattr(self.controller, 'lista_chars') and self.controller.lista_chars:
            personagem = self.controller.lista_chars[0]
        
        sugestoes = sugerir_tamanho_arma(personagem, self.dados_arma["tipo"])
        
        for key, valor in sugestoes.items():
            self.dados_arma["geometria"][key] = valor
            if key in self.sliders_geometria:
                self.sliders_geometria[key].set(valor)
        
        self.atualizar_preview()
        messagebox.showinfo("Sugestao Aplicada", "Tamanhos sugeridos foram aplicados!")

    # -------------------------------------------------------------------------
    # PASSO 4: VISUAL
    # -------------------------------------------------------------------------
    def passo_visual(self):
        """Passo 4: Cores e aparência"""
        self.lbl_passo_titulo.config(text="4. VISUAL")
        self.lbl_passo_desc.config(text="Personalize as cores da sua arma.")
        
        # Sliders RGB
        cores = self.dados_arma["cores"]
        
        frame_cores = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_cores.pack(fill="x", pady=10)
        
        self.scales_cor = {}
        for i, (comp, nome) in enumerate([("r", "Vermelho"), ("g", "Verde"), ("b", "Azul")]):
            tk.Label(
                frame_cores, text=nome, 
                bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, font=("Arial", 10)
            ).grid(row=i, column=0, sticky="w", pady=5)
            
            scale = tk.Scale(
                frame_cores, from_=0, to=255, orient="horizontal",
                bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, length=280,
                command=lambda v, c=comp: self.atualizar_cor(c, int(v))
            )
            scale.set(cores[comp])
            scale.grid(row=i, column=1, sticky="ew", pady=5)
            self.scales_cor[comp] = scale
        
        frame_cores.columnconfigure(1, weight=1)
        
        # Preview de cor
        self.frame_cor_preview = tk.Frame(
            self.frame_conteudo_passo, bg=f"#{cores['r']:02x}{cores['g']:02x}{cores['b']:02x}",
            height=50, bd=2, relief="ridge"
        )
        self.frame_cor_preview.pack(fill="x", pady=10)
        
        # Presets de cores
        tk.Label(
            self.frame_conteudo_passo, text="Presets:", 
            bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        ).pack(anchor="w", pady=(10, 5))
        
        frame_presets = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_presets.pack(fill="x")
        
        presets = [
            ("Aco", 200, 200, 210),
            ("Bronze", 205, 127, 50),
            ("Ouro", 255, 215, 0),
            ("Obsidiana", 30, 30, 40),
            ("Jade", 0, 168, 107),
            ("Rubi", 224, 17, 95),
            ("Safira", 15, 82, 186),
            ("Ametista", 153, 102, 204),
        ]
        
        for nome, r, g, b in presets:
            btn = tk.Button(
                frame_presets, text=nome, 
                bg=f"#{r:02x}{g:02x}{b:02x}", 
                fg="white" if (r + g + b) < 400 else "black",
                font=("Arial", 8), bd=0, padx=8, pady=3,
                command=lambda r=r, g=g, b=b: self.aplicar_preset_cor(r, g, b)
            )
            btn.pack(side="left", padx=2, pady=2)

    def atualizar_cor(self, componente, valor):
        """Atualiza uma cor"""
        self.dados_arma["cores"][componente] = valor
        cores = self.dados_arma["cores"]
        self.frame_cor_preview.config(bg=f"#{cores['r']:02x}{cores['g']:02x}{cores['b']:02x}")
        self.atualizar_preview()

    def aplicar_preset_cor(self, r, g, b):
        """Aplica um preset de cor"""
        self.dados_arma["cores"] = {"r": r, "g": g, "b": b}
        for comp, val in [("r", r), ("g", g), ("b", b)]:
            self.scales_cor[comp].set(val)
        self.frame_cor_preview.config(bg=f"#{r:02x}{g:02x}{b:02x}")
        self.atualizar_preview()

    # -------------------------------------------------------------------------
    # PASSO 5: HABILIDADES
    # -------------------------------------------------------------------------
    def passo_habilidades(self):
        """Passo 5: Habilidades e encantamentos"""
        self.lbl_passo_titulo.config(text="5. HABILIDADES")
        
        raridade = self.dados_arma["raridade"]
        rar_data = RARIDADES[raridade]
        max_slots = rar_data["slots_habilidade"]
        max_enc = rar_data["max_encantamentos"]
        
        self.lbl_passo_desc.config(
            text=f"Raridade {raridade}: {max_slots} slot(s) de habilidade, {max_enc} encantamento(s)"
        )
        
        # === HABILIDADES ===
        tk.Label(
            self.frame_conteudo_passo, text="Habilidades:", 
            font=("Arial", 11, "bold"), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
        ).pack(anchor="w", pady=(5, 5))
        
        # Lista de skills disponíveis
        frame_skills = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
        frame_skills.pack(fill="x")
        
        lista_skills = ["Nenhuma"] + list(SKILL_DB.keys())
        
        self.combos_skill = []
        for i in range(max_slots):
            frame = tk.Frame(frame_skills, bg=COR_BG_SECUNDARIO)
            frame.pack(fill="x", pady=2)
            
            tk.Label(
                frame, text=f"Slot {i+1}:", 
                bg=COR_BG_SECUNDARIO, fg=COR_TEXTO, width=8
            ).pack(side="left")
            
            combo = ttk.Combobox(frame, values=lista_skills, state="readonly", width=25)
            combo.pack(side="left", padx=5)
            
            # Preenche com dados existentes
            if i < len(self.dados_arma["habilidades"]):
                hab = self.dados_arma["habilidades"][i]
                # Suporta tanto string quanto dict
                if isinstance(hab, dict):
                    combo.set(hab.get("nome", "Nenhuma"))
                else:
                    combo.set(str(hab) if hab else "Nenhuma")
            else:
                combo.set("Nenhuma")
            
            combo.bind("<<ComboboxSelected>>", lambda e, idx=i: self.atualizar_skill_slot(idx))
            self.combos_skill.append(combo)
            
            # Label de custo
            lbl_custo = tk.Label(
                frame, text="", 
                bg=COR_BG_SECUNDARIO, fg=COR_SUCCESS, font=("Arial", 9)
            )
            lbl_custo.pack(side="left", padx=5)
        
        # === ENCANTAMENTOS ===
        if max_enc > 0:
            tk.Label(
                self.frame_conteudo_passo, text="Encantamentos:", 
                font=("Arial", 11, "bold"), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO
            ).pack(anchor="w", pady=(15, 5))
            
            frame_enc = tk.Frame(self.frame_conteudo_passo, bg=COR_BG_SECUNDARIO)
            frame_enc.pack(fill="x")
            
            self.vars_encantamento = {}
            for enc_nome in LISTA_ENCANTAMENTOS[:8]:  # Mostra 8 principais
                dados_enc = ENCANTAMENTOS[enc_nome]
                
                var = tk.BooleanVar(value=enc_nome in self.dados_arma["encantamentos"])
                self.vars_encantamento[enc_nome] = var
                
                frame = tk.Frame(frame_enc, bg=COR_BG)
                frame.pack(fill="x", pady=2)
                
                cor = f"#{dados_enc['cor'][0]:02x}{dados_enc['cor'][1]:02x}{dados_enc['cor'][2]:02x}"
                
                chk = tk.Checkbutton(
                    frame, text=enc_nome, variable=var,
                    bg=COR_BG, fg=cor, selectcolor=COR_BG_SECUNDARIO,
                    font=("Arial", 10),
                    command=lambda n=enc_nome: self.toggle_encantamento(n)
                )
                chk.pack(side="left")
                
                tk.Label(
                    frame, text=dados_enc["descricao"],
                    bg=COR_BG, fg=COR_TEXTO_DIM, font=("Arial", 8)
                ).pack(side="left", padx=10)

    def atualizar_skill_slot(self, idx):
        """Atualiza um slot de habilidade"""
        nome = self.combos_skill[idx].get()
        
        # Reconstrói lista de habilidades
        habilidades = []
        for combo in self.combos_skill:
            skill_nome = combo.get()
            if skill_nome != "Nenhuma":
                custo = SKILL_DB.get(skill_nome, {}).get("custo", 0)
                habilidades.append({"nome": skill_nome, "custo": custo})
        
        self.dados_arma["habilidades"] = habilidades
        self.criar_resumo_stats()

    def toggle_encantamento(self, nome):
        """Toggle de encantamento"""
        max_enc = RARIDADES[self.dados_arma["raridade"]]["max_encantamentos"]
        
        if self.vars_encantamento[nome].get():
            if len(self.dados_arma["encantamentos"]) < max_enc:
                if nome not in self.dados_arma["encantamentos"]:
                    self.dados_arma["encantamentos"].append(nome)
            else:
                self.vars_encantamento[nome].set(False)
                messagebox.showwarning("Limite", f"Maximo de {max_enc} encantamentos para esta raridade!")
        else:
            if nome in self.dados_arma["encantamentos"]:
                self.dados_arma["encantamentos"].remove(nome)

    # -------------------------------------------------------------------------
    # PASSO 6: FINALIZAR
    # -------------------------------------------------------------------------
    def passo_finalizar(self):
        """Passo 6: Resumo e confirmação"""
        self.lbl_passo_titulo.config(text="6. FINALIZAR")
        self.lbl_passo_desc.config(text="Revise sua arma antes de forjar!")
        
        # Resumo completo
        dados = self.dados_arma
        raridade = dados["raridade"]
        cor_rar = CORES_RARIDADE[raridade]
        
        # Frame do resumo
        frame_resumo = tk.Frame(self.frame_conteudo_passo, bg=COR_BG, bd=2, relief="ridge")
        frame_resumo.pack(fill="both", expand=True, pady=10)
        
        # Nome em destaque
        tk.Label(
            frame_resumo, text=dados["nome"] or "Arma Sem Nome",
            font=("Arial", 18, "bold"), bg=COR_BG, fg=cor_rar
        ).pack(pady=(15, 5))
        
        tk.Label(
            frame_resumo, text=f"{dados['tipo']} {raridade}",
            font=("Arial", 12), bg=COR_BG, fg=COR_TEXTO_DIM
        ).pack()
        
        # Stats
        stats_frame = tk.Frame(frame_resumo, bg=COR_BG)
        stats_frame.pack(pady=15)
        
        rar_data = RARIDADES[raridade]
        dano_final = dados["dano"] * rar_data["mod_dano"]
        
        stats = [
            ("Dano", f"{dano_final:.0f}"),
            ("Peso", f"{dados['peso']:.1f}kg"),
            ("Critico", f"+{rar_data['mod_critico']:.0%}"),
            ("Vel.Ataque", f"{rar_data['mod_velocidade_ataque']:.0%}"),
        ]
        
        for i, (nome, valor) in enumerate(stats):
            tk.Label(
                stats_frame, text=f"{nome}: {valor}",
                font=("Arial", 11), bg=COR_BG, fg=COR_TEXTO
            ).grid(row=i//2, column=i%2, padx=20, pady=3, sticky="w")
        
        # Habilidades
        if dados["habilidades"]:
            tk.Label(
                frame_resumo, text="Habilidades:",
                font=("Arial", 10, "bold"), bg=COR_BG, fg=COR_SUCCESS
            ).pack(anchor="w", padx=15)
            
            for hab in dados["habilidades"]:
                # Suporta tanto string quanto dict
                if isinstance(hab, dict):
                    nome = hab.get('nome', 'Desconhecida')
                    custo = hab.get('custo', 0)
                    texto = f"  - {nome} ({custo} mana)"
                else:
                    texto = f"  - {hab}"
                tk.Label(
                    frame_resumo, text=texto,
                    font=("Arial", 9), bg=COR_BG, fg=COR_TEXTO
                ).pack(anchor="w", padx=15)
        
        # Encantamentos
        if dados["encantamentos"]:
            tk.Label(
                frame_resumo, text="Encantamentos:",
                font=("Arial", 10, "bold"), bg=COR_BG, fg="#FFD700"
            ).pack(anchor="w", padx=15, pady=(10, 0))
            
            for enc in dados["encantamentos"]:
                cor = ENCANTAMENTOS[enc]["cor"]
                cor_hex = f"#{cor[0]:02x}{cor[1]:02x}{cor[2]:02x}"
                tk.Label(
                    frame_resumo, text=f"  - {enc}",
                    font=("Arial", 9), bg=COR_BG, fg=cor_hex
                ).pack(anchor="w", padx=15)

    # =========================================================================
    # PREVIEW
    # =========================================================================
    
    def atualizar_preview(self):
        """Atualiza o preview visual da arma"""
        self.canvas_preview.delete("all")
        
        w = self.canvas_preview.winfo_width()
        h = self.canvas_preview.winfo_height()
        cx, cy = w/2, h/2
        
        if w < 50:
            return
        
        # Desenha personagem fantasma para referência
        raio_char = 30
        self.canvas_preview.create_oval(
            cx - raio_char, cy - raio_char, cx + raio_char, cy + raio_char,
            outline="#444", dash=(4, 4), width=2
        )
        self.canvas_preview.create_text(
            cx, cy, text="P", font=("Arial", 16, "bold"), fill="#555"
        )
        
        tipo = self.dados_arma["tipo"]
        cores = self.dados_arma["cores"]
        geo = self.dados_arma["geometria"]
        cor_hex = f"#{cores['r']:02x}{cores['g']:02x}{cores['b']:02x}"
        cor_raridade = CORES_RARIDADE[self.dados_arma["raridade"]]
        
        # Renderiza baseado no tipo
        if tipo == "Reta":
            self.desenhar_arma_reta(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Dupla":
            self.desenhar_arma_dupla(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Corrente":
            self.desenhar_arma_corrente(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Arremesso":
            self.desenhar_arma_arremesso(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Arco":
            self.desenhar_arma_arco(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Orbital":
            self.desenhar_arma_orbital(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Mágica":
            self.desenhar_arma_magica(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        elif tipo == "Transformável":
            self.desenhar_arma_transformavel(cx, cy, raio_char, geo, cor_hex, cor_raridade)
        
        # Borda de raridade
        self.canvas_preview.create_rectangle(
            5, 5, w-5, h-5, outline=cor_raridade, width=2
        )
        
        # Nome da raridade
        self.canvas_preview.create_text(
            w - 10, 15, text=self.dados_arma["raridade"],
            font=("Arial", 10, "bold"), fill=cor_raridade, anchor="e"
        )

    def desenhar_arma_reta(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Reta"""
        cabo = geo.get("comp_cabo", 20)
        lamina = geo.get("comp_lamina", 50)
        largura = geo.get("largura", 5)
        
        # Cabo
        self.canvas_preview.create_rectangle(
            cx + raio, cy - largura*0.3,
            cx + raio + cabo, cy + largura*0.3,
            fill="#8B4513", outline="#5C3317"
        )
        
        # Lamina
        self.canvas_preview.create_rectangle(
            cx + raio + cabo, cy - largura/2,
            cx + raio + cabo + lamina, cy + largura/2,
            fill=cor, outline=cor_rar, width=2
        )

    def desenhar_arma_dupla(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Dupla - Adagas Gêmeas (karambit style)"""
        import math as _math
        cabo = geo.get("comp_cabo", 15)
        lamina = geo.get("comp_lamina", 35)
        largura = geo.get("largura", 4)
        sep = geo.get("separacao", 20)
        
        for i, offset in enumerate([-sep * 0.7, sep * 0.7]):
            lado = -1 if i == 0 else 1
            bx = cx + raio + 10
            by = cy + offset
            # Anel de polegar
            self.canvas_preview.create_oval(
                bx - 4, by - 4, bx + 4, by + 4,
                outline="#C8C8D0", width=2
            )
            # Cabo
            cabo_ex = bx + cabo * 0.7
            cabo_ey = by + cabo * 0.2 * lado
            self.canvas_preview.create_line(
                bx, by, cabo_ex, cabo_ey,
                fill="#6B3A1F", width=max(2, int(largura))
            )
            # Lâmina curva (karambit arc) - arc de 90 graus
            arc_r = lamina * 0.6
            arc_cx = cabo_ex + arc_r * 0.3
            arc_cy = cabo_ey - arc_r * lado * 0.5
            self.canvas_preview.create_arc(
                arc_cx - arc_r, arc_cy - arc_r,
                arc_cx + arc_r, arc_cy + arc_r,
                start=150 if lado < 0 else 180,
                extent=100,
                style="arc", outline=cor, width=max(2, int(largura))
            )
            # Ponta com glow
            tip_x = arc_cx + _math.cos(_math.radians(240 if lado < 0 else 280)) * arc_r
            tip_y = arc_cy + _math.sin(_math.radians(240 if lado < 0 else 280)) * arc_r
            self.canvas_preview.create_oval(
                tip_x - 3, tip_y - 3, tip_x + 3, tip_y + 3,
                fill=cor_rar, outline=cor_rar
            )

    def desenhar_arma_corrente(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Corrente - Mangual (heavy flail) v3.0"""
        import math as _math
        comp = geo.get("comp_corrente", 100) * 0.7
        ponta_tam = max(12, int(geo.get("comp_ponta", 20) * 0.8))
        
        # Cabo de madeira
        cabo_tam = geo.get("comp_cabo", 18) * 0.5
        self.canvas_preview.create_rectangle(
            cx + raio, cy - 5, cx + raio + cabo_tam, cy + 5,
            fill="#6B3A1F", outline="#4A2810"
        )
        # Argola de conexão
        self.canvas_preview.create_oval(
            cx + raio + cabo_tam - 4, cy - 5, cx + raio + cabo_tam + 4, cy + 5,
            outline="#A0A5B0", width=2
        )
        
        # Elos da corrente (retângulos alternados horizontal/vertical)
        num_elos = 8
        elo_start_x = cx + raio + cabo_tam + 4
        for i in range(num_elos):
            t = i / num_elos
            ex = elo_start_x + comp * t
            ey = cy + _math.sin(t * _math.pi) * 15  # Catenary sag
            ew = 8 if i % 2 == 0 else 5
            eh = 4 if i % 2 == 0 else 7
            self.canvas_preview.create_rectangle(
                ex - ew//2, ey - eh//2, ex + ew//2, ey + eh//2,
                fill="#6A6C78", outline="#9A9CA8"
            )
        
        # Bola espigada no final
        ball_x = elo_start_x + comp + 4
        ball_y = cy + _math.sin(_math.pi * 0.9) * 15
        # Bola principal
        self.canvas_preview.create_oval(
            ball_x - ponta_tam, ball_y - ponta_tam,
            ball_x + ponta_tam, ball_y + ponta_tam,
            fill=cor, outline=cor_rar, width=2
        )
        # Spikes (4 visíveis no preview)
        for sa in [0, 90, 180, 270]:
            s_r = _math.radians(sa)
            sx1 = ball_x + _math.cos(s_r) * (ponta_tam - 1)
            sy1 = ball_y + _math.sin(s_r) * (ponta_tam - 1)
            sx2 = ball_x + _math.cos(s_r) * (ponta_tam + 7)
            sy2 = ball_y + _math.sin(s_r) * (ponta_tam + 7)
            self.canvas_preview.create_line(sx1, sy1, sx2, sy2,
                                            fill=cor, width=3)
        # Highlight da bola
        self.canvas_preview.create_oval(
            ball_x - ponta_tam//3, ball_y - ponta_tam//3,
            ball_x, ball_y,
            fill="#FFFFFF", outline=""
        )

    def desenhar_arma_arremesso(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Arremesso"""
        tam = geo.get("tamanho_projetil", 15)
        largura = geo.get("largura", 10)
        qtd = int(geo.get("quantidade", 3))
        
        for i in range(qtd):
            offset_y = (i - qtd/2) * 25
            # Projetil (forma de lamina de arremesso)
            pts = [
                cx + raio + 30, cy + offset_y,
                cx + raio + 30 + tam, cy + offset_y - largura/2,
                cx + raio + 30 + tam*1.5, cy + offset_y,
                cx + raio + 30 + tam, cy + offset_y + largura/2,
            ]
            self.canvas_preview.create_polygon(pts, fill=cor, outline=cor_rar, width=2)

    def desenhar_arma_arco(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Arco"""
        tam = geo.get("tamanho_arco", 60)
        flecha = geo.get("tamanho_flecha", 40)
        
        # Arco (curva)
        self.canvas_preview.create_arc(
            cx - tam/2, cy - tam/2, cx + tam/2, cy + tam/2,
            start=-60, extent=120, style="arc",
            outline=cor, width=4
        )
        
        # Corda
        self.canvas_preview.create_line(
            cx + tam/2 * math.cos(math.radians(60)), cy - tam/2 * math.sin(math.radians(60)),
            cx + tam/2 * math.cos(math.radians(-60)), cy - tam/2 * math.sin(math.radians(-60)),
            fill="#8B4513", width=2
        )
        
        # Flecha
        self.canvas_preview.create_line(
            cx, cy, cx + raio + flecha, cy,
            fill="#8B4513", width=2, arrow="last"
        )
        self.canvas_preview.create_polygon(
            cx + raio + flecha, cy,
            cx + raio + flecha - 10, cy - 5,
            cx + raio + flecha - 10, cy + 5,
            fill=cor_rar
        )

    def desenhar_arma_orbital(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Orbital"""
        largura = geo.get("largura", 40)
        dist = geo.get("distancia", 30)
        qtd = int(geo.get("quantidade_orbitais", 1))
        
        # Orbita
        raio_orbita = raio + dist
        self.canvas_preview.create_oval(
            cx - raio_orbita, cy - raio_orbita,
            cx + raio_orbita, cy + raio_orbita,
            outline="#333", dash=(2, 4)
        )
        
        # Elementos orbitais
        for i in range(qtd):
            ang = (360 / qtd) * i
            ox = cx + raio_orbita * math.cos(math.radians(ang))
            oy = cy + raio_orbita * math.sin(math.radians(ang))
            
            if largura > 30:  # Escudo
                self.canvas_preview.create_arc(
                    ox - largura/2, oy - largura/2, ox + largura/2, oy + largura/2,
                    start=ang - largura/2, extent=largura,
                    style="arc", outline=cor, width=5
                )
            else:  # Drone/Orbe
                self.canvas_preview.create_oval(
                    ox - largura/4, oy - largura/4, ox + largura/4, oy + largura/4,
                    fill=cor, outline=cor_rar, width=2
                )

    def desenhar_arma_magica(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Magica"""
        qtd = int(geo.get("quantidade", 3))
        tam = geo.get("tamanho", 15)
        dist = geo.get("distancia_max", 60)
        
        for i in range(qtd):
            ang = -30 + (60 / max(1, qtd-1)) * i if qtd > 1 else 0
            d = raio + dist * (0.5 + i * 0.2)
            ox = cx + d * math.cos(math.radians(ang))
            oy = cy + d * math.sin(math.radians(ang))
            
            # Espada espectral
            self.canvas_preview.create_polygon(
                ox, oy - tam/2,
                ox + tam*2, oy,
                ox, oy + tam/2,
                ox - tam/2, oy,
                fill=cor, outline=cor_rar, width=1, stipple="gray50"
            )

    def desenhar_arma_transformavel(self, cx, cy, raio, geo, cor, cor_rar):
        """Desenha arma do tipo Transformavel (mostra ambas formas)"""
        # Forma 1 (acima)
        cabo1 = geo.get("forma1_cabo", 20)
        lam1 = geo.get("forma1_lamina", 50)
        largura = geo.get("largura", 5)
        
        self.canvas_preview.create_text(cx - 50, cy - 30, text="Forma 1", fill="#888", font=("Arial", 8))
        self.canvas_preview.create_rectangle(
            cx + raio, cy - 30 - largura*0.3,
            cx + raio + cabo1, cy - 30 + largura*0.3,
            fill="#8B4513"
        )
        self.canvas_preview.create_rectangle(
            cx + raio + cabo1, cy - 30 - largura/2,
            cx + raio + cabo1 + lam1, cy - 30 + largura/2,
            fill=cor, outline=cor_rar, width=2
        )
        
        # Forma 2 (abaixo)
        cabo2 = geo.get("forma2_cabo", 80)
        lam2 = geo.get("forma2_lamina", 30)
        
        self.canvas_preview.create_text(cx - 50, cy + 30, text="Forma 2", fill="#888", font=("Arial", 8))
        self.canvas_preview.create_rectangle(
            cx + raio, cy + 30 - largura*0.3,
            cx + raio + cabo2, cy + 30 + largura*0.3,
            fill="#8B4513"
        )
        self.canvas_preview.create_rectangle(
            cx + raio + cabo2, cy + 30 - largura/2,
            cx + raio + cabo2 + lam2, cy + 30 + largura/2,
            fill=cor, outline=cor_rar, width=2
        )

    # =========================================================================
    # ACOES
    # =========================================================================
    
    def atualizar_dado(self, chave, valor):
        """Atualiza um dado da arma"""
        self.dados_arma[chave] = valor
        self.atualizar_preview()
        self.criar_resumo_stats()

    def salvar_arma(self):
        """Salva a arma no banco de dados"""
        dados = self.dados_arma
        
        if not dados["nome"]:
            messagebox.showerror("Erro", "A arma precisa de um nome!")
            return
        
        geo = dados["geometria"]
        cores = dados["cores"]
        
        try:
            nova = Arma(
                nome=dados["nome"],
                tipo=dados["tipo"],
                dano=dados["dano"],
                peso=dados["peso"],
                raridade=dados["raridade"],
                estilo=dados.get("estilo", ""),
                # Geometria basica
                comp_cabo=geo.get("comp_cabo", 0),
                comp_lamina=geo.get("comp_lamina", 0),
                largura=geo.get("largura", 0),
                distancia=geo.get("distancia", 0),
                # Geometria extra
                comp_corrente=geo.get("comp_corrente", 0),
                comp_ponta=geo.get("comp_ponta", 0),
                largura_ponta=geo.get("largura_ponta", 0),
                tamanho_projetil=geo.get("tamanho_projetil", 0),
                quantidade=geo.get("quantidade", 1),
                tamanho_arco=geo.get("tamanho_arco", 0),
                forca_arco=geo.get("forca_arco", 0),
                tamanho_flecha=geo.get("tamanho_flecha", 0),
                quantidade_orbitais=geo.get("quantidade_orbitais", 1),
                tamanho=geo.get("tamanho", 0),
                distancia_max=geo.get("distancia_max", 0),
                separacao=geo.get("separacao", 0),
                forma1_cabo=geo.get("forma1_cabo", 0),
                forma1_lamina=geo.get("forma1_lamina", 0),
                forma2_cabo=geo.get("forma2_cabo", 0),
                forma2_lamina=geo.get("forma2_lamina", 0),
                # Cores
                r=cores["r"], g=cores["g"], b=cores["b"],
                # Habilidades
                habilidades=dados["habilidades"],
                encantamentos=dados["encantamentos"],
                cabo_dano=dados["cabo_dano"],
                afinidade_elemento=dados["afinidade_elemento"],
            )
            
            if self.indice_em_edicao is not None:
                self.controller.lista_armas[self.indice_em_edicao] = nova
                self.indice_em_edicao = None
            else:
                self.controller.lista_armas.append(nova)
            
            salvar_lista_armas(self.controller.lista_armas)
            self.atualizar_lista()
            self.nova_arma()
            
            messagebox.showinfo(
                "Arma Forjada!", 
                f"{nova.nome} foi forjada com sucesso!\n"
                f"Raridade: {nova.raridade}\n"
                f"Dano: {nova.dano:.0f}"
            )
            
        except Exception as e:
            messagebox.showerror("Erro ao Forjar", str(e))

    def atualizar_lista(self):
        """Atualiza a lista de armas"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for arma in self.controller.lista_armas:
            raridade = getattr(arma, 'raridade', 'Comum')
            self.tree.insert("", "end", values=(arma.nome, arma.tipo, raridade))

    def _normalizar_habilidades(self, habilidades):
        """Converte lista de habilidades para formato padrão (lista de dicts)"""
        if not habilidades:
            return []
        
        resultado = []
        for hab in habilidades:
            if isinstance(hab, dict):
                # Já está no formato correto
                resultado.append(hab)
            elif isinstance(hab, str):
                # String simples - converte para dict
                custo = SKILL_DB.get(hab, {}).get("custo", 0)
                resultado.append({"nome": hab, "custo": custo})
            else:
                # Outro formato - tenta converter
                resultado.append({"nome": str(hab), "custo": 0})
        
        return resultado

    def selecionar_arma(self, event):
        """Seleciona uma arma da lista"""
        sel = self.tree.selection()
        if not sel:
            return
        
        idx = self.tree.index(sel[0])
        arma = self.controller.lista_armas[idx]
        
        # Preenche dados para edicao
        self.dados_arma = {
            "nome": arma.nome,
            "tipo": arma.tipo,
            "raridade": getattr(arma, 'raridade', 'Comum'),
            "estilo": arma.estilo,
            "dano": arma.dano_base if hasattr(arma, 'dano_base') else arma.dano,
            "peso": arma.peso_base if hasattr(arma, 'peso_base') else arma.peso,
            "geometria": {
                "comp_cabo": arma.comp_cabo,
                "comp_lamina": arma.comp_lamina,
                "largura": arma.largura,
                "distancia": arma.distancia,
                "comp_corrente": getattr(arma, 'comp_corrente', 0),
                "comp_ponta": getattr(arma, 'comp_ponta', 0),
                "largura_ponta": getattr(arma, 'largura_ponta', 0),
                "tamanho_projetil": getattr(arma, 'tamanho_projetil', 0),
                "quantidade": getattr(arma, 'quantidade', 1),
                "tamanho_arco": getattr(arma, 'tamanho_arco', 0),
                "forca_arco": getattr(arma, 'forca_arco', 0),
                "tamanho_flecha": getattr(arma, 'tamanho_flecha', 0),
                "quantidade_orbitais": getattr(arma, 'quantidade_orbitais', 1),
                "tamanho": getattr(arma, 'tamanho', 0),
                "distancia_max": getattr(arma, 'distancia_max', 0),
                "separacao": getattr(arma, 'separacao', 0),
                "forma1_cabo": getattr(arma, 'forma1_cabo', 0),
                "forma1_lamina": getattr(arma, 'forma1_lamina', 0),
                "forma2_cabo": getattr(arma, 'forma2_cabo', 0),
                "forma2_lamina": getattr(arma, 'forma2_lamina', 0),
            },
            "cores": {"r": arma.r, "g": arma.g, "b": arma.b},
            "habilidades": self._normalizar_habilidades(getattr(arma, 'habilidades', [])),
            "encantamentos": getattr(arma, 'encantamentos', []),
            "cabo_dano": arma.cabo_dano,
            "afinidade_elemento": getattr(arma, 'afinidade_elemento', None),
        }
        
        self.indice_em_edicao = idx
        self.mostrar_passo(1)

    def editar_arma(self):
        """Inicia edicao da arma selecionada"""
        self.selecionar_arma(None)

    def deletar_arma(self):
        """Deleta a arma selecionada"""
        sel = self.tree.selection()
        if not sel:
            return
        
        idx = self.tree.index(sel[0])
        arma = self.controller.lista_armas[idx]
        
        if messagebox.askyesno("Confirmar", f"Deletar '{arma.nome}'?"):
            del self.controller.lista_armas[idx]
            salvar_lista_armas(self.controller.lista_armas)
            self.atualizar_lista()

    def nova_arma(self):
        """Inicia criacao de nova arma"""
        self.indice_em_edicao = None
        self.dados_arma = {
            "nome": "",
            "tipo": "Reta",
            "raridade": "Comum",
            "estilo": "",
            "dano": 10,
            "peso": 5,
            "geometria": {},
            "cores": {"r": 200, "g": 200, "b": 200},
            "habilidades": [],
            "encantamentos": [],
            "cabo_dano": False,
            "afinidade_elemento": None,
        }
        self.mostrar_passo(1)

    def atualizar_dados(self):
        """Chamado quando a tela e exibida"""
        self.atualizar_lista()
