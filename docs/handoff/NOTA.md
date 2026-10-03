Chat de 01–02/10/2026 (orquestrador), encerrado por desempenho ruim em sessão longa.

## Em andamento — terminar PRIMEIRO
1. **Ateliê (importar os próprios sprites) — aplicado na árvore, SEM COMMIT.**
   - A entrega do Codex `atelie2` foi aplicada à mão (o vigia barrou por um teste de Tk instável, `painel/test_guia.py`, "tcl_findLibrary", que não tem a ver com ela).
   - Conflitos resolvidos: o Ateliê virou ABA dentro do objeto ⚔️ Arena (`arena: [["arena",...],["atelie",...]]` em `remoto/app/app.js`), casca **v35**.
   - `painel/sprites/importar.py` agora usa `painel/sprites/fundo_auto.py` (o removedor novo), e os testes `painel/sprites/test_importar.py` e `painel/test_fundo_auto.py` passam (8).
   - FALTA, nesta ordem:
     - `python -m pytest remoto painel -q` (TEMP=E:\tmp_pytest, PYTEST_ADDOPTS=-p no:cacheprovider);
     - `NF_TESTE_NAVEGADOR=1 python -m pytest remoto/test_app_tela.py -q`;
     - captura da aba Ateliê no Chrome 390x844 (base: `scratchpad/prova_sprites.py`) e uma importação REAL de ponta a ponta com uma imagem de fundo xadrez e outra de fundo branco;
     - commit por caminho (NÃO incluir `random_builds/config/editing.json`, só fim de linha, nem os `palco/biblioteca/...` do Adrian);
     - `python -m coordenador reiniciar app` fora das janelas de postagem;
     - `python -m remoto.delegar limpar --id atelie2` e `--id arena-app` (as duas já aplicadas à mão; a arena-app ainda aparece como "olho").
2. **Mesa:** o item `09f68d88` (Chrome + arma dupla) já foi aplicado. Rode `python -m remoto.orquestrador agente-fim 09f68d88`.

## Pedidos do Adrian ainda abertos
- **Histórias:** "quero melhorar o fluxo das histórias, mas para isso preciso de uma visualização melhor de todo o macro do processo". Fazer uma página/visão do fluxo inteiro (roteiro → LLM → revisão → imagens → narração → render → vistoria → estoque → publicação), com contagens reais por etapa e onde trava. Use o agente `historias` + o `conferente`. Antes de construir, mostre a ele.
- **Launcher:** 3 passadas aplicadas (b107470). Ainda conferir na tela os ícones do menu, os botões da Arena e a prévia do lutador (`scratchpad/foto_launcher.py`).

## Decisões e regras novas de hoje (memórias salvas)
- A esteira de sprites está DESLIGADA inteira (`ESTEIRA_LIGADA=False`): o Adrian faz os sprites dele pelo Ateliê. Não religar sem ordem.
- O juiz é o ChatGPT; o Gemini não julga (recusa ou trava).
- Uma entrega do Codex nunca é recusada por "fora da lista"/binário/tamanho; só o que é protegido sai do diff (`remoto/delegar.py`).
- Nada vai ao Adrian sem conferência na TELA (é o papel do `conferente`). Hoje passaram: a imagem quebrada pela CSP, sete sprites com fundo grudado, o botão do Godot sem semente e a Arena que não renderizava.

## Armadilhas desta máquina
- Heredoc com `\n` ou `\\` dentro de Python gera arquivo quebrado: use Write/Edit.
- `ruff --fix` apaga importação de fixture do pytest (use `# noqa: F401`).
- `git commit` sem caminho leva o que estiver no índice (hoje levou a Arena junto). Sempre commite por caminho.
- O vigia do coordenador marca "olho" e para: confira `trabalho.olho` no retrato abaixo.
- Teste de tempo fica instável com a máquina carregada (`remoto/test_sincronia.py`, `remoto/test_delegar.py::test_parar_pelo_pedido`): rode de novo antes de concluir que quebrou.
