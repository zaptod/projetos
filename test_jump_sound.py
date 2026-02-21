"""
Quick test to verify jump sound triggering in-game.
Run this then watch console for [SOUND] messages.
"""
import pygame
pygame.init()
pygame.mixer.init()

from effects.audio import AudioManager

# Test the audio system directly
print("=== TESTING AUDIO SYSTEM ===")
audio = AudioManager.get_instance()

print("\n1. Testing play_movement('jump')...")
audio.play_movement("jump", 10.0, 10.0)

import time
time.sleep(1)

print("\n2. Testing play_movement('land')...")
audio.play_movement("land", 10.0, 10.0)

time.sleep(1)

print("\n3. Testing direct play('jump_start')...")
audio.play("jump_start")

time.sleep(1)

print("\n4. Testing direct play from group 'jump'...")
audio.play("jump")

time.sleep(2)

print("\n=== TEST COMPLETE ===")
print("If you heard sounds, the audio system is working.")
print("The issue might be in jump detection thresholds.")
