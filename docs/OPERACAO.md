# OPERAÇÃO — o mapa do que roda sozinho

O `README.md` da raiz é o mapa dos **projetos**. Este é o mapa da
**operação**: o que acontece entre "não existe nada" e "está no ar", quem
dispara cada coisa, o que impede um vídeo ruim de sair, como a IA confere o
trabalho, e o que a métrica sabe (e o que ela não sabe).

Escrito em 11/09/2026, depois de um dia em que três coisas diferentes foram
ao ar erradas. Cada seção termina com **o que ainda não existe**, nomeado —
um mapa que só mostra o que há mente por omissão.

---

## 1. O fluxo

Dois canais, mesma grade, fábricas diferentes.

| | `historias` (pacote `contos`) | `builds` (pacote `builds`) |
|---|---|---|
| o que é | drama narrado em série, imagem por IA | roleta de builds do jogo virando vídeo |
| de onde vem | LLM escreve o roteiro | o catálogo do `neural_fights` |
| destino | YouTube + TikTok | YouTube + TikTok |
| meta/dia | 8 vídeos | 8 vídeos |

A grade vive num lugar só, `random_builds/builds/grade.py`, e todo mundo lê
de lá: o publicador, o relatório do Telegram e a auditoria. Ela diz

```
GRADE = 00:37, 06:37, 09:37, 12:07, 15:37, 17:57, 20:37, 21:37, 22:37, 23:37
```

São as horas vagas das pessoas (pedido dele em 15/09/2026): indo para o
trabalho, café, almoço, lanche, ida embora e a noite ociosa até quase de
madrugada. Cada horário tem o próprio minuto (`grade.minuto(h)`), e a hora
identifica o horário nas tarefas e na guarda de um-por-horário. Até 15/09
eram oito, densos de manhã (6, 7, 8), todos em `:07`.

**O trabalho pesado é de madrugada.** Desde 15/09/2026 a criação roda só
entre 1h e 6h — depois do último post, das 00:37 — e de dia a máquina apenas
publica e avisa. Pesado é tudo o
que abre navegador e segura a máquina por horas: roteiro, imagem, render,
parecer do Gemini, conserto e métrica do TikTok. Cada rodada da madrugada faz,
nesta ordem:

1. coleta a métrica do YouTube e do TikTok, uma vez por noite;
2. pede o parecer do Gemini para cada vídeo pendente que ainda não tem
   veredito numerado por cena, para a postagem de dia só ler;
3. termina a história que ficou pela metade;
4. conserta os vídeos barrados;
5. começa uma história nova só se ela couber antes das 6h: medido na
   história 13 em 15/09/2026, uma história leva cerca de 2h15 (84 fotos e
   seis renders), e o config reserva 150 minutos.

Faltando menos de 30 minutos para fechar, a rodada não começa nada pesado.
Uma tarefa perdida de madrugada que o Windows tente rodar de manhã percebe
que está fora da janela e sai sem fazer nada.

**De dia, o que evita ficar sem vídeo — e encher o estoque.** Pedido dele no
mesmo dia: "a prioridade é não ficar sem vídeo". A criação também dispara 25
minutos depois de cada publicação (07:02, 10:02, 12:32, 16:02, 18:22, 21:02,
22:02, 23:02 e 00:02), em modo dia:

- com o estoque aprovado acima do teto e nada barrado, sai sem fazer nada;
- com vídeo barrado, conserta até dois por rodada, para terminar antes da
  próxima publicação;
- **abaixo do teto de estoque, termina a história incompleta e cria outra** —
  mesmo sem faltar vídeo para hoje;
- se o estoque não cobrir os horários que faltam hoje, é o mesmo trabalho,
  mas por emergência.

A criação de dia é de 15/09/2026 e vem de uma conta que não fecha: a grade
consome dez partes por dia e a janela de 1h às 6h só cabe **uma** história —
4h40 de janela contra 2h12 por história, e a rodada das 04:20 precisaria de
150 minutos e só tem 100. Seis produzidas contra dez publicadas são quatro a
menos por dia. Esperar faltar era reabastecer raspando o fundo; o trabalho
cabe justamente onde a máquina estava parada, nos buracos de 2h10 a 2h55
entre uma publicação e a próxima (06:47, 09:47, 12:42, 15:47 e 18:07).

**O teto de estoque são dois dias de grade** (vinte vídeos), e não um. Ele
continua derivado da grade — grade maior, teto maior, sem número solto em
lugar nenhum — e continua contando só vídeo novo e **aprovado**: barrado no
disco não é estoque. Era um dia desde 10/09 ("gordura de apenas um dia em
tudo, mas totalmente nova"), e a razão de então continua valendo: estoque
grande é feito com o molde de hoje e vai ao ar quando o molde já mudou. Vinte
vídeos saem em 48 horas, e é o mínimo para a grade de dez parar de pé.
`teto_de_estoque: 0` no config segue sendo o freio desligado.

E na hora de publicar, se nenhum vídeo da fila estiver limpo, sai o primeiro
que só tem o veto da IA contra ele, com aviso no Telegram. Vídeo mudo ou sem
imagem não sai nem assim.

**O TikTok posta em todos os horários.** De 13 a 15/09/2026 ele pulava 7h e
8h, por uma medição em que do sétimo post do dia em diante a distribuição
caía. Só que a fila avança com o YouTube: a parte publicada nesses horários
nunca chegava ao TikTok, e a série lá ficava com buracos. Decisão dele em
15/09 ("quero tapar esses buracos"): mesma parte nas duas plataformas em
todo horário. A grade nova não tem horários colados; a métrica do TikTok diz
se a distribuição aguenta os dez.

### As 25 tarefas do Windows

| família | quantas | quando | o que faz |
|---|---|---|---|
| `Historias_auto_HH` | 14 | 1h a 5h em `:20`, e 25 min depois de cada publicação | de madrugada: métrica, parecer, conserto e criação; de dia: conserto de barrado e criação enquanto o estoque estiver abaixo do teto |
| `NeuralFights_postar_HH` | 10 | nos dez horários da grade | publica um de cada canal, nos dois destinos |
| `NeuralFights_bot_telegram` | 1 | a cada 10 min | lê comandos, avisa erro, roda o apurador |

As tarefas acordam o PC se ele estiver suspenso, recuperam horário perdido
(o PC dorme, cai a luz) e estão configuradas para rodar na bateria — as duas coisas custaram um dia inteiro
em 09/09/2026, quando dez tarefas recusavam iniciar com `0x800710E0`.

### A linha de produção, de ponta a ponta

```
   LLM escreve o roteiro
        |  linguagem.conferir ........ termo de PARE descarta antes de gastar imagem
        |  pertinencia.problemas ..... o texto é mesmo desta história?
        v
   PicassoIA gera as imagens (uma por cena)
        |  prova de origem ........... o card do histórico com o NOSSO prompt
        |  fila.utilizavel ........... proporção DA HISTÓRIA (1:1 nova, 9:16 antiga), tamanho, não é colagem
        v
   narrador (edge-tts) + trilha + capa
        |  formato.resolver .......... velocidade e tela da HISTORIA (trava na 1a parte)
        |  aplicar_formato ........... voz 1,5x (atempo) e plano dividido ANTES de ir ao disco
        v
   render -> mp4 no disco ............ historia em cima, video de fundo mudo embaixo
        v
   qualidade.liberado(video) ......... A PORTA: mecânica + veto lembrado da IA
        v
   postar.py, nos horários da grade .. YouTube (API) e TikTok (navegador)
        v
   metricas .......................... reconcilia por título, busca views
```

O reparador (`contos/pipeline/reparo.py`) fica pendurado entre o render e a
porta: quando a vistoria acha algo que ele sabe consertar (cena com colagem,
imagem faltando), ele refaz e renderiza de novo, até 3 tentativas por vídeo.

**O formato do vídeo (desde 14/09/2026).** História nova sai **1,5x mais
rápida** (era 1,7x; ele achou rápido demais) e com a **tela dividida**: em cima
as imagens INTEIRAS (modo `encaixar`, sem corte) e a legenda, embaixo um
trecho mudo de `historias/assets/fundo/videoMaquiagem.mp4` (fora do git,
794 MB), sorteado pelo hash de `historia:parte`. O que manda está em
`config/render.json`, bloco `formato`. A voz é esticada depois da síntese e o
plano é dividido pelo mesmo fator antes de ir ao disco, então o parecer, os
cortes de Shorts e a métrica já leem o relógio final. O formato é **da
história**: se qualquer parte já renderizada não tem o campo `formato` no
plano, a série inteira fica no formato antigo (`contos/video/formato.py`); para
converter uma história de propósito, `outputs/<id>/formato.json`. Render de
prova: `main.py video <id> --parte N --prova PASTA --velocidade 1.7 --layout
dividido` — **nunca `--saida`**, que é a opção do log da agenda.

**Fotos quadradas e sem Pixar (14/09/2026, noite).** A foto 9:16 não
encaixava na metade de cima; história nova pede **1:1** ao PicassoIA
(`formato.aspecto` no `render.json`). A proporção também é da história: o
plano grava `aspecto_imagem`, e `fila.utilizavel`, o worker e o reparo usam a
proporção da própria história. Assim, uma cena refeita de uma história antiga
volta 9:16, e uma foto 9:16 perdida numa história 1:1 é recusada e refeita. O
cliente do PicassoIA recusa gerar se a proporção aplicada não bater com a
pedida (pedido vertical ainda aceita qualquer vertical, que é o que as builds
pedem). O molde `quebrada` perdeu o estilo "render 3D estilo Pixar" (o
personagem mudava de cena para cena) e usa o estilo fotográfico de todos. A
capa põe a foto quadrada inteira sobre o borrado dela.

**Furar a fila e as travas entre processos (14/09/2026).** Para um vídeo sair
antes da vez, escreva `historias/outputs/_publicar/prioridade.json` com
`{"videos": ["historia_00012:celular:p01"]}`: a próxima postagem da grade o
põe na frente e ele passa pelas mesmas guardas (vistoria, parecer,
um-por-horário, grade do TikTok); publicado, o pedido some sozinho. **A série
espera a parte barrada**: parte vetada ou reprovada segura as seguintes da mesma
história e a grade publica outra série; sem nada limpo sai a própria vetada com
arquivo inteiro, e a seguinte só vai fora de ordem em último caso. Parte cuja
anterior não tem mp4 nem está no ar não entra na fila. Entre processos: o
**apurador não edita código** enquanto a trava da agenda (`historias__auto`)
está ocupada; **uma renderização por história** (`historias__render__<id>`); a
criação espera até 25 min pela conta do LLM que a postagem estiver usando; e
`main.py publicar --tiktok` confere e grava o registro como a grade.

### O que ainda não existe aqui

- O vídeo de fundo tem **texto de tutorial em inglês e a marca "babycolor"**
  (visto pelo Gemini na prova). O parecer manda ignorar a metade de baixo, mas
  nada escolhe trechos limpos.
- O canal de `builds` **não tem fábrica automática**. As 8 tarefas de criação
  são só de histórias; os builds vêm de um estoque produzido a mão.
- Não há retomada de horário **dentro do dia**: se as 12h falharem, as 15h
  publicam o próximo vídeo, não dois. A grade não recupera atraso.

---

## 2. As medidas de segurança

A distinção que importa não é "que guardas existem", é **quais impedem**.
Um aviso é o que se lê depois; um erro é o que barra.

### O que BLOQUEIA

| guarda | onde vive | o que impede |
|---|---|---|
| termo de PARE | `contos/roteiro/linguagem.py` | roteiro que a plataforma derruba — descartado **antes** de gastar imagem |
| texto de outra conversa | `contos/roteiro/pertinencia.py` | prompts em inglês no meio de um drama em português (56 cenas de Minecraft entraram num vídeo assim) |
| vídeo mudo ou curto | `qualidade.vistoriar_arquivo` | menos de 8 s, mais de 180 s, média abaixo de -30 dB, menos de 100 KB |
| narração truncada | `qualidade.vistoriar_parte` | acima de 4,0 palavras/s a fala não cabe no vídeo: o áudio veio pela metade |
| cena sem imagem | `qualidade.vistoriar_parte` | cartão de texto no lugar da imagem — já passou três vezes como aviso |
| imagem sem prova de origem | `qualidade.vistoriar_parte` | placeholder ou teste indo ao ar como se fosse arte |
| colagem | `contos/imagens/composicao.py` | imagem em grade ou díptico onde devia haver um instante só (44 de 440 achadas) |
| imagem mais nova que o mp4 | `qualidade.vistoriar_parte` | render defasado: a correção não entrou no arquivo |
| veto da IA | `contos/publicar/parecer.py` | o Gemini assistiu e reprovou. **Vale por três rodadas de conserto**: depois delas vira aviso e o vídeo sai do jeito que está, com alerta no Telegram. Veto já gravado não gasta as tentativas do publicador, para os barrados da frente não esconderem os aprovados de trás |
| build com pendência | `builds/publicar/catalogo.py` | sem payoff, sem imagem do personagem, sem a luta no fim (23 de 66 estavam na fila) |
| conta ocupada | `builds/travas.py` | dois processos no mesmo login do PicassoIA ou do Gemini ao mesmo tempo |
| freio de mão | página Vila do painel | pausa a pipeline inteira, e a criação respeita |

### O que só AVISA

| aviso | por que não barra |
|---|---|
| sem capa própria | a capa melhora o clique, mas todo o acervo anterior a 11/09 está assim, e barrar pararia a grade para consertar vitrine |
| áudio baixo, mas acima de -30 dB | é estilo até certo ponto |
| abaixo de 1,5 palavras/s | vídeo arrastado é ruim, não é defeito |
| algumas cenas sem prova de origem | só barra quando **nenhuma** tem |
| termo de RISCO | reescreve o trecho em vez de descartar |

### A porta única

Três lugares perguntavam "este vídeo pode sair?" e davam **duas respostas
diferentes**. Medido em 11/09/2026: a auditoria mostrava zero barrados
enquanto o freio de estoque contava um vídeo reprovado pela IA.

Hoje existe uma função só, `qualidade.liberado(video)`, e os três consultam
ela: o publicador, o freio de estoque e a tela de auditoria. Ela **só lê** —
nunca abre navegador, porque o `panorama` tem regra escrita de não tocar
rede. Quem *pergunta* à IA é o publicador, uma vez, no horário. Os outros
dois leem o que ele achou.

### O que ainda não existe aqui

- **O canal de builds não tem vistoria de mp4.** A guarda de pendência olha o
  catálogo, não o arquivo: um build mudo ou truncado passa. Tudo o que foi
  construído nesta seção cobre **um canal só**.
- Nada confere a miniatura do YouTube depois do upload.

---

## 3. Como a IA confere

Três camadas, da mais barata para a mais cara.

**1. A vistoria mecânica** (`ffprobe`, milissegundos por vídeo). Mede o
arquivo: duração, canais de áudio, média em dB, silêncio no fim, tamanho.
Responde "o arquivo está inteiro?" e nada mais. Roda em todo vídeo, sempre.

**2. O parecer do Gemini** (`contos/publicar/parecer.py`). O Gemini
**assiste ao mp4** — o vídeo inteiro, não uma folha de contato. Um arquivo de
33 MB e 1:47 sobe em cerca de 100 s. O veredito é a primeira linha da
resposta, `APROVADO` ou `REPROVADO`, e qualquer outra coisa conta como sem
parecer. Isso é regra permanente do projeto: **quando for preciso analisar um
vídeo, o Gemini é quem olha** — ele enxerga o que o dado bruto não conta.

O parecer é **lembrado** em disco, com chave pela data de modificação do mp4:
re-renderizou, o veredito velho não vale mais. Assim a auditoria, o freio e o
publicador leem a opinião da IA sem abrir navegador nenhum. **O publicador
consulta antes de perguntar**, e um veto já registrado basta para barrar. Até
12/09/2026 ele perguntava de novo toda vez, e uma parte reprovada às 06:14
foi ao YouTube e ao TikTok às 15:34 do mesmo dia.

**Quem assistiu ganha de quem só viu a folha.** Quando a conta do Gemini está
ocupada, o pedido cai para o ChatGPT, que não assiste vídeo: ele julga uma
folha de contato com doze miniaturas. Essa resposta serve quando não há
nenhuma, mas **nunca** substitui um veredito feito com o arquivo inteiro. O
campo `vista` de cada ficha diz qual dos dois foi, e é ele que decide. Sem
essa regra, um "APROVADO" de oito caracteres apagou uma reprovação feita
depois de dois minutos e vinte e três de vídeo assistido.

Duas armadilhas de navegador que custaram tempo e estão consertadas: o
diálogo de consentimento ("o vídeo é meu") aparece **depois** do clique de
enviar, não antes; e só quando a duração do vídeo aparece na tela é que dá
para continuar.

### O que o Gemini reprova, e o que sabemos consertar

| motivo | o reparador resolve? |
|---|---|
| colagem, tela dividida, grade de painéis, marca d'água | **sim**: refaz a cena e re-renderiza. No vídeo de tela dividida, a queixa que fala da metade de baixo, do vídeo de fundo ou da maquiagem é o formato e **não** vira conserto (decidido pelo texto do veto, `reparo._motivo_e_do_formato`) |
| mp4 mais velho que a imagem | **sim**: só re-renderiza |
| imagem não bate com a narração da cena | **sim**: reescreve o prompt pela narração e refaz a cena |
| protagonista troca de rosto entre cenas | **sim**: fixa a descrição pela aparência que a IA viu na maioria das cenas e refaz só as apontadas |

**O número que a IA dá aponta CENA.** Até 13/09/2026 o prompt pedia "o
número do quadro" sem dizer o que era um quadro. Na folha de contato era a
sexta de doze miniaturas espaçadas no tempo, numa parte de 13 ou 14 cenas; no
vídeo, era a contagem do próprio Gemini. O reparador lia esse número como
cena e podia refazer a imagem boa. Agora a IA recebe cada cena com seu trecho
de tempo, a folha de contato tem um quadro por cena, e o veredito guarda se
numerou por cena. Veto sem essa numeração é perguntado de novo antes de
qualquer conserto, e nunca esquecido, porque esquecer liberaria o vídeo sem
parecer.

Os consertos de narração e de rosto mexem no roteiro, que é regravado inteiro,
com cópia do original ao lado. E a mesma regra entra antes do defeito nascer:
a revisão do roteiro passou a conferir se a imagem de cada cena mostra o que
a narração dela conta, e a ficha do protagonista exige etnia ou tom de pele e
**um traço concreto** do rosto. Repetir "a 30s man, short dark hair, tired
eyes" em todas as imagens não fixava ninguém: servia a um homem asiático e a
um branco igualmente.

**3. A prova de que está no ar** (`metricas.reconciliar`). O upload por
navegador quase nunca devolve o link. Então a reconciliação lê a playlist de
uploads do canal, normaliza os títulos e casa com o que o ledger diz que foi
publicado. Em builds casou 18 de 18. Essa é a única confirmação real de que
"publicado" significa publicado.

### O que ainda não existe aqui

- O **TikTok** só é conferido uma vez por dia, na coleta de métricas: o post
  que casa com o ledger prova que está no ar. Entre o envio e essa coleta, o
  que se sabe é a frase de status que o navegador devolveu.
- O parecer do Gemini cobre **só histórias**. Nenhum build é assistido.
- Um vídeo já publicado nunca é reavaliado. O erro descoberto depois do ar
  fica no ar até alguém apagar a mão.
- **Antes do render, quem confere imagem contra narração é só o LLM que
  revisa o roteiro.** Nada mede isso de forma independente antes de gastar
  imagem; a confirmação continua sendo o Gemini, depois do render.
- **O conserto de rosto depende de a IA descrever o protagonista.** Sem essa
  linha no veredito, a troca de rosto fica sem conserto.

### O apurador — a parte que surpreende

`remoto/apurador.py` é o pedaço mais autônomo do sistema, e vale saber que
ele existe: quando um erro cai no diário, o bot dispara uma sessão `claude -p`
que **lê** o código e escreve um diagnóstico no Telegram. Se o diagnóstico for
acionável, uma segunda sessão **edita o código** — só `Edit` e `Write`, nunca
`Bash` — e a suíte de testes é o único juiz. Falhou, ele restaura os arquivos
como estavam. Teto de 8 apurações por dia.

---

## 4. A métrica

O caminho completo, e ele tem um buraco grande.

```
   publicou -> registra no ledger do canal
                    |
                    v
            reconciliar(canal) ...... casa título com a playlist de uploads
                    |                 e preenche o youtube_id que faltava
                    v
            estatisticas() .......... views, likes, comentários (API do YouTube)
            retencao() .............. a curva, se o OAuth tiver Analytics
                    |
                    v
            outputs/_metricas/*.json
```

### Onde ele quebra hoje

| medido em 11/09/2026 | número |
|---|---|
| linhas no ledger de histórias | 48 |
| dessas, com `youtube_id` | **0** |
| arquivos de métrica do canal de histórias | **0** (a pasta não existe) |
| arquivos de métrica do canal de builds | 48 |
| desses, com curva de retenção | **1** |

A raiz: `contos/publicar/serie.py` nunca gravou o campo ao registrar. O que
vai na coluna de URL é uma frase de status — "publicado no TikTok (com a
confirmacao extra)" — não um link. Não é dado perdido: é campo que nunca foi
escrito.

A reconciliação por título resolve isso sem caminho novo, e é ela que passa a
ser o caminho **principal**, não o remendo, porque o upload por navegador não
vai voltar a devolver link.

**Depende de uma ação humana, e não adianta esconder isso em nota de rodapé:**

```
python -m neural_fights.tools.youtube_oauth --conta historinhas --com-upload --com-analytics
```

Sem reautorizar esse OAuth, o conserto fica pronto e inerte. A retenção
(1 de 48 em builds) tem a mesma causa do outro lado.

### Quando ela roda

Antes de 11/09/2026, **nunca sozinha**: zero das 17 tarefas atualizavam
métrica, e o único caminho completo era um botão numa aba do painel.

Hoje ela é serviço da madrugada: a primeira rodada da noite coleta, e as
outras saem caladas, porque views não mudam de hora em hora. Até 13/09/2026
ela ficava na postagem das 06:07, e a coleta do TikTok segurava o Studio por
até 12 minutos justamente quando o dia começava.

### O TikTok, pelo Studio

A API oficial do TikTok entrega views, curtidas, comentários e
compartilhamentos, e nada de tempo assistido nem retenção — além de exigir
app registrado e revisão. O TikTok Studio, aberto com o mesmo login que já
publica, entrega tudo isso e mais. Então a coleta abre o Studio e **escuta o
JSON que a própria página carrega**, sem ler a tela:

| resposta da página | o que traz |
|---|---|
| lista de conteúdo | todos os posts: hora exata, legenda, duração, views, curtidas, comentários, compartilhamentos, salvamentos |
| análise de cada vídeo | tempo médio assistido, taxa de conclusão, curva de retenção, origem do tráfego, seguidores ganhos |

O TikTok não devolve id ao publicar, então cada post é casado com o ledger
**pela hora**: o Studio registra a postagem de 1 a 7 segundos antes do que o
ledger anota, e a legenda confirma a parte ("Parte 3 de 6"). Medido em
13/09/2026: 21 de 21 em histórias e 19 de 19 em builds.

A análise por vídeo custa uma página cada, 8,8 segundos medidos, e roda na
madrugada com o perfil do TikTok travado. Por isso ela tem
orçamento: só vídeos da última semana, nunca duas vezes no mesmo dia, no
máximo 40 por canal, e quem nunca foi analisado passa na frente. Quem fica
de fora mantém a análise anterior em vez de perdê-la. Tudo vai para `_metricas_tiktok/`, **separado** da
pasta do YouTube, porque os experimentos indexam aquela pelo `youtube_id`.
Roda na mesma atualização diária do YouTube, num `try` próprio: login caído
no TikTok não apaga a métrica do YouTube.

### Como saber se está funcionando

- `historias/outputs/_metricas/` deixa de estar vazia.
- Os publicados de histórias passam a trazer `youtube_id` preenchido.
- O diário do dia mostra a atualização no primeiro disparo.

### O que ainda não existe aqui

- **A métrica do TikTok ainda não entra nos experimentos nem no painel.** Ela
  é coletada e gravada (veja abaixo), mas quem compara braços e formatos lê
  só a pasta do YouTube.
- 16 dos 48 arquivos de builds carregam um erro `channel==MINE` da API, e
  ninguém os repara.
- A comparação entre experimentos (`builds/experimentos.py`) já sabe medir
  braços, mas com histórias fora da métrica ela enxerga um canal só.

---

## Em uma frase

O sistema cria, confere e publica sozinho **um canal**; publica sozinho o
outro sem conferir; e mede sozinho um canal e meio. Os buracos estão
nomeados acima, cada um com o número que o mediu.
