# Vila — o mundinho dos bots, em sprites

> Parte do monorepo `e:/projetos`. O mapa de todos os projetos, quem depende de quem e como instalar está no [README da raiz](../README.md).


A página **🏭 Vila** do painel mostra a fábrica de conteúdo como um jogo:
cada etapa das pipelines (ChatGPT, Gemini, PicassoIA, Digen, estúdio, arena,
publicação) é um prédio, e um bot mora na casa central e **anda até o prédio
quando aquela etapa está trabalhando de verdade** — o dado vem do diário
`atividade.jsonl`, que todas as etapas alimentam. Erro = ❗ em cima do prédio
e linha no diário.

Esta pasta é o que faz a Vila ser *bonita*: um motor de **folhas de sprites**
no estilo Stardew Valley, com uma ferramenta para atribuir tudo sem tocar em
código.

## As três peças

| peça | o que é |
| --- | --- |
| **folha** | um PNG com grade uniforme de células (`tile_w`×`tile_h`, margem/espaço opcionais). `chave: "auto"` torna a cor do canto transparente — essencial para arte gerada por IA, que nunca vem com fundo transparente. |
| **papel** | um nome com significado (`predio.picasso`, `chao.grama`, `bot.baixo`) apontando para frames de uma folha. É o contrato: o painel pede papéis, nunca índices. |
| **mapa** | grade de chão (paleta de papéis `chao.*`), decorações, posição de cada prédio e da casa. |

Tudo vive em `config.json` + `sprites/`. O painel compõe o mundo estático em
**uma imagem só** (por isso o mapa pode ser grande) e anima por cima apenas
bots e efeitos.

## Papéis que ganham vida no painel

- `predio.<fabrica>` e `predio.casa` — posicionáveis, clicáveis (filtra o diário), recebem ❗/legenda de estado.
- `chao.*` — pintáveis; `variar` escolhe o frame pela posição (grama viva, não azulejo).
- `decor.*` — carimbos por cima do chão (árvores 2×2, cercas…).
- `bot.baixo/cima/esq/dir` — a caminhada (2+ frames). `bot.<fabrica>.<direcao>` dá um personagem próprio àquela fábrica, sem mudar nada no painel.
- `fx.trabalho` / `fx.erro` — reservados para efeitos em cima dos prédios.

## Como usar

```bash
python -m vila.gerar_base            # cenário base procedural (já vem pronto)
python -m vila.editor                # a Oficina, standalone
python -m unittest vila.test_motor   # contratos do motor
```

No painel: **Vila → 🎨 Oficina**. Fluxo com arte gerada por IA:

1. **➕ Importar folha** (PNG). Põe `auto` na chave → fundo some.
2. Ajustar a **grade** até as linhas casarem com os desenhos.
3. Clicar na célula (Ctrl+clique junta vários frames em ordem), escolher o
   papel e **🎯 Atribuir**.
4. Pintar o **mapa**: chão arrastando, decoração/prédio clicando, botão
   direito arrasta a câmera.
5. **💾 Salvar tudo** — a Vila do painel recompõe na hora.

## Dicas para gerar a arte (PicassoIA etc.)

- Peça **"pixel art sprite sheet"** com grade explícita: *"pixel art sprite
  sheet, 16x16 tiles on a strict grid, flat magenta background #FF00FF, top
  down RPG village tileset: grass, dirt path, water, trees, small houses"*.
- Fundo de **cor chapada** (magenta/verde-limão) → `chave: auto` resolve a
  transparência. Evite fundos com gradiente.
- A folha **não precisa** ter célula de 16px: uma folha 32×32 ou 48×48 é
  normalizada para o tile do mundo automaticamente (NEAREST, sem borrão).
- Prédios ficam bons com 4×3 tiles; árvores com 2×2; bots com 1 tile e 2
  frames por direção.
- Gere UMA categoria por folha (só chão, só prédios…) — grades de IA saem
  mais uniformes assim, e a Oficina aceita quantas folhas quiser.

O cenário base (`sprites/base.png`) é procedural e serve de gabarito: a arte
final só precisa substituí-lo **mantendo os papéis**.
