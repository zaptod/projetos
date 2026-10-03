# A equipe (quem faz o quê)

O Adrian fala com **um** chat: o orquestrador. O orquestrador distribui o trabalho, como um gerente, e só responde depois de conferido.

```
Adrian ──► ORQUESTRADOR (chat principal)
              │  entende, divide, delega, cobra, responde
              ├──► partes do sistema (agentes Claude, .claude/agents/)
              │      publicacao · builds · historias · metricas
              │      app-e-bot · painel-e-vila · jogo-zombie
              ├──► Codex (remoto.delegar) — trabalho grande, em worktree
              │      └─► vigia do coordenador aplica ──► INTEGRADOR se parar
              ├──► INTEGRADOR — entrega parada, conflito, teste instável
              └──► CONFERENTE — tela, caminho real, imagens — antes do Adrian
```

## Quem é quem

| Funcionário | Onde | Quando chamar | O que devolve |
|---|---|---|---|
| orquestrador | o chat | sempre | resposta curta ao Adrian, já conferida |
| publicacao | agente | grade, postagem, ledger, conferência ledger x canal | conserto + teste |
| builds | agente | duelo, roleta, render, palco, launcher do Neural | conserto + teste |
| historias | agente | roteiro, imagens, narração, render das histórias | conserto + teste |
| metricas | agente | views, retenção, relatórios | número medido |
| app-e-bot | agente | telas e rotas do app, bot do Telegram | conserto + teste |
| painel-e-vila | agente | painel do PC, Vila, Oficina/Ateliê de sprites | conserto + teste |
| jogo-zombie | agente | o jogo de `E:\jogo_ZOMBIE` | conserto + teste |
| **integrador** | agente | entrega do Codex "olho"/não aplicada | entrega aplicada e commitada |
| **conferente** | agente | ANTES de dizer "pronto" ao Adrian | APROVADO ou defeitos com prova |
| Codex | `remoto.delegar` | tarefa grande e bem especificada | diff na worktree (o vigia aplica) |

## O fluxo de uma tarefa
1. **Entender.** Se for uma decisão do Adrian, ela vira nó no Grimório.
2. **Delegar:**
   - à parte dona (agente), ou ao Codex se for grande;
   - em paralelo quando não mexem nos mesmos arquivos;
   - o `remoto/app/**` vai em sequência.
3. **Acompanhar:**
   - vigia armado (espera em segundo plano) em todo trabalho longo;
   - entrega "olho" vai ao **integrador** na hora;
   - não deixe nada parado (chegou a ficar 4 h).
4. **Conferir:** o **conferente** olha tela, caminho real e imagens.
5. **Fechar:**
   - commit por caminho;
   - reiniciar o serviço fora da janela de postagem;
   - Mesa `agente-fim`;
   - `delegar limpar`.
6. **Responder:** poucas linhas, dizendo o que foi conferido.

## Renovação do chat
Veja o `CLAUDE.md` §2. `/renovar` fecha com a NOTA e o retrato, e `/assumir` abre o chat seguinte. O hook de início injeta o `docs/handoff/ATUAL.md`, e o de pré-compactação regenera o retrato.
