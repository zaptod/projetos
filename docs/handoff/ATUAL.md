# Passagem de bastão — 02/10/2026 22:58 (estrutura nova)

Leia ANTES de agir. A NOTA é do chat anterior; o RETRATO é medido agora do disco.
Regras de operação: `CLAUDE.md`. Equipe: `docs/agentes/EQUIPE.md`.

# NOTA do chat anterior

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

# RETRATO (medido agora)

## Git
- ramo: `refactor/arquitetura`
- **mudanças NÃO commitadas (19)** — confira antes de qualquer coisa:
  - `M  docs/sessoes/app-e-bot.md`
  - `M  docs/sessoes/painel-e-vila.md`
  - `M painel/sprites/fundo_auto.py`
  - `AM painel/sprites/importar.py`
  - `A  painel/sprites/test_importar.py`
  - `M palco/biblioteca/LICENCAS.md`
  - `M palco/biblioteca/efeitos/objetos/projetil/fogo.tscn`
  - `A  palco/biblioteca/sprites_usuario/catalogo.json`
  - `M random_builds/config/editing.json`
  - `M  remoto/api_http.py`
  - `M  remoto/app/app.css`
  - `M  remoto/app/app.js`
  - `A  remoto/app/atelie.js`
  - `M  remoto/app/index.html`
  - `M  remoto/app/sw.js`
  - `M  remoto/test_api_http.py`
  - `M  remoto/test_app_quatro_objetos.py`
  - `M  remoto/test_app_tela.py`
  - `M  remoto/test_app_vila_objetos.py`
- últimos commits:
  - ef39910 Vila: metadados dos prédios do ChatGPT e do DeepSeek
  - f4745d1 fundo automático: descobre o fundo (liso, xadrez desenhado — inclusive fechado dentro do desenho —, ou já transparente) e tira sem furar o desenho; portão e aprovar barram fundo grudado; prédios do ChatGPT e DeepSeek da Vila limpos
  - b107470 Launcher 3ª passada: ícones do menu, botões da Arena, prévia do lutador (feito pelo Codex, validado pelo vigia)
  - 187f720 Arena: o render recebe o arquivo da timeline (com o dict nenhuma luta virava vídeo); mapa legível no seletor (casca v34)
  - 69119ed teste da Arena: as fixtures voltam (o ruff --fix as tirou como importação sem uso)
  - 8f9b57d Arena no app (⚔️: escolhe P1/P2/mapa/semente, renderiza no palco Godot e toca no celular, revanche; feito pelo Codex, conferido) + esteira de sprites DESLIGADA inteira (o Adrian mandou parar de gerar sprites)
  - befd723 teste: sem_ouvinte com folga de tempo (com a máquina carregada o comando de 119 s passava de 120 s e barrou a Arena)
  - a4d4c36 esteira: as folhas animadas não são mais pedidas à IA (o Adrian faz as dele pelo Ateliê); 13 em andamento descartadas; peças paradas continuam
  - 5351ecc launcher: 'Ver no palco' abria nada (exportava sem semente e quebrava em int(None)); a prévia do Godot abre em 9:16 na altura da tela em vez de 286x519
  - d17d6f1 Alterações propostas (feito pelo Codex, validado pelo vigia)
  - a297c4f esteira: o juiz passa a ser sempre o ChatGPT — o Gemini recusava ('sou uma IA com base em texto') ou travava; julgamento espera o ChatGPT em vez de ir ao Gemini
  - c206907 Corrigi os pontos medidos nas 14 capturas existentes. (feito pelo Codex, validado pelo vigia)

## Entregas do Codex (delegados)
- `atelie2`: terminou (Ateliê no app: importar os próprios sprites, limpar e cortar, passo a passo) — **PRECISA DE OLHO**: os testes falharam de novo depois da correção: 1 failed, 1116 passed, 3 warnings in 739.01s (0:12:19)

## Mesa, fila e Grimório
- agentes ativos na Mesa: ninguém trabalhando
- fila (3):
  - 1. b0d22ef8  [builds] Som real nas 15 builds de estoque ainda com som sintetizado (variantes B 00026–00041, A 00026–00029, 00085) — ~12 min cada, recusa as que 
  - 2. 5bc42650  [geral] Mover perfis de navegador do C: para o E: (decisão perfis-para-o-e): uma vez, todos os navegadores fechados, fora de :25–:55 e fora do lote
  - 3. 6a229e63  [builds] Corrente F4–F6: arte pela esteira, som e A/B (o rework que o Adrian pediu em palco-duelo-ab)
- Grimório: todas as respostas lidas

## Serviços e máquina
- coordenador: pid 3880, código ef39910
  - app: rodando
  - bot: rodando
  - carteiro: rodando
  - vila: rodando
- Claude: Claude liberado desde 01/10 13:30 pelo app (Android)
