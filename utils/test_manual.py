#!/usr/bin/env python3
"""
=============================================================================
NEURAL FIGHTS - MODO DE TESTE MANUAL v2.0
=============================================================================
Controle seu personagem manualmente para testar habilidades!

CONTROLES:
-----------
MOVIMENTO:
    W/A/S/D ou Setas    - Mover personagem
    SPACE               - Pular
    SHIFT               - Dash/Correr

COMBATE:
    J ou Z              - Ataque basico
    K ou X              - Ataque especial
    L ou C              - Defender/Bloquear

SKILLS (Numeros):
    1-5                 - Usar skill no slot
    
MENUS:
    TAB                 - Abrir menu de skills
    Q                   - Abrir menu de personagem
    E                   - Trocar oponente (Dummy/IA)

OUTROS:
    R                   - Resetar luta
    T                   - Trocar controle (P1/P2)
    F1                  - Mostrar/Ocultar debug
    F2                  - Vida infinita ON/OFF
    F3                  - Mana infinita ON/OFF
    F4                  - Cooldowns zerados ON/OFF
    ESC                 - Sair / Fechar menu

=============================================================================
"""

import pygame
import sys
import os
import math

# Adiciona o diretorio do projeto ao path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from simulation.simulacao import Simulador
from utils.config import PPM, LARGURA, ALTURA
from core.skills import SKILL_DB, listar_skills_para_ui
from data.database import carregar_personagens

# Cores
BRANCO = (255, 255, 255)
PRETO = (0, 0, 0)
VERDE = (0, 255, 0)
VERMELHO = (255, 0, 0)
AMARELO = (255, 255, 0)
CIANO = (0, 255, 255)
CINZA = (128, 128, 128)
AZUL = (50, 100, 200)
ROXO = (150, 50, 200)
LARANJA = (255, 150, 50)


class SimuladorManual(Simulador):
    """
    Simulador com controle manual do jogador e menus de configuração
    """
    
    def __init__(self):
        super().__init__()
        
        # Controle manual
        self.controlando = self.p1  # Comeca controlando P1
        self.mostrar_debug = True
        self.vida_infinita = False
        self.mana_infinita = False
        self.cooldowns_zerados = False
        
        # Modo do oponente: "DUMMY" ou "IA"
        self.modo_oponente = "IA"
        
        # Input state
        self.keys_pressed = set()
        self.keys_just_pressed = set()
        
        # Fontes
        self.font_pequena = pygame.font.Font(None, 20)
        self.font_media = pygame.font.Font(None, 28)
        self.font_grande = pygame.font.Font(None, 36)
        self.font_titulo = pygame.font.Font(None, 48)
        
        # Menu state
        self.menu_ativo = None  # None, "SKILLS", "PERSONAGEM"
        self.menu_scroll = 0
        self.menu_selecionado = 0
        self.slot_skill_editando = None  # 0-4 para editar slot de skill
        
        # Carregar dados
        self.todas_skills = self._carregar_todas_skills()
        self.todos_personagens = carregar_personagens()
        self.skills_filtradas = self.todas_skills.copy()
        self.filtro_elemento = None
        self.filtro_tipo = None
        
        # Lista de skills disponiveis para o personagem controlado
        self.atualizar_skills_disponiveis()
        
        # Print inicial
        self._mostrar_instrucoes()
    
    def _mostrar_instrucoes(self):
        """Mostra instruções no console"""
        print("\n" + "="*70)
        print("MODO DE TESTE MANUAL v2.0 - NEURAL FIGHTS")
        print("="*70)
        print("CONTROLES:")
        print("  WASD/Setas = Mover    | SPACE = Pular     | SHIFT = Correr")
        print("  J/Z = Atacar          | 1-5 = Skills      | T = Trocar P1/P2")
        print("  R = Reset luta        | E = Dummy/IA      | ESC = Sair")
        print("")
        print("MENUS:")
        print("  TAB = Menu de Skills (trocar habilidades)")
        print("  Q = Menu de Personagem")
        print("")
        print("CHEATS:")
        print("  F1 = Debug  | F2 = Vida Inf  | F3 = Mana Inf  | F4 = CD Zero")
        print("="*70 + "\n")
    
    def _carregar_todas_skills(self):
        """Carrega todas as skills do banco de dados"""
        skills = []
        for nome, dados in SKILL_DB.items():
            if nome != "Nenhuma" and dados.get("tipo") != "NADA":
                skill = {"nome": nome}
                skill.update(dados)
                skills.append(skill)
        
        # Ordena por elemento e tipo
        skills.sort(key=lambda s: (s.get("elemento", "Z"), s.get("tipo", "Z"), s["nome"]))
        return skills
    
    def atualizar_skills_disponiveis(self):
        """Atualiza lista de skills do personagem controlado"""
        self.skills_disponiveis = []
        if hasattr(self.controlando, 'skills_classe'):
            for sk in self.controlando.skills_classe:
                # Extrai dados para exibição no HUD
                if "data" in sk:
                    # Estrutura correta: {"nome": ..., "custo": ..., "data": {...}}
                    display_sk = {
                        "nome": sk["nome"],
                        "custo": sk.get("custo", sk["data"].get("custo", 0)),
                        "tipo": sk["data"].get("tipo", "NADA"),
                        "elemento": sk["data"].get("elemento", "")
                    }
                else:
                    # Estrutura antiga
                    display_sk = sk
                self.skills_disponiveis.append(display_sk)
        
        # Garante pelo menos 5 slots
        while len(self.skills_disponiveis) < 5:
            self.skills_disponiveis.append({"nome": "Vazio", "tipo": "NADA", "custo": 0})
    
    def aplicar_filtro_skills(self):
        """Aplica filtros à lista de skills"""
        self.skills_filtradas = []
        for sk in self.todas_skills:
            # Filtro por elemento
            if self.filtro_elemento and sk.get("elemento") != self.filtro_elemento:
                continue
            # Filtro por tipo
            if self.filtro_tipo and sk.get("tipo") != self.filtro_tipo:
                continue
            self.skills_filtradas.append(sk)
        
        self.menu_scroll = 0
        self.menu_selecionado = 0
    
    def trocar_skill_slot(self, slot, nova_skill):
        """Troca uma skill em um slot específico"""
        if slot < 0 or slot >= 5:
            return
        
        # Garante que temos skills suficientes
        while len(self.controlando.skills_classe) <= slot:
            self.controlando.skills_classe.append({
                "nome": "Vazio", 
                "custo": 0,
                "data": {"tipo": "NADA", "custo": 0}
            })
        
        # Encontra a skill no banco de dados
        if nova_skill["nome"] in SKILL_DB:
            skill_data = SKILL_DB[nova_skill["nome"]].copy()
            # Estrutura correta: {"nome": ..., "custo": ..., "data": {...}}
            self.controlando.skills_classe[slot] = {
                "nome": nova_skill["nome"],
                "custo": skill_data.get("custo", 0),
                "data": skill_data
            }
            # Registra cooldown
            self.controlando.cd_skills[nova_skill["nome"]] = 0.0
        
        self.atualizar_skills_disponiveis()
        print(f"Slot {slot+1} = {nova_skill['nome']}")
    
    def trocar_personagem(self, dados_personagem):
        """Troca o personagem controlado"""
        from core.entities import Lutador
        
        pos_atual = self.controlando.pos.copy()
        eh_p1 = self.controlando == self.p1
        
        # Cria novo lutador
        arma = self.controlando.arma  # Mantém a arma atual
        novo = Lutador(dados_personagem, arma)
        novo.pos = pos_atual
        
        if eh_p1:
            self.p1 = novo
            self.controlando = self.p1
        else:
            self.p2 = novo
            self.controlando = self.p2
        
        # Desativa IA se for dummy
        if self.modo_oponente == "DUMMY":
            oponente = self.p2 if eh_p1 else self.p1
            oponente.brain = None
        
        self.atualizar_skills_disponiveis()
        print(f"Personagem trocado para: {dados_personagem.nome}")
    
    def processar_input_manual(self, dt):
        """Processa input do jogador"""
        keys = pygame.key.get_pressed()
        
        # Detecta teclas recem pressionadas
        self.keys_just_pressed.clear()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                self.keys_just_pressed.add(event.key)
                self.keys_pressed.add(event.key)
            elif event.type == pygame.KEYUP:
                self.keys_pressed.discard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:  # Scroll up
                    self.menu_scroll = max(0, self.menu_scroll - 1)
                elif event.button == 5:  # Scroll down
                    self.menu_scroll += 1
        
        # Se menu está ativo, processa input do menu
        if self.menu_ativo:
            return self.processar_input_menu(dt)
        
        # ESC = Sair
        if pygame.K_ESCAPE in self.keys_just_pressed:
            return False
        
        # TAB = Menu de skills
        if pygame.K_TAB in self.keys_just_pressed:
            self.menu_ativo = "SKILLS"
            self.menu_scroll = 0
            self.menu_selecionado = 0
            self.slot_skill_editando = None
            self.filtro_elemento = None
            self.filtro_tipo = None
            self.aplicar_filtro_skills()
            return True
        
        # Q = Menu de personagem
        if pygame.K_q in self.keys_just_pressed:
            self.menu_ativo = "PERSONAGEM"
            self.menu_scroll = 0
            self.menu_selecionado = 0
            return True
        
        # E = Trocar modo oponente (Dummy/IA)
        if pygame.K_e in self.keys_just_pressed:
            oponente = self.p2 if self.controlando == self.p1 else self.p1
            if self.modo_oponente == "IA":
                self.modo_oponente = "DUMMY"
                oponente.brain = None
                print("Oponente: DUMMY (não ataca)")
            else:
                self.modo_oponente = "IA"
                # Recria a IA
                from ai.brain import AIBrain
                oponente.brain = AIBrain(oponente)
                print("Oponente: IA (ataca normalmente)")
            return True
        
        # F1 = Toggle debug
        if pygame.K_F1 in self.keys_just_pressed:
            self.mostrar_debug = not self.mostrar_debug
            print(f"Debug: {'ON' if self.mostrar_debug else 'OFF'}")
        
        # F2 = Vida infinita
        if pygame.K_F2 in self.keys_just_pressed:
            self.vida_infinita = not self.vida_infinita
            print(f"Vida Infinita: {'ON' if self.vida_infinita else 'OFF'}")
        
        # F3 = Mana infinita
        if pygame.K_F3 in self.keys_just_pressed:
            self.mana_infinita = not self.mana_infinita
            print(f"Mana Infinita: {'ON' if self.mana_infinita else 'OFF'}")
        
        # F4 = Cooldowns zerados
        if pygame.K_F4 in self.keys_just_pressed:
            self.cooldowns_zerados = not self.cooldowns_zerados
            print(f"Cooldowns Zero: {'ON' if self.cooldowns_zerados else 'OFF'}")
        
        # T = Trocar controle
        if pygame.K_t in self.keys_just_pressed:
            self.controlando = self.p2 if self.controlando == self.p1 else self.p1
            self.atualizar_skills_disponiveis()
            nome = self.controlando.dados.nome
            print(f"Agora controlando: {nome}")
        
        # R = Reset
        if pygame.K_r in self.keys_just_pressed:
            self.resetar_luta()
            print("Luta resetada!")
        
        # === MOVIMENTO ===
        p = self.controlando
        vel_movimento = 6.0
        
        # SHIFT = Correr
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            vel_movimento = 12.0
        
        # Aplica buff de velocidade dos buffs ativos
        for buff in p.buffs_ativos:
            if hasattr(buff, 'buff_velocidade'):
                vel_movimento *= buff.buff_velocidade
        
        # Direcao
        mov_x = 0
        mov_y = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            mov_x = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            mov_x = 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            mov_y = -1
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            mov_y = 1
        
        # Aplica movimento
        if mov_x != 0 or mov_y != 0:
            p.angulo_olhar = math.degrees(math.atan2(mov_y, mov_x))
            p.pos[0] += mov_x * vel_movimento * dt
            p.pos[1] += mov_y * vel_movimento * dt
        
        # SPACE = Pular
        if pygame.K_SPACE in self.keys_just_pressed:
            if hasattr(p, 'pular'):
                p.pular()
            elif hasattr(p, 'vel_z') and p.z <= 0.1:
                p.vel_z = 8.0
        
        # === COMBATE ===
        if pygame.K_j in self.keys_just_pressed or pygame.K_z in self.keys_just_pressed:
            if hasattr(p, 'atacar'):
                p.atacar()
            elif hasattr(p, 'usar_skill_arma'):
                p.usar_skill_arma(0)
            print(f"{p.dados.nome} atacou!")
        
        if pygame.K_k in self.keys_just_pressed or pygame.K_x in self.keys_just_pressed:
            if hasattr(p, 'usar_skill_arma'):
                p.usar_skill_arma(1)
            print(f"{p.dados.nome} usou ataque especial!")
        
        # L ou C = Bloquear
        if keys[pygame.K_l] or keys[pygame.K_c]:
            if hasattr(p, 'bloqueando'):
                p.bloqueando = True
        else:
            if hasattr(p, 'bloqueando'):
                p.bloqueando = False
        
        # === SKILLS (1-5) ===
        skill_keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]
        for i, key in enumerate(skill_keys):
            if key in self.keys_just_pressed:
                if i < len(self.skills_disponiveis):
                    skill = self.skills_disponiveis[i]
                    nome_skill = skill.get("nome", "Vazio")
                    
                    if nome_skill == "Vazio":
                        print(f"[SLOT {i+1}] Vazio - use TAB para adicionar skills")
                        continue
                    
                    if hasattr(p, 'usar_skill_classe'):
                        sucesso = p.usar_skill_classe(nome_skill)
                        if sucesso:
                            print(f">>> {p.dados.nome} usou: {nome_skill}")
                        else:
                            cd = p.cd_skills.get(nome_skill, 0)
                            custo = skill.get("custo", 0)
                            if cd > 0:
                                print(f"[CD] {nome_skill} em cooldown: {cd:.1f}s")
                            elif p.mana < custo:
                                print(f"[MANA] {nome_skill} requer {custo} mana (voce tem {p.mana:.0f})")
                            else:
                                print(f"[FALHA] Nao foi possivel usar {nome_skill}")
        
        # === CHEATS ===
        if self.vida_infinita:
            self.controlando.vida = self.controlando.vida_max
        
        if self.mana_infinita:
            self.controlando.mana = self.controlando.mana_max
        
        if self.cooldowns_zerados:
            for sk in self.controlando.cd_skills:
                self.controlando.cd_skills[sk] = 0
        
        return True
    
    def processar_input_menu(self, dt):
        """Processa input quando um menu está ativo"""
        
        # ESC = Fechar menu
        if pygame.K_ESCAPE in self.keys_just_pressed:
            if self.slot_skill_editando is not None:
                self.slot_skill_editando = None
            else:
                self.menu_ativo = None
            return True
        
        # TAB = Fechar menu de skills
        if pygame.K_TAB in self.keys_just_pressed and self.menu_ativo == "SKILLS":
            self.menu_ativo = None
            return True
        
        # Q = Fechar menu de personagem
        if pygame.K_q in self.keys_just_pressed and self.menu_ativo == "PERSONAGEM":
            self.menu_ativo = None
            return True
        
        if self.menu_ativo == "SKILLS":
            return self.processar_menu_skills()
        elif self.menu_ativo == "PERSONAGEM":
            return self.processar_menu_personagem()
        
        return True
    
    def processar_menu_skills(self):
        """Processa input do menu de skills"""
        
        # Se não está editando slot, seleciona qual slot editar
        if self.slot_skill_editando is None:
            # 1-5 = Selecionar slot para editar
            slot_keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]
            for i, key in enumerate(slot_keys):
                if key in self.keys_just_pressed:
                    self.slot_skill_editando = i
                    self.menu_scroll = 0
                    self.menu_selecionado = 0
                    return True
            
            # Filtros por elemento (teclas F5-F9 ou letras)
            elemento_keys = {
                pygame.K_f: "FOGO",
                pygame.K_g: "GELO", 
                pygame.K_i: "RAIO",
                pygame.K_n: "NATUREZA",
                pygame.K_l: "LUZ",
                pygame.K_d: "TREVAS",
                pygame.K_a: "ARCANO",
                pygame.K_v: "VOID",
                pygame.K_b: "SANGUE",
                pygame.K_c: "CAOS",
                pygame.K_m: "TEMPO",
                pygame.K_h: "GRAVITACAO",
            }
            
            for key, elem in elemento_keys.items():
                if key in self.keys_just_pressed:
                    if self.filtro_elemento == elem:
                        self.filtro_elemento = None
                    else:
                        self.filtro_elemento = elem
                    self.aplicar_filtro_skills()
                    return True
            
            # Limpar filtros
            if pygame.K_0 in self.keys_just_pressed:
                self.filtro_elemento = None
                self.filtro_tipo = None
                self.aplicar_filtro_skills()
                return True
        
        else:
            # Está editando um slot - navega na lista de skills
            # UP/DOWN = Navegar
            if pygame.K_UP in self.keys_just_pressed or pygame.K_w in self.keys_just_pressed:
                self.menu_selecionado = max(0, self.menu_selecionado - 1)
                # Ajusta scroll
                if self.menu_selecionado < self.menu_scroll:
                    self.menu_scroll = self.menu_selecionado
            
            if pygame.K_DOWN in self.keys_just_pressed or pygame.K_s in self.keys_just_pressed:
                self.menu_selecionado = min(len(self.skills_filtradas) - 1, self.menu_selecionado + 1)
                # Ajusta scroll
                max_visivel = 15
                if self.menu_selecionado >= self.menu_scroll + max_visivel:
                    self.menu_scroll = self.menu_selecionado - max_visivel + 1
            
            # PAGE UP/DOWN
            if pygame.K_PAGEUP in self.keys_just_pressed:
                self.menu_selecionado = max(0, self.menu_selecionado - 10)
                self.menu_scroll = max(0, self.menu_scroll - 10)
            
            if pygame.K_PAGEDOWN in self.keys_just_pressed:
                self.menu_selecionado = min(len(self.skills_filtradas) - 1, self.menu_selecionado + 10)
            
            # ENTER = Confirmar seleção
            if pygame.K_RETURN in self.keys_just_pressed:
                if 0 <= self.menu_selecionado < len(self.skills_filtradas):
                    skill = self.skills_filtradas[self.menu_selecionado]
                    self.trocar_skill_slot(self.slot_skill_editando, skill)
                    self.slot_skill_editando = None
            
            # BACKSPACE = Voltar sem selecionar
            if pygame.K_BACKSPACE in self.keys_just_pressed:
                self.slot_skill_editando = None
        
        return True
    
    def processar_menu_personagem(self):
        """Processa input do menu de personagem"""
        
        # UP/DOWN = Navegar
        if pygame.K_UP in self.keys_just_pressed or pygame.K_w in self.keys_just_pressed:
            self.menu_selecionado = max(0, self.menu_selecionado - 1)
            if self.menu_selecionado < self.menu_scroll:
                self.menu_scroll = self.menu_selecionado
        
        if pygame.K_DOWN in self.keys_just_pressed or pygame.K_s in self.keys_just_pressed:
            self.menu_selecionado = min(len(self.todos_personagens) - 1, self.menu_selecionado + 1)
            max_visivel = 12
            if self.menu_selecionado >= self.menu_scroll + max_visivel:
                self.menu_scroll = self.menu_selecionado - max_visivel + 1
        
        # ENTER = Confirmar
        if pygame.K_RETURN in self.keys_just_pressed:
            if 0 <= self.menu_selecionado < len(self.todos_personagens):
                personagem = self.todos_personagens[self.menu_selecionado]
                self.trocar_personagem(personagem)
                self.menu_ativo = None
        
        return True
    
    def resetar_luta(self):
        """Reseta a luta para o estado inicial"""
        self.p1.pos = [4.0, 3.0]
        self.p2.pos = [12.0, 3.0]
        
        self.p1.vida = self.p1.vida_max
        self.p2.vida = self.p2.vida_max
        self.p1.mana = self.p1.mana_max
        self.p2.mana = self.p2.mana_max
        
        self.p1.cd_skills = {}
        self.p2.cd_skills = {}
        
        self.p1.morto = False
        self.p2.morto = False
        self.p1.vivo = True
        self.p2.vivo = True
        
        self.projeteis = []
        if hasattr(self, 'areas'):
            self.areas = []
        if hasattr(self, 'beams'):
            self.beams = []
        if hasattr(self, 'summons'):
            self.summons = []
        if hasattr(self, 'traps'):
            self.traps = []
        if hasattr(self, 'channels'):
            self.channels = []
        if hasattr(self, 'transforms'):
            self.transforms = []
        
        self.textos = []
        self.vencedor = None
    
    def desenhar_menu_skills(self, surface):
        """Desenha o menu de seleção de skills"""
        # Fundo semi-transparente
        overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))
        
        # Título
        titulo = self.font_titulo.render("MENU DE SKILLS", True, CIANO)
        surface.blit(titulo, (LARGURA//2 - titulo.get_width()//2, 20))
        
        # === SLOTS ATUAIS ===
        pygame.draw.rect(surface, (30, 30, 50), (50, 70, 300, 150))
        pygame.draw.rect(surface, AMARELO, (50, 70, 300, 150), 2)
        
        slots_txt = self.font_media.render("SEUS SLOTS (1-5 para editar):", True, AMARELO)
        surface.blit(slots_txt, (60, 80))
        
        for i, sk in enumerate(self.skills_disponiveis[:5]):
            nome = sk.get("nome", "Vazio")
            tipo = sk.get("tipo", "NADA")
            custo = sk.get("custo", 0)
            elem = sk.get("elemento", "")
            
            cor = VERDE if self.slot_skill_editando == i else BRANCO
            if nome == "Vazio":
                cor = CINZA
            
            texto = f"{i+1}. {nome[:20]}"
            if elem:
                texto += f" [{elem[:3]}]"
            if custo > 0:
                texto += f" ({custo}mp)"
            
            sk_txt = self.font_pequena.render(texto, True, cor)
            surface.blit(sk_txt, (70, 105 + i * 22))
        
        # === FILTROS ===
        filtro_y = 230
        pygame.draw.rect(surface, (30, 40, 30), (50, filtro_y, 300, 60))
        pygame.draw.rect(surface, VERDE, (50, filtro_y, 300, 60), 1)
        
        filtro_txt = self.font_pequena.render("FILTROS: F=Fogo G=Gelo I=Raio N=Nat L=Luz", True, VERDE)
        surface.blit(filtro_txt, (60, filtro_y + 5))
        filtro_txt2 = self.font_pequena.render("D=Trevas A=Arcano V=Void B=Sangue 0=Limpar", True, VERDE)
        surface.blit(filtro_txt2, (60, filtro_y + 22))
        
        if self.filtro_elemento:
            filtro_atual = self.font_pequena.render(f"Filtro: {self.filtro_elemento}", True, AMARELO)
            surface.blit(filtro_atual, (60, filtro_y + 40))
        
        # === LISTA DE SKILLS ===
        lista_x = 400
        lista_y = 70
        lista_w = LARGURA - 450
        lista_h = ALTURA - 150
        
        pygame.draw.rect(surface, (20, 20, 40), (lista_x, lista_y, lista_w, lista_h))
        pygame.draw.rect(surface, CIANO, (lista_x, lista_y, lista_w, lista_h), 2)
        
        if self.slot_skill_editando is not None:
            titulo_lista = self.font_media.render(f"SELECIONE SKILL PARA SLOT {self.slot_skill_editando + 1}", True, CIANO)
        else:
            titulo_lista = self.font_media.render("TODAS AS SKILLS (selecione slot primeiro)", True, CINZA)
        surface.blit(titulo_lista, (lista_x + 10, lista_y + 5))
        
        # Lista de skills
        item_h = 22
        max_items = (lista_h - 40) // item_h
        
        for i, sk in enumerate(self.skills_filtradas[self.menu_scroll:self.menu_scroll + max_items]):
            idx = i + self.menu_scroll
            nome = sk.get("nome", "???")
            tipo = sk.get("tipo", "???")
            elem = sk.get("elemento", "")
            custo = sk.get("custo", 0)
            dano = sk.get("dano", sk.get("dano_tick", 0))
            
            # Cor baseada no elemento
            cores_elem = {
                "FOGO": (255, 100, 50),
                "GELO": (100, 200, 255),
                "RAIO": (255, 255, 100),
                "NATUREZA": (100, 255, 100),
                "LUZ": (255, 255, 200),
                "TREVAS": (150, 100, 200),
                "ARCANO": (200, 100, 255),
                "VOID": (100, 50, 150),
                "SANGUE": (200, 50, 50),
                "CAOS": (255, 50, 150),
                "TEMPO": (200, 200, 255),
                "GRAVITACAO": (150, 150, 200),
            }
            cor = cores_elem.get(elem, BRANCO)
            
            if idx == self.menu_selecionado and self.slot_skill_editando is not None:
                # Highlight seleção
                pygame.draw.rect(surface, (50, 50, 80), 
                               (lista_x + 5, lista_y + 30 + i * item_h, lista_w - 10, item_h))
                cor = AMARELO
            
            texto = f"{nome[:25]:<25} {tipo:<10} {elem[:4] if elem else '':>4} {custo:>3}mp"
            if dano > 0:
                texto += f" {dano:>3}dmg"
            
            sk_txt = self.font_pequena.render(texto, True, cor)
            surface.blit(sk_txt, (lista_x + 10, lista_y + 32 + i * item_h))
        
        # Instruções
        if self.slot_skill_editando is not None:
            inst = "W/S=Navegar | ENTER=Confirmar | BACKSPACE=Voltar | ESC=Fechar"
        else:
            inst = "1-5=Editar Slot | Letras=Filtrar | 0=Limpar | TAB/ESC=Fechar"
        inst_txt = self.font_pequena.render(inst, True, CINZA)
        surface.blit(inst_txt, (LARGURA//2 - inst_txt.get_width()//2, ALTURA - 40))
        
        # Contador de skills
        count = self.font_pequena.render(f"Skills: {len(self.skills_filtradas)}/{len(self.todas_skills)}", True, CINZA)
        surface.blit(count, (lista_x + lista_w - 120, lista_y + lista_h - 25))
    
    def desenhar_menu_personagem(self, surface):
        """Desenha o menu de seleção de personagem"""
        overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))
        
        titulo = self.font_titulo.render("SELECIONAR PERSONAGEM", True, ROXO)
        surface.blit(titulo, (LARGURA//2 - titulo.get_width()//2, 20))
        
        # Lista de personagens
        lista_x = 100
        lista_y = 80
        lista_w = LARGURA - 200
        lista_h = ALTURA - 180
        
        pygame.draw.rect(surface, (30, 20, 40), (lista_x, lista_y, lista_w, lista_h))
        pygame.draw.rect(surface, ROXO, (lista_x, lista_y, lista_w, lista_h), 2)
        
        item_h = 35
        max_items = (lista_h - 20) // item_h
        
        for i, pers in enumerate(self.todos_personagens[self.menu_scroll:self.menu_scroll + max_items]):
            idx = i + self.menu_scroll
            
            # Highlight
            if idx == self.menu_selecionado:
                pygame.draw.rect(surface, (60, 40, 80),
                               (lista_x + 5, lista_y + 10 + i * item_h, lista_w - 10, item_h - 2))
                cor = AMARELO
            else:
                cor = BRANCO
            
            # Nome e stats
            nome_txt = self.font_media.render(f"{pers.nome}", True, cor)
            surface.blit(nome_txt, (lista_x + 15, lista_y + 12 + i * item_h))
            
            # Classe
            classe = getattr(pers, 'classe', 'Desconhecida')
            classe_txt = self.font_pequena.render(f"{classe}", True, CIANO)
            surface.blit(classe_txt, (lista_x + 250, lista_y + 15 + i * item_h))
            
            # Stats
            vida = getattr(pers, 'vida', 100)
            forca = getattr(pers, 'forca', 10)
            stats_txt = self.font_pequena.render(f"HP:{vida} FOR:{forca}", True, CINZA)
            surface.blit(stats_txt, (lista_x + 400, lista_y + 15 + i * item_h))
        
        # Preview do selecionado
        if 0 <= self.menu_selecionado < len(self.todos_personagens):
            pers = self.todos_personagens[self.menu_selecionado]
            preview_y = ALTURA - 90
            
            pygame.draw.rect(surface, (40, 30, 50), (lista_x, preview_y, lista_w, 70))
            pygame.draw.rect(surface, ROXO, (lista_x, preview_y, lista_w, 70), 1)
            
            # Descrição ou skills
            skills_pers = getattr(pers, 'skills', [])
            if skills_pers:
                skills_txt = f"Skills: {', '.join(skills_pers[:4])}"
                sk_render = self.font_pequena.render(skills_txt, True, VERDE)
                surface.blit(sk_render, (lista_x + 10, preview_y + 10))
            
            # Stats detalhados
            stats_detail = f"Vida:{getattr(pers,'vida',100)} Mana:{getattr(pers,'mana',50)} "
            stats_detail += f"Força:{getattr(pers,'forca',10)} Destreza:{getattr(pers,'destreza',10)} "
            stats_detail += f"Int:{getattr(pers,'inteligencia',10)}"
            stats_render = self.font_pequena.render(stats_detail, True, BRANCO)
            surface.blit(stats_render, (lista_x + 10, preview_y + 35))
        
        # Instruções
        inst = "W/S=Navegar | ENTER=Confirmar | Q/ESC=Fechar"
        inst_txt = self.font_pequena.render(inst, True, CINZA)
        surface.blit(inst_txt, (LARGURA//2 - inst_txt.get_width()//2, ALTURA - 25))
    
    def desenhar_hud_manual(self, surface):
        """Desenha HUD com informacoes de controle"""
        p = self.controlando
        inimigo = self.p2 if p == self.p1 else self.p1
        
        # === PAINEL ESQUERDO - JOGADOR ===
        pygame.draw.rect(surface, (30, 30, 50), (10, 10, 250, 200))
        pygame.draw.rect(surface, CIANO, (10, 10, 250, 200), 2)
        
        nome_txt = self.font_grande.render(f">> {p.dados.nome}", True, CIANO)
        surface.blit(nome_txt, (20, 15))
        
        classe_txt = self.font_pequena.render(f"Classe: {p.classe_nome}", True, BRANCO)
        surface.blit(classe_txt, (20, 45))
        
        # Barra de vida
        vida_pct = p.vida / p.vida_max
        pygame.draw.rect(surface, CINZA, (20, 70, 200, 20))
        pygame.draw.rect(surface, VERDE if vida_pct > 0.3 else VERMELHO, (20, 70, int(200 * vida_pct), 20))
        vida_txt = self.font_pequena.render(f"HP: {int(p.vida)}/{int(p.vida_max)}", True, BRANCO)
        surface.blit(vida_txt, (25, 72))
        
        # Barra de mana
        mana_pct = p.mana / p.mana_max if p.mana_max > 0 else 0
        pygame.draw.rect(surface, CINZA, (20, 95, 200, 15))
        pygame.draw.rect(surface, AZUL, (20, 95, int(200 * mana_pct), 15))
        mana_txt = self.font_pequena.render(f"MP: {int(p.mana)}/{int(p.mana_max)}", True, BRANCO)
        surface.blit(mana_txt, (25, 96))
        
        # Skills
        y_skill = 120
        skills_txt = self.font_media.render("SKILLS (1-5):", True, AMARELO)
        surface.blit(skills_txt, (20, y_skill))
        y_skill += 22
        
        for i, sk in enumerate(self.skills_disponiveis[:5]):
            nome = sk.get("nome", "Vazio")
            custo = sk.get("custo", 0)
            cd_atual = p.cd_skills.get(nome, 0)
            
            if nome == "Vazio":
                cor = CINZA
                status = "[vazio]"
            elif cd_atual > 0:
                cor = CINZA
                status = f"[{cd_atual:.1f}s]"
            elif p.mana < custo:
                cor = (100, 100, 150)
                status = f"({custo}mp)"
            else:
                cor = VERDE
                status = f"({custo}mp)"
            
            sk_txt = self.font_pequena.render(f"{i+1}. {nome[:13]} {status}", True, cor)
            surface.blit(sk_txt, (25, y_skill))
            y_skill += 15
        
        # === PAINEL DIREITO - INIMIGO ===
        pygame.draw.rect(surface, (50, 30, 30), (LARGURA - 260, 10, 250, 100))
        pygame.draw.rect(surface, VERMELHO, (LARGURA - 260, 10, 250, 100), 2)
        
        modo_txt = f"[{self.modo_oponente}]"
        inimigo_txt = self.font_media.render(f"INIMIGO {modo_txt}", True, VERMELHO)
        surface.blit(inimigo_txt, (LARGURA - 250, 15))
        
        nome_ini = self.font_pequena.render(f"{inimigo.dados.nome}", True, BRANCO)
        surface.blit(nome_ini, (LARGURA - 250, 38))
        
        # Barra de vida inimigo
        vida_pct_i = inimigo.vida / inimigo.vida_max
        pygame.draw.rect(surface, CINZA, (LARGURA - 250, 60, 200, 20))
        pygame.draw.rect(surface, (200, 50, 50), (LARGURA - 250, 60, int(200 * vida_pct_i), 20))
        vida_txt_i = self.font_pequena.render(f"HP: {int(inimigo.vida)}/{int(inimigo.vida_max)}", True, BRANCO)
        surface.blit(vida_txt_i, (LARGURA - 245, 62))
        
        # Mana inimigo
        mana_pct_i = inimigo.mana / inimigo.mana_max if inimigo.mana_max > 0 else 0
        pygame.draw.rect(surface, CINZA, (LARGURA - 250, 85, 200, 10))
        pygame.draw.rect(surface, (100, 100, 200), (LARGURA - 250, 85, int(200 * mana_pct_i), 10))
        
        # === PAINEL INFERIOR - CHEATS E CONTROLES ===
        y_cheats = ALTURA - 50
        cheats = []
        if self.vida_infinita:
            cheats.append("VIDA INF")
        if self.mana_infinita:
            cheats.append("MANA INF")
        if self.cooldowns_zerados:
            cheats.append("CD ZERO")
        
        if cheats:
            cheats_txt = self.font_pequena.render(" | ".join(cheats), True, AMARELO)
            surface.blit(cheats_txt, (10, y_cheats))
        
        # Controles
        ctrl1 = "WASD=Mover | J=Atacar | 1-5=Skills | SPACE=Pular | SHIFT=Correr"
        ctrl2 = "TAB=Skills | Q=Personagem | E=Dummy/IA | T=Trocar | R=Reset | ESC=Sair"
        
        ctrl_txt1 = self.font_pequena.render(ctrl1, True, CINZA)
        ctrl_txt2 = self.font_pequena.render(ctrl2, True, CINZA)
        surface.blit(ctrl_txt1, (LARGURA//2 - ctrl_txt1.get_width()//2, ALTURA - 35))
        surface.blit(ctrl_txt2, (LARGURA//2 - ctrl_txt2.get_width()//2, ALTURA - 18))
        
        # === DEBUG INFO ===
        if self.mostrar_debug:
            debug_y = 220
            pygame.draw.rect(surface, (20, 20, 30), (10, debug_y, 250, 160))
            pygame.draw.rect(surface, (100, 100, 150), (10, debug_y, 250, 160), 1)
            
            debug_info = [
                f"Pos: ({p.pos[0]:.1f}, {p.pos[1]:.1f})",
                f"Angulo: {p.angulo_olhar:.0f}°",
                f"Vel: ({p.vel[0]:.1f}, {p.vel[1]:.1f})",
                f"Z: {p.z:.2f}",
                f"Projeteis: {len(self.projeteis)}",
                f"Areas: {len(getattr(self, 'areas', []))}",
                f"Summons: {len(getattr(self, 'summons', []))}",
                f"Beams: {len(getattr(self, 'beams', []))}",
            ]
            
            for i, info in enumerate(debug_info):
                txt = self.font_pequena.render(info, True, (150, 150, 200))
                surface.blit(txt, (20, debug_y + 5 + i * 18))
    
    def executar(self):
        """Loop principal com controle manual"""
        clock = pygame.time.Clock()
        running = True
        
        while running:
            dt = clock.tick(60) / 1000.0
            dt = min(dt, 0.05)
            
            # Processa input manual
            running = self.processar_input_manual(dt)
            
            # Se menu ativo, apenas desenha
            if self.menu_ativo:
                # Desenha jogo de fundo (pausado)
                self.desenhar()
                
                # Desenha menu
                if self.menu_ativo == "SKILLS":
                    self.desenhar_menu_skills(self.tela)
                elif self.menu_ativo == "PERSONAGEM":
                    self.desenhar_menu_personagem(self.tela)
                
                pygame.display.flip()
                continue
            
            # Desativa IA do personagem controlado
            controlando_tinha_brain = hasattr(self.controlando, 'brain') and self.controlando.brain is not None
            if controlando_tinha_brain:
                brain_backup = self.controlando.brain
                self.controlando.brain = None
            
            # Update normal
            self.update(dt)
            
            # Restaura brain
            if controlando_tinha_brain:
                self.controlando.brain = brain_backup
            
            # Desenha
            self.desenhar()
            self.desenhar_hud_manual(self.tela)
            
            pygame.display.flip()
            
            # Checa vitoria/derrota
            if self.vencedor:
                print(f"\n{'='*40}")
                print(f"VENCEDOR: {self.vencedor}")
                print(f"{'='*40}")
                print("Pressione R para resetar ou ESC para sair")
        
        pygame.quit()


def main():
    """Ponto de entrada"""
    print("\nIniciando NEURAL FIGHTS - Modo de Teste Manual v2.0...")
    print("Carregando...")
    
    sim = SimuladorManual()
    sim.executar()


if __name__ == "__main__":
    main()
