# Consertos — palco Godot (GOD)

- **Parte:** palco Godot (`palco/nucleo/*.gd`, ponte `random_builds/builds/palco/*.py`, `neural_fights/recording/timeline_arquivo.py`).
- **Relatório de origem:** `godot-palco.md` (11/10/2026), conferido contra o código de 14/10 e o commit `f5f8cd3` (12/10).
- **Contagem dos 13 itens do relatório:** 4 abertos, 9 consertados, 0 falsos. Além deles, 2 achados novos (GOD-2 e GOD-3), nascidos do próprio `f5f8cd3` ou ao lado dele.
- **Regra do projeto:** o Godot só cuida das regras e a arte é do Adrian. Nenhum conserto abaixo desenha nada no Godot: todos só ligam, dimensionam ou temporizam as folhas do Ateliê que já existem.

### GOD-1 — Rosto do Ateliê: a boca congela no grito, a expressão é sempre a última e os filhos não andam nem crescem  (médio)
- **Onde:** `palco/nucleo/palco.gd:355-359` (`_desenhar_quadro`), `palco/nucleo/palco.gd:226-227` (`_montar_cena`, `bib.rostos()`), `palco/nucleo/tocador_folha.gd:38-57` (`_preparar_catalogo`), `:116-121` (`gatilho`), `:123` (`avancar`), `:168` (`ajustar_corpo`).
- **Defeito:**
  - O `elif` virou `if`. Com `golpe_fase > 0`, a boca (`lutador.rosto.boca`) recebe `expr` e `golpe_fase` no mesmo quadro. Por isso troca de animação duas vezes por quadro: zera o `indice` e relê a folha do disco a cada troca, e o grito fica congelado no quadro 0.
  - O `_preparar_catalogo` guarda as animações só pelo gatilho. Dos 24 estados (as 24 expressões, com os mesmos nomes de `tabelas.expressoes`), fica só o último, e o índice `expr` nunca escolhe o rosto.
  - Os rostos pendurados como filhos do lutador nunca recebem `avancar` nem `ajustar_corpo`: ficam no quadro 0 e no tamanho nativo da folha.
  - Quando o corpo é o marcador (`lutador_padrao.gd`, que não tem `gatilho`), os rostos não recebem gatilho nenhum.
  - Hoje o defeito está latente, porque não existe folha de rosto em `biblioteca/animacoes/`.
- **Conserto:**
  1. Em `tocador_folha.gd`:
     - Guardar as animações por estado: `_animacoes_por_estado[estado_id][gatilho]`, com o estado ativo em `var estado_atual := ""` (padrão: o 1º estado). `_animacoes` passa a ser a do estado ativo.
     - Criar `func estado(nome: String)`, que troca o estado e reinicia a animação só quando o nome muda.
     - Fazer `avancar(delta)` e `ajustar_corpo(d)` repassarem aos filhos que têm o método, como o `gatilho` já faz.
  2. Em `palco.gd` (`_desenhar_quadro`):
     - Traduzir o índice: `var nome_expr := str(tl.dados.tabelas.expressoes[int(s.expr)])`. Chamar `estado(nome_expr)` no lutador e nos filhos (uma função `_rosto(no, nome, golpe)` que percorre `no.get_children()`).
     - Mandar um gatilho só: `"golpe_fase"` se `golpe_fase > 0`, senão `"expr"`.
     - Quando o lutador não tem `gatilho`/`avancar` (é o marcador), chamar `gatilho`, `avancar` e `ajustar_corpo` direto nos filhos.
- **Teste que prova:** `palco/testes/rosto_folha.gd`, rodado por `palco/testes/test_folha_animada.py` com o Godot, como o `test_folha_animada_com_lista_no_godot`.
  - **Montagem:** uma biblioteca de mentira com `lutador.rosto.boca` de 2 estados (`neutro` e `furia`), cada um com `parado`/`expr` (loop, 2 quadros) e `grito`/`golpe_fase` (sem loop, 4 quadros).
  - **Golpe:** 6 quadros com `golpe_fase = 1` e `expr` de `furia`. Afirma que a boca avança (`indice` 0 → 1 → 2 …), que `gatilho_animacao == "golpe_fase"` e que o estado é `furia`.
  - **Tamanho:** depois de `ajustar_corpo(170)` no pai, o filho tem `corpo_px == 170`.
  - **Hoje falha:** o `indice` fica em 0, o estado é sempre o último e `corpo_px` fica 0.
- **Origem:** `godot-palco.md` #2 e #5 (a parte do rosto; a parte `movimento.*` do #5 já foi consertada).

### GOD-2 — Lutador sem arma: `arm[slot]` sem a chave derruba o evento e, agora, o render inteiro  (médio)
- **Onde:** `palco/nucleo/palco.gd:636-641` (`_evento`, o laço `for slot in _donos_do_gatilho(ev)`).
- **Defeito:**
  - O conserto do #4 trocou `for slot in arm` por `arm[slot].has_method(...)`. Só que `arm` só ganha o slot quando o cabeçalho traz `arma` (`palco.gd:229-232`), e `timeline.py:_cabecalho_arma` devolve `None` quando `arma_obj` falta.
  - Sem a chave, o Godot dá `SCRIPT ERROR: Invalid access to property or key 'p1' on a base object of type 'Dictionary'`. Provado com a sonda `scratchpad/god_probe/sonda_arm.gd`, no Godot 4.7.2.
  - O resto do `_evento` (VFX, tremor) é abortado e, com o conserto do #1, o `render.py` recusa o vídeo.
  - Hoje está latente: os 143 personagens do banco têm `nome_arma`. Mas basta uma arma que não resolve, ou o `remover_arma` do launcher.
- **Conserto:**
  - Em `_evento`, usar `var a = arm.get(slot)` e `if a != null and a.has_method("gatilho"): a.gatilho(gatilho)`.
  - Fazer o mesmo com `lut[slot]` por segurança: `_donos_do_gatilho` já filtra por `lut.has`.
- **Teste que prova:** em `random_builds/tests/test_palco_regressions.py`, criar `test_evento_de_lutador_sem_arma_nao_derruba_o_render`. Ele pega a `sintetica.timeline_sintetica(2.0)`, faz `doc["lutadores"][0]["arma"] = None` e chama `render.renderizar` (skip sem Godot). Afirma que não há `ErroPalco` e que `resumo["eventos"]` > 0. Hoje falha com "N erro(s) de script do Godot".
- **Origem:** novo, regressão de `f5f8cd3` (conserto do `godot-palco.md` #4).

### GOD-3 — O gatilho de evento da arma é apagado no quadro seguinte  (médio)
- **Onde:** `palco/nucleo/palco.gd:437-438` (`_arma`: `no.gatilho("golpe_fase" if ... else "ocioso")` em todo quadro) contra `:639-640` (`_evento` manda `projetil_fim`, `arma_puxada`, `transformado` …).
- **Defeito:**
  - O `_evento` toca a animação do evento na arma do dono. No quadro seguinte, o `_arma` manda `ocioso`/`golpe_fase`, que toda arma do catálogo tem (63 `ocioso`). O tocador troca, e a animação do evento dura 1 quadro de vídeo.
  - São 21 animações de arma no catálogo, 7 de cada gatilho.
  - Hoje está latente: só os Cristais têm folha, e sem esses gatilhos.
- **Conserto:** em `tocador_folha.gd`, guardar `var _travado := false`.
  - `tocar()` de um gatilho que não é `ocioso` nem `golpe_fase` em animação sem loop marca `_travado = true`.
  - Enquanto `_travado`, `tocar("ocioso")` e `tocar("golpe_fase")` são ignorados.
  - O `avancar` solta a trava quando a animação termina (`_terminou`), antes de voltar ao `_ocioso`.
  - O `ko`/`acerto` do corpo ganha o mesmo comportamento de graça.
- **Teste que prova:** `palco/testes/tocador_folha.gd` (o teste GDScript que já existe) ganha um caso: uma peça com `ocioso` (loop) e `projetil_fim` (sem loop, 4 quadros). Chama `gatilho("projetil_fim")`, depois `gatilho("ocioso")` + `avancar(1/30)` 3 vezes. Afirma que `gatilho_animacao == "projetil_fim"` até o 4º quadro e `"ocioso"` depois. Hoje vira `ocioso` na primeira chamada.
- **Origem:** novo, achado ao conferir o `godot-palco.md` #4.

### GOD-4 — Documentação e código morto fora de sincronia  (baixo)
- **Onde:**
  - `random_builds/builds/palco/godot.py:165`: o docstring de `gravar_filme` cita `res://ferramentas/vitrine.tscn`.
  - `palco/nucleo/palco.gd:94,782` e `random_builds/builds/palco/render.py:173`: `rosto_herdado` é sempre `{}`.
  - `palco/ferramentas/validar.gd:36,41`: resolve `bib.evento(tipo, tier)` e `bib.objeto(tipo, elemento, nome)` sem `variante`/`forma`/`skill`.
  - `palco/nucleo/biblioteca.gd`: `_id_slot` devolve `""`, e `candidatos_objeto_png`, `candidatos_evento_com_png`, `opcoes_do_png` e `ordem_comum_e_elemento` ficaram como resto da cadeia PNG.
- **Defeito:** confunde quem repara. O relatório lista um campo que nunca é preenchido, e o validador imprime uma lista de peças que não é a do render.
- **Conserto:**
  - Tirar do docstring a frase da vitrine.
  - Apagar `rosto_herdado` em `palco.gd` (variável e chave do relatório) e em `render.py` (chave do resumo e o comentário de cima).
  - Em `validar.gd`, montar a variante como no `_evento` do `palco.gd`: `gatilho` para movimento, `motivo` para `projetil_fim`, `modo` para `agarrao_desfecho`, `critico` para acerto. Passar também `nome`/`tipo_skill`, e para objeto a `forma`.
  - Apagar `_id_slot` e as funções `*_png`, junto com as chamadas que só passam `""`.
- **Teste que prova:** em `palco/testes/test_buscas.py`, afirmar que `"vitrine.tscn"` não está em `godot.py`, `"rosto_herdado"` não está em `palco.gd` nem em `render.py`, e `"func candidatos_objeto_png"` não está em `biblioteca.gd`. Rodar `ferramentas/validar.gd` no exemplo e afirmar que a lista de peças de um evento `movimento` traz `movimento.<gatilho>` quando existe.
- **Origem:** `godot-palco.md` #12 (parte que sobrou) e resto do #6.

### GOD-5 — Caminho absoluto da fonte no A/B  (baixo)
- **Onde:** `random_builds/builds/palco/ab.py:20` (`FONTE`).
- **Defeito:** `C\:/Windows/Fonts/arialbd.ttf` fixo. Só afeta o lado a lado do A/B, fora da produção.
- **Conserto:** ler a fonte de `config/palco.json` (`"ab": {"fonte": ...}`). Se faltar, usar `os.environ["WINDIR"]` + `/Fonts/arialbd.ttf`, com o `:` escapado para o drawtext, e cair sem `fontfile` se o arquivo não existir.
- **Teste que prova:** em `random_builds/tests/test_palco_regressions.py`, criar `test_ab_fonte_vem_da_config`. Com `monkeypatch` na config apontando para uma fonte em `tmp_path`, afirmar que o filtro do drawtext usa esse caminho.
- **Origem:** `godot-palco.md` #13.

## Já consertados
- #1 (erro de script sai como OK) → `f5f8cd3`. `render.py:_erros_do_godot` e as linhas 104-110, mais `timeline.gd:147-150`.
- #3 (arma escalada duas vezes) → `f5f8cd3`. `util.gd:91-95` e o `_draw` do `tocador_folha.gd:189-191`.
- #4 (gatilho para os dois lutadores) → `f5f8cd3`. Veja a regressão em GOD-2 e a animação cortada em GOD-3.
- #5 (a parte `movimento.*`) → `f5f8cd3`. `biblioteca.gd:118,370`.
- #6 (`peca_png.gd` apagado) → `f5f8cd3`.
- #7 (piscada) → `f5f8cd3`. `tocador_folha.gd:156-158`.
- #8 (validador) → `f5f8cd3`. `timeline.gd:147-178` e `timeline_arquivo.py:211-266`.
- #9 (fps 0 e quadro fora da folha) → `f5f8cd3`. Só com `push_warning`: não vai ao relatório.
- #10 (AVI que sobra) → `f5f8cd3`. `render.py:112-113`.
- #11 (versão do Godot) → `f5f8cd3`. `config.py:56-78` e `godot.py:76`.
- #12 (as partes do README e do `timeline.md`) → `f5f8cd3`.

## Alarmes falsos
- Nenhum. Os 13 itens se confirmaram no código de 11/10.

## Decisões que são do Adrian
- Nenhuma nova. Ligar o duelo de produção pelo palco (`producao.duelo_celular`, hoje "desligado") continua pendente no Grimório (`builds/duelo-palco-sem-corrente`). GOD-1, GOD-2 e GOD-3 só aparecem em vídeo publicado depois dessa chave, ou quando ele desenhar rosto/arma com esses gatilhos no Ateliê.
