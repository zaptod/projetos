_Escrita pelo Claude a partir da documentação do projeto em 06/10/2026. Pode ler à vontade; se algo estiver errado, anote em 💡 Ideias._

# App, bot e Obsidian

As três portas que você usa pelo celular para mandar no sistema e saber o que está acontecendo.

| Porta | Para que serve | Escreve ou só lê? |
|---|---|---|
| **App** | ver tudo, decidir, mandar fazer, publicar lutas | manda e lê |
| **Bot do Telegram** | avisos e relatórios automáticos; pedidos por texto | manda pedido, não publica |
| **Obsidian** | entender o projeto, organizar ideias, ler o diário | você escreve as suas notas; o sistema escreve as dele |

## O app
- **A tela é a Vila:** uma cidadezinha animada. Uma prateleira de madeira tem os objetos que abrem cada área.
- **Os objetos, um por pergunta** (desde 02/10):
  - ⏳ **Agora** — o que está rodando e o que vem a seguir: a próxima postagem, as fábricas, os erros, a fila de trabalho, a equipe, o Codex ao vivo e a conversa com o coordenador;
  - 📖 **Decidir** — o Grimório com as escolhas pendentes, a Assembleia das IAs, os sprites para aprovar e "o que o orquestrador decidiu sozinho" (com botão para contestar);
  - 📯 **Mandar** — o interruptor do Claude, pausar, retomar e parar, gerar, a mensagem para o orquestrador, controlar o PC e conversar com cada IA;
  - 🔭 **Ver** — Cinema (os vídeos), Biblioteca, Pergaminhos, Diário e o Ateliê de sprites;
  - ⚔️ **Arena** — escolher dois lutadores e um mapa e pedir ao PC uma luta no palco novo.
- **⏳ Agora → 📝 Pedir:** um texto livre vira pedido para a equipe. Você recebe um recibo na hora e a resposta quando estiver pronto; para continuar, use **Responder**.
- **Conversar com cada IA:** você escreve e a mensagem vai direto. A resposta aparece como balão na Vila.
- **Publicar pelo celular:** só lutas, sempre públicas, para YouTube e TikTok se você não disser o destino. Histórias seguem a grade.

### Como o app se protege
- **Só funciona dentro do Tailscale.** O Tailscale é uma rede privada entre os seus aparelhos. O app nunca fica aberto na internet.
- **Pareamento por código:** 6 dígitos, uma vez só, válido por 5 minutos.
- **Dois toques** em tudo que não se desfaz. O primeiro mostra o que vai acontecer; o segundo, em até 60 s, executa e confere de novo.
- **Zona de perigo** (apagar mídia, trocar conta, refazer o banco de lutadores) só existe com o modo especial ligado **e** digitando o nome do alvo.
- **Nada de tela de login pelo celular:** logins, contas e janelas do jogo ficam no PC.
- **O app nunca pode cair** (01/10). Toda mudança no app entra junto com o reinício dele. Quem o mantém de pé é o coordenador, que funciona 24 horas.

## O bot do Telegram
- **Relatórios automáticos:**
  - **09:00 — funcionamento:** as fábricas por dentro, os erros e as tarefas do Windows;
  - **21:00 — metas:** o que saiu hoje, a semana e o estoque em dias;
  - **22:30 — confiabilidade:** o que foi prometido contra o que foi provado: horário em falta, canal parado, medição velha.
- **Avisos na hora:** erros, estoque abaixo do piso, resposta de uma IA quando o app está fechado, entrega que precisa de olho.
- **Apuração de erros:** quando algo quebra, uma IA investiga só lendo e manda o diagnóstico.
- **Texto livre** vira pedido, igual ao 📝 Pedir do app. /novo abre um assunto novo.
- **O bot não publica** (decisão de 28/09). Publicar pelo celular é só pelo app.

## O Obsidian
- **Escolha de 06/10:** o cofre fica numa pasta do PC, e o **Syncthing** (grátis) copia a pasta para o celular, pelo Wi-Fi ou pelo Tailscale. O PC precisa estar ligado para atualizar.
- **As pastas:**
  - 💡 Ideias e 📝 Minhas notas são **suas**: o sistema nunca mexe nelas;
  - 🗺️ Entender o projeto (esta seção) é escrita pelo Claude;
  - 🧭 Decisões e 📅 Diário do sistema são atualizadas sozinhas.
- **Para virar trabalho:** uma ideia madura sai daqui pelo 📝 Pedir do app, com o link da nota.

Veja também: [[A equipe]] e [[03 🗺️ Entender o projeto/Como funciona/Painel e Vila|Painel e Vila]].
