# Contrato de slots: o lugar de cada coisinha

Este documento é a proposta do **manifesto de slots**. É ele que guia o painel de anexo e é ele que o Godot lê.

- A engine está descrita em [`ENGINE.md`](ENGINE.md).
- Um exemplo real gerado da engine está em [`slots_exemplo.json`](slots_exemplo.json).
- As decisões que são só do Adrian estão em [`PERGUNTAS.md`](PERGUNTAS.md).

**Base:**
- Decisão `builds/sprites-modulares-painel` = **modular**: cada parte é um sprite **estático** e o Godot monta e anima.
- Decisões que continuam valendo:
  - vista de cima, tudo apontando para +x (`sprites-ia-formato`, `sprites-ia-estilo`);
  - contorno `#14141A`, cel de 2 tons, luz do alto à esquerda (`docs/palco/inventario_sprites.json`, "convencoes").

---

## 1. As regras de ouro (o que o Adrian precisa saber para desenhar)

1. **Toda imagem é parada.** PNG com fundo transparente, ou fundo liso que o painel recorta. O Godot cuida de mexer: posição, giro, escala, piscar, tremer, sumir.
2. **Um gabarito por grupo.** Cada parte é desenhada no MESMO quadrado das outras partes do grupo, já no lugar certo. Por isso não existe âncora para acertar: empilhou, encaixou.
3. **Tudo olha para a direita (+x), visto de cima.**
4. **Faltou a imagem, nada some.** Cada slot tem uma cadeia de reserva que termina no desenho de hoje.

### Gabaritos

| grupo | quadrado | onde fica o quê |
|---|---|---|
| lutador (todas as partes) | **1024×1024** | centro (512, 512) = centro da bolinha; o corpo é um círculo de **diâmetro 512 px** (raio 256), olhando para +x. Sobra uma margem de 256 px em volta para chapéu, capa, orelha, aura |
| camadas de estado (status, buff…) | 1024×1024 | o mesmo gabarito do lutador: um anel em volta do corpo é desenhado num raio de ~300 px |
| arma | **1024×256** | a mão (empunhadura) na borda esquerda, na altura do meio; a ponta na borda direita. O Godot estica até o alcance real da hitbox |
| projétil, orbe, summon, trap, portal | 512×512 | centro = centro do objeto, apontando para +x; o diâmetro da hitbox ocupa a largura toda |
| área (chão e borda) | 512×512 | círculo da área = largura toda |
| feixe (beam) | 1024×128 (corpo, repete ao longo) + 256×256 (ponta) | +x é o sentido do feixe |
| evento (acerto, KO…) | 512×512 (KO 1024×1024) | centro = ponto do evento |
| arena: chão | 1024×1024 que se repete (3 m por repetição, como hoje) | — |
| arena: obstáculo | 512×512 visto de cima | a largura do obstáculo é a largura da imagem |
| HUD | 1024×128 por peça | — |

**De onde saem esses tamanhos:**
- A maior bolinha do vídeo tem 408 px (`docs/palco/inventario_sprites.md`, "Tamanho"). Com o corpo de 512 px no gabarito, o Godot nunca amplia a arte.
- A regra "nítida a 408 px" já é cobrada no rosto (`palco/biblioteca/lutadores/rosto.gd:68-70`).
- O chão repete a cada 3 m (`palco/biblioteca/arenas/arena_padrao.gd:13-14`).

---

## 2. O lutador em partes (a bolinha)

Nove partes, de baixo para cima. "Quadro" diz o que o Godot faz com a peça:
- **tela**: não gira, porque a luz do brilho é fixa na tela;
- **olhar**: gira com o ângulo `ang` para onde o lutador olha;
- **mundo**: fica no chão.

| z | parte | quadro | varia por estado? | níveis permitidos | tingir | papel |
|---|---|---|---|---|---|---|
| 0 | `sombra` | mundo (no chão, não sobe com o pulo) | não | comum | não | recomendado |
| 10 | `acessorio_costas` (capa, asas, aljava, cauda) | olhar | não | classe, personagem | não | recomendado por classe |
| 20 | `pele` (o corpo) | **tela** | não (o Godot faz o flash de dano, o gelo, o piscar e o fantasma) | comum, classe, personagem | **cor do personagem** no comum | **obrigatório** |
| 25 | `marcas` (cicatriz, pintura, tatuagem) | olhar | não | classe, personagem | não | opcional |
| 40 | `olhos` (o PAR, numa imagem) | olhar | **sim, as 24 expressões** | comum, classe, personagem | não | **obrigatório** (neutro) |
| 45 | `sobrancelhas` (o par) | olhar | sim, as 24 expressões | comum, classe, personagem | não | opcional |
| 50 | `boca` | olhar | sim, as 24 expressões | comum, classe, personagem | não | **obrigatório** (neutro) |
| 55 | `detalhe_rosto` (suor, lágrima, veia, faíscas, brilho) | olhar | sim, só as 9 que usam: panico, nervoso, desespero, limite, tristeza, furia, berserk, alerta, extase | comum | não | opcional |
| 60 | `acessorio_cabeca` (chapéu, elmo, capuz, faixa) | olhar | não | classe, personagem | não | recomendado por classe |

**Por que essas nove:**
- **Pele, olhos, boca e acessório** são o pedido literal do Adrian.
- **Sobrancelhas e detalhe do rosto** são o que o rosto de hoje já usa para ler as 24 expressões: 4 sobrancelhas Kenney e 7 extras desenhados por código (`rosto.gd:19-34,309-361`). Sem eles, fúria e tristeza ficam com a mesma testa.
- **Sombra** já existe no desenho de hoje (`lutador_padrao.gd:128-135`).
- **Acessório de costas** existe porque, visto de cima, o que fica atrás do corpo (capa, asas) precisa ficar ABAIXO da pele, e o chapéu ACIMA. Isso não cabe numa camada só.
- **Marcas** é a identidade do personagem sem trocar a pele inteira.
- **O acessório de classe já era o plano do motor:** "a identidade migra para o PROP" (`neural_fights/simulation/simulacao.py:5109-5112`).
- **O inventário de 01/10** já pedia 16 peças de classe (`docs/palco/inventario_sprites.md`, "classe").

**O que NÃO é parte do lutador:**
- **A arma** é um grupo próprio: o Godot a prende na empunhadura (§5.2).
- **As marcas de estado** (atordoado, queimando…) são camadas por cima, do grupo `camada_estado` (§5.1).
- **O contorno e o brilho** continuam por código, no estilo global (`palco/biblioteca/estilo.tres`). Se a pele trouxer contorno próprio, o painel desliga o do código, por um campo no `.json` da peça.

### 2.1 O eixo de estado do rosto: as 24 expressões, com 6 representantes

O motor já traduz "o que está acontecendo" em expressão (`neural_fights/effects/character_flair.py:42-89`): atordoado → tonto, apanhou → dor, canalizando → concentrado, atacando → esforço, bloqueando → firmeza… Por isso o eixo de estado de olhos, sobrancelhas e boca é a **expressão**, e não uma lista inventada.

Para não exigir 24 desenhos, as expressões caem em **6 representantes**:

| representante | quem cai nele |
|---|---|
| `neutro` (base) | focado, glacial, concentrado, firmeza, tedio |
| `furia` | determinado, berserk, esforco, limite |
| `animado` | confiante, euforico, extase |
| `panico` | nervoso, desespero, alerta, confuso |
| `dor` | tonto, tristeza |
| `morto` | (só ele) |

Quem desenha só o `neutro` tem um rosto que nunca muda. Com os 6 representantes, o rosto já reage em toda luta. As outras 18 são refinamento opcional.

### 2.2 Herança e reserva (não exige 1000 imagens)

**Níveis do lutador:** `personagem` → `classe` → `comum`.

O nível `elemento` **não existe no lutador**, porque o motor não dá elemento a um lutador (ENGINE §1.2). Ver PERGUNTAS 1.

**Regra do dono da parte:**
1. Para cada parte, o nível MAIS ESPECÍFICO que tem qualquer arte dessa parte é o **dono** dela naquele lutador.
2. Dentro do dono, o estado cai assim: **expressão pedida → representante da família → `neutro`**.
3. Se nenhum nível tem arte da parte, entra a **reserva**, que é o desenho de hoje daquela parte:
   - `rosto.gd` para olhos, sobrancelhas, boca e detalhes;
   - o corpo por código para a pele;
   - nada para os acessórios.

**Exemplo:** um Berserker em `tonto`.
- O Adrian fez olhos de Berserker só em `neutro` e `furia`, e fez olhos comuns em todos os 6 representantes.
- A classe é dona dos olhos: `classe/berserker_furia/tonto` não existe; o representante `dor` também não existe na classe; cai em `classe/berserker_furia/neutro`.
- Os olhos comuns de `dor` **não** entram. Misturar o olho de um estilo com o de outro desmancha a identidade.
- Essa regra é decisão de produto: PERGUNTAS 2.

**Tingir:**
- A **pele comum** é uma máscara em tons de cinza que o Godot pinta com a cor do personagem (`cor` do cabeçalho; são 106 personagens, cada um com a sua cor). Uma imagem serve para o jogo inteiro.
- Pele de classe ou de personagem pode vir colorida (`tingir: "nenhum"`). O painel pergunta na hora de anexar. Ver PERGUNTAS 3.

---

## 3. O esquema de um slot

Cada slot é um objeto no manifesto. Exemplo completo em `slots_exemplo.json`.

```jsonc
{
  "id": "lutador/olhos/classe/berserker_furia/furia",  // estável: grupo/parte/nivel/alvo/estado
  "grupo": "lutador",            // lutador | camada_estado | arma | skill | efeito | arena | hud
  "parte": "olhos",
  "alvo": {"nivel": "classe", "chave": "berserker_furia", "rotulo": "Berserker (Fúria)"},
  "estado": "furia",             // "base" quando a parte não varia
  "eixo_estado": "expressao",    // expressao | estado_orbe | null
  "camada_z": 40,                // ordem dentro do grupo (maior = por cima)
  "quadro": "olhar",             // tela | olhar | mundo | arma | objeto | evento
  "ancora": "gabarito",          // gabarito (centro do quadrado) | empunhadura | centro
  "tamanho_px": [1024, 1024],    // tamanho recomendado (o painel aceita proporção igual)
  "tingir": "nenhum",            // nenhum | cor_personagem | elemento | cor_arma | cor_lado
  "papel": "opcional",           // obrigatorio | recomendado | opcional
  "fallback": [                  // a cadeia, na ordem; o primeiro que existir vence
    "lutador/olhos/classe/berserker_furia/neutro"
  ],
  "reserva": "rosto.gd: expressão furia",   // o desenho de hoje quando a cadeia acaba
  "destino": "palco/biblioteca/partes/lutador/olhos/classe/berserker_furia/furia.png",
  "godot_le_hoje": false,        // true = a busca do palco já existe (§6)
  "fonte": "neural_fights/effects/character_flair.py:636",  // de onde a engine tirou este slot
  "presenca": "5% dos passos"    // opcional: do inventário de 95 lutas, para ordenar a tela
}
```

**Ao lado de cada PNG anexado fica um `.json`** com:
- `origem`, `autor`, `prova` (a Oficina já recusa exportar sem prova; `painel/sprites/exportar.py:183-216`) e `data`;
- `tingir`;
- `contorno_proprio` (bool);
- o `slot` de onde veio.

**O id é estável.** Ele só muda se o nome da classe, da skill ou da arma mudar na engine. Os nomes passam pela mesma `slug` do palco (`palco/nucleo/util.gd:45-58`): sem acento, minúsculo, `_` no lugar de espaço e de parênteses.

---

## 4. Onde o arquivo vai no disco

**Uma árvore nova, só de partes, descoberta pelo NOME** (a mesma filosofia da `biblioteca.gd`: sem catálogo para editar):

```
palco/biblioteca/partes/<grupo>/<parte>/<nivel>/<alvo>/<estado>.png   (+ .json)
     ex.: partes/lutador/pele/comum/_/base.png
          partes/lutador/olhos/classe/berserker_furia/neutro.png
          partes/skill/projetil/skill/bola_de_fogo/base.png
          partes/arma/arma/estilo/katana/base.png
```

- O nível `comum` usa `_` como alvo.
- **Para o que o palco JÁ procura** (arma, skill, evento, camadas de estado), o painel grava também a **cena-embrulho** no caminho de hoje. Ela é uma `.tscn` de 1 quadro com `folha_animada.gd` (ou `peca.gd` + Sprite2D, para a arma), apontando para o PNG da árvore `partes/`. A Oficina já gera esse embrulho (`painel/sprites/exportar.py:256-357`).
  - Com isso, arma, skill, efeito e camada de estado anexados aparecem **sem mudar uma linha do Godot**.
- **O `sprites_usuario/` do Ateliê** (catálogo por animação de lado, `catalogo.json`) não serve para a bolinha modular. O painel novo usa `partes/`. Ver PERGUNTAS 6.

### Prévia para o painel

Depois de gravar ou trocar PNGs, o painel gera a folha das seis expressões
representantes com o comando abaixo (o `--import` só é necessário para PNG novo):

```powershell
E:\ferramentas\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path palco --import
E:\ferramentas\godot\Godot_v4.7.2-stable_win64_console.exe --path palco res://ferramentas/previa_sprites.tscn -- --classe=berserker --personagem= --saida=E:/tmp/previa_berserker.png
```

`classe` e `personagem` usam os mesmos nomes da timeline (o resolvedor aplica
`slug`); `personagem` pode ficar vazio. A folha usa fundo escuro de contraste e
as expressões `neutro`, `furia`, `animado`, `panico`, `dor` e `morto`.
Na HD 4600, a segunda linha deve rodar sem `--headless`: o renderer ANGLE
entrega o PNG em cerca de 7 s; no modo headless a leitura do viewport não fecha.

---

## 5. Os outros grupos

### 5.1 `camada_estado`: o que aparece em volta do lutador

**Já é lido hoje.** A busca é `lutador_padrao.gd:59-103`. As peças entram como filhas do lutador, escaladas pelo raio e sem girar.

| parte | alvos | qtd | fonte |
|---|---|---|---|
| `estado` | atordoado, bloqueando, super_armor, agarrado, tempo_parado, congelado, adrenalina, dormindo + escudo_bolha | 9 | `timeline.py:98` (flags) e `lutador_padrao.gd:61-70` |
| `status` | os 29 de `STATUS_VISUAL` | 29 | `neural_fights/core/status_runtime.py:117` |
| `buffs` | as 26 skills BUFF | 26 | `skills.py` |
| `canais` | as 3 skills CHANNEL | 3 | `skills.py` |
| `transformacoes` | as 3 skills TRANSFORM | 3 | `skills.py` |

**As outras 10 flags não ganham sprite:** atacando, morto, invencivel, canalizando, dash, intangivel, transformado, lancado, oculto e no_ar. O Godot as mostra mexendo no lutador: contorno, opacidade, pisca, sumir, rastro. Essa lista é explícita no manifesto (`tratamento: "godot"`), para a catraca cobrar flag nova.

**Embrulho:** `folha_animada` com `tamanho_m = 4.0`. Assim, o quadrado de 1024 do gabarito cobre 2× o diâmetro do corpo, igual ao gabarito do lutador.

### 5.2 `arma`

| parte | alvos | qtd | o Godot lê hoje? |
|---|---|---|---|
| `arma` (a peça inteira, presa na mão) | 8 tipos (reserva) + 54 estilos | 62 | **sim**: `armas/estilos/<estilo>` > `armas/tipos/<tipo>` (`biblioteca.gd:84-89`) |
| `corrente_cabo`, `corrente_elos`, `corrente_couro`, `corrente_corda` | Corrente | 4 | não: os elos são desenhados por código em `armas/tipos/corrente.gd` |
| `corrente_cabeca` | bola_espinhos, martelo, peso, ponta, foice, dardo | 6 | não (`timeline.py:245-250`) |
| `projetil_arma` (o que a arma atira) | faca, flecha, shuriken, chakram | 4 | sim, pelo nome (`skills/<nome>`), mas o nome é o da arma: precisa de busca por `forma` |
| `orbe` (Mágica) | orbitando, carregando, disparando (o estado cai em `orbitando`) | 3 | sim (`skills/magica` > `objetos/orbe/arcano`) |
| `brilho_raridade` | brilho_leve, brilho_medio, particulas, aura_dourada, chamas_miticas | 5 | não |
| `encantamento` | os 12 de `ENCANTAMENTOS` | 12 | não (o inventário marca como bloqueado: falta dado na timeline) |
| `rastro` | corte, estocada, esmagamento, chicote, puxada | 5 | não (hoje é uma `Line2D` na cor da arma, `palco.gd:428-445`) |

**A arma não varia por estado.** As 5 fases do golpe são giro e avanço, que o Godot já faz pela timeline (`palco.gd:474-502`).

**A Dupla usa a mesma peça duas vezes,** espelhada (`palco.gd:448-471`).

**Reserva:** a silhueta por tipo de `armas/arma_padrao.gd`.

### 5.3 `skill`

**Cadeia:** `skill/<nome>` → `elemento/<elemento>` → `comum` (do tipo) → arte CC0 de hoje. É exatamente a ordem que o palco já usa (`biblioteca.gd:101-107`).

| tipo de skill | partes | por skill | por elemento | o Godot lê hoje? |
|---|---|---|---|---|
| PROJETIL (34) | `projetil` | 34 | 12 | sim |
| AREA (33) | `area_chao`, `area_borda` | 66 | 24 | o chão sim, numa imagem só; a borda separada não |
| BEAM (6) | `feixe_corpo`, `feixe_ponta` | 12 | 24 | **não**: o feixe vai de A até B e a `folha_animada` não estica; precisa de código (a Oficina também recusa beam) |
| SUMMON (4) | `invocacao` | 4 | 12 | sim |
| TRAP (3) | `estrutura` | 3 | 12 | sim |
| DASH (6) | `portal` (só o Portal Arcano cria objeto, `entities.py:1370`) | 1 | 12 | sim |
| BUFF, CHANNEL, TRANSFORM | vão para `camada_estado` (§5.1) | — | — | sim |

**A skill não varia por estado.** O `prog` (0 a 1 da vida do objeto) e o `ativ` da área (aviso → dano) são feitos pelo Godot.

**O ponto aberto é a área:** o aviso pode pedir outra imagem. Hoje o manifesto deixa como estado opcional `aviso`, que cai na imagem `base`.

### 5.4 `efeito`

| parte | alvos | qtd | o Godot lê hoje? |
|---|---|---|---|
| `evento` | os 17 eventos com efeito (acerto, dano, cura, bloqueio, parry, esquiva, desvio, dash, parede, wall_splat, ko, escudo_quebrou, agarrao_desfecho, obstaculo, choque, movimento, projetil_fim) | 17 | sim |
| `evento` (variantes) | acerto × (4 tiers, critico, projetil_arma, 5 arquétipos) = 11; agarrao_desfecho × 5 modos; movimento × 7 gatilhos; projetil_fim × 8 motivos | 31 | sim (`palco.gd:585-598`) |
| `conjuracao` (evento `skill`) | comum + 12 elementos | 13 | sim (`eventos/skill_<elemento>`) |
| `impacto` (evento `explosao`) | comum + 12 elementos | 13 | sim |

**Cadeia do evento** (é a do palco, `biblioteca.gd:110-118`): variante → elemento → tier → tipo → padrão.

**Efeito estático:** o Godot faz o estouro com escala crescente + giro + sumir. A folha de quadros continua aceita (a `folha_animada` lê os dois). Ver PERGUNTAS 5.

### 5.5 `arena` e 5.6 `hud`

**Arena** (o Godot NÃO lê nada disto hoje; `arena_padrao.gd` desenha por código):

| parte | alvos | qtd |
|---|---|---|
| `chao` e `parede` | 20 arenas | 40 |
| `obstaculo` e `obstaculo_quebrado` | 22 tipos | 44 |
| `clima` | 11 efeitos de clima | 11 |

Cadeia: arena → tema (17) → padrão.

**HUD:** `placa_nome`, `moldura_vida`, `barra_vida`, `selo_plano`. São 4, tingidas pela cor do lado. Hoje são feitas por código (`hud_padrao.gd`).

---

## 6. O que o Godot já lê e o que precisa de código

| grupo | hoje | o que falta |
|---|---|---|
| lutador (9 partes) | **não** | um resolvedor de partes no `lutador_padrao.gd`: mesma regra do dono (§2.2), desenhar cada camada por z, `tela` sem giro e `olhar` com giro `ang` + squash (`esc_x/esc_y`), tingir a pele pela `cor`. O `rosto.gd` passa a usar a imagem da parte quando existir e o desenho de hoje quando não |
| camada_estado | **sim** (embrulho `.tscn`) | nada |
| arma | **sim** para a peça inteira | busca por `forma` do `projetil_arma`; peças da corrente; raridade, encantamento e rastro |
| skill | **sim** para projétil, área (1 imagem), summon, trap e portal | feixe (beam); borda da área separada |
| efeito | **sim** | nada |
| arena, hud | não | ler chão, parede, obstáculo, clima e as peças do HUD |

---

## 7. O manifesto é GERADO da engine (cada estado novo aparece sozinho)

O manifesto **não é escrito à mão**. Um gerador (proposto: `random_builds/builds/palco/manifesto.py`, comando `main.py palco manifesto`) importa os catálogos e monta a lista.

O protótipo usado para as contagens deste documento roda e está no scratchpad desta sessão. Ele importou cada lista da tabela abaixo.

| lista | de onde sai |
|---|---|
| classes (16) | `neural_fights/models/constants.py:387` `LISTA_CLASSES` |
| personagens (106) | `neural_fights/data/database.py` (o banco de runtime) |
| expressões (24) | `neural_fights/recording/timeline.py:121` `EXPRESSOES` (= `character_flair.py:636`) |
| flags (18) | `timeline.py:98` `FLAGS` |
| skills (118) e tipos | `neural_fights/core/skills.py:24` `SKILL_DB` (sem "Nenhuma") |
| status (29) | `neural_fights/core/status_runtime.py:117` `STATUS_VISUAL` |
| tipos de arma (8) | `constants.py:111` `TIPOS_ARMA` |
| estilos (54) | `neural_fights/tools/gerador_database.py:79` `ESTILOS_ARMA` |
| raridades e encantamentos | `constants.py:10` `RARIDADES`; `constants.py:237` `ENCANTAMENTOS` |
| cabeças e materiais da corrente | `timeline.py:245-250` |
| arquétipos (5) | `neural_fights/effects/weapon_animations.py:744` |
| elementos (12) | `neural_fights/utils/palette.py:23` `ELEMENT_PALETTES` |
| eventos com efeito, tiers, motivos, gatilhos, desfechos, estados do orbe | `palco/nucleo/timeline.gd:19`; `timeline.py:128-152`; `neural_fights/core/agarrao.py:22` |
| arenas, temas, obstáculos, climas | `neural_fights/core/arena.py:53` `ARENAS` |

**Duas tabelas pequenas são escritas à mão.** Elas são a decisão de produto:
- `FAMILIA`: expressão → representante (§2.1);
- `TRATAMENTO_FLAG`: flag → `camada` ou `godot` (§5.1).

Mais as partes por tipo de skill (§5.3).

**A catraca** (proposta: `tests/test_manifesto_sprites.py`) fica vermelha quando:
1. aparece expressão nova sem família;
2. aparece flag nova sem tratamento;
3. aparece tipo de skill novo sem partes;
4. aparece skill, classe, estilo, status, arena, obstáculo, clima, evento com efeito, variante (tier, motivo, gatilho, desfecho), estado do orbe, cabeça de corrente, raridade ou encantamento que não tem slot;
5. o `manifesto.json` commitado é diferente do que o gerador produz agora (esqueceram de regerar);
6. o `lutador_padrao.gd` procura uma categoria que o manifesto não tem (o mesmo jeito do `palco/testes/test_buscas.py`, que lê o `.gd` como texto);
7. a lista de expressões da timeline difere da do `character_flair` (esse teste já existe em `tests/test_timeline_palco_regressions.py:406-413`; a catraca reaproveita).

**O resultado:** um estado novo na engine **quebra o teste** até ganhar o seu lugar no painel.

---

## 8. Contagem

Gerada pelo protótipo, importando a engine em 06/10/2026.

| grupo | slots no manifesto | detalhe |
|---|---|---|
| lutador | **1.299** | comum 83 + 16 classes × 76 |
| camada_estado | 70 | 9 estados + 29 status + 26 buffs + 3 canais + 3 transformações |
| arma | 101 | 8 tipos + 54 estilos + corrente 10 + projétil da arma 4 + orbe 3 + raridade 5 + encantamento 12 + rastro 5 |
| skill | 224 | 8 partes comuns + 96 por elemento + 120 por skill |
| efeito | 74 | 17 eventos + 31 variantes + 26 de conjuração e impacto |
| arena | 95 | 40 chão/parede + 44 obstáculos + 11 climas |
| hud | 4 | — |
| **total** | **1.867** | sem os personagens individuais |

**Personagem individual:** 76 slots por personagem, abertos só quando o Adrian pede ("criar variação para este personagem"). Os 106 personagens dariam 8.056 slots em potencial. O painel não lista esses slots de cara.

**De onde sai o 83 do lutador comum:**
- sombra: 1
- pele: 1
- olhos, sobrancelhas e boca: 24 cada, 72 no total
- detalhe do rosto: 9

**De onde sai o 76 por classe:**
- pele, marcas, acessório de costas e acessório de cabeça: 1 cada, 4 no total
- olhos, sobrancelhas e boca: 24 cada, 72 no total

### Quantos o Adrian precisa preencher para um lutador completo

| nível de pronto | o que anexar | qtd |
|---|---|---|
| **mínimo (o jogo inteiro já muda)** | pele comum (tingida pela cor de cada personagem) + olhos `neutro` + boca `neutro` | **3** |
| rosto que reage | + olhos e boca nos 5 outros representantes (furia, animado, panico, dor, morto) + sombra | **14** |
| identidade de classe | + acessório de cabeça e de costas por classe | +2 por classe (**+32** nas 16) |
| rosto completo | + sobrancelhas (24) + 18 expressões restantes de olhos e boca + 9 detalhes | 83 no comum |

Com os **14** anexos comuns, todos os 106 personagens ficam com o visual novo e o rosto reagindo. Com mais **2 por classe**, cada classe tem silhueta própria.
