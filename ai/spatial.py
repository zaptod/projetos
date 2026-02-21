"""
NEURAL FIGHTS - Sistema de Consciência Espacial v10.0 ENHANCED
Sistema de reconhecimento de paredes, obstáculos e posicionamento tático.

MELHORIAS v10.0:
- Checagem de obstáculos mais frequente e precisa
- Pathfinding simplificado para rotas alternativas
- Predição de colisão em movimento
- Awareness de obstáculos durante ataques
- Sistema de "zonas seguras" e "zonas perigosas"
"""

import math
import random


class SpatialAwarenessSystem:
    """
    Sistema de consciência espacial AVANÇADO para IA.
    Gerencia awareness de paredes, obstáculos e posicionamento tático.
    """
    
    def __init__(self, parent):
        self.parent = parent
        
        # Estado de consciência espacial
        self.consciencia = {
            "parede_proxima": None,  # None, "norte", "sul", "leste", "oeste"
            "distancia_parede": 999.0,
            "obstaculo_proximo": None,  # Obstáculo mais próximo
            "distancia_obstaculo": 999.0,
            "obstaculos_proximos": [],  # Lista de obstáculos num raio
            "encurralado": False,
            "oponente_contra_parede": False,
            "oponente_perto_obstaculo": False,
            "caminho_livre": {"frente": True, "tras": True, "esquerda": True, "direita": True},
            "posicao_tatica": "centro",  # "centro", "perto_parede", "encurralado", "vantagem", "cobertura"
            "zona_segura": True,  # Se está em posição segura
            "distancia_centro": 0.0,  # Distância ao centro da arena
        }
        
        # Táticas espaciais
        self.tatica = {
            "usando_cobertura": False,
            "tipo_cobertura": None,  # "pilar", "obstaculo", "parede"
            "forcar_canto": False,  # Tentando encurralar oponente
            "recuar_para_obstaculo": False,  # Recuando de costas pra obstáculo (perigoso)
            "flanquear_obstaculo": False,  # Usando obstáculo pra flanquear
            "rota_alternativa": None,  # Direção alternativa se caminho bloqueado
            "obstaculo_entre_nos": False,  # Há obstáculo entre eu e oponente
            "last_check_time": 0.0,  # Otimização - não checa todo frame
        }
        
        # Cache para otimização
        self._arena_cache = None
        self._last_pos = None
    
    def atualizar(self, dt, distancia, inimigo):
        """
        Atualiza awareness de paredes, obstáculos e posicionamento tático.
        VERSÃO MELHORADA - checagem mais frequente e precisa.
        """
        # Otimização: checa mais frequentemente se movendo rápido ou perto de obstáculo
        self.tatica["last_check_time"] += dt
        
        check_interval = 0.15  # Mais frequente que antes (era 0.2)
        if self.consciencia["distancia_obstaculo"] < 3.0:
            check_interval = 0.08  # Muito mais frequente perto de obstáculos
        
        if self.tatica["last_check_time"] < check_interval:
            return
        self.tatica["last_check_time"] = 0.0
        
        p = self.parent
        esp = self.consciencia
        
        # Importa arena (com cache)
        try:
            from core.arena import get_arena
            self._arena_cache = get_arena()
        except:
            return
        
        arena = self._arena_cache
        
        # === DETECÇÃO DE PAREDES ===
        self._detectar_paredes(p, arena, esp)
        
        # === DETECÇÃO DE OBSTÁCULOS MELHORADA ===
        self._detectar_obstaculos_avancado(p, arena, esp)
        
        # === ANÁLISE DE CAMINHOS LIVRES ===
        self._analisar_caminhos(p, arena, esp, inimigo)
        
        # === VERIFICA OBSTÁCULO ENTRE COMBATENTES ===
        self._verificar_obstaculo_entre(p, arena, esp, inimigo)
        
        # === VERIFICA ENCURRALAMENTO ===
        self._verificar_encurralamento(esp)
        
        # === VERIFICA OPONENTE CONTRA PAREDE/OBSTÁCULO ===
        self._verificar_oponente_posicao(arena, inimigo, esp)
        
        # === CALCULA ROTA ALTERNATIVA ===
        self._calcular_rota_alternativa(p, arena, esp, inimigo)
        
        # === DEFINE POSIÇÃO TÁTICA ===
        self._definir_posicao_tatica(esp, distancia, p, arena)
    
    def _detectar_paredes(self, p, arena, esp):
        """Detecta paredes próximas - suporta arenas circulares"""
        if arena.config.formato == "circular":
            # Para arenas circulares, calcula distância à borda
            dx = p.pos[0] - arena.centro_x
            dy = p.pos[1] - arena.centro_y
            dist_centro = math.hypot(dx, dy)
            dist_borda = arena.raio - dist_centro
            
            esp["distancia_parede"] = max(0.1, dist_borda)
            esp["distancia_centro"] = dist_centro
            
            # Determina direção da parede mais próxima
            if dist_centro > 0.1:
                ang = math.degrees(math.atan2(dy, dx))
                if -45 <= ang < 45:
                    esp["parede_proxima"] = "leste"
                elif 45 <= ang < 135:
                    esp["parede_proxima"] = "sul"
                elif -135 <= ang < -45:
                    esp["parede_proxima"] = "norte"
                else:
                    esp["parede_proxima"] = "oeste"
            else:
                esp["parede_proxima"] = None
        else:
            # Arenas retangulares
            dist_norte = p.pos[1] - arena.min_y
            dist_sul = arena.max_y - p.pos[1]
            dist_oeste = p.pos[0] - arena.min_x
            dist_leste = arena.max_x - p.pos[0]
            
            paredes = [
                ("norte", dist_norte),
                ("sul", dist_sul),
                ("oeste", dist_oeste),
                ("leste", dist_leste),
            ]
            parede_mais_proxima = min(paredes, key=lambda x: x[1])
            
            esp["parede_proxima"] = parede_mais_proxima[0]
            esp["distancia_parede"] = parede_mais_proxima[1]
            esp["distancia_centro"] = math.hypot(
                p.pos[0] - arena.centro_x,
                p.pos[1] - arena.centro_y
            )
    
    def _detectar_obstaculos_avancado(self, p, arena, esp):
        """Detecta obstáculos próximos - VERSÃO MELHORADA"""
        obs_mais_proximo = None
        dist_obs_min = 999.0
        obstaculos_proximos = []
        
        raio_deteccao = 5.0  # Detecta obstáculos num raio de 5m
        
        if hasattr(arena, 'obstaculos'):
            for obs in arena.obstaculos:
                if not obs.solido:
                    continue
                
                # Calcula distância real considerando tamanho do obstáculo
                dx = p.pos[0] - obs.x
                dy = p.pos[1] - obs.y
                dist_centro = math.hypot(dx, dy)
                
                # Subtrai o "raio" do obstáculo (aproximado)
                raio_obs = (obs.largura + obs.altura) / 4
                dist = dist_centro - raio_obs - p.raio_fisico
                
                if dist < raio_deteccao:
                    obstaculos_proximos.append({
                        "obs": obs,
                        "dist": dist,
                        "angulo": math.degrees(math.atan2(dy, dx)),
                        "raio": raio_obs
                    })
                
                if dist < dist_obs_min:
                    dist_obs_min = dist
                    obs_mais_proximo = obs
        
        esp["obstaculo_proximo"] = obs_mais_proximo
        esp["distancia_obstaculo"] = max(0, dist_obs_min)
        esp["obstaculos_proximos"] = obstaculos_proximos
    
    def _analisar_caminhos(self, p, arena, esp, inimigo):
        """Verifica se há obstáculos bloqueando cada direção - VERSÃO MELHORADA"""
        check_dists = [1.5, 2.5]  # Checa múltiplas distâncias
        
        # Calcula ângulo para o inimigo
        ang_inimigo = math.atan2(inimigo.pos[1] - p.pos[1], inimigo.pos[0] - p.pos[0])
        
        direcoes = {
            "frente": ang_inimigo,
            "tras": ang_inimigo + math.pi,
            "esquerda": ang_inimigo + math.pi / 2,
            "direita": ang_inimigo - math.pi / 2,
        }
        
        for direcao, ang in direcoes.items():
            livre = True
            for check_dist in check_dists:
                check_x = p.pos[0] + math.cos(ang) * check_dist
                check_y = p.pos[1] + math.sin(ang) * check_dist
                
                # Verifica colisão com obstáculos
                if arena.colide_obstaculo(check_x, check_y, p.raio_fisico):
                    livre = False
                    break
                
                # Verifica limites da arena
                if not arena.ponto_dentro(check_x, check_y):
                    livre = False
                    break
            
            esp["caminho_livre"][direcao] = livre
    
    def _verificar_obstaculo_entre(self, p, arena, esp, inimigo):
        """Verifica se há obstáculo entre o lutador e o oponente"""
        esp_tatica = self.tatica
        esp_tatica["obstaculo_entre_nos"] = False
        
        if not hasattr(arena, 'obstaculos'):
            return
        
        # Linha entre eu e o oponente
        dx = inimigo.pos[0] - p.pos[0]
        dy = inimigo.pos[1] - p.pos[1]
        dist = math.hypot(dx, dy)
        
        if dist < 0.1:
            return
        
        # Normaliza
        nx, ny = dx / dist, dy / dist
        
        # Checa pontos ao longo da linha
        for t in range(1, int(dist)):
            check_x = p.pos[0] + nx * t
            check_y = p.pos[1] + ny * t
            
            if arena.colide_obstaculo(check_x, check_y, 0.3):
                esp_tatica["obstaculo_entre_nos"] = True
                return
    
    def _verificar_encurralamento(self, esp):
        """Verifica se está encurralado - VERSÃO MELHORADA"""
        caminhos_bloqueados = sum(
            1 for livre in esp["caminho_livre"].values() if not livre
        )
        
        # Encurralado se:
        # - Parede muito próxima (< 2.0m) E 2+ caminhos bloqueados
        # - OU 3+ caminhos bloqueados
        # - OU perto de obstáculo E não pode recuar
        esp["encurralado"] = (
            (esp["distancia_parede"] < 2.0 and caminhos_bloqueados >= 2) or
            caminhos_bloqueados >= 3 or
            (esp["distancia_obstaculo"] < 1.5 and not esp["caminho_livre"]["tras"])
        )
        
        # Zona segura = longe de paredes E longe de obstáculos
        esp["zona_segura"] = (
            esp["distancia_parede"] > 3.0 and
            esp["distancia_obstaculo"] > 2.0 and
            caminhos_bloqueados < 2
        )
    
    def _verificar_oponente_posicao(self, arena, inimigo, esp):
        """Verifica posição do oponente em relação a paredes/obstáculos"""
        # Distância do oponente à parede
        if arena.config.formato == "circular":
            dx = inimigo.pos[0] - arena.centro_x
            dy = inimigo.pos[1] - arena.centro_y
            dist_borda = arena.raio - math.hypot(dx, dy)
            esp["oponente_contra_parede"] = dist_borda < 2.0
        else:
            dist_ini_parede = min(
                inimigo.pos[1] - arena.min_y,
                arena.max_y - inimigo.pos[1],
                inimigo.pos[0] - arena.min_x,
                arena.max_x - inimigo.pos[0]
            )
            esp["oponente_contra_parede"] = dist_ini_parede < 2.0
        
        # Oponente perto de obstáculo
        esp["oponente_perto_obstaculo"] = False
        if hasattr(arena, 'obstaculos'):
            for obs in arena.obstaculos:
                if not obs.solido:
                    continue
                dx = inimigo.pos[0] - obs.x
                dy = inimigo.pos[1] - obs.y
                dist = math.hypot(dx, dy) - (obs.largura + obs.altura) / 4
                if dist < 2.0:
                    esp["oponente_perto_obstaculo"] = True
                    break
    
    def _calcular_rota_alternativa(self, p, arena, esp, inimigo):
        """Calcula uma rota alternativa se o caminho direto está bloqueado"""
        tatica = self.tatica
        tatica["rota_alternativa"] = None
        
        # Se caminho da frente está livre, não precisa de alternativa
        if esp["caminho_livre"]["frente"]:
            return
        
        # Procura melhor direção alternativa
        prioridade = ["esquerda", "direita", "tras"]
        random.shuffle(prioridade[:2])  # Randomiza esq/dir
        
        for direcao in prioridade:
            if esp["caminho_livre"][direcao]:
                tatica["rota_alternativa"] = direcao
                return
    
    def _definir_posicao_tatica(self, esp, distancia, p, arena):
        """Define a posição tática atual - VERSÃO MELHORADA"""
        if esp["encurralado"]:
            esp["posicao_tatica"] = "encurralado"
        elif self.tatica["usando_cobertura"]:
            esp["posicao_tatica"] = "cobertura"
        elif esp["oponente_contra_parede"] and distancia < 4.0:
            esp["posicao_tatica"] = "vantagem"
        elif esp["distancia_parede"] < 2.5:
            esp["posicao_tatica"] = "perto_parede"
        elif esp["distancia_obstaculo"] < 2.0:
            esp["posicao_tatica"] = "perto_obstaculo"
        else:
            esp["posicao_tatica"] = "centro"
    
    def avaliar_taticas(self, distancia, inimigo, tracos):
        """
        Avalia e retorna modificadores táticos baseados na posição espacial.
        VERSÃO MELHORADA com mais nuances.
        """
        esp = self.consciencia
        tatica = self.tatica
        
        modificadores = {
            "evitar_recuo": False,
            "forcar_lateral": False,
            "pressao_extra": 0.0,
            "direcao_preferida": None,
            "urgencia_reposicionamento": 0.0,
            "usar_projeteis": False,  # NOVO: sugere usar projéteis
            "flanquear": False,  # NOVO: sugere flanquear
            "recuar_seguro": True,  # NOVO: se é seguro recuar
        }
        
        # === COMPORTAMENTOS QUANDO ENCURRALADO ===
        if esp["encurralado"]:
            modificadores["urgencia_reposicionamento"] = 0.8
            modificadores["evitar_recuo"] = True
            modificadores["recuar_seguro"] = False
            
            # Determina melhor direção de fuga
            for direcao in ["esquerda", "direita", "frente"]:
                if esp["caminho_livre"].get(direcao, False):
                    modificadores["direcao_preferida"] = direcao
                    break
        
        # === APROVEITAR OPONENTE CONTRA PAREDE/OBSTÁCULO ===
        if esp["oponente_contra_parede"] or esp["oponente_perto_obstaculo"]:
            modificadores["pressao_extra"] = 0.25
            tatica["forcar_canto"] = True
            
            if "PREDADOR" in tracos or "SANGUINARIO" in tracos:
                modificadores["pressao_extra"] = 0.4
            if "OPORTUNISTA" in tracos:
                modificadores["pressao_extra"] = 0.35
        
        # === OBSTÁCULO ENTRE NÓS ===
        if tatica["obstaculo_entre_nos"]:
            modificadores["flanquear"] = True
            modificadores["usar_projeteis"] = True  # Projéteis são bons aqui
        
        # === EVITAR RECUAR PARA OBSTÁCULOS ===
        if not esp["caminho_livre"]["tras"]:
            modificadores["evitar_recuo"] = True
            modificadores["forcar_lateral"] = True
            modificadores["recuar_seguro"] = False
        
        # === USA ROTA ALTERNATIVA ===
        if tatica["rota_alternativa"]:
            modificadores["direcao_preferida"] = tatica["rota_alternativa"]
        
        # === ZONA SEGURA ===
        if esp["zona_segura"]:
            modificadores["recuar_seguro"] = True
        
        # === USO DE COBERTURA ===
        if esp["distancia_obstaculo"] < 3.0 and esp["obstaculo_proximo"]:
            obs = esp["obstaculo_proximo"]
            if hasattr(obs, 'bloqueiaProjeteis') and obs.bloqueiaProjeteis:
                tatica["usando_cobertura"] = True
                tatica["tipo_cobertura"] = getattr(obs, 'tipo', 'obstaculo')
        
        return modificadores
    
    def ajustar_direcao(self, direcao_alvo, tracos):
        """
        Ajusta uma direção de movimento para evitar colisões.
        VERSÃO MELHORADA com predição.
        """
        esp = self.consciencia
        p = self.parent
        
        if not self._arena_cache:
            return direcao_alvo
        
        arena = self._arena_cache
        
        # Calcula posição alvo
        check_dist = 1.5
        rad = math.radians(direcao_alvo)
        check_x = p.pos[0] + math.cos(rad) * check_dist
        check_y = p.pos[1] + math.sin(rad) * check_dist
        
        # Se caminho livre, mantém direção
        if not arena.colide_obstaculo(check_x, check_y, p.raio_fisico):
            if arena.ponto_dentro(check_x, check_y):
                return direcao_alvo
        
        # Procura alternativa com preferência por ângulos menores
        ajustes = [20, -20, 40, -40, 60, -60, 90, -90, 120, -120, 150, -150]
        
        for ajuste in ajustes:
            nova_dir = direcao_alvo + ajuste
            rad = math.radians(nova_dir)
            check_x = p.pos[0] + math.cos(rad) * check_dist
            check_y = p.pos[1] + math.sin(rad) * check_dist
            
            if not arena.colide_obstaculo(check_x, check_y, p.raio_fisico):
                if arena.ponto_dentro(check_x, check_y):
                    return nova_dir
        
        # Se nada funcionar, mantém original
        return direcao_alvo
    
    def prever_colisao(self, velocidade_x, velocidade_y, tempo=0.5):
        """
        Prevê se haverá colisão nos próximos frames.
        NOVO em v10.0
        """
        if not self._arena_cache:
            return False, None
        
        p = self.parent
        arena = self._arena_cache
        
        # Simula posição futura
        pos_futura_x = p.pos[0] + velocidade_x * tempo
        pos_futura_y = p.pos[1] + velocidade_y * tempo
        
        # Verifica colisão
        if arena.colide_obstaculo(pos_futura_x, pos_futura_y, p.raio_fisico):
            return True, "obstaculo"
        
        if not arena.ponto_dentro(pos_futura_x, pos_futura_y):
            return True, "parede"
        
        return False, None
    
    def get_melhor_posicao_ataque(self, inimigo, alcance):
        """
        Calcula a melhor posição para atacar considerando obstáculos.
        NOVO em v10.0
        """
        if not self._arena_cache:
            return None
        
        p = self.parent
        arena = self._arena_cache
        
        # Calcula ângulo para o inimigo
        ang_base = math.atan2(inimigo.pos[1] - p.pos[1], inimigo.pos[0] - p.pos[0])
        
        # Testa posições ao redor do inimigo
        melhores = []
        for offset_ang in range(-90, 91, 30):
            ang = ang_base + math.radians(offset_ang)
            
            # Posição a 'alcance' metros do inimigo
            pos_x = inimigo.pos[0] - math.cos(ang) * alcance
            pos_y = inimigo.pos[1] - math.sin(ang) * alcance
            
            # Verifica se posição é válida
            if not arena.colide_obstaculo(pos_x, pos_y, p.raio_fisico):
                if arena.ponto_dentro(pos_x, pos_y):
                    # Calcula distância até essa posição
                    dist = math.hypot(pos_x - p.pos[0], pos_y - p.pos[1])
                    melhores.append((pos_x, pos_y, dist, offset_ang))
        
        if not melhores:
            return None
        
        # Retorna posição mais próxima
        melhores.sort(key=lambda x: x[2])
        return melhores[0][:2]
    
    def get_estado(self):
        """Retorna o estado atual da consciência espacial"""
        return {
            "consciencia": self.consciencia.copy(),
            "tatica": self.tatica.copy(),
        }
