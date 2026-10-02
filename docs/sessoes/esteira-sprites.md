# Esteira de sprites

A esteira mantém uma ficha por item em `outputs/_ias/esteira_sprites`. O
coordenador usa `python -m esteira_sprites avancar` periodicamente; cada chamada
move no máximo uma etapa por ficha, por isso repetir o comando é seguro.

O portão técnico vem antes do Grok. O Grok apenas lista defeitos, recebe
controles estragados de propósito e nunca publica arte: a aprovação final é do
Adrian pela tela de conferência ou pelo comando `aprovar`.

## Perfis: palco e Vila (02/10/2026)

`python -m esteira_sprites [--perfil palco|vila] [--inventario <json>] <comando>`.
Sem nada, é o palco de sempre. O perfil escolhe quatro coisas
(`config.PERFIS`):

| | palco | vila |
|---|---|---|
| inventário padrão | `docs/palco/inventario_sprites.json` | `docs/vila/inventario_vila.json` |
| fichas | `outputs/_ias/esteira_sprites/<id>/` | `outputs/_ias/esteira_sprites/vila/<id>/` |
| bíblia do prompt | `prompt._palco` (o texto de antes) | `prompt._vila`: cartoon do Neural, folha descrita linha a linha |
| destino do `aprovar` | `palco/biblioteca` pela Oficina (`.tscn`) | `painel/flutuante/arte_vila/<nome_arquivo>` + `.json` ao lado |

- **A imagem-mestra é uma só**: `_mestra/aprovada.png`, a do Neural, para os
  dois perfis (decisão `painel-e-vila/vila-estilo-novo` = mesmo estilo do
  Neural). `mestra` e `mestra-aprovar` recusam fora do perfil palco, e
  `lote --perfil vila` não pede nada enquanto a mestra não estiver aprovada.
- **A pasta `vila/` da raiz foi aposentada** (`aposentar-vila-pixel`): a arte
  nova da Vila vai para `painel/flutuante/arte_vila/`, ao lado de quem desenha.
  O código que a carrega ainda não existe: vem com a arte aprovada.
- O coordenador precisa de uma segunda chamada para a Vila:
  `python -m esteira_sprites --perfil vila avancar`.
- Item com `externo` (a mestra no inventário da Vila) é pulado pelo `lote` e
  recusado pelo `pedir`. Item com `chroma` explícito usa esse fundo; sem ele,
  vale a regra antiga por palavra-chave (a do palco).
- Textura opaca (`fundo` começando com "opaco", como o chão): o prompt pede
  imagem que emenda nos 4 lados, a limpeza não tira chroma e o portão mede a
  costura (salto na emenda até 3x o salto entre vizinhos, piso 12).

## Validador de animação

Folha com `animacao.ciclo` no inventário passa por `esteira_sprites/animacao.py`
no portão, ciclo a ciclo (cada ciclo é uma lista de quadros da grade; nos
personagens da Vila, cada linha da folha 4x4 é uma direção). Reprova com o
número medido, e o motivo vai de volta ao gerador no refazer:

| o quê | como mede | limite de partida |
|---|---|---|
| quadros | células com ≥ 50 px de alfa contra as dos ciclos | exato |
| âncora `pes`/`base` | centróide dos 12% de baixo do alfa e a linha do chão | x 8% da altura; chão 2% (piso 2 px) |
| âncora `centro` | centro de massa | 8% da altura |
| escala | altura do alfa entre vizinhos | 8% |
| paleta | histograma 3 bits/canal contra a média do ciclo (variação total) | 0,25 |
| loop | último→primeiro contra a troca mediana | 2x (piso 0,05) |
| congelado | trocas com diferença < 0,01 | 34% das trocas |
| contorno | perímetro sem pixel escuro (luma ≤ 90) a 2 px | 30% |

Os limites são de partida. Medido em 02/10 na única folha de IA aprovada que
existe (o fogo do piriri, 26 quadros, como ciclo `centro`): paleta 0,10, escala
0,079 (no limite: fogo tremula de propósito), loop 0,12 contra 0,10, nada
congelado; o contorno falta em 95% porque é a arte de antes da mestra. Calibre
com as primeiras folhas da Vila e anote aqui.

A limpeza de um ciclo alinha pelos pés (`ancora="pe"`) e **não** descarta
célula vazia (senão o quadro seguinte subiria de linha e mudaria de direção);
o portão conta e reprova. O `passar` grava a prévia (`previa.gif` e
`previa.webp`, ciclos lado a lado sobre xadrez) mesmo quando reprova; o juiz
recebe a folha, o GIF e a pergunta "liste o que está errado NA ANIMAÇÃO".

Para calibrar sem ficha: `python -m esteira_sprites --perfil vila medir <id> <png>`
imprime as medidas e grava `<nome>_previa.gif` (e `.webp`) ao lado.

## Inventário da Vila

`python -m esteira_sprites.inventario_vila` regenera
`docs/vila/inventario_vila.{json,md}` a partir do código da Vila
(`painel/flutuante/arte.py`, `dados.py`, `vida.py`, `retrato.py` e a prateleira
de `remoto/app`). Rode de novo quando a Vila ganhar prédio, habitante ou enfeite;
o teste `test_inventario_vila_cobre_a_vila_de_hoje` acusa o esquecimento.

## Armadilhas

- O pedido de imagem do correio (`ias.correio.pedir_imagem`) **não leva anexo**:
  a mestra não vai junto com o pedido ao ChatGPT, só ao Grok. O prompt do palco
  diz "anexada"; o da Vila só cita o estilo.
- No inventário do palco, 28 itens têm o campo `fundo` diferente do fundo que o
  prompt e a limpeza usam (a regra por palavra-chave manda). A Vila evita isso
  com `chroma` explícito.
