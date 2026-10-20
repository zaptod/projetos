---
name: publicacao-conferir-ledger
description: Responder "o duelo saiu?", "por que o horário X não publicou?", "saiu repetido?" ou "o que está travado na lista a conferir?" lendo o ledger publicados.jsonl, a lista a conferir e o diário — SEM publicar e sem gravar nada. Use para investigar um horário vazio, um vídeo que pode ter saído público sem confirmação, duplicata no canal, ou antes de dizer ao Adrian quantos duelos foram ao ar.
---

# Conferir o que a publicação fez (só leitura)

## Procedimento
1. **Retrato por horário** (de `E:\projetos`, onde o `builds` instalado lê o ledger real):
   `PYTHONIOENCODING=utf-8 python .claude/skills/publicacao-conferir-ledger/scripts/retrato_do_ledger.py --dias 3 --formato duelo`
   Diz, por dia de grade (06:37 → 00:37) e por plataforma, o que saiu em cada horário, os
   horários VAZIOS já vencidos, duas linhas no mesmo horário (e se é o MESMO vídeo), títulos
   repetidos no YouTube e a lista "a conferir" com o motivo. Sem `--formato`, todos os formatos.
2. **Horário vazio → o log da rodada**: `outputs\postar.txt` (enorme; leia o FIM, procure a hora
   da grade) e o diário `%LOCALAPPDATA%\neural-fights\atividade.jsonl` (grava em **UTC**; o
   ledger grava hora local). A rodada diz o motivo: "a válvula fechou", "título repetido",
   "rede", "um por horário", "ficha da dona"…
3. **Ledger × canal**: leia a última conferência gravada, sem rodar outra:
   `python -c "from builds.publicar import conferencia as c; f=c.ultima('builds'); print(f.get('veredito'), f.get('dia_de_grade'), f.get('horarios_em_falta'))"`
4. **Ledger sujo?** `python ferramentas/curar_ledger.py` (A SECO: relata o que mudaria; grava só
   o relatório em pasta própria). `--gravar` é decisão de pessoa (faz cópia antes).
5. Responda com número, hora e caminho; o que é decisão (republicar, tirar da lista) vira nó no
   Grimório.

## Armadilhas que já custaram caro
- **`python -m builds.publicar.conferencia` NÃO é só leitura**: grava a ficha do dia em
  `_conferencia/<dia>.json` e pode mandar alarme ao Telegram (`atividade.registrar` ERRO).
  Para olhar, use `conferencia.ultima()`. `--aceitar-rascunhos` é decisão de pessoa.
- **`postar.py --ver` também escreve** (decodifica mp4, várias linhas no `atividade.jsonl`): no
  máximo uma vez, quando precisa do "o que postaria". Sem `--ver` ele PUBLICA.
- **Arquivo ausente de "a conferir" é uma afirmação** ("ninguém bloqueado"); não apague nem
  "conserte" `_youtube_a_conferir.json`/`_tiktok_a_conferir.json`. A marca de clique só sai por
  conferência humana; a `[audio]` sai sozinha quando o som volta.
- Duas linhas no mesmo horário podem ser de propósito: a dívida do YouTube dos builds sobe junto
  com o novo (`_alcance_do_youtube_dos_builds`). Repetição é o MESMO `video_id`, ou o mesmo
  `titulos.chave` no mesmo destino.
- Numa worktree, `random_builds/outputs/` está vazio: o retrato daria "0/10" falso. Rode de
  `E:\projetos`. O perfil do TikTok também mora no repo: navegador aberto da worktree abre perfil
  vazio e parece logout.
- Contar o ledger pelo `url` preenchido já mentiu (rascunho guardava frase de estado no `url`):
  só `metricas.publicado(linha)` diz se saiu.

## Checklist antes de entregar
- [ ] retrato rodado de `E:\projetos`, com a hora; horários vazios citados pelo nome da grade
- [ ] causa de cada vazio tirada do log/diário (não deduzida)
- [ ] nenhuma escrita: nada de `conferencia` CLI, `curar_ledger --gravar`, `postar.py` sem `--ver`
- [ ] "a conferir": cada item com o motivo e a ação proposta (conferir o perfil/canal na tela)
