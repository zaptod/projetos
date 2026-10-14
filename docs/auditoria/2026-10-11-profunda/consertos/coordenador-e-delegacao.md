# Consertos — coordenador e delegação (verificação de 14/10/2026)

- **Parte:** coordenador (Mesa, supervisor, vigia, pedidos) e delegação (`remoto/delegar.py`, `apurador`, `decisoes`, `claude_estado`, `orquestrador`).
- **Relatórios de origem:** `coordenador.md` (13 defeitos) e `remoto-delegacao.md` (14 defeitos), os dois escritos em 12/10 sobre o commit `707130f`.
- **Contagem:** 27 abertos, 0 consertados, 0 falsos.
- Nenhum commit mexeu nesses arquivos depois de `707130f`. Os commits de despachante e Mesa citados (8c6bcf3, c0de1ca, ebf2a0d, 1aa8d0b, 560bb01, 0b8e0d9, 0c09873, 1257601) são todos de ANTES dos relatórios, e os relatórios já os levaram em conta.
- **Conserto em ramo não mesclado:** o ramo `worktree-agent-ac362a0bfcc5f30f8` (5b087cb, "WIP etapa 2 — NÃO TESTADO") cobre COO-3 (que junta COO#4 e COO#11), COO-4 (COO#5) e COO-5 (COO#1), além da decisão D3. Isso NÃO conta como consertado. Reaproveite o ramo quando ele for terminado e testado.
- A worktree `E:\projetos-wt\codex-pedido-e3e343cd` (situação "parado") também tem mudanças no índice em `supervisor.py`: janela da postagem, reinícios em 24 h e a trava com o próprio pid. Também não está mesclada.

### COO-1 — `limpar_orfas` apaga a worktree viva de tarefa de outro repositório  (crítico)
- **Onde:** `remoto/delegar.py:2183` (`limpar_orfas`)
- **Defeito:** `registradas` vem só do `git worktree list` do repositório padrão. Por isso a worktree de uma tarefa com `repo_tarefa` (por exemplo `E:\jogo_ZOMBIE`) passa por órfã e vai para `_mover_para_o_lixo`, que primeiro dá `rmtree`.
- **Conserto:** monte `registradas` com a união dos `git worktree list --porcelain` de cada repositório distinto em `{repo_da(e) for e in listar()}` mais `repo()`. Some também os `worktree` de toda ficha de `listar()` que não tenha `limpo`. Pule qualquer pasta que esteja nesse conjunto.
- **Teste que prova:** `remoto/test_delegar.py::test_limpar_orfas_preserva_worktree_de_outro_repo`. Cria dois repositórios git temporários e uma tarefa com `repo_tarefa` no segundo, chama `limpar_orfas()` e afirma que a lista volta vazia e que a pasta da worktree ainda existe. Hoje a pasta some.
- **Origem:** `remoto-delegacao.md` #2

### COO-2 — Pedido preso em "entregue", ou "conferido" sem commit, quando a entrega não é aplicada direto  (médio)
- **Onde:** `coordenador/pedidos.py:3080` (`_conferir`), `coordenador/vigia_trabalho.py:960` (`_cuidar`, commit) e `:632` (`_contratar_integrador`)
- **Defeito:** `_conferir` só olha a ficha do próprio trabalhador. Com isso, uma entrega aplicada pelo `integrar-<id>` nunca fecha o pedido. E uma entrega com `aplicado` mas cujo commit falhou fecha como "✅ Pedido conferido".
- **Conserto:** (1) No vigia, depois de commitar, grave o hash na ficha com `self.delegar._mudar_estado(did, commit=commit)` ou com uma função pública equivalente. Ao aplicar uma ficha `integrar-X`, grave também na ficha X `aplicado_por="integrar-X"` e `commit=...`. (2) Em `_conferir`: leia também a ficha `integrar-<trabalhador>`. Feche como conferido só quando houver `aplicado` E `commit`, numa das duas fichas. Se houver `aplicado` sem `commit`, ou se o trabalhador estiver em `olho` no `trabalho_memoria.json`, chame `_esperar(dados, pedido, <motivo do olho>)`. (3) Em `_contratar_integrador`, não contrate quando o motivo começar com "aplicado na árvore".
- **Teste que prova:** em `coordenador/test_pedidos.py`, dois testes. `test_entregue_fecha_quando_integrador_aplica`: a ficha X sem aplicado e `integrar-X` com aplicado+commit; um `passo` deixa o pedido `conferido`. `test_aplicado_sem_commit_nao_vira_conferido`: a ficha com `aplicado` e sem `commit` deixa o pedido em `esperando_voce`, sem aviso "✅". Os dois falham hoje.
- **Origem:** `coordenador.md` #2 e #3

### COO-3 — Reinício recusado some ("executado pelo coordenador", CLI "ok") e reinício em backoff mata sem religar  (médio)
- **Onde:** `coordenador/supervisor.py:559` (`processar_comandos`) e `:697-708` (`reiniciar_servico`), `coordenador/__main__.py:202` (`reiniciar`), `coordenador/acoes_pc.py:43` (`reiniciar_tudo_seguro`)
- **Defeito:** o `False` de `reiniciar_servico` é ignorado: o comando é marcado como executado e nada entra em `reinicio_pedido`. Além disso, `reiniciar_servico` chama `religar(forcar=forcar)`, e o backoff recusa depois de o processo já ter sido parado.
- **Conserto:** em `reiniciar_servico`, depois de passar pelo `seguro()` e parar o processo, chame `self.religar(nome, "pedido", forcar=True)`. Em `processar_comandos`, se ele devolver `False`, faça `self.reinicio_pedido.add(valor)`, aplique o comando com `nota=f"pendente: {motivo_espera}"` e `continue`. Em `reiniciar_tudo`, mesma coisa por serviço. Na CLI, com `False`, imprima o motivo, deixe o pedido em disco para o residente (`reinicios_pendentes.json`, como no ramo 5b087cb) e devolva 2.
- **Teste que prova:** em `coordenador/test_coordenador.py`, dois testes. `test_reiniciar_recusado_fica_pendente`: com `postar.py` na lista de processos, o comando `servico_reiniciar app` é aplicado com nota "pendente", `reinicio_pedido=={'app'}`, e quando a publicação some o pulso seguinte para e inicia o app. `test_reiniciar_em_backoff_religa`: com `proximo_reinicio` no futuro, `reiniciar_servico` para e inicia e devolve True. Mais `test_cli_reiniciar_recusado_sai_2`.
- **Origem:** `coordenador.md` #4 e #11

### COO-4 — `saudes_ruins` não zera ao religar: o app novo é morto 5 s depois de subir  (médio)
- **Onde:** `coordenador/supervisor.py:466` (`religar`) e `:497-505` (`verificar_servico`)
- **Defeito:** depois da 1ª morte por saúde ruim, o contador fica em 3, e o primeiro pulso com a porta ainda fechada já mata o processo novo.
- **Conserto:** `self.saudes_ruins[nome] = 0` em `religar`, logo depois do `estado.update(situacao="rodando", ...)`.
- **Teste que prova:** `coordenador/test_coordenador.py::test_app_religado_tem_tolerancia_de_saude_de_novo`. A porta fica fechada por 3 pulsos (o app é morto), depois religa, e no pulso seguinte, com a porta ainda fechada, `parar` não é chamado para o pid novo.
- **Origem:** `coordenador.md` #5

### COO-5 — Uma leitura do `estado.json` no instante do `os.replace` derruba o coordenador inteiro  (médio)
- **Onde:** `coordenador/estado.py:36` (`gravar_estado`) e `coordenador/supervisor.py:755-765` (`rodar`)
- **Defeito:** um `PermissionError` do `os.replace` (com o app lendo o arquivo) sai do `pulso()` sem `try`. O processo morre e leva junto as threads do vigia, dos pedidos e da conversa.
- **Conserto:** em `gravar_estado`, repita o `os.replace` até 6 vezes com pausa de 0,15 s em `PermissionError`, como em `pedidos._gravar`. Em `rodar()`, ponha `try/except Exception` em volta de `self.pulso()` que loga `"[coordenador] pulso falhou: ..."` e segue.
- **Teste que prova:** em `coordenador/test_coordenador.py`, dois testes. `test_gravar_estado_tenta_de_novo`: monkeypatch de `os.replace` que falha 2 vezes com PermissionError; o arquivo termina gravado. `test_rodar_sobrevive_a_pulso_que_levanta`: um `gravar` que levanta no 1º pulso; `rodar(parar=...)` faz 3 pulsos e devolve 0.
- **Origem:** `coordenador.md` #1

### COO-6 — `coordenador pedir` morre com `TimeoutError` (trava de 10 s) e o pedido não é registrado  (médio)
- **Onde:** `coordenador/pedidos.py:3342` (`passo`, a trava em volta de `reconciliar_fantasmas` + `_andar_os_pedidos`), `:132` (`_TravaDoArquivo.__enter__`), `coordenador/__main__.py:155-163` (`pedir`)
- **Defeito:** o `passo` segura `pedidos.lock` enquanto lê fichas, eventos e respostas de cada trabalhador. Quem chega depois de 10 s recebe um `OSError` que o `pedir` não trata.
- **Conserto:** (1) `_TravaDoArquivo.__enter__` chama `trava_arquivo(alvo, prazo=60)`. (2) Tire `reconciliar_fantasmas()` de dentro do `with _TRAVA` e rode antes dele. (3) Em `main("pedir")`, capture `OSError` e imprima `recusado: a Mesa está ocupada (...); tente de novo`, devolvendo 3. Faça o mesmo tratamento no handler do app, que hoje devolve 503 sem explicação.
- **Teste que prova:** `coordenador/test_pedidos.py::test_pedir_com_trava_ocupada_nao_da_traceback`. Uma thread segura `_TRAVA` por 2 s com o prazo dublado em 1 s; `main(["pedir","x"])` devolve 3 e escreve "recusado" no stderr, sem traceback.
- **Origem:** `coordenador.md` #6

### COO-7 — `aplicar` marca APLICADA quando o `git apply -3` falha sem conflito  (médio)
- **Onde:** `remoto/delegar.py:2017` (`aplicar`, ramo do merge de 3 vias)
- **Defeito:** o retorno do `git apply -3` é ignorado. Reproduzi assim: um arquivo apagado na principal faz `apply -3` sair com 1 ("does not exist in index"), sem `U` e com o status vazio, e a ficha recebe `aplicado`. Isso alimenta o "conferido" falso de COO-2.
- **Conserto:** guarde `feito3 = _git("apply", "-3", ...)`. Se `feito3.returncode != 0` e `_resolver_conflitos_conhecidos` devolver vazio, chame `_desfazer_aplicacao(alvo_repo, arquivos)` e `raise Recusa("git apply -3 falhou: " + stderr[:300])`. Depois disso, confira também que `git status --porcelain -- *arquivos` não está vazio antes de gravar `aplicado`.
- **Teste que prova:** `remoto/test_delegar.py::test_aplicar_3vias_falho_nao_marca_aplicado`. A entrega muda `existente.py` e cria `novo.py`, e a principal commita `git rm existente.py`. `aplicar` levanta `Recusa`, `ler_estado(id)["aplicado"]` fica vazio e `novo.py` não existe.
- **Origem:** `remoto-delegacao.md` #1

### COO-8 — Nome de arquivo com acento vira `"docs/decis/303/243o.md"` na entrega  (médio)
- **Onde:** `remoto/delegar.py:1811` e `:1838` (`coletar`)
- **Defeito:** `git diff --name-only/--numstat` sai com aspas e octal (`core.quotepath` não está configurado em nenhum escopo), e o código ainda troca `\` por `/`.
- **Conserto:** use `_git("-c", "core.quotepath=false", "diff", "--cached", "--no-renames", "--name-only", "-z", base, cwd=wt)` e separe por `"\0"`. Faça o mesmo no `--numstat -z`: com `-z` o formato é `mais\tmenos\tcaminho\0`. Não aplique `.replace("\\", "/")` em nome que veio do git.
- **Teste que prova:** `remoto/test_delegar.py::test_coletar_nome_com_acento`. A worktree cria `docs/decisão.md`; `coletar` devolve `caminho == "docs/decisão.md"` e esse caminho existe na worktree.
- **Origem:** `remoto-delegacao.md` #3

### COO-9 — `claude.json` trancado por um instante mata o trabalhador Claude e os delegados da Mesa  (médio)
- **Onde:** `remoto/claude_estado.py:97` (`ler`) e `:186` (`mudar`, `os.replace` sem nova tentativa), `remoto/delegar.py:1215` (`_Rodada.guarda`), `coordenador/supervisor.py:726-728` (`pulso`)
- **Defeito:** um `PermissionError` passageiro vira "ilegível = PROIBIDO", e a guarda (assim como o pulso do supervisor) para os trabalhadores na hora.
- **Conserto:** em `ler()`, num `PermissionError`, tente de novo até 5 vezes com pausa de 0,2 s, e só depois devolva "ilegivel". Em `mudar`, repita o `os.replace` (6 vezes, 0,15 s). Em `guarda` e em `Supervisor.pulso`, só pare se `motivo_proibido()` vier com `origem == "arquivo"`, ou se vier "ilegivel" em duas leituras seguidas com 2 s ou mais entre elas.
- **Teste que prova:** em `remoto/test_claude_estado.py`, `test_ler_tenta_de_novo_no_permission_error`: monkeypatch de `Path.read_text` que falha 2 vezes com PermissionError e depois devolve `{"liberado": true}`; `ler()["liberado"] is True`. Em `remoto/test_delegar.py`, `test_guarda_nao_mata_por_ilegivel_unico`.
- **Origem:** `remoto-delegacao.md` #6

### COO-10 — Ficha "rodando" com PID reaproveitado nunca fecha (`testar`/`aplicar`/`limpar` "Ocupado" para sempre)  (médio)
- **Onde:** `remoto/delegar.py:1075` (`_rodando`) e `:1079` (`reconciliar_fantasmas`), `remoto/orquestrador.py:812` (`_pid_vivo`)
- **Defeito:** a vida do despachante é decidida só pela existência do número do PID.
- **Conserto:** ao gravar `pid`, grave também `pid_criado` (o horário de criação do processo, via `GetProcessTimes` ou `psutil.Process(pid).create_time()`). Em `_rodando`, um processo vivo com horário de criação diferente conta como morto. Em `reconciliar_fantasmas`, feche também fichas `rodando` cujo `eventos.jsonl` não muda há mais de `rodar_timeout_s + 600` s, qualquer que seja o PID.
- **Teste que prova:** `remoto/test_delegar.py::test_fantasma_com_pid_reaproveitado`. A ficha `rodando` tem o `pid` do próprio pytest, `pid_criado` diferente e `inicio` de horas atrás; `reconciliar_fantasmas(minutos=0)` devolve o id e `limpar` deixa de levantar `Ocupado`.
- **Origem:** `remoto-delegacao.md` #8

### COO-11 — Conflito da casca deixa `sw.js` e o teste da casca sujos fora de `aplicado.arquivos`  (médio)
- **Onde:** `remoto/delegar.py:2073-2081` (`_resolver_conflitos_conhecidos`) e `:2023` (`aplicar`)
- **Defeito:** o resolvedor reescreve `remoto/app/sw.js` e `remoto/test_app_vila_objetos.py` mesmo quando eles não estão no patch. O vigia commita só a lista, e o arquivo extra fica M na principal.
- **Conserto:** `_resolver_conflitos_conhecidos` devolve `(restantes, extras)`, em que `extras` são os arquivos fixos que ele de fato mudou. Em `aplicar`, use `arquivos = sorted(set(arquivos) | set(extras))` antes de gravar `aplicado`. Ajuste o outro chamador, se houver.
- **Teste que prova:** `remoto/test_delegar.py::test_casca_extra_entra_em_aplicado`. Na principal, sw.js e o teste estão em v5; a entrega sobe sw.js para v6; a principal commita v7. Depois de `aplicar`, `aplicado["arquivos"]` contém os dois arquivos, e `git status` só mostra arquivos que estão na lista.
- **Origem:** `remoto-delegacao.md` #7

### COO-12 — Entrega em `coordenador/**` aplicada e o coordenador segue com código velho  (médio)
- **Onde:** `coordenador/vigia_trabalho.py:977` e `coordenador/supervisor.py:687` (`pedir_reinicio`)
- **Defeito:** `pedir_reinicio("coordenador")` é ignorado, porque "coordenador" não está em `self.servicos`.
- **Conserto:** em `pedir_reinicio`, se `nome == "coordenador"`, faça `self.sair_quando_seguro = True`, registre o evento `reinicio_pedido` e avise. Em `rodar()`, troque o laço por `while not parar() and not (self.sair_quando_seguro and self.seguro("")[0] and not any(t.is_alive() for t in self.fundos.values()))`. Ao sair, devolva 0: a tarefa do Agendador religa em até 5 min. Conserte junto o `status --curto` (`__main__.py:197`), que lê uma chave `codigo_velho` que não existe no topo do `estado.json` e por isso sempre diz "código atual". Ele deve olhar `servicos.*.codigo_velho`.
- **Teste que prova:** `coordenador/test_coordenador.py::test_pedir_reinicio_coordenador_sai_do_laco`. Com `pedir_reinicio("coordenador")` e `seguro` ok, `rodar(parar=lambda: contador>5)` sai antes de 5 pulsos e há um evento `reinicio_pedido`. Mais um teste de que `status --curto` imprime "código velho" quando um serviço tem `codigo_velho: true`.
- **Origem:** `coordenador.md` #8

### COO-13 — "Suspender o PC" nunca olha o render  (médio)
- **Onde:** `coordenador/supervisor.py:387` (`_executar_acao`) e `coordenador/acoes_pc.py:37`
- **Defeito:** o supervisor não passa `render_ativo`, que fica no padrão `lambda: False`.
- **Conserto:** passe `render_ativo=lambda: any(re.search(r"godot|palco[\\/].*render|render_luta|producao", p["comando"], re.I) for p in self.processos())`. Confira os nomes reais dos processos de render do palco antes de fixar a regex.
- **Teste que prova:** `coordenador/test_coordenador.py::test_suspender_recusa_com_godot_renderizando`. Com os processos dublados contendo `godot --headless ... render`, `Supervisor._executar_acao("suspender")` levanta `ValueError` e o `rodar` dublado não é chamado.
- **Origem:** `coordenador.md` #9

### COO-14 — Trava única com pid reaproveitado: o coordenador não sobe e sai com 1 calado  (médio)
- **Onde:** `coordenador/supervisor.py:192` (`TravaUnica.adquirir`) e `:757` (`rodar`)
- **Defeito:** se o pid gravado no `coordenador.lock` passou a ser de outro programa, a trava nunca é retomada e ninguém é avisado.
- **Conserto:** grave `pid` e o horário de criação do processo no lock (JSON). Em `adquirir`, só respeite o dono se o pid estiver vivo E o horário de criação bater; se não houver horário (lock antigo), consulte a linha de comando do pid e exija `-m coordenador`. Em `rodar()`, quando não adquirir, logue `"[coordenador] trava de <pid> ativa; não subi"` no máximo uma vez por hora.
- **Teste que prova:** `coordenador/test_coordenador.py::test_trava_com_pid_de_outro_programa_e_retomada`. O lock tem o pid do próprio pytest e outro horário de criação; `adquirir()` devolve True.
- **Origem:** `coordenador.md` #12

### COO-15 — `apurador.uma_volta` marca o erro como apurado antes de abrir o pedido  (médio)
- **Onde:** `remoto/apurador.py:1103` (`marcar`) e `:1111` (`abrir_pedido`), na função `uma_volta`
- **Defeito:** se `pedidos.contratar` levanta, a exceção sobe ("Nunca levanta", diz a docstring) e o diagnóstico, já pago, se perde.
- **Conserto:** ponha o `abrir_pedido(erros, texto)` em `try/except Exception as exc`. Na falha, chame `_guardar_investigacao(erros, texto)` e devolva `{"feito": False, "motivo": f"Mesa indisponível: {exc}; pedido adiado", ...}`. Faça o mesmo no ramo `pendente` do início, sem `_tirar_investigacao`.
- **Teste que prova:** `remoto/test_apurador.py::test_mesa_indisponivel_guarda_a_investigacao`. Com `apurar` dublado devolvendo um texto e `abrir_pedido` levantando `OSError`, `uma_volta()` não levanta, e `_ler_estado()["investigacoes_pendentes"]` tem 1 item.
- **Origem:** `remoto-delegacao.md` #4

### COO-16 — `decisoes.responder` grava e depois estoura em `gerar_textos` (decode estrito)  (médio)
- **Onde:** `remoto/decisoes.py:1081` (`gerar_textos`), `:1110` (`_so_o_bloco_mudou`), `:607` (`responder`; também `:472`, `:506`, `:529`, `:652`, `:883`)
- **Defeito:** um `docs/sessoes/*.md` fora de utf-8 faz `UnicodeDecodeError` sair depois de o evento já estar gravado. O app mostra 500 e a segunda resposta duplica o evento. Hoje é latente: os 10 arquivos atuais são utf-8 válidos.
- **Conserto:** troque para `decode("utf-8", errors="surrogateescape")` nas duas leituras e grave com o mesmo `errors`. Em `responder` e nos outros chamadores, envolva `gerar_textos(itens)` em `try/except (OSError, UnicodeError) as exc` e ponha `evento["nota"] = f"textos não regenerados: {exc}"`.
- **Teste que prova:** `remoto/test_decisoes.py::test_responder_com_sessao_cp1252`. `docs/sessoes/builds.md` gravado em cp1252 com "ã"; `responder` não levanta e `_eventos.jsonl` tem exatamente 1 linha.
- **Origem:** `remoto-delegacao.md` #5

### COO-17 — Permissão com `alvo` absoluto dentro do repositório não libera nada (o laço de 11/10 volta)  (médio)
- **Onde:** `remoto/delegar.py:1547` (`_caminhos_do_alvo`) e `:1564` (`_liberar_caminhos`)
- **Defeito:** todo caminho com `:` é descartado, inclusive `E:\projetos\remoto\app\sw.js`. É raro desde que o padrão dos pedidos virou `["**"]`, mas ainda vale para caminho protegido e para `--permitido` estreito.
- **Conserto:** `_caminhos_do_alvo(alvo, raizes=())`. Antes de descartar por `:`, tente `Path(bruto).relative_to(r)` para cada `r` em `raizes` (o `repo_da(estado)` e a `worktree`) e use `.as_posix()`. `_liberar_caminhos` passa as duas raízes.
- **Teste que prova:** `remoto/test_delegar.py::test_alvo_absoluto_dentro_do_repo_libera`. `_caminhos_do_alvo(r"E:\projetos\remoto\app\sw.js", raizes=[Path(r"E:\projetos")]) == ["remoto/app/sw.js"]`, e `C:\Windows\x` continua fora.
- **Origem:** `remoto-delegacao.md` #14

### COO-18 — `esperando` do vigia nunca é limpo quando a entrega é aplicada ou limpa por fora  (baixo)
- **Onde:** `coordenador/vigia_trabalho.py:732` (`_faxina_olho`) e `:770` (`_faxina_delegados`)
- **Defeito:** a entrada fica no retrato para sempre e bloqueia a faxina. Na memória real, as 6 entradas de `esperando` são de fichas já aplicadas ou limpas desde 04–08/10.
- **Conserto:** em `_faxina_olho`, percorra também `esperando`, `sujo_desde` e `sujo_avisado` e tire o id quando a ficha estiver `aplicado`, `limpo`, tiver sumido (com `lista_ok`) ou quando `situacao` não for mais `terminou`.
- **Teste que prova:** `coordenador/test_vigia_trabalho.py::test_esperando_sai_quando_aplicada_por_fora`. Com `mem["esperando"]={"x1": "publicacao em andamento"}` e a ficha x1 `aplicado`+`limpo`, depois de um `passo` `esperando` fica vazio.
- **Origem:** `coordenador.md` #10

### COO-19 — Ficha "criado" antiga com commit à frente repete "precisa de olho" a cada passo  (baixo)
- **Onde:** `coordenador/vigia_trabalho.py:790` (`_faxina_delegados`, laço do `abandonar`)
- **Defeito:** o laço não consulta `mem["olho"]` nem `mem["arquivados"]`, então chama `_olho` a cada 60 s. O `outputs/coordenador.txt` tem 35.262 linhas "criado antigo". O Telegram fica limitado a 1 por dia por texto pelo porteiro, mas o Andamento e os 100 eventos do app enchem.
- **Conserto:** antes do `commits(d)`, faça `if did in mem["olho"] or did in mem["arquivados"]: continue`. Trate `commits(d) is None` como "não sei": registre `self.evento("trabalho_faxina", f"{did}: não sei se tem commit")` uma vez e não mande para `olho`.
- **Teste que prova:** `coordenador/test_vigia_trabalho.py::test_criado_antigo_sujo_avisa_uma_vez`. Cinco `passo()` seguidos e o dublê de `avisar` recebe exatamente 1 chamada.
- **Origem:** `coordenador.md` #7

### COO-20 — Conferente dos pedidos e gerente que contrata são código morto, e a mensagem promete o conferente  (baixo)
- **Onde:** `coordenador/pedidos.py:3082-3130` (`_conferir`, ramo `conferir`), `:343` (`_ROTULO["entregue"]`), `:2694`; `coordenador/equipe.py:74` (`_contratar`) e `:94` (`_conferir_aplicadas`)
- **Defeito:** nenhum código de produção liga `conferir`, então o caminho do conferente e as duas funções do gerente nunca rodam. O texto da linha 2694 ("depois o conferente olha") mente.
- **Conserto:** a decisão de 07/10 ("prova automática") já existe. Apague o ramo `conferir` de `_conferir`, `equipe._contratar` e `_conferir_aplicadas`, com os testes que só exercitam isso (`test_pedidos.py:165`, `test_equipe.py:109`). Troque o rótulo e a linha 2694 por "esperando o vigia testar e aplicar (prova automática)".
- **Teste que prova:** `coordenador/test_porta_unica.py::test_sem_conferente_morto`. Um grep no fonte afirma que não sobra `_conferir_aplicadas` nem "conferente olha".
- **Origem:** `coordenador.md` #13

### COO-21 — `corrigir` zera a prova dos testes antes de a rodada ser recusada  (baixo)
- **Onde:** `remoto/delegar.py:1675` (`corrigir`)
- **Conserto:** tire o `_mudar_estado(tarefa_id, testes=None)` de `corrigir` e zere `testes` dentro de `_preparar_rodada` (linha 1118), depois de todas as guardas e sob a trava, quando `tipo == "corrigir"`.
- **Teste que prova:** `remoto/test_delegar.py::test_corrigir_recusado_mantem_testes`. Com o teto do Codex dublado em 90%, `corrigir` levanta `Recusa` e `ler_estado(id)["testes"]` continua o de antes.
- **Origem:** `remoto-delegacao.md` #9

### COO-22 — `pedido_de_permissao` levanta `AttributeError` com `diff: None`  (baixo)
- **Onde:** `remoto/delegar.py:1490`
- **Conserto:** `(estado.get("diff") or {}).get("ok") is False`.
- **Teste que prova:** `remoto/test_delegar.py::test_pedido_de_permissao_sem_diff`. A ficha recém-criada (`diff: None`) tem `resposta.md` com "fora dos caminhos permitidos"; a função devolve `None` sem levantar.
- **Origem:** `remoto-delegacao.md` #10

### COO-23 — `.handoff.md` da renovação entra na entrega  (baixo)
- **Onde:** `remoto/delegar.py:103` (`NOSSOS`)
- **Conserto:** acrescente `".handoff.md"` a `NOSSOS`.
- **Teste que prova:** `remoto/test_delegar.py::test_handoff_e_ruido`. `_e_ruido(".handoff.md") is True`, e `coletar` numa worktree com `.handoff.md` devolve `arquivos == []`.
- **Origem:** `remoto-delegacao.md` #11

### COO-24 — Estado corrompido do apurador zera o teto das apurações  (baixo)
- **Onde:** `remoto/apurador.py:67-88` (`_gravar_estado`)
- **Conserto:** no ramo do arquivo ilegível, acrescente `dados["por_dia"] = {date.today().isoformat(): TETO_DIARIO}`.
- **Teste que prova:** `remoto/test_apurador.py::test_estado_corrompido_esgota_apuracoes`. Troque o arquivo por `{corrompido` e chame `_somar_uma(_ler_estado())`; `_contagem_de_hoje(_ler_estado()) >= TETO_DIARIO`.
- **Origem:** `remoto-delegacao.md` #12

### COO-25 — `ler_eventos(desde<0)` descarta uma linha inteira no corte exato  (baixo)
- **Onde:** `remoto/delegar.py:923-925` (`ler_eventos`)
- **Conserto:** só corte quando o byte anterior não for `\n`: leia 1 byte antes (`fh.seek(inicio-1); anterior = fh.read(1)`) e corte apenas se `anterior != b"\n"`.
- **Teste que prova:** `remoto/test_delegar.py::test_ler_eventos_corte_exato`. Cinco linhas e `maximo_bytes` igual ao tamanho exato das 3 últimas; a função devolve as 3.
- **Origem:** `remoto-delegacao.md` #13

## Já consertados
- Nenhum. Nenhum dos 27 defeitos tem commit de conserto no `refactor/arquitetura`. Os do ramo `worktree-agent-ac362a0bfcc5f30f8` (coordenador #1, #4, #5 e #11) não estão mesclados.

## Alarmes falsos
- Nenhum por inteiro. O `coordenador.md` #7 exagera o efeito: os "1.440 avisos por dia no Telegram" não acontecem, porque `ias.carteiro.avisar_telegram` passa pelo porteiro (`remoto.avisos.liberar`, o mesmo texto 1 vez por dia). O defeito existe (35.262 linhas no log) e por isso ficou baixo.

## Decisões do Adrian que mexem aqui
- **"Reiniciar serviços sozinho quando o código muda? → Só quando pedido"** (9cec584, 13/10): **NÃO implementada** no código em uso. `supervisor.verificar_servico` (linha 507) ainda reinicia quando `self.git(...)` vê arquivo mais novo, e `seguro()` (405-421) não tem a janela das postagens (o comentário ainda diz "sem janela de relógio"). Está implementada só no ramo não mesclado 5b087cb (não testado). É o mesmo trabalho que COO-3.
- **"Um gerente só para app, bot e Vila → Desligar as três e apagar a retomar_codex"** (b1ef6f7, 13/10): **implementada na máquina**, sem mudança de código. `Get-ScheduledTask` mostra `NeuralFights_app_celular`, `NeuralFights_bot_telegram` e `NeuralFights_vila_flutuante` como Disabled, e `NeuralFights_retomar_codex` não existe mais. O CLI `desligar-tarefas-antigas` já existia (`__main__.py:73`).
