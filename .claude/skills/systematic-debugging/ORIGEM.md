# ORIGEM: systematic-debugging

- **Fonte:** https://github.com/obra/superpowers/tree/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/systematic-debugging (Jesse Vincent; 302 mil estrelas pela API em 20/10/2026; o "Superpowers" está no marketplace oficial `claude-plugins-official` da Anthropic como plugin de terceiro)
- **Commit:** `bb92a77741419a4ab5f06e711a283343f1ada0c3` (10/10/2026; é o mesmo commit que o marketplace oficial fixa)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado e lido em:** 20/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\obra_superpowers\`
- **Copiado:** `SKILL.md`, `root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md`, sem alteração. **Só a skill, não o plugin** (o plugin instala um hook de início de sessão; não trouxemos).

## O que li (tudo, inclusive o que ficou de fora)
- `SKILL.md`: quatro fases (causa raiz → padrão → hipótese única → conserto com teste que falha antes). Depois de 3 consertos que não pegaram, parar e questionar a arquitetura.
- `root-cause-tracing.md`: rastrear o valor ruim para trás até a origem; consertar na origem.
- `defense-in-depth.md`: validar em cada camada por onde o dado passa.
- `condition-based-waiting.md`: esperar a condição em vez de `sleep` chutado.
- **Não copiados** (lidos): `find-polluter.sh` (bissecção com `npm test`; só local, mas não serve para pytest), `condition-based-waiting-example.ts` (código de outro projeto, "Lace"), `CREATION-LOG.md` e `test-*.md` (testes de pressão da própria skill). Nenhum deles manda dado para fora nem baixa nada.

## Cuidados neste repositório
- A skill cita `superpowers:test-driven-development` e `superpowers:verification-before-completion`. Aqui a segunda existe como `verification-before-completion`; a de TDD **não** foi trazida (ver `docs/pesquisa/skills-por-setor.md`).
- "Discuta com seu parceiro humano" = registrar no Grimório e seguir a recomendada (memória "Adrian não quer decidir").
- Combina com as memórias "Checar quando trava" (log parado = olhar a tela na hora) e "Ler a tela, não o DOM".

## Para que serve, e a quem
- **integrador**: separar falha real de teste instável antes de mexer.
- Todas as partes quando algo quebra (publicação que não saiu, render travado, rodada da madrugada parada).
