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
HORAS  = 6, 7, 8, 10, 12, 15, 17, 20      (oito horários)
MINUTO = 7                                 (publica em :07)
```

e a criação roda em `:20`, treze minutos depois de publicar — de propósito,
para o vídeo criado agora nunca disputar o horário que está saindo.

### As 17 tarefas do Windows

| família | quantas | quando | o que faz |
|---|---|---|---|
| `Historias_auto_HH` | 8 | nos oito horários, `:20` | cria: roteiro, imagens, voz, render |
| `NeuralFights_postar_HH` | 8 | nos oito horários, `:07` | publica um de cada canal, nos dois destinos |
| `NeuralFights_bot_telegram` | 1 | a cada 10 min | lê comandos, avisa erro, roda o apurador |

As tarefas recuperam horário perdido (o PC dorme, cai a luz) e estão
configuradas para rodar na bateria — as duas coisas custaram um dia inteiro
em 09/09/2026, quando dez tarefas recusavam iniciar com `0x800710E0`.

### A linha de produção, de ponta a ponta

```
   LLM escreve o roteiro
        |  linguagem.conferir ........ termo de PARE descarta antes de gastar imagem
        |  pertinencia.problemas ..... o texto é mesmo desta história?
        v
   PicassoIA gera as imagens (uma por cena)
        |  prova de origem ........... o card do histórico com o NOSSO prompt
        |  fila.utilizavel ........... vertical, tamanho, não é colagem
        v
   narrador (edge-tts) + trilha + capa
        v
   render -> mp4 no disco
        v
   qualidade.liberado(video) ......... A PORTA: mecânica + veto lembrado da IA
        v
   postar.py, às :07 ................. YouTube (API) e TikTok (navegador)
        v
   metricas .......................... reconcilia por título, busca views
```

O reparador (`contos/pipeline/reparo.py`) fica pendurado entre o render e a
porta: quando a vistoria acha algo que ele sabe consertar (cena com colagem,
imagem faltando), ele refaz e renderiza de novo, até 3 tentativas por vídeo.

### O que ainda não existe aqui

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
| veto da IA | `contos/publicar/parecer.py` | o Gemini assistiu e reprovou |
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
| colagem, tela dividida, grade de painéis | **sim** — refaz a cena e re-renderiza |
| mp4 mais velho que a imagem | **sim** — só re-renderiza |
| protagonista troca de rosto entre cenas | não: refazer uma cena não devolve continuidade |
| imagem não bate com a narração da cena | não: o prompt errado está no roteiro |

O reparador lê os motivos escritos pela IA, e isso exige falar a língua dela:
ele diz "cena", o Gemini escreve "quadro"; ele dizia "colagem", o Gemini
escreve "tela dividida" e "grade de painéis". Enquanto os dois vocabulários
não bateram, o log registrou "0 de 8 barrados consertados" por oito rodadas
seguidas, com o detector funcionando o tempo todo.

As duas linhas que ele não resolve nascem na escrita, não na imagem. Contra a
troca de rosto, a ficha física do protagonista passou a exigir etnia ou tom
de pele e **um traço concreto** do rosto: repetir "a 30s man, short dark
hair, tired eyes" em todas as imagens não fixa ninguém, porque serve a um
homem asiático e a um branco igualmente, e o gerador escolhia um diferente a
cada cena.

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
- **Nada confere se o prompt de imagem descreve o que a narração daquela cena
  diz.** Existe guarda para o texto ser da história certa, e nenhuma para a
  imagem combinar com a fala. É o Gemini quem descobre, já com o vídeo
  renderizado e o custo todo gasto.
- A ficha do protagonista só melhora as histórias **novas**. As já escritas
  ficam com a descrição vaga que têm.

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

Hoje ela está pendurada no `ferramentas/postar.py`, depois da publicação — e
não numa tarefa nova, porque uma nona coisa para endurecer contra bateria e
horário perdido não valeria a pena. Roda **uma vez por dia**, no primeiro
disparo, e sai calada nos outros sete: views não mudam de hora em hora.

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

A análise por vídeo custa uma página cada, 8,8 segundos medidos, e roda
dentro da tarefa das 06:07 com o perfil do TikTok travado. Por isso ela tem
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
