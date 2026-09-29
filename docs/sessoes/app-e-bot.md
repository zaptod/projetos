# App do celular e bot do Telegram

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/app-e-bot/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

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
- ⏳ **Grok: por onde entra na roda?** — Você pediu o Grok na roda das IAs. O login é seu (conta compartilhada não). Por onde? `ias-grok-acesso`

**App e bot**
- ✅ **Quem publica pelo celular** — Só o app (28/09/2026) `quem-publica-pelo-celular`
- ✅ **Destino padrão da publicação** — YouTube e TikTok (28/09/2026) `destino-padrao`
- ✅ **Tailscale sem login (unattended)** — Sim, ligar (28/09/2026) · “falta ele rodar o comando: tailscale set --unattended=true (a permissão do agente barrou)” `tailscale-unattended`
- ✅ **Onde fica pausar / retomar / parar** — Na Bancada, junto dos comandos (28/09/2026) `controle-onde`

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
  `decisoes/<projeto>/<id>.json` (ver §3.7). Tem também o **leitor de
  decisões tomadas** (§8): o que cada resposta dele gerou.
- `orquestrador.py` + `app/orquestrador.js` — a **Mesa de comando** (28/09):
  o orquestrador publica o que faz, o app mostra e manda comandos, e a
  sonda de uso roda no servidor (ver §7).
- `app/` — a PWA (`index.html`, `app.js`, `vila.js`, `comandos.js`,
  `decisoes.js`, `orquestrador.js`).
- **Desde 28/09 a Vila é a tela inteira** (pedido do Adrian: "o app focado
  na vila, e as outras entram de forma temática"). Não há mais barra de
  abas. Uma prateleira de madeira embaixo tem sete objetos:
  - 📌 Avisos (`tela-quadro`): o estado, a próxima postagem, fábricas,
    erros e paralelismo;
  - 📓 Diário;
  - 🎞 Cinema (vídeos, gerar e publicar);
  - 🛠 Bancada: o **Controle** (pausar, retomar, parar) em cima, as
    tarefas e os Comandos, com a zona de perigo. O Controle saiu dos Avisos
    em 28/09 (decisão `app-e-bot/controle-onde`: "Na Bancada");
  - 📜 Pergaminhos (relatórios);
  - 📖 Grimório (Decisões): a capa abre e a página vira;
  - 🗺 Comando (`tela-orquestrador`): a Mesa de comando, um mapa de
    campanha que se desdobra sobre a mesa de guerra (§7).

  Com sete objetos, cada um tem ~55 px a 390 px de largura: rótulo em
  10 px numa linha só (medido na prova: os sete cabem).

  Cada objeto abre por cima da Vila (ela fica parada atrás), e o "‹ Vila"
  ou o voltar do Android fecham (`history.pushState`). As animações são CSS
  puro e respeitam `prefers-reduced-motion`. Nenhum id sumiu do HTML:
  `test_app_vila_objetos.py` confere que todo id que o JS procura existe e
  que cada área tem objeto.
- **A Vila do app é nítida e dobrada desde 28/09** (painel-e-vila,
  `painel/flutuante/retrato.py`): o PC manda a Vila em pé, as duas metades
  do mundo em fileiras, desenhada em 3x (`/vilanova-retrato.webp`, e o atlas
  em `/vilanova-atlas.png?escala=3`, com os patos). As rotas de 1x continuam
  para a casca antiga. O canvas usa até 3 pixels por px (antes, 2). O
  placar virou plaquinhas da madeira da prateleira e fica no céu, fora da
  cena; a lupa (−/+) é uma aba presa na prateleira; o cartão do escolhido
  sobe quando o prédio está na metade de baixo. Como a câmera abre (perto
  ou a Vila inteira) é a decisão `painel-e-vila/vila-zoom-celular`, lida
  pelo servidor (`vila_nova.enquadramento`); pendente = perto. Dois
  defeitos achados na prova e consertados: o toque rodava duas vezes
  (touchend + o mouseup de compatibilidade) e desmarcava o prédio; o
  Pergaminho abria vazio ("Escolha um pergaminho") e agora abre no primeiro.

Estado em disco, em `%LOCALAPPDATA%\neural-fights\`: `app_celular.json`
(aparelhos pareados, só o hash do token), `app_celular_acoes.jsonl` (rastro),
`orquestrador\` (a Mesa de comando, §7),
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
python -m pytest remoto/ -q --basetemp=E:/projetos-wt/_pytest_app/x   # 598 testes (28/09, noite)
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
python -m remoto.decisoes tirar-dependencia <id> <decisao> --nota N   # aresta errada sai; a resposta fica
python -m remoto.decisoes onde
python -m remoto.decisoes leitor [--todos] [--projeto P] [--json]    # respostas não lidas (§8)
python -m remoto.decisoes leitor marcar <N|id@em|projeto/id> --gerou tarefa:<id>|no:<projeto/id>|nada \
    [--gerou ...] [--nota N] [--sem-commit]                          # o que ela gerou; vira lida
python -m remoto.orquestrador onde | estado | config | uso | pendentes   # a Mesa (§7)
python -m remoto.orquestrador capacidade --max-paralelo N | --teto P | --forca-total on|off \
    [--modo M] --fonte chat|app [--porque "palavras dele"]            # vira regra (§7)
python -m remoto.orquestrador eu "no que a sessão principal está"
```

Instância de teste que não toca o real: `NF_ORQUESTRADOR_PASTA` (cópia do
estado do orquestrador) e `NF_DECISOES_REPO` (um clone do Grimório; a CLI
do orquestrador que a prova chama commita nele, não no repositório).

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
   - O que cada resposta gerou fica no próprio nó, em `consequencias[]`
     (§8). "Lida" não tem arquivo: sai dessa lista.

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
| `decisoes/_eventos.jsonl` (no repositório) | **esta sessão** escreve (append, uma linha por resposta: `projeto`, `id`, `titulo`, `opcao`, `opcao_rotulo`, `comentario`, `em`, `anterior`, `a_rever`) | o **orquestrador** vigia (o `esperar` acorda com `decisao_nova`), lê pelo `leitor` e marca pelo `leitor marcar`; os itens novos ele registra pela CLI `python -m remoto.decisoes adicionar` |
| `consequencias[]` em `decisoes/<projeto>/<id>.json` | o **orquestrador**, só pela CLI `leitor marcar` (e a Mesa, sozinha, nas respostas de capacidade) | o Grimório mostra "o que isto gerou" e o selo "não lida ainda" (§8) |
| `%LOCALAPPDATA%\neural-fights\orquestrador\` | o **orquestrador** escreve `estado.json`, `decisoes_orquestrador.jsonl` e `comandos_aplicados.jsonl` pela CLI; o `aplicado` escreve `config.json` e `config_historico.jsonl`; **esta sessão** escreve `comandos.jsonl`, `uso*.json(l)` e `acessos.json` | ver §7; escrita atômica, sob `orquestrador.lock` |
| bloco `decisoes:inicio/fim` em cada `docs/sessoes/<parte>.md` | **gerado** por `remoto/decisoes.py` | cada parte lê como entrada; não edite à mão (é regenerado a cada resposta) |
| grade de postagem | `ferramentas/postar.py` | o app respeita a janela (−20/−25/−40 min conforme o destino, +18 min) e recusa se `postar.py` estiver vivo |
| dia de grade | `builds.publicar.conferencia` | `relatorios.metas` usa `_horario_da_grade`, `_dia_de_grade`, `_abertura_e_fechamento` e `dia_de_grade_fechado`, todas atrás de `relatorios._conferencia()`. As três primeiras são **internas** de lá: se a conferência as renomear, o `/metas` responde "falhou" (e os testes do remoto acusam). Pedido em aberto: uma função pública `dia_de_grade(instante)` |

## 7. A Mesa de comando (o orquestrador no app, 28/09/2026)

Pedido do Adrian: ver no que o orquestrador trabalha e controlar fluxo,
acessos, decisões, capacidade e agentes paralelos, com os limites de sessão
e semana à vista. Desenho: `~/.claude/plans/orquestrador-no-app.md`.

**Princípio.** O orquestrador **publica** o estado em arquivos, pela CLI; o
app **mostra** e **grava comandos**; o orquestrador lê (`pendentes`), aplica
e registra (`aplicado`). A config só muda no `aplicado`. A tela mostra cada
comando como pendente, aplicado ou recusado (com o motivo), e o valor pedido
aparece ao lado do valor em vigor. A pasta é
`%LOCALAPPDATA%\neural-fights\orquestrador\`; o `NF_ORQUESTRADOR_PASTA` a
troca, para a instância de teste.

| arquivo | quem escreve |
| --- | --- |
| `estado.json` (agora, fila, concluídos de hoje, modo, `principal`, `atualizado_em`) | CLI do orquestrador |
| `decisoes_orquestrador.jsonl` | CLI `decisao` |
| `config.json` + `config_historico.jsonl` | CLI `aplicado`, `capacidade` (e `modo`) |
| `comandos.jsonl` | servidor (`POST /api/orquestrador/comando` e o Contestar); a CLI `capacidade`, já aplicado, com `fonte: chat` |
| `comandos_aplicados.jsonl` | CLI `aplicado` e `capacidade` |
| `uso.json` + `uso_historico.jsonl` | a sonda do servidor |
| `acessos.json` | o servidor ao subir, ou a CLI `acessos` |
| `tarefas_historico.jsonl` (todo agente que terminou, uma vez; o `concluidos_hoje` se esvazia a cada dia) | a CLI, a cada escrita do estado |
| `decisoes_vistas.json` (a última linha do `_eventos.jsonl` que o `esperar` já mostrou) | o `esperar` |

**CLI do orquestrador:**

```bash
python -m remoto.orquestrador agente-inicio --parte P --titulo T [--da-fila ID] [--relato R] [--forcar]
python -m remoto.orquestrador relato <id> "uma linha"
python -m remoto.orquestrador agente-fim <id> [--situacao concluido|falhou|parado] [--commit H]...
python -m remoto.orquestrador fila adicionar --parte P --item T [--posicao N]
python -m remoto.orquestrador fila mover <id> subir|descer|topo
python -m remoto.orquestrador fila remover <id>
python -m remoto.orquestrador fila listar
python -m remoto.orquestrador decisao --titulo T --escolha E [--porque P] [--alternativa A] [--parte P]
python -m remoto.orquestrador eu "uma linha"          # a sessão principal: no que está agora
python -m remoto.orquestrador capacidade [--max-paralelo N] [--modo M] [--teto P] [--forca-total on|off] \
    [--fonte chat|app] [--porque "palavras dele"]      # instrução do Adrian: vira regra
python -m remoto.orquestrador modo um_por_vez|paralelo|forca_total   # operacional: NÃO vira regra
python -m remoto.orquestrador pendentes [--json]
python -m remoto.orquestrador aplicado <id> [--recusado MOTIVO] [--nota N]
python -m remoto.orquestrador esperar [--json]     # bloqueia até chegar comando; vale como pulso
python -m remoto.orquestrador config | estado | uso | pulso | sonda | onde
python -m remoto.orquestrador acessos [--conector NOME]... [--modo-permissao M]
```

- O `agente-inicio` **recusa** (código 3) em três casos:
  - passou da capacidade (`um_por_vez` = 1 agente; nos outros modos, o
    `max_paralelo`);
  - a fila está pausada;
  - o uso está acima do teto, fora da força total.

  O `--forcar` passa por cima, e só vale se o Adrian mandou.
- O padrão da config segue o Grimório: um por vez, teto de 50% e força total
  20 min antes de renovar. O Adrian respondeu as duas perguntas da Mesa às
  19:25 de 28/09:
  - `geral/forca-total-ainda-vale` → **ligada, 20 min antes de renovar**. Às
    ~18h o orquestrador tinha parado de usá-la; vale o Grimório, e a Mesa
    já nasce assim;
  - `geral/capacidade-pelo-app` → **substitui**: o que ele muda na Mesa vira
    a regra, e o orquestrador registra a mudança no Grimório.
- **Automatizado em 28/09 (noite): a capacidade vira regra sozinha.** Ao
  valer, cada mudança responde o nó dela, com commit por caminho:
  - `max_paralelo` e `modo` → `modo-de-trabalho` (1 agente efetivo = "um",
    mais = "paralelo", com "até N agentes" no comentário);
  - `teto_uso` → `teto-de-uso` (50 = "cinquenta"; outro número = "outro",
    com o número no comentário);
  - `forca_total` → `forca-total-ainda-vale` ("ligada" ou "só quando eu
    pedir").

  Vale pelos dois caminhos: o `aplicado` de um comando da Mesa (origem
  `mesa` no histórico do nó, com o aparelho) e o `capacidade --fonte chat`,
  para uma instrução dele no chat. O `capacidade` grava a config pelo mesmo
  `_mudar_config` do `aplicado` (com `config_historico`) e entra na lista
  de comandos já aplicado, com `fonte: chat`; o `aplicado` é escrito antes
  do comando, e o `esperar` nunca o vê como pendente. Com várias chaves
  numa instrução, o nó é respondido uma vez, com a config final (sem um
  "um por vez" no meio). Valor que não mudou não mexe no Grimório ("já
  estava assim"), nem regra que o nó já diz. Falha no Grimório nunca desfaz
  a config: vai para a nota do comando, que a tela mostra. O `modo` da CLI
  é **operacional** (ex.: a janela da força total) e não vira regra.
- **Consertado no mesmo dia: a aresta que derrubava a regra.** Responder
  `modo-de-trabalho` = paralelo (20:29) mandou `capacidade-pelo-app` para
  "a rever", porque ela dependia do modo (`=*`); a regra vale em qualquer
  modo. Com `decisoes tirar-dependencia` (f459fde) a aresta saiu e o nó
  voltou para "decidida" com a mesma resposta de 19:25; o histórico ganhou
  uma linha `origem: correcao`, com a nota. A mesma aresta, em
  `forca-total-ainda-vale` → `teto-de-uso`, saiu também (7e345d4): sem isso,
  mudar o teto pela Mesa mandaria a força total para "a rever". Há teste
  lendo os nós reais.
- **Sem `config.json`, a Mesa nasce como o Grimório diz**
  (`padrao_do_grimorio`). Antes nascia "um por vez", contra um Grimório que
  diz "paralelo" desde 20:29.
- **Perguntas abertas ao Adrian (28/09, noite), no Grimório:**
  - `geral/forca-total-pela-mesa`: o modo "Força total" tocado na Mesa vale
    até a janela renovar ou até ele desligar? Hoje vale até desligar e vira
    `modo-de-trabalho` = paralelo, com "força total" no comentário;
  - `geral/teto-da-semana`: hoje nada para quando a semana enche; só a
    sessão tem teto.
- O que o `aplicado` faz sozinho, por comando:
  - `priorizar`: reordena a fila;
  - `adicionar_a_fila` (`{parte, item}`) põe no fim, com `pedido: Adrian`;
    `tirar_da_fila` (id) tira, e recusa se o item não existe (desde 28/09,
    noite: antes a Mesa só subia e descia);
  - `parar_agente`: marca o agente como "parando". Quem para é o
    orquestrador, que depois roda `agente-fim --situacao parado`. Com um
    agente que não existe, o `aplicado` **recusa**, e o orquestrador
    registra com `--recusado`.
- **Fora do ar**: `estado.atualizado_em` com mais de 15 min. Todo comando da
  CLI conta como pulso, e o `esperar` pulsa a cada 5 min.
- **A sessão principal** (desde 28/09, noite; antes a Mesa só mostrava os
  agentes). No topo de Agora ficam:
  - o relato dela em uma linha, com a hora (`eu "..."`, em
    `estado.principal`);
  - o último movimento e o sinal de vida. Disparar, fechar, aplicar,
    recusar, decidir, pôr na fila e mudar a capacidade entram sozinhos na
    linha do tempo (as últimas 15);
  - o resumo "cabe mais um?": vagas ocupadas de N, a sessão contra o teto
    e a fila (pausada em vermelho).

  Agente sem relato há mais de 30 min ganha "sem notícia há X" na ficha.
- **Capacidade** mostra o que cada modo faz, o que a força total faz e o
  bloco **"No Grimório (vira regra)"**, com os três nós. Cada nó leva
  "bate" ou "diverge": diverge quando a Mesa vale uma coisa e o Grimório
  diz outra, ou quando o nó está "a rever". Embaixo fica o histórico das
  mudanças (`config_historico`), com a origem: app, chat ou orquestrador.
- **Limites** diz quando começa a força total ("a partir de 22:30") e se a
  sonda está ligada. "O que você mandou" diz a fonte de cada comando (pelo
  app ou pelo chat). O Grimório mostra no histórico de onde veio cada
  resposta: "pela Mesa de comando", "no chat", "correção".
- **Contestar** uma decisão do orquestrador cria o nó `contestada-<id>` no
  Grimório, pela mesma função do `remoto.decisoes adicionar --commit`
  (`decisoes.adicionar_e_commitar`):
  - o nó vai para a parte da decisão, ou para `geral`;
  - as opções são manter, trocar pela alternativa, ou outro caminho;
  - também grava um comando `contestar`, para o orquestrador ver.

**A sonda de uso** roda no servidor, a cada `sonda_min` do `config.json`
(padrão 10; 0 desliga). É a técnica do `~/.claude/vigia_uso.py`: `claude.exe
-p ok --model haiku --output-format stream-json --verbose`, lendo o
`rate_limit_event`. O `uso_sessao.json` do vigia entra como fonte extra
quando é mais novo. Medido em 28/09: 7,4 s por sonda.

**Nunca um número velho como se fosse atual.** A tela mostra "sem medição
desde HH:MM", sem barra nenhuma, quando:
- a última sonda falhou depois da medição;
- a medição passou de 25 min;
- a janela já renovou depois dela.

O gráfico do dia quebra a linha em buracos de mais de 30 min.

**Acessos** (sem segredo):
- os agentes de `.claude/agents/*.md` (nome e descrição);
- os conectores e o modo de permissão, que o orquestrador declara
  (`acessos --conector`). Quando ele não diz, ficam os anteriores;
- o Remote Control, lido do `~/.claude/settings.json`;
- as contas de `builds.contas`, só com o nome e o destino
  (`identidade().rotulo`), sem caminho, id nem token. Há teste com um token
  falso no registro;
- o que o app dispara, com as chaves do servidor que subiu (pela CLI, as do
  `app_celular.cmd`).

**Fluxo**: mostra o de trabalho (fila → agora → feitos hoje) e o das builds.
O das builds é o mesmo `builds.pipeline.fluxo.snapshot` do `main.py fluxo` e
da página 🧭 Fluxo do painel, lido em segundo plano (`painel_dados.FLUXO`,
90 s).

**Vigiar os comandos** (o orquestrador, em background):
`python -m remoto.orquestrador esperar --json` sai quando há comando
pendente **ou resposta nova do Adrian** no `_eventos.jsonl` (desde 28/09,
noite: itens com `"tipo": "decisao_nova"`, ao lado dos comandos, que ganharam
`"tipo": "comando"`). Aplique, registre com `aplicado`, leia as respostas com
o `leitor` (§8) e rearme.

**Prova de tela (28/09):** 390×844, clicando, na 8934 com cópia do estado e
na 8935 vazia, com 0 erros de JS.
- Os 7 objetos cabem na prateleira.
- O `+` vira pendente; a CLI aplica, e a tela mostra 2.
- Descer um item reordena a fila.
- A mensagem recusada mostra o motivo.
- O Contestar vira nó, com commit no clone.
- Com a sonda falhando, aparece "sem medição desde 19:22".
- Com 62%, aparece o aviso do teto.
- Com 20 min sem pulso, aparece "fora do ar" e o selo vermelho na
  prateleira.
- O Controle está na Bancada, e não nos Avisos.
- O caso ZERO diz que o orquestrador nunca publicou.

**Prova de tela (28/09, noite: a Mesa completada):** 390×844, clicando, na
8934, com cópia do estado e um clone do Grimório (`NF_DECISOES_REPO`). Na
8935 vazia, 0 erros de JS. Telas em `E:\projetos-wt\_prova_mesa2\telas\`.
- `eu` aparece no topo com a hora, e o resumo diz "2 de 2 vagas · 24% da
  sessão · teto 50% · 3 na fila".
- Um relato de 45 min dá "sem notícia há 45 min".
- O `+` pela Mesa foi aplicado pela CLI. O `modo-de-trabalho` do clone
  ganhou uma resposta `origem: mesa`, com commit, e
  `capacidade-pelo-app` seguiu "decidida".
- Teto 60 pela Mesa virou `teto-de-uso` = outro, e a força total seguiu
  "decidida".
- `capacidade --teto 50 --max-paralelo 2 --fonte chat` saiu "pelo chat"
  na lista, sem nada pendente.
- Um nó respondido à mão com outra coisa aparece como "diverge".
- "Pôr na fila" pelo diálogo mostrou o pedido pendente e depois o item
  "pedido por Adrian". O ✕ pediu confirmação, e o item saiu.
- Limites: "força total a partir de 22:30".
- O histórico do nó no Grimório diz "pela Mesa de comando" e "no chat".

## 8. O leitor de decisões tomadas (28/09/2026, noite)

Pedido do Adrian pela Mesa, às 21:50: "Quero que você crie um leitor de
decisões tomadas, para saber se isso gera mais ramificações ainda". Desenho:
seção "Leitor de decisões tomadas" de `~/.claude/plans/orquestrador-no-app.md`.

**O que é.** Cada resposta dele (uma linha do `_eventos.jsonl`) é **lida**
pelo orquestrador, que registra o que ela gerou: uma tarefa da Mesa, um nó
novo (ramo) ou nada. O registro fica **no próprio nó**, em `consequencias[]`,
e vai para o git. "Lida" não tem arquivo próprio: uma resposta está lida
quando o nó dela tem uma consequência daquele evento ou de um mais novo. Ler
a última resposta cobre as anteriores (o toque duplo de 19:57:42/43 em
`sprites-animados` se resolve com uma marca). No mesmo segundo, quem desempata
é a `linha` do arquivo.

**`python -m remoto.decisoes leitor`** lista as não lidas, da mais velha para
a mais nova, com três sinais:
- (a) os nós que a opção `desbloqueia`, com a situação de cada um;
- (b) os nós que foram para `a_rever`;
- (c) `COMENTÁRIO — precisa de leitura`, quando ele escreveu texto livre: só
  uma leitura (LLM) diz se isso abre tarefa ou ramo.

Também avisa quando a resposta já foi trocada por outra, ou quando o nó
sumiu. Linha ilegível no `_eventos.jsonl` aparece como "LINHA ILEGÍVEL" e
nunca some. `--todos` mostra as lidas, com o que geraram; `--json` para
máquina.

**`leitor marcar <evento> --gerou ... [--gerou ...] [--nota N]`**:
- `<evento>` é `N` (a linha), `id@em` ou `[projeto/]id` (a última resposta
  daquele nó);
- `--gerou tarefa:<id da Mesa>`, `no:<projeto/id>` ou `nada` (o `nada` não
  combina com os outros);
- commita por caminho: "decisão(<projeto>): lida — <título> gerou …". Com
  `--sem-commit`, não commita;
- `no:X` **liga o ramo** a esta resposta por `depende_de` (decisão + a opção
  que ele escolheu), se ainda não estiver ligado. O ramo precisa existir
  (crie antes com `adicionar`). Ligar a uma resposta que não vale mais é
  recusado. Ciclo também é recusado, e nada é gravado;
- repetir a mesma marca não duplica nada.

Formato de cada item de `consequencias[]` (chaves ordenadas, como o resto):

```json
{"alvo": "e4957f28", "em": "2026-09-28T22:40:51", "evento": "2026-09-28T19:57:43",
 "linha": 19, "nota": "...", "opcao": "limpar-depois", "origem": "leitor",
 "tipo": "tarefa"}
```

- `tipo` é `tarefa`, `no` ou `nada`;
- `alvo` é o id da Mesa, `projeto/id` ou `""`;
- `evento` e `linha` dizem qual resposta foi lida;
- `origem` é `leitor`, `semente` ou `mesa`.

**A Mesa marca sozinha** as respostas de capacidade (`modo-de-trabalho`,
`teto-de-uso` e `forca-total-ainda-vale`, pelo `aplicado` ou pelo
`capacidade --fonte chat`). Elas nascem lidas, com `nada` e origem `mesa`: a
config já vale. A resposta e a marca saem num commit só, com a mensagem de
sempre. As duas primeiras (22:26 e 22:30) foram gravadas antes de existir a
`linha`, e continuam valendo.

**O `esperar`** também acorda com resposta nova e ainda não lida
(`"tipo": "decisao_nova"`; §7). O cursor fica no `decisoes_vistas.json`: sem
ele, o `esperar` começa do fim, porque o passado é do `leitor`.

**No Grimório (app):**
- cada decisão mostra o cartão **"O que isto gerou"**:
  - as tarefas, com o estado vindo ao vivo da Mesa: concluída, em andamento,
    parando, na fila, falhou, parada, "fora da Mesa" (id que ela não
    conhece) ou "Mesa ilegível" (nunca vira "nenhuma");
  - os ramos, que abrem ao tocar, mesmo de outro projeto (o "‹ Árvore" volta
    para a árvore dele);
  - "nada novo", com a nota. A nota de uma leitura aparece uma vez só;
- o selo **"não lida ainda"** fica no alto do nó até a marca, e aparece
  "não lida" na árvore;
- a árvore mostra "gerou: 1 tarefa · 7 ramos";
- cada aba tem o número de não lidas, e a raiz do projeto tem o cartão
  "N respostas suas ainda não lidas pelo orquestrador".

Para a tarefa não virar "fora da Mesa" no dia seguinte, a Mesa guarda todo
agente que terminou em `tarefas_historico.jsonl` (uma vez; o
`concluidos_hoje` se esvazia a cada dia). O agente que sai da fila guarda o
id do item (`da_fila`), e a decisão que apontou para o item o acompanha.

**Semeado em 28/09**: o que o orquestrador já tinha lido à mão entrou com
origem `semente`:
- `builds/som-real-16a` → nada (re-render agendado na madrugada, fora da
  Mesa);
- `palco-seguir` e `hitstop` → `ec0e8556`;
- `generation-00077` → `5c54c4b9`;
- `sprites-animados` → `e4957f28`;
- `painel-e-vila/tarefa-da-vila-acorda-o-pc` e `aposentar-vila-pixel` →
  `e4957f28`;
- `cara-da-oficina` → o nó `aposentar-vila-pixel`;
- `jogo-zombie/duelo-e-isso` → `13f6a1e6` e os 7 nós `duelo-*`;
- `app-e-bot/controle-onde` → `676aeab8`;
- as 4 de `publicacao/*` → `8a6e221f`;
- `geral/*` → nada.

Ficaram **10 não lidas**, para o orquestrador ler:
- `builds/chao-da-arena`;
- `builds/palco-ab-2` (a 16G);
- `painel-e-vila/vila-zoom-celular` (o comentário sobre deitar o celular
  precisa de leitura);
- as 7 respostas dos `duelo-*`.

**Prova de tela (28/09, noite):** 390×844, clicando, na 8934 (cópia da
Mesa e clone do Grimório, avisos num arquivo em vez do Telegram) e na 8935
vazia. Foram 25 conferências pelo DOM e 0 erros de JS. Telas em
`E:\projetos-wt\_prova_leitor\telas\`.
- As abas dizem Builds 2, Painel e Vila 1, Jogo zombie 7, Geral 0. A raiz
  de Builds diz "2 respostas suas ainda não lidas".
- Cara da Oficina → o ramo Aposentar; tocar abre o nó, que mostra
  `e4957f28` "concluída".
- Duelo: é isso? → 1 tarefa (`13f6a1e6`, concluída) e 7 ramos. O ramo
  "voz" tem "não lida ainda".
- `8a6e221f` aparece "em andamento", ao vivo.
- `leitor marcar` pela CLI commitou no clone. O Builds caiu para 1, e o
  Chão mostrou `59bf5cfb`: na fila, e depois em andamento, quando o
  orquestrador de verdade o disparou com `--da-fila`.
- Responder de novo pelo app devolveu "não lida ainda", e o que a resposta
  anterior gerou ficou lá. O `esperar --json` saiu com `decisao_nova`
  `chao-da-arena`.
- No caso ZERO, nenhum contador e nenhum cartão.
