# Publicação

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/publicacao/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (29/09/2026) · “29/09 01:26, pela Mesa de comando: força total, até 2 agentes” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Outro (comente) (28/09/2026) · “28/09 21:48, pela Mesa de comando: passou de 100% da sessão, para tudo” `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Só quando eu pedir (28/09/2026) · “28/09 22:26, pela Mesa de comando: força total só quando eu pedir” `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`
- ✅ **Limpeza do disco (C: com 9 GB livres)** — Só o seguro (~1,2 GB) (29/09/2026) `limpeza-do-disco`
- ✅ **E: com 17 GB livres — o cache do Google Drive (186 GB)** — Abrir o Google Drive e deixar ele terminar e limpar sozinho (recomendado primeiro) (29/09/2026) `limpeza-do-disco-e`

**Publicação**
- ✅ **As 3 partes só no TikTok (00022:p03, 00027:p01, 00032:p04)** — Subir no YouTube (28/09/2026) `partes-so-no-tiktok`
- ✅ **5 duplicatas públicas no canal de builds** — Voltar a privado (reversível) (28/09/2026) `duplicatas-publicas-builds`
- ✅ **Rascunhos e privados** — Manter (28/09/2026) `rascunhos-e-privados`
- ✅ **Legenda incompleta da h31 p06 no TikTok** — Corrigir (28/09/2026) `legenda-h31-p06`
- ⏳ **A guarda de 1 post por horário conta pela hora do relógio** — A guarda que evita 2 posts no mesmo horário conta pela HORA DO RELÓGIO. Um upload manual às 22:12 contou como o post das 22:37 e o horário ficou sem vídeo novo. Troco a guarda para contar pelo HORÁRIO DA GRADE? `guarda-hora-da-grade`

<!-- decisoes:fim -->

Documento de passagem. Quem chegar aqui sem nunca ter visto o projeto consegue
operar esta parte lendo só isto. Escrito em 27/09/2026.

## 1. O que é, e o caminho de uma publicação

Esta parte **escolhe** qual vídeo sai, **publica** nos dois destinos e
**registra** o que saiu. Não cria nada: histórias e builds chegam prontos.

| Peça | Arquivo |
| --- | --- |
| A rodada inteira: escolha, guardas, avisos, recuperações | `E:\projetos\ferramentas\postar.py` (2868 linhas — é o cérebro) |
| Grade: horários, minuto, cota por plataforma | `E:\projetos\random_builds\builds\grade.py` |
| Título comparável ("isto já está no ar?") | `...\builds\publicar\titulos.py` |
| Ledger, `publicado()`, `prova_ok()`, reconciliação, métricas | `...\publicar\metricas.py` |
| Catálogo dos mp4 de builds; corte em pedaços ≤180 s | `...\publicar\catalogo.py`, `cortes.py` |
| Publicadores | `youtube.py` (API), `youtube_web.py` (navegador — é o caminho usado), `tiktok.py` (navegador) |
| Escrever título/descrição/legenda no campo e conferir | `...\publicar\escrita.py` (os dois publicadores passam por ele) |
| "O que aconteceu no clique" + lista "a conferir" | `...\publicar\desfecho.py` |
| Ledger × canal de verdade / privado que deve voltar | `conferencia.py`, `recuperar.py` |

Uma rodada (`postar.py` sem argumentos, disparada pelo Agendador):

1. `esperar_a_rede()` — resolve DNS por até 300 s (abrir o Chrome para descobrir
   que a rede caiu custa minutos).
2. **Histórias**: `fila_de_historias()` ordena → `proxima_historia()` peneira →
   `contos.publicar.catalogo.publicar_youtube` → `serie.registrar` →
   `_tiktok_das_historias` → `serie.registrar`.
3. **Builds**: `proximo_build()` → `youtube.publicar_como_configurado` →
   `_tiktok_dos_builds` (`tiktok.publicar`) — os dois **registram por dentro**.
4. Depois, e nunca no lugar: **recuperação do TikTok** (1 por canal, saiu no
   YouTube e nunca chegou lá), **recuperação do YouTube** (1, ficou privado no
   canal) e **reserva do TikTok** (só se builds não levou nada lá neste horário).
5. `avisar()` no Telegram, estoque em dias, e **saída 1** se tentou e nada saiu
   (era `return 0` fixo, e o Agendador registrava sucesso em rodada vazia).

O registro é assimétrico de propósito: **histórias registram por fora**
(`serie.registrar`), **builds por dentro** do publicador — porque
`metricas.registrar_publicado` descarta canal ≠ `builds`. Trocar duplica de um
lado e perde a linha do outro.

## 2. A grade e as guardas

`grade.GRADE` — dez horários com **minuto próprio**: `00:37, 06:37, 09:37,
12:07, 15:37, 17:57, 20:37, 21:37, 22:37, 23:37`. São as horas vagas das
pessoas (decisão dele, 15/09). **TikTok posta em todos**. Dez tarefas
`NeuralFights_postar_HH` no Agendador (conferidas hoje: todas "Pronto").

Use `grade.minuto(h)`, nunca a constante `MINUTO`; e `grade.slot(agora)` para
saber a que horário a rodada pertence — :57 mais ~4 min de upload cruzam a hora,
e a hora do relógio dava dois veredictos na mesma rodada.

**Cota por formato** (builds): `COTA_PADRAO = {duelo 4, build 3, estreia 1,
torneio 0}`, sobreponível em `config/publicacao.json` → `grade.mistura`.
`escolher_por_cota` é pura: vence o formato mais atrasado em `servidos/cota` nas
últimas `JANELA_DA_GRADE = 16` publicações. Cota 0 não é proibição.

| Guarda | Onde mora |
| --- | --- |
| Um por horário **por plataforma** | `postar.publicou_neste_horario` (janela = hora do relógio; fonte = ledger) |
| Título já publicado (fecha a fila) | `postar._sem_titulo_repetido`/`titulo_repetido`; regra em `titulos.chave/repetido` |
| Variante A/B (`:B` tem o mesmo título) | `postar.VARIANTES`, `_e_variante`, e a própria chave de título |
| Teto de 2 por fonte/dia, por destino | `TETO_POR_FONTE_NO_DIA`, `_fontes_cheias_hoje`, `_sem_fonte_cheia` |
| Ordem das partes na fila | `fila_de_historias` (menor parte que falta; a anterior tem de existir) |
| Ordem das partes **no destino** | `_em_ordem_no_destino` — pergunta ao TikTok, não ao ledger |
| Parte barrada segura as seguintes | `proxima_historia` (`bloqueadas`/`adiadas`) |
| "A conferir" (clique sem confirmação; e áudio mudo, com `estado` começando por `[audio] `) | `desfecho.a_conferir`/`marcas` + `postar._sem_a_conferir`/`_com_as_raizes`. Só a marca `[audio] ` sai sozinha (`desfecho.soltar_marca` com prefixo); a de clique só por conferência humana |
| Espera de processamento e confirmação | `youtube_web.py`, `tiktok.py`; veredito em `desfecho.classificar` |
| Texto que não entrou no campo (título, descrição, legenda) | `escrita.escrever` + `escrita.estado`, chamados por `youtube_web._escrever` e `tiktok._escrever_legenda`; foto da falha em `random_builds\outputs\_publicar\telas\` |
| Contador de estoque = funil da escolha | `postar._builds_prontos` (usado por `proximo_build`, `pendentes_por_canal`, `estoque_por_formato`) |
| Vídeo mudo: o arquivo inteiro **e cada trecho de luta** (`gameplay` do `edit_plan.json` → `_segments_<perfil>/seg_NNN.mp4`, antes da música) | `audio.veredito`: arquivo inteiro com `LIMIAR_MUDO_DB=-60` e `FRACAO_MUDA=0.5`; trecho de luta só pela média (-60 dB) e pela faixa ausente — silêncio entre golpes é normal. Usado pela fila e pelos contadores via `postar._audio_mudo`; medida lembrada por arquivo em `%LOCALAPPDATA%\neural-fights\audio_medido.json` |
| Luta muda em **todo caminho** (grade, recuperação, reserva, `main.py publicar`, bot, app) | `audio.barrar_luta_muda`, chamado de dentro de `youtube.publicar_como_configurado` e `tiktok.publicar`, antes de abrir o navegador; marca `[audio]` na lista "a conferir" daquele destino. A fila (rodada de verdade) marca no YouTube e solta sozinha quando o som volta (`audio.revisar_marcas`) |
| Imagem faltando / arquivo quebrado | `contos.publicar.qualidade.vistoriar_parte`; `v.pendencias` (builds) |
| História sendo renderizada | trava `historias__render__<fonte>` |
| Rodízio favela/normal/babaca | `_no_rodizio_dos_tipos` → `contos.publicar.tipos` |
| Válvula de qualidade: parte **retida** (veto da IA vencido, ou parecer só pela folha) só sai se o horário fosse ficar vazio | `postar._retencao` (lida de arquivo, não gasta `TENTATIVAS`), `proxima_historia` (retidos antes dos vetados e dos fora de ordem no último recurso); quando sai, `_marcar_retido` põe `[qualidade] ` na lista "a conferir" de cada destino onde saiu (não sai sozinha: quem confere é uma pessoa) |
| Desistência após 3 falhas | `_anotar_falha_no_tiktok`, `FALHAS_ATE_DESISTIR=3` |
| Cota do YouTube não mata o TikTok | `_e_limite_diario` + `try/except` por destino |

Só **uma** guarda falha fechada (erro ⇒ não publica): a lista "a conferir". As
outras, em dúvida, deixam passar — "não sei" nunca barra vídeo, mas vira erro no
diário.

## 3. As leis (decisões do dono)

- **Não ficar sem vídeo** (13/09) — mas **repetir é pior que não postar**
  (17/09). Quando brigam, o horário fica vazio e o log diz "a válvula fechou".
  A marca `titulo_repetido` no aviso hoje é *detector de escape*: deve ser zero.
- **Ordem da série é sagrada.** Fora de ordem só como último recurso no YouTube;
  no TikTok nunca, porque lá a recuperação é sempre extra.
- **Teto de 2 partes da mesma história/geração por dia**, no perfil inteiro —
  rodada normal, recuperação e reserva somadas.
- **Builds antigos (29/08–09/09, `CORTE_DO_TIKTOK`) são gordura, não atraso**:
  só saem no TikTok quando falta vídeo novo (`reserva_do_tiktok`).
- **Rascunhos do "Publicar mesmo assim" ficam** como gordura (15/09):
  `conferencia.rascunhos_aceitos` os tira do alarme. Não republicar.
- **Quem decide publicar de verdade é uma pessoa**: `postar_automatico: false`
  é para o botão do painel; a grade passa `postar=True` explícito.
- **O nome da conta é o destino**: `youtube_web` publica, `youtube` só lê.
- **Válvula de qualidade** (plano de 27/09, S2): retido = "a IA reprovou" ou
  "parecer só pela folha"; retido só sai quando não houver outro candidato
  para o horário, e quando sai fica marcado na lista "a conferir". Refina a
  de 13/09 ("depois de 3 rounds o vídeo tem que sair de qualquer forma"): o
  vencido continua saindo, mas só no lugar do horário vazio.

## 4. O que já quebrou

- **Rascunhos gêmeos** (22 no canal): clique sem confirmação não gravava linha, a
  fila reescolhia o mesmo vídeo, cada rodada deixava um rascunho. → `desfecho` +
  lista "a conferir", chamada **de dentro** do `tiktok.publicar`.
- **Repostagem de série inteira** (16/09: h3 e h16 em 11 dos 16 posts): o ledger
  era cego ao passado do TikTok. → `conciliar_tiktok.py`, teto por fonte e
  rodízio; só então as recuperações voltaram a ligar.
- **Ordem embaralhada**: a h3 saiu 7,8,9,10 e só então 1–6, porque a fila do
  TikTok era partida por data. → `_em_ordem_no_destino`.
- **Leitura do canal que perdia vídeo**: `_titulos_no_ar` contava o próprio vídeo
  publicado segundos antes ⇒ "título repetido" falso 4× em 16/09. → `menos=<id>`.
- **Contador que mentia**: `pendentes_por_canal` contava `catálogo − ledger`, sem
  pendências nem títulos repetidos ⇒ "2 dias de gordura" com `proximo_build()`
  devolvendo `None`. → mesmo funil da escolha.
- **Rascunho contava como publicação**: `url` guardava link *e* frase de estado.
  → `metricas.publicado(linha)` é a resposta única (`CONTRATO_DO_LEDGER = 2`).
- **Trava do ledger**: reescrita simultânea comia a linha nova. Quem acrescenta
  espera 120 s e grava mesmo sem trava (avisando); quem reescreve desiste.
- **Texto digitado contra o relógio** (20–27/09): 12 `Locator.type: Timeout
  30000ms` no YouTube e 22 "a legenda não entrou" no TikTok. Não era diálogo
  cobrindo o campo: o `type` tinha 30 s para o texto *inteiro*, uma ida e
  volta à página por letra. Com o League of Legends aberto (CPU 100%, i5 de 4
  núcleos): 126 ms/letra numa página vazia; ~1 s/letra no Studio. Sem jogo, no
  TikTok de verdade: 69 ms/letra (folga de só 1,8x). 13 das 17 falhas de
  25–27/09 caíram dentro de uma partida. A prova ficou nos rascunhos: o da
  h27 p01 tem 88 de 245 letras da descrição; o da h32 p04, o título cortado
  em "A Filha que Ficou — O grupo da f". → `escrita.py`, dois modos e uma
  leitura: **colar** (`insert_text`, 0,05 s para 1500 letras na mesma CPU;
  Enter e hashtag continuam tecla, 46 teclas em vez de 238) e **tecla a
  tecla sem o relógio único** (prazo de 180 s conferido entre palavras); e o
  campo é **lido de volta exigindo cada linha** (o critério antigo aprovava
  título cortado). **YouTube cola primeiro** — conferido pela API na rodada
  das 00:37 de 28/09: título e descrição idênticos ao catálogo nas duas
  publicações. **TikTok digita primeiro** — na mesma rodada, uma das duas
  legendas coladas perdeu dois parágrafos (o editor come o texto colado
  quando o Enter chega logo atrás; 85 de 230 letras no contador da tela) e
  o critério antigo de leitura a aprovou: a `historia_00031:celular:p06`
  ficou no TikTok sem "Eu escrevo e conto…" e "O que você faria…" —
  **corrigida em 28/09, 23:17** (decisão `legenda-h31-p06`) por
  `tiktok.corrigir_legenda(tiktok_id, texto)`: abre o editor do post
  (`/tiktokstudio/upload/post/<id>`, o lápis da lista), escreve com
  `_escrever_legenda`, exige o campo **igual** ao texto antes de salvar (no
  ensaio das 23:13 a digitação neste editor saiu embaralhada — o cursor
  pulou — e a leitura por linha pegou, mas não confere ordem) e prova pelo
  `desc` do `item_list` depois de salvar (`mesma_legenda`): post
  `7690426388284771592`, 230 caracteres, igual ao catálogo. O modo vai
  ao ledger (`prova[].escrita`, `prova[].legenda_modo`); a foto da falha, a
  `outputs\_publicar\telas\`.
- **Contador que mentia, de novo** (27/09): `estoque_por_formato` contava
  `catálogo − publicados` e dizia "build 7" (28 ÷ 3,75/dia) com zero builds
  publicáveis — 25 variantes B com título no ar e 3 com pendência. Era o
  defeito de 16/09 do `pendentes_por_canal`, de volta pelo segundo contador.
  → os dois contadores e a escolha passam por `_builds_prontos` (publicado,
  pendência, título no ar, áudio mudo). O áudio é lembrado por arquivo
  (tamanho + data) entre processos (`audio.medir_lembrado`); falha da
  ferramenta nunca é lembrada. A primeira versão lembrava dentro do
  `postar.py`, que o bot carrega do zero a cada relatório: os seis testes de
  `relatorios.metas` mediam 148 builds cada um e a suíte do bot passou de 900 s.
- **Luta muda debaixo da música** (medido pela parte Builds em 28/09): 38 de
  129 publicações desde 15/09 saíram com a luta calada, inclusive a
  `generation_00083:build:celular:B` das 00:45 (`seg_021` a -91 dB). A guarda
  de áudio media o arquivo *inteiro*, e a música cobria o buraco. → `audio.py`
  mede também cada trecho `gameplay` antes da mixagem, **só pela média**
  (a regra "calado em metade do tempo" tiraria da fila os duelos 00014,
  00016 e 00017, com golpes a -19/-21 dB e silêncio entre as trocas); a fila pula e marca
  `[audio]` na lista "a conferir" (só na rodada de verdade), e os dois
  publicadores barram antes de abrir o navegador — todo caminho passa por
  eles. Na fila de 28/09 (22 candidatos), 21 lutas entre -12,8 e -21 dB; só a
  estreia da `generation_00066` tem luta a -91 dB. A marca sai sozinha quando
  o re-render devolve o som (a medida é refeita porque o arquivo muda).
  Limite conhecido: a recuperação de *privados* do YouTube (`tornar_publico`)
  não passa pelo upload e não mede nada — o vídeo do canal pode ser de outro
  render que o do disco.
- **Veto vencido saía na hora** (até 28/09): `_parecer_da_ia` devolvia ""
  com "a IA reprovou, mas as rodadas de conserto acabaram; sai assim", e a
  parte ia ao ar na frente de qualquer outra. Na fila de 28/09, 03:05 (19
  partes): 10 vencidas, 7 vetadas, 1 só pela folha, 1 aprovada atrás de uma
  vetada — zero limpas. → válvula de qualidade (§2). Com esta fila ela leva
  a mesma parte (a h32 p05), só que marcada; a diferença aparece no dia em
  que houver parte limpa.
- **A recuperação do YouTube publicou 5 duplicatas** (27/09 20:5x → 28/09
  06:4x): `UlIc_DXyFa4`, `BM5BkPe56yo`, `EgganpfYcR0`, `y2H4ZzNIlEM` e
  `eopdwaZ0swA` voltaram ao ar com gêmeo **público** de mesmo título
  (`9U7UopBm3MM`, `XxOuPbJ2vtA`, `Jb7gIFumNQQ`, `xNZFFoMYQjk`,
  `UsDYI-pRqZ8`). O crivo do gêmeo procurava na playlist de envios (`UU…`),
  e ela não traz todos os Shorts públicos: no canal de builds, 145 públicos
  declarados, 139 vídeos na `UU` (115 públicos); a `UUSH` (Shorts) tem 145;
  a união, 169. → `recuperar.videos_do_canal` lê `UU` + `UUSH`, e
  `recuperaveis` para (`ListaIncompleta`) se a lista tiver menos públicos do
  que o canal declara. **Em 28/09, 21:58, as 5 voltaram a privado** (decisão
  `duplicatas-publicas-builds`), por `recuperar.recolher_duplicata(id,
  gemeo)`: só muda se, relido na hora, o gêmeo está público e tem a mesma
  `titulos.chave`; a troca é `recuperar.mudar_visibilidade` (o mesmo cuidado
  do `tornar_publico` com o `status`, e releitura). Conferido pela API: os 5
  `private`, os 5 gêmeos `public` — e os gêmeos são de **27/08** (o de
  `UsDYI-pRqZ8`, 13/09), anteriores às linhas. No ledger, as 4 linhas de
  `generation_00058/00060` (build e estreia) ganharam `estado:
  privado_de_proposito` (`publicado` segue verdadeiro) em 28/09, 23:59: sem
  isso, a próxima cura as chamaria de `rascunho_sem_gemeo` (gêmeo anterior à
  linha não conta) e a fila as republicaria — os gêmeos de 27/08 não estão
  no ledger, a guarda de título não os vê. Gravado com o filtro novo
  `curar_ledger.py --gravar --so-tipo privado_de_proposito
  --privada-de-proposito <video_id>…`, porque `--gravar` sozinho aplicaria
  junto as outras 244 curas pendentes (233 de formato, 5 `id_repetido`, 3
  `link_de_frase`, 3 `rascunho_sem_gemeo`), não decididas. Cópia:
  `publicados.jsonl.antes-cura-20260928_235920`; diff de 4 linhas.
- **Id do pedaço errado** (latente): o publicador perguntava ao canal o id
  pela linha do ledger, e com a parte cortada em dois Shorts o pedaço 2
  ganhava o id do 1 (e a capa do 2 ia para o 1). Nenhuma linha tem dois
  laudos desde que o laudo existe. → `recuperar.id_do_video` casa pelo
  índice do corte; a linha das histórias ganha `youtube_id` (primeiro
  arquivo) e `youtube_ids` (todos, na ordem), tirados dos laudos —
  `serie.registrar` tirava da URL, que pelo navegador é a frase.

## 5. O estado de hoje (27/09/2026)

Conferência da madrugada: **limpo** nos dois canais (1/1 builds, 27/27
histórias; zero fantasma, zero rascunho). Ledger: 244 linhas em builds, 320 em
histórias, nenhuma `(video_id, plataforma)` duplicada.

O assunto "parte longa vira dois Shorts `(1 de 2)`/`(2 de 2)`" foi commitado
em `42dced8` (27/09, 19:58); a pendência dele (o id de cada pedaço e os dois
ids na linha) fechou em `10142b1` (28/09).

**Problemas abertos** (atualizado em 28/09, 07:45)

- **(Fechado em 29/09)** **Três partes de histórias estavam só no TikTok** e o YouTube nunca ia
  recebê-las sozinho: `historia_00022:p03` (falhou 20/09), `00027:p01` (22/09)
  e `00032:p04` (27/09). A fila das histórias conta *qualquer* destino como
  publicado, e não existe "YouTube atrasado" para histórias. **A `h32 p05`
  saiu às 06:38 de 28/09 nos dois destinos** (`a5zqcwa-drY`): no YouTube a
  série tem p01–p03 e p05, sem a p04 (`_em_ordem_no_destino` só olha o
  TikTok). Decisão do Adrian (28/09): subir. O caminho é
  `python ferramentas/postar.py --so-youtube <video_id>` (com `--ver`, só
  confere): duplicata pelo ledger e pelo canal (público de mesma
  `titulos.chave`), lista "a conferir", trava de render e
  `vistoriar_parte` (áudio, prova de origem); grava a linha com `prova` e
  `youtube_id`, e a parte retida que sai vai à lista "a conferir".
  **Não** use `historias/main.py publicar <id> --youtube`: não passa por
  guarda nenhuma e grava sem `prova`. As três são retidas (a IA reprovou).
  Feito em 28/09: `00027:p01` → `-eM6_bHHzl0` (22:10) e `00032:p04` →
  `YqbQUrY1nuE` (22:14), públicos, título e descrição idênticos ao catálogo
  pela API, linhas 341/342 do ledger com `youtube_id`. **O Studio retomou o
  upload inacabado de 27/09**: `YqbQUrY1nuE` era o rascunho de título
  cortado e virou a publicação inteira (um só vídeo da p04 no canal). O
  rascunho `fn1_Sy3RpMk` da h27 p01 segue privado (decisão: manter).
  **A `00022:p03` subiu em 29/09, 01:07** → `CoDUmCFHAwc` (a de 28/09
  caiu com a rede antes do upload): público, título e descrição (com as
  hashtags, `descricao_completa`) idênticos ao catálogo pela API, único
  público com essa `titulos.chave`, linha 347 do ledger com `youtube_id` e
  `prova_ok`. O Studio **não** retomou o rascunho `pPACnX6RZ18` ("final
  celular p03", 20/09, descrição vazia): é um upload antigo, não inacabado
  da véspera como o da h32. Fica privado (decisão: manter). A série "A
  Ouvinte" está completa e em ordem de título no YouTube (p01–p03). As
  três partes da decisão `partes-so-no-tiktok` estão fechadas. A capa
  personalizada deu 403 (sem permissão de miniatura no canal de histórias;
  97 vezes no log, não é novo).
  **Efeito colateral medido**: a linha da h27 p01 (22:12) caiu na hora do
  relógio 22, e `publicou_neste_horario` (janela = hora do relógio, não
  `grade.slot`) fez a rodada das 22:37 achar que o YouTube das histórias já
  tinha saído; ela tentou levar a h27 p01 ao TikTok, onde já estava, e o
  horário ficou sem vídeo novo. → `--so-youtube` recusa quando a linha
  (gravada no fim, até `DURACAO_DE_UM_UPLOAD_MIN = 20`) cairia numa hora cuja
  rodada ainda não passou (`_horario_que_a_linha_tomaria`). A guarda da
  grade continua pela hora do relógio — trocar por `grade.slot` é conserto
  pendente, e mexe numa guarda.
- **NÃO usar `postar.py --recuperar --so historias`** para isso. O `--ver`
  de 28/09 lista 7 na fila, e o primeiro que ele tornaria público é
  `p-hNfT12nX8` — um *build* que caiu no canal de histórias em 31/08 (o
  outro é `FZsl4NDq6k4`). Também estão lá o rascunho da h27 p01 com a
  descrição cortada em 88 letras (`fn1_Sy3RpMk`), dois "Cinco anos pagando a
  luz de um estranho (Parte 1)" (`3Tb8mBy4jv0`, `MHHH0eDwMLo`, a mesma parte
  duas vezes) e as p03 das h5 e h4 (`VLTo6aSjXJ8`, `iR1K7Up0y4k`), que o
  ledger dá como publicadas. A recuperação do YouTube só é ligada para
  builds de propósito.
- **Rascunhos das falhas de escrita** (privados; decisão `rascunhos-e-privados`
  de 28/09: manter, não apagar): histórias `pPACnX6RZ18` ("final celular p03",
  20/09), `fn1_Sy3RpMk` (h27 p01, descrição cortada, 22/09) — o
  `YqbQUrY1nuE` (h32 p04) deixou de ser rascunho em 28/09, ver acima; builds `YUgFci9d_5Y` ("final celular",
  duelo_00010, 27/09), `_9d1f2LPYw4` e `Vt04zdE4o1k` (15/09). Nenhum deles
  entra na recuperação de builds (descrição vazia).
- **Variantes B**: em 27/09, 23:55, as 25 estavam fora da fila por título
  repetido; às 00:05 de 28/09, 18 já passavam — a parte Builds está dando
  título próprio a elas. A gordura de builds sai de 0 com isso. **3 por
  pendência** continuam (`generation_00085`, `generation_00077` e a variante).
- **`generation_00066:estreia:celular` é muda** (calada em 95% do tempo, 115 s
  de 121; os dois trechos de luta a -91 dB) e é barrada em toda rodada. Precisa
  re-render, não conserto de código. Desde 28/09 fica também na lista "a
  conferir" do YouTube, com o motivo, até o som voltar.
- **Luta muda já publicada**: as 38 de 15/09 a 28/09 (levantamento da parte
  Builds) estão no ar; a guarda só impede as próximas. O re-render espera o
  som novo aprovado pelo Adrian.
- **Duplicatas da `historia_00003` no canal**: 6 conteúdos no ar duas vezes (o
  vídeo inteiro *e* os dois pedaços). Medido em 17/09, **não reverificado hoje**.
  Nenhum código corrige isso — é limpeza no canal, decisão dele.
- **Aviso de variedade** (consertado em 28/09): "só N série(s) elegível(is),
  o dia precisa de 5" comparava com o dia inteiro a qualquer hora (164 no log,
  quase todos falsos à noite) e nem era avaliado sem fonte cheia. Agora
  `postar._avisar_variedade` compara a capacidade de hoje
  (`agenda.series_elegiveis` com o teto, menos o que cada série já levou
  hoje) com `_horarios_que_restam` (os não vencidos + o corrente se nada
  saiu nele, por `grade.slot`). Medido às 22:06: 4 séries, capacidade 6,
  restam 2 → sem aviso. Com zero séries e horário pela frente, avisa.
  Builds não são contados (`series_elegiveis` devolve `None`). O freio da
  criação continua na agenda (Histórias).

## 6. Como conferir, sem publicar nada

```
cd E:\projetos
python -m builds.publicar.conferencia --canal builds --dias 3     # ledger x canal (só lê a API)
python -m builds.publicar.conferencia --canal historias --dias 3
python ferramentas/curar_ledger.py                                # A SECO: só relata o que mudaria
python random_builds/main.py metricas                             # último dado salvo, sem rede
type outputs\postar.txt                                           # log das rodadas (enorme; leia o fim)
type random_builds\outputs\_conferencia\2026-09-27.json
```

Sem rede: leia os ledgers linha a linha com `json.loads` e conte por
`metricas.publicado(linha)`. `grade.horarios()`, `grade.vencidos()`,
`titulos.chave()` e `metricas.casar_ids()` são puros. Evite `postar.py --ver`:
decodifica mp4 e vários caminhos escrevem no `atividade.jsonl`.

## 7. O que NÃO fazer

- Não rodar `ferramentas/postar.py` sem `--ver`: **publica de verdade**.
- Não rodar `postar.py --recuperar --so historias` sem `--ver`: ele torna
  público o que o crivo aceita no canal de histórias, e lá isso inclui builds
  que caíram no canal errado e rascunho com descrição cortada (§5).
- Não voltar a escrever texto de vídeo com `Locator.type`: o prazo de 30 s é
  para o texto inteiro, e a máquina ocupada estoura (§4). Use `escrita`; o
  teste `test_escrita_no_campo_regressions` varre os dois publicadores.
- Não fazer trabalho pesado entre **:25 e :55** (as postagens automáticas).
- Não escrever no `publicados.jsonl` sem a trava `ledger__<canal>`, nem
  reescrevê-lo fora de `curar_ledger.py --gravar` (que faz cópia antes).
- Não apagar nem "consertar" `_tiktok_a_conferir.json` /
  `_youtube_a_conferir.json`: arquivo ausente significa "ninguém bloqueado", e
  isso **é uma afirmação**. Corrompido fica onde está, de propósito. A marca
  `[audio]` sai sozinha quando o som volta; a de clique, só por conferência.
- Não soltar marca por código sem prefixo: `desfecho.soltar_marca` recusa
  prefixo vazio, porque "" casaria com a marca de clique sem confirmação.
- Não reabrir a válvula de título repetido nem mexer em `TETO_POR_FONTE_NO_DIA`,
  `CORTE_DO_TIKTOK`, `RECUPERACAO_LIGADA`, `RESERVA_LIGADA`: são decisões dele.
- Não criar um segundo critério de "publicado", de "título igual" ou de "horário
  da grade" (cada duplicata dessas já custou um defeito), nem usar a hora do
  relógio onde cabe `grade.slot()`.
- Não perguntar ao Gemini na hora de postar (`PEDIR_PARECER_NA_POSTAGEM=False`).

## Contratos com outras partes

| Arquivo / recurso | Quem manda | Quem mais usa |
| --- | --- | --- |
| `random_builds/outputs/_publicar/publicados.jsonl` | **publicação**, só por `metricas.acrescentar_ao_ledger` | conferência, métricas, auditoria, relatórios do bot, app |
| `historias/outputs/_publicar/publicados.jsonl` | **publicação**, via `contos.publicar.serie.registrar` | idem |
| `builds/grade.py` | **publicação** | agenda de histórias, painel flutuante, `remoto/relatorios.py`, auditoria, `youtube_web` |
| `_tiktok_a_conferir.json`, `_youtube_a_conferir.json` | **publicação** (`desfecho`), sob a trava `<plataforma>_a_conferir` | app e bot leem para mostrar pendência |
| `_tiktok_desistencias.json` | **publicação** | — |
| `historias/.../prioridade.json` | **o Adrian** (pedido manual) | publicação só lê |
| `atividade.jsonl` (diário) | **todos escrevem**, ninguém é dono | bot avisa no celular, apurador investiga erro, página de confiabilidade soma |
| travas `ledger__<canal>`, `<plataforma>_a_conferir` | **publicação** | `historias__render__<fonte>` é da parte Histórias (aqui só se lê) |
| `config/publicacao.json` (`grade.mistura`, `visibilidade`, `postar_automatico`) | **o Adrian** | publicação e painel leem |
| `contos.publicar.{catalogo,serie,qualidade,parecer,tipos}` | parte **Histórias** | publicação chama |
| `builds.publicar.catalogo` (`pendencias`, `origem`, `capa`) | parte **Builds** | publicação chama |
| `builds.contas` (conta ativa por serviço/canal) | parte **Contas** | publicação lê para dizer o destino |

Regra acima de tudo: **um escritor por arquivo**. Se outra parte precisa mudar o
ledger, ela pede à publicação — não escreve por conta própria.
