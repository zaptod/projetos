# Passagem: BUILDS / NEURAL FIGHTS

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

Hoje no disco: 83 `generation_*`, 15 `duelo_*`, 2 `tournament_*`, 4 `fight_*`.

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

# GERAÇÃO NOTURNA — o que as tarefas NeuralFights_gerar_01..05 (HH:02) chamam
python main.py noite --listar        # tarefas + duelos que a grade escolheria (e o teto)
python main.py noite --ensaio        # faz todas as conferências e diz o que faria; não gera
python main.py noite --duelos 8      # rodada manual: 8 ignorando o teto (o relógio ainda manda)
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
`config/geracao.json`): na janela 01h–06h, gera duelos até o teto
(`dias_de_gordura` 2 × duelos/dia pela cota: 4/8 de 10 horários = 5 → **10
duelos**) e depois roda o `identity worker` (capa e payoff das builds). O
estoque é contado pelo **mesmo funil da escolha** (não publicado, sem
pendência, título livre; dois pendentes com o mesmo título contam um). Nada
começa se não termina antes de **:25** — cada duelo reserva 5 min, cada job
do worker 8 —, e no máximo 6 duelos por rodada. Trava `builds__gerar` entre
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
cota dele). Atenção: o comentário do config e do código falam em "8 disparos
diários", mas `builds/grade.py` tem **10** horários desde 15/09 — os pesos são
relativos, então a escolha continua certa; o texto é que envelheceu.

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
  **Build (roleta) continua manual**: nenhuma tarefa roda `generate-video`.
- **Personagens de agosto perdidos.** O banco foi refeito em 02/09 e as fichas
  de agosto saíram junto. Quem depende delas não volta: a estreia de uma build
  antiga é impossível, não pendente — `catalogo._falta_estreia()` diz isso com
  o nome do personagem, em vez de pedir para "gravar a luta" (era a lápide que
  contava 20 tarefas todo dia).
- **Vídeo mudo.** Render antigo saía calado ou com som só no fim.
  `generation_00066/estreia/final_celular.mp4` tem **114,7 s de silêncio em
  120,8 s (95%)**, média -30,4 dB — medido agora com ffmpeg. A guarda está na
  publicação (`_audio_mudo`, `FRACAO_MUDA = 0.5`) e é ela que segura esse vídeo.
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

## 5. Estado de hoje (27/09/2026, 23:58)

- **Duelos**: `duelo_00008` a `00011` já saíram; **4 no estoque** que a grade
  escolheria (`00012` a `00015`), teto 10. Rodada manual marcada para esta
  madrugada com vigia armado às 23:58 (A às 01:00:30, até 8 duelos antes de
  01:25; B às 01:55:30, o que faltar para 8, mais o worker). As tarefas de
  01:02 e 02:02 saem com "já rodando" se a manual estiver no meio.
- **Builds**: 18 variantes B voltaram à fila com título próprio (§4); gordura
  de builds 2 dias pelo `postar.py --ver`.
- **Worker**: 8 jobs na fila — `generation_00085` (4, de 24/09) e
  `generation_00077` (4, enfileirados em 27/09 às 23:55 sem drenar). A conta do
  PicassoIA é a mesma das histórias (mesma trava de perfil), e a rodada de
  histórias das 01:20 costuma segurá-la por ~2 h; o worker tenta de novo às
  03:02, 04:02 e 05:02. Build não tem `capa.png` (só duelo tem); o que falta
  nas duas é imagem do personagem e payoff.
- **82 personagens e 95 armas** no banco vivo; só **9** dos personagens de
  roleta estão nele (os de agosto se perderam em 02/09).
- Pendente:
  - **`generation_00066`** é a única estreia em estoque e está barrada por
    áudio mudo (95% de silêncio) — regravar ou descartar;
  - **7 builds fora por título** que são a mesma build de outra (§4) —
    decisão do Adrian se ficam fora para sempre;
  - **nenhuma tarefa gera build nem estreia**: a roleta continua manual.

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
  minha (`builds/pipeline/tarefas_noite.py`), trava `builds__gerar`. Os
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
