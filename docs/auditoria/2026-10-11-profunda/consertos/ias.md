# Consertos — parte ias (carteiro, correio, fichas das IAs, perfis de navegador)

- **Relatórios de origem:** `ias.md` (11 defeitos) e `maquina.md`, "O que precisa de ação" itens 3 e 9.
- **Verificado em 14/10/2026** no ramo `refactor/arquitetura` (f670aa9). O último commit em `ias/` é de 10/10 (b71f02e, só o `avisar_telegram`). Nenhum ramo não mesclado mexe em `ias/`.
- **Contagem:** 13 abertos, 0 consertados, 0 falsos.
- **Provas rodadas hoje** em pasta descartável (`NF_IAS_PASTA`, `NEURAL_FIGHTS_RUNTIME_DIR` e `LOCALAPPDATA` em `E:\tmp_pytest`, já apagada), com o script `scratchpad\provas_ias_verif\p_verif.py`. Os itens 1, 2, 3, 9, 10 e 11 foram reproduzidos. Os itens 4, 5, 6, 7 e 8 foram confirmados lendo o código, e o 5 também pelo log de 12/10.

Todos os abertos são médios ou baixos. Nenhum apaga dado sem volta nem publica errado sozinho. O IAS-3 piora a imagem que vai para o vídeo, mas não troca o vídeo.

### IAS-1 — Cota de imagem do Gemini não é reconhecida: ele nunca sai do rodízio e cada pedido gasta 2 turnos  (médio)
- **Onde:** `ias/imagem.py:355` (`classificar`), `ias/catalogo.py:31-44` (padrão `limite`), `ias/carteiro.py:1079-1093` (`_turno_imagem`, reforço), `ias/fichas/gemini.json` (`catalogo_textos`).
- **Defeito:** quando a cota acaba, o Gemini responde «Poderei criar mais imagens assim que seu limite for redefinido». `classificar` devolve `exc.categoria` (`sem_imagem`) de qualquer `ImagemFalhou` antes de olhar o texto. O regex de `limite` também não casa a frase. Resultado: `fora_de_cota("gemini")` fica sempre vazio, e o carteiro ainda repete o pedido com `REFORCO_IMAGEM` numa conversa nova.
- **Conserto:**
  1. Em `catalogo.PADROES["limite"]`, acrescentar `|limite\s+(?:for|seja|ser)\s+redefinid|criar\s+mais\s+imagens\s+assim\s+que`.
  2. Em `fichas/gemini.json` → `catalogo_textos`, incluir `{"texto": "Poderei criar mais imagens assim que seu limite for redefinido", "categoria": "limite"}`.
  3. Em `imagem.classificar`, quando `isinstance(exc, SemImagem)`, rodar antes `achado = motivo_da_tela(ia, tela or str(exc))`. Se a categoria do achado estiver em `CATEGORIAS_DE_COTA`, devolver o achado. Aqui o texto da exceção é a própria resposta da IA na tela, então vale como evidência, ao contrário do `classificar_erro`.
  4. Em `_turno_imagem`, antes do reforço: se `catalogo.classificar(str(recusa))` estiver em `("limite", "upgrade")`, relançar sem a segunda tentativa.
- **Teste que prova:** `ias/test_cota_do_gemini.py`. Usa `fabrica_duble(imagem_falhar=SemImagem("…«Poderei criar mais imagens assim que seu limite for redefinido…»"), tela=<frase>)` e um pedido ao `gemini`. Afirma:
  - `situacao == "falhou"` e `categoria == "limite"`;
  - o dublê recebeu 1 `gerar_imagem`, não 2;
  - `imagem.fora_de_cota("gemini") != ""`;
  - um pedido `livre` seguinte, com `rodizio_imagem=["gemini","chatgpt"]`, vai ao `chatgpt`.

  Hoje dá `sem_imagem`, 2 turnos e o gemini de novo.
- **Origem:** `ias.md` #1; `maquina.md` item 3 (IAS-M3, parte da cota). A parte "histórias caindo no Flash" do item 3 já está em `consertos/historias.md` HIS-2 e HIS-11.

### IAS-2 — `entregar()` síncrono devolve o pedido ainda pendente e reservado; ele vaza e é entregue 4 h depois  (médio)
- **Onde:**
  - `ias/carteiro.py:963-979` (`_rede_caiu`), `:866-869` (`_entregar_com_a_conta`), `:1099-1100` (`_turno_imagem`), `:697-702` (`_com_a_conta`);
  - `ias/correio.py:385,422-433` (`RESERVA_MAX_S`, `reservado_por_outro`);
  - quem chama: `historias/contos/imagens/worker.py:271` e `random_builds/builds/identity/worker.py:733`.
- **Defeito:** "volta para a fila" só faz sentido no laço do carteiro de serviço. O worker recebe `pendente`, trata como falha e pede outro. O pedido velho fica reservado. Passadas 4 h, o carteiro de serviço o entrega: gasta a conta e manda ao Telegram uma imagem que ninguém lê. Em 09/10 foram 629 pedidos assim.
- **Conserto:**
  1. `Carteiro(..., de_servico=False)` por padrão (o mesmo parâmetro do IAS-6).
  2. Em `_rede_caiu`, se `not self.de_servico`, devolver `False` para a falha seguir. Em `classificar_erro`, uma exceção que casa `REDE_CAIU` vira categoria `"rede"` com o motivo "a rede caiu (DNS/internet); tente de novo quando voltar".
  3. Em `_com_a_conta`, o bloco "larga esta espera para a conta livre" (`:697-702`) só roda se `self.de_servico`.
  4. No fim de `entregar()`, se `not self.de_servico` e a mensagem devolvida ainda estiver `pendente` ou `entregue` por este pid, chamar `_falhar(..., categoria="interrompida")`.
  5. Em `_varrer_abandonadas`, marcar também `falhou` / `abandonado` o pedido `pendente` com `dono` cuja reserva passou de `RESERVA_MAX_S` (`correio._idade_da_reserva(m) > RESERVA_MAX_S`), em vez de deixá-lo virar livre.
- **Teste que prova:** `ias/test_entregar_sincrono.py`.
  - (a) Um `Carteiro(ajustes={"janela_conversa_s": 0})` com `fabrica_duble(imagem_falhar=RuntimeError("net::ERR_NAME_NOT_RESOLVED"))` e um pedido `dono=os.getpid()`. Afirma que `entregar()` devolve `situacao == "falhou"` e `categoria == "rede"`. Hoje devolve `pendente`, o que foi reproduzido.
  - (b) Um pedido com `dono=os.getppid()` (vivo) e `reservado_em` de 5 h atrás. Afirma que `_varrer_abandonadas()` o marca `falhou` e que `proxima_pendente(so_livres=True)` devolve `None`. Hoje ele volta como livre.
- **Origem:** `ias.md` #2.

### IAS-3 — Download pelo botão cai (`TargetClosedError: Download.path`) e a prévia do `src` entra calada como imagem final  (médio)
- **Onde:** `ias/imagem.py:907-938` (`_bytes_do_download`), `:861-868` (`baixar_pelo_botao`), `:1026-1037` (`baixar_da_resposta`), `:344-346` (`guardar`); `ias/carteiro.py:143` (`chrome_caiu`) e `:1142-1146` (resposta no correio).
- **Defeito:** continua acontecendo. Em `historias/outputs/_logs/auto_20261012.txt` há 118 linhas `Download.path` e 47 imagens `src_da_tela` contra 42 pelo botão. O pedido `6bfdf416` ficou com 142 KB pela prévia, quando os vizinhos tinham ~3,2 MB pelo botão.
  - `path()` e `save_as()` morrem os dois com "Target page, context or browser has been closed".
  - O `chrome_caiu` lê "TargetClosed" e fecha e reabre a sessão (~1 min).
  - No fim a prévia do Gemini (metade da resolução) é gravada como se fosse o original.
  - O resumo no correio só diz `prova: turno_na_casa`, sem dizer que foi a prévia.
- **Conserto:**
  1. Em `guardar`, copiar `prova.get("download")` para o resumo (`"download": ...`). Em `_turno_imagem`, quando `salvo["download"] == "src_da_tela"` e `botoes_de_baixar` existe para a IA, escrever na resposta `"imagem pronta · WxH · prévia (o original não baixou)"` e gravar `previa=True` no delta.
  2. Em `baixar_pelo_botao`, quando `_bytes_do_download` falhar com `TargetClosedError` e `cliente.page.is_closed()` for `False`, clicar no botão mais UMA vez antes de desistir. A página está viva: no log, a imagem seguinte baixa normal.
  3. Em `_turno_imagem`, `chrome_caiu(exc)` só levanta `_ReabrirImagem` se `sessao.cliente.page.is_closed()` (ou se a sessão não responder). Com a página viva, segue para a reserva sem fechar o navegador.
  4. Ver em "Decisões que são do Adrian" se a prévia do Gemini deve ser aceita marcada ou recusada.
- **Teste que prova:** `ias/test_download_previa.py`.
  - Um cliente dublê cujo `Download.path()` e `save_as()` levantam `TargetClosedError`, com `page.is_closed()` `False` e `baixar()` devolvendo um PNG 64x64. Afirma que `baixar_da_resposta(...)["prova"]["download"] == "src_da_tela"` e que o botão foi clicado 2 vezes (hoje 1).
  - Pelo carteiro com dublê, afirma que `guardar(...)["download"] == "src_da_tela"` e que a resposta no correio contém "prévia". Hoje o campo não existe.
- **Origem:** `ias.md` #5; `maquina.md` item 9 (IAS-M9).

### IAS-4 — Mensagem "entregue" por um carteiro que morreu fica órfã para sempre  (médio)
- **Onde:** `ias/correio.py:448-482` (`reivindicar`: retoma só com `_entregador(m) == meu`), `:373` (`pendentes`); `ias/carteiro.py:1368-1389` (`_varrer_abandonadas`).
- **Defeito:** se o processo morre depois do `pendente → entregue`, nenhum carteiro novo retoma a mensagem e ninguém a marca falhou. O app mostra "em andamento" para sempre, sem aviso.
- **Conserto:** em `_varrer_abandonadas`, percorrer também `correio.ler(caixa)` com `situacao == "entregue"` e `correio._pid_vivo(correio._entregador(m)) is False` (e entregador diferente de `os.getpid()`):
  - **texto:** `atualizar(situacao="pendente", entregador=None, nota="o carteiro anterior caiu no meio; volta para a fila")`;
  - **imagem:** se houver `chat_imagem_url`, `pendente` com `nota` igual (a recuperação usa a URL). Sem a URL, `falhou` com `categoria="interrompida"` e erro "o carteiro que entregava (processo N) morreu no meio".
- **Teste que prova:** `ias/test_entregue_orfa.py`.
  - Uma mensagem de texto `entregue` com `entregador=999999` e `correio._pid_vivo` dublado para `False`. Afirma que, depois de `c._varrer_abandonadas()`, ela fica `pendente` e `proxima_pendente(so_livres=True)` a devolve. Hoje continua `entregue`.
  - O mesmo com uma imagem sem URL. Afirma `falhou` / `interrompida`.
- **Origem:** `ias.md` #6.

### IAS-5 — `gravar_casa` sem nova tentativa e `rodar()` sem proteção: a resposta obtida vira "falhou" e o carteiro morre  (médio)
- **Onde:**
  - `ias/correio.py:619-625` (`gravar_casa`), `:646` (`gravar_resumo_da_casa`), `:692` (`gravar_estado_do_carteiro`);
  - `ias/carteiro.py:1245-1254` (`_um_turno`), `:880-884` (`_entregar_com_a_conta`), `:1133-1138` (`_turno_imagem`), `:1429-1443` (`rodar`).
- **Defeito:** no Windows, `os.replace` sobre um `casa.json` aberto por outro processo dá `PermissionError`. Em `_um_turno` isso acontece depois de a IA responder e antes de gravar `respondida`, fora do `try`. A resposta se perde, a mensagem vira falhou, e uma segunda falha no `except` derruba `rodar()`.
- **Conserto:**
  1. Em `correio`, uma função `_substituir(tmp, alvo)` que tenta `os.replace` 6 vezes com pausa de 0,15 s quando dá `PermissionError`. Usar nas três funções de gravação e em `registrar_presenca`.
  2. Em `_um_turno` e `_turno_imagem`, chamar `correio.atualizar(... situacao="respondida" ...)` ANTES do `gravar_casa`, e envolver o `gravar_casa` em `try/except OSError` com log.
  3. Em `_entregar_com_a_conta:882-884`, também `try/except OSError`.
  4. Em `rodar()`, envolver `self.uma_volta()` em `try/except Exception`: logar o traceback, `self._estado("ocioso", nota=f"volta falhou: {type(e).__name__}")`, `self.dormir(intervalo)` e seguir.
- **Teste que prova:** `ias/test_gravar_casa_trancada.py`.
  - (a) Com `correio.os.replace` dublado para levantar `PermissionError` nas 2 primeiras chamadas, `gravar_casa` grava.
  - (b) Com `correio.gravar_casa` sempre levantando `PermissionError`, `Carteiro.entregar` de uma mensagem de texto com dublê respondendo "resposta boa" devolve `respondida` com `resposta == "resposta boa"` e não levanta. Hoje levanta e a mensagem fica `falhou`.
  - (c) `rodar(parar=...)` com um `uma_volta` que levanta na 1ª volta chega à 2ª volta.
- **Origem:** `ias.md` #4.

### IAS-6 — `carteiro.json` e o diário são escritos por qualquer `Carteiro` (o do worker também), e "entregando" sai antes de ter a conta  (médio)
- **Onde:** `ias/carteiro.py:614-622` (`_estado`), `:684-685` (`_com_a_conta`), `:1360-1365` (`_diario`, canal `"adrian"`), `:1500-1528` (`main`); `ias/correio.py:692-698`. Quem lê: `coordenador/supervisor.py:398-431`.
- **Defeito:** o worker das histórias e o do identity sobrescrevem `carteiro.json` com o PID e o estado deles (reproduzido hoje). Isso faz três estragos:
  - o app mostra o estado do worker;
  - o `supervisor.seguro("carteiro")` recusa o reinício, e `_interromper_entrega` pode marcar "interrompida" o pedido do worker;
  - quando o worker termina, o PID morto vira "parado" e a saúde fica ruim.

  No diário, as linhas do worker saem com `canal=adrian`.
- **Conserto:**
  1. Parâmetro `de_servico: bool = False` no `Carteiro.__init__`, e `main()` passa `de_servico=True`. Com `de_servico=False`, `_estado` não grava nada e `_diario` usa o canal `"pipeline"` em vez de `"adrian"`.
  2. Em `_com_a_conta`, a primeira volta grava `"esperando_trava"`. Só `_entregar_com_a_conta` (`:821`) grava `"entregando"`.
  3. Ajustar o helper `_novo` dos testes (`test_imagem.py`, `test_varredura_0510.py`, `test_correio.py`, `test_upgrade_do_rodape.py`) para `de_servico=True` onde afirmam o estado.
- **Teste que prova:** `ias/test_estado_so_do_servico.py`.
  - (a) Grava `gravar_estado_do_carteiro({"situacao": "ocioso"})` com `pid` de serviço e entrega um pedido por `Carteiro(ajustes={"janela_conversa_s": 0})` dublado. Afirma que `carteiro.json` não mudou (`pulso_em` e `situacao` iguais). Hoje fica com o pid do worker.
  - (b) `Carteiro(de_servico=True)` com a trava ocupada e `correio.gravar_estado_do_carteiro` capturado. Afirma que o 1º estado é `"esperando_trava"`.
- **Origem:** `ias.md` #3.

### IAS-7 — O rodízio do carteiro de serviço é fixo (Gemini sempre primeiro) e o `config.json` só vale depois de reiniciar  (médio)
- **Onde:** `ias/carteiro.py:566-567` (`self.ajustes = dict(config())`), `:728-729` (`_entregar_livre`: `self.ajustes.get("rodizio_imagem") or imagem.rodizio_ordem()`).
- **Defeito:** ACHADO NOVO além do `ias.md` #9. Como o `config.json` sempre tem `rodizio_imagem`, o `or imagem.rodizio_ordem()` nunca roda no carteiro de serviço. O pedido `livre` vai sempre ao primeiro livre da lista (gemini), e a divisão "vai quem gerou há mais tempo" decidida em 03/10 só vale fora dele. Reproduzido hoje: com o gemini tendo acabado de gerar, `rodizio_ordem() -> ['chatgpt','gemini']` e o pedido foi ao gemini. Além disso, `cota_pausa_h`/`rodizio_imagem` editados no `config.json` só valem depois de reiniciar, porque o coordenador só religa por `*.py`.
- **Conserto:**
  1. No `__init__`, guardar `self._ajustes_do_chamador = dict(ajustes or {})`. Em `uma_volta`, reler `self.ajustes = {**config(), **self._ajustes_do_chamador}`.
  2. Em `_entregar_livre`: `ordem = imagem.rodizio_ordem()`. Se `"rodizio_imagem" in self._ajustes_do_chamador` (o identity passa `[gerador]`), filtrar e ordenar por essa lista. Caso contrário, usar a ordem de `rodizio_ordem()` (que já lê o config).
- **Teste que prova:** `ias/test_rodizio_do_servico.py`. Com `carteiro.config` e `imagem._config` dublados para `{"rodizio_imagem": ["gemini","chatgpt"], "cota_pausa_h": 6}`, grava uma imagem do gemini respondida agora e cria um `Carteiro()` sem `rodizio_imagem` nos ajustes.
  - O pedido `livre` deve sair com `gerador == "chatgpt"`. Hoje sai gemini.
  - Trocando o dublê do config para `cota_pausa_h: 1` depois de criar o Carteiro, `uma_volta()` deve usar 1.
- **Origem:** `ias.md` #9 (mais o achado novo do rodízio).

### IAS-8 — `avisar_telegram` diz "entregue" quando o porteiro cala; o worker loga "NAO entregue" sem ter tentado  (baixo)
- **Onde:** `ias/carteiro.py:1446-1477` (`avisar_telegram`, `:1458-1459`), `:1323-1325` e `:1355-1356` (o log de `_anunciar*`).
- **Defeito:** `liberar() == False` (calado pelo porteiro) devolve `True` e o log diz "entregue". Quando a mensagem vai para a fila de pendentes, o log diz "NAO entregue" sem citar a fila. E os workers passam `avisar=lambda _: False`, por isso `auto_20261011.txt` tem 276 "aviso no Telegram NAO entregue" sem que tenha havido tentativa. Essas são as "dezenas por dia" que o `ias.md` não achou.
- **Conserto:**
  1. Uma função nova `avisar_telegram_situacao(texto, chave=None) -> str` que devolve `"entregue" | "calado" | "enfileirado" | "sem_destino"`. O `avisar_telegram` vira `return avisar_telegram_situacao(...) in ("entregue", "calado")`, para o supervisor e a assembleia não mudarem.
  2. Em `_anunciar*`, logar a situação textual quando `avisar` devolver `str`.
  3. Com `de_servico=False` (IAS-6), `_anunciar` não chama o Telegram nem loga.
- **Teste que prova:** em `ias/test_imagem.py`, um caso novo:
  - `avisar=lambda t: "calado"` faz o log conter "calado", não "entregue";
  - um `Carteiro()` de worker com `avisar=lambda t: False` não gera a linha "NAO entregue".

  Hoje as duas afirmações falham.
- **Origem:** `ias.md` #7.

### IAS-9 — O carteiro grava o modelo sem conferir se a troca pegou  (baixo)
- **Onde:** `ias/carteiro.py:233-236` (`SessaoReal.abrir_casa`), `:208-210` (`SessaoReal.modelo`), `:1251-1254` (`_um_turno`).
- **Defeito:** `modelo_confirmado` do cliente não é lido em `ias/`. A resposta fica gravada com o modelo fraco ou vazio, sem nota.
- **Conserto:**
  1. `SessaoReal.modelo_confirmado` como propriedade: `getattr(self.cliente, "modelo_confirmado", True)`.
  2. Em `_um_turno`, se `getattr(sessao, "modelo_confirmado", True) is False`, acrescentar ao `atualizar` a nota `nota=f"modelo não confirmado (saiu em {modelo or 'desconhecido'})"`.
  3. Se `mensagem.get("de") == "adrian"`, pôr a mesma frase no fim do texto do Telegram.
  4. Junto com HIS-11 (o carteiro de imagem não troca de modelo), que já está em `consertos/historias.md`.
- **Teste que prova:** em `ias/test_correio.py`, um caso novo com `SessaoDuble` e o atributo `modelo_confirmado = False`. Afirma que a mensagem respondida tem `nota` contendo "não confirmado". Hoje a nota fica vazia.
- **Origem:** `ias.md` #8.

### IAS-10 — `atualizar` grava o delta antes de conferir que a mensagem existe  (baixo)
- **Onde:** `ias/correio.py:266-279` (`atualizar`).
- **Defeito:** um id inexistente é acrescentado ao arquivo e só depois sobe `CorreioInvalido`. Reproduzido hoje: `ilegiveis` foi de 0 para 1.
- **Conserto:** dentro de `with _trancado(alvo)`, ler, dobrar (`_dobrar`) e conferir o id. Se não existir, levantar sem escrever. Se existir, escrever a linha ali mesmo (como faz o `reivindicar`).
- **Teste que prova:** em `ias/test_correio.py`, `atualizar("chatgpt", "deadbeef", nota="x")` levanta `CorreioInvalido`, o arquivo não contém `"deadbeef"` e `ilegiveis("chatgpt") == 0`. Hoje dá 1.
- **Origem:** `ias.md` #10.

### IAS-11 — A prova "o último turno é o seu pedido" compara só o prefixo fixo  (baixo)
- **Onde:** `ias/imagem.py:974-977` (`baixar_da_resposta`) e `:560-564` (`pedido_de_imagem`).
- **Defeito:** `_normal(prompt)[:60]` é sempre "crie uma imagem na proporção N:N. responda só com a imagem," (reproduzido hoje). Qualquer pedido de imagem nosso passa, inclusive na recuperação em conversa reaberta.
- **Conserto:** comparar também o fim, `fim = _normal(prompt)[-60:]`, e exigir `trecho in turno and fim in turno`. Se a interface encurtar o turno longo ("Mostrar mais"), cair para os 60 caracteres logo depois do prefixo fixo, isto é, o começo do texto da cena.
- **Teste que prova:** em `ias/test_imagem.py`, um cliente dublê cujo `imagens_da_resposta()` devolve `turno = pedido_de_imagem("um cachorro verde", "9:16")`, com `baixar_da_resposta(cliente, pedido_de_imagem("um gato azul", "9:16"))`. Deve levantar `SemProva`. Hoje passa.
- **Origem:** `ias.md` #11.

## Já consertados
- Nenhum. Não há commit em `ias/` depois de 10/10 nem ramo não mesclado mexendo na pasta.

## Alarmes falsos
- Nenhum. Uma correção pequena ao `ias.md` #9: o texto diz que `_entregar_livre` usa a lista velha "e" `rodizio_ordem()` na mesma volta. Na verdade só usa a lista do config, e `rodizio_ordem()` nunca roda ali (IAS-7). O efeito é pior do que o relatório descreve.

## Decisões que são do Adrian
- **Prévia do Gemini quando o original não baixa** (IAS-3): aceitar a imagem de metade da resolução (marcada "prévia"), ou recusar e gerar de novo, gastando cota e tempo? Em 12/10 isso foi mais da metade das imagens do Gemini (47 de 89).
