# -*- coding: utf-8 -*-
"""A sessao GUIADA: o Adrian mostra na tela, esta sessao grava.

Ordem dele (29/09/2026, 01:35): "preciso que voce abra uma sessao de cada
um para eu fazer o guia pra voce, voce se perde muito facil". Entao a sonda
automatica nao decide sozinha: o navegador fica VISIVEL, ele faz cada acao
devagar, e este modulo grava — captura da janela (PrintWindow, nunca da
tela: memoria ler-a-tela-nao-o-dom), o DOM do elemento clicado/focado e a
URL — em `random_builds/outputs/_ias/<ia>/guia/`, com carimbo de hora.

    python -m ias guia grok            abre, avisa no Telegram, grava

O contrato com a janela flutuante que o painel esta construindo e SO por
arquivos:

  _atual.json          escrito AQUI: {"ia", "passo", "desde"} a cada passo.
  <ia>/guia/colado.jsonl   escrito por ELE (append): `papel` em
                       {campo_texto, enviar, resposta, seletor_modelo, anexo,
                       gerar_imagem, erro_cota, observacao, proximo, mensagem},
                       `tipo` em {html, seletor, texto}, `conteudo`, `previa`,
                       `seletor_sugerido`. `proximo` avanca o passo;
                       `erro_cota` vai direto ao catalogo da ficha.
  <ia>/guia/comando.json   escrito por esta sessao de agente, lido aqui:
                       {"acao": "testar_ok"|"avisar"|"fechar"|"passo", ...}.
                       E o que permite testar o seletor NA MESMA sessao
                       (passo 4 do protocolo) sem fechar a janela.

Nunca fecha a janela sem avisar; nunca clica em plano/compra; nada em rajada.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import random
import re
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from . import catalogo, ficha as fichas
from .sonda import PASTA_PROVAS, PEDIDO_OK, _pausa

PASSOS = ("onde escreve", "como manda", "onde a resposta aparece",
          "onde troca de modelo", "como anexa imagem", "onde gera imagem",
          "o que aparece quando a cota acaba")
INTERVALO_S = 2.0
LEMBRETE_APOS_S = 15 * 60
ATUAL = PASTA_PROVAS / "_atual.json"

URLS = {
    "grok": "https://grok.com/",
    "gemini": "https://gemini.google.com/app",
    "chatgpt": "https://chatgpt.com/",
    "deepseek": "https://chat.deepseek.com/",
    "picasso": "https://picassoia.com/pt/collection/text-to-image/picassoia-image",
    "dreamface": "https://www.dreamfaceapp.com/pt/image",
    "digen": "https://digen.ai/en/space",
}
TITULOS = {"grok": "Grok", "gemini": "Gemini", "chatgpt": "ChatGPT",
           "deepseek": "DeepSeek", "picasso": "Picasso", "dreamface": "DreamFace",
           "digen": "Digen"}

# O que fica instalado na pagina: cada clique/foco/tecla vira um registro
# com o elemento e um caminho de seletor legivel (papel/aria/texto, e so
# por ultimo classe) — e o que o passo 4 traduz em `seletores.py`.
JS_INSTALAR = r"""() => {
  if (window.__guia_on) return false;
  window.__guia_on = true;
  window.__guia = [];
  const desc = (el) => {
    if (!el || !el.tagName) return null;
    const a = (n) => el.getAttribute ? el.getAttribute(n) : null;
    const partes = [];
    const tag = el.tagName.toLowerCase();
    if (a('data-testid')) partes.push(`${tag}[data-testid='${a('data-testid')}']`);
    if (a('aria-label')) partes.push(`${tag}[aria-label='${a('aria-label')}']`);
    if (a('role')) partes.push(`${tag}[role='${a('role')}']`);
    if (el.id) partes.push(`#${el.id}`);
    const t = (el.innerText || '').trim().slice(0, 40);
    if (t && ['button','a','div','span'].includes(tag)) partes.push(`${tag}:has-text('${t.replace(/'/g, "")}')`);
    const ph = a('placeholder') || a('data-placeholder') || a('aria-placeholder');
    if (ph) partes.push(`${tag}[placeholder*='${ph.slice(0, 30)}']`);
    return {tag, id: el.id || null, cls: String(el.className || '').slice(0, 120),
            aria: a('aria-label'), testid: a('data-testid'), role: a('role'),
            name: a('name'), type: a('type'), href: a('href'), placeholder: ph,
            contenteditable: a('contenteditable'), texto: t,
            html: (el.outerHTML || '').slice(0, 800), seletores: partes};
  };
  const alvo = (ev) => {
    let el = ev.target;
    // sobe ate o botao/link/campo mais proximo: o clique costuma cair no svg
    for (let i = 0; i < 6 && el && el.tagName; i++) {
      const tag = el.tagName.toLowerCase();
      if (['button','a','textarea','input','select'].includes(tag)
          || el.getAttribute('role') || el.getAttribute('contenteditable') === 'true'
          || el.getAttribute('data-testid')) break;
      el = el.parentElement;
    }
    return el || ev.target;
  };
  const guardar = (tipo, ev, extra) => {
    try {
      window.__guia.push({t: Date.now(), tipo, url: location.href,
                          el: desc(alvo(ev)), ...(extra || {})});
      if (window.__guia.length > 400) window.__guia.splice(0, 100);
    } catch (e) {}
  };
  document.addEventListener('click', (ev) => guardar('click', ev), true);
  document.addEventListener('focusin', (ev) => guardar('focus', ev), true);
  document.addEventListener('change', (ev) => guardar('change', ev,
      {files: ev.target && ev.target.files ? ev.target.files.length : null}), true);
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' || (ev.ctrlKey && ev.key.toLowerCase() === 'v'))
      guardar('tecla', ev, {tecla: ev.key, ctrl: ev.ctrlKey, shift: ev.shiftKey});
  }, true);
  window.__guia_desc = desc;
  return true;
}"""
JS_COLHER = ("() => { const e = window.__guia || []; window.__guia = [];"
             " const a = document.activeElement;"
             " return {eventos: e, ativo: (window.__guia_desc ? window.__guia_desc(a) : null),"
             " url: location.href, titulo: document.title}; }")


# ------------------------------------------------------------- a janela
def _hwnd_por_titulo(trecho: str) -> int:
    """O HWND da janela de nivel mais alto cujo titulo contem `trecho`."""
    user32 = ctypes.windll.user32
    achado = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cada(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        tamanho = user32.GetWindowTextLengthW(hwnd)
        if tamanho <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(tamanho + 1)
        user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
        if trecho.lower() in buffer.value.lower() and "chrome" in buffer.value.lower():
            achado.append(hwnd)
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(_cada), 0)
    return achado[0] if achado else 0


def _trazer_para_frente(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    SW_MAXIMIZE = 3
    try:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        user32.SetForegroundWindow(hwnd)
    except Exception:                                          # noqa: BLE001
        pass


def _fotografar_janela(hwnd: int):
    """A janela como imagem PIL, por PrintWindow (painel/flutuante/captura)."""
    from painel.flutuante import captura as cap
    from PIL import Image

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    caixa = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(caixa))
    largura, altura = caixa.right - caixa.left, caixa.bottom - caixa.top
    if largura <= 0 or altura <= 0:
        return None
    tela = user32.GetDC(hwnd)
    memoria = gdi32.CreateCompatibleDC(tela)
    bitmap = gdi32.CreateCompatibleBitmap(tela, largura, altura)
    antigo = gdi32.SelectObject(memoria, bitmap)
    try:
        user32.PrintWindow(hwnd, memoria, cap.PW_RENDERFULLCONTENT)
        cabeca = cap._BITMAPINFOHEADER()
        cabeca.biSize = ctypes.sizeof(cap._BITMAPINFOHEADER)
        cabeca.biWidth, cabeca.biHeight = largura, -altura
        cabeca.biPlanes, cabeca.biBitCount = 1, 32
        buffer = ctypes.create_string_buffer(largura * altura * 4)
        gdi32.GetDIBits(memoria, bitmap, 0, altura, buffer, ctypes.byref(cabeca), 0)
        return Image.frombuffer("RGBA", (largura, altura), buffer.raw,
                                "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32.SelectObject(memoria, antigo)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memoria)
        user32.ReleaseDC(hwnd, tela)


# ------------------------------------------------------------- arquivos
def _carimbo() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def escrever_atual(ia: str, passo: str) -> None:
    ATUAL.parent.mkdir(parents=True, exist_ok=True)
    ATUAL.write_text(json.dumps({"ia": ia, "passo": passo,
                                 "desde": fichas.agora()}, ensure_ascii=False,
                                indent=2), encoding="utf-8")


def _anexar_linha(arquivo: Path, dados: dict) -> None:
    with open(arquivo, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dados, ensure_ascii=False) + "\n")


def ler_colado(arquivo: Path, desde: int = 0) -> tuple:
    """(linhas novas, quantas linhas o arquivo tem agora)."""
    try:
        with open(arquivo, encoding="utf-8", errors="replace") as fh:
            linhas = fh.readlines()
    except OSError:
        return [], desde
    novas = []
    for bruta in linhas[desde:]:
        bruta = bruta.strip()
        if not bruta:
            continue
        try:
            item = json.loads(bruta)
        except ValueError:
            continue
        if isinstance(item, dict):
            novas.append(item)
    return novas, len(linhas)


def _ler_comando(arquivo: Path) -> dict | None:
    try:
        texto = arquivo.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    try:
        arquivo.unlink()
    except OSError:
        pass
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    return dados if isinstance(dados, dict) else None


def avisar(texto: str, log=print) -> bool:
    """Telegram (todos os autorizados) + relato no orquestrador. Nunca levanta."""
    entregue = False
    try:
        from remoto import config
        from remoto.api import Telegram
        tg = Telegram(config.token())
        for chat in config.carregar().get("autorizados") or []:
            try:
                tg.mensagem(chat, texto)
                entregue = True
            except Exception as exc:                           # noqa: BLE001
                log(f"[guia] telegram {chat}: {exc}")
    except Exception as exc:                                   # noqa: BLE001
        log(f"[guia] telegram indisponivel: {exc}")
    try:
        from remoto import orquestrador
        orquestrador.relato("7ce009d4", texto[:300])
    except Exception as exc:                                   # noqa: BLE001
        log(f"[guia] relato: {exc}")
    return entregue


def mensagem_de_abertura(ia: str) -> str:
    nome = TITULOS.get(ia, ia)
    return (f"{nome} aberto na tela. Me mostre: (1) onde escreve, (2) como manda, "
            "(3) onde a resposta aparece, (4) onde troca de modelo, (5) como anexa "
            "imagem, (6) onde gera imagem, (7) o que aparece quando a cota acaba. "
            "Faça cada ação na tela, devagar, e diga 'próximo' (aqui ou na janela "
            "flutuante) quando terminar cada passo.")


# -------------------------------------------------------------- a sessao
def _perfil(ia: str) -> Path:
    import builds.contas as contas
    canal = "geral" if ia in ("grok", "gemini", "chatgpt", "deepseek") else (
        "historias" if ia in ("picasso", "dreamface") else "builds")
    return contas.perfil(ia, canal)


def _testar_ok(ia: str, page, pasta: Path, log) -> dict:
    """Passo 4: digita PEDIDO_OK com os seletores de `seletores.py` e le."""
    import importlib
    from contos.llm import cliente as cli, seletores as sel
    importlib.reload(sel)
    resultado = {"ok": False, "tempo_s": None, "resposta": "", "erro": ""}
    try:
        cliente = cli.ClienteLLM(ia, None, page, {"resposta_timeout": 180}, log=log)
        t0 = time.monotonic()
        cliente.enviar(PEDIDO_OK)
        texto = cliente.esperar_resposta(180, estabilidade=2.0)
        resultado.update({"ok": bool(texto.strip()), "tempo_s": round(time.monotonic() - t0, 1),
                          "resposta": texto[:300]})
    except Exception as exc:                                   # noqa: BLE001
        resultado["erro"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    _anexar_linha(pasta / "testes.jsonl", {"em": fichas.agora(), "teste": "ok", **resultado})
    return resultado


def rodar(ia: str, *, log=print, limite_min: float = 240.0) -> dict:
    import builds.travas as travas
    from builds.identity import browser

    ia = str(ia).lower()
    pasta = PASTA_PROVAS / ia / "guia"
    pasta.mkdir(parents=True, exist_ok=True)
    colado = pasta / "colado.jsonl"
    comando = pasta / "comando.json"
    eventos = pasta / "eventos.jsonl"
    perfil = _perfil(ia)
    nome_trava = travas.do_perfil(ia, "geral" if ia in ("grok", "gemini", "chatgpt", "deepseek")
                                  else "historias" if ia in ("picasso", "dreamface") else "builds")
    resumo = {"ia": ia, "inicio": fichas.agora(), "passos": {}, "colados": 0,
              "eventos": 0, "capturas": 0, "fim": None}
    passo_n = 0
    escrever_atual(ia, PASSOS[0])
    _anexar_linha(eventos, {"em": fichas.agora(), "tipo": "passo", "passo": PASSOS[0]})

    with travas.trava(nome_trava, esperar=30.0) as minha:
        if not minha:
            avisar(f"Não consegui abrir o {TITULOS.get(ia, ia)}: a conta está em uso "
                   f"por outro processo ({nome_trava}). Tento de novo quando soltar.", log)
            return resumo
        with browser.contexto_persistente(headless=False, profile=perfil, esperar=30.0) as ctx:
            page = browser.pagina(ctx)
            page.goto(URLS[ia], wait_until="domcontentloaded", timeout=90_000)
            time.sleep(4.0)
            hwnd = 0
            for _ in range(10):
                hwnd = _hwnd_por_titulo(TITULOS.get(ia, ia))
                if hwnd:
                    break
                time.sleep(1.0)
            if hwnd:
                _trazer_para_frente(hwnd)
            log(f"[guia] {ia}: janela {'#%x' % hwnd if hwnd else 'NAO achada pelo titulo'}; url {page.url}")
            avisar(mensagem_de_abertura(ia), log)

            lidas = 0
            ultimo_hash_pagina = ultimo_hash_janela = ""
            ultimo_proximo = time.monotonic()
            lembrado = False
            fim = time.monotonic() + limite_min * 60
            rng = random.Random()
            while time.monotonic() < fim:
                inicio_volta = time.monotonic()
                # 1) o gancho de eventos, nesta pagina (re-instala apos navegar)
                try:
                    page.evaluate(JS_INSTALAR)
                    colhido = page.evaluate(JS_COLHER) or {}
                except Exception as exc:                       # noqa: BLE001
                    colhido = {"erro": f"{type(exc).__name__}"}
                    if "closed" in str(exc).lower() or page.is_closed():
                        log("[guia] a janela foi fechada por ele; encerro.")
                        break
                for ev in colhido.get("eventos") or []:
                    _anexar_linha(eventos, {"em": fichas.agora(), "passo": PASSOS[passo_n],
                                            **ev})
                    resumo["eventos"] += 1
                # 2) capturas: pagina (render do Chrome) e janela (PrintWindow),
                #    so quando mudou — 2 s por 4 h daria 7 mil arquivos iguais.
                carimbo = _carimbo()
                try:
                    png = page.screenshot()
                    h = hashlib.sha1(png).hexdigest()
                    if h != ultimo_hash_pagina:
                        (pasta / f"{carimbo}_pagina.png").write_bytes(png)
                        ultimo_hash_pagina = h
                        resumo["capturas"] += 1
                except Exception:                              # noqa: BLE001
                    pass
                if hwnd:
                    try:
                        imagem = _fotografar_janela(hwnd)
                        if imagem is not None:
                            h = hashlib.sha1(imagem.tobytes()[::97]).hexdigest()
                            if h != ultimo_hash_janela:
                                imagem.save(pasta / f"{carimbo}_janela.png")
                                ultimo_hash_janela = h
                    except Exception:                          # noqa: BLE001
                        pass
                _anexar_linha(eventos, {"em": fichas.agora(), "tipo": "tick",
                                        "passo": PASSOS[passo_n], "url": colhido.get("url"),
                                        "titulo": colhido.get("titulo"),
                                        "ativo": colhido.get("ativo")})
                # 3) o que ele colou na janela flutuante
                novas, lidas = ler_colado(colado, lidas)
                for item in novas:
                    resumo["colados"] += 1
                    papel = str(item.get("papel") or "")
                    log(f"[guia] colado: {papel}: {str(item.get('previa') or item.get('conteudo') or '')[:80]}")
                    if papel == "proximo":
                        resumo["passos"][PASSOS[passo_n]] = fichas.agora()
                        ultimo_proximo = time.monotonic()
                        lembrado = False
                        if passo_n + 1 >= len(PASSOS):
                            log("[guia] ultimo passo concluido; fico com a janela aberta "
                                "esperando comandos (testar_ok / fechar).")
                            escrever_atual(ia, "concluido; testes na mesma sessao")
                        else:
                            passo_n += 1
                            escrever_atual(ia, PASSOS[passo_n])
                            _anexar_linha(eventos, {"em": fichas.agora(), "tipo": "passo",
                                                    "passo": PASSOS[passo_n]})
                    elif papel == "erro_cota":
                        ficha = fichas.carregar(ia)
                        ficha["catalogo_textos"] = catalogo.juntar(ficha["catalogo_textos"], [
                            catalogo.item(catalogo.classificar(item.get("conteudo") or "") or "limite",
                                          str(item.get("conteudo") or item.get("previa") or ""),
                                          seletor=item.get("seletor_sugerido"), fonte="adrian",
                                          visto_em=fichas.agora(), nota="colado por ele na sessao guiada")])
                        fichas.salvar(ficha)
                # 4) comandos desta sessao de agente
                cmd = _ler_comando(comando)
                if cmd:
                    acao = str(cmd.get("acao") or "")
                    log(f"[guia] comando: {acao}")
                    if acao == "fechar":
                        avisar(cmd.get("texto") or f"Vou fechar a janela do {TITULOS.get(ia, ia)} "
                               "agora (terminei de gravar). Obrigado.", log)
                        time.sleep(float(cmd.get("espera_s", 20)))
                        break
                    if acao == "avisar":
                        avisar(str(cmd.get("texto") or ""), log)
                    if acao == "passo":
                        nome = str(cmd.get("passo") or "")
                        if nome in PASSOS:
                            passo_n = PASSOS.index(nome)
                            escrever_atual(ia, nome)
                    if acao == "testar_ok":
                        resultado = _testar_ok(ia, page, pasta, log)
                        log(f"[guia] teste OK: {resultado}")
                        avisar(f"Testei o seletor no {TITULOS.get(ia, ia)}: "
                               + (f"resposta em {resultado['tempo_s']}s: {resultado['resposta'][:80]!r}"
                                  if resultado["ok"] else f"falhou: {resultado['erro']}"), log)
                    if acao == "js":
                        try:
                            saida = page.evaluate(str(cmd.get("codigo") or "() => null"))
                        except Exception as exc:               # noqa: BLE001
                            saida = f"{type(exc).__name__}: {str(exc)[:300]}"
                        (pasta / "js_resultado.json").write_text(
                            json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                            encoding="utf-8")
                # 5) 15 min sem "proximo": lembra UMA vez, nao segue sozinho
                if (not lembrado and time.monotonic() - ultimo_proximo > LEMBRETE_APOS_S):
                    lembrado = True
                    avisar(f"Continuo com o {TITULOS.get(ia, ia)} aberto na tela, no passo "
                           f"'{PASSOS[passo_n]}'. Quando puder, siga e diga 'próximo'.", log)
                gasto = time.monotonic() - inicio_volta
                if gasto < INTERVALO_S:
                    time.sleep(INTERVALO_S - gasto + rng.uniform(0, 0.2))
            _pausa(rng, 0.5, 1.0)
    resumo["fim"] = fichas.agora()
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return resumo


def resumir_eventos(ia: str) -> list:
    """Os cliques/focos gravados, por passo, com os seletores sugeridos."""
    pasta = PASTA_PROVAS / ia / "guia"
    saida = []
    try:
        with open(pasta / "eventos.jsonl", encoding="utf-8", errors="replace") as fh:
            for linha in fh:
                try:
                    ev = json.loads(linha)
                except ValueError:
                    continue
                if ev.get("tipo") in ("click", "focus", "change", "tecla") and ev.get("el"):
                    el = ev["el"]
                    saida.append({"em": ev.get("em"), "passo": ev.get("passo"),
                                  "tipo": ev["tipo"], "tag": el.get("tag"),
                                  "aria": el.get("aria"), "testid": el.get("testid"),
                                  "texto": (el.get("texto") or "")[:40],
                                  "seletores": el.get("seletores"),
                                  "url": ev.get("url")})
    except OSError:
        pass
    return saida


_ = (re, os)
