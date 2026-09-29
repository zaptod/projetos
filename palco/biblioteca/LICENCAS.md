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

| `lutadores/rosto/*.png` (14 peças: `eye_open`, `eye_half_top`, `eye_half_top_wing`, `eye_half_bottom`, `eye_closed_up`, `eye_closed_down`, `eye_x`, `eyebrow_a`, `eyebrow_b`, `eyebrow_c`, `eyebrow_d`, `mouth_happy`, `mouth_sad`, `mouth_smirk`) | Kenney Shape Characters v1.0, `Vector/overview.svg` rasterizado a 8× pelo Godot e recortado por `main.py palco pecas-do-rosto` (máscara branca; o `eye_x` vem do rosto pronto `face_j`) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/shape-characters |

O resto da biblioteca (lutador, armas, arena, HUD, os objetos sem arte e os
extras do rosto: espiral, boca ondulada, gota, lágrima, veia) é desenho
vetorial em GDScript feito no repositório. As 24 expressões são as de
`neural_fights/effects/character_flair.py`, montadas com as peças acima
(`lutadores/rosto.gd`).

Peça nova de IA (PicassoIA, 16F) entra aqui com a prova de origem
(conta compartilhada: histórico com o nosso prompt).

<!-- efeitos_cc0:inicio (gerado por main.py palco efeitos-cc0) -->

Efeitos por tipo x elemento (16E):

| arquivo no palco | origem | autor | licença | prova |
|---|---|---|---|---|
| `efeitos/texturas/fogo.png` | Particle Pack v1.1, `fire_01.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/estrela_4.png` | Particle Pack v1.1, `star_07.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/bola.png` | Particle Pack v1.1, `circle_05.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/raio.png` | Particle Pack v1.1, `spark_01.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/magia_estrela.png` | Particle Pack v1.1, `magic_05.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/magia_anel.png` | Particle Pack v1.1, `magic_03.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/magia_pontos.png` | Particle Pack v1.1, `magic_02.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/terra.png` | Particle Pack v1.1, `dirt_01.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/giro_1.png` | Particle Pack v1.1, `twirl_01.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/giro_2.png` | Particle Pack v1.1, `twirl_02.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/giro_3.png` | Particle Pack v1.1, `twirl_03.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/arranhao.png` | Particle Pack v1.1, `scratch_01.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/aro.png` | Particle Pack v1.1, `circle_04.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/estrelinha.png` | Particle Pack v1.1, `star_04.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/luz_aneis.png` | Particle Pack v1.1, `light_03.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/fumaca_anel.png` | Particle Pack v1.1, `smoke_10.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/raio_linha.png` | Particle Pack v1.1, `spark_07.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/particle-pack |
| `efeitos/texturas/flor.png` | Light Masks v1.0, `shape_g.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/aneis_a.png` | Light Masks v1.0, `circle_rings_a.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/aneis_c.png` | Light Masks v1.0, `circle_rings_c.png` (256 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/aneis_d.png` | Light Masks v1.0, `circle_rings_d.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/gelo_rachado.png` | Light Masks v1.0, `water_caustics_b.png` (recortado num disco) (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/aro_fino.png` | Light Masks v1.0, `ring_a.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/aro_duplo.png` | Light Masks v1.0, `ring_b.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/folhagem.png` | Light Masks v1.0, `foliage_canopy_d.png` (recortado num disco) (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/feixe_a.png` | Light Masks v1.0, `streaks_composed_a.png` (deitado em +x) (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/feixe_d.png` | Light Masks v1.0, `streaks_composed_d.png` (deitado em +x) (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/light-masks |
| `efeitos/texturas/circulo_arcano.png` | 4 Summoning Circles, `circle6.png` (1000 -> 512, traco preto -> mascara) (512 px) | Luke.RUSTLTD | CC0 | opengameart.org/content/4-summoning-circles |
| `efeitos/texturas/circulo_tempo.png` | 4 Summoning Circles, `circle4.png` (1000 -> 512, traco preto -> mascara) (512 px) | Luke.RUSTLTD | CC0 | opengameart.org/content/4-summoning-circles |
| `efeitos/texturas/mancha.png` | Splat Pack v1.0, `splat03.png` (512 px) | Kenney | CC0 | `License.txt` do zip; kenney.nl/assets/splat-pack |

<!-- efeitos_cc0:fim -->
