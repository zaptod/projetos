---
name: integrador-teste-instavel
description: Use quando os testes de uma entrega do Codex deram vermelho (testes.log do vigia, `delegar testar` ou a suíte que você rodou depois de aplicar) e é preciso decidir se o defeito é da entrega ou do ambiente. Cobre teste de tempo, Tk/Tcl, Chrome do app (patchright), Godot que passa de 300 s, pasta presa do Windows, worktree apagada no meio, C: cheio e crash do Python. Ensina a rodar isolado e no caso-base, para não barrar entrega boa nem aplicar uma ruim.
---

# Falha da entrega ou teste instável?

**Quando usar:** existe um `FAILED`, um `error` ou um código de saída diferente de 0, e você precisa do veredito
antes de aplicar ou de commitar. Para aplicar e commitar, use a skill `integrador-aplicar-entrega`.

## Procedimento (PowerShell, em `E:\projetos`)
1. **Prepare o ambiente, uma vez por sessão:**
   `$env:TEMP='E:\tmp_pytest'; $env:TMP='E:\tmp_pytest'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'`
2. **Leia o log.**
   - `Select-String -Path "$env:LOCALAPPDATA\neural-fights\delegados\<id>\testes.log" -Pattern '^FAILED|^E  |passed|failed|estourou|cannot get C stack'`
   - A 1ª linha diz o comando, a 2ª o `cwd`, o `TEMP` e o `diff`.
   - O log é REESCRITO a cada `testar`: copie antes de rodar de novo.
3. **Classifique pela assinatura** com a tabela de [referencia.md](referencia.md#assinaturas).
   Sem assinatura conhecida, a suspeita padrão é a entrega.
4. **Caso-base:** rode o mesmo nodeid no HEAD, SEM a entrega, antes de aplicar:
   `python -X utf8 -m pytest "<arquivo>::<teste>" -q --basetemp=E:\tmp_pytest\base-<id>`
   Se falha igual sem a entrega, a falha NÃO é da entrega.
5. **Isolado e repetido**, com a entrega na árvore, três vezes:
   `1..3 | % { python -X utf8 -m pytest "<nodeid>" -q --basetemp=E:\tmp_pytest\iso-<id>-$_ }`
   Passou 3 de 3 isolado e só falha dentro da suíte: é carga ou ordem (instável). Falhou 3 de 3: é defeito.
6. **Confira de onde vem o código** quando a parte é builds ou histórias. Na raiz de uma worktree, `builds` e `contos`
   vêm da instalação editável do E:\projetos, não da entrega:
   `python -c "import builds, contos; print(builds.__file__, contos.__file__)"` no MESMO `cwd` do teste.
7. **Decida e aja:**
   - **Defeito da entrega:** conserte o CÓDIGO com Edit, nunca o teste. Ou devolva com
     `python -m remoto.delegar corrigir --id <id> --texto <arquivo.md>`; o texto vai num arquivo, com a cauda do log.
   - **Instável de tempo ou de carga:** dê folga no teste (prazo, espera, tolerância) com Edit e diga isso no commit.
     Não barre a entrega.
   - **Ambiente:** registre a assinatura e o comando isolado verde no relato, e siga com a entrega.
8. **Feche com a suíte da parte verde** e anote o número ("N passed"). Os comandos das suítes estão na referência da outra skill.

## Armadilhas que já custaram caro
- 02/10: a Arena ficou 2 h parada por um teste de TEMPO sem relação; o Ateliê, 4 h, por Tk no ambiente do Codex.
- O vigia reteste sozinho só `WinError 5/145/183` e Tcl sem biblioteca. Timeout do patchright, Godot, crash e
  worktree sumida vão direto para a correção ou para o `olho`, e é aí que você entra.
- O comando padrão do vigia é `python -m pytest random_builds ...` na RAIZ da worktree. Isso testa o `builds` de produção
  (medido em 20/10), e o verde ou o vermelho pode não ser da entrega.
- Testes do palco chamam o Godot (`E:\ferramentas\godot\...`). Rodados de uma worktree, foram com `--path E:\projetos\palco`,
  que é o palco de PRODUÇÃO, porque o `builds` vinha de lá. Em 08/10 morreram em "o Godot passou de 300 s".
- O Codex não roda Chrome nem Godot. "Testes verdes" dele em tela ou em GDScript não provam nada; rode `NF_TESTE_NAVEGADOR=1`.
- O C: vive cheio: sem `TEMP` no E:, o `conftest.py` da raiz põe o runtime em `%TEMP%\neural-fights-pytest`, no C:.
- O pulso de 4 s do painel redesenhava no meio do teste em máquina lenta (4d2c259). Teste do painel que falha só
  com a máquina carregada é carga, não defeito.
- `ruff check --fix` apaga re-export (`nf_bridge/loader.py`, `brain.py`); use `# noqa: F401`.

## Checklist de prova antes de entregar
- [ ] A linha exata do `testes.log` (ou do seu run) que deu a assinatura está citada no relato.
- [ ] O caso-base sem a entrega foi rodado, com o resultado ("falha igual" / "passa").
- [ ] O isolado foi rodado 3 vezes, com o placar (ex.: 3/3 verde).
- [ ] Para builds/histórias: o `__file__` impresso aponta para a árvore que você queria testar.
- [ ] O veredito está escrito (entrega / instável com folga commitada / ambiente) e a suíte da parte terminou verde, com o número.

## Referências
- [referencia.md](referencia.md): tabela de assinaturas, códigos de saída e o que o vigia e os conftests já engolem.
- Código: `remoto/delegar.py` (`_testar_travado`), `coordenador/vigia_trabalho.py` (`INFRA`, `falha_de_infra`, `comando_de_teste`),
  `painel/conftest.py` (`TK_SEM_BIBLIOTECA`), `conftest.py` da raiz, `testar.py`.
- Sessão: [../../../docs/sessoes/coordenador.md](../../../docs/sessoes/coordenador.md). Agente: [../../agents/integrador.md](../../agents/integrador.md).
