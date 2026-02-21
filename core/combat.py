# combat.py
import math
import random
from utils.config import *
from core.skills import get_skill_data


class ArmaProjetil:
    """Projétil de arma física (facas, flechas, etc) - diferente de skills"""
    def __init__(self, tipo, x, y, angulo, dono, dano, velocidade=15.0, tamanho=0.3, cor=(200, 200, 200)):
        self.tipo = tipo  # "faca", "flecha", "chakram", "shuriken"
        self.nome = tipo.capitalize()  # Nome para compatibilidade com debug
        self.x = x
        self.y = y
        self.angulo = angulo
        self.angulo_visual = angulo  # Para rotação visual
        self.dono = dono
        
        self.dano = dano
        self.vel = velocidade
        self.raio = tamanho  # Raio de colisão em metros
        self.cor = cor
        
        self.vida = 3.0  # Segundos até desaparecer
        self.ativo = True
        self.trail = []
        
        # Rotação visual (shurikens giram rápido)
        self.rotacao_vel = 0
        if tipo in ["shuriken", "chakram"]:
            self.rotacao_vel = 720  # graus/segundo
        elif tipo == "faca":
            self.rotacao_vel = 360
    
    def atualizar(self, dt):
        # Movimento
        rad = math.radians(self.angulo)
        self.x += math.cos(rad) * self.vel * dt
        self.y += math.sin(rad) * self.vel * dt
        
        # Rotação visual
        self.angulo_visual += self.rotacao_vel * dt
        
        # Trail
        self.trail.append((self.x, self.y))
        if len(self.trail) > 8:
            self.trail.pop(0)
        
        # Vida
        self.vida -= dt
        if self.vida <= 0:
            self.ativo = False
    
    def colidir(self, alvo):
        """Verifica colisão com um lutador"""
        if alvo == self.dono:
            return False
        if alvo.morto:
            return False
        
        dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
        # Usa raio_fisico se disponível, senão calcula do tamanho
        raio_alvo = getattr(alvo, 'raio_fisico', alvo.dados.tamanho / 4.0)
        
        # Colisão generosa para projéteis
        return dist < (self.raio + raio_alvo * 1.2)


class FlechaProjetil(ArmaProjetil):
    """Flecha rápida e precisa - voa em linha reta"""
    def __init__(self, x, y, angulo, dono, dano, forca=1.0, cor=(139, 90, 43)):
        # Flecha MUITO rápida: 35-55 m/s dependendo da força do arco
        super().__init__("flecha", x, y, angulo, dono, dano, 
                        velocidade=35.0 + forca * 20.0,  # MUITO mais rápido!
                        tamanho=0.6, cor=cor)  # Raio maior para colisão generosa
        self.forca = forca
        self.gravidade = 0.0  # SEM gravidade - voa em linha reta!
        self.vel_y_extra = 0
        self.vida = 5.0  # Vive 5 segundos (alcança ~200m)
        self.perfurante = forca > 0.5  # Flechas médias+ perfuram
    
    def atualizar(self, dt):
        # Movimento em LINHA RETA - flecha voa direto no alvo
        rad = math.radians(self.angulo)
        self.x += math.cos(rad) * self.vel * dt
        self.y += math.sin(rad) * self.vel * dt
        
        # Ângulo visual = ângulo de voo (linha reta)
        self.angulo_visual = self.angulo
        
        # Trail
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        
        self.vida -= dt
        if self.vida <= 0:
            self.ativo = False


class OrbeMagico:
    """Orbe mágico que flutua ao redor do mago e depois dispara no inimigo"""
    def __init__(self, x, y, dono, dano, indice=0, total=1, cor=(100, 100, 255)):
        self.x = x
        self.y = y
        self.dono = dono
        self.dano = dano
        self.cor = cor
        self.raio = 0.25  # Raio de colisão
        self.raio_visual = 0.15  # Tamanho visual inicial
        
        # Índice para posicionamento orbital
        self.indice = indice
        self.total = total
        
        # Estados: "orbitando", "carregando", "disparando"
        self.estado = "orbitando"
        
        # Órbita
        self.angulo_orbital = (360.0 / total) * indice
        self.vel_orbital = 180.0  # graus/segundo
        self.dist_orbital = 0.8  # distância do dono
        
        # Carregamento
        self.tempo_carga = 0.0
        self.carga_max = 0.6  # tempo para carregar
        
        # Disparo
        self.angulo_disparo = 0
        self.vel_disparo = 0
        self.vel_max = 18.0
        self.alvo = None
        
        # Visual
        self.pulso = 0.0
        self.particulas = []
        self.trail = []
        
        self.vida = 8.0  # Tempo máximo de existência
        self.ativo = True
    
    def iniciar_carga(self, alvo):
        """Começa a carregar para disparar"""
        if self.estado == "orbitando":
            self.estado = "carregando"
            self.tempo_carga = 0.0
            self.alvo = alvo
    
    def atualizar(self, dt):
        self.vida -= dt
        self.pulso += dt * 5.0
        
        if self.vida <= 0:
            self.ativo = False
            return
        
        if self.estado == "orbitando":
            self._atualizar_orbita(dt)
        elif self.estado == "carregando":
            self._atualizar_carga(dt)
        elif self.estado == "disparando":
            self._atualizar_disparo(dt)
        
        # Partículas mágicas
        if random.random() < 0.3:
            self.particulas.append({
                'x': self.x + random.uniform(-0.1, 0.1),
                'y': self.y + random.uniform(-0.1, 0.1),
                'vida': 0.3,
                'cor': self.cor
            })
        
        # Atualiza partículas
        for p in self.particulas:
            p['vida'] -= dt
            p['y'] -= dt * 0.5  # Sobe levemente
        self.particulas = [p for p in self.particulas if p['vida'] > 0]
    
    def _atualizar_orbita(self, dt):
        """Orbita ao redor do dono"""
        self.angulo_orbital += self.vel_orbital * dt
        rad = math.radians(self.angulo_orbital)
        
        # Flutua suavemente
        offset_y = math.sin(self.pulso) * 0.1
        
        self.x = self.dono.pos[0] + math.cos(rad) * self.dist_orbital
        self.y = self.dono.pos[1] + math.sin(rad) * self.dist_orbital + offset_y
    
    def _atualizar_carga(self, dt):
        """Carrega energia antes de disparar"""
        self.tempo_carga += dt
        
        # Cresce durante carga
        self.raio_visual = 0.15 + (self.tempo_carga / self.carga_max) * 0.15
        
        # Move-se para posição de disparo (entre dono e alvo)
        if self.alvo:
            dir_x = self.alvo.pos[0] - self.dono.pos[0]
            dir_y = self.alvo.pos[1] - self.dono.pos[1]
            dist = math.hypot(dir_x, dir_y)
            if dist > 0:
                dir_x /= dist
                dir_y /= dist
            
            # Move para frente do dono na direção do alvo
            target_x = self.dono.pos[0] + dir_x * 0.6
            target_y = self.dono.pos[1] + dir_y * 0.6
            
            self.x += (target_x - self.x) * dt * 5.0
            self.y += (target_y - self.y) * dt * 5.0
            
            # Calcula ângulo de disparo
            self.angulo_disparo = math.degrees(math.atan2(dir_y, dir_x))
        
        # Pronto para disparar
        if self.tempo_carga >= self.carga_max:
            self.estado = "disparando"
            self.vel_disparo = self.vel_max
    
    def _atualizar_disparo(self, dt):
        """Voa em direção ao alvo"""
        # Se tem alvo, persegue levemente
        if self.alvo and not self.alvo.morto:
            dir_x = self.alvo.pos[0] - self.x
            dir_y = self.alvo.pos[1] - self.y
            ang_alvo = math.degrees(math.atan2(dir_y, dir_x))
            
            # Ajuste suave de direção (homing leve)
            diff = ang_alvo - self.angulo_disparo
            while diff > 180: diff -= 360
            while diff < -180: diff += 360
            self.angulo_disparo += diff * dt * 2.0  # Homing suave
        
        # Movimento
        rad = math.radians(self.angulo_disparo)
        self.x += math.cos(rad) * self.vel_disparo * dt
        self.y += math.sin(rad) * self.vel_disparo * dt
        
        # Trail
        self.trail.append((self.x, self.y))
        if len(self.trail) > 12:
            self.trail.pop(0)
    
    def colidir(self, alvo):
        """Verifica colisão - só colide quando disparando"""
        if self.estado != "disparando":
            return False
        if alvo == self.dono:
            return False
        if alvo.morto:
            return False
        
        dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
        raio_alvo = alvo.dados.tamanho / 2
        
        return dist < (self.raio + raio_alvo)


class Projetil:
    """
    Projétil genérico que carrega dados do SKILL_DB
    v2.0 COLOSSAL - Suporta todos os novos tipos de projéteis
    """
    def __init__(self, nome_skill, x, y, angulo, dono):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.x = x
        self.y = y
        self.angulo = angulo
        self.dono = dono
        
        # Atributos básicos carregados
        self.tipo_efeito = data.get("efeito", "NORMAL")
        self.vel = data.get("velocidade", 10.0)
        self.raio = data.get("raio", 0.3)
        self.dano = data.get("dano", 10.0)
        self.cor = data.get("cor", BRANCO)
        self.vida = data.get("vida", 2.0)
        self.vida_max = self.vida
        
        # Elemento
        self.elemento = data.get("elemento", None)
        
        # Multi-shot support
        self.multi_shot = data.get("multi_shot", 1)
        
        # === NOVOS ATRIBUTOS v2.0 ===
        
        # Homing (teleguiado)
        self.homing = data.get("homing", False)
        self.homing_strength = 2.0 if self.homing else 0
        self.alvo = None
        
        # Perfuração
        self.perfura = data.get("perfura", False)
        self.alvos_perfurados = set() if self.perfura else None
        
        # Chain (correntes para múltiplos alvos)
        self.chain = data.get("chain", 0)
        self.chain_count = 0
        self.chain_decay = data.get("chain_decay", 0.8)
        self.chain_targets = set()
        
        # Retorno (volta para o dono)
        self.retorna = data.get("retorna", False)
        self.retornando = False
        self.dist_max_retorno = 8.0
        
        # Explosão no impacto
        self.raio_explosao = data.get("raio_explosao", 0)
        
        # Explosão com delay
        self.delay_explosao = data.get("delay_explosao", 0)
        self.explodiu = False
        
        # Cone (atinge área cônica)
        self.cone = data.get("cone", False)
        self.angulo_cone = data.get("angulo_cone", 60)
        
        # Duplicação temporal
        self.duplica_apos = data.get("duplica_apos", 0)
        self.duplicado = False
        
        # Split aleatório (Caos)
        self.split_aleatorio = data.get("split_aleatorio", False)
        self.max_splits = data.get("max_splits", 0)
        self.splits_feitos = 0
        
        # Backfire chance (Caos)
        self.chance_backfire = data.get("chance_backfire", 0)
        if self.chance_backfire > 0 and random.random() < self.chance_backfire:
            # Reverte direção!
            self.angulo += 180
        
        # Elemento aleatório (Caos)
        if data.get("elemento_aleatorio", False):
            elementos = ["FOGO", "GELO", "RAIO", "TREVAS", "LUZ", "NATUREZA", "ARCANO"]
            self.elemento = random.choice(elementos)
            # Ajusta cor baseado no elemento
            cores_elemento = {
                "FOGO": (255, 100, 0), "GELO": (150, 220, 255), "RAIO": (255, 255, 100),
                "TREVAS": (100, 0, 150), "LUZ": (255, 255, 200), "NATUREZA": (100, 255, 100),
                "ARCANO": (150, 100, 255)
            }
            self.cor = cores_elemento.get(self.elemento, self.cor)
        
        # Dano variável (Caos)
        dano_var = data.get("dano_variavel", None)
        if dano_var:
            multiplier = random.uniform(dano_var[0], dano_var[1])
            self.dano *= multiplier
        
        # Efeito aleatório (Caos)
        if data.get("efeito_aleatorio", False):
            efeitos = data.get("efeitos_possiveis", ["NORMAL"])
            self.tipo_efeito = random.choice(efeitos)
        
        # Condições de dano extra
        self.condicao = data.get("condicao", None)
        self.dano_bonus_condicao = data.get("dano_bonus_condicao", 1.0)
        self.executa = data.get("executa", False)  # Executa alvos com baixa vida
        
        # Lifesteal
        self.lifesteal = data.get("lifesteal", 0)
        
        # Remove congelamento (para Shatter)
        self.remove_congelamento = data.get("remove_congelamento", False)
        
        # Contagioso (espalha para outros)
        self.contagioso = data.get("contagioso", False)
        self.raio_contagio = data.get("raio_contagio", 2.0)
        
        self.ativo = True
        self.trail = []  # Rastro visual

    def atualizar(self, dt, alvos=None):
        """Atualiza projétil com suporte a homing e comportamentos especiais"""
        
        # === HOMING ===
        if self.homing and alvos:
            # Encontra alvo mais próximo
            if self.alvo is None or self.alvo.morto:
                menor_dist = float('inf')
                for alvo in alvos:
                    if alvo != self.dono and not alvo.morto:
                        dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
                        if dist < menor_dist:
                            menor_dist = dist
                            self.alvo = alvo
            
            # Persegue o alvo
            if self.alvo and not self.alvo.morto:
                dir_x = self.alvo.pos[0] - self.x
                dir_y = self.alvo.pos[1] - self.y
                ang_alvo = math.degrees(math.atan2(dir_y, dir_x))
                
                diff = ang_alvo - self.angulo
                while diff > 180: diff -= 360
                while diff < -180: diff += 360
                self.angulo += diff * self.homing_strength * dt
        
        # === RETORNO ===
        if self.retorna and not self.retornando:
            dist_dono = math.hypot(self.dono.pos[0] - self.x, self.dono.pos[1] - self.y)
            if dist_dono > self.dist_max_retorno or self.vida < self.vida_max * 0.3:
                self.retornando = True
        
        if self.retornando:
            dir_x = self.dono.pos[0] - self.x
            dir_y = self.dono.pos[1] - self.y
            self.angulo = math.degrees(math.atan2(dir_y, dir_x))
            dist_dono = math.hypot(dir_x, dir_y)
            if dist_dono < 0.5:
                self.ativo = False
        
        # === MOVIMENTO ===
        rad = math.radians(self.angulo)
        self.x += math.cos(rad) * self.vel * dt
        self.y += math.sin(rad) * self.vel * dt
        
        # Salva posição para trail
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)
        
        # === DUPLICAÇÃO TEMPORAL ===
        if self.duplica_apos > 0 and not self.duplicado:
            self.duplica_apos -= dt
            if self.duplica_apos <= 0:
                self.duplicado = True
                # Retorna dados para criar duplicata
                return {"duplicar": True, "x": self.x, "y": self.y, 
                        "angulo": self.angulo + random.uniform(-30, 30)}
        
        # === SPLIT ALEATÓRIO ===
        if self.split_aleatorio and self.splits_feitos < self.max_splits:
            if random.random() < 0.05:  # 5% chance por frame
                self.splits_feitos += 1
                return {"split": True, "x": self.x, "y": self.y,
                        "angulo": self.angulo + random.choice([-45, 45])}
        
        # === VIDA ===
        self.vida -= dt
        if self.vida <= 0:
            # Explosão com delay
            if self.delay_explosao > 0 and not self.explodiu:
                self.explodiu = True
                return {"explodir": True, "x": self.x, "y": self.y, 
                        "raio": self.raio_explosao or 2.0}
            self.ativo = False
        
        return None
    
    def verificar_condicao(self, alvo):
        """Verifica se a condição de dano extra é cumprida"""
        if not self.condicao:
            return 1.0
        
        hp_percent = alvo.vida / alvo.vida_max
        
        if self.condicao == "ALVO_BAIXA_VIDA" and hp_percent < 0.3:
            if self.executa:
                return 10.0  # Execução!
            return self.dano_bonus_condicao
        
        elif self.condicao == "ALVO_QUEIMANDO":
            for dot in alvo.dots_ativos:
                if dot.tipo in ["QUEIMANDO", "QUEIMAR"]:
                    return self.dano_bonus_condicao
        
        elif self.condicao == "ALVO_CONGELADO":
            if getattr(alvo, 'congelado', False):
                return self.dano_bonus_condicao
        
        return 1.0
    
    def pode_atingir(self, alvo):
        """Verifica se pode atingir o alvo (para perfuração)"""
        if self.perfura:
            if id(alvo) in self.alvos_perfurados:
                return False
            self.alvos_perfurados.add(id(alvo))
        return True
    
    def chain_para(self, alvo):
        """Tenta fazer chain para outro alvo"""
        if self.chain <= 0 or self.chain_count >= self.chain:
            return None
        
        self.chain_count += 1
        self.chain_targets.add(id(alvo))
        
        # Reduz dano
        self.dano *= self.chain_decay
        
        return {"chain": True, "from": (self.x, self.y), "to": alvo}


class AreaEffect:
    """
    Efeito de área (explosões, nuvens, campos, etc)
    v2.0 COLOSSAL - Suporta campos persistentes, vórtices, e mais
    """
    def __init__(self, nome_skill, x, y, dono):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.x = x
        self.y = y
        self.dono = dono
        
        self.raio = data.get("raio_area", 2.0)
        self.dano = data.get("dano", 10.0)
        self.cor = data.get("cor", BRANCO)
        self.duracao = data.get("duracao", 0.5)
        self.tipo_efeito = data.get("efeito", "NORMAL")
        
        # Elemento
        self.elemento = data.get("elemento", None)
        
        # Delay antes de ativar
        self.delay = data.get("delay", 0)
        self.ativado = self.delay <= 0
        self.aviso_visual = data.get("aviso_visual", self.delay > 0)
        
        # Garante que duração é suficiente após o delay
        if self.delay > 0 and self.duracao < 0.5:
            self.duracao = 0.5  # Mínimo 0.5s de duração ativa após delay
        
        self.vida = self.duracao
        self.ativo = True
        self.alvos_atingidos = set()  # Evita hit múltiplo inicial
        
        # Animação
        self.raio_atual = 0.0
        self.alpha = 255
        
        # === NOVOS ATRIBUTOS v2.0 ===
        
        # Dano por segundo (para campos persistentes)
        self.dano_por_segundo = data.get("dano_por_segundo", 0) or data.get("dano_tick", 0)
        self.tick_timer = 0
        self.tick_interval = 0.5
        
        # Slow
        self.slow_fator = data.get("slow_fator", 1.0)
        
        # Pull/Push
        self.puxa_para_centro = data.get("puxa_para_centro", False)
        self.puxa_continuo = data.get("puxa_continuo", False)
        self.forca_empurrao = data.get("forca_empurrao", 0)
        self.forca_puxar = 5.0 if self.puxa_para_centro else 0
        
        # Gravidade aumentada
        self.gravidade_aumentada = data.get("gravidade_aumentada", 1.0)
        
        # Ondas (múltiplas explosões)
        self.ondas = data.get("ondas", 1)
        self.onda_atual = 0
        self.intervalo_onda = 0.5
        self.timer_onda = 0
        
        # Pilares (múltiplos pontos)
        self.pilares = data.get("pilares", 0)
        self.posicoes_pilares = []
        if self.pilares > 0:
            for i in range(self.pilares):
                ang = (360 / self.pilares) * i + random.uniform(-20, 20)
                dist = random.uniform(1.0, self.raio)
                px = self.x + math.cos(math.radians(ang)) * dist
                py = self.y + math.sin(math.radians(ang)) * dist
                self.posicoes_pilares.append((px, py))
        
        # Vórtex (puxa continuamente)
        self.vortex = data.get("efeito") == "VORTEX" or self.puxa_continuo
        
        # Meteoros aleatórios (Caos)
        self.meteoros = data.get("meteoros_aleatorios", 0)
        self.meteoros_spawned = 0
        self.timer_meteoro = 0
        
        # Efeito secundário
        self.efeito2 = data.get("efeito2", None)
        
        # Stun/CC
        self.duracao_stun = data.get("duracao_stun", 0)
        self.duracao_fear = data.get("duracao_fear", 0)
        self.duracao_charme = data.get("duracao_charme", 0)
        self.chance_stun = data.get("chance_stun", 1.0)  # 100% por padrão
        
        # Taunt
        self.taunt = data.get("taunt", False)
        self.duracao_taunt = data.get("duracao_taunt", 0)

    def atualizar(self, dt, alvos=None):
        """Atualiza efeito de área com todos os novos comportamentos"""
        resultados = []
        
        # === DELAY ===
        if not self.ativado:
            self.delay -= dt
            if self.delay <= 0:
                self.ativado = True
                self.alvos_atingidos.clear()  # Reset para aplicar dano
            return resultados
        
        self.vida -= dt
        
        # === EXPANSÃO DO RAIO ===
        if self.raio_atual < self.raio:
            self.raio_atual += self.raio * 3 * dt
        
        # === ONDAS ===
        if self.ondas > 1 and self.onda_atual < self.ondas:
            self.timer_onda += dt
            if self.timer_onda >= self.intervalo_onda:
                self.timer_onda = 0
                self.onda_atual += 1
                self.alvos_atingidos.clear()  # Nova onda = novo dano
                resultados.append({"nova_onda": True})
        
        # === METEOROS ALEATÓRIOS ===
        if self.meteoros > 0 and self.meteoros_spawned < self.meteoros:
            self.timer_meteoro += dt
            if self.timer_meteoro >= 0.3:  # 1 meteoro a cada 0.3s
                self.timer_meteoro = 0
                self.meteoros_spawned += 1
                # Posição aleatória dentro da área
                ang = random.uniform(0, 360)
                dist = random.uniform(0, self.raio)
                mx = self.x + math.cos(math.radians(ang)) * dist
                my = self.y + math.sin(math.radians(ang)) * dist
                resultados.append({"meteoro": True, "x": mx, "y": my})
        
        # === VÓRTEX / PUXAR ===
        if (self.vortex or self.puxa_continuo) and alvos:
            for alvo in alvos:
                if alvo == self.dono or alvo.morto:
                    continue
                dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
                if dist < self.raio_atual * 1.5:  # Pull range um pouco maior
                    resultados.append({"pull": True, "alvo": alvo, "forca": self.forca_puxar})
        
        # === DANO POR SEGUNDO ===
        if self.dano_por_segundo > 0 and alvos:
            self.tick_timer += dt
            if self.tick_timer >= self.tick_interval:
                self.tick_timer = 0
                for alvo in alvos:
                    if alvo == self.dono or alvo.morto:
                        continue
                    dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
                    if dist < self.raio_atual:
                        resultados.append({
                            "dot_tick": True, 
                            "alvo": alvo, 
                            "dano": self.dano_por_segundo * self.tick_interval
                        })
        
        # === FADE OUT ===
        self.alpha = int(255 * max(0, self.vida / self.duracao))
        
        if self.vida <= 0:
            self.ativo = False
        
        return resultados
    
    def aplicar_efeitos_alvo(self, alvo):
        """Aplica todos os efeitos da área no alvo"""
        # Slow
        if self.slow_fator < 1.0:
            alvo.slow_timer = max(alvo.slow_timer, self.duracao)
            alvo.slow_fator = min(alvo.slow_fator, self.slow_fator)
        
        # Stun
        if self.duracao_stun > 0 and random.random() < self.chance_stun:
            alvo.stun_timer = max(alvo.stun_timer, self.duracao_stun)
        
        # Fear
        if self.duracao_fear > 0:
            if hasattr(alvo, 'medo_timer'):
                alvo.medo_timer = max(alvo.medo_timer, self.duracao_fear)
            alvo.brain.medo = 1.0
        
        # Gravidade
        if self.gravidade_aumentada > 1.0:
            # Impede pulo e causa slow
            alvo.vel_z = min(alvo.vel_z, 0)
            alvo.slow_fator = min(alvo.slow_fator, 1.0 / self.gravidade_aumentada)
        
        # Efeito principal
        alvo._aplicar_efeito_status(self.tipo_efeito)
        
        # Efeito secundário
        if self.efeito2:
            alvo._aplicar_efeito_status(self.efeito2)
    
    def calcular_puxar(self, alvo_pos):
        """Calcula força de puxar para o centro"""
        if not (self.puxa_para_centro or self.vortex):
            return (0, 0)
        
        dx = self.x - alvo_pos[0]
        dy = self.y - alvo_pos[1]
        dist = math.hypot(dx, dy)
        
        if dist < 0.1:
            return (0, 0)
        
        # Normaliza e aplica força
        forca = self.forca_puxar * (1.0 - dist / self.raio)  # Mais forte no centro
        return (dx / dist * forca, dy / dist * forca)


class Beam:
    """Raio instantâneo (relâmpagos, lasers)"""
    def __init__(self, nome_skill, x_origem, y_origem, x_destino, y_destino, dono):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.x1, self.y1 = x_origem, y_origem
        self.x2, self.y2 = x_destino, y_destino
        self.dono = dono
        
        self.dano = data.get("dano", 15.0)
        self.cor = data.get("cor", (255, 255, 100))
        self.tipo_efeito = data.get("efeito", "ATORDOAR")
        self.alcance = data.get("alcance", 8.0)
        
        # Chain (Corrente em Cadeia)
        self.chain = data.get("chain", 0)
        self.chain_count = 0
        self.chain_decay = data.get("chain_decay", 0.8)
        self.chain_targets = set()
        
        # Canalização
        self.canalizavel = data.get("canalizavel", False)
        self.dano_por_segundo = data.get("dano_por_segundo", 0)
        self.duracao_max = data.get("duracao_max", 0)
        self.penetra_escudo = data.get("penetra_escudo", False)
        
        self.vida = 0.15  # Curta duração visual
        self.ativo = True
        self.hit_aplicado = False
        
        # Efeito visual
        self.largura = 8
        self.segments = self._gerar_zigzag()

    def _gerar_zigzag(self):
        """Gera pontos de zigzag para efeito de raio"""
        segments = [(self.x1, self.y1)]
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        dist = math.hypot(dx, dy)
        
        if dist == 0:
            return segments
        
        num_segs = int(dist / 0.5) + 1
        for i in range(1, num_segs):
            t = i / num_segs
            px = self.x1 + dx * t + random.uniform(-0.3, 0.3)
            py = self.y1 + dy * t + random.uniform(-0.3, 0.3)
            segments.append((px, py))
        
        segments.append((self.x2, self.y2))
        return segments

    def atualizar(self, dt):
        self.vida -= dt
        self.largura = max(1, int(8 * (self.vida / 0.15)))
        if self.vida <= 0:
            self.ativo = False


class Buff:
    """Efeito de buff/debuff em um lutador"""
    def __init__(self, nome_skill, alvo):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.alvo = alvo
        self.duracao = data.get("duracao", 5.0)
        self.vida = self.duracao
        self.cor = data.get("cor", BRANCO)
        
        # Efeitos possíveis
        self.escudo = data.get("escudo", 0)
        self.escudo_atual = self.escudo
        self.buff_dano = data.get("buff_dano", 1.0)
        self.buff_velocidade = data.get("buff_velocidade", 1.0)
        self.refletir = data.get("refletir", 0)
        self.cura_por_segundo = data.get("regen", 0)
        
        self.ativo = True

    def atualizar(self, dt):
        self.vida -= dt
        
        # Cura contínua
        if self.cura_por_segundo > 0:
            self.alvo.vida = min(self.alvo.vida_max, self.alvo.vida + self.cura_por_segundo * dt)
        
        if self.vida <= 0:
            self.ativo = False
    
    def absorver_dano(self, dano):
        """Tenta absorver dano com escudo, retorna dano restante"""
        if self.escudo_atual <= 0:
            return dano
        
        if dano <= self.escudo_atual:
            self.escudo_atual -= dano
            return 0
        else:
            restante = dano - self.escudo_atual
            self.escudo_atual = 0
            return restante


class DotEffect:
    """Damage over Time (veneno, sangramento, queimadura)"""
    def __init__(self, tipo, alvo, dano_por_tick, duracao, cor):
        self.tipo = tipo
        self.alvo = alvo
        self.dano_por_tick = dano_por_tick * 0.5  # Reduzido em 50%
        self.duracao = duracao
        self.vida = duracao
        self.cor = cor
        
        self.tick_timer = 0.0
        self.tick_interval = 0.5
        self.ativo = True

    def atualizar(self, dt):
        self.vida -= dt
        self.tick_timer += dt
        
        if self.tick_timer >= self.tick_interval:
            self.tick_timer = 0
            # Aplica dano
            if not self.alvo.morto:
                self.alvo.vida -= self.dano_por_tick
                if self.alvo.vida <= 0:
                    self.alvo.morrer()
        
        if self.vida <= 0:
            self.ativo = False


# =============================================================================
# NOVAS CLASSES v2.0 - SUMMON, TRAP, TRANSFORM, CHANNEL
# =============================================================================

class Summon:
    """
    Criatura invocada que luta ao lado do conjurador
    v2.0 - Suporta Fenix, Treant, Espirito, Copia Sombria
    """
    def __init__(self, nome_skill, x, y, dono):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.x = x
        self.y = y
        self.dono = dono
        
        # Stats da criatura
        self.vida_max = data.get("summon_vida", 50.0)
        self.vida = self.vida_max
        self.dano = data.get("summon_dano", 10.0)
        self.cor = data.get("cor", (200, 200, 200))
        self.duracao = data.get("duracao", 10.0)
        self.vida_timer = self.duracao
        
        # Tipo de summon
        self.summon_tipo = data.get("summon_tipo", "BASICO")
        self.copia_caster = data.get("copia_caster", False)
        
        # Comportamento
        self.raio_agressao = 5.0
        self.raio_ataque = 1.5
        self.velocidade = 4.0
        self.cooldown_ataque = 1.5
        self.cd_timer = 0
        
        # Estado
        self.ativo = True
        self.alvo = None
        self.vel = [0, 0]
        self.angulo = 0
        
        # Habilidades especiais
        self.revive_count = 1 if "fenix" in nome_skill.lower() else 0
        self.aura_dano = data.get("aura_dano", 0)
        self.aura_raio = data.get("aura_raio", 0)
        
        # Projectile buffer (para summons que atiram)
        self.buffer_projeteis = []
    
    def atualizar(self, dt, alvos):
        """Atualiza comportamento do summon"""
        if not self.ativo:
            return []
        
        resultados = []
        
        # Timer de duracao
        self.vida_timer -= dt
        if self.vida_timer <= 0:
            self.ativo = False
            return resultados
        
        # Cooldown de ataque
        if self.cd_timer > 0:
            self.cd_timer -= dt
        
        # Encontra alvo mais proximo
        melhor_alvo = None
        menor_dist = self.raio_agressao
        
        for alvo in alvos:
            if alvo == self.dono or alvo.morto:
                continue
            dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
            if dist < menor_dist:
                menor_dist = dist
                melhor_alvo = alvo
        
        self.alvo = melhor_alvo
        
        if self.alvo:
            # Move em direcao ao alvo
            dx = self.alvo.pos[0] - self.x
            dy = self.alvo.pos[1] - self.y
            dist = math.hypot(dx, dy) or 1
            self.angulo = math.degrees(math.atan2(dy, dx))
            
            if dist > self.raio_ataque:
                # Aproxima
                self.x += (dx / dist) * self.velocidade * dt
                self.y += (dy / dist) * self.velocidade * dt
            elif self.cd_timer <= 0:
                # Ataca!
                self.cd_timer = self.cooldown_ataque
                resultados.append({
                    "tipo": "ataque",
                    "alvo": self.alvo,
                    "dano": self.dano,
                    "x": self.x,
                    "y": self.y
                })
        else:
            # Segue o dono
            dx = self.dono.pos[0] - self.x
            dy = self.dono.pos[1] - self.y
            dist = math.hypot(dx, dy) or 1
            
            if dist > 2.0:
                self.x += (dx / dist) * self.velocidade * dt
                self.y += (dy / dist) * self.velocidade * dt
        
        # Aura de dano
        if self.aura_dano > 0 and self.aura_raio > 0:
            for alvo in alvos:
                if alvo == self.dono or alvo.morto:
                    continue
                dist = math.hypot(alvo.pos[0] - self.x, alvo.pos[1] - self.y)
                if dist < self.aura_raio:
                    resultados.append({
                        "tipo": "aura",
                        "alvo": alvo,
                        "dano": self.aura_dano * dt
                    })
        
        return resultados
    
    def tomar_dano(self, dano):
        """Summon recebe dano"""
        self.vida -= dano
        if self.vida <= 0:
            if self.revive_count > 0:
                # Fenix revive!
                self.revive_count -= 1
                self.vida = self.vida_max * 0.5
                return {"revive": True, "x": self.x, "y": self.y}
            else:
                self.ativo = False
                return {"morreu": True}
        return None


class Trap:
    """
    Estrutura/armadilha colocada no campo
    v2.0 - Muralha de Gelo, armadilhas, etc
    """
    def __init__(self, nome_skill, x, y, dono):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.x = x
        self.y = y
        self.dono = dono
        
        self.vida_max = data.get("vida_estrutura", 100.0)
        self.vida = self.vida_max
        self.duracao = data.get("duracao", 5.0)
        self.vida_timer = self.duracao
        self.cor = data.get("cor", (200, 200, 255))
        
        # Dimensoes (para muralhas)
        self.largura = data.get("largura", 2.0)
        self.altura = data.get("altura", 3.0)
        self.raio = max(self.largura, self.altura) / 2  # Para desenho circular
        self.angulo = 0  # Para rotação visual
        
        # Comportamento
        self.bloqueia_movimento = data.get("bloqueia_movimento", True)
        self.bloqueia_projeteis = data.get("bloqueia_projeteis", True)
        self.dano_contato = data.get("dano_contato", 0)
        self.efeito_contato = data.get("efeito_contato", None)
        
        self.ativo = True
    
    def atualizar(self, dt):
        """Atualiza trap"""
        self.vida_timer -= dt
        if self.vida_timer <= 0 or self.vida <= 0:
            self.ativo = False
    
    def colidir_ponto(self, px, py):
        """Verifica se um ponto colide com a trap"""
        # Colisao retangular simplificada
        return (abs(px - self.x) < self.largura / 2 and 
                abs(py - self.y) < self.altura / 2)
    
    def tomar_dano(self, dano):
        """Trap recebe dano"""
        self.vida -= dano
        if self.vida <= 0:
            self.ativo = False


class Transform:
    """
    Transformacao temporaria do personagem
    v2.0 - Avatar de Gelo, Forma Relampago
    """
    def __init__(self, nome_skill, alvo):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.alvo = alvo
        self.duracao = data.get("duracao", 10.0)
        self.vida = self.duracao
        self.cor = data.get("cor", (200, 200, 255))
        
        # Salva stats originais
        self.stats_originais = {
            "velocidade": alvo.velocidade if hasattr(alvo, 'velocidade') else 5.0,
            "cor": alvo.cor if hasattr(alvo, 'cor') else (255, 255, 255),
        }
        
        # Modificadores
        self.bonus_resistencia = data.get("bonus_resistencia", 0)
        self.bonus_velocidade = data.get("bonus_velocidade", 1.0)
        self.intangivel = data.get("intangivel", False)
        self.dano_contato = data.get("dano_contato", 0)
        
        # Auras
        self.aura_slow = data.get("aura_slow", 1.0)
        self.aura_raio = data.get("aura_raio", 0)
        
        # Aplica transformacao
        self._aplicar_transformacao()
        self.ativo = True
    
    def _aplicar_transformacao(self):
        """Aplica os efeitos da transformacao"""
        if hasattr(self.alvo, 'velocidade'):
            self.alvo.velocidade *= self.bonus_velocidade
        if hasattr(self.alvo, 'cor'):
            self.alvo.cor = self.cor
        if self.intangivel and hasattr(self.alvo, 'intangivel'):
            self.alvo.intangivel = True
    
    def _reverter_transformacao(self):
        """Reverte para estado original"""
        if hasattr(self.alvo, 'velocidade'):
            self.alvo.velocidade = self.stats_originais["velocidade"]
        if hasattr(self.alvo, 'cor'):
            self.alvo.cor = self.stats_originais["cor"]
        if self.intangivel and hasattr(self.alvo, 'intangivel'):
            self.alvo.intangivel = False
    
    def atualizar(self, dt, alvos=None):
        """Atualiza transformacao"""
        resultados = []
        
        self.vida -= dt
        
        # Dano de contato
        if self.dano_contato > 0 and alvos:
            for alvo in alvos:
                if alvo == self.alvo or alvo.morto:
                    continue
                dist = math.hypot(alvo.pos[0] - self.alvo.pos[0], 
                                 alvo.pos[1] - self.alvo.pos[1])
                if dist < 1.0:  # Raio de contato
                    resultados.append({
                        "tipo": "contato",
                        "alvo": alvo,
                        "dano": self.dano_contato * dt
                    })
        
        # Aura de slow
        if self.aura_raio > 0 and self.aura_slow < 1.0 and alvos:
            for alvo in alvos:
                if alvo == self.alvo or alvo.morto:
                    continue
                dist = math.hypot(alvo.pos[0] - self.alvo.pos[0],
                                 alvo.pos[1] - self.alvo.pos[1])
                if dist < self.aura_raio:
                    resultados.append({
                        "tipo": "slow",
                        "alvo": alvo,
                        "fator": self.aura_slow
                    })
        
        if self.vida <= 0:
            self._reverter_transformacao()
            self.ativo = False
        
        return resultados


class Channel:
    """
    Skill canalizada que requer concentracao
    v2.0 - Chamas do Dragao, Fotossintese, Desintegrar
    """
    def __init__(self, nome_skill, dono):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        
        self.dono = dono
        self.duracao_max = data.get("duracao_max", 3.0)
        self.vida = self.duracao_max
        self.cor = data.get("cor", (255, 200, 100))
        
        # Efeitos
        self.dano_por_segundo = data.get("dano_por_segundo", 0)
        self.cura_por_segundo = data.get("cura_por_segundo", 0)
        self.alcance = data.get("alcance", 6.0)
        self.tipo_efeito = data.get("efeito", "NORMAL")
        self.penetra_escudo = data.get("penetra_escudo", False)
        
        # Restricoes
        self.imobiliza = data.get("imobiliza", False)
        
        # Estado
        self.ativo = True
        self.canalizando = True
        self.tick_timer = 0
        self.tick_interval = 0.1
        
        # Direção do beam (se aplicavel)
        self.angulo = dono.angulo_olhar if hasattr(dono, 'angulo_olhar') else 0
    
    def atualizar(self, dt, alvos=None):
        """Atualiza canalizacao"""
        resultados = []
        
        if not self.canalizando:
            self.ativo = False
            return resultados
        
        self.vida -= dt
        self.tick_timer += dt
        
        # Imobiliza o caster
        if self.imobiliza and hasattr(self.dono, 'vel'):
            self.dono.vel = [0, 0]
        
        # Aplica efeitos a cada tick
        if self.tick_timer >= self.tick_interval:
            self.tick_timer = 0
            
            # Cura o caster
            if self.cura_por_segundo > 0:
                cura = self.cura_por_segundo * self.tick_interval
                self.dono.vida = min(self.dono.vida_max, self.dono.vida + cura)
                resultados.append({
                    "tipo": "cura",
                    "alvo": self.dono,
                    "valor": cura
                })
            
            # Dano em linha (beam)
            if self.dano_por_segundo > 0 and alvos:
                rad = math.radians(self.angulo)
                for alvo in alvos:
                    if alvo == self.dono or alvo.morto:
                        continue
                    
                    # Verifica se alvo esta na linha do beam
                    dx = alvo.pos[0] - self.dono.pos[0]
                    dy = alvo.pos[1] - self.dono.pos[1]
                    dist = math.hypot(dx, dy)
                    
                    if dist < self.alcance:
                        # Angulo para o alvo
                        ang_alvo = math.degrees(math.atan2(dy, dx))
                        diff = abs(ang_alvo - self.angulo)
                        if diff > 180:
                            diff = 360 - diff
                        
                        # Se o alvo esta dentro de 15 graus do beam
                        if diff < 15:
                            dano = self.dano_por_segundo * self.tick_interval
                            resultados.append({
                                "tipo": "dano",
                                "alvo": alvo,
                                "dano": dano,
                                "efeito": self.tipo_efeito,
                                "penetra_escudo": self.penetra_escudo
                            })
        
        if self.vida <= 0:
            self.ativo = False
        
        return resultados
    
    def interromper(self):
        """Interrompe a canalizacao"""
        self.canalizando = False
        self.ativo = False