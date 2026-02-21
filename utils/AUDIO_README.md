# 🔊 Sistema de Áudio Neural Fights v10.0

## 📋 Visão Geral

Sistema completo de áudio procedural integrado ao Neural Fights, adicionando feedback sonoro para todos os aspectos do combate: golpes físicos, magias, skills, impactos, bloqueios e eventos especiais.

## 🎵 Características

### ✨ Geração Procedural de Sons
- **Sons sintéticos** gerados em tempo real quando arquivos de áudio não estão disponíveis
- Cada categoria tem perfis únicos de onda sonora
- Sistema baseado em **numpy** para síntese de audio
- **Fallback inteligente**: usa sons procedurais se arquivos reais não existirem

### 🎯 Áudio Posicional
- **Pan estéreo** baseado na posição do som na tela
- **Atenuação por distância** automática
- Som segue a posição da câmera (listener)
- Suporte para até **32 canais simultâneos**

### 🎮 Categorias de Sons

#### 1. **Golpes Físicos**
- `punch` (soco leve, médio, pesado)
- `kick` (chute leve, pesado, giratório)
- `slash` (cortes de espada leve, pesado, crítico)
- `stab` (estocadas rápidas e profundas)

#### 2. **Impactos**
- `impact` (impacto em carne, pesado, crítico)
- Volume e intensidade baseados no dano causado
- Sons diferentes para hits críticos e counters

#### 3. **Magias e Projéteis**
- `fireball` (cast, voar, impacto)
- `ice` (cast, estilhaço, impacto)
- `lightning` (carregar, raio, impacto)
- `energy` (carregar, disparo, impacto)
- `beam` (carregar, disparar, fim)

#### 4. **Skills Especiais**
- `dash` (whoosh, impacto)
- `teleport` (saída, entrada)
- `buff` (ativar, pulso)
- `heal` (cast, completar)
- `shield` (subir, bloquear, quebrar)

#### 5. **Movimentos**
- `jump` (início, aterrissagem)
- `footstep` (4 variações)
- `dodge` (whoosh, deslizar)

#### 6. **Ambiente**
- `wall_hit` (impacto leve/pesado na parede)
- `ground_slam` (impacto no chão)

#### 7. **Eventos Especiais**
- `ko_impact` (nocaute fatal)
- `combo_hit` (combo)
- `counter_hit` (contra-ataque)
- `perfect_block` (bloqueio perfeito)
- `stagger` (atordoamento)

## 🛠️ API do AudioManager

### Inicialização
```python
from audio import AudioManager

# Singleton - sempre retorna a mesma instância
audio = AudioManager.get_instance()

# Reset (útil para recarregar)
AudioManager.reset()
```

### Métodos Principais

#### `play(sound_name, volume=1.0, pan=0.0)`
Toca um som básico.
```python
audio.play("punch", volume=0.8)  # 80% do volume
audio.play("fireball_cast", volume=1.0, pan=-0.5)  # Pan para esquerda
```

#### `play_positional(sound_name, pos_x, listener_x, max_distance=20.0, volume=1.0)`
Toca som com posicionamento espacial.
```python
# Som na posição x=10, ouvinte em x=5
audio.play_positional("impact", 10.0, 5.0, volume=0.9)
```

#### `play_attack(attack_type, pos_x=0, listener_x=0)`
Toca som de ataque baseado no tipo.
```python
audio.play_attack("SOCO", pos_x=5.0, listener_x=0.0)
audio.play_attack("ESPADADA", pos_x=lutador.pos[0], listener_x=camera.x)
```

**Tipos suportados:**
- `"SOCO"` → punch
- `"CHUTE"` → kick
- `"ESPADADA"` → slash
- `"MACHADADA"` → slash
- `"FACADA"` → stab
- `"ARCO"` → energy
- `"MAGIA"` → energy

#### `play_impact(damage, pos_x=0, listener_x=0, is_critical=False, is_counter=False)`
Toca som de impacto proporcional ao dano.
```python
# Impacto normal
audio.play_impact(25.0, lutador.pos[0], camera.x)

# Impacto crítico
audio.play_impact(45.0, lutador.pos[0], camera.x, is_critical=True)

# Contra-ataque
audio.play_impact(30.0, lutador.pos[0], camera.x, is_counter=True)
```

**Lógica automática:**
- Dano > 50 → `impact_heavy`
- Crítico → `impact_critical`
- Counter → `counter_hit`
- Normal → `impact`

#### `play_skill(skill_type, skill_name="", pos_x=0, listener_x=0, phase="cast")`
Toca som de skill baseado no tipo e fase.
```python
# Cast de projétil
audio.play_skill("PROJETIL", "Bola de Fogo", pos_x=5.0, phase="cast")

# Impacto de área
audio.play_skill("AREA", "Explosão", pos_x=10.0, phase="impact")

# Beam ativo
audio.play_skill("BEAM", "Laser", pos_x=5.0, phase="active")
```

**Tipos suportados:**
- `"PROJETIL"` → fireball/ice/lightning/energy (depende do nome)
- `"BEAM"` → beam_charge/fire/end
- `"AREA"` → energy_impact/fireball_impact/ice_impact
- `"DASH"` → dash_whoosh/impact
- `"BUFF"` → buff_activate/heal_cast/shield_up
- `"TELEPORT"` → teleport_out/in

**Fases:**
- `"cast"` - Início da skill
- `"fly"/"active"` - Durante a execução
- `"impact"` - Acerto no alvo

#### `play_movement(movement_type, pos_x=0, listener_x=0)`
Sons de movimento.
```python
audio.play_movement("jump", pos_x=lutador.pos[0])
audio.play_movement("dodge", pos_x=lutador.pos[0])
audio.play_movement("footstep", pos_x=lutador.pos[0])
```

#### `play_special(event_type, volume=0.8)`
Eventos especiais do jogo.
```python
audio.play_special("ko", volume=1.0)
audio.play_special("perfect_block", volume=0.9)
audio.play_special("wall_hit", volume=0.6)
```

### Controles de Volume

```python
# Volume mestre (afeta tudo)
audio.set_master_volume(0.7)  # 70%

# Volume de efeitos sonoros
audio.set_sfx_volume(0.8)  # 80%

# Liga/desliga áudio
audio.toggle_enable()

# Para todos os sons
audio.stop_all()
```

## 🎨 Integração no Código

### No Simulador (simulacao.py)
```python
from audio import AudioManager

class Simulador:
    def __init__(self):
        # ...
        self.audio = None
    
    def recarregar_tudo(self):
        # ...
        AudioManager.reset()
        self.audio = AudioManager.get_instance()
```

### Em Ataques Físicos
```python
# Quando ataque acerta
if acertou:
    if self.audio:
        listener_x = self.cam.x / PPM
        self.audio.play_attack(tipo_ataque, atacante.pos[0], listener_x)
    
    # Após aplicar dano
    if self.audio:
        self.audio.play_impact(dano, defensor.pos[0], listener_x, 
                              is_critico, is_counter)
```

### Em Skills (entities.py)
```python
def usar_skill_arma(self, skill_idx=None):
    from audio import AudioManager
    # ...
    
    if tipo == "PROJETIL":
        audio = AudioManager.get_instance()
        if audio:
            audio.play_skill("PROJETIL", nome_skill, self.pos[0], phase="cast")
        # Cria projétil...
```

### Em Projéteis (simulacao.py)
```python
if colidiu and proj.ativo:
    if self.audio:
        listener_x = self.cam.x / PPM
        self.audio.play_skill("PROJETIL", tipo_proj, proj.x, 
                             listener_x, phase="impact")
```

### Em Eventos Especiais
```python
# Bloqueio
if bloqueou:
    if self.audio:
        self.audio.play_special("shield_block", volume=0.7)

# Colisão com parede
if colidiu_parede:
    if self.audio:
        volume = min(1.0, velocidade / 15) * 0.6
        self.audio.play_special("wall_hit", volume=volume)

# KO
if morreu:
    if self.audio:
        self.audio.play_special("ko", volume=1.0)
```

## 📁 Estrutura de Arquivos

### Arquivos de Som (Opcional)
Se você quiser usar sons reais ao invés dos procedurais, crie:
```
neural/
├── sounds/
│   ├── punch_light.wav
│   ├── punch_medium.wav
│   ├── kick_heavy.wav
│   ├── fireball_cast.wav
│   ├── ice_impact.wav
│   ├── beam_fire.wav
│   └── ...
```

**Formatos suportados:** `.wav`, `.ogg`, `.mp3`

### Arquivos do Sistema
- `audio.py` - AudioManager e sistema completo
- `simulacao.py` - Integração com combate
- `core/entities.py` - Integração com skills

## 🔧 Personalização

### Adicionando Novos Sons

1. **Som procedural:**
   Adicione lógica em `_generate_procedural_sound()`:
   ```python
   elif "novo_som" in name:
       # Sua lógica de síntese aqui
       wave = np.sin(2 * np.pi * 440 * t)
   ```

2. **Som de arquivo:**
   - Coloque o arquivo em `sounds/`
   - Nome: `categoria_variante.wav`
   - O sistema carrega automaticamente

### Adicionando Grupos de Sons

```python
def _setup_sounds(self):
    # Adicione um novo grupo
    self._register_sound_group("meu_grupo", [
        "som_1", "som_2", "som_3"
    ])
```

### Alterando Volume Base

```python
# No código
audio.play_skill("AREA", "Explosão", volume=1.2)  # 120% (máximo)

# Globalmente
audio.set_sfx_volume(0.5)  # 50% de todos os efeitos
```

## 🎯 Boas Práticas

1. **Use áudio posicional** quando relevante:
   ```python
   audio.play_positional("impact", lutador.pos[0], camera.x)
   ```

2. **Ajuste volume por contexto:**
   - Passos: 0.3
   - Hits normais: 0.6-0.8
   - Skills: 0.7-0.9
   - KO/eventos especiais: 1.0

3. **Sempre cheque se audio existe:**
   ```python
   if self.audio:
       self.audio.play(...)
   ```

4. **Use nomes descritivos de skills:**
   - Ajuda o sistema escolher sons adequados
   - "Bola de Fogo" → som de fogo
   - "Lança de Gelo" → som de gelo

## 🐛 Troubleshooting

### Sem som?
1. Verifique se pygame.mixer inicializou: `pygame.mixer.get_init()`
2. Verifique volume: `audio.master_volume` e `audio.sfx_volume`
3. Verifique se está habilitado: `audio.enabled`

### Sons cortando?
- Aumente número de canais: `pygame.mixer.set_num_channels(64)`

### Performance ruim?
- Desabilite sons procedurais (use arquivos)
- Reduza número de sons simultâneos
- Simplifique síntese em `_generate_procedural_sound()`

### Numpy não instalado?
- Sons procedurais não funcionarão
- Sistema usa silêncio como fallback
- Instale: `pip install numpy`

## 📊 Estatísticas do Sistema

- **Grupos de sons:** 14 categorias principais
- **Variantes:** 40+ sons diferentes
- **Canais simultâneos:** 32
- **Formato interno:** 44.1kHz, 16-bit, estéreo
- **Buffer:** 512 samples (baixa latência)
- **Atenuação:** Até 20 metros de distância

## 🎬 Exemplos Completos

### Exemplo 1: Combo System
```python
# A cada hit do combo
audio.play_attack("SOCO", lutador.pos[0], camera.x)
audio.play_impact(dano, alvo.pos[0], camera.x)

# No último hit
if combo_finalizado:
    audio.play_special("combo", volume=1.0)
```

### Exemplo 2: Skill Completa
```python
# Cast
audio.play_skill("PROJETIL", "Bola de Fogo", pos_x, phase="cast")

# Projétil voando (opcional)
# audio.play_skill("PROJETIL", "Bola de Fogo", pos_x, phase="fly")

# Impacto
audio.play_skill("PROJETIL", "Bola de Fogo", pos_x, phase="impact")
```

### Exemplo 3: Boss Fight
```python
# Entrada do boss
audio.play_special("ground_slam", volume=1.0)

# Ataques especiais
if boss_ataque_especial:
    audio.play_skill("BEAM", "Laser Destruidor", boss.pos[0], phase="cast")
    # ... depois
    audio.play_skill("BEAM", "Laser Destruidor", boss.pos[0], phase="active")
```

## 🚀 Melhorias Futuras

- [ ] Sistema de música ambiente por arena
- [ ] Efeitos de reverb baseados no ambiente
- [ ] Filtros de áudio em slow-motion
- [ ] Sons específicos por arma/personagem
- [ ] Sistema de vozes (grunts, gritos)
- [ ] Carregar sons de mod packs
- [ ] Editor de sons procedurais in-game

---

## 📞 Suporte

Para dúvidas sobre o sistema de áudio:
1. Leia este documento
2. Veja exemplos em `simulacao.py` e `entities.py`
3. Teste com `audio = AudioManager.get_instance()`

**Neural Fights v10.0 - AUDIO EDITION** 🎵
