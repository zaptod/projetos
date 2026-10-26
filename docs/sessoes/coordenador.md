# Coordenador residente

## Porta única de trabalho (07/10/2026)

Todo trabalho é um pedido em `coordenador/pedidos.py`. A fila da Mesa é só a
visão dos pedidos de origem `fila`; itens antigos migram uma vez. O gerente não
contrata da fila: só `MesaPedidos.passo` despacha. No chat, registre com
`python -m coordenador pedir "texto" [--permitido CAMINHO] [--ia codex|claude]`;
`delegar criar` exige `--pedido ID`. A exceção manual `--fora-da-porta MOTIVO`
fica anotada no diário do pedido.

O coordenador e o processo local que mantem app, bot, carteiro e Vila flutuante vivos sem depender de uma janela do VS Code. Ele adota processos ja existentes pela linha de comando, registra o estado em `%LOCALAPPDATA%\neural-fights\coordenador\estado.json` e religa quem cai (mesmo dentro da janela das postagens).

**Um gerente so (etapa 2, D3 de 13/10/2026):** codigo velho so MARCA (`codigo_velho` no estado, `status --curto` diz quem); o reinicio acontece quando e PEDIDO — o vigia aplicou uma entrega (`pedir_reinicio`), o app mandou `servico_reiniciar` ou alguem rodou `coordenador reiniciar <svc>` — e nunca de `post-12` a `post+18` min de um horario da grade (`grade.minuto(h)`), nem com publicacao em voo. `reiniciar_servico` mata TODOS os processos que casam a assinatura e so sobe o novo depois de ver o velho sumir da lista (ate 15 s); se ele nao morre, nao sobe irmao. `reinicios_24h` e o pedido pendente sobrevivem ao coordenador subir de novo (lidos do `estado.json`), e `estado.json` e gravado por temporario + replace com ate 10 tentativas.

Para instalar a tarefa (uma vez, em um prompt do usuario):

```powershell
cd E:\projetos
python -m coordenador instalar-tarefa
python -m coordenador desligar-tarefas-antigas
```

Ela inicia no logon como `NeuralFights_coordenador`. Para conferir ou controlar manualmente:

```powershell
python -m coordenador status
python -m coordenador status --curto
python -m coordenador reiniciar app
```

`reiniciar` so imprime `ok` (codigo 0) quando reiniciou. Recusado pelo momento
(janela, publicacao, carteiro entregando) diz o motivo, deixa o pedido em
`reinicios_pendentes.json` para o residente e sai com 2; velho que nao morre
(sem permissao?) ou novo que nao sobe sai com 3.

`status --curto` e o retrato para handoff: le os pedidos, incluindo o registro
do trabalhador (PID conferido, prova e espera), sem varrer fichas de delegados.

**Consertos da auditoria profunda (14/10/2026, `docs/auditoria/2026-10-11-profunda/consertos/coordenador-e-delegacao.md`):**
- `delegar limpar --orfas` so apaga pasta `codex-*` que NENHUM git conhece: junta o `worktree list` de todos os repositorios das fichas, toda ficha nao limpa protege a sua pasta, e pasta com `.git` (worktree viva de outro repo, ou registro perdido) nunca e apagada (COO-1; a do `E:\jogo_ZOMBIE` ia ao rmtree).
- O pedido so vira "conferido" com o COMMIT feito: hash gravado na ficha pelo vigia (`delegar.registrar_commit`; a do integrador grava tambem na original, `aplicado_por`) ou os arquivos limpos na arvore (aplicado e commitado a mao). Aplicado sem commit fica "entregue" com o motivo e avisa uma vez depois de 10 min; a entrega aplicada pelo `integrar-<id>` fecha o pedido; `olho` do vigia aparece como motivo (COO-2). O ramo `conferir` dos pedidos e o `_contratar`/`_conferir_aplicadas` do gerente (codigo morto) sairam (COO-20).
- `pedidos.lock` espera 60 s; `coordenador pedir` com a Mesa ocupada diz "recusado: a Mesa está ocupada" e sai com 3 (COO-6).
- **Mesa ilegivel tem alarme (19/10/2026)**: o `pedidos.json` zerou na queda de 16/10 21:38 e ficou ilegivel 3 dias sem ninguem saber. O pulso dos pedidos (`Supervisor._pedidos_vigiados`) abre um incidente em disco (`mesa_ilegivel.json`, `pedidos.marcar_ilegivel`) e manda UM aviso no Telegram; ao ler de novo fecha (`marcar_legivel`) e avisa "a Mesa voltou". O retrato leva `mesa_ilegivel` (o app mostra um cartao vermelho na Agora). Ver `docs/sessoes/app-e-bot.md`, "v73, 2ª volta".
- `aplicar`: `git apply -3` que falha sem conflito desfaz e recusa; o sw.js/teste da casca reescritos entram em `aplicado.arquivos` (e com mudanca alheia nao sao tocados) (COO-7, COO-11). `coletar` com `-z`/`core.quotepath=false` (nome com acento) e `.handoff.md` e ruido (COO-8, COO-23).
- `claude.json` trancado: `ler` tenta 5 vezes, `mudar` repete o replace; quem ja roda (guarda do despachante, pulso) so para com "proibido" do arquivo ou ilegivel por 2 s ou mais (COO-9).
- Ficha `rodando` grava `pid_criado`; PID vivo com outra hora de criacao conta como morto, e `rodando` sem evento ha `rodar_timeout_s + 600` s fecha (COO-10). O `coordenador.lock` grava pid + hora de criacao (lock antigo: exige `-m coordenador` na linha de comando); nao subir loga uma vez por hora (COO-14).
- `pedir_reinicio("coordenador")` (entrega em `coordenador/**`): o laco sai no proximo momento seguro sem thread de fundo viva, e a tarefa o religa (COO-12). "Suspender o PC" recusa com render (`--write-movie`, ffmpeg, `main.py noite|palco|...`, historias `auto`) (COO-13).
- Apurador: Mesa fora guarda a investigacao (COO-15); estado corrompido esgota tambem as apuracoes (COO-24). Grimorio: doc de sessao fora de utf-8 nao derruba o `responder` (COO-16). Permissao com alvo absoluto dentro do repo libera o relativo (COO-17). `esperando` do vigia limpa o que foi resolvido por fora; "criado antigo" avisa uma vez (COO-18, COO-19). `corrigir` recusado mantem a prova dos testes; `pedido_de_permissao` com `diff: None`; `ler_eventos` no corte exato (COO-21, 22, 25).

Para desfazer a substituicao das tres tarefas antigas, execute `python -m coordenador religar-tarefas-antigas`. Para remover somente a tarefa nova, execute `python -m coordenador remover-tarefa`.

Os comandos de celular aceitos sem IA sao `servico_reiniciar`, `servico_parar`, `servico_ligar` e `pc_acao`. Acoes do PC passam por uma allowlist; nao ha execucao de texto arbitrario. O interruptor do Claude interrompe somente delegados, nunca esses quatro servicos.

## O cerebro (02/10/2026): ele pensa, a mao e fechada

Pedido do Adrian (01/10): "nao quero depender do VS Code aberto" e "eu quero que o coordenador pense sim". Codigo: `coordenador/cerebro.py`; testes: `coordenador/test_cerebro.py` (dubles; o `conftest.py` troca o `rodar_codex` por uma bomba e falha o teste que chamar o Codex de verdade).

- **Quem pensa e o Codex, so leitura.** `codex exec --sandbox read-only --ephemeral --skip-git-repo-check -C <pasta temporaria vazia> --output-schema <schema> -o <saida> [-m modelo_codex da Mesa] -c model_reasoning_effort="medium" -`, prompt por stdin, pelo `delegar.comando_codex` (node + codex.js). Ambiente sem variaveis de segredo. Nunca `workspace-write` (ha teste).
- **Ele so devolve JSON** `{"resposta", "acoes": [{"tipo", "valor", "porque"}]}`. O `valor` e texto (objeto vai como JSON em texto: o schema estrito nao aceita objeto livre). O Python valida cada acao (`cerebro.validar`); fora da lista = descartada e registrada na conversa (`descartadas`).
- **Executa sozinho:** `servico_*` sobre os servicos do `servicos.json` e `pc_acao` do catalogo SEM perigo. Vira comando na fila do orquestrador (`aparelho: cerebro`), que o supervisor aplica no proximo pulso, com o rastro de sempre. O `rodar_tarefa:` fica fora (pode ser uma postagem).
- **Vira PROPOSTA** (Confirmar/Recusar no app, vence em 30 min): `pc_acao` com perigo, `fila_adicionar` e `delegar_codex` (id, titulo, tarefa, `permitidos`; caminho proibido do despachante nem vira proposta). Confirmar revalida a acao; delegar so com o Claude liberado, e roda `delegar.criar` + `rodar --fundo`.
- **Nao existe nem como proposta:** publicar/postar/upload, conta, senha, token, apagar, push (`cerebro.PROIBIDO`, no tipo e no valor). A resposta diz que e com a sessao do Claude.
- **Guardas:** Claude proibido = nao pensa (responde que esta proibido; a `mensagem` da Mesa fica guardada para a sessao); teto do Codex (`delegar.conferir_teto`); limite proprio de 30 pensamentos por hora (`config.json` da pasta: `{"pensamentos_por_hora": N}`).
- **Nao rouba a sessao do VS Code:** o comando `mensagem` so e dele quando o vigia do orquestrador NAO esta `ouvindo` nem `acordou` e a mensagem tem mais de 60 s. Ao responder, marca `orquestrador.aplicado(id, nota="coordenador: ...")`. Com o cerebro ligado, o aviso "o Claude nao esta aberto" sai de cena.
- **Contexto do prompt (~20 mil caracteres), declarado DADO e nao instrucao:** o estado do coordenador, a Mesa (agora, fila, concluidos), os erros recentes do `atividade.jsonl`, o lote/estoque (`remoto.lote.resumo`), os delegados, o uso do Codex e a lista fechada.
- **Entradas diretas:** o texto sem `/` no Telegram (`remoto/comandos.py: falar_ao_coordenador`) e a aba Conversa do app (`POST /api/coordenador/falar`) gravam em `entrada.jsonl`. O Telegram responde na hora "🛰 recebido, pensando…", e o coordenador manda a resposta pelo `avisar_telegram` de sempre.
- **Rodando:** o laco chama `cerebro.atender` a cada pulso, numa thread (uma por vez; pensar leva ate 180 s). A entrada e marcada lida ANTES de pensar.

Arquivos em `%LOCALAPPDATA%\neural-fights\coordenador\`: `entrada.jsonl`, `entrada_lida.json`, `conversa.jsonl` (`{id, em, de: adrian|coordenador, texto, origem: app|telegram, acoes, descartadas?, pensou?}`), `propostas.json` (`{id, em, vence_em, situacao: pendente|confirmada|recusada|vencida|falhou, acao, texto, porque, origem, nota?}`), `pensamentos.jsonl`, `config.json`, `cerebro.lock`. Sob o pytest, sem `NF_COORDENADOR_PASTA`, a pasta e a descartavel do conftest (`estado.pasta`): o teste antigo do bot com texto livre nao escreve na entrada real.

## O vigia de trabalho (02/10/2026)

Pedido do Adrian (02/10, 00:1x): "as tarefas no app estao todas paradas, quero alguem de olho nisso tambem", "alguem checando se precisa de decisao pro Grimorio", "alguem checando o avanco das tasks". Codigo: `coordenador/vigia_trabalho.py`; testes: `coordenador/test_vigia_trabalho.py`. O supervisor chama `passo()` a cada 60 s, numa thread.

1. **Entregas do Codex.** Delegado `terminou`, sem `aplicado` nem `limpo`, que terminou DEPOIS que o vigia nasceu (`desde` na memoria; os mais velhos so aparecem como `antigos`, porque varios ja foram aplicados a mao): `coletar` → validador → testes (o `testes_cmd`/`testes.cmd` do estado, senao `python -m pytest <pastas de topo mudadas> -q`; so `docs/` = sem testes; o `delegar.testar` ja poe TEMP no E: e `-p no:cacheprovider`) → momento seguro (o `seguro` do supervisor: sem publicacao e fora de [post−12, post+18]; o `aplicar` do despachante ainda recusa :25–:55, e isso tambem e espera) → arvore principal sem mudanca nao commitada nesses arquivos → `aplicar` → commit POR CAMINHO (`git commit -F - -- <arquivos>`, mensagem "<primeira linha util da resposta> (feito pelo Codex, validado pelo vigia)" + Co-Authored-By) → `limpar`. Mudou `remoto/`, `ias/`, `historias/contos/llm/` ou `painel/`: `pedir_reinicio` ao supervisor (reinicia no proximo momento seguro).
   - Testes vermelhos: UMA correcao (`delegar corrigir --fundo` com os ultimos 4 mil caracteres do `testes.log`), so quando o Codex pode comecar (fora de :30–:45, nenhum outro rodando, teto). Falhou de novo, o validador recusou, a correcao nao comecou em 10 min, ou o commit falhou: "entrega do Codex <id> precisa de olho: <motivo>" no Telegram e nos eventos, e nao mexe mais.
2. **Mesa.** Item `agora` com `CODEX` (maiusculo) no titulo cujos delegados citados (o id, ou todas as palavras dele: "armas 16F" cita `armas-16f`; so delegados criados a partir de 30 min antes do item) estao todos aplicados: `agente_fim(concluido, commits)`. Item sem relato ha 45 min: avisa uma vez por relato.
3. **Grimorio.** Na primeira vez que ve a entrega, a secao "o que ficou duvidoso" / "o que ficou de fora ou em duvida" / "duvidas" / "precisa de decisao" da `resposta.md` vai ao cerebro (`cerebro.classificar_duvida`, read-only, schema `{precisa_decisao, titulo, pergunta, opcoes, contexto}`). Escolha de produto com 2–3 opcoes vira no por `decisoes.adicionar_e_commitar`, no projeto da parte do item da Mesa (senao `geral`). Sem cerebro (proibido, teto, limite): so avisa. No maximo 5 nos por dia; titulo igual (normalizado) a um no existente ou ja criado: nao cria.
4. **Resumo de andamento:** Telegram + evento `trabalho_resumo`, so com novidade e no maximo a cada 60 min. O retrato vai sempre no `estado.json`, chave `trabalho` (formato no docstring do modulo), e o app mostra no cartao "Trabalho".
5. **Claude proibido:** so observa (nao coleta, nao testa, nao aplica, nao corrige, nao fecha a Mesa, nao cria no); avisos de parada e resumo continuam.

**Prova de tela obrigatoria (02/10):** se o diff validado tocar
`remoto/app/**` ou `remoto/api_http.py`, o vigia prefixa os testes com
`NF_TESTE_NAVEGADOR=1`. Assim o `remoto/test_app_tela.py` abre o Chrome contra
o servidor isolado antes de aplicar a entrega; qualquer falha tem o mesmo
destino de um teste vermelho: a entrega nao e aplicada.

**Desligar so o aplicar:** `{"vigia_aplica": false}` no `config.json` da pasta do coordenador. A entrega validada e testada fica em `esperando` ("pronta para aplicar") e o orquestrador aplica; o resto do vigia segue.

Memoria em `trabalho_memoria.json` (vistos, aplicados, corrigidos, olho, esperando, avisos de parada, nos por dia): reiniciar o coordenador nao repete aviso. A mesma entrega com o mesmo motivo vai ao `olho` (e ao Telegram) UMA vez: a guarda mora no `_olho`, por onde passam os 12 caminhos (maquina.md #1: 6.489 linhas `trabalho_olho` num dia, 14/10/2026).

## O vigia das rodadas penduradas (14/10/2026, SCR-7)

A rodada de historias das 07:02 de 12/10 (pid 4332) calou no Gemini as 13:09 e segurou `historias__auto` 31 h; os disparos seguintes sairam "ja tem uma rodada" e nada matou o Python (as 49 tarefas tinham PT72H, e o Agendador no limite mata so o `wscript`). Codigo: `coordenador/vigia_rodadas.py` (ligado pelo `montar()`, uma olhada por minuto, em fundo) e `random_builds/builds/rodada_viva.py`.

- A rodada longa (`agenda.rodar`/`rodar_faixas` das historias, `noite.rodar` dos builds) grava `<runtime>/rodadas/<pid>.json` (pid, inicio, trava, rotulo, pulso) quando PEGA a trava, e apaga quando solta. Cada linha do diario dela (`_SaidaNoDiario`, `_diario`, `noite._Diario`) e o laco do supervisor das faixas renovam o `pulso` (no maximo a cada 30 s).
- Pulso parado ha `LIMITE_SEM_PULSO_MIN` (120; o pior trecho calado saudavel medido nos logs de set-out foi 43,4 min nos builds e 22,6 min nas historias) com o MESMO processo vivo (a hora de criacao do pid tem de ser anterior a ficha): `taskkill /T /F` na arvore, confere a morte, apaga a ficha, evento `rodada_encerrada` e Telegram com pid, faixa e ultimo sinal. A trava de arquivo solta com o processo. Se nao morrer: avisa UMA vez, "feche na mao".
- Pid morto ou reaproveitado: a ficha e lixo e sai, sem aviso. Rodada que fala nao morre, por mais longa que seja.
- As tarefas `Historias_auto_*` e `NeuralFights_gerar_*` passam a nascer com `ExecutionTimeLimit` PT6H (`LIMITE_DA_TAREFA` nos dois instaladores); as que existem so mudam quando alguem reinstalar.

**PC religou (SCR-1, decisao `geral/pc-religado`: so o aviso).** Na primeira subida do coordenador depois de um boot novo (`coordenador/religou.py`, chamado pelo `rodar` do `__main__`), um aviso: hora do boot, hora do logon e o ultimo pulso do coordenador antes de cair (o `pulso_em` do `estado.json`). Uma vez por boot (marca `boot_<epoch>.marca` com O_EXCL); a primeira subida depois de instalar so grava a marca. Nao guarda senha nem liga logon automatico.

**Trava ocupada sai 0 (SCR-6).** Outro coordenador no ar nao e falha: com 1, o RestartOnFailure (PT1M x999) relancava a cada minuto. `desligar-/religar-tarefas-antigas` seguem nome a nome e dizem qual falhou. O `TimeTrigger PT5M` do XML FICA: e ele que religa o coordenador depois do "saio para subir com o codigo novo" (saida 0, que o RestartOnFailure nao cobre) — o 0x800710E0 a cada 5 min e o preco disso.

## Permissoes dos trabalhadores (03/10)

Cada tarefa guarda seu `repo` e `testes_cmd`; worktree, coleta, teste, aplicar,
commit do vigia e limpeza usam esse repositorio. `criar --repo` troca o repo da
tarefa, e o cargo `jogo-zombie` declara `E:\jogo_ZOMBIE` e `npx vitest run`.
Quando um trabalhador sai do escopo, `.permissao.json` o deixa em
`aguardando_permissao`; o gerente retoma regras automaticas e pede o Adrian nas
outras. O pedido continua chegando ao Adrian mesmo com o gerente desligado.

**Para ligar:** o `python -m coordenador rodar` ja monta os dois (`__main__.montar`). O coordenador que esta rodando so pega o codigo novo quando reiniciar (a tarefa `NeuralFights_coordenador`); nada foi reiniciado nesta entrega.

## Pedido honesto v2 (05/10): regras fixas, nada de adivinhar por texto

A v1 lia frases ("nao foi possivel") e palavras soltas, e caiu em 24 sondas do conferente. Agora (`coordenador/pedidos.py`):
- **Desfecho:** so a ULTIMA linha `DESFECHO: feito | bloqueado — ... | falhou — ...` decide. Sem ela, UMA continuacao ao mesmo trabalhador (`COBRAR_DESFECHO`); faltou de novo, `esperando_voce` com "o trabalhador nao declarou o desfecho — leia a resposta". `arquivos_de_codigo` nunca conta `resposta.md`/`.permissao.json`.
- **Estado do servidor** (gerente, renovacao, paralelo): roda sozinho so pela escolha ESTRUTURADA do Grimorio (opcao com `acao_servidor`, ex.: `decisoes/geral/gerente-ligado.json`; `decisoes adicionar --opcao "id=Rotulo|descricao|gerente ligar"`). `EXECUTAR: gerente ligar` de trabalhador vira permissao `estado_do_servidor` (regra so `perguntar_ao_adrian` ou `negar`, sem "Permitir sempre"); aprovada em Agora › Equipe, o pulso executa, rele e responde. A ficha volta a `terminou` (ninguem e relancado).
- **Origem do Grimorio:** nó criado para um pedido leva `origem.pedido` (`decisoes adicionar --pedido <pedido-id>`). A resposta só retoma esse pedido; se ele já fechou, fica anotada nele. Nó de chat/manual não abre trabalho: a Mesa o marca lido como `resposta sem pedido de origem: <nó> = <opção>`, deixa o aviso na tela e o `decisoes leitor` ainda o mostra para o chat decidir o próximo passo.
- **Continuacao (corrigida pela 3a conferencia):** texto livre NUNCA gruda em pedido nenhum, nem no ativo: abre pedido novo. A regra "gruda no ativo mais novo" mandou "Faz o video novo do Neural Fights" ao pedido-7c727778 (digen-parede, `trabalhando` com o pid 11412 morto, em retomada por horas), e sem ler o assunto nao ha como saber a qual pedido o texto pertence. Continuar e so EXPLICITO, com o id: o Responder do cartao (`POST /api/coordenador/pedido/<id>/responder`, pareamento + `--acoes`) ou `/responder <id> <texto>` no Telegram (o bot nao guarda o id da mensagem, entao reply a um aviso nao basta; o id vem em todo aviso de pedido). O "Novo assunto" e o `/novo` sairam (o `/novo` so explica). Os avisos do app e do Telegram dizem QUAL pedido (id + 1a linha).
- **Conversa solta (refeita na 5a conferencia):** LISTA FIXA e pequena, comparada INTEIRA sem acento nem pontuacao: `SAUDACOES` (oi, ola, bom dia/tarde/noite, e ai, opa, coordenador), `PERGUNTAS_DE_STATUS` (qual o progresso, como estao as coisas, alguma novidade, status, e ai como ta) e `AGRADECIMENTOS` (ok, valeu, obrigado, beleza); ate `CONVERSA_MAX_PECAS` (3) frases da lista em sequencia ("bom dia, coordenador, alguma novidade?"). Sobrou uma palavra de fora, e pedido ("reinicie o app", "pode ligar o gerente?", "ja loguei"). Tem precedencia sobre a pergunta de estado do cerebro. No Telegram a resposta volta NA RESPOSTA do bot (o `avisar` do processo do bot e vazio).
- **A conversa responde como gente (06/10/2026).** Medido no `pedidos.json`: "Ola" (pedido-48c48ef4, 02:54) recebeu o despejo "Retrato do servidor (02:54): 9 pedido(s) aberto(s). - pedido-cb44cd52 (esperando voce)..." (o `_retrato` era o TEXTO da resposta), e "Orquestrador?"/"Orquestrador conversei comigo." (03:14) viraram pedido de trabalho, "esperando" o teto do Claude (52%, teto 50%), sem resposta (a lista so tinha "coordenador"). Agora:
  - a lista fixa ganhou o chamado "orquestrador" e os pedidos de conversa ("tudo bem", "voce esta ai", "o que voce esta fazendo", "converse/fala comigo", e o "conversei comigo" do ditado do celular); continua comparada inteira;
  - conversa NUNCA entra na fila de trabalho: no app ela nasce `papo: "pensando"` e a thread PROPRIA `conversa` do pulso (`Supervisor.processar_conversa` -> `pedidos.atender_conversa`) responde em segundos com o modelo leve (`conversar_pelo_codex`: o Codex so leitura do cerebro, esforco `low`, prazo 45 s, sob `cerebro.disponivel`; medido 5,3-7,9 s), com o retrato como CONTEXTO (`_contexto_da_conversa`: assuntos em palavras dele, sem id) e nunca como texto. Sem modelo (proibido, teto do Codex, limite por hora, erro, prazo, ou resposta com id/hash/pid/arquivo), vale a resposta-modelo `_papo_modelo` ("Oi, Adrian! Estou aqui (03:40). Agora estou cuidando de «...». ... Quer que eu faca alguma coisa?"). O Claude fica de fora da conversa: o teto do Adrian ("passou de 50%, para tudo") protege a janela dele. No Telegram a resposta-modelo vai na hora (o bot nao roda modelo). Coordenador parado: passado `PAPO_PRAZO_S` (90 s), o `para_o_app` mostra a resposta-modelo guardada, sem gravar;
  - o pedido de TRABALHO ganha na hora o `recibo` (linha `tipo: "recibo"`): "Entendi: «assunto». Vou passar para a equipe e te aviso aqui quando ficar pronto." + quando comeca ("Comeca em ate um minuto", "Tem 2 rodando e 1 esperando antes; deve comecar em uns 20 min" — a mediana medida na propria conversa, do "contratado" a resposta final, 5 a 60 min; 20 sem medida — ou "Só que o Claude passou do limite de uso desta janela; comeca quando liberar, por volta das 05:00"). No Telegram o recibo e a resposta do bot, com `/responder <id>` so no fim;
  - pedido que o codigo antigo pos na fila sem trabalhador (nunca contratado, uma mensagem, do app/Telegram) e cujo texto e conversa pela lista de agora vira conversa e e respondido (`_conversas_presas`, na thread da conversa).
- **A pergunta livre: o modelo decide (Grimorio `app-e-bot/conversa-pergunta-livre`, 06/10/2026).** Antes, todo texto fora da lista fixa virava pedido e a resposta a uma pergunta ("por que o video das 17h nao saiu?") so vinha quando um trabalhador a pegava (horas, com o Claude no teto). Agora:
  - texto fora da lista, do app ou do Telegram, nasce conversa `forma: "livre"`, `papo: "pensando"` (situacao `respondido`: o `passo` nao contrata ninguem enquanto isso). O `registrar` so faz isso com `triar` ligado: o `MESA` do modulo (o do app e o do bot) liga; `MesaPedidos()` de teste nao, e o "mensagem" da Mesa (`orquestrador._registrar_pedido`) passa `triar=False`;
  - a thread `conversa` do coordenador chama o `triador` (`triar_pelo_codex`: o mesmo Codex so leitura do cerebro, esforco `low`, `ESQUEMA_TRIAGEM` `{tipo: conversa|trabalho, resposta}`). O prompt diz que toda pergunta e conversa, mesmo sem resposta no CONTEXTO (ele diz com franqueza que dali nao ve), e na duvida entre ordem e conversa e trabalho;
  - `conversa` com resposta limpa: vira a linha `final`, com o lembrete (`_lembrete`: no app `LIVRE_LEMBRETE_APP`, "toque «Passar para a equipe»"; no Telegram `LIVRE_LEMBRETE`, "mande de novo comecando com «pedido:»"); no Telegram vai pelo `avisar` do coordenador (o bot so responde "🧭 Li. Ja te respondo aqui");
  - `trabalho`: `_virar_trabalho` -> o MESMO id vira o pedido de sempre (`recebido`) com o recibo; no Telegram o recibo vai pelo `avisar`, com `/responder <id>`;
  - **SEM modelo (07/10/2026)**: o `_triar` devolve `("sem_modelo", motivo, de_novo)`. Erro, prazo, resposta fora do schema, vazia ou com id/arquivo: `de_novo`, fica "pensando" e tenta UMA vez mais no pulso seguinte (`TRIAGEM_TENTATIVAS = 2`, `triagem_falhas` no pedido). Parado (`CerebroIndisponivel`: proibido, teto do Codex, limite por hora) ou sem triador: na hora. Esgotado, a mensagem fica CONVERSA (`papo_por: "sem_modelo"`) com `LIVRE_SEM_MODELO` ("Nao consegui ler a sua mensagem agora (...). Ela ficou guardada aqui e nao passei nada para a equipe.") + como passar (app: o botao; Telegram: «pedido:»). Antes virava trabalho: uma pergunta contratava um trabalhador so porque o modelo caiu;
  - **Passar para a equipe (07/10/2026)**: `passar_para_equipe(id)` (rota do app `POST /api/coordenador/pedido/<id>/equipe`) faz `_virar_trabalho` no MESMO pedido, so para conversa `forma: "livre"` (pensando ou respondida); ValueError para saudacao/agradecimento e para o que ja e trabalho, KeyError para id desconhecido. Passada enquanto o modelo le, a thread da conversa ve `papo != "pensando"` e nao responde por cima. O `para_o_app` marca `pode_passar` nas linhas `final` (e na reserva) de conversa livre;
  - `pedido: ...` (ou `pedido - ...`) no comeco pula o modelo: vira trabalho na hora, sem o prefixo no texto;
  - coordenador parado: passado `PAPO_PRAZO_S`, a tela mostra `LIVRE_RESERVA` ("Recebi. Ainda estou lendo...").
- **Permissao do estado do servidor:** o coordenador avisa no Telegram (com o id do pedido) e marca `avisado` no pedido de permissao; o gerente da equipe nao repete, e deduplica por pedido de permissao (trabalhador + categoria + alvo + hora), esquecendo o que deixou de estar pendente. O cartao do pedido mostra Permitir/Negar (a rota de Agora › Equipe); o Responder desse pedido da 409 ("texto nao aprova nem nega").
- **Desfecho:** o formato colado (`feito | bloqueado — ... | falhou — ...`, `<o que falta>`) nao declara nada. "feito" sem o diff medido espera o despachante ate 2 min e depois vira respondido (nunca "entregue" sem nada a aplicar).
- **`decisoes adicionar --opcao`:** o ultimo campo so e `acao_servidor` quando comeca pelo NOME de uma acao (gerente, renovacao, paralelo); senao e o resto da descricao, que pode ter `|`.
- **Relancamento recusado** por espera (`RECUSAS_DE_ESPERA`: janela, paralelo cheio, teto do Codex, ja rodando) devolve a retomada; a recusa lida do `fundo.txt` entra no motivo do falhou.
- **4a conferencia (05/10):**
  - **Trava entre processos:** o `_TRAVA` era `threading.RLock` e o app/bot (um processo) e o `passo` do coordenador (outro) gravavam o mesmo `pedidos.json`; o passo regravava o retrato velho por cima do Responder. Agora `_TRAVA` e `_TravaDoArquivo` (o `trava_arquivo` do api_http, `pedidos.lock`, reentrante na thread) em registrar, passo, reabrir, reavaliar e Grimorio; os avisos pedidos com a trava na mao saem depois de solta-la (o Telegram e rede). `_gravar` tenta o `os.replace` de novo no PermissionError.
  - ~~Mensagem curta por contagem de palavras~~ (`CURTO_MAX_PALAVRAS`/`PERGUNTA_CURTA_MAX_PALAVRAS`): removida na 5a conferencia, engolia pedidos de verdade; ver "Conversa solta" acima. O agradecimento solto recebe um "De nada!" com o lembrete do Responder (`curto: true` na rota e no item; desde 06/10 nao mais o retrato com o `CURTO_AVISO`, que ficou so como a frase que a pagina Fluxo cita).
- **5a conferencia (05/10):**
  - **Responder em pedido de trabalhador LIMPO** (ou sem ficha): contrata UM trabalhador novo com a historia (texto do Adrian + ultima resposta + a resposta dele); recusado, `falhou` com o motivo da recusa. Nunca uma linha "recusado:" por pulso.
  - **Cobranca do DESFECHO** leva a resposta original no `continuacao.md` (o Claude abre sessao nova); a resposta final ao Adrian e a ORIGINAL com o desfecho depois, nao o "Ok, conferido". `resposta_cobrada` so sai quando o pedido termina de verdade; `_em_cobranca` so vale se a ultima continuacao foi o proprio `COBRAR_DESFECHO`.
  - **Texto do servidor** (cobranca, avisos) fica em `pedido['do_servidor']` (as ultimas 8), nunca em `pedido['texto']`, e nao conta para `_construir` nem para a escolha da IA.
  - **Trava curta:** o passo reserva o pedido (`contratando` + dono) sob a trava, solta, faz o lento (worktree, `delegar.criar`/`no_fundo`, rede) e grava com a trava de novo; `contratando` sem dono vivo ha `LENTO_PRAZO_S` volta ao que era. Medido: 5 contratos num pulso de 28 s, trava presa no maximo 0,01 s, `registrar` concorrente de outro processo no maximo 0,8 s, 0 erro.
  - **Marca GRIMORIO** so na ultima linha (uma DESFECHO depois e tolerada), como a EXECUTAR (`marca_grimorio`).
  - **Permitir e logo `/responder`** antes do pulso: a decisao vale primeiro (executa ou registra o "negou"), depois a resposta segue ao mesmo trabalhador.
  - **`/responder`** separa o id do texto por qualquer espaco (quebra de linha, tab).
  - **Formato copiado** e so o modelo literal (outro desfecho logo depois de `|`/`/`, ou `<...>`); "/" no meio do motivo e motivo.
  - **Sem a linha e ja aplicado:** a unica cobranca vai ao MESMO trabalhador (`so_desfecho`, com a resposta dele e "NAO mude arquivo nenhum"); Codex sem thread (so teria o `rodar`) vai direto a esperando voce.
  - Lição de teste: `NF_DELEGADOS_PASTA` isola config e fichas, mas NAO o repositorio: `delegar.criar` real faz worktree de verdade (a sonda h2r2 deixou duas, removidas).
- **Estado real em 05/10:** o no `geral/gerente-ligado` tem a decisao vigente "ligar" (04/10, ja lida), mas o config esta com `gerente_ligado=false`; a v2 nao reaplica decisao antiga. O gerente liga quando o Adrian responder o no de novo ou aprovar uma permissao.
- **Uma porta so (07/10):** `MesaPedidos.contratar` recebe contratos da Equipe, propostas confirmadas do cerebro e diagnosticos do apurador. Ela grava cargo, IA e caminhos permitidos no pedido, devolve o pedido aberto existente para texto/alvo/caminhos repetidos e so o `passo` contrata o delegado. O apurador nao gera mais remendo proprio: abre a investigacao com o diagnostico anexado. O vigia tambem espera fora da janela da postagem antes de aplicar ou pedir reinicio.
# Assembleia

No pulso, o supervisor chama o avanço da Assembleia em thread de fundo no
máximo a cada cinco minutos; falhas desse passo são registradas sem parar o
supervisor nem o carteiro.
# Gerente da equipe

O gerente roda no pulso do coordenador, no maximo uma vez por minuto. Nasce
desligado (`gerente_ligado: false`); o Adrian o liga pelo app. Ele tira itens
da fila, contrata uma sessao em worktree e pede conferencia depois da entrega.

## A trava central das postagens (26/10/2026): `random_builds/builds/janela.py`

UMA fonte da verdade para "agora pode fazer coisa pesada?". Antes cada
ferramenta tinha de lembrar da regra (`post-12` a `post+18` min) e havia tres
copias da conta, duas lendo a grade da PLATAFORMA e nao a de cada canal; no dia
26/10 tres agentes rodaram suites e renders dentro das janelas.

- **Quem publica:** a grade REAL de cada canal por data (`builds.grade.
  horas_do_canal(canal, plataforma, dia)`: duelos 8/dia e historias 3+1 desde
  27/10; antes disso historias nos dez horarios) mais a serie do Blue Lock
  (`horas_da_serie`, 20:37). Vale a virada da meia-noite (o 23:37 vai ate 23:55).
- **API:** `em_janela(agora, antes=12, depois=18, olhar_voo=True)` ->
  `(bool, motivo, ate_quando)` (fim exclusivo; janelas que se tocam se emendam;
  `ate_quando=None` quando o motivo e publicacao em voo, que e o `postar.py`/
  `publicar` vivo); `proxima_janela()`; `esperar_fora_da_janela(max_s)` (nao
  dorme a toa se a janela termina depois do prazo); `recusa(ferramenta)` (a
  frase padrao, com o `--forcar`).
- **CLI:** `python -m builds.janela agora | proxima | esperar --max 1800`
  (sai 0 livre, 2 em janela).
- **Ligado em:** `testar.py` (recusa com saida 4; `--forcar`, `--esperar N`;
  margem de 30 min ANTES do post, porque a suite leva 15-25 min);
  `python -m coordenador reiniciar <svc> --forcar` (ignora so a janela;
  publicacao em voo e carteiro entregando continuam barrando);
  `main.py duelo [--forcar]` (render manual, margem 30); `bluelock.comum.
  pode_pesado` (margem 18, mais publicacao em voo); e os antigos
  `supervisor.janela_das_postagens` e `pedidos.na_janela_das_postagens`
  agora so delegam (um relogio, nao tres).
- **Fica de fora, de proposito:** o `postar.py` e as tarefas do Agendador (sao
  a propria postagem); a geracao da madrugada `main.py noite` (01h-06h,
  agendada); SUBIR um servico que caiu (`seguro(janela=False)`); o botao
  "gravar duelo" do app (clique do Adrian, passa `--forcar`). A fabrica da
  serie ja usava `pode_pesado`.
- **Ao criar uma ferramenta pesada nova:** chame `janela.recusa("nome")` no
  comeco e ofereca `--forcar`. Nao copie a conta.
