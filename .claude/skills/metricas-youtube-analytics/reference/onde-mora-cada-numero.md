# Onde mora cada número do YouTube (conferido em 20/10/2026)

| Número | Fonte | Disco | Medido/derivado |
|---|---|---|---|
| views/likes/comentários por vídeo | Data API v3 (`metricas.API_VIDEOS`) | `random_builds/outputs/_metricas/<youtube_id>.json` | medido |
| % assistido e curva por vídeo | Analytics (`metricas.API_ANALYTICS`, `metricas.retencao`) | mesmo arquivo | medido |
| views do canal por dia, inscritos ganhos/perdidos | Analytics `dimensions=day` (`analise.buscar_serie_do_canal`) | `random_builds/outputs/_analise/canal_builds.json` | medido (desde 19/10) |
| views ganhas desde ontem, por vídeo | fotografia diária | `random_builds/outputs/_analise/historico/<dia>.json` | medido (1ª: 19/10) |
| origem do tráfego | Analytics `dimensions=insightTrafficSourceType` | **não fica em disco** | medido |
| formato de cada vídeo | `origem` do ledger casado pelo `youtube_id` | `random_builds/outputs/_publicar/publicados.jsonl` | linha sem `youtube_id` fica "sem formato" |
| a coleta de hoje deu certo? | `metricas.ler_marca()` / `partes_da_marca` | `_metricas/_atualizado_em.json` | medido, por parte (builds, builds_tiktok…) |
| "dias de estoque" | `postar.estoque()` | — | **derivado** (divisão) |

Token: `metricas._token("builds")[0]` (refresh do OAuth da conta do canal; a credencial de
LEITURA é a conta `youtube`; quem publica é `youtube_web` — o nome da conta é o destino).

Chamada a mão (o que o script faz):
```
GET https://youtubeanalytics.googleapis.com/v2/reports
  ids=channel==MINE  startDate=AAAA-MM-DD  endDate=AAAA-MM-DD
  metrics=views,averageViewPercentage  dimensions=video  sort=-views  maxResults=200
  Authorization: Bearer <token>
```

Serviço do dia (quem GRAVA): `historias/contos/pipeline/agenda._servico_do_dia` às 07:02 —
coleta (`metricas.atualizar_uma_vez_por_dia`), conferência, análise. Se ele não roda, a linha
`[coleta parada AAAA-MM-DD]` vai ao diário (desde 14/10). Em 13/10 não rodou porque outra rodada
segurava a trava: medidor que só fala quando roda é surdo no dia em que não roda.

Os 5 comandos de "está tudo bem?" estão em `docs/sessoes/metricas.md` §6.
