# 🎮 NEURAL FIGHTS - Documentação Completa do Projeto

## 📋 VISÃO GERAL

**Neural Fights** é um simulador de combate 2D top-down onde duas IAs com personalidades procedurais lutam entre si. É um projeto em Python puro usando Pygame para renderização e Tkinter/CustomTkinter para UI.

**Versão Atual:** v12.0 TOURNAMENT EDITION  
**Python:** 3.10+  
**Dependências:** pygame-ce, customtkinter

---

## 🏗️ ARQUITETURA DO PROJETO

O código instalável usa exclusivamente o namespace `neural_fights`; os scripts
na raiz são wrappers de desenvolvimento e ficam fora da wheel.

```
neural/
├── run.py                    # Entry point principal (UI Tkinter)
├── run_tournament.py         # Entry point do modo torneio
├── requirements.txt          # pygame-ce, customtkinter
│
├── neural_fights/ai/                       # Sistema de Inteligência Artificial
│   ├── brain.py              # Cérebro principal (4000+ linhas) - ARQUIVO CRÍTICO
│   ├── personalities.py      # 35+ arquétipos, 20+ estilos, 50+ traços
│   ├── choreographer.py      # Coreografia de combos
│   ├── emotions.py           # Sistema emocional dinâmico
│   ├── spatial.py            # Consciência espacial e pathfinding
│   ├── combat_tactics.py     # Táticas situacionais
│   └── skill_strategy.py     # Quando usar skills
│
├── neural_fights/core/                     # Núcleo do motor de jogo
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
├── neural_fights/simulation/               # Motor de simulação visual
│   └── simulacao.py          # Renderização Pygame (3000+ linhas) - ARQUIVO CRÍTICO
│
├── neural_fights/models/                   # Estruturas de dados
│   ├── characters.py         # Classe Personagem (dataclass)
│   ├── weapons.py            # Classe Arma (dataclass)
│   └── constants.py          # Classes, Raridades, Encantamentos
│
├── neural_fights/data/                     # Catálogo e fixtures empacotados
│   ├── database.py           # CRUD para armas/personagens
│   ├── armas.json            # Database de armas (3600+ linhas)
│   ├── personagens.json      # Database de personagens
│   └── fixtures/
│       └── default_match_config.json  # Config padrão imutável
│
├── neural_fights/effects/                  # Efeitos visuais e sonoros
│   ├── particles.py          # Partículas (sangue, faíscas, magia)
│   ├── camera.py             # Câmera dinâmica com shake/zoom
│   ├── impact.py             # Flash de impacto, shockwaves
│   ├── weapon_animations.py  # Animações de armas por tipo
│   ├── magic_vfx.py          # VFX de magias elementais
│   ├── visual.py             # Efeitos visuais diversos
│   ├── movement.py           # Trails de movimento
│   └── audio.py              # Sistema de áudio com categorias
│
├── neural_fights/ui/                       # Interface gráfica Tkinter
│   ├── main.py               # Janela principal, menu
│   ├── view_armas.py         # Editor visual de armas
│   ├── view_chars.py         # Editor de personagens
│   ├── view_luta.py          # Seleção de lutadores
│   ├── view_torneio.py       # Interface de torneio
│   ├── view_sons.py          # Configuração de áudio
│   └── theme.py              # Cores e estilos da UI
│
├── neural_fights/tournament/               # Sistema de torneio
│   └── tournament_mode.py    # Brackets e gestão
│
├── neural_fights/tools/                    # Ferramentas auxiliares
│   ├── gerador_database.py   # Gerador procedural de armas/chars
│   ├── diagnostico_hitbox.py # Debug de hitboxes
│   ├── analise_armas.py      # Balanceamento de armas
│   └── auditoria_skills.py   # Verificação de skills
│
└── neural_fights/utils/                    # Utilitários
    └── config.py             # Constantes globais (PPM, cores, etc)
```

Os JSONs versionados em `neural_fights/data/` são somente leitura durante a execução. Armas,
personagens, configurações de luta e demais estados alteráveis ficam no
diretório de dados do usuário, ou no caminho definido por
`NEURAL_FIGHTS_RUNTIME_DIR`.

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

### Perfis de Hitbox (neural_fights/core/hitbox.py)
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

## 🎭 SISTEMA DE PERSONALIDADES (neural_fights/ai/personalities.py)

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

## 🧠 SISTEMA DE IA (neural_fights/ai/brain.py) - ARQUIVO MAIS CRÍTICO

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

### Fluxo de Decisão (Onda 8)
O ponto de entrada é `AIBrain.processar(dt, distancia, inimigo)`, chamado
todo frame por `Lutador.update`:

1. **Sensores** — cooldowns, emoções, humor, observação HONESTA do
   oponente (`_observar` → `ObservacaoInimigo`: posição, velocidade e a
   fase da animação de ataque; a telepatia `inimigo.brain.acao_atual` foi
   removida na 8A), leitura/hábitos, momentum, espacial
   (`SpatialAwarenessSystem`, religado na 8C), percepção de armas, ritmo
   e o **PlanoDeLuta** (8E: intenção tática de 2-6s).
2. **Gates com early-return**, em ordem de prioridade:
   instintos (P1) → **desvio inteligente** (8C: projéteis/áreas/golpes
   via `percepcao` do mundo; executa guarda/dash/pulo/impulso) →
   **punição de whiff** (8D: recovery lido do corpo) → hesitação →
   coreógrafo (com veto por personalidade) → baiting → reação →
   ataque/skills (o roll com golpe em cooldown NÃO consome mais o frame
   — fix 8E) → decisão de movimento em timer (~250-600ms).
3. **`_decidir_movimento`** — proposta por arma/zona → pilha: plano de
   luta (estágio 0) → agressividade → eixos → traços → humor → filosofia
   → momentum → leitura → anti-repetição (consistente com o plano) →
   espacial → armas → veto de sobrevivência. Escrita única via
   `_definir_acao` com min-hold (alvo V2 ≥ 500ms).

### Hitstun e combos (Onda 8H)
- Golpe DISCRETO que conecta (melee, projétil, orbe — nunca área/beam/
  trap/DoT) aplica **hitstun**: `stun_timer` de 0.14-0.40s escalando com
  o dano. Golpe **bloqueado não atordoa** (a guarda é o quebra-combo).
- **Combo sofrido** é estado físico do alvo: `combo_contra` (hits do
  mesmo autor), janela = hitstun do hit + 0.45s de emenda. O atacante lê
  para o followup; o defensor para escapar; o renderer mostra o "xN".
- **Anti-stunlock em três freios**: hitstun decresce 15% por hit;
  pushback cresce com o combo (a string se encerra espacialmente); do 8º
  hit o alvo "acorda" (stun zero). Tanques (Cavaleiro/Colosso) sentem
  30% menos stun; ágeis (Assassino/Ladino/Ninja) 10% mais.
- **Combo flow**: swing iniciado com o alvo em hitstun tem cadência
  ×0.8 (MESTRE_COMBO ×0.85 adicional) — é o que forma strings de 2-4.
- **Burst de escape**: no 3º hit do combo, o defensor pode pagar 40 de
  estamina por pushback + 0.25s de invulnerabilidade. A chance vem da
  personalidade (`chance_burst_combo`: cauteloso/medroso escapa, teimoso
  e berserker tankam). Sorteio no stream do próprio defensor.
- IA: `_tentar_followup` lê o estado real (stun/combo ativo) e a arma
  pesada fecha a string com ESMAGAR; alvo em hitstun eleva a chance de
  ataque a 0.95; o instinto `sendo_comboado` lê `combo_contra`.

### Percepção e defesa (Ondas 8A-8B)
- `Lutador.percepcao` (`ai/percepcao.py`) — janela somente-leitura sobre
  as listas do Simulador; os buffers antigos são drenados antes do tick.
- `habilidade_leitura` (0-1, derivada dos eixos/quirks) — latência de
  observação, chance de má-leitura por golpe, precisão de antecipação.
- Estamina é o recurso defensivo: dash universal
  (`Lutador.iniciar_dash`), bloqueio direcional (±60°, ×0.35; Cavaleiro
  ×0.20) e parry (guarda erguida há <0.18s nega golpe físico e cambaleia
  o atacante). Ver constantes em `utils/config.py`.

### Valores Importantes
- `alcance_ideal` - Distância que a IA quer manter
- `alcance_efetivo` - Alcance real de ataque da arma
- `acao_atual` - Ação sendo executada agora (escritor único, min-hold)
- `plano` - Intenção tática atual ({tipo, expira_em, compromisso})
- `tell_atual` - Sinal legível para o renderer (instinto/desvio/punição/
  parry/troca de plano)

---

## 🎯 CLASSE LUTADOR (neural_fights/core/entities.py)

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

## 💫 SISTEMA DE SKILLS (neural_fights/core/skills.py)

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

### A luta como vídeo (Onda 9)
- **Câmera `DIRETOR`** (`effects/camera.py`, `match_config["camera_modo"]`):
  câmera de transmissão para vídeo. Zona morta com histerese, pan lento
  (2,4/s), zoom-in só após 1 s estável e +12 %, zoom-out rápido, push-in no
  KO, sem shake/punch. Teto de zoom em **metros** (`diretor_largura_min_m`:
  o lado menor nunca mostra menos de 7 m) e clamp macio à arena
  (`diretor_fora_arena`). Só lê posições — nunca toca `time_scale`; medido:
  não altera o resultado da luta.
- **`match_config["resolucao"]`** (`[largura, altura]`) sobrepõe o par do
  modo: gravação nativa em 1080×1920. A proporção decide `portrait_mode`.
- **Gravador** (`recording/fight_recorder.py`): além do mp4 e dos
  `eventos_dano`, devolve `serie_hp` (0,25 s), `eventos_narrativos`
  (tells `instinto/desvio/punicao/parry/clinch`, `combo` com `n`,
  `primeiro_sangue`, `virada`, `ko`) e `metricas_video` (visibilidade,
  tamanho do lutador, pan p90 em larguras/s, trocas de zoom/min). Tudo em
  tempo de VÍDEO. `saida=None` mede sem codificar.
- **Harness** `python -m neural_fights.tools.qualidade_luta --video`:
  alvos `V7_*` em `alvos_qualidade.json` (enforce_onda 9).
- Consumidor: `random_builds` (fight/estreia/torneio) — ver README de lá.

### O cara-a-cara (Onda 10A)
- **Diagnóstico**: o clinch da 8G só via contato físico (`dist < 1,35×
  raios`); o standoff real acontece na FAIXA de confronto (2,5–4,5 m)
  sem hit conectado — e o coreógrafo fabricava o momento (`FACE_OFF` =
  2–4 s de `BLOQUEAR` nos dois; `STANDOFF`/tédio alongavam o timer de
  decisão).
- **Detector de standoff** (`Simulador._detectar_standoff`): mede o tempo
  sem HIT REAL (`contadores_luta["hits_sofridos"]`, sem DoT) em duas
  bandas — PERTO (faixa de confronto) e LONGE (≤ 9 m). Perto: 1,5 s →
  `AIBrain.forcar_iniciativa` (P1: dash-in a 1,8–5 m ou golpe; tell
  `iniciativa`); +1,0 s → **agarrão**. Longe: 3 s → iniciativa; +1 s → os
  dois aproximam. Se o relógio expira já colado (< 2 m), agarra de
  primeira. Estado público `sim.standoff_estado` (a sonda lê).
- **Agarrão** (`core/agarrao.py`, funções puras; ciclo em
  `Simulador._iniciar_agarrao/_atualizar_agarrao`): lock de
  `AGARRAO_LOCK_S` (0,25 s, com lunge até o contato), desfecho sorteado
  JÁ no `rng_runtime` do iniciador: ARREMESSO (voa ~3,75 m, stun 0,45,
  4–8 % de vida, arma `lancado_por`), JOELHADA (corpo a corpo, conta
  combo), EMPURRAO, REVERSAO (troca papéis uma vez) e ESCAPE (dash
  `ignorar_custo=True` + 0,3 s de janela no iniciador). Dano real
  interrompe o lock. Clinch de contato também agarra (o resolvedor da 8G
  fica de reserva no cooldown). `brain._pedir_agarrao` é o gancho para os
  planos da 10C.
- **Wall-splat** (`Simulador._processar_wall_splat`): corpo LANÇADO
  (arremesso ou knockback ≥ `LANCADO_KNOCKBACK_MIN`) que bate na parede
  com intensidade ≥ 8 → stun 0,3–0,5 s, dano ≤ 8 %, tell `wall_splat`,
  `cam.aplicar_momento` (push-in do DIRETOR, sem punch).
- **Coreógrafo**: `FACE_OFF` uma vez por luta, 0,8 s, termina em
  `forcar_iniciativa` do mais agressivo; `STANDOFF` 1,0–1,5 s;
  `BREATHER` só com estamina < 30 nos dois; `CIRCULAR_LENTO`/`RECUPERAR`
  não esticam `timer_decisao`. Humor ENTEDIADO acelera a decisão (base
  0,3) e sobe agressividade.
- **Corpo vivo** (`executar_movimento`): verbo ofensivo em cima do alvo
  ORBITA (lateral ×0,6) em vez de congelar — exceto com o alvo em hitstun
  (combo segue reto); `BLOQUEAR` anda (strafe perto, avanço lento a > 3 m);
  `CIRCULAR` no meio-alcance não reaproxima sozinho.
- **Portão de ataque**: `chance_base` 0,75; 0,6 s de verbo passivo em
  alcance sem ameaça vira golpe P1 (tell `iniciativa`); hesitação em
  alcance é metade do raro; `BAITAR_E_PUNIR` sem isca contra oponente
  passivo vira `PRESSIONAR` (`_forcar_plano`).
- **Harness**: `pct_tempo_standoff`, `agarroes` (por desfecho),
  `wall_splats`, `iniciativas`; R1 exclui frames de agarrão. Alvos
  `R2_standoff` (≤ 0,12), `R2_standoff_p90`, `R3_agarroes` (≥ 0,4/luta),
  `R4_wall_splats`, metas em `_meta` (enforce 11). Tells `agarrao`
  (com `modo`), `wall_splat`, `iniciativa` viram `eventos_narrativos`.
- Testes: `test_agarrao_regressions`, `test_standoff_regressions`,
  `test_wall_splat_regressions`, `test_choreographer_retune_regressions`,
  `test_portao_ataque_regressions`.

### Velocidade e mobilidade por classe (Onda 10B)
- **Fórmula** (`models/characters.py`): `velocidade = velocidade_base_ms
  (classe) × clamp(1,10 − 0,05·peso_arma, 0,70, 1,05) × clamp(0,90 +
  0,02·força, 0,90, 1,10)`; `ESCALA_VELOCIDADE_MOVIMENTO = 1,0` (a base
  já é m/s). `mod_forca` saiu da velocidade. Garantia testada: o pior
  Ninja (6,93) anda mais que o melhor Cavaleiro (5,78).
- **`CLASSES_DATA`** ganhou `velocidade_base_ms` (Ninja 11 · Assassino 10
  · Monge/Ladino 9,5 · Duelista 8 · Gladiador/Berserker 7,5 · Guerreiro 7
  · casters 5,5–6,5 · Cavaleiro 5), `mod_cadencia` (Ninja 0,70 …
  Cavaleiro 1,20; substitui o `if "Ninja" in nome`) e `vel_giro`.
  `mod_velocidade` é só rótulo da UI. Dupla `cadencia_base_s` 1,2 → 0,85.
- **Mobilidade no motor** (`Lutador._mobilidade_perfil`, eixo 0–1 da
  personalidade): +8 % de velocidade, dash com cooldown ×(1 − 0,47·mob),
  custo ×(1 − 0,35·mob), força ×(1 + 0,31·mob), giro ×(1 + 0,3·mob).
  `ritmo_combate` (±20 % permanente) virou ±8 %.
- **Dash tático** (`AIBrain._considerar_dash_tatico`, antes da decisão de
  movimento; cooldown `cd_dash_tatico` 1,0–2,5 s): GAP_CLOSE (plano
  ofensivo, 2,5–5,5 m, oponente observado não atacando) → PRESSIONAR;
  HIT_AND_RUN (acertou há < 0,45 s, estilo HIT_RUN ou mob > 0,5) → dash
  para trás + RECUAR com dash-cancel do swing; FLANK (guarda física
  `tempo_bloqueando` > 0,2 ou LEVAR_PARA_PAREDE) → FLANQUEAR. Tell
  `dash_tatico` com `modo`.
- **Harness**: `velocidade_media_ms_por_classe` (só movimento PRÓPRIO —
  sem stun/lançado/dash/agarrão), `razao_velocidade_ninja_cavaleiro`,
  `distancia_percorrida_por_s_media`, `pct_frames_parado_em_range_media`,
  `dashes_taticos_por_luta_media`, `dashes_ofensivos_share`. Alvos `M1_*`
  a `M4_*` (enforce 10).
- Testes: `test_velocidade_classes_regressions`,
  `test_mobilidade_motor_regressions`, `test_dash_tatico_regressions`.

### Hit-stop só para pancada grande (ajuste de fluxo pós-O10)
- O congelamento por hit (`core/game_feel.py::HitStopManager.registrar_hit`,
  2–18 frames × multiplicador de classe até 1,8, em TODO golpe) quebrava
  o fluxo no ritmo novo (~44 congelamentos ≈ 4,3 s de tela parada por
  luta). Agora só congela quando `dano >= HITSTOP_DANO_MIN_PCT` (0,06 ≈
  1,5 momentos/luta; varredura no próprio knob) da vida_max do ALVO — em
  `utils/config.py`. Golpes comuns mantêm shake/partículas/knockback;
  magia carregada (alvo None) segue épica; o slow-motion de KO
  (`ativar_slow_motion`, só no fim do round) não muda. Display-only:
  headless não congela (doutrina da Onda 9). Teste:
  `test_hitstop_fluxo_regressions`.

### Planos visíveis e adaptativos (Onda 10C)
- **`ai/plano_de_luta.py`**: `PlanoDeLuta` (objeto compatível com o dict
  da 8E: `plano["tipo"]`, `.get`, `in`) com `rotulo`, `verbos`, `objetivo`,
  `progresso` 0–1, `adaptativo`, `marcadores` (snapshot de contadores no
  início); `DEFINICOES` (11 tipos) com `sucesso`/`falha`/`progresso`
  puros sobre um `ContextoPlano` (deltas desde o início: hits dados,
  punições, agarrões, wall-splats, skills, hp, distância, parede);
  `min_duracao` 1,2 s segura fim precoce.
- **Adaptativos** (nascem do que o lutador OBSERVA, sem telepatia):
  `QUEBRAR_GUARDA` (guarda física `tempo_bloqueando` em ≥ 2 dos meus
  últimos 4 swings → pesado/agarrão), `CORTAR_FUGA` (oponente visto
  recuando ≥ 0,6 s a > 3 m), `TROCAR_GOLPES` (agressivo, < 4 m),
  `ACABAR` (hp do oponente < 25 %: score 1,2 domina o ruído),
  `ESMAGAR_NA_PAREDE` (oponente contra a parede; +0,3 vindo de
  `LEVAR_PARA_PAREDE`). Gatilho dispara com score ≥ 0,85 (acima do ruído
  0,25×(1+caos)).
- **Ciclo** (`_atualizar_plano`): spike de dano → objetivo
  (sucesso/falha, ANTES do relógio) → expiração → isca sem oponente
  (10A). Contadores `planos_sucesso|falha|expirado|dano|adaptativos`.
- **O plano manda**: `_aplicar_plano_de_luta` mantém a proposta se ela já
  está em `verbos`, senão troca por um verbo do plano com
  `max(0,6, compromisso)`; `_aplicar_plano_ao_portao` entra no portão de
  ataque (ACABAR ≥ 0,9; TROCAÇÃO +0,2; PRESSÃO +0,1; ISCA −0,25 fora de
  janela; RECUPERAR −0,15; QUEBRAR_GUARDA/ESMAGAR → `_preferir_esmagar` e
  `_pedir_agarrao` a < 1,9 m — o Simulador agarra). `_VARIACOES_POR_PLANO`
  deriva das definições.
- **Visível**: rótulo na cor do lado sob o corpo + barra de progresso +
  flash de 0,6 s na troca (`simulacao.py`, knob `match_config["rotulo_plano"]`);
  tell `plano` (seta/arco) e `dash_tatico` desenhados; rosto reage
  (`character_flair`). Gravador: `plano` ∈ `TELLS_NARRATIVOS` (evento com
  `rotulo`/`plano`/`adaptativo`, throttle `PLANO_GAP_MIN_S` = 4 s por
  lutador) e **`serie_plano`** `(t, rotulo_p1, prog_p1, rotulo_p2, prog_p2)`
  na cadência de `serie_hp`. `random_builds`: `remapear_gravacao` e
  `gravar_confronto` carregam `serie_plano`; `planejar_callouts` aceita
  `plano` (throttle por lutador, cede a evento maior a < 1,5 s,
  `{ROTULO}` em `captions.callout`); o HUD em PIL desenha o rótulo e a
  barrinha sob a barra de vida (`fight_hud.plano`).
- **Harness**: `pct_frames_acao_coerente_media`,
  `planos_adaptativos_por_luta_media`, `planos_concluidos_share`,
  `planos_sucesso_share`; alvos `A7_coerencia_plano` (≥ 0,5),
  `A8_planos_adaptativos` (≥ 1), `A9_planos_concluidos` (≥ 0,3).
- Testes: `test_plano_adaptativo_regressions`,
  `test_plano_de_luta_regressions` (compat), `test_camera_diretor_regressions`
  (plano vira evento com throttle), `random_builds/tests/test_luta_video_regressions`
  (callouts de plano).

### Habilidades com consequência (Onda 10D)
- **Despachante único** (`Lutador._executar_skill(nome, data, *, origem,
  alvo, proposito, ...)`): `usar_skill_arma`/`usar_skill_classe` só pagam
  e gatilham; recoil e passivas de arma só em `origem="arma"`, bônus do
  Piromante e eco do Feiticeiro só em `"classe"`. `buffer_summons`/
  `buffer_traps` nascem no `__init__`.
- **Geometria de cast**: `_ponto_alvo_area` (AREA cai na posição
  PREVISTA do alvo, `pos + vel×(delay+0,15)`, até `alcance_cast`
  (6 m; Julgamento Celestial 8), recuando até ponto válido da arena —
  `centrado_no_caster: True` mantém no pé: Explosão Nova, Fúria
  Giratória, Repulsão, Medo Profundo, Provocar, Explosão Necrótica,
  Colheita de Almas, Sacrifício, Terremoto); `_direcao_dash` por
  PROPÓSITO (`AIBrain._proposito_do_cast`: ESCAPE em desvantagem/hp<35 %
  → direção com mais arena; ENGAGE → rumo ao alvo parando em
  `alcance_ideal×0,8`; REPOSICIONAR → lateral); `_destino_dash_valido`
  nunca atravessa parede/obstáculo. O Simulador injeta
  `lutador.arena_ref`.
- **Efeitos que eram `pass`**: EMPURRAO empurra (`forca_empurrao` da
  fonte ou `FORCA_EMPURRAO_PADRAO` 14 — só fontes discretas; áreas/traps
  empurram por conta própria) e LANÇA (wall-splat); EXPLOSAO sem
  `raio_explosao` ganha `raio×2` (splash em volta, sem repetir o alvo
  direto); PUXADO/VORTEX puxam para a origem por 0,3 s
  (`Lutador.puxao`); `AreaEffect.forca_puxar` 5 → 30; Repulsão
  `forca_empurrao` 2 → 20.
- **Obstáculos destrutíveis** (`core/arena.py`): `Arena` copia os
  `Obstaculo` por instância (o catálogo `ARENAS` nunca muta);
  `obstaculos_no_raio`, `danificar_obstaculo` (hp → 0: `solido=False`,
  `tipo += "_quebrado"`, entulho desenhado), `ultimo_obstaculo_colidido`
  (corpo lançado que bate numa caixa quebra-a e o splat é mais leve),
  `eventos_obstaculo` drenados pelo Simulador (`_drenar_eventos_obstaculo`:
  contador, tell `obstaculo`, destroços). Áreas ativas danificam uma vez.
  Só a Cyberpunk tem destrutíveis.
- **Kits** (`CLASSES_DATA[...]["skills_afinidade"]`, ordem `KIT_PAPEIS` =
  CONTROLE/ZONA/MOBILIDADE/PICO): 16×4 alcançando TRAP (Muralha de Gelo),
  CHANNEL (Fotossíntese), TRANSFORM (Forma Relâmpago), portal (Portal
  Arcano), cadeia (Corrente em Cadeia), Fênix, Treant e os 12 status
  órfãos. Auditoria: `alcance_cast`/`centrado_no_caster` no inventário e
  no manifesto (`tools/skill_runtime_evidence.py`).
- **Harness**: `share_casts_com_consequencia`, `status_cc_por_luta_media`,
  `obstaculos_destruidos_por_luta_media`; alvos `K1` (≥ 0,45), `K2`
  (≥ 1,5), `K3` (reportado). Re-pinos honestos no fecho da O10 (completo
  546 lutas): `A5_rotatividade` max 32 (planos terminam por objetivo),
  `R1_tempo_colado` 0,09 / p90 0,20 (PUXADO/VORTEX encostam por desenho;
  a sonda exclui frames de puxão/lançamento), `B2_tipo_max` 0,70
  (Orbital), `S5` 0,008, `C1` min 1 (pushes/CC encerram strings),
  `B3` 5,0, `D3_meta` 0,14, `D4` 0,22, `S3_share_skills_meta` 0,23 /
  `S3_share_basico_meta` 0,69 (kits trocaram dano por controle; casts
  por luta 20 → 13 porque as skills de assinatura custam 45–65 de mana —
  a próxima rodada de knobs é custo/cooldown dos kits).
- Testes: `test_area_alvo_regressions`, `test_empurrao_puxao_regressions`,
  `test_obstaculo_destrutivel_regressions`, `test_kits_de_classe_regressions`,
  `test_skill_dispatch_unificado_regressions`.

## 🧬 CONTRATO DE SKILLS — o "MCP interno" (Onda 11A)

- **`core/skill_contract.py`**: cada skill deriva um `SkillContract`
  self-describing de `SKILL_DB` + `STATUS_RUNTIME` + `CLASSES_DATA` (funções
  puras, import-safe, zero literal novo por skill). Declara: geometria REAL
  (`alcance_lancamento` = alcance_cast p/ AREA, raio, ancoragem no alvo,
  pilares), tempos (delay/telegraph/duracao), efeito com `categoria_efeito`
  canônica (nunca listas literais), custos efetivos (`custo_efetivo` espelha
  Mago ×0,8 + buffs; paridade garantida por teste), gates
  (`condicao`/`condicao_limiar`), grafo de combo (`combo_apos` + derivação
  status→condição) e `consequencia_esperada` — o oráculo do harness 1-a-1.
- **A estratégia delega ao contrato** (`ai/skill_strategy.py`):
  `_determinar_propositos` usa categoria (11 skills de CC voltaram à rotação:
  SILENCIADO/ENRAIZADO/KNOCK_UP/TEMPO_PARADO...), FINISHER vale para QUALQUER
  tipo com limiar declarado, `_pode_usar_skill` compara custo EFETIVO,
  `_descobrir_combos` lê o grafo com efeitos normalizados. Estado morto
  removido (scores, setup/pode_combo_apos).
- **`percepcao_kit`** (`ai/brain.py`): o brain lê o kit do INIMIGO pelos
  contratos (informação pública, como a arma) — `alcance_perigo_skill`,
  `tem_telegraph`, `tem_gap_closer`, `tem_execute`; consumo em
  `distancia_segura` (kite + cautela contra execute).
- **Inspetor**: `python -m neural_fights.tools.skill_inspector
  listar|explicar|exportar|cobertura|checar|demos` — a interface humana do
  contrato (import-safe; `checar` roda o motor).
- Campos novos pelo rito da auditoria: `combo_apos`, `condicao_limiar`,
  `forca_puxar`, `tick_interval` (MECHANICAL_FIELDS 117 → 121).

## 🔬 QUALIDADE 1-A-1 (Onda 11B)

- **Pilares consertados** (Julgamento Celestial): 1º pilar GARANTIDO na
  âncora do cast (era `uniform(1.0, raio)` — buraco morto no centro, ~37% de
  acertar alvo parado); cada pilar é um golpe distinto (`fonte_impacto`
  próprio + `ignorar_invencibilidade`; era 1 hit máx por cast) com dano/2;
  telegraph desenha os 5 círculos REAIS (`get_avisos_visuais`); filho herda
  snapshot do cast (subefeito não re-captura buffs nem re-sorteia efeito);
  mãe inerte não destrói mais obstáculos.
- **Checagem 1-a-1**: `tools/skill_check.py` casta CADA skill num cenário
  determinístico do motor real e exige a `consequencia_esperada` do contrato.
  118/118 skills verdes. Regressão: `tests/test_skill_one_by_one.py`
  (representantes por padrão; catálogo inteiro com `NF_SKILL_GATE=1`).
- Triagem completa dos 28 suspeitos em
  `neural_fights/data/triagem_skills_onda11.json` (fixados: eventos de
  projétil que se engoliam, explosão que perdia a identidade da skill,
  lifesteal sem gating, cura_por_morte por nome literal, ramos mortos de
  Beam/Buff/Summon, dano_variavel fora da escala ×2 por ser MULTIPLICADOR).

## 🎲 POOLS DE KIT (Onda 11C)

- **`KIT_POOLS`** (`models/constants.py`): por classe e papel, 1-5 opções (a
  1ª = kit fixo da O10, default de registros antigos). O personagem SORTEIA
  1 por papel NA CRIAÇÃO (`sortear_kit`) e persiste em `kit_skills` no
  registro — gerador, UI e roleta sorteiam; ficha/vídeo/harness veem o mesmo
  lutador. Fallback sem o campo = kit fixo. Validação em
  `database.validar_personagens`.
- **10 skills novas** (só mecânica provada): SANGUE (Estilhaço Vermelho,
  Transfusão, Ritual Carmesim, Forma Sanguinária), VOID (Fenda/Passo/Lança
  do Vazio), TRAPs (Barreira de Espinhos, Muro Ardente), Fúria do Trovão
  (CHANNEL/RAIO). Catálogo 108 → 118 skills.
- **W1 consertado** (`tools/gerador_database.py`): encantamento Title-case
  vs bucket UPPER fazia TODAS as armas sortearem de 12 skills FISICO;
  `_skills_para_elemento` normaliza + aliases declarados (Morte→TREVAS...).
- Alcançabilidade é CONTRATO: `tests/test_catalog_reachability.py` — toda
  skill tem slot em pool OU está em `SKILLS_FORA_DE_ROTACAO` declarada.
- Corpus engine migrado (kits sorteados, seed 1101): 82 skills de classe em
  circulação (eram 52). Alvo novo `S6_skills_distintas` (p50 ≥ 7; medido 8).
  Re-pinos honestos: B1_classe_min 0,18, S5_super_armor 0,005 (metas plenas
  em `_meta`, enforce 12). Ledger da O10 FECHADO sem knob de custo: S4 casts
  p50 13 → 14-18 e S3_share_skills 0,274 ≥ meta 0,23 vieram do custo efetivo
  (11A) + pools.

## 🎬 DESCRIÇÃO E DEMOS (Onda 11D)

- **Biblioteca de demos**: `python -m neural_fights.recording.skill_demo
  --todas` — cena encenada (caster + boneco, geometria do contrato, arena
  limpa, HUD off) grava mp4 LIMPO por skill em `outputs/skill_demos/` +
  `manifest.json` com hash do contrato (regrava só o que mudou). 116 demos.
- **UI**: criação de personagem mostra o KIT com swatch de cor, papel,
  custo/cd e DESCRIÇÃO (1ª vez que `descricao`/`cor` do catálogo aparecem na
  UI); botão 🎲 re-sorteia; clique abre a demo (`os.startfile`). A forja
  preenche a vaga órfã `lbl_custo` + descrição por slot.
- **Vídeo**: fichas (`runner.fichas_do_banco`) carregam `kit` com descrição;
  o `fight_card` lista os nomes; na ESTREIA (só nela — teto de 95 s da
  roleta) entram até 4 eventos `skill_card` entre o card e o gameplay: demo
  mp4 com placa (nome + descrição na cor da skill) ou card sintético.

## 🎨 RENDERIZAÇÃO (neural_fights/simulation/simulacao.py)

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

## 🔊 SISTEMA DE ÁUDIO (neural_fights/effects/audio.py)

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

### Flags em neural_fights/core/hitbox.py
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
python -m neural_fights.cli.roster --modo completo --seed 42

# Testes
python -m neural_fights.cli.headless
python test_visual_debug.py
```

---

## 🎯 ARQUIVOS POR OBJETIVO

| Objetivo | Arquivo |
|----------|---------|
| Corrigir comportamento da IA | `neural_fights/ai/brain.py` |
| Corrigir ataque/dano | `neural_fights/core/entities.py`, `neural_fights/core/hitbox.py` |
| Corrigir projéteis | `neural_fights/core/combat.py` |
| Adicionar nova arma | `neural_fights/tools/gerador_database.py`, `neural_fights/core/hitbox.py` |
| Nova personalidade | `neural_fights/ai/personalities.py` |
| Nova skill | `neural_fights/core/skills.py` |
| Corrigir visual | `neural_fights/simulation/simulacao.py` |
| Novo efeito | `neural_fights/effects/` |
| Problemas de física | `neural_fights/core/physics.py` |

---

*Última atualização: v12.0 TOURNAMENT EDITION*
