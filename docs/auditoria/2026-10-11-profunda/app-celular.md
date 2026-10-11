# Auditoria profunda do app do celular (PWA) — 11/10/2026

Só leitura: nenhum arquivo do projeto foi alterado. Nada foi publicado, apagado, pareado em conta real nem mandado a IA.

## Como foi provado

- `node --check` nos 13 `.js` de `remoto/app/`: todos passam (sem erro de sintaxe).
- Servidor de verdade (`remoto.api_http.criar_servidor`, `--local`, porta **8999**, `com_acoes=True`, sem publicar e sem zona de perigo) com **todo o estado em pasta temporária**: `LOCALAPPDATA`, `NEURAL_FIGHTS_RUNTIME_DIR`, `NF_IAS_PASTA`, `NF_COORDENADOR_PASTA`, `NF_DELEGADOS_PASTA`, `NF_ORQUESTRADOR_PASTA` apontando para `scratchpad\auditoria2\estado\`. Lançador: `scratchpad\auditoria2\lancar_servidor.py` (não usa o `main()` de propósito: o `main()` liga a sonda de uso, que chama o `claude.exe` a cada 10 min; o fixture `tela_isolada` de `test_app_tela.py` também sobe só o servidor). O estado real em `%LOCALAPPDATA%\neural-fights` e a porta 8931 não foram tocados; as leituras do pipeline (vídeos, fluxo, decisões do repositório) são só leitura.
- Chrome headless via patchright, `channel="chrome"`, viewport 390x844, `is_mobile=True`, `has_touch=True`, UA Android, `device_scale_factor=3`, capturando `console.error`, `pageerror`, respostas != 2xx e falhas de rede. Roteiros: `navegar.py` (todas as telas: 5 objetos da prateleira e todas as abas, inclusive Ateliê, Vila, Grimório, Sprites, Assembleia, Equipe, Coordenador (Painel e Conversa), Oficina, Conversa com cada IA e modos, Biblioteca (5 abas e um documento), Pergaminhos (4), Diário, Cinema (tocando um vídeo), Arena; diálogos dos comandos com campos (abertos e cancelados); escuro; deitado; voltar do Android; e depois **o servidor derrubado com a página aberta**), `navegar2.py` e `navegar3.py` (provas dirigidas). 98 capturas em `scratchpad\auditoria2\app\` (cada uma com o `.txt` do texto visível ao lado); logs em `navegar_log.json`, `navegar2_log.json`, `navegar3_log.json`.
- Varredura do texto visível de cada tela por `undefined`, `NaN`, `[object Object]`, `null`: **zero ocorrências** em 89 telas.
- `pageerror`: **zero** em todos os roteiros. `console.error`: só "Failed to load resource" (os 404 e as conexões recusadas depois da queda).
- Rotas: cada `fetch`/`api(...)` dos `.js` foi conferido contra o `_get`/`_post` de `api_http.py`: todas existem com o mesmo método (`/api/correio/livre` cabe em `CAIXAS_RE`; `/api/correio/<ia>/imagem` aceita `livre`; POST de texto só para as 4 de chat, e o JS nunca manda texto para as outras). Nenhuma rota chamada e inexistente.
- Token velho (aparelho esquecido): 3 pedidos em paralelo levam 401, o primeiro apaga o token e abre a tela Parear, os relógios param (0 pedidos nos 20 s seguintes), sem 429. Código errado: "codigo errado ou vencido". OK.

## Examinado

| Arquivo | Funções lidas | Observação |
| --- | --- | --- |
| `remoto/app/app.js` (939 linhas) | 42 funções + 31 listeners | inteiro |
| `remoto/app/vila.js` (1035) | 50 + 13 | inteiro |
| `remoto/app/orquestrador.js` (1243) | 58 + 25 | inteiro |
| `remoto/app/coordenador.js` (542) | 38 + 16 | inteiro |
| `remoto/app/conversa.js` (600) | 30 + 15 | inteiro |
| `remoto/app/decisoes.js` (561) | 21 + 14 | inteiro |
| `remoto/app/atelie_novo.js` (165 linhas longas) | 52 + 10 | inteiro |
| `remoto/app/oficina.js` (302) | 20 + 4 | inteiro |
| `remoto/app/comandos.js` (252) | 13 + 5 | inteiro |
| `remoto/app/biblioteca.js` (186) | 11 + 5 | inteiro |
| `remoto/app/equipe.js` (174) | 9 + 10 | inteiro |
| `remoto/app/assembleia.js` (68) | 3 + 2 | inteiro |
| `remoto/app/sw.js` (40) | 3 listeners | inteiro |
| `remoto/app/index.html` (798) | — | inteiro (ids, scripts, dialogs, nav) |
| `remoto/app/manifest.webmanifest`, `app.css` | — | só referências de arquivos |
| `remoto/api_http.py` | `_get`, `_post`, `_aparelho`, `_barrar_chute`, `_estatico`, `_arte_da_vila`, `_imagem_da_vila`, `_icone_do_objeto_do_atelie`, `criar_servidor`, `main`, tabela de rotas | as rotas que o JS chama |
| `remoto/test_app_tela.py` | fixture `tela_isolada`, `_esperar_tela` | para isolar o estado |

## Confirmados (do mais grave ao menos)

### 1. Com o servidor fora, a faixa "Não consegui falar com o PC" cobre a fileira de abas do objeto aberto e engole o toque
- **Onde:** `remoto/app/app.css:231` (`body.pareado .aviso { position: fixed; …; z-index: 21 }`) contra `app.css:308-309` (`.livro { position: fixed; inset: 0; z-index: 5 }`) e `app.css:639-640` (`.abas-objeto { z-index: 2 }`); `remoto/app/index.html:21-24` (`#aviso`); `remoto/app/app.js:165-199` (`conexao`).
- **O defeito:** a faixa `#aviso` é fixa, logo abaixo do cabeçalho, com `z-index` 21, e o objeto aberto (`.livro`) é fixo com `inset: 0` e `z-index` 5: a fileira `.abas-objeto` (Agora · Codex · Equipe · Coordenador etc.), que é a primeira coisa do objeto, fica exatamente embaixo da faixa. Enquanto o PC não responde, as abas do objeto aberto ficam escondidas atrás da faixa e o toque cai no `#aviso` (o botão "Tentar de novo" ou o texto), não na aba. Só "‹ Vila" e a prateleira continuam alcançáveis.
- **Quando acontece:** sempre que `conexao(false)` acende a faixa com um objeto aberto: Tailscale do celular desligado, PC sem o servidor (502), ou qualquer erro de API. É justamente a hora em que ele quer ir a "Coordenador" para ver o que caiu.
- **Prova:** captura `app\90b-agora-servidor-caiu.png` (a faixa cobre a fileira de abas, e o título "COORDENADOR" aparece cortado embaixo dela); o próprio patchright falhou ao tocar na aba: `navegar_log.json` → `excecao`: `<button class="acao" id="btn-tentar">Tentar de novo</button> from <div id="aviso" class="aviso" role="status"> subtree intercepts pointer events` (30 s de tentativas).
- **Conserto sugerido:** com `body.objeto-aberto`, a faixa fica abaixo da fileira de abas (ex.: `top` = altura do cabeçalho + da fileira) ou vira uma linha curta no próprio cabeçalho (o `#conexao` já diz "sem conexão desde…"), deixando as abas livres.

### 2. O service worker guarda para sempre cada versão das imagens da Vila: ~3,2 MB a mais no celular a cada arte salva no Ateliê
- **Onde:** `remoto/app/sw.js:21-40` (`fetch`: todo GET 200 da própria origem que não seja `/api/` ou `/v/` vai para o cache `painel-casca-v68`) + `remoto/app/vila.js:135-136, 230-231` (`/vilanova-atlas.png?escala=3&v=<versão>`, `/vilanova-<arranjo>.webp?v=<versão>&noite=<0|1>`).
- **O defeito:** o comentário do arquivo diz "Dados e vídeos nunca entram no cache", mas o manipulador de `fetch` guarda **qualquer** resposta 200 de GET fora de `/api/` e `/v/` — inclusive os fundos da Vila, o atlas, `/arte-vila/*` e as páginas `/p/<bilhete>` da Biblioteca. A versão da Vila muda a cada folha salva no Ateliê (08/10: "a versão da Vila inclui o mtime da folha"), e a URL muda com ela; a cópia antiga nunca sai (o `activate` só apaga caches de **outro nome**). Cada versão = retrato dia 0,95 MB + retrato noite 0,67 MB + atlas 0,67 MB (+ paisagem 0,90 MB se girou). Com o Adrian salvando dezenas de folhas por dia no Ateliê (5 de 1082 com arte hoje; a meta são as 1082), o cache cresce sem teto até a próxima troca de `CASCA`.
- **Quando acontece:** a cada carga do mundo com versão nova; no celular, quando o armazenamento aperta, o Android apaga o cache inteiro do site (e o app volta a precisar do PC para a casca).
- **Prova:** `sw.js:33-36` (condição `resp.status === 200 && resp.type === "basic"` sem lista de arquivos); tamanhos medidos no servidor de teste: `curl /vilanova-retrato.webp?v=x&noite=0` → 952 782 bytes; `noite=1` → 670 664; `/vilanova-paisagem.webp` → 904 754; `/vilanova-atlas.png?escala=3` → 671 594.
- **Conserto sugerido:** no `fetch`, só gravar no cache o que está em `ARQUIVOS` (`c.put` apenas se `ARQUIVOS` contém o caminho), e deixar o resto em rede pura (o `Cache-Control: max-age=86400` do servidor já cuida das imagens).

### 3. Cinema abre com um cartão vazio por 11 a 30+ s, sem "carregando…"
- **Onde:** `remoto/app/app.js:320-351` (`carregarVideos`) e `app.js:829` (`carregarAcoes().then(() => { if (tela === "videos") carregarVideos(); })`).
- **O defeito:** a tela Cinema não escreve nada enquanto `/api/acoes` e depois `/api/videos?n=60` não respondem; o cartão `<div class="cartao"><div id="videos">` fica em branco. O `/api/videos` frio (o servidor acabou de subir, ou primeira abertura do dia) leva segundos a dezenas de segundos porque varre os vídeos prontos em disco. Para o Adrian parece "não tem vídeo nenhum" ou "o app travou".
- **Quando acontece:** na primeira abertura do Cinema depois do servidor subir (a tarefa `NeuralFights_app_celular` o religa a cada queda) e sempre que o disco está lento.
- **Prova:** captura `app\40-videos.png` (cartão vazio 2 s depois de abrir; o `.txt` ao lado já tem a lista porque ela chegou logo depois do clique da câmera); `navegar2_log.json` notas: "cinema: lista apareceu depois de 11.4s; antes disso o cartão fica vazio" e, na primeira tentativa do mesmo roteiro, a lista não apareceu em 30 s (`Page.wait_for_function: Timeout 30000ms exceeded`). Captura `app\A0-cinema-5s.png` (5 s depois de abrir, ainda vazio).
- **Conserto sugerido:** em `mostrar()`/`carregarVideos`, escrever `carregando os vídeos…` em `#videos` antes do `await`, e chamar `carregarVideos` sem esperar o `/api/acoes` (o `publicarLigado` só decide se o botão Publicar aparece; dá para redesenhar quando `carregarAcoes` voltar).

### 4. Quatro 404 a cada carga do mundo da Vila (ícones dos objetos do Ateliê)
- **Onde:** `remoto/app/vila.js:155-167` (`vilaObjetosDoAtelie`) e `remoto/api_http.py:220-236` (`_icone_do_objeto_do_atelie`), `api_http.py:2241-2245`.
- **O defeito:** o app pede `/arte-vila/atelie/objetos/{agora,decidir,mandar,ver}.png?v=<versão>` toda vez que o mundo chega (primeira carga e cada vez que `retrato.versao` muda). Sem a peça no Ateliê (hoje não há `objetos/*.png` em `painel/flutuante/arte_vila`), são 4 respostas 404, 4 `console.error` e 4 linhas no `app_celular.txt` por carga — e a cada arte nova salva no Ateliê, de novo. Nada quebra (o emoji fica), mas o log do servidor e o console enchem de erro falso, o que atrapalha exatamente a leitura do log que a armadilha "script da casca que não chega some calado" manda fazer.
- **Quando acontece:** toda carga da Vila; na máquina real também (não existe `painel/flutuante/arte_vila/atelie/objetos/`).
- **Prova:** `navegar_log.json` → `respostas`: os 4 GET 404; `ls painel/flutuante/arte_vila/atelie/objetos` → "No such file or directory".
- **Conserto sugerido:** o `/api/vilanova?mundo=1` dizer quais objetos têm arte (`mundo.objetos_do_atelie: [...]`) e o JS só pedir esses; ou o servidor responder 204 sem logar.

### 5. "O que falta" do Ateliê deixa a busca escondida e o caminho velho
- **Onde:** `remoto/app/atelie_novo.js:98` (`animFaltam`) e `:35-36` (`animDesenhar`: `anim-busca-caixa` oculta quando `AnimAtelie.estado` existe; `anim-caminho` vem de grupo/peça/estado).
- **O defeito:** `animFaltam` redesenha a lista com o que falta, mas não limpa `AnimAtelie.peca`/`estado` nem chama `animDesenhar`: o cabeçalho continua "Lutador › Assassino (Crítico) › Base" (a peça que ele estava vendo) e a caixa "Buscar peça" fica oculta. A lista mostra 1077 itens ("5 de 1082 com arte") sem filtro possível e com o caminho mentindo.
- **Quando acontece:** tocar "O que falta" com um estado aberto.
- **Prova:** `navegar_log.json` passo `atelie-busca-oculta-depois-de-faltam Lutador › Assassino (Crítico) › Base`; captura `app\51g-atelie-faltam.png` e `.txt` (caminho "Lutador › Assassino (Crítico) › Base" acima de "O que falta desenhar"); o patchright não conseguiu preencher `#anim-busca` ("element is not visible").
- **Conserto sugerido:** em `animFaltam`, zerar `peca`/`estado`/`animacao`, mostrar a busca e escrever "O que falta desenhar" em `#anim-caminho` (e filtrar a lista pela busca).

### 6. `atelie_novo.js` define quatro funções duas vezes; a primeira versão é código morto que diverge da segunda
- **Onde:** `remoto/app/atelie_novo.js:60-66` vs `:84-97` (`animMiniatura`, `animAnimarMiniatura`); `:68-72` vs `:121-125` (`animFolha`); `:73-77` vs `:130` (`animPrevia`).
- **O defeito:** com `function` em escopo de script, a segunda declaração vence. As primeiras ficam no arquivo como se valessem (a primeira `animMiniatura` mostra "◌ usa a de X" e a vigente mostra a miniatura herdada; a primeira `animPrevia` desenha em `translate(160,90)` sem referência, a vigente desenha com `animReferencia`). Quem ler o arquivo conserta a função errada; e a `animAnimarMiniatura` morta pede `/folha` da peça filha (a que a vigente evita de propósito, "nunca se pede uma folha inexistente da filha").
- **Quando acontece:** manutenção; hoje o comportamento é o da segunda cópia.
- **Prova:** `grep -n "^function animMiniatura\|^async function animAnimarMiniatura\|^function animFolha\|^function animPrevia" remoto/app/atelie_novo.js` → linhas 60, 64, 68, 73, 84, 89, 121, 130. `node --check` passa (não é erro de sintaxe).
- **Conserto sugerido:** apagar as quatro primeiras cópias.

### 7. Prévia do Godot continua perguntando ao PC a cada 3 s depois que ele sai do Ateliê; `atelieParar` é vazio
- **Onde:** `remoto/app/atelie_novo.js:141-150` (`consultar` com `setTimeout(..., 3000)` sem guarda de tela) e `:158` (`function atelieParar() {}`); `:131` (`animTocar` com `requestAnimationFrame` eterno desde a carga).
- **O defeito:** depois de "Ver no Godot", o laço `consultar` só para quando o trabalho sai de `rodando`; trocar de tela ou voltar à Vila não o interrompe, e `atelieParar()` (chamado por `mostrar()`) não cancela nada. Se o Godot demorar (~1 min) e ele fechar o app no meio, ao voltar o `setTimeout` está perdido e o resultado nunca aparece. O `animTocar` roda a cada quadro em todas as telas (barato: sai cedo quando não há quadros, mas é um rAF permanente).
- **Quando acontece:** toda prévia do Godot; o rAF, sempre.
- **Prova:** leitura das linhas citadas; `atelieParar` é literalmente `{}`.
- **Conserto sugerido:** guardar o `setTimeout` em `AnimAtelie.previa` e cancelá-lo em `atelieParar`; ao reabrir, consultar o último `trabalho.id`.

### 8. Parear com o PC fora mostra o erro cru do navegador ("Failed to fetch")
- **Onde:** `remoto/app/app.js:593-609` (`btn-parear` usa `fetch` direto, não `api()`; `msg.textContent = err.message`).
- **O defeito:** sem rede/Tailscale, a mensagem é "Failed to fetch"; com o `tailscale serve` respondendo 502 em HTML, `resp.json()` lança `SyntaxError: Unexpected token '<'…`. É a única tela que um celular novo vê, e o texto não diz o que fazer.
- **Quando acontece:** parear com o servidor parado (depois de reiniciar o PC, §4 do doc da sessão) ou com o Tailscale do celular desligado.
- **Prova:** `navegar2_log.json` notas: `parear sem servidor, mensagem: Failed to fetch`; captura `app\A5b-parear-sem-servidor-msg.png`.
- **Conserto sugerido:** tratar `TypeError` do fetch como "Não consegui falar com o PC. Confira o Tailscale neste celular." e `!resp.ok` sem JSON como "O PC respondeu com erro N".

### 9. Títulos longos quebram o cabeçalho em duas linhas (Conversa "Criar · Qualquer um livre"; "Agora · Coordenador" com "sem conexão desde HH:MM")
- **Onde:** `remoto/app/conversa.js:206-207` (escreve `#titulo` com `Criar · ${d.rotulo}`), `remoto/app/app.js:762`, `app.css` (`header h1`).
- **O defeito:** o `h1` e o `#conexao` dividem a largura; com "Criar · Qualquer um livre" ou "sem conexão desde 15:08", o título vai para duas linhas e o cabeçalho cresce, empurrando a fileira de chips/abas (e, no caso 1, a faixa `#aviso` desce junto).
- **Quando acontece:** aba IAs com "Livre" escolhido; qualquer objeto com aba quando a conexão cai.
- **Prova:** capturas `app\31b-conversa-livre.png` (título em duas linhas) e `app\90b-agora-servidor-caiu.png` ("Agora ·" / "Coordenador").
- **Conserto sugerido:** `h1` com `white-space: nowrap; overflow: hidden; text-overflow: ellipsis` e um rótulo curto para "livre" ("Rodízio").

### 10. Diálogo de comando deixa "Continuar" ativo com a lista ainda em "carregando…"
- **Onde:** `remoto/app/comandos.js:100-103, 133-146` (`comandosPreencherIds` busca `/api/videos?n=80`, que é lento, e o botão `#btn-campos-ok` não espera).
- **O defeito:** o `select` nasce com a opção "carregando…" (`value=""`) e o Continuar já está habilitado; tocando, o pedido sai com `id: ""`. O servidor segura (409 "falta preencher: Geração"), então não há dano, mas é um toque perdido e um erro vermelho por um botão que não devia estar vivo. Além disso cada abertura do diálogo refaz a varredura cara de `/api/videos?n=80`.
- **Quando acontece:** "Re-renderizar build", "Enfileirar identidade", "Terminar história", etc., logo depois de abrir.
- **Prova:** `navegar2_log.json`: `rerender: opção visível no instante do Continuar = 'carregando…'`; `toast depois do Continuar: falta preencher: Geração`; resposta `409 /api/acao`; captura `app\30b-dialogo-0-rerender.png`.
- **Conserto sugerido:** desabilitar `#btn-campos-ok` até os `select` de build/história terem opções; reaproveitar a lista já carregada em `carregarVideos`.

### 11. A prova de tela (`test_app_tela.py`) ainda espera o Ateliê antigo (`#modular-slots`), removido em 08/10
- **Onde:** `remoto/test_app_tela.py:139-140` (`if nome == "atelie": page.locator("#modular-slots button").first.wait_for(state="visible")`) e `:160` (chamado para toda tela de `TELAS`, inclusive `"atelie"`).
- **O defeito:** `#modular-slots` era do Ateliê antigo, removido em 08/10 ("Atelie antigo removido"). A prova de tela de navegador (`NF_TESTE_NAVEGADOR=1`) espera por um elemento que não existe mais e estoura o prazo na tela Ateliê, então a suíte de tela nunca chega a conferir o Ateliê novo (e falha, ou é pulada).
- **Quando acontece:** toda rodada com `NF_TESTE_NAVEGADOR=1`.
- **Prova:** `grep -n "modular-slots" remoto/app/*.js remoto/app/index.html` → nada; só `remoto/test_app_tela.py:140`.
- **Conserto sugerido:** esperar `#anim-grupos button` (o que o Ateliê novo desenha primeiro).

### 12. `sw.js`: a lista `ARQUIVOS` não tem `icones/favicon-16.png` nem `favicon.ico`, que o `index.html` pede
- **Onde:** `remoto/app/sw.js:4-8`; `remoto/app/index.html:10-11`.
- **O defeito:** offline, o pedido de `favicon-16.png` cai em `fetch` → rejeita → `caches.match` → `undefined` → `respondWith(undefined)` = erro de rede nesse recurso (um `console.error` por abertura sem rede). Cosmético; mas a regra do doc é "a lista ARQUIVOS cobre todo arquivo que o index carrega", e não cobre.
- **Prova:** diff entre `ARQUIVOS` e os `href` de `index.html` (`favicon-16.png` só no index); todos os 12 `.js`, `app.css`, manifest e os 4 ícones grandes estão na lista.
- **Conserto sugerido:** acrescentar os dois à `ARQUIVOS`, ou tirar o `<link>` do 16 px (o 32 cobre).

## Não confirmados (lidos, sem prova de execução; ficam como observação)

- **`decisoes.js:553-561` + `:402-411`:** se o nó aberto sumir do Grimório (removido no PC), `decisoesReler` acende "Esta decisão mudou"; tocar "Ver o que vale" chama `decisoesAbrir(Decisoes.aberta)` e `itens[id]` é `undefined` → `TypeError` em `item.projeto` (erro não tratado no clique). Não foi possível provar sem apagar um nó do repositório real.
- **`app.js:466-479` (`tocar`)**: usa `alert()` para o erro de abrir vídeo; o `error` do `<video>` (bilhete vencido, servidor fora) chama `tocar` de novo e, se o `api()` falhar, o `alert` sobe mesmo com ele em outra tela (o player fica vivo em `#tela-videos` escondida). Na prova, com o vídeo **pausado** e o servidor caindo, nenhum `alert` apareceu (`navegar2_log.json`: `dialogos: []`); fica como risco só com o vídeo tocando.
- **`orquestrador.js:984-1014` (`orqCarregarFluxo`)**: lê `f.torneio.prontos`, `f.arena.lutas`, `f.etapas.map` e `g.etapas[e.id]` sem guarda; o `painel_dados.py:346-347` sempre manda `torneio` e `arena`, então hoje não quebra. Se o fluxo vier sem um deles, a mensagem para o Adrian seria o `TypeError` em inglês ("fluxo: Cannot read properties of undefined…").
- **`app.js:329-345` (`carregarVideos`)**: `v.pendencias.length` e `(v.bytes/1048576).toFixed(1)` confiam no servidor; `painel_dados.py:182-185` sempre manda os dois. Sem `bytes`, apareceria "NaN MB".
- **`sw.js:38`:** resposta não-200 cai na cópia guardada; para `/p/<bilhete>` (páginas da Biblioteca) isso serve uma página de bilhete **vencido** a partir do cache se a URL for reaberta (o bilhete é único por abertura, então na prática só pelo histórico do navegador).
- **`comandos.js:117-129`, `orquestrador.js:125-137, 599-616`, `app.js:386-413`:** os diálogos registram `close` com `{once: true}` a cada abertura; se um segundo `showModal()` acontecer com o diálogo já aberto (dois toques rápidos em botões diferentes), o `showModal` lança `InvalidStateError` e o `avisar` mostra a mensagem em inglês. Não reproduzido.
- **`conversa.js:369-374`:** o `POST /api/correio/<ia>/visto` sai a cada releitura (6 s) enquanto houver resposta não vista e a aba estiver visível — marca como visto mesmo com a tela coberta por outro objeto (a conversa para de ler ao trocar de tela, então na prática só enquanto ela está aberta). OK como está.
- **Vila "somando o placar…"** fica no céu enquanto `panorama.resumo()` roda (~159 s na primeira conta, doc §4): no servidor de teste ficou assim o tempo todo; na máquina real some depois do cálculo. Não é defeito do JS.

## O que está limpo (conferido)

- Nenhuma rota chamada pelo JS falta no servidor; nenhum nome/método divergente.
- Nenhum `setInterval` acumula: cada `*Mostrar` limpa o anterior (`clearInterval` antes de `setInterval`) e `mostrar()` chama todos os `*Parar` antes de abrir a tela nova; `vilaMostrar` reusa os relógios (`if (!Vila.relogioRetrato)`); `comandos`/`oficina`/`conversa`/`coordenador`/`equipe`/`decisoes` idem.
- Nenhum listener é registrado de novo a cada render sobre o mesmo elemento: os botões são recriados (`replaceChildren`) e os fixos (`$("btn-…")`) ligam uma vez no fim do arquivo; os dois `onclick` de `orq-menos/mais/teto/forca/modelo-*` são atribuição (sobrescrevem), não acúmulo.
- Toque duplo em ação que sai para o mundo: `agir` passa pelo `<dialog>` modal (um por vez); `coordEnviar`, `orqEnviar` (`Orq.voando`), `pedidoRapido`, `coordFalar`, `conversaEnviar/Criar` (`Conversa.enviando`), `coordPassar`, `pedidoEnviarResposta` e `claudeTrocar` têm trava de "em voo"; `spritesCartao` Descartar e `coordDoisToques` exigem dois toques.
- Estado marcado antes do servidor confirmar: só o esperado (fila "pendente" listrada, `Orq.alvoLocal` com envio adiado de 700 ms, pedidos do coordenador em `Coord.pedidos` até o evento confirmar) e todos voltam atrás no `catch`.
- `localStorage`/`sessionStorage`: lidos sem `try/catch`, mas só com chaves próprias e strings; `JSON.parse(localStorage.getItem(ULTIMO) || "null")` é a única análise e está dentro do `catch` de `carregarAgora`.
- 401: `api()` apaga o token e volta à tela Parear; provado com token velho (3 × 401, zero 429, zero pedido depois).
- Casca nova (`X-Casca` ≠ `meta casca`): recarrega só na Vila sem diálogo aberto, uma vez por versão (`sessionStorage`); fora disso a faixa pede o toque.
- Módulo que não chega: `load` confere as 11 funções-sentinela e recarrega uma vez; depois, a faixa nomeia o arquivo.
- Servidor caindo com a página aberta: nenhuma tela ficou em branco; Vila congela o último retrato e mostra a faixa; Agora/Coordenador/Mandar/Decidir/Ver mantêm o último desenho (Coordenador diz "FORA DO AR"); Ateliê escreve "Falhou: sem rede"; nenhum `pageerror`.
- Deitado (844x390): prateleira vira coluna, placar sobe ao cabeçalho, sem corte (`app\80-vila-deitada.png`).
- Escuro: Agora, Vila e Conversa do coordenador legíveis (`app\70*.png`).

## Decisões do Adrian conferidas contra o código

- "Só o app publica pelo celular", "destino padrão YouTube e TikTok", "dois passos": o botão Publicar só aparece com `publicarLigado` e `canal === "builds"` e passa por `perguntar(destinos)` + `/api/acao` + `/api/acao/confirmar` com código de 60 s (`app.js:329-332, 444-450, 415-442`). Não foi tocado.
- "Mensagem para uma IA pelo app: direto": `conversaEnviar` manda sem confirmação, como decidido. Não foi tocado.
- Nada aqui pede decisão nova dele: os consertos sugeridos são de tela, cache e log.
