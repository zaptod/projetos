# Histórias

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
   assistir. Barrado vai ao `reparo`; aprovado é estoque.

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
`agenda.provedores_do_roteiro()` quando `llm.json` falta. O ChatGPT não assiste vídeo
nesta máquina (conta free: o mp4 entra como "Arquivo" opaco) — cai na folha de
contato, mosaico de 12 quadros.

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
- **Gatilho "séries < 5"**: `agenda.falta_serie()`. 10 horários ÷ teto de 2 partes da mesma
  história por dia = `series_minimas = 5`. Com o teto de partes cheio (20) e menos de 5
  séries prontas, a criação é liberada até um **teto duro** de 26 — sem isso o freio conta
  partes e o dia fica com horário vazio por falta de variedade.

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

## 6. Estado de hoje (27/09/2026, ~19h35, medido)

- **22 partes aprovadas**; teto 20 (10 horários × 2 dias de gordura), teto duro 26 →
  **criação freada**. **0 barrados**, **0 incompletas**. **6 séries**
  (`historia_00031`…`00036`), mínimo da grade 5, `falta_serie` = `None`. Por tipo:
  **favela 10, normal 7, babaca 5** → o próximo a nascer é **babaca**.
- 34 histórias no disco, 200 mp4 de celular, ledger com 320 linhas (158 YouTube /
  162 TikTok). Criadas hoje: `00035` (babaca, 3) e `00036` (favela, 6).
- **Aviso de variedade** em todas as rodadas de postagem de hoje: "só 4 série(s)
  elegível(is) hoje, e o dia precisa de 5 — falta VARIEDADE, não partes" (150 ocorrências
  em `outputs/postar.txt`). Há 6 séries, mas o teto de 2/dia e a ordem das partes deixam 4
  elegíveis; o aviso é do `postar.py`, o conserto é na agenda **desta** parte.
- **14 falhas de YouTube** no `postar.txt`, as 5 últimas iguais: `TimeoutError` em
  `#title-textarea #textbox`. Hoje às 18h a `historia_00032:celular:p04` saiu **só no
  TikTok** e não há linha de YouTube para ela no ledger.
- **7 vídeos INSISTENTES** em `outputs/_reparos.json` (teto de tentativas): partes de
  `00004`, `00005`, `00010`, `00011`, todas antigas, esperando decisão humana.
- 103 linhas "a IA reprovou, mas as rodadas de conserto acabaram; sai assim" — o veto da IA
  não é definitivo depois do teto de reparos; **não verificado** se é decisão dele ou efeito
  colateral. Pendente antigo, **não verificado** se ainda vale: a imagem fica ~6 s na tela e
  o ideal é 3–5 s (exigiria 45–60 imagens por parte).

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
