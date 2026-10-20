# ORIGEM: webapp-testing

- **Fonte:** https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/webapp-testing (repositório oficial da Anthropic)
- **Commit:** `dbd4588f9e1033efb41dad4bef2f7947c8993d44` (09/10/2026)
- **Licença:** Apache-2.0 (`LICENSE.txt`, copiada junto)
- **Baixado e lido em:** 20/10/2026, quarentena `E:\tmp_pytest\skills_quarentena\anthropics_skills\`
- **Copiado:** a pasta inteira, sem alteração (`SKILL.md`, `scripts/with_server.py`, `examples/*.py`, `LICENSE.txt`).

## O que li (tudo)
- `SKILL.md`: escrever scripts Python do Playwright (`sync_playwright`), esperar `networkidle` antes de olhar o DOM, reconhecer a tela antes de agir (captura, `page.content()`, localizar botões), capturar o console.
- `scripts/with_server.py`: sobe um ou mais servidores locais (`subprocess.Popen(shell=True)`), espera a porta em `localhost` abrir, roda o comando e derruba os servidores. Só fala com `localhost`. Nenhum envio para fora, nenhum download.
- `examples/`: três exemplos (achar elementos, HTML estático por `file://`, capturar console). Só `localhost`/arquivo local.

## Cuidados neste repositório
- Os exemplos gravam em `/tmp` e `/mnt/user-data/outputs` (caminhos do claude.ai). Aqui, use `E:\tmp_pytest\...` (o C: vive cheio).
- O app do celular já roda pelo coordenador; **não** use `with_server.py` para subir o app de verdade (a lei "o app nunca cai" e a janela das postagens valem). Use-o só para servidores de teste descartáveis.
- O conferente abre o app no Chrome em **390x844**: `browser.new_page(viewport={"width": 390, "height": 844})`.
- Os `.py` desta pasta ficam fora do `ruff` (exclusão em `pyproject.toml`), porque são de fora e vieram como estão.

## Para que serve, e a quem
- **conferente**: abrir a tela de verdade, clicar no caminho real, tirar captura e ler o console
  (QA de tela antes de qualquer coisa chegar ao Adrian).
- **publicacao**: o padrão "reconhecer a tela antes de agir" (captura antes de clicar) serve ao
  TikTok por navegador. Sem evasão nem disfarce (memória "Contas de IA sem disfarce").
