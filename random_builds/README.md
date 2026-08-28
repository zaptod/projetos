# Random Builds — Roleta Procedural do Neural Fights

> **Painel de controle:** tudo daqui (e do neural_fights: simulação, torneio,
> lives, database) é acessível pela interface gráfica — dois cliques em
> `painel.bat` na raiz de `e:\projetos` (ou `python painel_ui.py`).
> Versão de terminal: `python painel.py`.

Sistema de vídeos no estilo **"Vamos criar um personagem aleatório"**, moldado
100% pela base de dados do **neural_fights**:

- **Nenhuma categoria é inventada.** Classes, personalidades, tipos de arma,
  estilos, raridades, encantamentos e skills vêm dos catálogos canônicos do
  jogo (`neural_fights.models.constants`, `ai.personalities`, `core.skills`,
  `tools.gerador_database`). Se o jogo ganhar uma classe nova, a roleta muda junto.
- **Roleta visual giratória.** Cada rolagem é uma roda com TODOS os resultados
  possíveis naquele momento (pós-regras: só estilos do tipo sorteado, dano na
  curva da raridade etc.), girando com desaceleração até o ponteiro parar no
  vencedor, que fica destacado.
- **Inserção no banco.** No final, personagem + arma são construídos pelas
  fábricas oficiais (`gerar_arma`/`gerar_personagem` — nome, cor, geometria por
  estilo, passiva) e anexados ao banco vivo do jogo via `salvar_database`
  (`%LOCALAPPDATA%\neural-fights\`), com validação oficial e nomes únicos.

- **Três vídeos de recompensa.** Cada build gera, no [Digen](https://digen.ai),
  um clipe do **personagem**, um da **arma** e um dos **dois juntos** — este
  último é o payoff final. Os três saem da mesma `CHARACTER_IDENTITY` +
  `WEAPON_IDENTITY` gravadas em disco, e é isso que mantém o mesmo rosto e a
  mesma lâmina nos três. A roleta não espera: ela enfileira e termina; um
  worker baixa os clipes depois e refaz o vídeo com eles dentro.
- **Ritmo de TikTok, não de ficha de RPG.** A roleta é o elemento dominante
  (título curto → resultado → roda grande), a revelação é vídeo e não cartão,
  e reação só entra onde o resultado justifica.

## Uso

```bash
python main.py generate-video                        # roletas -> 2 videos -> insere no NF
python main.py generate-video --seed 847293847       # mesma seed = mesmo video/build
python main.py generate-video --preview              # render rapido (metade da resolucao)
python main.py generate-video --no-insert            # nao toca o banco do jogo
python main.py generate-video --no-identity          # nao enfileira o clipe do Digen
python main.py generate-video --generation-only      # so dados (nunca insere)
python main.py generate-video --generation-only --count 1000   # balanceamento
python main.py generate-video --rerender generation_00001      # re-render puro

# roleta com nome pedido num comentario, creditando quem pediu e mostrando o print
python main.py generate-video --nome-pedido "Kaelen" --autor-pedido "@zeca" \
                              --print-pedido "C:/Users/adrian/Desktop/comentario.png"
# print que chegou depois: entra num video ja gerado, sem rolar nada de novo
python main.py generate-video --rerender generation_00061 --print-pedido print.png

python main.py generate-video --atributos                      # o que da para escolher
python main.py generate-video --genero feminino                # so o genero fixado
python main.py generate-video --fixar classe=Cavaleiro --fixar tamanho=1,92

python main.py tournament                                      # torneio -> 2 videos
python main.py tournament --fonte gerados --participantes 8    # so quem saiu das roletas
python main.py tournament --seed 4242 --preview
python main.py tournament --generation-only                    # so as lutas, sem video
python main.py tournament --rerender tournament_00003          # reaproveita as lutas gravadas
python main.py tournament --rerender tournament_00003 --refazer-edicao

python main.py fight                                           # uma luta -> 2 videos (ver "As lutas sao o produto")
python main.py fight --p1 "Kael" --p2 "Lyra" --seed 7 --preview
python main.py generate-video --no-estreia                     # roleta sem gravar a 1a luta
python main.py arena ranking                                   # cartel de todo mundo

python main.py fluxo                                           # onde cada build esta e o proximo passo
python main.py fluxo --limite 30                               # mais builds no relatorio
python main.py fluxo --json                                    # o mesmo dado, estruturado

python main.py publicar                                        # lista TODO video pronto, com texto pronto
python main.py publicar <id> --exportar                        # copia com nome legivel + .txt do texto
python main.py publicar <id> --youtube                         # API oficial (privado por padrao)
python main.py publicar <id> --youtube --visibilidade public   # publico (confirma no painel)
python main.py publicar <id> --tiktok                          # navegador: sobe e PARA antes de postar
python -m src.publicar.tiktok --login                          # login do TikTok (uma vez)

python main.py reactions                                       # assistente interativo
python main.py import-reactions <pasta> --categoria insane     # importa direto (scripts)
python main.py import-reactions clip.mp4 --categoria terrible --move
python main.py list-reactions                                  # lista a biblioteca
```

**Onde eu estou? (`fluxo`, e a página 🧭 Fluxo do painel):** a pipeline tem
quatro trilhos que andam em tempos diferentes — a build (roleta), a
identidade (duas imagens e um vídeo, fila assíncrona em dois sites), a
estreia (a primeira luta do personagem) e o torneio (que consome quem já
está pronto). Cada trilho tem seu próprio status, e é por isso que dá para
se perder: nenhum deles responde *"e agora, o que eu faço?"*.

O fluxo responde. Uma linha por build, uma coluna por etapa
(`BUILD · PERSON. · ARMA · JUNÇÃO · VÍDEO · ESTREIA`) e **uma frase com o
próximo passo** — já com o comando que destrava aquela build. Embaixo, o
estado da fila, o campeão da arena e a preparação das chaves (quantas builds
têm vídeo pronto, que tamanho de chave dá para montar com elas e com o
banco). Os alertas são os casos que nenhuma ferramenta reporta sozinha: job
com tentativas esgotadas, worker parado com fila cheia, e clipe baixado que
**não entrou** no mp4 publicável.

A regra de estado mora em `src/pipeline/fluxo.py` (puro leitura, testável
sem abrir janela); o painel e a CLI só desenham o mesmo dado. Na página do
painel, selecionar uma linha dá os botões do passo: assistir, abrir pasta,
re-renderizar, enfileirar identidade, gerar estreia.

**Publicar sem caçar arquivo (`publicar`, e a página 📤 Publicar):** os mp4
nascem em três lugares (`generation_XXXXX/`, `.../estreia/`,
`tournament_XXXXX/`), todos com o mesmo nome e nada dizendo de quem são —
achar o arquivo certo era o trabalho chato. A página junta os três num índice
só, com **título e descrição já escritos** a partir dos dados da build
(personagem, classe, arma, nota; adversário e desfecho na estreia; campeão no
torneio) e as hashtags do `config/publicacao.json`. O texto é editável na
tela e o que você salvar passa a valer — inclusive num envio futuro para a
outra plataforma.

Daí saem três caminhos:

- **Exportar**: copia o mp4 para `outputs/_publicar/` com nome legível
  (`20260827_generation_00057_celular_Aurelio-Iskarfael.mp4`) e grava um
  `.txt` ao lado com título, descrição e hashtags prontos para colar.
- **YouTube**: API oficial (Data API v3, upload resumável) reusando o OAuth
  que a live já tem — falta só autorizar o escopo de upload uma vez
  (`identity`/painel: **Autorizar upload no YouTube**, que roda o
  `youtube_oauth --com-upload`; o mesmo arquivo continua servindo ao chat da
  live). Sobe como **privado** por padrão: quem decide publicar é você, no
  Studio. Público exige confirmação no painel.
- **TikTok**: não existe API aberta de post (a oficial exige app aprovado em
  review), então é navegador — o mesmo padrão do PicassoIA/Digen: Chrome de
  verdade, perfil persistente em `.browser_profile/tiktok`, login manual uma
  vez. O painel sobe o arquivo, escreve a legenda e **para antes de
  publicar**, com a janela aberta para você conferir. Quando o site mudar,
  `python -m src.publicar.tiktok --sondar` despeja o DOM da tela de upload
  para reajustar os seletores (mesma ideia do `identity probe`).

**Nome pedido num comentário, com o print como prova:** `--nome-pedido`
troca o nome gerado pelo do comentário (validado por `src/character/nomes.py`
— moderação, alfabeto latino, 4 palavras, 28 caracteres; recusado, o vídeo
volta a apenas convidar) e `--autor-pedido` credita quem pediu. O que faltava
era a **prova**: `--print-pedido <imagem>` põe o print do comentário como
tela, logo depois do gancho — cedo de propósito, enquanto ainda vale
convencer.

O arquivo é copiado para dentro da geração como `comentario.png` (ou
`.jpg`/`.jpeg`/`.webp`): o print costuma nascer na área de trabalho, e um
re-render meses depois não pode depender de um arquivo que você já apagou.
Largar a imagem com esse nome na pasta da geração e re-renderizar com
`--refazer-edicao` tem o mesmo efeito — e `--print-pedido` junto de
`--rerender` faz as duas coisas de uma vez, que é o caso normal: o print
quase sempre chega depois do vídeo pronto. Print que não existe ou não é
imagem **falha alto**, em vez de render um vídeo sem a prova e você
descobrir na hora de publicar.

A tela usa o mesmo motor da revelação de identidade (contain, fundo da
própria imagem borrado, estalo de entrada), com duas diferenças declaradas em
`config/editing.json → comentario`: zoom quase parado (`1.0 → 1.03`), porque
Ken Burns em texto pequeno deixa o print ilegível, e **sem a placa do
rodapé**, que cobriria justamente o comentário — o crédito vai numa etiqueta
pequena no topo (`PEDIDO DE @zeca`). No painel, na página **🎬 Vídeos de
Build**: campos *Nome* / *de* e o botão **🖼 Print do comentário…** no card
de gerar, e **+ print do comentário** no card de re-renderizar.

**Escolher em vez de sortear (`--genero`, `--fixar`):** a premissa do formato
é a roleta decidir, então escolher é **exceção** — o padrão continua sendo
sortear tudo. `--genero masculino|feminino` fixa o gênero (que não é roleta de
tela: sai do sorteio do nome e serve à coerência do desenho) e
`--fixar atributo=valor`, repetível, fixa qualquer roleta:
`--fixar classe=Cavaleiro --fixar tamanho=1,92`. `--atributos` lista os 15
com faixas e opções. No painel: **🎛 Escolher atributos…** na página 🎬 Vídeos
de Build, com um combo por atributo categórico e um campo por numérico, todos
começando em *— sortear —*.

Quatro decisões que sustentam isso:

- **A roleta fixada continua girando e consumindo o RNG dela.** É a mesma
  doutrina do nome pedido: o sorteio roda igual e só o valor final é trocado.
  Sem isso, economizar um `choice` deslocaria a corrente e escolher a altura
  mudaria a arma. Travado em teste: fixar `tamanho` muda **só** `tamanho`, e
  nome, arma e cor do personagem ficam idênticos. O que legitimamente depende
  do valor escolhido muda junto (fixar `raridade=Mítico` reclampa a faixa de
  `dano` — é a regra do gerador, não efeito colateral).
- **A roda mostrada continua inteira**, parando no valor escolhido. Uma roda
  de um segmento só denunciaria a escolha e transformaria a cena numa placa.
- **O `generation.json` guarda o que teria saído** (`escolhas.sorteado`), do
  mesmo jeito que guarda o nome gerado quando um comentário venceu.
- **O vídeo não mente.** Havendo escolha, o gancho troca para o pool
  `hook_escolhido` ("NEM TUDO FOI SORTEADO HOJE") em vez de abrir com "100%
  ALEATORIO", a legenda da roleta fixada usa o banco `escolhido` de
  `frases.json` ("escolhi 1,92m") em vez de creditar a sorte, e a descrição de
  publicação troca "Personagem 100% aleatório / Tudo sorteado por roleta" por
  "quase todo aleatório" + a lista do que foi escolhido a dedo. O mesmo vale
  para o nome pedido, que antes desta onda continuava afirmando aleatoriedade
  no texto publicado.

Escolha inválida **falha alto**, na entrada: atributo que não existe, valor
fora da faixa, opção inexistente, prefixo ambíguo. Um atributo silenciosamente
ignorado viraria um sorteio que você acha que escolheu. Acento e caixa não
importam (`raridade=mitico` acha `Mítico`) e prefixo único serve
(`classe=Cavaleiro` acha `Cavaleiro (Defesa)`).

**Assistente interativo (`reactions`):** menu para inserir e categorizar
vídeos — modo INDIVIDUAL (um arquivo: mostra duração/resolução, escolhe a
categoria numerada, copia ou move) e modo LOTE (pasta inteira: mesma
categoria para todos, ou escolhendo vídeo por vídeo com `s` para pular e `q`
para encerrar). Também lista, recategoriza e remove por ID.

**Categorizar assistindo (janela do painel):** para triar um pack grande sem
abrir cada arquivo na mão. Na aba Reações do painel, o botão
**🎬 Categorizar assistindo…** abre uma janela que **toca os vídeos da pasta
um a um, embutidos na própria janela** (via ffplay); cada clique (ou tecla
1–9) importa na categoria escolhida pelo mesmo importador do
`import-reactions` — com pular (`s`), desfazer de verdade (`z` — remove do
catálogo e devolve o arquivo se ele foi movido) e contador por categoria em
cada botão. Vídeo cujo nome já consta como origem no catálogo não volta à
fila, então recarregar a mesma pasta nunca importa duas vezes. A lógica da
sessão vive em `src/assets/triagem.py`; sem ffplay no PATH, cada vídeo abre
no player padrão do sistema e os botões continuam valendo.

**Toda geração produz DOIS vídeos:** `final_celular.mp4` (1080x1920, 9:16,
título e resultado em cima, roda grande embaixo) e `final_normal.mp4`
(1920x1080, 16:9, roda à esquerda/resultado à direita). Os perfis ficam em
`config/render.json`.

## A montagem

```
gancho (1,4 s)
roletas do personagem        giro 1,15 s + resultado 0,8 s (2,45 s nos extremos)
CHARACTER_VIDEO              2-5 s      primeira recompensa
"agora a arma"               0,9 s
roletas da arma
WEAPON_VIDEO                 2-4 s      segunda recompensa
[compatibilidade]            1,6 s      SÓ quando o número surpreende
CHARACTER_WEAPON_VIDEO       3-6 s      payoff final
nota final (1,7 s) + outro (1,5 s)
```

Enquanto um clipe não chegou, o lugar dele é ocupado por um **nameplate**:
nome grande e uma linha de dado, tipografia pura — nunca um avatar genérico
nem uma ficha. Com o clipe, o mesmo texto vira uma placa discreta que entra e
sai por cima do vídeo.

O que saiu do formato anterior: a ficha de personagem, a ficha da arma, a tela
longa de compatibilidade e a tela de estatísticas do fim. Um vídeo que durava
**101 s** (69 s só de roleta parada em telas de interface) agora dura ~**42 s**
sem os clipes e ~**55 s** com os três.

**Reação não sai depois de toda roleta.** Cada rolagem é classificada
(`ABSURD`, `CONTRADICTORY`, `RARE`, `FUNNY`, `VERY_GOOD`, `GOOD`, `NORMAL`,
`BAD`) a partir do score, da probabilidade da opção e do método de avaliação;
a chance de reação vem da classe, com teto por vídeo, distância mínima entre
duas e nunca duas seguidas. Um resultado mediano improvável rende mais tela
que um bom comum, e uma arma que o personagem não levanta é *contraditória*,
não *ruim* — e pede outra reação. Tudo em `config/editing.json`.

## As lutas são o produto (Onda 9)

A roleta cria o personagem; **a luta é o que ele existe para fazer**. Três
formatos saem do mesmo gravador e do mesmo motor:

| comando | o que é | onde sai |
|---|---|---|
| `generate-video` | roleta + **estreia**: a primeira luta do personagem recém-criado, gravada logo após a inserção no banco | `outputs/<gen>/estreia/` |
| `fight` | uma luta, um vídeo (avulsa, revanche, defesa de título) | `outputs/fight_XXXXX/` |
| `tournament` | mata-mata; cada luta é um bloco do vídeo | `outputs/tournament_XXXXX/` |

```bash
python main.py fight                                   # ultimo criado x adversario por continuidade
python main.py fight --p1 "Kael" --p2 "Lyra" --seed 7  # duelo escolhido, reproduzivel
python main.py fight --arena Dojo --preview
python main.py fight --rerender fight_00003 --refazer-edicao
python main.py generate-video --no-estreia             # roleta sem a estreia
python main.py arena ranking                           # cartel de todo mundo
```

### O que mudou em relação ao "melhores momentos"

O formato anterior gravava a luta com a **câmera travada na arena inteira**
em 540×960 e mostrava **10 s** dela (janela quente + KO). No 9:16 isso dava
lutadores com 5 % da largura, borrados pelo upscale 2×, sem contexto. A
doutrina agora é a mesma da roleta: **a luta é o elemento dominante** (pelo
menos metade do vídeo, travado em teste), legível no celular.

- **Câmera DIRETOR** (`neural_fights/effects/camera.py`): câmera de
  transmissão, não de jogo. Zona morta com histerese (passos curtos não
  movem o quadro), pan lento (2,4/s contra 8/s do AUTO), zoom-in só depois
  de 1 s de estabilidade e +12 %, zoom-out rápido (nunca perde ninguém),
  push-in no KO, sem tremor e sem punch. O teto de zoom é em **metros**: o
  lado menor da tela nunca mostra menos de 7 m — em 1080×1920 o lutador
  fica com ~11,5 % da largura (era 4,3 %). Clamp macio à arena (até 35 % da
  janela pode sair dela) para centralizar a luta e não o palco.
- **Resolução nativa**: `--resolucao 1080x1920` / `1920x1080` no gravador
  (match_config `resolucao`). Zero upscale. Medido: câmera e resolução
  **não alteram a luta** — mesma seed, mesmo vencedor, mesma duração, mesmo
  HP (`tests/test_fight_recording_regressions.py`).
- **HUD do vídeo, não do jogo**: grava com `--sem-hud`; o gravador exporta
  `serie_hp` (a cada 0,25 s) e o renderer desenha as barras na tipografia do
  canal, com as cores dos lutadores e vida crítica piscando.
- **Corte de tédio** (`highlights.planejar_corte_tedio`): a luta entra quase
  inteira. Só saem janelas de mais de 4 s sem dano, com 1 s de contexto em
  cada ponta; os 8 s antes do KO são intocáveis; nenhum corte cai dentro de
  um combo (por construção: combo é sequência de golpes a menos de 1 s).
  Teto de 45 s; passando dele a regra aperta em degraus e, em último caso,
  cai no recorte antigo. HP e eventos são remapeados para o relógio do clipe.
- **Callouts sincronizados com o motor**: os tells da Onda 8 (instinto,
  desvio, punição, parry, clinch), combos, primeiro sangue, viradas de
  liderança e o KO saem da gravação como `eventos_narrativos` e viram texto
  grande sobre o gameplay (`PARRY!`, `COMBO x4`, `VIROU!`, `K.O.`). Orçamento
  em `config/editing.json → fight_callouts`: 1,2 s entre dois, no máximo 3
  por janela de 10 s, prioridade quando disputam.
- **Legibilidade medida** (`python -m neural_fights.tools.qualidade_luta
  --video`): alvos V7 no ledger de qualidade, travados no medido — lutadores
  visíveis ≥ 98 % dos frames, tamanho mediano ≥ 8 % da largura, pan p90
  ≤ 0,6 larguras/s, ≤ 16 trocas de zoom/min (metas plenas 10 % e 8 em
  `V7_*_meta`). Medido na fixture congelada (4 lutas): 98,9 % / 0,090 /
  0,46 / 13,9 — o resíduo é kiting de arqueiro. Luta melee de referência:
  100 % / 0,115 / 0,30 / 1,9. A câmera ARENA antiga dava 0,043 de tamanho.

### Carreira: o ciclo fecha

Toda luta gravada para vídeo vai para `outputs/_arena/ledger.json`
(`src/arena/ledger.py`, escrita atômica, idempotente por luta). É dele que
saem o **cartel** no card (`Kael (3V-1D) x Lyra (0V-2D)`), o gancho de
**revanche** (já se enfrentaram) e de **título** (o vencedor da última luta
registrada defende), e o `arena ranking`.

O adversário da estreia (e de um `fight` sem `--p2`) segue
`escolher_adversario`: primeiro o personagem **gerado mais recente** que
ainda não lutou com ele — "o de ontem contra o de hoje" liga um vídeo ao
outro —, senão alguém de poder próximo (força+mana), para a estreia não ser
atropelo por construção. A estreia não entra no vídeo da roleta de
propósito: estouraria o teto dele (95 s) e roubaria o lugar do elemento
dominante de lá. É o "parte 2" natural; o outro da roleta já convida.

### A estreia é melhor de 3

Uma luta só decidia a carreira do personagem num round que pode virar por um
crítico. A estreia agora é uma **série** (`estreia_melhor_de: 3` em
`config/editing.json`; ímpar, e `1` devolve o vídeo de luta única sem mais
nada mudar). Regras:

- A série **para assim que o placar fecha**: num 2 x 0 o terceiro round nem é
  gravado — meia gravação economizada por estreia dominante.
- Todos os rounds acontecem na **mesma arena**, com seed derivada
  (`seed + i*17`) e prefixo de arquivo próprio: é o mesmo confronto, não três
  lutas soltas.
- O vídeo conta a série: card e showcase de kit **uma vez** (quem entra na
  arena é o mesmo), e o miolo repete por round — `round_title` → gameplay →
  `round_result` com o placar correndo (`1 x 0`, `1 x 1`, `2 x 1`). O
  `fight_result` do fim é o veredito da **série**, com o placar sob o nome.
- **Cada round entra no ledger** (`match_id` distinto, senão os três
  colapsariam numa linha só): o cartel conta rounds, não séries.
- `estreia.json` ganhou `melhor_de`, `placar` e `rounds[]`; `vencedor` passou
  a ser o da série. O título de publicação diz "venceu por 2 x 1" no lugar de
  "venceu por KO", que descreveria só o round que fechou.

Luta avulsa também aceita: `python main.py fight --melhor-de 3`.

- **Gravador**: `python -m neural_fights.recording.fight_recorder --p1 X --p2 Y
  --seed 7 --saida luta.mp4 --camera DIRETOR --resolucao 1080x1920 --sem-hud`.
  Roda o `Simulador` com `headless=False` + `SDL_VIDEODRIVER=dummy`: nenhuma
  janela abre e todo o VFX continua vivo (o modo headless do jogo apaga
  auras, trilhas de skill e telegraph, além de congelar as animações
  pulsadas). Devolve JSON com resultado, `eventos_dano`, `serie_hp`,
  `eventos_narrativos` e `metricas_video`, tudo em tempo de vídeo.
- **A gravação é a fonte da verdade**: a luta é simulada UMA vez, desenhando.
  Simular em headless e regravar depois seriam dois caminhos de código — se
  divergissem, o vídeo contradiria o placar mostrado em seguida.
- **Custo**: ~1,5× tempo real por luta em 1080×1920 (os dois formatos gravam
  em paralelo). `--rerender` reaproveita o gameplay cortado.

## Torneio

Os personagens criados nas roletas são inseridos no banco do neural_fights —
o torneio pega esses personagens de volta e os faz **lutar de verdade** no
motor do jogo, virando mais um vídeo no mesmo formato. Cada luta usa a mesma
gravação da luta única (DIRETOR, nativo, HUD do vídeo, callouts, corte de
tédio) e conta no ledger.

- `--fonte gerados` só usa quem nasceu das roletas; `banco` usa o roster
  inteiro; `misto` (padrão) prioriza os gerados e completa com o banco.
- O chaveamento é o `Tournament` oficial do neural_fights (com toda a
  validação dele). A seed prende o `random` global que ele usa, então o
  **mesmo seed reproduz o mesmo torneio**.
- Cada luta é lida como narrativa e vira um evento avaliado, igual a uma
  rolagem: `ZEBRA` (o favorito por força+mana perdeu), `virada no fio de
  vida`, `atropelou sem tomar dano`, `speedrun`, `maratona`, `DUPLO KO`,
  `luta de viradas` (duas ou mais trocas de liderança lidas da gravação).
  Os limiares ficam em `scoring.json → tournament_drama`, calibrados sobre a
  distribuição real do motor (HP restante mediano 34%, duração mediana 31s).
- O score vira tier → a edição reage com clipes do banco de reações e as
  legendas saem do banco shitposter (`frases.json → torneio` e `→ luta`).
- Telas próprias no renderer: participantes, título da rodada, card de luta
  (fichas lado a lado com contraste garantido), resultado (KO, duração, HP,
  marcas), campeão (com selo **CRIADO NA ROLETA**) e resumo do torneio.

Saída em `outputs/tournament_XXXXX/`: `tournament.json`, `edit_plan.json`,
`captions.json`, `gameplay/`, `final_celular.mp4`, `final_normal.mp4`.

## Biblioteca de vídeos de reação

Pasta `assets/reactions/` com arquivos nomeados pelo ID (`0001.mp4`,
`0002.mp4`, ...) e um índice `catalog.json`. Cada vídeo tem uma **categoria
por tier** — `terrible`, `bad`, `neutral`, `good`, `great`, `insane` — e
substitui a tela de reação sintética daquele tier no vídeo final (áudio do
clipe mantido).

- **Cabe inteira na tela** (`fit: contain`): a reação é vídeo de outro
  formato, quase sempre deitado. Recortar para preencher o 9:16 comia ~48 %
  da largura e cortava justamente o rosto — que é o que a reação tem para
  mostrar. Agora ela entra menor, com barras, sem recorte e sem distorção.
- **Toca até o fim, dentro do orçamento.** O teto por clipe é
  `durations.reaction_max` (8 s); o que protege o ritmo do vídeo é
  `reaction_budget.max_segundos` (14 s no vídeo inteiro): as primeiras tocam
  inteiras e, quando o orçamento acaba, a próxima simplesmente não entra —
  nenhuma vira flash (piso em `min_util_segundos`). O teto antigo de 2 s
  cortava 96 % da biblioteca (mediana de 6,5 s) e a piada morria antes do
  punchline.
- `import-reactions` atribui o próximo ID, copia o arquivo, mede a duração
  (ffprobe) e registra no índice.
- Seleção na edição: tier da rolagem → categoria, com fallback
  (ex.: BAD sem clipes usa terrible; GREAT sem clipes usa insane) e controle
  de uso para não repetir o mesmo clipe.
- Sem clipe compatível, o renderer desenha o cartão sintético — a biblioteca
  pode começar vazia.

Requisitos: Python 3.11+, Pillow, FFmpeg no PATH, repositório `neural_fights`
ao lado desta pasta (`e:\projetos`).

## Duas imagens e um vídeo (PicassoIA + Digen)

Cada geração enfileira **três** artefatos, um por slot — e só um deles é vídeo:

| job | provedor | arquivo | tela | o que é |
|---|---|---|---|---|
| `character` | PicassoIA | `character_image.png` | 2,6 s | só o personagem, corpo inteiro, sem arma |
| `weapon` | PicassoIA | `weapon_image.png` | 2,1 s | só a arma, sem mãos, com o efeito do elemento |
| `character_weapon_ref` | PicassoIA **Editor Pro** | `character_weapon_reference.png` | — | o personagem **segurando** a arma |
| `character_weapon` | Digen | `character_weapon_video.mp4` | 3-6 s | o payoff, animando a imagem acima |

O terceiro **não é cena**: é insumo. Ele existe porque o composer do Digen
aceita **um** arquivo, e a segunda imagem entregue **substitui** a primeira
(verificado na tela). Então quem junta personagem e arma é o Editor Pro do
PicassoIA, que aceita várias entradas — e o Digen recebe uma imagem que já é o
payoff, bastando animá-la.

```
character ──┐
            ├──→ character_weapon_ref ──→ character_weapon
weapon   ───┘        (Editor Pro)              (Digen)
```

A corrente se resolve sozinha numa rodada: as duas imagens e a junção saem na
mesma passada do PicassoIA (assim que elas ficam prontas o portão libera a
junção), e a passada do Digen já encontra a referência no disco.

**Por que as revelações viraram imagem.** Pedir três vídeos é caro, lento e — o pior —
inconsistente: em `generation_00020` o mesmo personagem saiu de cabelo branco
no clipe dele e de cabelo preto no payoff, com os mesmos campos de identidade
nos dois prompts. Gerar o personagem **uma vez**, como imagem, e mandar essa
imagem como referência para o vídeo ataca a inconsistência na raiz. E a
geração de imagem no PicassoIA é ilimitada e gratuita, então o custo por build
cai de três vídeos para um.

As imagens têm uso **duplo**: são a referência visual do vídeo final e são o
conteúdo das duas revelações do vídeo da roleta — animadas com câmera
(push-in no personagem, pull-back na arma), nunca paradas. Imagem estática num
vertical é morte por retenção.

A chave da fila é `generation_id#slot`: os três são jobs independentes, e o
payoff pode falhar sem levar junto o clipe de personagem que já deu certo.

**Os clipes de vídeo nascem no MESMO space** (`espaco_por_geracao`, ligado por padrão): o
primeiro slot cria o space, os outros dois entram nele. Menos navegação, menos
space solto na conta, e o space vira o dossiê daquela build — personagem, arma
e os dois juntos lado a lado.

Isso quebra a premissa que sustentava a espera ("space novo tem UM vídeo, então
o único botão de download é o nosso"). No lugar dela entra identificação por
diferença: antes de enviar, fotografam-se as miniaturas dos cards que já estão
lá; o card que aparecer fora da foto é o nosso. Se as miniaturas do space não
forem distinguíveis (ausentes ou repetidas), aquele clipe ganha um space
próprio — perder a companhia dos outros dois é melhor do que arriscar baixar o
vídeo errado. E `enviado` no job distingue "o space existe porque outro slot o
criou" de "eu já mandei meu prompt": sem isso o slot da arma abriria o space do
personagem e esperaria para sempre por um vídeo que ninguém pediu.

**Consistência entre eles** é o ponto delicado. Antes de enfileirar, a geração
grava `identity/character_identity.json` e `identity/weapon_identity.json` com
todo campo visual permanente (classe, porte, físico, personalidade, cor
assinatura em nome e hex; estilo, raridade, elemento, aura). Os três prompts
são montados desses mesmos campos — o terceiro repete as **duas identidades por
inteiro**, nunca um resumo, porque é o resumo que faz o modelo entregar outro
rosto e outra lâmina. O prompt do personagem diz explicitamente *no weapon*, e
o da arma diz *no character*: o payoff é a primeira vez que os dois aparecem
juntos.

Os prompts ficam em `config/identity.json`, editáveis sem tocar em código:
`prompts_imagem` (personagem e arma), `prompts.character_weapon` (o payoff sem
referência) e `prompts_payoff` (as variantes com uma ou duas referências).

**O prompt do payoff é decidido no envio, não no enfileiramento.** Só ali se
sabe quantas imagens existem e se o anexo funcionou. A regra que não se quebra:
*o texto carrega em palavras o lado que a imagem não carregou em pixels* — com
as duas referências ele encurta e fala de ação e câmera; com uma só, o lado sem
imagem continua descrito por inteiro; sem nenhuma, sai o texto completo de
sempre, que é exatamente o vídeo que já saía antes desta mudança.

## Contas compartilhadas: prova de origem

As contas do PicassoIA e do Digen são usadas por **outras pessoas** ao mesmo
tempo. Isso muda a pergunta que o worker faz na hora de baixar: "apareceu um
resultado novo depois do meu clique" **não** quer dizer "é meu". Foi assim que
a `generation_00044` gravou, como referência (`character_weapon_reference.png`),
a foto de outra pessoa — ela entrou no histórico da conta 0,1 s depois do
envio ao Editor Pro, era retrato, e passou por toda guarda de tela. O payoff
foi ao Digen com essa imagem anexada.

Desde então **nada entra na build sem prova de origem** (`proveniencia.exigir`
em `config/identity.json`, ligado por padrão):

| Provedor | Prova | Força |
|---|---|---|
| PicassoIA (criador e Editor Pro) | A aba **Histórico** (`?tab=history`) lista cada geração da conta com o **prompt inteiro**, a data e a imagem. O worker procura o card que traz o prompt que ele mesmo enviou, com data igual ou posterior ao envio, e baixa a imagem **desse card**. Se a imagem que apareceu primeiro na tela era outra, ela é descartada; se o card existe mas ainda está sem imagem, a espera continua — é a nossa geração que não terminou. | forte |
| Digen | O card não mostra o prompt (só título do espaço e presets). Vale o card novo no **espaço que o worker criou**, com os presets que ele aplicou (`RM3.5 / 3s / 480P`). Presets diferentes = card de outra pessoa, recusado. Card ilegível não recusa (seria queimar crédito por deploy do site), mas fica registrado como prova *fraca*. | média |

Sem prova, **nenhum byte é baixado nem gravado**; o histórico registra
`origem_recusada`, a tentativa conta como falha e a próxima gera de novo. A
prova aceita vai para `identity/<slot>.json` (`origem`: método, força, URL,
hash do prompt, data do card) e a URL fica reivindicada em
`outputs/_identity/origens.jsonl` — a mesma imagem nunca é aceita por duas
builds. `proveniencia.exigir: false` é rollback: registra a prova, não barra.

O que já estava no disco foi aceito pela regra antiga. Para isso existe a
auditoria, também no painel (`Auditar origem`):

```bash
python main.py identity auditar                       # todas as builds, slot a slot
python main.py identity auditar generation_00044
python main.py identity auditar --quarentenar-suspeitos
python main.py identity quarentenar generation_00044 character_weapon_ref --motivo "foto alheia"
python main.py identity aprovar generation_00022 character_weapon_ref --motivo "conferida: e a build"
```

`ok` tem prova; `?` é anterior ao portão (nada acusa, nada prova — confira a
imagem antes de publicar); `!!` é **suspeito**: o site "ficou pronto" rápido
demais para ter gerado (0,1 s no Editor Pro não é geração, é algo que já
estava chegando). `quarentenar` nunca apaga: move o arquivo e a cópia de
upload para `identity/quarentena/` com o motivo, tira a `origem` do metadado,
reenfileira o slot (o próximo `identity worker` gera de novo, com prova) e
refaz o vídeo se o slot aparece na timeline. Quarentenar a referência avisa
que o payoff foi gerado com ela — refazê-lo gasta crédito do Digen, então é
decisão sua. `aprovar` é o par: você abriu a imagem, é sua, e o veredito
vai para o metadado (origem `manual`) — senão o slot acusaria para sempre.
`identity status` resume a origem de tudo e lista os suspeitos nas
inconsistências.

## O modelo importa mais que o anexo

Anexar a imagem ao composer do Digen **funciona** — a miniatura aparece, o
formulário aceita. Mas o `Real Motion` é o text-to-video da casa e **ignora a
referência**: com ele o anexo dá certo mecanicamente e o vídeo sai com outro
personagem. Medido em `generation_00021`: a referência era um guerreiro
barbudo de túnica azul e brilho ciano, e o payoff entregou um elfo de cabelo
branco com armadura vermelha.

Por isso o modelo troca junto com o texto — os dois dependem do mesmo fato:

```
sem referência anexada  →  Real Motion 3.5  +  texto com as duas identidades
com referência anexada  →  Kling 3.0        +  "siga a imagem anexada"
```

`referencias.modelo` em `config/identity.json` escolhe qual image-to-video usar
(o menu do Digen oferece Kling, Runway, Veo, Seedance e Sora). Um teste garante
que ele nunca seja igual ao modelo de texto — se fosse, a troca não estaria
fazendo nada.

**O composer do Digen aceita UMA referência** (`multiple: false`, confirmado
pelo próprio diálogo) e a segunda entrega substitui a primeira — o que fazia o
vídeo sair condicionado só na arma. É exatamente por isso que a junção acontece
antes, no PicassoIA: a imagem que sobe já contém os dois.

### Nada aqui confia em "não deu erro"

Toda a automação segue a mesma doutrina, e cada item dela veio de um bug real:

| ação | prova exigida |
|---|---|
| anexar imagem | miniatura nova no composer |
| trocar modelo | reler o botão e comparar |
| trocar duração/proporção | reler o controle e comparar |
| imagem pronta | URL nova **e** retrato **e** dimensão já conhecida |
| rodada sem produzir | dizer por quê (fila vazia? tentativas? dependência?) |

`set_input_files` num `input` escondido não levanta exceção e não anexa nada —
foi assim que uma rodada inteira reportou "1 referência anexada" com o composer
vazio. O caminho que funciona é o diálogo nativo que o item "Upload Image" abre.

## Como o worker roda

```
pré-passe (sem browser)   fecha pelo disco o que já está pronto
passada PicassoIA         perfil próprio, gera as duas imagens
passada Digen             perfil próprio, anexa as imagens, gera o payoff
```

As passadas são **sequenciais e irmãs, nunca aninhadas**:
`contexto_persistente` abre o próprio `sync_playwright` por dentro, e dois no
mesmo thread levantam *"Playwright Sync API inside the asyncio loop"*. Cada
provedor tem seu **perfil de Chrome separado** — não por causa de cookie, mas
porque o Chrome trava o `user_data_dir` e `_liberar_perfil` mata processos
filtrando por essa string: com perfil único, abrir o PicassoIA mataria o Chrome
que está esperando um vídeo no Digen.

Ser sequencial dá de graça a ordem do grafo: quando a passada do Digen começa,
as duas imagens já estão no disco e o payoff passa no portão da fila. Falha de
um provedor **não** leva o outro junto.

**O portão da fila.** O job do payoff declara `depends_on` das duas imagens e um
prazo absoluto. Ele sai da fila quando cada dependência está *satisfeita* — e
satisfeita tem cinco caminhos, cada um fechando um buraco real: artefato no
**disco** (porque `queue --limpar` apaga as linhas `done` e uma limpeza de
rotina não pode travar o payoff para sempre), linha ausente (`identity run` de
um slot solto), linha `done`, linha `failed` (não se espera defunto — e falha
**não** se propaga para o dependente, senão morreria o único vídeo que restou)
e, por fim, o prazo vencido.

**Instalação (uma vez):**

```bash
pip install -r requirements.txt
patchright install chrome
python main.py identity login        # janela do Chrome abre; faca o login
```

Credencial (opcional — com o login feito à mão o perfil já basta): um
`digen_credentials.json` na raiz de `random_builds/`, no formato
`{"email": "...", "password": "..."}`. Ele e o perfil do browser
(`.browser_profile/`) estão no `.gitignore`.

**Uso:**

```bash
python main.py identity worker           # baixa os clipes da fila e refaz os videos
python main.py identity worker --watch   # fica em pe drenando a fila
python main.py identity queue            # estado da fila
python main.py identity run generation_00011   # os tres clipes dessa geracao
python main.py identity run generation_00011 --slot weapon   # so um slot
python main.py identity probe            # despeja seletores (quando o Digen muda)
```

### Monitoramento

As falhas aqui são silenciosas: o Digen faz um deploy, um seletor para de casar
e nada avisa — a fila só para de andar. Três comandos cobrem isso.

```bash
python main.py identity doctor            # rapido, sem browser
python main.py identity doctor --online   # abre o Digen e confere de verdade
python main.py identity status            # fila + clipes + videos finais
python main.py identity history -n 40     # o que aconteceu, com tempos
```

**`doctor`** responde "está tudo certo?". Sem `--online` confere o local
(patchright, Chrome, ffmpeg, perfil, config, fila, Chrome órfão). Com
`--online` abre o navegador e confere o que só o site pode responder: a sessão
ainda vale, quantos créditos existem e — o mais importante — **se cada lista de
seletores ainda casa com a página real**. É o que pega um deploy do Digen antes
de a fila travar.

Sai com código **0 (ok) / 1 (aviso) / 2 (erro)**, então serve direto em
agendador ou CI.

**`status`** mostra onde cada geração está no caminho `clipe → plano → mp4
final`, e lista as **inconsistências que ninguém reporta sozinho**:

- clipe baixado mas **fora do `edit_plan`** — o re-render não aconteceu (worker
  morto entre o download e o render);
- **mp4 final mais velho que o clipe** — o mais traiçoeiro: o vídeo existe e
  parece pronto, mas é o antigo, sem o personagem;
- clipe truncado (bytes de menos);
- job parado há horas.

### Por que o Chrome não fica piscando

O worker resolve **sem abrir navegador** tudo que já está pronto no disco: se o
clipe existe e já está no vídeo final, ele só fecha o job. O browser só sobe
quando há geração de verdade a fazer.

Isso importa porque três coisas juntas produziam um ciclo de abrir e fechar
janela a cada poucos segundos:

- o guard de "já pronto" rodava **depois** de abrir o Chrome;
- a checagem de vida do navegador tratava **qualquer** exceção como morte — e
  `Execution context was destroyed` é transitório e normal numa SPA, acontece a
  cada re-render do Digen;
- o `--watch` repetia a rodada no mesmo intervalo, para sempre.

Agora: o pré-passe evita o browser, a checagem de vida só considera morte o que
realmente é (`target ... closed`, `connection closed`), e o `--watch` **recua**
progressivamente quando uma rodada abre o navegador e não conclui nada — até
`watch_backoff_max` (10 min). Fila vazia **não** aciona recuo, senão um job novo
demoraria minutos para ser notado.

**`history`** é um JSONL append-only (`outputs/_identity/history.jsonl`) com um
evento por transição. A fila diz o estado *agora*; o histórico responde "isso
piorou?" — a espera mediana do Digen subiu? a taxa de sucesso caiu depois do
último deploy deles?

Duas decisões que valem saber:

- A espera é medida por **pareamento** (abertura → `pronto`), não por contagem.
  Uma tentativa que estourou não entra na mediana — ela é "quanto demora quando
  dá certo", e contar as que falharam mascararia a lentidão real.
- Nenhum check fica amarelo em estado normal. Credencial ausente **com o perfil
  logado** é OK, não aviso; e "final mais velho que o clipe" tem tolerância de
  5 s, porque granularidade de filesystem não é problema. Um alerta sempre aceso
  só ensina a ignorar alertas.

No painel: botões **Diagnóstico** e **Status** na aba "Vídeos de Build", ou as
opções 7–9 e `h` no menu de identidade do `painel.py`.

**Como se encaixa no pipeline.** `generate-video` grava as duas identidades,
monta os três prompts, enfileira em `outputs/_identity/queue.json` e termina —
o vídeo sai na hora, com nameplates no lugar dos clipes. O worker baixa cada
mp4 para `outputs/<generation_id>/<slot>_video.mp4` e, **quando o último slot
daquela geração fecha**, chama `--rerender --refazer-edicao`, que remonta a
timeline a partir do `generation.json` (determinística: mesma seed, mesmo
plano) e agora encontra os arquivos. Re-renderizar a cada clipe custaria três
renders completos para chegar no mesmo resultado do último.

O renderer não precisou mudar para aceitar os clipes: ele decide por
**capacidade**, não por tipo — qualquer evento com `asset.synthetic == false`
apontando para um mp4 que existe vira segmento de vídeo real.

Os clipes são gerados em 9:16 e entram com `fit: "contain"`: encaixe exato no
perfil `celular`, pillarbox sobre o fundo no `normal`. O nameplate é composto
por cima como PNG com alpha (e não por `drawtext`, que no Windows exige escapar
o caminho da fonte e não compõe emoji).

**Geração antiga continua valendo.** O clipe único do formato anterior
(`identity/digen.mp4`) é lido como o clipe de personagem, e um job de fila sem
`slot` migra para `#character` na leitura — nenhum vídeo que já estava montado
perde o que tinha.

### Modelo, duração, proporção e resolução

Configurado em `config/identity.json`:

```json
"modelo":    "Real Motion 3.5",
"aspect":    "9:16",
"resolucao": "max",
"duracao_por_slot": {
  "character":        ["5s", "8s", "3s", "max"],
  "weapon":           ["3s", "5s", "max"],
  "character_weapon": ["5s", "8s", "3s", "max"]
}
```

O padrão é **a máxima qualidade, sempre em pé, e o tempo que a montagem vai
usar**. Duração deixou de ser `"max"` global: a edição corta o clipe do
personagem em 5 s, o da arma em 4 s e o payoff em 6 s (`config/editing.json` →
`identity_slots`), então pedir 15 s para os três faria o Digen gerar material
que a montagem joga fora — e demorar mais para entregar. `duracao_por_slot`
manda; `duracao` fica como queda para um slot sem entrada, e o `identity
doctor` avisa quando o que se pede não cabe na janela.

**Todo preset é conferido, não só setado.** Cada `_ajustar_*` lê o botão depois
de clicar e, se o valor não virou, reabre o menu e tenta de novo; na segunda
falha o job cai dizendo o motivo. Antes só o modelo era conferido — um clique
que o popover engolisse entregava um clipe de 3 s onde se pediu 8, com a
geração já gasta e nada no log dizendo isso. Imediatamente antes do clique de
enviar, os quatro controles são lidos de uma vez
(`[digen] presets: modelo=... duracao=... resolucao=... aspecto=...`), uma
proporção comprovadamente deitada aborta a geração, e o que foi lido fica
gravado em `identity/<slot>.json`.

`"max"` não é um valor fixo: a automação abre o menu daquele modelo, lê as
opções e escolhe a **maior numericamente**. Por isso um modelo novo que passe a
oferecer 12s ou 1080P é aproveitado sem ninguém precisar catalogar nada aqui —
e a comparação é numérica de propósito, porque em ordem alfabética `"1080P"` é
*menor* que `"480P"`. Ele vale em **qualquer posição** da lista de desejo: como
último item, quer dizer "e se nada disso existir, pega o maior que houver".

Proporção **não** aceita `"max"`: proporção não tem "maior", e o maior número
do menu seria 21:9 — deitado. Ela usa uma lista de fallback em que **todas as
opções são verticais** (`9:16 → 2:3 → 3:4`), então nem um modelo sem 9:16
consegue deitar o vídeo.

Hoje, com o RM3.5, isso resolve para **8s / 480P / 9:16**.

O rótulo "480P" engana: medindo os arquivos que saem, o RM3.5 entrega
**480x864**, enquanto o RM3.2 com "720P" entregava **448x832**. Ou seja, a
troca ganhou pixels, ganhou duração (8s contra 5s) e ganhou áudio nativo (AAC
estéreo nos dois modelos, mas o 3.5 tem trilha de verdade). Os rótulos de
resolução do Digen não correspondem à altura real do vídeo — confira sempre com
`ffprobe`, não pelo texto do botão.

Três detalhes que não são óbvios e já causaram erro:

**O nome do modelo é casado por texto EXATO.** No menu do Digen, *"Real Motion
3.5 Turbo"* aparece **antes** de *"Real Motion 3.5"*. Qualquer busca por
substring seleciona o Turbo. Por isso a seleção usa `:text-is()`, e há um teste
que trava a ordem da lista para lembrar por quê.

**A busca é escopada ao popover.** A página de Spaces tem uma galeria "Need
some inspiration?" com um card intitulado *"Real Motion 3.5"*. Sem escopo, o
seletor casa com o card atrás do menu e o clique não troca modelo nenhum — foi
o que impediu a primeira tentativa de funcionar.

**Trocar o modelo RESETA os outros controles.** Medido: `RM3.2 → RM3.5`
derrubou a duração de 5s para 3s, a proporção de 9:16 para Auto e a resolução
de 720P para 480P. Por isso o modelo é sempre o **primeiro** ajuste, e os
demais vêm depois — um teste verifica essa ordem no código.

Duração e resolução são **listas de preferência**, não valores fixos, porque
cada modelo oferece um conjunto diferente: o RM3.5 só tem 480P, enquanto o
RM3.2 chegava a 720P. A automação pega a primeira opção da lista que existir no
modelo escolhido e diz no log o que conseguiu.

Depois de trocar, a automação **confere** o que o botão passou a mostrar. Se
não bater com o pedido, o job falha em vez de gerar: modelo errado gasta uma
geração e entrega outra coisa.

### O fluxo no site (verificado em 22/08/2026)

1. `/en/space` — o composer mora na **própria página de Spaces**; não há rota
   separada de criação.
2. **New Space** reseta o composer para um espaço limpo. Ele *não* navega. É o
   que torna a espera confiável: espaço novo tem zero vídeos, então o primeiro
   que aparecer é o nosso.
3. O prompt vai num `contenteditable[role=textbox]`, colado de uma vez
   (`aria-placeholder="Describe your video..."`). **Não é `<textarea>`** —
   `get_by_placeholder` não casa.
4. `button.submit-btn` envia. Ele fica `disabled` com o campo vazio; esperar
   habilitar é a confirmação de que o texto entrou.
5. Só depois do clique o app navega para `/en/space/<id>`.
6. Estados: `Waiting in generation queue...` → `You are in the priority
   generation queue` → `Generating video... Estimated completion: N seconds` →
   pronto.

### Quanto tempo isso leva (medido)

A fila do Digen é a parte lenta: nas rodadas de validação o vídeo ficou pronto
em **~700 s** (quase 12 min), alternando entre `priority generation queue` e
`Generating video`. Por isso `render_timeout` é **1800 s** — com os 600 s
iniciais o job falhava e **regerava**, jogando fora o vídeo que estava a
caminho.

Estouro de espera **não é falha**. O job guarda o `space_url` assim que o
prompt é enviado; se a espera acabar, a próxima passada do worker **volta
àquele espaço** em vez de pedir outro vídeo, e não consome tentativa (senão um
render lento queimaria as três e o job morreria esperando algo que ia chegar).
Falha de verdade — sem crédito, modelo recusou — descarta o espaço, porque aí
retomar esperaria para sempre.

**Armadilhas que já custaram uma rodada** (todas travadas em
`tests/test_identity_regressions.py`):

- Os `<video>` são **lazy e nascem sem `src`**. Usar `video[src]` como sinal de
  "pronto" faz todo job morrer por timeout.
- O botão de download do card **não tem texto, `aria-label` nem `title`** — o
  rótulo vive num tooltip. A única âncora é o `d` do path do ícone.
- `role=button|Download` casa com **"Download Digen App"** do topo, que existe
  sempre — inclusive durante a geração. Isso dava "pronto" aos 24 s.
- O contador de créditos carrega em **duas etapas**: até ~15 s mostra o
  placeholder `Free, Meme 0` (saldo 0) e só depois o valor real.
- Vários controles são renderizados **duas vezes** (variante mobile escondida +
  desktop visível), com a escondida primeiro no DOM. Por isso `encontrar()`
  varre até achar uma visível em vez de olhar só `.first`.

**Automação furtiva.** O acesso é por `patchright` (Playwright patchado, sem o
vazamento de `Runtime.enable` no CDP) com Chrome real, perfil persistente e
janela visível. O perfil é o que faz o login acontecer uma vez só. Captcha e
2FA **não** são resolvidos programaticamente: a janela fica aberta esperando
você resolver, e o cookie fica salvo. Prompt longo é **colado**, não digitado
tecla a tecla — 650 chars a ~90 ms seriam quase um minuto de paciência
sobre-humana. Um job por vez, com intervalo entre eles.

Se o worker morrer no meio, o Chrome fica vivo segurando o perfil e o próximo
launch falharia com `Target page, context or browser has been closed`. O
`browser.py` detecta isso, encerra **apenas** os processos daquele
`--user-data-dir` (nunca o Chrome pessoal) e tenta de novo uma vez.

Se um deploy do Digen quebrar a automação, o conserto é `identity probe` +
ajustar `src/identity/selectors.py`. Nenhum outro arquivo muda.

## Roletas (tudo derivado do NF)

**Personagem:** CLASSE (16) → PERSONALIDADE (26) → TAMANHO (1,40–2,20m) →
FORÇA (3,0–9,0) → MANA (3,0–9,0)

**Arma:** TIPO (8) → ESTILO (variantes oficiais do tipo) → RARIDADE (pirâmide
Comum→Mítico) → ENCANTAMENTO (12) → HABILIDADE (skills ofensivas do elemento
do encantamento, como no gerador oficial) → DANO (curva oficial da raridade)
→ PESO (range oficial do estilo) → CRÍTICO → VELOCIDADE DE ATAQUE

As dependências (estilo⊂tipo, dano⊂raridade, peso⊂estilo, skill⊂elemento)
são regras geradas em `src/nf_bridge/roulette_factory.py` a partir de
`ESTILOS_ARMA` e `dano_base` do gerador oficial.

## Pipelines (nunca misturadas)

1. **Dados:** seed → roletas NF → registros canônicos (fábricas oficiais) →
   SynergyEngine (peso×força, classe×tipo preferido, elemento da classe ×
   encantamento, mana×custo da skill, alcance×tamanho) → BuildEvaluator →
   `generation.json`
2. **Edição:** `generation.json` → classificação editorial de cada rolagem
   (`reaction_classifier`) → EditingDirector (onde entra reação, com teto e
   distância mínima) → legendas/narração → `edit_plan.json` + `timeline.json`
   + `evaluation.json` + `subtitles.srt` → VideoRenderer (roda giratória,
   clipes, nameplates, reações; PIL → FFmpeg) → `final.mp4`
3. **Inserção:** `exporter.insert_into_database` → `salvar_database`
   (substituir=False) → `insercao.json` registra nomes e caminhos.

## Estrutura

```
config/            # tiers, probabilidades, edicao, legendas, render, sinergias
  frases.json      # banco shitposter: nucleos POR ROLETA x qualidade + prefixos/sufixos
                   #   por tier -> 500+ legendas possiveis por combinacao (roleta x tier)
src/
  nf_bridge/       # loader (catalogos NF), roulette_factory, exporter
  generation/      # random/probability/rule/validation/entity/session
  evaluation/      # roll/synergy/surprise/interest/build
  editing/ content/ assets/ visualization/ video/ pipeline/
  identity/        # Digen: browser furtivo, sessao, prompt, fila, worker
assets/            # reactions/{terrible,bad,neutral,good,great,insane,
                   #             funny,contradictory,rare}, music, sfx...
outputs/generation_XXXXX/
  generation.json character.json weapon.json rolls.json build.json
  edit_plan.json     # o plano que o renderer executa (com tempo, evento a evento)
  timeline.json      # a mesma montagem em forma legivel: roleta/resultado/reacao/video
  evaluation.json    # a classe editorial de cada rolagem e a reacao que ela ganhou
  subtitles.srt      # legendas no tempo do video
  captions.json narration.json insercao.json
  character_video.mp4 weapon_video.mp4 character_weapon_video.mp4
  final_celular.mp4 final_normal.mp4
  identity/          # character_identity.json, weapon_identity.json,
                     #   <slot>.json e <slot>.prompt.txt
outputs/_identity/queue.json      # fila de clipes pendentes
outputs/_identity/history.jsonl   # historico append-only (monitoramento)
outputs/_identity/probe_*.json    # dumps de seletor do `identity probe`
```

**Dependências:** `pip install -r requirements.txt` (Pillow + patchright) e
FFmpeg/FFprobe no PATH. `patchright` só é necessário para `identity`.

## Notas

- Rodas com mais de 24 opções (ex.: 26 personalidades) mostram uma amostragem
  uniforme que SEMPRE inclui o vencedor (`WHEEL_MAX_SEGMENTS`).
- Sem clipes reais em `assets/reactions/`, o renderer desenha cartões
  sintéticos; .mp4 colocados lá são normalizados e inseridos via FFmpeg.
- `--rerender` nunca re-rola nem re-insere; usa os JSONs existentes.
- `narration.json` sai com timestamps, pronto para plugar TTS.
- Sem o clipe do Digen a timeline sai **idêntica** à de antes: a identidade
  visual nunca muda um vídeo que já estava certo (travado em
  `tests/test_identity_regressions.py`).
- Testes: `python -m unittest discover -s tests -p "test_*.py"` daqui de dentro.
