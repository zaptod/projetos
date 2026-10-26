# ORIGEM: tiktok-video-publishing

- **Fonte:** https://github.com/social-media-skills/skills/tree/f28cef2b7067ec64e79c9d85421c022c06659e03/skills/tiktok-video-publishing (comunitário, Frank Heijdenrijk; 200 estrelas, MIT, último push 15/10/2026, pela API em 26/10/2026)
- **Commit:** `f28cef2b7067ec64e79c9d85421c022c06659e03` (26/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 26/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\redes\social-media-skills_skills\`
- **Lido por:** subagente de pesquisa (Claude), `SKILL.md` e as 4 `references/*.md` inteiros. Busca por URL, `curl`, `npx`, `pip`, `npm`, `fetch`, chave de API, telemetria, scraping, proxy, bot e evasão: o único endereço é o do WoopSocial, só citado. Nenhum script executado (`evals/evals.json` não copiado).
- **Copiado:** `SKILL.md` + `references/*.md`, sem alteração, **exceto** um parágrafo "AVISO DA CASA" inserido logo depois do frontmatter do `SKILL.md`.
- **Classificação:** APROVADA COM CAUTELA (só o texto entra; a parte de publicar pelo WoopSocial é ignorada).
- **Decisão:** pedido do Adrian em 26/10/2026 ("skills de análise e postagem de cada rede").

## Para que serve, e a quem
Configuração da postagem de um vídeo no TikTok: legenda como busca (palavra-chave nos primeiros ~100 caracteres), duetar/costurar/comentar ligados, capa, marcação de conteúdo de marca e de IA, especificações (1080x1920, MP4, limites) e a diferença entre postar direto e mandar para a caixa de entrada para pôr som em alta. Serve à POSTAGEM dos duelos no TikTok Studio (navegador).

## Cuidados neste repositório
- Os campos (`postType`, `postMode`, `MEDIA_UPLOAD`, `autoAddMusic`, `isBrandedContent`) são do WoopSocial, não do TikTok Studio. No navegador valem os equivalentes: legenda, capa, "permitir comentários/dueto/costura", "conteúdo gerado por IA", visibilidade.
- Marcação de IA: o TikTok exige rótulo visível em pessoas/vozes/cenas realistas geradas; deepfake de pessoa real e "endosso" por IA são proibidos. Duelo de personagens de jogo está fora disso, mas conferir o toggle de IA no Studio.
- **WoopSocial (e `scheduling-and-queue`) é serviço pago de terceiros: NÃO usar.** Publicar é `ferramentas/postar.py` e `publicar/*`; ver `publicacao-grade-e-guardas`.
- Cita skills irmãs **não** instaladas (`tiktok-script`, `tiktok-photo-mode`, `platform-specs-and-validation`...). Ignore.
- **Nunca agir em página pública pela conta pessoal do Adrian.** Nenhuma automação de engajamento (comentário fixado e resposta são manuais), multicontas disfarçadas ou evasão.
- "+5% views por hashtag", "96% do alcance nos 10 primeiros dias": sem link, hipóteses.
- As leis do `CLAUDE.md` vencem a skill (janela das postagens, commit por caminho).
