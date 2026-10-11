# Auditoria Criação das histórias — 11/10/2026

## Confirmados (do mais grave ao menos)

### 1. Falha ao retomar roteiro não chega ao ledger — gravidade: média

- Onde: `historias/contos/pipeline/agenda.py:2198` (`_retomar_texto`), `historias/contos/pipeline/agenda.py:630` (`_registrar_erro`)

- O defeito: ao falhar a escrita das partes restantes, `_retomar_texto` passa uma string para `_registrar_erro`, que exige um dicionário e chama `.get()`. A exceção é engolida pelo próprio registrador, portanto não há registro no ledger de atividade.

- Quando acontece: uma história truncada (por exemplo `historia_00001`) falha ao retomar por limite do LLM ou erro de rede → a rodada escreve no diário, mas o bot e a apuração automática, que leem `atividade.jsonl`, não recebem o erro.

- Prova: `python -c "from contos.pipeline import agenda; import builds.atividade as atividade; chamadas=[]; atividade.registrar=lambda *args, **kwargs: chamadas.append(args); agenda._registrar_erro('retomada de historia_00001: limite'); print('ledger=', chamadas)"` (em `historias/`) imprimiu `ledger= []`.

- Conserto sugerido: passar um dicionário de resultado para `_registrar_erro` (com `erro`, `motivo` e `historia_id`) ou fazê-la aceitar explicitamente texto.

### 2. Contador diário do caminho PicassoIA perde incrementos concorrentes — gravidade: baixa

- Onde: `historias/contos/imagens/cota.py:98` (`contar`)

- O defeito: o contador faz leitura-modificação-gravação sem trava e usa um único temporário `_picasso_por_dia.tmp`. Dois workers que leem o mesmo valor antes da gravação escrevem o mesmo próximo valor, subcontando envios e permitindo ultrapassar o teto diário.

- Quando acontece: duas execuções do caminho legado do PicassoIA enviam uma imagem simultaneamente, ambas vendo zero → as duas enviam, mas o JSON termina em um; os próximos envios continuam apesar de a conta compartilhada já ter usado mais que o teto.

- Prova: `python -c "import json,tempfile; from datetime import datetime; from pathlib import Path; from contos.imagens import cota; tmp=tempfile.TemporaryDirectory(); cota.CONTADOR=Path(tmp.name)/'contador.json'; inicial=cota._ler(); cota._ler=lambda: dict(inicial); a=cota.contar(datetime(2026,10,11,10)); b=cota.contar(datetime(2026,10,11,10)); print('retornos=',[a,b],'arquivo=',json.loads(cota.CONTADOR.read_text())); tmp.cleanup()"` (em `historias/`) imprimiu `retornos= [1, 1] arquivo= {'2026-10-11': 1}`; a simulação fixa as duas leituras antes das duas gravações, a intercalação que falta travar.

- Conserto sugerido: proteger o ciclo inteiro com a trava compartilhada e usar temporário exclusivo por processo antes de `os.replace`.

## Não confirmados

- Não encontrei outro defeito reproduzível nos fluxos atuais de roteiro, imagens pelo correio, renderização, reparo e agenda; as suspeitas restantes dependiam de navegador, rede ou estado real, que não foram acionados.
