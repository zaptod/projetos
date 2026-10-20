---
name: metricas-youtube-analytics
description: Medir no YouTube quanto o canal de duelos (Neural Fights, canal "builds") está rendendo — views por dia do canal, inscritos ganhos, % assistido e views por vídeo por formato (duelo × build × estreia), origem do tráfego — pela YouTube Data/Analytics API, sem gastar cota à toa e sem gravar nada para "só olhar". Use para o ponto de partida e a meta do plano (3.000 views/dia, 150 inscritos, 1 vídeo >100 mil), para comparar formatos ou quando um número do relatório parece bom demais.
---

# YouTube: o número que decide

## Procedimento
1. **Escreva o critério antes de medir** (janela, formato, mediana ou média, mínimo de views)
   — senão o corte escolhido confirma a conclusão.
2. **Canal por dia** (sem gravar nada; de `E:\projetos`):
   `PYTHONIOENCODING=utf-8 python .claude/skills/metricas-youtube-analytics/scripts/analytics_direto.py dia --dias 14`
   Medido 20/10 (04–17/10): **média 940/dia, mediana 910**, +8 inscritos; 13/10 = 2.367 (pico),
   15–17/10 = 334–566.
3. **Por formato**: `... analytics_direto.py formato --de AAAA-MM-DD --ate AAAA-MM-DD`
   (mediana por vídeo, % assistido só de vídeo com 20+ views). Medido 04–17/10: **duelo 76,5
   views / 50,8% (n=82)**, build 23 / 37,1%, estreia 9,5 / 13,0%.
4. **Tráfego**: `... analytics_direto.py trafego --dias 14` (04–17/10: SHORTS 78,5%, busca 20,5%).
5. **Disco (o que o serviço do dia coletou)**: `cd random_builds && python main.py metricas`
   (sem `--atualizar` só LÊ). Antes de citar número de disco, a marca:
   `python -c "from builds.publicar import metricas as m; print(m.partes_da_marca(m.ler_marca()))"`.
6. Relate o número com a janela, o n, a hora da medida e "medido" × "derivado".

## Armadilhas que já custaram caro
- **A Analytics atrasa ~3 dias** (o script usa hoje−3 como fim). Dia recente "baixo" ainda
  está juntando; vídeo só conta "maduro" com 3+ dias de IDADE (não "3 dias no calendário").
- **Vídeo sem view não tem linha** na consulta por vídeo; privado com `[0,0,0]` virou "0% de
  retenção" e derrubou o duelo de 51,5% para 34,0% (28/09). Ausência não é zero.
- **Duas medianas**: contando todo upload (sem linha = 0) ou só quem tem linha — diga qual.
- **Desde 31/03/2025 todo começo/replay de Short conta view** ("engaged views" é outra
  métrica): não compare views de antes e depois dessa data.
- **`main.py metricas --atualizar` grava e gasta cota** — é o serviço do dia (07:02); não rode
  para olhar, nem dentro da janela das postagens.
- 403 que culpa o "escopo" já foi a **API desligada no projeto do Google Cloud** (150783870054),
  não o token (11/09).
- A lista de vídeos do canal é `UU` + `UUSH` (playlists), conferida contra o `videoCount`; o
  `search` é eventual e o teto de 200 cortava vídeo.
- Retenção não se compara entre durações (vídeo curto tem % maior sozinho).
- Para julgar o VÍDEO (não o número), quem assiste é o Gemini — e ele não ouve; som é do Adrian.

## Checklist antes de entregar
- [ ] critério escrito antes; janela e n no relatório
- [ ] caso zero: o que a medida diz com zero vídeo/zero linha (não pode dar nota boa)
- [ ] número de disco com a data da marca (`_atualizado_em.json`)
- [ ] nada gravado para "só olhar" (script direto ou leitura de disco)
- Detalhe das fontes: [reference/onde-mora-cada-numero.md](reference/onde-mora-cada-numero.md)
