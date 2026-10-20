# ORIGEM: hyperframes-keyframes

- **Fonte:** https://github.com/heygen-com/hyperframes/tree/26a5ab775b77fde3c2f08839ba34c93f86e7b9da/skills/hyperframes-keyframes (oficial da HeyGen; 67,8 mil estrelas pela API em 20/10/2026)
- **Commit:** `26a5ab775b77fde3c2f08839ba34c93f86e7b9da` (20/10/2026), plugin versão **0.8.181**
- **Licença:** Apache-2.0 (`LICENSE` da raiz do repositório, copiado junto)
- **Baixado em:** 20/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\heygen-com_hyperframes\`
- **Lido por:** agente auditor só leitura (os 3 arquivos inteiros) e conferência minha dos pontos de rede.
- **Copiado:** `SKILL.md` e `references/keyframe-patterns.md`, sem alteração. **Fora:**
  `agents/openai.yaml` (só metadado de tela do Codex: nome e prompt padrão; inofensivo, inútil aqui).

## O que ensina
Keyframes que aguentam busca de quadro (o render pula para qualquer instante): punch-in, zoom,
máscara e `clip-path`, texto, SVG, 3D, em GSAP, CSS, Anime.js e WAAPI; quais propriedades são
seguras de animar e como provar com `hyperframes keyframes --shot` e `snapshot`.
`references/keyframe-patterns.md` só tem links de documentação (gsap.com, animejs.com, MDN, three.js).

## Cuidados OBRIGATÓRIOS neste repositório
Os mesmos da `hyperframes-core` (ver o `ORIGEM.md` dela): só na prova de 6 h, versão fixa
`hyperframes@0.8.181`, variáveis `HYPERFRAMES_NO_TELEMETRY=1`, `HYPERFRAMES_SKIP_SKILLS=1` e
`HYPERFRAMES_NO_UPDATE_CHECK=1` em toda chamada, nada de `feedback`/`cloud`/`publish`, GSAP local.
Os comandos que esta skill cita (`check`, `keyframes`, `snapshot`) são locais.

## Para que serve, e a quem
- **builds**: dreno da barra de dano fantasma, "mola" do carimbo K.O., flash no veredito,
  máscara da legenda.
