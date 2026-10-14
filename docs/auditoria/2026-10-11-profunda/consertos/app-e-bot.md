# Consertos — app-e-bot (verificação de 14/10/2026)

- **Parte:** app-e-bot (app do celular e bot do Telegram)
- **Relatórios de origem:** `app-celular.md` (12 itens), `remoto-api.md` (7), `remoto-bot.md` (14)
- **Contagem:** 33 abertos / 0 consertados / 0 falsos
- **Conferido em:** HEAD `f670aa9` (ramo `refactor/arquitetura`). Nenhum commit depois dos relatórios mexeu nestes defeitos: `a34b355` só acrescentou `--saida` ao `__main__` de `api_http.py` e `remoto/__main__.py`; `bc41a2a` e `b71f02e` são anteriores ao relatório do bot, que já os descontou.
- **Conserto já escrito, mas não mesclado:** a worktree do Codex `E:\projetos-wt\codex-pedido-c7e0c0d9` tem um diff preparado (não commitado) que cobre os itens APP-6 a APP-17 (os 12 do `app-celular.md`), com testes. Aplicar essa entrega pelo integrador deve ser o primeiro passo desses itens, depois de conferir a tela no Chrome 390x844. O ramo `worktree-agent-ac362a0bfcc5f30f8` troca só a assinatura do bot em `coordenador/servicos.json` (parte do APP-8).

Gravidade: nada aqui perde dado de produção nem publica errado. Os avisos do Telegram que se perdem (APP-12, APP-13) são dado passageiro e ficaram em **médio**.

---

### APP-1 — Em-voo da publicação preso, ou `fim.json` escrito com o `main.py` ainda vivo  (médio)
- **Onde:** `remoto/publicacao_filha.py:70-88` (`rodar`); `remoto/acoes.py:1099` (`situacao_da_filha`), `acoes.py:1178` (`_pode_soltar`), `acoes.py:1127` (`_vigia`)
- **Defeito:** (a) se gravar o `filho.json` falha, o `except` pula o `filho.wait()` e o `fim.json` sai na hora, com o `main.py publicar` ainda rodando; (b) quando a filha morre antes de abrir o `main.py`, nunca existe `filho.json` nem `fim.json`, então `filho` fica `None` para sempre. A vigia espera 6 h e o `liberar` recusa para sempre. O app fica bloqueado naquele destino até alguém editar `app_celular_em_voo.json` à mão.
- **Conserto:**
  1. Em `publicacao_filha.rodar`, gravar antes do `Popen` um `filho.json = {"pid": null, "fase": "abrindo"}`. Depois do `Popen`, gravar o `filho.json` com o pid num `try` só dele: se falhar, escrever uma linha no `saida.log` e seguir. O `codigo = filho.wait()` roda sempre que o `Popen` deu certo, e o `fim.json` só é escrito depois que o `wait()` volta.
  2. Em `situacao_da_filha`: sem `filho.json`, sem `fim.json` e com a filha morta de verdade (`filha is False`), devolver `filho = False`, porque a filha nem chegou ao `Popen`. Se o `filho.json` tem `pid: null` e a filha está morta, `filho` continua `None` (não dá para saber).
  3. Acrescentar `--liberar --forcar` em `acoes.liberar`/CLI. Ele solta mesmo com `filho None`, depois que o Adrian confirmou no canal, e escreve isso no diário.
- **Teste que prova:** em `remoto/test_acoes.py`:
  - `test_filha_morta_sem_filho_json_solta`: pasta sem `filho.json` e sem `fim.json`, com o pid de um processo já encerrado. Espera `situacao_da_filha(...)["filho"] is False` e `_pode_soltar(item) == ""`. Hoje dá `None` e a recusa "ainda pode estar rodando".
  - `test_filho_json_que_falha_nao_escreve_fim_antes_do_wait` (em `remoto/test_remoto.py` ou num `test_publicacao_filha.py` novo): criar `filho.tmp` como pasta e rodar `rodar()` com o comando `python -c "import time; time.sleep(2)"`. `rodar()` só pode voltar depois de cerca de 2 s, e o `fim.json` tem que ter `codigo == 0`. Hoje volta em cerca de 0,02 s com `codigo None`.
- **Origem:** `remoto-api.md` #3, `remoto-bot.md` #2

### APP-2 — Parear fica bloqueado 10 min por falhas que não são chute  (médio)
- **Onde:** `remoto/api_http.py:1442` (`_post`, rota `/api/parear`), `api_http.py:1032` (`_barrar_chute`), `api_http.py:911/919` (`Estado.bloqueado/falhou`), `api_http.py:833` (`vencidos` só em memória)
- **Defeito:** o `/api/parear` consulta o mesmo balde por IP (todo pedido chega como `127.0.0.1`) que conta os 401 de token velho e os bilhetes `/v/` desconhecidos depois de uma religada. Com 20 falhas, o celular novo, mesmo com o código certo, leva 429.
- **Conserto:** criar `Estado.falhas_parear` separado. O `/api/parear` só consulta e alimenta esse balde, só com código errado (403). O `_barrar_chute` continua com `falhas`. Além disso, durante `BILHETE_VALE_S` depois da subida do servidor (`Estado.subiu_em`), um `/v/` ou `/p/` "inventado" responde 404 sem chamar `estado.falhou`.
- **Teste que prova:** `remoto/test_api_http.py::test_parear_nao_bloqueia_por_token_velho`: 20 `GET /api/estado` com token velho (401). Depois, `novo_codigo()` e `POST /api/parear` com esse código. Espera 200 com `token`; hoje vem 429. E `test_bilhete_de_antes_da_subida_nao_conta_chute`: 25 `GET /v/<inventado>` logo depois de criar o servidor e em seguida `POST /api/parear` com código válido, que deve dar 200.
- **Origem:** `remoto-api.md` #1

### APP-3 — `--parear`/`--esquecer` com o app aberto: o escritor cai e o leitor vê zero aparelhos  (médio)
- **Onde:** `remoto/api_http.py:647` (`gravar_config`), `api_http.py:635` (`ler_config`), `api_http.py:732` (`aparelho_do_token`)
- **Defeito:** o `os.replace` falha com `PermissionError` enquanto o servidor lê o arquivo (1 vez por segundo). Uma leitura que cai no meio devolve `{}`, o token válido vira 401 e o celular apaga o token e precisa parear de novo.
- **Conserto:** (1) `gravar_config`: até 10 tentativas do `os.replace` a cada 50 ms em `PermissionError`; se todas falharem, apagar o `.tmp` e relançar. (2) `ler_config`: em `PermissionError`, tentar de novo 3 vezes a cada 50 ms, e não devolver `{}` enquanto o arquivo existir. (3) `aparelho_do_token`: guardar em memória a última config lida com sucesso, chaveada por `st_mtime_ns`. Se a leitura falhar com o arquivo existindo, usar o cache. Nunca tratar "não consegui ler" como "sem aparelhos".
- **Teste que prova:** `remoto/test_api_http.py::test_token_valido_sobrevive_a_gravacao_concorrente`: 4 threads chamando `aparelho_do_token(token_valido)` enquanto outra thread chama `gravar_config` 200 vezes. Espera zero `None` e zero exceção no escritor. Hoje dá dezenas de `None` e `PermissionError` no Windows.
- **Origem:** `remoto-api.md` #2

### APP-4 — Guarda "já tem X rodando" só olha as 40 tarefas mais novas; tarefa sem filha fica "rodando" para sempre  (médio)
- **Onde:** `remoto/tarefas.py:128` (`rodando`), `tarefas.py:57-79` (`iniciar`), `tarefas.py:83-97` (`_estado`), `tarefas.py:160` (`limpar_velhas`)
- **Defeito:** `rodando()` filtra `listar(40)`, então uma tarefa viva atrás de 40 pastas mais novas some e o mesmo comando sobe em paralelo. E, se `_iniciar_filha` levanta, o `tarefa.json` fica sem `pid` e a tarefa aparece "rodando" para sempre: bloqueia o comando, aparece no resumo e nunca é limpa.
- **Conserto:** (1) `rodando()` percorre todas as pastas de `pasta_das_tarefas()` que não têm `fim.json` (não usa `listar`). (2) Em `iniciar`, envolver `acoes._iniciar_filha` em `try/except Exception as exc`: gravar `fim.json = {"codigo": None, "erro": f"não subiu: {exc}", "fim": agora}` na pasta e relançar. (3) Em `_estado`, uma ficha sem `pid`, sem `filho.json` e com `inicio` de mais de 60 s vira `"sumiu"`.
- **Teste que prova:** em `remoto/test_comandos_app.py` (ou num `test_tarefas.py` novo), com `tarefas.PASTA` temporária:
  - uma pasta `escoar` viva (pid do próprio teste e `criado` certo) e 40 pastas mais novas terminadas: `rodando("escoar")` precisa ter 1 item (hoje 0);
  - `_iniciar_filha` dublado levantando `OSError`: depois de `iniciar`, `uma(chave)["situacao"] != "rodando"` e `rodando("gerar_historia") == []`.
- **Origem:** `remoto-api.md` #4, `remoto-bot.md` #8

### APP-5 — Token permanente do aparelho dentro da URL do vídeo da Arena  (médio)
- **Onde:** `remoto/api_http.py:1128` (`/api/arena/lutas`), `api_http.py:1059` (`_aparelho_do_video_da_arena`)
- **Defeito:** o `video_url` leva `?t=<token>`, e esse token vale para a API inteira. Contraria a tranca 3 do módulo ("o token nunca aparece em URL").
- **Conserto:** em `/api/arena/lutas`, usar `self.estado.bilhete(arquivo, self._dono)` e devolver `video_url = "/v/<bilhete>"`, como o `/api/video/...` já faz. Apagar o caminho `?t=` de `_aparelho_do_video_da_arena`, que passa a aceitar só o `Authorization`, e remover a rota se ninguém mais a usar. `remoto/app/app.js:657` não muda.
- **Teste que prova:** `remoto/test_arena.py::test_video_da_arena_sem_token_na_url`: `GET /api/arena/lutas` com uma luta pronta; espera que `token not in luta["video_url"]` e que a URL comece com `/v/`. Depois, `GET /api/arena/video/<id>.mp4?t=<token>` sem cabeçalho tem que dar 401/404 (hoje dá 206).
- **Origem:** `remoto-api.md` #6

### APP-6 — Com o PC fora, a faixa de aviso cobre as abas do objeto aberto  (médio)
- **Onde:** `remoto/app/app.css:231` (`body.pareado .aviso`), contra `.livro` (`app.css:308`) e `.abas-objeto` (`app.css:639`)
- **Defeito:** a faixa fixa (z-index 21, top 50px) fica exatamente sobre a fileira de abas do objeto. Quando o PC não responde, o toque cai no "Tentar de novo" e não na aba.
- **Conserto:** acrescentar `body.pareado.objeto-aberto .aviso { top: calc(<altura do cabeçalho + fileira de abas>px + env(safe-area-inset-top)); }`, de modo que a faixa fique abaixo das abas, ou empurrar o `padding-top` do `.livro` quando `#aviso` estiver visível. Subir a `CASCA` do `sw.js`. A worktree `codex-pedido-c7e0c0d9` usa `top: 120px`: conferir na captura.
- **Teste que prova:** `remoto/test_app_tela.py` (com `NF_TESTE_NAVEGADOR=1`): abrir Agora, derrubar o servidor e esperar a faixa. Depois, `page.locator(".abas-objeto button").nth(1).click(timeout=3000)` precisa trocar a aba. Hoje estoura com "subtree intercepts pointer events".
- **Origem:** `app-celular.md` #1

### APP-7 — Service worker guarda para sempre cada versão das imagens da Vila  (baixo)
- **Onde:** `remoto/app/sw.js:33`
- **Defeito:** todo GET 200 fora de `/api/` e `/v/` entra no cache `painel-casca-*`, incluindo os fundos e o atlas versionados. São cerca de 3 MB a mais por arte salva no Ateliê, e nada disso sai.
- **Conserto:** no `fetch`, calcular `caminho = url.pathname === "/" ? "./" : url.pathname.slice(1)` e só chamar `c.put` quando `ARQUIVOS.includes(caminho)`. O resto fica em rede pura, e o `max-age` do servidor já cobre. Subir a `CASCA`.
- **Teste que prova:** `remoto/test_app_modulos.py::test_sw_so_guarda_a_casca`: ler o `sw.js` e afirmar que o `c.put` está condicionado a `ARQUIVOS.includes(`. Opcionalmente, com navegador: depois de carregar a Vila, `caches.open(CASCA)` não pode ter nenhuma chave com `vilanova-`.
- **Origem:** `app-celular.md` #2

### APP-8 — Religada do bot vira "já tem um bot no ar" (trava sem espera, linha sem hora, assinatura larga)  (médio)
- **Onde:** `remoto/__main__.py:147-149` (`ligar`), `coordenador/servicos.json:20` (assinatura do serviço `bot`)
- **Defeito:** o bot novo pede a trava com `esperar=0.0` enquanto o antigo ainda solta o handle. Ele sai com uma linha sem hora, e o coordenador conta "caiu: processo ausente". A assinatura `-m\s+remoto(?:\s|$)` também casa `python -m remoto --avisar/--apurar/--testar-conserto`.
- **Conserto:** `travas.trava("remoto__bot", esperar=15.0)`; a linha de saída passa por `carimbar(...)`. Assinatura em `servicos.json`: `-m\s+remoto(?!\S)(?!.*--(?:avisar|apurar|status|esquecer|instalar|desinstalar|testar-conserto)\b)`, a mesma já escrita no ramo `worktree-agent-ac362a0bfcc5f30f8`; trazer só essa linha.
- **Teste que prova:** `remoto/test_remoto.py::test_ligar_espera_a_trava_do_antigo`: segurar a trava `remoto__bot` numa thread por 2 s, chamar `ligar()` com `Bot` dublado e afirmar que `Bot().rodar` foi chamado (hoje sai na hora). E, em `coordenador/test_*.py`, a regex da assinatura não pode casar `python -m remoto --avisar "x"` nem `-m remoto --apurar`, e tem que casar `-u -X utf8 -m remoto`.
- **Origem:** `remoto-bot.md` #5

### APP-9 — Sem rede, o laço do bot gira sem dormir e remonta o relatório vencido a cada volta  (médio)
- **Onde:** `remoto/api.py:134` (`novidades`), `remoto/bot.py:297` (`uma_volta`), `bot.py:184-215` (`_relatorios`)
- **Defeito:** `chamar` devolve `{}` sem levantar, `novidades` vira `[]` e `uma_volta` volta na hora (cerca de 2.700 voltas por segundo). `relatorios.montar` (com `schtasks` e OAuth) roda em toda volta enquanto a rede não volta.
- **Conserto:** `Telegram.novidades` devolve `None` quando `chamar` deu `{}` (rede) e `[]` quando o Telegram respondeu `ok` sem nada. Em `uma_volta`, se vier `None`, dormir 10 s (com `self._dormir`, para poder dublar) antes de seguir. Em `_relatorios`, guardar `self._relatorio_montado[nome] = (texto, hora)` e reaproveitar o texto por até 1 h enquanto não houver entrega. Também atualizar o docstring, que ainda diz "marca ANTES de mandar".
- **Teste que prova:** `remoto/test_telegram_entrega.py::test_sem_rede_uma_volta_dorme`, com o Telegram dublado devolvendo `{}` em `chamar` e `_dormir` contando: espera `_dormir` chamado com valor maior ou igual a 5. E `test_relatorio_vencido_monta_uma_vez_sem_rede`: 20 voltas sem rede chamam `relatorios.montar` 1 vez (hoje 20).
- **Origem:** `remoto-bot.md` #1

### APP-10 — Sem rede no `getMe`, o bot sai em vez de esperar  (médio)
- **Onde:** `remoto/bot.py:348-354` (`rodar`)
- **Defeito:** um `getMe` sem resposta (rede ou DNS caídos) é tratado como token errado e o processo termina. Quem traz o bot de volta é o coordenador, que tem um limite de falhas por hora.
- **Conserto:** repetir o `getMe` em laço: se `chamar("getMe")` devolve `{}` (rede), logar uma vez "sem rede; tento a cada 30 s" e dormir 30 s. Só sair quando o corpo tem `error_code` 401 ou 404, que é token errado de verdade. Para isso, `Telegram.eu()` passa a expor a resposta bruta (por exemplo, um `eu_bruto()`).
- **Teste que prova:** `remoto/test_remoto.py::test_rodar_espera_a_rede_no_getme`: o dublado devolve `{}` duas vezes e depois `{"ok": True, "result": {"username": "x"}}`. `rodar()` precisa chegar a `uma_volta` (interrompida por `KeyboardInterrupt` no dublado) e `_dormir` precisa ter sido chamado 2 vezes. Hoje volta na primeira chamada.
- **Origem:** `remoto-bot.md` #9

### APP-11 — Erros perdidos pelo `_alertar`: os que caem antes de uma religada e os que passam do 5º  (médio)
- **Onde:** `remoto/bot.py:64` (`__init__`: `self.avisados` com tudo o que já está no diário), `bot.py:128-130` (`_alertar`)
- **Defeito:** (a) a marca-d'água vive só na memória, então um erro gravado nos cerca de 30 s antes de uma religada nunca é avisado; (b) `avisados` recebe todos os recentes, mas só `novos[:5]` saem, e do 6º em diante somem (não vão à fila nem aos calados).
- **Conserto:** (a) persistir em `runtime_dir()/bot_visto.json` o `ts` do último evento tratado. Na subida, marcar como visto só o que tem `ts` menor ou igual a ele; o que é mais novo é tratado na primeira volta. (b) No `_alertar`, mandar os 5 mais novos um a um e juntar os restantes num único texto "e mais N erros: …" que também passa por `avisos.liberar`, ou ir à fila se não houver entrega. Só incluir em `avisados` o que foi mandado, juntado ou enfileirado.
- **Teste que prova:** `remoto/test_remoto.py`:
  - `test_erro_antes_da_religada_e_avisado`: bot A dá uma volta, entra um erro no diário, sobe o bot B (mesmo `bot_visto.json` temporário) e dá uma volta. Espera 1 mensagem sobre o erro (hoje 0).
  - `test_alertar_sete_erros_nao_perde_nenhum`: com 7 erros numa volta, todos os 7 detalhes aparecem no conjunto das mensagens enviadas (hoje só 5).
- **Origem:** `remoto-bot.md` #3, `remoto-bot.md` #4

### APP-12 — Porteiro e fila de avisos sem trava entre processos  (médio)
- **Onde:** `remoto/avisos.py:119-212` (`liberar`, `confirmar`, `desfazer`, `enfileirar`, `guardar_pendentes`), `remoto/bot.py:235-294` (`_entregar_pendentes` lê no começo e regrava no fim)
- **Defeito:** bot, carteiro, coordenador e cada `remoto --avisar` reescrevem `avisos_estado.json` e `avisos_pendentes.jsonl` inteiros sem trava. Na prova, de 300 `liberar()` sobraram 116 fichas, e o que outro processo enfileirou durante uma entrega se perde.
- **Conserto:** envolver o corpo de `liberar/confirmar/desfazer/enfileirar/guardar_pendentes` em `api_http.trava_arquivo(_pasta() / "avisos.lock")` (importar só a função; ela já funciona entre processos), ou `builds.travas.trava("remoto__avisos", esperar=10.0)`. Em `_entregar_pendentes`, trocar o `guardar_pendentes(restantes)` final por uma operação travada que relê a fila e tira só os itens entregues ou descartados (comparando `chave` e `em`).
- **Teste que prova:** `remoto/test_avisos.py::test_liberar_em_dois_processos_nao_perde_ficha`: 2 processos (`multiprocessing`) com 150 `liberar()` de chaves distintas cada, num `avisos.ARQUIVO` temporário. Espera 300 fichas (hoje cerca de 116). E `test_enfileirar_durante_entrega_sobrevive`: `enfileirar` chamado de dentro do `tg.mensagem` dublado precisa continuar em `pendentes()` depois do `_entregar_pendentes`.
- **Origem:** `remoto-bot.md` #6

### APP-13 — Uma linha inválida em `avisos_pendentes.jsonl` apaga a fila inteira  (médio)
- **Onde:** `remoto/avisos.py:185-191` (`pendentes`)
- **Defeito:** a list comprehension parseia o arquivo inteiro e qualquer `ValueError` devolve `[]`. O próximo `enfileirar` regrava o arquivo só com o item novo.
- **Conserto:** ler linha a linha; `json.loads` uma vez por linha dentro de `try`; pular (e contar) a linha ruim; manter só os `dict`. `OSError` continua devolvendo `[]`.
- **Teste que prova:** `remoto/test_avisos.py::test_linha_ruim_nao_apaga_a_fila`: arquivo com 2 itens bons e 1 linha `{quebrado`. Espera `len(pendentes()) == 2` e, depois de `enfileirar("novo")`, 3 itens. Hoje dá 0 e depois 1.
- **Origem:** `remoto-bot.md` #7

### APP-14 — POST que explode sai sem resposta; campo de texto com `-` derruba o comando  (baixo)
- **Onde:** `remoto/api_http.py:1082` (`do_POST`) e `1379` (`_post`); `api_http.py:1626` (`e_perigosa` com `args` não-dict); `api_http.py:2176` (`anexos` dict); `remoto/comandos_app.py:202` (`_TEXTO_OK`), `comandos_app.py:388/398` (`montar`)
- **Defeito:** ao contrário do `_get`, o `_post` não tem `except Exception → 500`, então a conexão fecha sem status e o log ganha um traceback. E um valor como `-x` passa na validação e vira opção no argparse do `main.py`.
- **Conserto:** (1) em `do_POST`, depois do `except CLIENTE_SAIU`, acrescentar `except Exception as exc: self._erro(500, type(exc).__name__)` (com o mesmo cuidado do `_get` para não gerar traceback duplo). (2) Em `_acao`, `args = corpo.get("args") or {}`; se não for `dict`, `_erro(400, "args invalido")` antes do `e_perigosa`. Em `_correio_post`, `anexos` que não é lista dá 400. (3) Em `_validar_campo`, recusar texto que começa com `-` ("não comece com hífen").
- **Teste que prova:** `remoto/test_api_http.py::test_post_com_args_texto_responde_400`: `POST /api/acao {"acao":"curar_ledger","args":"gravar"}` com token válido e `--acoes`. Espera status 400 ou 500 com JSON (hoje dá `RemoteDisconnected`). E `remoto/test_comandos_app.py::test_texto_com_hifen_recusado`: `validar("duelo", {"p1": "-x", ...})` levanta `Recusa`.
- **Origem:** `remoto-api.md` #5, `remoto-api.md` #7

### APP-15 — Vigia do tailnet manda "não sei"/"voltou" sem informação  (baixo)
- **Onde:** `remoto/vigia_tailnet.py:253-290` (`uma_olhada`), `vigia_tailnet.py:84` (`_rodar`, `timeout=20`)
- **Defeito:** três sondas sem resposta viram uma mensagem ao Telegram que diz que pode não ser nada, depois vem o "voltou". Foram 12 mensagens em 12/10, e cada olhada segura o laço do bot por até 45 s.
- **Conserto:** sem resposta só vai ao log (`self.log`), nunca ao `_mandar`. Só avisar quando houver prova de queda: um `GET https://<host>.ts.net/` sem 200, ou `serve status` respondendo sem a rota do app. Tirar a segunda sonda dentro da mesma olhada.
- **Teste que prova:** `remoto/test_vigia_tailnet.py::test_sem_resposta_nao_vai_ao_telegram`: o dublado de `_sondar` devolve `{"sem_resposta": True}` 5 vezes e depois `{"ok": True}`. Espera zero chamadas a `_mandar` (hoje 2: "não sei" e "voltou").
- **Origem:** `remoto-bot.md` #10

### APP-16 — Pequenos do bot: corte do relatório, config frágil, grupo com item calado  (baixo)
- **Onde:** `remoto/relatorios.py:413` (`funcionamento`); `remoto/config.py:84` (`carregar`), `config.py:91` (`salvar`); `remoto/bot.py:269-275` (`_entregar_pendentes`)
- **Defeito:** o corte de `funcionamento` usa o relógio e não o `agora` recebido; um autorizado não numérico derruba `carregar()` (e com ele o bot); `salvar()` descarta chaves fora do `PADRAO`; o texto agrupado inclui itens que o porteiro calou.
- **Conserto:** `corte = (agora.astimezone(timezone.utc) if agora.tzinfo else agora.astimezone()) - timedelta(hours=horas)`; em `carregar`, converter cada autorizado com `try/except (TypeError, ValueError)` e ignorar o inválido; em `salvar`, `limpo = {**PADRAO, **config}`; em `_entregar_pendentes`, calcular `liberados` antes e montar o texto só com eles.
- **Teste que prova:** `remoto/test_remoto.py`: `funcionamento(datetime(2020,1,1))` não mostra o erro de hoje; `carregar()` com `autorizados: [1, "abc"]` devolve `[1]`; `salvar({...,"minha_chave": 1})` mantém `minha_chave`. Em `test_telegram_entrega.py`: com 3 novos e 1 repetido já enviado, o texto mandado não contém o repetido.
- **Origem:** `remoto-bot.md` #11, #12, #13, #14

### APP-17 — Telas do app: Cinema vazio, 404 dos ícones, "O que falta", código morto, prévia do Godot, parear, título, Continuar, prova de tela, favicon  (baixo)
- **Onde e conserto, item por item.** Todos já estão escritos na worktree `E:\projetos-wt\codex-pedido-c7e0c0d9`; conferir e aplicar.
  - `remoto/app/app.js:320` (`carregarVideos`) e `:829`: escrever "carregando os vídeos…" em `#videos` antes do `await`; chamar `carregarVideos()` sem esperar `carregarAcoes()` e, quando ele voltar, redesenhar a lista já carregada.
  - `remoto/app/vila.js:156` (`vilaObjetosDoAtelie`): iterar `Vila.mundo.objetos_do_atelie`, que `remoto/vila_nova.py:mundo()` passa a mandar com os objetos para os quais `peca_do_atelie("objetos/<n>.png")` não é `None`. Hoje é `None` para os 4 na máquina real, por isso os 4 404.
  - `remoto/app/atelie_novo.js:98` (`animFaltam`): zerar `peca/estado/animacao`, chamar `animDesenhar()` e escrever "O que falta desenhar" em `#anim-caminho`.
  - `atelie_novo.js:60-77`: apagar as primeiras cópias de `animMiniatura`, `animAnimarMiniatura`, `animFolha` e `animPrevia` (as que valem são as das linhas 84, 89, 121 e 130).
  - `atelie_novo.js:143/158`: guardar o timer da prévia em `AnimAtelie.previa`; `atelieParar()` dá `clearTimeout` e zera o timer, e `consultar` sai se a prévia não é mais a corrente.
  - `app.js:593-609` (parear): `resp.json()` dentro de `try`; `TypeError` mostra "Não consegui falar com o PC. Confira o Tailscale neste celular."; `!resp.ok` sem JSON mostra "O PC respondeu com erro N".
  - `app.css:25` (`header h1`): `min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis`; `#conexao` com `max-width:44%` e ellipsis; em `conversa.js:206`, o rótulo de `livre` vira "Rodízio".
  - `comandos.js:100-103`: o `#btn-campos-ok` fica `disabled` até as promessas de `comandosPreencherIds` acabarem, e a lista reaproveita a que `carregarVideos` já baixou.
  - `remoto/test_app_tela.py:140`: esperar `#anim-grupos button` no lugar de `#modular-slots button`.
  - `sw.js:4-8`: acrescentar `"icones/favicon-16.png"` à `ARQUIVOS` e subir a `CASCA` (junto com o APP-6 e o APP-7, uma subida só).
- **Teste que prova:** `remoto/test_app_modulos.py` (estático: não há mais função duplicada em `atelie_novo.js`; `favicon-16` está em `ARQUIVOS`; `atelieParar` não é vazio); `remoto/test_vila_nova.py::test_mundo_lista_objetos_do_atelie_so_com_arte` (com `peca_do_atelie` → None, a lista vem vazia); `remoto/test_app_tela.py` com `NF_TESTE_NAVEGADOR=1` passando na tela Ateliê. Depois, o conferente abre o Chrome 390x844: Cinema mostra "carregando os vídeos…"; nenhum 404 de `/arte-vila/atelie/objetos/`; "O que falta" mostra a busca; parear sem servidor mostra a frase em português.
- **Origem:** `app-celular.md` #3, #4, #5, #6, #7, #8, #9, #10, #11, #12

---

## Já consertados
Nenhum. Os commits depois dos relatórios (`a34b355`; `bc41a2a`, `0b8e0d9` e `b71f02e` são anteriores ao relatório do bot e já foram descontados por ele) não tocam nestes defeitos.

## Alarmes falsos
Nenhum. Duas ressalvas de precisão:
- `app-celular.md` #4: a prova "não existe `painel/flutuante/arte_vila/atelie/objetos/`" olhou a pasta errada (a arte vem de `palco/biblioteca/animacoes` por `arte_pronta.peca_do_atelie`), mas o defeito é real: medi `None` para os 4 objetos na máquina.
- `app-celular.md` #12: o `favicon.ico` não é pedido pelo `index.html` (ele só é servido em `api_http.py:426`); falta só o `favicon-16.png`.

## Decisões que são do Adrian
- Nenhuma de produto. A única escolha com cara de produto é o rótulo "Rodízio" no lugar de "Qualquer um livre" no título da conversa (APP-17), que é reversível.
