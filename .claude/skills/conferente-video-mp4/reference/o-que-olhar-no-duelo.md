# O que olhar num duelo (por quadro)

## Sempre
- **Quadro 0**: os dois lutadores JÁ na arena (padrão de 6/6 canais que cresceram: nada de logo
  ou apresentação). HUD com os dois nomes, cada um na cor do seu lutador.
- **Zona das plataformas** (`renderer.ZONA_DAS_PLATAFORMAS`, pintada de vermelho no `_zona.png`):
  nada que precise ser lido nos 10% de cima, nos 20% de baixo e nos 12% da direita — ali ficam
  as abas do TikTok/Shorts, a legenda, o canal e os botões. Medido em 18/10: HUD em y 209–324
  e x ≤ 912 (de 1080×1920).
- **Rosto do vencedor** fora da zona e acima de 62% da altura em todo quadro da cauda; nada
  desenhado sobre o rosto (confete, número flutuante, "FATAL!").
- **Veredito** (nome + "KO · 5V-0D") inteiro na faixa 62–76% da altura e ≤ 74% da largura.
- **Cauda pós-K.O.** (~2,7 s): o perdedor caído na cor dele, o vencedor pula e sai confete;
  nenhum projétil parado no ar; nenhum rótulo de plano ("ACABAR") depois do K.O.; o "ACABOU"
  não cobre o vencedor; a câmera não mostra fora da arena (> ~17% da largura).
- **Texto cortado**: nenhum nome/rótulo saindo da borda ou atrás de outro.

## Semana 1 do plano (inglês + confronto)
- Tudo o que o público lê e ouve em **inglês**: HUD ("PRESSÃO" vira o rótulo inglês), callouts
  ("VIROU!", "VEM DE 4 SEGUIDAS", "ACABOU"), identidade ("Necromante"), veredito, voz. Português
  em qualquer quadro = defeito (o código e os docs seguem em português, não a tela).
- **Faixa fixa no topo com o confronto** (cada lado na cor do lutador) visível no quadro 0 e na
  metade — quem chega no meio entende o que vê. Fora da zona dos 10%.
- **A pergunta** ("Who wins?") escrita (e/ou falada) dentro do 1º segundo: confira o quadro 0 e
  o de 1 s (`--tempos 0,0.5,1`).
- **Título do catálogo** com o confronto entendível por quem nunca viu o canal (não só os nomes
  inventados) — confira o texto, não o vídeo.

## Semana 2 (câmera parada, 35–50 s)
- Arena inteira no quadro em TODOS os quadros (hoje, na metade do duelo, a arena já saiu do
  quadro); duração 35–50 s; o número/regra que cresce visível e legível do começo ao fim.

## Quando a luta não devia mudar
Mesmo par e seed contra a base: vencedor, motivo, duração e `ko_em_clipe` do `fight.json`
iguais. Prova de 20/10 pelo caminho real (Gunnar Vexevok × Aurelia Argalacern, seed 4242,
Torre): 27,94 s, -15,6 LUFS, -1,8 dBTP — a base de 18/10 dava 27,93 s, -15,5 LUFS, -1,6 dBTP.
