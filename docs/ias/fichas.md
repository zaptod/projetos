# As fichas das IAs — tabela comparativa (fase 1 da Vila das IAs)

Medido em **29/09/2026, 01:44–02:40**, nas sessões guiadas pelo Adrian (ordem
dele às 01:35: "abra uma sessão de cada um para eu fazer o guia") — Grok,
Gemini, ChatGPT e DeepSeek com o navegador na tela dele; PicassoIA, DreamFace
e Digen pelo **padrão que já existe em produção** (ordem dele às 02:3x).
A fonte de cada linha está no JSON (`ias/fichas/<ia>.json`, schema em
`ficha.md`); as provas (capturas, DOM, `colado.jsonl` da janela flutuante,
`testes.jsonl`) em `random_builds/outputs/_ias/<ia>/guia/` (fora do git).
`python -m ias fichas` reimprime a tabela crua; esta aqui é a resumida.

| IA | login | texto ("OK") | modelos | anexos | gera imagem | vídeo | cota (o que o site diz) | grátis / pede plano | erros catalogados |
|---|---|---|---|---|---|---|---|---|---|
| **Grok** (grok.com, conta X dele) | logado (perfil `grok__principal`) | sim; tempo não medido (fechou antes do teste) | Fast (grátis), Build; **Auto/Expert/Heavy → `#subscribe`** | imagem (`attach-button`, input `files` multiple, accept vazio) | **sim** — Imagine (Velocidade grátis; Qualidade 2.0?) | gera (Imagine Vídeo 480p/6s grátis; 720p/10s/15s pagos) | Configurações → Uso: pool **semanal** por produto (não aberto) | SuperGrok oferecido 3x; "Atualizar plano" | parede `#subscribe`, upsell SuperGrok, "Trabalhou por 9s" |
| **Gemini** (conta da pipeline) | logado | sim (`Pro`); tempo não medido | 3.6 Flash / 3.5 Flash Lite / **3.1 Pro** / Raciocínio complexo, sufixo Estendido | arquivos, Drive, Google Fotos, GitHub, Notebooks (+ Criar imagem/vídeo/música) | **sim** ("crie uma banana"; botão "Baixar imagem no tamanho original") | **assiste** (produção) e "Criar vídeo" no menu | **/usage**: pool de **5 h** (2 %, reset 03:01) + **semanal** (13 %, reset 1/10 12:01); selo **PLUS** | AI Pro R$ 96,99/mês = 2x o limite | recusa enlatada (4 frases), "Algo deu errado (1155)", consentimento de vídeo, "Parar resposta" |
| **ChatGPT** (Free) | logado | **OK em 6 s** (turno 15,9 s) | sem seletor no Free; pill **Pensar** | foto (`image/*`), mídia (`image/*,video/*`), arquivo (qualquer) | existe "Criar imagem" no `+`; não gerado | não assiste (mp4 vira "Arquivo" opaco) | nada na tela; só aparece ao estourar | Free; "Fazer upgrade" / "Ver planos" | Cloudflare (headless), "Entre para usar", citação web (`webpage-citation-pill`) |
| **DeepSeek** (grátis) | logado | **OK em 6 s** | sem modelo; toggles **DeepThink** e Search | imagem pelo clipe | **não** (site não oferece — "é só isso") | não | nenhum aviso na tela | tudo grátis | "Thought for N seconds", placeholder agora "Message DeepSeek" |
| **PicassoIA** (conta compartilhada) | logado | não é chat | PicassoIA Image; 24+ "Ilimitados" (Seedance 2.5 Lite, GPT Image 2.5…) | 1 imagem só no Editor Pro | **sim**, 1088x1920 em 9:16, JPG sem alfa, ~9–42 s | gera (site: 720p/10s) | "Gerar GRÁTIS"; **2 em paralelo** ("limite de gerações em paralelo"); +5 com créditos | plano ilimitado; modelos com relógio azul pedem crédito | **CONTEÚDO ILEGAL** (102x), parede "Planos e Créditos", modal de login, "Assine para Gerar" (sessão ruim), sem prova de origem (43x) |
| **DreamFace** | não medido (perfil de 01/09) | não é chat | Dream Image 2.0, GPT Image 2, Seedream 5.0 Pro/4.5/4.0 | imagem de referência | **nunca gerou** (só seletores; créditos 0 em 01/09) | não usado | créditos 0 (01/09) | pede crédito | insufficient/out of credits, Generation failed, login modal com reCAPTCHA |
| **Digen** (conta compartilhada) | não medido | não é chat | Real Motion 3.5 (RM3.5 Fast em promo) | 1 imagem de referência | não (vídeo) | **gera** (payoff das builds, ~295 s, timeout 1800 s) | chip "UltraMax, Meme 3, Pro Meme 0" (2 etapas, ~15 s) | RM incluso; créditos p/ outros modelos | parede "Upgrade / 20% OFF RM3.5 Fast" (10–15 s após carregar), insufficient credits, Generation failed |

Coluna "casa" (decisão `ias-chat-persistente`, 29/09: um chat de longa duração
por IA, com resumo periódico):

| IA | chat longo aguenta? | renomear / fixar | memória entre chats | projetos |
|---|---|---|---|---|
| Grok | não medido | não visto | **sim** ("Personalize o Grok com seu histórico", Beta, ligado) | sim ("Adicionar projeto") |
| Gemini | **sim** (a pipeline já escreve uma história inteira num chat; armadilha: ler a resposta anterior — o cliente ancora no último turno) | Fixar e renomear no menu do chat | não medido | Gems |
| ChatGPT | não medido (Free: contexto menor) | renomear/arquivar no "…" | não medido | sim |
| DeepSeek | **sim** (roteiros inteiros num chat) | "…" por chat | não | não |
| PicassoIA / DreamFace / Digen | não é chat (Digen: um Space por geração) | — | — | Digen: Space |

## O que cada uma tem de particular (medido hoje)

- **Grok**: deslogado o campo é um `<textarea>`; logado é um `div[role=textbox]` ProseMirror dentro de `[data-testid=chat-input]` — a sonda automática das 01:44 deu "logado" para a página anônima por causa do textarea genérico (e mandou 1–2 mensagens antes do login dele: "Círculo de cor vermelha" na barra lateral). Resposta em `[data-testid=assistant-message]` com `thinking-container` antes do texto. Imagine: aba "Gerações" mostra o que a conta gerou (prova de origem = post da própria conta, `?scope=asset`); "Remover fundo", "Fazer Vídeo", "Aspecto de proporção" no post.
- **Gemini**: a conta que a pipeline usa está com o selo **PLUS** em `/usage` — a nota de 27/09 dizia "free" e a decisão `gemini-pago` é "fica na gratuita". É fato novo para ele ver, não decisão minha. Cota real: 5 h + semanal; "modelos e recursos avançados consomem mais".
- **ChatGPT**: os seletores de `contos/llm/seletores.py` já batiam com tudo o que ele colou (`#prompt-textarea`, `send-button`, `composer-plus-btn`, `div.markdown`); teste na janela dele: OK em 6 s.
- **DeepSeek**: "é só isso" (Adrian). O placeholder mudou para inglês ("Message DeepSeek"); o candidato genérico `textarea[placeholder*='DeepSeek' i]` cobre.
- **PicassoIA**: texto novo para o catálogo: "Você atingiu seu limite de gerações em paralelo. Espere uma terminar." (tooltip do botão, logo após Gerar). O histórico mostrou o card de outra pessoa no topo — a prova de origem forte (card com o NOSSO prompt) continua obrigatória. Formato webp/jpg/png nas Opções avançadas; tempo estimado do site (1–2 min) é maior que o real (card: 7,64 s; produção 9–42 s).

## O que ficou sem medir, e por quê

- Tempo do "OK" no **Grok** e no **Gemini**: ele fechou a janela antes do `testar_ok` (1 mensagem cada, quando quiser).
- **Limite de caracteres do campo** em todas (a medida planejada — colar 120 mil chars sem enviar — não roda na sessão guiada; `python -m ias sondar <ia> --sem-gastar` faz).
- **Imagem 1:1 com resolução/alfa** no Grok (Imagine), Gemini e ChatGPT: uma geração cada, com download; no PicassoIA a de 9:16 já é medida em produção (1088x1920, JPG).
- **Grok: Configurações → Uso** (a cota semanal real) não foi aberta.
- **DreamFace e Digen**: login/créditos de hoje não conferidos (`python main.py identity doctor --online` no random_builds faz sem gerar).
- Mensagens de **limite estourado** (Gemini "Você atingiu o limite…", ChatGPT Free, Grok) só aparecem ao estourar: ficam com o texto genérico do catálogo até a primeira vez que a produção as vir.
