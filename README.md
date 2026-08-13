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

Depois de instalar o projeto pelo `pyproject.toml`, o mesmo comando fica disponivel como `neural-fights-audit-skills`.

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
