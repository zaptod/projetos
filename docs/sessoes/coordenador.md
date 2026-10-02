# Coordenador residente

O coordenador e o processo local que mantem app, bot, carteiro e Vila flutuante vivos sem depender de uma janela do VS Code. Ele adota processos ja existentes pela linha de comando, registra o estado em `%LOCALAPPDATA%\neural-fights\coordenador\estado.json` e so reinicia codigo velho fora das janelas de postagem e de uma publicacao real.

Para instalar a tarefa (uma vez, em um prompt do usuario):

```powershell
cd E:\projetos
python -m coordenador instalar-tarefa
python -m coordenador desligar-tarefas-antigas
```

Ela inicia no logon como `NeuralFights_coordenador`. Para conferir ou controlar manualmente:

```powershell
python -m coordenador status
python -m coordenador reiniciar app
```

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

**Desligar so o aplicar:** `{"vigia_aplica": false}` no `config.json` da pasta do coordenador. A entrega validada e testada fica em `esperando` ("pronta para aplicar") e o orquestrador aplica; o resto do vigia segue.

Memoria em `trabalho_memoria.json` (vistos, aplicados, corrigidos, olho, esperando, avisos de parada, nos por dia): reiniciar o coordenador nao repete aviso.

**Para ligar:** o `python -m coordenador rodar` ja monta os dois (`__main__.montar`). O coordenador que esta rodando so pega o codigo novo quando reiniciar (a tarefa `NeuralFights_coordenador`); nada foi reiniciado nesta entrega.
# Assembleia

No pulso, o supervisor chama o avanço da Assembleia em thread de fundo no
máximo a cada cinco minutos; falhas desse passo são registradas sem parar o
supervisor nem o carteiro.
