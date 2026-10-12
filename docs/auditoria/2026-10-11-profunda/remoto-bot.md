# Auditoria profunda — Bot do Telegram e avisos (`remoto/`)

Data: 12/10/2026. Só relatório; nenhum código do projeto foi mudado. Todas as
provas rodaram em pastas temporárias no `E:\tmp_pytest\` (ou em `E:\projetos-wt\_pytest_app\`),
com Telegram dublado (`TelegramSemRede`/`TelegramOk`, no molde do `TelegramFalso` de
`test_remoto.py`), `config.ARQUIVO`, `avisos.ARQUIVO/REGISTRO/PENDENTES`,
`tarefas.PASTA` e o diário apontados para lá, e `NF_COORDENADOR_PASTA` isolado. Nada
foi escrito em `%LOCALAPPDATA%\neural-fights` (lido só para contar, ver "Fatos").
Os scripts das provas ficaram no scratchpad da sessão (`prova_bot.py`, `prova_avisos.py`,
`prova_filha.py`, `prova_reinicio.py`); os trechos relevantes estão reproduzidos abaixo.

Já consertados antes e NÃO repetidos aqui: porteiro que anotava "enviado" antes de enviar e
a fila de pendentes (b71f02e); relatório marcado antes de enviar e comando descartado em erro
passageiro (bc41a2a).

## Examinado

Cada arquivo lido inteiro, função por função.

| Arquivo | Funções/métodos | Observação |
| --- | --- | --- |
| `remoto/bot.py` | 20 (`_codigo`, `carimbar`, `_log_com_hora`, `Bot`: `__init__`, `_marca`, `_erros_no_diario`, `_responder`, `_mensagem`, `_parear`, `_alertar`, `_apurar`, `_relatorios`, `avisar_todos`, `_entregar_pendentes`, `uma_volta`, `_ligar_vigia_tailnet`, `_vigiar_tailnet`, `rodar`) | laço, alertas, pendentes |
| `remoto/comandos.py` | 30 (`_catalogo`, `_tabela_videos`, `_rodar`, `ajuda`, `status`, `vila`, `erros`, `videos`, `_listar_videos`, `procurar_video`, `candidatos`, `_nao_achei`, `ver`, `publicar`, `gerar`, `historias`, `metas`, `lote`, `funcionamento`, `confiabilidade`, `auditoria`, `testar_conserto`, `pausar`, `retomar`, `parar`, `falar_ao_coordenador`, `responder`, `novo`, `executar`) | tabela fechada |
| `remoto/avisos.py` | 18 (`_pasta`, `_arquivo`, `_registro`, `_pendentes`, `normalizar`, `_assinatura`, `chave_de`, `_ler`, `_gravar`, `_data`, `liberar`, `confirmar`, `desfazer`, `pendentes`, `guardar_pendentes`, `enfileirar`, `_podar`, `_anotar`, `calados`) | porteiro |
| `remoto/relatorios.py` | 28 (`_conferencia`, `_instante`, `_dia_de_grade`, `_janela_da_grade`, `_horarios_servidos`, `_bateu_o_dia`, `_publicacoes`, `_historias`, `_builds`, `_lote`, `metas`, `_duracoes` (+`_ordem`), `_hora`, `_hora_local`, `_mediana`, `_tempo`, `funcionamento`, `_linhas_dos_calados`, `_linhas_das_credenciais`, `_linhas_do_agendador`, `_estado_caminho`, `enviados`, `marcar`, `devidos`, `_minutos`, `auditoria`, `confiabilidade`, `montar`) | |
| `remoto/config.py` | 8 (`runtime_dir`, `caminho`, `carregar`, `salvar`, `token`, `autorizado`, `autorizar`, `esquecer`) | |
| `remoto/api.py` | 9 (`_e_erro_de_formatacao`, `Telegram`: `__init__`, `_url`, `chamar`, `mensagem`, `arquivo`, `novidades`, `eu`; `_multipart`) | |
| `remoto/vigia_tailnet.py` | 20 (`_pasta_do_tailscale`, `_tailscale_exe`, `_bandeja_exe`, `_explorer_exe`, `_rodar`, `_estado`, `_serve`, `_aponta_para_o_app`, `_funnel_ligado`, `bandeja_aberta`, `sondar`, `abrir_bandeja`, `Vigia`: `__init__`, `talvez`, `uma_olhada`, `_esperar_voltar`, `_texto_sem_resposta`, `_texto_da_falha`, `_mandar`) | só `status --json`, `serve status --json`, `tasklist` (conferido) |
| `remoto/lote.py` | 15 (`_carregar_postar`, `_agenda`, `_geracao`, `_numero`, `_janela`, `_dias_de_lote`, `_situacao`, `_texto_do_canal`, `_quando`, `_calendario` (+`_abre`, `_fecha`), `resumo`, `_escapar`, `linhas`, `texto`) | só lê |
| `remoto/__main__.py` | 7 (`_limpar_consertos_orfaos`, `main`, `ligar`, `_conserto_em_texto`, `_teste_em_texto`, `avisar`) | |
| `remoto/tarefa.py` | 7 (`caminho_do_lancador`, `escrever_lancador`, `_schtasks`, `acao`, `instalar`, `desinstalar`, `instalada`) | |
| `remoto/publicacao_filha.py` | 4 (`criado_em`, `_gravar`, `rodar`, `main`) | |
| `remoto/tarefas.py` | 11 (`pasta_das_tarefas`, `_ler_json`, `iniciar`, `_estado`, `uma`, `listar`, `rodando`, `log`, `limpar_velhas`, `_idade`, `resumo`) | |
| `remoto/arena.py` | 2 (`executar`, `main`) | |
| `remoto/limpar_espelho.py` | 2 (`apagar`, `main`) | |
| `remoto/prova_lutador_montado.py` | 1 (`main`) | utilitário de prova |
| `remoto/conftest.py` | 1 (`_claude_isolado`) | |
| `remoto/__init__.py` | 0 | |

Total: 17 arquivos, 183 funções/métodos. Fora da fatia (já auditados): `api_http`,
`acoes`, `comandos_app`, `vila_nova`, `vila_dados`, `biblioteca`, `painel_dados`,
`delegar`, `orquestrador`, `apurador`, `decisoes`, `claude_estado`, `duble_codex`.

## Fatos a explicar (o que achei)

- **"aviso no Telegram NAO entregue" dezenas de vezes por dia em 11/10.** A frase só existe
  em `ias/carteiro.py:1325/1356` (fora desta fatia) e sai quando `avisar_telegram` devolve
  `False` — que acontece em DOIS casos: `remoto.json` sem `autorizados` ou nenhum `ok` do
  Telegram. Nos logs que existem hoje a linha aparece 3 vezes (02/10, `outputs/carteiro.txt`)
  e nenhuma em 11/10: o `carteiro.txt` não tem linha entre 10/10 01:43 e 11/10 18:16, e
  `outputs/_logs/` não tem cópia rodada. O estado real diz que em 11/10 saíram 62 avisos do
  carteiro, 29 do bot.alerta, 16 do `remoto --avisar` e 7 do bot (`avisos_enviados.jsonl`),
  e `avisos_pendentes.jsonl` **não existe** (nada ficou na fila). Não dá para reproduzir o
  "dezenas" com o que está em disco; o mecanismo que produziria isso está nos itens 1
  (laço quente) e 6 (corrida do porteiro) abaixo.
- **`reiniciar bot` registrou "ja tem um bot no ar; este sai".** Item 5: a trava é pedida
  com `esperar=0.0` e a linha sai sem hora; em 11/10 o coordenador religou o bot 9 vezes e
  duas delas viraram "religou → 12 s → caiu: processo ausente → religou de novo"
  (14:42:12→14:42:33 e 15:17:39→15:17:59), com a linha "ja tem um bot" entre elas no
  `bot.txt`. A assinatura do serviço casa também `remoto --avisar`/`--apurar`.
- **`config.runtime_dir()` ignora `NEURAL_FIGHTS_RUNTIME_DIR`.** Verdade no código, mas a
  suíte inteira do `remoto/` rodada com um `LOCALAPPDATA` falso não deixou nenhum arquivo
  nele (954 passed, pasta vazia): hoje os testes não escrevem no estado real por esse
  caminho. Detalhe e medição em "Não confirmados".
- **`publicacao_filha` sem `filho.json` deixa o em-voo preso.** O lado do `acoes` já foi
  auditado (ca70602). O lado desta fatia é pior (item 2): quando o `filho.json` não dá para
  gravar, a filha escreve `fim.json` na hora com o `main.py publicar` ainda rodando.

## Confirmados (do mais grave ao menos)

### 1. Sem rede o laço do bot gira sem dormir e remonta o relatório vencido a cada volta

- **Onde:** `remoto/bot.py:297-328` (`uma_volta`), `remoto/bot.py:367-375` (`rodar`),
  `remoto/api.py:176-194` (`chamar` devolve `{}` sem levantar), `remoto/bot.py:197-215`
  (`_relatorios`).
- **O defeito:** o único "dormir" do laço é o `timeout=30` do `getUpdates`. Sem rede o
  `urlopen` falha na hora, `chamar` devolve `{}`, `novidades` devolve `[]` e `uma_volta`
  termina sem esperar; `rodar` só dorme 5 s quando há exceção, e nenhuma escapa. Cada volta
  reexecuta `_alertar`, `_relatorios`, `_entregar_pendentes` e a vigia. Com um relatório
  vencido, `relatorios.montar(nome)` roda inteiro em toda volta até a rede voltar
  (o de funcionamento faz ~31 `schtasks /Query` e um OAuth com rede; o de metas recarrega o
  `postar.py` pelo caminho) — e o bot fica ocupado o tempo todo em vez de só esperar.
- **Quando acontece:** toda queda de rede/DNS (09/10: 06:39–22:40), reinício com o
  Tailscale/DNS ainda subindo.
- **Prova:** `prova_bot.py` (provas 1 e 5), Telegram dublado devolvendo `{}`:
  ```
  == 1. sem rede, uma_volta nao dorme (laco quente)
    1000 voltas em 0.36 s (2751 voltas/s); getUpdates chamado 1000 vezes
  == 5. relatorio vencido sem rede: montar() roda de novo a cada volta
    20 voltas sem rede: montar('metas') chamado 20 vezes; enviados marcados: {}
  ```
- **Conserto sugerido:** `api.novidades` devolver `None` quando `chamar` deu `{}` e
  `uma_volta` dormir 5–10 s nesse caso; `_relatorios` só remontar um vencido de novo depois
  de 1 min (ou guardar o texto montado até entregar).

### 2. `publicacao_filha.rodar`: se gravar `filho.json` falha, `fim.json` sai com o filho vivo

- **Onde:** `remoto/publicacao_filha.py:435-448`.
- **O defeito:** o `Popen`, o `_gravar(filho.json)` e o `wait()` estão no mesmo `try`. Se o
  `_gravar` do `filho.json` levanta (disco cheio — o `C:` vive perto de encher —, permissão,
  `.tmp` preso), o `except` engole, o `wait()` nunca roda e `fim.json` é escrito na hora com
  `codigo: None` enquanto o `main.py publicar` continua subindo o vídeo. Quem lê o
  `fim.json` (o servidor, na subida ou no pulso) conclui "terminou com erro" durante a
  publicação: o em-voo fecha errado e o vídeo pode ser reenviado; sem `filho.json`, nem
  `vivo_de_verdade` consegue dizer que a publicação ainda roda (é o "em-voo preso" visto
  pelo outro lado).
- **Quando acontece:** disco cheio ou erro de I/O no instante entre o `Popen` e o
  `filho.json`.
- **Prova:** `prova_filha.py` — o `.tmp` do `filho.json` pré-existe como pasta (o
  `write_text` falha como falharia com disco cheio), o comando dorme 8 s:
  ```
  rodar() voltou em 0.02 s com codigo 1; fim.json = {'codigo': None, 'erro': "PermissionError: ... filho.tmp", 'fim': '2026-10-12T19:05:15'}
  filho.json existe: False
  saida.log depois de 9 s: terminei        <- o filho seguiu rodando depois do fim.json
  ```
- **Conserto sugerido:** gravar `filho.json` fora do `try` do `wait()` (falha nele vira só
  um aviso no `saida.log`) e nunca escrever `fim.json` antes de `filho.wait()` voltar.

### 3. Erro gravado no diário pouco antes de uma religada do bot nunca vira aviso

- **Onde:** `remoto/bot.py:56-64` (`__init__`: `self.avisados = {…}` com tudo o que já
  está no diário) e `remoto/bot.py:119-128` (`_alertar` só compara com esse conjunto em
  memória).
- **O defeito:** a marca-d'água dos erros já avisados vive só na memória do processo. Toda
  subida considera "visto" tudo o que está no diário. O coordenador religa o bot a cada
  código novo (9 religadas em 11/10, 4 em 10/10, pelo `coordenador.txt`), e o bot fica até
  30 s preso no long poll entre duas olhadas no diário: um erro gravado nessa janela, com o
  bot morto antes da volta seguinte, nunca é avisado, nunca vai à fila, nunca aparece em
  `calados` e não dispara a apuração.
- **Quando acontece:** erro de fábrica nos ~30–45 s que antecedem cada religada (código
  novo, entrega aplicada, `reiniciar bot`).
- **Prova:** `prova_reinicio.py` — bot A dá uma volta, o erro entra no diário, bot B sobe
  no lugar (sem outra volta de A) e dá 3 voltas:
  ```
  avisos do bot novo sobre o erro: []
  pendentes: [] calados: []
  ```
- **Conserto sugerido:** guardar em disco (`avisos_estado.json` ou um `bot_visto.json`) o
  `ts` do último erro avisado e, na subida, marcar como visto só o que for anterior a ele.

### 4. `_alertar`: a partir do 6º erro novo numa volta, os demais somem

- **Onde:** `remoto/bot.py:128-130` (`self.avisados = {…recentes}` antes do laço;
  `for evento in reversed(novos[:5])`).
- **O defeito:** o conjunto `avisados` é atualizado com TODOS os recentes antes de enviar,
  mas só os 5 mais novos são enviados. O 6º em diante não é enviado, não é enfileirado, não
  conta como calado e não entra na apuração. Cascata (o caso em que o docstring diz que
  avisar mais importa) é justamente quando passa de 5.
- **Quando acontece:** 6+ erros entre duas voltas (~30 s): rodada caindo em cascata, worker
  reportando várias cenas, reparo em laço.
- **Prova:** `prova_bot.py` (prova 3), 7 erros distintos no diário numa volta:
  ```
  mensagens de erro enviadas: 5
  erros que nunca sairam: [0, 1]
  segunda volta mandou mais 0
  pendentes na fila: 0; calados: []
  ```
- **Conserto sugerido:** enviar os 5 mais novos e enfileirar (ou agrupar num texto só) o
  resto, ou só marcar como avisado o que de fato passou pelo porteiro.

### 5. `ligar()`: trava com `esperar=0.0` e linha sem hora — a religada vira "ja tem um bot"

- **Onde:** `remoto/__main__.py:427-430` (`travas.trava("remoto__bot", esperar=0.0)`,
  `print` sem `carimbar`), e a assinatura do serviço em `coordenador/servicos.json`
  (`-m\s+remoto(?:\s|$)`, fora da fatia).
- **O defeito:** quando o coordenador mata o bot e sobe outro em seguida
  (`reiniciar_servico`: `parar` e `religar` no mesmo pulso), o novo pede a trava de arquivo
  com paciência zero; se o antigo ainda está soltando o handle (o `taskkill /f` é
  assíncrono e a máquina costuma estar carregada), o novo imprime "ja tem um bot no ar; este
  sai sem fazer nada" — sem hora e sem dizer quem segura a trava — e sai. O coordenador
  registra "caiu: processo ausente" (conta nas 5 falhas por hora) e religa de novo. Agrava:
  a assinatura pela qual o coordenador "adota" o bot casa também os processos passageiros
  `python -m remoto --avisar "…"` (chamados por `ferramentas/postar.py:558/4265/4304/4367` e
  `historias/contos/pipeline/agenda.py:627`; 16 avisos assim em 11/10) e `python -m remoto
  --apurar` (filho do próprio bot): um `reiniciar bot` pode matar um `--avisar` e deixar o
  bot de verdade vivo, e o novo sai com a mesma linha.
- **Quando acontece:** toda religada pelo coordenador (código novo, entrega aplicada,
  `reiniciar bot`) e a tarefa `NeuralFights_bot_telegram` de 10 em 10 min (os "dois
  gerentes", decisão pendente `geral/gerente-unico-dos-servicos`). A linha "ja tem um bot"
  aparece 5 vezes no `bot.txt` inteiro (01/10, 02/10, 05/10 e duas em 11/10), sempre
  colada a uma religada.
- **Prova:** `outputs/coordenador.txt` (11/10) e `outputs/bot.txt:505-509`:
  ```
  2026-10-11T14:42:12 bot religou: PID 14420
  2026-10-11T14:42:24 bot caiu: processo ausente
  2026-10-11T14:42:33 bot caiu: processo ausente
  2026-10-11T14:42:33 bot religou: PID 14204
  2026-10-11T15:17:39 bot religou: PID 8576
  2026-10-11T15:17:53 bot caiu: processo ausente
  2026-10-11T15:17:59 bot religou: PID 4852

  505:11/10 14:31:56 [remoto] bot @... no ar.
  506:[remoto] ja tem um bot no ar; este sai sem fazer nada.      <- sem hora
  507:11/10 14:42:38 [remoto] bot @... no ar.
  508:[remoto] ja tem um bot no ar; este sai sem fazer nada.
  509:11/10 15:18:00 [remoto] bot @... no ar.
  ```
  Assinatura (regex do `servicos.json`) contra as linhas de comando reais:
  ```
  True  "C:\Python314\python.exe" -u -X utf8 -m remoto
  True  C:\Python314\python.exe -m remoto --apurar
  True  "C:\Python314\python.exe" -u -X utf8 -m remoto --avisar "postagem das ...
  True  C:\Python314\python.exe -m remoto --testar-conserto 2026
  ```
- **Conserto sugerido:** `esperar=15.0` na trava e `carimbar` na linha (com o motivo); no
  coordenador, assinatura `-m\s+remoto\s*$`.

### 6. `avisos.py`: leitura-modificação-escrita sem trava entre processos perde fichas

- **Onde:** `remoto/avisos.py:119-147` (`liberar`), `150-164` (`confirmar`), `167-182`
  (`desfazer`), `206-212` (`enfileirar`): `_ler()` → muda → `_gravar()` sem trava nenhuma.
- **O defeito:** o mesmo `avisos_estado.json` (75 KB hoje) é reescrito inteiro por quatro
  famílias de processos ao mesmo tempo — o bot, o carteiro, o coordenador e cada
  `remoto --avisar` do `postar.py`/`agenda.py`. Duas escritas cruzadas e a ficha de um deles
  some: o aviso perdido não fica calado (sai de novo na próxima vez), `confirmar` não acha a
  ficha e só anota, `desfazer` não desfaz nada. O mesmo vale para a fila de pendentes
  (`enfileirar` lê e regrava o arquivo inteiro).
- **Quando acontece:** na postagem (o `postar.py` manda `--avisar` enquanto o bot alerta e
  o carteiro anuncia), e em qualquer cascata de erros.
- **Prova:** `prova_avisos.py` (prova 1), dois processos, 150 `liberar()` cada, chaves
  distintas, num arquivo temporário:
  ```
  300 liberar() em 2 processos -> 116 fichas no arquivo (184 perdidas; a perdida nao cala a repeticao)
  ```
- **Conserto sugerido:** envolver `liberar/confirmar/desfazer/enfileirar/guardar_pendentes`
  em `api_http.trava_arquivo(<estado>.lock)` (já existe e é entre processos).

### 7. `avisos.pendentes()`: uma linha inválida apaga a fila inteira

- **Onde:** `remoto/avisos.py:185-191` (o `except ValueError` cobre o arquivo todo) e
  `206-212` (`enfileirar` regrava o que `pendentes()` devolveu).
- **O defeito:** uma linha que não é JSON (processo morto no meio de uma escrita antiga,
  edição à mão) faz `pendentes()` devolver `[]`; o `_entregar_pendentes` acha a fila vazia e
  o próximo `enfileirar` sobrescreve o arquivo só com o item novo — os avisos que esperavam
  a rede somem. (Cada linha também é parseada duas vezes.)
- **Quando acontece:** arquivo com uma linha ruim; raro, mas o efeito é perder toda a fila.
- **Prova:** `prova_avisos.py` (prova 2):
  ```
  pendentes() ve: 0 item(ns)          <- 2 itens bons + 1 linha ruim
  depois de enfileirar 1: arquivo tem 1 linha(s)
  ```
- **Conserto sugerido:** parsear linha a linha e pular a ruim (como `atividade.recentes`).

### 8. `tarefas.iniciar`: filha que não sobe deixa a tarefa "rodando" para sempre

- **Onde:** `remoto/tarefas.py:73-79` (`tarefa.json` gravado ANTES de `acoes._iniciar_filha`)
  e `remoto/tarefas.py:83-97` (`_estado`: sem `pid`, `vivo_de_verdade(None)` é `None`, logo
  "rodando").
- **O defeito:** se o `Popen` da filha levanta (WinError 1450 "recursos insuficientes",
  python ausente, job que não deixa criar processo), a pasta fica com `tarefa.json` sem
  `pid`. `uma()` diz "rodando" para sempre, `rodando(acao)` a lista, `comandos_app` (linha
  313) recusa o mesmo comando com "já está rodando", `resumo()` mostra "1 rodando há N
  dias" e `limpar_velhas` nunca a apaga ("nunca as que rodam").
- **Quando acontece:** falha de criação de processo no servidor do app (máquina sem
  memória/handles, que é o estado em que o `taskkill` demora — item 5).
- **Prova:** `prova_avisos.py` (prova 4), `_iniciar_filha` dublado levantando `OSError`
  (é o colaborador que falha; a função sob suspeita, `iniciar/_estado`, roda de verdade):
  ```
  iniciar levantou (esperado): WinError 1450: recursos insuficientes
  situacao da tarefa: rodando; rodando('gerar_historia'): 1
  limpar_velhas(dias=0) apagou: 0
  ```
- **Conserto sugerido:** no `except` do `_iniciar_filha` apagar a pasta (ou gravar
  `fim.json` com o erro); em `_estado`, ficha sem `pid` e sem `filho.json` é "sumiu".

### 9. `rodar()`: sem rede no `getMe` o bot sai em vez de esperar

- **Onde:** `remoto/bot.py:349-354`.
- **O defeito:** um `getMe` sem resposta (rede/DNS ainda subindo depois do boot, ou caído)
  é tratado como "token errado" e o processo termina. Quem religa é o coordenador, com
  backoff e limite de 5 falhas por hora ("parei de tentar") — e a decisão pendente
  `gerente-unico-dos-servicos` desligaria a tarefa do Agendador que hoje o traria de volta.
  Com o bot fora, nem a fila de pendentes nem a vigia do tailnet rodam quando a rede volta.
- **Quando acontece:** religada (código novo/reboot) durante uma queda de rede; no boot de
  28/09 o Tailscale/rede levou 20 min para ficar de pé.
- **Prova:** `prova_bot.py` (prova 2), `eu()` dublado devolvendo `{}`:
  ```
  rodar() voltou em 0.000 s; log: [remoto] o Telegram não respondeu ao getMe. O token está certo?
  ```
- **Conserto sugerido:** repetir o `getMe` em laço com espera (30 s) até responder, saindo
  só quando a resposta é um 401 de verdade (`error_code` no corpo).

### 10. Vigia do tailnet: "não sei"/"voltou" 12 mensagens num dia, com o app no ar

- **Onde:** `remoto/vigia_tailnet.py:284-288` (aviso de `sem_resposta` após 3 olhadas),
  `remoto/vigia_tailnet.py:84-94` (`_rodar`: `timeout=20`, qualquer `returncode != 0` vira
  "sem resposta") e `256-260` (`_dormir(5)` + segunda sonda, dentro do laço do bot).
- **O defeito:** quando o `tailscale status --json` não responde 3 vezes seguidas, a vigia
  manda "❔ não sei se o app está no tailnet … Pode ser só o comando travado, e o app pode
  estar no ar" e, ao responder de novo, "✅ voltou a responder". O próprio texto diz que a
  mensagem não tem informação. Cada olhada sem resposta também segura o laço do bot até
  45 s (20 s + 5 s + 20 s), e 3 seguidas somam 6 min de bot parado.
- **Quando acontece:** medido em `outputs/bot.txt`: 10/10 1 par, 11/10 3 pares, 12/10 6
  pares (12 mensagens ao Telegram; `avisos_enviados.jsonl` conta 12 com origem `bot` em
  12/10). Hoje o comando responde em 0,04–0,37 s (3 medições) e o `serve status` em
  0,03 s; a causa das falhas em série (máquina carregada, serviço ocupado) não foi medida.
- **Prova:** contagem por dia no log:
  ```
  10/10: naosei=1 voltou=1 fora=0
  11/10: naosei=3 voltou=3 fora=0
  12/10: naosei=6 voltou=6 fora=0
  ```
- **Conserto sugerido:** "sem resposta" só vai ao log (nunca ao Telegram), e só vira aviso
  quando acompanhado de prova de queda (a URL `*.ts.net` sem 200); subir o `timeout` da
  sonda e não repetir a sonda dentro da mesma olhada.

### 11. `relatorios.funcionamento` ignora o `agora` recebido no corte da janela

- **Onde:** `remoto/relatorios.py:412-415` (`corte = datetime.now(timezone.utc) - …`).
- **O defeito:** `montar("funcionamento", agora=X)` promete "últimas 24h" de `X`, mas o
  corte usa o relógio; só o cabeçalho obedece. Afeta reprodução de relatório antigo pela CLI
  e os testes que passam `agora`.
- **Prova:** `prova_bot.py` (prova 6): `funcionamento(datetime(2020,1,1))` → "mostra erro
  de hoje: True".
- **Conserto sugerido:** `corte = agora.astimezone(timezone.utc) - timedelta(hours=horas)`.

### 12. `config.carregar()` levanta com um autorizado não numérico (bot e `--status` quebram)

- **Onde:** `remoto/config.py:84` (`[int(c) for c in …]` sem proteção).
- **O defeito:** uma entrada como `"abc"` em `autorizados` (edição à mão; o arquivo tem
  dois backups `remoto.json.antes-*` de edições) derruba `Bot.__init__`, `python -m remoto
  --status`, `avisar()` e `carteiro.avisar_telegram` — o bot não sobe e não há aviso.
- **Prova:** `prova_avisos.py` (prova 3): `ValueError: invalid literal for int() with base
  10: 'abc'`.
- **Conserto sugerido:** ignorar (e logar) o item que não converte.

### 13. `config.salvar()` descarta qualquer chave que não esteja em `PADRAO`

- **Onde:** `remoto/config.py:91` (`limpo = {k: config.get(k, v) for k, v in PADRAO.items()}`).
- **O defeito:** `autorizar`/`esquecer`/`--token` regravam o `remoto.json` só com as chaves
  do `PADRAO`; qualquer chave extra some. Hoje o arquivo real só tem chaves do `PADRAO`
  (`alertas, autorizados, consertar, intervalo_alerta_s, token`), então nada se perde agora
  — vira perda no dia em que alguém acrescentar uma chave ao arquivo sem pô-la no
  `PADRAO`.
- **Prova:** `prova_bot.py` (prova 4): arquivo com `minha_chave` → depois de `autorizar(43)`
  as chaves são só as do `PADRAO`.
- **Conserto sugerido:** `limpo = {**config}` com os defaults por cima do que falta.

### 14. `_entregar_pendentes`: o grupo leva o texto de item que o porteiro acabou de calar

- **Onde:** `remoto/bot.py:269-276` (`texto` montado com `grupo`, `liberados` filtrado
  depois).
- **O defeito:** com mais de 3 pendentes, o texto agrupado é montado com TODOS os itens do
  grupo e só depois o porteiro decide quais estão liberados; o item calado (igual a um que
  já saiu hoje) vai no texto mesmo assim — o porteiro não cala nada nesse caminho.
- **Prova:** `prova_avisos.py` (prova 5): 3 novos + 1 repetido já enviado → "mensagens
  enviadas: 1; 'repetido' foi junto no grupo: True".
- **Conserto sugerido:** filtrar com `liberar` antes de montar o texto.

## Não confirmados

- **`config.runtime_dir()` ignora `NEURAL_FIGHTS_RUNTIME_DIR` — mas a suíte do `remoto/` não
  escapa para o estado real (hoje).** `remoto/config.py:26-28` monta sempre
  `%LOCALAPPDATA%\neural-fights`, enquanto `builds.contas.runtime_dir()` (e por ele diário,
  apurador, travas) obedece à variável que o `conftest.py` da raiz põe em toda suíte. Cada
  módulo cobre isso com uma variável própria (`config.ARQUIVO`, `avisos.*`, `tarefas.PASTA`,
  `acoes.ARQUIVO_*`, `decisoes.TRAVA/MIDIA_LOCAL`, `NF_ORQUESTRADOR_PASTA`…). Medido: a suíte
  inteira de `remoto/` (sem `test_app_tela.py`) com `LOCALAPPDATA` apontando para a pasta
  vazia `E:\tmp_pytest\fake_lad_audit` e `NEURAL_FIGHTS_RUNTIME_DIR` no padrão do conftest
  — `954 passed, 3 skipped, 14 deselected in 1072.54s` — e a pasta falsa terminou **vazia**:
  nenhum teste atual escreve pelo `runtime_dir()` de `config.py`. O risco fica para o
  próximo teste que esquecer a variável de módulo; conserto barato: `runtime_dir()` ler
  `NEURAL_FIGHTS_RUNTIME_DIR` primeiro (como `avisos._pasta` já faz).

- **`Telegram.mensagem` e o limite de 4096:** corta em 4000 caracteres Python; o Telegram
  conta de outro jeito para emojis fora do BMP. Não achei caso real de 400 por tamanho.
- **`bot.cmd` com `>>` (memória "agendador e arquivo trancado"):** a tarefa do Agendador e
  o coordenador anexam no mesmo `outputs/bot.txt` por caminhos diferentes (`>>` do cmd e
  `open("a")` do Python); as linhas das duas aparecem intercaladas no arquivo, então hoje
  não tranca. Fica a observação de que `tarefa.escrever_lancador` ainda gera o `>>`.
- **`Bot.__init__` guarda `self.config` uma vez:** `alertas` e `apurar` são lidos do cache
  do processo, `relatorios`/`vigiar_tailnet`/`autorizados` do disco. Mudar `alertas` no
  `remoto.json` só vale na próxima religada; não é erro, é inconsistência.
- **Mensagens enfileiradas na memória do Telegram entre religadas:** com `desde=None` na
  subida, o bot executa comandos mandados enquanto estava morto (um `/parar` de horas atrás
  roda na religada). O Telegram guarda 24 h. Não medi caso real; com as religadas de hoje
  (segundos) o efeito é pequeno.
- **`comandos.historias` (até 120 s) e `/auditoria` (decodifica mp4) dentro do laço:**
  bloqueiam o bot, por desenho; sem efeito além de atraso.
- **`relatorios.devidos`/`marcar` perto da meia-noite:** `hoje` é calculado antes de montar;
  um envio que atravessa 00:00 marca o dia anterior e o relatório sai de novo. Janela de
  segundos, uma vez por dia; não vi no `relatorios.json` real.
- **Vigia abrindo a bandeja pelo `explorer.exe`:** não exercitei (abriria a bandeja de
  verdade). O código só roda com o backend fora de `Running` e a bandeja fechada.
- **Markdown nos avisos de `_alertar`:** o detalhe do evento vai em `*…*` com `markdown=True`;
  um `_` no detalhe vira itálico, mas o `mensagem` reenvia sem formatação quando o Telegram
  recusa, então o texto chega.
- **`avisos._podar` com relógio no futuro/`em` ilegível:** `(_data(...) or agora) >= corte`
  mantém fichas sem data para sempre; só cresce com arquivo corrompido à mão.
