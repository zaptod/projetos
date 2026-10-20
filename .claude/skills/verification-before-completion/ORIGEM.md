# ORIGEM: verification-before-completion

- **Fonte:** https://github.com/obra/superpowers/tree/bb92a77741419a4ab5f06e711a283343f1ada0c3/skills/verification-before-completion (Jesse Vincent; 302 mil estrelas pela API em 20/10/2026; plugin "Superpowers", listado no marketplace oficial `claude-plugins-official`)
- **Commit:** `bb92a77741419a4ab5f06e711a283343f1ada0c3` (10/10/2026)
- **Licença:** MIT (`LICENSE` da raiz, copiado junto)
- **Baixado e lido em:** 20/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\obra_superpowers\`
- **Copiado:** `SKILL.md`, sem alteração. Só a skill, não o plugin (sem hook).

## O que li (tudo)
Um arquivo de texto. Regra: nada de dizer "pronto", "passou" ou "consertado" sem ter rodado AGORA o comando que prova e lido a saída inteira (código de saída, número de falhas). Relatório de agente não é prova: conferir o diff. Teste de regressão só vale com o ciclo vermelho-verde (tirar o conserto, ver falhar, devolver, ver passar).

## Cuidados neste repositório
- É a lei do `conferente` escrita como skill: "NADA vai ao Adrian sem ele" e "Teste verde ANTES do commit".
- Vale também para a entrega do Codex: "Codex cego para tela e Godot" (memória), o orquestrador prova rodando.
- Combina com "Relatório verde que mente" (testar o caso ZERO).

## Para que serve, e a quem
- **conferente** e **integrador** em primeiro lugar; todas as partes antes de dizer que terminou.
