# Auditoria profunda — Identity (arte dos lutadores por IA) — 11/10/2026

## Examinado

- `__init__.py` — 0 funcoes/classes lidas; declara o pacote Identity.
- `artefato.py` — 7 funcoes/classes lidas; localiza, valida, compara e quarentena os artefatos.
- `auditoria.py` — 6 funcoes/classes lidas; lista, aprova e quarentena provas de origem.
- `browser.py` — 21 funcoes/classes lidas; abre, protege e recupera contextos persistentes do Chrome.
- `client.py` — 43 funcoes/classes lidas; controla Digen, espera, prova e baixa video.
- `config.py` — 11 funcoes/classes lidas; resolve configuracao, perfis, credenciais e caminhos.
- `controle.py` — 13 funcoes/classes lidas; persiste pausa, retomada e parada do worker.
- `dreamface_selectors.py` — 1 funcao/classe lida; declara os seletores e resultados do DreamFace.
- `health.py` — 10 funcoes/classes lidas; faz os diagnosticos local e online da integracao.
- `history.py` — 7 funcoes/classes lidas; registra e resume o historico JSONL da fila.
- `identity_model.py` — 2 funcoes/classes lidas; extrai e grava identidades persistentes da build.
- `moderacao.py` — 6 funcoes/classes lidas; detecta e suaviza prompts recusados.
- `picasso_client.py` — 36 funcoes/classes lidas; controla Picasso, historico, prova e download de imagens.
- `picasso_selectors.py` — 8 funcoes/classes lidas; declara e consulta seletores do Picasso.
- `probe.py` — 3 funcoes/classes lidas; despeja DOM e confere seletores de manutencao.
- `prompt.py` — 19 funcoes/classes lidas; valida dados e monta os prompts por slot.
- `provedores.py` — 4 funcoes/classes lidas; registra provedores, clientes e seletores.
- `proveniencia.py` — 20 funcoes/classes lidas; decide e registra a prova de origem.
- `queue.py` — 36 funcoes/classes lidas; serializa, reivindica e recupera jobs em disco.
- `referencias.py` — 15 funcoes/classes lidas; prepara, compoe e anexa imagens de referencia.
- `selectors.py` — 22 funcoes/classes lidas; declara e resolve seletores do Digen.
- `session.py` — 6 funcoes/classes lidas; abre sessao e faz login assistido.
- `slots.py` — 8 funcoes/classes lidas; define slots, dependencias e nomes de artefatos.
- `status.py` — 11 funcoes/classes lidas; inventaria clipes, plano de edicao e fila.
- `worker.py` — 41 funcoes/classes lidas; drena provedores, correio, provas e re-render.

## Confirmados (do mais grave ao menos)

### 1. O correio inicia pedido depois do prazo da rodada — gravidade: media

- Onde: `worker.py:720-735` (`processar_correio`); o job ja foi reivindicado em `worker.py:1216`, mas nao ha nova verificacao do prazo antes de pedir a imagem.

- O defeito: `prazo` so limita a espera pela conta; nao impede `correio.pedir_imagem(...)` nem `Carteiro.entregar(...)` quando a hora ja venceu. O minimo de 60 s em `max(60.0, prazo - time.time())` tambem permite atravessar um prazo que esta a menos de um minuto.

- Quando acontece: a passada reivindica um job antes do limite e fica aguardando a conta, ou o limite vira enquanto prepara o job; ao obter a conta depois do limite, o worker ainda cria uma imagem. Isto viola a janela da rodada e pode gastar cota/rodar trabalho pesado fora do horario autorizado.

- Prova: executei, sem rede nem estado do projeto, `python -c "... worker.processar_correio(..., prazo=time.time()-1) ..."`, com correio e carteiro de memoria apenas para observar a chamada externa. A funcao real imprimiu `PEDIDO_CRIADO_APOS_PRAZO True`, depois `[identity] x: pedido pedido-teste ao gemini (0 anexo(s))` e `FLUXO_CONTINUOU_APOS_PEDIDO`.

- Conserto sugerido: conferir `_prazo_vencido(prazo)` imediatamente antes de `pedir_imagem` (e apos obter a conta) e devolver o job por `CorreioOcupado`/`reagendar`, sem criar pedido.

## Não confirmados

- `controle.py:_ler/_gravar` reescreve `controle.json` sem lock e sem escrita atomica; duas operacoes simultaneas podem perder uma pausa ou uma parada. A suspeita e concreta pela sequencia read-modify-write, mas nao a reportei como confirmada porque o caminho de locks do runtime real e protegido nesta worktree e nao reproduzi a corrida entre processos sem mexer no estado externo.
- `proveniencia.py:comprovar/reivindicar` consulta `origens.jsonl` e so registra a URL apos o download, sem uma reserva atomica. Seria uma janela para dois workers aceitarem a mesma URL, mas o worker da Identity tem trava de instancia e nao encontrei chamador concorrente que a contorne; sem reproducao nao e confirmado.
- `artefato.py:presta` e `status.py:inventario` fazem `is_file()` seguido de `stat()` sem tratar a mudanca do arquivo entre as duas chamadas. Isso pode levantar em corrida com quarentena/remocao, mas nao consegui provocar a janela de forma confiavel com operacoes reais de arquivo no ambiente restrito.
