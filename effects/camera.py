"""
NEURAL FIGHTS - Sistema de Câmera BULLETPROOF v9.0
=================================================
GARANTIA ABSOLUTA: NUNCA perde os lutadores de vista.

Como funciona:
1. Calcula bounding box de TODOS os lutadores
2. Calcula zoom MÍNIMO para caber todos na tela
3. Se algum lutador sair da tela = ZOOM OUT INSTANTÂNEO
4. Centro sempre exatamente entre os lutadores
"""

import random
import math
from utils.config import LARGURA, ALTURA, PPM


class Câmera:
    """
    Câmera do jogo com zoom dinâmico GARANTIDO.
    
    Esta câmera foi projetada para NUNCA perder os lutadores de vista,
    mesmo com knockbacks extremos de Berserkers ou Colossos.
    
    Suporta diferentes resoluções (modo paisagem e retrato).
    """
    
    def __init__(self, screen_width: int = None, screen_height: int = None):
        # Dimensões da tela (permite override para modo retrato)
        self.screen_width = screen_width if screen_width else LARGURA
        self.screen_height = screen_height if screen_height else ALTURA
        
        # Posição da câmera (centro da visão em pixels do mundo)
        self.x = 15.0 * PPM  # Centro da arena padrão
        self.y = 10.0 * PPM
        
        # Zoom atual e alvo
        self.zoom = 0.8  # Começa mais afastado
        self.target_zoom = 0.8
        
        # Modo de câmera
        self.modo = "AUTO"  # AUTO, P1, P2, FIXO, MANUAL
        self.shake_timer = 0.0
        self.shake_magnitude = 0.0
        self.offset_x = 0
        self.offset_y = 0
        
        # === PARÂMETROS BULLETPROOF v9.0 ===
        # Ajusta margens baseado no tamanho da tela
        min_dim = min(self.screen_width, self.screen_height)
        self.margem_segura = int(min_dim * 0.12)  # ~12% da menor dimensão
        self.margem_critica = int(min_dim * 0.02)  # ~2% da menor dimensão
        self.zoom_min = 0.15         # Pode mostrar arena ENORME se necessário
        self.zoom_max = 1.6          # Zoom máximo (combate próximo)
        self.velocidade_zoom_in = 2.0   # Zoom in é suave
        self.velocidade_zoom_out = 15.0 # Zoom out é RÁPIDO
        self.velocidade_pan = 8.0       # Movimento da câmera
        
        # Tracking de velocidade para enquadramento preditivo
        self._prev_centro = None
        self._velocidade_centro = (0, 0)
        
        # === ARENA BOUNDS (opcional) ===
        self.arena_centro = None  # (x, y) em metros
        self.arena_tamanho = None  # (largura, altura) em metros
        
        # Debug
        self._emergency_zoom_count = 0

    def set_arena_bounds(self, centro_x: float, centro_y: float, largura: float, altura: float):
        """
        Define os limites da arena para a câmera.
        Coordenadas em METROS.
        """
        self.arena_centro = (centro_x, centro_y)
        self.arena_tamanho = (largura, altura)
        
        # Centraliza câmera na arena
        self.x = centro_x * PPM
        self.y = centro_y * PPM
        
        # Ajusta zoom inicial para ver a arena toda
        zoom_x = (self.screen_width - self.margem_segura * 2) / (largura * PPM)
        zoom_y = (self.screen_height - self.margem_segura * 2) / (altura * PPM)
        self.zoom = min(zoom_x, zoom_y, 1.0)
        self.target_zoom = self.zoom

    def aplicar_shake(self, forca, duracao=0.2):
        """Aplica efeito de shake na câmera"""
        self.shake_magnitude = max(self.shake_magnitude, forca)
        self.shake_timer = max(self.shake_timer, duracao)

    def converter(self, world_x, world_y):
        """Converte coordenadas do mundo para tela"""
        screen_x = (world_x - self.x) * self.zoom + self.screen_width / 2 + self.offset_x
        screen_y = (world_y - self.y) * self.zoom + self.screen_height / 2 + self.offset_y
        return int(screen_x), int(screen_y)

    def converter_tam(self, tamanho):
        """Converte tamanho do mundo para tela"""
        return int(tamanho * self.zoom)
    
    def _get_posicao_tela(self, lutador):
        """Retorna posição do lutador na TELA (não no mundo)"""
        if lutador is None:
            return (self.screen_width // 2, self.screen_height // 2)  # Centro da tela como fallback
        x = lutador.pos[0] * PPM
        y = lutador.pos[1] * PPM
        z = getattr(lutador, 'z', 0) * PPM  # Altura (pulo)
        return self.converter(x, y - z)
    
    def _lutador_visivel(self, lutador) -> bool:
        """
        Verifica se o lutador está visível na tela.
        Retorna False se estiver fora ou muito perto da borda.
        """
        sx, sy = self._get_posicao_tela(lutador)
        
        # Usa margem crítica (bem menor que margem segura)
        return (self.margem_critica < sx < self.screen_width - self.margem_critica and
                self.margem_critica < sy < self.screen_height - self.margem_critica)
    
    def _lutador_na_zona_segura(self, lutador) -> bool:
        """Verifica se o lutador está na zona segura (com margem)"""
        sx, sy = self._get_posicao_tela(lutador)
        return (self.margem_segura < sx < self.screen_width - self.margem_segura and
                self.margem_segura < sy < self.screen_height - self.margem_segura)
    
    def _calcular_bounding_box(self, p1, p2):
        """
        Calcula a bounding box que contém ambos os lutadores.
        Retorna: (min_x, min_y, max_x, max_y) em pixels do mundo
        """
        # Posições em pixels
        x1, y1 = p1.pos[0] * PPM, p1.pos[1] * PPM
        x2, y2 = p2.pos[0] * PPM, p2.pos[1] * PPM
        
        # Considera altura Z (pulos/knockback vertical)
        z1 = getattr(p1, 'z', 0) * PPM
        z2 = getattr(p2, 'z', 0) * PPM
        
        # Tamanho visual dos lutadores (um pouco maior que hitbox)
        raio1 = getattr(p1, 'raio_fisico', 0.5) * PPM * 2
        raio2 = getattr(p2, 'raio_fisico', 0.5) * PPM * 2
        
        # Bounding box expandida
        min_x = min(x1 - raio1, x2 - raio2)
        max_x = max(x1 + raio1, x2 + raio2)
        min_y = min(y1 - raio1 - z1, y2 - raio2 - z2)  # Considera altura
        max_y = max(y1 + raio1, y2 + raio2)
        
        return min_x, min_y, max_x, max_y
    
    def _calcular_zoom_necessario(self, p1, p2) -> float:
        """
        Calcula o zoom NECESSÁRIO para manter ambos os lutadores visíveis.
        Este é o zoom MÍNIMO - não podemos ter zoom MAIOR que isso.
        """
        # Bounding box dos lutadores
        min_x, min_y, max_x, max_y = self._calcular_bounding_box(p1, p2)
        
        # Tamanho necessário para enquadrar (com margem segura)
        largura_mundo = (max_x - min_x)
        altura_mundo = (max_y - min_y)
        
        # Espaço disponível na tela (descontando margens)
        largura_tela = self.screen_width - self.margem_segura * 2
        altura_tela = self.screen_height - self.margem_segura * 2
        
        # Zoom necessário em cada eixo
        if largura_mundo > 0:
            zoom_x = largura_tela / largura_mundo
        else:
            zoom_x = self.zoom_max
            
        if altura_mundo > 0:
            zoom_y = altura_tela / altura_mundo
        else:
            zoom_y = self.zoom_max
        
        # Usa o MENOR zoom (para garantir que tudo caiba)
        zoom_necessario = min(zoom_x, zoom_y)
        
        # Clamp aos limites
        return max(self.zoom_min, min(self.zoom_max, zoom_necessario))
    
    def _calcular_centro_ideal(self, p1, p2) -> tuple:
        """
        Calcula o centro ideal da câmera para enquadrar ambos os lutadores.
        Retorna: (x, y) em pixels do mundo
        """
        # Centro exato entre os lutadores
        cx = (p1.pos[0] + p2.pos[0]) / 2 * PPM
        cy = (p1.pos[1] + p2.pos[1]) / 2 * PPM
        
        # Considera altura Z
        z1 = getattr(p1, 'z', 0) * PPM
        z2 = getattr(p2, 'z', 0) * PPM
        cy -= (z1 + z2) / 4  # Ajusta levemente para cima se estiverem pulando
        
        return cx, cy
    
    def _aplicar_zoom_emergencia(self, p1, p2):
        """
        Aplica zoom de emergência se algum lutador estiver fora da tela.
        INSTANTÂNEO - não suaviza.
        """
        # Se algum lutador for None, não há emergência
        if p1 is None or p2 is None:
            return False
        
        # Verifica se ambos estão visíveis
        p1_visivel = self._lutador_visivel(p1)
        p2_visivel = self._lutador_visivel(p2)
        
        if not p1_visivel or not p2_visivel:
            self._emergency_zoom_count += 1
            
            # Calcula zoom necessário para ver ambos
            zoom_necessario = self._calcular_zoom_necessario(p1, p2)
            
            # APLICA IMEDIATAMENTE (sem suavização)
            if zoom_necessario < self.zoom:
                self.zoom = zoom_necessario
                self.target_zoom = zoom_necessario
            
            # Também centraliza imediatamente
            cx, cy = self._calcular_centro_ideal(p1, p2)
            self.x = cx
            self.y = cy
            
            return True
        
        return False

    def atualizar(self, dt, p1, p2):
        """Atualiza a câmera baseado nos lutadores"""
        
        # === SHAKE ===
        if self.shake_timer > 0:
            self.shake_timer -= dt
            decay = min(1.0, self.shake_timer / 0.3)
            shake_atual = self.shake_magnitude * decay * decay
            self.offset_x = random.uniform(-shake_atual, shake_atual)
            self.offset_y = random.uniform(-shake_atual, shake_atual)
        else:
            self.offset_x *= 0.8
            self.offset_y *= 0.8
            self.shake_magnitude = 0
        
        # === MODO MANUAL (teclas WASD) ===
        if self.modo == "MANUAL":
            return
        
        # === PASSO 1: VERIFICAÇÃO DE EMERGÊNCIA ===
        # Se algum lutador estiver fora da tela, AÇÃO IMEDIATA
        if p1 is None or p2 is None:
            return  # Não pode atualizar sem lutadores
        
        emergencia = self._aplicar_zoom_emergencia(p1, p2)
        
        if emergencia:
            # Após emergência, retorna - próximo frame vai suavizar
            return
        
        # === PASSO 2: CÁLCULO DO ZOOM IDEAL ===
        if self.modo == "AUTO":
            zoom_necessario = self._calcular_zoom_necessario(p1, p2)
            
            # Adiciona um pouco de "drama" baseado na distância
            dist = math.hypot(p1.pos[0] - p2.pos[0], p1.pos[1] - p2.pos[1])
            
            # Combate muito próximo = pode dar zoom in (mas não mais que o necessário)
            if dist < 3.0:
                zoom_desejado = min(zoom_necessario * 1.3, self.zoom_max)
            else:
                zoom_desejado = zoom_necessario
            
            # Vida crítica = ligeiramente mais zoom
            vida_min = min(
                p1.vida / p1.vida_max if p1.vida_max > 0 else 1,
                p2.vida / p2.vida_max if p2.vida_max > 0 else 1
            )
            if vida_min < 0.25:
                zoom_desejado = min(zoom_desejado * 1.1, self.zoom_max)
            
            # === ATUALIZAÇÃO DO TARGET ZOOM ===
            # Zoom OUT é rápido, zoom IN é suave
            if zoom_desejado < self.target_zoom:
                # Precisa dar zoom out - rápido!
                velocidade = self.velocidade_zoom_out
            else:
                # Zoom in - pode ser suave
                velocidade = self.velocidade_zoom_in
            
            # Suaviza transição do target
            diff = zoom_desejado - self.target_zoom
            self.target_zoom += diff * velocidade * dt
            
            # === VERIFICAÇÃO FINAL DE SEGURANÇA ===
            # Garante que o target_zoom NUNCA seja maior que o necessário
            self.target_zoom = min(self.target_zoom, zoom_necessario * 1.1)
        
        elif self.modo == "P1":
            # Segue P1
            self.target_zoom = 1.2
        elif self.modo == "P2":
            # Segue P2
            self.target_zoom = 1.2
        
        # === PASSO 3: APLICA ZOOM SUAVEMENTE ===
        if self.zoom < self.target_zoom:
            # Zoom in
            self.zoom += (self.target_zoom - self.zoom) * 3 * dt
        else:
            # Zoom out - mais rápido
            self.zoom += (self.target_zoom - self.zoom) * 8 * dt
        
        self.zoom = max(self.zoom_min, min(self.zoom_max, self.zoom))
        
        # === PASSO 4: ATUALIZA POSIÇÃO DA CÂMERA ===
        if self.modo == "P1":
            tx, ty = p1.pos[0] * PPM, p1.pos[1] * PPM
            self.lerp_pos(tx, ty, dt, self.velocidade_pan)
        elif self.modo == "P2":
            tx, ty = p2.pos[0] * PPM, p2.pos[1] * PPM
            self.lerp_pos(tx, ty, dt, self.velocidade_pan)
        elif self.modo == "AUTO":
            cx, cy = self._calcular_centro_ideal(p1, p2)
            
            # === ENQUADRAMENTO PREDITIVO ===
            if self._prev_centro is not None:
                vel_x = (cx - self._prev_centro[0]) / dt if dt > 0 else 0
                vel_y = (cy - self._prev_centro[1]) / dt if dt > 0 else 0
                
                # Suaviza velocidade
                self._velocidade_centro = (
                    self._velocidade_centro[0] * 0.9 + vel_x * 0.1,
                    self._velocidade_centro[1] * 0.9 + vel_y * 0.1
                )
                
                # Antecipa ligeiramente (olha para onde estão indo)
                predicao = 0.1  # Segundos
                cx += self._velocidade_centro[0] * predicao
                cy += self._velocidade_centro[1] * predicao
            
            self._prev_centro = self._calcular_centro_ideal(p1, p2)
            
            # Acelera câmera se lutador perto da borda
            velocidade = self.velocidade_pan
            if not self._lutador_na_zona_segura(p1) or not self._lutador_na_zona_segura(p2):
                velocidade = self.velocidade_pan * 2
            
            self.lerp_pos(cx, cy, dt, velocidade)
        
        # === PASSO 5: VERIFICAÇÃO FINAL ===
        # Se MESMO ASSIM algum lutador estiver fora, força zoom
        if not self._lutador_visivel(p1) or not self._lutador_visivel(p2):
            zoom_min_necessario = self._calcular_zoom_necessario(p1, p2)
            if self.zoom > zoom_min_necessario:
                self.zoom = zoom_min_necessario

    def zoom_punch(self, intensidade=0.1, duracao=0.1):
        """Efeito de zoom punch para impactos"""
        # Apenas aumenta um pouco - o sistema vai corrigir
        self.target_zoom = min(self.target_zoom + intensidade, self.zoom_max)
    
    def lerp_pos(self, tx, ty, dt, velocidade=5.0):
        """Interpola suavemente a posição da câmera"""
        self.x += (tx - self.x) * velocidade * dt
        self.y += (ty - self.y) * velocidade * dt
    
    def esta_visivel(self, world_x, world_y, margem=50):
        """Verifica se uma posição do mundo está visível na tela"""
        sx, sy = self.converter(world_x, world_y)
        return -margem < sx < LARGURA + margem and -margem < sy < ALTURA + margem
    
    def get_bounds_mundo(self):
        """Retorna os limites do mundo visíveis na tela"""
        min_x = self.x - (LARGURA / 2) / self.zoom
        max_x = self.x + (LARGURA / 2) / self.zoom
        min_y = self.y - (ALTURA / 2) / self.zoom
        max_y = self.y + (ALTURA / 2) / self.zoom
        return min_x, min_y, max_x, max_y
