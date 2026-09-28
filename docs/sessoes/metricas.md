# Métricas e conferências

Documento de passagem. Tudo abaixo foi medido em 27/09/2026; onde um número da
fotografia não reproduziu, está dito. O que eu não medi está marcado como
**não medi**, nunca preenchido por suposição.

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
  um destino só. Só formata; o número é de `panorama.confiabilidade`.
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

**Repetição:** cada rodada da noite com déficit escreve a sua linha de erro —
até 4 avisos iguais por canal por noite. Não está deduplicado.

## 4. As conferências que faltam, e o número que deveria acender

| Falta | Hoje, medido | Acende quando |
| --- | --- | --- |
| canal sem evento no diário em 24 h | histórias 962 eventos, **builds 5** | qualquer canal com 0 |
| estoque por formato zerado | `estoque_por_formato` diz `build: 7 dias`, e os 25 pendentes de build estão **todos** barrados por título | formato com 0 pronto de verdade |
| cobertura de `youtube_id` no ledger | builds 120/129 (93%), **histórias 61/158 (39%)** | abaixo de ~90%: sem id não há métrica nem formato |
| colisão de título | dos 33 pendentes de builds, **25 barrados (76%)** | fila barrada acima de ~30% |
| publicação não pública no ledger | **5** (4 builds, 1 histórias) | qualquer uma acima de zero |

Nenhuma dessas tem alarme hoje. E o caso que prova a falta:
**a coleta do YouTube ficou dez dias quebrada e ninguém soube.** Na madrugada
de 27/09, 01:20, o log de `historias/outputs/_logs/auto_20260927.txt` diz
`[builds] metrica nao atualizou: name 'titulos' is not defined` (igual em
histórias): `metricas.casar_ids` passou a usar `titulos.corte` em 17/09 sem o
import no topo. `atualizar_tudo` engole a exceção, a marca do dia gravou
`builds: 0, historias: 0`, e só o TikTok atualizou (60 e 50). O import foi
consertado por outra sessão no commit `42dced8`, ainda em 27/09 — mas **os
arquivos em disco continuam sendo de 16/09** até a próxima rodada, e
`panorama.desempenho` só lê disco, sem dizer que o dado é velho. A conferência
que falta é justamente esta: *a última coleta deu zero vídeo?*

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
- **Painel com ✓ para grade furada.** `panorama.confiabilidade` e a página
  Confiabilidade do painel só leem `veredito`: uma ficha `limpo` com `grade`
  "em falta" aparece como `✓ casados/no_ledger`. Hoje só o diário acende.
- **"Dias de estoque" conta vídeo, não vídeo publicável.**
  `estoque_por_formato` não aplica pendências nem título repetido: diz
  `build: 7 dias` quando o real é 0. `estoque()` (que passa pelo mesmo funil
  de `proximo_build`) diz **builds 0 dias, abaixo do piso** — acredite neste.
- **Leitura do canal que perdia vídeo entre páginas.** `enviados()` sai da
  playlist de uploads (não do `search`, que é eventual) e pagina até o teto;
  o padrão é 200 e os canais já têm 166 e 185 uploads. Teto baixo = "vídeo
  sumido" que na verdade é página não lida.
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
python -c "from builds import atividade; import collections; e=atividade.recentes(1000); print(collections.Counter(x.get('canal') for x in e))"
cat random_builds/outputs/_metricas/_atualizado_em.json   # 0 vídeos = coleta quebrada
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
- **Não editar `random_builds/builds/publicar/*`**: é de outra sessão. O
  `NameError` do §4 é para reportar, não para consertar. Exceção só com o ok
  do Adrian, como o `conferencia.py` na noite de 27/09 — e fora de :25–:55,
  porque a conferência roda de madrugada.
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
| `*/outputs/_conferencia/<dia>.json` | `conferencia.salvar`, na rodada da noite | a leitura do dia (`ultima`) é o que o painel e o bot mostram |
| `rascunhos_aceitos.json` | só uma pessoa, por `--aceitar-rascunhos` | é decisão, não medida |
| grade e horários | `builds.grade` (fonte única) | três cópias da grade já fizeram relatório dar meta batida por engano |
