# Consertos — motor (Neural Fights) — verificação de 14/10/2026

- **Parte:** motor de luta e ferramentas do Neural Fights (`neural_fights/ai`, `core`, `effects`, `models`, `sounds`, `simulation`, `live`, `ui`, `tournament`, `recording`, `cli`, `tools/atelie_animacoes.py`, `tools/youtube_oauth.py`). O banco de personagens (`neural_fights/data/**`) está em `builds.md`.
- **Relatórios de origem:** `nf-ai.md`, `nf-core-a.md`, `nf-core-b.md`, `nf-effects-models.md`, `nf-simulation.md` (sem defeito confirmado), `nf-live-ui.md`, `nf-recording-cli.md`, `nf-tools.md`.
- **Contagem:** 72 defeitos (alguns itens juntam vários): **72 abertos / 0 consertados / 0 falsos inteiros**. Nenhum commit depois de 11/10 mexeu nestes arquivos, exceto o f5f8cd3, que só tocou em `recording/timeline_arquivo.validar` e não fecha nenhum item.
- **Gravidade:** 1 crítico (MOT-101, que é o mesmo conserto do BLD-1 (c) em `builds.md`), 25 médios, 46 baixos. Nada aqui publica errado sozinho: o motor afeta o que a luta mostra, e a luta só vira vídeo pelo caminho dos builds.
- **Como ler:** a metade A (MOT-1…33) é simulação, efeitos e som; a metade B (MOT-101…129) é live, launcher, torneio, gravação e CLI. Dentro de cada metade, os itens vão do mais grave ao menos.
- **Convenção do motor:** o determinismo é invariante a VFX. Na metade A, cada item diz se mexe na **SIMULAÇÃO** ou **SÓ NO VISUAL/SOM**. Os consertos de simulação mudam os números fixados nos testes. Eles vão num lote só, com re-pino (`# re-pino <id>`) e medição do ledger de qualidade antes e depois.
- **Testes:** `TEMP=E:\tmp_pytest` e `PYTEST_ADDOPTS=-p no:cacheprovider`.
- **Linhas:** as linhas citadas no `nf-live-ui.md` não batem com os arquivos de hoje. As linhas abaixo são as do código atual.

## Metade A — simulação, efeitos, modelos e som

### MOT-1 — Canal "Chamas do Dragão" empilha um DoT por tick  (médio)
- **Onde:** `neural_fights/core/combat.py:2297` (`Channel._processar_tick`) → `neural_fights/core/entities.py:3910-3941` (`_aplicar_efeito_status`, ramos ENVENENADO/SANGRANDO/QUEIMANDO)
- **Defeito:** cada tick de 0,1 s manda `self.tipo_efeito`. QUEIMANDO faz `dots_ativos.append` de um DotEffect novo. No fim do canal de 3 s o alvo tem 30 queimaduras, uns +92% de dano escondido. A prova de hoje (`scratchpad/mota_core_a.py`) deu 30 DoTs. A skill chega pelas 4 armas do banco runtime que a têm.
- **Conserto (SIMULAÇÃO):** em `_aplicar_efeito_status`, passar ENVENENADO/SANGRANDO/QUEIMANDO por `self._renovar_dot(...)` (entities.py:2227), como CORROENDO/NECROSE já fazem: renova a duração e fica com a maior intensidade, sem empilhar. Se a regra "empilhar" tiver de continuar para os golpes de arma, a saída mínima é outra: no `Channel._processar_tick`, mandar `self.tipo_efeito` só no primeiro tick em que o alvo é atingido (guardar `self._efeito_aplicado_em: set[id(alvo)]`) e `"NORMAL"` nos demais, como a AREA faz (`combat.py:1210`).
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_channel_dot_nao_empilha`. Monta Channel("Chamas do Dragão") com o alvo a 3 m, roda 180×`atualizar(1/60)` e afirma `len([d for d in alvo.dots_ativos if d.tipo=="QUEIMANDO"]) == 1`. Hoje dá 30.
- **Origem:** `nf-core-a.md` #1

### MOT-2 — Guarda cobrada por frame/tick em fonte contínua  (médio)
- **Onde:** `neural_fights/core/entities.py:3398-3404` (`tomar_dano`, ramo bloqueio). As fontes estão em `combat.py:2165` (Transform contato, `fonte_impacto=object()` por frame), `combat.py:2297` (Channel) e `combat.py:1196` (tick de AREA).
- **Defeito:** os 15 de estamina da guarda e o `contadores_luta["bloqueios"]` são cobrados por impacto. Fonte contínua gera um impacto por frame, então a guarda quebra em 7 frames e o contador de bloqueios infla.
- **Conserto (SIMULAÇÃO):** ler `tipo_fonte = (metadata_impacto or {}).get("tipo_fonte")`. Se ele estiver em `{"transform_skill", "trap_skill", "channel_skill", "dot_tick"}`, ou se o impacto vier com `ignorar_recuperacao_impacto=True` de um Channel, cobrar `custo = CUSTO_ESTAMINA_BLOQUEIO * min(1.0, dano_bloqueado / DANO_REFERENCIA_GUARDA)`. `DANO_REFERENCIA_GUARDA` é um knob novo em `utils/config.py` (sugestão: 30), e `dano_bloqueado = dano_antes - dano_final`. Nesses casos não incrementar `bloqueios` nem `bloqueios_visuais`. Antes, confirmar os nomes de `tipo_fonte` emitidos com `grep -n tipo_fonte neural_fights/core/combat.py`.
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_guarda_contra_contato_continuo_nao_quebra_em_frames`. O alvo fica em BLOQUEAR olhando o atacante (brain dublado só com `acao_atual="BLOQUEAR"`, `tempo_bloqueando=1.0`) e recebe 60 impactos de 0,33 com `tipo_fonte="transform_skill"`. Afirma `estamina > 50` e `contadores_luta["bloqueios"] <= 1`. Hoje dá 0 e 7+.
- **Origem:** `nf-core-a.md` #3

### MOT-3 — `brain.raiva += 0.2` sem teto  (médio)
- **Onde:** `neural_fights/core/entities.py:3622` (`tomar_dano`)
- **Defeito:** é o único incremento de raiva sem `min(1.0, ...)`. Com fonte contínua a raiva vai a 12. Ela decai (property delegada ao `EmotionSystem`, `ai/emotions.py:104`, de 0,24 a 0,9 por segundo), mas de 12 leva de 12 a 50 s para voltar abaixo de 1, e nesse tempo todo limiar `raiva > 0.7` fica ligado. O relatório errou ao dizer "sem decaimento".
- **Conserto (SIMULAÇÃO):** `self.brain.raiva = min(1.0, self.brain.raiva + 0.2)`, e pular o incremento para as mesmas fontes contínuas do MOT-2 (fazer junto).
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_raiva_do_dano_tem_teto`. Brain real (ou o EmotionSystem real) e 20 chamadas de `tomar_dano(5, ...)`. Afirma `brain.raiva <= 1.0`.
- **Origem:** `nf-core-a.md` #7 (e a parte de raiva do #3)

### MOT-4 — Eco do Feiticeiro desfaz "Troca de Almas"  (médio)
- **Onde:** `neural_fights/core/entities.py:1811-1818` (`usar_skill_classe`, bloco do eco)
- **Defeito:** o eco (22%) repete o despacho inteiro. O segundo `_trocar_posicoes` desfaz o primeiro e a skill cobra 40 de mana e 30 s de cooldown sem efeito nenhum. Comprovado hoje com rng 0,10.
- **Conserto (SIMULAÇÃO):** no `if "Feiticeiro" in self.classe_nome and ...`, acrescentar a condição `data.get("tipo") in ("PROJETIL", "AREA", "BEAM", "SUMMON")`, ou seja, não ecoar `efeito == "TROCAR_POS"` nem DASH/TRANSFORM/CHANNEL/BUFF. Atenção: a condição tem de vir ANTES do `rng_runtime.random()`, para não consumir sorteio à toa; se o tipo for checado depois do sorteio, a sequência de RNG muda de outro jeito.
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_eco_do_feiticeiro_nao_desfaz_troca`. Feiticeiro (Caos) em (0,0) com rng fixo 0,10, alvo em (6,0) e `usar_skill_classe("Troca de Almas", alvo)`. Afirma `f.pos[:2] == [6,0]`. Hoje dá [0,0].
- **Origem:** `nf-core-a.md` #2

### MOT-5 — `cooldown_ataque` congela durante stun, sono, canal e agarrão  (médio)
- **Onde:** `neural_fights/core/entities.py:2566` (`executar_ataques`), chamado só sob `stun_timer <= 0` (2195-2209)
- **Defeito:** a cadência só anda quando o corpo pode agir. O stun do parry (0,5 s) soma com os 0,9 s de cadência que o próprio parry impõe. Comprovado hoje: depois de 60 updates com stun 1 s, `cooldown_ataque` continua 0,50.
- **Conserto (SIMULAÇÃO):** tirar `self.cooldown_ataque -= dt` de `executar_ataques` e decrementar em `Lutador.update()` antes do ramo de stun/agarrão, junto dos outros timers: `self.cooldown_ataque = max(0.0, self.cooldown_ataque - dt)`. Rodar a medição de qualidade antes e depois, porque muda o ritmo de toda luta (ver Decisões).
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_cadencia_corre_durante_stun`. `cooldown_ataque=0.5`, `stun_timer=1.0` e 60×`update(1/60, inimigo)`. Afirma `cooldown_ataque == 0`.
- **Origem:** `nf-core-a.md` #4

### MOT-6 — Fluxo do coreógrafo enviesado para o lutador 1  (médio)
- **Onde:** `neural_fights/ai/choreographer.py:219-226` (`_atualizar_fluxo`)
- **Defeito:** pior que o relatório descreve. `ang_l2_para_l1 = ang + pi` sai do intervalo [-pi, pi], e o lutador parado conta como velocidade de ângulo 0. Medido (`scratchpad/mota_fluxo.py`): o L2 avançando só é reconhecido em 2 de 8 direções, e com o L2 a 0° ou 45° o fluxo vai para **+0,5, a favor do L1**. O L1 avançando falha a -179°. Isso alimenta o momento PRESSURE (`:394`), em que só o L1 recebe `PRESSIONAR_CONTINUO` (`:595`).
- **Conserto (SIMULAÇÃO):** criar `def _delta_ang(a, b): return abs((a - b + math.pi) % (2*math.pi) - math.pi)`. Usar `l1_avancando = vel1_mag > 0.5 and _delta_ang(ang_l1_para_l2, ang_vel_l1) < math.pi/3`, e o mesmo para o L2 com `ang_l2_para_l1 = math.atan2(l1.pos[1]-l2.pos[1], l1.pos[0]-l2.pos[0])`. Lutador parado não avança.
- **Teste que prova:** `tests/test_choreographer_retune_regressions.py::test_fluxo_simetrico_em_todas_as_direcoes`. Para 8 ângulos, o L2 avança contra o L1 parado e afirma `fluxo_direcao < 0`; o espelho, com o L1 avançando, afirma `> 0` (incluindo ±179°). Hoje falha em 6 dos 8 casos.
- **Origem:** `nf-ai.md` #6

### MOT-7 — Vantagem de canto vira agressividade permanente  (médio)
- **Onde:** `neural_fights/ai/brain.py:2387-2391` (`_avaliar_taticas_espaciais`)
- **Defeito:** a cada 0,2 s com o inimigo na parede, soma +0,25, +0,2 ou +0,15 em `agressividade_base` (persistente) e nunca desfaz. Em 0,6 s o PREDADOR fica em 1,0 pelo resto da luta.
- **Conserto (SIMULAÇÃO):** não mutar `agressividade_base`. Guardar `self.bonus_canto` (0 quando `oponente_vulneravel` for falso; senão, a soma dos bônus por traço, com teto de 0,4) e somá-lo onde a agressividade efetiva é calculada (`brain.py:4565-4571`, a função "f(agressividade_base, eixo agressao, humor)"), com clamp em 1,0.
- **Teste que prova:** `tests/test_ai_perception_contracts.py::test_bonus_de_canto_some_quando_inimigo_sai`. Brain com PREDADOR, 3 chamadas com `oponente_contra_parede=True` e depois 1 com False. Afirma que `agressividade_base` é igual ao valor inicial e que a agressividade efetiva voltou.
- **Origem:** `nf-ai.md` #1

### MOT-8 — Reação "FUGIR" do covarde é descartada  (médio)
- **Onde:** `neural_fights/ai/brain.py:3369` (`on_hit_recebido_de`) e `:3130-3159` (`_processar_reacao_oponente`)
- **Defeito:** a reação "FUGIR" não está no dicionário `acoes`. O despachante apaga a reação e devolve False.
- **Conserto (SIMULAÇÃO):** acrescentar `"FUGIR": ("FUGIR", lambda: setattr(self, 'medo', min(1.0, self.medo + 0.1)))` ao dicionário `acoes`. "FUGIR" já é ação válida do motor (`brain.py:3257`). Passar pela escrita única de `acao_atual`, como as outras.
- **Teste que prova:** `tests/test_brain_action_writer_regressions.py::test_covarde_foge_ao_apanhar`. Brain com `tracos=["COVARDE"]`, `medo=0.6` e rng que devolve 0,0, mais `on_hit_recebido_de(x)` e `_processar_reacao_oponente(...)`. Afirma `True` e `acao_atual == "FUGIR"`.
- **Origem:** `nf-ai.md` #3

### MOT-9 — "Posso atacar" julgado pelo ângulo do inimigo  (médio)
- **Onde:** `neural_fights/ai/brain.py:2725-2739` (`_calcular_estrategia_armas`) e `neural_fights/core/weapon_analysis.py:464-486` (`avaliar_posicao_combate`)
- **Defeito:** o brain passa "onde eu estou no olhar DELE" (sem normalizar, pode chegar a ±360) e a função usa esse número para o MEU arco. Atrás do inimigo, a recomendação sai "aproximar"; de costas, "posso_atacar" sai True. Isso alimenta `estrategia_recomendada` (`brain.py:2776`).
- **Conserto (SIMULAÇÃO):** `avaliar_posicao_combate(minha_arma, arma_inimigo, distancia, ang_meu, ang_dele)`. `ang_meu` é o ângulo do inimigo no MEU olhar, `ang_dele` é o meu no olhar dele, e os dois são normalizados com `(a+180)%360-180`. `posso_atacar` usa `ang_meu`; `get_threat_at_distance` usa `ang_dele`. Atualizar `evaluate_combat_position` (`:534`) e o chamador do brain.
- **Teste que prova:** `tests/test_ai_perception_contracts.py::test_posso_atacar_usa_meu_angulo`. Eu atrás do inimigo e olhando para ele (`ang_meu=0`, `ang_dele=180`) com Reta×Reta a 1,5 m: afirma `posso_atacar=True` e `inimigo_pode_atacar=False`.
- **Origem:** `nf-core-b.md` C3

### MOT-10 — Super armor: quebrar dói menos que absorver  (médio)
- **Onde:** `neural_fights/core/game_feel.py:592-594` (`SuperArmorSystem.processar_dano`) e `:606` (`reset_armor`)
- **Defeito:** ao quebrar, o golpe volta com `dano_base*0.5`, menos que a absorção normal do Cavaleiro (×0,75) e do Paladino (×0,6). `reset_armor` não tem chamador. No caminho `sempre_ativo` (`:484-490`) o `dano_absorvido` nunca zera.
- **Conserto (SIMULAÇÃO):** na quebra, `return (dano_base, knockback_x, knockback_y, True)` (golpe inteiro, com stagger). Em `verificar_ativacao` do ramo `sempre_ativo`, chamar `self._ativar_armor()` quando passar de inativo para ativo, em vez de escrever `data.ativo` direto. Chamar `reset_armor()` de todos os sistemas em `GameFeelManager.registrar_lutadores` ou no início de round.
- **Teste que prova:** `tests/test_game_feel_regressions.py` (novo), `test_quebra_da_armadura_nao_reduz_mais_que_absorcao`. Cavaleiro com 1000 HP em BLOQUEAR: o hit de 1500 que quebra devolve dano ≥ 1500×0,75.
- **Origem:** `nf-core-b.md` C4

### MOT-11 — Cache de perfil de arma por (nome, tipo), global ao processo  (médio)
- **Onde:** `neural_fights/core/weapon_analysis.py:202-204, 265` (cache) e `:516` (`analisador_armas` global)
- **Defeito:** a chave ignora as medidas. Arma editada no painel, ou de mesmo nome, recebe o perfil velho. A percepção da IA passa a depender da história do processo, não da semente, o que quebra a re-simulação por semente (palco/launcher) num processo que editou uma arma.
- **Conserto (SIMULAÇÃO):** chave `(arma.nome, arma.tipo, comp_cabo, comp_lamina, largura, peso, dano, getattr(arma,"comp_corrente",0), getattr(arma,"comp_ponta",0), getattr(arma,"tamanho_projetil",0), getattr(arma,"tamanho_arco",0), getattr(arma,"quantidade_orbitais",1))`, ou seja, todos os campos lidos em `_criar_perfil` (conferir a lista na função). E `analisador_armas._cache_profiles.clear()` no `Simulador.recarregar_tudo`.
- **Teste que prova:** `tests/test_ai_perception_contracts.py::test_perfil_de_arma_nao_vaza_entre_medidas`. Duas `SimpleNamespace` "Espada Longa"/Reta com lâmina 60 e 170. Afirma `p1 is not p2` e `p2.alcance_maximo > p1.alcance_maximo`.
- **Origem:** `nf-core-b.md` C2

### MOT-12 — Som de cast medido contra um ouvinte parado em x=0  (médio)
- **Onde:** `neural_fights/core/entities.py:1668` → `neural_fights/effects/audio.py:644` (`play_skill`) e `:526` (`play_positional`)
- **Defeito:** o cast passa só `pos_x` e `listener_x` fica 0. Acima de 20 m o cast fica mudo, a 10 m sai com metade do volume, e o vídeo herda isso pelo AnotadorDeAudio.
- **Conserto (SÓ SOM, não toca a simulação; o AudioManager não usa `rng_runtime`):** criar `AudioManager.listener_x: float | None = None`. O Simulador atualiza esse valor a cada passo (`self.audio.listener_x = self.cam.x / PPM`, no mesmo lugar onde já calcula `listener_x`, `simulacao.py:1213`). Em `play_skill` e `play_positional`, `listener_x=None` usa `self.listener_x`, e se ainda for None chama `self.play(...)` sem posição. Em `entities.py:1668`, deixar de passar `listener_x`.
- **Teste que prova:** `tests/test_audio_contracts.py::test_cast_toca_em_qualquer_x`. `AnotadorDeAudio(seed=1)` com `listener_x=25`, `play_skill("PROJETIL","Bola de Fogo",28,phase="cast")`. Afirma uma linha nova em `sons` com volume > 0,3. Hoje: silêncio.
- **Origem:** `nf-effects-models.md` #1

### MOT-13 — `AudioManager.play` com pan dobra o volume  (médio)
- **Onde:** `neural_fights/effects/audio.py:515-519`
- **Defeito:** `set_volume(min(1, left+right)) = fv*(2-|pan|)`. Todo som posicional sai até 1,8× mais alto, há um salto em pan=0, e a trilha do vídeo herda a relação errada entre os sons.
- **Conserto (SÓ SOM):** `sound.set_volume(final_volume)` sempre, guardando o pan só para o anotador, que já o grava. Quem quiser pan real usa o canal: `ch = sound.play(); ch.set_volume(fv*min(1,1-pan), fv*min(1,1+pan))`. Fazer junto com o MOT-12. Avisar o Adrian que o volume relativo dos golpes cai: só ele julga o som.
- **Teste que prova:** `tests/test_audio_contracts.py::test_pan_nao_altera_volume_total`. O volume anotado de `play("clash_swords",1.0,pan=0.0)` é igual ao de `pan=0.001` e ao de `pan=0.5`.
- **Origem:** `nf-effects-models.md` #2

### MOT-14 — Janela de ataque: a última condição apaga a melhor  (baixo)
- **Onde:** `neural_fights/ai/brain.py:1810-1866` (`_atualizar_janelas_oportunidade`)
- **Defeito:** as 7 condições sobrescrevem `qualidade`/`tipo`, e só a última é comparada (stun 1,0 perde para recuando 0,75).
- **Conserto (SIMULAÇÃO):** trocar cada bloco por `candidatas.append((qualidade, tipo, duracao))` e no fim usar `melhor = max(candidatas, key=lambda c: c[0])`. Manter a comparação com `janela["qualidade"]`.
- **Teste que prova:** `tests/test_ai_perception_contracts.py::test_janela_escolhe_a_melhor_do_frame`. Inimigo com `stun_timer=1`, `cooldown_ataque=0.3` e observado recuando, com janela atual de 0,8: afirma `tipo=="stunado"` e `qualidade==1.0`.
- **Origem:** `nf-ai.md` #2

### MOT-15 — Ladino paga e conta o bloqueio, e depois esquiva  (baixo)
- **Onde:** `neural_fights/core/entities.py:3398-3404` (custo/contagem) antes de `:3423-3439` (esquiva)
- **Conserto (SIMULAÇÃO):** mover o bloco da esquiva do Ladino (o sorteio `rng_runtime.random() < 0.12` e o `return False`) para antes de `guarda = self._avaliar_bloqueio(atacante)` (`:3337`). O número de sorteios por impacto não muda, só a ordem.
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_esquiva_do_ladino_nao_cobra_guarda`. Ladino em guarda com rng 0,05: afirma `estamina==100` e `bloqueios==0`.
- **Origem:** `nf-core-a.md` #5

### MOT-16 — `_aplicar_efeito_status` devolve "aplicado" sem fazer nada  (baixo)
- **Onde:** `neural_fights/core/entities.py:4065-4086` (PUXADO/VORTEX), `:4127-4140` (EMPURRAO/EXPLOSAO/DRENAR) e `:4212`
- **Conserto (SIMULAÇÃO leve; muda `flash_timer` e a sonda K1/K2, não muda posição nem vida):** esses cinco ramos fazem `return False`. Apagar `sendo_puxado`/`em_vortex`, que não têm nenhum leitor.
- **Teste que prova:** `tests/test_runtime_combat_contracts.py::test_efeito_sem_status_nao_marca_aplicado`. `resolver_impacto(0.0, 1, 0, "EMPURRAO")` afirma `efeito_aplicado is False` e `flash_timer == 0`.
- **Origem:** `nf-core-a.md` #6

### MOT-17 — Corrente V2: salto da mão vira velocidade da bola  (baixo, porque a V2 é desligada por padrão)
- **Onde:** `neural_fights/core/corrente.py:388` (`atualizar_bola`) e `:445-446`
- **Conserto (SIMULAÇÃO, só nas lutas com `corrente_v2`):** depois de calcular `hx1,hy1`, se `math.hypot(hx1-hx0, hy1-hy0) > max(0.5, 3*vel_nominal*dt)`, tratar como teleporte: `bola.x += hx1-hx0; bola.y += hy1-hy0; vhx = vhy = 0`. Pôr o termo de arrasto dentro do clamp de `a_max`.
- **Teste que prova:** `tests/test_corrente_v2_regressions.py::test_teleporte_da_mao_nao_acelera_bola`, com os helpers do arquivo: virada de 180° e teleporte de 8 m no meio do golpe. Afirma `v_depois < 2*v_antes`.
- **Origem:** `nf-core-b.md` C1

### MOT-18 — Hit stop soma as durações em fila  (baixo)
- **Onde:** `neural_fights/core/game_feel.py:355-360` (`registrar_hit`) e `:1101-1104` (`GameFeelManager.reset`)
- **Conserto (SIMULAÇÃO: o hit stop zera o dt, então muda a contagem de quadros e a timeline, não o vencedor):** com evento ativo, `self.timer_ativo = max(self.timer_ativo, duracao)`, e se `duracao > evento_atual.duracao` trocar `evento_atual`, sem fila. Em `reset`, chamar `HitStopManager.reset()` sempre.
- **Teste que prova:** `tests/test_game_feel_regressions.py::test_hitstop_usa_o_maior`. Registra 0,023 e depois 0,5 e soma os dt devolvidos como 0: afirma ≈ 0,5 (hoje 0,525).
- **Origem:** `nf-core-b.md` C6

### MOT-19 — Contrato: BEAM canalizável com `duracao = 0`  (baixo)
- **Onde:** `neural_fights/core/skill_contract.py:395-402`
- **Conserto (contrato; a IA lê, então é SIMULAÇÃO indireta):** `data.get("duracao_max") if (tipo == "CHANNEL" or canalizavel) else data.get("duracao")`.
- **Teste que prova:** `tests/test_skill_contract.py::test_beam_canalizavel_tem_duracao`. O contrato de "Chamas do Dragão" e o de "Desintegrar" têm `duracao == 3.0`.
- **Origem:** `nf-core-b.md` C5

### MOT-20 — Arena: dano fracionário em obstáculo é descartado  (baixo)
- **Onde:** `neural_fights/core/arena.py:657` (`danificar_obstaculo`)
- **Conserto (SIMULAÇÃO):** `obs.hp = float(obs.hp) - max(0.0, float(dano))`. Conferir se algum leitor espera `int` (HUD/serialização da timeline).
- **Teste que prova:** `tests/test_arena_legibilidade_regressions.py::test_dano_fracionario_desgasta_obstaculo`. 50×0,9 na caixa do Cyberpunk: afirma `hp == 55`.
- **Origem:** `nf-core-b.md` C7

### MOT-21 — Agarrão: `except TypeError` chama o dash de novo  (baixo)
- **Onde:** `neural_fights/core/agarrao.py:211-214` (`aplicar_desfecho`, ESCAPE). O relatório citava 477-481, linhas que não existem.
- **Conserto (SIMULAÇÃO só se houver bug dentro do dash):** apagar o `try/except` e chamar só `dash(ang_fuga, forca=18.0, ignorar_custo=True)`.
- **Teste que prova:** `tests/test_agarrao_regressions.py::test_escape_nao_repete_dash`. Um dash dublado que levanta TypeError: afirma uma chamada só e o erro propagado.
- **Origem:** `nf-core-b.md` C8

### MOT-22 — SUMMON mudo e grupo `footstep` vazio  (baixo)
- **Onde:** `neural_fights/effects/audio.py:290-398` (`_setup_sounds`) e `:400-411` (`_register_sound_group`)
- **Conserto (SÓ SOM):** acrescentar `self._register_sound("summon_cast")` em `_setup_sounds`. Em `_register_sound_group`, para "footstep" passar `["footstep_1", ..., "footstep_4"]` (ou usar `full_name = name` quando o nome já for completo) e garantir fallback em `SOUND_FALLBACKS`.
- **Teste que prova:** `tests/test_audio_contracts.py::test_summon_cast_toca`. Com o `AnotadorDeAudio`, `play_skill("SUMMON","x",phase="cast")` gera uma linha em `sons`.
- **Origem:** `nf-effects-models.md` #5

### MOT-23 — `AttackAnimationManager()` apaga as marcas a cada golpe pesado  (baixo)
- **Onde:** `neural_fights/effects/attack.py:678-703` (`__init__`) e `neural_fights/core/entities.py:2739`
- **Conserto (SÓ VISUAL; só roda com tela):** no início de `__init__`, `if getattr(self, "_pronto", False): return`, com `self._pronto = True` no fim. `reset()` continua zerando `_instance`.
- **Teste que prova:** `tests/test_vfx_doctrine_regressions.py::test_attack_manager_nao_reinicia`. Instância com 1 cratera e ppm 40: `AttackAnimationManager()` mantém 1 cratera e ppm 40.
- **Origem:** `nf-effects-models.md` #3

### MOT-24 — Faíscas da arma envelhecem duas vezes por quadro  (baixo)
- **Onde:** `neural_fights/effects/weapon_animations.py:1161-1165` (`_update_sparks`)
- **Conserto (SÓ VISUAL):** o corpo vira `for s in state.spark_list: s["timer"] += dt` e depois `state.spark_list = [s for s in state.spark_list if s["timer"] < s["life"]]`.
- **Teste que prova:** `tests/test_vfx_doctrine_regressions.py::test_faisca_vive_o_life`. Faísca com life 0,2 a 60 Hz continua viva no quadro 11 (t ≈ 0,183).
- **Origem:** `nf-effects-models.md` #4

### MOT-25 — Trilha das faíscas de explosão desenhada espelhada  (baixo)
- **Onde:** `neural_fights/effects/magic_vfx.py:112-114`
- **Conserto (SÓ VISUAL):** `ox, oy = min(p1[0],p2[0])-2, min(p1[1],p2[1])-2`, desenhar de `(p1[0]-ox, p1[1]-oy)` a `(p2[0]-ox, p2[1]-oy)` e fazer o blit em `(ox, oy)`, como `impact.DashTrail.draw`.
- **Teste que prova:** `tests/test_vfx_doctrine_regressions.py::test_trilha_de_faisca_nao_espelha`. Com p1=(100,100) e p2=(120,80), o pixel em (118,82) da tela é pintado e o (118,98) não.
- **Origem:** `nf-effects-models.md` #11

### MOT-26 — `AfterImage` nasce com vida maior que `max_vida`  (baixo)
- **Onde:** `neural_fights/effects/movement.py:169-179` (`_spawn_image`)
- **Conserto (SÓ VISUAL):** passar também `vida=max_vida` (calcular `mv = 0.2 + len(self.images)*0.02` e usar nos dois).
- **Teste que prova:** `tests/test_vfx_doctrine_regressions.py::test_afterimage_vida_igual_max`. Depois do spawn, `img.vida == img.max_vida`.
- **Origem:** `nf-effects-models.md` #12

### MOT-27 — `sound_config.json`: 26 de 46 chaves apontam para arquivo inexistente  (baixo)
- **Onde:** `neural_fights/sounds/sound_config.json`
- **Conserto (SÓ SOM):** para as 26 chaves (lista em `scratchpad/mota_som.py`), trocar o arquivo pelo alvo real do `SOUND_FALLBACKS` ou remover a chave. Não trocar `arena_victory` sem o Adrian (ver Decisões).
- **Teste que prova:** `tests/test_audio_contracts.py::test_config_so_aponta_arquivo_existente`. Toda chave de arquivo do config existe em `neural_fights/sounds/`.
- **Origem:** `nf-effects-models.md` #9

### MOT-28 — Estilos do editor de armas não existem para o renderer  (baixo)
- **Onde:** `neural_fights/models/constants.py:115-194` (`TIPOS_ARMA[...]["estilos"]`) e também `neural_fights/tournament/tournament_mode.py:1381` ("Corte (Espada)")
- **Conserto (SÓ VISUAL):** derivar `estilos` das chaves de `effects/weapon_render.py` (`ESTILOS_*`, `FORMAS_ARREMESSO`) cruzadas com `STYLE_PROFILES`, e trocar o rótulo do torneio pela chave real.
- **Teste que prova:** `tests/test_weapon_edit_regressions.py::test_estilos_do_editor_tem_desenho_e_perfil`. Todo estilo listado é chave do renderer e do animador.
- **Origem:** `nf-effects-models.md` #6

### MOT-29 — `Arma`: a migração de `tamanho` nunca roda; `get_escala_visual_arma` divide por zero  (baixo)
- **Onde:** `neural_fights/models/weapons.py:173` (`tamanho_antigo = kwargs.get(...)`) e `:439-440`
- **Conserto (dados/visual):** usar o parâmetro `tamanho` (`tamanho_antigo = float(tamanho or 0)`). Em `get_escala_visual_arma`, `if proporcao <= 0: return 1.0` antes do ramo `< 0.4`, ou apagar a função, que não tem chamador.
- **Teste que prova:** `tests/test_weapon_edit_regressions.py::test_migracao_tamanho_legado`. `Arma("T","Reta",10,1.0,tamanho=100)` dá `comp_cabo==30` e `comp_lamina==70`. Com geometria 0, `get_escala_visual_arma` devolve 1.0 sem exceção.
- **Origem:** `nf-effects-models.md` #7 e #8

### MOT-30 — 29 quirks sorteáveis sem efeito no runtime  (baixo)
- **Onde:** `neural_fights/ai/personalities.py:771` (`QUIRKS`), `ai/brain.py:503` (presets) e `:871` (`_gerar_quirks`)
- **Defeito:** são 29, não 28: o auditor perdeu `CAÇADOR_FERIDAS` por causa do acento. O lutador recebe um rótulo que nada lê.
- **Conserto (SIMULAÇÃO, porque muda o sorteio):** criar `QUIRKS_ATIVOS` com só os quirks que têm leitor e sortear dele (`_gerar_quirks` e presets). Os presets que fixam quirk morto (ex.: `personalities.py:1647`) ficam com o rótulo, mas fora da contagem. Implementar ou retirar é decisão do Adrian (ver Decisões).
- **Teste que prova:** `tests/test_personality_axis_contracts.py::test_quirk_sorteado_tem_leitor`. Todo quirk sorteável aparece citado entre aspas em algum .py de `neural_fights/` fora de `personalities.py`.
- **Origem:** `nf-ai.md` #4

### MOT-31 — Humores MELANCOLICO e EXTASE nunca produzidos  (baixo)
- **Onde:** `neural_fights/ai/personalities.py:1180-1181` e `ai/emotions.py:158` (`atualizar_humor`)
- **Conserto (SIMULAÇÃO, se ligar):** acrescentar gates na escada (sugestão: EXTASE com `excitacao > 0.8 and confianca > 0.7`; MELANCOLICO com `hp_pct < 0.35 and frustracao > 0.6 and raiva < 0.2`), ou retirar os dois do catálogo e do `character_flair`.
- **Teste que prova:** `tests/test_personality_axis_contracts.py::test_todo_humor_tem_produtor`. Todo nome de `HUMORES` aparece em `emotions.py`.
- **Origem:** `nf-ai.md` #5

### MOT-32 — Código morto do motor (espacial, arena, física, game_feel, câmera, skills sem fonte)  (baixo)
- **Onde:** `ai/spatial.py:347, 455, 479`; `core/arena.py:588, 591, 670, 900`; `core/physics.py:92, 104, 116`; `core/weapon_analysis.py:439`; `core/game_feel.py:617` (`ChannelingSystem`), `:1239`, e `core/entities.py:4339`; `core/skills.py` (`listar_skills_para_ui`, `listar_elementos`, `contar_skills`, `get_skills_by_*`); `effects/camera.py:631-642`
- **Conserto (nenhum efeito na luta):** apagar as funções sem chamador (zero usos em toda a árvore, conferido por regex). Para `esta_em_zona_perigo` (lava), esperar a decisão. Em `skill_contract`, `fontes` passa a incluir `arma:<nome>` (hoje diz "inalcançável" para skills que armas do banco usam). As 7 skills sem pool **já estão marcadas de propósito** em `models/constants.py:561` (`SKILLS_FORA_DE_ROTACAO`, "disponíveis para armas"); essa parte do relatório não é defeito.
- **Teste que prova:** `tests/test_skill_contract.py::test_fontes_incluem_arma`. Com o banco de armas carregado, o contrato de "Chamas do Dragão" lista uma fonte `arma:...`.
- **Origem:** `nf-ai.md` #7; `nf-core-b.md` C9; `nf-effects-models.md` #10

### MOT-33 — Miúdos de efeitos e modelos  (baixo)
- **Onde:** `effects/audio_anotador.py:204` (`arquivos_de_som` cria a pasta runtime/sounds), `effects/audio.py` (`_load_sound_config` sem validar `_volumes`), `models/constants.py:338-342` (escala no import), `get_class_data` e similares (default calado), `Arma.__init__` (lista `habilidades` por referência), `effects/particles.py:35-40` (`TETO_PARTICULAS=900`/`ParticleBudget` mortos), `impact.ImpactFlash.draw` e `BlockEffect.draw`
- **Conserto (nenhum efeito na luta):** em `arquivos_de_som`, cachear o AnotadorDeAudio por mtime do config. Validar `_volumes` com `float()` e clamp [0,1]. Guardar a escala com `if not _enc.get("_escalado")`. Logar o aviso no default do `get_*_data`. Fazer `list(habilidades)`. Apagar `ParticleBudget` e `TETO_PARTICULAS` de `particles.py`.
- **Teste que prova:** `tests/test_audio_contracts.py::test_volume_texto_no_config_nao_quebra_play`, com `"golpes": "1.0"` no config temporário e `play` sem exceção.
- **Origem:** `nf-effects-models.md` #13


## Metade B — live, launcher, torneio, gravação, CLI e ferramentas

### MOT-101 — "Gerar Roster" do torneio apaga o catálogo inteiro sem perguntar  (crítico)
- **Onde:** `neural_fights/ui/view_torneio.py:356-368` (`TournamentWindow.generate_roster`) → `neural_fights/tools/gerador_database.py:662` (`salvar_database`, `substituir=True`)
- **Defeito:** um clique grava 64 personagens e armas gerados por cima das armas e dos personagens que o Adrian criou no wizard. Grava no runtime que o launcher lê. Não pergunta nada. A cópia `_backup-*` sai (`database._copia_antes_de_perder`, chamada por `salvar_database`), mas só vai para o `logger.warning`: ninguém é avisado. É o mesmo conserto do BLD-1 (c) em `builds.md`. Faça um só.
- **Conserto:** antes de gerar, `messagebox.askyesno` mostrando quantos personagens e armas existem hoje e serão substituídos. Se a resposta for "não", sai sem tocar em nada. Se for "sim", copie antes os dois arquivos resolvidos por `database.resolver_database_paths(para_escrita=True)` para `<arquivo>.antes_do_roster_<AAAAMMDD-HHMMSS>.json`, ao lado deles, e só então chame `salvar_database`. Opção mais segura: ver as decisões do Adrian no fim.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_gerar_roster_pergunta_e_guarda_copia`. Com `NEURAL_FIGHTS_RUNTIME_DIR` em `E:\tmp_pytest`, monkeypatch de `askyesno` para `False`: os arquivos de runtime não mudam (hash igual). Com `True`: aparece o `.antes_do_roster_*.json` com o conteúdo anterior. Hoje falha porque o arquivo é sobrescrito sem chamar `askyesno`.
- **Origem:** `nf-live-ui.md` #C9

### MOT-102 — Torneio: o resultado de "SIMULAR LUTA" ou "Fighter N Venceu" vai para a luta corrente e é descartado em silêncio  (médio)
- **Onde:** `neural_fights/tournament/tournament_mode.py:372` (`Tournament.record_match_result`); `neural_fights/ui/view_torneio.py:276-288` (`_on_simulation_finished`) e `:310-330` (`register_winner`)
- **Defeito:** `record_match_result` usa `get_current_match()` em vez da luta selecionada no card "LUTAR". Se o vencedor não está na luta corrente, devolve `False`. A janela ignora esse retorno e escreve "Vencedor registrado".
- **Conserto:** acrescentar o parâmetro opcional `match: TournamentMatch | None = None` a `record_match_result`. Se vier, use essa luta (e recuse, com `False`, se ela já estiver `completed` ou tiver BYE/TBD); se não vier, mantenha `get_current_match()`. `_advance_to_next_match` continua igual. Na janela, passar `match=match` (simulação) e `match=self.current_match` (registro manual). Se o retorno for `False`, mostrar `messagebox.showerror` e não escrever "Vencedor".
- **Teste que prova:** `tests/test_tournament_record_match.py`. Bracket de 4 lutadores; pega a 2ª luta da rodada 1 (não a corrente); `record_match_result(winner_name=<lutador dela>, match=luta)` devolve `True` e `luta.completed is True`. Hoje o parâmetro não existe e a chamada sem ele devolve `False`.
- **Origem:** `nf-live-ui.md` #C1

### MOT-103 — Live: `!arena` grátis depois do primeiro pago, e o comando pago que cai em cooldown, teto ou saturação some  (médio)
- **Onde:** `neural_fights/live/policy.py:103-144` (`PolicyEngine.avaliar`: os ADIAR de `_checar_limites` l.157/168 e de `_checar_saturacao` l.181 saem antes do pagamento, l.140-142); `neural_fights/live/commands.py:223-235` (`CommandRouter._adiar`) e `:325-348` (`criar_preparador`: "último da fila vence")
- **Defeito:** (a) Depois do 1º `!arena` pago, o `ADIAR teto_do_round` sai antes de conferir créditos. `_adiar` põe na fila sem `registrar_uso`, e quem pagou 0 escolhe a arena; isso foi provado. (b) Comando só `ROUND_ATIVO` (`!curar`, `!meteoro`…) que cai em ADIAR termina `ADIADO` sem fila e sem reaplicação; provado: `fila_pendente=0`.
- **Conserto:** em `avaliar`, calcular `pago = privilegiado or value_units >= custo` logo depois do `somente_moderador`. Se não for `pago`, devolver `RECUSAR creditos_insuficientes` antes de `_checar_limites` e `_checar_saturacao`. A ordem "pagamento por último" continua valendo para os RECUSAR (que não cobram); o que muda é só que um ADIAR nunca sai para quem não pagou. Em `_adiar`, quando enfileira, chamar `self.policy.registrar_uso(command_id, viewer.viewer_id, custo=custo)`. Para comando sem `ENTRE_ROUNDS`, devolver `STATUS_RECUSADO` com detalhe `"<motivo> reembolso"` (o overlay já mostra toast de recusa quando `value_units > 0`), em vez de `ADIADO` mudo. No preparador, ver as decisões do Adrian (primeiro ou último pago vence).
- **Teste que prova:** `tests/test_live_command_regressions.py::test_arena_sem_credito_nao_entra_na_fila_depois_do_pago`. Registro `:memory:`, `simulador=None`: `!arena X` pago com 150 e `!arena Y` com 0. O segundo dá `RECUSADO creditos_insuficientes`, `fila_pendente()==1` e plano `cenario == X`. E `::test_curar_pago_em_cooldown_vira_recusa_com_reembolso`: policy com relógio fixo, dois `!curar` pagos com 1 s de intervalo; o segundo dá status `RECUSADO` com `"reembolso"` no detalhe. Hoje dá `ADIADO`.
- **Origem:** `nf-live-ui.md` #C2 e #C3

### MOT-104 — Live: lutador aposentado nunca volta; `!entrar` dá IntegrityError para sempre  (médio)
- **Onde:** `neural_fights/live/registry.py:556` (`LiveRegistry.criar_lutador`: `fighter_id_de(viewer.viewer_id)` com `ordinal=0` fixo; `fighter_id` é PK e `catalog_name` é UNIQUE sem filtro de `retired_at`)
- **Defeito:** depois de `aposentar_lutador`, o próximo `criar_lutador` gera o mesmo id e o INSERT falha; provado: `IntegrityError UNIQUE fighter.catalog_name`.
- **Conserto:** em `criar_lutador`, antes de gerar o id, contar os lutadores do espectador: `ordinal = SELECT COUNT(*) FROM fighter WHERE viewer_id=?`. Use `fighter_id_de(viewer.viewer_id, ordinal)`. O lutador novo é outro personagem, semeado pelo id novo; o histórico do antigo fica.
- **Teste que prova:** `tests/test_live_session_regressions.py::test_aposentado_ganha_lutador_novo`. Registro `:memory:`: cria, aposenta e cria de novo sem exceção; o `fighter_id` do novo é diferente e `obter_lutador_ativo` devolve o novo.
- **Origem:** `nf-live-ui.md` #C4

### MOT-105 — Fonte do YouTube: todo 403 vira "credencial ruim" e encerra; a quota nunca zera; chat e token nunca são refeitos  (médio)
- **Onde:** `neural_fights/live/sources/youtube.py:298-315` (`_transporte_urllib`), `:460-470` (`YouTubeChatSource._executar`), `:262-293` (`Quota`), `:425-439` (`buscar_pagina`)
- **Defeito:** 403 `quotaExceeded`/`rateLimitExceeded` encerra a thread, contra a invariante 3 do próprio módulo. `Quota.gastas` nunca volta a zero (vira o dia e o intervalo continua em 60 s). Chat encerrado ou `pageToken` inválido repete o erro com o mesmo token para sempre.
- **Conserto:** em `_transporte_urllib`, ler `errors[0].reason` do corpo JSON. Se for `quotaExceeded`, `rateLimitExceeded` ou `dailyLimitExceeded`, levantar um novo `ErroDeQuota(ErroDeTransporte)`. Se for `liveChatEnded`, `liveChatNotFound`, `liveChatDisabled` ou `pageTokenInvalid` (inclusive em 400/404), levantar `ErroDeChat(ErroDeTransporte)`. Só os demais 401/403 continuam `ErroDeAutenticacao`. Em `_executar`: `ErroDeQuota` espera `INTERVALO_MAXIMO` e continua; `ErroDeChat` zera `self._live_chat_id = ""` e `self._page_token = ""` e continua com backoff. Em `Quota`, guardar `dia` (data em America/Los_Angeles, a meia-noite PT da Google) e zerar `gastas` quando o dia muda, dentro de `gastar` e `fracao_usada`.
- **Teste que prova:** `tests/test_live_youtube_regressions.py`. (1) Transporte dublado que levanta `HTTPError 403` com corpo `{"error":{"errors":[{"reason":"quotaExceeded"}]}}`: a fonte continua viva depois de uma volta (`thread.is_alive()`), e hoje encerra. (2) Corpo `liveChatEnded`: na volta seguinte `resolver_live_chat_id` é chamado de novo. (3) `Quota` com relógio de data injetado: depois de trocar o dia, `gastas == 0`. Atenção: o teste atual da l.439, que trata 403 só como autenticação, precisa passar a usar `reason` de credencial (`forbidden` sem quota).
- **Origem:** `nf-live-ui.md` #C10

### MOT-106 — Live: o nome no HUD congela no `!entrar`; renomear e a blocklist posterior não chegam  (médio)
- **Onde:** `neural_fights/live/registry.py:334-345` (`LiveRegistry.mapa_nomes_exibicao`)
- **Defeito:** lê `fighter.display_name`, que é copiado uma vez no `!entrar`; `registrar_viewer` só atualiza `viewer`. Provado: o espectador renomeado para `NomeNovo` continua aparecendo como `Fulano`. Um termo bloqueado depois continua na tela.
- **Conserto:** `SELECT f.catalog_name, v.display_name_raw, v.viewer_id, v.platform FROM fighter f JOIN viewer v ON v.viewer_id = f.viewer_id WHERE f.retired_at IS NULL`. Para cada linha, devolver `self.sanitizar(display_name_raw, viewer_id=..., platform=...).valor`, que reaplica a blocklist viva.
- **Teste que prova:** `tests/test_live_session_regressions.py::test_hud_usa_nome_atual_e_blocklist_viva`. Cria um lutador com o nome `NomeAntigo`, chama `registrar_viewer` com `NomeNovo`: o mapa devolve `NomeNovo`. Depois `bloquear_termo("nomenovo")`: o mapa não contém `NomeNovo`.
- **Origem:** `nf-live-ui.md` #C12

### MOT-107 — Forja: só visitar o passo 3 já arredonda o dano para inteiro  (médio)
- **Onde:** `neural_fights/ui/view_armas.py:592-597` (passo de stats: `tk.Scale(from_=1, to=50)` sem `resolution`, seguido de `set(dano)`)
- **Defeito:** `set(12.5)` numa janela visível dispara `command('13')`, e `dados_arma["dano"]` vira 13.0 sem o Adrian tocar no controle. Provado com Tk de verdade.
- **Conserto:** passar `resolution=0.1` (o dano vem de `10 * mod_dano`, l.547) no `tk.Scale` do dano. Aplicar o mesmo cuidado aos sliders de geometria da l.632 se os valores lá forem fracionários (ver `GEOMETRIA` de cada tipo).
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_passo3_da_forja_nao_arredonda_dano`. `TelaArmas` com `dados_arma["dano"]=12.5`, chama o passo 3, `update()` algumas vezes, e afirma `dados_arma["dano"] == 12.5`. Hoje dá 13.0.
- **Origem:** `nf-live-ui.md` #C17

### MOT-108 — Live: a saturação conta a mesma área duas vezes e nunca decresce no round  (médio)
- **Onde:** `neural_fights/live/policy.py:172-182` (`_checar_saturacao`) e `:197-198` (`registrar_uso`)
- **Defeito:** `vivas = len(sim.areas)` (que já inclui as áreas de espectador; `_aplicar_global` cria 2 por comando, `effects.py:122-123`) `+ round.areas_de_espectador` (só cresce). Dois `!meteoro` já batem o teto 6 e, pelo MOT-103, o terceiro pagante cai em recusa.
- **Conserto:** quando há `estado_mundo["areas"]`, usar só ele (`vivas = int(estado_mundo["areas"])`); somar `round.areas_de_espectador` só quando `estado_mundo` vem vazio (sem simulador). Ou remover o contador e contar as áreas vivas com origem de espectador.
- **Teste que prova:** `tests/test_live_command_regressions.py::test_saturacao_nao_conta_duas_vezes`. `PolicyEngine` com 2 `registrar_uso("meteoro")` e `estado_mundo={"areas": 0}` (as áreas já expiraram): `avaliar("meteoro", ...)` dá `APLICAR`. Hoje dá `ADIAR saturacao`.
- **Origem:** `nf-live-ui.md` #C18

### MOT-109 — Gravador: o ffmpeg falha e a resposta é `sucesso: True` com um mp4 que não abre  (médio)
- **Onde:** `neural_fights/recording/fight_recorder.py:740-758` (`gravar_luta`: `processo.wait()` sem olhar o código) e `_abrir_ffmpeg`; o mesmo em `neural_fights/recording/skill_demo.py:255-261`
- **Defeito:** o código de saída do ffmpeg é ignorado. Se ele falha no trailer (disco cheio, arquivo trancado), sai `sucesso: True`, e o `capture.py` leva para o fight.json um mp4 sem `moov`. Falha precoce vira `BrokenPipeError` sem o motivo.
- **Conserto:** abrir o ffmpeg com `stderr=subprocess.PIPE` (ou para um arquivo temporário, para não encher o pipe). Envolver cada `stdin.write` em `try/except (BrokenPipeError, OSError)` que fecha, espera e levanta `RuntimeError(f"ffmpeg falhou: {stderr[-800:]}")`. No fim, `codigo = processo.wait()`; se `codigo != 0` ou se `Path(saida)` não existir ou tiver 0 bytes, `resultado["sucesso"] = False` e `resultado["erro"] = "ffmpeg saiu com {codigo}: {stderr[-800:]}"`.
- **Teste que prova:** `neural_fights/recording/test_fight_recorder_ffmpeg.py`. Monkeypatch de `_abrir_ffmpeg` com um dublê de `Popen` cujo `wait()` devolve 1 e cujo `stderr` diz "Error writing trailer": `gravar_luta(..., max_duracao=0.5)` dá `sucesso is False` com "trailer" no erro. Hoje dá `True`.
- **Origem:** `nf-recording-cli.md` #1 (e #4c)

### MOT-110 — skill_demo: a demo boa é destruída antes de saber se a nova vai sair; o ffmpeg travado não é morto  (médio)
- **Onde:** `neural_fights/recording/skill_demo.py:96` (`gravar_demo`: `_abrir_ffmpeg(destino, ...)` com `-y` no destino final, l.199-203; `return` precoce em "cast recusado", l.213-217; `finally`, l.255-261)
- **Defeito:** a demo anterior é truncada assim que o ffmpeg abre; se o cast falha, fica um mp4 quebrado. O manifest não muda, e com o mesmo hash a skill é pulada para sempre (`gerar`, l.290-296). Se o ffmpeg trava, o `TimeoutExpired` é engolido e o processo fica vivo.
- **Conserto:** gravar em `destino.with_name(destino.stem + ".tmp.mp4")`. No `finally`: `stdin.close()`; `codigo = ffmpeg.wait(timeout=60)`; em `subprocess.TimeoutExpired`, `ffmpeg.kill(); ffmpeg.wait()`. Só se `resultado["ok"]` e `codigo == 0`, fazer `tmp.replace(destino)`; senão `tmp.unlink(missing_ok=True)` e anotar o código em `resultado["erro"]`.
- **Teste que prova:** `neural_fights/recording/test_skill_demo_regressions.py::test_demo_anterior_sobrevive_a_cast_recusado`. Destino com um "mp4 anterior" de bytes conhecidos e monkeypatch de `usar_skill_classe` para `False`: depois de `gravar_demo(nome, saida=destino)`, o destino tem os mesmos bytes e não sobra `.tmp.mp4`. Hoje o arquivo é truncado.
- **Origem:** `nf-recording-cli.md` #4

### MOT-111 — Ateliê aceita NaN e infinito e grava `animacao.json` inválido  (médio)
- **Onde:** `neural_fights/tools/atelie_animacoes.py:56-93` (`validar`) e `:117` (`salvar`: `json.dumps` sem `allow_nan=False`)
- **Defeito:** `float("nan")` passa em `fps <= 0`; escala, rotação, âncora e durações não são checadas. O JSON sai com `NaN`, que o `JSON.parse` do app e o Godot recusam.
- **Conserto:** depois de converter, exigir `math.isfinite` em `fps`, `escala`, `rotacao`, `ancora.x/y` e em cada `float(v)` de `duracao_por_quadro`; se falhar, `ValueError("<campo> precisa ser um numero finito")`. Em todo `json.dumps` do módulo (`salvar`, `salvar_ajustes`), usar `allow_nan=False`.
- **Teste que prova:** `neural_fights/tools/test_atelie_animacoes.py::test_nan_e_recusado`. `validar({"quadros":[{x:0,y:0,w:1,h:1}], "fps":"nan", "ancora":{"x":0,"y":0}}, (1,1))` levanta `ValueError`; o mesmo com `escala: "inf"`. Hoje passa.
- **Origem:** `nf-tools.md` #1

### MOT-112 — Ateliê: um ajuste malformado aceito pelo endpoint derruba a árvore inteira  (médio)
- **Onde:** `neural_fights/tools/atelie_animacoes.py:314-318` (`salvar_ajustes`) e `:346-356` (`arvore`); a rota é `remoto/api_http.py:1496`
- **Defeito:** `salvar_ajustes` grava `novas` com qualquer item; `arvore` faz `nova.get(...)` e dá `AttributeError`, e o `GET /api/animacoes/arvore` passa a dar 500 em toda abertura do Ateliê.
- **Conserto:** em `salvar_ajustes`, exigir que cada item de `novas` seja `dict` com `peca`, `estado` e `id` passando por `_id(...)`, e que cada item de `escondidas` seja `str`; senão `ValueError("ajustes invalidos")`. Em `ajustes()` (leitura), filtrar silenciosamente os itens que não sejam `dict`/`str`, para um arquivo já estragado não derrubar a árvore.
- **Teste que prova:** `neural_fights/tools/test_atelie_animacoes.py::test_ajuste_malformado`. `salvar_ajustes({"novas":["x"],"escondidas":[]})` levanta `ValueError`. E, com `AJUSTES` em pasta temporária contendo `{"novas":["x"]}` à mão, `arvore()` não levanta. Hoje dá `AttributeError`.
- **Origem:** `nf-tools.md` #2

### MOT-113 — Launcher: a roda do mouse do wizard de personagens rola o canvas escondido da tela de Sons  (baixo)
- **Onde:** `neural_fights/ui/view_chars.py:196` e `neural_fights/ui/view_sons.py:361` (`bind_all("<MouseWheel>")`)
- **Defeito:** o último `bind_all` (TelaSons, a última construída em `main.py:68`) vence, e o wizard (16 classes no passo 2) não rola.
- **Conserto:** trocar os dois `bind_all` por um `bind("<Enter>")` no canvas, que faz `bind_all` da sua função, e um `bind("<Leave>")` que faz `unbind_all("<MouseWheel>")`. Ou `bind` no canvas e nos filhos, como `canvas_armas` já faz (l.1139-1175).
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_roda_do_mouse_rola_o_wizard`. `SistemaApp`, `show_frame("TelaPersonagens")`, passo 2, `event_generate("<MouseWheel>", delta=-120)` sobre `canvas_wizard` com o ponteiro dentro: o `yview()[0]` do wizard aumenta e o canvas de Sons não muda.
- **Origem:** `nf-live-ui.md` #C5

### MOT-114 — Launcher: a prévia do lutador some quando há arma (uma PhotoImage por canvas)  (baixo)
- **Onde:** `neural_fights/ui/arte_atelie.py:146-156` (`desenhar`: `canvas._arte_atelie_foto = foto`), chamado duas vezes por quadro em `neural_fights/ui/theme.py:173-175`
- **Defeito:** a imagem da arma sobrescreve a única referência, e a `PhotoImage` do corpo é coletada (o item fica sem imagem).
- **Conserto:** guardar num dict por canvas: `getattr(canvas, "_arte_atelie_fotos", None) or {}` com a chave `(x, y, id(arte))` (ou a tag do item), e limpar o dict quando `limpar=True`.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_corpo_e_arma_coexistem`. Duas `desenhar` com `limpar=False`, `gc.collect()`: as duas `PhotoImage` continuam em `canvas.tk.call("image","names")`.
- **Origem:** `nf-live-ui.md` #C6

### MOT-115 — Broadcast: o lower-third mostra "!?" para todo comando  (baixo)
- **Onde:** `neural_fights/live/broadcast.py:83` (`BroadcastOverlay.notificar_comando`: `getattr(evento, "texto", "")`)
- **Defeito:** o campo do `ViewerEvent` é `text`; o teste usa um `SimpleNamespace(texto=...)` que esconde o bug. Provado: verbo `'!?'`.
- **Conserto:** `getattr(evento, "text", "")`. No teste `tests/test_broadcast_show_regressions.py` (l.88, 108, 122), trocar o `SimpleNamespace(texto=...)` por `ViewerEvent(platform="yt", viewer_id="v1", viewer_name="Ana", kind="CHAT", text="!meteoro", value_units=300)`.
- **Teste que prova:** o mesmo arquivo, com `ViewerEvent` de verdade: `_lower_thirds[-1]["verbo"] == "!meteoro"`. Hoje dá `"!?"`.
- **Origem:** `nf-live-ui.md` #C8

### MOT-116 — Launcher: o rodapé da Arena fica atrás da barra de tarefas no 1366x768  (baixo)
- **Onde:** `neural_fights/ui/main.py:40-44` (`SistemaApp.__init__`: `geometry`/`maxsize` com a altura da área útil sem descontar a moldura)
- **Defeito:** cliente de 720 px mais a barra de título passam da área útil de 728, e `lbl_progresso_palco` (`view_luta.py:93`) fica tapado.
- **Conserto:** depois de `geometry`, chamar `update_idletasks()`, medir `moldura = self.winfo_rooty() - self.winfo_y()` e reaplicar `geometry(f"{w}x{min(720, altura - moldura)}+{esq}+{topo}")` e `maxsize(largura, altura - moldura)`.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_janela_cabe_na_area_util`. Afirma `app.winfo_rooty() + app.winfo_height() <= topo + altura_util`, usando `area_util_tela` (e não a própria janela, como o teste atual).
- **Origem:** `nf-live-ui.md` #C7

### MOT-117 — Launcher: fechar com render em andamento dá RuntimeError na thread e deixa o Godot órfão  (baixo)
- **Onde:** `neural_fights/ui/view_luta.py:340-370` (`TelaLuta._iniciar_palco.trabalho`); `neural_fights/ui/view_torneio.py:271-306`; `random_builds/builds/palco/godot.py:51` (`_rodar`) e `:140` (`abrir_previa`, `Popen` sem referência)
- **Defeito:** `self.after` é chamado de outra thread depois do `destroy`, e ninguém mata o Godot/ffmpeg filho.
- **Conserto:** a thread põe o desfecho numa `queue.Queue`; um `after(200, self._drenar_fila_palco)` na thread principal consome. `SistemaApp` registra `protocol("WM_DELETE_WINDOW", self._fechar)`, que sinaliza um `threading.Event` de cancelamento. Em `godot._rodar`, trocar `subprocess.run` por `Popen` guardado num registro global (`_PROCESSOS_VIVOS`), com uma função `encerrar_todos()` que `_fechar` chama.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_fechar_durante_render_nao_quebra_thread`. Monkeypatch de `exportar_palco_selecao` para dormir 0,5 s; `_iniciar_palco("mp4")`; `app.destroy()`; `join` da thread; o `threading.excepthook` dublado não recebe nada.
- **Origem:** `nf-live-ui.md` #C11

### MOT-118 — Launcher: o wizard de personagens mostra stats com fórmulas que o motor não usa  (baixo)
- **Onde:** `neural_fights/ui/view_chars.py:262-275` (`TelaPersonagens.criar_resumo_stats`)
- **Defeito:** HP=100+força·10 e vel=(10−tamanho·2)·mod; o modelo usa `velocidade_base_ms·fator_peso·fator_forca` e `resistencia` (`models/characters.py:68-71`).
- **Conserto:** montar um `Personagem` temporário com `self.dados_char`, como `salvar_personagem` faz, e mostrar `p.velocidade` (m/s) e `p.resistencia` (os mesmos rótulos VEL/RES da Arena). Remover as fórmulas locais.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_resumo_do_wizard_bate_com_o_modelo`. Guerreiro de 1,70 m e força 5: o texto do resumo contém `f"{Personagem(...).velocidade:.1f}"`.
- **Origem:** `nf-live-ui.md` #C14

### MOT-119 — Launcher: a lista de armas do passo 6 não atualiza ao voltar da Forja  (baixo)
- **Onde:** `neural_fights/ui/view_chars.py:1236` (`TelaPersonagens.atualizar_dados`: `if self.passo_atual == 5`)
- **Defeito:** o equipamento é o passo 6; o 5 é reconstruído à toa.
- **Conserto:** `if self.passo_atual == 6: self.mostrar_passo(6)`.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_passo6_recarrega_armas`. Passo 6 aberto, acrescenta uma arma em `controller.lista_armas`, chama `atualizar_dados()`: a arma nova aparece no `frame_armas_inner`.
- **Origem:** `nf-live-ui.md` #C15

### MOT-120 — Forja: "Sugerir Tamanhos (baseado no personagem)" nunca vê personagem  (baixo)
- **Onde:** `neural_fights/ui/view_armas.py:658-663` (`aplicar_sugestao_geometria`: `controller.lista_chars`)
- **Defeito:** o atributo é `lista_personagens` (`main.py:55`), então sempre cai em `sugerir_tamanho_arma(None, tipo)`.
- **Conserto:** ler `controller.lista_personagens`. Se houver mais de um, perguntar qual (um combobox simples) ou usar o personagem que está em edição na TelaPersonagens; nunca o `[0]` fixo.
- **Teste que prova:** `neural_fights/ui/test_launcher_regressions.py::test_sugestao_usa_personagem`. Monkeypatch de `sugerir_tamanho_arma` gravando o 1º argumento: depois do clique, ele não é `None`.
- **Origem:** `nf-live-ui.md` #C16

### MOT-121 — Gravador: fps que não divide 60 grava na velocidade errada, fps negativo trava e duração ≤ 0 dá "sucesso"  (baixo)
- **Onde:** `neural_fights/recording/fight_recorder.py:588` (`a_cada`), `:621-623` (laço), `:784-785` (`--fps`, `--max-duracao`); `neural_fights/recording/timeline.py:2543` (mesmo laço em `gravar_timeline`)
- **Defeito:** `a_cada = round(60/fps)` só dá tempo real para divisores de 60 (24 sai a 0,8x, 50 a 0,83x, e acima de 60 acelera). Com fps < 0 o laço nunca termina; com `max_duracao <= 0` sai `sucesso` com 0 s.
- **Conserto:** no começo de `gravar_luta` e de `gravar_timeline`: `if fps_saida < 1 or 60 % fps_saida: raise ValueError("fps precisa dividir 60")` e `if max_duracao <= 0: raise ValueError(...)`. Nas duas CLIs, um `type=` que rejeita isso com `parser.error`.
- **Teste que prova:** `neural_fights/recording/test_fight_recorder_validacao.py`. `gravar_luta(..., fps_saida=-30)`, `fps_saida=24` e `max_duracao=0` levantam `ValueError` imediatamente (hoje: laço infinito, sucesso com 0,8x e sucesso com 0 s); `main(["--fps","-30",...])` dá `SystemExit(2)`.
- **Origem:** `nf-recording-cli.md` #2, #3 e auditoria rasa (fps > 60, `--max-duracao 0`)

### MOT-122 — CLIs aceitam argumentos inválidos (roster 1, câmera livre, resolução sem "x", skill inexistente)  (baixo)
- **Onde:** `neural_fights/cli/live.py:33-37` (`_roster`) e `:99-100`; `neural_fights/recording/timeline.py:2618-2632`; `neural_fights/recording/fight_recorder.py:788-789`; `neural_fights/recording/skill_demo.py:109-121`
- **Defeito:** `--roster 1` dá `IndexError`, `--roster -1` corta em silêncio, `--camera foo` é aceito, `--resolucao 1080` dá traceback e `--skill "Nao Existe"` vira "skill sentinela".
- **Conserto:** em `_roster`, validar depois do corte (`if len(corte) < 2: raise RuntimeError(...)`) e no parser usar `type=` que rejeita `< 2` para `--roster` e `< 1` para `--max-partidas`. Em `timeline.py`, usar `choices=CAMERAS` e `parse_resolucao` (`fight_recorder.py:452`) com `parser.error` quando der `None`. Em `skill_demo.gravar_demo`, fazer `if nome not in SKILL_DB: erro "skill desconhecida"` antes de `derivar_contrato`.
- **Teste que prova:** `tests/test_cli_validacao.py`. `live.build_parser().parse_args(["--roster","1"])` dá `SystemExit`; `timeline.build_parser().parse_args([... "--camera","foo"])` dá `SystemExit`; `gravar_demo("Nao Existe", sem_video=True)["erro"] == "skill desconhecida"`.
- **Origem:** `nf-recording-cli.md` #5 e #10

### MOT-123 — Gravador sai com código 0 quando a timeline ou o som pedidos não saíram  (baixo)
- **Onde:** `neural_fights/recording/fight_recorder.py:845` (`main`)
- **Defeito:** `_salvar_timeline`/`_embutir_som` devolvem o erro no dicionário, mas o exit é 0. Hoje nenhum chamador de produção passa `--timeline`.
- **Conserto:** `if resultado.get("sucesso") and (resultado.get("erro_timeline") or (not args.sem_som and resultado.get("som_no_video") is False)): print(erro, file=sys.stderr); return 3`.
- **Teste que prova:** `neural_fights/recording/test_fight_recorder_validacao.py::test_timeline_falha_da_exit_3`. `main([... "--sem-video", "--timeline", r"Z:\nao_existe\x.gcpf", "--max-duracao", "0.5"])` dá `3`.
- **Origem:** `nf-recording-cli.md` #6

### MOT-124 — Torneio: chave sem seed, seed do retry colidindo com a luta seguinte, estatísticas e estado mortos  (baixo)
- **Onde:** `neural_fights/tournament/tournament_mode.py:214` e `:231` (`random.shuffle` global), `:1310-1314` (`attempt_seed`), `:143-149`/`:248-254` (stats), `:87` (`ROUND_COMPLETE`), `:1348-1352` ("Duplo KO")
- **Defeito:** dois torneios iguais dão chaves diferentes; o retry da luta k usa o seed inicial da luta k+1; `fastest_ko`, `longest_fight` e `most_aggressive` são sempre `None`; `ROUND_COMPLETE` nunca acontece.
- **Conserto:** `Tournament.__init__(..., seed: int | None = None)` cria `self._rng = random.Random(seed)`, usado nos dois `shuffle`; o seed é persistido em `save_state`/`load_state`. `attempt_seed = seed + match_id * (retry_limit + 1) + attempt`. Em `record_match_result`: `fastest_ko = min(...)` e `longest_fight = max(...)` pela `duration` quando `"KO" in ko_type` (ou remover os três campos e o `ROUND_COMPLETE`; ver decisões).
- **Teste que prova:** `tests/test_tournament_record_match.py::test_chave_reproduzivel_e_seeds_distintos`. `Tournament(seed=7)` com os mesmos 8 nomes, duas vezes: a mesma ordem. O conjunto de `attempt_seed` de todas as lutas com `retry_limit=2` não tem repetição.
- **Origem:** `nf-recording-cli.md` #7, #8 e #9

### MOT-125 — Live: journal sem `viewer_id`  (baixo)
- **Onde:** `neural_fights/live/commands.py:97-103` (`CommandRouter.processar`)
- **Defeito:** `registrar_evento` é chamado sem `viewer_id`; provado: as 3 linhas com `None`.
- **Conserto:** passar `viewer_id=viewer_id_de(evento.platform, evento.viewer_id)` (de `live/registry.py:148`).
- **Teste que prova:** `tests/test_live_command_regressions.py::test_journal_guarda_viewer`. Depois de `processar`, `SELECT viewer_id FROM event_journal` dá `viewer_id_de("yt","v1")`.
- **Origem:** `nf-live-ui.md` #C13

### MOT-126 — RecordingSource perde o resto da fila interna ao parar e abre o arquivo antes da interna subir  (baixo)
- **Onde:** `neural_fights/live/sources/replay.py:154-165` (`RecordingSource.start`/`stop`)
- **Defeito:** `start` abre o arquivo antes de `interna.start()`, e o handle vaza se a interna falhar. `stop` para a interna sem drenar a fila dela, e os últimos eventos não vão para o replay.
- **Conserto:** em `start`, chamar `self._interna.start()` antes de abrir o arquivo; se a abertura falhar, `self._interna.stop()`. Em `stop`, depois de `self._interna.stop()`, drenar `self._interna.drenar()` (ou o `get_nowait` da fila) e gravar e publicar cada evento antes de `super().stop()` e de fechar o arquivo.
- **Teste que prova:** `tests/test_live_session_regressions.py::test_recording_grava_o_que_sobrou`. Uma `ScriptedEventSource` com 5 eventos e `stop()` imediato: o JSONL tem 5 linhas.
- **Origem:** `nf-live-ui.md` #C19

### MOT-127 — OAuth do YouTube fica esperando para sempre quando o consentimento é recusado  (baixo)
- **Onde:** `neural_fights/tools/youtube_oauth.py:191-219` (`_receber_codigo`)
- **Defeito:** `?error=access_denied` só responde "tente de novo"; o laço `while "code" not in codigo` continua e o comando não retorna.
- **Conserto:** no handler, se `"error" in params`, guardar `codigo["error"] = params["error"][0]`; trocar o laço para `while not codigo:`; depois do laço, `if "error" in codigo: raise RuntimeError(f"autorizacao recusada: {codigo['error']}")`; o `main` trata a exceção e devolve exit 1.
- **Teste que prova:** `neural_fights/tools/test_youtube_oauth.py::test_recusa_encerra`. A thread com `_receber_codigo(porta_livre)`; `urlopen(".../?error=access_denied")`; `join(2)`: a thread terminou e levantou `RuntimeError`.
- **Origem:** `nf-tools.md` #3

### MOT-128 — Timeline: temporário com nome fixo  (baixo)
- **Onde:** `neural_fights/recording/timeline_arquivo.py:144` (`salvar`)
- **Defeito:** `caminho.name + ".tmp"` é o mesmo para dois gravadores no mesmo destino; um troca o arquivo do outro.
- **Conserto:** `temporario = caminho.with_name(f"{caminho.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")`; em exceção, `temporario.unlink(missing_ok=True)`.
- **Teste que prova:** `neural_fights/recording/test_timeline_arquivo.py::test_salvar_nao_usa_tmp_fixo`. Monkeypatch de `Path.write_bytes` capturando o nome: ele difere entre duas chamadas.
- **Origem:** auditoria rasa, citada em `nf-recording-cli.md` ("Os três já apontados")

### MOT-129 — Código morto (funções públicas sem chamador)  (baixo)
- **Onde:** `live/registry.py` (`ja_processado`, `stats_do_lutador`, `definir_banimento`), `live/roster.py` (`todos_os_nomes`, `recarregar_catalogo`), `ui/view_luta.py:380` (`atualizar_previews`), `ui/view_torneio.py` (`launch_tournament_window`), `utils/__init__.py` (`random_range`, `random_color_variation`, `rotate_point`, `angle_between`, `normalize_vector`, `ease_out`, `ease_in_out`), `utils/palette.py` (`hex_to_rgb`), `utils/fonts.py` (`limpar_cache`), `tournament_mode.py` (`run_single_match_visual`, `_default_weapon`, o ramo "trunca" de `_adjust_to_power_of_two`), `recording/timeline.py` (`definir_remapeamento`), `recording/timeline_arquivo.py` (`flags_ligadas`, `duracao_do_clipe`, `tempo_no_clipe`, `tempo_na_gravacao`)
- **Conserto:** remover, depois de um `grep -rn` em todo o repositório (inclusive `ferramentas/`, `painel/`, `historias/`) e de rodar a suíte. NÃO remover `executar_teste_stress`/`HeadlessBattle`: `executar_teste_stress` é chamado em `cli/headless.py:171` (o relatório errou nisso). `definir_banimento` pode virar o caminho de moderação em vez de sair; ver decisões.
- **Teste que prova:** a suíte `neural_fights` e `random_builds` verde depois da remoção, mais `python -m ruff check` sem `F401`/`F821` novos.
- **Origem:** `nf-live-ui.md` #C20, `nf-recording-cli.md` #11


---

## Já consertados
- Nenhum. Não há commit nestes arquivos depois de 11/10, exceto o f5f8cd3 (só `timeline_arquivo.validar`), e nenhum conserto em ramo não mesclado.

## Alarmes falsos
- Nenhum defeito inteiro é falso. Correções parciais:
  - `nf-core-a.md` #7: "sem decaimento no brain" é falso. `brain.raiva` é uma property delegada ao EmotionSystem, que decai em `emotions.py:104`. O "sem teto" continua valendo (MOT-3).
  - `nf-core-b.md` C9, parte "7 skills sem nenhuma fonte": é de propósito e está documentado em `models/constants.py:561` (`SKILLS_FORA_DE_ROTACAO`). O resto do C9 (funções sem chamador) continua aberto.
  - `nf-recording-cli.md` #11: `executar_teste_stress` não é código morto. É chamado em `cli/headless.py:171`.
  - `nf-recording-cli.md` #9a: o "duplo KO inalcançável" não está provado: se `_finalizar_round` já recebeu um `winner_slot`, `reason == "double_ko"` vem com vencedor. O item segue ABERTO pela colisão de seed (#9b).
  - `nf-simulation.md`: 0 confirmados. Os "não confirmados" dele estão coerentes com o código.
  - Esta verificação também corrigiu o MOT-101: o "Gerar Roster" deixa, sim, a cópia `_backup-*` (`database._copia_antes_de_perder`, chamada por `salvar_database`), mas ninguém é avisado.

## Decisões que são do Adrian
- **Quirks (MOT-30):** implementar os 29 efeitos prometidos, ou tirá-los do sorteio (o lutador perde rótulos que hoje aparecem como personalidade).
- **Cadência no stun (MOT-5):** o atordoamento pausa o relógio de ataque (como hoje, punição mais longa) ou corre em paralelo? Muda o ritmo de toda luta.
- **Lava do Vulcão/Inferno (MOT-32):** ligar o dano das poças, que o catálogo promete ("Poças de lava (dano!)"), ou tirar a promessa.
- **Som da vitória (MOT-27):** `arena_victory` toca hoje a abertura da arena quase muda (0,03). Que som deve tocar? Só ele julga o som.
- **Volume relativo dos golpes (MOT-13):** com o conserto do pan, os golpes caem até 1,8× em relação a UI e arena; ele precisa ouvir antes de valer para os vídeos.
- **Gerar Roster (MOT-101):** pergunta e substitui com cópia, OU acrescenta ao catálogo (`substituir=False`), OU grava num catálogo separado só de torneio?
- **`!arena` com dois pagantes no mesmo round (MOT-103):** vale o primeiro que pagou ou o último?
- **Comando pago que não coube (MOT-103):** recusar e avisar o reembolso na tela, ou guardar e aplicar quando o cooldown passar?
- **Estatísticas do torneio (MOT-124):** preencher KO mais rápido, luta mais longa e mais agressivo, ou tirar do save?
- **Moderação da live (MOT-129):** ligar `definir_banimento` a um comando de moderador no chat/CLI, ou remover?
