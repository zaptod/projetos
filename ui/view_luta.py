"""
ARENA DE COMBATE - NEURAL FIGHTS
Tela de seleção de lutadores para batalha
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation import simulacao
from ui.theme import (
    COR_BG, COR_BG_SECUNDARIO, COR_HEADER, COR_ACCENT, COR_SUCCESS,
    COR_TEXTO, COR_TEXTO_DIM, COR_WARNING, COR_P1, COR_P2, CORES_CLASSE
)


class TelaLuta(tk.Frame):
    """Tela de seleção de lutadores"""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg=COR_BG)
        
        self.personagem_p1 = None
        self.personagem_p2 = None
        
        self.setup_ui()

    def setup_ui(self):
        """Configura a interface"""
        # === HEADER ===
        header = tk.Frame(self, bg=COR_HEADER, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(
            header, text="◄ VOLTAR", 
            bg=COR_BG_SECUNDARIO, fg=COR_TEXTO,
            font=("Arial", 10, "bold"), bd=0, padx=15,
            command=lambda: self.controller.show_frame("MenuPrincipal")
        ).pack(side="left", padx=15, pady=15)
        
        tk.Label(
            header, text="⚔️ ARENA DE COMBATE",
            font=("Arial", 18, "bold"), bg=COR_HEADER, fg=COR_TEXTO
        ).pack(side="left", padx=20)

        # === FOOTER (botão iniciar) ===
        footer = tk.Frame(self, bg=COR_BG)
        footer.pack(fill="x", side="bottom", pady=15)
        
        self.btn_iniciar = tk.Button(
            footer, text="⚔️  INICIAR BATALHA  ⚔️",
            font=("Arial", 16, "bold"), 
            bg=COR_TEXTO_DIM, fg=COR_TEXTO,
            bd=0, padx=40, pady=12,
            state="disabled",
            command=self.iniciar_luta
        )
        self.btn_iniciar.pack()

        # === ÁREA PRINCIPAL ===
        main = tk.Frame(self, bg=COR_BG)
        main.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Configura 3 colunas com grid
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)
        main.grid_columnconfigure(2, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # === PLAYER 1 ===
        frame_p1 = tk.Frame(main, bg=COR_BG_SECUNDARIO, bd=2, relief="ridge")
        frame_p1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Título P1
        tk.Label(frame_p1, text="PLAYER 1", font=("Impact", 20), 
                 bg=COR_P1, fg=COR_TEXTO).pack(fill="x", pady=5)
        
        # Preview P1
        self.canvas_p1 = tk.Canvas(frame_p1, width=200, height=200, bg=COR_BG, highlightthickness=0)
        self.canvas_p1.pack(pady=10)
        
        self.lbl_nome_p1 = tk.Label(frame_p1, text="—", font=("Arial", 12, "bold"),
                                     bg=COR_BG_SECUNDARIO, fg=COR_TEXTO)
        self.lbl_nome_p1.pack()
        
        self.lbl_stats_p1 = tk.Label(frame_p1, text="", font=("Arial", 9),
                                      bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM, justify="center")
        self.lbl_stats_p1.pack(pady=5)
        
        # Lista P1
        tk.Label(frame_p1, text="Selecione:", font=("Arial", 9, "bold"),
                 bg=COR_BG_SECUNDARIO, fg=COR_TEXTO).pack(anchor="w", padx=10)
        
        frame_lista_p1 = tk.Frame(frame_p1, bg=COR_BG_SECUNDARIO)
        frame_lista_p1.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.listbox_p1 = tk.Listbox(
            frame_lista_p1, bg=COR_BG, fg=COR_TEXTO,
            selectbackground=COR_P1, selectforeground=COR_TEXTO,
            font=("Arial", 11), bd=0, highlightthickness=1,
            highlightcolor=COR_P1, activestyle="none"
        )
        scroll_p1 = ttk.Scrollbar(frame_lista_p1, orient="vertical", command=self.listbox_p1.yview)
        self.listbox_p1.configure(yscrollcommand=scroll_p1.set)
        
        self.listbox_p1.pack(side="left", fill="both", expand=True)
        scroll_p1.pack(side="right", fill="y")
        
        self.listbox_p1.bind("<<ListboxSelect>>", lambda e: self._on_select_p1())

        # === VS CENTRAL ===
        frame_vs = tk.Frame(main, bg=COR_BG, width=180)
        frame_vs.grid(row=0, column=1, sticky="ns", padx=10)
        
        tk.Label(frame_vs, text="", bg=COR_BG).pack(expand=True)  # Espaçador
        tk.Label(frame_vs, text="VS", font=("Impact", 50), bg=COR_BG, fg=COR_ACCENT).pack()
        
        # Config rápida
        frame_cfg = tk.Frame(frame_vs, bg=COR_BG_SECUNDARIO, padx=10, pady=10)
        frame_cfg.pack(pady=10)
        
        tk.Label(frame_cfg, text="⚙️ CONFIGURAÇÃO", font=("Arial", 10, "bold"), 
                 bg=COR_BG_SECUNDARIO, fg=COR_ACCENT).pack(pady=(0, 10))
        
        tk.Label(frame_cfg, text="Rounds:", font=("Arial", 9), 
                 bg=COR_BG_SECUNDARIO, fg=COR_TEXTO).pack()
        self.var_best_of = tk.StringVar(value="1")
        ttk.Combobox(frame_cfg, textvariable=self.var_best_of,
                     values=["1", "3", "5"], state="readonly", width=8).pack(pady=5)
        
        # === MODO RETRATO (9:16) ===
        tk.Label(frame_cfg, text="", bg=COR_BG_SECUNDARIO).pack(pady=2)  # Espaçador
        self.var_portrait = tk.BooleanVar(value=False)
        self.chk_portrait = tk.Checkbutton(
            frame_cfg, text="📱 Modo Retrato (9:16)",
            variable=self.var_portrait,
            font=("Arial", 9), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO,
            selectcolor=COR_BG, activebackground=COR_BG_SECUNDARIO,
            activeforeground=COR_ACCENT
        )
        self.chk_portrait.pack()
        tk.Label(frame_cfg, text="Ideal para TikTok/Reels",
                 font=("Arial", 7), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM).pack()
        
        # === SELETOR DE MAPA ===
        tk.Label(frame_cfg, text="", bg=COR_BG_SECUNDARIO).pack(pady=5)  # Espaçador
        tk.Label(frame_cfg, text="🗺️ MAPA:", font=("Arial", 10, "bold"), 
                 bg=COR_BG_SECUNDARIO, fg=COR_ACCENT).pack()
        
        self.var_cenario = tk.StringVar(value="Arena")
        
        # Botão de seleção de mapa
        self.btn_mapa = tk.Button(
            frame_cfg, text="🏟️ Arena Clássica",
            font=("Arial", 9, "bold"), bg=COR_BG, fg=COR_TEXTO,
            bd=1, relief="ridge", width=16, height=2,
            command=self._abrir_seletor_mapa
        )
        self.btn_mapa.pack(pady=5)
        
        # Info do mapa selecionado
        self.lbl_mapa_info = tk.Label(
            frame_cfg, text="30x20m • Retangular\n0 obstáculos",
            font=("Arial", 8), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM,
            justify="center"
        )
        self.lbl_mapa_info.pack()
        
        tk.Label(frame_vs, text="", bg=COR_BG).pack(expand=True)  # Espaçador

        # === PLAYER 2 ===
        frame_p2 = tk.Frame(main, bg=COR_BG_SECUNDARIO, bd=2, relief="ridge")
        frame_p2.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        
        # Título P2
        tk.Label(frame_p2, text="PLAYER 2", font=("Impact", 20), 
                 bg=COR_P2, fg=COR_TEXTO).pack(fill="x", pady=5)
        
        # Preview P2
        self.canvas_p2 = tk.Canvas(frame_p2, width=200, height=200, bg=COR_BG, highlightthickness=0)
        self.canvas_p2.pack(pady=10)
        
        self.lbl_nome_p2 = tk.Label(frame_p2, text="—", font=("Arial", 12, "bold"),
                                     bg=COR_BG_SECUNDARIO, fg=COR_TEXTO)
        self.lbl_nome_p2.pack()
        
        self.lbl_stats_p2 = tk.Label(frame_p2, text="", font=("Arial", 9),
                                      bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM, justify="center")
        self.lbl_stats_p2.pack(pady=5)
        
        # Lista P2
        tk.Label(frame_p2, text="Selecione:", font=("Arial", 9, "bold"),
                 bg=COR_BG_SECUNDARIO, fg=COR_TEXTO).pack(anchor="w", padx=10)
        
        frame_lista_p2 = tk.Frame(frame_p2, bg=COR_BG_SECUNDARIO)
        frame_lista_p2.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.listbox_p2 = tk.Listbox(
            frame_lista_p2, bg=COR_BG, fg=COR_TEXTO,
            selectbackground=COR_P2, selectforeground=COR_TEXTO,
            font=("Arial", 11), bd=0, highlightthickness=1,
            highlightcolor=COR_P2, activestyle="none"
        )
        scroll_p2 = ttk.Scrollbar(frame_lista_p2, orient="vertical", command=self.listbox_p2.yview)
        self.listbox_p2.configure(yscrollcommand=scroll_p2.set)
        
        self.listbox_p2.pack(side="left", fill="both", expand=True)
        scroll_p2.pack(side="right", fill="y")
        
        self.listbox_p2.bind("<<ListboxSelect>>", lambda e: self._on_select_p2())

    def atualizar_dados(self):
        """Atualiza listas de personagens"""
        # Limpa
        self.listbox_p1.delete(0, tk.END)
        self.listbox_p2.delete(0, tk.END)
        self.personagem_p1 = None
        self.personagem_p2 = None
        
        personagens = self.controller.lista_personagens
        
        if not personagens:
            self.listbox_p1.insert(tk.END, "(Nenhum personagem)")
            self.listbox_p2.insert(tk.END, "(Nenhum personagem)")
            self._atualizar_botao()
            return
        
        # Popula listas
        for p in personagens:
            classe = getattr(p, 'classe', 'Guerreiro')
            texto = f"{p.nome} ({classe})"
            self.listbox_p1.insert(tk.END, texto)
            self.listbox_p2.insert(tk.END, texto)
        
        # Auto-seleciona
        if len(personagens) >= 1:
            self.listbox_p1.selection_set(0)
            self._on_select_p1()
        if len(personagens) >= 2:
            self.listbox_p2.selection_set(1)
            self._on_select_p2()
        elif len(personagens) == 1:
            self.listbox_p2.selection_set(0)
            self._on_select_p2()

    def _on_select_p1(self):
        """Callback quando P1 seleciona"""
        sel = self.listbox_p1.curselection()
        if not sel:
            return
        idx = sel[0]
        personagens = self.controller.lista_personagens
        if idx < len(personagens):
            self.personagem_p1 = personagens[idx]
            self._desenhar_preview(self.personagem_p1, self.canvas_p1, self.lbl_nome_p1, self.lbl_stats_p1, COR_P1)
        self._atualizar_botao()

    def _on_select_p2(self):
        """Callback quando P2 seleciona"""
        sel = self.listbox_p2.curselection()
        if not sel:
            return
        idx = sel[0]
        personagens = self.controller.lista_personagens
        if idx < len(personagens):
            self.personagem_p2 = personagens[idx]
            self._desenhar_preview(self.personagem_p2, self.canvas_p2, self.lbl_nome_p2, self.lbl_stats_p2, COR_P2)
        self._atualizar_botao()

    def _desenhar_preview(self, p, canvas, lbl_nome, lbl_stats, cor_borda):
        """Desenha preview do personagem"""
        canvas.delete("all")
        
        if not p:
            lbl_nome.config(text="—")
            lbl_stats.config(text="")
            return
        
        lbl_nome.config(text=p.nome)
        
        cx, cy = 100, 100
        cor = f"#{p.cor_r:02x}{p.cor_g:02x}{p.cor_b:02x}"
        classe = getattr(p, 'classe', 'Guerreiro')
        cor_classe = CORES_CLASSE.get(classe, "#808080")
        
        # Aura
        canvas.create_oval(cx-60, cy-60, cx+60, cy+60, outline=cor_classe, width=2, dash=(4,2))
        
        # Personagem
        raio = min(p.tamanho * 6, 40)
        canvas.create_oval(cx-raio, cy-raio, cx+raio, cy+raio, fill=cor, outline=cor_borda, width=3)
        
        # Classe
        canvas.create_text(cx, cy+70, text=classe, font=("Arial", 10, "bold"), fill=cor_classe)
        
        # Arma
        if p.nome_arma:
            arma = next((a for a in self.controller.lista_armas if a.nome == p.nome_arma), None)
            if arma:
                cor_arma = f"#{arma.r:02x}{arma.g:02x}{arma.b:02x}"
                canvas.create_line(cx+raio, cy, cx+raio+40, cy, fill=cor_arma, width=4)
        
        # Stats
        arma_txt = p.nome_arma if p.nome_arma else "Mãos Vazias"
        stats = f"VEL: {p.velocidade:.1f} | RES: {p.resistencia:.1f}\n🗡️ {arma_txt}"
        lbl_stats.config(text=stats)

    def _atualizar_botao(self):
        """Atualiza estado do botão"""
        if self.personagem_p1 and self.personagem_p2:
            self.btn_iniciar.config(state="normal", bg=COR_ACCENT)
        else:
            self.btn_iniciar.config(state="disabled", bg=COR_TEXTO_DIM)

    def _abrir_seletor_mapa(self):
        """Abre a janela de seleção de mapa"""
        SeletorMapa(self, self._on_mapa_selecionado)
    
    def _on_mapa_selecionado(self, mapa_key: str, mapa_info: dict):
        """Callback quando um mapa é selecionado"""
        self.var_cenario.set(mapa_key)
        
        # Atualiza botão
        self.btn_mapa.config(text=f"{mapa_info['icone']} {mapa_info['nome']}")
        
        # Atualiza info
        info_text = f"{mapa_info['tamanho']} • {mapa_info['formato']}\n{mapa_info['obstaculos']} obstáculos"
        self.lbl_mapa_info.config(text=info_text)

    def iniciar_luta(self):
        """Inicia a simulação"""
        if not self.personagem_p1 or not self.personagem_p2:
            messagebox.showwarning("Atenção", "Selecione dois campeões!")
            return
        
        match_data = {
            "p1_nome": self.personagem_p1.nome,
            "p2_nome": self.personagem_p2.nome,
            "cenario": self.var_cenario.get(),
            "best_of": int(self.var_best_of.get()),
            "portrait_mode": self.var_portrait.get(),
        }
        
        try:
            with open("match_config.json", "w", encoding="utf-8") as f:
                json.dump(match_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar: {e}")
            return
        
        self.controller.withdraw()
        
        try:
            sim = simulacao.Simulador()
            sim.run()
        except Exception as e:
            messagebox.showerror("Erro", f"Simulação falhou:\n{e}")
        
        self.controller.deiconify()

    # Compatibilidade
    def atualizar_previews(self, event=None):
        pass


# =============================================================================
# SELETOR DE MAPA - JANELA POPUP
# =============================================================================

class SeletorMapa(tk.Toplevel):
    """Janela de seleção de mapa com preview visual"""
    
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        
        self.title("🗺️ Selecionar Mapa")
        self.geometry("900x650")
        self.configure(bg=COR_BG)
        self.resizable(False, False)
        
        # Centraliza
        self.transient(parent)
        self.grab_set()
        
        # Importa dados dos mapas
        from core.arena import ARENAS, LISTA_MAPAS, get_mapa_info
        self.ARENAS = ARENAS
        self.LISTA_MAPAS = LISTA_MAPAS
        self.get_mapa_info = get_mapa_info
        
        self.mapa_selecionado = "Arena"
        
        self._setup_ui()
        self._selecionar_mapa("Arena")
    
    def _setup_ui(self):
        """Configura a interface"""
        # Header
        header = tk.Frame(self, bg=COR_HEADER, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(
            header, text="🗺️ ESCOLHA O CAMPO DE BATALHA",
            font=("Arial", 16, "bold"), bg=COR_HEADER, fg=COR_TEXTO
        ).pack(pady=12)
        
        # Container principal
        main = tk.Frame(self, bg=COR_BG)
        main.pack(fill="both", expand=True, padx=15, pady=10)
        
        # === LISTA DE MAPAS (esquerda) ===
        frame_lista = tk.Frame(main, bg=COR_BG_SECUNDARIO, width=280)
        frame_lista.pack(side="left", fill="y", padx=(0, 10))
        frame_lista.pack_propagate(False)
        
        tk.Label(
            frame_lista, text="MAPAS DISPONÍVEIS",
            font=("Arial", 11, "bold"), bg=COR_BG_SECUNDARIO, fg=COR_ACCENT
        ).pack(pady=10)
        
        # Canvas com scroll para lista de mapas
        canvas_container = tk.Frame(frame_lista, bg=COR_BG_SECUNDARIO)
        canvas_container.pack(fill="both", expand=True, padx=5, pady=(0, 10))
        
        canvas = tk.Canvas(canvas_container, bg=COR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        
        self.frame_mapas = tk.Frame(canvas, bg=COR_BG)
        
        canvas.create_window((0, 0), window=self.frame_mapas, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Popula lista de mapas
        self.botoes_mapa = {}
        for mapa_key in self.LISTA_MAPAS:
            info = self.get_mapa_info(mapa_key)
            if not info:
                continue
            
            btn = tk.Button(
                self.frame_mapas,
                text=f"{info['icone']}  {info['nome']}",
                font=("Arial", 10), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO,
                bd=1, relief="ridge", anchor="w", padx=10,
                width=24, height=2,
                command=lambda k=mapa_key: self._selecionar_mapa(k)
            )
            btn.pack(fill="x", pady=2, padx=5)
            self.botoes_mapa[mapa_key] = btn
        
        # Atualiza scroll region
        self.frame_mapas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # === PREVIEW DO MAPA (direita) ===
        frame_preview = tk.Frame(main, bg=COR_BG_SECUNDARIO)
        frame_preview.pack(side="right", fill="both", expand=True)
        
        # Nome do mapa
        self.lbl_nome_mapa = tk.Label(
            frame_preview, text="Arena Clássica",
            font=("Impact", 24), bg=COR_BG_SECUNDARIO, fg=COR_ACCENT
        )
        self.lbl_nome_mapa.pack(pady=(15, 5))
        
        # Canvas para preview visual
        self.canvas_preview = tk.Canvas(
            frame_preview, width=400, height=300,
            bg=COR_BG, highlightthickness=2, highlightcolor=COR_ACCENT
        )
        self.canvas_preview.pack(pady=10)
        
        # Info do mapa
        self.lbl_descricao = tk.Label(
            frame_preview, text="Arena padrão sem obstáculos",
            font=("Arial", 11), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO,
            wraplength=350
        )
        self.lbl_descricao.pack(pady=5)
        
        # Stats do mapa
        frame_stats = tk.Frame(frame_preview, bg=COR_BG_SECUNDARIO)
        frame_stats.pack(pady=10)
        
        self.lbl_stats = tk.Label(
            frame_stats, text="",
            font=("Arial", 10), bg=COR_BG_SECUNDARIO, fg=COR_TEXTO_DIM,
            justify="center"
        )
        self.lbl_stats.pack()
        
        # === FOOTER ===
        footer = tk.Frame(self, bg=COR_BG)
        footer.pack(fill="x", pady=15)
        
        tk.Button(
            footer, text="Cancelar",
            font=("Arial", 11), bg=COR_TEXTO_DIM, fg=COR_TEXTO,
            bd=0, padx=20, pady=8,
            command=self.destroy
        ).pack(side="left", padx=20)
        
        self.btn_confirmar = tk.Button(
            footer, text="✓ CONFIRMAR MAPA",
            font=("Arial", 12, "bold"), bg=COR_ACCENT, fg=COR_TEXTO,
            bd=0, padx=30, pady=10,
            command=self._confirmar
        )
        self.btn_confirmar.pack(side="right", padx=20)
    
    def _selecionar_mapa(self, mapa_key: str):
        """Seleciona um mapa e atualiza preview"""
        self.mapa_selecionado = mapa_key
        info = self.get_mapa_info(mapa_key)
        config = self.ARENAS.get(mapa_key)
        
        if not info or not config:
            return
        
        # Atualiza destaque dos botões
        for key, btn in self.botoes_mapa.items():
            if key == mapa_key:
                btn.config(bg=COR_ACCENT, fg="white")
            else:
                btn.config(bg=COR_BG_SECUNDARIO, fg=COR_TEXTO)
        
        # Atualiza labels
        self.lbl_nome_mapa.config(text=f"{info['icone']} {info['nome']}")
        self.lbl_descricao.config(text=info['descricao'])
        
        stats_text = f"📏 Tamanho: {info['tamanho']}\n"
        stats_text += f"🔷 Formato: {info['formato']}\n"
        stats_text += f"🧱 Obstáculos: {info['obstaculos']}\n"
        stats_text += f"🎨 Tema: {info['tema'].capitalize()}"
        self.lbl_stats.config(text=stats_text)
        
        # Desenha preview
        self._desenhar_preview(config)
    
    def _desenhar_preview(self, config):
        """Desenha preview visual do mapa"""
        canvas = self.canvas_preview
        canvas.delete("all")
        
        # Dimensões do canvas
        cw, ch = 400, 300
        padding = 20
        
        # Escala para caber no canvas
        escala_x = (cw - padding * 2) / config.largura
        escala_y = (ch - padding * 2) / config.altura
        escala = min(escala_x, escala_y)
        
        # Offset para centralizar
        offset_x = (cw - config.largura * escala) / 2
        offset_y = (ch - config.altura * escala) / 2
        
        def to_canvas(x, y):
            return offset_x + x * escala, offset_y + y * escala
        
        # Cor do chão
        cor_chao = f"#{config.cor_chao[0]:02x}{config.cor_chao[1]:02x}{config.cor_chao[2]:02x}"
        cor_borda = f"#{config.cor_borda[0]:02x}{config.cor_borda[1]:02x}{config.cor_borda[2]:02x}"
        
        # Desenha formato base
        if config.formato == "circular":
            cx, cy = to_canvas(config.largura / 2, config.altura / 2)
            raio = min(config.largura, config.altura) / 2 * escala * 0.9
            canvas.create_oval(
                cx - raio, cy - raio, cx + raio, cy + raio,
                fill=cor_chao, outline=cor_borda, width=3
            )
        elif config.formato == "octogono":
            # Octógono
            w, h = config.largura * escala, config.altura * escala
            corte = min(w, h) * 0.2
            pontos = [
                to_canvas(config.largura * 0.2, 0),
                to_canvas(config.largura * 0.8, 0),
                to_canvas(config.largura, config.altura * 0.2),
                to_canvas(config.largura, config.altura * 0.8),
                to_canvas(config.largura * 0.8, config.altura),
                to_canvas(config.largura * 0.2, config.altura),
                to_canvas(0, config.altura * 0.8),
                to_canvas(0, config.altura * 0.2),
            ]
            flat_pontos = [coord for p in pontos for coord in p]
            canvas.create_polygon(flat_pontos, fill=cor_chao, outline=cor_borda, width=3)
        else:
            # Retangular
            x1, y1 = to_canvas(0, 0)
            x2, y2 = to_canvas(config.largura, config.altura)
            canvas.create_rectangle(x1, y1, x2, y2, fill=cor_chao, outline=cor_borda, width=3)
        
        # Desenha grid
        grid_cor = f"#{min(255, config.cor_chao[0]+15):02x}{min(255, config.cor_chao[1]+15):02x}{min(255, config.cor_chao[2]+15):02x}"
        grid_size = 4.0  # Metros
        
        x = 0
        while x <= config.largura:
            p1 = to_canvas(x, 0)
            p2 = to_canvas(x, config.altura)
            canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=grid_cor, dash=(2, 4))
            x += grid_size
        
        y = 0
        while y <= config.altura:
            p1 = to_canvas(0, y)
            p2 = to_canvas(config.largura, y)
            canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=grid_cor, dash=(2, 4))
            y += grid_size
        
        # Desenha obstáculos
        for obs in config.obstaculos:
            cx, cy = to_canvas(obs.x, obs.y)
            half_w = obs.largura * escala / 2
            half_h = obs.altura * escala / 2
            
            cor = f"#{obs.cor[0]:02x}{obs.cor[1]:02x}{obs.cor[2]:02x}"
            cor_escura = f"#{max(0,obs.cor[0]-40):02x}{max(0,obs.cor[1]-40):02x}{max(0,obs.cor[2]-40):02x}"
            
            if obs.tipo in ["lava", "fogo"]:
                # Vermelho/laranja brilhante
                canvas.create_oval(
                    cx - half_w, cy - half_h, cx + half_w, cy + half_h,
                    fill="#FF4500", outline="#FFD700", width=2
                )
            elif obs.tipo == "cristal":
                # Hexágono brilhante
                pontos = [
                    (cx, cy - half_h),
                    (cx + half_w * 0.8, cy - half_h * 0.5),
                    (cx + half_w * 0.8, cy + half_h * 0.5),
                    (cx, cy + half_h),
                    (cx - half_w * 0.8, cy + half_h * 0.5),
                    (cx - half_w * 0.8, cy - half_h * 0.5),
                ]
                flat = [coord for p in pontos for coord in p]
                canvas.create_polygon(flat, fill=cor, outline="white", width=1)
            elif obs.tipo in ["arvore", "palmeira"]:
                # Círculo verde com tronco
                canvas.create_rectangle(
                    cx - half_w * 0.2, cy - half_h * 0.3,
                    cx + half_w * 0.2, cy + half_h * 0.5,
                    fill=cor, outline=""
                )
                canvas.create_oval(
                    cx - half_w, cy - half_h, cx + half_w, cy,
                    fill="#228B22", outline="#006400", width=1
                )
            elif obs.tipo in ["pilar", "pilar_quebrado"]:
                # Círculo
                canvas.create_oval(
                    cx - half_w, cy - half_h, cx + half_w, cy + half_h,
                    fill=cor, outline=cor_escura, width=2
                )
            elif obs.tipo == "gelo":
                # Azul claro transparente
                canvas.create_rectangle(
                    cx - half_w, cy - half_h, cx + half_w, cy + half_h,
                    fill="#ADD8E6", outline="#87CEEB", width=2
                )
            elif obs.tipo == "nucleo":
                # Círculo brilhante
                canvas.create_oval(
                    cx - half_w * 1.3, cy - half_h * 1.3,
                    cx + half_w * 1.3, cy + half_h * 1.3,
                    fill="#1E3A5F", outline=""
                )
                canvas.create_oval(
                    cx - half_w, cy - half_h, cx + half_w, cy + half_h,
                    fill=cor, outline="white", width=2
                )
            else:
                # Retângulo genérico
                canvas.create_rectangle(
                    cx - half_w, cy - half_h, cx + half_w, cy + half_h,
                    fill=cor, outline=cor_escura, width=1
                )
        
        # Desenha pontos de spawn
        spawn_cor_p1 = "#3498DB"
        spawn_cor_p2 = "#E74C3C"
        
        p1_x, p1_y = to_canvas(config.largura * 0.2, config.altura / 2)
        p2_x, p2_y = to_canvas(config.largura * 0.8, config.altura / 2)
        
        # P1
        canvas.create_oval(p1_x - 8, p1_y - 8, p1_x + 8, p1_y + 8, fill=spawn_cor_p1, outline="white", width=2)
        canvas.create_text(p1_x, p1_y, text="1", fill="white", font=("Arial", 8, "bold"))
        
        # P2
        canvas.create_oval(p2_x - 8, p2_y - 8, p2_x + 8, p2_y + 8, fill=spawn_cor_p2, outline="white", width=2)
        canvas.create_text(p2_x, p2_y, text="2", fill="white", font=("Arial", 8, "bold"))
        
        # Legenda de spawn
        canvas.create_text(cw/2, ch - 10, text="● P1 Spawn   ● P2 Spawn", fill="#888888", font=("Arial", 8))
    
    def _confirmar(self):
        """Confirma a seleção do mapa"""
        info = self.get_mapa_info(self.mapa_selecionado)
        self.callback(self.mapa_selecionado, info)
        self.destroy()