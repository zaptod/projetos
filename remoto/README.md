# Remoto — o painel no seu bolso

> Parte do monorepo `e:/projetos`. O mapa de todos os projetos, quem depende de quem e como instalar está no [README da raiz](../README.md).


Bot de Telegram que **avisa** quando algo quebra e **aceita comandos** do
celular. Sem dependência nova: só `urllib` da biblioteca padrão.

## Por que Telegram (e não um site)

A máquina do outro lado tem YouTube, TikTok, ChatGPT e PicassoIA **logados**.
Um painel web precisaria de uma porta aberta para a internet — uma porta de
entrada para tudo isso. O bot faz o contrário: **ele** liga para o Telegram,
de dentro para fora. Nenhuma porta aberta, nenhum IP exposto, nenhum
certificado para manter.

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
| `/publicar <id> [youtube\|tiktok\|ambos]` | sobe aquele vídeo |
| `/gerar` | uma build nova |
| `/historias` | em que pé está o canal de histórias |
| `/pausar [min]` · `/retomar` · `/parar` | controle da fila |

Os comandos longos **não travam o chat**: eles disparam o processo e voltam
na hora. O resultado chega pelos alertas — que é justamente para isso que o
diário `atividade.jsonl` existe.

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
python -m unittest remoto.test_remoto -v   # 29, nenhum toca a rede
```
