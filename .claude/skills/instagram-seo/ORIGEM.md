# ORIGEM: instagram-seo

- **Fonte:** https://github.com/social-media-skills/skills/tree/f28cef2b7067ec64e79c9d85421c022c06659e03/skills/instagram-seo (comunitário, Frank Heijdenrijk; 200 estrelas, MIT, último push 15/10/2026, pela API em 26/10/2026)
- **Commit:** `f28cef2b7067ec64e79c9d85421c022c06659e03` (26/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 26/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\redes\social-media-skills_skills\`
- **Lido por:** subagente de pesquisa (Claude), `SKILL.md` e as 4 `references/*.md` inteiros (a `scope-and-connections.md` só por busca de risco e leitura do começo). Busca por URL, `curl`, `npx`, `pip`, `npm`, `fetch`, chave de API, telemetria, scraping, proxy, bot e evasão: o único endereço é o do WoopSocial, só citado. Nenhum script executado (`evals/evals.json` não copiado).
- **Copiado:** `SKILL.md` + `references/*.md`, sem alteração, **exceto** um parágrafo "AVISO DA CASA" inserido logo depois do frontmatter do `SKILL.md`.
- **Classificação:** APROVADA COM CAUTELA (só o texto entra; a parte de publicar pelo WoopSocial é ignorada).
- **Decisão:** pedido do Adrian em 26/10/2026 ("skills de análise e postagem de cada rede"; Instagram Reels específico).

## Para que serve, e a quem
Busca do Instagram por palavra-chave (hashtags viraram 3-5 rótulos): legenda com a palavra principal nos primeiros ~125 caracteres, campo Nome, bio, texto alternativo, texto na tela e a palavra dita nos 3 primeiros segundos, e a regra de que texto e imagem precisam combinar (visão computacional). Serve à POSTAGEM do Reel (legenda e hashtags).

## Cuidados neste repositório
- "Pesquisar palavra-chave" aqui é olhar os Reels do topo e o "As pessoas também perguntam" do Google, **manualmente**. Nada de raspagem em massa nem ferramenta de terceiros.
- A skill manda não inventar volume de busca: nenhum número de volume entra no Grimório sem fonte.
- O efeito de busca é lento (30-120 dias, segundo a skill): não medir em uma semana.
- **WoopSocial é serviço pago de terceiros: NÃO usar** (a legenda ia por `content.text` dele). Publicar é `ferramentas/postar.py` e `publicar/*`.
- Cita skills irmãs **não** instaladas (`caption-writer`, `hashtag-strategy`, `reels-script`, `social-seo`...). Ignore.
- **Nunca agir em página pública pela conta pessoal do Adrian.** Nenhuma automação de engajamento, multicontas disfarçadas ou evasão.
- As leis do `CLAUDE.md` vencem a skill.
