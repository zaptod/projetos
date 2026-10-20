# Referência: assinaturas de falha

Medido em 20/10/2026 nos 77 `testes.log` de `%LOCALAPPDATA%\neural-fights\delegados\*\`
e conferido no código (`remoto/delegar.py`, `coordenador/vigia_trabalho.py`, `painel/conftest.py`, `conftest.py`, `testar.py`).

## Assinaturas
| Assinatura no log | O que é | Veredito | O que fazer |
|---|---|---|---|
| `ImportError: E:\projetos-wt\codex-<id>\...\__init__.py` às centenas, vindo de `if not path.exists(): raise ImportError(path)` (ex.: 955 errors no pedido-50a767ed) | a worktree foi apagada ou movida no meio do teste (um `limpar` ou a faxina) | ambiente | `Test-Path E:\projetos-wt\codex-<id>`; aplique pelo `diff.patch` da ficha e teste na árvore |
| `FileNotFoundError` de arquivo RASTREADO dentro de `E:\projetos-wt\codex-<id>\` (`historias/config/llm.json`, `ferramentas/postar.py`, `decisoes/geral/modo-de-trabalho.json`) | mesma coisa: a worktree estava incompleta ou sumindo | ambiente | confira com `git ls-files <arquivo>` que ele é rastreado |
| `WinError 5`, `145`, `183` (vistos também `3` e `267`) em pasta temporária | pasta presa pelo Windows | ambiente | o vigia já reteste uma vez (`INFRA`); rode de novo com outro `--basetemp` |
| `tcl_findLibrary`, `init.tcl`, `tk wasn't installed properly` | Tcl carregado pela metade, com vários pytest juntos | ambiente | no `painel/` o conftest já vira skip; fora dele, rode isolado |
| `patchright._impl._errors.TimeoutError: Locator.wait_for: Timeout 5000ms` (ou 15000ms) | Chrome lento ou tela que não montou | instável OU defeito de JS | rode isolado 3x; se falhar sempre, abra a tela (conferente) e rode `node --check` no `.js` |
| `subprocess.TimeoutExpired` em `Godot_v4.7.2-stable_win64_console.exe` e "o Godot passou de N s" | Godot headless lento ou travado | ambiente, quase sempre | rode o teste do palco sozinho, com a máquina livre |
| código `2147483651` (0x80000003) e `<cannot get C stack on this system>` | o processo Python CAIU (crash nativo); não é assert | ambiente | rode a suíte em pedaços até achar o arquivo; isolado, costuma passar |
| `codigo: None` e `[estourou o tempo]` no fim | passou de `testes_timeout_s` (1800 s), e o `_matar` derrubou a árvore | ambiente ou teste pendurado | ache o último teste do log; com `faulthandler_timeout=180` sai `Timeout` e o traceback |
| `OSError: [Errno 28]`, `No space left on device` | disco cheio, quase sempre o C: | ambiente | `python -c "import shutil;print(shutil.disk_usage('C:/').free//2**30)"`; ponha `TEMP` no E: |
| `AssertionError` com hora, prazo, `elapsed`, segundos ou "deveria ter ..." | teste de tempo apertado | instável | dê folga no prazo; não barre a entrega |
| `AssertionError` lógico que falha igual isolado E não falha no caso-base | defeito da entrega | entrega | conserte o código ou mande `corrigir` |

## Códigos de saída do `delegar`
- `testar`: 0 ok, 5 falhou. Na ficha, `testes.codigo` é o código do pytest: 1 = falhas, 2 = interrompido, `None` = estourou o tempo.
- `diff`: 0 passa, 4 recusado. Qualquer `Recusa` sai com 3 e imprime "recusado: ..." no stderr.

## O que já é engolido sozinho
- O `delegar.testar` põe `TEMP`/`TMP` numa pasta nova por rodada (`E:\tmp_pytest\delegados\<id>\r<data>-<pid>-<n>`) e
  `PYTEST_ADDOPTS=-p no:cacheprovider --basetemp=<...>/bt`, e acrescenta `-o faulthandler_timeout=180` a todo pytest.
- O vigia reteste UMA vez por diff quando a cauda casa com `INFRA`: `WinError (5|145|183)`, `tcl_findLibrary` ou
  `Can't find a usable init.tcl`.
- O `painel/conftest.py` transforma em skip a falha de Tk sem biblioteca (`TK_SEM_BIBLIOTECA`).
- O `conftest.py` da raiz aponta `NEURAL_FIGHTS_RUNTIME_DIR` para `%TEMP%\neural-fights-pytest`, a não ser que já
  esteja definido. O `testar.py` usa `E:\tmp_pytest\neural-fights-testar`, `SDL_*=dummy` e `PYTHONUTF8=1`.

## De onde vem o código que o teste importa (medido em 20/10)
| `cwd` | `builds` | `contos` | `neural_fights`, `remoto` |
|---|---|---|---|
| raiz de uma worktree | `E:\projetos\random_builds\builds` (PRODUÇÃO) | `E:\projetos\historias\contos` (PRODUÇÃO) | a worktree |
| `<worktree>\random_builds` com `python -m pytest` | a worktree | — | — |

`historias/tests` tem `__init__.py`; por isso o pytest põe `historias/` no `sys.path`, e `contos` vem da worktree
quando o teste é de `historias/tests`. `random_builds/tests` não tem `__init__.py`. Na dúvida, imprima o `__file__`.

## Comandos de prova (PowerShell)
```
$env:TEMP='E:\tmp_pytest'; $env:TMP='E:\tmp_pytest'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'
python -X utf8 -m pytest "<nodeid>" -q --basetemp=E:\tmp_pytest\iso-<id>       # um teste
1..3 | % { python -X utf8 -m pytest "<nodeid>" -q --basetemp=E:\tmp_pytest\iso-<id>-$_ }   # repetido
python testar.py --lista                                                         # as suítes e os cwd
```
