# Auditoria profunda — Publicação dos builds — 11/10/2026

Fatia: `random_builds/builds/publicar/**` (16 arquivos, 304 funções, 9 227 linhas), lidos
inteiros, função por função. Provas rodadas em `E:\tmp_pytest\prova_publicar_*` (pasta
temporária fora do repositório), com `travas._pasta`, `desfecho.arquivo_a_conferir`,
`metricas.REGISTRO` e `atividade.registrar` apontando para lá — só o que resolve caminho
e o diário; nenhuma função sob suspeita foi dublada. Os scripts estão em
`scratchpad\auditoria2\prova_publicar\prova1..6*.py` (sessão). Nada de rede, nada de
navegador, nada do estado real. Os defeitos da auditoria rasa da manhã (#1 pendentes do
ledger) já estão consertados no HEAD (`metricas.py` de 14:31) — o item 3 abaixo é um
efeito NOVO desse conserto, não a repetição dele.

## Examinado

- `__init__.py` — vazio.
- `audio.py` — 14 funções/1 classe; mede som do arquivo inteiro e de cada trecho de luta, lembra a medida por arquivo, guarda do funil `barrar_luta_muda`, marca/solta `[audio]` na lista "a conferir".
- `capa.py` — 4 funções; desenha `capa.png` 1280x720 do duelo com a arte de IA ou o glifo.
- `catalogo.py` — 28 funções/1 classe; varre `outputs/`, monta `Video` com título/descrição/hashtags, pendências, descartados, textos editados, exportar.
- `conferencia.py` — 28 funções; ledger × canal (fantasma/rascunho/órfão), `chave_do_horario`, dia de grade, fichas do dia, alarmes e sinais.
- `cortes.py` — 11 funções; corta parte > 180 s em Shorts nas fronteiras de cena, `preparar` devolve a lista de pedaços.
- `desfecho.py` — 12 funções/2 classes; classifica o resultado do clique, lista "a conferir" por canal/destino sob trava, `resolver` chamado de dentro dos publicadores.
- `escrita.py` — 7 funções/1 classe; escreve no campo (colar/digitar), lê de volta exigindo cada linha, fotografa a tela.
- `metricas.py` — 59 funções/1 classe; ledger (`publicado`, `prova_ok`, trava, pendentes, acrescentar/reescrever), API do YouTube (estatísticas, retenção), reconciliação por título, marca da noite, relatório.
- `recuperar.py` — 18 funções/4 classes; lê o canal pela API (UU+UUSH), privados recuperáveis, id pelo canal, mudar visibilidade, recolher duplicata.
- `sinais.py` — 13 funções; sinais de ausência (noite sem conferência, canal parado, cobertura de ids).
- `tiktok.py` — 24 funções/1 classe; upload pelo Studio do TikTok, legenda em 3 modos, confirmação, `corrigir_legenda`, login, sonda.
- `tiktok_metricas.py` — 19 funções/1 classe; métricas do TikTok pelo JSON interno do Studio, casamento pela hora, análise por vídeo.
- `titulos.py` — 5 funções; `chave`/`corte`/`repetido`, o critério único de "título igual".
- `youtube.py` — 22 funções/3 classes; porta única `publicar_como_configurado` (guarda de áudio, id por 3 fontes, capa, registro), API resumable, cota, capa com bloqueio por conta.
- `youtube_web.py` — 40 funções/3 classes; upload pelo YouTube Studio (diálogo, parede no Criar, escrita, crianças, assistente, espera do processamento, "Publicar mesmo assim", confirmação).

## Confirmados (do mais grave ao menos)

### 1. "Publicar mesmo assim" na tela sem conseguir clicar vira "publicado" — gravidade: média
- Onde: `youtube_web.py:950-972` (`_confirmar`)
- O defeito: quando o aviso "Publicar mesmo assim" está na tela mas `assim.click()` levanta (ele só faz `passo(...)` e NÃO `continue`), a mesma volta do laço cai na checagem de `SINAIS_PUBLICADO`; o diálogo do Studio por trás do aviso sempre mostra "Link do vídeo", então a função devolve a URL e o vídeo entra no ledger como publicado — e no canal fica RASCUNHO. É a fábrica dos 30 rascunhos de 15/09 de volta pela porta do clique que falha (o que já aconteceu no Criar: backdrop engolindo o clique, 06/10).
- Quando acontece: o Studio abre o aviso, algo cobre o botão (overlay/backdrop, página lenta) e o Playwright estoura o clique → `estado = "https://youtu.be/…"` → `youtube.publicar_como_configurado` grava a linha; a fila nunca mais escolhe o vídeo (ledger diz "publicado"), o horário fica sem vídeo público e só a conferência da manhã acusa "rascunho".
- Prova: `python prova2_publicar_assim_sem_clique.py` (página de mentira com o aviso presente e `click()` levantando): `passos: ["achei 'Publicar mesmo assim' mas nao consegui clicar (RuntimeError)."]`, `_confirmar -> 'https://youtu.be/AbCdEfGhIjK'`, `youtube_web.confirmado -> True`, `desfecho.classificar -> publicado`.
- Conserto sugerido: com o aviso visível e o clique falhando, `continue` (tentar de novo até o prazo) e, no fim do prazo com o aviso ainda na tela, devolver a frase de "sem confirmação… pode ter ficado como RASCUNHO" — nunca os sinais da página de trás.

### 2. Marca `[audio]` não é trocada pela de clique sem confirmação, e o som voltando solta um vídeo que pode estar no ar — gravidade: média
- Onde: `desfecho.py:282-283` (`marcar_para_conferir`: `if video_id in dados: return True`); quem solta é `audio.py:317-352` (`revisar_marcas`) via `desfecho.soltar_marca(prefixo="[audio] ")`.
- O defeito: `marcar_para_conferir` devolve True sem tocar no arquivo quando o id já está lá, qualquer que seja o motivo da marca antiga. Uma marca de áudio (que a máquina solta sozinha) nunca é promovida à marca de clique (que só pessoa tira). `revisar_marcas` então solta a marca e o vídeo volta à fila com o clique já dado.
- Quando acontece: a fila marcou `[audio]` no TikTok (ou YouTube); o re-render devolveu o som antes de `revisar_marcas` rodar; alguém publica pelo `main.py publicar <id> --tiktok --postar` (esse caminho não consulta a lista "a conferir"; o app consulta, `remoto/acoes.py:710`), a guarda de áudio passa, o clique sai sem confirmação → `resolver` → "já avisado", marca segue `[audio]` → próxima rodada `revisar_marcas` vê som → solta → o vídeo é reescolhido e sobe de novo (duplicata no perfil).
- Prova: `python prova1_marca_nao_sobe.py`: `1) marca de audio gravada: '[audio] a luta esta muda…'`; `2) desfecho.resolver -> sem_confirmacao | marca no arquivo: '[audio] a luta esta muda…'` (1 aviso no diário dizendo "cliquei… pode estar no ar", mas o arquivo não mudou); `3) audio.revisar_marcas -> [('generation_00099:build:celular','tiktok')]`, `a_conferir(builds, tiktok) agora: set()`.
- Conserto sugerido: em `marcar_para_conferir`, se a marca existente começa com um prefixo que a máquina solta (`[audio] `) e a nova não tem prefixo (clique), REESCREVER o `estado` (e o `quando`); só devolver True sem gravar quando a marca nova não é mais forte.

### 3. Com uma pendente na fila lateral, o registro da publicação reescreve o ledger e, no Windows, um leitor aberto faz a linha nova SUMIR — gravidade: média (consequência alta, gatilho raro)
- Onde: `metricas.py:239-248` (`acrescentar_ao_ledger` chama `reescrever_ledger` quando há pendentes), `metricas.py:261-278` (`reescrever_ledger`: `os.replace` sem tratar erro, temporário fica), `metricas.py:324-344` (`registrar_publicado` engole tudo com `print`).
- O defeito: o conserto da manhã fez o escritor de uma publicação reescrever o arquivo inteiro sempre que existe pendente. `os.replace` sobre um arquivo que outro processo tem aberto para leitura (bot `/metas`, app, painel flutuante, conferência, `postar --ver`) falha no Windows com `PermissionError` (Python abre sem `FILE_SHARE_DELETE`). A linha nova não vai para o ledger NEM para a fila de pendentes; o `.tmp` fica órfão na pasta. Nos builds `registrar_publicado` engole a exceção e devolve `None` sem linha no diário: a publicação "deu certo" e não existe no ledger → reescolhida no horário seguinte (repostagem). Nas histórias `serie.registrar` não engole: a exceção sobe DEPOIS do upload e a ficha diz "YouTube falhou"; `ja_publicado` segue falso e a parte sobe de novo.
- Quando acontece: existe ≥1 arquivo em `publicados.jsonl.pendentes/` (alguém esperou 120 s pela trava) E um leitor está com o ledger aberto no instante do `os.replace`. Raro, mas o resultado é exatamente "publicação sem ledger = repostagem".
- Prova: `python prova3_ledger_pendente_replace.py` (ledger com 1 linha, 1 pendente, leitor aberto): `acrescentar_ao_ledger levantou: PermissionError: [WinError 5] Acesso negado: '…\tmpeh6jbb5u.tmp' -> '…\publicados.jsonl'`; `ledger no disco: ['antiga']`, `pendentes depois: ['pendente']`, `publicados() ve: ['antiga', 'pendente']` (a `NOVA` não está em lugar nenhum), `temporarios orfaos na pasta: ['tmpeh6jbb5u.tmp']`; e pelo caminho real `registrar_publicado -> None | linhas no diario: 0`.
- Conserto sugerido: em `acrescentar_ao_ledger`, com pendentes, fazer o APPEND da linha nova primeiro (o append não falha por leitor aberto) e só então tentar incorporar as pendentes por reescrita; se a reescrita falhar, apagar o `.tmp`, deixar as pendentes onde estão e avisar no diário (não `print`). `registrar_publicado` deve escrever no diário (ERRO) quando o registro falha.

### 4. O laudo do YouTube não guarda a prova do clique; exceção depois do clique vira "falha" e o vídeo volta à fila — gravidade: média
- Onde: `youtube_web.py:1510-1543` (`publicar`: `pronto.click()` sem `laudo["clicou"] = True`; compare `tiktok.py:725`), `desfecho.py:94` (`classificar` só vê `laudo["clicou"]`), `desfecho.py:242-248` e `:287-298` (`resolver` levanta `NaoConsegviMarcar` DEPOIS do clique).
- O defeito: o TikTok grava `laudo["clicou"]` no instante do clique "para sobreviver a qualquer exceção"; o YouTube não. Se algo levanta entre o clique e o fim (`desfecho.resolver` com a trava `youtube_a_conferir` ocupada por 20 s, arquivo ilegível ou gravação falhando; `progresso`/`_linha` levantando, como em 05/10), `publicar_como_configurado` não registra, o `postar` classifica pela ficha como falha comum (não é de rede → não repõe, mas também não marca) e o vídeo é reescolhido no horário seguinte: rascunho gêmeo ou duplicata no YouTube.
- Quando acontece: clique dado, Studio sem confirmação, e a marca "a conferir" não grava (trava ocupada pelo app/bot lendo, `.json` corrompido, disco) → `NaoConsegviMarcar` sobe; ou qualquer exceção no `passo`/`progresso` após o clique.
- Prova: `python prova4_youtube_sem_clicou.py`: `youtube_web.py grava laudo["clicou"]? False`, `tiktok.py … True`; `classificar('', falha, laudo do YouTube) -> falha` contra `… laudo do TikTok -> sem_confirmacao`; com outra thread segurando a trava: `resolver levantou depois do clique: NaoConsegviMarcar: a trava esta ocupada`, `a_conferir(historias, youtube) depois: set()`, laudo sem `clicou`.
- Conserto sugerido: `laudo["clicou"] = True` logo antes/depois de `pronto.click()` em `youtube_web.publicar`; e no `postar`, para o YouTube, tratar `prova.get("clicou")` como o TikTok já trata (`falha["clicou"]` → não repor, marcar "a conferir" quando a marca falhou… ou ao menos não reescolher no horário seguinte).

### 5. `cortes.pedacos` devolve pedaço de 1,5 s ou de duração negativa — gravidade: baixa
- Onde: `cortes.py:170-191` (`pedacos`, o laço que aumenta `quantos`), `cortes.py:143-157` (`_mais_perto`).
- O defeito: quando a fronteira escolhida fica mais à direita que o ponto ideal do pedaço SEGUINTE (acontece ao subir `quantos`, que encolhe `alvo` sem limitar a escolha ao próximo ideal), o corte seguinte cai antes do anterior: fatia negativa (o `ffmpeg -t` negativo falha e `preparar` manda o vídeo inteiro, fora do Shorts) ou fatia de 1,5 s, abaixo de `MINIMO_S` — e esta SOBE como Short "(5 de 11)".
- Quando acontece: só em vídeo longo com cenas longas (o menor caso achado: 598,7 s com fronteiras em 159,7/384,5/417,6 → pedaço de 11,4 s). Hoje nenhuma parte passa de 182 s, então é latente.
- Prova: `python prova5_cortes_fatia_degenerada.py`: `duracao 1137.5s … fatias abaixo de 12s: [(515.5, 517.0, 1.5)]`; `duracao 1135.5s … [(438.2, 412.9, -25.3)]`; `video mais curto achado com fatia degenerada: (598.7, …)`. Em 200 000 sorteios de 181–1200 s, 63 casos.
- Conserto sugerido: em `pedacos`, limitar `maximo` a `min(anterior + limite, duracao - MINIMO_S, ideal + alvo - MINIMO_S)` e, se alguma fatia sair < `MINIMO_S` ou negativa, descartar o resultado e seguir para `quantos + 1` (ou cair no corte no relógio).

### 6. `_nomes_no_banco` guarda a FALHA de leitura para o resto do processo — gravidade: baixa
- Onde: `catalogo.py:131-143` (`@lru_cache(maxsize=1)` devolvendo `None` em `except`), usado por `_falta_estreia` (`catalogo.py:146-167`).
- O defeito: `lru_cache` guarda `None` como resposta válida; uma leitura do banco que falhou uma vez (arquivo em uso, JSON meio escrito pela pipeline) faz toda build sem estreia dizer "sem luta no fim (estreia nao gravada)" — tarefa — em vez de "estreia impossivel" — lápide —, até o processo morrer. O app (24 h) e o bot leem isso nas pendências.
- Quando acontece: primeiro `pendencias_da_build` do processo coincide com o banco trancado/em escrita.
- Prova: `python prova6_nomes_no_banco_cache.py`: `1a chamada (banco falhou): None`, `2a chamada (banco legivel): None | carregar_database chamado 1 vez(es)`, `_falta_estreia … : sem luta no fim (estreia nao gravada)`; depois de `cache_clear`: `estreia impossivel: 'Lucrecia' nao esta mais no banco`.
- Conserto sugerido: não cachear `None` (cache manual: só guardar quando a leitura deu certo).

## Não confirmados

- `youtube_web.publicar` (linhas 1435-1441): se o rádio da visibilidade não é achado, publica "como o Studio deixou" e `youtube.publicar_como_configurado` grava no ledger a visibilidade PEDIDA (`_visibilidade_efetiva`, `youtube.py:199-215`), não a que valeu — vídeo privado com ledger "public". Precisa do Studio real para provar que o rádio some sem o resto sumir.
- `youtube_web._confirmar` (linhas 941-973), variante de tempo do item 1: "Link do vídeo" está no diálogo ANTES do aviso aparecer; se o aviso "Publicar mesmo assim" demora mais que a cacada de ~6 s (`_primeiro` com 6 seletores × 1 s), a função devolve a URL na primeira volta. Só se mede com o Studio de verdade.
- `tiktok._publicou` (linha 180): URL que muda para qualquer coisa sem "/upload" conta como publicado — um redirecionamento para `/login?redirect_url=%2Ftiktokstudio%2Fupload` (sessão caindo entre o clique e a leitura) viraria "publicado no TikTok" com linha no ledger. Não há como provar sem a sessão real expirando.
- `audio.barrar_luta_muda` (linhas 288-294): trecho `_segments_<perfil>/seg_NNN.mp4` ausente deixa a guarda CEGA (`None` → publica com linha de erro). Com a decisão `arquivo-de-videos` (vídeos para o Google Drive) isso pode virar sistemático; não medi se as pastas `_segments_*` estão sendo movidas.
- `conferencia.salvar` (linha 521), `metricas._gravar_marca` (1048), `audio._gravar_lembrado` (183), `youtube._gravar_bloqueios_da_capa` (496): o mesmo `os.replace` do item 3 contra um leitor aberto (o painel lê a ficha do dia a cada 3 s). Nos três últimos a exceção é engolida (só custa medir de novo); em `conferencia.salvar` vira "nao gravei a ficha" no log e a ficha do dia some (alarme de "noite sem conferência" no dia seguinte). Não achei ocorrência no diário.
- `youtube_web.publicar` (linha 1248): `postar` padrão é `True` quando `youtube.postar_automatico` não existe no config (não existe), ao contrário do TikTok (`False`). Hoje só `publicar_como_configurado` chama, e passa `postar=True` explícito — não é defeito em uso, mas um chamador novo "para conferir antes" publicaria.
- `metricas.idade_em_dias` (1087-1103): com `agora` ingênuo e `publicado_em` com fuso, tira o fuso sem converter (até 3 h de erro na idade; piso de 1 dia esconde). Só afeta `views_por_dia` de vídeos de menos de um dia.
- Testes: `test_parede_no_criar_regressions.PublicarLigacaoTests` roda `youtube_web.publicar` de verdade e `arquivo_a_conferir` sai de `metricas.REGISTRO` (não do runtime isolado pelo `conftest`); hoje todos os casos levantam ANTES do clique, então nada é gravado em `random_builds/outputs/_publicar/`, mas um caso novo que chegue a `desfecho.resolver` escreveria a lista "a conferir" REAL. Não é defeito hoje; é uma porta aberta.
