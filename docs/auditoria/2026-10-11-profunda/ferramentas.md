# Auditoria profunda — Ferramentas e manutenção — 11/10/2026

## Examinado

- `ferramentas/abrir.py` — 6 funções lidas; confere dependências e abre os alvos do projeto.
- `ferramentas/auditoria_arquitetura.py` — 13 funções lidas; mede regressões de imports, pacotes e âncoras.
- `ferramentas/auditoria_contas.py` — 5 funções lidas; mostra destinos de publicação e, opcionalmente, credenciais OAuth.
- `ferramentas/capas_atrasadas.py` — 4 funções lidas; encontra e envia capas pendentes de histórias.
- `ferramentas/conciliar_tiktok.py` — 10 funções lidas; propõe e grava no ledger posts já existentes no TikTok.
- `ferramentas/curar_ledger.py` — 32 funções lidas; analisa e cura inconsistências dos ledgers.
- `ferramentas/handoff.py` — 8 funções lidas; gera a passagem de estado entre sessões.
- `ferramentas/monitor_agentes.py` — 6 funções lidas; lê transcritos e mostra a atividade dos agentes.
- `ferramentas/obsidian.py` — 31 funções lidas; sincroniza as notas geradas do projeto para o cofre Obsidian.
- `ferramentas/ocultar_consoles.py` — 1 função lida; verifica se as tarefas agendadas ocultam o console.
- `ferramentas/painel.py` — 11 funções lidas; implementa o menu de desenvolvimento para builds, simulação, live e banco.
- `ferramentas/run.py` — 0 funções/classes próprias; encaminha para a CLI principal.
- `ferramentas/run_tournament.py` — 0 funções/classes próprias; encaminha para a CLI de torneio.
- `ferramentas/manutencao/README.md` — documentação dos scripts de manutenção, lida integralmente.
- `ferramentas/manutencao/copiar.py` — 4 funções lidas; copia arquivos de uma worktree com guarda da base Git.
- `ferramentas/manutencao/parecer_gemini_video.py` — 2 funções lidas; pede parecer de vídeo pelo navegador configurado.
- `ferramentas/manutencao/vigia_som.py` — 8 funções lidas; re-renderiza duelos noturnos e vigia o processo filho.
- `ferramentas/manutencao/vigia_som_dia.py` — 7 funções lidas; re-renderiza cópias durante o dia e as troca fora da grade.
- `ferramentas/manutencao/inventario/montar.py` — 3 funções lidas; gera as duas páginas do inventário de sprites.
- `ferramentas/manutencao/inventario/molde.html` — JavaScript do inventário lido integralmente; renderiza itens e salva o estado pelo app.
- `ferramentas/manutencao/test_manutencao.py` — 8 funções de teste/apoio lidas; cobre os scripts de manutenção.
- `ferramentas/diagnostico/debug_simulation.py` — 2 funções lidas; instala overlay de depuração da simulação.
- `ferramentas/diagnostico/test_arena.py` — 1 função lida; abre diagnóstico visual da arena.
- `ferramentas/diagnostico/test_headless_battle.py` — 0 funções/classes próprias; reexporta o runner headless.
- `ferramentas/diagnostico/test_jump_sound.py` — 1 função lida; reproduz sons de salto e aterrissagem para diagnóstico.
- `ferramentas/diagnostico/test_manual.py` — 0 funções/classes próprias; reexporta o simulador manual.
- `ferramentas/diagnostico/test_sound.py` — 1 função lida; reproduz um som de impacto para diagnóstico.
- `ferramentas/diagnostico/test_vfx.py` — 4 funções e 1 classe lidas; demonstra visualmente os efeitos mágicos.
- `ferramentas/diagnostico/test_visual_debug.py` — 18 funções e 2 classes lidas; exercita skills e produz capturas/relatório visual.
- `testar.py` — 6 funções lidas; agrega suites, smoke, integridade e arquitetura em runtime isolado.
- `conftest.py` — configuração de isolamento do runtime do pytest, lida integralmente.

## Confirmados (do mais grave ao menos)

### 1. Duas conciliações gravam o mesmo post do TikTok — gravidade: média

- Onde: `ferramentas/conciliar_tiktok.py:252-255,275-285` (`main`)

- O defeito: o comando decide as linhas a importar antes de pegar a trava do ledger. A trava serializa somente o append; quem a obtém depois não relê o ledger nem recalcula sua proposta.

- Quando acontece: duas execuções com `--gravar` leem a mesma captura quando o post ainda não tem dono. Ambas propõem a mesma linha; a primeira grava e a segunda acrescenta sua proposta já vencida. O ledger fica com duas linhas para o mesmo `video_id` e `tiktok_id`.

- Prova: em diretório temporário fora do repositório, rodei `PowerShell: $codigo | python -X utf8 -`, com duas threads chamando o `main` real, catálogo/ledger temporários e uma trava que serializa os dois appends. Saída: `RETORNOS=[0, 0]` e `LINHAS_NO_LEDGER=2`; cada execução informou `1 proposta(s)` e `1 gravadas.`

- Conserto sugerido: adquirir a trava antes de ler o ledger e recalcular `vistos`, donos e `novas` dentro dela, inclusive depois do filtro `--so`.

### 2. O copiador aceita caminho que escapa do destino — gravidade: média

- Onde: `ferramentas/manutencao/copiar.py:40-49` (`copiar`)

- O defeito: `rel` é usado diretamente em `origem / rel` e `destino / rel`, sem exigir que permaneça relativo às duas raízes. Um argumento com `..` permite sobrescrever arquivo irmão da árvore de destino, apesar de a ferramenta se declarar copiadora “para uma árvore principal”.

- Quando acontece: ao rodar com `arquivos` contendo `../fora.txt`, o conteúdo de `origem/../fora.txt` substitui `destino/../fora.txt`, que não pertence ao destino informado.

- Prova: em diretório temporário fora do repositório, rodei `python -X utf8 -c "... copiar(origem, destino, ['../fora.txt']) ..."`. Saída: `copiado ../fora.txt LF` e `CONTEUDO_FORA=fonte`, embora o arquivo externo ao destino tivesse começado como `original`.

- Conserto sugerido: resolver cada caminho e recusar qualquer origem ou alvo que não seja descendente, respectivamente, de `origem` e `destino`.

### 3. O CLI do Obsidian declara sucesso após não atualizar nada — gravidade: baixa

- Onde: `ferramentas/obsidian.py:511-514` (`main`)

- O defeito: o retorno é `0 if funcoes[args.acao]() else 0`; portanto, o código de saída é zero tanto para sucesso quanto para falha.

- Quando acontece: um cofre inexistente faz `diario()` retornar `False`, sem criar nota, mas o processo ainda informa êxito ao agendador ou chamador.

- Prova: rodei `python -X utf8 ferramentas/obsidian.py --cofre E:\tmp_pytest\ausente_auditoria_4f4c2c0f diario` sem criar esse diretório. Saída: `CODIGO_OBSIDIAN=0`.

- Conserto sugerido: retornar `0 if funcoes[args.acao]() else 1`.

## Não confirmados

- `ferramentas/capas_atrasadas.py:61-71` (`_ler_feitas`/`_gravar_feitas`) não serializa leitura e substituição de `_capas_atrasadas.json`; duas execuções podem perder uma marcação de progresso. Não confirmei porque não há chamador automático duplicado nesta fatia e não executei envios reais ao YouTube.
