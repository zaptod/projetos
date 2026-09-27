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
bandeja). Sair de vez: botão direito → **Fechar de verdade**. O mesmo menu troca
tamanho, arte (fofa/clássica), "sempre por cima", prever agora e abrir o painel.

## 2. Como a Vila se mantém no ar

Tarefa **`NeuralFights_vila_flutuante`**, conferida hoje:
`wscript.exe //B //Nologo …\oculto.vbs E:\projetos\vila_flutuante.cmd`,
repetição **PT10M** sem fim, último resultado `0`. O `//B` é o que faz **não
haver janela preta** (mesmo padrão das outras 25 tarefas do projeto).

**A guarda contra roubar foco mora no `.cmd`**: a janela já tem instância única,
mas o segundo lançamento **traz a janela para a frente de propósito** — é o que
faz o atalho funcionar, e repetir isso de 10 em 10 minutos roubaria o foco do
dono o dia inteiro. Então o `.cmd` procura um `pythonw.exe` cuja linha de comando
casa com `painel.flutuante|vila_flutuante` e **só lança se não houver nenhum**.

Não duplicar instância: mutex nomeado `Local\NeuralFights_VilaFlutuante`
(`flutuante/__main__.py`) e, em vez de sair calado, o segundo processo **pede
para a viva aparecer** — `flutuante/sinal.py` escuta em 127.0.0.1 numa porta
escolhida pelo sistema e grava porta + segredo em `flutuante.sinal` (sem isso,
janela sumida não voltava nunca mais: bug de 17/09).

Agora há **um** processo: PID 18316, `pythonw -m painel.flutuante --medio`, e o
`flutuante.json` diz `modo: "icone"` — o dono recolheu para o ícone.

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
aba, arte, enfeites) — estado dela, não do sistema. Com `--prova`, nem isso.

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

## 6. Estado de hoje e pendências

No ar: a flutuante mergeada (`ee31d13`), a tarefa de 10 min com resultado `0`,
uma instância só, arte fofa como padrão.

- **`vila_flutuante.cmd` NÃO está no git** (`??` no `git status`) — e é o arquivo
  que a tarefa chama. Máquina refeita a partir do repositório não sobe a Vila.
  **Nenhum código instala a tarefa** tampouco: ela foi feita à mão, e `postar.py
  --instalar`, `remoto --instalar` e `main.py auto --instalar` não a conhecem.
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
- Testes desta parte (168, não rodados agora): `painel/test_painel.py` (40),
  `painel/test_flutuante.py` (83), `painel/test_vila_fofa.py` (28),
  `vila/test_motor.py` (17).

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

**Meus:** `painel/**`, `vila/**`, `vila_flutuante.pyw`, `vila_flutuante.cmd`, e
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
