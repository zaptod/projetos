# Auditoria profunda — Delegação, orquestrador, apurador e Grimório — 11/10/2026

Lida em 12/10/2026 sobre o commit `707130f`. Provas rodadas em `E:\tmp_pytest\prova_delegar_*` e
`E:\tmp_pytest\prova2_*` (repositórios git de brinquedo; `LOCALAPPDATA`, `NEURAL_FIGHTS_RUNTIME_DIR`,
`NF_DELEGADOS_PASTA` e `NF_ORQUESTRADOR_PASTA` apontados para lá antes de importar o `remoto`; o
Codex é o `remoto/duble_codex.py`, com `NF_DUBLE_MODO`). Nada foi escrito em
`%LOCALAPPDATA%\neural-fights`; o Codex e o Claude de verdade não rodaram. Os scripts estão em
`scratchpad\auditoria2\provas_delegar.py` e `provas_2.py`. Os já consertados (EDEADLK da trava,
timeout dos testes, aceite de caminho protegido, ruído do .gitignore, limite lido da mensagem) não
entram aqui.

## Examinado
- `remoto/delegar.py` — 121 funções/classes lidas; o despachante: worktree por tarefa, `codex exec --json`
  / `claude -p` com eventos ao vivo, coleta do diff, testes, `aplicar` na árvore principal, permissões,
  limpeza, teto de uso do Codex e a tela da Oficina.
- `remoto/orquestrador.py` — 130 funções/classes lidas; a Mesa: estado/fila/agentes, comandos do app e o
  `aplicado` (servidor ou CLI), o `esperar` com o cursor do Grimório, vigia, sonda de uso do Claude,
  capacidade que vira regra, acessos e `para_o_app`.
- `remoto/apurador.py` — 59 funções lidas; erro no diário → `claude -p` só leitura → pedido na Mesa;
  conserto em worktree que só propõe remendo, teto por dia, barreiras do remendo.
- `remoto/decisoes.py` — 73 funções lidas; o Grimório: nós por projeto no git, árvore (bloqueada/a rever),
  `responder`, eventos, leitor/consequências, textos gerados, commit por caminho, dados para o app.
- `remoto/claude_estado.py` — 16 funções lidas; o interruptor liberado/proibido em `claude.json`
  (ausente = liberado, ilegível = proibido) com histórico.
- `remoto/duble_codex.py` — 2 funções lidas; o dublê do `codex exec --json` dos testes (modos ok, lento,
  falha, fora, binário, nada, permissão, escopo).

## Confirmados (do mais grave ao menos)

### 1. `aplicar` marca a entrega como APLICADA quando o `git apply -3` falha sem deixar conflito — gravidade: alta
- Onde: `remoto/delegar.py:2017-2025` (`aplicar`), com `_resolver_conflitos_conhecidos` (2034).
- O defeito: no ramo do merge de 3 vias o retorno do `git apply -3` é ignorado (`verificar=False`); a única
  medida de falha é "sobrou arquivo com marca de conflito" (`--diff-filter=U`). Quando o `apply -3` falha
  inteiro sem conflito (ex.: "does not exist in index", "Falling back to direct application... error"),
  `restantes` vem vazio, o estado recebe `aplicado` e o `_log` diz "aplicado na árvore principal". A árvore
  continua intocada e o segundo `aplicar` recusa com "já aplicado".
- Quando acontece: a entrega muda um arquivo que a árvore principal já apagou/renomeou (ou que já não está
  no índice) e o `--check` falha com a árvore limpa nesses caminhos → ramo `-3`. O vigia
  (`coordenador/vigia_trabalho.py:949-967`) então tenta commitar por caminho arquivos que não mudaram e cai em
  "aplicado na árvore, mas o commit falhou" (olho), com a entrega perdida e sem como reaplicar.
- Prova: `provas_2.py`, prova A2 — entrega do dublê (`remoto/existente.py` + `remoto/novo.py`), principal
  com `git rm remoto/existente.py` commitado. Saída: `git apply -3` direto → código 1
  "error: remoto/existente.py: does not exist in index / Falling back to direct application..."; depois
  `aplicar` DEVOLVEU `{'arquivos': ['remoto/existente.py', 'remoto/novo.py'], ...}`,
  `status depois: ''`, `novo.py existe na principal: False`, `estado.aplicado` preenchido.
- Conserto sugerido: conferir o `returncode` do `git apply -3` (e, após ele, `git diff --quiet HEAD -- arquivos`
  ter mudança): falhou sem `U` → `_desfazer_aplicacao` + `Recusa("git apply -3 falhou: ...")`.

### 2. `limpar_orfas` manda para o lixo a worktree VIVA de uma tarefa de outro repositório — gravidade: alta
- Onde: `remoto/delegar.py:2183-2193` (`limpar_orfas`).
- O defeito: "registradas" vem só de `git worktree list` do repositório padrão (`repo()` = E:\projetos). Toda
  tarefa criada com `repo_tarefa` (cargo `jogo-zombie`, `--repo E:\jogo_ZOMBIE`, pedido com
  `repositorio_externo` aprovado) tem a worktree em `E:\projetos-wt\codex-<id>` registrada no OUTRO
  repositório; para esta função ela é órfã e vai para `_lixo_codex` (ou é apagada) com o trabalho dentro.
  O estado da tarefa continua `criado`/`terminou`, sem `limpo`.
- Quando acontece: `python -m remoto.delegar limpar --orfas` (a limpeza recomendada no próprio `criar`:
  "limpe antes: limpar --orfas") com qualquer tarefa do zombie viva.
- Prova: `provas_delegar.py`, prova B — tarefa criada com `repo_tarefa` apontando para um segundo repositório;
  `git worktree list` dele mostra a worktree; `limpar_orfas()` devolve
  `[{'pasta': '...\wt_b\codex-tb-1', 'sobrou': None}]`, `worktree ainda existe: False`,
  estado `criado | limpo: None`.
- Conserto sugerido: considerar registrada toda worktree listada em qualquer `repo` dos estados de
  `listar()` (e nos `repos_conhecidos` das permissões), não só no `repo()`.

### 3. `coletar` grava nome de arquivo com acento ENTRE ASPAS e em octal, e a entrega inteira segue com esse nome — gravidade: média
- Onde: `remoto/delegar.py:1811-1843` (`coletar`: `--name-only`/`--numstat` sem `-z` nem `core.quotepath=false`),
  e `.replace("\\", "/")` em 1815/1840.
- O defeito: o git imprime `"docs/decis\303\243o.md"`; o código ainda troca a barra invertida por `/`, e o
  caminho vira `"docs/decis/303/243o.md"` no `diff.json`/estado. Com ele: o `git reset -q -- <nome>` de
  ruído/protegido/CRLF não acha nada; em `aplicar`, o `git status --porcelain -- <nome>` não acha a mudança
  pendente (a guarda do 3 vias fica cega) e `_desfazer_aplicacao` faz `checkout`/`unlink` de um caminho que não
  existe; o vigia commita por caminho com esse nome e falha. O repositório tem 19 arquivos rastreados com
  nome não-ASCII (`docs/obsidian/cofre/00 Início.md`, `01 💡 Ideias/…`).
- Quando acontece: qualquer entrega que crie ou mude arquivo com acento/emoji no nome (os docs do cofre do
  Obsidian, um "decisão.md").
- Prova: `provas_delegar.py`, prova C — worktree com `docs/decisão.md`; `coletar` devolve
  `caminhos no diff.json: ['"docs/decis/303/243o.md"']`, `o caminho existe no disco?: [False]`,
  `git status -- <esse nome> -> 0 '' ''` (nada encontrado).
- Conserto sugerido: `git -c core.quotepath=false diff ... -z` e separar por `\0` (e não trocar `\` por `/` em
  nome que veio do git).

### 4. `apurador.uma_volta` marca o erro como apurado ANTES de abrir o pedido; a Mesa falha e o diagnóstico some — gravidade: média
- Onde: `remoto/apurador.py:1099-1113` (`uma_volta`: `marcar(erros)` em 1103, `abrir_pedido` em 1111) e
  `abrir_pedido` (1032).
- O defeito: o `claude -p` roda (gasta uma das 8 apurações do dia), o erro entra em `apurados` e só então
  `abrir_pedido` chama `pedidos.contratar`. Qualquer exceção ali (`pedidos.json` trancado, Mesa ilegível)
  sobe de `uma_volta` (a docstring diz "Nunca levanta") e o diagnóstico não vai para lugar nenhum: a próxima
  volta diz "nenhum erro novo". Só o ramo "agenda ocupada" guarda a investigação pendente.
- Quando acontece: pulso do bot com a Mesa indisponível no instante do `contratar` (arquivo em uso, disco).
- Prova: `provas_2.py`, prova L — diário com um erro (`picasso`, ref `historia_00001:p1`), `CLAUDE_BIN` num
  `.cmd` que imprime o diagnóstico (dublê do binário, não da função), `pedidos.contratar` levantando
  `OSError` (a Mesa indisponível). Saída: `uma_volta LEVANTOU: OSError ...`,
  `apurados: ['2026-10-12T21:52:19+00:00|picasso']`, `investigacoes_pendentes: None`,
  `proxima volta: {'feito': False, 'motivo': 'nenhum erro novo'}`.
- Conserto sugerido: envolver `abrir_pedido` em try e, na falha, `_guardar_investigacao(erros, texto)` (o mesmo
  caminho da agenda ocupada) antes de devolver.

### 5. `decisoes.responder` grava a resposta e depois estoura em `gerar_textos`; o app mostra erro e a resposta duplica — gravidade: média
- Onde: `remoto/decisoes.py:1081` (`gerar_textos`: `alvo.read_bytes().decode("utf-8")` estrito), chamado em
  `responder` (607) DEPOIS do `_eventos.jsonl` (603-606) e dos `.json` (597).
- O defeito: um `docs/sessoes/<parte>.md` com um byte fora do utf-8 (cp1252 de um editor do Windows) faz
  `UnicodeDecodeError` sair de `responder` — não é `Recusa`, vira 500 na tela. A resposta já está no evento e
  no nó; ele responde de novo e o `_eventos.jsonl` ganha outra linha (o leitor cobra duas; `esperar` acorda
  duas vezes). O mesmo vale para `adicionar`, `marcar`, `semear` e `tirar_dependencia`, que chamam
  `gerar_textos` no fim. Dentro de `commitar_por_caminho` o decode estrito é apanhado (ValueError); fora dele não.
- Quando acontece: qualquer `docs/sessoes/*.md` salvo em cp1252/latin-1 (um "ã" basta).
- Prova: `provas_2.py`, prova K — repositório de brinquedo com `docs/sessoes/builds.md` em cp1252;
  `responder LEVANTOU: UnicodeDecodeError 'utf-8' codec can't decode byte 0xe3 ...`,
  `linhas no _eventos.jsonl: 1 ['verde']`, vigente gravada; segunda resposta levanta de novo e
  `linhas no _eventos.jsonl agora: 2 | historico: 2`.
- Conserto sugerido: `decode("utf-8", errors="surrogateescape")`/`"replace"` (ou `utf-8-sig`) em
  `gerar_textos` e `_so_o_bloco_mudou`, e tratar `OSError/UnicodeDecodeError` do `gerar_textos` como nota
  ("textos não regenerados"), nunca como falha da resposta.

### 6. `claude.json` trancado por um instante = "Claude PROIBIDO", e a guarda do despachante MATA o trabalhador Claude — gravidade: média
- Onde: `remoto/claude_estado.py:110-113` (`ler`: qualquer `OSError` que não seja ausência → proibido) e
  `remoto/delegar.py:1221-1225` (`_Rodada.guarda`: `motivo_proibido()` a cada 2 s → `parar`).
- O defeito: a regra "ilegível = proibido" é correta para JSON quebrado, mas um `PermissionError` passageiro
  (outro processo segurando o arquivo: antivírus, backup, o próprio `os.replace` do app — o
  `delegar._gravar_json` já documenta esse WinError 5 no Windows) é tratado como ordem do Adrian: a guarda
  mata o `claude -p` em andamento com "parei o Claude", `agente_inicio` recusa e `esperar` sai com
  `claude_proibido`. Nenhuma leitura tenta de novo. Em `mudar`, o `os.replace` também não tem retentativa
  (o toque no interruptor falha com WinError 5 se alguém estiver lendo).
- Quando acontece: leitura concorrente com escrita/bloqueio do `claude.json` (o app grava, 3 guardas + sonda +
  apurador leem a cada 2 s).
- Prova: `provas_2.py`, prova J — arquivo `{"liberado": true}`; outro processo abre com `CreateFile`
  share=0 por 6 s; `ler()` → `False | ilegivel | Claude PROIBIDO: claude.json não pôde ser lido: [Errno 13]`;
  `_Rodada.guarda` com um trabalhador `ia=claude` (python dormindo) → log "parei o Claude: Claude proibido:
  claude.json não pôde ser lido", `trabalhador Claude ainda vivo? False`; destrancado, `ler()` volta a
  "liberado".
- Conserto sugerido: em `ler`, repetir a leitura por ~1 s em `PermissionError` e só então falhar fechado; na
  guarda, exigir dois `motivo_proibido()` seguidos com `origem != "ilegivel"` para matar (ou só matar
  por `origem == "arquivo"`).

### 7. `aplicar` com conflito da casca deixa `remoto/test_app_vila_objetos.py` sujo FORA de `aplicado.arquivos` — gravidade: média
- Onde: `remoto/delegar.py:2073-2081` (`_resolver_conflitos_conhecidos`: sobe a casca também em `sw.js` e no
  teste), `aplicar` 2023 (`aplicado["arquivos"]` = só os arquivos do patch).
- O defeito: o resolvedor escreve em dois arquivos fixos que podem não estar no patch; `aplicado.arquivos`
  não os inclui. O vigia commita por caminho só o que está na lista
  (`vigia_trabalho.py:958`), e o arquivo extra fica modificado na árvore principal sem dono. A partir daí,
  qualquer outra entrega que toque esse arquivo cai em "git apply --check recusou e há mudança não commitada"
  (aplicar 2007-2011), e o retrato do handoff acusa "mudança não commitada" para sempre.
- Quando acontece: entrega que muda `sw.js` (`painel-casca-vN`) enquanto a principal já subiu a casca para
  outro número — exatamente o caso que o resolvedor existe para tratar (03/10).
- Prova: `provas_delegar.py`, prova D — principal com `sw.js` e o teste em v5, entrega v6, principal commita
  v7; `aplicar` devolve `aplicado.arquivos: ['remoto/app/sw.js']` e
  `git status: ' M remoto/app/sw.js\n M remoto/test_app_vila_objetos.py'` (ambos em v8).
- Conserto sugerido: `_resolver_conflitos_conhecidos` devolver também os arquivos extras que escreveu, e
  `aplicar` somá-los a `aplicado["arquivos"]`.

### 8. Ficha "rodando" com PID reaproveitado por outro programa nunca fecha; `testar`/`aplicar`/`limpar` ficam "Ocupado" para sempre — gravidade: média
- Onde: `remoto/delegar.py:1075-1076` (`_rodando`), `1079-1095` (`reconciliar_fantasmas`),
  `remoto/orquestrador.py:812-853` (`_pid_vivo`: só "existe um processo com esse PID?").
- O defeito: a vida do despachante é decidida só pelo número do PID. O Windows reaproveita PIDs em minutos;
  se o despachante morre (queda do VS Code, `taskkill`, reinício) e o PID vai para outro programa, a ficha
  continua `rodando` para `_rodando`, `reconciliar_fantasmas` pula ("não é False"), e `testar`, `aplicar`
  e `limpar` levantam `Ocupado` ("ainda está rodando") a cada passo do vigia, sem prazo e sem aviso. A
  `parar` grava `parar.pedido` que ninguém lê.
- Quando acontece: queda do processo do despachante seguida de reutilização do PID (12 processos novos por
  minuto nesta máquina: Chrome, pytest, git).
- Prova: `provas_delegar.py`, prova H — ficha `rodando` com `pid` de um processo vivo que não é despachante
  (o próprio python da prova) e `inicio` de horas atrás: `reconciliar_fantasmas(minutos=0): []`,
  `situacao: rodando`; `testar`/`aplicar`/`limpar` → `Ocupado: o Codex ainda está rodando`.
- Conserto sugerido: gravar junto com o `pid` a hora de criação do processo (ou a linha de comando) e
  comparar em `_pid_vivo`; e em `reconciliar_fantasmas` fechar também fichas `rodando` sem evento há
  mais de N minutos (`eventos.jsonl` parado), independentemente do PID.

### 9. `corrigir` apaga a prova dos testes ANTES de a rodada ser recusada — gravidade: baixa
- Onde: `remoto/delegar.py:1675-1676` (`corrigir`: `_mudar_estado(testes=None)` antes de `_rodada`).
- O defeito: a recusa de `_preparar_rodada` (teto do Codex, paralelo cheio, Claude proibido, limite de uso)
  chega depois de a prova ter sido zerada; a entrega que já estava testada e pronta volta a "sem testes" sem
  nada ter mudado, e o vigia tem de rodar a suíte de novo (minutos) ou, no caminho `sem_testes`, nada.
- Quando acontece: `corrigir` (inclusive o `retomar` de permissão) com o teto do Codex passado.
- Prova: `provas_delegar.py`, prova I — `testar` ok (`sha 30883236c04b`); rollout a 90 %; `corrigir recusou: o
  Codex está em 90% ...`; `estado.testes depois da recusa: None`.
- Conserto sugerido: zerar `testes` dentro de `_preparar_rodada`, depois das guardas (sob a trava).

### 10. `pedido_de_permissao` levanta `AttributeError` quando `coletar` falhou antes (`diff` é `None`) — gravidade: baixa
- Onde: `remoto/delegar.py:1490` (`estado.get("diff", {}).get("ok")`), chamado de `_encerrar` (1457).
- O defeito: `criar` grava `"diff": None`; se `coletar` em `_encerrar` levantar `Recusa` (worktree sumiu,
  `git add` falhou, `index.lock`), o `.get("diff", {})` devolve `None` e a linha estoura. O estado já foi
  gravado (terminou/falhou), mas o despachante morre com traceback em vez de registrar o pedido de permissão
  (um `.permissao.json` válido é lido ANTES desse trecho, então só a desistência por texto se perde).
- Quando acontece: resposta com "fora dos caminhos permitidos" e `coletar` recusado na mesma rodada.
- Prova: `provas_delegar.py`, prova E — ficha recém-criada (`diff: None`) com `resposta.md` "fora dos caminhos
  permitidos" → `AttributeError: 'NoneType' object has no attribute 'get'`.
- Conserto sugerido: `(estado.get("diff") or {}).get("ok")`.

### 11. `.handoff.md` da renovação não é ruído e entra na entrega — gravidade: baixa
- Onde: `remoto/delegar.py:103-118` (`NOSSOS`/`RUIDO`) e `renovar` (1696: pede a nota em `.handoff.md`).
- O defeito: o arquivo que o próprio despachante manda o trabalhador escrever na raiz da worktree não está em
  `NOSSOS`; `coletar` o coleta como mudança ("fora da lista (entrou)") e o vigia o commita na árvore
  principal — o mesmo defeito do `resposta.md` de 05/10, por outro nome.
- Quando acontece: toda tarefa renovada (`renovar_apos_turnos`/`renovar_apos_min`, ou `renovar` pelo app).
- Prova: `provas_delegar.py`, prova F — `_e_ruido('.handoff.md'): False`;
  `coletar` → `arquivos do diff: ['.handoff.md'] | avisos: ['fora da lista (entrou): .handoff.md']`.
- Conserto sugerido: `.handoff.md` em `NOSSOS` (e `permissao_concedida.md`, se algum dia for para a worktree).

### 12. `apurador`: estado corrompido zera o teto das APURAÇÕES; só o do conserto fica "esgotado" — gravidade: baixa
- Onde: `remoto/apurador.py:77-88` (`_gravar_estado`), `_contagem_de_hoje` (166), `_ler_estado` (59).
- O defeito: a docstring promete "o dia recomeça com o teto ESGOTADO", mas o ramo do arquivo corrompido só
  esgota `tentativas_por_dia`/`testes_por_dia` (conserto). `por_dia` (as 8 sessões `claude -p` por dia) parte
  de 0: um `apuracoes.json` ilegível libera mais 8 apurações no mesmo dia — e `apurados` some junto, então
  os erros das últimas 12 h são apurados outra vez.
- Quando acontece: gravação interrompida/disco cheio em `apuracoes.json`.
- Prova: `provas_2.py`, prova L2 — `por_dia` em 8; arquivo trocado por `{corrompido`;
  `_contagem_de_hoje = 0 (TETO_DIARIO = 8)`; após `_somar_uma`: `por_dia = {'2026-10-12': 1} |
  tentativas_por_dia = {'2026-10-12': 3}`.
- Conserto sugerido: no ramo corrompido, também `dados["por_dia"] = {hoje: TETO_DIARIO}`.

### 13. `ler_eventos(desde<0)` descarta uma linha inteira quando o corte cai exatamente num fim de linha — gravidade: baixa
- Onde: `remoto/delegar.py:923-925` (`ler_eventos`).
- O defeito: ao ler a cauda, o código sempre joga fora tudo até o primeiro `\n`, assumindo que a primeira
  linha veio pela metade; se `inicio` cai logo depois de um `\n`, a primeira linha estava inteira e some da
  primeira carga da tela (a Oficina mostra um evento a menos; o `offset` seguinte está certo).
- Quando acontece: primeira carga da Oficina com `eventos.jsonl` maior que 384 KB (tarefas longas).
- Prova: `provas_delegar.py`, prova M — 5 linhas, pedidos exatamente os bytes das 3 últimas:
  `eventos devolvidos: ['L4', 'L5']`.
- Conserto sugerido: só cortar quando `inicio > 0` e o byte `inicio-1` não for `\n`.

### 14. `decidir_permissao`: caminho absoluto dentro do repositório no `alvo` não libera nada e o laço de 11/10 volta — gravidade: baixa
- Onde: `remoto/delegar.py:1547-1561` (`_caminhos_do_alvo`: descarta tudo com `:`), `_liberar_caminhos` (1573).
- O defeito: o Codex escreve o `alvo` como quer; `E:\projetos\remoto\app\sw.js` (absoluto, dentro do repo)
  é descartado, `novos` vem vazio, a ficha volta a `criado` com "permissão concedida" e a lista de permitidos
  igual — o trabalhador relê "fora do escopo" e pede de novo (o caso de 11/10, agora pela forma absoluta).
- Quando acontece: `.permissao.json` com `alvo` absoluto (o Codex vê a worktree por caminho absoluto no prompt).
- Prova: `delegar._caminhos_do_alvo(r'E:\projetos\remoto\app\sw.js')` → `[]`;
  `_caminhos_do_alvo('E:/projetos/remoto/app/sw.js, remoto/x.py')` → `['remoto/x.py']`.
- Conserto sugerido: antes de descartar por `:`, tentar `Path(p).relative_to(repo_da(estado))` e
  `relative_to(worktree)`.

## Não confirmados
- `orquestrador.decisoes_novas` (695-725): resposta que chega entre `decisoes.ler_eventos()` (que fixa
  `ultima`) e `decisoes.leitor(todos=True)` é impressa com `n > cursor`, mas o cursor avança só até `ultima`:
  o próximo `esperar` a mostra de novo (lida duas vezes). Janela de milissegundos; não dá para provar sem
  dublar uma das duas funções sob suspeita.
- `orquestrador.aplicar_pelo_servidor` "mensagem" (1882-1889): `registrar_pedido` acontece ANTES do
  `aplicado(...)`; se o `_anexar` de `comandos_aplicados.jsonl` falhar (disco), o comando continua pendente e
  o próximo pulso registra o MESMO pedido de novo (depende do dedupe de `pedidos.registrar`, fora da fatia).
  Não provado: exigiria dublar `_anexar`.
- `orquestrador._gravar_json` (183-189) não tem a retentativa de `PermissionError` que `delegar._gravar_json`
  ganhou para o WinError 5 do `os.replace`; `aplicado`/`_mudar_config`/`sondar` podem cair por um leitor
  concorrente. Não reproduzi a corrida.
- `delegar.conferir_teto` (779-805) só olha `primary` (5 h); `secondary` (semana) é ignorado. Com a semana em
  100 % e a janela baixa, só a mensagem "try again at" (`_registrar_limite_de_uso`) segura; nas 40 rodadas com
  "usage limit" dos eventos reais (lidos, não alterados), as 32 com mensagem de verdade tinham a forma
  "try again at H:MM AM/PM", então hoje está coberto; se a mensagem semanal vier com data, não.
- `delegar.publicacao_em_voo` (1968-1972) casa qualquer python cuja linha de comando contenha `postar.py`
  (ex.: `python ferramentas/postar.py --help`, um editor via python): recusa falsa, passageira. Não há
  `test_postar.py` no repositório; sem caso real, fica aqui.
- `delegar._Rodada.rodar` (1292-1298): o prompt (até 100 KB) é escrito no stdin do Codex antes de ler o
  stdout; um Codex que escrevesse >64 KB no stdout antes de esgotar o stdin travaria os dois. O de verdade lê
  o stdin até o fim antes de responder (não observado travar).
- `_resolver_conflitos_conhecidos` escreve com `write_text` (fim de linha do SO = CRLF): suspeitei de diff de
  arquivo inteiro, mas o repositório tem `core.autocrlf=true` e `.gitattributes` com `text=auto`/`eol=lf`, e
  o git normaliza no `add`. Sem efeito aqui.
