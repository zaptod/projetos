"""Descoberta de seletores: abre a pagina e despeja o que existe na tela.

Estes sites sao SPAs com classes geradas por build — nao da para adivinhar o
DOM de fora, e ele muda a cada deploy. Este comando e a ferramenta de
manutencao: roda, olha o JSON, atualiza a lista de seletores. Nenhum outro
arquivo muda.

Serve para DOIS casos:

  `probe`                    o Digen logado, conferindo os seletores conhecidos.
  `probe --url <URL>`        QUALQUER pagina, sem depender de seletor nenhum.
                             E o caminho para um site que o projeto ainda nao
                             conhece: nao ha o que conferir, so o que descobrir.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, selectors, session
from .browser import contexto_persistente, pagina, pausa_humana

# Coleta em UMA passada no DOM: um round-trip de CDP em vez de centenas.
JS_COLETA = """() => {
  const visivel = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const attrs = (e, lista) => Object.fromEntries(
    lista.map(a => [a, e.getAttribute(a)]).filter(([, v]) => v));
  const pega = (sel, fn) =>
    Array.from(document.querySelectorAll(sel)).filter(visivel).map(fn);

  return {
    url: location.href,
    title: document.title,
    entradas: pega('input, textarea', e => ({
      tag: e.tagName.toLowerCase(),
      ...attrs(e, ['type', 'name', 'id', 'placeholder', 'aria-label',
                   'data-testid', 'role']),
    })),

    // <select> SEM filtro de visibilidade, e com as opcoes. O controle pode
    // ser um select nativo escondido atras de um botao estilizado — foi o
    // caso da proporcao no PicassoIA, e como `pega()` filtra por visibilidade
    // ele nao aparecia em lugar nenhum do despejo. Opcao de select nunca e
    // "visivel" para o Playwright: quem mexe nela e `select_option`, nao
    // clique.
    selects: Array.from(document.querySelectorAll('select')).map(e => ({
      ...attrs(e, ['name', 'id', 'aria-label', 'data-testid', 'class']),
      escondido: !(e.getBoundingClientRect().width > 0),
      valor: e.value,
      opcoes: Array.from(e.options).map(o => o.value).slice(0, 30),
    })),
    botoes: pega('button, [role=button], a[href]', e => {
      // O `d` do icone e a ancora que este projeto usa para botao sem texto
      // (download, modelo, anexo). Sem ele no despejo, um botao mudo aparece
      // aqui como uma linha vazia e nao da para escrever seletor nenhum.
      const path = e.querySelector('svg path');
      return {
        tag: e.tagName.toLowerCase(),
        texto: (e.innerText || '').trim().slice(0, 60),
        icone: path ? (path.getAttribute('d') || '').slice(0, 46) : null,
        ...attrs(e, ['type', 'aria-label', 'data-testid', 'data-slot',
                     'aria-haspopup', 'href', 'download']),
      };
    }).filter(b => b.texto || b['aria-label'] || b.download || b.icone),

    // TODO input de arquivo, VISIVEL OU NAO. O filtro de visibilidade
    // descartaria justamente o caso normal: num composer assim o input e
    // `display:none` e quem aparece e o botao que o aciona. E e nele que
    // `set_input_files` funciona, sem precisar clicar em nada.
    arquivos: Array.from(document.querySelectorAll('input[type=file]')).map(e => ({
      ...attrs(e, ['name', 'id', 'accept', 'multiple', 'data-testid', 'class']),
      escondido: !(e.getBoundingClientRect().width > 0),
      perto_de: (() => {
        let no = e.parentElement, saltos = 0;
        while (no && saltos++ < 5) {
          const texto = (no.innerText || '').trim();
          if (texto) return texto.slice(0, 60);
          no = no.parentElement;
        }
        return null;
      })(),
    })),
    videos: pega('video', e => ({
      src: e.getAttribute('src'),
      filho: (e.querySelector('source') || {}).src || null,
      duracao: e.duration || null,
    })),
    testids: [...new Set(Array.from(
      document.querySelectorAll('[data-testid]'))
      .map(e => e.getAttribute('data-testid')))].slice(0, 80),
  };
}"""


def coletar(page, sel=selectors) -> dict:
    """Despeja a tela. Com `sel=None`, so DESCOBRE — nao confere nada.

    Site que o projeto ainda nao conhece nao tem lista para conferir, e rodar
    os candidatos do Digen contra ele so produziria uma coluna de "--" sem
    significado nenhum.
    """
    dados = page.evaluate(JS_COLETA)
    if sel is None:
        dados["candidatos"] = {}
        return dados
    # Confere quais candidatos do selectors.py ainda casam nesta tela.
    dados["candidatos"] = {
        nome: bool(selectors.encontrar(page, lista, timeout=0.8))
        for nome, lista in (
            ("SESSAO_VIVA", selectors.SESSAO_VIVA),
            ("TELA_LOGIN", selectors.TELA_LOGIN),
            ("CAMPO_PROMPT", selectors.CAMPO_PROMPT),
            ("BOTAO_GERAR", selectors.BOTAO_GERAR),
            ("VIDEO_PRONTO", selectors.VIDEO_PRONTO),
            ("BOTAO_DOWNLOAD", selectors.BOTAO_DOWNLOAD),
            ("DESAFIO", selectors.DESAFIO),
            ("BOTAO_ANEXO", selectors.BOTAO_ANEXO),
        )
    }
    # A pergunta que decide o anexo de referencia: existe input de arquivo
    # nesta tela, mesmo escondido?
    dados["candidatos"]["ENTRADA_ARQUIVO"] = bool(
        selectors.entrada_de_arquivo(page))
    return dados


def _esperar_voce(segundos: float) -> None:
    """Janela para logar e navegar ate a tela certa, com a janela aberta.

    Nao usa `input()` de proposito: o probe tambem e disparado pelo painel, e
    la nao ha console para responder — o processo ficaria pendurado para
    sempre esperando um Enter que ninguem pode dar.
    """
    print("")
    print("=" * 68)
    print(f"  A JANELA ESTA ABERTA. Voce tem {segundos:.0f}s para:")
    print("    1. fazer login, se ele pedir;")
    print("    2. deixar na tela EXATA que interessa (o criador, com o")
    print("       composer visivel);")
    print("    3. abrir o menu/popover que voce quer que eu enxergue, se for")
    print("       o caso — o despejo fotografa o DOM como ele estiver.")
    print("  Nao feche a janela: eu fecho.")
    print("=" * 68)
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        restante = fim - time.monotonic()
        print(f"[probe] despejo em {restante:.0f}s...", flush=True)
        time.sleep(min(15.0, max(1.0, restante)))


def run(headless: bool = False, url: str | None = None,
        provedor: str | None = None, esperar: float = 0.0) -> Path:
    ajustes = config.settings()
    config.IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    nome = provedor or (config.PADRAO if url is None else "site")
    destino = config.IDENTITY_DIR / f"probe_{nome}_{carimbo}.json"
    conhecido = url is None

    with contexto_persistente(headless=headless,
                              profile=config.profile_dir(provedor)) as ctx:
        page = pagina(ctx)
        if conhecido:
            session.ensure_logged_in(page, ajustes)
            page.goto(selectors.URL_SPACES, wait_until="domcontentloaded")
        else:
            page.goto(url, wait_until="domcontentloaded",
                      timeout=int(float(ajustes.get("navigation_timeout", 60)) * 1000))
        pausa_humana()
        if esperar > 0:
            _esperar_voce(esperar)
        dados = coletar(page, selectors if conhecido else None)
        dados["provedor"] = nome
        (config.IDENTITY_DIR / f"probe_{nome}_{carimbo}.html").write_text(
            page.content(), encoding="utf-8")

    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)

    print(f"[probe] {destino}")
    print(f"[probe] {len(dados['entradas'])} entradas, "
          f"{len(dados['botoes'])} botoes, {len(dados['videos'])} videos, "
          f"{len(dados['arquivos'])} input(s) de arquivo, "
          f"{len(dados['selects'])} select(s)")
    for select in dados["selects"]:
        print(f"[probe]   select: id={select.get('id')!r} "
              f"name={select.get('name')!r} valor={select.get('valor')!r} "
              f"opcoes={select.get('opcoes')}")
    for arquivo in dados["arquivos"]:
        print(f"[probe]   arquivo: accept={arquivo.get('accept')!r} "
              f"multiple={arquivo.get('multiple')!r} "
              f"escondido={arquivo.get('escondido')} "
              f"perto de {str(arquivo.get('perto_de'))[:40]!r}")
    for nome, achou in dados["candidatos"].items():
        print(f"[probe]   {'OK ' if achou else '-- '} {nome}")
    return destino
