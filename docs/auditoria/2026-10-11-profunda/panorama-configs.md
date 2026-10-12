# Auditoria profunda — Panorama (`visao/**`) e TODOS os configs

Data: 12/10/2026. Só relatório; nenhum código do projeto foi mudado. Provas em
`E:\tmp_pytest\prova_panorama_*` com `NEURAL_FIGHTS_RUNTIME_DIR` isolado, sem
rede e sem gravar estado real (o script está em
`C:\Users\adrian\AppData\Local\Temp\claude\e--projetos\65fe1aa9-...\scratchpad\prova_panorama.py`).
Onde um número veio do disco real, foi por leitura (`publicados.jsonl`,
`_atualizado_em.json`, `schtasks`, `contas.json`).

Já consertado em `f143cf5` e NÃO repetido aqui: veredito/recursos/dados do
painel dizendo "tudo em dia" sem ter verificado qualidade, metas, disco,
travas, freio, credenciais, OAuth e Agendador.

Regra desta parte, aplicada a cada contagem: (a) o que sai com ZERO eventos;
(b) numerador e denominador falam da mesma coisa; (c) exceção vira alarme ou
silêncio.

## Examinado

Parte A (`visao/**`), cada arquivo inteiro, função por função:

- `visao/panorama/__init__.py` — `resumo()` (cache de 3 s, trava única), `_seguro`, `esquecer`.
- `visao/panorama/saude.py` — `_fluxo`, `_historias`, `_paralelismo`, `agora`.
- `visao/panorama/desempenho.py` — `_publicados_de`, `_builds`, `_historias`, `_salvas`, `_por_plataforma`, `_piores_quedas`, `publicado`, `_quando_atualizou`.
- `visao/panorama/inventario.py` — `_videos_de_build`, `_videos_de_historia`, `_historias_por_etapa`, `_banco_do_jogo`, `_geracoes`, `estoque`.
- `visao/panorama/qualidade.py` — `_erros_recentes`, `_ledger`, `_alvos_do_jogo`, `problemas`.
- `visao/panorama/confiabilidade.py` — `_ledger`, `_diario`, `_marca_das_metricas`, `_conferencias`, `_dia_local`, `_laudo`, `_publicacoes`, `_num_destino_so`, `_destino_da_falha`, `_ref_de_teste`, `_do_diario`, `_hora_local`, `_resumo_conferencia`, `_metricas`, `_sinais`, `_alertas`, `_dia_curto`, `_alertas_de_metrica`, `hoje`.
- `visao/panorama/auditoria.py` — `_publicado`, `_publicados_hoje`, `metas`, `qualidade`, `producao`, `completa`, `_nao_verificado`, `veredito`.
- `visao/panorama/recursos.py` — `_disco`, `_travas`, `_freio`, `_credenciais`, `leves`, `_sem_verificar`, `situacao`, `completo`, `_horas_de_criacao`, `_tarefas_de_geracao`, `_agendador`, `_oauth_vivo`.
- `visao/tests/*.py` — lidos para não repetir o que já tem guarda (5 arquivos).
- Contratos que o panorama consome (lidos nos trechos usados): `builds/grade.py`, `builds/publicar/sinais.py` (inteiro), `builds/publicar/metricas.py` (`publicado`, `publicados`, marca por parte, `carregar_salvas`), `builds/publicar/conferencia.py` (`salvar`, `ultima`), `builds/atividade.py` (`recentes`, `estado_das_fabricas`, `estado_por_canal`), `builds/contas.py` (`tem_login`, `oauth_vivo`), `builds/tarefas_windows.py`, `contos/pipeline/controller.py` (`status`), `contos/imagens/fila.py` (`resumo`), `remoto/relatorios.py` (inteiro: `metas`, `funcionamento`, `auditoria`, `confiabilidade`), `remoto/vila_dados.py` (`_Placar`), `painel/paginas/{auditoria,confiabilidade}.py` (chamadas).

Parte B (configs), 26 arquivos, **1.638 chaves** (contando aninhadas; `_comment*`/`_porque*` fora), cada uma procurada em 455 arquivos de código fora de `tests/`:

- `random_builds/config/`: `captions.json`, `editing.json`, `frases.json`, `geracao.json`, `identity.json`, `moderacao.json`, `palco.json`, `probability.json`, `publicacao.json`, `render.json`, `rules.json`, `scoring.json`, `synergies.json`.
- `historias/config/`: `agenda.json`, `imagens.json`, `llm.json`, `publicacao.json`, `render.json`, `roteiro.json`.
- `mimetizar/config/`: `analise.json`, `biblia.json`, `capacidades.json`, `coleta.json`, `medidas.json`.
- `ias/config.json`, `coordenador/servicos.json`.
- Leitores conferidos por arquivo: `builds/pipeline/noite.py`, `contos/pipeline/agenda.py`, `builds/palco/config.py`, `coordenador/supervisor.py`, `ias/carteiro.py` + `ias/imagem.py`, `contos/llm/papeis.py` + `cliente.py`, `builds/publicar/{catalogo,youtube,youtube_web,tiktok,cortes}.py`, `contos/publicar/{catalogo,serie}.py`, `ferramentas/postar.py`, `contos/imagens/{fila,worker,cota}.py`, `mimetizar/espelho/*.py`, `builds/identity/{worker,client,prompt,config}.py`, `builds/editing/timeline_builder.py`, `builds/video/renderer.py`, `contos/video/{renderer,timeline}.py`, `builds/content/voz.py`, `builds/generation/probability_engine.py`.
- Caminhos/arquivos/contas conferidos no disco: Godot (`E:/ferramentas/godot/...console.exe`), `E:/projetos/palco/_userdata`, `C:\Python314\python.exe` e `pythonw.exe`, `E:\projetos\outputs`, as duas `outputs/_publicar`, as 4 fontes de `C:/Windows/Fonts`, `random_builds/.browser_profile/tiktok`, as 62 tarefas do Agendador, as contas de `%LOCALAPPDATA%\neural-fights\contas.json` (youtube/tiktok/youtube_web/chatgpt/gemini/picasso/digen/dreamface) contra os nomes que os configs citam. Todos existem; `NF_GODOT` não está definido (o config vale).

## Confirmados (do mais grave ao menos)

### 1. `panorama.auditoria.metas` conta LINHAS do ledger contra HORÁRIOS da grade

- **Onde:** `visao/panorama/auditoria.py`, `_publicados_hoje` (acumula `quando[11:16]` por plataforma) e `metas` (`saiu = len(por_plataforma[plataforma])`, `devido = len(grade.vencidos(agora, plataforma))`).
- **O defeito:** o numerador é "quantas linhas o ledger tem hoje" e o denominador é "quantos horários venceram". Duas linhas no mesmo horário (a parte cortada em dois Shorts desde `10142b1`, a recuperação que anda junto, o mesmo vídeo registrado duas vezes) pagam dois horários. É exatamente o defeito que `remoto/relatorios.py:metas` consertou em `9d09759` ("11/10 horários") e que a conferência conta certo (`horarios_cumpridos` por slot distinto) — esta terceira cópia ficou para trás. É este número que vai ao `veredito` ("N publicação(ões) faltando hoje"), ao relatório `auditoria` do Telegram e à página Auditoria do painel.
- **Quando acontece:** todo dia em que histórias corta uma parte em dois Shorts (medido no ledger real: 08/10 teve 2 linhas nos horários 06, 09 e 12; 11/10 no das 20). Um dia com 3 horários perdidos e 3 horários dobrados sai `faltando 0` e veredito verde.
- **Prova:** (disco real, só leitura) `auditoria.metas(datetime(2026,10,8,23,59))` → histórias `youtube {'saiu': 13, 'devido': 10, 'faltando': 0}` com **10 horários distintos** cumpridos — "13 de 10". (Runtime isolado) 3 linhas no mesmo horário 06:37, relógio 13:00 (4 vencidos) → `{'saiu': 3, 'devido': 4, 'faltando': 1}`; o certo é 1 cumprido, 3 faltando.
- **Conserto sugerido:** acumular um `set` de slots por (canal, plataforma) com `grade.slot(instante)` (ou `conferencia.chave_do_horario`, como o relatório faz) e `saiu = len(slots)`; limitar `saiu` ao `devido`; teste com duas linhas no mesmo horário dando 1, e com zero linhas dando `faltando == devido`.

### 2. `panorama.desempenho.publicado`: "atualizado em" é a data da MARCA, inclusive da coleta que falhou; e views/likes/retenção são só de builds

- **Onde:** `visao/panorama/desempenho.py`, `_quando_atualizou` (mtime do `*.json` mais novo em `metricas.PASTA`) e `_salvas` (`metricas.carregar_salvas()` sem canal → só `random_builds/outputs/_metricas`).
- **O defeito:** (a) `_atualizado_em.json` mora na mesma pasta e é regravada a cada rodada da coleta — também quando a parte termina em `estado: erro` (`_gravar_marca` grava a ficha de erro). O arquivo mais novo da pasta é sempre a marca, então a tela diz "atualizado hoje 07:45" mesmo com onze noites de coleta morta (o caso de 17–28/09). O campo existe justamente para "número velho apresentado como novo ser pior do que número nenhum", e é ele que mente. (b) `total` soma builds + histórias, mas `com_metrica`, `views`, `likes`, `retencao_media` e `piores_quedas` vêm só da pasta de builds: ao lado de "publicados 1072" aparecem as views de um canal só, sem dizer qual.
- **Quando acontece:** sempre. No disco real de 12/10 o arquivo mais novo da pasta é `_atualizado_em.json` (07:45) e o vídeo mais novo é `GRnPDxMGGto.json` (07:17); com a coleta falhando, só a marca anda.
- **Prova:** (runtime isolado) pasta com `vid1.json` datado de 2023 e uma marca `{"partes": {"builds": {"estado": "erro", ...}}}` gravada agora → `atualizado_em: 2026-10-12T19:41` (a hora da marca de ERRO); `total: 3 (builds 1 + historias 2)`, `com_metrica: 1`, `views: 10` (só builds).
- **Conserto sugerido:** `atualizado_em` sai de `metricas.ler_marca()` → `partes_da_marca` → o menor `ultimo_ok` entre as partes (ou um dicionário por parte), nunca de mtime; `_salvas` usa `metricas.salvas_de_todos()` e separa `views`/`retencao` por canal (`{"builds": ..., "historias": ...}`) em vez de uma soma sem dono; teste: marca de erro recém-gravada não pode mudar `atualizado_em`.

### 3. `panorama.confiabilidade.hoje`: diário ilegível e ledger ilegível viram ZERO sem alerta

- **Onde:** `visao/panorama/confiabilidade.py`, `hoje` (`lidos = _diario(); eventos = lidos or []`) e `_ledger` (`except Exception: return []`).
- **O defeito:** `_diario()` devolve `None` quando `atividade.jsonl` não abre, e `hoje` o troca por `[]`: `falhas_tiktok 0`, `falhas_youtube 0`, `valvula []`, `falhas_ignoradas []` — parecem medidas. Só os sinais recebem `None` (e ficam calados, por desenho). Nenhum alerta diz "não consegui ler o diário". O ledger que levanta na leitura vira `[]`: `prometido 0`, `provado 0`, `num_destino_so {}` e `cobertura_ids None` — outra vez zero sem motivo. É o terceiro medidor da lei desta parte: exceção no meio da coleta virando silêncio.
- **Quando acontece:** diário trancado por outro processo, poda no meio, disco C: cheio (o diário mora em `%LOCALAPPDATA%`), ledger com permissão negada.
- **Prova:** (runtime isolado) `sinais.ler_diario` → `None`, conferências e marca saudáveis → `veredito: ok`, `alertas: []`, `falhas_tiktok: 0`, `valvula: []`. `metricas.publicados` levantando `OSError` → `prometido: 0` e nenhum alerta sobre o ledger.
- **Conserto sugerido:** `hoje` guarda `diario_lido: bool` e `ledger_lido: {canal: bool}`; `_alertas` abre com "não consegui ler o diário (atividade.jsonl)" / "não consegui ler o ledger de X" e o veredito sai `atencao`; `_ledger` devolve `None` em vez de `[]` e `hoje` distingue. Teste do caso vazio: diário `None` ≠ diário `[]`.

### 4. `panorama.saude.agora` e `panorama.qualidade.problemas`: diário que não abre = "tudo ocioso, zero erros"

- **Onde:** `visao/panorama/saude.py:agora` e `qualidade.py:_erros_recentes`, por cima de `builds/atividade.py:recentes` (`except OSError: return saida` → `[]`) e `estado_das_fabricas` (fábrica sem evento → `ocioso`).
- **O defeito:** com o diário inexistente/ilegível, `fabricas` sai todo `ocioso`, `com_erro []`, `total_erros 0`, `erros_recentes []`. É o que a Vila mostra como "calmo" e o que o placar do celular (`vila_dados._Placar`: `problemas = total_erros`) serve como `0`. Ausência de leitura e ausência de erro ficam iguais.
- **Quando acontece:** mesmos gatilhos do item 3 (o diário é um arquivo só, em `%LOCALAPPDATA%`).
- **Prova:** (runtime isolado) `atividade._arquivo` apontando para pasta inexistente → `estado_das_fabricas` sem nenhuma fábrica fora de `ocioso`; `qualidade.problemas()["total_erros"] == 0`.
- **Conserto sugerido:** `saude.agora`/`qualidade.problemas` conferem `atividade._arquivo().is_file()` (ou `sinais.ler_diario() is None`) e devolvem `{"erro": "diário ilegível"}`, que `_seguro` já sabe mostrar; o placar da Vila mostra "?" em vez de 0 quando a família veio com `erro`.

### 5. `panorama.auditoria.veredito` ignora a família `producao` com erro

- **Onde:** `visao/panorama/auditoria.py`, `_NOMES = {"qualidade", "metas", "recursos"}` — `producao` ficou de fora do laço "não consegui verificar".
- **O defeito:** `producao()` nunca levanta (cada pedaço vira `{"erro": ...}`), mas `completa()` pode trazer `producao` ilegível e o veredito continua "tudo em dia". Mesmo padrão do `f143cf5`, só que para a quarta família; `historias_incompletas` como `{"erro": ...}` também não vira problema.
- **Quando acontece:** `contos.pipeline.agenda.incompletas` falhando (roteiro quebrado, pasta sem permissão).
- **Prova:** (runtime isolado) `veredito({"qualidade": {...3 liberados}, "metas": {"faltando": 0}, "producao": {"erro": "tudo quebrado"}, "recursos": {"alertas": []}})` → `{'cor': 'ok', 'frase': 'tudo em dia'}`.
- **Conserto sugerido:** incluir `producao` em `_NOMES` e tratar `historias_incompletas`/`estoque`/`agora` com `erro` como "não consegui verificar a produção: …".

### 6. `panorama.recursos._disco` mede o E:, mas quem para a produção é o C:

- **Onde:** `visao/panorama/recursos.py`, `RAIZ = Path(__file__).parents[2]` (= `E:\projetos`), `DISCO_CRITICO_GB 2 / DISCO_BAIXO_GB 8`.
- **O defeito:** `historias/config/agenda.json` e `random_builds/config/geracao.json` dizem `disco_a_vigiar: "C:/"` e `disco_livre_minimo_gb: 5` — abaixo disso nada novo é criado. O runtime, os perfis de navegador, o TEMP e o `user://` do Godot vivem no C:. A tela Recursos e o veredito olham só o E: (45 GB livres) e dizem "disco ok" enquanto o C: (12,75 GB em 12/10, e já esteve em 9) se aproxima do freio que de fato para a criação. A decisão `limpeza-do-disco` nasceu do C:.
- **Quando acontece:** sempre que o C: encosta nos 5 GB: a produção para por "disco" e a Auditoria diz que o disco está em ordem.
- **Prova:** `recursos._disco()` → `{'livre_gb': 45.4, 'total_gb': 465.2, 'situacao': 'ok'}`; `shutil.disk_usage("C:/")` → 12,75 GB; os dois configs vigiam `C:/`.
- **Conserto sugerido:** `_disco` devolve um dicionário por volume — o do repositório e o `disco_a_vigiar` de cada config (lido deles, não copiado) — e aplica `disco_livre_minimo_gb` do próprio config como limiar do alerta.

### 7. `ferramentas/postar.py:_visibilidade_das_historias` lê a chave no lugar errado — o ledger grava "public" seja qual for o config

- **Onde:** `ferramentas/postar.py:2883` — `(carregar_config() or {}).get("visibilidade")`. A chave mora em `historias/config/publicacao.json` → `youtube.visibilidade`; na raiz não existe.
- **O defeito:** `alvo` é sempre `None` → `"public"`, que é o que entra em `visibilidade` das linhas do YouTube de histórias (chamadas em 1517, 1565, 1784, 4528). O campo que o relatório `metas` usa para "vídeo NÃO público" e que a conferência compara com o canal vira uma constante, não uma leitura. Hoje o config diz `public`, então o número bate por coincidência; se o Adrian trocar para `private` no config, o publicador (`youtube_web.publicar`, que lê `youtube.visibilidade`) sobe privado e o ledger continua afirmando público — a divergência que a conferência existe para pegar nasce do próprio registro.
- **Quando acontece:** a qualquer mudança de `youtube.visibilidade` nas histórias.
- **Prova:** leitura do código (o `carregar_config()` de `contos.publicar.catalogo` devolve o JSON inteiro; `get("visibilidade")` na raiz → `None`). Ledger real de 7 dias: 103 linhas de histórias, todas `public` — coerente com a constante.
- **Conserto sugerido:** `((carregar_config() or {}).get("youtube") or {}).get("visibilidade")`, e gravar no ledger a visibilidade que o publicador de fato pediu (o laudo `prova` já a tem), não a do config.

### 8. `panorama.inventario.estoque` perde o `erro` do catálogo: catálogo quebrado = "0 prontos"

- **Onde:** `visao/panorama/inventario.py`, `_videos_de_build` devolve `{"prontos": 0, "erro": True}` mas `estoque` só copia `.get("prontos", 0)`; `_videos_de_historia` nem marca erro.
- **O defeito:** estoque zero de verdade (a válvula fecha, o canal para) e "não consegui contar" ficam idênticos: `videos_prontos.builds == 0`. É o número que o placar da Vila mostra como `prontos` e que a Auditoria usa na seção Produção.
- **Quando acontece:** `catalogo.listar()` levantando (pasta `outputs` inacessível, `publicacao.json` ilegível).
- **Prova:** (runtime isolado) `catalogo.listar` levantando `RuntimeError` → `videos_prontos: {'builds': 0, 'historias': 367, 'total': 367}`, sem chave `erro`.
- **Conserto sugerido:** `videos_prontos` leva `{"builds": None, "erro": "..."}` (ou `erros: [...]`) e `total` fica `None` quando um lado não contou; a Vila mostra "?".

### 9. `panorama.qualidade._alvos_do_jogo` lê um arquivo que nada escreve

- **Onde:** `visao/panorama/qualidade.py:55` — `RUNTIME_DIR / "relatorio_qualidade.json"`.
- **O defeito:** nenhum código do repositório grava `relatorio_qualidade.json` (grep em `random_builds`, `historias`, `neural_fights`, `ferramentas`, `remoto`, `painel`, `coordenador`); o arquivo não existe no runtime real. `qualidade_das_lutas` é sempre `{}` — a tela mostra "nunca avaliado" para sempre e ninguém estranha. Medidor que nunca mede não é ausência que faz procurar; é uma caixa vazia com rótulo.
- **Quando acontece:** sempre.
- **Prova:** `os.path.exists(%LOCALAPPDATA%\neural-fights\relatorio_qualidade.json)` → `False`; `qualidade._alvos_do_jogo()` → `{}`.
- **Conserto sugerido:** ou o relatório de qualidade de luta (`neural_fights/tools/qualidade_luta.py`) passa a gravar nesse caminho, ou o campo sai do panorama e da página.

### 10. `panorama.recursos._agendador` confere uma lista menor que a do relatório das 09:00

- **Onde:** `visao/panorama/recursos.py:_agendador` — `Historias_auto_HH` + `NeuralFights_gerar_HH` + `NeuralFights_postar_HH` + `NeuralFights_bot_telegram`.
- **O defeito:** `remoto/relatorios.py:_linhas_do_agendador` já confere também `NeuralFights_app_celular`; nenhum dos dois confere `NeuralFights_coordenador`, `NeuralFights_vila_flutuante` e `NeuralFights_capas_atrasadas`, que existem no Agendador (62 tarefas listadas em 12/10). Duas listas em dois lugares é o que a doc da parte chama de três cópias da grade. O app do celular é o único caminho de publicação do Adrian desde 28/09 e a tela Recursos não o cobra.
- **Quando acontece:** quando uma dessas tarefas some ou vira "só no AC": a Auditoria diz "tarefas em ordem".
- **Prova:** leitura dos dois arquivos + `Get-ScheduledTask` (só leitura).
- **Conserto sugerido:** uma função única (em `builds/tarefas_windows.py` ou no coordenador, que já tem `servicos.json`) devolvendo os nomes esperados; os dois leitores a chamam. Observação relacionada: `docs/sessoes/metricas.md` §3 diz que o `funcionamento` "ainda não confere" as `gerar_HH` — já confere; a doc está atrasada.

## Chaves de configuração com problema

| Arquivo | Chave | Leitor | Problema |
| --- | --- | --- | --- |
| `historias/config/publicacao.json` | `youtube.visibilidade` | `ferramentas/postar.py:2883` | leitor lê `visibilidade` na RAIZ (não existe) → sempre `"public"` no ledger (item 7) |
| `historias/config/publicacao.json` | `um_clique.tiktok` (true) | nenhum (`serie.py:207` só lê `tiktok_partes_por_clique`) | chave sem leitor; desligar aqui não desliga nada |
| `historias/config/agenda.json` | `piso_de_estoque` (1) | nenhum (só `tests/test_agenda_automatica_regressions.py:823`) | chave sem leitor; o piso real é `piso_de_reposicao`/`dias_de_gordura` |
| `historias/config/agenda.json` | `reparos_por_rodada` (6) | `agenda.py:478` (`or 6`) e `agenda.py:1809` (`or 2`) | dois padrões diferentes para a mesma chave; vale só se a chave sumir |
| `historias/config/agenda.json` | `minutos_minimos` (30), `minutos_por_historia` (150), `passos_por_rodada` (12) | `agenda.py:1645/1753`, `:1861`, `:1480` | padrão do leitor ≠ arquivo (90, 240, 1): com a chave apagada o comportamento muda muito sem aviso |
| `historias/config/render.json` | `colors.text_dim`, `colors.accent_alt` | nenhum | chaves sem leitor |
| `historias/config/render.json` | `camera.corte_aperto` (1.22) | nenhum (`camera_cfg.get` só lê `flash_frames`, `fundo_borrado`, `vinheta`; `timeline.py` lê `zoom`, `alternar`, `corte_visual_s`, `plano_minimo_s`) | chave sem leitor |
| `historias/config/imagens.json` | `max_attempts` (3) | nenhum nas histórias (`builds/identity/*` lê o `max_attempts` do `identity.json`, não este) | chave sem leitor; as histórias usam `tentativas_por_espera` |
| `historias/config/imagens.json` | `aprimorar_timeout` (90), `poll_interval` (3) | `builds/identity/picasso_client.py:615/766` (padrões 60 e 3) | lidas via o dicionário repassado ao cliente; `aprimorar_prompt` está `false`, então `aprimorar_timeout` é letra morta hoje |
| `random_builds/config/publicacao.json` | `tiktok.postar_automatico` (false) | `builds/publicar/tiktok.py:582` | a grade (`postar.py:3770`) passa `postar=True` e ignora o valor; só o painel obedece — o `false` não significa "a grade não posta" |
| `random_builds/config/publicacao.json` | `youtube.visibilidade` (private) | `youtube.py`, `youtube_web.py` | padrão do config é `private`, mas a grade e o app publicam `public` por parâmetro; o comentário "mudar aqui muda o padrão do painel" vale só para o painel |
| `random_builds/config/render.json` | `colors.text_dim` | nenhum | chave sem leitor |
| `random_builds/config/render.json` | `audio.voz.taxa` ("+0%"), `max_atempo` (1.1), `folga` (0.15) | `builds/content/voz.py:PADRAO` ("+12%", 1.35, 0.3) | padrão do leitor ≠ arquivo; vale só se a chave sumir |
| `random_builds/config/editing.json` | `durations.reveal` (3.6) | nenhum (`_push_reveal` usa `durations["nameplate"]` e `identity_slots`) | chave sem leitor |
| `random_builds/config/editing.json` | `identity_still.fundo_borrado` (true) | nenhum (`timeline_builder.py:680` lê só `motion` e `flash_frames`) | chave sem leitor |
| `random_builds/config/probability.json` | `presets.stat_generous`, `presets.body_normal` | nenhum (`roulette_factory.py` só pede `stat_default` e `{"kind": "uniform"}`) | presets nunca referenciados |
| `random_builds/config/identity.json` | `referencias.max_anexos` (1) | nenhum (`client.py:566`, `worker.py:217` leem `habilitado`, `ordem`, `folha_unica`, `modelo`) | chave sem leitor |
| `random_builds/config/identity.json` | `blocos_identidade.*` | nenhum em produção (só `tests/test_prompt_cobertura_regressions.py`) | é cópia do texto já colado nos `prompts`; editar aqui não muda o prompt |
| `random_builds/config/geracao.json` | `minutos_por_build` (27) | `noite.py:1106` (`15`) e `PADRAO` (15) | padrão ≠ arquivo; a doc do próprio config explica o 27 (medido) — só aviso |
| `mimetizar/config/biblia.json` | `tentativas_por_secao` (2) | nenhum | chave sem leitor |
| `mimetizar/config/coleta.json` | `cookies_do_perfil` (true) | nenhum (`baixar.py:_cookies` só entra com `--com-sessao` e lê `servico_do_cookie`) | chave sem leitor |
| `mimetizar/config/coleta.json` | `timeout_por_video_s` (1800) | nenhum em `baixar.py` (o lido é o de `medidas.json`, 3600) | chave sem leitor |
| `mimetizar/config/capacidades.json` | `capacidades[].faz` | nenhum (`preset.py` lê `nome`, `onde`, `palavras`) | texto nunca entra no prompt |
| `coordenador/servicos.json` | `servicos[].saude` ("porta 8931", "processo vivo", "pulso carteiro") | nenhum (`supervisor._saude` decide por `nome == "app"/"carteiro"`) | documentação disfarçada de config: mudar o texto não muda a checagem |
| `ias/config.json` | `rodizio_imagem` (["gemini","chatgpt"]) | `carteiro.py:728`, `imagem.py:206` (padrão inclui `"picasso"`) | padrão ≠ arquivo; com a chave apagada o Picasso (fora da roda por decisão de 06/10) volta ao rodízio |

Tudo o mais conferiu: nome igual, tipo igual (`horas` mistas int/"HH:MM" são normalizadas por `agenda.carregar` e `noite.carregar`; `grade_proibida: null` é aceito por `na_grade`), leitor existente. Sem referência a caminho, executável, pasta ou conta inexistente: as contas citadas (`youtube_web`, `historinhas`, `neural_fights`, `principal`) estão em `contas.json`; `picasso`/`digen`/`dreamface` têm `ativa: {}` (caem em `principal`, que existe).

## Não confirmados

- **`remoto/relatorios.py:metas` conta linha sem `publicado()`** — `_publicacoes` não filtra por `metricas.publicado`: uma linha com `publicado: False` (as que `curar_ledger.py` grava como `nao_confirmado`/`rascunho`) ou com `visibilidade: private` paga horário como se tivesse saído (só a seção "NÃO públicos" avisa). No ledger real dos últimos 7 dias há 0 linhas `publicado: False` e 0 não públicas, então não acende hoje; é da parte `app-e-bot`, fica registrado.
- **`confiabilidade._metricas` trata `vazio` como coleta boa** — parte com `estado: vazio` (0 vídeos) renova `ultimo_ok` e não alerta. Para o TikTok a doc diz que lista vazia já vira falha; para o YouTube, `atualizar` devolvendo `[]` num canal com 170 vídeos seria sintoma (ledger sem `youtube_id`), e passaria calado. Precisa de decisão: `vazio` acende quando o ledger tem linhas com id?
- **`panorama.resumo()` segura a trava durante toda a conta** (~159 s na primeira vez, por `vila_dados`): o painel (pulso 3 s), a página Confiabilidade (`forcar=True`) e o placar da Vila (`forcar=True`) se enfileiram atrás do mesmo lock e recalculam tudo a cada 3 s. Não é medidor errado, é custo; não medi a duração hoje.
- **`auditoria.metas` fatia o dia pelo calendário** (`quando.startswith(hoje)`) enquanto `relatorios.metas` usa o dia de grade: o post das 00:10 (recuperação das 23:37) entra no dia seguinte. Com `grade.vencidos` também pelo calendário, o par é coerente; a borda é a mesma que a doc já anota para o relatório.
- **`recursos._credenciais` cobra login do `picasso`** por canal, embora o PicassoIA esteja fora da roda (decisão `picasso-fora-da-roda`, 06/10). Hoje `tem_login` dá `True` para os dois canais, então não alerta; se o perfil for apagado, a tela vai pedir um login de um serviço que não se usa.
- **`confiabilidade.CONFERENCIA_VELHA_DIAS` e `idade_dias`** são calculados e exportados, mas nenhum alerta os usa (a idade da conferência virou `sinais.noites_sem_conferencia`). Código morto, não erro.
- **`desempenho._por_plataforma` e `_num_destino_so` assumem `youtube` para linha sem `plataforma`** — coerente com `relatorios` (que a deixa fora do placar) só em parte; no ledger real todas as linhas dos 7 dias têm plataforma.
- **`editing.json` / `frases.json` / `captions.json` com leitura dinâmica** (`final_by_verdict[verdict]`, `por_roleta[eixo]`, `moldura[eixo]`): os nomes de veredito batem 7/7 com `scoring.build_verdicts`; não conferi cada eixo de `frases.json` contra o banco do jogo (o `nf_bridge/cobertura.py` já faz isso).
