# ORIGEM: video-editing

- **Fonte:** https://github.com/affaan-m/ECC/tree/90606c8315ee09cafc303515c5f33024db6b9882/skills/video-editing (comunitário, Affaan Mustafa; 287 mil estrelas e licença MIT pela API em 24/10/2026)
- **Commit:** `90606c8315ee09cafc303515c5f33024db6b9882`
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado em:** 24/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\ecc\`
- **Lido por:** orquestrador, `SKILL.md` inteiro.
- **Copiado:** só o `SKILL.md`. **Não copiei `assets/fusion/`**: são presets do DaVinci Fusion com instaladores Lua (`install_ito_*.lua`) que não foram lidos e que a série não usa.
- **Decisão:** Grimório `blue-lock/serie-videos-ferramentas`.

## Para que serve
O fluxo de edição de material real: captura → estrutura → cortes no ffmpeg → composição programável → acabamento. Também cobre reenquadramento 9:16 e corte por cena e por silêncio.

## Cuidados neste repositório
- A camada 5 manda gerar voz no ElevenLabs e música no fal.ai, o que pede chave de API paga e envia material para fora. **Não usar sem decisão própria no Grimório.** A voz da série é a do Adrian, e a trilha precisa de licença verificável.
- A camada 4 cita o Remotion. Aqui, a composição programável é o HyperFrames (`hyperframes-core`).
- "Edit, don't generate" combina com a regra da série: só captura real daquele commit.
