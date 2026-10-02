# -*- coding: utf-8 -*-
"""Seletores do ChatGPT e do Gemini, na doutrina da casa.

Cada alvo e uma LISTA de candidatos, tentados em ordem, e nao um seletor
unico: os dois sites mudam de classe com frequencia e um seletor solto
quebra a automacao inteira sem dizer o que quebrou. Quando quebrar mesmo
assim, o conserto e `python main.py llm probe --provedor chatgpt`, que
despeja o DOM real da tela — nenhum outro arquivo precisa mudar.

O que NUNCA se confia aqui (mesma licao do Digen): "nao deu erro" nao e
prova. O envio so e dado como feito quando o campo esvazia ou o botao de
parar aparece; a resposta so e dada como pronta quando o texto PARA de
crescer.
"""
from __future__ import annotations

PROVEDORES = ("chatgpt", "gemini", "deepseek", "grok")

CHATGPT = {
    "url": "https://chatgpt.com/",
    "url_novo_chat": "https://chatgpt.com/?model=auto",
    "campo": [
        "#prompt-textarea",
        "div[contenteditable='true'][id='prompt-textarea']",
        "div.ProseMirror[contenteditable='true']",
        "textarea[data-id='root']",
        "div[contenteditable='true']",
    ],
    "enviar": [
        "button[data-testid='send-button']",
        "button[aria-label*='Send' i]",
        "button[aria-label*='Enviar' i]",
        "button#composer-submit-button",
    ],
    # SO O BOTAO DE PARAR A RESPOSTA. Ate 17/09/2026 aqui havia
    # `aria-label*='Parar' i` ("contem", sem caixa), e ele casava com o
    # HISTORICO da barra lateral: "Fixar COMPARAR defeitos do formato A"
    # (medido na tela). O parecer ficou 8 min com "APROVADO" pronto e o
    # cliente dizendo "escrevendo". O rotulo tem de COMECAR com a palavra.
    "parar": [
        "button[data-testid='stop-button']",
        "button[aria-label^='Stop' i]",
        "button[aria-label^='Parar' i]",
        "button[aria-label^='Interromper' i]",
    ],
    # A mensagem do USUARIO ja na conversa: prova de que o envio entrou.
    # 02/10/2026 00:0x (conta Plus, scratchpad/diag_estrutura.py): a conversa
    # NAO tem mais `data-message-author-role` nem `section[data-turn]`. O balao
    # do usuario e `div[data-user-message-bubble=true]` (o texto do pedido, sem
    # o "Voce disse:" do h4 escondido).
    "turno_usuario": [
        "div[data-message-author-role='user']",
        "div[data-user-message-bubble='true']",
    ],
    "resposta": [
        "div[data-message-author-role='assistant']",
        "article[data-testid^='conversation-turn'] div.markdown",
        "div.agent-turn div.markdown",
        # o DOM novo (02/10/2026, medido na conversa "Revisao de cenas": o
        # "APROVADO" mora em `div[data-markdown-text-style=assistant-message]`
        # dentro de `div[data-chatgpt-selection-message-id]`). Sem ele a
        # resposta de TEXTO tambem ficaria em "0 chars".
        "div[data-markdown-text-style='assistant-message']",
    ],
    # A IMAGEM DA RESPOSTA (medido na casa em 29/09/2026, 16:1x,
    # scratchpad/diag_chatgpt_imagem.py e diag_chatgpt_baixar.py). O turno e
    # `section[data-turn=assistant]` (data-testid conversation-turn-N); a
    # resposta so de imagem NAO tem `data-message-author-role`. A imagem
    # gerada mora em `div#image-<uuid>` (classe `group/imagegen-image`), em
    # tres <img> com o mesmo src (backend-api/estuary/content, 1254x1254); a
    # final tem alt "Imagem gerada: <titulo>". No MESMO section, embaixo, vem
    # um ANUNCIO ("Anuncio", miniatura 512x512 de images.openai.com/
    # static-rsc) — foi ele que virou "o gato" do d228c94f. Por isso a
    # imagem so vale dentro do recipiente `imagegen-image`.
    #
    # O CARTAO NOVO (02/10/2026 00:0x, conta Plus "zaptod"; o 869758fa ficou
    # 420 s em "0 chars" com a imagem na tela). O turno do assistente e o div
    # que tem, como filho, `h4[data-conversation-role=assistant]` (o "ChatGPT
    # disse:" escondido). A imagem: `[data-testid=generated-image-gallery]` >
    # um item por imagem com `button[data-testid=generated-image-preview]`
    # (aria "Imagem 1 gerada") > <img> com src `blob:`, alt "Imagem 1 gerada",
    # 1254x1254 natural. No MESMO item, embaixo, os botoes "Editar a imagem
    # gerada 1" e "Compartilhar imagem gerada 1". O item so vale COM esses
    # botoes (prova de geracao terminada; sem eles e `imagem_em_geracao`).
    # Os rotulos em ingles sao palpite (a conta e pt-BR), nao medida.
    "imagem_turno": [
        "section[data-turn='assistant']",
        "article[data-turn='assistant']",
        "div:has(> h4[data-conversation-role='assistant'])",
    ],
    "imagem_gerada": [
        "div[id^='image-'][class*='imagegen-image']",
        "[class*='imagegen-image']",
        "[data-testid='generated-image-gallery'] "
        "div:has(> button[data-testid='generated-image-preview'])"
        ":has(button[aria-label^='Compartilhar imagem gerada'],"
        " button[aria-label^='Editar a imagem gerada'],"
        " button[aria-label^='Share generated image'],"
        " button[aria-label^='Edit generated image'])",
    ],
    # o item da galeria SEM os botoes: a imagem ainda nao e a final
    "imagem_em_geracao": [
        "[data-testid='generated-image-gallery'] "
        "div:has(> button[data-testid='generated-image-preview'])"
        ":not(:has(button[aria-label^='Compartilhar imagem gerada'],"
        " button[aria-label^='Editar a imagem gerada'],"
        " button[aria-label^='Share generated image'],"
        " button[aria-label^='Edit generated image']))",
    ],
    "imagem_final_alt": ["Imagem gerada", "Generated image"],
    # o alt do cartao novo tem o numero no meio: "Imagem 1 gerada"
    "imagem_final_alt_re": [r"^imagem \d+ gerada", r"^generated image \d+",
                            r"^image \d+ generated"],
    # O botao de baixar fica num DIALOGO. No cartao antigo ele abria com o
    # clique na imagem (tela cheia); no novo, o caminho que o Adrian mostrou
    # (02/10) e o "Compartilhar imagem gerada N" do proprio item, cujo dialogo
    # tem `button[aria-label=Baixar]` (medido; o visualizador da imagem tambem
    # tem um "Baixar", e o clique na imagem continua sendo a reserva).
    # Medido em 29/09: entrega os MESMOS bytes do src (PNG 1254x1254).
    "imagem_abrir_para_baixar": True,
    "imagem_abrir": [
        "button[aria-label^='Compartilhar imagem gerada']",
        "button[aria-label^='Share generated image']",
    ],
    "imagem_baixar": [
        "[role='dialog'] button[aria-label='Baixar']",
        "[role='dialog'] button[aria-label='Download']",
    ],
    "logado": [
        "#prompt-textarea",
        "div[contenteditable='true'][id='prompt-textarea']",
        "nav[aria-label*='Chat' i]",
    ],
    "login": [
        "button[data-testid='login-button']",
        "a[href*='/auth/login']",
        "button:has-text('Log in')",
        "button:has-text('Entrar')",
    ],
    # Anexo. O `input[type=file]` e SEMPRE oculto nos dois sites, entao ele
    # se resolve por `encontrar_oculto` — `encontrar` filtra por visibilidade
    # e nunca acharia. O botao de "+" so e clicado quando o input nao existe
    # ainda no DOM.
    "anexo_botao": [
        "button[aria-label*='Attach' i]",
        "button[aria-label*='Anexar' i]",
        "button[data-testid='composer-plus-btn']",
        "button[aria-label*='Add photos' i]",
    ],
    "anexo_input": [
        "input[type='file']",
    ],
    "anexo_prova": [
        "button[aria-label*='Remove' i]",
        "button[aria-label*='Remover' i]",
        "div[data-testid*='attachment' i]",
        "img[alt*='Uploaded' i]",
    ],
}

GEMINI = {
    "url": "https://gemini.google.com/app",
    "url_novo_chat": "https://gemini.google.com/app",
    # O MODELO NAO VEM ESCOLHIDO. A URL abre com o que estiver marcado na
    # conta, e em 08/09/2026 estava em "3.6 Flash" — o rapido. As historias 3
    # a 10 inteiras foram escritas por ele; e a primeira coisa a olhar quando
    # o texto parece raso. `modelo_botao` abre o menu, `modelo_opcao` sao as
    # escolhas, e `modelo_preferido` e a ordem em que se procura.
    "modelo_botao": [
        'button[data-test-id="bard-mode-menu-button"]',
        "bard-mode-switcher button",
        'button[aria-label*="modelo" i]',
    ],
    "modelo_opcao": [
        'button[role="menuitemradio"]',
        '[role="menuitem"]',
        "button.mat-mdc-menu-item",
    ],
    # Do mais forte para o mais fraco: escrever historia e trabalho de
    # raciocinio, nao de velocidade.
    "modelo_preferido": ["pro", "flash"],
    "campo": [
        "rich-textarea div.ql-editor[contenteditable='true']",
        "div.ql-editor[contenteditable='true']",
        "div[contenteditable='true'][role='textbox']",
        "textarea[aria-label*='prompt' i]",
    ],
    "enviar": [
        "button.send-button",
        "button[aria-label*='Send' i]",
        "button[aria-label*='Enviar' i]",
        "button[mattooltip*='Enviar' i]",
    ],
    "parar": [
        "button[aria-label^='Stop' i]",
        "button[aria-label^='Parar' i]",
        "button[aria-label^='Interromper' i]",
        "button.stop-icon",
        "mat-icon[fonticon='stop']",
    ],
    # O RACIOCINIO QUE NAO ACABA. Em 14/09/2026 o Pro passou a pensar por
    # mais de 10 minutos ("Developing the Core Twist") sem escrever um
    # caractere, e desde as 3:45 metade dos pedidos estourou 600-900 s com
    # "0 chars" — parecia limite de conta. A tela oferecia este botao, que
    # encerra o raciocinio e manda escrever.
    "responder_agora": [
        "button:has-text('Responder agora')",
        "button:has-text('Answer now')",
        "button[aria-label*='Responder agora' i]",
        "button[aria-label*='Answer now' i]",
        # Na captura ele parece um chip, que pode nao ser <button>.
        "[role='button']:has-text('Responder agora')",
        "text='Responder agora'",
        "text='Answer now'",
    ],
    # A mensagem do USUARIO ja na conversa ("Voce disse"): prova de que o
    # envio entrou. Sem ela e com o prompt de volta na caixa, a pagina voltou
    # ao inicio — com ela, e o Gemini "Analisando" o video (14/09/2026).
    "turno_usuario": [
        "user-query",
        "[data-test-id='user-query']",
        "div.user-query-container",
    ],
    "resposta": [
        "model-response message-content .markdown",
        "message-content.model-response-text",
        "div.model-response-text",
        "model-response",
    ],
    # A IMAGEM DA RESPOSTA (medido na casa em 29/09/2026, 16:2x,
    # scratchpad/diag_gemini_recipiente.py): `model-response > ... >
    # generated-image > single-image.generated-image > ... > img.image`
    # (lh3.googleusercontent.com/gg/...; a tela mostra 1024x559, o original e
    # 2816x1536). O botao "Baixar imagem no tamanho original" fica no mesmo
    # `single-image` (ver `ias/imagem.py`).
    "imagem_turno": [
        "model-response",
    ],
    "imagem_gerada": [
        "generated-image",
        "single-image.generated-image",
    ],
    "imagem_baixar": [
        "button[aria-label='Baixar imagem no tamanho original']",
        "button[aria-label='Download full size image']",
    ],
    "logado": [
        "rich-textarea div.ql-editor[contenteditable='true']",
        "div.ql-editor[contenteditable='true']",
    ],
    "login": [
        "a[href*='accounts.google.com']",
        "a[aria-label*='Sign in' i]",
        "a:has-text('Fazer login')",
    ],
    "anexo_botao": [
        # O rotulo ATUAL, medido em 11/09/2026 sondando a pagina: o botao de
        # `+` do compositor chama-se "Envio e ferramentas". Nenhum dos quatro
        # abaixo casava mais, e por isso `anexar` dizia "nao achei onde
        # anexar" — o input de arquivo so existe no DOM depois deste clique.
        "button[aria-label='Envio e ferramentas']",
        "button[aria-label*='Envio e ferramentas' i]",
        "button[aria-label*='Open upload file menu' i]",
        "button[aria-label*='Adicionar arquivos' i]",
        "button[aria-label*='Add files' i]",
        "button[aria-label*='Anexar' i]",
    ],
    "anexo_input": [
        "input[type='file']",
    ],
    # O Gemini pede consentimento de DIREITOS a cada video enviado, num
    # dialogo MODAL. Enquanto ele esta aberto o botao de enviar existe,
    # aparece habilitado e o clique nao faz nada — foi o que fez tres
    # tentativas seguidas morrerem em "cliquei em enviar mas nada mudou".
    # O `data-test-id` e o seletor certo: nao depende do idioma.
    "consentimento_video": [
        "[data-test-id='video-upload-consent-dialog-agree-button'] button",
        "button[aria-label='Concordo']",
        "button[aria-label='I agree']",
    ],
    # A prova de que o VIDEO subiu inteiro nao e a miniatura: e a duracao
    # aparecer ao lado do nome do arquivo. A miniatura sai em 10 s, a
    # duracao em ~30 s, e antes dela o modelo responde sobre um video que
    # ainda nao recebeu.
    "anexo_duracao": [
        "span.gds-emphasized-body-s",
    ],
    "anexo_prova": [
        "button[aria-label*='Remove' i]",
        "button[aria-label*='Remover' i]",
        "uploader-file-preview",
        "div.file-preview",
    ],
}

# O DEEPSEEK (16/09/2026): ESCREVE os roteiros; Gemini e ChatGPT analisam.
# Seletores passados pelo Adrian em 17/09/2026, copiados da tela logada
# (caixa, botao de enviar e uma resposta inteira com o raciocinio aberto).
# As classes curtas (`_27c9245`, `_52c986b`) sao geradas no build do site e
# mudam sem aviso: nenhum seletor aqui depende delas.
DEEPSEEK = {
    "url": "https://chat.deepseek.com/",
    "url_novo_chat": "https://chat.deepseek.com/",
    # Sem menu de modelo no site. O raciocinio ("Pensou por N segundos") vem
    # LIGADO na conta, em ingles, e fica num bloco proprio que nunca e lido.
    "modelo_fixo": "DeepSeek (site)",
    "deepthink_botao": [
        "div[role='button']:has-text('DeepThink')",
        "div[role='button']:has-text('Pensamento profundo')",
        "button:has-text('DeepThink')",
    ],
    "campo": [
        "textarea[placeholder='Mensagem para DeepSeek']",
        "textarea[placeholder*='DeepSeek' i]",
        "textarea[name='search']",
    ],
    # O botao de enviar e um DIV com role=button, primario e redondo, com a
    # seta. Enquanto o modelo escreve, o mesmo lugar vira o botao de parar;
    # por isso a prova de envio tambem aceita o campo esvaziar.
    "enviar": [
        "div[role='button'].ds-button--primary.ds-button--circle",
        "div[role='button'].ds-button--primary.ds-button--filled:has(svg)",
    ],
    "parar": [
        "div[role='button'].ds-button--primary.ds-button--circle:has(svg rect)",
        "div[role='button'][aria-label^='Stop' i]",
        "div[role='button'][aria-label^='Parar' i]",
        "div[role='button'][aria-label^='Interromper' i]",
    ],
    # Mensagem sem resposta final E sem raciocinio: a do assistente que
    # ainda esta pensando tem o bloco `ds-think-content` e nao conta.
    "turno_usuario": [
        "div.ds-message:not(:has(.ds-assistant-message-main-content))"
        ":not(:has(.ds-think-content))",
    ],
    # A RESPOSTA FINAL tem classe propria. O raciocinio usa o mesmo
    # `ds-markdown`, dentro de `ds-think-content` — por isso as duas listas.
    "resposta": [
        "div.ds-message div.ds-markdown.ds-assistant-message-main-content",
        "div.ds-markdown.ds-assistant-message-main-content",
        "div.ds-message div.ds-markdown",
    ],
    "raciocinio": [
        "div.ds-think-content",
    ],
    "logado": [
        "textarea[placeholder='Mensagem para DeepSeek']",
        "textarea[placeholder*='DeepSeek' i]",
    ],
    # A tela de entrar (vista em 17/09/2026): campos de senha e os botoes
    # "Entrar", "Entrar com Google", "Entrar com Apple".
    "login": [
        "input[type='password']",
        "div[role='button']:has-text('Entrar com Google')",
        "div.ds-button:has-text('Entrar com Google')",
    ],
    # ANEXO (medido em 29/09/2026: sessao guiada das 02:21 e de novo as
    # 14:32 no perfil, sem enviar; capturas em
    # `random_builds/outputs/_ias/deepseek/anexo/`). O clipe a esquerda do
    # enviar e so a porta do `input[type=file]`, que ja esta no DOM (multiple;
    # accept de imagens, PDF, texto/codigo e Office) — por isso nao ha
    # `anexo_botao`. Imagem vira MINIATURA: `div[role=button]` com
    # `<img src="blob:..." alt="<nome do arquivo>">`; arquivo que nao e imagem
    # vira CHIP com o nome e "TXT 59B". Nenhum dos dois tem aria-label, e as
    # classes sao hashes do build. As duas formas ficam NUM seletor so (lista
    # com virgula): `_provas_de_anexo` pega o maior numero entre os
    # seletores, e em seletores separados um PNG + um TXT contariam 1.
    "anexo_botao": [],
    "anexo_input": [
        "input[type='file']",
    ],
    "anexo_prova": [
        "div[role='button']:has(img[src^='blob:']), "
        "div:text-matches('^[A-Za-z0-9]{1,5} [0-9.,]+ ?[KMG]?B$')",
        "div[role='button']:has(img[src^='blob:'])",
    ],
    # A MINIATURA NAO PROVA QUE SUBIU: ela aparece em 0,07 s, e um PNG de
    # 3,2 MB so terminou de subir em 2,8 s — ate la o spinner gira dentro
    # dela e o botao de enviar fica `ds-button--disabled` (com anexo pronto
    # ele volta, mesmo com a caixa vazia). `cliente.anexar` espera este
    # seletor sumir antes de devolver.
    "anexo_subindo": [
        "div[role='button'].ds-button--primary.ds-button--circle"
        ".ds-button--disabled",
    ],
    # A resposta vem em markdown carregado e pode trazer rotulo de
    # raciocinio: `llm/texto.limpar_resposta` passa antes do parser.
    "limpar_resposta": True,
}

# O GROK (29/09/2026): pedido do Adrian para a Vila das IAs (plano
# `vila-das-ias.md`, fase 1). O LOGIN E DELE (conta pessoal do X, nao
# compartilhada; no `ias-grok-acesso` do Grimorio decide por onde) — o perfil
# de Chrome e `grok__principal` e ninguem loga por ele.
#
# MEDIDO NA SESSAO GUIADA DE 29/09/2026 (01:44-02:00, `outputs/_ias/grok/`):
# deslogado, o campo e um <textarea aria-label="Pergunte ao Grok qualquer
# coisa">; LOGADO, e um <div contenteditable role="textbox" class="tiptap
# ProseMirror" aria-label="Ask Grok anything"> (o idioma do aria muda com a
# conta). Enviar = button[data-testid='chat-submit'] (aria "Enviar"); anexo
# = button[data-testid='attach-button'] (aria "Anexar") com
# input[type=file][name='files'] multiple e accept vazio; o modelo e o botao
# aria "Seleção de modelo" (texto "Fast") e o menu tem [role=menuitemradio]
# Fast / Build / Auto / Expert / Heavy — Auto/Expert/Heavy abrem
# `#subscribe` (SuperGrok) na conta gratis, entao NAO ha `modelo_preferido`:
# o cliente fica no que a conta tiver. Resposta/turno e "parar" ainda por
# confirmar na sessao guiada.
GROK = {
    "url": "https://grok.com/",
    "url_novo_chat": "https://grok.com/",
    "modelo_botao": [
        "button[aria-label='Seleção de modelo']",
        "button[aria-label*='modelo' i]",
        "button[aria-label*='model' i]",
    ],
    "modelo_opcao": [
        "[role='menuitemradio']",
        "[role='menuitem']",
    ],
    "campo": [
        "div[data-testid='chat-input'] div[role='textbox']",
        "div[role='textbox'][aria-label*='Ask Grok' i]",
        "div[role='textbox'][aria-label*='Pergunte' i]",
        "div.ProseMirror[contenteditable='true'][role='textbox']",
        "div[contenteditable='true'][role='textbox']",
        "textarea[aria-label*='Pergunte ao Grok' i]",
        "textarea[aria-label*='Ask Grok' i]",
    ],
    "enviar": [
        "button[data-testid='chat-submit']",
        "button[aria-label='Enviar']",
        "button[aria-label='Submit']",
        "button[aria-label*='Send' i]",
    ],
    "parar": [
        "button[aria-label^='Stop' i]",
        "button[aria-label^='Parar' i]",
        "button[aria-label^='Interromper' i]",
    ],
    # A resposta e <div role="article" aria-label="Grok"
    # data-testid="assistant-message" class="message-bubble ..."> com o
    # raciocinio num `div.thinking-container` ("Trabalhou por 9s") ANTES do
    # texto (`div.response-content-markdown`). O balao do usuario nao tem
    # testid medido: e o `message-bubble` que NAO e assistant-message.
    "turno_usuario": [
        "[data-testid='user-message']",
        "div.message-bubble:not([data-testid='assistant-message'])",
    ],
    "resposta": [
        "div[data-testid='assistant-message'] div.response-content-markdown",
        "div[data-testid='assistant-message']",
        "div.response-content-markdown",
    ],
    "raciocinio": [
        "div.thinking-container",
    ],
    # O AVISO DO SITE NO LUGAR DA RESPOSTA (29/09/2026, 17:30 e 17:44; ver
    # `cliente.SiteIndisponivel`): o card "Alta procura — Por favor, tente
    # novamente em breve, ou atualize para um acesso com maior prioridade"
    # (botao "Aprimorar", que nunca se clica) no turno do assistente, e o
    # toast "Grok is experiencing issues. We are working on restoring service
    # as quickly as possible." no topo. Os padroes casam no texto do turno que
    # SOBRA fora da resposta e do raciocinio, com borda de palavra dos dois
    # lados. `indisponivel_pagina` e regex de JS, procurada na pagina inteira:
    # so vai ao log.
    "turno_assistente": [
        "div[data-testid='assistant-message']",
    ],
    "indisponivel": [
        r"(?<!\w)alta\s+procura(?!\w)",
        r"(?<!\w)atualize\s+para\s+um\s+acesso\s+com\s+maior\s+prioridade(?!\w)",
        r"(?<!\w)grok\s+is\s+experiencing\s+issues(?!\w)",
    ],
    "indisponivel_pagina": r"\bexperiencing issues\b",
    # A IMAGEM DA RESPOSTA (medido em 29/09/2026 17:5x, so leitura, na
    # conversa "Circulo de cor vermelha" da conta, onde a sonda de 01:44
    # pediu uma imagem; scratchpad/diag_grok2.py). A imagem gerada mora em
    # `div[data-testid=assistant-message] ... div.streamdown-chat-md ...
    # div[data-testid=Vyie8] > div.relative.group/image >
    # div.rounded-2xl`, em dois <img> com o MESMO src
    # `https://assets.grok.com/users/<id da conta>/generated/<uuid>/image.jpg`
    # (um de fundo, sem alt; o da frente com alt "Imagem gerada"). O ANEXO do
    # usuario tambem e assets.grok.com, mas `/users/<id>/<uuid>/preview-image`
    # (sem `/generated/`), dentro de `button[aria-label='Abrir anexo']`; a
    # foto do perfil ("pfp", 300x300) fica na barra lateral.
    #
    # O BALAO INTEIRO NAO BASTA: resposta de chat do Grok pode trazer imagem
    # da WEB (busca, link com previa) — `src` novo, grande, dentro do nosso
    # turno, e de terceiro. Por isso o recipiente e o `group/image` que TEM
    # uma imagem `/generated/` da conta, e o `alt` final e exigido. A classe
    # `Vyie8` e hash do build: nenhum seletor depende dela.
    "imagem_turno": [
        "div[data-testid='assistant-message']",
    ],
    "imagem_gerada": [
        "div[class*='group/image']:has(img[src*='assets.grok.com/users/'][src*='/generated/'])",
    ],
    "imagem_final_alt": ["Imagem gerada", "Generated image"],
    "limpar_resposta": True,
    # LOGADO e o editor ProseMirror (o textarea aparece so deslogado — por
    # isso ele NAO entra aqui: a sonda de 01:44 deu "logado" para a pagina
    # anonima por causa dele).
    "logado": [
        "div[role='textbox'][aria-label*='Ask Grok' i]",
        "div[role='textbox'][aria-label*='Pergunte' i]",
        "div.ProseMirror[contenteditable='true'][role='textbox']",
    ],
    "login": [
        "a[href*='/sign-in']",
        "a[href*='accounts.x.ai']",
        "a:has-text('Entrar')",
        "a:has-text('Sign in')",
    ],
    "anexo_botao": [
        "button[data-testid='attach-button']",
        "button[aria-label='Anexar']",
        "button[aria-label*='Attach' i]",
    ],
    "anexo_input": [
        "input[type='file'][name='files']",
        "input[type='file']",
    ],
    "anexo_prova": [
        "button[aria-label='Remove image']",
        "button[aria-label*='Remove' i]",
        "button[aria-label*='Remover' i]",
    ],
}

MAPA = {"chatgpt": CHATGPT, "gemini": GEMINI, "deepseek": DEEPSEEK,
        "grok": GROK}


def do_provedor(provedor: str) -> dict:
    chave = str(provedor or "").strip().lower()
    if chave not in MAPA:
        raise ValueError(
            f"provedor de LLM desconhecido: {provedor!r}. "
            f"Use um de: {', '.join(PROVEDORES)}")
    return MAPA[chave]


def encontrar(page, candidatos, timeout: float = 3.0):
    """O primeiro candidato VISIVEL, ou None.

    Varre em vez de olhar so o `.first` porque os dois sites renderizam a
    versao mobile escondida antes da desktop — pegar a primeira do DOM
    devolveria um elemento invisivel, e o clique estouraria em timeout.
    """
    import time
    fim = time.monotonic() + float(timeout)
    while True:
        for seletor in candidatos:
            try:
                alvos = page.locator(seletor)
                total = min(alvos.count(), 8)
            except Exception:
                continue
            for i in range(total):
                alvo = alvos.nth(i)
                try:
                    if alvo.is_visible():
                        return alvo
                except Exception:
                    continue
        if time.monotonic() >= fim:
            return None
        time.sleep(0.25)


def encontrar_oculto(page, candidatos, timeout: float = 3.0):
    """O primeiro candidato PRESENTE no DOM, visivel ou nao.

    Existe por causa do anexo: o `input[type=file]` dos dois sites e sempre
    oculto (quem aparece e o botao de clipe), e `encontrar` — que filtra por
    visibilidade de proposito — nunca o acharia. `set_input_files` funciona
    em input oculto, entao presente basta.
    """
    import time
    fim = time.monotonic() + float(timeout)
    while True:
        for seletor in candidatos:
            try:
                alvos = page.locator(seletor)
                if alvos.count():
                    return alvos.first
            except Exception:
                continue
        if time.monotonic() >= fim:
            return None
        time.sleep(0.25)


def resolver(page, candidatos, descricao: str, timeout: float = 15.0):
    alvo = encontrar(page, candidatos, timeout)
    if alvo is None:
        raise SeletorNaoEncontrado(
            f"nao achei {descricao}.\nCandidatos tentados: {candidatos}\n"
            "O site provavelmente mudou. Rode: python main.py llm probe "
            "--provedor <chatgpt|gemini|deepseek|grok> e ajuste "
            "contos/llm/seletores.py.")
    return alvo


class SeletorNaoEncontrado(RuntimeError):
    """O site mudou: diz o que se procurava e como consertar."""
