# Auditoria profunda 11–13/10/2026: o que ainda está aberto (verificado em 14/10/2026)

Os 34 relatórios desta pasta foram relidos defeito a defeito contra o código ATUAL do ramo `refactor/arquitetura` (`f670aa9`). Para cada defeito marcado "Confirmado":
- abri o arquivo e a linha citados (ou a função, quando a linha andou);
- rodei `git log -- <arquivo>` e li os diffs posteriores;
- reproduzi por script, numa pasta descartável, os casos que dava para provar sem tocar em banco, ledger ou estado reais.

Nenhum código foi alterado. Conserto em ramo não mesclado (`worktree-agent-ac362a0bfcc5f30f8`, `E:\projetos-wt\*`) **não** conta como consertado.

Os consertos, prontos para um agente executar sem reler os relatórios, estão em `consertos/<parte>.md`, na ordem de risco:

1. [publicacao](consertos/publicacao.md)
2. [builds](consertos/builds.md) (inclui banco e launcher)
3. [app-e-bot](consertos/app-e-bot.md)
4. [coordenador-e-delegacao](consertos/coordenador-e-delegacao.md)
5. [historias](consertos/historias.md)
6. [ias](consertos/ias.md)
7. [motor](consertos/motor.md)
8. [painel-e-vila](consertos/painel-e-vila.md)
9. [scripts-configs-panorama](consertos/scripts-configs-panorama.md)
10. [godot](consertos/godot.md)

## Números

| | Defeitos | Abertos | Consertados | Alarmes falsos |
|---|---:|---:|---:|---:|
| Relatórios de código (31 com "Confirmados") | 271 | 247 | 23 | 1 |
| Itens de código do `maquina.md` ("O que precisa de ação") | 11 | 5 | 4 | 2 |
| **Total** | **282** | **252** | **27** | **3** |

- **Por que 271 e não 281.** Os relatórios têm 265 títulos `### N.` em "Confirmados". Alguns títulos juntam defeitos distintos e foram contados à parte: `builds-conteudo` #8 virou 8a–8d, o `nf-recording-cli` trouxe 2 da auditoria rasa, e a tabela de chaves do `panorama-configs` virou 1 item. O "281" do handoff usou outra contagem.
- **Quase tudo continua aberto.** Fora da publicação (`a34b355` fechou 14 dos 21) e do Godot (`f5f8cd3` fechou 9 dos 13), nenhum commit depois de 11/10 mexeu nos arquivos citados. O que entrou depois disso foi só decisão e relatório.
- **Achados novos desta verificação (fora da contagem):**
  - **GOD-2 e GOD-3**, regressões do próprio `f5f8cd3`: lutador sem arma derruba o render inteiro, e o gatilho de evento da arma é apagado no quadro seguinte.
  - **Veto que falha aberto** (`publicacao.md`, "Observações"). Com `_pareceres.json` ilegível, os leitores engolem a exceção e a parte reprovada sai. Ficou improvável depois da gravação atômica do `a34b355`, mas o leitor deveria falhar fechado.
  - **`quem_narra`**: o prefixo "f" também erra. "filho" vira mulher (HIS, `roteiro` #8), além do que o relatório viu.

### Abertos por parte e gravidade

Gravidades usadas:
- **crítico:** perde dado sem volta;
- **alto:** publica errado;
- **médio:** trava a máquina, para trabalho, ou dá resultado errado mas recuperável;
- **baixo:** cosmético, mensagem errada ou código morto.

| Parte | Crítico | Alto | Médio | Baixo | Abertos | Consertados | Falsos |
|---|---:|---:|---:|---:|---:|---:|---:|
| publicacao | 0 | 1 | 3 | 3 | 7 | 14 | 0 |
| builds (inclui banco/launcher, identity) | 5 | 3 | 9 | 9 | 26 | 0 | 1 |
| app-e-bot | 0 | 0 | 15 | 18 | 33 | 0 | 0 |
| coordenador-e-delegacao | 1 | 0 | 18 | 8 | 27 | 0 | 0 |
| historias | 1 | 4 | 6 | 7 | 18 | 0 | 0 |
| ias (+2 do maquina) | 0 | 0 | 9 | 4 | 13 | 0 | 0 |
| motor (nf-*) | 1 | 0 | 25 | 46 | 72 | 0 | 0 |
| painel-e-vila | 0 | 1 | 13 | 9 | 23 | 0 | 0 |
| scripts-configs-panorama (+9 do maquina) | 0 | 1 | 19 | 9 | 29 | 4 | 2 |
| godot | 0 | 0 | 2 | 2 | 4 | 9 | 0 |
| **Total** | **8** | **10** | **119** | **115** | **252** | **27** | **3** |

O número de itens em cada `consertos/*.md` é menor que o de defeitos, porque defeitos com o mesmo conserto viraram um item só.

### Críticos (perde dado), 8 defeitos em 6 itens

| Item | Defeito | Onde |
|---|---|---|
| BLD-1 | O launcher grava por cima do banco a lista que carregou ao abrir: apaga os personagens que a roleta inseriu enquanto ele estava aberto. E todo salvar reescreve TODOS os registros pelo modelo: `genero` some de todos os personagens (71 na cópia do banco real), e `tipo_projetil`, `velocidade_projetil` e `tipo_orbital` somem das armas. | `neural_fights/data/database.py:1208-1217`, `ui/view_chars.py:1286,1310`, `ui/view_armas.py:1135` |
| BLD-2 | A inserção da roleta lê e grava em duas travas separadas: duas builds em paralelo perdem uma. A prova com dois processos reais perdeu uma. | `neural_fights/tools/gerador_database.py:686,708`, `random_builds/builds/nf_bridge/exporter.py:140` |
| BLD-3 | `remover_arma` apaga sem cópia, e duas perdas no mesmo segundo sobrescrevem a cópia anterior. | `database.py:1063`, `:889-903` |
| MOT-101 | "🎲 Gerar Roster" do torneio troca o banco inteiro num clique, sem perguntar. A cópia `_backup-*` sai, mas ninguém é avisado. É o mesmo conserto do BLD-1 (c). | `neural_fights/ui/view_torneio.py:356-368` |
| COO-1 | `delegar limpar_orfas` apaga a worktree VIVA de tarefa de outro repositório (`E:\jogo_ZOMBIE`), com o trabalho não commitado do Codex. | `remoto/delegar.py:2183` |
| HIS-1 | `roteiro.json` e `biblia.json` são gravados por cima, sem temporário: uma queda no meio corrompe a série. | `historias/contos/roteiro/roteiro.py:930,1112`, `gerar.py:39` |

### Altos (publica errado), 10 defeitos

| Item | Defeito |
|---|---|
| PUB-1 | O clique no YouTube foi dado, mas a marca "a conferir" falha: o vídeo volta à fila e pode ser repostado. O `a34b355` cobriu só o caso comum. |
| PNL-1 | Duplo clique no painel dispara dois processos, inclusive dois PUBLICAR (`painel/processos.py:50`). |
| BLD-4 | Hífen, apóstrofo e espaço furam a moderação do nome pedido: "Pu-ta", "Me-rda" e "Fu-ck" saem aceitos para o vídeo. |
| BLD-5 | O classificador de reação lê `rarity` ao contrário: o valor mais comum vira "RARO · 0% de chance" na tela. |
| BLD-6 | Três empates seguidos viram vitória inventada do primeiro lutador (`tournament/runner.py:462`). Latente: 0 de 217 lutas tiveram empate. |
| HIS-2 | O Gemini fora do modelo forte escreve o roteiro calado. A decisão `b339bbb` (pular para o próximo provedor e avisar) não foi implementada. |
| HIS-3 | Num chat com turnos, a pergunta devolvida à caixa faz a resposta do turno ANTERIOR ser lida como nova. |
| HIS-4 | Bíblia com menos partes que o pedido passa, e a retomada pede "PARTE 6 de 5". |
| HIS-5 | Arquivo ilegível acima de 10 KB conta como imagem pronta: os dois `except` devolvem True. |
| SCR-P7 | O ledger de histórias sempre grava `"public"`: a chave é lida na raiz do config em vez de `youtube.visibilidade`. Latente: hoje o config diz `public`. |

### Médios que param a máquina ou o trabalho (os que mais doem)

- **Coordenador.**
  - COO-5: uma leitura no instante do `os.replace` derruba o coordenador inteiro.
  - COO-6: `coordenador pedir` morre por `TimeoutError` e o pedido não é registrado.
  - COO-4: `saudes_ruins` não zera, e o app novo é morto 5 s depois de subir.
  - COO-3: reinício recusado sai como "executado".
  - COO-14: com pid reaproveitado, o coordenador não sobe e sai calado.
- **Entregas.**
  - COO-7: `aplicar` marca APLICADA com o `git apply -3` falhando.
  - COO-2: pedido preso em "entregue", ou "conferido" sem commit.
  - COO-10: ficha "rodando" com pid reaproveitado nunca fecha.
- **Bot e app.**
  - APP-9 e APP-10: sem rede, o bot gira sem dormir ou sai.
  - APP-11: erros somem do aviso (do 6º em diante, e os anteriores a uma religada).
  - APP-13: uma linha ruim apaga a fila de avisos.
  - APP-1: em-voo preso, ou `fim.json` gravado com o `main.py` vivo.
- **Carteiro.**
  - IAS-5: `gravar_casa` sem nova tentativa mata o carteiro.
  - IAS-1: a cota do Gemini não tira ele do rodízio.
  - IAS-3: a prévia de meia resolução entra calada como imagem final.
- **Histórias.**
  - HIS-8: serviço do dia marcado feito com etapa falhada.
  - HIS-9: `--saida` trancado derruba a tarefa sem log.
- **Máquina.**
  - SCR-7: rodada pendurada segura a tarefa 72 h.
  - SCR-1: depois de religar o PC nada volta sem logon.
  - SCR-M8: reinício por "código atualizado" dentro da janela das postagens. É a decisão `9cec584`, ainda não implementada.
  - SCR-3: o CI nunca roda.
  - SCR-2: `testar.py` deixa fora o coordenador e 784 testes do remoto.

## Alarmes falsos (3)

- **`builds-conteudo.md` #5** ("empate vira `None` na legenda e derruba `torneio_resultado`"). Nenhum caminho entrega `None`: `runner._evento_base:462` faz `vencedor = bruto["vencedor"] or p1`. O defeito real é o contrário: vitória inventada (BLD-6).
- **`maquina.md` #10** (capa 403 gastando cota). Já estava consertado em `6a18d94` (05/10): `capa_bloqueada()` pula o resto do dia depois de um 403.
- **`maquina.md` #17** (traceback 10053 no app). Já estava consertado em `9989b80` (05/10, `CLIENTE_SAIU`). O último traceback é de 05/10.

Correções parciais (o item continua aberto no resto):
- `nf-core-a` #7: a raiva decai (`emotions.py:104`); só falta o teto.
- `nf-core-b` C9: as 7 skills sem fonte estão fora da rotação de propósito (`SKILLS_FORA_DE_ROTACAO`).
- `nf-recording-cli` #11: `executar_teste_stress` tem chamador (`cli/headless.py:171`).
- `nf-recording-cli` #9a: o duplo KO não está provado.
- `coordenador` #7: não manda 1.440 avisos por dia, porque o porteiro segura. São só 35 mil linhas de log.
- `scripts` #5: no Python 3.14 não levanta, só perde a mensagem.
- `scripts` #9: `catalogo.py` e `ias/correio.py` já honram a variável.
- MOT-101: o "Gerar Roster" deixa, sim, a cópia `_backup-*`.

## Decisões do Adrian

### Já tomadas e ainda não implementadas (não perguntar de novo, só fazer)

| Decisão | Commit | Vira |
|---|---|---|
| Build que saiu só no TikTok vai ao YouTube depois (mesma regra das histórias) | `d104da1` | PUB-2 |
| Gemini sem o modelo forte: pular para o próximo provedor e avisar no Telegram | `b339bbb` | HIS-2 |
| Reiniciar serviços só quando pedido (não a cada código mudado) | `9cec584` | COO-3 e SCR-M8. Existe só no ramo WIP `5b087cb`, não mesclado nem testado. |

### Já executadas

- Desligar as três tarefas antigas e apagar `retomar_codex` (`b1ef6f7`).
- `main` recebe o ramo (`d421b98`).
- Enviar ao GitHub (`144cd45`). Os runs do CI desse push falharam em 0 s (SCR-3).
- Apagar o lixo (`ad54bf7`): **em parte**. Sobram `E:\tmp_pytest` (7.823 entradas), as worktrees destacadas `wt_bsp`/`wt_pub` e 4 pastas soltas em `E:\projetos-wt`. A parte que pede administrador está pendente.

### Novas, de produto (cada uma deve virar nó no Grimório antes do conserto correspondente)

**Builds e banco**

1. **"🎲 Gerar Roster" no launcher** (BLD-1, MOT-101): perguntar e substituir com cópia, acrescentar ao catálogo, gravar num catálogo separado só do torneio, ou tirar o botão (o painel já tem "Regenerar database")?
2. **Empate persistente** (BLD-6): desempatar por HP restante, mostrar "empate" no vídeo e no ledger, ou descartar a luta e sortear outra? O padrão técnico é falhar sem publicar.
3. **Nome pedido pelo comentarista** (BLD-22): vale a regra "não termina em qualidade" ("Kael o Sombrio" recusado) ou o nome é livre?

**Histórias e IAs**

4. **Série cujo plano veio com menos partes que o pedido** (HIS-4): sai mais curta ou é descartada?
5. **Imagem de referência entre geradores** (HIS-13): volta, ou o módulo morto é apagado?
6. **Prévia do Gemini quando o original não baixa** (IAS-3): aceitar a imagem de meia resolução (foi 47 de 89 em 12/10) ou recusar e gerar de novo, gastando cota?

**Publicação e painel**

7. **Visibilidade no ledger** (SCR-P7): vale a do config ou a que o publicador realmente usou? A recomendação é a do publicador.
8. **`tiktok.postar_automatico: false` dos builds** (SCR-PT): passa a valer também para a grade, ou a chave sai? Hoje a grade posta sempre.
9. **Botões "Login no PicassoIA", "Login no Digen" e "Vídeo do payoff (Digen)" na página Vídeos**, depois das decisões `picasso-fora-da-roda` e `digen-plano-free`: tirar ou manter?

**Máquina**

10. **Religar o PC** (SCR-1): logon automático com bloqueio de tela, ou só um aviso "PC religou"? O aviso precisa da senha dele numa tarefa "conectado ou não". Ligar o histórico do Agendador (SCR-8) precisa de administrador.

**Motor e live**

11. **Quirks** (MOT-30): implementar os 29 efeitos prometidos ou tirá-los do sorteio?
12. **Atordoamento** (MOT-5): pausa o relógio de ataque (como hoje) ou corre em paralelo? Muda o ritmo de toda luta.
13. **Lava do Vulcão/Inferno** (MOT-32): ligar o dano das poças que o catálogo promete, ou tirar a promessa?
14. **Som da vitória** (MOT-27): hoje toca a abertura da arena quase muda. Que som deve tocar? Só ele julga som.
15. **Volume dos golpes depois do conserto do pan** (MOT-13): os golpes caem até 1,8×; ele precisa ouvir antes de valer nos vídeos.
16. **Live: `!arena` com dois pagantes no mesmo round** (MOT-103): vale o primeiro ou o último? E o comando pago que não coube: recusa com reembolso na tela, ou fica guardado até o cooldown passar?
17. **Estatísticas do torneio** (MOT-124): preencher KO mais rápido, luta mais longa e mais agressivo, ou tirar do save?
18. **Moderação da live** (MOT-129): ligar `definir_banimento` a um comando de moderador, ou remover?

Pendente no Grimório, sem mudança: ligar o duelo de produção pelo palco (`builds/duelo-palco-sem-corrente`). GOD-1 a GOD-3 só aparecem em vídeo depois dessa chave.

## Operação (não é código; medido em 14/10 ~01:30, só leitura)

| Item | Situação |
|---|---|
| DNS da operadora | Resolvido: Ethernet em 1.1.1.1 e 8.8.8.8. |
| Gemini deslogado | Não dá para afirmar sem abrir o perfil. A última queixa de login é de 11/10. |
| Uso do Claude | Semana em 44% (era 88% em 11/10). `max_paralelo` continua 6. |
| Chrome | 155, com o patchright feito para o chromium 151. Vigiar. |
| Disco | C: com 13 GB livres. |

## Ordem sugerida de conserto

1. **Perda de dado.**
   - BLD-1, BLD-2 e BLD-3 com MOT-101: um lote só no `database.py`, com teste de corrida entre dois processos. Precisa antes da decisão 1.
   - HIS-1.
   - COO-1.
2. **Publica errado.** PUB-1, PNL-1, BLD-4, HIS-2 a HIS-5. Em seguida BLD-5, BLD-6 (precisa da decisão 2) e SCR-P7.
3. **Para a máquina.** Coordenador (COO-2 a COO-7, COO-14), bot (APP-9 a APP-13), carteiro (IAS-1, IAS-3, IAS-5) e SCR-M8, que é a decisão `9cec584`.
4. **O resto, por parte.** O motor vai num lote de simulação com re-pino e medição do ledger de qualidade.

Regras de todo lote:
- aplicar fora da janela das postagens;
- teste verde antes (`TEMP=E:\tmp_pytest`, `PYTEST_ADDOPTS=-p no:cacheprovider`);
- commit por caminho;
- reiniciar o serviço afetado pelo coordenador.
