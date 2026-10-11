# Auditoria Coordenador e delegacao — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Falha no `git apply` vira entrega aplicada — gravidade: alta

- Onde: `remoto/delegar.py:1931` (`aplicar`)

- O defeito: depois de `git apply --check` passar, o retorno do `git apply` real e ignorado. Mesmo com erro na aplicacao, a ficha recebe `aplicado` e a funcao devolve sucesso.

- Quando acontece: a arvore principal muda entre o `--check` e o `apply` (ou o segundo comando falha por outro motivo) -> o patch nao entra, mas o vigia entende que a entrega foi aplicada e pode seguir para commit/limpeza.

- Prova: em Python local, dublei o primeiro `git apply` com retorno 0 e o segundo com retorno 1. A chamada a `delegar.aplicar('auditoria', processos=[])` imprimiu `retornou_aplicado=True` e `estado_marcado_aplicado=True`.

- Conserto sugerido: confira o `returncode` do segundo `git apply` e levante `Recusa` antes de gravar `aplicado` se ele nao for zero.

### 2. Timeout dos testes deixa processos-filhos rodando — gravidade: media

- Onde: `remoto/delegar.py:1842` (`_testar_travado`)

- O defeito: usa `subprocess.run(..., shell=True, timeout=...)`; no Windows o timeout encerra o shell, mas nao a arvore de processos iniciada por ele.

- Quando acontece: um teste cria um filho (servidor, navegador ou worker) e passa do prazo -> a ficha registra timeout, enquanto o filho continua usando a worktree/porta e pode alterar estado depois.

- Prova: executei o mesmo padrao com um shell que inicia Python, espera 1 s e cria uma sentinela, com timeout de 0,05 s. Saiu `timeout_do_pai=sim` e, apos 1,5 s, `filho_continuou=True`.

- Conserto sugerido: rode com `Popen` e, no timeout, mate a arvore no Windows com `taskkill /T /F` antes de recolher a saida.

### 3. JSON ilegivel dos pedidos e sobrescrito como se estivesse vazio — gravidade: media

- Onde: `coordenador/pedidos.py:361` (`_ler`)

- O defeito: qualquer `OSError` ou JSON invalido vira `{}`; a proxima operacao de escrita persiste esse estado novo, sem preservar nem sinalizar os pedidos anteriores.

- Quando acontece: uma gravacao interrompida, erro transitório de leitura ou arquivo corrompido seguido de uma nova mensagem -> `pedidos.json` e substituido e todos os pedidos/conversas que ainda estavam no arquivo sao perdidos.

- Prova: em `NF_COORDENADOR_PASTA=.rt/auditoria-pedidos`, gravei `pedidos.json` com `{conteudo corrompido` e chamei `MesaPedidos().registrar(..., triar=False)`. O arquivo resultante foi aceito e o programa imprimiu `pedidos_gravados=1` e `texto= preservar historico`.

- Conserto sugerido: diferencie arquivo ausente de arquivo ilegivel; no segundo caso, recuse a escrita e preserve/arquive o original para recuperacao.

## Nao confirmados

- Nenhum adicional: os demais pontos suspeitos lidos nesta rodada nao tiveram reproducao concreta.
