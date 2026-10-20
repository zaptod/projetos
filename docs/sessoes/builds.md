# Passagem: BUILDS / NEURAL FIGHTS

## Imagens de identidade pelo correio (06/10/2026)

`character`, `weapon` e a imagem intermediaria da juncao agora usam a caixa
`livre` de `ias`: o carteiro escolhe somente os geradores de
`ias/config.json:rodizio_imagem` (Gemini e ChatGPT hoje). O PicassoIA nao e
escolhido automaticamente. A juncao so pede quando as duas imagens existem no
disco e as envia como anexos; o correio exige a miniatura de cada anexo e a
prova de que a imagem entregue pertence ao nosso turno antes de copiar o
arquivo para a build.

So jobs VIVOS (pendentes ou rodando) com `provider: picasso` migram na leitura
para `correio`, sem criar outro job; done/failed ficam `picasso` (a 1a versao
migrava todos e o queue.json real teve 210 restaurados em 07/10). O id do
pedido fica gravado na fila antes de entrar no correio,
portanto uma retomada consulta a mesma mensagem e nao pede uma segunda imagem.
Pedido que falhou (ou cujo entregador morreu) nao e reaproveitado: a proxima
tentativa nasce com id novo; reenfileirar zera o id ("faca de novo" nunca
devolve a imagem antiga). Conta ocupada pelas historias ou rodizio sem
gerador em cota NAO gasta tentativa: o job volta para a fila e a passada para
(espera pela conta: `espera_conta_correio_s`, padrao 1800 s, nunca alem do
prazo da rodada). Pedido com anexo so vai a gerador que conversa no chat.

Conferencia de 07/10/2026 (reprovada e consertada):
- o worker poe a raiz do repositorio no sys.path ao ser importado (o gerar.cmd
  roda de `random_builds/`, onde `ias` nao era achado); `ias` que nao importa
  e AMBIENTE: a passada para, nada gasta tentativa, a falha vai ao resumo;
- o worker segura a trava da CONTA (Gemini/ChatGPT) antes de criar o pedido;
  conta ocupada nunca entra no correio (la virava `falhou`, `erro` no diario
  e alerta "0 h");
- a imagem e gravada como PNG de verdade (o Gemini baixa JPEG), com a
  proporcao conferida (3% de folga) e o detector de colagem das historias
  (`contos.imagens.composicao`);
- os rotulos de pendencia dizem "(correio das IAs)" e casam com
  `noite._PENDENCIA_DO_WORKER`.
O video `character_weapon` continua no Digen e espera a imagem da juncao.

O Picasso permanece pausado e nao precisa ser retomado. Para liberar os jobs
no novo caminho, use `python main.py identity retomar --provedor correio` se o
correio tiver sido pausado; para conferir primeiro, use
`python main.py identity status`.

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/builds/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (06/10/2026) · “06/10 10:00, pela Mesa de comando: paralelo, até 6 agentes — nas palavras dele: pedido do Adrian, executado pelo servidor” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Passou de 50%, para tudo; força total 20 min antes de renovar (29/09/2026) · “29/09 07:26, pela Mesa de comando: passou de 50% da sessão, para tudo” `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Só quando eu pedir (29/09/2026) · “29/09 13:28, pela Mesa de comando: força total só quando eu pedir” `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`
- ✅ **Limpeza do disco (C: com 9 GB livres)** — Só o seguro (~1,2 GB) (29/09/2026) `limpeza-do-disco`
- ✅ **E: com 17 GB livres — o cache do Google Drive (186 GB)** — Abrir o Google Drive e deixar ele terminar e limpar sozinho (recomendado primeiro) (29/09/2026) `limpeza-do-disco-e`
- ✅ **Grok: por onde entra na roda?** — grok.com com a sua conta X (gratuito; você loga uma vez) (29/09/2026) `ias-grok-acesso`
- ✅ **Quando você fala com uma IA e a pipeline precisa da mesma conta** — Você: a pipeline espera a sua conversa terminar (29/09/2026) `ias-prioridade-conversa`
- ✅ **Cada IA tem UM chat de longa duração ou um chat novo por assunto?** — Um chat 'casa' por IA, com resumo periódico (29/09/2026) `ias-chat-persistente`
- ✅ **Fichas das IAs (fase 1): li?** — Li; seguir para a fase 2 (falar com cada uma pelo app) (29/09/2026) `ias-fichas-lidas`
- ✅ **Rodízio de imagens: quem vem primeiro** — Gemini primeiro (29/09/2026) `rodizio-de-imagens-quem-vem-primeiro`
- ✅ **Digen no plano Free: o Real Motion 3.5 pede plano** — Tirar o Digen da roda e desligar o vídeo do payoff das builds (29/09/2026) `digen-plano-free`
- ✅ **Fila: tarefas pesadas podem rodar de dia?** — Rodar de dia, 2 em paralelo (30/09/2026) · “Atualmente prefiro que rode de dia, eu estou trabalhando durante o dia, e de madrugada quando tem esse trabalho pesado o Pc faz muito barulho, por isso prefiro que esse trabalho pesado aconteça de dia, mas tome cuidado para não quebrar o processo, achei uma boa forma de encaixar isso, o ideal seria processar nos horários vagos tendo uma gordura boa pra semana, um planejamento como segunda fazemos as histórias e biuds da semana toda e dps ficamos apenas para mudanças” `fila-pesada-de-dia`
- ✅ **Lote: janela do trabalho pesado de dia** — 07h às 22h (recomendado) (30/09/2026) `lote-janela-de-dia`
- ✅ **Lote: em quais dias produzir** — Histórias seg–qua, builds seg–ter (recomendado) (30/09/2026) `lote-dias`
- ✅ **Lote: vídeo de até 6 dias** — Aceito; mudança crítica ganha re-render (recomendado) (30/09/2026) `lote-frescor`
- ✅ **Lote: estoque zero de madrugada** — Libera tudo (30/09/2026) `lote-estoque-zero-de-madrugada`
- ✅ **Lote: piso de reposição (qui–dom)** — 2 dias = 20 vídeos (recomendado) (30/09/2026) `lote-piso-de-reposicao`
- ✅ **Lote: como trocar da madrugada para o dia** — Esquema de dia validado 1 dia antes de desligar a madrugada; 1º lote seg 05/10 (recomendado) (30/09/2026) `lote-transicao`
- ✅ **Sprites: o que o Grok decide sozinho** — Aconselha; aprova só depois de calibrado (recomendado) (30/09/2026) `sprites-ia-juiz`
- ✅ **Contas extras de IA: quais** — 4 ChatGPT Free (30/09/2026) · “Quero achar uma forma de fazer com que essas contas sejam diferentes aos olhos da open aí, ou mudar o IP quando fazer a requisição, qualquer coisa assim mas a minha ideia é, tenho vários email Outlook, crio várias contas free, giro entre elas mudando o IP de requisição e consigo gerar imagens infinitas” `contas-ia-extras`
- ✅ **Contas de IA: como alternar** — Por papel; transborda quando a cota estoura (recomendado) (30/09/2026) `contas-ia-rodizio`
- ✅ **Perfis de navegador: mudar para o E:?** — Mover para o E: (recomendado) (30/09/2026) `perfis-para-o-e`
- ✅ **Imagens em volume: qual caminho dentro das regras** — Contas extras suas, cada uma com papel próprio, sem disfarce (30/09/2026) `contas-ia-caminho`
- ✅ **Codex e Gemini: o que delegar primeiro** — Consertos com teste (recomendado) (01/10/2026) `delegar-o-que-primeiro`
- ✅ **Codex e Gemini: quem confere o trabalho** — Validador + agente barato (recomendado) (01/10/2026) `quem-confere-delegado`
- ✅ **Codex: commita ou só propõe** — Só propõe o diff (recomendado) (01/10/2026) `codex-commita`
- ✅ **Gemini CLI também, ou só o Codex?** — Os dois (recomendado) (01/10/2026) `gemini-cli-tambem`
- ✅ **Codex e Gemini: teto de uso** — 50% da janela de 5 h de cada (recomendado) (01/10/2026) `teto-dos-delegados`
- ✅ **Gemini: o CLI não aceita a conta pessoal** — Seguir com o Gemini no navegador (recomendado) (01/10/2026) `gemini-sem-cli`
- ✅ **Codex: quanto ele pensa** — Médio por padrão, alto nas difíceis (recomendado) (01/10/2026) `codex-esforco`
- ✅ **Vigia do coordenador: aplica entrega do Codex sozinho?** — Sim, aplica sozinho (02/10/2026) `vigia-aplica-sozinho`
- ✅ **Liberar espaço: arquivar os vídeos no Google Drive** — Google Drive para computador (recomendado) (04/10/2026) `arquivo-de-videos`
- ✅ **Ligar o gerente da equipe (a fila anda sozinha)?** — Ligar (recomendado) (04/10/2026) `gerente-ligado`
- ✅ **PicassoIA fora da roda de imagens** — Tirar o PicassoIA de vez (06/10/2026) · “06/10 pelo chat: 'aparentemente o picasso morreu tambem, não podemos mais contar com ele.'” `picasso-fora-da-roda`
- ✅ **Permissao: O pedido 'apaga tudo por favor' chegou sem dizer O QUE apaga** — Negar (06/10/2026) `permissao-o-pedido-apaga-tudo-por-favor`
- ✅ **Enviar o 2º vídeo se o TikTok falhar?** — Enviar mesmo assim (recomendado) (07/10/2026) `enviar-o-2o-video-se-o-tiktok-falhar`
- ✅ **Permissao: Ligar já o palco nos duelos sem corrente? Pergunta para o Ad** — Permitir (07/10/2026) `permissao-ligar-ja-o-palco-nos-duelos-se`
- ✅ **Internet do PC: trocar o DNS da operadora** — Cloudflare e Google (recomendado) (10/10/2026) · “10/10 ~01h pelo chat: 'sim eu quero pode marcar no grimorio de uma vez'” `dns-do-pc`
- ✅ **Limpar o lixo da máquina** — Apagar tudo isso (recomendado) (12/10/2026) `limpeza-da-maquina`
- ✅ **Auditoria profunda: gastar quanto do Codex?** — Continuar em esforço alto (recomendado) (13/10/2026) `auditoria-profunda-custo`
- ✅ **Um gerente só para app, bot e Vila** — Desligar as três e apagar a retomar_codex (recomendado) (13/10/2026) `gerente-unico-dos-servicos`
- ✅ **Reiniciar serviços sozinho quando o código muda?** — Só quando pedido: entrega aplicada ou comando reiniciar (recomendado) (13/10/2026) `reinicio-por-codigo-velho`
- ✅ **O ramo main está 945 commits atrás** — main recebe o ramo refactor/arquitetura (recomendado) (13/10/2026) `main-recebe-o-ramo`
- ✅ **Enviar o ramo ao GitHub (push)?** — Enviar main e refactor/arquitetura (recomendado) (13/10/2026) `enviar-ao-github`
- ✅ **Quando o PC religa** — Só um aviso 'o PC religou' quando você entrar (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `pc-religado`
- ✅ **Objetivo único por 30 dias: Neural Fights crescer** — Seguir só o docs/PLANO.md: duelos do Neural Fights, 3.000 views/dia, 150 inscritos, 1 vídeo >100 mil, uma mudança medida por semana (20/10/2026) · “Decisão do Adrian no chat, 20/10/2026: 'quero que comece hoje ... quero seguir apenas esse plano.'” `objetivo-unico-neural-fights`
- ✅ **Canal de duelos em inglês** — Só o que o público vê em inglês (20/10/2026) · “Escolhida pelo orquestrador (adrian-nao-quer-decidir)” `canal-em-ingles`

**Builds**
- ✅ **Variantes B** — Título próprio para cada uma (27/09/2026) `variantes-b`
- ✅ **Roleta automática de madrugada** — Sim (28/09/2026) `roleta-de-madrugada`
- ✅ **Estreia generation_00066 (muda)** — Descartar (28/09/2026) `estreia-00066`
- ✅ **Onda 16: ferramenta do visual** — Godot 4 (28/09/2026) `ferramenta-do-visual`
- ✅ **Visual do lutador** — Bolinha com arte (28/09/2026) `visual-do-lutador`
- ✅ **Origem da arte** — CC0 + IA, trocável (28/09/2026) `origem-da-arte`
- ✅ **Transição até o palco** — O visual atual segue, já com o som real (28/09/2026) `transicao`
- ✅ **Som real da luta (16A)** — Aprovar: re-render do estoque na madrugada (28/09/2026) `som-real-16a`
- ✅ **Palco: o visual novo (A/B)** — Seguir: próxima etapa é a arte (16E) (28/09/2026) `palco-seguir`
- ✅ **Chão da arena** — Foto de pedra CC0 escurecida (como está) (28/09/2026) `chao-da-arena`
- ✅ **Hitstop: a pausinha no impacto** — Ligar (28/09/2026) `hitstop`
- ✅ **generation_00077: luta muda, lutadores fora do banco** — Descartar, como a 00066 (28/09/2026) `generation-00077`
- ✅ **Sprites animados: como produzir** — Continuar com o modelo padrão e limpar depois (28/09/2026) · “Eu consegui gerar alguns spritesheet bons, veja o arquivo piriri.py , eu consegui esse usando o chat gpt, mas como o processo é moroso quero apenas uma interface gráfica que facilite ao máximo esse processo, como essa limpeza de fundo, saneamento e auto faturamento de frames, identificação e outras coisas úteis.” `sprites-animados`
- ✅ **Palco: A/B depois da arte (16E)** — Seguir: trocar o visual do duelo (16G) (28/09/2026) `palco-ab-2`
- ✅ **Palco: os números de dano na tela** — Não (29/09/2026) `palco-numeros-de-dano`
- ✅ **Esteira de sprites: por onde começa** — As duas frentes (30/09/2026) `sprites-ia-alvo`
- ✅ **Sprites: peça parada ou quadro a quadro?** — Peça + Godot; folha só no impacto (recomendado) (30/09/2026) `sprites-ia-formato`
- ✅ **Sprites: como manter o mesmo estilo** — Imagem-mestra aprovada por você (recomendado) (30/09/2026) `sprites-ia-estilo`
- ✅ **Sprites: fundo pedido ao ChatGPT** — Magenta liso (verde nos roxos) (recomendado) (30/09/2026) `sprites-ia-fundo`
- ✅ **Duelo: trocar o visual para o palco?** — Ajustar primeiro (diga o quê no comentário) (30/09/2026) · “A corrente a animaçao dela é muito feia, e suaecanica é idêntica a da espada, quero um rework completo nela mas de resto tudo está perfeito” `palco-duelo-ab`
- ✅ **Corrente: mecânica própria** — Bola física com momento (recomendado) (01/10/2026) `corrente-mecanica`
- ✅ **Corrente: os 6 estilos** — Pesadas e leves (recomendado) (01/10/2026) `corrente-estilos`
- ✅ **Corrente: arte no palco** — Pela esteira de sprites (ChatGPT + Grok) (01/10/2026) `corrente-arte`
- ✅ **Corrente: lutas antigas mudam** — Chave só para lutas novas (01/10/2026) `corrente-seeds-antigas`
- ✅ **Todas as armas: o golpe acerta antes de bater** — Só a corrente agora (recomendado) (01/10/2026) `golpe-acerta-no-preparo`
- ✅ **Lote das builds: a quarta entra?** — seg–qua para as builds também (recomendado) (01/10/2026) `lote-builds-quarta`
- ✅ **Imagem-mestra do estilo: aprovar?** — Refazer (diga o que mudar no comentário) (02/10/2026) · “Sei lá quero algo mais estiloso” `imagem-mestra-v1`
- ✅ **Imagem-mestra: qual estilo (9 testes)?** — 2 Anime (02/10/2026) `imagem-mestra-v2`
- ✅ **Som real nas 15 builds de estoque: fazer ou tirar da fila?** — Só as novas têm som real (04/10/2026) `som-real-15-builds`
- ✅ **Parede de planos do Digen: consertar agora ou depois?** — Deixar em espera (05/10/2026) `digen-parede`
- ✅ **Sprites modulares e painel de anexo** — Modular: cada parte é um sprite estático e o Godot monta e anima (06/10/2026) · “06/10 pelo chat: animações modulares; sprites estáticos, o Godot cuida do movimento; painel de anexo pronto de manhã” `sprites-modulares-painel`
- ✅ **Sprites modulares: as 9 escolhas do desenho** — Aceito as 9 (recomendado) (06/10/2026) `sprites-modulares-9-respostas`
- ✅ **Sprites: guarda-roupa de variantes** — Sorteio fixo por lutador + provador (06/10/2026) · “06/10 pelo chat: 'vários olhos aleatórios ... igual aqueles jogos de colocar roupa' (orquestrador escolheu a recomendada; o Adrian pode trocar no app)” `sprites-guarda-roupa`
- ✅ **Sprites: recortador de folha** — Tira só verde ou magenta e separa cada sprite (06/10/2026) · “06/10 pelo chat (pedido direto do Adrian)” `sprites-recortador`
- ✅ **Recortador: par de olhos desenhado de frente** — Separar o par e pôr cada olho no seu lugar (recomendado) (06/10/2026) `recortador-par-de-olhos`
- ✅ **Corrente: quem desenha agora que a esteira desligou** — Código agora, arte depois (recomendado) (07/10/2026) `corrente-arte-atelie`
- ✅ **Duelo pelo palco: trocar já os que não têm corrente?** — Sim, troco os sem corrente (recomendado) (07/10/2026) `duelo-palco-sem-corrente`
- ✅ **Seus desenhos do Ateliê: guardar no git?** — Guardar no git (recomendado) (07/10/2026) `arte-atelie-no-git`
- ✅ **Desenho 'Comum' de habilidade: vale para todos os elementos?** — Sua arte por elemento ganha; o Comum troca só a provisória (recomendado) (07/10/2026) `comum-tingido-ordem`
- ✅ **Rosto desenhado só em algumas carinhas: o que aparece nas outras?** — Usa a sua mais parecida (recomendado) (07/10/2026) `boca-de-uma-carinha`
- ✅ **Launcher: o 'Iniciar batalha' com o visual antigo** — Tirar o pygame do launcher (08/10/2026) `launcher-iniciar-batalha`
- ✅ **Botão 'Gerar Roster' do torneio** — Gravar num catálogo só do torneio (recomendado) (14/10/2026) `gerar-roster-do-torneio`
- ✅ **Luta que termina empatada** — Desempatar pelo HP que sobrou (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `empate-persistente`
- ✅ **Nome pedido pelo comentarista** — Manter a regra (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `nome-pedido-livre`
- ✅ **Os 29 traços sem efeito** — Tirar do sorteio agora, implementar aos poucos (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `quirks-sem-efeito`
- ✅ **Atordoamento e relógio de ataque** — Manter como está (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `atordoamento-e-relogio`
- ✅ **Lava do Vulcão e do Inferno** — Ligar o dano da lava (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `lava-do-vulcao`
- ✅ **Som da vitória** — Uma fanfarra curta de vitória (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `som-da-vitoria`
- ✅ **Volume dos golpes depois do conserto** — Pode aplicar direto (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `volume-dos-golpes`
- ✅ **Live: !arena com dois pagantes** — Vale o primeiro; o que não coube é recusado com reembolso na tela (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `arena-dois-pagantes`
- ✅ **Estatísticas do torneio** — Preencher (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `estatisticas-do-torneio`
- ✅ **Moderação da live** — Ligar a um comando de moderador (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou ('não quero decidir nada, tome as melhores decisões'), 14/10 08:2x.” `banimento-na-live`
- ✅ **Esteira de sprites de volta, com o ChatGPT** — Ligar com o ChatGPT gerando tudo (peças e folhas), juiz ChatGPT, aprovação final do Adrian (14/10/2026) · “Ordem do Adrian no chat (14/10). Gerador sempre ChatGPT (sem Gemini cobrindo), folhas animadas incluídas, nada entra no jogo sem a aprovação dele na tela de conferência.” `esteira-sprites-chatgpt`
- ✅ **Sprite-base aprovado vai para a biblioteca** — Fica na biblioteca (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou as decisões (14/10).” `base-aprovado-na-biblioteca`
- ✅ **Sprite-base rejeitado depois das folhas** — Folhas não aprovadas voltam a refazer com o base novo (recomendado) (14/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou as decisões (14/10).” `base-rejeitado-depois`
- ✅ **HUD do topo do duelo sob as abas do TikTok/Shorts** — Descer o HUD para baixo de 10% da altura e fora dos 12% da direita (recomendado) (18/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou as decisões (14/10).” `hud-do-topo-zona-segura`
- ✅ **Câmera da luta sabe do HUD; callouts cabem na zona segura** — Câmera DIRETOR com margem de topo abaixo do HUD durante a luta e callouts encolhidos para caber à esquerda de 88% (recomendado) (19/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou as decisões (14/10).” `camera-da-luta-sob-o-hud`
- ✅ **Desligar a geração da madrugada (madrugada_na_transicao)** — Desligar: o pesado fica de dia, como decidido (recomendado) (19/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou as decisões (14/10).” `madrugada-na-transicao`
- ✅ **Vídeos narrados com a voz do Windows (12 a 19/10)** — Refazer a voz só do que ainda não foi publicado; o que já foi ao ar fica (recomendado) (19/10/2026) · “Escolhida pelo orquestrador: o Adrian delegou as decisões (14/10).” `voz-do-windows-12-a-19-10`
- ✅ **Estoque de duelos: regravar em inglês** — Regravar os 18 publicáveis com o código novo, fora da janela das postagens (recomendado) (20/10/2026) · “Escolhida pelo orquestrador (adrian-nao-quer-decidir)” `estoque-duelos-em-ingles`
- ✅ **7 duelos de 12/10 não se reproduzem no motor atual** — Regravar com o motor atual, mesmo par/seed/arena/id/título; o que der < 15 s vira pendente (recomendado) (20/10/2026) · “Escolhida pelo orquestrador (adrian-nao-quer-decidir)” `regravar-com-motor-novo`

<!-- decisoes:fim -->

Minha parte: `random_builds/` (main.py e o motor de geração — roleta/builds,
estreias, duelos, torneios, render, capa, áudio/voz, reações) e
`neural_fights/` (banco de personagens e armas, motor de luta, gravador). NÃO é
minha parte a publicação (`ferramentas/postar.py`) nem as histórias. Tudo
abaixo foi conferido em 27/09/2026 nos arquivos; o que veio de fora está dito.

## 1. Os formatos: o que são, quanto custam, onde saem

Tudo cai em `random_builds/outputs/<id>/`, sempre em dois perfis
(`final_celular.mp4` = 9:16 e `final_normal.mp4` = 16:9), mais `capa.png`.

| formato | o que é | duração medida (celular) | custo medido | pasta |
|---|---|---|---|---|
| **duelo** | a luta inteira em 20–35 s, um evento só, nenhuma cena parada; identidade (~1,5 s) e veredito (~1,2 s) são sobreposições no próprio clipe | `duelo_00015` = 27,8 s | ~4,3 min por duelo ponta a ponta (8 duelos entre 17:29 e 18:03 de 27/09); render ~45–90 s por perfil | `duelo_000NN/` |
| **build** | a roleta: personagem + arma sorteados, nota, narração com voz, reação, e o round decisivo da estreia no fim | `generation_00085` = 56,7 s | um `generate-video` levou 10 min (24/09, 20:33→20:43) e nesse tempo entrega build **e** estreia; a fila de imagem/clipe (PicassoIA/Digen) continua depois | `generation_000NN/` |
| **estreia** | a primeira luta do personagem novo, melhor de 3 (`editing.json: estreia_melhor_de`) | `generation_00085/estreia` = 80,5 s (renders antigos passam de 2 min) | sai dentro do mesmo `generate-video`: ~3,5 min dos 10 (gravação + 2 renders) | `generation_000NN/estreia/` |
| **torneio** | chave de 8, uma volta inteira | — | só 2 existem (`tournament_00006`, `00007`); cota 0, não é produzido | `tournament_000NN/` |
| luta avulsa | `fight`, 2 formatos, fora da grade | — | — | `fight_000NN/` |

Hoje no disco (28/09, 02:28): 83 `generation_*`, 23 `duelo_*`, 2
`tournament_*`, 4 `fight_*`.

Dentro da pasta: `fight.json` (gameplay simulado), `edit_plan.json` (a
montagem), `gameplay/` (clipes crus) e, na build, `build.json`,
`character.json`, `weapon.json`, `rolls.json`, `evaluation.json`,
`narration.json`, `voz.wav`, `subtitles.srt`, `identity/`.

## 2. Como gerar (de `E:\projetos\random_builds`, `python main.py ...`)

```bash
# DUELO — o formato que a grade mais quer (4 de 8)
python main.py duelo                                  # p1 e p2 em rodízio (arena/rodizio.py)
python main.py duelo --p1 "Wren Telgyll" --p2 "Emi Ossarhamar"
python main.py duelo --seed 4242 --preview
python main.py duelo --rerender duelo_00012 --refazer-edicao   # sem re-simular

# BUILD (+ ESTREIA no mesmo comando)
python main.py generate-video
python main.py generate-video --seed 847293847        # mesma seed = mesmo vídeo
python main.py generate-video --no-estreia            # roleta sem gravar a 1ª luta
python main.py generate-video --generation-only       # só dados, nunca insere no banco
python main.py generate-video --rerender generation_00061 --refazer-edicao

python main.py fight --p1 "Kael" --p2 "Lyra" --melhor-de 3
python main.py tournament --fonte misto --participantes 8

# SOM REAL DA LUTA em vídeo já gravado (Onda 16A, §7) — sem regravar a luta
python main.py som-da-luta --listar                  # estoque com a luta muda + comando
python main.py som-da-luta duelo_00014 generation_00029   # anota e re-renderiza NO LUGAR
python main.py som-da-luta E:\projetos\random_builds\outputs\duelo_00014 --destino outputs\_ouvir\teste --perfis celular   # numa cópia

# GERAÇÃO (lote de dia desde 30/09) — o que as tarefas NeuralFights_gerar_HH chamam
python main.py noite --listar        # tarefas + estoque da publicação + o modo e as metas de agora
python main.py noite --ensaio        # faz todas as conferências e diz o que faria; não gera
python main.py noite --duelos 8      # rodada manual: 8 ignorando o teto (o relógio ainda manda)
python main.py noite --builds 1      # rodada manual: 1 roleta; com --duelos/--builds só o pedido sai
python main.py noite --instalar      # (re)cria as tarefas; --remover apaga
```

**Rodízio do duelo** (`builds/arena/rodizio.py`, desde 28/09/2026): sem
`--p1`/`--p2`, luta primeiro quem apareceu menos nos últimos 20 duelos (como
p1 ou p2); no empate, quem saiu da roleta (tem vídeo de build) e, entre esses,
o mais recente. O p2 sai dos menos usados pela regra antiga (continuidade,
senão poder próximo). **Par com título já ocupado nunca é escolhido**, em
nenhuma ordem: o título do duelo era `{p1} x {p2}` e, desde 20/10/2026, é
o confronto pela arma em inglês (`{lado1} VS {lado2} — who wins?`, §13); a
guarda de título repetido barraria o vídeo para sempre. Antes era "o último criado na roleta",
e sem roleta nova isso deu 5 de 8 duelos com o mesmo p1 (Wren Telgyll, 27/09).
**Quem derruba a gravação sai do rodízio por 7 dias** (19/10): o duelo que
falha grava `falhou.json` na pasta dele, e quem aparece em 2 falhas na semana
fica de fora (`rodizio.suspensos`; `--p1`/`--p2` passam por cima). Sem isso
o par que estourou os 600 s (Ardeth Morturth × Zael Ossarvarn, 16:23 e 16:34
de 19/10) era "o menos usado" para sempre e toda rodada fechava com 0 duelos.

**A rodada** (`builds/pipeline/noite.py`, config em `config/geracao.json`)
gera duelos **e builds (roleta, `generate-video` inteiro: build, inserção no
banco, estreia, render e fila de identidade)** e depois roda o `identity
worker` (capa e payoff das builds). **Desde 30/09/2026 é o lote semanal de
dia** (decisões do Adrian no Grimório `geral/lote-*`: barulho de madrugada).
Quem decide o que cada disparo faz é `noite.planejar`, **antes da trava**, o
mesmo desenho da agenda das histórias:

| modo | quando | o que faz |
|---|---|---|
| `lote` | seg–qua (`dias_de_lote [0,1,2]`), 07h–22h, a partir de `lote_a_partir_de` 05/10 | gera até a meta **de cada formato** (desde 19/10, §13): o que a publicação tira dele até a próxima segunda 07h + o piso dele (seg 07:02 = **69 duelos, 35 vídeos de build, 8 estreias**; qua 07:02 = 57/27/6). A quarta entrou em 01/10 (nó `builds/lote-builds-quarta`): ela só gera se a terça não fechou — com as metas cheias, não faz nada |
| `reposicao` | qui–dom 07h–22h (e seg–qua antes de 05/10) | gera o formato que está abaixo do **piso dele** (duelo 25 = 4 dias, build 8 = 2 dias); até 19/10 era o total do canal contra 20, e as estreias paradas enchiam o total |
| `madrugada` | 01h–06h enquanto existir `madrugada_na_transicao` | o esquema antigo: teto de gordura (13 duelos, 8 builds desde 19/10), no máximo 6 duelos e 1 build por disparo |
| `zero` | fora da janela **sem duelo nem build** (estreia não conta: o YouTube não a posta) | libera tudo (`estoque_zero_libera_a_noite`), até os pisos; o League of Legends aberto não segura |
| `noite` | fora de tudo, com estoque | nada |

**Quem tem menos dias de estoque vai primeiro** (dias = estoque ÷ o que a
publicação tira dele por dia; empate, duelo) — decisão do Adrian de 28/09 —
e desde 19/10 a ordem é **refeita a cada passo**: depois de cada duelo ou
roleta o formato ganha o que entrou e quem ficou com menos dias vai de novo
(antes uma roleta de 34–94 min levava a rodada inteira). A estreia só nasce
dentro da roleta, mas a falta dela **não pede roleta** (§13). **O número que decide é o da publicação** (`noite.contar_estoque`
= `postar._builds_prontos` agrupado por formato, o mesmo que
`pendentes_por_canal()["builds"]`, o `--ver` e o alerta de piso contam; o
piso da publicação, `postar.piso_de_alerta("builds")`, lê o
`piso_de_reposicao` daqui); o de build soma as **builds em preparo** (A/celular
não publicada, só com pendência que o worker resolve e com job vivo na fila).
As histórias contaram por critério próprio em 30/09 e erraram 27 × 8.

**Relógio.** Nada roda **de post−18 a post+18** em cada um dos 10 horários
(`folga_da_grade` 18/18 desde 19/10 — era 15/15 —, `builds.grade.GRADE`,
inclusive 12:07 e 17:57; nas horas de :37 é de :19 a :55): um
passo só começa se termina antes de post−18. **Nem com a partida do League
of Legends aberta** (`jogo_que_segura`, §13), menos no estoque zero. A regra velha (`grade_proibida`
:25–:55 de toda hora) está `null` no config — tirava metade do dia e não via
12:07 nem 17:57; o padrão do código ainda a tem, para config ilegível
(`PADRAO` = esquema antigo de madrugada). Uma rodada dura até 55 min
(`rodada_de_dia`) e o disparo seguinte continua; com job de identidade
esperando, a geração para 20 min antes e o resto é do worker. De dia: até 11
duelos e 3 builds por rodada. Duelo reserva 5 min (**8** com o celular pelo
palco ligado, `minutos_por_duelo_palco`, §9), build **27**, imagem 8,
payoff 18. A build era 15 até 01/10: o primeiro disparo de dia (15:02,
`generation_00090`, com a pista das histórias rodando junto) levou **26,1
min** e terminou 15:28, 6 min dentro da folga do post das 15:37; sozinha, de
madrugada, a mesma coisa leva 7,7 min (`generation_00089`). **Disco:** com menos de 5 GB livres no C: nada novo é gerado
(o worker ainda termina o que já foi pago). O `som-da-luta` usa a mesma
régua da grade (`sonorizar.cabe_agora` → `noite.fora_da_grade`).

**Disparos** (`horas`): 07:02 a 21:02 de hora em hora, com **12:32** e
**18:22** (12:02 e 18:02 caem na folga de 12:07 e 17:57); 22:02, 23:02 e
00:02 (só estoque zero); 01:02–05:02 (transição e estoque zero). **Para
desligar a madrugada depois de validado o dia: apagar
`madrugada_na_transicao` do `geracao.json`** — as tarefas 01–05 continuam, só
para o estoque zero. `"builds": false` desliga a roleta; `"ativo": false`,
tudo. A roleta não usa o PicassoIA: só enfileira; quem abre o site é o
worker, com a trava de perfil (`travas.do_perfil`), **um provedor por vez e
com prazo** (`worker.drenar(so_provedor=, prazo=)`); resíduo: o Digen tem
espera própria de até 30 min. Trava `builds__gerar` entre processos (a rodada
que encontra outra em andamento sai). A saída vai para
`outputs/_logs/gerar_AAAAMMDD.txt` (com hora, e o modo de cada disparo) e
`gerar_saida.txt` (o resto); o lançador `gerar.cmd` é gerado pelo
`--instalar` e não vai para o git.

Pré-requisito real: **personagem com ficha no banco do neural_fights**. Duelo,
fight e torneio leem `fichas_do_banco()`; sem ficha não há quem lute e o duelo
levanta `"nao ha adversario disponivel no banco"`. O banco vivo é
`%LOCALAPPDATA%\neural-fights\{personagens,armas}.json` (hoje 82 e 95; última
escrita 24/09 20:33, a inserção da `generation_00085`); o que está em
`neural_fights/data/*.json` é o snapshot do pacote (64 personagens), não o banco
vivo. `generate-video` é o único que insere (a menos de `--no-insert`).

## 3. O dado que decide

Medição de 27/09/2026 (recebida da orquestração), % assistido e views medianas:
**duelo 51,5% / 78 views**, build 25,4% / 37, estreia 10,7% / 25.

O retrato local foi refeito no mesmo dia (`random_builds/outputs/_metricas/`,
95 arquivos gravados às 20:08 de 27/09; `python main.py metricas` sem
`--atualizar` lê ele) e aponta na mesma direção, com números menores:

| formato | n | retenção média | retenção mediana | views medianas |
|---|---|---|---|---|
| duelo | 7 | 34,0% | 36,3% | 44 |
| build | 59 | 25,1% | 20,0% | 23 |
| estreia | 27 | 10,4% | 5,1% | 7 |
| torneio | 1 | 19,9% | 19,9% | 25 |

A diferença para o número da orquestração é de fonte (não sei qual ela usou;
o 51,5% coincide com o `duelo_00001` sozinho). O duelo ganha nas duas
dimensões e é o formato mais barato — mas n = 7, todos de 11–13/09.

**A cota mora em `random_builds/config/publicacao.json`, bloco
`grade.mistura`:** `duelo 4, build 3, estreia 1, torneio 0`. O padrão de queda
(se o bloco desaparecer) é `COTA_PADRAO` em `ferramentas/postar.py:1717`, com o
mesmo conteúdo, lido por `cota_da_grade()`; quem escolhe o vídeo de cada
horário é `escolher_por_cota()` (vence o formato mais atrasado em relação à
cota dele). Os números são **pesos relativos**: `builds/grade.py` tem **10**
horários desde 15/09, e 4+3+1 = 8 dá ao duelo metade deles (5), ao build 3,75
e à estreia 1,25; formato sem estoque cede o horário. O comentário do config
foi corrigido em 28/09 (falava em "8 disparos"); o do código
(`ferramentas/postar.py:1715`) ainda fala, e o arquivo é da publicação.
**Aumentar a cota do duelo espera ~10 duelos medidos** (hoje há 7 com
métrica): não mexer antes.

## 4. O que já quebrou

- **Builds pararam por falta de estoque, e não há nada que os crie.** O canal
  publicou ~20 vídeos/dia até 20/09; depois: 2 em 21/09, **zero em 22, 23, 25 e
  26/09**, 2 em 24/09 e 2 em 27/09 (`outputs/_publicar/publicados.jsonl`). A
  causa é montante: a última build é a `generation_00085`, de 24/09, e os duelos
  anteriores aos de hoje são todos de 11/09. No Agendador do Windows havia **14
  tarefas `Historias_auto_*`** e **10 `NeuralFights_postar_*`** — e **nenhuma
  que gerasse build ou duelo**. **Remédio (27/09, 23:57):** as tarefas
  `NeuralFights_gerar_01..05` (HH:02) rodam `main.py noite` — duelos até o
  teto e o worker de identidade (§2). Testadas antes de registrar com um
  ensaio de ponta a ponta pelo próprio Agendador (tarefa temporária →
  wscript → `gerar.cmd --ensaio` → trava → diário), que não gera nada.
  Desde 28/09 (noite) a mesma rodada gera também a roleta (§2).
- **Personagens de agosto perdidos.** O banco foi refeito em 02/09 e as fichas
  de agosto saíram junto. Quem depende delas não volta: a estreia de uma build
  antiga é impossível, não pendente — `catalogo._falta_estreia()` diz isso com
  o nome do personagem, em vez de pedir para "gravar a luta" (era a lápide que
  contava 20 tarefas todo dia).
- **Vídeo mudo.** Render antigo saía calado ou com som só no fim.
  `generation_00066/estreia/final_celular.mp4` tem **114,7 s de silêncio em
  120,8 s (95%)**, média -30,4 dB — medido agora com ffmpeg. A guarda está na
  publicação (`_audio_mudo`, `FRACAO_MUDA = 0.5`) e era ela que segurava esse
  vídeo, medindo-o de novo a cada horário. **Descartada em 28/09** (decisão 5
  da rota): `config/publicacao.json → descartados` tira do catálogo, da fila,
  do painel e de `por_id` tudo o que tiver a chave `<fonte_id>:<origem>`
  (`generation_00066:estreia`), com o motivo escrito. Nada é apagado: o mp4
  fica na pasta, e tirar a linha devolve o vídeo. `main.py publicar` lista os
  descartados no fim, e publicar um deles na mão diz o motivo. A
  **`generation_00077`** saiu pelo mesmo caminho em 28/09 (decisão
  `generation-00077`: "Descartar, como a 00066"), com as duas chaves
  (`:build` e `:estreia`): medido pela régua da publicação, a luta está a
  -91 dB na build (`seg_022`, A e B) **e** na estreia (`seg_007`), e os dois
  lutadores saíram do banco em 02/09. Build descartada também tira o payoff
  dela da fila do worker (`queue.geracoes_descartadas()`): o job fica
  `pending`, ninguém o reivindica, e volta junto se a linha sair.
- **Gancho B com título igual ao do A.** A variante B (`final_<perfil>_ganchoB.mp4`)
  tem id com sufixo `:B` e o MESMO título; para o código eram dois vídeos, para
  o YouTube eram duplicatas. 21 chaves de título saíram duas vezes (medição de
  16/09 registrada no config). O remédio foi `grade.repetir_titulo: false`, que
  barra título já publicado — e isso deixou as variantes B paradas.
  **Segundo remédio (27/09, decisão do Adrian: título próprio para cada B):**
  dos 25 fora da fila por título, 21 eram B e 4 eram A. **18 B ganharam
  título próprio** em `outputs/_publicar/_textos/` (celular e normal; o A e a
  descrição não mudam), no tom pedido pelo Adrian em 27/08 (limpo e
  convidativo: pergunta a quem assiste, sem grito nem emoji) e sem nota nem
  veredito no título (ex.: "Suki Acijaggur: monge com Bomba Relógio? A roleta
  surtou"). **7 continuam fora de propósito**: `generation_00026/28/29` (A e
  B) e `generation_00027` (A) são re-execuções de seed fixa (99 e 4242) da
  MESMA build já publicada como `00025` e `00024` — mesmo personagem, mesma
  nota, mesmo gancho B. Título novo ali poria o mesmo vídeo no ar de novo.
  Conferido com `postar.py --ver --so builds`: "25 fora por título" virou 7,
  gordura de builds 0 → 2 dias.
- **A luta sem o som do jogo** (28/09). A guarda media o arquivo inteiro, e
  a música esconde uma luta calada. A causa era de render: o gravador
  escrevia `anullsrc`, o corte de tédio aplicava `-an`, e o som do jogo nunca
  entrou num mp4; desde 02/09 o que entrava era o sintetizado
  (`trilha.sfx_da_luta` — no `duelo_00015`, 25 vezes o mesmo hit e 14 o mesmo
  grave). A publicação passou a medir cada trecho de luta; a origem foi
  consertada na 16A (§7).

## 5. Estado de hoje (28/09/2026, madrugada)

- **Duelos**: rodada manual com vigia (armado 23:58, encerrou sozinho às
  02:19) gerou **8 duelos novos, `duelo_00016` a `00023`, 16 nomes diferentes**
  (A: 5 entre 01:00 e 01:20; B: 3 entre 01:55 e 02:03). ~4,5 min por duelo;
  duração 13–28 s; áudio medido nos 8: média -12 a -16 dB, zero silêncio. As
  tarefas das 01:02 e 02:02 saíram com "já rodando", como previsto. **12 no
  estoque** que a grade escolheria (`00012`–`00023`), teto 10: ~2 dias.
  Atenção: `duelo_00023` é "Kuro #2 x Orion o Implacável" — o `#2` é
  desempate de nome do banco e vai no título.
- **Builds**: 18 variantes B voltaram à fila com título próprio (§4); a
  `generation_00083` B já saiu (00:37). Gordura de builds 2 dias pelo
  `postar.py --ver`.
- **Worker** (rodadas das 02:04, 03:02, 04:02 e 05:02): as **3 imagens** de
  `generation_00085` e de `generation_00077` estão prontas; as da 00085 com
  prova de origem forte (`identity auditar`: 3 de 3). Às 03:02 e 04:02 o
  PicassoIA estava preso pela rodada de histórias (mesma trava de perfil); a
  partir das 03:06 um provedor ocupado passa a vez ao outro em vez de encerrar
  o worker. **Os dois payoffs do Digen faltam**, e as duas builds seguem fora
  da fila por pendência:
  - `generation_00085#character_weapon` **falhou 3 vezes às 04:03–04:07**
    (`failed`): um diálogo de propaganda do Digen ("Upgrade",
    `pc-pop-916.webp`, `role=dialog`) cobre o composer e engole o clique —
    a mesma família da "parede do PicassoIA". O anexo da referência também não
    entrou. **Consertado em 28/09 (08:00)**, olhando a tela: a propaganda
    aparece sozinha 10–15 s depois de a página carregar e fecha pelo X
    (`button[data-slot="dialog-close"]`). `client.instalar_guarda` registra
    um `add_locator_handler` do Playwright que fecha a parede antes de TODA
    ação na página (inclusive os cliques de `escrever` e `referencias.anexar`
    e as novas tentativas de um clique que já esperava), e há chamada
    explícita a `tirar_parede_da_frente` antes de cada clique do fluxo e na
    espera. Só o modal do shadcn (`data-slot="dialog-content"`): os popovers
    de modelo/duração/anexo também são `role=dialog` e não podem ser
    fechados. Provado no navegador de verdade com uma parede de mesma
    estrutura: o clique cru passou em 0,2 s. A conta do Digen aparece como
    **Free** (Meme 221, Pro Meme 0).
  - `generation_00077#character_weapon` pendente: não coube às 05:12 (18 min).
    Desde 28/09 à noite a 00077 está descartada (§4) e o worker não pega
    mais esse job.
  Build não tem `capa.png` (só duelo tem); o que falta nas duas é o payoff.
- **82 personagens e 95 armas** no banco vivo; só **9** dos personagens de
  roleta estão nele (os de agosto se perderam em 02/09).
- **Estreia**: nenhuma em estoque. A da `generation_00066` (muda) foi
  descartada de forma reversível (§4); o horário da estreia vai para outro
  formato.
- Pendente:
  - **7 builds fora por título** que são a mesma build de outra (§4) —
    decisão do Adrian se ficam fora para sempre;
  - a roleta entrou na rodada noturna em 28/09 (§2); a estreia sai dentro
    dela. Primeira roleta automática ainda não aconteceu (estoque acima do
    teto).

## 6. Como conferir sem publicar

```bash
cd E:\projetos\random_builds
python main.py fluxo --limite 30        # onde cada build está e o próximo passo
python main.py fluxo --json             # o mesmo, estruturado
python main.py publicar                 # LISTA o catálogo (sem id e sem flag, não envia nada)
python main.py metricas                 # sem --atualizar: mostra o último dado salvo
python main.py arena ranking            # cartel dos personagens
python main.py cobertura --apenas-faltando   # o que o banco tem e o vídeo não sabe descrever
python main.py noite --listar           # tarefas de geração + duelos que a grade escolheria
python main.py som-da-luta --listar     # estoque não publicado com a luta muda (§7); não muda nada

cd E:\projetos
python ferramentas/postar.py --ver --so builds   # diz o que postaria e SAI
```
Estoque por formato existe em código (`postar.estoque_por_formato()`, medido
contra a cota de cada um) e aparece no aviso do Telegram. O que a geração
usa para decidir (`noite.contar_estoque()`) é a mesma lista da publicação,
por formato, e aparece em `main.py noite --listar` junto com o modo e as
metas de agora.

**O que NÃO fazer:** não rodar `main.py publicar <id> --youtube/--tiktok`
(publica de verdade), nem `postar.py` sem `--ver`, nem `--instalar`. Não usar
`--forcar` para empurrar vídeo com pendência (mudo, sem payoff, sem luta) —
a pendência é a única coisa que segurou a estreia muda. Não apagar pasta de
`outputs/`: o ledger e as métricas referenciam o id. Não editar
`neural_fights/data/personagens.json` esperando mexer no banco vivo (é o
snapshot do pacote). Não refazer o banco: foi isso que matou agosto. E não
gerar vídeo na meia hora em volta de cada horário da grade
(`noite.fora_da_grade`; até 30/09 a regra era :25–:55 de toda hora).

## 7. O som da luta (Onda 16A, 28/09/2026)

Decisão do Adrian (28/09): o visual atual continua publicando, mas já com o
som de verdade do jogo. Até aqui o som do jogo nunca tinha entrado num mp4
(§4, "Vídeo mudo").

**Como é agora.**
- O gravador põe um `AnotadorDeAudio`
  (`neural_fights/effects/audio_anotador.py`) no lugar do `AudioManager`: ele
  herda toda a decisão de som do jogo (qual som, variante do grupo, volume por
  categoria e por distância) e anota em vez de tocar. A lista `sons` (formato
  em `docs/palco/sons.md`) atravessa o corte de tédio (`remapear_gravacao`) e
  fica em `fight.json` → `luta.sons`, no relógio do clipe.
- O render mistura a lista com os arquivos que o jogo usa
  (`neural_fights/effects/mixagem.py`: `%LOCALAPPDATA%\neural-fights\sounds\`
  antes do pacote, pelo `sound_config.json` e pelos fallbacks do jogo), com o
  pitch anotado, nível por trecho e limitador. O bruto da gravação também sai
  com esse som no lugar do `anullsrc`, e o corte leva o áudio junto (partes
  em PCM: com aac, um estalo caía 67 ms atrasado já na 2ª parte).
- A luta não muda: a variante do grupo continua sorteada pelo `random`
  global, como no jogo, e o teste compara vencedor, duração, HP, golpes e o
  estado do `random` no fim, com e sem anotador. O pitch (golpes ±7%,
  impactos ±6%, projéteis e skills ±4%, movimento ±8%, ambiente fixo) usa um
  `Random` próprio semeado pela seed da luta.
- Knob em `config/editing.json` → `som_da_luta`: `real` (liga),
  `sintetizado_de_reforco` (**desligado**: medido, o som real sozinho já deixa
  o trecho com 0% calado e 9 a 11 arquivos distintos; o sintetizado só
  somava repetição) e `alvo_db` = -13 (o trecho de luta em ~-18 LUFS, o nível
  em que o sintetizado estava).
- Luta gravada antes de 28/09 não tem `sons` e segue no sintetizado.
  `main.py som-da-luta <id>` re-simula a MESMA luta sem vídeo, confere
  vencedor, duração e golpes contra o `fight.json` (recusa se divergir) e
  re-renderiza no lugar — numa geração, a estreia e a build juntas. Nenhum
  alvo começa se não termina antes de :25.
- Consertos no caminho: o transcode simples do renderer saía com código 0 e
  SEM faixa de áudio (a 2ª tentativa nunca rodava) — agora refaz, e sem áudio
  mesmo assim é erro; o sintetizado do trecho de luta no fim do build
  ignorava o `start_offset` (tocava os golpes dos primeiros 6,5 s da luta
  sobre os últimos).

**Medido nos pares** (`random_builds\outputs\_ouvir\`, mesmo duelo e mesma
seed; "trecho" = o segmento de luta antes da música, que é o que a guarda
mede):

| duelo | trecho de luta: antes → depois | variedade: antes → depois | vídeo final |
|---|---|---|---|
| `duelo_00014` (machados de arremesso × corrente) | -18,2 → -17,8 LUFS; **63% → 0% calado**; LRA 23,7 → 4,1 | 36 camadas de 5 sons sintetizados (15 hits e 15 graves iguais) → 217 sons, 19 ids, **11 arquivos** | -15,0 → -15,5 LUFS |
| `duelo_00016` (piromante × machado-martelo) | -18,3 → -18,7; **57% → 0%**; LRA 17,4 → 7,2 | 22 camadas de 4 (15 hits iguais) → 161 sons, 19 ids, **11 arquivos** | -16,6 → -16,5 |
| `duelo_00022` (bestas, gelo) | -15,4 → -17,3; 29% → 0%; LRA 4,0 → 8,4 | 47 camadas de 4 (22 e 18 iguais) → 57 sons, 14 ids, **9 arquivos** | -13,7 → -15,4 |

A imagem é idêntica quadro a quadro nos três pares (`framemd5` do vídeo
igual): só o som muda. O wav do trecho sai limitado em -2,5 dBFS; o aac
intermediário pode passar disso (até +1 dB, em float, no `00014`: quatro
`energy_impact` no mesmo quadro), e a mixagem final — float, com `alimiter` e
`loudnorm` TP -1,5 — fecha com pico de -0,9 a -1,4 dB.

O juiz do som é o Adrian (o Gemini não recebe áudio). Ele aprovou em 28/09
(`som-real-16a`); desde 30/09 o pesado roda **de dia** (`fila-pesada-de-dia`).

**Re-render do estoque feito em 30/09 (09:55–09:58, de dia):** dos duelos
`00012`–`00023`, só **`00022` e `00023`** ainda estavam no estoque — os
`00012`–`00021` foram ao ar (YouTube e TikTok) entre 28 e 29/09 com o
sintetizado, porque o re-render da madrugada de 29/09 foi desarmado antes de
começar; trocar o arquivo de um publicado não muda o que foi ao ar. Medido no
trecho de luta (`seg_000`, celular), antes → depois: `00022` -15,4 → -17,3
LUFS, média -15,8 → -14,2 dB, **29% → 0% calado** (57 sons, 9 arquivos);
`00023` -14,6 → -18,3 LUFS, -15,8 → -14,3 dB, **40% → 0%** (60 sons, 9
arquivos). Vídeo inteiro -15,4 e -15,3 LUFS, duração igual (20,4 e 13,0 s).
~1,5 min por duelo. Como foi feito, para não pegar a publicação no meio: o
render vai para uma cópia (`som-da-luta <id> --destino E:\tmp_somdaluta\copia\<id>`)
e a troca no lugar é `os.replace` arquivo por arquivo (mp4, jsons, pastas
`_segments_*`), fora de :25–:55 e de [post-12, post+18] (12:07 e 17:57 não
são :37), sem `postar.py` rodando; arquivo aberto por quem lê faz a troca
falhar e voltar. Os originais ficaram em `E:\tmp_somdaluta\antes\`. O
render no lugar (`som-da-luta <id>` sem `--destino`) ainda escreve o mp4
direto, não atômico. Os duelos `00024`+ já nascem com o som real.

**Estoque com a luta muda** (`som-da-luta --listar`; a régua da LUTA da
guarda da publicação desde 6f09b80: média do trecho < -60 dB ou trecho sem
faixa de áudio — silêncio entre golpes não conta). Em 28/09, 07:31: 38
vídeos não publicados com luta (12 duelos, 26 builds), **2 mudos, de uma
fonte só**: `generation_00077` A e B (`seg_022` a -91 dB; render de 29/08,
antes do sintetizado). Som real impossível: Seraphina Pyrberim e Lucrecia
Aciaegir saíram do banco em 02/09 e a luta não re-simula. **Descartada em
28/09** (decisão `generation-00077`, build e estreia; §4). A
`generation_00066/estreia` (-91 dB) foi descartada pela decisão 5 do Adrian
(`config/publicacao.json` → `descartados`).

(Retrato de 28/09; o de 30/09, depois do re-render, é: 25 no estoque, 10
com o som real — `duelo_00022`–`00031` — e 15 com o sintetizado, todos
builds: as variantes B de `generation_00026`–`00041`, os A de `00026`–`00029`
que estão fora por título, e a `00085`, com pendência de payoff.)

**Essas 15 NÃO serão re-renderizadas** (decisão `som-real-15-builds`, 04/10/2026:
"Só as novas têm som real"). O item `b0d22ef8` saiu da fila da Mesa; elas
seguem no estoque com o sintetizado. O som real vale para as builds geradas
daqui em diante, que já nascem com ele. Não reabrir o re-render sem nova
ordem dele.

Os outros 36 estão com o sintetizado. Sete deles ficam calados em 57–63% do
trecho (`duelo_00014`, `00016`, `00017`, `generation_00029` A e B,
`generation_00077` A e B) — não é luta muda pela régua, mas é o som que
repete. Com o som aprovado, o re-render com o som real (de madrugada; o
comando para antes de :25 e continua depois de :55):
`python main.py som-da-luta duelo_00012 duelo_00013 duelo_00014 duelo_00015 duelo_00016 duelo_00017 duelo_00018 duelo_00019 duelo_00020 duelo_00021 duelo_00022 duelo_00023 generation_00029`
(~4 min por duelo). Conferido em 28/09 às 03:02 (`--so-anotar` numa cópia):
`duelo_00017` e os dois rounds de `generation_00029` re-simulam iguais ao
clipe; `00014`, `00016` e `00022` são os pares. As builds de antes de 11/09
(motor mudou na 15C) e as de elenco de agosto provavelmente não re-simulam:
o comando recusa e diz qual.

## 8. A corrente nova (rework, F0+F1 de 01/10/2026)

Pedido do Adrian (`palco-duelo-ab`): a corrente tinha a mesma mecânica da
espada. Decisões dele: bola física com momento, pesadas (Mangual, Meteor
Hammer, Corrente com Peso) com momento e leves (Chicote, Kusarigama, Rope
Dart) com enlace, e chave só para lutas novas. Plano em
`C:\Users\adrian\.claude\plans\corrente-rework.md`.

**O que existe:** `neural_fights/core/corrente.py`. A bola tem posição e
velocidade próprias, integradas em subpassos de no máximo 1/120 s, e fica presa
à mão pelo comprimento da corrente (`comp_corrente + comp_ponta` do banco,
entre 2,6 e 3,6 raios). O braço guia a bola por um servo de ângulo, no relógio
do MOTOR: preparo, golpe e follow.
- Acerto: a bola tem de varrer o corpo do alvo no tick, rápida o bastante,
  na fase de golpe.
- Dano: proporcional a v², com clamp entre 0,6 e 1,4.
- Empurrão: na direção da bola.
- Zona morta: natural; o braço encurta a corrente até 50%.
- Leves: em vez de empurrar, enlaçam. O alvo fica preso 0,4–0,6 s e é puxado
  (`core/agarrao.py`: `duracao_enlace`, `passo_enlace`).
- IA: anel de distância própria, e o matchup antigo deixa de sobrescrever a
  distância.

A corrente não usa RNG e não lê nada do animador. O campo `physics: chain`
passou a decidir quem tem bola, e `mod_velocidade` a escalar o braço.
`mod_dano` continua sem uso, documentado no módulo.

**Chave `CORRENTE_V2` — DESLIGADA.** Ela é lida do `match_config["corrente_v2"]`
da luta. Na falta dele, vale `neural_fights/utils/config.py: CORRENTE_V2 = False`.
Para ligar numa luta:
- `gravar_luta(..., corrente_v2=True)`;
- `gravar_timeline(..., corrente_v2=True)`;
- `qualidade_luta --corrente-v2`.

Para ligar em produção, a ordem é:
1. ~~o `random_builds` carimba `corrente_v2` no `fight.json` de toda luta nova
   e repassa o carimbo quando re-simula; sem carimbo vale False~~ — **feito
   na F2 (01/10, abaixo)**;
2. só então se troca o padrão (decisão do Adrian, depois da arte e do A/B).

Com a chave desligada, o Simulador não cria nem um atributo novo.

**Medido** (corpus completo, fixture engine, 546 lutas):

| | antiga (F0) | V2 |
|---|---|---|
| bola no corpo no acerto (`corrente_contato_no_acerto`) | **5,3%** (67/1263), folga mediana 1,08 m | **100%** (1269/1269), folga −0,20 m |
| winrate Corrente | 49,0% (77/157) | 46,2% (73/158) |
| pesadas / leves | 46/103 · 31/54 | 43/104 · 30/54 |
| B2 (tipo mín./máx.) | 0,331 / 0,616 | 0,338 / 0,626 |

Os outros tipos mudam no máximo uma vitória. Um alvo da onda 11 passa raspando
do limite: `D5_janela_seca_meta` foi de 5,94 para 6,02 (limite 6,0). Na
contagem, são 55 lutas com seca acima de 6 s contra 54; onze lutas com
corrente subiram e dez desceram, e a p90 só das lutas com corrente caiu
(6,25 → 6,22).

A referência do v² também foi medida, não escolhida. Com 85% da corrente, o
acerto mediano saía a 0,62 dela, 77% dos golpes caíam no piso e a Corrente ia
para 38% de vitórias. Hoje a referência está em 55%.

Ledger (`neural_fights/data/alvos_qualidade.json`):
- `K4_corrente_contato` (mín. 1,0): `enforce_onda` 99 até a troca;
- `B2c_corrente_winrate` (0,40–0,60).

**Achados de passagem** (não consertados, fora do escopo):
- O animador de arma é um singleton que guarda estado por `id` de lutador e
  nunca é zerado. Num processo com várias lutas (o corpus, ou `noite
  --duelos N`), ids reciclados mudam lutas.
  - Com o código ANTIGO, 5 das 546 lutas do corpus dão outro resultado no
    mesmo processo do que num processo novo.
  - Zerando o animador a cada luta, o antigo e o novo com a chave desligada
    dão 546/546 iguais.
  - A timeline já zera por precaução (`_zerar_animador_de_arma`).
- `brain._analisar_projeteis_vindo` divide por `vel_proj` zero. A luta
  `Aurora o Bravo × Jin a Protetora`, seed 21026, morre com
  `ZeroDivisionError` aos 24,1 s, num processo novo e no código antigo.

### F2 + F3 (01/10/2026, noite): a bola na timeline e a corrente no palco

**Carimbo (F2).** Toda luta nova grava `corrente_v2` no `fight.json` (no
confronto e em cada round), com o valor que o gravador USOU
(`runner.chave_corrente_padrao()` = `utils/config.py: CORRENTE_V2`, hoje
False; `FightSession.gerar`/`TournamentSession.gerar(corrente_v2=...)` passa
outro). O gravador recebe a chave explícita (`--corrente-v2` /
`--sem-corrente-v2`, `capture.gravar_uma(corrente_v2=)`) e devolve
`corrente_v2` no resultado. Quem re-simula lê `runner.corrente_da_luta(luta,
fight)` — round, senão confronto, senão **False** — e repassa: `som-da-luta`
(`som_real.anotar_luta`), `palco ab`, `palco ab --edicao`, `duelo --palco
--ab`. O `--rerender` (duelo, fight, build) não re-simula: reaproveita o clipe
e regrava o `fight.json` que leu, então o carimbo (ou a falta dele) fica como
está. Luta antiga sem o campo: re-simula com False, igual a hoje.

**Timeline revisão 4 (F2).** Canais `bola_x/bola_y/bola_vx/bola_vy` e o
cabeçalho `arma.corrente{comp_m, n_elos, cabeca, material, familia,
raio_bola_m, v_ref_ms, mao}` só de quem tem bola na luta; `luta.corrente_v2`
em toda timeline. Contrato em `docs/palco/timeline.md`. Sem a chave, nada
disso aparece e o resto da timeline é a revisão 3.

**A peça (F3).** `palco/biblioteca/armas/tipos/corrente.{tscn,gd}`: Verlet
SEM ESTADO — a cada quadro reintegra da âncora mais recente (início do
golpe, repouso da bola ou grade de 30 passos; nunca mais que 60 passos),
pontas presas na mão (derivada de `x, y, ang` + `mao`) e na bola; o passo em
que `tj` não anda (hitstop) não anda a corrente; salto (empurrão, puxão do
enlace) refaz a corrente na forma de descanso em vez de esticar. Elos
alternados frente/lado por código com contorno `#14141A`; `couro` (Chicote)
e `corda` (Meteor Hammer, Rope Dart) são cordões que afinam; cabeça por
estilo; rastro da bola proporcional a `v / v_ref`. Sem a chave, a mesma peça
desenha a corrente antiga (e o palco mantém o rastro genérico).

**Medido.** Render repetido bit a bit igual (Celeste a Impiedosa, Mangual ×
Emi Ossarhamar, Chicote; seed 30010; 450 quadros com corte de tédio e
hitstop): mp4 `dedef7bb…` nos dois, `framemd5` igual. Paridade Python×Godot
em 8 passos (inteiros e fracionários): canais a 1e-9, mão e pontas a 0,1 mm.
Na luta inteira (1700 passos): ~4,4 ms por quadro por corrente; a corrente
desenhada passa de 5% do comprimento em 5 de 1700 quadros (máx. 8,4%).

**Vitrines** (`outputs/_palco/corrente_f3/`, nada publica):
`b/palco_celular.mp4` (chave ligada só nela) e `ab/ab_corrente.mp4` (mesma
seed, antiga × nova; as lutas se separam no primeiro golpe de corrente).
Comandos:
`python main.py palco render --seed 30010 --p1 "Celeste a Impiedosa" --p2 "Emi Ossarhamar" --corrente-v2 --quadros 450`
e `python main.py palco corrente-ab --seed 30010 --p1 "Celeste a Impiedosa" --p2 "Emi Ossarhamar"`.

**Armadilha de worktree.** `neural_fights` está instalado em modo editável
apontando para `E:\projetos`: rodar o `main.py` de outra worktree usa o
`neural_fights` de `E:\projetos`, não o da worktree (a 1ª vitrine saiu com a
revisão 3 por isso). Na worktree, `PYTHONPATH=<worktree>`.

## 9. O duelo de produção pelo palco (16G, segunda metade, 07/10/2026)

**Pronto e DESLIGADO.** Chave: `config/palco.json → producao.duelo_celular`
= `"desligado"` (padrão; valor desconhecido ou config ilegível também) |
`"sem_corrente"` (pelo palco só se nenhum lutador usa arma do tipo Corrente;
arma fora do banco fica no pygame) | `"todos"`. Ligar é do Adrian: nó
`builds/duelo-palco-sem-corrente` (pendente). Só o `final_celular.mp4`; o
16:9 segue no pygame. Nos 91 duelos do disco, `sem_corrente` mandaria 70
(77%) pelo palco.

`_entregar_duelo` (duelo novo, `--rerender`, `som-da-luta` no lugar) chama
`builds/palco/producao.py` antes do celular; o B é montado em `<duelo>/palco/`
pelo mesmo miolo do A/B (`edicao.montar_sobre_o_palco`), medido, e só então
`_segments_celular/` e o mp4 vão para o lugar. Falhou qualquer guarda (golpes e
K.O. no mesmo quadro, duração da imagem = A + hitstop ± 3 quadros, nada preto,
congelado só depois do K.O., luta e vídeo pela régua da publicação, luta
calada ≤ 25%) ou o Godot: o celular sai pelo pygame, o motivo fica em
`<duelo>/palco_celular.json` e no diário (status `log`). O duelo nunca deixa
de sair por causa do palco. Detalhes e medidas: `docs/palco/README.md`.
Depois da conferência (07/10): as placas de nome somem quando o veredito entra
(job `nomes_ate_quadro`, conferido pelo relatório do Godot) e saem na cor do
lutador (`cor_nome`); 3 falhas SEGUIDAS viram um `erro` no diário (o bot avisa
uma vez; um duelo pelo palco zera, estado em `<runtime>/palco_producao.json`);
a chave desligada apaga `<duelo>/palco/`; Godot ausente falha antes de
re-simular.
Com a chave ligada o controller importa `builds.palco.producao`, sempre dentro
de um try (a frase do contrato "O palco", abaixo, de que a troca "espera o nó
`palco-duelo-ab`", vale para LIGAR a chave, não para o código, que já existe).

Prova em `E:\tmp_pytest\ab_0710\` (cópias, fora do catálogo): `duelo_00091`
(sem corrente) e `duelo_00090` em `todos` saíram pelo palco com 33/33 e 50/50
golpes no mesmo quadro, K.O. igual, trecho de luta igual ao A (-17,8 e -16,7
LUFS, 0% calado), B = A + hitstop (0,53 e 0,6 s); `duelo_00090` em
`sem_corrente` ficou no pygame (corrente). Palco de um duelo de 28 s: 182–208
s (Godot 87–91, x264 34–40, edição 51–60) com as histórias rodando junto; um
duelo novo inteiro de 22 s levou 3,6 min. Reserva da geração com a chave
ligada: `geracao.json → minutos_por_duelo_palco` = 8 (`noite.minutos_por_duelo`).
**Sessão bloqueada: não testado** (o Adrian estava no PC); se quebrar, a guarda
rc 4/quadro liso derruba o B e o celular sai pelo pygame.

**Consertos do palco de 14/10** (auditoria `2026-10-11-profunda/consertos/godot.md`;
todos latentes até a chave do duelo ou até haver folha de rosto/arma com esses
gatilhos no Ateliê):
- **Lutador sem arma** (`arma: null` no cabeçalho, quando a arma não resolve):
  `_evento` lia `arm[slot]` e a variante do acerto lia a arma do autor como
  Dictionary — SCRIPT ERROR e o render recusado (regressão do f5f8cd3). Teste
  `test_evento_de_lutador_sem_arma_nao_derruba_o_render` (render real).
- **Rosto do Ateliê** (`tocador_folha.gd`): os estados do catálogo são as 24
  carinhas; o canal `expr` (índice em `tabelas.expressoes`) vira `estado(nome)`
  e o palco manda UM gatilho por quadro (`golpe_fase` ou `expr`). Carinha não
  desenhada usa a família, depois a neutra, depois qualquer uma
  (`boca-de-uma-carinha`), e vai ao relatório em `rosto_herdado`. O tocador
  repassa `avancar`/`ajustar_corpo`/`estado` ao rosto pendurado; com o lutador
  marcador o palco repassa direto (`_repassar`). Teste `palco/testes/rosto_folha.gd`.
- **Evento da arma toca até o fim**: `ocioso`/`golpe_fase`/`expr` (gatilhos de
  quadro) não cortam uma animação de evento sem loop. Teste
  `palco/testes/tocador_folha.gd`.
- A variante do evento mora em `Biblioteca.variante_do_evento` (palco e
  `ferramentas/validar.gd` com a mesma cadeia); saiu o resto da cadeia PNG
  (`_id_slot`, `candidatos_*_png`, `opcoes_do_png`); a fonte do A/B vem de
  `palco.json → ab.fonte` ou do `WINDIR`.

## 10. Consertos do motor de 14/10 (auditoria `2026-10-11-profunda/consertos/motor.md`)

**Lote 1: o que NÃO muda a luta** (MOT-12, 13, 22–29, 32 código morto, 33,
102–129). Medido com a cópia do HEAD e a worktree, 16 lutas gravadas
(`gravar_luta`, seeds 1000–1015): vencedor, duração, HP final e golpes
**iguais em 16/16**.

- **Som** (o que vai para o vídeo):
  - o ouvinte é a câmera (`AudioManager.listener_x`, que o Simulador atualiza
    a cada passo). O cast media a distância contra x = 0: acima de 20 m saía
    mudo;
  - o pan não dobra mais o volume (`fv × (2 − |pan|)`); o som posicional leva
    o ganho constante `audio.GANHO_POSICIONAL` = 1,9;
  - para o golpe não ficar mais baixo no vídeo (ordem de 14/10 sobre o nó
    `volume-dos-golpes`), a mistura realça golpes e impactos em
    `mixagem.REALCE_GOLPES_DB` = +2 dB. Golpe no vídeo, nas 16 lutas, com o
    config e os wav do Adrian: **+0,68 dB em média** sobre hoje (5 de 16
    abaixo, pior −1,47 dB). Sem o realce dava −1,0 dB: o cast que voltou a
    soar pesa na normalização do trecho. O palco Godot toca o volume
    anotado, sem o realce;
  - `summon_cast` registrado; o grupo `footstep` deixou de estar vazio;
  - **fanfarra de vitória** (`builds/som-da-vitoria`): nenhum som do pacote
    era fanfarra. Ela é sintetizada por `neural_fights/tools/sintetizar_fanfarra.py`
    → `sounds/arena_victory.wav` (1,41 s, −13,6 dB de média) e entra na
    categoria "ui" (no config do Adrian, o "ambiente" está em 0,03 e a vitória
    saía muda);
  - `sound_config.json` do pacote: saíram as 26 chaves que apontavam para
    arquivo inexistente (o jogo cai na mesma cadeia de antes). O config do
    runtime do Adrian não foi tocado.
- **Live**: quem não pagou é recusado antes de qualquer ADIAR. Vale o
  primeiro `!arena`. Pago que não coube (cooldown, teto, saturação, alvo
  morto) vira `RECUSADO` com "reembolso", e o overlay mostra "não coube,
  reembolsado" (`builds/arena-dois-pagantes`). `!banir`/`!desbanir <nome>`
  são só de moderador (`builds/banimento-na-live`). O aposentado ganha um
  lutador novo. O HUD usa o nome atual com a blocklist viva. A saturação não
  conta a mesma área duas vezes. O journal grava o `viewer_id`. 403 de quota
  espera e segue. A quota zera à meia-noite do Pacífico.
- **Torneio**: o resultado vai para a luta SELECIONADA. A chave tem seed
  (`Tournament(seed=)`; o `random_builds` passa o mesmo número que dava ao
  `random.seed`, então a chave de cada seed é a de antes). O retry de empate
  sai da faixa `seed + match_id + tentativa × 1.000.000`; antes colidia com a
  luta seguinte. `fastest_ko`, `longest_fight` e `most_aggressive` (quem tirou
  mais vida por segundo) são preenchidos (`builds/estatisticas-do-torneio`).
- **Gravador**: o ffmpeg que falha (ou mp4 vazio) dá `sucesso: False` com o
  stderr. O fps precisa dividir 60, e a duração precisa ser > 0. Timeline ou
  som pedidos que não saíram dão exit 3. A skill_demo grava num `.tmp.mp4`
  e mata o ffmpeg travado.
- **Launcher**: a roda do mouse vai ao canvas sob o ponteiro
  (`theme.registrar_rolagem`). A Forja não arredonda o dano. Corpo e arma
  aparecem juntos na prévia. A janela cabe na área útil. Fechar no meio de um
  render mata o Godot (`palco.godot.encerrar_todos`). O resumo do wizard usa o
  `Personagem`. O passo 6 recarrega as armas. "Sugerir Tamanhos" usa o
  personagem em edição (e a altura em metros). Os estilos do editor são os do
  catálogo do banco.

**Lote 2: o que MUDA a luta, num lote só** (MOT-1–4, 6–11, 14–21, 30, 31,
lava e o empate do BLD-6). O MOT-5 ficou fora por decisão
(`atordoamento-e-relogio`: manter). Medido no harness, corpus completo (546
lutas, fixture engine), HEAD → lote:

| | antes | depois |
|---|---|---|
| `winrate_p1` (120 espelhos) | 0,458 | **0,500** |
| idem, smoke (48) | 0,458 | 0,521 |
| combos por luta | 2,99 | 3,17 |
| maior combo do corpus (C2) | 9 | 10 → **re-pino** do alvo para 10 |
| status de CC por luta (K2) | 1,766 | 1,760 |
| maior seca p90 | 5,93 s | 5,53 s |
| bloqueios por luta | 1,36 | 1,29 |

Alvos já fora na onda 99 antes do lote (B1, K4, R2_meta, R3_meta) seguem
iguais. O smoke na onda 11 (o gate) passa sem nenhuma violação. Os gates
pesados (`NF_QUALITY_GATE`, `NF_RECORDING_GATE`, `NF_SKILL_GATE`) dão 54
passed. O MOT-6 sozinho (cópia do HEAD só com o coreógrafo novo) não mexeu
no `winrate_p1` (0,458). A paridade de 0,500 é do lote inteiro.

- **O que cada um faz:**
  - MOT-1: o canal manda o status só no 1º tick por alvo (eram 30 queimaduras em 3 s);
  - MOT-2: fonte contínua (Transform, Channel, trap, tick de área/DoT, lava) paga a guarda em proporção ao dano segurado (`DANO_REFERENCIA_GUARDA` = 30) e não conta bloqueio;
  - MOT-3: raiva com teto 1,0, e fonte contínua não enfurece;
  - MOT-4: o eco do Feiticeiro só repete PROJETIL, AREA, BEAM e SUMMON, nunca a Troca de Almas;
  - MOT-6: fluxo do coreógrafo com ângulo normalizado; quem está parado não avança;
  - MOT-7: o bônus de canto vale enquanto o inimigo está no canto e não grava mais em `agressividade_base`;
  - MOT-8: o covarde foge;
  - MOT-9: "posso atacar" usa o meu ângulo;
  - MOT-10: quebrar a armadura dói o golpe inteiro;
  - MOT-11: o cache de perfil de arma é por medidas;
  - MOT-14: vale a melhor janela do quadro;
  - MOT-15: o Ladino esquiva antes da guarda;
  - MOT-17: teleporte da mão na corrente V2;
  - MOT-18: o hit stop usa o maior, sem fila;
  - MOT-19: BEAM canalizável tem duração;
  - MOT-20: dano fracionário em obstáculo;
  - MOT-21: o escape não repete o dash.
- **MOT-16 era alarme parcial**: PUXADO, VORTEX e EMPURRÃO têm efeito real no
  `tomar_dano` desde a Onda 10D. Devolver `False` derrubou o K2 do smoke de
  1,71 para 1,23. Ficou só a limpeza de `sendo_puxado`/`em_vortex`, que não
  tinham leitor.
- **Quirks** (`builds/quirks-sem-efeito`): só os 10 com leitor entram no
  sorteio (`personalities.QUIRKS_ATIVOS`). A auditoria contou 29 sem efeito; a
  medição achou 43:
  - os 29 da auditoria;
  - 13 que só eram citados no mapa de sorteio por traço;
  - "IMORTAL", que só existe como buff.

  Os `quirks_fixos` dos presets ficam.
- **Humores**: MELANCOLICO e EXTASE saíram do catálogo (nenhum produtor), pelo
  mesmo critério dos quirks.
- **Lava** (`builds/lava-do-vulcao`): em pé na poça do Vulcão ou no fogo do
  Inferno, 6% da vida máxima por segundo (`PERIGO_CHAO_DANO_PCT_S`), em ticks
  de 0,5 s, sem RNG. Em 24 lutas do smoke: no Vulcão, ~12% da vida por luta
  e 1 morte pela lava; no Inferno, ~2%. A IA ainda não desvia da poça.
  **Desde 14/10 (tarde) o tempo na poça acumula** (§11): Vulcão 10,3% →
  14,0% da vida por luta.
- **Empate** (`builds/empate-persistente`): três empates não viram mais
  vitória do p1. Vence quem tem mais HP (fração). Com HP igual, vence quem
  tirou mais vida. Ainda igual, decide a paridade da seed (par = p1). O
  `fight.json` leva `desempate: hp|dano|seed`. Evento sem vencedor levanta
  `EmpatePersistente`.
- Re-pinos: `tests/test_corrente_v2_regressions.py` (as 3 digitais de luta,
  chave desligada) e `alvos_qualidade.json` (C2 9 → 10; a descrição do V4
  registra a purga dos humores).

## 11. O fim do vídeo de luta (14/10/2026)

Achado do conferente, gravando pelo gravador de produção (seed 4242, Gunnar
Vexevok × Aurelia Argalacern, Arena, câmera ARENA): o fim era o pior trecho
do vídeo. Depois do K.O. a imagem **congelava** (freezedetect de 39,4 s até o
fim, 42,9 s), o perdedor **sumia** (o corpo caído era pintado em
`COR_CORPO` sobre o chão escuro), sobravam ~0,9 s de silêncio depois da
fanfarra e o pico verdadeiro dava -1,2 dBTP.

**O que mudou** (só o último item mexe na luta):
- **cena pós-K.O. viva** (só desenho, `simulacao.py`): perdedor caído na cor
  dele, com estrelas; ondas de choque no slow-mo; o vencedor pula e sai
  confete depois da fanfarra. Movimento médio por quadro pós-K.O. 0,00003 →
  0,00139 (a luta: 0,00078); congelado pós-K.O.: nenhum.
- **cauda = slow-mo + fanfarra + 0,1 s** (`fight_recorder.cauda_pos_ko_de`,
  a mesma conta no gravador e na timeline do palco; `cauda_pos_ko=None` é o
  padrão). A fanfarra é medida no arquivo que a mistura usaria (runtime >
  pacote > fallbacks), então trocar o wav muda a cauda junto. Sem o arquivo,
  os 3,5 s de antes; nunca menos que `CAUDA_MIN_POS_KO` = 1,5 s. Seed 4242
  na Arena: 3,5 → 2,73 s; silêncio final (-40 dB) 0,91 → 0,17 s.
- **teto de pico verdadeiro** (`mixagem.com_teto_de_pico`, no gravador e no
  mix final do renderer): mede o mp4 e, se passou, refaz com o limitador
  mais baixo devolvendo o integrado. -1,2 → -2,6 dBTP, -16,1 → -16,2 LUFS.
- **a lava acumula** (`PERIGO_CHAO_ESQUECE_S` = 1,0): sair da poça não zera o
  contador; ele só esquece depois de 1 s seguido fora. Antes, quem só
  atravessava (0,1–0,45 s por passagem) nunca levava dano. Vulcão, 24 lutas:
  10,3% → 14,0% da vida por luta (21 → 22 lutas com dano); Inferno 1,75% →
  2,0%. **Queimar a cada pisada foi recusado**: levava a 35%.

**Prova de que a luta só mudou pela lava** (48 lutas headless, 8 arenas × 6
seeds, fixture engine, base `3e5e2a4` × WIP): Arena, Arena Pequena,
Labirinto, Duto, Poço e Torre **36/36 iguais** (vencedor, motivo, duração,
quadros, HP); Vulcão 3/6 e Inferno 5/6 iguais (uma troca de vencedor, Vulcão
seed 103); com `PERIGO_CHAO_ESQUECE_S = 0` (o zerar de antes) **48/48
iguais** à base. Nenhum pino da suíte mudou por causa da lava (o gate de
qualidade passa sem re-pino); o único teste ajustado foi o piso da cauda do
gate de gravação (`test_gravacao_continua_depois_do_ko`: era "≥ 3,0 s",
agora "cobre slow-mo + fanfarra e não passa da conta + 2 quadros").

**Vídeo de prova** (fora do git e do catálogo): `E:\tmp_pytest\prova_fim_luta\`
— `vulcao_4242.mp4` (Gunnar Vexevok × Aurelia Argalacern, seed 4242,
Vulcão, DIRETOR, 1920×1080, sem HUD, largura mínima 5,5 m e espera 2,5 s
como o duelo, pelo `fight_recorder` em subprocesso como o `capture.gravar_uma`).
K.O. aos 21,57 s **pela lava** (um tique de 22,4 em Gunnar), vídeo de 24,30 s:
**cauda 2,73 s** (slow-mo 21,567 → 22,767, fanfarra 22,767 → 24,18);
silêncio final 0,16 s; nenhum congelado na cauda (freezedetect n=0,001
d=0,3); **-2,3 dBTP**, -17,7 LUFS, LRA 5,0, 1 tentativa de pico (já dentro);
11 arquivos de som. Quadros: `cauda_1_ko.png` (21,567), `cauda_2_slowmo.png`
(22,2), `cauda_3_perdedor_caido.png` (23,5), `cauda_4_ultimo.png` (24,25).
Gravação: 37 s.

**Reprovado pelo conferente (eb2444a) e consertado** — os números de áudio e
de cauda batiam; os defeitos eram de imagem (só desenho e câmera, nada da
luta):
1. **o confete cobria o rosto do vencedor** (18% do disco no último quadro,
   em toda luta): nascia no centro do rosto e era desenhado por cima. Agora
   nasce num anel FORA do rosto (`FESTA_BOCA_RAIOS` = 1,3 raio), abre num
   leque para cima e para os lados e nenhum pedaço é desenhado dentro do
   disco do rosto (nem sobre o nome); o alcance caiu de 6 para 3,5 raios
   (`FESTA_ALCANCE_RAIOS`, com piso/teto 24–34% do lado menor da tela) para
   caber no quadro com o vencedor a 15%+. O gravador e a timeline dizem ao
   desenho quanto a festa dura (`anunciar_fim_da_festa` → `_festa_dura_s`) e
   nenhuma rajada nasce a menos de 0,6 s do fim: o último quadro mostra a
   rajada de 0,7 s já aberta, não a de 1,40 s recém-nascida. A geometria
   mora em `utils/config.py` (`FESTA_*`), lida pelo desenho e pela câmera.
2. **o "ACABAR" depois do K.O.**: o rótulo do plano sob o corpo
   (`Simulador._desenhar_rotulo_do_plano`) some com `round_finalizado`, e a
   `serie_plano` do gravador ganha uma amostra vazia no quadro do K.O. (o HUD
   do renderer também mostrava "ACABAR" sob as barras a cauda inteira).
3. **câmera DIRETOR na cauda** (`Câmera._enquadrar_pos_ko`): com um morto,
   enquadra os dois se o vencedor ainda ocupa ≥ 15% da largura
   (`diretor_pos_ko_fracao_min`), senão só o vencedor; a caixa leva o pulo
   (`FESTA_ALTURA_PULO`), o nome e o alcance do confete, e cabe nos **60% de
   cima e fora dos 12% da direita** (`diretor_pos_ko_area` = (0, 0, 0,88,
   0,60)). Transição exponencial (`diretor_pos_ko_lerp` = 3,5/s), sem salto.
   **O veredito do duelo saiu do meio da tela** (passava sobre o rosto do
   vencedor) para a **zona segura das plataformas** (decisão da coordenação,
   15/10): inteiro entre 62% e 76% da altura (`renderer.VEREDITO_ZONA`; o
   bloco nome + cartel, com contorno, é centrado na faixa) e no máximo 74% da
   largura, centrado (`VEREDITO_LARGURA_MAX`), fora da coluna de botões. Os
   ~20% de baixo e os ~12% da direita (`ZONA_DAS_PLATAFORMAS`; desde 18/10 com o `topo` de
   10%, §12) o TikTok e o
   YouTube Shorts cobrem com legenda, canal e botões; um 1º conserto a 0,80
   caía ali. HUD, identidade e callouts do duelo terminam antes de 62%
   (teste). O HUD do topo (barra e nome do p2) entrava nos 12% da direita
   e nos 10% de cima: **consertado em 18/10 (§12)**.
4. **projétil/orbe/invocação parado no ar**: vivos no K.O., somem em fade em
   0,3 s de tempo real (`FADE_OBJETOS_POS_KO_S`; a tela antes deles é
   guardada e devolvida com opacidade 1 − fade).

Luta igual até o K.O.: 48 lutas headless (8 arenas) iguais às do eb2444a;
6 lutas pelo gravador (Torre, Vulcão ×2, Duto, Poço, Arena Pequena;
540×960, DIRETOR do duelo) com vencedor, motivo, duração, K.O., HP, dano,
sons, narrativa e série de HP até o K.O. **iguais à base `3e5e2a4`** (com e
sem a lava nova). Prova pelo caminho real do duelo (`main.py duelo --p1
"Gunnar Vexevok" --p2 "Aurelia Argalacern" --seed 4242 --arena Torre|Vulcao`,
na worktree, runtime numa cópia do banco), vídeo final do renderer
(loudnorm), 1080×1920, em `E:\tmp_pytest\prova_fim_luta3\{torre,vulcao}\`
(a de `prova_fim_luta2` é a do veredito a 0,80, superada) com quadros da
cauda a cada 0,25 s (`cauda_NN_<t>s.png`), as cópias com a zona das
plataformas e a faixa do veredito desenhadas (`zona\*_zona.png`), as folhas
`folha_zona_torre.png`/`folha_zona_vulcao.png` e a medição por quadro
(`zona_torre.json`/`zona_vulcao.json`):

| | Torre | Vulcão |
|---|---|---|
| K.O. no clipe / vídeo | 25,20 / 27,93 s | 15,84 / 18,57 s |
| cauda | 2,73 s | 2,73 s |
| pico / integrado | -1,6 dBTP / -15,5 LUFS | -1,8 dBTP / -15,6 LUFS |
| silêncio (-40 dB, 0,1 s) e congelado (0,001, 0,3 s) na cauda | nenhum | nenhum |
| quadro | os dois | só o vencedor |
| vencedor (diâmetro / largura) no fim | 15,3% (17,4% com a área de 70%) | 15,1% (17,2% com a área de 70%) |
| plano no HUD depois do K.O. | vazio (11 amostras) | vazio (11 amostras) |
| rosto do vencedor fora da zona das plataformas e acima de 62% | 12/12 quadros | 12/12 quadros |
| veredito (4 quadros) | y 1269–1383 px (66,1–72,0%), x 158–916 (≤ 84,8%) | y 1269–1383 px, x 160–916 |

**Segunda conferência (ffbb80b): mais dois, consertados** (15/10):
5. **Torre: a cauda mostrava até 47% da largura fora da arena** (a parede
   da direita ia de x≈810 antes do K.O. a x≈565 no último quadro). O centro
   pós-K.O. não passava pelo limite de arena e a caixa da festa atravessava
   a parede com o vencedor encostado nela. Agora a caixa da festa é cortada
   pela arena (`Câmera._cortar_na_arena`), o centro passa por
   `_limitar_centro_a_arena(cx, cy, zoom, fora=diretor_pos_ko_fora_arena)`
   — na cauda o limite é **0** (a luta continua com os 35% de
   `diretor_fora_arena`) — e, se isso cortar o vencedor, **o rosto e o nome
   ganham** (`_garantir_rosto`: o centro anda o mínimo para a
   `caixa_do_rosto` caber na área); o confete pode sair. Com o corpo
   encostado na parede, só a faixa da coluna de botões (12%) + margem pode
   mostrar o lado de fora. Teste com o vencedor encostado: 47,6% sem o
   conserto (caso zero, com o corte e o limite desligados), 17% com ele;
   longe da parede, 0%.
6. **Vulcão: o "134" sobre o olho do vencedor durante o "ACABOU"**: o texto
   flutuante vive no relógio da luta, que o slow-mo quase para. Os textos
   vivos no K.O. somem em fade de 0,3 s de tempo real, como os projéteis
   (`Simulador._desenhar_textos`). O "FATAL!" do K.O. some junto. Antes do
   K.O. (15,2–15,84 s) nada mudou.

Luta igual até o K.O. de novo: 6/6 pelo gravador contra a base `3e5e2a4`
e 48/48 headless. Provas em `E:\tmp_pytest\prova_fim_luta4\{torre,vulcao}\`
(mesmo caminho e mesmas medidas da 3; as de `prova_fim_luta3` ficam
superadas), mais `fora_da_arena_{torre,vulcao}.json`: a mesma luta
re-simulada pelo gravador com a câmera registrada a cada passo, e a fração
da tela fora da arena (largura e altura) em cada quadro da cauda; antes do
K.O. ela bate com a medida do conferente (25%, parede em x≈810). E
`vulcao\texto_134_rosto\sequencia_15.84_a_16.24.png` mostra o fade do "134".

| | Torre | Vulcão |
|---|---|---|
| fora da arena, largura (antes do K.O. → K.O. → último quadro) | 25,3% → 25,2% → **16,9%** (era 47%) | 0% em todos |
| fora da arena, altura | 0% em todos | 19,4% no K.O. (herdado da luta) → 0,0% |
| rosto fora da zona das plataformas e acima de 62% | 12/12 | 12/12 |
| veredito na faixa 62–76% e fora da zona | 4/4 | 4/4 |
| "134" sobre o vencedor | — | some entre 15,84 e ~16,14 s (0,3 s de tempo real) |
| cauda / pico / integrado | 2,73 s / -1,6 dBTP / -15,5 LUFS | 2,73 s / -1,8 dBTP / -15,6 LUFS |

**Terceira conferência (05bf5f0): uma regressão, consertada** (15/10):
7. **Vulcão: o vencedor subia para dentro do letreiro "ACABOU"** (nome
   atrás do "BOU" ~16,3 s, cabeça ~16,5 s, até ~16,77 s): o limite vertical
   novo descia a câmera já no K.O. O letreiro é do renderer (o callout do
   K.O., `fight_callouts`, 0,9 s a partir do K.O.) e a câmera é do gravador;
   a ponte:
   - `runner.reserva_do_letreiro(perfil)` mede a **caixa real** do letreiro
     (`renderer.letreiro_do_ko`/`caixa_do_letreiro`: cada texto de K.O. do
     config desenhado pelo próprio renderer no pico do pop-in, 1,35×) e a
     duração do callout (+0,05 s). Celular: borda de baixo 0,2599 da altura
     (y 356–499 px no pop-in, 374–479 depois); normal 0,2713;
   - `capture.gravar_uma(reserva_pos_ko=)` → `fight_recorder
     --reserva-pos-ko TOPO,SEGUNDOS` → `Câmera.reserva_pos_ko`; o Simulador
     escreve `cam.t_pos_ko` (relógio de parede) antes de cada atualização
     pós-K.O.; só os perfis com câmera DIRETOR recebem;
   - enquanto o letreiro está na tela, o topo da área pós-K.O.
     (`Câmera._area_pos_ko`, usada pelo enquadramento e pelo
     `_garantir_rosto`) fica na borda de baixo dele (a margem de 4% do lado
     menor fica entre os dois), e no quadro de agora o rosto é empurrado
     para baixo dele (`_tirar_rosto_do_letreiro`: um ajuste pequeno, ou, no
     1º quadro pós-K.O. de uma luta que acabou com o vencedor no alto, uma
     vez só, junto com o K.O.). Quando ele some, o topo volta exponencial
     (só desce, sem salto).
   Teste genérico (`random_builds/tests/test_letreiro_do_ko_regressions.py`):
   Vulcão e Torre, 3 cenas cada (longe, perto, encostado na parede), o
   letreiro medido a cada passo com o pop-in: rosto+nome nunca cruzam o
   letreiro enquanto o alfa > 0; o caso zero (sem reserva) acusa.

Luta igual até o K.O.: 6/6 pelo gravador (com a reserva) contra `3e5e2a4` e
48/48 headless. Provas em `E:\tmp_pytest\prova_fim_luta5\{torre,vulcao}\`
(as da `prova_fim_luta4` ficam superadas), mais
`letreiro_x_vencedor_{torre,vulcao}.json` (a mesma luta re-simulada pelo
gravador com a mesma reserva; em cada um dos 82 quadros da cauda: caixa do
rosto+nome na tela, caixa real do letreiro na idade daquele quadro, se
cruzam, e a fração fora da arena) e `tira_letreiro_{torre,vulcao}.png`
(K.O. → K.O.+1 s a cada 0,1 s):

| | Torre | Vulcão |
|---|---|---|
| quadros com o letreiro na tela | 28 | 28 |
| quadros em que rosto+nome cruzam o letreiro | **0** | **0** (era ~16,3–16,77 s) |
| menor folga rosto ↔ letreiro | 22 px (no pop-in do K.O.) | 22 px |
| fora da arena, largura (máx. / último quadro) | 25,1% (K.O., herdado) / 16,9% | 0% |
| fora da arena, altura (máx. / último) | 0% | 21,3% (K.O., herdado) / 0,1% |
| rosto fora da zona das plataformas e acima de 62%; veredito na faixa | 12/12; 4/4 | 12/12; 4/4 |
| cauda / pico / integrado | 2,73 s / -1,6 dBTP / -15,5 LUFS | 2,73 s / -1,8 dBTP / -15,6 LUFS |

**Quarta conferência (c34e6b7): um degrau, consertado** (15/10):
8. **Vulcão: a câmera saltava ~34 px no 1º quadro com o "ACABOU"** (6 px
   antes), sem o vencedor estar atrás do letreiro (folga de 44 px). A
   garantia por quadro (`_tirar_rosto_do_letreiro`) usava a caixa do rosto
   com o pulo MÁXIMO da festa, e no K.O. o pulo nem começou: ~50 px alta
   demais. Agora:
   - a garantia por quadro usa o **pulo de agora** (o Simulador escreve
     `cam.pulo_pos_ko`, `Simulador._fracao_do_pulo`; 0 até a fanfarra); o
     máximo só entra no alvo (`caixa_do_rosto(..., pulo=None)`);
   - a garantia entra **dentro** do passo do enquadramento, e no 1º segundo
     depois do K.O. (`diretor_pos_ko_degrau_ate_s` = 1,0, o slow-mo com o
     letreiro) o passo inteiro tem teto de degrau: 5 px por atualização
     (`diretor_pos_ko_degrau_max_px`; o gravador atualiza a 60 Hz e grava a
     30 fps → até 10 px por quadro), medido em 9 pontos da tela
     (`_degrau_na_tela`: 10/50/90% da largura × 30/45/60% da altura). Depois
     de 1 s o enquadramento anda livre para a festa chegar ao quadro dela.
   Testes (`test_letreiro_do_ko_regressions.py`): nenhum degrau > 12 px por
   quadro do K.O. ao K.O.+1 s em Vulcão e Torre (fora a cena em que a luta
   acaba com o vencedor atrás do letreiro, que sai de uma vez junto com o
   K.O.); caso zero: com o pulo máximo, a cena do Vulcão (44 px de folga)
   leva um empurrão > 12 px; com o pulo de agora, 0.

Luta igual até o K.O.: 6/6 pelo gravador e 48/48 headless. Provas em
`E:\tmp_pytest\prova_fim_luta6\{torre,vulcao}\` (as da 5 ficam superadas),
com o mesmo conjunto da 5 e `degrau_{Torre,Vulcao}.json`: a mesma luta
re-simulada pelo gravador com a câmera registrada a cada quadro capturado e
o degrau (máximo dos 9 pontos e o do centro) de quadro a quadro.

| | Torre | Vulcão |
|---|---|---|
| maior degrau do K.O. ao K.O.+1 s (9 pontos / centro) | 8,4 / 5,9 px | 10,4 / 7,1 px (era ~34 no 477) |
| maior degrau antes do K.O. (a luta, para comparar) | 12,6 px | 12,9 px |
| maior degrau no resto da cauda (o enquadramento solto depois de 1 s) | 25,4 px | 31,8 px |
| rosto+nome × letreiro (28 quadros com ele) | 0 cruzam, folga mín. 118 px | 0 cruzam, folga mín. 42 px |
| rosto fora da zona e acima de 62%; veredito na faixa | 12/12; 4/4 | 12/12; 4/4 |
| cauda / pico / integrado | 2,73 s / -1,6 dBTP / -15,5 LUFS | 2,73 s / -1,8 dBTP / -15,6 LUFS |

(A folga do `letreiro_x_vencedor_*.json` da prova 6 usa o pulo de agora —
0 enquanto o letreiro está na tela —, como a câmera; o da prova 5 usava o
pulo máximo e por isso dava 22 px.)

## 12. O HUD do topo na zona segura (18/10/2026)

Decisão `builds/hud-do-topo-zona-segura` (orquestrador, delegada pelo Adrian):
o HUD do celular ficava em y 56–168 de 1920 (2,9–8,8% da altura), sob as
abas "Seguindo | Para você"/LIVE do TikTok e os ícones do Shorts, e o do p2
ia até x 1042 (96,5% da largura), sob a coluna de botões.

**Como é agora** (`renderer._layout_do_topo`, só o 9:16; o 16:9 não é
publicado e segue igual):
- `ZONA_DAS_PLATAFORMAS` = topo 10%, baixo 20%, direita 12% — a mesma
  constante do veredito, sem número solto;
- empilhados, sem se cruzar, abaixo do topo e à esquerda de 88%: **HUD**
  (nomes, molduras, barras, plano), **identidade + selo** (só o 1,5 s
  inicial) e **callouts**. Cada altura sai da fonte no maior corpo com a
  amostra de pior caso (capitular acentuada, descendentes);
- o p2 é o espelho do p1 dentro da faixa segura (0–950 px): barras de 400
  px em x 43 e 507, calha de 64 px;
- callout que NASCE com a identidade na tela fica abaixo dela a vida toda
  (`callout_cy_identidade`, sem pular quando ela some); os outros, e o build
  e a estreia, logo abaixo do HUD. Em 83 de 120 duelos do disco há callout
  no 1,5 s inicial;
- a câmera da cauda: `runner.reserva_do_letreiro()` ganhou `hud` (borda de
  baixo do HUD pintado, `renderer.hud_do_topo`, 0,1688 no celular), o
  gravador aceita `--reserva-pos-ko TOPO,SEGUNDOS,HUD` e
  `Câmera._topo_base_pos_ko` põe o topo da área da festa abaixo do HUD a
  cauda inteira. Sem isso, um vencedor no alto da arena terminava com o rosto
  em y 46–56 px (sob as abas; teste, caso zero). O letreiro desceu junto
  (reserva `topo` 0,2599 → 0,2656, lida da caixa real como antes).

| celular, px (1080×1920) | antes | depois |
|---|---|---|
| HUD (nomes, barras, plano) | y 56–168, x 39–1042 (2,9–8,8%; 96,5%) | y 209–324, x 39–912 (10,9–16,9%; 84,4%) |
| identidade + selo | y 201–294, x 40–1041 | y 339–433, x 40–910 |
| letreiro do K.O. no pop-in | y 356–499 | y 367–510 (K.O./NOCAUTE/ACABOU) |
| callout nascido com a identidade | y 356–499 | y 483–626 |
| veredito | y 1260–1389 | igual |

**Medido.** Luta igual: 48/48 headless (8 arenas × 6 seeds; vencedor,
motivo, duração, quadros, HP) e 6/6 pelo gravador (Torre, Vulcão ×2, Duto,
Poço, Arena Pequena; dano, sons, narrativa e série de HP até o K.O., com a
reserva nova contra a base `5890566` com a antiga). Prova pelo caminho real
(`main.py duelo --p1 "Gunnar Vexevok" --p2 "Aurelia Argalacern" --seed 4242
--arena Torre|Vulcao`, na worktree, runtime numa cópia do banco), vídeo final
1080×1920 em `E:\tmp_pytest\prova_hud\{torre,vulcao}\`: quadros a cada 1 s
da luta (`luta\`) e a cada 0,25 s da cauda (`cauda\`), cópias com a zona
desenhada (`zona\`), `folha_zona.png`, `medida_hud.json` (o que o renderer
pintou: diferença quadro a quadro, no índice exato, entre o vídeo final e o
clipe cru) e `cauda_x_hud_*.json` (a luta re-simulada pelo gravador com a
mesma reserva, câmera a cada passo):

| | Torre | Vulcão |
|---|---|---|
| HUD pintado no vídeo (38 / 28 quadros) | y 208–327, x 39–911 | y 208–327, x 40–911 |
| px pintados nos 10% de cima / na coluna dos 12% na faixa do HUD | ≤ 4 / ≤ 4 (bordas do jogo re-codificadas: rastro da arma, contorno do lutador; nada do HUD) | ≤ 2 / 0 |
| rosto+nome do vencedor sob o HUD na cauda (82 quadros) | 0, folga mín. 185 px | 0, folga mín. 56 px |
| rosto+nome × letreiro (28 quadros com ele) | 0 cruzam, folga mín. 107 px | 0 cruzam, folga mín. 31 px |
| vencedor no último quadro (diâmetro / largura) | ~18,7% (era 15,3%) | ~16,7% (era 15,1%) |
| duração / integrado | 27,93 s / -15,5 LUFS | 18,57 s / -15,6 LUFS |

**O que piorou na 1ª rodada (434c553):** a câmera DIRETOR da luta não
sabia do HUD, que passou a cobrir o alto da arena em vez do vazio acima
dela: lutador (corpo + nome) sob o HUD, Torre 12 → 41 de 790 quadros,
Vulcão 7 → 44 de 647; e os callouts longos entravam nos 12% da direita e
saíam da tela no pop-in. **Consertados na 2ª rodada** (decisão
`builds/camera-da-luta-sob-o-hud`, 19/10):

- **Câmera da luta** (`Câmera._atualizar_modo_diretor`, só com `hud` na
  reserva, que agora só o 9:16 recebe — o 16:9 voltou a ser enquadrado como
  antes, também na cauda): o zoom necessário não conta a faixa do HUD como
  altura útil (`_zoom_necessario_da_luta`: margem de cima = linha do HUD +
  folga crítica + ~40 px do nome), o centro desce para o meio da área abaixo
  dele (`_desvio_do_centro_da_luta`), lutador sob o HUD conta como urgente no
  pan, e no fim de cada passo nenhum corpo + nome (`caixa_do_rosto`) fica
  acima da linha (`_tirar_lutadores_do_hud`: sobe o mínimo; se empurrar o
  outro para fora por baixo, abre até o zoom que cabe). Sem `hud`, o mesmo
  código de antes (teste).
- **Callouts** (`renderer._fonte_do_callout`, só no 9:16): centrados na
  faixa segura (x 475) e, no pico do pop-in (1,35x), inteiros entre a margem
  e 88% − margem (x ≤ 907). O texto que não cabe encolhe de 1 em 1 px, só o
  necessário; os curtos ficam no corpo de sempre (K.O., ACABOU, PARRY!,
  VIROU!). Os 35 textos do config: pico em x 60–894. O letreiro do K.O.
  não mudou de altura (reserva `topo` 0,2656).

**Medido na 2ª rodada.** Luta igual: 48/48 headless; 6/6 pelo gravador
(vencedor, motivo, duração, K.O., HP, dano, narrativa, série de HP). Os
`sons` têm os mesmos ids, tempos e pitch; só `volume`/`pan` mudam (máx.
0,02 de volume), porque o ouvinte do som é a câmera (`listener_x`) e ela
anda diferente. Provas em `E:\tmp_pytest\prova_hud2\{torre,vulcao}\`
(mesmo caminho real e mesmas medidas da 1ª; `lutador_x_hud_*.json` conta
quadro a quadro, pela câmera do gravador re-simulada, lutador × HUD na
luta e o vencedor na cauda; `folha_zona.png`):

| | Torre | Vulcão |
|---|---|---|
| quadros da luta com lutador sob o HUD | **0 de 790** (era 41) | **0 de 647** (era 44) |
| rosto do vencedor sob o HUD / × letreiro (cauda) | 0 / 0 (folgas 186 / 250 px) | 0 / 0 (folgas 57 / 142 px) |
| px pintados nos 10% de cima / na coluna dos 12% | 0 / 3 (ruído do x264) | 1 / 5 (ruído) |
| HUD pintado no vídeo | y 205–323, x 40–911 | y 205–323, x 39–911 |
| fora da arena na tela, máx. (largura / altura) | 25,3% / 0% | 0% / 25,3% (era 19,6%; sob o HUD, dentro dos 35% da luta) |
| duração | 27,93 s | 18,57 s |

Testes: `random_builds/tests/test_hud_zona_segura_regressions.py`
(HUD, callouts com todos os textos do config, câmera da luta em 6 cenas com
pulo e parede; cada um com o seu caso zero).

**3ª rodada (conferente de 19/10, mesmo nó): a garantia no quadro DESENHADO.**
O conferente achou, no Vulcão (quadros 345–348 do clipe, 11,50–11,60 s), o
caído encostando no canto de baixo à direita do HUD no empurrão do ESMAGAR,
com o nome na faixa dele, e o lutador cortado pela coluna da direita em
4,83 s, 11,23–12,03 s e 14,13–14,23 s (igual na base). Causa: o Simulador
atualiza a câmera no COMEÇO do passo e move o mundo depois; num arremesso o
lutador anda ~120 px por passo, e a garantia da 2ª rodada (e a medida
interna dela, feita dentro de `atualizar`) via o mundo de antes. Agora:

- `Simulador._update_step` chama `cam.depois_do_passo(p1, p2)` depois de
  mover o mundo, antes do desenho (só lê posições; sem `hud` não faz nada);
- a garantia (`Câmera._manter_na_area`) vale para a **área da luta**: abaixo
  do HUD, à esquerda da coluna dos 12% (`diretor_pos_ko_area[2]`) e dentro
  da tela, para `caixa_do_lutador` (corpo com os anéis + nome a `raio + 22`
  + o ícone de status acima dele + o plano embaixo; 58/30 px de tela). O
  zoom necessário e o centro contam essas margens; o push-in do "momento"
  (ESMAGAR, arremesso) não fecha além do que cabe; se os dois não cabem, o
  quadro abre;
- **teto de tranco:** a correção gasta um orçamento de 26 px por quadro de
  30 fps (`diretor_area_degrau_max_px`, por passo `dt × 30`), ou o tanto que
  a câmera já andou sozinha no passo, se for mais (o quadro de emergência de
  quem é arremessado já anda 90–190 px/quadro na base) — nunca mais que o
  dobro do que já existia.

**Medido** (base = `5890566`, antes do HUD; 2ª = `11477d2`):

| | Torre 2ª → 3ª | Vulcão 2ª → 3ª |
|---|---|---|
| **detector de pixels** no clipe cru (`detector_px2`: mancha grande da cor do corpo + o nome azul/vermelho logo acima; nada da câmera), 756 / 476 quadros: sob o HUD | 0 → **0** | 1 → **0** |
| idem, na coluna dos 12% da direita | 32 → **0** | 60 → **0** |
| idem, cortado pela borda da tela | 7 → **2** (610–611) | 12 → **0** |
| caixa da câmera NO DESENHO (`area_desenho_*.json`), 790 / 647 quadros da luta (base `5890566` entre parênteses): sob o HUD | (46) 6 → **1** | (50) 7 → **2** |
| idem, na coluna da direita | (84) 65 → **0** | (127) 125 → **4** |
| idem, cortado pela borda | (12) 10 → **3** | (36) 33 → **0** |
| maior degrau da câmera na luta (9 pontos) | (245) 246 → 227 px | (197) 349 → 190 px |

Os quadros que sobram são todos o começo de um arremesso, em que o lutador
anda mais rápido que o teto de tranco: Vulcão 515–518 do bruto (= 344–347
do clipe, o do conferente: o ícone de status e o anel claro **encostam** na
linha do HUD e na coluna, sem cruzar no pixel —
`E:\tmp_pytest\prova_hud3\vulcao_arremesso_344_349.png`) e 593–594; Torre
416 e 643–645 (o "ESTATELOU" joga o Gunnar contra a borda da esquerda por 2
quadros do clipe, 610–611 — `torre_borda_608_612.png`).

Luta igual: 48/48 headless e 6/6 pelo gravador (vencedor, motivo, duração,
K.O., HP, dano, narrativa, série de HP); os `sons` mantêm ids, tempos e
pitch, e só `volume`/`pan` mudam (máx. 0,10: o ouvinte é a câmera, que agora
anda também para a esquerda da coluna). A fração da tela fora da arena subiu
(Torre 30,2% da largura, Vulcão 31,3% da altura; a luta aceita 35%), quase
toda sob o HUD e a coluna. Provas em `E:\tmp_pytest\prova_hud3\{torre,vulcao}\`
(mesmo caminho real), `detector2_{torre,vulcao}.json` (o detector de pixels
quadro a quadro), `area_desenho_*.json`, `cauda_x_hud_*.json` e
`folha_zona.png`. Teste com o caso zero na luta de verdade:
`ArremessoDoVulcao4242Tests` (os dois lutadores num fixture,
`random_builds/tests/fixtures/duelo_4242/`; o gravador até 20,5 s, ~45 s).

## 13. Semana 1 do plano: o confronto, em inglês (20/10/2026)

`docs/PLANO.md`, semana 1 (o espelho é o Orbitality: título com o confronto,
luta no quadro 0), mais a decisão `geral/canal-em-ingles` (o que o público vê
vai em inglês; código e docs seguem em português). Só texto e tela: a luta
não muda.

- **Título** (`publicacao.json → titulos.duelo`): `{lado1} VS {lado2} — who
  wins?`, ex. "Tactical Knives VS Kusarigama — who wins?". O rótulo de cada
  lado é o **estilo da arma** do personagem no banco, traduzido
  (`builds/publicar/confronto.py`); mesmo rótulo dos dois lados desempata pela
  classe ("Longsword Ninja VS Longsword Monk"), depois pelo elemento da arma
  ("Flame Longsword"), depois pelo primeiro nome ("Aldric's Longsword"). Arma
  sem tradução cai na classe; sem classe, no nome. O duelo novo grava o
  rótulo em `fight.json → luta.confronto` (o título não muda se o banco
  mudar); duelo antigo é rotulado pelas fichas do próprio `fight.json` + banco.
- **Descrição = legenda do TikTok** (`tiktok.py` só manda a descrição): abre com
  "{lado1} VS {lado2}: who wins? Pick your side in the comments.", depois os
  nomes. A arena saiu (os nomes das arenas são portugueses). Hashtags:
  `#shorts #simulation #battle #whowins #gamedev`.
- **Rodízio** (`arena/rodizio.py`): o par ocupado é medido pelo título NOVO
  (`titulo_do_par(..., fichas)`, `titulos_do_disco`, os do disco pelo título
  exato do catálogo). Sem as fichas a checagem não veria o confronto (teste,
  caso zero).
- **Faixa do topo** (`renderer._desenhar_faixa`): na linha dos nomes do HUD,
  "Sword-Spear VS Longsword" centrado na faixa segura, cada lado na cor do
  lutador, a luta inteira, no mesmo corpo máximo dos nomes (só encolhe): o HUD
  não cresce e a reserva da câmera (`hud_do_topo`) não muda. O nome próprio
  sai do HUD e vai para a identidade (nome · classe · cartel) e continua
  sobre o lutador, desenhado pelo jogo.
- **"WHO WINS?"** escrito desde o quadro 0, na identidade (1,5 s), entre a
  linha de nome e o selo (`_layout_do_topo → pergunta_y`); o callout que nasce
  com a identidade desce junto (`callout_cy_identidade`).
- **Tudo da tela em inglês** (`builds/publicar/ingles.py`, mapa explícito,
  nada de LLM; `DueloTimelineBuilder._em_ingles`): classe e cartel (4W-2L),
  selo (REMATCH, TITLE ON THE LINE, "X IS ON A 4-WIN STREAK"), callouts (o
  modelo português que gerou o texto vira o inglês de mesmo índice), plano do
  HUD (PRESSURE, GUARD BREAK…), tipo de K.O. do veredito e a capa (rótulo
  sob cada retrato). O texto que o **jogo** desenha no clipe (plano sob o
  lutador, "CRÍTICO!") vai trocado pelo gravador só no duelo:
  `match_config["textos_da_tela"]` (`fight_recorder --textos-da-tela`,
  `capture.gravar_uma(textos_da_tela=)`, `runner._textos_da_tela("duelo")`),
  lido em `Simulador._texto_da_tela` (só exibição). Build, estreia e torneio
  não mudam.
- **Voz no quadro 0** (acréscimo, `docs/pesquisa/som-ganchos-e-musica.md`
  item 2): "Shuriken versus Sentinels, who will win?", o mesmo rótulo da
  faixa, pela **en-US-GuyNeural** do edge-tts (+12%), em
  `builds/content/voz_do_duelo.py` → `<duelo>/voz_gancho.wav` +
  `voz_gancho.json`. Só o edge: sem ele o duelo sai sem a voz (a pergunta
  escrita fica), nunca pelo SAPI pt-BR. O silêncio que o edge põe no começo
  sai (a voz começava aos 0,195 s; agora 0,023 s). Na mixagem
  (`render(..., voz_sobre_o_jogo=True)`, só o duelo) o **som da luta** abaixa
  sob a voz, como a música já abaixava: sem isso a voz ficava 5,1–5,6 dB
  ABAIXO dos golpes; com isso, 8,9–10,7 dB acima. As cópias da voz que só
  controlam o compressor ganham `apad`: o `sidechaincompress` acaba com a
  entrada de controle e o 1º render saiu com o áudio parando aos ~2,4 s
  (teste de integração com ffmpeg). A trilha não mudou (semana 2).
- **Quadro 0**: o duelo já não tinha intro nem contagem (o clipe começa no
  1º passo da luta; em `duelo_00141` os dois se chocam aos 0,5 s e o
  freezedetect não acha congelado nos 4 s iniciais). Nada a cortar.

**Medido.** Estoque real (`outputs/`, só leitura): 139 duelos, 28 não
publicados, **0 títulos repetidos** entre os não publicados com o formato
novo, 128 chaves distintas no disco inteiro, maior título 52 caracteres.
Banco vivo (184 armas, 171 personagens): tudo traduz. Luta igual com e sem o
mapa de textos: **6/6** pelo gravador (vencedor, motivo, durações, HP, dano,
séries de HP e plano, narrativa, K.O.). Testes:
`random_builds/tests/test_confronto_semana1_regressions.py` e
`test_ingles_do_duelo_regressions.py` (falham se aparecer arma, classe,
elemento, plano ou callout sem tradução, no catálogo do motor, no config ou no
banco vivo).

**Prova** (`E:\tmp_pytest\semana1\`, caminho real `main.py duelo` na
worktree, runtime numa cópia do banco, fora do catálogo de produção):
`duelo_00002` (seed 4242, Helga o Protetor × Nyxaris Cinzamordaca, "Shuriken
VS Sentinels — who wins?", 28,1 s, áudio 28,1 s) e `duelo_00001` (seed
20102026, "Rope Dart VS Tactical Knives", K.O. aos 3,1 s, 5,9 s). Quadros 0,
1 s, meio e fim, capa, `*_medidas.json` e `catalogo_prova.txt` (título e
legenda que a publicação leria). Quadro 0 → quadro 1 no `duelo_00002`: 77 mil
pixels da arena mudam (média 7,2/255); 0 → 0,5 s, 25,9.

**Epíteto do nome, só na exibição** (decisão do orquestrador, 20/10): o banco
guarda "Helga o Protetor"; o duelo mostra "Helga the Protector"
(`ingles.EPITETOS`, os `TITULOS` do `neural_fights/tools/gerador_database.py`
nos dois gêneros, mais "das Sombras" → "of the Shadows" e afins;
`ingles.nome`, que preserva o "#2" do desempate). Vale na identidade, no selo,
no veredito, na descrição (`catalogo.campos_do_confronto`, `{p1}`/`{p2}`) e no
nome que o JOGO escreve sobre o lutador e sobre o caído
(`Simulador._nome_na_tela`, pelo mesmo `textos_da_tela`; o nome traduzido
pode ir a 24 caracteres em vez de 18, senão "Helga the Protecto"). O nome
próprio fica. Teste: todo título do gerador tem tradução e nenhum dos 171 nomes
do banco vivo sai com epíteto português.

**Reprovação do conferente (20/10, capturas em `E:\tmp_pytest\conferente\semana1\`) e o que mudou:**
1. **O cartão final responde à pergunta:** "SHURIKEN WINS!" (o rótulo do
   vencedor, `veredito.titulo`, por `ingles.vence`: rótulo no plural leva
   "WIN!", "SENTINELS WIN!", 18 dos 54 estilos), e embaixo, pequeno,
   "Nyxaris Cinzamordaca · KO · 1W-0L".
2. **Cartão no centro da faixa** (x = `direita // 2`, 475 px) e inteiro antes de
   `VEREDITO_X_MAX` (900 px); centrado na tela ele ia a x 940, sobre a coluna.
3. **Contraste:** pílula `PILULA` (12,10,24, alfa 210) atrás da faixa e de cada
   lado da identidade; a cor do time é clareada (`cor_legivel`) até 4,5:1 sobre
   `fundo_da_pilula()` (o azul (36,81,243) dava 2,6–3,0:1). A pílula da faixa vai
   de 10% + 2 px até `FAIXA_FOLGA_HUD` = 8 px antes da moldura das barras (eram
   1–2 px); o texto encolhe para caber nela.
4. **Voz medida no mp4 FINAL** (depois do limitador e do `loudnorm`): o gêmeo é a
   mesma mistura com a voz muda (`_volume_da_voz_na_mistura` = 0, a mesma voz como
   controle do abaixamento). Os +10,7 dB de antes do master davam +4–6 no
   arquivo. Agora, só no duelo: voz comprimida (`acompressor` ratio 6, makeup 5),
   luta e música abaixadas mais forte sob ela (ratio 20). Medido no
   `duelo_00002` remontado: **+15,9 dB** durante a fala e a luta no 1 s seguinte
   +0,8 dB acima da voz (teto pedido: 5).
5. **Duelo < 15 s não é publicável:** pendência "duelo curto" no catálogo
   (`catalogo.DUELO_MINIMO_S`, trocável por `publicacao.json → duelo_minimo_s`,
   pela `total_duration` do `edit_plan.json`). No estoque de 20/10: **10 dos 28**
   ficam presos (8,8 a 14,5 s).
6. Descrição: "Computer-simulated duel. No script: …" (havia edição; "no edits"
   mentia).
7. Callouts revistos como fala de narrador ("SLAMMED INTO THE WALL", "SAW IT
   COMING", "WHIFF PUNISHED"…); "PIN TO WALL"; elemento "Keen", "Executioner's".
8. Nome de skill não aparece no duelo: teste que varre o fonte do Simulador
   (todo texto literal do `_push_texto` é inglês ou está no `TELA_DO_JOGO`) e
   teste de que nenhum nome do kit entra na tela, no título ou na descrição.

**2ª rodada do conferente (20/10, `E:\tmp_pytest\conferente\semana1_r2\`):**
o `duelo_00128` aprovado; dois bloqueios do formato, consertados:
- o **agarrão** que o jogo escreve ("ARREMESSO!", "JOELHADA", "EMPURRÃO",
  "ESCAPOU", "REVERSÃO!"; 66 de 139 duelos do disco têm um) e o **nome da
  invocação** (o da skill SUMMON: "Fênix", "Ira da Floresta", "Invocação:
  Espírito", "Cópia Sombria") iam direto ao `.render(` e agora passam pelo
  `_texto_da_tela` (`ingles.AGARRAO`, `ingles.INVOCACOES`: "THROW!", "KNEE!",
  "SHOVE!", "ESCAPED!", "REVERSAL!", "Phoenix"…);
- a varredura antiga só olhava o `_push_texto`. A nova (AST) exige que TODO
  `.render(` das funções do Simulador que vão ao vídeo receba texto pelo mapa,
  sem letras, ou um item revisado (`REVISADOS`: o glifo de status); as funções
  que não vão ao vídeo (HUD do jogo, debug, vitória, pausa) estão nomeadas.
  Rodada sobre o código de antes, ela acusa as duas linhas (4879 e 6442).
Prova: `duelo_00129` (novo, Aurora Telvalum × Corvo Radyumi, seed 1585334362,
Poço, o par/seed do `duelo_00132` do estoque; "Throwing Axes VS Tactical
Knives"): "THROW!" aos 9,0 s e "ESCAPED!" aos 16,9 s
(`E:\tmp_pytest\semana1\agarrao_duelo_00129\`).

**Como medir a voz no mp4 final (e o limite de cada régua):** o gêmeo com a voz
muda deu +15,3 a +15,9 dB em três duelos e +4,6 no `duelo_00129`, porque o
`loudnorm` dinâmico sobe o gêmeo quieto e infla a luta; a projeção do final
sobre a voz (alinhada: o aac atrasa ~5 ms; a voz passada pelo mesmo
compressor) dá +9,7 a +10,4, mas tem um teto de ~+10 dB (correlação 0,95: o
limitador do master entorta ~10% da voz, que cai no "resto"). Antes do master,
a mesma janela: voz −16,8 / −16,4 dB contra a luta abaixada −28,6 / −32,2
(00129 / 00128), sem contar os +6–9 dB do compressor da voz; música abaixada
−40 dB. Sem o compressor, ou com o makeup 3, a projeção piora (+9,1 / +9,3).

Mais: com o mapa (duelo), o nome sobre a bola vai a 24 caracteres mesmo sem
tradução ("Nyxaris Cinzamordaca" inteiro); o título do cartão abaixo de 70 px
(`VEREDITO_CORPO_MIN`) quebra em 2 ou 3 linhas equilibradas e volta a crescer,
limitado pela largura (x ≤ 900) e pela altura (acima dos 80%): "TACTICAL /
KNIVES WIN!" a 91 px; o pior caso real ("THREE-SECTION STAFF NECROMANCER
WINS!") fica em 67 px em 3 linhas.

Achados de outro agente, medidos: o rótulo é o **estilo** da arma, não o tipo
(8 tipos → 36 pares esgotariam em ~12 dias). Banco vivo: 171 personagens, **51
rótulos** distintos por lado, 14.535 pares de personagens → **1.516 títulos
distintos**; 128 já ocupados pelo disco; **1.393 livres = 464 dias a 3/dia**. A
guarda segue só pelo título. Campo do modelo sem valor **falha alto**:
`rodizio.titulo_do_par` e `catalogo.titulo_do_duelo` levantam
`TituloIncompleto`, e o catálogo segura o duelo com pendência (não derruba a
listagem). A frase da voz não passa pelo `voz.falavel` (pt-BR: "KO" → "nocaute").

**Estoque antigo (os 28 não publicados):** `--rerender --refazer-edicao` põe
em inglês tudo o que o RENDERER desenha (faixa, WHO WINS?, voz, identidade,
callouts, plano do HUD, veredito, capa), mas reaproveita o clipe gravado: o
que o JOGO desenhou dentro dele (plano sob o lutador "PRESSÃO", "CRÍTICO!",
nome sobre a bola) continua em português. Só uma gravação nova da luta tira
isso; o duelo gerado depois deste commit já nasce todo em inglês.

**Fora daqui, para a publicação:** o idioma do vídeo na API do YouTube
(`defaultLanguage`/`defaultAudioLanguage`) é da publicação. O palco (Godot,
`producao.duelo_celular` desligado) não recebeu o mapa dos textos que o jogo
desenha: ligar o palco pede esse passo antes.


- **Catálogo que a publicação lê** — `builds/publicar/catalogo.py` varre
  `outputs/` e devolve `Video(id, origem, perfil, titulo, descricao, hashtags,
  variante, pendencias, capa)`. Eu mando nos arquivos que ele encontra
  (`final_<perfil>.mp4`, `capa.png`, os JSONs); a publicação manda no que faz
  com eles. Os textos vêm de `config/publicacao.json`, não de código.
- **Banco de personagens e armas** — `%LOCALAPPDATA%\neural-fights\{personagens,
  armas}.json`. Escritor único do lado das builds: `builds/nf_bridge/exporter.py`
  via `database.inserir_no_banco(..., renomear_em_conflito=True)`, disparado
  só por `generate-video`. Todo o resto (duelo, fight, torneio, catálogo)
  apenas LÊ. Desde 14/10/2026 (auditoria profunda, BLD-1/2/3 e MOT-101):
  - ler, escolher o nome livre ("#2") e gravar acontecem numa trava só, e a
    trava mora no runtime (`<runtime>\.persistence.lock`), não no TEMP de cada
    processo: duas builds em paralelo entram as duas;
  - o launcher grava partindo do disco (`salvar_lista_chars/armas(lista,
    apagar=, novos=)`): registro intocado fica byte a byte, campo que o modelo
    não conhece (`genero`, `tipo_projetil`, `tipo_orbital`) fica, e lista
    velha (a roleta inseriu depois que a aba abriu) é recusada com
    `ListaDesatualizada` — a tela relê e tenta de novo;
  - toda gravação que tira personagem OU arma deixa `<runtime>\_backup-<carimbo
    com microssegundo>` (5 guardadas; `_backup-manual-*` não conta);
  - o "Gerar Roster" do torneio no launcher grava só em
    `<runtime>\torneio\{armas,personagens}.json` (decisão
    `builds/gerar-roster-do-torneio`); o torneio lê esse catálogo quando ele
    existe e o banco, só lendo, quando não. "Abrir no Godot" do torneio ainda
    procura o lutador no banco: com roster próprio, ele falha com erro na
    tela (a simulação do torneio funciona).
- **Títulos editados** — `outputs/_publicar/_textos/<id>.json`
  (`catalogo.salvar_texto`): valem sobre o título gerado, para o painel e para
  a grade. É onde moram os títulos próprios das variantes B (27/09/2026).
- **Tarefas de geração** — `NeuralFights_gerar_HH` (as `horas` do
  `geracao.json`: 01–05 e 07–00 desde 30/09, §2), família minha
  (`builds/pipeline/tarefas_noite.py`, `hora_e_minuto` aceita `"12:32"`),
  trava `builds__gerar`; duelos e roleta (a roleta escreve no banco pelo mesmo
  `exporter`). O `piso_de_reposicao` do `geracao.json` é o piso que a
  publicação alerta (`postar.piso_de_alerta("builds")`), e `janela_pesada`/
  `dias_de_lote` aparecem no painel do lote (`remoto/lote.py`). Os
  monitores de tarefa de outras partes (`remoto/relatorios.py`,
  `visao/panorama/recursos.py`) ainda listam só postagem e bot.
- **Ledger da arena** — `outputs/_arena/ledger.json`, dono meu
  (`builds/arena/ledger.py`): registra cada round e escolhe adversário por
  continuidade/poder.
- **Ledger de publicação** — `outputs/_publicar/publicados.jsonl`, dono da
  publicação. Eu só leio (para saber o que já saiu).
- **Diário** — `%LOCALAPPDATA%\neural-fights\atividade.jsonl`
  (`builds/atividade.py`), uma linha JSONL por evento; escreve quem faz a ação,
  leem o bot, o painel e o app do celular.
- **Grade de horários** — `builds/grade.py`, uma cópia só, usada por builds e
  histórias. A cota de formatos é minha (config acima); a hora não.
- **Som da luta** (Onda 16A) — `fight.json` → `luta.sons` (e o `gameplay` do
  `edit_plan.json`), no relógio do clipe; o formato está em
  `docs/palco/sons.md`, e é a seção `sons` da timeline da 16C (o palco lê de
  lá). A guarda de luta muda POR TRECHO é da publicação: ela mede os
  `_segments_<perfil>/seg_NNN.mp4` dos eventos `gameplay`, que o render daqui
  produz.
- **Timeline do palco** (Onda 16C) — o arquivo de que o Godot desenha a luta:
  um valor por passo de 60 Hz (lutadores, arma com a geometria da hitbox,
  câmera, objetos, efeitos, eventos, `sons`, `remapeamento`), schema em
  `docs/palco/timeline.md`. Sai do gravador com `--timeline CAMINHO`
  (`.gcpf` = container zstd que o Godot abre nativo) e do
  `neural_fights.recording.timeline.gravar_timeline(desenhar=False)`, que é o
  que o palco usa: mesma luta, mesma câmera e mesmo som do gravador, 10× mais
  rápido (medido no `duelo_00014`). Os vídeos de hoje não gravam timeline.
  **Revisão 3 (28/09, ainda `versao: 1`):** os eventos que o render acendia e
  a v1 não dizia — `projetil_fim` com o motivo (acerto, validade, choque,
  desvio/escudo/parry, trap, explosão por timer, retorno), `explosao`,
  `choque`, `refletido`, `texto` (cor por efeito, execução, `FATAL!`) e
  `movimento` (afterimage, poeira, linhas) — e o `ponto` do acerto por
  projétil. O motivo foi conferido contra o motor instrumentado
  (`RevisaoTresContraOMotorTests`); o palco desenha `explosao` e `choque` com
  a arte que já tinha.
- **O palco** (Onda 16D) — o projeto Godot `palco/` desenha a luta a partir da
  timeline e grava o vídeo COM o som do jogo; o lado Python é
  `builds/palco/` (`main.py palco ...`, `main.py duelo --palco [--ab]`).
  Os comandos `palco ...` **não publicam e não entram no catálogo**: saem em
  `outputs/_palco/`. A troca do visual é a 16G, com a aprovação do Adrian. Como funciona, comandos, guardas
  e medidas: `docs/palco/README.md`; como trocar arte e som:
  `docs/palco/COMO-EDITAR.md`. O `main.py` só importa `builds.palco` no ramo
  `palco`/`--palco`: erro no palco não derruba publicar nem a geração noturna.
  **16E (28/09):** hitstop do render ligado pela decisão `hitstop` (+2,6% de
  duração, medido em 23 duelos), as 24 expressões com as peças do Kenney
  (CC0, 12×), efeitos por tipo × elemento com arte CC0, HUD do palco (nome,
  vida, plano; `--hud`) e revisão por render curto. O A/B
  depois da arte é o nó `palco-ab-2` do Grimório.
  **16G, primeira metade (30/09):** `main.py palco ab --duelo X --edicao`
  (`builds/palco/edicao.py`) faz o B com a MESMA edição do duelo (o
  `edit_plan.json` do A com só o clipe trocado e as horas no relógio do
  palco), fora do catálogo, em `outputs/_palco/g16_<id>/`. A/B de
  `duelo_00031` e `duelo_00030`: mesmos quadros, mesmos golpes no mesmo
  quadro, mesmo som (0% calado); medidas em `docs/palco/README.md`. A troca do
  duelo de produção espera o nó `palco-duelo-ab`; só 9:16 (o 16:9 falta).
  **Ponte do Ateliê (07/10):** o catálogo de animações é a entrada da arte do
  Ateliê. PNG avulso de `manifesto_slots.json` não é instanciado pelo palco,
  pois dependia de um script removido. Regras em `docs/sprites/CONTRATO_SLOTS.md`.

## 13. A geração por formato (19/10/2026)

**O que estava errado (medido nos diários `outputs/_logs/gerar_*.txt`, 13 a
19/10):**

| dia | duelos | roletas | estreias renderizadas |
|---|---|---|---|
| 13/10 (ter) | 0 | 12 | 12 |
| 14/10 | 0 | 4 | 4 |
| 15/10 | 0 | 5 | 5 |
| 16/10 | 0 | 4 | 4 |
| 17/10 | 0 | 3 | 3 |
| 18/10 | 0 | 2 | 2 |
| 19/10 (até 16:12) | 14 | 9 | 8 (+2 não gravadas) |
| **7 dias** | **14 (2/dia)** | **39** | **38** |

O estoque de duelos da publicação caiu de **43 (13/10) para 13 (19/10,
01h)** sem a geração fazer um só. O gatilho era o TOTAL do canal, e o total
estava cheio de **estreias** (26 → 54): cada roleta grava uma, o YouTube não
posta mais estreia (`publicacao/duelo-no-lugar-da-estreia`) e o TikTok leva
~0,75 por dia. Com 66–77 vídeos "no estoque", a reposição (piso 20) dizia
"so o worker" o dia inteiro, e o lote de 19/10 às 14:03 dizia "88 vídeos para
um alvo de 88" com 26 duelos. A madrugada da transição só fez roletas (o teto
dela era 10 duelos e havia 13). Duas roletas de dia (10:03 e 12:34 de 19/10,
34 e 94 min — a de 94 com 7 erros 403 da voz e a pista das histórias junto)
levaram a rodada inteira, porque cada formato ia até o fim do alvo dele.

**Custo medido:** duelo 4,35–5,0 min (11 em 47,9 min às 07:02 de 19/10;
mediana 4,5). Roleta sozinha de madrugada: 10–17 min até 16/10; **25–29 min
em 19/10** (com o gancho B e o HUD novo), dos quais o vídeo das duas
estreias leva ~9 (`generation_00176`: gravação da estreia 3,4 + render das
estreias 8,9 + voz e build A/B 14,2 min). De dia, 27–35 min.

**A voz:** o 403 do edge-tts não começou em 19/10 às 11:32 — está nos
diários **desde 12/10 01:07** (233 falhas no dia 12; 40–222 por dia até 19/10)
e o cache de voz não ganhou nenhum mp3 de 12/10 a 19/10: **todas as falas
novas dessas roletas são do SAPI** (`.wav`, a voz do Windows, que é o
reserva de `voz.sintetizar`). O conserto (edge-tts 7.3.1, b38efe2) vale para
as próximas; as **51 roletas** de `generation_00126` (12/10 01:17) a `00185`
saíram com as falas novas na voz do SAPI (fala que já estava no cache ficou
no edge). Refazer a voz delas é decisão do Adrian (o som só ele julga).

**Desde 20/10/2026 (PLANO semana 1, ramo `integracao/publicacao-semana1`)
o canal é de DUELOS**: a publicação posta 3/dia no YouTube (09:37, 17:57,
21:37; desde 01/11 12:07, 20:37, 22:37) e 1 no TikTok (21:37; desde 01/11
20:37), e as duas misturas trocam build e estreia pelo
duelo (`TROCAS_NA_COTA` igual nos dois arquivos). `consumo_por_dia` passa a
**duelo 3, build 0, estreia 0** (os horários vêm de `grade.horas_do_canal
("builds", ...)`); piso do duelo 4 × 3 = **12**; lote de segunda 07:02 = 21 +
12 = **33 duelos**, terça 30. **Build e estreia ficam com meta 0: as metas
não pedem mais roleta** — sem roleta o banco de personagens para de crescer.
Ver a pergunta ao Adrian no relato do ramo.

**Como era em 19/10** (`builds/pipeline/noite.py`, chaves novas no `geracao.json`):
- `consumo_por_dia`: o que a publicação tira do estoque NOVO por dia — duelo
  10 × 5/8 = **6,25** e build 10 × 3/8 = **3,75** (YouTube, com a troca
  `TROCAS_NA_COTA`, espelho da do `postar.py`, comparada por teste); estreia
  6 × 1/8 = **0,75** (TikTok, que tira duelo e build do que já saiu no
  YouTube). É ele que dá os dias de cada formato;
- `piso_por_formato_em_dias` {duelo 4, build 2, estreia 2} → **25, 8 e 2**
  vídeos; `metas_do_plano`: reposição e estoque zero = o piso; lote = o que
  sai até a próxima segunda 07h + o piso. O `piso_de_reposicao` (20) segue
  sendo só o alerta da publicação;
- `videos_por_roleta` 2: a meta da build é em vídeos (A e B), o passo é uma
  roleta, e a roleta em preparo conta 2;
- a ordem é refeita a cada passo (menos dias primeiro; empate, duelo). Caso
  zero: sem duelo, o duelo vai primeiro, com 50 estreias e 10 builds;
- `estreia_so_abaixo_da_meta`: a estreia é **gravada** em toda roleta (a luta
  do fim da build e o cartel saem dela), mas o vídeo dela só é renderizado com
  as estreias abaixo da meta (`generate(estreia_render=False)`; reserva da
  roleta sem ele `minutos_por_build_sem_estreia` = 20). O vídeo que não saiu
  sai depois: `python main.py fight --rerender generation_XXXXX/estreia`. O
  `fluxo` mostra a estreia gravada sem vídeo como pronta, com esse comando. A
  falta de estreia não pede roleta;
- `jogo_que_segura` "League of Legends.exe": nenhum passo novo (duelo, roleta
  ou job do worker) começa com a partida aberta; na dúvida (tasklist falhou)
  não segura. Exceção: o estoque zero;
- `folga_da_grade` 18/18 (de :19 a :55 nas horas de :37);
- o duelo que falha deixa `falhou.json` e 2 falhas na semana tiram o nome do
  rodízio (§2). **Pendente:** por que as lutas de Zael Ossarvarn
  (`generation_00182`) são tão lentas — a estreia dele estourou os 600 s às
  10:17, os rounds da estreia da `generation_00185` contra ele levaram ~8
  min cada (12:35–12:51; um round normal leva 1,5–3,6), e o duelo Ardeth ×
  Zael estourou duas vezes. Não investigado aqui.

**Projeção** (a rodada de verdade com relógio, geradores e publicação em
dublê — duelo 4,6 min, roleta 19 min sem o vídeo da estreia e 28 com, 3 jobs
de imagem por roleta de 7/7/15 min, a roleta entra no estoque quando eles
acabam; YouTube 10 horários duelo 5/build 3; TikTok 6 com 1 estreia em 8;
começo 19/10 16:30 com 26 duelos, 10 builds e 52 estreias; sem jogo aberto):

| | antes (HEAD) | depois |
|---|---|---|
| menor estoque de duelos por dia, 20/10–02/11 | **3–4** de 22/10 em diante (vive no teto de 10 da madrugada) | **25–52**; o mínimo (25–26) é na segunda antes do lote |
| duelos por semana (seg 26/10–dom 01/11) | 44: 22 na segunda e 22 de madrugada, qui–dom, só quando o estoque fura 10 | 43, seg–ter de dia; qua–dom nada |
| roletas na mesma semana | 13, todas com o vídeo da estreia | 13, nenhuma com o vídeo da estreia (as 52 duram ~2 meses no TikTok) |
| máquina de geração na semana | 9,5 h + worker 6,3 h | 7,4 h (duelos 3,3 h + roletas 4,1 h) + worker 6,3 h |

Script da projeção (fora do git):
`C:\Users\adrian\AppData\Local\Temp\claude\e--projetos\3494d475-f7b5-498b-8dd1-7421616e2724\scratchpad\projetar_a832.py novo|antigo [dias]`.
