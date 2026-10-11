# Checagem da máquina — E:\projetos (só leitura)

Feita em 11/10/2026, 14:56–15:40, no PC do Adrian (Windows 10 Pro 19045). Nada foi alterado, publicado ou enviado; nenhuma rede externa além de DNS, `tailscale status` e `http://127.0.0.1:8931/sw.js`. Os scripts usados ficaram em `...\scratchpad\auditoria2\` (`analise.py`, `analise2.py`, `analise3.py`, saídas em `analise_saida.txt`).

Aviso: enquanto eu olhava, OUTROS auditores estavam rodando na mesma máquina (pytest em `historias random_builds`, `unittest`, `ffmpeg` medindo `generation_00119`, 24 worktrees `codex-pedido-*` criadas entre 15:03 e 15:14, `remoto/delegar.py` editado às 15:16). Isso derrubou e reiniciou serviços (ver item 6) e deixou o disco lento. Alguns números de hoje têm esse ruído.

---

## 1. Tarefas do Agendador — ATENÇÃO

Comando: `Get-ScheduledTask | ? TaskName -like 'NeuralFights_*' / 'Historias_auto_*' | Get-ScheduledTaskInfo` + `Actions`, `Settings`, `Triggers`.

**Inventário: 61 tarefas** (23 `Historias_auto_HH`, 23 `NeuralFights_gerar_HH`, 10 `NeuralFights_postar_HH`, `app_celular`, `bot_telegram`, `coordenador`, `vila_flutuante`, `capas_atrasadas`, `retomar_codex`).

Configuração (todas): `DisallowStartIfOnBatteries=False`, `StopIfGoingOnBatteries=False`, `StartWhenAvailable=True` (inicia se perdeu o horário). Todas chamam `wscript.exe //B //Nologo %LOCALAPPDATA%\neural-fights\oculto.vbs <cmd>`. Os arquivos chamados EXISTEM todos: `oculto.vbs`, `historias\auto.cmd`, `random_builds\gerar.cmd`, `postar.cmd`, `bot.cmd`, `coordenador.cmd`, `app_celular.cmd`, `vila_flutuante.cmd`, `ferramentas\capas_atrasadas.py`, `outputs\retomar_codex.py`, `C:\Python314\python.exe`/`pythonw.exe`.

**Horários x grade**
- `postar_*`: 00:37, 06:37, 09:37, 12:07, 15:37, 17:57, 20:37, 21:37, 22:37, 23:37 — **bate exatamente** com `GRADE` em `random_builds/builds/grade.py` (10 horários). Nenhuma faltando, nenhuma sobrando.
- `Historias_auto_*`: 01:20…05:20, 07:02…11:02, 12:32, 13:02…17:02, 18:22, 19:02…23:02, 00:02 — **bate exatamente** com `horas` em `historias/config/agenda.json` (23 disparos; não há 06h de propósito).
- `NeuralFights_gerar_*`: 23 tarefas nos MESMOS horários das histórias (00:02, 01:02…05:02, 07:02…, 12:32, 18:22…). Sem 06h. Geradas por `main.py noite --instalar` (`builds/pipeline/tarefas_noite.py`). Não achei arquivo de config com a lista; está coerente com as histórias.

**Últimos resultados (0x1 e 0x800710E0 são falha):**
| Tarefa | Estado | Último | Quando | Leitura |
|---|---|---|---|---|
| `Historias_auto_04` | Ready | **0x1** | 11/10 04:20 | A rodada das 04:20 pegou a historia_00070 (59 imagens pendentes, a passada anterior "morreu sem registrar o fim — processo encerrado de fora", pid 16152) e saiu com código 1 antes das 07:02. Ver item 2. |
| `Historias_auto_07` | **Running** (0x41301) | desde 07:02 | pid 6204, 8 h no ar: é a rodada de reposição que emenda passos (criou a 00071, renderizou, revisou 6 vídeos, consertou 2 barrados, criou a 00072 às 14:50 e está gerando 84 imagens). Normal pelo `passos_por_rodada: 12`, mas está em laço de falha (item 2). |
| `NeuralFights_app_celular` | Ready | **0x1** | 11/10 14:49 | Esperado pelo próprio `.cmd`: "se já houver um no ar, a porta 8931 está ocupada e este sai". Roda a cada 10 min e sempre falha com 1 porque o coordenador já mantém o app. Ruído permanente no Agendador. |
| `NeuralFights_bot_telegram` | Ready | **0x1** | 11/10 14:53 | Mesmo caso: `bot.txt` diz "[remoto] ja tem um bot no ar; este sai sem fazer nada". Duas gerências (tarefa de 10 min + coordenador) para o mesmo serviço. |
| `NeuralFights_coordenador` | Running | **0x800710E0** | 14:55 | A tarefa dispara a cada 5 min (gatilho Logon + repetição). O resultado 0x800710E0 ("o operador recusou o pedido") foi da tentativa das 14:55; o processo atual (pid 12920) subiu às 15:02:41 depois de o anterior cair (ver item 6). Não é bateria (`Bateria=False`). |
| `NeuralFights_retomar_codex` | Ready | 0x0 | 04/10 02:08 | Gatilho único de 02/10; sem próxima execução. Tarefa morta que ficou instalada (sobra). |
| todas as outras 55 | Ready | 0x0 | hoje/ontem | OK |

**Defeitos/atenções do item 1**
- `bot.cmd`, `postar.cmd` e `app_celular.cmd` ainda usam `>>` do cmd para o log (`outputs\bot.txt`, `postar.txt`, `app_celular.txt`). É o padrão que trancava a saída (memória "agendador-arquivo-trancado", 14/09); `gerar.cmd` e `auto.cmd` já usam `--saida`. Como `postar` roda 10x/dia num processo só, não trava hoje, mas é o mesmo risco.
- `NeuralFights_retomar_codex` é sobra (gatilho único de 02/10, nunca mais roda).

---

## 2. Logs dos últimos 7 dias — DEFEITO

Comando: `analise.py` (regex `Traceback`, `\berror\b|FALHOU|recusad|n[aã]o consegui|timeout`, por arquivo e por dia). Arquivos com mtime nos últimos 7 dias: `outputs/*.txt` (9), `historias/outputs/_logs` (10), `random_builds/outputs/_logs` (8).

**Totais: 59 Tracebacks, ~2.700 linhas de erro.** Por dia (linhas de erro / tracebacks): 04/10 20/12 · 05/10 32/4 · 06/10 65/0 · 07/10 461/0 · 08/10 310/0 · 09/10 561/0 · 10/10 1/0 · 11/10 25/0 · sem data no log: 1.224/43 (`postar.txt` e `app_celular.txt` não datam as linhas).

Por arquivo (tb / err / MB): `postar.txt` 0/664/2,2 · `auto_20261009` 0/570 · `auto_20261007` 0/462 · `auto_20261008` 0/345 · `auto_20261006` 0/198 · `carteiro.txt` 1/135 · `gerar_20261007` 0/131 · `coordenador.txt` 0/35/**5,7** · `app_celular.txt` **55**/0/2,1 · `bot.txt` 1/17 · `auto_saida.txt` 2/0.

**Os 15 erros mais repetidos** (contagem, primeira → última vez, leitura):
1. **445x** 06/10 → 08/10 `[gemini] a troca de modelo falhou (TimeoutError)` (auto_06/07/08, gerar_07) — site do Gemini (UI de trocar modelo) mudou ou travou: **ambiente**, mas 445 repetições em 3 dias = tentativa sem freio no código.
2. **346x** 04/10 → 09/10 `[imagens] pNN_cena_NN: gemini falhou 2x; tento o proximo` — consequência dos itens 1, 6 e da cota de imagens do Gemini (item 4): **ambiente**.
3. **278x** 05/10 → 09/10 `[imagens] pNN_cena_NN: chatgpt falhou 2x; tento o proximo` — **ambiente** (ChatGPT com `Page.goto` 90 s / download que não lê), ainda acontecendo às 15:21 de hoje em laço (`p01_cena_05`: chatgpt→gemini→chatgpt… 6 vezes seguidas).
4. **224x** 06/10 → 08/10 `[gemini] ATENCAO: nao consegui por no modelo forte depois de 3 tentativas; a historia vai sair em Gemini (Flash)` — mesmo defeito do 1; histórias saíram no modelo fraco (memória "qualidade-das-historias": o Flash era o problema). **Ambiente com efeito em produto.**
5. **180x** 07/10 `"error": {` (JSON do YouTube API em `postar.txt`/auto) — corpo do erro 403 do item 6.
6. **151x** (sem data; aparece até o fim de `postar.txt`) `capa recusada (403): "The authenticated user doesn't have permissions to upload and set custom video thumbnails."` — a conta do YouTube não tem permissão de miniatura personalizada (precisa de verificação por telefone no canal). **Ambiente/conta**; o código tenta a cada post e a `capas_atrasadas` diária repete.
7. **56x** 06/10 → 11/10 `[imagens] ... o Chrome caiu no gemini (o Chrome caiu no download e a recuperação falhou: a imagem nao apareceu na conversa reaberta em 60s)` — **código** (download do Gemini pelo patchright; hoje aparece como `ImagemFalhou: o download veio, mas o arquivo não foi lido (TargetClosedError: Download.path...)` dezenas de vezes entre 04:28 e 14:54, com fallback "uso a reserva do src da tela").
8. **28x** `[tiktok] não consegui escrever a legenda (TimeoutError); tentando de novo` — **ambiente** (site do TikTok lento).
9. **28x** 05/10–06/10 `[anexo] dialogo de arquivo nao abriu (TimeoutError)` (gerar) — **código/ambiente** (anexo de imagem no navegador).
10. **24x** `[parecer] nao consegui avisar no Telegram: No module named 'remoto'` (`postar.txt`, inclusive hoje 12:1x) — **código**: o parecer roda com cwd `historias/` e `remoto` não está no `sys.path` (`historias/contos/pipeline/agenda.py` importa `remoto`). O aviso de REPROVADO nunca chega ao Telegram.
11. **22x** 04/10 01:21 `[reparo] a geracao falhou (ModuleNotFoundError); desfazendo` — **código**, já conhecido: módulo meio velho/meio novo durante entrega aplicada em rodada viva (memória 07/10). Não repetiu depois de 04/10.
12. **21x** `[tiktok] não consegui escrever a legenda (TimeoutError).` — ambiente.
13. **21x** `tiktok: NAO subiu (TikTokFalhou: a legenda não entrou ... Adiado de propósito)` — consequência do 12; guarda certa.
14. **15x** `tiktok: NAO subiu (... o botão de publicar não ficou clicável em 2 min — o TikTok ainda estava processando)` — ambiente.
15. **15x** `[tiktok] a pagina nao abriu (tentativa 1 de 3: Page.goto: Timeout 90000ms)` — ambiente (09/10 foi o DNS da operadora — conhecido).

**Tracebacks**
- `app_celular.txt`: 55 tracebacks, **178 ocorrências** de `ConnectionAbortedError: [WinError 10053]` (até 05/10 13:07) e 8 "During handling of the above exception" em `remoto/api_http.py:569 _json` — o cliente (PWA) fecha a conexão e o servidor imprime traceback inteiro. **Código** (deveria engolir 10053). Parou em 05/10.
- `bot.txt` (05/10 18:06) e `carteiro.txt` (02/10 09:06): `SyntaxError: unterminated string literal` — arquivo pela metade durante entrega (conhecido, 28/09 e 07/10). Não repetiu.
- `auto_saida.txt`: `AttributeError: module 'contos.publicar.qualidade' has no attribute 'formato_de'` e `module 'builds.identity.slots' has no attribute 'CORREIO'` — hoje ambos existem no disco; foi a mesma janela de código meio aplicado.

**Hoje, ao vivo (auto_20261011.txt, 14:28–15:21):**
- 14:28 `[carteiro] gemini 7a39ece9 (imagem) falhou: o site diz: «Faça login para se conectar aos apps do Google, criar imagens e muito mais»` → **o Gemini está DESLOGADO** no perfil `gemini__principal`.
- 15:21 `[carteiro] chatgpt aeafcee6: TimeoutError: Page.goto: Timeout 90000ms exceeded (https://chatgpt.com/?model=auto)` e 15:18/15:21 `aviso no Telegram NAO entregue`.
- `historia_00072` (criada 14:50, 84 cenas) está presa na `p01_cena_05` alternando chatgpt/gemini "falhou 2x" desde 15:06.

---

## 3. Ledgers de publicação — ATENÇÃO

Comando: `analise.py`/`analise2.py` sobre `random_builds/outputs/_publicar/publicados.jsonl` (489 linhas) e `historias/outputs/_publicar/publicados.jsonl` (547 linhas).

- Linhas ilegíveis: **0 / 0**.
- `video_id`+`plataforma` repetidos: builds **4** (todos de 29–31/08: `generation_00072/00075/00082:estreia:celular` e `generation_00080:build:celular:B` no YouTube, republicados no dia seguinte — era do tempo da reconciliação que apagava linha, conhecido); histórias **0**.
- YouTube sem `youtube_id`: builds **0**; histórias **8** — 5 de 09–10/09 (`historia_00003`, ledger antigo) e **3 de 07/10** (`historia_00054:p02` 12:27, `historia_00063:p01` 15:38, `historia_00061:p03` 20:37, `url="publicado no YouTube (com a confirmacao extra)"`, sem id). Esses 3 não têm como ser conferidos com o canal nem receber métricas.
- `prova_ok` nos últimos 30 dias: builds 408 linhas, **False 12, ausente 62** (ausentes são todas de 15/09, antes do campo existir); histórias 504 linhas, **False 37, ausente 58** (ausentes de 15–18/09). Dos **49 False** recentes, TODOS são `historias/youtube`, com `prova.estado=publicado`, `prova.desfecho=publicado`, `prova.youtube_id=""` e o `youtube_id` de nível superior preenchido (ex.: 09/10 22:39 `historia_00064:p06` → `3dPPAyvKqqs`). Ou seja: a prova falha só porque o id não veio na hora do clique, o id é recuperado depois do canal, mas `prova_ok` fica False para sempre. Inconsistência de registro (quem lê `prova_ok` acha que 37 vídeos de histórias não subiram).
- Arquivo de vídeo no disco: dos 408 (builds) e 504 (histórias) dos últimos 30 dias, **0 sem mp4** na pasta da fonte (`outputs/<fonte_id>/**/*.mp4`, com a parte certa nas histórias).

**Publicações por dia (14 dias)** — slot = horário da grade imediatamente anterior (até 100 min):

| dia | builds/YT | builds/TT | hist/YT | hist/TT | horários atendidos | faltando |
|---|---|---|---|---|---|---|
| 27/09 | 4 | 4 | 3 | 4 | **6/10** | 00:37, 06:37, 09:37, 12:07 |
| 28/09 | 10 | 10 | 11 | 9 | 10/10 | |
| 29/09 | 8 | 8 | 9 | 8 | **8/10** | 20:37, 22:37 |
| 30/09 | 10 | 10 | 9 | 9 | 10/10 | |
| 01/10 | 10 | 10 | 10 | 10 | 10/10 | |
| 02/10 | 9 | 9 | 10 | 10 | 10/10 | |
| 03/10 | 8 | 8 | 8 | 8 | **8/10** | 06:37, 12:07 |
| 04/10 | 9 | 9 | 9 | 8 | **9/10** | 23:37 |
| 05/10 | 9 | 9 | 9 | 9 | 10/10 | |
| 06/10 | 10 | 10 | 8 | 10 | 10/10 | |
| 07/10 | 10 | 9 | 10 | 10 | 10/10 | |
| 08/10 | 10 | 10 | **13** | 10 | 10/10 | (3 YT de histórias a mais: 06:39+06:41, 09:38+09:40, 12:10+12:17 — dois vídeos no mesmo horário) |
| 09/10 | 3 | 3 | 4 | 4 | **4/10** | 09:37…21:37 (DNS da operadora caiu 06:39–22:40 — conhecido) |
| 10/10 | 10 | 10 | 1 | 1 | 10/10 | histórias pausadas a pedido dele (conhecido) |
| 11/10 (até 15:30) | 4 | 4 | 3 | 3 | 4/10 | em andamento |

- Horários da grade **sem nenhuma publicação nos últimos 7 dias: nenhum** (todos os 10 receberam entre 20 e 26 posts).
- Dias com buraco nos 14 dias: 27/09, 29/09, 03/10, 04/10, 09/10 (o de 09/10 é o DNS; os outros 4 não têm causa registrada no ledger — `postar.txt` não data as linhas, então não dá para achar pelo log).

---

## 4. Diário `atividade.jsonl` — ATENÇÃO

Local: `%LOCALAPPDATA%\neural-fights\atividade.jsonl` (1,9 MB, 8.867 linhas, 0 ilegíveis; há cópia `atividade.jsonl.antes-limpeza-20261006`).

Status nos 7 dias: ok 3.362 · log 2.650 · inicio 2.345 · **erro 408** · aviso 100 · pedido 2.

Erros por etapa (7 d):
- **correio: 321** — 108x `carteiro: sem_imagem: o Gemini respondeu sem imagem: «Poderei criar mais imagens assim que…»` (**cota de imagens do Gemini esgotada** — ambiente); 58x `recuperacao: o Chrome caiu no download…` (código, item 2.7); 41x `LLMFalhou: o envio voltou para a caixa de texto do gemini sem resposta` (conhecido, "raciocínio preso"); 13x `Page.goto: net::ERR_NAME_NOT_RESOLVED chatgpt.com` (DNS 09/10).
- **? (sem etapa): 34** — "grade builds/youtube: 9 de 10 horarios com video publico confirmado", "coleta do YouTube de historias falhou: o YouTube recusou playlistItems", "historia_00070: retomada falhou: ERR_NAME_NOT_RESOLVED gemini", "sinais builds: noite(s) sem conferencia: 04/10". Linhas de erro **sem campo `etapa`** — quem as grava não preenche.
- **publicar.tiktok: 20** — página não abriu (6), `Page.goto` 90 s (5), "não achei o campo de arquivo na página de upload" (4), botão não clicável em 2 min (3).
- **publicar.youtube: 14** — "página de upload abriu e ficou em branco" (5), não abriu (3), não carregou (2).
- **noite: 7** — `worker: AttributeError: module 'builds.identity.queue' has no attribute 'P…'` (código meio aplicado), PicassoIA timeout, 2x `GeracaoFalhou` em `character_weapon_ref` (generation_00098/00112).
- roteiro 3, imagens 3 (`historia_00070: 18 geradas, 66 pendentes`), llm.conversa 2, publicar.youtube.estagio 2 ("estagio ILEGIVEL no clique depois de 300s; publiquei assim mesmo"), publicar.tiktok.sem_confirmacao 1 (`generation_00104`), **imagens.morreu_calada 1** (`historia_00070`, pid 16152 morto de fora em 10/10 04:23).

Dado de teste nos erros dos 7 dias (`duble`, `teste`, `trava:build:celular`, `que_nao_existe`): **0**. OK.

---

## 5. Arquivos de estado em `%LOCALAPPDATA%\neural-fights` — ATENÇÃO

Comando: `analise.py` (parse de todo `.json`/`.jsonl`, exceto `browser_profiles/`, `_backup*`, `tarefas_antes_oculto*`).

- **2.134 arquivos** json/jsonl checados: **0 ilegíveis, 0 vazios**.
- Maiores que 5 MB: **4**, todos `delegados/*/eventos.jsonl` (corrente-codigo-agora 9,1 MB; pedido-7f7780d0-1 7,2; pedido-a28fbae4 5,9; conf-atelie-objeto 5,8). São transcrições do Codex; só peso.
- `locks/`: **212 arquivos `.lock`** (1 byte, a trava é do SO, então arquivo velho é normal). **92 têm nome de teste** (`teste_agenda_<pid>` x80, `teste_reentrante_*`, `teste_noite_*`, `historias__render__historia_que_nao_existe`, `historia_teste_sem_img`, `perfil__perfil-que-nao-existe__*`, `ias__duble__*`, `ias__carteiro__duble`): **pytest escreve travas na pasta REAL** (memória "proteção que precisa ser lembrada", 16/09, dizia o mesmo do diário).
- Única ficha de dona: `postar__rodada.dona.json` pid 6980, horário 12:07, pulso há 166 min, **processo morto**. Pelo comentário em `ferramentas/postar.py:4518+`, a ficha fica ao lado da trava de propósito e só conta como presa se o pid dela estiver vivo e calado — **não é trava presa**.
- `delegados/` (217 pastas): situações terminou 124 · parado 38 · falhou 16 · negado 8 · abandonado 5 · criado 26. **Nenhum "rodando" sem processo** no momento da leitura. **19 "terminou" sem `aplicado` e sem `limpo`** (lista no `analise_saida.txt`: `coordenador`, `coordenador-app`, `integrar-pedido-6d47da78`, `integrar-pedido-88e300da-1`, `integrar-pedido-f19c9cfb`, `pedido-1833f0c0`, `pedido-22b772f7`, `pedido-91d3610d` (3x "Investigar erro do apurador"), 9x "O Adrian respondeu no Grimório (…)", `pedido-88e300da-1`).
- O coordenador marca **8 entregas "precisa de olho: criado antigo com mudança não aplicada"**: `pedido-88e300da`, `integrar-pedido-4d3fc3ba`, `pedido-61fa5b2f`, `guarda-roupa`, `recortador-folha`, `sprites-9-escolhas`, `pedido-5f240534`, `picasso-goto` — e **escreve as 8 linhas a cada minuto**: `coordenador.txt` tem **6.489 linhas `trabalho_olho` só hoje** (6.581 linhas no dia; 811 por entrega). É isso que faz o log ter 5,7 MB. O mesmo texto vai ao Telegram como "Andamento" (avisos_enviados 15:07).
- `coordenador/estado.json`: pid 12920, `desde 15:02:41`, versão `0c09873`; serviços app (pid 5288, desde 15:17), bot (4852, 15:17), carteiro (13748, desde **10/10 00:58**), vila (6732, 14:41); `reinicios_24h: 0` em todos — **não bate** com os 5 "bot no ar" de hoje (12:42, 14:19, 14:31, 14:42, 15:18) nem com "app reiniciou: codigo atualizado" às 15:17. O contador de reinícios está zerado por engano ou zera a cada subida do coordenador.
- `coordenador/pedidos.json` (565 KB): 100 pedidos — contratando 30, respondido 30, cancelado 19, conferido 17, falhou 3, esperando_voce 1.
- `orquestrador/config.json`: `max_paralelo 6, modo paralelo, teto_sessao 50 %, teto_semana 95 %`. `uso.json` (sonda do app, 14:52): **sessão 41 %, semana 88 %, status `allowed_warning` (seven_day)**. `claude.json`: `liberado: true` desde 01/10 pelo app.
- `coordenador.lock` = `12920` e pid vivo. `app_celular.lock`, `decisoes.lock`, `claude.json.lock`: 0 bytes (normal).

---

## 6. Processos vivos — ATENÇÃO

Comando: `Get-CimInstance Win32_Process` (python/pythonw/chrome/node/codex/ffmpeg) às 15:04 e 15:20.

Python do projeto:
| pid | início | há | comando |
|---|---|---|---|
| 13748 | 10/10 00:58 | **38 h** | `-m ias carteiro --saida outputs\carteiro.txt` (serviço do coordenador) |
| 6204 | 11/10 07:02 | 8 h | `historias main.py auto` (rodada das 07:02, item 1) |
| 12920 | 11/10 15:02 | — | `-m coordenador rodar` |
| 5288 | 15:17 | — | `-m remoto.api_http --local --porta 8931 --acoes --publicar --perigosas` (dono da porta 8931) |
| 4852 | 15:17 | — | `-m remoto` (bot) |
| 6732 | 14:41 | — | `pythonw -m painel.flutuante --medio` (Vila) |
| 2564 | 15:02 | — | `random_builds main.py noite` (gerar_15) |
| 12052 | 15:02 | — | `historias main.py auto` (disparo 15:03, saiu: "já tem rodada") |

Python de fora do projeto: `node vite --port 5199` em `C:\Users\adrian\BLUE-Lock-project` (28 h, outro projeto do Adrian); `codex.exe app-server` da extensão do VS Code (11 h); e os processos dos outros auditores (pytest, unittest, ffmpeg x5, `navegar.py`, `lancar_servidor.py 8999`, `render_casos.py`, `remoto.delegar rodar --id pedido-ad5de4ce/64c2bbee`, `remoto.delegar limpar --id pedido-08e6806a`, `codex exec` em `E:\projetos-wt\…`).

- **Python com mais de 12 h que não é serviço: nenhum.** O carteiro (38 h) é serviço, MAS `carteiro.txt` parou em **10/10 01:43** ("chatgpt 168dc741: abandonado pelo processo 16152; não entrego") e o diário não tem **nenhuma** linha com `pid 13748`. Toda a atividade de correio dos 7 dias vem do processo das histórias (pid 6204) e do `postar`. O serviço está vivo e calado há 37 h; as caixas `ias/gemini/correio.jsonl` e `ias/chatgpt/correio.jsonl` (2,9 MB e 2,4 MB) foram escritas às 15:21 por outro processo. Não dá para dizer daqui se ele está travado ou só sem trabalho.
- Chrome: 62 processos; só **2 navegadores** com `--user-data-dir`: `browser_profiles\chatgpt__principal` (pai: node do patchright, filho do pid 6204, vivo) e um perfil temporário do playwright de outro auditor. **Nenhum Chrome órfão.**
- Hoje o coordenador registrou: 14:40/14:41 `vila caiu: processo ausente`, 14:42 `bot caiu` x2, 15:17 `app reiniciou: codigo atualizado`, `bot reiniciou: codigo atualizado`, 15:17:53/59 `bot caiu` x2. O coordenador anterior morreu por volta de 14:55 (tarefa 0x800710E0; o atual subiu 15:02). Causa provável: `remoto/delegar.py` e `remoto/test_delegar.py` foram editados às 15:16 (status do git) e os testes dos outros auditores — "código atualizado" reinicia app e bot a cada edição, e **isso cai dentro da janela das postagens** (15:37 ± 12/18 min, `post-12` a `post+18`). Linhas `caiu/reinici` por dia: 04/10 33 · 05/10 **211** · 06/10 13 · 07/10 29 · 08/10 24 · 09/10 1 · 10/10 10 · 11/10 17.

---

## 7. Disco — ATENÇÃO

Comando: `Get-PSDrive`, `robocopy /L /S /BYTES` (listagem, só leitura), `git worktree list`.

- **C: 14,1 GB livres** de 118,7 (o C: "vive cheio"; `disco_livre_minimo_gb: 5` da agenda ainda tem folga). **E: 56,3 GB livres** de 465.
- Tamanhos: `random_builds/outputs` **39,2 GB**; `historias/outputs` **56,4 GB**; `E:\projetos-wt` **7,1 GB** (77 worktrees + provas); `E:\tmp_pytest` **medição não terminou em 10 min** — 7.848 entradas só na raiz (pastas `pytest-of-*`/worktrees de teste), tantas que percorrer leva mais de 10 min com o disco ocupado; `%LOCALAPPDATA%\neural-fights` **17,3 GB no C:** (dos quais `browser_profiles` **13,7 GB**, `delegados` 0,2 GB) — o C: tem só 14,1 GB livres, e os perfis de navegador são a maior parte do que o projeto ocupa lá; `E:\projetos\outputs` 0,3 GB.
- Worktrees: `git worktree list` tem **77 entradas** (74 `E:\projetos-wt\codex-*`, `deepseek`, `E:\tmp_pytest\wt_bsp` e `wt_pub` em HEAD destacado, `E:\wt_corrente`). **24 worktrees `codex-pedido-*` foram criadas hoje entre 15:03 e 15:14** (todas em `0c09873`) pelos outros auditores — 24 cópias do repositório de uma vez.
- Pastas em `E:\projetos-wt` que **não estão** no `git worktree list` (lixo): `codex-app-5959d5ba`, `codex-b3-lista-unica`, `codex-integrar-carinha-parecida`, `codex-integrar-catalogo-animacoes`, `codex-pedido-50a767ed`, `-5deb09bc`, `-89b0653d`, `-d8ad11ef`, `-e0abfa99`, `-e29904c3`, `-f986bf91` (11 worktrees órfãs), mais **65 pastas de prova** (`prova_vila_*` x19, `prova_deitado_*` x8, `prova_arv_*`, `prova_dec_*`, `prova_grok_*`, `sonda_*`, `_prova_*` x16, `_codex_formato`, `_lixo_codex`, `_pytest_app`, `_tmp`, `_tmp_testes`), de 28/09 a 11/10.
- `E:\projetos\.claude\worktrees`: vazia. OK.
- 10 maiores logs: __LOGS__

---

## 8. Git em `E:\projetos` — ATENÇÃO

Comando: `git status --short`, `git rev-list --left-right --count main...HEAD`, `git fsck --no-dangling --connectivity-only`, `git ls-files` + tamanho.

- Ramo: `refactor/arquitetura` @ `0c09873` (11/10). **`main` está em `8fdfd48` de 20/02/2026 ("Zera os catalogos") — 945 commits atrás, 0 à frente.** Todo o trabalho de 8 meses vive no ramo de refactor; `main` não representa nada. Remoto: `origin https://github.com/zaptod/projetos.git`. 1 stash.
- `git fsck --no-dangling --connectivity-only`: **sem erro** (exit 0). `count-objects`: 700 soltos (11,6 MB), 13.402 em 3 packs (78,9 MB), 0 lixo.
- Arquivos rastreados > 20 MB: **0** (1.602 rastreados).
- Sem commit (data da última modificação):
  - do Adrian, de propósito: `palco/biblioteca/LICENCAS.md` (02/10), `palco/biblioteca/efeitos/objetos/projetil/fogo.tscn` (01/10), `palco/biblioteca/efeitos/folhas/` (05/10), `palco/biblioteca/efeitos/skills/` (02/10), `palco/biblioteca/partes/` (06/10), `painel/flutuante/arte_vila/habitantes/` e `predios/{gemini,grok,picasso}.{json,png}` (02/10).
  - **lixo na raiz desde 28–29/09**: `11239-removebg-preview (1).png`, `11243.png`, `sprites_transparentes.png`, `piriri.py`, `projetos-wt_prova_filaerro7.txt`.
  - `docs/handoff/ATUAL.md` (M) e `docs/handoff/historico/` (??) — gerados pelo hook hoje 14:52.
  - **`remoto/delegar.py` e `remoto/test_delegar.py` modificados às 15:16 de hoje** — alguém (outro auditor/orquestrador) está editando agora; não é meu.

---

## 9. Rede — DEFEITO

Comando: `Resolve-DnsName`, `Get-DnsClientServerAddress`, `Get-NetAdapter`, `Get-NetRoute 0.0.0.0/0`, `tailscale status`, `Invoke-WebRequest http://127.0.0.1:8931/sw.js`.

- DNS resolveu os 6: studio.youtube.com 142.250.219.14 · www.tiktok.com 23.212.191.16 · api.telegram.org 149.154.166.110 · oauth2.googleapis.com 142.251.0.95 · gemini.google.com 142.251.151.2 · chatgpt.com 104.18.32.47.
- **MAS os servidores DNS configurados são: `Ethernet: 181.213.132.8, 181.213.132.9` (os da operadora) e `Wi-Fi: 1.1.1.1, 8.8.8.8`.** Adaptadores UP: Ethernet (1 Gbps, rota padrão com métrica 25), Tailscale, Radmin VPN. **O Wi-Fi não está ativo.** Ou seja: a troca para 1.1.1.1/8.8.8.8 (depois da queda do DNS da operadora em 09/10, memória "aviso-sem-rede-calado") foi feita no adaptador errado — **a máquina continua usando o DNS da operadora**. Se ele cair de novo, cai tudo de novo.
- `tailscale status`: `desktop-tgti3ek` (este PC) e **`moto-g56-5g` 100.108.178.107 online** (sem "offline"); `desktop-j6adlhm` offline há 269 d. Health check: **"Tailscale can't reach the configured DNS servers. Internet connectivity may be affected."**
- App: `http://127.0.0.1:8931/sw.js` → **HTTP 200**, 2.058 bytes, `text/javascript` (pid 5288, escuta só em 127.0.0.1).

---

## 10. Python e dependências — OK

- Python **3.14.4** (`C:\Python314\python.exe`, o mesmo das tarefas). `pip check`: "No broken requirements found".
- Terceiros importados pelo código (fora de tests/outputs): PIL, customtkinter, edge_tts, numpy, patchright, pygame, pytest, requests — **todos instalados** (pillow 12.3.0, customtkinter 5.2.2, edge-tts 7.2.8, numpy 2.4.6, patchright 1.62.1, pygame-ce 2.5.7, pytest 8.4.2, requests 2.34.2). Dois "imports" que não são pacotes: `historias/tests/test_duas_historias_em_paralelo_regressions.py` importa `main`, e `test_recusa_no_trecho_regressions.py` importa `test_recusa_do_gemini_regressions` (só funcionam com cwd/rootdir certos).
- Godot: `random_builds/config/palco.json` → `E:/ferramentas/godot/Godot_v4.7.2-stable_win64_console.exe` — existe, `--version` = **4.7.2.stable.official.ed1daf0bf**.
- ffmpeg/ffprobe no PATH: **8.1.2-full_build (gyan.dev)**.
- Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe` **154.0.8037.98**; patchright 1.62.1 traz chromium 151.0.7922.34 no `browsers.json`, mas o código usa `channel="chrome"` (`builds/identity/browser.py`), então roda o Chrome instalado. Chrome 154 com driver feito para 151: funciona hoje (as páginas abrem), mas é 3 versões à frente do que o patchright testou.

---

## O que precisa de ação (do mais grave ao menos)

1. **DNS da operadora ainda ativo na Ethernet** (`181.213.132.8/.9`); o 1.1.1.1/8.8.8.8 só foi posto no Wi-Fi, que está desligado — `Get-DnsClientServerAddress -AddressFamily IPv4`; corrigir na interface "Ethernet" (`Set-DnsClientServerAddress -InterfaceAlias Ethernet -ServerAddresses 1.1.1.1,8.8.8.8`, decisão dele). O Tailscale já reclama que não alcança o DNS.
2. **Gemini deslogado** no perfil `gemini__principal` (14:28 «Faça login para se conectar aos apps do Google»); a historia_00072 está em laço `p01_cena_05: chatgpt/gemini falhou 2x` desde 15:06 e vai queimar a rodada — `historias/outputs/_logs/auto_20261011.txt`; relogar a conta (só o Adrian).
3. **Imagens do Gemini: cota esgotada** 108x em 7 dias («Poderei criar mais imagens assim que…») + "troca de modelo falhou" 445x e "a historia vai sair em Gemini Flash" 224x (06–08/10): o código insiste sem freio e as histórias saem no modelo fraco — `atividade.jsonl` etapa `correio`, `auto_2026100{6,7,8}.txt`; precisa de freio por cota e de alarme quando cai para o Flash.
4. **`coordenador.txt` recebe 6.489 linhas `trabalho_olho` por dia** (8 entregas "precisa de olho" repetidas a cada minuto; 5,7 MB) e o mesmo texto vai ao Telegram — `coordenador/` (quem gera `trabalho_olho`); e as 8 entregas presas (`pedido-88e300da`, `integrar-pedido-4d3fc3ba`, `pedido-61fa5b2f`, `guarda-roupa`, `recortador-folha`, `sprites-9-escolhas`, `pedido-5f240534`, `picasso-goto`) precisam ser aplicadas ou abandonadas — `python -m remoto.delegar ...`.
5. **Carteiro (pid 13748) vivo há 38 h e calado desde 10/10 01:43** (zero linhas no diário, `outputs/carteiro.txt` parado); confirmar se está travado — `python -m coordenador reiniciar carteiro` fora da janela das postagens.
6. **`[parecer] nao consegui avisar no Telegram: No module named 'remoto'`** 24x, inclusive hoje: o REPROVADO do parecer nunca chega ao Adrian — `historias/contos/pipeline/agenda.py` (import de `remoto` sem `E:\projetos` no `sys.path` quando o cwd é `historias/`).
7. **Ledger de histórias: 49 linhas `prova_ok=False` nos 30 dias em que o vídeo SUBIU** (prova com `youtube_id=""` e id recuperado depois) e **3 YouTube de 07/10 sem `youtube_id`** (`historia_00054:p02`, `00063:p01`, `00061:p03`) — `historias/outputs/_publicar/publicados.jsonl`; o reconciliador deveria virar `prova_ok` quando o id vem do canal e preencher os 3 ids.
8. **Serviços reiniciados por "código atualizado" dentro da janela das postagens** (15:17 hoje, a 20 min do 15:37) e `reinicios_24h: 0` mentindo (5 subidas do bot hoje) — `coordenador/estado.json`; e `remoto/delegar.py` + `remoto/test_delegar.py` modificados às 15:16 sem commit por outro agente.
9. **Download do Gemini/ChatGPT "o download veio, mas o arquivo não foi lido (TargetClosedError: Download.path)"** dezenas de vezes por dia desde 04:28 (fallback para o `src` da tela salva, mas custa 1–2 min por imagem) — código do download no patchright (`ias/` ou `historias/contos/imagens`).
10. **Capa recusada 403** 151x: "The authenticated user doesn't have permissions to upload and set custom video thumbnails" — a conta do YouTube precisa de verificação para miniatura; até lá `capas_atrasadas` (03:10 diária) e cada post gastam cota à toa — `ferramentas/capas_atrasadas.py`, `outputs/postar.txt`.
11. **Tarefas `NeuralFights_app_celular` e `NeuralFights_bot_telegram` falham com 0x1 a cada 10 min** de propósito (o coordenador já mantém os dois): ruído no Agendador que esconde falha real — desligar as duas ou trocar a saída por 0; `NeuralFights_retomar_codex` é sobra de 02/10 — `Unregister-ScheduledTask` (decisão dele).
12. **`bot.cmd`, `postar.cmd`, `app_celular.cmd` ainda usam `>>` do cmd** (o padrão que trancava a saída em 14/09) — trocar por `--saida` como `gerar.cmd`/`auto.cmd`.
13. **92 arquivos de trava de teste na pasta real** `%LOCALAPPDATA%\neural-fights\locks\` (`teste_agenda_*`, `historia_que_nao_existe`, `ias__duble__*`…): pytest escreve no diretório de produção — fixture de `locks` para TEMP.
14. **Lixo em disco**: 11 worktrees órfãs + 65 pastas `prova_*/_prova_*` em `E:\projetos-wt` (28/09–11/10), `E:\tmp_pytest` com 7.848 entradas, 2 worktrees em HEAD destacado dentro de `E:\tmp_pytest` — `git worktree prune` + apagar (decisão dele); e 5 arquivos soltos na raiz do repo desde 28/09 (`11239-removebg-preview (1).png`, `11243.png`, `sprites_transparentes.png`, `piriri.py`, `projetos-wt_prova_filaerro7.txt`).
15. **`main` está 945 commits atrás de `refactor/arquitetura`** (último commit de 20/02) — o repositório "vai ser mostrado": `main` precisa receber o ramo ou o ramo virar o padrão.
16. **24 worktrees `codex-pedido-*` criadas em 11 minutos hoje** (15:03–15:14) — memória "um projeto por vez"; e 19 delegados "terminou" sem aplicar nem limpar.
17. **`app_celular.txt` com 178 tracebacks de `ConnectionAbortedError 10053`** (até 05/10) — `remoto/api_http.py:569` deveria engolir cliente que fechou.
18. **4 dias com horário de postagem vazio sem causa registrada** (27/09 x4, 29/09 x2, 03/10 x2, 04/10 23:37) — `postar.txt` não data as linhas, então não dá para investigar pelo log; datar as linhas do `postar.txt`.
19. **Uso do Claude: semana em 88 %** (`orquestrador/uso.json`, status `allowed_warning`) com `max_paralelo 6` — memória "uso mínimo do Claude".
20. Chrome 154 com patchright feito para o chromium 151 — funciona, mas vigiar a próxima atualização do Chrome.
