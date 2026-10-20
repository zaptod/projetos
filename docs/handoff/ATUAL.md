# Passagem de bastão — 20/10/2026 01:57 (renovacao)

Leia ANTES de agir. A NOTA é do chat anterior; o RETRATO é medido agora do disco.
Regras de operação: `CLAUDE.md`. Equipe: `docs/agentes/EQUIPE.md`.

# NOTA do chat anterior

# NOTA do chat anterior

Chat de 14/10 → 20/10/2026 ~02h (orquestrador), renovado a pedido do Adrian: "quero que comece hoje, vamos assumir de outro chat, quero seguir apenas esse plano."

## OBJETIVO ÚNICO — leia primeiro
**`docs/PLANO.md`** (CLAUDE.md §0, Grimório `geral/objetivo-unico-neural-fights`, memória `objetivo-unico-plano-30-dias`): fazer o canal de DUELOS do Neural Fights crescer de 20/10 a 19/11 — 3.000 views/dia, 150 inscritos, 1 vídeo >100 mil. UMA mudança medida por semana. Pesquisa em `docs/pesquisa/shorts-que-deram-certo.md` (espelho: Orbitality, duelo de bolinhas em Python, 47,9 mil inscritos em 7 meses) e `docs/pesquisa/ferramentas-de-video.md` (HyperFrames + Remotion). O Adrian disse que estava gastando token à toa por falta de objetivo: **nada fora do plano sem ele pedir.**

## Em andamento — terminar PRIMEIRO (semana 1 do plano, começa HOJE 20/10)
1. **Semana 1 — só texto, sem mexer no motor:** títulos "Arma/Classe VS Arma/Classe — quem vence?" (hoje são nomes inventados: "Drusila Vyrhordan x Sigrid Brasbalmirn"), faixa fixa no topo com os dois nomes nas cores dos lutadores (o HUD já está na zona segura: 434c553/aafd8f0/305b994), pergunta escrita no 1º segundo, luta já no quadro 0. Onde: títulos/copy em random_builds (memória `tom-das-copys-dos-videos`), renderer `random_builds/builds/video/renderer.py`. Conferente antes de ir ao ar.
2. **Publicação da semana 1 — YouTube 3/dia em horário fixo, TikTok 1–3/dia.** Há WIPs prontos que mudam a grade e precisam ser AJUSTADOS ao plano (eram 10 YouTube + 6 TikTok):
   - ramo `worktree-agent-a2c31810ad6750ff2` (bab6d817 + WIP 13e8d819 + WIP b4f8decd, NÃO TESTADO): TikTok com fila própria, duelo no lugar da estreia no YouTube, noite das histórias + parte seguinte. Foi aplicado e REVERTIDO (f2a64886) porque a recuperação/reserva do TikTok lê o relógio e o ledger REAIS → 10 testes de historias vermelhos na árvore principal. Falta: tornar a checagem de grade injetável, rodar as suítes da árvore principal com o código do ramo à frente no PYTHONPATH em 3 horários, ajustar `testes` no config (o teste 20–26/10 não começou).
   - ramo `worktree-agent-a832b969b7de13af8` a346e118 (geração por formato, mais duelos): REVERTIDO (564b92cb) porque depende do item acima. Aplicar JUNTO, rebaseado.
   - Atenção: a grade do plano (YouTube 3/dia) é diferente das duas. Decidir com os números: menos posts e só confrontos diferentes.
3. **Com o Adrian (pedir logo):** abrir o TikTok Studio e ver se os vídeos estão "elegíveis para recomendação" (8–15 views/dia sugere bloqueio); conferir no YouTube Studio as views reais por dia (o canal tinha 27.605 views no total em 20/10 — "1.100/dia" da análise era pico).

## Conferir ao abrir (do retrato de 20/10 ~02h)
- **Vila parada** no coordenador: veio do commit `a6f02e20` ("vila: fechada FICA fechada; Vila.exe e atalho para reabrir"), que um agente fez DIRETO na árvore principal, sem conferente. Confira se ela parou porque o Adrian fechou (comportamento novo) ou se quebrou; ver o diff e o atalho.
- **Bot com código velho:** `python -m coordenador reiniciar bot` fora da janela das postagens.
- Commits que não passaram por mim: `a6f02e20` (Vila), `0629831e` (Blue Lock, "a main mudou — só documentação") e `826efc3d` (assinatura da Vila). Revisar os três.

## Parado (fora do plano — NÃO retomar sem o Adrian pedir)
- Formatos do Blue Lock (ramo `worktree-agent-a5bf20c8a149fe832`, 640e572 + WIP d542b2a7; só drible-do-bachira aprovado; relatório `E:\tmp_pytest\conferente\bluelock2\RELATORIO_onda1_v2.md`).
- Casinha do Blue Lock (ramo `worktree-agent-a53d8bfb4c1aa0cd3`, 472d1107 + WIP 942404b6; app aprovado, PC com 4 defeitos).
- Mudança completa para o PC `am` (ramo `worktree-agent-a17b6b10f3f33e011`, 3a1e3f8e + 31ac8a16 testados + WIP 4b35781c; chaves DESLIGADAS). No plano o am só produz duelos (mecanismo `python -m builds.pc_am`, doc docs/sessoes/pc-am.md).
- Decididas e não feitas: builds/madrugada-na-transicao (desligar), builds/voz-do-windows-12-a-19-10 (refazer voz das 51 roletas só se forem publicadas).

## No ar (feito neste chat)
App v72/v73 (sem dado velho com o PC fora; alarme da Mesa no Telegram), HUD do duelo na zona segura + câmera da luta, fim do vídeo de luta (cauda pós-K.O.), Análise dos vídeos (Biblioteca do app, diária 07:02), Blue Lock integrado (espelho só leitura, vigia da main e de TODOS os ramos a cada 30 min, atalho "Blue Lock — versões" na Área de Trabalho), fsync da Mesa (b1f65ad) e Mesa restaurada, edge-tts 7.3.1 (voz voltou; estava 403 desde 12/10), navegador automático fora da tela (88dd912), CI verde, PC `am` provisionado (Python 3.14.4, Git, Node 24, ffmpeg em C:\nf).

## Decisões e regras novas (viraram memória)
- `adrian-nao-quer-decidir`: o orquestrador escolhe a recomendada, registra já respondida no Grimório e executa.
- `objetivo-unico-plano-30-dias`, `pc-am-trabalhador`, `blue-lock-integrado`, `mesa-zerada-na-queda`, `voz-403-edge-tts`.
- Tela do PC principal: **1280x720 lógicos, 680 úteis** (memória `painel-ui-reativo` corrigida).
- O merge no repositório do Blue Lock é do Adrian (o modo automático nega PATCH/push); o vigia só manda o comando. Vale o merge do `fix/isagi-off-ball-20261020` (1770/1770 testes, CI verde).

## Armadilhas encontradas
- **Teste verde na worktree ≠ verde na árvore principal** quando o código lê relógio/ledger/estado REAIS (publicação revertida 2×). Rode as suítes da árvore principal com o código da worktree à frente, antes de aplicar.
- **Falhas silenciosas por dias:** Mesa zerada (16→19/10), voz 403 (12→19/10). Procure erro repetido no log, não só o último.
- **Agentes não podem commitar na árvore principal** (houve 826efc3d direto). Nem matar Chrome que não abriram (um agente matou ~35 em 19/10 11:05).
- **SSH no am:** usuário `alvo`, shell padrão CMD; PowerShell via `-EncodedCommand`. Testes de janela Tk falham lá sem sessão de desktop.
- **4+ agentes ao mesmo tempo** passa do limite dele (3) e bate no teto de uso; renove o chat antes.

# RETRATO (medido agora)

## Git
- ramo: `refactor/arquitetura`
- **mudanças NÃO commitadas (4)** — confira antes de qualquer coisa:
  - `M docs/handoff/ATUAL.md`
  - `M docs/handoff/NOTA.md`
  - `M palco/biblioteca/LICENCAS.md`
  - `M palco/biblioteca/efeitos/objetos/projetil/fogo.tscn`
- últimos commits:
  - f659ce76 plano unico (20/10 a 19/11): Neural Fights crescer — 3.000 views/dia, 150 inscritos, 1 video >100 mil; pesquisa dos Shorts que deram certo (Orbitality, Earclacks...) e das ferramentas de video (HyperFrames/Remotion); CLAUDE.md §0 aponta o objetivo
  - f252f026 decisão(geral): lida — Objetivo único por 30 dias: Neural Fights crescer gerou nada
  - bb42ed67 decisão(geral): Objetivo único por 30 dias: Neural Fights crescer → Seguir só o docs/PLANO.md: duelos do Neural Fights, 3.000 views/dia, 150 inscritos, 1 vídeo >100 mil, uma mudança medida por semana
  - 826efc3d vila: a assinatura do servico nao pega mais os filhos (previsao, guia)
  - cc7bbac1 Blue Lock: janela de versões refeita para a tela dele (1280x680) e CI sem rede não vira "vale"
  - acae1290 Blue Lock: vigia dos ramos (vale o merge?) e lançador de versões do jogo
  - a6f02e20 vila: fechada FICA fechada; Vila.exe e atalho para reabrir
  - 0629831e Blue Lock: a main mudou — só documentação, sem testes
  - 564b92cb Revert "geracao (builds): meta POR FORMATO em vez do total do canal; duelo primeiro no caso zero; estreia so vira video abaixo da meta; nada pesado com o LoL aberto; folga 18/18; quem derruba a gravacao sai do rodizio"
  - c97d157f decisão(builds): lida — Vídeos narrados com a voz do Windows (12 a 19/10) gerou nada
  - 386bd83d decisão(builds): lida — Desligar a geração da madrugada (madrugada_na_transicao) gerou nada
  - ba9c45eb decisão(builds): Vídeos narrados com a voz do Windows (12 a 19/10) → Refazer a voz só do que ainda não foi publicado; o que já foi ao ar fica (recomendado)

## Pedidos e trabalhadores
- pedido-e72192db | Auditoria profunda: Publicação das histórias, grade e c | cancelado | pedido-e72192db-1 | fatia passada ao Claude (Codex no teto da janela ate 18:31)
- pedido-9b1a4245 | Auditoria profunda: Publicação dos builds | cancelado | pedido-9b1a4245-1 | fatia passada ao Claude (Codex no teto da janela ate 18:31)
- pedido-64c2bbee | Auditoria profunda: postar.py (a rodada de publicação) | cancelado | pedido-64c2bbee | fatia passada ao Claude (Codex no teto da janela ate 18:31)
- serviços: código velho em bot

## Mesa, fila e Grimório
- agentes ativos na Mesa: ninguém trabalhando
- fila (0):
- Grimório: todas as respostas lidas

## Serviços e máquina
- coordenador: pid 6240, código f659ce76
  - app: rodando
  - bot: rodando (código velho)
  - carteiro: rodando
  - vila: parado
- Claude: Claude liberado desde 18/10 19:59 por orquestrador, a pedido do Adrian
