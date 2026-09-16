"""O diario e o banco saem do caminho ANTES de qualquer teste importar algo.

16/09/2026, e custou tempo de duas sessoes. O `testar.py` ja isolava: ele
roda cada suite com `NEURAL_FIGHTS_RUNTIME_DIR` apontando para uma pasta
descartavel. Mas rodar `pytest tests/<arquivo>` na mao — que e o que se faz o
dia inteiro enquanto se escreve — NAO passa por ele, e ali o runtime volta a
ser o de producao.

Foi assim que "desisti do TikTok para trava:build:celular" (um id de duble)
entrou no `atividade.jsonl` de VERDADE. O apurador automatico leu aquilo como
falha de producao, disparou um diagnostico e editou o repositorio por causa
de um video que nunca existiu.

A licao: **isolamento que depende de como o teste foi lancado nao e
isolamento.** Aqui ele passa a valer sempre, porque o pytest carrega este
arquivo antes de colher os testes, venha de onde vier.

Nao sobrescreve o que ja estiver definido: o `testar.py` e o CI escolhem a
pasta deles, e este arquivo so cobre quem nao escolheu nenhuma.
"""
import os
import tempfile
from pathlib import Path

_PADRAO = Path(tempfile.gettempdir()) / "neural-fights-pytest"

if not os.environ.get("NEURAL_FIGHTS_RUNTIME_DIR"):
    _PADRAO.mkdir(parents=True, exist_ok=True)
    os.environ["NEURAL_FIGHTS_RUNTIME_DIR"] = str(_PADRAO)
