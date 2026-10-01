# Regras desta tarefa (leia antes de começar)

Você é o Codex trabalhando numa worktree própria do projeto. O orquestrador
(o Claude) confere o seu trabalho, roda os testes de novo e aplica o diff ele
mesmo. Você **só propõe**.

- **Não commite, não crie branch, não dê push.** O `.git` é só de leitura.
- **Mexa só nos caminhos permitidos** (lista no fim). Diff fora dela é recusado
  inteiro, sem conversa.
- **Nada de arquivo binário** (imagem, áudio, vídeo, banco). Diff com binário
  é recusado.
- **Diff pequeno.** Conserto focado; não reformate arquivo inteiro, não renomeie
  o que a tarefa não pediu.
- **Teste de regressão junto** quando a tarefa for conserto: um teste que falha
  sem o conserto e passa com ele.
- **Rode os testes com `-p no:cacheprovider`** (ex.:
  `python -m pytest remoto/test_x.py -q -p no:cacheprovider`). A pasta
  `.pytest_cache` que o sandbox cria não pode ser apagada depois.
- **Não leia nem escreva** credenciais, tokens, `auth.json`, `.env` ou qualquer
  coisa em `%LOCALAPPDATA%` e `~/.codex`.
- **Não use rede.** Não instale pacote.
- Código e comentários seguem o estilo do arquivo que você mexe (português,
  sem acento nos comentários de código Python antigos quando o arquivo é assim).
- **No fim, responda em português**, curto: o que mudou (arquivo por arquivo),
  como você testou (comando e resultado) e o que ficou de fora ou em dúvida.
