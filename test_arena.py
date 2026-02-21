"""
Test file to debug arena obstacle drawing
"""
import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import PPM, LARGURA, ALTURA
from core.arena import Arena, ARENAS, set_arena
from effects.camera import Câmera

def main():
    pygame.init()
    screen = pygame.display.set_mode((LARGURA, ALTURA))
    pygame.display.set_caption("Arena Test - Press SPACE to toggle zoom")
    clock = pygame.time.Clock()
    
    # Create arena - Coliseu
    print("=== TESTING COLISEU ARENA ===")
    arena = set_arena("Coliseu")
    print(f"Arena: {arena.config.nome}")
    print(f"Size: {arena.largura}x{arena.altura} meters")
    print(f"Obstacles count: {len(arena.obstaculos)}")
    for i, obs in enumerate(arena.obstaculos):
        print(f"  Obstacle {i}: type={obs.tipo}, pos=({obs.x}, {obs.y})")
    
    # Create camera centered on arena
    cam = Câmera()
    cam.set_arena_bounds(arena.centro_x, arena.centro_y, arena.largura, arena.altura)
    
    zoomed_in = False
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_SPACE:
                    zoomed_in = not zoomed_in
                    if zoomed_in:
                        # Simulate zoomed-in on fighters in center
                        cam.zoom = 1.0
                        cam.x = 17.5 * PPM  # Center of 35m arena
                        cam.y = 17.5 * PPM
                    else:
                        # Full arena view
                        cam.set_arena_bounds(arena.centro_x, arena.centro_y, arena.largura, arena.altura)
        
        # Clear screen
        screen.fill((30, 30, 30))
        
        # Draw arena
        arena.desenhar(screen, cam)
        
        # Draw reference circles where obstacles SHOULD be
        for obs in arena.obstaculos:
            sx, sy = cam.converter(obs.x * PPM, obs.y * PPM)
            # Draw a white outline circle at each obstacle position
            pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 25, 2)
        
        # Info text
        font = pygame.font.Font(None, 24)
        texts = [
            f"Arena: {arena.config.nome}",
            f"Obstacles: {len(arena.obstaculos)}",
            f"Camera: ({cam.x:.0f}, {cam.y:.0f}) zoom={cam.zoom:.2f}",
            f"Zoomed: {zoomed_in} (Press SPACE to toggle)",
            "Press ESC to quit"
        ]
        for i, text in enumerate(texts):
            surf = font.render(text, True, (255, 255, 255))
            screen.blit(surf, (10, 10 + i * 25))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    main()
