"""
NEURAL FIGHTS - Sistema de Emoções e Humor v8.0
Gerencia estados emocionais e humor da IA.
"""

import random


class EmotionSystem:
    """
    Sistema de emoções para IA.
    Gerencia estados emocionais, humor e reações emocionais.
    """
    
    def __init__(self, parent, tracos):
        self.parent = parent
        self.tracos = tracos
        
        # === EMOÇÕES (0.0 a 1.0) ===
        self.medo = 0.0
        self.raiva = 0.0
        self.confianca = 0.5
        self.frustracao = 0.0
        self.adrenalina = 0.0
        self.excitacao = 0.0
        self.tedio = 0.0
        
        # === HUMOR ATUAL ===
        self.humor = "CALMO"
        self.humor_timer = 0.0
        self.cd_mudanca_humor = 0.0
        
        # === MEMÓRIA DE COMBATE ===
        self.hits_recebidos_total = 0
        self.hits_dados_total = 0
        self.hits_recebidos_recente = 0
        self.hits_dados_recente = 0
        self.tempo_desde_dano = 5.0
        self.tempo_desde_hit = 5.0
        self.combo_atual = 0
        self.max_combo = 0
        
        # Aplica modificadores iniciais baseados em traços
        self._aplicar_modificadores_iniciais()
    
    def _aplicar_modificadores_iniciais(self):
        """Aplica modificadores iniciais baseados na personalidade"""
        if "IMPRUDENTE" in self.tracos:
            self.confianca = 0.8
        if "COVARDE" in self.tracos or "MEDROSO" in self.tracos:
            self.medo = 0.2
        if "BERSERKER" in self.tracos:
            self.raiva = 0.3
        if "FURIOSO" in self.tracos:
            self.raiva = 0.4
        if "FRIO" in self.tracos:
            self.medo = 0.0
            self.raiva = 0.0
    
    def atualizar(self, dt, distancia, inimigo, tempo_combate, dir_circular_cd):
        """Atualiza estado emocional"""
        p = self.parent
        hp_pct = p.vida / p.vida_max
        inimigo_hp_pct = inimigo.vida / inimigo.vida_max if inimigo.vida_max > 0 else 1.0
        
        # Decay de emoções
        decay = 0.005 if "FRIO" in self.tracos else 0.015
        if "EMOTIVO" in self.tracos:
            decay *= 0.5
        
        self.raiva = max(0, self.raiva - decay * dt * 60)
        self.medo = max(0, self.medo - decay * dt * 60)
        self.frustracao = max(0, self.frustracao - 0.005 * dt * 60)
        self.adrenalina = max(0, self.adrenalina - 0.01 * dt * 60)
        self.excitacao = max(0, self.excitacao - 0.008 * dt * 60)
        self.tedio = max(0, self.tedio - 0.01 * dt * 60)
        
        # Decay de contadores
        if self.tempo_desde_dano > 3.0:
            self.hits_recebidos_recente = max(0, self.hits_recebidos_recente - 1)
        if self.tempo_desde_hit > 3.0:
            self.hits_dados_recente = max(0, self.hits_dados_recente - 1)
        
        # Atualiza timers
        self.tempo_desde_dano += dt
        self.tempo_desde_hit += dt
        
        # Medo
        if "DETERMINADO" not in self.tracos and "FRIO" not in self.tracos:
            if hp_pct < 0.15:
                self.medo = min(1.0, self.medo + 0.08 * dt * 60)
            elif hp_pct < 0.3:
                self.medo = min(0.8, self.medo + 0.03 * dt * 60)
            if self.hits_recebidos_recente >= 3:
                self.medo = min(1.0, self.medo + 0.15)
        
        # Confiança
        hp_diff = hp_pct - inimigo_hp_pct
        target_conf = 0.5 + hp_diff * 0.4
        self.confianca += (target_conf - self.confianca) * 0.05 * dt * 60
        self.confianca = max(0.1, min(1.0, self.confianca))
        
        # Excitação
        if distancia < 3.0:
            self.excitacao = min(1.0, self.excitacao + 0.02 * dt * 60)
        if self.combo_atual > 2:
            self.excitacao = min(1.0, self.excitacao + 0.05)
        
        # Tédio
        if distancia > 8.0 and tempo_combate > 10.0:
            self.tedio = min(1.0, self.tedio + 0.01 * dt * 60)
        
        # Adrenalina
        if hp_pct < 0.2 or (distancia < 2.0 and self.raiva > 0.5):
            self.adrenalina = min(1.0, self.adrenalina + 0.04 * dt * 60)
        
        # Atualiza cooldown de humor
        if self.cd_mudanca_humor > 0:
            self.cd_mudanca_humor -= dt
        
        return dir_circular_cd
    
    def atualizar_humor(self):
        """Atualiza humor baseado nas emoções"""
        if self.cd_mudanca_humor > 0:
            return
        
        novo_humor = self.humor
        p = self.parent
        
        if self.raiva > 0.7:
            novo_humor = "FURIOSO"
        elif self.medo > 0.6:
            novo_humor = "ASSUSTADO"
        elif self.medo > 0.4 and self.confianca < 0.3:
            novo_humor = "NERVOSO"
        elif self.adrenalina > 0.6:
            novo_humor = "DETERMINADO"
        elif self.confianca > 0.7:
            novo_humor = "CONFIANTE"
        elif self.frustracao > 0.5:
            novo_humor = "FURIOSO" if random.random() < 0.5 else "NERVOSO"
        elif self.excitacao > 0.6:
            novo_humor = "ANIMADO"
        elif self.tedio > 0.5:
            novo_humor = "ENTEDIADO"
        elif self.confianca > 0.4 and self.raiva < 0.3 and self.medo < 0.3:
            novo_humor = "CALMO"
        elif p.vida < p.vida_max * 0.2:
            novo_humor = "DESESPERADO"
        else:
            novo_humor = "FOCADO"
        
        if novo_humor != self.humor:
            self.humor = novo_humor
            self.cd_mudanca_humor = random.uniform(2.0, 5.0)
    
    def reagir_ao_dano(self, dano):
        """Reações emocionais ao dano recebido"""
        self.tempo_desde_dano = 0.0
        self.hits_recebidos_total += 1
        self.hits_recebidos_recente += 1
        self.combo_atual = 0
        
        if "VINGATIVO" in self.tracos:
            self.raiva = min(1.0, self.raiva + 0.25)
        if "BERSERKER" in self.tracos or "BERSERKER_RAGE" in self.tracos:
            self.raiva = min(1.0, self.raiva + 0.15)
            self.adrenalina = min(1.0, self.adrenalina + 0.2)
        if "FURIOSO" in self.tracos:
            self.raiva = min(1.0, self.raiva + 0.2)
        if "COVARDE" in self.tracos or "MEDROSO" in self.tracos:
            self.medo = min(1.0, self.medo + 0.2)
        if "PARANOICO" in self.tracos:
            self.medo = min(1.0, self.medo + 0.15)
        if "FRIO" not in self.tracos:
            self.raiva = min(1.0, self.raiva + 0.05)
        self.frustracao = min(1.0, self.frustracao + 0.1)
    
    def on_hit_dado(self):
        """Quando acerta um golpe"""
        self.hits_dados_total += 1
        self.hits_dados_recente += 1
        self.tempo_desde_hit = 0.0
        self.combo_atual += 1
        self.max_combo = max(self.max_combo, self.combo_atual)
        
        self.confianca = min(1.0, self.confianca + 0.05)
        self.frustracao = max(0, self.frustracao - 0.1)
        self.excitacao = min(1.0, self.excitacao + 0.1)
    
    def on_momento_cinematografico(self, tipo, iniciando):
        """Callback quando momento cinematográfico começa/termina"""
        if iniciando:
            if tipo == "CLASH":
                self.excitacao = 1.0
                self.adrenalina = min(1.0, self.adrenalina + 0.3)
            elif tipo == "STANDOFF":
                self.confianca = 0.5
            elif tipo == "FINAL_SHOWDOWN":
                self.adrenalina = 1.0
                self.excitacao = 1.0
                self.medo = 0.0
            elif tipo == "FACE_OFF":
                self.excitacao = min(1.0, self.excitacao + 0.2)
    
    def get_modificadores_humor(self):
        """Retorna modificadores baseados no humor atual"""
        from ai.personalities import HUMORES
        return HUMORES.get(self.humor, HUMORES["CALMO"])
    
    def get_estado(self):
        """Retorna o estado emocional atual"""
        return {
            "medo": self.medo,
            "raiva": self.raiva,
            "confianca": self.confianca,
            "frustracao": self.frustracao,
            "adrenalina": self.adrenalina,
            "excitacao": self.excitacao,
            "tedio": self.tedio,
            "humor": self.humor,
            "combo_atual": self.combo_atual,
            "max_combo": self.max_combo,
        }
