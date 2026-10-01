# Decisões — Geral

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (30/09/2026) · “30/09 11:43, pela Mesa de comando: paralelo, até 3 agentes” `modo-de-trabalho`
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
