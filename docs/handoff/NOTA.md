# NOTA do chat anterior

Chat de 20/10 02h → 21/10 ~11h (orquestrador). Parado a pedido do Adrian: "pare em um local seguro". Nada pela metade na árvore principal; os três trabalhos abertos estão em worktrees com commit WIP.

## OBJETIVO ÚNICO
`docs/PLANO.md` (canal de DUELOS do Neural Fights, 20/10→19/11: 3.000 views/dia, 150 inscritos, 1 vídeo >100 mil). Nada fora do plano sem o Adrian pedir. "Tudo"/"cada setor" = só as partes dos duelos (memória `pedido-vale-so-para-o-objetivo`).

## No ar (semana 1 do plano, desde 20/10)
- Canal de duelos em INGLÊS (decisão `geral/canal-em-ingles`): título "X VS Y — who wins?", faixa no topo nas cores (= cor do corpo, 23e3587e), WHO WINS? + voz en-US no quadro 0, cartão "X WIN(S)!", duelo < 15 s fora da fila (b529b242).
- Grade (bd1140aa, decisão `publicacao/grade-semana-1-duelos`): builds YouTube 09:37/17:57/21:37, TikTok 21:37, só duelo, idioma "en" no upload; troca sozinha em 01/11 para 12:07/20:37/22:37. Histórias seguem 10+6.
- Estoque regravado em inglês e com a cor certa; fila ~31 duelos (~10 dias). 20/10: os 3 saíram e o TikTok (96 views em 10 h, antigos ~1,5).
- 19 skills em `.claude/skills/` (12 da casa + 7 de fora), agentes pré-carregam pelo campo `skills:`.

## Em andamento — terminar PRIMEIRO
1. **Duelo das 09:37 de 21/10 NÃO publicou** (duelo_00132, "YouTubeWebFalhou: a tela de detalhes nao apareceu" em outputs/postar.txt ~09:45; fora do ledger e do a_conferir). Worktree `E:\projetos-wt\pub-0937`, ramo `publicacao/falha-0937`, WIP 6bb533ab NÃO TESTADO (youtube_web.py + teste test_detalhes_nao_vieram_regressions.py). FALTA: (a) ver pela Data API se ficou RASCUNHO órfão no canal (risco de duplicata); (b) por que foi pelo navegador e não pela API oficial; (c) ver se 17:57/21:37 de 21/10 saíram (`publicacao-conferir-ledger`); (d) testar, conferente, integrador.
2. **Coletor que mede sozinho** — `E:\projetos-wt\metricas-coletor`, ramo `metricas/coletor-sozinho`, b511f54a + 337d022d. Autor: 8301 testes verdes. Conferente foi PARADO no meio (não aprovou ainda). FALTA: conferente (página pagina_analise.html a 390x844, caso zero, diff de hora_a_hora.py no noite.rodar), integrador, `coordenador reiniciar bot` (para /semana), pôr `"semana": "21:05"` nos relatórios padrão de `remoto/config.py` (decisão `metricas/semana-no-telegram` = diário 21:05), atualizar a linha do PLANO que diz que o coletor não guarda. TikTok do coletor nunca rodou no Studio real: conferir o 1º arquivo cru.
3. **Lutas sem ficar colado** (pedido do Adrian 21/10) — `E:\projetos-wt\motor-dinamismo`, ramo `builds/motor-dinamismo`, WIP 3d17fb3c NÃO TESTADO (neural_fights/core/dinamismo.py "respiro + reengajamento", tools/dinamismo_luta.py, simulacao.py, recorder, runner…). FALTA tudo da prova: medir ANTES × DEPOIS no mesmo lote de 60 lutas (maior trecho colado ≤1,5 s mediana/≤3 s pior; tempo colado −50%; nenhuma >90 s; vitórias por classe sem mudar >10 pontos), testes, 3 vídeos de prova, conferente. Aviso: mudar o motor faz duelos antigos não se reproduzirem (já aconteceu com 14/10).

## Próximos do plano
- Medida da semana 1: fecha ~27–30/10 (Analytics atrasa 2–3 dias; rx3XnuU3rJw maduro em 23/10). Primeira leitura 21/10: novo 4–17x os antigos na mesma idade, INCERTO (n=3, formato + menos posts juntos).
- Semana 2 (`docs/pesquisa/som-ganchos-e-musica.md`): tirar a música de baixo da luta, silêncio antes do golpe final, K.O. mais alto e corte 1 s depois; câmera parada; 45–58 s.
- Menores registrados: cartel/camera fora da zona segura (sem. 2), capa horizontal, rótulo do plano tapado pela lâmina, nome pequeno sobre o lutador azul/vermelho em vez da cor; furos da varredura de português (`+=`, ramo if) — `random_builds/tests/test_ingles_do_duelo_regressions.py`.

## Pedidos do Adrian ainda abertos
- "quero que você altere na ia ou nas mecanicas, para que não aconteçam essas situaçoes onde os personagens ficam colados um no outro muito tempo, quero movimento e dinamismo nas lutas." (item 3; ele aceitou a versão completa, 2–3 h).

## Decisões e regras novas (viraram memória/Grimório)
- Memórias: `medir-sozinho-nao-perguntar` (métrica é o agente metricas que mede, nunca pedir ao Adrian), `pedido-vale-so-para-o-objetivo`, `um-projeto-por-vez` atualizada: LIMITE DE AGENTES REVOGADO ("PODE PASSAR DESSA PORRA DESSE LIMITE").
- Grimório: geral/canal-em-ingles, publicacao/grade-semana-1-duelos, builds/estoque-duelos-em-ingles, builds/regravar-com-motor-novo, metricas/semana-no-telegram.

## Armadilhas encontradas
- **Isolamento de worktree recusou** ("core.worktree redirect") quando o diretório veio como `e:\projetos` minúsculo; criar à mão: `git worktree add E:\projetos-wt\<nome> -b <ramo> refactor/arquitetura` e mandar o agente trabalhar SÓ lá. Sobrou `.claude/worktrees/agent-ac866c6f349dea304` travada (locked, base 3e5e2a4c) — limpar.
- Worktrees de agente nascem do `main` velho (3e5e2a4c): mandar alinhar com refactor/arquitetura antes.
- `.gitignore` ignorava `.claude/*`: exceção `!.claude/skills/` posta (bc7a1eaf).
- PowerShell 5.1: `git diff > arquivo` grava UTF-16 e o apply recusa; patches pelo Bash.
- Lutas gravadas antes de 14/10 não se reproduzem no motor atual (mesmo vencedor/K.O., outra duração/HP). Regravar muda a ordem da fila (catálogo ordena pelo mtime do mp4).
- Regravar sem contar luta de novo: script no scratchpad (`regravar_duelo.py`/`regravar_cor.py`: FightSession.gerar + _entregar_duelo, sem ledger.registrar).
- Medida de voz pelo "gêmeo mudo" é inválida (subestima); usar a do conferente (~+23 dB).
- O retrato acusa horários "VAZIOS" de builds por medir pela grade da plataforma (10/6), não a do canal (3/1): alarme falso.
- Uma história de 20/10 23:37 (historia_00085 p01, B_lmtyXdHkY) ficou PRIVADA no canal com o ledger dizendo pública — fora do plano, não mexido.
