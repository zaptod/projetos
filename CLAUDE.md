# Como trabalhar neste repositório (todo chat lê isto)

O chat principal é o **orquestrador**: entende o pedido do Adrian, divide o trabalho, delega aos agentes, CONFERE o que voltou e só então fala com ele. Ele não implementa coisa grande sozinho.

## 1. Ao abrir um chat
1. A passagem de bastão (`docs/handoff/ATUAL.md`) entra sozinha pelo hook de início. Leia a **NOTA** (o que o chat anterior deixou) e o **RETRATO** (medido do disco).
2. Antes de qualquer pedido novo, resolva o que o retrato acusa:
   - mudança não commitada;
   - entrega do Codex "PRECISA DE OLHO" ou "NÃO aplicada";
   - resposta do Grimório não lida.
3. Responda em português, curto, com o resultado.

## 2. Renovar o chat
Um chat longo piora: esquece decisões, repete erro e deixa entrega parada.
- **Renove** depois da 2ª compactação, depois de ~4 h de trabalho, ou quando o Adrian disser que está ruim.
- **Para renovar:** rode `/renovar`. Ele escreve a NOTA (em andamento, próximo passo e armadilhas), gera o `ATUAL.md` e avisa o Adrian para abrir um chat novo. No chat novo, `/assumir`.
- **Compactação:** antes de cada uma, o hook gera o retrato sozinho, mas a NOTA só sai do `/renovar`.

## 3. A equipe (detalhes em `docs/agentes/EQUIPE.md`)
- **Partes do sistema:** `publicacao`, `builds`, `historias`, `metricas`, `app-e-bot`, `painel-e-vila`, `jogo-zombie`. Cada uma lê o seu `docs/sessoes/<parte>.md` antes de mexer.
- **`integrador`:** aplica as entregas do Codex que o vigia barrou: resolve conflitos, roda os testes e commita por caminho.
- **`conferente`:** NADA vai ao Adrian sem ele. Abre a tela de verdade (Chrome 390x844 para o app; captura para o launcher e o Godot), roda o caminho real em vez do dublê, e olha as imagens sobre fundo de contraste.
- **Codex** (`python -m remoto.delegar`): trabalho grande e bem especificado, em worktree. Quem aplica é o vigia; quem confere é o `conferente`.
- **Delegue em paralelo** quando as partes não mexem nos mesmos arquivos. Duas tarefas no `remoto/app/**` vão em sequência.

## 4. Leis (quebrar já custou caro)
- **Decisão do Adrian vira nó no Grimório** (`python -m remoto.decisoes adicionar ... --commit`), nunca pergunta solta. Resposta dele se lê NA HORA (`python -m remoto.decisoes leitor`).
- **Janela das postagens:** nada de reiniciar app/carteiro nem aplicar entrega de `post-12` a `post+18` min (a grade está em `random_builds/builds/grade.py`).
- **Commit SEMPRE por caminho.** Nunca `git commit` sem caminho, que leva tudo o que estiver no índice. Não commite os arquivos do Adrian (`palco/biblioteca/LICENCAS.md`, `.../projetil/fogo.tscn`, `.../efeitos/folhas/**`), nem arquivo que só mudou o fim de linha.
- **Teste verde ANTES do commit.** Testes com `TEMP=E:\tmp_pytest` e `PYTEST_ADDOPTS=-p no:cacheprovider` (o C: vive cheio).
- **Edite Python com Write/Edit, nunca com heredoc:** o shell come a barra invertida.
- **IA que falha duas vezes num papel sai do papel NA HORA.** O Gemini não julga sprite.
- **Pedido a uma IA diz o que é e para que serve** (jogo, objeto, uso, o que cada anexo é).
- **Esteira de sprites DESLIGADA:** o Adrian faz os sprites dele no Ateliê do app.
- **Claude proibido:** antes de trabalho automático, `python -m remoto.orquestrador claude status`.

## 5. Ao terminar uma tarefa
1. O `conferente` confere: tela, caminho real e imagens.
2. Commit por caminho, com o que foi medido na mensagem.
3. Reinicie o serviço afetado pelo coordenador (`python -m coordenador reiniciar <app|bot|carteiro|vila>`).
4. Feche o item na Mesa (`python -m remoto.orquestrador agente-fim <id>`) e limpe o delegado (`python -m remoto.delegar limpar --id X`).
5. Diga ao Adrian o resultado em poucas linhas, com o que foi conferido.
