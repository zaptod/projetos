# A ficha de capacidades de uma IA (`ias/fichas/<ia>.json`)

Vila das IAs, fase 1 (plano `vila-das-ias.md`, 29/09/2026). Uma ficha por IA,
**medida, não suposta**: cada campo que ninguém mediu fica `null` e a tabela
imprime "—". A ficha vazia (`ias.ficha.vazia(ia)`) é válida — o caso ZERO.

Comandos: `python -m ias sondar <ia>|todas [--sem-gastar]` (refaz a sonda
automática), `python -m ias guia <ia>` (sessão guiada: o navegador fica
visível, o Adrian mostra, a sessão grava), `python -m ias fichas` (tabela),
`python -m ias tabela-png <saida>`, `python -m ias eventos <ia>` (os cliques
gravados na sessão guiada). As provas (capturas + texto lido da página +
DOM) ficam em `random_builds/outputs/_ias/<ia>/` (fora do git).

## Schema (versão 1)

| chave | tipo | o que é |
|---|---|---|
| `versao` | int | 1 |
| `ia` | str | `gemini`, `chatgpt`, `deepseek`, `grok`, `picasso`, `dreamface`, `digen` |
| `rotulo`, `tipo` | str | nome de tela; `chat`, `imagem` ou `video` |
| `site`, `perfil`, `trava` | str | URL do chat/criador, pasta de Chrome (`contas.perfil`), nome da trava (`travas.do_perfil`) |
| `medido_em`, `duracao_s` | str/num | quando e quanto a sonda levou |
| `login` | bloco | `estado` ∈ `logado / deslogado / nao_sei / sem_perfil / conta_ocupada / nao_medido` (os três estados da memória *login-do-llm-tres-estados*: `nao_sei` nunca vira `deslogado`); `detalhe`; `prova` (captura) |
| `texto` | bloco | `gera` (bool), `tempo_ok_s` (segundos até "OK"), `resposta`, `limite_chars_campo` (o `maxlength`, se houver), `chars_aceitos_no_campo` (quantos chars o campo aceitou colados, sem enviar), `prova` |
| `modelos` | bloco | `ativo`, `disponiveis` (lista lida do menu), `seletor` (o botão do menu), `prova` |
| `anexos` | bloco | `imagem` / `video` / `arquivo` (bool ou null), `accept` e `multiplos` do `input[type=file]`, `leu_o_anexo` (o modelo disse a cor do círculo?), `seletor`, `prova` |
| `imagem` | bloco | `gera`, `resolucao` `[w, h]`, `alfa` (canal alfa com transparência de verdade), `arquivo`, `tempo_s`, `prova_origem` (dict: o card do histórico no PicassoIA; o nosso turno/prompt nos chats), `prova` |
| `video` | bloco | `assiste` (recebe mp4 e julga), `gera`, `fonte` (`logs`, `docs`, `sonda`) |
| `catalogo_textos` | lista | ver abaixo |
| `cota` | bloco | `o_que_o_site_diz` (linhas curtas da tela que falam de plano/limite), `plano`, `creditos`, `prova` |
| `custo` | bloco | `gratis` e `pede_plano` — só o que foi VISTO |
| `casa` | bloco | para o chat "casa" de longa duração (decisão `ias-chat-persistente`, 29/09): `chat_longo` (aguenta?), `limite_mensagens_por_conversa`, `renomear`, `fixar`, `memoria_entre_chats`, `projetos`, `fonte`, `nota` |
| `pendencias` | lista | o que não foi medido e por quê |
| `capturas` | lista | caminhos das provas |

Convenção nos booleanos: `true` medido sim, `false` medido não, `null` não
medido.

## O catálogo de textos (`catalogo_textos[]`)

O pedaço mais valioso: o que o site põe na tela **no lugar** da resposta.

```json
{"categoria": "limite", "texto": "Você atingiu o limite de uso…",
 "seletor": "model-response message-content .markdown",
 "fonte": "sonda|logs|codigo|docs|adrian", "visto_em": "2026-09-29T01:44:00",
 "nota": "…"}
```

Categorias (`ias.ficha.CATEGORIAS`): `recusa_enlatada` (a frase fixa do
Gemini, `contos/llm/texto.RECUSA_ENLATADA`), `limite` (cota/mensagens/créditos),
`upgrade` (pede plano), `parede` (diálogo que cobre a página e engole o
clique — PicassoIA e Digen), `cloudflare` (desafio anti-bot: NÃO é deslogado),
`indisponivel` (modelo/serviço fora), `erro_site` ("Algo deu errado (1155)",
"Generation failed"), `consentimento` (direitos sobre o vídeo, Gemini),
`conteudo` (filtro de conteúdo), `login`, `outro`.

`ias.catalogo.classificar(texto)` é a função pura que decide a categoria
(linhas de 6 a 300 caracteres; um parágrafo que cita "language model" é
resposta, não recusa). `varrer(texto_visivel)` aplica isso a uma tela inteira.
`CONHECIDOS[ia]` é o que o código e os logs já sabiam antes da sonda, com o
seletor de onde cada texto aparece.

## A sessão guiada (`python -m ias guia <ia>`)

Ordem do Adrian (29/09, 01:35): ele mostra na tela, a sessão grava. Uma IA por
vez, janela visível e maximizada; aviso no Telegram e relato no orquestrador;
captura da **janela** (PrintWindow, nunca da tela) e da página a cada 2 s
(só quando muda), DOM do elemento clicado/focado com seletores por
papel/aria/texto, e a URL — em `random_builds/outputs/_ias/<ia>/guia/`.

Contrato por arquivos com a janela flutuante do painel:

- `random_builds/outputs/_ias/_atual.json` — escrito pela sessão:
  `{"ia", "passo", "desde"}` a cada passo (`ias.guia.PASSOS`).
- `<ia>/guia/colado.jsonl` — escrito pela janela (append): `em`, `papel` ∈
  {campo_texto, enviar, resposta, seletor_modelo, anexo, gerar_imagem,
  erro_cota, observacao, proximo, mensagem}, `tipo` ∈ {html, seletor, texto},
  `conteudo`, `previa`, `seletor_sugerido`. `proximo` avança o passo;
  `erro_cota` vai direto ao catálogo (fonte `adrian`). O seletor que ele colou
  vale mais do que o deduzido.
- `<ia>/guia/comando.json` — escrito pela sessão de agente, lido pela sessão
  guiada: `{"acao": "testar_ok"}` (digita "PEDIDO DE TEXTO: responda só OK"
  com os seletores de `seletores.py` e lê a resposta, na MESMA janela),
  `{"acao": "avisar", "texto": …}`, `{"acao": "js", "codigo": …}` (resultado
  em `js_resultado.json`), `{"acao": "fechar"}` (avisa antes de fechar).
