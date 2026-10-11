# Auditoria profunda — Motor: ferramentas (Ateliê, catálogo, consumo) — 11/10/2026

## Examinado

- `__init__.py` — 0 funções/classes lidas; delimita o pacote de ferramentas sem reexportar scripts.
- `analise_armas.py` — 4 funções/classes lidas; CLI legada do gate de geometria das armas.
- `atelie_animacoes.py` — 22 funções/classes lidas; persiste folhas e contratos do Ateliê, monta catálogo e prévia.
- `auditoria_comandos.py` — 19 funções/classes lidas; valida por AST o catálogo de comandos de live e suas evidências.
- `auditoria_personalidades.py` — 11 funções/classes lidas; valida por AST eixos, referências e despacho dos instintos.
- `auditoria_skills.py` — 21 funções/classes lidas; audita contratos de skills e manifestos de evidência.
- `catalogo_animacoes.py` — 20 funções/classes lidas; gera e valida o catálogo de animações do palco.
- `catalogo_vila.py` — 5 funções/classes lidas; deriva as peças da Vila a partir do inventário.
- `command_runtime_evidence.py` — 0 funções/classes lidas; manifesto literal de testes dos comandos.
- `consumo_atelie.py` — 4 funções/classes lidas; declara consumidores comprovados das peças do Ateliê.
- `diagnostico_hitbox.py` — 16 funções/classes lidas; gate estrutural do banco e da implementação de hitboxes.
- `gerador_database.py` — 14 funções/classes lidas; gera e persiste banco diverso de personagens e armas.
- `migrar_database.py` — 3 funções/classes lidas; migra aliases legados do banco em dry-run ou aplicação explícita.
- `qualidade_luta.py` — 30 funções/classes lidas; executa corpora, métricas e gates de qualidade de lutas.
- `resumo_banco.py` — 2 funções/classes lidas; imprime um resumo do banco para o painel.
- `skill_check.py` — 11 funções/classes lidas; exercita individualmente cada skill no motor real.
- `skill_inspector.py` — 11 funções/classes lidas; CLI para consultar contratos, cobertura e checagem de skills.
- `skill_runtime_evidence.py` — 0 funções/classes lidas; manifesto literal de evidências de skills.
- `youtube_oauth.py` — 13 funções/classes lidas; realiza a autorização OAuth e grava as credenciais do canal.

## Confirmados (do mais grave ao menos)

### 1. Ateliê aceita números não finitos e grava JSON que o cliente não consegue ler — gravidade: média

- Onde: `atelie_animacoes.py:56` (`validar`) e `:100` (`salvar`)

- O defeito: `float("nan")` passa pelas verificações de `fps`, `escala`, `rotacao` e das durações dos quadros, pois comparações com NaN não são verdadeiras. Em seguida `json.dumps` grava o literal `NaN`, que não pertence ao JSON e é recusado por `JSON.parse`/leitores estritos.

- Quando acontece: uma chamada autenticada a `/api/animacoes/salvar` com, por exemplo, `dados.fps: "nan"` é aceita e deixa `animacao.json` inválido; a resposta também contém NaN e a tela pode reportar falha mesmo tendo persistido o artefato quebrado. O palco deixa de poder carregar essa animação.

- Prova: executei, em diretório temporário fora do repositório, `python -c "... atelie.salvar(..., {'fps':'nan', ...}); print(animacao_json)"`. A saída continha `"fps": NaN`; a mesma constante é inválida para um parser JSON estrito.

- Conserto sugerido: exigir `math.isfinite()` para todos os números convertidos e serializar com `allow_nan=False`.

### 2. Um ajuste válido no endpoint pode derrubar toda a árvore do Ateliê — gravidade: média

- Onde: `atelie_animacoes.py:314` (`salvar_ajustes`) e `:346` (`arvore`)

- O defeito: `salvar_ajustes` só converte `novas` em lista, sem exigir que cada entrada seja objeto. `arvore` pressupõe depois que toda entrada tem `.get`, deixando uma configuração gravada pelo próprio endpoint tornar `GET /api/animacoes/arvore` um erro 500.

- Quando acontece: o cliente autenticado envia `{"novas":["nao-e-objeto"],"escondidas":[]}` a `/api/animacoes/ajustes`; o POST responde sucesso e a próxima abertura do Ateliê falha antes de listar peças.

- Prova: executei, em diretório temporário, `python -c "...; atelie.salvar_ajustes({'novas':['nao-e-objeto'],'escondidas':[]}); atelie.arvore()"`. Saiu `AttributeError: 'str' object has no attribute 'get'` em `arvore`, linha 350.

- Conserto sugerido: validar o schema de `novas` e `escondidas` antes de gravar e tratar entradas inválidas na leitura como erro recuperável.

### 3. Recusar o consentimento do YouTube deixa o OAuth aguardando para sempre — gravidade: baixa

- Onde: `youtube_oauth.py:191` (`_receber_codigo`)

- O defeito: o servidor local responde a `?error=access_denied`, mas não registra o erro nem encerra o laço; ele só termina se surgir `code`. Quem cancela/recusa a tela do Google fica com o comando travado até interrompê-lo manualmente.

- Quando acontece: após o usuário negar a autorização, o Google retorna ao loopback com `error=access_denied`; a página diz para tentar de novo, mas o processo ainda segura a porta e não retorna código de erro.

- Prova: executei em loopback isolado `python -c "... Thread(target=y._receber_codigo,...); urllib.request.urlopen('http://127.0.0.1:PORT/?error=access_denied'); print(thread.is_alive())"`. A resposta foi `Sem codigo na resposta - tente de novo.` e `aguardando_depois_do_erro= True`.

- Conserto sugerido: capturar `error`/`error_description`, encerrar o servidor e devolver uma falha tratada ao `main`.

## Não confirmados

- `atelie_animacoes.py:100` (`salvar`) e `:127` (`desfazer`): PNG, JSON e histórico são trocados em operações separadas, portanto uma disputa entre dois salvamentos ou um bloqueio do Windows pode deixar versões desencontradas. Não classifiquei como confirmado porque não forcei uma trava/condição de corrida real sem instrumentar as operações suspeitas.

- `youtube_oauth.py:273` (`main`): `--host` é exposto como configurável, mas `_receber_codigo` sempre escuta em `127.0.0.1`; hosts alternativos podem não receber retorno. Não confirmei por não abrir navegador nem rede externa.
