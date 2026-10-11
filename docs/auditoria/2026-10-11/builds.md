# Auditoria Geração dos builds — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Escritas concorrentes apagam lutas do ledger — gravidade: alta

- Onde: `random_builds/builds/arena/ledger.py:53` (`Ledger.registrar`) e `:80` (`Ledger.salvar`)
- O defeito: cada instância carrega o JSON uma vez e grava a sua cópia inteira sem uma trava entre ler, modificar e substituir o arquivo. A substituição atômica evita JSON partido, mas não evita perder a atualização do outro processo.
- Quando acontece: dois duelos/estreias terminam próximos, cada um cria seu `Ledger` antes de registrar uma luta diferente → o último `os.replace` deixa apenas uma das duas lutas, alterando cartel, ranking e escolha de adversário.
- Prova: em diretório temporário, duas threads com instâncias separadas registraram seeds 1 e 2 atrás de uma barreira; a releitura imprimiu `ledger= 1 [2]`.
- Conserto sugerido: proteger leitura-modificação-gravação do ledger com uma trava interprocesso e reler o arquivo dentro da seção crítica antes de gravar.

### 2. Gerações simultâneas recebem o mesmo diretório — gravidade: alta

- Onde: `random_builds/builds/pipeline/controller.py:43` (`_next_id`)
- O defeito: a função enumera os diretórios e calcula o próximo número sem reserva nem trava. Dois processos podem observar a mesma lista antes de qualquer um criar a pasta.
- Quando acontece: duas execuções de `generate-video` (ou de outro formato que usa `_next_id`) começam juntas → ambas escolhem, por exemplo, `generation_00002` e gravam no mesmo `outputs/`, misturando ou sobrescrevendo JSONs e mídia.
- Prova: com `generation_00001` em diretório temporário, duas threads sincronizadas chamaram `_next_id`; a saída foi `ids= ['generation_00002', 'generation_00002']`.
- Conserto sugerido: reservar o ID criando o diretório de forma exclusiva sob trava interprocesso e somente então iniciar a geração.

### 3. `--generation-only` ainda agenda geração de identidade — gravidade: média

- Onde: `random_builds/main.py:764-766` e `random_builds/builds/pipeline/controller.py:133` (`PipelineController.generate`)
- O defeito: o modo anunciado como “gera apenas os dados” passa `identity=True` por padrão e chama `_enfileirar_identidade`, que cria jobs para o worker gerar imagens.
- Quando acontece: `python main.py generate-video --generation-only` sem `--no-identity` → além dos JSONs de balanceamento, entram pedidos de identidade na fila e o worker pode gastar cota/abrir navegador para builds que não terão vídeo.
- Prova: uma execução isolada com sessão e métodos de saída dublados imprimiu `[gen] generation_00001 seed=7 final=1 (x)` e `identity= ['generation_00001']`.
- Conserto sugerido: forçar `identity=False` quando `generation_only=True` (ou tornar isso explícito por uma opção separada).

### 4. `--count 0` gera uma build apesar de pedir zero — gravidade: baixa

- Onde: `random_builds/main.py:758-766` (`main`)
- O defeito: a ramificação para lote só aceita `count > 1`; zero e números negativos caem em `controller.generate`, gerando uma build.
- Quando acontece: `python main.py generate-video --generation-only --count 0` → em vez de não gerar nada ou rejeitar a entrada, executa uma geração (e, sem `--no-identity`, também agenda identidade).
- Prova: com `PipelineController` dublado, esse comando chamou `generate` uma vez com `generation_only: True` e `identity: True`.
- Conserto sugerido: validar `--count` como inteiro positivo e tratar zero como lote vazio, sem chamar `generate`.

## Não confirmados

- Nenhuma suspeita adicional incluída: os demais pontos revisados não tiveram reprodução concreta sem acionar serviços, navegador ou estado real.
