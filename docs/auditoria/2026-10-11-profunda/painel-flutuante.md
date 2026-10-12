# Auditoria profunda — Vila flutuante — 11/10/2026

## Examinado

- `painel/flutuante/__init__.py` — 0 funções/classes lidas; define o contrato de somente leitura da Vila.
- `painel/flutuante/__main__.py` — 2 funções/classes lidas; inicia a janela, mutex e modo de prova.
- `painel/flutuante/arte.py` — 48 funções/classes lidas; desenha o mundo, prédios, habitantes e enfeites.
- `painel/flutuante/arte_pronta.py` — 39 funções/classes lidas; lê, indexa e adapta sprites aprovados para PC e celular.
- `painel/flutuante/caminhos.py` — 16 funções/classes lidas; descobre raízes e caminhos de dados.
- `painel/flutuante/captura.py` — 4 funções/classes lidas; captura uma única janela via PrintWindow.
- `painel/flutuante/cena.py` — 29 funções/classes lidas; anima a Vila no Canvas e invalida a arte aprovada.
- `painel/flutuante/coletor.py` — 21 funções/classes lidas; coleta disco, processos, Agendador e previsão fora da UI.
- `painel/flutuante/dados.py` — 38 funções/classes lidas; interpreta diário, travas, processos, ledgers e resumo.
- `painel/flutuante/demo.py` — 8 funções/classes lidas; fornece estado determinístico para demonstrações.
- `painel/flutuante/janela.py` — 87 funções/classes lidas; monta a interface, painéis, ciclo de dados e ciclo de animação.
- `painel/flutuante/paisagem.py` — 4 funções/classes lidas; compõe e converte a Vila horizontal do celular.
- `painel/flutuante/preferencias.py` — 13 funções/classes lidas; lê/grava preferências e caixa-preta da janela.
- `painel/flutuante/previsao.py` — 4 funções/classes lidas; consulta as filas em subprocesso sem vistoria/publicação.
- `painel/flutuante/retrato.py` — 13 funções/classes lidas; compõe e converte a Vila vertical do celular.
- `painel/flutuante/sinal.py` — 6 funções/classes lidas; faz o segundo lançamento pedir que a instância viva apareça.
- `painel/flutuante/tarefa.py` — 22 funções/classes lidas; gera e administra a tarefa de recuperação da Vila.
- `painel/flutuante/tarefas.py` — 7 funções/classes lidas; lê e classifica tarefas do Agendador sem alterá-las.
- `painel/flutuante/vida.py` — 29 funções/classes lidas; calcula caminhos, estados e animações dos habitantes.
- `painel/flutuante/guia/__init__.py` — 0 funções/classes lidas; documenta o contrato do guia das IAs.
- `painel/flutuante/guia/__main__.py` — 3 funções/classes lidas; inicia o guia e seus modos de prova.
- `painel/flutuante/guia/colado.py` — 37 funções/classes lidas; analisa colagens e persiste a fila do guia.
- `painel/flutuante/guia/janela.py` — 58 funções/classes lidas; implementa a UI, confirmação e persistência do guia.
- `painel/flutuante/arte_vila/cenario/caminho_terra.json` — metadado lido; descreve a textura aprovada de caminho.
- `painel/flutuante/arte_vila/cenario/chao_grama.json` — metadado lido; descreve a textura aprovada de grama.
- `painel/flutuante/arte_vila/predios/casa.json` — metadado lido; descreve a arte aprovada da casa.
- `painel/flutuante/arte_vila/predios/chatgpt.json` — metadado lido; descreve a arte aprovada do prédio ChatGPT.
- `painel/flutuante/arte_vila/predios/deepseek.json` — metadado lido; descreve a arte aprovada do prédio DeepSeek.
- `painel/flutuante/arte_vila/cenario/caminho_terra.png` — recurso binário referenciado pelo metadado e carregador; sem função a auditar.
- `painel/flutuante/arte_vila/cenario/chao_grama.png` — recurso binário referenciado pelo metadado e carregador; sem função a auditar.
- `painel/flutuante/arte_vila/predios/casa.png` — recurso binário referenciado pelo metadado e carregador; sem função a auditar.
- `painel/flutuante/arte_vila/predios/chatgpt.png` — recurso binário referenciado pelo metadado e carregador; sem função a auditar.
- `painel/flutuante/arte_vila/predios/deepseek.png` — recurso binário referenciado pelo metadado e carregador; sem função a auditar.

## Confirmados (do mais grave ao menos)

### 1. Metadado de sprite válido, mas inválido na estrutura, encerra a animação — gravidade: média

- Onde: `painel/flutuante/arte_pronta.py:458` (`folha`), alcançada por `painel/flutuante/janela.py:1090` (`_animar`)

- O defeito: `folha()` converte diretamente os dois valores de `grade` com `int()` sem validar estrutura ou conteúdo. O ciclo de animação só trata `tk.TclError`; portanto o `ValueError` escapa antes de ele agendar o próximo `after` e a Vila deixa de animar até ser reaberta.

- Quando acontece: a esteira grava, por falha parcial/corrupção, um `.json` parseável com `{"grade": ["corrompida", 1]}` ao lado de uma folha PNG válida → ao desenhar o habitante, a exceção interrompe o ciclo.

- Prova: em pasta temporária, criei PNG 8×8 e inventário mínimos, gravei esse JSON e executei `arte_pronta.folha("habitantes/bot/andar.png")`; saída: `ValueError invalid literal for int() with base 10: 'corrompida'`.

- Conserto sugerido: validar `grade`, ciclos e quadros, retornando grade 1×1/fallback para metadado inválido; também impedir que exceção não-Tk pare o reagendamento da animação.

### 2. O Guia avança mesmo depois de perder a mensagem do usuário — gravidade: média

- Onde: `painel/flutuante/guia/janela.py:575` (`proximo`)

- O defeito: `proximo()` chama `enviar_mensagem()`, ignora seu retorno e grava o marcador `proximo` em seguida. Se a primeira escrita falhar transitoriamente (arquivo bloqueado, disco cheio) e a segunda funcionar, o agente recebe a ordem de avançar sem a mensagem que deveria precedê-la.

- Quando acontece: há texto no campo de mensagem → a gravação da mensagem retorna `False` → a gravação seguinte do marcador funciona → só `proximo` fica em `colado.jsonl`.

- Prova: executei `JanelaGuia.proximo` sem dublar a função suspeita, com a primeira gravação simulando a falha transitória do disco e a segunda usando `colado.gravar_item` real em pasta temporária. Saída: `proximo ['proximo']`.

- Conserto sugerido: se `enviar_mensagem()` retornar `None`, parar e não gravar `proximo`.

### 3. O verificador do Agendador declara saudável uma tarefa sem supressão de diálogo — gravidade: baixa

- Onde: `painel/flutuante/tarefas.py:86` (`examinar_uma`)

- O defeito: o ramo sem `//B` retorna estado `oculta`, que `examinar()` considera correto. Assim, a própria razão indicada no texto — erro de script abrir caixa de diálogo — não entra em `problemas`, e o selo afirma que todas as tarefas estão ocultas.

- Quando acontece: ação `wscript.exe "C:/nf/oculto.vbs" "C:/nf/postar.cmd"` com ambos os arquivos existentes, mas sem `//B` → `ok=True` e selo verde, embora falhas do VBS passem a abrir diálogo.

- Prova: executei `tarefas.examinar` com essa única ação e verificador de existência realista; saída: `True tarefas ocultas ✓ 1/1 wscript sem //B (erro de script abriria caixa de diálogo)`.

- Conserto sugerido: classificar ausência de `//B` como `desconhecida`/`quebrada` (ou outro estado que entre em `problemas`).

### 4. Arte de emote aprovada depois da abertura nunca invalida o cache — gravidade: baixa

- Onde: `painel/flutuante/arte.py:946` (`emote`) e `painel/flutuante/cena.py:90` (`_conferir_arte`)

- O defeito: `emote()` é `lru_cache`, mas a invalidação de arte da cena não chama `emote.cache_clear()`. A assinatura muda e o carregador encontra a nova imagem, porém o emote já calculado continua sendo devolvido até reiniciar o processo.

- Quando acontece: a Vila já mostrou um emote de fallback → uma arte aprovada `interface/balao_emote.png` entra na pasta → a checagem de assinatura roda → o novo asset não aparece nos emotes já cacheados.

- Prova: em pasta temporária, gerei o fallback, acrescentei PNG vermelho aprovado, executei `arte_pronta.conferir()` e chamei novamente `arte.emote`. Saída: `True (255, 0, 0, 255)` — os bytes antes/depois permaneceram iguais (`True`), embora o carregador já lesse o pixel vermelho do novo PNG.

- Conserto sugerido: limpar o cache de `emote` (e os caches de enfeites afetados) quando `arte_pronta.conferir()` detectar mudança.

## Não confirmados

- `painel/flutuante/arte_pronta.py:636` e `:686` escrevem PNG/JSON do atlas do celular diretamente no destino final, sem arquivo temporário nem trava. Há risco de duas requisições simultâneas servirem arquivo parcial, mas não reproduzi uma corrida do servidor HTTP sem abrir o app nem alterar a saída real.
- `painel/flutuante/cena.py:90` recalcula o fundo quando uma prop animada é aprovada, mas não recria `self._props_animados` nem os itens do Canvas. A leitura indica que a prop pode sumir até reiniciar; não confirmei sem uma sessão Tk/celular real.
