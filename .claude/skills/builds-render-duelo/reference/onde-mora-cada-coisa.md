# Onde mora cada coisa do duelo (conferido no código em 20/10/2026)

| O que o público vê | Onde mora | Observação |
|---|---|---|
| Título, descrição, hashtags | `random_builds/config/publicacao.json` → `titulos.duelo` (`"{p1} x {p2}"`), `descricoes.duelo`, `hashtags.duelo` | Campos preenchidos por `builds/publicar/catalogo.py:_campos_duelo` (hoje só `p1`, `p2`, `arena`, `duracao`). `catalogo._formatar` **some com o campo que não existe** — campo novo esquecido não dá erro, só some do título. |
| Par do duelo (quem luta) | `builds/arena/rodizio.py` (`escolher_par`, `titulo_do_par`, `titulos_ocupados`) | Nunca escolhe par cujo título já foi ao ar. `titulo_do_par` formata o modelo do config só com `{p1}`,`{p2}`. |
| HUD do topo (nomes, barras, plano) | `builds/video/renderer.py` (`_layout_do_topo`, `hud_do_topo`, só 9:16) | Desde 18/10 em y 209–324 de 1920, x ≤ 912. Cada nome já sai na cor do lutador. |
| Cor de cada lado (corpo na arena = HUD = faixa) | `builds/video/cores.py` (`cores_da_gravacao` decide o desempate de cores parecidas ANTES de gravar; `cores_do_clipe` lê o que o gravador pintou) → `runner.gravar_confronto(cores_da_tela=)` → `fight_recorder --cores-da-tela` → `Simulador` (`match_config["cores_da_tela"]`, só exibição) → `fight.json → luta.cores_na_tela` → `renderer._cores_do_confronto` | Desde 20/10 (conferente, `duelo_00122`: faixa verde × corpo violeta). Clipe sem `cores_na_tela` (gravado antes): HUD na cor do banco, sem giro — re-render não desempata, só gravação nova. |
| Identidade + selo (1,5 s iniciais) | `renderer.py` | Hoje "Nome · Classe · 4V-2D" em português. |
| Rótulos do plano ("PRESSÃO", "PRA PAREDE", "ACABAR", "QUEBRAR GUARDA") | `neural_fights/ai/plano_de_luta.py` (o texto) e `renderer.py` (o desenho) | Em português, sob o corpo e no HUD. |
| Callouts ("VIROU!", "VEM DE 4 SEGUIDAS", K.O./NOCAUTE/ACABOU) | `random_builds/config/editing.json` (bloco dos callouts, `ko: [...]`); montados em `builds/tournament/timeline.py` e `runner.py` (`fight_callouts`) e desenhados pelo renderer | Letreiro do K.O. tem caixa medida (`builds/tournament/runner.py:reserva_do_letreiro`) para a câmera da cauda; texto mais largo muda a caixa — rode `test_letreiro_do_ko_regressions.py`. |
| Veredito (nome do vencedor + "KO · 5V-0D") | `renderer.py` (`VEREDITO_ZONA` 62–76% da altura, `VEREDITO_LARGURA_MAX` 74%) | Fora da zona das plataformas. |
| Câmera | `neural_fights` (Câmera DIRETOR; `diretor_pos_ko_*` na cauda) | Semana 2 do plano: câmera parada com a arena inteira (A/B). A cauda pós-K.O. tem 4 conferências de degrau/letreiro (docs/sessoes/builds.md §11). |
| Duração | as lutas são naturalmente curtas (12–28 s medidos; `duelo_00141` = 12,0 s) | Semana 2: 35–50 s pede mecânica de escalada, não "esticar". |
| Som da luta | `config/editing.json → som_da_luta` (real, alvo -13 dB) | Medido pela guarda `builds/publicar/audio.py`. |
| Voz | o duelo **não tem narração hoje** | Ver skill `builds-voz-do-duelo`. |

Para achar texto em português que vai para a tela (ferramenta Grep, ou no shell — não há `rg`):
`grep -nE '"[A-ZÁ-Ú][A-ZÁ-Ú !]{3,}"' random_builds/config/editing.json random_builds/builds/video/renderer.py neural_fights/ai/plano_de_luta.py`
O olho vale mais que o grep: rode o medidor do conferente e leia cada quadro.

## Título "Arma VS Arma — who wins?" sem fechar a fila

Medido em 20/10: `armas.json` vivo tem 184 armas e 8 tipos → 8×7/2 + 8 = **36** pares de tipo.
O plano pede título que quem nunca viu o canal entenda, mas a guarda de título repetido
(`postar._sem_titulo_repetido` → `titulos.repetido`) barra para sempre um título que já foi ao ar.
Caminhos (decisão de produto: vira nó no Grimório, com a recomendada):
1. usar o **nome da arma** (184, quase todos únicos) ou "Classe com Arma" em vez do tipo;
2. confronto + um diferencial (arena, número do episódio da série "Rei da Arena" — semana 3);
3. só por tipo, se a guarda passar a aceitar repetição em duelo — mexe numa lei do Adrian
   ("repetir é pior que não postar"); não faça sem decisão.
Antes de escolher, MEÇA: quantos títulos distintos o modelo novo gera sobre os duelos em estoque
(`main.py noite --listar` mostra os 28 de hoje) e sobre o que já foi ao ar.

Mudou o modelo? Os 3 lugares andam juntos: `publicacao.json:titulos.duelo`,
`catalogo._campos_duelo` (campos novos) e `rodizio.titulo_do_par` (mesmos campos). Teste:
`random_builds/tests/test_duelo_regressions.py`.
