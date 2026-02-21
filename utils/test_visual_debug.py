#!/usr/bin/env python3
"""
=============================================================================
NEURAL FIGHTS - Visual Debug Test Suite v1.0
=============================================================================
Script que roda simulação VISUAL testando TODAS as combinações de:
- Skills (109+ skills)
- Armas (6 raridades, múltiplos tipos)
- Personagens (16 classes)

Toda vez que uma skill é usada:
1. Tira screenshot
2. Verifica se o efeito visual foi renderizado corretamente
3. Salva log de resultados

Uso:
    python test_visual_debug.py
    python test_visual_debug.py --skill "Bola de Fogo"
    python test_visual_debug.py --tipo PROJETIL
    python test_visual_debug.py --all

=============================================================================
"""

import pygame
import sys
import os
import random
import math
import time
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    colors = {
        "INFO": Colors.CYAN,
        "OK": Colors.GREEN,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "DEBUG": Colors.BLUE,
        "HEADER": Colors.HEADER + Colors.BOLD,
    }
    color = colors.get(level, Colors.END)
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{level}] {timestamp}{Colors.END} {msg}")


def log_header(title: str):
    print()
    print(f"{Colors.HEADER}{'='*70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {title}{Colors.END}")
    print(f"{Colors.HEADER}{'='*70}{Colors.END}")
    print()


# =============================================================================
# GERADOR DE ARMAS (copiado do test_headless_battle.py)
# =============================================================================

def gerar_arma_aleatoria(nome: str = None, raridade: str = None) -> dict:
    """Gera uma arma completamente aleatória"""
    from models.constants import (
        LISTA_RARIDADES, TIPOS_ARMA, 
        LISTA_ENCANTAMENTOS, PASSIVAS_ARMA, get_raridade_data
    )
    from core.skills import SKILL_DB
    
    if raridade is None:
        raridade = random.choice(LISTA_RARIDADES)
    rar_data = get_raridade_data(raridade)
    
    tipo = random.choice(list(TIPOS_ARMA.keys()))
    tipo_data = TIPOS_ARMA[tipo]
    
    prefixos = ["Espada", "Lança", "Machado", "Adaga", "Cajado", "Arco", "Mangual", "Katana"]
    sufixos = ["do Caos", "Flamejante", "Gélida", "Sombria", "Divina", "Anciã", "Brutal", "Mística"]
    if nome is None:
        nome = f"{random.choice(prefixos)} {random.choice(sufixos)} #{random.randint(1, 999)}"
    
    num_skills = rar_data.get("slots_habilidade", 1)
    skills_disponiveis = [s for s in SKILL_DB.keys() if SKILL_DB[s].get("tipo", "NADA") != "NADA"]
    habilidades = []
    for _ in range(min(num_skills, len(skills_disponiveis))):
        skill = random.choice(skills_disponiveis)
        skills_disponiveis.remove(skill)
        custo = SKILL_DB[skill].get("custo", 20.0)
        habilidades.append({"nome": skill, "custo": custo})
    
    num_ench = random.randint(0, rar_data.get("max_encantamentos", 0))
    encantamentos = random.sample(LISTA_ENCANTAMENTOS, min(num_ench, len(LISTA_ENCANTAMENTOS)))
    
    passiva = None
    passiva_tipo = rar_data.get("passiva")
    if passiva_tipo and passiva_tipo in PASSIVAS_ARMA:
        passiva = random.choice(PASSIVAS_ARMA[passiva_tipo])
    
    arma = {
        "nome": nome, "tipo": tipo, "dano": round(random.uniform(2.0, 10.0), 1),
        "peso": round(random.uniform(1.0, 8.0), 1), "raridade": raridade,
        "comp_cabo": random.uniform(10.0, 40.0), "comp_lamina": random.uniform(30.0, 100.0),
        "largura": random.uniform(3.0, 15.0), "distancia": 20.0,
        "comp_corrente": random.uniform(0.0, 50.0) if tipo == "Corrente" else 0.0,
        "comp_ponta": random.uniform(5.0, 20.0) if tipo == "Corrente" else 0.0,
        "largura_ponta": random.uniform(3.0, 10.0) if tipo == "Corrente" else 0.0,
        "tamanho_projetil": random.uniform(5.0, 20.0) if tipo == "Arremesso" else 0.0,
        "quantidade": random.randint(1, 5) if tipo == "Arremesso" else 1,
        "tamanho_arco": random.uniform(30.0, 60.0) if tipo == "Arco" else 0.0,
        "forca_arco": random.uniform(5.0, 15.0) if tipo == "Arco" else 0.0,
        "tamanho_flecha": random.uniform(30.0, 50.0) if tipo == "Arco" else 0.0,
        "quantidade_orbitais": random.randint(1, 5) if tipo == "Orbital" else 1,
        "tamanho": random.uniform(5.0, 20.0), "distancia_max": random.uniform(5.0, 15.0) if tipo == "Magica" else 0.0,
        "separacao": random.uniform(10.0, 30.0) if tipo == "Dupla" else 0.0,
        "forma1_cabo": random.uniform(10.0, 25.0), "forma1_lamina": random.uniform(30.0, 60.0),
        "forma2_cabo": random.uniform(10.0, 25.0), "forma2_lamina": random.uniform(30.0, 60.0),
        "r": random.randint(50, 255), "g": random.randint(50, 255), "b": random.randint(50, 255),
        "estilo": tipo_data.get("estilos", ["Misto"])[0] if tipo_data.get("estilos") else "Misto",
        "cabo_dano": random.random() < 0.3, "habilidades": habilidades, "encantamentos": encantamentos,
        "passiva": passiva, "critico": round(random.uniform(0.0, 10.0), 1),
        "velocidade_ataque": round(random.uniform(0.7, 1.5), 2),
        "afinidade_elemento": random.choice([None, "FOGO", "GELO", "RAIO", "VENTO", "TERRA", "TREVAS", "LUZ"]),
        "durabilidade": 100.0, "durabilidade_max": 100.0,
        "habilidade": habilidades[0]["nome"] if habilidades else "Nenhuma",
        "custo_mana": habilidades[0]["custo"] if habilidades else 0.0,
    }
    return arma


def gerar_arma_com_skill(skill_nome: str, raridade: str = "Épico") -> dict:
    """Gera uma arma especificamente com uma skill desejada"""
    from core.skills import SKILL_DB
    
    arma = gerar_arma_aleatoria(raridade=raridade)
    skill_data = SKILL_DB.get(skill_nome, {})
    custo = skill_data.get("custo", 20.0)
    
    arma["habilidade"] = skill_nome
    arma["custo_mana"] = custo
    arma["habilidades"] = [{"nome": skill_nome, "custo": custo}]
    arma["nome"] = f"Arma de Teste - {skill_nome}"
    
    return arma


def gerar_personagem_aleatorio(nome: str = None, classe: str = None, arma: dict = None) -> dict:
    """Gera um personagem completamente aleatório"""
    from models.constants import LISTA_CLASSES
    from ai.personalities import LISTA_PERSONALIDADES
    
    nomes = ["Kael", "Luna", "Draven", "Aria", "Zed", "Nova", "Riven", "Sylas",
             "Ahri", "Darius", "Lux", "Talon", "Jinx", "Sett", "Akali", "Yasuo"]
    
    if nome is None:
        nome = f"{random.choice(nomes)}_{random.randint(1, 999)}"
    if classe is None:
        classe = random.choice(LISTA_CLASSES)
    if arma is None:
        arma = gerar_arma_aleatoria()
    
    return {
        "nome": nome, "tamanho": round(random.uniform(1.5, 2.2), 2),
        "forca": round(random.uniform(3.0, 10.0), 1), "mana": 10.0,  # Mana alta para usar skills
        "nome_arma": arma["nome"], "cor_r": random.randint(50, 255),
        "cor_g": random.randint(50, 255), "cor_b": random.randint(50, 255),
        "classe": classe, "personalidade": random.choice(LISTA_PERSONALIDADES),
        "_arma_obj": arma,
    }


# =============================================================================
# SIMULADOR VISUAL DE DEBUG
# =============================================================================

class VisualDebugSimulator:
    """Simulador visual com captura de screenshots e verificação de efeitos"""
    
    def __init__(self, output_dir: str = "debug_screenshots"):
        pygame.init()
        
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Configuração de tela
        self.screen_width = 1280
        self.screen_height = 720
        self.tela = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Neural Fights - Visual Debug Suite")
        self.clock = pygame.time.Clock()
        
        # Resultados
        self.resultados = {
            "total_skills_testadas": 0,
            "skills_ok": 0,
            "skills_falha": 0,
            "erros": [],
            "screenshots": [],
            "detalhes": {}
        }
        
        # Imports necessários
        from utils.config import PPM, FPS, LARGURA, ALTURA
        from effects import Câmera
        from core.arena import set_arena
        
        self.PPM = PPM
        self.FPS = FPS
        
        # Câmera
        self.cam = Câmera(self.screen_width, self.screen_height)
        
        # Arena padrão
        self.arena = set_arena("Arena")
        self.cam.set_arena_bounds(
            self.arena.centro_x, self.arena.centro_y,
            self.arena.largura, self.arena.altura
        )
    
    def _criar_arma(self, arma_data: dict):
        """Cria objeto Arma a partir dos dados"""
        from models import Arma
        
        return Arma(
            nome=arma_data["nome"], tipo=arma_data.get("tipo", "Reta"),
            dano=arma_data.get("dano", 5.0), peso=arma_data.get("peso", 3.0),
            comp_cabo=arma_data.get("comp_cabo", 15.0), comp_lamina=arma_data.get("comp_lamina", 50.0),
            largura=arma_data.get("largura", 8.0), distancia=arma_data.get("distancia", 20.0),
            r=arma_data.get("r", 200), g=arma_data.get("g", 200), b=arma_data.get("b", 200),
            estilo=arma_data.get("estilo", "Misto"), cabo_dano=arma_data.get("cabo_dano", False),
            habilidade=arma_data.get("habilidade", "Nenhuma"), custo_mana=arma_data.get("custo_mana", 0.0),
            raridade=arma_data.get("raridade", "Comum"), habilidades=arma_data.get("habilidades", []),
            encantamentos=arma_data.get("encantamentos", []), passiva=arma_data.get("passiva"),
            critico=arma_data.get("critico", 0.0), velocidade_ataque=arma_data.get("velocidade_ataque", 1.0),
            afinidade_elemento=arma_data.get("afinidade_elemento"),
            durabilidade=arma_data.get("durabilidade", 100.0), durabilidade_max=arma_data.get("durabilidade_max", 100.0),
            comp_corrente=arma_data.get("comp_corrente", 0.0), comp_ponta=arma_data.get("comp_ponta", 0.0),
            largura_ponta=arma_data.get("largura_ponta", 0.0), tamanho_projetil=arma_data.get("tamanho_projetil", 0.0),
            quantidade=arma_data.get("quantidade", 1), tamanho_arco=arma_data.get("tamanho_arco", 0.0),
            forca_arco=arma_data.get("forca_arco", 0.0), tamanho_flecha=arma_data.get("tamanho_flecha", 0.0),
            quantidade_orbitais=arma_data.get("quantidade_orbitais", 1), tamanho=arma_data.get("tamanho", 8.0),
            distancia_max=arma_data.get("distancia_max", 0.0), separacao=arma_data.get("separacao", 0.0),
            forma1_cabo=arma_data.get("forma1_cabo", 0.0), forma1_lamina=arma_data.get("forma1_lamina", 0.0),
            forma2_cabo=arma_data.get("forma2_cabo", 0.0), forma2_lamina=arma_data.get("forma2_lamina", 0.0),
        )
    
    def _criar_personagem(self, char_data: dict):
        """Cria objeto Personagem a partir dos dados"""
        from models import Personagem
        
        return Personagem(
            nome=char_data["nome"], tamanho=char_data.get("tamanho", 1.8),
            forca=char_data.get("forca", 5.0), mana=char_data.get("mana", 10.0),
            nome_arma=char_data.get("nome_arma", ""),
            r=char_data.get("cor_r", 200),
            g=char_data.get("cor_g", 100),
            b=char_data.get("cor_b", 100),
            classe=char_data.get("classe", "Guerreiro"),
            personalidade=char_data.get("personalidade", "Equilibrado"),
        )
    
    def _criar_lutador(self, char_data: dict, arma_data: dict, x: float, y: float):
        """Cria um Lutador completo"""
        from core.entities import Lutador
        
        personagem = self._criar_personagem(char_data)
        arma = self._criar_arma(arma_data)
        personagem.arma_obj = arma
        
        lutador = Lutador(personagem, x, y)
        lutador.mana = 1000.0  # Mana infinita para testes
        lutador.mana_max = 1000.0
        
        return lutador
    
    def _screenshot(self, nome: str):
        """Salva screenshot da tela atual"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{nome}_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)
        pygame.image.save(self.tela, filepath)
        return filepath
    
    def _verificar_efeito_visual(self, skill_tipo: str, buffers: dict) -> Tuple[bool, str]:
        """
        Verifica se o efeito visual correspondente ao tipo de skill foi criado.
        
        Retorna (sucesso, mensagem)
        """
        verificacoes = {
            "PROJETIL": ("projeteis", "Projétil criado"),
            "BEAM": ("beams", "Beam criado"),
            "AREA": ("areas", "Área criada"),
            "SUMMON": ("summons", "Summon invocado"),
            "TRAP": ("traps", "Trap criada"),
            "BUFF": ("buffs_ativos", "Buff aplicado"),  # Verificar no lutador
            "DASH": ("dash_realizado", "Dash executado"),  # Verificar posição mudou
            "TRANSFORM": ("transform_ativo", "Transformação ativa"),
            "CHANNEL": ("channels", "Channel ativo"),
        }
        
        if skill_tipo not in verificacoes:
            return True, f"Tipo {skill_tipo} não requer verificação visual"
        
        buffer_key, msg_ok = verificacoes[skill_tipo]
        
        # Verificações especiais
        if skill_tipo == "BUFF":
            if buffers.get("lutador"):
                lutador = buffers["lutador"]
                if hasattr(lutador, "buffs_ativos") and lutador.buffs_ativos:
                    return True, f"{msg_ok} (count: {len(lutador.buffs_ativos)})"
            return False, "Nenhum buff aplicado ao lutador"
        
        if skill_tipo == "DASH":
            pos_antes = buffers.get("pos_antes", [0, 0])
            pos_depois = buffers.get("pos_depois", [0, 0])
            dist = math.hypot(pos_depois[0] - pos_antes[0], pos_depois[1] - pos_antes[1])
            if dist > 0.5:  # Moveu pelo menos 0.5 unidades
                return True, f"Dash de {dist:.2f} unidades"
            return False, "Posição não mudou após dash"
        
        if skill_tipo == "TRANSFORM":
            if buffers.get("lutador"):
                lutador = buffers["lutador"]
                if hasattr(lutador, "transformacao_ativa") and lutador.transformacao_ativa:
                    return True, msg_ok
            return False, "Transformação não detectada"
        
        if skill_tipo == "CHANNEL":
            if buffers.get("lutador"):
                lutador = buffers["lutador"]
                if hasattr(lutador, "buffer_channels") and lutador.buffer_channels:
                    return True, f"Channel ativo (count: {len(lutador.buffer_channels)})"
            return False, "Nenhum channel encontrado no buffer"
        
        # Verificação padrão de buffer
        buffer = buffers.get(buffer_key, [])
        if buffer and len(buffer) > 0:
            return True, f"{msg_ok} (count: {len(buffer)})"
        
        return False, f"Nenhum {buffer_key} encontrado no buffer"
    
    def testar_skill(self, skill_nome: str, skill_data: dict) -> dict:
        """Testa uma skill específica e retorna resultado"""
        from core.entities import Lutador
        from core.skills import SKILL_DB
        from utils.config import PPM
        from ai import CombatChoreographer
        from core.game_feel import GameFeelManager
        
        resultado = {
            "skill": skill_nome,
            "tipo": skill_data.get("tipo", "DESCONHECIDO"),
            "sucesso": False,
            "erro": None,
            "screenshot": None,
            "verificacao": None
        }
        
        try:
            # Reset singletons
            CombatChoreographer.reset()
            GameFeelManager.reset()
            
            # Cria arma com a skill específica
            arma_data = gerar_arma_com_skill(skill_nome)
            char_data = gerar_personagem_aleatorio(arma=arma_data)
            
            # Cria oponente simples
            arma_oponente = gerar_arma_aleatoria()
            char_oponente = gerar_personagem_aleatorio(nome="Oponente", arma=arma_oponente)
            
            # Posições na arena
            spawn1 = (self.arena.centro_x - 5, self.arena.centro_y)
            spawn2 = (self.arena.centro_x + 5, self.arena.centro_y)
            
            # Cria lutadores
            p1 = self._criar_lutador(char_data, arma_data, spawn1[0], spawn1[1])
            p2 = self._criar_lutador(char_oponente, arma_oponente, spawn2[0], spawn2[1])
            
            # Inicializa choreographer
            choreographer = CombatChoreographer.get_instance()
            choreographer.registrar_lutadores(p1, p2)
            
            # Buffers para coleta de efeitos
            projeteis = []
            beams = []
            areas = []
            summons = []
            traps = []
            
            # Registra posição antes
            pos_antes = p1.pos.copy()
            
            # Força uso da skill
            log(f"  Usando skill: {skill_nome} ({skill_data.get('tipo', '?')})", "DEBUG")
            
            # Usa a skill (índice 0 pois é a primeira skill da arma)
            p1.usar_skill_arma(0)
            
            # Coleta buffers do lutador
            if hasattr(p1, 'buffer_projeteis'):
                projeteis.extend(p1.buffer_projeteis)
            if hasattr(p1, 'buffer_beams'):
                beams.extend(p1.buffer_beams)
            if hasattr(p1, 'buffer_areas'):
                areas.extend(p1.buffer_areas)
            if hasattr(p1, 'buffer_summons'):
                summons.extend(p1.buffer_summons)
            if hasattr(p1, 'buffer_traps'):
                traps.extend(p1.buffer_traps)
            
            pos_depois = p1.pos.copy()
            
            # Desenha cena
            self.tela.fill((20, 25, 35))
            
            # Desenha arena
            if self.arena:
                self.arena.desenhar(self.tela, self.cam)
            
            # Desenha lutadores
            for lutador in [p1, p2]:
                sx, sy = self.cam.converter(lutador.pos[0] * PPM, lutador.pos[1] * PPM)
                raio = self.cam.converter_tam(lutador.raio_fisico * PPM)
                cor = (lutador.dados.cor_r, lutador.dados.cor_g, lutador.dados.cor_b)
                pygame.draw.circle(self.tela, cor, (int(sx), int(sy)), int(raio))
                pygame.draw.circle(self.tela, (255, 255, 255), (int(sx), int(sy)), int(raio), 2)
            
            # Desenha projéteis
            for proj in projeteis:
                px, py = self.cam.converter(proj.x * PPM, proj.y * PPM)
                pr = self.cam.converter_tam(proj.raio * PPM)
                cor = proj.cor if hasattr(proj, 'cor') else (255, 255, 255)
                pygame.draw.circle(self.tela, cor, (int(px), int(py)), max(5, int(pr)))
            
            # Desenha beams
            for beam in beams:
                if hasattr(beam, 'segments') and len(beam.segments) >= 2:
                    pts = [(self.cam.converter(bx * PPM, by * PPM)) for bx, by in beam.segments]
                    pygame.draw.lines(self.tela, beam.cor if hasattr(beam, 'cor') else (255, 255, 100), False, pts, 4)
            
            # Desenha áreas
            for area in areas:
                ax, ay = self.cam.converter(area.x * PPM, area.y * PPM)
                ar = self.cam.converter_tam(getattr(area, 'raio', 2.0) * PPM)
                cor = area.cor if hasattr(area, 'cor') else (255, 100, 0)
                s = pygame.Surface((ar*2, ar*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*cor, 150), (ar, ar), ar)
                self.tela.blit(s, (ax - ar, ay - ar))
                pygame.draw.circle(self.tela, cor, (int(ax), int(ay)), int(ar), 2)
            
            # Desenha summons
            for summon in summons:
                sx, sy = self.cam.converter(summon.x * PPM, summon.y * PPM)
                raio = self.cam.converter_tam(0.8 * PPM)
                cor = summon.cor if hasattr(summon, 'cor') else (255, 180, 50)
                pygame.draw.circle(self.tela, cor, (int(sx), int(sy)), int(raio))
                pygame.draw.circle(self.tela, (255, 255, 255), (int(sx), int(sy)), int(raio * 0.4))
            
            # Desenha traps
            for trap in traps:
                tx, ty = self.cam.converter(trap.x * PPM, trap.y * PPM)
                traio = self.cam.converter_tam(getattr(trap, 'raio', 1.0) * PPM)
                cor = trap.cor if hasattr(trap, 'cor') else (180, 220, 255)
                pygame.draw.circle(self.tela, cor, (int(tx), int(ty)), int(traio), 3)
            
            # HUD com info da skill
            font = pygame.font.SysFont("Arial", 24)
            tipo_txt = f"Skill: {skill_nome} | Tipo: {skill_data.get('tipo', '?')}"
            txt_surface = font.render(tipo_txt, True, (255, 255, 255))
            self.tela.blit(txt_surface, (20, 20))
            
            # Contadores de efeitos
            stats_txt = f"Projéteis: {len(projeteis)} | Beams: {len(beams)} | Áreas: {len(areas)} | Summons: {len(summons)} | Traps: {len(traps)}"
            stats_surface = font.render(stats_txt, True, (200, 200, 200))
            self.tela.blit(stats_surface, (20, 50))
            
            pygame.display.flip()
            
            # Screenshot
            screenshot_path = self._screenshot(f"skill_{skill_nome.replace(' ', '_')}")
            resultado["screenshot"] = screenshot_path
            
            # Verifica efeito visual
            buffers = {
                "projeteis": projeteis,
                "beams": beams,
                "areas": areas,
                "summons": summons,
                "traps": traps,
                "lutador": p1,
                "pos_antes": pos_antes,
                "pos_depois": pos_depois,
            }
            
            skill_tipo = skill_data.get("tipo", "DESCONHECIDO")
            verificou, msg = self._verificar_efeito_visual(skill_tipo, buffers)
            resultado["verificacao"] = msg
            resultado["sucesso"] = verificou
            
            if verificou:
                log(f"  ✓ {msg}", "OK")
            else:
                log(f"  ✗ {msg}", "WARN")
            
        except Exception as e:
            resultado["erro"] = str(e)
            resultado["traceback"] = traceback.format_exc()
            log(f"  ERRO: {e}", "ERROR")
        
        return resultado
    
    def testar_todas_skills(self, filtro_tipo: str = None):
        """Testa todas as skills (ou apenas um tipo)"""
        from core.skills import SKILL_DB
        
        log_header(f"TESTE VISUAL DE SKILLS {'('+filtro_tipo+')' if filtro_tipo else '(TODAS)'}")
        
        skills_para_testar = {}
        for nome, data in SKILL_DB.items():
            if nome == "Nenhuma":
                continue
            tipo = data.get("tipo", "NADA")
            if tipo == "NADA":
                continue
            if filtro_tipo and tipo != filtro_tipo:
                continue
            skills_para_testar[nome] = data
        
        total = len(skills_para_testar)
        log(f"Skills a testar: {total}", "INFO")
        
        for idx, (nome, data) in enumerate(skills_para_testar.items(), 1):
            log(f"[{idx}/{total}] Testando: {nome}", "INFO")
            
            resultado = self.testar_skill(nome, data)
            self.resultados["detalhes"][nome] = resultado
            self.resultados["total_skills_testadas"] += 1
            
            if resultado["sucesso"]:
                self.resultados["skills_ok"] += 1
            else:
                self.resultados["skills_falha"] += 1
                if resultado["erro"]:
                    self.resultados["erros"].append({
                        "skill": nome,
                        "erro": resultado["erro"]
                    })
            
            if resultado["screenshot"]:
                self.resultados["screenshots"].append(resultado["screenshot"])
            
            # Processa eventos para não travar
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    log("Teste interrompido pelo usuário", "WARN")
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    log("Teste interrompido pelo usuário (ESC)", "WARN")
                    return
            
            # Pequena pausa para visualização
            pygame.time.wait(100)
    
    def testar_skill_especifica(self, skill_nome: str):
        """Testa uma skill específica com visualização prolongada"""
        from core.skills import SKILL_DB
        
        log_header(f"TESTE VISUAL: {skill_nome}")
        
        if skill_nome not in SKILL_DB:
            log(f"Skill '{skill_nome}' não encontrada!", "ERROR")
            return
        
        skill_data = SKILL_DB[skill_nome]
        log(f"Tipo: {skill_data.get('tipo', '?')}", "INFO")
        log(f"Dano: {skill_data.get('dano', 0)}", "INFO")
        log(f"Custo: {skill_data.get('custo', 0)}", "INFO")
        
        resultado = self.testar_skill(skill_nome, skill_data)
        self.resultados["detalhes"][skill_nome] = resultado
        self.resultados["total_skills_testadas"] += 1
        
        if resultado["sucesso"]:
            self.resultados["skills_ok"] += 1
        else:
            self.resultados["skills_falha"] += 1
            if resultado["erro"]:
                self.resultados["erros"].append({"skill": skill_nome, "erro": resultado["erro"]})
        
        if resultado["screenshot"]:
            self.resultados["screenshots"].append(resultado["screenshot"])
        
        # Mantém a tela por 3 segundos
        log("Mantendo visualização por 3 segundos...", "INFO")
        pygame.time.wait(3000)
    
    def salvar_relatorio(self):
        """Salva relatório JSON dos resultados"""
        filepath = os.path.join(self.output_dir, "relatorio_visual.json")
        
        # Simplifica resultados para JSON
        relatorio = {
            "data_teste": datetime.now().isoformat(),
            "total_skills_testadas": self.resultados["total_skills_testadas"],
            "skills_ok": self.resultados["skills_ok"],
            "skills_falha": self.resultados["skills_falha"],
            "taxa_sucesso": f"{100 * self.resultados['skills_ok'] / max(1, self.resultados['total_skills_testadas']):.1f}%",
            "erros": self.resultados["erros"],
            "screenshots_gerados": len(self.resultados["screenshots"]),
        }
        
        # Detalhes simplificados
        detalhes = {}
        for nome, res in self.resultados["detalhes"].items():
            detalhes[nome] = {
                "tipo": res.get("tipo"),
                "sucesso": res.get("sucesso"),
                "verificacao": res.get("verificacao"),
                "erro": res.get("erro"),
            }
        relatorio["detalhes_por_skill"] = detalhes
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        
        log(f"Relatório salvo em: {filepath}", "OK")
        return filepath
    
    def imprimir_sumario(self):
        """Imprime sumário dos resultados"""
        log_header("SUMÁRIO DOS TESTES VISUAIS")
        
        total = self.resultados["total_skills_testadas"]
        ok = self.resultados["skills_ok"]
        falha = self.resultados["skills_falha"]
        
        print(f"  Total de skills testadas: {total}")
        print(f"  {Colors.GREEN}✓ Sucesso: {ok}{Colors.END}")
        print(f"  {Colors.RED}✗ Falhas: {falha}{Colors.END}")
        print(f"  Taxa de sucesso: {100 * ok / max(1, total):.1f}%")
        print()
        
        if self.resultados["erros"]:
            print(f"  {Colors.RED}ERROS ENCONTRADOS:{Colors.END}")
            for erro in self.resultados["erros"]:
                print(f"    - {erro['skill']}: {erro['erro']}")
        
        print()
        print(f"  Screenshots salvos em: {self.output_dir}/")
        print(f"  Total de screenshots: {len(self.resultados['screenshots'])}")
    
    def cleanup(self):
        """Finaliza pygame"""
        pygame.quit()


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Neural Fights - Visual Debug Test Suite")
    parser.add_argument("--skill", type=str, help="Testa uma skill específica")
    parser.add_argument("--tipo", type=str, help="Testa apenas skills de um tipo (PROJETIL, BEAM, AREA, etc)")
    parser.add_argument("--all", action="store_true", help="Testa TODAS as skills")
    parser.add_argument("--output", type=str, default="debug_screenshots", help="Diretório de saída")
    
    args = parser.parse_args()
    
    log_header("NEURAL FIGHTS - VISUAL DEBUG TEST SUITE v1.0")
    
    # Inicializa simulador
    sim = VisualDebugSimulator(output_dir=args.output)
    
    try:
        if args.skill:
            sim.testar_skill_especifica(args.skill)
        elif args.tipo:
            sim.testar_todas_skills(filtro_tipo=args.tipo.upper())
        elif args.all:
            sim.testar_todas_skills()
        else:
            # Menu interativo
            print("Escolha uma opção:")
            print("  1. Testar TODAS as skills")
            print("  2. Testar por tipo (PROJETIL, BEAM, AREA, DASH, BUFF, SUMMON, TRAP, TRANSFORM, CHANNEL)")
            print("  3. Testar skill específica")
            print("  4. Teste rápido (10 skills aleatórias)")
            print()
            
            opcao = input("Opção (1-4): ").strip()
            
            if opcao == "1":
                sim.testar_todas_skills()
            elif opcao == "2":
                tipo = input("Tipo: ").strip().upper()
                sim.testar_todas_skills(filtro_tipo=tipo)
            elif opcao == "3":
                skill = input("Nome da skill: ").strip()
                sim.testar_skill_especifica(skill)
            elif opcao == "4":
                # Teste rápido
                from core.skills import SKILL_DB
                skills_validas = [k for k, v in SKILL_DB.items() if v.get("tipo", "NADA") != "NADA" and k != "Nenhuma"]
                sample = random.sample(skills_validas, min(10, len(skills_validas)))
                for skill_nome in sample:
                    resultado = sim.testar_skill(skill_nome, SKILL_DB[skill_nome])
                    sim.resultados["detalhes"][skill_nome] = resultado
                    sim.resultados["total_skills_testadas"] += 1
                    if resultado["sucesso"]:
                        sim.resultados["skills_ok"] += 1
                    else:
                        sim.resultados["skills_falha"] += 1
            else:
                print("Opção inválida")
                return
        
        # Salva relatório
        sim.salvar_relatorio()
        sim.imprimir_sumario()
        
    except KeyboardInterrupt:
        log("Interrompido pelo usuário", "WARN")
    except Exception as e:
        log(f"Erro fatal: {e}", "ERROR")
        traceback.print_exc()
    finally:
        sim.cleanup()


if __name__ == "__main__":
    main()
