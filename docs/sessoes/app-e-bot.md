# App do celular e bot do Telegram

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/app-e-bot/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Um projeto por vez (28/09/2026) `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Passou de 50%, para tudo; força total 20 min antes de renovar (28/09/2026) `teto-de-uso`

**App e bot**
- ✅ **Quem publica pelo celular** — Só o app (28/09/2026) `quem-publica-pelo-celular`
- ✅ **Destino padrão da publicação** — YouTube e TikTok (28/09/2026) `destino-padrao`
- ✅ **Tailscale sem login (unattended)** — Sim, ligar (28/09/2026) · “falta ele rodar o comando: tailscale set --unattended=true (a permissão do agente barrou)” `tailscale-unattended`
- ⏳ **Onde fica pausar / retomar / parar** — No app novo, o Controle (pausar, retomar, parar) ficou dentro do objeto Avisos (quadro de cortiça). Onde você quer? `controle-onde`

<!-- decisoes:fim -->

Documento de passagem. Quem chegar aqui sem nunca ter visto o projeto
consegue operar esta parte lendo só isto.

## 1. O que é, e onde mora

Duas portas de saída para o Adrian comandar o sistema de fora do PC:

| Peça | O que é | Sobe por |
| --- | --- | --- |
| **App** (PWA) | página instalável no celular: a Vila animada em tela cheia, e as outras áreas como objetos dela (ver abaixo) | tarefa `NeuralFights_app_celular` (a cada 10 min) → `app_celular.cmd` |
| **Bot** | bot de Telegram: avisos automáticos e uma tabela fechada de comandos | tarefa `NeuralFights_bot_telegram` → `bot.cmd` |

Tudo vive em `remoto/`:

- `api_http.py` — o servidor do app (rotas, pareamento, bilhetes de vídeo).
- `acoes.py` — as cinco ações antigas (pausar, retomar, parar, gerar,
  publicar) e as guardas de publicação. O 1º passo é `preparar` e o 2º é
  `confirmar` (o servidor chama os dois).
- `comandos_app.py` — o **catálogo** dos outros controles (fichas
  declarativas: campos, guardas, texto de confirmação).
- `tarefas.py` + `publicacao_filha.py` — trabalho pesado como processo
  desligado do servidor, com log em arquivo.
- `vila_nova.py` (desenho + vida da Vila) e `vila_dados.py` (o texto:
  fábricas, travas, placar).
- `comandos.py`, `bot.py`, `api.py`, `relatorios.py`, `apurador.py` — o bot.
  O `/publicar` do bot **não publica** (ver §3.3).
- `vigia_tailnet.py` — a vigia do tailnet, no laço do bot (ver §4).
- `decisoes.py` + `app/decisoes.js` — a **árvore de decisões** do Adrian
  (28/09), uma aba por projeto no app. A fonte é o repositório:
  `decisoes/<projeto>/<id>.json` (ver §3.7).
- `app/` — a PWA (`index.html`, `app.js`, `vila.js`, `comandos.js`,
  `decisoes.js`).
- **Desde 28/09 a Vila é a tela inteira** (pedido do Adrian: "o app focado
  na vila, e as outras entram de forma temática"). Não há mais barra de
  abas. Uma prateleira de madeira embaixo tem seis objetos:
  - 📌 Avisos (`tela-quadro`): o estado, o Controle (pausar, retomar,
    parar), a próxima postagem, fábricas, erros e paralelismo;
  - 📓 Diário;
  - 🎞 Cinema (vídeos, gerar e publicar);
  - 🛠 Bancada (Comandos, com a zona de perigo);
  - 📜 Pergaminhos (relatórios);
  - 📖 Grimório (Decisões): a capa abre e a página vira.

  Cada objeto abre por cima da Vila (ela fica parada atrás), e o "‹ Vila"
  ou o voltar do Android fecham (`history.pushState`). As animações são CSS
  puro e respeitam `prefers-reduced-motion`. Nenhum id sumiu do HTML:
  `test_app_vila_objetos.py` confere que todo id que o JS procura existe e
  que cada área tem objeto. O zoom inicial enche a altura, com teto de 3x,
  e por isso a arte do PC aparece ampliada (e um pouco borrada): mais
  nitidez pede fundo em resolução maior, e isso é da parte painel-e-vila.
  A prova de tela está em `prova_vila_objetos.py`, no scratchpad da sessão.

Estado em disco, em `%LOCALAPPDATA%\neural-fights\`: `app_celular.json`
(aparelhos pareados, só o hash do token), `app_celular_acoes.jsonl` (rastro),
`app_celular_em_voo.json` (publicações sem desfecho), `app_celular_tarefas/`
(uma pasta por tarefa), `remoto.json` (token do bot), `decisoes.lock` e
`decisoes_midia\<id>\` (mídia copiada de pasta temporária; a mídia nunca vai
para o git).

**Rede:** o servidor escuta só em `127.0.0.1:8931` e quem o publica é o
`tailscale serve` (`https://desktop-tgti3ek.tail63af85.ts.net`, *tailnet
only*). A porta **8765 é proibida** no código: é a do login OAuth do YouTube,
e um servidor esquecido nela já quebrou o login.

## 2. Como rodar e conferir sem publicar nada

```bash
python -m pytest remoto/ -q --basetemp=E:/projetos-wt/_pytest_app/x   # 517 testes (28/09)
python -m ruff check remoto/
python -m remoto.api_http --local --porta 8934 --acoes                # instância de teste
python -m remoto.api_http --parear      # código de 6 dígitos (5 min, uma vez)
python -m remoto.api_http --aparelhos   # id, nome, desde
python -m remoto.api_http --em-voo      # publicações sem desfecho
python -m remoto.tarefas                # tarefas recentes e como terminaram
python -m remoto.decisoes arvore [--projeto P]      # a árvore em texto
python -m remoto.decisoes listar [--projeto P] [--situacao pendente]
python -m remoto.decisoes adicionar --projeto builds --titulo "..." --pergunta "..." \
    --opcao "id=Rótulo|descrição" --opcao "outro=Outro (comente)" \
    --midia "E:\x.mp4|ANTES" [--copiar] [--depende "decisao=opcao"] [--commit]
python -m remoto.decisoes responder <id> <opcao> [--comentario C] [--sem-commit]
python -m remoto.decisoes gerar          # regenera os READMEs e os blocos das sessões
python -m remoto.decisoes onde
```

Opção cujo rótulo diz "(comente)" ou "(diga ...)" exige comentário.
`--depende "x=*"` quer dizer "x decidida, com qualquer opção". Mídia de pasta
temporária entra com `--copiar`. Só entram mp4, webm, png, jpg e webp.

Use **sempre** `--basetemp` no `E:` — o `C:` vive perto de encher, e a falha
"intermitente" da suíte em 17/09 era disco cheio.

**Não suba o servidor à mão na porta 8931.** Se ele cair, a tarefa do
Agendador o levanta em até 10 minutos. Para trocar de versão: pare o processo
e rode `app_celular.cmd` (ou espere a tarefa). Reinício fora de `:25–:55`, que
é a janela da postagem — e conte o tempo de subida: com a máquina carregada,
em 27/09 o app levou 10–12 min do processo parado até escutar na 8931.

A prova de tela roda em Chrome headless com perfil temporário
(`patchright`, `channel="chrome"`). Atenção: `page.evaluate` do patchright roda
em contexto **isolado** — ele não enxerga as variáveis da página; confira pelo
DOM e clicando.

## 3. Decisões do Adrian que valem como lei

1. **Só dentro do Tailscale.** `tailscale serve` sim; `tailscale funnel`
   (público) **nunca**.
2. **Pareamento por código** de 6 dígitos, uma vez, 5 minutos. O disco guarda
   só o hash do token; o token existe no celular.
3. **Publicar pelo app é só de builds**, e sempre como `public`. Histórias
   têm caminho próprio (`publicar_historia`), porque a ordem das partes é da
   grade. **Só o app publica pelo celular** (Adrian, 28/09/2026): o
   `/publicar` do bot responde que é pelo app e não toca em nada; o
   `/confirmar` saiu do bot. Isso também confirma o `--publicar` do app.
   Sem destino dito, vão **os dois** (YouTube e TikTok; `acoes.DESTINO_PADRAO`,
   decisão dele no mesmo dia). A tela do app sempre pergunta.
4. **Dois passos** em tudo que não se desfaz: o 1º pedido devolve um texto de
   confirmação e um código de 60 s; só o 2º executa, e ele **reavalia as
   guardas**. O `/gerar` e o `/parar` do bot ainda são de um passo só.
5. **Zona de perigo** (apagar mídia do Espelho, regenerar banco, esquecer ou
   trocar conta) só existe com `--perigosas` **e** digitando o nome do alvo.
6. **Nada de interface no celular**: logins, OAuth, Oficina, janelas do jogo e
   `os.startfile` ficam no PC.
7. **As decisões dele são uma árvore no git** (28/09/2026). Formato e regras:
   - Um arquivo por decisão em `decisoes/<projeto>/<id>.json`, com
     indentação 2, chaves ordenadas e LF. Projetos: `geral`, `builds`,
     `historias`, `publicacao`, `metricas`, `app-e-bot`, `painel-e-vila` e
     `jogo-zombie`.
   - A decisão fica `bloqueada` até os `depende_de` estarem decididos com a
     opção certa. Quando ele troca uma já tomada, tudo o que dependia dela
     vira `a_rever` (em qualquer nível) e fica assim até ele responder de
     novo.
   - O `historico` só cresce.
   - Cada resposta:
     - acrescenta uma linha em `decisoes/_eventos.jsonl` (o orquestrador vigia);
     - regenera `decisoes/<projeto>/README.md` e o bloco `decisoes:inicio/fim`
       de cada `docs/sessoes/<parte>.md` (as gerais entram em todas);
     - commita **por caminho**, com "decisão(<projeto>): <título> → <opção>".
   - O doc de sessão que tiver outra mudança por commitar fica fora do
     commit. O bloco dele fica escrito e entra num commit seguinte.
   - `index.lock` gera nova tentativa. Commit que falha não desfaz a decisão.
   - A mídia não vai para o git: o JSON aponta para o arquivo (caminho do
     repositório, `%LOCALAPPDATA%\...` ou absoluto), e a tela avisa "mídia
     não existe mais".

## 4. Armadilhas medidas (já quebraram)

- **PIPE mata o filho.** Com a saída do `main.py` num pipe do servidor, o
  servidor que reinicia mata a publicação no meio — inclusive depois do clique.
  Por isso a filha escreve em **arquivo** e roda desligada (`DETACHED` +
  breakaway do job). Há teste com job "mata ao fechar" provando os dois lados.
- **"YouTube: ..." não é sucesso.** O Studio devolve "cliquei em publicar, mas
  não confirmou… RASCUNHO" com código 0. Use `youtube_web.confirmado` e
  `tiktok.confirmado`; hoje o `main.py publicar` ainda imprime `A CONFERIR` e
  sai com **código 3**.
- **Lista "a conferir" vazia é uma afirmação.** `desfecho.a_conferir()`
  **levanta** quando não consegue ler. Tratar isso como "ninguém bloqueado"
  reposta todo mundo. O app falha fechado: **tudo que não dá para ler recusa**.
- **`travas.ocupada()` pega a trava** por um instante — um celular perguntando
  a cada segundo faria o dono da trava desistir. Use a sonda de leitura
  (`acoes.trava_ocupada`); há teste que falha se alguém chamar a outra.
- **`panorama.resumo()` leva ~159 s** na primeira conta: o placar roda em
  thread e é servido com a idade. Nunca dentro do pedido.
- **Partes cortadas** viram `X:corte01` no ledger e na marca: compare com
  `acoes.mesmo_video`, nunca com `==`.
- **Heredoc do bash come a barra invertida** ao escrever patches: use a
  ferramenta Write.
- **O Markdown do Telegram engole texto com dois `_`** (qualquer id do
  projeto): vira itálico. Aviso que leva id sai escapado
  (`acoes._escapar_markdown`) ou em texto puro (`Bot.avisar_todos`).
- **Depois de reiniciar a máquina, o app pode ficar fora do tailnet sem
  erro nenhum.** Em 28/09, no boot das 07:22, o cliente da bandeja
  (`tailscale-ipn.exe`, que a pasta Inicializar comum abre no logon) não
  subiu. Sem ele o `tailscaled` fica em `NoState` e o `tailscale serve
  status` diz "No serve config". O servidor seguia respondendo em
  `127.0.0.1:8931`, só que o celular não o alcançava. Abrir o
  `tailscale-ipn.exe` resolveu em 11 s, e a configuração do `serve` voltou
  sozinha, ainda "tailnet only". Nada de rodar `tailscale serve` de novo.
  Para conferir: `tailscale status` tem de sair de `NoState`, e a URL
  `*.ts.net` tem de responder 200. Desde 28/09 isso tem vigia
  (`vigia_tailnet.py`, no laço do bot, a cada 2 min):
  - ela confere o backend `Running`, o `serve` apontando para
    `127.0.0.1:8931` e o `funnel` desligado;
  - avisa no Telegram uma vez por ocorrência (um tropeço só não conta, o
    funnel conta na hora) e avisa de novo quando volta;
  - o único conserto que faz é abrir o `tailscale-ipn.exe` quando o backend
    está parado e a bandeja fechada; depois espera até 30 s e diz o que fez;
  - só roda `status --json`, `serve status --json` e `tasklist`, e há teste
    que varre o fonte atrás de `funnel`, `set`, `up` e `--bg`;
  - desliga com `"vigiar_tailnet": false` no `remoto.json`.
- **O modo "rodar sem login" (unattended) do Tailscale NÃO está ligado.** O
  Adrian decidiu ligar em 28/09 (`tailscale set --unattended=true`; a 1.102.4
  aceita a opção). O agente não pôde rodar o comando: a permissão da sessão
  barrou. Fica para o Adrian rodar à mão. Depois disso, conferir o backend
  `Running`, o `serve status` intacto e "tailnet only".
- **Nos testes do bot, `comandos._rodar` é um `Popen` de verdade.** O
  `/publicar` antigo chamava o `main.py publicar` real por ali. O fixture
  `bot` de `test_acoes.py` troca esse caminho, as guardas, o disparo e a
  filha por bombas: se o bot tocar em qualquer um deles, o teste falha.

## 5. Pendências e o que não fazer

- **Resolvido em 27/09/2026: processos desatualizados.** O bot rodava desde
  20/09 (PID 6120) e o app desde 27/09 19:18 (PID 13356), os dois sem o
  9d09759 (meta por plataforma; o relatório das 21h tinha mostrado
  "✓ histórias: 11/10"). Reiniciados pelos lançadores com o `remoto/` do HEAD
  518e6e8 (o fc17986, das 23:33, não toca em `remoto/`): app
  às 23:09 (PID 18260, escutando entre 23:19 e 23:22), bot às
  23:56 (PID 1560). Todo bot que sobe manda "🤖 bot no ar" aos autorizados
  (`bot.py:219`), e este também mandou. O `relatorios.metas()` do código novo,
  montado sem enviar às 23:23, mostra "histórias: youtube 6/10 · tiktok 7/10"
  e "builds: youtube 3/10 · tiktok 2/10". O "11/10" não aparece mais.
- **Confirmado pelo Adrian em 28/09/2026: o `--publicar` do app fica.** A
  divergência era esta: a decisão de 17/09 dizia `--acoes` sem `--publicar`,
  mas o `app_celular.cmd` (a101a2e) já subia com `--publicar --perigosas`
  desde pelo menos 24/09. Ele respondeu que "só o app" publica pelo
  celular, o que confirma o `--publicar` do app e tira o publicar do bot.
- **Resolvido em 28/09/2026: o `/publicar` do bot sem as guardas do app.**
  Antes ele chamava o `main.py publicar` direto, num passo só: sem "em voo",
  sem a lista "a conferir", sem a janela da grade, sem olhar o `postar.py`,
  e sem `--visibilidade`, então o YouTube subia privado
  (`publicacao.json:48`). Medido com os testes novos rodando contra o código
  antigo: 10 de 10 falharam. Nos 10, o bot disparou o `main.py publicar`
  sozinho, inclusive com o app publicando o mesmo vídeo. Agora ele usa
  `acoes.preparar` + `acoes.confirmar` (as funções do servidor), sobe como
  público e dá a vez: com o app e o bot atrás do mesmo vídeo, só um sai
  (teste com os dois confirmando ao mesmo tempo). **No mesmo dia o Adrian
  decidiu que só o app publica:** o `/publicar` do bot passou a só
  responder isso, e o `/confirmar` saiu. Do d68523e fica o `acoes.confirmar`,
  que o servidor usa.
- **Resolvido em 28/09/2026: a linha "`tailscale serve` sim, `funnel`
  nunca"** está no `README.md` da raiz (seção "O celular") e no
  `remoto/README.md`, que deixou de dizer que o app precisaria de porta
  aberta.
- **Conferido em 28/09/2026: nenhuma tarefa deste projeto sobe no logon.**
  Das 36 tarefas fora de `\Microsoft\`, as 32 do projeto rodam pelo
  `oculto.vbs`, sem janela, inclusive app, bot e Vila (de 10 em 10 min). As
  duas únicas com gatilho de logon são do Opera GX e da Realtek. Na pasta
  Inicializar e nas chaves `Run` não há nada do projeto; o Tailscale sobe
  pela pasta Inicializar comum.
- **Novo em 28/09/2026: a árvore de decisões** (a lei está em §3.7).
  - A mídia sai por id do item e índice, nunca por caminho. O `GET
    /api/decisao/<id>/midia/<n>` devolve o mesmo bilhete de 10 min dos
    vídeos, e o `/v/` serve por Range: 206, `Content-Range`, e 416 para
    intervalo fora do arquivo. O `Content-Type` vem da extensão; imagem sem
    Range vem inteira, com 200.
  - Responder exige o token e não depende de `--acoes` (não executa nada).
    Arquivo de decisão ilegível, ou ciclo na árvore, recusa em toda leitura.
  - Semeada com 24 decisões: 18 que ele já tinha tomado em 27–28/09
    (`decidida`, com a data) e 6 à espera dele. Três delas estão
    `bloqueadas`: o Chão e o Hitstop atrás do Palco, e a 00077 atrás do Som
    real.
  - Prova de tela clicando, na instância 8934 (cópia das decisões):
    - a árvore aparece em 3 níveis, com as cores;
    - o Som real toca e o pulo para o meio segue dos 16 s;
    - a bloqueada diz o que falta e não deixa escolher;
    - trocar a Ferramenta avisa que vão para "a rever" a Origem da arte e
      o Visual do lutador;
    - responder Palco = Seguir desbloqueia o Chão e o Hitstop;
    - a imagem aparece; os 12 duelos do zombie só com "semente N";
    - foram 26 respostas 206.
  - Com mais de 6 vídeos no item, eles só carregam ao tocar
    (`preload="none"`).
  - **Não feito, e é do Adrian:** a linha em cada `.claude/agents/<parte>.md`
    ("antes de começar, ler `decisoes/<parte>/` e o bloco da sessão;
    decisão vigente do Adrian manda"). São os arquivos de configuração dos
    agentes, e o pedido veio por mensagem de agente. O bloco gerado já está
    em cada `docs/sessoes/<parte>.md`, que todo agente lê primeiro.
- **Resolvido em 28/09/2026: o monitor do Agendador não olhava a geração
  noturna.** O `_linhas_do_agendador` (relatório de funcionamento) conferia
  as tarefas da criação das histórias, as 10 da postagem e o bot, e dizia
  "✓ 25 tarefas ativas e confiáveis". As cinco `NeuralFights_gerar_HH`
  (bdfa125) e a do app ficavam de fora. Agora ele confere as da geração
  pelas horas do `geracao.json` e pelo nome de `tarefas_noite`, e não cobra
  se ela estiver desligada (`ativo`). Na máquina real: 31, todas confiáveis.
  Lista que não se consegue ler vira aviso, em vez de sumir do total. A
  `NeuralFights_vila_flutuante` continua fora: é da parte painel-e-vila.
- **28/09/2026, a máquina reiniciou às 07:22.** As tarefas trouxeram de volta
  o app às 07:29 (PID 996) e o bot às 07:32 (PID 1620), os dois já com o
  d68523e, sem reinício à mão. O Tailscale ficou em `NoState` até 07:43
  (ver §4); depois disso a URL `*.ts.net` voltou a responder 200. Às 07:55
  o bot foi reiniciado pela tarefa, só ele, para o monitor novo (21ce589)
  valer no relatório das 09:00: PID 4648, "no ar" às 07:56:21. O app
  (PID 996) seguiu no ar, e o monitor dele fica para a próxima subida.
- **Mudou em 28/09/2026: o relatório de metas conta por dia de grade**
  (06:37 → 00:37 do dia seguinte), pela regra da conferência (fc17986). A
  recuperação das 23:37 que sai às 00:10 conta no dia anterior, e o dia em
  curso aparece como ⏳, não ✗. Ver §6: a regra vem de funções internas da
  `conferencia.py`.
- **Falta conferir o desfecho da tarefa `20260927-191533-3cf268`.** Quem
  roda `--em-voo` e `python -m remoto.tarefas` é o Adrian, porque a
  permissão foi barrada para os agentes. Um indício só: a subida das 23:11
  não imprimiu "ATENÇÃO: … esperando conferência" nem "retomei a vigia".
  Isso não prova nada, porque uma `Recusa` na leitura também é calada.
- O app **não** mata tarefa: um `kill` no meio de um upload deixa estado pela
  metade. Para frear, use Pausar/Parar, que o worker obedece.
- **Não** apague `vila/` (motor e Oficina): o painel do PC e a arte "clássico"
  da janela flutuante ainda dependem dele. A Vila antiga saiu só do app.
- **Não** mexa em `random_builds/builds/publicar/*` a partir daqui: aquilo é de
  outra sessão; o app **consome** aquelas funções.
- Controle novo = **ficha nova no catálogo**, nunca botão novo no JavaScript.
  Se ele gasta conta compartilhada, declare `perfis` (guarda de perfil ocupado)
  e ponha o nome em `comandos_app.PESADAS` (teto por hora).

## 6. Contratos com as outras partes

| Arquivo / recurso | Quem manda | Como o app entra |
| --- | --- | --- |
| `_tiktok_a_conferir.json` e `_youtube_a_conferir.json` | `builds.publicar.desfecho` | lê e escreve **sob a trava** `desfecho.nome_da_trava(<destino>)`; a marca do app leva `"app": <chave>` e só ela é retirada pelo app |
| `publicados.jsonl` (ledger) | `builds.publicar.metricas` | o app **só lê**; quem grava é o publicador, sob `ledger__<canal>` |
| `atividade.jsonl` (diário) | `builds.atividade` | o app lê; escreve **uma** linha (`etapa app.a_conferir`) quando marca algo a conferir |
| travas de perfil | `builds.travas` | só a sonda de leitura |
| `app_celular_*.json(l)` e as tarefas | **esta sessão** | escrita sob `trava_arquivo`, reentrante por thread |
| `decisoes/_eventos.jsonl` (no repositório) | **esta sessão** escreve (append, uma linha por resposta: `projeto`, `id`, `titulo`, `opcao`, `opcao_rotulo`, `comentario`, `em`, `anterior`, `a_rever`) | o **orquestrador** vigia; os itens novos ele registra pela CLI `python -m remoto.decisoes adicionar` |
| bloco `decisoes:inicio/fim` em cada `docs/sessoes/<parte>.md` | **gerado** por `remoto/decisoes.py` | cada parte lê como entrada; não edite à mão (é regenerado a cada resposta) |
| grade de postagem | `ferramentas/postar.py` | o app respeita a janela (−20/−25/−40 min conforme o destino, +18 min) e recusa se `postar.py` estiver vivo |
| dia de grade | `builds.publicar.conferencia` | `relatorios.metas` usa `_horario_da_grade`, `_dia_de_grade`, `_abertura_e_fechamento` e `dia_de_grade_fechado`, todas atrás de `relatorios._conferencia()`. As três primeiras são **internas** de lá: se a conferência as renomear, o `/metas` responde "falhou" (e os testes do remoto acusam). Pedido em aberto: uma função pública `dia_de_grade(instante)` |
