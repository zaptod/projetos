# Como editar o palco (guia curto)

O palco desenha a luta com PEÇAS de `palco/biblioteca/`. Para trocar qualquer
coisa você cria um arquivo com o NOME certo; não há catálogo para editar. Se a
peça faltar ou quebrar, entra a de reserva (`_padrao`) e nada some da tela.
Depois de mexer, gere uma prévia (passo 2) e olhe.

Comandos a partir de `E:\projetos\random_builds`.

## 1. Abrir o editor

```bash
python main.py palco editor
```

Abre o Godot 4.7 com o projeto `palco/` (o `user://` vai para o E:, não para o
C:). No editor, **F5** toca `palco/exemplos/exemplo.timeline.json` em tempo
real, em loop, numa janela pequena.

## 2. Gerar uma prévia (mp4 com som)

```bash
# o exemplo (4 s), em ~15 s
python main.py palco render --timeline ../palco/exemplos/exemplo.timeline.json --mp4 ../palco/_saida/previa.mp4
# uma luta de verdade pela seed, só os primeiros 5 s
python main.py palco render --seed 883770751 --p1 "Isandro Lumeprego" --p2 "Silas o Sombrio" --arena Torre --quadros 150
# um duelo já publicado contra o palco, lado a lado (--hud liga o HUD do palco)
python main.py palco ab --duelo duelo_00016 --hud
# a VITRINE: todas as peças animadas, página por página (~40 s de vídeo)
python main.py palco vitrine
python main.py palco vitrine --so rostos      # só as páginas cujo título tem "rostos"
```

A vitrine sai em `outputs/_palco/vitrine/vitrine.mp4` e mostra o que a
biblioteca RESOLVE: os 24 rostos (visão geral e a 408 px), os acertos e
eventos, os efeitos por tipo × elemento, o HUD sobre uma luta de mentira e as
armas. Peça nova aparece lá sem mexer em nada.

Ao lado de cada mp4 fica `<nome>.palco.json`. Em `pecas` está o arquivo que
entrou para cada pedido; em `reservas`, o que caiu no `_padrao`. É assim que
você confere se a sua peça nova foi usada.

**Evite renderizar entre :25 e :55** (é a janela das postagens).

## 3. Trocar uma arma

1. Descubra o **estilo** da arma (ex.: `Machado-Martelo`, `Espada Longa`) e o
   **tipo** (`Reta`, `Dupla`, `Corrente`, `Arremesso`, `Arco`, `Orbital`,
   `Mágica`, `Transformável`).
2. O nome do arquivo é o nome em minúsculas, sem acento, com `_` no lugar de
   espaço e hífen: `Machado-Martelo` → `machado_martelo.tscn`, `Mágica` →
   `magica.tscn`.
3. No editor: *Cena → Nova Cena → Node2D*. Ponha dentro a imagem (Sprite2D) ou
   o desenho. **Regras de montagem:**
   - a origem (0, 0) da cena é a **empunhadura** (a mão);
   - a arma aponta para a **direita** (+x);
   - o comprimento empunhadura → ponta, em px, vai em **`comprimento_ref`**:
     no nó raiz, *Anexar script* → `res://nucleo/peca.gd` e ajuste o campo no
     inspetor. Sem esse script vale 100 px.
4. Salve como `palco/biblioteca/armas/estilos/<estilo>.tscn` (só aquele estilo)
   ou `palco/biblioteca/armas/tipos/<tipo>.tscn` (todas as armas do tipo).
   Ordem de busca: **estilo > tipo > `_padrao`**.
5. **O palco estica a peça para o comprimento REAL da hitbox** e a gira para
   onde o golpe está: o que você desenha é o que acerta.

### O golpe animado (opcional)

Ponha um **AnimationPlayer** chamado `Anim` com uma animação `golpe`. Nela, crie
**marcas** (botão direito na régua da animação → *Inserir marca*) com os nomes
das fases: `preparo`, `golpe`, `impacto`, `seguimento`, `recuperacao`. O palco
leva a animação ao PROGRESSO de cada fase do motor, então ela cabe em qualquer
duração (um golpe de 0,5 s ou de 1 s). Sem marcas, a animação é dividida em 5
partes iguais. Uma animação `parado` (opcional) toca em loop fora do golpe.
Anime o que é enfeite (brilho, rastro, balanço); a posição e o ângulo da arma
vêm da luta.

## 4. Trocar um lutador

- `palco/biblioteca/lutadores/classes/<classe>.tscn` vale para a classe
  (`Piromante (Fogo)` → `piromante_fogo.tscn` ou só `piromante.tscn`);
- `palco/biblioteca/lutadores/nomes/<nome>.tscn` vale para um personagem;
- a origem é o **centro do corpo no chão**; desenhe o corpo com raio
  **`raio_ref`** (script `res://nucleo/peca.gd`, padrão 100 px). O palco escala
  para o raio real (`tamanho / 2`, o círculo que a simulação usa).
- O padrão (`lutadores/lutador_padrao.gd`) desenha a bolinha com as **24
  expressões** do jogo, o contorno, a sombra e as marcas de status. Uma peça
  sem script não muda de rosto: para manter as expressões, estenda o padrão.

### O rosto

As 24 expressões (`lutadores/rosto.gd`) são montadas com as **peças do Kenney
Shape Characters** (CC0), uma por arquivo em `lutadores/rosto/`: olho
(`eye_open`), meio-olhos (`eye_half_top`, `eye_half_bottom`,
`eye_half_top_wing`), olhos fechados (`eye_closed_up` = feliz,
`eye_closed_down` = calmo), olho em X (`eye_x`), 4 sobrancelhas
(`eyebrow_a` fina, `b` inclinada, `c` curta, `d` grossa) e 3 bocas
(`mouth_happy`, `mouth_sad`, `mouth_smirk`). Os png são BRANCOS: o palco pinta
com a cor do contorno do estilo (#14141A). O branco do olho arregalado e dos
dentes leva o cel de 2 tons (base e sombra embaixo) e o contorno; o brilho do
olho fica no canto da luz (alto à esquerda da tela), como o do corpo.

- **Trocar o desenho de uma peça:** substitua o png com o MESMO nome (branco
  com alfa, com ~6 px de borda vazia). O tamanho na tela vem do olho: o
  diâmetro do olho aberto (largura do `eye_open.png` menos 12 px) vale 0,40
  do raio do corpo, e as outras peças mantêm a proporção entre si.
- **Refazer todas do SVG:** `python main.py palco pecas-do-rosto --folha F.png`
  (rasteriza o `overview.svg` a 12×: nenhuma peça é ampliada numa bolinha de
  408 px, e o teste do palco cobra isso).
- **Mudar uma expressão:** o `match` no fim de `rosto.gd` (uma linha por
  expressão: quais peças, tamanho e inclinação da sobrancelha).

## 5. Mudar um som

- **No jogo E no vídeo:** troque o arquivo em
  `%LOCALAPPDATA%\neural-fights\sounds\` (e o `sound_config.json` de lá), como
  foi feito em 28/08. O próximo render já usa, sem regravar a luta.
- **Só no vídeo:** ponha `palco/biblioteca/sons/<id>.wav` (ou `.ogg`, `.mp3`).
  O `<id>` é a chave do som (`slash_heavy`, `impact_heavy`, `ko_impact`...,
  lista em `docs/palco/sons.md` e em `neural_fights/sounds/sound_config.json`).
- WAV a **48 kHz**; **FLAC não entra** (converta para OGG ou WAV).
- O volume geral, o estéreo e o número de sons simultâneos estão no estilo
  (passo 6).

## 6. Mudar o estilo de tudo

Abra `palco/biblioteca/estilo.tres` no editor e mexa no inspetor:

| grupo | campos |
|---|---|
| Contorno e sombra | largura e cor do contorno (#14141A), opacidade e achatamento da sombra |
| Tremor e hitstop | tremor da câmera nos golpes fortes; hitstop EXTRA por tier (LIGADO: 0 / 0,03 / 0,07 / 0,13 s) e o piso de dano (`hitstop_dano_min`, 3% da vida) abaixo do qual o golpe não para; muda a duração do vídeo (+2,6% medido) |
| Brilho e efeitos | halo dos projéteis e faíscas, cel do corpo (0 = chapado), tamanho da faísca, rastro da arma |
| Leitura | nome sobre o lutador e o tamanho dele, marcas de status, barras de cinema do golpe final, cor do fundo |
| Som | estéreo, volume, vozes |

Para um render só, sem mexer no arquivo:
`python main.py palco render ... --estilo tremor=0 --estilo nome_px=52`.

## 7. Efeitos e arenas

| peça | arquivo (ordem de busca) |
|---|---|
| efeito de evento | `efeitos/eventos/<tipo>_<tier>.tscn` > `efeitos/eventos/<tipo>.tscn` > `efeitos/eventos/_padrao.tscn` (tipos: `acerto`, `bloqueio`, `parry`, `esquiva`, `dash`, `parede`, `wall_splat`, `ko`, `skill`, `escudo_quebrou`, `cura`; tiers: `light`, `medium`, `heavy`, `colossal`) |
| projétil, área, beam... | `efeitos/skills/<skill>.tscn` > `efeitos/objetos/<tipo>/<elemento>.tscn` > `efeitos/objetos/<tipo>/_padrao.tscn` > `efeitos/objetos/_padrao.tscn` |
| HUD (nome, vida, plano) | `hud/_padrao.tscn` (liga com `--hud`) |
| arena | `arenas/<nome>.tscn` (ex. `salao_da_torre.tscn`) > `arenas/temas/<tema>.tscn` > `arenas/_padrao.tscn` |

**Efeitos por tipo × elemento (16E).** Projétil, área e beam têm uma cena
por elemento (os 12: `fogo`, `gelo`, `raio`, `trevas`, `luz`, `natureza`,
`arcano`, `caos`, `sangue`, `void`, `tempo`, `gravitacao`) e um `_padrao` do
tipo para elemento sem cena. Todas usam `efeitos/objetos/objeto_cc0.gd` com
texturas CC0 (máscaras brancas pintadas com a paleta do elemento). Para trocar
a arte de um par, abra a cena no editor e troque a textura no inspetor, grupo
"Arte (CC0)" (`nucleo` e `halo` do projétil, `preenchimento` e `anel` da área,
`corpo` e `ponta` do beam); no grupo "Movimento e cor" ficam o giro, o
tamanho, a mistura (`aditivo`), as duas cores do caos, o buraco do void, os
ponteiros do tempo e o anel que encolhe da gravitação. Para UMA skill, salve
uma cópia como `efeitos/skills/<skill>.tscn`. As cenas foram geradas por
`python main.py palco efeitos-cc0` a partir do catálogo CC0; rodar de
novo SOBRESCREVE as 39 cenas da tabela (e escreve as licenças).
Orbe, summon, trap e portal seguem no desenho da 16D (`objetos/_padrao`).

### Folha de sprite animada (o formato que a Oficina exporta)

Uma animação quadro a quadro (a do ChatGPT, por exemplo) entra no palco como
**duas peças com nome**: a imagem e uma cena que aponta para ela. Não há
catálogo: a CENA vai no caminho que a biblioteca procura, e o palco a usa no
lugar do padrão.

**1. A imagem** — `palco/biblioteca/efeitos/folhas/<nome>.png`
- RGBA com fundo **transparente** (nada de branco ou "xadrez" desenhado);
- uma **grade de quadros do mesmo tamanho**: largura = colunas × largura do
  quadro e altura = linhas × altura do quadro, **em px inteiros** (uma folha
  de 1942 px em 6 colunas não fecha: 323,67 px por quadro, e o quadro vaza
  no vizinho);
- quadros da esquerda para a direita, de cima para baixo; células vazias só
  no FIM da grade;
- o objeto desenhado **apontando para a DIREITA** (+x), já recortado e
  alinhado: o mesmo ponto (o centro da bola, o pé da explosão) na mesma
  posição em todos os quadros;
- até ~512 px por quadro (a bolinha de 408 px é o maior uso; mais que isso
  só pesa).

**2. A cena** — `<nome>.tscn` num destes lugares (a ordem de busca é a da
tabela acima):

| para | salve como |
|---|---|
| uma skill | `efeitos/skills/<skill>.tscn` (ex. `bola_acida.tscn`) |
| todo projétil / área / orbe de um elemento | `efeitos/objetos/<tipo>/<elemento>.tscn` |
| um evento | `efeitos/eventos/<tipo>.tscn` ou `<tipo>_<tier>.tscn` (ex. `acerto_heavy.tscn`) |

O nome passa pelo mesmo `slug` (minúsculas, sem acento, `_` no lugar de
espaço e hífen). A cena é um `Node2D` com o script
`res://biblioteca/efeitos/folha_animada.gd` e estes campos:

| campo | o que é | padrão |
|---|---|---|
| `folha` | a imagem da folha | — |
| `colunas`, `linhas` | a grade | 1, 1 |
| `quadros` | quantos quadros valem (os últimos da grade podem ser vazios); 0 = todos | 0 |
| `fps` | quadros por segundo de JOGO (congela no hitstop, anda devagar no slow-mo) | 24 |
| `laco` | `true` repete (projétil, aura); `false` toca uma vez (evento); num objeto sem laço, a vida dele (`prog` 0→1) escolhe o quadro | `true` |
| `ancora` | o ponto do QUADRO, em px a partir do canto de cima à esquerda, que fica na posição da peça (o centro do projétil, o pé da explosão); `(-1, -1)` = o centro | `(-1, -1)` |
| `girar` | gira com o ângulo do objeto (ou com a direção do golpe, no evento) | `true` |
| `escala_raio` | se > 0, a largura do quadro = `escala_raio` × o DIÂMETRO da hitbox (projétil, orbe, área): o que acerta é o que aparece | 0 |
| `tamanho_m` | senão, a largura do quadro no mundo, em metros (100 px = 1 m; a bolinha tem ~1,7 m) | 1,0 |
| `aditivo` | luz somada (fogo, energia) em vez de tinta normal | `false` |
| `tingir` | `""` = as cores da folha; `"elemento"` = multiplica pela cor do elemento; `"#RRGGBB"` = uma cor fixa | `""` |
| `duracao_s` | evento: quanto vive (s de jogo); 0 = uma volta da folha | 0 |
| `sumir_s` | evento: segundos finais em que ela some | 0,1 |

Exemplo (a bola ácida de 26 quadros numa grade 6 × 5 de 324 × 162 px):

```
[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://biblioteca/efeitos/folha_animada.gd" id="1_folha"]
[ext_resource type="Texture2D" path="res://biblioteca/efeitos/folhas/bola_acida.png" id="2_folha"]

[node name="BolaAcida" type="Node2D"]
script = ExtResource("1_folha")
folha = ExtResource("2_folha")
colunas = 6
linhas = 5
quadros = 26
fps = 18.0
laco = true
ancora = Vector2(250, 81)
escala_raio = 3.2
```

**3. Metadados e licença.** Ao lado da imagem, `efeitos/folhas/<nome>.json`
(opcional, para a Oficina e para quem revisa): `origem` (ferramenta e
modelo), `autor`, `licenca`, `prova` (onde está a conversa ou o histórico
com o nosso prompt), `data`, e o que foi feito na limpeza. **Obrigatório:**
uma linha em `palco/biblioteca/LICENCAS.md`. Arte de IA só entra com prova de
origem (conta compartilhada).

**4. Conferir.** `python main.py palco vitrine --so folhas` mostra toda cena
da biblioteca feita com `folha_animada.gd` (a página "FOLHAS ANIMADAS" aparece
sozinha); para ver numa luta, `palco render` e o `<mp4>.palco.json` diz em
`pecas` qual arquivo entrou. O beam ainda não aceita folha (ele é um traço
entre dois pontos): use o `objeto_cc0` com `corpo` e `ponta`.

Um efeito sem script com um AnimationPlayer `Anim` toca a primeira animação
pelo tempo de jogo (congela no hitstop, anda devagar no slow-mo) e some quando
ela acaba. Na arena, 100 px = 1 m e (0, 0) é o canto superior esquerdo do chão.

## 8. Licença

Todo arquivo que entrar na biblioteca ganha uma linha em
`palco/biblioteca/LICENCAS.md` (origem, autor, licença, prova). A arte CC0 mora
em `E:\ferramentas\arte_cc0\` (com `catalogo_candidatos.md`); traga só o que
usar, já no tamanho de uso. Arte do PicassoIA só com prova de origem (a conta é
compartilhada).
