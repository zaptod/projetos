# Histórias por IA — canal de relatos narrados

Projeto **separado** do `random_builds`, controlado pelo mesmo painel
(`python painel_ui.py` na raiz → página **📖 Histórias**).

O produto é um vertical de 60–90 s: uma história em primeira pessoa, no
estilo dos relatos do Reddit, narrada por voz sintética, com uma imagem por
cena e legenda karaokê. O único objetivo do roteiro é **prender quem
assiste** — todas as regras de escrita existem por causa disso.

## O fluxo

```
1. gerar    → o browser abre o ChatGPT/Gemini e conduz a conversa inteira
              (bíblia da história → parte 1 → parte 2 → ...)
2. imagens  → uma imagem por cena, em todas as partes (PicassoIA, com prova)
3. vídeo    → narração medida + plano + voz + UM MP4 POR PARTE
```

Uma **parte é um vídeo**. Uma história curta é uma série de uma parte só — o
resto da pipeline não precisa saber a diferença.

```bash
python main.py llm login --provedor chatgpt   # uma vez: salva a sessão no perfil
python main.py gerar --partes 8 --cenas 14    # a série inteira, sozinho
python main.py gerar --provedor gemini --tema "uma herança"
python main.py tudo historia_00002            # imagens + um vídeo por parte
python main.py video historia_00002 --parte 3 # só a parte 3
python main.py status historia_00002          # parte a parte
python main.py publicar                       # as partes em ORDEM de publicação
python main.py llm probe --provedor chatgpt   # quando o site mudar
```

### Por que em duas etapas (e por que isso exige a automação)

Pedir "uma história de 80 cenas" num prompt só não funciona: o modelo perde o
fio, repete informação e resolve o conflito no meio. O que funciona é o que um
roteirista faz:

1. **A bíblia** (`serie.prompt_biblia`): premissa, elenco, a virada central e o
   arco de **cada parte** — com o gancho de abertura e o cliffhanger de
   fechamento de cada uma. Nenhuma cena é escrita ainda.
2. **Cada parte** (`serie.prompt_parte`): escrita com a bíblia inteira em
   contexto, no formato do contrato.

As duas etapas acontecem **no mesmo chat**, então a parte 7 é escrita com a
bíblia e as seis partes anteriores ainda no contexto. É isso que copiar e colar
não dava — e é por isso que a automação importa aqui.

A bíblia também resolve o problema visual: ela fixa a **descrição física do
protagonista em inglês**, e essa mesma frase entra em toda cena de todas as
partes. É o que faz 80 imagens parecerem a mesma pessoa.

### Como cada parte é escrita

- **Parte 1** abre com o momento mais chocante da história inteira.
- **Partes do meio** recapitulam em UMA frase que funciona como gancho novo
  para quem cai ali primeiro (nunca "no episódio anterior"), e terminam em
  cliffhanger avisando que continua.
- **Última parte** responde a pergunta central e fecha com a pergunta para
  quem assiste.

Resposta cortada é normal (os sites limitam o tamanho da mensagem): quando vêm
menos cenas do que o pedido, o turno seguinte é **"continue da cena N"** — não
uma tentativa nova do zero. E o roteiro é salvo **a cada parte**: se o site cair
na parte 6, as cinco anteriores já estão no disco.

### Login e quando o site muda

```bash
python main.py llm login --provedor chatgpt   # janela abre, você entra, fica salvo
python main.py llm probe --provedor gemini    # despeja o DOM real
```

Cada LLM tem seu próprio perfil de Chrome (`.browser_profile/chatgpt`,
`.browser_profile/gemini`), separado dos perfis do outro projeto. Quando um dos
sites mudar de classe, o conserto é `llm probe` + ajustar
`src/llm/seletores.py` — **nenhum outro arquivo muda**.

Nada é dado como feito sem prova: o envio só conta quando o campo esvazia (ou o
botão de parar aparece), e a resposta só é lida quando o texto **para de
crescer**. Ler assim que aparece texto devolveria meia resposta — e meia
resposta é um roteiro sem final.

## Contas: quem publica o quê

Os dois canais **não** compartilham conta — publicar a história no canal de
builds é irreversível. O painel tem a página **🔑 Contas**: uma linha por
serviço × canal, com a conta ativa, se o login existe e onde ele mora.

| serviço | o que é | usado por |
|---|---|---|
| YouTube | OAuth (client-id/secret + token por conta) | publicar |
| TikTok | perfil de Chrome | publicar |
| ChatGPT / Gemini | perfil de Chrome | escrever os roteiros |
| PicassoIA | perfil de Chrome | imagens das cenas |
| Digen | perfil de Chrome | vídeo do payoff (canal de builds) |

Na página: **➕ Nova conta** (só o nome), **✓ Usar esta conta** (define a
ativa naquele canal) e **🔑 Entrar / Autorizar** (abre o login certo). O
login do ChatGPT/Gemini é **global**: feito uma vez, serve para qualquer
parte do projeto que precise do mesmo LLM.

A conta `principal` continua nos caminhos antigos (`.browser_profile/...`,
`youtube_credentials.json`) — nenhum login já feito se perde. Conta nova
ganha pasta e arquivo próprios em `%LOCALAPPDATA%/neural-fights/`.

## Publicar a série em um clique

```bash
python main.py publicar historia_00002 --vistoriar   # só confere
python main.py publicar historia_00002 --serie       # vistoria + sobe + agenda
python main.py publicar historia_00002 --serie --intervalo 12 --comecar 2026-09-01T18:00
```

No painel, o botão **🚀 Publicar série** faz o mesmo. O que acontece, nesta
ordem:

1. **Vistoria** cada parte no ARQUIVO, não no plano (`qualidade.py`): vídeo
   mudo, curto demais, sem imagem nenhuma ou mais velho que as imagens **não
   sobe**. Um roteiro perfeito não garante mp4 bom, e nada disso levanta
   exceção no render — o arquivo existe do mesmo jeito.
2. **Sobe na ordem**, na conta de YouTube do canal `historias`.
3. **Agenda**: a parte 1 sai em ~15 min e cada seguinte 24 h depois
   (`--intervalo`). Soltar oito partes no mesmo minuto mata a série. Tudo vai
   **privado com `publishAt`** — o horário é a única coisa que decide quando
   o vídeo aparece.
4. **Registra** o que subiu (`outputs/_publicar/publicados.jsonl`), então
   rodar de novo não publica duas vezes.

O TikTok **posta de verdade** (decisão de 31/08: um clique sem parada de
segurança): `--serie --tiktok` publica a próxima parte pendente — só
`tiktok_partes_por_clique` (config `publicacao.json → um_clique`, padrão 1)
por execução, porque o TikTok não agenda por aqui e despejar a série de uma
vez a mata. O botão do painel não pergunta nada: a **vistoria é o freio**, e
ele acrescenta `--tiktok` sozinho quando a conta do canal `historias` tem
login.

### Vários processos ao mesmo tempo

A trava é **por conta** (`random_builds/builds/travas.py`, nome
`servico__conta`): gerar roteiro no ChatGPT, imagens no PicassoIA e o worker
de builds no Digen rodam **em paralelo**. Só a MESMA conta serializa — com
uma conta de PicassoIA própria para o canal `historias` (página Contas), as
duas pipelines de imagem também rodam juntas. Cada etapa registra
início/ok/erro no diário (`atividade.jsonl`) que a página **🏭 Vila** do
painel mostra ao vivo.

## Quando o PicassoIA recusa uma cena

Aconteceu duas vezes em 31/08. O site avisa por **ícone** — um escudo
vermelho (`lucide shield-alert`), não por frase —, e é assim que a detecção
funciona hoje: `wait_for_render` acha o escudo em segundos, em vez de esperar
os 300 s do timeout e morrer dizendo "a imagem não ficou pronta".

Quando bloqueia, a escalada é esta:

```
prompt original
  ↓ bloqueado
ChatGPT reescreve a cena          ← src/imagens/reescritor.py
  ↓ bloqueado
ChatGPT reescreve mais conservador (pessoa de longe, de costas, fora do quadro)
  ↓ bloqueado
troca mecânica nível 2 → nível 3 (só o ambiente)   ← a rede de segurança
```

O **ChatGPT vem primeiro porque ele escreveu a história**: ele sabe o que a
cena está contando e reescreve mantendo o momento, enquanto a troca mecânica
só substitui palavra por palavra. A sessão abre na **primeira** recusa (quem
nunca é bloqueado nunca abre o navegador) e fica aberta até o fim — um chat
para a história inteira, então na terceira cena barrada o modelo já sabe o
que esse filtro costuma recusar. Se o navegador não abrir (sem login, conta
ocupada), a troca mecânica assume sozinha e nada trava.

Cena barrada até o fim fica marcada em `outputs/<id>/imagens.json`
(`recusadas`, com o motivo e a **última versão tentada**) e as outras cenas
continuam gerando.

Ajustes em `config/imagens.json`: `reescrever_com_llm` (padrão `true`),
`reescritas_max` (`2`), `llm_provedor` (`chatgpt`), `suavizar_antes` (`true`)
e `suavizacao_max` (`3`). A prevenção também subiu para o roteiro: as
regras de imagem agora mandam o LLM descrever o **antes ou o depois** (a mão
tremendo, a porta fechada) em vez do ato — passa no filtro e, de quebra,
sugerir assusta mais do que mostrar.

## O modelo de roteiro

Um modelo dita **só a estrutura** — nunca a ideia. Vêm três em
`config/roteiro.json` (`reddit`, `confissao`, `vinganca`), e o seu próprio é
um `.txt` em `modelos/`, uma linha por bloco:

```
GANCHO (1 cena): a frase mais chocante, no meio da ação.
SITUAÇÃO (2 cenas): quem sou eu e o que estava em jogo.
...
```

O modelo substitui a estrutura; **as regras de retenção e o contrato de
saída continuam valendo** — são eles que fazem o roteiro virar vídeo.

## O que o LLM devolve

```
TITULO: ...

CENA 1
IMAGEM: <prompt em inglês da cena>
TEMPO: 4
NARRACAO: <o que o narrador fala>

CENA 2
...
```

O parser aceita esse formato com qualquer enfeite (`**`, `##`, listas,
`NARRAÇÃO` com acento, "5 segundos") e também JSON. O que ele **recusa**,
dizendo o motivo: roteiro com menos de 4 cenas, cena sem narração, cena sem
prompt de imagem.

## As regras que fazem prender (config/roteiro.json → `regras`)

Desde 31/08 a narração é um **desabafo**, não um roteiro: contrações
(pra/tô/né), frases de tamanhos desiguais, no máximo uma autocorreção por
cena, detalhe mundano no meio da frase, virada contada na ordem em que a
pessoa descobriu, final imperfeito que fecha com a pergunta do próprio
autor. As imagens já entregam que o vídeo é artificial — o texto é a única
chance de parecer gente. As 13 regras vivem em `regras.narracao` e entram
nos prompts da bíblia e de cada parte.

- A **primeira frase** é o momento mais chocante — antes de qualquer contexto.
- Nada de saudação, apresentação ou "hoje eu vou contar".
- Frases de no máximo 14 palavras, linguagem falada.
- Cada cena termina deixando **uma pergunta no ar**.
- Detalhe concreto em quase toda cena (horário, valor, nome) — é o que vende
  verdade.
- Uma **virada** no meio que faz o começo significar outra coisa.
- O desfecho só nos últimos 20% — mas prometido lá no gancho.
- Termina com uma **pergunta direta** para quem assiste.

## Nada de vídeo truncado dizendo "pronto"

O bug mais caro do projeto até agora (31/08/2026), e o mais silencioso: um
segmento ficou sem o `moov atom` (o ffmpeg que o escrevia morreu no meio) e o
`concat` seguinte **parou nele** — imprimiu *"Error during demuxing"* no
stderr e **saiu com código 0**. O pipeline só olhava o código de saída, então
a parte 1 virou um mp4 de **11,8 s no lugar dos 193 s** do plano, o log
escreveu `[render:celular] parte 1/10: ... (193.352s)` e nada acusou.

Três guardas agora:

1. **Todo segmento é conferido depois de escrito** (`rb video/medidas.py`,
   ffprobe). Segmento ilegível é refeito uma vez, e o arquivo pela metade é
   apagado — nunca sobra lixo para o concat tropeçar.
2. **O concat recusa a lista** se algum segmento não abre, dizendo **qual**.
3. **O resultado é medido**: um vídeo mais curto que a soma dos segmentos não
   é sucesso, mesmo com o ffmpeg saindo 0.

O `stderr` do ffmpeg também parou de ser jogado fora — antes, quando ele
morria, o Python levantava um `OSError: [Errno 22]` cru (o cano quebrado) e o
motivo real ficava perdido.

## Por que a narração soava robótica (e o que mudou)

Diagnóstico de 01/09/2026, sobre a `historia_00003`:

| queixa | o que a medição achou |
| --- | --- |
| "a voz não condiz" | toda história saía em `pt-BR-AntonioNeural` — *Friendly, Positive* no catálogo do motor — fosse quem fosse que narrava |
| "a leitura é cortada" | **não era a voz, era o recorte**: cada cena era uma síntese separada, e a entonação reiniciava a cada ~14 s. 97% de fala e só 5,5 s de silêncio em 206 s — não faltava áudio, faltava continuidade |
| "não é cativante" | o roteiro media bem (24% de perguntas, 24% de frases curtas). O problema era **visual**: uma troca de imagem a cada **14,7 s**, contra 2,5 s do vídeo de build |

**Leitura contínua.** A parte inteira é narrada numa síntese só, e as cenas
são recortadas do áudio pelos limites de palavra (`voz.narrar_continuo`). A
prosódia atravessa as cenas, as pausas nascem da pontuação e some o vazio
digital entre elas. O plano de edição deixa de ser uma *previsão* da fala e
passa a ser o *recorte* dela. Conferido: as cenas caem a menos de 0,5 s de
onde a medição cena-a-cena as colocava, e o alinhamento tolera o motor falar
número por extenso ("R$ 1.200" vira cinco palavras).

**A voz vem de quem narra.** `roteiro/narrador.py` lê a descrição física do
protagonista — a mesma frase em inglês que já mantinha as imagens parecidas
— e escolhe entre as três vozes que o motor gratuito tem em pt-BR, ajustando
o tom pela idade. A bíblia agora também declara `NARRADOR:`, e o campo
explícito vence a adivinhação.

**A cama de som deixou de ser batida.** As histórias usavam a trilha do
canal de builds: bumbo, caixa, chimbal e 808. Debaixo de um desabafo em
primeira pessoa isso vira videoclipe e compete com a fala. `trilha.ambiente`
tem acordes longos, um sub respirando e nenhum tempo marcado — e fica em
−22 dBFS, abaixo dos −17 da trilha de builds.

**O olho ganhou o que olhar.** Cena longa vira dois ou três planos da MESMA
imagem, em enquadramentos diferentes (`timeline.dividir_planos`) — aberto,
fechado, lateral. Não custa imagem nova e a cadência foi de 14,7 s para
**6,0 s**. O texto pertence ao primeiro plano da cena; os outros são
continuação visual, e nem a legenda nem a voz os repetem.

## A cena espera a fala

O teto (`narracao.maximo_cena`, 14 s) vale para cena **sem** fala. Com fala
medida ele **não corta**: `voz.py` trunca o áudio no espaço que a cena der, e
uma frase decepada no meio da palavra é pior que uma cena longa. Medido em
31/08: 9 das 14 falas de uma parte saíam cortadas. Agora a cena cresce e o
`[timeline]` avisa quantas passaram do teto — narração mais curta no roteiro
é o que deixa o vídeo rápido de novo (por isso `narracao_max_chars` caiu para
220, ~10 s de fala).

A regra técnica que manda no vídeo. O `TEMPO` do roteiro é uma **dica**; a
duração real da cena é `max(tempo sugerido, fala medida + margem)`, com piso
e teto em `config/roteiro.json → narracao`.

A narração é **medida antes** de o plano existir (`voz.medir`), e só então as
cenas são cronometradas. Inverter essa ordem — cronometrar a cena e espremer
a voz depois — foi o bug mais caro do outro projeto: 29 de 33 falas cortadas
no meio da palavra. Um teste trava isso
(`test_nenhuma_cena_termina_antes_da_fala`).

## O vídeo

- **Título sobre a primeira imagem** (2,2 s, com cortina, saindo por fade) —
  nunca um cartão de texto antes dela, que é o que faz rolar o feed.
- **Ken Burns** em toda cena, alternando push-in e pull-back: imagem parada
  em vertical é morte por retenção, e movimento igual em todas vira slideshow.
- **Legenda karaokê**: a palavra falada acende, em grupos de 4. É o que
  segura quem assiste no mudo — a maior parte do público de Shorts. Os
  tempos vêm do próprio edge-tts (limites de palavra).
- **Som**: trilha sintetizada (nasce sozinha em `assets/music/`, sem custo),
  abaixada sob a fala (sidechain), tudo normalizado em **−14 LUFS**.
- **Sem imagem, a cena não deixa de existir**: sai com o texto grande sobre o
  fundo do canal. Vídeo incompleto é melhor que vídeo inexistente.

## O que é reaproveitado do `random_builds`

Três peças maduras, importadas pela ponte `src/compartilhado.py` (o `src` de
lá é registrado como pacote `rb`, para não colidir com o `src` daqui):

| peça | de onde | por quê |
|---|---|---|
| narrador | `content/voz.py` | edge-tts grátis, voz do Windows como reserva, cache, limites de palavra |
| trilha e efeitos | `video/trilha.py` | síntese própria, sem biblioteca de áudio |
| PicassoIA | `identity/picasso_client.py` | browser furtivo, login persistente, prova de origem |
| YouTube | `publicar/youtube.py` | mesmo OAuth, upload resumável |
| browser furtivo | `identity/browser.py` | patchright + Chrome real, perfil persistente |

**Conta compartilhada:** as imagens usam o mesmo perfil de Chrome e a mesma
conta do PicassoIA da outra pipeline. Por isso a **trava é a mesma**
(`queue.instancia_unica`): os dois workers nunca abrem o perfil ao mesmo
tempo, e o interruptor de pausa (faixa PIPELINE do painel) vale para os dois.
Nenhuma imagem entra na história sem **prova de origem** — o card do
histórico com o nosso prompt.

## Estrutura

```
config/
  roteiro.json     modelos (estrutura), regras de retenção, contrato, limites
  imagens.json     estilo visual das cenas + ajustes do PicassoIA
  render.json      perfis, cores, tipografia, câmera, legenda, som
  publicacao.json  título/descrição/hashtags
modelos/           seus modelos de roteiro (.txt)
src/
  compartilhado.py ponte para o random_builds
  llm/             seletores + cliente (ChatGPT/Gemini) + probe
  roteiro/         modelo (prompt-mestre), serie (bíblia + partes),
                   gerar (conduz a conversa), roteiro (parser/validação)
  imagens/         fila (estado no disco) + worker (PicassoIA)
  video/           timeline (a cena espera a fala) + renderer
  pipeline/        controller (orquestra tudo)
  publicar/        catálogo, exportação, YouTube
outputs/historia_00002/
  roteiro.json biblia.json imagens.json
  conversa/biblia.txt conversa/parte_01.txt ...   (o que o LLM respondeu)
  cenas/p01_cena_01.png ...                        (imagem por cena, por parte)
  partes/p01/edit_plan.json voz.wav voz_palavras.json legendas.srt
  final_celular_p01.mp4 final_celular_p02.mp4 ...  (um vídeo por parte)
```

**Dependências:** as mesmas do `random_builds` (Pillow, numpy, edge-tts,
patchright) mais FFmpeg no PATH. A pasta `random_builds/` precisa existir ao
lado desta.

**Testes:** `python -m unittest discover -s tests -p "test_*.py"` daqui de dentro.
