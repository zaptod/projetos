# Auditoria profunda — Motor: live e UI do launcher (nf-live-ui)

Data: 2026-10-13. Fatia: `neural_fights/live/**` (inclui `live/sources/`) e `neural_fights/ui/**`.
Só relatório; nenhum código do projeto foi alterado. Provas em
`%TEMP%\claude\e--projetos\...\scratchpad\prova_live_ui.py`, `prova_tk2.py` e `prova_tk3.py`
(rodadas de `E:\projetos` com `NEURAL_FIGHTS_RUNTIME_DIR` apontando para `E:\tmp_pytest\nf_prova_*`,
registro SQLite em `:memory:`, sem rede, sem Godot, nada gravado em `outputs/`). Capturas do launcher
em 1366x728 em `scratchpad\capturas\TelaLuta.png`, `TelaPersonagens.png`, `TelaArmas.png`.
Testes de base: `neural_fights/ui/test_launcher_regressions.py`, `tests/test_live_command_regressions.py`,
`tests/test_live_session_regressions.py`, `tests/test_broadcast_show_regressions.py`: 64 passed.

## Examinado (27 arquivos, 9.125 linhas, 384 funções — cada arquivo lido inteiro, função por função)

| Arquivo | Linhas | Funções | O que faz |
|---|---|---|---|
| `live/__init__.py` | 21 | 0 | exports |
| `live/events.py` | 239 | 10 | `ViewerEvent` imutável e validado, `EventKind` |
| `live/sources/base.py` | 166 | 13 | `EventSource`: thread produtora, fila limitada, stats |
| `live/sources/replay.py` | 227 | 17 | replay JSONL, `RecordingSource`, `ScriptedEventSource` |
| `live/sources/youtube.py` | 534 | 23 | chat do YouTube por `urllib`: token, polling, backoff, quota |
| `live/catalog.py` | 264 | 2 | `COMMAND_DB` (10 comandos) e gatilhos |
| `live/commands.py` | 367 | 21 | `CommandRouter`: idempotência, parsing, política, efeito, journal |
| `live/policy.py` | 209 | 10 | `PolicyEngine`: banimento, momento, cooldowns, teto, saturação, pagamento |
| `live/effects.py` | 157 | 9 | tradução do comando para a API do motor (buff, área, projétil) |
| `live/identity.py` | 164 | 7 | `catalog_name` `@id` e sanitização do nome de exibição |
| `live/registry.py` | 659 | 36 | SQLite: viewer, fighter, stats, journal, fila do round, blocklist |
| `live/roster.py` | 128 | 12 | `LiveRoster`: catálogo indexado + lutadores de espectador |
| `live/standings.py` | 119 | 7 | `registrar_resultado`, `RankedMatchmaker` |
| `live/session.py` | 326 | 18 | `LiveSession`: loop, drenagem, troca de partida, `Matchmaker` |
| `live/broadcast.py` | 299 | 13 | `BroadcastOverlay`: lower-thirds, toast, ticker, VS, countdown |
| `ui/__init__.py` | 2 | 0 | — |
| `ui/main.py` | 192 | 8 | `SistemaApp`, menu, `area_util_tela` |
| `ui/theme.py` | 197 | 9 | cores, `BotaoCanvas`, `CartaoMenu`, `desenhar_lutador` |
| `ui/arte_atelie.py` | 189 | 14 | prévia Tk das folhas do Ateliê (resolver, recortar, animar) |
| `ui/view_luta.py` | 725 | 20 | Arena: seleção, `exportar_palco_selecao`, `SeletorMapa` |
| `ui/view_torneio.py` | 409 | 18 | janela CTk do torneio: bracket, simular, Godot, salvar |
| `ui/view_chars.py` | 1.375 | 43 | wizard de personagens (6 passos) + CRUD |
| `ui/view_armas.py` | 1.312 | 40 | wizard da Forja (6 passos) + CRUD |
| `ui/view_sons.py` | 635 | 19 | configuração de sons e volumes |
| `ui/prova_launcher.py` | 42 | 1 | capturas das telas |
| `ui/test_launcher_regressions.py` | 156 | 14 | regressões do launcher |

Perguntas feitas a cada função. `live/`: fonte/socket/arquivo que nunca fecha; fila sem limite; thread sem
`join`; exceção engolida que vira "ok"; `time` dentro da simulação; dinheiro que some sem registro.
`ui/`: botão sem callback ou callback para função apagada em b03a7b7; `after()` chamado de thread;
duplo clique disparando dois processos; Godot/ffmpeg não morto ao fechar; caminho com espaço sem aspas;
estado marcado antes de o render terminar; janela que não cabe em 1366x768; funções públicas sem chamador.

### O que está certo (e vale registrar)
- **b03a7b7 não deixou órfão:** nenhuma referência a `INICIAR BATALHA`, `simulacao.Simulador`, rosto ou
  silhueta sobrou em `ui/`; `desenhar_lutador` só usa `arte_atelie`. Todo botão do launcher tem callback
  existente. O launcher não importa `pygame` (só `view_sons._testar_som`, sob demanda, para tocar som).
- **Fila da fonte é limitada e nunca bloqueia o jogo:** `EventSource._publicar` descarta o mais antigo
  com `put_nowait`; `drenar` usa `get_nowait`; `stop()` faz `join(timeout)` e avisa se não encerrou;
  `_loop_produtor` loga a exceção e conta `erros_conexao` em vez de fingir sucesso.
- **Sem `time` na simulação:** `LiveSession`, `PolicyEngine` e `YouTubeChatSource` recebem relógio
  injetado; o `time.time()` do `registry` é só carimbo de auditoria. O `dt` vem de `clock.tick(FPS)`.
- **Duplo clique coberto:** `TelaLuta._iniciar_palco` desliga os dois botões via `_palco_em_andamento`;
  o torneio desliga `btn_fight`/`btn_palco` enquanto a thread roda.
- **Caminho com espaço:** `godot.py`/`render.py` chamam `subprocess` com lista, sem `shell=True`.
- **Semente da exportação:** `exportar_palco_selecao` passa `--seed` (o `int(None)` de 02/10 não volta).
- **Journal antes de aplicar:** `processar` grava `RECEBIDO` antes de qualquer efeito; reentrega vira
  `DUPLICADO`. `_anotar` nunca derruba o frame.

## Confirmados (do mais grave ao menos)

### C1 — Torneio: "SIMULAR LUTA" e "Fighter N Venceu" gravam na luta corrente do bracket, não na selecionada; o resultado é descartado em silêncio
- **Onde:** `ui/view_torneio.py` `_on_simulation_finished` (l. 282) e `register_winner` (l. 323) →
  `tournament_mode.Tournament.record_match_result` (l. 372-381).
- **O defeito:** `record_match_result` ignora a luta selecionada: faz `match = self.get_current_match()`
  e, se o vencedor não está nela, imprime "ERRO" no console e devolve `False`. A janela não olha o
  retorno: escreve "Vencedor: X" / "✅ Vencedor registrado: X" no rodapé e redesenha o bracket — que
  continua igual. Cada card pendente tem botão "▶️ LUTAR" (`MatchCard`, l. 49-56), então selecionar
  qualquer luta que não seja a corrente é o uso normal da tela.
- **Quando acontece:** sempre que o Adrian clica LUTAR num card que não é o `get_current_match()` (por
  exemplo a 2ª luta da rodada enquanto a 1ª está pendente) e depois SIMULAR LUTA ou registra o vencedor à
  mão. A simulação (até 3 × 120 s) roda, o resultado some, a luta fica pendente para sempre.
- **Prova:** `prova_live_ui.py` §4 — bracket de 4: corrente `D vs B`, selecionada `C vs A`;
  `record_match_result(winner_name="C")` → `ERRO: Vencedor 'C' nao esta nesta luta!`, retorno `False`,
  `selecionada.completed = False`.
- **Conserto sugerido:** `record_match_result` receber o `match` (ou `match_id`) e a janela passar
  `self.current_match`; a janela tratar `False` como erro visível (`messagebox`), nunca como sucesso.

### C2 — Live: depois do primeiro `!arena` pago, qualquer um escolhe a arena de graça e o último da fila vence
- **Onde:** `live/policy.py` `avaliar` (ordem: `_checar_limites` l. 294-297 ANTES do pagamento l. 303-305)
  + `_checar_limites` devolve `ADIAR teto_do_round` (l. 329-331); `live/commands.py` `_adiar` (l. 1022-1034)
  enfileira sem `registrar_uso`; `criar_preparador` (l. 1142-1146) "último da fila vence".
- **O defeito:** com `usos_por_comando["arena"] >= 1` no round, a avaliação sai em `ADIAR` antes de checar
  `creditos_insuficientes`. `_adiar` vê `ENTRE_ROUNDS` em `aplicavel_em` e põe na fila. Quem pagou 150 é
  sobrescrito por quem digitou `!arena X` com 0 créditos; e como `registrar_uso` não roda, não há cooldown de
  300 s nem custo — dá para repetir a cada mensagem.
- **Quando acontece:** toda live com um `!arena` pago no round; a partir daí até o fim do round.
- **Prova:** `prova_live_ui.py` §2 — `!arena Gelo` com 0 créditos antes de qualquer pago → `RECUSADO
  creditos_insuficientes 0/150`; `!arena Vulcao` pago (150) → `APLICADO fila:Vulcao`; `!arena Inferno` com 0
  créditos → `ADIADO teto_do_round->fila`; `fila_pendente = 2`; plano da próxima partida:
  `{'cenario': 'Inferno'}`; créditos gastos do "pobre": 0.
- **Conserto sugerido:** checar pagamento antes de qualquer decisão `ADIAR` (ou repetir a checagem dentro de
  `_adiar`); `_adiar` chamar `registrar_uso` quando enfileira; e o preparador respeitar "primeiro pago vence"
  ou ao menos ignorar itens sem `viewer_id` pagante.

### C3 — Live: comando pago que cai em cooldown global/teto/saturação vira `ADIADO` e some — nada enfileira, nada reaplica, nada avisa de reembolso
- **Onde:** `live/policy.py` `_checar_limites` (`ADIAR cooldown_global` l. 318-320, `ADIAR teto_do_round`
  l. 330-331), `_checar_saturacao` (`ADIAR saturacao` l. 343-344); `live/commands.py` `_adiar` (l. 1034):
  para comandos só `ROUND_ATIVO` (todos os 9 exceto `arena`) devolve `ADIADO` sem fila.
- **O defeito:** o docstring promete "intenção paga que não coube agora vira crédito do próximo round", mas
  só `arena` tem `ENTRE_ROUNDS`; `!curar`, `!meteoro` etc. pagos num cooldown de 6-40 s terminam com
  status `ADIADO` e nunca mais são tocados. O journal registra, mas ninguém lê para reembolsar. O mesmo vale
  para superchat com comando durante a pausa de 6 s entre partidas: `RECUSADO fora_do_momento`.
- **Quando acontece:** dois espectadores pagam o mesmo comando com menos de `cooldown_global` de intervalo
  (6 s para `!curar`, 25 s para `!meteoro`), ou no 7º `!curar` do round, ou com 6 áreas vivas.
- **Prova:** `prova_live_ui.py` §2b — A paga 30 em `!curar p1` → `APLICADO Cura Menor`; B paga 30 um segundo
  depois → `ADIADO cooldown_global`; journal de B `('ADIADO', 'curar cooldown_global')`, `fila_pendente = 0`.
- **Conserto sugerido:** fila de "pendentes do round" para `ADIAR` (reaplicar quando o cooldown passa, na
  mesma `drenar_eventos`), ou devolver `RECUSADO` + marcador de reembolso que o overlay mostre
  (`notificar_comando` já trata recusa com `value_units > 0`).

### C4 — Live: lutador aposentado nunca volta — `!entrar` quebra com `IntegrityError` para sempre
- **Onde:** `live/registry.py` `criar_lutador` (l. 556-557: `fighter_id_de(viewer.viewer_id)` com
  `ordinal=0` fixo) + índice `idx_fighter_ativo` só sobre `retired_at IS NULL`, mas `fighter_id` é PRIMARY KEY
  e `catalog_name` é UNIQUE sem filtro.
- **O defeito:** `aposentar_lutador` marca `retired_at` e libera a vaga; o próximo `criar_lutador` gera o
  mesmo `fighter_id`/`catalog_name` e o INSERT falha. `commands.processar` engole em `STATUS_ERRO`.
- **Quando acontece:** qualquer espectador aposentado (moderação, futura regra de descarte) que digita
  `!entrar`; cada tentativa vira linha `ERRO` no journal.
- **Prova:** `prova_live_ui.py` §3 — criado `@ec164eab05`, `aposentar_lutador → True`, `criar_lutador` →
  `sqlite3.IntegrityError: UNIQUE constraint failed: fighter.catalog_name`; via router: `ERRO IntegrityError...`.
- **Conserto sugerido:** `ordinal = COUNT(fighter WHERE viewer_id=?)` ao gerar o id, ou reativar o aposentado
  (`retired_at = NULL`) em vez de criar outro.

### C5 — Launcher: a roda do mouse no wizard de personagens rola o canvas invisível da tela de Sons
- **Onde:** `ui/view_chars.py` l. 196 `self.canvas_wizard.bind_all("<MouseWheel>", ...)` e
  `ui/view_sons.py` l. 361 `canvas.bind_all("<MouseWheel>", ...)`; `ui/main.py` l. 69 constrói as telas na
  ordem `TelaPersonagens` → … → `TelaSons`.
- **O defeito:** `bind_all` sem `add="+"` substitui a ligação global; a última a ser construída
  (`TelaSons`) vence. Na Tela de Personagens a roda não move o wizard (passo 2 "CLASSE" tem 16 classes, não
  cabem) e ainda desloca o canvas de Sons escondido.
- **Quando acontece:** sempre, em toda sessão do launcher.
- **Prova:** `prova_live_ui.py` §6 — binding "all" aponta para o `_on_mousewheel` de Sons; `<MouseWheel
  delta=-120>` gerado sobre `canvas_wizard` no passo 2: wizard `yview` `(0.0, 0.318)` → `(0.0, 0.318)`
  (parado); canvas de Sons `(0.0, 0.252)` → `(0.025, 0.277)` (moveu).
- **Conserto sugerido:** trocar os dois `bind_all` por `bind` no próprio canvas/filhos (como já faz o
  `canvas_armas` do passo 6) ou um único `bind_all` no `SistemaApp` que despacha para a tela visível.

### C6 — Launcher: a prévia do lutador some quando há arma — `arte_atelie.desenhar` guarda UMA `PhotoImage` por canvas
- **Onde:** `ui/arte_atelie.py` `desenhar` l. 739-741 (`canvas._arte_atelie_foto = foto`); chamado duas
  vezes por quadro em `ui/theme.py` `desenhar_lutador.quadro` (corpo e arma, l. 365-367).
- **O defeito:** a segunda chamada (arma) sobrescreve a única referência Python; a `PhotoImage` do corpo é
  coletada e o Tk apaga a imagem (`image delete`) — o item do canvas fica apontando para imagem inexistente e
  não desenha nada. Com folha de 1 quadro não há re-tick; com animação o corpo pisca a cada quadro.
- **Quando acontece:** TelaLuta e TelaPersonagens sempre que o personagem tem arma E existe folha do Ateliê
  para a classe (hoje a maioria cai no marcador cinza, que não usa `PhotoImage`; assim que o Adrian subir a
  arte, o corpo desaparece). `view_armas.atualizar_preview` tem só uma imagem, não sofre.
- **Prova:** `prova_live_ui.py` §5 — `desenhar(corpo)` cria `pyimage1`; `desenhar(arma)`; `gc.collect()`;
  `image names` do Tk = `('pyimage2', …)`: `pyimage1` não existe mais.
- **Conserto sugerido:** guardar uma lista/dict por tag (`canvas._arte_atelie_fotos[ident] = foto`) e
  limpar por tag em `limpar`.

### C7 — Launcher: o rodapé da Arena (mensagem "Concluído: …" / erro do Godot) fica atrás da barra de tarefas no 1366x768 do Adrian
- **Onde:** `ui/main.py` `SistemaApp.__init__` l. 41-45 (`geometry` com altura = área útil, sem descontar a
  barra de título) e `ui/view_luta.py` l. 93-97 (`lbl_progresso_palco` abaixo dos botões).
- **O defeito:** `area_util_tela` devolve 1366x728; a janela pede cliente 1280x720 em +0+0, a barra de título
  tem 31 px → fundo da janela em y=751 > 728. Os botões terminam em 707 (visíveis); o rótulo de progresso
  termina em 731: tapado pela barra. O `maxsize` tem o mesmo erro. O teste `test_textos_e_acoes_cabem_na_area_util`
  passa porque compara com a própria janela, não com a área útil.
- **Quando acontece:** toda abertura do launcher na tela de 1366x768 (barra de 40 px). Depois de "VER
  LUTA"/"RENDERIZAR MP4" a mensagem de resultado ou de erro não aparece; só o `messagebox` de erro.
- **Prova:** `prova_tk3.py` — `area util 1366x728`, `geometry 1280x720+0+0`, `rooty 31`, fundo da janela 751;
  `btn_palco` fundo 707 visível; `lbl_progresso_palco` fundo 731 → escondido (com e sem texto).
  Captura `capturas/TelaLuta.png`: a faixa abaixo dos botões já é a barra do Windows.
- **Conserto sugerido:** descontar a moldura (`winfo_rooty() - winfo_y()` após `update_idletasks`) ao
  calcular altura e `maxsize`; e o teste comparar `winfo_rooty()+winfo_height()` com a área útil.

### C8 — Broadcast: o lower-third mostra "Fulano usou !?" para todo comando — `evento.texto` não existe (o campo é `text`)
- **Onde:** `live/broadcast.py` `notificar_comando` l. 321 `getattr(evento, "texto", "")`;
  `live/events.py` define `text` (l. 121).
- **O defeito:** o verbo nunca começa com "!", cai no `"!?"`. O teste `tests/test_broadcast_show_regressions.py`
  l. 88-126 passa porque usa `SimpleNamespace(..., texto="!meteoro")` — um dublê com o nome errado, que é
  exatamente o que esconde o bug.
- **Quando acontece:** toda live com overlay: `!entrar`, `!meteoro`, toast de recusa — sempre "!?".
- **Prova:** `prova_live_ui.py` §1 — `ViewerEvent(text="!meteoro")` aplicado → `{'nome': 'Ana', 'verbo': '!?'}`;
  recusa paga → `'Ana: !? — creditos_insuficientes 0/120'`.
- **Conserto sugerido:** `evento.text`; e o teste construir `ViewerEvent` de verdade.

### C9 — Torneio: "🎲 Gerar Roster" apaga o catálogo inteiro do Adrian (armas + personagens) sem perguntar
- **Onde:** `ui/view_torneio.py` `generate_roster` l. 367-368 → `gerador_database.salvar_database(armas,
  personagens)` com `substituir=True` (padrão, l. 665) → `database.resolver_database_paths(para_escrita=True)`
  grava em `ARQUIVO_ARMAS_RUNTIME`/`ARQUIVO_CHARS_RUNTIME` — a mesma cópia de runtime que o launcher lê.
- **O defeito:** um clique num botão de 100 px, sem `askyesno`, substitui os personagens e armas criados no
  wizard por 64 gerados. O `.bak` de `database.py` l. 327-360 é só para desfazer uma escrita que falha no
  meio, não um backup que fica.
- **Quando acontece:** clique acidental em "Gerar Roster" (está ao lado de "Novo Torneio").
- **Prova:** leitura (não executado de propósito: gravaria no catálogo). `salvar_database(..., substituir=True)`
  → `armas_final = armas_novas` (l. 681-683).
- **Conserto sugerido:** `askyesno` com o número de personagens que serão apagados, ou `substituir=False`
  (acrescenta), ou gravar em arquivo separado de torneio.

### C10 — YouTube: 403 de quota vira "falha de autenticação" e a fonte morre; a quota nunca zera; chat/token de página nunca são refeitos
- **Onde:** `live/sources/youtube.py` `_transporte_urllib` l. 306-308 (`401, 403 → ErroDeAutenticacao`);
  `_executar` l. 364-368 (`ErroDeAutenticacao → return`); `Quota` (l. 262-293) sem reset diário;
  `resolver_live_chat_id` docstring "refeito quando o token de página é recusado" (l. 396) mas `_live_chat_id`
  e `_page_token` nunca são limpos em erro (l. 369-381).
- **O defeito:** a API devolve `403 quotaExceeded`/`forbidden` para quota e para chat encerrado; o código
  trata todo 403 como credencial ruim e encerra a thread — contradiz a invariante 3 do próprio módulo ("quota
  degrada, não morre"). Numa live de madrugada que cruza o reset da quota (meia-noite PT) o intervalo fica
  em 60 s para sempre. Um `pageToken` inválido (404/400) vira `ErroDeTransporte` repetido eternamente com o
  mesmo token.
- **Quando acontece:** live longa (10.000 unidades = ~2.000 polls; a ~2 s por poll, menos de 1h10 de chat
  ativo) ou chat trocado no meio.
- **Prova:** leitura; `tests/test_live_youtube_regressions.py` l. 439 testa 403 só como autenticação.
- **Conserto sugerido:** olhar `errors[0].reason` do corpo (`quotaExceeded`/`rateLimitExceeded` → backoff
  longo; `liveChatEnded`/`pageTokenInvalid` → limpar `_live_chat_id`/`_page_token`); `Quota` com data do dia.

### C11 — Launcher: fechar a janela com exportação/render em andamento — a thread morre com `RuntimeError` e o Godot/ffmpeg continua
- **Onde:** `ui/view_luta.py` `_iniciar_palco.trabalho` l. 349-368 (`self.after` de thread, fora do
  `try`); `ui/view_torneio.py` l. 273 e 304-306 (idem); `random_builds/builds/palco/godot.py` `_rodar`
  (`subprocess.run` sem referência fora da thread) e `abrir_previa` (`Popen` esquecido).
- **O defeito:** `after()` chamado de outra thread só funciona enquanto a thread principal está no
  `mainloop`. Fechado o launcher, a chamada levanta `RuntimeError: main thread is not in main loop` dentro
  da thread (não é capturada: os `self.after` estão nos `except`/`else`). O processo filho do Godot (render de
  até 900 s) não é morto; nada guarda o `Popen`.
- **Quando acontece:** "RENDERIZAR MP4" e fechar a janela antes de terminar (render leva minutos).
- **Prova:** `prova_tk2.py` §B — botões `disabled`, `_palco_em_andamento=True`; `app.destroy()` com a
  exportação a meio → `threading.excepthook` recebe `RuntimeError: main thread is not in main loop`.
- **Conserto sugerido:** fila `queue.Queue` + `after` periódico na thread principal (padrão que o painel já
  adotou); guardar o `Popen` e `terminate()` em `WM_DELETE_WINDOW`.

### C12 — Live: o nome do lutador na tela congela no `!entrar`; troca de nome e blocklist posterior não chegam ao HUD
- **Onde:** `live/registry.py` `criar_lutador` l. 571 grava `viewer.display_name` em `fighter.display_name`;
  `mapa_nomes_exibicao` l. 341-345 lê `fighter`, não `viewer`; `registrar_viewer` l. 239-242 atualiza só
  `viewer`.
- **O defeito:** moderador bloqueia um termo depois (`bloquear_termo`) ou a pessoa renomeia; o `viewer`
  muda, o HUD continua mostrando o nome antigo — inclusive o ofensivo.
- **Quando acontece:** toda moderação feita depois do primeiro `!entrar` do espectador.
- **Prova:** `prova_live_ui.py` §3c — viewer renomeado para `NomeNovo` e termo `nomeantigo` bloqueado;
  `mapa_nomes_exibicao() = {'@9c1b164177': 'NomeAntigo'}`.
- **Conserto sugerido:** `mapa_nomes_exibicao` fazer JOIN com `viewer.display_name` (re-sanitizado pela
  blocklist viva).

### C13 — Live: o journal nunca sabe quem mandou o evento (`viewer_id` sempre NULL)
- **Onde:** `live/commands.py` `processar` l. 896-902 chama `registrar_evento` sem `viewer_id`;
  `registry.registrar_evento` aceita o campo (l. 407).
- **O defeito:** "dinheiro está envolvido, e falha silenciosa é inaceitável" (docstring), mas a tabela que
  deveria permitir reembolso/auditoria não liga evento a espectador; só o `detalhe` textual sobra.
- **Prova:** `prova_live_ui.py` §3b — `SELECT event_id, viewer_id, status` → `('en1', None, 'ERRO')`.
- **Conserto sugerido:** calcular `viewer_id_de(evento.platform, evento.viewer_id)` e passar.

### C14 — Launcher: o resumo de stats do wizard de personagens inventa fórmulas que o motor não usa
- **Onde:** `ui/view_chars.py` `criar_resumo_stats` l. 268-274 (`HP = 100 + forca*10`,
  `velocidade = (10 - tamanho*2) * mod_velocidade`); o modelo em `models/characters.py` l. 68-75 usa
  `velocidade_base_ms * fator_peso * fator_forca` e `resistencia = tamanho * forca * mod_vida`.
- **O defeito:** o Adrian ajusta altura/força olhando números que não existem no jogo. A Arena mostra os
  reais (`VEL 5.1 | RES 22.5` na captura) e o wizard mostra outros para o mesmo personagem.
- **Prova:** `prova_live_ui.py` §7 — Guerreiro 1,70 m / força 5: launcher `HP=270 Vel=6.6`; modelo
  `resistencia=15.3 velocidade=7.35 m/s`.
- **Conserto sugerido:** montar um `Personagem` temporário (como `salvar_personagem` faz) e ler
  `velocidade`/`resistencia` dele.

### C15 — Launcher: a lista de armas do passo 6 não atualiza ao voltar da Forja (o refresh mira o passo 5)
- **Onde:** `ui/view_chars.py` `atualizar_dados` l. 1235-1237: comentário "se estiver no passo de
  equipamento" mas testa `passo_atual == 5`; equipamento é o passo 6 (`mostrar_passo` l. 387-388).
- **O defeito:** forjar uma arma, voltar a Personagens parado no passo 6: a arma nova não aparece até
  navegar; no passo 5 (visual) o passo é reconstruído à toa.
- **Prova:** leitura.
- **Conserto sugerido:** `== 6`.

### C16 — Forja: "Sugerir Tamanhos (baseado no personagem)" nunca vê personagem
- **Onde:** `ui/view_armas.py` `aplicar_sugestao_geometria` l. 662-663 lê `controller.lista_chars`; o
  controller tem `lista_personagens` (`ui/main.py` l. 56).
- **O defeito:** `hasattr` falha sempre, `sugerir_tamanho_arma(None, tipo)` usa `tamanho_base = 10.0`
  fixo; o botão promete o que não faz.
- **Prova:** leitura (`models/weapons.py` l. 367-370).
- **Conserto sugerido:** `lista_personagens` (e escolher qual personagem, não o `[0]`).

### C17 — Forja: visitar o passo 3 arredonda o dano para inteiro
- **Onde:** `ui/view_armas.py` l. 592-597 `tk.Scale(from_=1, to=50)` sem `resolution` + `set(dano)` dispara
  `atualizar_dado("dano", float(v))`; `selecionar_raridade` l. 547 gera `10 * mod_dano` (12,5 etc.).
- **O defeito:** editar uma arma com dano 12,5 e passar pelo passo 3 grava 12 ou 13.
- **Prova:** leitura.
- **Conserto sugerido:** `resolution=0.5` ou não reescrever o dado no `set` inicial.

### C18 — Live: saturação conta a mesma área duas vezes e nunca decresce dentro do round
- **Onde:** `live/policy.py` `_checar_saturacao` l. 342 soma `estado_mundo["areas"]` (áreas vivas no
  `sim.areas`, que já inclui as de espectador) + `round.areas_de_espectador` (só cresce, l. 360-361).
  `_aplicar_global` cria 2 áreas por comando (l. 1287-1288) e `registrar_uso` conta 1.
- **O defeito:** 2 `!meteoro` (4 áreas vivas + 2) já batem o teto 6 mesmo com as áreas expiradas; o
  terceiro pagante cai em C3.
- **Prova:** leitura.
- **Conserto sugerido:** contar só o estado vivo, ou decrementar quando a área morre.

### C19 — `RecordingSource`: eventos que restam na fonte interna ao parar são perdidos; arquivo aberto antes de a interna subir
- **Onde:** `live/sources/replay.py` `start` l. 350-354 (abre o arquivo, depois `interna.start()` — se este
  levantar `RuntimeError` por já estar iniciada, o handle fica aberto), `stop` l. 356-361 (para a interna e
  a própria thread sem drenar o que sobrou na fila da interna).
- **Prova:** leitura.
- **Conserto sugerido:** abrir o arquivo depois de `interna.start()`; em `stop`, drenar+gravar o restante.

### C20 — Funções públicas sem chamador fora de testes
`registry.ja_processado`, `registry.stats_do_lutador`, `registry.definir_banimento` (não há caminho de
moderação ligado ao chat nem ao CLI), `roster.todos_os_nomes`, `roster.recarregar_catalogo`,
`view_luta.TelaLuta.atualizar_previews` (stub "compatibilidade"), `view_torneio.launch_tournament_window`.
Prova: `grep -rn` em `neural_fights/`, `random_builds/`, `remoto/` excluindo `tests/`.

## Não confirmados
- **Referência órfã de b03a7b7:** nenhuma. `grep` por rosto/silhueta/`Simulador`/`INICIAR BATALHA` em
  `ui/` só acha o teste que garante a ausência.
- **`after()` de thread em uso normal:** com o `mainloop` rodando o Tk marshala a chamada e funciona; só
  quebra ao fechar a janela (C11). Não reproduzi travamento com a janela aberta.
- **Duplo clique disparando dois Godot:** os botões ficam `disabled` durante o trabalho (prova §B). O
  único caso aberto é "SIMULAR LUTA" e "VER NO GODOT" do torneio em paralelo, que é intencional.
- **Caminho com espaço sem aspas:** `godot.py`/`render.py` usam lista no `subprocess`. Não achei `shell=True`.
- **Estado marcado antes de o render terminar:** `_finalizar_palco` só roda no `after` depois de
  `exportar_palco_selecao` devolver; o torneio só grava resultado depois de `run_single_match`. Correto.
- **Janela que não cabe:** com 1366x728 todos os botões das três telas ficam dentro da janela (teste
  parametrizado passa; capturas). O que fica fora é só o rótulo de progresso (C7).
- **`SeletorMapa` com `transient(Frame)`:** o Tk sobe até o toplevel; abriu sem erro na prova §C.
- **`time` dentro da simulação:** não há; relógios injetados.
- **Fila sem limite / thread sem join:** não há em `live/`; a fila do `RecordingSource` herda o `maxsize`
  da interna.
- **`live/session.py` chamando `pygame.display.flip()` com `Simulador` vivo:** ainda existe (`cli/live.py`
  cria `Simulador` com janela); o corte do pygame foi só no launcher. Não é defeito desta fatia.
- **Nome de personagem com `/` ou `:` quebrando `config.SAIDAS / f"{p1}_vs_{p2}.gcpf"`:** o gerador e o
  wizard não produzem esses caracteres hoje; não testei nome digitado à mão com barra.
