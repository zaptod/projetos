# Auditoria profunda — Sprites, esteira e Mimetizar — 11/10/2026

## Examinado

- `painel/sprites/__init__.py` — 0 funções/classes lidas; expõe o pacote.
- `painel/sprites/__main__.py` — 1 função lida; inicia a interface de linha de comando.
- `painel/sprites/alinhar.py` — 6 funções/classes lidas; alinha partes e monta a imagem de sprites.
- `painel/sprites/exportar.py` — 20 funções/classes lidas; exporta sprites, metadados e artefatos para a Vila.
- `painel/sprites/fatiar.py` — 10 funções/classes lidas; divide uma folha em células e remove células vazias.
- `painel/sprites/fundo_auto.py` — 9 funções lidas; detecta e remove fundo automaticamente.
- `painel/sprites/importar.py` — 8 funções/classes lidas; importa imagens, aplica receita e registra a folha.
- `painel/sprites/limpeza.py` — 16 funções lidas; faz limpeza de cor, transparência e ruído em imagens RGBA.
- `painel/sprites/lote.py` — 1 função lida; processa um lote de imagens.
- `painel/sprites/medidas.py` — 8 funções lidas; mede imagens, células e transparência.
- `painel/sprites/receita.py` — 6 funções/classes lidas; carrega, valida e aplica receitas de processamento.
- `painel/sprites/rotulos.py` — 5 funções/classes lidas; agrupa componentes e atribui rótulos às células.
- `painel/sprites/test_importar.py` — 5 funções lidas; cobre importação e aplicação de receita.
- `painel/sprites/fixtures/LEIAME.md` — 0 funções/classes lidas; documenta as imagens de fixture.
- `painel/sprites/fixtures/*.png` — 0 funções/classes lidas; assets binários de teste, inspecionados como fixtures sem código executável.
- `esteira_sprites/__init__.py` — 0 funções/classes lidas; expõe o pacote.
- `esteira_sprites/__main__.py` — 1 função lida; inicia a interface da esteira.
- `esteira_sprites/animacao.py` — 10 funções lidas; extrai quadros, mede movimento e valida animações.
- `esteira_sprites/aprovar.py` — 4 funções lidas; aprova, recusa ou libera fichas na esteira.
- `esteira_sprites/colher.py` — 3 funções lidas; coleta resultados concluídos da Vila.
- `esteira_sprites/config.py` — 7 funções/classes lidas; lê e valida a configuração da esteira.
- `esteira_sprites/ficha.py` — 6 funções lidas; lê, grava e altera fichas de sprites.
- `esteira_sprites/inventario_vila.py` — 17 funções lidas; lê inventário e decide se um sprite atende à Vila.
- `esteira_sprites/juiz.py` — 11 funções lidas; executa as regras de julgamento de uma ficha.
- `esteira_sprites/limpar.py` — 2 funções lidas; remove sobras da esteira.
- `esteira_sprites/pedir.py` — 3 funções lidas; cria pedidos de geração de sprites.
- `esteira_sprites/portao.py` — 7 funções lidas; aplica o portão de qualidade antes da entrega.
- `esteira_sprites/prompt.py` — 7 funções lidas; monta prompts e restrições de geração.
- `esteira_sprites/test_animacao.py` — 8 funções lidas; cobre medidas e validação de animação.
- `esteira_sprites/test_esteira.py` — 25 funções/classes lidas; cobre fluxo, configuração, portão e inventário da esteira.
- `mimetizar/main.py` — 3 funções lidas; fornece a CLI do Mimetizar.
- `mimetizar/espelho/__init__.py` — 0 funções/classes lidas; expõe o pacote.
- `mimetizar/espelho/absorver.py` — 12 funções lidas; prepara, executa e acompanha a absorção de canais.
- `mimetizar/espelho/analise.py` — 13 funções/classes lidas; calcula análises agregadas do canal.
- `mimetizar/espelho/baixar.py` — 12 funções lidas; baixa mídia e acompanha tentativas.
- `mimetizar/espelho/biblia.py` — 10 funções lidas; gera e valida a bíblia do canal.
- `mimetizar/espelho/canal.py` — 10 funções/classes lidas; cataloga abas e metadados do canal.
- `mimetizar/espelho/config.py` — 11 funções lidas; carrega configuração e cria diretórios de canais.
- `mimetizar/espelho/dossie.py` — 12 funções lidas; monta dossiês textuais de vídeos.
- `mimetizar/espelho/estado.py` — 8 funções lidas; persiste estado de etapas da absorção.
- `mimetizar/espelho/ffmpeg.py` — 7 funções lidas; invoca ffprobe e ffmpeg com timeout.
- `mimetizar/espelho/ficha.py` — 13 funções/classes lidas; gera fichas de vídeo e canal.
- `mimetizar/espelho/medidas.py` — 16 funções lidas; mede cortes, áudio e características de vídeos.
- `mimetizar/espelho/preset.py` — 11 funções lidas; produz presets a partir das análises.
- `mimetizar/espelho/status.py` — 8 funções lidas; resume o andamento de um canal.
- `mimetizar/espelho/transcrever.py` — 14 funções lidas; obtém legendas, transcreve e grava textos.
- `mimetizar/espelho/ytdlp.py` — 9 funções/classes lidas; localiza e executa o yt-dlp.
- `mimetizar/config/analise.json` — 0 funções/classes lidas; parâmetros da análise.
- `mimetizar/config/biblia.json` — 0 funções/classes lidas; estrutura da bíblia.
- `mimetizar/config/capacidades.json` — 0 funções/classes lidas; capacidades disponíveis.
- `mimetizar/config/coleta.json` — 0 funções/classes lidas; limites e parâmetros de coleta.
- `mimetizar/config/medidas.json` — 0 funções/classes lidas; parâmetros de medição.
- `mimetizar/README.md` — 0 funções/classes lidas; instruções de uso e fluxo.
- `mimetizar/pyproject.toml` — 0 funções/classes lidas; configuração de empacotamento e testes.
- `mimetizar/requirements.txt` — 0 funções/classes lidas; dependências declaradas.
- `mimetizar/tests/test_mimetizar_regressions.py` — 54 funções/classes lidas; regressões de coleta, análise, download, estado e CLI.
- `docs/sessoes/esteira-sprites.md` — 0 funções/classes lidas; histórico e contrato operacional da esteira.

Também reli a auditoria anterior de 11/10. As corridas já registradas em `esteira_sprites/ficha.py`, `esteira_sprites/pedir.py` e `mimetizar/espelho/estado.py` não são repetidas abaixo, conforme o pedido.

## Confirmados (do mais grave ao menos)

### 1. Falha temporária em Shorts ou lives vira catálogo aparentemente completo — gravidade: alta

- Onde: `mimetizar/espelho/canal.py:124` (`catalogar`)
- O defeito: qualquer `NaoColetou` nas abas secundárias é apenas registrada no log e ignorada. Como `coletar_aba` converte falhas de rede/yt-dlp em `NaoColetou`, o catálogo é salvo como sucesso, sem marca de incompletude.
- Quando acontece: a aba `videos` é coletada, mas a rede cai ao coletar `shorts` ou `streams` → o canal passa a ter somente os vídeos longos, e as etapas posteriores analisam esse conjunto incompleto como se fosse o canal todo.
- Prova: executei `PYTHONPATH=mimetizar` com `catalogar` real, em `TemporaryDirectory`, substituindo somente a fronteira de coleta: a aba `videos` retornou `longo` e as demais levantaram `NaoColetou('timeout temporario')`. A saída foi `catalogado= 1 ids= ['longo']`; não houve exceção nem indicação persistida de falha.
- Conserto sugerido: distinguir aba inexistente de falha transitória e propagar/reagendar a segunda, ou persistir explicitamente o catálogo como incompleto.

### 2. Timeout do yt-dlp não vale enquanto o processo está silencioso — gravidade: alta

- Onde: `mimetizar/espelho/ytdlp.py:79` (`rodar_streaming`)
- O defeito: o prazo só é passado a `proc.wait()` depois do laço `for linha in proc.stdout`. Se o processo fica vivo sem escrever nem fechar stdout, esse laço bloqueia e o timeout nunca é alcançado.
- Quando acontece: yt-dlp ou sua conexão trava silenciosamente → a coleta pode ficar presa indefinidamente, em vez de retornar o código `124` e permitir recuperação.
- Prova: executei `rodar_streaming` real com limite de `0.05` s, substituindo apenas o comando externo por `python -c "import time; time.sleep(0.4)"`. A saída foi `codigo= 0 decorrido>= 0.7`; era esperado retorno `124` próximo de `0.05` s.
- Conserto sugerido: controlar o prazo enquanto o stdout é consumido (por exemplo, leitor em thread/fila ou `communicate` com prazo) e encerrar o processo ao expirar.

### 3. Corte interrompido é contado como medição completa — gravidade: alta

- Onde: `mimetizar/espelho/medidas.py:53` (`cortes`) e `mimetizar/espelho/medidas.py:182` (`medir_video`)
- O defeito: `cortes` aceita o código `124` e informa que a saída é parcial, mas `medir_video` descarta essa informação. Sem amostra configurada, grava a duração inteira do vídeo como analisada e `amostra_parcial=False`, embora o ffmpeg tenha parado cedo.
- Quando acontece: um vídeo de 600 s atinge timeout depois de produzir somente um corte em 30 s → a ficha registra 600 s analisados e calcula cortes por minuto sobre a duração errada; a análise e o preset recebem medida enganosa.
- Prova: executei `medir_video` real com as fronteiras `ffmpeg`/`ffprobe` simulando vídeo de 600 s e retorno `124` com `pts_time:30.0`. A saída foi `analisado_s= 600 amostra_parcial= False cortes_por_min= 0.1 instantes= [30.0]`.
- Conserto sugerido: em timeout, falhar/reagendar a medição ou transportar a duração efetivamente processada e marcar a amostra como parcial.

### 4. Legenda vazia ou truncada bloqueia nova transcrição e é contada como sucesso — gravidade: média

- Onde: `mimetizar/espelho/transcrever.py:199` (`transcrever`)
- O defeito: a seleção de alvos pula qualquer vídeo que tenha um arquivo `.srt`, sem validar conteúdo nem os arquivos complementares. Uma interrupção entre criar a legenda e gravar o restante deixa esse vídeo permanentemente fora de novas tentativas; o resumo ainda diz que não houve texto pendente.
- Quando acontece: existe `transcricoes/v1.srt` vazio ou inválido, por exemplo após queda durante gravação → `transcrever` retorna zero pendências e não cria `v1.json`, embora não exista transcrição utilizável.
- Prova: executei `transcrever` real em `TemporaryDirectory` com `v1.srt` contendo apenas `WEBVTT`, substituindo somente configuração, catálogo, lista de baixados e persistência externa. A saída foi `resultado= {'transcritos': 0, 'por_legenda': 0, 'por_whisper': 0, 'sem_texto': 0} tem_json= False`.
- Conserto sugerido: considerar concluída apenas legenda não vazia e validada com seu metadado, e gravar os artefatos em arquivo temporário seguido de rename atômico.

### 5. Criação concorrente de canal perde uma absorção com `FileExistsError` — gravidade: média

- Onde: `mimetizar/espelho/config.py:66` (`criar_canal`)
- O defeito: o próximo identificador é calculado antes de `mkdir`, sem exclusão mútua nem nova tentativa. Dois processos podem escolher o mesmo diretório; um cria e o outro falha sem tratamento.
- Quando acontece: duas absorções começam sem haver canais no diretório → ambas escolhem `canal_00001`; uma segue, a outra encerra com `FileExistsError`, depois de já ter feito a coleta de metadados do canal.
- Prova: executei duas threads chamando `criar_canal` real em `TemporaryDirectory`, com barreira apenas para forçar ambas a observar o mesmo identificador. A saída foi `criados= ['canal_00001'] erros= ['FileExistsError']`.
- Conserto sugerido: criar o diretório em laço que trate `FileExistsError` e tente o próximo id, ou proteger a alocação por lock interprocesso.

## Não confirmados

- `mimetizar/espelho/baixar.py:170` (`baixar`): o código trata a presença física do arquivo como estado de download, mas também passa `--download-archive` ao yt-dlp. Se um vídeo baixado for apagado manualmente, o archive pode fazê-lo pular em tentativa futura mesmo estando ausente do disco. A hipótese depende do comportamento do yt-dlp instalado e não foi provada sem executar o binário/rede, proibidos nesta auditoria.
