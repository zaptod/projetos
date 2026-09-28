# Passagem: BUILDS / NEURAL FIGHTS

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/builds/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (28/09/2026) · “28/09 20:29, no chat: 'trabalhe em duas tarefas ao mesmo tempo' — max_paralelo 2” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Passou de 50%, para tudo; força total 20 min antes de renovar (28/09/2026) `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Ligada, 20 min antes de renovar (28/09/2026) `forca-total-ainda-vale`
- ↺ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`

**Builds**
- ✅ **Variantes B** — Título próprio para cada uma (27/09/2026) `variantes-b`
- ✅ **Roleta automática de madrugada** — Sim (28/09/2026) `roleta-de-madrugada`
- ✅ **Estreia generation_00066 (muda)** — Descartar (28/09/2026) `estreia-00066`
- ✅ **Onda 16: ferramenta do visual** — Godot 4 (28/09/2026) `ferramenta-do-visual`
- ✅ **Visual do lutador** — Bolinha com arte (28/09/2026) `visual-do-lutador`
- ✅ **Origem da arte** — CC0 + IA, trocável (28/09/2026) `origem-da-arte`
- ✅ **Transição até o palco** — O visual atual segue, já com o som real (28/09/2026) `transicao`
- ✅ **Som real da luta (16A)** — Aprovar: re-render do estoque na madrugada (28/09/2026) `som-real-16a`
- ✅ **Palco: o visual novo (A/B)** — Seguir: próxima etapa é a arte (16E) (28/09/2026) `palco-seguir`
- ✅ **Chão da arena** — Foto de pedra CC0 escurecida (como está) (28/09/2026) `chao-da-arena`
- ✅ **Hitstop: a pausinha no impacto** — Ligar (28/09/2026) `hitstop`
- ✅ **generation_00077: luta muda, lutadores fora do banco** — Descartar, como a 00066 (28/09/2026) `generation-00077`
- ✅ **Sprites animados: como produzir** — Continuar com o modelo padrão e limpar depois (28/09/2026) · “Eu consegui gerar alguns spritesheet bons, veja o arquivo piriri.py , eu consegui esse usando o chat gpt, mas como o processo é moroso quero apenas uma interface gráfica que facilite ao máximo esse processo, como essa limpeza de fundo, saneamento e auto faturamento de frames, identificação e outras coisas úteis.” `sprites-animados`

<!-- decisoes:fim -->

Minha parte: `random_builds/` (main.py e o motor de geração — roleta/builds,
estreias, duelos, torneios, render, capa, áudio/voz, reações) e
`neural_fights/` (banco de personagens e armas, motor de luta, gravador). NÃO é
minha parte a publicação (`ferramentas/postar.py`) nem as histórias. Tudo
abaixo foi conferido em 27/09/2026 nos arquivos; o que veio de fora está dito.

## 1. Os formatos: o que são, quanto custam, onde saem

Tudo cai em `random_builds/outputs/<id>/`, sempre em dois perfis
(`final_celular.mp4` = 9:16 e `final_normal.mp4` = 16:9), mais `capa.png`.

| formato | o que é | duração medida (celular) | custo medido | pasta |
|---|---|---|---|---|
| **duelo** | a luta inteira em 20–35 s, um evento só, nenhuma cena parada; identidade (~1,5 s) e veredito (~1,2 s) são sobreposições no próprio clipe | `duelo_00015` = 27,8 s | ~4,3 min por duelo ponta a ponta (8 duelos entre 17:29 e 18:03 de 27/09); render ~45–90 s por perfil | `duelo_000NN/` |
| **build** | a roleta: personagem + arma sorteados, nota, narração com voz, reação, e o round decisivo da estreia no fim | `generation_00085` = 56,7 s | um `generate-video` levou 10 min (24/09, 20:33→20:43) e nesse tempo entrega build **e** estreia; a fila de imagem/clipe (PicassoIA/Digen) continua depois | `generation_000NN/` |
| **estreia** | a primeira luta do personagem novo, melhor de 3 (`editing.json: estreia_melhor_de`) | `generation_00085/estreia` = 80,5 s (renders antigos passam de 2 min) | sai dentro do mesmo `generate-video`: ~3,5 min dos 10 (gravação + 2 renders) | `generation_000NN/estreia/` |
| **torneio** | chave de 8, uma volta inteira | — | só 2 existem (`tournament_00006`, `00007`); cota 0, não é produzido | `tournament_000NN/` |
| luta avulsa | `fight`, 2 formatos, fora da grade | — | — | `fight_000NN/` |

Hoje no disco (28/09, 02:28): 83 `generation_*`, 23 `duelo_*`, 2
`tournament_*`, 4 `fight_*`.

Dentro da pasta: `fight.json` (gameplay simulado), `edit_plan.json` (a
montagem), `gameplay/` (clipes crus) e, na build, `build.json`,
`character.json`, `weapon.json`, `rolls.json`, `evaluation.json`,
`narration.json`, `voz.wav`, `subtitles.srt`, `identity/`.

## 2. Como gerar (de `E:\projetos\random_builds`, `python main.py ...`)

```bash
# DUELO — o formato que a grade mais quer (4 de 8)
python main.py duelo                                  # p1 e p2 em rodízio (arena/rodizio.py)
python main.py duelo --p1 "Wren Telgyll" --p2 "Emi Ossarhamar"
python main.py duelo --seed 4242 --preview
python main.py duelo --rerender duelo_00012 --refazer-edicao   # sem re-simular

# BUILD (+ ESTREIA no mesmo comando)
python main.py generate-video
python main.py generate-video --seed 847293847        # mesma seed = mesmo vídeo
python main.py generate-video --no-estreia            # roleta sem gravar a 1ª luta
python main.py generate-video --generation-only       # só dados, nunca insere no banco
python main.py generate-video --rerender generation_00061 --refazer-edicao

python main.py fight --p1 "Kael" --p2 "Lyra" --melhor-de 3
python main.py tournament --fonte misto --participantes 8

# SOM REAL DA LUTA em vídeo já gravado (Onda 16A, §7) — sem regravar a luta
python main.py som-da-luta --listar                  # estoque com a luta muda + comando
python main.py som-da-luta duelo_00014 generation_00029   # anota e re-renderiza NO LUGAR
python main.py som-da-luta E:\projetos\random_builds\outputs\duelo_00014 --destino outputs\_ouvir\teste --perfis celular   # numa cópia

# GERAÇÃO NOTURNA — o que as tarefas NeuralFights_gerar_01..05 (HH:02) chamam
python main.py noite --listar        # tarefas + duelos que a grade escolheria (e o teto)
python main.py noite --ensaio        # faz todas as conferências e diz o que faria; não gera
python main.py noite --duelos 8      # rodada manual: 8 ignorando o teto (o relógio ainda manda)
python main.py noite --builds 1      # rodada manual: 1 roleta; com --duelos/--builds só o pedido sai
python main.py noite --instalar      # (re)cria as tarefas; --remover apaga
```

**Rodízio do duelo** (`builds/arena/rodizio.py`, desde 28/09/2026): sem
`--p1`/`--p2`, luta primeiro quem apareceu menos nos últimos 20 duelos (como
p1 ou p2); no empate, quem saiu da roleta (tem vídeo de build) e, entre esses,
o mais recente. O p2 sai dos menos usados pela regra antiga (continuidade,
senão poder próximo). **Par com título já ocupado nunca é escolhido**, em
nenhuma ordem: o título do duelo é `{p1} x {p2}` e a guarda de título
repetido barraria o vídeo para sempre. Antes era "o último criado na roleta",
e sem roleta nova isso deu 5 de 8 duelos com o mesmo p1 (Wren Telgyll, 27/09).

**A rodada noturna** (`builds/pipeline/noite.py`, config em
`config/geracao.json`): na janela 01h–06h, gera duelos **e builds (roleta,
`generate-video` inteiro: build, inserção no banco, estreia, render e fila
de identidade)** até o teto de cada um, e depois roda o `identity worker`
(capa e payoff das builds). Teto = `dias_de_gordura` 2 × horários/dia pela
cota: duelo 4/8 de 10 = 5 → **10 duelos**; build 3/8 de 10 = 3,75 → **8
builds**. **Quem tem menos dias de estoque vai primeiro** (dias = estoque ÷
horários/dia; empate, duelo) — decisão do Adrian de 28/09 ("Sim, gerar
builds também"), porque a rodada até :25 não dá para os dois quando os dois
estão baixos. O estoque é contado pelo **mesmo funil da escolha** (não
publicado, sem pendência, título livre; dois pendentes com o mesmo título
contam um); o de build soma as **builds em preparo** (A/celular não
publicada, só com pendência que o worker resolve — imagem, payoff, mp4 mais
velho — e com job vivo na fila), senão a rodada seguinte veria o estoque
igual e faria outra roleta por hora. Nada começa se não termina antes de
**:25** — duelo reserva 5 min, build 15 (medido 10 em 24/09) —, no máximo 6
duelos e **1 build** por rodada; `"builds": false` no config desliga a
roleta. A roleta não usa o PicassoIA: só enfileira; quem abre o site é o
worker, com a trava de perfil (`travas.do_perfil`). Medido em 28/09, 20:07
(`main.py noite --listar`): 10 duelos (2,0 dias, teto 10) e 14 builds (3,7
dias, teto 8) — nesta noite nenhuma roleta sairia. O worker é chamado **um provedor por vez e com
prazo**: imagem do PicassoIA reserva 8 min (medido 3,3–6), payoff do Digen
18 (medido 12–15, com o re-render da build); o worker não começa job nem
tentativa nova depois do prazo (`worker.drenar(so_provedor=, prazo=)`),
porque job que falha é repescado na mesma passada e `limite` não segurava o
tempo. Resíduo conhecido: o Digen tem espera própria de até 30 min, então um
payoff muito lento ainda pode passar de :25 — de madrugada não há post
nessa janela (00:37 e 06:37 são os vizinhos). Trava `builds__gerar` entre
processos (a rodada que encontra outra em andamento sai). A saída vai para
`outputs/_logs/gerar_AAAAMMDD.txt` (com hora) e `gerar_saida.txt` (o resto);
o lançador `gerar.cmd` é gerado pelo `--instalar` e não vai para o git.

Pré-requisito real: **personagem com ficha no banco do neural_fights**. Duelo,
fight e torneio leem `fichas_do_banco()`; sem ficha não há quem lute e o duelo
levanta `"nao ha adversario disponivel no banco"`. O banco vivo é
`%LOCALAPPDATA%\neural-fights\{personagens,armas}.json` (hoje 82 e 95; última
escrita 24/09 20:33, a inserção da `generation_00085`); o que está em
`neural_fights/data/*.json` é o snapshot do pacote (64 personagens), não o banco
vivo. `generate-video` é o único que insere (a menos de `--no-insert`).

## 3. O dado que decide

Medição de 27/09/2026 (recebida da orquestração), % assistido e views medianas:
**duelo 51,5% / 78 views**, build 25,4% / 37, estreia 10,7% / 25.

O retrato local foi refeito no mesmo dia (`random_builds/outputs/_metricas/`,
95 arquivos gravados às 20:08 de 27/09; `python main.py metricas` sem
`--atualizar` lê ele) e aponta na mesma direção, com números menores:

| formato | n | retenção média | retenção mediana | views medianas |
|---|---|---|---|---|
| duelo | 7 | 34,0% | 36,3% | 44 |
| build | 59 | 25,1% | 20,0% | 23 |
| estreia | 27 | 10,4% | 5,1% | 7 |
| torneio | 1 | 19,9% | 19,9% | 25 |

A diferença para o número da orquestração é de fonte (não sei qual ela usou;
o 51,5% coincide com o `duelo_00001` sozinho). O duelo ganha nas duas
dimensões e é o formato mais barato — mas n = 7, todos de 11–13/09.

**A cota mora em `random_builds/config/publicacao.json`, bloco
`grade.mistura`:** `duelo 4, build 3, estreia 1, torneio 0`. O padrão de queda
(se o bloco desaparecer) é `COTA_PADRAO` em `ferramentas/postar.py:1717`, com o
mesmo conteúdo, lido por `cota_da_grade()`; quem escolhe o vídeo de cada
horário é `escolher_por_cota()` (vence o formato mais atrasado em relação à
cota dele). Os números são **pesos relativos**: `builds/grade.py` tem **10**
horários desde 15/09, e 4+3+1 = 8 dá ao duelo metade deles (5), ao build 3,75
e à estreia 1,25; formato sem estoque cede o horário. O comentário do config
foi corrigido em 28/09 (falava em "8 disparos"); o do código
(`ferramentas/postar.py:1715`) ainda fala, e o arquivo é da publicação.
**Aumentar a cota do duelo espera ~10 duelos medidos** (hoje há 7 com
métrica): não mexer antes.

## 4. O que já quebrou

- **Builds pararam por falta de estoque, e não há nada que os crie.** O canal
  publicou ~20 vídeos/dia até 20/09; depois: 2 em 21/09, **zero em 22, 23, 25 e
  26/09**, 2 em 24/09 e 2 em 27/09 (`outputs/_publicar/publicados.jsonl`). A
  causa é montante: a última build é a `generation_00085`, de 24/09, e os duelos
  anteriores aos de hoje são todos de 11/09. No Agendador do Windows havia **14
  tarefas `Historias_auto_*`** e **10 `NeuralFights_postar_*`** — e **nenhuma
  que gerasse build ou duelo**. **Remédio (27/09, 23:57):** as tarefas
  `NeuralFights_gerar_01..05` (HH:02) rodam `main.py noite` — duelos até o
  teto e o worker de identidade (§2). Testadas antes de registrar com um
  ensaio de ponta a ponta pelo próprio Agendador (tarefa temporária →
  wscript → `gerar.cmd --ensaio` → trava → diário), que não gera nada.
  Desde 28/09 (noite) a mesma rodada gera também a roleta (§2).
- **Personagens de agosto perdidos.** O banco foi refeito em 02/09 e as fichas
  de agosto saíram junto. Quem depende delas não volta: a estreia de uma build
  antiga é impossível, não pendente — `catalogo._falta_estreia()` diz isso com
  o nome do personagem, em vez de pedir para "gravar a luta" (era a lápide que
  contava 20 tarefas todo dia).
- **Vídeo mudo.** Render antigo saía calado ou com som só no fim.
  `generation_00066/estreia/final_celular.mp4` tem **114,7 s de silêncio em
  120,8 s (95%)**, média -30,4 dB — medido agora com ffmpeg. A guarda está na
  publicação (`_audio_mudo`, `FRACAO_MUDA = 0.5`) e era ela que segurava esse
  vídeo, medindo-o de novo a cada horário. **Descartada em 28/09** (decisão 5
  da rota): `config/publicacao.json → descartados` tira do catálogo, da fila,
  do painel e de `por_id` tudo o que tiver a chave `<fonte_id>:<origem>`
  (`generation_00066:estreia`), com o motivo escrito. Nada é apagado: o mp4
  fica na pasta, e tirar a linha devolve o vídeo. `main.py publicar` lista os
  descartados no fim, e publicar um deles na mão diz o motivo. A
  **`generation_00077`** saiu pelo mesmo caminho em 28/09 (decisão
  `generation-00077`: "Descartar, como a 00066"), com as duas chaves
  (`:build` e `:estreia`): medido pela régua da publicação, a luta está a
  -91 dB na build (`seg_022`, A e B) **e** na estreia (`seg_007`), e os dois
  lutadores saíram do banco em 02/09. Build descartada também tira o payoff
  dela da fila do worker (`queue.geracoes_descartadas()`): o job fica
  `pending`, ninguém o reivindica, e volta junto se a linha sair.
- **Gancho B com título igual ao do A.** A variante B (`final_<perfil>_ganchoB.mp4`)
  tem id com sufixo `:B` e o MESMO título; para o código eram dois vídeos, para
  o YouTube eram duplicatas. 21 chaves de título saíram duas vezes (medição de
  16/09 registrada no config). O remédio foi `grade.repetir_titulo: false`, que
  barra título já publicado — e isso deixou as variantes B paradas.
  **Segundo remédio (27/09, decisão do Adrian: título próprio para cada B):**
  dos 25 fora da fila por título, 21 eram B e 4 eram A. **18 B ganharam
  título próprio** em `outputs/_publicar/_textos/` (celular e normal; o A e a
  descrição não mudam), no tom pedido pelo Adrian em 27/08 (limpo e
  convidativo: pergunta a quem assiste, sem grito nem emoji) e sem nota nem
  veredito no título (ex.: "Suki Acijaggur: monge com Bomba Relógio? A roleta
  surtou"). **7 continuam fora de propósito**: `generation_00026/28/29` (A e
  B) e `generation_00027` (A) são re-execuções de seed fixa (99 e 4242) da
  MESMA build já publicada como `00025` e `00024` — mesmo personagem, mesma
  nota, mesmo gancho B. Título novo ali poria o mesmo vídeo no ar de novo.
  Conferido com `postar.py --ver --so builds`: "25 fora por título" virou 7,
  gordura de builds 0 → 2 dias.
- **A luta sem o som do jogo** (28/09). A guarda media o arquivo inteiro, e
  a música esconde uma luta calada. A causa era de render: o gravador
  escrevia `anullsrc`, o corte de tédio aplicava `-an`, e o som do jogo nunca
  entrou num mp4; desde 02/09 o que entrava era o sintetizado
  (`trilha.sfx_da_luta` — no `duelo_00015`, 25 vezes o mesmo hit e 14 o mesmo
  grave). A publicação passou a medir cada trecho de luta; a origem foi
  consertada na 16A (§7).

## 5. Estado de hoje (28/09/2026, madrugada)

- **Duelos**: rodada manual com vigia (armado 23:58, encerrou sozinho às
  02:19) gerou **8 duelos novos, `duelo_00016` a `00023`, 16 nomes diferentes**
  (A: 5 entre 01:00 e 01:20; B: 3 entre 01:55 e 02:03). ~4,5 min por duelo;
  duração 13–28 s; áudio medido nos 8: média -12 a -16 dB, zero silêncio. As
  tarefas das 01:02 e 02:02 saíram com "já rodando", como previsto. **12 no
  estoque** que a grade escolheria (`00012`–`00023`), teto 10: ~2 dias.
  Atenção: `duelo_00023` é "Kuro #2 x Orion o Implacável" — o `#2` é
  desempate de nome do banco e vai no título.
- **Builds**: 18 variantes B voltaram à fila com título próprio (§4); a
  `generation_00083` B já saiu (00:37). Gordura de builds 2 dias pelo
  `postar.py --ver`.
- **Worker** (rodadas das 02:04, 03:02, 04:02 e 05:02): as **3 imagens** de
  `generation_00085` e de `generation_00077` estão prontas; as da 00085 com
  prova de origem forte (`identity auditar`: 3 de 3). Às 03:02 e 04:02 o
  PicassoIA estava preso pela rodada de histórias (mesma trava de perfil); a
  partir das 03:06 um provedor ocupado passa a vez ao outro em vez de encerrar
  o worker. **Os dois payoffs do Digen faltam**, e as duas builds seguem fora
  da fila por pendência:
  - `generation_00085#character_weapon` **falhou 3 vezes às 04:03–04:07**
    (`failed`): um diálogo de propaganda do Digen ("Upgrade",
    `pc-pop-916.webp`, `role=dialog`) cobre o composer e engole o clique —
    a mesma família da "parede do PicassoIA". O anexo da referência também não
    entrou. **Consertado em 28/09 (08:00)**, olhando a tela: a propaganda
    aparece sozinha 10–15 s depois de a página carregar e fecha pelo X
    (`button[data-slot="dialog-close"]`). `client.instalar_guarda` registra
    um `add_locator_handler` do Playwright que fecha a parede antes de TODA
    ação na página (inclusive os cliques de `escrever` e `referencias.anexar`
    e as novas tentativas de um clique que já esperava), e há chamada
    explícita a `tirar_parede_da_frente` antes de cada clique do fluxo e na
    espera. Só o modal do shadcn (`data-slot="dialog-content"`): os popovers
    de modelo/duração/anexo também são `role=dialog` e não podem ser
    fechados. Provado no navegador de verdade com uma parede de mesma
    estrutura: o clique cru passou em 0,2 s. A conta do Digen aparece como
    **Free** (Meme 221, Pro Meme 0).
  - `generation_00077#character_weapon` pendente: não coube às 05:12 (18 min).
    Desde 28/09 à noite a 00077 está descartada (§4) e o worker não pega
    mais esse job.
  Build não tem `capa.png` (só duelo tem); o que falta nas duas é o payoff.
- **82 personagens e 95 armas** no banco vivo; só **9** dos personagens de
  roleta estão nele (os de agosto se perderam em 02/09).
- **Estreia**: nenhuma em estoque. A da `generation_00066` (muda) foi
  descartada de forma reversível (§4); o horário da estreia vai para outro
  formato.
- Pendente:
  - **7 builds fora por título** que são a mesma build de outra (§4) —
    decisão do Adrian se ficam fora para sempre;
  - a roleta entrou na rodada noturna em 28/09 (§2); a estreia sai dentro
    dela. Primeira roleta automática ainda não aconteceu (estoque acima do
    teto).

## 6. Como conferir sem publicar

```bash
cd E:\projetos\random_builds
python main.py fluxo --limite 30        # onde cada build está e o próximo passo
python main.py fluxo --json             # o mesmo, estruturado
python main.py publicar                 # LISTA o catálogo (sem id e sem flag, não envia nada)
python main.py metricas                 # sem --atualizar: mostra o último dado salvo
python main.py arena ranking            # cartel dos personagens
python main.py cobertura --apenas-faltando   # o que o banco tem e o vídeo não sabe descrever
python main.py noite --listar           # tarefas de geração + duelos que a grade escolheria
python main.py som-da-luta --listar     # estoque não publicado com a luta muda (§7); não muda nada

cd E:\projetos
python ferramentas/postar.py --ver --so builds   # diz o que postaria e SAI
```
Estoque por formato existe em código (`postar.estoque_por_formato()`, medido
contra a cota de cada um) e aparece no aviso do Telegram. O de duelo que a
geração noturna usa (`noite.estoque_de_duelos()`) passa pelo funil da
escolha e aparece em `main.py noite --listar`.

**O que NÃO fazer:** não rodar `main.py publicar <id> --youtube/--tiktok`
(publica de verdade), nem `postar.py` sem `--ver`, nem `--instalar`. Não usar
`--forcar` para empurrar vídeo com pendência (mudo, sem payoff, sem luta) —
a pendência é a única coisa que segurou a estreia muda. Não apagar pasta de
`outputs/`: o ledger e as métricas referenciam o id. Não editar
`neural_fights/data/personagens.json` esperando mexer no banco vivo (é o
snapshot do pacote). Não refazer o banco: foi isso que matou agosto. E evitar
gerar vídeo entre :25 e :55, que é a janela da grade.

## 7. O som da luta (Onda 16A, 28/09/2026)

Decisão do Adrian (28/09): o visual atual continua publicando, mas já com o
som de verdade do jogo. Até aqui o som do jogo nunca tinha entrado num mp4
(§4, "Vídeo mudo").

**Como é agora.**
- O gravador põe um `AnotadorDeAudio`
  (`neural_fights/effects/audio_anotador.py`) no lugar do `AudioManager`: ele
  herda toda a decisão de som do jogo (qual som, variante do grupo, volume por
  categoria e por distância) e anota em vez de tocar. A lista `sons` (formato
  em `docs/palco/sons.md`) atravessa o corte de tédio (`remapear_gravacao`) e
  fica em `fight.json` → `luta.sons`, no relógio do clipe.
- O render mistura a lista com os arquivos que o jogo usa
  (`neural_fights/effects/mixagem.py`: `%LOCALAPPDATA%\neural-fights\sounds\`
  antes do pacote, pelo `sound_config.json` e pelos fallbacks do jogo), com o
  pitch anotado, nível por trecho e limitador. O bruto da gravação também sai
  com esse som no lugar do `anullsrc`, e o corte leva o áudio junto (partes
  em PCM: com aac, um estalo caía 67 ms atrasado já na 2ª parte).
- A luta não muda: a variante do grupo continua sorteada pelo `random`
  global, como no jogo, e o teste compara vencedor, duração, HP, golpes e o
  estado do `random` no fim, com e sem anotador. O pitch (golpes ±7%,
  impactos ±6%, projéteis e skills ±4%, movimento ±8%, ambiente fixo) usa um
  `Random` próprio semeado pela seed da luta.
- Knob em `config/editing.json` → `som_da_luta`: `real` (liga),
  `sintetizado_de_reforco` (**desligado**: medido, o som real sozinho já deixa
  o trecho com 0% calado e 9 a 11 arquivos distintos; o sintetizado só
  somava repetição) e `alvo_db` = -13 (o trecho de luta em ~-18 LUFS, o nível
  em que o sintetizado estava).
- Luta gravada antes de 28/09 não tem `sons` e segue no sintetizado.
  `main.py som-da-luta <id>` re-simula a MESMA luta sem vídeo, confere
  vencedor, duração e golpes contra o `fight.json` (recusa se divergir) e
  re-renderiza no lugar — numa geração, a estreia e a build juntas. Nenhum
  alvo começa se não termina antes de :25.
- Consertos no caminho: o transcode simples do renderer saía com código 0 e
  SEM faixa de áudio (a 2ª tentativa nunca rodava) — agora refaz, e sem áudio
  mesmo assim é erro; o sintetizado do trecho de luta no fim do build
  ignorava o `start_offset` (tocava os golpes dos primeiros 6,5 s da luta
  sobre os últimos).

**Medido nos pares** (`random_builds\outputs\_ouvir\`, mesmo duelo e mesma
seed; "trecho" = o segmento de luta antes da música, que é o que a guarda
mede):

| duelo | trecho de luta: antes → depois | variedade: antes → depois | vídeo final |
|---|---|---|---|
| `duelo_00014` (machados de arremesso × corrente) | -18,2 → -17,8 LUFS; **63% → 0% calado**; LRA 23,7 → 4,1 | 36 camadas de 5 sons sintetizados (15 hits e 15 graves iguais) → 217 sons, 19 ids, **11 arquivos** | -15,0 → -15,5 LUFS |
| `duelo_00016` (piromante × machado-martelo) | -18,3 → -18,7; **57% → 0%**; LRA 17,4 → 7,2 | 22 camadas de 4 (15 hits iguais) → 161 sons, 19 ids, **11 arquivos** | -16,6 → -16,5 |
| `duelo_00022` (bestas, gelo) | -15,4 → -17,3; 29% → 0%; LRA 4,0 → 8,4 | 47 camadas de 4 (22 e 18 iguais) → 57 sons, 14 ids, **9 arquivos** | -13,7 → -15,4 |

A imagem é idêntica quadro a quadro nos três pares (`framemd5` do vídeo
igual): só o som muda. O wav do trecho sai limitado em -2,5 dBFS; o aac
intermediário pode passar disso (até +1 dB, em float, no `00014`: quatro
`energy_impact` no mesmo quadro), e a mixagem final — float, com `alimiter` e
`loudnorm` TP -1,5 — fecha com pico de -0,9 a -1,4 dB.

O juiz do som é o Adrian (o Gemini não recebe áudio). **O re-render do
estoque espera a aprovação dele**, e roda de madrugada.

**Estoque com a luta muda** (`som-da-luta --listar`; a régua da LUTA da
guarda da publicação desde 6f09b80: média do trecho < -60 dB ou trecho sem
faixa de áudio — silêncio entre golpes não conta). Em 28/09, 07:31: 38
vídeos não publicados com luta (12 duelos, 26 builds), **2 mudos, de uma
fonte só**: `generation_00077` A e B (`seg_022` a -91 dB; render de 29/08,
antes do sintetizado). Som real impossível: Seraphina Pyrberim e Lucrecia
Aciaegir saíram do banco em 02/09 e a luta não re-simula. **Descartada em
28/09** (decisão `generation-00077`, build e estreia; §4). A
`generation_00066/estreia` (-91 dB) foi descartada pela decisão 5 do Adrian
(`config/publicacao.json` → `descartados`).

Os outros 36 estão com o sintetizado. Sete deles ficam calados em 57–63% do
trecho (`duelo_00014`, `00016`, `00017`, `generation_00029` A e B,
`generation_00077` A e B) — não é luta muda pela régua, mas é o som que
repete. Com o som aprovado, o re-render com o som real (de madrugada; o
comando para antes de :25 e continua depois de :55):
`python main.py som-da-luta duelo_00012 duelo_00013 duelo_00014 duelo_00015 duelo_00016 duelo_00017 duelo_00018 duelo_00019 duelo_00020 duelo_00021 duelo_00022 duelo_00023 generation_00029`
(~4 min por duelo). Conferido em 28/09 às 03:02 (`--so-anotar` numa cópia):
`duelo_00017` e os dois rounds de `generation_00029` re-simulam iguais ao
clipe; `00014`, `00016` e `00022` são os pares. As builds de antes de 11/09
(motor mudou na 15C) e as de elenco de agosto provavelmente não re-simulam:
o comando recusa e diz qual.

## Contratos com outras partes

- **Catálogo que a publicação lê** — `builds/publicar/catalogo.py` varre
  `outputs/` e devolve `Video(id, origem, perfil, titulo, descricao, hashtags,
  variante, pendencias, capa)`. Eu mando nos arquivos que ele encontra
  (`final_<perfil>.mp4`, `capa.png`, os JSONs); a publicação manda no que faz
  com eles. Os textos vêm de `config/publicacao.json`, não de código.
- **Banco de personagens e armas** — `%LOCALAPPDATA%\neural-fights\{personagens,
  armas}.json`. Escritor único: `builds/nf_bridge/exporter.py` via
  `salvar_database(substituir=False)`, disparado só por `generate-video`.
  Todo o resto (duelo, fight, torneio, catálogo) apenas LÊ.
- **Títulos editados** — `outputs/_publicar/_textos/<id>.json`
  (`catalogo.salvar_texto`): valem sobre o título gerado, para o painel e para
  a grade. É onde moram os títulos próprios das variantes B (27/09/2026).
- **Tarefas de geração** — `NeuralFights_gerar_01..05` (HH:02), família
  minha (`builds/pipeline/tarefas_noite.py`), trava `builds__gerar`; duelos
  e roleta (a roleta escreve no banco pelo mesmo `exporter`). Os
  monitores de tarefa de outras partes (`remoto/relatorios.py`,
  `visao/panorama/recursos.py`) ainda listam só postagem e bot.
- **Ledger da arena** — `outputs/_arena/ledger.json`, dono meu
  (`builds/arena/ledger.py`): registra cada round e escolhe adversário por
  continuidade/poder.
- **Ledger de publicação** — `outputs/_publicar/publicados.jsonl`, dono da
  publicação. Eu só leio (para saber o que já saiu).
- **Diário** — `%LOCALAPPDATA%\neural-fights\atividade.jsonl`
  (`builds/atividade.py`), uma linha JSONL por evento; escreve quem faz a ação,
  leem o bot, o painel e o app do celular.
- **Grade de horários** — `builds/grade.py`, uma cópia só, usada por builds e
  histórias. A cota de formatos é minha (config acima); a hora não.
- **Som da luta** (Onda 16A) — `fight.json` → `luta.sons` (e o `gameplay` do
  `edit_plan.json`), no relógio do clipe; o formato está em
  `docs/palco/sons.md`, e é a seção `sons` da timeline da 16C (o palco lê de
  lá). A guarda de luta muda POR TRECHO é da publicação: ela mede os
  `_segments_<perfil>/seg_NNN.mp4` dos eventos `gameplay`, que o render daqui
  produz.
- **Timeline do palco** (Onda 16C) — o arquivo de que o Godot desenha a luta:
  um valor por passo de 60 Hz (lutadores, arma com a geometria da hitbox,
  câmera, objetos, efeitos, eventos, `sons`, `remapeamento`), schema em
  `docs/palco/timeline.md`. Sai do gravador com `--timeline CAMINHO`
  (`.gcpf` = container zstd que o Godot abre nativo) e do
  `neural_fights.recording.timeline.gravar_timeline(desenhar=False)`, que é o
  que o palco usa: mesma luta, mesma câmera e mesmo som do gravador, 10× mais
  rápido (medido no `duelo_00014`). Os vídeos de hoje não gravam timeline.
- **O palco** (Onda 16D) — o projeto Godot `palco/` desenha a luta a partir da
  timeline e grava o vídeo COM o som do jogo; o lado Python é
  `builds/palco/` (`main.py palco ...`, `main.py duelo --palco [--ab]`).
  **Não publica e não entra no catálogo**: sai em `outputs/_palco/`. A troca do
  visual é a 16G, com a aprovação do Adrian. Como funciona, comandos, guardas
  e medidas: `docs/palco/README.md`; como trocar arte e som:
  `docs/palco/COMO-EDITAR.md`. O `main.py` só importa `builds.palco` no ramo
  `palco`/`--palco`: erro no palco não derruba publicar nem a geração noturna.
