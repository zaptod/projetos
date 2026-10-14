# Consertos — builds (verificação de 14/10/2026)

- **Parte:** `builds`, com o banco de personagens (`neural_fights/data`), o launcher (`neural_fights/ui`) e a Identity
- **Relatórios de origem:** `nf-data.md` (11), `builds-conteudo.md` (8, o #8 aberto em 8a–8d), `builds-palco-video.md` (1), `pipeline-builds.md` (3), `identity.md` (1)
- **Contagem:** 26 abertos / 0 consertados / 1 falso (27 linhas no TSV)
- Nenhum commit depois de 11/10 mexeu nestes pontos. O `873f2e6` (11/10) mudou `arena/ledger.py` (trava) e `controller.py` (`_next_id`). O builds-conteudo já o descontava, e o 8d continua aberto. Os `a34b355`/`f5f8cd3` não tocam estes arquivos. Nenhum ramo `delegar/*` nem a worktree `agent-ac362a0bfcc5f30f8` tem diff em `neural_fights/data`, `tools/gerador_database.py`, `nf_bridge/exporter.py` ou `ui/view_*`.
- As provas rodaram em cópias do banco real, em `E:\tmp_pytest\bld-rt-*`, com `NEURAL_FIGHTS_RUNTIME_DIR` definido antes do import. Do banco de verdade só se leu, e nada foi gravado nele. Scripts: `scratchpad\bld_prova_db.py`, `bld_corrida.py` (dois processos), `bld_prova_conteudo.py`, `bld_prova_empate.py` e `bld_faixas.py`.
- **Correções ao relatório nf-data:**
  - o `genero` NÃO é lido do banco pelo prompt de identidade: `identity/prompt.py:180` lê `generation["character"]`. Hoje nada lê `genero`, `tipo_projetil` ou `tipo_orbital` do banco. A perda é real, mas por enquanto não aparece em nenhum vídeo;
  - o banco real tem `forca` até 10,5 e `mana` até 9,6. A faixa "4,5–8 / 3–6" do relatório recusaria o banco atual (ver BLD-15).

---

### BLD-1 — Launcher grava a lista velha por cima do banco e reescreve todo registro pelo modelo  (crítico)
- **Onde:** `neural_fights/data/database.py:1206-1217` (`salvar_lista_armas`, `salvar_lista_chars`), chamados por `neural_fights/ui/view_chars.py:1286` (salvar campeão), `:1310` (deletar campeão) e `ui/view_armas.py:1135` (forjar arma nova). Também `ui/view_armas.py:1129` → `database.py:958` (`atualizar_arma` troca o dict inteiro por `Arma.to_dict()`) e `ui/view_torneio.py:356-368` (`generate_roster`: `gerador_database.salvar_database(armas, personagens)` com `substituir=True` e sem confirmação).
- **Defeito:** a API só sabe "troque a lista inteira". Duas coisas se perdem.
  - **Personagens da roleta.** A lista em memória do launcher (`controller.lista_personagens`, recarregada só ao trocar de aba, `ui/main.py:79-92`) vai ao disco e apaga o que a roleta inseriu enquanto a aba estava aberta. Prova: 143 → roleta → 144 → salvar no launcher → 143, "sobreviveu? False". Fica só um `_backup-*` que ninguém lê.
  - **Campos que o modelo não conhece.** Todo registro passa por `to_dict()` e perde os campos fora do modelo. Prova na cópia do banco real: `genero` sumiu de 71 personagens; `tipo_projetil`/`velocidade_projetil` de 19 armas e `tipo_orbital` de 18. Também mudaram `tamanho` em 105 armas, `critico` em 67 e `velocidade_ataque` em 17 (ruído de ponto flutuante).
- **Conserto:**
  1. **Gravar partindo do disco, dentro de UMA trava.** Em `database.py`, trocar o corpo das duas funções e acrescentar o parâmetro `apagar`:
     ```python
     class ListaDesatualizada(DataValidationError): ...

     @_serializar_persistencia
     def salvar_lista_chars(lista: Sequence[Personagem], *, apagar: Iterable[str] = ()) -> None
     @_serializar_persistencia
     def salvar_lista_armas(lista: Sequence[Arma], *, apagar: Iterable[str] = ()) -> None
     ```
     Regra, dentro da mesma trava:
     - (a) `armas_disco, chars_disco = carregar_database()`.
     - (b) `faltando = {nomes do disco} - {nomes da lista} - set(apagar)`. Se não estiver vazio, `raise ListaDesatualizada(f"o banco mudou desde que o launcher abriu: {sorted(faltando)[:5]}")` sem gravar nada.
     - (c) Para cada objeto da lista, `disco = por_nome.get(obj.nome)`:
       - se `disco` existe e `_modelo(disco).to_dict() == obj.to_dict()` (registro intocado), grava o `disco` **igual, byte a byte**;
       - se foi editado, grava `{**disco, **obj.to_dict()}` (mantém `genero`, `tipo_projetil` e qualquer chave desconhecida);
       - se é novo, grava `obj.to_dict()`.

       `_modelo` é `Arma(**d)` para arma. Para personagem é um helper novo, `_personagem_do_registro(item, pesos_por_nome)`, extraído do laço de `carregar_personagens` (`:1184-1202`).
     - (d) A outra metade do par sai do disco, como hoje. Depois, `salvar_database`.
  2. **`atualizar_arma` (`:999`):** `armas_novas[indice] = {**armas[indice], **nova_arma}` em vez de `nova_arma`.
  3. **Launcher:**
     - `view_chars.deletar_personagem` passa `apagar=[nome]`;
     - nos três chamadores, `except ListaDesatualizada`: `self.controller.recarregar_dados()`, reaplicar a edição (criar/atualizar pelo nome) e gravar de novo. Se ainda falhar, `messagebox.showwarning("O banco mudou", ...)`;
     - depois de todo salvar com sucesso, `self.controller.recarregar_dados()`.
  4. **`view_torneio.generate_roster`:** duas confirmações, com o mesmo texto de `painel/paginas/jogo.py:150-158` ("Isso APAGA o banco atual…" + "Certeza MESMO? Não tem volta.") antes de `salvar_database`.
- **Teste que prova:** `tests/test_banco_launcher_lista_velha_regressions.py`, com runtime em `tmp_path` via `NEURAL_FIGHTS_RUNTIME_DIR` e `monkeypatch` das constantes `ARQUIVO_*_RUNTIME`. Hoje (1) e (2) falham.
  1. `lista = carregar_personagens()`; `gerador_database.salvar_database([arma],[pers], substituir=False)`; `salvar_lista_chars(lista)` levanta `ListaDesatualizada` e o banco continua com o personagem novo.
  2. Personagem com `genero="f"` e arma com `tipo_projetil="faca"` no disco. `salvar_lista_chars(carregar_personagens())` e `salvar_lista_armas(carregar_armas())` deixam o JSON do disco **idêntico** (`==` no conteúdo lido).
  3. Editar a força de um personagem preserva o `genero` dele.
  4. `salvar_lista_chars(lista_sem_X, apagar=["X"])` apaga X e deixa `_backup-*`.
- **Origem:** `nf-data.md` #1 e #3

### BLD-2 — Inserção da roleta lê e grava em duas travas: dois processos perdem um personagem  (crítico)
- **Onde:** `neural_fights/tools/gerador_database.py:662-726` (`salvar_database(..., substituir=False)`: `database.carregar_database()` em `:686` e `database.salvar_database(...)` em `:708`, cada um com a sua trava). Chamado por `random_builds/builds/nf_bridge/exporter.py:140-158` (`insert_into_database`, que ainda faz o seu próprio `carregar_database` + `_nome_unico` antes). Quem insere em paralelo: a rodada `noite` (trava `builds__gerar`, um processo) mais um `main.py generate-video` manual pelo painel (`painel/paginas/videos.py:501`), pelo bot (`remoto/comandos.py:232`) ou pelo terminal. Nada impede os dois juntos.
- **Defeito:** leitura, modificação e escrita em duas travas separadas. Se A e B leem N, B grava N+1 e A grava N+1 com o seu, o de B some. Os dois processos dizem "inserido".
- **Prova com dois processos** (`scratchpad\bld_corrida.py`): dois `subprocess` chamam o `exporter.insert_into_database` real no mesmo runtime. A única intervenção é uma barreira de tempo depois do `carregar_database` real do gerador. Resultado: "B inseriu / A inseriu / no banco: A=True B=False", e ficou 1 `_backup-*`. Com a barreira só na leitura do exporter, os dois sobrevivem: a janela é a do gerador.
- **Conserto:**
  1. **Função nova em `database.py`**, com toda a leitura, checagem e gravação sob a mesma trava (processo + arquivo):
     ```python
     def nome_unico(base: str, usados: set[str]) -> str   # movida do exporter, igual: "X", "X #2", "X #3"...

     @_serializar_persistencia
     def inserir_no_banco(
         armas: Sequence[Mapping[str, Any]],
         personagens: Sequence[Mapping[str, Any]],
         *,
         renomear_em_conflito: bool = False,
         arquivo_armas: str | None = None,
         arquivo_personagens: str | None = None,
     ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
         """Acrescenta ao banco SEM tirar nada; devolve (armas, personagens) com o nome FINAL."""
     ```
     Regra:
     - `existentes = carregar_database(...)`;
     - com `renomear_em_conflito=False`, nome repetido levanta `DataValidationError("nomes ja existentes no banco: ...")`, a mesma mensagem de hoje;
     - com `True`, cada arma recebe `nome_unico`, e um mapa `antigo→novo` reescreve `nome_arma` dos personagens do lote antes de dar `nome_unico` aos personagens;
     - por fim, `salvar_database([*armas_existentes, *armas_novas], [*chars_existentes, *chars_novos], ...)` e devolve as listas novas.
  2. **`gerador_database.salvar_database`:** o ramo `substituir=False` passa a ser só `armas_novas, chars_novos = database.inserir_no_banco(armas, personagens, arquivo_armas=..., arquivo_personagens=...)`, e o retorno continua `(armas_final, personagens_final)` relidos com `database.carregar_database(...)`.
  3. **`exporter.insert_into_database`:** apaga o `carregar_database` e o `_nome_unico` próprios e chama `armas, pers = nf.database.inserir_no_banco([arma], [personagem], renomear_em_conflito=True)`. Devolve `armas[0]["nome"]` e `pers[0]["nome"]`. Hoje a corrida do `_nome_unico` faz o 2º processo levantar "nomes ja existentes" e a build morre; com a função nova, ganha "#2".
  4. Fazer junto com o BLD-7 (trava no TEMP): sem ele, dois processos com `TEMP` diferente continuam sem exclusão.
- **Teste que prova:**
  - `tests/test_banco_insercao_concorrente_regressions.py::test_dois_processos_inserem_os_dois`:
    - `tmp_path` como runtime, com o catálogo empacotado copiado;
    - o mesmo `TEMP` (e, depois do BLD-7, o mesmo runtime) nos dois filhos;
    - dois `subprocess.Popen([sys.executable, "-c", FILHO, rotulo, runtime, barreira])`. Cada filho troca `database.carregar_database` por um embrulho que chama o real e, só na leitura de dentro da inserção, cria `barreira/<rotulo>` e espera o outro arquivo por **no máximo 3 s** (depois do conserto o outro está parado na trava e a espera vence);
    - depois chama `gerador_database.salvar_database([arma_<rotulo>], [pers_<rotulo>], substituir=False)`.

    Afirma: os dois personagens no `personagens.json`, os dois filhos com `returncode == 0` e tudo em menos de 30 s (o teto da trava). Hoje falha com um deles ausente.
  - `random_builds/tests/test_insercao_roleta_concorrente_regressions.py`: o mesmo com `exporter.insert_into_database` e **o mesmo nome** nos dois filhos. Afirma que os dois entram, um como "Nome" e outro como "Nome #2", com `nome_arma` apontando para a arma certa de cada um. Hoje um some ou levanta "nomes ja existentes".
- **Origem:** `nf-data.md` #2

### BLD-3 — A cópia de segurança não cobre arma apagada e se sobrescreve no mesmo segundo  (crítico)
- **Onde:** `neural_fights/data/database.py:863-913` (`_copia_antes_de_perder`): só compara personagens (`:889-893`) e usa `carimbo = %Y%m%d-%H%M%S` + `os.makedirs(destino, exist_ok=True)` + `copy2` por cima (`:896-903`). Chamada por `salvar_database:948`.
- **Defeito:**
  - `remover_arma` (launcher "Deletar" na aba Armas, `ui/view_armas.py:1283`) apaga sem cópia. Prova: "arma sumiu? True, copias novas: []".
  - Duas perdas no mesmo segundo usam a mesma pasta, e a 2ª apaga o estado de antes da 1ª. Prova: uma pasta só, com 143 personagens; os 144 originais sumiram.
- **Conserto:**
  - assinatura `_copia_antes_de_perder(armas_path, chars_path, armas_novas, chars_novos) -> str | None`;
  - `perdidos` = personagens do disco ausentes em `chars_novos` **mais** armas do disco ausentes em `armas_novas`. Uma arma renomeada também sai por nome e por isso gera cópia: aceitável;
  - carimbo `datetime.now().strftime("%Y%m%d-%H%M%S-%f")` e `os.makedirs(destino)` **sem** `exist_ok`. Em `FileExistsError`, sufixo `-2`, `-3`…;
  - `_podar_copias` continua por ordem de nome (o `%f` mantém a ordem) e passa a ignorar pastas `_backup-manual-*` na contagem. Hoje o `_backup-manual-20260916-190311` do runtime real ocupa uma das 5 vagas;
  - `salvar_database:948` passa `armas_json`.
- **Teste que prova:** `tests/test_banco_backup_regressions.py` (acrescentar):
  1. `remover_arma("Arma Sem Dono")` cria exatamente 1 `_backup-*` cujo `armas.json` contém a arma;
  2. dois `salvar_database` seguidos, cada um tirando um personagem, deixam 2 pastas: a 1ª com N personagens, a 2ª com N-1;
  3. com `_backup-manual-x` presente e 6 perdas, sobram 5 automáticas mais a manual.

  Hoje (1) acha 0 pastas e (2) acha 1.
- **Origem:** `nf-data.md` #4 e #5

### BLD-4 — Hífen, apóstrofo e espaço furam a moderação do nome pedido  (alto)
- **Onde:** `random_builds/builds/character/moderacao.py:59` (`normalizar` troca `-`/`'` por espaço) e `:89-110` (`ofensivo` compara palavra por palavra e cola só letras soltas); `character/nomes.py:147` (`_PERMITIDOS = " -'"`).
- **Defeito:** "Pu-ta", "Pu'ta", "Me-rda", "Cor-no", "Fu-ck" e "Pu ta" (vira "Pu Ta") passam com `motivo=None` e vão para a placa, o gancho e o banco. "Puta" e "P u t a" são barrados.
- **Conserto:** em `ofensivo`, depois das passadas atuais, mais uma: `tokens = plano.split()`. Para todo `i` e `k` em `(2, 3)`, se `"".join(tokens[i:i+k]) in inteiras`, devolver esse termo. Isso cobre "pu ta" e "me rda", e "pu ta mae" pelo par inicial. Manter `-` e `'` em `_PERMITIDOS`, porque "Jean-Luc" e "D'Artagnan" são nomes legítimos. Não usar substring no `grudado` para palavras inteiras: "Escurinho" contém "cu".
- **Teste que prova:** `random_builds/tests/test_moderacao_regressions.py` (acrescentar): `sanitizar_nome_pedido(x)[0] is None` para `["Pu-ta", "Pu'ta", "Me-rda", "Cor-no", "Vi-ado", "Ba-ba-ca", "Fu-ck", "Bi-tch", "Pu ta", "Pu-ta Mae"]`, e aceitos para `["Jean-Luc", "D'Artagnan", "Ana B Silva", "Escurinho", "Anna"]`. Hoje os 10 primeiros passam.
- **Origem:** `builds-conteudo.md` #2

### BLD-5 — O classificador lê `rarity` ao contrário: o valor mais comum vira "RARO · 0% de chance"  (alto)
- **Onde:** `random_builds/builds/evaluation/reaction_classifier.py:91-101` (`_e_raro`: `rarity <= rare_probability`) e `:139-143` (motivo `probabilidade {rarity}`). O motor (`generation/probability_engine.py:72-88`) documenta 0 = centro/comum e 1 = raro.
- **Defeito:** altura 1,80 m (rarity 0,0) sai RARE "probabilidade 0.0", com pílula "RARO · 0% de chance", voz "Raro!" e reação com 60% de chance. Os extremos (rarity 1,0) saem NORMAL. Prova: `classify(... rarity 0.0) -> RARE`, `rarity 1.0 -> NORMAL`.
- **Conserto:**
  - em `_e_raro`, `chance = 1.0 - rarity` e RARE quando `chance <= cfg["rare_probability"]`;
  - em `classify`, o motivo vira `f"probabilidade {round(1.0 - rarity, 3)}"`, para que o `_badge_da_reacao` (`editing/timeline_builder.py:~493`) mostre a chance real;
  - corrigir a docstring;
  - em `tests/test_edicao_tiktok_regressions.py:96` (`test_improvavel_e_raro_mesmo_sem_ser_extremo`), trocar `rarity=0.01` por `rarity=0.99`.
- **Teste que prova:** `random_builds/tests/test_raridade_editorial_regressions.py`. Com `RollEvaluator`/`ProbabilityEngine.numeric_rarity(180, 140, 220, ...)`, o valor no centro nunca é RARE. Com `numeric_rarity(219, 140, 220, ...)` (≈0,975) é RARE, e o motivo dá "probabilidade 0.025", que o badge transforma em "2% de chance". Hoje o centro é RARE.
- **Origem:** `builds-conteudo.md` #1

### BLD-6 — Três empates seguidos viram vitória inventada do primeiro lutador  (alto)
- **Onde:** `random_builds/builds/tournament/runner.py:462` (`_evento_base`: `vencedor = bruto["vencedor"] or p1`); `:257-266` (`simular_luta`); a mesma saída em `gravar_confronto` (`:270`). Usado por `_rodar_luta` (`:590`) e `FightSession.gerar` (`:695`).
- **Defeito:** se o motor empata nas seeds base, +1 e +2, o evento registra vitória do p1. Isso vai para a legenda, o placar da série, o torneio e o ledger da arena. Prova (só o motor dublado): "seeds [700, 701, 702], bruto.vencedor None, evento A B". É latente: 0 de 217 `fight.json` em `outputs/` têm empate.
- **Conserto:** classe `EmpatePersistente(RuntimeError)` em `runner.py`.
  - Em `_evento_base`, `if not bruto.get("vencedor"): raise EmpatePersistente(f"{p1} x {p2}: 3 empates (seeds {bruto['seed']})")`, sem o `or p1`.
  - Em `FightSession.gerar` e `_rodar_luta`, capturar e repetir o confronto com `semente + 1000` até 2 vezes. Persistindo, propagar: a geração falha com motivo claro e nada vai ao ar.
  - A regra de desempate é decisão do Adrian (abaixo). O padrão técnico é falhar, não inventar.
- **Teste que prova:** `random_builds/tests/test_empate_persistente_regressions.py`. Dublar `neural_fights.simulation.headless.run_headless_match` para devolver `winner=None` sempre. Afirmar que `runner._evento_base("A","B", runner.simular_luta("A","B","Torre",700), {}, set(), "Torre")` levanta `EmpatePersistente`. Com o dublê vencendo só na seed 1700, `FightSession(...).gerar(p1="A", p2="B", seed=700)` devolve vencedor "B" e não "A". Hoje dá "A".
- **Origem:** `builds-palco-video.md` #1 (o `builds-conteudo.md` #5 é o outro lado da mesma linha, ver "Alarmes falsos")

### BLD-7 — A trava do banco mora no TEMP de cada processo, e até a leitura depende do C:  (médio)
- **Onde:** `neural_fights/data/database.py:94-95` (`_bloqueio_persistencia_interprocesso`). Todas as funções públicas passam por ela, inclusive `resolver_database_paths:173` e `resolver_match_config_path:1110`.
- **Defeito:** processos com `TEMP` diferente (o CLAUDE.md manda `TEMP=E:\tmp_pytest`) não se excluem. Prova: o lock deste teste foi `E:\tmp_pytest\neural-fights.persistence.lock`, e o da produção fica em `C:\Users\adrian\AppData\Local\Temp`. Com o C: cheio, `open(..., "a+b")` falha e até `carregar_personagens()` morre.
- **Conserto:**
  - `def _caminho_da_trava() -> str`: `pasta = resolver_runtime_data_dir()`, `os.makedirs(pasta, exist_ok=True)` e `return os.path.join(pasta, ".persistence.lock")`. Se `OSError`, cair para o TEMP, como hoje;
  - `_bloqueio_persistencia_interprocesso` usa `_caminho_da_trava()`;
  - tirar `@_serializar_persistencia` de `resolver_database_paths` e de `resolver_match_config_path`, que só calculam caminho e conferem existência. As funções que os chamam já estão travadas.
- **Teste que prova:** `tests/test_persistence_regressions.py` (acrescentar). O pai segura `_bloqueio_persistencia_interprocesso()`. Um filho com o **mesmo** `NEURAL_FIGHTS_RUNTIME_DIR` e `TEMP` **diferente** chama `salvar_match_config({...})` e só termina depois que o pai solta (tempo ≥ o que o pai segurou). Hoje passa direto (0,13 s no relatório).
- **Origem:** `nf-data.md` #6

### BLD-8 — Arma com espaço nas pontas passa na validação e derruba `carregar_personagens`  (médio)
- **Onde:** `neural_fights/data/database.py:401-406` (`_nome_obrigatorio` devolve o nome com strip), `:835` (`validar_database` usa `.strip()`) e `:1177-1192` (`carregar_personagens` indexa sem strip).
- **Defeito:** uma arma `"Com Espaco "` com personagem `nome_arma="Com Espaco"` é aceita no salvar. Depois `carregar_personagens()` dá `KeyError: 'Com Espaco'` (provado), e caem o launcher, `live/roster.py`, o Ateliê e a simulação.
- **Conserto:** em `_nome_obrigatorio`, `if nome != nome.strip(): erros.append(f"{caminho}.nome tem espaco nas pontas: {nome!r}")`. Em `validar_database:835`, usar `{arma["nome"] for arma in lista_armas}` sem strip. Em `validar_personagens`, a mesma regra para `nome_arma`. Conferido: nenhum nome no runtime real nem no empacotado tem espaço nas pontas, então nada existente é recusado.
- **Teste que prova:** `tests/test_data_contracts.py` (acrescentar): `salvar_database` com a arma `"Com Espaco "` levanta `DataValidationError` e o banco não muda. Hoje grava, e o `carregar_personagens` seguinte levanta `KeyError`.
- **Origem:** `nf-data.md` #7

### BLD-9 — `catalog.json` das reações corrompido derruba toda montagem de vídeo  (médio)
- **Onde:** `random_builds/builds/assets/catalog.py:65-85` (`_load_reaction_catalog`: `json.load` e `entry["file"]`/`entry["id"]` sem proteção); `builds/assets/importer.py:56-58` (`_save_catalog`: `open(..., "w")` direto no arquivo final).
- **Defeito:** JSON truncado dá `JSONDecodeError`, e uma entrada sem `file` dá `KeyError` (provados). Os dois acontecem dentro de `AssetCatalog(...)`, construído em 7 pontos de `pipeline/controller.py`. Build, duelo, torneio e re-render morrem até alguém consertar o JSON.
- **Conserto:**
  - em `_load_reaction_catalog`, `try: data = json.load(...) except (OSError, ValueError) as exc:` registrar `atividade.registrar("estudio", "erro", f"catalogo de reacoes ilegivel: {exc}", "builds")` e `return` (biblioteca vazia, render segue com cartão sintético);
  - no laço, pular entrada sem `file` ou `id` (`if not entry.get("file") or not entry.get("id"): continue`);
  - `_save_catalog`: gravar em `catalog.json.<pid>.tmp`, `flush` + `fsync`, depois `os.replace`.
- **Teste que prova:** `random_builds/tests/test_catalogo_reacoes_ilegivel_regressions.py`. Com `{ corrompido` e com `{"reactions":[{"id":"1"}]}`, `AssetCatalog(d).entries == []` sem exceção. Com um `_save_catalog` cujo `json.dump` levanta no meio, o `catalog.json` anterior continua legível. Hoje: `JSONDecodeError`, `KeyError` e arquivo truncado.
- **Origem:** `builds-conteudo.md` #3

### BLD-10 — `geracao.json` com bloco de tipo errado derruba a rodada antes do tratamento de erro  (médio)
- **Onde:** `random_builds/builds/pipeline/noite.py:100-111` (`carregar` aceita qualquer tipo), `:115-118` (`na_janela` faz `janela["inicio"]`) e `:932` (`_rodada` chama `modo_da_hora` fora do `try` de `planejar`).
- **Defeito:** com `"janela_pesada": "corrompida"`, a rodada dá `TypeError` e morre sem a política de config ilegível.
- **Conserto:** em `carregar`, depois do `update`, validar o tipo de cada chave contra o tipo em `PADRAO`. Se `PADRAO[k]` é dict e o valor não é dict (nem `None`, quando o padrão aceita `None`), ou se é número/lista com o tipo errado, voltar ao `PADRAO[k]` e imprimir `[noite] geracao.json: '<k>' com tipo errado; uso o padrao`. Fazer o mesmo para `madrugada_na_transicao` e `rodada_de_dia`.
- **Teste que prova:** `random_builds/tests/test_noite_config_tipos_regressions.py`. `geracao.json` em `tmp_path` com `{"dias_de_lote": [], "janela_pesada": "corrompida"}`. `noite.carregar(p)["janela_pesada"] == noite.PADRAO["janela_pesada"]` e `noite.modo_da_hora(cfg, datetime(2026,10,14,10))` não levanta. Hoje dá `TypeError`.
- **Origem:** `pipeline-builds.md` #3

### BLD-11 — Duas sonorizações do mesmo alvo disputam o mesmo `.tmp`  (médio)
- **Onde:** `random_builds/builds/pipeline/sonorizar.py:90-96` (`_gravar`: `caminho.name + ".tmp"` fixo). Não há trava em `sonorizar.py`, nem em `main.py:712` (`som-da-luta`).
- **Defeito:** dois `som-da-luta <alvo>` ao mesmo tempo: um dá `FileNotFoundError` no `replace` depois de já ter re-simulado. O alvo pode ficar com o JSON de um e o vídeo do outro.
- **Conserto:**
  - `_gravar` usa `tempfile.mkstemp(dir=caminho.parent, prefix=caminho.name + ".", suffix=".tmp")`, com `os.fdopen` → `write` → `os.replace` e `unlink` do tmp no `except`;
  - `sonorizar.rodar` envolve cada alvo em `travas.trava(f"sonorizar__{alvo}", esperar=0.0)`. Sem a trava, imprime "[som] <alvo> já está sendo sonorizado; pulo" e segue.
- **Teste que prova:** `random_builds/tests/test_sonorizar_concorrente_regressions.py`. Duas threads chamam `sonorizar._gravar(p, {"x": "a"*2_000_000})` e `{"x": "b"*...}` ao mesmo tempo, 20 vezes. Nenhuma exceção, e o arquivo final é JSON válido igual a um dos dois. Hoje sai `FileNotFoundError`.
- **Origem:** `pipeline-builds.md` #1

### BLD-12 — Ledger da arena: a 2ª corrupção apaga a prova da 1ª, e `registrar` regrava sem cópia  (médio)
- **Onde:** `random_builds/builds/arena/ledger.py:41-47` (`__init__`: `replace` para `ledger.corrompido.json` fixo) e `:80-87` (`registrar`: `except (OSError, ValueError): pass` e recomeça de `{"lutas": []}`). Estado de depois do `873f2e6`.
- **Defeito:**
  - uma segunda corrupção sobrescreve o `.corrompido.json` anterior;
  - se o arquivo corromper entre a abertura e o `registrar`, este grava só a luta nova por cima do histórico inteiro, sem cópia.
- **Conserto:**
  - função `_por_de_lado(caminho)`: destino `caminho.with_name(f"{caminho.stem}.corrompido-{datetime.now():%Y%m%d-%H%M%S-%f}.json")` e `replace`;
  - usar essa função no `__init__` e também no `except` do `registrar`, antes de recomeçar a lista.
- **Teste que prova:** `random_builds/tests/test_auditoria_1110_builds_regressions.py` (acrescentar):
  1. corromper o ledger, abrir `Ledger(p)`, corromper de novo e abrir de novo: existem 2 arquivos `*.corrompido-*.json`;
  2. com `Ledger(p)` aberto, corromper o arquivo e chamar `registrar(...)`: existe 1 `*.corrompido-*.json` com o conteúdo corrompido.

  Hoje: 1 arquivo e 0.
- **Origem:** `builds-conteudo.md` #8 (4º item)

### BLD-13 — `NEURAL_FIGHTS_RUNTIME_DIR` só vale no import  (médio)
- **Onde:** `neural_fights/data/database.py:57-65` (constantes) e `:196-197` (`resolver_database_paths` usa `ARQUIVO_*_RUNTIME`).
- **Defeito:** quem define a variável depois de importar continua no banco antigo (provado: `resolver_runtime_data_dir()` = `X:\nao-existe`, escrita no runtime velho). Um script "isolado" grava no banco real.
- **Conserto:** em `resolver_database_paths`, `base = resolver_runtime_data_dir()` e `runtime_armas/chars = os.path.join(base, "armas.json"/"personagens.json")`. Fazer o mesmo em `resolver_match_config_path` para `match_config.json`. As constantes ficam como alias documentado ("valor no import; não use para gravar").
- **Teste que prova:** `tests/test_persistence_regressions.py` (acrescentar). Depois do import, `monkeypatch.setenv("NEURAL_FIGHTS_RUNTIME_DIR", str(tmp_path))` faz `resolver_database_paths(para_escrita=True)[1] == str(tmp_path / "personagens.json")`. Hoje devolve o runtime do import.
- **Origem:** `nf-data.md` #10

### BLD-14 — Caminhos explícitos para arquivo inexistente viram banco vazio válido  (médio)
- **Onde:** `neural_fights/data/database.py:241-242` (`carregar_json` devolve `[]`) e `:841-855` (`carregar_database`).
- **Defeito:** `carregar_database(arquivo_armas=<não existe>, arquivo_personagens=<não existe>)` dá `([], [])` (provado). `catalogo_animacoes` e `qualidade_luta` seguem sobre um "banco vazio".
- **Conserto:** em `carregar_database`, quando os dois caminhos são explícitos, ou quando o resolvido é o empacotado (`ARQUIVO_ARMAS`/`ARQUIVO_CHARS`), e algum não existe: `raise DataValidationError(f"banco ausente: {caminho}")`. O caso "runtime ainda não criado" já cai no empacotado em `resolver_database_paths:208-210` e não muda.
- **Teste que prova:** `tests/test_data_contracts.py` (acrescentar): `carregar_database(arquivo_armas=tmp/"a.json", arquivo_personagens=tmp/"c.json")` sem os arquivos levanta `DataValidationError`. Com runtime vazio, sem par, `carregar_database()` continua devolvendo o empacotado. Hoje: `([], [])`.
- **Origem:** `nf-data.md` #9

### BLD-15 — A validação do banco não tem teto  (médio)
- **Onde:** `neural_fights/data/database.py:755-780` (`validar_personagens`: só `minimo`) e `:645-675` (`validar_armas`: `dano`, `peso` e `velocidade_ataque` sem `maximo`).
- **Defeito:** `tamanho/forca/mana = 1e6` e `dano/peso/velocidade_ataque = 1e9` são aceitos (provado). Pelo launcher, um personagem de 1e6 m gera luta absurda.
- **Conserto:** tetos de **sanidade**, não de contrato, em `models/constants.py`, como `LIMITES_BANCO = {"tamanho": (1.0, 3.0), "forca": (0.5, 15.0), "mana": (0.0, 15.0), "dano": (0.0, 100.0), "peso": (0.0, 30.0), "velocidade_ataque": (0.05, 3.0)}`, passados como `maximo=` aos `_validar_numero`. Medido no banco real: `tamanho` 1,4–2,2; `forca` 3,0–10,5; `mana` 2,3–9,6; `dano` 7–34; `peso` 0,8–8,9; `velocidade_ataque` 0,81–1,2. Nada existente é recusado. A faixa do relatório (forca 4,5–8, mana 3–6) recusaria o banco atual.
- **Teste que prova:** `tests/test_data_contracts.py` (acrescentar): `validar_database` com `tamanho=1e6` e com `dano=1e9` levanta `DataValidationError`. `validar_database(*carregar_database())` sobre o catálogo empacotado continua passando. Hoje os valores enormes são aceitos.
- **Origem:** `nf-data.md` #8

### BLD-16 — `funny.tamanho` nunca dispara  (baixo)
- **Onde:** `random_builds/builds/evaluation/reaction_classifier.py:104-120` (`_e_engracado` compara `score`), `builds/evaluation/roll_evaluator.py:40` (`neutral` dá 50) e `builds/nf_bridge/roulette_factory.py:49` (tamanho `neutral`).
- **Defeito:** 1,40 m e 2,20 m saem NORMAL "score 50" (provado). "tamanho de bolso" e "nao cabe na arena" nunca aparecem.
- **Conserto:** em `_e_engracado`, se `roll.get("evaluation_method", _metodo(roll)) == "neutral"` e o roll tem `value`, `min` e `max`, comparar `pos = (value - min) / (max - min) * 100` com `below`/`above` em vez do `score`. Se o evento não tiver `min`/`max`, buscar na roleta pelo `roulette_id`.
- **Teste que prova:** `random_builds/tests/test_edicao_tiktok_regressions.py` (acrescentar): roll de tamanho com `value=140, min=140, max=220, score=50` dá FUNNY "tamanho de bolso"; `value=220` dá "nao cabe na arena"; `value=180` dá NORMAL. Hoje os três dão NORMAL.
- **Origem:** `builds-conteudo.md` #4

### BLD-17 — `escolhas.por_entidade` estoura `KeyError` cru  (baixo)
- **Onde:** `random_builds/builds/generation/escolhas.py:155-161`.
- **Defeito:** uma chave fora do catálogo (escolhas montadas fora de `interpretar`) dá `KeyError: 'altura'` (provado).
- **Conserto:** antes do filtro, `desconhecidas = set(roletas) - set(disponivel)` e, se houver alguma, `raise ValueError(f"atributo desconhecido: {sorted(desconhecidas)}. Conhecidos: {sorted(disponivel)}")`. É a mesma mensagem de `interpretar`.
- **Teste que prova:** `random_builds/tests/test_escolhas_regressions.py` (ou o arquivo de escolhas existente): `por_entidade({"roletas": {"altura": 180}}, "character")` levanta `ValueError` com "altura". Hoje dá `KeyError`.
- **Origem:** `builds-conteudo.md` #7

### BLD-18 — Reação que não entra deixa o giro cheio gasto e `reaction: null` numa decisão "sim"  (baixo)
- **Onde:** `random_builds/builds/editing/timeline_builder.py:420-462` (`_push_reaction`, os dois `return`) e `:333` (`_marcar_cheias`, que roda antes).
- **Defeito:** clipe curto demais ou fora do orçamento sai sem empurrar a reação, mas a decisão continua `reaction=True`.
- **Conserto:** nos dois `return` de `_push_reaction`, `decision["reaction"] = False` e `decision["reaction_motivo"] = "clipe curto"/"sem orcamento"`. Como `_marcar_cheias` já rodou, mover a chamada de `_marcar_cheias` para depois do laço que empurra as reações, ou recalcular o giro cheio dessa roleta.
- **Teste que prova:** `random_builds/tests/test_edicao_tiktok_regressions.py` (acrescentar). Com o seletor dublado devolvendo um clipe de 0,5 s (abaixo de `min_util_segundos`), a decisão sai com `reaction is False` e o evento da roleta não está marcado como giro cheio. Hoje: `True` e cheio.
- **Origem:** `builds-conteudo.md` #8 (1º item)

### BLD-19 — `voz.hash` ignora volume, `max_atempo`, folga e atraso  (baixo)
- **Onde:** `random_builds/builds/content/voz.py:865-868`.
- **Defeito:** mudar esses valores no `render.json` não regera o `voz.wav` de uma build já narrada, porque `montar` usa os quatro (`:454-455`, `:520`).
- **Conserto:** incluir `"volume", "max_atempo", "folga", "atraso"` na tupla da assinatura. Todo `voz.wav` existente vai ser refeito uma vez no próximo re-render, o que é esperado.
- **Teste que prova:** `random_builds/tests/test_voz_regressions.py` (acrescentar): com `montar` dublado contando as chamadas, a 2ª chamada com o mesmo cfg não monta e a 3ª com `volume=0.5` monta. Hoje não monta.
- **Origem:** `builds-conteudo.md` #8 (2º item)

### BLD-20 — O diário dá a fábrica viva como ociosa depois de 600 eventos  (baixo)
- **Onde:** `random_builds/builds/atividade.py:266` (`estado_das_fabricas`) e `:323` (`estado_por_canal`).
- **Defeito:** um `inicio` mais antigo que os últimos 600 eventos não é examinado, e a fábrica sai "ocioso" com o PID vivo.
- **Conserto:** trocar `recentes(600)` por uma varredura do fim para o começo, em blocos, até ter o último evento não-`log` de cada fábrica de `FABRICAS` (e de cada canal), ou até acabar o arquivo. Teto de segurança: 20.000 linhas.
- **Teste que prova:** `random_builds/tests/test_atividade_regressions.py` (acrescentar): num diário temporário, `registrar("arena","inicio",...)` com o PID atual seguido de 600 `log` do estúdio deixa `estado_das_fabricas()["arena"]["status"] == "trabalhando"`. Hoje dá "ocioso".
- **Origem:** `pipeline-builds.md` #2

### BLD-21 — O correio pode começar um pedido até 60 s depois do prazo da rodada  (baixo)
- **Onde:** `random_builds/builds/identity/worker.py:719-731` (`processar_correio`).
- **Defeito:** o prazo é conferido antes da passada (`:1034`) e entre jobs (`:1255`), mas não depois da espera pela conta. O piso `max(60.0, prazo - now)` deixa `pedir_imagem` começar depois do prazo.
- **Conserto:** logo depois de entrar no `with _conta_do_rodizio(...)` e antes de `pedir_imagem`, `if pedido is None and _prazo_vencido(prazo): raise CorreioOcupado("prazo da rodada venceu esperando a conta")`. O chamador já reagenda sem gastar tentativa. Tirar o piso de 60 s: `max(1.0, prazo - now)`.
- **Teste que prova:** `random_builds/tests/test_identity_correio_prazo_regressions.py`: `processar_correio(job, ajustes, prazo=time.time()-1)`, com correio e carteiro dublados em memória, levanta `CorreioOcupado` e o dublê de `pedir_imagem` tem 0 chamadas. Hoje: 1 chamada.
- **Origem:** `identity.md` #1

### BLD-22 — `termina_bem` não vale para o nome pedido  (baixo, depende de decisão)
- **Onde:** `random_builds/builds/character/nomes.py:135-144` (`termina_bem`: 0 chamadores fora de testes) e `:165-205` (`sanitizar_nome_pedido`).
- **Defeito:** "Kael o Sombrio" entra como "Kael O Sombrio" (provado), embora a regra do pedido 4 diga que o nome não termina em qualidade.
- **Conserto (se o Adrian decidir que vale):** no fim de `sanitizar_nome_pedido`, `if not termina_bem(nome): return None, "termina em qualidade"`.
- **Teste que prova:** `random_builds/tests/test_nomes_regressions.py`: `sanitizar_nome_pedido("Kael o Sombrio") == (None, "termina em qualidade")` e "Kaelen" continua aceito.
- **Origem:** `builds-conteudo.md` #6

### BLD-23 — Código sem chamador  (baixo)
- **Onde:**
  - `neural_fights/data/database.py:1221` (`carregar_arma_por_nome`), `:1018` (`renomear_arma`) e `:311` (`salvar_jsons_coerentes`, público mas só interno);
  - `neural_fights/data/__init__.py` (exporta `ARQUIVO_*_RUNTIME`);
  - `random_builds/builds/assets/triagem.py` (`SessaoTriagem`);
  - `content/caption_generator.py` (`for_reveal`, `for_identity` e as chaves `reveal_*`/`identity*` de `captions.json`);
  - `character/lexico.py::significado`;
  - `character/nomes.py:44,128` (`_fundir`, `_pluralizar`).
- **Defeito:** funções públicas que ninguém chama. Cada uma é mais uma porta que o BLD-1 precisaria cobrir.
- **Conserto:** apagar com os testes que só existem para elas. Fazer depois do BLD-1, para não conflitar no `database.py`. `salvar_jsons_coerentes` vira `_salvar_jsons_coerentes`, e o `__init__` deixa de exportar as constantes.
- **Teste que prova:** a suíte inteira verde, e `grep` sem ocorrência fora de `tests/`.
- **Origem:** `nf-data.md` #11, `builds-conteudo.md` #8 (3º item)

---

## Já consertados
- (nenhum dos 27; o `873f2e6` consertou a trava do ledger da arena antes destes relatórios e já estava descontado)

## Alarmes falsos
- `builds-conteudo.md` #5 (empate vira `None` na legenda e derruba `torneio_resultado`): a função quebra com `None` se receber, mas nenhum caminho entrega `None`. Toda luta passa por `runner._evento_base:462` (`vencedor = bruto["vencedor"] or p1`, usado em `:590` e `:695`). O defeito real é o contrário, a vitória inventada do BLD-6. Depois do BLD-6 a legenda continua sem receber `None`, porque o empate vira exceção.

## Decisões que são do Adrian
- **Empate persistente** (três seeds empatadas, BLD-6): desempatar por HP restante, mostrar "empate" no vídeo e no ledger, ou descartar a luta e sortear outra? O conserto técnico padrão é falhar sem publicar.
- **Nome de comentário e `termina_bem`** (BLD-22): o nome pedido obedece à regra "não termina em qualidade" ("Kael o Sombrio" é recusado) ou o comentarista escreve o que quiser?
- **Botão "🎲 Gerar Roster" do torneio no launcher** (BLD-1, item 4): manter com duas confirmações ou tirar, já que o painel tem a mesma ação ("Regenerar database")?
