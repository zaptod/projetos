# Auditoria App do celular e bot — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Relatório periódico é dado como enviado mesmo quando o Telegram falha — gravidade: média

- Onde: `remoto/bot.py:205` (`Bot._relatorios`)

- O defeito: o estado `relatorios.json` é marcado antes do envio e o retorno de `tg.mensagem` é ignorado. Assim, uma indisponibilidade do Telegram (inclusive para todos os aparelhos autorizados) faz o relatório ser perdido até o dia seguinte.

- Quando acontece: relatório `metas` vencido, um autorizado e `mensagem()` devolvendo `{"ok": false}` → grava `{"metas": "2026-10-11"}` e a próxima volta conclui que nada é devido.

- Prova: executei um cenário isolado em diretório temporário, com `config.ARQUIVO` temporário, horário `metas=00:00` e um Telegram falso que retorna `{"ok": false}`. Saída: `marcado= {'metas': '2026-10-11'}` e `devidos_depois= []`.

- Conserto sugerido: só chamar `relatorios.marcar` após confirmar ao menos uma entrega, ou enfileirar a tentativa que falhou.

### 2. Falha transitória descarta para sempre um comando recebido no Telegram — gravidade: média

- Onde: `remoto/bot.py:294` (`Bot.uma_volta`)

- O defeito: o offset do Telegram avança antes de tratar a mensagem; a exceção é apenas registrada. A atualização não volta na próxima consulta, mesmo se a falha ocorreu antes de o comando ser executado.

- Quando acontece: chega `/ajuda` e `comandos.executar` levanta `OSError` temporário → o bot escreve o erro, muda `desde` para `1` e não responde nem executa o comando quando a dependência volta.

- Prova: executei um Telegram falso que entrega uma única atualização e fiz `comandos.executar` levantar `OSError`. Saída: `[remoto] erro tratando mensagem: falha temporaria`, seguida de `offset= 1 novidades_na_2a_volta= 0`.

- Conserto sugerido: não avançar o offset em falha anterior à execução, ou registrar uma resposta de erro recuperável ao remetente antes de confirmá-la.

## Não confirmados

- Nenhum outro caso foi incluído sem reprodução local.
