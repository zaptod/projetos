# ORIGEM: godot-gdscript-patterns

- **Fonte:** https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/game-development/skills/godot-gdscript-patterns (Seth Hobson; repositório comunitário grande, 41,2 mil estrelas pela API em 20/10/2026, ~12,8 mil instalações desta skill segundo skills.sh; não é oficial da Godot)
- **Commit:** `0874a27b17a22e2b7c2e2bcd725768e0803cad06` (17/10/2026)
- **Licença:** MIT (`LICENSE` da raiz do repositório, copiado junto)
- **Baixado e lido em:** 20/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\wshobson_agents\`
- **Copiado:** `SKILL.md`, `references/details.md`, `references/advanced-patterns.md`, sem alteração.

## O que li (tudo)
Só texto e GDScript de exemplo, sem script executável. Padrões do Godot 4: tipagem estática, `@export`/`@onready`, sinais para desacoplar, máquina de estados por nós, Autoloads (com moderação), Resources como dados, pool de objetos, componentes de vida/hitbox/hurtbox, troca de cena com carregamento em thread, sistema de save, dicas de desempenho (guardar referência de nó, não alocar no `_process`, desligar processamento fora da tela).

## Cuidados neste repositório
- **"Godot só regras; arte é do Adrian"** (memória): o palco Godot desenha o que o Python simulou. Os exemplos de entrada de teclado e de jogabilidade não se aplicam; o que serve é sinais, Resources, pool (partículas e projéteis do palco), tipagem e desempenho.
- O exemplo de save usa chave fixa no código (`ENCRYPTION_KEY`); não copie isso.
- Pequeno defeito do original: `details.md` aponta para `./advanced-patterns.md` (os dois arquivos estão na mesma pasta `references/`, então o link funciona).
- Não mexa nos arquivos do Adrian (`palco/biblioteca/LICENCAS.md`, `.../projetil/fogo.tscn`, `.../efeitos/folhas/**`).

## Para que serve, e a quem
- **builds**: o palco Godot (`palco/`) que renderiza o duelo; GDScript mais limpo e mais rápido no i5/i3 sem GPU boa.
