# A engine do Neural Fights, vista de quem vai desenhar

Auditoria feita em 06/10/2026, de madrugada, para servir de base ao **painel de anexo de sprites modulares** (decisão `builds/sprites-modulares-painel` = modular: "cada parte é um sprite estático e o Godot monta e anima").

Tudo aqui foi lido no código. Cada afirmação traz o arquivo e a linha onde está a verdade. Os caminhos são relativos a `E:\projetos\`.

Os números vêm de importar os catálogos de verdade, e não de comentários. Vários comentários estão velhos: "108 skills" em `neural_fights/models/constants.py:418` e "90/109" em `neural_fights/utils/palette.py:7`.

---

## 0. O mapa em uma tela

```
simulação (Python, neural_fights/)          palco (Godot 4.7, palco/)
  motor 60 Hz ── sonda ──> TIMELINE ───────>  palco.gd lê, nunca decide
                 recording/timeline.py        biblioteca.gd acha a peça pelo NOME do arquivo
                 (.json ou .gcpf zstd)        peças: lutador, arma, objeto, evento, arena, hud
```

- **A simulação não depende do palco.** O palco só lê a timeline (`palco/nucleo/palco.gd:2-4`; `palco/nucleo/timeline.gd:5`).
- **A ponte é a timeline v1, revisão 4.**
  - Quem escreve: `neural_fights/recording/timeline.py:75-88`.
  - Quem lê: `palco/nucleo/timeline.gd:11-15`.
  - Contrato completo: `docs/palco/timeline.md`.
  - O arquivo `.gcpf` é o container comprimido que o Godot abre nativo (`timeline.gd:85-128`).
- **Quem dispara o render:** `random_builds/builds/palco/` (`main.py palco render|ab|vitrine|editor`).
  - Imagem nova no `res://` precisa ser importada pelo Godot antes do render. Isso já é automático: `random_builds/builds/palco/godot.py:73` (`garantir_importado`, que roda `--headless --import`).
- **O palco ainda NÃO é o visual publicado.**
  - O duelo publicado continua no render em Python.
  - A troca espera o nó `palco-duelo-ab`. O Adrian aprovou tudo menos a corrente (`docs/sessoes/builds.md:69`).
  - Por isso, arte nova anexada aparece hoje na vitrine e no `palco render`/`ab`, e ainda não no vídeo publicado.

---

## 1. O lutador

### 1.1 O que ele é: uma bolinha vista de cima

- **É um círculo.**
  - Raio desenhado = `tamanho / 2`; raio de colisão = `tamanho / 4` (`neural_fights/recording/timeline.py:729-732`).
  - O `tamanho` vai de 1,4 a 2,2 m no gerador (`neural_fights/tools/gerador_database.py:504`).
  - No banco real vai de 1,51 a 2,04.
- **Escala do palco:** 100 px por metro (`palco/nucleo/util.gd:11`). Um lutador de 1,7 m tem raio de 85 px antes da câmera.
  - Na tela do vídeo (1080×1920), a bolinha ocupa de **88 a 408 px** de diâmetro (memória da Onda 16; `docs/palco/inventario_sprites.md`, "Tamanho").
- **Vista de cima.** O rosto ocupa a metade da frente da bolinha (`palco/biblioteca/lutadores/rosto.gd:48`).
  - `ang` é para onde ele olha: 0 = +x, sentido horário (`docs/palco/timeline.md:35-40`).
  - O rosto gira com `ang`. O corpo não gira: o brilho do corpo fica sempre no alto à esquerda da tela (`palco/biblioteca/lutadores/lutador_padrao.gd:153-164`).
  - O brilho do olho segue a mesma luz da tela, gire o rosto como girar (`rosto.gd:136-140`).
- **Pulo e squash.**
  - O corpo é desenhado em `(x, y − z)`, onde `z` é a altura do pulo.
  - O squash/stretch vem de `esc_x`/`esc_y`, aplicado ao corpo e ao rosto (`lutador_padrao.gd:115-120,153,169-173`).
  - Morto, `z = 0` e escala 1 (`lutador_padrao.gd:118-120`).
- **Não há mãos nem membros.** A arma nasce na "empunhadura", um ponto ao lado do corpo calculado pelo motor (`arma_gx/arma_gy`, `docs/palco/timeline.md:122-124`).

### 1.2 O que muda o visual de um lutador (cabeçalho da timeline)

Fonte: `neural_fights/recording/timeline.py:697-740`.

| campo | o que é | de onde |
|---|---|---|
| `nome`, `rotulo` | personagem e nome exibido | `personagens.json` |
| `classe` | ex. `"Berserker (Fúria)"` | `LISTA_CLASSES` |
| `cor` | cor do corpo, sólida, 0xRRGGBB (`cor_r/g/b`) | personagem |
| `cor_lado` | azul (p1) ou vermelho (p2): nome e HUD | `neural_fights/utils/config.py` |
| `cor_aura_classe` | cor da aura da classe; o palco hoje não desenha | `CLASSES_DATA[...]["cor_aura"]` |
| `tamanho`, `raio_corpo` | tamanho do corpo | personagem |
| `skills[]`, `arma{...}` | kit e arma | personagem e arma |

**O lutador NÃO tem campo de elemento.** O elemento só aparece de forma indireta:
- no rótulo da classe, como em "Piromante (Fogo)";
- no encantamento da arma.

Isso vale para o JSON do personagem e para a timeline (`neural_fights/data/personagens.json`; `random_builds/builds/nf_bridge/loader.py:304-308`).

Consequência para o painel: a variação "por elemento" de um LUTADOR não tem de onde sair hoje. Ver `CONTRATO_SLOTS.md` §2.2 e `PERGUNTAS.md` 5.

### 1.3 Classes: 16

Lista em `neural_fights/models/constants.py:387-413`; dados em `CLASSES_DATA`, `constants.py:594-823`.

| grupo | classes |
|---|---|
| físicos | Guerreiro (Força Bruta), Berserker (Fúria), Gladiador (Combate), Cavaleiro (Defesa) |
| ágeis | Assassino (Crítico), Ladino (Evasão), Ninja (Velocidade), Duelista (Precisão) |
| mágicos | Mago (Arcano), Piromante (Fogo), Criomante (Gelo), Necromante (Trevas) |
| híbridos | Paladino (Sagrado), Druida (Natureza), Feiticeiro (Caos), Monge (Chi) |

- **O que difere entre as classes é jogo, não visual:** vida, mana, força, velocidade, giro, kit (`constants.py:594-823`).
- **O único dado visual da classe é `cor_aura`** (`constants.py:608…821`), que o render atual não usa mais: só a transformação desenha halo (`neural_fights/simulation/simulacao.py:5109-5117`).
- **Como o palco procura a classe:** pelo nome com e sem parênteses: `classes/berserker_furia` e depois `classes/berserker` (`palco/nucleo/biblioteca.gd:92-98`).

### 1.4 Personagens

- **Base de runtime:** `%LOCALAPPDATA%\neural-fights\personagens.json`, com **106 personagens**. Ela tem prioridade sobre os 64 do `neural_fights/data/personagens.json` (`neural_fights/data/database.py:57-63`).
- **Campos visuais:** só `cor_r/g/b` e `tamanho`. Não há campo de imagem.
- **A arte de IA que existe** (`character_image.png` das gerações) mora em `random_builds/outputs/generation_*/`. Ela é a capa do vídeo, não uma peça do palco.

### 1.5 Os 12 elementos e as paletas

- **Paletas:** `neural_fights/utils/palette.py:23-118` (`ELEMENT_PALETTES`). A cópia do palco está em `palco/nucleo/util.gd:15-29`.
- **Os 12:** FOGO, GELO, RAIO, TREVAS, LUZ, NATUREZA, ARCANO, CAOS, SANGUE, VOID, TEMPO, GRAVITACAO, mais um DEFAULT cinza.
- **Estrutura de cada paleta:**
  - `core`: o centro quente;
  - `mid[3]` e `outer[3]`: os anéis;
  - `spark`: a faísca;
  - `glow`: o halo.
- **Lista canônica:** `neural_fights/core/combat.py:31-46` (`ELEMENTOS_MAGICOS`).

| elemento | mid[0] | glow |
|---|---|---|
| FOGO | #FFB432 | #FF6400 |
| GELO | #C8F0FF | #64C8FF |
| RAIO | #FFFF96 | #9696FF |
| TREVAS | #640096 | #640096 |
| LUZ | #FFFFDC | #FFFFC8 |
| NATUREZA | #64FF64 | #64FF64 |
| ARCANO | #DC96FF | #C864FF |
| CAOS | #FF6464 | #FF64FF |
| SANGUE | #DC3232 | #C80000 |
| VOID | #320064 | #320064 |
| TEMPO | #D2C3FF | #B4A0FF |
| GRAVITACAO | #8C6EFF | #6E50E6 |

**Atenção, há dois vocabulários de "elemento":**
- O das skills e paletas está em MAIÚSCULAS (`FOGO`).
- O dos 12 **encantamentos** de arma usa outra lista (`constants.py:237-333`): Chamas→Fogo, Gelo, Relâmpago→Raio, Veneno→Natureza, Trevas, Sagrado→Luz, Velocidade→Vento, Vampirismo→Sangue, Crítico→Precisão, Penetração→Força, Execução→Morte, Espelhamento→Arcano.
  - "Vento", "Precisão", "Força" e "Morte" não são elementos de paleta.

---

## 2. Os estados do lutador (o que EXISTE de verdade)

O motor não tem uma "máquina de estados de animação" com parado/andando/atacando. O que chega ao palco a cada passo (60 por segundo) são **canais** e **bits**. A lista completa dos canais está em `palco/nucleo/timeline.gd:38-44` e `docs/palco/timeline.md:99-160`.

### 2.1 Os 18 bits de `flags`

Fonte: `neural_fights/recording/timeline.py:98-117`. Acrescentar bit no fim não muda a versão.

| bit | flag | o palco desenha hoje (`lutador_padrao.gd`) | peça da biblioteca que ele já procura |
|---|---|---|---|
| 0 | atacando | contorno branco, mais grosso (189-191) | — |
| 1 | morto | rosto "morto", corpo no chão, arma caída (116-120,176-177) | — |
| 2 | atordoado | contorno amarelo + 3 estrelas girando (186-188,235-238) | `lutadores/estados/atordoado` |
| 3 | congelado | corpo puxado para azul-gelo (143-144) | `lutadores/estados/congelado` |
| 4 | invencivel | pisca a cada 2 quadros (125-126) | — |
| 5 | canalizando | nada no corpo (o efeito `canal` cuida) | `lutadores/canais/<skill>` |
| 6 | adrenalina | contorno vermelho pulsando (195-198) | `lutadores/estados/adrenalina` |
| 7 | agarrado | nada | `lutadores/estados/agarrado` |
| 8 | dash | nada (o evento `movimento` cuida) | — |
| 9 | intangivel | corpo a 45% de opacidade (123-124) | — |
| 10 | super_armor | anel dourado (216-217) | `lutadores/estados/super_armor` |
| 11 | bloqueando | arco de escudo na frente (219-220) | `lutadores/estados/bloqueando` |
| 12 | tempo_parado | nada | `lutadores/estados/tempo_parado` |
| 13 | dormindo | "z z" subindo (240-244) | `lutadores/estados/dormindo` |
| 14 | transformado | aura fina na cor do lado (148-150) | `lutadores/transformacoes/<skill>` |
| 15 | lancado | nada | — |
| 16 | oculto | não desenha nada, nem nome nem arma (110, `palco.gd:377,406`) | — |
| 17 | no_ar | nada (o `z` já levanta o corpo) | — |

Além dos bits, o canal `escudo > 0` vira a bolha `lutadores/estados/escudo_bolha` (`lutador_padrao.gd:69-70,211-214`).

### 2.2 As 24 expressões (canal `expr`): o "estado" que muda olhos e boca

- **Fonte:** `neural_fights/recording/timeline.py:121-126` = `neural_fights/effects/character_flair.py:636`. Há teste cobrando que as duas listas são iguais (`tests/test_timeline_palco_regressions.py:406-413`).
- **Lista:** neutro, focado, glacial, determinado, furia, berserk, confiante, animado, euforico, extase, panico, nervoso, desespero, tedio, tristeza, morto, tonto, dor, esforco, firmeza, alerta, confuso, limite, concentrado.
- **A expressão já é a "cara do estado".** O motor escolhe por prioridade (`character_flair.py:42-89`):
  1. **morto** → `morto`
  2. **atordoado** → `tonto`
  3. **flash de dano** → `dor`
  4. **canalizando** → `concentrado`
  5. **tell ativo:**
     - instinto/desvio/parry → `alerta`;
     - hesitação → `confuso`;
     - punição/iniciativa/dash tático/plano ofensivo → `determinado`;
     - agarrão → `esforco`;
     - wall splat → `dor`;
     - isca → `confiante`;
     - recuperar → `alerta`.
  6. **atacando** → `esforco`
  7. **ação BLOQUEAR** → `firmeza`
  8. **adrenalina** → `limite`
  9. **humor da IA** (15 humores → expressão, `character_flair.py:91-107`).
- **Como o palco desenha hoje:** `palco/biblioteca/lutadores/rosto.gd:365-437`, uma linha por expressão.
  - As peças CC0 do Kenney ficam em `lutadores/rosto/*.png` (14 peças): 7 olhos, 4 sobrancelhas, 3 bocas.
  - Os extras são desenhados por código: espiral, boca ondulada, suor, lágrima, veia, brilho e faíscas.
- **Piscar** é decisão do palco, pelo tempo de jogo (`rosto.gd:368`).

### 2.3 Golpe: 5 fases (canais `golpe_fase` + `golpe_p`)

- **Fases** (`timeline.py:95`): preparo (anticipation), golpe (attack), impacto, seguimento (follow), recuperação. O valor 0 quer dizer sem golpe.
- **O palco leva a animação `golpe` da peça da ARMA ao progresso de cada fase** (`palco.gd:474-502`). As marcas `preparo|golpe|impacto|seguimento|recuperacao` ficam na `Anim` (`palco.gd:29-32`).
- **O lutador em si não tem pose de golpe:** só o contorno branco (`atacando`) e a expressão `esforco`.

### 2.4 As outras listas que existem

| lista | itens | fonte |
|---|---|---|
| ação da IA (`acao`) | 16: APROXIMAR, APROXIMAR_LENTO, ATAQUE_RAPIDO, BLOQUEAR, CIRCULAR, COMBATE, CONTRA_ATAQUE, DESVIO, ESMAGAR, FLANQUEAR, FUGIR, MATAR, NEUTRO, POKE, PRESSIONAR, RECUAR | `neural_fights/ai/brain.py` (`acao_atual = ...`) |
| tells | 14: instinto, desvio, punicao, hesitacao, dash_tatico, iniciativa, plano, parry, burst, agarrao, enlace, obstaculo, wall_splat, clinch | `brain.py:1079-5382`; `core/entities.py:3792`; `simulation/simulacao.py:3410-4001` |
| planos de luta | 11: PRESSIONAR, BAITAR_E_PUNIR, MANTER_ZONA_MORTA, LEVAR_PARA_PAREDE, CACAR_JANELA_SKILL, RECUPERAR, QUEBRAR_GUARDA, CORTAR_FUGA, TROCAR_GOLPES, ACABAR, ESMAGAR_NA_PAREDE | `neural_fights/ai/plano_de_luta.py:102-186` |
| desfecho do agarrão | 5: ARREMESSO, JOELHADA, EMPURRAO, REVERSAO, ESCAPE | `neural_fights/core/agarrao.py:22` |
| movimento (gatilho) | 7: dash, knockback, recuperacao, aterrissagem, pulo, corrida, poeira | `timeline.py:152` |
| fim de projétil | 8: choque, explodiu, expirou, voltou, trap, acerto, bloqueado, sumiu | `timeline.py:147` |
| tier do impacto | 4: light, medium, heavy, colossal | `timeline.py:132` |
| estados do orbe | 3: orbitando, carregando, disparando | `timeline.py:128` |

**Ação, tell e plano não mudam o desenho sozinhos.** Entram pela expressão (§2.2) e, no caso do plano, pelo rótulo do HUD.

### 2.5 Os estados que o Adrian citou, um por um

| pedido | existe? | como chega ao palco |
|---|---|---|
| parado | derivável | `vx`, `vy` ≈ 0 e `golpe_fase` = 0. Não é flag |
| andando / correndo | derivável | `vx`, `vy`; o evento `movimento` com gatilho `corrida` |
| atacando | sim | flag 0 + `golpe_fase` 1..5 |
| defendendo | sim | flag 11 `bloqueando`; eventos `bloqueio` e `parry` |
| tomando dano | sim | canal `flash` (`flash_cor`) + eventos `acerto` e `dano`; expressão `dor` |
| atordoado | sim | flag 2; expressão `tonto` |
| agarrão / agarrado | sim | flag 7 (os dois lados); tells `agarrao`, `enlace` e `clinch`; eventos `agarrao` e `agarrao_desfecho` (5 modos) |
| arremessado | sim | flag 15 `lancado`; desfecho ARREMESSO; `movimento` com gatilho `knockback` |
| carregando skill | sim | flag 5 `canalizando` + o efeito `canal` (só as 3 skills CHANNEL); expressão `concentrado` |
| usando skill | sim, como instante | evento `skill` (slot, nome, tipo_skill, elemento) |
| caído | só como morto | flag 1 `morto`. Não existe "derrubado e levanta" |
| derrota | sim | flag 1 + evento `ko` (perdedor) |
| vitória | derivável, não é estado | canal global `fim` = 1 e o lutador vivo; evento `ko.vencedor`. Não existe pose de vitória no motor: a tela de vitória do jogo é texto (`simulacao.py:6652`) |
| entrada | **não existe** | nenhuma animação de entrada no motor nem na timeline |

**Estados novos das ondas 10 a 16** que já estão na lista acima:
- agarrão, com 5 desfechos e reversão (Onda 10);
- `lancado` e `wall_splat`;
- `plano` e os tells de plano;
- `burst`, `enlace` e `clinch`;
- a bola da corrente (revisão 4);
- `projetil_fim`, `explosao`, `choque`, `refletido` e `movimento` (revisão 3);
- `no_ar` e `oculto` (portal).

---

## 3. Armas

- **8 tipos** (`neural_fights/models/constants.py:111-202`): Reta, Dupla, Corrente, Arremesso, Arco, Orbital, Mágica e Transformável.
- **54 estilos** (`neural_fights/tools/gerador_database.py:79-166`). A Reta tem 12; os outros tipos têm 6 cada. A base real (`%LOCALAPPDATA%\neural-fights\armas.json`, 119 armas) usa exatamente esses 54.

| tipo | estilos |
|---|---|
| Reta | Espada Longa, Espada Curta, Montante, Katana, Sabre, Lança, Alabarda, Machado, Martelo, Maça, Foice, Claymore |
| Dupla | Adagas Gêmeas, Sai, Kamas, Garras, Tonfas, Facas Táticas |
| Corrente | Kusarigama, Mangual, Chicote, Corrente com Peso, Meteor Hammer, Rope Dart |
| Arremesso | Facas de Arremesso, Shuriken, Chakram, Machados de Arremesso, Kunai, Bumerangue |
| Arco | Arco Curto, Arco Longo, Arco Composto, Besta Leve, Besta Pesada, Arco Élfico |
| Orbital | Escudo Orbital, Drones de Combate, Orbes Místicos, Lâminas Orbitais, Cristais Flutuantes, Sentinelas |
| Mágica | Espadas Espectrais, Runas Flutuantes, Tentáculos Sombrios, Cristais Arcanos, Lanças de Mana, Chamas Espirituais |
| Transformável | Espada-Lança, Espada Extensível, Chicote-Espada, Arco-Lâminas, Bastão Segmentado, Machado-Martelo |

**Visual por arma:**
- **`cor`** da arma (`timeline.py:775-776`).
- **`raridade`**, com 6 níveis. Cinco deles têm `efeito_visual`: brilho_leve, brilho_medio, particulas, aura_dourada e chamas_miticas (`constants.py:10-102`).
- **Encantamentos**: 12 (`constants.py:237`).
- **`arquetipo_animacao`**, com 5 valores: corte, estocada, esmagamento, chicote e puxada (`neural_fights/effects/weapon_animations.py:744`).

**Onde a arma fica presa:**
- **Na empunhadura.** O palco põe a origem da peça na empunhadura e gira para a ponta. A ponta é o alcance REAL da hitbox, e o palco estica a peça até ela (`palco.gd:400-427`; `palco/nucleo/util.gd:84-99`).
- **Desenho:** apontando para +x, com `comprimento_ref` px da mão à ponta (`palco/nucleo/peca.gd:20-25`).

**Casos especiais:**
- **Dupla:** o palco instancia a MESMA peça uma segunda vez, espelhada na outra mão (`palco.gd:245-252,448-471`).
- **Corrente:**
  - Peça própria `armas/tipos/corrente.tscn`, que desenha os elos por código entre a mão e a bola.
  - A cabeça é uma de 6: `bola_espinhos`, `martelo`, `peso`, `ponta`, `foice`, `dardo`.
  - O material é um de 3: `elos`, `couro`, `corda`.
  - Fontes: `timeline.py:245-250`; `docs/palco/COMO-EDITAR.md` §3, "A corrente".
- **Orbital:** desenhado no alcance real de 1,5× o raio (`palco.gd:411-417`).
- **Arremesso e Arco:**
  - O que voa é o objeto `projetil_arma`, com forma faca, flecha, shuriken ou chakram (`docs/palco/timeline.md:203`).
  - O arco tem o canal `arma_puxada` para a corda (`palco/biblioteca/armas/arma_padrao.gd:124-138`).
- **Mágica:** os orbes são objetos `orbe` com estado orbitando, carregando ou disparando (`timeline.py:1216-1220`, `1262-1272`).
- **Transformável:** a forma 2 não tem dado na timeline. O inventário marca esse item como bloqueado (`docs/palco/inventario_sprites.md`).

**Como o palco resolve:**
- Ordem: `armas/estilos/<estilo>` > `armas/tipos/<tipo>` > `armas/_padrao` (`palco/nucleo/biblioteca.gd:84-89`).
- O padrão desenha uma silhueta por tipo (`palco/biblioteca/armas/arma_padrao.gd:60-83`).

---

## 4. Skills

O catálogo é `SKILL_DB`, em `neural_fights/core/skills.py:24-810`. São **118 skills** (119 chaves menos "Nenhuma").

| tipo | qtd | o que aparece na tela | peça que o palco procura hoje |
|---|---|---|---|
| PROJETIL | 34 | objeto `projetil` (x, y, r, ang) | `efeitos/skills/<skill>` > `objetos/projetil/<elemento>` > `objetos/projetil/_padrao` |
| AREA | 33 | objeto `area` (raio, aviso/ativo) | igual, com `area` |
| BUFF | 26 | efeito `buff` no lutador (+ escudo) | `lutadores/buffs/<skill>` |
| BEAM | 6 | objeto `beam` (de/até, largura) | `objetos/beam/<elemento>` (a Oficina recusa beam) |
| DASH | 6 | evento `movimento` com gatilho `dash`; só o Portal Arcano cria objeto `portal` | `efeitos/skills/portal_arcano` |
| SUMMON | 4 | objeto `summon` (Fênix, Treant, Espírito, Cópia Sombria) | `efeitos/skills/<skill>` > `objetos/summon/...` |
| TRAP | 3 | objeto `trap` (muro) | `efeitos/skills/<skill>` > `objetos/trap/...` |
| TRANSFORM | 3 | efeito `transformacao` + flag 14 | `lutadores/transformacoes/<skill>` |
| CHANNEL | 3 | efeito `canal` + flag 5 | `lutadores/canais/<skill>` |

**Fontes dessa tabela:**
- objetos: `timeline.md:197-215`;
- buscas: `palco/nucleo/biblioteca.gd:101-107`;
- peças de lutador: `lutador_padrao.gd:59-103`;
- portal: `neural_fights/core/entities.py:1370`.

**Elementos das skills:**
- 100 skills têm `elemento`. As outras 18 não têm e caem no cinza DEFAULT.
- Contagem por elemento: FOGO 11, RAIO 11, NATUREZA 11, GELO 10, LUZ 10, ARCANO 10, TREVAS 8, TEMPO 7, SANGUE 6, GRAVITACAO 6, CAOS 6, VOID 4.

**Toda skill tem `cor`.**

**O instante do cast** é o evento `skill`. O palco procura `eventos/skill_<elemento>` > `eventos/skill` (`biblioteca.gd:110-118`). Não procura por nome de skill.

**`KIT_POOLS`** (`constants.py:429-556`): cada classe tem 4 papéis (CONTROLE, ZONA, MOBILIDADE, PICO). Cobre 109 skills; as 9 restantes estão em `SKILLS_FORA_DE_ROTACAO` (`constants.py:561-571`).

**Status, as marcas que as skills deixam no alvo:**
- São 29, em `neural_fights/core/status_runtime.py:117-147` (`STATUS_VISUAL`).
- Cada um tem cor, glifo, estilo (anel, tint ou partícula) e prioridade.
- O palco desenha só o dominante, como anel ou partículas (`lutador_padrao.gd:221-233`), e procura `lutadores/status/<status>`.

---

## 5. Efeitos, objetos, arenas, HUD

### Eventos com efeito na tela

- **São 19** (`palco/nucleo/timeline.gd:19-25`): acerto, dano, cura, bloqueio, parry, esquiva, desvio, dash, parede, wall_splat, ko, escudo_quebrou, skill, agarrao_desfecho, obstaculo, explosao, choque, movimento e projetil_fim.
- **Ordem de busca** (`biblioteca.gd:110-118`): `eventos/<tipo>_<variante>` > `<tipo>_<elemento>` > `<tipo>_<tier>` > `<tipo>` > `_padrao`.
- **De onde sai a variante** (`palco.gd:585-598`):
  - `acerto`: crítico, `projetil_arma` ou o arquétipo da arma;
  - `agarrao_desfecho`: o modo;
  - `movimento`: o gatilho;
  - `projetil_fim`: o motivo.
- **Desenho padrão:** máscaras CC0 tingidas (`palco/biblioteca/efeitos/eventos/vfx_padrao.gd`).
- **Camada:** o KO vai para o chão, abaixo dos lutadores (`palco.gd:582-584`).
- **O `texto` (número de dano) NÃO vai à tela,** por decisão `palco-numeros-de-dano` = Não (`docs/palco/timeline.md:316-322`).

### Objetos

- **São 8 tipos:** projetil, projetil_arma, orbe, area, beam, summon, trap e portal (`timeline.gd:50-59`).
- **Camada:** area, trap e portal ficam na camada do chão; o resto, na camada de objetos (`palco.gd:529`).
- **Arte atual:** cenas CC0 por tipo × elemento (12 × projétil, área e beam = 39 cenas, com os `_padrao`), em `palco/biblioteca/efeitos/objetos/`. Usam o `objeto_cc0.gd`, com máscaras brancas SEMPRE tingidas pela paleta.

### Arenas

- **São 20** (`neural_fights/core/arena.py:53`).
- **17 temas:** castelo, caverna, classico, cyberpunk, esporte, floresta, gelo, gotico, inferno, japones, labirinto, medieval, praia, romano, ruinas, scifi e vulcao.
- **22 tipos de obstáculo:** altar, arvore, barril, caixa, console, cripta, cristal, fogo, gelo, lapide, lava, nucleo, ossos, painel, palmeira, parede, pedra, pilar, pilar_quebrado, rocha, tapete e trono.
- **11 climas** (`efeitos_especiais`): calor, chamas, chuva, escorregadio, gritos, luzes_piscando, neblina, neon, neve, particulas_fogo e poeira.
- **Ordem de busca:** `arenas/<slug do nome>` (por exemplo, `salao_da_torre`) > `temas/<tema>` > `_padrao` (`biblioteca.gd:142-147`).
- **Desenho padrão:** chão de pedra CC0 + paredes + obstáculos por código (`palco/biblioteca/arenas/arena_padrao.gd:1-20`). O obstáculo quebra pelo evento `obstaculo`.

### HUD

- **Peça:** `hud/_padrao` (`biblioteca.gd:150-151`), feita por código. Mostra nome, vida com o "fantasma" do dano e o rótulo do plano (`palco/biblioteca/hud/hud_padrao.gd:1-15`).
- Só aparece com `--hud`.

---

## 6. Como o Godot desenha HOJE

### Camadas (ordem de baixo para cima)

Fonte: `palco/nucleo/palco.gd:34-42`.

```
Mundo/Arena  ->  Mundo/Solo (áreas, traps, portais, KO)  ->  Mundo/Lutadores
             ->  Mundo/Armas (+ rastro da arma)  ->  Mundo/Objetos  ->  Mundo/Efeitos
CanvasLayer Rotulos (nomes)  ->  CanvasLayer Tela (HUD, barras de cinema, clarão)
```

**Dentro do lutador padrão** (`lutador_padrao.gd:109-205` + `_sincronizar_pecas` 59-103):
1. sombra de contato;
2. aura da transformação;
3. corpo (cel de 2 tons + brilho);
4. rosto (no quadro do olhar);
5. contorno;
6. marcas de status.

As peças `estados/status/buffs/canais/transformacoes` entram como **filhas** do lutador:
- posição `(0, −z)`;
- escala `raio_px / raio_ref`;
- **sem girar com o olhar.**

### Como a biblioteca acha uma peça

Fonte: `palco/nucleo/biblioteca.gd:1-161`.

- **Pelo nome do arquivo, sem catálogo.** Cada pedido tem uma lista de candidatos, do mais específico ao mais geral; o primeiro `.tscn`/`.scn` que existir vence.
- **Os nomes passam por `UtilPalco.slug`:** sem acento, minúsculo, `_` no lugar de espaço e de parênteses (`util.gd:45-58`).
- **Reserva:** o último candidato é sempre `_padrao`. Se até ele faltar, entra a reserva embutida: um X magenta de propósito (`palco/nucleo/peca_reserva.gd:1-19`). Nada some calado.
- **Relatório:** o palco grava `pecas` (o arquivo escolhido em cada pedido) e `reservas` (`palco.gd:674-675`), lado a lado com o mp4.
- **Peças do lutador** (`biblioteca.gd:126-139`): `lutadores/<categoria>/<nome>` > `lutadores/<categoria>/_padrao`. Sem nenhuma das duas, fica o desenho por código.

### Âncora, escala e giro por categoria

| peça | origem (0,0) | escala | giro |
|---|---|---|---|
| lutador | centro do corpo no chão | `raio_corpo×100 / raio_ref` (`palco.gd:355`) | o lutador se desenha; o rosto gira com `ang` |
| arma | empunhadura (a mão) | comprimento real / `comprimento_ref` | aponta para a ponta |
| objeto | centro | `r×100 / raio_ref` (sem `atualizar`) | `ang` |
| evento | ponto do evento (o acerto vai para a borda do alvo que encara o autor) | — | `dir` |
| arena | mundo (metros×100) | — | — |
| HUD | tela 1080×1920 | escala com a tela | — |

Fontes: `peca.gd:1-44`; `palco.gd:521-616`.

### O formato que a arte do Adrian já usa: `folha_animada.gd`

Fonte: `palco/biblioteca/efeitos/folha_animada.gd`.

- **Uma imagem com 1 ou mais quadros:**
  - `ancora` em px do quadro;
  - `girar` com o ângulo;
  - `tamanho_m` (largura no mundo) ou `escala_raio` (× o diâmetro da hitbox);
  - `aditivo`;
  - `tingir` = `""` (as cores da arte), `"elemento"` ou `"#RRGGBB"`.
- **Serve de objeto e de evento.** Com 1 quadro, é exatamente uma **peça estática** que o Godot posiciona, gira e escala.
- **Cuidado com a arte colorida:** o `objeto_cc0.gd` sempre multiplica a textura pela paleta (`objeto_cc0.gd:1-14`). Arte colorida tem que ir pela `folha_animada` com `tingir = ""`.

### O que é `sprites_usuario/`

- Hoje é **só um `catalogo.json`**, escrito pelo Ateliê. **Nenhum `.gd` lê essa pasta.**
- O catálogo é por **animação do lutador inteiro**: `parado_direita`, `ataque_leve_esquerda`, … 26 slots com âncora `pes` (`palco/biblioteca/sprites_usuario/catalogo.json:3-33`).
- Esse formato é o oposto da decisão modular: visão de lado e quadro a quadro, contra uma bolinha vista de cima com peças estáticas.

---

## 7. O que já existe para reaproveitar (não refazer)

### Ateliê (app do celular)

- **Onde fica:** aba da ⚔️ Arena (`remoto/app/app.js:29`).
- **Arquivos:** `remoto/app/atelie.js`, a tela em `remoto/app/index.html:675-698` e as rotas em `remoto/api_http.py`:
  - `GET /api/atelie` (1238-1253);
  - `GET /api/atelie/arquivo/...` (1271-1279);
  - `POST /api/atelie/importar` (1321-1372).
- **O que faz:**
  - sobe PNG/JPG/WEBP de até 20 MB;
  - remove o fundo sozinho (transparente, liso ou xadrez);
  - corta em quadros (auto, grade ou tira);
  - espelha;
  - mostra prévias;
  - grava em `palco/biblioteca/sprites_usuario/<sujeito>/<nome>/<slot>.png/.json/.gif`.
- **Exige:** celular pareado + servidor com `--acoes`.
- **O que falta para o painel modular:**
  - escolher o slot de PARTE (hoje são slots de animação);
  - gravar onde o palco lê;
  - o fluxo de "substituir" (hoje devolve 409 sem saída na tela, `api_http.py:1362-1363`).
- **Atenção:** `remoto/app/oficina.js` NÃO é de sprites. É a "Oficina do Codex".

### Motor sem interface

`painel/sprites/importar.py` (`processar`, `salvar`, `espelhar`) e `painel/sprites/fundo_auto.py`. É o que o Ateliê usa.

### Oficina do painel (PC)

- **Arquivo:** `painel/paginas/oficina.py`.
- **Exportação:** `painel/sprites/exportar.py` já escreve o formato que o Godot lê:
  - `.png` + `.json` + `.tscn` com a `folha_animada.gd` ou a `peca.gd`;
  - a linha de licença em `palco/biblioteca/LICENCAS.md`.
- **Destinos que ela sabe montar** (`exportar.py:167-180`): `armas/estilos/<estilo>`, `efeitos/skills/<skill>`, `efeitos/eventos/<tipo>[_<tier>]` e `efeitos/objetos/<tipo>/<elemento>`.
- **Recusa** (`exportar.py:183-216`): exportação sem prova de origem, beam, e arma com mais de 1 quadro.

### Achado: arte do Adrian que não aparece em lugar nenhum

O **`corpo_bolinha`** e o **`classe_berserker`** que ele fez em 02/10 foram exportados como **skill** (`palco/biblioteca/efeitos/folhas/corpo_bolinha.json:3-5`; `palco/biblioteca/efeitos/skills/corpo_bolinha.tscn`).
- O palco só procura `efeitos/skills/<nome da skill>`, e não existe skill chamada "corpo bolinha" nem "classe berserker".
- Essas duas artes **nunca aparecem na luta**.
- É exatamente o buraco que o painel de slots fecha: o lugar certo para cada coisa.

### Esteira de sprites

- `esteira_sprites/` está **desligada**: `ESTEIRA_LIGADA = False` (`esteira_sprites/__main__.py:122`) e `FOLHAS_POR_IA = False` (`:69`).

### Inventário dos 513

- **Arquivo:** `docs/palco/inventario_sprites.json`, com 25 campos por item, incluindo `presenca`, que mede quanto cada coisa aparece em 95 lutas.
- **Grupos:** personagens 49, armas 94, habilidades 212, efeitos 68, arena 85, HUD 4, base 1.
- **As marcações do Adrian** (falta/esteira/pronto/pular) estão em `%LOCALAPPDATA%\neural-fights\biblioteca\estado\237c51f24a0147f8bfd605374665fc02.json`: 18 marcações, 7 prontas.
- **O que está desatualizado:** o inventário foi feito ANTES do commit `4a2c74e`, que passou a procurar `lutadores/estados|status|buffs|canais|transformacoes`. Por isso ele ainda diz `palco_procura: false` nos estados.
- **Uso no manifesto:** a medição de presença é boa para ordenar os slots por importância.

### Tarefa paralela

O **pedido `pedido-5f240534`** (o mesmo pedido, delegado ao Codex pelo Grimório) está "rodando" em `E:\projetos-wt\codex-pedido-5f240534`. Ele pode escrever em `docs/**` e `remoto/**`. Às 04:18 ainda não tinha mudado nada. Quem orquestra precisa juntar as duas frentes.
