# ORIGEM: youtube-analise-referencias

- **Fonte:** https://github.com/AgriciDaniel/claude-youtube/tree/84c3fa6805200632fadb4fe2795ef265511271c7/skills/claude-youtube/references (comunitário, Daniel Agrici; 545 estrelas, MIT, último push 10/04/2026, pela API em 26/10/2026)
- **Commit:** `84c3fa6805200632fadb4fe2795ef265511271c7` (26/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 26/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\redes\AgriciDaniel_claude-youtube\`
- **Lido por:** subagente de pesquisa (Claude), as 3 references copiadas (`analytics-guide`, `shorts-playbook`, `algorithm-guide`) inteiras. Só texto: sem URL de serviço, `curl`, `npx`, chave ou script. NÃO lido nem copiado: o `SKILL.md` original, os `sub-skills/`, `templates/` e `dataforseo-integration.md` (a skill original integra o DataForSEO, serviço pago de terceiros).
- **Copiado:** as 3 references, sem alteração. O `SKILL.md` desta pasta é **escrito pela casa** (a original é um orquestrador de sub-skills e de DataForSEO) e só aponta quais partes ler.
- **Classificação:** APROVADA COM CAUTELA (só o texto entra).
- **Decisão:** pedido do Adrian em 26/10/2026 ("skills de análise e postagem de cada rede"); é o único material achado em que cada benchmark traz a fonte e o ano.

## Para que serve, e a quem
Ler o YouTube Studio e a Analytics API: hierarquia de métricas, funil de impressões e CTR, saúde por origem de tráfego, sinais de satisfação, retenção (AVD), Viewed vs Swiped Away, "engaged views" e a mudança de contagem de views dos Shorts de 31/03/2025. Serve ao agente `metricas` e à revisão semanal (`metricas-medida-da-semana`) para interpretar números que `metricas-youtube-analytics` mediu.

## Cuidados neste repositório
- Várias fontes são relatórios de agências ou ferramentas de marketing (Focus Digital, vidIQ, Retention Rabbit): indício, não meta. Confrontar com a mediana do próprio canal.
- Seções de CPM/RPM, receita por nicho e música em Shorts: **ignorar** (o canal não monetiza; números de 2025, EUA).
- "Responder 50+ comentários em 2 h" é tática MANUAL na conta do canal; automatizar resposta/curtida está proibido, e nunca pela conta pessoal do Adrian.
- Cita MrBeast e estudos de terceiros sem link direto; não repetir ao Adrian como fato.
- Nenhuma chamada de API sai desta skill: as chamadas reais continuam só nos scripts de `metricas-youtube-analytics`.
- As leis do `CLAUDE.md` vencem a skill.
