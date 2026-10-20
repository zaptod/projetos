# ORIGEM: python-testing-patterns

- **Fonte:** https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-testing-patterns (Seth Hobson; repositório comunitário grande, 41,2 mil estrelas pela API em 20/10/2026, ~28 mil instalações desta skill segundo skillselion/skills.sh)
- **Commit:** `0874a27b17a22e2b7c2e2bcd725768e0803cad06` (17/10/2026)
- **Licença:** MIT (`LICENSE` da raiz do repositório, copiado junto)
- **Baixado e lido em:** 20/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\wshobson_agents\`
- **Copiado:** `SKILL.md`, `references/details.md`, `references/advanced-patterns.md`, sem alteração.

## O que li (tudo)
Só texto, sem script. pytest: estrutura Arrange/Act/Assert, fixtures com escopo e teardown, `parametrize` com `pytest.param(id=...)`, `unittest.mock` (`patch`, `side_effect` para testar nova tentativa), exceções com `pytest.raises(match=)`, `monkeypatch` de variável de ambiente, `tmp_path`, `conftest.py`, marcadores (`slow`, `integration`), hypothesis (teste por propriedade), freezegun (tempo congelado), cobertura.

## Cuidados neste repositório (as leis do CLAUDE.md vencem a skill)
- Rode com `TEMP=E:\tmp_pytest` e `PYTEST_ADDOPTS=-p no:cacheprovider` (o C: vive cheio).
- Os exemplos de `pip install` (pytest-cov, freezegun, hypothesis) são informativos: não instale pacote novo sem pedido.
- O `pytest.ini`/`pyproject` de exemplo traz `--cov` no `addopts`; **não** copie para o nosso `pyproject.toml`.
- "Relatório verde que mente" (memória): sempre teste o caso ZERO (lista vazia, nada publicado, contador parado).
- Testes que varrem o código-fonte (ex.: contra barra invertida comida por heredoc) são de propósito aqui; a skill não os proíbe.

## Para que serve, e a quem
- **integrador**: separar falha da entrega de teste instável; escrever o teste que faltou.
- **builds, publicacao, metricas** ao escrever teste (ex.: mock da API do YouTube, caso zero de
  "nada publicado", nova tentativa no upload).
