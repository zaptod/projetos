# ORIGEM: youtube-shorts

- **Fonte:** https://github.com/social-media-skills/skills/tree/f28cef2b7067ec64e79c9d85421c022c06659e03/skills/youtube-shorts (comunitário, Frank Heijdenrijk; 200 estrelas, MIT, último push 15/10/2026, pela API em 26/10/2026)
- **Commit:** `f28cef2b7067ec64e79c9d85421c022c06659e03` (26/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 26/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\redes\social-media-skills_skills\`
- **Lido por:** subagente de pesquisa (Claude), `SKILL.md` e as 4 `references/*.md` inteiros. Busca por URL, `curl`, `npx`, `pip`, `npm`, `fetch`, chave de API, telemetria, scraping, proxy, bot e evasão em todos os `.md`: o único endereço é o do WoopSocial (agendador pago de terceiros), só citado. Nenhum script executado (a skill não traz script; o `evals/evals.json` não foi copiado).
- **Copiado:** `SKILL.md` + `references/*.md`, sem alteração, **exceto** um parágrafo "AVISO DA CASA" inserido logo depois do frontmatter do `SKILL.md`.
- **Classificação:** APROVADA COM CAUTELA (só o texto entra; a parte de publicar pelo WoopSocial é ignorada).
- **Decisão:** pedido do Adrian em 26/10/2026 ("skills de análise e postagem de cada rede").

## Para que serve, e a quem
Shorts do YouTube: a lógica de distribuição (Viewed vs Swiped Away, teste de 30-60 min numa audiência semente, % médio assistido, replay acima de 100%), a Escada de Retenção (parar, segurar, ângulo, ponte), o gancho no quadro 1, legenda queimada, tamanho e cadência, divulgação de conteúdo alterado por IA e Content ID em Shorts. É a skill de ANÁLISE e otimização dos duelos no YouTube; complementa `metricas-youtube-analytics` (que mede) e `hyperframes-direcao` (que dirige o vídeo).

## Cuidados neste repositório
- A divulgação "conteúdo alterado" existe no envio do YouTube: conferir se o fluxo do navegador a marca nos duelos gerados. O aviso de Content ID acima de 1 minuto vale para a trilha.
- "The Flattening" (Shorts perdem força após ~28-30 dias) é afirmação da skill: confirmar na curva de views por idade do próprio canal antes de agir.
- **WoopSocial (e `scheduling-and-queue`) é serviço pago de terceiros: NÃO usar.** Mandar vídeo, legenda ou dados do canal a ele exige decisão do Adrian no Grimório. Aqui publica o navegador (`ferramentas/postar.py`, `random_builds/builds/publicar/*`); ver `publicacao-grade-e-guardas`.
- Cita skills irmãs que **não** foram instaladas (`hook-writer`, `youtube-long-form`, `brand-profile`...). Use `hyperframes-direcao`, `content-engine` e `storytelling-narrative`. Ignore o "leia brand-profile primeiro".
- **Nunca agir em página pública (curtir, comentar, seguir, responder) pela conta pessoal do Adrian.** Nenhuma automação de engajamento, multicontas disfarçadas ou evasão de detecção. A skill também recusa view/inscrito comprado.
- Os números ("~75% viewed", "~70% assistido") vêm sem link e a própria skill pede reverificar a cada trimestre: são hipóteses a testar contra o dado do canal (`metricas-youtube-analytics`, `metricas-medida-da-semana`), não metas.
- As leis do `CLAUDE.md` vencem a skill (janela das postagens, commit por caminho, Claude proibido em trabalho automático).
