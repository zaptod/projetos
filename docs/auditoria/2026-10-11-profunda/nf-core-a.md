# Auditoria profunda — Motor: entidades, combate e hitbox (nf-core-a)

Data: 2026-10-13. Escopo: `neural_fights/core/entities.py`, `neural_fights/core/combat.py`, `neural_fights/core/hitbox.py`. Só relatório; nenhum código do projeto foi alterado.

Método: os três arquivos lidos inteiros, função por função; chamadores conferidos em `simulation/simulacao.py`, `core/skills.py`, `models/constants.py`, `core/status_runtime.py`, `utils/config.py` e `ai/brain.py`. Provas rodadas em `C:\Users\adrian\AppData\Local\Temp\claude\...\scratchpad\prova_nf_core.py` (fora do repositório), com lutadores montados como em `tests/test_runtime_combat_contracts.py` (`SimpleNamespace` + `AIBrain` dublado) e RNG fixo injetado em `rng_runtime`; nenhuma função sob suspeita foi dublada.

## Examinado

| Arquivo | Linhas | Funções/métodos lidos |
|---|---|---|
| `neural_fights/core/entities.py` | 4.415 | 127 (`ImpactResult`, `DamageContext`, `_StatusTimerAttr`, `Lutador` com 120 métodos) |
| `neural_fights/core/combat.py` | 2.466 | 69 (funções soltas + `ArmaProjetil`, `FlechaProjetil`, `OrbeMagico`, `Projetil`, `AreaEffect`, `Beam`, `Buff`, `DotEffect`, `Summon`, `Trap`, `Transform`, `Channel`, `PortalPair`) |
| `neural_fights/core/hitbox.py` | 1.056 | 31 (`HitboxInfo`, `SistemaHitbox`, funções de módulo) |

Total: 7.937 linhas, 227 funções.

## Confirmados (do mais grave ao menos)

### 1. Canal "Chamas do Dragão" reaplica o DoT a cada tick de 0,1 s — 30 queimaduras empilhadas, +92% de dano escondido

- **Onde:** `neural_fights/core/combat.py:2295-2305` (`Channel._processar_tick` passa `self.tipo_efeito` em cada tick) → `neural_fights/core/entities.py:3830-3837` (`tomar_dano` chama `_aplicar_efeito_status` em todo impacto) → `entities.py:3932-3941` (`QUEIMANDO` faz `dots_ativos.append` de um `DotEffect` novo, sem renovar).
- **O defeito:** `_aplicar_efeito_status` empilha ENVENENADO/SANGRANDO/QUEIMANDO sem limite (só CORROENDO/NECROSE/MALDITO passam por `_renovar_dot`). Uma canalização com `efeito` de DoT vira um gerador de DoTs: 10 por segundo. A `AreaEffect` já se protege disso (`dot_tick` sai com `"tipo": "NORMAL"`, `combat.py:1210`); o `Channel` não.
- **Quando acontece:** toda vez que um Piromante canaliza Chamas do Dragão (`skills.py:63-68`: BEAM canalizável, `efeito: QUEIMANDO`, `tick_interval` padrão 0,1 s) sobre um alvo no cone de 15°. Único CHANNEL do catálogo com efeito de DoT; Transfusão/Desintegrar/Fúria do Trovão/Fotossíntese não têm `efeito`.
- **Prova (P1):** canal de 3 s a 3 m, alvo parado: dano direto 204,0; ao fim do canal o alvo tinha **30 `DotEffect` QUEIMANDO** ativos; deixando-os expirar, mais **187,5** de dano (92% do direto), invisível no número do canal e fora do orçamento de balanceamento da skill.
- **Conserto sugerido:** no `Channel._processar_tick`, enviar `tipo_efeito` só no primeiro tick (ou a cada N s) e `"NORMAL"` nos demais, como a AREA faz; ou, mais robusto, fazer ENVENENADO/SANGRANDO/QUEIMANDO passarem por `_renovar_dot` em `_aplicar_efeito_status` (hoje a política de empilhar vs renovar é inconsistente dentro da mesma função).

### 2. Eco do Feiticeiro (22%) com "Troca de Almas" troca duas vezes — a skill não faz nada e ainda cobra 40 de mana e 30 s de cooldown

- **Onde:** `neural_fights/core/entities.py:1812-1818` (eco chama `usar_skill_classe(..., _eco_caos=True)` antes do cast principal) → `entities.py:1413-1414` e `1346-1353` (`_trocar_posicoes` é um swap puro, aplicado duas vezes).
- **O defeito:** o eco repete o despacho inteiro. Para skills idempotentes-aditivas (projétil, área) isso dobra o efeito, que é a intenção. Para `TROCAR_POS` o segundo swap desfaz o primeiro.
- **Quando acontece:** Feiticeiro (Caos) é a ÚNICA classe cujo pool de MOBILIDADE é `["Troca de Almas"]` (`models/constants.py:541-544`, e kit fixo em `:806`). Em 22% dos casts dessa skill o lutador paga e fica onde está. Para a IA (que usa a skill como escape/engage) é um "dash" que falha silenciosamente.
- **Prova (P2):** com `rng_runtime.random()` fixo em 0,99 (sem eco): p1 (0,0)→(6,0), p2 (6,0)→(0,0). Com 0,10 (eco): p1 (0,0)→(0,0), p2 (6,0)→(6,0); `retorno=True`, mana gasta 40, `cd=30.0` nos dois casos.
- **Conserto sugerido:** excluir do eco os efeitos não-aditivos (`efeito == "TROCAR_POS"`, e provavelmente `tipo in ("DASH", "TRANSFORM", "CHANNEL")`, onde o eco só dobra distância ou se auto-interrompe), ou rolar o eco só para PROJETIL/AREA/BEAM/SUMMON.

### 3. Fontes contínuas (contato de transformação, ticks de canal) cobram a guarda por FRAME/TICK, não por golpe: a guarda quebra em 0,12 s e o contador `bloqueios` infla

- **Onde:** `neural_fights/core/entities.py:3337-3405` (`tomar_dano` → `_avaliar_bloqueio` + `CUSTO_ESTAMINA_BLOQUEIO` em TODO impacto que chega ali) com `combat.py:2154-2166` (`Transform.atualizar` emite um `"contato"` por frame com `fonte_impacto=object()`) e `combat.py:2287-2305` (`Channel` emite um impacto por tick de 0,1 s). O simulador manda cada um por `tomar_dano` (`simulacao.py:2106-2116`).
- **O defeito:** o custo da guarda (15 de estamina, `config.py:16`) é cobrado por impacto lógico, e a granularidade de uma fonte contínua é o passo da simulação, não um golpe. Um projétil de 120 custa 15; um toque de Forma Relâmpago (20 dps ⇒ 0,33 por frame) custa 15 por frame = 900/s. A guarda, que a Onda 8B fez virar "quebra-combo universal", é inútil contra qualquer fonte contínua — e a vítima fica sem fôlego para dash/burst em seguida. De quebra, `contadores_luta["bloqueios"]` (lido pela qualidade de luta) conta 7 "bloqueios" num décimo de segundo, e `brain.raiva += 0.2` (`entities.py:3622`) dispara por frame.
- **Quando acontece:** Forma Relâmpago (`dano_contato` 20), Forma Sanguinária (7), Barreira de Espinhos / Muro Ardente (`dano_contato` 8/10, por frame em `simulacao.py:2060-2079`), qualquer CHANNEL com `dano_por_segundo` (Chamas do Dragão, Desintegrar, Transfusão, Fúria do Trovão) e ticks de AREA (`dot_tick`, a cada 0,5 s). Precisa que a vítima esteja em BLOQUEAR olhando para o atacante — exatamente a resposta que a IA defensiva toma.
- **Prova (P3):** Forma Relâmpago encostada 1 s em alvo de guarda erguida: estamina 100 → **0,0 em 7 frames**, `bloqueios=7`, dano sofrido 37,0 (depois da quebra passa inteiro), `brain.raiva` = **12,0** (sem teto). Fúria do Trovão (20 dps) a 3 m: guarda quebrada em **0,6 s**, 69,5 de vida perdida em 2,5 s. Referência: um projétil de 120 bloqueado custou 15 e tirou 42,0.
- **Conserto sugerido:** cobrar a guarda proporcional ao dano bloqueado (ou uma vez por fonte por janela, usando `_fontes_impacto_recentes`/chave da fonte-mãe em vez de `object()` por frame), e não incrementar `bloqueios`/`raiva` para `tipo_fonte` contínua (`transform_skill`, `trap_skill`, `channel_skill`, `dot_tick`). Mesmo tratamento para o `+0.2` de raiva, que hoje não tem teto nem decaimento em `brain.py`.

### 4. `cooldown_ataque` congela enquanto o lutador está atordoado/dormindo/canalizando/agarrado

- **Onde:** `neural_fights/core/entities.py:2566` é o único decremento de `cooldown_ataque`, dentro de `executar_ataques`, que só roda quando `pode_iniciar_acao()` (`:2558`) e, em `update`, só sob `stun_timer <= 0` (`:2195-2209`).
- **O defeito:** o relógio de cadência só anda quando o corpo pode agir. Quem leva hitstun/parry/stun sai do controle com a MESMA cadência pendente de antes: o stun de 0,5 s do parry (`STAGGER_PARRY_S`) soma-se aos 0,9 s de `cooldown_ataque` que o próprio parry impõe (`:3360`), em vez de correr em paralelo. Isso alonga toda punição em todo golpe que atordoa, escondido do balanceamento (HITSTUN_* e cadência foram tunados como se fossem independentes).
- **Quando acontece:** em todo hitstun (Onda 8H), parry, CONGELADO, TEMPO_PARADO, SONO, canalização, agarrão — ou seja, dezenas de vezes por luta.
- **Prova (P4):** `cooldown_ataque=0.5`, `stun_timer=1.0`, 60 chamadas de `update(1/60)`: `stun_timer=0.00`, **`cooldown_ataque=0.48`** (um único frame de decremento, o último). Dormindo 1 s: idem, 0,48.
- **Conserto sugerido:** decrementar `cooldown_ataque` em `update()` junto dos outros timers (ou decidir explicitamente que stun pausa a cadência e documentar isso nos knobs de HITSTUN).

### 5. Ladino em guarda paga a estamina do bloqueio e DEPOIS esquiva — e o bloqueio é contado

- **Onde:** `neural_fights/core/entities.py:3337-3405` (bloqueio: custo e contador) vem ANTES de `:3423-3439` (esquiva de 12% do Ladino).
- **O defeito:** ordem de resolução: a guarda é debitada e contabilizada num golpe que no fim "não acertou" (`bloqueado_por="esquiva"`). Além disso `_fontes_impacto_recentes[chave_fonte]` (`:3240`) já foi gravada, então nada é desfeito.
- **Quando acontece:** Ladino (12% dos golpes recebidos) com guarda erguida; sem Duelista atacando.
- **Prova (P5):** `rng=0.05`, guarda erguida: `resultado=esquiva`, `dano=0.0`, **estamina 100 → 85**, **`bloqueios=1`**, vida intacta.
- **Conserto sugerido:** mover o sorteio da esquiva para antes de `_avaliar_bloqueio` (junto da `_consumir_esquiva_prevista`, `:3285`), ou não cobrar/contar bloqueio quando o impacto termina negado.

### 6. `_aplicar_efeito_status` devolve "aplicado" para EMPURRAO/EXPLOSAO/DRENAR/PUXADO/VORTEX sem fazer nada

- **Onde:** `neural_fights/core/entities.py:4066-4070`, `4082-4086` (só setam `sendo_puxado`/`em_vortex`, que NINGUÉM lê — grep no pacote: zero leitores), `4127-4140` (`pass`) e `4212` (`return True`).
- **O defeito:** o retorno `True` vira `ImpactResult.efeito_aplicado=True` (`:3863-3868` e `:3277-3283`), `flash_timer` em impactos de dano zero (`:3281-3282`) e alimenta a sonda K1/K2 (`:3840-3849`) como se um status tivesse sido aplicado. O puxão real de PUXADO/VORTEX vive em `tomar_dano` (`:3679-3689`), não aqui.
- **Quando acontece:** toda explosão/empurrão/vórtice; em `status_stack` de áreas (`simulacao.py:861-876`) com esses efeitos o impacto de dano 0 conta como "efeito aplicado".
- **Prova (P6):** `resolver_impacto(0.0, ..., "EMPURRAO")` → `atingiu=True efeito_aplicado=True flash=0.15`; mesmo para EXPLOSAO/DRENAR/PUXADO/VORTEX; `NORMAL` → `efeito_aplicado=False flash=0.00`.
- **Conserto sugerido:** retornar `False` nesses ramos (e apagar `sendo_puxado`/`em_vortex`), deixando `efeito_aplicado` significar o que o nome diz.

### 7. `brain.raiva += 0.2` em `tomar_dano` sem teto (os outros 5 incrementos usam `min(1.0, ...)`) e sem decaimento no brain

- **Onde:** `neural_fights/core/entities.py:3622`; comparação: `ai/brain.py:2350, 3547, 5136, 5431` clampam em 1,0; não há decremento de `raiva` em `brain.py`.
- **O defeito:** com fontes contínuas (item 3) a raiva vai a 12+ num segundo; como não decai, qualquer limiar `raiva > 0.7` fica verdadeiro pelo resto da luta a partir do 4º impacto — o "estado emocional" deixa de ser estado.
- **Prova:** P3 (`raiva do brain=12.0` após 60 frames de contato).
- **Conserto sugerido:** `self.brain.raiva = min(1.0, self.brain.raiva + 0.2)` e não incrementar para `tipo_fonte` contínua.

## Não confirmados (lidos, com veredito)

- **Invencibilidade pós-impacto (0,3 s) é inócua.** `entities.py:3180-3198` só bloqueia a chave do MESMO golpe, que `_fontes_impacto_recentes` (`:3160`, janela de 1,0 s) já bloqueia antes. Prova P7: repetição da mesma chave sai como `fonte_duplicada`; golpe seguinte 0 s depois atinge com `invencivel_timer=0.30`; `anulados_invencibilidade` fica em 0. Não é defeito de jogo, mas o contador da qualidade de luta nunca sai do zero e o campo `_invencivel_chave` é código morto na prática.
- **Hitbox: sweet spot e zona morta nunca entram no dano.** `HitboxInfo.is_in_hitbox`/`get_damage_at_distance` (`hitbox.py:167-217`) não têm chamador; `verificar_colisao` devolve só `(bool, motivo)`. `_verificar_segunda_lamina` (`:832`) é inalcançável (a hitbox idle devolve "não está atacando" antes) e `_colisao_area` (`:904`) também (Mágica retorna em `:616`). Código morto, sem efeito em luta.
- **Hitbox: alcance da lâmina independe do comprimento da arma.** `hitbox.py:317-322`: `escala = alcance_alvo / tam_base` faz `cabo_px + lamina_px == raio_char * range_mult` sempre. Toda Reta alcança `tamanho` m; o gatilho de ataque em `entities.py:2652-2668` usa o comprimento real. Inconsistência de desenho, não acerta-nunca nem acerta-sempre (a hitbox é a mais generosa das duas).
- **Determinismo.** Nenhum uso de `random` global fora do default injetável; sets/dicts só com `id()` de objetos vivos ou iteração que não afeta resultado; `("fonte_id", id(x))` (`entities.py:3183`) só nasce no caminho do `Channel`, que ignora a recuperação. `OrbeMagico.atualizar` (`combat.py:357-363`) e `Beam._gerar_zigzag` (`:1420-1438`) gastam o RNG de gameplay com partículas/zigue-zague puramente visuais; hoje é reproduzível porque roda igual no headless, mas é o ponto onde um "pular VFX no headless" quebraria a invariância.
- **Divisão por zero.** `AreaEffect.atualizar` divide por `self.duracao` (`combat.py:1240`); só explodiria com `duracao: 0` sem `delay`, que não existe no catálogo. `_executar_skill` multi-shot divide por `multi-1` só com `multi > 1`. `alvo_cumpre_condicao` e `calcular_dano_ataque` protegem `vida_max`.
- **Índices.** `usar_skill_arma` aceita `skill_idx` negativo (`entities.py:1472`) e cai na última skill; `skill_idx` fora do intervalo cai silenciosamente na skill atual. Nenhum chamador passa índice ruim.
- **Ondas/meteoros com dt=1/60** (Wrath of Nature: 3 ondas, 2 emitidas, correto — P8).
- **Empate/KO no mesmo impacto.** Reflexo de dano mata o atacante depois de o defensor já ter morrido na mesma chamada (`entities.py:3479` antes de `:3509`); `morrer()` é idempotente e `morreu` fica correto — quem decide o empate é o simulador.
- **`morrer()` da passiva de morte** só é chamado por caminhos de dano (nenhum chamador do simulador para tempo esgotado/ring-out), então Último Suspiro/Ressurreição não revivem fora de hora; cooldowns 90/120 s limitam a um uso.
- **DoT dos encantamentos por projétil** (`entities.py:1177-1233`): cada faca de uma salva rola 50% e empilha um DoT próprio (3 venenos por salva de Arremesso). Mesma raiz do item 1 (empilhar vs renovar), mas aqui a documentação não diz qual era a intenção; fica como alerta.
- **Área sem delay nasce com `raio_atual = 0`** e cresce em 1/3 s (`combat.py:943, 1125-1129`); o simulador testa `raio_atual + raio_alvo` (`simulacao.py:2750`). Um alvo na borda que recua nos primeiros 0,3 s escapa — comportamento, não defeito.
