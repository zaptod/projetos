# Auditoria profunda — postar.py (a rodada de publicação) — 11/10/2026

Só leitura: nenhum código do projeto foi mudado, nada publicado, nenhum
navegador aberto, nenhum estado real tocado. As provas rodaram em
`E:\tmp_pytest\aud_postar\` com `NEURAL_FIGHTS_RUNTIME_DIR` apontando para lá,
dublando apenas ENTRADAS e EFEITOS (ledger temporário, catálogo, trava de
render, envio ao Telegram); a função sob suspeita rodou de verdade em todas.

## Examinado

- `ferramentas/postar.py` — 5.608 linhas, 172 funções e 3 classes lidas uma a
  uma (grade, fila de histórias e de builds, válvula de qualidade, dívida do
  YouTube, reposição por rede e volta final, recuperação do TikTok e do YouTube,
  reserva, pausa, trava da rodada com ficha da dona/pulso/em voo, instalação das
  tarefas, aviso do Telegram, lote semanal). Para cada chamada a módulo vizinho
  conferi, por `inspect.signature`, que a função existe e aceita os argumentos
  usados (66 funções/constantes em 22 módulos: `metricas`, `desfecho`,
  `recuperar`, `tiktok`, `youtube`, `youtube_web`, `audio`, `titulos`,
  `catalogo` (os dois), `conferencia`, `atividade`, `contas`,
  `tarefas_windows`, `noite`, `travas`, `serie`, `parecer`, `qualidade`,
  `tipos`, `reparo`, `agenda`, `roteiro`) — nenhuma divergência.
- Medido nos ledgers reais (só leitura): histórias 547 linhas, builds 489;
  `quando` sempre 19 caracteres; `parte` sempre `int` (histórias) ou `None`
  (builds); ZERO linhas com `publicado: false`; builds só no TikTok: 2, ambos
  de 27–28/08 (conciliados, `ja_estava_no_tiktok`); histórias só no TikTok: 1
  (h16 p01, anterior ao corte, decisão `h16-p01-so-no-tiktok`). Desde 06/10
  nenhuma rodada teve a última linha do ledger mais de 35 min depois do
  horário; os 6 horários sem linha nenhuma (09/10, 09:37–21:37) são a queda de
  DNS já conhecida.
- Diário (`atividade.jsonl`, 8.896 linhas): zero eventos `publicar.rodada` ou
  `publicar.guarda`; o log `outputs/postar.txt` (35.610 linhas) não tem nenhuma
  ocorrência de "segura a publicacao", "matei" ou "parou na etapa" — a trava da
  rodada nunca entrou em ação entre dois disparos do Agendador (ver o item 1).

## Confirmados (do mais grave ao menos)

### 1. A trava da rodada, a morte da dona pendurada e o "em voo" nunca funcionam entre duas tarefas do Agendador — gravidade: alta
- Onde: `ferramentas/postar.py:3726-3738` (`escrever_lancador`, o `postar.cmd`
  gravado com `>> "E:\projetos\outputs\postar.txt" 2>&1`), `5288-5302`
  (`main`, que só pega `_trava_da_rodada` DEPOIS de o python existir) e todo o
  bloco `4505-5260`.
- O defeito: as 10 tarefas `NeuralFights_postar_HH` rodam o MESMO
  `E:\projetos\postar.cmd` (conferido no Agendador), e o `>>` do cmd abre o
  arquivo de saída negando escrita a outro processo. Enquanto uma rodada está
  viva, o cmd do horário seguinte morre em "O arquivo já está sendo usado por
  outro processo" ANTES de o python começar — e sai com código 0. Nada do que
  foi desenhado para esse caso (esperar 15 min, matar a dona pendurada de 70
  min com pulso parado, pousar o vídeo em voo na lista "a conferir", avisar no
  Telegram "quem segura", sair 1) chega a rodar; e o Agendador registra sucesso.
  A memória de 14/09 (`agendador-arquivo-trancado`) já tinha medido isso nas
  tarefas das histórias e anotava "postar.cmd ainda usa `>>`, mas não se
  sobrepõem hoje" — desde 06/10 a sobreposição é o caso previsto (reposição
  até 25 min, volta final até 40, espera da trava de 15), e a própria
  `publicacao.md` diz "quem impede duas rodadas juntas é a trava".
- Quando acontece: uma rodada passa do horário seguinte (rede ruim, Studio
  lento, Chrome preso) → o horário seguinte some em silêncio, com código 0 no
  Agendador, sem linha de log, sem Telegram. Pior: uma dona PENDURADA (o caso
  para o qual `_pode_matar` existe) segura o `postar.txt` e cada horário
  seguinte morre do mesmo jeito até ela cair sozinha — ninguém a mata, e o
  limite de 2 h da tarefa só encerra o `wscript`. Só os caminhos do app
  (`--tudo`, `--recuperar`, lançados sem `>>`) chegam a disputar a trava.
  Ainda não aconteceu de verdade: desde 06/10 nenhuma rodada passou de 35 min
  (medido no ledger).
- Prova: dois `.cmd` idênticos ao lançador, em `E:\tmp_pytest\aud_postar\`
  (`a.cmd` dorme 12 s com `>> saida.txt`; `b.cmd` escreve um marcador
  `b_rodou.txt` e usa o mesmo `>> saida.txt`), lançados por
  `Start-Process cmd /c` com 3 s de intervalo: o B termina com
  `ExitCode 0`, `b_rodou.txt existe: False`, stderr do cmd "O arquivo já está
  sendo usado por outro processo", `saida.txt` só com "A comecou / A
  terminou". Controle: B sozinho → `b_rodou.txt existe: True`.
  `Get-ScheduledTaskInfo` das 10 tarefas: todas `LastTaskResult 0x0`.
- Conserto sugerido: o lançador não redireciona pelo cmd — o python abre o
  log (`--saida`, como o `main.py auto` das histórias desde 14/09) e o cmd vai
  para `> NUL 2>&1`; e um teste de contrato lendo `escrever_lancador()` que
  recuse `>>`.

### 2. O "último recurso fora de ordem" publica parte de uma série que está sendo renderizada — gravidade: média
- Onde: `ferramentas/postar.py:980-990` (`proxima_historia`, laço `adiadas`),
  contra a guarda de `887-894`.
- O defeito: a parte barrada por `travas.ocupada("historias__render__<fonte>")`
  manda a série para `bloqueadas`, e as partes seguintes para `adiadas`. No
  último recurso, `adiadas[:3]` só pergunta `_veto_lembrado` e `_retencao` —
  não pergunta de novo pela trava de render — e vistoria e devolve a parte
  seguinte da MESMA série que o reparo está regravando. O comentário da linha
  887 ("HISTORIA SENDO RENDERIZADA NAO SAI NESTE HORARIO", porque o mp4 pode
  estar sendo escrito) é desfeito pelo caminho de baixo, que ainda por cima
  fura a ordem da série.
- Quando acontece: fila só com partes de uma série em render (p03 barrada pela
  trava, p04 adiada), nenhuma retida/vetada que passe na vistoria → a p04 vai
  ao ar fora de ordem, lida do mp4 enquanto o `Pipeline.render` escreve na
  pasta. Raro (precisa a fila estar seca), mas é exatamente a madrugada de
  reparo com estoque magro.
- Prova: `prova_adiadas_render.py` — `fila_de_historias` devolve p03 e p04 da
  `historia_00050`, `travas.ocupada` responde True só para essa série, veto e
  retenção vazios, vistoria gravando o que foi lida. Saída:
  `escolhida: historia_00050:celular:p04`, `recusados: ['...p03: a historia
  esta sendo renderizada']`, `vistoriou: [('historia_00050', 4)]`.
- Conserto sugerido: no laço de `adiadas`, pular quem tem
  `travas.ocupada(f"historias__render__{alvo.fonte_id}")` (ou guardar as
  fontes em render num conjunto à parte e nunca adiá-las).

### 3. Build que saiu só no TikTok (YouTube caiu por rede, TikTok confirmou) nunca chega ao YouTube — gravidade: média
- Onde: `ferramentas/postar.py:3443-3445` (`_builds_prontos`: "qualquer
  plataforma conta"), `3605` (`postar_build` reposto escolhe `proximo_build()`),
  `3291-3294` (`_juntar_reposicao`: vídeo diferente vira ficha extra).
- O defeito: a dívida do YouTube (decisão `youtube-caiu-depois-do-tiktok`,
  06/10) só existe para histórias (`_divida_do_youtube`). Para builds, quando
  o YouTube cai por rede e o TikTok confirma, a reposição no mesmo horário roda
  `postar_build` de novo: `ja_tk` está marcado, `proximo_build` exclui o build
  A (já tem linha, a do TikTok) e sobe OUTRO build B no YouTube. O A fica
  TikTok-only para sempre: não volta à fila, não é "privado no canal" (a
  recuperação do YouTube só trata privados) e a reserva é só do TikTok.
- Quando acontece: Studio em branco/`infraestrutura:` no YouTube dos builds com
  o TikTok bom — o mesmo quadro que gerou a dívida da h54 p02 em 06/10, só que
  no canal de builds. Ainda não aconteceu desde 10/09 (os 2 builds TikTok-only
  do ledger são de agosto, conciliados).
- Prova: `prova_build_orfao.py` — ledger temporário com a linha TikTok
  publicada do `generation_00101`, catálogo com 00101 e 00102:
  `_builds_prontos()` → `['generation_00102:duelo:celular']` (o 00101 saiu da
  fila do YouTube); ficha de antes com `youtube_falhou` por
  `net::ERR_TIMED_OUT` → `_derrubados_pela_rede` = `['youtube']`;
  `_juntar_reposicao(r, nova)` devolve a ficha de antes intacta e o 00102 como
  extra (`reposto: True`) — o horário fica com A só no TikTok e B só no
  YouTube.
- Conserto sugerido: decisão do Adrian (vale a mesma regra das histórias para
  builds?); se sim, uma `_divida_do_youtube` dos builds antes de
  `proximo_build`, com os mesmos crivos (título no YouTube, "a conferir", teto
  por geração).

### 4. `--tudo` (o "escoar" do app) sobe parte vetada pela IA, retida e com a série em render, sem marca nenhuma e sem `prova`/`youtube_id` no ledger — gravidade: média
- Onde: `ferramentas/postar.py:4445-4502` (`escoar_historias`: fila direto de
  `fila_de_historias()`, linha 4463; upload com `provas=[]`, linha 4474;
  `serie.registrar` sem `prova`/`youtube_id`, 4475-4477); botão em
  `remoto/comandos_app.py:412-416`.
- O defeito: o escoar passa só pelos crivos da fila (publicado, "a conferir",
  teto por fonte, título) e NÃO por `proxima_historia`: nada de vistoria,
  veto de pé, retenção, consertada, trava de render. A parte reprovada pela IA
  vai ao ar e não ganha a marca `[qualidade]` (a válvula de qualidade do plano
  de 27/09 é contornada por um clique); o teto de 2 por série/dia é aplicado
  uma vez, no início, e a fila inteira da mesma série sai em sequência; e a
  linha fica sem `prova`, `prova_ok` e `youtube_id` (o que `publicacao.md` §5
  condena no `main.py publicar`).
- Quando acontece: alguém aperta "escoar" no app (com a pausa das histórias
  ligada o catálogo barra; sem ela, não).
- Prova: `prova_escoar.py` — fila com a p03 da h50, `_veto_lembrado` e
  `_retencao` devolvendo veto, `travas.ocupada` True, vistoria reprovando;
  upload e registro dublados como gravadores. Saída: `subiu ao YouTube:
  ['historia_00050:celular:p03']`, `vistoriou antes? []`, `marcou 'a
  conferir'? []`.
- Conserto sugerido: o escoar consome `proxima_historia()` em laço (uma parte
  por volta, com `_valvula_da_parte`/`_marcar_retido` e `provas` como na
  rodada), ou o botão some do app.

### 5. Fichas de builds "mentem" quando um destino já tinha saído no horário — gravidade: baixa
- Onde: `ferramentas/postar.py:3599-3604` (`postar_build`, caminho `ja_yt`:
  `"feito": True` antes de o TikTok rodar), `3651` (caminho `ja_tk`:
  `ficha["tiktok"] = ""` sem `so_youtube`), `3364-3366` (`_publicou_sem_queda`),
  `4193-4196` (`avisar`), `5601-5603` (código de saída).
- O defeito: (a) com o YouTube já no ar, a ficha nasce `feito: True`; se o
  TikTok falha por motivo que não é rede (perfil ocupado, legenda), a passada
  não publicou nada e mesmo assim sai `[POSTADO]`, código 0, e vale como
  "prova de que a rede voltou" para a volta final das histórias. (b) Com o
  TikTok já no ar (`ja_tk`), a ficha não leva `so_youtube` (as histórias levam,
  linha 1593) e o Telegram diz "TikTok 🚫 não subiu" para um build cujo TikTok
  simplesmente já tinha saído; `_juntar_reposicao` também não reconhece o caso
  (só olha `so_youtube`).
- Quando acontece: toda reposição de builds em que um destino já estava no ar.
- Prova: `_derrubados_pela_rede` da ficha `{"feito": True, "so_tiktok": True,
  "tiktok": "", "tiktok_falha": "PerfilOcupado: ..."}` → `[]`;
  `_publicou_sem_queda` → `True`; código de saída → 0. `prova_aviso_ja_tk.py`
  (só o envio ao Telegram e os contadores dublados) com a ficha que o caminho
  `ja_tk` monta: linha do Telegram `▸ TikTok    🚫 não subiu · conta`.
- Conserto sugerido: `feito` só depois do destino rodar (como em
  `postar_historia`), `so_youtube` também em `postar_build`, e
  `_publicou_sem_queda` exigir que a ficha tenha publicado NESTA passada
  (`url` ou TikTok confirmado sem `so_*`).

## Não confirmados

- `publicou_neste_horario` (994-1052) não filtra por `metricas.publicado`: uma
  linha do horário com `publicado: false` barraria o destino ("já publiquei")
  — ao contrário de `_saidas_hoje` e `_horarios_que_restam`, que filtram.
  Hoje é latente: os ledgers têm zero linhas assim e nenhum publicador grava
  linha não confirmada em tempo real; só a cura (`curar_ledger.py --gravar`,
  244 pendentes) as criaria, e em horários passados. Fica como segundo
  critério de "publicado" a unificar.
- Reposição com o `.bak` da dona morta (4657-4674, 5108-5154): depois de pousar
  o voo da dona anterior, `_gravar_dona` manda a ficha dela (com o voo
  `clicou`) para o `.bak`; se a principal da rodada nova se perder numa queda
  entre os dois `os.replace`, a rodada seguinte decide pelo `.bak` e marca "a
  conferir" o mesmo vídeo de novo (segundo Telegram). Não reproduzi a queda; a
  marca repetida é inócua para a fila.
- `_derrubados_pela_rede` lê `MARCAS_DE_REDE` no `motivo` da ficha, que no
  caso "não há parte publicável" carrega os textos dos `recusados`; se algum
  motivo de vistoria/veto contivesse "timed out"/"infraestrutura", a rodada
  reporia o canal e pularia recuperação e reserva ("o TikTok caiu por rede").
  Varri `contos/publicar/*.py` e os textos de erro da vistoria: nenhuma
  dessas marcas aparece; o `TimeoutExpired` do ffprobe é engolido em `{}`.
  Sem caminho real, não é defeito.
- `escrever_lancador` roda a cada `--instalar` e regrava `postar.cmd`, que
  pode estar em execução (o cmd lê o lote aos pedaços). O conteúdo é idêntico
  byte a byte, então não vi como falhar; é só um risco se o lançador mudar.
