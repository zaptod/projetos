#!/usr/bin/env python3
"""
=============================================================================
NEURAL FIGHTS - Headless Battle Test Suite v1.0
=============================================================================
Script que cria armas e personagens diversos, coloca-os para lutar em modo
headless (sem interface gráfica) com debug completo.

Uso:
    python test_headless_battle.py

Funcionalidades:
    - Gera armas aleatórias de todas as raridades
    - Gera personagens de todas as classes
    - Executa lutas em modo headless
    - Debug completo de skills, IA, combate
    - Detecta e reporta erros
=============================================================================
"""

import sys
import os
import random
import traceback
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurações de debug
DEBUG_AI = True
DEBUG_SKILLS = True
DEBUG_COMBAT = True
DEBUG_SUMMONS = True
DEBUG_STRATEGY = True
VERBOSE = True

# Cores para terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def log(msg: str, level: str = "INFO"):
    """Logger colorido"""
    colors = {
        "INFO": Colors.CYAN,
        "OK": Colors.GREEN,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "DEBUG": Colors.BLUE,
        "HEADER": Colors.HEADER + Colors.BOLD,
    }
    color = colors.get(level, Colors.END)
    print(f"{color}[{level}]{Colors.END} {msg}")


def log_header(title: str):
    """Imprime cabeçalho destacado"""
    print()
    print(f"{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {title}{Colors.END}")
    print(f"{Colors.HEADER}{'='*70}{Colors.END}")
    print()


# =============================================================================
# GERADOR DE ARMAS ALEATÓRIAS
# =============================================================================

def gerar_arma_aleatoria(nome: str = None, raridade: str = None) -> dict:
    """Gera uma arma completamente aleatória"""
    from models.constants import (
        LISTA_RARIDADES, TIPOS_ARMA, ENCANTAMENTOS, 
        LISTA_ENCANTAMENTOS, PASSIVAS_ARMA, get_raridade_data
    )
    from core.skills import SKILL_DB
    
    # Raridade
    if raridade is None:
        raridade = random.choice(LISTA_RARIDADES)
    rar_data = get_raridade_data(raridade)
    
    # Tipo de arma
    tipo = random.choice(list(TIPOS_ARMA.keys()))
    tipo_data = TIPOS_ARMA[tipo]
    
    # Nome automático
    prefixos = ["Espada", "Lança", "Machado", "Adaga", "Cajado", "Arco", "Mangual", "Katana"]
    sufixos = ["do Caos", "Flamejante", "Gélida", "Sombria", "Divina", "Anciã", "Brutal", "Mística"]
    if nome is None:
        nome = f"{random.choice(prefixos)} {random.choice(sufixos)} #{random.randint(1, 999)}"
    
    # Habilidades baseadas na raridade
    num_skills = rar_data.get("slots_habilidade", 1)
    skills_disponiveis = [s for s in SKILL_DB.keys() if SKILL_DB[s].get("tipo", "NADA") != "NADA"]
    habilidades = []
    for _ in range(min(num_skills, len(skills_disponiveis))):
        skill = random.choice(skills_disponiveis)
        skills_disponiveis.remove(skill)
        custo = SKILL_DB[skill].get("custo", 20.0)
        habilidades.append({"nome": skill, "custo": custo})
    
    # Encantamentos
    num_ench = random.randint(0, rar_data.get("max_encantamentos", 0))
    encantamentos = random.sample(LISTA_ENCANTAMENTOS, min(num_ench, len(LISTA_ENCANTAMENTOS)))
    
    # Passiva
    passiva = None
    passiva_tipo = rar_data.get("passiva")
    if passiva_tipo and passiva_tipo in PASSIVAS_ARMA:
        passiva = random.choice(PASSIVAS_ARMA[passiva_tipo])
    
    # Geometria baseada no tipo
    arma = {
        "nome": nome,
        "tipo": tipo,
        "dano": round(random.uniform(2.0, 10.0), 1),
        "peso": round(random.uniform(1.0, 8.0), 1),
        "raridade": raridade,
        "comp_cabo": random.uniform(10.0, 40.0),
        "comp_lamina": random.uniform(30.0, 100.0),
        "largura": random.uniform(3.0, 15.0),
        "distancia": 20.0,
        "comp_corrente": random.uniform(0.0, 50.0) if tipo == "Corrente" else 0.0,
        "comp_ponta": random.uniform(5.0, 20.0) if tipo == "Corrente" else 0.0,
        "largura_ponta": random.uniform(3.0, 10.0) if tipo == "Corrente" else 0.0,
        "tamanho_projetil": random.uniform(5.0, 20.0) if tipo == "Arremesso" else 0.0,
        "quantidade": random.randint(1, 5) if tipo == "Arremesso" else 1,
        "tamanho_arco": random.uniform(30.0, 60.0) if tipo == "Arco" else 0.0,
        "forca_arco": random.uniform(5.0, 15.0) if tipo == "Arco" else 0.0,
        "tamanho_flecha": random.uniform(30.0, 50.0) if tipo == "Arco" else 0.0,
        "quantidade_orbitais": random.randint(1, 5) if tipo == "Orbital" else 1,
        "tamanho": random.uniform(5.0, 20.0),
        "distancia_max": random.uniform(5.0, 15.0) if tipo == "Magica" else 0.0,
        "separacao": random.uniform(10.0, 30.0) if tipo == "Dupla" else 0.0,
        "forma1_cabo": random.uniform(10.0, 25.0),
        "forma1_lamina": random.uniform(30.0, 60.0),
        "forma2_cabo": random.uniform(10.0, 25.0),
        "forma2_lamina": random.uniform(30.0, 60.0),
        "r": random.randint(50, 255),
        "g": random.randint(50, 255),
        "b": random.randint(50, 255),
        "estilo": tipo_data.get("estilos", ["Misto"])[0] if tipo_data.get("estilos") else "Misto",
        "cabo_dano": random.random() < 0.3,
        "habilidades": habilidades,
        "encantamentos": encantamentos,
        "passiva": passiva,
        "critico": round(random.uniform(0.0, 10.0), 1),
        "velocidade_ataque": round(random.uniform(0.7, 1.5), 2),
        "afinidade_elemento": random.choice([None, "FOGO", "GELO", "RAIO", "VENTO", "TERRA", "TREVAS", "LUZ"]),
        "durabilidade": 100.0,
        "durabilidade_max": 100.0,
        "habilidade": habilidades[0]["nome"] if habilidades else "Nenhuma",
        "custo_mana": habilidades[0]["custo"] if habilidades else 0.0,
    }
    
    return arma


# =============================================================================
# GERADOR DE PERSONAGENS ALEATÓRIOS
# =============================================================================

def gerar_personagem_aleatorio(nome: str = None, classe: str = None, 
                                personalidade: str = None, arma: dict = None) -> dict:
    """Gera um personagem completamente aleatório"""
    from models.constants import LISTA_CLASSES
    from ai.personalities import LISTA_PERSONALIDADES
    
    nomes = [
        "Kael", "Luna", "Draven", "Aria", "Zed", "Nova", "Riven", "Sylas",
        "Ahri", "Darius", "Lux", "Talon", "Jinx", "Sett", "Akali", "Yasuo",
        "Pyke", "Kayn", "Qiyana", "Aphelios", "Viego", "Yone", "Gwen", "Nilah"
    ]
    
    if nome is None:
        nome = f"{random.choice(nomes)}_{random.randint(1, 999)}"
    
    if classe is None:
        classe = random.choice(LISTA_CLASSES)
    
    if personalidade is None:
        personalidade = random.choice(LISTA_PERSONALIDADES)
    
    if arma is None:
        arma = gerar_arma_aleatoria()
    
    personagem = {
        "nome": nome,
        "tamanho": round(random.uniform(1.5, 2.2), 2),
        "forca": round(random.uniform(3.0, 10.0), 1),
        "mana": round(random.uniform(3.0, 10.0), 1),
        "nome_arma": arma["nome"],
        "cor_r": random.randint(50, 255),
        "cor_g": random.randint(50, 255),
        "cor_b": random.randint(50, 255),
        "classe": classe,
        "personalidade": personalidade,
        "_arma_obj": arma,  # Referência interna para a arma
    }
    
    return personagem


# =============================================================================
# SIMULADOR HEADLESS
# =============================================================================

class HeadlessBattle:
    """Simulador de batalha sem interface gráfica"""
    
    def __init__(self, char1_data: dict, char2_data: dict, 
                 arma1_data: dict, arma2_data: dict,
                 max_frames: int = 3000, debug: bool = True):
        self.char1_data = char1_data
        self.char2_data = char2_data
        self.arma1_data = arma1_data
        self.arma2_data = arma2_data
        self.max_frames = max_frames
        self.debug = debug
        
        self.p1 = None
        self.p2 = None
        self.frame = 0
        self.vencedor = None
        self.erros = []
        self.stats = {
            "skills_usadas_p1": 0,
            "skills_usadas_p2": 0,
            "dano_causado_p1": 0.0,
            "dano_causado_p2": 0.0,
            "summons_criados": 0,
            "projeteis_criados": 0,
            "beams_criados": 0,
            "areas_criadas": 0,
        }
        
        # Buffers de combate
        self.projeteis = []
        self.beams = []
        self.areas = []
        self.summons = []
        self.traps = []
    
    def _criar_arma(self, arma_data: dict):
        """Cria objeto Arma a partir dos dados"""
        from models import Arma
        
        try:
            arma = Arma(
                nome=arma_data["nome"],
                tipo=arma_data.get("tipo", "Reta"),
                dano=arma_data.get("dano", 5.0),
                peso=arma_data.get("peso", 3.0),
                comp_cabo=arma_data.get("comp_cabo", 15.0),
                comp_lamina=arma_data.get("comp_lamina", 50.0),
                largura=arma_data.get("largura", 8.0),
                distancia=arma_data.get("distancia", 20.0),
                r=arma_data.get("r", 200),
                g=arma_data.get("g", 200),
                b=arma_data.get("b", 200),
                estilo=arma_data.get("estilo", "Misto"),
                cabo_dano=arma_data.get("cabo_dano", False),
                habilidade=arma_data.get("habilidade", "Nenhuma"),
                custo_mana=arma_data.get("custo_mana", 0.0),
                raridade=arma_data.get("raridade", "Comum"),
                habilidades=arma_data.get("habilidades", []),
                encantamentos=arma_data.get("encantamentos", []),
                passiva=arma_data.get("passiva"),
                critico=arma_data.get("critico", 0.0),
                velocidade_ataque=arma_data.get("velocidade_ataque", 1.0),
                afinidade_elemento=arma_data.get("afinidade_elemento"),
                durabilidade=arma_data.get("durabilidade", 100.0),
                durabilidade_max=arma_data.get("durabilidade_max", 100.0),
                comp_corrente=arma_data.get("comp_corrente", 0.0),
                comp_ponta=arma_data.get("comp_ponta", 0.0),
                largura_ponta=arma_data.get("largura_ponta", 0.0),
                tamanho_projetil=arma_data.get("tamanho_projetil", 0.0),
                quantidade=arma_data.get("quantidade", 1),
                tamanho_arco=arma_data.get("tamanho_arco", 0.0),
                forca_arco=arma_data.get("forca_arco", 0.0),
                tamanho_flecha=arma_data.get("tamanho_flecha", 0.0),
                quantidade_orbitais=arma_data.get("quantidade_orbitais", 1),
                tamanho=arma_data.get("tamanho", 8.0),
                distancia_max=arma_data.get("distancia_max", 0.0),
                separacao=arma_data.get("separacao", 0.0),
                forma1_cabo=arma_data.get("forma1_cabo", 0.0),
                forma1_lamina=arma_data.get("forma1_lamina", 0.0),
                forma2_cabo=arma_data.get("forma2_cabo", 0.0),
                forma2_lamina=arma_data.get("forma2_lamina", 0.0),
            )
            return arma
        except Exception as e:
            self.erros.append(f"Erro ao criar arma {arma_data['nome']}: {e}")
            log(f"Erro ao criar arma: {e}", "ERROR")
            traceback.print_exc()
            return None
    
    def _criar_personagem(self, char_data: dict, arma, pos_x: float, pos_y: float):
        """Cria objeto Personagem/Lutador a partir dos dados"""
        from models import Personagem
        from core.entities import Lutador
        
        try:
            # Cria objeto Personagem
            peso_arma = arma.peso if arma else 0
            personagem = Personagem(
                nome=char_data["nome"],
                tamanho=char_data.get("tamanho", 1.7),
                forca=char_data.get("forca", 5.0),
                mana=char_data.get("mana", 5.0),
                nome_arma=char_data.get("nome_arma", ""),
                peso_arma_cache=peso_arma,
                r=char_data.get("cor_r", 200),
                g=char_data.get("cor_g", 50),
                b=char_data.get("cor_b", 50),
                classe=char_data.get("classe", "Guerreiro (Força Bruta)"),
                personalidade=char_data.get("personalidade", "Aleatório"),
            )
            
            # Anexa arma
            personagem.arma_obj = arma
            
            # Cria Lutador
            lutador = Lutador(personagem, pos_x, pos_y)
            
            return lutador
            
        except Exception as e:
            self.erros.append(f"Erro ao criar personagem {char_data['nome']}: {e}")
            log(f"Erro ao criar personagem: {e}", "ERROR")
            traceback.print_exc()
            return None
    
    def iniciar(self) -> bool:
        """Inicializa a batalha"""
        log_header("INICIALIZANDO BATALHA HEADLESS")
        
        try:
            # Cria armas
            log(f"Criando arma 1: {self.arma1_data['nome']} ({self.arma1_data.get('raridade', 'Comum')})")
            arma1 = self._criar_arma(self.arma1_data)
            
            log(f"Criando arma 2: {self.arma2_data['nome']} ({self.arma2_data.get('raridade', 'Comum')})")
            arma2 = self._criar_arma(self.arma2_data)
            
            if not arma1 or not arma2:
                return False
            
            # Cria personagens
            log(f"Criando lutador 1: {self.char1_data['nome']} ({self.char1_data.get('classe', '?')})")
            self.p1 = self._criar_personagem(self.char1_data, arma1, 5.0, 10.0)
            
            log(f"Criando lutador 2: {self.char2_data['nome']} ({self.char2_data.get('classe', '?')})")
            self.p2 = self._criar_personagem(self.char2_data, arma2, 25.0, 10.0)
            
            if not self.p1 or not self.p2:
                return False
            
            # Info dos lutadores
            log(f"P1: {self.p1.dados.nome} - HP={self.p1.vida:.0f}, Mana={self.p1.mana:.0f}", "OK")
            log(f"   Classe: {self.p1.classe_nome}", "DEBUG")
            log(f"   Skills Arma: {[s['nome'] for s in self.p1.skills_arma]}", "DEBUG")
            log(f"   Skills Classe: {[s['nome'] for s in self.p1.skills_classe]}", "DEBUG")
            
            log(f"P2: {self.p2.dados.nome} - HP={self.p2.vida:.0f}, Mana={self.p2.mana:.0f}", "OK")
            log(f"   Classe: {self.p2.classe_nome}", "DEBUG")
            log(f"   Skills Arma: {[s['nome'] for s in self.p2.skills_arma]}", "DEBUG")
            log(f"   Skills Classe: {[s['nome'] for s in self.p2.skills_classe]}", "DEBUG")
            
            return True
            
        except Exception as e:
            self.erros.append(f"Erro na inicialização: {e}")
            log(f"Erro na inicialização: {e}", "ERROR")
            traceback.print_exc()
            return False
    
    def _coletar_buffers(self, lutador):
        """Coleta objetos dos buffers do lutador"""
        # Projéteis
        if hasattr(lutador, 'buffer_projeteis') and lutador.buffer_projeteis:
            self.projeteis.extend(lutador.buffer_projeteis)
            self.stats["projeteis_criados"] += len(lutador.buffer_projeteis)
            if DEBUG_SKILLS:
                for p in lutador.buffer_projeteis:
                    log(f"[PROJETIL] {lutador.dados.nome} criou {p.nome}", "DEBUG")
            lutador.buffer_projeteis = []
        
        # Beams
        if hasattr(lutador, 'buffer_beams') and lutador.buffer_beams:
            self.beams.extend(lutador.buffer_beams)
            self.stats["beams_criados"] += len(lutador.buffer_beams)
            if DEBUG_SKILLS:
                for b in lutador.buffer_beams:
                    log(f"[BEAM] {lutador.dados.nome} criou {b.nome}", "DEBUG")
            lutador.buffer_beams = []
        
        # Áreas
        if hasattr(lutador, 'buffer_areas') and lutador.buffer_areas:
            self.areas.extend(lutador.buffer_areas)
            self.stats["areas_criadas"] += len(lutador.buffer_areas)
            if DEBUG_SKILLS:
                for a in lutador.buffer_areas:
                    log(f"[AREA] {lutador.dados.nome} criou {a.nome}", "DEBUG")
            lutador.buffer_areas = []
        
        # Summons
        if hasattr(lutador, 'buffer_summons') and lutador.buffer_summons:
            self.summons.extend(lutador.buffer_summons)
            self.stats["summons_criados"] += len(lutador.buffer_summons)
            if DEBUG_SUMMONS:
                for s in lutador.buffer_summons:
                    log(f"[SUMMON] {lutador.dados.nome} invocou {s.nome} em ({s.x:.1f}, {s.y:.1f})", "DEBUG")
            lutador.buffer_summons = []
        
        # Traps
        if hasattr(lutador, 'buffer_traps') and lutador.buffer_traps:
            self.traps.extend(lutador.buffer_traps)
            if DEBUG_SKILLS:
                for t in lutador.buffer_traps:
                    log(f"[TRAP] {lutador.dados.nome} colocou {t.nome}", "DEBUG")
            lutador.buffer_traps = []
    
    def _atualizar_projeteis(self, dt: float):
        """Atualiza projéteis"""
        for proj in self.projeteis[:]:
            try:
                alvos = [self.p1, self.p2]
                if hasattr(proj, 'atualizar'):
                    import inspect
                    sig = inspect.signature(proj.atualizar)
                    if len(sig.parameters) > 1:
                        proj.atualizar(dt, alvos)
                    else:
                        proj.atualizar(dt)
                
                # Remove inativos
                if not proj.ativo:
                    self.projeteis.remove(proj)
                    continue
                
                # Verifica colisão
                for alvo in alvos:
                    if alvo == proj.dono or alvo.morto:
                        continue
                    
                    import math
                    dist = math.hypot(alvo.pos[0] - proj.x, alvo.pos[1] - proj.y)
                    if dist < (proj.raio + alvo.raio_fisico):
                        dano = proj.dano
                        alvo.tomar_dano(dano, 0, 0, proj.tipo_efeito if hasattr(proj, 'tipo_efeito') else "NORMAL")
                        
                        if proj.dono == self.p1:
                            self.stats["dano_causado_p1"] += dano
                        else:
                            self.stats["dano_causado_p2"] += dano
                        
                        if DEBUG_COMBAT:
                            log(f"[HIT] {proj.nome} atingiu {alvo.dados.nome} (-{dano:.1f} HP)", "DEBUG")
                        
                        proj.ativo = False
                        if proj in self.projeteis:
                            self.projeteis.remove(proj)
                        break
                        
            except Exception as e:
                self.erros.append(f"Erro ao atualizar projétil: {e}")
                if proj in self.projeteis:
                    self.projeteis.remove(proj)
    
    def _atualizar_beams(self, dt: float):
        """Atualiza beams"""
        for beam in self.beams[:]:
            try:
                if hasattr(beam, 'atualizar'):
                    beam.atualizar(dt)
                
                if not beam.ativo:
                    self.beams.remove(beam)
                    continue
                
                # Verifica colisão com linha do beam
                # Beam usa x1,y1 -> x2,y2
                for alvo in [self.p1, self.p2]:
                    if alvo == beam.dono or alvo.morto:
                        continue
                    
                    import math
                    # Distância do ponto ao segmento
                    dx = beam.x2 - beam.x1
                    dy = beam.y2 - beam.y1
                    length = math.hypot(dx, dy) or 1
                    
                    t = max(0, min(1, ((alvo.pos[0] - beam.x1) * dx + (alvo.pos[1] - beam.y1) * dy) / (length * length)))
                    closest_x = beam.x1 + t * dx
                    closest_y = beam.y1 + t * dy
                    
                    dist = math.hypot(alvo.pos[0] - closest_x, alvo.pos[1] - closest_y)
                    if dist < (beam.largura / 50 + alvo.raio_fisico):  # largura em pixels, converter
                        dano = beam.dano * dt
                        alvo.tomar_dano(dano, dx/length, dy/length, beam.tipo_efeito if hasattr(beam, 'tipo_efeito') else "NORMAL")
                        
                        if beam.dono == self.p1:
                            self.stats["dano_causado_p1"] += dano
                        else:
                            self.stats["dano_causado_p2"] += dano
                            
            except Exception as e:
                self.erros.append(f"Erro ao atualizar beam: {e}")
                if beam in self.beams:
                    self.beams.remove(beam)
    
    def _atualizar_areas(self, dt: float):
        """Atualiza áreas de efeito"""
        for area in self.areas[:]:
            try:
                if hasattr(area, 'atualizar'):
                    area.atualizar(dt)
                
                if not area.ativo:
                    self.areas.remove(area)
                    continue
                
                # Verifica colisão
                for alvo in [self.p1, self.p2]:
                    if alvo == area.dono or alvo.morto:
                        continue
                    
                    import math
                    dist = math.hypot(alvo.pos[0] - area.x, alvo.pos[1] - area.y)
                    if dist < area.raio:
                        dano = area.dano * dt
                        alvo.tomar_dano(dano, 0, 0, area.tipo_efeito if hasattr(area, 'tipo_efeito') else "NORMAL")
                        
                        if area.dono == self.p1:
                            self.stats["dano_causado_p1"] += dano
                        else:
                            self.stats["dano_causado_p2"] += dano
                            
            except Exception as e:
                self.erros.append(f"Erro ao atualizar área: {e}")
                if area in self.areas:
                    self.areas.remove(area)
    
    def _atualizar_summons(self, dt: float):
        """Atualiza summons"""
        for summon in self.summons[:]:
            try:
                alvos = [self.p1, self.p2]
                resultados = summon.atualizar(dt, alvos)
                
                for res in resultados:
                    if res.get("tipo") == "ataque":
                        alvo = res["alvo"]
                        dano = res["dano"]
                        alvo.tomar_dano(dano, 0, 0, "NORMAL")
                        
                        if summon.dono == self.p1:
                            self.stats["dano_causado_p1"] += dano
                        else:
                            self.stats["dano_causado_p2"] += dano
                        
                        if DEBUG_SUMMONS:
                            log(f"[SUMMON ATK] {summon.nome} atacou {alvo.dados.nome} (-{dano:.1f})", "DEBUG")
                    
                    elif res.get("revive"):
                        if DEBUG_SUMMONS:
                            log(f"[SUMMON] {summon.nome} REVIVEU!", "DEBUG")
                
                if not summon.ativo:
                    self.summons.remove(summon)
                    
            except Exception as e:
                self.erros.append(f"Erro ao atualizar summon: {e}")
                if summon in self.summons:
                    self.summons.remove(summon)
    
    def _atualizar_traps(self, dt: float):
        """Atualiza armadilhas"""
        for trap in self.traps[:]:
            try:
                if hasattr(trap, 'atualizar'):
                    trap.atualizar(dt)
                
                if not trap.ativo:
                    self.traps.remove(trap)
                    
            except Exception as e:
                self.erros.append(f"Erro ao atualizar trap: {e}")
                if trap in self.traps:
                    self.traps.remove(trap)
    
    def executar_frame(self, dt: float = 0.016) -> bool:
        """Executa um frame da simulação"""
        try:
            self.frame += 1
            
            # Atualiza IA de ambos os lutadores
            for lutador, inimigo in [(self.p1, self.p2), (self.p2, self.p1)]:
                if lutador.morto:
                    continue
                
                # Atualiza o lutador (método é update, não atualizar)
                try:
                    lutador.update(dt, inimigo)
                except Exception as e:
                    self.erros.append(f"Erro ao atualizar {lutador.dados.nome}: {e}")
                    if self.debug:
                        log(f"Erro em update(): {e}", "ERROR")
                        traceback.print_exc()
                
                # Coleta buffers
                self._coletar_buffers(lutador)
            
            # Atualiza objetos de combate
            self._atualizar_projeteis(dt)
            self._atualizar_beams(dt)
            self._atualizar_areas(dt)
            self._atualizar_summons(dt)
            self._atualizar_traps(dt)
            
            # Verifica vencedor
            if self.p1.morto and not self.p2.morto:
                self.vencedor = self.p2.dados.nome
                return False
            elif self.p2.morto and not self.p1.morto:
                self.vencedor = self.p1.dados.nome
                return False
            elif self.p1.morto and self.p2.morto:
                self.vencedor = "EMPATE"
                return False
            
            # Limite de frames
            if self.frame >= self.max_frames:
                # Vencedor por HP
                if self.p1.vida > self.p2.vida:
                    self.vencedor = f"{self.p1.dados.nome} (HP)"
                elif self.p2.vida > self.p1.vida:
                    self.vencedor = f"{self.p2.dados.nome} (HP)"
                else:
                    self.vencedor = "EMPATE (Tempo)"
                return False
            
            return True
            
        except Exception as e:
            self.erros.append(f"Erro no frame {self.frame}: {e}")
            log(f"Erro no frame {self.frame}: {e}", "ERROR")
            traceback.print_exc()
            return False
    
    def executar(self) -> dict:
        """Executa a batalha completa"""
        if not self.iniciar():
            return {"success": False, "erros": self.erros}
        
        log_header("EXECUTANDO BATALHA")
        
        start_time = time.time()
        dt = 0.016  # ~60 FPS
        
        # Loop principal
        while self.executar_frame(dt):
            # Log periódico
            if self.frame % 500 == 0 and VERBOSE:
                log(f"Frame {self.frame}: P1={self.p1.vida:.0f}HP P2={self.p2.vida:.0f}HP | "
                    f"Proj={len(self.projeteis)} Sum={len(self.summons)}", "INFO")
        
        elapsed = time.time() - start_time
        
        # Resultado
        log_header("RESULTADO DA BATALHA")
        
        resultado = {
            "success": True,
            "vencedor": self.vencedor,
            "frames": self.frame,
            "tempo_real": elapsed,
            "erros": self.erros,
            "stats": self.stats,
            "p1_final": {
                "nome": self.p1.dados.nome,
                "vida": self.p1.vida,
                "vida_max": self.p1.vida_max,
                "morto": self.p1.morto,
            },
            "p2_final": {
                "nome": self.p2.dados.nome,
                "vida": self.p2.vida,
                "vida_max": self.p2.vida_max,
                "morto": self.p2.morto,
            },
        }
        
        log(f"VENCEDOR: {self.vencedor}", "OK")
        log(f"Frames: {self.frame} | Tempo Real: {elapsed:.2f}s", "INFO")
        log(f"P1 Final: {self.p1.dados.nome} - {self.p1.vida:.0f}/{self.p1.vida_max:.0f} HP", "INFO")
        log(f"P2 Final: {self.p2.dados.nome} - {self.p2.vida:.0f}/{self.p2.vida_max:.0f} HP", "INFO")
        
        log(f"\nEstatísticas:", "HEADER")
        log(f"  Projéteis criados: {self.stats['projeteis_criados']}", "DEBUG")
        log(f"  Beams criados: {self.stats['beams_criados']}", "DEBUG")
        log(f"  Áreas criadas: {self.stats['areas_criadas']}", "DEBUG")
        log(f"  Summons criados: {self.stats['summons_criados']}", "DEBUG")
        log(f"  Dano P1: {self.stats['dano_causado_p1']:.0f}", "DEBUG")
        log(f"  Dano P2: {self.stats['dano_causado_p2']:.0f}", "DEBUG")
        
        if self.erros:
            log(f"\nErros encontrados ({len(self.erros)}):", "WARN")
            for erro in self.erros[:10]:  # Máximo 10 erros
                log(f"  - {erro}", "ERROR")
        
        return resultado


# =============================================================================
# SUITE DE TESTES
# =============================================================================

def executar_teste_rapido():
    """Executa um teste rápido com 2 personagens aleatórios"""
    log_header("TESTE RÁPIDO - 1 BATALHA ALEATÓRIA")
    
    # Gera personagens e armas
    arma1 = gerar_arma_aleatoria(raridade="Épico")
    arma2 = gerar_arma_aleatoria(raridade="Épico")
    char1 = gerar_personagem_aleatorio(arma=arma1)
    char2 = gerar_personagem_aleatorio(arma=arma2)
    
    # Executa batalha
    batalha = HeadlessBattle(char1, char2, arma1, arma2, max_frames=2000)
    resultado = batalha.executar()
    
    return resultado


def executar_teste_todas_classes():
    """Testa todas as classes contra um oponente padrão"""
    from models.constants import LISTA_CLASSES
    
    log_header("TESTE DE TODAS AS CLASSES")
    
    resultados = []
    vitorias = {}
    
    for classe in LISTA_CLASSES:
        log(f"\nTestando classe: {classe}", "INFO")
        
        arma1 = gerar_arma_aleatoria(raridade="Raro")
        arma2 = gerar_arma_aleatoria(raridade="Raro")
        char1 = gerar_personagem_aleatorio(nome=f"Test_{classe[:4]}", classe=classe, arma=arma1)
        char2 = gerar_personagem_aleatorio(nome="Oponente", classe="Guerreiro (Força Bruta)", arma=arma2)
        
        batalha = HeadlessBattle(char1, char2, arma1, arma2, max_frames=1500, debug=False)
        resultado = batalha.executar()
        
        resultados.append({
            "classe": classe,
            "resultado": resultado
        })
        
        if resultado["success"]:
            if char1["nome"] in str(resultado["vencedor"]):
                vitorias[classe] = vitorias.get(classe, 0) + 1
    
    # Resumo
    log_header("RESUMO - TESTE DE CLASSES")
    for res in resultados:
        status = "OK" if res["resultado"]["success"] and not res["resultado"]["erros"] else "WARN"
        erros = len(res["resultado"]["erros"])
        log(f"{res['classe']}: Erros={erros}", status)
    
    return resultados


def executar_teste_todas_raridades():
    """Testa todas as raridades de armas"""
    from models.constants import LISTA_RARIDADES
    
    log_header("TESTE DE TODAS AS RARIDADES")
    
    resultados = []
    
    for raridade in LISTA_RARIDADES:
        log(f"\nTestando raridade: {raridade}", "INFO")
        
        arma1 = gerar_arma_aleatoria(raridade=raridade)
        arma2 = gerar_arma_aleatoria(raridade=raridade)
        char1 = gerar_personagem_aleatorio(nome=f"Test_{raridade[:4]}", arma=arma1)
        char2 = gerar_personagem_aleatorio(nome="Oponente", arma=arma2)
        
        batalha = HeadlessBattle(char1, char2, arma1, arma2, max_frames=1500, debug=False)
        resultado = batalha.executar()
        
        resultados.append({
            "raridade": raridade,
            "resultado": resultado
        })
    
    # Resumo
    log_header("RESUMO - TESTE DE RARIDADES")
    for res in resultados:
        status = "OK" if res["resultado"]["success"] and not res["resultado"]["erros"] else "WARN"
        erros = len(res["resultado"]["erros"])
        log(f"{res['raridade']}: Erros={erros}", status)
    
    return resultados


def executar_teste_stress(num_batalhas: int = 10):
    """Executa múltiplas batalhas aleatórias"""
    log_header(f"TESTE DE STRESS - {num_batalhas} BATALHAS")
    
    resultados = []
    total_erros = 0
    total_frames = 0
    
    for i in range(num_batalhas):
        log(f"\nBatalha {i+1}/{num_batalhas}", "INFO")
        
        arma1 = gerar_arma_aleatoria()
        arma2 = gerar_arma_aleatoria()
        char1 = gerar_personagem_aleatorio(arma=arma1)
        char2 = gerar_personagem_aleatorio(arma=arma2)
        
        batalha = HeadlessBattle(char1, char2, arma1, arma2, max_frames=1000, debug=False)
        resultado = batalha.executar()
        
        resultados.append(resultado)
        total_erros += len(resultado.get("erros", []))
        total_frames += resultado.get("frames", 0)
    
    # Resumo
    log_header("RESUMO - TESTE DE STRESS")
    log(f"Batalhas executadas: {num_batalhas}", "INFO")
    log(f"Total de frames: {total_frames}", "INFO")
    log(f"Total de erros: {total_erros}", "WARN" if total_erros > 0 else "OK")
    
    # Erros únicos
    erros_unicos = set()
    for res in resultados:
        for erro in res.get("erros", []):
            erros_unicos.add(erro[:100])  # Trunca para evitar duplicatas longas
    
    if erros_unicos:
        log(f"\nErros únicos encontrados ({len(erros_unicos)}):", "ERROR")
        for erro in list(erros_unicos)[:20]:
            log(f"  - {erro}", "ERROR")
    
    return resultados


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Neural Fights - Headless Battle Test Suite")
    parser.add_argument("--mode", choices=["rapido", "classes", "raridades", "stress", "all"],
                       default="rapido", help="Modo de teste")
    parser.add_argument("--stress-count", type=int, default=10,
                       help="Número de batalhas no teste de stress")
    parser.add_argument("--verbose", action="store_true", default=True,
                       help="Modo verboso")
    
    args = parser.parse_args()
    
    global VERBOSE
    VERBOSE = args.verbose
    
    log_header("NEURAL FIGHTS - HEADLESS BATTLE TEST SUITE v1.0")
    
    try:
        if args.mode == "rapido":
            executar_teste_rapido()
        
        elif args.mode == "classes":
            executar_teste_todas_classes()
        
        elif args.mode == "raridades":
            executar_teste_todas_raridades()
        
        elif args.mode == "stress":
            executar_teste_stress(args.stress_count)
        
        elif args.mode == "all":
            executar_teste_rapido()
            executar_teste_todas_classes()
            executar_teste_todas_raridades()
            executar_teste_stress(args.stress_count)
    
    except Exception as e:
        log(f"ERRO FATAL: {e}", "ERROR")
        traceback.print_exc()
        return 1
    
    log_header("TESTES CONCLUÍDOS")
    return 0


if __name__ == "__main__":
    exit(main())
