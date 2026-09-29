# `sons` — o som que o jogo tocou (contrato da Onda 16A)

Dono: builds (16A, 28/09/2026). Leitor: o palco (16C/16D), que reservou a
seção `sons` da timeline para este formato. Código de referência:
`neural_fights/effects/audio_anotador.py` (quem anota) e
`neural_fights/effects/mixagem.py` (quem transforma em áudio).

## De onde vem

O gravador (`neural_fights/recording/fight_recorder.gravar_luta`, com
`anotar_som=True`, o padrão) injeta um `AnotadorDeAudio` no
`Simulador(audio=...)`. Ele é um `AudioManager` que herda TODA a decisão de som
do jogo — grupo → variante, volume por categoria, atenuação por distância, som
fora do alcance que não toca — e troca só as duas pontas que tocam no
dispositivo: não abre mixer e não decodifica arquivo. Cada `sound.play()` que o
jogo faria vira uma linha. Nada da luta muda (ver Determinismo).

## Formato

Uma lista JSON de objetos, na ordem em que o jogo pediu (`t` não decresce):

| campo    | tipo e precisão      | unidade                       | quando          |
|----------|----------------------|-------------------------------|-----------------|
| `t`      | float, 3 casas       | segundos, relógio do VÍDEO    | sempre          |
| `i`      | int                  | passo do motor (60 Hz)        | desde 28/09 (revisão 2 da timeline) |
| `id`     | string               | chave do som no jogo          | sempre          |
| `volume` | float 0..1, 4 casas  | ganho linear                  | sempre          |
| `pitch`  | float > 0, 4 casas   | razão de velocidade de leitura| sempre          |
| `pan`    | float -1..1, 3 casas | esquerda..direita             | só se ≠ 0       |
| `x`      | float, 2 casas       | metros, coordenada do mundo   | só posicional   |

- **`id`** é a CHAVE, não o arquivo. Num grupo (`"impact"`, `"slash"`...) é a
  variante já sorteada (`"impact_flesh"`, `"slash_heavy"`). Exemplos:
  `arena_start`, `slash_light`, `slash_heavy`, `slash_critical`,
  `impact_heavy`, `energy_blast`, `fireball_impact`, `dash_whoosh`,
  `jump_start`, `jump_land`, `clash_swords`, `wall_hit`, `ko_impact`,
  `slowmo_whoosh`, `arena_victory`.
- **`volume`** é o que o jogo passaria ao `Sound.set_volume`: base × categoria ×
  `sfx_volume` × `master_volume` × distância, com o teto de 1,0 do pygame. As
  categorias vêm do `_volumes` do `sound_config.json` (no do Adrian, "ambiente"
  está em 0,03 — parede e abertura de arena quase caladas, como ao vivo).
  Atenção: o jogo ao vivo soma esquerda e direita num volume só quando há pan
  (`AudioManager.play`), então um som posicional sai até 2× mais alto que o
  mesmo som sem pan; o `volume` anotado já é esse número final.
- **`pitch`**: 1.0 é o arquivo como é; 1.05 lê 5% mais rápido (mais agudo e
  mais curto, como fita). O jogo ao vivo não tem pitch: a variação existe para
  o vídeo não repetir o mesmo golpe 25 vezes.
- **`pan`** e **`x`**: anotados para quem quiser espacializar (o palco). O jogo
  ao vivo não faz estéreo e a mistura do vídeo de hoje também não usa.
- **`i`** é o passo exato do motor em que o jogo pediu o som (`ac270f2`, a
  revisão 2 da timeline): o mesmo relógio das trilhas e dos eventos da
  timeline (`i / 60` s). Quem grava (`fight_recorder` e `gravar_timeline`)
  avança `AnotadorDeAudio.passo` junto com o `t_video`; sem isso
  (`passo = None`) o campo não sai. É aditivo: o `t` não mudou e a mistura
  do mp4 continua lendo só o `t`.

## Relógio: `t` é tempo de VÍDEO

- Não é tick nem tempo de jogo. O motor roda a 60 Hz e o vídeo a 30 fps (dois
  passos de jogo por quadro); `t = quadros_capturados / fps` no começo do passo
  em que o som foi pedido. O som aparece no quadro que captura aquele passo.
- É o MESMO relógio de `eventos_dano`, `serie_hp`, `serie_plano` e
  `eventos_narrativos`.
- No slow-motion do KO o vídeo continua andando um quadro por passo e o jogo
  anda menos: `t` fica no relógio do vídeo (o som cai quando a imagem mostra),
  e o som não é esticado.
- `arena_start` sai em `t = 0` (pedido na configuração da partida, antes do
  primeiro passo), com `i = 0`.
- **`t` e `i` juntos:** `t = ceil(i / 2) / 30` na gravação bruta (um som
  pedido num passo ímpar aparece no quadro do passo par seguinte; há teste
  cobrando). No corte de tédio (abaixo) o `t` vai para o relógio do CLIPE e
  o `i` **fica**: ele continua dizendo em que passo da timeline (gravação
  bruta) o som nasceu.

## Onde a lista mora, e o corte de tédio

1. O resultado do gravador (`fight_recorder`, uma linha JSON) traz `sons` no
   relógio da GRAVAÇÃO bruta, com `versao_sons: 1`.
2. O corte de tédio (`random_builds/builds/tournament/highlights.py`,
   `remapear_gravacao(gravacao, trechos)`) leva a lista para o relógio do CLIPE
   com `mapear_tempo`: `t_clipe = soma das durações dos trechos anteriores +
   (t − início do trecho)`. **Som cujo `t` cai num corte sai da lista.** Um som
   que começou antes de um corte continua soando por cima do jump cut (a
   mistura soma o arquivo inteiro a partir do `t`).
3. `fight.json` → `luta.sons` e `lutas[i].sons` ficam no relógio do CLIPE;
   `edit_plan.json` → evento `gameplay` → `luta.sons` também.
4. Evento que mostra só um pedaço do clipe (o round decisivo no fim do vídeo de
   build) tem `start_offset`: quem mistura usa `t − start_offset`, e aceita o
   som que começou antes do pedaço pela cauda.
5. Luta gravada antes de 28/09/2026 não tem a chave. `main.py som-da-luta <id>`
   re-simula a MESMA luta sem vídeo e grava a lista (recusa se vencedor,
   duração ou golpes não baterem com o `fight.json`).

## Como virar áudio (o que `mixagem.py` faz)

- **Arquivo**: resolvido NA HORA pela cadeia do jogo, nunca guardado na lista —
  `sound_config.json` do runtime (`%LOCALAPPDATA%\neural-fights\sounds\`) se
  existir, senão o do pacote; o arquivo configurado é procurado no runtime e
  depois no pacote; sem configuração, `<id>.wav/.ogg/.mp3`; sem arquivo,
  `AudioManager.SOUND_FALLBACKS[id]`, recursivo. `arquivos_de_som()` devolve o
  mapa `id -> arquivo` pronto. Trocar um wav vale no próximo render, sem
  regravar a luta.
- **Tocar**: amostras × `volume`, lidas a `pitch` × a velocidade, começando em
  `t`.
- **Nível**: a mistura do vídeo normaliza o trecho de luta (energia dos momentos
  ativos em `alvo_db`, hoje −13 dBFS, `random_builds/config/editing.json →
  som_da_luta`) e limita o pico em −2,5 dBFS (o trecho ainda vira aac antes
  da mixagem final, e o aac passa do pico da fonte). É decisão de vídeo, não
  do contrato.

## Determinismo

- A variante de um grupo é sorteada pelo `random` GLOBAL, exatamente como o
  `AudioManager.play`. É isso que mantém partículas e tremor de câmera iguais
  aos da gravação sem anotador: o gravador sempre rodou com o `AudioManager` de
  verdade (o driver `dummy` abre o mixer), e esse sorteio já consumia o
  `random` global. Teste: `tests/test_som_real_da_luta_regressions.py`
  (vencedor, duração, HP, golpes e o estado do `random` no fim, com e sem
  anotador).
- O `pitch` usa `random.Random(f"neural-fights:som:{seed}")`, um sorteio por
  som emitido e na ordem de emissão, com variação por categoria do NOME PEDIDO
  (`VARIACAO_DE_PITCH`: golpes ±7%, impactos ±6%, projéteis e skills ±4%,
  movimento ±8%, ambiente e interface fixos). Não toca no `random` global.
- Mesma luta e mesma seed = mesma lista.

## Versão

`versao_sons` = 1 (`VERSAO_SONS` em `audio_anotador.py`). Campo novo e opcional
não muda a versão; mudar o significado de um campo existente (unidade, relógio)
sobe.

O `i` entrou assim em 28/09/2026: `versao_sons` continua 1; quem quiser
saber se a lista tem `i` olha a `revisao` da timeline (≥ 2) ou o próprio
item. Lista gravada antes disso (os `fight.json` de antes de 28/09 à
tarde) não tem o campo.

## Exemplo (duelo real, relógio do vídeo; gravado antes do `i`)

```json
[
  {"t": 0.0,   "id": "arena_start",   "volume": 0.0134, "pitch": 1.0},
  {"t": 0.0,   "id": "energy_blast",  "volume": 0.6689, "pitch": 0.9728, "pan": 0.101, "x": 2.02},
  {"t": 0.067, "id": "dash_whoosh",   "volume": 0.6698, "pitch": 0.9825, "pan": 0.101, "x": 2.01},
  {"t": 1.0,   "id": "energy_impact", "volume": 0.8025, "pitch": 0.9908, "pan": 0.143, "x": 2.85}
]
```
