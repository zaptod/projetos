# combat.py
import copy
import math
import random
from utils.config import BRANCO
from core.skills import get_skill_data
from core.status_runtime import BUFF_EFFECT_RUNTIME


PERFIS_MUTACAO = (
    {
        "nome": "brutal",
        "buff_dano": 1.5,
        "buff_velocidade": 0.8,
        "mod_dano_recebido": 1.15,
    },
    {
        "nome": "agil",
        "buff_dano": 0.85,
        "buff_velocidade": 1.6,
        "mod_dano_recebido": 1.0,
    },
    {
        "nome": "resiliente",
        "buff_dano": 0.9,
        "buff_velocidade": 0.85,
        "mod_dano_recebido": 0.6,
    },
)


def criar_metadata_impacto(fonte=None, **overrides):
    """Cria o contrato unico que acompanha uma fonte ate ``Lutador``."""
    metadata = {
        "nome_skill": getattr(fonte, "nome", None),
        "tipo_fonte": getattr(fonte, "tipo_fonte", "desconhecida"),
        "eh_skill": bool(getattr(fonte, "eh_skill", False)),
        "eh_projetil": bool(getattr(fonte, "eh_projetil", False)),
        "ground": bool(getattr(fonte, "ground", False)),
        "rouba_buff": bool(getattr(fonte, "rouba_buff", False)),
        "refletido": bool(getattr(fonte, "refletido", False)),
    }
    metadata.update(overrides)
    return metadata


def refletir_projetil(projetil, novo_dono):
    """Troca ownership e voo uma unica vez, antes de qualquer dano."""
    if (
        projetil is None
        or novo_dono is None
        or getattr(projetil, "dono", None) is novo_dono
        or getattr(projetil, "reflexoes", 0) >= 1
        or not getattr(projetil, "ativo", True)
    ):
        return False

    dono_anterior = getattr(projetil, "dono", None)
    projetil.dono = novo_dono
    if hasattr(projetil, "angulo"):
        projetil.angulo = (float(projetil.angulo) + 180.0) % 360.0
    if hasattr(projetil, "angulo_disparo"):
        projetil.angulo_disparo = (
            float(projetil.angulo_disparo) + 180.0
        ) % 360.0
    if hasattr(projetil, "angulo_visual"):
        projetil.angulo_visual = getattr(
            projetil,
            "angulo",
            getattr(projetil, "angulo_disparo", projetil.angulo_visual),
        )
    if hasattr(projetil, "alvo"):
        projetil.alvo = dono_anterior
    if hasattr(projetil, "alvo_forcado"):
        projetil.alvo_forcado = dono_anterior
    if hasattr(projetil, "retornando"):
        projetil.retornando = False
    projetil.reflexoes = 1
    projetil.refletido = True
    return True


def _posicao_alvo(alvo):
    """Retorna a posicao planar de lutadores e entidades auxiliares."""
    pos = getattr(alvo, "pos", None)
    if pos is not None and len(pos) >= 2:
        return float(pos[0]), float(pos[1])
    if hasattr(alvo, "x") and hasattr(alvo, "y"):
        return float(alvo.x), float(alvo.y)
    return None


def _alvo_esta_ativo(alvo):
    """Contrato minimo usado por efeitos que escolhem alvos adicionais."""
    if alvo is None or getattr(alvo, "morto", False):
        return False
    return getattr(alvo, "ativo", True) and _posicao_alvo(alvo) is not None


def alvo_cumpre_condicao(alvo, condicao):
    """Avalia as condicoes ofensivas declaradas no ``SKILL_DB``."""
    if not condicao:
        return True

    if condicao == "ALVO_BAIXA_VIDA":
        vida_max = max(0.0001, float(getattr(alvo, "vida_max", 0.0)))
        return float(getattr(alvo, "vida", 0.0)) / vida_max < 0.3

    if condicao == "ALVO_QUEIMANDO":
        return any(
            getattr(dot, "tipo", None) in {"QUEIMANDO", "QUEIMAR"}
            and getattr(dot, "ativo", True)
            for dot in getattr(alvo, "dots_ativos", ())
        )

    if condicao == "ALVO_CONGELADO":
        return bool(
            getattr(alvo, "congelado", False)
            or getattr(alvo, "congelado_timer", 0.0) > 0.0
        )

    # Condicao desconhecida nunca concede bonus silenciosamente.
    return False


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
        self.tipo_fonte = "projetil_arma"
        self.eh_skill = False
        self.eh_projetil = True
        self.ground = False
        self.rouba_buff = False
        self.reflexoes = 0
        self.refletido = False
        
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
        self.tipo_fonte = "orbe_arma"
        self.eh_skill = False
        self.eh_projetil = True
        self.ground = False
        self.rouba_buff = False
        self.reflexoes = 0
        self.refletido = False
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
        self.tipo_fonte = "projetil_skill"
        self.eh_skill = True
        self.eh_projetil = True
        self.ground = False
        self.rouba_buff = bool(data.get("rouba_buff", False))
        self.reflexoes = 0
        self.refletido = False
        
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
        self.fonte_impacto = object()
        
        # === NOVOS ATRIBUTOS v2.0 ===
        
        # Homing (teleguiado)
        self.homing = data.get("homing", False)
        self.homing_strength = 2.0 if self.homing else 0
        self.alvo = None
        
        # Perfuração
        self.perfura = data.get("perfura", False)
        self.alvos_perfurados = set() if self.perfura else None
        
        # Alvo explícito usado por vetores derivados, como o contágio.
        self.alvo_forcado = None
        
        # Retorno (volta para o dono)
        self.retorna = data.get("retorna", False)
        self.retornando = False
        self.dist_max_retorno = 8.0
        
        # Explosão no impacto
        self.raio_explosao = data.get("raio_explosao", 0)
        
        # Explosão com delay
        self.delay_explosao = data.get("delay_explosao", 0)
        self.explodiu = False

        # Metadados do status viajam com a fonte; o alvo não reconstrói a skill.
        self.duracao_efeito = data.get("duracao_controle")
        self.percentual_efeito = data.get("link_percent")
        
        # Cone (atinge área cônica)
        self.cone = data.get("cone", False)
        self.angulo_cone = data.get("angulo_cone", 60)
        self.origem_cone = (float(dono.pos[0]), float(dono.pos[1])) if self.cone else None
        self.alcance_cone = data.get(
            "alcance_cone",
            data.get("alcance", max(0.5, self.vel * self.vida)),
        )
        
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
        self.alvos_contagiados = set()
        
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
        # Cones sao volumes ancorados no ponto e angulo originais do cast.
        rad = math.radians(self.angulo)
        if not self.cone:
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
            if self.tipo_efeito == "BOMBA_RELOGIO":
                self.ativo = False
                return None
            # Explosão com delay
            if self.delay_explosao > 0 and not self.explodiu:
                self.explodiu = True
                self.ativo = False
                return {"explodir": True, "x": self.x, "y": self.y, 
                        "raio": self.raio_explosao or 2.0}
            self.ativo = False
        
        return None

    def criar_duplicata(self, evento):
        """Materializa o unico filho temporal, incapaz de duplicar novamente."""
        if not evento or not evento.get("duplicar"):
            return None
        duplicata = Projetil(
            self.nome,
            evento["x"],
            evento["y"],
            evento["angulo"],
            self.dono,
        )
        duplicata.dano = self.dano * 0.7
        duplicata.duplicado = True
        duplicata.duplica_apos = 0.0
        duplicata.refletido = self.refletido
        duplicata.reflexoes = self.reflexoes
        return duplicata
    
    def verificar_condicao(self, alvo):
        """Retorna o multiplicador declarado quando a condição é cumprida."""
        if not self.condicao:
            return 1.0

        if alvo_cumpre_condicao(alvo, self.condicao):
            if self.executa:
                return 10.0
            return self.dano_bonus_condicao

        return 1.0

    def colidir(self, alvo):
        """Testa a colisão circular padrão ou o volume angular de um cone."""
        if alvo is self.dono or not _alvo_esta_ativo(alvo) or not self.ativo:
            return False

        pos_alvo = _posicao_alvo(alvo)
        raio_alvo = float(getattr(alvo, "raio_fisico", 0.5))
        if not self.cone:
            return math.hypot(pos_alvo[0] - self.x, pos_alvo[1] - self.y) < (
                self.raio + raio_alvo
            )

        origem_x, origem_y = self.origem_cone
        dx = pos_alvo[0] - origem_x
        dy = pos_alvo[1] - origem_y
        distancia = math.hypot(dx, dy)
        if distancia > self.alcance_cone + raio_alvo:
            return False
        if distancia <= raio_alvo:
            return True

        angulo_alvo = math.degrees(math.atan2(dy, dx))
        diferenca = (angulo_alvo - self.angulo + 180.0) % 360.0 - 180.0
        tolerancia_alvo = math.degrees(
            math.asin(min(1.0, raio_alvo / max(distancia, raio_alvo)))
        )
        return abs(diferenca) <= self.angulo_cone / 2.0 + tolerancia_alvo

    def criar_contagio(self, alvo_origem, candidatos):
        """Cria o próximo vetor da Praga sem reinfectar a mesma fonte."""
        if not self.contagioso or not _alvo_esta_ativo(alvo_origem):
            return None

        origem = _posicao_alvo(alvo_origem)
        self.alvos_contagiados.add(id(alvo_origem))
        elegiveis = []
        for candidato in candidatos or ():
            if (
                candidato is self.dono
                or candidato is alvo_origem
                or id(candidato) in self.alvos_contagiados
                or not _alvo_esta_ativo(candidato)
                or not callable(getattr(candidato, "resolver_impacto", None))
            ):
                continue
            destino = _posicao_alvo(candidato)
            distancia = math.hypot(destino[0] - origem[0], destino[1] - origem[1])
            if distancia <= self.raio_contagio:
                elegiveis.append((distancia, candidato, destino))

        if not elegiveis:
            return None

        _, proximo, destino = min(elegiveis, key=lambda item: item[0])
        angulo = math.degrees(math.atan2(destino[1] - origem[1], destino[0] - origem[0]))
        contagio = Projetil(self.nome, origem[0], origem[1], angulo, self.dono)
        contagio.dano = self.dano
        contagio.alvo_forcado = proximo
        contagio.alvos_contagiados = self.alvos_contagiados.copy()
        return contagio

    def pode_atingir(self, alvo):
        """Verifica se pode atingir o alvo (para perfuração)"""
        if self.perfura:
            if id(alvo) in self.alvos_perfurados:
                return False
            self.alvos_perfurados.add(id(alvo))
        return True
    
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
        self.tipo_fonte = "area_skill"
        self.eh_skill = True
        self.eh_projetil = False
        # Explosoes e fenomenos aereos atingem alvos em voo. Apenas skills
        # explicitamente presas ao solo concedem a imunidade de Levitar.
        self.ground = bool(data.get("ground", False))
        self.rouba_buff = False
        self.refletido = False
        
        self.raio = data.get("raio_area", 2.0)
        self.dano = data.get("dano", 10.0)
        self.dano_precalculado = False
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

        # Condições ofensivas também pertencem ao contrato de AREA.
        self.condicao = data.get("condicao")
        self.dano_bonus_condicao = data.get("dano_bonus_condicao", 1.0)
        self.executa = data.get("executa", False)
        self.remove_congelamento = data.get("remove_congelamento", False)

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
                resultados.append({
                    "nova_onda": True,
                    "x": self.x,
                    "y": self.y,
                    "raio": self.raio * 1.5,
                })
        
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
                imune_ground = getattr(alvo, "esta_imune_ground", None)
                if self.ground and callable(imune_ground) and imune_ground():
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
                    imune_ground = getattr(alvo, "esta_imune_ground", None)
                    if self.ground and callable(imune_ground) and imune_ground():
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
    
    def aplicar_efeitos_alvo(self, alvo, aplicar_efeito_principal=True):
        """Aplica os efeitos de controle da área no alvo."""
        usa_runtime_status = callable(getattr(alvo, "esta_imune_a_debuffs", None))

        # Slow
        if self.slow_fator < 1.0:
            if usa_runtime_status:
                intensidade = 0.5 / max(0.01, self.slow_fator)
                alvo._aplicar_efeito_status(
                    "LENTO",
                    duracao=self.duracao,
                    intensidade=intensidade,
                )
            else:
                alvo.slow_timer = max(alvo.slow_timer, self.duracao)
                alvo.slow_fator = min(alvo.slow_fator, self.slow_fator)
        
        # Stun
        if self.duracao_stun > 0 and random.random() < self.chance_stun:
            if usa_runtime_status:
                alvo._aplicar_efeito_status("ATORDOADO", duracao=self.duracao_stun)
            else:
                alvo.stun_timer = max(alvo.stun_timer, self.duracao_stun)
        
        # Fear
        if self.duracao_fear > 0:
            if usa_runtime_status:
                alvo._aplicar_efeito_status("MEDO", duracao=self.duracao_fear)
            else:
                alvo.medo_timer = max(alvo.medo_timer, self.duracao_fear)
                brain = getattr(alvo, "brain", None)
                if brain is not None:
                    brain.medo = 1.0
        
        # Gravidade
        if self.gravidade_aumentada > 1.0:
            # Impede pulo e causa slow
            alvo.vel_z = min(alvo.vel_z, 0)
            fator_gravidade = 1.0 / self.gravidade_aumentada
            if usa_runtime_status:
                alvo._aplicar_efeito_status(
                    "LENTO",
                    duracao=self.duracao,
                    intensidade=0.5 / max(0.01, fator_gravidade),
                )
            else:
                alvo.slow_timer = max(alvo.slow_timer, self.duracao)
                alvo.slow_fator = min(alvo.slow_fator, fator_gravidade)
        
        # Efeito principal
        if aplicar_efeito_principal:
            kwargs_status = {}
            if self.dono is not None:
                kwargs_status["origem"] = self.dono
            if self.tipo_efeito == "CHARME" and self.duracao_charme > 0.0:
                kwargs_status["duracao"] = self.duracao_charme
            alvo._aplicar_efeito_status(self.tipo_efeito, **kwargs_status)
        
        # Efeito secundário
        if self.efeito2:
            if self.dono is None:
                alvo._aplicar_efeito_status(self.efeito2)
            else:
                alvo._aplicar_efeito_status(self.efeito2, origem=self.dono)

        if self.taunt and self.dono is not None and self.duracao_taunt > 0.0:
            aplicar_taunt = getattr(alvo, "aplicar_provocacao", None)
            if callable(aplicar_taunt):
                aplicar_taunt(self.dono, self.duracao_taunt)

    def verificar_condicao(self, alvo):
        """Retorna ``(cumprida, multiplicador)`` para a resolução da área."""
        if not self.condicao:
            return True, 1.0
        cumprida = alvo_cumpre_condicao(alvo, self.condicao)
        if not cumprida:
            return False, 1.0
        if self.executa:
            return True, 10.0
        return True, self.dano_bonus_condicao
    
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
        self.tipo_fonte = "beam_skill"
        self.eh_skill = True
        self.eh_projetil = False
        self.ground = False
        self.rouba_buff = False
        self.refletido = False
        
        self.dano = data.get("dano", 15.0)
        self.cor = data.get("cor", (255, 255, 100))
        self.tipo_efeito = data.get("efeito", "ATORDOAR")
        self.alcance = data.get("alcance", 8.0)
        
        # Chain (Corrente em Cadeia)
        self.chain = data.get("chain", 0)
        self.chain_count = 0
        self.chain_decay = data.get("chain_decay", 0.8)
        self.chain_range = data.get("chain_range", 5.0)
        self.chain_targets = set()
        self.alvo_forcado = None
        
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

    def criar_salto(self, alvo_origem, candidatos):
        """Cria um segmento de chain lightning para o hostil mais próximo."""
        if self.chain <= 0 or self.chain_count >= self.chain:
            return None

        origem = _posicao_alvo(alvo_origem)
        if origem is None:
            return None
        self.chain_targets.add(id(alvo_origem))

        elegiveis = []
        for candidato in candidatos or ():
            if (
                candidato is self.dono
                or candidato is alvo_origem
                or id(candidato) in self.chain_targets
                or not _alvo_esta_ativo(candidato)
            ):
                continue
            destino = _posicao_alvo(candidato)
            distancia = math.hypot(destino[0] - origem[0], destino[1] - origem[1])
            if distancia <= self.chain_range:
                elegiveis.append((distancia, candidato, destino))

        if not elegiveis:
            return None

        _, proximo, destino = min(elegiveis, key=lambda item: item[0])
        salto = Beam(
            self.nome,
            origem[0],
            origem[1],
            destino[0],
            destino[1],
            self.dono,
        )
        salto.dano = self.dano * self.chain_decay
        salto.chain_count = self.chain_count + 1
        salto.chain_targets = self.chain_targets.copy()
        salto.alvo_forcado = proximo
        return salto


class Buff:
    """Efeito de buff/debuff em um lutador"""
    def __init__(self, nome_skill, alvo, *, rng=None):
        self.nome = nome_skill
        data = get_skill_data(nome_skill)
        self.efeito = data.get("efeito_buff")
        defaults = BUFF_EFFECT_RUNTIME.get(self.efeito, {})

        self.alvo = alvo
        self.dono = alvo
        self.rng = rng if rng is not None else random
        self.roubavel = bool(data.get("roubavel", True))
        duracao_fallback = data.get("duracao_imortal") or data.get("imune_debuffs") or 5.0
        self.duracao = data.get("duracao", duracao_fallback)
        if self.efeito == "IMORTAL":
            self.duracao = data.get("duracao_imortal", self.duracao)
        self.vida = self.duracao
        self.cor = data.get("cor", BRANCO)
        
        # Efeitos possíveis
        self.escudo = data.get("escudo", 0)
        self.escudo_atual = self.escudo
        self.buff_dano = data.get(
            "buff_dano",
            data.get("bonus_dano", defaults.get("buff_dano", 1.0)),
        )
        self.buff_velocidade = data.get(
            "buff_velocidade",
            data.get(
                "bonus_velocidade",
                data.get(
                    "bonus_velocidade_movimento",
                    defaults.get("buff_velocidade", 1.0),
                ),
            ),
        )
        self.buff_velocidade_ataque = data.get("bonus_velocidade_ataque", 1.0)
        self.refletir = data.get("refletir", data.get("reflete_dano", 0))
        self.cura_por_segundo = data.get(
            "regen",
            data.get("cura_tick", defaults.get("cura_por_segundo", 0)),
        )
        self.mod_dano_recebido = data.get(
            "dano_recebido_bonus",
            defaults.get("mod_dano_recebido", 1.0),
        )
        self.mod_cura_recebida = defaults.get("mod_cura_recebida", 1.0)
        self.mod_cooldown = (
            0.0 if data.get("sem_cooldown") else defaults.get("mod_cooldown", 1.0)
        )
        self.mod_mana_custo = 0.5 if data.get("custo_mana_metade") else 1.0
        self.lifesteal = data.get("lifesteal", 0.0)
        self.imortal_disponivel = bool(defaults.get("imortal", False))
        self.voo = bool(data.get("voo", False))
        self.imune_ground = bool(data.get("imune_ground", False))
        self.altura_voo = max(0.1, float(data.get("altura_voo", 1.5)))
        self.reflete_projeteis = bool(data.get("reflete_projeteis", False))
        self.reflete_skills = bool(data.get("reflete_skills", False))
        self.reflete_skills_disponivel = self.reflete_skills

        self.perfil_stats = None
        self.modificadores_stats = {}
        if data.get("stats_aleatorios", False):
            perfil = copy.deepcopy(self.rng.choice(PERFIS_MUTACAO))
            self.perfil_stats = perfil.pop("nome")
            self.modificadores_stats = perfil
            self.buff_dano *= perfil["buff_dano"]
            self.buff_velocidade *= perfil["buff_velocidade"]
            self.mod_dano_recebido *= perfil["mod_dano_recebido"]

        self.ativo = True

    def clonar_para(self, novo_alvo):
        """Clona estado restante sem compartilhar a instancia roubada."""
        clone = copy.copy(self)
        clone.alvo = novo_alvo
        clone.dono = novo_alvo
        clone.rng = getattr(novo_alvo, "rng_runtime", random)
        clone.modificadores_stats = dict(self.modificadores_stats)
        clone.ativo = True
        return clone

    def consumir_reflexao_skill(self):
        if not self.ativo or not self.reflete_skills_disponivel:
            return False
        self.reflete_skills_disponivel = False
        return True

    def atualizar(self, dt):
        dt = max(0.0, dt)
        tempo_ativo = min(dt, max(0.0, self.vida))
        self.vida = max(0.0, self.vida - dt)
        
        # Cura contínua
        if self.cura_por_segundo > 0 and tempo_ativo > 0.0:
            self.alvo.receber_cura(self.cura_por_segundo * tempo_ativo)
        
        if self.vida <= 0:
            self.ativo = False

    def consumir_imortalidade(self):
        if not self.ativo or not self.imortal_disponivel:
            return False
        self.imortal_disponivel = False
        self.ativo = False
        self.vida = 0.0
        return True
    
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
        if not self.ativo:
            return

        dt = max(0.0, dt)
        tempo_ativo = min(dt, max(0.0, self.vida))
        self.vida = max(0.0, self.vida - dt)
        self.tick_timer += tempo_ativo

        # Consome todos os ticks completos acumulados. Somente o trecho do
        # frame em que o DoT ainda estava vivo entra no acumulador.
        while self.tick_timer + 1e-9 >= self.tick_interval:
            self.tick_timer = max(0.0, self.tick_timer - self.tick_interval)
            if not self.alvo.morto:
                aplicar_direto = getattr(self.alvo, "aplicar_dano_direto", None)
                if callable(aplicar_direto):
                    aplicar_direto(
                        self.dano_por_tick,
                        compartilhar_link=True,
                        flash_cor=self.cor,
                    )
                else:
                    limitar_letal = getattr(
                        self.alvo,
                        "_limitar_dano_letal_por_imortalidade",
                        None,
                    )
                    dano_tick = (
                        limitar_letal(self.dano_por_tick)
                        if callable(limitar_letal)
                        else self.dano_por_tick
                    )
                    self.alvo.vida -= dano_tick
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
        self._ultimo_ataque_copiado = getattr(dono, "ataque_id", 0)
        
        # Comportamento
        self.raio_agressao = 20.0 if self.copia_caster else 5.0
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

        ataque_copia_pendente = False
        if self.copia_caster:
            ataque_atual = getattr(self.dono, "ataque_id", 0)
            ataque_copia_pendente = ataque_atual != self._ultimo_ataque_copiado
            self._ultimo_ataque_copiado = ataque_atual
        
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

            if ataque_copia_pendente:
                resultados.append({
                    "tipo": "ataque",
                    "alvo": self.alvo,
                    "dano": self._calcular_dano_copiado(),
                    "x": self.x,
                    "y": self.y,
                })

            if dist > self.raio_ataque:
                # Aproxima
                self.x += (dx / dist) * self.velocidade * dt
                self.y += (dy / dist) * self.velocidade * dt
            elif not self.copia_caster and self.cd_timer <= 0:
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

    def _calcular_dano_copiado(self):
        """Replica o dano do ataque básico atual do conjurador."""
        arma = getattr(getattr(self.dono, "dados", None), "arma_obj", None)
        dano_base = float(getattr(arma, "dano", self.dano))
        modificar = getattr(self.dono, "get_dano_modificado", None)
        return modificar(dano_base) if callable(modificar) else dano_base
    
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
        self.tipo_fonte = "trap_skill"
        self.eh_skill = True
        self.eh_projetil = False
        self.ground = bool(data.get("ground", True))
        self.rouba_buff = False
        self.refletido = False
        
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

        anterior = getattr(alvo, "transformacao_ativa", None)
        if anterior is not None and anterior is not self:
            encerrar = getattr(anterior, "encerrar", None)
            if callable(encerrar):
                encerrar()

        # Campos reais consumidos por Lutador. O snapshot permite restaurar
        # exatamente o estado anterior, inclusive quando ele ja tinha buffs.
        self.stats_originais = {
            "mod_velocidade_transformacao": getattr(
                alvo,
                "mod_velocidade_transformacao",
                1.0,
            ),
            "resistencia": getattr(alvo, "resistencia", 0.0),
            "mod_defesa": getattr(alvo, "mod_defesa", 1.0),
            "cor_aura": getattr(alvo, "cor_aura", (255, 255, 255)),
            "intangivel": getattr(alvo, "intangivel", False),
        }

        # Modificadores
        self.bonus_resistencia = data.get("bonus_resistencia", 0)
        self.bonus_velocidade = data.get("bonus_velocidade", 1.0)
        self.intangivel = data.get("intangivel", False)
        self.dano_contato = data.get("dano_contato", 0)

        # Auras
        self.aura_slow = data.get("aura_slow", 1.0)
        self.aura_raio = data.get("aura_raio", 0)

        self.ativo = True
        self._aplicado = False

        self._aplicar_transformacao()
        alvo.transformacao_ativa = self

    def _aplicar_transformacao(self):
        """Aplica uma unica vez os modificadores usados pelo runtime."""
        if self._aplicado:
            return False

        fator_resistencia = max(0.01, 1.0 + float(self.bonus_resistencia))
        self.alvo.mod_velocidade_transformacao = (
            float(self.stats_originais["mod_velocidade_transformacao"])
            * max(0.0, float(self.bonus_velocidade))
        )
        self.alvo.resistencia = (
            float(self.stats_originais["resistencia"]) * fator_resistencia
        )
        self.alvo.mod_defesa = (
            float(self.stats_originais["mod_defesa"]) / fator_resistencia
        )
        self.alvo.cor_aura = self.cor
        self.alvo.intangivel = bool(
            self.stats_originais["intangivel"] or self.intangivel
        )
        self.alvo._transformacao_token = self
        self._aplicado = True
        return True

    def _reverter_transformacao(self):
        """Restaura o snapshot sem desfazer uma transformacao mais nova."""
        if not self._aplicado:
            return False
        if getattr(self.alvo, "_transformacao_token", None) is not self:
            self._aplicado = False
            return False

        for atributo, valor in self.stats_originais.items():
            setattr(self.alvo, atributo, valor)
        self.alvo._transformacao_token = None
        self._aplicado = False
        return True

    def encerrar(self):
        """Encerra de forma idempotente e libera a referencia do lutador."""
        self._reverter_transformacao()
        self.ativo = False
        if getattr(self.alvo, "transformacao_ativa", None) is self:
            self.alvo.transformacao_ativa = None

    def atualizar(self, dt, alvos=None):
        """Atualiza transformacao"""
        resultados = []

        if not self.ativo:
            return resultados
        if getattr(self.alvo, "morto", False):
            self.encerrar()
            return resultados

        tempo_ativo = min(max(0.0, float(dt)), max(0.0, self.vida))
        self.vida = max(0.0, self.vida - tempo_ativo)

        # Dano de contato
        if self.dano_contato > 0 and alvos:
            for alvo in alvos:
                if alvo == self.alvo or getattr(alvo, "morto", False):
                    continue
                dist = math.hypot(alvo.pos[0] - self.alvo.pos[0], 
                                 alvo.pos[1] - self.alvo.pos[1])
                if dist < 1.0:  # Raio de contato
                    resultados.append({
                        "tipo": "contato",
                        "alvo": alvo,
                        "dano": self.dano_contato * tempo_ativo
                    })

        # Aura de slow
        if self.aura_raio > 0 and self.aura_slow < 1.0 and alvos:
            for alvo in alvos:
                if alvo == self.alvo or getattr(alvo, "morto", False):
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
            self.encerrar()

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
        self.tipo_fonte = "channel_skill"
        self.eh_skill = True
        self.eh_projetil = False
        self.ground = False
        self.rouba_buff = False
        self.refletido = False
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
        self.tick_timer = 0.0
        self.tick_interval = max(0.001, float(data.get("tick_interval", 0.1)))

        # Direção do beam (se aplicavel)
        self.angulo = dono.angulo_olhar if hasattr(dono, 'angulo_olhar') else 0

        anterior = getattr(dono, "channel_ativo", None)
        if anterior is not None and anterior is not self:
            interromper = getattr(anterior, "interromper", None)
            if callable(interromper):
                interromper()

        dono.channel_ativo = self
        dono.canalizando = True
        dono.skill_canalizando = nome_skill
        dono.tempo_canalizacao = 0.0
        dono.atacando = False
        dono.usando_skill = False
        if hasattr(dono, "vel"):
            dono.vel[0] = 0.0
            dono.vel[1] = 0.0

    def _processar_tick(self, alvos):
        """Executa um intervalo inteiro; o dano entra pelo ponto canonico."""
        resultados = []

        if self.cura_por_segundo > 0:
            cura = self.cura_por_segundo * self.tick_interval
            receber_cura = getattr(self.dono, "receber_cura", None)
            cura_real = receber_cura(cura) if callable(receber_cura) else 0.0
            resultados.append({
                "tipo": "cura",
                "alvo": self.dono,
                "valor": cura_real,
            })

        if self.dano_por_segundo <= 0 or not alvos:
            return resultados

        for alvo in alvos:
            if alvo == self.dono or getattr(alvo, "morto", False):
                continue

            dx = alvo.pos[0] - self.dono.pos[0]
            dy = alvo.pos[1] - self.dono.pos[1]
            dist = math.hypot(dx, dy)
            if dist >= self.alcance:
                continue

            ang_alvo = math.degrees(math.atan2(dy, dx))
            diff = abs((ang_alvo - self.angulo + 180.0) % 360.0 - 180.0)
            if diff >= 15.0:
                continue

            dano = self.dano_por_segundo * self.tick_interval
            direcao_x = dx / dist if dist > 0.0 else 0.0
            direcao_y = dy / dist if dist > 0.0 else 0.0
            resolver = getattr(alvo, "resolver_impacto", None)
            if callable(resolver):
                impacto = resolver(
                    dano,
                    direcao_x,
                    direcao_y,
                    self.tipo_efeito,
                    atacante=self.dono,
                    ignorar_invencibilidade=True,
                    ignorar_escudo=self.penetra_escudo,
                    metadata_impacto=criar_metadata_impacto(self),
                )
            else:
                tomar_dano = getattr(alvo, "tomar_dano", None)
                impacto = None
                if callable(tomar_dano):
                    try:
                        tomar_dano(
                            dano,
                            direcao_x,
                            direcao_y,
                            self.tipo_efeito,
                            atacante=self.dono,
                            ignorar_invencibilidade=True,
                            ignorar_escudo=self.penetra_escudo,
                            metadata_impacto=criar_metadata_impacto(self),
                        )
                    except TypeError:
                        tomar_dano(
                            dano,
                            direcao_x,
                            direcao_y,
                            self.tipo_efeito,
                            atacante=self.dono,
                        )

            resultados.append({
                "tipo": "impacto",
                "alvo": alvo,
                "dano": getattr(
                    impacto,
                    "dano",
                    getattr(alvo, "ultimo_dano_recebido", 0.0),
                ),
                "efeito": self.tipo_efeito,
                "penetra_escudo": self.penetra_escudo,
                "impacto": impacto,
            })

        return resultados

    def atualizar(self, dt, alvos=None):
        """Atualiza canalizacao"""
        resultados = []

        if not self.ativo:
            return resultados
        if (
            not self.canalizando
            or getattr(self.dono, "morto", False)
            or getattr(self.dono, "channel_ativo", None) is not self
        ):
            self.interromper()
            return resultados

        if hasattr(self.dono, "vel"):
            self.dono.vel[0] = 0.0
            self.dono.vel[1] = 0.0

        tempo_ativo = min(max(0.0, float(dt)), max(0.0, self.vida))
        self.vida = max(0.0, self.vida - tempo_ativo)
        self.tick_timer += tempo_ativo
        self.dono.tempo_canalizacao = (
            float(getattr(self.dono, "tempo_canalizacao", 0.0)) + tempo_ativo
        )

        while self.tick_timer + 1e-12 >= self.tick_interval:
            self.tick_timer -= self.tick_interval
            resultados.extend(self._processar_tick(alvos))

        if self.vida <= 0:
            self.interromper()

        return resultados

    def interromper(self):
        """Interrompe a canalizacao"""
        self.canalizando = False
        self.ativo = False
        channel_atual = getattr(self.dono, "channel_ativo", None)
        if channel_atual is self:
            self.dono.channel_ativo = None
        if channel_atual is self or channel_atual is None:
            self.dono.canalizando = False
            self.dono.skill_canalizando = None
            self.dono.tempo_canalizacao = 0.0


class PortalPair:
    """Par bidirecional com trava por entidade para impedir ping-pong."""

    def __init__(
        self,
        nome_skill,
        ponto_inicial,
        ponto_final,
        dono,
        *,
        duracao=None,
        raio=0.65,
    ):
        data = get_skill_data(nome_skill)
        self.nome = nome_skill
        self.dono = dono
        self.ponto_a = (float(ponto_inicial[0]), float(ponto_inicial[1]))
        self.ponto_b = (float(ponto_final[0]), float(ponto_final[1]))
        self.duracao = float(
            data.get("duracao_portal", 5.0) if duracao is None else duracao
        )
        self.vida = max(0.0, self.duracao)
        self.raio = max(0.05, float(raio))
        self.cor = data.get("cor", (100, 100, 255))
        self.ativo = self.vida > 0.0
        # O conjurador nasce sobre a boca de destino; ele precisa sair do
        # volume antes de poder atravessar o portal de volta.
        self.entidades_bloqueadas = {id(dono)} if dono is not None else set()

    def _dentro(self, entidade, ponto):
        return math.hypot(
            entidade.pos[0] - ponto[0],
            entidade.pos[1] - ponto[1],
        ) <= self.raio

    def atualizar(self, dt, entidades=()):
        if not self.ativo:
            return []
        self.vida = max(0.0, self.vida - max(0.0, float(dt)))
        if self.vida <= 0.0:
            self.ativo = False
            self.entidades_bloqueadas.clear()
            return []

        eventos = []
        for entidade in entidades or ():
            if entidade is None or getattr(entidade, "morto", False):
                continue
            identificador = id(entidade)
            dentro_a = self._dentro(entidade, self.ponto_a)
            dentro_b = self._dentro(entidade, self.ponto_b)
            if identificador in self.entidades_bloqueadas:
                if not dentro_a and not dentro_b:
                    self.entidades_bloqueadas.discard(identificador)
                continue

            destino = None
            origem = None
            if dentro_a:
                origem, destino = self.ponto_a, self.ponto_b
            elif dentro_b:
                origem, destino = self.ponto_b, self.ponto_a
            if destino is None:
                continue

            entidade.pos[0], entidade.pos[1] = destino
            self.entidades_bloqueadas.add(identificador)
            eventos.append({
                "tipo": "portal",
                "entidade": entidade,
                "origem": origem,
                "destino": destino,
            })
        return eventos
