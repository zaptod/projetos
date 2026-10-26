# Skills de fora por setor (20/10/2026)

**Pergunta:** que skills prontas do Claude Code (formato `SKILL.md` ou plugin oficial) dão
expertise real a cada setor do **canal de duelos do Neural Fights**, sem risco?

**Escopo (Adrian, 20/10):** só os setores do canal de duelos: builds, publicacao, metricas,
conferente, integrador. Histórias, app/bot, painel/Vila, zombie e Blue Lock ficaram de fora.

**Como foi feito:** cada candidato foi baixado como tarball do commit exato para uma pasta
própria e vazia em `E:\tmp_pytest\skills_quarentena\<dono>_<repo>\`, extraído sem caminho
absoluto nem `..`, e lido. **Nenhum script deles foi executado.** Recusa automática para:
código que manda dado para fora, download de binário, instrução para contornar permissão.
Nada foi instalado como plugin, nem global nem no projeto. As aprovadas foram copiadas para
`.claude/skills/<nome>/`, cada uma com um `ORIGEM.md` (URL, commit, licença, o que foi lido,
cuidados neste repositório, setor).

Configuração:
- `.gitignore` não foi mexido: `.claude/*` ignora `.claude/skills/`, então as skills entraram
  com `git add -f` por caminho. **Falta a exceção `!.claude/skills/`**, que o orquestrador põe ao
  juntar; sem ela, skill nova ou editada some do `git status`.
- `pyproject.toml`: `.claude/skills` entrou no `exclude` do `ruff` (o CI roda `ruff check .`
  e um exemplo da Anthropic tem um `f-string` sem variável; código de fora fica como veio).

## Resumo por setor

| Setor | Aprovadas (em `.claude/skills/`) | Recusadas ou adiadas para este setor |
|---|---|---|
| **builds** (vídeo, ffmpeg, voz, Godot) | `hyperframes-core`, `hyperframes-keyframes` (só na prova de 6 h, com telemetria desligada), `godot-gdscript-patterns` | roteador `hyperframes` e `hyperframes-cli` (telemetria e feedback por padrão); `hyperframes-audio` (overlay é mudo; pede `npm i`); `hyperframes-studio` (edição humana); Remotion (adiado, é a reserva do plano); `godot-agent-vision` (pede `pip install` e mexe no `project.godot`); ffmpeg (nenhuma boa) |
| **publicacao** | `verification-before-completion`, `systematic-debugging` (quando um horário não sai) | `playwright-cli` (pede `npm install -g` e pré-libera comandos); nada de TikTok/YouTube de fora |
| **metricas** | `python-testing-patterns` (caso zero, mocks da API); `dataviz` já existe na máquina | skills de YouTube Analytics (intermediário de dados ou origem incerta) |
| **conferente** | `webapp-testing` (Chrome 390x844, captura, console), `verification-before-completion` | `playwright-cli` (idem); `godot-agent-vision` (idem) |
| **integrador** | `systematic-debugging`, `verification-before-completion`, `python-testing-patterns` | `test-driven-development` (manda apagar código escrito antes do teste: choca com "Delegar nunca joga fora") |

Fora do escopo (não buscado): historias, app-e-bot, painel-e-vila, jogo-zombie, blue-lock. A
`frontend-design` (Anthropic) foi lida e chegou a ser aprovada para o app e o painel, mas saiu
com a redução de escopo; está na quarentena se um dia for pedida.

## Candidatos verificados

| Candidato | Fonte e versão | Popularidade (API, 20/10) | O que traz | Veredito |
|---|---|---|---|---|
| `anthropics/skills` | oficial Anthropic, `dbd4588f` (09/10) | 182 mil estrelas | 18 skills (webapp-testing, frontend-design, skill-creator, mcp-builder, pdf, docx, pptx, xlsx, claude-api, canvas-design...) | **webapp-testing** aprovada. `frontend-design` lida e segura, mas fora do escopo (app/painel). `skill-creator` e `claude-api` já existem na máquina. `mcp-builder`, documentos e arte: nenhum setor precisa agora. |
| `heygen-com/hyperframes` | oficial HeyGen, `26a5ab77`, plugin 0.8.181 | 67,8 mil | plugin com 21 skills: roteador, core, cli, animation, creative, keyframes, audio, studio, registry, media-use e 10 workflows (captions, motion-graphics...) | **core** e **keyframes** aprovadas. **Recusadas:** roteador `hyperframes` (a descrição se diz "entrada obrigatória para qualquer vídeo" e tomaria todo pedido de vídeo, inclusive duelo e história; manda rodar `usage`, que lê as credenciais do Claude Code, `skills update`, que baixa do GitHub, e `upgrade` sem perguntar) e **`hyperframes-cli`** (`SKILL.md:139-154`: todo render manda telemetria anônima e, depois de render bom, "send one feedback report" para um canal público, sem perguntar; mais as páginas de nuvem HeyGen/Lambda/Cloud Run). `audio` e `studio` não servem ao uso. `animation` (1,2 MB), `creative` (1,2 MB), `media-use` (1,8 MB), `embedded-captions` (3,5 MB) não lidas: avaliar só se a prova passar. Desligar: `HYPERFRAMES_NO_TELEMETRY=1`, `HYPERFRAMES_SKIP_SKILLS=1`, `HYPERFRAMES_NO_UPDATE_CHECK=1`. |
| `remotion-dev/skills` | oficial Remotion, `039e8a2f`, v4.0.537 | 5,4 mil (Remotion: 65,4 mil) | roteador `remotion-best-practices` + create, markup, render (inclui WebM transparente `--pixel-format=yuva420p --codec=vp9`), captions, studio, docs, upgrade, saas, maps | **Adiado, não copiado.** Existe e é o que a pesquisa dizia. É a reserva do plano: entra se o HyperFrames falhar na prova. Li o roteador e o `remotion-render`; o resto (1,2 MB do roteador) fica para quando for usado. `remotion-upgrade`/`docs` buscam na rede; `saas` fala de Lambda: na hora, mesmos cuidados do HyperFrames. |
| `wshobson/agents` | comunitário (Seth Hobson), `0874a27b` (17/10) | 41,2 mil | 185 skills em plugins | **godot-gdscript-patterns** e **python-testing-patterns** aprovadas (só texto). |
| `obra/superpowers` | comunitário (Jesse Vincent), `bb92a777`; o marketplace oficial fixa este mesmo commit | 302 mil | 15 skills de processo + hook de início de sessão | **systematic-debugging** e **verification-before-completion** aprovadas (só as skills, sem o hook). **test-driven-development recusada:** "escreveu código antes do teste? apague" briga com "Delegar nunca joga fora" (entrega do Codex entra com aviso, não é apagada) e com nossos testes que varrem o fonte de propósito. O anexo `writing-good-tests.md` dela é bom (nada de asserção espelho, mock não ganha asserção): vale reaproveitar numa skill nossa. Resto (brainstorming, writing-plans, subagent-driven-development...) duplica o fluxo do orquestrador e da Mesa. |
| `microsoft/playwright-cli` | oficial Microsoft, `b1a5903c` | 14,4 mil | skill `playwright-cli` + 10 referências | **Recusada:** o frontmatter tem `allowed-tools: Bash(playwright-cli:*) Bash(npx playwright:*)` (pré-libera comandos sem pedir), e a instalação manda `npm install -g @playwright/cli@latest` (global). O projeto já usa Playwright em Python, que a `webapp-testing` cobre. Li só o `SKILL.md` antes de recusar. |
| `anthropics/claude-plugins-official` | marketplace oficial, `a0b04d9d` | — | 315 plugins listados | Lido o `marketplace.json`. Nenhum plugin de Godot, ffmpeg, YouTube ou TikTok. `playwright` é servidor MCP (não skill; instalar plugin está fora desta tarefa). `telegram` é ponte de conversa, não serve. `pyright-lsp` (servidor de linguagem Python) pode ser útil, mas é plugin, não skill: decisão à parte. |
| `thedivergentai/gd-agentic-skills` | comunitário, `db004d74`, LGPL-3.0 | 870 | dezenas de skills Godot/Bevy | **Recusada** a `godot-agent-vision` (a única que tocava no nosso caso: captura do Godot para o conferente): manda `pip install -r requirements`, instala um addon temporário dentro do projeto Godot e mexe no `project.godot` (o palco é do Adrian). Li só o `SKILL.md`. O resto é jogo interativo, não render. |
| skills de ffmpeg e de YouTube | diretórios (skills.sh, skillselion, claudskills, claudemarketplaces) | dezenas a centenas | ver "Lacunas" | **Não baixadas.** |

## Regras para quem usa
- As **leis do `CLAUDE.md` vencem qualquer skill** (commit por caminho, testes com
  `TEMP=E:\tmp_pytest`, janela das postagens, "Claude proibido", Grimório em vez de pergunta).
  Cada `ORIGEM.md` lista os choques que achei.
- Atualizar uma skill = nova quarentena, nova leitura, novo `ORIGEM.md`. Nunca `npx skills add`,
  `claude plugin install` ou `hyperframes skills update` direto no repositório.
- O que falta por setor deve virar **skill nossa** (feita com `anthropic-skills:skill-creator` a
  partir de `docs/sessoes/<parte>.md`), não skill de diretório.

## O que já existe sem copiar nada

Estas já aparecem na lista de skills desta máquina (vêm da conta ou de plugin já instalado),
então não foram duplicadas em `.claude/skills/`:
- `anthropic-skills:skill-creator` — criar e medir skills nossas (a do repositório
  `anthropics/skills` é a mesma; não copiada).
- `claude-api` — referência da API da Anthropic.
- `dataviz` — gráficos e painéis (serve a **metricas** para relatório e página de confiabilidade).
- `code-review`, `security-review`, `simplify` — revisão de diff (serve ao **integrador**).
- `run` — subir e olhar o app (serve ao **conferente**).

## Lacunas (nenhuma skill de fora boa o bastante)

- **ffmpeg / edição de vídeo e áudio:** só achei skills pequenas de pessoas físicas
  (`gupsammy/claudest` ~270 estrelas e 34 instalações; `einverne/dotfiles` 121 estrelas, GPL-3.0,
  arquivo de configuração pessoal; `bighardperson`, `mrgoonie/xxxnaper`, `josiahsiegel`, todas com
  dezenas de instalações). Nenhuma é oficial nem muito usada; não baixei. O Claude já escreve
  ffmpeg direto, e o que falta (motion graphics por cima da luta) é papel do HyperFrames.
  **Melhor caminho:** escrever a nossa skill `ffmpeg-do-canal` com `anthropic-skills:skill-creator`,
  a partir do que já está em `random_builds` (1080x1920, `xfade`, filtro `ass`, voz edge-tts,
  o "vídeo mudo barrado").
- **YouTube Data / Analytics:** não existe skill oficial do Google. As comunitárias são de
  diretório (`membranedev/application-skills` 269 estrelas, passa pela plataforma Membrane, ou
  seja, os dados do canal iriam para um intermediário; `sundial-org/awesome-openclaw-skills` 668
  estrelas, coleção copiada; `vm0-ai`, `zeropointrepo`, `int-youtube`). **Recusadas sem baixar:**
  intermediário de dados ou origem incerta, e o projeto já fala com a API oficial direto
  (`urllib`, ver `pyproject.toml`). Mesmo caminho: skill nossa a partir de `docs/sessoes/metricas.md`.
- **TikTok Studio / publicação por navegador:** nada de fora. E a memória "Contas de IA sem
  disfarce" proíbe construir evasão; nenhuma skill de "automação furtiva" entra.

## Redes (26/10)

Pedido do Adrian: skills de análise e de postagem para YouTube (Shorts), TikTok e Instagram (Reels).
Quarentena em `E:\tmp_pytest\skills_quarentena\redes\` (commits fixados em `SHAS.txt`). Nada foi executado.
Regras comuns: nunca agir em página pública pela conta pessoal do Adrian, nada de engajamento
automático, evasão ou multicontas disfarçadas, e nenhum dado vai a serviço de terceiros sem decisão
dele. A biblioteca `social-media-skills/skills` (200 estrelas, MIT, push 15/10) liga toda a publicação
ao **WoopSocial** (agendador pago de terceiros): só o texto entrou, com um "AVISO DA CASA" no topo.

| Rede | Análise | Postagem |
|---|---|---|
| YouTube (Shorts) | `youtube-shorts`, `youtube-analise-referencias` | `youtube-publishing-and-metadata` |
| TikTok | `tiktok-growth` | `tiktok-video-publishing` |
| Instagram (Reels) | `instagram-growth` | `instagram-reels-publishing`, `instagram-seo` |

### Aprovadas com cautela (instaladas em `.claude/skills/`, cada uma com `ORIGEM.md`)
- `youtube-shorts` (social-media-skills, MIT): Viewed vs Swiped Away, Escada de Retenção, Content ID e aviso de IA; a parte WoopSocial é ignorada.
- `youtube-publishing-and-metadata` (idem): título, descrição, hashtags, "feito para crianças" como marcação legal; escrita para vídeo longo, aproveitar título e hashtags.
- `youtube-analise-referencias` (AgriciDaniel/claude-youtube, MIT; SKILL.md escrito pela casa): 3 references com benchmark e fonte; sem a integração DataForSEO; ignorar CPM/RPM.
- `tiktok-growth` (social-media-skills): diagnóstico sintoma -> etapa quebrada (conclusão, loop, busca, série).
- `tiktok-video-publishing` (idem): legenda como busca, capa, dueto/costura, rótulo de IA; campos são do WoopSocial, valem os equivalentes do TikTok Studio.
- `instagram-growth` (idem): envios por alcance e tempo de exibição; marca d'água do TikTok derruba o Reel.
- `instagram-reels-publishing` (idem): 1080x1920, zona segura (topo ~250 px, rodapé ~350 px, recorte 3:4 da grade), capa escolhida antes de publicar.
- `instagram-seo` (idem): palavra-chave nos ~125 primeiros caracteres, hashtags como 3-5 rótulos, texto e imagem combinando.

Todos os benchmarks ("~70% assistido", "envios 3-5x curtidas") vêm sem link ou de relatórios de agências:
são hipóteses a confrontar com `metricas-*`, não metas.

### Recusadas (com o motivo)
- `msitarzewski/agency-agents` (tiktok-strategist, instagram-curator, video-optimization-specialist, social-media-strategist, short-video-editing-coach, support-analytics-reporter): personas genéricas de marca, com metas sem fonte (CTR 8%, engajamento 8%) e foco em anúncios, influenciadores e Shopping; sem nada específico de Shorts ou Reels.
- `sickn33/agentic-awesome-skills` `instagram`: kit de scripts em Python (OAuth da Meta, token e segredo em texto puro no disco, painel local, envio de mídia ao Imgur), marcado `risk: critical`; a casa posta pelo navegador e não usa API de postagem.
- `sickn33` `youtube-seo-optimizer`: pesquisa por palavra-chave na web, voltada a vídeo longo e podcast, e sobreposta à `youtube-publishing-and-metadata`.
- `sickn33` `social-content`: manda raspar posts em escala (Apify) e é genérica.
- `coreyhaines31/marketingskills` `social`, `video`, `analytics`: foco LinkedIn/X, avatares pagos (HeyGen) e GA4 de site; `video` repete o `hyperframes-core`.
- `social-media-skills` `analytics-and-reporting` e `platform-specs-and-validation`: a fonte de dados e a validação são o WoopSocial (serviço pago de terceiros), sem uso fora dele.
- `ECC` `social-publisher` e `wshobson/agents` `social-publishing`: publicam via SocialClaw com chave de API, serviço pago de terceiros.
- `ECC` `crosspost`: X, LinkedIn, Threads e Bluesky, fora das nossas redes.
- `ravsau/youtuber-skills` `youtube-retention` (6 estrelas): leitor de curva pequeno, benchmarks sem fonte e sobreposto a `youtube-shorts`.
- Registros e listas (`awesome-agent-skills`, `agentic-awesome-skills`) trazem também `taisly`, `upload-post`, `publora`, `postiz`, `ScrapeCreators`, `last30days`, `apify-*`, `*-automation` (Composio): **só registradas**, todas postam por intermediário, raspam ou automatizam conta de terceiros.
- Não avaliadas por fugirem do pedido: `hook-writer`, `hashtag-strategy`, `reels-script`, `tiktok-script`, `thumbnail-design` do mesmo repositório (candidatas a uma 2ª rodada se faltar roteiro por rede).

## Roteiro, humor e voz (26/10)

Pedido do Adrian: o ep. 2 da série "Como eu criei um Blue Lock" foi reprovado (roteiro, piadas e pronúncia dos nomes). Quarentena em `E:\tmp_pytest\skills_quarentena\roteiro\` (commits em `SHAS.txt`). Nada foi executado. A 2ª rodada das `redes` (hook-writer, reels-script, tiktok-script, thumbnail-design) está resolvida aqui.

### Aprovadas com cautela (instaladas em `.claude/skills/`, cada uma com `ORIGEM.md`)
- `humor-sitcom-comedy` (jtydhr88/screenwriting-skills `sw-sitcom-comedy`, MIT, 1819 estrelas): mecânica de piada (setup em dois tempos, soco no fim, topper, callback, graça por personagem, contagem por página, diagnóstico). Está em chinês e responde em português se perguntada em português; ler só as seções de piada; aviso e resumo da casa no topo.
- `roteiro-hook-writer` (social-media-skills `hook-writer`, MIT): gerar 5 a 10 ganchos de mecanismos diferentes e pontuar; o gancho sai do elemento mais forte do próprio vídeo.
- `storytelling-falado` (artemnovitckii/content-skills `storytelling`, MIT): "mas/portanto" no lugar de "e então", última frase primeiro, ritmo, tom de falar com uma pessoa, ~2 palavras por segundo.

### Recusadas (com o motivo)
- `social-media-skills` `reels-script`, `tiktok-script`, `short-form-video-script`: sobrepostas a `youtube-shorts`, `tiktok-growth`, `instagram-reels-publishing`, `hyperframes-direcao` e à `roteiro-hook-writer`; metade é publicação pelo WoopSocial e prompts do Veo.
- `thumbnail-design`: capa do YouTube; Short não usa miniatura e o assunto não é roteiro.
- `scripting-and-storyboarding`, `story-writer`, `storytelling-and-narrative`, `meme-and-culture` (mesmo repositório): storyboard longo, Stories do Instagram, sobreposta à `storytelling-narrative` e meme de marca; todas ligadas ao WoopSocial.
- `vkorost/claude-standup-skills` (1 estrela): imita a voz de sete humoristas reais, em inglês, com palavrão e política; a mecânica geral que cabe ao canal já está na `humor-sitcom-comedy`.
- `talsraviv/comedy-writers-room`: sem licença no repositório.
- `artemnovitckii` `anti-ai-writing`, `dumbify`, `viral-hooks`: lista de vocabulário em inglês e sobreposta à `roteiro-hook-writer`; só a `storytelling` entrou.
- `ai-voiceover` (social-media-skills): ElevenLabs e WoopSocial; o motor da casa é o edge-tts, que não aceita audio tags. Só rende a regra "escreva para o ouvido, leia em voz alta, anote a pronúncia".
- `openai/skills` `speech`: exige chave e API paga da OpenAI e roda um script; só tem um modelo de "direção de voz" curto (afeto, tom, ritmo, pausas, ênfase).
- `microsoft/hve-core` `tts-voiceover`: Azure Speech com credencial, 400 KB de scripts; a ideia (léxico `sub alias`) está anotada abaixo.
- `bitwize-music-studio/claude-ai-music-skills` `pronunciation-specialist` (CC0): para letra de música no Suno, inglês, depende de servidor MCP próprio.
- `BBuf/AI-Infra-Auto-Driven-SKILLS` `sglang-explainer-video`: 1064 estrelas, mas sem licença no repositório; só a ideia (léxico `pronunciation.json` que cresce a cada erro, mais conferência por transcrição) foi anotada.

### Lacuna (nenhuma skill de fora serve): pronúncia de nomes japoneses em TTS pt-BR
Não existe skill séria para respelling pt-BR/japonês em TTS. O edge-tts rejeita SSML (`phoneme`, `sub`), então a alavanca é o **respelling no texto** (ex.: escrever o nome como o português o lê) numa tabela única de nomes, aplicada antes de sintetizar, conferida pelo ouvido do Adrian (som só ele julga). Padrões tirados das fontes lidas: léxico com precedência (base + exceções do projeto, `bitwize` `SKILL.md`), léxico por arquivo que cresce a cada erro achado (`hve-core` `SKILL.md`; `BBuf` PR 106) e "leia em voz alta, anote a pronúncia" (`ai-voiceover` `references/script-for-the-ear-and-recipes.md`). Fica como skill da casa a escrever, se o Adrian quiser.

## Visual e retenção (26/10)

Pedido do Adrian: "o que mais prende são as representações visuais, sejam do próprio jogo ou de diagramas; use e abuse". Quarentena em `E:\tmp_pytest\skills_quarentena\visual\` (commits em cada `ORIGEM.md`). Nada foi executado. O `iart-ai` (19 pacotes, 56 skills, MIT) foi a melhor fonte; quase tudo nele usa Remotion e `scripts/`, então só o texto entrou, com um aviso de que no HyperFrames o código de exemplo (rAF, CSS transition, `useCurrentFrame`) mostra a técnica e deve ser reescrito em GSAP numa timeline pausada.

### Instaladas (todas MIT, só texto, cada uma com `ORIGEM.md` e AVISO DA CASA)
- `visual-retencao-vertical` (iart `short-form-video`): arco de retenção, gramática do gancho, interrupção a cada 2-4 s, laço, zonas seguras. Benchmarks sem fonte: hipótese.
- `visual-diagramas-animados` (iart `diagram-animation`): nós -> arestas -> rótulos, ativo aceso e resto apagado, ponto que viaja, barras, linha, contador.
- `visual-explicador-roteiro-tela` (iart `explainer-video`): uma ideia, uma analogia, voz como espinha, imagem ilustra a frase, ritmo por batida.
- `visual-svg-desenho-e-trajetoria` (iart `svg-animation`): seta que se desenha (`pathLength`), `MotionPath`, morph.
- `visual-gsap-plugins` (oficial GreenSock `gsap-plugins` + `gsap-timeline`): DrawSVG, MotionPath, MorphSVG, SplitText, Flip, CustomEase/Wiggle/Bounce; plugins hoje grátis.
- `visual-principios-de-movimento` (iart `animation-principles`): easing por intenção, antecipação, overshoot, stagger.
- `visual-graficos-animados` (iart `chart-animation`): dado -> pixel, contador, ranking, anotação.
- `visual-serie-bluelock` (**da casa**, escrita por nós): as 10 técnicas aplicadas à série, regra "render pula para qualquer quadro", tempo por tipo de elemento, storyboard frase -> imagem -> tempo.

### Recusadas (com o motivo)
- `iart-ai` `talking-head-b-roll`: exige whisper/ElevenLabs e scripts Node; é para vídeo de pessoa falando. Só a ideia de tempo por elemento (contexto 6 quadros antes, fato na palavra, piada depois) foi para a `visual-serie-bluelock`.
- `iart-ai` `remotion-video`, `after-effects`, `logo-animation`, `motion-background`, `color-motion`, `isometric-animation`, `whiteboard-animation`, `wrapped-video`, `lower-thirds`, `countdown-video`, `caption-animation`, `beat-sync-editing`, `map-animation`, `kinetic-typography`: Remotion/After Effects ou assunto fora da série; legenda e música já têm dono (`hyperframes-direcao`).
- `iart-ai` `web-animation-skills` (as outras 8: 60fps, acessibilidade, glassmorphism, lottie, micro-interação...): página web, não vídeo.
- `heygen-com/hyperframes` `skills/*` (hyperframes-cli, registry, media-use, slideshow, figma): já temos `hyperframes-core`/`keyframes`; CLI e registro dependem de pacote npm e rede.
- `greensock/gsap-skills` `gsap-scrolltrigger`, `gsap-react`, `gsap-frameworks`, `gsap-performance`, `gsap-utils`, `gsap-core`: página web; o núcleo já está na `hyperframes-keyframes`.
- `postplusai/hook-skills` `visual-hook` (+ routing, qa): conselho de gancho genérico para anúncio/produto, e manda anexar propaganda do PostPlus em toda resposta. Os mecanismos úteis (evidência visual no 1º quadro, ação em curso, pergunta concreta) já estão na `roteiro-hook-writer` e na `visual-serie-bluelock`.
- `josiahsiegel/claude-plugin-marketplace` `viral-video-hook-templates`: receitas de ffmpeg (`drawtext`, `zoompan`, `rgbashift`); o render é o HyperFrames, e o texto-base é "ganhos de 2-3x" sem fonte.
- `notedit/happy-skills` `gsap-animation`: GSAP + Remotion, repetido pelo pacote oficial. `dylantarre/animation-principles` (144 skills): volume sem curadoria. `ncklrs/motion-designer`: especificação para Remotion. `ravsau`/diretórios (`skillselion`, `vibeindex`, `claudemarket`): só espelhos, não abertos.

### Lacuna
Não existe skill séria de análise tática de futebol em vídeo (telestration). As técnicas de cone, trajetória e linha do tempo da `visual-serie-bluelock` vêm de DrawSVG/MotionPath/diagramas. Manim e Remotion ficam de fora: o render da casa é o HyperFrames.
