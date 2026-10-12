# Auditoria profunda — Motor: IA dos lutadores — 11/10/2026

## Examinado

- `neural_fights/ai/__init__.py` — 2 funções lidas; exporta o catálogo de IA por importação preguiçosa.
- `neural_fights/ai/brain.py` — 122 funções/properties lidas; monta personalidade, percepção, decisão, planos, ações e uso de skills do lutador.
- `neural_fights/ai/choreographer.py` — 26 funções/classes lidas; coordena ritmo, fluxo e momentos compartilhados do combate.
- `neural_fights/ai/contracts.py` — 1 função lida; resolve o controlador de IA atual ou o alias legado.
- `neural_fights/ai/emotions.py` — 13 funções/properties lidas; mantém emoções, humor e memória emocional.
- `neural_fights/ai/percepcao.py` — 13 funções/classes lidas; cria a visão pública do mundo e do inimigo.
- `neural_fights/ai/personalities.py` — 1 função lida e todos os catálogos; declara traços, eixos, estilos, quirks, humores, instintos, ritmos e presets.
- `neural_fights/ai/plano_de_luta.py` — 11 funções/classes lidas; define e avalia intenções táticas persistentes.
- `neural_fights/ai/skill_contracts.py` — 11 funções lidas; normaliza dados de skills para a estratégia.
- `neural_fights/ai/skill_strategy.py` — 40 funções/classes lidas; classifica o kit, cria rotações e seleciona skills.
- `neural_fights/ai/spatial.py` — 16 funções/classes lidas; calcula consciência de arena, obstáculos, rotas e colisões.

## Confirmados (do mais grave ao menos)

### 1. Vantagem de canto vira agressividade permanente — gravidade: média

- Onde: `neural_fights/ai/brain.py:2387` (`_avaliar_taticas_espaciais`)
- O defeito: a cada avaliação em que o inimigo está na parede, o método soma `0.25` a `agressividade_base`, que é persistente. Não há redução quando o inimigo sai do canto.
- Quando acontece: um lutador com `PREDADOR` diante de inimigo junto à parede passa de agressividade-base `0.5` para `1.0` após três avaliações (cerca de 0,6 s), e conserva esse máximo no restante da luta.
- Prova: `python -` com objetos físicos mínimos e três chamadas ao método real imprimiu `canto 1.0 0.9500000000000001`.
- Conserto sugerido: calcule o bônus de canto localmente na decisão, ou guarde e reverta o bônus ao sair da condição, sem mutar `agressividade_base` a cada tick.

### 2. A melhor janela de ataque do frame é perdida pela última condição — gravidade: média

- Onde: `neural_fights/ai/brain.py:1805-1866` (`_atualizar_janelas_oportunidade`)
- O defeito: as condições escrevem na mesma variável temporária; uma condição posterior, de menor qualidade, sobrescreve a anterior antes da comparação final.
- Quando acontece: oponente em recuperação (`0,8`), atordoado (`1,0`) e recuando (`0,75`) enquanto já há janela de `0,8`: a janela de stun não substitui a atual porque o método compara apenas o último valor, `0,75`.
- Prova: `python -` chamando o método real com esse estado imprimiu `janela {'aberta': True, 'tipo': 'existente', 'qualidade': 0.8, 'duracao': 1.0}`; deveria resultar em `stunado`, qualidade `1.0`.
- Conserto sugerido: atualize a candidata imediatamente quando sua qualidade superar a melhor do frame, ou acumule candidatas e escolha `max` por qualidade.

### 3. Reação de fuga do covarde é descartada — gravidade: média

- Onde: `neural_fights/ai/brain.py:3368` (`on_hit_recebido_de`) e `neural_fights/ai/brain.py:3111` (`_processar_reacao_oponente`)
- O defeito: ao apanhar com medo alto, o covarde agenda `FUGIR`; o despachante não possui essa chave no dicionário nem em ramo especial e devolve `False` após apagar a reação.
- Quando acontece: `COVARDE` com `medo > 0,4` recebe hit; fica na ação anterior em vez de fugir.
- Prova: `python -` executando os dois métodos reais imprimiu `reacao FUGIR False COMBATE`.
- Conserto sugerido: inclua `FUGIR` no despacho, mapeando-a para a ação de fuga do motor.

### 4. 28 quirks sorteáveis não têm leitor de runtime — gravidade: média

- Onde: `neural_fights/ai/personalities.py:771` (`QUIRKS`) e `neural_fights/ai/brain.py:847` (`_gerar_quirks`)
- O defeito: o gerador sorteia todo o catálogo, inclusive 28 quirks que não aparecem em nenhum arquivo de runtime fora do catálogo/presets. O lutador recebe um rótulo e a promessa de um efeito que nunca é consultado.
- Quando acontece: por exemplo, presets e sorteio podem dar `AURA_INTIMIDANTE`, `REGENERADOR`, `SOMBRA_MORTAL`, `ADRENALINE_JUNKIE`, `BURST_MODE` ou `EXECUTION_INSTINCT`; nenhum deles altera a luta.
- Prova: `python -` leu o catálogo e todos os `.py` de `neural_fights/` fora de `personalities.py`; imprimiu `quirks sem leitor fora do catalogo: 28` seguido dos 28 nomes, incluindo os exemplos.
- Conserto sugerido: implemente cada efeito prometido ou retire esses nomes do sorteio e dos presets até haver consumidor.

### 5. Dois humores declarados nunca podem ser produzidos — gravidade: baixa

- Onde: `neural_fights/ai/personalities.py:1180-1181` (`HUMORES`) e `neural_fights/ai/emotions.py:158` (`atualizar_humor`)
- O defeito: `MELANCOLICO` e `EXTASE` constam do catálogo de humores dinâmicos, mas não aparecem em nenhuma alternativa da escada que escolhe `novo_humor`.
- Quando acontece: em qualquer estado normal de combate, esses dois humores nunca chegam ao lutador; seus modificadores ficam mortos.
- Prova: o mesmo `python -` de auditoria imprimiu `humores sem produtor em EmotionSystem: ['MELANCOLICO', 'EXTASE']`; busca no runtime só encontrou as duas declarações no catálogo.
- Conserto sugerido: acrescente gates observáveis na escada de humor ou retire os dois estados declarados.

### 6. Fluxo erra na passagem angular de -180°/180° — gravidade: baixa

- Onde: `neural_fights/ai/choreographer.py:219-229` (`_atualizar_fluxo`)
- O defeito: compara ângulos por subtração absoluta, sem normalizar o delta circular. Direções a 179° e -179° são quase iguais, mas são tratadas como separadas por 358°.
- Quando acontece: lutador avança praticamente na linha do adversário atravessando o eixo negativo de X; o avanço não é reconhecido, portanto o fluxo e momentos dependentes ficam errados.
- Prova: `python -` chamou o método real com vetores separados por 2° nessa fronteira e imprimiu `fluxo 0.0`; o avanço deveria aumentar o fluxo positivo.
- Conserto sugerido: normalize a diferença angular para `[-pi, pi]` antes de compará-la ao limiar.

### 7. Três recursos espaciais completos nunca são chamados — gravidade: baixa

- Onde: `neural_fights/ai/spatial.py:347` (`avaliar_taticas`), `:455` (`prever_colisao`) e `:479` (`get_melhor_posicao_ataque`)
- O defeito: os três métodos calculam modificadores táticos, colisão futura e ponto de ataque, mas não há chamada no motor nem em outro módulo. As decisões seguem sem esses resultados.
- Quando acontece: sempre; cobertura/projéteis sugeridos, predição e posicionamento calculado por esses métodos não participam de nenhuma luta.
- Prova: `python -` analisou as chamadas AST de todos os módulos fora de `spatial.py` e imprimiu `{'get_melhor_posicao_ataque': [], 'prever_colisao': [], 'avaliar_taticas': []}`.
- Conserto sugerido: integre cada resultado à decisão correspondente ou remova o recurso declarado para não prometer comportamento inexistente.

## Não confirmados

- Nenhum adicional: as demais suspeitas levantadas na leitura não tiveram cenário concreto reproduzível sem inventar um estado que o runtime não fornece.
