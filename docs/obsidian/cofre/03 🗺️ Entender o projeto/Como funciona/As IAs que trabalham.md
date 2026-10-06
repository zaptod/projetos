_Escrita pelo Claude a partir da documentação do projeto em 06/10/2026. Pode ler à vontade; se algo estiver errado, anote em 💡 Ideias._

# As IAs que trabalham

O projeto usa dois tipos de IA:
- **As IAs de fora:** Gemini, ChatGPT, DeepSeek e Grok. A máquina abre o site delas no navegador, com as suas contas, e conversa como uma pessoa faria.
- **As IAs que programam:** o Claude e o Codex. Elas mexem no próprio sistema. Ver [[A equipe]].

## Quem faz o quê nas fábricas
| IA | O que faz | Observação |
|---|---|---|
| **DeepSeek** | escreve os roteiros (1º da fila) | — |
| **ChatGPT** | escreve roteiro (2º), **desenha fotos** das histórias, reescreve pedido de imagem recusado, julga pela folha de fotos | não assiste vídeo nesta máquina |
| **Gemini** | **assiste aos vídeos** e dá o parecer, **desenha fotos** das histórias, escreve roteiro (3º) | conta gratuita; é o único que assiste vídeo |
| **Grok** | conversa com você pelo app e aconselha | não tem papel nas fábricas |
| **PicassoIA** | **FORA desde 06/10/2026** | era o desenhista principal, rápido (65–76 fotos por hora) |
| **Digen** | **FORA desde 29/09/2026** | fazia o vídeo de "payoff" das builds |

### Imagens das histórias, depois do PicassoIA
- Só o **Gemini** (cerca de 20 fotos por hora) e o **ChatGPT** (cerca de 15 a 30 por hora) desenham.
- **Um gerador por história** (03/10), para o rosto não mudar no meio da série.
- **Duas histórias ao mesmo tempo, uma em cada gerador** (06/10).
- O Gemini vem primeiro no rodízio (29/09).

### Por que o Gemini é o último a escrever roteiro
Ele é o único que assiste vídeo. Se ficasse preso horas escrevendo uma história, o juiz sairia do ar.

### O que o Gemini não faz
- **Ele não ouve o som** do vídeo. O único juiz do som é você.
- **Ele não julga sprites.** Ele recusava e travava nesse papel e saiu dele em 02/10.

## O correio e o carteiro
É o jeito que você e o sistema conversam com as IAs de fora sem bagunçar.
- **O correio** é uma caixa de cartas, uma por IA. Você (pelo app) ou uma fábrica deixa a mensagem na caixa.
- **O carteiro** é um programa que fica rodando no PC. Ele pega a carta mais antiga, abre o site da IA, entrega a pergunta, espera a resposta e põe a resposta de volta na caixa.
- **Uma conta, um usuário por vez.** Se a fábrica está usando a conta do ChatGPT, o carteiro espera. Ele nunca derruba o trabalho dela.
- **Você tem prioridade** (29/09): quando você conversa com uma IA, a fábrica espera a sua conversa terminar.
- **Cada IA tem um chat "casa"** de longa duração. A cada 12 mensagens, ela faz um resumo, para não perder o fio.
- **No máximo 2 navegadores abertos** ao mesmo tempo (30/09).
- A resposta aparece como **balão em cima do prédio dela na Vila**. Se você não estiver olhando o app, vai para o Telegram.
- **A Assembleia:** você faz uma pergunta e diz o que está em jogo; as IAs dão a recomendação delas, mas **só você decide**, no Grimório.

## Regras que valem para todas
- **Prova de origem.** Algumas contas eram compartilhadas com outras pessoas, e foto alheia já entrou: numa build em 25/08 e numa parte de história em 14/09. Por isso só entra imagem com prova de que saiu do nosso pedido.
- **Sem disfarce.** Você pediu várias contas grátis do ChatGPT com IP trocado (30/09). O caminho escolhido foi contas extras **suas**, cada uma com um papel próprio, sem esconder quem é.
- **Pedido diz o que é e para que serve.** Toda pergunta a uma IA leva o jogo, o objeto, o tamanho real, o uso e o que é cada anexo. Sem isso, a resposta vinha genérica.
- **IA que falha duas vezes num papel sai do papel na hora.**
- **Pergunte "o que está errado", nunca "ficou bom?".** Pergunta dirigida produz concordância: dois dias de nota 9 num vídeo que você reprovou numa olhada (16/09).

## As IAs que programam (resumo)
- **Claude:** o orquestrador e os agentes de cada parte. Você liga e desliga pelo app; com ele proibido, nada automático roda.
- **Codex** (do ChatGPT Plus, comprado em 01/10): faz trabalho grande e bem descrito numa cópia separada do projeto. Só propõe a mudança; quem aplica é o vigia, e quem confere é o conferente.

Veja também: [[A equipe]] e [[Fluxo das histórias]].
