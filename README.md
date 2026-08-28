# Neural Fights

Simulador de combate 2D com lutadores controlados por IA. Requer Python 3.10 ou superior.

```powershell
python -m pip install .
neural-fights
```

Para desenvolvimento (testes, cobertura e lint):

```powershell
python -m pip install -e ".[dev]"
```

## Entrypoints

```powershell
python run.py                         # launcher grafico
python run.py --sim                   # IA contra IA no simulador visual
python run.py --test                  # diagnostico manual controlavel
python run_tournament.py              # interface de torneio
python test_headless_battle.py --mode rapido --seed 42
python test_headless_battle.py --mode stress --stress-count 20 --seed 42
```

Os mesmos fluxos ficam disponíveis após a instalação:

```powershell
neural-fights
neural-fights --sim
neural-fights-tournament
neural-fights-headless --mode rapido --seed 42
neural-fights-roster --modo completo --seed 42
neural-fights-migrate-database
neural-fights-audit-skills --strict
neural-fights-live --source replay --events tests/fixtures/eventos_exemplo.jsonl
```

Modulos executaveis dentro de pacotes devem ser chamados com `python -m`, evitando alteracoes manuais em `sys.path`:

```powershell
python -m neural_fights.cli.roster --modo completo --seed 42
python -m neural_fights.tools.analise_armas
python -m neural_fights.tools.diagnostico_hitbox
python -m neural_fights.tools.migrar_database          # dry-run
python -m neural_fights.tools.migrar_database --apply  # grava somente apos validar
```

## Arquitetura

- `neural_fights/core/`: entidades, combate, status, hitboxes e regras de dominio.
- `neural_fights/simulation/`: loop visual e runner headless sobre o mesmo motor.
- `neural_fights/ai/`: decisao, estrategia e coreografia dos lutadores.
- `neural_fights/models/` e `neural_fights/data/`: modelos, persistencia e fixtures.
- `neural_fights/ui/`: launcher e telas Tk/CustomTkinter.
- `neural_fights/tournament/`: estado e orquestracao do torneio.
- `neural_fights/effects/`: apresentacao visual e audio, sem regras de dominio.
- `neural_fights/live/`: sessao de transmissao interativa; ingestao de eventos de
  plataforma e orquestracao de partidas encadeadas.
- `neural_fights/tools/` e `neural_fights/cli/`: validadores, migracoes e CLIs.
- `tests/`: regressao automatizada e contratos; diagnosticos interativos ficam na raiz.

Todo codigo distribuido vive sob o namespace publico `neural_fights`. Os
scripts da raiz sao wrappers de desenvolvimento e nao entram na wheel.

## Verificacao local

Execute a suite automatizada pela pasta dedicada, sem coletar os diagnosticos visuais e de audio:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m ruff check .
python -m pip check
```

Audite o contrato estrutural das skills com:

```powershell
python -m neural_fights.tools.auditoria_skills --strict --verify-evidence-sources
python -m neural_fights.tools.analise_armas --strict
python -m neural_fights.tools.diagnostico_hitbox --strict
```

A auditoria normal valida somente os contratos estruturais e funciona na wheel,
que nao inclui `tests/`. No checkout, `--verify-evidence-sources` tambem confere
via AST se cada evidencia aponta para uma classe e um teste existentes. Erros
retornam `1`; em `--strict`, warnings tambem bloqueiam com codigo `2`.

Consulte os CONTRATOS derivados (o "MCP interno" da Onda 11) e rode a
checagem 1-a-1 no motor real com o inspetor:

```powershell
python -m neural_fights.tools.skill_inspector listar --tipo AREA
python -m neural_fights.tools.skill_inspector explicar "Julgamento Celestial"
python -m neural_fights.tools.skill_inspector exportar --saida skills.json
python -m neural_fights.tools.skill_inspector cobertura
python -m neural_fights.tools.skill_inspector checar --todas
```

E gere/atualize a biblioteca de demos por skill (mp4 limpo por cena
roteirizada; o manifest com hash regrava so o que mudou):

```powershell
python -m neural_fights.recording.skill_demo --todas
```

Depois de instalar o projeto pelo `pyproject.toml`, o mesmo comando fica disponivel como `neural-fights-audit-skills`.

## Sessao de live

`neural-fights-live` abre **uma** janela e roda partidas encadeadas nela ate ser
interrompido. A janela e criada uma unica vez e nunca recriada: e ela que o OBS
captura, e recriar a janela derrubaria a fonte de captura no meio da transmissao.
A troca de partida usa `recarregar_tudo()`, que nao toca no display.

```powershell
neural-fights-live --source replay --events tests/fixtures/eventos_exemplo.jsonl
neural-fights-live --max-partidas 10 --pausa 8 --sem-hud
neural-fights-live --sem-registry          # chat vira so ambientacao
neural-fights-live --source youtube --video-id ID_DA_LIVE
```

Eventos de espectador entram por `neural_fights/live/sources/`. A fonte `replay`
le um arquivo JSON Lines de `ViewerEvent`, o que permite ensaiar o show inteiro e
rodar regressao no CI sem rede nem credencial de plataforma. `RecordingSource`
envolve qualquer fonte e grava a sessao, transformando uma live real no arquivo
de replay da proxima sessao de desenvolvimento.

Os overlays sao decididos pelo bloco `overlays` do match config
(`hud`, `analise`, `hitbox_debug`), e nao apenas pelas teclas G/TAB/H. O overlay
de diagnostico de hitbox e desligado por padrao para nao ir ao ar por descuido.

### Registro de espectadores

Espectadores e os lutadores que eles possuem ficam em SQLite
(`live.sqlite3`, no diretorio de runtime), **nunca** em `personagens.json`. O
catalogo JSON continua sendo o conteudo curado e read-only: inserir nele custa
uma revalidacao completa e duas reescritas integrais sob lock entre processos,
o que congelaria a transmissao.

Cada lutador tem dois nomes, e a separacao e deliberada:

- `catalog_name` (`@<id>`) e a chave que o motor usa. E ASCII, imutavel, e usa um
  prefixo que o gerador de roster nunca produz, entao colisao com o catalogo
  curado e impossivel por construcao.
- `display_name` e o texto sanitizado que aparece na tela. Nome de espectador e
  conteudo de terceiro: a sanitizacao remove zero-width, sobrescrita
  bidirecional, marcas combinantes, controles, emoji e pontuacao, aplica um teto
  de tamanho e consulta uma blocklist editavel ao vivo. Se sobrar vazio, cai num
  handle deterministico.

Espectadores entram por comando explicito no chat:

```
!entrar
```

O comando e idempotente por duas vias: o `event_id` da plataforma e chave
primaria no journal (reconexao reentrega o que ja foi lido) e um espectador so
pode ter um lutador ativo, garantido por indice unico no banco. Todo evento
recebido fica journalizado com o seu desfecho -- nada e descartado em silencio.

### Chat do YouTube

```powershell
neural-fights-live --source youtube --video-id ID_DA_LIVE
neural-fights-live --source youtube --gravar-eventos sessao.jsonl
```

As credenciais ficam num JSON no diretorio de runtime (ou no caminho de
`--credenciais`, ou em `NEURAL_FIGHTS_YOUTUBE_CREDENTIALS`) -- nunca no pacote,
nunca no controle de versao:

```json
{
  "client_id": "...apps.googleusercontent.com",
  "client_secret": "...",
  "refresh_token": "...",
  "video_id": "opcional; sem ele a conta e consultada"
}
```

A integracao usa apenas `urllib` da biblioteca padrao: e um GET REST com bearer
token e um POST de refresh, e o CI trava o conteudo da wheel. Tres invariantes:

- **A luta nunca para.** Queda de rede vira backoff com jitter (2s a 60s) dentro
  da thread da fonte; a transmissao continua e o `nextPageToken` e preservado,
  entao a reconexao retoma de onde parou em vez de reprocessar tudo.
- **Nada e cobrado duas vezes.** O `id` da mensagem vira `event_id`, chave
  primaria no journal: a reentrega apos reconexao e idempotente por construcao.
- **A quota degrada, nao morre.** `pollingIntervalMillis` da resposta e
  respeitado, e perto do teto diario o intervalo cresce em vez de a live
  terminar com um 403.

Super Chat e Super Sticker viram creditos em centesimos da moeda (R$ 1,00 = 100
creditos); membros valem um valor fixo. A paridade entre moedas **nao** e
resolvida: calibre os custos do catalogo contra a moeda predominante da sua
audiencia.

`--gravar-eventos` envolve qualquer fonte e grava a sessao em JSON Lines, o que
transforma uma live real no arquivo de replay da proxima sessao de
desenvolvimento -- e num teste de regressao, se algo der errado ao vivo.

### Comandos de espectador

O vocabulario vive em `neural_fights/live/catalog.py`, e e auditado pelo mesmo
mecanismo das skills:

```powershell
python -m neural_fights.tools.auditoria_comandos --strict --verify-evidence-sources
```

Campo nao declarado no inventario e **erro**, nao aviso; toda `skill` referenciada
precisa existir em `SKILL_DB` e toda arena em `ARENAS`; e cada comando precisa
apontar para um teste real, conferido por AST.

Tres categorias:

| Categoria | Escopo | Efeito |
|---|---|---|
| `ASSIST` | `ALVO` | ajuda o lutador escolhido (`!curar p1`) |
| `CAOS` | `GLOBAL` | atinge os dois (`!meteoro`) |
| `PROXIMO_ROUND` | `ROUND` | vale para a proxima partida (`!arena Vulcao`) |

O caos instancia a area **uma vez por lutador**: como `AreaEffect` exclui o
proprio dono, cada um e atingido pela area do outro. O efeito e simetrico e
ninguem recebe credito de abate que nao merece -- e a auditoria proibe que um
comando global use skill com `lifesteal`, `cura_por_morte`, `rouba_buff` ou
`executa`.

A ordem de avaliacao da politica e deliberada: banimento, momento, cooldown do
comando, cooldown do espectador, teto por round, saturacao e **pagamento por
ultimo**. Recusa por regra nunca cobra. Intencao paga que nao coube vira credito
do proximo round, gravado em SQLite -- o espectador ja gastou, e uma queda de
processo nao pode engolir o que foi comprado.

### Progressao

Lutadores de espectador entram nas partidas de verdade. O `Simulador` aceita um
`roster_provider` opcional -- a unica costura que a camada de live pede no motor
-- e `LiveRoster` resolve os dois espacos de nome com cache: o catalogo curado
indexado uma vez, e os lutadores de espectador materializados do SQLite sob
demanda.

Resultados alimentam a classificacao (`fighter_stats`), e o `RankedMatchmaker`
coloca quem tem lutador na frente do catalogo curado -- a graca da feature e ver
o proprio nome na arena. O roster curado nao acumula ficha: ele e cenario, nao
competidor.

**Custo de uma troca de partida** (medido neste projeto, 64 personagens):

| | antes | depois |
|---|---|---|
| resolucao de roster | 27 ms | 1 ms |
| recarga de assets de audio | ~970 ms | 0 ms |
| **total** | **~1004 ms** | **~36 ms** |

O gargalo nao era o roster: `_configurar_partida_atual` reseta o `AudioManager` a
cada partida, e sem cache isso relia e redecodificava todos os assets do disco --
95% do custo, cerca de um segundo congelado entre lutas. O cache de assets vive
em `effects/audio.py`, e beneficia todos os caminhos (launcher, torneio, live).
Ele e descartado antes de `pygame.mixer.quit()`, porque um `Sound` nao sobrevive
ao encerramento do mixer.

## Dados empacotados e dados de execução

`neural_fights/data/armas.json`, `neural_fights/data/personagens.json` e `neural_fights/data/fixtures/` são o catálogo e as fixtures imutáveis distribuídos com a aplicação. Enquanto não existir uma cópia local completa, as leituras usam esse catálogo empacotado. A primeira gravação cria, em uma única transação, `armas.json` e `personagens.json` no diretório de dados do usuário; a partir daí, as leituras usam o par local. Se apenas um dos dois arquivos locais existir, a aplicação acusa o snapshot incompleto em vez de misturar versões.

As operações de persistência usam escrita temporária, substituição
atômica, rollback do par e lock entre threads e processos. JSON com números
não finitos ou chaves duplicadas é recusado na fronteira de leitura.

Por padrão, os dados de execução ficam em `%LOCALAPPDATA%\neural-fights` no Windows ou `$XDG_STATE_HOME/neural-fights` no Linux. Use `NEURAL_FIGHTS_RUNTIME_DIR` para isolar esse estado, por exemplo em testes ou automações. Configurações de luta e overrides de áudio também ficam nessa área gravável; nenhum fluxo normal modifica os assets em `neural_fights/data/` ou `neural_fights/sounds/`.

Os arquivos `test_sound.py`, `test_jump_sound.py` e demais demonstracoes na raiz sao diagnosticos manuais. Eles sao seguros para importacao, mas recursos de audio ou janela so devem ser iniciados executando esses arquivos diretamente.

## Geracao de roster

O gerador usa os catalogos canonicos de skills e personalidades, valida todas
as referencias e grava armas/personagens na mesma transacao. Informe uma seed
para obter o mesmo roster em qualquer execucao:

```powershell
python -m neural_fights.cli.roster --modo completo --seed 42
```
