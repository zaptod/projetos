# Consertos — scripts, configs e panorama (SCR)

- **Parte:** scripts/tarefas do Windows/CI, panorama (`visao/**`) e configs, ferramentas, e os itens de CÓDIGO do `maquina.md` (6, 7, 8, 10, 11, 12, 13, 17, 18).
- **Relatórios de origem:** `scripts.md`, `panorama-configs.md`, `ferramentas.md`, `maquina.md` (seção "O que precisa de ação").
- **Conferido em:** 14/10/2026, ~01:30, no código do `refactor/arquitetura` @ `f670aa9`. Depois de 12/10 19:55 nenhum commit mexeu em código (só decisões e relatórios). O que mudou na máquina foi medido só por leitura.
- **Contagem:** 29 abertos, 4 consertados, 2 falsos (35 linhas no TSV). IDs: `SCR-<n>` = `scripts.md` #n, `SCR-P<n>` = `panorama-configs.md`, `SCR-PT` = a tabela de chaves dele, `SCR-F<n>` = `ferramentas.md`, `SCR-M<n>` = `maquina.md`.

---

### SCR-P7 — Ledger de histórias grava "public" seja qual for o config  (alto, latente)
- **Onde:** `ferramentas/postar.py:2892` (`_visibilidade_das_historias`)
- **Defeito:** o código lê `visibilidade` na raiz de `historias/config/publicacao.json`, mas a chave mora em `youtube.visibilidade`. Por isso o ledger sempre grava `"public"`, mesmo que o publicador suba o vídeo privado. Hoje o config diz `public`, então os dois batem por coincidência.
- **Conserto:** `alvo = ((carregar_config() or {}).get("youtube") or {}).get("visibilidade")`. Melhor ainda, gravar no ledger a visibilidade que o publicador pediu de fato (o laudo `prova` do `youtube_web` já a tem) nas chamadas de 1517, 1575, 1789 e 4548.
- **Teste que prova:** `historias/tests/test_visibilidade_do_ledger_regressions.py`. Dubla `carregar_config` com `{"youtube": {"visibilidade": "private"}}` e afirma que `_visibilidade_das_historias() == "private"`. Hoje devolve `"public"`.
- **Origem:** `panorama-configs.md` #7 (e a linha `youtube.visibilidade` da tabela)

### SCR-7 — Rodada pendurada segura a tarefa por 72 h e fecha a fábrica sem aviso  (médio)
- **Onde:** `random_builds/builds/pipeline/tarefas_noite.py:122` e `historias/contos/pipeline/tarefas.py:139` (só chamam `endurecer`); `random_builds/builds/tarefas_windows.py:119` (`limitar_execucao`, hoje usado só em `postar.py:3850`).
- **Defeito:** as 49 tarefas diárias (`Historias_auto_*`, `NeuralFights_gerar_*`) ficam com `PT72H` (medido em 14/10). Uma `main.py auto`/`noite` que trava segura a trava da faixa. Os disparos seguintes saem 0x0 dizendo "já tem rodada", e ninguém mata o Python.
- **Conserto:** (1) em `tarefas_noite.instalar` e `tarefas.instalar`, depois do `endurecer`, chamar `tarefas_windows.limitar_execucao(nome, "PT6H")`. (2) No coordenador (`coordenador/vigia_trabalho.py`), um vigia que lê o pulso da rodada no `atividade.jsonl` (`pid` + último evento). Se o pid estiver vivo e sem evento há mais de 90 min, ele mata a árvore (`taskkill /T /F /PID`) e avisa no Telegram com o pid e a última etapa.
- **Teste que prova:** `random_builds/tests/test_tarefas_limite_regressions.py` dubla `_schtasks`/`limitar_execucao` e afirma que `tarefas_noite.instalar` chama `limitar_execucao(..., "PT6H")` em cada tarefa (o mesmo para `historias/tests/test_tarefas_limite_regressions.py`). `coordenador/test_vigia_trabalho.py::test_rodada_sem_pulso_e_morta_e_avisada` usa um diário dublado com o último evento há 2 h e o pid vivo, e afirma que houve `parar(pid)` e um aviso.
- **Origem:** `scripts.md` #7

### SCR-1 — Depois de religar o PC nada volta sem alguém entrar, e nada avisa  (médio, decisão do Adrian)
- **Onde:** as 61 tarefas (`LogonType Interactive`, medido em 14/10); `coordenador/__main__.py:46` (`InteractiveToken`); `historias/contos/pipeline/tarefas.py` (docstring 7-17). `Winlogon\AutoAdminLogon` e `DefaultUserName` vazios.
- **Defeito:** queda de energia, Windows Update ou BSOD deixam publicação, criação, coordenador, app e bot parados até o logon. O bot é uma das coisas que não sobem, então ninguém avisa.
- **Conserto:** o mínimo técnico, sem navegador, é uma tarefa nova `NeuralFights_boot_aviso` com gatilho `ONSTART`, "executar estando o usuário conectado ou não" (`/RU adrian /RP <senha>`, que só o Adrian digita) e ação `python -X utf8 -m remoto --avisar "o PC religou às HH:MM; a sessão está fechada"`. O gerador fica em `remoto/tarefa.py` (`instalar_aviso_de_boot`). O passo completo (logon automático + bloqueio de tela no logon) é decisão dele.
- **Teste que prova:** `remoto/test_tarefa_boot.py` dubla `_schtasks` e afirma que os argumentos do `/Create` têm `/SC ONSTART`, `/RU` e a ação `-m remoto --avisar`, e que nenhum navegador é aberto.
- **Origem:** `scripts.md` #1

### SCR-M8 — Coordenador reinicia app/bot por "código atualizado" dentro da janela das postagens; `reinicios_24h` mente  (médio)
- **Onde:** `coordenador/supervisor.py:507-526` (`verificar_servico`), `:405-421` (`seguro`), `:286` e `:468` (`reinicios_24h`).
- **Defeito:** (a) Qualquer mudança no git (`self.git(...)`) religa o serviço sozinho. O `seguro()` não olha a janela `post-12 … post+18`, e o Adrian já decidiu (9cec584) que só se reinicia quando alguém pede. (b) `reinicios_24h` nasce 0 a cada subida do coordenador, nunca envelhece e não conta as subidas que ele adota.
- **Conserto:** já está escrito no ramo NÃO mesclado `worktree-agent-ac362a0bfcc5f30f8` (commit `5b087cb`, WIP não testado), em `.claude/worktrees/agent-ac362a0bfcc5f30f8`. Lá estão `janela_das_postagens()`, `seguro(..., janela=True)`, a lista `reinicios` com janela de 24 h guardada no `estado.json` e o fim do religar por `self.git`. Falta terminar, rodar `coordenador/` no pytest e mesclar. A regra: `codigo_velho` só marca e mostra; religar acontece por `reinicio_pedido` (entrega aplicada ou `coordenador reiniciar`) e nunca dentro da janela.
- **Teste que prova:** `coordenador/test_um_gerente_so.py` (já existe no ramo). Afirma que, com o git dizendo "mudou" e sem pedido, `verificar_servico` não chama `parar`; que, com pedido e relógio às 17:50 (grade 17:57), o reinício fica adiado com `motivo_espera` "janela das postagens"; e que `reinicios_24h` sobrevive a um `Supervisor` novo lendo o `estado.json`.
- **Origem:** `maquina.md` #8

### SCR-3 — CI nunca roda, catraca de arquitetura e ruff vermelhos  (médio)
- **Onde:** `.github/workflows/ci.yml:20,108,184` e `nightly.yml:22` (`env:` de JOB com `${{ runner.temp }}`); `ferramentas/arquitetura_baseline.json`; `neural_fights/ui/view_torneio.py:303`.
- **Defeito:** os 87 runs do GitHub listados (19/08 → 14/10, inclusive os do push de 14/10 01:09) acabam em 0 s com "workflow file issue". O CI nunca executou um passo. A causa provável é o contexto `runner`, que não existe em `jobs.<id>.env`. No local, `auditoria_arquitetura.py --strict` sai com 1 (`sys_path` 19 com teto 2, piorou desde o relatório com `historias/contos/pipeline/agenda.py:44` do a34b355; `nomes_repetidos` 2 com teto 1), e o `ruff` mostra 21 erros. Um deles é bug real: o F821 em `view_torneio.py:303`, `lambda: ... str(error)` depois do fim do `except`, que vira `NameError`.
- **Conserto:** (1) Tirar `NEURAL_FIGHTS_RUNTIME_DIR` do `env:` de job e defini-lo num passo: `run: echo "NEURAL_FIGHTS_RUNTIME_DIR=${{ runner.temp }}/neural-fights-runtime" >> $GITHUB_ENV`. Vale para os 3 jobs do `ci.yml` e para o `nightly.yml`. (2) `view_torneio.py`: `except Exception as error: msg = str(error); self.after(0, lambda: messagebox.showerror("Godot", msg))`. (3) `ruff --fix` só para F401/F541, conferindo os re-exports (memória "CI vermelho desde agosto"), e os F841 à mão. (4) Catraca: os 7 testes passam a usar o `conftest`/workspace em vez de `sys.path.insert`; `docs/sprites/prototipo_*.py` vai para `IGNORAR`; `agenda.py:42-44` fica (o workspace não instala `remoto`) e a ferramenta grava `--gravar` com a explicação no commit.
- **Teste que prova:** `tests/test_ci_workflow_regressions.py` lê os dois YAML e afirma que nenhum `jobs.*.env` contém `runner.` (hoje falha em 4 lugares). Depois, `python -m ruff check .` sai 0 e `python -X utf8 ferramentas/auditoria_arquitetura.py --strict` sai 0. O primeiro run do GitHub após o push tem de durar mais de 0 s.
- **Origem:** `scripts.md` #3

### SCR-2 — `testar.py` só roda unittest: 784 testes do remoto e o coordenador inteiro ficam de fora  (médio)
- **Onde:** `testar.py:70-107` (`SUITES`).
- **Defeito:** `unittest discover` não coleta funções pytest, então os testes do app, do delegar, do orquestrador e o `coordenador/`, `esteira_sprites/` e `palco/testes/` inteiros nunca entram no "TUDO VERDE". Os `conftest.py` de `remoto/`, `coordenador/` e `painel/` também não carregam.
- **Conserto:** trocar cada comando por `[PY, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", <pasta>]` e acrescentar as suítes `coordenador`, `esteira_sprites` e `palco/testes`. No CI (`ci.yml`, job `workspace-windows`), o mesmo `python testar.py`.
- **Teste que prova:** `tests/test_testar_cobre_tudo_regressions.py`. Para cada pasta com `test_*.py` fora de `IGNORAR`, afirma que existe uma suíte em `testar.SUITES` cujo comando contém `pytest` e a pasta. Hoje falha em `coordenador` e no motor (`unittest`).
- **Origem:** `scripts.md` #2

### SCR-6 — Tarefa do coordenador: 0x800710E0 a cada 5 min, laço de RestartOnFailure, `tarefas_antigas` para no primeiro erro  (médio)
- **Onde:** `coordenador/__main__.py:44-46` (`xml_tarefa`), `:73-75` (`tarefas_antigas`); `coordenador/supervisor.py:755-758` (`rodar`).
- **Defeito:** o `TimeTrigger PT5M` com `IgnoreNew` faz o Agendador gravar 0x800710E0 a cada 5 min. Medido agora: a tarefa está Running com último resultado 0x800710E0 em 14/10 01:25. Assim uma falha real fica invisível. `rodar()` devolve 1 quando outra instância tem a trava, e com `RestartOnFailure PT1M x999` isso vira relance de minuto em minuto. `tarefas_antigas` usa `check=True` num laço.
- **Conserto:** tirar o `<TimeTrigger>` do XML (fica `LogonTrigger` + `RestartOnFailure`). Em `rodar()`, quando `trava.adquirir()` falha, imprimir "já há um coordenador no ar" e devolver 0. Em `tarefas_antigas`, `check=False` e um resumo por nome (`{nome: returncode}`).
- **Teste que prova:** `coordenador/test_coordenador.py`, três casos: `test_xml_sem_gatilho_de_5_min` (`"PT5M" not in xml_tarefa(sid="")`); `test_rodar_com_trava_ocupada_sai_0` (dubla `TravaUnica.adquirir` como False e afirma retorno 0); `test_tarefas_antigas_segue_depois_de_erro` (o `rodar` dublado falha no primeiro nome e afirma que os três foram chamados).
- **Origem:** `scripts.md` #6

### SCR-P1 — `panorama.auditoria.metas` conta linhas do ledger, não horários  (médio)
- **Onde:** `visao/panorama/auditoria.py:45-67` (`_publicados_hoje`) e `:87` (`metas`).
- **Defeito:** duas linhas no mesmo horário (parte em 2 Shorts, recuperação) pagam dois horários. "13 de 10" esconde horários perdidos, e é esse número que vai ao veredito, à página Auditoria e ao relatório.
- **Conserto:** em `_publicados_hoje`, acumular um `set` com a chave de horário `grade.slot(instante)` (a mesma `conferencia.chave_do_horario` que o `remoto/relatorios.metas` usa desde `9d09759`). Em `metas`, `saiu = min(len(slots), devido)`.
- **Teste que prova:** `visao/tests/test_auditoria_regressions.py::test_duas_linhas_no_mesmo_horario_pagam_um`. Ledger dublado com 3 linhas às 06:37 e relógio às 13:00 (4 vencidos) deve dar `saiu 1, faltando 3`. Hoje dá 3/1. Mais o caso zero: sem linhas, `faltando == devido`.
- **Origem:** `panorama-configs.md` #1

### SCR-P10 — Conferência do Agendador com lista velha e cega a tarefa desligada  (médio)
- **Onde:** `visao/panorama/recursos.py:250-258` (`_agendador`); `remoto/relatorios.py:523` (`_linhas_do_agendador`); `random_builds/builds/tarefas_windows.py:136` (`conferir`).
- **Defeito:** (a) As duas listas diferem entre si e não incluem `NeuralFights_coordenador` nem `NeuralFights_capas_atrasadas`. Desde b1ef6f7, bot, app e Vila são do coordenador e as tarefas deles estão Disabled de propósito. (b) `conferir()` lê só os três ajustes de bateria e não lê `State`, então um `NeuralFights_postar_HH` desligado passa como "confiável".
- **Conserto:** criar uma função única `tarefas_windows.esperadas()` que devolve `{nome: "ligada"|"desligada"}`: `Historias_auto_*`, `gerar_*`, `postar_*`, `coordenador` e `capas_atrasadas` ligadas; `app_celular`, `bot_telegram` e `vila_flutuante` desligadas. Os dois leitores passam a usá-la. `conferir()` acrescenta `$t.State` ao script e devolve `ligada: State != 'Disabled'`. Quando o estado não bate com o esperado, a tarefa vai para `fracas`.
- **Teste que prova:** `visao/tests/test_recursos_agendador_regressions.py::test_postar_desligada_e_fraca`. Dubla `_rodar` com `"False;False;True;Disabled"` para `NeuralFights_postar_17` e afirma que ela está em `fracas`. Mais um teste que afirma que `remoto.relatorios` e `recursos` conferem o mesmo conjunto de nomes.
- **Origem:** `panorama-configs.md` #10

### SCR-P6 — Recursos mede o disco E:, mas quem para a produção é o C:  (médio)
- **Onde:** `visao/panorama/recursos.py:33,45-55` (`_disco`).
- **Defeito:** a tela e o veredito dizem "disco ok" (E: com 57 GB livres) enquanto o C: (13 GB hoje), o disco que `agenda.json`/`geracao.json` vigiam com piso de 5 GB, se aproxima do freio.
- **Conserto:** `_disco()` devolve um dicionário por volume: o do repositório e o `disco_a_vigiar` de `historias/config/agenda.json` e de `random_builds/config/geracao.json`, lidos dos arquivos. Para cada um, o limiar crítico é o `disco_livre_minimo_gb` do próprio config e o "baixo" é esse valor mais 3 GB. O alerta cita o volume.
- **Teste que prova:** `visao/tests/test_panorama_regressions.py::test_disco_vigia_o_volume_do_config`. Dubla `shutil.disk_usage` (C: 4 GB, E: 50 GB) e afirma que o resultado tem `C:/` com situação `critico`.
- **Origem:** `panorama-configs.md` #6

### SCR-P3 — Diário ou ledger ilegível vira "zero" e o veredito fica verde  (médio)
- **Onde:** `visao/panorama/confiabilidade.py:503` (`hoje`: `eventos = lidos or []`) e `:52-60` (`_ledger`: `except: return []`); `visao/panorama/saude.py:53` (`agora`); `visao/panorama/qualidade.py:13` (`_erros_recentes`), por cima de `builds/atividade.py` (`recentes`, `estado_das_fabricas`).
- **Defeito:** quando o diário não abre, o resultado é "0 falhas, fábricas ociosas, 0 erros", igual a um dia calmo. Quando o ledger não abre, sai `prometido 0`. Nenhum alerta aparece.
- **Conserto:** `_ledger` devolve `None` na exceção. `hoje` grava `diario_lido` e `ledger_lido[canal]`, e `_alertas` começa com "não consegui ler o diário (atividade.jsonl)" / "não consegui ler o ledger de X", o que põe o veredito em `atencao`. `saude.agora` e `qualidade.problemas` conferem `sinais.ler_diario() is None` (ou `atividade._arquivo().is_file()`) e devolvem `{"erro": "diário ilegível"}`, que `_seguro` e a Vila mostram como "?".
- **Teste que prova:** `visao/tests/test_confiabilidade_regressions.py::test_diario_ilegivel_nao_e_dia_calmo`. Com `sinais.ler_diario` dublado devolvendo `None`, afirma `veredito != "ok"` e um alerta com "diário". Com `metricas.publicados` levantando `OSError`, afirma um alerta com "ledger". Com `atividade._arquivo` apontando para pasta inexistente, `qualidade.problemas()` tem `erro`.
- **Origem:** `panorama-configs.md` #3 e #4

### SCR-P5 — Veredito ignora a família `producao` com erro  (médio)
- **Onde:** `visao/panorama/auditoria.py:215-216` (`_NOMES`).
- **Defeito:** com `producao` ilegível, o veredito continua "tudo em dia".
- **Conserto:** `_NOMES["producao"] = "a produção"`. Tratar também `historias_incompletas`/`estoque`/`agora` com chave `erro` dentro de `producao` como "não consegui verificar a produção: …".
- **Teste que prova:** `visao/tests/test_verificacao_impossivel_regressions.py::test_producao_com_erro_nao_e_tudo_em_dia`. `veredito({... "producao": {"erro": "x"} ...})["cor"] != "ok"`. Hoje dá `ok`.
- **Origem:** `panorama-configs.md` #5

### SCR-P2 — "Atualizado em" das métricas vem do mtime da marca, inclusive da marca de erro; views só de builds  (médio)
- **Onde:** `visao/panorama/desempenho.py:118-130` (`_quando_atualizou`) e `:49-55` (`_salvas`).
- **Defeito:** `_atualizado_em.json` mora na mesma pasta e é regravado mesmo com a coleta em erro. Por isso a tela diz "atualizado hoje" com a coleta morta. `views`/`retencao` são só de builds, ao lado de um `total` dos dois canais.
- **Conserto:** `atualizado_em` passa a sair de `metricas.ler_marca()` → `partes`, um dicionário por parte com o `ultimo_ok` (nunca mtime). `_salvas` usa `metricas.salvas_de_todos()` e separa `views`/`likes`/`retencao_media` por canal: `{"builds": ..., "historias": ...}`.
- **Teste que prova:** `visao/tests/test_panorama_regressions.py::test_marca_de_erro_nao_atualiza`. Uma pasta temporária com `vid.json` de 2023 e uma marca `{"partes": {"builds": {"estado": "erro"}}}` gravada agora deve dar um `atualizado_em` que não é de hoje. Mais um caso com as métricas de histórias aparecendo sob `historias`.
- **Origem:** `panorama-configs.md` #2
- Obs.: o arquivo mais novo de `random_builds/outputs/_metricas` é de 12/10 07:45. Em 13/10 nem a marca foi gravada, então vale olhar a coleta da noite (parte `metricas`).

### SCR-P8 — Estoque: catálogo quebrado vira "0 prontos"  (médio)
- **Onde:** `visao/panorama/inventario.py:11-26` e `:78-85` (`estoque`).
- **Defeito:** estoque zero e "não consegui contar" são iguais. É o número que a Vila e a Auditoria mostram.
- **Conserto:** `_videos_de_historia` devolve `{"prontos": None, "erro": str(exc)}` na exceção, e `_videos_de_build` faz o mesmo. `estoque` copia `None` e junta `erros: [...]`, e `total` fica `None` se um lado falhou. Na Vila (`remoto/vila_dados._Placar`), `None` aparece como "?".
- **Teste que prova:** `visao/tests/test_panorama_regressions.py::test_catalogo_quebrado_nao_e_zero`. Com `catalogo.listar` levantando, afirma `videos_prontos["builds"] is None` e `"erros"` presente.
- **Origem:** `panorama-configs.md` #8

### SCR-M7 — `prova_ok` False em vídeo que subiu; ids de 07/10 continuam faltando  (médio)
- **Onde:** `random_builds/builds/publicar/metricas.py:729-731` (`reconciliar`, filtro `faltam`) e `:764`.
- **Defeito:** o a34b355 só marca `prova_ok=True` na linha que a reconciliação preenche AGORA. As linhas que já têm `youtube_id` (recuperado antes) e `prova_ok: False` nunca entram em `faltam`. Medido no ledger: 36 de histórias e 12 de builds continuam False com id. Os 3 de 07/10 (`historia_00054:p02`, `00063:p01`, `00061:p03`) seguem sem id, e há mais 2 novos (`historia_00050:p06` em 13/10 22:41 e `historia_00072:p02` em 14/10 00:44) e 1 de builds (`generation_00107:estreia`, 13/10 23:47).
- **Conserto:** em `reconciliar`, depois do laço `casar_ids`, ainda dentro da trava, uma segunda passada marca `prova_ok=True` em toda linha YouTube com `youtube_id` presente que conste da lista `videos` do canal (o id está no canal, então é prova). Ela entra no mesmo `reescrever_ledger`. Para as linhas sem id que `casar_ids` não casa, logar o motivo por linha (título/corte/hora fora da folga) para descobrir por que as de 07/10 nunca casam.
- **Teste que prova:** `random_builds/tests/test_reconciliar_prova_ok_regressions.py`. Um ledger temporário com uma linha `{"youtube_id": "abc", "prova_ok": false}` e `enviados` dublado contendo `abc` deve sair com `prova_ok` True. Hoje continua False, porque `faltam` vem vazio e a função retorna antes.
- **Origem:** `maquina.md` #7

### SCR-9 — Runtime de teste não isola `remoto.config`, `remoto.biblioteca`, `handoff` e `coordenador.estado`  (médio, latente)
- **Onde:** `remoto/config.py:25-27`, `remoto/biblioteca.py:17`, `ferramentas/handoff.py:35`, `coordenador/estado.py:11-20`.
- **Defeito:** com `NEURAL_FIGHTS_RUNTIME_DIR` definido, esses módulos continuam apontando para `C:\Users\adrian\AppData\Local\neural-fights` (medido). O próximo teste sem patch grava em produção. (`historias/contos/publicar/catalogo.py:43` e `ias/correio.py:82` já honram a variável: essa parte do relatório estava errada.)
- **Conserto:** os quatro passam a usar `builds.contas.runtime_dir()`, que honra a variável via `neural_fights.data.database.RUNTIME_DIR`. `coordenador/estado.py` deixa de exigir `PYTEST_CURRENT_TEST`, e `biblioteca.PASTA`/`handoff.LOCAL` viram funções resolvidas tarde, porque hoje são resolvidas no import.
- **Teste que prova:** `tests/test_runtime_isolado_regressions.py` roda um subprocesso com `NEURAL_FIGHTS_RUNTIME_DIR=<tmp>` e afirma que `remoto.config.runtime_dir()`, `remoto.biblioteca.PASTA`, `ferramentas.handoff.LOCAL` e `coordenador.estado.pasta()` ficam todos sob `<tmp>`.
- **Origem:** `scripts.md` #9

### SCR-4 — `postar.py --instalar` cria tarefa com janela preta; `--hora` recria a tarefa antiga  (médio)
- **Onde:** `ferramentas/postar.py:3830` (`instalar`, `/TR f'"{lancador}"'`) e `:5416` (`instalar(args.hora)` sem `nome`).
- **Defeito:** é o único instalador sem `wscript //B oculto.vbs`, e reinstalar volta com 10 janelas pretas por dia. O `--hora` cria `NeuralFights_postar` sem sufixo, a tarefa que `instalar_grade` apaga para não haver postagem dobrada.
- **Conserto:** `"/TR", tarefas_windows.acao_oculta(lancador)`. Em `main`: `instalar(args.hora, nome=nome_da_tarefa(int(args.hora[:2])))`. Acrescentar a opção `--lancador`, que só chama `escrever_lancador()`. Atualizar o docstring de `ferramentas/ocultar_consoles.py:11-13`, onde o único instalador que ainda desfaz é o `postar.py`.
- **Teste que prova:** `historias/tests/test_postar_rodada_segura_regressions.py::test_instalar_usa_wscript_oculto` dubla `subprocess.run` e afirma que o argumento após `/TR` contém `wscript.exe` e `//B` (igual a `remoto/test_remoto.py:588-592`). Mais `test_hora_usa_nome_com_sufixo`: `main(["--instalar","--hora","17:57"])` cria `NeuralFights_postar_17`.
- **Origem:** `scripts.md` #4

### SCR-F1 — `conciliar_tiktok --gravar` decide as linhas antes da trava  (médio)
- **Onde:** `ferramentas/conciliar_tiktok.py:252-254` (leitura e proposta) e `:275-289` (trava + append).
- **Defeito:** duas execuções simultâneas propõem a mesma linha e as duas a gravam. O ledger fica com o mesmo `tiktok_id` duas vezes.
- **Conserto:** dentro do `with travas.trava(...)`, reler `_ledger_lido(caminho)` e `_posts_ja_com_dono` e recalcular `linhas_a_importar` (e o filtro `--so`) antes do append. Se o recálculo der vazio, imprimir "nada novo (outra conciliação já gravou)".
- **Teste que prova:** `ferramentas/manutencao/test_manutencao.py::test_conciliar_duas_vezes_grava_uma` chama `main` duas vezes em sequência com o mesmo arquivo de captura, mas com o ledger lido antes de a primeira gravar (dublando `_ledger_lido` para devolver o estado antigo só fora da trava). Afirma 1 linha no ledger. Hoje dá 2.
- **Origem:** `ferramentas.md` #1

### SCR-F2 — `copiar.py` aceita `..` e escreve fora do destino  (médio)
- **Onde:** `ferramentas/manutencao/copiar.py:40-49` (`copiar`).
- **Defeito:** `destino / "../fora.txt"` sobrescreve um arquivo irmão da árvore principal, sem cópia. Isso só acontece com argumento passado à mão.
- **Conserto:** para cada `rel`, `fonte = (origem / rel).resolve()` e `alvo = (destino / rel).resolve()`. Recusar com `ValueError` se `not fonte.is_relative_to(origem.resolve())` ou `not alvo.is_relative_to(destino.resolve())`, ou se `Path(rel).is_absolute()`.
- **Teste que prova:** `ferramentas/manutencao/test_manutencao.py::test_copiar_recusa_caminho_que_escapa`. `copiar(origem, destino, ["../fora.txt"])` levanta `ValueError`, e o arquivo de fora continua "original".
- **Origem:** `ferramentas.md` #2

### SCR-5 — `remoto --instalar`: mensagem perdida, tarefa diferente da viva e religa o que foi desligado  (baixo)
- **Onde:** `remoto/tarefa.py:63-65` (`_schtasks` com `text=True`) e `:78-100` (`instalar`).
- **Defeito:** sob `-X utf8` a saída do `schtasks` (cp850) não decodifica. Medido: `UnicodeDecodeError` na thread leitora, `stdout ''`, rc 0. O crash que o relatório descreve não reproduz no 3.14, mas a mensagem some. O `/Create /F` também deixaria `PT72H` + `WakeToRun=True` (a viva tem `PT0S`/`False`) e REABILITARIA a `NeuralFights_bot_telegram`, que o Adrian mandou desligar (b1ef6f7: o coordenador é o único gerente).
- **Conserto:** `_schtasks` sem `text=True`, decodificando com `.decode("oem", "replace")`, como `tarefas_noite.py`. Como bot, app e Vila agora são do coordenador, `python -m remoto --instalar` passa a só regravar o `bot.cmd` (`escrever_lancador`) e a dizer que a tarefa não é mais usada. O mesmo vale para `painel/flutuante/tarefa.py --instalar`, que só pode criar a tarefa com um `--forcar` explícito.
- **Teste que prova:** `remoto/test_remoto.py::test_instalar_nao_recria_tarefa_do_bot` dubla `_schtasks` e afirma que nenhum `/Create` é chamado e que o `.cmd` foi escrito. Mais `test_schtasks_decodifica_oem`: o dublê devolve `b"\xcaXITO"` e a mensagem contém "XITO".
- **Origem:** `scripts.md` #5 (e a continuação do `maquina.md` #11)

### SCR-11 — Quatro geradores gravam CR CR LF nos `.cmd`  (baixo)
- **Onde:** `ferramentas/postar.py:3791`, `remoto/tarefa.py:55`, `historias/contos/pipeline/tarefas.py:65`, `coordenador/__main__.py:53`.
- **Defeito:** `write_text` com o texto já em `\r\n` grava `\r\r\n`. O `cat -A` mostra `^M^M$` em `postar.cmd`, `bot.cmd`, `historias/auto.cmd` e `coordenador.cmd`.
- **Conserto:** `with open(destino, "w", encoding=..., newline="") as fh: fh.write(texto)` nos quatro, como `tarefas_noite.py:86`.
- **Teste que prova:** `tests/test_lancadores_crlf_regressions.py` chama cada `escrever_lancador()` (e `coordenador.__main__.instalar` com `rodar` dublado e `CMD` apontado para tmp) e afirma `b"\r\r\n" not in arquivo.read_bytes()`.
- **Origem:** `scripts.md` #11

### SCR-12 — `--saida` sem valor ou `_logs` apagada: a rodada morre sem rastro  (baixo)
- **Onde:** `historias/main.py:703-709` e `random_builds/main.py:236-242` (`_redirecionar_saida`), `ferramentas/postar.py:5689-5694`, `remoto/__main__.py:236-239`, `remoto/api_http.py:2704-2707`.
- **Defeito:** `--saida` no fim manda a saída ao console do Agendador. Com a pasta do log apagada, `open()` levanta antes do `main()` e a saída vai a `NUL`.
- **Conserto:** nos cinco: `Path(arquivo).parent.mkdir(parents=True, exist_ok=True)` antes do `open`. `--saida` sem valor dá `sys.exit(2)` com a mensagem gravada em `atividade.jsonl` (`atividade.registrar(..., status="erro")`).
- **Teste que prova:** `historias/tests/test_saida_regressions.py`. `_redirecionar_saida(["auto", "--saida", str(tmp/"nao_existe"/"x.txt")])` devolve um arquivo aberto e a pasta passa a existir. `["auto", "--saida"]` levanta `SystemExit(2)`. O mesmo em `random_builds/tests`.
- **Origem:** `scripts.md` #12

### SCR-10 — `integridade()` não olha `.cmd` nem `coordenador/ias/palco`; pasta descartável no C:  (baixo)
- **Onde:** `testar.py:58` (`PASTA_DESCARTAVEL`) e `:163-175` (`EXTENSOES_VIGIADAS` e a lista de pastas).
- **Defeito:** o byte de controle num `.cmd` passa sem ser visto, e a suíte escreve no C: cheio.
- **Conserto:** `EXTENSOES_VIGIADAS = ("*.py", "*.bat", "*.cmd")`; varrer todas as pastas da raiz menos `IGNORAR`; `PASTA_DESCARTAVEL = Path(r"E:\tmp_pytest") / "neural-fights-testar"` se `E:\tmp_pytest` existir, senão `tempfile.gettempdir()`.
- **Teste que prova:** `tests/test_testar_cobre_tudo_regressions.py::test_integridade_ve_cmd` grava um `.cmd` com `\x08` numa pasta temporária vigiada e afirma que `testar.integridade()` acusa.
- **Origem:** `scripts.md` #10

### SCR-8 — Histórico do Agendador desligado  (baixo, precisa de admin)
- **Onde:** máquina: `Microsoft-Windows-TaskScheduler/Operational` com `IsEnabled=False` (medido em 14/10).
- **Defeito:** nenhum disparo, recusa ou falha fica registrado, o que impede investigar SCR-1, SCR-6 e SCR-7.
- **Conserto:** como administrador, `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`. Depois, `visao/panorama/recursos.py` lê os eventos 101/103/203 por tarefa.
- **Teste que prova:** n/a (máquina). A verificação é `Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational'` mostrando `IsEnabled True` e `RecordCount` > 0 no dia seguinte.
- **Origem:** `scripts.md` #8

### SCR-M13 — Travas de teste velhas na pasta real de locks  (baixo)
- **Onde:** `%LOCALAPPDATA%\neural-fights\locks\` (93 de 217 arquivos com nome de teste); `random_builds/builds/travas.py:54`.
- **Defeito:** é lixo de 06/10 para trás. Não nasce nenhum novo desde 06/10 01:33, porque o pytest acha o `conftest.py` da raiz (rootdir `E:\projetos`). O caminho que ainda escreveria é um `python -m unittest` direto, sem a variável.
- **Conserto:** apagar os `.lock` com nome `teste_*`, `*duble*`, `*que_nao_existe*`, `*sem_img*` e `perfil-que-nao-existe*` (fora da janela das postagens; travas do SO, então só os sem dono). Em `travas.py`, quando o nome da trava começa com `teste_` e `NEURAL_FIGHTS_RUNTIME_DIR` não está definido, levantar `RuntimeError("trava de teste no runtime real")`.
- **Teste que prova:** `random_builds/tests/test_travas_teste_fora_do_real_regressions.py`. Sem a variável, `travas.trava("teste_x")` levanta. Com a variável, cria o arquivo sob ela.
- **Origem:** `maquina.md` #13

### SCR-P9 — `qualidade._alvos_do_jogo` lê um arquivo que nada escreve  (baixo)
- **Onde:** `visao/panorama/qualidade.py:55`.
- **Defeito:** `relatorio_qualidade.json` não tem escritor, então "nunca avaliado" aparece para sempre.
- **Conserto:** `neural_fights/tools/qualidade_luta.py` grava `RUNTIME_DIR/relatorio_qualidade.json` ao terminar. Se ninguém for gravar, o campo sai do panorama e da página Auditoria.
- **Teste que prova:** `visao/tests/test_panorama_regressions.py::test_alvos_do_jogo_tem_escritor` faz grep no repositório por `relatorio_qualidade.json` fora de `visao/` e afirma pelo menos um escritor.
- **Origem:** `panorama-configs.md` #9

### SCR-PT — Chaves de config sem leitor, com padrão diferente ou lidas no lugar errado  (baixo)
- **Onde:** a tabela de `panorama-configs.md` (24 chaves). Amostra reconferida: `historias/config/publicacao.json` `um_clique.tiktok` sem leitor (`serie.py:207` só lê `tiktok_partes_por_clique`); `agenda.json` `piso_de_estoque` sem leitor; `ias/config.json` `rodizio_imagem` com padrão `["gemini","chatgpt","picasso"]` em `ias/imagem.py:206` (o Picasso volta se a chave sumir); `random_builds/config/publicacao.json` `tiktok.postar_automatico` ignorado pela grade (`postar.py:3767`).
- **Defeito:** mudar essas chaves não muda nada, ou muda só se a chave sumir.
- **Conserto:** (1) Tirar as chaves sem leitor (lista da tabela), ou documentá-las com `_comment`. (2) Igualar o padrão do leitor ao arquivo em `ias/imagem.py:206` (`["gemini","chatgpt"]`), `agenda.py:478/1809` (`reparos_por_rodada`, um padrão só), `voz.py:PADRAO` e `noite.py:1106`. (3) `coordenador/servicos.json` `saude` vira comentário (`_saude`).
- **Teste que prova:** `tests/test_config_chaves_regressions.py` carrega cada config da tabela e afirma que toda chave não `_comment*` aparece em pelo menos um `.py` fora de `tests/`, com uma lista de exceções explícitas.
- **Origem:** `panorama-configs.md` (tabela "Chaves de configuração com problema")

### SCR-F3 — `obsidian.py` sai 0 também na falha  (baixo)
- **Onde:** `ferramentas/obsidian.py:514` (`main`).
- **Defeito:** `return 0 if funcoes[args.acao]() else 0`.
- **Conserto:** `return 0 if funcoes[args.acao]() else 1`.
- **Teste que prova:** `ferramentas/manutencao/test_manutencao.py::test_obsidian_cofre_ausente_sai_1`. `obsidian.main(["--cofre", str(tmp/"ausente"), "diario"]) == 1`.
- **Origem:** `ferramentas.md` #3

---

## Já consertados
- `maquina.md` #6 (parecer/agenda sem `remoto`) → `a34b355` (`agenda.py:42-44` + `AgendaAchaORemotoTests`)
- `maquina.md` #11 (tarefas app/bot 0x1, `retomar_codex`) → decisão `b1ef6f7`, executada na máquina: as três tarefas estão Disabled e `retomar_codex` foi apagada. Sobram `outputs/retomar_codex.{cmd,py,txt}`.
- `maquina.md` #12 (`>>` nos .cmd) → `a34b355` (geradores + `app_celular.cmd`; `postar.cmd`/`bot.cmd` regravados em 12/10)
- `maquina.md` #18 (`postar.txt` sem data) → `a34b355` (`_SaidaDatada`, `postar.py:82`)

## Alarmes falsos
- `maquina.md` #10 (capa 403 gastando cota): já estava consertado em `6a18d94` (05/10). O `capa_bloqueada()` pula o resto do dia depois de um 403, e o "151x" é o mesmo número citado nesse commit.
- `maquina.md` #17 (10053 com traceback): já estava consertado em `9989b80` (05/10, `CLIENTE_SAIU`). O último traceback é de 05/10, como o próprio relatório dizia.
- Parciais (seguem ABERTOS no resto): `scripts.md` #5 "crasha" (no 3.14 não levanta; só perde a mensagem); `scripts.md` #9 em `catalogo.py` e `ias/correio.py` (os dois já honram a variável).

## Decisões que são do Adrian
- SCR-1: logon automático + bloqueio de tela, ou só o aviso de "PC religou" (que precisa da senha dele numa tarefa "conectado ou não").
- SCR-8: ligar o histórico do Agendador (precisa de admin).
- SCR-P7: a visibilidade do ledger deve ser a do config ou a do laudo do publicador (a recomendação é a do laudo).
- SCR-PT: o `tiktok.postar_automatico: false` dos builds deve valer também para a grade, ou a chave sai (hoje a grade posta sempre).

## Operação (não é código) — medido em 14/10/2026 ~01:30, sem mudar nada
- **DNS da operadora** (maquina #1): **resolvido.** `Get-DnsClientServerAddress` → Ethernet `1.1.1.1, 8.8.8.8` (Wi-Fi idem).
- **Gemini deslogado** (#2): **não dá para afirmar sem abrir o perfil.** A última queixa de login é de 11/10 (`auto_20261011.txt`, 1 linha, e o diário em 11/10 17:28Z). Em 12/10 houve 2 respostas do Gemini, em 13–14/10 nenhuma, e nenhuma queixa de login ou cota.
- **Cota/Flash do Gemini** (#3): 0 "Poderei criar mais imagens" e 0 "Gemini (Flash)" nos logs de 12–14/10. A decisão `b339bbb` (pular para DeepSeek/ChatGPT e avisar) é de 13/10 e não tem código ainda (parte historias).
- **Lixo em disco** (#14, decisão `ad54bf7` "apagar tudo isso"): **executada em parte.** Os 5 arquivos soltos da raiz sumiram; `git worktree list` caiu de 77 para 60; em `E:\projetos-wt` sobram 4 pastas fora do worktree list (`_lixo_codex`, `_pytest_app`, `_prova_fila_full.txt`, `_prova_fila_t9.txt`); `E:\tmp_pytest` continua com 7.823 entradas e as worktrees destacadas `wt_bsp`/`wt_pub`; 1 stash. O handoff diz "lixo com admin" pendente.
- **`main` atrás** (#15, decisão `d421b98`): **executada.** `main` foi resetado para `d6aedb4` (13/10) e hoje está 15 commits atrás e 0 à frente de `refactor/arquitetura`.
- **Push** (decisão `144cd45` "enviar main e refactor"): **executada.** `origin/main = d6aedb4` e `origin/refactor/arquitetura = f670aa9` (0 à frente). Os runs desse push falharam em 0 s (ver SCR-3).
- **Reiniciar só quando pedido** (decisão `9cec584`): **só decidida.** O código do `refactor/arquitetura` ainda reinicia por código mudado; o conserto está no ramo WIP não mesclado (SCR-M8).
- **Desligar as três tarefas e apagar `retomar_codex`** (decisão `b1ef6f7`): **executada** (ver "Já consertados").
- **Uso do Claude** (#19): `orquestrador/uso.json` → sessão 23 %, semana 44 %, `allowed` (era 88 % em 11/10). `max_paralelo` continua 6.
- **Chrome** (#20): agora **155.0.8059.79** (era 154), com o patchright feito para o chromium 151, 4 versões atrás. Funciona, mas vale vigiar.
- **Disco:** C: 13 GB livres (piso de 5 GB), E: 57 GB.
- **PC religou** em 13/10 22:43 (`LastBootUpTime`). A postagem das 23:37 saiu (log 23:40), então alguém entrou. Não fica rastro de quanto tempo ficou parado (SCR-8).
