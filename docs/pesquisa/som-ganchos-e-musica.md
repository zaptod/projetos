# Som, ganchos e música: o que tem evidência para o Neural Fights (20/10/2026)

Pesquisa de 20/10/2026 para as semanas 2 a 4 do `docs/PLANO.md`. Não repete o que já está em
`shorts-que-deram-certo.md` (título com o confronto, faixa no topo, câmera parada, série) nem em
`ferramentas-de-video.md` (HyperFrames, sons CC0); só cita quando precisa.

**Como foi feito.** Além das fontes na web, **medi o áudio de verdade**: baixei a trilha de 7
Shorts campeões (Orbitality ×2, Earclacks ×2, pulsebattles, Ham's, CodeCrafted) e de 2 duelos
nossos (`random_builds/outputs/duelo_00095` e `duelo_00141`, `final_celular.mp4`), medi volume
(EBU R128 pelo ffmpeg), quanto do tempo fica em silêncio, quantos ataques sonoros por segundo e
o volume do fim, e olhei o espectrograma dos 12 primeiros e 10 últimos segundos de cada um. A
legenda automática do YouTube confirmou onde há voz. Tudo só leitura, nada no repositório além
deste arquivo.

**Aviso honesto:** quase toda "estatística de Shorts/TikTok" que circula vem de blog de quem vende
ferramenta, sem dado de origem. Marquei cada número como **oficial**, **estudo** (com amostra),
**medido por mim** ou **terceiro** (fraco).

---

## 1. O que eu ouvi nos campeões (medido por mim)

| Vídeo | Views | Dur. | Voz no início? | % do tempo em silêncio (< −40 dB do pico) | "Piso" entre golpes | Últimos 3 s vs média | LUFS |
|---|---|---|---|---|---|---|---|
| Orbitality, [Vampire VS Toxic Spike](https://www.youtube.com/shorts/CsXJu_TvRFE) | 22,1 mi | 51 s | **sim**, 0–2,2 s: "Vampire versus Toxic Spike, who will win?" | **27%** | −83 dB | −28 dB (acaba em silêncio) | −19,4 |
| Orbitality, [Electric Ball VS Laser V2](https://www.youtube.com/shorts/it8YKbG-d34) | 3,85 mi | 48 s | não | **30%** | −59 dB | −10 dB | −19,9 |
| Earclacks, [Growing Ball VS Laser Ball](https://www.youtube.com/shorts/JTFk3xm__VA) | 14,1 mi | 49 s | não (efeito tonal tipo "boing") | 9% | −36 dB | **+9 dB** | −15,6 |
| Earclacks, [Sword VS Dagger](https://www.youtube.com/shorts/RMjY1CnGPt4) | 3,42 mi | 50 s | não | 15% | −64 dB | **+9 dB** | −22,1 |
| pulsebattles, [One Punch Man vs Gojo](https://www.youtube.com/shorts/fa9f_MR-0co) | 3,73 mi | 26 s | **sim**, 0–3,3 s: "One Punch Man versus Gojo, who will win?" | **37%** | −110 dB | **+17 dB** (2,8 s de silêncio e depois o golpe final) | −15,6 |
| Ham's, [Grappling VS Heal \| KOTR E34](https://www.youtube.com/shorts/PAWECNFqicQ) | 567 mil | 61 s | não | 20% | −46 dB | −8 dB | −21,9 |
| CodeCrafted, [When it finally reached the center](https://www.youtube.com/shorts/NiFpcFMjqGk) | 27,4 mi | 63 s | não; **0,57 s mudo no começo** | 2% (música contínua) | −12 dB | −14 dB | −21,4 |
| **Neural Fights, duelo_00141** | — | **12 s** | não | **0%** | **−15 dB** | 0 dB | −16,8 |
| **Neural Fights, duelo_00095** | — | **13 s** | não | **1%** | **−20 dB** | −8 dB | −16,2 |

**O que isso quer dizer:**
1. **Os duelos campeões não têm tapete musical.** Nos 6 de duelo/bolinha com arma, entre um golpe e
   outro o som cai para perto do silêncio (9% a 37% do vídeo, piso de −36 a −110 dB). No espectrograma
   cada golpe é um risco vertical isolado sobre fundo preto. **O nosso é o contrário:** um grave
   contínuo (a trilha sintetizada de `random_builds/builds/video/trilha.py`: "loop escuro em tom menor:
   bumbo, caixa, chimbal, 808, pad, arpejo") ocupa 100% do tempo, só 15–20 dB abaixo do pico, e os
   golpes aparecem como riscos finos por cima. O único campeão com música contínua é o CodeCrafted
   (que não é duelo: é uma bola acelerando com melodia por cima).
2. **O gancho de áudio que funciona é a VOZ com a pergunta, não um estrondo.** Dois dos duelos
   campeões abrem com uma voz de 2–3 s lendo o confronto e "who will win?" (o de 22 mi do Orbitality,
   o maior do grupo de duelos, e o de 3,7 mi do pulsebattles). Os outros começam com o primeiro golpe em 0,05–0,57 s; nenhum abre com
   música ou vinheta.
3. **O golpe tem "assinatura".** Earclacks (o nome do canal é "clack") tem um tom metálico fixo em
   ~1 kHz e ~4,4 kHz em todo choque de arma; no Orbitality os golpes do fim ganham dois tons fixos
   (~500 Hz e ~1,1 kHz). Ou seja: o choque soa como um instrumento, sempre o mesmo para o mesmo evento.
4. **O fim é mais alto ou é seco.** Earclacks termina +9 dB acima da média e o pulsebattles +17 dB, com
   uma **pausa de 2,8 s em silêncio antes do golpe final**. O Orbitality corta seco: ~1,4 s de silêncio
   depois do último golpe e o Short recomeça sozinho (loop natural, sem tela final).
5. **Volume:** os campeões ficam entre −15,6 e −22 LUFS; nós em −16/−17. Volume não é o problema
   (o YouTube só abaixa o que passa de ~−14).

Como repetir a medida: `ffmpeg -i X -ac 1 -ar 22050 -f f32le -` + janelas de 50 ms em numpy;
`ffmpeg -af ebur128` para LUFS; `showspectrumpic` para o espectrograma.

## 2. O que as plataformas dizem

- **Som ligado.** TikTok: "88% dos usuários dizem que o som é vital para a experiência" (Nielsen para
  o TikTok, jul/2020) e "9 em 10" (Kantar, jan/2021) ([TikTok, Evolution of Sound vol. 1](https://ads.tiktok.com/business/en-US/blog/evolution-of-sound-volume-1)).
  É pesquisa de opinião, não medida de comportamento. YouTube: o único número com fonte é de 2016,
  para o YouTube inteiro: 96% assistem com som ([Nieman Lab](https://www.niemanlab.org/reading/youtube-takes-a-shot-at-facebook-our-audience-continues-to-watch-not-scroll-with-sound-on/)).
  **Para Shorts não achei número oficial.** Conclusão prática: nas duas plataformas o padrão é som
  ligado, então o som pesa; mas o confronto precisa ser lido sem som (faixa no topo), porque parte do
  público está mudo.
- **Som também é sinal de distribuição no TikTok.** O TikTok lista "sons" entre as informações do
  vídeo usadas na recomendação, e o For You "geralmente não mostra dois vídeos seguidos do mesmo
  criador ou **com o mesmo som**" ([Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)).
  A página de transparência confirma: quando os vídeos do topo são parecidos demais, "por exemplo,
  **com o mesmo som**", o sistema troca alguns ([Transparência](https://www.tiktok.com/transparency/en/recommendation-system)).
  A mesma página diz que pesam "o idioma configurado pelo autor do vídeo" e "a região de onde o
  vídeo foi postado".
- **Por que o som no choque importa (ciência):** dois discos que se cruzam parecem *passar um pelo
  outro*; um som curto no instante do encontro faz o cérebro ver um *choque* ([Sekuler, Sekuler e Lau,
  Nature 385:308, 1997](https://michaelbach.de/ot/aud-bounce/)). Em jogo, áudio "suculento" aumentou a
  sensação de presença num experimento com duas versões do mesmo jogo ([Smets e van der Spek, 2021](https://research.tue.nl/en/publications/that-sounds-juicy-exploring-juicy-audio-effects-in-video-games/)).
  Sobre "satisfying"/ASMR em si **não há estudo controlado** ([Live Science](https://www.livescience.com/62091-oddlysatisfying-videos-satisfying.html)).
- **Gancho:** o próprio TikTok diz que "mais de 63% dos vídeos com maior CTR mostram a mensagem
  principal nos 3 primeiros segundos" ([guia oficial de anúncios, PDF](https://ads.tiktok.com/business/library/Auction_Ads_Creative_Tips.pdf);
  correlação, sem amostra publicada).
- **"Viewed vs swiped away" (no Studio: "Quantos escolheram assistir"):** não há número oficial. O
  estudo de Paddy Galloway (5.400 Shorts de 33 canais) é citado como "70–90% nos melhores, abaixo de
  60% a distribuição cai" ([terceiro, Virvid](https://virvid.ai/blog/first-3-seconds-hook-faceless-shorts-2026));
  o mesmo estudo achou que Shorts com mais de 50 s de duração média vista tiveram em média 4,1 mi de
  views ([videogen](https://videogen.io/blog/decoding-the-youtube-shorts-algorithm-a-deep-dive-into-3-3-billion-views)).
  Use só contra o nosso próprio histórico.
- **Contagem de views:** desde 31/03/2025 todo começo ou replay de Short conta como view
  ([MediaPost](https://www.mediapost.com/publications/article/404562/youtube-changes-how-it-counts-shorts-views.html)),
  e a documentação da API diz que **a partir de 24/08/2026** isso vale para todos os formatos do canal
  ([videos, Data API](https://developers.google.com/youtube/v3/docs/videos)). Loop dá view.
- **Duração:** Shorts vão até 3 min desde 15/10/2024 ([ppc.land](https://ppc.land/youtube-expands-shorts-duration-to-3-minutes/)),
  mas "**Shorts com mais de um minuto que tenham uma reivindicação ativa de Content ID, qualquer que
  seja a política, ficam bloqueados**" ([Ajuda oficial](https://support.google.com/youtube/answer/13053317)).
- **Música e API:** o recurso `video` da Data API **não tem nenhum campo para anexar som ou música**
  ([referência oficial](https://developers.google.com/youtube/v3/docs/videos)); um agendador confirma
  que por app de terceiros "não é possível escolher um som" ([Publer](https://publer.com/help/en/article/how-to-add-a-trending-sound-to-youtube-shorts-bwr81l)).
  Música da biblioteca de áudio do YouTube (sem royalties) "não recebe reivindicação de Content ID";
  música da biblioteca de Shorts só entra pelas ferramentas de criação do app
  ([Ajuda oficial](https://support.google.com/youtube/answer/13486873?hl=en)). No TikTok, conta
  comercial só vê a Commercial Music Library; música embutida no arquivo é julgada à parte e pode
  ser mutada ([Soundstripe, terceiro](https://www.soundstripe.com/blogs/tiktok-copyright)). Se o
  editor web do TikTok oferece a biblioteca de sons: **não confirmei** (fontes se contradizem).
- **Os campeões não usam música em alta.** Nenhum dos 7 tem crédito de música na página, e o
  espectrograma não mostra faixa musical nos 6 duelos. No TikTok, o 1º vídeo do Earclacks saiu com
  "som original – Earclacks", e os fãs reaproveitaram o som em montagens ([Know Your Meme](https://knowyourmeme.com/memes/weapon-ball-battles-earclacks)).

### Comentários e curtidas por mil views (medido nas páginas, 20/10)

| Vídeo | Pergunta no título/descrição? | Série? | Comentários / mil views | Curtidas / views |
|---|---|---|---|---|
| Ham's KOTR E34 | não | **sim (recorde, episódio)** | **1,23** | 2,0% |
| Earclacks Sword VS Dagger | **"Who will win…?"** na descrição | não | 0,38 | 1,5% |
| pulsebattles OPM vs Gojo | **"Who Will Win"** no título | não | 0,30 | 1,4% |
| Orbitality Vampire | só na voz | não | 0,10 | 2,1% |
| Orbitality Electric | não | não | 0,08 | 2,6% |
| Earclacks Growing | "Who will reach the goal first…?" | não | 0,05 | 1,1% |
| CodeCrafted | não | não | 0,02 | 0,6% |

Sete vídeos é pouco (é correlação), mas o desenho é claro: **série com recorde** dá de 3 a 50 vezes
mais comentário por view; pergunta escrita ajuda um pouco.

---

## (a) As 10 recomendações mais fortes

| # | Recomendação | Evidência | Custo para nós | Como medir | Semana |
|---|---|---|---|---|---|
| 1 | **Tirar a trilha de baixo da luta: só o som do que acontece, golpe sobre silêncio.** A trilha fica só na vinheta final (ou some). | Medido: 6/6 duelos campeões têm 9–37% de silêncio e piso de −36 a −110 dB; nós 0–1% e −15/−20 dB. TikTok troca vídeos "com o mesmo som" e não mostra dois seguidos com o mesmo som ([transparência](https://www.tiktok.com/transparency/en/recommendation-system), [Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)); a nossa trilha é **o mesmo loop em todo vídeo**. Sekuler 1997 (o som no contato faz ver o choque). | Pequeno: em `video/som_da_luta.py`/`trilha.py`, ganho da trilha durante a luta para zero (ou −30 dB) e os golpes sobem para o lugar dela (o `alvo_db` já existe no `edit_plan`). Sem motor novo. | A/B por 7 dias, metade com e metade sem trilha, sorteado: "Quantos escolheram assistir", % média assistida e views em 48 h. Som quem julga é o Adrian (o Gemini não ouve). | **2** |
| 2 | **Voz de 2 s no quadro 0 em inglês: "Sword versus Dagger, who will win?"**, com a mesma frase escrita. | Os 2 duelos com voz no início: 22,1 mi (Orbitality) e 3,7 mi (pulsebattles), confirmado pela legenda automática. TikTok: mensagem nos 3 primeiros segundos ([PDF oficial](https://ads.tiktok.com/business/library/Auction_Ads_Creative_Tips.pdf)). | Pequeno: o `content/voz.py` já fala; trocar para voz em inglês (edge-tts; atenção à memória "voz 403": atualizar o pacote antes). | "Quantos escolheram assistir" contra a semana anterior. | **1** (faz parte do "canal em inglês") |
| 3 | **Cada arma/classe com som próprio e fixo, e o som cresce com a regra de escalada** (o tom sobe um degrau de uma escala pentatônica a cada acerto ou a cada nível do contador; o último terço fica mais denso e mais alto). | Earclacks: tom metálico fixo em todo choque (o "clack" que dá nome ao canal); Orbitality: tons fixos nos golpes do fim. Earclacks termina +9 dB acima da média. Escalada visível em 4/12 campeões (pesquisa anterior). Áudio "suculento" aumenta presença ([Smets e van der Spek](https://research.tue.nl/en/publications/that-sounds-juicy-exploring-juicy-audio-effects-in-video-games/)). | Médio: tabela arma → som (bancos CC0 com `origens.jsonl`, já previstos) e deslocamento de tom pelo contador na mixagem. Escala própria, sem música de ninguém. | Curva de retenção: % que chega ao último terço e ao fim (YouTube Analytics por vídeo). | **2** (junto com "um contador que cresce") |
| 4 | **Final: 1–3 s de silêncio antes do golpe decisivo, o K.O. é o som mais alto do vídeo, e o vídeo acaba ≤1 s depois** (sem tela final longa; o Short recomeça sozinho). | pulsebattles: 2,8 s de silêncio e depois o final +17 dB. Orbitality: acaba seco, ~1,4 s depois do último golpe. Replay conta view desde 31/03/2025 ([MediaPost](https://www.mediapost.com/publications/article/404562/youtube-changes-how-it-counts-shorts-views.html)). Loop: um caso de ~100% → ~200% assistido ([vidIQ](https://vidiq.com/blog/post/double-youtube-watch-time-looping-shorts/)). | Pequeno: o motor já marca o golpe final e o corte de tédio já existe; é cortar o fim e abrir uma pausa antes do K.O. | % média assistida acima de 100% = gente revendo; views por espectador único. | **2** |
| 5 | **Duração de 45 a 58 s; nunca passar de 60 s.** | Campeões: 48–63 s. Galloway/5.400 Shorts: 50–60 s rendem mais ([videogen](https://videogen.io/blog/decoding-the-youtube-shorts-algorithm-a-deep-dive-into-3-3-billion-views), terceiro). Acima de 1 min, qualquer reivindicação de Content ID bloqueia o Short ([Ajuda oficial](https://support.google.com/youtube/answer/13053317)). | O PLANO já pede 35–50 s; mudar o alvo para 45–58 e pôr uma trava em 59 s no render. | Views e % assistida por faixa de duração (35–44 × 45–58). | **2** |
| 6 | **Declarar o idioma: `defaultLanguage` e `defaultAudioLanguage` = `"en"` no upload; no TikTok, conta com o idioma do app em inglês.** | A API tem o campo de idioma do áudio ([referência](https://developers.google.com/youtube/v3/docs/videos)); hoje `random_builds/builds/publicar/youtube.py` (`_corpo`, linhas 560–572) **não manda idioma nenhum**. O TikTok usa "o idioma configurado pelo autor" e "a região de onde foi postado" ([transparência](https://www.tiktok.com/transparency/en/recommendation-system)). | Mínimo: 2 linhas no `_corpo` + mudar o idioma do app na conta do TikTok (o Adrian, 1 minuto). | Studio → Público → países: % de views de EUA/Reino Unido/Canadá/Austrália antes × depois. | **1** |
| 7 | **3 horários fixos pensando nos EUA** (hora de Brasília): ~10h, ~19h e ~22h até 31/10; **a partir de 01/11 (fim do horário de verão nos EUA) somar 1 h** (11h, 20h, 23h), usando os minutos próprios da `grade.py`. | Orbitality posta 05, 13 e 21 UTC (02h, 10h e 18h de Brasília). Buffer (1,8 mi de vídeos): melhores horários de Shorts são sexta 16h–19h no horário local, à noite em geral (18h–23h); piores dias segunda e terça ([Buffer](https://buffer.com/resources/best-time-to-post-on-youtube/)). TikTok (7,1 mi de posts): domingo 9h e noite ([Buffer](https://buffer.com/resources/best-time-to-post-on-tiktok/)). O YouTube diz que não há horário mágico (Todd Sherman, [SEJ](https://www.searchenginejournal.com/youtube-explains-how-shorts-algorithm-works/494953/)). | Pequeno: ajustar a grade (já está no plano da semana 1, "YouTube 3/dia em horário fixo"). Respeitar a janela das postagens ao mexer. | Views nas primeiras 24 h por horário (cada horário vira um braço). | **1** |
| 8 | **Pergunta que pede escolha, nunca isca: descrição com "Who will win, the Sword or the Dagger? ⚔️🗡️" + 3–5 hashtags do nicho; um comentário com a mesma pergunta postado pela API logo após o upload** (fixar é manual: a API não tem "fixar"). | Pergunta na descrição/título: 0,30–0,38 comentários por mil views, contra 0,02–0,10 sem (medido, n pequeno). Hashtags que os campeões usam: `#satisfying #simulation #physics #weaponballs #ballsbattle` (páginas dos vídeos). Comentários são sinal de recomendação ([Newsroom TikTok](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)). A `commentThreads` só tem `list` e `insert` ([referência](https://developers.google.com/youtube/v3/docs/commentThreads)). | Pequeno: modelo de descrição + 1 chamada `commentThreads.insert` (OAuth já existe). | Comentários por mil views × semana anterior. | **1** (texto) e **3** (comentário automático) |
| 9 | **Série "Rei da Arena" com recorde na tela e o desafiante pedido nos comentários** ("Challenger requested by @fulano"), e 1 resposta por semana a comentário com um Short ("reply with video"). | Ham's KOTR E34 (série com recorde): **1,23 comentários por mil views**, 3 a 50 vezes mais que os avulsos (medido). CodeCrafted abre o vídeo de 27 mi com o pedido de um inscrito. O YouTube deixa responder comentário com um Short e avisa quem comentou ([Ajuda](https://support.google.com/youtube/answer/12816427)); no TikTok a resposta em vídeo aparece para quem viu o original (relato de criador, sem estudo: [The Method](https://themethod.beehiiv.com/p/feature-creators-using-get-millions-views-tiktok)). | Médio (já é a semana 3 do plano). A resposta em vídeo é pelo app do celular: manual, ~5 min por semana do Adrian, ou fica de fora. | Inscritos por mil views e comentários por mil views, série × avulso. | **3** |
| 10 | **Cada vídeo com um conceito próprio, e rodízio do que se repete** (arena, regra de escalada, conjunto de sons, cor do K.O.), para não cair em "inautêntico". | Texto oficial: é permitido "mesma abertura e fechamento, mas a maior parte do conteúdo diferente" e "cada vídeo com história, foco ou conceito distinto"; não é permitido "conteúdo gerado por IA com modelos genéricos que dão impressão de produção em massa" ([Ajuda, política do YPP](https://support.google.com/youtube/answer/1311392?hl=en)). TikTok: fora do For You o "material não original ou reaproveitado sem nada novo" ([Diretrizes](https://www.tiktok.com/community-guidelines/en/integrity-authenticity)). | Pequeno: estender o rodízio de alavancas que já existe para som e arena; vale também para a recomendação 1 (sem o mesmo loop em todo vídeo). | Nenhum aviso de "conteúdo inautêntico" no Studio; elegibilidade "recomendável" de cada post no TikTok Studio (o agente `metricas`). | **2 a 4** |

**As 5 mais fortes, em ordem:** 1 (tirar a trilha da luta), 2 (voz com a pergunta no quadro 0),
4 (pausa antes do K.O. e fim seco), 5 (45–58 s, nunca acima de 60) e 9 (série com desafiante dos
comentários). A 6 e a 7 são quase de graça e entram já na semana 1.

## (b) O que NÃO fazer

| Não fazer | Por quê (fonte) |
|---|---|
| **Pôr música comercial ou "em alta" dentro do arquivo** (YouTube ou TikTok) | Pela API não dá para anexar som do YouTube ([referência](https://developers.google.com/youtube/v3/docs/videos)), então qualquer música vai "assada" no arquivo e cai no Content ID comum. Acima de 1 min, qualquer reivindicação **bloqueia** o Short ([Ajuda](https://support.google.com/youtube/answer/13053317)). No TikTok, música embutida pode ser mutada, inclusive em conta pessoal ([Soundstripe](https://www.soundstripe.com/blogs/tiktok-copyright)). E os campeões não usam. |
| **Tocar a melodia de uma música famosa nota a nota nas colisões** (a moda "a bola toca a música") | Melodia reconhecível é *cover*: leva reivindicação de composição mesmo sem a gravação original ([Stemsplit](https://stemsplit.io/blog/cover-songs-youtube-permission), [Third Chair](https://usethirdchair.com/blog/youtube-content-id-for-music-rights-claims-and-gaps)). Com 45–58 s ainda passa, mas acima de 60 s bloqueia. Usar só escala/melodia nossa. |
| **Música de banco "grátis" (Pixabay e afins) sem prova** | Pode levar Content ID mesmo com licença (pesquisa anterior, `ferramentas-de-video.md`). Se for usar música, só a biblioteca de áudio do YouTube, que "não recebe reivindicação" ([Ajuda](https://support.google.com/youtube/answer/13486873?hl=en)), ou a nossa sintetizada, e com `origens.jsonl`. |
| **Usar som da biblioteca geral do TikTok se a conta for comercial (Business)** | Conta comercial só pode usar a Commercial Music Library ([Soundstripe](https://www.soundstripe.com/blogs/tiktok-music-licensing-rules)). Conferir o tipo da conta. |
| **Isca de engajamento** ("like se o Sword vence", "follow para a parte 2") | Fora do For You: "conteúdo que tenta manipular as pessoas para inflar curtidas ou seguidores" ([Diretrizes do TikTok](https://www.tiktok.com/community-guidelines/en/integrity-authenticity)). Pergunta de verdade ("quem vence?") pode. |
| **Voltar a 10 posts/dia no TikTok** | Medido por nós: 28 de 36 posts ficaram em 0 com ~10/dia. O TikTok evita dois vídeos seguidos do mesmo criador ([Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)). Manter 1/dia até haver dado novo. |
| **O mesmo loop musical em todo vídeo** | O TikTok troca e espaça vídeos "com o mesmo som" ([transparência](https://www.tiktok.com/transparency/en/recommendation-system)), e o YouTube pune "modelo genérico" ([política](https://support.google.com/youtube/answer/1311392?hl=en)). É o que fazemos hoje com a trilha. |
| **Passar de 60 s "porque Shorts vão até 3 min"** | Acima de 1 min, uma reivindicação qualquer bloqueia; e não há dado de que 90 s rende mais ([Bytecap](https://www.bytecap.io/research/best-youtube-shorts-length)). |
| **Subir o volume para "chamar atenção"** | Já estamos em −16/−17 LUFS, mais alto que os campeões (−15,6 a −22). O YouTube só abaixa. O ganho vem do contraste (silêncio × golpe), não do volume. |
| **VPN ou truque de região para cair no público dos EUA** | O TikTok proíbe "ferramentas de automação, scripts ou truques para contornar os sistemas" ([Diretrizes](https://www.tiktok.com/community-guidelines/en/integrity-authenticity)) e a nossa regra é não construir evasão. O certo é idioma do autor + texto e voz em inglês (recomendação 6). |
| **Ficar dependendo do navegador para postar no TikTok sem saber o risco** | A mesma regra de "scripts para contornar" vale de olho. A via oficial é a Content Posting API, mas app sem auditoria só posta **privado** ([TikTok Developers](https://developers.tiktok.com/doc/content-posting-api-get-started)). Não é para o plano de 30 dias; fica anotado. |

**Não vale o esforço agora (pouca evidência ou fora do automático):** ligar Shorts a vídeo longo (o
clique no "vídeo relacionado" relatado fica entre 0,05% e 1%, [Subscribr](https://subscribr.ai/youtube-strategy/drive-traffic-shorts-to-long-videos));
enquete em sticker (só pelo app do celular, sem efeito medido, [blog do YouTube](https://blog.youtube/creator-and-artist-stories/grow-youtube-channel-interactive-shorts/));
som em alta (nenhum duelo campeão usa; a API não anexa); ASMR (sem estudo).

## (c) Em qual semana entra cada uma

| Semana do PLANO | O que entra daqui | Medida |
|---|---|---|
| **1 (já começou: canal em inglês)** | 2 (voz "X versus Y, who will win?" em inglês), 6 (idioma `en` no upload e no app do TikTok), 7 (3 horários para os EUA, +1 h a partir de 01/11), 8 só o texto (pergunta na descrição + hashtags do nicho). Tudo é parte de "falar inglês com o público certo", sem mexer no motor. | A do plano: views por vídeo e "% que assistiu" × semana anterior; mais o % de views de países de língua inglesa. |
| **2 (câmera parada, 35–50 s, contador que cresce)** | 1 (sem trilha na luta, golpe sobre silêncio), 3 (som por arma que cresce com o contador), 4 (pausa antes do K.O. e fim seco), 5 (alvo 45–58 s, trava em 59 s). O som entra **nesta** semana porque sai do mesmo render e precisa estar fixado antes do teste de narração da semana 3 (senão o teste compara duas mixagens diferentes). Para não misturar efeitos: o A/B da semana 2 sorteia o vídeo inteiro (atual × novo); se der para separar, um braço só de som. | "Quantos escolheram assistir", % assistida, % que chega ao fim, inscritos por mil views. |
| **3 (Rei da Arena + voz do Adrian)** | 9 (desafiante dos comentários, recorde, 1 resposta em vídeo por semana se o Adrian quiser), 8 completo (comentário com a pergunta pela API). Atenção: com a narração do Adrian, a voz abaixa os golpes só enquanto fala (sem trilha por baixo). | Inscritos e comentários por mil views, série × avulso, narrado × não. |
| **4 (dobrar o que subiu)** | 10 (rodízio de arena, regra e sons; conferir elegibilidade no TikTok Studio); se o fim seco subiu o "% assistido" acima de 100%, levar para todos. | Meta de 30 dias. |

---

## Fontes

**Oficiais.** YouTube: [política de monetização / inautêntico](https://support.google.com/youtube/answer/1311392?hl=en) ·
[Shorts e Content ID (bloqueio acima de 1 min)](https://support.google.com/youtube/answer/13053317) ·
[música permitida em Shorts](https://support.google.com/youtube/answer/13486873?hl=en) ·
[responder comentário com Short](https://support.google.com/youtube/answer/12816427) ·
[Data API: videos](https://developers.google.com/youtube/v3/docs/videos) ·
[Data API: commentThreads](https://developers.google.com/youtube/v3/docs/commentThreads) ·
[stickers interativos (blog do YouTube)](https://blog.youtube/creator-and-artist-stories/grow-youtube-channel-interactive-shorts/).
TikTok: [como o For You recomenda](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you) ·
[sistema de recomendação (transparência)](https://www.tiktok.com/transparency/en/recommendation-system) ·
[diretrizes de integridade](https://www.tiktok.com/community-guidelines/en/integrity-authenticity) ·
[Evolution of Sound vol. 1](https://ads.tiktok.com/business/en-US/blog/evolution-of-sound-volume-1) ·
[dicas criativas (63% nos 3 s)](https://ads.tiktok.com/business/library/Auction_Ads_Creative_Tips.pdf) ·
[Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started).

**Estudos e dados.** [Buffer, Shorts 1,8 mi de vídeos](https://buffer.com/resources/best-time-to-post-on-youtube/) ·
[Buffer, TikTok 7,1 mi de posts](https://buffer.com/resources/best-time-to-post-on-tiktok/) ·
[vidIQ, primeiros 10 vídeos (367 mil canais de Shorts)](https://vidiq.com/research/youtube-first-10-videos-study/) ·
[Sekuler et al. 1997 (demonstração)](https://michaelbach.de/ot/aud-bounce/) ·
[Smets e van der Spek 2021](https://research.tue.nl/en/publications/that-sounds-juicy-exploring-juicy-audio-effects-in-video-games/) ·
[MediaPost, contagem de views](https://www.mediapost.com/publications/article/404562/youtube-changes-how-it-counts-shorts-views.html) ·
[Nieman Lab, 96% com som (2016)](https://www.niemanlab.org/reading/youtube-takes-a-shot-at-facebook-our-audience-continues-to-watch-not-scroll-with-sound-on/).

**Terceiros (fracos, usados só como direção).** [Galloway via videogen](https://videogen.io/blog/decoding-the-youtube-shorts-algorithm-a-deep-dive-into-3-3-billion-views) ·
[Galloway via Virvid](https://virvid.ai/blog/first-3-seconds-hook-faceless-shorts-2026) ·
[Publer, som pela API](https://publer.com/help/en/article/how-to-add-a-trending-sound-to-youtube-shorts-bwr81l) ·
[Soundstripe, TikTok](https://www.soundstripe.com/blogs/tiktok-copyright) ·
[Bytecap, duração](https://www.bytecap.io/research/best-youtube-shorts-length) ·
[Subscribr, Shorts → vídeo longo](https://subscribr.ai/youtube-strategy/drive-traffic-shorts-to-long-videos) ·
[The Method, resposta em vídeo](https://themethod.beehiiv.com/p/feature-creators-using-get-millions-views-tiktok) ·
[Know Your Meme, Earclacks](https://knowyourmeme.com/memes/weapon-ball-battles-earclacks) ·
[Live Science, satisfying](https://www.livescience.com/62091-oddlysatisfying-videos-satisfying.html) ·
[Stemsplit, covers](https://stemsplit.io/blog/cover-songs-youtube-permission) ·
[vidIQ, loop](https://vidiq.com/blog/post/double-youtube-watch-time-looping-shorts/) ·
[SEJ, Todd Sherman](https://www.searchenginejournal.com/youtube-explains-how-shorts-algorithm-works/494953/).

**Medido por mim (20/10/2026):** áudio e páginas dos 7 Shorts linkados na seção 1 e de
`random_builds/outputs/duelo_00095` e `duelo_00141`.
