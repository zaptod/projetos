---
name: visual-serie-bluelock
description: Caderno de técnicas visuais e de retenção para a série vertical "Como eu criei um Blue Lock" (60-80 s, pt-BR, HyperFrames + GSAP, gravações do simulador de futebol). Use ao planejar ou revisar a CAMADA VISUAL de um episódio - diagramas animados, seta que se desenha, cone, trajetória, contador, comparação, interrupção de padrão, laço aberto, reengate a cada 2-4 s, pico de imagem nos pontos de queda. Escrita pela casa, nas nossas palavras, juntando as skills visual-* instaladas.
---

# Visual da série Blue Lock

Pedido do Adrian (26/10): **"o que mais prende são as representações visuais, sejam do próprio jogo ou de diagramas; use e abuse disso."** Esta skill é o mapa: qual técnica usar, quando, e em qual skill ler os detalhes. Ela não substitui `hyperframes-core`, `hyperframes-keyframes` e `hyperframes-direcao` (contrato, GSAP e direção da casa); soma o que faltava.

Fontes (todas MIT, só o texto): `visual-retencao-vertical`, `visual-diagramas-animados`, `visual-explicador-roteiro-tela`, `visual-svg-desenho-e-trajetoria`, `visual-gsap-plugins`, `visual-principios-de-movimento`, `visual-graficos-animados`. Os números de benchmark delas (87% decidem em 3 s, etc.) vêm sem fonte: são hipótese, a medir com `metricas-*`.

## Regra zero: o render pula para qualquer quadro
No HyperFrames tudo é função do tempo de UMA timeline GSAP pausada. Nada de `requestAnimationFrame`, `performance.now`, transição CSS, `Math.random`, `setTimeout`. Contador: `gsap.to(o, {v: 82, onUpdate})`. Seta: `strokeDashoffset` de 1 a 0 com `pathLength="1"`. Os exemplos das skills `visual-*` mostram a técnica, não o código final.

## As 10 técnicas (use todas ao longo do episódio)

1. **Imagem do jogo no 1º quadro, texto-gancho já na tela.** O lance mais forte (gol, defesa, a falha da IA) abre o vídeo, sem fade de preto. O gancho é texto em quadro 0 porque 85% veem sem som. (`visual-retencao-vertical`, "Hook grammar".)
2. **Seta que se desenha no tempo da fala.** A palavra "passa" abre o traço do pé até o destino, a duração do traço é a da palavra. Largura grossa, cor fixa por significado. (`visual-svg-desenho-e-trajetoria`, "Stroke draw-on"; `visual-gsap-plugins`, DrawSVG.)
3. **Revelação em ordem: nós, arestas, rótulos; o ativo aceso e o resto a 35%.** Esquema da IA do jogador (ver bola, decidir, chutar) aparece um bloco por frase; o bloco falado fica aceso. Cada passo segura 0,5 a 1,5 s. (`visual-diagramas-animados`, "Core principle".)
4. **Cone de visão e raio de decisão sobre o lance.** Pausa curta (ou câmera lenta) na gravação, desenha o cone com `clip-path`/arco SVG que cresce, mostra quem está dentro. É a "telestration" do futebol: desenho por cima do lance, sempre ligado ao que a voz diz.
5. **Bola na trajetória com `MotionPath`.** A curva do chute é um path; um ponto (ou rastro) a percorre com `autoRotate`, e o tempo bate com o do vídeo gravado. (`visual-svg-desenho-e-trajetoria`, "Motion along a path".)
6. **Contador que sobe e comparação lado a lado.** "Antes 12% de gol, depois 41%": dois painéis, número que sobe com `easeOutCubic` e vira ao pousar no valor; só dado medido, nunca inventado. (`visual-graficos-animados`, "Counters" e "Labeling".)
7. **Linha do tempo de versões (v1, v2, v3).** Régua horizontal que se desenha, marcador que anda e para em cada versão, com mini-clipe do jogo em cada parada. Dá a sensação de progresso e "falta ver o próximo". (`visual-diagramas-animados`, "Line chart draw-on".)
8. **Interrupção de padrão a cada 2-4 s, com intervalo desigual.** Punch-in 1,0 a 1,1x, corte para diagrama, tremida de câmera no impacto, pop de legenda, troca de ângulo. Nunca ampliar acima de 1,1x (regra do Adrian: regravar maior). (`visual-retencao-vertical`, "Pattern interrupts & cut rhythm".)
9. **Laço aberto no começo, fechado no fim, e fim que emenda no começo.** Abra uma pergunta nos 3 primeiros segundos ("por que ele não chuta?"), responda só no final e termine num quadro igual ao primeiro, para o replay ser invisível. (`visual-retencao-vertical`, "Loops & re-watch"; `visual-explicador-roteiro-tela`, "Story structure".)
10. **Movimento com peso: easing por intenção, antecipação, overshoot.** Chute: recua um pouco antes (antecipação), seta sai rápida e freia (`power3.out`), número passa 5% do valor e assenta (`back.out(1.4)`), impacto com tremida curta (`CustomWiggle`). Movimento linear parece gerado. (`visual-principios-de-movimento`, "Easing is the single biggest lever".)

Extras que cabem: `Flip` para o placar/ranking trocar de posição sem salto; `SplitText` para legenda palavra por palavra; barra de progresso do vídeo no rodapé (reengate visual, fora da zona das plataformas).

## Visual lidera, voz confirma (tempo certo por tipo de elemento)
Do método de b-roll de fala da iart (`talking-head-b-roll`, só lido): decida o tempo POR ELEMENTO, não uma vez para tudo.
- **Contexto que o olho prepara** (eixo, quadro do diagrama, cone): entra ~6 quadros (0,2 s) ANTES da palavra.
- **Fato novo** (número, nome, resultado): pousa EXATAMENTE na palavra.
- **Piada, negação, resposta guardada:** só aparece depois da palavra que revela. Nunca antes, ou a graça morre.
Isto casa com a regra do Adrian de que roteiro e voz vão a ele antes do render: o mapa "frase -> imagem -> tempo" entra no roteiro.

## Uma cena = um quadro de storyboard
Para cada frase do roteiro anote: **frase | imagem (jogo ou diagrama) | técnica nº | entra | sai**. Sem imagem para a frase = a frase está fraca ou é preciso cortar. Ritmo: no problema, cortes rápidos; no "como funciona", o mais lento, uma ideia por vez; no final, segure.

## Retenção: onde pôr o pico
- Se a curva do episódio anterior cai num ponto, o **pico de imagem** (a técnica 1, 4 ou 5 mais forte) vai ~1 s ANTES dele, não depois.
- Depois de um trecho de diagrama (mais calmo), volte ao jogo em ação.
- Uma ideia por vídeo; a segunda ideia vira outro episódio.
- Zonas das plataformas: topo 10%, rodapé 20%, direita 12% ficam livres de texto e rosto (ver `conferente-video-mp4`).

## Tom (regras do Adrian, `serie-blue-lock-*`)
Sem falar de IA de desenvolvimento, nada técnico de código/GitHub/local do projeto, piada e pergunta ao público, qualidade antes de volume. Diagrama mostra a IDEIA do jogador (ver, decidir, agir), não o código.

## Lacunas
Não achei skill séria de análise tática de futebol em vídeo; as técnicas 4, 5 e 7 vêm da prática de telestration e dos mecanismos de desenho/trajetória das skills de SVG e GSAP. Manim e Remotion não foram instalados (o render é o HyperFrames).
