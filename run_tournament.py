"""
NEURAL FIGHTS - Lançador do Modo Torneio
========================================
Execute este script para iniciar o Modo Torneio diretamente.
"""

import os
import sys

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    try:
        import customtkinter as ctk
    except ImportError:
        print("=" * 60)
        print("  ERRO: CustomTkinter não instalado!")
        print("=" * 60)
        print("\n  Execute: pip install customtkinter")
        print("\n  Depois execute este script novamente.")
        input("\n  Pressione ENTER para sair...")
        return
    
    # Configura tema
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Importa e lança o torneio
    from ui.view_torneio import TournamentWindow
    
    print("=" * 60)
    print("  🏆 NEURAL FIGHTS - MODO TORNEIO")
    print("=" * 60)
    print("\n  Iniciando janela do torneio...")
    
    # Cria janela raiz oculta
    root = ctk.CTk()
    root.withdraw()
    
    # Cria janela do torneio
    window = TournamentWindow(root)
    window.protocol("WM_DELETE_WINDOW", root.destroy)
    
    # Inicia loop principal
    root.mainloop()


if __name__ == "__main__":
    main()
