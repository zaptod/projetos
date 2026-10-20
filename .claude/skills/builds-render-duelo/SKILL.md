---
name: builds-render-duelo
description: Gerar, re-renderizar ou mudar o VÍDEO DE DUELO do Neural Fights (random_builds `main.py duelo`) e provar o mp4 antes de entregar. Use quando a tarefa mexe no que o público vê no duelo — título, faixa do topo com os nomes, pergunta "quem vence?", luta no quadro 0, câmera, duração, HUD, veredito, idioma da tela — ou quando é preciso gerar um duelo de prova sem sujar o banco nem o catálogo.
---

# Duelo: gerar, mudar e provar

O duelo é o formato do plano (`docs/PLANO.md`): no YouTube rende ~3x a estreia (análise de 20/10:
duelo 106 views/vídeo, build 81, estreia 28). Toda mudança aqui é a "mudança da semana" e tem de
ser medida depois (skill `metricas-medida-da-semana`).

## Procedimento
1. **Relógio.** Nada pesado de `post-12` a `post+18` min de cada horário de `builds.grade.GRADE`
   (00:37 06:37 09:37 12:07 15:37 17:57 20:37 21:37 22:37 23:37). A regra ":25–:55" que ainda
   aparece em `.claude/agents/builds.md` é VELHA.
2. **Ache onde mora o que vai mudar** — tabela em [reference/onde-mora-cada-coisa.md](reference/onde-mora-cada-coisa.md).
   Título e descrição NÃO são código: `random_builds/config/publicacao.json` (`titulos.duelo`,
   `descricoes.duelo`, `hashtags.duelo`), e o dono desse arquivo é o Adrian (registre a mudança
   no Grimório).
3. **Mude numa worktree** e prove pelo **caminho real** com o banco numa cópia:
   [reference/prova-pelo-caminho-real.md](reference/prova-pelo-caminho-real.md). Nunca
   `--forcar`, nunca refazer o banco, nunca apagar pasta de `outputs/`.
4. **Luta igual.** Se tocou em desenho/câmera/HUD, a luta (vencedor, motivo, duração, HP, golpes)
   tem de sair idêntica à base: em `random_builds/tests/` os `test_luta_video_regressions.py`,
   `test_duelo_regressions.py`, `test_hud_zona_segura_regressions.py`,
   `test_letreiro_do_ko_regressions.py`, e `tests/test_fim_da_luta_regressions.py`
   (TEMP=E:\tmp_pytest, `PYTEST_ADDOPTS=-p no:cacheprovider`).
5. **Meça o mp4** com o medidor do conferente e OLHE os quadros:
   `python .claude/skills/conferente-video-mp4/scripts/medir_video.py <mp4> --saida E:\tmp_pytest\conferente\<tarefa>`.
6. **Commit por caminho** com o número medido; atualize `docs/sessoes/builds.md` no mesmo commit.

## Armadilhas que já custaram caro
- **Título só com a arma colide com a guarda de título repetido.** O banco vivo tem 184 armas
  de só **8 tipos** (Reta, Dupla, Mágica, Transformável, Arremesso, Arco, Corrente, Orbital) →
  36 pares. "Sword VS Dagger" por TIPO esgota em ~12 dias a 3/dia e a guarda (`titulos.chave`,
  fechada desde 17/09) passa a barrar todo duelo. O rodízio (`builds/arena/rodizio.py:titulo_do_par`)
  lê o MESMO modelo do `publicacao.json` só com `{p1}`/`{p2}`: campo novo no título exige mexer
  lá e em `catalogo._campos_duelo` juntos. Detalhe e saídas em `reference/onde-mora-cada-coisa.md`.
- **Worktree importa o código errado.** Da raiz (de qualquer pasta fora de `random_builds/`),
  `import builds` resolve para `E:\projetos\random_builds` (instalação editável), não para a
  worktree. Rode de `<worktree>\random_builds` ou ponha a worktree à frente no `PYTHONPATH`.
- **Duelo exige ficha no banco VIVO** (`%LOCALAPPDATA%\neural-fights\{personagens,armas}.json`);
  `neural_fights/data/*.json` é só o snapshot. Sem ficha: "nao ha adversario disponivel no banco".
- **Palco (Godot) no celular está DESLIGADO** (`config/palco.json → producao.duelo_celular`); se
  ligado e falhar, o celular sai pelo pygame e o motivo vai para `<duelo>/palco_celular.json`.
- **Zona das plataformas** (`renderer.ZONA_DAS_PLATAFORMAS`: topo 10%, baixo 20%, direita 12%):
  nada importante ali — o TikTok/Shorts cobre. Texto novo no topo tem de caber abaixo de 10%.
- Teste verde não é prova: 02/10 passou uma Arena que não gerava vídeo com "testes verdes".

## Checklist antes de entregar
- [ ] rodado pelo caminho real (`main.py duelo ...`) com runtime numa cópia, fora da janela
- [ ] luta idêntica à base (testes de luta verdes) quando mexeu em desenho/câmera
- [ ] `medida.json`: 1080x1920, áudio presente, `regua_da_publicacao` com `""` nas duas medidas,
      sem congelado fora da cauda, pico ≤ -1 dBTP
- [ ] quadros 0 s, 1 s e fim OLHADOS (Read) sobre a zona pintada; texto novo legível e fora da zona
- [ ] título do catálogo conferido: `python main.py publicar` lista o título que vai ao ar
- [ ] semana 1 (inglês): [reference/semana1-ingles.md](reference/semana1-ingles.md) item a item
