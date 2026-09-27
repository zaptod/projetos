# Publicação

Documento de passagem. Quem chegar aqui sem nunca ter visto o projeto consegue
operar esta parte lendo só isto. Escrito em 27/09/2026.

## 1. O que é, e o caminho de uma publicação

Esta parte **escolhe** qual vídeo sai, **publica** nos dois destinos e
**registra** o que saiu. Não cria nada: histórias e builds chegam prontos.

| Peça | Arquivo |
| --- | --- |
| A rodada inteira: escolha, guardas, avisos, recuperações | `E:\projetos\ferramentas\postar.py` (2868 linhas — é o cérebro) |
| Grade: horários, minuto, cota por plataforma | `E:\projetos\random_builds\builds\grade.py` |
| Título comparável ("isto já está no ar?") | `...\builds\publicar\titulos.py` |
| Ledger, `publicado()`, `prova_ok()`, reconciliação, métricas | `...\publicar\metricas.py` |
| Catálogo dos mp4 de builds; corte em pedaços ≤180 s | `...\publicar\catalogo.py`, `cortes.py` |
| Publicadores | `youtube.py` (API), `youtube_web.py` (navegador — é o caminho usado), `tiktok.py` (navegador) |
| "O que aconteceu no clique" + lista "a conferir" | `...\publicar\desfecho.py` |
| Ledger × canal de verdade / privado que deve voltar | `conferencia.py`, `recuperar.py` |

Uma rodada (`postar.py` sem argumentos, disparada pelo Agendador):

1. `esperar_a_rede()` — resolve DNS por até 300 s (abrir o Chrome para descobrir
   que a rede caiu custa minutos).
2. **Histórias**: `fila_de_historias()` ordena → `proxima_historia()` peneira →
   `contos.publicar.catalogo.publicar_youtube` → `serie.registrar` →
   `_tiktok_das_historias` → `serie.registrar`.
3. **Builds**: `proximo_build()` → `youtube.publicar_como_configurado` →
   `_tiktok_dos_builds` (`tiktok.publicar`) — os dois **registram por dentro**.
4. Depois, e nunca no lugar: **recuperação do TikTok** (1 por canal, saiu no
   YouTube e nunca chegou lá), **recuperação do YouTube** (1, ficou privado no
   canal) e **reserva do TikTok** (só se builds não levou nada lá neste horário).
5. `avisar()` no Telegram, estoque em dias, e **saída 1** se tentou e nada saiu
   (era `return 0` fixo, e o Agendador registrava sucesso em rodada vazia).

O registro é assimétrico de propósito: **histórias registram por fora**
(`serie.registrar`), **builds por dentro** do publicador — porque
`metricas.registrar_publicado` descarta canal ≠ `builds`. Trocar duplica de um
lado e perde a linha do outro.

## 2. A grade e as guardas

`grade.GRADE` — dez horários com **minuto próprio**: `00:37, 06:37, 09:37,
12:07, 15:37, 17:57, 20:37, 21:37, 22:37, 23:37`. São as horas vagas das
pessoas (decisão dele, 15/09). **TikTok posta em todos**. Dez tarefas
`NeuralFights_postar_HH` no Agendador (conferidas hoje: todas "Pronto").

Use `grade.minuto(h)`, nunca a constante `MINUTO`; e `grade.slot(agora)` para
saber a que horário a rodada pertence — :57 mais ~4 min de upload cruzam a hora,
e a hora do relógio dava dois veredictos na mesma rodada.

**Cota por formato** (builds): `COTA_PADRAO = {duelo 4, build 3, estreia 1,
torneio 0}`, sobreponível em `config/publicacao.json` → `grade.mistura`.
`escolher_por_cota` é pura: vence o formato mais atrasado em `servidos/cota` nas
últimas `JANELA_DA_GRADE = 16` publicações. Cota 0 não é proibição.

| Guarda | Onde mora |
| --- | --- |
| Um por horário **por plataforma** | `postar.publicou_neste_horario` (janela = hora do relógio; fonte = ledger) |
| Título já publicado (fecha a fila) | `postar._sem_titulo_repetido`/`titulo_repetido`; regra em `titulos.chave/repetido` |
| Variante A/B (`:B` tem o mesmo título) | `postar.VARIANTES`, `_e_variante`, e a própria chave de título |
| Teto de 2 por fonte/dia, por destino | `TETO_POR_FONTE_NO_DIA`, `_fontes_cheias_hoje`, `_sem_fonte_cheia` |
| Ordem das partes na fila | `fila_de_historias` (menor parte que falta; a anterior tem de existir) |
| Ordem das partes **no destino** | `_em_ordem_no_destino` — pergunta ao TikTok, não ao ledger |
| Parte barrada segura as seguintes | `proxima_historia` (`bloqueadas`/`adiadas`) |
| "A conferir" (clique sem confirmação) | `desfecho.a_conferir` + `postar._sem_a_conferir`/`_com_as_raizes` |
| Espera de processamento e confirmação | `youtube_web.py`, `tiktok.py`; veredito em `desfecho.classificar` |
| Vídeo mudo | `postar._audio_mudo` (`LIMIAR_MUDO_DB=-60`, `FRACAO_MUDA=0.5`) |
| Imagem faltando / arquivo quebrado | `contos.publicar.qualidade.vistoriar_parte`; `v.pendencias` (builds) |
| História sendo renderizada | trava `historias__render__<fonte>` |
| Rodízio favela/normal/babaca | `_no_rodizio_dos_tipos` → `contos.publicar.tipos` |
| Desistência após 3 falhas | `_anotar_falha_no_tiktok`, `FALHAS_ATE_DESISTIR=3` |
| Cota do YouTube não mata o TikTok | `_e_limite_diario` + `try/except` por destino |

Só **uma** guarda falha fechada (erro ⇒ não publica): a lista "a conferir". As
outras, em dúvida, deixam passar — "não sei" nunca barra vídeo, mas vira erro no
diário.

## 3. As leis (decisões do dono)

- **Não ficar sem vídeo** (13/09) — mas **repetir é pior que não postar**
  (17/09). Quando brigam, o horário fica vazio e o log diz "a válvula fechou".
  A marca `titulo_repetido` no aviso hoje é *detector de escape*: deve ser zero.
- **Ordem da série é sagrada.** Fora de ordem só como último recurso no YouTube;
  no TikTok nunca, porque lá a recuperação é sempre extra.
- **Teto de 2 partes da mesma história/geração por dia**, no perfil inteiro —
  rodada normal, recuperação e reserva somadas.
- **Builds antigos (29/08–09/09, `CORTE_DO_TIKTOK`) são gordura, não atraso**:
  só saem no TikTok quando falta vídeo novo (`reserva_do_tiktok`).
- **Rascunhos do "Publicar mesmo assim" ficam** como gordura (15/09):
  `conferencia.rascunhos_aceitos` os tira do alarme. Não republicar.
- **Quem decide publicar de verdade é uma pessoa**: `postar_automatico: false`
  é para o botão do painel; a grade passa `postar=True` explícito.
- **O nome da conta é o destino**: `youtube_web` publica, `youtube` só lê.

## 4. O que já quebrou

- **Rascunhos gêmeos** (22 no canal): clique sem confirmação não gravava linha, a
  fila reescolhia o mesmo vídeo, cada rodada deixava um rascunho. → `desfecho` +
  lista "a conferir", chamada **de dentro** do `tiktok.publicar`.
- **Repostagem de série inteira** (16/09: h3 e h16 em 11 dos 16 posts): o ledger
  era cego ao passado do TikTok. → `conciliar_tiktok.py`, teto por fonte e
  rodízio; só então as recuperações voltaram a ligar.
- **Ordem embaralhada**: a h3 saiu 7,8,9,10 e só então 1–6, porque a fila do
  TikTok era partida por data. → `_em_ordem_no_destino`.
- **Leitura do canal que perdia vídeo**: `_titulos_no_ar` contava o próprio vídeo
  publicado segundos antes ⇒ "título repetido" falso 4× em 16/09. → `menos=<id>`.
- **Contador que mentia**: `pendentes_por_canal` contava `catálogo − ledger`, sem
  pendências nem títulos repetidos ⇒ "2 dias de gordura" com `proximo_build()`
  devolvendo `None`. → mesmo funil da escolha.
- **Rascunho contava como publicação**: `url` guardava link *e* frase de estado.
  → `metricas.publicado(linha)` é a resposta única (`CONTRATO_DO_LEDGER = 2`).
- **Trava do ledger**: reescrita simultânea comia a linha nova. Quem acrescenta
  espera 120 s e grava mesmo sem trava (avisando); quem reescreve desiste.

## 5. O estado de hoje (27/09/2026)

Conferência da madrugada: **limpo** nos dois canais (1/1 builds, 27/27
histórias; zero fantasma, zero rascunho). Ledger: 244 linhas em builds, 320 em
histórias, nenhuma `(video_id, plataforma)` duplicada.

**Trabalho NÃO COMMITADO de uma sessão já fechada** — `titulos.py`,
`recuperar.py`, `metricas.py`, `test_id_pelo_canal_regressions.py` (modificados)
e `test_titulo_do_corte_regressions.py` (novo). Assunto único: uma parte longa
vira dois Shorts `(1 de 2)`/`(2 de 2)` e o ledger guarda **uma** linha para os
dois. `titulos.chave()` passa a ignorar o sufixo do corte (a *parte* fica) e
nasce `titulos.corte()`; `recuperaveis` deduplica por `(chave, corte)` para não
deixar metade da parte privada para sempre; `id_no_canal` virou `ids_no_canal`
(lista); `casar_ids` ganhou guarda para linha inteira não casar com meio vídeo.

Falta, e era o que impedia commitar:

1. **`casar_ids` estava QUEBRADO** e foi consertado em 27/09/2026 pela
   orquestração: usava `titulos.corte(...)` sem `titulos` importado no topo
   (o único import era local, dentro de `_chave_de_titulo`), e o `NameError`
   derrubava `metricas.reconciliar` (madrugada) e `ferramentas/curar_ledger.py`.
   Hoje `metricas.py` tem `from . import titulos` no topo, com comentário
   dizendo por que ele mora lá. Conferido chamando a função pura: casa a linha
   certa e não casa linha inteira com meio vídeo.
2. A suíte completa foi rodada pela orquestração em 27/09/2026, depois do
   conserto (`python testar.py`, TEMP no `E:`, fora da janela :25-:55).
3. `ids_no_canal` **não tem chamador**: `youtube.py:151` segue usando
   `id_no_canal`, então o ledger grava só o id do primeiro pedaço. Decidir se
   passa a guardar os dois. **É a única pendência que sobrou deste assunto.**

**Problemas abertos**

- **25 builds fora da fila por título repetido** (quase todos variantes `:B`) e
  **3 por pendência** (`generation_00085`, `generation_00077` e sua variante).
  Com isso a gordura de builds está em **0 dias**, abaixo do piso.
- **`generation_00066:estreia:celular` é muda** (calada em 95% do tempo, 115 s
  de 121) e é barrada em toda rodada. Precisa re-render, não conserto de código.
- **Duplicatas da `historia_00003` no canal**: 6 conteúdos no ar duas vezes (o
  vídeo inteiro *e* os dois pedaços). Medido em 17/09, **não reverificado hoje**.
  Nenhum código corrige isso — é limpeza no canal, decisão dele.
- Histórias avisam "só 4 séries elegíveis, o dia precisa de 5": com teto 2 e dez
  horários falta **variedade**, não partes. O conserto é na agenda (Histórias).

## 6. Como conferir, sem publicar nada

```
cd E:\projetos
python -m builds.publicar.conferencia --canal builds --dias 3     # ledger x canal (só lê a API)
python -m builds.publicar.conferencia --canal historias --dias 3
python ferramentas/curar_ledger.py                                # A SECO: só relata o que mudaria
python random_builds/main.py metricas                             # último dado salvo, sem rede
type outputs\postar.txt                                           # log das rodadas (enorme; leia o fim)
type random_builds\outputs\_conferencia\2026-09-27.json
```

Sem rede: leia os ledgers linha a linha com `json.loads` e conte por
`metricas.publicado(linha)`. `grade.horarios()`, `grade.vencidos()`,
`titulos.chave()` e `metricas.casar_ids()` são puros. Evite `postar.py --ver`:
decodifica mp4 e vários caminhos escrevem no `atividade.jsonl`.

## 7. O que NÃO fazer

- Não rodar `ferramentas/postar.py` sem `--ver`: **publica de verdade**.
- Não fazer trabalho pesado entre **:25 e :55** (as postagens automáticas).
- Não escrever no `publicados.jsonl` sem a trava `ledger__<canal>`, nem
  reescrevê-lo fora de `curar_ledger.py --gravar` (que faz cópia antes).
- Não apagar nem "consertar" `_tiktok_a_conferir.json` /
  `_youtube_a_conferir.json`: arquivo ausente significa "ninguém bloqueado", e
  isso **é uma afirmação**. Corrompido fica onde está, de propósito.
- Não reabrir a válvula de título repetido nem mexer em `TETO_POR_FONTE_NO_DIA`,
  `CORTE_DO_TIKTOK`, `RECUPERACAO_LIGADA`, `RESERVA_LIGADA`: são decisões dele.
- Não criar um segundo critério de "publicado", de "título igual" ou de "horário
  da grade" (cada duplicata dessas já custou um defeito), nem usar a hora do
  relógio onde cabe `grade.slot()`.
- Não perguntar ao Gemini na hora de postar (`PEDIR_PARECER_NA_POSTAGEM=False`).

## Contratos com outras partes

| Arquivo / recurso | Quem manda | Quem mais usa |
| --- | --- | --- |
| `random_builds/outputs/_publicar/publicados.jsonl` | **publicação**, só por `metricas.acrescentar_ao_ledger` | conferência, métricas, auditoria, relatórios do bot, app |
| `historias/outputs/_publicar/publicados.jsonl` | **publicação**, via `contos.publicar.serie.registrar` | idem |
| `builds/grade.py` | **publicação** | agenda de histórias, painel flutuante, `remoto/relatorios.py`, auditoria, `youtube_web` |
| `_tiktok_a_conferir.json`, `_youtube_a_conferir.json` | **publicação** (`desfecho`), sob a trava `<plataforma>_a_conferir` | app e bot leem para mostrar pendência |
| `_tiktok_desistencias.json` | **publicação** | — |
| `historias/.../prioridade.json` | **o Adrian** (pedido manual) | publicação só lê |
| `atividade.jsonl` (diário) | **todos escrevem**, ninguém é dono | bot avisa no celular, apurador investiga erro, página de confiabilidade soma |
| travas `ledger__<canal>`, `<plataforma>_a_conferir` | **publicação** | `historias__render__<fonte>` é da parte Histórias (aqui só se lê) |
| `config/publicacao.json` (`grade.mistura`, `visibilidade`, `postar_automatico`) | **o Adrian** | publicação e painel leem |
| `contos.publicar.{catalogo,serie,qualidade,parecer,tipos}` | parte **Histórias** | publicação chama |
| `builds.publicar.catalogo` (`pendencias`, `origem`, `capa`) | parte **Builds** | publicação chama |
| `builds.contas` (conta ativa por serviço/canal) | parte **Contas** | publicação lê para dizer o destino |

Regra acima de tudo: **um escritor por arquivo**. Se outra parte precisa mudar o
ledger, ela pede à publicação — não escreve por conta própria.
