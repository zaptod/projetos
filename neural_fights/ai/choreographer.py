"""
=============================================================================
NEURAL FIGHTS - Sistema de Coreografia v6.0 HUMAN EDITION
=============================================================================
Coordenador de Coreografia de Combate.
Gerencia interações entre IAs para criar momentos cinematográficos realistas.

NOVIDADES v6.0:
- Ritmo de combate mais natural
- Trocas de golpes realistas
- Momentos de tensão e respiro
- Sincronização de ações reativas
- Fluxo e refluxo da luta
=============================================================================
"""

import random
import math

from neural_fights.ai.contracts import obter_brain


class CombatChoreographer:
    """
    Coordenador de Coreografia de Combate v6.0.
    Gerencia interações entre IAs para criar momentos cinematográficos realistas.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = CombatChoreographer()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def __init__(self, rng=None):
        self.rng = rng if rng is not None else random
        # Estado do confronto
        self.momento_atual = "NEUTRO"
        self.timer_momento = 0.0
        self.duracao_momento = 0.0
        
        # Participantes
        self.lutador1 = None
        self.lutador2 = None
        
        # Histórico de momentos
        self.momentos_recentes = []
        self.cooldown_momentos = {}
        
        # Intensidade da luta (0.0 a 1.0)
        self.intensidade = 0.0
        self.climax_atingido = False
        
        # Contadores de ação
        self.trocas_seguidas = 0
        self.tempo_sem_hit = 0.0
        self.ultimo_agressor = None
        
        # Sincronização
        self.sync_action = None
        self.sync_timer = 0.0
        
        # === NOVOS v6.0 ===
        # Ritmo da luta
        self.ritmo_atual = "NEUTRO"  # NEUTRO, AGRESSIVO, CAUTELOSO, EXPLOSIVO
        self.ritmo_timer = 0.0
        
        # Fluxo de combate
        self.fluxo_direcao = 0  # -1 = L1 recuando, 0 = neutro, 1 = L2 recuando
        self.fluxo_intensidade = 0.0
        
        # Contagem de engajamentos
        self.engajamentos_proximos = 0
        self.tempo_em_range = 0.0
        self.tempo_fora_range = 0.0
        
        # Troca de golpes
        self.sequencia_hits = []  # Quem acertou: [1, 2, 1, 1, 2...]
        self.ultima_troca_tempo = 0.0
        
        # === CLASH DETECTION v6.1 ===
        # Rastreia ataques recentes para detectar clash (janela de tempo maior)
        self.l1_ultimo_ataque_tempo = 999.0  # Tempo desde último ataque de L1
        self.l2_ultimo_ataque_tempo = 999.0  # Tempo desde último ataque de L2
        self.clash_window = 0.35  # Janela de tempo para considerar "mesmo momento"
    
    def registrar_lutadores(self, l1, l2):
        """Registra os dois lutadores"""
        self.lutador1 = l1
        self.lutador2 = l2
        self.rng = getattr(l1, "rng_runtime", self.rng)
        self.l1_ultimo_ataque_tempo = 999.0
        self.l2_ultimo_ataque_tempo = 999.0
        # Onda 10A: o encarar acontece UMA vez por luta e curto.
        self._face_off_usado = False
    
    def update(self, dt):
        """Atualiza o sistema de coreografia"""
        if not self.lutador1 or not self.lutador2:
            return
        
        # Atualiza timers
        self.timer_momento -= dt
        self.sync_timer -= dt
        self.tempo_sem_hit += dt
        self.ritmo_timer -= dt
        self.ultima_troca_tempo += dt
        
        # === CLASH DETECTION v6.1 - Rastreia ataques ===
        self.l1_ultimo_ataque_tempo += dt
        self.l2_ultimo_ataque_tempo += dt
        
        # Detecta quando um lutador começa a atacar
        l1_atacando_agora = getattr(self.lutador1, 'atacando', False)
        l2_atacando_agora = getattr(self.lutador2, 'atacando', False)
        
        if l1_atacando_agora:
            self.l1_ultimo_ataque_tempo = 0.0
        if l2_atacando_agora:
            self.l2_ultimo_ataque_tempo = 0.0
        
        # Decay de cooldowns
        for k in list(self.cooldown_momentos.keys()):
            self.cooldown_momentos[k] -= dt
            if self.cooldown_momentos[k] <= 0:
                del self.cooldown_momentos[k]
        
        # Calcula distância
        distancia = math.sqrt(
            (self.lutador1.pos[0] - self.lutador2.pos[0])**2 + 
            (self.lutador1.pos[1] - self.lutador2.pos[1])**2
        )
        
        # Atualiza tempo em/fora de range
        if distancia < 4.0:
            self.tempo_em_range += dt
            self.tempo_fora_range = 0
        else:
            self.tempo_fora_range += dt
            self.tempo_em_range = 0
        
        # Calcula intensidade
        self._calcular_intensidade()
        
        # Atualiza ritmo da luta
        self._atualizar_ritmo(dt, distancia)
        
        # Atualiza fluxo de combate
        self._atualizar_fluxo(dt, distancia)
        
        # Termina momento atual
        if self.timer_momento <= 0 and self.momento_atual != "NEUTRO":
            self._finalizar_momento()
        
        # Detecta oportunidades de momento
        if self.momento_atual == "NEUTRO":
            self._detectar_momento()
    
    def _atualizar_ritmo(self, dt, distancia):
        """Atualiza o ritmo geral da luta"""
        if self.ritmo_timer > 0:
            return
        
        l1, l2 = self.lutador1, self.lutador2
        
        # Analisa situação
        ambos_agressivos = False
        ambos_cautelosos = False
        
        brain1 = obter_brain(l1)
        brain2 = obter_brain(l2)
        if brain1 and brain2:
            a1 = brain1.acao_atual in ["MATAR", "ESMAGAR", "PRESSIONAR", "APROXIMAR"]
            a2 = brain2.acao_atual in ["MATAR", "ESMAGAR", "PRESSIONAR", "APROXIMAR"]
            c1 = brain1.acao_atual in ["RECUAR", "CIRCULAR", "BLOQUEAR"]
            c2 = brain2.acao_atual in ["RECUAR", "CIRCULAR", "BLOQUEAR"]
            
            ambos_agressivos = a1 and a2
            ambos_cautelosos = c1 and c2
        
        novo_ritmo = self.ritmo_atual
        
        # Determina novo ritmo
        if ambos_agressivos and distancia < 4.0:
            novo_ritmo = "EXPLOSIVO"
        elif self.trocas_seguidas >= 4:
            novo_ritmo = "AGRESSIVO"
        elif ambos_cautelosos or self.tempo_sem_hit > 4.0:
            novo_ritmo = "CAUTELOSO"
        elif self.intensidade > 0.7:
            novo_ritmo = "AGRESSIVO"
        else:
            novo_ritmo = "NEUTRO"
        
        if novo_ritmo != self.ritmo_atual:
            self.ritmo_atual = novo_ritmo
            self.ritmo_timer = self.rng.uniform(2.0, 5.0)
            
            # Notifica IAs sobre mudança de ritmo
            self._notificar_mudanca_ritmo(novo_ritmo)
    
    def _atualizar_fluxo(self, dt, distancia):
        """Atualiza o fluxo de quem está dominando"""
        l1, l2 = self.lutador1, self.lutador2
        
        # Analisa velocidades relativas
        vel1_mag = math.sqrt(l1.vel[0]**2 + l1.vel[1]**2) if l1 else 0
        vel2_mag = math.sqrt(l2.vel[0]**2 + l2.vel[1]**2) if l2 else 0
        
        # Direção do movimento relativo ao oponente
        if l1 and l2:
            # L1 indo em direção a L2?
            ang_l1_para_l2 = math.atan2(l2.pos[1] - l1.pos[1], l2.pos[0] - l1.pos[0])
            ang_vel_l1 = math.atan2(l1.vel[1], l1.vel[0]) if vel1_mag > 0.5 else 0
            l1_avancando = abs(ang_l1_para_l2 - ang_vel_l1) < math.pi / 3
            
            # L2 indo em direção a L1?
            ang_l2_para_l1 = ang_l1_para_l2 + math.pi
            ang_vel_l2 = math.atan2(l2.vel[1], l2.vel[0]) if vel2_mag > 0.5 else 0
            l2_avancando = abs(ang_l2_para_l1 - ang_vel_l2) < math.pi / 3
            
            # Atualiza fluxo
            if l1_avancando and not l2_avancando:
                self.fluxo_direcao = min(1.0, self.fluxo_direcao + dt * 0.5)
            elif l2_avancando and not l1_avancando:
                self.fluxo_direcao = max(-1.0, self.fluxo_direcao - dt * 0.5)
            else:
                # Decay para neutro
                self.fluxo_direcao *= 0.98
        
        # Fluxo baseado em hits recentes
        if len(self.sequencia_hits) >= 3:
            ultimos = self.sequencia_hits[-3:]
            if ultimos.count(1) >= 2:
                self.fluxo_direcao = min(1.0, self.fluxo_direcao + 0.1)
            elif ultimos.count(2) >= 2:
                self.fluxo_direcao = max(-1.0, self.fluxo_direcao - 0.1)
        
        self.fluxo_intensidade = abs(self.fluxo_direcao)
    
    def _notificar_mudanca_ritmo(self, ritmo):
        """Notifica IAs sobre mudança de ritmo"""
        for l in [self.lutador1, self.lutador2]:
            brain = obter_brain(l)
            if brain:
                # IAs podem reagir ao ritmo
                if hasattr(brain, 'on_ritmo_mudou'):
                    brain.on_ritmo_mudou(ritmo)
                
                # Ajusta comportamento base
                if ritmo == "EXPLOSIVO":
                    brain.excitacao = min(1.0, brain.excitacao + 0.2)
                elif ritmo == "CAUTELOSO":
                    brain.tedio = min(0.5, brain.tedio + 0.1)
    
    def _calcular_intensidade(self):
        """Calcula intensidade atual da luta"""
        l1, l2 = self.lutador1, self.lutador2
        
        # HP médio (mais intenso quando ambos baixos)
        hp1_pct = l1.vida / l1.vida_max
        hp2_pct = l2.vida / l2.vida_max
        hp_fator = 1.0 - ((hp1_pct + hp2_pct) / 2)
        
        # Diferença de HP (mais intenso quando próximo)
        hp_diff = abs(hp1_pct - hp2_pct)
        equilibrio_fator = 1.0 - hp_diff
        
        # Ação recente
        acao_fator = min(1.0, self.trocas_seguidas / 5.0)
        
        # Tempo (builds up)
        brain1 = obter_brain(l1)
        if brain1:
            tempo_fator = min(1.0, brain1.tempo_combate / 60.0)
        else:
            tempo_fator = 0.5
        
        # Combina fatores
        self.intensidade = (hp_fator * 0.3 + equilibrio_fator * 0.25 + 
                           acao_fator * 0.25 + tempo_fator * 0.2)
        
        # Clímax quando ambos < 25% HP
        if hp1_pct < 0.25 and hp2_pct < 0.25:
            self.climax_atingido = True
            self.intensidade = min(1.0, self.intensidade + 0.3)
    
    def _detectar_momento(self):
        """Detecta oportunidade para momento cinematográfico"""
        l1, l2 = self.lutador1, self.lutador2
        distancia = math.sqrt((l1.pos[0] - l2.pos[0])**2 + (l1.pos[1] - l2.pos[1])**2)
        
        hp1_pct = l1.vida / l1.vida_max
        hp2_pct = l2.vida / l2.vida_max
        
        # === CLASH (Colisão de ataques) v6.1 - Janela de tempo melhorada ===
        if self._pode_momento("CLASH"):
            # Verifica se ambos atacaram dentro da janela de tempo
            ambos_atacando_agora = getattr(l1, 'atacando', False) and getattr(l2, 'atacando', False)
            ambos_atacaram_recente = (self.l1_ultimo_ataque_tempo < self.clash_window and 
                                       self.l2_ultimo_ataque_tempo < self.clash_window)
            
            if (ambos_atacando_agora or ambos_atacaram_recente) and distancia < 3.5:
                self._iniciar_momento("CLASH", 0.8)
                # Reset timers para evitar múltiplos clashes
                self.l1_ultimo_ataque_tempo = 999.0
                self.l2_ultimo_ataque_tempo = 999.0
                return
        
        # === STANDOFF (Confronto visual) ===
        if self._pode_momento("STANDOFF"):
            if 4.0 < distancia < 7.0 and self.tempo_sem_hit > 3.0:
                if self.intensidade > 0.4 or self.rng.random() < 0.02:
                    # Onda 10A: beat curto — o standoff longo realimentava
                    # a seca que o disparou.
                    self._iniciar_momento("STANDOFF", self.rng.uniform(1.0, 1.5))
                    return
        
        # === FACE_OFF (Ambos param e se encaram) ===
        if self._pode_momento("FACE_OFF") and not getattr(self, "_face_off_usado", False):
            if hp1_pct < 0.5 and hp2_pct < 0.5 and self.intensidade > 0.5:
                if 3.0 < distancia < 6.0 and self.rng.random() < 0.03:
                    # Onda 10A: os dois se encaram por 0,8s, UMA vez por
                    # luta, e o beat termina com alguém tomando a
                    # iniciativa (ver _explodir_face_off). Antes: 2-4s de
                    # BLOQUEAR nos dois — o "cara a cara" fabricado.
                    self._face_off_usado = True
                    self._iniciar_momento("FACE_OFF", 0.8)
                    return
        
        # === CLIMAX_CHARGE (Ambos preparam ataque final) ===
        if self._pode_momento("CLIMAX_CHARGE"):
            if self.climax_atingido and self.intensidade > 0.7:
                if self.rng.random() < 0.05:
                    self._iniciar_momento("CLIMAX_CHARGE", self.rng.uniform(2.0, 3.5))
                    return
        
        # === PURSUIT (Perseguição cinematográfica) ===
        if self._pode_momento("PURSUIT"):
            if distancia > 8.0 and self.tempo_sem_hit > 2.0:
                # Detecta quem está fugindo
                if hp1_pct < hp2_pct * 0.7 or hp2_pct < hp1_pct * 0.7:
                    if self.rng.random() < 0.04:
                        self._iniciar_momento("PURSUIT", self.rng.uniform(2.0, 4.0))
                        return
        
        # === EXCHANGE (Troca rápida de golpes) ===
        if self._pode_momento("EXCHANGE"):
            if distancia < 3.0 and self.trocas_seguidas >= 3:
                if self.rng.random() < 0.1:
                    self._iniciar_momento("EXCHANGE", self.rng.uniform(1.5, 2.5))
                    return
        
        # === BREATHER (Pausa para respirar) ===
        if self._pode_momento("BREATHER"):
            sem_folego = (
                getattr(l1, "estamina", 100.0) < 30.0
                and getattr(l2, "estamina", 100.0) < 30.0
            )
            # Onda 10A: respiro só quando os DOIS estão sem fôlego — parar
            # a luta por decisão de diretor é o que o espectador odeia.
            if self.trocas_seguidas >= 5 and distancia > 4.0 and sem_folego:
                if self.rng.random() < 0.06:
                    self._iniciar_momento("BREATHER", self.rng.uniform(1.0, 2.0))
                    return
        
        # === CIRCLE_DANCE (Circulam um ao outro) ===
        if self._pode_momento("CIRCLE_DANCE"):
            if 3.0 < distancia < 6.0 and self.intensidade > 0.3:
                if self.rng.random() < 0.025:
                    self._iniciar_momento("CIRCLE_DANCE", self.rng.uniform(2.0, 4.0))
                    return
        
        # === FINAL_SHOWDOWN (Momento final) ===
        if self._pode_momento("FINAL_SHOWDOWN"):
            # Onda 5D (item puxado da 5E): o gate de climax nunca chegava a
            # ser atingido — FINAL_SHOWDOWN jamais disparou em medição. O
            # plano manda o trigger honesto: AMBOS abaixo de 30%.
            if hp1_pct < 0.30 and hp2_pct < 0.30:
                if self.rng.random() < 0.12:
                    self._iniciar_momento("FINAL_SHOWDOWN", self.rng.uniform(2.5, 4.0))
                    return
        
        # === NOVOS MOMENTOS v6.0 ===
        
        # === PRESSURE (Um lado pressionando o outro) ===
        if self._pode_momento("PRESSURE"):
            if abs(self.fluxo_direcao) > 0.5 and self.tempo_em_range > 2.0:
                if self.rng.random() < 0.08:
                    self._iniciar_momento("PRESSURE", self.rng.uniform(2.0, 4.0))
                    return
        
        # === RESET (Ambos se afastam para respirar) ===
        if self._pode_momento("RESET"):
            if self.trocas_seguidas >= 6 and distancia < 3.0:
                if self.rng.random() < 0.1:
                    self._iniciar_momento("RESET", self.rng.uniform(1.0, 2.0))
                    self.trocas_seguidas = 0
                    return
        
        # === FEINT_DANCE (Dança de fintas) ===
        if self._pode_momento("FEINT_DANCE"):
            if 2.5 < distancia < 5.0 and self.tempo_sem_hit > 1.5:
                # Ambos em postura de combate mas sem atacar
                brain1 = obter_brain(l1)
                brain2 = obter_brain(l2)
                if brain1 and brain2:
                    a1 = brain1.acao_atual in ["COMBATE", "CIRCULAR", "FLANQUEAR"]
                    a2 = brain2.acao_atual in ["COMBATE", "CIRCULAR", "FLANQUEAR"]
                    if a1 and a2 and self.rng.random() < 0.06:
                        self._iniciar_momento("FEINT_DANCE", self.rng.uniform(1.5, 3.0))
                        return
    
    def _pode_momento(self, tipo):
        """Verifica se pode iniciar este tipo de momento"""
        return tipo not in self.cooldown_momentos
    
    def _iniciar_momento(self, tipo, duracao):
        """Inicia um momento cinematográfico"""
        self.momento_atual = tipo
        self.duracao_momento = duracao
        self.timer_momento = duracao
        self.momentos_recentes.append(tipo)
        
        # Mantém histórico limitado
        if len(self.momentos_recentes) > 10:
            self.momentos_recentes.pop(0)
        
        # Notifica as IAs
        self._notificar_momento_iniciado(tipo)
    
    def _finalizar_momento(self):
        """Finaliza o momento atual"""
        tipo_anterior = self.momento_atual
        self.momento_atual = "NEUTRO"
        
        # Cooldown baseado no tipo
        cooldowns = {
            "CLASH": 5.0,
            "STANDOFF": 8.0,
            "FACE_OFF": 12.0,
            "CLIMAX_CHARGE": 15.0,
            "PURSUIT": 6.0,
            "EXCHANGE": 4.0,
            "BREATHER": 10.0,
            "CIRCLE_DANCE": 7.0,
            "FINAL_SHOWDOWN": 20.0,
            # Novos v6.0
            "RAPID_EXCHANGE": 3.0,
            "NEAR_MISS": 2.0,
            "PRESSURE": 5.0,
            "RESET": 8.0,
            "FEINT_DANCE": 6.0,
        }
        self.cooldown_momentos[tipo_anterior] = cooldowns.get(tipo_anterior, 5.0)
        
        # Notifica as IAs
        self._notificar_momento_finalizado(tipo_anterior)
        if tipo_anterior == "FACE_OFF":
            self._explodir_face_off()

    def _explodir_face_off(self):
        """Onda 10A: o encarar acaba em ação — o lado mais agressivo toma a
        iniciativa (dash-in ou golpe, via ``AIBrain.forcar_iniciativa``)."""
        l1, l2 = self.lutador1, self.lutador2
        if l1 is None or l2 is None:
            return
        if getattr(l1, "morto", False) or getattr(l2, "morto", False):
            return

        def _agressao(l):
            brain = obter_brain(l)
            fn = getattr(brain, "agressividade_efetiva", None)
            if callable(fn):
                try:
                    return float(fn())
                except Exception:
                    return 0.5
            return 0.5

        ini, outro = (l1, l2) if _agressao(l1) >= _agressao(l2) else (l2, l1)
        brain = obter_brain(ini)
        forcar = getattr(brain, "forcar_iniciativa", None)
        if not callable(forcar):
            return
        distancia = math.hypot(
            outro.pos[0] - ini.pos[0], outro.pos[1] - ini.pos[1]
        )
        forcar(distancia, outro, permitir_dash=True)
    
    def _notificar_momento_iniciado(self, tipo):
        """Notifica IAs sobre momento iniciado"""
        for l in [self.lutador1, self.lutador2]:
            brain = obter_brain(l)
            if brain:
                brain.on_momento_cinematografico(tipo, True, self.duracao_momento)
    
    def _notificar_momento_finalizado(self, tipo):
        """Notifica IAs sobre momento finalizado"""
        for l in [self.lutador1, self.lutador2]:
            brain = obter_brain(l)
            if brain:
                brain.on_momento_cinematografico(tipo, False, 0)
    
    def registrar_hit(self, atacante, defensor):
        """Registra quando um hit acontece - integrado com sistema de fluxo"""
        self.tempo_sem_hit = 0.0
        self.trocas_seguidas += 1
        self.ultima_troca_tempo = 0.0
        
        # Registra na sequência de hits
        if atacante == self.lutador1:
            self.sequencia_hits.append(1)
        else:
            self.sequencia_hits.append(2)
        
        # Mantém histórico limitado
        if len(self.sequencia_hits) > 20:
            self.sequencia_hits.pop(0)
        
        # Notifica IAs
        brain_atacante = obter_brain(atacante)
        brain_defensor = obter_brain(defensor)
        if brain_atacante:
            brain_atacante.on_hit_dado()
        if brain_defensor:
            brain_defensor.on_hit_recebido_de(atacante)
        
        self.ultimo_agressor = atacante
        
        # Detecta troca rápida de golpes
        if self.trocas_seguidas >= 3 and self._pode_momento("RAPID_EXCHANGE"):
            if self.rng.random() < 0.3:
                self._iniciar_momento("RAPID_EXCHANGE", self.rng.uniform(1.0, 2.0))
    
    def registrar_esquiva(self, esquivador, atacante):
        """Registra quando alguém desvia de um ataque"""
        brain_esquivador = obter_brain(esquivador)
        if brain_esquivador and hasattr(brain_esquivador, 'on_esquiva_sucesso'):
            brain_esquivador.on_esquiva_sucesso()

        # Pode criar momento de tensão
        if self._pode_momento("NEAR_MISS") and self.rng.random() < 0.15:
            self._iniciar_momento("NEAR_MISS", self.rng.uniform(0.5, 1.0))

    def registrar_parry(self, defensor, atacante):
        """Onda 8B: parry conectou — momento dramático por natureza.

        O brain do defensor já abriu a janela pos_parry pelo hook do
        motor; aqui o diretor só amplifica o drama do instante.
        """
        if self._pode_momento("NEAR_MISS") and self.rng.random() < 0.35:
            self._iniciar_momento("NEAR_MISS", self.rng.uniform(0.6, 1.2))
    
    def get_acao_sincronizada(self, lutador):
        """Retorna ação sincronizada para o lutador (se houver)"""
        if self.momento_atual == "NEUTRO":
            return None
        
        # Ações baseadas no momento
        if self.momento_atual == "STANDOFF":
            return "CIRCULAR_LENTO"
        elif self.momento_atual == "FACE_OFF":
            return "ENCARAR"
        elif self.momento_atual == "CLIMAX_CHARGE":
            return "PREPARAR_ATAQUE"
        elif self.momento_atual == "PURSUIT":
            if lutador == self.ultimo_agressor:
                return "PERSEGUIR"
            else:
                return "FUGIR_DRAMATICO"
        elif self.momento_atual == "EXCHANGE":
            return "TROCAR_GOLPES"
        elif self.momento_atual == "BREATHER":
            return "RECUPERAR"
        elif self.momento_atual == "CIRCLE_DANCE":
            return "CIRCULAR_SINCRONIZADO"
        elif self.momento_atual == "CLASH":
            return "CLASH"
        elif self.momento_atual == "FINAL_SHOWDOWN":
            return "ATAQUE_FINAL"
        # === NOVOS v6.0 ===
        elif self.momento_atual == "RAPID_EXCHANGE":
            return "TROCAR_RAPIDO"
        elif self.momento_atual == "NEAR_MISS":
            return "REAGIR_ESQUIVA"
        elif self.momento_atual == "PRESSURE":
            # Quem está pressionando vs sendo pressionado
            if self.fluxo_direcao > 0.3 and lutador == self.lutador1:
                return "PRESSIONAR_CONTINUO"
            elif self.fluxo_direcao < -0.3 and lutador == self.lutador2:
                return "PRESSIONAR_CONTINUO"
            else:
                return "RESISTIR_PRESSAO"
        elif self.momento_atual == "RESET":
            return "SEPARAR"
        elif self.momento_atual == "FEINT_DANCE":
            return "FINTA"
        
        return None
    
    def get_intensidade(self):
        """Retorna intensidade atual"""
        return self.intensidade
    
    def get_momento(self):
        """Retorna momento atual"""
        return self.momento_atual
    
    def get_ritmo(self):
        """Retorna ritmo atual da luta"""
        return self.ritmo_atual
    
    def get_fluxo(self):
        """Retorna direção do fluxo (-1 a 1)"""
        return self.fluxo_direcao
