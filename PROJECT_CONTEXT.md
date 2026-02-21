# 🎮 NEURAL FIGHTS - Documentação Completa do Projeto

## 📋 VISÃO GERAL

**Neural Fights** é um simulador de combate 2D top-down onde duas IAs com personalidades procedurais lutam entre si. É um projeto em Python puro usando Pygame para renderização e Tkinter/CustomTkinter para UI.

**Versão Atual:** v12.0 TOURNAMENT EDITION  
**Python:** 3.10+  
**Dependências:** pygame, customtkinter

---

## 🏗️ ARQUITETURA DO PROJETO

```
neural/
├── run.py                    # Entry point principal (UI Tkinter)
├── run_tournament.py         # Entry point do modo torneio
├── requirements.txt          # pygame, customtkinter
│
├── ai/                       # Sistema de Inteligência Artificial
│   ├── brain.py              # Cérebro principal (4000+ linhas) - ARQUIVO CRÍTICO
│   ├── personalities.py      # 35+ arquétipos, 20+ estilos, 50+ traços
│   ├── choreographer.py      # Coreografia de combos
│   ├── emotions.py           # Sistema emocional dinâmico
│   ├── spatial.py            # Consciência espacial e pathfinding
│   ├── combat_tactics.py     # Táticas situacionais
│   └── skill_strategy.py     # Quando usar skills
│
├── core/                     # Núcleo do motor de jogo
│   ├── entities.py           # Classe Lutador (1600+ linhas) - ARQUIVO CRÍTICO
│   ├── combat.py             # Projéteis (Flecha, Faca, Orbe, etc)
│   ├── physics.py            # Colisões, movimento, knockback
│   ├── hitbox.py             # Perfis de hitbox por tipo de arma
│   ├── skills.py             # Database de 100+ skills com 12 elementos
│   ├── arena.py              # Arenas com limites e obstáculos
│   ├── magic_system.py       # Sistema de magia elementar
│   ├── weapon_analysis.py    # Análise de matchup de armas
│   └── game_feel.py          # Hit stop, screen shake
│
├── simulation/               # Motor de simulação visual
│   └── simulacao.py          # Renderização Pygame (3000+ linhas) - ARQUIVO CRÍTICO
│
├── models/                   # Estruturas de dados
│   ├── characters.py         # Classe Personagem (dataclass)
│   ├── weapons.py            # Classe Arma (dataclass)
│   └── constants.py          # Classes, Raridades, Encantamentos
│
├── data/                     # Persistência JSON
│   ├── database.py           # CRUD para armas/personagens
│   ├── armas.json            # Database de armas (3600+ linhas)
│   ├── personagens.json      # Database de personagens
│   └── match_config.json     # Config de lutas
│
├── effects/                  # Efeitos visuais e sonoros
│   ├── particles.py          # Partículas (sangue, faíscas, magia)
│   ├── camera.py             # Câmera dinâmica com shake/zoom
│   ├── impact.py             # Flash de impacto, shockwaves
│   ├── weapon_animations.py  # Animações de armas por tipo
│   ├── magic_vfx.py          # VFX de magias elementais
│   ├── visual.py             # Efeitos visuais diversos
│   ├── movement.py           # Trails de movimento
│   └── audio.py              # Sistema de áudio com categorias
│
├── ui/                       # Interface gráfica Tkinter
│   ├── main.py               # Janela principal, menu
│   ├── view_armas.py         # Editor visual de armas
│   ├── view_chars.py         # Editor de personagens
│   ├── view_luta.py          # Seleção de lutadores
│   ├── view_torneio.py       # Interface de torneio
│   ├── view_sons.py          # Configuração de áudio
│   └── theme.py              # Cores e estilos da UI
│
├── tournament/               # Sistema de torneio
│   └── tournament_mode.py    # Brackets e gestão
│
├── tools/                    # Ferramentas auxiliares
│   ├── gerador_database.py   # Gerador procedural de armas/chars
│   ├── diagnostico_hitbox.py # Debug de hitboxes
│   ├── analise_armas.py      # Balanceamento de armas
│   └── auditoria_skills.py   # Verificação de skills
│
└── utils/                    # Utilitários
    ├── config.py             # Constantes globais (PPM, cores, etc)
    └── helpers.py            # Funções auxiliares
```

---

## ⚙️ CONSTANTES FÍSICAS IMPORTANTES

```python
PPM = 50              # Pixels Por Metro - TODAS as posições são em METROS
GRAVIDADE_Z = 35.0    # Gravidade para pulos
ATRITO = 8.0          # Desaceleração
ALTURA_PADRAO = 1.70  # Altura base de personagem em metros
FPS = 60
LARGURA, ALTURA = 1200, 800  # Resolução da janela
```

**IMPORTANTE:** O jogo usa sistema métrico. Posições (pos[0], pos[1]) são em METROS. Para renderização, multiplique por PPM.

---

## ⚔️ SISTEMA DE ARMAS (8 Tipos)

Cada tipo de arma tem comportamento completamente diferente:

| Tipo | Mecânica | range_mult | Exemplos |
|------|----------|------------|----------|
| **Reta** | Golpe direto com lâmina | 2.0 | Espadas, Lanças, Machados |
| **Dupla** | Par de armas rápidas | 1.5 | Adagas, Sai, Garras |
| **Corrente** | Flexível com ZONA MORTA | 4.0 | Kusarigama, Chicote, Mangual |
| **Arremesso** | Múltiplos projéteis | 5.0 | Shuriken, Facas, Chakram |
| **Arco** | Projétil único preciso | 20.0 | Arcos, Bestas |
| **Orbital** | Orbes que orbitam | 1.5 | Escudos, Drones |
| **Mágica** | Espadas espectrais | 2.5 | Runas, Espadas Espectrais |
| **Transformável** | Alterna 2 formas | 2.5 | Espada-Lança |

### Cálculo de Alcance
```python
alcance_real = raio_fisico * range_mult
raio_fisico = personagem.tamanho / 4.0  # ~0.425m para tamanho 1.7m
```

### Perfis de Hitbox (core/hitbox.py)
```python
HITBOX_PROFILES = {
    "Reta": {
        "shape": "arc",
        "range_mult": 2.0,
        "base_arc": 90,           # Arco em graus
        "min_range_ratio": 0.3,   # Zona morta
        "hit_window_start": 0.2,
        "hit_window_end": 0.85,
    },
    "Arco": {
        "shape": "line",
        "range_mult": 20.0,       # Alcance MUITO longo
        "min_range_ratio": 0.1,
        "is_projectile": True,    # Usa projéteis
    },
    # ...
}
```

---

## 🎭 SISTEMA DE PERSONALIDADES (ai/personalities.py)

### Arquétipos (35+)
Define o comportamento base da IA:
- **Ofensivos:** BERSERKER, ASSASSINO, GLADIADOR, PREDADOR, CARRASCO
- **Defensivos:** SENTINELA, PALADINO, GUARDIAO, MURALHA, CAÇADOR
- **Ranged:** ARQUEIRO, MAGO, LANCEIRO, ATIRADOR
- **Híbridos:** SAMURAI, NINJA, ACROBATA, DUELISTA, CAPOEIRISTA

### Estilos de Luta (20+)
Define como a IA executa ataques:
- BERSERK, TANK, KITE, BURST, COUNTER, COMBO, HIT_RUN, AMBUSH, TURTLE, PRESSURE...

### Traços (50+)
Modificadores que se combinam:
- **Agressivos:** BERSERKER, SANGUINARIO, PREDADOR, FURIOSO, IMPACIENTE
- **Defensivos:** CAUTELOSO, PACIENTE, PARANOICO, EVASIVO, COWARDLY
- **Especiais:** PHOENIX (revive com baixa vida), VAMPIRO (lifesteal), KAMIKAZE

### Cada IA tem:
- 1 Arquétipo principal
- 1 Estilo de luta  
- 5-7 Traços combinados
- 1-3 Quirks únicos
- 1 Filosofia de combate
- Humor dinâmico (muda durante luta)

---

## 🧠 SISTEMA DE IA (ai/brain.py) - ARQUIVO MAIS CRÍTICO

### Estados Emocionais (0.0 a 1.0)
```python
medo: float        # Aumenta quando toma dano
raiva: float       # Aumenta com frustrações
confianca: float   # Aumenta com acertos
frustracao: float  # Aumenta com misses
adrenalina: float  # Aumenta em momentos críticos
```

### Ações da IA
```python
# Movimento
"APROXIMAR", "RECUAR", "FUGIR", "FLANQUEAR", "CIRCULAR"

# Ataque
"MATAR", "ESMAGAR", "ATAQUE_RAPIDO", "PRESSIONAR", "POKE"

# Defesa/Especial
"CONTRA_ATAQUE", "BLOQUEAR", "USAR_SKILL", "COMBATE"
```

### Fluxo de Decisão
1. `atualizar()` - Chamado a cada frame
2. `_analisar_situacao()` - Coleta dados do combate
3. `_decidir_acao()` - Escolhe ação baseado em personalidade
4. `_executar_acao()` - Move e ataca

### Valores Importantes
- `alcance_ideal` - Distância que a IA quer manter
- `alcance_efetivo` - Alcance real de ataque da arma
- `acao_atual` - Ação sendo executada agora

---

## 🎯 CLASSE LUTADOR (core/entities.py)

```python
class Lutador:
    # Posição e Movimento
    pos: list[float, float]  # [x, y] em METROS
    vel: list[float, float]  # Velocidade atual
    z: float                 # Altura (pulo)
    angulo_olhar: float      # Direção que olha (graus)
    
    # Combate
    vida: float
    vida_max: float
    mana: float
    mana_max: float
    atacando: bool
    timer_animacao: float
    cooldown_ataque: float
    
    # Física
    raio_fisico: float       # = tamanho / 4.0
    
    # Buffers de Projéteis
    buffer_projeteis: list   # Flechas, facas, etc
    buffer_orbes: list       # Orbes mágicos
    buffer_areas: list       # Áreas de efeito
    
    # IA
    brain: AIBrain           # Cérebro da IA
    dados: Personagem        # Dados do personagem
```

### Métodos Importantes
- `atualizar(dt, inimigo)` - Loop principal
- `mover(dx, dy, dt)` - Movimento com colisão
- `atacar(inimigo)` - Executa ataque
- `tomar_dano(dano, dx, dy, efeito)` - Recebe dano
- `_disparar_flecha(alvo)` - Para arcos
- `_disparar_arremesso(alvo)` - Para armas de arremesso

---

## 💫 SISTEMA DE SKILLS (core/skills.py)

### Tipos de Skills
- **PROJETIL** - Bola de Fogo, Estilhaço de Gelo
- **AREA** - Explosão Nova, Inferno
- **BEAM** - Chamas do Dragão, Raio Laser
- **BUFF** - Escudo de Brasas, Frenesi
- **SUMMON** - Fênix, Golem, Mortos-Vivos
- **DASH** - Avanço Brutal, Passo das Sombras
- **TRAP** - Armadilha Congelante
- **CHANNEL** - Canalizar energia

### Elementos (12)
FOGO, GELO, RAIO, TREVAS, LUZ, NATUREZA, ARCANO, CAOS, VOID, SANGUE, TEMPO, GRAVITACAO

### Estrutura de Skill
```python
"Bola de Fogo": {
    "tipo": "PROJETIL",
    "dano": 35.0,
    "velocidade": 11.0,
    "raio": 0.5,           # Em metros
    "vida": 2.0,           # Segundos
    "cor": (255, 100, 0),
    "custo": 25.0,         # Mana
    "cooldown": 5.0,       # Segundos
    "efeito": "EXPLOSAO",
    "elemento": "FOGO",
}
```

---

## 🎨 RENDERIZAÇÃO (simulation/simulacao.py)

### Classe Simulacao
```python
def __init__(self, p1, p2, ...):
    self.p1: Lutador
    self.p2: Lutador
    self.projeteis: list
    self.particulas: list
    self.cam: Camera
    self.audio: AudioManager
    
def atualizar(self, dt):
    # 1. Hit stop
    # 2. Coleta projéteis dos lutadores
    # 3. Atualiza projéteis e colisões
    # 4. Atualiza lutadores
    # 5. Efeitos visuais
    
def renderizar(self, tela):
    # 1. Background
    # 2. Arena
    # 3. Lutadores (desenhar_personagem)
    # 4. Armas (desenhar_arma)
    # 5. Projéteis
    # 6. Partículas
    # 7. UI (vida, mana, nomes)
```

### Desenho de Armas
Cada tipo tem visual único:
- **Reta**: Lâmina poligonal + guarda
- **Dupla**: Par de adagas triangulares
- **Corrente**: Corrente animada com física
- **Arco**: Arco curvo + flecha
- **Orbital**: Orbes brilhantes orbitando

---

## 🏆 SISTEMA DE TORNEIO

- Brackets de 8, 16, 32 ou 64 participantes
- Interface visual com CustomTkinter
- Simulação baseada em atributos ou visual
- Salvar/Carregar estado

---

## 👤 CLASSES DE PERSONAGENS (16)

| Classe | Estilo | Atributos Fortes |
|--------|--------|------------------|
| Guerreiro | Balanced | FOR, RES |
| Berserker | Agressivo | FOR, VEL |
| Paladino | Tank + Heal | RES, MANA |
| Assassino | Burst | VEL, AGI |
| Arqueiro | Ranged | DEX, VEL |
| Mago | Magic DPS | INT, MANA |
| Necromante | Summons | INT, MANA |
| Monge | Combo | AGI, VEL |
| Ladino | Evasivo | AGI, DEX |
| Cavaleiro | Tank | RES, FOR |
| Druida | Hybrid | INT, RES |
| Samurai | Counter | FOR, DEX |
| Ninja | Hit&Run | VEL, AGI |
| Bárbaro | Berserk | FOR, RES |
| Feiticeiro | Control | INT, MANA |
| Gladiador | Showman | FOR, AGI |

---

## 🔊 SISTEMA DE ÁUDIO (effects/audio.py)

### Categorias com Volume Independente
- **golpes** - Sons de ataque
- **impactos** - Sons de acerto
- **projeteis** - Sons de projéteis/magias
- **skills** - Sons de habilidades
- **movimento** - Passos, dash
- **ambiente** - Ambiente da arena
- **ui** - Interface

---

## 🐛 DEBUG

### Flags em core/hitbox.py
```python
DEBUG_HITBOX = False  # Prints verbosos
DEBUG_VISUAL = True   # Mostra hitboxes na tela
```

### Arquivos de Teste
- `test_visual_debug.py` - Debug visual de hitboxes
- `test_headless_battle.py` - Testes sem UI
- `test_vfx.py` - Testes de efeitos visuais
- `test_manual.py` - Controle manual de personagem

---

## 📝 CONVENÇÕES DE CÓDIGO

- **Idioma**: Código em inglês, comentários em português
- **Unidades**: Sempre METROS, não pixels (exceto rendering)
- **Posições**: `pos[0]` = X, `pos[1]` = Y (metros)
- **Ângulos**: Graus (não radianos), 0° = direita
- **Type hints**: Usar quando possível
- **Classes**: PascalCase
- **Funções/variáveis**: snake_case
- **Constantes**: MAIUSCULAS_COM_UNDERSCORE

---

## ⚠️ ARMADILHAS COMUNS

1. **Esquecer PPM**: Posições são em metros. Para renderizar: `pos_pixels = pos * PPM`

2. **Alcance de armas**: Não é fixo! É `raio_fisico * range_mult` do perfil

3. **Projéteis**: Spawn deve ser FORA do corpo do atirador: `pos + raio_fisico + margem`

4. **brain.py gigante**: Tem 4000+ linhas, procure funções específicas com grep

5. **Tipos de arma**: Cada tipo tem mecânica COMPLETAMENTE diferente

6. **alcance_ataque vs alcance_ideal**: 
   - `alcance_ataque`: Distância máxima para acertar
   - `alcance_ideal`: Distância que a IA QUER manter

---

## 🔧 COMANDOS ÚTEIS

```bash
# Executar jogo
python run.py

# Modo torneio
python run_tournament.py

# Gerar database nova
python -c "from tools.gerador_database import gerar_database_completa; gerar_database_completa()"

# Testes
python test_headless_battle.py
python test_visual_debug.py
```

---

## 🎯 ARQUIVOS POR OBJETIVO

| Objetivo | Arquivo |
|----------|---------|
| Corrigir comportamento da IA | `ai/brain.py` |
| Corrigir ataque/dano | `core/entities.py`, `core/hitbox.py` |
| Corrigir projéteis | `core/combat.py` |
| Adicionar nova arma | `tools/gerador_database.py`, `core/hitbox.py` |
| Nova personalidade | `ai/personalities.py` |
| Nova skill | `core/skills.py` |
| Corrigir visual | `simulation/simulacao.py` |
| Novo efeito | `effects/` |
| Problemas de física | `core/physics.py` |

---

*Última atualização: v12.0 TOURNAMENT EDITION*
