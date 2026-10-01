# Inventário de sprites do palco

Tarefa 2eb994b3, pedido do Adrian de 01/10/2026: todas as folhas e peças das animações de personagens, armas, habilidades, efeitos e arena. Gerado em 2026-10-01 20:20.

Cada linha saiu do código ou dos dados; o campo `fonte` do JSON diz de onde. A versão para máquina, com um objeto por item, é [`inventario_sprites.json`](inventario_sprites.json). A esteira (`main.py palco faltantes`, que ainda não existe) pode lê-la direto.

## Resumo

- **513 itens** no total: 78 folhas 4×4 e 435 peças paradas.
- **Só 1 tem arte da esteira**: o projétil de FOGO, a folha do piriri, que ainda está sem commit. Outros **85 têm arte CC0 provisória**, a trocar.
- **132 são desenho de código** e **295 não têm nada**. Faltam **427**.
- **82 são opcionais**: uma peça compartilhada (tipo×elemento, por exemplo) já cobre. Sem eles, o mínimo é **431 itens**.
- **178 itens pedem uma mudança pequena no palco** antes de aparecer (o palco ainda não procura o nome). **28 estão bloqueados** por falta de dado na timeline: a forma 2 da Transformável, os encantamentos e a corrente em elos, que espera a revisão 4. Tudo está na seção "Mudanças de busca".

| prioridade | total | ia | cc0 | vetor | nenhuma | folhas | opcionais | bloqueados |
|---|---|---|---|---|---|---|---|---|
| P1 | 60 | 0 | 19 | 22 | 19 | 27 | 18 | 0 |
| P2 | 97 | 0 | 5 | 23 | 69 | 32 | 21 | 4 |
| P3 | 356 | 1 | 61 | 87 | 207 | 19 | 43 | 24 |
| **todas** | 513 | 1 | 85 | 132 | 295 | 78 | 82 | 28 |

| grupo | P1 | P2 | P3 | total | faltam (vetor + nenhuma) |
|---|---|---|---|---|---|
| base | 1 | 0 | 0 | 1 | 1 |
| personagens | 24 | 10 | 15 | 49 | 35 |
| armas | 4 | 15 | 75 | 94 | 94 |
| habilidades | 9 | 41 | 162 | 212 | 164 |
| efeitos | 22 | 22 | 24 | 68 | 62 |
| arena | 0 | 9 | 76 | 85 | 67 |
| hud | 0 | 0 | 4 | 4 | 4 |

**Os 10 primeiros da ordem de produção** (a lista inteira está na seção "Ordem de produção" e no campo `ordem` do JSON):

1. `imagem_mestra`: Imagem-mestra de estilo: 1 bolinha com rosto + 1 arma + 1 projétil + 1 impacto no estilo do palco (contorno #14141A, cel de 2 tons, luz do alto à esquerda). Vai anexada a TODO pedido e a todo julgamento do Grok. (P1, estrutural)
2. `conjuracao_generica`: Conjuração (o instante do cast) em máscara branca, tingida pelo elemento da skill. (P1, 95/95 lutas; 1122 casts)
3. `acerto_light`: Faísca/estouro do acerto leve (tier do autor). (P1, 1338 acertos em 95 lutas (14.1 por luta))
4. `acerto_medium`: Faísca/estouro do acerto médio (tier do autor). (P1, 1395 acertos em 95 lutas (14.7 por luta))
5. `impacto_generico`: Estouro genérico em máscara branca (o palco tinge pelo elemento do evento: tingir='elemento'). (P1, 73/95 lutas)
6. `corpo_bolinha`: Corpo da bolinha: máscara branca com o cel de 2 tons e o brilho; o palco tinge com a cor do personagem (88 cores no banco). (P1, todo duelo (2 por luta); o palco ainda não procura este nome)
7. `acerto_colossal`: Faísca/estouro do acerto colossal (tier do autor). (P1, 281 acertos em 95 lutas (3.0 por luta))
8. `acerto_heavy`: Faísca/estouro do acerto pesado (tier do autor). (P1, 125 acertos em 95 lutas (1.3 por luta))
9. `evento_ko`: K.O.: explosão grande no chão sob o corpo caído. (P1, 95/95 lutas)
10. `evento_desvio`: Desvio (a IA leu e saiu): anel de esquiva. (P1, 95/95 lutas)

## Como ler

**Convenções da esteira** (decisões do Grimório):

- **Formato híbrido** (`sprites-ia-formato` = híbrido): peça parada que o Godot anima (gira, pulsa, estica, segue a timeline). A folha 4×4 fica só para o IMPACTO: acerto, estouro, conjuração, erupção, K.O.
- **Fundo** (`sprites-ia-fundo` = chroma): magenta liso `#FF00FF`. Quando o objeto é roxo ou magenta, verde `#00FF00`: elementos TREVAS, ARCANO, VOID, TEMPO e GRAVITAÇÃO (matiz de 250° a 280° na paleta) e os acessórios das classes roxas. Chão, parede e fundo de arena são texturas opacas.
- **Estilo** (`sprites-ia-estilo` = mestra): uma imagem-mestra aprovada vai anexada a todo pedido. Contorno `#14141A`, cel de 2 tons, luz do alto à esquerda, vista de cima, tudo apontando para +x.
- **Alvo** (`sprites-ia-alvo` = os dois): habilidades e armas. **Corrente** (`corrente-arte` = esteira): elo, cabo e 6 cabeças.
- **Números de dano** (`palco-numeros-de-dano` = não): nenhum sprite de número.
- **Chão da arena** (`chao-da-arena` = pedra): a pedra CC0 fica. Por isso o chão por tema é P3.

**Tamanho**: o maior uso é a bolinha de 408 px, então até 512 px por quadro (COMO-EDITAR §7). A folha 4×4 tem 1024×1024 (quadros de 256). O K.O. e as erupções, maiores, usam 2048×2048 (quadros de 512). O ChatGPT entrega 1254², sem alfa: a Oficina recorta o chroma e fatia.

**Prioridade medida**: P1: presença >= 50% das 95 lutas medidas (ou estrutural); P2: 10-50%; P3: < 10% ou nunca visto. Métricas só de contagem: P1 >= 1 por luta, P2 >= 0,1. Estados/expressões: P1 >= 5% dos passos, P2 >= 0,5%.

**Amostra**: 95 lutas re-simuladas pela seed (fight.json dos duelos + estreias das gerações), vencedor idêntico ao gravado em 95/95; 50 lutas puladas porque um dos lutadores saiu do banco. Cada luta re-simulada gerou a timeline v1 completa (objetos, efeitos, eventos, flags, expressões) com `neural_fights.recording.timeline.gravar_timeline(desenhar=False)`, o mesmo laço do palco. A amostra mostra quem lutou de verdade, não o banco: as Runas Flutuantes estão em 2 das 101 armas do banco e apareceram em 48 lutas; o Berserker é 5 dos 88 personagens e apareceu em 53.

**Colunas**:

- `arquivo` é a arte (png) proposta, relativa a `palco/biblioteca/`.
- `cena` é o arquivo que a biblioteca PROCURA. O nome passa por `UtilPalco.slug`: minúsculas, sem acento, `_` no lugar de espaço e pontuação.
- `procura?` diz se o palco já procura esse nome hoje. "não" quer dizer que precisa de uma mudança pequena no palco.
- `arte` é o que está lá agora: ia, cc0, vetor ou nenhuma.

Busca da biblioteca (`palco/nucleo/biblioteca.gd`):

```
armas    estilos/<estilo> > tipos/<tipo> > _padrao
lutador  nomes/<nome> > classes/<classe> > classes/<classe sem parenteses> > _padrao
objeto   skills/<nome> > objetos/<tipo>/<elemento> > objetos/<tipo>/_padrao > objetos/_padrao
evento   eventos/<tipo>_<tier> > eventos/<tipo> > eventos/_padrao
arena    <nome> > temas/<tema> > _padrao
hud      _padrao
```

## Mudanças de busca que destravam itens

Hoje o palco não acha estes itens pelo nome. Cada linha é uma mudança pequena no palco ou na timeline, para o builds fazer. Este inventário não mexe em código.

| o que falta | itens que destrava | onde |
|---|---|---|
| evento por **elemento**: `eventos/<tipo>_<elemento>` (para `skill` e `explosao`, que já trazem `elemento`) | 13 impactos e 13 conjurações por elemento | `biblioteca.gd evento()` |
| evento por **campo**: `eventos/acerto_critico`, `eventos/agarrao_desfecho_<modo>`, `eventos/acerto_<arquétipo do autor>` | crítico, 4 desfechos de agarrão, 4 impactos por arma | `biblioteca.gd evento()` + `palco.gd _evento` |
| `movimento` e `projetil_fim` em `EVENTOS_COM_VFX`, com busca por `gatilho`/`motivo` | 6 de movimento e 2 de fim de projétil | `timeline.gd`, `palco.gd` |
| o lutador carregar peças de `lutadores/{estados,status,buffs,transformacoes,canais}/` | corpo, 10 estados, 29 status, 32 auras de skill | `lutador_padrao.gd` |
| o rosto trocar 7 extras vetoriais por `peca()` | 7 peças do rosto | `rosto.gd` |
| o orbe da Mágica usar o **estilo** da arma do dono (hoje sai sem nome e DEFAULT; o dono já traz `arma.estilo` no cabeçalho) | 6 orbes por estilo | `palco.gd _objetos` (ou `timeline.py`) |
| o projétil de arma usar o **estilo** do dono (Kunai, Bumerangue e Machados saem como `faca`; a besta, como `flecha`) | virote e arte própria em voo por estilo | `palco.gd _objetos` (ou `timeline.py`) |
| a **forma atual** da Transformável na timeline | 6 peças de forma 2 | `timeline.py` (canal novo) |
| os **encantamentos** no cabeçalho da arma | 12 brilhos de encantamento | `timeline.py _cabecalho_arma` |
| a **raridade** desenhada (o `efeito_visual` já vem na timeline) | 5 brilhos de raridade | `arma_padrao.gd` |
| timeline **rev 4** da corrente (canais da bola) + peça Verlet | elo, cabo, corda, couro e as 6 cabeças | outro agente (plano `corrente-rework.md`, F2/F3) |
| obstáculo e clima por arquivo (`arenas/obstaculos/<tipo>`, clima na cena do tema) | 22 obstáculos e 10 climas | `arena_padrao.gd` |
| conjuração por skill: `skills/<skill>_conjuracao` (o evento `skill` traz o nome) | Troca de Almas (a única skill sem objeto e sem aura) | `biblioteca.gd evento()` |
| textura no rastro da arma e do projétil (hoje é Line2D com gradiente) | 4 rastros por arquétipo e o rastro do projétil | `palco.gd`, `objeto_padrao.gd` |
| a cena da skill tocar o surgir/sumir e a destruição pelo `prog`/`hp` da trilha | surgir de invocação e destruição de barreira | cena da skill (sem mudar o núcleo) |
| o corpo da bolinha em png tingido | corpo (e a sombra, opcional) | `lutador_padrao.gd` |

**Achados de passagem** (medidos na re-simulação):

- **Elemento DEFAULT onde o catálogo tem outro.** `Corrente em Cadeia` (beam), `Muro Ardente` (trap), os canais `Fotossíntese`, `Fúria do Trovão` e `Desintegrar` e a transformação `Forma Sanguinária` saem na timeline com `elemento` DEFAULT, embora o catálogo diga RAIO, FOGO, NATUREZA... Na busca por elemento, caem no `default`, ou seja, em `_padrao`.
- **O orbe da arma Mágica é o objeto mais comum da luta**: 1514 trilhas, em 53/95 lutas. Mesmo assim, não há cena `objetos/orbe/*`, e ele cai no `objetos/_padrao`. O projétil de arma também sai DEFAULT.
- **Três dashes viram objeto ÁREA com o nome da skill**: `Avanço Brutal` (70/95 lutas, a skill mais vista), `Teleporte Relâmpago` e `Passo do Vazio`. A cena `efeitos/skills/<skill>` já é achada.
- **Projétil e área com o mesmo nome**: `Bomba Relógio`, `Colapso` e `Meteoro` criam os dois. A busca `skills/<skill>` serve à MESMA cena para os dois tipos, então ela precisa olhar `tipo` em `configurar()`.

## 0. Base

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `imagem_mestra` | Imagem-mestra de estilo: 1 bolinha com rosto + 1 arma + 1 projétil + 1 impacto no estilo do palco (contorno #14141A, cel de 2 tons, luz do alto à esquerda). Vai anexada a TODO pedido e a todo julgamento do Grok. | `_estilo/imagem_mestra.png` | `` | não | peca | 1 | 1254x1254 (o tamanho que o ChatGPT entrega) | magenta #FF00FF | P1 |  | nenhuma |

## 1. Personagens

O lutador é a **bolinha** (decisão `visual-do-lutador`), o círculo da simulação (raio = tamanho/2). A timeline não tem "animação de andar": o corpo é a bolinha e o motor manda posição, pulo (`z`), squash (`esc_x`, `esc_y`), olhar (`ang`), flash de dano (`flash`, `flash_cor`), expressão (`expr`, 24) e 18 flags.

Estados que a timeline emite, medidos em % dos 246.712 passos de lutador (`flags`, `docs/palco/timeline.md`):

| flag | % dos passos | o que o palco faz hoje | sprite? |
|---|---|---|---|
| atacando | 35.36% | contorno branco | não (a arma e o rastro mostram) |
| morto | 8.12% | rosto 'morto', arma caída | não (a folha `evento_ko`) |
| atordoado | 14.13% | estrelas + contorno amarelo | `estado_atordoado` + `status_atordoado` |
| congelado | 0.44% | tinge de azul | `estado_congelado` |
| invencivel | 25.46% | pisca | não |
| canalizando | 2.08% | — | `skill_<canal>` |
| adrenalina | 26.13% | contorno vermelho pulsando | `estado_adrenalina` |
| agarrado | 1.22% | — | `estado_agarrado` |
| dash | 7.07% | — | `movimento_dash` |
| intangivel | 0.40% | semitransparente | não |
| super_armor | 1.63% | anel dourado | `estado_super_armor` |
| bloqueando | 7.23% | arco azul na frente | `estado_bloqueando` |
| tempo_parado | 0.61% | — | `estado_tempo_parado` |
| dormindo | 0.00% | z | `estado_dormindo` |
| transformado | 5.08% | aura fina | `skill_<transformação>` |
| lancado | 5.57% | — | não |
| oculto | 0.13% | não desenha (portal) | não |
| no_ar | 13.85% | sobe por z, a sombra encolhe | não |

Os estados que o Adrian citou, um a um: **parado** e **andando** são a bolinha com o squash do motor, sem sprite. **Atacando** é a arma com as fases e o rastro. **Levando dano** é o flash do corpo, a expressão `dor` e a folha de acerto. **Atordoado** usa estrelas e o anel do status. **Agarrado** usa a marca e o desfecho do agarrão. **KO** é o rosto `morto` com a folha de K.O. **Vitória** não existe na timeline (sairia do `ko.vencedor`). **Esquiva**, **desvio** e **bloqueio** são folhas de evento, mais o arco do escudo.

**Expressões**: as 24 de `character_flair.py` já existem no palco (`rosto.gd`). São 14 peças CC0 do Kenney mais 7 extras em vetor. **Nenhuma expressão falta.** Medido em % dos passos:

| expressão | % | expressão | % | expressão | % |
|---|---|---|---|---|---|
| esforco | 16.2% | determinado | 15.2% | alerta | 14.8% |
| tonto | 12.8% | morto | 8.1% | confuso | 5.6% |
| furia | 5.5% | confiante | 5.3% | nervoso | 3.8% |
| limite | 3.8% | dor | 2.8% | concentrado | 1.6% |
| glacial | 1.1% | firmeza | 0.9% | euforico | 0.6% |
| animado | 0.5% | tedio | 0.5% | neutro | 0.3% |
| focado | 0.2% | panico | 0.1% | berserk | 0.0% |
| extase | 0.0% | desespero | 0.0% | tristeza | 0.0% |

Classes: as 16 de `LISTA_CLASSES`. A arte muda por classe (o acessório) e a cor muda por personagem: o palco tinge com `cor`. O elemento da classe não muda o corpo. Um arquivo por personagem (`lutadores/nomes/<nome>`, 88 no banco) é opcional e não entra na conta.

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `corpo_bolinha` | Corpo da bolinha: máscara branca com o cel de 2 tons e o brilho; o palco tinge com a cor do personagem (88 cores no banco). | `lutadores/pecas/corpo.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512 (círculo de 480 px), máscara branca com o cel de 2 tons e o brilho, que o palco tinge | magenta #FF00FF | P1 | todo duelo (2 por luta) | vetor |
| `sombra_contato` | Sombra de contato no chão (achatada, encolhe com o pulo). *(opcional)* | `lutadores/pecas/sombra.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x160 | magenta #FF00FF | P3 | todo duelo | vetor |
| `rosto_eye_open` | Peça do rosto `eye_open` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_open.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eye_half_top` | Peça do rosto `eye_half_top` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_half_top.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eye_half_top_wing` | Peça do rosto `eye_half_top_wing` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_half_top_wing.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eye_half_bottom` | Peça do rosto `eye_half_bottom` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_half_bottom.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eye_closed_up` | Peça do rosto `eye_closed_up` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_closed_up.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eye_closed_down` | Peça do rosto `eye_closed_down` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_closed_down.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eye_x` | Peça do rosto `eye_x` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eye_x.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eyebrow_a` | Peça do rosto `eyebrow_a` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eyebrow_a.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eyebrow_b` | Peça do rosto `eyebrow_b` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eyebrow_b.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eyebrow_c` | Peça do rosto `eyebrow_c` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eyebrow_c.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_eyebrow_d` | Peça do rosto `eyebrow_d` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/eyebrow_d.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_mouth_happy` | Peça do rosto `mouth_happy` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/mouth_happy.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_mouth_sad` | Peça do rosto `mouth_sad` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/mouth_sad.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_mouth_smirk` | Peça do rosto `mouth_smirk` (máscara branca; o palco pinta com #14141A). *(opcional)* | `lutadores/rosto/mouth_smirk.png` | `lutadores/rosto.gd` | sim | peca | 1 | como está (12x do SVG; ~6 px de borda vazia) | transparente | P1 | as 24 expressões usam | cc0 |
| `rosto_olho_espiral` | Olho em espiral (tonto). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/olho_espiral.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P1 | 13% dos passos de lutador (tonto) | vetor |
| `rosto_faiscas_alerta` | Faíscas de alerta sobre a cabeça (alerta). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/faiscas_alerta.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P1 | 15% dos passos de lutador (alerta) | vetor |
| `rosto_boca_onda` | Boca ondulada (nervoso, pânico, tonto, confuso). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/boca_onda.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P1 | 22% dos passos de lutador (nervoso, panico, tonto, confuso) | vetor |
| `rosto_gota_suor` | Gota de suor (pânico, nervoso, desespero, limite). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/gota_suor.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P1 | 8% dos passos de lutador (panico, nervoso, desespero, limite) | vetor |
| `rosto_veia_raiva` | Veia de raiva (fúria, berserk). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/veia_raiva.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P1 | 6% dos passos de lutador (furia, berserk) | vetor |
| `rosto_lagrima` | Lágrima (tristeza). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/lagrima.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P3 | 0% dos passos de lutador (tristeza) | vetor |
| `rosto_brilho_pupila` | Brilho na pupila (êxtase). Hoje é desenho vetorial em rosto.gd. | `lutadores/rosto/brilho_pupila.png` | `lutadores/rosto.gd` | não | peca | 1 | 256x256 máscara branca (~6 px de borda vazia) | magenta #FF00FF | P3 | 0% dos passos de lutador (extase) | vetor |
| `classe_guerreiro` | Acessório da classe Guerreiro (Força Bruta) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/guerreiro.png` | `lutadores/classes/guerreiro.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P2 | 18 aparições em 95 lutas (banco: 6 de 88) | nenhuma |
| `classe_berserker` | Acessório da classe Berserker (Fúria) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/berserker.png` | `lutadores/classes/berserker.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P1 | 53 aparições em 95 lutas (banco: 5 de 88) | nenhuma |
| `classe_gladiador` | Acessório da classe Gladiador (Combate) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/gladiador.png` | `lutadores/classes/gladiador.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P2 | 12 aparições em 95 lutas (banco: 8 de 88) | nenhuma |
| `classe_cavaleiro` | Acessório da classe Cavaleiro (Defesa) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/cavaleiro.png` | `lutadores/classes/cavaleiro.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P3 | 7 aparições em 95 lutas (banco: 5 de 88) | nenhuma |
| `classe_assassino` | Acessório da classe Assassino (Crítico) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/assassino.png` | `lutadores/classes/assassino.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | verde #00FF00 | P3 | 5 aparições em 95 lutas (banco: 4 de 88) | nenhuma |
| `classe_ladino` | Acessório da classe Ladino (Evasão) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/ladino.png` | `lutadores/classes/ladino.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P2 | 21 aparições em 95 lutas (banco: 7 de 88) | nenhuma |
| `classe_ninja` | Acessório da classe Ninja (Velocidade) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/ninja.png` | `lutadores/classes/ninja.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P3 | 8 aparições em 95 lutas (banco: 6 de 88) | nenhuma |
| `classe_duelista` | Acessório da classe Duelista (Precisão) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/duelista.png` | `lutadores/classes/duelista.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P3 | 7 aparições em 95 lutas (banco: 4 de 88) | nenhuma |
| `classe_mago` | Acessório da classe Mago (Arcano) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/mago.png` | `lutadores/classes/mago.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | verde #00FF00 | P3 | 3 aparições em 95 lutas (banco: 3 de 88) | nenhuma |
| `classe_piromante` | Acessório da classe Piromante (Fogo) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/piromante.png` | `lutadores/classes/piromante.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P2 | 10 aparições em 95 lutas (banco: 4 de 88) | nenhuma |
| `classe_criomante` | Acessório da classe Criomante (Gelo) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/criomante.png` | `lutadores/classes/criomante.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P3 | 2 aparições em 95 lutas (banco: 6 de 88) | nenhuma |
| `classe_necromante` | Acessório da classe Necromante (Trevas) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/necromante.png` | `lutadores/classes/necromante.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | verde #00FF00 | P3 | 4 aparições em 95 lutas (banco: 5 de 88) | nenhuma |
| `classe_paladino` | Acessório da classe Paladino (Sagrado) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/paladino.png` | `lutadores/classes/paladino.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P3 | 5 aparições em 95 lutas (banco: 5 de 88) | nenhuma |
| `classe_druida` | Acessório da classe Druida (Natureza) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/druida.png` | `lutadores/classes/druida.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P2 | 10 aparições em 95 lutas (banco: 5 de 88) | nenhuma |
| `classe_feiticeiro` | Acessório da classe Feiticeiro (Caos) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/feiticeiro.png` | `lutadores/classes/feiticeiro.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | verde #00FF00 | P2 | 12 aparições em 95 lutas (banco: 8 de 88) | nenhuma |
| `classe_monge` | Acessório da classe Monge (Chi) sobre a bolinha (capacete, capuz, chapéu, faixa...): diz a classe sem texto. | `lutadores/classes/monge.png` | `lutadores/classes/monge.tscn` | sim | peca | 1 | 512x512, acessório desenhado sobre a bolinha (a bolinha = círculo de 400 px centrado) | magenta #FF00FF | P2 | 13 aparições em 95 lutas (banco: 7 de 88) | nenhuma |
| `estado_atordoado` | Estrela girando sobre a cabeça (atordoado; 3 estrelas que o Godot gira) | `lutadores/estados/atordoado.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 256x256, peça pequena centrada | magenta #FF00FF | P1 | 14% dos passos de lutador; status ATORDOADO 95/95 lutas | vetor |
| `estado_bloqueando` | Escudo em arco na frente da bolinha (bloqueando) | `lutadores/estados/bloqueando.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x256 (arco de 100°, aberto para a esquerda) | magenta #FF00FF | P1 | 7% dos passos de lutador | vetor |
| `estado_super_armor` | Anel dourado de super armor | `lutadores/estados/super_armor.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 2% dos passos de lutador | vetor |
| `estado_escudo_bolha` | Bolha do escudo dos buffs (Escudo Arcano, Barreira Divina, Escudo de Brasas) | `lutadores/estados/escudo_bolha.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 3 lutas com buff de escudo | vetor |
| `estado_agarrado` | Mão/laço do agarrão sobre o agarrado (e o enlace da corrente leve) | `lutadores/estados/agarrado.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 1% dos passos de lutador; agarrão em 57/95 lutas | nenhuma |
| `estado_tempo_parado` | Mostrador de relógio parado sobre o lutador (tempo parado) | `lutadores/estados/tempo_parado.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 1% dos passos de lutador | nenhuma |
| `estado_congelado` | Bloco de gelo envolvendo a bolinha (congelado; hoje só tinge de azul) | `lutadores/estados/congelado.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0% dos passos de lutador | vetor |
| `estado_adrenalina` | Aura de adrenalina (hoje é o contorno vermelho pulsando) | `lutadores/estados/adrenalina.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P1 | 26% dos passos de lutador | vetor |
| `estado_dormindo` | Z do sono (dormindo) | `lutadores/estados/dormindo.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 256x256, peça pequena centrada | magenta #FF00FF | P3 | 0% dos passos de lutador; nenhum passo nas 95 lutas | vetor |
| `estado_vitoria` | Marca de vitória sobre o vencedor depois do K.O. (a timeline não tem estado de vitória: sairia do ko.vencedor) | `lutadores/estados/vitoria.png` | `lutadores/_padrao.tscn` | não | peca | 1 | 256x256, peça pequena centrada | magenta #FF00FF | P3 | não é estado da timeline | nenhuma |

## 2. Armas

São os 8 tipos e os 54 estilos de `neural_fights/data/armas.json`, um registro por estilo. O palco põe a peça na empunhadura, gira para a ponta da timeline e estica até o comprimento REAL da hitbox. Por isso cada arma é **uma peça parada**, e o golpe é animado pelo Godot com as fases do motor.

O que o motor emite por tipo: o relógio do golpe vem de `WEAPON_PROFILES[tipo]`, em segundos, pelas fases preparo, golpe, impacto, seguimento e recuperação. O movimento vem do arquétipo do estilo (`ARQUETIPO_POR_ESTILO`).

| tipo | preparo | golpe | impacto | seguimento | recuperação | total | o que mais a timeline traz | peças |
|---|---|---|---|---|---|---|---|---|
| Reta | 0.100 | 0.110 | 0.025 | 0.090 | 0.140 | 0.465 | ângulo, lunge, ponta (a geometria honesta) | 1 peça por estilo |
| Dupla | 0.040 | 0.065 | 0.015 | 0.040 | 0.065 | 0.225 | duas_laminas (±separação, ±10°); o lado da Adaga Gêmea não vem (lacuna 6) | 1 lâmina por estilo (o palco espelha) |
| Corrente | 0.200 | 0.250 | 0.050 | 0.200 | 0.250 | 0.950 | corrente_v2: a bola com posição/velocidade (rev 4 pendente); o giro do Mangual não vem | elo + cabo + 6 cabeças (+ corda, couro) |
| Arremesso | 0.130 | 0.055 | 0.000 | 0.110 | 0.160 | 0.455 | projetil_arma com forma faca/shuriken/chakram, fim (acerto, expirou, bloqueado, choque, voltou) | 1 peça por estilo (mão e voo) |
| Arco | 0.280 | 0.040 | 0.000 | 0.090 | 0.220 | 0.630 | arma_puxada 0..1; flecha como projetil_arma 'Flecha' | arco/besta por estilo + flecha (+ virote) |
| Orbital | 0.000 | 0.160 | 0.025 | 0.120 | 0.000 | 0.305 | peça no alcance da hitbox (1,5× o raio), giro de 360° no golpe; bloqueia projétil | 1 peça por estilo |
| Mágica | 0.120 | 0.170 | 0.060 | 0.120 | 0.170 | 0.640 | orbes (orbitando, carregando, disparando), sem nome, DEFAULT | foco por estilo + orbe (+ orbe por estilo) |
| Transformável | 0.090 | 0.160 | 0.035 | 0.130 | 0.160 | 0.575 | forma atual NÃO vem na timeline | forma 1 por estilo (+ forma 2, bloqueada) |

Arquétipos por estilo (`weapon_animations.py`): **estocada** = Lança, Espada Curta, Sai, Facas Táticas, Kunai, Rope Dart e Lanças de Mana. **Esmagamento** = Martelo, Maça, Machado, Meteor Hammer, Corrente com Peso e Montante. **Chicote** = Chicote, Kusarigama e Foice. **Puxada** = os 6 arcos e bestas. O resto é **corte**. O Mangual e as Adagas Gêmeas têm animador próprio.

Uma peça propria pode ter um `AnimationPlayer` `Anim` com a animação `golpe` e as marcas `preparo/golpe/impacto/seguimento/recuperacao` (COMO-EDITAR §3). Mas o que a peça desenha é a arma parada; o enfeite animado (brilho, balanço) é opcional.

`armas/tipos/<tipo>.tscn` (8 cenas) é o fallback do tipo. Não precisa de arte nova: aponta para a peça do estilo mais comum do tipo.

O projétil de arremesso em voo chega com o nome da FORMA do motor: `Faca`, `Shuriken`, `Chakram` e `Flecha` (`ArmaProjetil.nome = tipo.capitalize()`). Por isso as cenas `efeitos/skills/faca.tscn`, `shuriken.tscn` e `chakram.tscn` já são achadas, e cada uma só aponta para a peça do estilo. Elas não pedem arte nova e não estão na conta. Medido: faca em 9/95 lutas, flecha em 22, shuriken em 1 e chakram em 1. Facas de Arremesso, Kunai, Bumerangue e Machados de Arremesso voam todos como `faca`.

### Reta

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_espada_longa` | Espada Longa inteira (cabo + lâmina/cabeça). | `armas/estilos/espada_longa.png` | `armas/estilos/espada_longa.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_espada_curta` | Espada Curta inteira (cabo + lâmina/cabeça). | `armas/estilos/espada_curta.png` | `armas/estilos/espada_curta.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_montante` | Montante inteira (cabo + lâmina/cabeça). | `armas/estilos/montante.png` | `armas/estilos/montante.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_katana` | Katana inteira (cabo + lâmina/cabeça). | `armas/estilos/katana.png` | `armas/estilos/katana.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_sabre` | Sabre inteira (cabo + lâmina/cabeça). | `armas/estilos/sabre.png` | `armas/estilos/sabre.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 6 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_lanca` | Lança inteira (cabo + lâmina/cabeça). | `armas/estilos/lanca.png` | `armas/estilos/lanca.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_alabarda` | Alabarda inteira (cabo + lâmina/cabeça). | `armas/estilos/alabarda.png` | `armas/estilos/alabarda.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 2 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_machado` | Machado inteira (cabo + lâmina/cabeça). | `armas/estilos/machado.png` | `armas/estilos/machado.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_martelo` | Martelo inteira (cabo + lâmina/cabeça). | `armas/estilos/martelo.png` | `armas/estilos/martelo.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_maca` | Maça inteira (cabo + lâmina/cabeça). | `armas/estilos/maca.png` | `armas/estilos/maca.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_foice` | Foice inteira (cabo + lâmina/cabeça). | `armas/estilos/foice.png` | `armas/estilos/foice.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_claymore` | Claymore inteira (cabo + lâmina/cabeça). | `armas/estilos/claymore.png` | `armas/estilos/claymore.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 3 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |

### Dupla

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_adagas_gemeas` | Adagas Gêmeas: uma das duas lâminas. | `armas/estilos/adagas_gemeas.png` | `armas/estilos/adagas_gemeas.tscn` | sim | peca | 1 | 512x128 (4:1): uma lâmina só (o palco espelha a segunda) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 4 de 101 armas) | nenhuma |
| `arma_sai` | Sai: uma das duas lâminas. | `armas/estilos/sai.png` | `armas/estilos/sai.tscn` | sim | peca | 1 | 512x128 (4:1): uma lâmina só (o palco espelha a segunda) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_kamas` | Kamas: uma das duas lâminas. | `armas/estilos/kamas.png` | `armas/estilos/kamas.tscn` | sim | peca | 1 | 512x128 (4:1): uma lâmina só (o palco espelha a segunda) | magenta #FF00FF | P2 | 12 aparições em 95 lutas (banco: 4 de 101 armas) | nenhuma |
| `arma_garras` | Garras: uma das duas lâminas. | `armas/estilos/garras.png` | `armas/estilos/garras.tscn` | sim | peca | 1 | 512x128 (4:1): uma lâmina só (o palco espelha a segunda) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_tonfas` | Tonfas: uma das duas lâminas. | `armas/estilos/tonfas.png` | `armas/estilos/tonfas.tscn` | sim | peca | 1 | 512x128 (4:1): uma lâmina só (o palco espelha a segunda) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_facas_taticas` | Facas Táticas: uma das duas lâminas. | `armas/estilos/facas_taticas.png` | `armas/estilos/facas_taticas.tscn` | sim | peca | 1 | 512x128 (4:1): uma lâmina só (o palco espelha a segunda) | magenta #FF00FF | P2 | 12 aparições em 95 lutas (banco: 4 de 101 armas) | nenhuma |

### Corrente

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_kusarigama` | Cabeça da corrente Kusarigama: peso da kusarigama (a foice fica na mão). **Bloqueado:** a corrente em elos depende da timeline rev 4 (canais da bola) e da peça Verlet (outro agente). | `armas/pecas/corrente/cabeca_kusarigama.png` | `armas/estilos/kusarigama.tscn (ou a peça Verlet armas/tipos/corrente.*)` | sim | peca | 1 | 256x256: a ponta da corrente, o ponto de prender no meio da borda esquerda | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_mangual` | Cabeça da corrente Mangual: bola de ferro com espinhos. **Bloqueado:** a corrente em elos depende da timeline rev 4 (canais da bola) e da peça Verlet (outro agente). | `armas/pecas/corrente/cabeca_mangual.png` | `armas/estilos/mangual.tscn (ou a peça Verlet armas/tipos/corrente.*)` | sim | peca | 1 | 256x256: a ponta da corrente, o ponto de prender no meio da borda esquerda | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_chicote` | Cabeça da corrente Chicote: ponta de chicote de couro. **Bloqueado:** a corrente em elos depende da timeline rev 4 (canais da bola) e da peça Verlet (outro agente). | `armas/pecas/corrente/cabeca_chicote.png` | `armas/estilos/chicote.tscn (ou a peça Verlet armas/tipos/corrente.*)` | sim | peca | 1 | 256x256: a ponta da corrente, o ponto de prender no meio da borda esquerda | magenta #FF00FF | P3 | 6 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_corrente_com_peso` | Cabeça da corrente Corrente com Peso: peso de ferro maciço. **Bloqueado:** a corrente em elos depende da timeline rev 4 (canais da bola) e da peça Verlet (outro agente). | `armas/pecas/corrente/cabeca_corrente_com_peso.png` | `armas/estilos/corrente_com_peso.tscn (ou a peça Verlet armas/tipos/corrente.*)` | sim | peca | 1 | 256x256: a ponta da corrente, o ponto de prender no meio da borda esquerda | magenta #FF00FF | P3 | 3 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_meteor_hammer` | Cabeça da corrente Meteor Hammer: martelo-meteoro (bola pesada sem cabo). **Bloqueado:** a corrente em elos depende da timeline rev 4 (canais da bola) e da peça Verlet (outro agente). | `armas/pecas/corrente/cabeca_meteor_hammer.png` | `armas/estilos/meteor_hammer.tscn (ou a peça Verlet armas/tipos/corrente.*)` | sim | peca | 1 | 256x256: a ponta da corrente, o ponto de prender no meio da borda esquerda | magenta #FF00FF | P2 | 11 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_rope_dart` | Cabeça da corrente Rope Dart: dardo de metal na ponta da corda. **Bloqueado:** a corrente em elos depende da timeline rev 4 (canais da bola) e da peça Verlet (outro agente). | `armas/pecas/corrente/cabeca_rope_dart.png` | `armas/estilos/rope_dart.tscn (ou a peça Verlet armas/tipos/corrente.*)` | sim | peca | 1 | 256x256: a ponta da corrente, o ponto de prender no meio da borda esquerda | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `corrente_elo` | Elo de metal da corrente (o palco repete ao longo da corrente em Verlet). **Bloqueado:** timeline rev 4 + peça Verlet (outro agente). | `armas/pecas/corrente/elo.png` | `armas/tipos/corrente.*` | não | peca | 1 | 128x64: um elo deitado em +x (o palco repete ao longo da corrente) | magenta #FF00FF | P2 | 21 aparições de corrente em 95 lutas | nenhuma |
| `corrente_cabo` | Cabo/empunhadura da corrente (Mangual, Corrente com Peso). **Bloqueado:** timeline rev 4 + peça Verlet. | `armas/pecas/corrente/cabo.png` | `armas/tipos/corrente.*` | não | peca | 1 | 256x128 (empunhadura à esquerda) | magenta #FF00FF | P2 | 21 aparições de corrente | nenhuma |
| `corrente_segmento_corda` | Segmento de corda (Rope Dart, Meteor Hammer) no lugar do elo de metal. **Bloqueado:** timeline rev 4 + peça Verlet. | `armas/pecas/corrente/corda.png` | `armas/tipos/corrente.*` | não | peca | 1 | 128x64: um elo deitado em +x (o palco repete ao longo da corrente) | magenta #FF00FF | P2 | Rope Dart + Meteor Hammer | nenhuma |
| `corrente_segmento_couro` | Segmento de couro trançado (Chicote). **Bloqueado:** timeline rev 4 + peça Verlet. | `armas/pecas/corrente/couro.png` | `armas/tipos/corrente.*` | não | peca | 1 | 128x64: um elo deitado em +x (o palco repete ao longo da corrente) | magenta #FF00FF | P3 | Chicote | nenhuma |

### Arremesso

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_facas_de_arremesso` | Facas de Arremesso: a peça arremessada (na mão e em voo). | `armas/estilos/facas_de_arremesso.png` | `armas/estilos/facas_de_arremesso.tscn` | sim | peca | 1 | 256x256 centrado apontando para +x (serve na mão e em voo) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_shuriken` | Shuriken: a peça arremessada (na mão e em voo). | `armas/estilos/shuriken.png` | `armas/estilos/shuriken.tscn` | sim | peca | 1 | 256x256 centrado apontando para +x (serve na mão e em voo) | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_chakram` | Chakram: a peça arremessada (na mão e em voo). | `armas/estilos/chakram.png` | `armas/estilos/chakram.tscn` | sim | peca | 1 | 256x256 centrado apontando para +x (serve na mão e em voo) | magenta #FF00FF | P3 | 7 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_machados_de_arremesso` | Machados de Arremesso: a peça arremessada (na mão e em voo). | `armas/estilos/machados_de_arremesso.png` | `armas/estilos/machados_de_arremesso.tscn` | sim | peca | 1 | 256x256 centrado apontando para +x (serve na mão e em voo) | magenta #FF00FF | P3 | 2 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_kunai` | Kunai: a peça arremessada (na mão e em voo). | `armas/estilos/kunai.png` | `armas/estilos/kunai.tscn` | sim | peca | 1 | 256x256 centrado apontando para +x (serve na mão e em voo) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_bumerangue` | Bumerangue: a peça arremessada (na mão e em voo). | `armas/estilos/bumerangue.png` | `armas/estilos/bumerangue.tscn` | sim | peca | 1 | 256x256 centrado apontando para +x (serve na mão e em voo) | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |

### Arco

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_arco_curto` | Arco Arco Curto (sem a corda: o palco desenha a corda e a puxada). | `armas/estilos/arco_curto.png` | `armas/estilos/arco_curto.tscn` | sim | peca | 1 | 512x1024: o arco em pé, a corda (que o palco desenha) à esquerda, a frente para +x | magenta #FF00FF | P3 | 4 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_arco_longo` | Arco Arco Longo (sem a corda: o palco desenha a corda e a puxada). | `armas/estilos/arco_longo.png` | `armas/estilos/arco_longo.tscn` | sim | peca | 1 | 512x1024: o arco em pé, a corda (que o palco desenha) à esquerda, a frente para +x | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_arco_composto` | Arco Arco Composto (sem a corda: o palco desenha a corda e a puxada). | `armas/estilos/arco_composto.png` | `armas/estilos/arco_composto.tscn` | sim | peca | 1 | 512x1024: o arco em pé, a corda (que o palco desenha) à esquerda, a frente para +x | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_besta_leve` | Besta Besta Leve (sem a corda: o palco desenha a corda e a puxada). | `armas/estilos/besta_leve.png` | `armas/estilos/besta_leve.tscn` | sim | peca | 1 | 1024x512: a besta vista de cima apontando para +x, coronha à esquerda | magenta #FF00FF | P2 | 11 aparições em 95 lutas (banco: 5 de 101 armas) | nenhuma |
| `arma_besta_pesada` | Besta Besta Pesada (sem a corda: o palco desenha a corda e a puxada). | `armas/estilos/besta_pesada.png` | `armas/estilos/besta_pesada.tscn` | sim | peca | 1 | 1024x512: a besta vista de cima apontando para +x, coronha à esquerda | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_arco_elfico` | Arco Arco Élfico (sem a corda: o palco desenha a corda e a puxada). | `armas/estilos/arco_elfico.png` | `armas/estilos/arco_elfico.tscn` | sim | peca | 1 | 512x1024: o arco em pé, a corda (que o palco desenha) à esquerda, a frente para +x | magenta #FF00FF | P3 | 9 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `flecha` | Flecha em voo (e encaixada na corda durante a puxada). | `efeitos/pecas/flecha.png` | `efeitos/skills/flecha.tscn` | sim | peca | 1 | 512x128 apontando para +x | magenta #FF00FF | P2 | 22 lutas com flecha | nenhuma |
| `virote` | Virote de besta (mais curto e grosso que a flecha). | `efeitos/pecas/virote.png` | `(proposto) efeitos/skills/virote.tscn` | não | peca | 1 | 512x128 apontando para +x | magenta #FF00FF | P3 | Besta Leve + Besta Pesada | nenhuma |

### Orbital

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_escudo_orbital` | Escudo Orbital: escudo pequeno (o palco gira no raio da hitbox). | `armas/estilos/escudo_orbital.png` | `armas/estilos/escudo_orbital.tscn` | sim | peca | 1 | 256x256 centrado (o palco põe no raio da hitbox e gira) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_drones_de_combate` | Drones de Combate: drone (o palco gira no raio da hitbox). | `armas/estilos/drones_de_combate.png` | `armas/estilos/drones_de_combate.tscn` | sim | peca | 1 | 256x256 centrado (o palco põe no raio da hitbox e gira) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_orbes_misticos` | Orbes Místicos: orbe (o palco gira no raio da hitbox). | `armas/estilos/orbes_misticos.png` | `armas/estilos/orbes_misticos.tscn` | sim | peca | 1 | 256x256 centrado (o palco põe no raio da hitbox e gira) | magenta #FF00FF | P3 | 2 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_laminas_orbitais` | Lâminas Orbitais: lâmina giratória (o palco gira no raio da hitbox). | `armas/estilos/laminas_orbitais.png` | `armas/estilos/laminas_orbitais.tscn` | sim | peca | 1 | 256x256 centrado (o palco põe no raio da hitbox e gira) | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_cristais_flutuantes` | Cristais Flutuantes: cristal (o palco gira no raio da hitbox). | `armas/estilos/cristais_flutuantes.png` | `armas/estilos/cristais_flutuantes.tscn` | sim | peca | 1 | 256x256 centrado (o palco põe no raio da hitbox e gira) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_sentinelas` | Sentinelas: sentinela (olho mecânico) (o palco gira no raio da hitbox). | `armas/estilos/sentinelas.png` | `armas/estilos/sentinelas.tscn` | sim | peca | 1 | 256x256 centrado (o palco põe no raio da hitbox e gira) | magenta #FF00FF | P3 | 9 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |

### Mágica

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_espadas_espectrais` | Espadas Espectrais: espada espectral na mão. | `armas/estilos/espadas_espectrais.png` | `armas/estilos/espadas_espectrais.tscn` | sim | peca | 1 | 256x256 centrado (o foco mágico na mão) | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `orbe_espadas_espectrais` | Projétil/orbe do estilo Espadas Espectrais (espada espectral disparada; 3 estados: orbitando, carregando, disparando). | `efeitos/orbes/espadas_espectrais.png` | `efeitos/objetos/orbe/espadas_espectrais.tscn (proposto)` | não | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | 1 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_runas_flutuantes` | Runas Flutuantes: runa flutuante na mão. | `armas/estilos/runas_flutuantes.png` | `armas/estilos/runas_flutuantes.tscn` | sim | peca | 1 | 256x256 centrado (o foco mágico na mão) | magenta #FF00FF | P1 | 48 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `orbe_runas_flutuantes` | Projétil/orbe do estilo Runas Flutuantes (runa flutuante disparada; 3 estados: orbitando, carregando, disparando). | `efeitos/orbes/runas_flutuantes.png` | `efeitos/objetos/orbe/runas_flutuantes.tscn (proposto)` | não | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P1 | 48 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_tentaculos_sombrios` | Tentáculos Sombrios: tentáculo sombrio na mão. | `armas/estilos/tentaculos_sombrios.png` | `armas/estilos/tentaculos_sombrios.tscn` | sim | peca | 1 | 256x256 centrado (o foco mágico na mão) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `orbe_tentaculos_sombrios` | Projétil/orbe do estilo Tentáculos Sombrios (tentáculo sombrio disparada; 3 estados: orbitando, carregando, disparando). | `efeitos/orbes/tentaculos_sombrios.png` | `efeitos/objetos/orbe/tentaculos_sombrios.tscn (proposto)` | não | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_cristais_arcanos` | Cristais Arcanos: cristal arcano na mão. | `armas/estilos/cristais_arcanos.png` | `armas/estilos/cristais_arcanos.tscn` | sim | peca | 1 | 256x256 centrado (o foco mágico na mão) | magenta #FF00FF | P3 | 4 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `orbe_cristais_arcanos` | Projétil/orbe do estilo Cristais Arcanos (cristal arcano disparada; 3 estados: orbitando, carregando, disparando). | `efeitos/orbes/cristais_arcanos.png` | `efeitos/objetos/orbe/cristais_arcanos.tscn (proposto)` | não | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | 4 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_lancas_de_mana` | Lanças de Mana: lança de mana na mão. | `armas/estilos/lancas_de_mana.png` | `armas/estilos/lancas_de_mana.tscn` | sim | peca | 1 | 256x256 centrado (o foco mágico na mão) | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `orbe_lancas_de_mana` | Projétil/orbe do estilo Lanças de Mana (lança de mana disparada; 3 estados: orbitando, carregando, disparando). | `efeitos/orbes/lancas_de_mana.png` | `efeitos/objetos/orbe/lancas_de_mana.tscn (proposto)` | não | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_chamas_espirituais` | Chamas Espirituais: chama espiritual na mão. | `armas/estilos/chamas_espirituais.png` | `armas/estilos/chamas_espirituais.tscn` | sim | peca | 1 | 256x256 centrado (o foco mágico na mão) | magenta #FF00FF | P3 | 2 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `orbe_chamas_espirituais` | Projétil/orbe do estilo Chamas Espirituais (chama espiritual disparada; 3 estados: orbitando, carregando, disparando). | `efeitos/orbes/chamas_espirituais.png` | `efeitos/objetos/orbe/chamas_espirituais.tscn (proposto)` | não | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | 2 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `orbe_default` | Orbe da arma Mágica (todos os estilos hoje): orbitando, carregando, disparando. | `efeitos/pecas/orbe.png` | `efeitos/objetos/orbe/default.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P1 | 53/95 lutas; 1514 trilhas de orbe (o objeto mais comum da luta) | vetor |

### Transformável

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arma_espada_lanca` | Espada-Lança: forma 1 (a forma em que começa). | `armas/estilos/espada_lanca.png` | `armas/estilos/espada_lanca.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 7 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_espada_lanca_forma2` | Espada-Lança: forma 2 (depois de transformar). **Bloqueado:** a timeline não traz a forma atual (forma_atual não está em _cabecalho_arma nem nos canais). | `armas/estilos/espada_lanca_forma2.png` | `armas/estilos/espada_lanca.tscn` | não | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 7 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_espada_extensivel` | Espada Extensível: forma 1 (a forma em que começa). | `armas/estilos/espada_extensivel.png` | `armas/estilos/espada_extensivel.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_espada_extensivel_forma2` | Espada Extensível: forma 2 (depois de transformar). **Bloqueado:** a timeline não traz a forma atual (forma_atual não está em _cabecalho_arma nem nos canais). | `armas/estilos/espada_extensivel_forma2.png` | `armas/estilos/espada_extensivel.tscn` | não | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 1 de 101 armas) | nenhuma |
| `arma_chicote_espada` | Chicote-Espada: forma 1 (a forma em que começa). | `armas/estilos/chicote_espada.png` | `armas/estilos/chicote_espada.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_chicote_espada_forma2` | Chicote-Espada: forma 2 (depois de transformar). **Bloqueado:** a timeline não traz a forma atual (forma_atual não está em _cabecalho_arma nem nos canais). | `armas/estilos/chicote_espada_forma2.png` | `armas/estilos/chicote_espada.tscn` | não | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 0 aparições em 95 lutas (banco: 0 de 101 armas) | nenhuma |
| `arma_arco_laminas` | Arco-Lâminas: forma 1 (a forma em que começa). | `armas/estilos/arco_laminas.png` | `armas/estilos/arco_laminas.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 9 aparições em 95 lutas (banco: 6 de 101 armas) | nenhuma |
| `arma_arco_laminas_forma2` | Arco-Lâminas: forma 2 (depois de transformar). **Bloqueado:** a timeline não traz a forma atual (forma_atual não está em _cabecalho_arma nem nos canais). | `armas/estilos/arco_laminas_forma2.png` | `armas/estilos/arco_laminas.tscn` | não | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 9 aparições em 95 lutas (banco: 6 de 101 armas) | nenhuma |
| `arma_bastao_segmentado` | Bastão Segmentado: forma 1 (a forma em que começa). | `armas/estilos/bastao_segmentado.png` | `armas/estilos/bastao_segmentado.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 5 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_bastao_segmentado_forma2` | Bastão Segmentado: forma 2 (depois de transformar). **Bloqueado:** a timeline não traz a forma atual (forma_atual não está em _cabecalho_arma nem nos canais). | `armas/estilos/bastao_segmentado_forma2.png` | `armas/estilos/bastao_segmentado.tscn` | não | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 5 aparições em 95 lutas (banco: 2 de 101 armas) | nenhuma |
| `arma_machado_martelo` | Machado-Martelo: forma 1 (a forma em que começa). | `armas/estilos/machado_martelo.png` | `armas/estilos/machado_martelo.tscn` | sim | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 5 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |
| `arma_machado_martelo_forma2` | Machado-Martelo: forma 2 (depois de transformar). **Bloqueado:** a timeline não traz a forma atual (forma_atual não está em _cabecalho_arma nem nos canais). | `armas/estilos/machado_martelo_forma2.png` | `armas/estilos/machado_martelo.tscn` | não | peca | 1 | 1024x256 (4:1): a empunhadura no meio da borda esquerda, a ponta na borda direita | magenta #FF00FF | P3 | 5 aparições em 95 lutas (banco: 3 de 101 armas) | nenhuma |

### raridade

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `raridade_brilho_leve` | Brilho de raridade Incomum (brilho_leve) ao longo da arma. | `armas/raridade/brilho_leve.png` | `(proposto) dentro de arma_padrao.gd` | não | peca | 1 | 1024x256 (máscara branca que o palco tinge pela cor da raridade) | magenta #FF00FF | P2 | o banco tem 89 de 101 armas acima de Comum | nenhuma |
| `raridade_brilho_medio` | Brilho de raridade Raro (brilho_medio) ao longo da arma. | `armas/raridade/brilho_medio.png` | `(proposto) dentro de arma_padrao.gd` | não | peca | 1 | 1024x256 (máscara branca que o palco tinge pela cor da raridade) | magenta #FF00FF | P2 | o banco tem 89 de 101 armas acima de Comum | nenhuma |
| `raridade_particulas` | Brilho de raridade Épico (particulas) ao longo da arma. | `armas/raridade/particulas.png` | `(proposto) dentro de arma_padrao.gd` | não | peca | 1 | 1024x256 (máscara branca que o palco tinge pela cor da raridade) | magenta #FF00FF | P2 | o banco tem 89 de 101 armas acima de Comum | nenhuma |
| `raridade_aura_dourada` | Brilho de raridade Lendário (aura_dourada) ao longo da arma. | `armas/raridade/aura_dourada.png` | `(proposto) dentro de arma_padrao.gd` | não | peca | 1 | 1024x256 (máscara branca que o palco tinge pela cor da raridade) | magenta #FF00FF | P2 | o banco tem 89 de 101 armas acima de Comum | nenhuma |
| `raridade_chamas_miticas` | Brilho de raridade Mítico (chamas_miticas) ao longo da arma. | `armas/raridade/chamas_miticas.png` | `(proposto) dentro de arma_padrao.gd` | não | peca | 1 | 1024x256 (máscara branca que o palco tinge pela cor da raridade) | magenta #FF00FF | P2 | o banco tem 89 de 101 armas acima de Comum | nenhuma |

### encantamento

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `encantamento_fogo` | Brilho de encantamento Fogo na lâmina (Chamas). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/fogo.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_gelo` | Brilho de encantamento Gelo na lâmina (Gelo). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/gelo.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_raio` | Brilho de encantamento Raio na lâmina (Relâmpago). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/raio.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_natureza` | Brilho de encantamento Natureza na lâmina (Veneno). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/natureza.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_trevas` | Brilho de encantamento Trevas na lâmina (Trevas). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/trevas.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_luz` | Brilho de encantamento Luz na lâmina (Sagrado). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/luz.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_vento` | Brilho de encantamento Vento na lâmina (Velocidade). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/vento.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_sangue` | Brilho de encantamento Sangue na lâmina (Vampirismo). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/sangue.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_precisao` | Brilho de encantamento Precisão na lâmina (Crítico). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/precisao.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_forca` | Brilho de encantamento Força na lâmina (Penetração). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/forca.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_morte` | Brilho de encantamento Morte na lâmina (Execução). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/morte.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |
| `encantamento_arcano` | Brilho de encantamento Arcano na lâmina (Espelhamento). **Bloqueado:** a timeline não traz os encantamentos da arma (_cabecalho_arma). | `armas/encantamentos/arcano.png` | `(proposto)` | não | peca | 1 | 1024x256 máscara ao longo da lâmina | magenta #FF00FF | P3 |  | nenhuma |

### rastro

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `rastro_corte` | Textura do rastro do golpe: arco de corte. | `efeitos/texturas/rastro_corte.png` | `(proposto) palco.gd rastro[slot]` | não | peca | 1 | 1024x128 faixa em +x, do transparente (esquerda) ao cheio (direita) | magenta #FF00FF | P1 | 129 lutadores com esse arquétipo em 95 lutas | vetor |
| `rastro_estocada` | Textura do rastro do golpe: rastro reto de estocada. | `efeitos/texturas/rastro_estocada.png` | `(proposto) palco.gd rastro[slot]` | não | peca | 1 | 1024x128 faixa em +x, do transparente (esquerda) ao cheio (direita) | magenta #FF00FF | P2 | 13 lutadores com esse arquétipo em 95 lutas | vetor |
| `rastro_esmagamento` | Textura do rastro do golpe: rastro pesado de esmagamento. | `efeitos/texturas/rastro_esmagamento.png` | `(proposto) palco.gd rastro[slot]` | não | peca | 1 | 1024x128 faixa em +x, do transparente (esquerda) ao cheio (direita) | magenta #FF00FF | P2 | 17 lutadores com esse arquétipo em 95 lutas | vetor |
| `rastro_chicote` | Textura do rastro do golpe: rastro curvo de chicote. | `efeitos/texturas/rastro_chicote.png` | `(proposto) palco.gd rastro[slot]` | não | peca | 1 | 1024x128 faixa em +x, do transparente (esquerda) ao cheio (direita) | magenta #FF00FF | P3 | 6 lutadores com esse arquétipo em 95 lutas | vetor |

## 3. Habilidades

São as 118 skills do contrato (`catalogo_de_contratos()`), por tipo: 34 PROJETIL, 33 AREA, 26 BUFF, 6 BEAM, 6 DASH, 4 SUMMON, 3 TRAP, 3 TRANSFORM e 3 CHANNEL. 109 estão nos `KIT_POOLS` e 9 em `SKILLS_FORA_DE_ROTACAO`. Por elemento: FOGO 11, RAIO 11, NATUREZA 11, GELO 10, LUZ 10, ARCANO 10, TREVAS 8, TEMPO 7, SANGUE 6, GRAVITAÇÃO 6, CAOS 6, VOID 4 e sem elemento (DEFAULT) 18.

**Como compartilham.** O palco procura primeiro `efeitos/skills/<skill>` e, se não achar, `efeitos/objetos/<tipo>/<elemento>`. A base **tipo × elemento** cobre todas as skills sem arte própria:

- projétil e área: 13 peças cada, incluindo DEFAULT;
- beam: corpo e ponta por elemento, 26 peças;
- impacto: 13 folhas;
- conjuração: 1 folha genérica tingida.

Arte **própria** só onde a forma não é "bola/círculo de energia": 40 skills com forma própria, 5 erupções, as 3 explosões de projétil-área, os dashes, as invocações e as barreiras. Buff, transformação e canal são **auras sobre o lutador**, que o palco ainda não procura.

Ícone de skill: o palco e o HUD não mostram ícone, então não entra. Se o HUD mostrar o kit um dia, são 118 ícones de 128×128.

### Base tipo × elemento

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `projetil_fogo` | Projétil de skill em voo, elemento FOGO. Compartilhada por: Bola de Fogo, Combustão Espontânea. | `efeitos/folhas/11239_removebg_preview_1.png` | `efeitos/objetos/projetil/fogo.tscn` | sim | folha | 26 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | ia |
| `projetil_gelo` | Projétil de skill em voo, elemento GELO. Compartilhada por: Morte Glacial, Prisão de Gelo. | `efeitos/pecas/projetil/gelo.png` | `efeitos/objetos/projetil/gelo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤1 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_raio` | Projétil de skill em voo, elemento RAIO. Compartilhada por: Corrente Elétrica. | `efeitos/pecas/projetil/raio.png` | `efeitos/objetos/projetil/raio.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤1 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_trevas` | Projétil de skill em voo, elemento TREVAS. Compartilhada por: Esfera Sombria, Maldição, Necrose. | `efeitos/pecas/projetil/trevas.png` | `efeitos/objetos/projetil/trevas.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | ≤9 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_luz` | Projétil de skill em voo, elemento LUZ. Compartilhada por: Smite. | `efeitos/pecas/projetil/luz.png` | `efeitos/objetos/projetil/luz.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤4 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_natureza` | Projétil de skill em voo, elemento NATUREZA. Compartilhada por: Praga. | `efeitos/pecas/projetil/natureza.png` | `efeitos/objetos/projetil/natureza.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P2 | ≤11 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_arcano` | Projétil de skill em voo, elemento ARCANO. Compartilhada por: Disparo de Mana, Roubar Magia. | `efeitos/pecas/projetil/arcano.png` | `efeitos/objetos/projetil/arcano.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | ≤1 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_caos` | Projétil de skill em voo, elemento CAOS. Compartilhada por: Chama Caótica, Instabilidade. | `efeitos/pecas/projetil/caos.png` | `efeitos/objetos/projetil/caos.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_sangue` | Projétil de skill em voo, elemento SANGUE. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/projetil/sangue.png` | `efeitos/objetos/projetil/sangue.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_void` | Projétil de skill em voo, elemento VOID. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/projetil/void.png` | `efeitos/objetos/projetil/void.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_tempo` | Projétil de skill em voo, elemento TEMPO. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/projetil/tempo.png` | `efeitos/objetos/projetil/tempo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_gravitacao` | Projétil de skill em voo, elemento GRAVITACAO. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/projetil/gravitacao.png` | `efeitos/objetos/projetil/gravitacao.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `projetil_default` | Projétil de skill em voo, elemento DEFAULT. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/projetil/default.png` | `efeitos/objetos/projetil/default.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | nenhuma |
| `area_fogo` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento FOGO. Compartilhada por: Explosão Nova, Inferno. | `efeitos/pecas/area/fogo.png` | `efeitos/objetos/area/fogo.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | ≤10 lutas (soma das skills genéricas do par) | cc0 |
| `area_gelo` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento GELO. Compartilhada por: Shatter, Zero Absoluto. | `efeitos/pecas/area/gelo.png` | `efeitos/objetos/area/gelo.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | ≤2 lutas (soma das skills genéricas do par) | cc0 |
| `area_raio` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento RAIO. Compartilhada por: Campo Elétrico. | `efeitos/pecas/area/raio.png` | `efeitos/objetos/area/raio.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | ≤3 lutas (soma das skills genéricas do par) | cc0 |
| `area_trevas` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento TREVAS. Compartilhada por: Colheita de Almas, Explosão Necrótica, Medo Profundo. | `efeitos/pecas/area/trevas.png` | `efeitos/objetos/area/trevas.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | ≤7 lutas (soma das skills genéricas do par) | cc0 |
| `area_luz` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento LUZ. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/area/luz.png` | `efeitos/objetos/area/luz.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `area_natureza` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento NATUREZA. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/area/natureza.png` | `efeitos/objetos/area/natureza.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `area_arcano` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento ARCANO. Compartilhada por: Explosão Arcana. | `efeitos/pecas/area/arcano.png` | `efeitos/objetos/area/arcano.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | ≤3 lutas (soma das skills genéricas do par) | cc0 |
| `area_caos` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento CAOS. Compartilhada por: Explosão do Caos. | `efeitos/pecas/area/caos.png` | `efeitos/objetos/area/caos.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | ≤10 lutas (soma das skills genéricas do par) | cc0 |
| `area_sangue` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento SANGUE. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/area/sangue.png` | `efeitos/objetos/area/sangue.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | cc0 |
| `area_void` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento VOID. Compartilhada por: Fenda do Vazio. | `efeitos/pecas/area/void.png` | `efeitos/objetos/area/void.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | ≤1 lutas (soma das skills genéricas do par) | cc0 |
| `area_tempo` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento TEMPO. Compartilhada por: Slow Motion. | `efeitos/pecas/area/tempo.png` | `efeitos/objetos/area/tempo.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | ≤7 lutas (soma das skills genéricas do par) | cc0 |
| `area_gravitacao` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento GRAVITACAO. Compartilhada por: Campo de Gravidade, Pulso Gravitacional, Repulsão. | `efeitos/pecas/area/gravitacao.png` | `efeitos/objetos/area/gravitacao.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P2 | ≤28 lutas (soma das skills genéricas do par) | cc0 |
| `area_default` | Área no chão (zona/campo; o aviso é a mesma peça mais apagada), elemento DEFAULT. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/area/default.png` | `efeitos/objetos/area/default.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | ≤0 lutas (soma das skills genéricas do par) | nenhuma |
| `beam_fogo_corpo` | Feixe FOGO: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/fogo_corpo.png` | `efeitos/objetos/beam/fogo.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_fogo_ponta` | Feixe FOGO: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/fogo_ponta.png` | `efeitos/objetos/beam/fogo.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_gelo_corpo` | Feixe GELO: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/gelo_corpo.png` | `efeitos/objetos/beam/gelo.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_gelo_ponta` | Feixe GELO: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/gelo_ponta.png` | `efeitos/objetos/beam/gelo.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_raio_corpo` | Feixe RAIO: corpo do feixe. Compartilhada por: Corrente em Cadeia, Raio Sagrado, Relâmpago. | `efeitos/pecas/beam/raio_corpo.png` | `efeitos/objetos/beam/raio.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤9 lutas | cc0 |
| `beam_raio_ponta` | Feixe RAIO: ponta/impacto do feixe. Compartilhada por: Corrente em Cadeia, Raio Sagrado, Relâmpago. | `efeitos/pecas/beam/raio_ponta.png` | `efeitos/objetos/beam/raio.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤9 lutas | cc0 |
| `beam_trevas_corpo` | Feixe TREVAS: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/trevas_corpo.png` | `efeitos/objetos/beam/trevas.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_trevas_ponta` | Feixe TREVAS: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/trevas_ponta.png` | `efeitos/objetos/beam/trevas.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_luz_corpo` | Feixe LUZ: corpo do feixe. Compartilhada por: Raio Sagrado. | `efeitos/pecas/beam/luz_corpo.png` | `efeitos/objetos/beam/luz.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_luz_ponta` | Feixe LUZ: ponta/impacto do feixe. Compartilhada por: Raio Sagrado. | `efeitos/pecas/beam/luz_ponta.png` | `efeitos/objetos/beam/luz.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_natureza_corpo` | Feixe NATUREZA: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/natureza_corpo.png` | `efeitos/objetos/beam/natureza.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_natureza_ponta` | Feixe NATUREZA: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/natureza_ponta.png` | `efeitos/objetos/beam/natureza.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_arcano_corpo` | Feixe ARCANO: corpo do feixe. Compartilhada por: Desintegrar. | `efeitos/pecas/beam/arcano_corpo.png` | `efeitos/objetos/beam/arcano.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_arcano_ponta` | Feixe ARCANO: ponta/impacto do feixe. Compartilhada por: Desintegrar. | `efeitos/pecas/beam/arcano_ponta.png` | `efeitos/objetos/beam/arcano.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_caos_corpo` | Feixe CAOS: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/caos_corpo.png` | `efeitos/objetos/beam/caos.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_caos_ponta` | Feixe CAOS: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/caos_ponta.png` | `efeitos/objetos/beam/caos.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_sangue_corpo` | Feixe SANGUE: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/sangue_corpo.png` | `efeitos/objetos/beam/sangue.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_sangue_ponta` | Feixe SANGUE: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/sangue_ponta.png` | `efeitos/objetos/beam/sangue.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤0 lutas | cc0 |
| `beam_void_corpo` | Feixe VOID: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/void_corpo.png` | `efeitos/objetos/beam/void.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_void_ponta` | Feixe VOID: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/void_ponta.png` | `efeitos/objetos/beam/void.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_tempo_corpo` | Feixe TEMPO: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/tempo_corpo.png` | `efeitos/objetos/beam/tempo.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_tempo_ponta` | Feixe TEMPO: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/tempo_ponta.png` | `efeitos/objetos/beam/tempo.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_gravitacao_corpo` | Feixe GRAVITACAO: corpo do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/gravitacao_corpo.png` | `efeitos/objetos/beam/gravitacao.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_gravitacao_ponta` | Feixe GRAVITACAO: ponta/impacto do feixe. Compartilhada por: (nenhuma skill do catálogo). | `efeitos/pecas/beam/gravitacao_ponta.png` | `efeitos/objetos/beam/gravitacao.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | ≤0 lutas | cc0 |
| `beam_default_corpo` | Feixe DEFAULT: corpo do feixe. Compartilhada por: Corrente em Cadeia. | `efeitos/pecas/beam/default_corpo.png` | `efeitos/objetos/beam/default.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | ≤4 lutas | nenhuma |
| `beam_default_ponta` | Feixe DEFAULT: ponta/impacto do feixe. Compartilhada por: Corrente em Cadeia. | `efeitos/pecas/beam/default_ponta.png` | `efeitos/objetos/beam/default.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | ≤4 lutas | nenhuma |

### Impacto e conjuração

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `impacto_fogo` | Estouro/impacto do projétil e da área, elemento FOGO (evento explosao). | `efeitos/folhas/impacto_fogo.png` | `(proposto) efeitos/eventos/explosao_fogo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 5 explosões em 95 lutas (0.05 por luta) | nenhuma |
| `impacto_gelo` | Estouro/impacto do projétil e da área, elemento GELO (evento explosao). | `efeitos/folhas/impacto_gelo.png` | `(proposto) efeitos/eventos/explosao_gelo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 2 explosões em 95 lutas (0.02 por luta) | nenhuma |
| `impacto_raio` | Estouro/impacto do projétil e da área, elemento RAIO (evento explosao). | `efeitos/folhas/impacto_raio.png` | `(proposto) efeitos/eventos/explosao_raio.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 2 explosões em 95 lutas (0.02 por luta) | nenhuma |
| `impacto_trevas` | Estouro/impacto do projétil e da área, elemento TREVAS (evento explosao). | `efeitos/folhas/impacto_trevas.png` | `(proposto) efeitos/eventos/explosao_trevas.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 13 explosões em 95 lutas (0.14 por luta) | nenhuma |
| `impacto_luz` | Estouro/impacto do projétil e da área, elemento LUZ (evento explosao). | `efeitos/folhas/impacto_luz.png` | `(proposto) efeitos/eventos/explosao_luz.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 2 explosões em 95 lutas (0.02 por luta) | nenhuma |
| `impacto_natureza` | Estouro/impacto do projétil e da área, elemento NATUREZA (evento explosao). | `efeitos/folhas/impacto_natureza.png` | `(proposto) efeitos/eventos/explosao_natureza.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 16 explosões em 95 lutas (0.17 por luta) | nenhuma |
| `impacto_arcano` | Estouro/impacto do projétil e da área, elemento ARCANO (evento explosao). | `efeitos/folhas/impacto_arcano.png` | `(proposto) efeitos/eventos/explosao_arcano.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 10 explosões em 95 lutas (0.11 por luta) | nenhuma |
| `impacto_caos` | Estouro/impacto do projétil e da área, elemento CAOS (evento explosao). | `efeitos/folhas/impacto_caos.png` | `(proposto) efeitos/eventos/explosao_caos.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 8 explosões em 95 lutas (0.08 por luta) | nenhuma |
| `impacto_sangue` | Estouro/impacto do projétil e da área, elemento SANGUE (evento explosao). | `efeitos/folhas/impacto_sangue.png` | `(proposto) efeitos/eventos/explosao_sangue.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 24 explosões em 95 lutas (0.25 por luta) | nenhuma |
| `impacto_void` | Estouro/impacto do projétil e da área, elemento VOID (evento explosao). | `efeitos/folhas/impacto_void.png` | `(proposto) efeitos/eventos/explosao_void.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P3 | 0 explosões em 95 lutas (0.00 por luta) | nenhuma |
| `impacto_tempo` | Estouro/impacto do projétil e da área, elemento TEMPO (evento explosao). | `efeitos/folhas/impacto_tempo.png` | `(proposto) efeitos/eventos/explosao_tempo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P3 | 3 explosões em 95 lutas (0.03 por luta) | nenhuma |
| `impacto_gravitacao` | Estouro/impacto do projétil e da área, elemento GRAVITACAO (evento explosao). | `efeitos/folhas/impacto_gravitacao.png` | `(proposto) efeitos/eventos/explosao_gravitacao.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 12 explosões em 95 lutas (0.13 por luta) | nenhuma |
| `impacto_default` | Estouro/impacto do projétil e da área, elemento DEFAULT (evento explosao). | `efeitos/folhas/impacto_default.png` | `(proposto) efeitos/eventos/explosao_default.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 462 explosões em 95 lutas (4.86 por luta) | nenhuma |
| `impacto_generico` | Estouro genérico em máscara branca (o palco tinge pelo elemento do evento: tingir='elemento'). | `efeitos/folhas/impacto.png` | `efeitos/eventos/explosao.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 73/95 lutas | vetor |
| `conjuracao_generica` | Conjuração (o instante do cast) em máscara branca, tingida pelo elemento da skill. | `efeitos/folhas/conjuracao.png` | `efeitos/eventos/skill.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 95/95 lutas; 1122 casts | vetor |
| `conjuracao_fogo` | Conjuração do elemento FOGO. *(opcional)* | `efeitos/folhas/conjuracao_fogo.png` | `(proposto) efeitos/eventos/skill_fogo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 49 casts em 95 lutas | nenhuma |
| `conjuracao_gelo` | Conjuração do elemento GELO. *(opcional)* | `efeitos/folhas/conjuracao_gelo.png` | `(proposto) efeitos/eventos/skill_gelo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 7 casts em 95 lutas | nenhuma |
| `conjuracao_raio` | Conjuração do elemento RAIO. *(opcional)* | `efeitos/folhas/conjuracao_raio.png` | `(proposto) efeitos/eventos/skill_raio.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 108 casts em 95 lutas | nenhuma |
| `conjuracao_trevas` | Conjuração do elemento TREVAS. *(opcional)* | `efeitos/folhas/conjuracao_trevas.png` | `(proposto) efeitos/eventos/skill_trevas.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 49 casts em 95 lutas | nenhuma |
| `conjuracao_luz` | Conjuração do elemento LUZ. *(opcional)* | `efeitos/folhas/conjuracao_luz.png` | `(proposto) efeitos/eventos/skill_luz.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 28 casts em 95 lutas | nenhuma |
| `conjuracao_natureza` | Conjuração do elemento NATUREZA. *(opcional)* | `efeitos/folhas/conjuracao_natureza.png` | `(proposto) efeitos/eventos/skill_natureza.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 118 casts em 95 lutas | nenhuma |
| `conjuracao_arcano` | Conjuração do elemento ARCANO. *(opcional)* | `efeitos/folhas/conjuracao_arcano.png` | `(proposto) efeitos/eventos/skill_arcano.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 31 casts em 95 lutas | nenhuma |
| `conjuracao_caos` | Conjuração do elemento CAOS. *(opcional)* | `efeitos/folhas/conjuracao_caos.png` | `(proposto) efeitos/eventos/skill_caos.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 25 casts em 95 lutas | nenhuma |
| `conjuracao_sangue` | Conjuração do elemento SANGUE. *(opcional)* | `efeitos/folhas/conjuracao_sangue.png` | `(proposto) efeitos/eventos/skill_sangue.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 139 casts em 95 lutas | nenhuma |
| `conjuracao_void` | Conjuração do elemento VOID. *(opcional)* | `efeitos/folhas/conjuracao_void.png` | `(proposto) efeitos/eventos/skill_void.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P3 | 6 casts em 95 lutas | nenhuma |
| `conjuracao_tempo` | Conjuração do elemento TEMPO. *(opcional)* | `efeitos/folhas/conjuracao_tempo.png` | `(proposto) efeitos/eventos/skill_tempo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 54 casts em 95 lutas | nenhuma |
| `conjuracao_gravitacao` | Conjuração do elemento GRAVITACAO. *(opcional)* | `efeitos/folhas/conjuracao_gravitacao.png` | `(proposto) efeitos/eventos/skill_gravitacao.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P2 | 75 casts em 95 lutas | nenhuma |
| `conjuracao_default` | Conjuração do elemento DEFAULT. *(opcional)* | `efeitos/folhas/conjuracao_default.png` | `(proposto) efeitos/eventos/skill_default.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 433 casts em 95 lutas | nenhuma |

### As 118 skills, uma a uma

| tipo | elemento | skill | cast em (de 95) | kit no banco (de 88) | prio | folhas/peças |
|---|---|---|---|---|---|---|
| AREA | ARCANO | Explosão Arcana | 3 | 3 | P3 | chão = base area_arcano |
| AREA | CAOS | Apocalipse | 1 | 1 | P3 | chão (própria); erupção 4x4 (própria) |
| AREA | CAOS | Explosão do Caos | 10 | 4 | P2 | chão = base area_caos |
| AREA | FOGO | Explosão Nova | 1 | 2 | P3 | chão = base area_fogo |
| AREA | FOGO | Inferno | 9 | 2 | P3 | chão = base area_fogo |
| AREA | FOGO | Pilar de Fogo | 10 | 3 | P2 | chão (própria); erupção 4x4 (própria) |
| AREA | GELO | Nevasca | 1 | 2 | P3 | chão (própria) |
| AREA | GELO | Shatter | 0 | 0 | P3 | chão = base area_gelo |
| AREA | GELO | Zero Absoluto | 2 | 4 | P3 | chão = base area_gelo |
| AREA | GRAVITACAO | Buraco Negro | 3 | 3 | P3 | chão (própria) |
| AREA | GRAVITACAO | Campo de Gravidade | 13 | 5 | P2 | chão = base area_gravitacao |
| AREA | GRAVITACAO | Pulso Gravitacional | 6 | 1 | P3 | chão = base area_gravitacao |
| AREA | GRAVITACAO | Repulsão | 9 | 3 | P3 | chão = base area_gravitacao |
| AREA | LUZ | Julgamento Celestial | 5 | 5 | P3 | chão (própria); erupção 4x4 (própria) |
| AREA | NATUREZA | Esporos Alucinógenos | 21 | 6 | P2 | chão (própria) |
| AREA | NATUREZA | Nuvem Tóxica | 16 | 6 | P2 | chão (própria) |
| AREA | NATUREZA | Raízes | 11 | 2 | P2 | chão (própria) |
| AREA | NATUREZA | Wrath of Nature | 8 | 0 | P3 | chão (própria); erupção 4x4 (própria) |
| AREA | RAIO | Campo Elétrico | 3 | 0 | P3 | chão = base area_raio |
| AREA | RAIO | Julgamento de Thor | 0 | 2 | P3 | chão (própria); erupção 4x4 (própria) |
| AREA | RAIO | Tempestade | 1 | 3 | P3 | chão (própria) |
| AREA | SANGUE | Ritual Carmesim | 49 | 2 | P1 | chão (própria) |
| AREA | TEMPO | Parar o Tempo | 11 | 5 | P2 | chão (própria) |
| AREA | TEMPO | Slow Motion | 7 | 3 | P3 | chão = base area_tempo |
| AREA | TREVAS | Colheita de Almas | 0 | 2 | P3 | chão = base area_trevas |
| AREA | TREVAS | Explosão Necrótica | 3 | 3 | P3 | chão = base area_trevas |
| AREA | TREVAS | Medo Profundo | 4 | 3 | P3 | chão = base area_trevas |
| AREA | VOID | Fenda do Vazio | 1 | 1 | P3 | chão = base area_void |
| AREA | VOID | Tentáculos do Vazio | 1 | 2 | P3 | chão (própria) |
| AREA | DEFAULT | Fúria Giratória | 9 | 5 | P3 | chão (própria) |
| AREA | DEFAULT | Provocar | 13 | 2 | P2 | chão (própria) |
| AREA | DEFAULT | Sacrifício | 14 | 8 | P2 | chão (própria) |
| AREA | DEFAULT | Terremoto | 7 | 5 | P3 | chão (própria) |
| BEAM | ARCANO | Desintegrar | 1 | 1 | P3 | corpo + ponta = base beam_arcano; canal (overlay) |
| BEAM | FOGO | Chamas do Dragão (fora de rotação) | 2 | 0 | P3 | corpo + ponta (próprios); canal (overlay) |
| BEAM | LUZ | Raio Sagrado | 5 | 5 | P3 | corpo + ponta = base beam_luz |
| BEAM | RAIO | Corrente em Cadeia | 4 | 1 | P3 | corpo + ponta = base beam_raio |
| BEAM | RAIO | Relâmpago | 4 | 4 | P3 | corpo + ponta = base beam_raio |
| BEAM | VOID | Lança do Vazio | 1 | 1 | P3 | corpo + ponta (próprios) |
| BUFF | ARCANO | Amplificar Magia | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | ARCANO | Conjuração Perfeita (fora de rotação) | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | ARCANO | Contrafeitiço | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | ARCANO | Escudo Arcano | 1 | 1 | P3 | aura sobre o lutador |
| BUFF | CAOS | Mutação | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | FOGO | Escudo de Brasas (fora de rotação) | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | GRAVITACAO | Levitar | 7 | 2 | P3 | aura sobre o lutador |
| BUFF | LUZ | Anjo Guardião | 0 | 1 | P3 | aura sobre o lutador |
| BUFF | LUZ | Barreira Divina | 2 | 5 | P3 | aura sobre o lutador |
| BUFF | LUZ | Benção (fora de rotação) | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | LUZ | Cura Maior | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | LUZ | Cura Menor (fora de rotação) | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | LUZ | Purificar (fora de rotação) | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | LUZ | Ressurreição | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | NATUREZA | Regeneração | 0 | 0 | P3 | aura sobre o lutador |
| BUFF | RAIO | Sobrecarga | 0 | 1 | P3 | aura sobre o lutador |
| BUFF | SANGUE | Pacto de Sangue | 5 | 1 | P3 | aura sobre o lutador |
| BUFF | TEMPO | Acelerar | 13 | 5 | P2 | aura sobre o lutador |
| BUFF | TEMPO | Previsão | 1 | 1 | P3 | aura sobre o lutador |
| BUFF | TEMPO | Reverter | 0 | 1 | P3 | aura sobre o lutador |
| BUFF | DEFAULT | Determinação | 10 | 8 | P2 | aura sobre o lutador |
| BUFF | DEFAULT | Golpe do Executor | 22 | 5 | P2 | aura sobre o lutador |
| BUFF | DEFAULT | Grito de Guerra | 1 | 1 | P3 | aura sobre o lutador |
| BUFF | DEFAULT | Reflexo Espelhado | 4 | 2 | P3 | aura sobre o lutador |
| BUFF | DEFAULT | Velocidade Arcana | 14 | 14 | P2 | aura sobre o lutador |
| BUFF | DEFAULT | Último Suspiro | 1 | 2 | P3 | aura sobre o lutador |
| CHANNEL | NATUREZA | Fotossíntese | 12 | 2 | P2 | aura sobre o lutador |
| CHANNEL | RAIO | Fúria do Trovão | 3 | 3 | P3 | aura sobre o lutador |
| CHANNEL | SANGUE | Transfusão | 0 | 0 | P3 | aura sobre o lutador |
| DASH | ARCANO | Portal Arcano | 6 | 3 | P3 | portal arcano (par de portais) |
| DASH | RAIO | Teleporte Relâmpago | 25 | 11 | P2 | estouro de raio na saída e na chegada — rastro/estouro do dash |
| DASH | TREVAS | Portal Sombrio | 5 | 7 | P3 | portal sombrio (par de portais) |
| DASH | VOID | Passo do Vazio | 2 | 2 | P3 | piscada de vazio (some e reaparece) — rastro/estouro do dash |
| DASH | DEFAULT | Avanço Brutal | 70 | 25 | P1 | rastro de investida no chão (a área de dano do avanço) — rastro/estouro do dash |
| DASH | DEFAULT | Troca de Almas | 19 | 5 | P2 | troca de almas (dois espíritos trocando de lugar) |
| PROJETIL | ARCANO | Disparo de Mana (fora de rotação) | 0 | 0 | P3 | voo = base projetil_arcano; impacto = impacto_arcano |
| PROJETIL | ARCANO | Mísseis Arcanos | 1 | 1 | P3 | voo (própria); impacto = impacto_arcano |
| PROJETIL | ARCANO | Roubar Magia (fora de rotação) | 2 | 0 | P3 | voo = base projetil_arcano; impacto = impacto_arcano |
| PROJETIL | CAOS | Chama Caótica | 0 | 1 | P3 | voo = base projetil_caos; impacto = impacto_caos |
| PROJETIL | CAOS | Instabilidade | 1 | 2 | P3 | voo = base projetil_caos; impacto = impacto_caos |
| PROJETIL | CAOS | Roleta Russa | 9 | 1 | P3 | voo (própria); impacto = impacto_caos |
| PROJETIL | FOGO | Bola de Fogo | 0 | 0 | P3 | voo = base projetil_fogo; impacto = impacto_fogo |
| PROJETIL | FOGO | Combustão Espontânea | 1 | 0 | P3 | voo = base projetil_fogo; impacto = impacto_fogo |
| PROJETIL | FOGO | Lança de Fogo | 1 | 1 | P3 | voo (própria); impacto = impacto_fogo |
| PROJETIL | FOGO | Meteoro | 5 | 1 | P3 | voo (própria); explosão (área) própria; impacto = impacto_fogo |
| PROJETIL | GELO | Cone de Gelo | 1 | 1 | P3 | voo (própria); impacto = impacto_gelo |
| PROJETIL | GELO | Estilhaço de Gelo (fora de rotação) | 0 | 0 | P3 | voo (própria); impacto = impacto_gelo |
| PROJETIL | GELO | Lança de Gelo | 0 | 2 | P3 | voo (própria); impacto = impacto_gelo |
| PROJETIL | GELO | Morte Glacial | 0 | 2 | P3 | voo = base projetil_gelo; impacto = impacto_gelo |
| PROJETIL | GELO | Prisão de Gelo | 1 | 2 | P3 | voo = base projetil_gelo; impacto = impacto_gelo |
| PROJETIL | GRAVITACAO | Colapso | 7 | 4 | P3 | voo (própria); explosão (área) própria; impacto = impacto_gravitacao |
| PROJETIL | LUZ | Smite | 4 | 1 | P3 | voo = base projetil_luz; impacto = impacto_luz |
| PROJETIL | NATUREZA | Dardo Venenoso | 2 | 4 | P3 | voo (própria); impacto = impacto_natureza |
| PROJETIL | NATUREZA | Espinhos | 1 | 0 | P3 | voo (própria); impacto = impacto_natureza |
| PROJETIL | NATUREZA | Praga | 12 | 3 | P2 | voo = base projetil_natureza; impacto = impacto_natureza |
| PROJETIL | RAIO | Corrente Elétrica | 1 | 1 | P3 | voo = base projetil_raio; impacto = impacto_raio |
| PROJETIL | RAIO | Mjolnir | 21 | 5 | P2 | voo (própria); impacto = impacto_raio |
| PROJETIL | SANGUE | Estilhaço Vermelho | 2 | 1 | P3 | voo (própria); impacto = impacto_sangue |
| PROJETIL | SANGUE | Lâmina de Sangue | 9 | 1 | P3 | voo (própria); impacto = impacto_sangue |
| PROJETIL | TEMPO | Eco Temporal | 2 | 2 | P3 | voo (própria); impacto = impacto_tempo |
| PROJETIL | TEMPO | Idade Acelerada | 7 | 3 | P3 | voo (própria); impacto = impacto_tempo |
| PROJETIL | TREVAS | Esfera Sombria | 4 | 3 | P3 | voo = base projetil_trevas; impacto = impacto_trevas |
| PROJETIL | TREVAS | Maldição | 10 | 2 | P2 | voo = base projetil_trevas; impacto = impacto_trevas |
| PROJETIL | TREVAS | Necrose | 0 | 0 | P3 | voo = base projetil_trevas; impacto = impacto_trevas |
| PROJETIL | TREVAS | Possessão | 5 | 5 | P3 | voo (própria); impacto = impacto_trevas |
| PROJETIL | DEFAULT | Bomba Relógio | 18 | 0 | P2 | voo (própria); explosão (área) própria; impacto = impacto_default |
| PROJETIL | DEFAULT | Execução | 2 | 1 | P3 | voo (própria); impacto = impacto_default |
| PROJETIL | DEFAULT | Impacto Sônico | 35 | 12 | P2 | voo (própria); impacto = impacto_default |
| PROJETIL | DEFAULT | Link de Vida | 4 | 3 | P3 | voo (própria); impacto = impacto_default |
| SUMMON | FOGO | Fênix | 4 | 1 | P3 | corpo do summon |
| SUMMON | NATUREZA | Ira da Floresta | 10 | 2 | P2 | corpo do summon |
| SUMMON | DEFAULT | Cópia Sombria | 2 | 1 | P3 | corpo do summon |
| SUMMON | DEFAULT | Invocação: Espírito | 7 | 1 | P3 | corpo do summon |
| TRANSFORM | GELO | Avatar de Gelo | 0 | 1 | P3 | aura sobre o lutador |
| TRANSFORM | RAIO | Forma Relâmpago | 2 | 0 | P3 | aura sobre o lutador |
| TRANSFORM | SANGUE | Forma Sanguinária | 23 | 2 | P2 | aura sobre o lutador |
| TRAP | FOGO | Muro Ardente | 1 | 1 | P3 | segmento da barreira |
| TRAP | GELO | Muralha de Gelo | 0 | 4 | P3 | segmento da barreira |
| TRAP | NATUREZA | Barreira de Espinhos | 1 | 0 | P3 | segmento da barreira |

### Peças por skill

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `skill_explosao_arcana` | Explosão Arcana (genérica: usa a base area_arcano). *(opcional)* | `efeitos/pecas/skills/explosao_arcana.png` | `efeitos/skills/explosao_arcana.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 3/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_apocalipse` | Apocalipse: chuva de meteoros (aviso longo + quedas) (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/apocalipse.png` | `efeitos/skills/apocalipse.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_apocalipse_erupcao` | Apocalipse: a erupção/queda quando a área ativa (ativ 0→1). | `efeitos/folhas/skills/apocalipse_erupcao.png` | `efeitos/skills/apocalipse.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_explosao_do_caos` | Explosão do Caos (genérica: usa a base area_caos). *(opcional)* | `efeitos/pecas/skills/explosao_do_caos.png` | `efeitos/skills/explosao_do_caos.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 10/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_explosao_nova` | Explosão Nova (genérica: usa a base area_fogo). *(opcional)* | `efeitos/pecas/skills/explosao_nova.png` | `efeitos/skills/explosao_nova.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_inferno` | Inferno (genérica: usa a base area_fogo). *(opcional)* | `efeitos/pecas/skills/inferno.png` | `efeitos/skills/inferno.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 9/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_pilar_de_fogo` | Pilar de Fogo: coluna de fogo que sobe do chão (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/pilar_de_fogo.png` | `efeitos/skills/pilar_de_fogo.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 10/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_pilar_de_fogo_erupcao` | Pilar de Fogo: a erupção/queda quando a área ativa (ativ 0→1). | `efeitos/folhas/skills/pilar_de_fogo_erupcao.png` | `efeitos/skills/pilar_de_fogo.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P2 | cast em 10/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_nevasca` | Nevasca: tempestade de neve vista de cima (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/nevasca.png` | `efeitos/skills/nevasca.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_shatter` | Shatter (genérica: usa a base area_gelo). *(opcional)* | `efeitos/pecas/skills/shatter.png` | `efeitos/skills/shatter.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_zero_absoluto` | Zero Absoluto (genérica: usa a base area_gelo). *(opcional)* | `efeitos/pecas/skills/zero_absoluto.png` | `efeitos/skills/zero_absoluto.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_buraco_negro` | Buraco Negro: vórtice escuro girando (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/buraco_negro.png` | `efeitos/skills/buraco_negro.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 3/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_campo_de_gravidade` | Campo de Gravidade (genérica: usa a base area_gravitacao). *(opcional)* | `efeitos/pecas/skills/campo_de_gravidade.png` | `efeitos/skills/campo_de_gravidade.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P2 | cast em 13/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_pulso_gravitacional` | Pulso Gravitacional (genérica: usa a base area_gravitacao). *(opcional)* | `efeitos/pecas/skills/pulso_gravitacional.png` | `efeitos/skills/pulso_gravitacional.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 6/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_repulsao` | Repulsão (genérica: usa a base area_gravitacao). *(opcional)* | `efeitos/pecas/skills/repulsao.png` | `efeitos/skills/repulsao.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 9/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_julgamento_celestial` | Julgamento Celestial: 5 pilares de luz descendo do céu (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/julgamento_celestial.png` | `efeitos/skills/julgamento_celestial.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 5/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_julgamento_celestial_erupcao` | Julgamento Celestial: a erupção/queda quando a área ativa (ativ 0→1). | `efeitos/folhas/skills/julgamento_celestial_erupcao.png` | `efeitos/skills/julgamento_celestial.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P3 | cast em 5/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_esporos_alucinogenos` | Esporos Alucinógenos: nuvem de esporos rosados (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/esporos_alucinogenos.png` | `efeitos/skills/esporos_alucinogenos.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 21/95 lutas; no kit de 6 dos 88 do banco | nenhuma |
| `skill_nuvem_toxica` | Nuvem Tóxica: nuvem verde de veneno (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/nuvem_toxica.png` | `efeitos/skills/nuvem_toxica.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 16/95 lutas; no kit de 6 dos 88 do banco | nenhuma |
| `skill_raizes` | Raízes: raízes que prendem (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/raizes.png` | `efeitos/skills/raizes.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 11/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_wrath_of_nature` | Wrath of Nature: raízes e espinhos que brotam (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/wrath_of_nature.png` | `efeitos/skills/wrath_of_nature.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 8/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_wrath_of_nature_erupcao` | Wrath of Nature: a erupção/queda quando a área ativa (ativ 0→1). | `efeitos/folhas/skills/wrath_of_nature_erupcao.png` | `efeitos/skills/wrath_of_nature.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P3 | cast em 8/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_campo_eletrico` | Campo Elétrico (genérica: usa a base area_raio). *(opcional)* | `efeitos/pecas/skills/campo_eletrico.png` | `efeitos/skills/campo_eletrico.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 3/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_julgamento_de_thor` | Julgamento de Thor: raio que cai do céu num círculo (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/julgamento_de_thor.png` | `efeitos/skills/julgamento_de_thor.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_julgamento_de_thor_erupcao` | Julgamento de Thor: a erupção/queda quando a área ativa (ativ 0→1). | `efeitos/folhas/skills/julgamento_de_thor_erupcao.png` | `efeitos/skills/julgamento_de_thor.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_tempestade` | Tempestade: nuvem de tempestade com raios (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/tempestade.png` | `efeitos/skills/tempestade.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_ritual_carmesim` | Ritual Carmesim: círculo ritual de sangue (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/ritual_carmesim.png` | `efeitos/skills/ritual_carmesim.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P1 | cast em 49/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_parar_o_tempo` | Parar o Tempo: mostrador de relógio parado no chão (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/parar_o_tempo.png` | `efeitos/skills/parar_o_tempo.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P2 | cast em 11/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_slow_motion` | Slow Motion (genérica: usa a base area_tempo). *(opcional)* | `efeitos/pecas/skills/slow_motion.png` | `efeitos/skills/slow_motion.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 7/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_colheita_de_almas` | Colheita de Almas (genérica: usa a base area_trevas). *(opcional)* | `efeitos/pecas/skills/colheita_de_almas.png` | `efeitos/skills/colheita_de_almas.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 0/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_explosao_necrotica` | Explosão Necrótica (genérica: usa a base area_trevas). *(opcional)* | `efeitos/pecas/skills/explosao_necrotica.png` | `efeitos/skills/explosao_necrotica.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 3/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_medo_profundo` | Medo Profundo (genérica: usa a base area_trevas). *(opcional)* | `efeitos/pecas/skills/medo_profundo.png` | `efeitos/skills/medo_profundo.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 4/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_fenda_do_vazio` | Fenda do Vazio (genérica: usa a base area_void). *(opcional)* | `efeitos/pecas/skills/fenda_do_vazio.png` | `efeitos/skills/fenda_do_vazio.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_tentaculos_do_vazio` | Tentáculos do Vazio: tentáculos saindo do chão (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/tentaculos_do_vazio.png` | `efeitos/skills/tentaculos_do_vazio.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_furia_giratoria` | Fúria Giratória: redemoinho de lâminas (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/furia_giratoria.png` | `efeitos/skills/furia_giratoria.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 9/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_provocar` | Provocar: onda de provocação (anel vermelho com marcas) (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/provocar.png` | `efeitos/skills/provocar.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 13/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_sacrificio` | Sacrifício: círculo de sacrifício (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/sacrificio.png` | `efeitos/skills/sacrificio.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P2 | cast em 14/95 lutas; no kit de 8 dos 88 do banco | nenhuma |
| `skill_terremoto` | Terremoto: rachaduras no chão com pedras (peça do chão; o aviso é ela apagada). | `efeitos/pecas/skills/terremoto.png` | `efeitos/skills/terremoto.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P3 | cast em 7/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_desintegrar_corpo` | Desintegrar: corpo do feixe (genérico: usa a base beam_arcano_corpo). *(opcional)* | `efeitos/pecas/skills/desintegrar_corpo.png` | `efeitos/skills/desintegrar.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_desintegrar_ponta` | Desintegrar: ponta do feixe (genérico: usa a base beam_arcano_ponta). *(opcional)* | `efeitos/pecas/skills/desintegrar_ponta.png` | `efeitos/skills/desintegrar.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_chamas_do_dragao_corpo` | Chamas do Dragão: corpo do feixe (jato de fogo de dragão). | `efeitos/pecas/skills/chamas_do_dragao_corpo.png` | `efeitos/skills/chamas_do_dragao.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_chamas_do_dragao_ponta` | Chamas do Dragão: ponta do feixe (jato de fogo de dragão). | `efeitos/pecas/skills/chamas_do_dragao_ponta.png` | `efeitos/skills/chamas_do_dragao.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_raio_sagrado_corpo` | Raio Sagrado: corpo do feixe (genérico: usa a base beam_luz_corpo). *(opcional)* | `efeitos/pecas/skills/raio_sagrado_corpo.png` | `efeitos/skills/raio_sagrado.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | cast em 5/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_raio_sagrado_ponta` | Raio Sagrado: ponta do feixe (genérico: usa a base beam_luz_ponta). *(opcional)* | `efeitos/pecas/skills/raio_sagrado_ponta.png` | `efeitos/skills/raio_sagrado.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | cast em 5/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_corrente_em_cadeia_corpo` | Corrente em Cadeia: corpo do feixe (genérico: usa a base beam_raio_corpo). *(opcional)* | `efeitos/pecas/skills/corrente_em_cadeia_corpo.png` | `efeitos/skills/corrente_em_cadeia.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_corrente_em_cadeia_ponta` | Corrente em Cadeia: ponta do feixe (genérico: usa a base beam_raio_ponta). *(opcional)* | `efeitos/pecas/skills/corrente_em_cadeia_ponta.png` | `efeitos/skills/corrente_em_cadeia.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_relampago_corpo` | Relâmpago: corpo do feixe (genérico: usa a base beam_raio_corpo). *(opcional)* | `efeitos/pecas/skills/relampago_corpo.png` | `efeitos/skills/relampago.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_relampago_ponta` | Relâmpago: ponta do feixe (genérico: usa a base beam_raio_ponta). *(opcional)* | `efeitos/pecas/skills/relampago_ponta.png` | `efeitos/skills/relampago.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_lanca_do_vazio_corpo` | Lança do Vazio: corpo do feixe (lança de vazio esticada). | `efeitos/pecas/skills/lanca_do_vazio_corpo.png` | `efeitos/skills/lanca_do_vazio.tscn` | sim | peca | 1 | 1024x128, faixa horizontal repetível em +x | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_lanca_do_vazio_ponta` | Lança do Vazio: ponta do feixe (lança de vazio esticada). | `efeitos/pecas/skills/lanca_do_vazio_ponta.png` | `efeitos/skills/lanca_do_vazio.tscn` | sim | peca | 1 | 256x256, a ponta/impacto do feixe | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_amplificar_magia` | Amplificar Magia: aura/marca sobre o lutador enquanto dura (Próximas magias +50% dano e área). | `lutadores/buffs/amplificar_magia.png` | `(proposto) lutadores/buffs/amplificar_magia.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_conjuracao_perfeita` | Conjuração Perfeita: aura/marca sobre o lutador enquanto dura (Skills sem cooldown por 10s). | `lutadores/buffs/conjuracao_perfeita.png` | `(proposto) lutadores/buffs/conjuracao_perfeita.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_contrafeitico` | Contrafeitiço: aura/marca sobre o lutador enquanto dura (Reflete a próxima skill inimiga). | `lutadores/buffs/contrafeitico.png` | `(proposto) lutadores/buffs/contrafeitico.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_escudo_arcano` | Escudo Arcano: aura/marca sobre o lutador enquanto dura (Escudo que reflete projéteis). | `lutadores/buffs/escudo_arcano.png` | `(proposto) lutadores/buffs/escudo_arcano.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 1/95 lutas; cast em 1/95 lutas; no kit de 1 dos 88 do banco | vetor |
| `skill_mutacao` | Mutação: aura/marca sobre o lutador enquanto dura (Stats aleatórios (pode ser bom ou ruim)). | `lutadores/buffs/mutacao.png` | `(proposto) lutadores/buffs/mutacao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_escudo_de_brasas` | Escudo de Brasas: aura/marca sobre o lutador enquanto dura (Escudo que queima quem ataca corpo a corpo). | `lutadores/buffs/escudo_de_brasas.png` | `(proposto) lutadores/buffs/escudo_de_brasas.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | vetor |
| `skill_levitar` | Levitar: aura/marca sobre o lutador enquanto dura (Flutua no ar - imune a efeitos terrestres). | `lutadores/buffs/levitar.png` | `(proposto) lutadores/buffs/levitar.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 7/95 lutas; cast em 7/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_anjo_guardiao` | Anjo Guardião: aura/marca sobre o lutador enquanto dura (Previne morte uma vez (HP mínimo 1)). | `lutadores/buffs/anjo_guardiao.png` | `(proposto) lutadores/buffs/anjo_guardiao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_barreira_divina` | Barreira Divina: aura/marca sobre o lutador enquanto dura (Escudo que reflete 30% do dano). | `lutadores/buffs/barreira_divina.png` | `(proposto) lutadores/buffs/barreira_divina.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 2/95 lutas; cast em 2/95 lutas; no kit de 5 dos 88 do banco | vetor |
| `skill_bencao` | Benção: aura/marca sobre o lutador enquanto dura (Bênção que aumenta cura e regenera). | `lutadores/buffs/bencao.png` | `(proposto) lutadores/buffs/bencao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_cura_maior` | Cura Maior: aura/marca sobre o lutador enquanto dura (Cura massiva + remove 2 debuffs). | `lutadores/buffs/cura_maior.png` | `(proposto) lutadores/buffs/cura_maior.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_cura_menor` | Cura Menor: aura/marca sobre o lutador enquanto dura (Recupera vida instantaneamente). | `lutadores/buffs/cura_menor.png` | `(proposto) lutadores/buffs/cura_menor.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_purificar` | Purificar: aura/marca sobre o lutador enquanto dura (Remove TODOS debuffs + imunidade). | `lutadores/buffs/purificar.png` | `(proposto) lutadores/buffs/purificar.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_ressurreicao` | Ressurreição: aura/marca sobre o lutador enquanto dura (Revive aliado com 30% HP (ou self se morrer)). | `lutadores/buffs/ressurreicao.png` | `(proposto) lutadores/buffs/ressurreicao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_regeneracao` | Regeneração: aura/marca sobre o lutador enquanto dura (Regenera vida ao longo do tempo). | `lutadores/buffs/regeneracao.png` | `(proposto) lutadores/buffs/regeneracao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_sobrecarga` | Sobrecarga: aura/marca sobre o lutador enquanto dura (Acelera drasticamente mas recebe mais dano). | `lutadores/buffs/sobrecarga.png` | `(proposto) lutadores/buffs/sobrecarga.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_pacto_de_sangue` | Pacto de Sangue: aura/marca sobre o lutador enquanto dura (Sacrifica HP por poder - lifesteal e dano). | `lutadores/buffs/pacto_de_sangue.png` | `(proposto) lutadores/buffs/pacto_de_sangue.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 5/95 lutas; cast em 5/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_acelerar` | Acelerar: aura/marca sobre o lutador enquanto dura (Acelera muito o movimento). | `lutadores/buffs/acelerar.png` | `(proposto) lutadores/buffs/acelerar.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P2 | ativo em 13/95 lutas; cast em 13/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_previsao` | Previsão: aura/marca sobre o lutador enquanto dura (Vê o futuro - esquiva 2 ataques). | `lutadores/buffs/previsao.png` | `(proposto) lutadores/buffs/previsao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 1/95 lutas; cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_reverter` | Reverter: aura/marca sobre o lutador enquanto dura (Volta ao estado de 3s atrás (HP, posição)). | `lutadores/buffs/reverter.png` | `(proposto) lutadores/buffs/reverter.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | verde #00FF00 | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_determinacao` | Determinação: aura/marca sobre o lutador enquanto dura (Cooldowns reduzidos pela metade). | `lutadores/buffs/determinacao.png` | `(proposto) lutadores/buffs/determinacao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | ativo em 10/95 lutas; cast em 10/95 lutas; no kit de 8 dos 88 do banco | nenhuma |
| `skill_golpe_do_executor` | Golpe do Executor: aura/marca sobre o lutador enquanto dura (Próximo ataque causa dano dobrado). | `lutadores/buffs/golpe_do_executor.png` | `(proposto) lutadores/buffs/golpe_do_executor.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | ativo em 22/95 lutas; cast em 22/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_grito_de_guerra` | Grito de Guerra: aura/marca sobre o lutador enquanto dura (Entra em fúria - mais dano, mais vulnerável). | `lutadores/buffs/grito_de_guerra.png` | `(proposto) lutadores/buffs/grito_de_guerra.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 1/95 lutas; cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_reflexo_espelhado` | Reflexo Espelhado: aura/marca sobre o lutador enquanto dura (Reflete 50% do dano recebido). | `lutadores/buffs/reflexo_espelhado.png` | `(proposto) lutadores/buffs/reflexo_espelhado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 4/95 lutas; cast em 4/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_velocidade_arcana` | Velocidade Arcana: aura/marca sobre o lutador enquanto dura (Aumenta velocidade de movimento). | `lutadores/buffs/velocidade_arcana.png` | `(proposto) lutadores/buffs/velocidade_arcana.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | ativo em 14/95 lutas; cast em 14/95 lutas; no kit de 14 dos 88 do banco | nenhuma |
| `skill_ultimo_suspiro` | Último Suspiro: aura/marca sobre o lutador enquanto dura (Ao morrer, revive com 50% HP (passivo)). | `lutadores/buffs/ultimo_suspiro.png` | `(proposto) lutadores/buffs/ultimo_suspiro.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 1/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_fotossintese` | Fotossíntese: aura/marca sobre o lutador enquanto dura (Canaliza para curar (não pode mover)). | `lutadores/canais/fotossintese.png` | `(proposto) lutadores/canais/fotossintese.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | ativo em 12/95 lutas; cast em 12/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_furia_do_trovao` | Fúria do Trovão: aura/marca sobre o lutador enquanto dura (Descarga contínua de trovões - imóvel enquanto canaliza). | `lutadores/canais/furia_do_trovao.png` | `(proposto) lutadores/canais/furia_do_trovao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 3/95 lutas; cast em 3/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_transfusao` | Transfusão: aura/marca sobre o lutador enquanto dura (Dreno canalizado - fere o alvo e cura o conjurador). | `lutadores/canais/transfusao.png` | `(proposto) lutadores/canais/transfusao.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_portal_arcano` | Portal Arcano: portal arcano (par de portais); o Godot gira e abre/fecha pelo prog. | `efeitos/pecas/skills/portal_arcano.png` | `efeitos/skills/portal_arcano.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 6/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_teleporte_relampago` | Teleporte Relâmpago: estouro de raio na saída e na chegada. | `efeitos/folhas/skills/teleporte_relampago.png` | `efeitos/skills/teleporte_relampago.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | cast em 25/95 lutas; no kit de 11 dos 88 do banco | nenhuma |
| `skill_portal_sombrio` | Portal Sombrio: portal sombrio (par de portais); o Godot gira e abre/fecha pelo prog. | `efeitos/pecas/skills/portal_sombrio.png` | `efeitos/skills/portal_sombrio.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | verde #00FF00 | P3 | cast em 5/95 lutas; no kit de 7 dos 88 do banco | nenhuma |
| `skill_passo_do_vazio` | Passo do Vazio: piscada de vazio (some e reaparece). | `efeitos/folhas/skills/passo_do_vazio.png` | `efeitos/skills/passo_do_vazio.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P3 | cast em 2/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_avanco_brutal` | Avanço Brutal: rastro de investida no chão (a área de dano do avanço). | `efeitos/pecas/skills/avanco_brutal.png` | `efeitos/skills/avanco_brutal.tscn` | sim | peca | 1 | 1024x1024 vista de cima, círculo inscrito; o centro do quadro é o centro da área | magenta #FF00FF | P1 | cast em 70/95 lutas; no kit de 25 dos 88 do banco | nenhuma |
| `skill_troca_de_almas` | Troca de Almas: troca de almas (dois espíritos trocando de lugar). | `efeitos/folhas/skills/troca_de_almas.png` | `(proposto) efeitos/skills/troca_de_almas_conjuracao.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | cast em 19/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_disparo_de_mana` | Disparo de Mana em voo (forma genérica: usa a base projetil_arcano). *(opcional)* | `efeitos/pecas/skills/disparo_de_mana.png` | `efeitos/skills/disparo_de_mana.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_misseis_arcanos` | Mísseis Arcanos em voo: míssil arcano pequeno (sai 5, teleguiado). | `efeitos/pecas/skills/misseis_arcanos.png` | `efeitos/skills/misseis_arcanos.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_roubar_magia` | Roubar Magia em voo (forma genérica: usa a base projetil_arcano). *(opcional)* | `efeitos/pecas/skills/roubar_magia.png` | `efeitos/skills/roubar_magia.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 2/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_chama_caotica` | Chama Caótica em voo (forma genérica: usa a base projetil_caos). *(opcional)* | `efeitos/pecas/skills/chama_caotica.png` | `efeitos/skills/chama_caotica.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_instabilidade` | Instabilidade em voo (forma genérica: usa a base projetil_caos). *(opcional)* | `efeitos/pecas/skills/instabilidade.png` | `efeitos/skills/instabilidade.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_roleta_russa` | Roleta Russa em voo: bala de revólver com brilho caótico. | `efeitos/pecas/skills/roleta_russa.png` | `efeitos/skills/roleta_russa.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 9/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_bola_de_fogo` | Bola de Fogo em voo (forma genérica: usa a base projetil_fogo). *(opcional)* | `efeitos/pecas/skills/bola_de_fogo.png` | `efeitos/skills/bola_de_fogo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_combustao_espontanea` | Combustão Espontânea em voo (forma genérica: usa a base projetil_fogo). *(opcional)* | `efeitos/pecas/skills/combustao_espontanea.png` | `efeitos/skills/combustao_espontanea.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_lanca_de_fogo` | Lança de Fogo em voo: lança de fogo alongada. | `efeitos/pecas/skills/lanca_de_fogo.png` | `efeitos/skills/lanca_de_fogo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_meteoro` | Meteoro em voo: rocha em chamas caindo (cauda de fogo). | `efeitos/pecas/skills/meteoro.png` | `efeitos/skills/meteoro.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 5/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_meteoro_explosao` | Meteoro: cratera/explosão do meteoro (o objeto área que nasce no fim). | `efeitos/folhas/skills/meteoro_explosao.png` | `efeitos/skills/meteoro.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | cast em 5/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_cone_de_gelo` | Cone de Gelo em voo: leque de estilhaços de gelo (sai em cone). | `efeitos/pecas/skills/cone_de_gelo.png` | `efeitos/skills/cone_de_gelo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_estilhaco_de_gelo` | Estilhaço de Gelo em voo: estilhaço de gelo. | `efeitos/pecas/skills/estilhaco_de_gelo.png` | `efeitos/skills/estilhaco_de_gelo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 0 dos 88 do banco; fora de rotação | nenhuma |
| `skill_lanca_de_gelo` | Lança de Gelo em voo: lança de gelo cristalina (perfura). | `efeitos/pecas/skills/lanca_de_gelo.png` | `efeitos/skills/lanca_de_gelo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_morte_glacial` | Morte Glacial em voo (forma genérica: usa a base projetil_gelo). *(opcional)* | `efeitos/pecas/skills/morte_glacial.png` | `efeitos/skills/morte_glacial.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_prisao_de_gelo` | Prisão de Gelo em voo (forma genérica: usa a base projetil_gelo). *(opcional)* | `efeitos/pecas/skills/prisao_de_gelo.png` | `efeitos/skills/prisao_de_gelo.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_colapso` | Colapso em voo: mini singularidade (esfera escura com anel). | `efeitos/pecas/skills/colapso.png` | `efeitos/skills/colapso.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 7/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_colapso_explosao` | Colapso: implosão gravitacional (o objeto área que nasce no fim). | `efeitos/folhas/skills/colapso_explosao.png` | `efeitos/skills/colapso.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | verde #00FF00 | P3 | cast em 7/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_smite` | Smite em voo (forma genérica: usa a base projetil_luz). *(opcional)* | `efeitos/pecas/skills/smite.png` | `efeitos/skills/smite.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_dardo_venenoso` | Dardo Venenoso em voo: dardo com a ponta verde pingando. | `efeitos/pecas/skills/dardo_venenoso.png` | `efeitos/skills/dardo_venenoso.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_espinhos` | Espinhos em voo: espinho de planta (sai 3). | `efeitos/pecas/skills/espinhos.png` | `efeitos/skills/espinhos.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_praga` | Praga em voo (forma genérica: usa a base projetil_natureza). *(opcional)* | `efeitos/pecas/skills/praga.png` | `efeitos/skills/praga.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P2 | cast em 12/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_corrente_eletrica` | Corrente Elétrica em voo (forma genérica: usa a base projetil_raio). *(opcional)* | `efeitos/pecas/skills/corrente_eletrica.png` | `efeitos/skills/corrente_eletrica.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_mjolnir` | Mjolnir em voo: martelo de guerra girando com faíscas (volta ao dono). | `efeitos/pecas/skills/mjolnir.png` | `efeitos/skills/mjolnir.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P2 | cast em 21/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_estilhaco_vermelho` | Estilhaço Vermelho em voo: estilhaço cristalino de sangue. | `efeitos/pecas/skills/estilhaco_vermelho.png` | `efeitos/skills/estilhaco_vermelho.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_lamina_de_sangue` | Lâmina de Sangue em voo: lâmina crescente de sangue. | `efeitos/pecas/skills/lamina_de_sangue.png` | `efeitos/skills/lamina_de_sangue.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 9/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_eco_temporal` | Eco Temporal em voo: esfera com ponteiros de relógio. | `efeitos/pecas/skills/eco_temporal.png` | `efeitos/skills/eco_temporal.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 2/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_idade_acelerada` | Idade Acelerada em voo: ampulheta girando. | `efeitos/pecas/skills/idade_acelerada.png` | `efeitos/skills/idade_acelerada.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 7/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_esfera_sombria` | Esfera Sombria em voo (forma genérica: usa a base projetil_trevas). *(opcional)* | `efeitos/pecas/skills/esfera_sombria.png` | `efeitos/skills/esfera_sombria.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 4/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_maldicao` | Maldição em voo (forma genérica: usa a base projetil_trevas). *(opcional)* | `efeitos/pecas/skills/maldicao.png` | `efeitos/skills/maldicao.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P2 | cast em 10/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_necrose` | Necrose em voo (forma genérica: usa a base projetil_trevas). *(opcional)* | `efeitos/pecas/skills/necrose.png` | `efeitos/skills/necrose.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 0/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_possessao` | Possessão em voo: espírito fantasma. | `efeitos/pecas/skills/possessao.png` | `efeitos/skills/possessao.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | verde #00FF00 | P3 | cast em 5/95 lutas; no kit de 5 dos 88 do banco | nenhuma |
| `skill_bomba_relogio` | Bomba Relógio em voo: bomba redonda com mostrador de relógio e pavio. | `efeitos/pecas/skills/bomba_relogio.png` | `efeitos/skills/bomba_relogio.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P2 | cast em 18/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_bomba_relogio_explosao` | Bomba Relógio: explosão da bomba (o objeto área que nasce no fim). | `efeitos/folhas/skills/bomba_relogio_explosao.png` | `efeitos/skills/bomba_relogio.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | cast em 18/95 lutas; no kit de 0 dos 88 do banco | nenhuma |
| `skill_execucao` | Execução em voo: lâmina de execução de energia. | `efeitos/pecas/skills/execucao.png` | `efeitos/skills/execucao.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_impacto_sonico` | Impacto Sônico em voo: onda sonora em arco (crescente). | `efeitos/pecas/skills/impacto_sonico.png` | `efeitos/skills/impacto_sonico.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P2 | cast em 35/95 lutas; no kit de 12 dos 88 do banco | nenhuma |
| `skill_link_de_vida` | Link de Vida em voo: elo de luz (corrente de vida). | `efeitos/pecas/skills/link_de_vida.png` | `efeitos/skills/link_de_vida.tscn` | sim | peca | 1 | 512x512, objeto com ~400 px apontando para +x; o centro do quadro é o centro do projétil | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 3 dos 88 do banco | nenhuma |
| `skill_fenix` | Fênix: fênix de fogo (vista de cima; o Godot balança e vira pelo ang). | `efeitos/pecas/skills/fenix.png` | `efeitos/skills/fenix.tscn` | sim | peca | 1 | 512x512 vista de cima, a frente para +x | magenta #FF00FF | P3 | cast em 4/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_ira_da_floresta` | Ira da Floresta: treant (árvore viva) (vista de cima; o Godot balança e vira pelo ang). | `efeitos/pecas/skills/ira_da_floresta.png` | `efeitos/skills/ira_da_floresta.tscn` | sim | peca | 1 | 512x512 vista de cima, a frente para +x | magenta #FF00FF | P2 | cast em 10/95 lutas; no kit de 2 dos 88 do banco | nenhuma |
| `skill_copia_sombria` | Cópia Sombria: cópia sombria do lutador (vista de cima; o Godot balança e vira pelo ang). *(opcional)* | `efeitos/pecas/skills/copia_sombria.png` | `efeitos/skills/copia_sombria.tscn` | sim | peca | 1 | 512x512 vista de cima, a frente para +x | magenta #FF00FF | P3 | cast em 2/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_invocacao_espirito` | Invocação: Espírito: espírito invocado (vista de cima; o Godot balança e vira pelo ang). | `efeitos/pecas/skills/invocacao_espirito.png` | `efeitos/skills/invocacao_espirito.tscn` | sim | peca | 1 | 512x512 vista de cima, a frente para +x | magenta #FF00FF | P3 | cast em 7/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_avatar_de_gelo` | Avatar de Gelo: aura/marca sobre o lutador enquanto dura (Transforma em elemental de gelo - aura de slow). | `lutadores/transformacoes/avatar_de_gelo.png` | `(proposto) lutadores/transformacoes/avatar_de_gelo.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 0/95 lutas; cast em 0/95 lutas; no kit de 1 dos 88 do banco | vetor |
| `skill_forma_relampago` | Forma Relâmpago: aura/marca sobre o lutador enquanto dura (Transforma em raio puro - atravessa inimigos). | `lutadores/transformacoes/forma_relampago.png` | `(proposto) lutadores/transformacoes/forma_relampago.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | ativo em 2/95 lutas; cast em 2/95 lutas; no kit de 0 dos 88 do banco | vetor |
| `skill_forma_sanguinaria` | Forma Sanguinária: aura/marca sobre o lutador enquanto dura (Forma predadora: rápida, resistente e que fere ao toque). | `lutadores/transformacoes/forma_sanguinaria.png` | `(proposto) lutadores/transformacoes/forma_sanguinaria.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | ativo em 23/95 lutas; cast em 23/95 lutas; no kit de 2 dos 88 do banco | vetor |
| `skill_muro_ardente` | Muro Ardente: segmento de muro de fogo (repetido ao longo da largura). | `efeitos/pecas/skills/muro_ardente.png` | `efeitos/skills/muro_ardente.tscn` | sim | peca | 1 | 512x256 vista de cima, repetível em x | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 1 dos 88 do banco | nenhuma |
| `skill_muralha_de_gelo` | Muralha de Gelo: bloco de muralha de gelo (repetido ao longo da largura). | `efeitos/pecas/skills/muralha_de_gelo.png` | `efeitos/skills/muralha_de_gelo.tscn` | sim | peca | 1 | 512x256 vista de cima, repetível em x | magenta #FF00FF | P3 | cast em 0/95 lutas; no kit de 4 dos 88 do banco | nenhuma |
| `skill_barreira_de_espinhos` | Barreira de Espinhos: segmento de cerca de espinhos (repetido ao longo da largura). | `efeitos/pecas/skills/barreira_de_espinhos.png` | `efeitos/skills/barreira_de_espinhos.tscn` | sim | peca | 1 | 512x256 vista de cima, repetível em x | magenta #FF00FF | P3 | cast em 1/95 lutas; no kit de 0 dos 88 do banco | nenhuma |

## 4. Efeitos gerais

Eventos que viram efeito na tela hoje (`EVENTOS_COM_VFX`): acerto (4 tiers), dano, cura, bloqueio, parry, esquiva, desvio, dash, parede, wall_splat, ko, escudo_quebrou, skill, agarrao_desfecho, obstaculo, explosao e choque. Presença medida em lutas (de 95):

| evento | lutas | total | evento | lutas | total |
|---|---|---|---|---|---|
| tell | 95 | 4961 | movimento | 95 | 3926 |
| acerto | 95 | 3139 | texto | 95 | 3134 |
| projetil_fim | 93 | 2065 | parede | 95 | 1974 |
| plano | 95 | 1864 | dano | 77 | 1263 |
| skill | 95 | 1122 | desvio | 95 | 975 |
| cura | 35 | 660 | explosao | 73 | 559 |
| dash | 93 | 552 | hitstop | 62 | 308 |
| combo | 60 | 197 | wall_splat | 68 | 123 |
| agarrao | 57 | 100 | primeiro_sangue | 95 | 95 |
| ko | 95 | 95 | agarrao_desfecho | 51 | 88 |
| choque | 35 | 65 | bloqueio | 46 | 65 |
| virada | 36 | 49 | parry | 21 | 48 |
| esquiva | 17 | 44 | obstaculo | 13 | 16 |
| escudo_quebrou | 3 | 4 | refletido | 1 | 1 |

**Não precisam de sprite:**

- **Hitstop**: é o mundo parado por 0 a 4 quadros (`estilo.gd`), não um desenho.
- **Números de dano e textos** (`texto`, 3134 nas 95 lutas): decisão `palco-numeros-de-dano` = não.
- **Tremor de câmera, barras de cinema e clarão do K.O.**: procedurais.
- **`tell`, `plano`, `primeiro_sangue`, `combo` e `virada`**: são legenda e callout da edição em Python, não peça do palco.

### acerto

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `acerto_light` | Faísca/estouro do acerto leve (tier do autor). | `efeitos/folhas/acerto_light.png` | `efeitos/eventos/acerto_light.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 1338 acertos em 95 lutas (14.1 por luta) | vetor |
| `acerto_medium` | Faísca/estouro do acerto médio (tier do autor). | `efeitos/folhas/acerto_medium.png` | `efeitos/eventos/acerto_medium.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 1395 acertos em 95 lutas (14.7 por luta) | vetor |
| `acerto_heavy` | Faísca/estouro do acerto pesado (tier do autor). | `efeitos/folhas/acerto_heavy.png` | `efeitos/eventos/acerto_heavy.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 125 acertos em 95 lutas (1.3 por luta) | cc0 |
| `acerto_colossal` | Faísca/estouro do acerto colossal (tier do autor). | `efeitos/folhas/acerto_colossal.png` | `efeitos/eventos/acerto_colossal.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P1 | 281 acertos em 95 lutas (3.0 por luta) | cc0 |
| `acerto_critico` | Acerto crítico (o anel dourado de hoje vira folha própria). | `efeitos/folhas/acerto_critico.png` | `(proposto) efeitos/eventos/acerto_critico.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 102 críticos em 95 lutas | vetor |
| `acerto_corte` | Impacto por arma: corte (talho). *(opcional)* | `efeitos/folhas/acerto_corte.png` | `(proposto) efeitos/eventos/acerto_corte.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | ver arquétipos em Armas | nenhuma |
| `acerto_estocada` | Impacto por arma: estocada (furo). *(opcional)* | `efeitos/folhas/acerto_estocada.png` | `(proposto) efeitos/eventos/acerto_estocada.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | ver arquétipos em Armas | nenhuma |
| `acerto_esmagamento` | Impacto por arma: esmagamento (amassado/onda). *(opcional)* | `efeitos/folhas/acerto_esmagamento.png` | `(proposto) efeitos/eventos/acerto_esmagamento.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | ver arquétipos em Armas | nenhuma |
| `acerto_projetil_arma` | Impacto por arma: projétil de arma cravando. *(opcional)* | `efeitos/folhas/acerto_projetil_arma.png` | `(proposto) efeitos/eventos/acerto_projetil_arma.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | ver arquétipos em Armas | nenhuma |

### evento

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `evento_ko` | K.O.: explosão grande no chão sob o corpo caído. | `efeitos/folhas/ko.png` | `efeitos/eventos/ko.tscn` | sim | folha | 16 | 2048x2048: grade 4x4, 16 quadros de 512x512 | magenta #FF00FF | P1 | 95/95 lutas | cc0 |
| `evento_desvio` | Desvio (a IA leu e saiu): anel de esquiva. | `efeitos/folhas/desvio.png` | `efeitos/eventos/desvio.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 95/95 lutas | vetor |
| `evento_dash` | Dash: poeira e linhas de arrancada. | `efeitos/folhas/dash.png` | `efeitos/eventos/dash.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 93/95 lutas | vetor |
| `evento_parede` | Batida na parede: poeira e lascas. | `efeitos/folhas/parede.png` | `efeitos/eventos/parede.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 95/95 lutas | cc0 |
| `evento_wall_splat` | Wall splat: impacto forte na parede com rachadura. | `efeitos/folhas/wall_splat.png` | `efeitos/eventos/wall_splat.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 68/95 lutas | cc0 |
| `evento_dano` | Dano sem golpe (DoT/encanto): tique. | `efeitos/folhas/dano.png` | `efeitos/eventos/dano.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 77/95 lutas | vetor |
| `evento_agarrao_desfecho` | Desfecho do agarrão (arremesso, joelhada, empurrão, escape). | `efeitos/folhas/agarrao_desfecho.png` | `efeitos/eventos/agarrao_desfecho.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 51/95 lutas | vetor |
| `evento_bloqueio` | Bloqueio: faísca no arco do escudo. | `efeitos/folhas/bloqueio.png` | `efeitos/eventos/bloqueio.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 46/95 lutas | vetor |
| `evento_cura` | Cura: cruzes/brilho subindo. | `efeitos/folhas/cura.png` | `efeitos/eventos/cura.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 35/95 lutas | vetor |
| `evento_choque` | Choque de projéteis/armas no ar (duas cores). | `efeitos/folhas/choque.png` | `efeitos/eventos/choque.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 35/95 lutas | vetor |
| `evento_parry` | Parry: faísca dourada de aparo. | `efeitos/folhas/parry.png` | `efeitos/eventos/parry.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 21/95 lutas | vetor |
| `evento_esquiva` | Esquiva do Ladino: rastro fantasma. | `efeitos/folhas/esquiva.png` | `efeitos/eventos/esquiva.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 17/95 lutas | vetor |
| `evento_escudo_quebrou` | Escudo quebrando: cacos de vidro/energia. | `efeitos/folhas/escudo_quebrou.png` | `efeitos/eventos/escudo_quebrou.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 | 3/95 lutas | vetor |
| `agarrao_arremesso` | Desfecho do agarrão: arremesso. *(opcional)* | `efeitos/folhas/agarrao_arremesso.png` | `(proposto) efeitos/eventos/agarrao_desfecho_arremesso.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 42 em 95 lutas | nenhuma |
| `agarrao_escape` | Desfecho do agarrão: escape. *(opcional)* | `efeitos/folhas/agarrao_escape.png` | `(proposto) efeitos/eventos/agarrao_desfecho_escape.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 23 em 95 lutas | nenhuma |
| `agarrao_empurrao` | Desfecho do agarrão: empurrao. *(opcional)* | `efeitos/folhas/agarrao_empurrao.png` | `(proposto) efeitos/eventos/agarrao_desfecho_empurrao.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 12 em 95 lutas | nenhuma |
| `agarrao_joelhada` | Desfecho do agarrão: joelhada. *(opcional)* | `efeitos/folhas/agarrao_joelhada.png` | `(proposto) efeitos/eventos/agarrao_desfecho_joelhada.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 11 em 95 lutas | nenhuma |

### movimento

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `movimento_recuperacao` | Movimento: flash do fim do atordoamento. | `efeitos/folhas/movimento_recuperacao.png` | `(proposto) efeitos/eventos/movimento_recuperacao.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 1223 em 95 lutas (12.9 por luta) | nenhuma |
| `movimento_dash` | Movimento: afterimage/rastro do dash. | `efeitos/folhas/movimento_dash.png` | `(proposto) efeitos/eventos/movimento_dash.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 815 em 95 lutas (8.6 por luta) | nenhuma |
| `movimento_knockback` | Movimento: linhas de empurrão. | `efeitos/folhas/movimento_knockback.png` | `(proposto) efeitos/eventos/movimento_knockback.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 766 em 95 lutas (8.1 por luta) | nenhuma |
| `movimento_pulo` | Movimento: poeira do pulo. | `efeitos/folhas/movimento_pulo.png` | `(proposto) efeitos/eventos/movimento_pulo.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 619 em 95 lutas (6.5 por luta) | nenhuma |
| `movimento_aterrissagem` | Movimento: poeira da aterrissagem. | `efeitos/folhas/movimento_aterrissagem.png` | `(proposto) efeitos/eventos/movimento_aterrissagem.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 341 em 95 lutas (3.6 por luta) | nenhuma |
| `movimento_corrida` | Movimento: linhas de velocidade. | `efeitos/folhas/movimento_corrida.png` | `(proposto) efeitos/eventos/movimento_corrida.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 162 em 95 lutas (1.7 por luta) | nenhuma |

### projétil

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `projetil_fim_expirou` | Fim de projétil: projétil que some no fim da vida (puff). | `efeitos/folhas/projetil_fim_expirou.png` | `(proposto) efeitos/eventos/projetil_fim_expirou.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 305 em 95 lutas | nenhuma |
| `projetil_fim_bloqueado` | Fim de projétil: projétil barrado (escudo, parry, dash). | `efeitos/folhas/projetil_fim_bloqueado.png` | `(proposto) efeitos/eventos/projetil_fim_bloqueado.tscn` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P1 | 104 em 95 lutas | nenhuma |
| `rastro_projetil` | Rastro do projétil em voo (tingido pelo elemento). *(opcional)* | `efeitos/texturas/rastro_projetil.png` | `` | não | peca | 1 | 1024x128 faixa em +x, do transparente (esquerda) ao cheio (direita) | magenta #FF00FF | P2 |  | vetor |

### sangue

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `sangue_respingo` | Respingo de sangue no acerto forte. *(opcional)* | `efeitos/folhas/sangue_respingo.png` | `(proposto) dentro de eventos/acerto_<tier>` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | o render antigo tinha; o palco não | nenhuma |
| `sangue_mancha_chao` | Mancha/cicatriz no chão deixada pelo golpe ou elemento. *(opcional)* | `efeitos/pecas/mancha_chao.png` | `` | não | peca | 1 | 512x512 vista de cima | magenta #FF00FF | P3 |  | cc0 |

### invocação

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `summon_surgir` | Surgir/sumir de invocação e de armadilha (fumaça + brilho). | `efeitos/folhas/surgir.png` | `` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | summons em 21/95 lutas | nenhuma |
| `trap_destruicao` | Barreira/armadilha destruída (cacos). | `efeitos/folhas/trap_destruicao.png` | `` | não | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P3 |  | nenhuma |

### status

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `status_envenenado` | Status ENVENENADO (dot; hoje particula na cor do status, glifo ☠). | `lutadores/status/envenenado.png` | `(proposto) lutadores/status/envenenado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 37/95 lutas | vetor |
| `status_sangrando` | Status SANGRANDO (dot; hoje particula na cor do status, glifo ▽). | `lutadores/status/sangrando.png` | `(proposto) lutadores/status/sangrando.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 9/95 lutas | vetor |
| `status_queimando` | Status QUEIMANDO (dot; hoje particula na cor do status, glifo ✹). | `lutadores/status/queimando.png` | `(proposto) lutadores/status/queimando.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 22/95 lutas | vetor |
| `status_corroendo` | Status CORROENDO (dot; hoje anel na cor do status, glifo ≈). | `lutadores/status/corroendo.png` | `(proposto) lutadores/status/corroendo.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_necrose` | Status NECROSE (dot; hoje anel na cor do status, glifo ◆). | `lutadores/status/necrose.png` | `(proposto) lutadores/status/necrose.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_maldito` | Status MALDITO (dot; hoje anel na cor do status, glifo ✖). | `lutadores/status/maldito.png` | `(proposto) lutadores/status/maldito.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 2/95 lutas | vetor |
| `status_congelado` | Status CONGELADO (cc; hoje tint na cor do status, glifo ❄). | `lutadores/status/congelado.png` | `(proposto) lutadores/status/congelado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 5/95 lutas | vetor |
| `status_lento` | Status LENTO (cc; hoje anel na cor do status, glifo ↓). | `lutadores/status/lento.png` | `(proposto) lutadores/status/lento.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P1 | 63/95 lutas | vetor |
| `status_atordoado` | Status ATORDOADO (cc; hoje anel na cor do status, glifo ⚡). | `lutadores/status/atordoado.png` | `(proposto) lutadores/status/atordoado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P1 | 95/95 lutas | vetor |
| `status_paralisia` | Status PARALISIA (cc; hoje anel na cor do status, glifo ~). | `lutadores/status/paralisia.png` | `(proposto) lutadores/status/paralisia.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_enraizado` | Status ENRAIZADO (cc; hoje particula na cor do status, glifo ✿). | `lutadores/status/enraizado.png` | `(proposto) lutadores/status/enraizado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 13/95 lutas | vetor |
| `status_silenciado` | Status SILENCIADO (cc; hoje anel na cor do status, glifo ⛔). | `lutadores/status/silenciado.png` | `(proposto) lutadores/status/silenciado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 4/95 lutas | vetor |
| `status_cego` | Status CEGO (debuff; hoje anel na cor do status, glifo ◐). | `lutadores/status/cego.png` | `(proposto) lutadores/status/cego.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 5/95 lutas | vetor |
| `status_medo` | Status MEDO (cc; hoje anel na cor do status, glifo !). | `lutadores/status/medo.png` | `(proposto) lutadores/status/medo.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 4/95 lutas | vetor |
| `status_charme` | Status CHARME (controle_mental; hoje anel na cor do status, glifo ♥). | `lutadores/status/charme.png` | `(proposto) lutadores/status/charme.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 20/95 lutas | vetor |
| `status_sono` | Status SONO (cc; hoje anel na cor do status, glifo ☾). | `lutadores/status/sono.png` | `(proposto) lutadores/status/sono.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_knock_up` | Status KNOCK_UP (cc; hoje anel na cor do status, glifo ↑). | `lutadores/status/knock_up.png` | `(proposto) lutadores/status/knock_up.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_tempo_parado` | Status TEMPO_PARADO (cc; hoje tint na cor do status, glifo ⌛). | `lutadores/status/tempo_parado.png` | `(proposto) lutadores/status/tempo_parado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 11/95 lutas | vetor |
| `status_fraco` | Status FRACO (debuff; hoje anel na cor do status, glifo ○). | `lutadores/status/fraco.png` | `(proposto) lutadores/status/fraco.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_vulneravel` | Status VULNERAVEL (debuff; hoje anel na cor do status, glifo ⚠). | `lutadores/status/vulneravel.png` | `(proposto) lutadores/status/vulneravel.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P2 | 38/95 lutas | vetor |
| `status_exausto` | Status EXAUSTO (debuff; hoje anel na cor do status, glifo ▤). | `lutadores/status/exausto.png` | `(proposto) lutadores/status/exausto.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 2/95 lutas | vetor |
| `status_marcado` | Status MARCADO (debuff; hoje anel na cor do status, glifo ⊕). | `lutadores/status/marcado.png` | `(proposto) lutadores/status/marcado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_exposto` | Status EXPOSTO (debuff; hoje anel na cor do status, glifo △). | `lutadores/status/exposto.png` | `(proposto) lutadores/status/exposto.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 2/95 lutas | vetor |
| `status_bomba_relogio` | Status BOMBA_RELOGIO (especial; hoje anel na cor do status, glifo ⊗). | `lutadores/status/bomba_relogio.png` | `(proposto) lutadores/status/bomba_relogio.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 6/95 lutas | vetor |
| `status_link_alma` | Status LINK_ALMA (especial; hoje anel na cor do status, glifo ✦). | `lutadores/status/link_alma.png` | `(proposto) lutadores/status/link_alma.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 1/95 lutas | vetor |
| `status_possesso` | Status POSSESSO (controle_mental; hoje tint na cor do status, glifo ★). | `lutadores/status/possesso.png` | `(proposto) lutadores/status/possesso.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 2/95 lutas | vetor |
| `status_trocar_pos` | Status TROCAR_POS (transporte; hoje anel na cor do status, glifo ◎). | `lutadores/status/trocar_pos.png` | `(proposto) lutadores/status/trocar_pos.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_puxado` | Status PUXADO (transporte; hoje anel na cor do status, glifo ●). | `lutadores/status/puxado.png` | `(proposto) lutadores/status/puxado.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `status_vortex` | Status VORTEX (transporte; hoje anel na cor do status, glifo @). | `lutadores/status/vortex.png` | `(proposto) lutadores/status/vortex.tscn` | não | peca | 1 | 512x512, anel/aura que envolve a bolinha (a bolinha ocupa o círculo central de ~300 px) | magenta #FF00FF | P3 | 0/95 lutas | vetor |

## 5. Arena

São 20 arenas e 17 temas (`neural_fights/core/arena.py`). O duelo 9:16 usa as verticais. Medido: Poço do Templo (ruinas) em 40 lutas, Duto de Serviço (cyberpunk) em 28 e Salão da Torre (castelo) em 27, de 95. Nos 42 duelos dos fight.json: Torre 15, Poço 12, Duto 11 e Ringue 4.

Hoje a `arena_padrao.gd` desenha chão (a pedra CC0), paredes, borda e obstáculos por código. A arena própria entra como `arenas/<nome>.tscn` (`poco_do_templo`, `duto_de_servico`, `salao_da_torre`, `ringue_de_boxe`) ou `arenas/temas/<tema>.tscn`, montada com as peças abaixo. Clima e luz ainda não são desenhados (lacuna 11 da timeline).

### tema

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arena_classico_chao` | Tema classico (Arena Clássica (Arena), Arena Compacta (Arena Pequena)): chão. | `arenas/temas/classico_chao.png` | `arenas/temas/classico.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_classico_parede` | Tema classico (Arena Clássica (Arena), Arena Compacta (Arena Pequena)): parede/borda. | `arenas/temas/classico_parede.png` | `arenas/temas/classico.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_classico_fundo` | Tema classico (Arena Clássica (Arena), Arena Compacta (Arena Pequena)): fundo além das paredes. | `arenas/temas/classico_fundo.png` | `arenas/temas/classico.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_romano_chao` | Tema romano (Coliseu Romano (Coliseu)): chão. | `arenas/temas/romano_chao.png` | `arenas/temas/romano.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_romano_parede` | Tema romano (Coliseu Romano (Coliseu)): parede/borda. | `arenas/temas/romano_parede.png` | `arenas/temas/romano.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_romano_fundo` | Tema romano (Coliseu Romano (Coliseu)): fundo além das paredes. | `arenas/temas/romano_fundo.png` | `arenas/temas/romano.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_japones_chao` | Tema japones (Dojo Sagrado (Dojo)): chão. | `arenas/temas/japones_chao.png` | `arenas/temas/japones.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_japones_parede` | Tema japones (Dojo Sagrado (Dojo)): parede/borda. | `arenas/temas/japones_parede.png` | `arenas/temas/japones.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_japones_fundo` | Tema japones (Dojo Sagrado (Dojo)): fundo além das paredes. | `arenas/temas/japones_fundo.png` | `arenas/temas/japones.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_floresta_chao` | Tema floresta (Clareira Sombria (Floresta)): chão. | `arenas/temas/floresta_chao.png` | `arenas/temas/floresta.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_floresta_parede` | Tema floresta (Clareira Sombria (Floresta)): parede/borda. | `arenas/temas/floresta_parede.png` | `arenas/temas/floresta.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_floresta_fundo` | Tema floresta (Clareira Sombria (Floresta)): fundo além das paredes. | `arenas/temas/floresta_fundo.png` | `arenas/temas/floresta.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_caverna_chao` | Tema caverna (Caverna de Cristais (Caverna)): chão. | `arenas/temas/caverna_chao.png` | `arenas/temas/caverna.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_caverna_parede` | Tema caverna (Caverna de Cristais (Caverna)): parede/borda. | `arenas/temas/caverna_parede.png` | `arenas/temas/caverna.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_caverna_fundo` | Tema caverna (Caverna de Cristais (Caverna)): fundo além das paredes. | `arenas/temas/caverna_fundo.png` | `arenas/temas/caverna.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_medieval_chao` | Tema medieval (Salão do Trono (Castelo)): chão. | `arenas/temas/medieval_chao.png` | `arenas/temas/medieval.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_medieval_parede` | Tema medieval (Salão do Trono (Castelo)): parede/borda. | `arenas/temas/medieval_parede.png` | `arenas/temas/medieval.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_medieval_fundo` | Tema medieval (Salão do Trono (Castelo)): fundo além das paredes. | `arenas/temas/medieval_fundo.png` | `arenas/temas/medieval.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_vulcao_chao` | Tema vulcao (Cratera Vulcânica (Vulcao)): chão. | `arenas/temas/vulcao_chao.png` | `arenas/temas/vulcao.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_vulcao_parede` | Tema vulcao (Cratera Vulcânica (Vulcao)): parede/borda. | `arenas/temas/vulcao_parede.png` | `arenas/temas/vulcao.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_vulcao_fundo` | Tema vulcao (Cratera Vulcânica (Vulcao)): fundo além das paredes. | `arenas/temas/vulcao_fundo.png` | `arenas/temas/vulcao.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_gotico_chao` | Tema gotico (Cemitério Amaldiçoado (Cemiterio)): chão. | `arenas/temas/gotico_chao.png` | `arenas/temas/gotico.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_gotico_parede` | Tema gotico (Cemitério Amaldiçoado (Cemiterio)): parede/borda. | `arenas/temas/gotico_parede.png` | `arenas/temas/gotico.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_gotico_fundo` | Tema gotico (Cemitério Amaldiçoado (Cemiterio)): fundo além das paredes. | `arenas/temas/gotico_fundo.png` | `arenas/temas/gotico.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_scifi_chao` | Tema scifi (Estação Orbital (Espacial)): chão. | `arenas/temas/scifi_chao.png` | `arenas/temas/scifi.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_scifi_parede` | Tema scifi (Estação Orbital (Espacial)): parede/borda. | `arenas/temas/scifi_parede.png` | `arenas/temas/scifi.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_scifi_fundo` | Tema scifi (Estação Orbital (Espacial)): fundo além das paredes. | `arenas/temas/scifi_fundo.png` | `arenas/temas/scifi.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_esporte_chao` | Tema esporte (Ringue de Boxe (Ringue)): chão. | `arenas/temas/esporte_chao.png` | `arenas/temas/esporte.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas; Ringue em 4 dos 42 duelos dos fight.json | cc0 |
| `arena_esporte_parede` | Tema esporte (Ringue de Boxe (Ringue)): parede/borda. | `arenas/temas/esporte_parede.png` | `arenas/temas/esporte.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P2 | 0/95 lutas; Ringue em 4 dos 42 duelos dos fight.json | vetor |
| `arena_esporte_fundo` | Tema esporte (Ringue de Boxe (Ringue)): fundo além das paredes. | `arenas/temas/esporte_fundo.png` | `arenas/temas/esporte.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas; Ringue em 4 dos 42 duelos dos fight.json | vetor |
| `arena_praia_chao` | Tema praia (Praia do Confronto (Praia)): chão. | `arenas/temas/praia_chao.png` | `arenas/temas/praia.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_praia_parede` | Tema praia (Praia do Confronto (Praia)): parede/borda. | `arenas/temas/praia_parede.png` | `arenas/temas/praia.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_praia_fundo` | Tema praia (Praia do Confronto (Praia)): fundo além das paredes. | `arenas/temas/praia_fundo.png` | `arenas/temas/praia.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_ruinas_chao` | Tema ruinas (Templo Esquecido (Templo), Poco do Templo (Poco)): chão. | `arenas/temas/ruinas_chao.png` | `arenas/temas/ruinas.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 40/95 lutas | cc0 |
| `arena_ruinas_parede` | Tema ruinas (Templo Esquecido (Templo), Poco do Templo (Poco)): parede/borda. | `arenas/temas/ruinas_parede.png` | `arenas/temas/ruinas.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P2 | 40/95 lutas | vetor |
| `arena_ruinas_fundo` | Tema ruinas (Templo Esquecido (Templo), Poco do Templo (Poco)): fundo além das paredes. | `arenas/temas/ruinas_fundo.png` | `arenas/temas/ruinas.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 40/95 lutas | vetor |
| `arena_gelo_chao` | Tema gelo (Tundra Congelada (Gelo)): chão. | `arenas/temas/gelo_chao.png` | `arenas/temas/gelo.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_gelo_parede` | Tema gelo (Tundra Congelada (Gelo)): parede/borda. | `arenas/temas/gelo_parede.png` | `arenas/temas/gelo.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_gelo_fundo` | Tema gelo (Tundra Congelada (Gelo)): fundo além das paredes. | `arenas/temas/gelo_fundo.png` | `arenas/temas/gelo.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_inferno_chao` | Tema inferno (Portões do Inferno (Inferno)): chão. | `arenas/temas/inferno_chao.png` | `arenas/temas/inferno.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_inferno_parede` | Tema inferno (Portões do Inferno (Inferno)): parede/borda. | `arenas/temas/inferno_parede.png` | `arenas/temas/inferno.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_inferno_fundo` | Tema inferno (Portões do Inferno (Inferno)): fundo além das paredes. | `arenas/temas/inferno_fundo.png` | `arenas/temas/inferno.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_cyberpunk_chao` | Tema cyberpunk (Beco Neon (Cyberpunk), Duto de Servico (Duto)): chão. | `arenas/temas/cyberpunk_chao.png` | `arenas/temas/cyberpunk.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 28/95 lutas | cc0 |
| `arena_cyberpunk_parede` | Tema cyberpunk (Beco Neon (Cyberpunk), Duto de Servico (Duto)): parede/borda. | `arenas/temas/cyberpunk_parede.png` | `arenas/temas/cyberpunk.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P2 | 28/95 lutas | vetor |
| `arena_cyberpunk_fundo` | Tema cyberpunk (Beco Neon (Cyberpunk), Duto de Servico (Duto)): fundo além das paredes. | `arenas/temas/cyberpunk_fundo.png` | `arenas/temas/cyberpunk.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 28/95 lutas | vetor |
| `arena_labirinto_chao` | Tema labirinto (Labirinto de Pedra (Labirinto)): chão. | `arenas/temas/labirinto_chao.png` | `arenas/temas/labirinto.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 0/95 lutas | cc0 |
| `arena_labirinto_parede` | Tema labirinto (Labirinto de Pedra (Labirinto)): parede/borda. | `arenas/temas/labirinto_parede.png` | `arenas/temas/labirinto.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P3 | 0/95 lutas | vetor |
| `arena_labirinto_fundo` | Tema labirinto (Labirinto de Pedra (Labirinto)): fundo além das paredes. | `arenas/temas/labirinto_fundo.png` | `arenas/temas/labirinto.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 0/95 lutas | vetor |
| `arena_castelo_chao` | Tema castelo (Salao da Torre (Torre)): chão. | `arenas/temas/castelo_chao.png` | `arenas/temas/castelo.tscn` | sim | peca | 1 | 1024x1024 repetível (seamless) nos dois eixos | opaco | P3 | 27/95 lutas | cc0 |
| `arena_castelo_parede` | Tema castelo (Salao da Torre (Torre)): parede/borda. | `arenas/temas/castelo_parede.png` | `arenas/temas/castelo.tscn` | sim | peca | 1 | 1024x256 repetível em x (vista de cima, a face interna para baixo) | opaco | P2 | 27/95 lutas | vetor |
| `arena_castelo_fundo` | Tema castelo (Salao da Torre (Torre)): fundo além das paredes. | `arenas/temas/castelo_fundo.png` | `arenas/temas/castelo.tscn` | sim | peca | 1 | 1080x1920 (9:16), o que aparece além das paredes | opaco | P3 | 27/95 lutas | vetor |

### obstáculos

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `evento_obstaculo` | Obstáculo quebrando: destroços. | `efeitos/folhas/obstaculo.png` | `efeitos/eventos/obstaculo.tscn` | sim | folha | 16 | 1024x1024: grade 4x4, 16 quadros de 256x256 | magenta #FF00FF | P2 | 13/95 lutas | cc0 |
| `obstaculo_altar` | Obstáculo 'altar': altar (arenas: Templo Esquecido). | `arenas/obstaculos/altar.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_arvore` | Obstáculo 'arvore': copa de árvore (arenas: Clareira Sombria). | `arenas/obstaculos/arvore.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_barril` | Obstáculo 'barril': barril (arenas: Beco Neon). | `arenas/obstaculos/barril.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_caixa` | Obstáculo 'caixa': caixote (arenas: Beco Neon, Duto de Servico). | `arenas/obstaculos/caixa.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P2 | 28/95 lutas | vetor |
| `obstaculo_console` | Obstáculo 'console': console (arenas: Estação Orbital). | `arenas/obstaculos/console.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_cripta` | Obstáculo 'cripta': cripta (arenas: Cemitério Amaldiçoado). | `arenas/obstaculos/cripta.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_cristal` | Obstáculo 'cristal': cristal (arenas: Caverna de Cristais). | `arenas/obstaculos/cristal.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_fogo` | Obstáculo 'fogo': fogueira (chão) (arenas: Portões do Inferno). | `arenas/obstaculos/fogo.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_gelo` | Obstáculo 'gelo': bloco de gelo (arenas: Tundra Congelada). | `arenas/obstaculos/gelo.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_lapide` | Obstáculo 'lapide': lápide (arenas: Cemitério Amaldiçoado). | `arenas/obstaculos/lapide.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_lava` | Obstáculo 'lava': poça de lava (chão) (arenas: Cratera Vulcânica). | `arenas/obstaculos/lava.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_nucleo` | Obstáculo 'nucleo': núcleo de energia (arenas: Estação Orbital). | `arenas/obstaculos/nucleo.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_ossos` | Obstáculo 'ossos': pilha de ossos (arenas: Portões do Inferno). | `arenas/obstaculos/ossos.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_painel` | Obstáculo 'painel': painel (arenas: Estação Orbital). | `arenas/obstaculos/painel.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_palmeira` | Obstáculo 'palmeira': palmeira (arenas: Praia do Confronto). | `arenas/obstaculos/palmeira.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_parede` | Obstáculo 'parede': parede interna do labirinto (arenas: Labirinto de Pedra). | `arenas/obstaculos/parede.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_pedra` | Obstáculo 'pedra': pedra (arenas: Clareira Sombria). | `arenas/obstaculos/pedra.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_pilar` | Obstáculo 'pilar': pilar de pedra (cilindro visto de cima) (arenas: Coliseu Romano, Salão do Trono, Labirinto de Pedra, Salao da Torre). | `arenas/obstaculos/pilar.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P2 | 27/95 lutas | vetor |
| `obstaculo_pilar_quebrado` | Obstáculo 'pilar_quebrado': pilar quebrado (arenas: Templo Esquecido, Poco do Templo). | `arenas/obstaculos/pilar_quebrado.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P2 | 40/95 lutas | vetor |
| `obstaculo_rocha` | Obstáculo 'rocha': rocha (arenas: Caverna de Cristais, Cratera Vulcânica, Praia do Confronto). | `arenas/obstaculos/rocha.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_tapete` | Obstáculo 'tapete': tapete (chão, não sólido) (arenas: Salão do Trono). | `arenas/obstaculos/tapete.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |
| `obstaculo_trono` | Obstáculo 'trono': trono (arenas: Salão do Trono, Portões do Inferno). | `arenas/obstaculos/trono.png` | `(proposto) arenas/obstaculos/<tipo>` | não | peca | 1 | 512x512 vista de cima, base no centro | magenta #FF00FF | P3 | 0/95 lutas | vetor |

### clima

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `clima_calor` | Clima 'calor' (arenas: Cratera Vulcânica): partícula/camada. | `arenas/clima/calor.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_chamas` | Clima 'chamas' (arenas: Portões do Inferno): partícula/camada. | `arenas/clima/chamas.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_chuva` | Clima 'chuva' (arenas: Beco Neon): partícula/camada. | `arenas/clima/chuva.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_escorregadio` | Clima 'escorregadio' (arenas: Tundra Congelada): partícula/camada. | `arenas/clima/escorregadio.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_luzes_piscando` | Clima 'luzes_piscando' (arenas: Estação Orbital): partícula/camada. | `arenas/clima/luzes_piscando.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_neblina` | Clima 'neblina' (arenas: Cemitério Amaldiçoado): partícula/camada. | `arenas/clima/neblina.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_neon` | Clima 'neon' (arenas: Beco Neon): partícula/camada. | `arenas/clima/neon.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_neve` | Clima 'neve' (arenas: Tundra Congelada): partícula/camada. | `arenas/clima/neve.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_particulas_fogo` | Clima 'particulas_fogo' (arenas: Cratera Vulcânica): partícula/camada. | `arenas/clima/particulas_fogo.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P3 | 0/95 lutas | nenhuma |
| `clima_poeira` | Clima 'poeira' (arenas: Templo Esquecido, Poco do Templo): partícula/camada. | `arenas/clima/poeira.png` | `(proposto) dentro da cena do tema` | não | peca | 1 | 256x256 partícula (ou 1080x1920 camada, para neblina/chuva) | magenta #FF00FF | P2 | 40/95 lutas | nenhuma |

### luz

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `luz_ambiente` | Luz ambiente/vinheta por cima da arena (luz do alto à esquerda, como o cel). *(opcional)* | `arenas/luz.png` | `` | não | peca | 1 | 1080x1920 máscara | magenta #FF00FF | P3 |  | nenhuma |

## 6. HUD

O HUD do palco (`hud_padrao.gd`) é desenhado: nome, vida com o "fantasma" do dano, plano com a barrinha. Não há retrato. Só vira sprite se a mestra pedir.

| item | o quê | arquivo | cena (busca) | procura? | tipo | quadros | tamanho | fundo | prio | presença | arte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `hud_moldura_vida` | HUD: moldura da barra de vida. *(opcional)* | `hud/moldura_vida.png` | `hud/_padrao.tscn` | sim | peca | 1 | 1024x128 | magenta #FF00FF | P3 |  | vetor |
| `hud_barra_vida` | HUD: preenchimento da barra (cel 2 tons, tingido pela cor do lado). *(opcional)* | `hud/barra_vida.png` | `hud/_padrao.tscn` | sim | peca | 1 | 1024x128 | magenta #FF00FF | P3 |  | vetor |
| `hud_placa_nome` | HUD: placa atrás do nome. *(opcional)* | `hud/placa_nome.png` | `hud/_padrao.tscn` | sim | peca | 1 | 1024x128 | magenta #FF00FF | P3 |  | vetor |
| `hud_selo_plano` | HUD: selo do plano de luta (PRESSÃO, ISCA, ESMAGAR...). *(opcional)* | `hud/selo_plano.png` | `hud/_padrao.tscn` | sim | peca | 1 | 1024x128 | magenta #FF00FF | P3 |  | vetor |

## Ordem de produção

Critérios, nesta ordem:

1. A imagem-mestra.
2. Prioridade.
3. Obrigatório antes de opcional.
4. Livre antes de bloqueado.
5. O estrutural de todo duelo: corpo, conjuração, acertos, impacto.
6. O que falta antes do CC0 a trocar.
7. O que o palco já procura antes do que pede mudança.
8. Presença.

O que já tem arte da esteira fica de fora. Vai em lotes por elemento: a mestra vale para todos, e a F1 da esteira mede 10 skills de um elemento.

| # | item | prio | presença | procura? | arte | arquivo |
|---|---|---|---|---|---|---|
| 1 | `imagem_mestra` | P1 | estrutural | não | nenhuma | `_estilo/imagem_mestra.png` |
| 2 | `conjuracao_generica` | P1 | 95/95 lutas; 1122 casts | sim | vetor | `efeitos/folhas/conjuracao.png` |
| 3 | `acerto_light` | P1 | 1338 acertos em 95 lutas (14.1 por luta) | sim | vetor | `efeitos/folhas/acerto_light.png` |
| 4 | `acerto_medium` | P1 | 1395 acertos em 95 lutas (14.7 por luta) | sim | vetor | `efeitos/folhas/acerto_medium.png` |
| 5 | `impacto_generico` | P1 | 73/95 lutas | sim | vetor | `efeitos/folhas/impacto.png` |
| 6 | `corpo_bolinha` | P1 | todo duelo (2 por luta) | não | vetor | `lutadores/pecas/corpo.png` |
| 7 | `acerto_colossal` | P1 | 281 acertos em 95 lutas (3.0 por luta) | sim | cc0 | `efeitos/folhas/acerto_colossal.png` |
| 8 | `acerto_heavy` | P1 | 125 acertos em 95 lutas (1.3 por luta) | sim | cc0 | `efeitos/folhas/acerto_heavy.png` |
| 9 | `evento_ko` | P1 | 95/95 lutas | sim | cc0 | `efeitos/folhas/ko.png` |
| 10 | `evento_desvio` | P1 | 95/95 lutas | sim | vetor | `efeitos/folhas/desvio.png` |
| 11 | `evento_dash` | P1 | 93/95 lutas | sim | vetor | `efeitos/folhas/dash.png` |
| 12 | `evento_dano` | P1 | 77/95 lutas | sim | vetor | `efeitos/folhas/dano.png` |
| 13 | `skill_avanco_brutal` | P1 | cast em 70/95 lutas; no kit de 25 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/avanco_brutal.png` |
| 14 | `classe_berserker` | P1 | 53 aparições em 95 lutas (banco: 5 de 88) | sim | nenhuma | `lutadores/classes/berserker.png` |
| 15 | `orbe_default` | P1 | 53/95 lutas; 1514 trilhas de orbe (o objeto mais comum da luta) | sim | vetor | `efeitos/pecas/orbe.png` |
| 16 | `evento_agarrao_desfecho` | P1 | 51/95 lutas | sim | vetor | `efeitos/folhas/agarrao_desfecho.png` |
| 17 | `skill_ritual_carmesim` | P1 | cast em 49/95 lutas; no kit de 2 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/ritual_carmesim.png` |
| 18 | `arma_runas_flutuantes` | P1 | 48 aparições em 95 lutas (banco: 2 de 101 armas) | sim | nenhuma | `armas/estilos/runas_flutuantes.png` |
| 19 | `impacto_default` | P1 | 462 explosões em 95 lutas (4.86 por luta) | não | nenhuma | `efeitos/folhas/impacto_default.png` |
| 20 | `rastro_corte` | P1 | 129 lutadores com esse arquétipo em 95 lutas | não | vetor | `efeitos/texturas/rastro_corte.png` |
| 21 | `acerto_critico` | P1 | 102 críticos em 95 lutas | não | vetor | `efeitos/folhas/acerto_critico.png` |
| 22 | `movimento_aterrissagem` | P1 | 341 em 95 lutas (3.6 por luta) | não | nenhuma | `efeitos/folhas/movimento_aterrissagem.png` |
| 23 | `movimento_corrida` | P1 | 162 em 95 lutas (1.7 por luta) | não | nenhuma | `efeitos/folhas/movimento_corrida.png` |
| 24 | `movimento_dash` | P1 | 815 em 95 lutas (8.6 por luta) | não | nenhuma | `efeitos/folhas/movimento_dash.png` |
| 25 | `movimento_knockback` | P1 | 766 em 95 lutas (8.1 por luta) | não | nenhuma | `efeitos/folhas/movimento_knockback.png` |
| 26 | `movimento_pulo` | P1 | 619 em 95 lutas (6.5 por luta) | não | nenhuma | `efeitos/folhas/movimento_pulo.png` |
| 27 | `movimento_recuperacao` | P1 | 1223 em 95 lutas (12.9 por luta) | não | nenhuma | `efeitos/folhas/movimento_recuperacao.png` |
| 28 | `projetil_fim_bloqueado` | P1 | 104 em 95 lutas | não | nenhuma | `efeitos/folhas/projetil_fim_bloqueado.png` |
| 29 | `projetil_fim_expirou` | P1 | 305 em 95 lutas | não | nenhuma | `efeitos/folhas/projetil_fim_expirou.png` |
| 30 | `status_atordoado` | P1 | 95/95 lutas | não | vetor | `lutadores/status/atordoado.png` |
| 31 | `status_lento` | P1 | 63/95 lutas | não | vetor | `lutadores/status/lento.png` |
| 32 | `orbe_runas_flutuantes` | P1 | 48 aparições em 95 lutas (banco: 2 de 101 armas) | não | nenhuma | `efeitos/orbes/runas_flutuantes.png` |
| 33 | `estado_adrenalina` | P1 | 26% dos passos de lutador | não | vetor | `lutadores/estados/adrenalina.png` |
| 34 | `rosto_boca_onda` | P1 | 22% dos passos de lutador (nervoso, panico, tonto, confuso) | não | vetor | `lutadores/rosto/boca_onda.png` |
| 35 | `rosto_faiscas_alerta` | P1 | 15% dos passos de lutador (alerta) | não | vetor | `lutadores/rosto/faiscas_alerta.png` |
| 36 | `estado_atordoado` | P1 | 14% dos passos de lutador; status ATORDOADO 95/95 lutas | não | vetor | `lutadores/estados/atordoado.png` |
| 37 | `rosto_olho_espiral` | P1 | 13% dos passos de lutador (tonto) | não | vetor | `lutadores/rosto/olho_espiral.png` |
| 38 | `rosto_gota_suor` | P1 | 8% dos passos de lutador (panico, nervoso, desespero, limite) | não | vetor | `lutadores/rosto/gota_suor.png` |
| 39 | `estado_bloqueando` | P1 | 7% dos passos de lutador | não | vetor | `lutadores/estados/bloqueando.png` |
| 40 | `rosto_veia_raiva` | P1 | 6% dos passos de lutador (furia, berserk) | não | vetor | `lutadores/rosto/veia_raiva.png` |
| 41 | `evento_parede` | P1 | 95/95 lutas | sim | cc0 | `efeitos/folhas/parede.png` |
| 42 | `evento_wall_splat` | P1 | 68/95 lutas | sim | cc0 | `efeitos/folhas/wall_splat.png` |
| 43 | `conjuracao_default` | P1 | 433 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_default.png` |
| 44 | `conjuracao_natureza` | P1 | 118 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_natureza.png` |
| 45 | `conjuracao_raio` | P1 | 108 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_raio.png` |
| 46 | `conjuracao_sangue` | P1 | 139 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_sangue.png` |
| 47 | `rosto_eye_closed_down` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_closed_down.png` |
| 48 | `rosto_eye_closed_up` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_closed_up.png` |
| 49 | `rosto_eye_half_bottom` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_half_bottom.png` |
| 50 | `rosto_eye_half_top` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_half_top.png` |
| 51 | `rosto_eye_half_top_wing` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_half_top_wing.png` |
| 52 | `rosto_eye_open` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_open.png` |
| 53 | `rosto_eye_x` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eye_x.png` |
| 54 | `rosto_eyebrow_a` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eyebrow_a.png` |
| 55 | `rosto_eyebrow_b` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eyebrow_b.png` |
| 56 | `rosto_eyebrow_c` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eyebrow_c.png` |
| 57 | `rosto_eyebrow_d` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/eyebrow_d.png` |
| 58 | `rosto_mouth_happy` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/mouth_happy.png` |
| 59 | `rosto_mouth_sad` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/mouth_sad.png` |
| 60 | `rosto_mouth_smirk` | P1 | as 24 expressões usam | sim | cc0 | `lutadores/rosto/mouth_smirk.png` |
| 61 | `evento_bloqueio` | P2 | 46/95 lutas | sim | vetor | `efeitos/folhas/bloqueio.png` |
| 62 | `arena_ruinas_parede` | P2 | 40/95 lutas | sim | vetor | `arenas/temas/ruinas_parede.png` |
| 63 | `skill_impacto_sonico` | P2 | cast em 35/95 lutas; no kit de 12 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/impacto_sonico.png` |
| 64 | `evento_choque` | P2 | 35/95 lutas | sim | vetor | `efeitos/folhas/choque.png` |
| 65 | `evento_cura` | P2 | 35/95 lutas | sim | vetor | `efeitos/folhas/cura.png` |
| 66 | `arena_cyberpunk_parede` | P2 | 28/95 lutas | sim | vetor | `arenas/temas/cyberpunk_parede.png` |
| 67 | `arena_castelo_parede` | P2 | 27/95 lutas | sim | vetor | `arenas/temas/castelo_parede.png` |
| 68 | `skill_teleporte_relampago` | P2 | cast em 25/95 lutas; no kit de 11 dos 88 do banco | sim | nenhuma | `efeitos/folhas/skills/teleporte_relampago.png` |
| 69 | `flecha` | P2 | 22 lutas com flecha | sim | nenhuma | `efeitos/pecas/flecha.png` |
| 70 | `classe_ladino` | P2 | 21 aparições em 95 lutas (banco: 7 de 88) | sim | nenhuma | `lutadores/classes/ladino.png` |
| 71 | `skill_esporos_alucinogenos` | P2 | cast em 21/95 lutas; no kit de 6 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/esporos_alucinogenos.png` |
| 72 | `skill_mjolnir` | P2 | cast em 21/95 lutas; no kit de 5 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/mjolnir.png` |
| 73 | `evento_parry` | P2 | 21/95 lutas | sim | vetor | `efeitos/folhas/parry.png` |
| 74 | `classe_guerreiro` | P2 | 18 aparições em 95 lutas (banco: 6 de 88) | sim | nenhuma | `lutadores/classes/guerreiro.png` |
| 75 | `skill_bomba_relogio` | P2 | cast em 18/95 lutas; no kit de 0 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/bomba_relogio.png` |
| 76 | `skill_bomba_relogio_explosao` | P2 | cast em 18/95 lutas; no kit de 0 dos 88 do banco | sim | nenhuma | `efeitos/folhas/skills/bomba_relogio_explosao.png` |
| 77 | `evento_esquiva` | P2 | 17/95 lutas | sim | vetor | `efeitos/folhas/esquiva.png` |
| 78 | `skill_nuvem_toxica` | P2 | cast em 16/95 lutas; no kit de 6 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/nuvem_toxica.png` |
| 79 | `skill_sacrificio` | P2 | cast em 14/95 lutas; no kit de 8 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/sacrificio.png` |
| 80 | `classe_monge` | P2 | 13 aparições em 95 lutas (banco: 7 de 88) | sim | nenhuma | `lutadores/classes/monge.png` |
| 81 | `skill_provocar` | P2 | cast em 13/95 lutas; no kit de 2 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/provocar.png` |
| 82 | `classe_feiticeiro` | P2 | 12 aparições em 95 lutas (banco: 8 de 88) | sim | nenhuma | `lutadores/classes/feiticeiro.png` |
| 83 | `classe_gladiador` | P2 | 12 aparições em 95 lutas (banco: 8 de 88) | sim | nenhuma | `lutadores/classes/gladiador.png` |
| 84 | `arma_facas_taticas` | P2 | 12 aparições em 95 lutas (banco: 4 de 101 armas) | sim | nenhuma | `armas/estilos/facas_taticas.png` |
| 85 | `arma_kamas` | P2 | 12 aparições em 95 lutas (banco: 4 de 101 armas) | sim | nenhuma | `armas/estilos/kamas.png` |
| 86 | `skill_parar_o_tempo` | P2 | cast em 11/95 lutas; no kit de 5 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/parar_o_tempo.png` |
| 87 | `skill_raizes` | P2 | cast em 11/95 lutas; no kit de 2 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/raizes.png` |
| 88 | `arma_besta_leve` | P2 | 11 aparições em 95 lutas (banco: 5 de 101 armas) | sim | nenhuma | `armas/estilos/besta_leve.png` |
| 89 | `classe_druida` | P2 | 10 aparições em 95 lutas (banco: 5 de 88) | sim | nenhuma | `lutadores/classes/druida.png` |
| 90 | `classe_piromante` | P2 | 10 aparições em 95 lutas (banco: 4 de 88) | sim | nenhuma | `lutadores/classes/piromante.png` |
| 91 | `skill_ira_da_floresta` | P2 | cast em 10/95 lutas; no kit de 2 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/ira_da_floresta.png` |
| 92 | `skill_pilar_de_fogo` | P2 | cast em 10/95 lutas; no kit de 3 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/pilar_de_fogo.png` |
| 93 | `skill_pilar_de_fogo_erupcao` | P2 | cast em 10/95 lutas; no kit de 3 dos 88 do banco | sim | nenhuma | `efeitos/folhas/skills/pilar_de_fogo_erupcao.png` |
| 94 | `arena_esporte_parede` | P2 | 0/95 lutas; Ringue em 4 dos 42 duelos dos fight.json | sim | vetor | `arenas/temas/esporte_parede.png` |
| 95 | `clima_poeira` | P2 | 40/95 lutas | não | nenhuma | `arenas/clima/poeira.png` |
| 96 | `obstaculo_pilar_quebrado` | P2 | 40/95 lutas | não | vetor | `arenas/obstaculos/pilar_quebrado.png` |
| 97 | `status_vulneravel` | P2 | 38/95 lutas | não | vetor | `lutadores/status/vulneravel.png` |
| 98 | `status_envenenado` | P2 | 37/95 lutas | não | vetor | `lutadores/status/envenenado.png` |
| 99 | `obstaculo_caixa` | P2 | 28/95 lutas | não | vetor | `arenas/obstaculos/caixa.png` |
| 100 | `obstaculo_pilar` | P2 | 27/95 lutas | não | vetor | `arenas/obstaculos/pilar.png` |
| 101 | `impacto_sangue` | P2 | 24 explosões em 95 lutas (0.25 por luta) | não | nenhuma | `efeitos/folhas/impacto_sangue.png` |
| 102 | `skill_forma_sanguinaria` | P2 | ativo em 23/95 lutas; cast em 23/95 lutas; no kit de 2 dos 88 do banco | não | vetor | `lutadores/transformacoes/forma_sanguinaria.png` |
| 103 | `skill_golpe_do_executor` | P2 | ativo em 22/95 lutas; cast em 22/95 lutas; no kit de 5 dos 88 do banco | não | nenhuma | `lutadores/buffs/golpe_do_executor.png` |
| 104 | `status_queimando` | P2 | 22/95 lutas | não | vetor | `lutadores/status/queimando.png` |
| 105 | `status_charme` | P2 | 20/95 lutas | não | vetor | `lutadores/status/charme.png` |
| 106 | `skill_troca_de_almas` | P2 | cast em 19/95 lutas; no kit de 5 dos 88 do banco | não | nenhuma | `efeitos/folhas/skills/troca_de_almas.png` |
| 107 | `rastro_esmagamento` | P2 | 17 lutadores com esse arquétipo em 95 lutas | não | vetor | `efeitos/texturas/rastro_esmagamento.png` |
| 108 | `impacto_natureza` | P2 | 16 explosões em 95 lutas (0.17 por luta) | não | nenhuma | `efeitos/folhas/impacto_natureza.png` |
| 109 | `skill_velocidade_arcana` | P2 | ativo em 14/95 lutas; cast em 14/95 lutas; no kit de 14 dos 88 do banco | não | nenhuma | `lutadores/buffs/velocidade_arcana.png` |
| 110 | `impacto_trevas` | P2 | 13 explosões em 95 lutas (0.14 por luta) | não | nenhuma | `efeitos/folhas/impacto_trevas.png` |
| 111 | `skill_acelerar` | P2 | ativo em 13/95 lutas; cast em 13/95 lutas; no kit de 5 dos 88 do banco | não | nenhuma | `lutadores/buffs/acelerar.png` |
| 112 | `rastro_estocada` | P2 | 13 lutadores com esse arquétipo em 95 lutas | não | vetor | `efeitos/texturas/rastro_estocada.png` |
| 113 | `status_enraizado` | P2 | 13/95 lutas | não | vetor | `lutadores/status/enraizado.png` |
| 114 | `impacto_gravitacao` | P2 | 12 explosões em 95 lutas (0.13 por luta) | não | nenhuma | `efeitos/folhas/impacto_gravitacao.png` |
| 115 | `skill_fotossintese` | P2 | ativo em 12/95 lutas; cast em 12/95 lutas; no kit de 2 dos 88 do banco | não | nenhuma | `lutadores/canais/fotossintese.png` |
| 116 | `status_tempo_parado` | P2 | 11/95 lutas | não | vetor | `lutadores/status/tempo_parado.png` |
| 117 | `impacto_arcano` | P2 | 10 explosões em 95 lutas (0.11 por luta) | não | nenhuma | `efeitos/folhas/impacto_arcano.png` |
| 118 | `skill_determinacao` | P2 | ativo em 10/95 lutas; cast em 10/95 lutas; no kit de 8 dos 88 do banco | não | nenhuma | `lutadores/buffs/determinacao.png` |
| 119 | `estado_super_armor` | P2 | 2% dos passos de lutador | não | vetor | `lutadores/estados/super_armor.png` |
| 120 | `estado_agarrado` | P2 | 1% dos passos de lutador; agarrão em 57/95 lutas | não | nenhuma | `lutadores/estados/agarrado.png` |
| 121 | `estado_tempo_parado` | P2 | 1% dos passos de lutador | não | nenhuma | `lutadores/estados/tempo_parado.png` |
| 122 | `raridade_aura_dourada` | P2 | o banco tem 89 de 101 armas acima de Comum | não | nenhuma | `armas/raridade/aura_dourada.png` |
| 123 | `raridade_brilho_leve` | P2 | o banco tem 89 de 101 armas acima de Comum | não | nenhuma | `armas/raridade/brilho_leve.png` |
| 124 | `raridade_brilho_medio` | P2 | o banco tem 89 de 101 armas acima de Comum | não | nenhuma | `armas/raridade/brilho_medio.png` |
| 125 | `raridade_chamas_miticas` | P2 | o banco tem 89 de 101 armas acima de Comum | não | nenhuma | `armas/raridade/chamas_miticas.png` |
| 126 | `raridade_particulas` | P2 | o banco tem 89 de 101 armas acima de Comum | não | nenhuma | `armas/raridade/particulas.png` |
| 127 | `summon_surgir` | P2 | summons em 21/95 lutas | não | nenhuma | `efeitos/folhas/surgir.png` |
| 128 | `area_gravitacao` | P2 | ≤28 lutas (soma das skills genéricas do par) | sim | cc0 | `efeitos/pecas/area/gravitacao.png` |
| 129 | `evento_obstaculo` | P2 | 13/95 lutas | sim | cc0 | `efeitos/folhas/obstaculo.png` |
| 130 | `projetil_natureza` | P2 | ≤11 lutas (soma das skills genéricas do par) | sim | cc0 | `efeitos/pecas/projetil/natureza.png` |
| 131 | `area_caos` | P2 | ≤10 lutas (soma das skills genéricas do par) | sim | cc0 | `efeitos/pecas/area/caos.png` |
| 132 | `area_fogo` | P2 | ≤10 lutas (soma das skills genéricas do par) | sim | cc0 | `efeitos/pecas/area/fogo.png` |
| 133 | `arma_meteor_hammer` | P2 | 11 aparições em 95 lutas (banco: 2 de 101 armas) | sim | nenhuma | `armas/pecas/corrente/cabeca_meteor_hammer.png` |
| 134 | `corrente_cabo` | P2 | 21 aparições de corrente | não | nenhuma | `armas/pecas/corrente/cabo.png` |
| 135 | `corrente_elo` | P2 | 21 aparições de corrente em 95 lutas | não | nenhuma | `armas/pecas/corrente/elo.png` |
| 136 | `corrente_segmento_corda` | P2 | Rope Dart + Meteor Hammer | não | nenhuma | `armas/pecas/corrente/corda.png` |
| 137 | `skill_campo_de_gravidade` | P2 | cast em 13/95 lutas; no kit de 5 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/campo_de_gravidade.png` |
| 138 | `skill_praga` | P2 | cast em 12/95 lutas; no kit de 3 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/praga.png` |
| 139 | `skill_explosao_do_caos` | P2 | cast em 10/95 lutas; no kit de 4 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/explosao_do_caos.png` |
| 140 | `skill_maldicao` | P2 | cast em 10/95 lutas; no kit de 2 dos 88 do banco | sim | nenhuma | `efeitos/pecas/skills/maldicao.png` |
| 141 | `conjuracao_gravitacao` | P2 | 75 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_gravitacao.png` |
| 142 | `conjuracao_tempo` | P2 | 54 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_tempo.png` |
| 143 | `conjuracao_fogo` | P2 | 49 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_fogo.png` |
| 144 | `conjuracao_trevas` | P2 | 49 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_trevas.png` |
| 145 | `agarrao_arremesso` | P2 | 42 em 95 lutas | não | nenhuma | `efeitos/folhas/agarrao_arremesso.png` |
| 146 | `conjuracao_arcano` | P2 | 31 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_arcano.png` |
| 147 | `conjuracao_luz` | P2 | 28 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_luz.png` |
| 148 | `conjuracao_caos` | P2 | 25 casts em 95 lutas | não | nenhuma | `efeitos/folhas/conjuracao_caos.png` |
| 149 | `agarrao_escape` | P2 | 23 em 95 lutas | não | nenhuma | `efeitos/folhas/agarrao_escape.png` |
| 150 | `agarrao_empurrao` | P2 | 12 em 95 lutas | não | nenhuma | `efeitos/folhas/agarrao_empurrao.png` |
| 151 | `agarrao_joelhada` | P2 | 11 em 95 lutas | não | nenhuma | `efeitos/folhas/agarrao_joelhada.png` |
| 152 | `acerto_corte` | P2 | ver arquétipos em Armas | não | nenhuma | `efeitos/folhas/acerto_corte.png` |
| 153 | `acerto_esmagamento` | P2 | ver arquétipos em Armas | não | nenhuma | `efeitos/folhas/acerto_esmagamento.png` |
| 154 | `acerto_estocada` | P2 | ver arquétipos em Armas | não | nenhuma | `efeitos/folhas/acerto_estocada.png` |
| 155 | `acerto_projetil_arma` | P2 | ver arquétipos em Armas | não | nenhuma | `efeitos/folhas/acerto_projetil_arma.png` |
| 156 | `rastro_projetil` | P2 | estrutural | não | vetor | `efeitos/texturas/rastro_projetil.png` |
| 157 | `sangue_respingo` | P2 | o render antigo tinha; o palco não | não | nenhuma | `efeitos/folhas/sangue_respingo.png` |

(Os demais P3, até o 512, estão no JSON pelo campo `ordem`.)

## Fontes

- palco/nucleo/biblioteca.gd, palco.gd, timeline.gd; palco/biblioteca/**/*.gd (o que cada peça desenha hoje)
- docs/palco/COMO-EDITAR.md, README.md, timeline.md
- neural_fights/data/armas.json (54 estilos); neural_fights/models/constants.py (TIPOS_ARMA, LISTA_CLASSES, KIT_POOLS, SKILLS_FORA_DE_ROTACAO, RARIDADES, ENCANTAMENTOS)
- neural_fights/core/skills.py + skill_contract.py (118 contratos); core/status_runtime.py (29 status); core/arena.py (20 arenas)
- neural_fights/effects/weapon_animations.py (WEAPON_PROFILES, ARQUETIPO_POR_ESTILO); effects/character_flair.py (24 expressões)
- neural_fights/recording/timeline.py (o que a sonda emite)
- %LOCALAPPDATA%/neural-fights/{personagens,armas}.json (banco: 88 personagens, 101 armas)
- random_builds/outputs/*/fight.json (42 lutas de duelo) e generation_*/estreia.json (53 estreias): seeds re-simuladas
- decisoes/builds/sprites-ia-*.json, sprites-animados, chao-da-arena, corrente-*, visual-do-lutador, palco-numeros-de-dano; decisoes/geral/sprites-ia-juiz.json
- planos: esteira-de-sprites-por-ia.md, corrente-rework.md, onda16-palco-godot.md
