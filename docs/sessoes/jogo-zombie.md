# Jogo zombie

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/jogo-zombie/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (29/09/2026) · “29/09 21:39, pela Mesa de comando: paralelo, até 2 agentes” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Passou de 50%, para tudo; força total 20 min antes de renovar (29/09/2026) · “29/09 07:26, pela Mesa de comando: passou de 50% da sessão, para tudo” `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Só quando eu pedir (29/09/2026) · “29/09 13:28, pela Mesa de comando: força total só quando eu pedir” `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`
- ✅ **Limpeza do disco (C: com 9 GB livres)** — Só o seguro (~1,2 GB) (29/09/2026) `limpeza-do-disco`
- ✅ **E: com 17 GB livres — o cache do Google Drive (186 GB)** — Abrir o Google Drive e deixar ele terminar e limpar sozinho (recomendado primeiro) (29/09/2026) `limpeza-do-disco-e`
- ✅ **Grok: por onde entra na roda?** — grok.com com a sua conta X (gratuito; você loga uma vez) (29/09/2026) `ias-grok-acesso`
- ✅ **Quando você fala com uma IA e a pipeline precisa da mesma conta** — Você: a pipeline espera a sua conversa terminar (29/09/2026) `ias-prioridade-conversa`
- ✅ **Cada IA tem UM chat de longa duração ou um chat novo por assunto?** — Um chat 'casa' por IA, com resumo periódico (29/09/2026) `ias-chat-persistente`
- ✅ **Fichas das IAs (fase 1): li?** — Li; seguir para a fase 2 (falar com cada uma pelo app) (29/09/2026) `ias-fichas-lidas`
- ✅ **Rodízio de imagens: quem vem primeiro** — Gemini primeiro (29/09/2026) `rodizio-de-imagens-quem-vem-primeiro`
- ✅ **Digen no plano Free: o Real Motion 3.5 pede plano** — Tirar o Digen da roda e desligar o vídeo do payoff das builds (29/09/2026) `digen-plano-free`
- ⏳ **Fila: tarefas pesadas podem rodar de dia?** — Você apertou 'retomar a fila' 3 vezes, mas as 3 tarefas de builds que sobraram (re-render do som real dos duelos 17–23, 16G duelo pelo palco, 16F armas) são pesadas e a regra é rodá-las só de 01h a 06h. Rodo de dia? `fila-pesada-de-dia`

**Jogo zombie**
- ✅ **Formato do 1º vídeo** — Duelo (27/09/2026) `formato-do-primeiro-video`
- ✅ **Velocidade por clipe** — Sim (28/09/2026) `velocidade-por-clipe`
- ✅ **Duelo: é isso?** — Quase: ajustar (comente) (28/09/2026) · “Eu gostei da ideia de duelo, mas se vamos fazer algo assim tem que ser algo mais elaborado, quais planos os humanos vão usar para derrotar os zombies, quais habilidades eles tem, tem animaçoes para mostrar isso, como os humanos se comunicam, o que a nacionalidade deles traz de diferente, todos esses aspectos mecânicos, gráficos e criativos influenciam” `duelo-e-isso`
- ✅ **Duelo: quem escolhe o plano?** — O país escolhe (28/09/2026) `duelo-plano-quem-escolhe`
- ✅ **Duelo: como o espectador entende o plano?** — Ícone na cabeça (28/09/2026) `duelo-leitura-do-plano`
- ✅ **Duelo: quem está no esquadrão?** — Misto + civis para proteger (28/09/2026) `duelo-elenco`
- ✅ **Duelo: o que o país muda?** — Só cor, nomes, adereço e idioma (28/09/2026) `duelo-nacionalidade`
- ✅ **Duelo: os humanos falam em voz alta?** — Sem voz: só texto nos balões (28/09/2026) `duelo-voz`
- ✅ **Duelo: arte dos personagens** — Levar o duelo ao palco Godot (Onda 16) (28/09/2026) `duelo-arte`
- ✅ **Duelo elaborado: quando fazer** — Depois da estabilização (rotas de 3 semanas) (28/09/2026) `duelo-quando`

<!-- decisoes:fim -->

A parte que mora em **outro repositório**: `E:\jogo_ZOMBIE`. Aqui não se publica nada — o jogo só **gera o mp4 e um JSON**; conta, grade e postagem são da parte de Publicação, em `E:\projetos`.

Escrito em 27/09/2026 pela sessão dona. Tudo abaixo foi conferido lendo o repositório do jogo naquele dia; o que não deu para conferir está marcado **(não verificado)**.
Atualizado em 28/09/2026 (Semana 1 das rotas): commits `d9f6382`, `dab114c`, `a372bdc` e `24b68cd`, o êxodo remedido, e o cenário **`duelo`** — o formato que o Adrian
escolheu em 27/09 — com critérios escritos antes de medir, o lote 1 que reprovou (3/12), a velocidade por clipe que ele aprovou às ~03:20, o **lote 2 que passou na barra
(6/12)** e a divergência Chrome × Node (§3b, §4).

## 1. O que é, e como rodar

Sandbox de simulação de vila no navegador (TypeScript, PixiJS, Preact, Tweakpane, Vite) com **IA clássica** — sem LLM, sem serviço externo, offline e determinístico. Aldeões
percebem com limitação (visão, audição), lembram, planejam (utility + GOAP), trabalham, conversam (avisos, boatos que se distorcem, confiança, sino), e um conselho transforma o que
chegou ao líder em planos coletivos (HTN, leilão de tarefas, esquadrões). Zumbis têm tipos, módulos de IA e bandos. M0–M12 estão marcadas prontas no README; M13–M15 (corrida
armamentista, performance, polimento) seguem abertas.

`src/sim` e `src/ai` são **puros** (sem DOM, sem PixiJS, sem `Math.random`, sem relógio), com teste de arquitetura garantindo. Toda alteração externa passa por um `Command`:
partida = semente + comandos.

```
npm install
npm run dev        # Vite em http://localhost:5173
npm test           # Vitest: 75 arquivos, 348 testes no 24b68cd, verdes em 28/09 08:07. 66–77 s com a máquina livre, 104–174 s
                   # disputada. Com um jogo aberto levou 592 s e 3 testes estouraram o tempo: rodar de novo, não "consertar"
npm run typecheck  |  npm run bench  |  npm run experiment   (ver §4)
```

URL: `?seed=`, `?preset=nightSiege`, `?cinema=1`, `?overlay=paths,beliefs,council`, `?panel=village`.

**Gravar um clipe** (precisa de Chrome e ffmpeg):

```
npm run record -- --cenario exodo --seed 6 --velocidade 1 --saida out/exodo.mp4 --resultado out/exodo.json
npm run record -- --cenario duelo --seed 13 --velocidade auto --tiles 22 --escala 2 --max-duracao 45 --saida out/d13.mp4 --resultado out/d13.json
```

`--velocidade auto` só existe para o duelo: **a página de gravação** (no Chrome) joga a rodada uma vez sem desenhar antes do primeiro quadro e grava na velocidade da regra
do §3b (a mais lenta de 1× a 3× que põe o clipe em até 30 s). Tem de ser na página, e não no Node do `record.mjs`: os dois motores divergem (§4). O JSON traz a velocidade
escolhida em `velocidade`.

**Lote de duelos de madrugada, com um comando só** (vigia armado antes; não fica no git, porque `out/` é ignorado):

```
bash E:/jogo_ZOMBIE/out/ferramentas/lote-duelos.sh 25 36 duelo-lote3
```

Grava só entre :55 e :16, das 01:00 às 05:16; pula semente já gravada (retoma na madrugada seguinte); o vigia corta gravação viva em :25–:54 e para tudo com disco < 3 GB
ou entre 06:00 e 12:00; no fim roda o juiz. Nome da pasta só com ASCII. Parar: `powershell -NoProfile -ExecutionPolicy Bypass -File
E:/jogo_ZOMBIE/out/ferramentas/parar-tudo.ps1 -Dir E:/jogo_ZOMBIE/out/<pasta>`. A primeira versão (28/09 manhã) perdia a barra invertida do caminho do Windows, criava a
pasta `out$NOME` e o vigia nunca armava; a de hoje só usa barra normal e foi testada em seco às 17:31 (vigia armou, laço pulou a semente gravada, juiz rodou, vigia saiu).

Outras flags: `--resolucao 1080x1920` (padrão), `--fps`, `--max-duracao`, `--cauda`, `--com-preparacao`, `--escala` e `--tiles` (tamanho do aldeão e quanto chão cabe no quadro),
`--pular N` (joga N segundos de jogo fora antes do primeiro quadro guardado), `--camera fixa`, `--lobotomia`, `--pais BR|PT|AR|US|JP|DE`, `--prever --paises BR,US,JP --alvo 80`
(estima sem vídeo).

O gravador serve `record.html` pelo Vite, dirige um Chrome headless pelo DevTools Protocol **um quadro de vídeo por chamada** (o resultado não depende da velocidade da máquina),
manda os quadros ao ffmpeg com faixa de áudio silenciosa (`anullsrc`, porque a fábrica junta clipes com `concat -c copy`) e imprime **uma linha JSON no stdout**. Saída: o `.mp4` em
`--saida` e o mesmo JSON em `--resultado`. As gravações ficam em `out/`, **ignorado pelo git desde `d9f6382`** (27/09): antes dos duelos eram 38 arquivos, 206 MB; os
duelos da madrugada de 28/09 estão em `out/duelo/` (lote 1) e `out/duelo-ritmo/` (lote 2). Cenários: `nightSiege, rumorMill, keenEars, hiddenBite, fortressTown, lastStand,
arena, limpeza, exodo, duelo`.

Desde `dab114c` (28/09) o recuo da câmera de diretor não passa da largura do mapa: em mapa estreito o recuo de 48 tiles abria o clipe numa figura pequena entre duas faixas
pretas. Isso muda o enquadramento de `exodo` e `limpeza` (36 de largura) se forem regravados.

## 2. Estado da branch `feat/m15-polish`

HEAD = **`24b68cd`**, árvore limpa. Os commits de 27–28/09, todos com o "sim" do Adrian, por caminho explícito e sem push. A branch não foi mergeada na `main` e não tem
remoto.

- `d9f6382` (27/09 23:58) `chore: ignore recordings, and settle the exodus figures` — o `.gitignore` com `out/` e o comentário do êxodo com os três critérios. O número
  do comentário foi **corrigido antes do commit**: o rascunho dizia "7 vitórias em 10", e a remedição deu 6 (§3).
- `dab114c` (28/09 03:18) `fix(record): pull the director back no wider than the map` — `src/record/main.ts` (§1).
- `a372bdc` (28/09 03:18) `feat(sim): a duel scenario, and a judge for its recordings` — o cenário `duelo` e `DUEL_CRITERIA` (`scenarios.ts`), i18n, `src/record/duel.ts`
  (`judgeDuel`, `judgeDuelBatch`, com o caso zero) e testes, `tests/scenarios/duel.test.ts` (o duelo apaga toda parede antes de pôr os guardas; a ordem inversa apagaria os
  guardas), `scripts/duel-verdict.mjs` e o README. Suíte verde (75 arquivos, 344 testes) e `npm run build` verde antes dos dois.

- `24b68cd` (28/09 08:09) `feat(record): film each duel at the pace its own round calls for` — `DUEL_PACE`/`duelSpeed()` em `src/record/duel.ts` com 4 testes (limites,
  a mais lenta que cabe, monotonia, caso zero); `--velocidade auto` no `record.mjs` (só com `duelo`, recusa `--lobotomia`), com a velocidade escolhida **dentro da página**
  (`paceFor` em `src/record/main.ts`); `duel-verdict.mjs --prever` usa a regra e `--velocidade V` pergunta "e se fosse fixa"; `scenarios.ts` só ganhou comentário (lote 2 e
  Chrome × Node) e perdeu `DUEL_SPEED` — a luta não mudou. Suíte (348) e build verdes antes.

**Atenção à diferença entre o código do lote 2 e o `24b68cd`**: o lote 2 (03:55–04:59) foi gravado com uma versão anterior da regra, que escolhia a velocidade **no Node**
(guardada em `out/duelo-ritmo/codigo.patch`). Só a semente 15 saiu diferente por isso (§3b).

Os commits do dia 27/09:

- `8d39b27 fix(ai)` — a horda que parava de caçar (§4).
- `4e26d16 experiment` — novos braços do arnês: `EXPERIMENT_QUIET`, `EXPERIMENT_SPAWN=fora`, e mortes e tiles por aldeão-segundo por rodada.
- `795eff4 feat(sim)` — a segunda forma de vitória (regra de fuga) e os cenários `exodo` e `limpeza`. Toca `src/sim/Sim.ts`, `round/round.ts`, `round/scenarios.ts`,
  `core/commands.ts`, `src/record/*`, i18n e `tests/scenarios/exodus.test.ts`.
- `89e6c80 fix(ai)` — conserta a saturação do `seekSafety` (`src/ai/human/goals.ts`) e faz um esquadrão sob ordem de marcha amortecer a fuga, ficar isento da debandada por moral e
  marchar em passo de caminhada (`ai/village/squads.ts`, `executors.ts`, `decide.ts`).

**Regra do dono: commit só quando ele pedir.** E por caminho explícito, nunca `git add -A`.

## 3. O cenário "Êxodo" (`exodo`)

A vila vence **fugindo**, não matando. Todo cenário anterior só era ganho limpando a horda, e uma vila de doze mata ~5 zumbis numa rodada inteira: em 32 rodadas medidas isso não
aconteceu **uma vez**. Daí a segunda vitória.

- **A regra** (`sim/round/round.ts`, `sim/Sim.ts`): a rodada pode carregar uma `EscapeRule` `{x, y, need}`; quem chega a `ESCAPE_REACH = 2,5` tiles do ponto é **removido do
  mundo**. Tirar do mapa é a regra, não atalho: quem "escapou" e ficasse parado na borda seguia sendo isca, puxava a horda para quem vinha atrás e ainda virava zumbi — foi por isso
  que as primeiras medições do êxodo saíram como derrota. A fuga é checada **antes** da aniquilação, de propósito: a rodada que termina com o último aldeão saindo do mapa é
  vitória, e perguntar "sobrou alguém?" primeiro chamaria esse mesmo instante de derrota. `tests/scenarios/exodus.test.ts` cobre exatamente isso — nada mais na suíte chama o
  `escape` de um cenário.
- **Configuração**: mapa 36 × 150 (o **comprimento da estrada** é o que dita a duração da rodada), vila no meio, horda do sul (20 andarilhos em t=0, **4 corredores em t=10 s** — a
  dificuldade inteira), saída ao norte 4 tiles dentro da borda, 10 s de preparação, hora 9. Cota = `max(2, ceil(0,6 × aldeões gerados))` — fração, não número fixo, porque as vilas
  nascem entre 5 e 17 pessoas. A ordem de evacuar vem no `setup()` (`ForceStrategy evacuate`), porque o conselho só pontua `evacuate` com `nearThreat >= 8`, quando a horda já está
  dentro da vila.
- **Remedido em 28/09 no build que está no HEAD** (sementes 1–10, `npm run record -- --prever`, sem vídeo): **6 vitórias, 4 derrotas, 0 no relógio**; **8 de 10** terminam
  entre 45 e 75 s; primeiro contato antes da metade da rodada em **2**, depois em 3, e **nunca** nas outras 5 (a coluna sai limpa, sem um arranhão). Os dois números velhos
  ("8 em 10" nos comentários, "7 em 10" na mensagem do `795eff4`) não reproduzem; 6 é também o único que fecha com "o conserto do `89e6c80` passou duas sementes de vitória
  para derrota". O comentário commitado em `d9f6382` já diz 6. Critérios do êxodo: passa o 1 (60%) e o 2 (8/10), reprova o 3 (2/10).
- **O clipe `exodo-66` é de um build anterior** e não se reproduz mais: a mesma semente 6 hoje vence aos 50,8 s de jogo (o clipe diz 64,25). Os números do clipe abaixo
  descrevem aquela gravação, não o jogo de hoje.
- **O clipe gravado em 17/09**: `out/exodo-66.mp4` (16,4 MB) + `.json`. Seed 6, 1080x1920, velocidade 1, câmera DIRETOR, sem HUD, vencedor `vila`, motivo `vila_escapou`, 64,25 s de jogo e
  **64,33 s de vídeo**, 15 aldeões no início e 5 no fim, 0 mordidos, 25 zumbis vivos; diâmetro do aldeão (p50) 66,35 px.
- **A fraqueza medida**: `eventos_dano` tem **um único** evento — `[56.55, "vila", 1, "mordida"]`. A primeira mordida vem aos 56,55 s de 64,33 s: **88% do vídeo sem um contato**.
  Um minuto de gente andando e um susto no fim.
- A mesma rodada foi gravada em três tamanhos de aldeão: `out/exodo.json` (p50 54,06 px), `exodo-66` (66,35) e `exodo-83` (83,55). `exodo-83b.mp4` é **byte a byte idêntico** ao
  `exodo-83.mp4` (regravação, que de graça serve de prova de determinismo); `exodo-66-400.mp4` é a redução para olhar em tamanho de celular.

## 3b. O cenário "Duelo" (`duelo`) — o primeiro formato do canal (decisão do Adrian, 27/09)

**O que é.** Uma luta só, do primeiro golpe ao veredito, no tamanho de um Short: **seis guardas com lança numa praça em ruínas contra quatro zumbis rápidos** vindos do leste.
Acaba por regra: `vila_resistiu` (zumbis e mordidos zerados) ou `vila_caiu` (nenhum aldeão). Gravação: `--cenario duelo --velocidade auto --tiles 22 --escala 2
--max-duracao 45` (aldeão com ~82 px). **Velocidade por clipe** (Adrian, 28/09 ~03:20): a mais lenta de 1× a 3×, em passos de 0,25, que põe a rodada em até 30 s de vídeo
com a cauda (`duelSpeed`, `src/record/duel.ts`). É uma regra fixa, calculada antes de gravar: ninguém escolhe a velocidade de uma semente. O lote 1 foi a 2× fixo.

**O que ele NÃO é** — e a definição é minha, para o Adrian confirmar: os `out/duelo*.mp4` antigos eram (a) o "duelo alternado" BR × AR de 17/09, que no mesmo seed é o
**mesmo mapa** e lia como "uma vila piscando de cor", descartado na mesma noite pelo "sem cortes" dele; e (b) recortes de 5–12 s da `arena`, que acabam **todos** em
`tempo_limite` — reprovam o desfecho por construção. Gravar mais desses não mediria nada.

**Critérios, escritos antes de medir** (texto no comentário do cenário, números em `DUEL_CRITERIA`, aplicados por `src/record/duel.ts`):

1. **Contato cedo e mantido**: primeira mordida, morte ou abate até **15%** do vídeo; e do primeiro contato ao veredito nenhum trecho sem contato maior que **30%** do vídeo.
   Porta quebrada não conta.
2. **Desfecho claro**: a rodada termina por regra dentro do clipe; `tempo_limite` reprova.
3. **Duração de Short**: **20 a 35 s** de vídeo, cauda incluída.
4. (do cenário) cada lado vence entre **30% e 70%** das sementes; 5. pelo menos **metade** das sementes passa 1–3. Requisito da gravação: aldeão p50 ≥ 66 px.

Justificativas, resumidas: os três clipes cegos de 16/09 foram largados no segundo 2–3 e não tinham contato nenhum nos primeiros 10 s (daí 15%); o êxodo tem um buraco de 30 s
em 64 (daí 30%); o duelo do Neural Fights mira 20–35 s, suas lutas medem 16–19 s e **retém mediana de 51,5%** contra 25,4% do build e 10,7% da estreia (só 5 duelos medidos);
35 s foi a duração que o Adrian escolheu para este canal em 16/09.

**Como a cena foi achada** — calibrada nas sementes **101–110**, sem vídeo, para as sementes gravadas (1 em diante) nunca terem sido olhadas na escolha:

- **Duelo dentro de vila não acaba.** 9 braços de lugarejo de 5 casas: **0 vitórias da vila, 8 derrotas e 82 relógios em 90 rodadas**. Não falta luta (contato em < 10 s);
  os sobreviventes entram nas casas e a horda os perde.
- **Tirar as casas não basta**: o gerador sempre ergue prefeitura, armazém, forja, oficina, capela e celeiro. 50 de 60 rodadas no relógio. Na rodada rastreada segundo a
  segundo, cinco aldeões ficaram dentro desses prédios de 40 s até o teto, com o zumbi mais perto a 10–14 tiles.
- **Por isso a arena é ruína**: toda parede, porta e janela do mapa apagada antes de pôr os guardas (o pincel de deus deixa sino, estoques e bancadas). Ficou assim no
  quadro: chão de terra onde eram os prédios, com um caixote e um estoque soltos — conferido num quadro do teste, não parece defeito, mas quem julga é o Adrian.
- **A horda vê a arena toda e corre no passo de um aldeão** (visão 30, 360°, lembra 30 s; velocidade 2,6 contra 1,7 do andarilho). Só com a visão, as vitórias da horda
  levavam mediana de 83–128 s (dez braços), porque os últimos aldeões fugiam mais rápido; com o passo, 45–57 s (quatro braços), e 1 rodada em 60 bateu o teto. **Isso muda o
  caráter do zumbi** (andarilho que corre) — decisão de produto a confirmar.
- **O braço escolhido** (6 guardas × 4, incubação 4–8 s): 4 vitórias da vila e 6 derrotas nas 10 de calibração, todas por regra, em 25–70 s de jogo; os critérios passam
  **5 de 10** a velocidade 2 (conferido depois com o mesmo juiz). Número de calibração, não resultado — e otimista, como se viu abaixo.

**Lote de 28/09 — o resultado: o duelo REPROVA nos próprios critérios.** Sementes **1 a 12**, fixadas antes de gravar, gravadas em sequência (01:00–02:13, com o vigia
armado desde 00:14 e pausa automática de 01:20 a 01:55 pela janela das postagens), todas julgadas por `node scripts/duel-verdict.mjs out/duelo` (saída em
`out/duelo/veredito.json`):

| semente | vencedor | 1º contato (s) | maior buraco (s) | vídeo (s) | cedo | desfecho | curto | passa |
|---|---|---|---|---|---|---|---|---|
| 1 | horda | 0,53 | 5,40 | 22,57 | sim | sim | sim | **sim** |
| 2 | vila | 0,08 | 4,42 | 16,53 | sim | sim | não | não |
| 3 | horda | 1,30 | 4,34 | 22,93 | sim | sim | sim | **sim** |
| 4 | horda | 1,38 | 10,70 | 41,40 | sim | sim | não | não |
| 5 | horda | 0,18 | 4,60 | 19,43 | sim | sim | não | não |
| 6 | vila | 1,63 | 4,05 | 14,13 | sim | sim | não | não |
| 7 | horda | 0,33 | 5,95 | 20,10 | sim | sim | sim | **sim** |
| 8 | horda | 0,65 | 7,72 | 24,43 | não | sim | sim | não |
| 9 | vila | 1,50 | 1,55 | 9,47 | não | sim | não | não |
| 10 | horda | 0,53 | 8,62 | 24,83 | não | sim | sim | não |
| 11 | horda | 2,28 | 10,10 | 45,00 | sim | sim | não | não |
| 12 | horda | 0,00 | 8,73 | 27,03 | não | sim | sim | não |

- **Passam 3 de 12** (sementes 1, 3 e 7 — as três vitórias da horda). A barra do cenário é metade: reprova.
- **Vila 3, horda 9 (25%)**: fora da faixa 30–70%. Na calibração (101–110) tinha dado 4 × 6.
- **O que funcionou**: desfecho por regra em **12 de 12**; primeiro contato em até 2,3 s de vídeo em **12 de 12**; aldeão a **82 px** em todas.
- **O que reprova não é a luta, é o tamanho**: a duração depende de quem vence. A vila vence rápido (12–26 s de jogo = 9,5–16,5 s de vídeo a 2×, com a cauda): **as três vitórias da vila
  saíram curtas demais**. A horda leva 32–85 s para virar seis guardas: das nove, uma curta e duas longas. Uma velocidade só para todas as sementes não cabe as duas.
- **E há trégua**: cinco vitórias da horda têm 7,7–10,7 s de vídeo sem contato nenhum; em três delas isso passa de 30% do clipe.
- A gravação reproduziu a prévia sem vídeo **nas 12**: mesmo vencedor e mesmo instante do veredito (±0,01 s de jogo). Consequência útil: os critérios podem ser
  **estimados sem gravar** (a prévia leva ~0,3 s por semente). Mas não é garantia semente a semente: no lote 2, uma em 12 divergiu (§4).
- Custo real: 12 clipes, 288 s de vídeo, **38 min de gravação** (2269 s), 4,7 a 13,1 s de relógio por segundo de vídeo; as cinco primeiras (01:00–01:20) rodaram ~1,5× mais
  devagar por segundo de vídeo que as sete últimas, com a máquina disputada. 36 MB em `out/duelo/`.
- Isto está escrito também no comentário do cenário (`THE RECORDED BATCH FAILS`), como o êxodo registra a própria reprovação.

**O que a prévia sem vídeo diz, em sementes que nunca foram gravadas** (28/09, 02:55–03:10). Repete-se com `node scripts/duel-verdict.mjs --prever --de 301 --ate 400`
(com a regra; `--velocidade 2` para a linha do 2× fixo; a linha das 7 guardas precisou de um script de rascunho, porque muda o cenário). Primeiro a conferência: aplicado às
sementes 1–12, o cálculo sem vídeo repete o veredito gravado **semente por semente** (3/12, as mesmas bandeiras). Depois:

| receita | sementes 201–260 | sementes 301–400 |
|---|---|---|
| a de hoje, 2× fixo | passam **19/60 (32%)**, vila 27/60 (45%) | passam **33/100 (33%)**, vila 63/100 (63%) |
| a de hoje, velocidade por regra (a mais lenta de 1× a 3× que põe o clipe em ≤ 30 s) | passam **34/60 (57%)** | passam **55/100 (55%)** |
| 7 guardas e aldeão correndo a 2,6, com a mesma regra | 44/60 (73%) | 62/100 (62%) |

- **O lote não foi azarado no que reprova**: 32–33% passam em 160 sementes novas; 3/12 é isso. **Foi azarado no equilíbrio**: a vila vence 53% somando as 182 sementes
  medidas; os 25% do lote são uma cauda (com p = 0,5, um lote de 12 cai fora de 30–70% em ~15% das vezes — o critério 4 é ruidoso nesse tamanho).
- **A regra de velocidade conserta o tamanho** (curto demais/longo demais cai de 47–50% para 7% das sementes) e leva a 55–57%, **em cima da barra** de metade. O que sobra é a
  trégua: 38–40% das sementes ainda reprovam no critério 1.
- **A terceira linha é um exemplo de por que se confirma em sementes novas**: escolhida como a melhor de 12 combinações em 201–260 (73%), deu 62% em 301–400. O ganho sobre a
  receita de hoje é pequeno e não justifica mexer no cenário agora.
- **Lição de método: 10 sementes de calibração enganaram.** Nas 101–110 a receita passava 5/10 (medido com o mesmo juiz) e aprovava; o real, em 160 sementes, é um terço. A
  prévia custa ~0,3 s por semente: **calibre em 100, não em 10**, e grave só o lote pré-registrado.
- A regra muda o ritmo de clipe para clipe (vitória da vila a 1×, derrota longa a 3×) — era escolha de apresentação do Adrian, e ele **aprovou às ~03:20 de 28/09**.

**Lote 2 — pré-registrado às 03:28 de 28/09, antes de gravar** (este parágrafo foi commitado antes da primeira gravação do lote, que começa às 03:55):

- **O que se grava**: sementes **13 a 24**, reservadas desde o lote 1 e nunca olhadas (nem em prévia); todas, em sequência, sem escolher. Cenário **sem mudança** (o de
  `a372bdc`), `--velocidade auto` (a regra), `--resolucao 1080x1920 --tiles 22 --escala 2 --max-duracao 45`, em `out/duelo-ritmo/`. Código: `a372bdc` + a regra não commitada
  (`out/duelo-ritmo/codigo.patch`). Juiz: `node scripts/duel-verdict.mjs out/duelo-ritmo`.
- **Esperado**: cerca de **55%** passando (6–7 de 12), pela prévia em 160 sementes novas.
- **Falsificador, combinado com o Adrian**: **menos de 6 de 12 passando** ⇒ o tamanho não era o único problema, e o próximo alvo é o **trecho sem contato** (critério 1).
- O critério 4 (cada lado vence 30–70%) é reportado junto, mas num lote de 12 ele falha por acaso em ~15% das vezes: se for só ele a reprovar, isso é dito como tal.
- **Quando**: janelas de gravação da madrugada de 28/09 (03:55–04:16 e 04:55–05:16), com o vigia armado antes; o que não couber fica para a madrugada seguinte, com o
  **mesmo código**, retomando da primeira semente que falta (o laço pula as já gravadas).

**Lote 2 — o resultado: passa na barra, 6 de 12.** Gravado inteiro na mesma madrugada, 03:55–04:59, sem falha e sem corte do vigia; cada clipe levou 108–235 s de relógio.

| semente | vencedor | velocidade | 1º contato (s) | maior buraco (s) | vídeo (s) | cedo | desfecho | curto | passa |
|---|---|---|---|---|---|---|---|---|---|
| 13 | horda | 3 | 0,93 | 7,27 | 30,93 | sim | sim | sim | **sim** |
| 14 | horda | 1,5 | 0,60 | 5,90 | 29,70 | sim | sim | sim | **sim** |
| 15 | vila | 1,5* | 1,93 | 8,33 | 24,87 | não | sim | sim | não |
| 16 | vila | 1,5 | 2,37 | 7,57 | 27,23 | sim | sim | sim | **sim** |
| 17 | horda | 1,75 | 0,14 | 6,00 | 28,40 | sim | sim | sim | **sim** |
| 18 | vila | 2,5 | 0,84 | 4,92 | 29,67 | sim | sim | sim | **sim** |
| 19 | — | 3 | 3,92 | — | 45,00 | não | não | não | não |
| 20 | horda | 2,25 | 0,44 | 8,36 | 27,30 | não | sim | sim | não |
| 21 | vila | 1 | 0,00 | 9,85 | 25,83 | não | sim | sim | não |
| 22 | horda | 1,75 | 0,00 | 9,78 | 27,33 | não | sim | sim | não |
| 23 | vila | 1 | 0,25 | 9,65 | 29,83 | não | sim | sim | não |
| 24 | horda | 2,75 | 0,87 | 5,28 | 28,53 | sim | sim | sim | **sim** |

- **Passam 6 de 12** (13, 14, 16, 17, 18, 24): é a barra, então o falsificador ("menos de 6") **não** disparou. Esperado era ~55% (6–7).
- **Equilíbrio**: vila 5, horda 6, uma sem desfecho — dentro de 30–70%. O critério 4 passa; o juiz dá `aprovado: true`.
- **O tamanho deixou de reprovar** em todo clipe que tem desfecho (24,9–30,9 s). A semente 19 é uma rodada que **nunca acaba** (600 s de jogo sem veredito na prévia): a 3× o
  clipe bate o teto de 45 s. É o único "sem desfecho" em 24 gravações.
- **O que sobra é a trégua**: 15, 20, 21, 22 e 23 têm 8,3–9,9 s de vídeo sem contato nenhum, mais de 30% do clipe. **É o próximo alvo** (fila §6).
- \* A semente 15 foi gravada a 1,5× porque a primeira versão da regra perguntava ao Node, e o Node joga essa rodada diferente do Chrome (§4). Regravada às 08:02 com a regra
  dentro da página, saiu a 1,25× (`out/duelo-ritmo/prova/duelo-s15-regra.mp4`) e reprova do mesmo jeito (buraco de 10 s em 29,2 s). O 6/12 não muda.
- Os mp4 e JSON: `E:\jogo_ZOMBIE\out\duelo-ritmo\duelo-s13.mp4` … `duelo-s24.mp4`; veredito em `out/duelo-ritmo/veredito.json`.

## 3c. Duelo elaborado: a proposta (28/09, à noite)

O Adrian respondeu "Quase: ajustar" ao `duelo-e-isso` (28/09, 18:40). Ele pediu planos dos humanos, habilidades, animações, comunicação e nacionalidade. A proposta, com arquivo e linha do que existe e do que falta, está em **`docs/zombie/duelo-elaborado.md`**. Seis nós novos no Grimório, todos dependentes de `duelo-e-isso=quase` (commit `3e03425`):

- `duelo-plano-quem-escolhe`;
- `duelo-leitura-do-plano`, com maquete;
- `duelo-elenco`;
- `duelo-nacionalidade`;
- `duelo-voz`;
- `duelo-arte`.

**Até as respostas, o cenário não muda.**

**Medido para a proposta**: sem vídeo, no Node, sementes **401–440**, HEAD `24b68cd`, 13 s. As sondas e as saídas estão em `E:\jogo_ZOMBIE\out\design\`, fora do git.

- **O conselho decide por dentro e nada aparece.**
  - Linha de lanças (`formMilitia`) em 31 de 40 rodadas.
  - `shelterInPlace` em 40 de 40, sem abrigo nenhum na arena.
  - Nas 15 rodadas em que o registro guardou o fim, a milícia foi **largada** (`council.dropped`) depois de uma mediana de **4,5 s** de jogo. Debandada: 0.
- **Os guardas passam 41% do tempo fugindo** (`seekSafety`) e 25% lutando.
- **A trégua é uma perseguição.** Falsificador escrito antes de medir: H1 ("trégua é guarda fugindo") cairia se a fatia de fuga na trégua não fosse maior que a do contato, ou ficasse abaixo de 50%.
  - Deu **52,3% contra 41,4%**. H1 sobrevive, por pouco.
  - O zumbi mais próximo fica a uma mediana de **3,6 tiles** na trégua e de 0,9 com contato.
  - O guarda corre a 2,8 e o zumbi do duelo a 2,6: ninguém alcança ninguém.
- **H2, pré-registrada no doc (§8)**: "uma linha que segura acaba com a trégua".
  - Linha de base e medição depois do conserto nas sementes **441–540**.
  - H2 cai se a reprovação no critério 1 não baixar de ~38–40% para **25% ou menos**, ou se o critério 4 sair de 30–70%.

## 4. O que foi medido e vale como conhecimento

- **Chrome e Node não jogam sempre a mesma rodada (28/09).** O Chrome do gravador (153) e o Node da suíte e das prévias (24, V8 13.6) calculam `Math.sin`, `cos`, `atan2`,
  `exp`, `log` e `log10` com bits diferentes (medido em 200 mil entradas por função); `hypot` e `pow` batem. Em 23 de 24 duelos gravados isso não mudou nada (mesmo tique de
  veredito); na **semente 15** mudou a rodada: veredito aos **35,8 s de jogo no Node e 32,05 s no Chrome**, os dois de forma determinística. Consequências: "partida = semente
  + comandos" vale **dentro de um motor**; a prévia no Node serve para **contar critérios em muitas sementes**, não como prova de uma gravação específica (julgue gravação
  pelo JSON dela); e tudo que decide algo **da gravação** (a velocidade) roda na página. Consertar de verdade seria trocar essas funções por versões próprias em JS
  puro — não foi feito, e mexe em muito código de IA (23 `cos`, 20 `sin`, 18 `atan2`).

- **A horda parava de caçar.** Zumbi mandado a um prédio onde já havia chegado esquecia o objetivo e voltava a vagar a meia velocidade: cerco virava aglomeração fora de paredes
  intactas. Cinco tentativas falharam antes, quatro **raciocinadas em vez de medidas** (paciência, centro do prédio, o tile da porta, alcançabilidade). A causa: porta e janela são
  impassáveis até quebrar, então teste de linha de caminhada mirado no tile da própria abertura **nunca** pode dar certo. Hoje mira o tile vizinho do lado da aproximação.
- **Saturação do `seekSafety`: a distância não entrava na conta.** Ameaça pesada como `max(proximidade, perigoRecente × 0,5)` numa logística de inclinação 20 — joelho de 0,9 tile
  sobre uma entrada de nove: um **degrau vestido de ponderação**. Um avistamento fixa `perigoRecente` em 1, então o piso 0,5 já caía depois do degrau e travava o termo em 0,98
  sempre que algo tinha sido visto. Fugir batia qualquer tarefa 3,48 a 2,39 **em toda distância**: o aldeão não escolhia mal, não havia o que escolher. De brinde, o sino de abrigar
  era ignorado em qualquer alcance. Sintoma: 0 rodadas ganhas em 64, estourando o relógio com aldeões vivos e **parados**. Conserto: inclinação 8, centro 0,45, termo de susto 0,35.
- **Aldeão não atravessa ameaça visível — isso matou a premissa "atravesse".** Depois do conserto a coluna anda, mas **não passa**: uma vila que mata cinco por rodada não fura oito
  zumbis. A parada estava *escondendo* esse fato, não causando. Formato que dependa de a vila atravessar a horda está morto.
- **Advertência: "vila lobotomizada dura mais" foi medido contra um inimigo com defeito.** 1246 s contra 572 s da vila pensante, sem perder nenhuma das oito sementes casadas — mas
  os empates eram a horda que esquecia o objetivo ao chegar. **Não repetir esse número sem remedir** depois do `8d39b27`.
- O relógio mente sozinho: sobrevivência tem máximo em **ficar parado**. Por isso o arnês conta mortes e tiles por aldeão-segundo, exposição (fração de aldeão-segundos ao ar
  livre), quantos zumbis sobraram e quantos estavam ao lado de um prédio, e soma os desfechos em três baldes com asserção de que a soma fecha — defesa contra o erro que apareceu
  três vezes num dia: **marcador lido como medida** (o teto lido como duração; o fim do relógio lido como vitória).
- Chaves do arnês (`scripts/experiment.test.ts`, por variável de ambiente): `EXPERIMENT_SCENARIO`, `ROUNDS`, `SEEDS`, `SEED_START`, `OUTBREAK_SECONDS`, `LEARNING=on|off`,
  `LOBOTOMY=1`, `ABLATE=decisions|council`, `SPAWN=fora` (nasce fora de casa — controle, porque o braço sem mente nunca se move e o resultado dele podia ser o valor do tile de
  nascimento), `QUIET=1` (passo furtivo: separa "barulho" de "cruzar campo de visão", já que o volume do passo é função em degrau do passo, não da distância), `MASK`, `BLOCK`. Nada
  é escrito só para o braço lobotomizado: é este código com o pensamento desligado, para a comparação não poder ser fraudada com um espantalho.

## 5. Regras de método impostas pelo dono e pelo orquestrador

- **Critério de gravação escrito ANTES de medir.** Para o êxodo: vitória entre **40% e 80%** das sementes, **metade** delas entre **45 e 75 s**, e **contato antes da metade do
  vídeo** em pelo menos metade. Os três estão escritos no comentário de `EXODUS_PARAMS` desde `d9f6382`; o êxodo **reprova o terceiro** (2 de 10, §3). Para o duelo: §3b,
  em `DUEL_CRITERIA`, com um juiz executável (`scripts/duel-verdict.mjs`).
- **Nunca escolher a semente que venceu.** Gravar a semente porque deu o resultado bonito troca medição por propaganda.
- **Calibrar, confirmar e gravar em faixas de sementes separadas, e calibrar em muitas.** A gravação reproduz a prévia sem vídeo em 23 de 24 (§3b, §4), então os critérios se contam
  sem gravar a ~0,3 s por semente. Em 28/09: calibrado em 101–110 (5/10 passavam), gravado em 1–12 (3/12), confirmado em 201–260 e 301–400 (32–33%). Dez sementes de
  calibração mentiram por uma margem de 50% contra 33%.
- **Medir o tamanho do aldeão na tela antes de polir o resto.** O aldeão sai com `907 × escala / tiles` px de diâmetro; a 1080 px sobre ~6,5 cm de tela são ~166 px/cm. Um vídeo já
  foi reprovado por aritmética: 48 tiles na escala 2 dão 38 px, ou **2,3 mm** no celular. Piso ~**66 px** (~4 mm). O relatório traz `metricas_video.diametro_agente_p50` para isso.
- **Pergunta dirigida produz concordância**: perguntar "o que está errado neste vídeo", nunca "minha correção funcionou?".

## 6. Pendências e o que depende de decisão do dono

- **Formato do vídeo: decidido em 27/09 — o duelo.** O que ainda é dele: se a definição do §3b (seis guardas × quatro zumbis rápidos numa ruína, sem cortes) é o duelo que
  ele quis; se zumbi que corre e arena em ruína servem; e o que achou dos clipes, olhando no celular. O orquestrador leva a pergunta aberta, sem dizer qual venceu nem quais
  passaram. **Até a resposta, o cenário não muda.**
- **Respondido às ~03:20 de 28/09**: "sim" aos dois commits do duelo (`dab114c`, `a372bdc`) e "sim" à velocidade por clipe. O lote 2 (§3b) é o teste dessa regra.
- **Duelo elaborado (28/09, à noite)**: são seis nós pendentes do Adrian (§3c). O pacote mínimo que responde ao comentário dele custa **13–19 dias de sessão**. Com país
  mecânico, soma de 5 a 7; com arte nova, de 5 a 15. Isso compete com o objetivo das semanas ("estabilizar o que existe"). Quando fazer é decisão dele.
- **Regra de velocidade**: commitada em `24b68cd`. **Próximo alvo: a trégua** (critério 1, 5 de 12 no lote 2), sem mudar a luta antes da resposta dele; próxima faixa para gravar: 25–36.
- **Publicar ou não**: decisão dele, e não antes de 7 dias seguidos sem horário perdido nos dois canais atuais (rotas de 27/09). O canal nunca publicou (§Contratos). A ponte
  JSON/mp4 → estoque do `postar.py` é da Semana 3.
- **O experimento de 4 braços** (pensante × lobotomizada × silenciosa × nascendo fora, remedido depois do conserto da horda) **ocupa a máquina por horas** e não foi rodado. Precisa
  de janela: nada pesado entre :25 e :55, e a criação de histórias roda 01h–06h.
- O êxodo reprova o próprio critério 3 (§3); regravá-lo só se ele voltar a ser formato.

## 7. O que NÃO fazer

- **Não publicar nada daqui**: o jogo não tem login nem publicação própria, e por decisão registrada **não vai ter**.
- **Não commitar sem o dono pedir**; nunca `git add -A`; não mergear `feat/m15-polish` por conta.
- **Não rodar gravação nem experimento em lote** sem autorização: horas de máquina, atropela as postagens.
- **Não citar 1246 s × 572 s** como prova de nada (inimigo com defeito), nem os números do êxodo sem remedir.
- **Não escolher semente, nem velocidade à mão por semente**, no duelo: o lote é uma faixa em sequência, todos reportados; a velocidade é a regra (`--velocidade auto`).
  Faixas já usadas: 1–12 (lote 1), **13–24 (lote 2)**, 101–110 (calibração), 201–260 e 301–400 (prévia), 401–440 (sonda do duelo elaborado, §3c). Reservada: 441–540
  (linha de base e teste da H2, §3c). A próxima faixa limpa para gravar é **25–36**; para prévia, **541** em diante.
- **Não confiar num clipe gravado antes de um conserto de IA**: o `exodo-66` já não se reproduz (§3). O JSON do próprio clipe é a única fonte dos números dele.
- **Não desenhar formato que dependa de a vila atravessar a horda** — está medido que ela não atravessa.
- Não escrever arquivo grande no `C:` (o disco do sistema já encheu e derrubou rodada): tudo no `E:`.
- Não trocar `escala`/`tiles` no olho: medir o diâmetro no relatório.

## Contratos com outras partes

| Contrato | Quem manda | Quem consome |
|---|---|---|
| Linha JSON do `npm run record` (e `--resultado x.json`) | esta parte (`src/record/report.ts`) | a fábrica de vídeo / Publicação, em `E:\projetos` |
| Conta e postagem do canal zombie | Publicação (`random_builds/builds/contas.py`) | — |

**O contrato do gravador.** O mesmo que o `fight_recorder` do Neural Fights imprime, com os momentos de uma rodada de zumbis no lugar do HP dos lutadores. Todos os tempos em
**segundos de vídeo**. Campos observados em `out/exodo-66.json`:

```
sucesso, cenario, seed, pais, doutrina, resolucao [l,a], fps, velocidade,
camera_modo ("DIRETOR" | "FIXA"), hud (sempre false), vencedor, empate,
motivo ("vila_escapou", ...), duracao_jogo, duracao_video, ko_em_video,
resumo { aldeoes_no_inicio, aldeoes_no_fim, mordidos_no_fim, zumbis_no_fim,
         pico_de_zumbis, mortos, ondas, ondas_no_plano },
serie_vila   [ [t, aldeões vivos, deles mordidos, zumbis], ... ]   (a cada 0,25 s)
eventos_dano [ [t, "vila"|"zumbis", quantidade, categoria] ]       (corte do tédio)
eventos_narrativos [ {t, tipo, slot, n?, quantidade?, x, y} ]      (callouts; x,y em fração
              do mapa, para marcar em cima do quadro; o fim da rodada NÃO tem posição —
              aconteceu à vila, não num lugar)
eventos_som  [ [t, "grito"|"golpe"|"gemido"|..., intensidade, x] ] (desenho de som)
metricas_video { frames, zoom_p50, diametro_agente_p50 }
arquivo  (caminho absoluto do mp4)
```

Com país, `doutrina.etiqueta` são as duas ou três palavras que o cabeçalho da faixa queima na imagem (texto queimado é invisível para a tradução das plataformas; a frase inteira
vai na descrição). O mp4 sai com faixa de áudio silenciosa para o `concat -c copy` da fábrica funcionar.

**Para a ponte da Semana 3 (duelo):** `cenario` vem `"duelo"`; `ko_em_video` só é preenchido quando a vila **cai** — quando a vila vence, o instante do veredito está em
`eventos_narrativos` com `tipo: "vila_resistiu"`. A **`velocidade` muda de clipe para clipe** (1× a 3×, regra do §3b): quem mostrar "tempo de jogo" na tela tem de ler o
campo, nunca supor. O veredito do lote (quais clipes passam nos critérios) sai de `scripts/duel-verdict.mjs --json`, em `out/<pasta>/veredito.json`.

**O canal no registro de contas.** `random_builds/builds/contas.py` tem `"zombie": "Jogo zombie (gravações da partida)"`, com o comentário de 15/09/2026 dizendo que o jogo mora em
outro repositório, só grava o mp4, e não tem login nem publicação própria. No registro (`%LOCALAPPDATA%\neural-fights\contas.json`) as contas ativas do canal `zombie` são:
**YouTube `zombie_survivores`**, **YouTube web `zombie_survivores`** e **TikTok `zombie_surviv0rs`** (o `0` no lugar do `o` é o nome real da conta, não erro de digitação).

**O canal NUNCA publicou**: `random_builds/outputs/_publicar/publicados.jsonl` tem 244 linhas e **zero** menção a zombie. E o módulo de métricas só conhece `CANAIS = ("builds",
"historias")` — um vídeo do zombie publicado hoje não ganharia métrica nenhuma. O `ID_DE_VIDEO` de `visao/panorama/confiabilidade.py` também não aceita id de zombie, e o próprio
comentário de lá avisa que um canal novo precisa entrar ali.
