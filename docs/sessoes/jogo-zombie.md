# Jogo zombie

A parte que mora em **outro repositório**: `E:\jogo_ZOMBIE`. Aqui não se publica nada — o jogo só **gera o mp4 e um JSON**; conta, grade e postagem são da parte de Publicação, em `E:\projetos`.

Escrito em 27/09/2026 pela sessão dona. Tudo abaixo foi conferido lendo o repositório do jogo naquele dia; o que não deu para conferir está marcado **(não verificado)**.

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
npm test           # Vitest: 73 arquivos, 336 testes, 56,6 s (verificado 27/09)
npm run typecheck  |  npm run bench  |  npm run experiment   (ver §4)
```

URL: `?seed=`, `?preset=nightSiege`, `?cinema=1`, `?overlay=paths,beliefs,council`, `?panel=village`.

**Gravar um clipe** (precisa de Chrome e ffmpeg):

```
npm run record -- --cenario exodo --seed 6 --velocidade 1 --saida out/exodo.mp4 --resultado out/exodo.json
```

Outras flags: `--resolucao 1080x1920` (padrão), `--fps`, `--max-duracao`, `--cauda`, `--com-preparacao`, `--escala` e `--tiles` (tamanho do aldeão e quanto chão cabe no quadro),
`--pular N` (joga N segundos de jogo fora antes do primeiro quadro guardado), `--camera fixa`, `--lobotomia`, `--pais BR|PT|AR|US|JP|DE`, `--prever --paises BR,US,JP --alvo 80`
(estima sem vídeo).

O gravador serve `record.html` pelo Vite, dirige um Chrome headless pelo DevTools Protocol **um quadro de vídeo por chamada** (o resultado não depende da velocidade da máquina),
manda os quadros ao ffmpeg com faixa de áudio silenciosa (`anullsrc`, porque a fábrica junta clipes com `concat -c copy`) e imprime **uma linha JSON no stdout**. Saída: o `.mp4` em
`--saida` e o mesmo JSON em `--resultado`. Tudo que existe hoje está em `out/` (39 arquivos, ~240 MB), e `out/` **não** está no `.gitignore`. Cenários: `nightSiege, rumorMill,
keenEars, hiddenBite, fortressTown, lastStand, arena, limpeza, exodo`.

## 2. Estado da branch `feat/m15-polish`

**Não há trabalho de código sem commit.** `git status` mostra apenas `out/` como não rastreado (os mp4/json das gravações); `git diff` e `git diff --cached` estão vazios. HEAD =
`89e6c80`. A branch não foi mergeada na `main` e não tem remoto.

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
- **Divergência a resolver**: a mensagem do commit diz **7 vitórias em 10** (7 sementes na janela de 45–75 s) e os comentários do código dizem **8 em 10**. Uma das duas está velha;
  remedir antes de citar qualquer uma.
- **O clipe pronto**: `out/exodo-66.mp4` (16,4 MB) + `.json`. Seed 6, 1080x1920, velocidade 1, câmera DIRETOR, sem HUD, vencedor `vila`, motivo `vila_escapou`, 64,25 s de jogo e
  **64,33 s de vídeo**, 15 aldeões no início e 5 no fim, 0 mordidos, 25 zumbis vivos; diâmetro do aldeão (p50) 66,35 px.
- **A fraqueza medida**: `eventos_dano` tem **um único** evento — `[56.55, "vila", 1, "mordida"]`. A primeira mordida vem aos 56,55 s de 64,33 s: **88% do vídeo sem um contato**.
  Um minuto de gente andando e um susto no fim.
- A mesma rodada foi gravada em três tamanhos de aldeão: `out/exodo.json` (p50 54,06 px), `exodo-66` (66,35) e `exodo-83` (83,55). `exodo-83b.mp4` é **byte a byte idêntico** ao
  `exodo-83.mp4` (regravação, que de graça serve de prova de determinismo); `exodo-66-400.mp4` é a redução para olhar em tamanho de celular.

## 4. O que foi medido e vale como conhecimento

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
  vídeo**. A janela 45–75 s está nos comentários do cenário; os outros dois foram acordados na sessão e **não estão escritos no repositório** — quem continuar deveria gravá-los
  junto ao `EXODUS_SHARE`. O `exodo-66` **falha** o terceiro critério (contato a 88%).
- **Nunca escolher a semente que venceu.** Gravar a semente porque deu o resultado bonito troca medição por propaganda.
- **Medir o tamanho do aldeão na tela antes de polir o resto.** O aldeão sai com `907 × escala / tiles` px de diâmetro; a 1080 px sobre ~6,5 cm de tela são ~166 px/cm. Um vídeo já
  foi reprovado por aritmética: 48 tiles na escala 2 dão 38 px, ou **2,3 mm** no celular. Piso ~**66 px** (~4 mm). O relatório traz `metricas_video.diametro_agente_p50` para isso.
- **Pergunta dirigida produz concordância**: perguntar "o que está errado neste vídeo", nunca "minha correção funcionou?".

## 6. Pendências e o que depende de decisão do dono

- **Formato do vídeo**: decisão dele. O êxodo dá uma rodada inteira sem corte com veredito no fim, mas com 88% sem contato. Alternativas já implementadas e não decididas: `arena`
  em faixa ("qual país aguenta mais", 3 vilas empilhadas, câmera FIXA), `limpeza`, duelos curtos (`out/duelo*.mp4`).
- **Publicar ou não**: decisão dele. O canal nunca publicou (§Contratos).
- **O experimento de 4 braços** (pensante × lobotomizada × silenciosa × nascendo fora, remedido depois do conserto da horda) **ocupa a máquina por horas** e não foi rodado. Precisa
  de autorização e de janela: nada pesado entre :25 e :55, e a criação de histórias roda 01h–06h.
- Regravar o êxodo com o critério escrito antes; reconciliar 7-em-10 × 8-em-10 (§3); limpar ou ignorar os ~240 MB de `out/`.

## 7. O que NÃO fazer

- **Não publicar nada daqui**: o jogo não tem login nem publicação própria, e por decisão registrada **não vai ter**.
- **Não commitar sem o dono pedir**; nunca `git add -A`; não mergear `feat/m15-polish` por conta.
- **Não rodar gravação nem experimento em lote** sem autorização: horas de máquina, atropela as postagens.
- **Não citar 1246 s × 572 s** como prova de nada (inimigo com defeito), nem os números do êxodo sem remedir.
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

**O canal no registro de contas.** `random_builds/builds/contas.py` tem `"zombie": "Jogo zombie (gravações da partida)"`, com o comentário de 15/09/2026 dizendo que o jogo mora em
outro repositório, só grava o mp4, e não tem login nem publicação própria. No registro (`%LOCALAPPDATA%\neural-fights\contas.json`) as contas ativas do canal `zombie` são:
**YouTube `zombie_survivores`**, **YouTube web `zombie_survivores`** e **TikTok `zombie_surviv0rs`** (o `0` no lugar do `o` é o nome real da conta, não erro de digitação).

**O canal NUNCA publicou**: `random_builds/outputs/_publicar/publicados.jsonl` tem 244 linhas e **zero** menção a zombie. E o módulo de métricas só conhece `CANAIS = ("builds",
"historias")` — um vídeo do zombie publicado hoje não ganharia métrica nenhuma. O `ID_DE_VIDEO` de `visao/panorama/confiabilidade.py` também não aceita id de zombie, e o próprio
comentário de lá avisa que um canal novo precisa entrar ali.
