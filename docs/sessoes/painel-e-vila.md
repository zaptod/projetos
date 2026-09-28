# Painel e Vila

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
`builds.tarefas_windows.endurecer`; `--lancador` só reescreve o `.cmd`;
`--desinstalar` remove a tarefa. Os caminhos **vêm do ambiente**: o
`pythonw.exe` ao lado do Python que roda o instalador e a raiz dos dados
(`caminhos.raiz_dos_dados`). Por isso o `vila_flutuante.cmd` é **gerado e fica
fora do git**, como o `bot.cmd` e o `postar.cmd`: numa máquina nova, clone +
`--instalar`. Sem o `oculto.vbs` (pacote `builds`) o instalador **recusa**, em
vez de apontar a tarefa direto para o `.cmd`. A tarefa que está no ar foi
criada à mão em 27/09 com os mesmos parâmetros e não foi recriada. O `.cmd`
que está no disco continua o feito à mão até alguém rodar `--lancador`: a
diferença são os comentários e a guarda "na dúvida não abre" (o modo a seco
mostra o diff).

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
  último `visto` (a hora da queda, com 5 min de folga), a hora em que a
  seguinte `notada` e `windows_reiniciou` quando o Windows ligou depois do
  último sinal. Queda nativa (crash) também deixa evento no Visualizador de
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
   **clássica em pixel** continua no menu do botão direito.
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
  máquina escritos à mão; hoje ele é gerado e ignorado. **Decisão pendente do
  Adrian:** a tarefa acorda o PC a cada 10 min (`WakeToRun`, ligado pelo
  `endurecer` como em todas) e a Vila herda a prioridade 7 da tarefa (roda em
  `BelowNormal`). Para uma janela, acordar a máquina não serve para nada, mas a
  tarefa do bot, também de 10 em 10, já faz o mesmo.
- **`vila/` continua em uso pelo painel**, mesmo com a Vila antiga fora do app do
  celular: a página `paginas/vila.py` (mapa grande em pixel, de
  `vila/config.json`), o fallback da flutuante quando a arte clássica está
  escolhida (`mundo.py` → `vila.gerar_base.predio_procedural`, `vila.motor`) e a
  **Oficina** (`vila/editor.py`, pela página ou `python -m vila.editor`). Sobra
  do app: `remoto/vila_dados.py` define `_motor()` e **ninguém o chama**.
- A **Oficina não usa o `estilo.py`**: tem cores literais próprias, é a última
  tela fora do sistema visual. E são **duas artes da mesma Vila** para manter (o
  mapa grande em pixel e a fofa): não é bug, é custo.

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
- Testes desta parte (189): `painel/test_painel.py` (40),
  `painel/test_flutuante.py` (92, com a caixa-preta e o WM_CLOSE de verdade),
  `painel/test_tarefa_da_vila.py` (12, o instalador e a guarda do `.cmd`
  rodada pelo `cmd`), `painel/test_vila_fofa.py` (28), `vila/test_motor.py`
  (17).
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
