# Auditoria profunda do palco Godot — 11/10/2026 (só leitura)

Fatia: `palco/nucleo/*.gd`, `palco/project.godot`, `palco/palco.tscn`,
`palco/ferramentas/**`, `palco/testes/**`, a ponte Python
`random_builds/builds/palco/*.py` e o que escreve a timeline em
`neural_fights/recording/` (`timeline_arquivo.py`, `documento()` e
`gravar_timeline()` de `timeline.py`, `_salvar_timeline` de `fight_recorder.py`).
Nada do projeto foi alterado; os arquivos do Adrian (`LICENCAS.md`, `fogo.tscn`,
`efeitos/folhas/**`) não foram tocados. Provas, quadros e scripts de sondagem
estão em `C:\Users\adrian\AppData\Local\Temp\claude\e--projetos\65fe1aa9-5965-4d18-9756-f332b198f269\scratchpad\auditoria2\godot\`
(abaixo: `<scratch>`).

## Como foi provado

- Godot `4.7.2.stable.official` em `E:/ferramentas/godot/` (o que o
  `config/palco.json` aponta), `APPDATA` trocado para `palco/_userdata` como a
  ponte faz.
- `--headless --check-only --script` nos 26 scripts (11 do núcleo, 2
  ferramentas, 4 testes, 9 da biblioteca que o palco instancia): **26/26 rc 0**.
- Testes GDScript existentes: `ferramentas/testes.gd`, `testes/tocador_folha.gd`,
  `testes/consumo_atelie.gd` (5/5 OK), `testes/folha_animada_lista.gd`: **4/4 rc 0**.
  `ferramentas/validar.gd` no exemplo: OK, 240 passos, 12 peças.
- Suíte Python: `random_builds/tests/test_palco_regressions.py`,
  `test_palco_atelie_e3.py`, `test_palco_edicao_regressions.py`,
  `test_palco_producao_regressions.py` e `palco/testes` com `TEMP=E:\tmp_pytest`:
  **91 passed em 46 s** (inclui os renders curtos com Godot, antes das 15:25).
- Seis renders de verdade pela ponte (`render.renderizar`, timelines sintéticas
  de 2 s gravadas no `<scratch>`, nunca em `outputs/`), antes da janela :25–:55:

| caso | resultado | quadros / duração (ffprobe) | quadros distintos? |
|---|---|---|---|
| `valida` | ErroPalco: passou de 107 s (ver "Não confirmados", carga) | relatório do Godot: ok, 64 quadros, laço 68,8 s | — |
| `evento_sem_campo` (explosao sem x/y/origem) | rc 2 "evento 3 (explosao) sem x" | 0 | — |
| `acerto_pelado` (acerto sem alvo/autor/x/y/tier) | ok | 64 / 2,133 s, 1080x1920 | sim (5 md5 diferentes, 364–521 cores) |
| `peca_sem_folha` (Adagas Gêmeas/Dupla, Cristais Flutuantes/Orbital, classe inexistente) | ok, 9 reservas | 64 / 2,133 s | sim (1028–1160 cores) |
| `zero_eventos` (sem eventos, sons null) | Godot ok; Python barra: 1 som distinto < 6 | 60 | — |
| `n_zero` | rc 2 "n invalido: 0.0" | 0 | — |
| `mesmo_quadro_corte` (ko e acerto no mesmo passo + remapeamento com corte) | ok | 52 / 1,733 s (= 48 do corte + 4 de hitstop) | sim |

- Sondas headless (`<scratch>/gd/bordas.gd`, `piscada.gd`, `expr_e_escala.gd`,
  rodadas com `--script` de fora do projeto) e dois experimentos de
  timeout/kill (`timeout_kill.py`, `script_error_e_kill.py`).

## Examinado

| arquivo | funções lidas |
|---|---|
| `palco/nucleo/palco.gd` | 20 (todas) |
| `palco/nucleo/timeline.gd` | 26 (todas) |
| `palco/nucleo/biblioteca.gd` | 41 (todas) |
| `palco/nucleo/sons.gd` | 8 (todas) |
| `palco/nucleo/plano.gd` | 9 (todas) |
| `palco/nucleo/tocador_folha.gd` | 11 (todas) |
| `palco/nucleo/estilo.gd` | 3 (todas) + os exports |
| `palco/nucleo/util.gd` | 7 (todas) |
| `palco/nucleo/peca.gd` / `peca_reserva.gd` / `gatilhos_animacao.gd` | 4 / 1 / 2 (todas) |
| `palco/project.godot`, `palco/palco.tscn` | inteiros |
| `palco/ferramentas/testes.gd`, `validar.gd` | 1, 2 |
| `palco/testes/*.gd` (4), `test_buscas.py`, `test_folha_animada.py` | 7, 1, 3 |
| `random_builds/builds/palco/godot.py` | 9 (todas) |
| `random_builds/builds/palco/render.py` | 3 (todas) |
| `random_builds/builds/palco/config.py` | 6 (todas) |
| `random_builds/builds/palco/checagens.py` | 8 (todas) |
| `random_builds/builds/palco/producao.py` | 19 (todas) |
| `random_builds/builds/palco/plano.py` | 9 (todas) |
| `random_builds/builds/palco/sons.py` | 7 (todas) |
| `random_builds/builds/palco/cli.py` | 10 (todas) |
| `random_builds/builds/palco/edicao.py` | 14 (todas) |
| `random_builds/builds/palco/fonte.py`, `ab.py`, `sintetica.py`, `previa_animacao.py`, `prova_e3.py`, `__init__.py` | 3, 5, 3, 7, 2, 0 |
| `neural_fights/recording/timeline_arquivo.py` | 14 (todas) |
| `neural_fights/recording/timeline.py` | 2 (`documento`, `gravar_timeline`: o que o Godot lê) |
| `neural_fights/recording/fight_recorder.py` | 1 (`_salvar_timeline`) |
| fora da fatia, lidos porque o palco os instancia | `lutador_padrao.gd`, `arma_padrao.gd`, `vfx_padrao.gd`, `objeto_padrao.gd`, `arena_padrao.gd`, cabeçalho de `hud_padrao.gd` |
| dados | `catalogo_animacoes.json` (314 peças), `estilo.tres` (vazio: só os padrões do `estilo.gd`), os 5 `animacao.json` reais, `exemplos/exemplo.timeline.json` |

## Confirmados (do mais grave ao menos)

### 1. Erro de script em todo quadro sai como render OK (rc 0, `ok: true`, zero avisos)

- **Onde:** `random_builds/builds/palco/render.py:97-100` (só olha `rc` e
  `rel["ok"]`), `godot.py:82-85` (o filtro de `SCRIPT ERROR` existe SÓ no
  `--import`); `palco/nucleo/timeline.gd:134-175` (`validar` não confere
  `tabelas` nem `arena`).
- **O defeito:** um erro de execução em GDScript aborta só a função, o laço
  continua, o Movie Maker grava, o palco escreve `ok: true` e sai 0. A ponte
  grava o `godot.log` mas não o lê. Foi exatamente a classe do bug da
  `folha_animada` de 07/10 ("SCRIPT ERROR a cada projétil" com vídeo saindo).
- **Quando:** qualquer peça/caminho com erro de execução; na prova,
  `tabelas: null` (o validador passa) faz `_atelie_efeitos` (`palco.gd:585`)
  chamar `null.get` a cada quadro.
- **Prova:** `<scratch>/script_error/`: `renderizar` devolveu `ok=True`,
  64 quadros, `avisos_godot=[]`; `_saida_trabalho/godot.log` tem **64 linhas
  `SCRIPT ERROR: Invalid call. Nonexistent function 'get' in base 'Nil'`**.
- **Conserto sugerido:** em `render.py`, depois de gravar o log, contar
  `SCRIPT ERROR`/`ERROR:` em `filme["saida"]` e levantar `ErroPalco` (ou ao
  menos listar em `problemas`); e em `timeline.gd:validar` exigir `tabelas` e
  `arena` como dicionários.

### 2. O corpo do lutador nunca recebe o gatilho `golpe_fase`: o `elif` é código morto

- **Onde:** `palco/nucleo/palco.gd:353-357`.
- **O defeito:** `if str(s.get("expr", "")) != "": gatilho("expr") elif
  golpe_fase > 0: gatilho("golpe_fase")`. O canal `expr` é um índice numérico
  (JSON vira float; `str(18.0)` = `"18"`), nunca vazio, então o corpo recebe
  `expr` em todo quadro e o ramo `golpe_fase` é inalcançável. O catálogo tem
  **24 animações `golpe_fase` no grupo lutador** (e `lutador.rosto.boca`) que
  nunca tocarão. E como o gatilho é sempre o mesmo `"expr"`, a animação
  `expr` nunca reinicia nem muda com a expressão.
- **Quando:** assim que o Adrian desenhar uma folha de golpe para um corpo.
- **Prova:** `<scratch>/gd/expr_e_escala.gd`: no exemplo, **156 passos com
  `golpe_fase > 0`, 0 deles com `str(expr) == ""`**.
- **Conserto sugerido:** mandar os dois gatilhos (o `expr` é do rosto, o
  `golpe_fase` do corpo), e `expr` só quando o índice muda.

### 3. Arma do Ateliê é escalada duas vezes e perde escala/espelho/rotação do `animacao.json`

- **Onde:** `palco/nucleo/palco.gd:427-432` (posição, rotação e
  `UtilPalco.esticar_arma`), `util.gd:92-99` (sem `comprimento_ref` assume
  100 px → `scale = L/100`), `tocador_folha.gd:76-79` (lê `escala`,
  `espelho`, `rotacao` para `scale`/`rotation_degrees`) e `:168-172` (aplica
  a regra "N corpos" por cima).
- **O defeito:** o `TocadorFolha` não declara `comprimento_ref` nem
  `desenha_comprimento`; `esticar_arma` então multiplica o nó por
  `comprimento/100` E o `_draw` ainda escala pelo diâmetro do corpo. Uma arma
  de 1,5 m sai 150% do que a regra do Ateliê diz; uma adaga de 0,6 m, 60%.
  Além disso `no.scale = ONE * k` apaga o `espelho` (sinal) e a `escala` do
  json, e `no.rotation = ângulo` apaga a `rotacao`.
- **Quando:** toda arma com folha do Ateliê (hoje: Cristais Flutuantes).
- **Prova:** `expr_e_escala.gd` com a peça real `arma.estilo.cristais_flutuantes`:
  `comprimento_ref=<null>`, escala do nó 1,27, fator do tocador 0,543 →
  **217 px desenhados contra 170 px da regra (127%)**; depois de
  `esticar_arma(60)`, `scale = (0.6, 0.6)` (escala/espelho do json sumiram).
- **Conserto sugerido:** em `esticar_arma`, tratar peça com `catalogo_peca`
  como `desenha_comprimento` (escala 1), e no tocador aplicar `escala`,
  `espelho` e `rotacao` dentro do `_draw` (não no transform do nó).

### 4. Todo evento manda o gatilho para OS DOIS lutadores e AS DUAS armas

- **Onde:** `palco/nucleo/palco.gd:623-629`.
- **O defeito:** `evento()` é filtrado por `slot/alvo/autor/iniciador`
  (`:619-622`), mas `gatilho()` vai para `lut` e `arm` inteiros, sem dono. O
  catálogo tem `acerto` e `ko` no grupo lutador e `projetil_fim` (7),
  `arma_puxada` (7), `transformado` (7) no grupo arma: no K.O., o vencedor
  "cai" junto; quem bateu toca a reação de `acerto`; a arma de p1 reage ao
  projétil de p2.
- **Quando:** quando houver folha de corpo/arma com esses gatilhos (latente
  hoje: só Cristais Flutuantes tem folha, e sem esses gatilhos).
- **Prova:** leitura das linhas + inventário do catálogo
  (`<scratch>`, saída do inventário: lutador `{'acerto': 1, 'ko': 1, ...}`,
  arma `{'projetil_fim': 7, 'arma_puxada': 7, 'transformado': 7, ...}`).
- **Conserto sugerido:** escolher os slots pelos campos do evento
  (`slot`, `alvo`, `autor`, `iniciador`, `vencedor`, `perdedor`) como já se
  faz para `evento()`; `ko` → só o perdedor.

### 5. Sete peças `movimento.*` do catálogo nunca são procuradas pela biblioteca

- **Onde:** `palco/nucleo/biblioteca.gd:135-138` e `:487-491` (ids
  `skill.`, `skill.tipo.`, `evento.<tipo>`, `efeito.<tipo>`, `elemento.`,
  `efeito.generico`); `palco.gd:660-661` põe o gatilho do movimento só na
  `variante` da cadeia `.tscn`.
- **O defeito:** para `tipo == "movimento"` o palco pede
  `evento.movimento`/`efeito.movimento`; o catálogo cadastra
  `movimento.dash`, `movimento.knockback`, `movimento.poeira`,
  `movimento.pulo`, `movimento.aterrissagem`, `movimento.corrida`,
  `movimento.recuperacao` (grupo efeito, gatilho = o nome). Desenhadas no
  Ateliê, nunca aparecem. O mesmo vale para os 4 `lutador.rosto.*`
  (nenhum prefixo `lutador.rosto` é procurado desde que o `lutador_padrao`
  virou marcador).
- **Prova:** inventário de prefixos do catálogo × prefixos que o
  `biblioteca.gd` consulta (`buff. classe. efeito. elemento. estado.
  estado_lutador. evento. skill.`): `movimento.` e `lutador.rosto` ficam
  de fora.
- **Conserto sugerido:** no `_evento`, para `movimento`, incluir
  `"movimento." + slug(gatilho)` na frente da lista de ids de
  `bib.evento`/`tem_folha_evento`.

### 6. `biblioteca.gd` carrega um script apagado (`peca_png.gd`) quando um PNG do manifesto aparece

- **Onde:** `palco/nucleo/biblioteca.gd:40` (`PECA_PNG`), `:304-329`
  (`_cena_png`: `set_script(load(PECA_PNG))`, `_vetor(..., no.get("empunhadura"))`,
  `no.call("preparar")`).
- **O defeito:** `nucleo/peca_png.gd` saiu no commit `30fbc7e` e a cadeia
  `png:` ficou. Com `manifesto_slots.json` + PNG em `partes/`, dá `File not
  found`, `Invalid type in function '_vetor' ... Nil to Vector2`, e a peça
  cai na reserva como "(png ilegivel)".
- **Quando:** hoje é código morto (não há `manifesto_slots.json` em
  `palco/biblioteca/` e nada o grava), mas o `CONTRATO_SLOTS.md` e o
  `docs/palco/README.md` ainda descrevem a cadeia como viva.
- **Prova:** `<scratch>/gd/bordas.gd`: `peca_png.gd existe? BUG`; com um
  manifesto de mentira, `bib.arma("Reta","")` → 2 `ERROR` + 1 `SCRIPT ERROR`
  e `escolhas = {"armas:Reta/": "(png ilegivel: ...)"}`.
- **Conserto sugerido:** apagar a cadeia `png:` (`_carregar_destinos`,
  `png_do_slot`, `_cena_png`, `candidatos_*_png`) ou restaurar o script;
  e atualizar os dois docs.

### 7. Piscada de 2 quadros de vídeo quando uma animação sem loop acaba e volta ao repouso

- **Onde:** `palco/nucleo/tocador_folha.gd:129-130` (`_trocar(_ocioso)`) e
  `:133-142` (`_trocar` não zera `indice`/`decorrido`); `_draw` em `:162`
  devolve sem desenhar quando `indice >= quadros.size()`.
- **O defeito:** ao terminar o golpe (8 quadros) o tocador troca para a
  ociosa (2 quadros) com `indice = 7` → nada é desenhado até o próximo avanço
  de quadro da folha (1/fps da folha ≈ 2–3 quadros de vídeo a 30 fps).
- **Prova:** `<scratch>/gd/piscada.gd`: quadros 15 e 16 `anim=ocioso
  indice=7/2 <-- NADA DESENHADO`; "2 quadro(s) de vídeo sem desenho".
- **Conserto sugerido:** em `_trocar`, `indice = 0; sentido = 1; decorrido = 0.0`.

### 8. O validador deixa passar timelines que o palco desenha errado em silêncio

- **Onde:** `palco/nucleo/timeline.gd:160-169` (só conta 2 entradas e
  `raio_corpo`), sem checar `slot ∈ {p1, p2}`, `tabelas` e `arena`;
  `neural_fights/recording/timeline_arquivo.py:190-312` também não confere
  os slots.
- **O defeito:** com `slot: "a"/"b"`, `cabecalho_lutador("p1")` devolve `{}`
  (`:343-347`): lutadores com raio padrão, sem arma, rótulo "p1"/"p2", e
  render "ok". `tabelas: null` → item 1. `arena: null` → `_evento` de
  `obstaculo` (`palco.gd:647`) faz `null.get` (SCRIPT ERROR, o evento some).
- **Prova:** `bordas.gd`: slots a/b → 0 erro; tabelas null → 0 erro;
  arena null → 0 erro (e o render do item 1).
- **Conserto sugerido:** exigir exatamente um `p1` e um `p2`, `tabelas` e
  `arena` dicionários (nos dois validadores).

### 9. `tocador_folha.carregar` aceita `fps: 0` (congela calado) e quadros que não cabem na folha

- **Onde:** `palco/nucleo/tocador_folha.gd:70` (`fps = maxf(0.01, ...)` →
  100 s por quadro) e `:63-82` (nenhuma conferência de `x+w`, `y+h` contra a
  textura).
- **Prova:** `bordas.gd`: fps 0 → `fps=0.01`, índice 0 depois de 1 s;
  8 quadros de 64 px numa folha 4x4 → `carregar` devolve true.
- **Quando:** `animacao.json` editado à mão ou exportado errado pelo Ateliê;
  o `draw_texture_rect_region` fora da textura desenha lixo (não provado
  visualmente: headless não desenha).
- **Conserto sugerido:** `fps <= 0` → 12 com `push_warning`; recusar quadro
  fora de `textura.get_size()` e anotar no relatório.

### 10. Timeout e rc 2 deixam AVI no `_trabalho`

- **Onde:** `random_builds/builds/palco/render.py:95-102` (levanta antes de
  qualquer limpeza; `shutil.rmtree(trabalho)` só no fim feliz, `:173-174`).
- **O defeito:** o Movie Maker grava o AVI incrementalmente (6,5 MB aos 5 s,
  15,7 MB aos 11 s na prova); no timeout ou no rc 2 o arquivo fica. A
  produção limpa o seu (`producao._limpar_falha`), o `main.py palco render`
  e o A/B não.
- **Prova:** `<scratch>/valida/_saida_trabalho/saida.avi` (4,1 MB após o
  timeout) e `<scratch>/evento_sem_campo/_saida_trabalho/saida.avi` (40 KB,
  1 quadro, rc 2).
- **Conserto sugerido:** `avi.unlink(missing_ok=True)` no caminho de erro
  (manter `job.json`, `godot.log` e o relatório).

### 11. Nenhuma conferência da versão do Godot

- **Onde:** `random_builds/builds/palco/config.py:29-42` (só `is_file()`);
  `palco/project.godot:13` pede `"4.7"`.
- **O defeito:** trocar o executável no `config` (ou `NF_GODOT`) por outro
  4.x roda sem aviso; diferença de versão muda o Movie Maker/importador e a
  única pista seria o log. Baixo, mas foi pedido.
- **Conserto sugerido:** `--version` uma vez por sessão (cache) e comparar
  o `major.minor` com `config/features`.

### 12. Documentação e código fora de sincronia (confunde quem repara)

- `docs/palco/README.md:49,156,173` e o docstring de `godot.gravar_filme`
  (`godot.py:164`) falam de `main.py palco vitrine` e
  `res://ferramentas/vitrine.tscn`: o subcomando não existe em `cli.py` e o
  arquivo não existe (`palco/ferramentas/` tem só `testes.gd` e `validar.gd`).
- `docs/palco/timeline.md:537` cita `palco/ferramentas/paridade_corrente.gd`,
  que não existe (o teste `test_palco_corrente_regressions.py` não depende
  dele).
- `palco.gd:94,771` relata `rosto_herdado`, que ninguém preenche desde que
  o `lutador_padrao.gd` virou marcador (sempre `{}`); `render.py:161` o
  repassa.
- `ferramentas/validar.gd` resolve `bib.evento(tipo, tier)` e
  `bib.objeto(tipo, elemento, nome)` sem variante/forma/skill: a lista de
  "peças" que ele imprime não é a que o render usa.

### 13. Caminhos absolutos do Windows em ferramentas de desenvolvimento

- `random_builds/builds/palco/ab.py:20`: `FONTE = "C\\:/Windows/Fonts/arialbd.ttf"`
  (só o lado a lado do A/B); `godot.py:99-112` usa `ctypes.windll` com
  fallback. Nada no caminho de produção; baixo.

## Não confirmados (investigado e limpo, ou sem prova)

- **Godot órfão no timeout:** NÃO. Matar o `_console.exe` leva o Godot real
  junto (`script_error_e_kill.py`: pid 8168 vivo aos 12 s, sumiu em < 4 s
  após o `kill()` do launcher; `gravar_filme(timeout=15)` voltou em 15,2 s).
  Uma primeira medição deu 46 s para um `timeout=3`; não reproduziu com a
  sonda instrumentada e fica como observação.
- **AVI/mp4 de 0 bytes como sucesso:** não. `render.py:101` barra AVI vazio;
  mp4 vazio cai em `conferir` como "não tem faixa de vídeo".
- **rc e stderr lidos:** sim (`godot.py:51-60`, `capture_output` com stdout+stderr
  juntos, rc devolvido e traduzido em `MOTIVOS`).
- **Timeline vazia (`n = 0`):** rc 2 "n invalido". **0 eventos:** o Godot
  sai ok com 60 quadros; o Python barra por `min_ids_distintos` (por desenho).
- **Evento com campo faltando:** os da revisão 3 são barrados (rc 2);
  `acerto` sem `alvo/x/y/tier` é aceito e o efeito nasce em (0,0) com tremor
  "light" — é o contrato (`CAMPOS_EVENTO` só cobre a revisão 3).
- **Peça sem folha / lutador sem arte:** cai no marcador neutro
  (`peca_reserva`) e o relatório lista em `reservas`; os quadros do render
  `peca_sem_folha` não são lisos (desvio de luma 24–25, 1028–1160 cores).
- **Dois eventos no mesmo quadro:** lista por quadro (`eventos_por_quadro`);
  o render `mesmo_quadro_corte` deu 52 quadros = 48 do corte + 4 de hitstop,
  7 vfx.
- **Som ausente:** `MesaDeSom.faltando` → `render.py:143` barra.
- **fps zero / divisão por zero:** `hz <= 0` e `n <= 0` barrados;
  `_duracao_atual`, `esticar_arma`, `passo_de` têm `maxf/clamp`;
  `duracao_por_quadro` 0 e negativa terminam o laço (0 ms na sonda).
- **Trecho de remapeamento que dá 0 quadros:** `PlanoQuadros` e `plano.py`
  mapeiam igual (`mapear(0.005) = 0`), e `validar` rejeita duração/velocidade
  ≤ 0.
- **Índice fora da lista:** `amostra` clampa (`n = 1` com `p = 0.5` → ok);
  `_desenhar_quadro` só lê `t_src[f]` com `f < total`; `_marcas` sempre tem
  6 entradas.
- **Sinal conectado duas vezes:** o palco não usa sinais.
  **`queue_free` + acesso:** `_envelhecer_vfx` checa `is_instance_valid` e
  `is_queued_for_deletion`; `_objetos`/`_atelie_efeitos` apagam do dicionário
  ao liberar.
- **Estado entre renders no mesmo processo:** um processo por render; a
  prévia em loop reseta vfx/trauma e os nós de objeto/efeito somem pelo
  `vivos` do quadro seguinte.
- **`res://`/`user://` vs caminho absoluto:** os caminhos absolutos que o
  Godot recebe vêm do job (timeline, relatório, sons) e `FileAccess` os
  aceita; `textura_png`/`tocador_folha` usam `globalize_path`. OK.
- **Hitstop Python × Godot e plano de quadros:** batem (91 testes + a
  conferência em `render.py:134-138`).
- **`garantir_importado`:** o marcador está mais novo que as fontes
  (0,2 s por chamada, não reimporta). Dois renders em paralelo que
  disparassem `--import` ao mesmo tempo poderiam brigar pelo `.godot/`
  (risco teórico, não testado).
- **Prazo do render sob carga:** com 26 Godot headless rodando ao mesmo
  tempo (minha compilação), o laço de 64 quadros levou 68,8 s e estourou o
  prazo de 107 s (`90 + 8 × duração`). Na produção a chave devolve o duelo
  ao pygame, como desenhado; só observação para o "2 em paralelo".
- **`arena: null` em tempo de execução:** só com evento `obstaculo`; não
  renderizado (janela das postagens). Coberto pelo item 8.
- **`draw_texture_rect_region` fora da textura:** efeito visual não provado
  (headless não rasteriza). Coberto pelo item 9.
