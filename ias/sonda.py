# -*- coding: utf-8 -*-
"""A sonda: abre cada IA no perfil dela e MEDE a ficha, com prova.

Regras que valem aqui (plano `vila-das-ias.md`, fase 1):

  TRAVA DA CONTA   a rodada das historias usa Gemini/ChatGPT/DeepSeek/
                   PicassoIA de madrugada. A sonda pede a trava do perfil e,
                   ocupada, a ficha diz `conta_ocupada` e segue para a
                   proxima IA. Nunca forca, nunca mata nada.
  MINIMO DE COTA   tres mensagens por chat (OK, o anexo, uma imagem) e UMA
                   imagem por gerador. Nada e repetido "para conferir".
  PROVA            captura da janela (`page.screenshot`) e o TEXTO lido da
                   pagina, em `random_builds/outputs/_ias/<ia>/` (fora do
                   git). Campo sem prova fica `None`, nao vira chute.
  RITMO HUMANO     `_pausa` entre acoes, como em `contos.llm.cliente`.
  UM NAVEGADOR     uma IA por vez; o PC nao aguenta mais que dois Chrome.

Os clientes sao os que ja existem: `contos.llm.cliente.ClienteLLM` para os
chats e os seletores/clientes de `builds.identity` para PicassoIA, DreamFace
e Digen. Este modulo nao inventa seletor: quando um nao casa, ele despeja o
DOM real (`dom_*.json`) e anota a pendencia.
"""
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

from . import IAS, catalogo, ficha as fichas

RAIZ_REPO = Path(__file__).resolve().parents[1]
PASTA_PROVAS = RAIZ_REPO / "random_builds" / "outputs" / "_ias"
PNG_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "circulo_vermelho.png"

# Quanto esperar a conta ficar livre. Curto de proposito: a geracao segura a
# conta por horas, e contra isso o que funciona e voltar depois.
ESPERA_CONTA_S = 30.0
# Prazo de UMA resposta curta. "OK" vem em segundos; imagem em ate ~2 min.
PRAZO_TEXTO_S = 240.0
PRAZO_IMAGEM_S = 300.0
# Quantos caracteres se cola no campo para medir o que ele aceita (sem
# enviar). 120 mil ja passa do que qualquer prompt nosso tem.
CHARS_DE_PROVA = 120_000

PEDIDO_OK = "PEDIDO DE TEXTO: responda só OK"
PEDIDO_ANEXO = ("PEDIDO DE TEXTO: o anexo é um círculo de que cor? "
                "Responda com uma palavra.")
PEDIDO_IMAGEM = ("Gere uma imagem quadrada (proporção 1:1): a red circle on a "
                 "white background, flat, minimal, no text.")
PROMPT_GERADOR = "a red circle on a white background, flat, minimal, no text"

CHATS = ("gemini", "chatgpt", "deepseek", "grok")
GERADORES = ("picasso", "dreamface", "digen")
# Quem pode desenhar dentro do chat. O DeepSeek nao oferece (site sem
# ferramenta de imagem): perguntar gastaria cota para ouvir "nao".
CHATS_QUE_DESENHAM = ("gemini", "chatgpt", "grok")

# Seletores de MODELO dos chats que `contos.llm.seletores` nao precisa ter
# (o cliente nao troca o modelo do ChatGPT). Ficam aqui, na sonda: ler o
# menu e fechar com ESC nao muda nada na conta.
SELETORES_DE_MODELO = {
    "chatgpt": {
        "botao": ["button[data-testid='model-switcher-dropdown-button']",
                  "button[aria-label*='Model selector' i]",
                  "button[aria-label*='Seletor de modelo' i]",
                  "button[aria-haspopup='menu']:has-text('ChatGPT')"],
        "opcao": ["[role='menuitem']", "[role='menuitemradio']", "[role='option']"],
    },
}
# O botao de "Ferramentas"/"+" do ChatGPT lista o que a conta pode fazer
# (Criar imagem, Pesquisa aprofundada...). Le-se e fecha-se com ESC.
FERRAMENTAS_CHATGPT = ["button[data-testid='composer-plus-btn']",
                       "button[aria-label*='Adicionar arquivos' i]",
                       "button[aria-label*='Add files' i]"]

PLANO = re.compile(
    r"\b(?:free|gr[aá]tis|gratuito|plus|pro\+?|advanced|premium\+?|supergrok"
    r"|ultramax|ai\s+pro|ai\s+ultra|team|business)\b", re.IGNORECASE)


def _log_padrao(msg: str) -> None:
    print(msg, flush=True)


def _pausa(rng: random.Random, minimo: float = 0.6, maximo: float = 1.6) -> None:
    time.sleep(rng.uniform(minimo, maximo))


def pasta_de(ia: str) -> Path:
    pasta = PASTA_PROVAS / str(ia).lower()
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _carimbo() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _texto_visivel(page) -> str:
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''") or ""
    except Exception:                                          # noqa: BLE001
        return ""


def _captura(page, pasta: Path, nome: str, ficha: dict, log) -> str | None:
    """Captura + texto lido, lado a lado. Devolve o caminho da imagem."""
    try:
        alvo = pasta / f"{_carimbo()}_{nome}.png"
        page.screenshot(path=str(alvo))
        alvo.with_suffix(".txt").write_text(_texto_visivel(page)[:20000],
                                            encoding="utf-8")
        ficha["capturas"].append(str(alvo))
        return str(alvo)
    except Exception as exc:                                   # noqa: BLE001
        log(f"[sonda] nao consegui capturar {nome}: {type(exc).__name__}")
        return None


def _despejar_dom(page, pasta: Path, nome: str) -> str | None:
    """Um retrato do DOM (botoes, campos, inputs) para consertar seletor."""
    try:
        dados = {
            "url": page.url, "titulo": page.title(),
            "quando": fichas.agora(),
            "contenteditable": page.eval_on_selector_all(
                "[contenteditable='true'], textarea",
                "els => els.slice(0,8).map(e => ({tag: e.tagName, id: e.id, "
                "cls: String(e.className||'').slice(0,80), aria: e.getAttribute('aria-label'), "
                "ph: e.getAttribute('placeholder') || e.getAttribute('data-placeholder'), "
                "maxlength: e.getAttribute('maxlength')}))"),
            "botoes": page.eval_on_selector_all(
                "button, [role='button'], a[href]",
                "els => els.slice(0,80).map(e => ({t: (e.innerText||'').trim().slice(0,40), "
                "aria: e.getAttribute('aria-label'), test: e.getAttribute('data-testid'), "
                "href: e.getAttribute('href'), cls: String(e.className||'').slice(0,60)}))"),
            "inputs": page.eval_on_selector_all(
                "input",
                "els => els.slice(0,20).map(e => ({type: e.type, accept: e.accept, "
                "multiple: e.multiple, name: e.name, id: e.id}))"),
        }
        alvo = pasta / f"{_carimbo()}_dom_{nome}.json"
        alvo.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return str(alvo)
    except Exception:                                          # noqa: BLE001
        return None


def _anotar_textos(ficha: dict, page, seletor: str | None = None) -> list:
    """Varre o texto visivel e junta o que e aviso ao catalogo da ficha."""
    novos = catalogo.varrer(_texto_visivel(page), fonte="sonda",
                            visto_em=fichas.agora(), seletor=seletor)
    ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], novos)
    return novos


def _linhas_de_plano(page) -> list:
    """Linhas curtas da tela que falam de plano/cota (o que o site diz)."""
    saida = []
    for linha in _texto_visivel(page).splitlines():
        limpo = " ".join(linha.split())
        if 3 <= len(limpo) <= 120 and PLANO.search(limpo):
            if limpo not in saida:
                saida.append(limpo)
    return saida[:12]


def _medir_png(caminho: Path) -> tuple:
    """(largura, altura, tem_alfa_de_verdade)."""
    from PIL import Image
    with Image.open(caminho) as img:
        tem_alfa = False
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            canal = img.convert("RGBA").getchannel("A")
            tem_alfa = canal.getextrema()[0] < 255
        return img.width, img.height, tem_alfa


# ================================================================ os chats
def _estado_login(page, alvo: dict) -> tuple:
    """(estado, detalhe) — os TRES estados (login-do-llm-tres-estados)."""
    from contos.llm import probe, seletores as sel
    if sel.encontrar(page, alvo["logado"], timeout=6.0) is not None:
        return "logado", "o campo de prompt montou na janela de verdade"
    titulo = (page.title() or "").strip()
    if any(marca in titulo.lower() for marca in probe.BARRADO):
        return "nao_sei", f"desafio anti-bot na tela ({titulo!r})"
    if sel.encontrar(page, alvo["login"], timeout=3.0) is not None:
        return "deslogado", "a tela de login esta na frente"
    return "nao_sei", f"nem o chat nem a tela de login em {page.url}"


def _modelos_do_chat(ia: str, cliente, ficha: dict, log) -> None:
    from contos.llm import seletores as sel
    page = cliente.page
    bloco = ficha["modelos"]
    if ia == "deepseek":
        estado = None
        try:
            botao = sel.encontrar(page, cliente.sel.get("deepthink_botao") or [], timeout=4.0)
            if botao is not None:
                estado = botao.evaluate(
                    "el => { const p = el.getAttribute('aria-pressed');"
                    " if (p === 'true') return true; if (p === 'false') return false;"
                    " const c = String(el.className || '').toLowerCase();"
                    " return /active|selected|checked/.test(c) ? true : null; }")
        except Exception:                                      # noqa: BLE001
            pass
        bloco["ativo"] = cliente.sel.get("modelo_fixo") or "DeepSeek (site)"
        bloco["disponiveis"] = ["DeepSeek (site)", "DeepThink " + (
            "ligado" if estado else "desligado" if estado is False else "(estado ilegivel)")]
        bloco["seletor"] = (cliente.sel.get("deepthink_botao") or [None])[0]
        return
    extra = SELETORES_DE_MODELO.get(ia) or {}
    candidatos_botao = list(cliente.sel.get("modelo_botao") or []) + list(extra.get("botao") or [])
    candidatos_opcao = list(cliente.sel.get("modelo_opcao") or []) + list(extra.get("opcao") or [])
    botao = sel.encontrar(page, candidatos_botao, timeout=6.0)
    if botao is None:
        bloco["seletor"] = None
        ficha["pendencias"].append("seletor de modelo nao achado (menu pode nao existir na conta free)")
        return
    try:
        bloco["ativo"] = " ".join((botao.inner_text(timeout=3000) or "").split())[:60] or None
        bloco["seletor"] = candidatos_botao[0]
        botao.click(timeout=8000)
        _pausa(cliente.rng, 0.8, 1.4)
        vistos = []
        for seletor in candidatos_opcao:
            achado = page.locator(seletor)
            total = min(achado.count(), 12)
            for i in range(total):
                try:
                    if not achado.nth(i).is_visible():
                        continue
                    texto = " ".join((achado.nth(i).inner_text(timeout=1500) or "").split())[:80]
                except Exception:                              # noqa: BLE001
                    continue
                if texto and texto not in vistos:
                    vistos.append(texto)
            if vistos:
                break
        bloco["disponiveis"] = vistos
        page.keyboard.press("Escape")
        _pausa(cliente.rng, 0.4, 0.8)
    except Exception as exc:                                   # noqa: BLE001
        log(f"[sonda] {ia}: leitura do menu de modelo falhou ({type(exc).__name__})")
        try:
            page.keyboard.press("Escape")
        except Exception:                                      # noqa: BLE001
            pass


def _limite_do_campo(cliente, ficha: dict, log) -> None:
    """maxlength do campo e quantos chars ele aceita colados (sem enviar)."""
    from contos.llm import seletores as sel
    page = cliente.page
    campo = sel.encontrar(page, cliente.sel["campo"], timeout=5.0)
    if campo is None:
        return
    try:
        maxlength = campo.get_attribute("maxlength")
        ficha["texto"]["limite_chars_campo"] = int(maxlength) if maxlength and maxlength.isdigit() else None
    except Exception:                                          # noqa: BLE001
        pass
    try:
        campo.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        texto = ("x" * 99 + " ") * (CHARS_DE_PROVA // 100)
        if cliente._aceita_fill(campo):
            campo.fill(texto)
        else:
            page.keyboard.insert_text(texto)
        time.sleep(1.0)
        aceito = len(cliente._texto_do_campo(campo))
        ficha["texto"]["chars_aceitos_no_campo"] = aceito
        log(f"[sonda] campo aceitou {aceito} de {len(texto)} chars colados")
        campo.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        time.sleep(0.5)
        if len(cliente._texto_do_campo(campo).strip()) > 5:
            # Editor que nao limpou: recarrega o chat novo em vez de enviar lixo.
            page.goto(cliente.sel["url_novo_chat"], wait_until="domcontentloaded",
                      timeout=90_000)
            cliente._esperar_montar()
    except Exception as exc:                                   # noqa: BLE001
        log(f"[sonda] medida do campo falhou ({type(exc).__name__}: {str(exc)[:80]})")
        try:
            page.goto(cliente.sel["url_novo_chat"], wait_until="domcontentloaded",
                      timeout=90_000)
            cliente._esperar_montar()
        except Exception:                                      # noqa: BLE001
            pass


def _accept_do_anexo(cliente, ficha: dict, log) -> None:
    """O `accept`/`multiple` do input de arquivo (sem subir nada)."""
    from contos.llm import seletores as sel
    page = cliente.page
    bloco = ficha["anexos"]
    campo = sel.encontrar_oculto(page, cliente.sel["anexo_input"], timeout=2.0)
    clicou = False
    if campo is None:
        botao = sel.encontrar(page, cliente.sel.get("anexo_botao") or [], timeout=4.0)
        if botao is not None:
            try:
                botao.click(timeout=6000)
                clicou = True
                _pausa(cliente.rng, 0.5, 1.0)
            except Exception:                                  # noqa: BLE001
                pass
        campo = sel.encontrar_oculto(page, cliente.sel["anexo_input"], timeout=6.0)
    if clicou:
        # O menu do "+" lista o que a conta pode fazer: vale como texto.
        _anotar_textos(ficha, page, seletor="(menu de anexo)")
        try:
            page.keyboard.press("Escape")
        except Exception:                                      # noqa: BLE001
            pass
    if campo is None:
        bloco["seletor"] = None
        ficha["pendencias"].append("input[type=file] nao achado: anexo nao medido")
        return
    try:
        accept = campo.get_attribute("accept") or ""
        multiplos = campo.get_attribute("multiple")
    except Exception:                                          # noqa: BLE001
        return
    bloco["seletor"] = "input[type='file']"
    bloco["accept"] = accept
    bloco["multiplos"] = multiplos is not None
    baixo = accept.lower()
    if not baixo:
        # Sem restricao no input: o site decide no envio. Imagem certamente
        # entra; video/arquivo ficam "provavel" (True) com a nota.
        bloco["imagem"], bloco["video"], bloco["arquivo"] = True, True, True
        ficha["pendencias"].append("accept vazio no input: video/arquivo aceitos pelo INPUT, "
                                   "nao provado no envio")
    else:
        bloco["imagem"] = ("image" in baixo) or (".png" in baixo) or (".jpg" in baixo)
        bloco["video"] = ("video" in baixo) or (".mp4" in baixo)
        bloco["arquivo"] = any(m in baixo for m in ("pdf", "text", "application", ".txt", ".doc", ".csv"))
    log(f"[sonda] anexo: accept={accept!r} multiple={bloco['multiplos']}")


def _imagens_da_resposta(cliente) -> list:
    """`[{src, w, h}]` das imagens dentro do ULTIMO turno do assistente."""
    js = (
        "([respostas, usuarios]) => {"
        " const depois = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);"
        " let usuario = null;"
        " for (const s of usuarios) { let els = [];"
        "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
        "   const u = els[els.length - 1]; if (u && (!usuario || depois(usuario, u))) usuario = u; }"
        " for (const s of respostas) { let els = [];"
        "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
        "   if (usuario) els = els.filter(e => depois(usuario, e));"
        "   if (!els.length) continue;"
        "   const alvo = els[els.length - 1];"
        "   return [...alvo.querySelectorAll('img')]"
        "     .filter(i => i.naturalWidth >= 64 && i.naturalHeight >= 64)"
        "     .map(i => ({src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight,"
        "                 alt: i.alt || ''}));"
        " }"
        " return []; }")
    try:
        achado = cliente.page.evaluate(js, [list(cliente.sel.get("resposta") or []),
                                            list(cliente.sel.get("turno_usuario") or [])])
        return achado if isinstance(achado, list) else []
    except Exception:                                          # noqa: BLE001
        return []


def _baixar_imagem(cliente, src: str, destino: Path) -> Path | None:
    """Traz a imagem da resposta para o disco (blob:, data: ou https)."""
    import base64
    js = ("async (src) => { const r = await fetch(src); const b = await r.blob();"
          " const buf = await b.arrayBuffer();"
          " let s = ''; const bytes = new Uint8Array(buf);"
          " for (let i = 0; i < bytes.length; i += 0x8000)"
          "   s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));"
          " return {tipo: b.type, b64: btoa(s)}; }")
    corpo = None
    try:
        achado = cliente.page.evaluate(js, src)
        if isinstance(achado, dict) and achado.get("b64"):
            corpo = base64.b64decode(achado["b64"])
    except Exception:                                          # noqa: BLE001
        corpo = None
    if corpo is None and src.startswith("http"):
        try:
            resposta = cliente.ctx.request.get(src, timeout=60_000)
            if resposta.ok:
                corpo = resposta.body()
        except Exception:                                      # noqa: BLE001
            corpo = None
    if not corpo or len(corpo) < 512:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(corpo)
    return destino


def _imagem_no_chat(ia: str, cliente, ficha: dict, pasta: Path, log) -> None:
    """Pede UMA imagem 1:1 e mede o que voltou (ou o texto que veio no lugar)."""
    from contos.llm import seletores as sel, texto as txt
    page = cliente.page
    bloco = ficha["imagem"]
    inicio = time.monotonic()
    try:
        cliente.enviar(PEDIDO_IMAGEM)
    except Exception as exc:                                   # noqa: BLE001
        bloco["gera"] = None
        ficha["pendencias"].append(f"pedido de imagem nao enviado: {type(exc).__name__}: {str(exc)[:100]}")
        return
    fim = inicio + PRAZO_IMAGEM_S
    imagens, texto, parado_desde = [], "", None
    while time.monotonic() < fim:
        imagens = _imagens_da_resposta(cliente)
        texto = cliente._resposta_nova()
        escrevendo = sel.encontrar(page, cliente.sel["parar"], timeout=0.3) is not None
        if imagens and not escrevendo:
            break
        if not escrevendo and texto.strip():
            parado_desde = parado_desde or time.monotonic()
            if time.monotonic() - parado_desde >= 6.0 and time.monotonic() - inicio > 20:
                break
        else:
            parado_desde = None
        time.sleep(2.0)
    decorrido = time.monotonic() - inicio
    bloco["tempo_s"] = round(decorrido, 1)
    bloco["prova"] = _captura(page, pasta, "imagem", ficha, log)
    cliente._ultima_resposta = texto
    if txt.e_recusa_enlatada(texto):
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("recusa_enlatada", texto, seletor=(cliente.sel.get("resposta") or [None])[0],
                          visto_em=fichas.agora(), nota="ao pedir imagem 1:1")])
    novos = catalogo.varrer(texto, visto_em=fichas.agora(),
                            seletor=(cliente.sel.get("resposta") or [None])[0])
    ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], novos)
    if not imagens:
        bloco["gera"] = False
        bloco["prova_origem"] = {"tipo": "chat proprio", "url_chat": page.url,
                                 "prompt": PEDIDO_IMAGEM, "resposta": texto[:300]}
        log(f"[sonda] {ia}: sem imagem em {decorrido:.0f}s; resposta: {texto[:120]!r}")
        return
    escolhida = imagens[-1]
    destino = pasta / f"{_carimbo()}_circulo_{ia}.png"
    arquivo = _baixar_imagem(cliente, escolhida["src"], destino)
    bloco["gera"] = True
    bloco["prova_origem"] = {"tipo": "chat proprio (nosso turno, nosso prompt)",
                             "url_chat": page.url, "prompt": PEDIDO_IMAGEM,
                             "src": str(escolhida["src"])[:200],
                             "na_tela": [escolhida["w"], escolhida["h"]],
                             "comprovada": True}
    if arquivo is None:
        bloco["resolucao"] = [escolhida["w"], escolhida["h"]]
        ficha["pendencias"].append("imagem gerada mas nao baixada (medida so pela tela)")
        return
    try:
        largura, altura, alfa = _medir_png(arquivo)
        bloco["resolucao"] = [largura, altura]
        bloco["alfa"] = alfa
        bloco["arquivo"] = str(arquivo)
        log(f"[sonda] {ia}: imagem {largura}x{altura} alfa={alfa} em {decorrido:.0f}s")
    except Exception as exc:                                   # noqa: BLE001
        bloco["resolucao"] = [escolhida["w"], escolhida["h"]]
        ficha["pendencias"].append(f"arquivo da imagem ilegivel ({type(exc).__name__})")


def sondar_chat(ia: str, *, gastar: bool = True, headless: bool = False,
                log=_log_padrao) -> dict:
    """Uma IA de chat inteira. Devolve a ficha (ja gravada por quem chama)."""
    import builds.travas as travas
    from builds.identity import browser
    from contos.llm import cliente as cli, seletores as sel

    ficha = fichas.carregar(ia)
    ficha["catalogo_textos"] = catalogo.juntar(catalogo.conhecidos(ia), ficha["catalogo_textos"])
    ficha["pendencias"] = []
    pasta = pasta_de(ia)
    alvo = sel.do_provedor(ia)
    ficha["site"] = alvo["url"]
    perfil = cli.perfil_de(ia)
    ficha["perfil"] = str(perfil)
    nome_trava = travas.do_perfil(ia, "geral")
    ficha["trava"] = nome_trava
    inicio = time.monotonic()
    ficha["medido_em"] = fichas.agora()

    with travas.trava(nome_trava, esperar=ESPERA_CONTA_S) as minha:
        if not minha:
            ficha["login"] = {"estado": "conta_ocupada",
                              "detalhe": f"a trava {nome_trava} esta com outro processo "
                                         f"(a rodada das historias?) — sonda adiada",
                              "prova": None}
            ficha["pendencias"].append("conta ocupada: rodar de novo quando a rodada soltar")
            ficha["duracao_s"] = round(time.monotonic() - inicio, 1)
            return ficha
        with browser.contexto_persistente(headless=headless, profile=perfil,
                                          esperar=ESPERA_CONTA_S) as ctx:
            page = browser.pagina(ctx)
            cliente = cli.ClienteLLM(ia, ctx, page,
                                     {"resposta_timeout": PRAZO_TEXTO_S,
                                      "pensar_ate": 120}, log=log)
            page.goto(alvo["url_novo_chat"], wait_until="domcontentloaded", timeout=90_000)
            cliente._esperar_montar()
            _pausa(cliente.rng, 1.5, 2.5)
            prova = _captura(page, pasta, "abertura", ficha, log)
            estado, detalhe = _estado_login(page, alvo)
            ficha["login"] = {"estado": estado, "detalhe": detalhe, "prova": prova}
            _anotar_textos(ficha, page)
            ficha["cota"]["o_que_o_site_diz"] = _linhas_de_plano(page)
            ficha["cota"]["prova"] = prova
            log(f"[sonda] {ia}: login {estado} ({detalhe})")
            if estado != "logado":
                dom = _despejar_dom(page, pasta, "deslogado")
                if dom:
                    ficha["capturas"].append(dom)
                if ia == "grok":
                    ficha["pendencias"].append(
                        "sem login; aguardando o Adrian (no ias-grok-acesso)")
                else:
                    ficha["pendencias"].append(
                        f"sem login: python main.py llm login --provedor {ia}")
                ficha["duracao_s"] = round(time.monotonic() - inicio, 1)
                return ficha

            _modelos_do_chat(ia, cliente, ficha, log)
            ficha["modelos"]["prova"] = _captura(page, pasta, "modelo", ficha, log)
            _limite_do_campo(cliente, ficha, log)
            _accept_do_anexo(cliente, ficha, log)
            dom = _despejar_dom(page, pasta, "logado")
            if dom:
                ficha["capturas"].append(dom)

            if gastar:
                # 1) texto: "OK" e o tempo dele.
                try:
                    t0 = time.monotonic()
                    cliente.enviar(PEDIDO_OK)
                    resposta = cliente.esperar_resposta(PRAZO_TEXTO_S, estabilidade=2.0)
                    ficha["texto"]["tempo_ok_s"] = round(time.monotonic() - t0, 1)
                    ficha["texto"]["gera"] = bool(resposta.strip())
                    ficha["texto"]["resposta"] = resposta[:200]
                    log(f"[sonda] {ia}: texto em {ficha['texto']['tempo_ok_s']}s: {resposta[:60]!r}")
                except Exception as exc:                       # noqa: BLE001
                    ficha["texto"]["gera"] = None
                    ficha["pendencias"].append(f"texto: {type(exc).__name__}: {str(exc)[:120]}")
                    log(f"[sonda] {ia}: texto falhou: {exc}")
                ficha["texto"]["prova"] = _captura(page, pasta, "texto", ficha, log)
                _anotar_textos(ficha, page)
                _pausa(cliente.rng, 1.5, 3.0)

                # 2) anexo: o PNG nosso, e se o modelo LEU o anexo.
                if ficha["anexos"].get("imagem") is not False:
                    try:
                        quantos = cliente.anexar([PNG_FIXTURE], espera=60.0)
                        _pausa(cliente.rng, 0.8, 1.5)
                        cliente.enviar(PEDIDO_ANEXO)
                        resposta = cliente.esperar_resposta(PRAZO_TEXTO_S, estabilidade=2.0)
                        baixo = resposta.lower()
                        ficha["anexos"]["imagem"] = quantos >= 1
                        ficha["anexos"]["leu_o_anexo"] = ("verm" in baixo or "red" in baixo)
                        log(f"[sonda] {ia}: anexo {quantos}, leu={ficha['anexos']['leu_o_anexo']} "
                            f"({resposta[:60]!r})")
                    except Exception as exc:                   # noqa: BLE001
                        ficha["pendencias"].append(f"anexo: {type(exc).__name__}: {str(exc)[:120]}")
                        log(f"[sonda] {ia}: anexo falhou: {exc}")
                    ficha["anexos"]["prova"] = _captura(page, pasta, "anexo", ficha, log)
                    _anotar_textos(ficha, page)
                    _pausa(cliente.rng, 1.5, 3.0)

                # 3) imagem: so onde o site oferece.
                if ia in CHATS_QUE_DESENHAM:
                    _imagem_no_chat(ia, cliente, ficha, pasta, log)
                else:
                    ficha["imagem"]["gera"] = False
                    ficha["imagem"]["prova_origem"] = {"tipo": "nao pedido",
                                                       "motivo": "o site nao oferece geracao de imagem"}
            _anotar_textos(ficha, page)
            ficha["cota"]["o_que_o_site_diz"] = list(dict.fromkeys(
                ficha["cota"]["o_que_o_site_diz"] + _linhas_de_plano(page)))[:12]

    # O que se sabe de VIDEO vem da producao, nao desta sonda (custaria um
    # mp4 por IA): ver docs/sessoes/historias.md §2.
    if ia == "gemini":
        ficha["video"] = {"assiste": True, "gera": None,
                          "fonte": "logs: parecer de video em producao (unico que assiste mp4)"}
    elif ia == "chatgpt":
        ficha["video"] = {"assiste": False, "gera": None,
                          "fonte": "docs: conta free recebe o mp4 como 'Arquivo' opaco (12/09)"}
    elif ia == "deepseek":
        ficha["video"] = {"assiste": False, "gera": None,
                          "fonte": "sonda: accept do input" if ficha["anexos"].get("accept") else "nao medido"}
    _inferir_custo(ficha)
    ficha["duracao_s"] = round(time.monotonic() - inicio, 1)
    return ficha


def _inferir_custo(ficha: dict) -> None:
    """Gratis x plano, so pelo que foi VISTO (textos de upgrade na tela)."""
    upgrades = [it["texto"] for it in ficha["catalogo_textos"]
                if it.get("categoria") == "upgrade" and it.get("fonte") in ("sonda", "docs")]
    if upgrades and not ficha["cota"].get("plano"):
        ficha["cota"]["plano"] = "gratuito (o site oferece upgrade)"
    gratis = []
    if ficha["texto"].get("gera"):
        gratis.append("texto")
    if ficha["anexos"].get("imagem"):
        gratis.append("anexo de imagem")
    if ficha["imagem"].get("gera"):
        gratis.append("imagem no chat")
    if ficha["video"].get("assiste"):
        gratis.append("assistir video")
    ficha["custo"]["gratis"] = gratis
    pede = list(ficha["custo"].get("pede_plano") or [])
    if ficha["imagem"].get("gera") is False and ficha["ia"] in CHATS_QUE_DESENHAM:
        pede.append("imagem no chat (recusou/nao gerou na conta atual)")
    ficha["custo"]["pede_plano"] = list(dict.fromkeys(pede))


# ============================================================ os geradores
def _sessao_do_gerador(page, sel) -> tuple:
    from builds.identity import selectors as motor
    from contos.llm import probe
    if motor.encontrar(page, sel.SESSAO_VIVA, timeout=8.0) is not None:
        return "logado", "o compositor esta na tela"
    titulo = (page.title() or "").strip()
    if any(marca in titulo.lower() for marca in probe.BARRADO):
        return "nao_sei", f"desafio anti-bot ({titulo!r})"
    if motor.encontrar(page, sel.DESAFIO, timeout=1.5) is not None:
        return "nao_sei", "captcha/desafio na tela"
    if motor.encontrar(page, sel.TELA_LOGIN, timeout=3.0) is not None:
        return "deslogado", "a tela de login esta na frente"
    return "nao_sei", f"nem compositor nem login em {page.url}"


def sondar_gerador(ia: str, *, gastar: bool = True, headless: bool = False,
                   log=_log_padrao) -> dict:
    import builds.contas as contas
    import builds.travas as travas
    from builds.identity import browser, config as icfg, provedores

    ficha = fichas.carregar(ia)
    ficha["catalogo_textos"] = catalogo.juntar(catalogo.conhecidos(ia), ficha["catalogo_textos"])
    ficha["pendencias"] = []
    pasta = pasta_de(ia)
    sel = provedores.seletores(ia)
    canal = "historias" if ia in ("picasso", "dreamface") else "builds"
    perfil = contas.perfil(ia, canal)
    ficha["site"] = sel.URL_CRIACAO
    ficha["perfil"] = str(perfil)
    nome_trava = travas.do_perfil(ia, canal)
    ficha["trava"] = nome_trava
    ajustes = icfg.settings(ia) if ia != "dreamface" else icfg.settings()
    inicio = time.monotonic()
    ficha["medido_em"] = fichas.agora()

    with travas.trava(nome_trava, esperar=ESPERA_CONTA_S) as minha:
        if not minha:
            ficha["login"] = {"estado": "conta_ocupada",
                              "detalhe": f"a trava {nome_trava} esta com outro processo",
                              "prova": None}
            ficha["pendencias"].append("conta ocupada: rodar de novo depois")
            ficha["duracao_s"] = round(time.monotonic() - inicio, 1)
            return ficha
        with browser.contexto_persistente(headless=headless, profile=perfil,
                                          esperar=ESPERA_CONTA_S) as ctx:
            page = browser.pagina(ctx)
            rng = random.Random()
            page.goto(sel.URL_CRIACAO, wait_until="domcontentloaded",
                      timeout=int(float(ajustes.get("navigation_timeout", 60)) * 1000))
            browser.esperar_hidratacao(page, float(ajustes.get("hydration_timeout", 45)))
            _pausa(rng, 2.0, 3.5)
            prova = _captura(page, pasta, "abertura", ficha, log)
            estado, detalhe = _sessao_do_gerador(page, sel)
            ficha["login"] = {"estado": estado, "detalhe": detalhe, "prova": prova}
            _anotar_textos(ficha, page)
            ficha["cota"]["o_que_o_site_diz"] = _linhas_de_plano(page)
            ficha["cota"]["prova"] = prova
            log(f"[sonda] {ia}: login {estado} ({detalhe})")
            dom = _despejar_dom(page, pasta, estado)
            if dom:
                ficha["capturas"].append(dom)
            if estado != "logado":
                ficha["pendencias"].append(
                    f"sem login: python main.py identity login --provedor {ia} (em random_builds)")
                ficha["duracao_s"] = round(time.monotonic() - inicio, 1)
                return ficha

            ficha["texto"]["gera"] = False       # gerador nao conversa
            if ia == "picasso":
                _sondar_picasso(ctx, page, sel, ajustes, ficha, pasta, gastar, log)
            elif ia == "dreamface":
                _sondar_dreamface(page, sel, ficha, pasta, log)
            elif ia == "digen":
                _sondar_digen(ctx, page, sel, ajustes, ficha, pasta, log)
            _anotar_textos(ficha, page)
            ficha["cota"]["o_que_o_site_diz"] = list(dict.fromkeys(
                ficha["cota"]["o_que_o_site_diz"] + _linhas_de_plano(page)))[:12]
    ficha["duracao_s"] = round(time.monotonic() - inicio, 1)
    return ficha


def _sondar_picasso(ctx, page, sel, ajustes, ficha, pasta, gastar, log) -> None:
    from builds.identity.client import ConteudoRecusado, EsperaEstourou
    from builds.identity.picasso_client import ParedeDePlanos, PicassoClient

    cliente = PicassoClient(ctx, page, ajustes)
    parede = cliente._tirar_parede_da_frente()
    if parede:
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("parede", parede, seletor="div[role='dialog']", visto_em=fichas.agora(),
                          nota="fechada pela sonda (X/ESC)")])
    ficha["modelos"]["ativo"] = cliente._modelo_atual()
    ficha["modelos"]["seletor"] = 'button:has-text("picassoia image")'
    ficha["modelos"]["disponiveis"] = [m for m in [ficha["modelos"]["ativo"]] if m]
    # Os <select> nativos dizem o que a conta pode pedir.
    aspectos = []
    try:
        for i in range(page.locator("select").count()):
            opcoes = page.locator("select").nth(i).evaluate(
                "e => Array.from(e.options).map(o => o.value)")
            aspectos.append(opcoes)
    except Exception:                                          # noqa: BLE001
        pass
    ficha["custo"]["gratis"] = [f"selects: {aspectos}"] if aspectos else []
    sem_plano = cliente._sem_plano()
    if sem_plano:
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("upgrade", "Assine para Gerar", seletor="button:has-text('Assine para Gerar')",
                          visto_em=fichas.agora())])
        ficha["cota"]["plano"] = "sessao FREE (Assine para Gerar na tela)"
    ficha["cota"]["creditos"] = cliente.creditos()
    ficha["anexos"] = {**ficha["anexos"], "imagem": None, "video": False, "arquivo": False,
                       "seletor": "button[aria-label='Carregar imagem'] (Editor Pro)",
                       "prova": None}
    ficha["video"] = {"assiste": False, "gera": False, "fonte": "site: so imagem"}
    ficha["modelos"]["prova"] = _captura(page, pasta, "compositor", ficha, log)

    if not gastar:
        return
    bloco = ficha["imagem"]
    t0 = time.monotonic()
    try:
        antes = cliente.submit_prompt(PROMPT_GERADOR, aspect="1:1")
        url = cliente.wait_for_render(antes=antes)
        bloco["tempo_s"] = round(time.monotonic() - t0, 1)
        prova = cliente.comprovar_origem(url, cliente.prompt_enviado or PROMPT_GERADOR,
                                         cliente.enviado_em)
        bloco["prova_origem"] = prova
        bloco["prova"] = _captura(page, pasta, "imagem", ficha, log)
        if prova.get("comprovada"):
            destino = pasta / f"{_carimbo()}_circulo_picasso.png"
            cliente.download(prova.get("url") or url, destino)
            largura, altura, alfa = _medir_png(destino)
            bloco.update({"gera": True, "resolucao": [largura, altura], "alfa": alfa,
                          "arquivo": str(destino)})
            log(f"[sonda] picasso: imagem {largura}x{altura} alfa={alfa} em {bloco['tempo_s']}s")
        else:
            bloco["gera"] = True
            ficha["pendencias"].append(
                f"imagem gerou mas SEM prova de origem no historico ({prova.get('motivo', '?')}): nao baixada")
    except ConteudoRecusado as exc:
        bloco["gera"] = None
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("conteudo", str(exc), seletor="svg.lucide-shield-alert", visto_em=fichas.agora())])
        ficha["pendencias"].append(f"recusa de conteudo num circulo vermelho?! {str(exc)[:100]}")
    except ParedeDePlanos as exc:
        bloco["gera"] = None
        ficha["cota"]["plano"] = "parede de planos"
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("upgrade", str(exc), seletor="button:has-text('Assine para Gerar')",
                          visto_em=fichas.agora())])
        ficha["pendencias"].append("parede de planos na sonda: reabrir o perfil (worker faz isso)")
    except EsperaEstourou as exc:
        bloco["gera"] = None
        ficha["pendencias"].append(f"a imagem nao voltou: {str(exc)[:120]}")
    except Exception as exc:                                   # noqa: BLE001
        bloco["gera"] = None
        ficha["pendencias"].append(f"geracao falhou: {type(exc).__name__}: {str(exc)[:120]}")
    bloco["prova"] = bloco.get("prova") or _captura(page, pasta, "imagem", ficha, log)


def _sondar_dreamface(page, sel, ficha, pasta, log) -> None:
    from builds.identity import selectors as motor
    botao = motor.encontrar(page, sel.BOTAO_MODELO, timeout=4.0)
    ficha["modelos"]["ativo"] = " ".join((botao.inner_text() or "").split())[:60] if botao else None
    ficha["modelos"]["disponiveis"] = list(sel.MODELOS)
    ficha["modelos"]["seletor"] = sel.BOTAO_MODELO[0][1]
    credito = motor.encontrar(page, sel.CREDITOS, timeout=4.0)
    if credito is not None:
        texto = " ".join((credito.inner_text() or "").split())
        numero = re.search(r"\d+", texto)
        ficha["cota"]["creditos"] = int(numero.group()) if numero else None
        ficha["cota"]["o_que_o_site_diz"] = list(dict.fromkeys(
            [texto[:80]] + ficha["cota"]["o_que_o_site_diz"]))
    aspecto = motor.encontrar(page, sel.BOTAO_ASPECTO, timeout=2.0)
    ficha["custo"]["gratis"] = [f"aspecto atual: {(aspecto.inner_text() or '').strip()}"] if aspecto else []
    erro = motor.encontrar(page, sel.ERRO_GERACAO, timeout=1.0)
    if erro is not None:
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("limite", (erro.inner_text() or "")[:200], seletor="text=…", visto_em=fichas.agora())])
    ficha["anexos"] = {**ficha["anexos"], "imagem": True, "video": False, "arquivo": False,
                       "seletor": "input[type='file'] (referencia)", "prova": None}
    ficha["video"] = {"assiste": False, "gera": None, "fonte": "site: imagem (e avatar/video em outra tela)"}
    ficha["imagem"]["gera"] = None
    ficha["pendencias"].append(
        "geracao NAO sondada: nao ha cliente do DreamFace com prova de origem "
        "(so seletores); gerar sem prova violaria a regra da conta compartilhada")
    ficha["modelos"]["prova"] = _captura(page, pasta, "compositor", ficha, log)


def _sondar_digen(ctx, page, sel, ajustes, ficha, pasta, log) -> None:
    from builds.identity.client import DigenClient, tirar_parede_da_frente
    parede = tirar_parede_da_frente(page)
    if parede:
        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
            catalogo.item("parede", parede, seletor=sel.PAREDE, visto_em=fichas.agora(),
                          nota="fechada pela sonda")])
    cliente = DigenClient(ctx, page, ajustes)
    ficha["modelos"]["ativo"] = cliente._modelo_atual()
    ficha["modelos"]["seletor"] = sel.BOTAO_MODELO[0][1] if getattr(sel, "BOTAO_MODELO", None) else None
    try:
        from builds.identity import selectors as motor
        botao = motor.encontrar(page, sel.CREDITOS, timeout=4.0)
        rotulo = (botao.get_attribute("aria-label") or "") if botao else ""
        ficha["cota"]["creditos"] = cliente.creditos(espera=20)
        if rotulo:
            ficha["cota"]["o_que_o_site_diz"] = list(dict.fromkeys(
                [rotulo[:100]] + ficha["cota"]["o_que_o_site_diz"]))
            ficha["cota"]["plano"] = rotulo.split(",")[0].strip()[:40]
    except Exception as exc:                                   # noqa: BLE001
        ficha["pendencias"].append(f"creditos ilegiveis ({type(exc).__name__})")
    ficha["anexos"] = {**ficha["anexos"], "imagem": True, "video": None, "arquivo": False,
                       "seletor": "composer '+' (uma imagem de referencia)", "prova": None}
    ficha["video"] = {"assiste": False, "gera": True, "fonte": "producao: payoff das builds"}
    ficha["imagem"]["gera"] = False
    ficha["imagem"]["prova_origem"] = {"tipo": "nao pedido", "motivo": "gerador de VIDEO (custa credito); nada gerado na sonda"}
    ficha["modelos"]["prova"] = _captura(page, pasta, "compositor", ficha, log)


# ==================================================================== porta
def sondar(ia: str, *, gastar: bool = True, headless: bool = False,
           log=_log_padrao) -> dict:
    """Sonda UMA IA, grava a ficha e devolve. Nunca deixa de gravar."""
    ia = str(ia).lower()
    if ia not in IAS:
        raise ValueError(f"IA desconhecida: {ia!r}. Use uma de: {', '.join(IAS)}")
    log(f"[sonda] === {ia} ===")
    try:
        if ia in CHATS:
            ficha = sondar_chat(ia, gastar=gastar, headless=headless, log=log)
        else:
            ficha = sondar_gerador(ia, gastar=gastar, headless=headless, log=log)
    except Exception as exc:                                   # noqa: BLE001
        ficha = fichas.carregar(ia)
        ficha["medido_em"] = fichas.agora()
        ficha["pendencias"] = list(ficha.get("pendencias") or []) + [
            f"a sonda caiu: {type(exc).__name__}: {str(exc)[:160]}"]
        if ficha["login"]["estado"] == "nao_medido":
            ficha["login"]["detalhe"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        log(f"[sonda] {ia}: a sonda caiu: {type(exc).__name__}: {str(exc)[:200]}")
    caminho = fichas.salvar(ficha)
    log(f"[sonda] {ia}: ficha em {caminho}")
    return ficha
