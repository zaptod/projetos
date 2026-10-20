---
name: integrador-aplicar-entrega
description: Use quando uma entrega do Codex ficou parada (no `olho` do vigia, "terminou" sem `aplicado`, conflito de merge, "aplicado sem commit") e você vai aplicá-la à mão na árvore E:\projetos. Diz como achar a ficha, a worktree e o diff.patch reais, conferir o momento seguro (janela post-12..post+18, publicação em voo, rodada viva), aplicar pelo `delegar aplicar` ou por `git apply -3`, commitar por caminho, gravar o commit na ficha e limpar sem o vigia contratar outro integrador.
---

# Aplicar uma entrega parada do Codex

**Quando usar:** a ficha `<id>` terminou e não entrou sozinha. **Não usar** para teste vermelho
sem saber se o defeito é da entrega: antes passe pela skill `integrador-teste-instavel`.
O passo a passo base (diff, `apply -3`, CRLF, ruff, nunca) está no agente `integrador.md`; aqui fica o que ele não diz.

## Procedimento (PowerShell, em `E:\projetos`)
1. **Ache o motivo e os arquivos reais.**
   - `python -m remoto.delegar ver --id <id>`: worktree, diff (sha, passa/RECUSADO), testes e aplicado.
   - Ficha e provas: `$env:LOCALAPPDATA\neural-fights\delegados\<id>\` (`estado.json`, `diff.patch`,
     `testes.log`, `resposta.md`, `tarefa.md`). O `diff.patch` fica lá mesmo se a worktree sumir.
   - Motivo do vigia: `python -m coordenador status --curto` (motivo "o vigia: ...") e as chaves
     `olho`/`esperando`/`integrando` de `$env:LOCALAPPDATA\neural-fights\coordenador\trabalho_memoria.json`.
2. **Não duplique.** Se `integrando` tem `<id>`, existe `integrar-<id>`: rode `python -m remoto.delegar ver --id integrar-<id>`.
   Se ele está `rodando` ou terminou bem, deixe com ele. Se você vai fazer à mão, rode `delegar parar --id integrar-<id>` antes.
   Entrega em `esperando`: quem aplica é o vigia (a cada 60 s); não mexa nela.
3. **Momento seguro** (detalhe em [referencia.md](referencia.md#momento-seguro)):
   ```
   python -c "from datetime import datetime; from coordenador.pedidos import na_janela_das_postagens as j; from remoto.delegar import publicacao_em_voo as v; from builds import rodada_viva as r, grade; print('janela', j(datetime.now()), '| proximo', grade.proximo(), '| publicando', v(), '| rodadas', [(f.get('rotulo'), f.get('pid')) for f in r.fichas() if f.get('pid')])"
   ```
   Só siga com `janela False` e `publicando []`. Rodada viva que importa a parte mexida (builds ou historias): espere ela acabar.
4. **Árvore limpa nos arquivos da entrega:** `git status --porcelain -- <arquivos do diff>` deve sair vazio.
   Se não sair, é mudança de outro: commite ou guarde a mudança dele antes. Nunca aplique por cima.
5. **Caminho A: `python -m remoto.delegar aplicar --id <id> --sem-testes`.**
   Ele faz `apply --check`, depois `apply -3`, e resolve sozinho conflito de casca (`painel-casca-vN`) e de comentário.
   Grava `aplicado` na ficha, o que faz o vigia largar a entrega. Use `--sem-testes` só porque você roda os testes no passo 7.
6. **Caminho B (o A recusou com "conflito de merge em: ..."):**
   `git apply -3 "$env:LOCALAPPDATA\neural-fights\delegados\<id>\diff.patch"`.
   Junte os dois lados de cada `<<<<<<<` (as duas features ficam). Depois `git reset -q -- <arquivos>`.
7. **Testes da parte**, na árvore, antes do commit. As suítes e os comandos estão em [referencia.md](referencia.md#suites).
   Se tocou `remoto/app/**` ou `remoto/api_http.py`, rode também a prova de tela (`NF_TESTE_NAVEGADOR=1`).
8. **Commit por caminho:** `git add -A -- <arquivos>` e depois `git commit -F <msg.txt> -- <arquivos>`.
   A mensagem leva "(feito pelo Codex, integrado)", o que foi medido e a linha Co-Authored-By.
9. **Grave o commit na ficha.** Só assim a Mesa fecha o pedido (COO-2):
   `python -c "from remoto import delegar; delegar.registrar_commit('<id>', '<hash>', aplicado_por='integrador')"`
10. **Limpe e confira:**
    - `python -m remoto.delegar limpar --id <id>` (e o `integrar-<id>`, se ele existir);
    - `python -m remoto.delegar ver --id <id>` deve mostrar `limpo`;
    - se der "Resource deadlock", rode o `limpar` de novo na hora;
    - `python -m remoto.delegar listar | Select-String integrar-` não pode mostrar nenhum integrador novo.
11. **Devolva ao orquestrador** quais serviços reiniciar, conforme a pasta mexida: `remoto/` reinicia app e bot,
    `ias/` e `historias/contos/llm/` reiniciam o carteiro, `painel/` reinicia a Vila, `coordenador/` reinicia o coordenador.
    Mudança na casca do app só vale junto com o `coordenador reiniciar app`.

## Armadilhas que já custaram caro
- 08/10: um `limpar` de entrega NÃO aplicada que morreu no meio deixou 7 `integrar-*` contratados (Claude, cota). Confira o `limpo`.
- No caminho B a ficha fica sem `aplicado`. Se a entrega não está no `olho` e você demora a limpar, o vigia tenta
  aplicar de novo, dá "não mudou nada" e contrata um integrador. Rode `registrar_commit` e `limpar` logo depois do commit.
- 07/10 01:22: uma entrega aplicada com a rodada das histórias viva matou a rodada (`AttributeError ... CORREIO`). Histórias importam builds.
- 01/10 23:42: casca nova do app sem reinício. O Adrian viu "o app caiu".
- `delegar corrigir --texto` recebe CAMINHO de arquivo, não o texto.
- O `diff.patch` é contra a `base` da ficha, não contra o HEAD. Por isso conflito é normal e se resolve com `-3`; não é defeito.
- Entrega do `E:\jogo_ZOMBIE`: o `repo` da ficha manda. Aplique e commite LÁ, não no E:\projetos.

## Checklist de prova antes de entregar
- [ ] O comando do passo 3 deu `janela False` e `publicando []`; nenhuma rodada viva da parte mexida.
- [ ] `git status --porcelain -- <arquivos>` saiu vazio depois do commit.
- [ ] Os testes da parte passaram, com o número anotado (ex.: "312 passed"); a prova de tela, se o app mudou.
- [ ] `git show --stat HEAD` lista só os arquivos da entrega, sem LICENCAS.md, fogo.tscn, folhas/** e sem arquivo que só mudou o fim de linha.
- [ ] `delegar ver --id <id>` mostra `commit` e `limpo`; não nasceu nenhum `integrar-` novo.
- [ ] O relato diz os conflitos que você juntou, os serviços a reiniciar e o que o `conferente` deve abrir.

## Referências
- [referencia.md](referencia.md): os comandos do `delegar` com as flags e os códigos de saída, o que o vigia já faz sozinho,
  a janela das postagens e as suítes de teste.
- Agente: [../../agents/integrador.md](../../agents/integrador.md). Sessão: [../../../docs/sessoes/coordenador.md](../../../docs/sessoes/coordenador.md) (vigia, COO-2/7/11).
- Código: `remoto/delegar.py` (`coletar`, `aplicar`, `limpar`, `registrar_commit`), `coordenador/vigia_trabalho.py` (`_cuidar`, `_olho`).
