# Decisões — Builds

Gerado por `remoto/decisoes.py` a cada resposta. Não edite à mão:
a fonte são os `<id>.json` desta pasta.

Legenda: ✅ decidida · ⏳ pendente · 🔒 bloqueada · ↺ a rever

- ✅ **Variantes B** — Título próprio para cada uma (27/09/2026) `variantes-b`
- ✅ **Roleta automática de madrugada** — Sim (28/09/2026) `roleta-de-madrugada`
- ✅ **Estreia generation_00066 (muda)** — Descartar (28/09/2026) `estreia-00066`
- ✅ **Onda 16: ferramenta do visual** — Godot 4 (28/09/2026) `ferramenta-do-visual`
  - ✅ **Visual do lutador** — Bolinha com arte (28/09/2026) `visual-do-lutador`
  - ✅ **Origem da arte** — CC0 + IA, trocável (28/09/2026) `origem-da-arte`
    - ⏳ **Sprites animados: como produzir** — A IA não entrega sprite sheet fatiável. O teste do fireball saiu em 1024×576, fundo branco sem alfa, grade e rótulos desenhados e 14 colunas em vez de 6. Nano Banana 2 e GPT Image exigem crédito ou plano nesta conta compartilhada. Como produzir as animações? `sprites-animados`
  - ⏳ **Palco: o visual novo (A/B)** — Seguir com o palco (Godot) como o visual novo das lutas? `palco-seguir`
    - 🔒 **Chão da arena** — Qual chão fica na arena? · espera Palco: o visual novo (A/B) = Seguir: próxima etapa é a arte (16E) `chao-da-arena`
    - 🔒 **Hitstop: a pausinha no impacto** — Ligar a pausa curta no momento do golpe? Deixa o vídeo um pouco mais longo. · espera Palco: o visual novo (A/B) = Seguir: próxima etapa é a arte (16E) `hitstop`
- ✅ **Transição até o palco** — O visual atual segue, já com o som real (28/09/2026) `transicao`
  - ⏳ **Som real da luta (16A)** — O som real (DEPOIS) substitui o sintetizado (ANTES)? `som-real-16a`
    - 🔒 **generation_00077: luta muda, lutadores fora do banco** — O que fazer com a generation_00077? · espera Som real da luta (16A) = decidida `generation-00077`
