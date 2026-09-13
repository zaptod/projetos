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

PROVEDORES = ("chatgpt", "gemini")

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
    "parar": [
        "button[data-testid='stop-button']",
        "button[aria-label*='Stop' i]",
        "button[aria-label*='Parar' i]",
    ],
    "resposta": [
        "div[data-message-author-role='assistant']",
        "article[data-testid^='conversation-turn'] div.markdown",
        "div.agent-turn div.markdown",
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
        "button[aria-label*='Stop' i]",
        "button[aria-label*='Parar' i]",
        "button.stop-icon",
        "mat-icon[fonticon='stop']",
    ],
    "resposta": [
        "model-response message-content .markdown",
        "message-content.model-response-text",
        "div.model-response-text",
        "model-response",
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

MAPA = {"chatgpt": CHATGPT, "gemini": GEMINI}


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
            "--provedor <chatgpt|gemini> e ajuste src/llm/seletores.py.")
    return alvo


class SeletorNaoEncontrado(RuntimeError):
    """O site mudou: diz o que se procurava e como consertar."""
