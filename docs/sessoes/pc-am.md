# PC am — o trabalhador remoto

Pedido do Adrian (19/10/2026): "quero passar todo o trabalho pesado para um PC que estou deixando ligado aqui." Este documento foi escrito pela
sessão que preparou o am e o mecanismo no mesmo dia; tudo o que tem número foi medido naquela noite. O que não deu para conferir está marcado
**(não verificado)**.

## 0. A regra

- **No am roda só trabalho sem login.** Publicação (YouTube/TikTok), IAs com conta (ChatGPT, Gemini, DeepSeek), PicassoIA/Digen, perfis de
  navegador, credenciais e o banco de contas ficam **neste PC**. No am há só o repositório público, o Blue Lock público e as entradas que um
  trabalho copia (o banco de personagens, o ledger da arena, a trilha), sobrescritas a cada trabalho.
- **Cada trabalho tem uma chave**, em `random_builds/config/pc_am.json → trabalhos`. **Nasceram todas desligadas; desde 26/10 `testes` e `bluelock` estão ligadas e o `duelo` não** (seção 3, há teste). Desligada = o
  trabalho roda aqui exatamente como antes. Só `true` liga.
- **O am nunca para nada.** Chave ligada e o am fora, ocupado ou falhando: o trabalho roda aqui, com aviso. A única exceção é a medição
  (`--forcar-am`), que **nunca** roda aqui (para não pôr carga neste PC por acidente).

## 0b. Disponibilidade sozinha e queda segura (ponto 9, 26/10/2026)

Pedido: "quando o PC am desliga, tudo cai neste PC; o sistema tem que perceber sozinho se ele está disponível e mandar o pesado para lá".

- **A sonda** (`builds/pc_am/sonda.py`): UMA chamada `ssh` (`BatchMode`, `ConnectTimeout` 4 s, prazo 12 s) que roda `echo` e lista a pasta
  `ativos` do am — nenhum Python lá. Estados: **disponível**, **ocupado** (já há `paralelo.maximo` = **1** trabalho vivo; o agente confere o pid, então
  arquivo que sobrou de uma queda não conta) e **indisponível** (não conectou). Cache em `%LOCALAPPDATA%\neural-fights\pc_am\sonda.json`:
  45 s para disponível/ocupado, 90 s para indisponível (o am desligado custa uma sonda a cada 90 s, não um timeout por trabalho; o am que liga é
  notado em até 90 s). `python -m builds.pc_am sonda [--agora] [--json]`; o retrato do handoff (`ferramentas/handoff.py`) mostra a linha.
- **Roteamento:** `maquina.executar` sonda ANTES de tudo. Disponível → o trabalho vai ao am (se a chave dele estiver ligada). **Indisponível →
  roda aqui NA HORA, sem tentar SSH, sem aviso no Telegram, sem erro: uma linha de log** (`[pc_am] ... rodando neste PC — am indisponivel`, e
  `atividade` com status `log`). Ocupado → o duelo (que não espera) roda aqui; o que espera (`espera_da_fila_s`) espera a vez. A medição
  (`--forcar-am`) continua sem rodar aqui. O único aviso que sobrou é a ANOMALIA: a sonda disse "disponível" e o SSH caiu em seguida (um aviso por
  queda, e o cache passa a "indisponível").
- **Um pesado por vez:** `paralelo.maximo` = 1 (padrão do código e do `pc_am.json`). O mecanismo de vários ao mesmo tempo continua lá (a fila de
  20/10), só não é o padrão.
- **A janela das postagens** tem UM ponto, `builds/pc_am/relogio.py` (`liberado()`): a trava central `builds.janela.em_janela` → se não
  importa, `bluelock.comum.janela_das_postagens` → se não, `builds.grade` (post−12..post+18). Não consegui ler = espera. Dentro da janela o
  `executar` levanta `NaJanela` (o CLI sai com 5) — nem o envio vai ao am, porque ele usa a mesma rede por onde sobe o vídeo. Chave desligada não
  é barrada (é o de sempre). A fila (`fila.py`) pergunta no começo de cada passo.
- **Sem GitHub no am** (o am não tem login e o repositório do Blue Lock é privado): o `lado_am` não fala mais com o GitHub. O código chega por
  `git bundle` + scp (`refs/pcam/*`, ref temporária daqui apagada no fim; delta desde o HEAD do am quando ele é ancestral; sem clone, `git init`
  + `git fetch` do bundle). Commit explícito do Blue Lock (o ramo que o vigia testa) vai pelo mesmo caminho, a partir do espelho daqui.
- **Chaves em 26/10:** ver a tabela da seção 3. O am estava DESLIGADO: a prova do caminho de queda é o teste
  `test_pc_am_sonda.py::test_caso_zero_*` e `python -m builds.pc_am sonda` (→ "indisponível ... o pesado roda neste PC").

## 1. O am

| | |
|---|---|
| Rede | Tailscale `am` = `100.118.115.9` (direto pela LAN `192.168.0.9` quando o Tailscale acha; às vezes pelo relay `sao`). Ethernet 100 Mbps lá; este PC está no Wi-Fi |
| Acesso | `ssh -i ~/.ssh/id_ed25519_am -o BatchMode=yes alvo@100.118.115.9` — só chave, só pela rede do Tailscale (firewall). Shell padrão = CMD. `alvo` é administrador |
| Máquina | Windows 11 Pro 26100, i3-4170 (2 núcleos / 4 threads), 8 GB, AMD Radeon R5 220 (driver 15.201, 2015), só o C: (~68 GB livres depois da instalação). Suspensão na tomada: **nunca** (já estava). O `alvo` fica logado no console (sessão 1) |
| Instalado em 19/10 (winget, silencioso) | **Python 3.14.4** em `C:\Python314` (o mesmo daqui, todos os usuários, no PATH), **Git 2.55.0.windows.5**, **Node 24.15.0** / npm 11.12.1 (o Blue Lock pede ≥ 22.12; o CI dele usa 24), **FFmpeg 8.1.2** full (Gyan, o mesmo daqui; em `%LOCALAPPDATA%\Microsoft\WinGet\Links`). O Chrome 155 já estava lá (aqui 155.0.8059.82, lá .85) |
| **Não** instalado | Godot (a chave do palco, `config/palco.json → producao.duelo_celular`, está `desligado`; os testes do palco pulam lá), torch/whisper, nada de login |
| Workspace | `pip install -e ".[dev]" -e ./random_builds -e ./historias -e ./mimetizar -e ./visao -e ./painel` + `playwright` + `edge-tts`, com as versões **travadas pelo `pip freeze` daqui** (`C:\nf\tmp\restricoes.txt`); `pip check` limpo. `npm ci` no Blue Lock (7 s) |

```
C:\nf\
  agente\lado_am.py        o agente (o lado daqui o reenvia sozinho quando muda)
  projetos\                clone de github.com/zaptod/projetos (vai ao commit daqui a cada trabalho)
  BLUE-Lock-project\       clone de github.com/zaptod/BLUE-Lock-project (vai ao commit do espelho daqui; nunca empurra nada)
  runtime\                 o NEURAL_FIGHTS_RUNTIME_DIR dos trabalhos
  trabalhos\<id>\          job.json, log.txt, fim.json, pid.txt (e a saída do trabalho, se for lá)
  estado\                  pip.txt / npm.txt: hash do pyproject / do package-lock da última instalação
  tmp\                     restricoes.txt, diffs, bundles, zips de entrada (apagados depois de usados)
  ativo.json               o trabalho que está rodando agora (um por vez)
```

## 2. Como funciona (`random_builds/builds/pc_am/`)

`maquina.executar(trabalho, local=...)` é a porta única:

1. **Chave** desligada → `local()`.
2. **Fila:** a trava `pc_am` daqui (`builds.travas`, um trabalho pesado por vez no am, que tem 8 GB) e o `ativo.json` de lá, que recusa um
   segundo. O tempo que cada tipo espera a fila está em `espera_da_fila_s` (o duelo não espera: a geração tem relógio).
3. **Saúde** (`lado_am saude`): SSH responde, disco ≥ `disco_minimo_gb` (10), memória livre ≥ `memoria_minima_mb` (1200), ninguém rodando.
4. **Código:** o clone do am vai ao **commit exato** daqui. Se o GitHub não tem o commit (ramo à frente do `origin`, como hoje), vai um
   `git bundle` desde o HEAD do am, por scp. As mudanças **não commitadas** daqui vão junto (`git diff --binary HEAD`, aplicado com
   `git apply`), para rodar o mesmo código que rodaria aqui. Arquivo novo **sem `git add`** não vai (o resultado lista quais). Mudou um
   `pyproject.toml` → `pip install` de novo; mudou o `package-lock.json` do Blue Lock → `npm ci`.
5. **Entradas:** só as que mudaram (sha256 dos dois lados), num **zip só, um scp só**, aberto lá (`desempacotar`).
6. **Execução:** desanexada (WMI `Win32_Process.Create`: a queda do SSH não a mata), sem janela, com **prazo** (`prazo_s` por tipo; estourou =
   a árvore inteira morre, rc 124), log, `fim.json`, prioridade **abaixo do normal**. O trabalho que precisa de **placa de vídeo** (o WebGL do
   Blue Lock) roda numa tarefa "só interativa" (`schtasks /IT`, criada e apagada a cada trabalho) na sessão do console — ninguém logado lá =
   recusa e o trabalho roda aqui.
7. **Espera:** o agente segura a pergunta até 90 s (espera longa) e responde quando o `fim.json` aparece.
8. **Busca atômica:** o produto vem para `.pc_am-<id>` ao lado do destino, **cada arquivo conferido por tamanho e sha256 contra o do am**, e só
   então vai ao lugar com `os.replace`/`os.rename`. Qualquer falha apaga o temporário: nada pela metade aqui.
9. **Diário:** `atividade.registrar(<fábrica do trabalho>, inicio|ok|log, ..., etapa="pc_am", ref=<id>)` — `arena` para o duelo, `estudio`
   (canal `bluelock`) para o Blue Lock, `pc_am` para os testes. Nunca `erro` (o `erro` dispara a apuração automática).

**Queda segura (o que cai para cá e o que não):**

| O que aconteceu | O que acontece |
|---|---|
| chave desligada | aqui, sem tocar no am |
| SSH não conecta / saúde ruim antes de lançar | nova tentativa por até 45 s (a rede pisca 20–40 s às vezes); depois **aqui**, com UM aviso no Telegram por queda (`%LOCALAPPDATA%\neural-fights\pc_am\estado.json`; a volta zera). Com a queda já conhecida, cai na hora. A medição (`--forcar-am`) não roda aqui nem avisa: sai com rc 2 |
| am ocupado | espera `espera_da_fila_s`; depois aqui |
| a rede cai **depois de lançado** | **não** roda aqui (duplicaria o trabalho): insiste até o prazo + 3 min; só então é falha |
| o trabalho falha lá (rc, produto faltando, sha256 diferente) | `FalhaNoAm` com o motivo e o fim do log; na produção (`cair_na_falha=True`, o padrão) roda aqui também; na medição, erro |

O transporte é `TransporteSsh` (ssh/scp com a chave, `CREATE_NO_WINDOW`). Parâmetro grande demais para a linha do CMD de lá (8191) vai por
arquivo. Os testes (`random_builds/tests/test_pc_am.py`, 22) trocam só o transporte por cópia de arquivo e rodam o `lado_am.py` **de verdade**
numa pasta temporária (`PC_AM_BASE`, `PC_AM_LANCAR=popen`): caso zero, am fora (um aviso por queda), am ok, falha lá sem nada aqui, produto
corrompido recusado, sem produto, prazo, ocupado, piscar antes e depois de lançar, bundle + diff com git de verdade, o duelo trazido virando o
próximo número com os caminhos trocados.

## 3. Os trabalhos e como ligar

```
python -m builds.pc_am saude                       # o am responde? disco, memória, CPU, quem está rodando
python -m builds.pc_am chaves                      # o que está ligado
python -m builds.pc_am ligar duelo                 # / desligar duelo   (mexe no config/pc_am.json, que é versionado)
python -m builds.pc_am preparar                    # põe os dois clones no commit daqui e instala (aquecimento)
```
(de dentro de `random_builds\`, ou de qualquer lugar com o workspace instalado.)

| Trabalho | Chave | Comando | O que volta |
|---|---|---|---|
| Suítes de teste | `testes` | `python -m builds.pc_am testar-no-am <pasta> [-- args do pytest]` (`coordenador`, `remoto`, `tests`, `random_builds`, `historias`, `bluelock`...; as de projeto rodam de dentro da pasta, como no `testar.py`) | o log e o placar; rc do pytest (0/1/5 são resultado, não falha do am) |
| Duelo da geração | `duelo` | sozinho, pela `noite` (`_duelo_de_verdade`), ou `python -m builds.pc_am duelo [--p1 --p2 --seed --arena --preview]` | `outputs/duelo_XXXXX` inteiro, com o **próximo número daqui**, caminhos do JSON trocados para os daqui, luta registrada no **ledger daqui** |
| Gravação do Blue Lock | `bluelock` | `python -m builds.pc_am bluelock-gravar -- <os mesmos argumentos do bluelock.gravar>` | o mp4 e o json na pasta do `--saida` daqui (o `arquivo` do json corrigido) |

**Chaves em 26/10/2026 (`config/pc_am.json → trabalhos`):** `testes` **LIGADA**, `bluelock` **LIGADA**, `duelo` **DESLIGADA**. Ligar testes e
Blue Lock é seguro: não mexem no estoque do canal, e com o am fora/ocupado/em janela rodam aqui como sempre (o caso zero está no teste). O
`duelo` fica desligado porque afeta o estoque publicável e a prova que o liga (o duelo do am igual ao daqui: `fight.json`/`edit_plan.json`
sem diferença, mesma capa e mesmo áudio, seção 4) foi feita em 19/10 com o código de antes de ~100 commits e **não pôde ser refeita: o am
está desligado**. Quando o am ligar: `python -m builds.pc_am duelo --forcar-am` (mede e compara com `main.py duelo` do mesmo par/semente) e,
passando, `python -m builds.pc_am ligar duelo`.

**O duelo, em detalhe.** O par e a semente são escolhidos **aqui** (`rodizio.escolher_par` com o ledger daqui, a mesma conta do
`controller.duelo`); o am roda `main.py duelo --p1 --p2 --seed`. As entradas que o duelo lê e o git não tem (levantado lendo o caminho do
`main.py duelo`): `personagens.json` e `armas.json` do runtime (o do pacote tem outros 64 nomes), `runtime\sounds\` (mudam a cauda depois do
K.O.), `outputs\_arena\ledger.json` (cartel, revanche, título vão para o `fight.json`), todos os `generation_*\insercao.json`
(`vencedor_gerado`), a arte dos dois lutadores (capa) e `assets\music\`. O que sobrou lá de outra vez é apagado (espelho). Com o am fora, o
mesmo `controlador.duelo(p1, p2, seed)` roda aqui, com o mesmo par e semente. Não precisa de rede nem de login (o duelo não narra).

**O Blue Lock, em detalhe.** O clone do am vai ao commit do **espelho daqui** (`E:\BLUE-Lock-project`, só leitura; o código vai por
bundle, o am não fala com o GitHub). Lá o gravador roda com `--forcar` (no am não há publicação nem LoL para respeitar) e `--espelho C:\nf\BLUE-Lock-project`.
**Precisa da GPU:** na sessão 0 do SSH o Chrome só tem SwiftShader — 10 s de partida levaram **913 s**. Na sessão do console (tarefa `/IT`), o
ANGLE pega a **R5 220 por D3D11** e os mesmos 10 s levam 55 s. `--software` força a sessão 0.

**Ainda não ligado no mecanismo:** `bluelock.fabrica`/`bluelock.formatos` não estão no ramo `refactor/arquitetura` (estão no WIP parado de
19/10, ramo `worktree-agent-a5bf20c8a149fe832`, commit `d542b2a`). Quando entrarem, o trabalho é igual ao `bluelock_gravar`: `python -m
bluelock.fabrica --n N --pasta <trabalhos/id/saida>` lá, a pasta volta para cá (`modo_destino="arquivos"`), na sessão do console.

## 4. Medido em 19/10/2026 (mesma entrada nos dois)

Este PC estava carregado (outras sessões, histórias e o harness do Blue Lock rodando: CPU 82–100%); o am, ocioso.

| Trabalho | Aqui | No am (só o trabalho) | No am, ponta a ponta |
|---|---|---|---|
| `pytest coordenador` (596 testes) | 204 s (595 ok) | 38–77 s (595 ok) | 57–119 s |
| `pytest tests` de `random_builds` (2153) | (não medido aqui — ver §6) | 146 s, 2127 ok, 26 pulados (Godot, Digen) | 153 s |
| Duelo `Aldric Solulacern × Elowen Emberdoen`, seed 1456749669 (15,1 s de luta, celular + normal + capa) | 184 s | 134–173 s | 321 s na 1ª (com 6,5 min de envio pasta a pasta antes do zip e um piscar da rede); ver a linha seguinte |
| Duelo, mesma entrada, código final | — | 122 s | 518 s: preparo 10 s, trabalho 122 s, e **6,5 min trazendo os 41 MB** com a rede caindo (scp recomeça do zero) |
| Blue Lock 10 s, 1080×1920, 3×3, semente 42, `face59d` | 111 s (HD 4600, 20/10 00:00) | 55 s (GPU, sessão do console) / 913 s (SwiftShader, sessão 0) | 94 s (saúde 7, código 4, trabalho 57, trazendo 26) |

**O duelo do am é o mesmo duelo.** Contra o feito aqui com a mesma entrada: `fight.json` e `edit_plan.json` com **0 diferenças** (depois da
troca de caminho), a mesma `luta`, a mesma capa (sha256 igual), o mesmo áudio (md5 da trilha decodificada igual). Os quadros do vídeo não
são bit a bit iguais (PSNR médio 35 dB) — **mas dois duelos feitos AQUI com a mesma entrada também não são** (o `duelo_00141` de produção ×
o refeito aqui: os mesmos 35 dB, os mesmos 45 de 357 quadros idênticos no 16:9): o desenho do pygame tem efeito visual sem semente, e a luta
(que é determinística) não depende dele. Quadro a quadro, lado a lado, é a mesma cena. Provas em `E:\tmp_pytest\pc_am_prova\`
(`duelo_am`, `duelo_aqui`, `lado_a_lado.png`, `bl_am_gpu*.mp4/json`).

**O Blue Lock do am:** duas gravações lá com a mesma entrada deram os **mesmos 16 eventos** e o mesmo placar; GPU `ANGLE (AMD Radeon R5 220
Direct3D11)`. E a gravação feita AQUI com a mesma entrada (20/10 00:00, HD 4600) deu **os mesmos 16 eventos**, nos mesmos tempos — mesmo com o
Chrome 155.0.8059.85 lá e .82 aqui (o Blue Lock só promete determinismo "no mesmo runtime"; vale reconferir quando o Chrome de um dos dois
atualizar).

**A rede é o gargalo, não a máquina.** Medido com um ping a cada 10 s (`192.168.0.9`, pela LAN, fora do Tailscale): com o am ocioso, nada
perdido; com 4 processos queimando CPU lá, 0 de 97 perdidos; **durante o duelo e a cópia dos 41 MB, 4 quedas de 10–40 s** (23:30–23:34). O
Ethernet do am está com "Energia Eficiente Ethernet" e "Power Saving Mode" **ligados** e este PC está no Wi-Fi. **Não mexi** em nada disso
(sem prova da causa); se as quedas continuarem, o primeiro teste é desligar os dois no adaptador do am (`Set-NetAdapterAdvancedProperty -Name
Ethernet -DisplayName 'Energia Eficiente Ethernet' -DisplayValue Desactivado`, idem `Power Saving Mode`), e o segundo, este PC no cabo. O
Defender do am (o processo que mais gastou CPU lá) varre cada arquivo novo; uma exclusão de `C:\nf` é decisão do Adrian.

## 5. Armadilhas (todas apareceram nesta noite)

- **A rede pisca.** Várias vezes o `connect` do SSH deu timeout por 20–40 s (com ping ok antes e depois; o Tailscale às vezes vai pelo relay
  `sao`, às vezes direto pela LAN). Daí a paciência antes de lançar, a insistência depois de lançado e a espera longa. Na 1ª prova o piscar
  aconteceu com o duelo rodando lá, o código de então tratou como "am fora" e **refez o duelo aqui, dentro da janela das postagens** — por isso
  existe o teste `test_queda_depois_de_lancado_nao_roda_aqui_de_novo`.
- **pythonw não serve de executor na sessão 0:** sem console, não há handles de stdin/stdout, e todo `subprocess` que os herda morre com
  `WinError 6` (2 testes do coordenador caíram assim). O executor é `python.exe` (na sessão 0 não aparece janela para ninguém); na sessão do
  console é `pythonw`, mas o `{PY}` do trabalho é sempre o `python.exe`.
- **A tarefa `/IT` não se apaga sozinha:** o executor, na sessão do console, tem o token filtrado do UAC; quem apaga é o lado do SSH, na
  pergunta do fim.
- **Commit que não está no GitHub** vai por bundle (é o caso enquanto o `refactor/arquitetura` daqui estiver à frente do `origin`).
- **Arquivo sem `git add` não vai.** Para testar no am código novo, `git add` antes (o diff de `HEAD` leva o que está no índice).
- **Rodar de uma worktree**: o `neural_fights` instalado aponta para `E:\projetos`; use `PYTHONPATH=<worktree>\random_builds;<worktree>`.
  O am sempre recebe o commit + diff da árvore de onde o comando roda.
- O agente do am (`lado_am.py`) é só biblioteca padrão: ele precisa funcionar antes de o clone estar no commit certo.
- Os comandos de prova escrevem no **diário de verdade** (`atividade.jsonl`) com `etapa=pc_am`.

## 6. O que fica neste PC, e por quê

| Fica aqui | Por quê |
|---|---|
| Publicação (`postar`, YouTube API e web, TikTok), métricas do Studio | contas, credenciais e perfis de navegador logados; regra do pedido |
| Histórias (roteiro no LLM, imagens, parecer) e o worker de identidade (PicassoIA/Digen) | dependem de navegador logado nas IAs |
| Roleta/build (`generate-video`) | escreve no banco vivo e enfileira a identidade daqui; levar ao am pede trazer o banco de volta — candidato para depois, com o mesmo mecanismo |
| Palco (Godot) | chave desligada; o Godot não foi instalado no am |
| App, bot, carteiro, coordenador, Vila, vigia do Blue Lock | são os serviços desta máquina (o vigia lê o espelho daqui) |
| A suíte `random_builds` como verificação antes do commit desta sessão | rodou NO AM (2127 ok); aqui rodaram só `test_pc_am` + as suítes da geração (165 ok), para não pôr 5 min de carga neste PC à noite |

## 7. A fila sem descanso (`builds/pc_am/fila.py`, 20/10/2026)

Pedido do Adrian: "quero que você coloque peso mesmo nesse PC, não dê um minuto de descanso para ele." Um laço mantém o am com **um trabalho
pesado por vez** e, ao terminar um, pega o próximo nesta ordem:

| # | Fonte | Quando produz | Teto / guarda |
|---|---|---|---|
| 1 | **Pedido explícito** (`%LOCALAPPDATA%\neural-fights\pc_am\pedidos.json`) | sempre que houver | — |
| 2 | **Duelos** para o estoque | estoque da publicação (`noite.contar_estoque()["duelo"]`) abaixo do teto | `dias_de_estoque_duelo` × `consumo_duelo_por_dia` = 14 × 6,25 = **88** (o consumo é o da geração nova, `a346e118`, só lido) |
| 3 | Formatos do **Blue Lock** | só quando `bluelock.formatos` existir no ramo (hoje está no WIP `d542b2a`): até lá a fonte passa com o motivo | `teto_bluelock_por_formato` (10), para quando a fonte for ligada |
| 4 | **Voz das roletas** `generation_00126..00185` feitas com o SAPI | voz.wav da janela do 403 (12/10 01:00 a 19/10 18:00), **não publicadas** como build (ledger `publicados`), sem `voz_refeita.json` | as 51 da decisão `builds/voz-do-windows-12-a-19-10` (35 ainda não publicadas em 19/10); 2 tentativas por roleta |
| 5 | **Ramos do Blue Lock** (`bluelock.ramos.VigiaDeRamos` com o `npm test` no am) | no máximo uma olhada a cada `ramos_a_cada_min` (30) | o vigia só testa a ponta ff com CI não vermelho |
| 6 | **Suítes inteiras** no commit atual (as do `testar.py` + `npm test` do Blue Lock) | uma vez por commit, de novo depois de `repetir_suites_h` (12) | placar em `pc_am\suites.json` |

**A voz refeita** (`builds/pc_am/refazer_voz.py`, roda no am): manda a pasta da roleta (sem os finais nem os segmentos), as reações e a trilha;
lá apaga `voz.wav`/`voz.hash`/`voz_palavras.json`, `rerender(refazer_edicao=True)` (as falas são medidas de novo e o plano cresce até a voz
caber) e **só aceita o edge**: se aparecer `.wav` novo no cache de voz (o SAPI é a reserva do sintetizador) sai com rc 7 e nada volta. O que
volta (finais, plano, voz, legendas) entra na pasta daqui um `os.replace` por arquivo, os `.mp4` por último, com os caminhos do am trocados, e
a roleta ganha `voz_refeita.json`.

**Guardas:** a fila nunca roda nada aqui (`cair_para_aqui=False` em tudo); disco do am abaixo de `disco_minimo_am_gb` (15) = **para e avisa**;
disco daqui abaixo de `disco_minimo_aqui_gb` (10) = só o que não traz arquivo; o que voltou é apagado no am; fonte que falha
`falhas_para_descansar` (3) vezes seguidas descansa `descanso_depois_de_falhas_min` (60); **avisos no Telegram, um por episódio**: am fora,
disco do am, disco daqui, e parado **sem motivo** por mais de `aviso_parado_min` (15) — "nada útil" (tudo em dia) e "fila desligada" não são
alarme. A saúde do am (disco, memória, CPU e temperatura, se a placa informar via ACPI) vai para o estado.

**O estado** (o app e a Vila leem): `%LOCALAPPDATA%\neural-fights\pc_am\fila.json` — `texto` ("o am está fazendo duelo para o estoque (21/88)
desde 10:00; fila: …"), `fazendo`, `ultimo`, `pedidos`, `contas` (duelos estoque/teto, voz faltando), `am` (saúde), `motivos` de cada fonte;
o histórico em `fila_historico.jsonl`.

**A geração daqui deixa os duelos para o am** (`noite._trabalhar`): com a chave `trabalhos.duelo` ligada **e** a fila viva (estado de menos de
10 min, am não fora, disco do am ok), a noite não gera duelo ("o PC am repõe o estoque"). Fila parada ou am fora = a noite gera aqui, como
sempre. Do mesmo jeito, o `npm test` dos ramos **daqui** (`bluelock.ramos._pode_pesado_aqui`) sai de cena com a fila viva.

**Comandos:**
```
python -m builds.pc_am fila status            # o texto e o estado
python -m builds.pc_am fila passo             # um passo agora (respeita fila.ligada)
python -m builds.pc_am fila rodar             # o laço (é o que o serviço roda)
python -m builds.pc_am fila ligar|desligar    # config/pc_am.json -> fila.ligada
python -m builds.pc_am pedir duelo --p1 X --p2 Y [--seed S]
python -m builds.pc_am pedir testar coordenador [-- args do pytest]
python -m builds.pc_am pedir voz generation_00150
python -m builds.pc_am pedir bluelock -- --saida E:\x\lance.mp4 --segundos 20
```

**Como ligar (pronto e DESLIGADO):**
1. `python -m builds.pc_am ligar duelo` (a chave do duelo; sem ela a noite continua gerando aqui) e `python -m builds.pc_am fila ligar`.
2. O serviço `am` do coordenador (o laço `fila rodar` como serviço `sob_demanda`) **NÃO foi registrado** na integração de 26/10 (o ponto 9 não
   pede a fila 24 h): para a fila, rode `python -m builds.pc_am fila rodar` à mão. Registrar = um bloco `am` em `coordenador/servicos.json`
   (comando `-m builds.pc_am fila rodar`, `sob_demanda`) e `am` nas `choices` do `reiniciar` — junto com os testes do coordenador.

## Contratos com outras partes

| Contrato | Quem manda | Quem consome |
|---|---|---|
| `random_builds/config/pc_am.json` (as chaves) | o orquestrador liga depois de conferir | `builds.pc_am`, a `noite` |
| `outputs/duelo_XXXXX` vindo do am | `builds.pc_am.trabalhos.duelo` | Publicação (o mesmo catálogo de sempre) |
| `C:\nf\` no am | esta parte | ninguém mais |
