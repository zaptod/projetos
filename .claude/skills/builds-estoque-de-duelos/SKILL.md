---
name: builds-estoque-de-duelos
description: Saber quantos DUELOS prontos o canal tem, quantos dias isso cobre e fazer a geração automática (`main.py noite`, tarefas NeuralFights_gerar_HH) produzir mais duelos ou duelos diferentes. Use quando o estoque de duelos está acabando, quando a geração não gerou, quando o plano muda o ritmo de postagem (YouTube 3/dia) ou antes de mudar o rodízio de quem luta.
---

# Estoque e geração de duelos

## Procedimento
1. **Conte pelo funil da publicação, nunca à mão:** de `E:\projetos\random_builds`,
   `python main.py noite --listar` (tarefas, estoque por formato, modo de agora, os duelos que a
   grade escolheria). Medido 20/10 02:47: **28 duelos, 12 builds, 52 estreias**; "5,0 por dia".
   Esse número é `noite.contar_estoque()` = `postar._builds_prontos` por formato (pendência,
   título repetido e áudio mudo incluídos). `postar.estoque_por_formato` NÃO aplica esse funil
   e já anunciou 7 dias com a fila fechada — não use para decidir.
2. **Dias de estoque** = duelos ÷ duelos publicados por dia na grade vigente. Com o plano
   (YouTube 3/dia, só confrontos diferentes) os mesmos 28 duram ~9 dias; com a grade atual
   (10/dia, cota duelo 4 de 8) ~5. Diga qual grade usou.
3. **O que a próxima rodada faria, sem gerar:** `python main.py noite --ensaio`.
4. **Gerar na mão** (fora da janela, ver relógio): `python main.py noite --duelos N` (ignora o
   teto, o relógio ainda manda) ou um a um `python main.py duelo`. Sai em `outputs/duelo_000NN/`.
5. **Diário da geração:** `random_builds\outputs\_logs\gerar_AAAAMMDD.txt` (modo de cada
   disparo; "já rodando" = a trava `builds__gerar` estava com outra rodada — normal).
6. Mudou regra de geração/rodízio: teste junto, commit por caminho, e `docs/sessoes/builds.md`.

## Relógio (duas réguas, as duas valem)
- **Geração** (`noite.fora_da_grade`, `config/geracao.json → folga_da_grade` 15/15): um passo só
  começa se TERMINA antes de post−15 e nada começa antes de post+15. Reserva por duelo: 5 min
  (8 com o palco ligado). Disparos a HH:02, mais 12:32 e 18:22.
- **Serviços/entregas** (CLAUDE.md, `coordenador/supervisor.py`): post−12 a post+18.
- Lote de dia: seg–qua 07–22 h gera até o alvo; qui–dom só repõe abaixo do piso de 20.
  ATENÇÃO: `madrugada_na_transicao` ainda está no `geracao.json` (modo "madrugada" medido às
  02:47 de 20/10) apesar da decisão `builds/madrugada-na-transicao` (19/10: desligar). Desligar
  = apagar a chave; é decisão já tomada, falta executar.

## Armadilhas que já custaram caro
- **Nada gerava duelo** de 21 a 27/09: havia 10 tarefas de postar e nenhuma de gerar; o canal
  publicou zero em 4 dias. Ausência de geração tem de acender — confira as tarefas no `--listar`.
- **Contador que mentia**: estoque "2 dias" com `proximo_build()` devolvendo `None`. Estoque só
  vale se passar pelo mesmo funil da escolha.
- **Rodízio** (`builds/arena/rodizio.py`): luta quem apareceu menos nos últimos 20 duelos;
  **par com título já ocupado nunca é escolhido**. Antes, "o último da roleta" deu 5 de 8 duelos
  com o mesmo p1. Se o modelo do título mudar (semana 1), o rodízio muda junto — ver
  `builds-render-duelo/reference/onde-mora-cada-coisa.md`.
- **Banco vivo**: duelo só com fichas em `%LOCALAPPDATA%\neural-fights\personagens.json`;
  `generate-video` é o único que insere. Nunca refaça o banco (agosto morreu assim).
- **Disco**: com < 5 GB livres no C: nada novo é gerado (`disco_livre_minimo_gb`).
- **WIPs que mexem aqui, NÃO aplicados** (20/10): geração por formato / mais duelos
  (a346e118 no ramo `worktree-agent-a832b969b7de13af8`; aplicado e revertido em 564b92cb porque
  depende do WIP da publicação). O ramo `integracao/publicacao-semana1` já junta os dois
  (4a5d9928 publicação + ad862828 geração + 2 WIPs NÃO TESTADOS) e está 10 commits atrás de
  `refactor/arquitetura`. Ver `git log --oneline refactor/arquitetura..integracao/publicacao-semana1`
  e a skill `publicacao-grade-e-guardas`.
- O PC `am` como gerador de duelos está pronto e DESLIGADO (fora do plano até o Adrian pedir).

## Checklist antes de entregar
- [ ] número do estoque tirado do `noite --listar` (com hora) e a grade usada para os dias
- [ ] nenhum disparo dentro da janela; diário do dia lido até o fim
- [ ] duelos novos medidos (skill `conferente-video-mp4`) antes de contar como estoque
- [ ] pares novos: nenhum título repetido (o `--listar` mostra os títulos)
