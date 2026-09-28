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
ffmpeg, UMA compressão: h264 crf 18 + aac 192k, nível da luta no alvo (-13 dBFS ativo)
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
python main.py palco ab --duelo duelo_00016                       # A/B: o duelo x o palco
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

## Medido (28/09/2026, máquina ocupada)

| peça | tempo |
|---|---|
| timeline da luta (`gravar_timeline`, sem desenhar) | ~2-3 s por duelo |
| Godot, 2 s de vídeo (60 quadros) | 6,7 s de parede |
| Godot, duelo_00016 (23,23 s, 697 quadros, corte já aplicado) | 62-67 s (laço de 61-66 s; ~90 ms por quadro) |
| AVI intermediário | 108 MB para 23 s (~155 KB/quadro), apagado depois |
| x264 + aac do mp4 | 26-46 s para 23 s de vídeo |
| mp4 final | 8,2 MB para 23 s |

Nível do duelo_00016 no palco (sons de reserva): −19,5 LUFS integrado, média
−16,1 dB, pico −2,2 dBFS — na faixa do que a 16A mede no visual de hoje com o
som real (−17,8 a −18,7 LUFS).

## Pendente

- **16E (biblioteca):** peças por classe e por estilo de arma (as 54), as 24
  expressões como arte (hoje é o rosto vetorial portado do jogo), efeitos por
  (tipo, elemento) além do padrão tingido, arenas com arte, HUD no palco,
  `main.py palco vitrine`, e prender som em quadro de animação (API na peça).
- **Lacunas da timeline v1** (docs/palco/timeline.md): choque de projéteis, fim
  do projétil e o motivo, texto flutuante, eventos de movimento (pulo,
  aterrissagem, knockback). O palco usa o que existe.
- **16G:** a edição do duelo (identidade, HUD, veredito, música) sobre o clipe
  do palco, o perfil 16:9, o palco na geração noturna, e medir o render com a
  sessão bloqueada. Só depois da aprovação do Adrian.
