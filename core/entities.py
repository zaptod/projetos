"""
NEURAL FIGHTS - Entidade Lutador
Classe principal do lutador com sistema de combate.
"""

import math
import random
from utils.config import PPM, GRAVIDADE_Z, ATRITO, ALTURA_PADRAO


class Lutador:
    """
    Classe principal do lutador com suporte completo a:
    - Sistema de classes expandido
    - Novos tipos de skills (DASH, BUFF, AREA, BEAM, SUMMON)
    - Efeitos de status (DoT, buffs, debuffs)
    """
    def __init__(self, dados_char, pos_x, pos_y):
        # Importações tardias para evitar circular imports
        from ai import AIBrain
        from core.skills import get_skill_data
        from models import get_class_data
        from core.combat import DotEffect
        from effects.audio import AudioManager
        
        self.dados = dados_char
        self.pos = [pos_x, pos_y]
        self.vel = [0.0, 0.0]
        self.z = 0.0
        self.vel_z = 0.0
        self.raio_fisico = (self.dados.tamanho / 4.0)
        
        # Carrega dados da classe
        self.classe_nome = getattr(self.dados, 'classe', "Guerreiro (Força Bruta)")
        self.class_data = get_class_data(self.classe_nome)
        
        # Status calculados com modificadores de classe
        self.vida_max = self._calcular_vida_max()
        self.vida = self.vida_max
        self.estamina = 100.0
        self.estamina_max = 100.0
        self.mana_max = self._calcular_mana_max()
        self.mana = self.mana_max
        
        # Regeneração baseada na classe
        self.regen_mana_base = self.class_data.get("regen_mana", 3.0)
        
        # Modificadores de classe
        self.mod_dano = self.class_data.get("mod_forca", 1.0)
        self.mod_velocidade = self.class_data.get("mod_velocidade", 1.0)
        self.mod_defesa = 1.0 / self.class_data.get("mod_vida", 1.0)
        
        # Cor de aura da classe
        self.cor_aura = self.class_data.get("cor_aura", (200, 200, 200))
        
        # === SISTEMA DE SKILLS EXPANDIDO ===
        self.skills_arma = []
        self.skills_classe = []
        self.skill_atual_idx = 0
        self.cd_skills = {}
        
        # Carrega skills da arma
        arma = self.dados.arma_obj
        if arma:
            habilidades = getattr(arma, 'habilidades', [])
            if habilidades:
                for hab in habilidades:
                    if isinstance(hab, dict):
                        nome_hab = hab.get("nome", "Nenhuma")
                        custo_hab = hab.get("custo", 0)
                    else:
                        nome_hab = str(hab)
                        custo_hab = getattr(arma, 'custo_mana', 0)
                    
                    skill_data = get_skill_data(nome_hab)
                    if skill_data["tipo"] != "NADA":
                        self.skills_arma.append({
                            "nome": nome_hab,
                            "custo": custo_hab,
                            "data": skill_data
                        })
                        self.cd_skills[nome_hab] = 0.0
            else:
                nome_raw = getattr(arma, 'habilidade', "Nenhuma")
                skill_data = get_skill_data(nome_raw)
                if skill_data["tipo"] != "NADA":
                    custo = getattr(arma, 'custo_mana', skill_data["custo"])
                    self.skills_arma.append({
                        "nome": nome_raw,
                        "custo": custo,
                        "data": skill_data
                    })
                    self.cd_skills[nome_raw] = 0.0
            
            # Carrega dados de raridade da arma
            self.arma_raridade = getattr(arma, 'raridade', 'Comum')
            self.arma_critico = getattr(arma, 'critico', 0.0)
            self.arma_vel_ataque = getattr(arma, 'velocidade_ataque', 1.0)
            self.arma_encantamentos = getattr(arma, 'encantamentos', [])
            self.arma_passiva = getattr(arma, 'passiva', None)
            self.arma_tipo = arma.tipo
        else:
            self.arma_raridade = 'Comum'
            self.arma_critico = 0.0
            self.arma_vel_ataque = 1.0
            self.arma_encantamentos = []
            self.arma_passiva = None
            self.arma_tipo = None
        
        # Carrega skills de afinidade da classe
        for skill_nome in self.class_data.get("skills_afinidade", []):
            skill_data = get_skill_data(skill_nome)
            if skill_data["tipo"] != "NADA":
                self.skills_classe.append({
                    "nome": skill_nome,
                    "custo": skill_data.get("custo", 15),
                    "data": skill_data
                })
                self.cd_skills[skill_nome] = 0.0
        
        # Compatibilidade com código antigo
        self.skill_arma_nome = self.skills_arma[0]["nome"] if self.skills_arma else "Nenhuma"
        self.custo_skill_arma = self.skills_arma[0]["custo"] if self.skills_arma else 0
        self.cd_skill_arma = 0.0
        
        # Buffers para objetos criados
        self.buffer_projeteis = []
        self.buffer_areas = []
        self.buffer_beams = []
        self.buffer_orbes = []
        
        # Efeitos ativos
        self.buffs_ativos = []
        self.dots_ativos = []

        # Estado de combate
        self.morto = False
        self.invencivel_timer = 0.0
        self.flash_timer = 0.0
        self.flash_cor = (255, 255, 255)  # Cor do flash de dano
        self.stun_timer = 0.0
        self.slow_timer = 0.0
        self.slow_fator = 1.0
        self.modo_adrenalina = False
        
        # === SISTEMA DE CHANNELING v8.0 (Para Magos) ===
        self.canalizando = False
        self.skill_canalizando = None
        self.tempo_canalizacao = 0.0
        self.usando_skill = False  # Flag para skills em geral
        
        # Animação e visual
        self.angulo_olhar = 0.0
        self.angulo_arma_visual = 0.0
        self.cooldown_ataque = 0.0
        self.timer_animacao = 0.0
        self.atacando = False
        self.modo_ataque_aereo = False
        
        # === SISTEMA DE PREVENÇÃO DE MULTI-HIT v10.1 ===
        # Cada ataque recebe um ID único para evitar múltiplos hits no mesmo swing
        self.ataque_id = 0  # Incrementa a cada novo ataque
        self.alvos_atingidos_neste_ataque = set()  # IDs dos alvos já atingidos neste ataque
        
        # === SISTEMA DE ANIMAÇÃO DE ARMAS v2.0 ===
        self.weapon_anim_scale = 1.0      # Escala da arma (squash/stretch)
        self.weapon_anim_shake = (0, 0)   # Offset de shake no impacto
        self.weapon_trail_positions = []  # Posições do trail da arma
        self.arma_droppada_pos = None
        self.arma_droppada_ang = 0
        self.fator_escala = self.dados.tamanho / ALTURA_PADRAO
        self.alcance_ideal = 1.5
        
        # Efeitos visuais temporários
        self.dash_trail = []
        self.aura_pulso = 0.0
        
        # Sistema de dash evasivo v7.0
        self.dash_timer = 0.0
        self.pos_historico = []

        # IA
        self.brain = AIBrain(self)

    def _calcular_vida_max(self):
        """Calcula vida máxima com modificadores"""
        base = 80.0 + (self.dados.resistencia * 5)  # Vida reduzida para lutas mais rápidas
        return base * self.class_data.get("mod_vida", 1.0)
    
    def _calcular_mana_max(self):
        """Calcula mana máxima com modificadores"""
        base = 50.0 + (getattr(self.dados, 'mana', 0) * 10.0)
        return base * self.class_data.get("mod_mana", 1.0)

    def trocar_skill(self):
        """Troca para a próxima skill disponível"""
        if len(self.skills_arma) <= 1:
            return
        
        self.skill_atual_idx = (self.skill_atual_idx + 1) % len(self.skills_arma)
        skill = self.skills_arma[self.skill_atual_idx]
        self.skill_arma_nome = skill["nome"]
        self.custo_skill_arma = skill["custo"]
    
    def get_skill_atual(self):
        """Retorna dados da skill atualmente selecionada"""
        if not self.skills_arma:
            return None
        return self.skills_arma[self.skill_atual_idx]
    
    def calcular_dano_ataque(self, dano_base):
        """Calcula dano final com crítico e encantamentos"""
        from models import ENCANTAMENTOS
        
        dano = dano_base * self.mod_dano
        
        critico_chance = self.arma_critico
        if "Assassino" in self.classe_nome:
            critico_chance += 0.20  # Reduzido de 0.25
        
        is_critico = random.random() < critico_chance
        if is_critico:
            dano *= 1.5  # Reduzido de 2.0
        
        for enc_nome in self.arma_encantamentos:
            if enc_nome in ENCANTAMENTOS:
                enc = ENCANTAMENTOS[enc_nome]
                dano += enc.get("dano_bonus", 0)
        
        return dano, is_critico
    
    def aplicar_efeitos_encantamento(self, alvo):
        """Aplica efeitos de encantamentos no alvo"""
        from models import ENCANTAMENTOS
        from core.combat import DotEffect
        
        for enc_nome in self.arma_encantamentos:
            if enc_nome not in ENCANTAMENTOS:
                continue
            
            enc = ENCANTAMENTOS[enc_nome]
            efeito = enc.get("efeito")
            
            if random.random() > 0.5:
                continue
            
            if efeito == "burn":
                dot = DotEffect("Queimadura", alvo, dano_tick=5, duracao=3.0)
                alvo.dots_ativos.append(dot)
            elif efeito == "slow":
                alvo.slow_timer = 2.0
                alvo.slow_fator = 0.5
            elif efeito == "poison":
                dot = DotEffect("Veneno", alvo, dano_tick=enc.get("dot_dano", 3), 
                               duracao=enc.get("dot_duracao", 5.0))
                alvo.dots_ativos.append(dot)
            elif efeito == "lifesteal":
                percent = enc.get("lifesteal_percent", 10) / 100.0
                cura = alvo.vida * 0.1 * percent
                self.vida = min(self.vida_max, self.vida + cura)

    def usar_skill_arma(self, skill_idx=None):
        """Usa a skill equipada na arma"""
        from core.combat import Projetil, AreaEffect, Beam, Buff, Summon, Trap, Transform, Channel
        from effects.audio import AudioManager
        
        if skill_idx is not None and skill_idx < len(self.skills_arma):
            skill_info = self.skills_arma[skill_idx]
        elif self.skills_arma:
            skill_info = self.skills_arma[self.skill_atual_idx]
        else:
            return False
        
        nome_skill = skill_info["nome"]
        if nome_skill == "Nenhuma":
            return False
        
        if self.cd_skills.get(nome_skill, 0) > 0:
            return False
        
        data = skill_info["data"]
        tipo = data.get("tipo", "NADA")
        
        custo_real = skill_info["custo"]
        if "Mago" in self.classe_nome:
            custo_real *= 0.8
        
        if self.arma_passiva and self.arma_passiva.get("efeito") == "no_mana_cost":
            chance = self.arma_passiva.get("valor", 0) / 100.0
            if random.random() < chance:
                custo_real = 0
        
        if self.mana < custo_real:
            return False
        
        self.mana -= custo_real
        
        cd = data["cooldown"]
        if self.arma_passiva and self.arma_passiva.get("efeito") == "cooldown":
            cd *= (1 - self.arma_passiva.get("valor", 0) / 100.0)
        
        self.cd_skills[nome_skill] = cd
        self.cd_skill_arma = cd
        
        rad = math.radians(self.angulo_olhar)
        spawn_x = self.pos[0] + math.cos(rad) * 0.6
        spawn_y = self.pos[1] + math.sin(rad) * 0.6
        
        if tipo == "PROJETIL":
            # === ÁUDIO v10.0 - SOM DE CAST DE PROJÉTIL ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("PROJETIL", nome_skill, self.pos[0], phase="cast")
            
            multi = data.get("multi_shot", 1)
            if multi > 1:
                spread = 30
                for i in range(multi):
                    ang_offset = -spread/2 + (spread / (multi-1)) * i
                    p = Projetil(nome_skill, spawn_x, spawn_y, self.angulo_olhar + ang_offset, self)
                    self.buffer_projeteis.append(p)
            else:
                p = Projetil(nome_skill, spawn_x, spawn_y, self.angulo_olhar, self)
                self.buffer_projeteis.append(p)
            
            if data["dano"] > 20:
                self.vel[0] -= math.cos(rad) * 5.0
                self.vel[1] -= math.sin(rad) * 5.0
        
        elif tipo == "AREA":
            # === ÁUDIO v10.0 - SOM DE ÁREA ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("AREA", nome_skill, self.pos[0], phase="cast")
            
            area = AreaEffect(nome_skill, self.pos[0], self.pos[1], self)
            self.buffer_areas.append(area)
        
        elif tipo == "DASH":
            # === ÁUDIO v10.0 - SOM DE DASH ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("DASH", nome_skill, self.pos[0], phase="cast")
            
            dist = data.get("distancia", 4.0)
            dano = data.get("dano", 0)
            
            self.pos[0] += math.cos(rad) * dist
            self.pos[1] += math.sin(rad) * dist
            
            self.dash_timer = 0.25
            
            for i in range(5):
                self.dash_trail.append((
                    self.pos[0] - math.cos(rad) * dist * (i/5),
                    self.pos[1] - math.sin(rad) * dist * (i/5),
                    1.0 - i*0.2
                ))
            
            if dano > 0:
                area = AreaEffect(nome_skill, self.pos[0], self.pos[1], self)
                area.dano = dano
                area.raio = 1.5
                self.buffer_areas.append(area)
            
            if data.get("invencivel"):
                self.invencivel_timer = 0.3
        
        elif tipo == "BUFF":
            # === ÁUDIO v10.0 - SOM DE BUFF ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("BUFF", nome_skill, self.pos[0], phase="cast")
            
            if data.get("cura"):
                self.vida = min(self.vida_max, self.vida + data["cura"])
            
            buff = Buff(nome_skill, self)
            self.buffs_ativos.append(buff)
        
        elif tipo == "BEAM":
            # === ÁUDIO v10.0 - SOM DE BEAM ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("BEAM", nome_skill, self.pos[0], phase="cast")
            
            alcance = data.get("alcance", 8.0)
            end_x = self.pos[0] + math.cos(rad) * alcance
            end_y = self.pos[1] + math.sin(rad) * alcance
            
            beam = Beam(nome_skill, self.pos[0], self.pos[1], end_x, end_y, self)
            self.buffer_beams.append(beam)
        
        # === TIPOS ADICIONAIS (v2.0) ===
        elif tipo == "SUMMON":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("SUMMON", nome_skill, self.pos[0], phase="cast")
            
            summon_x = self.pos[0] + math.cos(rad) * 1.5
            summon_y = self.pos[1] + math.sin(rad) * 1.5
            
            summon = Summon(nome_skill, summon_x, summon_y, self)
            if not hasattr(self, 'buffer_summons'):
                self.buffer_summons = []
            self.buffer_summons.append(summon)
        
        elif tipo == "TRAP":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("TRAP", nome_skill, self.pos[0], phase="cast")
            
            trap_x = self.pos[0] + math.cos(rad) * 2.0
            trap_y = self.pos[1] + math.sin(rad) * 2.0
            
            trap = Trap(nome_skill, trap_x, trap_y, self)
            if not hasattr(self, 'buffer_traps'):
                self.buffer_traps = []
            self.buffer_traps.append(trap)
        
        elif tipo == "TRANSFORM":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("TRANSFORM", nome_skill, self.pos[0], phase="cast")
            
            transform = Transform(nome_skill, self)
            self.transformacao_ativa = transform
        
        elif tipo == "CHANNEL":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("CHANNEL", nome_skill, self.pos[0], phase="cast")
            
            channel = Channel(nome_skill, self)
            if not hasattr(self, 'buffer_channels'):
                self.buffer_channels = []
            self.buffer_channels.append(channel)
        
        return True

    def usar_skill_classe(self, skill_nome):
        """Usa uma skill de classe específica"""
        from core.combat import Projetil, AreaEffect, Beam, Buff, Summon, Trap, Transform, Channel
        from effects.audio import AudioManager
        
        skill_info = None
        for sk in self.skills_classe:
            if sk["nome"] == skill_nome:
                skill_info = sk
                break
        
        if not skill_info:
            return False
        
        if self.cd_skills.get(skill_nome, 0) > 0:
            return False
        
        data = skill_info["data"]
        tipo = data.get("tipo", "NADA")
        custo = skill_info["custo"]
        
        if "Mago" in self.classe_nome:
            custo *= 0.8
        
        # Custo em vida (Pacto de Sangue, Sacrifício)
        custo_vida = data.get("custo_vida", 0) or data.get("custo_vida_percent", 0) * self.vida_max
        if custo_vida > 0:
            if self.vida <= custo_vida:
                return False  # Não pode usar se morreria
            self.vida -= custo_vida
        
        if self.mana < custo:
            return False
        
        self.mana -= custo
        
        cd = data.get("cooldown", 5.0)
        self.cd_skills[skill_nome] = cd
        
        rad = math.radians(self.angulo_olhar)
        spawn_x = self.pos[0] + math.cos(rad) * 0.6
        spawn_y = self.pos[1] + math.sin(rad) * 0.6
        
        if tipo == "PROJETIL":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("PROJETIL", skill_nome, self.pos[0], phase="cast")
            
            multi = data.get("multi_shot", 1)
            if multi > 1:
                spread = 30
                for i in range(multi):
                    ang_offset = -spread/2 + (spread / (multi-1)) * i
                    p = Projetil(skill_nome, spawn_x, spawn_y, self.angulo_olhar + ang_offset, self)
                    self.buffer_projeteis.append(p)
            else:
                p = Projetil(skill_nome, spawn_x, spawn_y, self.angulo_olhar, self)
                self.buffer_projeteis.append(p)
        
        elif tipo == "AREA":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("AREA", skill_nome, self.pos[0], phase="cast")
            
            area = AreaEffect(skill_nome, self.pos[0], self.pos[1], self)
            self.buffer_areas.append(area)
        
        elif tipo == "DASH":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("DASH", skill_nome, self.pos[0], phase="cast")
            
            dist = data.get("distancia", 4.0)
            dano = data.get("dano", 0)
            
            self.pos[0] += math.cos(rad) * dist
            self.pos[1] += math.sin(rad) * dist
            
            for i in range(5):
                self.dash_trail.append((
                    self.pos[0] - math.cos(rad) * dist * (i/5),
                    self.pos[1] - math.sin(rad) * dist * (i/5),
                    1.0 - i*0.2
                ))
            
            if dano > 0:
                area = AreaEffect(skill_nome, self.pos[0], self.pos[1], self)
                area.dano = dano
                area.raio = 1.5
                self.buffer_areas.append(area)
            
            if data.get("invencivel"):
                self.invencivel_timer = 0.3
        
        elif tipo == "BUFF":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("BUFF", skill_nome, self.pos[0], phase="cast")
            
            if data.get("cura"):
                self.vida = min(self.vida_max, self.vida + data["cura"])
            
            buff = Buff(skill_nome, self)
            self.buffs_ativos.append(buff)
        
        elif tipo == "BEAM":
            # === ÁUDIO v10.0 - SOM DE SKILL DE CLASSE ===
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("BEAM", skill_nome, self.pos[0], phase="cast")
            
            alcance = data.get("alcance", 8.0)
            end_x = self.pos[0] + math.cos(rad) * alcance
            end_y = self.pos[1] + math.sin(rad) * alcance
            
            beam = Beam(skill_nome, self.pos[0], self.pos[1], end_x, end_y, self)
            self.buffer_beams.append(beam)
        
        # === NOVOS TIPOS v2.0 ===
        elif tipo == "SUMMON":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("SUMMON", skill_nome, self.pos[0], phase="cast")
            
            # Spawn na frente do caster
            summon_x = self.pos[0] + math.cos(rad) * 1.5
            summon_y = self.pos[1] + math.sin(rad) * 1.5
            
            summon = Summon(skill_nome, summon_x, summon_y, self)
            if not hasattr(self, 'buffer_summons'):
                self.buffer_summons = []
            self.buffer_summons.append(summon)
        
        elif tipo == "TRAP":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("TRAP", skill_nome, self.pos[0], phase="cast")
            
            # Spawn na frente do caster
            trap_x = self.pos[0] + math.cos(rad) * 2.0
            trap_y = self.pos[1] + math.sin(rad) * 2.0
            
            trap = Trap(skill_nome, trap_x, trap_y, self)
            if not hasattr(self, 'buffer_traps'):
                self.buffer_traps = []
            self.buffer_traps.append(trap)
        
        elif tipo == "TRANSFORM":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("TRANSFORM", skill_nome, self.pos[0], phase="cast")
            
            transform = Transform(skill_nome, self)
            if not hasattr(self, 'transformacao_ativa'):
                self.transformacao_ativa = None
            self.transformacao_ativa = transform
        
        elif tipo == "CHANNEL":
            audio = AudioManager.get_instance()
            if audio:
                audio.play_skill("CHANNEL", skill_nome, self.pos[0], phase="cast")
            
            channel = Channel(skill_nome, self)
            if not hasattr(self, 'channel_ativo'):
                self.channel_ativo = None
            self.channel_ativo = channel
        
        return True

    def update(self, dt, inimigo):
        """Atualiza estado do lutador"""
        from core.physics import normalizar_angulo
        
        if self.invencivel_timer > 0:
            self.invencivel_timer -= dt
        if self.flash_timer > 0:
            self.flash_timer -= dt
        if self.stun_timer > 0:
            self.stun_timer -= dt
        if self.cd_skill_arma > 0:
            self.cd_skill_arma -= dt
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_fator = 1.0
        
        for skill_nome in list(self.cd_skills.keys()):
            if self.cd_skills[skill_nome] > 0:
                self.cd_skills[skill_nome] -= dt

        self._atualizar_buffs(dt)
        self._atualizar_dots(dt)
        self._atualizar_dash_trail(dt)
        self._atualizar_orbes(dt)
        
        if self.dash_timer > 0:
            self.dash_timer -= dt
        
        self.pos_historico.append((self.pos[0], self.pos[1]))
        if len(self.pos_historico) > 15:
            self.pos_historico.pop(0)
        
        self.aura_pulso += dt * 3
        if self.aura_pulso > math.pi * 2:
            self.aura_pulso = 0

        if self.morto:
            self.aplicar_fisica(dt)
            return

        mana_regen = self.regen_mana_base
        if "Mago" in self.classe_nome:
            mana_regen *= 1.5
        self.mana = min(self.mana_max, self.mana + mana_regen * dt)
        
        if "Paladino" in self.classe_nome:
            self.vida = min(self.vida_max, self.vida + self.vida_max * 0.005 * dt)  # Reduzido de 2% para 0.5%
        
        dx = inimigo.pos[0] - self.pos[0]
        dy = inimigo.pos[1] - self.pos[1]
        distancia = math.hypot(dx, dy)
        angulo_alvo = math.degrees(math.atan2(dy, dx))
        diff = normalizar_angulo(angulo_alvo - self.angulo_olhar)
        
        vel_giro = 20.0 if "Assassino" in self.classe_nome or "Ninja" in self.classe_nome else 10.0
        self.angulo_olhar += diff * vel_giro * dt

        if self.stun_timer <= 0 and not inimigo.morto:
            # Só processa IA se tiver brain (não em modo manual)
            if self.brain is not None:
                self.brain.processar(dt, distancia, inimigo)
                self.executar_movimento(dt, distancia)
                self.executar_ataques(dt, distancia, inimigo)

        self.aplicar_fisica(dt)

    def _atualizar_buffs(self, dt):
        """Atualiza buffs ativos"""
        for buff in self.buffs_ativos[:]:
            buff.atualizar(dt)
            if not buff.ativo:
                self.buffs_ativos.remove(buff)
    
    def _atualizar_dots(self, dt):
        """Atualiza DoTs ativos"""
        for dot in self.dots_ativos[:]:
            dot.atualizar(dt)
            if not dot.ativo:
                self.dots_ativos.remove(dot)
    
    def _atualizar_dash_trail(self, dt):
        """Fade do trail de dash"""
        for i, (x, y, alpha) in enumerate(self.dash_trail):
            self.dash_trail[i] = (x, y, alpha - dt * 3)
        self.dash_trail = [(x, y, a) for x, y, a in self.dash_trail if a > 0]

    def _atualizar_orbes(self, dt):
        """Atualiza orbes mágicos e remove os inativos"""
        for orbe in self.buffer_orbes:
            orbe.atualizar(dt)
        self.buffer_orbes = [o for o in self.buffer_orbes if o.ativo]

    def aplicar_fisica(self, dt):
        """Aplica física de movimento"""
        vel_mult = self.slow_fator * self.mod_velocidade
        
        if self.z > 0 or self.vel_z > 0:
            self.vel_z -= GRAVIDADE_Z * dt
            self.z += self.vel_z * dt
            if self.z < 0:
                self.z = 0
                self.vel_z = 0
        
        fr = ATRITO if self.z == 0 else ATRITO * 0.2
        self.vel[0] -= self.vel[0] * fr * dt
        self.vel[1] -= self.vel[1] * fr * dt
        self.pos[0] += self.vel[0] * vel_mult * dt
        self.pos[1] += self.vel[1] * vel_mult * dt

    def executar_movimento(self, dt, distancia):
        """Executa movimento baseado na ação da IA - v8.0 com comportamento humano"""
        acao = self.brain.acao_atual
        acc = 45.0 * self.mod_velocidade
        if self.modo_adrenalina:
            acc = 70.0 * self.mod_velocidade
        
        for buff in self.buffs_ativos:
            acc *= buff.buff_velocidade
        
        # v8.0: Aplica variação humana na aceleração
        if hasattr(self.brain, 'ritmo_combate'):
            acc *= self.brain.ritmo_combate
        
        # v8.0: Momentum afeta velocidade
        if hasattr(self.brain, 'momentum'):
            if self.brain.momentum > 0.3:
                acc *= 1.0 + self.brain.momentum * 0.15
            elif self.brain.momentum < -0.3:
                acc *= 1.0 + self.brain.momentum * 0.1  # Diminui menos quando perdendo
        
        mx, my = 0, 0
        rad = math.radians(self.angulo_olhar)
        
        if acao in ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "APROXIMAR", "CONTRA_ATAQUE", "PRESSIONAR"]:
            mx = math.cos(rad)
            my = math.sin(rad)
            mult = {
                "MATAR": 1.0, "ESMAGAR": 0.85, "ATAQUE_RAPIDO": 1.25,
                "APROXIMAR": 1.0, "CONTRA_ATAQUE": 1.4, "PRESSIONAR": 1.1
            }.get(acao, 1.0)
            mx *= mult
            my *= mult
            
            # v8.0: Micro-ajustes durante ataques para parecer mais humano
            if hasattr(self.brain, 'micro_ajustes'):
                mx += random.uniform(-0.05, 0.05)
                my += random.uniform(-0.05, 0.05)
            
        elif acao == "COMBATE":
            mx = math.cos(rad) * 0.6
            my = math.sin(rad) * 0.6
            # v8.0: Mais variação no combate
            chance_strafe = 0.35 if "ESPACAMENTO_MESTRE" in self.brain.tracos else 0.3
            if random.random() < chance_strafe:
                strafe_rad = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
                strafe_mult = random.uniform(0.25, 0.4)
                mx += math.cos(strafe_rad) * strafe_mult
                my += math.sin(strafe_rad) * strafe_mult
                
        elif acao in ["RECUAR", "FUGIR"]:
            mx = -math.cos(rad)
            my = -math.sin(rad)
            if acao == "FUGIR":
                mx *= 1.3
                my *= 1.3
            # v8.0: Desvio diagonal ao fugir para parecer mais esperto
            if random.random() < 0.3:
                lateral = random.choice([-1, 1]) * self.brain.dir_circular
                rad_lat = math.radians(self.angulo_olhar + (30 * lateral))
                mx += math.cos(rad_lat) * 0.3
                my += math.sin(rad_lat) * 0.3
        
        elif acao == "DESVIO":
            # v8.0: Nova ação de desvio mais dinâmica
            rad_lat = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
            mx = math.cos(rad_lat) * 1.2
            my = math.sin(rad_lat) * 1.2
            # Adiciona um pouco de recuo
            mx -= math.cos(rad) * 0.3
            my -= math.sin(rad) * 0.3
                
        elif acao == "CIRCULAR":
            rad_lat = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
            mx = math.cos(rad_lat) * 0.85
            my = math.sin(rad_lat) * 0.85
            # v8.0: Ajuste de distância enquanto circula
            if distancia < 2.5:
                mx -= math.cos(rad) * 0.3  # Afasta um pouco
                my -= math.sin(rad) * 0.3
            elif distancia > 4.0:
                mx += math.cos(rad) * 0.2  # Aproxima um pouco
                my += math.sin(rad) * 0.2
            else:
                mx += math.cos(rad) * 0.25
                my += math.sin(rad) * 0.25
            
        elif acao == "FLANQUEAR":
            # v8.0: Flanqueio mais dinâmico
            angulo_flank = 50 + random.uniform(-10, 10)  # Variação humana
            rad_f = math.radians(self.angulo_olhar + (angulo_flank * self.brain.dir_circular))
            mx = math.cos(rad_f)
            my = math.sin(rad_f)
            
        elif acao == "APROXIMAR_LENTO":
            mx = math.cos(rad) * 0.55
            my = math.sin(rad) * 0.55
            # v8.0: Pequenos movimentos laterais ao aproximar
            if random.random() < 0.2:
                rad_lat = math.radians(self.angulo_olhar + (90 * random.choice([-1, 1])))
                mx += math.cos(rad_lat) * 0.15
                my += math.sin(rad_lat) * 0.15
            
        elif acao == "POKE":
            # v8.0: Poke mais inteligente
            if random.random() < 0.6:
                mx = math.cos(rad) * 0.8
                my = math.sin(rad) * 0.8
            else:
                # Recua depois do poke
                mx = -math.cos(rad) * 0.4
                my = -math.sin(rad) * 0.4
                
        elif acao == "BLOQUEAR":
            if random.random() < 0.4 and distancia > 2.5:
                strafe_rad = math.radians(self.angulo_olhar + (90 * self.brain.dir_circular))
                mx = math.cos(strafe_rad) * 0.2
                my = math.sin(strafe_rad) * 0.2
        
        elif acao == "ATAQUE_AEREO":
            mx = math.cos(rad) * 0.8
            my = math.sin(rad) * 0.8
        
        # v8.0: Nova ação - pressionar continuamente
        elif acao == "PRESSIONAR_CONTINUO":
            mx = math.cos(rad) * 1.1
            my = math.sin(rad) * 1.1
            # Pequenos ajustes laterais
            if random.random() < 0.25:
                rad_lat = math.radians(self.angulo_olhar + (30 * self.brain.dir_circular))
                mx += math.cos(rad_lat) * 0.2
                my += math.sin(rad_lat) * 0.2
            
        # Sistema de pulos
        if "SALTADOR" in self.brain.tracos and self.z == 0:
            chance_pulo = 0.08
            if distancia < 3.0:
                chance_pulo = 0.12
            if acao in ["RECUAR", "FUGIR"]:
                chance_pulo = 0.15
            if random.random() < chance_pulo:
                self.vel_z = random.uniform(10.0, 14.0)
        
        elif acao in ["RECUAR", "FUGIR"] and self.z == 0:
            chance = 0.03
            if self.brain is not None and self.brain.medo > 0.5:
                chance = 0.06
            if random.random() < chance:
                self.vel_z = random.uniform(9.0, 12.0)
        
        # v8.0: Pulo ofensivo mais inteligente
        ofensivos = ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "CONTRA_ATAQUE"]
        if acao in ofensivos and 3.5 < distancia < 7.0 and self.z == 0:
            chance = 0.025
            if "ACROBATA" in self.brain.tracos:
                chance = 0.05
            if random.random() < chance:
                self.vel_z = random.uniform(12.0, 15.0)
                self.modo_ataque_aereo = True
        
        if self.z == 0 and distancia < 5.0 and random.random() < 0.005:
            self.vel_z = random.uniform(8.0, 11.0)

        self.vel[0] += mx * acc * dt
        self.vel[1] += my * acc * dt

    def executar_ataques(self, dt, distancia, inimigo):
        """Executa ataques físicos com sistema de animação aprimorado v2.0"""
        from core.combat import ArmaProjetil, FlechaProjetil, OrbeMagico
        from effects.weapon_animations import get_weapon_animation_manager, WEAPON_PROFILES
        
        self.cooldown_ataque -= dt
        
        arma_tipo = self.dados.arma_obj.tipo if self.dados.arma_obj else "Reta"
        is_orbital = self.dados.arma_obj and "Orbital" in arma_tipo
        
        # Obtém gerenciador de animações
        anim_manager = get_weapon_animation_manager()
        
        # Calcula posição da ponta da arma para trail
        rad = math.radians(self.angulo_olhar)
        tip_dist = self.raio_fisico * 2.5
        weapon_tip = (
            self.pos[0] + math.cos(rad) * tip_dist,
            self.pos[1] + math.sin(rad) * tip_dist
        )
        
        # Atualiza animação
        transform = anim_manager.get_weapon_transform(
            id(self), arma_tipo, self.angulo_olhar, weapon_tip, dt
        )
        
        # Aplica transformações
        self.weapon_anim_scale = transform["scale"]
        self.weapon_anim_shake = transform["shake"]
        self.weapon_trail_positions = transform["trail_positions"]
        
        # Orbital: sempre gira
        if is_orbital:
            spd = 200
            if self.brain.acao_atual in ["MATAR", "BLOQUEAR", "COMBATE"] or distancia < 2.5:
                spd = 1000
            self.angulo_arma_visual += spd * dt
        elif self.atacando:
            # Usa novo sistema de animação
            self.timer_animacao -= dt
            
            # Obtém perfil da arma
            profile = WEAPON_PROFILES.get(arma_tipo, WEAPON_PROFILES["Reta"])
            
            if self.timer_animacao <= 0:
                self.atacando = False
                self.angulo_arma_visual = self.angulo_olhar
            else:
                # Aplica offset do animador
                self.angulo_arma_visual = self.angulo_olhar + transform["angle_offset"]
        else:
            # Animação idle
            self.angulo_arma_visual = self.angulo_olhar + transform["angle_offset"]

        if not self.atacando and not is_orbital and self.cooldown_ataque <= 0:
            acoes_ofensivas = ["MATAR", "ESMAGAR", "COMBATE", "ATAQUE_RAPIDO", "FLANQUEAR", "POKE", "PRESSIONAR", "CONTRA_ATAQUE"]
            deve_atacar = False
            
            # Calcula alcance de ataque usando mesmo método que brain.py
            try:
                from core.hitbox import HITBOX_PROFILES
                from utils.config import PPM
                profile_hitbox = HITBOX_PROFILES.get(arma_tipo, HITBOX_PROFILES.get("Reta", {}))
                range_mult = profile_hitbox.get("range_mult", 2.0)
                alcance_base = self.raio_fisico * range_mult
                
                # Adiciona componente da arma como brain.py faz
                arma = self.dados.arma_obj if self.dados else None
                if arma_tipo == "Dupla":
                    comp = getattr(arma, 'comp_lamina', 55) / PPM if arma else 1.1
                    alcance_ataque = alcance_base + comp * 0.4
                elif arma_tipo == "Reta":
                    comp_total = (getattr(arma, 'comp_cabo', 20) + getattr(arma, 'comp_lamina', 40)) / PPM if arma else 1.2
                    alcance_ataque = alcance_base + comp_total * 0.3
                else:
                    alcance_ataque = alcance_base
                
                # Margem de 30% para garantir ataque quando IA decide
                alcance_ataque *= 1.3
            except:
                alcance_ataque = self.raio_fisico * 3.0  # Fallback generoso
            
            # Ajustes APENAS para armas ranged (não sobrescreve corpo-a-corpo!)
            if arma_tipo == "Arco":
                alcance_ataque = 20.0  # Arco: MUITO alcance (20 metros!)
            elif arma_tipo == "Arremesso":
                alcance_ataque = 12.0  # Arremesso: alcance médio
            elif arma_tipo == "Mágica":
                alcance_ataque = 8.0
            # Para armas corpo-a-corpo (incluindo Dupla), usa o cálculo baseado no profile
            
            # Verifica se deve atacar
            if self.brain.acao_atual in acoes_ofensivas and distancia < alcance_ataque:
                deve_atacar = True
            if self.brain.acao_atual == "POKE" and abs(distancia - self.alcance_ideal) < 1.5:
                deve_atacar = True
            if self.modo_ataque_aereo and distancia < 2.0:
                deve_atacar = True
            
            # === ARMAS RANGED: atacam mesmo recuando/fugindo! ===
            if arma_tipo in ["Arremesso", "Arco"] and distancia < alcance_ataque:
                # Arqueiros atiram mesmo fugindo (desde que não esteja em cooldown)
                if self.brain.acao_atual in ["RECUAR", "FUGIR", "APROXIMAR"]:
                    if random.random() < 0.7:  # 70% chance de atirar mesmo recuando
                        deve_atacar = True

            if deve_atacar and abs(self.z - inimigo.z) < 1.5:
                self.atacando = True
                
                # === v10.1: Novo ataque = novo ID, limpa alvos atingidos ===
                self.ataque_id += 1
                self.alvos_atingidos_neste_ataque.clear()
                
                # Usa duração do perfil da arma
                profile = WEAPON_PROFILES.get(arma_tipo, WEAPON_PROFILES["Reta"])
                self.timer_animacao = profile.total_time
                
                # Inicia animação no gerenciador
                anim_manager.start_attack(id(self), arma_tipo, tuple(self.pos), self.angulo_olhar)
                
                if arma_tipo == "Arremesso":
                    self._disparar_arremesso(inimigo)
                elif arma_tipo == "Arco":
                    self._disparar_flecha(inimigo)
                elif arma_tipo == "Mágica":
                    self._disparar_orbes(inimigo)
                
                base_cd = 0.5 + random.random() * 0.5
                if arma_tipo in ["Arremesso", "Arco"]:
                    base_cd = 0.8 + random.random() * 0.4
                elif arma_tipo == "Mágica":
                    base_cd = 1.0 + random.random() * 0.5
                if "Assassino" in self.classe_nome or "Ninja" in self.classe_nome:
                    base_cd *= 0.7
                elif "Colosso" in self.brain.arquetipo:
                    base_cd *= 1.3
                self.cooldown_ataque = base_cd
    
    def _disparar_arremesso(self, alvo):
        """Dispara projéteis de arma de arremesso"""
        from core.combat import ArmaProjetil
        
        arma = self.dados.arma_obj
        if not arma:
            return
        
        qtd = int(getattr(arma, 'quantidade', 3))
        tam = getattr(arma, 'tamanho_projetil', 15) / PPM
        dano_por_proj = arma.dano / max(qtd, 1)
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (200, 200, 200)
        
        nome_lower = arma.nome.lower()
        if "shuriken" in nome_lower:
            tipo_proj = "shuriken"
            vel = 18.0
        elif "chakram" in nome_lower:
            tipo_proj = "chakram"
            vel = 14.0
        else:
            tipo_proj = "faca"
            vel = 16.0
        
        rad_base = math.radians(self.angulo_olhar)
        spread = 25 if qtd > 1 else 0
        
        for i in range(qtd):
            if qtd > 1:
                offset = -spread/2 + (spread / (qtd-1)) * i
            else:
                offset = 0
            
            ang = self.angulo_olhar + offset
            # Spawn BEM FORA do corpo do lutador
            spawn_dist = self.raio_fisico + 0.5
            spawn_x = self.pos[0] + math.cos(math.radians(ang)) * spawn_dist
            spawn_y = self.pos[1] + math.sin(math.radians(ang)) * spawn_dist
            
            proj = ArmaProjetil(
                tipo=tipo_proj,
                x=spawn_x, y=spawn_y,
                angulo=ang,
                dono=self,
                dano=dano_por_proj * (self.dados.forca / 2.0),
                velocidade=vel,
                tamanho=tam,
                cor=cor
            )
            self.buffer_projeteis.append(proj)
    
    def _disparar_flecha(self, alvo):
        """Dispara flecha do arco - DIRETA E PRECISA"""
        from core.combat import FlechaProjetil
        
        arma = self.dados.arma_obj
        if not arma:
            return
        
        dano = arma.dano * (self.dados.forca / 2.0 + 0.5)  # Dano base melhor
        forca = getattr(arma, 'forca_arco', 1.0)
        # Normaliza força do arco (valores no JSON são 5-50, queremos 0.5-2.0)
        forca_normalizada = max(0.5, min(2.0, forca / 25.0))
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (139, 90, 43)
        
        # === MIRA DIRETA NO ALVO (sem gravidade, sem complicação) ===
        dx = alvo.pos[0] - self.pos[0]
        dy = alvo.pos[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        
        if dist > 0.1:
            # Velocidade da flecha
            vel_flecha = 35.0 + forca_normalizada * 20.0
            tempo_voo = dist / vel_flecha
            
            # Predição simples: 70% da velocidade do alvo
            alvo_futuro_x = alvo.pos[0] + alvo.vel[0] * tempo_voo * 0.7
            alvo_futuro_y = alvo.pos[1] + alvo.vel[1] * tempo_voo * 0.7
            
            # Mira direto no alvo (sem compensação de gravidade - flecha voa reta!)
            dx_mira = alvo_futuro_x - self.pos[0]
            dy_mira = alvo_futuro_y - self.pos[1]
            angulo_mira = math.degrees(math.atan2(dy_mira, dx_mira))
        else:
            angulo_mira = self.angulo_olhar
        
        # Imprecisão pequena (arqueiro é preciso!)
        angulo_mira += random.uniform(-2, 2)
        
        # === SPAWN DA FLECHA: Sai do CORPO do arqueiro (não do range!) ===
        # A flecha nasce na beirada do corpo do arqueiro, na direção da mira
        rad = math.radians(angulo_mira)
        spawn_dist = self.raio_fisico + 0.3  # Logo na borda do corpo + pequena folga
        spawn_x = self.pos[0] + math.cos(rad) * spawn_dist
        spawn_y = self.pos[1] + math.sin(rad) * spawn_dist
        
        flecha = FlechaProjetil(
            x=spawn_x, y=spawn_y,
            angulo=angulo_mira,
            dono=self,
            dano=dano,
            forca=forca_normalizada,
            cor=cor
        )
        self.buffer_projeteis.append(flecha)

    def _disparar_orbes(self, alvo):
        """Dispara orbes mágicos"""
        from core.combat import OrbeMagico
        
        arma = self.dados.arma_obj
        if not arma:
            return
        
        qtd = int(getattr(arma, 'quantidade', 2))
        dano_por_orbe = arma.dano / max(qtd, 1)
        
        cor = (arma.r, arma.g, arma.b) if hasattr(arma, 'r') else (100, 100, 255)
        
        orbes_orbitando = [o for o in self.buffer_orbes if o.ativo and o.estado == "orbitando"]
        
        if orbes_orbitando:
            for orbe in orbes_orbitando[:qtd]:
                orbe.iniciar_carga(alvo)
        else:
            for i in range(qtd):
                orbe = OrbeMagico(
                    x=self.pos[0], y=self.pos[1],
                    dono=self,
                    dano=dano_por_orbe * (self.dados.forca / 2.0 + self.dados.mana / 2.0),
                    indice=i,
                    total=qtd,
                    cor=cor
                )
                orbe.iniciar_carga(alvo)
                self.buffer_orbes.append(orbe)

    def tomar_dano(self, dano, empurrao_x, empurrao_y, tipo_efeito="NORMAL", atacante=None):
        """Recebe dano com suporte a efeitos e reflexão"""
        from core.combat import DotEffect
        
        if self.morto or self.invencivel_timer > 0:
            return False
        
        dano_final = dano
        
        if "Cavaleiro" in self.classe_nome:
            dano_final *= 0.75
        
        if "Ladino" in self.classe_nome and random.random() < 0.2:
            return False
        
        for buff in self.buffs_ativos:
            if buff.escudo_atual > 0:
                dano_final = buff.absorver_dano(dano_final)
        
        # Reflexo de dano (Reflexo Espelhado)
        dano_refletido = 0
        for buff in self.buffs_ativos:
            if hasattr(buff, 'refletir') and buff.refletir > 0:
                dano_refletido += dano_final * buff.refletir
        
        # Aplica dano refletido ao atacante (se existir)
        if dano_refletido > 0 and atacante is not None and not atacante.morto:
            # Aplica dano direto sem recursão (sem passar atacante)
            atacante.vida -= dano_refletido
            atacante.flash_timer = 0.15
            atacante.flash_cor = (200, 200, 255)  # Flash azulado para reflexo
            if atacante.vida <= 0:
                atacante.morrer()
        
        self.vida -= dano_final
        self.invencivel_timer = 0.3
        
        # Flash de dano mais longo e visível (proporcional ao dano)
        self.flash_timer = min(0.25, 0.1 + dano_final * 0.005)
        
        # Cor do flash baseada no tipo de efeito
        self.flash_cor = {
            "NORMAL": (255, 255, 255),
            # Fogo
            "FOGO": (255, 150, 50),
            "QUEIMAR": (255, 100, 0),
            "QUEIMANDO": (255, 120, 20),
            # Gelo
            "GELO": (150, 220, 255),
            "CONGELAR": (100, 200, 255),
            "CONGELADO": (180, 230, 255),
            "LENTO": (150, 200, 255),
            # Natureza/Veneno
            "VENENO": (100, 255, 100),
            "ENVENENADO": (80, 220, 80),
            "NATUREZA": (100, 200, 50),
            # Sangue
            "SANGRAMENTO": (255, 50, 50),
            "SANGRANDO": (200, 30, 30),
            "SANGUE": (180, 0, 50),
            # Raio
            "RAIO": (255, 255, 100),
            "PARALISIA": (255, 255, 150),
            # Trevas
            "TREVAS": (150, 50, 200),
            "MALDITO": (100, 0, 150),
            "NECROSE": (50, 50, 50),
            "DRENAR": (120, 0, 150),
            # Luz
            "LUZ": (255, 255, 220),
            "CEGO": (255, 255, 200),
            # Arcano
            "ARCANO": (150, 100, 255),
            "SILENCIADO": (180, 150, 255),
            # Tempo
            "TEMPO": (200, 180, 255),
            "TEMPO_PARADO": (220, 200, 255),
            # Gravitação
            "GRAVITACAO": (100, 50, 150),
            "PUXADO": (120, 70, 180),
            "VORTEX": (80, 30, 130),
            # Caos
            "CAOS": (255, 100, 200),
            # CC
            "ATORDOAR": (255, 255, 100),
            "ATORDOADO": (255, 255, 100),
            "ENRAIZADO": (139, 90, 43),
            "MEDO": (150, 0, 150),
            "CHARME": (255, 150, 200),
            "SONO": (100, 100, 200),
            "KNOCK_UP": (200, 200, 255),
            # Debuffs
            "FRACO": (150, 150, 150),
            "VULNERAVEL": (255, 150, 150),
            "EXAUSTO": (100, 100, 100),
            "MARCADO": (255, 200, 50),
            "EXPOSTO": (255, 180, 100),
            "CORROENDO": (150, 100, 50),
            # Especiais
            "EXPLOSAO": (255, 200, 100),
            "EMPURRAO": (200, 200, 200),
            "BOMBA_RELOGIO": (255, 150, 0),
            "POSSESSO": (100, 0, 100),
        }.get(tipo_efeito, (255, 255, 255))
        
        if self.brain is not None:
            self.brain.raiva += 0.2
        
        # Knockback proporcional ao dano e vida restante
        kb = 15.0 + (1.0 - (self.vida/self.vida_max)) * 10.0
        kb += dano_final * 0.2  # Dano alto = mais knockback
        self.vel[0] += empurrao_x * kb
        self.vel[1] += empurrao_y * kb
        
        self._aplicar_efeito_status(tipo_efeito)
        
        if self.vida < self.vida_max * 0.3:
            self.modo_adrenalina = True
        
        if self.vida <= 0:
            self.morrer()
            return True
        return False

    def _aplicar_efeito_status(self, efeito, duracao=None, intensidade=1.0):
        """
        Aplica efeitos de status do dano - Sistema v2.0 COLOSSAL
        
        Args:
            efeito: Nome do efeito a aplicar
            duracao: Duração customizada (opcional)
            intensidade: Multiplicador de intensidade (default 1.0)
        """
        from core.combat import DotEffect
        
        # =================================================================
        # DANOS AO LONGO DO TEMPO (DoT)
        # =================================================================
        if efeito == "VENENO" or efeito == "ENVENENADO":
            dot = DotEffect("ENVENENADO", self, 1.5 * intensidade, duracao or 4.0, (100, 255, 100))
            self.dots_ativos.append(dot)
            
        elif efeito == "SANGRAMENTO" or efeito == "SANGRANDO":
            dot = DotEffect("SANGRANDO", self, 2.0 * intensidade, duracao or 3.0, (180, 0, 30))
            self.dots_ativos.append(dot)
            
        elif efeito == "QUEIMAR" or efeito == "QUEIMANDO":
            dot = DotEffect("QUEIMANDO", self, 2.5 * intensidade, duracao or 2.5, (255, 100, 0))
            self.dots_ativos.append(dot)
            
        elif efeito == "CORROENDO":
            # Corrosão: Dano + reduz defesa
            dot = DotEffect("CORROENDO", self, 1.5 * intensidade, duracao or 4.0, (150, 100, 50))
            self.dots_ativos.append(dot)
            self.mod_defesa *= 0.8  # -20% defesa
            
        elif efeito == "NECROSE":
            # Necrose: DoT que impede cura
            dot = DotEffect("NECROSE", self, 3.0 * intensidade, duracao or 5.0, (50, 50, 50))
            self.dots_ativos.append(dot)
            if not hasattr(self, 'cura_bloqueada'):
                self.cura_bloqueada = 0
            self.cura_bloqueada = duracao or 5.0
            
        elif efeito == "MALDITO":
            # Maldição: DoT + dano recebido aumentado
            dot = DotEffect("MALDITO", self, 1.0 * intensidade, duracao or 6.0, (100, 0, 100))
            self.dots_ativos.append(dot)
            if not hasattr(self, 'vulnerabilidade'):
                self.vulnerabilidade = 1.0
            self.vulnerabilidade = 1.3
        
        # =================================================================
        # CONTROLE DE GRUPO (CC)
        # =================================================================
        elif efeito == "CONGELAR" or efeito == "CONGELADO":
            self.stun_timer = max(self.stun_timer, duracao or 2.0)
            self.slow_timer = max(self.slow_timer, (duracao or 2.0) + 1.0)
            self.slow_fator = 0.3
            if not hasattr(self, 'congelado'):
                self.congelado = False
            self.congelado = True
            
        elif efeito == "LENTO":
            self.slow_timer = max(self.slow_timer, duracao or 2.0)
            self.slow_fator = min(self.slow_fator, 0.5 / intensidade)
            
        elif efeito == "ATORDOAR" or efeito == "ATORDOADO":
            self.stun_timer = max(self.stun_timer, (duracao or 0.8) * intensidade)
            
        elif efeito == "PARALISIA":
            # Paralisia: Stun mais curto mas frequente
            self.stun_timer = max(self.stun_timer, (duracao or 0.5) * intensidade)
            self.flash_cor = (255, 255, 100)
            self.flash_timer = 0.3
            
        elif efeito == "ENRAIZADO":
            # Enraizado: Não pode mover mas pode atacar
            if not hasattr(self, 'enraizado_timer'):
                self.enraizado_timer = 0
            self.enraizado_timer = max(self.enraizado_timer, duracao or 2.5)
            self.slow_fator = 0.0  # Velocidade zero
            
        elif efeito == "SILENCIADO":
            # Silenciado: Não pode usar skills
            if not hasattr(self, 'silenciado_timer'):
                self.silenciado_timer = 0
            self.silenciado_timer = duracao or 3.0
            
        elif efeito == "CEGO":
            # Cego: Ângulo de visão prejudicado (IA afetada)
            if not hasattr(self, 'cego_timer'):
                self.cego_timer = 0
            self.cego_timer = duracao or 2.0
            self.flash_cor = (255, 255, 200)
            self.flash_timer = 0.5
            
        elif efeito == "MEDO":
            # Medo: Força a fugir
            if not hasattr(self, 'medo_timer'):
                self.medo_timer = 0
            self.medo_timer = duracao or 2.5
            if self.brain is not None:
                self.brain.medo = 1.0  # Maximiza medo na IA
            
        elif efeito == "CHARME":
            # Charme: Inimigo te segue
            if not hasattr(self, 'charme_timer'):
                self.charme_timer = 0
            self.charme_timer = duracao or 2.0
            
        elif efeito == "SONO":
            # Sono: Stun longo que quebra com dano
            if not hasattr(self, 'dormindo'):
                self.dormindo = False
            self.dormindo = True
            self.stun_timer = max(self.stun_timer, duracao or 4.0)
            
        elif efeito == "KNOCK_UP":
            # Knock Up: Joga no ar
            self.vel_z = 12.0 * intensidade
            self.stun_timer = max(self.stun_timer, 0.5)
            
        elif efeito == "PUXADO":
            # Puxado: Atração gravitacional (implementado no efeito de área)
            if not hasattr(self, 'sendo_puxado'):
                self.sendo_puxado = False
            self.sendo_puxado = True
            
        elif efeito == "TEMPO_PARADO":
            # Tempo parado: Completamente imobilizado
            self.stun_timer = max(self.stun_timer, duracao or 2.0)
            self.slow_fator = 0.0
            if not hasattr(self, 'tempo_parado'):
                self.tempo_parado = False
            self.tempo_parado = True
            
        elif efeito == "VORTEX":
            # Vortex: Sendo puxado continuamente
            if not hasattr(self, 'em_vortex'):
                self.em_vortex = False
            self.em_vortex = True
        
        # =================================================================
        # DEBUFFS
        # =================================================================
        elif efeito == "FRACO":
            # Fraco: Dano reduzido
            if not hasattr(self, 'dano_reduzido'):
                self.dano_reduzido = 1.0
            self.dano_reduzido = 0.7
            
        elif efeito == "VULNERAVEL":
            # Vulnerável: Dano recebido aumentado
            if not hasattr(self, 'vulnerabilidade'):
                self.vulnerabilidade = 1.0
            self.vulnerabilidade = 1.5
            
        elif efeito == "EXAUSTO":
            # Exausto: Regen de stamina/mana reduzida
            if not hasattr(self, 'exausto_timer'):
                self.exausto_timer = 0
            self.exausto_timer = duracao or 5.0
            self.regen_mana_base *= 0.3
            
        elif efeito == "MARCADO":
            # Marcado: Próximo ataque causa dano extra
            if not hasattr(self, 'marcado'):
                self.marcado = False
            self.marcado = True
            
        elif efeito == "EXPOSTO":
            # Exposto: Ignora parte da defesa
            if not hasattr(self, 'exposto_timer'):
                self.exposto_timer = 0
            self.exposto_timer = duracao or 4.0
        
        # =================================================================
        # EFEITOS DE EMPURRÃO/MOVIMENTO
        # =================================================================
        elif efeito == "EMPURRAO":
            # Já tratado pelo knockback normal
            pass
            
        elif efeito == "EXPLOSAO":
            # Explosão já causa o knockback
            pass
        
        # =================================================================
        # EFEITOS ESPECIAIS
        # =================================================================
        elif efeito == "DRENAR":
            # Drenar: Já é tratado pelo lifesteal da skill
            pass
            
        elif efeito == "BOMBA_RELOGIO":
            # Bomba relógio: Explode depois de X segundos
            if not hasattr(self, 'bomba_relogio_timer'):
                self.bomba_relogio_timer = 0
            self.bomba_relogio_timer = duracao or 3.0
            self.bomba_relogio_dano = 80.0 * intensidade
            
        elif efeito == "LINK_ALMA":
            # Link de alma: Dano compartilhado
            if not hasattr(self, 'link_alma_alvo'):
                self.link_alma_alvo = None
                
        elif efeito == "POSSESSO":
            # Possessão: Controle invertido temporário
            if not hasattr(self, 'possesso_timer'):
                self.possesso_timer = 0
            self.possesso_timer = duracao or 3.0

    def tomar_clash(self, ex, ey):
        """Recebe impacto de clash de armas"""
        self.stun_timer = 0.5
        self.atacando = False
        self.vel[0] += ex * 25
        self.vel[1] += ey * 25

    def morrer(self):
        """Processa morte do lutador"""
        self.morto = True
        self.vida = 0
        self.arma_droppada_pos = list(self.pos)
        self.arma_droppada_ang = self.angulo_arma_visual

    def get_pos_ponteira_arma(self):
        """Retorna posição da ponta da arma"""
        arma = self.dados.arma_obj
        if not arma:
            return None
        
        if any(t in arma.tipo for t in ["Orbital", "Arremesso", "Mágica"]):
            return None
        
        rad = math.radians(self.angulo_arma_visual)
        ax, ay = int(self.pos[0] * PPM), int(self.pos[1] * PPM)
        
        if "Transformável" in arma.tipo:
            forma = getattr(arma, 'forma_atual', 1)
            if forma == 1:
                cabo_v = getattr(arma, 'forma1_cabo', arma.comp_cabo)
                lamina_v = getattr(arma, 'forma1_lamina', arma.comp_lamina)
            else:
                cabo_v = getattr(arma, 'forma2_cabo', arma.comp_cabo)
                lamina_v = getattr(arma, 'forma2_lamina', arma.comp_lamina)
            cabo_px = int(((cabo_v/100)*PPM) * self.fator_escala)
            lamina_px = int(((lamina_v/100)*PPM) * self.fator_escala)
        elif "Corrente" in arma.tipo:
            cabo_px = 0
            lamina_px = int(((getattr(arma, 'comp_corrente', 80)/100)*PPM) * self.fator_escala)
        else:
            cabo_px = int(((arma.comp_cabo/100)*PPM) * self.fator_escala)
            lamina_px = int(((arma.comp_lamina/100)*PPM) * self.fator_escala)
        
        xi = ax + math.cos(rad) * cabo_px
        yi = ay + math.sin(rad) * cabo_px
        xf = ax + math.cos(rad) * (cabo_px + lamina_px)
        yf = ay + math.sin(rad) * (cabo_px + lamina_px)
        return (xi, yi), (xf, yf)

    def get_escudo_info(self):
        """Retorna info do escudo orbital"""
        arma = self.dados.arma_obj
        if not arma or "Orbital" not in arma.tipo:
            return None
        cx, cy = int(self.pos[0] * PPM), int(self.pos[1] * PPM)
        dist_base_px = int(((arma.distancia/100)*PPM)*self.fator_escala)
        raio_char_px = int((self.dados.tamanho/2)*PPM)
        return (cx, cy), dist_base_px + raio_char_px, self.angulo_arma_visual, arma.largura
    
    def get_dano_modificado(self, dano_base):
        """Retorna dano com todos os modificadores"""
        dano = dano_base * self.mod_dano
        
        for buff in self.buffs_ativos:
            dano *= buff.buff_dano
        
        if "Berserker" in self.classe_nome:
            hp_pct = self.vida / self.vida_max
            dano *= 1.0 + (1.0 - hp_pct) * 0.5
        
        if "Assassino" in self.classe_nome and random.random() < 0.25:
            dano *= 2.0
        
        return dano

    # =========================================================================
    # SISTEMA DE CHANNELING v8.0 (Para Classes Mágicas)
    # =========================================================================
    
    def pode_canalizar_magia(self) -> bool:
        """
        Verifica se o personagem pode canalizar magias.
        Apenas classes mágicas têm acesso ao channeling.
        """
        classes_magicas = ["Mago", "Piromante", "Criomante", "Necromante", "Feiticeiro"]
        return any(c in self.classe_nome for c in classes_magicas)
    
    def iniciar_canalizacao(self, skill_nome: str, skill_data: dict) -> bool:
        """
        Inicia a canalização de uma magia poderosa.
        
        Args:
            skill_nome: Nome da skill a ser canalizada
            skill_data: Dados da skill
            
        Returns:
            True se a canalização iniciou com sucesso
            
        Nota:
            O GameFeelManager gerencia o estado real da canalização.
            Este método apenas marca o lutador como "canalizando".
        """
        if not self.pode_canalizar_magia():
            return False
        
        # Marca estado de canalização no lutador
        self.canalizando = True
        self.skill_canalizando = skill_nome
        self.tempo_canalizacao = 0.0
        
        # O resto é gerenciado pelo GameFeelManager
        return True
    
    def interromper_canalizacao(self):
        """Interrompe a canalização atual"""
        self.canalizando = False
        self.skill_canalizando = None
        self.tempo_canalizacao = 0.0
    
    def atualizar_canalizacao(self, dt: float) -> dict:
        """
        Atualiza o estado de canalização.
        
        Returns:
            Dict com resultado se a magia foi liberada, None caso contrário
        """
        if not getattr(self, 'canalizando', False):
            return None
        
        self.tempo_canalizacao += dt
        
        # O GameFeelManager processa a lógica real
        # Este método apenas rastreia o tempo no lutador
        return None
    
    def get_progresso_canalizacao(self) -> float:
        """Retorna o progresso da canalização (0.0 a 1.0)"""
        if not getattr(self, 'canalizando', False):
            return 0.0
        
        # Tempo padrão de canalização varia por classe
        tempo_base = {
            "Mago (Arcano)": 1.5,
            "Piromante (Fogo)": 2.0,
            "Criomante (Gelo)": 1.2,
            "Necromante (Trevas)": 2.5,
            "Feiticeiro (Caos)": 1.0,
        }.get(self.classe_nome, 1.5)
        
        return min(1.0, getattr(self, 'tempo_canalizacao', 0.0) / tempo_base)
