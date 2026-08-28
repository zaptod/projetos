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
        self.zoom = min(zoom_x, zoom_y, 1.0)
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

    def _limitar_centro_a_arena(self, cx, cy):
        """Clamp MACIO à arena: os lutadores ficam no centro, não a arena.

        A arena é o palco, mas quem manda no quadro é a luta. A janela pode
        avançar além da borda da arena até `diretor_fora_arena` da própria
        dimensão (35%): dois lutadores encostados na parede de cima aparecem
        a ~1/3 do topo, não colados nele. Só quando nem isso basta (janela
        muito maior que a arena naquele eixo) o eixo centraliza na arena.
        """
        if self.arena_centro is None or self.arena_tamanho is None or self.zoom <= 0:
            return cx, cy
        meia_w = (self.screen_width / 2) / self.zoom
        meia_h = (self.screen_height / 2) / self.zoom
        fora_w = self.diretor_fora_arena * 2 * meia_w
        fora_h = self.diretor_fora_arena * 2 * meia_h
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

        # --- 1. zoom ---
        teto = self._diretor_teto_zoom()
        necessario = self._calcular_zoom_necessario(p1, p2, zoom_max=teto)
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
        cx, cy = self._limitar_centro_a_arena(cx, cy)
        dx_px = (cx - self.x) * self.zoom
        dy_px = (cy - self.y) * self.zoom
        dist = math.hypot(dx_px, dy_px)
        zona = self.diretor_deadzone * min(self.screen_width, self.screen_height)
        urgente = (not self._lutador_na_zona_segura(p1)
                   or not self._lutador_na_zona_segura(p2))
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
