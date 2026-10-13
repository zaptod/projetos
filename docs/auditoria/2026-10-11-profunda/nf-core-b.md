# Auditoria profunda — Motor: arena, skills, corrente e o resto do core (nf-core-b)

Data: 2026-10-13. Fatia: `neural_fights/core/*.py` EXCETO `entities.py`, `combat.py` e `hitbox.py`.
Só relatório; nenhum código do projeto foi alterado. Provas em `%TEMP%\claude\...\scratchpad\prova_core_b.py`
(rodada de `E:\projetos`, sem rede, sem Godot, nada gravado em `outputs/`). Testes de base
`tests/test_generator_determinism.py` e `tests/test_catalog_reachability.py`: 6 passed.

## Examinado (11 arquivos, 180 funções — cada arquivo lido inteiro, função por função)

| Arquivo | Linhas | Funções | O que faz |
|---|---|---|---|
| `core/__init__.py` | 69 | 2 | exports lazy (`__getattr__`/`__dir__`) |
| `core/physics.py` | 132 | 9 | geometria (linha×círculo, linha×linha, ângulo) |
| `core/match_series.py` | 66 | 6 | `BestOfSeries` (estado puro do melhor-de-N) |
| `core/agarrao.py` | 296 | 15 | iniciativa, pesos, desfecho do agarrão; enlace da corrente leve |
| `core/status_runtime.py` | 357 | 13 | catálogo canônico de status, `StatusTimers`, aliases |
| `core/arena.py` | 1.476 | 23 | 20 arenas, limites/colisão, obstáculos destrutíveis, desenho |
| `core/corrente.py` | 582 | 28 | Corrente V2: bola física em subpassos, acerto por trilha, alcances |
| `core/skills.py` | 878 | 7 | `SKILL_DB` (118 skills) + escala ×2 no import + consultas |
| `core/skill_contract.py` | 519 | 15 | `SkillContract` derivado (geometria, efeito, custos, consequências) |
| `core/weapon_analysis.py` | 536 | 15 | perfis de arma para a IA (alcance, ameaça, matchup) |
| `core/game_feel.py` | 1.319 | 47 | hit stop, super armor, channeling, camera feel, `GameFeelManager` |

Perguntas feitas a cada função: `random` global / `time` / ordem de dict; divisão por zero; índice fora;
estado que sobrevive entre lutas no processo; contrato × implementação; pool com skill inexistente;
corrente que explode ou nunca solta; game_feel que muda o resultado; `None` em campo opcional;
função pública sem chamador.

### O que está certo (e vale registrar)
- **Determinismo do motor:** `agarrao.py` e `corrente.py` não tocam `random`; todo sorteio usa `rng_runtime`.
  `sortear_desfecho` itera dict literal (ordem estável). `corrente.atualizar_bola` é puro em float, subpasso fixo
  1/120 s, restrição inextensível — a bola **nunca** passa de `comp` da mão e **sempre solta** (não há estado
  "preso" fora do Simulador). `random` global aparece só em VFX (`CameraFeel.update`, partículas do Simulador)
  e no fallback de `ChannelingSystem.interromper` (código morto, ver C8).
- **Hit stop faz parte da simulação, de forma consistente:** `Simulador._processar_hit_stop` pula o resto do
  passo quando `GameFeelManager.update` devolve 0; é determinístico (gate por `HITSTOP_DANO_MIN_PCT`, sem RNG)
  e roda igual em headless e com tela, então não quebra a invariância a VFX.
- **Catálogo íntegro:** todas as skills de `KIT_POOLS` e `skills_afinidade` existem em `SKILL_DB`; todo
  `efeito`/`efeito2` está em `STATUS_RUNTIME` ou em `EFEITOS_TRATADOS_FORA_DO_STATUS`; todo `combo_apos`
  aponta para skill existente (P4).
- `Arena.__init__` copia os obstáculos por instância (`dataclasses.replace`), então quebrar um pilar não
  contamina o catálogo `ARENAS`. `BestOfSeries` e `StatusTimers` estão corretos (incl. `tick`/`modificador`
  com os dois chamadores reais em `entities.py` — `min` para dano causado, `max` para recebido).
- `custo_efetivo`/`cooldown_efetivo`/`custo_vida_do_cast` do contrato espelham `entities.usar_skill_*`
  (Mago ×0,8; `custo_vida` absoluto antes do percentual).

## Confirmados (do mais grave ao menos)

### C1 — Corrente V2: salto da mão (virada ou teleporte) vira velocidade da bola e passa a porta do acerto
- **Onde:** `neural_fights/core/corrente.py:388` (`vhx, vhy = (hx1-hx0)/dt`), `:445-446` (termo `-ARRASTO*rel`
  fora do clamp de `a_max`), `:459-466` (restrição inextensível transfere `v_r` relativo à mão para a bola),
  `:506-512` (`verificar_golpe` lê `bola.vx` absoluto).
- **O defeito:** a velocidade da mão é a diferença de posição entre ticks dividida por `dt`. Se a mão "pula"
  (o lutador virou 180° num tick, ou foi teleportado), `vh` vira centenas de m/s; a restrição e o arrasto
  injetam essa velocidade na bola num único passo, e `verificar_golpe` compara `v_rel` com `V_MIN_FRAC·v_ref`:
  uma bola que estava lenta demais para valer golpe passa a valer com `mult` no teto (1,4).
- **Quando acontece:** durante a fase de golpe (`atacando` + janela), quando (a) o inimigo lança
  `Troca de Almas` (`entities._trocar_posicoes` troca `pos` na hora), (b) o próprio lutador usa dash-skill de
  teleporte (`Portal Sombrio` 8 m, `Portal Arcano` 10 m, `Passo do Vazio`, `Teleporte Relâmpago`), (c) o
  Simulador fixa `angulo_olhar` de ambos no início do agarrão (`simulacao.py:3397-3398`) ou o brain restaura
  o olhar após um dash de desvio (`brain.py:1738-1744`). No giro normal o olhar é suavizado
  (`entities.py:2179`), então não dispara.
- **Prova (P3):** golpe de Mangual no meio da fase de golpe, `v_bola = 45,8 m/s`; virada de 180° num tick →
  `104,2 m/s`; teleporte de 8 m → `470,4 m/s` (`v_ref = 27,6`; teto do multiplicador em 32,6 m/s).
- **Conserto sugerido:** em `atualizar_bola`, limitar a velocidade da mão a um teto físico
  (ex.: `|vh| ≤ 3·velocidade_nominal`) ou, quando `hypot(hx1-hx0, hy1-hy0) > raio` num tick, tratar como
  teleporte: transladar a bola junto (`bola.x += hx1-hx0`) e zerar `vh`. Teste: o P3 com `assert v1 < 2·v0`.

### C2 — `weapon_analysis`: cache global por `(nome, tipo)` entrega o perfil de OUTRA arma e sobrevive entre lutas
- **Onde:** `neural_fights/core/weapon_analysis.py:202-204` (chave `f"{arma.nome}_{arma.tipo}"`), `:265`
  (grava), `:516` (`analisador_armas = WeaponAnalyzer()` global, nunca limpo).
- **O defeito:** o perfil (alcance, zona morta, velocidade, tempos) depende de `comp_lamina`, `peso` etc.,
  mas a chave do cache ignora tudo isso. Duas armas de mesmo nome e tipo com medidas diferentes recebem o
  mesmo perfil — e qual delas "ganha" depende da ORDEM em que o processo as viu. A percepção da IA
  (`brain.py:2638-2742`: `distancia_segura`, `distancia_ataque`, `estrategia_recomendada`) passa a depender
  do histórico do processo, não da semente.
- **Quando acontece:** hoje o banco não tem par repetido (155 armas, 0 duplicatas; o exportador garante
  `_nome_unico`), então a exposição real é: (1) editar medidas/peso de uma arma no painel sem reiniciar o
  processo (a IA continua com o perfil velho); (2) qualquer ferramenta/teste que monte armas com
  `SimpleNamespace` de nome repetido; (3) renomear-e-recriar no mesmo processo.
- **Prova (P1):** `Espada Longa` (lâmina 60, peso 2) → alcance 2,0 / vel 0,564; a segunda `Espada Longa`
  (lâmina 170, peso 12) devolve o MESMO objeto (`p1 is p2 == True`), alcance 2,0 / vel 0,564, quando sozinha
  dá 5,0 / 0,384.
- **Conserto sugerido:** chave com as medidas que entram na conta (`nome, tipo, comp_cabo, comp_lamina,
  largura, peso, dano, comp_corrente, comp_ponta, ...`) ou `id(arma)`; e limpar `_cache_profiles` em
  `Simulador.recarregar_tudo`.

### C3 — `avaliar_posicao_combate`: "posso atacar" é julgado pelo ângulo do INIMIGO, não pelo meu
- **Onde:** `neural_fights/core/weapon_analysis.py:480-482` (usa `angulo_relativo` para o meu arco) e `:486`
  (`angulo_para_mim = (a+180)%360-180` é só normalização, não vira o ângulo).
- **O defeito:** `brain._calcular_estrategia_armas` (`brain.py:2724-2739`) passa `ang_relativo = (ângulo
  inimigo→eu) − olhar do inimigo`, ou seja, "onde eu estou no campo de visão DELE". A função usa esse mesmo
  número para decidir se o inimigo está no MEU arco de ataque. Resultado: atrás do inimigo e em alcance, a
  recomendação é "aproximar"; de frente para ele (onde ele me vê), "posso_atacar" dá True mesmo que eu esteja
  de costas.
- **Quando acontece:** toda luta, a cada reavaliação da percepção de armas (alimenta
  `estrategia_recomendada`).
- **Prova (P2):** `evaluate_combat_position(Reta, Reta, 1.5, 180.0)` → `posso_atacar=False`,
  `inimigo_pode_atacar=False`, `"aproximar"`; com `0.0` → `True, True, "esperar"`.
- **Conserto sugerido:** receber dois ângulos (o inimigo no meu olhar e eu no olhar dele) ou calcular o meu
  no brain e passar separado; `posso_atacar` usa o meu, `ameaca_inimigo` usa o dele.

### C4 — Super armor: QUEBRAR a armadura reduz mais o dano do que ela ativa (Cavaleiro e Paladino)
- **Onde:** `neural_fights/core/game_feel.py:592-594` (`return (dano_base * 0.5, ...)` ao quebrar) contra
  `:576` (`dano_final = dano_base * reducao`).
- **O defeito:** o golpe que quebra a armadura é devolvido com 50% de redução fixa. Para classes cuja
  armadura reduz menos que 50% (Cavaleiro 25%, Paladino 40%), o golpe que "rompe" a defesa dói MENOS que um
  golpe absorvido normalmente. Além disso `reset_armor` não tem chamador: quebrada, fica quebrada até o
  próximo `recarregar_tudo`. No Cavaleiro ("sempre_ativo") `verificar_ativacao` escreve `data.ativo` direto
  sem `_ativar_armor()`, então `dano_absorvido` nunca zera entre ativações: a armadura é um orçamento
  acumulado de `0,3·vida_max` para a luta inteira, não "por ativação" como no Berserker.
- **Quando acontece:** golpe melee (`simulacao.py:4243` → `processar_hit`) que cruza `limite_dano` com a
  armadura ativa.
- **Prova (P5):** Cavaleiro 1000 HP, `BLOQUEAR`: hit 100 → 75,0 (ativa); hit 1500 que quebra → 750,0
  (0,5×); depois `verificar_ativacao` devolve `ativo=False, quebrada=True` para sempre.
- **Conserto sugerido:** ao quebrar devolver `max(dano_base*reducao, dano_base*0.5)` ou simplesmente
  `dano_base` (sem redução, com stagger); chamar `reset_armor` em `recarregar_tudo`/início de round e em
  `_ativar_armor` do caminho "sempre_ativo".

### C5 — Contrato: BEAM canalizável declara `duracao = 0` (Chamas do Dragão, Desintegrar)
- **Onde:** `neural_fights/core/skill_contract.py:395-402` (lê `duracao_max` só quando `tipo == "CHANNEL"`).
- **O defeito:** `Chamas do Dragão` e `Desintegrar` são `BEAM` com `canalizavel=True` e `duracao_max=3.0`;
  o contrato sai com `canalizavel=True, duracao=0.0`. Quem lê o contrato (IA, inspetor, harness) vê uma
  canalização de zero segundos; `_dano_estimado` só acerta por coincidência (`duracao` padrão 3,0 == os 3,0
  do catálogo). A mesma linha cai em `_consequencias`, que marca "canalizacao" para BEAM canalizável — ou
  seja, o próprio módulo trata BEAM+canalizável como canalização, menos no campo `duracao`.
- **Prova (P4):** `Chamas do Dragão: canalizavel=True duracao=0.0`; `Desintegrar: canalizavel=True
  duracao=0.0`; `Transfusão (CHANNEL): duracao=3.0`.
- **Conserto sugerido:** `data.get("duracao_max") if (tipo == "CHANNEL" or canalizavel) else
  data.get("duracao")`.

### C6 — Hit stop: a fila SOMA durações; o comentário diz "usa o maior"
- **Onde:** `neural_fights/core/game_feel.py:355-360` e `:398-401`.
- **O defeito:** um golpe mais longo registrado durante um hit stop ativo entra na fila e só começa quando o
  atual acaba — o congelamento total é `d1 + d2`, não `max(d1, d2)`. Como o hit stop zera o `dt` da
  simulação (`_processar_hit_stop`), isso é tempo de luta congelado a mais, determinístico mas diferente do
  desenhado. Também: `GameFeelManager.reset` só reseta `HitStopManager` se havia instância do manager
  (`:1103`); `HitStopManager.get_instance()` chamado direto antes (tests/ferramentas) deixa fila e timer
  velhos para a luta seguinte.
- **Prova (P6):** `d1=0,023 s`, `d2=0,500 s`, congelamento medido `0,525 s` (máximo seria 0,500).
- **Conserto sugerido:** em `registrar_hit`, se já há evento ativo, `timer_ativo = max(timer_ativo,
  duracao)` e trocar `evento_atual` pelo mais forte, sem fila; `reset` sempre chamar `HitStopManager.reset()`.

### C7 — Arena: dano fracionário em obstáculo destrutível é descartado (no-op silencioso)
- **Onde:** `neural_fights/core/arena.py:657` (`int(obs.hp) - int(max(0.0, float(dano)))`).
- **O defeito:** `int()` trunca; dano < 1 nunca desgasta o obstáculo, e dano 1,9 vale 1. O `hp` do modelo é
  `int`, mas o chamador passa `float(area.dano)` (`simulacao.py:1613`). Hoje as áreas têm dano ≥ 10 depois
  da escala, então o efeito prático é só o arredondamento para baixo a cada golpe (perde até 0,99 por hit).
- **Prova (P8):** 50 golpes de 0,9 na caixa do Cyberpunk: hp 100 → 100.
- **Conserto sugerido:** manter `hp` em float (`obs.hp = float(obs.hp) - max(0.0, float(dano))`).

### C8 — `agarrao.aplicar_desfecho` (ESCAPE): `except TypeError` engole erro de DENTRO do dash e o chama de novo
- **Onde:** `neural_fights/core/agarrao.py:477-481`.
- **O defeito:** o `try/except TypeError` existe para tolerar assinaturas antigas de `iniciar_dash`, mas
  pega qualquer `TypeError` levantado dentro do dash (bug real) e re-executa o dash com outros argumentos —
  efeito colateral duplicado (gasto, timers) antes de o erro final subir. `Lutador.iniciar_dash(angulo,
  forca=16.0, ignorar_custo=False)` (`entities.py:655`) já aceita a assinatura nova; o fallback só esconde
  defeitos.
- **Prova (P9):** dash que levanta `TypeError` internamente é chamado DUAS vezes
  (`(ang, 18.0, True)` e `(ang, 18.0, False)`) e o erro sai na segunda.
- **Conserto sugerido:** remover o fallback (chamar só a assinatura atual) ou checar a assinatura com
  `inspect.signature` uma vez.

### C9 — Funções públicas sem chamador (código morto que mente sobre o jogo)
- `arena.esta_em_zona_perigo` (`arena.py:670`): lava/fogo do Vulcão e Inferno estão no catálogo como
  "Poças de lava (dano!)" e nunca causam dano — ninguém chama (prova P8 + grep: só a definição).
- `Arena.wall_sound_cooldown` (`arena.py:588, 699-700`): decrementado por frame, nunca preenchido; o
  Simulador tem o seu próprio `_wall_sound_cooldown` (`simulacao.py:2405-2444`). `Arena.efeitos_ativos`
  (`:591`): nunca lido. `Arena.esta_dentro` (`:900`): sem chamador fora do arquivo e sem o caso octógono
  que `ponto_dentro` trata.
- `game_feel.ChannelingSystem` inteiro + `GameFeelManager.iniciar_canalizacao`/`_processar_magia_liberada`
  (`game_feel.py:617-895, 1239-1265`): `Lutador.iniciar_canalizacao` (`entities.py:4339`) não tem
  chamador, logo o sistema nunca roda. Dentro dele há dois defeitos latentes: o estado `COOLDOWN` nunca
  expira (`update` não trata `COOLDOWN`, `pode_canalizar` fica False para sempre — prova P7: 10 s depois,
  `pode_canalizar=False, timer=2.0`), e `interromper` cai em `random` global quando o lutador não tem
  `rng_runtime` (`:834`). A canalização real do jogo é `channel_ativo` em `combat.py`/`entities.py`.
- `physics.angulo_entre_pontos`, `ponto_no_circulo`, `mover_ponto_direcao` (`physics.py:92-132`): sem
  chamador e fora do `__init__`.
- `weapon_analysis.calcular_angulo_ataque_ideal` (`weapon_analysis.py:439`): sem chamador; e a lógica
  devolve "pelas costas" para toda arma exceto Orbital (o primeiro ponto cego sempre tem arco ≥ 90).
- `skills.get_skills_by_*`, `listar_skills_para_ui`, `listar_elementos`, `contar_skills`: sem chamador no
  projeto (UI não as usa).
- 7 skills do catálogo sem NENHUMA fonte (pool, afinidade ou arma do banco): `Benção`, `Conjuração
  Perfeita`, `Cura Menor`, `Disparo de Mana`, `Escudo de Brasas`, `Estilhaço de Gelo`, `Purificar`
  (P4: 9 sem pool; dessas, `Chamas do Dragão` e `Roubar Magia` entram por arma). O contrato `fontes`
  ignora armas como origem, então diz "inalcançável" para duas skills que armas do banco usam.
- **Conserto sugerido:** apagar o morto ou ligar (lava → `tomar_dano` por tick no Simulador; `fontes` do
  contrato incluindo `arma:<nome>`); marcar as 7 skills como fora de jogo ou colocá-las num pool.

## Não confirmados (lidos, suspeitos, mas sem defeito provado ou de impacto só cosmético)

- **`arena.ponto_dentro` no octógono usa o círculo inscrito** (`arena.py:603-605`): o Dojo (22 m, corte
  de 4,4 m) tem o canto (3,3) jogável e `ponto_dentro` diz False (P8). O docstring assume a aproximação; o
  efeito é a IA (`ai/spatial.py`) evitar uma faixa de chão que existe. Design, não bug — mas a aproximação
  é grosseira (perde ~15% da área).
- **Octógono: cantos sem rebote** (`arena.py:753-784`): o lutador é empurrado de volta mas a velocidade não
  é refletida; fica "raspando" o canto frame a frame. Cosmético/física leve; não medido em luta.
- **`_aplicar_colisao_obstaculos` registra colisão fantasma** (`arena.py:848`): o `if impacto_max > 2` está
  dentro do laço, então um segundo obstáculo tocado sem impacto herda o impacto do primeiro. Só acontece com
  dois obstáculos sobrepostos no mesmo frame (nenhuma arena do catálogo tem). Alimenta apenas
  `colisoes_recentes` (VFX e sonda da timeline).
- **`time.time()` no desenho de lava/cristal/núcleo/console** (`arena.py:1110, 1121, 1202, 1314`): os
  quadros gravados não são reproduzíveis bit a bit entre duas gravações da mesma semente. Não toca a
  simulação (invariância preservada); só a imagem.
- **`skills.py` escala no import** (`:831-834`): um `importlib.reload` aplicaria ×2 de novo (×4). Só em
  testes/ferramentas; o jogo importa uma vez. `escudo` (25/50/40) ficou fora da escala pela mesma razão que
  curas entraram ("cosmético contra pool 2,8×") — inconsistência de balanceamento, não defeito.
- **`skill_contract`: `Troca de Almas` com `alcance_lancamento = 0`** (`:218-219` via `distancia: 0.0`):
  o runtime (`entities._executar_dash_skill` → `_trocar_posicoes`) não tem porta de distância própria —
  depende de `_resolver_alvo_troca`, que não li (fora da fatia). Se não houver porta, o contrato subestima
  o perigo da skill para a IA.
- **`SkillContract.chance_efeito` só cobre `chance_stun`**: o runtime lê `chance_stun` (`combat.py:1057,
  1265, 1366`) — coerente. OK.
- **`status_runtime.get_status_runtime` devolve cópia rasa**: o dict `visual` é compartilhado; um chamador
  que o mutar altera o catálogo. Nenhum chamador muta hoje.
- **`SuperArmorSystem.__init__` lê `lutador.vida_max`** sem `getattr`: só quebra com dublê sem o campo.
- **`CameraFeel.update` consome `random` global**: VFX; como o motor usa `rng_runtime`, não interfere na
  luta. Só vale lembrar se um dia algum código do motor voltar a usar `random` global.
- **`HitStopManager.registrar_hit` com `alvo=None`** (magia carregada) pula o gate por vida — caminho morto
  (vem de `_processar_magia_liberada`, ver C9).

## Como foi provado
`prova_core_b.py` (scratchpad), com `sys.path` apontando para `E:\projetos`, sem dublar nenhuma função sob
suspeita: P1/P2 com `SimpleNamespace` de armas sobre o `WeaponAnalyzer` real; P3 com os helpers de
`tests/test_corrente_v2_regressions.py` e `corrente.atualizar_bola` real; P4 lendo `SKILL_DB`, `KIT_POOLS`,
`CLASSES_DATA`, `catalogo_de_contratos()` e o banco (`database.carregar_database()`); P5–P7 com as classes
reais de `game_feel`; P8 com `Arena(ARENAS[...])`; P9 com `agarrao.aplicar_desfecho` real.
