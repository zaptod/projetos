---
name: metricas-medida-da-semana
description: A revisão semanal do docs/PLANO.md — medir se a mudança da semana no duelo (inglês e título com o confronto; câmera parada e 35–50 s; série "Rei da Arena" e voz do Adrian) subiu views por vídeo, % assistido e inscritos por mil views contra a semana anterior, com certeza estatística, e dizer o que dobrar e o que cortar. Use toda segunda do plano, antes de decidir a mudança seguinte, ou quando alguém afirmar que uma mudança "funcionou".
---

# A medida da semana

**Regra do plano:** UMA mudança medida por semana; a medida de sucesso já está escrita na tabela
"As 4 semanas" do `docs/PLANO.md`. Meta de 30 dias: 3.000 views/dia, 150 inscritos (eram 13),
1 vídeo > 100 mil. Ponto de partida medido (04–17/10): **~910 views/dia (mediana), duelo
76,5 views/vídeo no YouTube e 1 no TikTok**.

## Procedimento
1. **Antes de olhar o resultado**, escreva: a janela (a semana começa no dia em que a mudança
   foi AO AR, não no commit), o formato (duelo), a plataforma, a medida da tabela do plano e o
   que conta como "subiu" (rótulo `claro` ou `provavel`).
2. **Por vídeo** (disco, sem rede; de `E:\projetos`):
   `PYTHONIOENCODING=utf-8 python .claude/skills/metricas-medida-da-semana/scripts/comparar_semanas.py --inicio AAAA-MM-DD`
   e o mesmo com `--plataforma tiktok`. Só entra vídeo com 3+ dias de idade; a semana só fecha
   de verdade ~3 dias depois do último post dela.
   Exemplo medido (YouTube, duelos publicados 10–16/10 × 03–09/10): 107 × 100,5 views/vídeo,
   53,4% × 48,4% assistido → **incerto**. TikTok na mesma janela: mediana 0 × 1, 18 de 33 em
   zero → **claro** (o efeito dos ~10 posts/dia).
3. **Canal** (inscritos por mil views, views/dia):
   `... metricas-youtube-analytics/scripts/analytics_direto.py dia --de <inicio> --ate <fim>`
   → inscritos líquidos ÷ views × 1000 (os canais que cresceram: 0,4–8,3; o nosso ~0,5).
4. **A página do Adrian**: `python -m builds.publicar.analise --ver` (o serviço do dia grava e
   põe na Biblioteca do app às 07:02). Desde o ramo `metricas/coletor-sozinho` (21/10) ela SABE
   a mudança: `random_builds/config/medida_da_semana.json` (`inicio` = a HORA em que a mudança
   foi ao ar; escreva a semana nova ANTES de olhar) e mostra "Medida da semana (mesma idade)":
   novos × antigos aos 6/12/24/48/72 h e 7 dias (±5 h, sem interpolar), % assistido, views
   engajadas e inscritos por mil. Feita agora, só disco: `python -m builds.publicar.analise
   --semana` (sai 1 sem comparação) ou `/semana` no Telegram. O script acima continua sendo a
   conta pelo total com 3+ dias.
5. **Relatório** (curto, para o orquestrador): a mudança, a janela, n de cada lado, as medianas,
   o rótulo, "ainda juntando" e a recomendação ("dobrar", "cortar" ou "medir mais uma semana").
   O Gemini assiste os 5 melhores e 5 piores (semana 4); som só o Adrian julga.

## Armadilhas que já custaram caro
- **Escolher o corte depois de ver** (o "6 primeiros" e o limiar de 10 h foram ajustados nos
  mesmos dados que testavam — 19/10). Critério escrito ANTES.
- **Caso zero**: semana sem vídeo não é "sem efeito" — o script sai 1 e diz "não há comparação".
  Medidor que dá nota boa para máquina parada já mentiu 3 vezes num dia (27/09).
- **Duas mudanças na mesma semana** (ex.: grade nova + título novo) não se separam depois.
  Se o WIP da publicação entrar junto com o inglês, diga isso no relatório.
- **Contar post e não bloco** no TikTok: a unidade do efeito "descansar" é o bloco de posts.
- **Data no calendário × idade do vídeo**: "maduro" é idade ≥ 3 dias.
- **Views antes/depois de 31/03/2025** não se comparam (mudou a contagem de Shorts).
- Mediana por vídeo, nunca soma (o viral faz um perfil morto parecer vivo); diga o n e os zeros.
- Número de disco sem a data da marca (`metricas.ler_marca`) pode ser de dias atrás.

## Checklist antes de entregar
- [ ] critério escrito antes, com a data em que a mudança foi ao ar
- [ ] YouTube e TikTok separados; n, zeros e "ainda juntando" dos dois lados
- [ ] rótulo de certeza citado; "incerto" dito como incerto
- [ ] inscritos por mil views da mesma janela (quando a semana pede)
- [ ] recomendação em uma linha, e a decisão vira nó no Grimório (escolhida a recomendada)
