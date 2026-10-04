# Conferência do pedido-d23fa2c3 (som real das 15 builds sai da fila)

**DEFEITOS (menores).** A decisão foi aplicada: o item saiu da fila e nada o põe de volta sozinho. O que sobra está no doc e no commit; nenhum desses defeitos reabre o re-render hoje.

## Conferido e certo
- **Fila:** o retrato do handoff, medido do disco às 13:48 de 04/10 (depois do commit d39860c, das 13:47:50), mostra `fila (1): 6a229e63 [builds] Corrente F4–F6`. O `b0d22ef8` não está lá, e a Corrente continua.
- **Nada religa sozinho:** em `coordenador/` e `remoto/`, nenhum código cria o item "Som real nas 15". As únicas menções estão em comentários (`remoto/avisos.py:7`, `coordenador/vigia_trabalho.py:744,796`). O `fila_adicionar` do cérebro está em `SEMPRE_PROPOSTA` (`coordenador/cerebro.py:57`), então só entra se o Adrian aprovar.
- **Agendador do Windows:** `schtasks /query /fo LIST /v` não tem nenhuma ação com `som`, `vigia_som` ou `som-da-luta`. As ações do projeto são `bot.cmd`, `coordenador.cmd`, `historias/auto.cmd`, `postar.cmd`, `random_builds/gerar.cmd`, `app_celular.cmd`, `vila_flutuante.cmd` e `outputs/retomar_codex.py`.
- **"As novas já nascem com o som real":** confere. `random_builds/config/editing.json:303` tem `som_da_luta.real: true` e `sintetizado_de_reforco: false`.
- **As 15 continuam publicáveis:** a guarda da publicação só barra a luta MUDA (`builds/publicar/audio.py:272`, `barrar_luta_muda`), e o sintetizado tem som.

## Defeitos (do mais grave ao menos grave)
1. **O §7 do doc ainda manda re-renderizar uma das 15.** `docs/sessoes/builds.md:493-495` diz "Com o som aprovado, o re-render com o som real ...: `python main.py som-da-luta duelo_00012 ... duelo_00023 generation_00029`". Só que `generation_00029` (A e B) faz parte das 15 que a decisão manda NÃO re-renderizar. A linha 127 (referência de comandos) também usa `generation_00029` como exemplo de `som-da-luta`.
   - Quem seguir o §7 refaz o que o Adrian tirou da fila. Os duelos `00012`–`00021` já foram ao ar e os `00022`/`00023` já foram refeitos, então esse comando inteiro ficou obsoleto.
   - Conserto: marcar o parágrafo como histórico/superado pela `som-real-15-builds` e tirar `generation_00029` do comando (ou o comando inteiro).
2. **A nota entrou no meio de um raciocínio.** Ela foi inserida entre o parêntese "(Retrato de 28/09; o de 30/09 ...)" (l. 479-482) e "Os outros 36 estão com o sintetizado" (l. 490). Esses "36" são 38 menos os 2 mudos do retrato de 28/09, mas, logo depois da nota, a frase parece dizer "36 além dessas 15".
   - Conserto: pôr a nota DEPOIS do parágrafo das l. 490-500 (fim do §7), ou começar a l. 490 com "Em 28/09, os outros 36 ...".
3. **Arquivo de rascunho commitado na raiz.** O commit d39860c levou `.conf_som_real.md` (o briefing do conferente) para a raiz do repositório. Isso está fora dos caminhos permitidos (`remoto/**`, `coordenador/**`, `docs/**`), e o repositório vai ser mostrado a outras pessoas. O mesmo aconteceu com `.tarefa_imagens_heranca.md` em d5f9a45: os dois aparecem em `git ls-files`.
   - A mensagem do commit é a fala de espera do trabalhador: "Ainda sem saída; aguardo a notificação do conferente." Não descreve a mudança.
   - Causa provável: o vigia commita tudo o que mudou na worktree e usa a última fala como mensagem.
   - Conserto: `git rm --cached` dos dois, e um padrão no `.gitignore` ou um filtro no vigia para `.conf_*.md`, `.tarefa_*.md` e `.codex_tarefa.md`.

## O que não conferi
- Não rodei `python -m remoto.orquestrador fila listar`: a fila mora em `%LOCALAPPDATA%`, que esta tarefa proíbe ler. A prova da fila é o retrato do handoff de 13:48.
- Não há tela, imagem nem vídeo nesta entrega (só fila + doc), então não houve captura.
