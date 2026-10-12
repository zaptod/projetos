# Auditoria profunda — App do celular: servidor e ações — 11/10/2026

Fatia: `remoto/api_http.py`, `remoto/acoes.py`, `remoto/comandos_app.py`, `remoto/vila_nova.py`,
`remoto/biblioteca.py`, `remoto/painel_dados.py`, no HEAD `e8cc338` (12/10, 18h). Nada do projeto
foi alterado. Provas rodadas em `E:\tmp_pytest\prova_remoto_api\` com `LOCALAPPDATA` e
`NEURAL_FIGHTS_RUNTIME_DIR` apontando para lá (o `remoto/config.runtime_dir` só lê
`LOCALAPPDATA`), servidor no loopback com porta escolhida pelo sistema, sem navegador, sem rede,
sem a 8931 e sem tocar `%LOCALAPPDATA%\neural-fights`. Os scripts ficaram em
`C:\Users\adrian\AppData\Local\Temp\claude\e--projetos\65fe1aa9-…\scratchpad\auditoria2\provas_api\`.
Nenhuma prova dubla a função sob suspeita: os dublês são o processo filho, o subprocesso da
previsão, o catálogo de vídeos e o disco temporário.

## Examinado

- `api_http.py` — 108 funções e 4 classes lidas (2.700 linhas): o servidor HTTP do app (trancas de
  rede/Host/token, pareamento, bilhetes de vídeo e de página, 60+ rotas GET/POST, trava de arquivo
  entre threads e processos, CLI `--parear/--esquecer/--em-voo/--liberar/--soltar-marca`).
- `acoes.py` — 78 funções e 2 classes (1.331 linhas): as ações do app (dois passos, guardas de
  publicação, marca "a conferir", em-voo, filha desligada, vigia, desfechos, limites por hora,
  rastro, fila de avisos ao Telegram, `Pendentes`).
- `comandos_app.py` — 14 funções (495 linhas): o catálogo declarativo (validação, zona de perigo,
  guardas, montagem da linha de comando, execução por tarefa). As 22 linhas de comando montadas
  foram conferidas flag a flag contra `random_builds/main.py`, `historias/main.py`,
  `ferramentas/postar.py`, `curar_ledger.py`, `conciliar_tiktok.py`, `remoto.limpar_espelho` e
  `neural_fights.tools.gerador_database`: todas existem com o nome usado.
- `vila_nova.py` — 20 funções e 1 classe (452 linhas): fundo/retrato/paisagem/atlas em cache, o
  motor da vida da Vila numa thread que dorme sem pedido, o enquadramento pela decisão.
- `biblioteca.py` — 25 funções (381 linhas): registro atômico de itens, fontes automáticas,
  leitura de Markdown e páginas só dentro das raízes permitidas, marcações por página.
- `painel_dados.py` — 24 funções e 3 classes (377 linhas): o filtro `limpar`, estado/diário/
  erros/vídeos para o app, cache de relatórios, previsão e fluxo em segundo plano.

Também lidos para seguir os contratos: `remoto/tarefas.py`, `remoto/publicacao_filha.py`,
`remoto/config.py`, `builds/atividade._vivo`, `painel/flutuante/vida.Vida`, `previsao.main`,
`conftest.py`, `testar.py`, e os fixtures de `test_api_http.py`, `test_acoes.py`,
`test_biblioteca.py`.

## Confirmados (do mais grave ao menos)

### 1. Parear fica bloqueado por 10 min por erros que não são chute — gravidade: alta
- Onde: `api_http.py:1442` (`_post`, rota `/api/parear`), `api_http.py:1032` (`_barrar_chute`),
  `api_http.py:911` (`Estado.bloqueado`), `api_http.py:2298` e `2395` (`/v/` e `/p/`).
- O defeito: o contador de falhas é por IP, e atrás do `tailscale serve` todo pedido chega de
  `127.0.0.1`. O docstring do `_barrar_chute` diz que o bloqueio "só pesa sobre quem NÃO tem token
  válido" — e é exatamente quem precisa do `/api/parear`. Qualquer 20 falhas de qualquer origem em
  10 min fecham o pareamento para o celular novo, com o código certo na mão; o código continua
  válido no disco e ninguém entra. Duas origens reais, não chutes:
  (a) um aparelho esquecido (decisão `o-aparelho-pareado-em-17-09-ainda-e-seu` → esquecer) ou
  qualquer processo local com token velho; (b) **toda vez que o coordenador reinicia o app**
  (`python -m coordenador reiniciar app`, a cada entrega), os bilhetes `/v/…` que a tela ainda
  tem (galeria, conversa com imagens, vídeo pausado) viram "inventado" — a memória `vencidos` que
  existe para não contar o vídeo parado morre com o processo — e cada um conta como chute.
- Quando acontece: 20 × `GET /api/estado` com token velho → 401; em seguida `POST /api/parear`
  com código recém-gerado → 429. Ou: servidor A emite 20 bilhetes, reinicia como B, a tela pede
  os 20 `/v/` (404) → `/api/parear` 429, enquanto o token do celular já pareado segue 200.
- Prova: `p1_parear_429.py` → `20 consultas com token velho: [401]` /
  `parear com o codigo certo: (429, '{"erro": "tentativas demais; espere alguns minutos"}')` /
  `pareamento no disco ainda pendente: True`. `p1b_restart_bilhetes.py` →
  `bilhetes validos antes do reinicio: 206` / `os mesmos /v/ depois do reinicio: [404]` /
  `token valido continua ok: 200` / `parear um 2o celular com codigo certo: (429, …)`.
- Conserto sugerido: contar o `/api/parear` num balde próprio (só erros de código, que já morrem
  em 5) e não contar bilhete desconhecido logo após a subida (ou persistir `vencidos`).

### 2. `--parear`/`--esquecer` falham e o celular pareado perde o token enquanto o app consulta — gravidade: média
- Onde: `api_http.py:647` (`gravar_config`, `os.replace`), `api_http.py:635` (`ler_config`,
  `except OSError → {}`), `api_http.py:732` (`aparelho_do_token`, lê o arquivo a cada pedido, sem a
  trava), `remoto/app/app.js:143` (401 → `localStorage.removeItem(TOKEN)`).
- O defeito: no Windows o `os.replace` falha com `PermissionError` enquanto outro processo/thread
  tem o mesmo arquivo aberto para leitura; o servidor abre `app_celular.json` em TODO pedido
  autenticado (1/s pela Vila). Dois lados: o escritor (`--parear`, `--esquecer`, `trocar_codigo`)
  cai com traceback — no servidor, `trocar_codigo` sem resposta (ver item 5); e a leitura que cai
  no meio da troca devolve `{}` (sem aparelhos) → o token VÁLIDO vira 401 → a casca apaga o token
  e o celular tem de parear de novo (e o 401 ainda conta no balde do item 1).
- Quando acontece: um `--parear`/`--esquecer` rodado com o app aberto no celular.
- Prova: `p5_replace_vs_leitor.py` (4 threads lendo `ler_config`, escritor sob `_trava_config`
  por 4 s) → `gravacoes: 9, falhas do escritor (os.replace): 2521 | PermissionError: [WinError 5]
  Acesso negado: '…app_celular.tmp' -> '…app_celular.json'` e `leituras: {'ok': 28625,
  'vazias': 40}`. As 40 "vazias" são leituras com o arquivo existindo e `aparelhos == []`.
- Conserto sugerido: ler a config pela mesma `trava_arquivo` (ou guardar em memória e reler só
  quando `st_mtime_ns` mudar), e tentar o `os.replace` de novo por alguns ms em `PermissionError`.

### 3. Publicação cuja filha morreu antes de nascer o `main.py` fica presa no em-voo para sempre — gravidade: média
- Onde: `acoes.py:1099` (`situacao_da_filha`), `acoes.py:1127` (`_vigia`, `sumiu`),
  `acoes.py:1178` (`_pode_soltar`), `acoes.py:1194` (`liberar`).
- O defeito: `filho` só é `False` com `fim.json` presente; sem `filho.json` e sem `fim.json` ele é
  `None`. A vigia só conclui com `filha is False and filho is False`, então espera as 6 h de
  `ESPERA_MAX_S` e marca "a_conferir"; depois disso o `--liberar` (e o controle "Liberar vídeo
  travado" do catálogo) recusa para sempre com "o main.py dessa publicação ainda pode estar
  rodando". A filha está comprovadamente morta (PID + hora de nascimento) e nunca registrou filho:
  o `main.py` não pode existir. Enquanto isso `video_para_publicar` recusa qualquer publicação do
  app naquele destino ("outra publicação do app … confira e libere antes"). Só sai editando
  `app_celular_em_voo.json` à mão.
- Quando acontece: a filha (`python -m remoto.publicacao_filha`) morre no import/argparse, antes
  do `rodar()` — por exemplo com o `remoto/` meio velho/meio novo durante uma entrega aplicada
  (memória de 07/10), ou morta pelo `taskkill /t` de uma religada antes de abrir o `main.py`.
- Prova: `p3_liberar_preso.py` (filha real que nasceu e morreu, pasta sem `filho.json`/`fim.json`)
  → `situacao_da_filha: {'terminou': False, 'filha': False, 'filho': None}` /
  `a vigia a da por 'sumiu'? False (so conclui depois de ESPERA_MAX_S = 21600 s)` /
  `liberar RECUSA: não solto generation_00001:celular: o main.py dessa publicação ainda pode estar
  rodando` — e o mesmo com o item já em `a_conferir`.
- Conserto sugerido: em `situacao_da_filha`, filha morta de verdade E sem `filho.json` = `filho =
  False` (ela escreve o `filho.json` antes de qualquer outra coisa); e `--liberar --forcar` para a
  conferência humana.

### 4. A guarda "já tem X rodando" não vê tarefa viva atrás de 40 mais novas — gravidade: média
- Onde: `comandos_app.py:313` (`guardar` → `tarefas.rodando(nome)`), `api_http.py:1597`
  (`_arena_luta` → `tarefas.rodando("arena")`); a causa em `remoto/tarefas.py:128-131`
  (`rodando` = `listar(40)` filtrado, e `listar` corta pelas 40 pastas de nome mais novo).
- O defeito: a guarda que impede dois "Escoar a fila", dois "Publicar história" ou dois renders
  da Arena ao mesmo tempo olha só as 40 tarefas mais recentes. Uma tarefa longa (escoar, gerar
  história de 40 min) com 40 tarefas mais novas na pasta (cada luta da Arena é uma; a pasta guarda
  7 dias) fica invisível e o mesmo comando sobe de novo em paralelo — no mesmo perfil de Chrome.
- Quando acontece: pasta `app_celular_tarefas` com uma `escoar` viva e 40 pastas mais novas.
- Prova: `p10_rodando_top40.py` → `sozinha, rodando('escoar') = ['20261001-000000-aaaaaa']`;
  com 40 pastas mais novas terminadas: `uma('…aaaaaa')['situacao'] = rodando` e
  `rodando('escoar') = []`.
- Conserto sugerido: `rodando()` percorrer todas as pastas (ou todas sem `fim.json`), não `listar(40)`.

### 5. POST que explode sai sem resposta nenhuma (o `_post` não tem o `except Exception` do `_get`) — gravidade: média
- Onde: `api_http.py:1379` (`_post`, nenhuma rota POST está dentro de `try/except Exception`);
  exemplos concretos em `api_http.py:1626` (`e_perigosa(nome, args)` com `args` que não é dict →
  `comandos_app.py:289 args.get`) e `api_http.py:2176` (`(corpo.get("anexos") or [])[:4]` com
  dict). Outros candidatos pelo mesmo caminho: `trocar_codigo` em `PermissionError` (item 2),
  `_arena_luta` com `p1` lista (unhashable), `_responder_decisao`/`_equipe` em exceções fora de
  `Recusa/OSError/KeyError`.
- O defeito: o `_get` responde `500 {"erro": "<Tipo>"}` a qualquer exceção; o `_post` deixa a
  exceção subir, o `handle_error` imprime o traceback e a conexão fecha sem status. A casca vê
  "Failed to fetch", sem motivo, e o log ganha um traceback por toque.
- Quando acontece: `POST /api/acao {"acao":"curar_ledger","args":"gravar"}` ou
  `POST /api/correio/chatgpt {"texto":"oi","anexos":{"b64":"x"}}` com token válido e `--acoes`.
- Prova: `p4_post_sem_resposta.py` → `args='gravar'-> (None, 'RemoteDisconnected: Remote end
  closed connection without response')`, `anexos={} -> (None, 'RemoteDisconnected…')`,
  `tracebacks no log do servidor: 2`, `["AttributeError: 'str' object has no attribute 'get'",
  'KeyError: slice(None, 4, None)']`. (`args: []` passa porque `[] or {}` vira `{}`.)
- Conserto sugerido: envolver o despacho do `_post` no mesmo `try/except Exception → _erro(500)`
  do `_get`, e validar `isinstance(args, dict)` antes do `e_perigosa`.

### 6. O token do aparelho viaja dentro de uma URL (vídeo da Arena) — gravidade: média
- Onde: `api_http.py:1128` (`/api/arena/lutas` monta `video_url=…?t=<token>`), `api_http.py:1059`
  (`_aparelho_do_video_da_arena` aceita `?t=`).
- O defeito: o docstring do módulo (linha 28) e a tranca 3 dizem que "o token nunca aparece em URL
  (histórico do navegador, captura de tela)"; todas as outras mídias usam bilhete de 10 min para um
  arquivo. A Arena devolve o token permanente em texto, numa URL que o `<video>` guarda no
  histórico/cache do Chrome e que vale para TODA a API, não só para aquele mp4. Quem vê a URL (tela
  compartilhada, DevTools, cache do service worker) vira o celular.
- Quando acontece: qualquer `GET /api/arena/lutas` com uma luta pronta.
- Prova: `p6_token_na_url.py` → `status: 200 | token inteiro dentro da URL? True` /
  `a URL sem Authorization serve o video? 206`.
- Conserto sugerido: a Arena usar `self.estado.bilhete(arquivo, self._dono)` e `/v/`, como o
  `/api/video/...`; apagar o caminho `?t=`.

### 7. Campo de texto começando com `-` passa na validação e derruba o comando — gravidade: baixa
- Onde: `comandos_app.py:202` (`_TEXTO_OK` aceita `-` em qualquer posição), `comandos_app.py:383`
  e `396` (`montar` põe o valor logo depois de `--tema`/`--p1`/`--p2`).
- O defeito: `--p1 -x` faz o argparse do `main.py duelo` ler `-x` como opção ("expected one
  argument") e sair com 2; a tarefa sobe, falha na hora e o celular vê "falhou" sem saber por quê.
  Mesmo com `--tema` de `gerar_historia` (`"-"` ou `"--help"`).
- Quando acontece: `duelo` com `p1: "-x"`, ou `gerar_historia` com `tema: "- ideia"`.
- Prova: `validar("duelo", {"p1": "-x", "p2": "--palco"})` → `{'p1': '-x', 'p2': '--palco'}`;
  `montar` → `[…, '--p1', '-x', '--p2', '--palco']`; um `ArgumentParser` com a mesma definição de
  `--p1/--p2/--palco` do `main.py duelo` → `error: argument --p1: expected one argument`, código 2.
- Conserto sugerido: recusar valor que começa com `-` no `_validar_campo`, ou montar com `--p1=…`.

## Não confirmados

- **Previsão presa em "calculando" até reiniciar** (`painel_dados.py:278-293`, `_Previsao._calcular`):
  se o subprocesso imprimir um JSON válido que não é objeto, a exceção (`AttributeError`) não está no
  `except`, a thread morre e `_rodando` fica `True` para sempre — `ler()` nunca recalcula. O mecanismo
  foi provado com o subprocesso dublado (`p2_previsao_presa.py`: `thread de calculo viva? False |
  _rodando = True`, três leituras seguintes `{'calculando': True}` mesmo com `PREVISAO_VALE_S = 0`).
  Não entra nos confirmados porque `painel.flutuante.previsao.main` só escreve `json.dumps(dados)`
  com `dados` dict: hoje não há entrada real que dispare. Vale um `except Exception` e um `finally`
  que solte `_rodando`.
- **"Falhou" na tela com a publicação rodando** (`acoes.py:957`, `_disparar_publicacao`): se o
  `_mexer_no_voo(chave, pid=…)` levantar DEPOIS de a filha nascer (disco cheio, trava estourada por
  outro processo), a exceção sai do `with`, `confirmar` responde `falhou: OSError`, o item fica
  `em_andamento` sem `pid` e `vigiar(chave)` não é chamado — só a `conciliar()` do próximo reinício
  retoma. A marca "a conferir" está posta, então não reposta. Não provei: exigiria encher o disco ou
  dublar a própria gravação.
- **`ler_config` com `aparelhos` que não é lista** (`api_http.py:635`, `trocar_codigo:690 .append`,
  `aparelho_do_token:737`): arquivo corrompido à mão derruba `/api/parear` sem resposta
  (`AttributeError`) e o `--aparelhos`. Só com edição manual do JSON; não é entrada do sistema.
- **`Motor.retrato` lê `self._vida.habitantes` enquanto `_girar` o muda** (`vila_nova.py:400`): não
  dá `RuntimeError` porque `Vida.__init__` é o único lugar que acrescenta habitantes; a leitura pode
  ver uma pose de meio-tick, sem efeito. Descartado.
- **`_corpo` com `Content-Length` maior que o corpo** (`api_http.py:1371`) prende a thread por
  `TIMEOUT_S` (15 s); com `CONEXOES_MAX = 32`, 32 dessas fecham o servidor por 15 s. É o desenho
  (timeout + teto) e só do tailnet; não conta como defeito.
- **Confirmação não reconfere `--publicar`/`--perigosas`** (`api_http.py:1639`): não é defeito — as
  chaves são do processo e o pedido pendente nasceu nele.
- **`e_perigosa` antes de validar, com `gravar: "false"` (string)** (`api_http.py:1626`,
  `comandos_app.py:219 bool(bruto)`): a string viraria `True` e o `--gravar` rodaria. A casca manda
  `entrada.checked` (booleano, `comandos.js:123`), então hoje não dispara; latente para outra casca.
