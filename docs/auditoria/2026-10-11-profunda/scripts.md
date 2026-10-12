# Auditoria profunda — Scripts, tarefas do Windows e CI

Feita em 12/10/2026, 19:20–20:10, só leitura. Nenhum `.cmd` foi rodado, nenhuma
tarefa registrada ou alterada, nada escrito em `%LOCALAPPDATA%\neural-fights`.
Provas por `Get-ScheduledTask`/`Get-ScheduledTaskInfo` (exportadas para o
scratchpad), `Get-CimInstance Win32_Process`, `python -c` e pytest/unittest em
modo **só coleta** (`--collect-only` / `TestLoader.discover`), com
`TEMP=E:\tmp_pytest`, `PYTEST_ADDOPTS=-p no:cacheprovider` e
`NEURAL_FIGHTS_RUNTIME_DIR=E:\tmp_pytest\auditoria_scripts_rt`.

Aviso: enquanto eu lia, outro chat commitou `a34b355` (19:28, "Conserto da
auditoria profunda 11/10 (publicacao)"), que trocou o `>>` por `--saida` em
`ferramentas/postar.py`, `remoto/tarefa.py` e `app_celular.cmd`. O relatório
descreve o estado DEPOIS desse commit. Os arquivos gerados no disco
(`postar.cmd`, `bot.cmd`) ainda são os antigos, com `>>` — ver item 4.

O que já estava em `maquina.md` (§1, itens 11 e 12) e em `postar.md` (#1) não
volta aqui como achado novo: `>>` trancando o log, `app_celular`/`bot` falhando
0x1 a cada 10 min por dupla gerência, `retomar_codex` como sobra.

---

## Examinado

Lançadores (todos lidos inteiros, com `cat -A` para ver fim de linha):

- Rastreados: `app_celular.cmd`, `carteiro.cmd`, `coordenador.cmd`,
  `criar videos.bat`, `jogo.bat`, `painel.bat`, `testar.bat`.
- Gerados e fora do git (`.gitignore`): `postar.cmd`, `bot.cmd`,
  `historias/auto.cmd`, `random_builds/gerar.cmd`, `vila_flutuante.cmd`,
  `outputs/retomar_codex.cmd`.
- `%LOCALAPPDATA%\neural-fights\oculto.vbs` (só leitura).

Quem gera e instala:

- `ferramentas/postar.py` (`escrever_lancador` 3787, `instalar_grade` 3811,
  `instalar` 3821, `main` `--instalar`/`--hora`, `__main__` 5688-5700).
- `random_builds/builds/tarefas_windows.py` (inteiro), `random_builds/builds/pipeline/tarefas_noite.py`
  (inteiro), `random_builds/main.py` (`_noite`, `_redirecionar_saida`, `__main__`).
- `historias/contos/pipeline/tarefas.py` (inteiro), `historias/main.py`
  (`cmd_auto`, `_redirecionar_saida`, `__main__`).
- `coordenador/__main__.py` (inteiro), `coordenador/servicos.json`,
  `coordenador/supervisor.py` (`_iniciar`, `religar`, `reiniciar_servico`, `pulso`).
- `painel/flutuante/tarefa.py` (inteiro), `painel/flutuante/tarefas.py` (parte),
  `ferramentas/ocultar_consoles.py` (inteiro).
- `remoto/__main__.py`, `remoto/tarefa.py` (inteiros), `remoto/api_http.py`
  (códigos de saída e `--saida`).

Testes e CI: `testar.py`, `conftest.py` da raiz, `remoto/conftest.py`,
`coordenador/conftest.py`, `painel/conftest.py`, `.github/workflows/ci.yml`,
`.github/workflows/nightly.yml`, `pyproject.toml`,
`ferramentas/auditoria_arquitetura.py` + `arquitetura_baseline.json`,
`ferramentas/abrir.py`.

Isolamento do runtime: `remoto/config.py`, `random_builds/builds/contas.py`,
`random_builds/builds/travas.py`, `coordenador/estado.py`,
`painel/flutuante/caminhos.py`, `remoto/avisos.py`, `remoto/biblioteca.py`,
`remoto/delegar.py`, `ias/correio.py`, `ferramentas/handoff.py`,
`historias/contos/publicar/catalogo.py`.

Máquina (consulta): as 62 tarefas `NeuralFights_*`/`Historias_auto_*` com
ação, principal, settings, gatilhos e último resultado; processos vivos do
projeto com pai e linha de comando; `Winlogon\AutoAdminLogon`; o log
`Microsoft-Windows-TaskScheduler/Operational`; teste de abertura dos quatro
logs de `outputs/`.

Total: 44 arquivos lidos (33 de código/config/CI, 11 lançadores e scripts).

---

## Confirmados (do mais grave ao menos)

### 1. Depois de religar o PC, NADA volta sozinho — e o bot que avisaria é uma das tarefas que não volta — gravidade: alta

**Onde.** As 62 tarefas: `Principal = adrian / LogonType=Interactive /
RunLevel=Limited` (todas, sem exceção). `historias/contos/pipeline/tarefas.py`
docstring (linhas 7-17) explica a escolha ("precisa de sessão gráfica") e
avisa: "o PC precisa estar LIGADO e com a sessão ABERTA". `coordenador/__main__.py:46`
(`<LogonType>InteractiveToken</LogonType>`).

**O defeito.** Tarefa `Interactive` só roda com a sessão do usuário aberta.
Não há logon automático (`HKLM\...\Winlogon`: `AutoAdminLogon` vazio,
`DefaultUserName` vazio). Então uma queda de energia, um reinício forçado do
Windows Update ou um BSOD deixam a fábrica inteira parada — publicação,
histórias, gerar, coordenador, app, bot — até o Adrian sentar e digitar a
senha. O `LogonTrigger` do coordenador não ajuda: ele também espera o logon.
E o aviso ("o PC religou e ninguém entrou") não existe, porque o bot do
Telegram é uma dessas tarefas. `StartWhenAvailable=True` em todas só vale
DEPOIS do logon: aí 56 tarefas diárias perdidas disparam de uma vez.

**Quando acontece.** Em todo reinício sem pessoa na frente do PC. O último
boot foi 03/10 09:48 (`Win32_OperatingSystem.LastBootUpTime`); o rastro do que
aconteceu nos reinícios anteriores não existe (item 8).

**Prova.** `Get-ScheduledTask | % Principal` (62/62 Interactive);
`Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'`
(vazio). Nenhum documento em `docs/sessoes`, `CLAUDE.md` ou nas auditorias
irmãs menciona o reinício (grep por `AutoAdminLogon|religar o PC|logon` vazio).

**Conserto sugerido.** Decisão do Adrian (vira nó no Grimório): (a) logon
automático (`netplwiz`/`Sysinternals Autologon`) + bloqueio de tela logo
após o logon (uma tarefa `ONLOGON` com `rundll32 user32.dll,LockWorkStation`;
bloqueado o navegador funciona, deslogado não — a própria docstring diz);
ou (b) pelo menos UMA tarefa "rodar esteja o usuário conectado ou não"
(`/RU adrian /RP senha`, sem navegador: só `python -m remoto --avisar`) no
gatilho de inicialização do sistema, dizendo "o PC religou às HH:MM e a
sessão está fechada". A (b) é o mínimo: transforma silêncio em aviso.

### 2. `testar.py` e o CI rodam uma fração da suíte: 784 testes do `remoto` e 118 do `random_builds` são invisíveis, e `coordenador/` (489) nem está na lista — gravidade: alta

**Onde.** `testar.py:68-107` (`SUITES`: tudo por `python -m unittest discover`),
`.github/workflows/ci.yml:198-207` (`python testar.py`).

**O defeito.** `unittest discover` só coleta classes `TestCase`. 30 dos 35
`remoto/test_*.py` são pytest puro (funções soltas, `monkeypatch`, `tmp_path`,
`pytest.fixture`); 5 dos 93 de `random_builds/tests` também. O unittest
carrega esses módulos, não acha `TestCase` e segue em frente, verde. E três
pastas com testes não estão em `SUITES` nem no CI: `coordenador/` (11
arquivos), `esteira_sprites/` (2), `palco/testes/` (2). O "TUDO VERDE — N
testes" soma só o que o unittest enxerga.

Medido (só coleta, mesmo ambiente):

| suíte | unittest (o que `testar.py` roda) | pytest (o que existe) | invisíveis |
|---|---:|---:|---:|
| `remoto` | 189 | 973 | **784** |
| `random_builds/tests` | 1850 | 1968 | 118 |
| `painel` | 304 | 316 | 12 |
| `ias` | 196 | 201 | 5 |
| `historias/tests` | 1824 | 1826 | 2 |
| `coordenador` | não roda | 489 | **489** |
| `esteira_sprites` | não roda | 47 | 47 |
| `palco/testes` | não roda | 4 | 4 |
| `tests`, `mimetizar`, `visao` | 1055 / 178 / 107 | iguais | 0 |

Ou seja: o app do celular (`test_api_http`, `test_app_*`, `test_comandos_*`),
o delegar (`test_delegar`), o orquestrador, as decisões, o apurador e o
coordenador inteiro — a parte que mais mudou nas últimas três semanas — não
passam pelo "um comando que testa tudo".

**Quando acontece.** Sempre que alguém confia no `python testar.py` (ou no
`testar.bat`, `abrir.py testar`, CI) para dizer "não quebrei nada".

**Prova.** `python -c "import unittest; unittest.TestLoader().discover('remoto', top_level_dir='.').countTestCases()"`
= 189; `python -m pytest --collect-only -q remoto | tail -1` = "973 tests
collected". Lista dos 30 arquivos sem `unittest`: `for f in remoto/test_*.py; do grep -q unittest $f || echo $f; done`.
`grep -n coordenador testar.py` = nada.

**Conserto sugerido.** Trocar o motor das suítes por `python -m pytest -q
-p no:cacheprovider <pasta>` (os `TestCase` continuam rodando, e os
`conftest.py` de `remoto/`, `coordenador/` e `painel/` passam a valer — hoje
sob unittest eles nem são carregados); incluir `coordenador`,
`esteira_sprites`, `palco/testes`; e um teste de contrato que compara
`pytest --collect-only` com o que a suíte rodou (contagem que não bate =
vermelho), que é exatamente o que o comentário de 11/09 em `testar.py:76-80`
pedia.

### 3. A catraca de arquitetura e o `ruff` estão vermelhos há semanas: `python testar.py` SEMPRE falha e o CI nunca chega aos testes — gravidade: alta

**Onde.** `ferramentas/arquitetura_baseline.json` (teto `sys_path: 2`,
`nomes_repetidos: 1`); `testar.py:195-218` (`arquitetura()` → `--strict`);
`.github/workflows/ci.yml:31` e `:203` (`ruff check .`) e `:204-207` (catraca
antes de `testar.py`); `neural_fights/ui/view_torneio.py:304`.

**O defeito.** Hoje a medição dá `sys_path = 18` (teto 2) e
`nomes_repetidos = 2` (teto 1): 16 `sys.path.insert` novos (worker do
identity, `capas_atrasadas.py`, `vigia_som*.py`, 7 testes de regressão, um
protótipo em `docs/sprites/`) e um pacote `sprites` repetido
(`docs/sprites` x `painel/sprites`). Resultado: a etapa `arquitetura` do
`testar.py` sai FALHA todo dia, e no CI o job `workspace-windows` morre na
catraca antes de rodar um teste. O job `tests` (Linux) morre antes ainda, no
`ruff`: 21 erros, entre eles um bug real — `view_torneio.py:303-304` usa
`error` dentro de um `lambda` agendado por `after(0, ...)` depois que o
`except ... as error` já apagou o nome (Python deleta a variável ao sair do
`except`): quando o export para o Godot falhar, a janela mostra `NameError`
em vez do erro. Somado: a branch está 243 commits à frente de
`origin/refactor/arquitetura` (último push 04/10) — o CI não viu duas
semanas de trabalho, e quando vir, será vermelho por motivos que não são o
trabalho. É o cenário que a docstring da própria catraca descreve:
"vermelho falso ensina a ignorar vermelho".

**Quando acontece.** A cada `python testar.py` e a cada push.

**Prova.** `python -X utf8 ferramentas/auditoria_arquitetura.py --detalhe`
(saída com `[PIOR]` duas vezes, exit 1); `python -m ruff check . --statistics`
(15 F401, 3 F841, 2 F541, 1 F821); `git status -sb` ("ahead 243").

**Conserto sugerido.** Ou se desfazem as 16 cirurgias (as dos testes viram
`conftest`/instalação editável; `docs/sprites/prototipo_*.py` sai da conta
via `IGNORAR` ou vira `.txt`), ou se grava o novo teto COM a explicação no
commit, como a ferramenta pede — o que não dá é ficar vermelho. `ruff --fix`
só para F401/F541 (memória "CI vermelho desde agosto": cuidado com
re-exports); o F821 é conserto à mão (`erro = error` antes do lambda).
Depois, push.

### 4. `postar.py --instalar` é o único instalador que ainda aponta a tarefa direto para o `.cmd` (volta a janela preta), e o `--hora` recria a tarefa antiga que o `instalar_grade` apaga de propósito — gravidade: média-alta

**Onde.** `ferramentas/postar.py:3830` (`"/TR", f'"{lancador}"'`),
`:3821-3823` (`nome = nome or TAREFA`), `:3811-3818` (`instalar_grade` apaga
`NeuralFights_postar`), `:5416` (`--hora` → `instalar(args.hora)` sem
`nome`). Compare com `tarefas_noite.py:114`, `tarefas.py:120`,
`remoto/tarefa.py:68-73`, `painel/flutuante/tarefa.py:161-164`, que usam
`tarefas_windows.acao_oculta`.

**O defeito.** Os outros quatro instaladores foram adaptados em 17/09 para o
`wscript //B oculto.vbs <cmd>`; o do `postar.py` não. Rodar
`python ferramentas/postar.py --instalar` hoje recria as 10
`NeuralFights_postar_HH` com `/TR "E:\projetos\postar.cmd"`: dez janelas
pretas por dia, exatamente o que o Adrian pediu para tirar. E é o comando
que alguém VAI rodar em breve, porque o `a34b355` trocou o `>>` por `--saida`
no gerador mas o `postar.cmd` do disco ainda é o antigo (linha 5: `>>`) — a
única forma documentada de regravar é `--instalar`. O
`ferramentas/ocultar_consoles.py:12-14` ainda lista `remoto --instalar` e
`main.py auto --instalar` como os que desfariam a troca (já consertados) e
não cita o `postar.py` (o único que desfaz).

O `--hora HH:MM` tem o segundo problema: `instalar(args.hora)` sem `nome`
cai em `TAREFA = "NeuralFights_postar"`, o nome sem sufixo — que o
`instalar_grade` apaga com o comentário "se ela ficar, o dia ganha uma
postagem a mais às 17:07 além da `_17`". Um `--hora 17:57` cria exatamente a
duplicata que o código tenta evitar.

**Quando acontece.** Em qualquer reinstalação da grade; no `--hora` sempre.

**Prova.** Leitura do código acima; `remoto/test_remoto.py:588-592` testa
que o bot usa `wscript.exe //B //Nologo` — não há teste equivalente para o
`postar.py`. As 10 tarefas vivas estão corretas hoje
(`wscript ... "E:\projetos\postar.cmd"`, ETL=PT2H) porque foram trocadas à
mão em 17/09 (`maquina.md` §1).

**Conserto sugerido.** `"/TR", tarefas_windows.acao_oculta(lancador)` em
`instalar`; `--hora` passa `nome=nome_da_tarefa(int(hora[:2]))`; um teste
igual ao do bot; e um `--lancador` (só regravar o `.cmd`, como a Vila tem) para
aplicar o `--saida` sem recriar tarefa. Regravar fora de `post-12 … post+18`.

### 5. `remoto --instalar` crasha DEPOIS de criar a tarefa e ANTES de endurecê-la (`text=True` no `schtasks` sob `-X utf8`), e "corrige" a tarefa viva para pior — gravidade: média

**Onde.** `remoto/tarefa.py:63-66` (`_schtasks` com `text=True`), `:78-100`
(`instalar`: `/Create` → `endurecer`). Os três módulos irmãos
(`tarefas_noite.py:88-91`, `tarefas.py:92-98`, `painel/flutuante/tarefa.py:131-139`)
documentam por que NÃO usar `text=True`.

**O defeito.** Todo lançador do projeto roda `python -X utf8`. Nesse modo
`text=True` decodifica como UTF-8, e o `schtasks` escreve na página de
código do console (cp850: "ÊXITO", "próxima" → bytes 0xD2/0xA2). Medido
agora com uma consulta: `subprocess.run(['schtasks','/Query',...],
text=True)` sob `-X utf8` → `UnicodeDecodeError: 'utf-8' codec can't decode
byte 0xa2` impresso pela thread leitora e `stdout=''`. No `/Create` a
mensagem de êxito tem "ÊXITO" na primeira linha: o `instalar()` devolve
`mensagem=""` (ou levanta, conforme a versão do Python) — e no caminho do
`/Create` que falha, o motivo some. Pior: se levantar, a tarefa já foi criada
com os padrões do Windows (recusa na bateria, nunca recupera horário
perdido) e o `endurecer` não roda. A tarefa viva hoje tem
`ExecutionTimeLimit=PT0S` e `WakeToRun=False` (ajustados à mão); o
instalador deixaria `PT72H` + `WakeToRun=True` (o `endurecer` liga o acordar
em toda tarefa, e o bot é o motivo que a Vila cita para não precisar
acordar). São dois instaladores (o de código e a mão de quem ajustou)
escrevendo a mesma tarefa com configurações diferentes, sem que o código
saiba.

**Quando acontece.** Em `python -m remoto --instalar` (o `bot.cmd` do disco
ainda é o antigo com `>>`; para aplicar o `--saida` do `a34b355` alguém vai
rodar isso).

**Prova.** `python -X utf8 -c "import subprocess; subprocess.run(['schtasks','/Query','/TN','NeuralFights_bot_telegram'], capture_output=True, text=True)"`
(traceback de decode); sem `text=True` os bytes vêm (`b'...Hora da pr\xa2xima...'`).
`Get-ScheduledTask NeuralFights_bot_telegram | % Settings` (PT0S, Wake=False).

**Conserto sugerido.** `_schtasks` igual ao de `tarefas_noite.py` (bytes +
`decode("utf-8","replace")` ou `"oem"`); depois do `endurecer`, `instalar()`
chama `limitar_execucao(TAREFA, "PT0S")` (o regex `PT\d+[HMS]` aceita) para
o bot ficar sem limite como a tarefa viva; e o `WakeToRun` vira decisão
escrita no código (a docstring da Vila diz que "a tarefa do bot já acorda" —
se é isso, manter `True` e ajustar a tarefa viva, não o contrário). E um
`--lancador` para regravar só o `.cmd`, como a Vila tem.

### 6. O coordenador registra 0x800710E0 em TODO disparo de 5 min enquanto vive, `RestartOnFailure` 999x pode virar um laço de 1 em 1 min, e `desligar-tarefas-antigas` para no primeiro nome que faltar — gravidade: média

**Onde.** `coordenador/__main__.py:44-46` (`xml_tarefa`: `LogonTrigger` +
`TimeTrigger` PT5M, `MultipleInstancesPolicy=IgnoreNew`,
`RestartOnFailure PT1M x 999`), `:73-75` (`tarefas_antigas` com
`check=True`), `coordenador/supervisor.py:757-760` (`rodar` devolve 1 quando
a `TravaUnica` já é de outro).

**O defeito.** (a) O processo nunca termina; o gatilho de 5 min dispara com
a tarefa "Em execução" e o `IgnoreNew` recusa — e o Agendador grava essa
recusa como "Último resultado 0x800710E0" com a hora do disparo
(`LastRunTime 19:30:30` com o pid 5208 vivo desde antes). Não é bateria
(`maquina.md` suspeitou e descartou); é o desenho. Consequência: o último
resultado do coordenador é SEMPRE um código de falha, e uma falha real fica
indistinguível. (b) `rodar()` sai com 1 quando outro coordenador já tem a
trava (ex.: um `python -m coordenador rodar` aberto à mão no VS Code, ou o
python órfão que sobrevive quando o Agendador mata só o `wscript`). Com
`RestartOnFailure` de 1 min x 999, a tarefa relança a cada minuto — cada
relance importa `coordenador`, `remoto.orquestrador`, `ias.assembleia`,
`ferramentas.obsidian` — por até 16 h. (c) `tarefas_antigas` usa
`check=True` num laço: se `NeuralFights_app_celular` não existir (ou for
renomeada), o `CalledProcessError` interrompe antes do bot e da Vila; o
comando nunca rodou (as três tarefas estão `Ready`/habilitadas), então o
caminho nunca foi exercido.

**Quando acontece.** (a) a cada 5 min, hoje; (b) sempre que houver dois
coordenadores; (c) na primeira vez que alguém rodar o comando com um nome
faltando.

**Prova.** `Get-ScheduledTaskInfo NeuralFights_coordenador`
(`LastTaskResult 0x800710E0`, `LastRunTime 12/10 19:30:30`, `State Running`)
contra `Win32_Process` (pid 5208 `-m coordenador rodar` com pai cmd 20396 ←
wscript 17264). XML lido no `__main__.py`.

**Conserto sugerido.** Tirar o `TimeTrigger` de 5 min (ou pôr
`StopExisting`? não — isso mataria o coordenador a cada 5 min) e deixar o
`LogonTrigger` + `RestartOnFailure` cuidarem da volta; `rodar()` devolve 0
quando a trava é de outro ("já tem um no ar" não é falha); `tarefas_antigas`
com `check=False` e um resumo por nome. Fica registrado que o `app_celular`
é o único serviço cuja tarefa foi feita à mão (ação sem aspas, sem
`WorkingDirectory`) e cujo `.cmd` não tem gerador — numa máquina nova ninguém
consegue recriá-la, o motivo que `painel/flutuante/tarefa.py:12-16` dá para
ter gerador.

### 7. Limite de execução só nas 10 de postagem; nas 46 diárias uma rodada pendurada segura a tarefa por 72 h, ninguém mata o Python e a trava `historias_auto` fecha a fábrica em silêncio — gravidade: média

**Onde.** `tarefas_windows.limitar_execucao` só é chamado em
`ferramentas/postar.py:3850`; `tarefas_noite.instalar` e
`historias/.../tarefas.instalar` chamam só `endurecer` (que preserva o
`PT72H` do `/Create`). `tarefas_windows.py:103-111` (medido em 06/10: o
limite mata só o `wscript`). `random_builds/builds/travas.py:100-101`
(`msvcrt.locking`, solta só quando o processo morre);
`historias/contos/pipeline/agenda.py:1311` e `noite.py:984` (`esperar=0.0`:
o segundo sai na hora).

**O defeito.** Uma `main.py auto` que trava (navegador preso, `print` num
console, laço de falha de imagem — `maquina.md` §1 viu a `Historias_auto_07`
8 h "Running" em laço) fica com a trava `historias_auto`; as outras 22 horas
do dia disparam, veem a trava ocupada e saem; o Agendador só devolve a
tarefa daquela hora depois de 72 h e, mesmo aí, mata o `wscript` e deixa o
Python. Resultado: três dias sem história nova, com 22 tarefas "0x0" verdes
(cada uma saiu limpa dizendo "já tem uma rodada"). O mesmo vale para
`NeuralFights_gerar_HH`. Não há vigia que mate rodada pendurada (grep por
`pendurad|taskkill` em `agenda.py`/`noite.py`: nada; o `postar.py` tem a
"dona pendurada" só para a postagem).

**Quando acontece.** A cada rodada que trava sem morrer.

**Prova.** `Get-ScheduledTask Historias_auto_*,NeuralFights_gerar_* | % Settings.ExecutionTimeLimit`
= `PT72H` nas 46; `NeuralFights_postar_*` = `PT2H`. Hoje há 2 `auto.cmd` e 2
`gerar.cmd` vivos (pids 4332/3200 e 15916/17296, pais cmd←wscript de
tarefas diferentes) — pelas faixas de paralelo isso é esperado, e mostra que
a trava é por história, não por rodada: uma pendurada segura a sua faixa.

**Conserto sugerido.** Um "pulso" por rodada (a `atividade.jsonl` já tem) e
um vigia no coordenador (`vigia_trabalho`) que mata o pid da rodada sem
pulso há N min e avisa; `limitar_execucao(nome, "PT6H")` nas 46 (devolve a
tarefa ao Agendador; não substitui o vigia). E ligar o histórico do
Agendador (item 8) para ver quando isso aconteceu.

### 8. O histórico do Agendador está DESLIGADO: nenhum disparo, falha ou recusa fica registrado — gravidade: baixa (mas é o que impede investigar os itens 1, 6 e 7)

**Onde.** `Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational'`
→ `IsEnabled=False`, `RecordCount` vazio.

**O defeito.** Só existe o "Último resultado" de cada tarefa, sobrescrito a
cada disparo. "6 horários perdidos" (memória `aviso-sem-rede-calado`), "4
dias com horário vazio sem causa" (`maquina.md` §18) e o 0x1 da
`Historias_auto_04` não têm rastro: não dá para saber se a tarefa disparou e
morreu ou se nem disparou.

**Prova.** `Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'; StartTime=(Get-Date).AddDays(-7)}`
→ 0 eventos.

**Conserto sugerido.** `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`
(precisa de administrador; decisão dele). Custa alguns MB; o `recursos.py`
do panorama pode ler os eventos 103/203/0x800710E0 por tarefa.

### 9. O `conftest.py` da raiz não isola `remoto.config`, `remoto.biblioteca`, `ias.correio`, `handoff`, `catalogo` — e sob o unittest do `testar.py` nenhum `conftest` é carregado — gravidade: média-baixa

**Onde.** `conftest.py:26-29` (só exporta `NEURAL_FIGHTS_RUNTIME_DIR`);
`remoto/config.py:26-28` (`LOCALAPPDATA` direto), `remoto/biblioteca.py:17`,
`ias/correio.py:85`, `ferramentas/handoff.py:35`,
`historias/contos/publicar/catalogo.py:46`, `coordenador/estado.py:11-20`
(honra a variável só se `PYTEST_CURRENT_TEST` também estiver — sob unittest,
nunca). Compare `random_builds/builds/contas.py:98-107` e
`remoto/avisos.py:61-64`, que honram.

**O defeito.** O comentário do `conftest.py` promete "isolamento que não
depende de como o teste foi lançado". Não é o caso: com a variável apontando
para `E:\tmp_pytest\x`, `remoto.config.runtime_dir()` continua devolvendo
`C:\Users\adrian\AppData\Local\neural-fights` e `remoto.biblioteca.PASTA`
idem (medido). Hoje os testes de `remoto/` se protegem um a um
(`config.ARQUIVO`, `monkeypatch`, `remoto/conftest.py` para avisos e
`claude_estado`), então não achei teste escrevendo no runtime real — mas o
próximo teste (do Codex, por exemplo, que roda a suíte na worktree) que
chamar `config.salvar`, `biblioteca`, `ias.correio` ou `coordenador.estado`
sem patch escreve em produção. E `remoto/conftest.py`,
`coordenador/conftest.py` e `painel/conftest.py` são fixtures do pytest: o
`testar.py` roda tudo por `unittest`, que não os carrega (ligado ao item 2).

**Quando acontece.** Em todo teste novo sem patch; em `python testar.py`
sempre que um `TestCase` dependa desses `conftest`.

**Prova.** `NEURAL_FIGHTS_RUNTIME_DIR=E:/tmp_pytest/x python -c "from remoto import config, biblioteca; print(config.runtime_dir(), biblioteca.PASTA)"`
→ os dois em `C:\Users\adrian\AppData\Local\neural-fights`.

**Conserto sugerido.** Uma função única (`builds.contas.runtime_dir` já é
ela) usada por `remoto.config`, `biblioteca`, `ias.correio`, `handoff`,
`catalogo` e `coordenador.estado` (sem a condição de `PYTEST_CURRENT_TEST`);
e o item 2 (pytest) faz os `conftest` valerem no `testar.py`.

### 10. `integridade()` do `testar.py` não olha `.cmd` nem `coordenador/`, `ias/`, `palco/`, `esteira_sprites/`; e a pasta descartável fica no C: — gravidade: baixa

**Onde.** `testar.py:58` (`PASTA_DESCARTAVEL = tempfile.gettempdir()/...`),
`:163-175` (`EXTENSOES_VIGIADAS = ("*.py", "*.bat")`, lista de pastas).

**O defeito.** A checagem de byte de controle nasceu porque um LANÇADOR
(`.bat`) foi corrompido pelo heredoc. Os três `.cmd` rastreados
(`app_celular.cmd`, `carteiro.cmd`, `coordenador.cmd`) e os cinco gerados não
são olhados; `coordenador/`, `ias/`, `palco/`, `esteira_sprites/` e
`neural_fights/` também não. E `tempfile.gettempdir()` é o `C:` (a regra do
projeto é `TEMP=E:\tmp_pytest`, "o C: vive cheio"): `testar.bat`/`abrir.py
testar` não exportam `TEMP`, então a suíte do neural_fights escreve
`armas.json`/`personagens.json`/`live.sqlite3` no C:.

**Prova.** Leitura; `python testar.py --lista`.

**Conserto sugerido.** `("*.py", "*.bat", "*.cmd")`, pastas da raiz inteiras
menos `IGNORAR`, e `PASTA_DESCARTAVEL` sob `E:\tmp_pytest` quando existir.

### 11. Quatro geradores escrevem CR CR LF nos `.cmd` (o próprio projeto já chamou isso de "sorte") — gravidade: baixa

**Onde.** `historias/contos/pipeline/tarefas.py:65` (`write_text("...\r\n", encoding="utf-8")`),
`ferramentas/postar.py:3791`, `remoto/tarefa.py:53`, `coordenador/__main__.py:53`.
Certo em `tarefas_noite.py:76-78` (`newline=""`) e `painel/flutuante/tarefa.py`
(bytes).

**O defeito.** `write_text` no Windows traduz `\n` em `\r\n`; o texto já
tem `\r\n` → `\r\r\n` no disco. `cat -A` confirma `^M^M$` em `auto.cmd`,
`bot.cmd`, `postar.cmd` e `coordenador.cmd`. O `cmd.exe` tolera hoje; o
`tarefas_noite.py:72-75` diz por que não confiar.

**Conserto sugerido.** `open(destino, "w", encoding="utf-8", newline="")`
nos quatro, como o `tarefas_noite.py`.

### 12. `--saida` sem valor ou pasta `_logs` ausente: a rodada morre antes do `main()` sem uma linha em lugar nenhum — gravidade: baixa

**Onde.** `historias/main.py:688-710` e `random_builds/main.py:224-243`
(`_redirecionar_saida`), `ferramentas/postar.py:5688-5700`,
`remoto/__main__.py:232-242`, `remoto/api_http.py:2704-2710`.

**O defeito.** (a) `--saida` como último argumento → devolve `argv[:i], None`
e a saída cai no console do Agendador — o `print` que travou 13 min em
08/09. (b) `open(arquivo, "a")` fora de `try`: se `outputs/_logs/` foi
apagada (limpeza de disco, `git clean`), a exceção sai antes do `main()`, o
console vai para `NUL` (`> NUL 2>&1`), e a tarefa termina 0x1 sem rastro —
a pasta só é criada pelo `escrever_lancador`, no `--instalar`.

**Conserto sugerido.** `Path(arquivo).parent.mkdir(parents=True, exist_ok=True)`
antes do `open`, e `--saida` sem valor é erro de uso (exit 2 com mensagem no
`atividade.jsonl`).

---

## Não confirmados

- **`>>` + neto segurando o log.** Com o `.cmd` antigo (`>>`), o handle do
  log passa ao Python e a qualquer filho que ele abra sem `capture_output`
  (Chrome do patchright, `git`, `claude -p`). Se o bot morrer e um neto
  ficar, o arquivo continua com `deny-write`: a tarefa de 10 min morre antes
  do Python (conhecido) E o `supervisor._iniciar` (`open(log, "a")`) levanta
  `PermissionError`, que o `religar` conta como falha e, após 5 por hora,
  "parei de tentar". Hoje os quatro logs abrem livres (testado); com o
  `--saida` do `a34b355` aplicado (regravando os `.cmd`), o cenário some.
- **Espaços e aspas.** Nenhum caminho em uso tem espaço (`E:\projetos`,
  `C:\Python314`). Os geradores põem aspas em tudo; a ação da
  `NeuralFights_app_celular` é a única sem aspas (feita à mão). O
  `oculto.vbs` monta `cmd.exe /c "<cmd>"`, que funciona com espaço no nome
  (regra das duas aspas do `cmd /c`). Não há defeito ativo.
- **`cd /d`.** Presente em todos os `.cmd`; os `.bat` usam `cd /d "%~dp0"`.
  Nada a apontar.
- **`oculto.vbs` e o código de saída.** `shell.Run(..., 0, True)` devolve o
  código do `cmd.exe`, que devolve o do Python: os `0x1`/`0x3`
  (`api_http.py:2620-2622` devolve 3 na porta ocupada) chegam ao Agendador.
  Funciona como descrito no comentário.
- **Variáveis de ambiente do Agendador.** As tarefas rodam com o token
  interativo do `adrian`, então `PATH`, `TEMP` e `LOCALAPPDATA` são os dele.
  `ffmpeg` só é procurado por `shutil.which` (no PATH do usuário); não achei
  código dependendo de variável que o Agendador não tenha. O
  `coordenador/__main__.py:33-34` já evita `%VAR%` nos argumentos
  (documentado: o Agendador não expande).
- **`vila_flutuante.cmd` x coordenador.** A guarda procura `pythonw.exe` com
  `painel.flutuante` na linha; o `servicos.json` lança a Vila com o mesmo
  `pythonw -m painel.flutuante --medio`, então a guarda vê a Vila do
  coordenador e não abre uma segunda. Correto.
- **Dois `auto.cmd` e dois `gerar.cmd` ao mesmo tempo.** Vivos agora (pids
  4332/3200 e 15916/17296, de tarefas diferentes). É o paralelo por faixas
  (memória "trabalho pesado de dia, 2 em paralelo"), não duplicação.
- **`NeuralFights_capas_atrasadas` (03:10, `python.exe` direto, sem `.cmd`
  nem gerador).** Única tarefa que chama Python sem `-u` nem `--saida`; o
  `capas_atrasadas.py:28` faz `sys.path.insert`. Resultado 0x0 diário; o 403
  de miniatura está em `maquina.md` #10. Sem gerador, vale o mesmo aviso do
  item 6 (não recriável).
