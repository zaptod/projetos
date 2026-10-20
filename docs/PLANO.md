# PLANO ÚNICO — fazer o Neural Fights crescer (20/10 a 19/11/2026)

**Decidido pelo Adrian em 20/10/2026:** "quero seguir apenas esse plano." Tudo o que não serve a ele espera. Base: `docs/pesquisa/shorts-que-deram-certo.md` e `docs/pesquisa/ferramentas-de-video.md`.

## Meta de 30 dias (honesta)
- **3.000 views/dia** no YouTube do Neural Fights (conferir o ponto de partida real no YouTube Studio — o canal tinha 27.605 views no total em 20/10).
- **150 inscritos** (hoje 13).
- **1 vídeo acima de 100 mil views.**
- Monetização NÃO cabe em 30 dias (1.000 inscritos + 10 mi views de Shorts em 90 dias; 20 mi a partir de 01/02/2027).

## O que a pesquisa mostrou (espelho: Orbitality — duelo de bolinhas em Python, 47,9 mil inscritos e 81 mi views em 7 meses)
1. Título com o CONFRONTO entendido por quem nunca viu o canal ("Espada VS Adaga") — 12/12 exemplos.
2. A luta começa no quadro 0, com a pergunta "quem vence?".
3. Faixa fixa no topo com os dois nomes, cada um na cor do lutador; um número que muda na tela.
4. Câmera parada mostrando a arena inteira (5/5 simulações).
5. 35–63 s (o nosso duelo tem ~15 s).
6. Série/recorde/torneio na tela.
7. Formato sozinho não basta (cópias com 71 e 114 inscritos); variar o estilo (regra do YouTube de 15/07/2025 contra conteúdo repetitivo em massa).

## Ponto de partida (medido pelo agente metricas em 20/10 02h)
- YouTube: ~910 views/dia (média 11–17/10), ~760/dia em 28 dias, caindo para ~450/dia em 15–17/10; 13 inscritos. Os 5 melhores de 14 dias são duelos; as estreias estão entre os piores.
- TikTok: ~14 views/dia; sem punição na conta nem vídeo restrito (getPenaltyDetails 0, quality_advisor vazio). Com ~10 posts/dia, 28 de 36 posts (12–15/10) ficaram em 0; só pegaram os posts depois de pausa → TikTok 1/dia.
- O coletor ainda não guarda: situação de cada post, punição/qualidade, série diária da conta no TikTok (`random_builds/builds/publicar/tiktok_metricas.py`).

## As 4 semanas (UMA mudança medida por semana na Análise dos vídeos)
| Semana | Mudança | Medida de sucesso |
|---|---|---|
| **1 (começa 20/10)** | **Canal em INGLÊS** (decisão geral/canal-em-ingles: título, legenda, tela, voz e idioma do upload; código/docs seguem em português). Títulos "Sword VS Dagger — who wins?"; faixa fixa no topo com os nomes nas cores; pergunta escrita no 1º segundo; luta já no quadro 0. Publicação: YouTube 3/dia em horário fixo, só confrontos diferentes; TikTok 1–3/dia | views por vídeo e "% que assistiu" × semana anterior |
| **2** | Câmera parada com a arena inteira (A/B contra a atual); duelo de 35–50 s; um contador/regra que cresce até o fim. Prova de 1 dia do **HyperFrames** (plugin oficial do Claude Code; Remotion de reserva): barra de vida com dano fantasma, carimbo K.O., placar animado — só entra se renderizar em ≤10 min no i5, rodar no am e o Adrian escolher o novo no A/B | idem + inscritos por mil views |
| **3** | Série **"Rei da Arena"**: campeão defende o título, recorde e "próximo desafiante" na tela. Teste da **voz do Adrian**: 3 vídeos/semana (o sistema gera a luta + roteiro dos momentos-chave; ele grava no celular vendo o vídeo sem som; o sistema sincroniza, nivela e legenda) contra 3 sem voz | inscritos por mil views (narrados × não) |
| **4** | Dobrar o que subiu, cortar o que não subiu. Gemini Pro assiste os nossos 5 melhores e 5 piores contra os campeões | meta de 30 dias |

## O que PARA durante o plano
- Formatos e casinha do Blue Lock (WIPs guardados); o vigia de ramos do Blue Lock continua.
- Melhorias nas histórias (seguem no automático, como estão).
- A mudança completa para o PC `am` (ele só produz duelos; o mecanismo `pc_am` está pronto no WIP 4b35781c com as chaves desligadas).
- Ferramentas novas que não sirvam a uma das 4 semanas.

## Pendências que entram no plano
- Publicação (TikTok 6/dia com fila própria e duelo no lugar da estreia) e geração por formato (mais duelos): WIPs prontos, aplicar JUNTOS na semana 1, ajustando a grade para "YouTube 3/dia" do plano.
- Refazer a voz das 51 roletas que saíram com a voz do Windows (decisão builds/voz-do-windows-12-a-19-10) só se elas forem publicadas.

## Medido pelo sistema (agente `metricas`, nunca perguntar ao Adrian)
- TikTok Studio: os vídeos estão "elegíveis para recomendação"? (8–15 views/dia sugere bloqueio).
- YouTube Studio: views reais por dia (ponto de partida).

## Com o Adrian
- Semana 3: gravar a narração (~20 min/semana).

## Regra do Claude
Uma revisão por semana (ler a Análise, decidir a mudança seguinte, aplicar). Nada fora deste plano sem o Adrian pedir.
