# Esteira de sprites

A esteira mantém uma ficha por item em `outputs/_ias/esteira_sprites`. O
coordenador usa `python -m esteira_sprites avancar` periodicamente; cada chamada
move no máximo uma etapa por ficha, por isso repetir o comando é seguro.

O portão técnico vem antes do juiz (hoje o ChatGPT; antes o Grok). O juiz apenas
lista defeitos, recebe controles estragados de propósito e nunca publica arte: a
aprovação final é do Adrian pela tela de conferência ou pelo comando `aprovar`.

## Religada com o ChatGPT gerando tudo (14/10/2026)

Ordem do Adrian no chat: "Agora que tudo já está mais limpo e organizado quero
que você volte a utilizar o ChatGPT para os sprites." Ele não quis decidir
detalhes; o que ficou:

- **Ligada:** `ESTEIRA_LIGADA = True` e `FOLHAS_POR_IA = True` em
  `esteira_sprites/__main__.py` (peças paradas E folhas animadas). O coordenador
  já chamava `python -m esteira_sprites --perfil <palco|vila> ciclo` a cada 5 min
  (`coordenador/supervisor.py::ciclo_das_esteiras`); nada mudou lá.
- **Gerador = ChatGPT, sempre** (`pedir.GERADOR`), para peça e folha, palco e
  Vila. `pedir()` não aceita mais `caixa`: não há como mandar a outra IA. O
  caminho é o de sempre (`ias.correio.pedir_imagem` → carteiro, contas, travas,
  prova de origem).
- **Acabou a cobertura pelo Gemini** (decisão `painel-e-vila/folhas-chatgpt-ocupado`,
  de 02/10, superada): com o ChatGPT ocupado, a ficha ESPERA em `pedido` na
  caixa dele, sem prazo.
- **Fichas que o Gemini começou** (antes de 14/10: 4 do palco e 4 da Vila em
  `gerado`/`limpo`/`pedido`) não andam com a imagem dele: o `avancar` cancela no
  correio o que estiver pendente, e o `ciclo` as refaz no ChatGPT dentro do
  mesmo teto, antes de pedir item novo. A tentativa do Gemini fica na ficha
  (`trocado_para: chatgpt`) e não gasta o teto (`contar_desde` anda uma casa).
- **Juiz = ChatGPT** (`juiz.JUIZ`; a constante dizia "gemini" e não era usada).
  Ele julga o que ele mesmo gerou; o que compensa: o controle cego (1 em 10 vai
  estragado de propósito; sem defeito grave, a ficha marca `juiz_fraco`), a
  medida do portão e a aprovação do Adrian. A pergunta diz o jogo, o que é o
  desenho, o formato, para que serve a resposta e agora sempre o **TAMANHO
  REAL NA TELA** (`juiz.tamanho_real_txt`: o "no mundo WxH (xN no celular)" da
  Vila; no palco, a escala da bolinha de ~400 px no vídeo 1080x1920, ~144 px
  no celular).
- **O que o Adrian já fez nunca é pedido** (`esteira_sprites/ja_feito.py`,
  usado pelo `lote`):
  1. folha dele no Ateliê: `palco/biblioteca/animacoes/<peça>/<estado>/<animação>/folha.png`
     (o `historico/` não conta). Na Vila a chave é a mesma que o Ateliê e a
     Vila usam (`catalogo_vila.chave_do_item`); no palco, a pasta do
     `nome_arquivo` diz a família do catálogo (`PALCO_NO_ATELIE`: `armas/estilos`
     e `efeitos/orbes` → `arma.estilo`, `lutadores/status` → `estado`, skills →
     `skill`...) e qualquer animação da peça conta;
  2. arte já na biblioteca: a Vila em `painel/flutuante/arte_vila/<nome_arquivo>`;
     o palco em `palco/biblioteca/<nome_arquivo>` (pega o fogo do piriri,
     `efeitos/folhas/11239_removebg_preview_1.png`) ou onde o `aprovar`
     exportaria (`efeitos/folhas/<id>.png`). O `aprovar` nunca sobrescreve, então
     pedir isso só gastaria a vez do ChatGPT.
- **Descartados:** os descartes de 02/10 (01:03 e 16:42) foram a parada da
  esteira, não um "não quero": o item volta à fila com o teto zerado
  (`volta_a_fila`). O que o Adrian descartar daqui em diante
  (`RELIGADA_EM = "2026-10-14"`) fica fora; antes, o ciclo seguinte repedia.
- **Ritmo:** `ALVO_EM_VOO = 2` por perfil (era 4). O ChatGPT também faz as
  imagens das histórias pelo rodízio e o carteiro entrega um pedido por vez
  por conta: no máximo 4 imagens da esteira na fila dele, e as histórias
  passam entre elas.
- **Aprovação final continua dele:** nada sai de `a_conferir` para
  `palco/biblioteca` nem para `painel/flutuante/arte_vila` sem o `aprovar`. No
  palco o `aprovar` (Oficina) grava `efeitos/folhas/<id>.png`, a cena e anota o
  `LICENCAS.md`, sem sobrescrever nada.
- **Medir sem gastar:** `python -m esteira_sprites [--perfil vila] lote --prioridade P1 --n 999 --seco`
  lista o que seria pedido, sem gravar ficha nem tocar o correio.

Medido em 14/10 (seco, fichas e Ateliê reais): a primeira passada pede **2 no
palco** (refaz `arma_runas_flutuantes` e `orbe_default`, que eram do Gemini) e
**2 na Vila** (`predio_digen`, `predio_estudio`). A fila depois disso: palco
P1 30, P2 72, P3 287 (389: 338 peças, 51 folhas); Vila P1 23, P2 40, P3 34
(97: 21 peças, 76 folhas). Pulados por já feitos: 9 no palco (1 do Ateliê,
8 na biblioteca) e 15 na Vila (4 do Ateliê, 11 já aprovados).

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

## Conferência pelo celular e exportação

`GET /api/sprites/conferir` lista somente fichas `a_conferir` dos dois perfis,
com tentativas desde `contar_desde`, veredito, portão e URLs fechadas dos
arquivos da ficha. O app usa essa lista em **Decidir > 🎨 Sprites**. As ações
pareadas `POST /api/sprites/<perfil>/<id>/aprovar|refazer|descartar` exigem
`--acoes`; em `refazer`, o motivo vira o motivo do próximo pedido e reinicia
`contar_desde` antes dele.

Na Vila, a exportação salva PNG otimizado: peça até 512 px no maior lado,
folha até 1024 px (256 px por célula 4×4), com LANCZOS. O `.json` ao lado
guarda `tamanho_original`, para a prova continuar auditável sem versionar a
arte grande da IA.

## Armadilhas

- O pedido de imagem do correio (`ias.correio.pedir_imagem`) **não leva anexo**:
  a mestra não vai junto com o pedido ao ChatGPT, só ao Grok. O prompt do palco
  diz "anexada"; o da Vila só cita o estilo.
- No inventário do palco, 28 itens têm o campo `fundo` diferente do fundo que o
  prompt e a limpeza usam (a regra por palavra-chave manda). A Vila evita isso
  com `chroma` explícito.
