# Consertos — painel-e-vila (PNL)

- **Parte:** painel-e-vila (painel/, painel/flutuante/, Oficina de sprites, esteira_sprites; o relatório `sprites.md` também cobre `mimetizar/`)
- **Relatórios de origem:** `painel-flutuante.md` (4), `painel-paginas.md` (14), `sprites.md` (5)
- **Contagem:** 23 abertos · 0 consertados · 0 falsos (verificado em 14/10/2026 no ramo refactor/arquitetura; nenhum arquivo citado mudou depois de 11/10)
- **Esteira de sprites DESLIGADA:** nenhum defeito confirmado é da esteira em si. Os 5 do `sprites.md` são todos do Mimetizar. Só o PNL-20 depende de um `.json` que só a esteira grava, e por isso fica com gravidade baixa.

---

### PNL-1 — Duplo clique dispara dois processos, inclusive PUBLICAR  (alto)
- **Onde:** `painel/processos.py:50` (`Supervisor.rodar`). Os chamadores são `publicar.enviar`, `videos.gerar/lote/rerender`, `fluxo.processar_fila`, `historias.gerar/publicar_serie`, `mimetizar.absorver`, `experimentos.atualizar_metricas`, `contas.entrar`, `jogo.*` e `extras.*`.
- **Defeito:** `rodar` sempre faz `Popen`, sem checar se já há um processo vivo com o mesmo rótulo. O `main.py publicar <id>` não tem guarda de "já publicado", e `youtube.publicar_como_configurado` também não olha o ledger. Assim, um segundo clique em PUBLICAR pode subir o mesmo vídeo duas vezes: na API, sem trava nenhuma; no navegador, depois dos 90 s de espera pela trava do perfil.
- **Conserto:** em `Supervisor.rodar`, guardar `{rotulo: processo}`. Se já existir um processo vivo (`poll() is None`) com o mesmo rótulo, não abrir outro e registrar `"já está rodando: <rotulo>"` na gaveta. Também acrescentar o parâmetro opcional `botao=` em `rodar`: ele põe o botão em `state="disabled"` no disparo e o devolve a `"normal"` no `fim` (onde hoje se chama `depois`). Em `publicar.enviar`, passar `botao=self.btn_enviar`.
- **Teste que prova:** em `painel/test_painel.py`, `SupervisorTests.test_rotulo_vivo_nao_dispara_de_novo`. Ele chama `rodar([PY, "-c", "import time; time.sleep(2)"], rotulo="x")` duas vezes e afirma que só existe um processo vivo e que a gaveta recebeu "já está rodando". Hoje há 2 processos vivos.
- **Origem:** `painel-paginas.md` #6

### PNL-2 — A caixa TikTok do Publicar promete postar e não manda `--postar`  (médio)
- **Onde:** `painel/paginas/publicar.py:448` (`enviar`) e a legenda em `publicar.py:180`
- **Defeito:** o comando sai como `main.py publicar <id> --tiktok` sem `--postar`. Com isso, `random_builds/main.py:147` passa `postar=None`, e `tiktok.py:581` cai em `postar_automatico=false`: o vídeo sobe, mas fica parado sem o clique final.
- **Conserto:** em `enviar()`, quando `self.var_tt.get()` estiver marcado e a fonte for builds, acrescentar `"--postar"` aos argumentos, que é o que a legenda promete e o que foi decidido em 31/08. Conferir antes se `historias/main.py publicar` aceita `--postar`; se não aceitar, deixar o ramo das histórias como está, porque lá o código já passa `postar=True`.
- **Teste que prova:** em `painel/test_painel.py`, `PublicarTests.test_tiktok_marcado_manda_postar`. Ele monta a página com um item de builds selecionado, `var_tt=1`, `var_yt=0` e `Supervisor.rodar` dublado para capturar os argumentos, chama `enviar()` e afirma que `"--postar"` está nos argumentos.
- **Origem:** `painel-paginas.md` #1

### PNL-3 — Painel lido com erro vira placar zero e calmo  (médio)
- **Onde:** `painel/app.py:373` (`_entregar_resumo`), `painel/app.py:204` (`_entregar_pipeline`), `painel/paginas/vila.py:174` (`atualizar`), `painel/paginas/fluxo.py:113` (`atualizar`), `painel/paginas/confiabilidade.py:215` (`_ler`)
- **Defeito:** o `{"erro": ...}` devolvido por `Supervisor.tarefa` chega às páginas como se fosse um resumo, e todo `.get(...) or {}` vira "0 publicados · 0 problema(s)" / "0 na fila". Na Confiabilidade, `_ler` devolve `{}` quando a família falta, e a tela mostra "✓ 0/0 nada fora do lugar" em verde. A faixa da pipeline mostra "● rodando" quando a leitura do `controle` estoura, porque `dados.get("situacao") or "rodando"`.
- **Conserto:** em `_entregar_resumo`, se `dados.get("erro")`, registrar `"[painel] panorama ilegível: <erro>"` na gaveta e chamar `pagina.ilegivel(erro)` quando o método existir, sem chamar `atualizar`. Em vila, fluxo e confiabilidade, `ilegivel()` escreve "não consegui ler: …" no placar ou rótulo, com a cor de erro. Em `_entregar_pipeline`, para `erro`, mostrar "? pipeline ilegível". Em `confiabilidade._ler`, devolver `{"erro": "panorama sem confiabilidade"}` no lugar de `{}`, e em `_desenhar` tratar `prometido == 0` como "nada medido", sem o verde.
- **Teste que prova:** em `painel/test_painel.py`, `PlacarComErroTests`. Monta a Casca da Vila, chama `_entregar_resumo({"erro": "X"})` e afirma que `lbl_placar` NÃO contém "0 problema(s)" e que a gaveta contém "ilegível". Um segundo caso chama `confiabilidade.Pagina._desenhar({})` e afirma que a faixa não contém "nada fora do lugar".
- **Origem:** `painel-paginas.md` #4

### PNL-4 — Janela abre em 1000x600 e corta os botões de ação  (médio)
- **Onde:** `painel/app.py:71` (`Casca.__init__`: só `minsize(1000, 600)`; não há `geometry` fora do `--prova`)
- **Defeito:** a área de conteúdo é montada com `place` e não pede tamanho, então a janela nasce em 1000x600. Medido em 14/10 com `janelas.montar("criacao")` e o supervisor dublado: 1000x600. A página Publicar perde o botão Copiar e o cartão ONDE POSTAR; a página Vídeos perde Auditar origem e a tabela.
- **Conserto:** no fim de `Casca.__init__`, abrir na tela disponível com `self.update_idletasks(); self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()-71}+0+0")` (ou `self.state("zoomed")` no Windows), mantendo `minsize` como piso. Respeitar o tamanho que `--prova` define depois.
- **Teste que prova:** em `painel/test_painel.py`, `TamanhoInicialTests.test_abre_do_tamanho_da_tela`. Monta `janelas.montar("criacao")` sem `geometry`, dá `update()` e afirma que `winfo_width() >= 1300` ou `state() == "zoomed"`. Hoje dá 1000.
- **Origem:** `painel-paginas.md` #2

### PNL-5 — Vídeos de Build não cabe nem maximizada: a galeria some  (médio)
- **Onde:** `painel/paginas/videos.py:42` (`construir`: 5 blocos empilhados por `pack`, sem rolagem)
- **Defeito:** em 1366x697, a `Treeview` de VÍDEOS PRONTOS e a linha Voz/Salvar ajustes/Gerar trilha ficam sem mapear (medido: `[(0, 'pack')]`).
- **Conserto:** em `construir`, criar um `Canvas` rolável (a página já tem `_area_rolavel`, em `videos.py:453`, para a janela de atributos; extrair ou reaproveitar) e montar os cinco blocos dentro do quadro interno, com roda do mouse. Fazer o mesmo em Publicar e Histórias, se o PNL-4 sozinho não bastar.
- **Teste que prova:** em `painel/test_painel.py`, `VideosCabeTests`. Usa `geometry("1366x697")`, mostra a página `videos`, rola até o fim e afirma que toda `ttk.Treeview` da página tem `winfo_ismapped() == 1`.
- **Origem:** `painel-paginas.md` #3

### PNL-6 — "Parar" mata só o filho direto; Chrome, ffmpeg e worker ficam vivos  (médio)
- **Onde:** `painel/processos.py:153` (`parar_tudo`)
- **Defeito:** `processo.kill()` encerra só o `python main.py`, e os netos ficam órfãos segurando o perfil do Chrome e os arquivos.
- **Conserto:** no Windows, trocar o `kill()` por `subprocess.run(["taskkill", "/T", "/F", "/PID", str(processo.pid)], capture_output=True, creationflags=SEM_JANELA)`, com `kill()` como reserva, e registrar na gaveta o PID e o rótulo de cada árvore encerrada.
- **Teste que prova:** em `painel/test_painel.py`, `SupervisorTests.test_parar_mata_os_netos`. Roda um filho que abre um neto (`python -c` com `Popen` de `sleep` gravando o PID num arquivo temporário), chama `parar_tudo()` e afirma, por `tasklist /FI "PID eq <neto>"`, que o neto morreu.
- **Origem:** `painel-paginas.md` #7

### PNL-7 — A conferência do canal falha e a tela nunca diz  (médio)
- **Onde:** `painel/paginas/confiabilidade.py:122` (`conferir`)
- **Defeito:** o callback `lambda _r: self.recarregar()` joga fora o `{"erro": ...}` (token vencido, sem rede), e a tela continua mostrando a conferência anterior.
- **Conserto:** trocar o lambda por um método `_conferido(resultado)`. Se `isinstance(resultado, dict) and resultado.get("erro")`, escrever `"conferência falhou: <erro>"` na faixa, com a cor de erro, e na gaveta (`self.casca._registrar(..., "erro")`), sem recarregar por cima. Caso contrário, recarregar.
- **Teste que prova:** em `painel/test_painel.py`, `ConfiabilidadeTests.test_conferencia_com_erro_aparece`. Dubla `Supervisor.tarefa` para entregar `{"erro": "HttpError: token expirado"}`, chama `conferir()` e afirma que a faixa contém "token expirado".
- **Origem:** `painel-paginas.md` #8

### PNL-8 — Histórias que não carregam somem da lista do Publicar sem aviso  (médio)
- **Onde:** `painel/paginas/publicar.py:241` (`_ler`)
- **Defeito:** `except Exception: historias = []` faz a página mostrar só as builds, sem nenhuma linha de erro.
- **Conserto:** no `except`, guardar `aviso = f"histórias não carregaram: {type(e).__name__}: {e}"` e devolver `{"itens": ..., "publicados": ..., "avisos": [aviso]}`. No callback que desenha, se houver `avisos`, escrever no rótulo de estado da página e na gaveta.
- **Teste que prova:** em `painel/test_painel.py`, `PublicarTests.test_historias_quebradas_avisam`. Dubla `contos.publicar.catalogo.resumo` com `side_effect=RuntimeError("x")` e `catalogo_builds.listar` com `[]`, chama `_ler()` e afirma que `"avisos"` existe e contém "x".
- **Origem:** `painel-paginas.md` #10

### PNL-9 — O Guia avança mesmo depois de perder a mensagem  (médio)
- **Onde:** `painel/flutuante/guia/janela.py:577` (`proximo`)
- **Defeito:** o retorno `None` de `enviar_mensagem()` é ignorado, e o marcador `proximo` é gravado mesmo assim.
- **Conserto:** `if self.texto_da_mensagem() and self.enviar_mensagem() is None: self._dica("mensagem não gravada — o próximo NÃO foi enviado"); return None`.
- **Teste que prova:** em `painel/test_guia.py`, `test_proximo_para_se_a_mensagem_falhou`. Dubla `_gravar` com `side_effect=[False, True]`, preenche a mensagem, chama `proximo()` e afirma que o retorno é `None` e que `_gravar` foi chamado só uma vez.
- **Origem:** `painel-flutuante.md` #2

### PNL-10 — Mimetizar: catálogo do canal salvo como completo quando Shorts ou lives falham  (médio)
- **Onde:** `mimetizar/espelho/canal.py:134` (`catalogar`)
- **Defeito:** quando uma aba secundária levanta `NaoColetou` (falha passageira), o código só registra no log e segue, e o catálogo é gravado sem marca de incompleto.
- **Conserto:** acumular `faltaram = [aba, ...]` no `except NaoColetou` e gravar `dados["abas_faltando"] = faltaram` e `dados["completo"] = not faltaram` no JSON do canal. Em `status.py`, mostrar "catálogo INCOMPLETO (faltou: shorts)" e oferecer recatalogar. O caso "o canal não tem aba", que já devolve `{}` em `coletar_aba`, continua contando como completo.
- **Teste que prova:** em `mimetizar/tests/test_mimetizar_regressions.py`, `test_aba_que_falha_marca_catalogo_incompleto`. Dubla `coletar_aba` para devolver vídeos em `videos` e levantar `NaoColetou` em `shorts`, roda `catalogar` num `TemporaryDirectory` e afirma `completo is False` e `"shorts" in abas_faltando`.
- **Origem:** `sprites.md` #1

### PNL-11 — Mimetizar: o timeout do yt-dlp não vale com o processo calado  (médio)
- **Onde:** `mimetizar/espelho/ytdlp.py:96` (`rodar_streaming`). Chamado por `baixar.py:223` e `:267` com o padrão de 86400 s.
- **Defeito:** o prazo só é passado ao `proc.wait()`, que roda depois do `for linha in proc.stdout`. Um yt-dlp vivo e calado prende a coleta para sempre.
- **Conserto:** ler o stdout numa thread que põe as linhas numa `queue.Queue`. O laço principal faz `get(timeout=1)` e confere `time.monotonic() > fim`. Ao expirar, `proc.kill()` e devolve `124`. Acrescentar também um prazo de silêncio (`silencio_s`, padrão 600 s), passado pelos chamadores do `baixar`.
- **Teste que prova:** em `mimetizar/tests/test_mimetizar_regressions.py`, `test_rodar_streaming_respeita_prazo_calado`. Dubla `comando_base` para `[sys.executable, "-c", "import time; time.sleep(5)"]`, chama com `timeout=0.2` e afirma o código `124` em menos de 2 s.
- **Origem:** `sprites.md` #2

### PNL-12 — Mimetizar: corte interrompido conta como medição completa  (médio)
- **Onde:** `mimetizar/espelho/medidas.py:189` (`medir_video`) e `:68` (`cortes` devolve `parcial`, que ninguém lê)
- **Defeito:** com o ffmpeg cortado por timeout (124), a ficha registra a duração inteira como analisada e grava `amostra_parcial=False`.
- **Conserto:** em `medir_video`, se `planos["parcial"]`, usar `analisado = min(analisado, ultimo_instante_processado)`. Ler o último `pts_time` do showinfo e devolvê-lo em `cortes()` como `ate_s`. Gravar também `amostra_parcial=True` e `motivo_parcial="timeout"`. Se `ate_s` for desconhecido, levantar `NaoMediu`, para a etapa reagendar.
- **Teste que prova:** em `mimetizar/tests/test_mimetizar_regressions.py`, `test_corte_com_timeout_marca_parcial`. Dubla `ffmpeg.ffmpeg` com `(124, "", "pts_time:30.0")` e `ffprobe` com 600 s, e afirma `amostra_parcial is True` e `analisado_s <= 30.5`.
- **Origem:** `sprites.md` #3

### PNL-13 — Mimetizar: `.srt` vazio bloqueia nova transcrição  (médio)
- **Onde:** `mimetizar/espelho/transcrever.py:211` (seleção de `alvos` em `transcrever`)
- **Defeito:** todo vídeo que já tenha um `.srt` é pulado, mesmo vazio ou só com `WEBVTT`, e mesmo sem o `.json` ao lado.
- **Conserto:** criar `_transcricao_valida(destino, vid)`, que exige o `.srt` com pelo menos uma linha `-->` e o `{vid}.json` existente, e usá-la no filtro de `alvos`. Na gravação, escrever em `.srt.tmp` e fazer `replace`.
- **Teste que prova:** em `mimetizar/tests/test_mimetizar_regressions.py`, `test_srt_vazio_volta_para_a_fila`. Grava `v1.srt` com só `WEBVTT`, dubla a obtenção para devolver uma legenda válida e afirma `transcritos == 1` e que `v1.json` existe.
- **Origem:** `sprites.md` #4

### PNL-14 — Mimetizar: criação concorrente de canal morre com `FileExistsError`  (médio)
- **Onde:** `mimetizar/espelho/config.py:79` (`criar_canal`)
- **Defeito:** `proximo_id()` roda antes de `mkdir(exist_ok=False)`, sem laço nem trava. Duas absorções ao mesmo tempo, que o duplo clique do PNL-1 também produz pelo painel, escolhem o mesmo id.
- **Conserto:** `for _ in range(50): canal_id = proximo_id(); try: (OUTPUTS / canal_id).mkdir(parents=True, exist_ok=False); return canal_id, OUTPUTS / canal_id; except FileExistsError: continue`, e no fim `raise RuntimeError`.
- **Teste que prova:** em `mimetizar/tests/test_mimetizar_regressions.py`, `test_criar_canal_concorrente`. Duas threads com barreira chamam `criar_canal` num `TemporaryDirectory`, e o teste afirma 2 pastas criadas, diferentes, e zero erros.
- **Origem:** `sprites.md` #5

### PNL-15 — "Entrar/Autorizar" do Grok chama um login que recusa o grok  (baixo)
- **Onde:** `painel/paginas/contas.py:225` (`entrar`)
- **Defeito:** `grok` cai no `else`, que chama `identity login --provedor grok`; o argparse recusa com o código 2. O login certo é `historias/main.py llm login --provedor grok`, que aceita grok (`historias/main.py:580`).
- **Conserto:** trocar a tupla para `("chatgpt", "gemini", "deepseek", "grok")`. No `else`, só disparar se `servico in builds.identity.config.PROVEDORES`; caso contrário, `messagebox.showinfo` dizendo que esse serviço não tem login pelo painel.
- **Teste que prova:** em `painel/test_painel.py`, `ContasTests.test_grok_vai_para_llm_login`. Seleciona a linha `("grok", canal)`, dubla `_abrir` e `messagebox`, chama `entrar()` e afirma que os argumentos contêm `"llm", "login", "--provedor", "grok"` e que o `cwd` é `HISTORIAS`.
- **Origem:** `painel-paginas.md` #5

### PNL-16 — O erro de leitura do Fluxo some no pulso seguinte  (baixo)
- **Onde:** `painel/paginas/fluxo.py:134` (`atualizar`) e `:139` (`_desenhar_tabela`)
- **Defeito:** o erro e o alerta do panorama dividem o rótulo `_alerta`; o pulso de 4 s o reescreve com `""` e deixa a cor vermelha.
- **Conserto:** criar `self._erro_leitura` (rótulo próprio, abaixo de `_alerta`). `_desenhar_tabela` escreve nele em caso de erro e o limpa em caso de sucesso. Em `atualizar`, voltar `_alerta` para `fg=self.t.aviso` sempre que reescrever.
- **Teste que prova:** em `painel/test_painel.py`, `FluxoTests.test_erro_sobrevive_ao_pulso`. Chama `_desenhar_tabela({"erro": "X"})`, depois `atualizar({})`, e afirma que algum rótulo da página ainda contém "X".
- **Origem:** `painel-paginas.md` #9

### PNL-17 — `encerrar()` não desliga o pulso da pipeline  (baixo)
- **Onde:** `painel/app.py:400` (`Casca.encerrar`)
- **Defeito:** `_pulso_pipeline` continua agendado depois de `encerrar`, e aparece "invalid command name …_bater" nos testes.
- **Conserto:** acrescentar `if self._pulso_pipeline: self._pulso_pipeline.desligar()` logo após `self._pulso.desligar()`.
- **Teste que prova:** em `painel/test_painel.py`, `FreioDaPipelineTests.test_encerrar_desliga_o_pulso_da_pipeline`. Monta a Casca com `pipeline=True`, chama `encerrar()` e afirma que o `Periodico` do pipeline não está ligado (sem `after` pendente).
- **Origem:** `painel-paginas.md` #11

### PNL-18 — O botão da vista ativa da Oficina perde o destaque no hover  (baixo)
- **Onde:** `painel/widgets.py:120` (`Oficina.botao`, binds `<Enter>` e `<Leave>`)
- **Defeito:** o `<Leave>` volta para o `bg` capturado na criação e apaga o `acento_fundo` que `_pintar_vista` (`oficina.py:779`) pôs.
- **Conserto:** no `<Enter>`, guardar `alvo._bg_antes = alvo.cget("bg")` e pintar `realce`. No `<Leave>`, `configure(bg=getattr(alvo, "_bg_antes", fundo))`.
- **Teste que prova:** em `painel/test_oficina_sprites.py`, `test_hover_preserva_vista_ativa`. Gera `<Enter>` e `<Leave>` no botão da vista ativa e afirma que o `bg` é igual a `tema.acento_fundo`.
- **Origem:** `painel-paginas.md` #12

### PNL-19 — Os testes da casca leem o disco real  (baixo)
- **Onde:** `painel/test_painel.py:30` (`setUpModule`) e `painel/test_oficina_sprites.py:427`
- **Defeito:** só `panorama.resumo` é dublado; `builds.pipeline.fluxo.snapshot` (no `ao_mostrar` do Fluxo) e `builds.identity.controle.estado` (no pulso da pipeline) leem a máquina de verdade.
- **Conserto:** em `setUpModule`, iniciar também `patch("builds.pipeline.fluxo.snapshot", return_value={"linhas": []})` (conferir o formato que `_desenhar_tabela` espera) e `patch("builds.identity.controle.estado", return_value={"situacao": "rodando"})`, e pará-los em `tearDownModule`.
- **Teste que prova:** em `painel/test_painel.py`, `PanoramaDubladoTests.test_snapshot_e_controle_dublados`. Afirma que `regra.snapshot` e `controle.estado` são `MagicMock` dentro do módulo.
- **Origem:** `painel-paginas.md` #13

### PNL-20 — `grade` inválida no `.json` de uma folha para a animação da Vila  (baixo; só a esteira desligada grava esse .json)
- **Onde:** `painel/flutuante/arte_pronta.py:468` (`folha`) e `painel/flutuante/janela.py:1096` (`_animar`)
- **Defeito:** `int(grade[0])` levanta `ValueError`. Como `_animar` só trata `tk.TclError`, o `after` seguinte não é agendado e a Vila congela até ser reaberta.
- **Conserto:** em `folha()`, envolver a leitura de `grade` e `ciclos` em `try/except (TypeError, ValueError, IndexError)`, caindo para a grade 1x1 com o ciclo "tudo". Em `_animar`, trocar o `try` por um `try/except Exception` que registra o erro e SEMPRE reagenda o `after`, num `finally`.
- **Teste que prova:** em `painel/test_arte_pronta.py`, `test_grade_corrompida_vira_1x1`. Grava o PNG e o JSON `{"grade": ["corrompida", 1]}` numa pasta temporária e afirma que `folha(...)` devolve `colunas == 1`, sem exceção.
- **Origem:** `painel-flutuante.md` #1

### PNL-21 — `wscript` sem `//B` conta como tarefa oculta (selo verde)  (baixo)
- **Onde:** `painel/flutuante/tarefas.py:97` (`examinar_uma`)
- **Defeito:** o ramo sem `//b` devolve o estado `oculta`, e `examinar()` não o põe em `problemas`.
- **Conserto:** devolver `ficha("desconhecida", "wscript sem //B (erro de script abriria caixa de diálogo)", alvo)`.
- **Teste que prova:** em `painel/test_flutuante.py`, `test_wscript_sem_B_entra_nos_problemas`. Monta uma ação `wscript.exe "C:/nf/oculto.vbs" "C:/nf/postar.cmd"` com `existe=lambda _p: True` e afirma `examinar(...)["ok"] is False`.
- **Origem:** `painel-flutuante.md` #3

### PNL-22 — O cache do emote nunca é limpo quando chega arte nova  (baixo)
- **Onde:** `painel/flutuante/arte.py:945` (`emote`, `@lru_cache`) e `painel/flutuante/cena.py:89` (`_conferir_arte`)
- **Defeito:** quando a assinatura da arte muda, a cena limpa `mundo`, `p` e `prop`, mas nunca chama `emote.cache_clear()`.
- **Conserto:** em `_conferir_arte`, dentro do `if` que detecta mudança, chamar `arte.emote.cache_clear()` e o `cache_clear()` de qualquer outro `lru_cache` de `arte.py` que leia `arte_pronta` (conferir com `grep -n lru_cache painel/flutuante/arte.py`).
- **Teste que prova:** em `painel/test_vila_fofa.py`, `test_emote_novo_entra_sem_reiniciar`. Gera `emote("x")`, grava `interface/balao_emote.png` vermelho numa pasta temporária, força `_conferir_arte` e afirma que o pixel central mudou.
- **Origem:** `painel-flutuante.md` #4

### PNL-23 — O combo do freio não oferece o alvo "correio"  (baixo)
- **Onde:** `painel/app.py:193` (`_pipeline_alvo`)
- **Defeito:** a lista fixa `["tudo", "picasso", "digen"]` não inclui `correio`, que a CLI aceita em `random_builds/main.py:457` e `:613`.
- **Conserto:** expor `PROVEDORES_FREIO = ("tudo", "correio", "digen", "picasso")` em `builds.identity.controle` (ou no `main.py`), usar a mesma tupla nos `choices` do argparse e no combo.
- **Teste que prova:** em `painel/test_painel.py`, `FreioDaPipelineTests.test_combo_tem_os_alvos_da_cli`. Afirma que `set(casca._pipeline_alvo["values"]) == set(PROVEDORES_FREIO)`.
- **Origem:** `painel-paginas.md` #14

---

## Já consertados
Nenhum. Nenhum dos 23 arquivos citados recebeu commit depois de 11/10 (o último do painel é `f143cf5`, em `painel/flutuante/janela.py`, e não toca nestes pontos).

## Alarmes falsos
Nenhum. Os 23 foram reabertos no código atual. O #2 e o #3 do `painel-paginas.md` foram medidos de novo, montando a janela (1000x600 e a `Treeview` sem mapear em 1366x697).

## Decisões que são do Adrian
- O TikTok pelo painel posta de verdade ou só sobe? Já decidido em 31/08 ("publicar sem confirmação, TikTok posta"); o PNL-2 segue essa decisão. Só perguntar de novo se ele mudou de ideia.
- A página Vídeos ainda oferece "Login no PicassoIA", "Login no Digen" e "Vídeo do payoff (Digen)", depois das decisões `picasso-fora-da-roda` e `digen-plano-free`. Tirar os botões ou deixá-los? (registrado em `painel-paginas.md` #14)
