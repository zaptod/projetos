"""
Real-time debug for simulation - patches the Simulador to show arena info
Run this instead of run.py
"""
import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation.simulacao import Simulador
from utils.config import PPM, LARGURA, ALTURA

# Store original desenhar
original_desenhar = Simulador.desenhar

def patched_desenhar(self):
    """Patched desenhar that adds debug overlay"""
    # Call original
    original_desenhar(self)
    
    # Add debug overlay
    font = pygame.font.Font(None, 20)
    
    # Arena info
    if self.arena:
        texts = [
            f"[DEBUG] Arena: {self.arena.config.nome}",
            f"[DEBUG] Obstacles: {len(self.arena.obstaculos)}",
            f"[DEBUG] Camera: ({self.cam.x:.0f}, {self.cam.y:.0f}) zoom={self.cam.zoom:.2f}",
        ]
        
        # DRAW OBSTACLES DIRECTLY HERE - bypassing arena._desenhar_obstaculos
        for i, obs in enumerate(self.arena.obstaculos):
            sx, sy = self.cam.converter(obs.x * PPM, obs.y * PPM)
            size = self.cam.converter_tam(obs.largura * PPM / 2)
            texts.append(f"[DEBUG] Obs {i}: screen=({sx}, {sy}) size={size}")
            
            # Draw FILLED green circle
            pygame.draw.circle(self.tela, (0, 255, 0), (sx, sy), max(25, int(size)))
            # Draw magenta outline on top
            pygame.draw.circle(self.tela, (255, 0, 255), (sx, sy), max(25, int(size)), 3)
    else:
        texts = ["[DEBUG] self.arena is None!"]
    
    # Draw debug text in top-right
    y = 10
    for text in texts:
        surf = font.render(text, True, (255, 255, 0))
        self.tela.blit(surf, (LARGURA - surf.get_width() - 10, y))
        y += 18

# Patch the method
Simulador.desenhar = patched_desenhar

def main():
    print("=== RUNNING SIMULATION WITH DEBUG OVERLAY ===")
    print("Look for magenta circles where obstacles should be")
    print("Debug info will appear in top-right corner")
    print("=" * 50)
    
    sim = Simulador()
    
    # Print arena info after creation
    print(f"\nAfter Simulador init:")
    print(f"  sim.arena = {sim.arena}")
    if sim.arena:
        print(f"  Arena name: {sim.arena.config.nome}")
        print(f"  Obstacles: {len(sim.arena.obstaculos)}")
        for i, obs in enumerate(sim.arena.obstaculos):
            print(f"    {i}: {obs.tipo} at ({obs.x}, {obs.y})")
    
    sim.run()

if __name__ == "__main__":
    main()
