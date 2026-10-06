Chat de 02–05/10/2026 (orquestrador). Encerrado por ser longo: passou de várias compactações. Fechou a VARREDURA DE ERROS de 05/10 e o "pedido honesto" do servidor.

## Em andamento — terminar PRIMEIRO
1. **Conferir a primeira noite com o código novo (06/10 de manhã), só leitura:**
   - **Histórias:**
     - a madrugada CRIOU história nova? Antes, o freio contava 58 retidas como estoque e não criava nada desde 03/10 (corrigido em d0e2dfd + 6a18d94).
     - Comando: `python -X utf8 ferramentas/postar.py --ver` mostra a gordura de histórias acima de 1.
     - Log: `historias/outputs/_logs/auto_20261006.txt` deve dizer "N publicável(eis)", não "60 novos na fila".
   - **Conferência:**
     - 10/10 nos dois canais e nos dois destinos;
     - SEM o alarme falso "noite sem conferência" (dabfbd0).
   - **Carteiro:** nenhuma imagem gerada duas vezes. No `outputs/carteiro.txt` aparecem as linhas "ficou entregue enquanto eu esperava a conta" (10be64d).
   - **Builds:** as junções de 00090, 00095 e 00098 saíram da fila `failed` (2664b7c).
2. **`postar.py --ver` termina com código 1** mesmo mostrando o retrato inteiro (visto na prova de 05/10 21h). Investigar com o agente `publicacao`.
3. **Pedidos do servidor ainda parados:**
   - `pedido-cb44cd52` (ligar o gerente): falhou porque o Codex não grava no LOCALAPPDATA. O caminho certo agora é o Adrian tocar na caixinha "gerente ligado" (Agora > Equipe), que foi consertada em ec8b196 e salva no toque. Também serve uma resposta nova no nó `geral/gerente-ligado`, que tem `acao_servidor`. O config real continua `gerente_ligado=false`.
   - `pedido-cd2e5e0c` (arquivo no Drive): esperando o Adrian abrir o Google Drive para computador, entrar na conta de 5 TB e confirmar que `G:\Meu Drive` existe. Depois disso, construir o arquivador: publicado há mais de 3 dias vai para `G:\Meu Drive\neural-fights-arquivo`, com um ponteiro no ledger.
   - `pedido-7c727778` (digen-parede = "deixar em espera", marcar os 13 testes como skip): a última olhada mostrava "permissão espera Adrian" (pedido-7c727778-1). Ver em Agora > Equipe > Pedidos de permissão.
4. **Entrega parada `pedido-fc098cab`** (consertada-primeiro, nascida do nó reolhar-depois-do-conserto):
   - Estado: "PRECISA DE OLHO", com conflito em `ferramentas/postar.py`.
   - O grupo A da varredura (6a18d94) já pôs a parte consertada na frente das retidas, e o Adrian decidiu "Não" na nova olhada. Provavelmente está obsoleta.
   - O que fazer: o `integrador` compara com o HEAD, aproveita só o que faltar (com teste) ou descarta, e roda `python -m remoto.delegar limpar --id pedido-fc098cab`.
   - O commit `dcb152e` (vigia antigo, mensagem com a fala do agente "Não commitei…") veio dessa linha: conferir `git show --stat dcb152e`.
   - Também limpar `pedido-a9e9cd15` (a prova, que não tem código) e `pedido-cb44cd52-1`.
5. **Mesa:** o item "16:06 Picasso: o despachante caía… cp1252" ainda aparece como ativo, mas já foi resolvido em e676e95. Feche com `python -m remoto.orquestrador agente-fim <id>` (pegue o id com `python -m remoto.orquestrador status`).
6. **Capas atrasadas das histórias:** 100 de 225 subiram em 05/10. A tarefa `NeuralFights_capas_atrasadas` (03:10) sobe 60 por dia e para no 429 "too many thumbnails". Conferir `historias/outputs/_publicar/_capas_atrasadas.json`.

## Pedidos do Adrian ainda abertos
- **"Só confio neste chat":** a prova de ponta a ponta passou em 05/10 20:58. O `pedido-a9e9cd15` entrou pelo caminho do app → servidor → trabalhador Claude → "DESFECHO: feito" em 1 min, com a resposta igual à medida. Próximo passo: ele usar o 📝 Pedir no celular para coisas reais. O chat novo acompanha as primeiras e confere cada resposta (o servidor agora só marca "entregue" com DESFECHO feito).
- **Histórias:** "quero melhorar o fluxo das histórias, mas para isso preciso de uma visualização melhor de todo o macro do processo". A página do fluxo de PEDIDOS existe (Biblioteca > Fluxo, 9989b80), mas a visão macro das HISTÓRIAS (roteiro → imagens → narração → render → vistoria → estoque → publicação, com contagens) ainda não foi feita. Mostrar a ele antes de construir.
- **Estoque de histórias em 1 vídeo:** 57 partes retidas, das quais 38 consertadas. Ele decidiu "Não, manter uma passada só" (`historias/reolhar-depois-do-conserto`), então elas só saem quando o horário ficaria vazio. A saída é a fábrica voltar a criar (item 1) e a qualidade na origem: o elenco agora tem gênero (d0e2dfd), e 23% dos vetos eram por pessoa ou gênero errado.
- **Launcher:** ainda falta conferir na tela os ícones do menu, os botões da Arena e a prévia do lutador (`scratchpad/foto_launcher.py`).

## Decisões e regras novas deste chat
- **Grimório:**
  - `historias/reolhar-depois-do-conserto` = NÃO (uma passada só);
  - `builds/digen-parede` = deixar em espera (skip);
  - `geral/gerente-ligado` = Ligar (ainda não aplicado, ver item 3).
- **Pedido honesto (c77b53b), regras fixas sem adivinhar pelo texto:**
  - DESFECHO na última linha; sem ela, uma cobrança e depois "esperando você";
  - o estado do servidor (gerente, renovação, paralelo) muda SÓ por `acao_servidor` estruturada no nó do Grimório ou por permissão `estado_do_servidor` aprovada na Equipe;
  - a continuação só é EXPLÍCITA: botão Responder ou `/responder <id>`;
  - conversa solta por lista fixa (saudação, status, agradecimento).
- **Conferente é só leitura.** O vigia nunca aplica nem commita entrega de conferente (e676e95).
- **Capa de histórias:** o canal historinhas foi verificado em 05/10 e a capa entra. Existe um limite próprio de cerca de 100 capas por dia (429).
- **Este PC (i5 com 4 núcleos):** um workflow roda no máximo 2 agentes de uma vez.

## Armadilhas encontradas
- **"Entregue" mentia:** o servidor marcava entregue com resposta "Não foi possível". Agora vale a linha DESFECHO. Ao conferir um pedido, leia a RESPOSTA, não a situação.
- **O Codex em worktree não grava em `%LOCALAPPDATA%`:** config e permissões são só pelo servidor ou pelo app.
- **Heurística de texto para intenção fura sempre:** 18 nós reais do Grimório autorizavam a ação errada, e "Deixar desligado" ligava. Use campo estruturado.
- **O coordenador reiniciou sozinho às 18:40 no meio da edição da v2** e rodou código pela metade. Para reiniciar com o código final: `schtasks /End /TN NeuralFights_coordenador` e depois `schtasks /Run /TN NeuralFights_coordenador`. Só o `/Run` diz "já em execução" e não faz nada.
- **Recargas automáticas desfazem formulários** (caixinha do gerente). Campo editado fica "sujo" até salvar.
- **Agentes podem ter sido barrados pelo classificador** em `git diff` e em mudanças de config. Quando uma ação é negada, ela vai para o Adrian; não contorne.
- Continuam valendo: heredoc em Python (use Write/Edit), commit sempre por caminho, `ruff --fix` apaga fixture, testes de tempo instáveis com a máquina carregada.
