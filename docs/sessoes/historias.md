# Histórias

<!-- decisoes:inicio -->
## Decisões do Adrian (gerado — não edite à mão)

Fonte: `decisoes/historias/` e `decisoes/geral/`. **Decisão vigente do Adrian manda.** Para mudar uma, ele usa a tela Decisões do app.

**Geral**
- ✅ **Objetivo das próximas semanas** — Estabilizar o que existe (27/09/2026) `objetivo-das-semanas`
- ✅ **Modo de trabalho dos agentes** — Vários projetos em paralelo (29/09/2026) · “29/09 09:09, no chat: paralelo, até 2 agentes — nas palavras dele: Adrian pediu a fila em cards enquanto o prédio do Grok roda” `modo-de-trabalho`
- ✅ **Teto de uso do Claude** — Passou de 50%, para tudo; força total 20 min antes de renovar (29/09/2026) · “29/09 07:26, pela Mesa de comando: passou de 50% da sessão, para tudo” `teto-de-uso`
- ✅ **Força total antes de renovar: ainda vale?** — Ligada, 20 min antes de renovar (29/09/2026) · “29/09 07:27, pela Mesa de comando: força total 20 min antes de renovar” `forca-total-ainda-vale`
- ✅ **Capacidade mudada pelo app vira regra?** — Substitui: o que eu mudo no app vira a regra (28/09/2026) `capacidade-pelo-app`
- ✅ **Força total ligada pela Mesa: por quanto tempo?** — Até eu desligar (28/09/2026) `forca-total-pela-mesa`
- ✅ **Teto também no limite semanal?** — Outro (comente) (28/09/2026) · “Controlo isso com a mesa” `teto-da-semana`
- ✅ **Limpeza do disco (C: com 9 GB livres)** — Só o seguro (~1,2 GB) (29/09/2026) `limpeza-do-disco`
- ✅ **E: com 17 GB livres — o cache do Google Drive (186 GB)** — Abrir o Google Drive e deixar ele terminar e limpar sozinho (recomendado primeiro) (29/09/2026) `limpeza-do-disco-e`
- ✅ **Grok: por onde entra na roda?** — grok.com com a sua conta X (gratuito; você loga uma vez) (29/09/2026) `ias-grok-acesso`
- ✅ **Quando você fala com uma IA e a pipeline precisa da mesma conta** — Você: a pipeline espera a sua conversa terminar (29/09/2026) `ias-prioridade-conversa`
- ✅ **Cada IA tem UM chat de longa duração ou um chat novo por assunto?** — Um chat 'casa' por IA, com resumo periódico (29/09/2026) `ias-chat-persistente`
- ✅ **Fichas das IAs (fase 1): li?** — Li; seguir para a fase 2 (falar com cada uma pelo app) (29/09/2026) `ias-fichas-lidas`

**Histórias**
- ✅ **Vídeo reprovado ou não assistido** — Fica retido; só sai se o horário fosse ficar vazio (27/09/2026) `reprovado-ou-nao-assistido`
- ✅ **Gemini pago** — Não: fica na gratuita (28/09/2026) `gemini-pago`
- ✅ **Reprovados que já estão no ar** — Manter no ar (28/09/2026) `reprovados-no-ar`
- ✅ **Rodada de histórias travada há 10 h segurando a trava** — Matar o PID 7300 agora e deixar a próxima rodada retomar a 00038 (29/09/2026) `rodada-travada-7300`

<!-- decisoes:fim -->

Documento de passagem — escrito em 27/09/2026 pela sessão dona desta parte.

Esta parte **cria**: roteiro num LLM, uma imagem por cena no PicassoIA, narração,
um mp4 por parte, uma IA assiste, e o vídeo aprovado fica no estoque. **Não
publica** — quem publica é `ferramentas/postar.py` (`publicacao.md`).

Mapa (sob `E:\projetos\historias\`): `contos/pipeline/` tem `agenda.py` (1186 linhas, o
cérebro: rodada automática, freios, escolha do tipo), `controller.py` (a pipeline),
`reparo.py`/`conserto_de_cena.py`, `conferir.py` e `tarefas.py` (tarefas
`Historias_auto_HH` + `auto.cmd`, gerado e gitignorado); `contos/llm/` (`cliente.py`,
`seletores.py`, `papeis.py`, `probe.py`); `contos/roteiro/` (`serie.py`, 1062 linhas:
bíblia, partes, modo livre, tipos; `gerar.py`; `roteiro.py`, o parser); `contos/imagens/`
(`worker.py`, `composicao.py`, `reescritor.py`); `contos/publicar/` (`catalogo.py`,
`qualidade.py`, `parecer.py`, `tipos.py`, `serie.py`); e `config/` (`roteiro.json`, 32 KB
com moldes, tipos, ganchos e linguagem, mais `agenda.json`, `llm.json`, `imagens.json`,
`render.json`, `publicacao.json`).

## 1. Como nasce uma história

O Agendador chama `main.py auto` (sem bandeira) nos horários de `config/agenda.json`
(`1,2,3,4,5` e `07:02, 10:02, 12:32, 16:02, 18:22, 21:02, 22:02, 23:02, 00:02`). A
rodada nunca levanta exceção: devolve dicionário, escreve em
`outputs/_logs/auto_<data>.txt`, e o `main.py` decide o código de saída.

1. **Trava** `historias__auto` com `esperar=0.0` — disparo que acha rodada em andamento
   sai na hora (esperar empurraria a fila para o disparo seguinte). A **pausa da Vila**
   (`identity/controle`) também segura a rodada.
2. **Janela pesada 01h–06h**. Fora dela (`modo_dia`) a rodada só faz o que evita ficar
   sem vídeo: conserta barrados e cria se o estoque estiver magro. Métrica e revisão do
   estoque são só de madrugada.
3. **Termina incompleta antes de criar** (`incompletas()`): parte sem texto é reescrita,
   imagem que falta é gerada, parte sem vídeo é renderizada.
4. **Roteiro**, num chat só: bíblia (premissa, elenco, descrição física do protagonista
   em inglês, alavancas) → cada parte → **revisão por parte** (revisão com menos cenas
   que a original é descartada). Depois **imagens** (`cenas/pNN_cena_NN.png`, com prova
   de origem) e **vídeo** (a voz é medida **antes** do plano: a cena espera a fala; um
   mp4 + capa por parte).
5. **Vistoria e parecer**: `qualidade.liberado()` mede o arquivo, `parecer` manda uma IA
   assistir. Barrado vai ao `reparo`; aprovado é estoque. O que só a folha de contato
   aprovou fica gravado como **`nao_assistido`**, nunca como aprovado (ver Contratos).

Medido em `outputs/_logs/auto_20260927.txt` — `00035` (babaca, 3 partes, 42 cenas):
roteiro 3 min 36 s, imagens 26 min 23 s (~38 s/cena), render 16 min 44 s, **total
46 min 43 s**. `00036` (favela, 6 partes, 84 cenas): roteiro 4 min 27 s, imagens
43 min 43 s, render 34 min 27 s (~5 min 45 s/parte), **total 1 h 22 min**. Parecer:
~1 min por parte. `minutos_por_historia: 150` é a estimativa conservadora que decide
se outra história cabe antes de a janela fechar.

## 2. Quem escreve e quem julga

Em **`config/llm.json`** → `papeis`; quem lê é `contos/llm/papeis.py`. Cada lista é
**ordem de queda**, e a queda fica no diário e no `roteiro.json` (`quedas`, e
`provedor` por parte).

```
roteiro:       deepseek -> chatgpt -> gemini   (bíblia, partes, revisão)
qualidade:     chatgpt  -> gemini              (parecer da folha, conserto de cena)
video:         gemini                          (só o Gemini assiste mp4)
imagem_prompt: chatgpt                         (reescreve prompt recusado)
```

O Gemini é o último no roteiro **porque é o único que assiste vídeo**: prendê-lo numa
geração de horas tiraria o juiz do ar. Conta ocupada passa ao próximo livre, sem
esperar. O `provedor: gemini` de `agenda.json` é só o fallback de
`agenda.provedores_do_roteiro()` quando `llm.json` falta. Desde 29/09/2026 `seletores.py`
também tem o **Grok** (`grok.com`, perfil `grok__principal`, login pessoal do Adrian) — ele
**não** está em nenhum papel: entrou pela Vila das IAs (`ias/`, `docs/ias/fichas.md`), que
mede a ficha de capacidades de cada IA (o que gera, cota, textos de erro) sem mexer na
pipeline. O ChatGPT não assiste vídeo
nesta máquina (conta free: o mp4 entra como "Arquivo" opaco) — cai na folha de
contato, um quadro por cena. **A conta do Gemini também é free** ("Faça upgrade para o
Google AI Pro" na barra lateral).

## 3. Os três tipos, o modo livre e os dois rodízios

`config/roteiro.json` → `tipos` (decisão dele, 17/09/2026): **favela** (novela caricata da
quebrada, narrador de fora, sem crime/arma/droga/polícia; molde `quebrada`), **normal**
(relato em 1ª pessoa de alguém comum; moldes `reddit`, `confissao`, `vinganca`) e
**babaca** (post do Reddit "Eu sou o babaca?", pedindo que quem assiste julgue; molde
`babaca`). Favela e normal usam o `partes` da agenda (6); o babaca tem `partes: [2, 6]` e
o número é **sorteado** por história (`serie.partes_do_tipo()`). Os três estão em
**`modo: livre`**: a IA recebe só o assunto, o tamanho, o guia de linguagem, a
continuidade das imagens e o formato — molde, alavancas, narrador e abertura/fechamento
são dela (`serie.prompt_biblia_livre`). O rodízio de molde ainda existe e acontece
**dentro** do tipo, pelo menos usado.

- **Quem nasce a seguir**: `agenda.tipo_mais_magro()` — o tipo com menos partes aprovadas
  na fila; empate pela ordem do config.
- **Rodízio na saída**: `contos/publicar/tipos.py` (função pura) intercala os tipos pelo
  que está há mais tempo sem publicar, preservando a ordem das partes.
- **Gatilho de séries**: `agenda.falta_serie()`. 10 horários ÷ teto de 2 partes da mesma
  história por dia = `series_minimas = 5`. Desde 28/09 ele conta as séries **elegíveis**
  (`agenda.series_elegiveis`): uma série só entrega se a **próxima** parte dela (a menor que
  ainda não foi ao ar, em qualquer destino — `partes_publicadas`) está aprovada, e entrega
  no máximo 2 por dia, as que vêm em seguida aprovadas. Com o teto de partes cheio (20) e a
  **capacidade do dia** abaixo dos 10 horários, a criação é liberada até um **teto duro**
  de 26. Até 27/09 contava séries **distintas**: com 6 séries no estoque o `postar.py`
  avisou 150 vezes num dia "só 4 série(s) elegível(is)" — série com a próxima parte
  barrada tem partes na fila e não entrega nenhuma.

## 4. Armadilhas medidas (não descubra de novo)

- **Resposta lida pela posição**: `.nth(total-1)` pegava a resposta *anterior* em chat
  com vários turnos. `cliente._resposta_atual()` faz scroll até o fim e usa âncora — a
  resposta é a que vem **depois** do último turno do usuário.
- **Botão de parar que casava com "Comparar"**: `aria-label*='Parar'` pegava o
  histórico da barra lateral ("Fixar **Comparar** defeitos…") e o parecer ficou 8 min
  com APROVADO na tela e o cliente dizendo "escrevendo". O rótulo tem de **começar**
  com a palavra (`^='Parar'`), em `seletores.py`.
- **Veredito em inglês**: um parecer veio "REPROVED cena 1: …" e virou "sem parecer" —
  o veto se perdia. `parecer.PALAVRAS_DE_REPROVACAO`/`_APROVACAO` aceitam as duas.
- **Recusa enlatada do Gemini** ("Sou uma IA com base em texto, e isso está além das
  minhas capacidades", "Não fui programado para fazer isso", "Fui criado apenas para
  processar e gerar texto"…): uma frase sorteada de uma lista fixa, no lugar da resposta.
  Nos logs, 18 em 169 revisões de vídeo de 13 a 27/09, e **5 de 9** na madrugada de 27/09.
  **Não é o upload** (o histórico do Gemini mostra o mp4 com a duração no balão da
  pergunta), **não é o texto do pedido de parecer** (o pedido da `00034 p04` **sem** o
  vídeo não foi recusado — o Pro ficou 5 min pensando, 1 tentativa —, e "PEDIDO DE TEXTO"
  na 1ª linha não mudou nada: por isso **não** entrou) e **não é o modelo** (recusou no
  "Pro" e no "3.1 Pro Raciocínio avançado"). No parecer é o **vídeo, do lado do Google**,
  com taxa **por vídeo** e em rajadas: `00034 p04` teve 1 de 7 tentativas assistidas (5
  frases + um "Algo deu errado (1155)" que devolveu a pergunta à caixa, e só às 05:25 de
  28/09 foi assistida), `00036 p01` 0 de 2, `00034 p02` 1 de 4 — e `00034 p01` 6 de 7,
  `00036 p02`–`p06` 5 de 5. O fundo de
  maquiagem das recusadas não tem nada que as assistidas não tenham (quadros comparados em
  28/09). A frase também aparece sem anexo, em pedido que fala de imagem (a reescrita de
  prompt das 02:18 de 27/09). O que se controla daqui: `parecer.RecusaDoModelo`
  (subclasse de `SemParecer`, detectada por `llm.texto.e_recusa_enlatada`), **uma**
  pergunta de novo num chat novo (`REPETIR_RECUSA = 1`; na hora recuperou só 1 de 5 em
  28/09), e a revisão da madrugada pergunta de novo, **no fim da passada e só ao
  Gemini**, o que a folha aprovou (`nao_assistido`), e devolve ao Gemini o
  `nao_assistido` de noites anteriores — foi assim que a `00034 p02` (APROVADO, 01:44) e a
  `00034 p04` (REPROVADO, 05:25, na rodada seguinte) foram assistidas em 28/09. A reescrita
  do reparo pergunta de novo num chat novo e,
  recusada duas vezes, vira falha do provedor em vez de "nenhum motivo tem conserto".
- **Parede de planos do PicassoIA**: o diálogo de assinatura cobre a página e engole o
  clique, mesmo em conta com plano. `worker.gerar()` fecha o navegador e **reabre o perfil
  uma vez**; só se voltar morre como `NaoRodou` (a história fica pendente e a próxima
  rodada tenta). Antes de alarmar "acabou o grátis", reabrir o perfil e tentar gerar.
- **Colagem / díptico**: `composicao.e_colagem()` acha calhas atravessando a imagem, e
  colagem **se refaz com o mesmo prompt** (quem errou foi o desenho). Não pega colagem sem
  calha, e moldura não é colagem (conserta sem gerar de novo).
- **Imagem faltando não renderiza**: antes só a agenda pulava a parte incompleta; hoje
  `main.py video`, `tudo()` e o botão do painel também.
- **Trecho preto na vistoria**: `qualidade.trechos_pretos()` — área ≥80 % escura por >0,5 s
  é **erro**. Os limiares são medidos: com 40 %, cena noturna reprovava.
- **A vistoria é cara e roda muitas vezes**: `aprovados_no_estoque()` levou 107 s para 19
  vídeos (28/09, 02:55, máquina ocupada): 51 s de decode do áudio, 35 s do detector de
  colagem nas 266 imagens, 17 s de ffprobe, 4 s do resto — e a mesma passada roda 2 a 5
  vezes por rodada (diário de 27/09: 71 a 400 s de log parado por rodada; às 12:32 foram
  24 min, porque 6 mp4 novos pagaram o trecho preto). Desde 28/09 as três medidas ficam em
  `outputs/_vistoria_medidas.json` (como `_vistoria_pretos.json`): chave = caminho + mtime
  + tamanho + versão do que se mede; arquivo refeito é medido de novo, e o **laudo** não é
  guardado (limites, roteiro e parecer valem na hora). Medido às 08:09 de 28/09, em dois
  processos seguidos: **116,2 s → 2,3 s**, o mesmo resultado (17 aprovadas, 7 barradas).
  Teste que vistoria cena **de verdade** aponta `qualidade._outputs` para a pasta dele: o
  memo de produção só recebe o que a produção mediu.
- **Prova de origem**: a conta do PicassoIA é compartilhada com outras pessoas, então o
  `worker` só baixa imagem cujo card comprova que veio do **nosso** prompt. Sem prova nada
  é baixado, a cena fica pendente e a vistoria barra a parte.

## 5. As leis (decisões dele — não negocie sozinho)

1. **A ordem das partes é sagrada**: parte N não sai antes da N-1.
2. **Imagem sem prova de origem não vai ao ar.** Nunca.
3. **Não ficar sem vídeo** é a prioridade: daí a rodada de dia, e daí o estoque contar
   só o que a vistoria aprova.
4. **Tom das copys**: limpo e convidativo, CAPS só no título, um emoji no máximo, e a
   legenda nunca repete número que a tela já mostra. Nada de "narrado por IA" (quebra a
   imersão); a linha "os personagens são invenção minha" fica. Texto em
   `config/publicacao.json`.
5. **Linguagem que passa na plataforma**: `config/roteiro.json` → `linguagem` (9 regras
   de eufemismo). A tensão mora no que a pessoa **sente**, não no que a câmera mostra —
   é o que passa no filtro do PicassoIA e não derruba a monetização.

## 6. Estado de hoje (28/09/2026, ~08h, medido)

- **Estoque** (08:09): **17 aprovadas, 7 barradas**; teto 20, teto duro 26 → a
  criação **segue liberada** pelo freio de partes. **6 séries** com parte aprovada, **5
  elegíveis**, capacidade do dia **9 de 10** (`00034` tem p02, p05 e p06 aprovadas e a p01
  reprovada: entrega 0; `00032` só tem a p06: entrega 1). Por tipo: **favela 11, normal
  3, babaca 3** → o próximo a nascer é **normal** (empate com babaca, a ordem do config
  decide).
- **A rodada das 07:02 morreu calada às 07:21** (PID 11632): último turno do DeepSeek
  aberto às 07:21:12, nenhum erro no log nem no diário, nenhum `main.py` vivo às 07:29. A
  `historia_00038` ficou com as partes 1–2 no `roteiro.json` (a 3ª só em
  `conversa/parte_03.txt`): a próxima rodada a retoma pelo caminho `partes_sem_texto`
  (`_retomar_texto`). Quem matou o processo **não foi apurado**.
- 36 pastas `historia_*` (35 com mp4), 190 mp4 de celular, ledger com 328 linhas (162
  YouTube / 166 TikTok). Criada na madrugada: `00037` (favela, 6; 18 problemas às 05:15,
  terminada às 05:54).
- **Aviso de variedade** do `postar.py` ("só N série(s) elegível(is) hoje, e o dia
  precisa de 5"): 162 no `outputs/postar.txt`, e **148 deles com série(s) já no teto do
  dia** — a linha de cima diz "a historia ja saiu 2x hoje". O aviso compara as séries que
  **sobram** com as 5 que o dia **inteiro** precisa; à tarde ele dispara com 6 séries no
  estoque. Só 14 foram de manhã, sem série nenhuma no teto. O aviso é do `postar.py`
  (publicação); o gatilho de criação desta parte passou a contar séries elegíveis (§3).
- **Os 5 aprovados sem ninguém assistir** (27/09, 01:30–01:43: o Gemini recusou, a folha
  do ChatGPT aprovou em 8 caracteres), marcados `nao_assistido` em 28/09 00:04 e todos
  assistidos pelo Gemini em 28/09: `00034 p01` **reprovado** (cena 2: peça íntima sem
  relação com a narração; cena 8: a protagonista duplicada), `00034 p02` **aprovado**
  (01:44, revisão da madrugada), `00034 p03` **reprovado** (cena 14: troca de rosto e
  roupa), `00034 p04` **reprovado** (05:25, revisão da madrugada, depois de 6 tentativas
  recusadas: cena 13, a filha no chão e a imagem outra) e `00035 p01` **reprovado**
  (cenas 4–7: protagonista muda de aparência) — este **já estava no ar desde 27/09 20:43**,
  YouTube e TikTok. Também foram ao ar só com a folha, em 14–17/09: `00009 p05`,
  `00010 p02`, `00010 p03` (continuam `nao_assistido`; publicado não volta à revisão).
- **7 vídeos INSISTENTES** em `outputs/_reparos.json` (teto de tentativas): partes de
  `00004`, `00005`, `00010`, `00011`, todas antigas, esperando decisão humana.
- 108 linhas "a IA reprovou, mas as rodadas de conserto acabaram; sai assim" no
  `postar.txt`. Isso **era** a decisão dele de 13/09 ("tem que sair de qualquer forma");
  a de 27/09 é reter o reprovado e o `nao_assistido` enquanto houver outro candidato — a
  válvula é da publicação (S2). Pendente antigo, **não verificado** se ainda vale: a imagem
  fica ~6 s na tela e o ideal é 3–5 s (exigiria 45–60 imagens por parte).

## 7. Como conferir sem gerar nada

```
cd E:\projetos\historias
python main.py status [historia_00036]   # onde cada história está / parte por parte
python main.py auto --listar             # tarefas, próximo disparo, pendentes
python main.py conferir [historia_00036 --numeros]   # cache de voz + palavras/s
python main.py publicar                  # lista o catálogo (não sobe nada)
python main.py publicar historia_00036 --vistoriar   # laudo, sem upload
type outputs\_logs\auto_20260927.txt     # o que a madrugada fez
```

Em Python, sem efeito: `agenda.aprovados_no_estoque()`, `barrados_no_estoque()`,
`estoque_por_tipo()`, `incompletas()`, `falta_serie(agenda.carregar(), ap)`.

**O que NÃO fazer:** `python main.py auto` sem bandeira **é a rodada de verdade** (abre
navegador, gasta PicassoIA, 1–4 h) — só com `--listar`/`--instalar`/`--remover`. Nada de
`gerar`, `imagens`, `video`, `tudo`, `llm login`, `llm probe` numa sessão de leitura. Nada
entre **01h e 06h** (a criação segura as contas) nem pesado entre **:25 e :55** (postagem).
`pytest` avulso já escreveu no diário de produção: rode pelo `testar.py`, e nenhum teste
chama `agenda.rodar()` sem dublê de `_trabalhar`. Não mexa em `ferramentas/postar.py`,
`builds/grade.py` nem no ledger.

## Contratos com outras partes

**Travas por conta** (`builds/travas.py`; arquivo em disco, e **reentrante no mesmo
processo** — trava que já é sua devolve `True` de novo). `travas.do_perfil(<provedor>,
"geral")` é a de **ChatGPT / Gemini / DeepSeek**: o canal `geral` é o repo inteiro, e a
geração segura a conta pela história toda (horas) — contra isso funciona **trocar de
provedor**, não esperar. `travas.do_perfil("picasso", "historias")` é o **PicassoIA**,
disputado com o worker de builds quando a conta é a mesma (espera 20 s e desiste com
`NaoRodou`). `historias__auto` garante uma rodada automática por máquina;
`historias__render__<id>` impede dois renders da mesma história.

**O parecer que ninguém assistiu** (decisão dele em 27/09/2026: parecer só pela folha
fica retido e só sai se o horário fosse ficar vazio — a válvula é da publicação, S2).
Cada ficha de `outputs/_pareceres.json` (chave = id do vídeo,
`historia_NNNNN:celular:pNN`) tem desde 28/09 dois campos:

```
"situacao":  "aprovado" | "reprovado" | "nao_assistido"
"assistido": true | false      # true só com vista "video inteiro (m:ss)"
```

`nao_assistido` = só a folha de contato aprovou; `reprovado` vale para veto de vídeo **e**
de folha. **`aprovado` continua sendo a palavra do revisor** e não mudou de sentido: o
`postar.py` lê esse campo, e trocá-lo mudaria a escolha antes de a válvula existir. Para
ler, use `parecer.situacao(ficha)` (nas fichas antigas, sem o campo, deduz de `aprovado`
+ `vista`), `parecer.situacao_do_video(video_ou_id)` (pelo id, como `veto_por_id`) ou
`parecer.nao_assistido(video_ou_id)`. O estoque desta parte (`qualidade.liberado`,
`aprovados_no_estoque`) **ainda conta** `nao_assistido` como aprovado — muda junto com a
válvula, não antes.

**O diário** é `builds.atividade.registrar(...)` com `canal="historias"` e `etapa` (ex.:
`imagens.parede_de_planos`, `criacao.series`) — é o que o bot de apuração lê para
diagnosticar no Telegram, então erro que importa vai para lá e nunca só no `print`. **O
ledger** é `historias/outputs/_publicar/publicados.jsonl`: **nós lemos** (freio de estoque,
rodízio de tipo, conferência) e **quem escreve é a publicação**; linha só conta como
publicada se passa por `builds.publicar.metricas.publicado()`.

**Quem manda**: `historias/**` é desta parte; `ferramentas/postar.py`, `builds/grade.py` e
`builds/publicar/*` são da publicação (`publicacao.md`); `builds/travas.py`,
`atividade.py`, `content/voz.py`, `video/trilha.py` e `identity/*` são biblioteca
compartilhada (mexer ali afeta builds — avise); `painel/**` e `vila/**` são do painel
(`painel-e-vila.md`) e `remoto/**` do bot (`app-e-bot.md`). PicassoIA e as contas de LLM
são **contas compartilhadas com outras pessoas**: nada entra sem prova de origem, e a
página Contas do painel decide qual conta cada canal usa.
