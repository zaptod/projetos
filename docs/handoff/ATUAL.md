# Passagem de bastão — 05/10/2026 21:00 (renovacao)

Leia ANTES de agir. A NOTA é do chat anterior; o RETRATO é medido agora do disco.
Regras de operação: `CLAUDE.md`. Equipe: `docs/agentes/EQUIPE.md`.

# NOTA do chat anterior

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

# RETRATO (medido agora)

## Git
- ramo: `refactor/arquitetura`
- **mudanças NÃO commitadas (4)** — confira antes de qualquer coisa:
  - `M docs/handoff/ATUAL.md`
  - `M docs/handoff/NOTA.md`
  - `M palco/biblioteca/LICENCAS.md`
  - `M palco/biblioteca/efeitos/objetos/projetil/fogo.tscn`
- últimos commits:
  - c77b53b coordenador: pedido honesto v2 — regras fixas no lugar de adivinhar pelo texto: DESFECHO so na ultima linha (sem ela, UMA cobranca ao mesmo trabalhador com a resposta original no continuacao.md; a resposta final ao Adrian e a ORIGINAL com o desfecho depois), estado do servidor (gerente/renovacao/paralelo) so pela opcao estruturada do Grimorio (acao_servidor em decisoes/geral/gerente-ligado.json) ou por permissao estado_do_servidor aprovada em Agora > Equipe, continuacao so EXPLICITA (Responder do cartao, /responder <id> no Telegram; texto livre abre pedido novo), Responder em pedido de trabalhador limpo contrata UM trabalhador novo com a historia (recusado = falhou com o motivo, nunca "recusado:" por pulso), texto do servidor em pedido['do_servidor'] (fora do texto e da escolha da IA), conversa solta por LISTA FIXA comparada inteira (saudacao, status, agradecimento; CURTO_MAX_PALAVRAS removido), trava de arquivo entre processos no pedidos.json com o lento fora dela (reserva "contratando" + dono), pagina Fluxo e casca v44 — medido em 05/10: suite coordenador+remoto verde, tela no Chrome (test_app_tela/vila_objetos/fluxo) 34 passed sem worktree nova; sonda de trava num clone isolado: 5 contratos num pulso de 28 s com a trava presa no maximo 0,01 s e registrar concorrente de outro processo em no maximo 0,80 s (26 chamadas, 0 erro; 2,59 s no pior caso com chamadas a cada 0,2 s); sondas do conferente test_h2r3_logica 58/65, as 7 vermelhas sao as que pedem o "curto" por contagem que a regra 4 removeu; mutacoes da rodada 4/4 derrubadas
  - f176f12 A entrega pedido-cb44cd52-1 não tinha nenhum código para integrar. Consertei o vigia para que esse travamento não se rep (feito pelo Codex, validado pelo vigia)
  - 9989b80 varredura 05/10 (app): celular que fecha a conexao vira uma linha "saiu" (CLIENTE_SAIU no _json/_bytes/_erro, do_GET/do_POST em casca, handle_error cala so ele), bandeja do Tailscale aberta pelo explorer e "nao sei" so depois de 3 olhadas sem resposta, aba Fluxo na Biblioteca com o caminho de um pedido guardada por test_app_fluxo (validador so recusa a entrega vazia; momento seguro e so "sem publicacao em voo"), casca v43 — medido no app_celular.txt: 221 linhas de ConnectionAbortedError/Reset/BrokenPipe e 124 blocos de traceback, cada um "200" seguido de "500"; prova isolada na 8977 com 30 clientes em RST e 5 cortados antes do pedido: 28 "saiu", 0 Traceback, 0 500; tailscale-ipn.exe era filho do bot e morria a cada religada (5 NoState em 03/10, 5 em 04/10) e os 4 "fora do tailnet" das 23:00-00:06 eram o status travado; o conferente pegou 2 frases falsas na pagina (copiadas de docstring velha) e os 2 testes novos falham contra elas — remoto 900 testes verdes, Fluxo no Chrome 390x844 claro e escuro, mutacoes: item 22 6/6, vigia 10/32, Fluxo 2/2
  - faf4938 coordenador: pedido honesto — DESFECHO na ultima linha (feito/bloqueado/falhou; sem ela, frase de bloqueio so na abertura ou na forma de estado; com codigo vira "entregue com aviso"; "feito" desmentido pelo texto e sem codigo espera voce), acoes de estado do servidor pelo proprio servidor (gerente/renovacao/paralelo) so na ultima linha e so se o Adrian citou o objeto, conversa solta responde o retrato, pedido novo nao gruda em entregue/esperando voce, ficha "rodando" de pid morto retoma em vez de girar — medido em 05/10: cb44cd52 e cd2e5e0c estavam "entregue" com "Nao foi possivel ligar"/"bloqueado so pelo login do Drive" (reavaliados para esperando_voce); nas 60 respostas reais de delegados a regra nova da 0 falso bloqueio nas 4 entregas boas que a anterior travava e mantem os 5 bloqueios de verdade; o contexto do no do cb44 citava "paralelo" e nao autoriza mais; o 7c727778 girava a cada ~6 s com o pid 11412 morto (393 de 400 linhas da conversa) — 256 testes do coordenador e 150 do remoto verdes, 10 mutacoes derrubadas
  - e676e95 varredura 05/10 (coord-despachante): _log a prova de cp1252 e repo principal por --git-common-dir, conferente read-only que so registra veredito, "nao mudou nada" vira nada a aplicar, faxina de olho/corrigidos/delegados, arvore suja e trava ocupada esperam (avisam uma vez, aplicam sozinhas quando limpa), commit com no/arquivos e o que o vigia mediu, supervisor ignora teste e poupa a bandeja do Tailscale, testar com trava e pasta por rodada, reteste por falha de ambiente, rascunhos fora do indice — 266 testes da parte e 873 do remoto verdes, 4 mutacoes derrubadas
  - dabfbd0 varredura 05/10 (metricas): conferencia do dia cobrada pela origem da rodada (servico/painel/manual) e pelo 1o disparo da agenda + 3 h, nao mais por rodada antes das 06:37 — alarme "noite sem conferencia" saia todo dia de 02 a 05/10 nos dois canais com a conferencia rodando as 07:04-07:35
  - 10be64d varredura 05/10 (ias): pedido do worker reservado e reivindicar atomico, recuperacao do Chrome com 21 leituras, casa so com conversa e resumo validado, colagem refeita pelo correio; conferencia: reserva separada de quem entrega, espera da conta rele o pedido, toda falha por _falhar, queda do Chrome repete o mesmo gerador — desde 02/10 36/173 imagens do PicassoIA, 12/178 do Gemini e 6/166 do ChatGPT geradas 2x, 5 respondidas viraram falhou, 5 de 5 recuperacoes falharam
  - e9ab8f5 varredura 05/10 (coord-limite): limite do Claude sem queimar retomada, Grimorio retoma o mesmo pedido, EXECUTAR por lista branca, integrador/gerente no Codex acima do teto — 206 testes do coordenador verdes, 7 mutacoes derrubadas
  - 2664b7c varredura 05/10 (builds): juncao so com as duas imagens no disco, failed reabrivel volta (e chama o worker sozinho), parede de planos pausa sem queimar tentativa, falhas do worker no resumo da noite, poda do diario por idade e prioridade, recentes(n) de tras para frente — 3 juncoes e 2 imagens presas medidas na fila
  - dcb152e A entrega pedido-fc098cab está aplicada e com a suíte verde nesta worktree. Não commitei, como manda a tarefa: as mudanç (feito pelo Codex, validado pelo vigia)
  - 6a18d94 varredura 05/10 (publicacao): estoque sem -1 por log, consertada retida na frente, reposicao por rede, marca so onde saiu, legenda com pausa, capa bloqueada por conta, rodape do Studio — 37 de 57 retidas consertadas, 151 capas 403 contra 34, 13 estagios ilegiveis
  - d0e2dfd varredura 05/10 (historias): parte consertada reconhecida, plano B do estoque sem retidas, recusa enlatada no roteiro, genero no elenco — 37 de 57 retidas ja consertadas, 23% dos vetos eram pessoa/genero errado

## Trabalhadores do servidor (delegados)
- `pedido-a9e9cd15`: orquestrador / claude / terminou (PROVA DE PONTA A PONTA (05/10, pedida pelo orquestrador para conferir o servidor) — terminou e NÃO foi aplicado
- `pedido-7c727778-1`: orquestrador / codex / aguardando_permissao (O Adrian respondeu no Grimório (builds/digen-parede): «Parede de planos do Digen)
- `pedido-cb44cd52-1`: orquestrador / codex / terminou (O Adrian respondeu no Grimório (geral/gerente-ligado): «Ligar o gerente da equip) — terminou e NÃO foi aplicado
- `pedido-fc098cab`: orquestrador / claude / terminou (O Adrian respondeu no Grimório (historias/reolhar-depois-do-conserto): «IA olha ) — **PRECISA DE OLHO**: aplicar recusou: conflito de merge em: ferramentas/postar.py

## Mesa, fila e Grimório
- agentes ativos na Mesa: 16:06  Picasso: o despachante caía ao imprimir a seta do cargo historias (cp1252); consertei _log em remoto/delegar.py c; ninguém trabalhando
- fila (1):
  - 1. 6a229e63  [builds] Corrente F4–F6: arte pela esteira, som e A/B (o rework que o Adrian pediu em palco-duelo-ab)
- Grimório: todas as respostas lidas

## Serviços e máquina
- coordenador: pid 7596, código c77b53b
  - app: rodando
  - bot: rodando
  - carteiro: rodando
  - vila: rodando
- Claude: Claude liberado desde 01/10 13:30 pelo app (Android)
