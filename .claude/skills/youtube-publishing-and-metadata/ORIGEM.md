# ORIGEM: youtube-publishing-and-metadata

- **Fonte:** https://github.com/social-media-skills/skills/tree/f28cef2b7067ec64e79c9d85421c022c06659e03/skills/youtube-publishing-and-metadata (comunitário, Frank Heijdenrijk; 200 estrelas, MIT, último push 15/10/2026, pela API em 26/10/2026)
- **Commit:** `f28cef2b7067ec64e79c9d85421c022c06659e03` (26/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 26/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\redes\social-media-skills_skills\`
- **Lido por:** subagente de pesquisa (Claude), `SKILL.md` e as 4 `references/*.md` inteiros. Busca por URL, `curl`, `npx`, `pip`, `npm`, `fetch`, chave de API, telemetria, scraping, proxy, bot e evasão: o único endereço é o do WoopSocial (agendador pago de terceiros), só citado. Nenhum script executado (a skill não traz script; `evals/evals.json` não copiado).
- **Copiado:** `SKILL.md` + `references/*.md`, sem alteração, **exceto** um parágrafo "AVISO DA CASA" inserido logo depois do frontmatter do `SKILL.md`.
- **Classificação:** APROVADA COM CAUTELA (só o texto entra; a parte de publicar pelo WoopSocial é ignorada).
- **Decisão:** pedido do Adrian em 26/10/2026 ("skills de análise e postagem de cada rede").

## Para que serve, e a quem
Título (palavra-chave cedo, clareza), descrição, capítulos, tags, categoria, privacidade e a marca "feito para crianças" (COPPA/FTC) do YouTube; Teste e Comparação de títulos/miniaturas no Studio. Serve à POSTAGEM do duelo (título com o confronto, descrição, hashtags).

## Cuidados neste repositório
- Escrita para vídeo longo e busca (descrição de 300-500 palavras, capítulos). Para Short, aproveite a parte do título e das hashtags e ignore o resto.
- **"Feito para crianças" é marcação legal, não alavanca de alcance.** Duelo de personagens de jogo pode ser lido como feito para crianças: decidir com verdade (registrar no Grimório se houver dúvida), nunca marcar para ganhar alcance.
- Teste e Comparação de títulos é recurso do Studio (conta do canal), não de API.
- **WoopSocial (e `scheduling-and-queue`) é serviço pago de terceiros: NÃO usar.** Os campos `title/privacy/category/tags/madeForKids` são dele; no navegador valem os equivalentes do YouTube Studio. Publicar é com `ferramentas/postar.py` e `publicar/*`; ver `publicacao-grade-e-guardas`.
- Cita skills irmãs **não** instaladas (`youtube-long-form`, `thumbnail-design`, `brand-profile`, `goals-and-kpis`...). Ignore.
- **Nunca agir em página pública pela conta pessoal do Adrian.** Nenhuma automação de engajamento, multicontas disfarçadas ou evasão de detecção.
- Números de CTR/impressões ("+8,3% CTR", "+23% impressões") vêm sem link: hipóteses, não metas.
- As leis do `CLAUDE.md` vencem a skill (janela das postagens, commit por caminho).
