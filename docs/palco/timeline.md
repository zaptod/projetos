# `timeline v1`: o contrato entre a simulação e o palco (Onda 16C)

Dono: builds (16C, 28/09/2026). Leitor: o palco em Godot (16D). Código:
`neural_fights/recording/timeline.py` (a sonda, o laço e o hash de estado) e
`neural_fights/recording/timeline_arquivo.py` (disco, schema em código, leitura).
Testes: `tests/test_timeline_palco_regressions.py`.

O palco desenha a luta **só** a partir deste arquivo. A simulação nunca depende
dele e ele nunca decide nada da luta: tudo o que o motor sabia a cada passo sai
daqui, em **metros, graus e segundos**.

## Relógio

- **Um valor por passo do motor, a 60 Hz** (`hz: 60`). O passo `i` vale
  `t = i / 60` s de **vídeo**, contados a partir do primeiro passo. É o mesmo
  relógio do gravador: o quadro `k` do vídeo de 30 fps é o passo `2k` (o
  gravador captura um quadro a cada dois passos).
- Por que 60 Hz e não 30: (1) é a taxa da simulação, então nenhum estado se
  perde; (2) várias fases de golpe duram menos que um quadro de 30 fps (o
  impacto da Adaga Gêmea tem 8 ms, a antecipação 18 ms) e a 60 Hz a marca de
  impacto cai a no máximo 16,7 ms do instante real; (3) a câmera lenta do palco
  (16D) a 0,5× precisa de 60 amostras por segundo para não repetir quadro. O
  custo é o dobro do tamanho, e a compressão (abaixo) paga isso.
- `trilhas.global.tj` é o tempo de **jogo**: no slow-mo do KO (`escala` 0,25) o
  vídeo anda um passo e o jogo anda um quarto. `hitstop > 0` = mundo congelado
  (os lutadores ficam parados na timeline, como na tela).
- Eventos têm `i` (passo) e `t` (`i / 60`). A lista `sons` (Onda 16A) usa o `t`
  do gravador, que é quantizado ao quadro de 1/30 s: um som pedido num passo
  ímpar aparece no passo par seguinte, o primeiro quadro que mostra aquele
  passo. **Desde a revisão 2** cada som traz também o `i`, o passo exato em
  que o jogo o pediu: `t = ceil(i / 2) / 30` (há teste cobrando). O palco
  que toca a 60 Hz ou em câmera lenta usa `i / 60`; quem mistura o mp4 de
  30 fps continua no `t`.

## Unidades e coordenadas

Mundo em **metros**, x para a direita e **y para baixo** (como o motor), `z` =
altura do pulo (o render desenha o corpo em `(x, y − z)`). Ângulos em **graus**,
0 = +x, crescendo no sentido horário na tela (y para baixo). Cores `0xRRGGBB`.
`ppm_motor: 50` só documenta a conversão do motor (px por metro).

## O documento

```text
formato: "neural-fights/timeline"   versao: 1   revisao: 4   hz: 60   n: <passos>   duracao: n/60
luta:        seed, p1, p2, cenario, camera_modo, camera_largura_min_m, camera_espera_zoom_in,
             corrente_v2 (revisão 4: a chave da corrente nova DESTA luta)
tela_referencia: [1080, 1920]       a tela para a qual a câmera foi calculada
arena:       formato, largura, altura, min, max, centro, raio, paredes, cores, tema,
             efeitos (clima), obstaculos[] (tipo, x, y, largura, altura, cor, solido...)
lutadores[]: slot, nome, rotulo, classe, cor, cor_lado, cor_aura_classe, tamanho,
             raio_corpo (o círculo DESENHADO = tamanho/2), raio_fisico (colisão =
             tamanho/4), vida_max, mana_max, estamina_max, forca, tier_impacto,
             skills[], arma{...}
tabelas:     expressoes (as 24), acoes, planos + planos_tipo, tells, fases, flags,
             estados_orbe
trilhas:
  global:    canais por passo (tj, escala, hitstop, letterbox, fim)
  camera:    canais por passo (x, y, zoom, lv, av, ox, oy)
  lutadores: p1 e p2, 38 canais por passo cada
  objetos[]: projeteis, orbes, areas, beams, summons, traps, portais: [i0, i1]
  efeitos[]: status, buffs, canalizacao, transformacao: [i0, i1]
eventos[]:   {i, t, tipo, ...}
sons:        null | {versao, relogio: "video", itens[]} no formato da 16A
remapeamento: null | {relogio: "gravacao", trechos: [[inicio, duracao, velocidade]...]}
resultado:   vencedor, vencedor_slot, motivo, duracao_jogo, duracao_video,
             ko_em_video, passos, quadros_video, passos_por_quadro, hp_final, seed
```

**Canais** são listas com um valor por passo (`n` valores). **Trilhas com
intervalo** (`objetos`, `efeitos`) vivem de `i0` a `i1` inclusive, e cada canal
delas tem `i1 − i0 + 1` valores: o valor do passo `i` é `canal[i − i0]`. Cada
trilha tem um `id` único e campos fixos (nome, dono, elemento, cor...). É o
mesmo desenho de uma animação: uma cena nasce em `i0`, segue os canais, some em
`i1`.

### A arma no cabeçalho do lutador

| campo | o que é |
|---|---|
| `tipo`, `estilo`, `raridade`, `cor`, `efeito_visual` | identidade; o estilo escolhe a peça do palco (`armas/estilos/<estilo>`) |
| `empunhadura` | `{avanco_r, lateral_r}` em frações do raio do corpo (`Simulador.GRIP_PROFILES`); `null` para Arremesso, Orbital e Mágica |
| `comprimento_m` | empunhadura → ponta, fixo por arma |
| `alcance_m`, `alcance_min_m` | a hitbox do motor (`sistema_hitbox.calcular_hitbox_arma`) |
| `hitbox` | forma no golpe e parada, `range_mult` |
| `perfil_golpe` | durações das 5 fases pelo **relógio do motor** (`WEAPON_PROFILES[tipo]`, o que o `timer_animacao` conta) e a `janela_hit` em segundos desde o início |
| `perfil_animacao` | durações, ângulos e easings do **animador visual** (`get_animation_profile(tipo, estilo)`) |
| `arquetipo_animacao` | corte, estocada, esmagamento, chicote ou puxada |
| `duas_laminas` | só na Dupla: a regra das duas mãos (`±separacao_r` na perpendicular, `±abertura_graus`, comprimento de cada lâmina) |

**Dois relógios de golpe, de propósito.** O motor conta o golpe pelo perfil do
TIPO (`entities.py`: `timer_animacao = WEAPON_PROFILES[tipo].total_time`) e é
por ele que a janela de acerto abre (`hitbox._verificar_janela_hit`). O
animador visual anima pelo perfil do ESTILO, que tem outras durações (Katana:
0,575 s de animação contra 0,465 s de golpe). `golpe_*` é o relógio honesto (o
que acerta); `anim_*` é o que o pygame mostra hoje. O `seek` do palco usa
`golpe_fase` + `golpe_p`.

### Canais por lutador (`trilhas.lutadores.p1` e `.p2`)

| canal | unidade | o que é |
|---|---|---|
| `x` | m | posição no chão; x cresce para a direita |
| `y` | m | posição no chão; y cresce para baixo, como no motor |
| `z` | m | altura do pulo; o render desenha o corpo em (x, y − z) |
| `ang` | graus | para onde o lutador olha (`angulo_olhar`) |
| `vx`, `vy` | m/s | velocidade no chão |
| `hp` | 0..1 | vida / vida_max |
| `mp` | 0..1 | mana / mana_max |
| `est` | 0..1 | estamina / estamina_max |
| `expr` | índice | `tabelas.expressoes` (as 24 de `character_flair`) |
| `acao` | índice | `tabelas.acoes`: `brain.acao_atual` |
| `plano` | índice | `tabelas.planos` (o rótulo que o render mostra) e `planos_tipo`; −1 sem plano |
| `plano_p` | 0..1 | progresso do plano |
| `tell` | índice | `tabelas.tells`: sinal público ativo; −1 nenhum |
| `flags` | bits | bit n = `tabelas.flags[n]` (lista abaixo) |
| `golpe_fase` | índice | `tabelas.fases` pelo RELÓGIO DO MOTOR; 0 = sem golpe |
| `golpe_p` | 0..1 | progresso dentro da fase |
| `golpe_d` | s | duração da fase atual |
| `golpe_id` | int | `ataque_id`: muda a cada golpe novo |
| `golpe_janela` | 0/1 | o golpe pode conectar agora (janela da hitbox) |
| `anim_fase`, `anim_p` | índice, 0..1 | fase e progresso do ANIMADOR visual (perfil do estilo) |
| `arma_ang` | graus | ângulo da arma (`angulo_arma_visual`) = o da hitbox |
| `arma_lunge` | raios | avanço da empunhadura, em frações do raio do corpo |
| `arma_gx`, `arma_gy` | m | empunhadura (onde a arma nasce) |
| `arma_px`, `arma_py` | m | ponta: empunhadura + comprimento honesto (= alcance da hitbox) |
| `arma_puxada` | 0..1 | corda do arco puxada |
| `hb_on` | 0/1 | hitbox ativa |
| `hb_ang`, `hb_larg` | graus | centro e abertura angular da hitbox |
| `escudo` | 0..1 | escudo restante / escudo total dos buffs; 0 sem escudo |
| `combo` | int | combo SOFRIDO em curso (2, 3...); 0 fora de combo |
| `flash`, `flash_cor` | s, 0xRRGGBB | flash de dano restante e a cor dele |
| `esc_x`, `esc_y` | fator | squash/stretch do corpo (aterrissagem, dash) |

`flags`: 0 `atacando`, 1 `morto`, 2 `atordoado`, 3 `congelado`, 4 `invencivel`,
5 `canalizando`, 6 `adrenalina`, 7 `agarrado`, 8 `dash`, 9 `intangivel`,
10 `super_armor`, 11 `bloqueando`, 12 `tempo_parado`, 13 `dormindo`,
14 `transformado`, 15 `lancado`, 16 `oculto` (portal: o render não desenha),
17 `no_ar`. Acrescentar bit no fim não muda a versão.

**Corrente V2** (rework de 01/10/2026, `neural_fights/core/corrente.py`; chave
`corrente_v2` da luta, DESLIGADA por padrão). Com a chave, a bola tem posição e
velocidade próprias no motor e o golpe acerta onde ela passa. Com a chave:
`arma_ang` de quem usa corrente aponta da mão para a BOLA; `arma_px/py`
continua com o comprimento antigo fixo (4 raios); `hb_*` e `golpe_janela`
continuam descrevendo o setor antigo, que a chave deixa de usar.

**Revisão 4 (01/10/2026): a bola.** Só no lutador cuja arma tem bola NESTA
luta (chave ligada e `physics: chain` no catálogo), e sempre os dois juntos
(o validador recusa um sem o outro):

| canal | unidade | o que é |
|---|---|---|
| `bola_x`, `bola_y` | m | centro da bola no fim do passo (no chão, como a hitbox: quem desenha o lutador levantado por `z` sobe a bola junto) |
| `bola_vx`, `bola_vy` | m/s | velocidade da bola (a do motor) |

e no cabeçalho, `arma.corrente`:

| campo | o que é |
|---|---|
| `comp_m` | corrente da mão ao centro da bola (`corrente.comprimento`: `comp_corrente + comp_ponta` do banco, 2,6 a 3,6 raios) |
| `n_elos` | quantos elos desenhar (um a cada 0,16 raio, de 8 a 40) |
| `cabeca` | `bola_espinhos` (Mangual), `martelo` (Meteor Hammer), `peso` (Corrente com Peso), `ponta` (Chicote), `foice` (Kusarigama), `dardo` (Rope Dart) |
| `material` | `elos`, `couro` (Chicote) ou `corda` (Meteor Hammer, Rope Dart) |
| `familia` | `pesada` (momento) ou `leve` (enlace), a decisão `corrente-estilos` |
| `raio_bola_m` | raio da cabeça (o do toque no acerto) |
| `v_ref_ms` | velocidade de referência do v² (`corrente.velocidade_nominal`): o rastro do palco é proporcional a `v / v_ref` |
| `mao` | `{avanco_r, lateral_r}`: a MÃO da corrente é `(x, y) + R(ang)·(avanco_r, lateral_r)·raio_corpo` — no olhar, sem o avanço do golpe; a mesma conta de `corrente.mao` |

A mão não tem canal: é derivável de `x`, `y`, `ang` e `mao` (há teste
cobrando que a bola nunca passa de `comp_m` dessa mão). O comprimento EM USO
também não: o palco usa a distância mão-bola com 6% de folga, limitada a
`comp_m` (o braço recolhe a corrente na guarda). Luta sem a chave não tem
nada disso e sai igual à revisão 3, mais `luta.corrente_v2: false`.

**Geometria honesta.** A arma nasce na mão e `empunhadura + comprimento` é o
`raio_corpo × range_mult` da hitbox (a mesma conta de `Simulador.desenhar_arma`).
A ponta está no **plano do chão**, como a hitbox: quem desenha o lutador
levantado por `z` sobe a arma junto. Morto, a arma é a caída
(`arma_droppada_pos`/`ang`, sem empunhadura). Há teste cobrando que a ponta cai
no alcance da hitbox, tipo a tipo e na luta real.

### Câmera e global

| canal | unidade | o que é |
|---|---|---|
| `camera.x`, `camera.y` | m | centro da câmera |
| `camera.zoom` | fator | zoom do motor (px da tela de referência por px de mundo) |
| `camera.lv`, `camera.av` | m | largura e altura visíveis: o palco usa isto, e não o zoom, e fica livre da resolução |
| `camera.ox`, `camera.oy` | m | tremor (0 no DIRETOR e no ARENA) |
| `global.tj` | s | tempo de jogo acumulado |
| `global.escala` | fator | `time_scale` (0,25 no slow-mo do KO) |
| `global.hitstop` | s | hit-stop restante |
| `global.letterbox` | s | barras cinematográficas do golpe letal |
| `global.fim` | 0/1 | round terminado; o resto é a cauda do vídeo |

### Objetos e efeitos (trilhas com intervalo)

| tipo | campos fixos | canais |
|---|---|---|
| `projetil` (skill) | nome, dono, elemento, cor, efeito, vida0, cone{angulo, alcance, origem}? | x, y, r, ang, prog |
| `projetil_arma` | nome, dono, cor, forma (faca, flecha, shuriken, chakram), vida0 | x, y, r, ang, prog |
| `orbe` | nome, dono, elemento, cor | x, y, r, estado (`tabelas.estados_orbe`) |
| `area` | nome, dono, elemento, cor, efeito, raio_max, pilares?, raio_pilar?, segmento? | x, y, r (raio visível), ativ (0 = aviso, 1 = dano), prog |
| `beam` | nome, dono, elemento, cor, efeito, de, ate, pontos (o zigue-zague é estado de jogo), vida0 | larg, prog |
| `summon` | nome, dono, elemento, cor, forma, raio, raio_ataque, raio_protecao | x, y, ang, hp, prog |
| `trap` | nome, dono, elemento, cor, largura, altura, angulo, bloqueia_movimento | x, y, hp, prog |
| `portal` | nome, dono, elemento, cor, a, b, raio | prog |
| `status` | alvo, status, cor, glifo, estilo, prioridade, duracao | rest (s) |
| `buff` | alvo, nome, efeito, cor, duracao, escudo_max | rest, escudo |
| `canal` | alvo, nome, elemento, cor, duracao, alcance | prog, ang |
| `transformacao` | alvo, nome, elemento, cor, cor_aura, duracao | prog |

`prog` vai de 0 (nasceu) a 1 (acabou). `dono`/`alvo` = `p1` ou `p2`. Os status
trazem a mesma metadata visual que o render usa (`STATUS_VISUAL`: cor, glifo,
estilo anel/tint/partícula, prioridade do anel dominante).

### Eventos

Detectados por TRANSIÇÃO, com a lembrança guardada na sonda (contador que
subiu, vida que caiu, cooldown que saltou). Todo evento tem `i`, `t` e `tipo`.

| tipo | campos | de onde sai |
|---|---|---|
| `acerto` | alvo, autor, dano, dano_pct, golpes, categoria, tier, critico?, golpe? + hitstop? (quando o golpe congelou o mundo), x, y, z, dir, ponto? + projetil? (revisão 3: o impacto de projétil) | vida que caiu + `hits_sofridos` que subiu; `tier` = tier de impacto do autor (`LIMIARES_FORCA`); `critico` pelo `criticos_melee` do autor; `golpe` = LEVE..EPICO do hit-stop |
| `dano` | alvo, dano, categoria, x, y | vida que caiu SEM golpe (DoT, encanto, custo) |
| `cura` | alvo, valor, x, y | vida que subiu mais de 0,5 |
| `primeiro_sangue` | slot (quem bateu) | o primeiro acerto |
| `bloqueio`, `parry` | slot (quem defendeu), x, y, ang | contadores `bloqueios` e `parries` |
| `esquiva` | slot, x, y | `esquivas_visuais` (a esquiva do Ladino: o golpe errou) |
| `desvio` | slot, x, y | `desvios_ia` (a IA leu e saiu) |
| `dash` | slot, x, y, vx, vy | contador `dashes` |
| `skill` | slot, nome, tipo_skill, elemento | o cooldown da skill saltou |
| `agarrao` | iniciador, alvo, origem | contador `agarroes` |
| `agarrao_desfecho` | iniciador, alvo, modo (ARREMESSO, JOELHADA, EMPURRAO, ESCAPE...), revertido | contadores `agarrao_<modo>` e `agarrao_reversao` |
| `parede` | slot, x, y, intensidade | `arena.colisoes_recentes` |
| `wall_splat` | autor, alvo, x, y | contador `wall_splats` |
| `obstaculo` | indice, obstaculo | obstáculo que deixou de ser sólido |
| `escudo_quebrou` | slot, x, y | escudo dos buffs chegou a 0 |
| `hitstop` | dur, golpe, alvo, x, y | `total_hitstops` do game feel |
| `combo` | slot (quem SOFRE), n | `combo_contra` subiu (2, 3...) |
| `tell` | slot, tell, modo?, papel?, revertido?, plano?, rotulo? | `brain.tell_atual` novo |
| `plano` | slot, plano, rotulo | `brain.plano` trocou |
| `virada` | slot (novo líder) | a mesma regra da legenda (histerese 5%, a cada 0,25 s de jogo, depois de 3 s) |
| `ko` | vencedor, perdedor, empate, x, y | `round_finalizado` virou verdade |

### Eventos da revisão 3 (o que o render acendia e a v1 não dizia)

Tirados das **listas de VFX que o motor cria** (`impact_flashes`,
`magic_clashes`, `block_effects`, `magic_vfx.explosions`, `textos` e as cinco
do `MovementAnimationManager`) e do **último estado de cada projétil**. A sonda
continua só LENDO: reconhece o que já viu numa lista pela identidade do
objeto, lembrada por `weakref` (não prolonga a vida de nada; um `id`
reciclado conta como objeto novo), e o que já existia antes do primeiro passo
é linha de base, não evento. Em ordem de impacto visual:

| tipo | campos | de onde sai |
|---|---|---|
| `projetil_fim` | id (da trilha), objeto (`projetil`, `projetil_arma`, `orbe`), dono (o de agora, depois de refletido), motivo, x, y, elemento?, alvo? (`p1`/`p2`), alvo_objeto? (id da trap/summon), defesa? | a trilha que voava no passo anterior e não voa neste (sai no passo `i1 + 1`, uma vez por trilha) |
| `explosao` | origem (`impacto` = a `DramaticExplosion` do acerto de projétil, com o elemento; `area` = o flash "explosion" do timer, do raio de explosão e do meteoro, com a cor), x, y, tamanho, elemento?, cor?, projetil? | objeto novo em `magic_vfx.explosions` ou flash `explosion` novo |
| `choque` | origem (`projeteis` ou `armas`), x, y, cor1, cor2, projeteis? (as duas trilhas) | `MagicClash` novo; `projeteis` quando trilhas acabaram no ponto (`_executar_clash_magico`), senão é o choque de armas (`efeito_clash`) |
| `refletido` | id, de, para, x, y | o dono da MESMA trilha mudou entre dois passos (`combat.refletir_projetil`); o `dono` fixo da trilha continua o primeiro |
| `texto` | texto_id, texto, estilo, cor, x, y, valor?, cor_base?, slot?, execucao?, acumulado? | `FloatingText` novo em `sim.textos`; `acumulado` = o número que SOMOU no texto que já estava na tela (hit no mesmo alvo em < 0,35 s), com o mesmo `texto_id` |
| `movimento` | slot, gatilho, vfx[], x, y, dir?, intensidade?, dash? | os VFX de movimento que nasceram no passo, UM evento por lutador |

**`motivo` do `projetil_fim`**, na ordem em que o motor decide
(`simulacao._atualizar_projeteis`; o primeiro sinal que bate vence):

| motivo | o sinal |
|---|---|
| `choque` | `MagicClash` novo perto do ponto (o choque roda ANTES de o projétil andar) |
| `explodiu` | o timer de explosão acabava neste passo (`explosion_timer <= dt`) |
| `expirou` | a vida acabava neste passo (`vida <= dt`; o `atualizar` do projétil roda antes de qualquer colisão) |
| `voltou` | estava retornando e chegou ao dono |
| `trap` | uma trap (que não é do dono) perdeu vida ou sumiu neste passo, com o projétil ao alcance |
| `acerto` | o flash `magic` (só o acerto de projétil o acende, na posição do projétil) casou com a trilha; o ORBE não acende flash e acaba por eliminação (vida, choque, trap ou colisão: o que sobra é acerto) |
| `bloqueado` | `defesa`: `escudo` (`BlockEffect` novo, o Orbital), `parry` (flash `clash` sem `MagicClash`), `dash` (o alvo em dash ao alcance: `_efeito_desvio_dash`) |
| `sumiu` | nenhum sinal: um caminho do motor que a sonda não conhece |

O ponto do fim é o final EXATO quando o objeto ainda existe (o alvo guarda o
projétil como fonte de impacto por ~1 s), o flash do acerto quando houver, e
senão a última amostra mais o último deslocamento (o motor anda antes de
colidir). O acerto em lutador ganha `ponto` (onde o projétil estava, como o
flash do render) e `projetil` (a trilha); projétil que nasce e acerta no MESMO
passo não tem trilha, e o acerto leva só o `ponto`.

**Conferido contra o motor** (28/09/2026): o motor INSTRUMENTADO (embrulhos em
`_executar_clash_magico`, `_resolver_colisao_projetil_traps`, nos três efeitos
de bloqueio, no `atualizar` de cada projétil e em `refletir_projetil`, que
chamam o original e só anotam) contra o que a sonda deduziu, em 29 lutas (as
5 de referência e 24 pares sorteados do banco, até 90 s cada): **865 de 865
fins com o motivo do motor** (355 acertos, 316 por validade, 96 choques, 91
desvios com dash, 3 traps, 3 explosões por timer, 1 escudo).
`voltou` e `parry` não apareceram. Antes de acertar a regra, 11 erros em 458:
10 orbes tomados por desvio (orbe não tem bloqueio) e um acerto cujo flash foi
para um orbe que orbitava ao lado do alvo. O teste
`RevisaoTresContraOMotorTests` repete a conferência numa luta de arremesso do
banco.

**`estilo` do `texto`**: `dano` (número; a `cor` é a final, com o degrau de
tamanho do `FloatingText.TIERS`, e a `cor_base` a do efeito), `execucao` (o
número roxo do bônus de condição >= 5), `fatal` (`FATAL!`; `execucao: true`
no roxo da execução), `cura` (`+N`), `clash` (`CLASH!`), `outro`. O `slot` é o
lutador mais perto (o texto nasce 30 a 50 px acima do alvo).

**`gatilho` do `movimento`**: `dash` (afterimage; `dash` = `dash_forward`,
`dash_backward`, `dash_lateral`), `knockback` (motion blur ou as linhas cor
`(255, 200, 150)`, com `dir` e `intensidade`), `recuperacao` (o flash do fim do
atordoamento), `aterrissagem` e `pulo` (a poeira com `z` cruzando os limiares
do motor), `corrida` (linhas de velocidade sem afterimage), `poeira`. `vfx`
lista o que nasceu: `afterimage`, `blur`, `linhas`, `poeira`, `recuperacao`.
Poeira, linhas e flash não guardam o dono: é o lutador mais perto (nascem na
posição dele).

**O palco (Godot)** desenha `explosao` (a paleta do elemento; a da área, a cor)
e `choque` (as duas cores, com tremor de câmera) com as texturas CC0 que a
biblioteca já tinha (`vfx_padrao.gd`), e o `acerto` por projétil acende no
`ponto`. `texto`, `movimento`, `projetil_fim` e `refletido` chegam às peças em
`evento()` e não pedem peça (arte nova não entrou na 16C). O `texto` fica
SÓ na timeline: decisão `palco-numeros-de-dano` do Adrian (29/09, "Não"),
nenhum número de dano na tela do palco; o teste do palco cobra que `texto`
não está em `EVENTOS_COM_VFX`. O validador
(`nucleo/timeline.gd` e `timeline_arquivo.validar`) confere os campos
obrigatórios, o `motivo` e o `ponto`; tipo desconhecido, `revisao` maior que a
conhecida e timeline antiga passam.

### `sons` (o formato da 16A)

A seção é a lista do `AnotadorDeAudio` da Onda 16A **sem tradução**:
`{"versao": 1, "relogio": "video", "itens": [{t, i, id, volume, pitch, pan?, x?}]}`.
O `i` (revisão 2) é o passo do motor em que o som foi pedido; o `t` continua o
do quadro que mostra esse passo (`ceil(i / 2) / 30`). Timeline de revisão 1
não tem `i`: o leitor usa `t × 60`.
Formato, relógio e mistura estão no contrato da 16A (`docs/palco/sons.md`).
Sai preenchida pelo gravador (`gravar_luta(timeline=...)`) e pelo
`gravar_timeline` fora do headless (os dois injetam o anotador); `null` quando
a luta rodou sem anotador (headless, ou `anotar_som=False`). No `duelo_00014`:
227 sons de 19 ids, 17,8 KB do JSON.

### `remapeamento` (corte de tédio e câmera lenta)

`trechos: [[inicio, duracao, velocidade], ...]` no relógio da gravação, em
ordem e sem sobreposição. `(inicio, duracao)` é exatamente o que
`highlights.planejar_corte_tedio` devolve; `velocidade` < 1 é câmera lenta do
palco (0,5 = metade), ausente vale 1. O palco renderiza o corte DIRETO: para
cada quadro de saída em `t_clipe`, `timeline_arquivo.tempo_na_gravacao(remap,
t_clipe)` diz o instante da gravação, e o passo é `t × 60` (interpolando entre
dois passos se quiser). `tempo_no_clipe` é o inverso, com a mesma conta de
`highlights.mapear_tempo`. No `duelo_00014` real, os trechos publicados dão
27,89 s de clipe, exatamente o `duracao_clipe` do `fight.json`.

## Em disco

- **`.timeline.json`**: UTF-8 sem espaço (`timeline_arquivo.salvar(doc,
  caminho)`). Godot: `JSON.parse_string(FileAccess.get_file_as_string(p))`.
- **`.gcpf`**: o MESMO JSON dentro do container de
  `FileAccess.open_compressed` do Godot 4 (`salvar(doc, caminho,
  compressao="zstd")`). O `open_compressed` **não lê gzip comum**; ele lê o
  formato do `FileAccessCompressed`: `"GCPF"`, modo (u32: DEFLATE 1, ZSTD 2,
  GZIP 3), tamanho do bloco (u32), total descomprimido (u32), o tamanho
  comprimido de cada um dos `total // bloco + 1` blocos (u32), os blocos
  comprimidos um a um e `"GCPF"` de novo no fim. O modo vem do cabeçalho do
  arquivo. Godot:

  ```gdscript
  var f := FileAccess.open_compressed(caminho, FileAccess.READ, FileAccess.COMPRESSION_ZSTD)
  var doc = JSON.parse_string(f.get_as_text())
  ```

  Blocos de 256 KiB (o Godot escreve em 4 KiB, mas lê o tamanho do cabeçalho;
  bloco grande comprime melhor porque cada bloco é comprimido sozinho).

**Medido (28/09/2026)**, `duelo_00014` (Valkyrie a Sábia x Beatrix das Sombras,
seed 529488362, Torre, 1080×1920, DIRETOR 5,5 m): luta de 25,95 s, vídeo de
29,43 s, **1766 passos**.

| formato | bytes | por segundo de vídeo |
|---|---|---|
| JSON | 987.072 | 33,5 KB |
| GCPF zstd (bloco 256 KiB) | 117.762 | 4,0 KB |
| GCPF zstd (bloco 64 KiB) | 125.961 | |
| GCPF zstd (bloco 4 KiB, o padrão de escrita do Godot) | 153.051 | |
| GCPF deflate | 169.585 | |
| GCPF gzip | 169.633 | |

Do JSON, 62% são os canais dos lutadores (612 KB), 21% objetos (210 KB), 7%
câmera. **Recomendação: o palco lê o `.gcpf` zstd** (8,4× menor, nativo). O
JSON fica para olhar e depurar.

**Conferido no Godot 4.7.2 desta máquina** (`E:\ferramentas\godot`, headless):
os quatro arquivos do `duelo_00014` abrem (`get_file_as_string` para o JSON,
`open_compressed` para os três GCPF) e o texto sai com o MESMO md5 do JSON
escrito pelo Python. Ler + parse: JSON 13 + 36 ms, zstd 19 + 37 ms, gzip 36 +
45 ms, deflate 84 + 65 ms. No Godot todo número do JSON vira float (`versao`
chega como 1.0): quem compara converte com `int()`. O teste opcional
`test_godot_abre_o_container_nativo` repete a conferência com `NF_GODOT`
apontando para o executável de console.

## A sonda só LÊ

`SondaTimeline` não chama `desenhar()`, `arena.limpar_colisoes()`,
`get_weapon_transform()` nem `animator.get_state()` (que criaria uma entrada),
não lê `brain.humor` num cérebro sem motor emocional (a property o criaria),
não instala nada no jogo (o `registro_eventos_dano` é da `SondaDeDano` do
gravador) e não prolonga a vida de nenhum objeto do jogo (lembra deles por
`weakref`). Tudo por `getattr` tolerante: fake de contrato não a derruba.

**Ordem no laço:** `on_frame` logo depois de `sim.update(dt)` e **antes** de
`sim.desenhar()`. O `desenhar()` esvazia `arena.colisoes_recentes`; chamada
depois dele, a sonda perde os impactos de parede comuns (os wall-splats
continuam, porque vêm de contador).

**Determinismo, medido:** hash de estado por passo (`timeline.hash_estado`:
corpo, timers, status, contadores, cooldowns, o RNG de cada lutador, mente,
mundo, câmera; e, no hash completo, o `random` global, as listas de VFX, o
relógio visual e o animador de arma) com e sem a sonda: **0 divergências em
2670 passos** no headless e **0 em 2670** no laço do gravador com `desenhar()`
a cada passo (540×960). A timeline sai idêntica em duas execuções da mesma
seed.

**Achado para a 16D:** rodar a luta **sem** `desenhar()` dá o mesmo hash da
luta em todos os 1766 passos do `duelo_00014`, o mesmo `random` global passo a
passo (o `desenhar()` não consome o `random`, então partículas e a variante
sorteada do som da 16A também não mudam) e custa **1,8 s contra 18,1 s** em
1080×1920 com a máquina livre (10 s contra 43 s com ela cheia). A única
diferença é `arena.colisoes_recentes`, que só o desenho esvazia (93 entradas
no fim da luta), e a sonda já lida com isso. Conferido de ponta a ponta: a
timeline que o GRAVADOR escreve do `duelo_00014` (desenhando, com som) e a do
`gravar_timeline` sem desenhar são iguais em trilhas, eventos e sons. O palco
pode simular sem desenhar.

**No gravador:** `gravar_luta(timeline=...)` com e sem a sonda dá o mesmo hash
por passo, os mesmos golpes, série de HP, eventos narrativos, métricas de
câmera e os mesmos 227 sons (a lista de som depende do `random` global: uma
sonda que consumisse um número a mudaria).

A sonda custa ~1 ms por passo (1,6 a 2,2 s num duelo de 29 s), com
`hash_estado` desligado (ele é só para teste).

**Revisão 3, medido (28/09/2026)** no `duelo_00014` (1080×1920, fora do
headless, sem desenhar, como o palco roda): **0 divergências de hash em 1766
passos** com e sem a sonda, e o `random` global no MESMO estado no fim; o
`hash_estado` passou a ver também as listas de movimento, as explosões e o
texto de cada `FloatingText`, que a sonda agora lê. A luta inteira levou 1,09 s
sem a sonda e 1,64 s com ela. O arquivo cresceu 5,5% (JSON 987.072 →
1.041.807 bytes; zstd 117.762 → 124.795): 68 `projetil_fim`, 47 `explosao`,
44 `texto`, 88 `movimento`, 3 `choque`. O gravador de verdade (desenhando a
cada passo, com o som) continua com o mesmo hash por passo, os mesmos golpes e
os mesmos sons com e sem a sonda, e a timeline dele e a do palco sem desenhar
têm os mesmos eventos (os testes pesados, `NF_RECORDING_GATE=1`).

## O que o render atual mostra e a v1 ainda NÃO expressa

Para ninguém perder nada na troca. "Derivável" = o palco reconstrói com o que
já está na timeline.

1. ~~Choque de projéteis~~: `choque` (revisão 3).
2. ~~Fim de projétil e o porquê, explosão no ponto de impacto~~:
   `projetil_fim` e `explosao` (revisão 3).
3. ~~Reflexão de projétil~~: `refletido` (revisão 3).
4. ~~Texto flutuante~~: `texto` (revisão 3). Continua: crítico só existe no
   corpo a corpo.
5. ~~Eventos de movimento~~: `movimento` (revisão 3). O motion blur e o flash
   de recuperação entram como `vfx`; a animação deles é do palco.
6. **Estado extra do animador de arma**: o lado da Adaga Gêmea que golpeia
   (`dagger_side`), o giro do mangual (`mangual_spin_speed`) e o tremor da arma
   no impacto (`weapon_anim_shake`, sorteado no `random` global). O ângulo e o
   lunge resultantes estão (`arma_ang`, `arma_lunge`).
7. **Arco de corte e telegraph** (`_desenhar_slash_arc`, o telegraph de golpe
   pesado do `AttackAnimationManager`): deriváveis de `golpe_fase`, `hb_ang`,
   `hb_larg`, `perfil_animacao.angulos` e `tier_impacto`. Atenção: o render de
   hoje calcula esse arco com o perfil do ESTILO enquanto o timer roda no do
   TIPO (o comentário em `simulacao.py` diz o contrário do que `entities.py`
   faz).
8. **Partículas, decalques e rastros**: partículas globais, sangue e cicatriz
   de elemento no chão, faíscas, flashes, ondas de choque, bolinhas dos orbes,
   rastro da arma e dos projéteis. Os GATILHOS estão nos eventos e nas
   trilhas (rastro = histórico de `arma_px/py` e `x/y`); a simulação das
   partículas é do palco.
9. **Piscada dos olhos**: hoje depende do relógio de parede e de `id(lutador)`
   (não é reprodutível). O palco decide, por slot e `t`.
10. **Pulsos e brilhos de relógio de parede** (beam, portal, glow de projétil,
    anel de super armor): o palco usa o `t` da timeline.
11. **Clima e luz ambiente da arena**: a v1 traz a lista `arena.efeitos` e a
    `cor_ambiente`; a simulação do clima é do palco.
12. **Orbital**: o render desenha a peça a 1× o raio, mas a hitbox é um setor
    de 1,5× o raio; a v1 grava a peça como o render (`comprimento_m`) e a
    hitbox à parte (`alcance_m`). Decidir qual o palco mostra.
13. ~~Posição do impacto de projétil~~: `acerto.ponto` (revisão 3).
14. **Fora da luta** (não é lacuna da timeline): o HUD do vídeo, identidade,
    veredito, legendas, voz e música continuam na edição em Python até a 16G;
    o HUD do jogo, o placar de série e o cartaz de vitória já estão desligados
    no vídeo.

## Onde a sonda está ligada

- **Gravador:** `fight_recorder.gravar_luta(timeline=CAMINHO)` e
  `python -m neural_fights.recording.fight_recorder ... --timeline CAMINHO`.
  A sonda roda logo depois de `sim.update(dt)` e **antes** de `sim.desenhar()`;
  no fim entra a lista do anotador em `sons` e o arquivo é gravado (`.gcpf` =
  zstd, senão JSON). O resultado leva `timeline` (o caminho), `timeline_bytes`
  e `timeline_passos`, nunca o documento (o gravador imprime o resultado numa
  linha JSON). Falha da timeline vira `erro_timeline` e não derruba o vídeo.
- **Sem desenhar (o palco):** `timeline.gravar_timeline(..., desenhar=False)`,
  o mesmo laço do gravador com o anotador de som. É o que a 16D chama.

Ainda não feito:

1. O repasse em `capture.gravar_uma`/`runner.gravar_confronto` (os vídeos de
   hoje não gravam timeline; o palco gera a dele sozinho).
2. O remapeamento na timeline gravada pelo gravador: o corte de tédio é
   decidido depois da gravação (`planejar_corte_tedio`); hoje quem o preenche
   é o palco, a partir dos eventos.
3. ~~Decidir com a 16A se o anotador passa a carimbar o som no passo~~:
   feito na revisão 2 (`ac270f2`) sem trocar o relógio — o som ganhou o `i` e
   o `t` de vídeo ficou, porque é ele que a mistura do mp4 e o corte de tédio
   usam.

## Versão

`versao: 1`. Campo, canal, evento, flag ou tabela NOVOS não mudam a versão (o
leitor ignora o que não conhece). Mudar o significado, a unidade ou o relógio
de algo que existe sobe a versão. `timeline_arquivo.validar(doc)` é o schema em
código: lista vazia = válido.

**`revisao`** conta as mudanças ADITIVAS dentro da v1, para quem quiser saber
o que um arquivo traz sem procurar campo por campo. O palco recusa `versao`
diferente de 1 e aceita qualquer `revisao`; arquivo sem o campo é revisão 1.

| revisão | data | o que entrou |
|---|---|---|
| 1 | 28/09/2026 (`3097a37`) | a v1 |
| 2 | 28/09/2026 (`ac270f2`) | `i` em cada item de `sons` |
| 3 | 28/09/2026 | eventos `projetil_fim`, `explosao`, `choque`, `refletido`, `texto`, `movimento`; `ponto` e `projetil` no `acerto` |
| 4 | 01/10/2026 | a bola da corrente nova: canais `bola_x/bola_y/bola_vx/bola_vy` e cabeçalho `arma.corrente` de quem tem bola; `luta.corrente_v2` |

**Paridade Python × Godot (revisão 4).** `palco/ferramentas/paridade_corrente.gd`
lê a timeline como o palco e escreve o que leu (canais interpolados, mão, bola
e a corrente que a peça desenharia); `random_builds/tests/test_palco_corrente_regressions.py`
refaz as contas em Python e compara: canais a 1e-9, mão e pontas a 0,1 mm (o
`Vector2` do Godot é float32).
