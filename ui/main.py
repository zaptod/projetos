# main.py
import tkinter as tk
from tkinter import messagebox
import sys
import os

# Adiciona o diretório pai ao path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import database

# --- IMPORTANDO AS TELAS (VIEWS) ---
from ui.view_armas import TelaArmas
from ui.view_chars import TelaPersonagens
from ui.view_luta import TelaLuta
from ui.view_sons import TelaSons

# Configurações Visuais Globais
COR_FUNDO = "#2C3E50"
COR_TEXTO = "#ECF0F1"

class SistemaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Neural Fights - Launcher & Gerenciador")
        self.geometry("1000x750")
        self.configure(bg=COR_FUNDO)

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
        
        # Título
        tk.Label(self, text="NEURAL FIGHTS", font=("Impact", 40), 
                 bg=COR_FUNDO, fg="#E74C3C").pack(pady=(60, 10))
        
        tk.Label(self, text="Sistema de Gerenciamento e Simulação", font=("Helvetica", 14), 
                 bg=COR_FUNDO, fg="#BDC3C7").pack(pady=(0, 50))

        # Estilo dos Botões
        btn_style = {
            "font": ("Helvetica", 14, "bold"), 
            "width": 30, 
            "pady": 10,
            "bg": "#34495E",
            "fg": "white",
            "activebackground": "#2980B9",
            "activeforeground": "white",
            "relief": "flat"
        }

        # Botões de Navegação
        tk.Button(self, text="⚔️  FORJAR ARMAS", command=lambda: controller.show_frame("TelaArmas"), **btn_style).pack(pady=10)
        tk.Button(self, text="👤  CRIAR PERSONAGENS", command=lambda: controller.show_frame("TelaPersonagens"), **btn_style).pack(pady=10)
        tk.Button(self, text="🎮  SIMULAÇÃO (LUTA)", command=lambda: controller.show_frame("TelaLuta"), **btn_style).pack(pady=10)
        tk.Button(self, text="🏆  MODO TORNEIO", command=lambda: self.abrir_torneio(controller), **btn_style).pack(pady=10)
        tk.Button(self, text="🔊  CONFIGURAR SONS", command=lambda: controller.show_frame("TelaSons"), **btn_style).pack(pady=10)
        tk.Button(self, text="💬  INTERAÇÕES SOCIAIS", command=lambda: controller.show_frame("TelaInteracoes"), **btn_style).pack(pady=10)
        
        # Botão Sair
        tk.Button(self, text="SAIR", command=controller.quit, 
                  font=("Helvetica", 12, "bold"), bg="#C0392B", fg="white", width=15).pack(side="bottom", pady=40)
    
    def abrir_torneio(self, controller):
        """Abre a janela do modo torneio"""
        try:
            import customtkinter as ctk
            from ui.view_torneio import TournamentWindow
            
            # Verifica se já existe uma janela aberta
            if controller.tournament_window is not None:
                try:
                    controller.tournament_window.lift()
                    controller.tournament_window.focus_force()
                    return
                except:
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
        
        tk.Label(self, text="Interações Sociais & Feedback", font=("Helvetica", 24, "bold"), 
                 bg=COR_FUNDO, fg="white").pack(pady=50)
        
        tk.Label(self, text="Módulo em desenvolvimento...\nAqui você verá likes, comentários e evolução da IA.", 
                 font=("Helvetica", 12), bg=COR_FUNDO, fg="#BDC3C7").pack(pady=20)
        
        tk.Button(self, text="Voltar ao Menu", font=("Arial", 12), bg="#E67E22", fg="white",
                  command=lambda: controller.show_frame("MenuPrincipal")).pack(pady=50)

def main():
    """Inicia o launcher."""
    app = SistemaApp()
    app.mainloop()

if __name__ == "__main__":
    main()