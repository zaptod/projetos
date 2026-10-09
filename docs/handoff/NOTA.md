Chat de 08/10 00:28 → 22:55 (orquestrador). Renovado por ser longo (~22 h). Entregou: Ateliê novo inteiro (E1–E6, celular), launcher compatível (L1+L2, sem pygame), Vila no Ateliê (habitantes, cenário animado, atualização automática PC e celular), varredura de consumo (toda peça sabe onde aparece; Godot usa skill/efeito/elemento/estado/buff), limpeza de fundo (magenta/verde/liso com grade), YouTube alcança o TikTok, reforma b5 + cargo `executor` para o Codex.

## Em andamento — terminar PRIMEIRO
1. **Teste que trava o vigia:** `painel/test_painel.py` (`_fechar` → `processos.aguardar` → `visao/panorama` lendo métricas reais via `random_builds/builds/publicar/metricas.py:carregar_salvas`) estoura o tempo; o vigia reabre tarefas "falhou" por causa dele (aconteceu 3x hoje). Consertar: dublê das métricas nesse teste. Pedido Codex simples (`python -m coordenador pedir --ia codex ...`).
2. **6 peças da Vila sem consumidor** (avisadas no Ateliê com o motivo): `arvore_vento`, `fumaca` (não existem na Vila) e `objetos/agora|decidir|mandar|ver` (são os ícones da barra do app — dá para ligar no `remoto/app`). Registro: `neural_fights/tools/consumo_atelie.py`; prova: `tests/test_consumo_atelie.py`.
3. **Delegado do apurador terminado e não aplicado:** `pedido-a55bf491` "Investigar erro do apurador" (h00065: Chrome caiu 3x, imagem sem prova não registrada; não alterou código) → só limpar: `python -m remoto.delegar limpar --id pedido-a55bf491`.
4. **Mesa com ~12 pedidos velhos em "esperando_voce"** (aparecem no retrato): fechar os resolvidos/obsoletos — `pedido-5f521cb9`/`pedido-2938beb7` (YouTube alcança: feito 824a788), `pedido-dbc9a016`/`pedido-275c2a1b`/`pedido-c9800372` (Ateliê antigo/corrente desenhada: obsoletos), `pedido-00cae350` (palco nos duelos: segurado de propósito, ver decisões), `pedido-61fa5b2f`/`pedido-b288c8fe`/`pedido-7f7780d0` (conferir e fechar). **REAL:** `pedido-af69943d` — a API do YouTube do canal de histórias recusa com 401; o Adrian precisa reautorizar a conta, depois `postar.py --so-youtube historia_00016:p01` (antes `--ver`), fora da janela.
5. **Ressalvas pequenas (não bloqueiam):** prévia montada põe a arma um pouco afastada do corpo; `Ver no Godot` de peças sem lutador no banco troca a arma/classe só na prévia (`previa_animacao._troca_para_peca`); modo escuro do Ateliê ok, mas o "Ver na Vila" é GIF (sem transparência).

## Pedidos do Adrian ainda abertos
- Nenhum pedido explícito pendente. Último: "a árvore tinha uma animação, subiu só a imagem" → resolvido (cenário animado, conferido PC e celular).
- Ele está desenhando no Ateliê agora (Bot: andar+trabalhar; Arena: andar; árvore; cristais). Quando ele disser "não funcionou", conferir PRIMEIRO o `outputs/app_celular.txt` (o que o celular pediu) e testar NO CAMINHO REAL: Chrome com UA Android + toque (`scratchpad` deste chat tinha `celular_atelie.py`/`celular_vila.py`; recriar se sumirem) e a janela da Vila no PC por PrintWindow.

## Decisões e regras novas deste chat
- Grimório `builds/launcher-iniciar-batalha` = **tirar o pygame do launcher** (feito: Arena só Godot).
- Plano do Ateliê novo aprovado (`~/.claude/plans/entendi-enquanto-isso-quero-dreamy-sky.md`): uma animação por folha, sem variantes, 3 prévias, catálogo editável. Ateliê antigo (Montar/Recortador/Provador/variantes) REMOVIDO.
- Godot sem visual próprio (marcador neutro); física da corrente saiu junto com o desenho — volta como regra quando houver arte de corrente.
- Palco nos duelos publicados continua DESLIGADO (`producao.duelo_celular=desligado`): ligar publicaria bolinhas cinza até ter arte.
- Pedido do chat ao Codex nasce com cargo `executor` (`.claude/agents/executor.md`); integrador do vigia é sempre Codex.
- Desenhos do Ateliê vão para o git (`palco/biblioteca/animacoes/**`) — commitados a0837b5; os novos dele precisam de commit periódico.
- Memórias novas: `codex-cego-para-tela-e-godot`, `limpar-entrega-dispara-integrador`.

## Armadilhas encontradas
- **O Codex não roda Chrome nem Godot no sandbox** e entrega "pronto" com JS que não compila, GDScript que não compila, rotas 404 e folhas em resolução cheia. SEMPRE: `node --check`, compilar o Godot (`--headless --path palco --import`), rodar o fluxo como celular e o render, e medir (contar cores de folha de teste nos quadros do vídeo).
- **Testei no lugar errado 3 vezes** (Chrome do PC em vez de celular; Vila do PC em vez da do app; folha de teste minha em vez da dele). O Adrian usa o CELULAR.
- Vila: a vida fala `dir`/`esq`, o Ateliê grava `direita`/`esquerda`; o atlas do celular só levava o quadro 0; o cenário é pintado no fundo uma vez.
- Pillow 12: `ImageDraw.floodfill` em imagem vinda de `Image.fromarray` não pinta (somente-leitura) — usar `.copy()`.
- `capture="environment"` no input de arquivo abre a CÂMERA no Android.
- Testes em worktree importam `random_builds`/`neural_fights` de `E:\projetos` (instalação editável): rodar a suíte na árvore principal depois de aplicar.
- Mesa reabre tarefa "pronta" sozinha (resume) quando o vigia acha falha de ambiente → `delegar parar` + fechar o pedido; `delegar limpar` com deadlock → repetir na hora (senão o vigia contrata integrador).
- Reiniciei o app às 11:57 dentro da janela (12:07) — conferir `grade.minuto` antes de qualquer reinício.
- Cota: Claude semanal estava em 77% às ~10h.
