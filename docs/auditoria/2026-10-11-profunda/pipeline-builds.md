# Auditoria profunda — Pipeline dos builds — 11/10/2026

## Examinado

- `random_builds/builds/pipeline/controller.py` — 33 funções e 1 classe lidas; cria, re-renderiza e entrega builds, lutas, duelos e torneios.
- `random_builds/builds/pipeline/fluxo.py` — 13 funções lidas; consolida disco e fila de identidade no estado exibido pelo painel e CLI.
- `random_builds/builds/pipeline/noite.py` — 64 funções e 1 classe lidas; planeja e executa a rodada automática, respeitando estoque, grade e worker.
- `random_builds/builds/pipeline/sonorizar.py` — 17 funções lidas; anota som real nas lutas, re-renderiza e lista o estoque sonoro.
- `random_builds/builds/pipeline/tarefas_noite.py` — 11 funções e 1 classe lidas; cria, remove e consulta as tarefas do Agendador da rodada.
- `random_builds/main.py` — 9 funções lidas; define a CLI e encaminha os comandos da pipeline.
- `random_builds/builds/tarefas_windows.py` — 8 funções lidas; endurece tarefas do Windows e monta a ação oculta.
- `random_builds/builds/travas.py` — 10 funções lidas; implementa travas interprocesso por recurso/perfil.
- `random_builds/builds/atividade.py` — 17 funções e 1 classe lidas; grava, poda e interpreta o diário operacional das fábricas.
- `docs/sessoes/builds.md` — lido integralmente; contratos de lote, janela da grade, tarefas, diário, estoque e som confrontados com o código.

## Confirmados (do mais grave ao menos)

### 1. Duas sonorizações do mesmo alvo disputam o mesmo temporário — gravidade: média

- Onde: `random_builds/builds/pipeline/sonorizar.py:90` (`_gravar`), chamada por `sonorizar`; não há trava no caminho `main.py som-da-luta`.
- O defeito: toda gravação usa o temporário fixo `<arquivo>.tmp`. Duas execuções simultâneas para a mesma luta escrevem e renomeiam esse mesmo arquivo; uma pode substituir dados da outra e a outra recebe `FileNotFoundError` ao tentar renomear um temporário que já foi consumido.
- Quando acontece: dois operadores/processos iniciam `som-da-luta duelo_00012` ao mesmo tempo (ou uma tentativa coincide com outro re-render que usa esse caminho) → uma chamada falha depois de já ter re-simulado/anotado a luta; o alvo pode ficar com JSON/plano de uma chamada e vídeo da outra ou sem o re-render esperado.
- Prova: em diretório temporário fora do repositório, duas threads chamaram a função real `_gravar` simultaneamente sobre `fight.json`, cada uma com JSON de 20 MB. Saída: `['A:ok', 'B:FileNotFoundError']` e `tmp_existe= False`.
- Conserto sugerido: proteger a sonorização/re-render por uma trava interprocesso por diretório de alvo e usar temporário exclusivo (`NamedTemporaryFile`/UUID) para cada escrita.

### 2. Diário marca uma fábrica viva como ociosa após 600 eventos posteriores — gravidade: baixa

- Onde: `random_builds/builds/atividade.py:257` (`estado_das_fabricas`) e `:314` (`estado_por_canal`).
- O defeito: ambas as visões consultam somente `recentes(600)`. Se o último `inicio` de uma fábrica ficar antes de 600 logs posteriores, ele não é examinado, embora o PID ainda esteja vivo; a fábrica cai no estado padrão `ocioso`.
- Quando acontece: uma luta/render longo começa e as outras fábricas emitem 600 eventos `log` antes de terminar → a Vila/painel informa que a Arena está ociosa em vez de trabalhando, ocultando a atividade que deveria monitorar.
- Prova: em arquivo temporário, a função real `registrar` gravou um `inicio` da Arena (PID do processo atual) e 600 logs do Estúdio. `_vivo(pid)` imprimiu `True`, mas `estado_das_fabricas()['arena']['status']` imprimiu `ocioso`.
- Conserto sugerido: percorrer o diário até encontrar o último evento não-`log` de cada fábrica/canal, em vez de limitar a busca a 600 linhas.

### 3. Configuração estruturalmente corrompida derruba a rodada antes do tratamento de erro — gravidade: média

- Onde: `random_builds/builds/pipeline/noite.py:376` (`modo_da_hora`) e `:932` (`_rodada`).
- O defeito: `carregar` aceita qualquer valor do JSON sobre os padrões; `modo_da_hora` pressupõe que `janela_pesada` é dicionário. `_rodada` chama essa função antes do `try` que cobre `planejar`, contrariando o contrato de a rodada não levantar por conta da tarefa.
- Quando acontece: `config/geracao.json` fica parcialmente editado, por exemplo `"janela_pesada": "corrompida"` → o próximo disparo chama `na_janela`, recebe `TypeError: string indices must be integers, not 'str'` e termina sem executar a política segura de configuração ilegível.
- Prova: em diretório temporário, foi criado um `geracao.json` com `{"dias_de_lote": [], "janela_pesada": "corrompida"}` e carregado pela função real. A execução imprimiu `str` e depois `TypeError string indices must be integers, not 'str'` ao chamar `modo_da_hora`.
- Conserto sugerido: validar os tipos de cada bloco ao carregar (ou fazer `modo_da_hora`/`na_janela` recuar para `PADRAO`), antes de qualquer decisão da rodada.

## Não confirmados

- `random_builds/builds/atividade.py:148` (`_podar`) regrava o diário inteiro sem trava e pode disputar uma gravação concorrente; a inspeção apontou a janela de corrida, mas não houve reprodução confiável de perda de evento com as funções reais.
- `random_builds/builds/pipeline/controller.py:90` e os caminhos de duelo/luta/torneio reservam a pasta de saída antes de algumas validações; uma falha pode deixar pasta vazia, mas o catálogo não a trata como vídeo e o ID não é reutilizado de propósito. Não confirmou efeito operacional incorreto.
