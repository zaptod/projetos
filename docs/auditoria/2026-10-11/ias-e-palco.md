# Auditoria IAs, esteira e Godot — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Pedido de sprite fica orfao e e repetido se a ficha falhar — gravidade: alta

- Onde: `esteira_sprites/pedir.py:34-47` (`pedir`)

- O defeito: o pedido e anexado ao Correio antes de a ficha registrar a tentativa e o estado. Se a gravacao da ficha falhar ou o processo morrer nessa janela, permanece um pedido entregavel sem ficha; a proxima execucao cria outro pedido para o mesmo item.

- Quando acontece: erro de disco/interrupcao em `ficha.gravar` apos `correio.pedir_imagem` -> o carteiro pode gerar a primeira imagem e a esteira volta a solicitar uma segunda, gastando duas geracoes para a mesma peca.

- Prova: trecho local em `TemporaryDirectory`, com `NF_IAS_PASTA` e a raiz da esteira temporarios, injetou `OSError` em `ficha.gravar`: imprimiu `pendentes= 1 ficha= None`; depois de chamar `pedir('peca')` novamente, imprimiu `apos_repetir= 2`.

- Conserto sugerido: grave primeiro uma ficha em estado transacional/reservado e, apos enfileirar, conclua-a; na retomada, reconcilie pedidos pelo `correio_id` em vez de criar outro.

### 2. Gravacoes concorrentes da ficha da esteira usam o mesmo temporario — gravidade: media

- Onde: `esteira_sprites/ficha.py:35-44` (`gravar`)

- O defeito: todas as gravacoes de uma mesma ficha usam `ficha.tmp`, sem trava. Duas execucoes sobrepostas de `avancar` leem-modificam-gravam sem exclusao mutua; uma substitui o temporario da outra e uma das chamadas pode falhar.

- Quando acontece: dois coordenadores/processos avancam a mesma ficha ao mesmo tempo -> historico, estado ou tentativa de um deles e perdido, e o outro pode receber `FileNotFoundError` no `tmp.replace`.

- Prova: duas threads chamando a funcao real contra raiz temporaria, sincronizadas imediatamente antes de `Path.replace`, imprimiram `FileNotFoundError(2, 'O sistema nao pode encontrar o arquivo especificado')` e a ficha final continha apenas `valor: B`.

- Conserto sugerido: proteja leitura-modificacao-gravacao por trava por item e use temporario unico (`mkstemp`/PID+nonce) antes do replace.

### 3. Estado resumido do Mimetizar tambem perde atualizacao concorrente — gravidade: baixa

- Onde: `mimetizar/espelho/estado.py:38-44` (`gravar`) e `:47-54` (`marcar`)

- O defeito: `_estado.json.tmp` e compartilhado entre todas as gravacoes e `marcar` faz leitura-modificacao-gravacao sem trava. A escrita atomica evita JSON truncado, mas nao evita colisao nem perda de uma etapa.

- Quando acontece: duas invocacoes do Mimetizar marcam etapas no mesmo canal -> uma chamada falha ou o `_estado.json` conserva so a ultima versao, fazendo o status esconder trabalho/falhas recentes.

- Prova: duas threads chamando `estado.gravar` contra pasta temporaria, sincronizadas antes de `os.replace`, imprimiram `erros= ['FileNotFoundError'] estado= B`.

- Conserto sugerido: use trava por canal durante `marcar` e um arquivo temporario exclusivo por gravacao.

## Não confirmados

- Godot: revisei os caminhos de carga, validacao de timeline, plano de quadros, folhas e som; nao confirmei defeito de execucao. A execucao de teste de folha foi iniciada, mas a captura final do processo Godot nao ficou disponivel nesta sessao, portanto nao a uso como prova.
