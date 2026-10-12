# Auditoria profunda — Painel: casca e páginas — 12/10/2026

Fatia: `painel/*.py`, `painel/paginas/**`, `painel_ui.py` e os testes da casca
(`test_painel.py`, `test_confiabilidade_grade.py`, `test_conftest_tk.py`,
`test_tcl.py`, `conftest.py`). A Vila flutuante e `painel/sprites/**` ficaram
de fora (já auditadas). Só relatório: nenhum arquivo do projeto foi alterado
além deste.

Provas rodadas com dublês (`panorama.resumo` vazio, `Supervisor.tarefa` e
`Supervisor.rodar` sem efeito — nenhum comando real, nenhuma leitura pesada),
em pasta temporária da sessão; as fotos são `PrintWindow` da janela montada
de verdade (`painel.prova`). Scripts: `prova_layout.py` e `prova_pontual.py`
no scratchpad da sessão. Os CLIs externos foram conferidos lendo o argparse
de cada `main.py`; o único comando executado fora dos dublês foi
`main.py identity login --provedor grok`, que o argparse recusa antes de
qualquer ação (prova do item 3).

## Examinado

- `painel_ui.py` — 0 funções; atalho que chama `painel.__main__.main`.
- `painel/__init__.py` — 0 funções; só a docstring do pacote.
- `painel/__main__.py` — 4 funções (`_fumar_uma`, `_fumar`, `_prova`, `main`); CLI, smoke por processo e prova de tela.
- `painel/app.py` — 25 funções/métodos; a `Casca`: barra lateral, páginas por `place`, console em gaveta, faixa do freio da pipeline, pulsos do `panorama` e da pipeline.
- `painel/janelas.py` — 8 funções; `JANELAS`, `montar`, `abrir` (pythonw destacado), `abrir_flutuante`, `abrir_guia`.
- `painel/processos.py` — 18 funções/métodos; `Supervisor` (fila única, `rodar`, `tarefa`, `_drenar`, `parar_tudo`) e `Periodico`.
- `painel/widgets.py` — 16 métodos; a `Oficina` de widgets (rótulo, cartão, botão, campo, combo, marcador, zona de perigo, tabela, `aplicar_ttk`).
- `painel/estilo.py` — 6 funções/métodos; os dois temas e as escalas.
- `painel/prova.py` — 3 funções; foco e `PrintWindow`.
- `painel/arrastar.py` — 9 funções/métodos; WM_DROPFILES por ctypes.
- `painel/conftest.py` — 4 funções; raiz Tk da sessão, skip quando o Tcl não acha a biblioteca, Ateliê vazio.
- `painel/paginas/__init__.py` — 0 funções; o contrato de página.
- `painel/paginas/auditoria.py` — 11 funções; os quatro controles e a fila (só histórias) de `panorama.auditoria`.
- `painel/paginas/confiabilidade.py` — 12 funções; provado/sem prova/válvula/conferência.
- `painel/paginas/contas.py` — 14 funções; registro de contas, login por serviço, OAuth.
- `painel/paginas/experimentos.py` — 27 funções/métodos; experimentos A/B e o `Dialogo` modal.
- `painel/paginas/extras.py` — 31 funções/métodos; Torneio, Reações, Áudio.
- `painel/paginas/fluxo.py` — 10 funções; tabela de etapas de `builds.pipeline.fluxo`.
- `painel/paginas/historias.py` — 16 funções; roteiro, lista, publicar série.
- `painel/paginas/jogo.py` — 19 funções/métodos; Simulação, Database, Live.
- `painel/paginas/mimetizar.py` — 21 funções; Espelho (catalogar, absorver, bíblia, preset).
- `painel/paginas/oficina.py` — 84 funções/métodos; a Oficina de sprites (a parte Tk; o motor em `painel/sprites/` ficou fora).
- `painel/paginas/publicar.py` — 33 funções/métodos; lista unificada, texto, onde postar, envio.
- `painel/paginas/videos.py` — 32 funções/métodos; gerar, re-renderizar, identidade, retenção, galeria, escolher atributos.
- `painel/paginas/vila.py` — 17 funções; o hub: placar, outras janelas, paralelismo, diário.
- `painel/test_painel.py` — 81 funções/classes de teste; contratos da casca, varreduras por AST, CLI × argparse.
- `painel/test_confiabilidade_grade.py` — 6 funções; `_linha_da_conferencia`.
- `painel/test_conftest_tk.py` — 2 funções; o skip do Tcl.
- `painel/test_tcl.py` — 2 funções; a raiz Tk da sessão.

Total: 29 arquivos, 511 funções/métodos/classes lidos função por função.

Conferidos por fora (só leitura, para saber se cada botão aponta para algo que existe): os argparse de `random_builds/main.py`, `historias/main.py`, `mimetizar/main.py`, `neural_fights/cli/{main,headless,roster,live,tournament}.py`, `neural_fights/tools/youtube_oauth.py`, `builds/publicar/{youtube_web,tiktok}.py`; as funções de `builds.contas`, `builds.identity.controle`, `builds.pipeline.fluxo`, `builds.experimentos`, `builds.publicar.{catalogo,metricas,conferencia,youtube}`, `builds.generation.escolhas`, `builds.atividade`, `builds.assets`, `neural_fights.effects.audio_paths`, `contos.pipeline.controller.Pipeline.listar`, `contos.publicar.catalogo.resumo`, `espelho.{status,absorver,baixar,config}`, `panorama.{resumo,auditoria}`, `remoto.__main__` (trava de instância do bot).

## Confirmados (do mais grave ao menos)

### 1. A caixa "TikTok" da página Publicar diz que posta e não posta — gravidade: alta

- Onde: `painel/paginas/publicar.py:180-183` (legenda "o TikTok posta de verdade, sem confirmação") e `:446-464` (`enviar`).
- O defeito: `enviar()` monta `main.py publicar <id> --youtube --tiktok --visibilidade X` sem `--postar`. Em `random_builds/main.py:147` isso vira `tiktok.publicar(video, postar=None)`, e `tiktok.publicar` (`builds/publicar/tiktok.py:581-582`) resolve `None` pelo config: `postar_automatico`, que em `random_builds/config/publicacao.json:60` é `false`. A ajuda do próprio CLI diz: `--tiktok` "abre o navegador e sobe; NAO publica sozinho"; `--postar` "no TikTok, clica em publicar no fim". O painel promete o contrário do que manda.
- Quando acontece: toda vez que o Adrian marca TikTok e aperta PUBLICAR no painel. O vídeo sobe e fica parado na tela do TikTok sem o clique final; se ninguém clica, não sai (o mesmo mecanismo dos rascunhos de 15/09, agora na outra plataforma).
- Prova: leitura dos três pontos acima (`publicar.py:450-464`, `main.py:147`, `tiktok.py:562-582`, `publicacao.json:60`). O caminho das histórias é diferente e passa `postar=True` à mão (`historias/main.py:485`), por isso a série do botão "Publicar série" não tem esse defeito.
- Conserto sugerido: ou acrescentar `--postar` quando `var_tt` estiver marcada (é o que a legenda promete e a decisão de 31/08 pede), ou trocar a legenda para "sobe e PARA antes de postar". Não deixar os dois discordando.

### 2. As janelas abrem em 1000×600 e o `pack` corta os botões de ação de seis páginas — gravidade: alta

- Onde: `painel/app.py:71` (`minsize(1000, 600)`, sem `geometry`), `painel/app.py:297-301` (as páginas entram por `place(relwidth=1, relheight=1)`, que não propaga tamanho) e `painel/__main__.py:117-119` / `ferramentas/abrir.py` (nenhum `geometry`/`zoomed`).
- O defeito: como a área de conteúdo não pede tamanho, a janela nasce no mínimo, 1000×600, e não na tela de 1366×768. Nesse tamanho a área útil da janela de criação tem 534 px e o `pack` corta em silêncio o que entrou por último — que em quase toda página é a fileira de botões. Medido com a janela montada de verdade (`prova_layout.py criacao natural`):
  - Fluxo: cortada a fileira `▶ Assistir · 📁 Pasta · 🔁 Re-renderizar · 🧩 Enfileirar identidade · ⬇ Processar fila` e a legenda.
  - Publicar: cortados o botão `📋 Copiar`, o cartão inteiro de ONDE POSTAR (YouTube/TikTok/contas/visibilidade/PUBLICAR) e o rodapé (Assistir/Pasta/Exportar/logins/métricas). Foto: `foto_natural_publicar.png` — o cartão aparece só o título, sem conteúdo.
  - Experimentos: cortada a fileira `Ativar · Encerrar · Marcar vídeos · Apagar`.
  - Vídeos de Build: cortados `🔎 Auditar origem`, a linha de voz/`💾 Salvar ajustes`/`🎵 Gerar trilha`, o cabeçalho e a tabela inteira de VÍDEOS PRONTOS.
  - Histórias: cortados `🔑 Login no LLM` e a fileira `Gerar tudo · Só imagens · Só vídeo · Assistir · Pasta · Publicar série`.
  - Contas: cortada a fileira `Usar esta conta · Nova conta · Entrar/Autorizar · Esquecer` e a ajuda.
  - Oficina de sprites: cortados o botão de vista `Folha final`, o combo de fundo e o cursor (foto `foto_oficina_oficina.png`).
  - Jogo e Vila: nada cortado.
- Quando acontece: em toda abertura pelo `painel.bat`, pela Vila ou por `python -m painel`, até ele maximizar à mão. É a lei nº 1 da sessão ("já houve botão fora da tela") voltando pela porta do tamanho inicial; os testes só medem em `1366x740`.
- Prova: `prova_layout.py` (dublês; mede `winfo_ismapped` de todo widget com gerenciador) → `"tamanho": [1000, 600]` nas quatro janelas; lista de cortados acima; fotos no scratchpad.
- Conserto sugerido: na `Casca`, depois de montar, abrir com `geometry` igual à tela disponível (ou `state("zoomed")`), e deixar `minsize` só como piso; e dar às páginas longas (Vídeos, Publicar, Histórias) rolagem como a Oficina tem.

### 3. Vídeos de Build não cabe nem maximizada: a galeria de vídeos prontos some — gravidade: alta

- Onde: `painel/paginas/videos.py:43-49` (cinco blocos empilhados por `pack`, sem rolagem) e `:235-262` (`_galeria`).
- O defeito: a página pede 971 px de altura e a área maximizada em 1366×768 tem 631. O `pack` corta a linha `Voz · 💾 Salvar ajustes · 🎵 Gerar trilha` do cartão de retenção e a seção inteira "VÍDEOS PRONTOS" (cabeçalho com ↻/Pasta/Normal/Celular e a tabela). O duplo-clique "assiste", o botão "Re-renderizar" (que depende do combo alimentado pela galeria) e o salvar da retenção ficam sem como ser usados nessa página.
- Quando acontece: sempre, na tela dele, mesmo maximizada.
- Prova: `prova_layout.py criacao 1366x697 - videos` → cortados `Frame:['Voz:', '💾 Salvar ajustes', '🎵 Gerar trilha']`, `Frame:['VÍDEOS PRONTOS', …]`, `Treeview`. Foto: `foto_max_videos.png` (a página termina no cartão Retenção, cortado no meio das caixas).
- Conserto sugerido: a página precisa de rolagem (o `_area_rolavel` que ela mesma já tem para a janela de atributos serve) ou de ganhar os botões de ação fixos no rodapé, como Confiabilidade faz.

### 4. Panorama com erro vira placar "0 publicados · 0 prontos · 0 problema(s)" na Vila e "0 na fila" no Fluxo — gravidade: alta

- Onde: `painel/app.py:313-319` (`_entregar_resumo` entrega qualquer coisa à página, inclusive `{"erro": …}`), `painel/paginas/vila.py:705-737` (`atualizar`) e `fluxo.py:107-137`.
- O defeito: `Supervisor.tarefa` converte exceção em `{"erro": "…"}`, mas a casca não olha a chave e cada `atualizar(resumo)` faz `resumo.get("saude") or {}` — todo número vira zero e nenhuma cor muda. O hub passa a dizer que não há nada trabalhando e nenhum problema justamente quando não conseguiu ler. A mesma coisa no diário: `vila._aplicar` descarta o erro e deixa a caixa como estava.
- Quando acontece: `panorama.resumo()` estourando (ledger ilegível, import quebrado, disco cheio) ou a família inteira falhando. Também quando uma família devolve `{}`: Confiabilidade desenha "✓ 0/0 com prova — nada fora do lugar" em verde para `confiabilidade: {}`.
- Prova: `prova_pontual.py placar` →
  `A1 vila placar com panorama em erro -> '📤 0 publicados · 🎬 0 prontos · ⚙ 0 trabalhando · ⚠ 0 problema(s)'`,
  `A3 fluxo cartoes -> '0 na fila · 0 gerando · 0 com falha…'`,
  `A6 confiabilidade com familia {} -> '✓ 0/0 com prova — nada fora do lugar' fg=#6ee7a0`.
- Conserto sugerido: em `_entregar_resumo`, se `dados.get("erro")`, registrar no console e passar à página um sinal de "ilegível" (ou não chamar `atualizar`), e nas páginas tratar o caso zero/vazio como "não li", nunca como calma — a regra que a flutuante já ganhou em 11/10 (`f143cf5`).

### 5. "Entrar / Autorizar" do Grok na página Contas manda para um login que não existe — gravidade: média

- Onde: `painel/paginas/contas.py:214-247` (`entrar`): chatgpt/gemini/deepseek vão para `historias/main.py llm login`; "youtube", "youtube_web" e "tiktok" têm caminho próprio; tudo o mais cai no `else` → `random_builds/main.py identity login --provedor <servico>`.
- O defeito: `builds.contas.SERVICOS` tem `grok` (desde a decisão `ias-grok-acesso`), mas `identity login` só aceita `digen, dreamface, picasso` (`builds/identity/config.py:28`). O clique dispara um subprocesso que o argparse recusa; o erro só aparece na gaveta do console, com código 2, e nada abre. O login do Grok existe em `historias/main.py llm login --provedor grok` (choices incluem grok), que o `else` não usa.
- Quando acontece: linha Grok selecionada em Contas → Entrar/Autorizar.
- Prova: `python -X utf8 main.py identity login --provedor grok --canal builds` em `random_builds/` → `error: argument --provedor: invalid choice: 'grok' (choose from digen, dreamface, picasso)`, exit 2 (o argparse recusa antes de qualquer ação).
- Conserto sugerido: incluir `grok` no ramo das histórias (`("chatgpt", "gemini", "deepseek", "grok")`) e, para o `else`, só aceitar o que está em `PROVEDORES`; o resto avisa na hora em vez de morrer no console.

### 6. Nenhum botão trava o duplo clique: dois cliques = dois processos (inclusive PUBLICAR) — gravidade: média

- Onde: `painel/processos.py:46-65` (`Supervisor.rodar`) e todos os botões que o chamam (`publicar.enviar`, `videos.gerar/lote/rerender`, `fluxo.processar_fila`, `historias.gerar/publicar_serie`, `mimetizar.absorver`, `experimentos.atualizar_metricas`, `contas.entrar`, `jogo.*`, `extras.*`).
- O defeito: `rodar` sempre faz `Popen`; não há "já está rodando com este rótulo" nem desabilitar o botão até o `fim`. No publicar não há trava de conta no caminho (`grep travas` em `main.py`, `youtube.py`, `tiktok.py`, `youtube_web.py` não acha nada), e a guarda do ledger não vê um upload que ainda está em andamento.
- Quando acontece: clique duplo acidental, ou clique repetido porque "não aconteceu nada" (a gaveta abre, mas o botão não muda de estado). Para `publicar`, `metricas --atualizar` e `identity worker` o segundo processo escreve nos mesmos arquivos.
- Prova: `prova_pontual.py duplo` → `D1 dois cliques no mesmo botao -> processos vivos: 2`.
- Conserto sugerido: `Supervisor.rodar` recusar (ou enfileirar) rótulo igual ao de um processo vivo, e os botões de ação ganharem `state="disabled"` entre o `cmd` e o `fim`.

### 7. "Parar" mata só o filho direto; Chrome/ffmpeg/worker netos continuam — gravidade: média

- Onde: `painel/processos.py:131-141` (`parar_tudo` → `processo.kill()`), botão em `app.py:220-222`.
- O defeito: `kill()` é `TerminateProcess` do `python main.py …`; o que ele abriu (patchright/Chrome do login, ffmpeg do render, o worker) fica órfão e segue escrevendo, agora sem ninguém lendo a saída. O painel diz "parei 1 processo(s)".
- Quando acontece: qualquer "Parar" durante render, upload ou login.
- Prova: `prova_pontual.py duplo` → `D2 Parar: neto 5344 continua vivo = True` (um filho que abriu um neto; após `parar_tudo()` o neto ainda estava no `tasklist`).
- Conserto sugerido: encerrar a árvore (`taskkill /T /PID` ou Job Object), e dizer na gaveta o que foi morto.

### 8. A conferência do canal falha e a tela nunca diz — gravidade: média

- Onde: `painel/paginas/confiabilidade.py:116-121` (`conferir`): `tarefa(_conferir, lambda _r: self.recarregar(), …)`.
- O defeito: o valor devolvido por `_conferir` — que é `{"erro": …}` quando `conferir_tudo` estoura (token vencido, sem rede) — é jogado fora; o callback só recarrega a ficha, que volta como estava. A faixa passa de "conferindo o canal…" para a leitura normal, e o cartão CONFERÊNCIA continua mostrando a conferência anterior.
- Quando acontece: OAuth vencido, YouTube fora, rede caída — o cenário em que o botão mais seria usado.
- Prova: `prova_pontual.py conferencia` (tarefa dublada entregando `{"erro": "HttpError: token expirado"}`) → `B1 faixa: 'lendo…'`; nenhuma linha de erro chega ao console.
- Conserto sugerido: o callback olhar `erro` e escrever na faixa/console antes de recarregar.

### 9. O erro do Fluxo some no pulso seguinte (≤4 s) — gravidade: média-baixa

- Onde: `painel/paginas/fluxo.py:139-145` (`_desenhar_tabela` escreve o erro em `_alerta`) e `:134-136` (`atualizar` reescreve `_alerta` com `""` quando o panorama não traz alerta, sem devolver a cor).
- O defeito: a mensagem "não consegui ler o fluxo: …" vive no mesmo rótulo que o alerta do panorama; o pulso de 4 s a apaga e deixa o rótulo vermelho e vazio. A tabela fica velha sem aviso.
- Prova: `prova_pontual.py placar` → `A4 'não consegui ler o fluxo: RuntimeError…'` e, depois de um `atualizar({})`, `A5 '' fg=#fb8a8a`.
- Conserto sugerido: rótulo próprio para o erro da leitura (ou não sobrescrever quando há erro pendente).

### 10. Histórias que não carregam somem da lista de Publicar sem aviso — gravidade: média-baixa

- Onde: `painel/paginas/publicar.py:237-243` (`_ler`): `except Exception: historias = []`.
- O defeito: qualquer falha em `contos.publicar.catalogo.resumo()` (roteiro ilegível, import quebrado no projeto das histórias) vira lista vazia; a página mostra só builds e nenhuma linha de erro. "Não cabe" e "não existe" ficam iguais — exatamente o que a lei nº 1 proíbe.
- Prova: `prova_pontual.py historias` (resumo dublado estourando) → `F1 -> {'itens': [], 'publicados': {}} | tem 'erro'? False`.
- Conserto sugerido: guardar a exceção em `dados["avisos"]` e registrar na gaveta.

### 11. `encerrar()` não desliga o pulso do freio da pipeline; o `after` dispara depois do `destroy` — gravidade: baixa

- Onde: `painel/app.py:347-363` (`encerrar`): desliga `_pulso` e o supervisor, mas não `_pulso_pipeline` (criado em `:83-87`).
- O defeito: o docstring diz "Desliga TUDO", mas a faixa da pipeline continua agendada; quando outro interpretador Tk gira no mesmo processo (testes, `--smoke`), o callback cai em "invalid command name …_bater". Em produção o processo acaba junto com a janela, então o efeito é ruído de fechamento e saída suja nos testes da janela de criação.
- Prova: `prova_pontual.py pulso` → `C1 depois de encerrar(): pulso panorama ligado= False | pulso pipeline ligado= True agendado= True`; a execução seguinte imprimiu `invalid command name "…_bater" ("after" script)`.
- Conserto sugerido: `if self._pulso_pipeline: self._pulso_pipeline.desligar()` em `encerrar`.

### 12. O botão da vista ativa da Oficina perde o destaque ao passar o mouse — gravidade: baixa

- Onde: `painel/widgets.py:120-121` (`botao`: `<Leave>` sempre volta a `bg=fundo` capturado na criação) contra `painel/paginas/oficina.py:779-784` (`_pintar_vista` pinta o ativo com `acento_fundo`).
- O defeito: entrar e sair do botão "Limpa + grade"/"Original"/"Folha final" apaga a marca de qual vista está ativa, até a próxima `_pintar_vista`. Fere a regra "o acento é do que está ativo".
- Prova: `prova_pontual.py hover` → `bg antes= #33240f (acento_fundo) | depois de passar o mouse= #2b2219`.
- Conserto sugerido: o `<Leave>` restaurar o `bg` atual (lido no `<Enter>`) em vez do capturado na criação.

### 13. Testes da casca leem dados reais do disco (só leitura) — gravidade: baixa

- Onde: `painel/test_painel.py` `GavetaTests`/`FreioDaPipelineTests` (`Casca.criar([fluxo.Pagina])` → `ao_mostrar` → `regra.snapshot(limite=14)` varre `random_builds/outputs/generation_*` de verdade; `pipeline=True` → `controle.estado()` lê o `controle.json` real); `painel/test_oficina_sprites.py:427` (`janelas.montar("oficina")` carrega o jogo para listar elementos e estilos).
- O defeito: o dublê de `574e8a8` cobre só `panorama.resumo`; `fluxo.snapshot` e `controle.estado` seguem reais. Nada é escrito, mas o tempo do teste e o resultado dependem do estado da máquina (o `_fechar` que estourou 60 s em 08/10 era isto), e um `outputs/` corrompido derruba teste de layout.
- Prova: leitura de `fluxo.py:98-101` (`recarregar` em `ao_mostrar`) e `app.py:83-87`; nenhum `patch` para eles em `test_painel.py`.
- Conserto sugerido: dublar `builds.pipeline.fluxo.snapshot` e `builds.identity.controle.estado` no `setUpModule`, como já se faz com o panorama.

### 14. Combo do freio não conhece o alvo "correio" que a CLI aceita — gravidade: baixa

- Onde: `painel/app.py:153-155` (`["tudo", "picasso", "digen"]`) contra `random_builds/main.py:457` e `:613` (`choices=("tudo", "correio", "digen", "picasso")`).
- O defeito: a pausa por "correio" só existe na linha de comando; pelo painel não dá para pausar esse provedor. Além disso a página Vídeos ainda oferece "Login no PicassoIA"/"Login no Digen" e "Vídeo do payoff (Digen)" depois das decisões `picasso-fora-da-roda` e `digen-plano-free` — botões para uma roda que o Adrian desligou (não é defeito de código; fica registrado para quem decide o que a tela mostra).
- Prova: leitura dos dois pontos.
- Conserto sugerido: ler as opções do próprio `controle`/CLI em vez de lista escrita na tela.

## Não confirmados

- `after()` de thread: nenhum. Só `Supervisor._drenar`/`encerrar` e `Periodico` tocam em `after`, sempre na thread do Tk; toda leitura de fundo passa por `tarefa()` e os callbacks chegam pela fila (`SupervisorTests.test_a_tarefa_entrega_na_thread_da_interface` cobre). A Oficina usa `Periodico` de 60 ms para ler os arquivos soltos — na thread certa.
- Comando com caminho com espaço sem aspas: nenhum. Todo disparo é lista para `Popen` (sem shell), e `os.startfile` recebe `Path`.
- cp1252 no console: o `Supervisor` lê o filho com `encoding="utf-8", errors="replace"` e todo filho roda com `-X utf8`; a gaveta é um `Text` do Tk. O único cp1252 encontrado foi no meu próprio script de prova (`tasklist`), não no painel.
- Botão cujo callback não existe / função pública sem chamador: nenhum. Todos os `command=` apontam para métodos existentes; `abrir_escolhas` (o "escolher atributos" perdido em 09/2026) está ligado e `catalogo()` traz `genero`; o freio da pipeline está na faixa da janela de criação. Todo subcomando e bandeira que as páginas mandam existe no argparse correspondente (`generate-video`, `identity run/worker/login/queue/doctor/status/auditar`, `tournament`, `fight`, `arena ranking`, `import-reactions`, `reactions`, `publicar`, `metricas --atualizar`, `trilha`; `historias`: `prompt/roteiro/gerar/llm login/imagens/video/tudo/publicar`; `mimetizar`: `canal/absorver/biblia/preset/llm login`; `neural_fights.cli.{main --sim/--test, tournament, headless, roster, live}` e `tools.youtube_oauth --com-upload/--com-analytics/--out`), com a exceção do item 5.
- Página Auditoria com builds na fila: a fila de `panorama.auditoria.qualidade` é só de histórias (`auditoria.py:150-152`), então `main.py video <id>` em `historias/` está certo para toda linha.
- "Bot do celular" na Vila abrindo um segundo bot: `remoto.__main__` tem trava de instância única (`remoto__bot`, `esperar=0.0`), o segundo sai avisando.
- Ids da página Publicar × ledger das histórias: `contos.publicar.catalogo.resumo()` devolve `id = v.id` e `serie.py:101` grava `video_id = video.id` — casam.
- `EstadoSemDonoTests`/`WidgetSemTelaTests`/`ComandosDaUITests` continuam cobrindo o que foi perdido antes (estado lido sem escritor, tabela sem `pack`, bandeira que o CLI não aceita); rodados mentalmente contra o código atual, nada novo cairia neles — o que escapa deles é o tamanho da janela (itens 2 e 3), que nenhum teste mede.
