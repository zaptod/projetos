# Licenças da biblioteca do palco

Tudo o que entra em `palco/biblioteca/` tem uma linha aqui: de onde veio, a
licença e a prova. A fonte de verdade da arte CC0 é `E:\ferramentas\arte_cc0\`
(`LICENCAS.md` e `_manifesto.json` de lá têm o sha256 de cada pacote). Só o
que o palco USA vem para o repositório, já no tamanho de uso
(`trazer_cc0.py` da 16D fez a conversão: máscara branca RGBA, redução, e a
receita do chão).

| arquivo no palco | origem | autor | licença | prova |
|---|---|---|---|---|
| `efeitos/texturas/estrela.png` | Kenney Particle Pack v1.1, `star_06.png` (512 → 256) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/estrela_larga.png` | idem, `star_08.png` | Kenney | CC0 | idem |
| `efeitos/texturas/anel.png` | idem, `circle_02.png` | Kenney | CC0 | idem |
| `efeitos/texturas/faisca.png` | idem, `spark_03.png` | Kenney | CC0 | idem |
| `efeitos/texturas/brilho.png` | idem, `light_01.png` | Kenney | CC0 | idem |
| `efeitos/texturas/chama.png` | idem, `flare_01.png` | Kenney | CC0 | idem |
| `efeitos/texturas/fumaca.png` | idem, `smoke_09.png` | Kenney | CC0 | idem |
| `efeitos/texturas/rastro.png` | idem, `trace_05.png` | Kenney | CC0 | idem |
| `efeitos/texturas/onda.png` | Kenney Light Masks v1.0, `circle_rings_b.png` (512 → 256) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/sequencias/acerto_forte_4x4.png` | "Hit Animation", `hit - yellow.png` (4096 → 2048, 4×4 quadros) | Sinestesia | CC0 | opengameart.org/content/hit-animation-frame-by-frame |
| `efeitos/sequencias/ko_8x8.png` | "2D Explosion Animations #2", `Half Sized/2.png` (8×8 quadros de 256) | Sinestesia | CC0 | opengameart.org/content/2d-explosion-animations-2-frame-by-frame |
| `efeitos/sequencias/poeira_4x2.png` | Kenney Smoke Particles, `White puff/whitePuff00,03,06,10,13,17,20,24` (8 quadros de 256) | Kenney | CC0 | `license.txt` do zip; kenney.nl/assets/smoke-particles |
| `arenas/texturas/pedra.jpg` | Poly Haven `stone_tiles_02_diff_2k.jpg` (dessaturado 45%, escurecido 42%, 512 com borrão leve) | Poly Haven | CC0 | polyhaven.com/a/stone_tiles_02 e polyhaven.com/license |

O resto da biblioteca (lutador, rosto, armas, objetos, arena, HUD) é desenho
vetorial em GDScript feito no repositório. O rosto é o port das 24 expressões
de `neural_fights/effects/character_flair.py`.

Peça nova de IA (PicassoIA, 16F) entra aqui com a prova de origem
(conta compartilhada: histórico com o nosso prompt).
