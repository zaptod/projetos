# Auditoria profunda — Motor: gravação, torneio, CLI e utils — 13/10/2026

Só relatório; nenhum código do projeto foi alterado. Provas rodadas fora do
repositório (`E:\tmp_pytest\prova_nf\` e o scratchpad da sessão), sem rede,
sem Godot e sem escrever em `outputs/`. Lutadores reais do banco
(`Roland o Nobre` x `Elara o Lendário`), gravações curtas (1 a 8 s), ffmpeg
real (8.1.2) e Python 3.14.4.

## Examinado

Leitura inteira, função por função: 18 arquivos, 229 funções/métodos.

- `neural_fights/recording/fight_recorder.py` — 20 funções, 3 classes de sonda; o gravador oficial (mp4 por pipe ao ffmpeg, eventos de dano, narrativa, câmera, som anotado, timeline).
- `neural_fights/recording/timeline.py` — 103 funções/métodos; a `SondaTimeline` (contrato do palco), `hash_estado`, o laço `gravar_timeline` e a CLI.
- `neural_fights/recording/timeline_arquivo.py` — 18 funções; JSON e container GCPF, `validar`, `quadro`, remapeamento.
- `neural_fights/recording/skill_demo.py` — 9 funções; demos de skill em mp4 com manifest.
- `neural_fights/recording/__init__.py` — docstring.
- `neural_fights/tournament/tournament_mode.py` — 32 funções/métodos; chave eliminatória, BYEs, save/load validado, `TournamentRunner` (headless e visual).
- `neural_fights/tournament/__init__.py` — reexports.
- `neural_fights/cli/main.py`, `roster.py`, `tournament.py`, `headless.py`, `live.py`, `__init__.py` — 22 funções; pontos de entrada.
- `neural_fights/utils/__init__.py`, `config.py`, `console.py`, `fonts.py`, `palette.py` — 25 funções; constantes, saída segura, cache de fontes, paleta.

Também lidos para contexto (fora da fatia, só o necessário): `simulation/headless.py` (validação de `fixed_dt`/`max_frames`, `double_ko`), `simulacao.py:596-616` e `:6714-6735` (`_finalizar_round`, `avancar_relogio`), `random_builds/builds/tournament/capture.py` (quem chama o gravador por subprocesso) e `random_builds/builds/palco/fonte.py` (quem chama `gravar_timeline`).

### Os três já apontados na auditoria rasa (conferidos; continuam)

- **fps acima de 60 acelera a luta** — continua (`fight_recorder.py:588`); e é só um caso de um defeito maior, ver o item 2 abaixo.
- **`--max-duracao 0` dá sucesso com 0 s** — continua, e `-5` idem: `sucesso=True, duracao_video=0.0, serie_hp=[(0.0, 100.0, 100.0)]` (`fight_recorder.py:621-623`, `:785`).
- **`timeline_arquivo.salvar` com temporário fixo** — continua (`timeline_arquivo.py:145`, `caminho.name + ".tmp"`).

## Confirmados (do mais grave ao menos)

### 1. O ffmpeg pode terminar com erro e o gravador responde `sucesso: True` com um mp4 que não abre

- **Onde:** `neural_fights/recording/fight_recorder.py:743-748` (`processo.stdin.close(); processo.wait()` sem olhar o código de saída) e `:753-758` (o `finally` idem); `main` em `:845` devolve `0 if resultado.get("sucesso")`. O mesmo padrão em `skill_demo.py:256-261`.
- **O defeito:** o retorno do `wait()` é descartado, ninguém confere se o arquivo existe, tem tamanho ou abre. Se o ffmpeg falha DEPOIS de consumir todos os quadros (trailer do mp4, disco cheio na hora de fechar, arquivo trancado por antivírus/player, muxer), a resposta é "sucesso" e o `arquivo` aponta para um mp4 sem `moov`. O `capture.py` do random_builds só lê a linha JSON, então o defeito passa para o fight.json e para a edição. Quando o ffmpeg morre ANTES de consumir tudo, o erro vira `BrokenPipeError: [Errno 32] Broken pipe` / `OSError: [Errno 22] Invalid argument` — o motivo real (que o ffmpeg imprimiu no stderr) não chega ao resultado.
- **Quando acontece:** qualquer falha do ffmpeg no fechamento (o C: desta máquina "vive cheio"); e qualquer falha precoce vira uma mensagem que não explica nada.
- **Prova** (ffmpeg real, sem dublar nada): outro handle trancou os 4 KiB iniciais do mp4 quando ele já tinha 524 336 bytes; o muxer mp4 volta ao início no fim para gravar o tamanho do `mdat`, falhou (`Error writing trailer: Permission denied`) e saiu com código ≠ 0. `gravar_luta` devolveu `sucesso=True, erro=None, duracao_video=8.0`, arquivo de 1 095 189 bytes; `ffprobe`: `moov atom not found / Invalid data found when processing input`. Com `preset="nao_existe"` (falha precoce), a exceção que sobe é `BrokenPipeError` ou `OSError: [Errno 22]`, e com `.xyz` como saída idem.
- **Conserto sugerido:** guardar `codigo = processo.wait()`; se `codigo != 0` ou o arquivo não existe/tem 0 bytes, devolver `sucesso: False` com o `stderr` do ffmpeg (abrir o `Popen` com `stderr=PIPE` e ler no fim, ou gravar o stderr num arquivo ao lado). Envolver o `stdin.write` em `try/except (BrokenPipeError, OSError)` que espera o processo e relata o stderr em vez da exceção crua. Opcional: `ffprobe` rápido do arquivo antes de dizer sucesso.

### 2. Qualquer fps que não divide 60 grava a luta na velocidade errada (24, 25, 40, 45, 50…)

- **Onde:** `fight_recorder.py:587-589` (`a_cada = max(1, round(FPS / fps_saida))`, `dt_video = 1 / fps_saida`) e o mesmo em `timeline.py:2543`.
- **O defeito:** o gravador captura um quadro a cada `a_cada` passos de 1/60 s e declara ao ffmpeg `-r fps_saida`. Isso só é tempo real quando `60 / fps_saida` é inteiro (30, 20, 15, 12, 10, 60). Em 24 fps, `a_cada = 2` → 30 quadros de jogo por segundo mostrados a 24/s → luta a 0,8x. Em 45 ou 50, `a_cada = 1` → 60 quadros por segundo mostrados a 45 ou 50 → 0,75x e 0,83x. Acima de 60 (já apontado) acelera. `duracao_video` e `t_video` (eventos de dano, série de HP, sons, `ko_em_video`) passam a divergir do tempo de jogo; a `SondaCamera` mede o pan com `dt_video` errado. A CLI aceita qualquer `--fps` sem aviso, e o `capture.py` repassa `fps` como parâmetro.
- **Quando acontece:** sempre que alguém grava com `--fps` fora de {60, 30, 20, 15, 12, 10, …}. Hoje a produção usa 30, então não dói; é uma armadilha armada para a primeira vez que alguém pedir 24 ou 50.
- **Prova** (`gravar_luta`, `saida=None`, `max_duracao=3.0`, seed 5): fps 30 → `duracao_jogo=2.98` (0,99x); fps 24 → `2.38` (0,79x); fps 25 → `2.48` (0,83x); fps 45 → `2.25` (0,75x); fps 50 → `2.5` (0,83x). Com `--timeline` em 24 fps o documento registra `passos_por_quadro=2`, `n=143`, `quadros=72`, `duracao_video=3.0`: 23,83 quadros gerados por segundo de jogo contra os 24/s declarados.
- **Conserto sugerido:** exigir `FPS % fps_saida == 0` (`parser.error` na CLI, `ValueError` na função) ou, se quiser fps livre, capturar por acumulador de tempo (`proximo_quadro += 1/fps_saida` comparado ao `t_jogo`), nunca por passo inteiro.

### 3. `--fps` negativo é aceito e o gravador entra em laço infinito

- **Onde:** `fight_recorder.py:620-671` e `:784` (`type=int` sem limite); o laço de `timeline.py:2549-2576` tem a mesma estrutura.
- **O defeito:** com `fps_saida < 0`, `a_cada = max(1, round(60/fps)) = 1`, `t_video = capturados / fps_saida` fica negativo e decresce, então nem `t_video >= max_duracao` nem `t_video - t_ko_video >= cauda_pos_ko` acontecem — nem depois do KO. `--fps 0` dá `ZeroDivisionError` (vira `sucesso: False`, aceitável).
- **Quando acontece:** erro de digitação na CLI ou no `capture.py`. O subprocesso só morre pelo `timeout=600` do `capture.py`, que então reporta "gravacao passou de 600s" — dez minutos perdidos por lutador.
- **Prova:** `python -m neural_fights.recording.fight_recorder --p1 … --p2 … --sem-video --sem-som --fps -30 --max-duracao 1` não terminou em 25 s (`TimeoutExpired`).
- **Conserto sugerido:** validar `fps_saida >= 1` (e, pelo item 2, divisor de 60) na entrada de `gravar_luta`/`gravar_timeline` e com `parser.error` nas duas CLIs.

### 4. `skill_demo`: a demo anterior é destruída antes de saber se a nova vai sair, e o ffmpeg que não responde não é morto

- **Onde:** `neural_fights/recording/skill_demo.py:199-203` (abre o ffmpeg com `-y` no destino FINAL antes do cast), `:213-217` (`return` dentro do `try` com "cast recusado pelo runtime"), `:255-261` (`finally`: `ffmpeg.wait(timeout=60)` dentro de `except Exception: pass`, sem `kill()`), `:296-309` (`gerar` só atualiza o manifest em sucesso).
- **O defeito:** (a) `_abrir_ffmpeg` usa `ffmpeg -y` direto em `outputs/skill_demos/<slug>.mp4`: a demo boa é truncada na hora em que o processo abre; se o cast é recusado, uma exceção acontece ou a consequência não é observada, o `finally` fecha o pipe e o ffmpeg deixa um mp4 de 0 quadros no lugar da demo boa. O manifest continua apontando para esse arquivo (`caminho_da_demo` só confere `is_file()`), então o random_builds (`tournament/timeline.py:182`) passa a usar um clipe quebrado como card de skill. Depois de `--forcar` o hash fica "em dia" e o clipe quebrado nunca mais é regravado. (b) Se o ffmpeg travar, `wait(timeout=60)` levanta `TimeoutExpired`, é engolido e o processo filho fica vivo (zumbi) segurando o arquivo. (c) O código de saída do ffmpeg é ignorado como no item 1: `ok` depende só da consequência observada.
- **Quando acontece:** qualquer regravação (`--todas` depois de mudar um contrato) em que uma skill falha no meio.
- **Prova:** com um "mp4 anterior" de 1000 bytes no destino, `_abrir_ffmpeg(...)` seguido de `stdin.close(); wait()` (exatamente o caminho do `return` precoce) devolveu `returncode = 4294967268` (≠ 0) e deixou o arquivo com 262 bytes — a demo anterior foi substituída por lixo. Os itens (b) e (c) são por leitura das linhas citadas.
- **Conserto sugerido:** gravar em `destino.with_suffix(".tmp.mp4")` e só `replace()` para o nome final quando `resultado["ok"]` e o ffmpeg saiu com 0; no `finally`, `except subprocess.TimeoutExpired: ffmpeg.kill(); ffmpeg.wait()`; registrar o código de saída em `resultado["erro"]`.

### 5. `cli.live --roster 1` derruba a sessão com `IndexError`

- **Onde:** `neural_fights/cli/live.py:33-37` (`_roster`: confere `len(nomes) < 2` ANTES de aplicar `nomes[:limite]`) e `:40-43` (`_montar_config` lê `nomes[1]`).
- **O defeito:** a guarda "são necessários ao menos dois personagens" é feita sobre o catálogo inteiro, não sobre o corte. `--roster 1` devolve uma lista de 1 nome e o `nomes[1]` explode com traceback na montagem da config (`:195`), sem mensagem de erro útil. `--roster -1` corta o último lutador em silêncio (`nomes[:-1]`); `--roster 0` é tratado como "todos".
- **Quando acontece:** operador ensaiando a live com um lutador só, ou digitando negativo.
- **Prova:** `live._roster(1)` → `['Roland o Nobre']`; `live._montar_config(nomes, "Arena", False)` → `IndexError: list index out of range`; o parser aceita `--roster 1`, `--max-partidas 0` e `--pausa -3`.
- **Conserto sugerido:** validar depois do corte (`if limite is not None and limite < 2: erro`), ou `type=` que rejeite `< 2` no parser.

### 6. O gravador diz `sucesso: True` e sai com código 0 mesmo quando a timeline (ou o som) que foi pedida não foi gravada

- **Onde:** `fight_recorder.py:434-449` (`_salvar_timeline` "nunca levanta"), `:640-644` (exceção da sonda vira `erro_timeline` e a sonda é desligada), `:719-721`, `:845` (`return 0 if resultado.get("sucesso")`); o mesmo para `_embutir_som` (`:396-431`: `som_no_video: False` continua "sucesso").
- **O defeito:** quem pediu `--timeline caminho` recebe exit 0 e `"timeline": null`. Um pipeline que encadeia "gravar → renderizar no Godot" só descobre no Godot que o arquivo não existe. É decisão documentada ("a timeline nunca derruba a gravação"), mas o código de saída deveria distinguir "tudo o que foi pedido saiu" de "saiu só o mp4".
- **Quando acontece:** disco/caminho inválido, falha na sonda (qualquer exceção em `on_frame`), `numpy` ausente para o som.
- **Prova:** `gravar_luta(..., timeline=r"Z:\nao_existe\x.gcpf")` → `sucesso=True, timeline=None, erro_timeline="FileNotFoundError: [WinError 3] …"`; a CLI com o mesmo `--timeline` devolveu exit `0` e o JSON com o `erro_timeline`.
- **Conserto sugerido:** manter o mp4, mas `return 0` só quando não há `erro_timeline`/`erro_som` (ou um exit 3 "parcial"), e imprimir o erro no stderr.

### 7. A chave do torneio é sorteada com o `random` global, sem seed: dois torneios "iguais" nunca são iguais

- **Onde:** `neural_fights/tournament/tournament_mode.py:214` e `:231` (`random.shuffle` do módulo); `TournamentRunner.simulation_config["seed"]` em `:1137` só semeia as lutas (`:1310`).
- **O defeito:** o motor é determinístico por seed e o runner cuida disso luta a luta (`seed + match_id`), mas o pareamento não: o mesmo roster gera chaves diferentes a cada `generate_bracket()`, e não há parâmetro para fixar. Um torneio de vídeo não pode ser re-simulado nem reproduzido a partir do save sem o arquivo de estado. Além disso, `random.shuffle` global pode ser afetado por (e afetar) quem mais usa `random` no processo — a UI do torneio e o motor visual rodam no mesmo processo.
- **Quando acontece:** sempre.
- **Prova:** mesma lista de 8 nomes, três `generate_bracket()` seguidos → 3 ordens distintas.
- **Conserto sugerido:** `random.Random(seed)` próprio no `Tournament` (seed no construtor e persistida no save), usado nos dois `shuffle`.

### 8. `Tournament.stats` promete `fastest_ko`, `longest_fight` e `most_aggressive` e nunca os preenche; `ROUND_COMPLETE` nunca é atingido

- **Onde:** `tournament_mode.py:143-149` e `:248-254` (inicialização), `:372-417` (`record_match_result` só mexe em `total_fights`/`total_kos`), `:84-88` (`TournamentState.ROUND_COMPLETE` sem nenhum `self.state = …` que o use), `:752-769` (o `load_state` valida esses campos com cuidado).
- **O defeito:** três estatísticas são salvas, validadas no load e exibidas como "None" para sempre; o estado `ROUND_COMPLETE` existe, é aceito pelo save e nunca ocorre. Código morto que custa validação e confunde quem lê o JSON.
- **Quando acontece:** todo torneio.
- **Prova:** torneios de 3, 5, 6 e 7 participantes levados ao fim com `record_match_result` (KO de 10 s cada): `total_fights` certo (2, 4, 5, 6), `fastest_ko=None longest_fight=None most_aggressive=None` em todos.
- **Conserto sugerido:** preencher em `record_match_result` (`min`/`max` de `duration` quando `"KO" in ko_type`; `most_aggressive` a partir do `engine_result`), ou remover os três campos e o estado do contrato de save.

### 9. `run_single_match` rotula "Duplo KO" num caminho que não existe e o seed do retry colide com o da luta seguinte

- **Onde:** `tournament_mode.py:1310-1346` (`attempt_seed = initial_seed + attempt`, `initial_seed = seed + match_id`) e `:1348-1352` (`"Duplo KO" if result.reason == "double_ko"`).
- **O defeito:** (a) um `double_ko` chega sem `winner` (os dois mortos; `headless.py:193-203`) e é tratado como empate → refeito com outro seed; quando por fim há vencedor, `reason` já não é `double_ko`. O rótulo "Duplo KO" é inalcançável e, se alcançado, contaria como KO em `stats["total_kos"]` (`"KO" in ko_type`). (b) O retry da luta `k` usa `seed + k + 1`, que é exatamente o seed inicial da luta `k + 1`: duas lutas do mesmo torneio podem rodar com o mesmo seed, o que enfraquece a "tentativa determinística" prometida na mensagem de erro.
- **Quando acontece:** (a) nunca produz saída errada hoje, é só código morto enganoso; (b) sempre que uma luta empata.
- **Prova:** por leitura das linhas citadas e de `headless.py:189-203` (`winner_slot=simulator.vencedor_round_side`; o `double_ko` vem de `p1.morto and p2.morto`).
- **Conserto sugerido:** `attempt_seed = seed + match_id * (retry_limit + 1) + attempt` (ou um espaço de seeds por luta); tratar `double_ko` com vencedor como empate explícito e remover o rótulo.

### 10. CLIs aceitam argumentos inválidos em silêncio (menores)

- **Onde / o que:**
  - `timeline.py:2619` — `--camera` é texto livre (`--camera foo` aceito; o gravador oficial restringe a `CAMERAS` em `fight_recorder.py:799`). `--resolucao 1080` (sem `x`) dá `ValueError` com traceback em `:2634`.
  - `fight_recorder.py:788-789` — `--crf` e `--preset` sem validação: o erro vira o `BrokenPipeError` do item 1 em vez de "preset inválido".
  - `skill_demo.py:109-121` — `--skill "Nao Existe"` é tratado como "skill sentinela" (o `derivar_contrato` de nome desconhecido devolve tipo `NADA`); a mensagem esconde o erro de digitação.
  - `live.py:99-100` — `--roster` e `--max-partidas` aceitam 0 e negativos (ver item 5).
- **Prova:** `timeline.build_parser().parse_args([... "--camera", "foo"])` → `foo`; `skill_demo --skill "Nao Existe" --sem-video` → `FALHA Nao Existe: skill sentinela`, exit 1.
- **Conserto sugerido:** `choices=CAMERAS` e `type=` com validação (`parse_resolucao` já existe em `fight_recorder.py:452` e devolve `None` para entrada ruim — usá-lo nas duas CLIs); em `skill_demo`, `if nome not in SKILL_DB: erro "skill desconhecida"`.

### 11. Funções públicas sem chamador (candidatas a remoção)

Por `grep` em todo o repositório (fora de `tests/`): `utils/__init__.py` — `random_range`, `random_color_variation`, `rotate_point`, `angle_between`, `normalize_vector`, `ease_out`, `ease_in_out` (as duas aleatórias usam o `random` global: se um dia entrarem no motor, quebram o determinismo); `utils/palette.py` — `hex_to_rgb`; `utils/fonts.py` — `limpar_cache`; `tournament_mode.py` — `Tournament.add_participant` (só o `__main__` do próprio arquivo), `TournamentRunner.run_single_match_visual`, `TournamentRunner._default_weapon` (arma inventada que ninguém usa); `timeline.py` — `definir_remapeamento` (o palco escreve `doc["remapeamento"]` direto: `random_builds/builds/palco/cli.py:143,194,267`); `timeline_arquivo.py` — `flags_ligadas`, `duracao_do_clipe`, `tempo_no_clipe`, `tempo_na_gravacao`, `ler_gcpf` (só via `carregar`); `cli/headless.py` — `HeadlessBattle`/`executar_teste_stress` (só `ferramentas/diagnostico/test_headless_battle.py`). `Tournament._adjust_to_power_of_two` (`:196-210`) tem um ramo "trunca para `power // 2`" inalcançável: `n > power // 2` é sempre verdadeiro quando `power` é a próxima potência de 2.

## Não confirmados

- **Determinismo da gravação e da timeline** (`fight_recorder.py:568`, `timeline.py:2535-2536`): `Simulador(seed=…)` + `AnotadorDeAudio(seed=…)`; as sondas só leem; `gravar_timeline` zera o animador de arma (`_zerar_animador_de_arma`) e `gravar_luta` não, mas o gravador roda uma luta por processo (`capture.py`) e `qualidade_luta.py` é a única que chama `gravar_luta` repetidamente no mesmo processo (afetaria só os canais `anim_fase/anim_p`, visuais). A suíte `tests/test_timeline_palco_regressions.py` compara hash por passo com e sem sonda. Não vi caminho que quebre; não re-provei.
- **`hash_estado` entre processos** (`timeline.py:2289-2294`): a docstring diz que `hash(getstate())` é estável entre processos; a tupla contém `None`, cujo `hash` só é constante desde o Python 3.12. Esta máquina roda 3.14.4, então vale; em 3.11 a comparação cruzada falharia.
- **Alinhamento som/quadro** (`fight_recorder.py:624-628`): `t_video` é fixado antes do `update` e é o do quadro que captura o passo; conferido passo a passo (passo ímpar recebe o `t` do quadro seguinte), coerente com `docs/palco/sons.md`. OK.
- **Contagem de quadros/duração** (`:621, :680`): `t_video = capturados / fps` antes da captura, `duracao_video = capturados / fps`; com `max_duracao=120` e fps 30 saem exatos 3600 quadros. Sem off-by-one. O `ko_em_video` e a cauda de 3,5 s batem.
- **`validar` do `timeline_arquivo`** numa timeline real gravada pelo gravador (`.gcpf`, zstd): lista vazia de problemas, `n=179`, `quadros=90`, `sons=21`. O container GCPF abre no Python; o Godot foi conferido pela própria 16C.
- **Torneio com ímpar/BYE/save**: 3, 5, 6 e 7 participantes chegam ao campeão sem luta contra `BYE_n` nem `TBD`; save/load de um torneio terminado com BYEs e `ko_type="Decisão por HP"` volta com o mesmo campeão. Um participante real chamado `BYE_1` é respeitado (o sentinela gerado vira `BYE_2`). Ranking não existe nesta fatia (não há ordenação instável a checar).
- **`run_tournament_automated` com `continue` em luta de BYE** (`tournament_mode.py:1403-1406`): seria laço infinito se uma luta de BYE chegasse pendente ao ponteiro, mas `_process_byes` as fecha antes (`:343`, `:458`) e o `load_state` exige o ponteiro na primeira pendente. Só um save montado à mão chegaria lá.
- **`cli/headless.py` com argumento inválido**: `--p1 "Nao Existe"`, `--stress-count 0` e `--fixed-dt 0` devolvem JSON com `success: false` e exit 1 (a validação mora em `simulation/headless.py:56-72`). OK.
- **Caminho com espaço**: `capture.py` passa `str(Path(saida))` como argumento próprio de `subprocess.run` (lista, sem shell); `_abrir_ffmpeg` idem; `tournament_mode.launch_simulation` usa lista. Não há concatenação em string de comando.
- **`_recorte_util`** (`fight_recorder.py:334-371`) e `parse_resolucao` (`:452-466`): dimensões sempre pares, `None` quando não há o que aparar; `"1080X1920"` aceito. OK.
- **`console._texto_compativel`** (`console.py:9-13`): `backslashreplace` é reversível e não levanta; só falharia com um nome de codificação que o Python não conhece (`LookupError`), improvável para `sys.stdout.encoding`.
- **`palette.get_element_from_skill`** (`palette.py:159`): a heurística `"tempo"` casa com "tempestade" quando a skill não tem campo `elemento`; só vale para skill sem o campo (90/109 têm) e o timeline usa `resolver_elemento`, que prefere o objeto. Cosmético.
