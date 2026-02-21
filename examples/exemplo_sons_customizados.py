"""
EXEMPLO: Como adicionar seus próprios sons ao Neural Fights
"""

from audio import AudioManager

# =============================================================================
# MÉTODO 1: Usar Arquivos de Som
# =============================================================================

"""
1. Crie a pasta 'sounds' na raiz do projeto (se não existe)
2. Adicione seus arquivos de som:

neural/
├── sounds/
│   ├── punch_light.wav       # Som de soco leve
│   ├── punch_medium.wav      # Som de soco médio
│   ├── punch_heavy.wav       # Som de soco pesado
│   ├── fireball_cast.ogg     # Som de cast de bola de fogo
│   ├── fireball_impact.mp3   # Som de impacto de bola de fogo
│   └── ...

3. O AudioManager carregará automaticamente!

Formatos suportados: .wav, .ogg, .mp3
"""

# =============================================================================
# MÉTODO 2: Adicionar Novos Grupos de Sons
# =============================================================================

def exemplo_adicionar_grupo():
    """Adiciona um novo grupo de sons ao sistema"""
    audio = AudioManager.get_instance()
    
    # Registra novo grupo com variações
    audio._register_sound_group("explosao", [
        "explosao_pequena",
        "explosao_media", 
        "explosao_grande"
    ])
    
    # Agora pode usar:
    audio.play("explosao")  # Toca variação aleatória


# =============================================================================
# MÉTODO 3: Sons Procedurais Customizados
# =============================================================================

def exemplo_som_procedural():
    """
    Adicione sua própria síntese em audio.py na função
    _generate_procedural_sound()
    """
    
    # No arquivo audio.py, adicione:
    """
    elif "meu_som" in name:
        import numpy as np
        duration = 0.2
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Gere sua onda sonora
        freq = 440  # Lá (A4)
        wave = np.sin(2 * np.pi * freq * t)
        
        # Adicione envelope
        envelope = np.exp(-t * 10)
        wave = wave * envelope
        
        # Converta para int16
        wave = (wave / np.max(np.abs(wave)) * 0.7 * 32767).astype(np.int16)
        stereo = np.column_stack((wave, wave))
        
        return pygame.sndarray.make_sound(stereo)
    """


# =============================================================================
# MÉTODO 4: Sons por Personagem
# =============================================================================

def exemplo_sons_por_personagem():
    """Cria sons específicos para cada personagem"""
    
    # Estrutura de pastas sugerida:
    """
    sounds/
    ├── characters/
    │   ├── ninja/
    │   │   ├── attack_1.wav
    │   │   ├── attack_2.wav
    │   │   └── skill_kunai.wav
    │   ├── mago/
    │   │   ├── attack_staff.wav
    │   │   ├── skill_fireball.wav
    │   │   └── skill_ice.wav
    │   └── guerreiro/
    │       ├── attack_sword.wav
    │       └── skill_charge.wav
    """
    
    # No código do personagem:
    audio = AudioManager.get_instance()
    classe = "ninja"
    
    # Carrega som específico
    som_path = f"characters/{classe}/attack_1"
    audio._register_sound(som_path)
    audio.play(som_path)


# =============================================================================
# MÉTODO 5: Sistema de Vozes (Voice Acting)
# =============================================================================

def exemplo_sistema_vozes():
    """Sistema de vozes para personagens"""
    
    # Estrutura sugerida:
    """
    sounds/
    ├── voices/
    │   ├── ninja/
    │   │   ├── grunt_1.wav
    │   │   ├── grunt_2.wav
    │   │   ├── grunt_3.wav
    │   │   ├── skill_cast.wav
    │   │   ├── damage_light.wav
    │   │   ├── damage_heavy.wav
    │   │   └── death.wav
    │   └── mago/
    │       └── ...
    """
    
    # Adicione ao AudioManager:
    audio = AudioManager.get_instance()
    
    # Registra grupo de vozes
    audio._register_sound_group("ninja_grunt", [
        "voices/ninja/grunt_1",
        "voices/ninja/grunt_2",
        "voices/ninja/grunt_3"
    ])
    
    # Use no combate:
    # Quando ataca
    audio.play("ninja_grunt")
    
    # Quando toma dano
    audio.play("voices/ninja/damage_light")
    
    # Quando morre
    audio.play("voices/ninja/death")


# =============================================================================
# MÉTODO 6: Música Ambiente
# =============================================================================

def exemplo_musica_ambiente():
    """Sistema de música para arenas"""
    
    """
    sounds/
    ├── music/
    │   ├── arena_theme.ogg
    │   ├── coliseum_theme.ogg
    │   ├── forest_theme.ogg
    │   ├── boss_theme.ogg
    │   └── victory_theme.ogg
    """
    
    import pygame
    
    # Carrega música (separado de SFX)
    pygame.mixer.music.load("sounds/music/arena_theme.ogg")
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)  # Loop infinito
    
    # Para trocar música
    pygame.mixer.music.fadeout(1000)  # 1 segundo
    pygame.mixer.music.load("sounds/music/boss_theme.ogg")
    pygame.mixer.music.play(-1)


# =============================================================================
# MÉTODO 7: Sons de UI
# =============================================================================

def exemplo_sons_ui():
    """Adiciona sons para interface"""
    
    """
    sounds/
    ├── ui/
    │   ├── button_hover.wav
    │   ├── button_click.wav
    │   ├── menu_open.wav
    │   ├── menu_close.wav
    │   ├── selection.wav
    │   └── error.wav
    """
    
    # No código da UI:
    audio = AudioManager.get_instance()
    
    # Ao passar mouse sobre botão
    audio.play("ui/button_hover", volume=0.3)
    
    # Ao clicar
    audio.play("ui/button_click", volume=0.5)
    
    # Menu abrindo
    audio.play("ui/menu_open", volume=0.4)


# =============================================================================
# MÉTODO 8: Efeitos de Reverb/Echo
# =============================================================================

def exemplo_reverb():
    """Adiciona reverb baseado no ambiente"""
    
    # Requer processamento de áudio adicional
    # Sugestão: use biblioteca como pydub
    
    """
    from pydub import AudioSegment
    from pydub.effects import reverb
    
    # Carrega som
    sound = AudioSegment.from_file("sounds/punch.wav")
    
    # Adiciona reverb baseado na arena
    if arena == "Caverna":
        sound = reverb(sound, room_size=0.8)
    elif arena == "Arena":
        sound = reverb(sound, room_size=0.3)
    
    # Salva temporário
    sound.export("temp_reverb.wav", format="wav")
    
    # Carrega no pygame
    reverb_sound = pygame.mixer.Sound("temp_reverb.wav")
    reverb_sound.play()
    """


# =============================================================================
# MÉTODO 9: Sistema de Layers (Camadas de Som)
# =============================================================================

def exemplo_layers():
    """Sistema de camadas de som para complexidade"""
    
    # Para beams/lasers, use camadas:
    audio = AudioManager.get_instance()
    
    # Layer 1: Charge up
    audio.play("beam_charge", volume=0.7)
    
    # Layer 2: Continuous fire (após 0.5s)
    # Use um loop channel
    import pygame
    channel = pygame.mixer.Channel(10)  # Canal dedicado
    loop_sound = pygame.mixer.Sound("sounds/beam_loop.wav")
    channel.play(loop_sound, loops=-1)  # Loop infinito
    
    # Layer 3: End sound (quando para)
    channel.stop()
    audio.play("beam_end", volume=0.8)


# =============================================================================
# MÉTODO 10: Sons Dinâmicos (Muda com Velocidade)
# =============================================================================

def exemplo_sons_dinamicos():
    """Sons que mudam baseado em game state"""
    
    audio = AudioManager.get_instance()
    
    # Som de dash muda com velocidade
    velocidade = 15.0  # m/s
    max_vel = 20.0
    
    # Volume proporcional
    volume = min(1.0, velocidade / max_vel)
    audio.play("dash_whoosh", volume=volume)
    
    # Pitch shift (requer processamento)
    # sound.set_pitch(1.0 + velocidade/50)  # Não nativo pygame


# =============================================================================
# MÉTODO 11: Pool de Sons para Performance
# =============================================================================

def exemplo_pool_sons():
    """
    Para sons muito frequentes (passos), use pool
    """
    
    class SoundPool:
        def __init__(self, sound_name, pool_size=5):
            self.sounds = []
            for i in range(pool_size):
                sound = pygame.mixer.Sound(f"sounds/{sound_name}.wav")
                self.sounds.append(sound)
            self.index = 0
        
        def play(self):
            self.sounds[self.index].play()
            self.index = (self.index + 1) % len(self.sounds)
    
    # Uso:
    footstep_pool = SoundPool("footstep", pool_size=8)
    
    # A cada passo
    footstep_pool.play()


# =============================================================================
# MÉTODO 12: Mixer de Volumes por Categoria
# =============================================================================

def exemplo_mixer():
    """Sistema de mixer para controle fino"""
    
    class AudioMixer:
        def __init__(self):
            self.volumes = {
                "master": 1.0,
                "sfx": 0.8,
                "voice": 0.9,
                "music": 0.6,
                "ui": 0.5
            }
        
        def get_volume(self, category):
            return self.volumes["master"] * self.volumes.get(category, 1.0)
        
        def set_volume(self, category, volume):
            self.volumes[category] = max(0.0, min(1.0, volume))
    
    # Uso:
    mixer = AudioMixer()
    
    # Toca som com volume do mixer
    audio = AudioManager.get_instance()
    volume = mixer.get_volume("sfx")
    audio.play("punch", volume=volume)


# =============================================================================
# MÉTODO 13: Sons com Delay (Eco)
# =============================================================================

def exemplo_echo():
    """Cria efeito de eco"""
    
    import pygame
    import time
    
    audio = AudioManager.get_instance()
    
    # Som original
    audio.play("explosion", volume=1.0)
    
    # Ecos (em thread separada ou timer)
    delays = [0.1, 0.2, 0.3]
    volumes = [0.6, 0.4, 0.2]
    
    for delay, vol in zip(delays, volumes):
        # Em produção, use threading.Timer ou pygame.time
        time.sleep(delay)
        audio.play("explosion", volume=vol)


# =============================================================================
# DICA: Testando Seus Sons
# =============================================================================

def testar_sons():
    """Script de teste para verificar todos os sons"""
    
    audio = AudioManager.get_instance()
    
    print("🎵 Testando Sistema de Áudio...")
    
    # Lista todos os sons carregados
    print(f"\n📦 Sons em cache: {len(audio.sounds)}")
    for nome in sorted(audio.sounds.keys()):
        print(f"  - {nome}")
    
    # Lista grupos
    print(f"\n🎭 Grupos de sons: {len(audio.sound_groups)}")
    for nome in sorted(audio.sound_groups.keys()):
        print(f"  - {nome} ({len(audio.sound_groups[nome])} variações)")
    
    # Testa cada categoria
    print("\n🎮 Testando categorias...")
    
    categorias = {
        "Golpes": ["punch", "kick", "slash"],
        "Magias": ["fireball_cast", "ice_impact", "lightning_bolt"],
        "Skills": ["dash_whoosh", "buff_activate", "heal_cast"],
        "Eventos": ["ko_impact", "perfect_block", "wall_hit"]
    }
    
    for categoria, sons in categorias.items():
        print(f"\n🔊 {categoria}:")
        for som in sons:
            print(f"  Testando: {som}...")
            audio.play(som)
            # time.sleep(0.5)  # Pausa entre testes


# =============================================================================
# EXECUTAR EXEMPLOS
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EXEMPLOS DE CUSTOMIZAÇÃO DE ÁUDIO - NEURAL FIGHTS")
    print("=" * 70)
    
    # Inicializa pygame e audio
    import pygame
    pygame.init()
    pygame.mixer.init()
    
    # Descomente para testar:
    # testar_sons()
    # exemplo_adicionar_grupo()
    # exemplo_sons_por_personagem()
    
    print("\n✅ Exemplos carregados!")
    print("📖 Leia os comentários no código para mais detalhes")
    print("🎵 Boa customização!")
