# Mudar a grade do canal de duelos (conferido em 20/10/2026)

## Quem lê a grade (`builds.grade`) — 18 módulos fora dos testes
`ferramentas/postar.py` · `random_builds/builds/pipeline/noite.py` (folga da geração) ·
`builds/publicar/{conferencia,sinais,analise,youtube_web}.py` · `coordenador/{pedidos,supervisor}.py`
(janela das postagens) · `remoto/{relatorios,painel_dados,acoes}.py` · `painel/flutuante/dados.py`
(previsão do próximo horário) · `visao/panorama/{auditoria,recursos}.py` · `ferramentas/{handoff,obsidian}.py`
· `ferramentas/manutencao/vigia_som_dia.py` · `historias/contos/pipeline/agenda.py`.
Refazer a lista: Grep `builds\.grade|from builds import grade` em `*.py`, sem `tests/`.

Consequências que já morderam:
- a **conferência** cobra "horários em falta" pela grade (`deficit`): grade menor muda o alarme;
- a **geração** reserva a meia hora em volta de cada horário: grade menor libera mais tempo;
- o **alvo do lote** (`alvo_do_lote`) é "horários até segunda 07h + piso": grade menor = alvo menor;
- a **análise** só compara "antes × durante" se souber as datas do teste: no WIP isso é
  `publicacao.json → testes` + `grade.teste_do_tiktok()` (só datas, não ligam nada) — **ainda
  não existe no ramo**; sem isso, anote o início da mudança no commit e na skill
  `metricas-medida-da-semana`, ou a semana não tem comparação.

## O que o plano pede × o que existe
| | código (refactor/arquitetura) | WIP `integracao/publicacao-semana1` | plano (semana 1) |
|---|---|---|---|
| YouTube | 10/dia, cota duelo 4 build 3 estreia 1 | 10/dia, estreia trocada por duelo (`TROCAS_NA_COTA`) | **3/dia em horário fixo**, só confrontos diferentes |
| TikTok | 10/dia, mesma fila do YouTube | 6/dia de dia (`HORAS_DO_TIKTOK`), fila própria | **1–3/dia** |

Dados para escolher horário (análise de 20/10): no YouTube de builds **nenhum horário se
destaca** (diferenças dentro do acaso). No TikTok, blocos depois de 22 h+ sem postar deram certo
6/6; depois de 5–10 h, 4/33 → poucos posts, espaçados. O Orbitality posta 3/dia em horário fixo
(05, 13 e 21 h UTC = 02, 10 e 18 h de Brasília).

## Aplicar o WIP + o ajuste ao plano (ordem segura)
1. Rebase de `integracao/publicacao-semana1` sobre `refactor/arquitetura` numa worktree; os 2 WIPs
   estão marcados "NÃO TESTADO" — leia o diff inteiro antes.
2. Torne injetáveis a hora e o ledger que a recuperação/reserva do TikTok leem (foi o que quebrou
   10 testes de histórias na árvore principal).
3. Ajuste ao plano (grade do canal de duelos) com teste do caso zero e da semana simulada
   (o WIP tem uma: 70 no YouTube, 42 no TikTok, nenhuma fora de ordem, nenhuma repetida).
4. Suítes da árvore principal com a worktree à frente (mecânica na skill `integrador-aplicar-entrega`):
   `random_builds/tests`, `historias/tests` (a publicação mora em testes de lá:
   `test_postar_ver_saida_regressions.py`, `test_divida_dos_builds_regressions.py`…), `remoto`,
   `coordenador`, em 3 horários.
5. `python ferramentas/postar.py --ver --so builds` UMA vez com o código novo (diz o que postaria
   e sai; decodifica mp4 e escreve no `atividade.jsonl`, por isso só uma vez).
6. Aplicar fora da janela; as tarefas `NeuralFights_postar_HH` só mudam com `--instalar`, que é do
   orquestrador com o OK do Adrian.
