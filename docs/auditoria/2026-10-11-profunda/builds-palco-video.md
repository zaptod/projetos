# Auditoria profunda — Palco, torneio e vídeo dos builds — 11/10/2026

## Examinado

- `random_builds/builds/__init__.py` — módulo vazio; contrato do pacote.
- `random_builds/builds/atividade.py` — funções/classes lidas; registra atividade da automação.
- `random_builds/builds/contas.py` — funções/classes lidas; localiza e administra o estado de contas/runtime.
- `random_builds/builds/experimentos.py` — funções/classes lidas; lê e calcula experimentos de builds.
- `random_builds/builds/grade.py` — funções/classes lidas; decide a grade e a seleção de publicações.
- `random_builds/builds/tarefas_windows.py` — funções/classes lidas; instala e consulta tarefas do Windows.
- `random_builds/builds/tempos.py` — funções/classes lidas; calcula janelas e datas de execução.
- `random_builds/builds/travas.py` — funções/classes lidas; coordena travas entre processos.
- `random_builds/builds/nf_bridge/cobertura.py` — funções/classes lidas; audita a cobertura do banco do jogo pela camada de vídeo.
- `random_builds/builds/nf_bridge/exporter.py` — funções/classes lidas; exporta dados do Neural Fights para builds.
- `random_builds/builds/nf_bridge/loader.py` — funções/classes lidas; carrega o motor e seus dados sem acoplamento no import.
- `random_builds/builds/nf_bridge/roulette_factory.py` — funções/classes lidas; constrói dados da roleta a partir do banco.
- `random_builds/builds/palco/__init__.py` — módulo/documentação pública do Palco.
- `random_builds/builds/palco/ab.py` — 4 funções; produz comparação A/B e extrai quadro de inspeção.
- `random_builds/builds/palco/checagens.py` — 9 funções; mede streams, áudio, loudness, quadros e validade do MP4.
- `random_builds/builds/palco/cli.py` — 11 funções; expõe render, validação, prévia e A/B em linha de comando.
- `random_builds/builds/palco/config.py` — 6 funções/classes; carrega configuração e resolve Godot, projeto e appdata.
- `random_builds/builds/palco/edicao.py` — funções/classes lidas; reaplica a edição do duelo sobre o vídeo do Palco e mede o resultado.
- `random_builds/builds/palco/fonte.py` — 3 funções; simula a timeline e calcula cortes de tédio.
- `random_builds/builds/palco/godot.py` — 9 funções; executa/importa Godot, prévia e Movie Maker.
- `random_builds/builds/palco/plano.py` — 10 funções; espelha a contagem, remapeamento e hitstop do Palco.
- `random_builds/builds/palco/previa_animacao.py` — 6 funções; seleciona lutadores e renderiza a prévia do Ateliê.
- `random_builds/builds/palco/producao.py` — funções/classes lidas; escolhe, confere e troca o celular de produção pelo Palco.
- `random_builds/builds/palco/prova_e3.py` — 2 funções; executa e identifica a prova determinística E3.
- `random_builds/builds/palco/render.py` — 3 funções; monta o job Godot, comprime e confere a saída.
- `random_builds/builds/palco/sintetica.py` — 2 funções; gera timeline sintética para teste.
- `random_builds/builds/palco/sons.py` — 5 funções; resolve arquivos e deriva a trilha de eventos.
- `random_builds/builds/tournament/__init__.py` — módulo vazio; contrato do pacote.
- `random_builds/builds/tournament/capture.py` — 2 funções; grava confrontos isolados e em paralelo.
- `random_builds/builds/tournament/duelo.py` — 7 funções/classes; constrói o plano compacto de duelo.
- `random_builds/builds/tournament/highlights.py` — 8 funções; planeja/remapeia cortes e extrai clipes.
- `random_builds/builds/tournament/runner.py` — funções/classes lidas; simula/grava confrontos e produz torneios, lutas e séries.
- `random_builds/builds/tournament/som_real.py` — 7 funções/classes; reanota e injeta som real em lutas já gravadas.
- `random_builds/builds/tournament/timeline.py` — funções/classes lidas; constrói planos de torneio e luta, HUD e callouts.
- `random_builds/builds/video/medidas.py` — 4 funções; valida duração, integridade e áudio de vídeo.
- `random_builds/builds/video/renderer.py` — funções/classes lidas; renderiza eventos, gameplay, sobreposições e mixagem final.
- `random_builds/builds/video/roleta_som.py` — funções/classes lidas; sintetiza efeitos sonoros da roleta e eventos.
- `random_builds/builds/video/som_da_luta.py` — funções/classes lidas; compõe os efeitos e o áudio da luta.
- `random_builds/builds/video/trilha.py` — funções/classes lidas; resolve e mistura música de fundo.
- `random_builds/builds/visualization/character_visualizer.py` — 2 funções; desenha card de personagem.
- `random_builds/builds/visualization/draw_common.py` — 7 funções; fornece fontes, gradientes, texto e barras PIL.
- `random_builds/builds/visualization/weapon_visualizer.py` — 2 funções; desenha card e glifo de arma.

## Confirmados (do mais grave ao menos)

### 1. Três empates consecutivos viram vitória inventada do primeiro lutador — gravidade: alta

- Onde: `random_builds/builds/tournament/runner.py:246` (`simular_luta`) e `random_builds/builds/tournament/runner.py:464` (`_evento_base`).

- O defeito: `simular_luta` tenta três seeds quando o motor empata, mas depois da terceira ainda devolve `vencedor=None`. `_evento_base` converte esse valor silenciosamente em `p1`; assim, o torneio/série registra uma vitória e elimina o outro participante embora nenhuma das três simulações tenha vencedor.

- Quando acontece: `run_headless_match` devolve três resultados válidos de empate/timeout para as seeds `base_seed`, `base_seed+1` e `base_seed+2` → o placar recebe vitória de `p1`, em vez de falhar ou de aplicar uma regra explícita de desempate.

- Prova: comando executado em processo Python isolado, substituindo apenas a dependência de motor para reproduzir três respostas de empate (sem dublar `simular_luta` nem `_evento_base):

  ```powershell
  $env:TEMP='E:\tmp_pytest'; python -c "from types import SimpleNamespace as S; from neural_fights.simulation import headless; from random_builds.builds.tournament import runner; chamadas=[]; headless.run_headless_match=lambda *a, **k: (chamadas.append(k['seed']) or S(success=True,winner=None,p1_hp_ratio=.4,p2_hp_ratio=.4,duration=120.0,reason='timeout',seed=k['seed'],error=None)); bruto=runner.simular_luta('A','B','Torre',700); evento=runner._evento_base('A','B',bruto,{},set(),'Torre'); print('seeds=',chamadas); print('bruto.vencedor=',bruto['vencedor']); print('evento.vencedor=',evento['vencedor'],'perdedor=',evento['perdedor'])"
  ```

  Saída: `seeds= [700, 701, 702]`, `bruto.vencedor= None`, `evento.vencedor= A perdedor= B`.

- Conserto sugerido: após esgotar as três tentativas sem vencedor, levantar erro (ou executar um desempate explicitamente registrado) antes de criar o evento.

## Não confirmados

- `tournament/highlights.py:extrair` — uma falha de ffmpeg em apenas uma parte pode levar a uma concatenação parcial; a leitura indica que a função continua com as partes restantes, mas não foi possível provocar uma falha parcial determinística sem corromper/criar mídia de teste fora do escopo. Não contado como confirmado.
- `palco/producao.py:_trocar_no_lugar` — a troca de segmentos remove a cópia anterior antes de mover a nova; há risco teórico se o processo morrer entre operações, mas não foi possível demonstrar perda com `os.replace` normal no mesmo volume. Não contado como confirmado.
