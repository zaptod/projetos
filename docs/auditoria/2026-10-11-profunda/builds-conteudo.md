# Auditoria profunda — builds: conteúdo (arena, assets, character, content, editing, evaluation, generation)

Data: 12/10/2026. Fatia: `random_builds/builds/{arena,assets,character,content,editing,evaluation,generation}/**` (32 arquivos, 5.997 linhas, 171 funções/métodos, lidos inteiros). Já consertado e não repetido: ledger da arena sem trava (873f2e6).

Provas rodadas em `%TEMP%\claude\...\scratchpad\` (fora do repositório), com `LOCALAPPDATA` apontado para a pasta de prova, sem rede, sem navegador, sem escrita em `outputs/` nem em `%LOCALAPPDATA%\neural-fights`. Dados reais foram só LIDOS (`outputs/generation_*/evaluation.json`, `generation.json`, `fight.json`). Nenhuma função sob suspeita foi dublada.

## Examinado

| arquivo | funções | o que foi olhado |
|---|---|---|
| `arena/__init__.py` | 0 | docstring |
| `arena/ledger.py` | 12 | trava reentrante, releitura sob trava, arquivo corrompido, id idempotente, `escolher_adversario` com fichas sem `forca` |
| `arena/rodizio.py` | 10 | determinismo da fila, par ocupado nas duas ordens, `except Exception` em `titulos_ocupados`, custo O(n²) |
| `assets/selector.py` | 3 | fallback por categoria, `last_id`, cartão sintético |
| `assets/importer.py` | 7 | `_save_catalog` não atômico, `next_id`, ffprobe ausente |
| `assets/triagem.py` | 11 | trava de thread, desfazer, estado em `outputs/_triagem.json`, quem chama |
| `assets/catalog.py` | 8 | catálogo corrompido/entrada sem `file`, legado, pastas por categoria |
| `assets/reaction_cli.py` | 12 | menu interativo (EOF/Ctrl+C) |
| `character/character_builder.py` | 3 | escala das roletas (cm→m, x10), score sem rolagem pontuada |
| `character/moderacao.py` | 5 | normalização, leet, letras soltas, hífen/apóstrofo |
| `character/nomes.py` | 8 | `PROIBIDO_NO_FIM`, `termina_bem` (quem lê), sanitização do nome pedido, `@` |
| `character/lexico.py` | 20 | morfofonologia, pools com `NEUTRO`, `_montar` sem travar, `significado` (sem leitor) |
| `content/narration_generator.py` | 8 | fala por classe/tier, roleta-relâmpago muda, `None` em `final_score` |
| `content/caption_generator.py` | 32 | placeholders crus, `None` em `{VENCEDOR}`/`{PERDEDOR}`, `for_reveal`/`for_identity` (sem leitor) |
| `content/voz.py` | 27 | cache por hash e `.parcial`, dois processos, `implausivel`, assinatura do `voz.hash` |
| `editing/comentario.py` | 2 | troca de extensão, `presta` |
| `editing/editing_director.py` | 4 | orçamento, consecutivas, `events.index` |
| `editing/artifacts.py` | 7 | SRT (`1000 ms`), chave `(entity, index)` |
| `editing/timeline_builder.py` | 20 | `ajustar_ao_roteiro`, reação descartada por orçamento vs `decision["reaction"]`, badge, nameplate |
| `evaluation/surprise_engine.py` | 2 | sentido de `rarity` (1 = mais raro) |
| `evaluation/interest_engine.py` | 2 | `event["evaluation"]` |
| `evaluation/build_evaluator.py` | 3 | pesos vindos do config, `final_spread` |
| `evaluation/roll_evaluator.py` | 8 | `hi<=lo`, método desconhecido, `eval_min/eval_max` |
| `evaluation/synergy_engine.py` | 6 | unidades (kg, m, mana), `Mágica` com acento (confere com `LISTA_TIPOS_ARMA`), `SKILL_DB[...]["custo"]` existe nos 119 |
| `evaluation/reaction_classifier.py` | 7 | sentido de `rarity`, `funny` por score, precedência |
| `generation/random_engine.py` | 3 | fork por namespace, `new_seed` |
| `generation/validation_engine.py` | 2 | `validations` (vazio no config real) |
| `generation/probability_engine.py` | 8 | `rarity` categórica/numérica, pesos zero, `custom_curve` |
| `generation/rule_engine.py` | 5 | `in` com `value` None, ações desconhecidas |
| `generation/session_generator.py` | 3 | determinismo com nome pedido/escolhas, chaves `nome_pedido`/`escolhas` |
| `generation/escolhas.py` | 8 | `_para_interno`, `por_entidade` com chave desconhecida, prefixo ambíguo |
| `generation/entity_generator.py` | 9 | `_validate` (reroll sem evento anterior), `_fixar`, roda com >24 opções |

## Confirmados (do mais grave ao menos)

### 1. O classificador editorial lê `rarity` ao contrário do motor: o valor MAIS comum vira "RARO · 0% de chance"

- **Onde:** `builds/evaluation/reaction_classifier.py:91-101` (`_e_raro`: `rarity <= cfg["rare_probability"]` → RARE) contra `builds/generation/probability_engine.py:72-81, 83-88` (`roll_categorical` devolve "rarity 0..1 (1 = rarest)"; `numeric_rarity` é "distance from the center", 0 no centro) e `builds/evaluation/surprise_engine.py:7-8` (lê `rarity*100` como "quão raro", coerente com o motor).
- **O defeito:** o classificador trata `rarity` como se fosse a PROBABILIDADE da opção (docstring de `_e_raro`: "`rarity` e a probabilidade da opcao sorteada"), mas o campo que chega no evento é o complemento: 0 = centro da faixa/opção mais comum, 1 = extremo/opção mais rara. Resultado: valores no centro da faixa (altura 1,80 m, força 6,0, mana 6,0, peso 4,0 kg) são classificados RARE com motivo `probabilidade 0.0`; os genuinamente improváveis (rarity ≈ 1) nunca entram por esse caminho (só se o `surprise` ≥ 88). Daí descem três coisas erradas: peso editorial 78 (`PESO[RARE]`) ganha giro cheio e reação com 60% de chance (`reaction_chance_by_classification.RARE`); a pílula na tela (`timeline_builder._badge_da_reacao`) escreve **"RARO · 0% de chance"**; a voz (`narration_generator.EXTREMOS["RARE"]`) diz **"1,80m. Raro!"/"Isso quase não sai."** sobre a altura mais mediana possível.
- **Quando acontece:** em toda build. Para numérica, `numeric_rarity ≤ 0.07` cobre ±3,5% do centro da faixa; para categórica, qualquer opção com `p·n/2 ≥ 0.93` (opção dominante).
- **Prova:** `prova_raridade.py`. Sintético: `tamanho 1.80m rarity=0.0 -> RARE 'probabilidade 0.0'`; `1.40m` e `2.20m` (extremos, rarity 1.0) → NORMAL; `SurpriseEngine(score 50, rarity 0.0) = 0` e `(rarity 1.0) = 45` (o outro leitor do mesmo campo entende 1 = raro). Badge: `'RARO · 0% de chance'`; falas: `['Tamanho?', '1,80m. Raro!']`. **Dado real (só leitura):** nas últimas 40 gerações (560 rolagens), **20 RARE por "probabilidade"**, TODAS com rarity ≤ 0,07 (centro), e **7 delas com meme de reação no vídeo** (`generation_00094, 00096, 00102, 00105, 00118, 00132`, p.ex. `generation_00105 tamanho=1,80m score=50 probabilidade 0.0 reacao=sim`). O teste `tests/test_edicao_tiktok_regressions.py::test_improvavel_e_raro_mesmo_sem_ser_extremo` (`rarity=0.01` → RARE) fixa a leitura invertida.
- **Conserto sugerido:** em `_e_raro` e no motivo de `classify`, usar `1 - rarity` como probabilidade (`rarity >= 1 - cfg["rare_probability"]`) ou renomear o campo no evento para `improbabilidade`; trocar o motivo para a probabilidade de verdade (badge "7% de chance" só quando é 7%); ajustar o teste citado e acrescentar um com o `numeric_rarity` real (centro → nunca RARE; extremo → RARE). Depois, medir de novo o número de RARE por build (hoje ~0,5 por vídeo, metade com reação).

### 2. Hífen e apóstrofo furam a moderação do nome pedido: "Pu-ta", "Me-rda", "Cor-no" vão para a placa e para o gancho

- **Onde:** `builds/character/nomes.py:147` (`_PERMITIDOS = " -'"`) + `:181-182` (mantém `-`/`'` no nome limpo) contra `builds/character/moderacao.py:59` (`re.sub(r"[^a-z\s]+", " ", plano)` troca `-`/`'` por ESPAÇO) e `:101-104` (passada de palavra inteira compara token a token).
- **O defeito:** a palavra inteira "puta" vira "pu ta" na normalização e não casa com nada; `_juntar_letras_soltas` só cola corridas de letras ISOLADAS (3+), então "pu ta"/"me rda" ficam separadas; a passada de trecho (`grudado`) só tem os termos longos de `trecho`, e "puta", "merda", "corno", "viado", "babaca", "fuck", "bitch" estão em `palavra_inteira`. O nome sanitizado conserva o hífen/apóstrofo e sai como `Pu-ta` no `naming.character_name`, na placa (`_nameplate` → `PU-TA`), no gancho (`_sanitizar` mantém `-`) e no banco name-keyed do jogo. O mesmo vale para o espaço simples: "Pu ta" → nome aceito "Pu Ta".
- **Quando acontece:** `main.py generate-video --nome-pedido "<texto do comentário>"` com texto de estranho (é a única entrada externa que vira pixel, como o próprio módulo diz).
- **Prova:** `prova_moderacao.py`: `'Puta' -> None 'conteudo ofensivo'` (bloqueia); `'Pu-ta' -> nome='Pu-ta'`, `"Pu'ta" -> "Pu'ta"`, `'Me-rda'`, `'Cor-no'`, `'Vi-ado'`, `'Ba-ba-ca'`, `'Fu-ck'`, `'Bi-tch'`, `'Pu ta' -> 'Pu Ta'`, `'Pu-ta Mae' -> 'Pu-ta Mae'` — todos aceitos (`motivo=None`). `'P u t a'` é barrado (letras soltas), confirmando que só esse caso foi coberto.
- **Conserto sugerido:** em `ofensivo`, além de `plano` e das letras soltas, testar também o texto com os separadores REMOVIDOS por palavra (cada token de `bruto.split()` com `-`/`'` tirados) e o `grudado` contra `palavra_inteira` quando o nome tem 1–2 palavras; ou simplesmente tirar `-` e `'` de `_PERMITIDOS` (nome de comentário não precisa deles). Teste de regressão com os 10 casos acima.

### 3. `catalog.json` da biblioteca de reações corrompido ou com entrada sem `file` derruba TODA montagem de vídeo (build, duelo, torneio, re-render)

- **Onde:** `builds/assets/catalog.py:65-85` (`_load_reaction_catalog`: `json.load` e `entry["file"]`/`entry["id"]` sem proteção); construído sem `try` em 7 pontos de `builds/pipeline/controller.py` (471, 523, 585, 595, 654, 662, 706). O escritor é `builds/assets/importer.py:56-58` (`_save_catalog`: `open(..., "w")` + `json.dump` direto no arquivo final, sem tmp+replace).
- **O defeito:** a docstring promete "A biblioteca funciona VAZIA", mas um JSON truncado (escrita não atômica interrompida, disco cheio — o C: vive cheio) ou uma entrada editada à mão sem `file` levanta `JSONDecodeError`/`KeyError` na construção do `AssetCatalog`, antes de qualquer edição. Como o catálogo é lido a cada geração, um arquivo ruim trava a rodada inteira do `noite` até alguém abrir o JSON.
- **Quando acontece:** `catalog.json` escrito pela metade (importador interrompido, disco cheio) ou editado à mão; em paralelo com uma geração lendo.
- **Prova:** `prova_catalogo_e_funny.py` (1): `{ corrompido` → `EXCECAO JSONDecodeError`; `{"reactions":[{"id":"0001"}]}` → `EXCECAO KeyError 'file'`.
- **Conserto sugerido:** `_load_reaction_catalog` com `try/except (OSError, ValueError, KeyError)` que registra no diário e segue com a lista vazia (pulando entrada inválida); `_save_catalog` gravando em `.tmp` + `os.replace`. Teste: catálogo corrompido → biblioteca vazia e render segue com cartão sintético.

### 4. `funny.tamanho` do `editing.json` nunca dispara: a roleta de tamanho tem método `neutral` (score fixo 50) e a regra compara SCORE

- **Onde:** `builds/evaluation/reaction_classifier.py:104-120` (`_e_engracado` compara `roll["score"]` com `below`/`above`) contra `builds/nf_bridge/roulette_factory.py` (roleta `tamanho`: `{"method": "neutral"}`) e `config/editing.json → classification.funny.tamanho {"below": 12, "above": 88, "tamanho de bolso", "nao cabe na arena"}`.
- **O defeito:** `RollEvaluator.evaluate` devolve 50 para todo método `neutral`, então nenhum valor de 1,40 m a 2,20 m chega a ≤ 12 ou ≥ 88. As duas frases cômicas do config ("tamanho de bolso", "nao cabe na arena") são configuração sem leitor; um anão de 1,40 m ou um gigante de 2,20 m sai como NORMAL (relâmpago, sem reação). As outras entradas (`forca`, `velocidade_ataque`, `dano`) são `higher_is_better` e funcionam.
- **Quando acontece:** sempre; 32 de 32 rolagens de `tamanho` nas últimas 40 gerações têm score 50 (2 delas RARE pelo defeito 1, nenhuma FUNNY).
- **Prova:** `prova_catalogo_e_funny.py` (2): `scores possiveis para tamanho: {50}`; `tamanho 140 cm -> NORMAL`, `220 cm -> NORMAL`.
- **Conserto sugerido:** `_e_engracado` comparar pelo VALOR posicionado na faixa (`(value-min)/(max-min)*100`, que o evento já tem em `value` e a roleta em `min/max`) quando o método é `neutral`, ou pela `rarity` numérica; ou trocar a regra do config para `value_below_cm`/`value_above_cm`. Teste: 1,40 m → FUNNY "tamanho de bolso".

### 5. Empate chega ao texto da tela como `None` e derruba a legenda do torneio

- **Onde:** `builds/content/caption_generator.py:232-236` (`torneio_resultado`: `.replace("{VENCEDOR}", luta["vencedor"])` sem `str()`), `:241-250` e `:284-290` (`_sub_luta`/`_sub_serie` usam `str(...)`, que transforma `None` em `"None"`). Origem: `builds/tournament/runner.py:259-266` (`simular_luta` devolve `"vencedor": resultado.winner` após 3 tentativas, pode ser `None`) e `neural_fights/recording/fight_recorder.py:689-697` (`"vencedor": None if empate`); `gravar_confronto` só refaz 3 vezes e segue com o empate.
- **O defeito:** (a) torneio e luta avulsa sem série (`tournament/timeline.py:322` e `:462`) chamam `torneio_resultado` → `TypeError: replace() argument 2 must be str, not None` → render morre depois de gravar as lutas; (b) estreia/série (`luta_round`, `luta_serie`) não morre, mas escreve **"None leva esse."** e **"1 x 1 no ultimo round. None."** no cartão.
- **Quando acontece:** três empates seguidos na mesma dupla (seed, seed+1, seed+2). Latente: 0 de 217 `fight.json` em `outputs/` tem `"empate": true`. O caminho existe no código e no gravador.
- **Prova:** `prova_legenda_empate.py`: `torneio_resultado` → `EXCECAO: TypeError: replace() argument 2 must be str, not None`; `luta_round` → `'None leva esse.'`; `luta_serie` → `'1 x 1 no ultimo round. None.'`.
- **Conserto sugerido:** em `_sub_luta`/`_sub_serie`/`torneio_resultado`, `None` vira "ninguém"/"empate" e o pool de empate (criar `luta.resultado_empate` em `frases.json`); `gravar_confronto`/`simular_luta` com empate persistente devem marcar a luta como empate explícito e a timeline escolher a frase de empate. Teste com `vencedor: None`.

### 6. A guarda `termina_bem` (regra do pedido 4) não tem leitor em produção: o nome pedido pode terminar em epíteto

- **Onde:** `builds/character/nomes.py:135-144` (`termina_bem`) — 0 chamadas fora de testes; `sanitizar_nome_pedido` (`:165-205`) não a aplica.
- **O defeito:** a docstring do módulo diz que a regra "vale para o que o jogo antigo escrevia e para o que outra pessoa escrever depois", mas só a suíte a chama. "Kael o Sombrio", "Lyra das Chamas", "Bob Lendario" entram inteiros pelo comentário. (Os nomes GERADOS são seguros pela whitelist estrutural do `lexico`.)
- **Quando acontece:** `--nome-pedido` com epíteto/qualidade no fim.
- **Prova:** `sanitizar_nome_pedido('Kael o Sombrio') -> ('Kael O Sombrio', None)` com `termina_bem(...) == False` (idem os outros dois).
- **Conserto sugerido:** decidir com o Adrian se nome de comentário obedece à regra; se sim, `sanitizar_nome_pedido` recusa com motivo "termina em qualidade" (ou corta a última palavra e re-sanitiza).

### 7. `escolhas.por_entidade` estoura com `KeyError` cru em chave fora do catálogo

- **Onde:** `builds/generation/escolhas.py:155-161` (`disponivel[chave]["entidade"]`).
- **O defeito:** `interpretar` valida as chaves, mas `SessionGenerator.generate(escolhas=...)` aceita o dicionário de qualquer origem (painel, pedido gravado em JSON, re-render com `generation.json` antigo); uma chave desconhecida vira `KeyError: 'altura'` sem dizer que é escolha inválida.
- **Quando acontece:** escolhas montadas fora de `interpretar` (hoje só `main.py` chama `interpretar`; o risco é de quem gravar o dict em arquivo).
- **Prova:** `prova_catalogo_e_funny.py` (4): `por_entidade({"roletas": {"altura": 180}}, "character")` → `KeyError 'altura'`.
- **Conserto sugerido:** levantar `ValueError("atributo desconhecido: 'altura'. Conhecidos: ...")` como `interpretar` faz.

### 8. Observações de menor peso (confirmadas por leitura, sem prova separada)

- `builds/editing/timeline_builder.py:438-462` — quando o clipe é curto demais (`< min_util_segundos`) ou não cabe no orçamento, `_push_reaction` sai sem empurrar nada, mas `decision["reaction"]` continua `True`: `_marcar_cheias` (`:352`) já deu giro cheio àquela roleta e `evaluation.json` registra `reaction: null` para uma decisão "sim". Efeito: giro cheio gasto numa roleta sem reação.
- `builds/content/voz.py:865-870` — a assinatura do `voz.hash` ignora `volume`, `max_atempo`, `folga`, `atraso`: mudar o volume no `render.json` não regera `voz.wav` numa build já narrada (re-render mantém a voz antiga).
- `builds/assets/triagem.py` (`SessaoTriagem`, 11 funções) e `builds/content/caption_generator.py` (`for_reveal`, `for_identity` + chaves `reveal_character`, `reveal_weapon`, `identity`, `identity_pedido` do `captions.json`) e `builds/character/lexico.py::significado`, `nomes._pluralizar`, `nomes._fundir` — sem chamador fora de testes (a janela "Categorizar assistindo" do painel não existe mais; ver memória "Painel: funções perdidas na reescrita").
- `builds/arena/ledger.py:41-47` — ledger corrompido é renomeado para `ledger.corrompido.json` com `replace`, sobrescrevendo um `.corrompido.json` anterior (a segunda corrupção apaga a prova da primeira); e `registrar` (`:86-87`) engole o mesmo erro sem renomear, então o `salvar` seguinte sobrescreve o arquivo ruim sem cópia.

## Não confirmados

- **`EntityGenerator._validate` perde o evento re-rolado** (`entity_generator.py:218`: `if old and new_event` — roleta sem evento anterior ganha valor na entidade mas não entra em `events`): caminho existe, mas `config/rules.json` tem `validations: []` e `generated_rules()` não gera validação; não reproduzido em 39 seeds com uma validação sintética. Latente, sem alcance hoje.
- **`rodizio.titulos_ocupados` engole qualquer exceção de `metricas.publicados()`** (`rodizio.py:112-115`) e segue só com os pares do disco: `metricas.publicados` já tolera linha inválida (`ValueError` por linha), e todo duelo publicado continua em `outputs/duelo_*`, então o conjunto do disco cobre; só falharia se pastas de duelo fossem retiradas de `outputs/` (regra: não se apaga). Não confirmado.
- **Dois processos sintetizando o MESMO texto no mesmo cache de voz** (`voz.py:173`, `.parcial` com nome determinístico): builds têm trava `builds__gerar`, e as histórias usam `historias/outputs/_voz_cache` (cache próprio). Colisão exigiria texto idêntico em dois processos da mesma família ao mesmo tempo. Não reproduzido.
- **`synergy_engine._alcance_tamanho` compara `"Mágica"` com acento** — conferido: `LISTA_TIPOS_ARMA` tem `'Mágica'` (UTF-8 `M\xc3\xa1gica`) e `tipos_preferidos_da_classe('Mago')` devolve `['Orbital', 'Mágica']`. Não é defeito (o `M�gica` no console é só cp1252).
- **`synergy_engine._mana_habilidade` com `custo` ausente** — conferido: os 119 itens de `SKILL_DB` têm `custo`. Não é defeito.
- **Unidades em `SynergyEngine.evaluate`** (`forca`, `mana`, `tamanho`, `peso`) — `character_builder.finalize_*` converte antes (`generation_00140`: `tamanho 1.46`, `forca 7.8`, `peso 4.3`). Não é defeito.
- **`_nameplate` com `tamanho` ausente → "0,00 m"** — o registro NF (`generation["character"]`) tem `tamanho`. Não é defeito hoje.
- `outputs/generation_00141/` está VAZIA (reservada pelo `mkdir` exclusivo do `_next_id` de 873f2e6 e a geração não seguiu). Fora da fatia (pipeline); fica o registro para quem cuida do catálogo/fluxo.
