# 🎮 NEURAL FIGHTS - Contexto do Projeto para IA

## 📋 Visão Geral

**Neural Fights** é um simulador de combate 2D top-down onde duas IAs com personalidades procedurais lutam entre si. O projeto foca em:

- Combate fluido com física realista
- IAs com comportamento humano e personalidades únicas
- Sistema de armas diversificado (8 tipos diferentes)
- Sistema de skills e magias
- Modo torneio com brackets
- Efeitos visuais cinematográficos

---

## 🗂️ Estrutura do Projeto

Todo módulo distribuído pertence ao namespace `neural_fights`. `tests/` e os
wrappers da raiz existem apenas no checkout e não são empacotados.

```
neural-fights/
├── run.py                    # Entry point principal
├── run_tournament.py         # Entry point do modo torneio
├── requirements.txt          # Dependências Python
│
├── neural_fights/ai/                       # Sistema de Inteligência Artificial
│   ├── brain.py              # Cérebro principal da IA (4000+ linhas)
│   ├── personalities.py      # Traços, arquétipos, estilos de luta
│   ├── choreographer.py      # Coreografia de combate
│   ├── emotions.py           # Sistema emocional
│   ├── spatial.py            # Consciência espacial
│   ├── combat_tactics.py     # Táticas de combate
│   └── skill_strategy.py     # Estratégia de uso de skills
│
├── neural_fights/core/                     # Núcleo do jogo
│   ├── entities.py           # Classe Lutador (personagem)
│   ├── combat.py             # Sistema de combate, projéteis
│   ├── physics.py            # Física (colisões, movimento)
│   ├── hitbox.py             # Sistema de hitbox por tipo de arma
│   ├── skills.py             # Database de 200+ skills
│   ├── arena.py              # Sistema de arenas
│   ├── magic_system.py       # Sistema de magia elementar
│   └── game_feel.py          # Hit stop, screen shake
│
├── neural_fights/simulation/               # Simulador visual
│   └── simulacao.py          # Renderização Pygame (3000+ linhas)
│
├── neural_fights/models/                   # Modelos de dados
│   ├── characters.py         # Classe Personagem
│   ├── weapons.py            # Classe Arma
│   └── constants.py          # Constantes (classes, raridades)
│
├── neural_fights/data/                     # Catálogo e fixtures empacotados
│   ├── database.py           # Funções de carregar/salvar
│   ├── armas.json            # Database de armas
│   ├── personagens.json      # Database de personagens
│   └── fixtures/
│       └── default_match_config.json  # Configuração padrão imutável
│
├── neural_fights/effects/                  # Efeitos visuais e sonoros
│   ├── particles.py          # Sistema de partículas
│   ├── camera.py             # Câmera com zoom/shake
│   ├── impact.py             # Efeitos de impacto
│   ├── weapon_animations.py  # Animações de armas
│   ├── magic_vfx.py          # VFX de magias
│   └── audio.py              # Sistema de áudio
│
├── neural_fights/ui/                       # Interface gráfica (Tkinter)
│   ├── main.py               # Janela principal
│   ├── view_armas.py         # Editor de armas
│   ├── view_chars.py         # Editor de personagens
│   ├── view_luta.py          # Configuração de lutas
│   ├── view_torneio.py       # Interface do torneio
│   └── theme.py              # Cores e estilos
│
├── neural_fights/tournament/               # Sistema de torneio
│   └── tournament_mode.py    # Brackets e gestão de torneio
│
├── neural_fights/tools/                    # Ferramentas auxiliares
│   ├── gerador_database.py   # Gerador procedural de armas/chars
│   ├── diagnostico_hitbox.py # Debug de hitboxes
│   └── analise_armas.py      # Análise de balanceamento
│
└── neural_fights/utils/                    # Utilitários
    └── config.py             # Configurações globais
```

Os arquivos versionados em `neural_fights/data/` são defaults imutáveis. Dados editados e
configurações de luta são gravados fora do checkout, no diretório de runtime do
usuário (configurável por `NEURAL_FIGHTS_RUNTIME_DIR`).

---

## ⚔️ Sistema de Armas (8 Tipos)

| Tipo | Descrição | Alcance | Exemplos |
|------|-----------|---------|----------|
| **Reta** | Armas de lâmina direta | 2.0x | Espadas, Lanças, Machados |
| **Dupla** | Armas duplas de curto alcance | 1.5x | Adagas, Sai, Garras |
| **Corrente** | Armas flexíveis com zona morta | 4.0x | Kusarigama, Chicote, Mangual |
| **Arremesso** | Projéteis múltiplos | 5.0x | Shuriken, Facas, Chakram |
| **Arco** | Projéteis únicos de longo alcance | 8.0x | Arcos, Bestas |
| **Orbital** | Orbitam o personagem | 1.5x | Escudos, Drones, Orbes |
| **Mágica** | Espadas espectrais flutuantes | 2.5x | Runas, Espadas Espectrais |
| **Transformável** | Muda entre duas formas | 2.5x | Espada-Lança, Chicote-Espada |

### Atributos de Armas
```python
{
    "nome": str,           # Nome único
    "tipo": str,           # Um dos 8 tipos
    "dano": float,         # 5-30 base
    "velocidade": float,   # 0.5-2.0
    "peso": float,         # Afeta knockback
    "raridade": str,       # Comum → Mítico
    "elemento": str,       # Fogo, Gelo, etc (opcional)
    "skill": str,          # Skill especial da arma
    "r", "g", "b": int,    # Cor RGB
    # Atributos específicos por tipo...
}
```

---

## 🎭 Sistema de Personalidades

### Arquétipos (35+)
- **Ofensivos**: BERSERKER, ASSASSINO, GLADIADOR, PREDADOR
- **Defensivos**: SENTINELA, PALADINO, GUARDIAO, MURALHA
- **Ranged**: ARQUEIRO, MAGO, LANCEIRO
- **Híbridos**: SAMURAI, NINJA, ACROBATA, DUELISTA

### Estilos de Luta (20+)
- BERSERK, TANK, KITE, BURST, COUNTER, COMBO, HIT_RUN, AMBUSH...

### Traços (50+)
- **Agressivos**: BERSERKER, SANGUINARIO, PREDADOR, FURIOSO
- **Defensivos**: CAUTELOSO, PACIENTE, PARANOICO, EVASIVO
- **Especiais**: PHOENIX, VAMPIRO, SHOWMAN, KAMIKAZE

### Cada IA tem:
- 1 Arquétipo principal
- 1 Estilo de luta
- 5-7 Traços combinados
- 1-3 Quirks únicos
- 1 Filosofia de combate
- Humor dinâmico que muda durante a luta

---

## 🧠 Sistema de IA (brain.py)

### Estados Emocionais
```python
medo: float        # 0.0 - 1.0
raiva: float       # 0.0 - 1.0
confianca: float   # 0.0 - 1.0
frustracao: float  # 0.0 - 1.0
adrenalina: float  # 0.0 - 1.0
```

### Ações Disponíveis
- APROXIMAR, RECUAR, FUGIR
- MATAR, ESMAGAR, ATAQUE_RAPIDO
- FLANQUEAR, CIRCULAR
- COMBATE, PRESSIONAR, POKE
- CONTRA_ATAQUE, BLOQUEAR
- USAR_SKILL

### Sistemas Avançados
- **Leitura de Oponente**: Detecta padrões de ataque
- **Janelas de Oportunidade**: Ataca em momentos ideais
- **Momentum**: Pressão psicológica
- **Consciência Espacial**: Evita paredes, usa cobertura
- **Percepção de Armas**: Adapta-se ao matchup

---

## 🎯 Sistema de Hitbox

Cada tipo de arma tem perfil único:
```python
HITBOX_PROFILES = {
    "Reta": {
        "range_mult": 2.0,      # Alcance = raio_char * mult
        "base_arc": 90,         # Arco de ataque em graus
        "min_range_ratio": 0.3, # Zona morta
        "hit_window": (0.2, 0.85),  # Janela de hit
    },
    "Corrente": {
        "range_mult": 4.0,
        "base_arc": 180,
        "min_range_ratio": 0.25,  # Zona morta grande
        "has_dead_zone": True,
    },
    # ...
}
```

---

## 🏆 Sistema de Torneio

- Brackets de 8, 16, 32 ou 64 participantes
- Simulação visual com Pygame
- Registro manual de vencedor
- Histórico de resultados
- Randomização de matchups

---

## 📊 Classes de Personagens (16)

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

## 🎨 Renderização (simulacao.py)

### Método `desenhar_arma()`
Renderiza armas com visual único por tipo:
- **Reta**: Lâmina poligonal com guarda
- **Dupla**: Par de adagas triangulares
- **Corrente**: Corrente animada com física de onda
- **Arremesso**: Shuriken rotativo
- **Arco**: Arco curvo + flecha com penas
- **Orbital**: Orbes brilhantes orbitando
- **Mágica**: Espadas espectrais flutuantes
- **Transformável**: Indicador de forma

### Efeitos por Raridade
- Comum: Sem efeito
- Incomum: Brilho verde sutil
- Raro: Glow azul
- Épico: Aura roxa pulsante
- Lendário: Partículas douradas
- Mítico: Trail rosa + partículas

---

## 🔧 Comandos Úteis

```bash
# Executar jogo
python run.py

# Executar torneio
python run_tournament.py

# Gerar nova database
python -m neural_fights.cli.roster --modo completo --seed 42

# Testar batalha headless
python -m neural_fights.cli.headless

# Testar VFX
python test_vfx.py
```

---

## 📝 Convenções de Código

- **Idioma**: Código em inglês, comentários em português
- **Tipos**: Use type hints quando possível
- **Docstrings**: Documentar funções públicas
- **Constantes**: MAIÚSCULAS_COM_UNDERSCORE
- **Classes**: PascalCase
- **Funções/variáveis**: snake_case

---

## 🐛 Debug

### Hitbox Visual
```python
# Em neural_fights/core/hitbox.py
DEBUG_HITBOX = False  # Prints verbosos
DEBUG_VISUAL = True   # Mostra hitboxes na tela
```

### Configurações em neural_fights/utils/config.py
```python
PPM = 50              # Pixels por metro
LARGURA = 1280        # Largura da janela
ALTURA = 720          # Altura da janela
FPS = 60              # Frames por segundo
```

---

## 🎯 Próximos Passos Sugeridos

1. **Balanceamento**: Ajustar dano/vida para lutas ~30-60s
2. **Novas Armas**: Adicionar variantes únicas
3. **Novos VFX**: Efeitos elementais mais elaborados
4. **Multiplayer**: Modo PvP local
5. **Replay**: Sistema de gravação de lutas
6. **Achievements**: Sistema de conquistas

---

## 📚 Arquivos Importantes para Modificar

| Objetivo | Arquivo |
|----------|---------|
| Adicionar nova arma | `neural_fights/tools/gerador_database.py`, `neural_fights/data/armas.json` |
| Novo tipo de arma | `neural_fights/core/hitbox.py`, `neural_fights/simulation/simulacao.py` |
| Nova personalidade | `neural_fights/ai/personalities.py` |
| Novo comportamento IA | `neural_fights/ai/brain.py` |
| Nova skill | `neural_fights/core/skills.py` |
| Novo efeito visual | `neural_fights/effects/` |
| Nova classe | `neural_fights/models/constants.py`, `neural_fights/models/characters.py` |

---

*Última atualização: v12.0 TOURNAMENT EDITION*
