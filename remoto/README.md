# Remoto — o painel no seu bolso

> Parte do monorepo `e:/projetos`. O mapa de todos os projetos, quem depende de quem e como instalar está no [README da raiz](../README.md).


Duas portas para o celular:

- o **bot de Telegram**, que **avisa** quando algo quebra e **aceita
  comandos**. Sem dependência nova: só `urllib` da biblioteca padrão;
- o **app do celular** (PWA), com a Vila, o diário, os vídeos, os relatórios
  e a tela Comandos — servido **só dentro do tailnet** do Tailscale.

> **`tailscale serve` sim, `tailscale funnel` nunca.** O `funnel` publica na
> internet aberta; o `serve` só para os aparelhos do tailnet. O servidor do
> app escuta apenas em `127.0.0.1:8931`, e a porta **8765 é proibida** no
> código: é a do login OAuth do YouTube, e um servidor esquecido nela já
> quebrou o login.

## Por que um bot, e por que o app só no Tailscale

A máquina do outro lado tem YouTube, TikTok, ChatGPT e PicassoIA **logados**.
Um painel web aberto na internet seria uma porta de entrada para tudo isso.
O bot faz o contrário: **ele** liga para o Telegram, de dentro para fora.
Nenhuma porta aberta, nenhum IP exposto, nenhum certificado para manter.

O app não abre porta para a internet: quem o publica é o `tailscale serve`,
que só atende quem está no tailnet, e o próprio servidor ainda confere o
`Host` e exige um token de aparelho (pareado uma vez, por código de 6 dígitos
que vale 5 minutos; o disco guarda só o hash do token).

```bash
python -m remoto.api_http --parear      # código de 6 dígitos para o app
python -m remoto.api_http --aparelhos   # quem está pareado
tailscale serve status                  # tem de dizer "tailnet only"
```

O servidor do app não se sobe à mão: a tarefa `NeuralFights_app_celular`
roda `app_celular.cmd` de 10 em 10 minutos. O resto (guardas, dois passos,
estado em disco, armadilhas) está em `docs/sessoes/app-e-bot.md`.

## Ligar (uma vez)

```bash
# 1. no celular: fale com @BotFather, mande /newbot, copie o token
python -m remoto --token 8123456:AAH...

# 2. ligue (ou use o botão 🤖 Bot do celular na página Vila do painel)
python -m remoto
```

Ele imprime um código de 6 dígitos. No Telegram, mande `/parear <código>`
para o seu bot — é assim que ele aprende que aquele celular é seu.

```bash
python -m remoto --status              # token? quem está autorizado?
python -m remoto --esquecer 123456789  # tira um celular da lista
```

## Comandos

| comando | o que faz |
| --- | --- |
| `/status` | o que está rodando agora, e o que falhou |
| `/vila` | as 7 fábricas, uma linha cada |
| `/erros [n]` | os últimos problemas, com hora |
| `/videos` | os vídeos prontos, com id |
| `/ver <id>` | **manda o mp4 no chat** — assistir antes de aprovar |
| `/publicar` | **não publica**: responde que publicar é só pelo app do celular |
| `/gerar` | uma build nova |
| `/historias` | em que pé está o canal de histórias |
| `/pausar [min]` · `/retomar` · `/parar` | controle da fila |

Os comandos longos **não travam o chat**: eles disparam o processo e voltam
na hora. O resultado chega pelos alertas — que é justamente para isso que o
diário `atividade.jsonl` existe.

**Só o app publica pelo celular** (decisão do Adrian, 28/09/2026). No app
existe a tela para conferir o vídeo e o destino, a confirmação em dois passos
e todas as guardas: vídeo já no ar, título repetido, a outra variante, a
lista "a conferir", a postagem da grade perto ou rodando, o Chrome ocupado e
qualquer publicação ainda sem desfecho. Sem destino dito, vão os dois
(YouTube e TikTok). Até 27/09 o `/publicar` do bot chamava o `main.py
publicar` direto, num passo só, sem nada disso, e o YouTube subia privado.

A tela **Decisões** do app (28/09/2026) mostra o que o Adrian precisa
decidir. Cada decisão vem com os vídeos (tocando por Range), as imagens, as
opções e um campo de comentário. A resposta vai para
`%LOCALAPPDATA%\neural-fights\decisoes\respostas.jsonl` e para o Telegram.
Item novo entra pela CLI: `python -m remoto.decisoes adicionar ...`.

O bot também **vigia o tailnet** (`vigia_tailnet.py`). A cada 2 minutos ele
confere três coisas: o Tailscale está `Running`, o `serve` aponta para o app
e o `funnel` está desligado. Quando algo falha, avisa uma vez, e avisa de novo
quando voltar. O único conserto que ele faz sozinho é abrir o cliente da
bandeja (`tailscale-ipn.exe`) quando ela não subiu. Ele nunca mexe no
`serve` nem no `funnel`.

## As duas trancas

1. **Lista branca.** Qualquer pessoa pode mandar mensagem para um bot se
   souber o nome dele. Quem não está na lista recebe `não autorizado.` e mais
   nada — nem a lista de comandos, que já seria informação sobre a máquina.
2. **Tabela fechada.** Não existe caminho de "texto do celular" para "comando
   do sistema". Cada comando é uma função de `comandos.py`, e um `/rodar` ou
   `/exec` morre como comando desconhecido. Há teste travando isso.

O token nunca entra no repositório: fica em
`%LOCALAPPDATA%/neural-fights/remoto.json`, junto das outras credenciais.

## O que o bot NÃO resolve

Passos que exigem uma tela de verdade — o QR do TikTok, um captcha, o login
do Google. O Chrome roda com janela (`headless=False` é o que evita a
detecção de bot), então esses momentos precisam de acesso remoto à área de
trabalho (RustDesk, Chrome Remote Desktop). O bot cobre o dia a dia; o
acesso remoto é a saída de emergência.

## Testes

```bash
python -m pytest remoto/ -q --basetemp=E:/projetos-wt/_pytest_app/x   # nenhum toca a rede
```

O `--basetemp` vai para o `E:` de propósito: o `C:` vive perto de encher.
