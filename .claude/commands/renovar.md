---
description: Fecha este chat com a passagem de bastão (NOTA + retrato) para um chat novo continuar
---

Este chat vai ser renovado. Faça, nesta ordem:

1. **Feche o que der em 2 minutos:** commit por caminho do que já está testado. NÃO commite o que não passou nos testes; isso vai para a NOTA.
2. **Reescreva `docs/handoff/NOTA.md`** (com a ferramenta Write), curto e concreto. Apague o que já foi resolvido da nota anterior e leve só o que continua valendo.
   - **Em andamento — terminar PRIMEIRO:** cada item com o estado exato, os arquivos, o que já foi feito e o que FALTA, com os comandos.
   - **Pedidos do Adrian ainda abertos:** com as palavras dele.
   - **Decisões e regras novas deste chat:** e se viraram memória.
   - **Armadilhas encontradas:** o que quebrou e como evitar.
3. Rode `python -X utf8 ferramentas/handoff.py gerar --motivo renovacao` e leia o `docs/handoff/ATUAL.md` gerado. Se o RETRATO mostrar algo que a NOTA não cobre (entrega parada, mudança sem commit), acrescente na NOTA e gere de novo.
4. Commit por caminho: `git add docs/handoff/NOTA.md docs/handoff/ATUAL.md && git commit -m "handoff: ..."`.
5. Diga ao Adrian, em 3 linhas: o que ficou pronto, o que ficou para o próximo chat e "abra um chat novo e digite /assumir".
