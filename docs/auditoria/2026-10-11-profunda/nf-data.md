# Auditoria profunda — Motor: dados e banco de personagens (`neural_fights/data/**`)

Data: 2026-10-13. Só relatório; nenhum código do projeto foi alterado. Provas rodadas em pasta temporária (`NEURAL_FIGHTS_RUNTIME_DIR` apontado para `%TEMP%\nf-audit-rt-*` antes do import), sem gravar no banco real nem em `%LOCALAPPDATA%\neural-fights` (de lá só se leu `personagens.json`/`armas.json`).

## Examinado

| Arquivo | Linhas | O que é | Como foi lido |
|---|---|---|---|
| `neural_fights/data/database.py` | 1.224 | banco de armas/personagens em JSON, trava própria, validação, transação de dois arquivos, cópia antes de perder, match_config | inteiro, as 40 funções uma a uma |
| `neural_fights/data/__init__.py` | 63 | re-exporta a API | inteiro |
| `neural_fights/data/fixtures/default_match_config.json` | 7 | config de luta padrão | inteiro |
| `neural_fights/data/alvos_qualidade.json` | 697 | 88 alvos do harness de qualidade + 7 notas (`_doc`, `_nota_*`) | varrido por script: todo alvo tem `metrica`, nenhum `min > max`, nenhuma chave fora do contrato; o consumidor (`tools/qualidade_luta.py:733`) pula as chaves `_*` |
| `neural_fights/data/triagem_skills_onda11.json` | 37 | ata da triagem 11B | inteiro; nenhum código lê este arquivo (é documento) |
| `neural_fights/data/personagens.json` / `armas.json` | 770 / 2.604 | catálogo empacotado (64 personagens, 54 armas) | passado pelo `validar_database` real: válido; o runtime real (142 personagens, 155 armas) também valida |

Chamadores lidos para entender quem grava: `tools/gerador_database.py:662-726` (`salvar_database`, `substituir=True/False`), `random_builds/builds/nf_bridge/exporter.py:139-158` (`insert_into_database`, a roleta), `ui/view_chars.py:1286,1310`, `ui/view_armas.py:1129-1135,1283`, `ui/view_torneio.py:176,356-368`, `painel/paginas/jogo.py:147-160`, `remoto/comandos_app.py:443-445`, `ferramentas/painel.py:291-294`, `cli/roster.py:16`, `tools/migrar_database.py:138-156`, `models/characters.py:34-116`, `models/weapons.py:42-262`, e os testes `tests/test_data_contracts.py`, `test_persistence_regressions.py`, `test_banco_backup_regressions.py`, `conftest.py`.

O que está BEM (e foi conferido, não presumido): leitura corrompida levanta `DataValidationError` em vez de virar `[]` (`carregar_json:244-260`, chaves duplicadas e NaN rejeitados); toda gravação é temporário + `fsync` + `os.replace` (`_escrever_temporario:263`, `salvar_json:297`); o par armas/personagens é gravado com rollback se um `os.replace` falhar (`salvar_jsons_coerentes:311`); a trava é reentrante dentro do processo (RLock + profundidade por thread, `:140-159`) e segura entre processos que compartilham o mesmo `TEMP` (prova P7, "mesmo TEMP"); nome duplicado de arma/personagem é rejeitado (`:632,751`); campos opcionais `None` (`habilidades`, `encantamentos`, `passiva`, `afinidade_elemento`, `kit_skills`) são tratados; par runtime parcial (só um dos dois arquivos) é recusado (`:203-207`).

## Confirmados (do mais grave ao menos)

### 1. O launcher grava a lista que carregou na abertura e apaga, em silêncio, o que a roleta inseriu depois

- **Onde:** `database.py:1207-1217` (`salvar_lista_armas`, `salvar_lista_chars`) chamados por `ui/view_chars.py:1286,1310` e `ui/view_armas.py:1135` com `self.controller.lista_personagens` / `lista_armas`, listas carregadas uma vez em `ui/main.py:85-86`. Agravante: `ui/view_torneio.py:176` ("🎲 Gerar Roster") chama `gerador_database.salvar_database(armas, personagens)` com `substituir=True` por padrão (`:365`) e **sem nenhuma confirmação** — troca o banco inteiro num clique (o painel e o app pedem duas confirmações para a mesma ação, `painel/paginas/jogo.py:150-158`, mas essa porta não).
- **O defeito:** a API só conhece "substitua a lista inteira". O launcher fica aberto horas; nesse tempo a roleta (`exporter.insert_into_database`) insere personagens no mesmo `personagens.json`. Quando o Adrian salva ou apaga UM campeão no launcher, a lista da memória (sem os novos) vai para o disco por cima. A cópia de segurança (`_copia_antes_de_perder:863`) é criada, mas só avisa por `logger.warning` — nenhum lugar lê as pastas `_backup-*` nem avisa o bot/app (grep: só `database.py` e testes citam `_backup-`). O personagem some; a build que depende dele (estreia, ficha, catálogo) vira "pendência que parece tarefa", exatamente o cenário de 02/09.
- **Quando acontece:** launcher aberto + roleta rodando de dia (decisão 30/09: pesado de dia) + qualquer salvar/deletar nas abas Campeões/Armas; ou um clique em "Gerar Roster" no torneio.
- **Prova (P3):** runtime temporário com os 64 do catálogo → `lista = carregar_personagens()` (o que o launcher faz) → `gerador_database.salvar_database([arma],[Lutador A], substituir=False)` (a roleta) → banco com 65 → `salvar_lista_chars(lista)` → banco volta a 64, "Lutador A sobreviveu? False". Pasta `_backup-*` criada, nenhum erro, nenhum aviso ao chamador.
- **Conserto sugerido:** (a) `salvar_lista_chars`/`salvar_lista_armas` passam a fazer merge por nome: recarregam o banco dentro da mesma trava, aplicam só o que mudou (inserido/editado/apagado pelo launcher, por nome) e mantêm o resto; ou, mais simples, recusam gravar quando o banco no disco tem nomes que a lista não tem e o chamador não pediu `apagar=`; (b) `_copia_antes_de_perder` devolve a lista de perdidos e `salvar_database` registra no `atividade.jsonl` (o bot já apura isso), não só no logger; (c) "Gerar Roster" pede as duas confirmações como o painel, ou usa `substituir=False`.

### 2. A inserção da roleta não é atômica entre processos: duas builds em paralelo perdem uma

- **Onde:** `tools/gerador_database.py:662-726` (`salvar_database(..., substituir=False)`): chama `database.carregar_database()` (`:686`, trava 1) e depois `database.salvar_database(...)` (`:708`, trava 2). A trava de `database.py:140` cobre cada chamada, não o par. Chamado por `random_builds/builds/nf_bridge/exporter.py:152`.
- **O defeito:** leitura-modificação-escrita em duas travas. Processo A lê N, processo B lê N, B grava N+1, A grava N+1 (com o dele) — o de B some. O comentário em `database.py:75-78` diz que o RLock existe para "operações de leitura-modificação-escrita", mas só as funções que ficam dentro de `database.py` (`atualizar_arma`, `renomear_arma`, `remover_arma`) ganham isso; a inserção da roleta ficou fora.
- **Quando acontece:** com "2 em paralelo" de dia (decisão 30/09) toda vez que duas builds chegam à inserção com menos de ~1 s de diferença. Não há `_backup-*` automático no runtime real hoje, ou seja, ainda não aconteceu — mas a janela existe em toda rodada paralela.
- **Prova (P2):** duas threads chamando `gerador_database.salvar_database(..., substituir=False)` com um atraso de 1 s depois do `carregar_database` real (a função real roda; só o retorno demora, para fixar a ordem): "Lutador A no banco? False | Lutador B no banco? True", uma pasta `_backup-*` criada.
- **Conserto sugerido:** mover a inserção para `database.py` como `inserir_no_banco(armas, personagens)` decorada com `_serializar_persistencia` (carrega + checa nomes + grava sob a mesma trava), e o `gerador_database.salvar_database(substituir=False)` passa a chamá-la; o exporter também (o `_nome_unico` dele tem a mesma corrida).

### 3. A ida-e-volta pelo launcher apaga campos que o modelo não conhece (`genero` da roleta, geometria de projétil/orbital, `tamanho`)

- **Onde:** `database.py:1207-1217` gravam `Arma.to_dict()` / `Personagem.to_dict()` (`models/weapons.py:224-262`, `models/characters.py:99-116`); `Arma.__init__` recebe `**kwargs` e descarta (`weapons.py:76,204`); `Personagem.to_dict` só devolve 10 chaves + `kit_skills`. A roleta grava `personagem["genero"]` (`exporter.py:106`) e as armas geradas levam `tipo_projetil`, `velocidade_projetil`, `tipo_orbital` (`gerador_database.py`); o runtime real tem `genero` em personagens e esses campos em 12 armas.
- **O defeito:** qualquer salvar no launcher reescreve TODOS os registros pelo modelo, não só o editado. `genero` some de todos os personagens (é lido pelo prompt de identidade, `random_builds/builds/identity/prompt.py:209`); `tipo_projetil`/`tipo_orbital` somem das armas; `tamanho` 0 vira `largura` em 36 das 54 armas (`weapons.py:100`: `float(tamanho) if tamanho else float(largura)`); `critico` e `velocidade_ataque` ganham ruído de ponto flutuante (3.8 → 3.8000000000000007). A segunda volta é estável (0 mudanças), então o estrago é de uma vez só, mas definitivo.
- **Quando acontece:** todo salvar/deletar nas abas Campeões ou Armas do launcher.
- **Prova (P1, P4):** catálogo empacotado → `Arma(**a).to_dict()`: `tamanho` muda em 36 armas, `critico` em 13, `tipo_projetil`/`velocidade_projetil`/`tipo_orbital` somem de 6 armas cada. Runtime temporário: personagem inserido com `genero="feminino"` → `salvar_lista_chars(carregar_personagens())` → `genero: <sumiu>`; armas com `tipo_projetil/tipo_orbital`: 12 antes, 0 depois.
- **Conserto sugerido:** junto com o item 1, gravar por diferença (só o registro tocado) e, para o registro tocado, partir do dict original do disco e sobrepor os campos do formulário — nunca regenerar a lista inteira a partir dos objetos. Se `to_dict` tiver de continuar sendo a fonte, `Arma` guarda os `kwargs` desconhecidos e os devolve, e `Personagem.to_dict` preserva `genero`.

### 4. `remover_arma` apaga do banco sem deixar cópia

- **Onde:** `database.py:1063-1107` (`remover_arma`), chamado por `ui/view_armas.py:1283`. A rede de segurança `_copia_antes_de_perder:863-913` só compara **personagens** (`:889-893`); a remoção de arma não entra.
- **O defeito:** a regra "apagar do banco deixa cópia" (commit `b1e6418`) ficou só para personagem. Uma arma apagada no launcher (com os personagens migrados para a substituta) não tem volta — e a arma da roleta é feita sob medida para o personagem da build (nome, raridade, encantamento combinam com o vídeo).
- **Quando acontece:** "Deletar" na aba Armas.
- **Prova (P5):** arma sem dono inserida → `remover_arma("Arma Nova A")` → "arma sumiu do banco? True | copias: []".
- **Conserto sugerido:** `_copia_antes_de_perder` compara também os nomes de armas (e renomeações: nome que sai sem entrar).

### 5. Duas perdas no mesmo segundo: a segunda cópia sobrescreve a primeira

- **Onde:** `database.py:896-903`: `carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")`, `os.makedirs(destino, exist_ok=True)`, `shutil.copy2` por cima.
- **O defeito:** a pasta é por segundo; a segunda gravação no mesmo segundo reutiliza a pasta e substitui `personagens.json`/`armas.json` — o estado anterior à primeira perda (o mais valioso) some. `remover_arma` + edição em sequência, ou o item 2 com duas builds, cabem num segundo.
- **Prova (P6):** `salvar_database(armas, chars[1:])` e `salvar_database(armas, chars[2:])` em seguida → uma única pasta `_backup-20261013-140118` guardando 63 personagens; os 64 da primeira perda não existem mais.
- **Conserto sugerido:** carimbo com microssegundos ou sufixo `-2`, `-3` quando a pasta existe; nunca `exist_ok=True` + copy por cima.

### 6. A trava entre processos mora no `TEMP` de cada processo e qualquer operação (até ler) depende de abrir arquivo no C:

- **Onde:** `database.py:94` (`tempfile.gettempdir()/neural-fights.persistence.lock`), `:110` (`msvcrt.locking`). Todas as 15 funções públicas, inclusive as puras (`resolver_database_paths:174`, `resolver_match_config_path:1111`) e as de leitura, passam por ela.
- **O defeito:** dois processos com `TEMP` diferente não se excluem: um usa `C:\Users\adrian\AppData\Local\Temp\...lock`, o outro `E:\tmp_pytest\...lock`. Hoje os processos de produção (tarefas agendadas, launcher, app, coordenador) compartilham o `TEMP` do usuário, e o executor/Codex roda com `TEMP=E:\tmp_pytest` **mas** com `NEURAL_FIGHTS_RUNTIME_DIR=.rt` (banco próprio), então o furo é latente — basta alguém rodar um `python -m random_builds...` com o `TEMP` do CLAUDE.md apontado para o banco real. A trava também ignora `NEURAL_FIGHTS_RUNTIME_DIR` (uma trava global para todos os bancos: não corrompe, só serializa demais). E o C: "vive cheio": se `open(...,"a+b")` falhar, `carregar_personagens()` falha — até a leitura do banco morre por falta de espaço num disco que o banco nem usa.
- **Prova (P7):** pai segura `_bloqueio_persistencia_interprocesso()`; filho com o mesmo `TEMP` espera ("filho gravou em 2.33s"); filho com `TEMP` diferente passa direto ("terminou enquanto o pai segurava o lock? True", 0.13 s).
- **Conserto sugerido:** lock ao lado do banco (`RUNTIME_DIR/.persistence.lock`), um por runtime; leitura pura (`resolver_*`) sem trava.

### 7. Arma com espaço no fim do nome passa na validação e derruba `carregar_personagens` com `KeyError`

- **Onde:** `validar_database:835` passa `{arma["nome"].strip()}` para a checagem de `nome_arma`, mas `carregar_personagens:1177-1192` indexa `pesos_por_nome` pelo nome **sem** strip.
- **O defeito:** arma `"Com Espaco "` + personagem com `nome_arma="Com Espaco"` é um banco válido que não carrega: o launcher, o `live/roster.py:47`, o `api_http.py:361` (Ateliê) e a simulação (`simulacao.py:112`) caem no `KeyError` até alguém editar o JSON na mão. `validar_armas` também só usa o nome com strip para detectar duplicata (`:631-634`) e grava o original.
- **Prova (P9):** `salvar_database` aceitou o par; `carregar_personagens` → `KeyError: 'Com Espaco'`.
- **Conserto sugerido:** rejeitar nome com espaço nas pontas na validação (`_nome_obrigatorio` já calcula o strip; basta comparar `nome != nome.strip()`), e indexar `pesos_por_nome` pelo mesmo nome que a validação usou.

### 8. A validação não tem teto: `tamanho`/`forca`/`mana` e `dano`/`peso`/`velocidade_ataque` aceitam qualquer tamanho

- **Onde:** `validar_personagens:755-780` (só `minimo`), `validar_armas:645-675` (`critico` tem `maximo=15`; `dano`, `peso`, `velocidade_ataque` não).
- **O defeito:** o contrato do motor é tamanho 1,5-2,0 m, força 4,5-8, mana 3-6 (`effects/attack.py:42`, `tests/test_impacto_regressions.py:4`); o launcher deixa digitar o que for, e um personagem com `tamanho=1e6` gera vida/resistência absurdas e uma luta que não cabe na tela. O gerador respeita faixas; a validação, que é a porta do banco, não.
- **Prova (P9):** `tamanho/forca/mana = 1e6: aceito`; `dano/peso/velocidade_ataque = 1e9: aceito`.
- **Conserto sugerido:** faixas canônicas em `models/constants.py` (as que o gerador já usa) e `maximo=` nos `_validar_numero` correspondentes.

### 9. Caminhos explícitos para arquivos inexistentes viram banco vazio, válido e gravável

- **Onde:** `carregar_json:241-242` devolve `[]` para arquivo ausente; `carregar_database:841-855` aceita o par vazio; `salvar_database` grava por cima.
- **O defeito:** `carregar_database(arquivo_armas=..., arquivo_personagens=...)` com nomes errados (erro de digitação, pasta movida) devolve `([], [])` sem erro — e `catalogo_animacoes.py:244`, `qualidade_luta.py:72` operam sobre "banco vazio" como se fosse real. Vale também para o catálogo empacotado: wheel sem `data/*.json` abre o launcher com zero personagens, sem mensagem. É o padrão "leitura que falha vira `[]`" que a auditoria achou em 9 arquivos, aqui na variante "ausente", não "corrompido".
- **Prova (P10):** `carregar_database(arquivo_armas=<não existe>, arquivo_personagens=<não existe>)` → `([], [])`.
- **Conserto sugerido:** quando os dois caminhos são explícitos (ou são o empacotado), arquivo ausente é erro; `[]` por ausência só faz sentido para o runtime ainda não criado, e esse caso já é tratado em `resolver_database_paths:208-210`.

### 10. `NEURAL_FIGHTS_RUNTIME_DIR` é lido no import; mudar a variável depois não muda o banco

- **Onde:** `database.py:57-65` (`RUNTIME_DIR = resolver_runtime_data_dir()` e os `ARQUIVO_*_RUNTIME` congelados no import).
- **O defeito:** `resolver_runtime_data_dir()` respeita a variável a cada chamada, mas `resolver_database_paths` usa as constantes — um teste ou script que define a variável depois de importar grava no banco real achando que está isolado (o `conftest.py` existe justamente porque isso já custou duas sessões em 16/09; `random_builds/tests/test_tempo_por_etapa_regressions.py:50` anota o mesmo).
- **Prova (P8):** depois do import, `os.environ[...]="X:\nao-existe"` → `resolver_runtime_data_dir()` devolve `X:\nao-existe`, `resolver_database_paths(para_escrita=True)` devolve o runtime antigo.
- **Conserto sugerido:** `resolver_database_paths` calcula os caminhos a partir de `resolver_runtime_data_dir()` na hora; as constantes ficam como alias documentado.

### 11. Funções públicas sem chamador e exportações mortas

- **Onde:** `carregar_arma_por_nome:1221` (0 chamadores fora de testes), `renomear_arma:1018` (0; o launcher usa `atualizar_arma`), `salvar_jsons_coerentes:311` (só interno, mas público). `__init__.py` exporta `ARQUIVO_CHARS_RUNTIME`/`ARQUIVO_ARMAS_RUNTIME`, que ninguém importa além dos testes.
- **Prova:** grep no repositório (`neural_fights`, `random_builds`, `remoto`, `painel`, `coordenador`), excluindo testes e worktrees.
- **Conserto sugerido:** remover ou marcar como ferramenta; cada função pública a mais é mais uma que o item 1 pode repetir.

## Não confirmados

- **Leitura corrompida virando `[]` e a próxima gravação apagando o banco:** não acontece aqui. `carregar_json` levanta `DataValidationError` para JSON inválido, chave duplicada, NaN/Infinity; `_copia_antes_de_perder` engole a exceção (`:883-886`) mas aí a gravação que segue é a de um chamador que já leu com sucesso. O caso 02/09 foi `substituir=True`, não leitura falha — e esse hoje deixa cópia.
- **Gravação sem temporário + `os.replace`:** não há. Todas passam por `_escrever_temporario` com `fsync`.
- **Trava reentrante:** confirmada reentrante (RLock + `depth` por thread). `atualizar_arma` → `carregar_database` → `resolver_database_paths` → `carregar_json` aninham sem travar (os testes `test_data_contracts.py:273-358` exercem isso).
- **Transação de dois arquivos sob queda do processo (não sob exceção):** por leitura, se o processo morrer entre o primeiro e o segundo `os.replace` (`:348-351`), fica um par misto (armas novas + personagens velhos) que `resolver_database_paths` não detecta (os dois arquivos existem) e sobram `.tmp`/`.bak` na pasta. Não há `.tmp`/`.bak` no runtime real hoje, e não dá para provar sem matar o processo no instante certo; fica como risco anotado. Mitigação barata: gravar os dois documentos num único JSON ou escrever um marcador antes/depois.
- **Migração de versão do esquema:** não existe campo de versão nos JSON; a única migração é por apelidos (`tools/migrar_database.py`). Não é defeito hoje, mas qualquer mudança de campo vai repetir o `kit_skills` ("opcional porque registro antigo não tem") em vez de migrar.
- **`match_config`:** sem esquema (`carregar_match_config` aceita qualquer dict), mas `salvar_match_config` preserva campos desconhecidos e o round trip está coberto por teste; sem defeito encontrado.
- **`alvos_qualidade.json` e `triagem_skills_onda11.json`:** estrutura íntegra; o primeiro é lido por `qualidade_luta.py` ignorando as chaves `_*`; o segundo não é lido por código.
- **Lock herdado por processo filho:** `open()` em Python 3 cria handle não herdável; o coordenador pode lançar workers enquanto um processo segura a trava sem que o filho a herde.
