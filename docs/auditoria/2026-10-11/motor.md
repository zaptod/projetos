# Auditoria Motor da luta — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. FPS acima de 60 acelera a luta gravada — gravidade: alta

- Onde: `neural_fights/recording/fight_recorder.py:620-662` (`gravar_luta`)

- O defeito: o motor avanca sempre um passo de 1/60 s, mas para `fps_saida > 60` captura todos os passos e os entrega ao ffmpeg com o FPS maior solicitado. O relogio do video passa a correr mais rapido que o da luta.

- Quando acontece: `--fps 120` grava 60 quadros de jogo por segundo, mas os declara como 120; uma luta de 0,10 s vira clipe de 0,05 s, com acao e audio acelerados e metadados de duracao divergentes.

- Prova: executei um simulador falso sem efeitos colaterais, com `fps_saida=120` e `max_duracao=.05`; a saida foi `{'120fps': (0.1, 0.05)}` para `(duracao_jogo, duracao_video)`. O mesmo caminho usa `a_cada = max(1, round(FPS / fps_saida))`, portanto nunca duplica quadros para FPS acima do tick do motor.

- Conserto sugerido: rejeitar FPS maior que `FPS` ou repetir/interpolar quadros e manter um relogio de captura independente.

### 2. Duração máxima zero registra gravação inexistente como sucesso — gravidade: média

- Onde: `neural_fights/recording/fight_recorder.py:620-623,685-694` (`gravar_luta`)

- O defeito: `max_duracao` não é validada. Com zero ou valor negativo, o laço não executa nenhum passo e a função ainda monta resultado com `sucesso: True` e motivo `time_limit`.

- Quando acontece: `python -m neural_fights.recording.fight_recorder ... --max-duracao 0` pode concluir a pipeline com um resultado de luta de 0,00 s (e, quando há saída, um vídeo vazio), em vez de falhar a entrada inválida.

- Prova: no mesmo harness isolado, `gravar_luta(..., max_duracao=0, anotar_som=False)` devolveu `{'zero': (True, 0.0, 0.0)}` para `(sucesso, duracao_jogo, duracao_video)`.

- Conserto sugerido: validar no início que `max_duracao` é finita e maior que zero, inclusive na CLI.

### 3. Duas gravações da mesma timeline disputam o mesmo temporário — gravidade: média

- Onde: `neural_fights/recording/timeline_arquivo.py:140-147` (`salvar`)

- O defeito: todo escritor usa literalmente `<destino>.tmp`, sem lock nem nome exclusivo. Dois processos no mesmo destino sobrescrevem ou removem o temporário um do outro antes do `replace`.

- Quando acontece: duas renderizações solicitando a mesma `--timeline` em paralelo deixam uma falhar com `FileNotFoundError`; em `gravar_luta`, essa falha é engolida por `_salvar_timeline` e o resultado geral permanece `sucesso: True`, apesar de a timeline pedida não ter sido gerada para uma das lutas.

- Prova: em diretório temporário, sincronizei duas threads logo após `Path.write_bytes` e chamei `salvar` para o mesmo arquivo. A execução imprimiu `{'erros': ['FileNotFoundError'], 'arquivo_final': '{"gravador":2}'}`.

- Conserto sugerido: usar `NamedTemporaryFile(delete=False, dir=caminho.parent)` com nome exclusivo e, se o mesmo destino for permitido, uma trava por caminho.

## Não confirmados

- Nenhum adicional: as suspeitas examinadas fora destes três casos não tiveram reprodução concreta nesta auditoria.
