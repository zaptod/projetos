# Auditoria profunda — Roteiro e LLM das histórias — 12/10/2026

Fatia: `historias/contos/roteiro/**` e `historias/contos/llm/**` (6.320 linhas, 14 arquivos,
201 funções/classes lidas uma a uma). Só relatório; nenhum arquivo do projeto mudou.

Provas em `C:\Users\adrian\AppData\Local\Temp\claude\e--projetos\65fe1aa9-5965-4d18-9756-f332b198f269\scratchpad\`
(`_dubles.py` + `prova*.py`), rodadas de `historias/` com `TEMP=E:\tmp_pytest`. Runtime isolado:
`roteiro.OUTPUTS`, `gerar.OUTPUTS`, `cliente.RAIZ` e `PASTA_EM_BRANCO` apontam para
`E:\tmp_pytest\auditoria_llm_*`; o diário (`builds.atividade`) é um gravador em memória; a
página do navegador é um dublê de DOM; `time` anda em passos de 1 s. Nenhuma prova dubla a
função sob suspeita — só a página, o diário e o cliente de quem chama. As medições de
produção são leitura de `outputs/_logs/auto_*.txt` e dos `roteiro.json`/`biblia.json` do acervo
(72 histórias).

## Examinado

- `historias/contos/llm/cliente.py` — 50 funções/classes; chat no navegador (abrir, modelo, envio, espera, anexo, diário, trava de conta).
- `historias/contos/llm/seletores.py` — 5 funções + 4 mapas (ChatGPT, Gemini, DeepSeek, Grok); `encontrar`/`encontrar_oculto`/`resolver`.
- `historias/contos/llm/papeis.py` — 11 funções/classes; ordem de queda por papel, `evitados`, `ajustes`.
- `historias/contos/llm/probe.py` — 3 funções; despejo do DOM, `sessao_valida` (3 estados), `login`.
- `historias/contos/llm/texto.py` — 2 funções; limpeza de markdown/raciocínio e `e_recusa_enlatada`.
- `historias/contos/roteiro/gerar.py` — 22 funções/classes; conduz a conversa (bíblia, partes, revisão, coerência, retomada, queda de provedor).
- `historias/contos/roteiro/roteiro.py` — 48 funções; parser tolerante, títulos, detector de recusa no trecho, `salvar_serie`, listagens do rodízio, ids.
- `historias/contos/roteiro/serie.py` — 33 funções; moldes/tipos/rodízios, prompts (guiado e livre), `parse_biblia`.
- `historias/contos/roteiro/linguagem.py` — 7 funções; faixas `risco`/`pare` com borda de palavra.
- `historias/contos/roteiro/coerencia.py` — 7 funções; números/anos contra a ficha de FATOS.
- `historias/contos/roteiro/pertinencia.py` — 4 funções; fração de prompts em inglês.
- `historias/contos/roteiro/narrador.py` — 4 funções; voz por narrador/idade.
- `historias/contos/roteiro/modelo.py` — 5 funções; prompt-mestre do caminho manual.
- `historias/contos/roteiro/__init__.py` — 0 funções; marcador de pacote.

## Os fatos medidos, explicados pelo código

- **`[gemini] a troca de modelo falhou (TimeoutError)` 445x e `a historia vai sair em Gemini` 224x (06–08/10)**: é
  `cliente._tentar_modelo` (linha 309) engolindo o `TimeoutError` do `botao.click(timeout=8000)` /
  `inner_text(timeout=3000)` e `escolher_modelo` (185–199) tentando 3x por chat. As linhas estão
  dentro do laço de imagens do carteiro (`ias/carteiro.py:236` chama `escolher_modelo` a cada chat
  novo; trecho de 07/10 08:19–08:22: imagem gravada → troca falhou ×3 → ATENCAO → chat novo →
  imagem…), por isso a mensagem "a historia vai sair em" aparece até em pedido de imagem. Custo
  medido nos 3 dias: 210 casos, mediana **32 s por chat**, ~1,9 h de espera somada. O roteiro
  registrou "SEM confirmar o modelo" **1** vez no período e nenhum `roteiro.json` do acervo tem
  `NAO CONFIRMADO`. O que falta é o aviso (confirmado nº 1) e o custo repetido (nº 6).
- **Login caído errando dos dois lados**: já está coberto por `probe.sessao_valida` (3 estados,
  `headless=False`) e por `cliente.estado_da_pagina`/`conferir_sessao` (`deslogado` só com a tela
  de login, reconfirmada após 5 s). Não achei regressão; ver "Não confirmados" para o que sobra.
- **Resposta anterior lida em chat com vários turnos**: a âncora (`_JS_RESPOSTA`) resolve quando o
  nosso turno novo **está** no DOM. Quando a pergunta volta para a caixa **sem** entrar na
  conversa (o "devolvido"), em chat com turnos anteriores ela ainda devolve a resposta anterior —
  confirmado nº 2.
- **Raciocínio preso ("0 chars")**: `_responder_agora` aos 300 s e `_diagnosticar_calado`; o
  roteiro espera o prazo inteiro por desenho. Nos logs sobram 4 "espera estourou em 600s; uso o
  que ja veio" (30/09, 02/10, 03/10), todos no parecer/reparo, não no roteiro.
- **Recusa do LLM no título**: `gerar._titulo_aceito` + `roteiro.e_recusa_no_trecho` (05–06/10)
  cobrem o caso; nada a repetir.

## Confirmados (do mais grave ao menos)

### 1. Modelo forte não confirmado: nem diário, nem Telegram, nem queda de provedor — a história sai no Flash calada — gravidade: alta

- Onde: `historias/contos/llm/cliente.py:196` (`escolher_modelo`, o `self.log(... ATENCAO ...)`),
  `historias/contos/roteiro/gerar.py:510` (`gerar_serie`, só `log` + `modelo_llm = "NAO CONFIRMADO…"`),
  `historias/contos/roteiro/gerar.py:743` (`escrever_serie` não vê `modelo_confirmado`).
- O defeito: `escolher_modelo` "nunca levanta" e só escreve no `log`; `_registrar_turno` (o único
  caminho para `atividade.jsonl`/Telegram) é chamado apenas por `perguntar`. Quem decide que o
  Flash é o problema de qualidade (o Adrian) nunca fica sabendo que a história está nascendo
  nele: a ordem de queda (`deepseek → chatgpt → gemini`) não é acionada por modelo fraco, e a
  faixa segue escrevendo 6 partes e 84 imagens em cima do texto fraco (o mesmo caso da
  `historia_00004` de 09/09).
- Quando acontece: o menu de modelo do Gemini não responde (timeout no clique, menu que não abre,
  cota do Pro esgotada → só Flash/Flash Lite no menu — 1 linha "-> 3.5 Flash Lite" em 07/10 16:00).
- Prova: `python prova1_modelo.py` →
  ```
  retorno de escolher_modelo: ''   modelo_confirmado: False   cliques no botao de modelo: 3
  [gemini] ATENCAO: nao consegui por no modelo forte depois de 3 tentativas; a historia vai sair em modelo desconhecido.
  registros no diario (atividade.registrar): 0    excecao levantada: nenhuma
  ```
  Produção: 224 linhas ATENCAO em 06–08/10, 0 linhas `llm.*` de aviso no diário por isso.
- Conserto sugerido: `escolher_modelo` registrar `aviso` no diário (e `erro` quando o papel é
  `roteiro`), e `gerar_serie`/`escrever_serie` tratarem `modelo_confirmado=False` como queda para o
  próximo provedor — decisão do Adrian se o Flash pode escrever ou não (hoje não há nó para isso).

### 2. Pergunta devolvida à caixa em chat com turnos anteriores: a resposta do turno ANTERIOR volta como resposta desta pergunta — gravidade: alta (sem ocorrência medida no acervo)

- Onde: `historias/contos/llm/cliente.py:501-509` (`_envio_devolvido`: "SO SEM CONVERSA NA TELA"),
  `cliente.py:963-969` (`_resposta_nova`: ancorado ⇒ aceita texto igual ao anterior),
  `cliente.py:1150-1158` (`esperar_resposta` só consulta `_envio_devolvido` quando `calado`).
- O defeito: o chat do roteiro tem vários turnos (bíblia, partes, revisões). Se o envio "confirma"
  (o campo esvaziou um instante — `_confirmou_envio`, 592) e o site devolve a pergunta à caixa sem
  criar turno (o "Algo deu errado (1155)" do parecer, a volta ao início de 14/09), o último
  `user-query` do DOM é a pergunta anterior, `_JS_RESPOSTA` devolve a resposta anterior
  **ancorada**, o texto não é "calado" (milhares de chars) e a espera devolve em ~3 s a parte N
  como se fosse a parte N+1 (ou a revisão). `pertinencia` não pega (prompts em inglês) e a parte
  duplicada vira vídeo.
- Quando acontece: a devolução da pergunta pelo site a partir do 2º turno de um chat.
- Prova: `python prova2_devolvido.py` →
  ```
  _envio_devolvido() com turno anterior na tela: False
  esperar_resposta devolveu em 12.0 s (relogio falso)
  texto devolvido == resposta do turno anterior: True
  log: [gemini] resposta pronta: 1842 chars em 11s
  ```
  Acervo: 0 partes com narração igual à anterior em 72 histórias; 3 "o envio voltou para a caixa"
  nos logs, todos no parecer (chat novo, onde a detecção funciona).
- Conserto sugerido: `enviar` guardar o número de `turno_usuario` antes do envio e `esperar_resposta`
  exigir **turno novo** (contagem +1 ou texto do último turno == prompt) antes de aceitar qualquer
  resposta; sem turno novo em `devolvido_apos_s`, levantar "envio devolvido".

### 3. `salvar_serie` grava `roteiro.json` em cima do arquivo, sem temporário: morte no meio = história some em silêncio — gravidade: média

- Onde: `historias/contos/roteiro/roteiro.py:930` (`salvar_serie`), `roteiro.py:1137`
  (`listar` engole `ValueError`), `gerar.py:714-718` (`_situacao` → "nova").
- O defeito: `open(..., "w")` + `json.dump` com `indent=2` (dezenas de escritas pequenas). O
  arquivo é regravado **a cada parte** e **a cada retomada**; `registrar_queda` (942-945) já usa
  `tmp + os.replace`, `salvar_serie` e `_gravar` (biblia.json) não. Um processo morto no meio
  (a rodada de 07/10 01:51 morreu com módulo meio velho/meio novo; o disco E: a 0 % ocioso) deixa
  JSON truncado: `listar()` pula a pasta sem aviso (some do rodízio, do `incompletas()`, do
  painel), `carregar` levanta e `_situacao` responde "nova" — `escrever_serie` com esse id
  escreveria **outra bíblia** na mesma pasta, por cima das `cenas/` da história antiga. Com duas
  faixas, `listar()` da outra faixa lê o arquivo no meio da gravação pelo mesmo caminho.
- Quando acontece: kill/queda de energia/E/S interrompida durante a gravação; leitura concorrente.
- Prova: `python prova3_salvar_serie.py` →
  ```
  antes: listar() ve ['historia_00099']
  salvar_serie: processo morto no meio da gravacao
  roteiro.json existe: True | tamanho: 418
  depois: listar() ve [] (sem aviso)
  carregar: JSONDecodeError Unterminated string starting at: line 20 column 3 (char 393)
  gerar._situacao(hid): 'nova'
  registrar_queda usa tmp+os.replace: True   salvar_serie usa tmp+os.replace: False
  ```
- Conserto sugerido: gravar em `roteiro.json.tmp` + `os.replace` (como `registrar_queda`), idem
  `_gravar`; `listar()` registrar no diário o `roteiro.json` ilegível em vez de pular calado.

### 4. Bíblia com menos partes do que o pedido passa, e a história fica "incompleta" para sempre (retomada escreve "PARTE 6 de 5") — gravidade: média

- Onde: `historias/contos/roteiro/gerar.py:570` (`if not biblia.get("partes")` — a única porta),
  `roteiro.py:897` (`partes_esperadas` = pedido), `roteiro.py:1021-1025` (`partes_que_faltam`),
  `serie.py:1038-1050` (`prompt_parte_livre` com `total = len(partes)`).
- O defeito: `problemas_da_biblia` acusa "so 5 parte(s) planejadas de 6", o gerador pede de novo
  uma vez e, se vier 5 outra vez, **segue** (a porta só exige lista não vazia). O roteiro nasce com
  5 partes escritas e `partes_esperadas: 6`; `incompletas()` o devolve a cada rodada e a retomada
  pede ao LLM "PARTE 6 de 5 … É a última parte" sem plano nenhum — um episódio fantasma depois do
  fim, publicado em sequência.
- Quando acontece: LLM que planeja menos partes 2x seguidas (o babaca de 2 partes é imune; favela
  e normal pedem 6).
- Prova: `python prova4_partes_curtas.py` →
  ```
  partes planejadas: 5 | pedidas: 6
  problemas_da_biblia: ['so 5 parte(s) planejadas de 6']
  porta do gerar: passa = True
  roteiro: partes escritas 5 | partes_esperadas 6   partes_que_faltam: [6]
  prompt da retomada, 1a linha: Escreva agora a PARTE 6 de 5, e so ela, seguindo o seu proprio planejamento.
  diz que e a ultima: True | plano da parte 6: {}
  ```
  Acervo: 0 casos hoje (as 2 diferenças achadas são roteiros de 09/2026 sem `partes_esperadas`).
- Conserto sugerido: depois da 2ª tentativa, ou levantar `GeracaoFalhou` quando
  `len(partes) != partes_esperadas`, ou gravar `partes_esperadas = len(biblia["partes"])` (a série
  vira a que o plano tem).

### 5. `modelo_llm` do roteiro é lido uma vez, no 1º chat: chat novo por recusa pode escrever as partes no Flash com o roteiro dizendo "3.1 Pro"; a retomada nunca marca "NAO CONFIRMADO" e troca o `provedor` do topo — gravidade: média

- Onde: `historias/contos/roteiro/gerar.py:503-514` (lido antes da bíblia), `gerar.py:135`
  (`_perguntar_sem_recusa` → `cliente.abrir(novo_chat=True)` reexecuta `escolher_modelo`),
  `gerar.py:445-451` (`retomar_serie`: `modelo_llm=getattr(cliente, "modelo_atual")`,
  `provedor=provedor`).
- O defeito: o campo que existe "para distinguir o que saiu do Flash" mente nos dois caminhos: na
  geração, cada chat novo pode trocar o modelo sem que o roteiro saiba; na retomada, o modelo
  não confirmado é gravado limpo e o `provedor` original (quem escreveu a bíblia) é substituído
  pelo da retomada (as partes guardam o seu, o topo não).
- Quando acontece: recusa enlatada no meio da escrita (3 chats por parte no pior caso) ou retomada
  por outro provedor com o menu de modelo falhando.
- Prova: `python prova7_modelo_gravado.py` →
  ```
  chats abertos: 2 | modelo do 2o chat: Gemini confirmado: False
  roteiro.json modelo_llm: '3.1 Pro Raciocínio avançado' (as duas partes sairam do 2o chat)
  linhas 'NAO CONFIRMADO' no log: 0
  antes: provedor=deepseek modelo_llm='DeepSeek (site) + DeepThink'
  depois: provedor= 'chatgpt' modelo_llm= 'GPT qualquer' | partes: [(1, 'gemini'), (2, 'chatgpt')]
  ```
- Conserto sugerido: gravar `modelo` (e `modelo_confirmado`) **por parte**, lendo o cliente na hora
  de cada `partes_prontas.append`, e a retomada manter o `provedor` do topo.

### 6. A troca de modelo custa ~32 s por chat e é refeita em todo chat novo, inclusive nos do carteiro de imagens — gravidade: média

- Onde: `historias/contos/llm/cliente.py:185-195` (3 tentativas, `sleep(2.5*volta)`), `cliente.py:272-281`
  (`encontrar` 6 s + `inner_text` 3 s + `click` 8 s por tentativa), `cliente.py:144` (toda `abrir()`).
- O defeito: nada lembra que o menu não respondeu há 40 s; cada chat novo paga as 3 tentativas
  inteiras, e o carteiro abre um chat por imagem (e outro a cada "recusou a imagem; tento uma vez
  em conversa nova"). Medido em 06–08/10: 210 casos, mediana 32 s, ~1,9 h de espera somada —
  numa fábrica que faz ~20 imagens/h no Gemini é ~18 % do tempo de cada imagem.
- Quando acontece: sempre que o botão de modelo existe mas não responde (06–08/10 inteiros).
- Prova: `prova1_modelo.py` → `cliques no botao de modelo: 3`, `segundos dormidos entre tentativas: 7.5`
  (fora os timeouts de 6+3+8 s por tentativa); logs: `grep -c "troca de modelo falhou" auto_2026100[678].txt` → 74, 218, 113.
- Conserto sugerido: lembrar por processo a última falha (ex.: 10 min) e, nesse prazo, tentar 1x;
  e `escolher_modelo` aceitar `preferido=None` do carteiro para pular a troca em pedido de imagem.

### 7. `titulo_da_parte` pode devolver só `" (Parte n/N)"` — gravidade: baixa

- Onde: `historias/contos/roteiro/roteiro.py:454-459`.
- O defeito: sem marca e sem título próprio, o título é a frase-gancho da série + ordem; se passa
  de 100 caracteres, o corte monta `" — ".join((marca, curto))` com os dois vazios e sobra só a
  ordem — vai para o mp4, a capa e o YouTube.
- Quando acontece: série sem `serie_nome` (bíblias antes de 11/09 ou LLM que não devolve a linha),
  parte sem título (o do plano também vazio) e título da série longo (131 chars no exemplo).
- Prova: `python prova5_pequenas.py` → `len(base) = 131` / `titulo_da_parte -> ' (Parte 1/2)'`.
- Conserto sugerido: quando `marca` e `proprio` ficam vazios, cortar a `base` (`base[:folga]`) em vez de descartá-la.

### 8. `narrador.quem_narra`: "moça", "menina", "mãe" viram voz de homem — gravidade: baixa

- Onde: `historias/contos/roteiro/narrador.py:54` (`startswith(("homem", "masc", "m"))`).
- O defeito: o prefixo `"m"` casa qualquer palavra começada em m. O gerador normaliza o campo para
  `mulher`/`homem` (acervo: 0 divergências), então só atinge roteiro montado à mão, teste ou o
  caminho manual (`salvar`), e a adivinhação pela descrição física nunca roda.
- Prova: `prova5_pequenas.py` → `narrador='moça' -> homem`, `'menina' -> homem`, `'mãe' -> homem`.
- Conserto sugerido: `startswith(("homem", "masc"))` e, sem casar, cair na contagem de pistas.

### 9. Prompt guiado para narrador homem: "na primeira pessoa de uma homem adulta adulto" — gravidade: baixa

- Onde: `historias/contos/roteiro/serie.py:335-337` (`prompt_biblia`, ramo `elif narrador`).
- O defeito: o artigo e o adjetivo são fixos no feminino e o masculino é colado no fim. Hoje os
  três tipos estão em `modo: livre` (`prompt_biblia_livre`), então o texto só sai se um tipo voltar
  ao guiado ou pelo caminho manual.
- Prova: `prova5_pequenas.py` → `QUEM CONTA: homem. A historia inteira e na primeira pessoa de uma homem adulta adulto.`
- Conserto sugerido: montar a frase inteira por gênero ("de um homem adulto" / "de uma mulher adulta").

## Não confirmados

- **Botão de parar do turno anterior confirma o envio seguinte.** Depois de "espera estourou em
  600s; uso o que ja veio" (4 casos nos logs, todos no parecer/reparo) o modelo pode continuar
  escrevendo; o próximo `enviar` acha o botão de parar na tela e `_confirmou_envio` (590) dá
  `True` sem o campo esvaziar — a resposta do turno velho seria lida como a nova (a âncora não
  ajuda: o turno novo não entrou). Não reproduzi a sequência inteira; o ramo do roteiro nunca
  estourou os 600 s com texto parcial nos logs.
- **`modelo_preferido` por substring (`"pro"`/`"flash"`).** `_tentar_modelo` (295-303) escolhe a
  primeira opção do menu cujo texto contenha `pro`; um rótulo como "Respostas prontas" ou "Flash
  Lite — Pro…" seria escolhido como forte. O DOM do menu não foi medido nesta auditoria; nos logs
  só aparecem "3.1 Pro Raciocínio avançado" (55x) e uma vez "3.5 Flash Lite" (Pro ausente).
- **`linguagem.PARE` com "cama"/"beijo" perto de "criança/adolescente".** `conferir_texto` (86-93)
  acende PARE para "a criança dormia na cama" (SEXUAL inclui `cama`, janela de 120 chars) e, com
  2 trocas recusadas, descarta a história e cai para o próximo provedor (que escreve outra
  bíblia). Nos logs houve 1 PARE em 13 dias ("adolescente", h43, resolvido na 1ª troca) — sem
  evidência de falso positivo em produção.
- **Falha de conteúdo vira queda de provedor.** `escrever_serie` (771) trata `GeracaoFalhou`
  (bíblia fora do formato, premissa impublicável) como falha do DeepSeek e manda o ChatGPT e o
  Gemini escreverem bíblias novas para o mesmo slot; `registrar_queda` não grava nada enquanto não
  há `roteiro.json`. Medido: 1 `GeracaoFalhou` e 12 `ERR_NAME_NOT_RESOLVED` (a queda do DNS de
  09/10) entre as 22 quedas dos logs — barato hoje, mas é custo triplo quando acontece.
- **`_Diario.__call__` não protege o `print`.** `self._log(texto)` (67) fica fora do `try`; um
  `UnicodeEncodeError` num console cp1252 (os textos têm «», —, í) derrubaria a geração. Não
  reproduzi: `main.py --saida` abre o log pelo Python em utf-8, e as tarefas do Agendador passam
  por ele.
- **`_falhas_seguidas` conta entre rodadas sem janela de tempo.** Duas falhas de ontem + uma de hoje
  = "erro" no diário hoje; e só a 3ª exata vira erro (a 4ª volta a aviso). É o desenho declarado
  (40), não um defeito provado.
- **`parse_biblia` ignora rótulo de topo escrito depois das partes** (`chave in rotulos and not
  atual`, 564) e "PARTE 1: Título" com dois-pontos não é cabeçalho (549). Medido nos 80 arquivos
  `conversa/biblia*.txt` do acervo: 0 ocorrências; os 7 `biblia_2.txt` vieram de "sem descrição física" (5) e
  "partes sem GANCHO" (2), não do parser.
