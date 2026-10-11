# Pente fino de bugs — resumo (11/10/2026)

8 auditorias pelo Codex, uma por parte (relatórios nesta pasta), cada defeito com prova
rodada. O orquestrador conferiu no código os de maior gravidade antes desta lista.

Legenda: ✔ conferido pelo orquestrador no código · ▸ prova do Codex (rodou e mostrou a falha)
· ✘ alarme falso.

## Alta — podem repostar vídeo, apagar dados ou mentir que está tudo bem

| # | Defeito | Onde | Conf. |
|---|---|---|---|
| 1 | Publicação some do ledger se a reconciliação segura a trava > 120 s: o escritor grava SEM trava e o `os.replace` da reconciliação apaga a linha → o vídeo volta à fila e é repostado | `random_builds/builds/publicar/metricas.py:175` | ✔ |
| 2 | A mesma parte de história sobe duas vezes se duas publicações se cruzam (o `ja_publicado` e o upload não ficam sob trava da parte) | `historias/contos/publicar/serie.py:151` | ▸ |
| 3 | `pedidos.json` da Mesa apagado inteiro: leitura que falha UMA vez (arquivo trancado no Windows, JSON partido) vira `{}` e a próxima gravação sobrescreve todos os pedidos e a conversa | `coordenador/pedidos.py:361` | ✔ |
| 4 | Veredito do panorama diz "tudo em dia" quando a vistoria e as metas NEM FORAM lidas (ignora o campo `erro`) | `visao/panorama/auditoria.py:202` | ▸ |
| 5 | O despachante do Codex morre com `[Errno 36] Resource deadlock avoided` na trava de arquivo quando vários rodam juntos (visto hoje às 13:31 na auditoria do motor e em 07/10 no integrador) | `remoto/delegar.py` (`_trava`) | ✔ (log) |

## Média

| # | Defeito | Onde | Conf. |
|---|---|---|---|
| 6 | Lutas somem do histórico do ranking quando duas terminam juntas (cada `Ledger()` grava a sua cópia inteira) | `random_builds/builds/arena/ledger.py:53` | ✔ |
| 7 | Duas gerações simultâneas pegam a mesma pasta `generation_N` | `random_builds/builds/pipeline/controller.py:43` | ▸ |
| 8 | Relatório do Telegram marcado como enviado antes de enviar: Telegram fora = relatório do dia perdido | `remoto/bot.py:205` | ▸ |
| 9 | Comando do Telegram com erro passageiro é descartado para sempre (offset avança antes) | `remoto/bot.py:294` | ▸ |
| 10 | Erro ao retomar roteiro não chega ao `atividade.jsonl` (passa texto onde se espera dicionário; a exceção é engolida) → bot e apuração não sabem | `historias/contos/pipeline/agenda.py:2198` | ▸ |
| 11 | Falha ao consultar o Agendador vira "34 tarefas, nada faltando" no panorama e "💤 tudo parado" na Vila | `visao/panorama/recursos.py:211`, `painel/flutuante/dados.py:830` | ▸ |
| 12 | Timeout dos testes do despachante mata o shell mas deixa os processos-filhos rodando | `remoto/delegar.py:1842` | ▸ |

## Baixa / escondido (não afeta o que sai hoje)

- Gravar a mais de 60 fps acelera a luta — os vídeos usam 30/24 fps (`fight_recorder.py:620`).
- `--max-duracao 0` dá "sucesso" com luta de 0 s; timeline com temporário fixo (`timeline_arquivo.py:140`).
- `--generation-only` ainda agenda arte por IA; `--count 0` gera uma build (`random_builds/main.py:758`).
- Contador do PicassoIA sem trava (PicassoIA está fora da roda) (`historias/contos/imagens/cota.py:98`).
- Esteira de sprites e Mimetizar com corrida de gravação (a esteira está DESLIGADA).

## Alarme falso

- ✘ "Falha no `git apply` vira entrega aplicada" (`remoto/delegar.py:1931`): `_git(...)` tem
  `verificar=True` por padrão e LEVANTA `Recusa` quando o comando falha; a prova do Codex
  dublou o próprio `_git` e pulou essa verificação.
