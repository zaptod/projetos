# App do celular e bot do Telegram

Documento de passagem. Quem chegar aqui sem nunca ter visto o projeto
consegue operar esta parte lendo só isto.

## 1. O que é, e onde mora

Duas portas de saída para o Adrian comandar o sistema de fora do PC:

| Peça | O que é | Sobe por |
| --- | --- | --- |
| **App** (PWA) | página instalável no celular: a Vila animada, diário, vídeos por streaming, relatórios e a tela Comandos | tarefa `NeuralFights_app_celular` (a cada 10 min) → `app_celular.cmd` |
| **Bot** | bot de Telegram: avisos automáticos e uma tabela fechada de comandos | tarefa `NeuralFights_bot_telegram` → `bot.cmd` |

Tudo vive em `remoto/`:

- `api_http.py` — o servidor do app (rotas, pareamento, bilhetes de vídeo).
- `acoes.py` — as cinco ações antigas (pausar, retomar, parar, gerar,
  publicar) e as guardas de publicação.
- `comandos_app.py` — o **catálogo** dos outros controles (fichas
  declarativas: campos, guardas, texto de confirmação).
- `tarefas.py` + `publicacao_filha.py` — trabalho pesado como processo
  desligado do servidor, com log em arquivo.
- `vila_nova.py` (desenho + vida da Vila) e `vila_dados.py` (o texto:
  fábricas, travas, placar).
- `comandos.py`, `bot.py`, `api.py`, `relatorios.py`, `apurador.py` — o bot.
- `app/` — a PWA (`index.html`, `app.js`, `vila.js`, `comandos.js`).

Estado em disco, em `%LOCALAPPDATA%\neural-fights\`: `app_celular.json`
(aparelhos pareados, só o hash do token), `app_celular_acoes.jsonl` (rastro),
`app_celular_em_voo.json` (publicações sem desfecho), `app_celular_tarefas/`
(uma pasta por tarefa) e `remoto.json` (token do bot).

**Rede:** o servidor escuta só em `127.0.0.1:8931` e quem o publica é o
`tailscale serve` (`https://desktop-tgti3ek.tail63af85.ts.net`, *tailnet
only*). A porta **8765 é proibida** no código: é a do login OAuth do YouTube,
e um servidor esquecido nela já quebrou o login.

## 2. Como rodar e conferir sem publicar nada

```bash
python -m pytest remoto/ -q --basetemp=E:/projetos-wt/_pytest_app/x   # 425 testes
python -m ruff check remoto/
python -m remoto.api_http --local --porta 8934 --acoes                # instância de teste
python -m remoto.api_http --parear      # código de 6 dígitos (5 min, uma vez)
python -m remoto.api_http --aparelhos   # id, nome, desde
python -m remoto.api_http --em-voo      # publicações sem desfecho
python -m remoto.tarefas                # tarefas recentes e como terminaram
```

Use **sempre** `--basetemp` no `E:` — o `C:` vive perto de encher, e a falha
"intermitente" da suíte em 17/09 era disco cheio.

**Não suba o servidor à mão na porta 8931.** Se ele cair, a tarefa do
Agendador o levanta em até 10 minutos. Para trocar de versão: pare o processo
e rode `app_celular.cmd` (ou espere a tarefa). Reinício fora de `:25–:55`, que
é a janela da postagem.

A prova de tela roda em Chrome headless com perfil temporário
(`patchright`, `channel="chrome"`). Atenção: `page.evaluate` do patchright roda
em contexto **isolado** — ele não enxerga as variáveis da página; confira pelo
DOM e clicando.

## 3. Decisões do Adrian que valem como lei

1. **Só dentro do Tailscale.** `tailscale serve` sim; `tailscale funnel`
   (público) **nunca**.
2. **Pareamento por código** de 6 dígitos, uma vez, 5 minutos. O disco guarda
   só o hash do token; o token existe no celular.
3. **Publicar pelo app é só de builds**, e sempre como `public`. Histórias
   têm caminho próprio (`publicar_historia`), porque a ordem das partes é da
   grade.
4. **Dois passos** em tudo que não se desfaz: o 1º pedido devolve um texto de
   confirmação e um código de 60 s; só o 2º executa, e ele **reavalia as
   guardas**.
5. **Zona de perigo** (apagar mídia do Espelho, regenerar banco, esquecer ou
   trocar conta) só existe com `--perigosas` **e** digitando o nome do alvo.
6. **Nada de interface no celular**: logins, OAuth, Oficina, janelas do jogo e
   `os.startfile` ficam no PC.

## 4. Armadilhas medidas (já quebraram)

- **PIPE mata o filho.** Com a saída do `main.py` num pipe do servidor, o
  servidor que reinicia mata a publicação no meio — inclusive depois do clique.
  Por isso a filha escreve em **arquivo** e roda desligada (`DETACHED` +
  breakaway do job). Há teste com job "mata ao fechar" provando os dois lados.
- **"YouTube: ..." não é sucesso.** O Studio devolve "cliquei em publicar, mas
  não confirmou… RASCUNHO" com código 0. Use `youtube_web.confirmado` e
  `tiktok.confirmado`; hoje o `main.py publicar` ainda imprime `A CONFERIR` e
  sai com **código 3**.
- **Lista "a conferir" vazia é uma afirmação.** `desfecho.a_conferir()`
  **levanta** quando não consegue ler. Tratar isso como "ninguém bloqueado"
  reposta todo mundo. O app falha fechado: **tudo que não dá para ler recusa**.
- **`travas.ocupada()` pega a trava** por um instante — um celular perguntando
  a cada segundo faria o dono da trava desistir. Use a sonda de leitura
  (`acoes.trava_ocupada`); há teste que falha se alguém chamar a outra.
- **`panorama.resumo()` leva ~159 s** na primeira conta: o placar roda em
  thread e é servido com a idade. Nunca dentro do pedido.
- **Partes cortadas** viram `X:corte01` no ledger e na marca: compare com
  `acoes.mesmo_video`, nunca com `==`.
- **Heredoc do bash come a barra invertida** ao escrever patches: use a
  ferramenta Write.

## 5. Pendências e o que não fazer

- O bot (`/publicar`) **não** usa as guardas novas nem o "em voo" do app: ele
  pode mandar o mesmo vídeo que o app acabou de mandar. Unificar é a próxima
  dívida.
- O app **não** mata tarefa: um `kill` no meio de um upload deixa estado pela
  metade. Para frear, use Pausar/Parar, que o worker obedece.
- **Não** apague `vila/` (motor e Oficina): o painel do PC e a arte "clássico"
  da janela flutuante ainda dependem dele. A Vila antiga saiu só do app.
- **Não** mexa em `random_builds/builds/publicar/*` a partir daqui: aquilo é de
  outra sessão; o app **consome** aquelas funções.
- Controle novo = **ficha nova no catálogo**, nunca botão novo no JavaScript.
  Se ele gasta conta compartilhada, declare `perfis` (guarda de perfil ocupado)
  e ponha o nome em `comandos_app.PESADAS` (teto por hora).

## 6. Contratos com as outras partes

| Arquivo / recurso | Quem manda | Como o app entra |
| --- | --- | --- |
| `_tiktok_a_conferir.json` e `_youtube_a_conferir.json` | `builds.publicar.desfecho` | lê e escreve **sob a trava** `desfecho.nome_da_trava(<destino>)`; a marca do app leva `"app": <chave>` e só ela é retirada pelo app |
| `publicados.jsonl` (ledger) | `builds.publicar.metricas` | o app **só lê**; quem grava é o publicador, sob `ledger__<canal>` |
| `atividade.jsonl` (diário) | `builds.atividade` | o app lê; escreve **uma** linha (`etapa app.a_conferir`) quando marca algo a conferir |
| travas de perfil | `builds.travas` | só a sonda de leitura |
| `app_celular_*.json(l)` e as tarefas | **esta sessão** | escrita sob `trava_arquivo`, reentrante por thread |
| grade de postagem | `ferramentas/postar.py` | o app respeita a janela (−20/−25/−40 min conforme o destino, +18 min) e recusa se `postar.py` estiver vivo |
