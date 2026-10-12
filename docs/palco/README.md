# O palco (Onda 16D): a luta desenhada pelo Godot

Dono: builds (16D, 28/09/2026). O palco desenha a luta **só** a partir da
timeline v1 ([`timeline.md`](timeline.md), 16C) e toca o som do jogo pela
seção `sons` ([`sons.md`](sons.md), 16A). Ele **não publica nada**: tudo sai em
`random_builds/outputs/_palco/`, que o catálogo não varre. A troca do visual é a
16G, e só com a aprovação do Adrian, olhando e ouvindo.

Para mexer na arte, nos sons e no estilo: [`COMO-EDITAR.md`](COMO-EDITAR.md).

## A esteira

```
seed ──► gravar_timeline (16C, sem desenhar, ~2-3 s) ──► timeline.gcpf (zstd)
          + corte de tédio do duelo (highlights) ──► `remapeamento`
          + `sons` (16A: o que o jogo tocou)
job.json ──► Godot (palco/, Movie Maker, --fixed-fps 30) ──► AVI (MJPEG 0,95 + PCM 48 kHz)
          ──► relatorio_godot.json (quadros, sons tocados, peças usadas, reservas)
ffmpeg, UMA compressão: h264 crf 18 + aac 192k, luta a -18 LUFS, pico <= -1 dBFS
          ──► mp4 CONFERIDO ──► <mp4>.palco.json (tempos, medidas, peças)
```

- **O palco nunca decide nada da luta.** A simulação roda sem ele; ele só lê.
- **O corte de tédio é renderizado direto** (o plano de quadros pula os
  trechos cortados): não há mais a terceira compressão do corte.
- **Tempo só do contador de quadros.** Quadro `k` do vídeo = instante
  `t_src[k]` da gravação = passo `t × 60` da timeline, interpolado entre dois
  passos quando a câmera lenta pede. Eventos e sons passam pelo mesmo mapa
  (`PlanoQuadros.mapear` em GDScript e `builds/palco/plano.py` em Python, com
  teste cobrando que batem).
- **O golpe usa o relógio do MOTOR** (`golpe_fase` + `golpe_p`): "o que acerta
  é o que aparece". A animação da arma vai por `seek` para o progresso da fase.
- **Orbital no alcance real da hitbox** (`arma.alcance_m`, 1,5× o raio), e não
  a 1× como o render de hoje.

## Comandos (de `E:\projetos\random_builds`)

```bash
python main.py palco render --timeline T.gcpf --mp4 X.mp4      # timeline -> mp4 conferido
python main.py palco render --seed 883770751 --p1 "A" --p2 "B" --arena Torre
python main.py palco render --timeline T.json --quadros 90       # prévia: só 3 s
python main.py palco render ... --estilo tremor=0 --estilo nome_px=48 --hud
python main.py palco validar --timeline T.gcpf                    # headless, sem janela
python main.py palco testes                                       # testes do núcleo (GDScript)
python main.py palco editor                                       # abre o editor do Godot
python main.py palco sintetica --destino T.json --duracao 2       # timeline de mentira
python main.py palco ab --duelo duelo_00016 [--hud]               # A/B: o duelo x o palco
python main.py palco ab --duelo duelo_00031 --edicao              # 16G: B = palco + a MESMA edicao do duelo
python main.py duelo --seed N --palco                             # um duelo novo, só palco
python main.py duelo --seed N --palco --ab                        # + visual de hoje, lado a lado
```

`--saida` é do `main.py` (log), por isso o mp4 é `--mp4`. O subcomando `palco`
é despachado no topo do `main.py` e só ali importa `builds.palco`: um erro no
palco não derruba `publicar` nem a geração noturna.

## Onde as coisas estão

| o quê | onde |
|---|---|
| projeto Godot | `palco/` (`project.godot`, `palco.tscn`) |
| núcleo (não mexer para trocar arte) | `palco/nucleo/`: `palco.gd` (laço), `timeline.gd`, `plano.gd`, `biblioteca.gd`, `sons.gd`, `estilo.gd`, `peca.gd` |
| biblioteca (as peças) | `palco/biblioteca/{lutadores,armas,efeitos,sons,arenas,hud}` + `estilo.tres` + `LICENCAS.md` |
| exemplo que o F5 do editor toca | `palco/exemplos/exemplo.timeline.json` |
| testes do núcleo | `palco/ferramentas/testes.gd`, `validar.gd` |
| lado Python | `random_builds/builds/palco/` (`config`, `godot`, `plano`, `sons`, `fonte`, `render`, `checagens`, `sintetica`, `ab`, `cli`) |
| config | `random_builds/config/palco.json` (Godot, APPDATA, janela, encode, nível, pisos) |
| testes Python | `random_builds/tests/test_palco_regressions.py` |
| saídas | `random_builds/outputs/_palco/` |

## Configuração (medida no portão 16B)

- **Godot 4.7.2**, achado por `NF_GODOT` ou `config/palco.json → godot` (nunca
  caminho no código; há teste). O `_console.exe` devolve o código de saída.
- `gl_compatibility` (a HD 4600 não tem Vulkan e cai sozinha no ANGLE/D3D11);
  viewport 1080×1920, `stretch viewport/keep`, janela 270×480; vsync desligado;
  física a 30 ticks sem jitter fix; áudio e movie writer a 48 kHz; MJPEG 0,95;
  WAV importado sem compressão, sem normalizar e sem trim.
- **`--fixed-fps 30` é obrigatório** (sem ele o Movie Maker grava a 60 fps).
- **O `user://` cairia no C:** (quase cheio): o Python troca o `APPDATA` SÓ no
  processo do Godot, para `palco/_userdata/` (no shell inteiro isso quebra o
  Python).
- O cache (`palco/.godot/`) fica fora do git; `godot.garantir_importado` roda
  `--headless --import` quando algum arquivo do projeto muda.

## As guardas (falha é ERRO, nunca rc 0 calado)

| rc / conferência | o que pega |
|---|---|
| 2 | job ou timeline ilegível ou inválida (`Timeline.validar`: formato, versão, canais com `n` amostras, intervalos `[i0, i1]`, eventos em ordem, sons, trechos) |
| 3 | o 1º quadro não teve delta 1/30: faltou `--fixed-fps 30` |
| 4 | quadro sem desenho: a janela foi MINIMIZADA (o Movie Maker gravaria quadros vazios COM som e sairia 0) |
| conferência do mp4 | h264 na resolução pedida; nº de quadros = o do plano (Godot E Python); duração = quadros/30; faixa de áudio 48 kHz com a mesma duração; loudness integrada e média acima do piso; nenhum quadro liso; nenhum som sem arquivo |
| prazo | `90 s + 8 × duração do vídeo` (um palco que não encerra morre em minutos) |

O mapa do relógio: o Godot sai **no** último quadro (`quit()` no quadro N ainda
grava o N).

## Janela, foco e o Agendador

- A janela de render tem 270×480, **sem foco** (`no_focus`: WS_EX_NOACTIVATE,
  medido; NÃO é "sempre por cima"), e abre em `config/palco.json → janela.posicao`,
  que conta a partir da TELA 0 — aqui o monitor da ESQUERDA (x = −1366). O
  padrão `[1070, 200]` põe a janela no canto direito do monitor da esquerda.
- **Medido (28/09):** com outra janela em foco (explorer, Chrome), o foco nunca
  passou para o Godot em nenhuma amostra de 50 ms do render; o teste
  `test_render_curto_conferido_e_sem_roubar_foco` cobra isso a cada execução.
- **Janela coberta funciona; MINIMIZADA não** (rc 4).
- **O Godot precisa de sessão interativa** (há desktop e GPU). As tarefas do
  Agendador daqui são todas `LogonType Interactive` (só rodam com o Adrian
  logado), então a geração noturna teria desktop. **Sessão BLOQUEADA: não
  testado** — travar a sessão do Adrian para medir atrapalharia quem usa o PC e
  os navegadores logados da publicação. O palco não entra na geração noturna
  antes da 16G; quando entrar, medir numa madrugada com a sessão bloqueada (se
  quebrar, a guarda rc 4 ou a de quadro liso acusa, não passa calado).

## Medido (28/09/2026)

| peça | tempo |
|---|---|
| timeline da luta (`gravar_timeline`, sem desenhar, com os `sons` da 16A) | 1,8 s (duelo_00016) |
| Godot, 2 s de vídeo (60 quadros) | 6,7 s de parede |
| Godot, duelo_00016 (23,23 s, 697 quadros, corte do fight.json) | 51-67 s (laço de 50-66 s; 72-95 ms por quadro) |
| Godot, duelo seed 4242 (11,1 s, 333 quadros, luta curta sem corte) | 25,8 s |
| AVI intermediário (MJPEG 0,95) | 108-262 MB para 23 s, conforme o chão; apagado depois |
| x264 + aac do mp4 | 22-46 s para 23 s de vídeo |
| `palco ab` inteiro (timeline + palco + lado a lado) | ~2 min |

O chão pesa no arquivo: com a textura de pedra a 1024 px o mp4 do duelo_00016
foi de 8,2 MB para 35 MB (o x264 gasta bits no grão); a 512 px com borrão leve,
14 MB. O mesmo duelo no ar tem 7,7 MB.

**Nível:** o palco leva a luta a −18 LUFS integrado (o nível da luta na
mistura da 16A) e limita o pico em −1 dBFS. Mirar a energia ativa em −13 dBFS,
como a 16A descreve, deu −20,3 LUFS no duelo_00016, contra −16,5 do mesmo
duelo no ar: 4 LU a menos, e num A/B de ouvido o mais alto parece melhor. Hoje:
duelo_00016 no palco a −18,0 LUFS, média −13,7 dB, pico −5,1 dBFS; 161 sons de
19 arquivos distintos, nenhum sem arquivo, nenhum cortado por falta de voz.

**Hitstop do render: LIGADO** (Grimório `hitstop` = ligar, 28/09/2026). O
estilo global (`palco/nucleo/estilo.gd`, grupo "Tremor e hitstop") para o
vídeo 0 / 0,03 / 0,07 / 0,13 s (0 / 1 / 2 / 4 quadros) nos acertos de tier
leve / médio / pesado / colossal, e só no acerto que tirou ≥ 3% da vida do
alvo (`hitstop_dano_min`): o tier é do AUTOR, não do golpe, e sem o piso o
tique de 1% de um projétil parava como uma machadada. Medido nos 23 duelos
do disco (timeline re-simulada, sem render): **+12,9 s sobre 491,9 s =
+2,6%, +0,56 s por duelo**; o maior foi o `duelo_00023` (+0,80 s, +6,2%), o
`duelo_00016` fica 23,23 → 24,03 s, e `00015`/`00017` (só golpes leves) não
mudam. Sem o piso seriam +4,0% e +19,8% no `00023`. O Python refaz a conta
(`plano.quadros_de_hitstop`, lendo `estilo.gd` e `estilo.tres`) e o render
acusa se ela não bater com a do Godot; `palco validar` mostra os quadros com
hitstop sem abrir janela. No A/B o palco fica mais longo que o lado de hoje:
o mais curto congela no último quadro.

**16E, medido em 28/09 (21h):** a revisão de peças (10 páginas, 39 s,
1170 quadros) levou 97 s de Godot; o palco do `duelo_00016` com a arte da 16E,
o HUD e o hitstop deu 721 quadros (24,03 s: 697 + 24 de hitstop) em 53 s de
Godot e 22 s de x264. O A/B depois da arte está em
`outputs/_palco/ab2_duelo_00016/ab_celular.mp4` (nó `palco-ab-2` do Grimório).

**A/B do duelo_00016** (`outputs/_palco/ab_duelo_00016/ab_celular.mp4`): o
lado esquerdo é o `_ouvir/par2_duelo_00016` da 16A (o visual de hoje já com o
som real), o direito o palco; mesma seed, mesmo corte (23,23 s). O vídeo passa
duas vezes: a 1ª com o som da esquerda, a 2ª com o da direita (46,6 s).

## Pendente

- **16E (biblioteca), feito em 28/09:** hitstop do render ligado; as 24
  expressões montadas com as peças do Kenney (`lutadores/rosto/`, 12×);
  efeitos por (tipo × elemento) para projétil, área e beam com arte CC0
  (`objetos/<tipo>/<elemento>.tscn`); HUD do palco com nome, vida e plano
  legíveis no celular (`--hud`).
- **16E, falta:** peças por classe e por estilo de arma (as 54), acessórios
  das 16 classes, arenas com arte, efeito de skill (evento) por elemento,
  orbe/summon/trap/portal com arte, e prender som em quadro de animação (API
  na peça). As armas e os acessórios dependem da IA (16F, com prova de
  origem).
- **Lacunas da timeline v1** (docs/palco/timeline.md): choque de projéteis, fim
  do projétil e o motivo, texto flutuante, eventos de movimento (pulo,
  aterrissagem, knockback). O palco usa o que existe.
- **16G, o que falta:** o perfil 16:9 (o palco só desenha 9:16), LIGAR a
  chave do duelo de produção (pronta e desligada desde 07/10, seção abaixo;
  decisão do Adrian no nó `duelo-palco-sem-corrente`) e medir o render com a
  sessão bloqueada (não testado: o Adrian estava usando o PC).

## 16G, primeira metade: o A/B com a edição (30/09/2026)

`palco ab --duelo X --edicao` (`builds/palco/edicao.py`) faz o lado B com a
MESMA edição do duelo: re-simula a luta pela seed do `fight.json` (vencedor e
duração têm de bater), o palco desenha com o mesmo corte **sem o HUD dele**, e
o `edit_plan.json` do A é copiado trocando só o clipe. O que tem hora (barras,
plano, callouts, `luta.sons`, veredito) passa pelo relógio do palco:
`plano.paradas_de_hitstop` diz onde o hitstop para a imagem, e o que vem depois
anda o mesmo tanto. O `VideoRenderer` de sempre monta o B, com a música da
mesma seed; a capa não usa quadro do vídeo e é a mesma. O A é o
`final_celular.mp4` do duelo, intocado. Saída em `outputs/_palco/g16_<id>/`
(`final_celular.mp4` = B, `ab_celular.mp4` lado a lado, `medidas.json`).
Se o gameplay composto cair no transcode simples (sem HUD), é erro.

Medido (os dois duelos mais recentes com o som real, sem escolher):

| | `duelo_00031` (sem corte) | `duelo_00030` (corte de tédio) |
|---|---|---|
| quadros A / B | 729 / 729, 1080×1920 | 489 / 489, 1080×1920 |
| clipe de luta: pygame / palco / pedido | 726 / 730 / 730 | 486 / 489 / 489 |
| momentos de golpe no mesmo quadro | 105 de 105 (maior diferença 0) | 18 de 18 (0,004 s) |
| K.O. A / B | 20,83 / 20,833 s | 12,77 / 12,767 s |
| hitstop | 0 quadros (só golpes leves ou < 3%) | 0 quadros |
| trecho de luta A = B | -17,1 LUFS, média -14,9 dB, 0% calado | -16,9 LUFS, -15,5 dB, 0% calado |
| sons | 98, 21 ids, nenhum sem arquivo | 56 (4 caem no corte), 21 ids |
| preto / congelado ≥ 0,5 s | nenhum / nenhum | nenhum / A 14,57 s e B 14,73 s até o fim (depois do K.O., a cena para) |
| tempo | Godot 100 s + x264 33 s; A/B ~4 min | Godot 48 s + 18 s; ~2 min |

O clipe do pygame tem 3-4 quadros a menos do que declara (o renderer repete o
último); o do palco tem o que o corte pede. O som do B é o mesmo mix do A
(`luta.sons` pelo mesmo `som_da_luta`): sem hitstop nestes dois, o que muda
no A/B é só o desenho.

## 16G, segunda metade: o duelo de produção pelo palco (07/10/2026)

Pronto e **DESLIGADO**. A chave é `random_builds/config/palco.json →
producao.duelo_celular`:

| valor | o `final_celular.mp4` do duelo sai |
|---|---|
| `"desligado"` (padrão; qualquer valor desconhecido ou config ilegível também) | pelo pygame, como sempre |
| `"sem_corrente"` | pelo palco se NENHUM lutador usa arma do tipo Corrente; com corrente (ou arma que o banco não conhece), pelo pygame |
| `"todos"` | pelo palco |

Só o 9:16 (110 de 110 publicações de duelo são celular); o `final_normal.mp4`
continua no pygame. Nos 91 duelos do disco, `sem_corrente` mandaria 70 (77%)
pelo palco e 21 ficariam no pygame.

**Como.** `PipelineController._entregar_duelo` (duelo novo, `--rerender` e o
`som-da-luta` no lugar passam por ele; o `som-da-luta --destino` numa cópia
segue no pygame) pergunta à chave antes de renderizar o celular. Ligada, `builds/palco/producao.py` monta o B com o MESMO miolo do A/B
(`edicao.montar_sobre_o_palco`) em `<duelo>/palco/`, mede e só então troca:
primeiro `_segments_celular/` (que a guarda da luta muda da publicação mede),
depois o mp4 por `os.replace`. Reprovou ou quebrou (Godot, import, re-simulação
que não bate, guarda): o AVI e os mp4 do B são apagados, o motivo vai para
`<duelo>/palco_celular.json` e para o diário (status `log`, que não dispara a
apuração) e o celular sai pelo pygame. **O duelo nunca deixa de sair por causa
do palco.** Prévia (`--preview`) nunca vai pelo palco.

**Guardas do B** (falhou uma, fica o pygame): a luta re-simulada bate com o
`fight.json` (vencedor, duração); a conferência do render (quadros, faixa,
volume, quadro liso, hitstop Python = Godot); o composto não caiu no
transcode simples; todo momento de golpe do A no mesmo quadro do B e
vice-versa; K.O. no mesmo quadro; duração da IMAGEM = A + hitstop, com folga de
`folga_quadros` (3); nenhum trecho preto; congelado só depois do K.O.; o
trecho de luta e o arquivo inteiro passam pela régua da publicação
(`publicar.audio.medir`); o trecho calado no máximo `limite_calado` (25%).

A 1ª versão media a duração do ARQUIVO e barrou um B perfeito: a faixa de
áudio passa ~0,1 s do último quadro (no A também: `duelo_00091` com 840
quadros = 28,0 s e arquivo de 28,1 s). A guarda mede quadros/30.

**Prova** (`E:\tmp_pytest\ab_0710\`, cópias fora do catálogo; o
`_entregar_duelo` de verdade com a chave forçada só no processo; palco da
worktree, sem as peças do Ateliê, que outra sessão estava ligando):

| | `duelo_00091` (Dupla × Dupla), `sem_corrente` | `duelo_00090` (Arremesso × Corrente) | duelo NOVO (gravar + entregar), 22 s |
|---|---|---|---|
| saiu por | palco | `sem_corrente`: pygame ("corrente: Vex Fylermar (Acieloth)"); `todos`: palco | palco |
| quadros A / B | 840 / 855 (palco 856; hitstop 16 = 0,533 s) | 840 / 858 (hitstop 18 = 0,6 s) | — / 660 (hitstop 19) |
| golpes no mesmo quadro | 33 de 33 (maior diferença 0,004 s) | 50 de 50 (0) | 36 de 36 (0) |
| K.O. A / B (relógio sem hitstop) | 24,5 / 24,5 s | 24,5 / 24,5 s | 17,87 / 17,867 s |
| trecho de luta A → B | -17,8 → -17,8 LUFS; -15,2 → -15,3 dB; 0% → 0% calado | -16,7 → -16,7; -13,8 → -13,8; 0% → 0% | -17,8 LUFS, -14,9 dB, 0% |
| vídeo inteiro A → B | -16,8 → -16,6 LUFS | -15,4 → -15,5 | -16,7 |
| preto / congelado | nenhum / A 25,96 s e B 27,59 s até o fim (depois do K.O.) | nenhum / A 27,06 s e B 27,62 s | nenhum / 21,02 s (K.O. 18,47) |
| tempo do palco | 182 s (timeline 3, Godot 87, x264 34, edição 51, medidas 3) | 208 s (2 / 91 / 40 / 60 / 4) | 129 s; o duelo inteiro 3,6 min |

O B tem 1 quadro a menos que o clipe do palco no `00091` (855 × 856): a edição
arredonda a duração para 3 casas (28,533 × 30 = 855,99) e o último quadro, já
parado depois do K.O., cai. Dentro da folga. A primeira passada da prova
(10:21, antes do conserto da guarda de duração) caiu no pygame sozinha — o
caminho de falha também foi exercido de verdade.

**Reserva da geração:** `geracao.json → minutos_por_duelo_palco` = 8 (o
duelo do pygame segue com 5), só com a chave ligada (`noite.minutos_por_duelo`).

**Peso:** `<duelo>/palco/` fica com o clipe do palco (19 MB para 28 s), a
timeline, o plano B e as medidas — ~0,9 GB por semana de lote no E:.

### Depois da conferência (07/10, tarde)

- **Nome por trás do veredito.** A placa do palco ficava atrás do nome grande
  do vencedor. O job ganhou `nomes_ate_quadro` (o quadro do B em que o
  veredito da edição entra, `edicao.quadro_do_veredito`, arredondado para
  baixo): `palco.gd` esconde as placas dali em diante e devolve o campo no
  relatório; o render CONFERE (palco.gd sem o campo = erro, e o celular cai
  no pygame). Não dá para fazer só pela edição: a placa está no pixel do
  clipe. Vale também para o `palco ab --edicao`.
- **Cor da placa.** Era a do lado (azul p1, salmão p2) e o HUD da edição usa a
  do lutador. A timeline do duelo ganha `cor_nome` = `cor` do lutador
  (`edicao.nomes_na_cor_do_lutador`) e o `palco.gd` usa `cor_nome` se houver;
  o anel continua no `cor_lado`.
- **Falha silenciosa.** Cada falha segue `log` no diário; com
  `producao.falhas_para_avisar` (3) falhas SEGUIDAS sai UM `erro` (o bot
  avisa) com o motivo da última, e um duelo que passa pelo palco zera a conta
  (com `ok` "palco voltou" se tinha avisado). Estado em
  `<runtime>/palco_producao.json`. Duelo com corrente não conta.
- **Restos.** Chave voltando a `desligado` (ou duelo com corrente no
  `sem_corrente`) apaga `<duelo>/palco/` junto do `palco_celular.json`.
- **Godot ausente** falha antes de re-simular a luta (`config.godot` e
  `config.projeto` primeiro): na conferência levava 5,5 s para descobrir.
- **`folha_animada.gd`** (a peça que a Oficina exporta; o fogo do Adrian) fazia
  `float()` de lista nos canais da trilha: SCRIPT ERROR a cada projétil. Agora
  `_numero()`; teste em
  `palco/testes/test_folha_animada.py` (falha com o arquivo antigo).

A/B de novo (13:00, palco de a5296e6 + estes consertos, `duelo_00091`,
`E:\tmp_pytest\ab_0710\duelo_00091_sem_corrente{,_palco_atelie}\`): sem peças e
com peças de TESTE do Ateliê numa cópia da biblioteca (garras magenta, sai
verde, acerto/K.O. em estrela, invocação ciano, e a pele do Adrian). Os dois
pelo palco: 33/33 golpes no mesmo quadro, K.O. 24,5/24,5 s, 855 quadros,
trecho de luta -17,8 LUFS e 0% calado como o A, nomes escondidos no quadro 819
(relatório do Godot confirma), nenhum aviso do Godot. Com peças, o relatório
lista 8 lugares servidos por `partes/` (as duas armas, 3 acertos, K.O., 2
invocações). Palco 282 s (Godot 165 s, com import) e 190 s (Godot 77 s).
