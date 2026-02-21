"""
NEURAL FIGHTS - Interface do Modo Torneio v2.0
==============================================
Interface para gerenciar torneio com simulador visual completo.
Lança as lutas no Pygame e permite registrar vencedores manualmente.
"""

import customtkinter as ctk
from tkinter import messagebox
import subprocess
import threading
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tournament.tournament_mode import Tournament, TournamentRunner, TournamentState


class MatchCard(ctk.CTkFrame):
    """Card visual para uma luta"""
    
    def __init__(self, parent, match, on_select=None, is_current=False):
        super().__init__(parent, corner_radius=8)
        self.match = match
        self.on_select = on_select
        
        # Cores baseadas no status
        if match.completed:
            self.configure(fg_color=("#2d5a2d", "#1a3d1a"))  # Verde
        elif is_current:
            self.configure(fg_color=("#8b4513", "#5a2d0a"))  # Laranja/Marrom
        else:
            self.configure(fg_color=("gray75", "gray25"))
        
        # Layout
        self.grid_columnconfigure(1, weight=1)
        
        # Status
        status_text = "✅" if match.completed else ("⚔️" if is_current else "⏳")
        ctk.CTkLabel(self, text=status_text, font=("Arial", 16), width=30).grid(row=0, column=0, rowspan=2, padx=5)
        
        # Fighter 1
        f1_style = {"font": ("Arial", 12, "bold"), "text_color": "gold"} if match.winner_name == match.fighter1_name else {"font": ("Arial", 12)}
        ctk.CTkLabel(self, text=match.fighter1_name[:25], **f1_style).grid(row=0, column=1, sticky="w", padx=5)
        
        # Fighter 2
        f2_style = {"font": ("Arial", 12, "bold"), "text_color": "gold"} if match.winner_name == match.fighter2_name else {"font": ("Arial", 12)}
        ctk.CTkLabel(self, text=match.fighter2_name[:25], **f2_style).grid(row=1, column=1, sticky="w", padx=5)
        
        # Botão de ação
        if not match.completed and not match.fighter1_name.startswith("BYE") and not match.fighter2_name.startswith("BYE"):
            btn = ctk.CTkButton(self, text="▶️ LUTAR", width=80, height=40,
                               command=self._on_click, fg_color="#e74c3c")
            btn.grid(row=0, column=2, rowspan=2, padx=5, pady=5)
        elif match.completed:
            result = f"{match.ko_type}"
            ctk.CTkLabel(self, text=result, font=("Arial", 10)).grid(row=0, column=2, rowspan=2, padx=5)
    
    def _on_click(self):
        if self.on_select:
            self.on_select(self.match)


class TournamentWindow(ctk.CTkToplevel):
    """Janela principal do modo torneio"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("🏆 Neural Fights - Modo Torneio")
        self.geometry("1100x750")
        
        self.tournament = Tournament("Campeonato Neural Fights")
        self.runner = TournamentRunner(self.tournament)
        self.current_match = None
        
        self.build_ui()
        self.load_participants()
    
    def build_ui(self):
        """Constrói a interface"""
        # Header
        header = ctk.CTkFrame(self, height=60, fg_color=("gray85", "gray15"))
        header.pack(fill="x", padx=10, pady=5)
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="🏆 MODO TORNEIO", font=("Impact", 24)).pack(side="left", padx=20)
        
        self.progress_label = ctk.CTkLabel(header, text="", font=("Arial", 14))
        self.progress_label.pack(side="right", padx=20)
        
        # Main container
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=10, pady=5)
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)
        
        # Left - Bracket
        left_frame = ctk.CTkFrame(main)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(left_frame, text="📋 Bracket", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.bracket_scroll = ctk.CTkScrollableFrame(left_frame)
        self.bracket_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Right - Controls
        right_frame = ctk.CTkFrame(main, width=350)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.pack_propagate(False)
        
        # Luta Atual
        ctk.CTkLabel(right_frame, text="⚔️ Luta Selecionada", font=("Arial", 14, "bold")).pack(pady=10)
        
        self.current_match_frame = ctk.CTkFrame(right_frame, fg_color=("gray75", "gray25"))
        self.current_match_frame.pack(fill="x", padx=10, pady=5)
        
        self.fighter1_label = ctk.CTkLabel(self.current_match_frame, text="-", font=("Arial", 16))
        self.fighter1_label.pack(pady=5)
        
        ctk.CTkLabel(self.current_match_frame, text="VS", font=("Arial", 12, "bold")).pack()
        
        self.fighter2_label = ctk.CTkLabel(self.current_match_frame, text="-", font=("Arial", 16))
        self.fighter2_label.pack(pady=5)
        
        # Botão Iniciar Luta
        self.btn_fight = ctk.CTkButton(right_frame, text="▶️ INICIAR LUTA (Pygame)", 
                                       font=("Arial", 14, "bold"), height=50,
                                       fg_color="#e74c3c", hover_color="#c0392b",
                                       command=self.launch_fight)
        self.btn_fight.pack(pady=15, padx=20, fill="x")
        
        # Registrar Vencedor
        ctk.CTkLabel(right_frame, text="📝 Registrar Vencedor:", font=("Arial", 12)).pack(pady=(20, 5))
        
        winner_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        winner_frame.pack(fill="x", padx=10)
        
        self.btn_win1 = ctk.CTkButton(winner_frame, text="Fighter 1 Venceu", 
                                      fg_color="#27ae60", hover_color="#1e8449",
                                      command=lambda: self.register_winner(1))
        self.btn_win1.pack(side="left", expand=True, padx=2, fill="x")
        
        self.btn_win2 = ctk.CTkButton(winner_frame, text="Fighter 2 Venceu",
                                      fg_color="#3498db", hover_color="#2980b9",
                                      command=lambda: self.register_winner(2))
        self.btn_win2.pack(side="right", expand=True, padx=2, fill="x")
        
        # Separador
        ctk.CTkLabel(right_frame, text="─" * 40, text_color="gray50").pack(pady=20)
        
        # Controles do Torneio
        ctk.CTkLabel(right_frame, text="🎮 Controles", font=("Arial", 14, "bold")).pack(pady=5)
        
        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(btn_frame, text="🔄 Novo Torneio", width=100,
                     command=self.new_tournament).pack(side="left", padx=2)
        
        ctk.CTkButton(btn_frame, text="🎲 Gerar Roster", width=100,
                     command=self.generate_roster).pack(side="left", padx=2)
        
        ctk.CTkButton(btn_frame, text="💾 Salvar", width=60,
                     command=self.save_state).pack(side="right", padx=2)
        
        ctk.CTkButton(btn_frame, text="📂 Carregar", width=70,
                     command=self.load_state).pack(side="right", padx=2)
        
        # Campeão
        self.champion_frame = ctk.CTkFrame(right_frame, fg_color=("gold", "#b8860b"))
        self.champion_label = ctk.CTkLabel(self.champion_frame, text="", 
                                           font=("Impact", 18), text_color="black")
        
        # Footer
        footer = ctk.CTkFrame(self, height=40, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=5)
        
        self.status_label = ctk.CTkLabel(footer, text="Pronto", font=("Arial", 11))
        self.status_label.pack(side="left", padx=10)
    
    def load_participants(self):
        """Carrega participantes"""
        count = self.tournament.load_participants_from_database(max_participants=64)
        
        if count < 2:
            self.status_label.configure(text="⚠️ Poucos personagens! Use 'Gerar Roster'")
        else:
            self.tournament.generate_bracket()
            self.tournament.start_tournament()
            self.refresh_bracket()
    
    def refresh_bracket(self):
        """Atualiza visualização do bracket"""
        # Limpa
        for widget in self.bracket_scroll.winfo_children():
            widget.destroy()
        
        if not self.tournament.bracket:
            ctk.CTkLabel(self.bracket_scroll, text="Nenhum bracket gerado").pack(pady=20)
            return
        
        current_match = self.tournament.get_current_match()
        
        for round_obj in self.tournament.bracket:
            # Título da rodada
            round_frame = ctk.CTkFrame(self.bracket_scroll, fg_color="transparent")
            round_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(round_frame, text=f"📋 {round_obj.name}", 
                        font=("Arial", 13, "bold")).pack(anchor="w", padx=5)
            
            # Lutas
            for match in round_obj.matches:
                is_current = (match == current_match)
                card = MatchCard(round_frame, match, 
                               on_select=self.select_match,
                               is_current=is_current)
                card.pack(fill="x", pady=2, padx=10)
        
        # Atualiza progresso
        progress = self.tournament.get_progress()
        self.progress_label.configure(
            text=f"{progress['completed_matches']}/{progress['total_matches']} lutas • {progress['current_round_name']}"
        )
        
        # Mostra campeão se houver
        if self.tournament.champion:
            self.champion_label.configure(text=f"🏆 CAMPEÃO: {self.tournament.champion}")
            self.champion_label.pack(pady=10)
            self.champion_frame.pack(fill="x", padx=10, pady=10)
    
    def select_match(self, match):
        """Seleciona uma luta para visualizar/executar"""
        self.current_match = match
        
        self.fighter1_label.configure(text=match.fighter1_name)
        self.fighter2_label.configure(text=match.fighter2_name)
        
        self.btn_win1.configure(text=f"🏆 {match.fighter1_name[:15]}")
        self.btn_win2.configure(text=f"🏆 {match.fighter2_name[:15]}")
        
        self.status_label.configure(text=f"Luta selecionada: {match.fighter1_name} vs {match.fighter2_name}")
    
    def launch_fight(self):
        """Lança a simulação visual no Pygame"""
        if not self.current_match:
            # Pega a próxima luta pendente
            self.current_match = self.tournament.get_current_match()
        
        if not self.current_match:
            messagebox.showinfo("Info", "Nenhuma luta pendente!")
            return
        
        if self.current_match.completed:
            messagebox.showinfo("Info", "Esta luta já foi concluída!")
            return
        
        # Configura e lança
        self.runner.setup_match_config(
            self.current_match.fighter1_name,
            self.current_match.fighter2_name
        )
        
        self.status_label.configure(text=f"🎮 Luta iniciada: {self.current_match.fighter1_name} vs {self.current_match.fighter2_name}")
        
        # Atualiza labels
        self.select_match(self.current_match)
        
        # Lança em thread separada
        def launch():
            self.runner.launch_simulation()
        
        thread = threading.Thread(target=launch, daemon=True)
        thread.start()
    
    def register_winner(self, fighter_num):
        """Registra o vencedor da luta atual"""
        if not self.current_match:
            messagebox.showwarning("Aviso", "Selecione uma luta primeiro!")
            return
        
        if self.current_match.completed:
            messagebox.showinfo("Info", "Esta luta já foi concluída!")
            return
        
        winner = self.current_match.fighter1_name if fighter_num == 1 else self.current_match.fighter2_name
        
        # Registra
        self.tournament.record_match_result(
            winner_name=winner,
            ko_type="KO",
            duration=0
        )
        
        self.status_label.configure(text=f"✅ Vencedor registrado: {winner}")
        self.current_match = None
        
        # Atualiza
        self.refresh_bracket()
        
        # Seleciona próxima luta automaticamente
        next_match = self.tournament.get_current_match()
        if next_match:
            self.select_match(next_match)
        
        # Verifica se acabou
        if self.tournament.champion:
            messagebox.showinfo("🏆 TORNEIO FINALIZADO", 
                              f"O grande campeão é:\n\n{self.tournament.champion}!")
    
    def new_tournament(self):
        """Cria novo torneio"""
        self.tournament = Tournament("Campeonato Neural Fights")
        self.runner = TournamentRunner(self.tournament)
        self.current_match = None
        self.load_participants()
        self.status_label.configure(text="🆕 Novo torneio criado!")
        
        # Esconde campeão
        self.champion_frame.pack_forget()
    
    def generate_roster(self):
        """Gera novo roster"""
        self.status_label.configure(text="🎲 Gerando roster...")
        self.update()
        
        try:
            from tools.gerador_database import gerar_database_completa, salvar_database
            
            armas, personagens = gerar_database_completa(64, "balanceada")
            salvar_database(armas, personagens)
            
            self.status_label.configure(text=f"✅ Gerados {len(personagens)} personagens!")
            
            # Recarrega
            self.new_tournament()
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar: {e}")
    
    def save_state(self):
        """Salva estado"""
        self.tournament.save_state()
        self.status_label.configure(text="💾 Estado salvo!")
    
    def load_state(self):
        """Carrega estado"""
        if self.tournament.load_state():
            self.refresh_bracket()
            self.status_label.configure(text="📂 Estado carregado!")
        else:
            self.status_label.configure(text="⚠️ Nenhum estado salvo encontrado")


def launch_tournament_window(parent=None):
    """Lança a janela de torneio"""
    window = TournamentWindow(parent)
    return window


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    root.withdraw()
    
    window = TournamentWindow(root)
    window.protocol("WM_DELETE_WINDOW", root.destroy)
    
    root.mainloop()
