# Provar um duelo pelo caminho real, sem sujar nada

O caminho real é `main.py duelo` (gravação pelo `fight_recorder` em subprocesso → timeline →
renderer → `final_celular.mp4`). Dublê/fixture não conta como prova.

## Isolamento (o que cada variável protege)
| Risco | Proteção |
|---|---|
| escrever no banco vivo e na carreira dos lutadores | `NEURAL_FIGHTS_RUNTIME_DIR` = cópia só com `personagens.json`, `armas.json`, `match_config.json` (o runtime inteiro tem 5,4 GB — não copie tudo) |
| som diferente do de produção | `NEURAL_FIGHTS_SOUND_RUNTIME_DIR` = `%LOCALAPPDATA%\neural-fights\sounds` (só lido) |
| o duelo de prova entrar no catálogo e ir ao ar | rodar o `main.py` **da worktree**: `outputs/` dela é vazio e fora do git; o catálogo de produção lê `E:\projetos\random_builds\outputs` |
| código errado | rodar de `<worktree>\random_builds` (ali `import builds` é o da worktree) |

## Comandos (PowerShell, da worktree)
```powershell
$wt = "E:\projetos\.claude\worktrees\<sua-worktree>"
$rt = "E:\tmp_pytest\runtime_duelo"
New-Item -ItemType Directory -Force $rt | Out-Null
Copy-Item "$env:LOCALAPPDATA\neural-fights\personagens.json","$env:LOCALAPPDATA\neural-fights\armas.json","$env:LOCALAPPDATA\neural-fights\match_config.json" $rt
$env:NEURAL_FIGHTS_RUNTIME_DIR = $rt
$env:NEURAL_FIGHTS_SOUND_RUNTIME_DIR = "$env:LOCALAPPDATA\neural-fights\sounds"
$env:TEMP = "E:\tmp_pytest"
Set-Location "$wt\random_builds"
python main.py duelo --p1 "Gunnar Vexevok" --p2 "Aurelia Argalacern" --seed 4242 --arena Torre
```
Par e seed fixos = a mesma luta das provas de 14–18/10 (`E:\tmp_pytest\prova_hud\`), então dá
para comparar com a base. `--arena` aceita os cenários de vídeo (Torre, Vulcao, Duto, Poco,
Arena, Arena Pequena…). `--preview` acelera o render mas não é o render de produção: a prova
final é sem ele.

Re-render sem re-simular (mudou só desenho/edição): `python main.py duelo --rerender duelo_000NN --refazer-edicao`
— numa CÓPIA da pasta, nunca num duelo do estoque de produção (o mp4 dele é o que vai ao ar).

## Depois
1. `python ..\.claude\skills\conferente-video-mp4\scripts\medir_video.py outputs\duelo_00001\final_celular.mp4 --saida E:\tmp_pytest\conferente\<tarefa>`
2. Read na `folha.png` e nos `quadro_*_zona.png`.
3. Compare com a base (mesmo par/seed) quando a mudança não devia mexer na luta: vencedor,
   duração e K.O. do `fight.json` (`luta`) iguais.
4. Apague `$rt` e o `outputs\` da worktree só depois de anotar os caminhos no relatório.

Tempo medido: um duelo novo de ~22 s leva ~3,6–4,5 min ponta a ponta no i5 (render 45–90 s por perfil).
