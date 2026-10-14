# Decisões — Builds

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Variantes B** — Título próprio para cada uma (27/09/2026) `variantes-b`
- ✅ **Roleta automática de madrugada** — Sim (28/09/2026) `roleta-de-madrugada`
- ✅ **Estreia generation_00066 (muda)** — Descartar (28/09/2026) `estreia-00066`
- ✅ **Onda 16: ferramenta do visual** — Godot 4 (28/09/2026) `ferramenta-do-visual`
  - ✅ **Visual do lutador** — Bolinha com arte (28/09/2026) `visual-do-lutador`
  - ✅ **Origem da arte** — CC0 + IA, trocável (28/09/2026) `origem-da-arte`
    - ✅ **Sprites animados: como produzir** — Continuar com o modelo padrão e limpar depois (28/09/2026) · “Eu consegui gerar alguns spritesheet bons, veja o arquivo piriri.py , eu consegui esse usando o chat gpt, mas como o processo é moroso quero apenas uma interface gráfica que facilite ao máximo esse processo, como essa limpeza de fundo, saneamento e auto faturamento de frames, identificação e outras coisas úteis.” `sprites-animados`
  - ✅ **Palco: o visual novo (A/B)** — Seguir: próxima etapa é a arte (16E) (28/09/2026) `palco-seguir`
    - ✅ **Chão da arena** — Foto de pedra CC0 escurecida (como está) (28/09/2026) `chao-da-arena`
    - ✅ **Hitstop: a pausinha no impacto** — Ligar (28/09/2026) `hitstop`
    - ✅ **Palco: A/B depois da arte (16E)** — Seguir: trocar o visual do duelo (16G) (28/09/2026) `palco-ab-2`
      - ✅ **Palco: os números de dano na tela** — Não (29/09/2026) `palco-numeros-de-dano`
      - ✅ **Duelo: trocar o visual para o palco?** — Ajustar primeiro (diga o quê no comentário) (30/09/2026) · “A corrente a animaçao dela é muito feia, e suaecanica é idêntica a da espada, quero um rework completo nela mas de resto tudo está perfeito” `palco-duelo-ab`
- ✅ **Transição até o palco** — O visual atual segue, já com o som real (28/09/2026) `transicao`
  - ✅ **Som real da luta (16A)** — Aprovar: re-render do estoque na madrugada (28/09/2026) `som-real-16a`
    - ✅ **generation_00077: luta muda, lutadores fora do banco** — Descartar, como a 00066 (28/09/2026) `generation-00077`
- ✅ **Esteira de sprites: por onde começa** — As duas frentes (30/09/2026) `sprites-ia-alvo`
  - ✅ **Sprites: como manter o mesmo estilo** — Imagem-mestra aprovada por você (recomendado) (30/09/2026) `sprites-ia-estilo`
- ✅ **Sprites: peça parada ou quadro a quadro?** — Peça + Godot; folha só no impacto (recomendado) (30/09/2026) `sprites-ia-formato`
  - ✅ **Sprites: fundo pedido ao ChatGPT** — Magenta liso (verde nos roxos) (recomendado) (30/09/2026) `sprites-ia-fundo`
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
- ⏳ **Botão 'Gerar Roster' do torneio** — O botão 'Gerar Roster' do torneio troca o banco inteiro de personagens e armas por 64 inventados, sem perguntar. Fica uma cópia, mas ninguém avisa. O que ele deve fazer? `gerar-roster-do-torneio`
- ⏳ **Luta que termina empatada** — Hoje, quando a luta empata, o código inventa vitória do primeiro lutador. O que fazer no empate? `empate-persistente`
- ⏳ **Nome pedido pelo comentarista** — O nome que o público pede para o personagem tem uma regra 'não termina em qualidade' (ex.: não aceita 'João Forte'). Mantém a regra? `nome-pedido-livre`
- ⏳ **Os 29 traços sem efeito** — 29 traços de personalidade são sorteados para os lutadores mas não fazem nada na luta. O que fazer? `quirks-sem-efeito`
- ⏳ **Atordoamento e relógio de ataque** — Hoje o atordoamento pausa o relógio de ataque do lutador (muda o ritmo de toda luta). Mantém? `atordoamento-e-relogio`
- ⏳ **Lava do Vulcão e do Inferno** — O catálogo promete dano de lava nas arenas Vulcão e Inferno, mas a lava não machuca. O que fazer? `lava-do-vulcao`
- ⏳ **Som da vitória** — Na vitória hoje toca a abertura da arena, quase muda. Que som deve tocar? `som-da-vitoria`
- ⏳ **Volume dos golpes depois do conserto** — O som dos golpes estoura porque o pan soma os dois lados (até 1,8x). Consertando, os golpes ficam mais baixos. Você quer ouvir antes de valer nos vídeos? `volume-dos-golpes`
- ⏳ **Live: !arena com dois pagantes** — Na live, se duas pessoas pagam !arena no mesmo round, qual vale? E o comando pago que cai em cooldown hoje some sem reembolso. `arena-dois-pagantes`
