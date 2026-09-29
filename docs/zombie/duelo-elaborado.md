# Duelo elaborado: proposta de design

Escrito em 28/09/2026, à noite, pela sessão do jogo zombie (tarefa 13f6a1e6 do orquestrador). É uma **proposta**: ainda não há código. As escolhas de produto viraram nós no Grimório (§10), e nada daqui muda o cenário antes das respostas do Adrian.

**A decisão que pede isto** (`jogo-zombie/duelo-e-isso`, 28/09 18:40, "Quase: ajustar"):

> "Eu gostei da ideia de duelo, mas se vamos fazer algo assim tem que ser algo mais elaborado, quais planos os humanos vão usar para derrotar os zombies, quais habilidades eles tem, tem animaçoes para mostrar isso, como os humanos se comunicam, o que a nacionalidade deles traz de diferente, todos esses aspectos mecânicos, gráficos e criativos influenciam"

**O duelo de hoje** (`E:\jogo_ZOMBIE`, branch `feat/m15-polish`, HEAD `24b68cd`): seis guardas com lança numa praça em ruínas contra quatro zumbis rápidos, até o veredito, com velocidade por clipe. Cenário `duelo` em `src/sim/round/scenarios.ts:472-492`; critérios em `DUEL_CRITERIA` (`scenarios.ts:310-319`); juiz em `src/record/duel.ts`. O lote 2 passou em 6 de 12. Detalhes em `docs/sessoes/jogo-zombie.md` §3b.

---

## 0. Resumo

1. **Muito do que ele pede já existe dentro da simulação, mas nada aparece no vídeo.** O jogo tem:
   - conselho com 16 estratégias;
   - esquadrões com formação, moral e debandada;
   - emboscada com isca e fogo segurado;
   - armadilhas;
   - gritos que carregam o que o aldeão viu;
   - sino;
   - seis doutrinas de país.

   O gravador desliga todas as camadas de depuração (`src/record/main.ts:26`) e não há texto no mundo: nenhum `Text` em `src/render`.
2. **Medido hoje, 40 duelos sem vídeo** (sementes 401–440, §2):
   - o conselho forma a linha de lanças em 31 de 40 rodadas, e ela é largada depois de uma mediana de 4,5 s de jogo;
   - os guardas passam 41% do tempo fugindo;
   - nos trechos sem contato, que o juiz reprova como "trégua", o zumbi mais próximo fica a uma mediana de 3,6 tiles de um guarda. A trégua é uma **perseguição**, e não uma pausa.
3. **A proposta**:
   - cada duelo mostra **um plano** dos humanos: parede de lanças, isca e emboscada, linha de armadilhas, barricada ou, em último caso, círculo;
   - o plano é executado por um **esquadrão com papéis**;
   - ele é anunciado por **placa e balão** no primeiro segundo e meio;
   - o plano **funciona ou quebra na tela**, com animação própria;
   - o **país** decide qual plano, uma habilidade de assinatura, o adereço, a cor e o idioma dos gritos.
4. **Custo**: o pacote mínimo que responde ao comentário (§9) leva de **13 a 19 dias de sessão**. Arte nova de personagem soma de 5 a 15 dias. O maior risco está no equilíbrio: cada plano muda quem vence e tem de passar de novo nos critérios, em 100 sementes.
5. **Isso compete com o objetivo das semanas**, que é estabilizar o que existe (`decisoes/geral/objetivo-das-semanas`). Quando fazer é decisão dele.

---

## 1. O que já existe e o que falta (arquivo:linha no `E:\jogo_ZOMBIE`)

### IA: GOAP, conselho e esquadrões

| O quê | Onde | Estado |
|---|---|---|
| 24 ações GOAP do aldeão (lutar, fugir, segurar abertura, avisar o líder, tocar o sino, cumprir tarefa…) | `src/ai/human/goap/humanDomain.ts:74-98`, `:112-180` | existe |
| Luta com lança "de fora da mordida": avança até o alcance e recua quando o zumbi fecha | `src/ai/human/executors.ts:970-1019` (`canKite`) | existe |
| Arqueiro mantém 3 tiles de distância | `executors.ts:63`, `:987-993` | existe |
| O guarda larga a luta com HP < 35% e medo > 0,85 | `executors.ts:65-66`, `:980` | existe |
| Conselho: 16 estratégias com pontuação e motivos | `src/ai/village/strategies.ts:73-297`; a escolha em `src/ai/village/Council.ts:111-127` | existe |
| Ordem de deus que força uma estratégia por 120 s | `Council.ts:37`, `:139`; comando `ForceStrategy` em `src/sim/core/commands.ts:37` | existe; o êxodo usa |
| Planos HTN por estratégia, entre eles **emboscada com isca** (`baitTheZone`) e **linha de armadilhas** | `src/ai/village/htn/villageDomain.ts:540-575`; milícia em `:483-495` | existe |
| Esquadrões com tipo (milícia, patrulha, escolta, emboscada, vigia), ordem, moral e debandada | `src/ai/village/squads.ts:13-84`, `:153-210` | existe |
| Formações em linha, cunha, círculo e coluna | `src/ai/village/formations.ts:2-47` | existe |
| Emboscada: zona de 6 tiles, dispara com 3 zumbis dentro, arqueiros seguram o fogo até lá | `squads.ts:79-84`, `:189-207`; `src/sim/agents/humanCombat.ts:147` | existe |
| Aprendizado entre rodadas: táticas do zumbi, entre elas FLANKING e FAST_ZOMBIES | `src/ai/learning/tactics.ts:6-23` | existe; num duelo de uma rodada, não pesa |
| **A linha que segura.** A milícia é largada em ~4,5 s, e fugir (`seekSafety`) domina o tempo | §2 | **falta** |
| **Planos no chão aberto.** `fortify` e `shelterInPlace` miram prédios, e a arena não tem nenhum. Mesmo assim o conselho escolhe `shelterInPlace` em 40 de 40 rodadas: ordem de se abrigar sem abrigo | `strategies.ts:176-203`, §2 | **falta** |

### Facções e países ("arena por país")

| O quê | Onde | Estado |
|---|---|---|
| Seis doutrinas: BR, PT, AR, US, JP e DE. Cada uma mexe em quanto da vila é guarda, na arma do civil, na média dos traços, nos passos, no modo de comunicação, no viés de cada estratégia e no ritmo do conselho | `src/sim/round/countries.ts:14-60`; o tipo está em `src/sim/agents/doctrine.ts:130-144` | existe |
| Aparência por país: nome, doutrina numa frase e em 2–3 palavras, cor e 30 nomes próprios | `src/record/countries.ts:78-119` | existe |
| `--pais` no gravador, com cor do país e mordida escondida | `src/record/main.ts:124-128` | existe; com `duelo`, **troca** a doutrina do duelo pela do país |
| **O país dentro do duelo.** O duelo usa uma cópia da metade "de luta" do BR (`scenarios.ts:338-342`). Numa ruína sem casas, metade das alavancas da doutrina não faz nada: quanto é guarda e a arma do civil (ninguém recebe ofício de uma casa, `scenarios.ts:335-337`), e também abrigar, fortificar e evacuar | — | **falta**: o país muda os traços, a comunicação e a cor, e quase nada que se veja |

### Habilidades

| O quê | Onde | Estado |
|---|---|---|
| Seis papéis: lavrador, lenhador, mineiro, ferreiro, carpinteiro e guarda. Cada um tem o que coleta, o que fabrica, a arma inicial e um bônus de bravura | `src/sim/agents/roles.ts:156`, `:175-183` | existe |
| Três armas. Porrete: 25 de dano, alcance 1,0. Lança: 40, alcance 1,6, e golpeia por cima de barricada. Arco: 35, alcance 10, gasta flecha | `src/sim/economy/goods.ts:56-60`; `src/sim/agents/strikeLine.ts:5-18` | existe |
| Armadilha: 60 de dano, prende 3 s e se gasta com o uso | `src/sim/agents/traps.ts:1-35` | existe |
| Isca: chocalha uma vez por segundo, o zumbi ouve a ~24 tiles, e ela se gasta | `src/sim/agents/bait.ts:1-19` | existe |
| Paliçada, a estrutura de barricada | `src/sim/world/structures.ts:5` (`Palisade`); o pincel de deus em `src/sim/sandbox/godTools.ts:19` | existe; nenhuma tarefa a põe em chão aberto |
| **Habilidade ativa por papel** (escudo que empurra, grito de reunião, tocha, isca humana…) | — | **falta** |

### Comunicação entre humanos

| O quê | Onde | Estado |
|---|---|---|
| Grito de aviso quando vê um zumbi. O grito carrega o que foi visto (onde, quantos, com que confiança) e chega a ~14 tiles | `src/ai/comms/speech.ts:11-14`, `:64-77` | existe |
| Fofoca que distorce: boato que cresce, falso avistamento de quem está com medo | `speech.ts:80-98`, `:126-143`; `src/ai/comms/claims.ts:9-12` | existe |
| O aldeão vai contar ao líder | `speech.ts:100-123` | existe |
| Sino com código (abrigar, tudo limpo) | `claims.ts:30`; ação `ringBell` em `executors.ts:1307` | existe |
| Registro do conselho ("Adotou: Formar milícia…") e textos em pt-BR para cada estratégia e fala | `src/ai/village/councilState.ts:93`; `src/i18n/pt-BR.ts:212`, `:284-285`, `:401`, `:459-460` | existe; só aparece no painel da interface |
| Medido no duelo (§2): ~20 gritos, ~2 falas e ~4 badaladas de sino por rodada | — | acontece |
| **Nada disso aparece no vídeo.** No JSON sai só o *som* (`berro`, `sino`, em `src/record/sounds.ts:7-17`), e o mp4 sai mudo (`anullsrc`, `scripts/record.mjs:265`) | — | **falta** |

### Animações e VFX (PixiJS)

| O quê | Onde | Estado |
|---|---|---|
| Quatro silhuetas pré-desenhadas: aldeão, armado (com lança), zumbi e cadáver. Tintura por país, balanço do passo e ginga do zumbi | `src/render/layers/AgentLayer.ts:173`, `:243-271`, `:296-322` | existe |
| Efeitos: sangue na mordida, poça na morte, gosma no abate, anel verde ao virar, lascas ao arrombar, pulso da onda, anel do último sobrevivente | `src/render/layers/FxLayer.ts:75-113` | existe |
| Camada do conselho (linhas do esquadrão até a âncora e pontos de tarefa), só para depuração | `src/render/overlays/CouncilOverlay.ts:17-34`; desligada no gravador (`main.ts:26`) | existe; invisível |
| **Golpe.** Não há estocada nem balanço: o golpe só vira evento quando mata. Hoje o golpe é só um som (`humanCombat.ts:169`) | — | **falta** |
| **Arqueiro com cara de arqueiro.** Quem segura arco é desenhado **com lança** (`AgentLayer.ts:246`: qualquer arma usa o desenho do guarda). Flecha não tem traço | — | **falta** |
| Estalo e zumbi preso na armadilha, isca chacoalhando, texto ou ícone no mundo | — | **falta** |

### O gravador

| O quê | Onde | Estado |
|---|---|---|
| Um quadro por chamada, determinístico | `src/record/main.ts:211-238` | existe |
| Câmera de diretor puxada pelos eventos (peso por tipo) | `src/record/director.ts:40-47` | existe; tipo novo de evento precisa de peso |
| Velocidade por clipe (regra do duelo) | `main.ts:105-110`; `src/record/duel.ts` | existe |
| Contrato em JSON: `eventos_narrativos` com mordida, abate, sequência, último sobrevivente e veredito, com x e y | `src/record/report.ts:103-150` | existe; **sem** plano, ordem ou fala |
| Faixa de legenda da fábrica: ~520 px do topo em 1920 | `main.ts:33-35` | restrição: placa queimada no topo briga com ela |

---

## 2. O que o duelo faz hoje por dentro (medido em 28/09, à noite)

**Como foi medido.** Rodadas do `duelo` sem vídeo, no Node, sementes **401–440** (40 sementes, faixa nunca usada), no HEAD `24b68cd`, com a mesma montagem da `preview.ts`. Custo: 13 s. As sondas e as saídas estão em `E:\jogo_ZOMBIE\out\design\` (`sonda-duelo.test.ts`, `sonda-tregua.test.ts`, `sonda-401-440.json`, `tregua-401-440.json`), fora do git. É uma prévia no Node: conta bem em muitas sementes, mas não prova uma gravação específica (§4 da sessão).

**Resultado**: vila 21, horda 19.

- **O conselho decide, e a decisão não aparece.** Estratégias adotadas em ao menos um momento da rodada:

  | estratégia | rodadas (de 40) | observação |
  |---|---|---|
  | `shelterInPlace` | 40 | sem abrigo nenhum na arena |
  | `ration` | 40 | irrelevante num duelo |
  | `quarantine` | 35 | |
  | `formMilitia` | 31 | sempre em **linha** |
  | `patrol` | 16 | em coluna |
  | `buddySystem` | 16 | |

- **A linha não dura.** Nas 15 rodadas em que o registro do conselho guardou o fim da milícia, ela foi **largada** (`council.dropped`) depois de uma mediana de **4,5 s** de jogo (1 a 5 s). Nunca debandou por moral: `council.routed` = 0.
- **Onde vai o tempo dos guardas** (7192 guarda-segundos):

  | objetivo | fatia |
  |---|---|
  | fugir (`seekSafety`) | **41%** |
  | lutar (`defend`) | 25% |
  | vagar | 15% |
  | isolar-se (mordido) | 5% |
  | conselho | 5% |
  | avisar o líder | 4% |
  | sino | 3% |

- **A trégua é uma perseguição.** Hipótese H1, escrita antes de medir: "o trecho sem contato é guarda fugindo".
  - **Falsificador**: H1 cai se, nos segundos de trégua (corridas de pelo menos 3 s sem mordida nem abate, depois do primeiro contato), a fatia de fuga **não** for maior que nos segundos com contato, ou se ficar abaixo de 50%.
  - **O que deu**: fuga em **52,3%** dos guarda-segundos na trégua, contra 41,4% com contato.
  - A distância mediana do zumbi mais próximo a um humano é de **3,6 tiles** na trégua e de **0,9** com contato.
  - A trégua ocupa **1344** segundos de jogo, contra 514 com contato.
  - **H1 sobrevive, por pouco** (52% contra a barra de 50%). A leitura: o guarda corre a 2,8 e o zumbi do duelo corre a 2,6. Ninguém alcança ninguém, e o vídeo mostra gente correndo em círculo.
- A mesma coisa no quadro: `out/design/hoje-s16-3s5-guardas-espalhados.png` (semente 16, 3,5 s de vídeo). Os seis guardas que começaram em anel estão espalhados em três direções.

**Por que isso importa para a proposta.** Um plano que **segura**, a linha que não é largada, ataca ao mesmo tempo o pedido do Adrian (o plano na tela) e o critério que ainda reprova metade dos clipes (a trégua). Isso é a hipótese H2 do §8, com falsificador.

---

## 3. Os planos dos humanos

Cada vídeo mostra **um** plano. Um plano precisa de quatro coisas:

- (a) uma **peça visível** no chão ou na formação;
- (b) um **anúncio** no primeiro segundo e meio;
- (c) um **momento de verdade**, em que funciona ou quebra;
- (d) uma **resposta do zumbi** que o possa derrotar.

Sem a (d), o plano vira propaganda e o critério 4 (cada lado vence de 30% a 70%) cai.

| plano | peça visível | anúncio | momento de verdade | o zumbi responde | o que existe | o que falta | custo |
|---|---|---|---|---|---|---|---|
| **Parede de lanças** | 4–6 guardas em linha ou cunha, lanças para fora | placa "PAREDE DE LANÇAS" e o capitão: "FECHA A LINHA!" | o primeiro zumbi morre na ponta da lança; ou alguém é mordido e a linha abre | contornar pelo flanco (o corredor dá a volta) | milícia em linha (`villageDomain.ts:483-495`), luta de fora da mordida (`executors.ts:995-1013`), formações | a **disciplina de segurar**: não largar a estratégia em contato e não fugir enquanto a moral aguenta. O mesmo tipo de isenção que a coluna em marcha já tem (`squads.ts:172`). Falta também a linha voltar-se para a ameaça | 2–3 dias |
| **Isca e emboscada** | isca chocalhando (anel de som) e arqueiros agachados de um lado | "EMBOSCADA", depois "SEGURA…" e "AGORA!" | com 3 zumbis na zona, os arqueiros disparam juntos | o corredor vê o arqueiro e ignora a isca (visão de 30 tiles no duelo) | `baitTheZone` (`villageDomain.ts:541-548`), zona e disparo (`squads.ts:79-84`, `:189-207`), fogo segurado (`humanCombat.ts:147`), isca (`bait.ts`) | no duelo não há kit de isca, arco nem `approach` (a direção conhecida da horda). Falta a flecha na tela e a visão do zumbi que torne a espera possível (hoje ele vê tudo, 360°) | 2–3 dias |
| **Linha de armadilhas** | armadilhas no caminho do leste | "ARMADILHAS" e "ATRÁS DA LINHA!" | a armadilha estala e o zumbi fica preso 3 s enquanto a lança chega | desviar ou pisar e sobreviver (60 de dano contra 120 de HP) | armadilha (`traps.ts`), `trapLine` (`villageDomain.ts:556-575`), desenho da armadilha (`StructureLayer.ts:69`) | kits no estoque do duelo, efeito do estalo, marca de "preso" | 1–2 dias |
| **Barricada** | fileira de paliçada, ou carroça, entre a praça e o leste | "BARRICADA" e "SEGURA A CERCA!" | a lança fura por cima da cerca (alcance de 1,6 contra o mínimo de 1,5); ou a cerca cai | quebrar a cerca (15 de dano por golpe em estrutura) ou dar a volta | paliçada (`structures.ts:5`), lança por cima (`strikeLine.ts:5`), efeito de arrombamento (`FxLayer.ts:97-101`) | tarefa de levantar paliçada em chão aberto; ou o cenário já a põe (`PlaceStructure`) | 2–3 dias |
| **Círculo, costas com costas** (último recurso) | anel de guardas | o capitão: "CÍRCULO!" | o anel aguenta ou quebra | cercar | formação `circle` (`formations.ts:38-42`), anel de escolta (`squads.ts:76-78`) | o gatilho: formar o anel quando estiver em desvantagem, em vez de debandar | 1–2 dias |

**Um plano que já acontece sem querer: a isca humana.** A perseguição medida no §2 é, na prática, um guarda puxando zumbis. Se ele puxar **para a linha de lanças**, a trégua vira o plano: "o mais rápido puxa, os outros esperam". O comportamento de fuga existe. Falta a fuga ter um destino, que é a linha, e a linha segurar. É a candidata natural à assinatura da Argentina (§7).

---

## 4. Habilidades por papel (elenco do esquadrão)

Proposta de elenco misto de 6, no lugar de 6 lanceiros iguais:

| papel | arma e habilidade | na tela | o que existe | o que falta |
|---|---|---|---|---|
| **Capitão** (1) | lança; **dá a ordem** (anuncia o plano) e o **grito de reunião**: devolve moral e chama de volta quem fugiu | estrela na cabeça; os balões das ordens saem dele | líder da vila (`Village.ts:42-43`), moral do esquadrão (`squads.ts:63-78`) | ligar o líder ao esquadrão do duelo; o grito como ação |
| **Lanceiro** (2–3) | lança; **estocada** que empurra o zumbi meio tile | estocada animada | dano e alcance, luta de fora da mordida | o empurrão (movimento e colisão), a animação |
| **Arqueiro** (1) | arco com 20 flechas; **segura o fogo** | silhueta com arco, flecha em traço | arco, munição e fogo segurado | a silhueta própria (hoje sai com lança), o traço da flecha |
| **Armadilheiro** (1) | porrete; **põe armadilha ou isca** no preparo | armadilhas no chão desde o 1º quadro | armadilha, isca, tarefas `placeTrap`/`placeBait` (`tasks.ts:14`) | kit no estoque do duelo |
| **Batedor ou isca** (0–1) | mãos nuas e o mais rápido; **puxa** a horda | rastro de poeira | fuga (`executors.ts:873-949`) | o destino da fuga (a linha) |
| Civis (opcional, 2–3) | ninguém luta; **o que se protege** | escolta em círculo | esquadrão de escolta (`squads.ts:13`, `:76-78`) | o cenário com civis; o equilíbrio fica mais difícil |

Os civis dão ao vídeo o que perder e o que salvar ("salvaram as crianças?"). Custam equilíbrio: uma rodada de guardas mais civis tem dois fins possíveis, e o critério 4 precisa valer para os dois. É uma opção do nó `duelo-elenco`.

---

## 5. Animações e VFX

Tudo em código no PixiJS, no estilo de hoje. Arte nova é o nó `duelo-arte` (§10).

| momento | hoje | proposta | custo |
|---|---|---|---|
| golpe de lança | nada: só o som | estocada (o corpo avança 0,2 tile e volta) e faísca na ponta; exige um evento `golpe` no timeline | 1 dia |
| flecha | nada | traço de 0,15 s do arqueiro até o alvo, e poeira quando erra | 0,5 dia |
| armadilha | desenho parado | mandíbula que fecha, anel de estalo e o zumbi tremendo por 3 s | 0,5 dia |
| isca | desenho parado | anel de som a cada 1 s (o mesmo ritmo de `bait.ts`) | 0,25 dia |
| linha e formação | invisível | corda fina entre vizinhos da linha enquanto ela segura, que arrebenta quando quebra | 0,5 dia |
| ordem do capitão | invisível | pulso dourado no capitão e o balão | com §6 |
| debandada | invisível | ícone de medo em quem foge; a corda some | 0,25 dia |
| arqueiro, capitão e armadilheiro | silhueta de lança para todos | 3 silhuetas novas (arco, estrela ou capa, bolsa); o adereço do país vai por cima (§7) | 1 dia |

**Determinismo.** Efeito é apresentação: roda no tempo do quadro (`FxLayer.ts:31-33`) e não muda a simulação. Um evento novo no timeline é dado puro (`src/sim/world/timeline.ts:24-28`); o `src/sim` continua sem DOM e sem relógio. A câmera de diretor precisa de um peso para cada tipo novo (`director.ts:40`).

---

## 6. Comunicação na tela

Tudo sai do que a simulação já decide. Nada é roteirizado.

| gatilho no jogo | onde nasce | fala proposta (pt-BR) | quem fala |
|---|---|---|---|
| grito de aviso com N zumbis | `speech.ts:64-77` (claim `sighting`, `count`, x, y) | "VINDO! 4 PELO LESTE" | quem viu |
| o conselho adota o plano | `Council.ts:111-127` (`council.chose`) | "LINHA! LANÇAS À FRENTE!", "EMBOSCADA: SEGURA O FOGO", "ATRÁS DAS ARMADILHAS!" | capitão |
| a emboscada dispara | `squads.ts:201` (`sprung = true`) | "AGORA!" | capitão |
| mordido que confessa | claim `infected` (`claims.ts:9`) | "FUI MORDIDO!" (ou silêncio: o traço de honestidade decide) | o mordido |
| a linha é largada ou quebra | `council.dropped` / `council.routed` | "CORRE!" | quem sai |
| sino | `ringBell` | nenhuma fala: o anel do sino já diz | — |
| último de pé | já é evento (`lastSurvivor`) | "SÓ SOBROU EU." | o último |

**Ritmo**: no máximo 1 balão novo a cada 1,5 s de vídeo e no máximo 2 na tela ao mesmo tempo. O resto do que é dito fica no JSON para a fábrica. Frase de até 4 palavras, em caixa alta: é o tamanho que se lê num celular em 1,5 s.

**Como sai.** O caminho que conserva o determinismo tem quatro passos:

1. Eventos novos no timeline: `ordem` (estratégia e quem falou) e `fala` (tipo da claim e quem falou).
2. Um campo novo no JSON (`eventos_narrativos` com `tipo: "ordem" | "fala"`).
3. O texto, resolvido pelo i18n no render.
4. Uma camada de balões na página de gravação.

A **placa** do plano também pode ser desenhada pela fábrica, a partir do JSON. Com isso ela fica sem texto queimado, que a tradução das plataformas não enxerga (`src/record/countries.ts:66-71`). O custo passa para a Publicação, na ponte da Semana 3.

**Voz.** Hoje o mp4 é mudo, e o JSON leva só o tipo do som. Grito falado seria voz sintetizada na fábrica: o edge-tts dos builds tem vozes pt-BR, pt-PT, es-AR, en-US, ja-JP e de-DE. **Só o Adrian julga som.** O Gemini não recebe o áudio. É o nó `duelo-voz`.

---

## 7. Nacionalidade: o que cada país muda de verdade

O que já está escrito nas doutrinas (`countries.ts:14-60`) vira, no duelo, **qual plano, uma habilidade de assinatura, um adereço, a cor e o idioma**:

| país | doutrina de hoje | plano preferido no duelo | assinatura | visual (cor e adereço) | voz e fala |
|---|---|---|---|---|---|
| BR | "portas abertas": bravura e sociabilidade altas, corre a 2,8 | parede de lanças **avançando** | grito de reunião mais forte (quem fugiu volta) | 0xffb000 e faixa na testa | pt-BR: "BORA, FECHA!" |
| PT | "ninguém sai": conselho lento (×3), fortificar | barricada | a cerca demora a subir, mas aguenta mais | 0xff4d6d e boina | pt-PT: "AGUENTEM A CERCA!" |
| AR | "drama": boato exagerado, evacua | isca humana puxando para a linha | o batedor mais rápido | 0x7cc4f0 e lenço | es-AR: "¡VIENEN TODOS!" |
| US | "todos armados": arco, emboscada | isca e emboscada | 2 arqueiros no lugar de 1 | 0x5b7cfa e boné | en-US: "HOLD… NOW!" |
| JP | "em duplas": notícia exata, mordida declarada, passo furtivo | círculo em duplas | mordido sempre confessa (honestidade 1) e o par o isola | 0xf2f2f2 e faixa | ja-JP: frase curta |
| DE | "engenharia": armadilha e barricada, conselho rápido (×0,5) | linha de armadilhas | +2 armadilhas no preparo | 0xff9f1c e capacete | de-DE: "ACHTUNG, FALLEN!" |

Custos e riscos:

- **Cada país tem de passar sozinho no critério 4** (vencer de 30% a 70% em 100 sementes de prévia). São 6 países × 100 sementes × ~0,3 s, ~3 min por rodada de ajuste. O custo real é a iteração do equilíbrio: 6 a 9 dias com a mecânica. Só visual, nomes e voz: 1 a 2 dias.
- **Tom.** As doutrinas de hoje são estereótipos de cultura pop ("Drama: todo boato vira fim do mundo"). Num canal público isso pode divertir ou ofender. A proposta troca a piada pelo **plano**: o país é "o que eles fazem bem", e não "do que se ri deles". Quem decide é o Adrian.
- As cores foram escolhidas longe do verde do zumbi (ΔE ≥ 35, `src/record/countries.ts:73`). As cores de DE (0xff9f1c) e BR (0xffb000) são próximas entre si; num vídeo de um país só, isso não importa.

---

## 8. Como cabe num Short de 20–35 s

**Roteiro-alvo** (em segundos de vídeo, com a velocidade por clipe da regra de hoje):

| trecho | o que se vê | critério |
|---|---|---|
| 0,0–1,5 | as peças do plano já no chão (armadilhas, cerca, linha), a placa e o grito do capitão; os zumbis entram pela borda | primeiro contato até **15%** (≤ 4,5 s num clipe de 30 s) |
| 1,5–5 | o primeiro contato **na peça do plano**: estala, fura ou dispara | idem |
| 5–20 | o plano funcionando ou rachando: "FUI MORDIDO", "CORRE!", "CÍRCULO!" | nenhum buraco > **30%** do vídeo |
| até 31,5 | o veredito e 3,5 s de cauda | vídeo de **20 a 35 s**, desfecho por regra |

**O preparo acontece fora do vídeo**, porque o gravador pula a preparação (`main.ts:139`). Por isso o plano precisa estar **montado** quando o vídeo começa, e a placa explica o que já está ali. Mostrar o preparo acelerado (`--com-preparacao`) come o orçamento dos 15%. Dá para uns 1,5 s, e não mais.

**Critérios novos, escritos antes de medir.** Entram em `DUEL_CRITERIA` quando a implementação começar, junto ao cenário, como os de hoje:

6. o plano é **anunciado** (evento `ordem`) até **5%** do vídeo;
7. o plano tem um **momento de verdade** marcado (armadilha pegou, emboscada disparou, a linha segurou 3 s em contato, ou debandou) antes de **60%** do vídeo;
8. no máximo **1 fala nova a cada 1,5 s** de vídeo.

Os critérios 1 a 5 de hoje continuam valendo sem mudança.

**H2, com falsificador escrito agora.** "Uma linha que segura acaba com a trégua."

- Linha de base: antes de mexer, a prévia do duelo de hoje nas sementes **441–540** mede quantas reprovam no critério 1. Nas 160 de 28/09, foram 38–40%.
- Depois da disciplina de segurar, mede-se de novo nas mesmas sementes.
- **H2 cai se a reprovação no critério 1 não baixar para 25% ou menos**, ou se o critério 4 sair de 30–70%. Se cair, a trégua não é falta de plano, e o próximo alvo é a velocidade relativa entre o guarda e o zumbi (2,8 contra 2,6).

---

## 9. Custo por eixo

Em dias de sessão, com a medição incluída (prévia de 100 sementes por mudança, ~1 min cada). As faixas se sobrepõem em parte, porque o elenco e os planos dividem código.

| eixo | o que entra | dias | risco |
|---|---|---|---|
| **Planos** (mecânica) | a linha que segura, isca e emboscada, armadilhas e o círculo; barricada opcional (+2–3) | **5–8** | **médio-alto**: cada plano mexe em quem vence e na trégua; tudo passa de novo em 100 sementes e num lote pré-registrado |
| **Leitura do plano** | eventos `ordem`/`fala`, camada de balão e ícone no PixiJS, campos no JSON | **2–3** no jogo (+1–2 na Publicação se a placa for da fábrica) | baixo: é preciso medir o tamanho da letra no celular, como se mediu o aldeão (66 px) |
| **Habilidades** (elenco misto) | capitão, lanceiro com empurrão, arqueiro e armadilheiro | **3–5** (+2–3 com civis) | médio |
| **Animações e VFX** em código | estocada, flecha, armadilha, isca, corda da linha, 3 silhuetas | **3–5** | baixo |
| **Arte nova** de personagem | sprites CC0 5–8; arte por IA 8–12 (com prova de origem de cada imagem); o palco Godot da Onda 16 10–15 | **5–15** | alto |
| **Comunicação** em texto | falas por evento, ritmo e i18n por país | **2–3** | baixo-médio (tom) |
| **Voz** falada | gritos sintetizados na fábrica, no idioma do país | **2–3** (Publicação) | médio: só ele julga som |
| **Nacionalidade** | só visual, nomes e voz: **1–2**. Com mecânica (plano, assinatura e equilíbrio de 6 países): **6–9** | | médio-alto |

**Pacote mínimo que responde ao comentário**, somado sem sobreposição:

- 3 planos (lanças que seguram, isca e emboscada, armadilhas);
- placa e balão;
- elenco misto;
- VFX em código;
- falas em texto;
- país só no visual.

Dá **13–19 dias**. Com país mecânico, **+5–7**. Com arte nova, **+5–15**. Gravação: um lote pré-registrado de 12 clipes leva ~40 min de madrugada por versão.

---

## 10. Nós no Grimório (projeto `jogo-zombie`, todos dependentes de `duelo-e-isso=quase`)

| id | pergunta | opções |
|---|---|---|
| `duelo-plano-quem-escolhe` | quem escolhe o plano de cada duelo | o conselho (IA) · um plano por vídeo, fixo · o país |
| `duelo-leitura-do-plano` | como o espectador entende o plano (com a maquete) | placa · balão · ícone · placa + balão · só o movimento |
| `duelo-elenco` | quem está no esquadrão | seis lanceiros · elenco misto · misto + civis |
| `duelo-nacionalidade` | o que o país muda | estreia sem país · só visual e voz · mecânica, visual e voz |
| `duelo-voz` | os humanos falam em voz alta | sem voz (texto) · gritos sintetizados · só efeitos |
| `duelo-arte` | arte dos personagens | código melhorado · sprites CC0 · arte por IA · palco Godot |

**Mídia anexada** (em `E:\jogo_ZOMBIE\out\design\`, fora do git):

- `maquete-leitura-do-plano.png`: três formas de ler o plano, desenhadas **por cima de um quadro real** (semente 16, 0,3 s). É maquete, e não o jogo.
- `hoje-s16-3s5-guardas-espalhados.png`: o duelo de hoje, 3,5 s depois, com os guardas espalhados.

**Ordem sugerida, se ele topar construir**: plano e leitura primeiro (é o que ele pediu e o que ataca a trégua); elenco junto; país e voz depois; arte por último, porque é a mais cara e a única que não muda o que acontece.
