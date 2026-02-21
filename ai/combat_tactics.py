"""
NEURAL FIGHTS - Sistema de Táticas de Combate v8.0
Gerencia leitura do oponente, janelas de oportunidade, baiting e momentum.
"""

import math
import random


class CombatTacticsSystem:
    """
    Sistema de táticas de combate para IA.
    Gerencia leitura do oponente, janelas de ataque, baiting e momentum.
    """
    
    def __init__(self, parent, tracos, estilo_luta):
        self.parent = parent
        self.tracos = tracos
        self.estilo_luta = estilo_luta
        
        # Leitura do oponente
        self.leitura_oponente = {
            "ataque_iminente": False,
            "direcao_provavel": 0.0,
            "tempo_para_ataque": 0.0,
            "padrao_movimento": [],  # Últimos 15 movimentos
            "padrao_ataque": [],     # Últimos 10 ataques
            "tendencia_esquerda": 0.5,
            "frequencia_pulo": 0.0,
            "agressividade_percebida": 0.5,
            "previsibilidade": 0.5,  # Quão previsível é o oponente
        }
        
        # Sistema de janelas de oportunidade
        self.janela_ataque = {
            "aberta": False,
            "tipo": None,  # "pos_ataque", "recuperando", "fora_alcance", "pulo", "fugindo", "pos_esquiva"
            "duracao": 0.0,
            "qualidade": 0.0,  # 0-1, quão boa é a janela
        }
        
        # Sistema de baiting (isca/finta)
        self.bait_state = {
            "ativo": False,
            "tipo": None,  # "recuo_falso", "abertura_falsa", "skill_falsa"
            "timer": 0.0,
            "sucesso_count": 0,
            "falha_count": 0,
        }
        
        # Momentum e pressão
        self.momentum = 0.0  # -1 (perdendo) a 1 (ganhando)
        self.pressao_aplicada = 0.0  # Quanto está pressionando
        self.pressao_recebida = 0.0  # Quanto está sendo pressionado
        
        # Sistema de combos e follow-ups
        self.combo_state = {
            "em_combo": False,
            "hits_combo": 0,
            "ultimo_tipo_ataque": None,
            "pode_followup": False,
            "timer_followup": 0.0,
        }
        
        # Timing humano
        self.tempo_reacao_base = random.uniform(0.12, 0.25)
        self.variacao_timing = random.uniform(0.05, 0.15)
    
    def atualizar_leitura(self, dt, distancia, inimigo):
        """Lê e antecipa os movimentos do oponente como um humano faria"""
        leitura = self.leitura_oponente
        
        # Detecta se oponente está preparando ataque
        ataque_prep = False
        if hasattr(inimigo, 'atacando') and inimigo.atacando:
            ataque_prep = True
        if hasattr(inimigo, 'cooldown_ataque') and inimigo.cooldown_ataque < 0.2:
            ataque_prep = True
        if hasattr(inimigo, 'ai') and inimigo.ai:
            ai_ini = inimigo.ai
            if ai_ini.acao_atual in ["MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "CONTRA_ATAQUE"]:
                ataque_prep = True
        
        leitura["ataque_iminente"] = ataque_prep
        
        # Calcula direção provável do ataque
        if inimigo.vel[0] != 0 or inimigo.vel[1] != 0:
            leitura["direcao_provavel"] = math.degrees(math.atan2(inimigo.vel[1], inimigo.vel[0]))
        
        # Registra padrão de movimento
        mov_atual = (inimigo.vel[0], inimigo.vel[1], inimigo.z)
        leitura["padrao_movimento"].append(mov_atual)
        if len(leitura["padrao_movimento"]) > 15:
            leitura["padrao_movimento"].pop(0)
        
        # Analisa tendência lateral
        if len(leitura["padrao_movimento"]) >= 5:
            lateral_sum = sum(m[0] for m in leitura["padrao_movimento"][-5:])
            if lateral_sum > 0:
                leitura["tendencia_esquerda"] = max(0.2, leitura["tendencia_esquerda"] - 0.02)
            else:
                leitura["tendencia_esquerda"] = min(0.8, leitura["tendencia_esquerda"] + 0.02)
        
        # Detecta frequência de pulos
        pulos_recentes = sum(1 for m in leitura["padrao_movimento"] if m[2] > 0)
        leitura["frequencia_pulo"] = pulos_recentes / max(1, len(leitura["padrao_movimento"]))
        
        # Calcula previsibilidade do oponente
        if len(leitura["padrao_movimento"]) >= 8:
            variacoes = []
            for i in range(1, min(8, len(leitura["padrao_movimento"]))):
                m1 = leitura["padrao_movimento"][-i]
                m2 = leitura["padrao_movimento"][-i-1]
                var = abs(m1[0] - m2[0]) + abs(m1[1] - m2[1])
                variacoes.append(var)
            
            media_variacao = sum(variacoes) / len(variacoes) if variacoes else 1.0
            # Menos variação = mais previsível
            leitura["previsibilidade"] = max(0.2, min(0.9, 1.0 - media_variacao * 0.3))
    
    def atualizar_janelas(self, dt, distancia, inimigo):
        """Atualiza janelas de oportunidade para ataque"""
        janela = self.janela_ataque
        
        # Decay de janela atual
        if janela["aberta"]:
            janela["duracao"] -= dt
            if janela["duracao"] <= 0:
                janela["aberta"] = False
                janela["tipo"] = None
        
        # Detecta novas janelas
        # 1. Pós-ataque do oponente (recovery)
        if hasattr(inimigo, 'atacando') and not inimigo.atacando:
            if hasattr(inimigo, 'cooldown_ataque') and 0 < inimigo.cooldown_ataque < 0.5:
                if not janela["aberta"] or janela["qualidade"] < 0.7:
                    janela["aberta"] = True
                    janela["tipo"] = "pos_ataque"
                    janela["duracao"] = inimigo.cooldown_ataque
                    janela["qualidade"] = 0.8 - (distancia * 0.1)
        
        # 2. Oponente no ar (vulnerável)
        if hasattr(inimigo, 'z') and inimigo.z > 0.3:
            if not janela["aberta"] or janela["qualidade"] < 0.6:
                janela["aberta"] = True
                janela["tipo"] = "pulo"
                janela["duracao"] = 0.5
                janela["qualidade"] = 0.6
        
        # 3. Oponente usando skill (cast time)
        if hasattr(inimigo, 'usando_skill') and inimigo.usando_skill:
            if not janela["aberta"] or janela["qualidade"] < 0.75:
                janela["aberta"] = True
                janela["tipo"] = "casting"
                janela["duracao"] = 0.8
                janela["qualidade"] = 0.75
    
    def atualizar_momentum(self, dt, distancia, inimigo, acao_atual, 
                           hits_dados_recente, hits_recebidos_recente):
        """Atualiza momentum e pressão do combate"""
        # Decay natural
        self.momentum *= 0.995
        
        # Baseado em hits recentes
        diff_hits = hits_dados_recente - hits_recebidos_recente
        self.momentum += diff_hits * 0.05
        
        # Baseado em HP
        p = self.parent
        meu_hp = p.vida / p.vida_max
        ini_hp = inimigo.vida / inimigo.vida_max
        hp_diff = meu_hp - ini_hp
        self.momentum += hp_diff * 0.02
        
        # Baseado em pressão
        if distancia < 3.0:
            if acao_atual in ["MATAR", "PRESSIONAR", "ESMAGAR"]:
                self.pressao_aplicada = min(1.0, self.pressao_aplicada + dt * 0.5)
            else:
                self.pressao_aplicada = max(0.0, self.pressao_aplicada - dt * 0.3)
        else:
            self.pressao_aplicada = max(0.0, self.pressao_aplicada - dt * 0.5)
        
        # Pressão recebida
        if hasattr(inimigo, 'ai') and inimigo.ai:
            ai_ini = inimigo.ai
            if distancia < 3.0 and ai_ini.acao_atual in ["MATAR", "PRESSIONAR", "ESMAGAR"]:
                self.pressao_recebida = min(1.0, self.pressao_recebida + dt * 0.5)
            else:
                self.pressao_recebida = max(0.0, self.pressao_recebida - dt * 0.3)
        
        # Clamp momentum
        self.momentum = max(-1.0, min(1.0, self.momentum))
    
    def atualizar_combo_state(self, dt):
        """Atualiza estado do sistema de combos"""
        combo = self.combo_state
        
        if combo["timer_followup"] > 0:
            combo["timer_followup"] -= dt
            if combo["timer_followup"] <= 0:
                combo["pode_followup"] = False
                combo["em_combo"] = False
    
    def processar_baiting(self, dt, distancia, inimigo, medo, confianca):
        """Processa comportamento de baiting (fintas)"""
        bait = self.bait_state
        
        # Condições para tentar bait
        pode_bait = (
            distancia < 6.0 and
            distancia > 2.5 and
            confianca > 0.4 and
            medo < 0.5 and
            not bait["ativo"]
        )
        
        # Chance de iniciar bait baseada em traços
        chance_bait = 0.01
        if "ASTUTO" in self.tracos or "ESTRATEGISTA" in self.tracos:
            chance_bait = 0.03
        if "TRAPACEIRO" in self.tracos:
            chance_bait = 0.04
        if self.estilo_luta in ["TECHNICAL", "MIND_GAMES"]:
            chance_bait *= 2.0
        
        if pode_bait and random.random() < chance_bait:
            bait["ativo"] = True
            bait["tipo"] = random.choice(["recuo_falso", "abertura_falsa"])
            bait["timer"] = random.uniform(0.3, 0.6)
            return True  # Indica que está em modo bait
        
        # Processa bait ativo
        if bait["ativo"]:
            bait["timer"] -= dt
            if bait["timer"] <= 0:
                bait["ativo"] = False
            return True
        
        return False
    
    def on_hit_dado(self):
        """Quando acerta um golpe"""
        combo = self.combo_state
        combo["em_combo"] = True
        combo["hits_combo"] += 1
        combo["pode_followup"] = True
        combo["timer_followup"] = 0.5
        
        # Momentum positivo
        self.momentum = min(1.0, self.momentum + 0.15)
        
        # Combo master continua pressionando
        if "COMBO_MASTER" in self.tracos or "MESTRE_COMBO" in self.tracos:
            combo["timer_followup"] = 0.7
    
    def on_hit_recebido(self, dano):
        """Quando recebe dano"""
        self.momentum = max(-1.0, self.momentum - 0.1)
        
        # Quebra combo
        self.combo_state["em_combo"] = False
        self.combo_state["hits_combo"] = 0
    
    def on_esquiva_sucesso(self):
        """Quando desvia com sucesso"""
        self.janela_ataque["aberta"] = True
        self.janela_ataque["tipo"] = "pos_esquiva"
        self.janela_ataque["qualidade"] = 0.85
        self.janela_ataque["duracao"] = 0.5
    
    def on_inimigo_fugiu(self):
        """Quando inimigo foge"""
        self.momentum = min(1.0, self.momentum + 0.1)
        self.janela_ataque["aberta"] = True
        self.janela_ataque["tipo"] = "fugindo"
        self.janela_ataque["qualidade"] = 0.6
        self.janela_ataque["duracao"] = 1.0
    
    def get_modificadores(self, distancia, inimigo_hp_pct):
        """Retorna modificadores baseados no momentum e leitura"""
        mods = {
            "agressividade_bonus": 0.0,
            "defensividade_bonus": 0.0,
            "urgencia": 0.0,
        }
        
        # Modificadores de momentum
        if self.momentum > 0.5:
            mods["agressividade_bonus"] += 0.2
            mods["urgencia"] += 0.1
        elif self.momentum < -0.5:
            mods["defensividade_bonus"] += 0.2
        
        # Modificadores de leitura
        if self.leitura_oponente["previsibilidade"] > 0.7:
            mods["agressividade_bonus"] += 0.15
        
        if self.leitura_oponente["ataque_iminente"]:
            mods["defensividade_bonus"] += 0.3
        
        return mods
    
    def get_estado(self):
        """Retorna o estado tático atual"""
        return {
            "leitura": self.leitura_oponente.copy(),
            "janela": self.janela_ataque.copy(),
            "bait": self.bait_state.copy(),
            "momentum": self.momentum,
            "pressao_aplicada": self.pressao_aplicada,
            "pressao_recebida": self.pressao_recebida,
            "combo": self.combo_state.copy(),
        }
