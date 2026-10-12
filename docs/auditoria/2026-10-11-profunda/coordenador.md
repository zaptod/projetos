# Auditoria profunda — Coordenador (Mesa, vigia, cérebro, equipe) — 11/10/2026

Fatia: `coordenador/**` (11 módulos + 10 arquivos de teste, 12.356 linhas). Todos lidos inteiros, função por função. Provas rodadas em `%TEMP%\claude\...\scratchpad\auditoria2\provas\` com `LOCALAPPDATA`, `NEURAL_FIGHTS_RUNTIME_DIR`, `NF_COORDENADOR_PASTA` e `NF_DELEGADOS_PASTA` apontando para pastas descartáveis (nada tocou `%LOCALAPPDATA%\neural-fights`; o estado real foi apenas LIDO para a evidência do item 2). Não repeti os dois defeitos já consertados (`_ler()` → `{}`, 0b8e0d9; "mesmas pastas juntava pedidos", 1257601).

## Examinado
- `__init__.py` — 0 funções; docstring.
- `__main__.py` — 7 funções lidas (`_sid_do_usuario`, `xml_tarefa`, `instalar`, `remover`, `tarefas_antigas`, `montar`, `main`); CLI e montagem do supervisor de produção.
- `acoes_pc.py` — 4 funções (`catalogo`, `tarefa_permitida`, `validar`, `executar`); allowlist das ações do PC.
- `estado.py` — 5 funções (`pasta`, `caminho`, `ler_estado`, `gravar_estado`, `gravar_comando_servico`); o `estado.json` que o app lê.
- `equipe.py` — `GerenteEquipe` + 11 métodos/funções; permissões automáticas (contratar/conferir ficaram sem chamador).
- `supervisor.py` — `Supervisor`, `TravaUnica` + 55 funções/métodos; pulso de 5 s, adoção, religada, comandos, threads de fundo.
- `cerebro.py` — 52 funções; conversa, propostas, Codex só leitura, validação da lista fechada.
- `vigia_trabalho.py` — `VigiaTrabalho` + 61 funções/métodos; coletar → testar → aplicar → commit → limpar; faxinas; Mesa; Grimório; resumo.
- `pedidos.py` — `MesaPedidos`, `_TravaDoArquivo` + 179 funções/métodos (3.621 linhas, lido inteiro); o coração: registrar, contratar, acompanhar, retomar, desfecho, EXECUTAR, Grimório, conversa, conferir, passo.
- `servicos.json` — as 4 fichas (app, bot, carteiro, vila).
- `conftest.py` — 2 (isola pasta do coordenador, avisos, interruptor; bomba no `rodar_codex`).
- Testes (lidos inteiros, procurando teste de dublê e escrita em estado real): `test_coordenador.py` (42 defs), `test_equipe.py` (26), `test_cerebro.py` (28), `test_porta_unica.py` (6), `test_pedidos_ilegivel.py` (7), `test_pedidos.py` (89), `test_pedidos_conferente5.py` (26), `test_pedidos_honesto.py` (110), `test_conversa.py` (41), `test_vigia_trabalho.py` (96). Nenhum escreve no estado real (conftest + `NEURAL_FIGHTS_RUNTIME_DIR` da raiz cobrem `estado`, `delegar`, `orquestrador`, `claude_estado`). Dois testes exercitam caminho que a produção não liga (itens 13 e 7).
- Fora da fatia, só para entender contratos: `remoto/api_http.py::trava_arquivo/_trava_de_arquivo`, `remoto/delegar.py` (`criar`, `aplicar`, `limpar`, `no_fundo`, `ler_config`, `_pid_vivo`, `registrar_pedido_permissao`), `remoto/orquestrador.py::agente_fim/_pid_vivo`, `remoto/decisoes.py` (assinaturas), `random_builds/builds/grade.py`.

## Confirmados (do mais grave ao menos)

### 1. O coordenador inteiro cai quando o app lê `estado.json` no instante do `os.replace` — gravidade: alta
- Onde: `estado.py:36-42` (`gravar_estado`) e `supervisor.py:755-765` (`Supervisor.rodar`).
- O defeito: `gravar_estado` faz `os.replace` sem nova tentativa; no Windows o destino aberto por OUTRO processo (o app lendo para a aba Coordenador, `remoto/api_http.py:530`; `python -m coordenador status`) dá `PermissionError`. `rodar()` chama `self.pulso()` sem `try/except`: a exceção sai do laço, a trava única é solta e o processo morre — com ele as threads do vigia, dos pedidos e da conversa. `pedidos._gravar` (linhas 430-439) tem a nova tentativa exatamente por este motivo; `estado.py` não.
- Quando acontece: a cada pulso (5 s) o coordenador grava `estado.json`; basta uma leitura do app coincidir com o `replace`. Ele volta pela tarefa do Agendador (1-5 min) e perde o estado em memória (`falhas` por hora, `religado_por_codigo`, `erros_comando`, `reinicio_pedido`, `esteira_em`), e um `contratando`/`executando` em voo fica órfão até os prazos de 5 min / timeout+300 s.
- Prova: `p8_estado_race.py` — um filho lendo `ler_estado()` em laço (como o app) e o pai gravando: `rodar() protege o pulso com try/except? False`, `gravar_estado tenta de novo no PermissionError? False`, `gravacoes ate falhar: 0; erro: PermissionError: [WinError 5] Acesso negado: '...\.estado.json.tmp' -> '...\estado.json'`.
- Conserto sugerido: mesma nova tentativa de `pedidos._gravar` em `gravar_estado` (6×0,15 s) e `try/except` por pulso em `rodar()` (logar e seguir).

### 2. Pedido fica "entregue" para sempre quando a entrega é aplicada por um integrador (ou vai para `olho`) — gravidade: alta
- Onde: `pedidos.py:3080-3081` (`_conferir`: `if not ficha.get("aplicado"): return`), `vigia_trabalho.py:593-668` (`_olho` → `_contratar_integrador`), `remoto/delegar.py:2023-2025` (`aplicar` só marca a ficha que aplicou).
- O defeito: o vigia, ao não conseguir aplicar a entrega X (conflito, validador, coletar), contrata `integrar-X`; quando a entrega do integrador é aplicada, `aplicado` fica na ficha `integrar-X`, nunca na ficha X. O pedido só olha a ficha do próprio trabalhador: nunca sai de "entregue", não avisa o Adrian, e o trabalhador X segue "em uso" (`_em_uso_real`), então a faxina nunca limpa a worktree dele. O mesmo para X em `olho` sem integrador.
- Quando acontece: qualquer pedido cuja entrega o vigia não aplica direto. No estado real de hoje: `pedido-96003df6` está "entregue" desde 2026-10-12T05:26 e o vigia o tem em `olho` ("a correção pedida às 10:12 não começou") — ninguém vai fechar.
- Prova: `p7_entregue.py` — pedido entregue, `integrar-<id>` com `aplicado`, 3 dias de pulsos: `situacao=entregue motivo=''`, `avisos ao Adrian sobre este pedido: []`, `o trabalhador original segue 'em uso': True`.
- Conserto sugerido: `_conferir` olhar também a ficha `integrar-<trabalhador>` (aplicado → conferido; falhou/olho → "esperando você" com o motivo do vigia), ou o vigia gravar na ficha original `aplicado_por: integrar-X`.

### 3. Commit do vigia falha e o pedido vira "✅ conferido" com os arquivos soltos na árvore — gravidade: alta
- Onde: `vigia_trabalho.py:949-966` (`_cuidar`: `aplicar` → `commitar`), `remoto/delegar.py:2023-2025` (`aplicado` gravado antes do commit), `pedidos.py:3080-3088` (`_conferir` fecha só por `ficha.aplicado`).
- O defeito: `delegar.aplicar` marca `aplicado` na ficha; o commit por caminho vem depois, no vigia. Se o commit falha (index.lock, hook, git ausente), o vigia vai para `olho` e ainda contrata um integrador (que manda `git apply -3` por cima do que já está aplicado), mas a Mesa vê `aplicado` e manda "✅ Pedido conferido" ao Adrian — nada commitado.
- Quando acontece: `commitar_por_caminho` levanta depois de 6 tentativas com `index.lock` preso, ou qualquer outro erro do `git commit`.
- Prova: `p7_entregue.py` (P7b) — `commitar` falhando: `olho: [('pedido-abcd1234', 'aplicado na árvore, mas o commit falhou ...')]`, `ficha.aplicado depois do commit falhar: {'arquivos': ['remoto/x.py']}`; o pedido com essa ficha: `conferido`, aviso `✅ Pedido conferido`.
- Conserto sugerido: o vigia gravar o hash na ficha (`_mudar_estado(did, commit=...)`) e `_conferir` exigir `aplicado` E `commit`; sem commit, "esperando você" com o motivo do `olho`. E `_contratar_integrador` não contratar quando o motivo começa com "aplicado na árvore".

### 4. `servico_reiniciar` recusado é marcado "executado pelo coordenador" e nunca refeito; a CLI imprime "ok" — gravidade: alta
- Onde: `supervisor.py:559-563` (`processar_comandos`), `supervisor.py:697-708` (`reiniciar_servico` devolve `False`), `__main__.py:202-205` (`reiniciar` ignora o retorno), `acoes_pc.py:43-45` (`reiniciar_tudo_seguro` idem).
- O defeito: `reiniciar_servico` devolve `False` quando `seguro()` recusa (publicação em andamento, carteiro entregando) e só muda `situacao="reiniciando"`; `processar_comandos` não olha o retorno e aplica o comando com `nota="executado pelo coordenador"`. Nada entra em `reinicio_pedido`, então o pulso seguinte não refaz: o reinício pedido pelo app/bot/CLI some. `python -m coordenador reiniciar app` imprime "ok" e sai 0 sem reiniciar (é o passo 3 do fechamento de tarefa no CLAUDE.md).
- Quando acontece: qualquer reinício pedido durante uma postagem (10 vezes por dia, ~30 min cada) ou com o carteiro entregando.
- Prova: `p2_reiniciar.py` — com `postar.py` rodando: `aplicar recebeu: [('c1', {'nota': 'executado pelo coordenador'})]`, `parou: [] iniciou: []`, `reinicio_pedido: set()`; a publicação acaba, 3 pulsos: `parou: [] iniciou: [] situacao: reiniciando`. CLI: imprime `ok`, `codigo de saida: 0 | parou/iniciou a mais: (0, 0)`.
- Conserto sugerido: quando `reiniciar_servico` devolver `False`, `self.reinicio_pedido.add(nome)` e aplicar o comando com nota "agendado: <motivo>"; na CLI, sair com 2 e imprimir o motivo.

### 5. Depois da primeira morte por "saúde ruim", o app é morto 5 s após cada religada enquanto a porta não abrir — gravidade: média
- Onde: `supervisor.py:496-506` (`verificar_servico`), `supervisor.py:466-468` (`religar` não zera `saudes_ruins`).
- O defeito: `saudes_ruins[nome]` só volta a 0 quando a saúde dá "ok". Depois de matar por 3 pulsos ruins o contador fica em 3; o processo novo é adotado e, no primeiro pulso em que a porta 8931 ainda não respondeu, o contador vai a 4 (≥ 3) e ele é morto de novo. A tolerância de 15 s só vale para o primeiro.
- Quando acontece: app lento para abrir a porta (importa patchright etc.): 5 falhas em uma hora → "falhou; parei de tentar".
- Prova: `p3_saude.py` — `pulso 3: saudes_ruins=3 parou=[10]`; religa no pulso 5 (`PID 100`); `pulso 6: ... porta ainda fechada; saudes_ruins=4 parou=[10, 100]` → "o processo novo 100 foi morto no pulso 6: nasceu no pulso anterior".
- Conserto sugerido: `self.saudes_ruins[nome] = 0` em `religar` (e no `reiniciar_servico`).

### 6. A trava do `pedidos.json` vale entre processos, mas quem escreve sem ela perde gravações e o prazo de 10 s faz o `pedir` morrer com traceback sem registrar o pedido — gravidade: média
- Onde: `pedidos.py:98-150` (`_TravaDoArquivo`, prazo padrão de `trava_arquivo` = 10 s, `remoto/api_http.py:542`), `__main__.py:155-164` (`pedir` só trata `ValueError`), `pedidos.py:3336-3365` (`passo` segura a trava durante toda a `_andar_os_pedidos`).
- O defeito (duas partes): (a) qualquer escritor que faça `_ler()`/`_gravar()` sem `with _TRAVA` — o padrão que a própria suíte usa 8 vezes (`test_pedidos.py:164-166`, `test_pedidos_conferente5.py:324-328, 338-341`, `test_pedidos_honesto.py:1159-1163` …) e que um script avulso copia — perde gravações do outro lado e morre com `PermissionError`; (b) se o `passo` do coordenador segurar a trava mais de 10 s (ele lê, sob a trava, `estado.json` de cada trabalhador, `eventos.jsonl` de trás para frente até 64 MB, `fundo.txt`, `resposta.md`…), `python -m coordenador pedir` estoura com `TimeoutError` (OSError, não capturada) e o pedido NÃO fica registrado; o app devolve 503.
- Quando acontece: (a) script na mão ou teste rodado contra a pasta real; (b) pulso lento com muitos pedidos vivos. É a explicação provável do "dois processos perderam a mudança um do outro" de ontem: não é a trava falhando.
- Prova: `p1_run.py` — (a) dois processos COM `_TRAVA`: `esperado 300, gravado 300`; um com e um SEM: `esperado 300, gravado 207, codigos [0, 1]` (o sem trava morreu em `_gravar: os.replace … PermissionError`); (c) um processo segura a trava 13 s e `pedir` no meio: `pedir: codigo 1 depois de 10.6s`, `TimeoutError: trava ocupada ha mais de 10 s: pedidos.lock`, `pedidos gravados depois: 0`. Leitor sem trava (`para_o_app` em laço) + escritor com trava: `esperado 150, gravado 150` (o retry do `_gravar` cobre).
- Conserto sugerido: `_TravaDoArquivo.__enter__` passar `prazo` maior (60 s) e `main("pedir")` tratar `OSError` com mensagem e código 3; no `passo`, ler os arquivos dos trabalhadores fora da trava (como já faz com o `criar`).

### 7. Ficha "criado" antiga com commit à frente dispara um aviso no Telegram a cada passo (60 s) — gravidade: média
- Onde: `vigia_trabalho.py:783-799` (`_faxina_delegados`, laço do `abandonar`), `vigia_trabalho.py:593-608` (`_olho` sempre avisa).
- O defeito: o laço não consulta `mem["olho"]`; a cada passo chama `_olho(... integrar=False)`, que manda "⚠ entrega X travou (…) precisa de olho" ao Telegram e empilha novidade. `commits_a_frente` devolvendo `None` (git falhou / sem `base`) também cai aí (`None != 0`).
- Quando acontece: um `criado` com mais de 24 h que tenha commit próprio ou cuja branch o git não resolva: 1.440 avisos por dia por ficha até o Adrian limpar a mão. O teste `test_criado_antigo_sujo_precisa_de_olho_sem_apagar` roda um passo só e não vê.
- Prova: `p4_p5_vigia.py` (P4) — 5 passos: `avisos ao Telegram ate agora = 2, 3, 4, 5, 6`; com `commits_a_frente → None`: `mais um aviso: 1`.
- Conserto sugerido: `if did in mem["olho"]: continue` antes do `_olho`, e tratar `None` como "não sei" (evento, sem olho).

### 8. Entrega em `coordenador/**` aplicada e o coordenador continua com código velho: `pedir_reinicio("coordenador")` é um no-op — gravidade: média
- Onde: `vigia_trabalho.py:977-978` (chama `pedir_reinicio("coordenador")`), `supervisor.py:687-691` (`pedir_reinicio` só aceita nome em `self.servicos`).
- O defeito: o vigia pede, o supervisor ignora em silêncio (sem evento). O coordenador roda o código antigo até alguém matá-lo; `status --curto` diz "serviços: código atual" (só olha os 4 serviços). Guarda morta.
- Quando acontece: toda entrega que toque `coordenador/` (como as desta auditoria).
- Prova: `p4_p5_vigia.py` (P6) — `pedir_reinicio("coordenador")` e `pedir_reinicio("app")`: `reinicio_pedido: {'app'} | eventos: ['app']`.
- Conserto sugerido: `pedir_reinicio("coordenador")` marcar uma bandeira que faz `rodar()` sair em momento seguro (a tarefa do Agendador religa em ≤5 min), com evento e aviso.

### 9. "Suspender o PC" nunca olha o render — gravidade: média
- Onde: `supervisor.py:387-389` (`_executar_acao` não passa `render_ativo`), `acoes_pc.py:37-47` (`render_ativo=lambda: False`).
- O defeito: a guarda `render_ativo` existe na assinatura mas ninguém a implementa nem a passa; só `publicar_ativo`. Com o Godot renderizando, "suspender" (do app ou proposta do cérebro confirmada) põe o PC para dormir no meio do render.
- Quando acontece: qualquer `pc_acao suspender` durante render/produção pesada.
- Prova: `p9_render_e_backoff.py` (P9) — `render_ativo passado pelo supervisor? False`; chamada com os argumentos exatos do supervisor: `comando que iria ao Windows com o Godot renderizando: [['rundll32', 'powrprof.dll,SetSuspendState', '0,1,0']]`.
- Conserto sugerido: `render_ativo=lambda: any(re.search(r"godot|palco.*render|producao", p["comando"], re.I) for p in self.processos())`.

### 10. `esperando` da memória do vigia nunca é limpo quando a entrega é aplicada/limpa por fora, e a faxina pula o delegado por isso — gravidade: baixa
- Onde: `vigia_trabalho.py:732-749` (`_faxina_olho` só limpa `olho` e `corrigidos`), `vigia_trabalho.py:770-771` (`_faxina_delegados`: `did in mem["esperando"] → continue`).
- O defeito: `_cuidar` só roda para `terminou` sem `aplicado`/`limpo`; aplicada a mão (ou pelo orquestrador), a entrada em `esperando` fica para sempre no retrato (`trabalho.esperando` do app) e bloqueia a faxina da worktree.
- Quando acontece: entrega que esperou (publicação, carteiro, árvore suja) e foi aplicada por outro caminho; ficha que falhou enquanto esperava. O estado real hoje tem 6 entradas em `esperando` (2 "publicacao em andamento"), sem como saber daqui quais são fantasmas.
- Prova: `p4_p5_vigia.py` (P5) — `esperando 3 passos depois de aplicada e limpa por fora: {'x1': 'publicacao em andamento'}`; `y1 falhou ha >6 h; esperando: {..., 'y1': 'carteiro entregando'} | limpar chamado: []`.
- Conserto sugerido: em `_faxina_olho`, também tirar de `esperando`, `sujo_desde` e `sujo_avisado` o que está aplicado, limpo, sumiu ou não está mais em `terminou`.

### 11. Reiniciar um serviço em backoff mata e não religa — gravidade: baixa
- Onde: `supervisor.py:697-708` (`reiniciar_servico` → `parar` e depois `religar(..., forcar=False)`), `supervisor.py:441-447` (`religar` recusa com `proximo_reinicio` no futuro).
- O defeito: o processo é parado, `religar` devolve `False` pelo backoff e `situacao` fica "rodando" com `pid=None`; o serviço só volta quando o backoff passar (até 5 min) e o pulso notar a ausência.
- Prova: `p9_render_e_backoff.py` (P10) — `reiniciar_servico devolveu False | parou: [10] | iniciou: [] | situacao: rodando`.
- Conserto sugerido: `reiniciar_servico` chamar `religar(nome, "pedido", forcar=True)` (a parada já foi feita) ou zerar `proximo_reinicio` antes.

### 12. Trava única com pid reaproveitado: o coordenador sai com 1 em silêncio, a cada 5 min — gravidade: baixa
- Onde: `supervisor.py:187-215` (`TravaUnica.adquirir`), `supervisor.py:755-758` (`rodar` devolve 1 sem log nem aviso).
- O defeito: se o `coordenador.lock` guardar um pid que agora é de outro programa, `adquirir` devolve `False` e `rodar()` sai sem escrever nada; a tarefa tenta a cada 5 min e falha calada; o app vê `vivo: False` sem motivo.
- Prova: `p9_render_e_backoff.py` (P11) — pid "vivo" de outro programa: `rodar() devolveu 1 | log: [] | avisos: []`.
- Conserto sugerido: gravar no lock também a linha de comando (conferir que o dono é `-m coordenador`) e logar/avisar quando não adquirir.

### 13. Guarda morta: o conferente dos pedidos nunca é contratado, e o gerente nunca contrata nem confere — gravidade: baixa
- Onde: `pedidos.py:3082` (`if not pedido.get("conferir")`), `pedidos.py:2693-2694` e `_ROTULO["entregue"]` ("esperando o vigia testar e aplicar, depois o conferente olha"), `equipe.py:75-119` (`_contratar`, `_conferir_aplicadas`).
- O defeito: nenhum código de produção põe `conferir` no pedido (grep em todo o repositório: só `test_pedidos.py:165` o liga à mão), então `_conferir` sempre fecha por "prova automática" e as 40 linhas do conferente (`mesa-conf-*`, APROVADO/DEFEITOS) não rodam; a mensagem ao Adrian e o rótulo prometem um conferente que não existe. `equipe._contratar` e `_conferir_aplicadas` não têm chamador fora de `test_equipe.py`. Pode ser decisão (07/10, uso mínimo do Claude / prova automática), mas então é texto que mente e teste que testa o dublê.
- Prova: `grep -rn '"conferir"\]\|conferir=True' --include=*.py` → só `coordenador/test_pedidos.py:165`; `grep -rn "_conferir_aplicadas\|_contratar(item"` → só `test_equipe.py:109` e um comentário.
- Conserto sugerido: ou expor `conferir` (ex.: `pedir --conferir`, cargo conferente da config), ou apagar o caminho e corrigir as mensagens.

## Não confirmados
- "Dois processos gravando `pedidos.json` perderam um a mudança do outro" por falha da trava entre processos: NÃO reproduzido — 300/300 com os dois lados sob `_TRAVA` (`msvcrt.locking` no `pedidos.lock` vale entre processos). As causas que reproduzi estão no item 6 (escritor sem a trava; prazo de 10 s). Para fechar, falta saber qual script da CLI rodou ontem e se ele usou `_TRAVA`.
- `cerebro.atender` marca a entrada como lida ANTES de pensar (`cerebro.py:735`): uma queda do processo (não exceção) entre marcar e responder perde a mensagem do Telegram em silêncio. Não provei com queda real; a exceção comum é tratada.
- `MesaPedidos.passo` segurando a trava por muito tempo em produção (`_rodada_mais_nova` lê até 64 MB por ficha terminada, a cada pulso, sob a trava; `_estado_do`/`_resposta`/`fundo.txt` por pedido): não medi com o estado real (não quis tocá-lo); é o que torna o item 6(b) provável.
- `vigia._cuidar` trata `fim` ausente como "mais velho que o vigia" (`str(None or "") < mem["desde"]`, linha 840): não achei ficha "terminou" sem `fim` no delegar.
- `cerebro._gravar("propostas.json")` sem nova tentativa com o app lendo propostas (`propostas_para_o_app`): mesma corrida do item 1, mas dentro de thread protegida (`em_fundo`) — vira "Falhei ao pensar" e a entrada já lida se perde. Não rodei a corrida.
