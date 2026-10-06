# Passagem de bastão — 06/10/2026 18:43 (renovacao)

Leia ANTES de agir. A NOTA é do chat anterior; o RETRATO é medido agora do disco.
Regras de operação: `CLAUDE.md`. Equipe: `docs/agentes/EQUIPE.md`.

# NOTA do chat anterior

Chat de 05/10 22:50 → 06/10 18:45 (orquestrador). Renovado por ser longo (~20 h). Entregou: Ateliê de sprites modulares (guarda-roupa + recortador + provador), cofre do Obsidian no celular, títulos das histórias, PicassoIA fora, conversa do app, e a publicação à prova de rede/sobreposição/duplicata.

## Em andamento — terminar PRIMEIRO
1. **Publicação, defeito BAIXO aberto no f79a894 (ficha .bak):** a `.bak` da ficha da trava (`%LOCALAPPDATA%\neural-fights\locks\postar__rodada.dona.json.bak`) fica sempre uma gravação atrás e guarda o último `em_voo` "clicou" JÁ CONFIRMADO; se a principal faltar/ficar ilegível, a rodada seguinte marca "a conferir" um vídeo que já saiu (alarme falso + Telegram). Não bloqueia nem duplica. Conserto sugerido pelo conferente: no `finally` do `_em_voo` (pouso) gravar a ficha DUAS vezes (a .bak também fica `em_voo: null`), OU ao decidir pela .bak não marcar se o ledger já tem o alvo naquele destino com `quando ≥ voo.desde`. Caso espelhado mais raro: principal estragada no "clicou" e .bak em "escolhido" → pode subir de novo. Provas: `E:\tmp_pytest\conf_pulso\f79_*.txt`. Agente `publicacao`; grave fora das janelas (post-12 a post+18) e passe pelo `conferente`.
2. **Conferir a 1ª noite com a publicação nova (20:37, 21:37, 22:37, 23:37, 00:37 são de 60 min):** commits 4e8df2b → 0b5b6a9 → 65dc781 → 9025da2 → 78112e5 → f79a894 em `ferramentas/postar.py`. Olhar no `outputs/postar.txt`/ledgers: nada duplicado, nenhum horário bloqueado por "rodada anterior", "volta final" quando a rede cai, ficha com `em_voo: null` no fim. `python -X utf8 ferramentas/postar.py --ver` (EXIT 0).
3. **Estoque de histórias baixíssimo** (2 limpas, ~57 retidas/38 consertadas às 16h; piso 20). Sem PicassoIA a fábrica faz ~1 parte/h. Decisão dele: **"duas histórias ao mesmo tempo, uma em cada gerador"** (`historias/imagens-dois-geradores-juntos`) — AINDA NÃO FEITA (o trabalhador `pedido-4d99bb1b-1` terminou sem entrega). Agente `historias`.
4. **Builds sem imagem:** o PicassoIA está PAUSADO nos builds (`random_builds/main.py identity pausar --provedor picasso`); as imagens de identidade (character/weapon/character_weapon) estão fixas no PicassoIA em `random_builds/builds/identity/slots.py:51`. Tarefa Codex pronta e NÃO rodada: `builds-sem-picasso` (`python -m remoto.delegar rodar --id builds-sem-picasso --fundo`; spec em scratchpad da sessão anterior — recrie se sumir). Estoque de builds ~56 (5,6 dias).
5. **Decisões do Adrian ainda NÃO implementadas** (trabalhadores do servidor ficaram "rodando"/parados sem entrega): `publicacao/youtube-caiu-depois-do-tiktok` = **subir a MESMA parte no YouTube** (`pedido-637b4d56-1`; tem de passar pela porta `_subir_parte_no_youtube` e respeitar a marca `[pedaco]`); `historias/titulo-marca-no-meio` = **tirar a marca da frente** nos 5 títulos com a série no meio (`pedido-936b3f89`); `app-e-bot/conversa-pergunta-livre` = **o modelo decide** entre conversa e pedido. Confira o estado de cada `pedido-*` com `python -m remoto.delegar ver --id X` e limpe os mortos.
6. **Re-render das partes com o título antigo queimado** (h54, h58, h55 p05, h59 p01, h53 p02…): plano na resposta do agente historias de 06/10 ~00:08 (comando `python main.py video historia_000NN --parte N` em `historias/`, de dia, fora das janelas). Parte já pode ter sido refeita pelo reparo/lote — conferir o mtime antes.
7. **Ressalvas do conferente no Ateliê (não bloqueiam):** prévia presa ocupa ~37% em pé e cobre o topo da folha do Godot; miniaturas da galeria mostram o gabarito inteiro (olho ~15 px); brilho a <16 px do olho entra no recorte e encolhe o olho; o modo do par fica lembrado entre folhas; "Mandar para" começa em "Sombra" com 83 opções; `test_app_recortador_tela::provador_preso[dark]` instável (1 em 3).

## Pedidos do Adrian ainda abertos
- Sprites: "quero vários olhos aleatórios … igual aqueles jogos de colocar roupa" e "recortar cada sprite da spritesheet … só verde ou magenta" — **ENTREGUE** (merge 988fd01 + baaa5a6, casca v52). Mostrar como usar se ele pedir; ele cria as imagens. O palco Godot ainda NÃO é o visual publicado (espera o nó `palco-duelo-ab`).
- Obsidian: "quero que o Obsidian sirva para organizar minhas ideias e entender meu projeto, arquitetura intuitiva para um humano" — entregue (cofre `E:\Obsidian\Neural Fights`, Syncthing pareado com o celular; `ferramentas/obsidian.py` + coordenador atualizam 04/05/📊 Agora). Ele achou o plugin **Copilot (Logan Yang)** — próximo passo possível, precisa de chave de API (custo).
- "Visão macro do processo das histórias" → hoje está no cofre (03 Entender o projeto / Fluxo das histórias + 📊 Agora). A tarefa Codex `fluxo-historias` (números por etapa) NÃO rodou.

## Decisões e regras novas deste chat
- Grimório: `geral/picasso-fora-da-roda` = tirar; `builds/sprites-modulares-painel` = modular; `builds/sprites-modulares-9-respostas` = aceito; `builds/sprites-guarda-roupa` = sorteio fixo por lutador + provador; `builds/sprites-recortador` = só verde/magenta; `builds/recortador-par-de-olhos` = **separar** (já é o padrão); `app-e-bot/obsidian-no-celular` = Syncthing; `historias/imagens-dois-geradores-juntos` = duas histórias ao mesmo tempo; `historias/titulo-marca-no-meio` = tirar; `publicacao/youtube-caiu-depois-do-tiktok` = mesma parte; `app-e-bot/conversa-pergunta-livre` = modelo decide; `geral/modo-de-trabalho` = paralelo até 3.
- Capacidade: `orquestrador/config.json max_paralelo=3` e `delegados/config.json delegados_paralelo=3` (subidos às 04:35 com o "tudo permitido" dele).
- Memórias novas: `falar-com-o-adrian` (responder primeiro o que ele perguntou, sem jargão — ele reclamou "o orquestrador não está falando comigo") e `grimorio-gera-trabalhador-duplicado`.

## Armadilhas encontradas
- **Toda resposta no Grimório vira trabalhador do servidor** que refaz o trabalho do chat (5x nesta noite). Depois de `decisoes responder`, e quando o Adrian responde algo já feito: `delegar listar | grep pedido-` → `parar` + `limpar`.
- **Reiniciar o coordenador:** `schtasks /End` + `/Run` NÃO mata o python. Funciona: `taskkill /PID <python do coordenador> /F` (sem /T) e `schtasks /Run /TN NeuralFights_coordenador`; conferir `python -m coordenador status` (pid novo, versão = HEAD).
- `delegar rodar --fundo` pode morrer no lançamento ("Resource deadlock avoided") deixando a tarefa em "criado" — conferir `delegar ver` 30 s depois. `delegar corrigir --texto` recebe CAMINHO de arquivo. O Codex esgotou a janela de 5 h às 06:3x (volta em ~5 h); agentes Claude cobriram.
- **Suíte crua escreve no diário de produção** (`%LOCALAPPDATA%\neural-fights\atividade.jsonl`): sempre `NEURAL_FIGHTS_RUNTIME_DIR` + TEMP no E:. Em 06/10 25 linhas falsas foram removidas (backup `atividade.jsonl.antes-limpeza-20261006`).
- **Disco E: saturado** deixa render "parado" (era grep -r órfão + suítes); antes de achar que travou, medir disco.
- **Rede do PC cai** (23:37, 00:37, 06:37 de 05–06/10, erro 10053 / página em branco). Causa não medida (suspeitos: Syncthing desde 03:26, cliente da Riot). A publicação agora aguenta (volta final).
- Codex trabalha sem tela: entrega "pronta" sem prova visual; o conferente reprovou TODAS as primeiras versões (anexar quebrado, câmera no lugar da galeria, paridade quebrada, rosto duplo, encaixe na zona errada). Nunca mostrar ao Adrian sem a passada do conferente no caminho real.
- `python -m neural_fights.tools.manifesto_sprites -h` trata `-h` como caminho de saída (gravou `E:\projetos\-h`); `importar-antigas` re-copia o capacete apagado — não rode de novo.
- Sobras que pedem administrador: `E:\projetos-wt\_lixo_codex\*` (comando takeown/icacls no `delegar limpar`).

# RETRATO (medido agora)

## Git
- ramo: `refactor/arquitetura`
- **mudanças NÃO commitadas (4)** — confira antes de qualquer coisa:
  - `M docs/handoff/ATUAL.md`
  - `M docs/handoff/NOTA.md`
  - `M palco/biblioteca/LICENCAS.md`
  - `M palco/biblioteca/efeitos/objetos/projetil/fogo.tscn`
- últimos commits:
  - f79a894 postar: ficha da trava duravel — fsync no .tmp antes da troca e a anterior guardada em .bak; principal vazia/NUL decide pela .bak, so bloqueia se as duas nao responderem — defeito do conferente no 78112e5
  - 78112e5 postar: ficha invalida nao esconde o voo (voo inteiro pousa; "nao da para saber" = nao publica), voo em "escolhido" nao pousa (preso por teste), upload do youtube_web fala a cada 60 s — pontos do conferente no 9025da2
  - baaa5a6 sprites: migrar_variantes leva tambem o historico da peca APAGADA para v01 (o capacete do Berserker no disco real perdia o Desfazer); migracao rodada: pele comum -> v01/base.png (md5 igual), historico do capacete -> v01/base.png.historico; 46 testes de sprites verdes
  - 988fd01 merge: sprites-integracao (guarda-roupa de variantes vNN, recortador verde/magenta, Provador, sorteio estavel Python=Godot, folha do Godot com cor; casca v52) — aprovado pelo conferente
  - 9025da2 postar: voo que a dona deixou no ar vai para "a conferir" antes da escolha, pulso decide quem esta pendurado, descendentes so nascidos depois do pai, ficha validada — achados do conferente no 65dc781
  - 6fd8362 app: recortador encaixa no DESTINO ao mandar, pares de olhos (separar/girar/vista-de-cima), borda sem franja, Provador com o lutador preso a vista, Ver no Godot 150 s (casca v52)
  - 65dc781 postar: dona pendurada da trava da rodada morre (70 min, so de horario anterior, nunca o --tudo), aviso diz quem segura, margem tambem nos passos extras, tarefas com limite de 2 h — achados do conferente no 0b5b6a9
  - bfb6b35 sprites: sorteio de variantes estavel (rendezvous + fmix32) igual no Python e no Godot; folha do lutador com a cor dele e titulo em 2 linhas
  - 79f58c2 decisão(builds): lida — Recortador: par de olhos desenhado de frente gerou tarefa pedido-b288c8fe
  - 09d10ad decisão(builds): Recortador: par de olhos desenhado de frente → Separar o par e pôr cada olho no seu lugar (recomendado)
  - 0d259c5 decisão(builds): nova — Recortador: par de olhos desenhado de frente
  - 0b5b6a9 postar: rodada nao encosta no horario seguinte (margem de 20 min, reposicao 25 / volta 40), trava entre processos e guarda de um por horario falhando FECHADA — achados do conferente no 4e8df2b

## Trabalhadores do servidor (delegados)
- `pedido-7c727778-1`: orquestrador / codex / rodando (O Adrian respondeu no Grimório (builds/digen-parede): «Parede de planos do Digen)

## Mesa, fila e Grimório
- agentes ativos na Mesa: ninguém trabalhando
- fila (1):
  - 1. 6a229e63  [builds] Corrente F4–F6: arte pela esteira, som e A/B (o rework que o Adrian pediu em palco-duelo-ab)
- Grimório: todas as respostas lidas

## Serviços e máquina
- coordenador: pid 12716, código f79a894
  - app: rodando
  - bot: rodando
  - carteiro: rodando
  - vila: rodando
- Claude: Claude liberado desde 01/10 13:30 pelo app (Android)
