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
python -m scripts.gerar_roster --modo completo --seed 42
python -m tools.analise_armas
python -m tools.diagnostico_hitbox
python -m tools.migrar_database          # dry-run
python -m tools.migrar_database --apply  # grava somente apos validar
```

## Arquitetura

- `core/`: entidades, resolucao de combate, status, hitboxes e regras de dominio.
- `simulation/`: loop visual que consome o motor de combate.
- `ai/`: decisao, estrategia e coreografia dos lutadores.
- `models/` e `data/`: modelos, validacao, persistencia e fixtures.
- `ui/`: launcher e telas Tk/CustomTkinter.
- `tournament/`: estado e orquestracao do torneio.
- `effects/`: apresentacao visual e audio, sem regras de dominio.
- `tools/` e `scripts/`: validadores, migracoes e CLIs operacionais.
- `tests/`: regressao automatizada e contratos; diagnosticos interativos ficam na raiz.

## Verificacao local

Execute a suite automatizada pela pasta dedicada, sem coletar os diagnosticos visuais e de audio:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m ruff check .
python -m pip check
```

Audite o contrato estrutural das skills com:

```powershell
python -m tools.auditoria_skills --strict
python -m tools.analise_armas --strict
python -m tools.diagnostico_hitbox --strict
```

A auditoria normal retorna `1` para erros estruturais. Em `--strict`, warnings tambem bloqueiam o comando com codigo `2`. Todos os campos avancados atualmente catalogados possuem evidencia comportamental referenciada no manifesto; uma capacidade nova sem teste volta a bloquear o gate estrito.

Depois de instalar o projeto pelo `pyproject.toml`, o mesmo comando fica disponivel como `neural-fights-audit-skills`.

O estado gerado em execução fica no diretório local de dados do usuário (`%LOCALAPPDATA%\neural-fights` no Windows ou `$XDG_STATE_HOME/neural-fights` no Linux). Ele pode ser isolado com `NEURAL_FIGHTS_RUNTIME_DIR`. Dados canônicos e fixtures permanecem imutáveis em `data/` e `data/fixtures/`.

Os arquivos `test_sound.py`, `test_jump_sound.py` e demais demonstracoes na raiz sao diagnosticos manuais. Eles sao seguros para importacao, mas recursos de audio ou janela so devem ser iniciados executando esses arquivos diretamente.

## Geracao de roster

O gerador usa os catalogos canonicos de skills e personalidades, valida todas
as referencias e grava armas/personagens na mesma transacao. Informe uma seed
para obter o mesmo roster em qualquer execucao:

```powershell
python -m scripts.gerar_roster --modo completo --seed 42
```
