"""
NEURAL FIGHTS - Sistema de Arena v2.0
Define os limites do mapa, obstáculos e colisões.
Sistema expandido com múltiplos mapas temáticos.
"""

import math
import pygame
from neural_fights.utils.config import COR_FUNDO, PPM
import dataclasses
from dataclasses import dataclass, field
from typing import Tuple, List, Optional


@dataclass
class Obstaculo:
    """Um obstáculo na arena"""
    tipo: str  # "pilar", "caixa", "barreira", "fosso", "plataforma"
    x: float  # Centro X em metros
    y: float  # Centro Y em metros
    largura: float  # Em metros
    altura: float  # Em metros
    cor: Tuple[int, int, int] = (80, 80, 80)
    solido: bool = True  # Se bloqueia movimento
    destrutivel: bool = False
    hp: int = 100


@dataclass
class ArenaConfig:
    """Configuração de uma arena"""
    nome: str
    largura: float  # Em metros
    altura: float   # Em metros
    cor_chao: Tuple[int, int, int] = (30, 30, 30)
    cor_parede: Tuple[int, int, int] = (60, 60, 80)
    cor_borda: Tuple[int, int, int] = (100, 100, 140)
    espessura_parede: float = 0.3  # Em metros
    tem_paredes: bool = True
    formato: str = "retangular"  # "retangular", "circular", "octogono"
    obstaculos: List[Obstaculo] = field(default_factory=list)
    tema: str = "neutro"  # Tema visual
    descricao: str = ""
    icone: str = "⬜"  # Emoji para UI
    cor_ambiente: Tuple[int, int, int] = (0, 0, 0)  # Luz ambiente
    efeitos_especiais: List[str] = field(default_factory=list)


# =============================================================================
# MAPAS TEMÁTICOS DIVERSOS
# =============================================================================

ARENAS = {
    # === ARENAS CLÁSSICAS ===
    "Arena": ArenaConfig(
        nome="Arena Clássica",
        largura=30.0,
        altura=20.0,
        cor_chao=(25, 25, 35),
        cor_parede=(50, 50, 70),
        cor_borda=(80, 80, 120),
        formato="retangular",
        tema="classico",
        descricao="Arena padrão sem obstáculos",
        icone="🏟️",
    ),
    
    "Arena Pequena": ArenaConfig(
        nome="Arena Compacta",
        largura=16.0,
        altura=12.0,
        cor_chao=(35, 25, 25),
        cor_parede=(70, 50, 50),
        cor_borda=(120, 80, 80),
        formato="retangular",
        tema="classico",
        descricao="Espaço apertado - combate intenso",
        icone="📦",
    ),
    
    # === COLISEU ROMANO ===
    "Coliseu": ArenaConfig(
        nome="Coliseu Romano",
        largura=35.0,
        altura=35.0,
        cor_chao=(60, 50, 35),
        cor_parede=(100, 85, 60),
        cor_borda=(160, 140, 100),
        formato="circular",
        tema="romano",
        descricao="Arena circular majestosa",
        icone="🏛️",
        obstaculos=[
            # Pilares mais próximos do centro para serem visíveis
            Obstaculo("pilar", 13.0, 17.5, 1.5, 1.5, (140, 120, 90)),
            Obstaculo("pilar", 22.0, 17.5, 1.5, 1.5, (140, 120, 90)),
            Obstaculo("pilar", 17.5, 13.0, 1.5, 1.5, (140, 120, 90)),
            Obstaculo("pilar", 17.5, 22.0, 1.5, 1.5, (140, 120, 90)),
        ],
    ),
    
    # === DOJO JAPONÊS ===
    "Dojo": ArenaConfig(
        nome="Dojo Sagrado",
        largura=22.0,
        altura=22.0,
        cor_chao=(70, 55, 40),
        cor_parede=(50, 40, 30),
        cor_borda=(90, 75, 55),
        formato="octogono",
        tema="japones",
        descricao="Local de treino tradicional",
        icone="⛩️",
    ),
    
    # === FLORESTA SOMBRIA ===
    "Floresta": ArenaConfig(
        nome="Clareira Sombria",
        largura=32.0,
        altura=24.0,
        cor_chao=(25, 40, 20),
        cor_parede=(15, 30, 10),
        cor_borda=(40, 70, 30),
        formato="retangular",
        tema="floresta",
        descricao="Árvores bloqueiam a visão",
        icone="🌲",
        cor_ambiente=(10, 30, 10),
        obstaculos=[
            # Árvores espalhadas
            Obstaculo("arvore", 6.0, 6.0, 2.0, 2.0, (50, 35, 20)),
            Obstaculo("arvore", 26.0, 6.0, 2.0, 2.0, (50, 35, 20)),
            Obstaculo("arvore", 6.0, 18.0, 2.0, 2.0, (50, 35, 20)),
            Obstaculo("arvore", 26.0, 18.0, 2.0, 2.0, (50, 35, 20)),
            Obstaculo("arvore", 16.0, 4.0, 1.5, 1.5, (45, 30, 18)),
            Obstaculo("arvore", 16.0, 20.0, 1.5, 1.5, (45, 30, 18)),
            # Pedras
            Obstaculo("pedra", 10.0, 12.0, 1.2, 0.8, (70, 70, 65)),
            Obstaculo("pedra", 22.0, 12.0, 1.2, 0.8, (70, 70, 65)),
        ],
    ),
    
    # === CAVERNA DE CRISTAIS ===
    "Caverna": ArenaConfig(
        nome="Caverna de Cristais",
        largura=28.0,
        altura=20.0,
        cor_chao=(30, 25, 40),
        cor_parede=(50, 40, 70),
        cor_borda=(100, 80, 150),
        formato="retangular",
        tema="caverna",
        descricao="Cristais brilham na escuridão",
        icone="💎",
        cor_ambiente=(20, 10, 40),
        obstaculos=[
            # Estalagmites
            Obstaculo("cristal", 7.0, 5.0, 1.0, 1.0, (150, 100, 200)),
            Obstaculo("cristal", 21.0, 5.0, 1.0, 1.0, (100, 150, 200)),
            Obstaculo("cristal", 7.0, 15.0, 1.0, 1.0, (200, 100, 150)),
            Obstaculo("cristal", 21.0, 15.0, 1.0, 1.0, (150, 200, 100)),
            Obstaculo("cristal", 14.0, 10.0, 1.5, 1.5, (180, 180, 220)),
            # Formações rochosas
            Obstaculo("rocha", 4.0, 10.0, 2.0, 3.0, (60, 50, 80)),
            Obstaculo("rocha", 24.0, 10.0, 2.0, 3.0, (60, 50, 80)),
        ],
    ),
    
    # === CASTELO MEDIEVAL ===
    "Castelo": ArenaConfig(
        nome="Salão do Trono",
        largura=30.0,
        altura=22.0,
        cor_chao=(40, 35, 30),
        cor_parede=(70, 60, 50),
        cor_borda=(120, 100, 80),
        formato="retangular",
        tema="medieval",
        descricao="O salão real aguarda sangue",
        icone="🏰",
        obstaculos=[
            # Pilares do salão
            Obstaculo("pilar", 8.0, 7.0, 1.5, 1.5, (90, 80, 70)),
            Obstaculo("pilar", 22.0, 7.0, 1.5, 1.5, (90, 80, 70)),
            Obstaculo("pilar", 8.0, 15.0, 1.5, 1.5, (90, 80, 70)),
            Obstaculo("pilar", 22.0, 15.0, 1.5, 1.5, (90, 80, 70)),
            # Trono no fundo (made larger and brighter for better visibility)
            Obstaculo("trono", 15.0, 3.5, 4.0, 3.0, (180, 140, 60)),
            # Tapete (não sólido)
            Obstaculo("tapete", 15.0, 11.0, 6.0, 12.0, (120, 30, 30), solido=False),
        ],
    ),
    
    # === VULCÃO ===
    "Vulcao": ArenaConfig(
        nome="Cratera Vulcânica",
        largura=26.0,
        altura=26.0,
        cor_chao=(50, 25, 15),
        cor_parede=(80, 40, 20),
        cor_borda=(200, 80, 30),
        formato="circular",
        tema="vulcao",
        descricao="Lava e calor intenso",
        icone="🌋",
        cor_ambiente=(50, 20, 0),
        obstaculos=[
            # Poças de lava (dano!)
            Obstaculo("lava", 8.0, 13.0, 3.0, 3.0, (255, 100, 0), solido=False),
            Obstaculo("lava", 18.0, 13.0, 3.0, 3.0, (255, 100, 0), solido=False),
            Obstaculo("lava", 13.0, 8.0, 2.5, 2.5, (255, 120, 20), solido=False),
            Obstaculo("lava", 13.0, 18.0, 2.5, 2.5, (255, 120, 20), solido=False),
            # Rochas vulcânicas
            Obstaculo("rocha", 6.0, 6.0, 1.5, 1.5, (60, 30, 20)),
            Obstaculo("rocha", 20.0, 6.0, 1.5, 1.5, (60, 30, 20)),
            Obstaculo("rocha", 6.0, 20.0, 1.5, 1.5, (60, 30, 20)),
            Obstaculo("rocha", 20.0, 20.0, 1.5, 1.5, (60, 30, 20)),
        ],
        efeitos_especiais=["calor", "particulas_fogo"],
    ),
    
    # === CEMITÉRIO ===
    "Cemiterio": ArenaConfig(
        nome="Cemitério Amaldiçoado",
        largura=28.0,
        altura=20.0,
        cor_chao=(25, 30, 25),
        cor_parede=(40, 45, 40),
        cor_borda=(60, 70, 60),
        formato="retangular",
        tema="gotico",
        descricao="Os mortos observam a luta",
        icone="⚰️",
        cor_ambiente=(20, 25, 35),
        obstaculos=[
            # Lápides
            Obstaculo("lapide", 5.0, 5.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 9.0, 5.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 19.0, 5.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 23.0, 5.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 5.0, 15.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 9.0, 15.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 19.0, 15.0, 1.0, 0.5, (80, 80, 80)),
            Obstaculo("lapide", 23.0, 15.0, 1.0, 0.5, (80, 80, 80)),
            # Cripta central
            Obstaculo("cripta", 14.0, 10.0, 4.0, 3.0, (60, 65, 60)),
        ],
        efeitos_especiais=["neblina"],
    ),
    
    # === NAVE ESPACIAL ===
    "Espacial": ArenaConfig(
        nome="Estação Orbital",
        largura=24.0,
        altura=18.0,
        cor_chao=(30, 35, 45),
        cor_parede=(50, 60, 80),
        cor_borda=(100, 150, 200),
        formato="retangular",
        tema="scifi",
        descricao="Gravidade artificial instável",
        icone="🚀",
        cor_ambiente=(10, 20, 40),
        obstaculos=[
            # Consoles
            Obstaculo("console", 4.0, 4.0, 2.0, 1.0, (50, 70, 100)),
            Obstaculo("console", 20.0, 4.0, 2.0, 1.0, (50, 70, 100)),
            Obstaculo("console", 4.0, 14.0, 2.0, 1.0, (50, 70, 100)),
            Obstaculo("console", 20.0, 14.0, 2.0, 1.0, (50, 70, 100)),
            # Núcleo central
            Obstaculo("nucleo", 12.0, 9.0, 2.5, 2.5, (80, 200, 255)),
            # Painéis laterais
            Obstaculo("painel", 8.0, 9.0, 0.5, 4.0, (40, 60, 90)),
            Obstaculo("painel", 16.0, 9.0, 0.5, 4.0, (40, 60, 90)),
        ],
        efeitos_especiais=["luzes_piscando"],
    ),
    
    # === RINGUE DE BOXE ===
    "Ringue": ArenaConfig(
        nome="Ringue de Boxe",
        largura=14.0,
        altura=14.0,
        cor_chao=(40, 35, 30),
        cor_parede=(80, 20, 20),
        cor_borda=(200, 50, 50),
        formato="retangular",
        tema="esporte",
        descricao="Combate direto e brutal",
        icone="🥊",
    ),
    
    # === PRAIA PARADISÍACA ===
    "Praia": ArenaConfig(
        nome="Praia do Confronto",
        largura=34.0,
        altura=22.0,
        cor_chao=(220, 200, 150),  # Areia
        cor_parede=(100, 180, 220),  # Água
        cor_borda=(150, 200, 240),
        formato="retangular",
        tema="praia",
        descricao="Sol, areia e sangue",
        icone="🏖️",
        cor_ambiente=(40, 50, 60),
        obstaculos=[
            # Palmeiras
            Obstaculo("palmeira", 6.0, 5.0, 1.5, 1.5, (80, 60, 40)),
            Obstaculo("palmeira", 28.0, 5.0, 1.5, 1.5, (80, 60, 40)),
            Obstaculo("palmeira", 6.0, 17.0, 1.5, 1.5, (80, 60, 40)),
            Obstaculo("palmeira", 28.0, 17.0, 1.5, 1.5, (80, 60, 40)),
            # Rochas na areia
            Obstaculo("rocha", 17.0, 8.0, 2.0, 1.5, (120, 115, 100)),
            Obstaculo("rocha", 17.0, 14.0, 1.5, 1.0, (120, 115, 100)),
        ],
    ),
    
    # === TEMPLO ANTIGO ===
    "Templo": ArenaConfig(
        nome="Templo Esquecido",
        largura=26.0,
        altura=26.0,
        cor_chao=(50, 55, 45),
        cor_parede=(70, 80, 60),
        cor_borda=(100, 120, 80),
        formato="octogono",
        tema="ruinas",
        descricao="Ruínas de poder antigo",
        icone="🗿",
        obstaculos=[
            # Pilares quebrados
            Obstaculo("pilar_quebrado", 8.0, 8.0, 1.5, 1.5, (90, 100, 80)),
            Obstaculo("pilar_quebrado", 18.0, 8.0, 1.5, 1.5, (90, 100, 80)),
            Obstaculo("pilar_quebrado", 8.0, 18.0, 1.5, 1.5, (90, 100, 80)),
            Obstaculo("pilar_quebrado", 18.0, 18.0, 1.5, 1.5, (90, 100, 80)),
            # Altar central
            Obstaculo("altar", 13.0, 13.0, 3.0, 3.0, (80, 70, 50)),
        ],
        efeitos_especiais=["poeira"],
    ),
    
    # === ARENA DE GELO ===
    "Gelo": ArenaConfig(
        nome="Tundra Congelada",
        largura=28.0,
        altura=20.0,
        cor_chao=(180, 200, 220),
        cor_parede=(120, 150, 180),
        cor_borda=(200, 230, 255),
        formato="retangular",
        tema="gelo",
        descricao="Superfície escorregadia",
        icone="❄️",
        cor_ambiente=(30, 40, 60),
        obstaculos=[
            # Blocos de gelo
            Obstaculo("gelo", 7.0, 6.0, 2.5, 2.5, (150, 200, 240)),
            Obstaculo("gelo", 21.0, 6.0, 2.5, 2.5, (150, 200, 240)),
            Obstaculo("gelo", 7.0, 14.0, 2.5, 2.5, (150, 200, 240)),
            Obstaculo("gelo", 21.0, 14.0, 2.5, 2.5, (150, 200, 240)),
            Obstaculo("gelo", 14.0, 10.0, 3.0, 2.0, (170, 210, 250)),
        ],
        efeitos_especiais=["neve", "escorregadio"],
    ),
    
    # === INFERNO ===
    "Inferno": ArenaConfig(
        nome="Portões do Inferno",
        largura=30.0,
        altura=24.0,
        cor_chao=(40, 15, 15),
        cor_parede=(80, 20, 20),
        cor_borda=(200, 50, 0),
        formato="retangular",
        tema="inferno",
        descricao="Fogo eterno queima tudo",
        icone="👹",
        cor_ambiente=(60, 15, 0),
        obstaculos=[
            # Pilares de fogo
            Obstaculo("fogo", 8.0, 6.0, 2.0, 2.0, (255, 100, 0), solido=False),
            Obstaculo("fogo", 22.0, 6.0, 2.0, 2.0, (255, 100, 0), solido=False),
            Obstaculo("fogo", 8.0, 18.0, 2.0, 2.0, (255, 100, 0), solido=False),
            Obstaculo("fogo", 22.0, 18.0, 2.0, 2.0, (255, 100, 0), solido=False),
            # Ossos/crânios
            Obstaculo("ossos", 15.0, 5.0, 3.0, 1.5, (200, 190, 170)),
            Obstaculo("ossos", 15.0, 19.0, 3.0, 1.5, (200, 190, 170)),
            # Trono demoníaco
            Obstaculo("trono", 15.0, 12.0, 2.5, 2.5, (100, 20, 20)),
        ],
        efeitos_especiais=["chamas", "gritos"],
    ),
    
    # === CIDADE CYBERPUNK ===
    "Cyberpunk": ArenaConfig(
        nome="Beco Neon",
        largura=22.0,
        altura=16.0,
        cor_chao=(25, 25, 35),
        cor_parede=(40, 30, 50),
        cor_borda=(255, 50, 150),
        formato="retangular",
        tema="cyberpunk",
        descricao="Luzes neon e sombras",
        icone="🌃",
        cor_ambiente=(40, 20, 50),
        obstaculos=[
            # Caixas de lixo
            Obstaculo("caixa", 4.0, 4.0, 1.5, 1.5, (60, 60, 70), destrutivel=True),
            Obstaculo("caixa", 18.0, 4.0, 1.5, 1.5, (60, 60, 70), destrutivel=True),
            Obstaculo("caixa", 4.0, 12.0, 1.5, 1.5, (60, 60, 70), destrutivel=True),
            Obstaculo("caixa", 18.0, 12.0, 1.5, 1.5, (60, 60, 70), destrutivel=True),
            # Barris
            Obstaculo("barril", 11.0, 8.0, 1.0, 1.0, (80, 50, 30), destrutivel=True),
        ],
        efeitos_especiais=["neon", "chuva"],
    ),
    
    # === LABIRINTO ===
    "Labirinto": ArenaConfig(
        nome="Labirinto de Pedra",
        largura=30.0,
        altura=24.0,
        cor_chao=(45, 45, 40),
        cor_parede=(80, 75, 70),
        cor_borda=(100, 95, 90),
        formato="retangular",
        tema="labirinto",
        descricao="Muitos obstáculos para usar",
        icone="🧱",
        obstaculos=[
            # Paredes do labirinto
            Obstaculo("parede", 10.0, 8.0, 6.0, 0.8, (90, 85, 80)),
            Obstaculo("parede", 20.0, 16.0, 6.0, 0.8, (90, 85, 80)),
            Obstaculo("parede", 8.0, 12.0, 0.8, 8.0, (90, 85, 80)),
            Obstaculo("parede", 22.0, 12.0, 0.8, 8.0, (90, 85, 80)),
            # Pilares
            Obstaculo("pilar", 15.0, 6.0, 1.2, 1.2, (100, 95, 85)),
            Obstaculo("pilar", 15.0, 18.0, 1.2, 1.2, (100, 95, 85)),
        ],
    ),

    # === ARENAS VERTICAIS (9:16) — DESENHADAS PARA O VIDEO DE CELULAR ===
    # Toda arena acima e paisagem ou quadrada. Com a camera presa em 1080x1920
    # o quadro encaixa pela LARGURA e sobra faixa morta em cima e embaixo, o
    # que espreme o lutador: medido, o Templo (26 m) deixava o corpo com 3,1%
    # da largura e o Ringue (14 m) com 5,0%. Estas tres tem proporcao 9:16
    # exata, entao a arena INTEIRA enche a tela vertical sem faixa morta.
    # As TRES tem o MESMO tamanho (10,125 x 18 m, 182 m2 — a faixa das
    # compactas: Arena Pequena 192, Ringue 196). Tamanho unico e deliberado:
    # com a camera presa o corpo na tela e proporcional ao zoom, entao arenas
    # de tamanhos diferentes dariam legibilidade diferente a cada estreia. A
    # variedade mora no tema, nas cores e nos obstaculos. 10,125 m e o ponto
    # otimo: pede zoom 1,62 e o teto da camera e `zoom_max` 1,6 — arena menor
    # nao renderia mais nada, so comprimiria a luta.
    # O corredor central fica livre; os obstaculos moram nas laterais, porque
    # num palco estreito qualquer coisa no meio vira parede.
    "Duto": ArenaConfig(
        nome="Duto de Servico",
        largura=10.125,
        altura=18.0,
        cor_chao=(22, 26, 38),
        cor_parede=(30, 90, 110),
        cor_borda=(0, 200, 230),
        formato="retangular",
        tema="cyberpunk",
        descricao="Corredor vertical de neon",
        icone="🧪",
        cor_ambiente=(20, 40, 60),
        obstaculos=[
            Obstaculo("caixa", 1.7, 5.5, 1.2, 1.2, (60, 80, 100), destrutivel=True),
            Obstaculo("caixa", 8.4, 12.5, 1.2, 1.2, (60, 80, 100), destrutivel=True),
        ],
    ),

    "Poco": ArenaConfig(
        nome="Poco do Templo",
        largura=10.125,
        altura=18.0,
        cor_chao=(46, 50, 42),
        cor_parede=(66, 76, 58),
        cor_borda=(104, 124, 84),
        formato="retangular",
        tema="ruinas",
        descricao="Fenda funda entre ruinas",
        icone="🗿",
        obstaculos=[
            Obstaculo("pilar_quebrado", 1.8, 5.5, 1.3, 1.3, (90, 100, 80)),
            Obstaculo("pilar_quebrado", 8.3, 12.5, 1.3, 1.3, (90, 100, 80)),
        ],
        efeitos_especiais=["poeira"],
    ),

    "Torre": ArenaConfig(
        nome="Salao da Torre",
        largura=10.125,
        altura=18.0,
        cor_chao=(38, 32, 30),
        cor_parede=(78, 62, 48),
        cor_borda=(150, 118, 70),
        formato="retangular",
        tema="castelo",
        descricao="Salao alto e estreito",
        icone="🏰",
        cor_ambiente=(30, 22, 16),
        obstaculos=[
            Obstaculo("pilar", 1.8, 5.5, 1.2, 1.2, (100, 95, 85)),
            Obstaculo("pilar", 8.3, 12.5, 1.2, 1.2, (100, 95, 85)),
        ],
    ),
}

# As arenas 9:16, na ordem em que o sorteio de video as ve. O random_builds
# importa DAQUI em vez de repetir os nomes: arena nova entra no sorteio ao
# ser adicionada nesta tupla, e em nenhum outro lugar.
ARENAS_VERTICAIS = ("Duto", "Poco", "Torre")

# Lista ordenada de mapas para seleção
LISTA_MAPAS = [
    "Arena", "Arena Pequena", "Ringue", "Coliseu", "Dojo",
    "Castelo", "Templo", "Floresta", "Caverna", "Gelo",
    "Vulcao", "Inferno", "Cemiterio", "Praia", "Espacial",
    "Cyberpunk", "Labirinto",
    # 9:16, para o video vertical (ver ARENAS_VERTICAIS)
    "Duto", "Poco", "Torre"
]

def get_mapa_info(nome: str) -> dict:
    """Retorna informações do mapa para exibição"""
    if nome not in ARENAS:
        return {}
    cfg = ARENAS[nome]
    return {
        "nome": cfg.nome,
        "descricao": cfg.descricao,
        "icone": cfg.icone,
        "tamanho": f"{cfg.largura:.0f}x{cfg.altura:.0f}m",
        "formato": cfg.formato.capitalize(),
        "obstaculos": len(cfg.obstaculos),
        "tema": cfg.tema,
    }


class Arena:
    """
    Sistema de arena com limites, paredes e obstáculos.
    """
    
    def __init__(self, config: ArenaConfig = None):
        if config is None:
            config = ARENAS["Arena"]
        
        self.config = config
        self.largura = config.largura
        self.altura = config.altura
        
        # Limites em metros
        self.min_x = 0
        self.max_x = config.largura
        self.min_y = 0
        self.max_y = config.altura
        
        # Centro da arena
        self.centro_x = config.largura / 2
        self.centro_y = config.altura / 2
        
        # Para coliseu circular
        if config.formato == "circular":
            self.raio = min(config.largura, config.altura) / 2 - config.espessura_parede
        else:
            self.raio = None
        
        # Obstáculos — Onda 10D: cópia POR INSTÂNCIA. `list(...)` copiava a
        # lista mas não os objetos: quebrar um pilar numa luta quebraria o
        # catálogo ARENAS para todas as seguintes.
        self.obstaculos = (
            [dataclasses.replace(o) for o in config.obstaculos] if config.obstaculos else []
        )
        # Onda 10D: último obstáculo em que cada lutador bateu (wall-splat em
        # obstáculo destrutível quebra) e fila de destruições para o Simulador.
        self.ultimo_obstaculo_colidido: dict = {}
        self.eventos_obstaculo: list = []
        
        # Histórico de colisões para efeitos
        self.colisoes_recentes: List[Tuple[float, float, float]] = []  # (x, y, intensidade)
        
        # Cooldown de som de colisão por lutador (evita som repetido ao deslizar)
        self.wall_sound_cooldown: dict = {}  # {lutador_id: tempo_restante}
        
        # Efeitos especiais ativos
        self.efeitos_ativos = list(config.efeitos_especiais) if config.efeitos_especiais else []
    
    def ponto_dentro(self, x: float, y: float, margem: float = 0.3) -> bool:
        """Onda 8C: um ponto está dentro dos limites jogáveis da arena?

        O SpatialAwarenessSystem sempre assumiu este método (um dos
        motivos de nunca ter sido ligado). Circular usa o raio; octógono
        aproxima pelo círculo inscrito; retangular usa os limites.
        """
        if self.config.formato == "circular":
            dist = math.hypot(x - self.centro_x, y - self.centro_y)
            return dist + margem <= (self.raio or 0.0)
        if self.config.formato == "octogono":
            raio_inscrito = min(self.largura, self.altura) / 2 - margem
            return math.hypot(x - self.centro_x, y - self.centro_y) <= raio_inscrito
        return (
            self.min_x + margem <= x <= self.max_x - margem
            and self.min_y + margem <= y <= self.max_y - margem
        )

    def colide_obstaculo(self, x: float, y: float, raio: float) -> Optional[Obstaculo]:
        """
        Verifica se uma posição colide com algum obstáculo sólido.
        Retorna o obstáculo colidido ou None.
        """
        for obs in self.obstaculos:
            if not obs.solido:
                continue
            
            # AABB collision com círculo
            half_w = obs.largura / 2
            half_h = obs.altura / 2
            
            # Ponto mais próximo no retângulo
            closest_x = max(obs.x - half_w, min(x, obs.x + half_w))
            closest_y = max(obs.y - half_h, min(y, obs.y + half_h))
            
            # Distância ao ponto mais próximo
            dist = math.hypot(x - closest_x, y - closest_y)
            
            if dist < raio:
                return obs
        
        return None
    
    def obstaculos_no_raio(self, x: float, y: float, raio: float) -> list:
        """Onda 10D: obstáculos SÓLIDOS tocados por um círculo (área/explosão)."""
        tocados = []
        for obs in self.obstaculos:
            if not obs.solido:
                continue
            half_w = obs.largura / 2
            half_h = obs.altura / 2
            closest_x = max(obs.x - half_w, min(x, obs.x + half_w))
            closest_y = max(obs.y - half_h, min(y, obs.y + half_h))
            if math.hypot(x - closest_x, y - closest_y) < raio:
                tocados.append(obs)
        return tocados

    def danificar_obstaculo(self, obs, dano: float, autor=None) -> bool:
        """Onda 10D: `destrutivel`/`hp` existiam no modelo e nunca eram lidos.
        Devolve True se o obstáculo QUEBROU (vira passável, `tipo` +
        "_quebrado", entra em `eventos_obstaculo`)."""
        if obs is None or not getattr(obs, "destrutivel", False) or not obs.solido:
            return False
        try:
            obs.hp = int(obs.hp) - int(max(0.0, float(dano)))
        except (TypeError, ValueError):
            return False
        if obs.hp > 0:
            return False
        obs.hp = 0
        obs.solido = False
        if not obs.tipo.endswith("_quebrado"):
            obs.tipo = obs.tipo + "_quebrado"
        obs.cor = tuple(max(0, int(c * 0.55)) for c in obs.cor)
        self.eventos_obstaculo.append((obs, autor))
        return True

    def esta_em_zona_perigo(self, x: float, y: float) -> Optional[str]:
        """
        Verifica se está em zona de perigo (lava, fogo, etc.)
        Retorna o tipo de perigo ou None.
        """
        for obs in self.obstaculos:
            if obs.tipo in ["lava", "fogo"]:
                half_w = obs.largura / 2
                half_h = obs.altura / 2
                
                if (obs.x - half_w <= x <= obs.x + half_w and
                    obs.y - half_h <= y <= obs.y + half_h):
                    return obs.tipo
        
        return None
    
    def aplicar_limites(self, lutador, dt: float) -> float:
        """
        Aplica limites da arena ao lutador.
        Retorna a intensidade do impacto (0.0 se não houve impacto significativo).
        Deslizar na parede retorna 0.0, apenas impactos reais retornam > 0.
        """
        if not self.config.tem_paredes:
            return 0.0
        
        # Atualiza cooldown de som
        lutador_id = id(lutador)
        # Onda 10D: a memória do obstáculo batido vale só para este frame.
        self.ultimo_obstaculo_colidido.pop(lutador_id, None)
        if lutador_id in self.wall_sound_cooldown:
            self.wall_sound_cooldown[lutador_id] = max(0, self.wall_sound_cooldown[lutador_id] - dt)
        
        impacto_max = 0.0  # Maior intensidade de impacto neste frame
        margem = lutador.raio_fisico
        bounce = 0.3  # Coeficiente de rebote
        
        if self.config.formato == "circular":
            # Arena circular
            dx = lutador.pos[0] - self.centro_x
            dy = lutador.pos[1] - self.centro_y
            dist = math.hypot(dx, dy)
            
            if dist + margem > self.raio:
                # Colisão com borda circular
                
                # Normaliza direção
                if dist > 0:
                    nx, ny = dx / dist, dy / dist
                else:
                    nx, ny = 1, 0
                
                # Calcula velocidade perpendicular à parede ANTES do rebote
                dot = lutador.vel[0] * nx + lutador.vel[1] * ny
                
                # Empurra de volta
                lutador.pos[0] = self.centro_x + nx * (self.raio - margem - 0.01)
                lutador.pos[1] = self.centro_y + ny * (self.raio - margem - 0.01)
                
                # Rebote apenas se indo em direção à parede
                if dot > 0:
                    lutador.vel[0] -= (1 + bounce) * dot * nx
                    lutador.vel[1] -= (1 + bounce) * dot * ny
                    
                    # Registra impacto apenas se velocidade perpendicular significativa
                    intensidade = abs(dot)
                    if intensidade > 2:
                        self.colisoes_recentes.append((lutador.pos[0], lutador.pos[1], intensidade))
                        impacto_max = max(impacto_max, intensidade)
        
        elif self.config.formato == "octogono":
            # Arena octogonal (simplificado como retângulo com cantos cortados)
            impacto_ret = self._aplicar_limites_retangular(lutador, margem, bounce)
            impacto_max = max(impacto_max, impacto_ret)
            
            # Corta cantos (45 graus)
            corte = min(self.largura, self.altura) * 0.2
            cantos = [
                (self.min_x + corte, self.min_y, 1, 1),      # Superior esquerdo
                (self.max_x - corte, self.min_y, -1, 1),    # Superior direito
                (self.min_x + corte, self.max_y, 1, -1),    # Inferior esquerdo
                (self.max_x - corte, self.max_y, -1, -1),   # Inferior direito
            ]
            
            for cx, cy, dx, dy in cantos:
                # Verifica se está no canto
                px = lutador.pos[0]
                py = lutador.pos[1]
                
                if dx > 0:  # Esquerda
                    in_x = px < cx
                else:  # Direita
                    in_x = px > cx
                    
                if dy > 0:  # Cima
                    in_y = py < cy
                else:  # Baixo
                    in_y = py > cy
                
                if in_x and in_y:
                    # Está no canto - aplica limite diagonal
                    # Linha do canto: dy*x + dx*y = dy*cx + dx*cy
                    linha_val = dy * (px - cx) + dx * (py - cy)
                    if (dx * dy > 0 and linha_val < 0) or (dx * dy < 0 and linha_val > 0):
                        # Projeta de volta
                        norm = math.hypot(dx, dy)
                        nx, ny = dx / norm, dy / norm
                        dist_linha = abs(linha_val) / norm
                        
                        # Calcula velocidade perpendicular ao canto
                        vel_perp = abs(lutador.vel[0] * nx + lutador.vel[1] * ny)
                        if vel_perp > 2:
                            impacto_max = max(impacto_max, vel_perp)
                        
                        lutador.pos[0] += nx * (dist_linha + margem)
                        lutador.pos[1] += ny * (dist_linha + margem)
        else:
            # Arena retangular padrão
            impacto_ret = self._aplicar_limites_retangular(lutador, margem, bounce)
            impacto_max = max(impacto_max, impacto_ret)
        
        # Aplica colisão com obstáculos
        impacto_obs = self._aplicar_colisao_obstaculos(lutador, margem, bounce)
        impacto_max = max(impacto_max, impacto_obs)
        
        return impacto_max
    
    def _aplicar_colisao_obstaculos(self, lutador, margem: float, bounce: float) -> float:
        """Aplica colisão com obstáculos sólidos. Retorna intensidade do impacto."""
        impacto_max = 0.0
        
        for obs in self.obstaculos:
            if not obs.solido:
                continue
            
            half_w = obs.largura / 2
            half_h = obs.altura / 2
            
            # AABB expandida pelo raio do lutador
            left = obs.x - half_w - margem
            right = obs.x + half_w + margem
            top = obs.y - half_h - margem
            bottom = obs.y + half_h + margem
            
            px, py = lutador.pos[0], lutador.pos[1]
            
            if left < px < right and top < py < bottom:
                # Onda 10D: registra o obstáculo (wall-splat destrutível).
                self.ultimo_obstaculo_colidido[id(lutador)] = obs
                # Determina lado de colisão
                dist_left = px - left
                dist_right = right - px
                dist_top = py - top
                dist_bottom = bottom - py
                
                min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
                
                if min_dist == dist_left:
                    lutador.pos[0] = left
                    if lutador.vel[0] > 0:
                        impacto_max = max(impacto_max, abs(lutador.vel[0]))
                        lutador.vel[0] *= -bounce
                elif min_dist == dist_right:
                    lutador.pos[0] = right
                    if lutador.vel[0] < 0:
                        impacto_max = max(impacto_max, abs(lutador.vel[0]))
                        lutador.vel[0] *= -bounce
                elif min_dist == dist_top:
                    lutador.pos[1] = top
                    if lutador.vel[1] > 0:
                        impacto_max = max(impacto_max, abs(lutador.vel[1]))
                        lutador.vel[1] *= -bounce
                else:
                    lutador.pos[1] = bottom
                    if lutador.vel[1] < 0:
                        impacto_max = max(impacto_max, abs(lutador.vel[1]))
                        lutador.vel[1] *= -bounce
                
                # Registra colisão apenas se impacto significativo
                if impacto_max > 2:
                    self.colisoes_recentes.append((lutador.pos[0], lutador.pos[1], impacto_max))
        
        return impacto_max
    
    def _aplicar_limites_retangular(self, lutador, margem: float, bounce: float) -> float:
        """Aplica limites retangulares. Retorna intensidade do impacto (0 se apenas deslizando)."""
        impacto_max = 0.0
        
        # Parede esquerda
        if lutador.pos[0] - margem < self.min_x:
            lutador.pos[0] = self.min_x + margem
            # Só conta como impacto se estava indo em direção à parede
            if lutador.vel[0] < 0:
                intensidade = abs(lutador.vel[0])
                lutador.vel[0] *= -bounce
                if intensidade > 2:
                    self.colisoes_recentes.append((lutador.pos[0], lutador.pos[1], intensidade))
                    impacto_max = max(impacto_max, intensidade)
        
        # Parede direita
        if lutador.pos[0] + margem > self.max_x:
            lutador.pos[0] = self.max_x - margem
            if lutador.vel[0] > 0:
                intensidade = abs(lutador.vel[0])
                lutador.vel[0] *= -bounce
                if intensidade > 2:
                    self.colisoes_recentes.append((lutador.pos[0], lutador.pos[1], intensidade))
                    impacto_max = max(impacto_max, intensidade)
        
        # Parede superior
        if lutador.pos[1] - margem < self.min_y:
            lutador.pos[1] = self.min_y + margem
            if lutador.vel[1] < 0:
                intensidade = abs(lutador.vel[1])
                lutador.vel[1] *= -bounce
                if intensidade > 2:
                    self.colisoes_recentes.append((lutador.pos[0], lutador.pos[1], intensidade))
                    impacto_max = max(impacto_max, intensidade)
        
        # Parede inferior
        if lutador.pos[1] + margem > self.max_y:
            lutador.pos[1] = self.max_y - margem
            if lutador.vel[1] > 0:
                intensidade = abs(lutador.vel[1])
                lutador.vel[1] *= -bounce
                if intensidade > 2:
                    self.colisoes_recentes.append((lutador.pos[0], lutador.pos[1], intensidade))
                    impacto_max = max(impacto_max, intensidade)
        
        return impacto_max
    
    def esta_dentro(self, x: float, y: float, margem: float = 0) -> bool:
        """Verifica se um ponto está dentro da arena"""
        if self.config.formato == "circular":
            dx = x - self.centro_x
            dy = y - self.centro_y
            return math.hypot(dx, dy) + margem <= self.raio
        else:
            return (self.min_x + margem <= x <= self.max_x - margem and
                    self.min_y + margem <= y <= self.max_y - margem)
    
    def get_spawn_points(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Retorna pontos de spawn para dois lutadores"""
        # P1 na esquerda, P2 na direita
        p1_x = self.centro_x - self.largura * 0.3
        p1_y = self.centro_y
        
        p2_x = self.centro_x + self.largura * 0.3
        p2_y = self.centro_y
        
        return (p1_x, p1_y), (p2_x, p2_y)
    
    def limpar_colisoes(self):
        """Limpa histórico de colisões após processamento"""
        # Limpa completamente - colisões já foram processadas neste frame
        self.colisoes_recentes.clear()
    
    def desenhar(self, surface: pygame.Surface, camera):
        """
        Desenha a arena na tela.
        """
        # Desenha chão
        self._desenhar_chao(surface, camera)
        
        # Desenha obstáculos
        self._desenhar_obstaculos(surface, camera)
        
        # Desenha paredes
        if self.config.tem_paredes:
            self._desenhar_paredes(surface, camera)
        
        # Desenha efeitos de colisão com paredes
        self._desenhar_efeitos_colisao(surface, camera)
    
    # Quanto o tom mais escuro do chao precisa ficar ACIMA do fundo, em
    # luminancia. Medido em 11/09/2026: `cor_chao * 0.72` deixava Duto em
    # 18,0 e Torre em 23,7 contra 25,4 do COR_FUNDO — nas duas, a borda do
    # palco ficava mais ESCURA que o vazio em volta e a arena sumia na
    # moldura. Duas das tres arenas que vao ao ar.
    PISO_DE_CONTRASTE = 12.0

    @staticmethod
    def _luminancia(cor) -> float:
        return 0.2126 * cor[0] + 0.7152 * cor[1] + 0.0722 * cor[2]

    @classmethod
    def _tons_do_chao(cls, cor):
        """(escuro, meio, claro) com o escuro garantidamente sobre o fundo.

        A vinheta continua sendo a mesma multiplicacao de antes; o que muda
        e que o tom mais escuro tem PISO. Sem isso, uma arena de chao
        escuro desenha a propria borda com menos luz que o nada em volta.
        """
        escuro = [max(0, int(c * 0.72)) for c in cor]
        alvo = cls._luminancia(COR_FUNDO) + cls.PISO_DE_CONTRASTE
        falta = alvo - cls._luminancia(escuro)
        if falta > 0:
            # Somar o mesmo em todos os canais preserva o matiz do chao —
            # clarear por multiplicacao saturaria o canal dominante.
            escuro = [min(255, int(c + falta)) for c in escuro]
        meio = [max(0, int(c * 0.88)) for c in cor]
        claro = [min(255, int(c * 1.18) + 6) for c in cor]
        # A escada tem que continuar subindo depois do piso, senao a
        # vinheta inverte e o centro fica mais escuro que a borda.
        meio = [max(a, b) for a, b in zip(meio, escuro)]
        claro = [max(a, b) for a, b in zip(claro, meio)]
        return tuple(escuro), tuple(meio), tuple(claro)

    def _desenhar_chao(self, surface: pygame.Surface, camera):
        """Desenha o chão da arena"""
        cor = self.config.cor_chao
        
        if self.config.formato == "circular":
            # Chão circular com profundidade (passe de arte 1): vinheta
            # radial em anéis + borda dupla que lê como parede. Um círculo
            # chapado não dá palco; o olho precisa de centro e limite.
            cx, cy = camera.converter(self.centro_x * PPM, self.centro_y * PPM)
            raio = camera.converter_tam(self.raio * PPM)
            if raio > 0:
                escuro, meio, claro = self._tons_do_chao(cor)
                pygame.draw.circle(surface, escuro, (cx, cy), raio)
                pygame.draw.circle(surface, meio, (cx, cy), int(raio * 0.86))
                pygame.draw.circle(surface, cor, (cx, cy), int(raio * 0.62))
                pygame.draw.circle(surface, claro, (cx, cy), int(raio * 0.30))
                # borda-parede: traço escuro grosso + fio de luz interno
                pygame.draw.circle(
                    surface, tuple(max(0, c - 26) for c in escuro),
                    (cx, cy), raio, max(3, raio // 90),
                )
                pygame.draw.circle(
                    surface, tuple(min(255, c + 46) for c in cor),
                    (cx, cy), raio - max(3, raio // 90), 2,
                )
        else:
            # Chão retangular
            min_px = camera.converter(self.min_x * PPM, self.min_y * PPM)
            max_px = camera.converter(self.max_x * PPM, self.max_y * PPM)
            
            largura = max_px[0] - min_px[0]
            altura = max_px[1] - min_px[1]
            
            if largura > 0 and altura > 0:
                # Passe 7 (arte): o retangular ganha o tratamento do
                # circular - vinheta em camadas + borda que le parede.
                rect = pygame.Rect(min_px[0], min_px[1], largura, altura)
                escuro, meio, claro = self._tons_do_chao(cor)
                pygame.draw.rect(surface, escuro, rect)
                pygame.draw.rect(surface, meio, rect.inflate(-int(largura * 0.10), -int(altura * 0.10)))
                pygame.draw.rect(surface, cor, rect.inflate(-int(largura * 0.30), -int(altura * 0.30)))
                pygame.draw.rect(surface, claro, rect.inflate(-int(largura * 0.62), -int(altura * 0.62)))
                borda = max(3, int(min(largura, altura)) // 90)
                pygame.draw.rect(
                    surface, tuple(max(0, c - 26) for c in escuro), rect, borda
                )
                pygame.draw.rect(
                    surface, tuple(min(255, c + 46) for c in cor),
                    rect.inflate(-borda * 2, -borda * 2), 2,
                )
        
        # Grid no chão — só no formato retangular: nas arenas circulares e
        # octogonais as linhas vazavam para fora do disco (Passe 2), e a
        # vinheta em anéis já dá textura ao chão redondo.
        if self.config.formato == "retangular":
            self._desenhar_grid(surface, camera)
    
    def _desenhar_grid(self, surface: pygame.Surface, camera):
        """Desenha grid no chão"""
        grid_size = 2.0  # Metros
        # Textura, nao informacao — mas VISIVEL. Com +5 por canal o grid
        # ficava abaixo do que a compressao do mp4 preserva: o chao lia
        # como um borrao liso, e sem referencia de escala a luta parece
        # acontecer no vazio. +14 continua discreto e sobrevive ao h264.
        cor_grid = tuple(min(255, c + 14) for c in self.config.cor_chao)
        
        # Linhas verticais
        x = math.ceil(self.min_x / grid_size) * grid_size
        while x < self.max_x:
            p1 = camera.converter(x * PPM, self.min_y * PPM)
            p2 = camera.converter(x * PPM, self.max_y * PPM)
            pygame.draw.line(surface, cor_grid, p1, p2, 1)
            x += grid_size
        
        # Linhas horizontais
        y = math.ceil(self.min_y / grid_size) * grid_size
        while y < self.max_y:
            p1 = camera.converter(self.min_x * PPM, y * PPM)
            p2 = camera.converter(self.max_x * PPM, y * PPM)
            pygame.draw.line(surface, cor_grid, p1, p2, 1)
            y += grid_size
    
    def _desenhar_obstaculos(self, surface: pygame.Surface, camera):
        """Desenha os obstáculos da arena"""
        for obs in self.obstaculos:
            cx, cy = camera.converter(obs.x * PPM, obs.y * PPM)
            cx, cy = int(cx), int(cy)  # Ensure integers
            half_w = int(camera.converter_tam(obs.largura * PPM / 2))
            half_h = int(camera.converter_tam(obs.altura * PPM / 2))
            
            if half_w < 1 or half_h < 1:
                continue
            
            rect = pygame.Rect(cx - half_w, cy - half_h, half_w * 2, half_h * 2)
            cor = obs.cor

            # Onda 10D: obstáculo QUEBRADO vira entulho achatado com rachaduras
            # (pilar_quebrado do catálogo mantém o desenho próprio abaixo).
            if obs.tipo.endswith("_quebrado") and obs.tipo != "pilar_quebrado":
                alt = max(2, int(half_h * 0.8))
                entulho = pygame.Rect(cx - half_w, cy + half_h - alt, half_w * 2, alt)
                pygame.draw.rect(surface, cor, entulho)
                cor_esc = tuple(max(0, c - 25) for c in cor)
                pygame.draw.line(surface, cor_esc, (entulho.left + 2, entulho.top + alt // 2),
                                 (entulho.right - 2, entulho.top + 1), 2)
                pygame.draw.line(surface, cor_esc, (cx - half_w // 2, entulho.top),
                                 (cx + half_w // 3, entulho.bottom - 1), 1)
                continue

            # Passe 7 (arte): sombra de contato achatada - obstaculo sem
            # sombra flutua; com ela pertence ao chao (planos nao tem).
            if obs.tipo not in ("tapete", "lava", "fogo", "gelo"):
                sw = int(half_w * 2.2)
                sh = max(3, int(half_h * 0.7))
                s_sombra = pygame.Surface((sw, sh), pygame.SRCALPHA)
                pygame.draw.ellipse(s_sombra, (0, 0, 0, 80), (0, 0, sw, sh))
                surface.blit(s_sombra, (cx - sw // 2, cy + half_h - sh // 2))

            # Desenho especial baseado no tipo
            if obs.tipo in ["pilar", "pilar_quebrado"]:
                # Pilar cilíndrico
                pygame.draw.ellipse(surface, cor, rect)
                # Sombra superior
                cor_clara = tuple(min(255, c + 30) for c in cor)
                top_rect = pygame.Rect(int(cx - half_w * 0.8), int(cy - half_h * 0.9), int(half_w * 1.6), int(half_h * 0.6))
                pygame.draw.ellipse(surface, cor_clara, top_rect)
                # Se quebrado, adiciona rachadura
                if obs.tipo == "pilar_quebrado":
                    pygame.draw.line(surface, (40, 40, 40), (int(cx - half_w * 0.3), int(cy - half_h)), 
                                   (int(cx + half_w * 0.2), int(cy + half_h * 0.5)), 2)
            
            elif obs.tipo in ["lava", "fogo"]:
                # Efeito pulsante para fogo/lava
                import time
                pulse = int(abs(math.sin(time.time() * 3)) * 50)
                cor = (min(255, cor[0] + pulse), max(0, cor[1] - pulse//2), 0)
                pygame.draw.rect(surface, cor, rect)
                # Brilho interno
                inner_rect = rect.inflate(-4, -4)
                inner_cor = (255, min(255, cor[1] + 80), 50)
                pygame.draw.rect(surface, inner_cor, inner_rect)
            
            elif obs.tipo == "cristal":
                # Cristal com brilho
                import time
                brilho = int(abs(math.sin(time.time() * 2 + obs.x)) * 40)
                cor = tuple(min(255, c + brilho) for c in obs.cor)
                # Desenha hexágono aproximado
                pontos = [
                    (cx, cy - half_h),
                    (cx + half_w * 0.8, cy - half_h * 0.5),
                    (cx + half_w * 0.8, cy + half_h * 0.5),
                    (cx, cy + half_h),
                    (cx - half_w * 0.8, cy + half_h * 0.5),
                    (cx - half_w * 0.8, cy - half_h * 0.5),
                ]
                pygame.draw.polygon(surface, cor, pontos)
                pygame.draw.polygon(surface, (255, 255, 255), pontos, 2)
            
            elif obs.tipo in ["arvore", "palmeira"]:
                # Tronco
                tronco_rect = pygame.Rect(int(cx - half_w * 0.3), int(cy - half_h * 0.5), int(half_w * 0.6), int(half_h * 1.5))
                pygame.draw.rect(surface, cor, tronco_rect)
                # Copa
                copa_cor = (30, 80, 30) if obs.tipo == "arvore" else (50, 120, 40)
                pygame.draw.circle(surface, copa_cor, (cx, int(cy - half_h * 0.3)), int(half_w * 1.2))
            
            elif obs.tipo == "tapete":
                # Tapete decorativo (não sólido)
                pygame.draw.rect(surface, cor, rect)
                # Bordas douradas
                pygame.draw.rect(surface, (180, 150, 50), rect, 3)
            
            elif obs.tipo == "trono":
                # Trono especial - enhanced visibility
                cor_ouro = (255, 215, 0)  # Gold
                cor_veludo = (100, 20, 40)  # Dark red velvet
                
                # Base do trono (assento)
                pygame.draw.rect(surface, cor, rect)
                # Borda do assento
                pygame.draw.rect(surface, cor_ouro, rect, 3)
                
                # Encosto alto (backrest)
                encosto_h = int(half_h * 1.8)
                encosto_w = int(half_w * 1.4)
                encosto_rect = pygame.Rect(cx - encosto_w // 2, cy - half_h - encosto_h, encosto_w, encosto_h)
                pygame.draw.rect(surface, cor, encosto_rect)
                pygame.draw.rect(surface, cor_ouro, encosto_rect, 3)
                
                # Almofada do assento (veludo)
                almofada = pygame.Rect(cx - half_w + 4, cy - half_h + 4, half_w * 2 - 8, half_h * 2 - 8)
                pygame.draw.rect(surface, cor_veludo, almofada)
                
                # Detalhes dourados no encosto
                deco_y = cy - half_h - encosto_h // 2
                pygame.draw.circle(surface, cor_ouro, (cx, int(deco_y)), max(4, int(half_w * 0.3)))
                
                # Apoios de braço
                arm_w = int(half_w * 0.3)
                arm_h = int(half_h * 0.6)
                # Esquerdo
                pygame.draw.rect(surface, cor, pygame.Rect(cx - half_w - arm_w, cy - arm_h // 2, arm_w, arm_h))
                # Direito
                pygame.draw.rect(surface, cor, pygame.Rect(cx + half_w, cy - arm_h // 2, arm_w, arm_h))
            
            elif obs.tipo in ["gelo"]:
                # Gelo semi-transparente
                s = pygame.Surface((half_w * 2, half_h * 2), pygame.SRCALPHA)
                pygame.draw.rect(s, (*cor, 180), (0, 0, half_w * 2, half_h * 2))
                # Reflexos
                pygame.draw.line(s, (255, 255, 255, 100), (5, 5), (half_w, half_h * 0.7), 2)
                surface.blit(s, (cx - half_w, cy - half_h))
            
            elif obs.tipo == "lapide":
                # Lápide
                # Base
                pygame.draw.rect(surface, cor, rect)
                # Topo arredondado
                pygame.draw.arc(surface, cor, 
                              pygame.Rect(cx - half_w, cy - half_h * 1.5, half_w * 2, half_h),
                              0, 3.14159, max(2, int(half_w * 0.5)))
            
            elif obs.tipo == "nucleo":
                # Núcleo energético
                import time
                pulse = abs(math.sin(time.time() * 4))
                raio = int(half_w * (0.8 + pulse * 0.2))
                # Aura externa
                pygame.draw.circle(surface, (cor[0]//2, cor[1]//2, cor[2]//2), (cx, cy), int(half_w * 1.3))
                # Núcleo
                pygame.draw.circle(surface, cor, (cx, cy), raio)
                # Centro brilhante
                pygame.draw.circle(surface, (255, 255, 255), (cx, cy), max(3, raio // 3))
            
            elif obs.tipo in ("rocha", "pedra"):
                # Poligono irregular deterministico da posicao
                semente = obs.x * 13.7 + obs.y * 7.3
                pontos = []
                for i in range(7):
                    a = i * math.tau / 7
                    fator = 0.75 + 0.25 * abs(math.sin(semente + i * 2.1))
                    pontos.append((
                        cx + math.cos(a) * half_w * fator,
                        cy + math.sin(a) * half_h * fator,
                    ))
                pygame.draw.polygon(surface, cor, pontos)
                pygame.draw.polygon(
                    surface, tuple(max(0, c - 30) for c in cor), pontos, 2
                )
                pygame.draw.circle(
                    surface, tuple(min(255, c + 25) for c in cor),
                    (int(cx - half_w * 0.25), int(cy - half_h * 0.3)),
                    max(2, int(half_w * 0.3)),
                )

            elif obs.tipo == "caixa":
                pygame.draw.rect(surface, cor, rect)
                pygame.draw.rect(
                    surface, tuple(max(0, c - 35) for c in cor), rect, 2
                )
                pygame.draw.line(
                    surface, tuple(max(0, c - 25) for c in cor),
                    (cx - half_w, cy), (cx + half_w, cy), 1,
                )
                pygame.draw.line(
                    surface, tuple(max(0, c - 25) for c in cor),
                    (cx, cy - half_h), (cx, cy + half_h), 1,
                )

            elif obs.tipo == "barril":
                pygame.draw.ellipse(surface, cor, rect)
                for frac_b in (-0.35, 0.35):
                    y_aro = int(cy + half_h * frac_b)
                    pygame.draw.line(
                        surface, tuple(max(0, c - 45) for c in cor),
                        (int(cx - half_w * 0.9), y_aro),
                        (int(cx + half_w * 0.9), y_aro), 2,
                    )
                pygame.draw.ellipse(
                    surface, tuple(max(0, c - 35) for c in cor), rect, 2
                )

            elif obs.tipo == "parede":
                pygame.draw.rect(surface, cor, rect)
                cor_junta = tuple(max(0, c - 30) for c in cor)
                n_fiadas = max(2, half_h // 6)
                for fi in range(1, n_fiadas):
                    y_f = cy - half_h + (half_h * 2 * fi) // n_fiadas
                    pygame.draw.line(surface, cor_junta,
                                     (cx - half_w, y_f), (cx + half_w, y_f), 1)
                pygame.draw.rect(surface, cor_junta, rect, 2)

            elif obs.tipo == "altar":
                base = rect.inflate(int(half_w * 0.6), int(half_h * 0.6))
                pygame.draw.rect(surface, tuple(max(0, c - 30) for c in cor), base)
                pygame.draw.rect(surface, cor, rect)
                topo = rect.inflate(-int(half_w * 0.7), -int(half_h * 0.7))
                pygame.draw.rect(
                    surface, tuple(min(255, c + 40) for c in cor), topo
                )
                pygame.draw.rect(surface, (220, 200, 140), rect, 2)

            elif obs.tipo == "cripta":
                pygame.draw.rect(surface, cor, rect)
                pygame.draw.ellipse(
                    surface, cor,
                    pygame.Rect(cx - half_w, cy - int(half_h * 1.6),
                                half_w * 2, half_h),
                )
                pygame.draw.rect(
                    surface, tuple(max(0, c - 35) for c in cor), rect, 2
                )
                cruz_c = tuple(min(255, c + 50) for c in cor)
                pygame.draw.line(surface, cruz_c,
                                 (cx, cy - int(half_h * 0.6)),
                                 (cx, cy + int(half_h * 0.4)), 2)
                pygame.draw.line(surface, cruz_c,
                                 (int(cx - half_w * 0.35), cy - int(half_h * 0.25)),
                                 (int(cx + half_w * 0.35), cy - int(half_h * 0.25)), 2)

            elif obs.tipo == "ossos":
                cor_osso = (225, 220, 200)
                semente = obs.x * 5.1 + obs.y * 3.3
                for i in range(3):
                    a = semente + i * 2.2
                    x1 = cx + math.cos(a) * half_w * 0.6
                    y1 = cy + math.sin(a) * half_h * 0.6
                    x2 = cx - math.cos(a) * half_w * 0.6
                    y2 = cy - math.sin(a) * half_h * 0.6
                    pygame.draw.line(surface, cor_osso,
                                     (int(x1), int(y1)), (int(x2), int(y2)), 3)
                    for px_o, py_o in ((x1, y1), (x2, y2)):
                        pygame.draw.circle(surface, cor_osso,
                                           (int(px_o), int(py_o)), 3)

            elif obs.tipo in ("console", "painel"):
                import time as _t
                pygame.draw.rect(surface, cor, rect)
                pygame.draw.rect(
                    surface, tuple(min(255, c + 35) for c in cor), rect, 2
                )
                if obs.tipo == "console":
                    for i in range(3):
                        aceso = (_t.time() * 2 + obs.x + i * 0.7) % 2.0 < 1.0
                        cor_led = (90, 255, 140) if aceso else (30, 70, 45)
                        pygame.draw.circle(
                            surface, cor_led,
                            (int(cx - half_w * 0.5 + i * half_w * 0.5),
                             int(cy - half_h * 0.4)), max(2, half_w // 8),
                        )
                else:
                    linha_y = cy - half_h + int(
                        ((_t.time() * 0.8 + obs.y) % 1.0) * half_h * 2
                    )
                    pygame.draw.rect(
                        surface, (60, 130, 180), rect.inflate(-6, -6)
                    )
                    pygame.draw.line(
                        surface, (140, 220, 255),
                        (cx - half_w + 3, linha_y), (cx + half_w - 3, linha_y), 1,
                    )

            else:
                # Obstaculo generico (fallback de verdade agora)
                pygame.draw.rect(surface, cor, rect)
                cor_borda = tuple(max(0, c - 30) for c in cor)
                pygame.draw.rect(surface, cor_borda, rect, 2)
    
    def _desenhar_paredes(self, surface: pygame.Surface, camera):
        """Desenha as paredes da arena"""
        esp = self.config.espessura_parede
        cor = self.config.cor_parede
        cor_borda = self.config.cor_borda
        
        if self.config.formato == "circular":
            # Borda circular - só desenha o ANEL da parede, não o interior
            cx, cy = camera.converter(self.centro_x * PPM, self.centro_y * PPM)
            raio_ext = camera.converter_tam((self.raio + esp) * PPM)
            raio_int = camera.converter_tam(self.raio * PPM)
            
            if raio_ext > 0:
                # Desenha apenas o anel da parede (borda externa)
                espessura_parede = max(2, raio_ext - raio_int)
                pygame.draw.circle(surface, cor, (cx, cy), raio_ext, int(espessura_parede))
                
                # Borda interna decorativa
                pygame.draw.circle(surface, cor_borda, (cx, cy), raio_int, max(2, camera.converter_tam(3)))
        
        elif self.config.formato == "octogono":
            # Desenha octógono
            corte = min(self.largura, self.altura) * 0.2
            pontos = [
                (self.min_x + corte, self.min_y),
                (self.max_x - corte, self.min_y),
                (self.max_x, self.min_y + corte),
                (self.max_x, self.max_y - corte),
                (self.max_x - corte, self.max_y),
                (self.min_x + corte, self.max_y),
                (self.min_x, self.max_y - corte),
                (self.min_x, self.min_y + corte),
            ]
            
            pontos_tela = [camera.converter(p[0] * PPM, p[1] * PPM) for p in pontos]
            
            # Desenha parede externa
            pontos_ext = []
            for p in pontos:
                dx = p[0] - self.centro_x
                dy = p[1] - self.centro_y
                dist = math.hypot(dx, dy)
                if dist > 0:
                    nx, ny = dx / dist, dy / dist
                else:
                    nx, ny = 0, 0
                pontos_ext.append(camera.converter((p[0] + nx * esp) * PPM, (p[1] + ny * esp) * PPM))
            
            # Passe 2 (arte): a parede octogonal era desenhada como
            # poligono cheio + REPINTURA do interior com cor_chao — o que
            # apagava obstaculos e grid ja desenhados (Templo ficava sem
            # altar e pilares). Agora e um ANEL de verdade: um trapezio
            # por aresta, sem tocar o interior.
            n = len(pontos_tela)
            for i in range(n):
                j = (i + 1) % n
                pygame.draw.polygon(
                    surface, cor,
                    (pontos_tela[i], pontos_tela[j], pontos_ext[j], pontos_ext[i]),
                )
            pygame.draw.polygon(surface, cor_borda, pontos_tela, max(3, camera.converter_tam(5)))
        
        else:
            # Paredes retangulares
            # Parede superior
            p1 = camera.converter((self.min_x - esp) * PPM, (self.min_y - esp) * PPM)
            p2 = camera.converter((self.max_x + esp) * PPM, self.min_y * PPM)
            rect = pygame.Rect(p1[0], p1[1], p2[0] - p1[0], p2[1] - p1[1])
            pygame.draw.rect(surface, cor, rect)
            
            # Parede inferior
            p1 = camera.converter((self.min_x - esp) * PPM, self.max_y * PPM)
            p2 = camera.converter((self.max_x + esp) * PPM, (self.max_y + esp) * PPM)
            rect = pygame.Rect(p1[0], p1[1], p2[0] - p1[0], p2[1] - p1[1])
            pygame.draw.rect(surface, cor, rect)
            
            # Parede esquerda
            p1 = camera.converter((self.min_x - esp) * PPM, self.min_y * PPM)
            p2 = camera.converter(self.min_x * PPM, self.max_y * PPM)
            rect = pygame.Rect(p1[0], p1[1], p2[0] - p1[0], p2[1] - p1[1])
            pygame.draw.rect(surface, cor, rect)
            
            # Parede direita
            p1 = camera.converter(self.max_x * PPM, self.min_y * PPM)
            p2 = camera.converter((self.max_x + esp) * PPM, self.max_y * PPM)
            rect = pygame.Rect(p1[0], p1[1], p2[0] - p1[0], p2[1] - p1[1])
            pygame.draw.rect(surface, cor, rect)
            
            # Bordas internas
            min_px = camera.converter(self.min_x * PPM, self.min_y * PPM)
            max_px = camera.converter(self.max_x * PPM, self.max_y * PPM)
            largura = max_px[0] - min_px[0]
            altura = max_px[1] - min_px[1]
            if largura > 0 and altura > 0:
                pygame.draw.rect(surface, cor_borda, 
                               pygame.Rect(min_px[0], min_px[1], largura, altura),
                               max(3, camera.converter_tam(5)))
    
    def _desenhar_efeitos_colisao(self, surface: pygame.Surface, camera):
        """Desenha efeitos visuais de colisão com paredes"""
        for i, (x, y, intensidade) in enumerate(self.colisoes_recentes):
            # Fade baseado na posição na lista (mais recente = mais visível)
            alpha = int(200 * (i + 1) / len(self.colisoes_recentes)) if self.colisoes_recentes else 0
            
            cx, cy = camera.converter(x * PPM, y * PPM)
            raio = int(min(30, intensidade * 5))
            
            if raio > 2:
                s = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*self.config.cor_borda, alpha), (raio, raio), raio)
                surface.blit(s, (cx - raio, cy - raio))


# Instância global da arena (pode ser substituída)
_arena_atual: Optional[Arena] = None

def get_arena() -> Arena:
    """Obtém a arena atual"""
    global _arena_atual
    if _arena_atual is None:
        _arena_atual = Arena()
    return _arena_atual

def set_arena(config_nome: str = "Arena") -> Arena:
    """Define a arena atual pelo nome"""
    global _arena_atual
    if config_nome in ARENAS:
        _arena_atual = Arena(ARENAS[config_nome])
    else:
        _arena_atual = Arena()
    return _arena_atual
