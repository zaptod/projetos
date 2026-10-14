# Consertos — publicacao (verificação de 14/10/2026)

- **Parte:** `publicacao` (`ferramentas/postar.py`, `random_builds/builds/publicar/**`, `historias/contos/publicar/**`, `random_builds/builds/contas.py`, `grade.py`)
- **Relatórios de origem:** `postar.md` (5), `publicar-builds.md` (6), `publicar-historias.md` (10)
- **Contagem:** 7 abertos / 14 consertados / 0 falsos
- O `a34b355` ("os 8 itens, com testes") fechou de fato 14 dos 21. Dois deles ficaram pela metade e seguem abertos aqui: PUB-1 (exceção depois do clique) e PUB-3 (renomear). Os testes novos passam no HEAD: `random_builds` 42 passed (`test_conserto_publicacao_1110`, `test_trava_do_ledger`, `test_youtube_publicar_assim`) e `historias` 26 passed (`test_conserto_publicacao_1110`).
- O `e3e08fc` (fila lateral do ledger) é anterior a estes relatórios, que já o tinham como consertado. O item builds #3 era um efeito novo dele e foi fechado pelo `a34b355`.
- A **decisão `d104da1`** (`decisoes/publicacao/build-so-no-tiktok.json`, opção `divida`: "mesma regra das histórias", 13/10) **NÃO está implementada**, nem no HEAD nem em ramo nenhum (`git log --all -G "divida.*build"` vazio). Ela vira o PUB-2.

---

### PUB-1 — Clique dado no YouTube e marca "a conferir" que falha: o vídeo volta à fila  (alto)
- **Onde:** `random_builds/builds/publicar/youtube_web.py:1528` (`_depois_do_clique`, os dois `_desf.resolver`); `historias/contos/publicar/catalogo.py:283` (`publicar_youtube`); `ferramentas/postar.py:1227` (`_subir_parte_no_youtube`), `:1580` (`postar_historia`), `:3681` (`postar_build`), `:4793` (`_em_voo`)
- **Defeito:** o `a34b355` grava `laudo["clicou"]` e marca "a conferir" quando algo levanta depois do clique. Mas, se a própria marca falha (`NaoConsegviMarcar`: trava `youtube_a_conferir` ocupada por 20 s, disco, JSON), a falha é engolida e nada durável guarda o clique:
  - **builds:** `youtube_clicou` só impede a reposição do MESMO horário, e o vídeo é escolhido de novo no horário seguinte;
  - **histórias:** o laudo do pedaço que falhou nunca entra em `provas`, porque o catálogo só o anexa depois do sucesso. A ficha não ganha `youtube_clicou` e, se a mensagem tem marca de rede, `_derrubados_pela_rede` repõe a mesma parte na hora.
- **Conserto:**
  1. Em `catalogo.publicar_youtube`, anexar o `laudo` a `provas` ANTES de chamar `publicar_como_configurado`. Na exceção, `_subir_parte_no_youtube` olha `provas[-1].get("clicou")`.
  2. No `postar_historia`, se o laudo da tentativa tem `clicou`, gravar `ficha["youtube_clicou"] = True`. `_derrubados_pela_rede` já respeita essa chave.
  3. Em `_em_voo`, guardar se o `yield` levantou. Se levantou com `voo["etapa"] == "clicou"` e `_voo_no_ledger(voo)` está vazio, chamar a mesma marcação de `_pousar_voo_perdido` (`desfecho.marcar_para_conferir`, com `aviso`). Se essa marca também falhar, gravar o voo numa lista durável da ficha da trava (`_DONA["voos_sem_marca"]`), e a rodada seguinte o pousa primeiro (como `_pousar_voo_perdido` já faz com a dona morta) e não publica aquele alvo enquanto a marca não gravar.
- **Teste que prova:** `ferramentas/tests/test_clique_sem_marca_regressions.py`.
  - (a) Builds: `_youtube_dos_builds` é dublado para pôr `laudo["clicou"]=True` e levantar `TimeoutError("timed out")`, e `desfecho.marcar_para_conferir` para levantar `NaoConsegviMarcar`. Com a ficha da trava ativa, afirma que a rodada seguinte não escolhe o mesmo `generation_*` (hoje escolhe).
  - (b) Histórias: com o `catalogo.publicar_youtube` dublado do mesmo jeito, afirma que a ficha tem `youtube_clicou` e que `_derrubados_pela_rede(ficha) == []` (hoje dá `["youtube"]`).
- **Origem:** `publicar-builds.md` #4

### PUB-2 — Build que saiu só no TikTok nunca chega ao YouTube (decisão d104da1 não aplicada)  (médio)
- **Onde:** `ferramentas/postar.py:3456` (`_builds_prontos`, "qualquer plataforma conta"), `:3646` (`postar_build`, `alvo = proximo_build(...)` depois de `ja_tk`), `:3295` (`_juntar_reposicao`)
- **Defeito:** quando o YouTube dos builds cai e o TikTok confirma, a reposição sobe OUTRO build no YouTube. O primeiro fica só no TikTok para sempre: fora da fila, fora da recuperação (que só trata privados) e fora da reserva.
- **Conserto:** fazer, para os builds, a mesma dívida das histórias (decisão `publicacao/build-so-no-tiktok`, opção `divida`).
  - Criar `_divida_do_youtube_dos_builds()` → `(alvo, quando)`. Ela procura no ledger de builds o `video_id` com linha `tiktok` publicada a partir de `CORTE_DA_DIVIDA_DOS_BUILDS = "2026-10-13"` e sem linha `youtube` publicada, e aplica os crivos de sempre: item ainda no catálogo, fora da lista "a conferir" do YouTube, `titulo_repetido` falso e áudio não mudo.
  - Em `postar_build`, antes de `proximo_build`, se há dívida, subir ESSE alvo só no YouTube (`ficha["so_youtube"] = True`, `ficha["youtube_devido"] = <quando>`), um por horário. Com `alvo` igual, `_juntar_reposicao` já junta as fichas.
  - O TikTok do horário segue com `proximo_build()`, como nas histórias.
- **Teste que prova:** `ferramentas/tests/test_divida_dos_builds_regressions.py`. Ledger temporário com o `generation_00101` publicado só no TikTok (14/10) e catálogo com 00101 e 00102. `postar_build()` com o YouTube e o TikTok dublados: afirma que o YouTube recebeu `generation_00101` e o TikTok `generation_00102`. Hoje o YouTube recebe o 00102 e o 00101 fica órfão. Um segundo caso, com a linha do TikTok de antes do corte, afirma que nada muda.
- **Origem:** `postar.md` #3 (decisão `publicacao/build-so-no-tiktok`, commit `d104da1`)

### PUB-3 — `renomear` grava o registro e depois falha ao mover a pasta: a conta aponta para login que não existe  (médio)
- **Onde:** `random_builds/builds/contas.py:262-310` (`renomear`, `_gravar(dados)` seguido de `origem.rename(alvo)`)
- **Defeito:** o `a34b355` só inverteu a ordem. Agora a gravação vem antes e o `rename` depois, sem desfazer. No Windows o `rename` falha justamente com o Chrome aberto naquele perfil. Medido no HEAD com um arquivo aberto dentro da pasta: `PermissionError` no rename, o registro já diz `historinhas`, a pasta continua `tiktok__canal2` e `perfil()` aponta para `tiktok__historinhas`, que não existe. O próximo upload pede login.
- **Conserto:** dentro do `_editar`, guardar `copia = json.loads(json.dumps(dados))` antes de alterar. Depois de `_gravar(dados)`, fazer o `rename` num `try`. Se ele levantar, chamar `_gravar(copia)` (o registro volta ao nome antigo) e levantar `RuntimeError(f"nao renomeei: a pasta {origem} esta em uso ({exc}); feche o Chrome desse perfil")`. A alternativa é renomear primeiro e desfazer o `rename` se a gravação falhar. Nos dois casos, nunca deixar só um dos dois mudado.
- **Teste que prova:** `random_builds/tests/test_contas_renomear_regressions.py`. Runtime temporário, conta `canal2` escolhida para `historias` e um arquivo aberto em `browser_profiles/tiktok__canal2/Cookies`. Afirma que `renomear("tiktok","canal2","historinhas")` levanta, que `contas("tiktok")` continua com `canal2`, que `ativa("tiktok","historias") == "canal2"` e que `perfil(...)` aponta para a pasta que existe. Hoje o registro fica com `historinhas`.
- **Origem:** `publicar-historias.md` #7

### PUB-4 — `cortes.pedacos` devolve fatia curta ou negativa  (médio)
- **Onde:** `random_builds/builds/publicar/cortes.py:160-191` (`pedacos`), `:143` (`_mais_perto`)
- **Defeito:** ao subir `quantos`, a escolha de um corte pode passar do ponto ideal do corte seguinte, e o fallback `min(ideal, anterior + limite, ...)` cai antes do anterior. A verificação final só olha `<= limite + MARGEM_S`. Medido no HEAD: `pedacos(598.7, pontos=[159.7, 384.5, 417.6])` dá uma fatia de 11,4 s, e em 20 000 sorteios saem 6 fatias abaixo de `MINIMO_S`, uma delas negativa (343,78 → 342,44). Hoje está latente, porque nenhuma parte passa de 182 s. Quando disparar, sobe um Short de 1-11 s ou cai no vídeo inteiro fora do Shorts.
- **Conserto:** no laço, usar `maximo=min(anterior + limite, duracao - MINIMO_S, ideal + alvo - MINIMO_S)` e, no fallback, `escolha = max(anterior + MINIMO_S, min(ideal, anterior + limite, duracao - MINIMO_S))`. Antes do `return`, exigir também `all(fim - ini >= MINIMO_S for ini, fim in fatias)`; se falhar, `quantos += 1`. Se nada servir até `MAX_PEDACOS`, cortar no relógio (fatias iguais de `duracao / quantos`).
- **Teste que prova:** `random_builds/tests/test_cortes_fatias_regressions.py`. Caso fixo `pedacos(598.7, pontos=[159.7, 384.5, 417.6])` e 5 000 sorteios com `random.seed(1)` (duração 181-1200 s, 1-12 fronteiras). Afirma que toda fatia tem `MINIMO_S <= fim - ini <= limite + MARGEM_S` e que as fatias são contíguas e crescentes. Hoje falha no caso fixo.
- **Origem:** `publicar-builds.md` #5

### PUB-5 — `_nomes_no_banco` guarda a falha de leitura para o resto do processo  (baixo)
- **Onde:** `random_builds/builds/publicar/catalogo.py:131` (`_nomes_no_banco`, `@lru_cache` com `return None` no `except`), usado por `_falta_estreia` (`:146`)
- **Defeito:** uma leitura do banco que falhou uma vez faz toda build sem estreia dizer "estreia não gravada" (tarefa) em vez de "estreia impossível" (lápide) até o app ou o bot reiniciar.
- **Conserto:** tirar o `@lru_cache` e usar um cache manual (`_NOMES: frozenset | None = None` no módulo) preenchido só quando a leitura deu certo. Com falha, devolver `None` sem guardar, para a próxima chamada tentar de novo.
- **Teste que prova:** `random_builds/tests/test_nomes_no_banco_cache_regressions.py`. `carregar_database` dublado para levantar na 1ª chamada e devolver `[{"nome": "Ana"}]` na 2ª. Afirma que a 2ª chamada de `_nomes_no_banco()` devolve `frozenset({"Ana"})` e que o dublê foi chamado 2 vezes. Hoje devolve `None` e o dublê é chamado 1 vez.
- **Origem:** `publicar-builds.md` #6

### PUB-6 — `conformidade()` acusa o canal `zombie` para sempre  (baixo)
- **Onde:** `random_builds/builds/contas.py:339` (`conformidade`, laço `for canal in CANAIS`)
- **Defeito:** a regra 3 cobra conta própria de todo canal que não é `geral`. O `zombie` não publica e gera 3 alertas que nunca apagam, então o "TUDO DENTRO DO PADRAO" de `ferramentas/auditoria_contas.py` nunca aparece.
- **Conserto:** constante `CANAIS_PUBLICANDO = ("builds", "historias")` (o zombie entra quando estrear). A regra 3 itera só sobre ela. `CANAIS` fica igual, para o app poder escolher conta para o zombie.
- **Teste que prova:** `random_builds/tests/test_contas_conformidade_regressions.py`. Registro com `neural_fights`/`historinhas` escolhidos e identificados nos 3 serviços. Afirma `conformidade() == []`. Hoje devolve os 3 itens do zombie.
- **Origem:** `publicar-historias.md` #9

### PUB-7 — Memo dos trechos pretos não leva o critério na chave  (baixo)
- **Onde:** `historias/contos/publicar/qualidade.py:532` (`erros_de_preto`, chave `real|mtime|size|layout`; arquivo `_vistoria_pretos.json`)
- **Defeito:** mudar `PRETO_AREA`/`PRETO_PIXEL` não mede de novo nada que já foi medido, até o mp4 ser re-renderizado.
- **Conserto:** acrescentar à chave `f"|{PRETO_AREA}|{PRETO_PIXEL}|{PRETO_MIN_S}|{PRETO_FPS}"`. As entradas antigas morrem sozinhas e são medidas uma vez de novo.
- **Teste que prova:** `historias/tests/test_memo_pretos_criterio_regressions.py`. `trechos_pretos` dublado com contador: 1ª chamada mede; troca `PRETO_AREA` (monkeypatch); a 2ª chamada mede de novo e o contador vai a 2. Hoje fica em 1.
- **Origem:** `publicar-historias.md` #10

---

## Já consertados
- `postar.md` #1 (`postar.cmd` com `>>` mata o horário seguinte) → `a34b355`. `escrever_lancador` grava `--saida ... > NUL 2>&1`, o `postar.cmd` em disco já foi regravado (12/10 19:44), as 10 tarefas rodam ele e o log sai datado.
- `postar.md` #2 (adiadas furam a trava de render) → `a34b355` (`postar.py:1014`)
- `postar.md` #4 (`--tudo` sem vistoria, veto, marca nem prova) → `a34b355` (`escoar_historias` consome `proxima_historia`)
- `postar.md` #5 (fichas de builds com `feito` falso e sem `so_youtube`) → `a34b355`
- `publicar-builds.md` #1 ("Publicar mesmo assim" sem clique vira publicado) → `a34b355` (`_confirmar`: `continue`)
- `publicar-builds.md` #2 (marca `[audio]` não promovida) → `a34b355` (`desfecho.py:285`)
- `publicar-builds.md` #3 (reescrita do ledger com leitor aberto) → `a34b355` (3 tentativas, `.tmp` apagado, linha vai para pendentes, ERRO no diário)
- `publicar-historias.md` #1 (`contas.json` regravado de leitura falha) → `a34b355`
- `publicar-historias.md` #2 (`_pareceres.json` sem trava/atômico) → `a34b355`
- `publicar-historias.md` #3 (pedaço 1 sobe 2x) → `a34b355` (`PublicacaoParcial` + registro parcial)
- `publicar-historias.md` #4 (ffmpeg no prazo deixa mudo passar) → `a34b355`
- `publicar-historias.md` #5 (ffprobe no prazo barra vídeo bom) → `a34b355`
- `publicar-historias.md` #6 (`--comecar` 3 h antes) → `a34b355`
- `publicar-historias.md` #8 (`escolher` sem limpar o nome) → `a34b355`

## Alarmes falsos
- Nenhum. Os 21 defeitos eram reais no código de 11/10.

## Observações fora da contagem (achadas na verificação)
- **Veto que falha aberto com `_pareceres.json` ilegível** (`historias/contos/publicar/parecer.py:472` `veto_por_id`, `:251` `situacao_do_video`; `ferramentas/postar.py:732` `_veto_lembrado`). Agora a leitura levanta em vez de virar `{}`, mas todos os leitores engolem a exceção e respondem "sem parecer". Enquanto o arquivo estiver corrompido ou trancado, a parte reprovada sai (é o contrário da lista "a conferir", que falha fechada). Com a gravação atômica, o gatilho ficou improvável. Sugestão: `_veto_lembrado` e `_retencao` tratarem a exceção de leitura como "retido" e avisarem no diário uma vez por dia.
- **`parecer.limpar_motivos_gravados`** (`parecer.py:789`) ainda grava com `open("w")` sem trava e sem `.tmp`. Hoje ninguém a chama (só está no `__all__`). Se for usada, deve ir por `_gravar_lembretes` dentro de `travas.trava("pareceres_json")`.

## Decisões que são do Adrian
- Nenhuma nova. A única de produto (`build-so-no-tiktok`) já foi tomada em 13/10 (`divida`) e só falta implementar (PUB-2).
