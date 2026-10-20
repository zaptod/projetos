# Ferramentas de vídeo por código e por IA: o que o pessoal está usando (out/2026)

Pesquisa feita em 20/10/2026 para o Neural Fights (duelos 1080x1920 em pygame/Godot, editados hoje
por Python + ffmpeg). Nada foi instalado e nenhum código foi alterado. Estrelas do GitHub foram lidas
em 20/10/2026. Quando uma fonte não confirmou um dado, isso está escrito.

---

## 0. Resumo em 6 linhas

1. **O que já temos é mais do que parece.** O nosso código já faz tremor de tela, flash, zoom,
   hitstop, câmera lenta (palco Godot), legenda karaokê com a hora de cada palavra da voz
   (`voz.py` pede `boundary="WordBoundary"` ao edge-tts), callouts e loudnorm. O que falta é
   **acabamento de motion graphics**: texto que entra com força, barra de vida com "dano
   fantasma", placar que rola, transições com shader, estilos de legenda variados.
2. **O que está em alta para isso:** vídeo como página web renderizada quadro a quadro:
   **HyperFrames** (HeyGen, Apache-2.0, 67,8 mil estrelas, já vem com plugin oficial para o
   Claude Code e um catálogo com centenas de blocos prontos) e **Remotion** (React, 65,4 mil
   estrelas, com skills oficiais para o Claude Code, grátis para quem trabalha sozinho).
3. **Pilha recomendada:** manter Python + ffmpeg como esqueleto, acrescentar **uma** camada de
   motion graphics (HyperFrames; o Remotion fica de reserva) renderizada com fundo transparente
   e posta por cima do clipe da luta, e trocar os sons por bancos **CC0** (Kenney, Sonniss GDC,
   Freesound filtrado por CC0).
4. **O que NÃO vale para nós:** RIFE e upscaling (nós geramos a imagem; câmera lenta boa se
   faz simulando mais quadros, e as nossas placas não têm Vulkan), Blender (o 5.0 não dá suporte
   às nossas GPUs), After Effects (pago), CapCut automatizado (sem API oficial, e os termos
   proíbem script) e Veo/Sora como conteúdo principal (cota pequena, marca d'água, risco de
   monetização).
5. **Maior risco:** tempo de render num i5-4590 sem GPU, porque o Chrome tira uma foto por
   quadro. Isso precisa ser **medido** na prova de conceito antes de qualquer adoção.
6. **Prova de 1 dia:** o mesmo duelo com 5 efeitos novos feitos nas duas ferramentas, medindo
   o tempo de render no i5 e no i3, se a saída se repete e se o Adrian prefere o vídeo novo no A/B.

---

## 1. Tabela comparativa

Legenda de "nossos PCs": **i5** = i5-4590/16 GB/Intel HD 4600; **i3** = i3-4170/8 GB/Radeon R5 220.

| Ferramenta | O que faz | Custo / licença | Roda nos nossos PCs? | Curva | Como encaixa no pipeline | Exemplo real | Fonte (data) |
|---|---|---|---|---|---|---|---|
| **HyperFrames** (HeyGen) | HTML/CSS/GSAP vira MP4 por Chrome sem tela + ffmpeg. Catálogo de blocos: 74 de texto/legenda, 31 transições, 96 de movimento/efeitos, 18 de gráficos/contadores | **Apache-2.0**, sem taxa por render nem limite comercial | Sim, só CPU. Node 22 + ffmpeg. **No Windows, o caminho determinístico não existe** (usa captura com "espera assentar"); o determinismo completo é só no Linux | Baixa para o Claude: ele escreve HTML. Para nós, zero | O Python grava `edit_plan.json` (barras, callouts, veredito); a composição HTML lê o arquivo e renderiza **WebM com transparência**; o ffmpeg põe por cima do clipe | Catálogo com exemplos animados: hyperframes.heygen.com/catalog (estilos "Kinetic Slam", "Pill Karaoke", "Highlight (TikTok-style)", "Particle Burst"; transição "flash-through-white") | [GitHub](https://github.com/heygen-com/hyperframes) (lido 20/10/2026); [HeyGen Research, 22/06/2026](https://www.heygen.com/research/html-to-video); [themenonlab, 20/09/2026](https://themenonlab.blog/blog/heygen-hyperframes-video-as-code) |
| **Remotion** | Vídeo como componente React (`interpolate`, `spring`), renderizado por Chrome sem tela | **Grátis** para indivíduo, empresa de até 3 pessoas e para "automação". Acima disso: US$ 25/mês por pessoa ("Creators") ou US$ 0,01 por render com mínimo de US$ 100/mês ("Automators"). Na 5.0, contratados passam a contar no total de pessoas | Sim, só CPU (Windows x64 suportado). Padrão: usa metade das threads. Não há número oficial de velocidade; o próprio Remotion manda medir com `npx remotion benchmark` | Média (React/TypeScript), mas as skills ensinam o Claude | Igual ao HyperFrames: lê o JSON por "props" e renderiza WebM VP8/VP9 `yuva420p` com transparência | GitHub Unwrapped (2021–2024); vitrine em remotion.dev/showcase | [Licença](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md); [FAQ da licença](https://www.remotion.dev/docs/license/faq); [transparência](https://www.remotion.dev/docs/transparent-videos); [benchmark](https://www.remotion.dev/docs/cli/benchmark) |
| **Motion Canvas** | Animação em TypeScript com editor ao vivo | MIT | Sim (navegador) | Média | Mesma ideia do Remotion, mas para render em lote é pior | Vídeos do canal aarthificial (o autor criou a ferramenta para eles) | **Original sem manutenção** (último commit em dez/2024, site fora do ar); o fork que segue é o "Canvas Commons" ([slama.dev](https://slama.dev/motion-canvas/1/); [HN](https://hn.nuxt.dev/item/47155375)) |
| **Revideo** | Fork do Motion Canvas feito para render por API/lote | MIT | Sim | Média | Serviria, mas é pequeno (4,1 mil estrelas, ~3 mil downloads/semana em mar/2026) | Motor do Midrender | [GitHub](https://github.com/redotvideo/revideo); [pkgpulse, 09/03/2026](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026) |
| **Manim** (Community) | Animação matemática em Python | MIT, 41,7 mil estrelas. v0.19.2 em 17/01/2026 (Python ≥ 3.11) | Sim, CPU (Cairo) | Média | Python puro; bom para gráfico de "estatística do lutador", fraco para ação | 3Blue1Brown | [GitHub](https://github.com/ManimCommunity/manim); [Zenodo v0.19.2](https://zenodo.org/records/18278418) |
| **Blender (bpy)** | 3D/2D (Grease Pencil) por script | Grátis (GPL) | **Mal.** O Blender 5.0 só dá suporte a Intel Kaby Lake+ e AMD GCN4+; a HD 4600 e a R5 220 ficam de fora. O Cycles na CPU funciona, mas é lento | Alta | Não encaixa: o visual já vai para o Godot | — | [Blender Artists, requisitos do 5.0](https://blenderartists.org/t/system-requirements-for-blender-5-0/1602460) |
| **MoviePy 2.x** | Edição em Python por cima do ffmpeg | MIT. v2.2.1 em 21/05/2025. A 2.0 quebrou a API (`subclipped`, `with_volume_scaled`...) e a v1 não recebe mais manutenção | Sim | Baixa | Não traz nada que o nosso `renderer.py` (PIL + ffmpeg) já não faça. Não vale migrar | Muitos canais "história do Reddit" automatizados | [PyPI](https://pypi.org/project/moviepy/); [GitHub](https://github.com/Zulko/moviepy) |
| **ffmpeg avançado** | `xfade` (dezenas de transições prontas), `zoompan` (Ken Burns), `crop` com expressão/`sendcmd` (tremor, panorâmica), `setpts`/`minterpolate` (velocidade), `ass` (legenda estilizada), `overlay` | Grátis | Sim (já usamos) | Média (sintaxe chata) | Já é o esqueleto. Continua sendo quem junta tudo, faz o loudnorm e codifica | — | [ottverse, xfade](https://ottverse.com/crossfade-between-videos-ffmpeg-xfade-filter/); [ffmpeg-user, crop+sendcmd](https://lists.ffmpeg.org/pipermail/ffmpeg-user/2020-December/051071.html) |
| **Godot (Movie Maker)** | Grava a cena com passo de tempo fixo (`--write-movie`, `--fixed-fps`), sem depender do PC aguentar tempo real | Grátis (MIT) | Sim (já usamos no palco, renderer de compatibilidade) | Já dominado | **Onde a câmera lenta, as partículas e o impacto devem morar**, porque ali controlamos o tempo da simulação | Anúncio oficial do Movie Maker | [docs Godot](https://docs.godotengine.org/en/latest/tutorials/animation/creating_movies.html); [anúncio](https://godotengine.org/article/movie-maker-mode-arrives-in-godot-4) |
| **After Effects automatizado** (nexrender) | Troca camadas de um modelo do AE por JSON e renderiza com `aerender` | nexrender é MIT, mas **exige o After Effects instalado (pago)** | Pesado demais para esses PCs | Alta | Não | — | [nexrender](https://github.com/inlife/nexrender) |
| **CapCut automatizado** (pyJianYingDraft / pyCapCut) | Gera o arquivo de rascunho do CapCut/JianYing por Python | Projeto da comunidade (~3,7 mil estrelas). **Não há API oficial**, e os termos do CapCut proíbem "scripts automatizados" (segundo uma resenha de um fornecedor; conferir) | A exportação automática só funciona no Windows com CapCut ≤ 6.8 | Média | Não: frágil e fora dos termos | — | [gittrend, pyJianYingDraft](https://gittrend.io/repo/GuanYixuan/pyJianYingDraft); [wireflow](https://www.wireflow.ai/blog/capcut-api) |
| **Legendas: faster-whisper / WhisperX / pycaps** | Transcreve com a hora de cada palavra; o pycaps desenha legenda animada com CSS (palavra "sendo narrada", modelos, emoji, som) | MIT | Sim, na CPU com int8. Referência: o modelo *small* levou 1m42s para 13 min de áudio num i7-12700K (no nosso i5 será bem mais lento, mas nossos áudios têm menos de 1 min) | Baixa | **Não precisamos do Whisper:** o edge-tts já devolve a hora de cada palavra. O pycaps só vale pelos estilos (renderizador CSS precisa de Playwright/Chromium; o "PicTex" não precisa de navegador) | Demo no Hugging Face (CPU) | [pycaps](https://github.com/francozanardi/pycaps); [faster-whisper (PyPI)](https://pypi.org/project/faster-whisper/1.0.0); [Fora Soft, 31/05/2026](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/whisperx-diarization-word-level-timestamps) |
| **RIFE (interpolação de quadros)** | Cria quadros intermediários (câmera lenta "falsa") | MIT | **Não serve:** o rife-ncnn-vulkan precisa de Vulkan, que a HD 4600 no Windows praticamente não tem (só um driver beta de 2016) e a R5 220 (TeraScale) não tem; na CPU é lento | — | **Desnecessário:** somos nós que geramos a luta, então câmera lenta perfeita = simular com passo menor e gravar mais quadros | — | [fórum Intel](https://community.intel.com/t5/Graphics/Vulkan-support-for-HD4600-on-windows/m-p/398463); [rife-ncnn-vulkan](https://github.com/TNTwise/rife-ncnn-vulkan) |
| **Upscaling (Real-ESRGAN etc.)** | Aumenta a resolução | Livre | Mesma falta de Vulkan | — | **Desnecessário:** já renderizamos em 1080x1920 nativo | — | — |
| **Sons grátis** | Kenney (CC0: "Impact Sounds" e outros), Sonniss GDC (pacote anual, uso comercial sem crédito, proibido treinar IA), Freesound (filtrar `license:"Creative Commons 0"`; o original exige OAuth2), Pixabay (licença própria, sem crédito), Mixkit (licença "free" serve para YouTube; existe uma "restricted" que NÃO serve) | Grátis | Sim | Baixa | Pasta de sons com `origens.jsonl` (prova de origem, como já fazemos com imagem) | — | [Kenney via Godot Assets](https://godotengine.org/asset-library/asset/edit/7723); [Sonniss GDC 2026 (rekkerd)](https://rekkerd.org/sonniss-releases-gdc-2026-game-audio-bundle/); [Pixabay FAQ](https://pixabay.com/service/faq/); [Mixkit](https://mixkit.co/llm-info/); [Freesound/CC](https://opensource.creativecommons.org/blog/entries/freesound-intro/) |
| **Veo (Gemini Pro)** | Gera clipes de vídeo de 8 s | Incluso no AI Pro: **3 por dia** (Veo 3.x Fast) | Nuvem | Baixa | No máximo um plano de abertura ou de fundo. Não serve para a luta (não é a nossa simulação) | — | [Android Authority](https://www.androidauthority.com/ai-pro-veo-3-fast-daily-generations-3565685/); [zenken, 2026](https://ai.zenken.co.jp/en/post/gemini-video-guide/) |
| **Sora (ChatGPT Plus)** | Gera clipes de vídeo | Plus: 720p, **com marca d'água**. A Wikipedia diz que o app fechou em 26/04/2026 e a API em 24/09/2026; **não confirmei em 2ª fonte** | Nuvem | Baixa | Não recomendo | — | [Wikipedia](https://en.wikipedia.org/wiki/Sora_(text-to-video_model)); [techpresso, jul/2026](https://academy.techpresso.co/reviews/is-sora-worth-it) |

---

## 2. Skills, plugins e MCP para o Claude Code ligados a vídeo

**Não existe plugin de vídeo da Anthropic.** Não achei nenhum no marketplace oficial
`claude-plugins-official` (busca de 20/10/2026), e um blog independente afirma o mesmo
([laozhang](https://blog.laozhang.ai/es/posts/claude-code-video-editing.md)). Os "oficiais" abaixo
são oficiais **do fabricante da ferramenta**.

| Nome | Link | Estrelas (20/10/2026) | Oficial? | O que faz de verdade | Serve para nós? |
|---|---|---|---|---|---|
| **HyperFrames** (plugin + 21 skills) | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | 67,8 mil | Sim, da HeyGen | `claude plugin marketplace add heygen-com/hyperframes` + `claude plugin install hyperframes@hyperframes` (ou `npx skills add heygen-com/hyperframes`). Ensina o Claude a escrever a composição HTML, adicionar blocos do catálogo (`npx hyperframes add flash-through-white`), pré-visualizar e renderizar. Tem até a skill `/remotion-to-hyperframes` | **Sim, candidata nº 1** |
| **Remotion Agent Skills** | [remotion-dev/skills](https://github.com/remotion-dev/skills) | 5,4 mil (o Remotion em si: 65,4 mil) | Sim, da Remotion | `npx skills add remotion-dev/skills`. Comandos: `/remotion-best-practices`, `/remotion-create`, `/remotion-markup` (animação, layout, tipografia, efeitos, áudio, tempo), `/remotion-studio`, `/remotion-render`, `/remotion-captions`, `/remotion-docs`, `/remotion-upgrade` etc. São guias de boas práticas; o Claude escreve o código | **Sim, candidata nº 2** ([docs](https://www.remotion.dev/docs/ai/skills)) |
| **Kinocut** (ex-`mcp-video`) | [KyaniteLabs/mcp-video](https://github.com/KyaniteLabs/mcp-video) | 212 | Não (comunidade) | MCP com **203 ferramentas** sobre ffmpeg: cortar, juntar, legenda, vinheta, brilho, aberração cromática, transições glitch/morph/pixelate, cortes para Shorts, transcrição (Whisper, ~1 GB). v1.16.1 em 05/10/2026 | Talvez como caixa de ferramentas, mas 203 ferramentas pesam no contexto, e o Claude já escreve ffmpeg direto |
| **video-use** | [browser-use/video-use](https://github.com/browser-use/video-use) | 29,4 mil | Não (da equipe do browser-use) | Edita **filmagem falada** pelo texto: corta muleta e silêncio, gradua cor, legenda, sobreposições. Precisa de chave da **ElevenLabs** | Não: o nosso vídeo não é gente falando |
| **blender-mcp** | [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) | 31,7 mil | Não (não é da Blender Foundation) | Claude controla o Blender: cena, objetos, Python arbitrário, assets do Poly Haven. Avisos do próprio README: soquete **sem autenticação**, executa código arbitrário, telemetria ligada por padrão | Não (GPU sem suporte, e o visual é Godot) |
| **manim-mcp-server** | [abhiemj/manim-mcp-server](https://mcpservers.org/servers/abhiemj/manim-mcp-server) | não confirmado | Não | Roda um script Manim e devolve o vídeo | Não |
| **Video Editor MCP** | [Kush36Agrawal/Video_Editor_MCP](https://glama.ai/mcp/servers/@Kush36Agrawal/Video_Editor_MCP/tree/74b373d5612a16068c39b630facfa1b5190ebc7c) | pequeno | Não | Uma ferramenta, `execute_ffmpeg` (recebe o comando inteiro) | Não acrescenta nada |
| **NIRA video MCP** | [claudemarketplaces](https://claudemarketplaces.com/mcp/pachote/nira-video-mcp) | não confirmado | Não | Diz ter 55 ferramentas ffmpeg (cor, master de áudio, motion graphics) | Não verificado |
| **open-edit** | [veedstudio/open-edit](https://gittrend.io/repo/veedstudio/open-edit) | ~211 | Da VEED | Edição pelo agente, legendas estilizadas | Não |
| **claude-video / claude-shorts** | [skillselion](https://skillselion.com/skills/agricidaniel/claude-video) | ~23 | Não | Junta ffmpeg, Whisper, PySceneDetect, Real-ESRGAN, Remotion; o claude-shorts corta vídeo longo em Shorts com legenda animada pelo Remotion | Só como leitura de exemplo |
| **pycaps** (biblioteca, não plugin) | [francozanardi/pycaps](https://github.com/francozanardi/pycaps) | 229 | — | Legenda animada com CSS, modelos, marcação de palavras | Talvez, se quisermos estilos de legenda sem o Node |

---

## 3. Efeitos em alta nos Shorts de luta/simulação, e quem faz cada um bem

O formato "simulação que luta sozinha" (bolas com armas no estilo Earclacks, que gerou jogos de
fã no Godot, no Roblox e no navegador; ver [CrazyGames](https://www.crazygames.com/br/game/ball-battle-simulator)
e [BallWarfare](https://rio-tatsuki.itch.io/ballwarfare)) vive de **sensação de impacto** e de
**ler o placar num relance**. As tendências de edição de 2026 citadas por fornecedores (speed
ramp na batida, texto cinético porque muita gente assiste sem som, cortes a cada 0,6–0,8 s no
estilo "alta energia", glitch e transições fortes nos primeiros segundos) estão em
[CapCut, 2026](https://www.capcut.com/help/latest-capcut-editing-trends),
[Opus, 12/05/2026](https://www.opus.pro/blog/editing-aesthetics-dominating-short-form-2026) e
[Influencers Time](https://www.influencers-time.com/kinetic-typography-enhances-short-form-video-performance/).
São fontes de quem vende ferramenta: servem de direção, não de medida.

Referência de "game feel": hitstop de 50–100 ms; tremor pequeno e proporcional ao golpe
("trauma"), porque tremor grande enjoa; empilhar flash + tremor + partícula + som no mesmo
instante ([wayline](https://www.wayline.io/learn/game-feel/1);
[eastondev, 21/05/2026](https://eastondev.com/blog/en/posts/dev/20260521-game-feedback-feel/)).

| Efeito | Já temos? | Quem faz melhor (para nós) | Por quê |
|---|---|---|---|
| **Hitstop** (congela 1–4 quadros no golpe forte) | Sim (palco: `hitstop_<tier>`) | **Godot / simulação** | Só o motor sabe o instante exato do contato |
| **Câmera lenta / speed ramp** | Parcial (`slowmo_whoosh` no palco) | **Godot / simulação**: diminuir o passo do tempo perto do golpe decisivo e voltar acelerando | Fica perfeita, sem os borrões da interpolação. `setpts`+`minterpolate` do ffmpeg só para trecho já gravado |
| **Zoom de impacto** (punch-in) | Sim (`zoom` no renderer) | **Câmera do motor** (sabe onde está o golpe); `crop`/`zoompan` do ffmpeg como plano B | Zoom no motor não perde resolução |
| **Tremor de tela** | Sim (`screen_shake`, `shake_small`) | Câmera do motor, ou `crop` com expressão `sin(t)` no ffmpeg | — |
| **Flash** | Sim (`flash`, `flash_frames`) | Qualquer um; transição "flash-through-white" do HyperFrames | — |
| **Partículas** (faísca, poeira, sangue estilizado) | Parcial | **Godot `CPUParticles2D`** (roda em GPU fraca) para o que encosta na luta; blocos "Particle Burst" do HyperFrames para o que fica por cima | Partícula presa ao mundo precisa do motor |
| **Texto cinético / carimbo "K.O."** | Callouts estáticos ou simples | **HyperFrames (GSAP) ou Remotion (`spring`)** | Curvas de animação, escala com "mola", desfoque de movimento: em HTML isso é uma linha; em PIL dá muito trabalho |
| **Placar / contador animado** | Sim, simples | **HyperFrames** ("Split-Flap Board", gráficos) ou Remotion `interpolate` | Números rolando e "batendo" no lugar |
| **Barra de vida animada** (dano fantasma branco que desce atrasado, piscar no crítico) | Barra existe | **HyperFrames/Remotion** lendo a série de vida do `edit_plan.json` | É dado que vira animação: ponto forte dessas ferramentas |
| **Transições** | Cortes | `xfade` do ffmpeg (dezenas prontas) ou as **31 transições** com shader do HyperFrames | — |
| **Legendas animadas** (karaokê, palavra que pula, destaque) | Sim (karaokê desenhado em PIL) | **HyperFrames** ("Pill Karaoke", "Kinetic Slam", "Highlight (TikTok-style)") ou pycaps; ASS + filtro `ass` do ffmpeg como caminho barato em Python | Já temos a hora de cada palavra pelo edge-tts. Falta variedade de estilo |
| **Som de impacto em camadas** | Sim (sons da luta) | Kenney "Impact Sounds" (CC0) + Sonniss GDC + Freesound CC0 | Um "tum" grave + um estalo agudo + o whoosh no mesmo quadro do hitstop |

**Ideia que vale ouro:** tudo que depende do **tempo da luta** (hitstop, câmera lenta, zoom,
partícula presa ao mundo) fica no motor. Tudo que é **informação por cima** (texto, placar,
barra, legenda, transição) vai para a camada de motion graphics.

---

## 4. Recomendação: pilha para começar (3 peças)

1. **Python + ffmpeg (o que já existe) continua sendo o esqueleto.** Ele roda a luta, grava o
   `edit_plan.json`, junta as camadas, faz o loudnorm e codifica. Nada é jogado fora.
2. **HyperFrames como camada de motion graphics; o Remotion fica de reserva.**
   - Por que o HyperFrames primeiro: licença Apache sem nenhuma condição (o Remotion é grátis
     para nós hoje, mas tem regra de número de pessoas, que muda na 5.0); plugin oficial para o
     Claude Code; feito para um agente escrever HTML (que o Claude escreve melhor que React);
     catálogo com legendas, transições, contadores e efeitos prontos.
   - Por que o Remotion na reserva: é mais maduro (desde 2021, versão 4.x estável) e tem skills
     oficiais. Se o HyperFrames no Windows sair instável (ele não tem o modo determinístico
     no Windows), o Remotion é a troca natural; o próprio HyperFrames converte composição do
     Remotion.
   - Como encaixa: `edit_plan.json` → composição (escrita uma vez pelo Claude, depois roda
     sozinha sem Claude) → **WebM com transparência** 1080x1920 → `ffmpeg -c:v libvpx-vp9 -i
     overlay.webm ... overlay` por cima do clipe da luta. Atenção: sem o `-c:v libvpx-vp9`
     **antes** do `-i`, o ffmpeg joga fora a transparência
     ([videobgremover](https://docs.videobgremover.com/video-background-removal/output-formats.md)).
3. **Sons CC0 com prova de origem.** Kenney + Sonniss GDC + Freesound (só CC0), cada arquivo
   registrado num `origens.jsonl`, como já fazemos com imagem. Música do Pixabay pode levar
   reivindicação do Content ID mesmo com licença: preferir efeito sonoro a música de banco.

Não recomendo agora: Blender, After Effects, CapCut, RIFE, upscaling, MoviePy (migrar não traz
nada), Kinocut/video-use (não são para o nosso tipo de vídeo), Veo/Sora na luta.

O ChatGPT Plus e o Gemini Pro entram onde já entram: o ChatGPT gera arte estática (selo "K.O.",
fundos, ícones) pela esteira de sprites; o Gemini assiste ao mp4 e aponta "o que está errado"
(ele não ouve; o som quem julga é o Adrian).

---

## 5. Riscos

| Risco | Tamanho | Como medir / evitar |
|---|---|---|
| **Render lento no i5/i3 sem GPU.** O Chrome tira uma foto por quadro: 45 s a 30 fps são 1.350 fotos, e com transparência são PNG, que é mais lento que JPEG. Referência de terceiros: ~2 min para uma composição de 11 s numa máquina Linux de 4 vCPU ([Vercel template](https://vercel.com/new/jvtubs-projects/templates/next.js/hyperframes-on-vercel)). **Estimativa minha, não medida:** 5–15 min por vídeo no i5 | Alto | Medir na prova. Renderizar só a camada de cima (fundo transparente, poucos elementos). Rodar de madrugada (01h–06h) |
| **RAM do i3 (8 GB)** com vários Chrome em paralelo | Médio | `--workers 1` no i3; o paralelo fica para o i5 |
| **HyperFrames no Windows não é determinístico** (usa "esperar assentar") e o projeto é jovem (v0.x, versões quase toda semana, com correções de Windows em 0.7.27, 0.7.32, 0.7.37, 0.7.42) | Médio | Fixar a versão. Renderizar o mesmo vídeo duas vezes e comparar os quadros. Se variar, ir para o Remotion |
| **Duas pilhas** (Node + Python) para manter | Médio | O Node fica isolado numa pasta, chamado por um único `subprocess` com entrada e saída em arquivo, como o Godot hoje |
| **Licença do Remotion**, se a equipe passar de 3 pessoas (na 5.0, contratado conta) | Baixo hoje | Mais um motivo para começar pelo HyperFrames |
| **Telemetria** (Remotion: a do lado do cliente sempre ligada; blender-mcp: ligada por padrão) | Baixo | Desligar onde dá; documentar |
| **YouTube: conteúdo "inautêntico"** (a regra de 15/07/2025 tira a monetização do que é produzido em massa e repetitivo) | Médio para canal automático | Edição melhor ajuda, mas um **modelo igual em todo vídeo** atrapalha. Fazer rodízio de estilos (legenda, transição, cor do K.O.), como já fazemos com as alavancas ([Plagiarism Today, 08/07/2025](https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/)) |
| **Content ID em música de banco grátis** | Médio | Guardar a prova da licença; preferir CC0 e efeito sonoro |
| **Claude proibido em alguns períodos** | Baixo | O Claude escreve as composições uma vez; a produção roda sem ele |
| **Janela das postagens / app que nunca cai** | — | A prova roda numa worktree, fora da grade, sem reiniciar nada e sem tocar no catálogo |

---

## 6. Prova de conceito de 1 dia

**Pergunta que a prova responde:** "uma camada de motion graphics feita pelo Claude deixa o
duelo visivelmente melhor, renderiza nos nossos PCs num tempo que cabe na madrugada e sai igual
toda vez?"

**Antes de começar:** checar `python -m remoto.orquestrador claude status`; trabalhar numa
worktree e numa pasta temporária no E: (`TEMP=E:\tmp_...`); escolher **1 duelo já publicado**
(com `final_<perfil>.mp4`, `edit_plan.json` e as palavras da voz). Nada entra no catálogo, e o
app e o carteiro não são reiniciados.

| Hora | Passo | O que medir |
|---|---|---|
| 0:00–0:45 | Instalar Node 22, HyperFrames (versão fixa) e o plugin do Claude Code numa pasta isolada; Remotion + `npx skills add remotion-dev/skills` noutra | Instalou sem erro de PATH? (é a falha mais comum no Windows) |
| 0:45–3:00 | **Teste A (HyperFrames):** o Claude escreve UMA composição que lê o `edit_plan.json` e faz 5 coisas: (1) barra de vida com dano fantasma, (2) carimbo "K.O." com texto cinético, (3) placar que rola, (4) legenda karaokê em estilo de pílula usando as palavras do edge-tts, (5) transição flash para o veredito. Renderizar **só a camada de cima** em WebM transparente 1080x1920 30 fps | Tempo de render no **i5** e no **i3** (com `--workers 1` e `auto`); pico de RAM; tamanho do arquivo |
| 3:00–5:00 | **Teste B (Remotion):** a mesma coisa, com as skills | Os mesmos números |
| 5:00–5:45 | Juntar com o ffmpeg: `-c:v libvpx-vp9 -i overlay.webm` + `overlay` por cima do clipe, sem o HUD antigo, mantendo o loudnorm | A transparência sobreviveu? O som ficou igual? |
| 5:45–6:30 | Repetir o render da camada de cima **duas vezes** e comparar os quadros (hash ou SSIM) | É determinístico? (no HyperFrames/Windows é o ponto fraco) |
| 6:30–7:15 | Trocar 3 sons de impacto por camadas Kenney/Sonniss, com `origens.jsonl` | Licença anotada para cada arquivo |
| 7:15–8:00 | **Juízo:** o `conferente` abre o mp4 (quadros sobre fundo de contraste); o Gemini assiste e diz "o que está errado"; A/B para o Adrian no app (atual × novo, ordem sorteada) | Escolha do Adrian; defeitos listados |

**Passa ("vale") se TUDO isto for verdade:**
- a camada de cima de um duelo de ~45 s renderiza em **≤ 10 min no i5** e roda no i3 sem
  estourar a RAM;
- dois renders saem iguais (ou a diferença é invisível e não muda o tempo);
- zero passo manual depois que a composição está escrita;
- **o Adrian escolhe o vídeo novo** no A/B (e o Gemini não aponta defeito novo grave).

**Decisão:** se A e B passam, fica o HyperFrames (licença mais simples), a não ser que o B seja
claramente mais estável no Windows. Se só um passa, fica esse. Se nenhum passa por tempo de
render, o plano B é levar os 2–3 efeitos que mais agradaram para o próprio `renderer.py`
(curvas de easing e "mola" em PIL) e para o Godot, sem uma pilha nova.

---

## 7. Fontes principais (com data)

- Remotion: [skills (docs)](https://www.remotion.dev/docs/ai/skills) · [repo das skills](https://github.com/remotion-dev/skills) · [LICENSE](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) · [FAQ da licença](https://www.remotion.dev/docs/license/faq) · [preços](https://www.remotion.dev/docs/license/pricing) · [migração 5.0](https://www.remotion.dev/docs/5-0-migration) · [transparência](https://www.remotion.dev/docs/transparent-videos) · [desempenho](https://www.remotion.dev/docs/performance) · [Chrome Headless Shell](https://www.remotion.dev/docs/chrome-headless-shell) · [Tella, 27/08/2026](https://www.tella.com/blog/how-to-use-remotion-agent-skills-with-claude-code)
- HyperFrames: [GitHub](https://github.com/heygen-com/hyperframes) · [catálogo](https://hyperframes.heygen.com/catalog) · [HeyGen Research, 22/06/2026](https://www.heygen.com/research/html-to-video) · [themenonlab, 20/09/2026](https://themenonlab.blog/blog/heygen-hyperframes-video-as-code) · [silenceper, 02/05/2026](https://silenceper.com/en/article/2026-05-02-hyperframes-html-video-rendering/) · [conector Claude](https://claude.com/connectors/hyperframes-heygen) · [notas de versão no Windows](https://newreleases.io/project/github/heygen-com/hyperframes/release/v0.7.42) · [guia Windows (terceiro)](https://autoae.online/blog/hyperframes-topic2video-windows-setup)
- Comparativo: [pkgpulse, 09/03/2026](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026) · Motion Canvas: [slama.dev](https://slama.dev/motion-canvas/1/) · Revideo: [GitHub](https://github.com/redotvideo/revideo)
- MCP/skills: [Kinocut](https://github.com/KyaniteLabs/mcp-video) · [video-use](https://github.com/browser-use/video-use) · [blender-mcp](https://github.com/ahujasid/blender-mcp) · [marketplace oficial](https://code.claude.com/docs/en/discover-plugins?m=1) · [laozhang (sem plugin oficial de vídeo)](https://blog.laozhang.ai/es/posts/claude-code-video-editing.md) · [Medium, 4 ferramentas](https://medium.com/@umair349hassan/how-to-use-claude-code-for-video-editing-4-github-tools-with-install-steps-72cf6be7f04e)
- Hardware: [Blender 5.0 (requisitos)](https://blenderartists.org/t/system-requirements-for-blender-5-0/1602460) · [Vulkan na HD 4600 (Intel)](https://community.intel.com/t5/Graphics/Vulkan-support-for-HD4600-on-windows/m-p/398463)
- Godot Movie Maker: [docs](https://docs.godotengine.org/en/latest/tutorials/animation/creating_movies.html)
- Legendas: [pycaps](https://github.com/francozanardi/pycaps) · [faster-whisper](https://pypi.org/project/faster-whisper/1.0.0) · [WhisperX (Fora Soft, 31/05/2026)](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/whisperx-diarization-word-level-timestamps)
- Som: [Pixabay FAQ](https://pixabay.com/service/faq/) · [Mixkit](https://mixkit.co/llm-info/) · [Sonniss GDC 2026](https://rekkerd.org/sonniss-releases-gdc-2026-game-audio-bundle/) · [Kenney Impact Sounds](https://godotengine.org/asset-library/asset/edit/7723) · [Freesound + CC](https://opensource.creativecommons.org/blog/entries/freesound-intro/)
- Plataforma: [YouTube "inautêntico" (Plagiarism Today, 08/07/2025)](https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/) · [Gulf News](https://gulfnews.com/technology/youtube-updates-monetisation-policies-ai-and-repetitive-content-ban-begins-july-15-1.500192660)
- IA generativa: [Veo no AI Pro (Android Authority)](https://www.androidauthority.com/ai-pro-veo-3-fast-daily-generations-3565685/) · [Sora (Wikipedia; fechamento não confirmado)](https://en.wikipedia.org/wiki/Sora_(text-to-video_model))
- CapCut/AE: [pyJianYingDraft](https://gittrend.io/repo/GuanYixuan/pyJianYingDraft) · [nexrender](https://github.com/inlife/nexrender)
