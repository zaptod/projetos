# Avaliação de arquitetura — E:\projetos (12/10/2026, só leitura)

Base: código em `E:\projetos` (ramo `refactor/arquitetura` @ `e8cc338`), os 8 relatórios de `docs/auditoria/2026-10-11/`, os 15 de `docs/auditoria/2026-10-11-profunda/`, `docs/sessoes/*.md`, `docs/arquitetura/FLUXO_ATUAL.md`, `docs/OPERACAO.md`, `CLAUDE.md`, os `.cmd`, `pyproject.toml`, `pip list --editable`, e as memórias do orquestrador. Nada foi alterado.

**Resumo em três linhas.** O sistema funciona (10/10 horários publicados na maioria dos dias; o Godot, o app e a grade saíram limpos das auditorias). O que dói não são peças quebradas: é que **cada peça inventou o próprio jeito de guardar estado, de travar, de logar e de achar os módulos**, e 24 h por dia várias peças pisam no mesmo arquivo. Quase todos os "altos" das auditorias são o mesmo defeito em arquivos diferentes.

---

## 1. O mapa de verdade

### 1.1 As partes e quem chama quem

```
          AGENDADOR DO WINDOWS — 61 tarefas, todas por wscript //B oculto.vbs <cmd>
 ┌──────────────┬────────────────┬────────────────┬─────────────────┬──────────────────────┐
 │postar_HH x10 │Historias_auto  │NeuralFights_   │NeuralFights_    │app_celular, bot_     │
 │(grade fixa)  │_HH x23         │gerar_HH x23    │coordenador      │telegram, vila x3     │
 │postar.cmd    │auto.cmd        │gerar.cmd       │(a cada 5 min)   │(a cada 10 min)       │
 │ >> postar.txt│ --saida > NUL  │ --saida > NUL  │coordenador.cmd  │ >> *.txt  /  ps1     │
 └──────┬───────┴───────┬────────┴───────┬────────┴────────┬────────┴──────────┬───────────┘
        v               v                v                 v                   v
 ferramentas/     historias/        random_builds/   coordenador/         "já tem um, saio"
 postar.py        main.py auto      main.py noite    Supervisor (pulso 5 s)   (sempre 0x1)
 (5.608 linhas)   contos.pipeline   builds.pipeline   ├─ adota/religa ─────────────┐
   │ │ │           .agenda           .noite            ├─ threads: cerebro, pedidos, │
   │ │ │             │ │               │               │   conversa, vigia_trabalho, │
   │ │ │             │ │               │               │   equipe, esteira,          │
   │ │ │             │ │               │               │   assembleia, obsidian      │
   │ │ │             │ │               │               v                             v
   │ │ │             │ │               │   ┌────────────────────────────────────────────┐
   │ │ │             │ │               │   │ 4 SERVIÇOS 24 h (coordenador/servicos.json)│
   │ │ │             │ │               │   │ app      remoto.api_http :8931 ── PWA      │
   │ │ │             │ │               │   │ bot      remoto (__main__)   ── Telegram   │
   │ │ │             │ │               │   │ carteiro ias carteiro        ── Chrome IAs │
   │ │ │             │ │               │   │ vila     painel.flutuante (pythonw)        │
   │ │ │             │ │               │   └────────────────────────────────────────────┘
   v v v             v v               v
 contos.publicar   ias.correio      neural_fights        remoto.delegar ──> Codex / Claude
 builds.publicar   (Gemini/ChatGPT  + palco/ (Godot)     em E:\projetos-wt\codex-<id>
 YouTube Studio e   por Chrome)      render dos builds    (o vigia aplica o diff no E:\projetos
 TikTok Studio                                             e commita; 70 worktrees hoje)
```

| Parte | Quem dispara | Processo | cwd | Importa |
|---|---|---|---|---|
| Publicação | 10 tarefas `postar_HH` | `ferramentas/postar.py` | `E:\projetos` | `builds`, `contos`, `remoto` |
| Histórias | 23 tarefas `Historias_auto_HH` | `historias/main.py auto` | `historias/` | `contos`, `builds`, `ias` (via `sys.path`) |
| Builds (noite) | 23 tarefas `gerar_HH` | `random_builds/main.py noite` | `random_builds/` | `builds`, `neural_fights` |
| Coordenador | tarefa de 5 min (trava única) | `python -m coordenador rodar` | `E:\projetos` | tudo |
| app/bot/carteiro/vila | **o coordenador E 3 tarefas de 10 min** | 4 processos | `E:\projetos` | `remoto`, `ias`, `painel` |
| Codex/Claude | Mesa (`pedidos.passo`), app (Equipe), cérebro, CLI do chat | `remoto/delegar.py` | worktree | o da **árvore principal** (ver P5) |

### 1.2 Onde mora cada estado, e quem grava

Três raízes de estado: `%LOCALAPPDATA%\neural-fights\` (2.134 arquivos json; 17 GB no C:, 13,7 GB são perfis de Chrome), `outputs/` dentro de cada projeto (ledgers, pareceres, reparos, logs) e `decisoes/` no git.

| Arquivo de estado | Onde | Escritores (processo → função) | Trava / gravação |
|---|---|---|---|
| **ledger de builds** `publicados.jsonl` | `random_builds/outputs/_publicar/` | postar, `main.py publicar`, app (`remoto/acoes.py`), `publicacao_filha` → `youtube.py:180` e `tiktok.py:738` → `metricas.registrar_publicado`; reconciliação `metricas.py:731` (reescreve tudo); `curar_ledger.py:558`; `conciliar_tiktok.py` | `ledger__builds` (`builds.travas`) + fila lateral `.pendentes/` (desde `e3e08fc`) |
| **ledger de histórias** `publicados.jsonl` | `historias/outputs/_publicar/` | `serie.registrar` ← `postar.py:1413,1537,1750,2839,4475`, `historias/main.py:466,489`, `serie.publicar`, `curar_ledger.py:559`; reconciliação | `ledger__historias`, mesma receita |
| **Mesa** `pedidos.json` | `…\coordenador\` | só `coordenador/pedidos.py` (28 `_gravar`), mas de **4 processos**: app, bot, coordenador (passo/conversa/Grimório), CLI `coordenador pedir` | `pedidos.lock` (`api_http.trava_arquivo`); leitura ilegível recusa (desde `0b8e0d9`) |
| **contas** `contas.json` | `…\neural-fights\` | `builds/contas.py:126 _gravar` ← `adicionar/escolher/remover/renomear/identificar`; chamados por `youtube_web.py:837` (no meio de uma publicação), app `comandos_app.py:485`, painel `paginas/contas.py:181`, `auditoria_contas.py:118` | **nenhuma**; `open("w")` direto; ilegível vira `{}` |
| **pareceres da IA** `_pareceres.json` | `historias/outputs/` | `parecer.py:224-225` e `:229 _lembrar` ← `parecer.pedir` em `agenda.py:1677,1703` (faixas paralelas), `reparo.py:954`, `postar.py:607`; `esquecer`, `limpar motivos` | **nenhuma**; `open("w")`; ilegível vira `{}` |
| **diário** `atividade.jsonl` | `…\neural-fights\` | `builds.atividade.registrar` (append) de 29 módulos / todos os processos; `_podar` (`atividade.py:148`) reescreve o arquivo inteiro | append sem trava (ok); **poda sem trava** |
| **delegados** `delegados/<id>/estado.json`, `eventos.jsonl` | `…\neural-fights\` | `remoto/delegar.py:504 _gravar_estado` em criar/rodar/corrigir/parar/aplicar/limpar; chamados por Mesa, vigia, cérebro, app (Equipe `api_http.py:2978`), CLI do chat | `delegar.lock` (`trava_arquivo`, 180 s), tmp+replace com retry |
| **Mesa do orquestrador** `orquestrador/estado.json`, `comandos*.jsonl` | `…\neural-fights\` | `remoto/orquestrador.py:248,279` (agora/fila), `aplicado`, `agente_fim`, `aplicar_pelo_servidor`; app, coordenador, chat | `orquestrador.lock`; ilegível = `Recusa` (modelo bom) |
| **estado do coordenador** `coordenador/estado.json` | idem | só o Supervisor (`estado.py:36`) | escritor único, tmp+replace |
| **avisos** `avisos_estado.json`, `avisos_enviados.jsonl` | `…\neural-fights\` | `remoto/avisos.py` ← `carteiro.avisar_telegram` (coordenador, carteiro, histórias via `python -m remoto --avisar`), bot | nenhuma ("nunca levanta") |
| **relatórios do bot** `relatorios.json` | `…\neural-fights\` | só `relatorios.marcar` ← `bot.py:214` | escritor único, sem atômico |
| **correio das IAs** `ias/<ia>/correio.jsonl`, `carteiro.json` | `…\neural-fights\ias\` | `ias/correio.py` ← app, carteiro, histórias (imagens), assembleia, esteira | `_trancado` próprio (10 s, não reentrante) |
| **lista "a conferir"** `_<plataforma>_a_conferir.json` | `outputs/_publicar/` | `desfecho.py` (publicadores), `remoto/acoes.py:551-592` (app) | `tiktok_a_conferir`/`youtube_a_conferir` |
| **reparos** `_reparos.json` | `historias/outputs/` | `reparo.py` | `historias__reparos_json` (bom) |
| **Grimório** `decisoes/<proj>/*.json`, `_eventos.jsonl` | git | `remoto/decisoes.py` (app, CLI) | `decisoes.lock` |
| **fila de identidade** `queue.json` | `random_builds/…/identity` | `identity/queue.py` | lock próprio em **`%TEMP%`** (`queue.py:28`) |
| **banco do jogo** `personagens.json`, `armas.json` | runtime | `neural_fights/data/database.py` | lock próprio |
| **travas** `locks/*.lock`, `postar__rodada.dona.json` | `…\neural-fights\locks\` | `builds.travas` (212 arquivos, 92 de teste) | — |
| **logs** `outputs/*.txt`, `*/outputs/_logs/*` | `E:\projetos\outputs` etc. | `>>` do cmd (postar, bot, app), `--saida` do Python (auto, gerar, carteiro), `Supervisor._log` (coordenador) | três estilos; `postar.txt` e `app_celular.txt` **sem data** |

Mecanismos de trava hoje (não são 3, são **6**): `builds/travas.py` (byte lock, reentrante por thread, pasta `locks/`), `remoto/api_http.py:552 trava_arquivo` (RLock + byte lock, prazo, reentrante; usado por `delegar`, `orquestrador`, `decisoes`, `cerebro`, `pedidos`), `ias/correio.py:135 _trancado`, `identity/queue.py:43 _bloqueio` (em `%TEMP%`), `neural_fights/data/database.py:110`, `coordenador/supervisor.py:187 TravaUnica` (`O_EXCL` + pid). Cada um com prazo, reentrância e pasta diferentes.

---

## 2. Os problemas estruturais

### P1. Cada arquivo de estado tem a sua receita de "ler tudo, gravar tudo" — e metade sem trava nem gravação atômica
- **O que é.** Em vez de um jeito só de guardar JSON, há seis: o bom (`orquestrador._ler_json/_gravar_json`: ilegível levanta `Recusa`, grava em `.tmp` + `os.replace`; `delegar._gravar_json` ainda tenta de novo no `PermissionError` do Windows) e os ruins (`contas.py:117-131`, `parecer.py:105-113,224,229`, `esteira_sprites/ficha.py:35-44`, `mimetizar/espelho/estado.py:38-54`, `capas_atrasadas.py:61-71`, `cota.py:98`, `atividade._podar:148-158`, `sonorizar.py:90`, `timeline_arquivo.py:140`). Nos ruins, "não consegui ler" vira `{}` e a próxima gravação apaga o registro inteiro; dois processos gravando ao mesmo tempo perdem a gravação de um.
- **Bugs da auditoria que são isto.** RESUMO #3 (`pedidos.json`), #6 (ledger da arena), profunda publicar-histórias #1 (`contas.json` zerado → "publicar no canal errado não tem desfazer") e #2 (`_pareceres.json`: corrida real com 3 processos deixou **6 fichas de 122**; os 125 vetos deixam de barrar), ias-e-palco #2 e #3, histórias #2, motor #3, pipeline-builds #1, ferramentas (capas). A auditoria de 11/10 provou o mesmo defeito em **9 arquivos**.
- **O que já custou.** 4 repostagens no YouTube em 29–31/08 (reconciliação apagava linha do ledger, `maquina.md` §3); `pedidos.json` e a conversa do app em risco a cada leitura trancada; a decisão `historias/reprovado-ou-nao-assistido` ("fica retido") deixa de valer sem aviso quando o arquivo de pareceres some.
- **Conserto.** Um módulo só (`estado_json`: `ler()` que recusa ilegível e guarda cópia, `gravar()` tmp+replace com retry, `alterar()` que segura a trava do arquivo em volta de ler-mudar-gravar), e todo arquivo de estado passa por ele.

### P2. Seis mecanismos de trava, cada um com prazo, pasta e reentrância diferentes
- **Evidências.** Lista em §1.2. `identity/queue.py:28` tranca em `%TEMP%` (o C:, que vive cheio); `ias/correio.py:135` espera só 10 s e não é reentrante; `artefato.py:7` lembra que `msvcrt.locking` não é reentrante; `builds.travas._pasta()` segue `NEURAL_FIGHTS_RUNTIME_DIR` mas `remoto/config.py:26 runtime_dir()` **ignora** a variável — então o `conftest` isola metade dos arquivos e a outra metade vai para a pasta real (**92 locks de teste na pasta de produção**, `maquina.md` §5).
- **Bugs.** RESUMO #5 (`[Errno 36] Resource deadlock avoided` no `delegar`, consertado esperando o EDEADLK em `0b8e0d9`); memória `limpar-entrega-dispara-integrador` (08/10: limpeza morta por deadlock → **7 integradores Claude** contratados, cota queimada); memória `grimorio-gera-trabalhador-duplicado` ("deadlock deixa a tarefa em `criado` para sempre").
- **Conserto.** Um `trava(nome, prazo)` só — o de `api_http.trava_arquivo` é o mais completo — num módulo neutro que `builds.travas`, `correio`, `queue` e `database` passam a chamar, todos na mesma pasta `runtime/locks`, que respeita o isolamento de teste.

### P3. Dois gerentes para os mesmos serviços (Agendador E coordenador), e o reinício por "código velho" ignora a janela das postagens
- **Evidências.** `app_celular.cmd`, `bot.cmd`, `vila_flutuante.cmd` (tarefas de 10 min) **e** `coordenador/servicos.json` mantêm os mesmos 4 processos; o comando para desligar as antigas existe (`coordenador/__main__.py:73-75`) mas nunca rodou — `maquina.md` §1: `app_celular` e `bot_telegram` falham com 0x1 a cada 10 min. `supervisor.py:409-410`: "03/10: sem janela de relógio" — `seguro()` só olha publicação em voo, embora o `CLAUDE.md` §4 e a memória `app-nunca-cai` digam `post-12 … post+18`. `supervisor.py:65-70` já registra 13 religadas em 12 min em 04/10 por edição em andamento; `reinicios_24h` zera a cada subida do coordenador (`supervisor.py:285`, estado só em memória).
- **O que já custou.** 05/10: **211 linhas** "caiu/reiniciou"; 11/10 15:17 app e bot reiniciados "código atualizado" a 20 min do post das 15:37 (`maquina.md` §6); cada religada do bot derruba o app do tailnet por 1–3 min; o Agendador cheio de 0x1 esconde falha real.
- **Conserto.** Desligar as três tarefas antigas e devolver ao `seguro()` a janela da grade + as travas de rodada (ver P4), com "código velho" virando reinício **pedido** (pelo vigia ao aplicar, ou por `coordenador reiniciar`) e não automático a cada save.

### P4. `E:\projetos` é produção e bancada ao mesmo tempo: código trocado embaixo de processo vivo
- **Evidências.** O vigia aplica o diff na árvore principal (`vigia_trabalho.py:13-20`) evitando só a janela da postagem; serviços e rodadas importam módulos tarde. Memória `entrega-aplicada-quebra-rodada-viva` (07/10 01:51: rodada das histórias morreu com `slots` velho + `provedores` novo); `maquina.md` §2.11 (22x `ModuleNotFoundError` em 04/10), tracebacks `SyntaxError: unterminated string literal` em `bot.txt` e `carteiro.txt` (arquivo pela metade durante entrega), `auto_saida.txt` com `AttributeError … formato_de / CORREIO`; `maquina.md` §8: `remoto/delegar.py` editado às 15:16 sem commit enquanto o coordenador rodava.
- **O que já custou.** Uma história de ~4 h perdida; bot e carteiro mortos por sintaxe; "noite(s) sem conferência".
- **Conserto.** Uma função `momento_seguro()` única (publicação em voo OU janela da grade OU travas `historias__auto*`, `noite`, `postar__rodada` ocupadas → não aplica, não reinicia), usada por supervisor, vigia e `delegar.aplicar`; e aplicar + reiniciar no mesmo passo.

### P5. Importação que depende da pasta atual, e instalação editável que faz worktree importar a árvore principal
- **Evidências.** `pip list --editable`: `builds`, `contos`, `panorama`, `painel`, `neural_fights`, `espelho` apontam para `E:\projetos\…` (finder `MAPPING = {'builds': 'E:\\projetos\\random_builds\\builds'}`, instalado com `sys.meta_path.append`, isto é, **depois** do `sys.path`). `remoto`, `coordenador`, `ias`, `ferramentas`, `esteira_sprites` **não são instalados**: só importam com `cwd=E:\projetos`. Daí: `historias/contos/imagens/worker.py:29-35` (`sys.path.append` da raiz, depois de "toda passada de imagens morreu com No module named 'ias' em 04/10"); `agenda.py:612-619` avisa por subprocesso "porque `remoto` não está instalado"; `postar.txt`: **24x** `[parecer] nao consegui avisar no Telegram: No module named 'remoto'` — o REPROVADO do parecer nunca chega ao Adrian (`maquina.md` §2.10); `avisos.py` docstring: 22 avisos "No module named 'ias'". Nas worktrees do Codex, `import builds`/`contos` resolve para `E:\projetos` a não ser que o cwd seja `random_builds/`; `historias/tests/test_trecho_preto_regressions.py:308` ("`import remoto` só passava com o PYTHONPATH da worktree"). A catraca `ferramentas/auditoria_arquitetura.py` existe justamente para isto (eram 45 cirurgias de `sys.path`, teto 2).
- **O que já custou.** Avisos perdidos, passada de imagens morta em 04/10, testes "verdes" do Codex rodando parte do código da árvore principal (memória `codex-cego-para-tela-e-godot`).
- **Conserto.** Tornar a raiz importável de qualquer pasta (um `.pth` com `E:\projetos` agora; um pacote `operacao` com `pyproject` depois) e rodar toda worktree com `PYTHONPATH=<worktree>;<worktree>\random_builds;<worktree>\historias;<worktree>\visao` (o `sys.path` ganha do finder editável).

### P6. Três mesas de trabalho e quatro portas diretas para contratar Codex/Claude
- **Evidências.** `pedidos.json` (Mesa), `orquestrador/estado.json` (fila/agora) e `delegados/*/estado.json` (fichas) descrevem o mesmo trabalho; portas que pulam a Mesa: app Equipe `api_http.py:2978-2990`, proposta do cérebro `cerebro.py:565-580`, CLI `delegar.py:2138`, gerente `equipe.py:55-83` — tudo já documentado em `FLUXO_ATUAL.md` "Retrabalho e duplicação". `maquina.md` §5: 217 delegados, 19 "terminou" sem aplicar/limpar, 8 "precisa de olho" **gravados a cada minuto** (6.489 linhas/dia em `coordenador.txt`, 5,7 MB, e o mesmo texto no Telegram); §7: 77 worktrees (24 criadas em 11 min), 11 órfãs, 7,1 GB.
- **O que já custou.** 06/10: 5 trabalhadores duplicados numa noite; 08/10: 7 integradores; uso semanal do Claude em 88 % (`uso.json`).
- **Conserto.** Executar a "etapa b" já desenhada em `FLUXO_ATUAL.md`: pedido é a única origem (`origem_ref` obrigatória), as portas diretas chamam a Mesa, e o vigia avisa "precisa de olho" **uma vez** (ele já tem `trabalho_memoria.json` para isso).

### P7. "Não sei" vira "ok": falha engolida que sai como sucesso
- **Evidências.** 1.000 `except Exception` no código de produção, 427 no padrão `except: pass/return {}`. Concretos: `metricas.py:342-344 registrar_publicado` engole com `print` (publicação sem ledger = repostagem); `qualidade._audio` devolve `None` e o mudo **passa** (profunda publicar-histórias #4) enquanto `_ffprobe` devolve `{}` e o bom é **barrado** (#5) — as duas medidas tratam "não medi" ao contrário; `agenda._servico_do_dia:1627` marca o serviço do dia mesmo falhando; `historias/main.py:162 cmd_tudo` devolve 0 com erro; `obsidian.py:511` `0 if … else 0`; `catalogo.py:131 lru_cache` guarda o `None` da falha; `recursos.py:211` e `dados.py:830` (consertados em `f143cf5`); `coordenador/estado.py reinicios_24h`.
- **O que já custou.** Memória `relatorio-verde-que-mente`: métrica 10 dias morta (17→27/09) com exceção engolida; `aviso-sem-rede-calado` (09/10: 6 horários perdidos e 5 avisos calados); vídeo mudo no ar.
- **Conserto.** Regra de três estados (ok / falhou / não-medido) em toda medida e porta, com teste do caso ZERO, e nenhum `except … pass` sem linha no diário.

### P8. Três estilos de log, e o `>>` do cmd que mata a trava da rodada
- **Evidências.** `postar.cmd`, `bot.cmd`, `app_celular.cmd` usam `>> arquivo 2>&1`; `auto.cmd`/`gerar.cmd`/`carteiro.cmd` usam `--saida`; o coordenador loga sozinho. Profunda `postar.md` #1 (prova com dois `.cmd` reais): enquanto uma rodada vive, a tarefa seguinte **morre antes do Python** com código 0 — toda a trava da rodada, a morte da dona pendurada e o pouso do "em voo" (`postar.py:4505-5260`) **nunca rodam** pelo Agendador. `postar.txt` (35.610 linhas) e `app_celular.txt` não datam as linhas → 4 dias com horário vazio sem causa (`maquina.md` §18); 178 tracebacks de `WinError 10053` (cliente fechou) em `app_celular.txt`.
- **O que já custou.** 14/09: 7:20 e 8:20 das histórias morreram assim (memória `agendador-arquivo-trancado`); desde 06/10 a sobreposição de rodadas de postagem é caso previsto (reposição até 25 min, volta final 40).
- **Conserto.** Um `log.py` compartilhado (data+hora+pid em toda linha, arquivo aberto pelo Python, rotação por dia) e todo `.cmd` com `--saida … > NUL 2>&1`.

### P9. Estado sem esquema nem versão, e duas definições de "pasta de runtime"
- **Evidências.** Nenhum arquivo de estado tem `versao`; leitores tolerantes transformam campo errado em "vazio e calmo" (`dados.py:830`: `ok: None` virava "💤 tudo parado"). `remoto/config.py:26` ignora `NEURAL_FIGHTS_RUNTIME_DIR`; `builds/contas.py:98` honra. `maquina.md` §5: `atividade.jsonl` tem linhas de erro **sem campo `etapa`**.
- **Custo.** Isolamento de teste pela metade (P2); "tudo em dia" para verificação que não aconteceu.
- **Conserto.** Uma `runtime_dir()` só (a de `neural_fights.data.database`) e `{"versao": N}` em cada arquivo, validado por quem lê.

### P10. Seis instaladores de tarefas do Windows
- **Evidências.** `postar.py --instalar`, `main.py auto --instalar`, `main.py noite --instalar`, `coordenador instalar-tarefa`, `painel.flutuante.tarefa --instalar`, `remoto --instalar`; 61 tarefas, `retomar_codex` é sobra de 02/10; gerar/histórias com os mesmos 23 horários sem arquivo de configuração comum.
- **Custo.** Baixo hoje (horários batem com a grade). Fica para depois.
- **Conserto.** Um instalador que lê grade + agenda e escreve todas as tarefas e `.cmd` com o mesmo molde.

---

## 3. Plano de reforma — etapas pequenas, do que mais dói

Regra geral de todas: trabalhar numa worktree, aplicar só em `momento_seguro` (fora de `post-12…post+18`, sem `historias__auto*`/`noite`/`postar__rodada` ocupadas), commit por caminho, teste verde antes (`TEMP=E:\tmp_pytest`, `PYTEST_ADDOPTS=-p no:cacheprovider`). Cada etapa cabe num dia.

| # | Etapa | O que muda | O que NÃO muda | Como provar | Decisão? |
|---|---|---|---|---|---|
| **1** | **Lançadores e logs** (P8) | `postar.py:3726 escrever_lancador` grava `--saida … > NUL`; `bot.cmd`/`app_celular.cmd` idem (o `_redirecionar_saida` do `historias/main.py` é o molde); toda linha de `postar.txt` e `app_celular.txt` com data; `api_http.py:569` engole `10053`. Regravar os `.cmd` logo depois de um post terminar (nunca com rodada viva). | A lógica da rodada, a grade, o ledger. | Teste de contrato lendo `escrever_lancador()` e recusando `>>`; `postar.py --ver`; `schtasks` roda e o log aparece datado; suíte `remoto`. | Não |
| **2** | **Um gerente só** (P3) | `python -m coordenador desligar-tarefas-antigas`; apagar `NeuralFights_retomar_codex`; `supervisor.seguro()` volta a incluir a janela da grade; "código velho" só reinicia quando **pedido** (`reinicio_pedido`) e `reinicios_24h` persistido no `estado.json`. | O coordenador continua religando quem cai; os 4 serviços; o `reiniciar <svc>` manual. | Suíte `coordenador` (489); `Get-ScheduledTask` sem 0x1; 24 h sem "bot no ar" repetido em `avisos_enviados.jsonl`. | **D1, D3** |
| **3** | **Um jeito de gravar estado** (P1), começando pelos dois "altos" abertos | Módulo `estado_json` (ler/gravar/alterar sob trava do arquivo), aplicado em `contas.py` e `parecer.py`; `renomear` grava antes de mover a pasta. | Formato dos arquivos; quem chama. | `test_contas_publicacao_regressions`, `test_varredura_0510_regressions`, `test_recusa_do_gemini_regressions`; repetir as provas `p1b_contas_corrida.py` e `p2_pareceres.py` do scratchpad (devem terminar com 122 de 122 fichas). | Não |
| **4** | **Estado, segunda leva** (P1) | O mesmo módulo em `esteira_sprites/ficha.py`, `mimetizar/espelho/estado.py`, `capas_atrasadas.py`, `cota.py`, `relatorios.py`, `atividade._podar` (poda sob trava), `sonorizar._gravar` e `timeline_arquivo.salvar` com temporário único. | Nada de comportamento. | Suítes `random_builds`, `historias`, `mimetizar`, `remoto`; `python testar.py`. | Não |
| **5** | **Uma trava só** (P2) | `trava_arquivo` sai de `api_http` para um módulo neutro (ou entra em `builds.travas` como `trava_arquivo`); `correio._trancado`, `identity.queue._bloqueio` e `database` chamam ele; `remoto/config.runtime_dir()` passa a honrar `NEURAL_FIGHTS_RUNTIME_DIR`; locks todos em `runtime/locks`. | Os nomes das travas (`ledger__*`, `perfil__*`, `postar__rodada`). | Suítes `ias`, `remoto`, `random_builds`; depois de `python testar.py`, a contagem de `*.lock` em `%LOCALAPPDATA%\neural-fights\locks` **não cresce** (hoje: 92 de teste). | Não |
| **6** | **Momento seguro único** (P4) | `momento_seguro()` num módulo só (publicação em voo, janela da grade, travas de rodada ocupadas); `supervisor.seguro`, `vigia_trabalho`, `delegar.aplicar` e o integrador usam ela; aplicar + reiniciar no mesmo passo. | O que o vigia faz depois de aplicar. | Suítes `coordenador` e `remoto`; teste que segura `historias__auto` e vê `aplicar` recusar. | Não |
| **7** | **Importável de qualquer pasta** (P5) | `.pth` em site-packages com `E:\projetos` (um arquivo de uma linha); tirar `sys.path.append` do `worker.py:35` e o subprocesso de `agenda.avisar`; `delegar.testar` e `delegar.rodar` exportam `PYTHONPATH` da worktree (ela ganha do editável); baixar o teto em `arquitetura_baseline.json`. | Os pacotes editáveis existentes; o `pyproject.toml` da raiz (o CI exige só `neural_fights` na wheel). | `python -c "import remoto, ias, coordenador"` de `C:\`; `ferramentas/auditoria_arquitetura.py --strict`; `postar.txt` sem "No module named"; teste na worktree que imprime `builds.__file__` dentro de `E:\projetos-wt\`. | Não |
| **8** | **Três estados nos medidores** (P7) | `qualidade._audio`/`_ffprobe` devolvem "não medi" como erro próprio; `_servico_do_dia` marca só com tudo ok; `cmd_tudo` e `obsidian.main` com código de saída; `registrar_publicado` grava ERRO no diário; `_nomes_no_banco` não cacheia `None`; linhas do diário sempre com `etapa`. | As guardas que já barram. | Suítes `historias`, `random_builds`, `tests/test_obsidian`; um teste de caso ZERO por medidor. | Não |
| **9** | **Uma porta só para trabalho** (P6) | `origem_ref` obrigatória no pedido; Equipe do app, cérebro e CLI chamam `pedidos.contratar`; vigia avisa "olho" uma vez por entrega; faxina (`delegar limpar --orfas`, `git worktree prune`). | Codex em worktree, vigia aplica, o Grimório. | Suítes `coordenador` + `remoto`; `coordenador.txt` < 500 linhas/dia; `delegar listar` sem "rodando" morto. | **D2, D4, D8** |
| **10** | **Versão e runtime únicos** (P9) + **instalador único de tarefas** (P10) | `{"versao": 1}` nos arquivos de estado; uma `runtime_dir()`; `ferramentas/tarefas.py --instalar` gera as 61 tarefas e os `.cmd` de uma lista só. | Horários da grade e da agenda. | `Get-ScheduledTask` antes/depois idênticos; `python testar.py`. | Não |

### Decisões do Adrian

- **D1 — Tarefas antigas `app_celular`, `bot_telegram`, `vila_flutuante`.** (a) desabilitar (reversível); (b) apagar; (c) manter. **Recomendo (a)**, e apagar só a `retomar_codex`.
- **D2 — Lixo da máquina** (Grimório `limpeza-da-maquina`). **Recomendo:** apagar worktrees órfãs e provas, mover perfis de Chrome para o E:, raiz do git só com o rastreado.
- **D3 — Reinício automático por "código velho".** (a) manter, só fora da janela; (b) só quando o vigia aplica ou alguém manda `reiniciar`. **Recomendo (b)**.
- **D4 — `remoto.delegar criar` solto pelo chat.** (a) bloquear (exige `--pedido`); (b) permitir com aviso. **Recomendo (a)**.
- **D5 — `main` 945 commits atrás de `refactor/arquitetura`.** (a) `main` recebe o ramo; (b) o ramo vira o padrão. **Recomendo (a)**.
- **D6 — Apurador**: (a) abre pedido de investigação com o diagnóstico; (b) mantém remendo próprio. **Recomendo (a)**.
- **D7 — Build que saiu só no TikTok → YouTube depois** (Grimório `build-so-no-tiktok`; recomendo a regra das histórias).

---

## 4. O que NÃO vale mexer

- **`ferramentas/postar.py`** (5.608 linhas): grande e feio, mas as guardas foram medidas uma a uma (172 funções, 66 chamadas conferidas, zero divergência). Reescrever é a receita de repostagem. Só o lançador (etapa 1) e o `adiadas` precisam de toque.
- **`grade.py` e `tipos.py`**: limpos; a grade bate exatamente com as 61 tarefas.
- **`metricas.py` (ledger com trava + fila lateral) e `builds/travas.py`**: o desenho está certo; é o modelo das etapas 3–5.
- **`orquestrador._ler_json/_gravar_json` e `delegar._gravar_json`**: o padrão bom; a reforma é espalhá-los.
- **`conftest.py` da raiz, `testar.py`, `auditoria_arquitetura.py`**: funcionam; só precisam que `remoto/config.runtime_dir` obedeça.
- **O coordenador em si** (`Supervisor` injetável, pulso, threads, `TravaUnica`): estrutura boa; o problema é o gerente duplicado e a janela.
- **O app (PWA)**: 89 telas, zero `pageerror`, rotas todas existentes.
- **Godot/`palco/`**: nenhum defeito de execução confirmado na avaliação de arquitetura (os da auditoria de execução já têm conserto).
- **`atividade.jsonl` em append**: seguro; só a poda.
- **`decisoes/` e o Grimório**: fonte de verdade correta.
