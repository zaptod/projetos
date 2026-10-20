---
name: publicacao-grade-e-guardas
description: Mudar quantos duelos saem por dia e em que horário (grade), a mistura de formatos (cota duelo/build/estreia), o título que a guarda compara, ou qualquer guarda contra repetição da publicação (ferramentas/postar.py, builds/grade.py, builds/publicar/*). Use antes de aplicar a grade do plano (YouTube 3/dia em horário fixo, TikTok 1–3/dia), antes de aplicar os WIPs de 19/10 da publicação, ou quando uma guarda parece estar barrando duelo bom.
---

# Grade e guardas da publicação

**Lei do dono:** não ficar sem vídeo, mas **repetir é pior que não postar**. Três guardas falham
FECHADAS (erro ⇒ não publica): a lista "a conferir", a de um por horário (ledger ilegível) e a
trava da rodada. Não afrouxe nenhuma, nem `TETO_POR_FONTE_NO_DIA`, `CORTE_DO_TIKTOK`,
`RECUPERACAO_LIGADA`, `RESERVA_LIGADA` ou o título repetido: são decisões do Adrian (Grimório).

## O que está NO CÓDIGO em 20/10 (confira de novo: `grep -n HORAS_POR_PLATAFORMA -A4 random_builds/builds/grade.py`)
- `grade.GRADE` = 10 horários (00:37 06:37 09:37 12:07 15:37 17:57 20:37 21:37 22:37 23:37) e
  `HORAS_POR_PLATAFORMA` = os 10 para YouTube **e** TikTok.
- Cota `postar.COTA_PADRAO` / `config/publicacao.json → grade.mistura`: duelo 4, build 3,
  estreia 1 (pesos; `escolher_por_cota` dá o horário ao formato mais atrasado nos últimos 16).
- **`docs/sessoes/publicacao.md` descreve como feito o TikTok 6/dia com fila própria e "duelo no
  lugar da estreia" (19/10) — isso NÃO está no ramo**: está em `integracao/publicacao-semana1`
  (4a5d9928 + ad862828 da geração + WIPs 78e5657f/41600582 NÃO TESTADOS), revertido da árvore
  principal porque a recuperação/reserva do TikTok lia relógio e ledger REAIS (10 testes de
  histórias vermelhos). E o plano pede outra grade (YouTube 3/dia). Detalhe em
  [reference/mudar-a-grade.md](reference/mudar-a-grade.md).

## Procedimento para mudar grade, cota ou guarda
1. **Decisão primeiro.** Mudança de ritmo/formato é do Adrian: nó no Grimório
   (`python -m remoto.decisoes adicionar ... --commit`), já respondido com a recomendada.
2. **Meça antes**: o que a mudança deve dar, em número, contado pelo retrato
   (`python .claude/skills/publicacao-conferir-ledger/scripts/retrato_do_ledger.py --dias 7`).
3. **Um critério só**: `metricas.publicado(linha)`, `titulos.chave()`, `grade.slot()` e
   `conferencia.chave_do_horario()` — nunca a hora do relógio, nunca um segundo "é igual?".
4. **Guarda no funil**: proteção nova mora nos funis por onde todo caminho passa
   (`youtube.publicar_como_configurado`, `tiktok.publicar`, os 4 `_voando` do `postar.py`) —
   conte os caminhos (rodada, recuperação, reserva, escoar, `--so-youtube`, app, bot).
5. **Teste na worktree E na árvore principal**: rode as suítes de `E:\projetos` com o código da
   worktree à frente no `PYTHONPATH`, em 3 horários diferentes (perto de um post, longe, depois
   da meia-noite): código que lê relógio/ledger reais passa num e quebra no outro.
6. **Aplicar fora da janela** (post−12 a post+18) e entre rodadas; reinstalar as tarefas do
   Agendador (`postar.py --instalar`) é do orquestrador com o OK do Adrian — agente nunca roda.

## Armadilhas que já custaram caro
- **A grade é por PLATAFORMA, não por canal**: `HORAS_POR_PLATAFORMA["youtube"]` vale para
  duelos E histórias. "YouTube 3/dia nos duelos" exige grade por canal (conceito novo) — e há 18
  módulos (fora testes) que importam `builds.grade` (coordenador, agenda das histórias, painel, relatórios,
  conferência, análise, panorama…). Conte-os antes.
- Hora do relógio no lugar de `grade.slot`: :57 + 4 min de upload cruzava a hora e dava dois
  veredictos na mesma rodada (até 29/09). Teto por fonte contava o dia do calendário (até 29/09).
- A recuperação do YouTube publicou 5 duplicatas (27–28/09). Rascunho do "Publicar mesmo assim"
  contava como publicação. Cada "segundo critério" virou um defeito.
- Título do duelo por tipo de arma fecharia a fila (36 pares) — ver `builds-render-duelo`.
- Não pergunte ao Gemini na hora de postar (`PEDIR_PARECER_NA_POSTAGEM=False`).

## Checklist antes de entregar
- [ ] número esperado calculado antes e medido depois (retrato do ledger, mesma janela)
- [ ] caso ZERO testado (canal sem vídeo, ledger vazio/ilegível) — falha fechada onde é lei
- [ ] suítes da árvore principal verdes com a worktree à frente, em 3 horários
- [ ] nenhuma linha escrita no ledger fora de `metricas.acrescentar_ao_ledger`; nada publicado
- [ ] `docs/sessoes/publicacao.md` corrigido no mesmo commit (ele É acreditado)
