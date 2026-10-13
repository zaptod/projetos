# Auditoria profunda — Motor: efeitos, modelos e sons

Fatia: `neural_fights/effects/**` (16 arquivos, 406 funções), `neural_fights/models/**` (4 arquivos, 26 funções), `neural_fights/sounds/**` (1 módulo, 1 `sound_config.json`, 20 arquivos de áudio). Data: 13/10/2026. Só relatório; nenhum código do projeto foi alterado.

Provas rodadas fora do repositório, em `E:\tmp_pytest\nf_audit_*` (script `prova_effects.py` no scratchpad do chat), com `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`, sem rede, sem Godot, sem escrever em `outputs/`. Nenhuma função sob suspeita foi dublada: as provas chamam o código real (`Simulador`, `AudioManager`/`AnotadorDeAudio`, `AttackAnimationManager`, `WeaponAnimator`, `Arma`, `Câmera`).

## Examinado

**effects/** — `__init__.py` (re-exports), `audio_paths.py` (6 funções), `budget.py` (`FrameBudget`), `visual.py` (`FloatingText`, `Decal`), `particles.py` (`ParticleBudget`, `Particula`, `HitSpark`, `Shockwave`, `EncantamentoEffect`), `impact.py` (`ImpactFlash`, `MagicClash`, `BlockEffect`, `DashTrail`), `audio.py` (`AudioManager` inteiro: registro, fallbacks, `play`, `play_positional`, `play_attack`, `play_impact`, `play_skill`, `play_movement`, `play_special`, `play_ui`, atalhos), `audio_anotador.py` (`_SomRegistrado`, `AnotadorDeAudio`, `arquivos_de_som`), `mixagem.py` (`decodificar`, `com_pitch`, `mixar`, `nivel_ativo_db`, `limitar`, `normalizar`, `gravar_wav`, `trilha_da_luta`), `camera.py` (`Câmera`: ARENA/AUTO/DIRETOR/P1/P2/MANUAL, emergência, punch, shake), `character_flair.py` (`resolver_expressao`, `_Rosto` e as 24 expressões, `desenhar_rosto`), `weapon_render.py` (`Pincel`, 54 silhuetas, `desenhar`), `magic_vfx.py` (`MagicParticle`, trilha, explosão, beam, aura, summon, `MagicVFXManager`), `attack.py` (tiers, `CraterMark`, `GroundCrack`, `WeaponTrailEnhanced`, `ImpactShockwave`, `ImpactSparks`, `ScreenFlash`, `AttackAnticipation`, `AttackAnimationManager`, `calcular_knockback_com_forca`), `movement.py` (`AfterImage(Trail)`, `DustCloud`, `SpeedLinesEffect`, `MotionBlur`, `SquashStretch`, `RecoveryFlash`, `MovementAnimationManager`), `weapon_animations.py` (`Easing`, perfis, `WeaponAnimator` com as 4 coreografias + mangual + adagas, `WeaponTrailRenderer`, `SlashEffect`, `ThrustEffect`, `BowDrawEffect`, `WeaponAnimationManager`).

**models/** — `constants.py` (raridades, tipos, encantamentos, passivas, classes, kits, helpers), `weapons.py` (`gerar_passiva_arma`, `Arma`, validação/sugestão/escala), `characters.py` (`Personagem`), `__init__.py`.

**sounds/** — `sound_config.json` conferido chave a chave contra os 20 arquivos no disco e contra `SOUND_FALLBACKS`.

**Chamadores conferidos** (fora da fatia, só leitura): `simulation/simulacao.py` (semente, escolha do áudio, `_update_step`, trilhas de projétil, `criar_attack_impact`, `reset_weapon_animation_manager`), `core/entities.py` (`AttackAnimationManager().criar_anticipation`, `play_skill` no cast), `recording/timeline.py` e `fight_recorder.py` (uso do `AnotadorDeAudio`), `ui/view_armas.py` (estilos).

## Confirmados (do mais grave ao menos)

### 1. Som de skill no cast é medido contra um ouvinte parado em x=0: some no terço direito da arena

- **Onde:** `neural_fights/core/entities.py:1668` chamando `neural_fights/effects/audio.py:644` (`AudioManager.play_skill`) → `play_positional` (`audio.py:526`).
- **O defeito:** `audio.play_skill(tipo, nome_skill, self.pos[0], phase="cast")` passa a posição do conjurador como `pos_x` e deixa `listener_x` no default `0`. `play_positional` atenua por `|pos_x - 0|` com `max_distance=20` e devolve sem tocar quando a distância passa de 20 m. O ouvinte de verdade (a câmera) nunca entra. Todos os outros pontos do jogo (`simulacao.py:1214, 1771, 1904, 2833, 2851, 2872, 4187, 4419`) passam `listener_x` calculado; este é o único que esquece.
- **Quando acontece:** toda conjuração de PROJETIL/AREA/DASH/BUFF/BEAM/SUMMON/TRAP/TRANSFORM/CHANNEL. Arena padrão tem 30 m de largura (`core/arena.py:57`), a "Colosso" 35 m: quem conjura com x > 20 m fica mudo; quem conjura a 10 m toca com metade do volume. No vídeo (o `AnotadorDeAudio` herda a mesma decisão) o lado direito da arena não tem som de cast.
- **Prova:** `AnotadorDeAudio(seed=1).play_skill("PROJETIL", "Bola de Fogo", x, phase="cast")` para x = 2, 10, 19, 21, 28 m → volumes 0,67 / 0,29 / 0,02 / SILÊNCIO / SILÊNCIO.
- **Conserto sugerido:** em `entities.py:1668` passar `listener_x` da câmera (como os demais chamadores fazem), ou chamar `play_skill(..., pos_x=0)` para cair no `play` não posicional. No `AudioManager`, `play_positional` deveria recusar `listener_x` ausente em vez de assumir 0.

### 2. `AudioManager.play` com pan dobra o volume: todo som posicional sai até 1,8x mais alto que o mesmo som sem pan

- **Onde:** `neural_fights/effects/audio.py:515-519`.
- **O defeito:** para `pan != 0`, `left = fv*(1-max(0,pan))`, `right = fv*(1+min(0,pan))` e o volume aplicado é `min(1, left+right) = fv*(2-|pan|)`. Em pan ≈ 0 isso é `2*fv`; só em |pan| = 1 volta a `fv`. O código queria somar canais, mas o pygame recebe um volume mono. Resultado: descontinuidade em pan=0 (0,56 → 1,0 com pan 0,001) e som posicional perto do ouvinte sempre saturado em 1,0.
- **Quando acontece:** todo `play_positional` (ataques, impactos, skills, pulo/aterrissagem, dash, clash mágico). O `AnotadorDeAudio` anota esse mesmo volume, então a trilha do vídeo (`mixagem.mixar`) recebe golpes em 1,0 e UI/arena em 0,56; a normalização por trecho depois empurra tudo para `ALVO_DB`, mas a relação entre sons fica errada.
- **Prova:** `play("clash_swords", 1.0, pan=0.0)` → 0,56; `pan=0.001` → 1,0; `pan=0.5` → 0,84; `play_positional(pos_x=10.0, listener_x=10.2)` → 1,0; mesma posição do ouvinte → 0,56 (master 0,7 × sfx 0,8 × cat 1,0).
- **Conserto sugerido:** `sound.set_volume(final_volume)` sempre e guardar o pan só para quem souber usá-lo (o anotador já grava `pan`); ou usar `Channel.set_volume(left, right)` com `left = fv*min(1, 1-pan)`, `right = fv*min(1, 1+pan)`.

### 3. `AttackAnimationManager()` em `entities.py` reinicializa o singleton a cada ataque pesado: apaga crateras, rachaduras, flashes, o telegraph anterior e o PPM

- **Onde:** `neural_fights/effects/attack.py:669-703` (`__new__` devolve o singleton, mas `__init__` roda de novo em toda chamada) e `neural_fights/core/entities.py:2739` (`AttackAnimationManager().criar_anticipation(self)`).
- **O defeito:** `__init__` recria todas as listas e põe `self.ppm = 50`. A simulação guarda a mesma instância em `self.attack_anims` (`simulacao.py:486`) e chama `set_ppm(PPM)`. Cada vez que um lutador de tier heavy/colossal começa um ataque, `AttackAnimationManager()` zera `crater_marks`, `ground_cracks`, `screen_flashes`, `anticipations` (o `MAX_ANTICIPATIONS = 2` nunca chega a valer: só sobrevive o telegraph mais novo) e o PPM. Só nasce quando há display (`pygame.display.get_surface()`), portanto roda na gravação de vídeo e na live, não no headless.
- **Quando acontece:** toda luta com Guerreiro/Berserker/Cavaleiro etc. acima de força 7,0 (≈25 % do roster, segundo o próprio comentário do módulo). As marcas criadas por `criar_attack_impact` (`simulacao.py:4370`) desaparecem no golpe pesado seguinte.
- **Prova:** instância com 1 cratera, 1 rachadura, 1 flash, 1 antecipação e ppm 40 → `AttackAnimationManager()` devolve o mesmo objeto (`is` True) e deixa 0/0/0/0 e ppm 50.
- **Conserto sugerido:** guardar a inicialização em `__new__` (ou proteger `__init__` com `if getattr(self, "_pronto", False): return`), e em `entities.py` usar o `attack_anims` recebido pelo contexto da partida em vez de construir o singleton.

### 4. Faíscas da arma vivem metade do tempo e andam 2x mais rápido (`_update_sparks` envelhece duas vezes por quadro)

- **Onde:** `neural_fights/effects/weapon_animations.py:1161-1165`.
- **O defeito:** a primeira linha faz `s.update({"timer": s["timer"] + dt})` dentro da compreensão (muta o timer) e filtra por `s["timer"] + dt < life` (já com o timer mutado, ou seja, `timer+2dt`); o laço seguinte soma `dt` de novo. Cada faísca avança `2*dt` por quadro e é descartada com `timer + 2dt ≥ life`. `draw_sparks` posiciona por `vx * timer`, então também viaja o dobro.
- **Quando acontece:** todo impacto de arma com `spark_on_impact` (quase todos os perfis). Os `spark_count` e `life` dos perfis estão calibrados para uma duração que nunca acontece.
- **Prova:** faísca com `life=0.20` a 60 Hz: último quadro viva em t = 0,100 s com timer interno 0,200 s; morta em t = 0,117 s.
- **Conserto sugerido:** trocar as três linhas por `for s in state.spark_list: s["timer"] += dt` e `state.spark_list = [s for s in state.spark_list if s["timer"] < s["life"]]`.

### 5. Invocação (SUMMON) e passos nunca tocam: `summon_cast` não é registrado e o grupo `footstep` nasce vazio

- **Onde:** `neural_fights/effects/audio.py:290-398` (`_setup_sounds`), `audio.py:400-411` (`_register_sound_group`), `audio.py:705-706`, `audio.py:723-739`.
- **O defeito:** (a) `play_skill("SUMMON")` pede `"summon_cast"`, que tem fallback em `SOUND_FALLBACKS` mas nunca passa por `_register_sound`, então `play` cai em "Sound not found". (b) `_register_sound_group("footstep", ["step_1", ...])` monta `full_name = "footstep_step_1"` porque `step_1` não começa com `footstep`; esse nome não tem config, arquivo nem fallback, e o grupo fica vazio. `play_movement("footstep")` toca nada.
- **Quando acontece:** toda conjuração de skill SUMMON (`entities.py:1668` passa o tipo "SUMMON") fica muda no jogo e no vídeo. Passos não têm chamador hoje (só o grupo morto).
- **Prova:** `AnotadorDeAudio(seed=0)`: chaves conhecidas que não resolvem para arquivo nenhum = `['footstep', 'step_1', 'step_2', 'step_3', 'step_4', 'summon_cast']`; `play_skill("SUMMON", ...)` não gera linha em `sons`.
- **Conserto sugerido:** acrescentar `self._register_sound("summon_cast")` em `_setup_sounds`; em `_register_sound_group` usar o nome da lista como está (`full_name = name`) ou registrar `footstep` com nomes `footstep_1..4`.

### 6. Estilos oferecidos no editor de armas não existem para o renderer nem para o animador

- **Onde:** `neural_fights/models/constants.py:111-202` (`TIPOS_ARMA[...]["estilos"]`), consumido por `ui/view_armas.py:496, 572, 575`; chaves reais em `effects/weapon_render.py` (`ESTILOS_*`, `FORMAS_ARREMESSO`) e `effects/weapon_animations.py` (`STYLE_PROFILES`).
- **O defeito:** o combo de estilo do editor lista "Corte (Espada)", "Estocada (Lança)", "Contusão (Maça)", "Misto", "Flail (Mangual)", "Machado (Não Retorna)", "Faca (Rápida)", "Chakram (Retorna)", "Besta", "Besta de Repetição", "Defensivo (Escudo)", "Ofensivo (Drone)", "Mágico (Orbe)", "Espada↔Lança", "Compacta↔Estendida", "Chicote↔Espada", "Arco↔Lâminas". Nenhum é chave de silhueta nem de perfil: a arma criada por ali desenha com o default do tipo (Espada Longa, Mangual genérico, faca, Orbes Místicos…) e anima com o perfil genérico. O catálogo atual (`armas.json`) está limpo porque foi gerado por outro caminho; o editor continua oferecendo os rótulos errados.
- **Quando acontece:** toda arma criada ou editada pela tela de armas (o `estilo` default é `estilos[0]`, sempre inválido para Reta/Arremesso/Orbital/Transformável).
- **Prova:** comparação das listas: 17 rótulos sem desenho/perfil; `armas.json`: 0.
- **Conserto sugerido:** fazer `TIPOS_ARMA[...]["estilos"]` apontar para as chaves de `weapon_render`/`STYLE_PROFILES` (ou derivar a lista delas), e um teste que cruze as três fontes.

### 7. `Arma`: migração de `tamanho` legado nunca roda (parâmetro nomeado nunca cai em `**kwargs`)

- **Onde:** `neural_fights/models/weapons.py:63` (`tamanho=0` na assinatura) e `weapons.py:172-181`.
- **O defeito:** o bloco "Migração de dados antigos" lê `kwargs.get('tamanho', 0)`, mas `tamanho` é parâmetro nomeado, então `kwargs` nunca o contém e `tamanho_antigo` é sempre 0. Registro antigo `{"tipo": "Reta", "tamanho": 100}` carrega com `comp_cabo = comp_lamina = largura = 0`.
- **Quando acontece:** só com dados legados sem geometria; hoje é código morto que promete uma migração que não existe. Uma arma assim passa pela validação (`calcular_tamanho_arma` = 0 → "MUITO PEQUENA") e desenha com L = 0.
- **Prova:** `Arma("Teste", "Reta", 10, 1.0, tamanho=100)` → `comp_cabo=0.0, comp_lamina=0.0, largura=0.0` (esperado 30/70/5).
- **Conserto sugerido:** usar `tamanho` (o parâmetro) no bloco de migração, ou remover o bloco.

### 8. `get_escala_visual_arma` divide por zero com arma de geometria nula

- **Onde:** `neural_fights/models/weapons.py:439-440`.
- **O defeito:** `proporcao < 0.4` inclui `proporcao == 0` e devolve `0.4 / proporcao`. `calcular_tamanho_arma` devolve 0 para Arremesso com `tamanho_projetil=0`, Arco com `tamanho_arco=0`, Reta sem cabo/lâmina (ver item 7).
- **Quando acontece:** sem chamador no repositório (função exportada em `models/__init__`, nunca usada) — latente.
- **Prova:** `get_escala_visual_arma(Arma("Kunai","Arremesso",5,0.5,tamanho_projetil=0), Personagem("P",10,5,5))` → `ZeroDivisionError`.
- **Conserto sugerido:** `if proporcao <= 0: return 1.0` antes do ramo, ou apagar a função.

### 9. `sound_config.json` aponta 26 das 46 chaves para arquivos que não existem no pacote

- **Onde:** `neural_fights/sounds/sound_config.json` contra `neural_fights/sounds/*.mp3|wav`.
- **O defeito:** `punch_*`, `kick_*`, `impact_*`, `ice_impact`, `lightning_impact`, `energy_impact`, `beam_end`, `teleport_*`, `buff_activate`, `heal_cast`, `shield_*`, `summon_cast`, `arena_victory`, `round_start`, `ko_impact`, `ui_back`, `slowmo_*` listam `.mp3` inexistentes. Tudo cai no `SOUND_FALLBACKS` (todos têm), então nada quebra, mas o arquivo de configuração — a fonte que o painel edita — descreve uma biblioteca que não é a que toca. Caso notável: `arena_victory` resolve para `arena_start.mp3` (2 MB, a abertura da arena) na categoria `ambiente` com volume 0,03 no config do Adrian; a "vitória" é a música de abertura quase muda.
- **Quando acontece:** sempre; o fallback é silencioso (`logger.debug`).
- **Prova:** 26 chaves ausentes, 0 sem fallback; `reg.sounds["arena_victory"].arquivo.name == "arena_start.mp3"`.
- **Conserto sugerido:** limpar o config para as chaves com arquivo real, ou registrar explicitamente os aliases; um teste que recuse chave de config sem arquivo.

### 10. `Câmera.esta_visivel` e `get_bounds_mundo` usam `LARGURA/ALTURA` do config, não a tela da câmera

- **Onde:** `neural_fights/effects/camera.py:631-642`.
- **O defeito:** a câmera aceita `screen_width/height` (1080×1920 no vídeo), mas estes dois métodos usam as constantes 1200×800. Em retrato a "altura visível" sai com 29 m quando são 70 m.
- **Quando acontece:** sem chamador no repositório hoje (código morto); quem religar o culling pega o quadro errado.
- **Prova:** `Câmera(1080,1920)` + `set_arena_bounds(15,10,30,20)` → `get_bounds_mundo` altura 29,2 m vs real 70,07 m.
- **Conserto sugerido:** usar `self.screen_width/self.screen_height`, ou apagar os dois métodos.

### 11. Trilha das faíscas de explosão desenhada espelhada

- **Onde:** `neural_fights/effects/magic_vfx.py:112-114`.
- **O defeito:** a linha é traçada de `(2,2)` a `(|dx|+2, |dy|+2)` numa surface colada em `(min x, min y)`: só está certa quando dx e dy têm o mesmo sinal; nos outros dois quadrantes a trilha sai refletida (vai de cima-esquerda para baixo-direita embora a partícula suba para a direita).
- **Quando acontece:** partículas com `trail=True` (as 15×tamanho faíscas de `DramaticExplosion`), metade das direções.
- **Prova:** p1=(100,100), p2=(120,80) → segmento desenhado de (100,80) a (120,100).
- **Conserto sugerido:** calcular os dois pontos relativos ao offset (`p1 - offset`, `p2 - offset`), como `impact.DashTrail.draw` já faz.

### 12. `AfterImage` nasce com `vida` maior que `max_vida`

- **Onde:** `neural_fights/effects/movement.py:100-102, 169-179`.
- **O defeito:** `AfterImageTrail._spawn_image` passa `max_vida=0.2 + n*0.02` e deixa `vida` no default 0,3. `update` clampa `prog` em 0, então a cópia fica opaca por 0,1 s e só então começa a esmaecer; a "images mais antigas duram mais" do comentário não acontece do jeito escrito.
- **Prova:** `AfterImage(..., max_vida=0.2)` → `vida=0.3, max_vida=0.2`.
- **Conserto sugerido:** passar `vida=max_vida` no spawn.

### 13. Miúdos (confirmados por leitura, sem prova separada)

- `audio_anotador.arquivos_de_som()` instancia um `AnotadorDeAudio` a cada chamada e, por herança de `AudioManager.__init__`, faz `os.makedirs(runtime/sounds)` e relê o config — a mistura cria pasta no diretório de runtime só para listar arquivos (provado: pasta criada). Baixo.
- `AudioManager._load_sound_config` aceita qualquer valor em `_volumes` (string, >1, negativo) sem validar; `set_category_volume` clampa, o load não. Um `"golpes": "1.0"` no JSON do runtime quebra em `play` com `TypeError`. Baixo.
- `models/constants.py:338-342` multiplica `dano_bonus`/`dot_dano` dos encantamentos no import; um `importlib.reload` dobra de novo. Baixo.
- `get_class_data`/`get_raridade_data`/`get_tipo_arma_data` devolvem o default (Guerreiro/Comum/Reta) para nome desconhecido sem avisar — um erro de digitação na classe vira Guerreiro calado. Baixo.
- `Arma.__init__` guarda a lista `habilidades` recebida por referência; `adicionar_habilidade` muta a lista do chamador. Baixo.
- `particles.py` define `TETO_PARTICULAS = 900`, `TETO_DECALS`, `TETO_VFX_POR_LISTA` e `ParticleBudget`, nenhum usado (o orçamento vivo é `budget.FrameBudget` com teto 260): duas "doutrinas" com o mesmo nome e valores diferentes. Baixo.
- Caminhos mortos em `attack.py` (o próprio módulo documenta): `WeaponTrailEnhanced.add_point`, `ImpactShockwave`, `ImpactSparks`, `ScreenFlash` fora do tier colossal, `calcular_knockback_forca` (método, não a função). `MagicVFXManager.spawn_aura/spawn_beam` sem chamador; neles o `_capar(self.auras)` poderia expulsar uma aura persistente que `_auras_persistentes` ainda referencia (só latente, porque ninguém chama `spawn_aura`).
- `impact.ImpactFlash.draw` grava `self.tela = tela` (atributo perdido); `BlockEffect.draw` passa cor com alfa direto na tela (o alfa é ignorado). Cosmético.

## Não confirmados

- **Invariância a VFX (a regra de ouro): confirmada OK.** Duas sementes (123, 777), luta até o KO (2800 e 2749 quadros a 60 Hz): (A) headless puro × (B) headless + `desenhar()` em todo quadro + câmera em AUTO (tremor sorteado no `random` global) + `AudioManager` real no driver dummy (sorteio de variante no `random` global) + 7 chamadas extras a `random.random()` por quadro. O hash de posição/vida/mana/morto por quadro foi idêntico. Motivo: o combate usa `random.Random` próprio por lutador (`simulacao.py:392-396`); fora de `effects/` só `simulacao.py` (partículas), `utils/__init__.py` (helpers de cor) e `live/registry.py` tocam o `random` global. `WeaponAnimator` tem RNG próprio semeado por round; o pitch do anotador também.
- Efeito escrevendo estado da simulação: não encontrado. Todos os efeitos só leem `pos`, `z`, `vida`, `morto`, `brain.*`. `calcular_knockback_com_forca` (em `effects/attack.py`) é usado pelo combate (`simulacao.py:4173`), mas é função pura — mora na pasta errada, não é bug.
- `time` ou relógio de parede em efeito/som: não há; `character_flair` e `weapon_render` recebem `tempo_s` do chamador.
- Listas que crescem sem teto entre lutas: `MagicVFXManager.trails` é limpo por quadro (`simulacao.py:1507-1509`) e o manager é recriado por partida; `WeaponAnimator.states` é recriado por round (`reset_weapon_animation_manager`); `MovementAnimationManager`/`AttackAnimationManager` têm tetos e `reset()` na montagem da partida. OK.
- Divisão por zero em efeitos: `MotionBlur`, `SquashStretch`, `ImpactFlash`, `Shockwave`, `DramaticBeam` etc. têm `max_vida`/`vida_max` fixos > 0; `_get_phase` protege duração 0 com `max(duration, 0.001)`; `Câmera._limitar_centro_a_arena` protege `zoom <= 0`. Único buraco real está no item 8 (`get_escala_visual_arma`). `Câmera.set_arena_bounds` divide por `largura*PPM` — as arenas do catálogo têm largura ≥ 16 m.
- Índice fora da lista em paletas: `ELEMENT_PALETTES.get(..., DEFAULT)` em todos os pontos; `CORES_ENCANTAMENTOS.get(..., [(255,255,255)])`; `random.randint(0, len(segments)-2)` em `DramaticBeam` com `segments` ≥ 2 sempre. OK.
- Cadeia de fallbacks de som com ciclo: nenhum ciclo em `SOUND_FALLBACKS` (todos terminam em arquivo existente).
- `Personagem.to_dict` não grava `peso_arma`: é derivado da arma no carregamento (`peso_arma_cache` é calculado por quem monta a ficha), não há perda.
- `_get_sound_category` por prefixo: a ordem do dicionário dá o resultado esperado para os nomes usados (`dash`→skills, `impact_x`→impactos, `ice_x`→projeteis).
- `mixagem.py`: `limitar`/`normalizar`/`mixar` lidam com buffer vazio, `t` antes do trecho, pitch ≤ 0 e falta de numpy; o cache de `decodificar` é por caminho+mtime e tem no máximo os ~20 arquivos. Não achei defeito.
