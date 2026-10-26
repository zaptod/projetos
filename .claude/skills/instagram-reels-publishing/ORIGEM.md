# ORIGEM: instagram-reels-publishing

- **Fonte:** https://github.com/social-media-skills/skills/tree/f28cef2b7067ec64e79c9d85421c022c06659e03/skills/instagram-reels-publishing (comunitário, Frank Heijdenrijk; 200 estrelas, MIT, último push 15/10/2026, pela API em 26/10/2026)
- **Commit:** `f28cef2b7067ec64e79c9d85421c022c06659e03` (26/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 26/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\redes\social-media-skills_skills\`
- **Lido por:** subagente de pesquisa (Claude), `SKILL.md` e as 4 `references/*.md` inteiros. Busca por URL, `curl`, `npx`, `pip`, `npm`, `fetch`, chave de API, telemetria, scraping, proxy, bot e evasão: o único endereço é o do WoopSocial, só citado. Nenhum script executado (`evals/evals.json` não copiado).
- **Copiado:** `SKILL.md` + `references/*.md`, sem alteração, **exceto** um parágrafo "AVISO DA CASA" inserido logo depois do frontmatter do `SKILL.md`.
- **Classificação:** APROVADA COM CAUTELA (só o texto entra; a parte de publicar pelo WoopSocial é ignorada).
- **Decisão:** pedido do Adrian em 26/10/2026 ("skills de análise e postagem de cada rede"; Instagram Reels específico).

## Para que serve, e a quem
Mecânica de postar um Reel: 1080x1920 (9:16), MP4/MOV H.264, 30/60 fps, ~15-20 Mbps, zona segura (topo ~250 px e rodapé ~350 px são interface; recorte 4:5 do feed e 3:4 da grade do perfil), capa personalizada escolhida ANTES de publicar (não se troca depois), áudio, legenda queimada, como evitar vídeo borrado. Serve à POSTAGEM dos duelos no Instagram web (navegador).

## Cuidados neste repositório
- Comparar a zona segura do Reel com a que o `conferente-video-mp4` já pinta (topo 10%, baixo 20%, direita 12%): a do Instagram é maior embaixo e tem o recorte 3:4 da grade. Vale pintar a do Instagram na conferência.
- A capa não se edita depois: o fluxo de `publicar/*` do Instagram deve escolher a capa no envio (como já se faz na série Blue Lock).
- Som em alta, "compartilhar no Feed", marcações e Insights são do app/navegador: coerente com a postagem pela web.
- Remover marca d'água de outra rede (TikTok) antes de subir: usar o arquivo limpo do catálogo.
- **WoopSocial (e `scheduling-and-queue`) é serviço pago de terceiros: NÃO usar.** `postType REEL`, `cover` e `content.text` são campos dele. Publicar é `ferramentas/postar.py` e `publicar/*`.
- Cita skills irmãs **não** instaladas (`reels-script`, `captions-and-clipping`, `platform-specs-and-validation`, `ideogram`, `nano-banana`...). Ignore.
- **Nunca agir em página pública pela conta pessoal do Adrian.** Nenhuma automação de engajamento, multicontas disfarçadas ou evasão.
- As especificações vêm sem link para a documentação da Meta e a skill pede reverificar a cada trimestre: confira no app antes de mudar o render.
- As leis do `CLAUDE.md` vencem a skill (janela das postagens, commit por caminho).
