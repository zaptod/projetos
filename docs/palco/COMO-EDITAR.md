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
# um duelo já publicado contra o palco, lado a lado
python main.py palco ab --duelo duelo_00016
```

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
| Tremor e hitstop | tremor da câmera nos golpes fortes; hitstop EXTRA por tier (muda a duração do vídeo) |
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
| arena | `arenas/<nome>.tscn` (ex. `salao_da_torre.tscn`) > `arenas/temas/<tema>.tscn` > `arenas/_padrao.tscn` |

Um efeito sem script com um AnimationPlayer `Anim` toca a primeira animação
pelo tempo de jogo (congela no hitstop, anda devagar no slow-mo) e some quando
ela acaba. Na arena, 100 px = 1 m e (0, 0) é o canto superior esquerdo do chão.

## 8. Licença

Todo arquivo que entrar na biblioteca ganha uma linha em
`palco/biblioteca/LICENCAS.md` (origem, autor, licença, prova). A arte CC0 mora
em `E:\ferramentas\arte_cc0\` (com `catalogo_candidatos.md`); traga só o que
usar, já no tamanho de uso. Arte do PicassoIA só com prova de origem (a conta é
compartilhada).
