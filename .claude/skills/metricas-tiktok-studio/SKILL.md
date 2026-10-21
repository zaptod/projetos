---
name: metricas-tiktok-studio
description: Medir os duelos no TikTok (perfil do canal "builds") — views, % assistido, taxa de conclusão e origem do tráfego por post, lidos do JSON interno do TikTok Studio; e responder se o perfil está sendo distribuído (posts em 0 view, elegibilidade para recomendação, efeito do número de posts por dia). Use para o ponto de partida do TikTok, para medir o teste de 1–3 posts/dia do plano ou quando a coleta do Studio parou, veio curta ou "parece logout".
---

# TikTok Studio: medir sem enganar

## Procedimento
1. **Ler o que já foi coletado (sem navegador)**, de `E:\projetos`:
   `python -c "from builds.publicar import tiktok_metricas as t; print(len(t.carregar_salvas('builds')))"`
   (303 em 20/10). Cada registro tem `views`, `media_percentual`, `media_segundos`,
   `taxa_de_conclusao`, `origem_do_trafego`, `origem` (formato), `quando` (local),
   `publicado_em` (UTC). Por formato nos últimos 14 dias (20/10): **duelo 59 posts, mediana 1
   view, 20 em zero, soma 716**; build 29 / 1 / 8 zeros; estreia 24 / 1 / 9 zeros.
2. **A marca da coleta** antes de citar número: `metricas.partes_da_marca(metricas.ler_marca())["builds_tiktok"]`
   (`estado`, `ultimo_ok`, `erro`; lista `completa`/`suficiente` × `parada`/`tempo` = incompleta).
3. **A análise já mede o efeito do ritmo**: `PYTHONIOENCODING=utf-8 python -m builds.publicar.analise --ver`
   — achado "o perfil só aparece depois de descansar" (builds: pausa 22 h+ → 6 de 6 blocos
   deram certo; 5–10 h → 4 de 33). Unidade = BLOCO de posts, não post.
4. **Elegibilidade / punição**: o PLANO registra (agente metricas, 20/10 02h) "sem punição na
   conta nem vídeo restrito (getPenaltyDetails 0, quality_advisor vazio)" — lido à mão no
   Studio. Desde o ramo `metricas/coletor-sozinho` (21/10) o coletor GUARDA: `situacao` de
   cada post (`status`/`visibility`/`in_review`/`permissions`, crus) e uma ficha por dia da
   conta em `*/outputs/_metricas_tiktok_conta/<dia>.json` (`vv_history`, `seguidores`,
   `punicao`/`qualidade` com `lida` e o corpo cru) — ler com
   `tiktok_metricas.carregar_contas('builds')`. O FORMATO dessas respostas não foi medido pelo
   código: confira o bruto da 1ª ficha real antes de confiar no `vv_history` decifrado.
   `lida: false` = não medi, NUNCA "sem punição"; nunca diga "elegível" sem ter lido.
5. **Coletar de novo** é o serviço do dia (`tiktok_metricas.coletar`, abre o Chrome): não rode
   para "só olhar"; se precisar, fora da janela das postagens e com a publicação parada.

## Armadilhas que já custaram caro
- **Lista curta como "0 vídeos"**: o Studio pagina pela resposta de `creator/manage/item_list`
  (constante `tiktok_metricas.LISTA`; corpo `cursor`/`size`: 50 na 1ª página, 10 depois, `has_more`), a lista mora num DIV com rolagem
  própria e cada rolagem repede a 1ª página. Até 28/09 a coleta parava em 50–60 posts (60 de
  119 envios casados). Hoje `Lista` guarda o MAIOR cursor e diz por que parou.
- **Perfil do TikTok mora DENTRO do repo** (`random_builds/.browser_profile/tiktok`, via
  `tiktok.perfil_da_conta`): da worktree o Chrome abre um perfil VAZIO e parece logout. Prova
  no navegador sempre com a raiz `E:\projetos`.
- **Trava do perfil**: a coleta e a publicação usam a mesma pasta; a coleta espera e desiste
  (`PerfilOcupado`) em vez de abrir uma 2ª janela.
- **A curva só é relida para 40 posts por rodada** (`MAXIMO_DE_ANALISES`, `DIAS_DE_ANALISE`=7):
  número de % assistido de post antigo pode estar parado há dias (`analisado_em`).
- **3 envios que o Studio não lista mais** (histórias, 17 e 20/09) ficam com número parado —
  "sem par" e "parado" eram os mesmos 3.
- **Viral distorce média**: um post de 12.572 views era 86% das views de um perfil — use
  mediana por post e diga quantos estão em zero.
- `atividade.jsonl` grava UTC; ledger e `quando` gravam local; `publicado_em` do Studio é UTC.

## Checklist antes de entregar
- [ ] data da marca `builds_tiktok` citada; lista completa/suficiente
- [ ] mediana por post + quantos em zero + n (nunca só a soma)
- [ ] elegibilidade só afirmada se lida no Studio, com a hora
- [ ] nenhum Chrome aberto pela worktree; nenhuma coleta durante a janela das postagens
