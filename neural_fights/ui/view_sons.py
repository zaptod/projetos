"""
NEURAL FIGHTS - Sound Configuration UI
======================================
Interface para configurar sons para todos os eventos do jogo.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import shutil

from neural_fights.effects.audio_paths import (
    PACKAGE_SOUND_DIR,
    get_runtime_config_path,
    get_runtime_sound_dir,
    load_sound_config,
    remove_runtime_sound_overrides,
    resolve_sound_file,
    save_sound_config,
)

# Cores do tema
COR_FUNDO = "#2C3E50"
COR_TEXTO = "#ECF0F1"
COR_CARD = "#34495E"
COR_ACCENT = "#3498DB"
COR_SUCCESS = "#2ECC71"
COR_WARNING = "#F39C12"


# ============================================================================
# DEFINIÇÃO DE TODOS OS EVENTOS DE SOM DO JOGO
# ============================================================================

SOUND_EVENTS = {
    "Golpes Físicos": {
        "punch_light": "Soco Leve",
        "punch_medium": "Soco Médio",
        "punch_heavy": "Soco Pesado",
        "kick_light": "Chute Leve",
        "kick_heavy": "Chute Pesado",
        "kick_spin": "Chute Giratório",
        "slash_light": "Corte Leve",
        "slash_heavy": "Corte Pesado",
        "slash_critical": "Corte Crítico",
        "stab_quick": "Estocada Rápida",
        "stab_deep": "Estocada Profunda",
    },
    "Impactos": {
        "impact_flesh": "Impacto no Corpo",
        "impact_heavy": "Impacto Pesado",
        "impact_critical": "Impacto Crítico",
        "ko_impact": "Nocaute (KO)",
        "combo_hit": "Acerto de Combo",
        "counter_hit": "Contra-Ataque",
        "perfect_block": "Bloqueio Perfeito",
        "stagger": "Atordoamento",
    },
    "Projéteis - Fogo": {
        "fireball_cast": "Bola de Fogo - Conjurar",
        "fireball_fly": "Bola de Fogo - Voando",
        "fireball_impact": "Bola de Fogo - Impacto",
    },
    "Projéteis - Gelo": {
        "ice_cast": "Gelo - Conjurar",
        "ice_shard": "Estilhaço de Gelo",
        "ice_impact": "Gelo - Impacto",
    },
    "Projéteis - Raio": {
        "lightning_charge": "Raio - Carregar",
        "lightning_bolt": "Raio - Descarga",
        "lightning_impact": "Raio - Impacto",
    },
    "Projéteis - Energia": {
        "energy_charge": "Energia - Carregar",
        "energy_blast": "Energia - Disparo",
        "energy_impact": "Energia - Impacto",
    },
    "Beam / Raio Contínuo": {
        "beam_charge": "Beam - Carregar",
        "beam_fire": "Beam - Disparo",
        "beam_end": "Beam - Fim",
    },
    "Habilidades Especiais": {
        "dash_whoosh": "Dash - Movimento",
        "dash_impact": "Dash - Impacto",
        "teleport_out": "Teleporte - Saída",
        "teleport_in": "Teleporte - Entrada",
        "buff_activate": "Buff - Ativar",
        "buff_pulse": "Buff - Pulso",
        "heal_cast": "Cura - Conjurar",
        "heal_complete": "Cura - Completa",
        "shield_up": "Escudo - Ativar",
        "shield_block": "Escudo - Bloquear",
        "shield_break": "Escudo - Quebrar",
    },
    "Movimentos": {
        "jump_start": "Pulo - Início",
        "jump_land": "Pulo - Aterrissar",
        "step_1": "Passo 1",
        "step_2": "Passo 2",
        "step_3": "Passo 3",
        "step_4": "Passo 4",
        "dodge_whoosh": "Esquiva - Som",
        "dodge_slide": "Esquiva - Deslizar",
    },
    "Colisões com Ambiente": {
        "wall_impact_light": "Parede - Impacto Leve",
        "wall_impact_heavy": "Parede - Impacto Pesado",
        "ground_impact": "Chão - Impacto",
        "obstacle_hit": "Obstáculo - Colisão",
    },
    "Clash / Colisão de Ataques": {
        "clash_swords": "Clash - Espadas",
        "clash_magic": "Clash - Magia",
        "clash_projectiles": "Clash - Projéteis",
        "parry_success": "Aparar - Sucesso",
    },
    "Magia - Geral": {
        "magic_cast_generic": "Magia - Conjurar Genérico",
        "magic_channel_loop": "Magia - Canalizando (Loop)",
        "magic_explosion": "Magia - Explosão",
        "magic_aura_activate": "Magia - Aura Ativar",
        "magic_summon": "Magia - Invocar",
    },
    "Ambiente / Arena": {
        "arena_start": "Arena - Início da Luta",
        "round_start": "Round - Início",
        "round_end": "Round - Fim",
        "arena_ko": "Arena - Nocaute",
        "arena_victory": "Arena - Vitória",
        "arena_draw": "Arena - Empate",
        "ambient_fire_loop": "Ambiente - Fogo (Loop)",
        "ambient_wind_loop": "Ambiente - Vento (Loop)",
        "ambient_water_loop": "Ambiente - Água (Loop)",
    },
    "Interface (UI)": {
        "ui_select": "UI - Selecionar",
        "ui_confirm": "UI - Confirmar",
        "ui_back": "UI - Voltar",
        "ui_error": "UI - Erro",
        "ui_notification": "UI - Notificação",
    },
    "Efeitos Especiais": {
        "slowmo_whoosh": "Slow Motion - Ativar",
        "slowmo_return": "Slow Motion - Desativar",
        "critical_flash": "Flash Crítico",
        "rage_mode": "Modo Fúria",
        "power_up": "Power Up",
        "level_up": "Level Up",
    },
}


class TelaSons(tk.Frame):
    """Tela de configuração de sons."""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg=COR_FUNDO)
        
        # Assets originais ficam no pacote; customizacoes sao estado local.
        self.sound_dir = str(get_runtime_sound_dir())
        self.package_sound_dir = str(PACKAGE_SOUND_DIR)
        os.makedirs(self.sound_dir, exist_ok=True)
        
        # Arquivo de configuração
        self.config_file = str(get_runtime_config_path())
        self.sound_config = self._load_config()
        
        # Widgets de som selecionados
        self.sound_widgets = {}
        
        # Sliders de volume
        self.volume_sliders = {}
        
        self._criar_interface()
    
    def _load_config(self) -> dict:
        """Carrega configuração de sons."""
        try:
            return load_sound_config()
        except (OSError, ValueError, TypeError):
            return {}
    
    def _save_config(self):
        """Salva configuração de sons."""
        # Adiciona volumes ao config
        volumes = {}
        for cat, slider_data in self.volume_sliders.items():
            volumes[cat] = slider_data['var'].get() / 100.0
        self.sound_config["_volumes"] = volumes
        
        save_sound_config(self.sound_config)
    
    def _criar_painel_volumes(self):
        """Cria painel com sliders de volume por categoria."""
        
        volume_frame = tk.LabelFrame(
            self, text=" 🎚️ Volumes por Categoria ",
            font=("Arial", 11, "bold"), bg=COR_CARD, fg=COR_ACCENT,
            relief="flat", bd=2
        )
        volume_frame.pack(fill="x", padx=10, pady=5)
        
        # Frame interno para organizar sliders em grid
        inner_frame = tk.Frame(volume_frame, bg=COR_CARD)
        inner_frame.pack(fill="x", padx=10, pady=10)
        
        # Categorias de volume
        volume_categories = {
            "master": ("🔊 Volume Geral", 70),
            "golpes": ("⚔️ Golpes Físicos", 100),
            "impactos": ("💥 Impactos", 100),
            "projeteis": ("🔮 Projéteis/Magias", 100),
            "skills": ("✨ Habilidades", 100),
            "movimento": ("👣 Movimentos", 70),
            "ambiente": ("🏟️ Ambiente/Arena", 80),
            "ui": ("🖱️ Interface (UI)", 60),
        }
        
        # Carrega volumes salvos
        saved_volumes = self.sound_config.get("_volumes", {})
        
        row = 0
        col = 0
        for cat_id, (cat_name, default_vol) in volume_categories.items():
            # Obtém volume salvo ou usa padrão
            current_vol = int(saved_volumes.get(cat_id, default_vol / 100.0) * 100)
            
            # Container do slider
            slider_container = tk.Frame(inner_frame, bg=COR_CARD)
            slider_container.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
            
            # Label do nome
            tk.Label(
                slider_container, text=cat_name, font=("Arial", 9),
                bg=COR_CARD, fg=COR_TEXTO, width=18, anchor="w"
            ).pack(side="left")
            
            # Variável do slider
            vol_var = tk.IntVar(value=current_vol)
            
            # Slider
            slider = ttk.Scale(
                slider_container, from_=0, to=100, 
                variable=vol_var, orient="horizontal", length=120,
                command=lambda v, cid=cat_id: self._on_volume_change(cid, v)
            )
            slider.pack(side="left", padx=5)
            
            # Label de valor
            val_label = tk.Label(
                slider_container, text=f"{current_vol}%", font=("Arial", 9, "bold"),
                bg=COR_CARD, fg=COR_SUCCESS, width=5
            )
            val_label.pack(side="left")
            
            self.volume_sliders[cat_id] = {
                'var': vol_var,
                'label': val_label,
                'slider': slider
            }
            
            col += 1
            if col >= 4:  # 4 sliders por linha
                col = 0
                row += 1
        
        # Configura grid
        for i in range(4):
            inner_frame.grid_columnconfigure(i, weight=1)
    
    def _on_volume_change(self, category: str, value):
        """Callback quando volume muda."""
        vol = int(float(value))
        if category in self.volume_sliders:
            self.volume_sliders[category]['label'].config(text=f"{vol}%")
            
            # Aplica em tempo real se AudioManager existir
            try:
                from neural_fights.effects.audio import AudioManager
                audio = AudioManager.get_instance()
                audio.set_category_volume(category, vol / 100.0)
            except (OSError, RuntimeError, AttributeError, TypeError):
                pass

    def _criar_interface(self):
        """Cria a interface principal."""
        
        # === HEADER ===
        header = tk.Frame(self, bg=COR_FUNDO)
        header.pack(fill="x", pady=(10, 5))
        
        tk.Button(
            header, text="← Voltar", font=("Arial", 10),
            bg="#E67E22", fg="white", relief="flat",
            command=lambda: self.controller.show_frame("MenuPrincipal")
        ).pack(side="left", padx=10)
        
        tk.Label(
            header, text="🔊 Configuração de Sons",
            font=("Helvetica", 20, "bold"), bg=COR_FUNDO, fg="white"
        ).pack(side="left", padx=20)
        
        # Botões de ação
        btn_frame = tk.Frame(header, bg=COR_FUNDO)
        btn_frame.pack(side="right", padx=10)
        
        tk.Button(
            btn_frame, text="💾 Salvar", font=("Arial", 10, "bold"),
            bg=COR_SUCCESS, fg="white", relief="flat",
            command=self._salvar_tudo
        ).pack(side="left", padx=5)
        
        tk.Button(
            btn_frame, text="🔄 Recarregar", font=("Arial", 10),
            bg=COR_ACCENT, fg="white", relief="flat",
            command=self._recarregar
        ).pack(side="left", padx=5)
        
        tk.Button(
            btn_frame, text="📁 Abrir Pasta", font=("Arial", 10),
            bg=COR_CARD, fg="white", relief="flat",
            command=self._abrir_pasta_sons
        ).pack(side="left", padx=5)
        
        # === INFO ===
        info_frame = tk.Frame(self, bg=COR_CARD)
        info_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(
            info_frame, 
            text="📌 Clique no botão '...' para selecionar um arquivo de som (.wav, .ogg, .mp3)\n"
                 "📌 Sons configurados são copiados para a pasta local do usuário\n"
                 "📌 Sons não configurados usam o asset padrão ou fallback disponível",
            font=("Arial", 9), bg=COR_CARD, fg="#BDC3C7", justify="left"
        ).pack(pady=8, padx=10)
        
        # === PAINEL DE VOLUMES ===
        self._criar_painel_volumes()
        
        # === ÁREA PRINCIPAL COM SCROLL ===
        main_container = tk.Frame(self, bg=COR_FUNDO)
        main_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Canvas com scrollbar
        canvas = tk.Canvas(main_container, bg=COR_FUNDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        
        self.scrollable_frame = tk.Frame(canvas, bg=COR_FUNDO)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # === CRIAR CATEGORIAS ===
        self._criar_categorias()
    
    def _criar_categorias(self):
        """Cria todas as categorias de sons."""
        
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.sound_widgets = {}
        
        row = 0
        col = 0
        
        for categoria, eventos in SOUND_EVENTS.items():
            # Card de categoria
            card = tk.LabelFrame(
                self.scrollable_frame, text=f" {categoria} ",
                font=("Arial", 11, "bold"), bg=COR_CARD, fg=COR_ACCENT,
                relief="flat", bd=2
            )
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            # Eventos dentro da categoria
            for i, (event_id, event_name) in enumerate(eventos.items()):
                self._criar_linha_evento(card, event_id, event_name, i)
            
            col += 1
            if col >= 2:  # 2 colunas
                col = 0
                row += 1
        
        # Configura grid weights
        for i in range(2):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)
    
    def _criar_linha_evento(self, parent, event_id: str, event_name: str, row: int):
        """Cria uma linha para configurar um evento de som."""
        
        frame = tk.Frame(parent, bg=COR_CARD)
        frame.pack(fill="x", padx=5, pady=2)
        
        # Nome do evento
        tk.Label(
            frame, text=event_name, font=("Arial", 9),
            bg=COR_CARD, fg=COR_TEXTO, width=22, anchor="w"
        ).pack(side="left", padx=(5, 10))
        
        # Campo de arquivo
        file_var = tk.StringVar()
        
        # Verifica se já tem som configurado
        if event_id in self.sound_config:
            file_var.set(self.sound_config[event_id])
        else:
            # Verifica se existe arquivo na pasta
            for ext in ['.wav', '.ogg', '.mp3']:
                filepath = os.path.join(self.sound_dir, f"{event_id}{ext}")
                if os.path.exists(filepath):
                    file_var.set(os.path.basename(filepath))
                    break
        
        entry = tk.Entry(
            frame, textvariable=file_var, font=("Arial", 8),
            width=25, bg="#1a1a2e", fg=COR_TEXTO, relief="flat"
        )
        entry.pack(side="left", padx=2)
        
        # Indicador de status
        status_label = tk.Label(frame, text="", font=("Arial", 10), bg=COR_CARD, width=2)
        status_label.pack(side="left", padx=2)
        
        # Atualiza status
        self._atualizar_status(event_id, file_var.get(), status_label)
        
        # Botão selecionar arquivo
        tk.Button(
            frame, text="...", font=("Arial", 8), width=3,
            bg=COR_ACCENT, fg="white", relief="flat",
            command=lambda eid=event_id, fv=file_var, sl=status_label: self._selecionar_arquivo(eid, fv, sl)
        ).pack(side="left", padx=2)
        
        # Botão limpar
        tk.Button(
            frame, text="✕", font=("Arial", 8), width=2,
            bg="#C0392B", fg="white", relief="flat",
            command=lambda eid=event_id, fv=file_var, sl=status_label: self._limpar_som(eid, fv, sl)
        ).pack(side="left", padx=2)
        
        # Botão testar (play)
        tk.Button(
            frame, text="▶", font=("Arial", 8), width=2,
            bg=COR_SUCCESS, fg="white", relief="flat",
            command=lambda eid=event_id, fv=file_var: self._testar_som(eid, fv)
        ).pack(side="left", padx=2)
        
        self.sound_widgets[event_id] = {
            'var': file_var,
            'status': status_label
        }
    
    def _atualizar_status(self, event_id: str, filename: str, status_label: tk.Label):
        """Atualiza o indicador de status do som."""
        if filename:
            if resolve_sound_file(filename) is not None:
                status_label.config(text="✓", fg=COR_SUCCESS)
            else:
                status_label.config(text="?", fg=COR_WARNING)
        else:
            status_label.config(text="○", fg="#666666")
    
    def _selecionar_arquivo(self, event_id: str, file_var: tk.StringVar, status_label: tk.Label):
        """Abre diálogo para selecionar arquivo de som."""
        
        filepath = filedialog.askopenfilename(
            title=f"Selecionar som para: {event_id}",
            filetypes=[
                ("Arquivos de Áudio", "*.wav *.ogg *.mp3"),
                ("WAV", "*.wav"),
                ("OGG", "*.ogg"),
                ("MP3", "*.mp3"),
                ("Todos", "*.*")
            ],
            initialdir=self.sound_dir if os.listdir(self.sound_dir) else os.path.expanduser("~")
        )
        
        if filepath:
            # Copia arquivo para pasta de sons
            filename = os.path.basename(filepath)
            dest_name = f"{event_id}{os.path.splitext(filename)[1]}"
            dest_path = os.path.join(self.sound_dir, dest_name)
            
            try:
                if os.path.abspath(filepath) != os.path.abspath(dest_path):
                    remove_runtime_sound_overrides(event_id)
                    shutil.copy2(filepath, dest_path)
                
                file_var.set(dest_name)
                self.sound_config[event_id] = dest_name
                self._atualizar_status(event_id, dest_name, status_label)
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao copiar arquivo:\n{e}")
    
    def _limpar_som(self, event_id: str, file_var: tk.StringVar, status_label: tk.Label):
        """Remove configuração de som."""
        remove_runtime_sound_overrides(event_id)
        file_var.set("")
        if event_id in self.sound_config:
            del self.sound_config[event_id]
        self._atualizar_status(event_id, "", status_label)
    
    def _testar_som(self, event_id: str, file_var: tk.StringVar):
        """Testa reprodução do som."""
        filename = file_var.get()
        
        if not filename:
            messagebox.showinfo(
                "Info",
                "Nenhum som configurado.\nSerá usado o asset padrão ou fallback.",
            )
            return
        
        filepath = resolve_sound_file(filename)

        if filepath is None:
            messagebox.showwarning("Aviso", f"Arquivo não encontrado:\n{filename}")
            return
        
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            
            sound = pygame.mixer.Sound(str(filepath))
            sound.play()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao reproduzir:\n{e}")
    
    def _salvar_tudo(self):
        """Salva toda a configuração."""
        # Atualiza config com valores atuais (sons)
        for event_id, widgets in self.sound_widgets.items():
            filename = widgets['var'].get()
            if filename:
                self.sound_config[event_id] = filename
            elif event_id in self.sound_config:
                del self.sound_config[event_id]
        
        self._save_config()
        
        # Salva também no AudioManager
        try:
            from neural_fights.effects.audio import AudioManager
            audio = AudioManager.get_instance()
            audio.reload_sounds()
        except (OSError, RuntimeError, AttributeError, TypeError):
            pass
        
        messagebox.showinfo("Sucesso", "Configuração de sons e volumes salva!")
    
    def _recarregar(self):
        """Recarrega a configuração do disco."""
        self.sound_config = self._load_config()
        
        # Atualiza sliders de volume
        saved_volumes = self.sound_config.get("_volumes", {})
        for cat_id, slider_data in self.volume_sliders.items():
            vol = int(saved_volumes.get(cat_id, 0.7 if cat_id == "master" else 1.0) * 100)
            slider_data['var'].set(vol)
            slider_data['label'].config(text=f"{vol}%")
        
        self._criar_categorias()
    
    def _abrir_pasta_sons(self):
        """Abre a pasta de sons no explorador."""
        import subprocess
        import platform
        
        if platform.system() == "Windows":
            os.startfile(self.sound_dir)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", self.sound_dir])
        else:  # Linux
            subprocess.Popen(["xdg-open", self.sound_dir])
    
    def atualizar_dados(self):
        """Chamado quando a tela é exibida."""
        self.sound_config = self._load_config()
        
        # Atualiza sliders de volume
        saved_volumes = self.sound_config.get("_volumes", {})
        for cat_id, slider_data in self.volume_sliders.items():
            default_vol = 70 if cat_id == "master" else (70 if cat_id == "movimento" else 100)
            vol = int(saved_volumes.get(cat_id, default_vol / 100.0) * 100)
            slider_data['var'].set(vol)
            slider_data['label'].config(text=f"{vol}%")
        
        # Atualiza status de todos os sons
        for event_id, widgets in self.sound_widgets.items():
            filename = widgets['var'].get()
            self._atualizar_status(event_id, filename, widgets['status'])


# ============================================================================
# VERSÃO STANDALONE (executável independente)
# ============================================================================

def run_standalone():
    """Executa o configurador de sons como aplicação independente."""
    
    root = tk.Tk()
    root.title("Neural Fights - Sound Configurator")
    root.geometry("1100x800")
    root.configure(bg=COR_FUNDO)
    
    # Fake controller
    class FakeController:
        def show_frame(self, name):
            root.quit()
    
    tela = TelaSons(root, FakeController())
    tela.pack(fill="both", expand=True)
    
    root.mainloop()


if __name__ == "__main__":
    run_standalone()
