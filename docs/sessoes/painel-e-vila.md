# Painel e Vila

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/painel-e-vila/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (29/09/2026) · “29/09 21:39, pela Mesa de comando: paralelo, até 2 agentes” `modo-de-trabalho`
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
- ⏳ **Lote: piso de reposição (qui–dom)** — Abaixo de quantos dias de estoque a máquina volta a criar fora do lote? `lote-piso-de-reposicao`
- ⏳ **Lote: como trocar da madrugada para o dia** — Quando desligar as tarefas da madrugada? `lote-transicao`

**Painel e Vila**
- ✅ **Tarefa da Vila acorda o PC** — Tirar o acordar da tarefa da Vila (recomendado) (28/09/2026) `tarefa-da-vila-acorda-o-pc`
- ✅ **Cara da Oficina** — Quente, igual à Vila (como está) (28/09/2026) · “Eu descartei essa vila” `cara-da-oficina`
- ✅ **Zoom da Vila no celular** — Perto e grande (como está) (28/09/2026) · “Também adicionei suporte se eu deitar o celular, pode mudar as casas de lugar se for mais fácil, não ligo” `vila-zoom-celular`
- ✅ **Aposentar a Vila em pixel e a Oficina** — Aposentar (tirar do painel e do código) (28/09/2026) `aposentar-vila-pixel`
- ✅ **Ao girar, a Vila abre no prédio escolhido** — Abrir no prédio escolhido (como está agora) (29/09/2026) `girar-foca-o-predio`
- ✅ **O prédio do Grok na Vila** — Manter (como está) (29/09/2026) `predio-do-grok`

<!-- decisoes:fim -->

Documento de passagem. Tudo abaixo foi conferido no código e na máquina em 27/09/2026.

## 1. Painel, flutuante, e como abrir

| Peça | O que é | Como abrir |
| --- | --- | --- |
| **Painel** | quatro janelas grandes, cada uma um processo (`painel/app.py` + `painel/paginas/`) | `painel.bat` → `ferramentas/abrir.py painel`; ou `python -m painel` |
| **Oficina de sprites** | a quarta janela: folha de sprites do ChatGPT → peça do palco (`painel/paginas/oficina.py` + `painel/sprites/`) | botão **🎨 Oficina de sprites** na Vila; `ferramentas/abrir.py oficina`; `python -m painel --janela oficina` |
| **Vila flutuante** | uma janela pequena, **sem borda do Windows**, sempre por cima, no lugar dos consoles pretos (`painel/flutuante/`) | dois cliques em `vila_flutuante.pyw`; `python -m painel.flutuante`; ou o botão **🪟 Vila flutuante** na página Vila |
| **Guia das IAs** (29/09) | a janela onde o Adrian **cola o HTML/seletor/texto** de cada coisa que mostra na sessão guiada da Vila das IAs (`painel/flutuante/guia/`), sem borda, por cima, canto direito | `python -m painel.flutuante.guia`; o botão **◈** na barra da Vila flutuante ou o menu dela (botão direito → "Abrir o guia das IAs") |

As quatro janelas (`painel/janelas.py`, `JANELAS`): **🏘 Vila** — o hub, uma
página só (placar, as outras janelas, paralelismo e o diário com filtro por
fábrica; o mapa em pixel saiu em 28/09, ver §6); **🎬 Criação de vídeos** —
auditoria, confiabilidade, fluxo, publicar, experimentos, vídeos, histórias,
espelho, contas, reações (a única com `pipeline: True`, a faixa do freio de
mão); **🎮 Jogo** — torneio, simulação, database, live, áudio; **🎨 Oficina de
sprites** (28/09) — uma página, cara quente (`cara-da-oficina` = "quente";
trocar é a linha `"tema"` dela em `JANELAS`).

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
direito → **Fechar de verdade**. O mesmo menu troca tamanho, "sempre por
cima", prever agora e abrir o painel (a troca de arte saiu com a clássica,
em 28/09; `"arte": "classico"` guardado volta para a fofa).

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
   determinística (`random.Random(semente)`, com teste de bytes iguais). É a
   **única** desde 28/09: a clássica em pixel (`mundo.py`) foi aposentada
   por decisão do Adrian (`aposentar-vila-pixel`). **Desde 28/09
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
   fazia; só quem está de folga passeia. Prédio **nunca some** (todo prédio de
   `dados.PREDIOS` tem lote em `arte.LOTES`, com teste) — sumir é o jeito mais
   silencioso de mentir. E nada se
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
- **A Vila em pixel foi aposentada (28/09)**, por decisão do Adrian
  (`aposentar-vila-pixel` = "aposentar", depois de "Eu descartei essa vila"
  na `cara-da-oficina`). Saíram, com o histórico no git (commit desta
  mudança): a pasta `vila/` inteira (motor, `gerar_base`, a Oficina antiga
  `editor.py`, `config.json`, `sprites/` e os 23 testes), a arte clássica da
  flutuante (`flutuante/mundo.py`, o item do menu e o `--arte`) e o mapa em
  pixel da página Vila. Contado antes de apagar: importavam `vila` só
  `paginas/vila.py`, `flutuante/mundo.py`, os próprios testes e o
  `testar.py` (pelo nome); o `abrir.py oficina` chamava `vila.editor`; o app
  do celular não usava mais nada. O que o mapa fazia e ainda serve ficou: o
  filtro do diário virou uma caixa. Não mudou nada em `arte.py`, `vida.py`,
  `dados.py`, `retrato.py` nem no app (provas de tela da flutuante média e
  grande e do app, 28/09). Sobra em `dados.py` o reconhecimento do processo
  `vila.editor` ("Oficina da Vila"), que agora nunca casa — o arquivo é da
  Vila fofa e ficou intocado de propósito.
- **Oficina de sprites (28/09)**, no lugar da antiga. Pedido do Adrian em
  `builds/sprites-animados` = "limpar depois": uma interface que facilite
  limpar, sanear e fatiar as folhas que ele gera no ChatGPT (o `piriri.py`
  dele tirava o fundo com limiar 240 pixel a pixel). As contas moram em
  `painel/sprites/` (sem Tk, numpy + Pillow, sem laço por pixel): `rotulos`
  (componentes conectados por corridas — o scipy não está instalado),
  `limpeza` (fundo por preenchimento das bordas ou cor-chave, com suavidade e
  descontaminação; alfa mínimo; despill que troca a franja pela cor do
  desenho em volta, e não apaga o verde de um ácido verde; linhas de grade
  por "corrida longa que os vizinhos não têm"; ilhas), `fatiar` (linhas
  desenhadas, vãos, colunas×linhas, ou por desenho), `alinhar` (âncora por
  massa/caixa/pé, célula única, margem, largura máx. com LANCZOS),
  `medidas`, `receita` (o estado; desfazer é voltar a receita), `lote` e
  `exportar`. **Medido na 11243** (`fixtures/folha_acida_chatgpt.png`): 26
  quadros pela grade 6×5; linhas de grade 10 → 0; px nas faixas da grade
  52.134 → 0; franja verde forte 192.156 → 0 (nem escondida em pixel
  transparente); pontinhos 4.462 → 0; buracos no desenho 0 (o `piriri.py`
  abre 205); âncoras ±0,5 px; ~0,5 s por folha. **O que a folha tinha de
  verdade:** ela já vem RGBA, e 256 mil pixels têm alfa 1–2 com cor
  (0,255,0) — a "franja" e a grade que se viam eram esse fantasma; por isso
  o limiar de branco não resolvia. **Exporta** no formato que o palco já lê
  (`docs/palco/COMO-EDITAR.md`, seção "Folha de sprite animada", da 16E):
  `efeitos/folhas/<nome>.png` + `.json` (origem, prova, receita, medidas),
  a cena com `folha_animada.gd` em `skills/<skill>`,
  `objetos/<tipo>/<elemento>` ou `eventos/<tipo>[_<tier>]`, e a linha de
  `LICENCAS.md` num bloco próprio (`<!-- oficina:inicio -->`). Sem prova de
  origem recusa; arquivo existente pede confirmação; beam não entra (o palco
  não aceita folha nele). SpriteFrames `.tres` não: o palco não lê. Conferido
  numa CÓPIA do palco com o Godot 4.7 headless: a biblioteca achou a cena
  pelo nome e carregou a folha (1674×610, 6×5, 26 quadros). Soltar arquivo
  na janela: `painel/arrastar.py` (WM_DROPFILES por ctypes; o
  `tkinterdnd2` não está instalado).
- **Prova de tela sem roubar o foco** (`painel/prova.py`, 28/09). Medido: um
  `tk.Tk()` de um processo filho do VS Code vira a janela da frente no
  primeiro `update_idletasks`, mesmo retirada; fora da tela o Tk não pinta
  (foto branca). O que funciona: devolver o foco a quem tinha e mandar a
  janela para o fundo (13 ms); coberta, o `PrintWindow` ainda a fotografa.
  Vale para `python -m painel --prova` e para a `--prova` da flutuante.

## 6c. O prédio do Grok e o balão do correio (29/09/2026)

Vila das IAs, fase 2 (`docs/sessoes/app-e-bot.md` §10): o Adrian conversa
com Grok, Gemini, ChatGPT e DeepSeek pelo app, e a resposta não vista vira
balão em cima do prédio. O Grok não tinha prédio (decisão
`geral/ias-grok-acesso`: grok.com com a conta X dele, perfil
`grok__principal`).

- **Onde ele entrou.** O mundo (704×240) estava cheio: nenhuma vaga de
  72×64 sem mover casa. A única de 72 px era **entre o DeepSeek e o
  ChatGPT**, ocupada por uma árvore com um caminhozinho em x=112 (o ponto
  "arvore" do passeio). O Grok ficou nela, no lote `(5.5, 1)` — meio tile
  para cair no centro: 8 px de cada telhado vizinho. A árvore e o ponto do
  passeio saíram (a árvore ficaria dentro da casa); o caminho da porta
  (x=120) substitui o da árvore. Fica inteiro na fileira 1 do retrato
  (x 84..156 < DOBRA) e na paisagem. Arte: telhado grafite (`#5c667c`),
  emblema **foguetinho** (inspirado, nunca copiado), habitante de boné;
  `dados.PREDIOS["grok"]` = 🚀 "conversa", `_SERVICO_PARA_PREDIO["grok"]`
  (a trava `grok__principal` acende a bandeira dele).
- **Nada fora dele mudou, medido.** Duas armadilhas que mudariam a vila
  inteira: (1) as flores do chão sorteiam a cor **depois** de saber que
  nascem — excluir um lote novo antes da cor embaralharia o sorteio de
  todas; por isso `arte.LOTES_TARDIOS`: a flor sorteia igual e só não é
  pintada; (2) a pele do habitante vinha de `sorted(CORES)` — "grok" no
  meio mudaria a pele de picasso, tiktok e youtube; agora é
  `ORDEM_DAS_PELES`, nome novo no fim. E as árvores ganharam o tom fixo
  por árvore (era `i % 3` numa lista que perdeu o primeiro item). Conferido
  por hash: mundo, retrato e paisagem (1× e 3×, dia e noite) só diferem em
  x 84..156, y 4..83 do mundo, e nenhum habitante antigo mudou de bytes
  (`PredioDoGrok.test_nada_fora_do_grok_mudou` guarda o md5 do mundo com a
  região dele apagada).
- **O balão atrás do placar** (app, `vila.js`). O balão da resposta ficava
  70 px acima da porta; prédio da fileira de cima com a câmera no topo
  (o "perto" em pé, e o deitado, que abre com a fileira encostada no
  placar/cabeçalho), o balão caía atrás do placar. Agora
  `vilaOndeFicaOBalao` (pura, testada no node) mede onde o topo do balão
  cairia na tela: abaixo do fim do placar (`Vila.faixa[0]`), fica em cima
  como antes; senão **desvia para baixo do prédio**, no caminho da porta,
  com o rabo apontando para cima. É desenhado depois dos habitantes: é ele
  a novidade, não quem está parado na porta. Dois vizinhos com resposta
  (o Grok fica a 72 px dos dois) não se cobrem: o segundo sobe (ou desce)
  um degrau. A janela flutuante **não** lê o correio (é só do app), então
  não havia balão para desviar nela; o ❗ e os emotes dela já cabem no
  canvas.
- **Provas (29/09, 09:33):** flutuante média de dia e grande de noite
  (`--prova --demo`, sem tocar na do dono) e o app na **8937** (a 8934
  estava com a prova de outro agente) em 390×844 e 844×390, correio de
  prova em `NF_IAS_PASTA` temporário com uma resposta do Grok e uma do
  DeepSeek não vistas: em pé "perto" no Grok o balão desvia para baixo
  (topo do balão a 355 px, placar até 96); na Vila inteira fica em cima
  (217 ≥ 96); deitado idem (176 ≥ 34 e 76 ≥ 34); o cartão diz "🚀 Grok ·
  conversa · 💬 Conversar"; zero erro de JS. Casca `v16`.

## 6b. O Guia das IAs (29/09/2026)

Pedido do Adrian às 01:55: "cria uma interface gráfica flutuante pra eu
colar os htmls e etc tb". Contexto: a Vila das IAs (plano
`vila-das-ias.md`, fase 1). O agente do guia (`ias/guia.py`, sessão
`historias`) abre o navegador de cada IA **visível** e ele mostra onde
escreve, manda, anexa, troca de modelo; esta janela fica ao lado para ele
colar o HTML do elemento (copiado do DevTools), seletores, textos de
erro/cota e observações. **A interface com o agente é só por arquivo**, em
`random_builds/outputs/_ias/` — nada aqui importa `ias` nem `historias`:

- **leio** `_atual.json` (`{"ia": "grok", "passo": "onde escreve", "desde":
  iso}`, o agente escreve a cada passo); sem ele a janela cai na primeira IA
  e diz "sem _atual.json: o agente ainda não disse qual IA" (caso zero com
  teste); clicar no nome da IA escolhe a mão ou volta a "seguir o agente";
- **escrevo** `<ia>/guia/colado.jsonl`, append de UMA linha por item:
  `{"id", "em", "ia", "papel", "tipo", "conteudo", "previa"}` +
  `"passo"` (do `_atual.json`) + `"seletor_sugerido"` (o seletor **como
  ficou depois de ele editar** — o nome é o que `ias/guia.py` lê) +
  `"cortado": true` quando o conteúdo passou de 100 mil caracteres.
  `papel` ∈ {campo_texto, enviar, resposta, seletor_modelo, anexo,
  gerar_imagem, erro_cota, observacao} (os oito botões) e os marcadores
  `proximo` (o agente avança o passo) e `mensagem` (texto curto ao agente);
  `tipo` ∈ {html, seletor, texto}.
- **apagar é lápide, o arquivo nunca encolhe**: `{"papel": "apagado",
  "alvo": id}`. O agente lê por **contagem de linhas** (`ler_colado`);
  reescrever o arquivo com uma linha a menos faria o item seguinte cair num
  índice que ele já passou, e ele nunca o veria. `ler_itens` esconde alvo e
  lápide; o ✕ pede dois cliques.

**O que ela faz com o que foi colado** (`guia/colado.py`, sem Tk, com
teste): detecta o tipo (HTML se começa com `<`; seletor se tem cara de
CSS/XPath — uma frase com aspas e "erro:" é texto); a prévia é uma linha
(tag, `#id`, role, aria, testid, placeholder, «texto visível», "+N dentro");
e o **seletor robusto** vem por `data-testid` > id estável > `aria-label` >
role+placeholder/name > placeholder/name > `type=submit`/contenteditable >
texto visível (`button:has-text('…')`, o botão antes do div que o embrulha)
> role só > tag só. **Nunca por classe** e nunca por id gerado
(`parece_gerado`: hash hex, número comprido, `:r5:` do React/radix,
prefixos `css-`/`sc-`/`headlessui-`, bloco de 5+ com letras e dígitos
misturados, bloco sem vogal). Sem âncora, devolve só a tag com "edite antes
de gravar". Ele edita o seletor na caixa antes de gravar; uma colada nova
não apaga o que ele editou. Ctrl+V em qualquer lugar da janela **troca** o
conteúdo da caixa (um item por colada); nas duas entradas de texto a colagem
é a normal.

**Janela** (`guia/janela.py`): tema da Vila, 400×660 por padrão (cabe em
1366×768 com a lista ainda com espaço; teste mede todo botão dentro),
canto direito, arrastável pela barra, redimensionável pelo ◢, `−` recolhe
para uma faixa de 34 px com a IA e o passo (nunca `iconify`/`withdraw`,
teste), `✕` **fecha de verdade** — diferente da Vila, não há alerta que
fechar esconderia, e o ◈ da Vila reabre. Instância única por mutex
`Local\NeuralFights_GuiaIAs` + `guia.sinal` (o segundo lançamento traz a
viva). **Abrir não rouba o foco do navegador**: se a janela nova virou a da
frente no primeiro desenho, `devolver_foco` devolve a quem tinha (mesma
medição de `painel/prova.py`). Só a `JanelaGuia` chama `after`; a escuta
do sinal publica numa fila. Lê `_atual.json` e o jsonl por mtime a cada
1,5 s, na thread do Tk (arquivos de bytes).

**Prova:** `python -m painel.flutuante.guia --prova f.png --demo --colar
demo` (itens de demonstração em memória, o textarea do Grok na caixa; nada
vai para o disco nem para as preferências). Testes: `painel/test_guia.py`
(41). Preferências em `guia.json` no runtime (posição, tamanho, por cima,
recolhida, IA escolhida a mão).

## 7. Como conferir sem quebrar nada

- `python -m painel --janela oficina --arquivo F.png --prova saida.png`
  fotografa uma janela no tamanho da tela dele (`--tamanho`, padrão
  1366x705), sem roubar o foco; `--vista folha` mostra a folha final.
  `python -m painel.sprites medir F.png` imprime as medidas sem janela.
- `python -m painel --smoke` monta as quatro janelas, **uma por processo**, e passa
  por cada página (três Tk no mesmo processo dão "async handler deleted by the
  wrong thread"). Nenhuma suíte pega erro de layout.
- `python -m painel.flutuante --prova saida.png` abre, espera os dados,
  fotografa **só a janela** e sai **sem mudar as preferências**. `--demo` usa
  dados falsos (a barra diz "DEMONSTRAÇÃO"), `--hora HH` finge dia/noite,
  `--gif` grava 5 s, `--medir-cpu SEG` mede a CPU. A `--prova` **não** passa pelo
  mutex: abre uma segunda janela de propósito, e é a forma segura de olhar sem
  mexer na do dono.
- Testes desta parte (272, todos pelo `discover` do painel):
  `painel/test_painel.py` (40), `painel/test_flutuante.py` (88, com a
  caixa-preta e o WM_CLOSE de verdade), `painel/test_tarefa_da_vila.py` (19,
  o instalador, a guarda do `.cmd` rodada pelo `cmd` e o "não acorda o PC"),
  `painel/test_vila_fofa.py` (40, com a escala, a Vila dobrada e a deitada
  do celular, o prédio do Grok nos dois arranjos com a vila intocada fora
  dele, e o balão do correio do app rodado no node: desvio e caso zero),
  `painel/test_oficina_sprites.py` (40: a 11243 medida, o `piriri.py`
  medido do mesmo jeito, fundo branco que não fura o brilho, tela verde,
  exportação no formato do palco, soltar arquivo, a página cabendo em
  1366×768), `painel/test_guia.py` (41, o guia das IAs: detector, prévia,
  seletor robusto, jsonl com lápide, caso zero e a janela cabendo) e
  `painel/test_confiabilidade_grade.py` (4). As fixtures são
  cópias das folhas do Adrian em `painel/sprites/fixtures/` (os originais
  da raiz são dele).
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

**Meus:** `painel/**`, `vila_flutuante.pyw`, o `vila_flutuante.cmd`
(gerado pelo `flutuante/tarefa.py`), a tarefa `NeuralFights_vila_flutuante`, e
em disco `flutuante.json` + `flutuante.sinal`; do guia (§6b), `guia.json` +
`guia.sinal` no runtime e `random_builds/outputs/_ias/<ia>/guia/colado.jsonl`
(append; o agente do guia, `ias/guia.py`, só lê). O `_atual.json` da mesma
pasta é dele: eu só leio.

**A Oficina de sprites escreve no palco** (dono: a sessão do palco), e só
quando o Adrian aperta **Exportar**: `palco/biblioteca/efeitos/folhas/`, a
cena em `efeitos/skills|objetos|eventos/` e o bloco `oficina` do
`LICENCAS.md`. O formato é o da `folha_animada.gd` e da seção "Folha de
sprite animada" de `docs/palco/COMO-EDITAR.md`: se ele mudar lá, o
`painel/sprites/exportar.py` muda junto (o teste confere os campos do
script).

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
(12 desde o Grok, §6c)
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

**A Vila deitada do celular** (28/09, `flutuante/paisagem.py`, só o app
usa). Na decisão `vila-zoom-celular` ("perto e grande") o Adrian comentou
"também adicionei suporte se eu deitar o celular, pode mudar as casas de
lugar se for mais fácil". Deitado não precisou mudar casa nenhuma: a tela é
larga como o mundo, então o arranjo deitado é o **mundo inteiro numa fileira**
(704×490 com o céu de morros em cima e o pé de grama embaixo; o céu é o
mesmo `retrato.desenhar_ceu`, que ganhou `largura`, nuvens e morros por
parâmetro — com os padrões o retrato saiu **byte a byte igual**, medido nos
quatro desenhos de 1× e 3×). Vai em 3× como WebP (`/vilanova-paisagem.webp`:
117 KB de dia, 92 KB de noite), com o mesmo atlas. O servidor manda as duas
geometrias com a lista `fileiras` ([x0 do mundo, y na imagem]); o `vila.js`
converte toque, sprite e câmera só por ela, nos dois arranjos. **Quem
decide o arranjo** é `matchMedia("(orientation: landscape)")`, que também
põe a classe `deitado` no body: a tela e a conta nunca discordam. Deitado,
a prateleira vira **coluna à direita** (7 objetos de ~55 px, a lupa numa aba
na borda de dentro), o placar **sobe para o cabeçalho** em plaquinhas de uma
linha (o nó é movido para dentro do `header`; abaixo de 780 px fica só
símbolo e número), e a Vila fica com a altura toda menos o cabeçalho
(a 844×390: faixa de 42 a 390, "perto" em 1,45×, a Vila inteira em 1,09× —
os 11 prédios de uma vez, 12 com o Grok). O cartão do escolhido vai embaixo, do lado
oposto ao prédio. **Girar** não recarrega: troca o arranjo e a arte (cada
fundo é baixado uma vez), o escolhido continua marcado e a câmera abre
"perto" **nele** (sem escolhido, na casa); objeto aberto continua aberto.
Resize que não troca o arranjo (a barra do navegador) não reabre mais a
câmera. Os objetos deitados usam até 760 px de largura e respeitam o
entalhe (`safe-area`). Prova de tela: `deitado/prova_deitado.py` no
scratchpad da sessão (844×390 e 390×844, girando nos dois sentidos com um
prédio escolhido e com o Grimório aberto, os 7 objetos deitados até o fim
da rolagem, abrir já deitado; dia e noite; zero erro de JS).
