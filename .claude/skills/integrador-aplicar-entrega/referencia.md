# Referência: aplicar entrega do Codex

Conferido no código em 20/10/2026 (`remoto/delegar.py`, `coordenador/vigia_trabalho.py`,
`coordenador/pedidos.py`, `random_builds/builds/grade.py`, `testar.py`).

## Onde mora cada coisa (`python -m remoto.delegar onde`)
| O quê | Caminho |
|---|---|
| Fichas dos delegados | `%LOCALAPPDATA%\neural-fights\delegados\<id>\` (`estado.json`, `diff.patch`, `diff.json`, `testes.log`, `resposta.md`, `tarefa.md`, `log.txt`, `eventos.jsonl`; o integrador do vigia tem também `integrar.md` na ficha ORIGINAL) |
| Worktrees | `E:\projetos-wt\codex-<id>` (ramo `delegar/codex-<id>`); o que o sandbox não deixa apagar vai para `E:\projetos-wt\_lixo_codex` |
| Memória do vigia | `%LOCALAPPDATA%\neural-fights\coordenador\trabalho_memoria.json` (`olho`, `esperando`, `integrando`, `sem_mudanca`, `retestes`, `aplicados`) |
| Liga/desliga o aplicar do vigia | `%LOCALAPPDATA%\neural-fights\coordenador\config.json` → `{"vigia_aplica": true}` |
| Config do despachante | `%LOCALAPPDATA%\neural-fights\delegados\config.json` (`janela_sem_aplicar` ausente = sem janela de relógio no `aplicar`) |

Campos úteis do `estado.json`: `base` (commit de onde o diff sai), `branch`, `repo` (E:\projetos ou
outro repositório), `testes_cmd`, `permitidos`, `diff`, `testes` (`ok`, `codigo`, `diff_sha`),
`aplicado` (`arquivos`), `commit`, `aplicado_por`, `limpo`.

## Subcomandos do `python -m remoto.delegar` (conferidos com `--help`)
| Comando | Faz | Saída |
|---|---|---|
| `ver --id X` | imprime a ficha (diff, testes, aplicado) | 0 |
| `listar` | todas as fichas, a mais nova primeiro | 0 |
| `onde` | pastas de estado, worktrees, repo e codex home | 0 |
| `diff --id X` | `coletar`: `git add -A` na worktree sem NOSSOS/RUIDO, tira PROIBIDOS e o que só mudou CRLF, grava `diff.patch`/`diff.json` | 0 passa, 4 recusado |
| `testar --id X [--cmd C]` | `coletar` e depois os testes NA WORKTREE, com TEMP em `E:\tmp_pytest\delegados\X\r...`, `-p no:cacheprovider` e `faulthandler_timeout=180`; escreve o `testes.log` | 0 ok, 5 falhou |
| `aplicar --id X [--sem-testes]` | recusa se houver publicação em voo, se o diff mudou desde os testes ou se os testes falharam (a não ser com `--sem-testes`); tenta `apply --check`, depois `apply -3` e o resolvedor de casca; grava `aplicado`. NÃO commita | 0, ou 3 com "recusado: ..." |
| `limpar --id X` / `limpar --orfas` | `worktree remove --force` + `branch -D`, grava `limpo`; `--orfas` só apaga `codex-*` que nenhum git conhece | 0 |
| `parar --id X` | para o trabalhador | 0 |
| `corrigir --id X --texto ARQ [--fundo]` | manda o Codex corrigir (o texto vai num ARQUIVO) | — |

Recusas comuns do `aplicar`:
- "há mudança não commitada nos mesmos arquivos": a árvore está suja.
- "conflito de merge em: ...": siga o caminho B.
- "git apply -3 não mudou nada": a entrega já estava lá.
- "a worktree sumiu": use o `diff.patch` da ficha com `git apply -3`.

Não existe subcomando para gravar o commit; use `delegar.registrar_commit(id, hash, aplicado_por=...)`.

## O que o vigia já faz sozinho (não refaça)
Ele age a cada 60 s, em toda ficha `terminou` sem `aplicado` e sem `limpo` que terminou depois que ele nasceu:
1. coleta e valida o diff (só recusa diff vazio; o resto vira aviso);
2. testa: o `testes_cmd`, ou então `python -m pytest <pastas de topo> -q`; `docs/` não tem teste;
   com `remoto/app/**` ou `api_http.py` o comando ganha `NF_TESTE_NAVEGADOR=1`;
3. falha de ambiente (`WinError 5/145/183`, Tcl sem biblioteca) é testada de novo UMA vez por diff;
4. espera o momento seguro (sem publicação e fora da janela) e a árvore limpa nos arquivos;
5. aplica, commita por caminho ("validado pelo vigia"), grava o commit, pede reinício dos serviços dos módulos e limpa.

Teste vermelho leva UMA correção. Se falhar de novo, ou se outra etapa travar, a entrega vai para o `olho`:
o Telegram recebe um aviso UMA vez por motivo, e o vigia contrata o `integrar-<id>` (Codex, cargo integrador,
na worktree dele). O integrador NÃO é contratado em três casos:
- entrega vazia;
- motivo "aplicado na árvore..." (commit falhou);
- trava passageira.

Depois de 48 h, o item do `olho` vai para `arquivados`, e o vigia não mexe mais nele: fica para você.
Ficha que terminou antes de o vigia nascer vai para `antigos`, e também ninguém mexe.
A faxina (6 h depois do fim) só apaga worktree de `falhou`/`negado`, de conferente ou de integrador
aplicado/caído, e só quando não há commit próprio; o `diff.patch` fica na ficha.

## Momento seguro
- **Janela das postagens:** a `GRADE` de `random_builds/builds/grade.py` hoje é 00:37, 06:37, 09:37, 12:07, 15:37,
  17:57, 20:37, 21:37, 22:37 e 23:37. A janela vai de 12 min antes a 18 min depois de cada horário:
  `coordenador.pedidos.na_janela_das_postagens(agora)`, com `JANELA_ANTES_MIN, JANELA_DEPOIS_MIN = 12, 18`,
  que olha também o dia anterior e o seguinte. Não calcule de cabeça: a grade muda por decisão.
- **Publicação em voo:** `remoto.delegar.publicacao_em_voo()` lista processos com `publicacao_filha`, `postar.py`
  ou `main.py ... publicar`.
- **Rodada viva:** `builds.rodada_viva.fichas()` lê `%LOCALAPPDATA%\neural-fights\rodadas\<pid>.json`
  (`rotulo` historias/builds). Uma ficha `ilegivel` é lixo, não é rodada.

## Suítes
Rode igual ao `testar.py` (`python testar.py --lista` mostra a lista):

| Parte | Comando (PowerShell) |
|---|---|
| builds | `cd random_builds; python -X utf8 -m pytest -q -p no:cacheprovider tests` |
| histórias | `cd historias; python -X utf8 -m pytest -q -p no:cacheprovider tests` |
| app/bot | `python -X utf8 -m pytest -q -p no:cacheprovider remoto` |
| tela do app | `$env:NF_TESTE_NAVEGADOR='1'; python -m pytest remoto/test_app_tela.py -q` |
| coordenador, painel, ias, palco, ferramentas, bluelock | `python -X utf8 -m pytest -q -p no:cacheprovider <pasta>` (palco: `palco/testes`) |
| neural_fights | `python -X utf8 -m pytest -q -p no:cacheprovider tests` |

Antes, na mesma sessão:
```
$env:TEMP='E:\tmp_pytest'; $env:TMP='E:\tmp_pytest'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'
```
Lint: `python -m ruff check <arquivos>`. Nunca `--fix` às cegas, porque ele apaga re-export; ponha `# noqa: F401`.
Casca do app (`painel-casca-vN`): a versão tem de ser a mesma em `remoto/app/sw.js` e em `remoto/test_app_vila_objetos.py`
(hoje é a v73).

## Fechar
- Item da Mesa: `python -m remoto.orquestrador agente-fim <id> --commit <hash> --relato "..."`. Quem fecha é o orquestrador.
- Reinício: `python -m coordenador reiniciar <app|bot|carteiro|vila>`. Quem reinicia é o orquestrador, fora da janela.
  O comando sai com 0 se reiniciou, 2 se foi recusado pelo momento (fica pendente) e 3 se o processo velho não morreu
  ou o novo não subiu.
