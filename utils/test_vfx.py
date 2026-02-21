"""
NEURAL FIGHTS - Teste de Efeitos Visuais Dramáticos v11.0
=========================================================
Demonstra todos os novos efeitos de magia de forma visual.
"""

import pygame
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from effects.magic_vfx import (
    MagicVFXManager,
    MagicParticle,
    DramaticExplosion,
    DramaticBeam,
    DramaticAura,
    DramaticSummon,
    ELEMENT_PALETTES
)

# Câmera simples para teste
class DummyCamera:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.x = width // 2
        self.y = height // 2
        self.zoom = 1.0
    
    def converter(self, x, y):
        return int(x), int(y)
    
    def converter_tam(self, tam):
        return int(tam * self.zoom)


def main():
    pygame.init()
    pygame.mixer.init()
    
    WIDTH, HEIGHT = 1200, 800
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Neural Fights - VFX Test v11.0")
    clock = pygame.time.Clock()
    
    # Câmera dummy
    cam = DummyCamera(WIDTH, HEIGHT)
    
    # Manager de VFX
    vfx = MagicVFXManager.get_instance()
    
    # Fonte para texto
    font = pygame.font.Font(None, 24)
    font_big = pygame.font.Font(None, 36)
    
    # Elementos disponíveis
    elementos = list(ELEMENT_PALETTES.keys())
    elemento_atual = 0
    
    # Estado
    running = True
    auto_spawn = False
    auto_timer = 0
    
    # Instruções
    instrucoes = [
        "CLIQUE ESQUERDO: Explosão",
        "CLIQUE DIREITO: Beam (para cursor)",
        "SCROLL: Mudar elemento",
        "1: Spawn Aura no centro",
        "2: Spawn Summon no centro",
        "3: Explosão em todos elementos",
        "SPACE: Auto-spawn ligado/desligado",
        "R: Reset efeitos",
        "ESC: Sair"
    ]
    
    while running:
        dt = clock.tick(60) / 1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    
                elif event.key == pygame.K_r:
                    MagicVFXManager.reset()
                    vfx = MagicVFXManager.get_instance()
                    
                elif event.key == pygame.K_SPACE:
                    auto_spawn = not auto_spawn
                    
                elif event.key == pygame.K_1:
                    # Aura no centro
                    elem = elementos[elemento_atual]
                    vfx.spawn_aura(WIDTH//2, HEIGHT//2, 100, elem, 2.0)
                    
                elif event.key == pygame.K_2:
                    # Summon no centro
                    elem = elementos[elemento_atual]
                    vfx.spawn_summon(WIDTH//2, HEIGHT//2, elem)
                    
                elif event.key == pygame.K_3:
                    # Explosão em cada elemento
                    for i, elem in enumerate(elementos):
                        x = 100 + (i % 6) * 180
                        y = 200 + (i // 6) * 250
                        vfx.spawn_explosion(x, y, elem, 1.0, 30)
            
            elif event.type == pygame.MOUSEWHEEL:
                elemento_atual = (elemento_atual + event.y) % len(elementos)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                elem = elementos[elemento_atual]
                
                if event.button == 1:  # Esquerdo - explosão
                    vfx.spawn_explosion(mx, my, elem, 1.0, 30)
                    
                elif event.button == 3:  # Direito - beam
                    vfx.spawn_beam(WIDTH//2, HEIGHT//2, mx, my, elem, 8)
        
        # Auto spawn
        if auto_spawn:
            auto_timer += dt
            if auto_timer > 0.5:
                auto_timer = 0
                elem = random.choice(elementos)
                x = random.randint(100, WIDTH - 100)
                y = random.randint(100, HEIGHT - 100)
                
                effect_type = random.choice(["explosion", "beam", "aura", "summon"])
                if effect_type == "explosion":
                    vfx.spawn_explosion(x, y, elem, random.uniform(0.5, 1.5), random.randint(10, 50))
                elif effect_type == "beam":
                    x2 = random.randint(100, WIDTH - 100)
                    y2 = random.randint(100, HEIGHT - 100)
                    vfx.spawn_beam(x, y, x2, y2, elem, random.randint(5, 12))
                elif effect_type == "aura":
                    vfx.spawn_aura(x, y, random.randint(50, 150), elem, random.uniform(0.5, 2.0))
                elif effect_type == "summon":
                    vfx.spawn_summon(x, y, elem)
        
        # Update
        vfx.update(dt)
        
        # Draw
        screen.fill((20, 20, 30))
        
        # Grid de fundo
        for x in range(0, WIDTH, 50):
            pygame.draw.line(screen, (30, 30, 40), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 50):
            pygame.draw.line(screen, (30, 30, 40), (0, y), (WIDTH, y))
        
        # Desenha VFX
        vfx.draw(screen, cam)
        
        # UI
        # Elemento atual
        elem = elementos[elemento_atual]
        palette = ELEMENT_PALETTES[elem]
        cor = palette["mid"][0] if palette["mid"] else (255, 255, 255)
        
        pygame.draw.rect(screen, (40, 40, 50), (10, 10, 200, 40))
        txt = font_big.render(f"Elemento: {elem}", True, cor)
        screen.blit(txt, (20, 18))
        
        # Swatch de cores do elemento
        pygame.draw.rect(screen, palette["core"], (220, 10, 30, 30))
        for i, c in enumerate(palette["mid"][:3]):
            pygame.draw.rect(screen, c, (255 + i*35, 10, 30, 30))
        for i, c in enumerate(palette["outer"][:3]):
            pygame.draw.rect(screen, c, (360 + i*35, 10, 30, 30))
        
        # Status
        status = "AUTO: ON" if auto_spawn else "AUTO: OFF"
        status_cor = (100, 255, 100) if auto_spawn else (255, 100, 100)
        txt = font.render(status, True, status_cor)
        screen.blit(txt, (WIDTH - 100, 15))
        
        # Contadores
        count_txt = f"Explosões: {len(vfx.explosions)} | Beams: {len(vfx.beams)} | Auras: {len(vfx.auras)} | Summons: {len(vfx.summons)}"
        txt = font.render(count_txt, True, (200, 200, 200))
        screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT - 30))
        
        # Instruções
        pygame.draw.rect(screen, (40, 40, 50, 200), (10, 60, 280, len(instrucoes) * 22 + 10))
        for i, instr in enumerate(instrucoes):
            txt = font.render(instr, True, (180, 180, 180))
            screen.blit(txt, (15, 65 + i * 22))
        
        pygame.display.flip()
    
    pygame.quit()
    print("Teste concluído!")


if __name__ == "__main__":
    main()
