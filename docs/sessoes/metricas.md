# Métricas e conferências

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/metricas/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (29/09/2026) · “29/09 01:19, pela Mesa de comando: força total, até 2 agentes” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Outro (comente) (28/09/2026) · “28/09 21:48, pela Mesa de comando: passou de 100% da sessão, para tudo” `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Só quando eu pedir (28/09/2026) · “28/09 22:26, pela Mesa de comando: força total só quando eu pedir” `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`
- ✅ **Limpeza do disco (C: com 9 GB livres)** — Só o seguro (~1,2 GB) (29/09/2026) `limpeza-do-disco`
- ✅ **E: com 17 GB livres — o cache do Google Drive (186 GB)** — Abrir o Google Drive e deixar ele terminar e limpar sozinho (recomendado primeiro) (29/09/2026) `limpeza-do-disco-e`

<!-- decisoes:fim -->

Documento de passagem. A fotografia do §2 é de 27/09/2026; o que foi medido
de novo em 28/09 (madrugada e noite) está com a data e a hora. Onde um número da fotografia
não reproduziu, está dito. O que eu não medi está marcado como **não medi**,
nunca preenchido por suposição.

## 1. Onde cada número mora

| Número | Mora em | Medido ou suposto |
| --- | --- | --- |
| views/likes/comentários | Data API v3 → `*/outputs/_metricas/<youtube_id>.json` | MEDIDO |
| % assistido e curva | Analytics API (`yt-analytics.readonly`) → mesmo arquivo | MEDIDO |
| origem do tráfego | Analytics, `dimensions=insightTrafficSourceType` | MEDIDO, **não fica em disco** |
| inscritos / vídeos / views do canal | Data API `channels?part=statistics` | MEDIDO, **nenhum código consulta** |
| views/dia, "dias no ar" | `metricas.views_por_dia` (piso de 1 dia) | derivado |
| TikTok (views, tempo, curva, tráfego) | JSON do Studio → `*/outputs/_metricas_tiktok/*.json` | MEDIDO |
| o que saiu, quando, visibilidade | os dois `publicados.jsonl` | MEDIDO |
| ledger × canal | `*/outputs/_conferencia/<dia>.json` | MEDIDO |
| a coleta da noite deu certo? | `random_builds/outputs/_metricas/_atualizado_em.json` (marca do dia, por parte) | MEDIDO |
| noite sem conferência, canal parado, `youtube_id` | `builds.publicar.sinais` (a conta), gravado na ficha da conferência | MEDIDO |
| "dias de estoque" | `ferramentas/postar.py: estoque()` | **SUPOSTO** (divisão; ver §5) |

Dois canais, dois mundos de arquivo: builds em
`E:\projetos\random_builds\outputs\`, histórias em
`E:\projetos\historias\outputs\`. O diário é um só, fora do repo:
`%LOCALAPPDATA%\neural-fights\atividade.jsonl`.

Comandos (de `E:\projetos`, salvo onde dito):

```bash
cd random_builds && python main.py metricas             # só LÊ o que está salvo
cd random_builds && python main.py metricas --atualizar # vai à API e GRAVA
python -m builds.publicar.conferencia --canal builds --dias 1
python -c "from builds.publicar import tiktok_metricas as t; print(len(t.carregar_salvas('historias')))"
```

`builds` e `contos` são importáveis de qualquer pasta (instalação editável);
`remoto` e `panorama` só de `E:\projetos`. Os relatórios e a checagem rápida
estão no §6.

## 2. A fotografia de 27/09/2026, e como refazer cada medida

Canal (uma chamada, `channels?part=statistics&mine=true` com
`metricas._token(canal)`): **builds 3 inscritos, 135 vídeos, 7027 views**;
**histórias 18, 176, 4317**. A fotografia da manhã dizia 133/7004 — o número
anda durante o dia, então sempre anote a hora.

Mediana de views. Há **duas** e elas divergem: contando todos os uploads e
tratando vídeo sem linha na Analytics como 0, dá **17 (builds) e 1
(histórias)** — é a mediana da fotografia (18 e 2). Contando só quem tem
linha, dá 25,5 e 3,5. Diga sempre qual das duas.

Desde 18/09 (vídeos publicados de 18/09 em diante): builds **média 47,8**,
n=70 — confere com o 47. Histórias deu **38,9** (mediana 7), e não 25: esse
número da fotografia **não reproduziu**; não descobri o denominador dele.

Por formato — uma chamada só, e é a medida que decide a Onda 15:

`GET metricas.API_ANALYTICS` com `ids=channel==MINE`,
`startDate=2026-08-01`, `endDate=2026-09-27`,
`metrics=views,averageViewPercentage`, `dimensions=video`, `sort=-views`,
`maxResults=200`, e `Authorization: Bearer {metricas._token(canal)[0]}`.

O formato vem do `origem` do ledger, casado pelo `youtube_id`. Medianas:
**duelo 51,5% / 78 views (n=5)**, **build 25,4% / 37 (n=53)**, **estreia
10,7% / 25 (n=35)**, torneio 19,9%/25 (n=1). Reproduz exato. Mas **33 dos 127
vídeos ficaram sem formato**, porque a linha do ledger não tem `youtube_id`.

**Duelo: 51,5% ou 34,0%?** (28/09). O agente de builds mediu no retrato local
(`comparar_formatos` sobre `_metricas/*.json`, arquivos de 27/09 20:07)
**34,0% de retenção média e 44 views medianas, n=7**. Os dois números medem
coisas diferentes, e o de 34,0% está errado:

- n=7 contra n=5: dois dos sete duelos em disco (`ReZ81HQB1pU`,
  `YS7PiOSlmBc`, de 12/09) estão **privados** no canal — rascunhos do
  "Publicar mesmo assim", com 0 view. A consulta por `dimensions=video` só
  devolve linha de vídeo **visto**, então eles nunca entraram no 51,5%.
- No disco eles entraram com **0% de retenção**: para vídeo sem view a
  Analytics por vídeo devolve a linha `[0, 0, 0]`, e `retencao()` a gravava
  como medida. Retenção de zero espectadores não existe.
- 34,0% é **média** dos 7 com os dois zeros; a mediana dos mesmos 7 é 36,3%.
  Tirando os dois privados: **mediana 51,45%, média 47,5% (n=5)**, e views
  mediana **80** (Data API, vida toda) — o 78 era a contagem da Analytics
  dentro da janela 01/08–27/09.

Conserto (28/09): `comparar_formatos` deixa privado de fora (conta em
`privados_fora`) e só faz média de retenção de vídeo com view; `retencao()`
trata a linha de zeros como "sem dado". O número certo **com o disco de
27/09** é 51,45% / 80 (n=5). Mas o ledger já tem **11 duelos no YouTube com
id**, e o disco só tem 7: os quatro mais novos ficaram sem medida porque a
coleta de builds falhou na madrugada de 28/09. **O número de hoje** (coleta
refeita às 08:13 de 28/09, código novo): 11 duelos em disco, 9 públicos, 5
com retenção — **mediana 51,5%, média 47,5% (n=5)**, views mediana **106
(n=9 públicos)**. Os 4 públicos sem retenção são os mais novos: a Analytics
ainda não tem linha para eles (não é 0%).

Tráfego (mesma chamada com `dimensions=insightTrafficSourceType`, sem
`video`): builds **SHORTS 4499 (64%) + YT_SEARCH 2399 (34%)**; histórias
**SHORTS 93%**. O "99% vem do feed de Shorts" **só fecha somando busca**
(64+34) — e desde 18/09 a busca passou o feed em builds (55% x 43%). Vale
como aviso: em builds, hoje, um terço da audiência é busca.

TikTok (só disco, nada de rede): 257 arquivos (builds 101, histórias 156),
mediana **2 em builds e 1 em histórias**, soma 16.987 views. O maior vídeo
tem 12.568 — **86% das views do canal de histórias** e 74% do total dos dois.
Refazer: `tiktok_metricas.carregar_salvas(canal)` e mediana do campo `views`.

## 3. As conferências que existem

**Relatórios do bot** (`remoto/relatorios.py`, horários em
`%LOCALAPPDATA%\neural-fights\remoto.json`):

- `metas` **21:00** — o que saiu hoje (hora e canal), série de 7 dias, vídeos
  não públicos, estoque em dias. Olha para fora.
- `funcionamento` **09:00** — fábricas do diário (passadas, erros, mediana
  emparelhada por pid), 5 últimos erros, Agendador do Windows, OAuth dos dois
  canais. Olha para dentro.
- `confiabilidade` **22:30** — prometido × provado, válvula aberta, vídeo em
  um destino só e, desde 28/09, **grade em falta, noite sem conferência,
  canal parado, `youtube_id` faltando e métrica velha**. Só formata; o número
  é de `panorama.confiabilidade`, que é o mesmo que a página do painel lê. É
  por ele que "o relatório diário acusa métrica velha" sem tocar em
  `remoto/relatorios.py` (que é do app e bot).
- `auditoria` — **sem horário**: é pedido. Decodifica mp4, leva segundos.

**Conferência noturna** (`builds.publicar.conferencia.conferir_tudo`, na
rodada de madrugada): baixa os uploads reais do canal e compara com o ledger
numa janela de 3 dias. Acusa `fantasmas` (ledger afirma, canal não tem),
`rascunhos` (privado no canal), `orfaos_privados`, `so_sd`, `duplicados`,
`mesmo_video`. Suja → linha de erro no diário, que vira aviso no Telegram.
`conferir` é pura quando as duas listas são injetadas; só `buscar_no_canal`
toca a rede.

**O que ela passou a acusar em 27/09** (commit `a973437`, e o conserto da
noite de 27/09): a intenção também entra na conta. Déficit acende um erro
próprio, separado de `sujo` — ledger coerente e grade cumprida são perguntas
diferentes.

**O dia conferido é o DIA DE GRADE que acabou de fechar**, não o do
calendário: de 06:37 até 00:37 do dia seguinte. Nada disso está escrito no
código — o dia de grade abre no horário depois do **maior buraco** da grade
(a madrugada, 00:37 → 06:37) e sai de `grade.horas_da_plataforma` e
`grade.minuto`; `conferencia.dia_de_grade_fechado(agora)` diz qual é. Às
01:28 e às 05:20 de 28/09 é o de 27/09; às 14:00 de 28/09 continua o de 27/09
(o de 28 ainda não fechou); às 00:30 de 28/09 é o de 26/09. Um post das 00:39,
ou uma recuperação das 06:34, paga o horário das 00:37 do dia anterior.

Por que mudou: o `a973437` contava o dia do calendário, e a conferência roda
de madrugada (01:28, 03:20, 04:20 e 05:20 em 27/09). Às 05:20 o único horário
vencido do dia é o das 00:37, então **um dia 10/10 dava déficit 9 toda
noite**. Medido com a versão do HEAD e o relógio às 05:20 de 28/09: 10/10 →
déficit 9; a nova dá 0. Dia 0/10: déficit 10 nas duas.

Campos da ficha (nenhuma em disco os tem ainda; a primeira é a de 28/09):

- `dia` — o dia em que a ficha **rodou** (é o nome do arquivo).
- `dia_de_grade`, `janela_da_grade` (`["2026-09-27T06:37", "2026-09-28T00:37"]`).
- `slots_da_grade` — `len(grade.horas_da_plataforma())`, hoje 10.
- `horarios_cumpridos` — **horário distinto** com vídeo que o canal confirma
  **público**. Linha não é horário: duas no mesmo horário pagam um, o mesmo
  vídeo em duas linhas paga um, rascunho no canal não paga, fantasma não paga.
  Sai do ledger inteiro, não da janela de `--dias`.
- `horarios_em_falta` — lista `"HH:MM"`, na ordem do dia de grade.
- `linhas_no_dia_de_grade` — quantas o ledger afirma. Separa "não publicou"
  (0 linhas) de "publicou e não chegou" (linhas sem horário cumprido).
- `deficit` (= `len(horarios_em_falta)`) e `grade` ("cumprida"/"em falta").

O que o alarme vai encontrar, lado do ledger (só disco, sem rede; é o teto do
que o canal pode confirmar), YouTube, por dia de grade, medido às 23:05 de
27/09: **builds 0, 0, 0, 1, 0, 0** linhas de 21 a 26/09; **histórias 10, 9,
9, 10, 7, 9**, sempre um horário por linha. O de 27/09 ainda não tinha
fechado (builds 3, histórias 5). Refazer: `_horario_da_grade` +
`_dia_de_grade` sobre `metricas.publicados(canal)`. A confirmação pelo canal
**não medi** (é rede).

Primeira rodada real (01:35 de 28/09): **builds 5/10, histórias 7/10** no dia
de grade 27/09, e os dois acenderam. Em builds faltaram 06:37, 09:37, 12:07,
15:37 e 21:37; em histórias, 17:57, 21:37 e 22:37.

**Uma vez por dia de grade** (28/09). A conferência roda até quatro vezes por
noite e cada rodada escrevia a sua linha: em 26/09 o mesmo alarme de
histórias saiu às 01:32, 04:20 e 05:20. Agora a ficha guarda `avisos` —
`grade: {dia_de_grade, deficit}` e `noite: {dia, erro, eventos, cobertura,
noites}` — e a rodada seguinte herda da anterior (`ultima(canal)`, lida
**antes** de gravar). A grade só avisa de novo se o déficit **crescer** no
mesmo dia de grade; dia de grade novo avisa sempre. A ficha antiga, sem
`avisos` (a das 01:35 de 28/09), conta como já avisada, porque aquela versão
avisava todo déficit. O alarme de ledger `sujo` continua a cada rodada — não
foi pedido.

**Conferência que falha vira alarme** (28/09). Até então a exceção (token,
rede) só virava ficha com `erro`: a página via, o celular não. Agora é uma
linha de erro da fábrica `conferencia`, uma por noite para o mesmo tipo de
erro. A ficha de erro também carrega `avisos`, `rodadas` e `sinais`.

**Pedaços da parte cortada** (28/09): desde `10142b1` a linha de histórias
cortada em dois Shorts guarda `youtube_ids`. A conferência passa a ler os
outros ids: o pedaço 2 deixa de ser "órfão", e o pedaço privado vira
rascunho **da linha** (`pedaco: true`) em vez de "privado fora do ledger". A
grade continua pagando um horário por linha. Ainda aparece como `duplicados`
(o `titulos.chave` tira o corte), o que não suja o veredito.

### A lista do canal: `UU` + `UUSH`, e o número que o canal declara (28/09, noite)

A playlist de envios (`UU`) **não traz todos os Shorts**. `metricas.enviados`
— que alimenta a conferência, a reconciliação e o `curar_ledger` — lia só
ela. Medido com o código antigo e o novo, só leitura, 28/09:

| canal | hora | leitura | vídeos | públicos | canal declara | chamadas HTTP |
| --- | --- | --- | --- | --- | --- | --- |
| builds | 21:55 | só `UU` (antiga) | 178 linhas, **143 ids** | **125** | 151 | 9 |
| builds | 22:13 | só `UU` (antiga) | 178 linhas, 143 ids | **120** | 146 | 9 |
| builds | 22:12 | `UU`+`UUSH` (nova) | **170** | **147** | 146 | 23 |
| histórias | 22:13 | só `UU` (antiga) | 196 | 187 | 187 | 9 |
| histórias | 22:12 | `UU`+`UUSH` (nova) | 196 | 187 | 187 | 25 |

(O declarado caiu de 151 para 146 entre 21:55 e 22:12 — a volta a privado
das cinco duplicatas, pela publicação.) Em histórias a `UU` vem completa; em
builds a leitura antiga ficava **cega para 26 públicos** e ainda repetia 35
linhas. As chamadas: `channels` 1, `playlistItems` 14–16 (duas listas, e
`_todos_os_ids` passa de novo até a lista parar de mexer — no mínimo duas
passadas), `videos` 8 (4 de `enviados`, 4 de `estatisticas`). Uma noite de
quatro rodadas nos dois canais ≈ **200 unidades** das 10.000 do dia.

O que mudou:

- `enviados` lê a união pela **mesma** função da recuperação
  (`recuperar._ids_do_canal`, de `6fa9ad6`) — não é cópia — e devolve
  `ListaDoCanal`, que leva `declarados` (`statistics.videoCount`, na mesma
  chamada do `channels`). Sem teto: o de 200 ia cortar histórias (196).
  Traz `privacidade`. `publicado_em` passou a ser o do vídeo; o do item da
  playlist era igual nos 200 medidos.
- `metricas.conferir_lista(lista)` → `{videos, publicos, declarados,
  completa, motivo}`. Público **distinto** contra o declarado; `None` só
  para lista que não veio do canal (dublês). Canal que não diz o número
  (`-1`) ou credencial sem canal: **nunca** completa.
- Conferência com lista curta: veredito **`incompleta`** — nem `limpo`, nem
  `sujo` por fantasma (ausência não prova nada com vídeo faltando). O que foi
  **achado** (rascunho, privado fora do ledger) continua sujando. A grade
  continua contada: vídeo faltando só a faz dar menos. A ficha leva `lista`;
  alarme próprio no diário **uma vez por noite** (`avisos.noite.lista`);
  panorama acusa "sem veredito do ledger"; a linha de comando sai com 1.
- Reconciliação com lista curta **acusa no log e segue**: casar só dá id a
  vídeo achado, com hora e dono conferidos; parar derrubaria a coleta.

**O que ainda não fecha:**

- às **21:58** a união deu **149 públicos contra 151** — teria acendido. Um
  público, `V61uLqU_PfI` (31/08), não está em **nenhuma** das duas listas
  (achado cruzando com os ids do ledger). O número declarado é piso, não
  prova: lista com público a mais e outro faltando passa.
- **privado que falta é invisível**: `videoCount` só conta público. Oito
  privados do ledger de builds (12 a 14/09, entre eles `ReZ81HQB1pU` e
  `YS7PiOSlmBc`) não estão em nenhuma lista, e dois ids do ledger
  (`FZsl4NDq6k4`, `p-hNfT12nX8`) o `videos` nem devolve. Para eles a
  conferência continua cega.
- as páginas da `playlistItems` passam por `recuperar._get` e **não entram em
  `metricas.CHAMADAS`**: na marca da coleta, a reconciliação conta só
  `channels` + `videos`. O número acima foi medido por fora (contando o
  `requests.get`). Contar ali é uma linha em `recuperar.py`, que é da
  publicação.

Refazer (só leitura, sem gravar ficha):
`python -c "from builds.publicar import conferencia as c, metricas as m; l=c.buscar_no_canal('builds'); print(m.conferir_lista(l))"`.

**`rodadas`**: as horas em que a ficha do dia foi gravada. Sem isso, o botão
do painel às 14:00 regravava a ficha e apagava o rastro de que a noite não
rodou.

**Gravação de uma vez** (28/09): `salvar` grava em `<dia>.json.tmp` e troca
com `os.replace`. A página lê a ficha a cada 3 s e a madrugada a regrava a
cada rodada; escrever por cima deixava o leitor ver JSON pela metade
(`ultima()` → `{}` → "nunca rodou").

### Os sinais de ausência (`builds/publicar/sinais.py`, 28/09)

Todo alarme reagia a evento, e ausência não escreve linha. Três contas
puras, as mesmas para a conferência (linha no diário, uma vez por noite) e
para o panorama (relatório das 22:30 e painel):

| Sinal | Conta | Acende quando | Caso vazio |
| --- | --- | --- | --- |
| noite sem conferência | a última ficha contra `noite_esperada(agora)` — a noite do dia D acaba quando o dia de grade de D abre (06:37) | a noite esperada não tem ficha com rodada **antes das 06:37** | nenhuma ficha = "nunca rodou" (acende) |
| canal parado | eventos `inicio/ok/erro` do canal nas últimas 24 h, **fora** das fábricas que observam (`conferencia`, `metricas`, `apurador`) | menos eventos que horários da grade na janela lida (10 em 24 h) | diário vazio ou menos de 12 h lidas: `None`, não acende |
| `youtube_id` | publicações do YouTube de 7 dias atrás até 24 h atrás (a reconciliação só roda de madrugada) | cobertura abaixo de 90% | nenhuma linha na janela: `None`, **não é 100%** |

Por que tirar as fábricas que observam: a conferência escreve dois erros por
noite justamente sobre o canal parado. Contados, fariam o morto parecer vivo.
Por que o diário inteiro: `atividade.recentes()` lê só as últimas **1200
linhas**, e histórias escreveu 1103 eventos em 27/09 — a janela de 24 h saía
cortada sem aviso. `sinais.ler_diario()` lê o arquivo todo (a poda o mantém
abaixo de 4000 linhas) e devolve `None` quando não abre.

Medido com os dados reais às 03:22 de 28/09 (código novo, só leitura):
**builds 43 eventos de trabalho em 24 h, histórias 159** (o diário cobre 24 h;
mínimo 10). `youtube_id` de 21 a 27/09: **builds 1/1, histórias 54/54**.
Nenhuma noite faltando. Os casos que teriam acendido: a noite de 21/09 (sem
ficha nos dois canais), builds com **0 eventos em 25 e 26/09**, e histórias
de 18 a 27/09 com a reconciliação morta.

### A coleta da noite: marca por parte (28/09)

`metricas.atualizar_uma_vez_por_dia` era "rode `atualizar_tudo` e grave a
marca", com falha ou sem. Medido nos logs `auto_*.txt`: de **17 a 28/09 o
YouTube falhou onze noites seguidas** (SSLError em 17, 19 e 28/09; NameError
de 18 a 27/09); em 21/09 a coleta nem rodou. A marca foi gravada todas as
noites, a rodada seguinte não tentava de novo, e o log dizia "metricas da
noite atualizadas".

Agora a coleta tem quatro **partes** (`builds`, `builds_tiktok`, `historias`,
`historias_tiktok`), e a marca guarda uma ficha por parte: `estado`
(`ok`/`vazio`/`erro`), `videos`, `quando`, `duracao_s`, `erro`, `tentativas`,
`ultimo_ok` e, no YouTube, `chamadas`. **Só a parte que deu certo fica feita
na noite**: a que falhou vira uma linha de erro da fábrica `metricas` (o
apurador a investiga — foi um NameError de código que durou dez dias), uma
por noite para o mesmo tipo de erro, e a próxima rodada tenta **só ela**. A
marca antiga (sem `partes`) é lida: parte com 0 vídeos conta como não feita.
`vazio` (nada para medir) é diferente de `ok` e de `erro`. `completa` diz se a
noite fechou; `atualizar_uma_vez_por_dia` só devolve `True` (e o log só diz
"atualizadas") quando fecha.

**Chamadas contadas** (`metricas.CHAMADAS`, por `_get` e `_token`): `data`
(Data API, 1 unidade cada, de 10.000 por dia), `analytics` (cota própria) e
`token` (o refresh do OAuth). Uma queda de **conexão** (SSLError, timeout)
tem uma segunda tentativa depois de 5 s — inclusive no refresh do token, que
derrubou a coleta em 17 e 19/09; resposta ruim do Google não é repetida. Custo esperado de uma parte
do YouTube: 1 `channels` + até 4 páginas de `playlistItems` + 1 `videos` a
cada 50 ids na Data API, e 2 consultas por vídeo na Analytics. Desde a noite
de 28/09 a reconciliação lê `UU`+`UUSH` (14–16 páginas, que **não** entram na
marca — ver "A lista do canal" acima) e 1 `videos` a cada 50. **Medido**
(builds, 08:13 de 28/09): **8 `data`, 226 `analytics`, 2 `token`, 405 s**
para 126 linhas do ledger / 121 vídeos. Histórias com o contador novo:
**não medi** (a próxima noite grava).

A marca conta **vídeo, não linha** (`dd9b122`): `videos` são ids distintos
(um arquivo por id) e `linhas` as linhas do ledger. Antes dizia 126 com 121
arquivos em disco, porque há linhas repetidas para o mesmo id.

### O TikTok: a lista inteira (28/09)

`tiktok_metricas.coletar` parava em 50 ou 60 posts toda noite (17 a 28/09):
**60 de 119 envios casados em builds, 50 de 165 em histórias**. Medido no
Studio: `item_list` é um `POST /tiktok/creator/manage/item_list/v1/` com
corpo `{"cursor", "size"}` — 50 na primeira página, 10 nas seguintes — e a
resposta traz `cursor` (onde a próxima começa) e `has_more`. A lista mora num
DIV com rolagem própria; `mouse.wheel` sem o ponteiro em cima dele não pede
página nenhuma. E a cada rolagem o Studio repede a primeira página
(`cursor 0`, `has_more=true`), que não pode apagar a notícia de que acabou.

Agora: `Lista` guarda a resposta de **maior** `cursor`; `ler_a_lista` rola o
DIV por JS (sem nome de classe — as do Studio são geradas) alternando com a
tecla End, e diz **por que** parou: `completa` (`has_more=false`),
`suficiente` (já cobre o envio mais velho do ledger), `parada` ou `tempo`
(estas duas = lista INCOMPLETA, gravada na marca e alertada no panorama).
Lista vazia e zero casados viram **falha**, não "0 vídeos".

Prova (só leitura, perfil verdadeiro, 28/09 08:04–08:09): **builds 130 posts
(`suficiente`) → 120/120 envios casados; histórias 190 posts (`completa`) →
163/166**. Os 3 de histórias sem par (11, 12 e 16/09) são envios que o ledger
tem e o Studio não lista — **não investiguei**. A primeira noite com o código
novo é a de 29/09.

### As tarefas do Agendador que o panorama confere (28/09)

`panorama.recursos._agendador` (a tela Recursos e o relatório `auditoria`)
conferia `Historias_auto_HH`, `NeuralFights_postar_HH` e o bot. As cinco
`NeuralFights_gerar_01` a `_05` (01:02 a 05:02, geração de duelos, criadas em
27/09) entraram, lidas de `builds.pipeline.noite.carregar()["horas"]` e
nomeadas por `tarefas_noite.nome_da_tarefa` — sem lista fixa; com `ativo:
false` não são cobradas. O relatório `funcionamento` das 09:00 tem a sua
própria lista em `remoto/relatorios.py` (app e bot) e **ainda não as
confere**.

`carregar_salvas('builds')` lia a própria marca como se fosse vídeo: **95
registros, um sem id** (medido em 28/09). Agora pula a marca **pelo nome
exato** — id do YouTube pode começar com `_` (`_bHp95XZpgc`).

## 4. As conferências que faltam, e o número que deveria acender

| Falta | Hoje, medido | Acende quando |
| --- | --- | --- |
| estoque por formato zerado | `estoque_por_formato` diz `build: 7 dias`, e os 25 pendentes de build estão **todos** barrados por título | formato com 0 pronto de verdade |
| colisão de título | dos 33 pendentes de builds, **25 barrados (76%)** | fila barrada acima de ~30% |
| publicação não pública no ledger | **5** (4 builds, 1 histórias) | qualquer uma acima de zero |

Nenhuma dessas tem alarme hoje (as duas primeiras são da publicação). Saíram
desta tabela em 28/09, porque agora existem (§3): **canal sem evento em 24 h**
e **cobertura de `youtube_id`** — que, aliás, mudou: histórias estava em
61/158 (39%) em 27/09 e foi a **156/161 (97%)** na madrugada de 28/09, quando
a reconciliação voltou a rodar; builds 125/133 (94%), com as linhas sem id em
16 e 17/09.

O caso que provava a falta — *a coleta do YouTube ficou dez dias quebrada e
ninguém soube* — tinha duas metades. O NameError (`titulos` sem import) foi
consertado por outra sessão em `42dced8`; histórias voltou a coletar às 01:29
de 28/09 (**156 vídeos**, marca e disco concordando: 156 arquivos com
`atualizado` de 28/09). A outra metade — falha engolida, marca gravada, log
dizendo "atualizadas" — é o conserto da marca por parte (§3). Na mesma noite
builds falhou por SSLError às 01:20 e a marca gravou `builds: 0`: é o caso que
a versão nova repete na rodada seguinte.

## 5. Armadilhas medidas

- **Taxa 1,0 com canal parado.** Builds passou 21–27/09 quase sem publicar e
  a conferência dizia "limpo" toda noite: quem não afirma nada tem ledger
  coerente. Foi o que o `deficit` de 27/09 conserta — e é a razão de nunca
  medir o ledger contra ele mesmo. Com o dia de grade, o builds deve acender
  na noite de 28/09 (3 linhas no ledger em 27/09, às 23:05).
- **`metas` contava linhas, não horários.** Imprimiu
  `✓ histórias: 11/10 horários` com **5 do YouTube e 6 do TikTok**, contra uma
  meta de 10 por plataforma. Consertado em `9d09759` (placar por canal e
  plataforma, slot distinto). Resta uma borda, medida: ele fatia o dia pelo
  **calendário** e usa `grade.slot`, então um post das 00:10 de 28/09 (a
  recuperação das 23:37 de 27/09) entra em 28/09 como slot 23 — paga o 23:37
  de um dia em que ele ainda não aconteceu. **Não consertado** (é de
  `remoto/relatorios.py`).
- **Dia do calendário numa conferência de madrugada.** O `deficit` de
  `a973437` contava o dia que tinha acabado de começar e dava déficit 9 num
  dia 10/10. Um medidor que acende sempre é tão surdo quanto um que nunca
  acende. Conserto: dia de grade (§3).
- **Painel com ✓ para grade furada.** Até 28/09 `panorama.confiabilidade` e a
  página Confiabilidade só liam `veredito`: a ficha `limpo` com `grade` "em
  falta" aparecia como `✓ 5/5`. Agora o resumo leva a grade, o alerta diz os
  horários que faltaram, e a linha do cartão é `builds: ✕ grade 5/10 · ledger
  ✓ 5/5` — o ✓ exige as duas coisas.
- **Marca gravada com a coleta morta.** Onze noites (17 a 28/09) com o YouTube
  falhando e a marca dizendo "feito". Marca que se grava sem olhar o
  resultado é medidor verde. Conserto: marca por parte (§3).
- **O observador contado como trabalho.** Contar os alarmes da conferência
  como "evento do canal" faria o canal parado parecer vivo — ela escreve
  sobre ele duas vezes por noite. `sinais` tira `conferencia`, `metricas` e
  `apurador`, e tira `log` (2126 linhas do `estudio` em três dias).
- **`atividade.recentes()` lê só 1200 linhas.** Num dia de histórias (1103
  eventos em 27/09) uma janela de 24 h lida por ali sai cortada, sem aviso.
  Para janela de tempo, `sinais.ler_diario()`.
- **Perfil do TikTok de builds mora DENTRO do repositório**
  (`random_builds/.browser_profile/tiktok`). Rodando o código de uma
  worktree, `perfil_da_conta("builds")` aponta para a pasta da worktree, o
  Chrome cria um perfil vazio e a tela é de login — parece logout e não é
  (28/09, 07:58). Para provar coisa no navegador a partir de worktree, troque
  a raiz do caminho pela de `E:\projetos`.
- **Id do YouTube que começa com `_`.** `_bHp95XZpgc.json` é vídeo. Filtro por
  "começa com sublinhado" para pular a marca jogava um vídeo fora — medido
  antes de ir ao ar (93 em vez de 94).
- **"Dias de estoque" conta vídeo, não vídeo publicável.**
  `estoque_por_formato` não aplica pendências nem título repetido: diz
  `build: 7 dias` quando o real é 0. `estoque()` (que passa pelo mesmo funil
  de `proximo_build`) diz **builds 0 dias, abaixo do piso** — acredite neste.
- **Leitura do canal que perdia vídeo entre páginas — e entre listas.**
  `enviados()` sai das playlists (não do `search`, que é eventual). Até
  28/09 lia só a de envios, com teto de 200: em builds, 26 públicos de fora;
  em histórias (196) o teto ia cortar em dias. Agora é `UU` + `UUSH` sem
  teto, e a lista se confere contra o `videoCount` do canal (§3).
- **Sufixo "(1 de 2)" que não casa.** O ledger guarda "(Parte 4)" e o canal
  guarda "(Parte 4) (1 de 2)": `titulos.chave` tira o corte e mantém a parte.
  Sem isso, cinco vídeos no ar foram reportados como "fantasmas". Quem
  precisa distinguir os dois pedaços chama `titulos.corte`.
- **Relatório diário que ninguém lê.** A linha `builds: 0/10` saiu seis dias
  seguidos no `metas` sem ninguém notar. Por isso o alarme da grade nasceu no
  diário (que vira mensagem no Telegram), e não em mais uma linha de
  relatório.
- **Ausência não é zero.** `retencao()` devolve `erro` em vez de 0 quando a
  Analytics não dá linha, e `comparar_formatos` descarta vídeo sem data.
- **Fuso.** `atividade.jsonl` grava UTC; os `publicados.jsonl` gravam hora
  local. Fatiar as duas strings igual põe "20:11" ao lado de "17:12".

## 6. "Está tudo bem?" em cinco comandos

```bash
cd E:/projetos
python -c "from builds.publicar import conferencia as c; [print(k, c.ultima(k).get('veredito'), c.ultima(k).get('dia_de_grade'), c.ultima(k).get('grade'), c.ultima(k).get('horarios_em_falta')) for k in ('builds','historias')]"
PYTHONIOENCODING=utf-8 python -c "from remoto import relatorios; print(relatorios.montar('metas'))"
PYTHONIOENCODING=utf-8 python -c "from remoto import relatorios; print(relatorios.montar('confiabilidade'))"
python -c "from builds.publicar import sinais as s; print(s.eventos_por_canal(s.ler_diario()))"
python -c "from builds.publicar import metricas as m; import json; print(json.dumps({k: (v.get('estado'), v.get('ultimo_ok'), v.get('erro')) for k, v in m.partes_da_marca(m.ler_marca()).items()}, indent=1))"
```

Nessa ordem eles respondem: o canal tem o que o ledger diz e a grade foi
cumprida? saiu vídeo hoje? dá para provar? algum canal está morto? a medição
ainda mede?

## 7. O que NÃO fazer

- **Não rodar `metricas.atualizar()` nem `--atualizar` para "só olhar"**: ele
  grava em `outputs/` e gasta cota. Para olhar, `carregar_salvas` ou uma
  chamada direta à Analytics, que não toca disco.
- **Não tratar o que está em `_metricas/` como de hoje.** Confira
  `_atualizado_em.json` antes de citar número de disco.
- **Não editar `random_builds/builds/publicar/*` fora do que é desta parte.**
  `conferencia.py` (ok do Adrian em 27/09), `metricas.py` e
  `tiktok_metricas.py` (Semana 2 da rota aprovada em 27/09) e o `sinais.py`
  (novo) foram mexidos por esta parte; os publicadores e o `postar.py`
  continuam da publicação. Mudança **fora de :25–:55**, e nada pela metade no
  disco nas rodadas da madrugada (01:28, 03:20, 04:20, 05:20): desenvolver
  numa worktree (`E:/projetos-wt/metricas`, com `PYTHONPATH` apontando para
  ela) e trazer os arquivos prontos de uma vez.
- **Não chamar `conferencia.aceitar*` na rodada automática.** Aceitar rascunho
  é decisão de uma pessoa.
- **Não somar plataformas nem canais.** Cada um tem ledger, credencial, pasta
  e grade próprios.
- **Não escrever um segundo caminho de aviso.** Alarme novo = linha de erro no
  `atividade.jsonl`, que já chega ao Telegram.

## Contratos com outras partes

| Recurso | Quem escreve | Por que esta parte só lê |
| --- | --- | --- |
| `*/outputs/_publicar/publicados.jsonl` | `builds.publicar.metricas` / `contos.publicar.serie`, no ato de publicar, sob a trava `ledger__<canal>` | escritor único: duas mãos no ledger é a divergência que a conferência existe para achar |
| `atividade.jsonl` | cada fábrica, por `builds.atividade.registrar` (nunca levanta) | é observabilidade; quem mede não pode fabricar o fato que mede |
| `*/outputs/_metricas*/` | `metricas.atualizar` e `tiktok_metricas.coletar`, chamados pela grade e pela madrugada | uma passada por dia, em um lugar só; conferir não é coletar |
| `*/outputs/_conferencia/<dia>.json` | `conferencia.salvar`, na rodada da noite (e o botão do painel) | a leitura do dia (`ultima`) é o que o painel e o bot mostram; `avisos` e `rodadas` são a memória da noite |
| `_metricas/_atualizado_em.json` (marca do dia) | `metricas.atualizar_uma_vez_por_dia` | a marca decide o que a próxima rodada tenta; o panorama só a lê |
| `rascunhos_aceitos.json` | só uma pessoa, por `--aceitar-rascunhos` | é decisão, não medida |
| grade e horários | `builds.grade` (fonte única) | três cópias da grade já fizeram relatório dar meta batida por engano |
