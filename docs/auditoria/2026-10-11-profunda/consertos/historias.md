# Consertos — historias (verificação de 14/10/2026)

- **Parte:** `historias` (roteiro/LLM, imagens/vídeo, pipeline/CLI)
- **Relatórios de origem:** `historias-imagens-video.md` (5), `historias-pipeline.md` (4), `historias-roteiro-llm.md` (9)
- **Contagem:** 18 abertos / 0 consertados / 0 falsos
- Nenhum commit depois de 11/10 mexeu nestes defeitos: `80a4505` (agenda `_retomar_texto`, erro da retomada como dicionário) e `a34b355` (agenda põe a raiz no `sys.path`) tocam a `agenda.py`, mas em outros pontos. Nenhum ramo `delegar/*` ou worktree recente tem diff em `historias/contos` ou `historias/main.py`.
- A **decisão `b339bbb`** (`decisoes/historias/gemini-sem-pro-escreve.json`, opção `cair`: "Pular para o próximo provedor e avisar no Telegram"; nunca escrever no Flash, e sem provedor forte a rodada espera) **NÃO está implementada**: é o HIS-2.

---

### HIS-1 — roteiro.json e biblia.json gravados por cima, sem temporário  (crítico)
- **Onde:** `historias/contos/roteiro/roteiro.py:930` (`salvar_serie`), `roteiro.py:1112` (`salvar`, caminho manual), `historias/contos/roteiro/gerar.py:39` (`_gravar`, grava `biblia.json`), `roteiro.py:1125` (`listar`)
- **Defeito:** `open(..., "w")` + `json.dump(indent=2)` direto no arquivo final, regravado a cada parte. Se o processo morre no meio, o JSON fica truncado: `listar()` pula a pasta calado (some do rodízio, de `incompletas()` e do painel), `carregar` levanta e `gerar._situacao` responde "nova". Aí `escrever_serie` com o mesmo id (próximo provedor da mesma rodada) escreve outra bíblia na pasta, por cima das `cenas/` da antiga.
- **Conserto:** criar em `roteiro.py` uma `_gravar_json_atomico(caminho, dados)`: grava em `caminho.with_name(caminho.name + f".{os.getpid()}.tmp")`, `fh.flush()` + `os.fsync`, e `os.replace` no final, com até 3 tentativas em `PermissionError` (leitor aberto no Windows), como no ledger de `a34b355`. Usar essa função em `salvar_serie`, `salvar`, `registrar_queda` e `gerar._gravar`. Em `listar()`, no `except ValueError`, registrar `aviso` no diário (`builds.atividade`, etapa `roteiro.ilegivel`, ref = id da pasta), uma vez por pasta e por dia. Em `gerar._situacao`, se `roteiro.json` existe mas não lê, devolver `"ilegivel"`, e `escrever_serie` levanta `GeracaoFalhou` sem tentar outro provedor (nunca tratar como "nova").
- **Teste que prova:** `historias/tests/test_roteiro_gravacao_atomica_regressions.py`: (a) faz `json.dump` levantar no meio (dublê que escreve metade e lança `OSError`) e afirma que o `roteiro.json` anterior continua legível e igual; (b) com um `roteiro.json` truncado na pasta, `gerar._situacao(id) == "ilegivel"` e `escrever_serie([...], historia_id=id)` levanta sem chamar `gerar_serie`; (c) `listar()` com JSON truncado registra 1 aviso no diário. Hoje (a) acha o JSON truncado e (b) devolve "nova".
- **Origem:** `historias-roteiro-llm.md` #3

### HIS-2 — Gemini fora do modelo forte escreve o roteiro calado (decisão b339bbb não aplicada)  (alto)
- **Onde:** `historias/contos/llm/cliente.py:150-200` (`escolher_modelo`) e `:269-312` (`_tentar_modelo`); `historias/contos/roteiro/gerar.py:503-514` (`gerar_serie`); `gerar.py:721` (`escrever_serie`)
- **Defeito:** `escolher_modelo` só escreve "ATENCAO" no log e devolve. `gerar_serie` grava `modelo_llm = "NAO CONFIRMADO (...)"` e escreve a história inteira assim mesmo. Nada vai ao diário nem ao Telegram, e a ordem de queda não anda. E há mais: `_tentar_modelo` devolve `confirmado=True` quando cai na 2ª preferência (`"flash"` em `seletores.py:186`) ou quando "nenhum modelo de [...] nesta conta" (`:305-308`). Então o Flash passa como "confirmado" justamente no caso da cota do Pro esgotada (o "-> 3.5 Flash Lite" de 07/10).
- **Conserto:** (1) No cliente, um atributo novo `self.modelo_forte: bool`. É True só quando o nome escolhido casa com `ordem[0]`. Fica False no 2º item da lista, em "nenhum modelo nesta conta" e em falha. Para o DeepSeek (`modelo_fixo`) é True. (2) Em `abrir()`, se `self.papel == "roteiro"` e `not self.modelo_forte`, registrar no diário `erro` (etapa `llm.modelo_fraco`, ref = papel/história, texto "o <provedor> não entrou no modelo forte (<nome>); passo ao próximo provedor") e levantar uma `ModeloFraco(LLMFalhou)` nova. (3) Em `gerar_serie`/`retomar_serie`, nada a mudar além de deixar a `ModeloFraco` subir, porque `escrever_serie` já trata exceção como queda para o próximo provedor. (4) Quando o último provedor cai por `ModeloFraco`, a rodada não escreve e avisa no Telegram uma vez por dia (`agenda._avisar_uma_vez_por_dia`, chave `modelo-fraco`). (5) Não levantar para outros papéis: parecer e reparo só avisam no diário, e o carteiro de imagens nada (ver HIS-11).
- **Teste que prova:** `historias/tests/test_modelo_fraco_cai_regressions.py`. Com um dublê de página cujo menu oferece só "3.5 Flash" e preferência `["pro","flash"]`, afirma `cliente.modelo_forte is False`. Depois chama `escrever_serie(["gemini","deepseek"])` com o gemini dublado nesse estado e o deepseek normal, e afirma: a história sai com `provedor == "deepseek"`, o `roteiro.json` tem `quedas[0]["provedor"] == "gemini"` e o diário dublado recebe 1 `erro` `llm.modelo_fraco`. Só com o gemini, levanta e não grava `roteiro.json`. Hoje o gemini escreve e o diário fica vazio.
- **Origem:** `historias-roteiro-llm.md` #1 (e decisão `historias/gemini-sem-pro-escreve`, commit `b339bbb`)

### HIS-3 — Pergunta devolvida à caixa num chat com turnos: volta a resposta anterior  (alto)
- **Onde:** `historias/contos/llm/cliente.py:447` (`enviar`), `:488` (`_envio_devolvido`), `:947` (`_resposta_nova`), `:1021`/`:1150-1160` (`esperar_resposta`)
- **Defeito:** `_envio_devolvido` desiste se existe QUALQUER turno do usuário na tela, e `_resposta_nova` aceita o texto "ancorado" depois do ÚLTIMO turno do usuário sem conferir que esse turno é o prompt atual. Se o site devolve a pergunta para a caixa sem criar turno, a resposta da parte N volta como se fosse a da parte N+1 (ou a da revisão), e a parte duplicada vira vídeo.
- **Conserto:** em `enviar`, antes de colar, guardar `self._turnos_usuario_antes = <contagem de elementos de sel["turno_usuario"]>` (função nova `_contar_turnos_usuario`, que nunca levanta e devolve -1 se não souber). Em `esperar_resposta`, antes de aceitar qualquer texto: se a contagem é conhecida e não subiu (`atual <= antes`), não aceitar a resposta. Passado `devolvido_apos` sem turno novo, levantar `LLMFalhou("o envio voltou para a caixa: nenhum turno novo na conversa")`, mesmo com conversa na tela. Reserva para quando a contagem é -1: comparar `_texto_do_turno_usuario()` com `self._ultimo_prompt` (os 40 primeiros chars sem espaços repetidos).
- **Teste que prova:** `historias/tests/test_envio_devolvido_com_turnos_regressions.py`. Dublê de DOM com 1 turno de usuário e 1 resposta (1842 chars). `enviar` "confirma" (o campo esvazia) mas não acrescenta turno, e o prompt volta à caixa. Afirma que `esperar_resposta` levanta `LLMFalhou` em vez de devolver o texto anterior (hoje devolve em ~12 s). Num segundo caso, com o turno novo e a resposta nova no DOM, devolve a resposta nova.
- **Origem:** `historias-roteiro-llm.md` #2

### HIS-4 — Bíblia com menos partes passa e a retomada pede "PARTE 6 de 5"  (alto)
- **Onde:** `historias/contos/roteiro/gerar.py:570` (`gerar_serie`, porta depois do 2º pedido), `serie.py:593`/`:608` (`parse_biblia`/`problemas_da_biblia`), `serie.py:1038-1050` (`prompt_parte_livre`), `roteiro.py:897` (`partes_esperadas`)
- **Defeito:** a porta só exige lista de partes não vazia. Uma bíblia com 5 de 6 partes vira roteiro com `partes_esperadas: 6`, `incompletas()` o devolve sempre e a retomada pede ao LLM um episódio depois do fim, sem plano ("PARTE 6 de 5 … É a última parte").
- **Conserto:** em `gerar.py`, logo depois do 2º `parse_biblia`, se `0 < len(biblia["partes"]) < biblia["partes_esperadas"]`, fazer `biblia["partes_esperadas"] = len(biblia["partes"])` e logar "[serie] a bíblia planejou N de M partes; a série fica com N". Com menos de 2 partes, levantar `GeracaoFalhou`. Como defesa, em `retomar_serie`, se o número a escrever for maior que `len(biblia["partes"])`, levantar `GeracaoFalhou("parte sem plano")` em vez de pedir ao LLM.
- **Teste que prova:** `historias/tests/test_biblia_curta_regressions.py`. Com cliente dublado que devolve 5 partes nas duas tentativas para `partes=6`, `gerar_serie` grava `partes_esperadas == 5` e `R.partes_que_faltam(...) == []`. E `retomar_serie` num roteiro com 5 partes no plano e `partes_esperadas=6` levanta sem chamar `cliente.perguntar`. Hoje dá `[6]` e o prompt "PARTE 6 de 5".
- **Origem:** `historias-roteiro-llm.md` #4

### HIS-5 — Arquivo ilegível acima de 10 KB conta como imagem pronta  (alto)
- **Onde:** `historias/contos/imagens/fila.py:78` (`vertical`), `:102` (`proporcao_ok`), `:126` (`utilizavel`)
- **Defeito:** os dois validadores devolvem `True` quando a PIL não abre o arquivo. Um download truncado ou uma página de erro salva como `.png` fica "pronta", o worker nunca a refaz, o renderer (`video/renderer.py:400-415`) a troca calado por cena sem imagem, e a vistoria não acusa "cena sem imagem" porque a fila diz pronta. Medido hoje: 11.200 bytes de lixo deram `vertical=True`, `proporcao_ok=True` e `utilizavel=True`.
- **Conserto:** nos dois `except` de `vertical` e `proporcao_ok`, `return False`. Em `utilizavel`, antes da proporção, decodificar uma vez com `Image.open(c).verify()` dentro de `try` (False em qualquer erro). Atualizar o comentário de `vertical`, que hoje diz que "utilizavel ja recusa".
- **Teste que prova:** `historias/tests/test_imagem_ilegivel_regressions.py`: grava 11.200 bytes de lixo como `cena_01.png` numa pasta temporária e afirma `utilizavel(p) is False` e `vertical(p) is False`. Grava um PNG 1088x1920 de verdade e afirma True. Com `fila.OUTPUTS` apontado para a pasta, afirma que `fila.pendentes(...)` inclui a cena do lixo.
- **Origem:** `historias-imagens-video.md` #2

### HIS-6 — Cena gravada no disco antes da prova ser registrada conta como pronta  (médio)
- **Onde:** `historias/contos/imagens/fila.py:378` (`estado`, campo `pronta`), `historias/contos/imagens/worker.py:512-525` (`_gerar_pelo_correio`)
- **Defeito:** o worker copia a imagem para a cena (`:515`), refaz a colagem (até 2×420 s) e só então chama `fila.registrar` (`:521`). Uma queda nesse intervalo deixa um arquivo sem registro que `estado()` dá como pronto, e a vistoria (`publicar/qualidade.py:825-834`) só AVISA quando parte das cenas está sem prova. O `shutil.copyfile` também não é atômico (com o HIS-5, o truncado passa).
- **Conserto:** (1) No worker, copiar para `destino.with_suffix(".tmp.png")`, rodar a refeita sobre esse temporário, chamar `fila.registrar` e só então fazer `os.replace(tmp, destino)`. Num `finally`, apagar o `.tmp.png` que sobrar. (2) Em `fila.estado`, `pronta = utilizavel(caminho, aspecto) and bool((registro.get("prova") or {}).get("comprovada"))`. Arquivo órfão vira pendente e é refeito. Conferir antes, no acervo, quantas cenas prontas hoje não têm prova (as históricas 00001/00002 de placeholder), para não reabrir histórias publicadas. Se houver, limitar a regra às histórias com `criado_em` >= 2026-09-14 (data da regra "nada vai ao disco sem prova").
- **Teste que prova:** `historias/tests/test_cena_orfa_sem_prova_regressions.py`. Com `fila.OUTPUTS` temporário, PNG válido 1088x1920 e sem `imagens.json`: `fila.estado(...)[0]["pronta"] is False`. Com `registrar(..., prova={"comprovada": True})`: True. E com o entregador dublado que lança na refeita, afirma que o arquivo final da cena não existe depois da exceção. Hoje dá `pronta=True` e o arquivo fica.
- **Origem:** `historias-imagens-video.md` #1

### HIS-7 — Reescritor do caminho do correio nunca é fechado  (médio)
- **Onde:** `historias/contos/imagens/worker.py:484` (`_gerar_pelo_correio`; retorna em `:571`)
- **Defeito:** o `Reescritor` (navegador do ChatGPT com trava de conta, `ExitStack` e thread própria) fica aberto até o processo acabar, depois de qualquer recusa. Só o caminho legado fecha (`:927`). O correio é o caminho ativo (`config/imagens.json` tem `geradores_imagem`).
- **Conserto:** envolver o laço `for linha in pendentes:` (`:487-570`) em `try:` / `finally: if reescritor is not None: reescritor.fechar()`.
- **Teste que prova:** em `historias/tests/test_reescritor_regressions.py`, caso novo: troca `contos.imagens.reescritor.Reescritor` por uma classe que conta `fechar()`, roda `_gerar_pelo_correio` com o entregador dublado (1 cena, entrega com prova) e afirma 1 chamada a `fechar`, inclusive quando o entregador lança `RuntimeError`.
- **Origem:** `historias-imagens-video.md` #3

### HIS-8 — Serviço do dia marcado como feito mesmo com etapa falhada  (médio)
- **Onde:** `historias/contos/pipeline/agenda.py:1590` (`_servico_do_dia`), `:1630` (`_marcar_servico(agora)`)
- **Defeito:** as três etapas (métrica, tempos e conferência) engolem a exceção, e a marca do dia é gravada assim mesmo. `servico_pendente()` passa a responder False e nada repete no mesmo dia.
- **Conserto:** guardar `falhas = []` (nome da etapa em cada `except`). Só chamar `_marcar_servico(agora)` se `not falhas`. Senão gravar na marca `{"data": None, "falhas": falhas, "tentativas": n+1, "em": ...}`, para a próxima rodada repetir só as etapas falhadas. Depois de 3 tentativas no dia, marcar o dia como feito e registrar `erro` no diário (etapa `historias.servico_do_dia`), para não ficar em laço.
- **Teste que prova:** em `historias/tests/test_agenda_automatica_regressions.py`, caso novo: com `OUTPUTS` temporário e `metricas.atualizar_uma_vez_por_dia` dublado lançando `OSError`, chama `_servico_do_dia` e afirma `servico_pendente(agora) is True`. Com as 3 etapas ok, afirma False. Hoje a primeira afirmação dá False.
- **Origem:** `historias-pipeline.md` #1

### HIS-9 — `--saida` trancado derruba a tarefa do Agendador sem deixar log  (médio)
- **Onde:** `historias/main.py:688-709` (`_redirecionar_saida`), `:712-716` (`__main__`)
- **Defeito:** o `open(argv[i+1], "a")` não trata `OSError`, e roda antes de qualquer redirecionamento. Como o `auto.cmd` manda o console para `NUL`, a rodada morre sem uma linha de explicação.
- **Conserto:** em `_redirecionar_saida`, envolver o `open` em `try/except OSError as exc`. Tentar uma alternativa `Path(argv[i+1]).with_name(f"{stem}_{os.getpid()}{suffix}")`. Se essa também falhar, devolver `(argv_sem_opcao, None)`, registrar `erro` em `builds.atividade` (etapa `historias.saida_trancada`) e seguir com a saída padrão. A rodada não deve morrer por causa do log.
- **Teste que prova:** `historias/tests/test_saida_trancada_regressions.py`: com `builtins.open` dublado lançando `PermissionError` só para o caminho pedido, afirma que `_redirecionar_saida([... "--saida", X])` devolve um arquivo aberto no caminho alternativo (ou None) sem levantar. Hoje levanta `PermissionError`.
- **Origem:** `historias-pipeline.md` #2

### HIS-10 — `modelo_llm` do roteiro mente (chat novo por recusa e retomada)  (médio)
- **Onde:** `historias/contos/roteiro/gerar.py:503-514` (`gerar_serie`), `:135` (`_perguntar_sem_recusa` abre chat novo), `:445-451` (`retomar_serie`)
- **Defeito:** o modelo é lido uma vez, no 1º chat. O chat novo aberto por recusa pode cair em outro modelo sem o roteiro saber. A retomada grava `modelo_atual` sem olhar `modelo_confirmado` e troca o `provedor` do topo (quem escreveu a bíblia) pelo dela.
- **Conserto:** em cada `partes_prontas.append({...})` (`gerar.py:435` e `:641`), acrescentar `"modelo": getattr(cliente, "modelo_atual", "")` e `"modelo_forte": getattr(cliente, "modelo_forte", getattr(cliente, "modelo_confirmado", False))`, lidos na hora. Em `retomar_serie`, passar a `salvar_serie` o `provedor=roteiro.get("provedor") or provedor` e `modelo_llm=roteiro.get("modelo_llm")` (o topo é de quem escreveu a bíblia). Se a parte saiu de modelo não forte, o topo ganha `"modelo_llm": "NAO CONFIRMADO (...)"`. Feito o HIS-2, o caso do roteiro quase some, mas o registro por parte continua sendo a prova.
- **Teste que prova:** `historias/tests/test_modelo_por_parte_regressions.py`: um cliente dublado cujo 2º `abrir()` põe `modelo_atual="Flash"`/`modelo_confirmado=False`, mais uma recusa enlatada na parte 1. Afirma que `roteiro["partes"][0]["modelo"] == "Flash"`. E que a retomada com `provedor="chatgpt"` mantém `roteiro["provedor"] == "deepseek"`.
- **Origem:** `historias-roteiro-llm.md` #5

### HIS-11 — Troca de modelo refeita (3 tentativas, ~32 s) em todo chat novo, até nos pedidos de imagem  (médio)
- **Onde:** `historias/contos/llm/cliente.py:144` (`abrir`), `:150-199` (`escolher_modelo`), `ias/carteiro.py:236`
- **Defeito:** nada lembra que o menu de modelo acabou de falhar. Cada chat novo paga 3 tentativas mais `sleep(2.5*volta)` e os timeouts. O carteiro abre um chat por imagem. Medido em 06–08/10: 210 casos, mediana de 32 s por chat e ~1,9 h somadas.
- **Conserto:** (1) Variável de módulo `_FALHA_DE_MODELO: dict[provedor -> monotonic]`. Se `escolher_modelo` falhou há menos de 600 s, fazer só 1 tentativa (sem sleep). Gravar o instante na falha e apagá-lo no sucesso. (2) `escolher_modelo(preferido=False)` = não mexer no modelo (devolve o texto do botão, ou "", com `modelo_forte=False`). `ias/carteiro.py:236` passa a chamar `c.escolher_modelo(preferido=False)` nos pedidos de imagem. A regra de queda do HIS-2 só vale para o papel `roteiro`.
- **Teste que prova:** em `historias/tests/test_modelo_forte_regressions.py`, caso novo: com um botão dublado que sempre dá `TimeoutError`, duas chamadas seguidas a `escolher_modelo` somam 3 + 1 cliques e só um ciclo de sleeps (`time.sleep` dublado). E `escolher_modelo(preferido=False)` não clica em nada.
- **Origem:** `historias-roteiro-llm.md` #6

### HIS-12 — Contador diário de imagens sem trava entre processos  (baixo)
- **Onde:** `historias/contos/imagens/cota.py:96` (`contar`)
- **Defeito:** lê, soma e grava sem trava, e o `.tmp` tem nome fixo. Duas passadas juntas contam 1 em vez de 2. Inativo hoje: só o caminho legado chama (`worker.py:132`) e `teto_de_imagens_por_dia` é 0.
- **Conserto:** fazer o ciclo ler-somar-gravar dentro de `travas.trava("historias_cota_imagens")` (a mesma primitiva da pipeline), relendo o JSON já dentro da trava, com `.tmp` por pid.
- **Teste que prova:** `historias/tests/test_cota_concorrente_regressions.py`: duas threads chamam `contar()` sincronizadas por `threading.Barrier` (com `_ler` envolvido para esperar a barreira) e afirmam que o gravado é 2. Hoje dá 1.
- **Origem:** `historias-imagens-video.md` #4

### HIS-13 — `imagens/referencia.py` é código morto que promete uma guarda  (baixo)
- **Onde:** `historias/contos/imagens/referencia.py:45-135`
- **Defeito:** nenhum módulo de `historias/contos` importa o arquivo (só `tests/test_referencia_regressions.py`). A "âncora visual", o "estilo congelado" e o "dividir por parte" descritos nele não acontecem.
- **Conserto:** remover `referencia.py` e `tests/test_referencia_regressions.py` e tirar as menções em `docs/sessoes/historias.md`, se houver. Integrar só se o Adrian pedir a imagem de referência (ver decisões).
- **Teste que prova:** um teste de arquitetura em `historias/tests/test_autossuficiencia_regressions.py` afirmando que todo módulo em `contos/imagens/*.py` é importado por algum módulo de produção (varre `import`/`from`). Hoje falha para `referencia`.
- **Origem:** `historias-imagens-video.md` #5

### HIS-14 — `main.py tudo` devolve 0 com imagens falhadas  (baixo)
- **Onde:** `historias/main.py:162` (`cmd_tudo`)
- **Defeito:** imprime os erros de `pipeline.tudo()` e devolve `0` sempre. O botão "Gerar tudo" do painel mostra sucesso.
- **Conserto:** `return 1 if (resultado["imagens"].get("erros") or resultado["imagens"].get("faltam") or resultado.get("video", {}).get("erro")) else 0`. Conferir antes as chaves reais que `pipeline.tudo` devolve, em `contos/pipeline/controller.py`.
- **Teste que prova:** `historias/tests/test_cmd_tudo_codigo_regressions.py`: um pipeline dublado devolvendo `{"imagens": {"erros": ["x"], "faltam": 1}}` dá `cmd_tudo(...) == 1`, e com `{"imagens": {"erros": [], "faltam": 0}}` dá 0.
- **Origem:** `historias-pipeline.md` #3

### HIS-15 — `agenda.rodar` relança a exceção em vez de devolver o resultado  (baixo)
- **Onde:** `historias/contos/pipeline/agenda.py:1367` (`rodar`), `:1462` (`raise`)
- **Defeito:** depois de montar `resultado` e avisar no Telegram, o `except` relança, contra a docstring ("nunca levanta"). O `cmd_auto` recebe um traceback em vez do dicionário.
- **Conserto:** trocar o `raise` da `:1462` por `return resultado` (o traceback continua no log pelo `print` da linha anterior; acrescentar `traceback.print_exc()` antes). Conferir se o `cmd_auto` devolve código ≠ 0 quando `resultado.get("erro")`.
- **Teste que prova:** em `historias/tests/test_agenda_automatica_regressions.py`, caso novo: `agenda._emendar` dublado lança `OSError`, `rodar(...)` (trava e saída em temporário) devolve um dict com `"erro"` contendo `OSError`, e `main.cmd_auto` devolve ≠ 0.
- **Origem:** `historias-pipeline.md` #4

### HIS-16 — `titulo_da_parte` pode virar só " (Parte n/N)"  (baixo)
- **Onde:** `historias/contos/roteiro/roteiro.py:454-459` (`titulo_da_parte`)
- **Defeito:** sem `serie_nome`, sem título próprio e com o título da série acima de 100 chars, o corte junta dois vazios. Medido hoje: dá `' (Parte 1/2)'`.
- **Conserto:** no ramo `len(titulo) > TITULO_MAXIMO`, se `not marca and not curto`, usar `curto = base[:TITULO_MAXIMO - len(ordem) - 3].rstrip(" ,;–—-")` e montar `f"{curto} ({ordem})"`.
- **Teste que prova:** em `historias/tests/test_titulo_proprio_regressions.py`, caso novo: `titulo_da_parte({"titulo": "X"*131, "serie": True, "serie_nome": "", "partes": [{"n":1,"titulo":"","cenas":[]},{"n":2,"titulo":"","cenas":[]}]}, 1)` começa com `"XXX"`, tem até 100 chars e termina em `"(Parte 1/2)"`.
- **Origem:** `historias-roteiro-llm.md` #7

### HIS-17 — `quem_narra` erra o gênero pelo prefixo de uma letra  (baixo)
- **Onde:** `historias/contos/roteiro/narrador.py:52-55` (`quem_narra`)
- **Defeito:** `startswith(("mulher","fem","f"))` e `startswith(("homem","masc","m"))`. Medido hoje: "moça", "menina" e "mãe" dão homem, e "filho" dá mulher (o "f" o relatório não viu). Só atinge roteiro manual ou de teste, porque o gerador normaliza para mulher/homem.
- **Conserto:** comparar a primeira palavra (sem acento) com conjuntos: `{"mulher","feminino","fem","f","moca","menina","mae","garota","senhora"}` → mulher; `{"homem","masculino","masc","m","rapaz","menino","pai","garoto","senhor","filho"}` → homem. Sem casar, cair na contagem de pistas da `protagonista`.
- **Teste que prova:** em `historias/tests/test_serie_regressions.py`, caso novo parametrizado: `quem_narra({"narrador": n})` para moça/menina/mãe dá mulher, filho/rapaz dá homem e "f"/"m" isolados continuam.
- **Origem:** `historias-roteiro-llm.md` #8

### HIS-18 — Prompt guiado: "na primeira pessoa de uma homem adulta adulto"  (baixo)
- **Onde:** `historias/contos/roteiro/serie.py:335-337` (`prompt_biblia`, ramo `elif narrador`)
- **Defeito:** artigo e adjetivo fixos no feminino, com " adulto" colado no fim. Só sai se um tipo voltar ao modo guiado (hoje os três estão em `modo: livre`).
- **Conserto:** `frase = "de uma mulher adulta" if narrador == "mulher" else "de um homem adulto"` e `add(f"QUEM CONTA: {narrador}. A historia inteira e na primeira pessoa {frase}.")`.
- **Teste que prova:** em `historias/tests/test_serie_regressions.py`, caso novo: `prompt_biblia(..., narrador="homem")` contém "de um homem adulto" e não contém "uma homem" nem "adulta adulto".
- **Origem:** `historias-roteiro-llm.md` #9

---

## Já consertados
- Nenhum. `80a4505` e `a34b355` mexeram na `agenda.py` em pontos que não são estes defeitos.

## Alarmes falsos
- Nenhum. Os 18 conferem com o código atual. Três foram reproduzidos hoje por script (`imagens` #2, `roteiro` #7, `roteiro` #8).

## Decisões que são do Adrian
- **Já decidida e não aplicada:** `historias/gemini-sem-pro-escreve` = "cair" (`b339bbb`, 13/10). Vira o HIS-2. Não precisa perguntar de novo.
- HIS-4: série cujo plano veio com menos partes que o pedido (5 de 6) sai mais curta (proposta) ou é descartada?
- HIS-13: quer a "imagem de referência" (âncora visual entre geradores) de volta, ou o módulo morto pode ser apagado?
