# Painel e Vila

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/painel-e-vila/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (28/09/2026) · “28/09 20:29, no chat: 'trabalhe em duas tarefas ao mesmo tempo' — max_paralelo 2” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Passou de 50%, para tudo; força total 20 min antes de renovar (28/09/2026) `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Ligada, 20 min antes de renovar (28/09/2026) `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`

**Painel e Vila**
- ✅ **Tarefa da Vila acorda o PC** — Tirar o acordar da tarefa da Vila (recomendado) (28/09/2026) `tarefa-da-vila-acorda-o-pc`
- ✅ **Cara da Oficina** — Quente, igual à Vila (como está) (28/09/2026) · “Eu descartei essa vila” `cara-da-oficina`
- ✅ **Zoom da Vila no celular** — Perto e grande (como está) (28/09/2026) · “Também adicionei suporte se eu deitar o celular, pode mudar as casas de lugar se for mais fácil, não ligo” `vila-zoom-celular`
- ✅ **Aposentar a Vila em pixel e a Oficina** — Aposentar (tirar do painel e do código) (28/09/2026) `aposentar-vila-pixel`

<!-- decisoes:fim -->

Documento de passagem. Tudo abaixo foi conferido no código e na máquina em 27/09/2026.

## 1. Painel, flutuante, e como abrir

| Peça | O que é | Como abrir |
| --- | --- | --- |
| **Painel** | três janelas grandes, cada uma um processo (`painel/app.py` + `painel/paginas/`) | `painel.bat` → `ferramentas/abrir.py painel`; ou `python -m painel` |
| **Vila flutuante** | uma janela pequena, **sem borda do Windows**, sempre por cima, no lugar dos consoles pretos (`painel/flutuante/`) | dois cliques em `vila_flutuante.pyw`; `python -m painel.flutuante`; ou o botão **🪟 Vila flutuante** na página Vila |

As três janelas (`painel/janelas.py`, `JANELAS`): **🏘 Vila** — o hub, uma página
só, e daqui se abrem as outras; **🎬 Criação de vídeos** — auditoria,
confiabilidade, fluxo, publicar, experimentos, vídeos, histórias, espelho,
contas, reações (a única com `pipeline: True`, a faixa do freio de mão);
**🎮 Jogo** — torneio, simulação, database, live, áudio.

`janelas.abrir()` usa `pythonw` + `DETACHED_PROCESS`: **fechar quem abriu não
fecha quem foi aberto**. Decisão do Adrian (01/09/2026) — uma travar não pode
derrubar as outras; e duas telas Tk pesadas no mesmo processo disputam a mesma
thread, então a Vila engasgaria enquanto a galeria varre o disco.

**Os quatro tamanhos** da flutuante (`flutuante/preferencias.py`), cada um
respondendo uma pergunta: **ÍCONE** 56×56 ("está tudo bem?" — borda colorida e
selo de erros); **FAIXA** 340×64 ("o que roda e quando sai o próximo?");
**MÉDIO** 720×520 (pedido explícito, não passa disso: Vila + quem está vivo +
abas Diário/Postagem/Erros/Terminal); **GRANDE** até 1180×700, limitado pela tela.

**O ícone é o "fechar".** `✕` e `−` **viram o ícone**, não fecham: janela sem
borda não aparece na barra de tarefas nem no Alt-Tab, e fechar de verdade
esconderia os alertas (`pystray` não está instalado; o ícone faz o papel da
bandeja). O pedido de fechar que vem **do sistema** (WM_CLOSE: "Finalizar
tarefa", `taskkill` sem `/F`, o Alt+F4 das janelas comuns) também vira o
ícone desde 28/09 — antes ele destruía a janela calada (ver §5). Sair de vez: botão
direito → **Fechar de verdade**. O mesmo menu troca tamanho, arte
(fofa/clássica), "sempre por cima", prever agora e abrir o painel.

## 2. Como a Vila se mantém no ar

Tarefa **`NeuralFights_vila_flutuante`**, conferida em 28/09:
`wscript.exe //B //Nologo …\oculto.vbs E:\projetos\vila_flutuante.cmd`,
repetição **PT10M** sem fim, último resultado `0`. O `//B` é o que faz **não
haver janela preta** (mesmo padrão das outras 25 tarefas do projeto).

**Quem instala** (desde 28/09): `python -m painel.flutuante.tarefa`
(`flutuante/tarefa.py`). Sem bandeira é **a seco**: mostra a raiz, o pythonw, a
ação e a diferença entre o `.cmd` que está no disco e o que ele escreveria.
`--instalar` escreve o `.cmd` e cria (ou recria) a tarefa com
`schtasks /Create … /SC MINUTE /MO 10 /RL LIMITED` + os ajustes de
`builds.tarefas_windows.endurecer`, **menos o de acordar o PC** (ver §6);
`--ajustar` só reaplica esses ajustes na tarefa existente; `--lancador` só reescreve o `.cmd`;
`--desinstalar` remove a tarefa. Os caminhos **vêm do ambiente**: o
`pythonw.exe` ao lado do Python que roda o instalador e a raiz dos dados
(`caminhos.raiz_dos_dados`). Por isso o `vila_flutuante.cmd` é **gerado e fica
fora do git**, como o `bot.cmd` e o `postar.cmd`: numa máquina nova, clone +
`--instalar`. Sem o `oculto.vbs` (pacote `builds`) o instalador **recusa**, em
vez de apontar a tarefa direto para o `.cmd`. A tarefa que está no ar foi
criada à mão em 27/09 com os mesmos parâmetros e não foi recriada; só o
`.cmd` foi reescrito pelo `--lancador` (28/09, 07:56), e a batida seguinte
da tarefa rodou com ele sem abrir segunda Vila. O modo a seco diz se o `.cmd`
do disco ainda é o que o instalador escreveria (`lancador_igual`). Medido na
batida das 08:04, com a máquina carregada: a instância levou **~5 min** para
terminar (o `wscript` viveu de 08:04:00 a 08:08:59; nesse tempo o Agendador
mostra `267009` = "em execução", depois `0`). O prazo de 2 min do `.cmd` é o
da consulta (`-OperationTimeoutSec`), não o da batida inteira; como a
repetição é de 10 min e a regra é `IgnoreNew`, isso não acumula. Às 15:34 o
resultado seguia `0`, com a mesma Vila desde 07:24.

**A guarda contra roubar foco mora no `.cmd`**: a janela já tem instância única,
mas o segundo lançamento **traz a janela para a frente de propósito** — é o que
faz o atalho funcionar, e repetir isso de 10 em 10 minutos roubaria o foco do
dono o dia inteiro. Então o `.cmd` procura um `pythonw.exe` cuja linha de comando
casa com `painel.flutuante|vila_flutuante` e **só lança se não houver nenhum**.
E **na dúvida não abre** (desde 28/09): se a consulta ao WMI falhar ou passar
de 2 min, o `.cmd` sai sem lançar e a próxima batida tenta de novo. Antes, o
erro do WMI deixava a variável vazia e o `.cmd` lançava — o segundo lançamento
que rouba o foco. O teste roda o `.cmd` gerado pelo `cmd` de verdade, com o WMI
e o `Start-Process` trocados por dublê.

Não duplicar instância: mutex nomeado `Local\NeuralFights_VilaFlutuante`
(`flutuante/__main__.py`) e, em vez de sair calado, o segundo processo **pede
para a viva aparecer** — `flutuante/sinal.py` escuta em 127.0.0.1 numa porta
escolhida pelo sistema e grava porta + segredo em `flutuante.sinal` (sem isso,
janela sumida não voltava nunca mais: bug de 17/09).

**O PID muda, e isso não é defeito em si**: cada queda é reposta pela tarefa
em até 10 min com um processo novo (em 27/09 foram três: a de antes das
18:50, a 17020 e a 18316; a 7720, que nasceu às 20:54, acabou no reinício do
Windows às 07:21 de 28/09 — evento 1074 do winlogon —, e a 11728 subiu às
07:24, já com a caixa-preta). Para saber o PID de
agora, a linha de comando é a do `.cmd` (`pythonw -X utf8 -m painel.flutuante
--medio`). Para saber **por que** a anterior acabou, leia a **caixa-preta** no
`flutuante.json` (desde 28/09):

- `vida`: `pid`, `desde`, `visto` (o "estou viva", a cada 5 min) e `saiu`
  (`"menu"` quando alguém usou **Fechar de verdade**);
- `quedas`: as últimas 10 vidas que acabaram **sem** passar pelo menu, com o
  último `visto` (a hora da queda, com 5 min de folga), `notada` (quando a
  seguinte subiu e percebeu) e `windows_reiniciou` quando o Windows ligou
  depois do último sinal. Queda nativa (crash) também deixa evento no Visualizador de
  Eventos (Aplicativo, `pythonw.exe`, 1000/1001); morte de fora
  (TerminateProcess) só deixa rastro aqui;
- `fechar_pedido`: quantas vezes o sistema pediu para fechar (WM_CLOSE) e a
  última. Hoje isso vira o ícone; a conta mostra se acontece na prática.

## 3. De onde vêm os dados

`flutuante/caminhos.py` é o mapa, `flutuante/dados.py` são funções **puras** de
leitura, `flutuante/coletor.py` é a única thread que toca disco (quatro ritmos:
disco 2-4 s, processos 15 s, previsão 10 min, tarefas 5 min).

- **Diário** `%LOCALAPPDATA%\neural-fights\atividade.jsonl` — quem trabalha, o
  balão do que está sendo feito, os erros das últimas 2 h.
- **Travas** `…\locks` — qual conta está em uso, por prédio.
- **Ledgers** `random_builds/outputs/_publicar/publicados.jsonl` e o de
  `historias/` — placar, últimos publicados e a prova. Mais `relatorios.json` e
  os terminais `outputs/bot.txt`, `postar.txt`, `historias/…/auto_saida.txt`.
- **Processos vivos** por `Get-CimInstance`; **tarefas** por `Get-ScheduledTask`
  (só confere se ainda abrem console — nada aqui muda tarefa).
- **Previsão** do próximo horário em **subprocesso**:
  `python -m painel.flutuante.previsao --raiz …`.

**A regra de ouro:** `postar.py --ver` **ESCREVE no `atividade.jsonl`** (roda a
vistoria da parte escolhida e grava uma linha por chamada). A janela perguntando
de tempos em tempos encheria o diário de vistorias que ninguém pediu. A previsão
chama só as funções de **fila** — `fila_de_historias()`, `proximo_build()`,
`estoque()` — e por isso a tela diz "**provável**": a vistoria na hora do post
pode pular a primeira.

O **único** arquivo que a janela escreve é `flutuante.json` (tamanho, posição,
aba, arte, enfeites e a caixa-preta da §2) — estado dela, não do sistema. Com
`--prova`, nem isso.

## 4. As regras de interface que valem como lei

1. **A tela é 1366×768.** Nada de tamanho fixo: geometria adaptativa, rolagem
   por página, barra lateral que vira ícone abaixo de 1000 px. O `pack` do Tk
   **corta em silêncio** — sem rolagem, "não cabe" e "não existe" ficam iguais.
2. **Duas caras** (`painel/estilo.py`): Vila quente (`#171310`, acento âmbar, o
   mundo é protagonista); janelas de trabalho sóbrias e densas (`#121016`, roxo).
   Cada uma é um processo, nunca aparecem juntas.
3. **O acento é só do que é clicável ou está ativo.** Título de cartão em roxo
   foi tentado e revertido: com três cartões roxos, o item de menu ativo deixa de
   se destacar. Superfície se separa por **borda de 1px**, não por bloco de cor
   mais clara. Escalas fechadas: espaço 4/8/12/16/24/32 e nada entre; texto por
   PAPEL; cor por SIGNIFICADO (`erro`, não `vermelho`).
4. **Console em gaveta.** Ocupava 130 px fixos e quase sempre vazios; numa tela
   de 768 px isso jogava para baixo da dobra o cartão "ONDE POSTAR", a tabela de
   paralelismo e fileiras de botões. Hoje é uma faixa de 32 px que se abre
   sozinha quando um comando começa.
5. **Arte fofa é o padrão** (`flutuante/arte.py`): "não quero isso pixelado".
   Pillow em 4× reduzido com LANCZOS (o Tk não suaviza nada), procedural e
   determinística (`random.Random(semente)`, com teste de bytes iguais). A
   **clássica em pixel** continua no menu do botão direito. **Desde 28/09
   toda função de desenho aceita `escala`** e desenha de verdade nesse tamanho
   (o `Pincel` guarda `k` pixels internos por pixel do mundo: 4 em 1×, 2×escala
   acima disso); as coordenadas continuam em pixels do mundo. Com escala 1 o
   resultado é byte a byte o de antes (medido nos 400 desenhos; só o chão mudou,
   de propósito: as ruas agora pintam todas as bordas antes dos miolos, e sumiu
   o "U" que a borda da calçada riscava por cima da rua em cada encontro).
6. **Personagens com vida** (`flutuante/vida.py`): andam por um grafo de caminhos
   (ninguém atravessa casa), sentam no banco, regam flores, alimentam os patos,
   conversam quando se cruzam, comemoram ao terminar e consolam quem errou;
   publicação solta confete, e a cada 3 publicações do dia vem um enfeite.
7. **O estado real sempre vence a animação.** Serviço trabalhando leva o
   habitante ao prédio com o balão do que está sendo feito, não importa o que ele
   fazia; só quem está de folga passeia. Prédio **nunca some** (fallback em três
   degraus no `mundo.py`) — sumir é o jeito mais silencioso de mentir. E nada se
   perde no meio da graça: placa com a cor do estado, bandeira de conta em uso,
   balão e ❗ no erro.

## 5. As armadilhas medidas

- **`after()` de uma thread quebra o Tkinter** ("main thread is not in main
  loop"). A regra: *quem trabalha publica numa fila; quem desenha lê a fila na
  thread da interface*. No painel só o `Supervisor` (`painel/processos.py`) toca
  em `after` — ele substituiu cinco filas copiadas, duas delas chamando `after`
  de dentro da thread. Na flutuante, só a classe `Janela`.
- **Sondar trava PEGANDO a trava derruba o dono.** `travas.ocupada()` responde
  pegando a trava por um instante; com os trabalhadores usando `trava(nome)` sem
  espera, esse instante faz o dono de verdade ouvir "ocupado" e desistir da
  rodada. `dados.trava_ocupada` só tenta **ler** o byte trancado — no Windows,
  byte trancado por outro processo não lê.
- **`PrintWindow` para fotografar** (`flutuante/captura.py`, com
  `PW_RENDERFULLCONTENT`). **Nunca** `ImageGrab.grab(bbox=…)`: ele fotografa a
  *região da tela*, e com a janela coberta vai para o disco o que estiver na
  frente. Já aconteceu — o que foi salvo foi conversa pessoal do Adrian.
- **Botões sobrepostos.** No `pack`, quem chega antes reserva o espaço: os botões
  da barra de título entram **primeiro** e o texto fica com o que sobra; ao
  contrário, o `✕` cobria o vizinho. Pelo mesmo motivo, a gaveta empacotada
  depois do corpo com `expand=True` não aparecia.
- **Janela que sumia ao minimizar.** Sem barra de tarefas, `iconify`/`withdraw`
  desapareciam com ela para sempre; hoje `−` e `✕` viram o ícone, e há teste que
  proíbe essas chamadas.
- **WM_CLOSE matava a Vila calada** (medido em 28/09). Janela Tk sem borda,
  sem `protocol("WM_DELETE_WINDOW")`: o WM_CLOSE e o SC_CLOSE do sistema caem
  no padrão do Tk, que **destrói a raiz** — o processo acaba sem passar pelo
  `sair()` e sem deixar rastro. Agora o protocolo manda para o ícone
  (`Janela.pedido_de_fechar`), e o teste posta WM_CLOSE e SC_CLOSE de verdade
  na janela. Cuidado ao medir isso: tecla postada com `PostMessage`
  (WM_SYSKEYDOWN + F4) **não** fecha nem janela Tk com borda, então ela não
  serve para simular Alt+F4.
- **O app do celular passava por bot** (achado na prova de tela de 28/09: a
  Vila listava dois "Bot do Telegram"). `-m\s+remoto\b` casa com
  `-m remoto.api_http`, porque o ponto é fronteira de palavra — e o coletor
  dava o **bot como vivo** só porque o app estava no ar. Hoje o app é
  "📱 App do celular" e o bot só casa com `-m remoto` seguido de espaço ou
  fim.

## 6. Estado de hoje e pendências

No ar: a flutuante mergeada (`ee31d13`), a tarefa de 10 min com resultado `0`,
uma instância só, arte fofa como padrão.

**Por que a Vila reiniciou em 27/09 — investigado em 28/09, causa NÃO
determinada.** Foram três mortes sem ninguém matar de propósito: antes das
18:50 (o Adrian viu sumir), a 17020 (entre 18:55 e 19:14) e a 18316 (entre
19:44 e 20:54), mais uma derrubada de propósito às 18:54 para testar a
tarefa. Descartado, medindo:

- **crash nativo**: o Windows registra crash de `pythonw.exe` nesta máquina
  (há eventos 1001 de 31/08) e não há nenhum em 27/09; nem travamento (1002)
  nem memória baixa (2004);
- **alguém matando**: nenhum comando de matar processo nas transcrições das
  sessões nessas janelas (as cinco pastas de projeto varridas);
- **os testes do painel**: a Vila 7720 sobreviveu a cinco rodadas do
  `testar.py` (que inclui os testes da flutuante) na madrugada seguinte;
- **a tarefa**: não foi alterada desde 18:54:27;
- **`taskkill /T` pegando órfão por PID reciclado** (o Claude Code encerra
  árvores com `taskkill /PID … /T /F`, e o pai registrado da Vila atual é o
  PID 17020, reciclado da Vila morta): testado com 3.705 processos
  suspensos até reciclar o PID — o `taskkill /T` **poupou** o órfão.

O que sobra, e que só a caixa-preta vai separar da próxima vez: um pedido de
fechar do sistema (agora vira ícone), o **Fechar de verdade** do menu, ou
morte de fora sem rastro. As duas quedas coincidiram com uma sessão do
Claude Code encerrando processos (a `TaskStop` das 19:04:39 e o fim do
`claude -p` do apurador às 20:52:37), mas o mecanismo não apareceu.

- **O `.cmd` e a tarefa agora têm instalador** (§2). Entre o commit `a101a2e`
  (27/09) e 28/09 o `vila_flutuante.cmd` esteve no git com os caminhos desta
  máquina escritos à mão; hoje ele é gerado e ignorado. **A tarefa não acorda
  mais o PC** (decisão do Adrian em 28/09, `tarefa-da-vila-acorda-o-pc` =
  "tirar"): o `endurecer` liga o `WakeToRun` em todas as tarefas, e o
  instalador o desliga **depois** dele (`sem_acordar`; na ordem inversa ele
  religaria). `--ajustar` reaplica os ajustes na tarefa que já existe sem
  recriá-la — foi assim que a tarefa no ar mudou em 28/09 (`WakeToRun=False`,
  o resto igual, a Vila 11728 intocada). O modo a seco mostra `acorda_o_pc`.
  A Vila segue herdando a prioridade 7 da tarefa (roda em `BelowNormal`).
- **`vila/` continua em uso pelo painel**, mesmo com a Vila antiga fora do app do
  celular: a página `paginas/vila.py` (mapa grande em pixel, de
  `vila/config.json`), o fallback da flutuante quando a arte clássica está
  escolhida (`mundo.py` → `vila.gerar_base.predio_procedural`, `vila.motor`) e a
  **Oficina** (`vila/editor.py`, pela página ou `python -m vila.editor`). O app
  do celular não usa mais nada da `vila/`: o `_motor()` morto de
  `remoto/vila_dados.py` saiu em 28/09. Ainda sobra lá a constante `ESCALA = 2`,
  que ninguém lê — o arquivo é do app, então fica para a sessão dele.
- A **Oficina entrou no sistema visual** em 28/09: usa a cara da **VILA** do
  `estilo.py` (o conteúdo dela é pixel art, e o `estilo` explica por que
  essa moldura é quente e o acento é âmbar) pelo kit `painel.widgets`; o
  acento ficou só na célula escolhida, no item selecionado e no único botão
  primário (**Salvar tudo**); título de coluna é discreto. O tamanho sai da
  tela (`editor.geometria`: 1330×680 na dele, com o rodapé acima da barra
  do Windows — antes os 1330×700 fixos o punham embaixo dela), a largura
  mínima é a do conteúdo, e o que cede na altura é a folha, a lista de
  papéis (agora com barra) e o mapa. Se o Adrian preferir a cara sóbria
  (roxa) das janelas de trabalho, é trocar `estilo.VILA` por
  `estilo.OFICINA` numa linha. Continuam **duas artes da mesma Vila** para
  manter (o mapa grande em pixel e a fofa): não é bug, é custo.

## 7. Como conferir sem quebrar nada

- `python -m painel --smoke` monta as três janelas, **uma por processo**, e passa
  por cada página (três Tk no mesmo processo dão "async handler deleted by the
  wrong thread"). Nenhuma suíte pega erro de layout.
- `python -m painel.flutuante --prova saida.png` abre, espera os dados,
  fotografa **só a janela** e sai **sem mudar as preferências**. `--demo` usa
  dados falsos (a barra diz "DEMONSTRAÇÃO"), `--hora HH` finge dia/noite,
  `--gif` grava 5 s, `--medir-cpu SEG` mede a CPU. A `--prova` **não** passa pelo
  mutex: abre uma segunda janela de propósito, e é a forma segura de olhar sem
  mexer na do dono.
- Testes desta parte (199): `painel/test_painel.py` (40),
  `painel/test_flutuante.py` (92, com a caixa-preta e o WM_CLOSE de verdade),
  `painel/test_tarefa_da_vila.py` (12, o instalador e a guarda do `.cmd`
  rodada pelo `cmd`), `painel/test_vila_fofa.py` (32, com a escala e a
  Vila dobrada do celular), `vila/test_motor.py`
  (17) e `vila/test_editor.py` (6: sem cor literal, cabe na tela dele, nada
  espremido nem desmapeado pelo `pack`). Os da `vila/` entram no `testar.py`
  **pelo nome** (`vila/` é pacote de namespace e o `discover` recusa): teste
  novo ali precisa entrar na lista.
- `python -m painel.flutuante.tarefa` (sem bandeira) confere o `.cmd` e a
  tarefa sem escrever nada.

**Não fazer:** matar o `pythonw` do dono (é a Vila na tela dele; a tarefa repõe
em até 10 min, mas ele perde posição e tamanho); tirar a guarda do
`vila_flutuante.cmd` ou encurtar a repetição (o segundo lançamento rouba o foco);
fazer a janela chamar `postar.py --ver`, `travas.ocupada()` ou `panorama.resumo()`
na thread da interface; usar `ImageGrab`; apontar a tarefa direto para o `.cmd`
(volta a janela preta) ou mexer no `oculto.vbs`.

## Contratos com outras partes

**Só LEIO, nunca escrevo:**

| Arquivo | Dono | Eu |
| --- | --- | --- |
| `atividade.jsonl` | `builds.atividade` — toda etapa escreve | leio a cauda |
| `locks/` | `builds.travas` | sondo lendo o byte trancado |
| `publicados.jsonl` (2) | a sessão de publicação | leio |
| `relatorios.json`, `bot.txt`, `postar.txt`, `auto_saida.txt` | quem os gera | leio a cauda |
| tarefas do Agendador | os instaladores de cada parte | `Get-ScheduledTask` |
| `ferramentas/postar.py` | outra sessão | subprocesso, só as funções de fila |

**Meus:** `painel/**`, `vila/**`, `vila_flutuante.pyw`, o `vila_flutuante.cmd`
(gerado pelo `flutuante/tarefa.py`), a tarefa `NeuralFights_vila_flutuante`, e
em disco `flutuante.json` + `flutuante.sinal`. `vila/config.json` e
`vila/sprites/` são da **Oficina** — quem edita mapa e papéis é ela, não o código
do painel.

**O que o app do celular consome da Vila** (`remoto/vila_nova.py`, dono é a
sessão do app): `painel.flutuante.arte` (fundo dia/noite e atlas de personagens,
enviados como imagem pronta do PC), `painel.flutuante.vida` (a vida roda **no
servidor**, não no celular), `painel.flutuante.dados` / `Caminhos` e
`cena.e_noite`. O celular só interpola entre dois retratos. **Consequência:
mexer em `arte.py`, `vida.py` ou `dados.py` muda o app também** — são a mesma
Vila, e foi essa a decisão (um segundo desenho em JavaScript divergiria na
primeira mudança).

**A Vila em pé do celular** (28/09, `flutuante/retrato.py`, só o app usa). O
mundo é 704×240; no celular em pé, caber pela altura mostrava 2 prédios de 11
(o erro dos outros ficava fora da tela) e a arte de 1× chegava ampliada e
borrada. O retrato é a **mesma** Vila dobrada: a fileira de cima é o mundo de
x=0 a `DOBRA`=420, a de baixo vai de 420 ao fim, completada por um campo de
136 px (grama, árvores, uma placa onde a rua acaba); uma sebe entre as duas,
céu com morros (nuvens de dia; estrelas e lua de noite) em cima e grama
embaixo. A dobra em 420 é a única faixa em que nada fica cortado nas duas
ruas (há teste). A vida continua em coordenadas do mundo: o app só converte
com `para_retrato`/`para_mundo` (a mesma conta em `vila.js`). Vai em escala 3
(WebP: 126 KB de dia, 95 KB de noite) e o atlas também (PNG de 673 KB,
baixado uma vez por versão), com os patos do lago.
**Como a câmera abre é decisão do Adrian** (`painel-e-vila/vila-zoom-celular`):
o servidor lê o nó; pendente = `perto` (uma fileira enche a altura, na casa,
como era); `longe` = a Vila inteira. Prova de tela: `prova_app.py` no
scratchpad da sessão de 28/09 (Chrome headless, 390×844, instância 8934).
