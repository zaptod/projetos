# O motor de voz e o caminho da voz do Adrian (conferido em 20/10/2026)

## `random_builds/builds/content/voz.py`
| Peça | O que faz | Cuidado |
|---|---|---|
| `PADRAO` / `config(cfg)` | motor `edge`, voz `pt-BR-AntonioNeural`, taxa `+0%`, tom `+0Hz`, `voz_sapi` "Maria", `max_atempo` 1.1, `folga` 0.15 | `render.json → audio.voz` sobrepõe; o mesmo valor está nos dois de propósito (SCR-PT, 14/10) |
| `falavel(texto)` | texto de tela → texto falado (caixa alta vira frase, unidades viram palavra, emoji some, põe ponto final) | tabela `_SUBS` em **português** |
| `sintetizar(texto, cfg, cache, log)` | edge → se falhar, SAPI (ou o inverso se `motor: sapi`); cache por `sha1(motor|voz|taxa|tom|texto)` em `random_builds/outputs/_voz_cache/` | a queda para SAPI só vai ao `log` |
| `_edge` | grava `.parcial`, palavras (`.words.json`, `boundary="WordBoundary"`) ANTES do áudio, depois renomeia | é o que permite legenda karaokê com a hora de cada palavra |
| `motivo_do_cache_ruim` / `implausivel` | descarta entrada sem sidecar ou fora de 1,0–4,0 palavras/s (≥ 12 palavras) | a faixa foi medida em pt-BR |
| `medir(linhas)` | duração real de cada fala → a cena ESPERA a fala (`editing.json → narracao`) | |
| `montar` / `gerar(out_dir)` | `narration.json` → `voz.wav` + `voz.hash` (+ `voz_palavras.json`); fala longa acelera até `max_atempo` e, se não couber, corta com fade | nunca duas falas por cima |
| `respirar` + `_pausa_com_ar` + `_tirar_o_estalo` | varia pausas sem zerar o ar entre palavras (pipoco de 10/09: 333 → 33) | |

Quem chama: `builds/pipeline/controller.py` (`_medir_falas`, `_voz`) — só no caminho da roleta
(build). O duelo não passa por lá: frase no duelo é código novo no caminho do duelo, e o tempo
da frase tem de entrar ANTES do primeiro golpe importante (a luta começa no quadro 0).

Vozes que existem nesta máquina (medido): edge `en-US-GuyNeural`, `AndrewNeural`,
`BrianNeural`, `ChristopherNeural`, `EricNeural` (e as `Multilingual`); SAPI `Microsoft Zira`
e `Microsoft David` (en-US), `Microsoft Maria` (pt-BR).
Listar: `python -m edge_tts --list-voices` (precisa de rede).

## A voz do Adrian (semana 3) — o que já existe para o roteiro
`fight.json → luta.eventos_narrativos` já marca os momentos com o tempo do clipe:
`primeiro_sangue`, `wall_splat`, `desvio`, mudança de `plano` (com `rotulo`), virada, K.O.
(`ko_em_clipe`). É daí que sai o "roteiro de momentos" da pesquisa (§5): o app toca o vídeo sem
som com o roteiro por cima, ele grava assistindo, o sistema nivela, abaixa a música
(ducking) e legenda pela transcrição. Se ele não gravar até o horário, o vídeo sai sem voz.
Medida de sucesso (do plano): **inscritos por mil views**, narrados × não narrados (10 × 10).

## Conferir uma narração que já existe
```
python .claude/skills/builds-voz-do-duelo/scripts/conferir_fala.py --wav E:\projetos\random_builds\outputs\generation_00185\voz.wav
```
Medido em 20/10: 59,5 s, 1 pipoco (0,02/s) — normal. Uma narração com o defeito de 10/09 dava ~2,6/s.
