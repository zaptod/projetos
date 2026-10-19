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
from neural_fights.utils.config import LARGURA, ALTURA, PPM
from neural_fights.utils.config import (
    FESTA_ALCANCE_RAIOS,
    FESTA_ALCANCE_TELA_MAX,
    FESTA_ALCANCE_TELA_MIN,
    FESTA_ALTURA_PULO,
    FESTA_BOCA_RAIOS,
    FESTA_QUEDA_RAIOS,
)


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
        # ARENA (padrão): enquadra a arena inteira, sem seguir lutadores.
        # AUTO: zoom dinâmico seguindo os lutadores. P1/P2: segue um lado.
        # DIRETOR: câmera de transmissão para VÍDEO (ver _atualizar_modo_diretor).
        # MANUAL: WASD. (tecla 0 volta para ARENA, tecla 3 liga AUTO)
        self.modo = "ARENA"  # ARENA, AUTO, DIRETOR, P1, P2, FIXO, MANUAL
        self.zoom_arena = None  # calculado em set_arena_bounds

        # === MODO DIRETOR (Onda 9: a luta como vídeo) ===
        # O AUTO é câmera de JOGO: pan a 8/s, predição, punch, zoom de
        # emergência a cada knockback — no celular isso enjoa ("câmera que
        # persegue cansa"). O ARENA é o oposto: quadro travado, lutadores com
        # 5% da largura no 9:16. O DIRETOR fica no meio, como uma câmera de
        # transmissão esportiva: zona morta (o centro pode oscilar sem a
        # câmera mexer), pan lento, zoom-in só depois de 1 s de estabilidade,
        # zoom-out rápido (nunca perde ninguém), sem tremor e sem punch.
        # Só LÊ posições: não toca em nada que altere o combate.
        self.diretor_deadzone = 0.06          # fração da menor dimensão
        self.diretor_pan = 2.4                # lerp/s do pan (AUTO usa 8)
        self.diretor_pan_urgente = 7.0        # lerp/s com alguém na borda
        self.diretor_zoom_in = 1.1            # lerp/s fechando o quadro
        self.diretor_zoom_out = 6.0           # lerp/s abrindo o quadro
        self.diretor_espera_zoom_in = 1.5     # s de estabilidade antes de fechar
        self.diretor_histerese_zoom = 0.12    # fecha só se o alvo passa de +12%
        # Abre só se o alvo cai abaixo de -8%: `necessario` já embute a margem
        # segura (12%), então 8% de folga ainda deixa os dois no quadro — e a
        # correção de emergência cobre o resto. Com 3% um arqueiro em kiting
        # fazia a câmera respirar 20 vezes por minuto.
        self.diretor_histerese_zoom_out = 0.08
        # O teto de zoom é em METROS, não em fator: o lado menor da tela
        # nunca mostra menos que `largura_min_m`. Em 1080x1920 isso dá zoom
        # ~3,1 (o 1,6 do AUTO foi calibrado para 1200x800 e deixava o
        # lutador com 6% da largura no vertical). `zoom_max` é o freio
        # absoluto para telas gigantes.
        self.diretor_largura_min_m = 7.0
        self.diretor_zoom_max = 4.0
        self.diretor_push_ko = 1.25           # push-in no nocaute
        self.diretor_fora_arena = 0.35        # fração da janela que pode sair da arena
        # Pós-K.O. (14/10/2026, ``_enquadrar_pos_ko``): enquadra os dois se o
        # vencedor ainda ocupa esta fração da largura; senão, só o vencedor.
        # A caixa inclui o pulo e o alcance do confete da festa.
        self.diretor_pos_ko_fracao_min = 0.15
        self.diretor_pos_ko_lerp = 3.5        # lerp/s (exponencial: sem salto)
        self.diretor_pos_ko_margem = 0.04     # fração do lado menor, por borda
        # Área da tela (x0, y0, x1, y1, em frações) onde a festa cabe. Abaixo
        # de 60% fica o veredito do vídeo (renderer VEREDITO_ZONA, 62–76%) e,
        # mais abaixo, a legenda/botões do TikTok e do Shorts (20% de baixo);
        # os 12% da direita são a coluna de botões das plataformas.
        self.diretor_pos_ko_area = (0.0, 0.0, 0.88, 0.60)
        # Fração da janela que pode mostrar o lado de fora da arena na cauda.
        # A luta aceita 35% (``diretor_fora_arena``); na festa o quadro é de
        # um lutador só e a parede encostada mostrava 47% de nada (Torre,
        # 15/10). O rosto e o nome do vencedor ainda ganham deste limite.
        self.diretor_pos_ko_fora_arena = 0.0
        # Letreiro do K.O. do vídeo ("K.O."/"ACABOU", desenhado pelo renderer
        # do random_builds por cima do clipe; 15/10, conferente): enquanto ele
        # está na tela, o topo da área pós-K.O. fica ABAIXO dele. Quem grava
        # diz onde ele termina (``topo``: borda de baixo, fração da altura,
        # lida da caixa real do letreiro) e até quando (``ate_s``: segundos de
        # parede depois do K.O.). None = não há letreiro (jogo, palco).
        # ``hud`` (opcional, 18/10/2026): borda de baixo do HUD do vídeo, que
        # fica na tela a cauda inteira; o topo da área nunca sobe acima dele.
        self.reserva_pos_ko = None
        self.t_pos_ko = None                  # o Simulador escreve, no pós-K.O.
        self.pulo_pos_ko = None               # idem: pulo da festa agora, em raios
        # Maior deslocamento da imagem por ATUALIZAÇÃO (o gravador atualiza a
        # 60 Hz e grava a 30 fps: 2 por quadro → até 10 px por quadro).
        self.diretor_pos_ko_degrau_max_px = 5.0
        self.diretor_pos_ko_degrau_ate_s = 1.0      # segundos de parede depois do K.O.
        # Teto de tranco da correção da área da luta (HUD + coluna de botões):
        # px por quadro de 30 fps, o que o conferente aceitou (19/10/2026).
        # Vira orçamento por passo (``dt`` × 30 quadros/s), dividido entre a
        # correção do passo e a de depois da física.
        self.diretor_area_degrau_max_px = 26.0
        self._orcamento_area = 0.0
        self._pos_ko_topo = None
        self._diretor_t = 0.0
        self._diretor_estavel_desde = None
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
        # O teto era 1.0, e isso QUEBRAVA a promessa do modo ARENA ("enquadra
        # a arena inteira"): arena menor que a tela nao era ampliada, ficava
        # pequena no meio dela. Medido em 1080x1920: Ringue e as verticais
        # 9:16 travavam todas em zoom 1.0 e o corpo saia com os mesmos 5% da
        # largura — o palco menor nao chegava na tela, so encolhia a arena.
        # O teto agora e `zoom_max`, o mesmo do combate proximo. Nada borra:
        # os corpos e o cenario sao desenhados por vetor (pygame.draw) na
        # escala da camera, nao sao bitmaps esticados.
        self.zoom = min(zoom_x, zoom_y, self.zoom_max)
        self.target_zoom = self.zoom
        # Zoom que enquadra a arena inteira — alvo permanente do modo ARENA
        self.zoom_arena = self.zoom

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
    
    def _calcular_zoom_necessario(self, p1, p2, zoom_max: float | None = None) -> float:
        """
        Calcula o zoom NECESSÁRIO para manter ambos os lutadores visíveis.
        Este é o zoom MÍNIMO - não podemos ter zoom MAIOR que isso.
        `zoom_max` sobrepõe o teto da classe (o DIRETOR usa o teto em metros).
        """
        if zoom_max is None:
            zoom_max = self.zoom_max
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
        return max(self.zoom_min, min(zoom_max, zoom_necessario))

    def _diretor_teto_zoom(self) -> float:
        """Zoom em que o lado menor da tela mostra `diretor_largura_min_m`."""
        menor = min(self.screen_width, self.screen_height)
        return max(self.zoom_min,
                   min(self.diretor_zoom_max, menor / (self.diretor_largura_min_m * PPM)))
    
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

        # === MODO ARENA (padrão): quadro TRAVADO, nem tremor ===
        # O tremor de impacto é ótimo para quem joga, mas aqui a promessa é
        # outra: o enquadramento não se mexe. Consumimos os timers assim mesmo
        # para que trocar de modo no meio da luta não herde um tremor velho.
        if self.modo == "ARENA":
            self.shake_timer = max(0.0, self.shake_timer - dt)
            self.shake_magnitude = 0
            self.offset_x = 0
            self.offset_y = 0
            self._punch_mag = 0.0
            self._punch_timer = 0.0
            self._atualizar_modo_arena(dt, p1, p2)
            return

        # === MODO DIRETOR (vídeo): mesma promessa do ARENA quanto a tremor ===
        if self.modo == "DIRETOR":
            self.shake_timer = max(0.0, self.shake_timer - dt)
            self.shake_magnitude = 0
            self.offset_x = 0
            self.offset_y = 0
            self._punch_mag = 0.0
            self._punch_timer = 0.0
            self._atualizar_modo_diretor(dt, p1, p2)
            return

        # === SHAKE ===
        if self.shake_timer > 0:
            self.shake_timer -= dt
            decay = min(1.0, self.shake_timer / 0.3)
            # Teto DURO no aplicador central: nao importa quantas fontes
            # empilhem magnitude, o tremor visivel e tempero (<=12px),
            # nao prato ("a tela treme muito" — recalibragem global).
            shake_atual = min(12.0, self.shake_magnitude * 0.6) * decay * decay
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

        # === PASSO 6: ZOOM PUNCH (depois de TODOS os clamps) ===
        self._aplicar_punch(dt)

    def _atualizar_modo_arena(self, dt, p1, p2):
        """Enquadramento TRAVADO na arena inteira (modo padrão).

        A câmera não segue lutador, não faz pan e não muda de zoom: a cena é
        a arena, e a arena não se mexe. Quem assiste acompanha a LUTA, não a
        câmera — uma câmera que persegue os lutadores num quadro pequeno vira
        um enjoo, e é justamente o que este modo evita.

        Consequência aceita de propósito: um knockback que jogue alguém para
        fora dos limites da arena o tira do quadro por um instante. Preferimos
        isso a mexer o enquadramento.
        """
        if self.arena_centro is None:
            return

        self.x = self.arena_centro[0] * PPM
        self.y = self.arena_centro[1] * PPM
        if self.zoom_arena:
            self.zoom = self.zoom_arena

    # ------------------------------------------------------------ DIRETOR

    def _limitar_centro_a_arena(self, cx, cy, zoom=None, fora=None):
        """Clamp MACIO à arena: os lutadores ficam no centro, não a arena.

        A arena é o palco, mas quem manda no quadro é a luta. A janela pode
        avançar além da borda da arena até `diretor_fora_arena` da própria
        dimensão (35%): dois lutadores encostados na parede de cima aparecem
        a ~1/3 do topo, não colados nele. Só quando nem isso basta (janela
        muito maior que a arena naquele eixo) o eixo centraliza na arena.
        ``zoom`` (padrão: o atual) é o do quadro que se quer limitar e
        ``fora`` (padrão: ``diretor_fora_arena``) a fração que pode sair.
        """
        zoom = self.zoom if zoom is None else zoom
        if self.arena_centro is None or self.arena_tamanho is None or zoom <= 0:
            return cx, cy
        meia_w = (self.screen_width / 2) / zoom
        meia_h = (self.screen_height / 2) / zoom
        fora = self.diretor_fora_arena if fora is None else fora
        fora_w = fora * 2 * meia_w
        fora_h = fora * 2 * meia_h
        ax, ay = self.arena_centro[0] * PPM, self.arena_centro[1] * PPM
        meia_aw = self.arena_tamanho[0] * PPM / 2
        meia_ah = self.arena_tamanho[1] * PPM / 2
        lo_x = ax - meia_aw + meia_w - fora_w
        hi_x = ax + meia_aw - meia_w + fora_w
        lo_y = ay - meia_ah + meia_h - fora_h
        hi_y = ay + meia_ah - meia_h + fora_h
        cx = ax if lo_x > hi_x else max(lo_x, min(hi_x, cx))
        cy = ay if lo_y > hi_y else max(lo_y, min(hi_y, cy))
        return cx, cy

    def aplicar_momento(self, duracao=0.4):
        """Onda 10A: push-in curto para um momento (wall-splat, arremesso).

        Só o DIRETOR reage (fecha o quadro ~10% enquanto dura) e sem punch
        nem tremor — a promessa "câmera calma" da Onda 9 fica de pé. É um
        sinal só de leitura: quem chama é o motor, e o resultado da luta não
        depende dele (mesma doutrina do aplicar_shake).
        """
        try:
            duracao = float(duracao)
        except (TypeError, ValueError):
            duracao = 0.4
        self._momento_timer = max(getattr(self, "_momento_timer", 0.0), duracao)

    def _atualizar_modo_diretor(self, dt, p1, p2):
        """Câmera de transmissão: enquadra os dois sem perseguir cada passo.

        1. ZOOM com histerese assimétrica: abrir é urgente (alguém saindo do
           quadro), fechar só depois de `diretor_espera_zoom_in` s de
           estabilidade e só quando o alvo passa de +12% — senão a luta vira
           sanfona. No nocaute (alguém `morto`) o quadro fecha um pouco.
        2. PAN com zona morta: o ponto médio pode oscilar `deadzone` sem a
           câmera reagir; fora dela o movimento é um lerp lento.
        3. SEGURANÇA: lutador na margem crítica → correção imediata mínima.
        """
        if p1 is None or p2 is None or dt <= 0:
            return
        self._diretor_t += dt
        self._camera_no_comeco_do_passo = (self.x, self.y, self.zoom)
        self._orcamento_area = self.diretor_area_degrau_max_px * dt * 30.0

        # --- 0. pós-K.O.: a festa do vencedor manda no quadro ---
        p1_morto = bool(getattr(p1, "morto", False))
        p2_morto = bool(getattr(p2, "morto", False))
        if p1_morto != p2_morto:
            vencedor, perdedor = (p2, p1) if p1_morto else (p1, p2)
            self._enquadrar_pos_ko(dt, vencedor, perdedor)
            return

        # --- 1. zoom ---
        teto = self._diretor_teto_zoom()
        # com o HUD do vídeo na reserva, a faixa dele não conta como altura útil
        necessario = self._zoom_necessario_da_luta(p1, p2, teto)
        # Onda 10A: o zoom-in segue a distância FILTRADA (~2 s) — arremessos,
        # dash-ins e kiting mudam a distância de verdade e o quadro virava
        # sanfona (V7_zoom_calmo). Abrir continua imediato (segurança).
        tau = getattr(self, "diretor_zoom_tau", 2.0)
        suave = getattr(self, "_diretor_zoom_suave", None)
        if suave is None:
            suave = necessario
        suave += (necessario - suave) * min(1.0, dt / max(tau, 1e-6))
        self._diretor_zoom_suave = suave
        morto = bool(getattr(p1, "morto", False) or getattr(p2, "morto", False))
        push = self.diretor_push_ko if morto else 1.0
        desejado_abrir = min(teto, necessario * push)
        desejado = min(teto, min(necessario, suave) * push)
        # Onda 10A: momento (wall-splat/arremesso) fecha o quadro um pouco,
        # pelo mesmo caminho suave do push-in do KO.
        momento = getattr(self, "_momento_timer", 0.0)
        if momento > 0.0:
            self._momento_timer = momento - dt
            desejado = min(teto, desejado * getattr(self, "diretor_push_momento", 1.10))
            if self._area_da_luta() is not None:
                # com a área da luta, o push-in não fecha além do que cabe nela
                # (o empurrão do ESMAGAR cortava o caído na coluna de botões)
                desejado = min(desejado, necessario)
        if desejado_abrir < self.zoom * (1.0 - self.diretor_histerese_zoom_out):
            self._diretor_estavel_desde = None
            self.zoom += (desejado_abrir - self.zoom) * min(1.0, self.diretor_zoom_out * dt)
        elif desejado > self.zoom * (1.0 + self.diretor_histerese_zoom):
            if self._diretor_estavel_desde is None:
                self._diretor_estavel_desde = self._diretor_t
            estavel = self._diretor_t - self._diretor_estavel_desde
            if morto or estavel >= self.diretor_espera_zoom_in:
                self.zoom += (desejado - self.zoom) * min(1.0, self.diretor_zoom_in * dt)
        else:
            self._diretor_estavel_desde = None
        self.zoom = max(self.zoom_min, min(teto, self.zoom))

        # --- 2. pan com zona morta (histerese) ---
        # Começa a mover só quando o centro sai da zona; uma vez movendo, vai
        # até perto do centro (40% da zona) e para. Sem a histerese a câmera
        # estacionava exatamente na borda da zona e qualquer passo de 4 cm a
        # acordava — o "tremor de deriva" que a zona morta existe para matar.
        cx, cy = self._calcular_centro_ideal(p1, p2)
        desvio_x, desvio_y = self._desvio_do_centro_da_luta(self.zoom)   # 0 sem HUD
        cx -= desvio_x
        cy -= desvio_y
        cx, cy = self._limitar_centro_a_arena(cx, cy)
        dx_px = (cx - self.x) * self.zoom
        dy_px = (cy - self.y) * self.zoom
        dist = math.hypot(dx_px, dy_px)
        zona = self.diretor_deadzone * min(self.screen_width, self.screen_height)
        urgente = (not self._lutador_na_zona_segura(p1)
                   or not self._lutador_na_zona_segura(p2)
                   or self.lutador_fora_da_area(p1) or self.lutador_fora_da_area(p2))
        movendo = getattr(self, "_diretor_movendo", False)
        if dist > zona:
            movendo = True
        elif dist < zona * 0.4:
            movendo = False
        self._diretor_movendo = movendo
        if urgente:
            self.lerp_pos(cx, cy, dt, self.diretor_pan_urgente)
        elif movendo:
            self.lerp_pos(cx, cy, dt, self.diretor_pan)

        # --- 3. segurança: ninguém sai do quadro ---
        for lutador in (p1, p2):
            if self._lutador_visivel(lutador):
                continue
            if self.zoom > necessario:
                self.zoom = necessario
            sx, sy = self._get_posicao_tela(lutador)
            margem = self.margem_segura
            if sx < margem:
                self.x -= (margem - sx) / self.zoom
            elif sx > self.screen_width - margem:
                self.x += (sx - (self.screen_width - margem)) / self.zoom
            if sy < margem:
                self.y -= (margem - sy) / self.zoom
            elif sy > self.screen_height - margem:
                self.y += (sy - (self.screen_height - margem)) / self.zoom

        # --- 4. a área da luta (só com ``hud`` na reserva): ninguém sob o HUD
        # nem na coluna de botões, no quadro de agora ---
        self._manter_na_area(p1, p2, ja_andou=self._degrau_na_tela(
            self._camera_no_comeco_do_passo, (self.x, self.y, self.zoom)))

    # ------------------------------------------------------- pós-K.O.

    @staticmethod
    def _raio_desenhado(lutador) -> float:
        """Raio do corpo na tela, em px do mundo (o desenho usa tamanho/2)."""
        dados = getattr(lutador, "dados", None)
        tamanho = getattr(dados, "tamanho", None)
        if tamanho:
            return float(tamanho) / 2.0 * PPM
        return float(getattr(lutador, "raio_fisico", 0.5)) * 2.0 * PPM

    def _caixa_da_festa(self, vencedor, zoom: float) -> tuple:
        """Caixa (px do mundo) do vencedor comemorando: corpo no alto do pulo,
        nome sobre a cabeça e o confete inteiro (a mesma conta do desenho:
        anel fora do rosto + alcance com piso/teto pelo lado menor da tela)."""
        zoom = max(zoom, 1e-6)
        r = self._raio_desenhado(vencedor)
        x = vencedor.pos[0] * PPM
        y = vencedor.pos[1] * PPM - float(getattr(vencedor, "z", 0.0) or 0.0) * PPM
        menor = min(self.screen_width, self.screen_height)
        alcance_px = min(max(r * zoom * FESTA_ALCANCE_RAIOS, menor * FESTA_ALCANCE_TELA_MIN),
                         menor * FESTA_ALCANCE_TELA_MAX)
        voo = r * FESTA_BOCA_RAIOS + alcance_px / zoom
        nome = 40.0 / zoom                       # rótulo do nome: ~40 px na tela
        cima = max(0.75 * voo, (1.0 + FESTA_ALTURA_PULO) * r + nome)
        # o confete cai ``FESTA_QUEDA_RAIOS * tau^2`` (tau até 1,4 s)
        baixo = max(1.3 * r, FESTA_QUEDA_RAIOS * 1.96 * r)
        return x - voo, y - cima, x + voo, y + baixo

    def _caixa_do_caido(self, perdedor, zoom: float) -> tuple:
        r = self._raio_desenhado(perdedor)
        x = perdedor.pos[0] * PPM
        y = perdedor.pos[1] * PPM
        estrelas = 30.0 / max(zoom, 1e-6)
        return x - 1.3 * r, y - r - estrelas, x + 1.3 * r, y + r

    def _zoom_que_cabe(self, caixa_de_zoom) -> float:
        """Ponto fixo de ``zoom -> caixa(zoom) -> zoom que a enquadra``
        (o confete tem piso em px, então a caixa depende do zoom)."""
        margem = self.diretor_pos_ko_margem * min(self.screen_width, self.screen_height)
        ax0, ay0, ax1, ay1 = self._area_pos_ko()
        livre_w = max(1.0, (ax1 - ax0) * self.screen_width - 2 * margem)
        livre_h = max(1.0, (ay1 - ay0) * self.screen_height - 2 * margem)
        zoom = max(self.zoom, self.zoom_min)
        for _ in range(8):
            x0, y0, x1, y1 = caixa_de_zoom(zoom)
            zoom = min(livre_w / max(x1 - x0, 1e-6), livre_h / max(y1 - y0, 1e-6))
            zoom = max(self.zoom_min, min(self._diretor_teto_zoom(), zoom))
        return zoom

    def alvo_pos_ko(self, vencedor, perdedor) -> tuple:
        """(cx, cy, zoom, modo) do quadro pós-K.O. no DIRETOR.

        Os dois cabem com o vencedor ocupando pelo menos
        ``diretor_pos_ko_fracao_min`` da largura → enquadra os dois; senão,
        só o vencedor. Nos dois casos a caixa leva o pulo e o confete.
        """
        # A festa é cortada pela arena (15/10, conferente): o confete de quem
        # está encostado na parede não puxa o quadro para fora dela (na Torre
        # a cauda chegou a mostrar 47% da largura fora da arena).
        def festa(zoom):
            return self._cortar_na_arena(self._caixa_da_festa(vencedor, zoom))

        def caixa_par(zoom):
            a = festa(zoom)
            b = self._caixa_do_caido(perdedor, zoom)
            return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])

        zoom_par = self._zoom_que_cabe(caixa_par)
        fracao = 2.0 * self._raio_desenhado(vencedor) * zoom_par / self.screen_width
        if fracao >= self.diretor_pos_ko_fracao_min:
            caixa, zoom, modo = caixa_par(zoom_par), zoom_par, "dois"
        else:
            zoom = self._zoom_que_cabe(festa)
            caixa, modo = festa(zoom), "vencedor"
        # o centro da caixa vai ao centro da ÁREA (não da tela)
        ax0, ay0, ax1, ay1 = self._area_pos_ko()
        desvio_x = ((ax0 + ax1) / 2.0 - 0.5) * self.screen_width / zoom
        desvio_y = ((ay0 + ay1) / 2.0 - 0.5) * self.screen_height / zoom
        cx = (caixa[0] + caixa[2]) / 2.0 - desvio_x
        cy = (caixa[1] + caixa[3]) / 2.0 - desvio_y
        # o limite de arena do DIRETOR na luta (mais apertado: a festa não
        # mostra o lado de fora) ...
        cx, cy = self._limitar_centro_a_arena(cx, cy, zoom, self.diretor_pos_ko_fora_arena)
        # ... e, se ele cortar o vencedor, o rosto e o nome ganham: o resto da
        # festa (confete) pode sair do quadro, o vencedor não.
        cx, cy = self._garantir_rosto(vencedor, cx, cy, zoom)
        return cx, cy, zoom, modo

    def _cortar_na_arena(self, caixa) -> tuple:
        """A caixa (px do mundo) cortada pelos limites da arena."""
        if self.arena_centro is None or self.arena_tamanho is None:
            return caixa
        ax, ay = self.arena_centro[0] * PPM, self.arena_centro[1] * PPM
        mw, mh = self.arena_tamanho[0] * PPM / 2, self.arena_tamanho[1] * PPM / 2
        x0, y0 = max(caixa[0], ax - mw), max(caixa[1], ay - mh)
        x1, y1 = min(caixa[2], ax + mw), min(caixa[3], ay + mh)
        if x1 <= x0 or y1 <= y0:
            return caixa
        return x0, y0, x1, y1

    def caixa_do_rosto(self, vencedor, zoom: float, pulo: float | None = None) -> tuple:
        """Corpo do vencedor + o nome sobre a cabeça (px do mundo), com o pulo
        da festa em ``pulo`` raios (padrão: o MÁXIMO, ``FESTA_ALTURA_PULO``,
        que é o que o alvo do enquadramento reserva)."""
        r = self._raio_desenhado(vencedor)
        x = vencedor.pos[0] * PPM
        y = vencedor.pos[1] * PPM - float(getattr(vencedor, "z", 0.0) or 0.0) * PPM
        nome = 40.0 / max(zoom, 1e-6)
        pulo = FESTA_ALTURA_PULO if pulo is None else max(0.0, float(pulo))
        return (x - 1.15 * r, y - (1.0 + pulo) * r - nome,
                x + 1.15 * r, y + 1.1 * r)

    def _garantir_rosto(self, vencedor, cx, cy, zoom):
        """Empurra o centro o mínimo para o rosto/nome caberem na ÁREA."""
        margem = self.diretor_pos_ko_margem * min(self.screen_width, self.screen_height)
        ax0, ay0, ax1, ay1 = self._area_pos_ko()
        lim = (ax0 * self.screen_width + margem, ay0 * self.screen_height + margem,
               ax1 * self.screen_width - margem, ay1 * self.screen_height - margem)
        x0, y0, x1, y1 = self.caixa_do_rosto(vencedor, zoom)
        tela = lambda wx, c, meia: (wx - c) * zoom + meia  # noqa: E731
        sx0, sx1 = tela(x0, cx, self.screen_width / 2), tela(x1, cx, self.screen_width / 2)
        sy0, sy1 = tela(y0, cy, self.screen_height / 2), tela(y1, cy, self.screen_height / 2)
        if sx0 < lim[0]:
            cx -= (lim[0] - sx0) / zoom
        elif sx1 > lim[2]:
            cx += (sx1 - lim[2]) / zoom
        if sy0 < lim[1]:
            cy -= (lim[1] - sy0) / zoom
        elif sy1 > lim[3]:
            cy += (sy1 - lim[3]) / zoom
        return cx, cy

    def _topo_do_letreiro(self):
        """Borda de baixo do letreiro do K.O. (fração da altura) enquanto ele
        está na tela; None quando não há letreiro ou ele já saiu."""
        reserva = self.reserva_pos_ko
        t = self.t_pos_ko
        if not reserva or t is None:
            return None
        try:
            topo, ate = float(reserva["topo"]), float(reserva["ate_s"])
        except (KeyError, TypeError, ValueError):
            return None
        if t >= ate:
            return None
        return max(0.0, min(topo, self.diretor_pos_ko_area[3] - 0.1))

    def _fracao_do_hud(self) -> float:
        """Borda de baixo do HUD do vídeo (fração da altura) que quem grava
        passou em ``reserva_pos_ko["hud"]``; 0 sem HUD (jogo, palco, 16:9)."""
        reserva = self.reserva_pos_ko
        if not reserva:
            return 0.0
        try:
            hud = float(reserva.get("hud") or 0.0)
        except (AttributeError, TypeError, ValueError):
            return 0.0
        return max(0.0, min(hud, self.diretor_pos_ko_area[3] - 0.1))

    def _topo_base_pos_ko(self) -> float:
        """Topo da área pós-K.O. sem o letreiro: o de ``diretor_pos_ko_area``
        ou, se quem grava disse onde o HUD do vídeo termina (``hud`` da
        reserva), abaixo dele — o HUD fica na tela a cauda inteira."""
        return max(self.diretor_pos_ko_area[1], self._fracao_do_hud())

    # ------------------------------------------------ o HUD durante a luta
    # Decisão builds/camera-da-luta-sob-o-hud (18–19/10/2026): com o HUD do
    # celular abaixo das abas das plataformas (y 212–324 de 1920), ele cobria
    # o alto da arena e o lutador passava por baixo dele; e a coluna de botões
    # (12% da direita) cortava quem encostava nela. Com ``hud`` na reserva
    # (só o 9:16), o DIRETOR enquadra a luta na ÁREA da luta — abaixo do HUD,
    # à esquerda da coluna e dentro da tela — e garante, no quadro de AGORA
    # (o Simulador chama ``depois_do_passo`` depois de mover o mundo, antes
    # do desenho), que corpo + nome + ícone de cada lutador fiquem nela, com
    # teto de tranco por correção. Só lê posições.

    # px de tela (não escalam com o zoom) do que o Simulador desenha em volta
    # do corpo: o nome a ``raio + 22`` (corpo 13) e o ícone de status acima
    # dele; embaixo, o rótulo do plano e a barrinha
    LUTA_ACIMA_PX = 58.0
    LUTA_ABAIXO_PX = 30.0

    def _area_da_luta(self):
        """(x0, y0, x1, y1) em px: onde corpo + nome de cada lutador ficam
        na luta. None sem ``hud`` na reserva (16:9, jogo, palco)."""
        hud = self._fracao_do_hud()
        if hud <= 0.0:
            return None
        mc = float(self.margem_critica)
        return (mc, hud * self.screen_height + mc,
                self.diretor_pos_ko_area[2] * self.screen_width - mc,
                self.screen_height - mc)

    def caixa_do_lutador(self, lutador, zoom=None) -> tuple:
        """Corpo (com os anéis) + nome + ícone sobre a cabeça + plano sob o
        corpo, em px do mundo, no ``zoom`` dado (padrão: o atual)."""
        zoom = max(self.zoom if zoom is None else zoom, 1e-6)
        r = self._raio_desenhado(lutador)
        x = lutador.pos[0] * PPM
        y = lutador.pos[1] * PPM - float(getattr(lutador, "z", 0.0) or 0.0) * PPM
        return (x - 1.2 * r, y - r - self.LUTA_ACIMA_PX / zoom,
                x + 1.2 * r, y + r + self.LUTA_ABAIXO_PX / zoom)

    def _caixas_na_tela(self, lutadores, x, y, zoom) -> list:
        meia_w, meia_h = self.screen_width / 2, self.screen_height / 2
        saida = []
        for lut in lutadores:
            x0, y0, x1, y1 = self.caixa_do_lutador(lut, zoom)
            saida.append(((x0 - x) * zoom + meia_w, (y0 - y) * zoom + meia_h,
                          (x1 - x) * zoom + meia_w, (y1 - y) * zoom + meia_h))
        return saida

    def lutador_fora_da_area(self, lutador) -> bool:
        """O corpo + nome dele, no quadro de agora, sai da área da luta?"""
        area = self._area_da_luta()
        if area is None:
            return False
        x0, y0, x1, y1 = self._caixas_na_tela((lutador,), self.x, self.y, self.zoom)[0]
        return x0 < area[0] or y0 < area[1] or x1 > area[2] or y1 > area[3]

    def _margens_da_luta(self) -> tuple:
        """(esq, cima, dir, baixo) px do enquadramento: a ``margem_segura``
        de sempre ou, com a área da luta, a faixa do HUD + nome em cima e a
        coluna de botões à direita, com metade da margem de folga."""
        ms = float(self.margem_segura)
        area = self._area_da_luta()
        if area is None:
            return ms, ms, ms, ms
        folga = ms / 2.0
        return (ms, max(ms, area[1] + self.LUTA_ACIMA_PX + folga),
                max(ms, self.screen_width - area[2] + folga), ms)

    def _zoom_necessario_da_luta(self, p1, p2, zoom_max) -> float:
        """``_calcular_zoom_necessario`` com as margens da área da luta."""
        if self._area_da_luta() is None:
            return self._calcular_zoom_necessario(p1, p2, zoom_max=zoom_max)
        esq, cima, dir_, baixo = self._margens_da_luta()
        min_x, min_y, max_x, max_y = self._calcular_bounding_box(p1, p2)
        largura_tela = self.screen_width - esq - dir_
        altura_tela = self.screen_height - cima - baixo
        zoom_x = largura_tela / (max_x - min_x) if max_x > min_x else zoom_max
        zoom_y = altura_tela / (max_y - min_y) if max_y > min_y else zoom_max
        return max(self.zoom_min, min(zoom_max, zoom_x, zoom_y))

    def _desvio_do_centro_da_luta(self, zoom) -> tuple:
        """(dx, dy) px do mundo: quanto o centro da câmera anda para o meio
        da luta cair no meio da área ((0, 0) sem área)."""
        esq, cima, dir_, baixo = self._margens_da_luta()
        zoom = max(zoom, 1e-6)
        return ((esq - dir_) / 2.0 / zoom, (cima - baixo) / 2.0 / zoom)

    def _manter_na_area(self, p1, p2, ja_andou: float = 0.0) -> None:
        """No quadro de agora: se o corpo + nome de alguém sai da área da
        luta, a câmera anda o mínimo (e abre o zoom, se os dois não cabem),
        com teto de tranco: o que sobra do orçamento do passo
        (``diretor_area_degrau_max_px`` por quadro, medido em
        ``_degrau_na_tela``) ou, se a câmera já andou mais que isso neste
        passo (``ja_andou``: o arremesso que abre o quadro de emergência),
        o mesmo tanto que ela andou — nunca mais que o dobro do tranco que
        já existia."""
        area = self._area_da_luta()
        if area is None:
            return
        aw, ah = area[2] - area[0], area[3] - area[1]
        extras = self.LUTA_ACIMA_PX + self.LUTA_ABAIXO_PX
        antes = (self.x, self.y, self.zoom)
        x, y, zoom = antes
        for _ in range(6):
            caixas = self._caixas_na_tela((p1, p2), x, y, zoom)
            bx0 = min(c[0] for c in caixas)
            by0 = min(c[1] for c in caixas)
            bx1 = max(c[2] for c in caixas)
            by1 = max(c[3] for c in caixas)
            if bx1 - bx0 > aw or by1 - by0 > ah:
                # não cabem os dois: abre o zoom (em volta do centro da tela)
                zw = aw / max((bx1 - bx0) / zoom, 1e-6)
                zh = (ah - extras) / max((by1 - by0 - extras) / zoom, 1e-6)
                novo_zoom = max(self.zoom_min, min(zoom, zw, zh) * 0.995)
                if novo_zoom >= zoom - 1e-9:
                    break
                zoom = novo_zoom
                continue
            if bx0 < area[0]:
                x += (bx0 - area[0]) / zoom
            elif bx1 > area[2]:
                x += (bx1 - area[2]) / zoom
            if by0 < area[1]:
                y += (by0 - area[1]) / zoom
            elif by1 > area[3]:
                y += (by1 - area[3]) / zoom
            break
        novo = (x, y, zoom)
        if novo == antes:
            return
        teto = max(self._orcamento_area, float(ja_andou or 0.0))
        degrau = self._degrau_na_tela(antes, novo)
        fracao = 1.0 if degrau <= teto else max(0.0, teto) / degrau
        self._orcamento_area = max(0.0, self._orcamento_area - degrau * fracao)
        self.x = antes[0] + (x - antes[0]) * fracao
        self.y = antes[1] + (y - antes[1]) * fracao
        self.zoom = antes[2] + (zoom - antes[2]) * fracao

    def depois_do_passo(self, p1, p2) -> None:
        """O Simulador chama depois de mover o mundo, antes do desenho: a
        câmera foi atualizada no começo do passo, e um arremesso anda até
        ~100 px por passo — sem isto o quadro desenhado mostrava o lutador sob
        o HUD (Vulcão, seed 4242, ~11,5 s; conferente 19/10). Só no DIRETOR
        da luta e só com a área da luta (``hud`` na reserva)."""
        if self.modo != "DIRETOR" or p1 is None or p2 is None:
            return
        if getattr(p1, "morto", False) or getattr(p2, "morto", False):
            return
        comeco = getattr(self, "_camera_no_comeco_do_passo", None)
        ja_andou = 0.0 if comeco is None else self._degrau_na_tela(
            comeco, (self.x, self.y, self.zoom))
        self._manter_na_area(p1, p2, ja_andou=ja_andou)

    def _area_pos_ko(self) -> tuple:
        """``diretor_pos_ko_area`` com o topo abaixo do HUD do vídeo e,
        enquanto ele está na tela, do letreiro do K.O. (voltando suave depois,
        ``_pos_ko_topo``)."""
        x0, _y0, x1, y1 = self.diretor_pos_ko_area
        y0 = self._topo_base_pos_ko()
        topo = self._pos_ko_topo
        letreiro = self._topo_do_letreiro()
        if letreiro is not None:
            topo = letreiro if topo is None else max(topo, letreiro)
        return x0, y0 if topo is None else max(y0, topo), x1, y1

    def _enquadrar_pos_ko(self, dt, vencedor, perdedor):
        """Vai suave (exponencial, nunca salta) ao quadro de ``alvo_pos_ko``.

        Só lê posições; depois do K.O. a luta acabou e nada a muda."""
        passo = 1.0 - math.exp(-self.diretor_pos_ko_lerp * dt)
        # o topo reservado ao letreiro: segura enquanto ele está na tela e,
        # quando ele sai, desce de volta suave (a área cresce sem salto)
        letreiro = self._topo_do_letreiro()
        if letreiro is not None:
            self._pos_ko_topo = letreiro
        elif self._pos_ko_topo is not None:
            base = self._topo_base_pos_ko()
            self._pos_ko_topo += (base - self._pos_ko_topo) * passo
            if self._pos_ko_topo - base < 1e-3:
                self._pos_ko_topo = None
        cx, cy, zoom, modo = self.alvo_pos_ko(vencedor, perdedor)
        self._pos_ko_modo = modo
        antes = (self.x, self.y, self.zoom)
        novo_zoom = max(self.zoom_min, min(self._diretor_teto_zoom(),
                                           self.zoom + (zoom - self.zoom) * passo))
        novo = (self.x + (cx - self.x) * passo, self.y + (cy - self.y) * passo, novo_zoom)
        if letreiro is not None:
            # a garantia do letreiro entra NO passo (e não depois dele): o
            # teto de degrau abaixo vale para o movimento inteiro
            self.x, self.y, self.zoom = novo
            self._tirar_rosto_do_letreiro(vencedor, letreiro)
            novo = (self.x, self.y, self.zoom)
            self.x, self.y, self.zoom = antes
        # Teto de degrau (15/10, conferente: nenhum degrau > 12 px por quadro
        # de 30 fps): se a imagem andaria mais que isto neste passo, o passo
        # inteiro (centro e zoom) encolhe na mesma proporção.
        # Só no 1º segundo (o slow-mo, com o letreiro na tela): depois a festa
        # precisa chegar ao quadro dela antes de o vídeo acabar.
        fracao = 1.0
        t = self.t_pos_ko
        if t is not None and t <= self.diretor_pos_ko_degrau_ate_s:
            degrau = self._degrau_na_tela(antes, novo)
            teto = self.diretor_pos_ko_degrau_max_px
            if degrau > teto > 0:
                fracao = teto / degrau
        self.x = antes[0] + (novo[0] - antes[0]) * fracao
        self.y = antes[1] + (novo[1] - antes[1]) * fracao
        self.zoom = antes[2] + (novo[2] - antes[2]) * fracao
        if letreiro is not None:
            self._tirar_rosto_do_letreiro(vencedor, letreiro)

    def _degrau_na_tela(self, antes, depois) -> float:
        """Quanto (px) a imagem anda na tela de ``antes`` para ``depois``
        (x, y, zoom): o maior deslocamento de 9 pontos (10/50/90% da largura
        × 30/45/60% da altura), onde estão o vencedor e o fundo atrás dele —
        o centro mede o deslocamento, as bordas pegam o zoom."""
        w, h = self.screen_width, self.screen_height
        x0, y0, z0 = antes
        x1, y1, z1 = depois
        maior = 0.0
        for fy in (0.30, 0.45, 0.60):
            for fx in (0.1, 0.5, 0.9):
                sx, sy = fx * w, fy * h
                wx, wy = (sx - w / 2) / z0 + x0, (sy - h / 2) / z0 + y0
                nx, ny = (wx - x1) * z1 + w / 2, (wy - y1) * z1 + h / 2
                maior = max(maior, math.hypot(nx - sx, ny - sy))
        return maior

    def _tirar_rosto_do_letreiro(self, vencedor, letreiro):
        """No quadro DE AGORA (não só no alvo): se o rosto/nome do vencedor
        sobe até o letreiro, a câmera sobe o necessário. Depois do 1º quadro
        pós-K.O. isso é sempre um ajuste pequeno (o alvo já está abaixo do
        letreiro); só no 1º, se a luta acabou com o vencedor no alto da
        tela, ele sai de trás do letreiro de uma vez — junto com o K.O."""
        margem = self.diretor_pos_ko_margem * min(self.screen_width, self.screen_height)
        limite = letreiro * self.screen_height + margem / 2.0
        # o pulo de AGORA (no K.O. ele nem começou): com o máximo, a caixa
        # ficava ~50 px alta demais e empurrava a câmera 34 px num quadro
        # sem o vencedor estar atrás do letreiro (Vulcão, 15/10)
        _x0, y0, _x1, _y1 = self.caixa_do_rosto(vencedor, self.zoom, self.pulo_pos_ko)
        topo_tela = (y0 - self.y) * self.zoom + self.screen_height / 2
        if topo_tela < limite:
            self.y -= (limite - topo_tela) / self.zoom

    def _aplicar_punch(self, dt):
        # Transiente de <=0,15s; decai linearmente e não realimenta o lerp
        # de forma permanente.
        if getattr(self, "_punch_timer", 0.0) > 0.0:
            self._punch_timer -= dt
            frac = max(0.0, self._punch_timer / max(self._punch_dur, 1e-6))
            self.zoom += self._punch_mag * frac
            if self._punch_timer <= 0.0:
                self._punch_mag = 0.0

    def zoom_punch(self, intensidade=0.1, duracao=0.1):
        """Efeito de zoom punch para impactos.

        Passe 4 (arte): somar no target_zoom era invisível — a
        "VERIFICAÇÃO FINAL DE SEGURANÇA" do frame seguinte clampava o
        target de volta antes do zoom suave (3*dt) sair do lugar. O punch
        agora é um bump DECADENTE aplicado depois dos clamps do update.
        """
        self._punch_mag = max(getattr(self, "_punch_mag", 0.0), intensidade)
        self._punch_timer = max(duracao, 0.01)
        self._punch_dur = self._punch_timer
    
    def lerp_pos(self, tx, ty, dt, velocidade=5.0):
        """Interpola suavemente a posição da câmera"""
        self.x += (tx - self.x) * velocidade * dt
        self.y += (ty - self.y) * velocidade * dt
    
