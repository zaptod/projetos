# App do celular e bot do Telegram

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/app-e-bot/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (30/09/2026) · “30/09 11:43, pela Mesa de comando: paralelo, até 3 agentes” `modo-de-trabalho`
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
- ✅ **Fila: tarefas pesadas podem rodar de dia?** — Rodar de dia, 2 em paralelo (30/09/2026) · “Atualmente prefiro que rode de dia, eu estou trabalhando durante o dia, e de madrugada quando tem esse trabalho pesado o Pc faz muito barulho, por isso prefiro que esse trabalho pesado aconteça de dia, mas tome cuidado para não quebrar o processo, achei uma boa forma de encaixar isso, o ideal seria processar nos horários vagos tendo uma gordura boa pra semana, um planejamento como segunda fazemos as histórias e biuds da semana toda e dps ficamos apenas para mudanças” `fila-pesada-de-dia`
- ✅ **Lote: janela do trabalho pesado de dia** — 07h às 22h (recomendado) (30/09/2026) `lote-janela-de-dia`
- ✅ **Lote: em quais dias produzir** — Histórias seg–qua, builds seg–ter (recomendado) (30/09/2026) `lote-dias`
- ✅ **Lote: vídeo de até 6 dias** — Aceito; mudança crítica ganha re-render (recomendado) (30/09/2026) `lote-frescor`
- ✅ **Lote: estoque zero de madrugada** — Libera tudo (30/09/2026) `lote-estoque-zero-de-madrugada`
- ✅ **Lote: piso de reposição (qui–dom)** — 2 dias = 20 vídeos (recomendado) (30/09/2026) `lote-piso-de-reposicao`
- ✅ **Lote: como trocar da madrugada para o dia** — Esquema de dia validado 1 dia antes de desligar a madrugada; 1º lote seg 05/10 (recomendado) (30/09/2026) `lote-transicao`
- ✅ **Sprites: o que o Grok decide sozinho** — Aconselha; aprova só depois de calibrado (recomendado) (30/09/2026) `sprites-ia-juiz`
- ✅ **Contas extras de IA: quais** — 4 ChatGPT Free (30/09/2026) · “Quero achar uma forma de fazer com que essas contas sejam diferentes aos olhos da open aí, ou mudar o IP quando fazer a requisição, qualquer coisa assim mas a minha ideia é, tenho vários email Outlook, crio várias contas free, giro entre elas mudando o IP de requisição e consigo gerar imagens infinitas” `contas-ia-extras`
- ✅ **Contas de IA: como alternar** — Por papel; transborda quando a cota estoura (recomendado) (30/09/2026) `contas-ia-rodizio`
- ✅ **Perfis de navegador: mudar para o E:?** — Mover para o E: (recomendado) (30/09/2026) `perfis-para-o-e`
- ✅ **Imagens em volume: qual caminho dentro das regras** — Contas extras suas, cada uma com papel próprio, sem disfarce (30/09/2026) `contas-ia-caminho`
- ✅ **Codex e Gemini: o que delegar primeiro** — Consertos com teste (recomendado) (01/10/2026) `delegar-o-que-primeiro`
- ✅ **Codex e Gemini: quem confere o trabalho** — Validador + agente barato (recomendado) (01/10/2026) `quem-confere-delegado`
- ⏳ **Codex: commita ou só propõe** — O Codex pode commitar ou só entregar o diff? `codex-commita`
- ⏳ **Gemini CLI também, ou só o Codex?** — Conecto o Gemini pela linha de comando também? `gemini-cli-tambem`
- 🔒 1 bloqueada(s), esperando outra decisão: ver `decisoes/geral/README.md`

**App e bot**
- ✅ **Quem publica pelo celular** — Só o app (28/09/2026) `quem-publica-pelo-celular`
- ✅ **Destino padrão da publicação** — YouTube e TikTok (28/09/2026) `destino-padrao`
- ✅ **Tailscale sem login (unattended)** — Sim, ligar (28/09/2026) · “falta ele rodar o comando: tailscale set --unattended=true (a permissão do agente barrou)” `tailscale-unattended`
- ✅ **Onde fica pausar / retomar / parar** — Na Bancada, junto dos comandos (28/09/2026) `controle-onde`
- ✅ **Aviso no Telegram: comando da Mesa sem ninguém ouvindo** — Manter os dois avisos (o de parado e o de voltou) (29/09/2026) `aviso-no-telegram-comando-da-mesa-sem-ni`
- ✅ **O aparelho pareado em 17/09 ainda é seu?** — Esquecer o de 17/09 (29/09/2026) `o-aparelho-pareado-em-17-09-ainda-e-seu`
- ✅ **Mensagem para uma IA pelo app: direto ou com confirmação?** — Direto (como está): escrevi, foi (29/09/2026) `mensagem-para-uma-ia-pelo-app-direto-ou`
- ✅ **Sprites: onde você aprova** — Tela 'Conferir sprites' no app (recomendado) (30/09/2026) `sprites-ia-conferir`
- ✅ **Liberar o Claude com a sessão fechada** — Rodar o orquestrador sem janela (01/10/2026) · “Quero que seja tudo automatizado” `liberar-sem-sessao-aberta`

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
- `lote.py` — o lote da semana (estoque x alvo até segunda, piso, janela):
  um resumo para o /lote, o relatório de metas, o painel e o app (§14).
- `vigia_tailnet.py` — a vigia do tailnet, no laço do bot (ver §4).
- `claude_estado.py` — o **interruptor do Claude** (29/09, §12.2): liberado
  ou proibido, em `claude.json`; a sonda, o apurador e o orquestrador obedecem.
- `app/conversa.js` + as rotas `/api/correio*` — a **conversa com cada IA**
  (29/09, Vila das IAs fase 2, §10). O correio e o carteiro moram em `ias/`
  (`correio.py`, `carteiro.py`), fora de `remoto/`: o servidor só lê e
  escreve a caixa; quem abre navegador é o carteiro, em processo próprio.
  Desde 29/09 (tarde) a mesma tela tem o **🎨 Criar** (pedir imagem), a
  galeria e a tela cheia; o catálogo dos geradores é `ias/imagem.py` (§13).
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
`app_celular_em_voo.json` (publicações sem desfecho), `claude.json` +
`claude_historico.jsonl` (o interruptor do Claude, §12.2), `app_celular_tarefas/`
(uma pasta por tarefa), `remoto.json` (token do bot), `decisoes.lock` e
`decisoes_midia\<id>\` (mídia copiada de pasta temporária; a mídia nunca vai
para o git).

**Rede:** o servidor escuta só em `127.0.0.1:8931` e quem o publica é o
`tailscale serve` (`https://desktop-tgti3ek.tail63af85.ts.net`, *tailnet
only*). A porta **8765 é proibida** no código: é a do login OAuth do YouTube,
e um servidor esquecido nela já quebrou o login.

## 2. Como rodar e conferir sem publicar nada

```bash
python -m pytest remoto/ -q --basetemp=E:/projetos-wt/_pytest_app/x   # 671 testes (29/09, 15h)
python -m pytest ias/ -q --basetemp=E:/projetos-wt/_pytest_app/x      # 108 (correio, carteiro e imagem, §10 e §13)
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
python -m remoto.orquestrador vigia       # quem ouve os comandos agora (código 1 = ninguém; §9)
python -m ias carteiro [--uma-vez] [--duble]   # o carteiro do correio (§10); --duble não abre navegador
python -m ias correio <ia> [--enviar TEXTO] [--json]   # a caixa de uma IA
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
- **Script da casca que não chega some calado** (30/09, §15). A fila de
  escuta do servidor era 5; no Windows a conexão que passa da fila leva RST,
  e o `tailscale serve` troca a recusa por 502. O arquivo nem aparece no
  `app_celular.txt`. Sem o `conversa.js`, o cartão do prédio mostra só "Ver
  no diário". Para conferir no log: toda carga (`GET /`) tem de ter os seis
  `.js` logo depois. Uma lista de `.js` depois de `GET /sw.js` é o precache
  do service worker, não carga da página.
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
| `%LOCALAPPDATA%\neural-fights\orquestrador\` | o **orquestrador** escreve `estado.json`, `decisoes_orquestrador.jsonl` e `comandos_aplicados.jsonl` pela CLI; o `aplicado` escreve `config.json` e `config_historico.jsonl`; o `esperar` escreve `vigia.json` (o pulso, §9); **esta sessão** escreve `comandos.jsonl`, `uso*.json(l)`, `acessos.json` e `aviso_sem_ouvinte.json` | ver §7; escrita atômica, sob `orquestrador.lock` |
| bloco `decisoes:inicio/fim` em cada `docs/sessoes/<parte>.md` | **gerado** por `remoto/decisoes.py` | cada parte lê como entrada; não edite à mão (é regenerado a cada resposta) |
| `claude.json` + `claude_historico.jsonl` (o interruptor do Claude, §12.2) | **esta sessão**: o servidor (`POST /api/claude`) e a CLI `orquestrador claude` gravam, por `claude_estado.mudar` (atômico, sob `claude.json.lock`) | a sonda, o apurador, o `agente-inicio` e o `esperar` só **leem**, a cada vez |
| grade de postagem | `ferramentas/postar.py` | o app respeita a janela (−20/−25/−40 min conforme o destino, +18 min) e recusa se `postar.py` estiver vivo |
| estoque e lote da semana (§14) | `ferramentas/postar.py` (`estoque_do_lote`, `piso_de_alerta`) e `contos.pipeline.agenda` (`lote_valendo`, config) | `remoto/lote.py` **só lê** e formata; nenhum número de piso ou alvo mora em `remoto/`. Se o `postar` renomear `estoque_do_lote`, o /lote, o relatório, o painel e o app dizem "não deu para contar" (e `test_lote.py` acusa) |
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
| `vigia.json` (o pulso de quem ouve os comandos, a cada 30 s, e a saída com o motivo; §9) | o `esperar` |
| `aviso_sem_ouvinte.json` (a ocorrência do aviso no Telegram) | o servidor |

**CLI do orquestrador:**

```bash
python -m remoto.orquestrador agente-inicio --parte P --titulo T [--da-fila ID] [--relato R] [--forcar]
python -m remoto.orquestrador relato <id> "uma linha"
python -m remoto.orquestrador agente-fim <id> [--situacao concluido|falhou|parado] [--commit H]...
python -m remoto.orquestrador fila adicionar --parte P --item T [--posicao N]
python -m remoto.orquestrador fila mover <id> subir|descer|topo
python -m remoto.orquestrador fila ordenar <id> <id> ...   # a ordem final inteira (§11)
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
python -m remoto.orquestrador claude [status|liberar|proibir] [--motivo M] [--sem-aviso]   # §12.2
```

- O `agente-inicio` **recusa** (código 3) com o **Claude proibido** (§12.2),
  e aí nem o `--forcar` passa. Liberado, recusa em três casos:
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
  - `priorizar`: reordena a fila. Desde 29/09 a forma que o app manda é
    `{"ordem": [ids...], "esperava": versão}` — a ordem final inteira, um
    comando por reordenação (§11). `{item, direcao}` continua valendo;
  - `adicionar_a_fila` (`{parte, item}`) põe no fim, com `pedido: Adrian`;
    `tirar_da_fila` (id) tira, e recusa se o item não existe (desde 28/09,
    noite: antes a Mesa só subia e descia);
  - `parar_agente`: marca o agente como "parando". Quem para é o
    orquestrador, que depois roda `agente-fim --situacao parado`. Com um
    agente que não existe, o `aplicado` **recusa**, e o orquestrador
    registra com `--recusado`.
- **Fora do ar**: `estado.atualizado_em` com mais de 15 min. Todo comando da
  CLI conta como pulso, e o `esperar` pulsa a cada 5 min. **Isso diz "a
  sessão deu sinal", não "alguém ouve os comandos"**: desde 29/09 quem
  responde a segunda pergunta é o pulso do vigia (§9).
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

**A sonda de uso** (com o Claude proibido ela não roda, e a tela diz "Sonda
parada: Claude proibido desde HH:MM"; §12.2) roda no servidor, a cada `sonda_min` do `config.json`
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
o `leitor` (§8) e rearme. **Desligar o `esperar` deixa os pedidos dele
parados** (a Mesa agora diz isso em vermelho, e o Telegram avisa; §9).

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

## 9. Sincronia: o que a tela mostra contra o que acontece (29/09/2026)

Pedido do Adrian: "cuide desse problema de sincronização que existe hoje no
app". Levantado medindo (log `outputs/app_celular.txt`, `comandos.jsonl`,
`comandos_aplicados.jsonl`, `estado.json`, `uso_historico.jsonl`); prova em
`E:\projetos-wt\_prova_sinc\` (telas e `prova_8934.txt`).

| dessincronia | medida | conserto |
| --- | --- | --- |
| comando sem ninguém ouvindo | "retomar a fila" 00:58:45 → 01:01:21 (2 min 36 s), `esperar` desligado desde o checkpoint; nos 9 comandos até 00:58, a espera foi de 12 s a 286 s | pulso do vigia; Mesa com três situações; aviso depois de 2 min; Telegram uma vez por ocorrência |
| "no ar" com o vigia desligado | `fora_do_ar` olha `estado.atualizado_em`, que QUALQUER comando da CLI renova (relato, fila…) | o ouvido é o `vigia.json`, não o sinal da sessão |
| toque repetido | 01:15:19: max_paralelo 4, 4 e 5 no mesmo segundo = 2 respostas e 2 commits no Grimório para uma mudança; e o alvo do "+" lia o pendente MAIS VELHO | a tela junta os toques (700 ms, só o valor final); o servidor não grava de novo um pedido idêntico pendente (menos o `priorizar`, que soma) |
| casca velha aberta | o cache foi do v8 ao v13 em 28/09; o PWA volta do fundo com o mesmo JS, e casca velha ignora campo novo calada | `X-Casca` em toda resposta JSON e `<meta name="casca">` no `index.html`; na Vila, sem diálogo, recarrega sozinho; fora dela, uma faixa pede o toque; uma vez por versão |
| relógio e fuso | as horas da API vão sem fuso; o PC está a ≤1 s do Google (−03:00); o celular não é medido | `Date` + `X-Fuso-Min` em toda resposta; "há X min" pelo relógio do PC (prova: celular em Tóquio diz "agora", antes "há 12 h") |
| Grimório parado | carregava uma vez: a marca do leitor, um nó novo e a resposta de outra aba só apareciam ao reabrir | relê a cada 20 s ("atualizado às HH:MM"); o nó aberto só redesenha se ele não estiver no meio de uma resposta |
| resposta dada numa tela velha | trocava a decisão por cima de outra que ele não viu (outra aba, outro aparelho, a Mesa) | `esperava` (a vigente que a tela mostrou): diferente = 409 "mudou enquanto a tela estava aberta", e a tela reabre com o que vale |
| Vila acordando | o motor dorme 30 s sem pedido e guardava os prédios: em 00:55 o primeiro retrato era de 39 min antes (a leitura leva 104 ms) | leitura mais velha que 10 s é refeita antes de responder; falhou = prédios vazios, nunca os velhos |
| previsão e fluxo guardados | a previsão (1,9 s para calcular) voltava a de horas atrás como se fosse agora, no primeiro pedido | `vencida` + `idade_s`; a tela diz "previsão há X; recalculando…" e busca de novo em 4 s |
| `uso.json` | sem defeito: sonda a cada ~11,5 min; buracos só nos reinícios (19:22→19:55, 23:41→23:57) e a tela já diz "sem medição desde" | nada |
| dois aparelhos | 2 pareados (`076f31d9` de 17/09 e `614c026b`); o log não dizia qual | o log leva a data e o id do aparelho |
| "Agora" contra os agentes reais | a Mesa só sabe o que o orquestrador registra; do 8a6e221f a Mesa ficou 20 min sem relato até o fim | sessão fechada diz "os agentes da lista podem não estar rodando" |

**O vigia** (`vigia.json` na pasta do orquestrador), escrito só pelo
`esperar`:
- `{"situacao": "ouvindo", "pid", "desde", "pulso_em", "pulso_s": 30}`, a
  cada 30 s enquanto ele espera;
- ao sair, `{"situacao": "saiu", "saiu_em", "motivo"}`: `comando`,
  `decisao_nova`, `interrompido` ou `erro: …`. Morto à força, o pulso
  envelhece e o PID some (`_pid_vivo`, por `OpenProcess`);
- dois `esperar` juntos: a saída de um não apaga o pulso do outro.

`situacao_do_vigia` (servidor e `python -m remoto.orquestrador vigia`):
- **ouvindo**: pulso com menos de 90 s e o processo existe;
- **acordou** ("aplicando"): saiu com um pedido há menos de 3 min;
- **fora**: sessão com sinal nos últimos 15 min, vigia desligado há X;
- **fechada**: nem vigia, nem sinal da sessão.

`sem_ouvinte`: o pendente mais velho, passado de 2 min e sem ninguém ouvindo,
vira "Ninguém está ouvindo agora; o comando será aplicado quando o
orquestrador voltar" (faixa vermelha, selo vermelho na prateleira, o toast
do envio já diz na hora). Ouvindo e ainda pendente é "preso". O servidor
olha a cada 30 s (`AVISO_SEM_OUVINTE`) e manda UM aviso no Telegram por
ocorrência, e um "voltou e aplicou … (ficou pendente X)" quando ela fecha. A
ocorrência mora em `aviso_sem_ouvinte.json`: reiniciar o servidor no meio
não repete o aviso.

**Log do servidor** desde 29/09: `29/09 01:26:49 127.0.0.1 GET /api/x 200
614c026b` (data, e o id do aparelho quando a rota pede token).

**Prova de tela (29/09):** 390×844, clicando, na 8934 (estado copiado,
Grimório clonado, casca copiada, avisos num arquivo) e na 8935 vazia. 0
exceções de JS; o único erro do console é o 409 da resposta velha, de
propósito.
- A reprodução das 00:58 dá a faixa "Ninguém está ouvindo agora…", "o vigia
  está desligado há 38 min" e o selo vermelho. Sai um aviso, e um só em 35 s.
- Com o `esperar` ligado aparece "👂 ouvindo" e a faixa some. Depois vem o
  "voltou e aplicou".
- Três toques no "+" mostram "2 → 5" na hora e gravam um comando só (5). O
  toast diz "está ouvindo", o `esperar` acorda com ele e a tela mostra
  "⚙ aplicando".
- Mudar um arquivo da casca recarrega sozinho na Vila. Na Mesa aparece a
  faixa, e voltar à Vila recarrega.
- Duas abas no Grimório: a parada mostra a resposta da outra em até 20 s. A
  que estava no meio de uma resposta mostra "mudou no PC", e o "sim" dela
  sai 409 e reabre com o que vale.
- Celular em Tóquio: "sinal de vida 13:39 (agora)".

## 10. A conversa com cada IA: correio, carteiro e a tela Conversar (29/09/2026)

Vila das IAs, fase 2 (plano `~/.claude/plans/vila-das-ias.md`; o Adrian
liberou em `geral/ias-fichas-lidas`). Pedido dele: "que eu possa falar com
cada uma individualmente pelo app". Três decisões do Grimório mandam aqui:
`ias-prioridade-conversa` (ele tem prioridade sobre a pipeline na mesma
conta), `ias-chat-persistente` (um chat "casa" por IA, com resumo
periódico) e `ias-grok-acesso` (grok.com com a conta X dele, perfil
`grok__principal`).

**Princípio.** Tudo passa pelo **correio** (arquivo), nunca direto: o app
deixa a mensagem na caixa, o **carteiro** (processo próprio) entrega e grava
a resposta. O servidor do app nunca abre navegador. Conversam só as IAs de
chat: DeepSeek, ChatGPT, Gemini e Grok. Os geradores de imagem entraram em
29/09 à tarde pelo **Criar** (§13).

**O correio** (`ias/correio.py`), em
`%LOCALAPPDATA%\neural-fights\ias\<ia>\correio.jsonl` (`NF_IAS_PASTA` troca
a raiz, para a instância de teste). Registro **só de acréscimo**: a primeira
linha de uma mensagem é o registro inteiro; as seguintes, com o mesmo `id`,
são deltas. Ler é dobrar por id; meia linha e delta órfão são pulados e
contados (`ilegiveis`). Uma linha por `write`, sob trava de arquivo ao lado.
Formato dobrado:

```json
{"id": "3679ee70", "em": "2026-09-29T07:33:46", "de": "adrian", "para": "deepseek",
 "thread": "casa:deepseek", "texto": "...", "anexos": ["...\\anexos\\20260929_073346_ab12_foto.png"],
 "situacao": "pendente|entregue|respondida|falhou", "resposta": null, "erro": null,
 "categoria": null, "nota": null, "entregue_em": "...", "respondida_em": "...",
 "dur_s": 4.0, "modelo": "...", "visto": true, "atualizado_em": "..."}
```

Na mesma pasta: `casa.json` (a URL do chat de longa duração, a geração, o
contador de mensagens, `falhas_seguidas`), `casa_resumo.md` (o último resumo
que a IA fez) e a pasta `anexos`. Na raiz `ias`: `carteiro.json` (o estado
do carteiro, com PID e pulso) e `presenca.json` (a última vez que o app
pediu cada caixa). O caso ZERO existe: sem pasta, tudo é vazio e
`estado_do_carteiro` diz `nunca`.

**O carteiro** (`python -m ias carteiro`, `ias/carteiro.py`; config em
`ias/config.json`):
- pega a pendente mais velha entre todas as caixas; pega a **trava da conta**
  (`travas.do_perfil(ia, "geral")`) em passos de 20 s. Se a pipeline estiver
  com ela, espera, escreve `nota: "esperando a pipeline soltar a conta"` na
  mensagem e "esperando_trava" no `carteiro.json`; **nunca mata**. Passado
  `espera_conta_max_s` (3 h) a mensagem falha com o motivo;
- com a conta, abre o `ClienteLLM` (`abrir_cliente`, trava reentrante) no
  chat **casa**: navega para a URL de `casa.json` e só aceita com **prova**
  (um turno nosso na tela e a URL sem redirecionar). Sem casa, casa que não
  abre, ou duas falhas seguidas → **casa nova**, e o `casa_resumo.md` entra
  como primeira mensagem (`PROLOGO_CASA_NOVA`);
- `perguntar` com anexos (só imagens); marca `entregue` antes e `respondida`
  (com `dur_s` e `modelo`) depois. Enquanto espera, o log do cliente pulsa o
  `carteiro.json` (a resposta pode levar minutos);
- **prioridade dele**: depois de responder, segura a conta por
  `janela_conversa_s` (90 s) esperando a próxima mensagem para a mesma IA —
  a pipeline, que pede a trava com paciência curta, cai para outro provedor;
- a cada `resumo_a_cada` (12) mensagens respondidas na casa, pede à IA um
  resumo (`PEDIDO_RESUMO`) e grava `casa_resumo.md` (não vira mensagem do
  correio);
- **erro legível**: `classificar_erro` olha o tipo da exceção (login caído,
  conta ocupada), os `catalogo_textos` da ficha da IA (fase 1) contra o texto
  **que surgiu depois do envio** (`tela_do_turno`: a página é fotografada
  antes e `catalogo.linhas_novas` tira o que já estava lá, por contagem), a
  varredura `catalogo.varrer` e só então a exceção crua → `erro` +
  `categoria` na mensagem ("o site diz: «…»"). Nunca a página inteira: em
  30/09 o botão fixo "Fazer upgrade" do rodapé do ChatGPT Free virou o motivo
  de `82e154e4` e `5030f732` e escondeu a exceção de verdade;
- **diário**: o próprio cliente registra cada turno (`papel=conversa`,
  `ref=Adrian`, canal `adrian`): a Vila mostra o habitante "conversa Adrian";
- **Telegram**: a resposta (ou a falha) vai em texto puro aos autorizados
  **quando o app não está olhando** aquela caixa (`presenca.json`, 45 s);
  com a tela aberta, só o balão;
- um carteiro por vez (trava `ias__carteiro`); `--uma-vez` entrega o que há
  e sai; `--duble` responde sem navegador, com trava própria por IA
  (`ias__duble__<ia>`, nunca a da conta) e aviso no log — é o da prova de
  tela. O ritmo humano é o do `ClienteLLM`; um Chrome por vez; `headless`
  por IA no config (todos `false`: ChatGPT em headless cai no Cloudflare).
- **Anexo no DeepSeek entra desde 29/09 (15h)**: `anexo_prova` e
  `anexo_subindo` preenchidos em `contos/llm/seletores.py` (parte
  historias, tarefa dc176b96); teste real pelo caminho do carteiro:
  círculo vermelho → "Vermelho" em 9,3 s. O carteiro só recusa na hora
  ("mande sem anexo") quem tiver `anexo_prova` vazio. **O carteiro que já
  estava no ar carregou o módulo antigo**: só aceita anexo para o DeepSeek
  depois de reiniciado.

**No app.** Tocar num prédio de IA de chat → o cartão tem **💬 Conversar**
→ `tela-conversa` (`app/conversa.js`), por cima da Vila: chips das quatro
IAs (o **Grok** entra por aqui, porque não tem prédio), a casa (geração,
mensagens, último resumo), a linha do carteiro (pronto / entregando ao X /
esperando a conta / parado / nunca rodou), o histórico em balões (os dele à
direita com a situação — "na caixa, esperando o carteiro", "entregue ·
esperando a resposta…", "respondida HH:MM em N s · modelo", "falhou:
motivo" — e os da IA à esquerda), a caixa de texto e o anexo de imagem
(base64 no POST). Relê a cada 6 s sem recarregar; a tela aberta marca as
respostas como **vistas**. Na Vila, uma resposta **não vista** vira balão de
fala em cima do prédio (`vilaDesenharCorreio`, canvas) e entra no cartão
(`.vila-resposta`); a Vila relê o correio junto do `/api/vila` (15 s). Na
Mesa, "Agora" ganhou a linha do carteiro (`#orq-carteiro`: estado, a quem
está entregando, as caixas com pendentes e não vistas). Casca `v15`.

Rotas (todas com token; ler nunca depende de `--acoes`):

| rota | o que faz |
| --- | --- |
| `GET /api/correio` | as quatro caixas (pendentes, em andamento, não vistas, última) + o carteiro; registra presença `app` |
| `GET /api/correio/<ia>?n=60` | o histórico da caixa, a casa e o carteiro; registra presença `correio:<ia>` |
| `POST /api/correio/<ia>` `{texto, anexos:[{nome, b64}]}` | deixa a mensagem na caixa (pendente). **Só com `--acoes`** (faz o PC abrir um navegador na conta dele); corpo até 12 MB; anexo só png/jpg/webp até 8 MB; texto vazio = 400 |
| `POST /api/correio/<ia>/visto` | marca as respondidas/falhadas como vistas |

`orquestrador.para_o_app()` leva `carteiro` (estado + caixas) e nunca quebra
a Mesa se o pacote `ias` faltar.

**Testes** (`ias/test_correio.py`, 29; `remoto/test_correio_app.py`, 11):
o caso ZERO do correio e da Mesa; dobra por id, ilegíveis, vistas, anexo;
o carteiro entregando (casa, Telegram), falhando (motivo pelo catálogo, pela
tela e pela exceção), a prioridade (trava ocupada → espera, registra, nunca
mata; presa além do limite → falhou sem abrir navegador), a janela de
conversa numa sessão só, casa reaberta, casa inutilizável → nova com o
resumo, duas falhas → casa nova, o resumo periódico; e as rotas (401,
403 sem `--acoes`, 404 para IA que não conversa, histórico, envio, anexo,
visto, o `conversa.js` servido). Nenhum abre navegador nem toca o
`%LOCALAPPDATA%` real.

**Prova de tela (29/09, 07:33–07:48):** 390×844, clicando, na 8934
(`scratchpad/servidor_conversa.py`: estado copiado, Grimório clonado, casca
copiada, correio em `E:\projetos-wt\_prova_conversa\ias`) com o carteiro
**dublê** (`python -m ias carteiro --duble --demora 4 --janela 8`). 22
conferências OK, 0 erros de JS; telas em
`E:\projetos-wt\_prova_conversa\telas\duble_*.png`, relatório em
`prova_duble.txt`:
- o toque no prédio do DeepSeek abre o cartão com 💬 Conversar; a tela abre
  com os quatro chips (Grok incluído) e o caso ZERO;
- a mensagem aparece "na caixa, esperando o carteiro" e vira "respondida
  07:33 em 4 s · dublê" sem recarregar; o correio tem as 4 linhas (pendente,
  entregue, respondida, visto);
- uma segunda mensagem pela CLI com a tela fechada aparece no cartão do
  DeepSeek como "💬 OK (dublê) — recebi: …" (não vista) e o balão no canvas;
- a Mesa diz "📮 Carteiro: pronto · caixas: 🐋 DeepSeek · 1 resposta(s) não
  vista(s)"; durante a entrega dizia "entregando ao DeepSeek desde 07:34";
- o chip do Grok abre a caixa dele vazia.

**Pendências desta fase:**
- ~~**prédio do Grok na Vila**~~ — feito em 29/09 pela parte painel-e-vila
  (db3f438: `remoto/app/vila.js`, `conversa.js`); o Grok tem prédio e a
  resposta dele vira balão no canvas;
- **tarefa do Windows para o carteiro** (`NeuralFights_carteiro`): o
  agente não pôde registrar; o XML e o comando estão no fim desta seção;
- ~~anexo no DeepSeek (seletores, historias)~~ — feito em 29/09 (ver acima);
- ~~o balão no canvas fica atrás do placar~~ — feito no mesmo db3f438: o
  balão desvia do placar.

**O envio REAL de ponta a ponta (29/09, 07:55–07:56):** pelo app (instância
8936 com a casca nova, pareamento próprio e o correio **real**), "PEDIDO DE
TEXTO: responda só OK" para o DeepSeek, com a tela fechada em seguida:
- 07:55:04 a mensagem entrou na caixa (`%LOCALAPPDATA%\neural-fights\ias\deepseek\correio.jsonl`, id `9407c5ad`);
- 07:55:56 `python -m ias carteiro --uma-vez` subiu, 07:56:00 abriu a **casa
  nova** do DeepSeek (Chrome no perfil `deepseek__principal`, chat
  `chat.deepseek.com/a/chat/s/cc2d815e-…`, guardado em `casa.json`);
- 07:56:08 respondida: "OK", 8,6 s (`modelo: DeepSeek (site)`), 4 linhas no
  correio (pendente → entregue → respondida → visto);
- na Vila (8936), o habitante do DeepSeek ficou "trabalhando · conversa
  Adrian · conta: principal" e o cartão mostrou "💬 OK"
  (`E:\projetos-wt\_prova_conversa_real\telas\real_4_vila_resposta_real.png`);
- 07:56:30 "aviso no Telegram entregue" (o app não estava olhando a caixa);
- reaberta a tela, "respondida 07:56 em 9 s" e o balão "OK"
  (`real_4_respondida.png`; relatório em `prova_real.txt`, log do carteiro em
  `carteiro_real.log`).

**O 8931 foi reiniciado às 07:55:02** (`scratchpad/reiniciar_app.ps1`, pela
tarefa): PID 14896, escutando às 07:55:10, com a casca `v15` e as rotas do
correio.

**O carteiro como tarefa do Windows — fica para o Adrian.** O lançador
`E:\projetos\carteiro.cmd` está no repositório (log aberto pelo Python com
`--saida outputs\carteiro.txt`; segundo carteiro sai com código 3 pela
trava `ias__carteiro`). A tarefa `NeuralFights_carteiro`, espelho da do app
(a cada 10 min, `oculto.vbs`, sem janela), **não pôde ser registrada pelo
agente** (a permissão da sessão barrou o `schtasks /create`). O XML pronto
está em `E:\projetos-wt\_prova_conversa_real\carteiro_task.xml`; para
registrar:

```
schtasks /create /tn NeuralFights_carteiro /xml E:\projetos-wt\_prova_conversa_real\carteiro_task.xml
schtasks /run /tn NeuralFights_carteiro
```

Até lá o carteiro sobe à mão (`python -m ias carteiro --saida
outputs\carteiro.txt`, uma vez; ele fica no ar). Com ele parado, a tela diz
"o carteiro está parado (sinal HH:MM): a mensagem fica na caixa até ele
voltar", e nada se perde.

## 11. A fila em cards que ele rearranja arrastando (29/09/2026)

Pedido do Adrian pela Mesa (09:1x, `d04cce3f`): "mude a forma da fila para
cards que eu possa rearranjar sem problemas". O que incomodava, medido no
`comandos.jsonl`: para pôr um item no topo ele mandou **6 "subir" seguidos**,
cada um um comando pendente até o orquestrador aplicar.

**O comando.** `priorizar` ganhou a forma `{"ordem": [ids...], "esperava":
versão}` — a ordem final inteira, **um comando por reordenação**, idempotente:
- `fila_versao` (em `para_o_app`) é um resumo (sha1[:8]) da ORDEM dos ids; a
  tela guarda o que viu e devolve como `esperava`. Diferente da atual = a fila
  mudou no PC no meio do arrasto: o servidor responde **409 com
  `codigo: "fila_mudou"`** (`orquestrador.FilaMudou`) e a `fila_versao` que
  vale; a tela avisa "a fila mudou no PC enquanto você arrastava" e reabre
  com a atual. Sem `esperava` (a CLI, uma casca antiga) não confere versão;
- na entrada (`gravar_comando`) é **estrito**: id que a fila não tem, item
  que a ordem não diz onde fica, id repetido → Recusa (409). Ordem igual à
  atual **não vira comando**: a resposta traz `ja_estava: true` e a tela diz
  "já estava nessa ordem". A mesma ordem nova duas vezes (toque duplo) é um
  comando só, como os outros — só o `priorizar` de um item (`{item,
  direcao}`, que continua valendo) soma;
- no `aplicado` é **tolerante**, porque entre o toque e a aplicação o
  orquestrador pode ter posto ou tirado um item: id que já saiu é pulado, e
  item que entrou depois fica no fim; os dois vão para a nota do comando
  ("2 item(ns) entrou(aram) depois e ficou(aram) no fim"). Ordem que já
  vale na hora de aplicar dá nota "já estava assim";
- a CLI ganhou `fila ordenar <id> <id> ...` (estrita como o app).

**A tela** (`app/orquestrador.js`, seção "fila"): cada item é um card
(`.orq-card`) com a cor da parte na borda esquerda e o emoji dela
(`ORQ_PARTE`: 🧭 geral, 🎲 builds, 📖 historias, 📣 publicacao, 📊 metricas,
📱 app-e-bot, 🏘 painel-e-vila, 🧟 jogo-zombie), o título, o id curto
(`#abcd1234`) e a situação (pedido por Adrian, desde, ordem pedida
(pendente), tirar pedido (pendente)). O menu `⋯` tem **⤒ topo**, **⤓ fim** e
**✕ tirar** (com o diálogo de confirmação de sempre); topo e fim também
mandam a ordem inteira. Os botões ↑/↓ saíram.
- **Arrastar e soltar** por Pointer Events, sem biblioteca: a alça `⠿`
  (`touch-action: none`) começa na hora; no resto do card é toque longo
  (400 ms parado; mexer antes é rolagem normal). O card vira um fantasma
  (`position: fixed`) que segue o dedo, o lugar dele fica como placeholder,
  os vizinhos deslizam (FLIP leve, `transition: transform .15s`), e perto
  da borda da tela rola sozinho. `prefers-reduced-motion` desliga as
  transições. Um `touchmove` não passivo faz `preventDefault` só com o
  arrasto ligado, para o navegador não cancelar o pointer.
- **Enquanto o orquestrador não aplica**, os cards ficam **listrados**
  (`.pendente`) na ordem pedida (o pendente mais novo de ordem inteira,
  `orqOrdemMostrada`, com a mesma tolerância do `aplicado`). Aplicado, a
  releitura de 10 s limpa as listras; **recusado**, os cards voltam ao lugar
  e a situação diz "a última ordem pedida foi recusada: motivo" por 10 min.
- **Sem briga com o PC:** durante o arrasto `orqDesenharFila` não redesenha
  (`Orq.fila.arrastando`); o `Orq.dados` segue sendo relido, mas a versão
  que vai no `esperava` é a da fila **desenhada** (`versaoVista`), capturada
  antes do redesenho local — a prova pegou a primeira versão mandando a
  versão nova, que batia sem ele ter visto a mudança (o 409 saía como "a
  ordem não diz onde fica o item…").
- `ErroApi` (`app.js`) agora leva `codigo` e `dados` do corpo do erro.
- Casca `v17` (`sw.js`; o v16 foi o prédio do Grok, db3f438).

**Testes** (`test_orquestrador.py`, +7): reordenação completa num comando
(com `fila_versao` mudando e a linha do tempo), id desconhecido / faltando /
repetido e as formas inválidas, ordem igual (`ja_estava`, toque duplo), a
rota com `esperava` velho → 409 `fila_mudou` (e com a versão certa → 200;
sem `esperava` → 200), o `aplicado` tolerante (item saiu, item entrou, "já
estava assim"), o caso ZERO (fila vazia tem versão; ordem vazia "já estava";
id qualquer é desconhecido; `esperava` errado é 409) e a CLI `fila ordenar`.
Suíte do `remoto/`: 643 verdes.

**Prova de tela (29/09, 10:3x):** 390×844, `is_mobile` + toque, na 8934
(`scratchpad/prova_fila_cards.py` + `servidor_conversa.py`: estado próprio
que nasce vazio, Grimório clonado, casca copiada). Arrasto simulado pelo
`page.mouse` (Pointer Events), conferido pelo DOM e pelos arquivos; telas em
`E:\projetos-wt\_prova_fila\telas\`, relatório em `prova_fila.txt`. 0 erros
de JS (o único erro de console é o 409, de propósito). Na última rodada,
43 de 44 conferências OK; a que falhou lia "tirar pedido (pendente)" no
card 0,6 s depois do POST, antes da releitura (a tela `10b_tirado.png` da
rodada das 10:24 mostra o texto; a prova agora espera até 12 s):
- caso ZERO: "A fila está vazia.", nenhum card;
- 5 itens pela CLI viram 5 cards, 4 cores, emoji e id curto;
- arrastar o 5.º para o topo pela alça: fantasma, placeholder já no topo
  antes de soltar; ao soltar, a tela mostra a ordem nova listrada e grava
  **um** comando `priorizar` com a ordem inteira e `esperava` = a versão
  vista; `aplicado` pela CLI limpa as listras em ≤ 15 s;
- `⋯` → ⤓ fim manda a ordem inteira com o item no fim;
- soltar no mesmo lugar: nenhum comando;
- a fila muda no PC (CLI) durante o arrasto, com a releitura de 10 s no
  meio: o arrasto sobrevive, ao soltar sai 409, toast "a fila mudou no PC
  enquanto você arrastava", nenhum comando gravado, a tela reabre com os 6;
- toque longo no corpo do card também arrasta;
- `aplicado --recusado "motivo"`: os cards voltam e a situação diz o motivo;
- ✕ tirar pede confirmação e vira `tirar_da_fila`; o card diz "tirar pedido
  (pendente)" e sai quando aplicado;
- "O que você mandou" descreve "a ordem inteira (N)".

**Armadilhas da prova (não são do app):**
- **Chrome headless segura os eventos de ponteiro na fila de entrada até o
  próximo quadro.** Medido: `mouse.up()` volta em 5 ms, e o POST só saía na
  chamada seguinte do driver; sem `setPointerCapture` era igual. Uma
  captura de tela (força um quadro) ou um `mouse.move` de 1 px depois do
  `down`/`up` entrega o evento em ~0,1 s. Sem isso o `pointerdown` do toque
  longo chegava tarde, o timer de 400 ms começava atrasado, os moves o
  cancelavam e o mouse **selecionava texto** em vez de arrastar. No celular
  há quadros o tempo todo durante o arrasto.
- **A API síncrona do patchright só entrega eventos (`request`, `console`)
  dentro de uma chamada**: o carimbo de tempo de um `page.on("request")`
  é o da chamada que bombeou o laço, não o do pedido. Meça pelos arquivos
  do servidor.
- **Um `MutationObserver` que escreve no DOM que observa trava a página**
  (laço de microtarefas): a primeira versão do observador de toasts fez a
  tela "congelar" depois de qualquer toast. Observe só `class` do `#toast`
  (`attributeFilter`) e escreva uma vez por texto.
- Com 6 cards a lista passa de 844 px: role o card até a vista antes de
  medir o centro (`scroll_into_view_if_needed`), senão o toque cai fora da
  viewport e não chega a ninguém.
- **O toast fica 8 s por cima do que está embaixo** (`position: fixed`,
  `z-index` 40): um toque logo depois de um aviso cai no toast, não no card.
  Espere `#toast.oculto` antes do próximo toque. O clique de "Confirmar" do
  diálogo também espera um quadro no headless.

**O 8931 foi reiniciado às 10:55:01** (`scratchpad/reiniciar_app.ps1`, pela
tarefa, na janela :55–:10): PID 14360, escutando às 10:55:09, com o e298df7
(a fila em cards) e o db3f438 (o prédio do Grok) juntos. Até esse reinício o
servidor antigo servia a casca nova do disco com o código antigo em memória:
uma reordenação pelo celular voltaria 409 "item da fila inválido" — por
isso casca e código sobem no mesmo commit e o reinício vem logo atrás.

**Fica para o Adrian decidir:** nada novo — reordenar continua sendo
"comando pendente até o orquestrador aplicar", como o resto da Mesa.

## 12. O ícone novo e o interruptor do Claude (29/09/2026)

Pedido do Adrian (13:4x, `9c2ee626`): "troque o ícone do app por esse, e
agora depois dessa interação usar o Claude está proibido até segunda ordem,
crie algo no app para ligar e desligar isso."

### 12.1 O ícone

O cérebro de circuitos com as casinhas e o "ai". A fonte (2816×1536, 5,5 MB,
com fundo desfocado) **não está no repositório**: fica em
`%LOCALAPPDATA%\neural-fights\icone_fonte\fonte_icone_novo.png`, com o
gerador `gerar_icones.py` ao lado. O recorte acha a borda escura do quadrado
pelo **salto de brilho** (o fundo embaixo do ícone também é escuro, então um
limiar fixo falhava): x 816–1999, y 181–1365, raio do canto ~256 px, máscara
antisserrilhada em 4x e LANCZOS. Cor da borda: `#09256f`.

Em `remoto/app/icones/`: `icone-192.png` e `icone-512.png` (`any`,
transparentes fora do quadrado), `icone-maskable-512.png` (fundo cheio
`#09256f`, ícone a 80%: 10% de margem de cada lado), `apple-touch-icon.png`
180 (opaco: o iOS pinta transparência de preto), `favicon-32/16.png` e
`favicon.ico` (16/32/48). O `icone.svg` saiu (a rota dá 404). O manifest tem
`theme_color` e `background_color` = `#09256f` (a tela de abertura casa com o
ícone); o `<meta name="theme-color">` do `index.html` segue `#17251a`, a cor
da Vila com o app aberto. Casca `v18`.

**No celular:** o Android só troca o ícone de um PWA já instalado quando
atualiza o manifest (o Chrome confere de tempos em tempos, pode levar um
dia) ou quando ele é reinstalado. Se o ícone velho ficar, remover da tela
inicial e adicionar de novo.

### 12.2 O interruptor "Claude liberado / proibido"

O Adrian quer poder **proibir todo uso automático do Claude** e ligar e
desligar pelo app. "Usar o Claude" é tudo que chama o Claude Code sozinho:

| quem | o que faz com o Claude proibido |
| --- | --- |
| a **sonda de uso** do servidor (`claude.exe -p ok --model haiku`) | não roda (`_Sonda` pula; `sondar` devolve `parada` sem chamar nem gravar). `ler_uso` dá `situacao: "parada"` e a Mesa diz "Sonda parada: Claude proibido desde HH:MM · última medição às …", **sem barra nem número** |
| o **apurador** do bot (`claude -p`) | `uma_volta` não chama o Claude, **não marca** os erros (ficam para quando liberar, dentro das 12 h) e escreve no diário `apurador/log` "apuração pulada: Claude proibido pelo Adrian desde HH:MM (N erro(s) guardado(s))". `apurar` e `consertar` também recusam sozinhos (guarda no ponto, não só no funil) |
| `orquestrador agente-inicio` | recusa com código 3: "Claude proibido pelo Adrian desde HH:MM; nem o --forcar passa" — com ou sem `--forcar` |
| `orquestrador esperar` | **não acorda** com comando nem com decisão nova (cada saída acorda a sessão principal, e isso é uso). Os comandos ficam pendentes e o cursor das decisões não anda. O `vigia.json` segue pulsando, com `segurando: "Claude proibido desde …"`. Sai **só** quando o estado volta a `liberado`, com `{"tipo": "claude_liberado", "em", "por", "motivo", "texto"}` na frente e os comandos e decisões guardados atrás (motivo da saída: `claude_liberado`) |
| o aviso "ninguém ouvindo" | vira `guardado` na Mesa (sem faixa vermelha nem selo) e **não** manda Telegram: comando parado é a ordem dele, não ausência |

O carteiro das IAs (`ias/`) abre navegador, não o Claude: não é afetado.

**O estado** (`remoto/claude_estado.py`): `%LOCALAPPDATA%\neural-fights\claude.json`
= `{liberado, em, por, motivo}`, escrita atômica sob `claude.json.lock`, e
cada mudança anexada em `claude_historico.jsonl` (com o valor de antes).
Pedir o que já vale não reescreve nada (toque duplo = uma linha).
- **Ausente = liberado** (como tudo era antes), com `origem: "sem_arquivo"`;
  a tela diz "nunca foi mudado", e a primeira leitura sem arquivo fica
  registrada no histórico (na máquina real: 14:04:10, na subida do 8931).
- **Ilegível = PROIBIDO** (falha fechado, como o resto do app).
- Lido a cada chamada: ninguém guarda em memória. O bot dispara o
  apurador como **processo novo** (`python -m remoto --apurar`), então o
  bot em si **não precisa reiniciar** para o apurador obedecer.
- `NF_CLAUDE_ESTADO` troca o arquivo (instância de teste); com
  `NEURAL_FIGHTS_RUNTIME_DIR` (pytest, `testar.py`) ele mora lá; e o
  `remoto/conftest.py` põe um `claude.json` por teste.

**No app:** o botão grande "🤖 Claude: LIBERADO / PROIBIDO" (verde /
vermelho, "desde HH:MM · pelo app (aparelho)", "tocar para liberar/proibir")
fica no **topo da Mesa, preso ao rolar** (`position: sticky`), e no topo da
**Bancada**. Dois toques: o botão e o "Confirmar" do diálogo, que explica o
que muda. Com proibido, a Mesa mostra a faixa "Claude proibido desde HH:MM —
nenhum agente, sonda ou apuração roda; os comandos ficam guardados.", e um
comando mandado pela Mesa diz "guardado — o Claude está proibido; o comando
sai quando você liberar". O toque grava **direto** no estado pelo servidor
(`POST /api/claude {"liberar": true|false}` — o alvo, não "inverter"; só com
token, sem depender de `--acoes`), porque com o Claude proibido um "liberar"
que fosse comando nunca seria aplicado. `GET /api/claude` e o campo `claude`
do `/api/orquestrador` trazem o estado e as últimas mudanças. Cada mudança
manda no Telegram "🤖 Claude proibido pelo app às HH:MM — nenhum agente,
sonda ou apuração roda; os comandos da Mesa ficam guardados." (ou
"liberado"). A CLI manda o mesmo, com "por <quem>" (`--sem-aviso` cala). A
mudança **não** entra na linha do tempo do `estado.json`: gravar lá renova o
"sinal de vida" da sessão. Casca `v19`.

Armadilha medida na prova: o `top` de um `position: sticky` dentro do livro
conta da borda **interna do padding** (64 px + safe-area) e da moldura da
Mesa (12 px). Com `top: 54px` ele parava em y = 130, cobrindo a tela; com
-10 px (Bancada) e -22 px (Mesa) ele para em y = 54, logo abaixo do
cabeçalho.

**Testes** (`remoto/test_claude_estado.py`, 16, com dublê — nenhum chama o
Claude): caso ZERO (sem arquivo), ilegível, gravação e histórico, a sonda
pulada (e o laço), a CLI `sonda`, o apurador pulado (diário, sem marcar,
`apurar` e `consertar`), o apurador liberado como antes, `agente-inicio`
recusado com e sem `--forcar`, o `esperar` segurando e saindo só no liberar
(inclusive com comando chegando no meio), o "guardado" sem Telegram, a CLI
`claude` e a rota do app (401 sem token, 400 sem alvo, alternância, toque
repetido, aviso). Suíte do `remoto/`: 660 verdes.

**Prova de tela (29/09, 14:04):** 390×844, clicando, na 8934
(`scratchpad/prova_claude.py` + `servidor_conversa.py`, `NF_CLAUDE_ESTADO`
próprio, avisos num arquivo). 33 conferências, 0 erros de JS; telas em
`E:\projetos-wt\_prova_claude\telas\`, relatório em `prova_claude.txt`:
- o ícone novo nos `<link>`, e os três do manifest saem 200 `image/png`;
- caso ZERO: "LIBERADO · nunca foi mudado", sem faixa;
- tocar e **cancelar** não cria o `claude.json` nem avisa;
- tocar e **confirmar**: `liberado: false`, "PROIBIDO · desde 14:04 · pelo
  app", a faixa, e o aviso "Claude proibido pelo app às 14:04";
- Limites: "Sonda parada: Claude proibido desde 14:04", sem nenhum "%";
  rolado 3408 px até o fim, o botão segue em y = 54;
- o "+" da capacidade dá o toast "guardado…"; `agente-inicio` com e sem
  `--forcar` sai 3 com "Claude proibido pelo Adrian desde 14:04";
- a Bancada mostra PROIBIDO; liberar por lá volta a LIBERADO e avisa, e a
  Mesa perde a faixa. Histórico: padrão → proibido → liberado.

**O 8931 foi reiniciado às 14:04:07** (`scratchpad/reiniciar_app.ps1`, pela
tarefa, na janela :55–:10): PID 1920, escutando às 14:04:15, casca `v19`,
`/api/claude` respondendo 401 sem token. O bot **não** foi reiniciado (ver
acima: o apurador sobe como processo novo a cada volta).

**Estado deixado:** liberado (arquivo ausente). Quem proíbe é o Adrian (ou o
orquestrador, a pedido dele), pelo app ou pela CLI.

## 13. Pedir imagem pelo app (29/09/2026, tarde)

Demanda urgente do Adrian pela Mesa (14:29, `ca47239a`): "os modelos que
geram imagem e etc, eu preciso ter suporte para isso também". Caso real que
veio junto: às 14:24 ele pediu pelo **Conversar** do Gemini "gere uma imagem
de um gato pra mim" (correio `dde066f1`); o Gemini desenhou, a tela ficou com
0 caracteres, o carteiro esperou 420 s por texto e falhou com "raciocínio
preso ou limite".

**O que cada gerador faz hoje** (`ias/imagem.py: gerador()`, lido da ficha
`ias/fichas/<ia>.json`; o app desenha o Criar disto):

| IA | pelo app | como gera | prova de origem |
| --- | --- | --- | --- |
| PicassoIA | 🎨 Criar, 7 proporções (a ficha ganhou `imagem.proporcoes`) | o `PicassoClient` do identity no perfil das histórias, a espera que reenvia no estouro (`contos.imagens.worker._gerar_esperando`), **Aprimorador desligado à força** | **forte**: `proveniencia.comprovar` (o card do histórico com o NOSSO prompt); a URL é reivindicada em `origens.jsonl` (`ias_<id>`) |
| Grok, Gemini, ChatGPT | 🎨 Criar (proporção escrita no pedido: 1:1, 3:4, 4:3, 9:16, 16:9) **e** imagem na conversa | o `ClienteLLM` na **casa** da IA, pelo `perguntar` de sempre | o turno nosso na tela (o último turno do usuário contém o pedido) **e** a imagem dentro da resposta a ele, no recipiente de imagem gerada, com `src` que não existia antes do envio e a geração terminada (desde 29/09 16h, ver "O gato do ChatGPT e o anúncio") |
| DreamFace | Criar **desabilitado**: "créditos 0 (ficha de 29/09…) · só há seletores… nenhuma geração em produção" | — | — |
| Digen | Criar **desabilitado**: "gera VÍDEO a partir de uma imagem (Real Motion 3.5): próximo passo" | — | — |
| 🎲 Livre | o **rodízio**: `rodizio_imagem` do `ias/config.json` (picasso → gemini → grok → chatgpt) | o primeiro que a ficha diz que gera, que faz a proporção, que está em cota e cuja conta está **livre agora** | a do gerador escolhido |

ChatGPT: medido ao vivo em 29/09 17:16 (o gato do `0edfbdb5`, abaixo): a
ficha diz `gera: true`, PNG 1254x1254 em ~33 s. O Gemini também gerou de
verdade (o gato do `dde066f1`). O Grok **não** foi provado gerando imagem.

**O correio** (`ias/correio.py`): as caixas agora são 8 (`CAIXAS`): as 4 de
chat, `picasso`, `dreamface`, `digen` e `livre`. Um pedido é
`pedir_imagem(caixa, prompt, proporcao=, modelo=)` →
`{"tipo": "imagem", "texto": <prompt>, "proporcao", "modelo_pedido",
"gerador": caixa | None (livre), ...}`; prompt até **5.000** caracteres.
Mensagem sem `tipo` é texto (tudo antes de 29/09). Texto para quem não
conversa continua recusado. Respondido, o registro ganha
`imagem: {arquivo, largura, altura, bytes, formato, sha256, prova, forca}`.

**O disco:** `%LOCALAPPDATA%\neural-fights\ias\<gerador>\imagens\<id>.<ext>`
com os **bytes originais** (a extensão sai dos bytes: png, jpg, webp) e
`<id>.prova.json` ao lado (a prova inteira). Sem prova (`comprovada`), nada
vai ao disco. `arquivo_da_imagem(caixa, id)` só devolve arquivo de pedido
**registrado e respondido**, com nome `<id>.<ext>` e dentro da pasta do
gerador; nome adulterado no registro (`../../x`) dá `None`.

**O carteiro** (`ias/carteiro.py`):
- pega a pendente mais velha das 8 caixas. Pedido para gerador que a ficha
  diz que não gera falha na hora, com o motivo, **sem abrir navegador**;
- trava da conta como a conversa (espera a pipeline, nunca mata). O
  PicassoIA usa `travas.do_perfil("picasso", "historias")`, a mesma do
  worker das histórias e do de builds;
- **parede de planos** ("Assine para Gerar"): fecha o navegador e reabre o
  perfil **uma vez**, como o worker (17/09); de novo = falha "parede";
- no chat, um pedido de imagem entra na **mesma sessão da casa** (e na janela
  de conversa de 90 s, junto das mensagens de texto);
- **motivo legível** (`imagem.classificar`): recusa do filtro → `conteudo`
  ("recusou o prompt («CONTEÚDO ILEGAL»): reescreva o pedido"; o prompt dele
  **não** é reescrito sozinho); sem prova → `sem_prova` ("nada foi
  baixado"); texto do catálogo da ficha na tela ("Voce atingiu seu limite de
  geracoes em paralelo") → `limite`; estouro → `indisponivel`; pausa do
  PicassoIA no painel → `pausado`; o chat respondeu só texto → `sem_imagem`;
- **cota:** falha `limite`/`upgrade`/`parede` tira o gerador do rodízio por
  `cota_pausa_h` (6 h) (`imagem.fora_de_cota`);
- **rodízio:** todas as contas ocupadas → espera (nota "rodízio: todas as
  contas ocupadas"); ninguém que possa gerar → falha `rodizio` com os
  motivos de cada um. O escolhido vai em `gerador` e `rodizio`;
- **Telegram:** a imagem vai como **documento** (`sendDocument`, qualidade
  original) quando o app não está olhando nem a caixa do pedido nem a do
  gerador; a falha vai em texto;
- `--duble` gera um PNG de verdade sem navegador (`imagem.png_de_teste`).

**A resposta que é uma imagem** (o gato do `dde066f1`, commit 983083f;
a régua foi apertada em 29/09 16h, ver o anúncio abaixo):
`ClienteLLM.esperar_resposta` agora também olha as imagens do turno
(`imagens_da_resposta`): só vale imagem que está na **resposta ao nosso
turno** (`imagem_turno`: o primeiro turno do assistente depois do último
turno do usuário), dentro de um **recipiente de imagem gerada**
(`imagem_gerada`), com `src` que **não existia na página antes do envio**
(`enviar` tira a foto, `_srcs_antes_do_envio`), carregada, com 256+ px,
**sem borrão**, com o `alt` de imagem final quando a IA tem um medido
(`imagem_final_alt`), sem "Criando imagem" na resposta, sem botão de parar e
estável por 5 s (`imagem_estabilidade`). Ela volta em
`imagens_na_resposta`; o carteiro baixa com a prova do turno
(`SessaoReal.imagem_da_resposta`) e grava como a de um pedido pelo Criar
(`gerador` = a IA da conversa). Só imagem, sem texto: a resposta vira
"(imagem · 1024x1024 · 212 KB)". Imagem sem prova e sem texto: falha com o
motivo. Só texto: como antes.

**Rotas** (todas com token; pedir só com `--acoes`; ler nunca depende dele):

| rota | o que faz |
| --- | --- |
| `GET /api/correio` | ganhou `imagens` (as caixas picasso, dreamface, digen, livre) e `geradores` (a ficha de cada um) |
| `GET /api/correio/<caixa>` | as 8 caixas; `conversa`, `gerador`, `rodizio`, `geradores`; cada mensagem com imagem traz `imagem.url` (`/v/<bilhete>`, reaproveitado enquanto vale mais de 5 min: a tela relê a cada 6 s) e `imagem.nome` — **nunca** o caminho |
| `POST /api/correio/<gerador|livre>/imagem` `{prompt, proporcao, modelo?}` | o pedido; 400 com o motivo da ficha (proporção que o gerador não oferece, DreamFace, Digen, modelo que não existe, vazio, > 5.000); 403 sem `--acoes`; direto, sem confirmação (decisão `mensagem-para-uma-ia-pelo-app-direto-ou`: gera na conta dele, não publica) |
| `GET /api/imagem/<caixa>/<id 8 hex>` | o bilhete da imagem de um pedido registrado e respondido; 404 para pendente, adulterado ou inexistente |
| `GET /api/imagens?ia=<gerador>` | a galeria (todas, ou as de um gerador; o rodízio conta no escolhido), com bilhete |
| `POST /api/correio/<caixa>/visto` | vale para as 8 |

Imagem pedida sem `Range` vem inteira com 200 até 24 MB
(`IMAGEM_INTEIRA_MAX`; antes, 4 MB): um PNG do ChatGPT passa de 4 MB, e um
`<img>` não remonta um 206.

**No app** (`app/conversa.js`, casca `v20`):
- o cartão do prédio tem **🎨 Criar** ao lado do 💬 Conversar (Grok, Gemini,
  ChatGPT) ou sozinho (PicassoIA). No Digen ele aparece **desabilitado**,
  com "🎨 não gera imagem hoje: … (próximo passo)";
- a tela tem 8 chips (as 4 de chat, PicassoIA, DreamFace, Digen e 🎲 Livre)
  e os modos da IA (💬 Conversar / 🎨 Criar / 🖼 Galeria);
- o **Criar**: o aviso (modelo, nota da ficha, ou o motivo em vermelho), o
  prompt (`maxlength` = o teto), a proporção (as da ficha) e o modelo (só
  quando a ficha dá mais de um);
- o balão do pedido: "🎨 prompt", "proporção 1:1 · rodízio → 🎨 PicassoIA",
  e a situação: "na caixa" → "**gerando… (Xs)**" (anda a cada segundo pelo
  relógio do PC, sem reler) → "gerada HH:MM em N s · modelo", ou
  "falhou: motivo";
- o balão da IA: a **miniatura**; tocar abre a **tela cheia** com ⬇ Baixar
  (os bytes do PC, com o nome `<gerador>_<id>.<ext>`) e ↗ Compartilhar (a
  folha do sistema, com o arquivo; sem suporte, "use ⬇ Baixar");
- a **galeria** por IA (no 🎲 Livre, todas), em 3 colunas.

**Testes:** `ias/test_imagem.py` (38: o pedido no correio, o caso ZERO,
os geradores pela ficha, o carteiro gerando arquivo com prova e bytes
originais, sem prova → nada no disco, recusa de conteúdo, cota → motivo e
fora do rodízio, parede reabre uma vez / duas vezes falha, gerador que não
gera não abre navegador, trava da pipeline espera, app olhando sem Telegram,
imagem na casa do chat, o rodízio escolhendo o livre / pulando o fora de
cota / esperando / desistindo com os motivos / pela proporção, a conversa
que respondeu com imagem, e a `SessaoReal` baixando com a prova do turno);
`remoto/test_imagem_app.py` (11: as listas de caixas batem, caso ZERO, 401,
403, o pedido, as recusas com motivo, imagem só por bilhete de pedido
respondido e byte a byte, pendente/adulterado/rota torta = 404, galeria,
conversa com imagem, visto); e
`historias/tests/test_resposta_com_imagem_regressions.py` (4). Nenhum abre
navegador nem toca o `%LOCALAPPDATA%` real.

**Prova de tela (dublê, 29/09 15:0x):** 390×844, clicando, na 8934
(`scratchpad/servidor_conversa.py` + `prova_imagem.py`, correio em
`E:\projetos-wt\_prova_imagem\ias`, carteiro `--duble --demora 8`). Todas
as conferências OK, 0 erros de JS; telas em
`E:\projetos-wt\_prova_imagem\telas\duble_*.png`, relatório em
`prova_duble.txt`:
- Digen: 🎨 Criar desabilitado, com "gera VÍDEO… (próximo passo)"; Grok:
  Conversar e Criar lado a lado; PicassoIA: só Criar;
- Criar · PicassoIA: 8 chips, modos Criar/Galeria, as 7 proporções, sem
  seletor de modelo, o aviso com "PicassoIA Image" e "Aprimorador
  desligado", o caso ZERO;
- o pedido "a red circle on white" 1:1: "gerando… (6s)" → "(8s)" sem
  recarregar, depois a miniatura carregada, "gerada 15:00 em 8 s · dublê",
  a imagem e o `.prova.json` no disco;
- tela cheia; ⬇ Baixar entrega o arquivo **byte a byte igual** ao do PC;
  ↗ Compartilhar busca os bytes (`GET /v/` no log) para a folha do sistema;
- galeria; DreamFace com "créditos 0" e tudo desabilitado; 🎲 Livre com a
  ordem do rodízio e "rodízio → 🎨 PicassoIA"; falha "nada foi baixado"
  aparece no balão; o Grok tem os três modos e a imagem fica na conversa.
- A prova pegou um defeito: trocar de chip não redesenhava os modos (o Grok
  aparecia com os modos do PicassoIA, sem 💬). Consertado antes do commit.

**O gato do Gemini (`dde066f1`), de verdade:**
- 15:23: reenviado **uma vez** depois do 983083f (delta `situacao:
  pendente`, `nota: "reenviada uma vez…"`). A espera reconheceu a imagem em
  **25 s** ("resposta com imagem (1024x559) e 0 chars"), contra os 420 s e a
  falha de 14:31. Mas o download pelo `src` falhou: a sessão não devolveu
  imagem e o `fetch` da página deu "Failed to fetch" (CORS do
  googleusercontent);
- diagnóstico na casa, só leitura (`scratchpad/diag_botao_gemini.py`): cada
  imagem tem "Baixar imagem no tamanho original", que nasce **disabled** até
  a imagem carregar (a conversa rola num container próprio; imagem fora da
  vista não carrega). O clique busca `gg` (texto) e `rd-gg` (o JPEG inteiro)
  e só então solta o download `Gemini_Generated_Image_*.jfif`. Com a API
  síncrona do patchright o evento só chega dentro de uma chamada: esperar
  com `time.sleep` o perde (`wait_for_timeout`, sim). E um `src` vazio fazia
  o `fetch("")` baixar a própria página (864 KB de HTML) — agora recusado;
- dd4f4dc: `imagem.baixar_pelo_botao` (só o Gemini tem botão medido,
  `BOTAO_BAIXAR`), e depois o `src`;
- o gato foi **recuperado da casa sem mandar nada de novo**
  (`scratchpad/recuperar_gato.py`, com a trava da conta): o JPEG original,
  **2816×1536, 2.992.466 bytes** (a tela mostrava 1024×559), com a prova do
  turno, em `ias\gemini\imagens\dde066f1.jpg`; a mensagem virou
  "respondida · (imagem · 2816x1536 · 2922 KB)" e o **Telegram recebeu o
  documento**.

**A prova real do PicassoIA (29/09, 15:41–15:43)**, pelo app de ponta a
ponta: 8934 com o **correio real** (`servidor_conversa.py … --correio-real`)
e o **carteiro real** (PID 8776, reiniciado às 15:40 com o código novo),
390×844, clicando (`scratchpad/prova_imagem.py … real`). Todas as
conferências OK, 0 erros de JS; telas em
`E:\projetos-wt\_prova_imagem_real\telas\real_*.png`, relatório em
`prova_real.txt`:
- Vila → PicassoIA → 🎨 Criar → "a red circle on white", 1:1 → a tela
  fechada (de volta à Vila);
- o carteiro: sessão válida, proporção 1:1, quantidade 1, presets
  `modelo=PICASSOIA IMAGE`, prompt de 21 chars enviado; "imagem pronta
  (1024x1024) em 4s" — e **"a imagem que apareceu primeiro NÃO é a do nosso
  prompt; vale a do card do histórico"**: a guarda da conta compartilhada
  trabalhou ao vivo;
- 15:42:47 "imagem gravada (2d16d86d.jpg, 21 KB, prova historico_prompt) em
  68s"; 15:42:50 "aviso no Telegram entregue" (o documento);
- de volta ao Criar: a miniatura carregada, "gerada 15:42 em 68 s ·
  PICASSOIA IMAGE", "prova: card do histórico"; `2d16d86d.jpg` (1024×1024,
  21.779 bytes) e `2d16d86d.prova.json` (`forca: forte`) em
  `%LOCALAPPDATA%\neural-fights\ias\picasso\imagens\`; a imagem é um
  círculo vermelho sobre branco;
- tela cheia; ⬇ Baixar = o arquivo do PC **byte a byte**; ↗ Compartilhar
  busca os bytes; galeria com a imagem.
- A foto `real_7_gerada.png` mostrou o Criar (preso embaixo) cobrindo
  metade da miniatura: ele deixou de ser `sticky` (`#conversa-criar {
  position: static }`); conferido depois: miniatura em y 442–702, o Criar
  começa em 760 (`real_10_criar_depois_do_ajuste.png`).

**O gato do ChatGPT e o anúncio (`d228c94f`, 29/09 16:02; defeito
`f9b134e9`).** O Adrian pediu "Crie um gato para mim" pelo 🎨 Criar do
ChatGPT. O correio disse "imagem pronta · 512x512 · 35 KB" em 32 s, com
prova `turno_na_casa`, e o arquivo era a foto de uma **mesa de som com uma
xícara de café**.
- **Causa, medida na tela** (a casa aberta só para leitura, sem mandar
  nada: `scratchpad/diag_chatgpt_imagem.py` e `diag_chatgpt_baixar.py`;
  captura em `E:\projetos-wt\_prova_imagem_chatgpt\diag\casa_viewport.png`):
  a mesa de som é a miniatura de um **anúncio** que o ChatGPT põe embaixo da
  resposta ("CAVN AI · AI Music Videos · Anúncio", 512x512,
  `images.openai.com/static-rsc-5/…`). Ele fica **dentro do mesmo**
  `section[data-turn=assistant]` do gato, e depois dele na página. A regra
  antiga ("depois do último turno do usuário") pegava a **última** imagem
  grande depois do turno: o anúncio. O gato de verdade (1254x1254, "Imagem
  gerada: Retrato Aconchegante de Gato Tigrado", `backend-api/estuary/
  content`) estava na tela e foi ignorado. Não havia imagem antiga na casa
  (só texto): "dentro do turno" sozinho também não bastaria.
- **O que o DOM do ChatGPT tem** (29/09): turnos em `section[data-turn=
  user|assistant]` (`data-testid=conversation-turn-N`); a resposta só de
  imagem **não** tem `data-message-author-role`; a imagem gerada mora em
  `div#image-<uuid>` com a classe `group/imagegen-image`, em três `<img>`
  com o mesmo `src` (uma sob fundo borrado). O "Baixar" só existe na
  visualização em tela cheia (clique na imagem → `[role=dialog]
  button[aria-label=Baixar]`) e entrega os **mesmos bytes** do `src`
  (PNG 1254x1254, 2.587.976 bytes, mesmo sha256).
- **O Gemini** (medido do mesmo jeito, `diag_gemini_recipiente.py`): a
  imagem mora em `model-response … generated-image > single-image`, com o
  botão "Baixar imagem no tamanho original" no mesmo `single-image`; a regra
  antiga acertava por sorte (não há anúncio lá).
- **O conserto** (`contos/llm/cliente.py`, `seletores.py`, `ias/imagem.py`):
  - seletores novos por IA: `imagem_turno`, `imagem_gerada`,
    `imagem_final_alt` (ChatGPT: "Imagem gerada"/"Generated image"),
    `imagem_baixar` e `imagem_abrir_para_baixar` (ChatGPT). O `BOTAO_BAIXAR`
    de `ias/imagem.py` saiu: o botão vem dos seletores;
  - o JS devolve só as imagens do recipiente, por `src` (as três cópias
    viram uma; "borrada" só se todas estiverem), diz se a resposta mostra
    "Criando/Gerando imagem" e conta as grandes **fora** (o anúncio), que
    vão ao log: "N imagem(ns) grande(s) FORA da resposta ignorada(s)";
  - a espera loga uma linha "imagem: …" a cada mudança do que vê (a medida
    da geração ao vivo; só quando há imagem, anúncio ou "gerando": a
    pipeline reescrevendo prompt no ChatGPT não ganha a linha); texto parado com imagem a caminho não fecha a
    espera; no estouro vale a mesma régua (nada de prévia);
  - `baixar_da_resposta` **refaz a prova** na hora de baixar: nosso turno,
    a imagem ainda dentro da resposta, `src` fora da foto de antes do envio,
    geração terminada. Falhou uma = `SemProva`, **nada no disco**. A prova
    gravada ganha `dentro_da_resposta`, `src_novo`,
    `imagens_antes_do_envio`, `ignoradas_fora_da_resposta` e o `alt`;
  - o botão de baixar é o do mesmo recipiente da imagem escolhida (antes:
    o último da página depois do turno); o do ChatGPT abre a tela cheia,
    baixa e fecha com Escape; arquivo com forma diferente da imagem da tela
    (proporção, 3%) não vale e cai no `src`;
  - IA sem os dois seletores não procura imagem (o DeepSeek); o Grok usa o
    balão `assistant-message` inteiro como recipiente até a primeira imagem
    real medir o dele.
- **Testes:** `historias/tests/test_imagem_do_nosso_turno_regressions.py`
  (13: antiga + nova no nosso turno → a nova; geração em andamento →
  espera; botão de parar → espera; sem imagem nova → falha; sem o alt
  final; sem a resposta ao nosso turno; texto parado esperando a imagem;
  estouro com a mesma régua; turno só de texto não escreve "imagem:" no
  log; caso ZERO: IA sem recipiente, página sem turno, página que não
  responde); `ias/test_imagem.py` (+14: a prova
  refeita na hora de baixar, o anúncio aceito pela espera vira `falhou`
  sem arquivo pelo carteiro inteiro, a imagem antiga idem, o ChatGPT
  baixando pela tela cheia, a proporção, o `src` vazio que nunca baixa a
  página); e
  `historias/tests/test_imagem_js_no_navegador.py` (5), que roda o JS num
  **Chrome headless de verdade** com a estrutura medida (anúncio incluído)
  — só com `NF_TESTE_NAVEGADOR=1`, fora da suíte normal.
- **Conferido na casa real do Gemini** (só leitura,
  `scratchpad/conferir_js_casa_real.py`): o JS novo acha 1 imagem, a do
  último turno, no `generated-image`; nada "fora"; o botão marcado é o
  "Baixar imagem no tamanho original" do mesmo recipiente.
- **A prova real (29/09, 16:44–17:20).** O `d228c94f` virou `falhou`
  ("imagem errada: não era do nosso turno…"), com `imagem` vazia; o
  arquivo errado e a prova foram para `ias\chatgpt\imagens\_erradas\`. O
  carteiro foi reiniciado com o código novo (PID 4564, 16:41). O pedido foi
  reenviado **uma vez**, pelo 🎨 Criar do ChatGPT na instância 8934 com o
  correio real (`scratchpad/prova_gato_chatgpt.py`, 390x844, clicando),
  e a tela foi fechada. Resultado, `0edfbdb5`:
  - 16:44–17:16 o carteiro **esperou a pipeline** (a rodada das histórias
    abriu o ChatGPT às 16:37 para reescrever prompt bloqueado e o segurou até
    o fim das imagens), sem forçar;
  - log da espera: 17:16:22 "a IA diz que ainda está gerando"; 17:16:47 "1
    no recipiente (1254x1254, alt «Imagem gerada: Gato tigrado aconchegado
    na cama»); 1 final e nova"; aceita às 17:16:54 (33 s); 17:16:57
    "baixada pelo botão do site: ChatGPT Image … .png (2481992 bytes)";
    17:17:32 "aviso no Telegram entregue" (o `sendDocument` respondeu ok);
  - a prova gravada: `dentro_da_resposta`, `src_novo`,
    `imagens_antes_do_envio: 3`, `download: botao_tamanho_original`;
    arquivo `0edfbdb5.png`, PNG 1254x1254, 2.481.992 bytes: um gato;
  - **capturas da janela durante a geração** (PrintWindow, a cada ~3 s,
    `scratchpad/vigia_janela_chatgpt.py`; em
    `E:\projetos-wt\_prova_gato_chatgpt\janela\`): 17:16:26 "Criando
    imagem" com o botão de parar; 17:16:45 a imagem **revelando de cima
    para baixo com o botão de parar já sumido** ("Iniciar Voz") — o botão
    sozinho não prova que acabou, e por isso a estabilidade de 5 s; 17:16:49
    completa; 17:16:55 a tela cheia aberta pelo carteiro com o botão de
    baixar. Desta vez não houve anúncio (`ignoradas_fora_da_resposta: 0`);
  - no app (`E:\projetos-wt\_prova_gato_chatgpt\telas\`): o `d228c94f`
    aparece "16:02 · falhou: imagem errada: não era do nosso turno…", e o
    reenvio "16:44 · gerada 17:16 em 40 s · chatgpt" com a miniatura do
    gato (`5_gerada_no_app.png`); a tela cheia abre, e o ⬇ Baixar entrega o
    arquivo do PC **byte a byte**. O toque na Vila não achou o prédio do
    ChatGPT (o script entrou pelo chip, que abre o mesmo Criar).

**Grok e Digen ao vivo (29/09, 17:30–17:56, tarefa 80c3fa98).**
- **Grok pela Vila: não provado.** Dois pedidos pelo correio como o app faz
  (`899d74b9` 17:30 e `7d2dd374` 17:44, "gato laranja…" 1:1), entregues pelo
  carteiro PID 15260. A captura da janela nas duas: toast "Grok is
  experiencing issues…" e, no lugar da resposta, o card **"Alta procura — Por
  favor, tente novamente em breve, ou atualize para um acesso com maior
  prioridade"** (botão Aprimorar, nunca clicado). A espera gastou os 420 s
  (0 chars) e o pedido virou `falhou` com esse texto (`erro_site` no
  primeiro; `indisponivel` no segundo, depois que o texto entrou no
  `catalogo_textos` da ficha). Uma terceira tentativa e o reinício do
  carteiro (para carregar o recipiente novo) foram barrados pela
  permissão desta sessão: ficam para quem me chamou.
- **O recipiente do Grok foi medido e apertado** (0b3a910), só leitura, na
  conversa "Círculo de cor vermelha" da conta (a imagem que a sonda de 01:44
  pediu): a gerada é `assets.grok.com/users/<conta>/generated/<uuid>/image.jpg`
  num `div.group/image`, alt "Imagem gerada"; o anexo do usuário é
  `/users/<conta>/<uuid>/preview-image`; a foto do perfil fica na barra
  lateral. O balão inteiro aceitava uma imagem da **web** dentro da resposta
  (medido no Chrome headless); o novo seletor não. Na casa real ele acha 1
  imagem, 784x1168, e a sessão a baixa (JPG 784x1168, 109.323 bytes): o
  pedido era 1:1 — o Grok não respeita a proporção escrita.
- **Digen: parou na parede de plano.** Pelo `DigenClient` de produção, com a
  trava do perfil (`scratchpad/digen_prova.py`): logado, chip **"Free, Meme
  149, Pro Meme 0"**; Space novo, o gato `0edfbdb5` anexado (miniatura no
  composer), RM3.5 / 8s / 480P / 1:1, enviar → "Creating Task…" → **"Upgrade
  your plan to unlock this model"** (US$4.99). Parei (regra: não contornar);
  nenhum vídeo, nada baixado. O guarda do cliente fecha esse diálogo no ESC
  como se fosse propaganda e `ERRO_GERACAO` não conhece o texto — a fila de
  vídeo das builds deve bater na mesma parede sem acusar. Capturas em
  `%LOCALAPPDATA%\neural-fights\ias\digen\provas\`; decisão no Grimório
  `geral/digen-plano-free`.

**Pendências e o que é do Adrian:**
- O Grok gerando imagem **pela Vila** não foi provado (ver acima): falta
  uma tentativa fora da "Alta procura", com o carteiro reiniciado no
  recipiente novo. A espera **já reconhece** o card desde 02df6bd (sai em
  segundos com `SiteIndisponivel`, `indisponivel` + `pausa_rodizio`), e o
  grok.com **em branco** na abertura (30/09 09:16) também vira
  `SiteIndisponivel` em vez de "chat aberto" (a casa não é abandonada nem
  conta falha). O botão de baixar do Grok não foi medido;
- ~~`ias/sonda.py` com o seu próprio `_imagens_da_resposta`~~ — resolvido
  em 29/09 (tarefa 4c0615e6): a sonda pede com `imagem.pedido_de_imagem`,
  espera com `ClienteLLM.esperar_resposta` e baixa com
  `imagem.baixar_da_resposta` (recipiente da resposta ao nosso turno, src
  novo, geração terminada); a regra antiga e o `_baixar_imagem` saíram. No
  dublê de `ias/test_sonda.py` o código velho dava `gera: True` só com o
  anúncio e baixava o anúncio (512x512) no lugar do círculo (300x300); o
  novo dá `gera: False` e baixa o círculo. Sem resposta final no prazo, ou
  imagem sem prova, a ficha fica `gera: None` (não medido), nunca `True`.
  Não rodada ao vivo;
- DreamFace: sem cliente com prova de origem e créditos 0 (01/09). Digen:
  vídeo a partir de imagem pede plano hoje (conta Free; decisão
  `digen-plano-free`); o anexo da imagem nossa funciona;
- o rodízio é simples de propósito (ordem fixa, cota por falha recente); a
  fase 3 amplia (peso, custo, qualidade);
- modelo: nenhum cliente troca de modelo de imagem hoje (o PicassoIA fica
  no "PicassoIA Image" da URL do criador); o seletor aparece quando uma
  ficha der mais de um.

## 14. O lote da semana no bot, no painel e no app (30/09/2026)

Tarefa 1e396735 da Mesa, parte app-e-bot do plano "lote semanal de dia"
(`~/.claude/plans/lote-semanal-de-dia.md`; decisões `geral/lote-*`: janela
07–22h, histórias seg–qua, builds seg–ter, piso de reposição 20 vídeos,
1º lote seg 05/10).

**O defeito medido.** O relatório de metas (`PISO_DE_ESTOQUE = 1` dia) e o
painel flutuante (`dias < 1`) ainda alertavam abaixo de UM dia, enquanto a
criação já repunha abaixo de 20 vídeos. Às 11:53 de 30/09: histórias 6
vídeos (0,6 dia), builds 17 (1,7 dia), piso 20 nos dois. O relatório dizia
"builds: 1 dia(s)" sem alerta; agora diz "lote 17/69 · piso 20 ⚠ abaixo do
piso". E, sem conseguir contar, a seção de estoque **sumia** do relatório.

**Um cálculo, três telas.** `remoto/lote.py`:
- `resumo(agora, postar=None)` — um dict pronto para JSON, sempre com os dois
  canais. Os números vêm de `postar.estoque_do_lote` (o funil da escolha,
  sem retidas; o piso de `piso_de_alerta`; o alvo = horários da grade até
  seg 07h + piso). A janela e os dias de lote vêm do config de quem cria
  (`agenda.json`, `geracao.json`); "lote em curso até qua 07/10 22h" /
  "próximo lote: seg 05/10" vem de `agenda.lote_valendo`. Cada canal leva um
  `texto` pronto e uma `situacao` (`sem_conta`, `abaixo_do_piso`, `sem_alvo`,
  `falta`, `cobre`). Nunca levanta.
- `linhas(resumo)` — o Markdown do Telegram; `texto()` — o /lote.

Quem mostra:
- **relatório de metas** (21:00 e `/metas`): a seção "*Lote da semana*"
  substitui "*Estoque*" e aparece sempre;
- **`/lote`** no bot (só leitura, na tabela e na `/ajuda`);
- **painel flutuante**: a `previsao` (subprocesso) põe `lote` no JSON; a
  janela troca GORDURA por LOTE DA SEMANA (vermelho: abaixo do piso ou sem
  contagem). A `previsao` ainda manda `gordura` (dias inteiros do mesmo
  lote) só para a janela antiga, até ela reiniciar;
- **app** (Avisos, bloco da previsão): as mesmas linhas; casca `v21`.

**Caso ZERO** (`remoto/test_lote.py`): zero vídeo = "lote 0/69 ⚠ abaixo do
piso"; `-1`, canal ausente ou `postar` que explode = "não deu para contar o
estoque", nunca "✓ cobre"; um teste usa o `estoque_do_lote` e o
`piso_de_alerta` **de verdade** com a contagem dada.

**O que exige reinício** (não feito pelo agente): o **bot** (para o `/lote`
e o relatório novo) e o **app** (o relatório de metas dos Pergaminhos). A
casca do app e a `previsao` são lidas do disco a cada vez. A **janela
flutuante** (`NeuralFights_vila_flutuante`, parte painel-e-vila) só mostra a
seção nova depois de reiniciar; até lá segue com a GORDURA antiga.

## 15. O script que não chegava: sem "Conversar" nem "Criar" (30/09/2026)

Tarefa 74856214 da Mesa. Às 13:10 ele disse, pelo app: "Não estou
conseguindo conversar nem pedir imagens pras IAs".

**O que o log do 8931 mostrava.** A carga da página de 12:01:17 recebeu
`/`, `app.css`, `app.js`, `vila.js`, `comandos.js`, `decisoes.js` e
`orquestrador.js`, mas **não o `conversa.js`**. (A lista das 12:01:21, logo
depois do `GET /sw.js`, é o precache do service worker, não carga da
página.) Sem esse arquivo, `conversaAbrir` não existe, e o `vila.js` só
desenha "💬 Conversar" e "🎨 Criar" quando ela existe. O cartão do prédio
ficou só com "Ver no diário": às 13:06:55 ele tocou nesse botão, o único
que havia. Entre 12:01 e 13:15 não houve nenhum `GET /api/correio/<ia>`. A
carga de 13:15:09 recebeu o `conversa.js`, e a conversa do Gemini abriu às
13:15:14.

Varrendo o log inteiro, a mesma coisa aconteceu às 14:54:07 de 29/09: a
carga perdeu o `vila.js` e o `conversa.js`, e nenhuma conversa abriu até a
carga das 15:07.

**Reproduzido num Chrome de verdade** (412×915, instância de teste na 8934
com o estado copiado para `E:\projetos-wt\_prova_conversa30`, scripts em
`scratchpad/sonda_*30.py`):
- com o `conversa.js` respondendo 502, o cartão do DeepSeek ficou
  `['Ver no diário']`, e o do PicassoIA também;
- com tudo carregado, conversar e Criar funcionaram tocando: o POST chegou
  e a mensagem entrou na caixa de teste.

**A causa, medida.** O `Servidor` herdava `request_queue_size = 5` do
socketserver. No Windows, a conexão que chega além dessa fila leva RST. Uma
carga abre cerca de 8 conexões de uma vez (os scripts), enquanto o surto
de `/api` da carga anterior ainda está em voo. O `tailscale serve` troca a
recusa por 502, e o service worker repassava o 502 para a página.

A medida foi feita no navegador, recarregando no `load` como o app faz
(`scratchpad/medir_fila_test.py`):

| fila | cargas | cargas que perderam script |
| --- | --- | --- |
| 5 | 145 | 22 (`ERR_CONNECTION_REFUSED`) |
| 64 | 170 | 0 |

Os testes de navegador novos também falhavam 5 de 8 vezes com a fila em 5;
com 64, passaram 10 de 10.

**O conserto:**
- `api_http.Servidor.request_queue_size = 64`;
- `sw.js`: uma resposta diferente de 200 (o 502) cai na cópia guardada. Só
  quando não há cópia o erro segue para a página. Casca `v22`;
- `app.js`: no `load`, confere se cada script chegou (a lista `MODULOS`,
  com a função de entrada de cada um). Se faltar algum, recarrega **uma**
  vez sozinho (a trava é o `sessionStorage` `painel.modulos`). Se ainda
  faltar, a faixa `#modulo-faltando` mostra o nome do arquivo e um botão
  "Recarregar". O `<html data-modulos>` diz `ok` ou a lista do que falta,
  para as provas de tela.

**Testes** (`remoto/test_app_modulos.py`):
- a fila da classe e a do servidor criado são pelo menos 64;
- todo `<script>` do `index.html` está na lista `MODULOS`, e cada função
  da lista existe no topo do arquivo dela. Renomear a função sem mexer na
  lista daria recarga e faixa falsas;
- o `sw.js` roda no **Node**, com `caches` e `fetch` dublês: 502 e rede
  caída caem na cópia, 200 vem da rede, e sem cópia o 502 segue;
- com `NF_TESTE_NAVEGADOR=1`: um 502 no `conversa.js` faz uma recarga e
  volta `ok`; um 502 que não passa faz uma recarga só e mostra a faixa, sem
  laço.

**Reinício:** o 8931 foi reiniciado às 13:57:35 (PID 12968, com
`scratchpad/reiniciar_app.ps1`) e serve a casca `v22`. **No celular:**
fechar o app e abrir de novo, uma vez.
