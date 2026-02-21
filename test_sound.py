"""Test sound system"""
import os
os.chdir(r'c:\Users\adrian\Desktop\projetos\.venv\neural')

import pygame
pygame.init()
pygame.mixer.init()

from effects.audio import AudioManager

# Create audio manager
audio = AudioManager.get_instance()

print(f"Audio enabled: {audio.enabled}")
print(f"Sounds loaded: {list(audio.sounds.keys())}")
print(f"Sound groups: {list(audio.sound_groups.keys())}")

# Play directly to test
print("\nPlaying wall_impact_light directly at FULL VOLUME...")
if 'wall_impact_light' in audio.sounds:
    sound = audio.sounds['wall_impact_light']
    sound.set_volume(1.0)  # Max volume
    sound.play()
    print("Playing NOW!")
else:
    print("Sound not found!")

import time
time.sleep(3)
print("Done!")
