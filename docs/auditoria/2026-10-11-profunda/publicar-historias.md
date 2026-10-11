# Auditoria profunda — Publicação das histórias, grade e contas — 11/10/2026

Fatia: `historias/contos/publicar/**`, `random_builds/builds/grade.py`, `random_builds/builds/contas.py`.
Nada do projeto foi alterado. As provas rodaram em
`%TEMP%\claude\...\scratchpad\auditoria2\provas_publicar\` (scripts `p1_*.py` a `p5_*.py`),
com `NEURAL_FIGHTS_RUNTIME_DIR` apontando para uma pasta descartável, `contas.ARQUIVO`,
`parecer.LEMBRETES`, `serie.REGISTRO` e `qualidade._outputs` desviados para lá, e o diário
(`builds.atividade.registrar`) dublado onde a função sob prova o chamaria. Nenhuma prova
dubla a função sob suspeita; o que foi dublado está dito em cada item. Os dois defeitos
desta fatia da auditoria da manhã (#1 ledger sem trava, #2 `serie.publicar` sem trava da
parte) já estão consertados no `e3e08fc` e não são repetidos aqui.

## Examinado

- `historias/contos/publicar/__init__.py` — vazio.
- `historias/contos/publicar/catalogo.py` — 17 funções/classes (+3 propriedades de `Video`); os mp4 prontos com título/descrição, a pausa, a última porta do upload (`publicar_youtube`/`publicar_tiktok`).
- `historias/contos/publicar/serie.py` — 9 funções/classes; publicar a série inteira (vistoria, sobe na ordem, agenda, registra no ledger).
- `historias/contos/publicar/qualidade.py` — 32 funções; a vistoria mecânica do mp4 (ffprobe/ffmpeg, memos em disco, trechos pretos, imagens, prova de origem) e `liberado()`.
- `historias/contos/publicar/parecer.py` — 33 funções/classes; a IA assiste o vídeo, o veredito e a memória dele (`_pareceres.json`), consertado/não assistido.
- `historias/contos/publicar/tipos.py` — 3 funções; rodízio de tipo na fila de postagem (função pura).
- `random_builds/builds/grade.py` — 9 funções; os dez horários do dia, `vencidos`, `slot`, `proximo`, `proximo_em`.
- `random_builds/builds/contas.py` — 29 funções; registro de contas por serviço/canal (`contas.json`), perfis, credenciais, identidade, conformidade.

Total: 8 arquivos, ~132 funções/classes lidas, uma a uma. `grade.py` e `tipos.py` saíram limpos
(as viradas de dia em `slot`/`proximo_em`/`vencidos` e a intercalação do rodízio conferem com
os testes e com o cálculo à mão).

## Confirmados (do mais grave ao menos)

### 1. `contas.json` lido como `{}` quando falha, e a próxima gravação apaga o registro inteiro — gravidade: alta
- Onde: `random_builds/builds/contas.py:117` (`_ler`), `:126` (`_gravar`), e todo escritor (`adicionar`, `escolher`, `remover`, `renomear`, `identificar`).
- O defeito: `_ler` devolve `{}` para qualquer `OSError`/`ValueError` (arquivo trancado por outro processo, JSON pela metade), `estado()` reconstrói o padrão por cima desse `{}` e `_gravar` escreve com `open("w")` + `json.dump`, sem temporário, sem `os.replace` e sem trava. Resultado: uma leitura que falhou UMA vez vira o registro novo, e o registro antigo (qual conta cada canal usa, os ids dos canais) desaparece. Com o arquivo trancado, `open("w")` ainda trunca antes de o `dump` falhar: o registro fica com 0 bytes. Mesmo padrão do #3 da manhã (`pedidos.json`), em outro arquivo.
- Quando acontece: `youtube_web.py:837` chama `identificar()` no meio de uma publicação; o app (`remoto/comandos_app.py:485`) e o painel chamam `escolher()`; o painel/panorama leem a cada tela. Dois deles ao mesmo tempo, ou um crash no meio do `dump`, e `ativa("youtube_web", "historias")` passa a devolver `principal`, `explicita()` vira `False` e `identidade(...).get("id")` vira `""` — o Studio então avisa "o canal não tem id gravado; vai para onde o Studio abrir" (`youtube_web.py:1312`) e publica no canal que estiver aberto. Publicar no canal errado não tem desfazer.
- Prova: `python p1_contas_registro.py <rt>` — registro bom (tiktok e youtube_web com conta própria por canal, id `UC_hist`); com o JSON pela metade `_ler() -> {}`; depois de um `identificar()` o arquivo só tem `['identidades']`, `ativa(tiktok, historias) = principal`, `explicita = False`, `id do historinhas = None`. Com o arquivo trancado por outro handle: `_ler() -> {}`, `escolher()` levanta `PermissionError` e o registro fica com **0 bytes** (tinha 1484). `python p1b_contas_corrida.py <rt>` — dois processos reais (150 `identificar` × 150 `escolher`, sem dublê): 5 leituras vazias e no fim `youtube_web.ativa = {}` — a escolha do canal de builds sumiu.
- Conserto sugerido: gravar por temporário + `os.replace` sob `travas.trava("contas_json")`, e nunca gravar a partir de uma leitura que falhou (distinguir "arquivo não existe" de "não consegui ler" e levantar no segundo caso).

### 2. `_pareceres.json` sem trava e sem gravação atômica: fichas somem e os 125 vetos deixam de barrar — gravidade: alta
- Onde: `historias/contos/publicar/parecer.py:105` (`_lembretes`), `:229` (`_lembrar`, `open("w")` + `json.dump`), também `marcar_nao_assistido:224`, `esquecer:433`.
- O defeito: o mesmo padrão do item 1 na memória dos vereditos. `_lembretes()` devolve `{}` se o arquivo está trancado ou pela metade; `_lembrar` grava o dicionário inteiro por cima, sem temporário nem trava. Quem lê (`veto_por_id`, `lembrado`, `situacao_do_video`, `ja_olhado`) passa a responder "sem parecer", e `qualidade.liberado()` e o `postar._veto_lembrado` deixam o vídeo reprovado sair. A decisão `historias/reprovado-ou-nao-assistido` ("fica retido") deixa de valer sem nenhum aviso.
- Quando acontece: duas faixas da agenda em paralelo (`paralelo_por_gerador`), ou uma faixa e o `postar.py:607`, dando parecer na mesma janela — os dois gravam `_pareceres.json`. Hoje o arquivo tem 293 fichas (125 `reprovado`, 39 `aprovado`), 166 KB; um crash no meio do `dump` o deixa ilegível e a próxima `lembrar` o substitui por uma ficha só.
- Prova: `python p2_pareceres.py <rt>` — duas fichas (uma vetada, `veto_por_id = True`); com o JSON pela metade `_lembretes() -> {}`; depois de `lembrar(novo)` o arquivo tem só `['historia_00051:celular:p01']`, `veto_por_id(vetado) = None`, `situacao_do_video(vetado) = ''`, `ja_olhado(vetado) = False`. Corrida real com 3 processos × 40 `lembrar` (sem dublê): **6 fichas no fim, de 122 esperadas**, e a ficha vetada original sumiu.
- Conserto sugerido: `travas.trava("pareceres_json")` em volta de ler-alterar-gravar, temporário + `os.replace`, e leitura que falha levanta em vez de devolver `{}`.

### 3. Parte cortada em dois Shorts: o 2º pedaço falha, o 1º já subiu e nada é registrado — a rodada seguinte sobe o 1º de novo — gravidade: média
- Onde: `historias/contos/publicar/catalogo.py:309-316` (`publicar_youtube`), chamador `serie.py:247-276` (e `ferramentas/postar.py:1203` pelo mesmo caminho).
- O defeito: `publicar_youtube` percorre `cortes.preparar(...)` e só devolve as URLs no fim; se o segundo upload levanta, a exceção sobe sem informar que o primeiro já está no canal. `serie.publicar` cai no `except Exception` → `erros_envio` → `continue`, sem `registrar`. Na próxima execução `ja_publicado` é `None` e o pedaço 1 é enviado outra vez: dois Shorts iguais no ar, uma linha no ledger.
- Quando acontece: `cortar_para_shorts: true` (config atual); a parte passa de 180 s (as 16 `_corteNN.mp4` da `historia_00003` em `outputs/` mostram que o caminho já rodou de verdade; hoje 0 dos 195 mp4 do memo passa de 180 s, então está dormente) e o Studio cai no 2º pedaço (TargetClosed, queda do Chrome — categoria `recuperacao` conhecida).
- Prova: `python p4_corte_duplo.py <rt>` — dublados `cortes.preparar` (2 pedaços), `publicar_como_configurado` (contador, falha só no 2º pedaço da 1ª rodada), `vistoriar_serie`, `videos_da_serie` e o diário; `serie.publicar` e `catalogo.publicar_youtube` reais. Saída: rodada 1 `enviados = []`, `uploads = [p01#1]`, ledger 0 linhas; rodada 2 `uploads = [p01#1, p01#1, p01#2]`; **o pedaço 1 subiu 2 vezes, ledger com 1 linha**.
- Conserto sugerido: registrar cada pedaço no ato (ou devolver as URLs parciais na exceção) e, na retomada, pular os pedaços já confirmados.

### 4. ffmpeg que estoura o prazo faz o vídeo MUDO passar na vistoria — gravidade: média
- Onde: `historias/contos/publicar/qualidade.py:293-318` (`_audio`) e `:603-609` (`vistoriar_arquivo`).
- O defeito: `_audio` devolve `(None, 0.0)` em `TimeoutExpired`/`OSError`, e `vistoriar_arquivo` só acusa "praticamente mudo" quando `media is not None`. "Não medi" vira "não tem defeito", sem erro nem aviso no laudo.
- Quando acontece: o E: é HDD e já ficou 0 % ocioso (06/10: um mp4 levou 33 min); o decode de 150 s de áudio estourando os 300 s deixa um render mudo seguir para `liberado() -> ok` e para a grade. Vídeo mudo no ar foi incidente real (memória "vídeo mudo barrado").
- Prova: `python p3_qualidade_timeout.py <rt>` — mp4 mudo de verdade (gerado com ffmpeg, `anullsrc`): vistoria real → `['audio a -91.0 dB de media: praticamente mudo', 'os ultimos 12.0s sao mudos...']`. Com `subprocess.run` dublado para levantar `TimeoutExpired` só quando o executável é `ffmpeg` (simula o disco ocupado; `_audio` e `vistoriar_arquivo` reais, memo limpo): `erros = []`, `avisos = []`, `media_db = None`.
- Conserto sugerido: medida de áudio que falhou vira erro ("não consegui medir o áudio") ou ao menos aviso, nunca silêncio.

### 5. ffprobe que estoura o prazo barra vídeo bom com "sem faixa de áudio: vai ao ar mudo" — gravidade: média
- Onde: `historias/contos/publicar/qualidade.py:265-287` (`_ffprobe`), `:584-601` (`vistoriar_arquivo`).
- O defeito: `_ffprobe` devolve `{}` em timeout/erro e `vistoriar_arquivo` lê isso como "0 faixas, 0 s": três erros falsos (`sem faixa de video`, `sem faixa de audio`, `0.0s e curto demais`). Não é o contrário do item 4 por acaso — as duas medidas tratam "não medi" de jeitos opostos.
- Quando acontece: o mesmo disco ocupado (timeout de 60 s no ffprobe). A parte sai do estoque publicável naquela passada, o diário recebe "vistoria hNN pM: 3 erro(s) — sem faixa de video" (`_registrar_vistoria`), o bot apura um defeito que não existe; o reparo responde "nenhum dos motivos tem conserto automatico" (`reparo.py:733`).
- Prova: `python p3_qualidade_timeout.py <rt>` — mp4 bom (tom de 440 Hz), vistoria real `erros = []`; com `TimeoutExpired` só para `ffprobe`: `existe = True`, `erros = ['sem faixa de video', 'sem faixa de audio: o video vai ao ar mudo', '0.0s e curto demais para uma historia']`.
- Conserto sugerido: `_ffprobe` que falhou devolve `None` e a vistoria responde "não consegui medir" (erro próprio, sem afirmar "mudo"), para o reparo e o bot não lerem defeito de arquivo.

### 6. `main.py publicar --comecar 2026-10-20T18:00` agenda 3 h antes do pedido — gravidade: média
- Onde: `historias/contos/publicar/serie.py:120-133` (`horarios`); chamador `historias/main.py:514` (`datetime.fromisoformat(args.comecar)`, sem fuso).
- O defeito: `horarios` faz `inicio.replace(tzinfo=timezone.utc)` quando a data vem sem fuso. O `main.py` entrega hora local sem fuso (a ajuda sugere `2026-09-01T18:00`); o YouTube recebe `publishAt` em UTC, três horas mais cedo (fuso da máquina: -03:00). Os testes existentes (`test_contas_publicacao_regressions.py:195-207`) só passam datas já em UTC, por isso não pegam.
- Quando acontece: qualquer uso manual com `--comecar`; a parte 1 marcada para 18:00 sai às 15:00, e as seguintes a cada 24 h a partir daí.
- Prova: `python p5_diversos.py <rt>` (5a) — `horarios(1, comecar_em=datetime(2026,10,20,18,0))[0] = 2026-10-20T18:00:00Z`, que é **15:00** na hora da máquina.
- Conserto sugerido: `inicio.astimezone(timezone.utc)` para data sem fuso (assume local), ou o `main.py` passar `datetime.fromisoformat(...).astimezone()`.

### 7. `renomear` move a pasta do Chrome ANTES de gravar o registro: gravação que falha deixa a conta apontando para login que não existe — gravidade: média
- Onde: `random_builds/builds/contas.py:249-261` (`renomear`).
- O defeito: `origem.rename(alvo)` acontece primeiro; `_gravar(dados)` depois. Se a gravação falha (registro trancado, só-leitura, disco), a pasta já se chama `<servico>__<novo>` e o registro continua com `<antigo>`; `perfil()` então cria uma pasta nova vazia com o nome antigo e `tem_login` vira `False` — exatamente o estrago que a docstring diz evitar, e o próximo upload pede login no meio da fila. O `movidos` nunca chega a quem chamou.
- Quando acontece: `python -c "contas.renomear(...)"` (`ferramentas/auditoria_contas.py:118`) enquanto o painel/app segura ou regrava o `contas.json`.
- Prova: `python p5_diversos.py <rt>` (5d) — conta `canal2` com `Cookies` na pasta (`tem_login = True`); registro em só-leitura; `renomear` levanta `PermissionError`; depois: registro ainda `['principal', 'canal2']`, `ativa = {'historias': 'canal2'}`, pasta antiga **não existe**, `tiktok__historinhas` existe, `tem_login(historias) = False`.
- Conserto sugerido: gravar o registro primeiro (ou gravar e, se o `rename` falhar, desfazer), e devolver erro claro com o caminho movido.

### 8. `escolher()` aceita nome sem limpar e cria conta/pasta com espaço e acento (o app manda o nome cru) — gravidade: baixa
- Onde: `random_builds/builds/contas.py:329-340` (`escolher`); chamador `remoto/comandos_app.py:485` (`registro.escolher(args["servico"], args["canal"], args["conta"])`).
- O defeito: `adicionar` passa por `_limpar_nome`; `escolher` não — um nome que não está na lista é anexado como veio. O mesmo destino passa a existir com dois nomes (`Canal Histórias` e `canal_historias`), a pasta de perfil vira `tiktok__Canal Histórias`, e a regra "um destino, um nome" (`conformidade`) não enxerga porque os dois não têm identidade.
- Quando acontece: pelo app, qualquer `escolher_conta` com um nome digitado/novo; pelo painel não (`painel/paginas/contas.py:181` limpa antes).
- Prova: `python p5_diversos.py <rt>` (5b) — `escolher("tiktok","historias","Canal Histórias")` → `contas = ['principal', 'Canal Histórias']`, `perfil = tiktok__Canal Histórias`; `adicionar` do mesmo nome devolve `canal_historias` e a lista fica com os dois.
- Conserto sugerido: `escolher` passa o nome por `_limpar_nome` (ou recusa nome que não está na lista).

### 9. `conformidade()` nunca fica vazia: o canal `zombie` é acusado para sempre — gravidade: baixa
- Onde: `random_builds/builds/contas.py:291-299` (`conformidade`, laço `for canal in CANAIS`); leitor `ferramentas/auditoria_contas.py:105-108` ("TUDO DENTRO DO PADRAO" só com lista vazia).
- O defeito: `CANAIS` ganhou `zombie` em 15/09 e a regra 3 cobra conta própria de todo canal que não é `geral`; com builds e histórias perfeitos ainda saem 3 alertas (`youtube`, `tiktok`, `youtube_web`: "zombie cai em principal"). Alerta que nunca apaga é alerta que ninguém lê.
- Prova: `python p5_diversos.py <rt>` (5c) — registro com `neural_fights`/`historinhas` escolhidos e identificados nos três serviços → `conformidade()` devolve os 3 itens do zombie.
- Conserto sugerido: só cobrar conta própria dos canais com produção (ou tirar o zombie de `CANAIS` até ele publicar).

### 10. Memo dos trechos pretos não leva o critério: mudar `PRETO_AREA`/`PRETO_PIXEL` não re-mede nada — gravidade: baixa
- Onde: `historias/contos/publicar/qualidade.py:532` (`erros_de_preto`, chave `real|mtime|size|layout`), `_vistoria_pretos.json`.
- O defeito: ao contrário de `_vistoria_medidas.json` (chave com a versão do comando/fonte), o memo dos pretos só muda de chave quando o mp4 muda. Trecho medido com um limiar continua valendo depois de o limiar mudar (como em 17/09 e 30/09) — em memória e em disco, até o vídeo ser re-renderizado.
- Prova: `python p5_diversos.py <rt>` (5e) — `trechos_pretos` dublado com contador; 1ª chamada mede (1); `PRETO_AREA, PRETO_PIXEL = 0.40, 0.03`; 2ª chamada devolve o mesmo erro e o contador fica em 1.
- Conserto sugerido: pôr `PRETO_AREA/PRETO_PIXEL/PRETO_MIN_S/PRETO_FPS` na chave do memo.

## Não confirmados

- `catalogo.listar` (`:184-202`): um `final_celular.mp4` (sem `_pNN`) numa história de várias partes ganharia `parte=1` e o mesmo id de `final_celular_p01.mp4` (duas entradas com o mesmo id no catálogo). Não há arquivo assim em `outputs/` hoje (só `_corteNN`, que o filtro já tira); teórico.
- `serie.publicar` (`:222-228`): com outra publicação segurando `publicar__<id>__<plataforma>`, cada parte espera 120 s e é pulada — 6 partes = 12 min travado para não publicar nada. Deterministico pelo código, mas é caminho manual (`main.py publicar --serie`) e não há dano, só espera.
- `parecer.ler_veredito` (`:758`): só a primeira linha decide; uma resposta "Veredito: REPROVADO" vira `SemParecer` e cai para a folha do ChatGPT (que pode aprovar como `nao_assistido`). Depende do formato que o Gemini escolhe; não dá para provar sem a IA.
- `parecer._pedir_em` (`:927`): `prompt()` roda fora do `try`; se `plano.cenas_com_tempo`/`cenas_do_roteiro` levantar, a exceção crua passa por `pedir` (que só trata `SemParecer`/`ContaOcupada`) e chega à agenda. `cenas_do_plano` engole `OSError`/`ValueError` e `cenas_do_roteiro` tolera tipos; não achei entrada real que levante.
- `qualidade.vistoriar_parte` (`:831`): `max(a.stat().st_mtime ...)` sem `try` — imagem apagada entre `fila.estado` e o `stat` derruba a vistoria com `FileNotFoundError`. Janela de milissegundos; não reproduzido.
- Reparo depois de parecer aprovado: um re-render (ex. "imagem mais nova que o video") invalida `lembrado` pelo mtime, mas `situacao_do_video`/`ja_olhado` continuam dizendo "aprovado" pelo id e a revisão da madrugada não pergunta de novo — o mp4 novo sai com a aprovação do antigo. É a regra "uma passada só" (decisão `reolhar-depois-do-conserto`), então não conta como defeito; fica registrado porque é o único caminho em que um mp4 que ninguém viu sai como `aprovado`.
