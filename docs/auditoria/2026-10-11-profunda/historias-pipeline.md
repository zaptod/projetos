# Auditoria profunda — Pipeline das histórias — 11/10/2026

## Examinado

- `historias/contos/pipeline/__init__.py` — 0 funções/classes lidas; marcador de pacote vazio.
- `historias/contos/pipeline/agenda.py` — 94 funções/classes lidas; planeja e executa rodadas, estoque, travas e faixas paralelas.
- `historias/contos/pipeline/conferir.py` — 4 funções/classes lidas; varre cache de voz e partes já renderizadas.
- `historias/contos/pipeline/conserto_de_cena.py` — 13 funções/classes lidas; classifica vetos e reescreve/grava correções de cenas.
- `historias/contos/pipeline/controller.py` — 26 funções/classes lidas; executa roteiro, imagens, render e estado da história.
- `historias/contos/pipeline/reparo.py` — 39 funções/classes lidas; registra e aplica reparos automáticos.
- `historias/contos/pipeline/tarefas.py` — 9 funções/classes lidas; cria, remove e lista tarefas do Agendador.
- `historias/main.py` — 20 funções/classes lidas; interface CLI, códigos de saída e redirecionamento da tarefa.

## Confirmados (do mais grave ao menos)

### 1. Falha transitória do serviço diário é marcada como concluída — gravidade: média

- Onde: `historias/contos/pipeline/agenda.py:1587` (`_servico_do_dia`), especialmente linha 1627.
- O defeito: cada uma das três etapas pode falhar, mas `_marcar_servico(agora)` roda mesmo assim. `servico_pendente()` então devolve falso e a agenda não tenta de novo naquele dia.
- Quando acontece: rede indisponível na métrica/conferência ou erro de disco na consolidação → a única rodada diária perde a etapa e grava a marca de sucesso.
- Prova: `python -c "... agenda._servico_do_dia(...); print('marca=', agenda._marca_do_servico().is_file(), 'pendente=', agenda.servico_pendente(agora))"` (em diretório temporário, com as três dependências lançando erro) saiu `marca= True pendente= False`.
- Conserto sugerido: marcar o serviço somente se todas as etapas obrigatórias concluírem, ou persistir quais falharam para repeti-las.

### 2. Tarefa automática pode morrer sem diário se o arquivo de saída estiver bloqueado — gravidade: média

- Onde: `historias/main.py:688` (`_redirecionar_saida`), linha 708.
- O defeito: a abertura de `--saida` não trata `OSError`/`PermissionError`. Ela ocorre antes de `main()` e antes de redirecionar `stderr`; no `auto.cmd`, o console vai para `NUL`, portanto a tarefa termina sem o log que deveria explicar a falha.
- Quando acontece: outro programa abre `outputs/_logs/auto_saida.txt` sem compartilhamento de escrita no Windows → o disparo agendado encerra antes da agenda e não deixa registro utilizável.
- Prova: `python -c "from unittest.mock import patch; import main; ... main._redirecionar_saida([...,'--saida','C:/bloqueado.txt'])"` com `open` lançando `PermissionError('arquivo bloqueado')` saiu `PermissionError: arquivo bloqueado`.
- Conserto sugerido: capturar o erro no bloco `__main__`, registrar em alternativa segura e sair com código não zero sem iniciar a rodada.

### 3. `main.py tudo` informa sucesso mesmo com imagens falhadas e vídeo ausente — gravidade: média

- Onde: `historias/main.py:162` (`cmd_tudo`).
- O defeito: o comando imprime os erros devolvidos por `pipeline.tudo()`, mas retorna incondicionalmente `0`.
- Quando acontece: o gerador falha e `tudo` devolve `imagens.erros` e imagens pendentes → automação/chamador recebe sucesso apesar de a história continuar sem poder renderizar.
- Prova: `python -c "import argparse, main; ... print('codigo=', main.cmd_tudo(...))"` com resultado realista `{'imagens': {'erros': ['gerador indisponivel'], 'faltam': 1}}` imprimiu `! gerador indisponivel` e `codigo= 0`.
- Conserto sugerido: retornar código não zero quando houver erros de imagens, imagens faltantes ou erro de vídeo.

### 4. Erro interno da rodada escapa em vez de virar resultado estruturado — gravidade: baixa

- Onde: `historias/contos/pipeline/agenda.py:1364` (`rodar`), linhas 1451–1459.
- O defeito: depois de construir `resultado` e avisar, o `except` relança a exceção. Isso contradiz o contrato da própria rodada (“devolve o que aconteceu”) e pula o tratamento uniforme de `cmd_auto`/`_fechar_passo`.
- Quando acontece: uma exceção inesperada abaixo de `_emendar` (por exemplo, E/S interrompida) → `main.py auto` recebe traceback em vez de um dicionário com `erros`, e não registra a duração/fechamento da rodada pelo caminho normal.
- Prova: `python -c "... agenda._emendar=lambda *a: (_ for _ in ()).throw(OSError('disco indisponivel')); ... agenda.rodar(...)"` (saída e trava isoladas em temporário) saiu `OSError: disco indisponivel`.
- Conserto sugerido: retornar `resultado` com `erros` após registrar/avisar, deixando `cmd_auto` definir o código de saída.

## Não confirmados

- `conserto_de_cena.gravar_roteiro` e `reparo._gravar` escrevem JSON diretamente, sem troca atômica; uma queda no meio poderia truncar o estado. Não forcei interrupção de processo/escrita no sistema de arquivos, portanto não há prova reproduzível nesta auditoria.
- `agenda._avisar_uma_vez_por_dia` faz leitura e escrita da marca sem trava. Duas rodadas que chegassem antes da trava principal podem duplicar aviso, mas não reproduzi uma interlevação real sem alterar a primitiva de trava.
