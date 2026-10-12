# Auditoria profunda — Imagens e vídeo das histórias — 11/10/2026

## Examinado

- `historias/contos/imagens/__init__.py` — 0 funções/classes; marcador vazio do pacote.
- `historias/contos/imagens/composicao.py` — 6 funções/classes lidas; detecta colagem e remove moldura de imagens.
- `historias/contos/imagens/cota.py` — 9 funções/classes lidas; persiste e consulta o contador diário do PicassoIA.
- `historias/contos/imagens/fila.py` — 25 funções/classes lidas; monta prompts e determina/guarda o estado das imagens de cena.
- `historias/contos/imagens/reescritor.py` — 12 funções/classes lidas; reescreve prompts recusados usando um LLM em thread própria.
- `historias/contos/imagens/referencia.py` — 8 funções/classes lidas; implementa âncora visual, estilo congelado e divisão por parte.
- `historias/contos/imagens/worker.py` — 22 funções/classes lidas; pede, recebe, comprova e grava imagens pelo correio ou pelo caminho legado.
- `historias/contos/video/__init__.py` — 0 funções/classes; marcador vazio do pacote.
- `historias/contos/video/capa.py` — 13 funções/classes lidas; compõe e grava capas verticais.
- `historias/contos/video/formato.py` — 7 funções/classes lidas; resolve e grava o formato fixado da história.
- `historias/contos/video/fundo.py` — 3 funções/classes lidas; escolhe deterministicamente o trecho de vídeo de fundo.
- `historias/contos/video/plano.py` — 4 funções/classes lidas; lê os tempos medidos das cenas ou os estima pelo roteiro.
- `historias/contos/video/renderer.py` — 21 funções/classes lidas; renderiza segmentos, tela dividida, áudio e legenda karaoke.
- `historias/contos/video/timeline.py` — 11 funções/classes lidas; produz plano, cortes visuais e SRT a partir de roteiro e voz.
- `historias/contos/video/velocidade.py` — 8 funções/classes lidas; acelera a voz e mantém plano/palavras no mesmo relógio.

## Confirmados (do mais grave ao menos)

### 1. Cena sem prova de origem é considerada pronta — gravidade: alta

- Onde: `historias/contos/imagens/fila.py:126` (`utilizavel`) e `:378` (`estado`)
- O defeito: a prontidão depende só de existir um arquivo grande com proporção válida; o registro e `prova.comprovada` não participam. O worker grava o arquivo antes de `fila.registrar`, portanto uma queda nesse intervalo deixa no disco uma imagem sem prova que a próxima rodada aceita e pode renderizar.
- Quando acontece: processo cai após copiar/baixar uma imagem e antes de registrar `imagens.json` → a imagem fica sem prova, mas a cena deixa de ser pendente.
- Prova: em diretório temporário fora do repositório, criei uma PNG válida de 30.168 bytes sem `imagens.json`, direcionei `fila.OUTPUTS` para lá e rodei `fila.estado(...)`; saída: `bytes= 30168 pronta= True prova= None`.
- Conserto sugerido: só marcar pronta quando o arquivo for utilizável **e** o registro da cena tiver `prova.comprovada`; trate o arquivo órfão como pendente.

### 2. Arquivo corrompido maior que o mínimo passa como imagem utilizável — gravidade: média

- Onde: `historias/contos/imagens/fila.py:78` (`vertical`), `:102` (`proporcao_ok`) e `:126` (`utilizavel`)
- O defeito: ambos os validadores de proporção retornam `True` ao não conseguir abrir a imagem. Assim, tamanho acima de 10 KB basta para um PNG/JPEG ilegível passar como pronto.
- Quando acontece: download truncado, página de erro salva como `.png` ou arquivo corrompido com mais de 10 KB → a geração não o refaz; o renderer só depois falha ao abrir e troca a cena por cartão de texto.
- Prova: em diretório temporário, gravei 11.200 bytes de `nao-e-uma-imagem` como `cena_01.png` e executei as funções reais. Saída: `vertical= True`, `proporcao_ok= True`, `utilizavel= True`.
- Conserto sugerido: em erro de abertura, `vertical`/`proporcao_ok` devem devolver `False` (ou `utilizavel` deve validar a decodificação uma vez).

### 3. Reescritor do caminho do correio nunca é fechado — gravidade: média

- Onde: `historias/contos/imagens/worker.py:409` (`_gerar_pelo_correio`)
- O defeito: cria `Reescritor` na linha 483, mas retorna sem chamar `fechar()`; o caminho legado o fecha na linha 927. Após uma recusa, isso deixa a `ExitStack`, o cliente de navegador e a thread dedicada sem encerramento explícito.
- Quando acontece: geração pelo correio com `reescrever_com_llm: true` e ao menos uma recusa → o navegador do reescritor pode permanecer aberto até o processo terminar, concorrendo com as contas e perfis compartilhados.
- Prova: executei `_gerar_pelo_correio` real com correio/roteiro temporários e um `Reescritor` de rastreamento (sem trocar a função auditada). Depois do retorno normal, a saída foi `reescritor_fechado= False`.
- Conserto sugerido: envolver o laço de cenas em `try/finally` e chamar `reescritor.fechar()` no `finally`.

### 4. Contador diário perde envios em concorrência — gravidade: baixa

- Onde: `historias/contos/imagens/cota.py:96` (`contar`)
- O defeito: leitura, incremento e substituição do JSON não são protegidos por trava. Duas passadas podem ler o mesmo valor, ambas gravar `+1` e persistir só um envio; o teto deixa de proteger a conta se o caminho legado for reativado.
- Quando acontece: dois processos/threads chamam `contar()` no mesmo dia → contador subestima o uso. A configuração atual usa o correio e deixa o teto em `0`, portanto o impacto está inativo hoje, mas a guarda documentada não é segura.
- Prova: em diretório temporário, sincronizei duas chamadas reais de `cota.contar()` logo após a leitura. Saída: `retornos= [1, 1]` e `gravado= {'2026-10-11': 1}`.
- Conserto sugerido: fazer o incremento sob a mesma trava interprocesso usada pela pipeline, relendo o JSON já dentro da seção crítica.

### 5. Âncora de referência e divisão por parte são código morto — gravidade: baixa

- Onde: `historias/contos/imagens/referencia.py:45` a `:135`
- O defeito: o módulo promete congelar estilo, eleger `referencia.png` e distribuir partes por provedor, mas não é importado nem chamado por nenhum módulo de `historias/contos`; nenhum gerador recebe a referência. As garantias descritas no próprio arquivo, portanto, não ocorrem.
- Quando acontece: qualquer história gerada com mais de um provedor → não há âncora visual aplicada; `adotar_primeira`, `definir`, `estilo` e `dividir_por_parte` nunca executam.
- Prova: `rg -n "adotar_primeira|tem_referencia|referencia" historias/contos --glob '*.py'` retornou apenas as definições em `referencia.py` (as demais ocorrências são comentários/texto), sem importador ou chamada.
- Conserto sugerido: integrar explicitamente o módulo ao fluxo que aceita referência, ou removê-lo e retirar a promessa/documentação associada para não manter uma guarda inexistente.

## Não confirmados

- Nenhum. Casos dependentes de navegador logado, rede ou ffmpeg não foram classificados sem uma prova isolada.
