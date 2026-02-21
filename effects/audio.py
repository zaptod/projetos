"""
NEURAL FIGHTS - Sistema de Áudio v2.0
Gerenciador de sons para golpes, magias e efeitos de combate.
Suporta configuração via UI (view_sons.py).
"""

import pygame
import os
import random
import json
from typing import Dict, List, Optional


class AudioManager:
    """
    Gerenciador central de áudio do jogo.
    Sistema procedural que gera sons sintetizados se arquivos não existirem.
    Carrega configuração de sound_config.json para sons personalizados.
    """
    
    _instance = None
    
    # Categorias de volume
    VOLUME_CATEGORIES = {
        "master": "Volume Geral",
        "golpes": "Golpes Físicos",
        "impactos": "Impactos",
        "projeteis": "Projéteis/Magias",
        "skills": "Habilidades",
        "movimento": "Movimentos",
        "ambiente": "Ambiente/Arena",
        "ui": "Interface (UI)",
    }
    
    # Mapeamento de sons para categorias
    SOUND_TO_CATEGORY = {
        # Golpes
        "punch": "golpes", "kick": "golpes", "slash": "golpes", "stab": "golpes",
        "punch_light": "golpes", "punch_medium": "golpes", "punch_heavy": "golpes",
        "kick_light": "golpes", "kick_heavy": "golpes", "kick_spin": "golpes",
        "slash_light": "golpes", "slash_heavy": "golpes", "slash_critical": "golpes",
        "stab_quick": "golpes", "stab_deep": "golpes",
        # Impactos
        "impact": "impactos", "impact_flesh": "impactos", "impact_heavy": "impactos",
        "impact_critical": "impactos", "ko_impact": "impactos", "combo_hit": "impactos",
        "counter_hit": "impactos", "perfect_block": "impactos", "stagger": "impactos",
        "clash_swords": "impactos", "clash_magic": "impactos", "clash_projectiles": "impactos",
        # Projéteis/Magias
        "fireball": "projeteis", "ice": "projeteis", "lightning": "projeteis",
        "energy": "projeteis", "beam": "projeteis",
        "fireball_cast": "projeteis", "fireball_fly": "projeteis", "fireball_impact": "projeteis",
        "ice_cast": "projeteis", "ice_shard": "projeteis", "ice_impact": "projeteis",
        "lightning_charge": "projeteis", "lightning_bolt": "projeteis", "lightning_impact": "projeteis",
        "energy_charge": "projeteis", "energy_blast": "projeteis", "energy_impact": "projeteis",
        "beam_charge": "projeteis", "beam_fire": "projeteis", "beam_end": "projeteis",
        # Skills
        "dash": "skills", "teleport": "skills", "buff": "skills", "heal": "skills", "shield": "skills",
        "dash_whoosh": "skills", "dash_impact": "skills",
        "teleport_out": "skills", "teleport_in": "skills",
        "buff_activate": "skills", "buff_pulse": "skills",
        "heal_cast": "skills", "heal_complete": "skills",
        "shield_up": "skills", "shield_block": "skills", "shield_break": "skills",
        "slowmo_whoosh": "skills", "slowmo_return": "skills",
        # Movimento
        "jump": "movimento", "footstep": "movimento", "dodge": "movimento",
        "jump_start": "movimento", "jump_land": "movimento",
        "step_1": "movimento", "step_2": "movimento", "step_3": "movimento", "step_4": "movimento",
        "dodge_whoosh": "movimento", "dodge_slide": "movimento",
        # Ambiente
        "wall_hit": "ambiente", "wall_impact_light": "ambiente", "wall_impact_heavy": "ambiente",
        "ground_impact": "ambiente", "arena_start": "ambiente", "arena_victory": "ambiente",
        "round_start": "ambiente", "round_end": "ambiente",
        # UI
        "ui": "ui", "ui_select": "ui", "ui_confirm": "ui", "ui_back": "ui",
    }
    
    def __init__(self):
        self.enabled = True
        self.master_volume = 0.7
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        
        # Volumes por categoria (0.0 a 1.0)
        self.category_volumes = {
            "golpes": 1.0,
            "impactos": 1.0,
            "projeteis": 1.0,
            "skills": 1.0,
            "movimento": 0.7,
            "ambiente": 0.8,
            "ui": 0.6,
        }
        
        # Cache de sons carregados
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.sound_groups: Dict[str, List[pygame.mixer.Sound]] = {}
        
        # Diretório de sons - usa caminho absoluto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.sound_dir = os.path.join(base_dir, "sounds")
        print(f"[AUDIO] Sound directory: {self.sound_dir}")
        print(f"[AUDIO] Directory exists: {os.path.exists(self.sound_dir)}")
        
        if not os.path.exists(self.sound_dir):
            os.makedirs(self.sound_dir, exist_ok=True)
        
        # Carrega configuração de sons
        self.sound_config = self._load_sound_config()
        
        # Inicializa mixer do pygame
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(32)  # 32 canais simultâneos
        except:
            print("Aviso: Sistema de áudio não disponível")
            self.enabled = False
            return
        
        # Carrega/gera sons
        self._setup_sounds()
    
    def _load_sound_config(self) -> dict:
        """Carrega configuração de sons personalizada."""
        config_file = os.path.join(self.sound_dir, "sound_config.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Carrega volumes de categoria se existirem
                    if "_volumes" in config:
                        for cat, vol in config["_volumes"].items():
                            if cat in self.category_volumes:
                                self.category_volumes[cat] = vol
                        # Carrega master volume se existir
                        if "master" in config["_volumes"]:
                            self.master_volume = config["_volumes"]["master"]
                    return config
            except:
                pass
        return {}
    
    def save_volume_config(self):
        """Salva configuração de volumes no arquivo."""
        config_file = os.path.join(self.sound_dir, "sound_config.json")
        config = self._load_sound_config() if os.path.exists(config_file) else {}
        config["_volumes"] = {
            "master": self.master_volume,
            **self.category_volumes
        }
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AUDIO] Error saving volume config: {e}")
    
    def set_category_volume(self, category: str, volume: float):
        """Define volume de uma categoria."""
        if category == "master":
            self.master_volume = max(0.0, min(1.0, volume))
        elif category in self.category_volumes:
            self.category_volumes[category] = max(0.0, min(1.0, volume))
    
    def get_category_volume(self, category: str) -> float:
        """Obtém volume de uma categoria."""
        if category == "master":
            return self.master_volume
        return self.category_volumes.get(category, 1.0)
    
    def _get_sound_category(self, sound_name: str) -> str:
        """Determina a categoria de um som."""
        # Tenta correspondência exata primeiro
        if sound_name in self.SOUND_TO_CATEGORY:
            return self.SOUND_TO_CATEGORY[sound_name]
        # Tenta pelo prefixo (nome do grupo)
        for prefix, cat in self.SOUND_TO_CATEGORY.items():
            if sound_name.startswith(prefix):
                return cat
        return "golpes"  # Default
    
    def reload_sounds(self):
        """Recarrega todos os sons do disco (útil após configurar no UI)."""
        self.sounds.clear()
        self.sound_groups.clear()
        self.sound_config = self._load_sound_config()
        self._setup_sounds()
        print("AudioManager: Sons recarregados!")
    
    @classmethod
    def get_instance(cls):
        """Singleton"""
        if cls._instance is None:
            cls._instance = AudioManager()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset singleton"""
        if cls._instance:
            cls._instance.stop_all()
        cls._instance = None
    
    def _setup_sounds(self):
        """Configura biblioteca de sons"""
        
        # === GOLPES FÍSICOS ===
        self._register_sound_group("punch", [
            "punch_light", "punch_medium", "punch_heavy"
        ])
        self._register_sound_group("kick", [
            "kick_light", "kick_heavy", "kick_spin"
        ])
        self._register_sound_group("slash", [
            "slash_light", "slash_heavy", "slash_critical"
        ])
        self._register_sound_group("stab", [
            "stab_quick", "stab_deep"
        ])
        self._register_sound_group("impact", [
            "impact_flesh", "impact_heavy", "impact_critical"
        ])
        
        # === MAGIAS E PROJÉTEIS ===
        self._register_sound_group("fireball", [
            "fireball_cast", "fireball_fly", "fireball_impact"
        ])
        self._register_sound_group("ice", [
            "ice_cast", "ice_shard", "ice_impact"
        ])
        self._register_sound_group("lightning", [
            "lightning_charge", "lightning_bolt", "lightning_impact"
        ])
        self._register_sound_group("energy", [
            "energy_charge", "energy_blast", "energy_impact"
        ])
        self._register_sound_group("beam", [
            "beam_charge", "beam_fire", "beam_end"
        ])
        
        # === SKILLS ESPECIAIS ===
        self._register_sound_group("dash", [
            "dash_whoosh", "dash_impact"
        ])
        self._register_sound_group("teleport", [
            "teleport_out", "teleport_in"
        ])
        self._register_sound_group("buff", [
            "buff_activate", "buff_pulse"
        ])
        self._register_sound_group("heal", [
            "heal_cast", "heal_complete"
        ])
        self._register_sound_group("shield", [
            "shield_up", "shield_block", "shield_break"
        ])
        
        # === MOVIMENTOS ===
        self._register_sound_group("jump", [
            "jump_start", "jump_land"
        ])
        self._register_sound_group("footstep", [
            "step_1", "step_2", "step_3", "step_4"
        ])
        self._register_sound_group("dodge", [
            "dodge_whoosh", "dodge_slide"
        ])
        
        # === AMBIENTE ===
        # BUGFIX v2.0: sons de parede com fallback cruzado
        # Registra individualmente e depois cria aliases entre si para garantir
        # que pelo menos um nome seja encontrado mesmo sem todos os arquivos
        self._register_sound("wall_hit")          # Som principal de parede
        self._register_sound("wall_impact_light") # Impacto leve (alternativo)
        self._register_sound("wall_impact_heavy") # Impacto pesado (alternativo)
        # Aliases de fallback: garante que ao menos um nome funcione
        if "wall_hit" not in self.sounds and "wall_impact_light" in self.sounds:
            self.sounds["wall_hit"] = self.sounds["wall_impact_light"]
        if "wall_impact_light" not in self.sounds and "wall_hit" in self.sounds:
            self.sounds["wall_impact_light"] = self.sounds["wall_hit"]
        if "wall_impact_heavy" not in self.sounds and "wall_impact_light" in self.sounds:
            self.sounds["wall_impact_heavy"] = self.sounds["wall_impact_light"]
        self._register_sound("ground_impact")
        
        # === UI E FEEDBACK ===
        self._register_sound_group("ui", [
            "ui_select", "ui_confirm", "ui_back"
        ])
        
        # === ARENA EVENTS ===
        self._register_sound("arena_start")
        self._register_sound("arena_victory")
        self._register_sound("round_start")
        self._register_sound("round_end")
        
        # === CLASH ===
        self._register_sound("clash_magic")
        self._register_sound("clash_swords")
        self._register_sound("clash_projectiles")
        
        # === SLOW MOTION ===
        self._register_sound("slowmo_whoosh")
        self._register_sound("slowmo_return")
        
        # Sons individuais importantes
        self._register_sound("ko_impact")
        self._register_sound("combo_hit")
        self._register_sound("counter_hit")
        self._register_sound("perfect_block")
        self._register_sound("stagger")
        self._register_sound("shield_block")
        self._register_sound("shield_break")
    
    def _register_sound_group(self, group_name: str, sound_names: List[str]):
        """Registra um grupo de sons variantes"""
        sounds = []
        for name in sound_names:
            full_name = f"{group_name}_{name}" if not name.startswith(group_name) else name
            sound = self._load_or_generate_sound(full_name)
            if sound:
                sounds.append(sound)
                self.sounds[full_name] = sound
        
        if sounds:
            self.sound_groups[group_name] = sounds
    
    def _register_sound(self, name: str):
        """Registra um som individual"""
        sound = self._load_or_generate_sound(name)
        if sound:
            self.sounds[name] = sound
    
    def _load_or_generate_sound(self, name: str) -> Optional[pygame.mixer.Sound]:
        """Carrega som do disco APENAS se configurado ou existir arquivo."""
        if not self.enabled:
            return None
        
        # Primeiro, verifica se há som configurado
        if name in self.sound_config:
            configured_file = self.sound_config[name]
            filepath = os.path.join(self.sound_dir, configured_file)
            if os.path.exists(filepath):
                try:
                    sound = pygame.mixer.Sound(filepath)
                    print(f"[AUDIO] Loaded configured: {name} -> {filepath}")
                    return sound
                except Exception as e:
                    print(f"[AUDIO] Error loading {filepath}: {e}")
        
        # Tenta carregar arquivo com nome padrão
        for ext in ['.wav', '.ogg', '.mp3']:
            filepath = os.path.join(self.sound_dir, f"{name}{ext}")
            if os.path.exists(filepath):
                try:
                    sound = pygame.mixer.Sound(filepath)
                    print(f"[AUDIO] Loaded: {name} -> {filepath}")
                    return sound
                except Exception as e:
                    print(f"[AUDIO] Error loading {filepath}: {e}")
        
        # SEM som configurado = não toca nada (sem sons procedurais)
        return None
    
    # =========================================================================
    # API PÚBLICA
    # =========================================================================
    
    def play(self, sound_name: str, volume: float = 1.0, pan: float = 0.0):
        """
        Toca um som.
        
        Args:
            sound_name: Nome do som ou grupo
            volume: Volume (0.0 a 1.0)
            pan: Panorâmica (-1.0 esquerda, 0.0 centro, 1.0 direita)
        """
        if not self.enabled or not sound_name:
            print(f"[AUDIO] play() - disabled or no name: enabled={self.enabled}, name={sound_name}")
            return
        
        # Tenta tocar do grupo primeiro (variação aleatória)
        sound = None
        actual_name = sound_name
        if sound_name in self.sound_groups:
            sounds = self.sound_groups[sound_name]
            sound = random.choice(sounds)
            print(f"[AUDIO] Playing from group: {sound_name}")
        elif sound_name in self.sounds:
            sound = self.sounds[sound_name]
            print(f"[AUDIO] Playing sound: {sound_name}")
        else:
            print(f"[AUDIO] Sound NOT FOUND: {sound_name} (available: {list(self.sounds.keys())[:5]}...)")
            return
        
        if sound:
            # Obtém volume da categoria do som
            category = self._get_sound_category(actual_name)
            category_vol = self.category_volumes.get(category, 1.0)
            
            # Volume final = base * categoria * sfx * master
            final_volume = volume * category_vol * self.sfx_volume * self.master_volume
            
            # Aplica volume e pan
            if pan != 0.0:
                # Pan: -1 (esquerda) a 1 (direita)
                left = final_volume * (1 - max(0, pan))
                right = final_volume * (1 + min(0, pan))
                sound.set_volume(min(1.0, left + right))
            else:
                sound.set_volume(final_volume)
            
            print(f"[AUDIO] >>> PLAYING {actual_name} [{category}] vol={final_volume:.2f}")
            sound.play()
    
    def play_positional(self, sound_name: str, pos_x: float, listener_x: float, 
                       max_distance: float = 20.0, volume: float = 1.0):
        """
        Toca som com posicionamento espacial baseado na distância e pan.
        
        Args:
            sound_name: Nome do som
            pos_x: Posição X da fonte do som
            listener_x: Posição X do ouvinte (câmera)
            max_distance: Distância máxima de audição
            volume: Volume base
        """
        if not self.enabled:
            return
        
        # Calcula distância
        distance = abs(pos_x - listener_x)
        
        # Atenuação por distância
        if distance > max_distance:
            return  # Muito longe
        
        distance_volume = 1.0 - (distance / max_distance)
        
        # Pan baseado na posição
        pan = (pos_x - listener_x) / max_distance
        pan = max(-1.0, min(1.0, pan))  # Clamp
        
        self.play(sound_name, volume * distance_volume, pan)
    
    def play_attack(self, attack_type: str, pos_x: float = 0, listener_x: float = 0,
                     damage: float = 0, is_critical: bool = False):
        """
        Toca som de ataque baseado no tipo e dano.
        
        attack_type pode ser:
        - Tipo de arma: "Reta", "Dupla", "Corrente", "Arremesso", "Arco", "Mágica", "Orbital", "Transformável"
        - Tipo de ataque legado: "SOCO", "CHUTE", "ESPADADA", etc.
        
        damage: Dano causado pelo ataque (usado para selecionar variação do som)
        is_critical: Se é um golpe crítico
        """
        # Mapeia tipos de ARMA para categoria de som base
        weapon_sound_category = {
            # Armas de lâmina -> slash
            "Reta": "slash",
            "Dupla": "slash",
            "Transformável": "slash",
            # Armas de corrente -> slash (mais pesado)
            "Corrente": "slash",
            # Armas de impacto
            "Orbital": "impact",
            # Armas ranged (não deveriam chegar aqui, mas por segurança)
            "Arremesso": "energy",
            "Arco": "energy",
            "Mágica": "energy",
        }
        
        # Mapeia tipos de ATAQUE legado para categoria de som
        attack_sound_category = {
            "SOCO": "punch",
            "CHUTE": "kick",
            "ESPADADA": "slash",
            "MACHADADA": "slash",
            "FACADA": "stab",
            "ARCO": "energy",
            "MAGIA": "energy",
        }
        
        # Primeiro tenta mapear como tipo de arma
        category = weapon_sound_category.get(attack_type)
        
        # Se não encontrou, tenta como tipo de ataque legado
        if not category:
            category = attack_sound_category.get(attack_type, "punch")
        
        # Seleciona variação do som baseado no dano (para slash)
        if category == "slash":
            if is_critical or damage >= 35:
                sound = "slash_critical"
                volume = 0.9
            elif damage >= 20:
                sound = "slash_heavy"
                volume = 0.8
            else:
                sound = "slash_light"
                volume = 0.7
            print(f"[AUDIO] Slash sound: damage={damage:.1f}, critical={is_critical} -> {sound}")
        else:
            sound = category
            volume = 0.7
        
        if pos_x != 0:
            self.play_positional(sound, pos_x, listener_x, volume=volume)
        else:
            self.play(sound, volume=volume)
    
    def play_impact(self, damage: float, pos_x: float = 0, listener_x: float = 0, 
                   is_critical: bool = False, is_counter: bool = False):
        """Toca som de impacto baseado no dano"""
        if is_counter:
            sound = "counter_hit"
            volume = 1.0
        elif is_critical:
            sound = "impact_critical"
            volume = 0.9
        elif damage > 50:
            sound = "impact_heavy"
            volume = 0.8
        else:
            sound = "impact"
            volume = 0.6
        
        if pos_x != 0:
            self.play_positional(sound, pos_x, listener_x, volume=volume)
        else:
            self.play(sound, volume=volume)
    
    def play_skill(self, skill_type: str, skill_name: str = "", 
                   pos_x: float = 0, listener_x: float = 0, phase: str = "cast"):
        """
        Toca som de skill baseado no tipo.
        
        Args:
            skill_type: PROJETIL, BEAM, AREA, DASH, BUFF, etc
            skill_name: Nome da skill (para sons específicos)
            pos_x: Posição X
            listener_x: Posição do ouvinte
            phase: "cast", "fly", "impact", "active"
        """
        sound = None
        volume = 0.7
        
        # Mapeia tipo de skill para som
        if skill_type == "PROJETIL":
            if "fogo" in skill_name.lower() or "fire" in skill_name.lower():
                sound = f"fireball_{phase}" if phase in ["cast", "fly", "impact"] else "fireball_cast"
            elif "gelo" in skill_name.lower() or "ice" in skill_name.lower():
                sound = f"ice_{phase}" if phase in ["cast", "impact"] else "ice_cast"
            elif "raio" in skill_name.lower() or "lightning" in skill_name.lower():
                sound = f"lightning_{phase}" if phase in ["charge", "bolt", "impact"] else "lightning_bolt"
            else:
                sound = f"energy_{phase}" if phase in ["charge", "blast", "impact"] else "energy_blast"
        
        elif skill_type == "BEAM":
            if phase == "cast":
                sound = "beam_charge"
            elif phase == "active":
                sound = "beam_fire"
            else:
                sound = "beam_end"
        
        elif skill_type == "AREA":
            if "fogo" in skill_name.lower():
                sound = "fireball_impact"
                volume = 1.0
            elif "gelo" in skill_name.lower():
                sound = "ice_impact"
            else:
                sound = "energy_impact"
                volume = 0.9
        
        elif skill_type == "DASH":
            if phase == "cast":
                sound = "dash_whoosh"
            else:
                sound = "dash_impact"
        
        elif skill_type == "BUFF":
            if "cura" in skill_name.lower() or "heal" in skill_name.lower():
                sound = "heal_cast" if phase == "cast" else "heal_complete"
            elif "escudo" in skill_name.lower() or "shield" in skill_name.lower():
                sound = "shield_up"
            else:
                sound = "buff_activate"
        
        elif skill_type == "TELEPORT":
            sound = "teleport_out" if phase == "cast" else "teleport_in"
        
        if sound:
            if pos_x != 0:
                self.play_positional(sound, pos_x, listener_x, volume=volume)
            else:
                self.play(sound, volume=volume)
    
    def play_movement(self, movement_type: str, pos_x: float = 0, listener_x: float = 0):
        """Toca som de movimento"""
        print(f"[AUDIO] play_movement called: type={movement_type}, pos_x={pos_x}")
        sound_map = {
            "jump": "jump_start",
            "land": "jump_land",
            "dodge": "dodge_whoosh",
            "footstep": "footstep",
        }
        
        sound = sound_map.get(movement_type)
        print(f"[AUDIO] play_movement: mapped '{movement_type}' -> '{sound}'")
        if sound:
            # Volume mais alto para pulos (0.7) para ser audível mesmo com atenuação espacial
            volume = 0.3 if movement_type == "footstep" else 0.7
            if pos_x != 0:
                print(f"[AUDIO] Calling play_positional for {sound}")
                self.play_positional(sound, pos_x, listener_x, volume=volume)
            else:
                print(f"[AUDIO] Calling play for {sound}")
                self.play(sound, volume=volume)
    
    def play_special(self, event_type: str, volume: float = 0.8):
        """Toca sons de eventos especiais"""
        special_sounds = {
            # Combate
            "ko": "ko_impact",
            "combo": "combo_hit",
            "perfect_block": "perfect_block",
            "stagger": "stagger",
            "wall_hit": "wall_impact_light",  # Usa o arquivo existente
            "ground_slam": "ground_impact",
            "shield_block": "shield_block",
            "shield_break": "shield_break",
            # Clash
            "clash": "clash_magic",
            "clash_magic": "clash_magic",
            "clash_swords": "clash_swords",
            "clash_projectiles": "clash_projectiles",
            # Arena events
            "arena_start": "arena_start",
            "arena_victory": "arena_victory", 
            "round_start": "round_start",
            "round_end": "round_end",
            # Slow motion
            "slowmo_start": "slowmo_whoosh",
            "slowmo_end": "slowmo_return",
        }
        
        sound = special_sounds.get(event_type)
        if sound:
            self.play(sound, volume=volume)
    
    def play_ui(self, ui_action: str):
        """Toca sons de UI"""
        sound_map = {
            "select": "ui_select",
            "confirm": "ui_confirm",
            "back": "ui_back",
        }
        
        sound = sound_map.get(ui_action)
        if sound:
            self.play(sound, volume=0.5)
    
    def set_master_volume(self, volume: float):
        """Define volume mestre (0.0 a 1.0)"""
        self.master_volume = max(0.0, min(1.0, volume))
    
    def set_sfx_volume(self, volume: float):
        """Define volume de efeitos sonoros (0.0 a 1.0)"""
        self.sfx_volume = max(0.0, min(1.0, volume))
    
    def stop_all(self):
        """Para todos os sons"""
        if self.enabled:
            pygame.mixer.stop()
    
    def toggle_enable(self):
        """Liga/desliga áudio"""
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop_all()


# Atalhos globais
def play_sound(sound_name: str, volume: float = 1.0):
    """Atalho para tocar som"""
    AudioManager.get_instance().play(sound_name, volume)

def play_attack_sound(attack_type: str, pos_x: float = 0, listener_x: float = 0,
                      damage: float = 0, is_critical: bool = False):
    """Atalho para som de ataque"""
    AudioManager.get_instance().play_attack(attack_type, pos_x, listener_x, damage, is_critical)

def play_impact_sound(damage: float, pos_x: float = 0, listener_x: float = 0, 
                     is_critical: bool = False, is_counter: bool = False):
    """Atalho para som de impacto"""
    AudioManager.get_instance().play_impact(damage, pos_x, listener_x, is_critical, is_counter)

def play_skill_sound(skill_type: str, skill_name: str = "", 
                    pos_x: float = 0, listener_x: float = 0, phase: str = "cast"):
    """Atalho para som de skill"""
    AudioManager.get_instance().play_skill(skill_type, skill_name, pos_x, listener_x, phase)
