# main.py
import tkinter as tk
from tkinter import messagebox, ttk
import ctypes

from neural_fights.data import database

# --- IMPORTANDO AS TELAS (VIEWS) ---
from neural_fights.ui.view_armas import TelaArmas
from neural_fights.ui.view_chars import TelaPersonagens
from neural_fights.ui.view_luta import TelaLuta
from neural_fights.ui.view_sons import TelaSons
from neural_fights.ui.theme import (
    BotaoCanvas, CartaoMenu, COR_BG, COR_ACCENT, COR_TEXTO_DIM, CORES_CLASSE,
    CORES_RARIDADE, criar_titulo,
)

# Configurações Visuais Globais
COR_FUNDO = COR_BG
COR_TEXTO = "#ECF0F1"


def area_util_tela(root):
    """Retorna a work area do Windows, sem deixar a barra cobrir o launcher."""
    try:
        class Rect(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                       ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        rect = Rect()
        if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except (AttributeError, OSError):
        pass
    return 0, 0, root.winfo_screenwidth(), max(620, root.winfo_screenheight() - 40)

class SistemaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Neural Fights - Launcher & Gerenciador")
        esquerda, topo, largura, altura = area_util_tela(self)
        largura_inicial, altura_inicial = min(1280, largura), min(720, altura)
        self.geometry(f"{largura_inicial}x{altura_inicial}+{esquerda}+{topo}")
        self.maxsize(largura, altura)
        self.minsize(min(900, largura), min(620, altura))
        self.configure(bg=COR_FUNDO)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=COR_BG, fieldbackground=COR_BG,
                        foreground=COR_TEXTO, rowheight=30, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=COR_ACCENT, foreground=COR_TEXTO,
                        font=("Segoe UI Semibold", 9))

        # Carrega dados iniciais
        self.lista_armas = []
        self.lista_personagens = []
        self.recarregar_dados() # Carrega do disco

        # --- ESTRUTURA DE NAVEGAÇÃO ---
        container = tk.Frame(self, bg=COR_FUNDO)
        container.pack(side="top", fill="both", expand=True)
        
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        # Registra todas as telas (Menu, Armas, Personagens, Luta, Interações, Sons)
        for F in (MenuPrincipal, TelaArmas, TelaPersonagens, TelaLuta, TelaInteracoes, TelaSons):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("MenuPrincipal")
        
        # Referência para janela do torneio
        self.tournament_window = None

    def recarregar_dados(self):
        """
        Lê o JSON do disco novamente.
        Essencial para que alterações na Tela de Armas afetem a Tela de Personagens
        sem precisar fechar o programa.
        """
        self.lista_armas = database.carregar_armas()
        self.lista_personagens = database.carregar_personagens()

    def show_frame(self, page_name):
        '''Traz a tela solicitada para o topo'''
        
        # 1. Sincroniza dados antes de mostrar a tela
        self.recarregar_dados()
        
        # 2. Pega a tela e traz pra frente
        frame = self.frames[page_name]
        frame.tkraise()
        
        # 3. Se a tela tiver função de atualizar a UI interna (tabelas/combos), chama ela
        if hasattr(frame, "atualizar_dados"):
            frame.atualizar_dados()

class MenuPrincipal(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.configure(bg=COR_FUNDO)
        
        titulo = tk.Canvas(self, height=88, bg=COR_FUNDO, highlightthickness=0)
        titulo.pack(fill="x", pady=(18, 0))
        titulo.bind("<Configure>", lambda event: (titulo.delete("all"), criar_titulo(titulo, "NEURAL FIGHTS", event.width)))
        tk.Label(self, text="Sistema de Gerenciamento e Simulação", font=("Segoe UI", 13),
                 bg=COR_FUNDO, fg=COR_TEXTO_DIM).pack(pady=(0, 10))
        menu = tk.Frame(self, bg=COR_FUNDO)
        menu.pack(fill="both", expand=True, padx=90, pady=(0, 8))
        menu.grid_columnconfigure(0, weight=1, uniform="menu")
        menu.grid_columnconfigure(1, weight=1, uniform="menu")
        menu.grid_rowconfigure((0, 1, 2), weight=1)
        botoes = (
            ("⚒", "FORJAR ARMAS", "Crie e ajuste o arsenal", lambda: controller.show_frame("TelaArmas")),
            ("♟", "CRIAR PERSONAGENS", "Monte novos campeões", lambda: controller.show_frame("TelaPersonagens")),
            ("⚔", "SIMULAÇÃO (LUTA)", "Escolha a arena e lute", lambda: controller.show_frame("TelaLuta")),
            ("♛", "MODO TORNEIO", "Dispute o bracket", lambda: self.abrir_torneio(controller)),
            ("♫", "CONFIGURAR SONS", "Ajuste efeitos e volume", lambda: controller.show_frame("TelaSons")),
            ("✦", "INTERAÇÕES SOCIAIS", "Feedback da comunidade", lambda: controller.show_frame("TelaInteracoes")),
        )
        cores_menu = (
            list(CORES_RARIDADE.values())[4], list(CORES_CLASSE.values())[8],
            list(CORES_RARIDADE.values())[5], list(CORES_CLASSE.values())[7],
            list(CORES_CLASSE.values())[10], list(CORES_CLASSE.values())[14],
        )
        for indice, (icone, texto, descricao, comando) in enumerate(botoes):
            CartaoMenu(menu, icone, texto, descricao, comando, cores_menu[indice],
                       destaque=indice == 2).grid(
                row=indice // 2, column=indice % 2, sticky="nsew", padx=8, pady=6
            )
        
        # Botão Sair
        BotaoCanvas(self, "SAIR", command=controller.quit, cor=COR_ACCENT,
                     width=130, height=32, bg=COR_FUNDO).pack(side="bottom", pady=8)
    
    def abrir_torneio(self, controller):
        """Abre a janela do modo torneio"""
        try:
            import customtkinter as ctk
            from neural_fights.ui.view_torneio import TournamentWindow
            
            # Verifica se já existe uma janela aberta
            if controller.tournament_window is not None:
                try:
                    controller.tournament_window.lift()
                    controller.tournament_window.focus_force()
                    return
                except (tk.TclError, AttributeError):
                    pass
            
            # Configura customtkinter
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            
            # Cria nova janela
            controller.tournament_window = TournamentWindow()
            
        except ImportError as e:
            messagebox.showerror("Erro", 
                f"CustomTkinter não instalado!\n\n"
                f"Execute: pip install customtkinter\n\n"
                f"Erro: {e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir torneio: {e}")

# --- PLACEHOLDER (Futuramente será view_interacoes.py) ---
class TelaInteracoes(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.configure(bg=COR_FUNDO)
        
        tk.Label(self, text="INTERAÇÕES SOCIAIS & FEEDBACK", font=("Bahnschrift SemiBold", 24),
                 bg=COR_FUNDO, fg=COR_ACCENT).pack(pady=50)
        
        tk.Label(self, text="Módulo em desenvolvimento...\nAqui você verá likes, comentários e evolução da IA.", 
                 font=("Helvetica", 12), bg=COR_FUNDO, fg="#BDC3C7").pack(pady=20)
        
        BotaoCanvas(self, "VOLTAR AO MENU", command=lambda: controller.show_frame("MenuPrincipal"),
                     width=190, bg=COR_FUNDO).pack(pady=50)

def main():
    """Inicia o launcher."""
    app = SistemaApp()
    app.mainloop()

if __name__ == "__main__":
    main()
