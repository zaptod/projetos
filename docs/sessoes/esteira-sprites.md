# Esteira de sprites

A esteira mantém uma ficha por item em `outputs/_ias/esteira_sprites`. O
coordenador usa `python -m esteira_sprites avancar` periodicamente; cada chamada
move no máximo uma etapa por ficha, por isso repetir o comando é seguro.

O portão técnico vem antes do juiz (hoje o ChatGPT; antes o Grok). O juiz apenas
lista defeitos, recebe controles estragados de propósito e nunca publica arte: a
aprovação final é do Adrian pela tela de conferência ou pelo comando `aprovar`.

## Fluxo sprite-base → folhas (14/10/2026, tarde) — esteira PAUSADA

Pausada às 11:4x (`ESTEIRA_LIGADA = False`): o pedido ao ChatGPT ia **sem
anexo** (nem a imagem-mestra, nem um desenho do personagem), e cada folha saía
com outra forma. O Adrian: "gerar um sprite base para pegar o estilo certo e a
partir desse sprite base fazer as variações em sprite sheet das animações". O
fluxo novo está no código (`esteira_sprites/base.py`); a esteira **continua
desligada** até a ordem dele.

1. **Todo pedido anexa a imagem-mestra** (`pedir.py`), nos dois perfis. Sem
   ela: `lote` não pede nada e `pedir` levanta `SemMestra` (o palco agora
   também tem `exige_mestra=True`).
2. **Toda folha tem um sprite-base** (`base.id_do_base`), nesta ordem: campo
   `base` no item; habitante da Vila → `habitante_<subgrupo>_base` (as 7 folhas
   de cada IA); a peça parada do mesmo objeto (`cenario/arvore_vento.png` →
   `cenario/arvore.png`); senão `<id da folha>_base` (no palco, o quadro-chave
   do efeito). Os bases derivados (`derivado: true`) **não vão ao JSON** do
   inventário (o Ateliê e a Vila leem o JSON): `config.itens()` os acrescenta.
3. **De onde vem o desenho do base** (`base.referencia`): (1) o Ateliê, o 1º
   quadro de qualquer folha que o Adrian fez para a peça, o base ou uma irmã;
   (2) o que ele aprovou: a ficha do base em `aprovado`/`na_biblioteca`, o 1º
   quadro de uma folha irmã aprovada, ou a peça já na biblioteca sem ficha;
   (3) o base que o **juiz aprovou** (`base.juiz_aprovou`: `a_conferir`, fluxo
   novo, veredito sem grave, portão limpo, não é o controle). `a_conferir`
   sozinho não basta: tentativas esgotadas e juiz que falhou 3x também caem lá.
4. **A folha só é pedida com o base pronto.** O `pedir` grava na ficha
   `base_<n>.png` (transparente, para o juiz) e `base_<n>_chroma.png` (sobre o
   chroma da folha, para o gerador) e anexa: imagem 1 = a mestra, imagem 2 = o
   base. O texto começa com o cabeçalho `ANEXOS (leia antes de desenhar):`
   dizendo o que é cada uma (`prompt.ANEXO_ESTILO`, `prompt.ANEXO_BASE`); um
   prompt repetido (falha do gerador) ou reescrito pelo juiz troca o cabeçalho,
   não empilha. Folha sem base: `base.BaseFaltando`; o `refazer` dela espera.
5. **O juiz da folha recebe o base** (`base_para_juiz.png`, sobre a mesma cor
   lisa) e a pergunta `juiz.PERGUNTA_DO_BASE` ("o personagem dos quadros é o
   mesmo do sprite-base?"), com a nota `mesmo_do_base` no JSON.
6. **`lote`: na mesma prioridade, os bases vêm PRIMEIRO**; base derivado só é
   pedido se alguma folha dele vai precisar (a pedir, do fluxo antigo, ou em
   `refazer` sem base) e não tem outra referência. O Adrian aprova o base e as
   folhas juntos na conferência (o base aparece lá como qualquer `a_conferir`).
7. **Fichas fora do fluxo** (`_fora_do_fluxo`): `outro_gerador` (Gemini, antes
   de 14/10) e `sem_anexo` (pedidas sem `fluxo: base_v1`). Não andam; o
   `avancar` cancela no correio o que estiver pendente e o `ciclo` as refaz no
   fluxo novo PRIMEIRO, dentro do teto, sem gastar tentativa
   (`contar_desde` anda uma casa).

`lote --seco` agora explica cada linha e conta as folhas que esperam o base
mesmo com `--n` pequeno. Medido em 14/10 (código da worktree, fichas reais,
Ateliê e bibliotecas da árvore principal, só leitura):

```
=== --perfil palco lote --prioridade P1 --n 2 --seco ===
acerto_light_base	sprite-base de 1 folha(s): acerto_light
acerto_medium_base	sprite-base de 1 folha(s): acerto_medium
# fora do fluxo (o ciclo refaz PRIMEIRO, sem gastar tentativa): arma_runas_flutuantes, orbe_default, rastro_corte, skill_ritual_carmesim
# folhas P1 que esperam o sprite-base: 19
=== --perfil vila lote --prioridade P1 --n 2 --seco ===
habitante_deepseek_base	sprite-base de 7 folha(s): habitante_deepseek_parado, habitante_deepseek_andar, ...
habitante_gemini_base	sprite-base de 7 folha(s): habitante_gemini_parado, habitante_gemini_andar, ...
# fora do fluxo (o ciclo refaz PRIMEIRO, sem gastar tentativa): predio_digen, predio_estudio, predio_arena, predio_youtube
# folhas P1 que esperam o sprite-base: 12
```

A fila inteira (`--n 999`): palco P1 30 (19 bases, 11 peças), P2 70 (16
bases), P3 281 (16 bases); nenhuma folha do palco entra antes do base. Vila P1
17 (6 bases de habitante, 5 folhas que já têm base, 6 peças), P2 22, P3 22.
As 5 folhas da Vila P1 com base pronto: `habitante_chatgpt_parado`,
`habitante_grok_parado`, `habitante_picasso_andar` (1º quadro da folha irmã
que o Adrian aprovou) e `habitante_arena_parado`, `habitante_bot_parado` (1º
quadro do que ele fez no Ateliê).

Ainda em aberto:
- O `aprovar` de um base derivado exporta como qualquer peça (palco:
  `efeitos/folhas/<id>.png` + cena; Vila: `habitantes/<ia>/base.png`). Ninguém
  carrega esse arquivo; se o Adrian não quiser o base na biblioteca, a
  conferência precisa de um "aprovar só como referência".

### Base rejeitado depois das folhas (decisão `builds/base-rejeitado-depois` = "refazer", 14/10)

Quando o Adrian manda **refazer** ou **descarta** um sprite-base (app ou
`aprovar.refazer`/`descartar`) depois que folhas saíram dele, `base.rejeitar`:

1. grava na ficha do base `versao_rejeitada` = quantas tentativas ela tinha
   (a versão do base é o número de tentativas da ficha dele) e um evento
   `base_rejeitado` com as folhas que voltaram;
2. cada folha **que o Adrian ainda não aprovou** (`pedido`, `gerado`, `limpo`,
   `medido`, `julgado`, `a_conferir`, `refazer`) cuja última tentativa usou o
   desenho da ficha do base (origem `juiz` ou `aprovado_pelo_adrian`) até essa
   versão vai a `refazer` com `espera_base`; o pendente no correio (gerar ou
   julgar) é cancelado. **Não gasta tentativa**: nenhuma tentativa nova, e
   `contar_desde` = todas (o teto recomeça com o base novo). O motivo do
   próximo pedido vira `base.MOTIVO_BASE_NOVO`, exceto se ela já estava em
   `refazer` (o motivo do Adrian ou o erro do correio ficam);
3. `aprovado`, `na_biblioteca` e `descartado` **não mudam**; nem as folhas cujo
   base veio do Ateliê, de uma folha irmã ou da biblioteca (não saíram dele).

A folha guarda a versão que usou: `tentativas[-1].base.versao` (sem o campo =
pedida antes disto = uma das velhas). Enquanto o base novo não passa no juiz,
`base.referencia` dá `None` (o base rejeitado também desliga a folha irmã
aprovada e a arte da biblioteca, que são o desenho velho; só o Ateliê, o base
novo aprovado pelo Adrian ou o base novo aprovado pelo juiz servem) e o
`preparar` não reaproveita o base velho: o `refazer` da folha espera
(`BaseFaltando`, "espera o sprite-base NOVO"). Quando o juiz aprova o base
novo, o `avancar` repede as folhas com ele e o `pedir` tira o `espera_base`
(evento `base_novo`).

Base **descartado** com folhas esperando o novo: o descarte do Adrian, que
normalmente fica fora, não vale para ele; o `lote` pede o base de novo (senão
as folhas esperavam para sempre). Se ele descartar também as folhas, ninguém
espera e o base fica fora. O `lote --seco` mostra a linha
`# folhas que esperam o sprite-base NOVO` quando há alguma.

## Religada com o ChatGPT gerando tudo (14/10/2026)

Ordem do Adrian no chat: "Agora que tudo já está mais limpo e organizado quero
que você volte a utilizar o ChatGPT para os sprites." Ele não quis decidir
detalhes; o que ficou:

- **Ligada** (até 11:4x; depois PAUSADA, ver a seção acima): `ESTEIRA_LIGADA = True` e `FOLHAS_POR_IA = True` em
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

- Até 14/10 (manhã) o pedido de imagem da esteira **não levava anexo**. Desde o
  fluxo sprite-base, `pedir` passa `anexos=` ao `ias.correio.pedir_imagem`, e o
  carteiro só entrega pedido com anexo a quem recebe anexo no chat
  (`correio.CHATS`); o ChatGPT recebe.
- Ficha sem `fluxo: base_v1` na última tentativa é do fluxo antigo: não anda
  e é refeita. Teste que monta ficha à mão em produção precisa desse campo.
- Base que já foi para a biblioteca (`na_biblioteca`) e depois o Adrian manda
  refazer: as folhas esperam o novo (a biblioteca não serve mais de
  referência), mas o `aprovar` do base novo vai dar `FileExistsError`, porque
  nunca sobrescreve. Tirar o arquivo velho à mão antes de aprovar.
- No inventário do palco, 28 itens têm o campo `fundo` diferente do fundo que o
  prompt e a limpeza usam (a regra por palavra-chave manda). A Vila evita isso
  com `chroma` explícito.
