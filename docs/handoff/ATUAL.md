# Passagem de bastão — 13/10/2026 14:12 (renovacao)

Leia ANTES de agir. A NOTA é do chat anterior; o RETRATO é medido agora do disco.
Regras de operação: `CLAUDE.md`. Equipe: `docs/agentes/EQUIPE.md`.

# NOTA do chat anterior

# NOTA do chat anterior

Chat de 11/10 (madrugada) → 13/10 14:30 (orquestrador), renovado a pedido do Adrian ("pare tudo, deixe a sessão reiniciar"). Fez: auditoria RASA (8 partes, consertos aplicados), depois a auditoria PROFUNDA pedida por ele ("cheque TUDO MESMO" / "analise tudo e conserte realmente tudo") — **34 relatórios em `docs/auditoria/2026-10-11-profunda/` (30 fatias de código + app-celular, godot-palco, maquina, ARQUITETURA), 281 defeitos confirmados com prova**. Consertos já aplicados: publicação (a34b355, 8 itens), Godot (f5f8cd3 pelo vigia), despachante/Mesa (8c6bcf3, c0de1ca, ebf2a0d, 1aa8d0b, 560bb01), DNS na Ethernet, tarefas duplicadas desligadas, `main` fast-forward local, lixo da máquina (parcial).

**O Codex está FORA até sábado 18/10 06:06** (95% da semana, gastou em esforço alto). Tudo pelo Claude: no máximo 3 agentes ao mesmo tempo, cada conserto em worktree → revisão do orquestrador → cherry-pick → suítes na árvore principal → fora da janela (`post-12..post+18` min dos 10 horários em `random_builds/builds/grade.py`).

## Em andamento — terminar PRIMEIRO
1. **Consolidar a auditoria profunda** (o agente foi parado no começo): ler os 34 `docs/auditoria/2026-10-11-profunda/*.md`, conferir cada "Confirmado" no código atual (`git log -5 -- <arquivo>` para ver o que a34b355/f5f8cd3 já consertaram), descartar alarme falso, escrever `docs/auditoria/2026-10-11-profunda/RESUMO.md` (tabela por gravidade, alarmes falsos, decisões do Adrian, números) e um arquivo de conserto por parte em `docs/auditoria/2026-10-11-profunda/consertos/<parte>.md` na ordem de risco: publicacao, builds (inclui banco/launcher: `nf-data.md` — o launcher apaga o que a roleta inseriu e tira `genero` de todos), app-e-bot, coordenador+delegacao, historias, ias, motor, painel-e-vila, scripts/configs/panorama, godot. O prompt completo que usei está no `.jsonl` deste chat (agente "Consolidar a auditoria profunda").
2. **Etapa 2 da reforma ("um gerente só")** — decidida por ele (Grimório `geral/gerente-unico-dos-servicos` e `geral/reinicio-por-codigo-velho` = só quando pedido, nunca na janela). Trabalho PELA METADE, NÃO TESTADO, commit WIP no ramo `worktree-agent-ac362a0bfcc5f30f8` (worktree `E:\projetos\.claude\worktrees\agent-ac362a0bfcc5f30f8`; mexe em `coordenador/supervisor.py`, `estado.py`, `__main__.py`, `servicos.json`). Terminar: os 6 itens do prompt (código velho → `reinicio_pedido` só por entrega aplicada ou `coordenador reiniciar`; `seguro()` com a janela da grade; `reiniciar` recusado não imprime ok; `reinicios_24h` persistido; `saudes_ruins` zera ao religar; `gravar_estado` com retry; assinatura do bot não casa `remoto --avisar`; `reiniciar_servico` mata o velho). `python -m pytest coordenador -q` verde → cherry-pick → reiniciar coordenador (matar `-m coordenador rodar` e `Start-ScheduledTask NeuralFights_coordenador`, ou rodar `coordenador.cmd`).
3. **Consertos do app e da operação que o Codex deixou pela metade** (parados em 1 h): worktrees `E:\projetos-wt\codex-pedido-c7e0c0d9` (app: 12 arquivos mexidos, tarefa em `scratchpad\auditoria2\conserto_app.md` — recriar se o scratchpad sumiu: é a lista do `app-celular.md`) e `E:\projetos-wt\codex-pedido-e3e343cd` (operação: `conserto_operacao.md` = itens 1-9 do `maquina.md`). Um agente Claude termina cada um NA worktree, roda as suítes, commita lá; o orquestrador revisa e faz cherry-pick.
4. **Lixo da máquina** (decisão `geral/limpeza-da-maquina` = apagar): feito em parte. Faltam 9 pastas em `E:\projetos-wt` que precisam de administrador (`codex-app-5959d5ba`, `codex-b3-lista-unica`, `codex-pedido-50a767ed`, `-5deb09bc`, `-89b0653d`, `-d8ad11ef`, `-e0abfa99`, `-f986bf91`, `_lixo_codex`: `takeown /F <pasta> /R /D Y; icacls <pasta> /grant %USERNAME%:F /T; rmdir /S /Q <pasta>` como administrador) e o `E:\tmp_pytest` (a remoção de 6.900 pastas velhas foi interrompida; repetir `Get-ChildItem E:\tmp_pytest -Directory | ? LastWriteTime -lt (Get-Date).AddDays(-2) | Remove-Item -Recurse -Force`). Os 5 arquivos soltos da raiz foram MOVIDOS para `E:\_apagados_2026-10-13` (podem ser desenhos dele; não apagar sem ele ver).
5. **`main` recebeu o ramo só localmente** (`git branch -f main refactor/arquitetura`); o push espera a decisão `geral/enviar-ao-github` (aberta no Grimório). Nunca `git push` sem ela.

## Pedidos do Adrian ainda abertos
- "Continue, quero tudo bem avaliado, tive muitos problemas com a arquitetura e bugs, quero que você analise tudo e conserte realmente tudo." → auditoria 100% feita; FALTA consertar (281 confirmados; ~40 já consertados) e executar a reforma em 10 etapas do `ARQUITETURA.md` §3 (etapa 1 feita junto com a34b355: lançadores com `--saida`; etapa 2 em andamento; 3 a 10 por fazer).
- Decisões dele já tomadas que ainda precisam virar código: reinício só quando pedido (etapa 2); Codex em esforço alto quando voltar (`--esforco high` no `coordenador pedir`).
- Esperando resposta dele no Grimório: `publicacao/build-so-no-tiktok`, `historias/gemini-sem-pro-escreve`, `geral/enviar-ao-github`.

## Decisões e regras novas deste chat
- Decididas por ele (Grimório): `app-e-bot/permissao-dos-pedidos-do-app` = projeto inteiro (`PERMITIDOS=["**"]`, 1257601); `geral/dns-do-pc` = público (Ethernet!); `geral/auditoria-profunda-custo` = esforço alto; `geral/gerente-unico-dos-servicos` = desligar as 3 tarefas (feito); `geral/reinicio-por-codigo-velho` = só quando pedido; `geral/main-recebe-o-ramo` = main recebe (feito local); `geral/limpeza-da-maquina` = apagar (parcial); pausa das histórias foi desfeita por ele ("já não quero mais que o builds pare nem o canal de histórias").
- `coordenador pedir --esforco high` existe (0c09873). `python -m coordenador pedir` avisa quando junta ao pedido aberto (4ff80d5) e só junta por mesmo texto/alvo (1257601).
- Memórias novas: `aviso-sem-rede-calado`, `historias-pausadas`, `aceite-que-nao-libera`, `pente-fino-2026-10-11`, `auditoria-profunda-2026-10-12`.

## Armadilhas encontradas
- **NUNCA `postar.py --instalar` nem `remoto --instalar`** (tarefa sem `oculto.vbs` = 10 janelas pretas; o segundo quebra sob `-X utf8`): regravar só os `.cmd` por `escrever_lancador()` (feito em 12/10; os 3 `.cmd` já usam `--saida`).
- **Codex em `--esforco high` queima a janela de 5 h em ~12 min com 6 em paralelo** e a semana em um dia. O despachante agora lê "try again at HH:MM" da mensagem dele (8c6bcf3); sem isso a Mesa lançava 10 que morriam em 30 s.
- **VS Code caiu 2x e o Claude bateu o limite de sessão 2x**: agentes em background sobrevivem na transcrição — `SendMessage` ao id retoma do ponto na MESMA sessão; em sessão nova, só o que está em worktree/arquivo sobrevive (por isso o WIP commitado no item 2).
- `rede`: a troca de DNS de 10/10 foi no Wi-Fi, mas o PC usa a Ethernet — `Get-NetAdapter | ? Status -eq Up` antes de mexer em rede.
- Dois processos escrevendo `pedidos.json` perdem um a mudança do outro quando um deles ignora `_TRAVA` (scripts avulsos: use sempre `with P._TRAVA`), e o prazo de 10 s da trava derruba `coordenador pedir` com traceback.
- `git worktree remove` de worktree de agente pode pedir `-f -f`; `delegar limpar` pede takeown para pastas que o Codex criou.
- Os relatórios de auditoria do Codex são aplicados pelo vigia como "só documentação" e levaram `.rt/` para o git (agora ruído e .gitignore, 560bb01/1aa8d0b).
- `testar.py`/CI rodam uma fração da suíte (`unittest discover` não vê pytest): não confiar no "TUDO VERDE"; rodar `python -m pytest <pasta> -q` por parte com `TEMP=E:\tmp_pytest` e `PYTEST_ADDOPTS=-p no:cacheprovider`.

# RETRATO (medido agora)

## Git
- ramo: `refactor/arquitetura`
- **mudanças NÃO commitadas (4)** — confira antes de qualquer coisa:
  - `M docs/handoff/ATUAL.md`
  - `M docs/handoff/NOTA.md`
  - `M palco/biblioteca/LICENCAS.md`
  - `M palco/biblioteca/efeitos/objetos/projetil/fogo.tscn`
- últimos commits:
  - c529d9b auditoria profunda: live e launcher (27 arquivos, 384 funcoes; 20 confirmados: torneio grava na luta corrente e diz vencedor registrado, !arena de graca depois do 1o pago, comando pago em cooldown some sem reembolso, lutador aposentado nunca volta, roda do mouse rola o canvas errado)
  - e56d911 auditoria profunda: dados e banco de personagens (6 arquivos + 15 chamadores; 11 confirmados: launcher apaga o que a roleta inseriu, insercao da roleta nao atomica entre processos, salvar reescreve todos os registros e perde genero/tipo_projetil, remover_arma sem copia, trava no TEMP de cada processo)
  - 6737890 auditoria profunda: efeitos, modelos e sons (21 arquivos, 432 funcoes; invariancia a VFX confirmada OK; 13 confirmados: som de conjuracao atenuado por x=0, pan soma e estoura 1,8x, singleton de animacao reiniciado a cada ataque, faiscas com dt dobrado, SUMMON mudo e footstep vazio, 26/46 sons apontam para arquivo inexistente)
  - 3184633 decisão(geral): lida — Enviar o ramo ao GitHub (push)? gerou nada
  - 144cd45 decisão(geral): Enviar o ramo ao GitHub (push)? → Enviar main e refactor/arquitetura (recomendado)
  - c3af559 decisão(publicacao): lida — Build que saiu só no TikTok: levar ao YouTube depois? gerou nada
  - d104da1 decisão(publicacao): Build que saiu só no TikTok: levar ao YouTube depois? → Mesma regra das histórias (recomendado)
  - eb60754 decisão(historias): lida — Gemini sem o modelo forte pode escrever roteiro? gerou nada
  - b339bbb decisão(historias): Gemini sem o modelo forte pode escrever roteiro? → Pular para o próximo provedor (DeepSeek/ChatGPT) e avisar no Telegram (recomendado)
  - fe17685 decisão(historias): lida — Criar histórias durante a pausa? gerou nada
  - 08ddce9 decisão(historias): Criar histórias durante a pausa? → Continuar criando (estoque pronto para a volta)
  - e972f7a decisão(historias): lida — Pausa dos canais de histórias gerou nada

## Pedidos e trabalhadores
- pedido-99bb27be | Consolidar a auditoria profunda e abrir os consertos qu | cancelado | pedido-99bb27be | consolidacao passou ao Claude (Codex fora ate 18/10); ver NOTA item 1
- pedido-e72192db | Auditoria profunda: Publicação das histórias, grade e c | cancelado | pedido-e72192db-1 | fatia passada ao Claude (Codex no teto da janela ate 18:31)
- pedido-9b1a4245 | Auditoria profunda: Publicação dos builds | cancelado | pedido-9b1a4245-1 | fatia passada ao Claude (Codex no teto da janela ate 18:31)
- pedido-64c2bbee | Auditoria profunda: postar.py (a rodada de publicação) | cancelado | pedido-64c2bbee | fatia passada ao Claude (Codex no teto da janela ate 18:31)
- serviços: código atual

## Mesa, fila e Grimório
- agentes ativos na Mesa: ninguém trabalhando
- fila (0):
- Grimório: todas as respostas lidas

## Serviços e máquina
- coordenador: pid 15904, código c529d9b
  - app: rodando
  - bot: rodando
  - carteiro: rodando
  - vila: rodando
- Claude: Claude liberado desde 01/10 13:30 pelo app (Android)
