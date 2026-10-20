# Semana 1 do plano: o duelo em inglês, com o confronto (a partir de 20/10/2026)

Decisões: `geral/canal-em-ingles` ("só o que o público vê em inglês": título, legenda, texto na
tela, voz, idioma do upload; código, docs e app seguem em português) e `geral/objetivo-unico-neural-fights`.
Pesquisa: `docs/pesquisa/shorts-que-deram-certo.md` §2 e §6 (recomendações 1 e 4 — "só texto,
sem mexer no motor").

| Item do plano | Onde mexer | Como provar |
|---|---|---|
| Título "Sword VS Dagger — who wins?" | `config/publicacao.json → titulos.duelo` + campos em `catalogo._campos_duelo` + `rodizio.titulo_do_par` (os três juntos) | `python main.py publicar` lista o título; medir quantos títulos distintos o modelo gera (36 pares só por tipo!) |
| Descrição repete a pergunta; hashtags em inglês | `descricoes.duelo`, `hashtags.duelo` (hoje `#luta #ia` etc.) | idem |
| Faixa fixa no topo com o confronto, cada lado na cor do lutador | `builds/video/renderer.py` (`_layout_do_topo`; o HUD já pinta cada nome na cor do lutador — medido no `duelo_00141`; no palco Godot o campo é `cor_nome`) | quadros 0 s e ½ com a zona pintada; nada nos 10% de cima |
| Pergunta escrita no 1º segundo | renderer (sobreposição dos primeiros quadros; a identidade de 1,5 s já ocupa a faixa logo abaixo do HUD) | `medir_video.py --tempos 0,0.5,1` |
| Luta já no quadro 0 | o duelo já começa na arena (medido: `duelo_00141` quadro 0 com os dois lutadores) | quadro 0 |
| Texto da tela em inglês | rótulos do plano (`neural_fights/ai/plano_de_luta.py`), callouts e K.O. (`config/editing.json`), identidade/veredito (`renderer.py`) | ler TODOS os quadros da folha; zero português |
| Voz/pergunta falada (opcional) | skill `builds-voz-do-duelo` | `conferir_fala.py` sai 0 |
| Idioma do upload na API | o YouTube sobe pelo navegador (`publicar/youtube_web.py`, modo `navegador`); não há `defaultLanguage` no código hoje | é da parte publicação — peça a ela |

Cuidados:
- Texto mais largo muda caixas medidas: o letreiro do K.O. (`runner.reserva_do_letreiro`) e o
  HUD (`hud_do_topo`) alimentam a câmera da cauda. Rode `test_letreiro_do_ko_regressions.py` e
  `test_hud_zona_segura_regressions.py`.
- `voz.falavel` e as legendas da roleta são pt-BR (roleta: `config/frases.json`, `captions.json`);
  o plano é do duelo — a roleta segue na cota até a publicação mudar.
- Duelos JÁ renderizados (28 no estoque em 20/10) saem com a tela antiga: re-render com
  `--rerender <id> --refazer-edicao` (sem re-simular), ou a semana mistura vídeo velho e novo e a
  medida não separa. Decida e anote a data em que o primeiro duelo novo foi ao ar.
