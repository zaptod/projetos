# Auditoria profunda — Motor: simulação — 11/10/2026

## Examinado

- `neural_fights/simulation/__init__.py` — 1 função lida; faz os reexports tardios do motor headless e visual.
- `neural_fights/simulation/headless.py` — 8 funções/métodos e 2 classes lidos; executa uma luta determinística sem janela e serializa o resultado.
- `neural_fights/simulation/layout.py` — 3 funções/propriedades e 1 classe lidas; calcula as âncoras de HUD para paisagem e retrato.
- `neural_fights/simulation/manual.py` — 20 funções/métodos e 1 classe lidos; implementa o campo de testes manual, menus e a ponte para o palco.
- `neural_fights/simulation/probes.py` — 14 funções/métodos e 2 classes lidos; coleta métricas passivas de qualidade, ritmo e variedade da luta.
- `neural_fights/simulation/simulacao.py` — 91 funções/métodos e 2 classes lidos; inicializa, avança, resolve e desenha a luta, incluindo VFX e encerramento dos singletons.
- `neural_fights/simulation/vfx_probe.py` — 8 funções/métodos e 1 classe lidos; conta VFX vivos por quadro e produz percentis do volume visual.
- `neural_fights/simulation/test_manual_palco_regressions.py` — 2 testes lidos; verifica a exportação manual da timeline contra a mesma fonte usada pelo palco.

## Confirmados (do mais grave ao menos)

Nenhum defeito confirmado nesta fatia.

## Não confirmados

- RNG global nos efeitos visuais, em `simulacao.py:786, 2470-2480, 2712-2715, 2904` e outros: é uma suspeita natural porque VFX sorteia partículas e o simulador também semeia `random`. Não se confirmou: uma execução real, sem dublar método algum, com a mesma seed, mesmos lutadores e 720 passos produziu exatamente o mesmo estado de combate em `headless=True` e `headless=False` (`(None, 604.6206, 694.3045, False)`). As decisões dos lutadores usam o `rng_runtime` próprio configurado em `simulacao.py:392-396`, separado do fluxo visual.
- Exportação do modo manual, em `manual.py:69-92`: a função re-simula a seed e a dupla inicial, portanto não serializa movimentos ou cheats aplicados durante a sessão manual. Não foi classificado como defeito: a ponte não possui formato de gravação de entradas e os testes/contrato a definem como a mesma simulação de produção por seed, não como replay de uma sessão controlada.
