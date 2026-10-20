---
name: conferente-video-mp4
description: Conferir um mp4 de DUELO (ou build) do Neural Fights antes de ir ao Adrian ou ao ar — medir duração, resolução, som (LUFS, pico, silêncio, luta muda pela régua da publicação), imagem congelada, e OLHAR os quadros com a zona das plataformas pintada (topo 10%, baixo 20%, direita 12%). Use depois de toda entrega que gera ou muda vídeo (render, título na tela, HUD, câmera, voz, palco Godot) e para provar a mudança da semana do plano no próprio vídeo.
---

# Conferir um vídeo de duelo

**Teste verde não é prova; prova é o mp4 aberto e olhado.** Em 02/10 passaram, com "testes
verdes", uma Arena que não gerava vídeo e imagens quebradas. Em 14–15/10 o fim do duelo foi
reprovado 4 vezes só por imagem (confete no rosto, "ACABAR" depois do K.O., câmera fora da
arena, número sobre o olho) — os números de áudio batiam.

## Procedimento
1. **Medir e tirar os quadros** (só lê o mp4; capturas fora do repo):
   `python .claude/skills/conferente-video-mp4/scripts/medir_video.py <mp4> --saida E:\tmp_pytest\conferente\<tarefa>`
   Rode de `E:\projetos` (ou da pasta `random_builds` da worktree, se o vídeo é de lá).
   Gera `medida.json`, `quadro_<t>s.png` (0 s, 1 s, ¼, ½, ¾, fim−0,3 s), `quadro_*_zona.png` e
   `folha.png` (sobre fundo verde de contraste). `--tempos 0,0.5,1,25.2` para instantes exatos
   (o K.O. está em `fight.json → luta.ko_em_clipe`).
2. **OLHE** com Read: a `folha.png` e cada `_zona.png`. Pergunte "o que está errado aqui?",
   nunca "está certo?" (pergunta dirigida produz concordância).
3. **Compare com o que a entrega promete** e com a base (mesmo par/seed: ver
   `builds-render-duelo/reference/prova-pelo-caminho-real.md`) — critérios em
   [reference/o-que-olhar-no-duelo.md](reference/o-que-olhar-no-duelo.md).
4. Vídeo para julgar CONTEÚDO (a luta prende? a pergunta se entende?): peça ao orquestrador o
   parecer do Gemini com o mp4 — ele NÃO ouve; som é só do Adrian.
5. Devolva `APROVADO` (com o que conferiu e os caminhos) ou `DEFEITOS` numerados, do mais grave
   ao menos, cada um com o quadro (caminho + segundo), o número e a causa provável.

## Leitura do `medida.json`
| Campo | Bom | Barra / suspeito |
|---|---|---|
| `largura`×`altura`, `fps` | 1080×1920, 30 (celular) | outro tamanho no `final_celular.mp4` |
| `tem_audio`, `regua_da_publicacao` | `""` em `arquivo_inteiro` e `luta` | texto = a publicação barra; `None` = não mediu |
| `lufs_integrado` | ~-14 a -17 (alvo `loudnorm` -14; duelos medidos -15,5 a -16,8) | < -20 ou > -12 |
| `pico_verdadeiro_dbtp` | ≤ -1,0 | > -1,0 (teto de pico desde 14/10) |
| `silencio_final_s` | < 0,3 | > 0,9 (o defeito de 14/10) |
| `congelados_0.001_0.3s` | vazio, ou só a cauda pós-K.O. curta | congelado no meio da luta ou a cauda inteira parada |

## Armadilhas
- O ffmpeg fecha o último `silencedetect` no fim do arquivo: "tem silence_end" não quer dizer
  que acabou antes (o script já trata). `-ss` a 0,1 s do fim não devolve quadro (usa fim−0,3).
- Use `audio.medir` (sem memória); `audio.medir_lembrado`/`veredito` gravam em
  `%LOCALAPPDATA%\neural-fights\audio_medido.json`.
- Duelo da worktree não está no catálogo: o título que vai ao ar confira à parte
  (`python main.py publicar`, que só lista).
- Nada de reiniciar serviço nem commitar: isso é do orquestrador.
