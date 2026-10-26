# -*- coding: utf-8 -*-
"""Publicar no TikTok por automação de navegador (patchright).

Diferente do YouTube, aqui NÃO existe caminho oficial disponível: a Content
Posting API do TikTok exige app aprovado em review. Sobra o navegador — o
mesmo padrão que o projeto já usa no PicassoIA e no Digen: Chrome de verdade,
perfil persistente (login feito UMA vez, na mão) e nenhum truque de stealth
além do que `identity/browser.py` já faz.

Duas consequências que valem estar escritas:

  1. É automação da SUA conta, no site deles, e pode quebrar quando o TikTok
     mudar a tela. Por isso o `sondar()`: ele despeja o DOM da página de
     upload para ajustar os seletores, como o `identity probe` faz.
  2. Por padrão a ferramenta NÃO clica em "Publicar". Ela sobe o arquivo,
     escreve a legenda e PARA com a janela aberta — publicar é irreversível e
     a última palavra é sua. Quem posta passa `postar=True` explícito (a
     grade, `main.py publicar --postar`). A chave `tiktok.postar_automatico`
     do config SAIU em 14/10/2026 (decisão `publicacao/tiktok-postar-
     automatico`): a grade sempre a ignorou, e mudar ela não mudava nada.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from .. import atividade
from ..identity.browser import (AberturaFalhou, abrir_pagina,
                                contexto_persistente, ir_para, pagina)
from . import audio, desfecho, escrita

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = RAIZ / ".browser_profile" / "tiktok"

# Quanto esperar a tela de login montar antes de acusar o perfil de
# degradado. A home do TikTok e pesada: com 6 s a checagem acusava
# pagina que so estava lenta (medido em 31/08/2026).
PACIENCIA_LOGIN_S = 40


def perfil_da_conta(canal: str = "builds"):
    """A pasta de Chrome da conta de TikTok ATIVA naquele canal.

    Existe porque os canais deixaram de compartilhar conta: publicar a
    historia no perfil do canal de builds e irreversivel.
    """
    try:
        from ..contas import perfil
        return perfil("tiktok", canal)
    except Exception:
        return PERFIL


def _conta_ativa(canal: str) -> str:
    """Qual conta de TikTok está publicando — nunca levanta."""
    try:
        from ..contas import ativa
        return str(ativa("tiktok", canal))
    except Exception:
        return ""


URL_UPLOAD = "https://www.tiktok.com/tiktokstudio/upload"

# Espera o input de arquivo aparecer (a página é uma SPA pesada).
ESPERA_PAGINA_S = 60.0
# Depois de entregar o arquivo, o TikTok processa e só então habilita a
# legenda e o botão. Sem confirmação visual não dá para dizer que subiu.
ESPERA_PROCESSAR_S = 300.0

ENTRADA_ARQUIVO = 'input[type="file"]'
# A legenda é um contenteditable (não textarea). Os candidatos vão do mais
# específico ao mais genérico — o primeiro que existir na tela vale.
CAMPO_LEGENDA = (
    'div[contenteditable="true"][role="combobox"]',
    'div[contenteditable="true"]',
    '[data-e2e="caption-input"]',
)
BOTAO_POSTAR = (
    'button[data-e2e="post_video_button"]',
    'button:has-text("Publicar")',
    'button:has-text("Post")',
)
# A SEGUNDA confirmação. O TikTok abre um modal "Publicar agora" quando o
# fluxo vai rápido demais (relatado pelo Adrian em 31/08/2026, com o DOM:
# `<div class="TUXButton-label">Publicar agora</div>`). Sem clicar aqui, o
# vídeo NÃO sobe — e a automação achava que tinha publicado.
#
# O rótulo é um `div` DENTRO do botão (design system TUX), então o seletor
# precisa pegar o botão ancestral; clicar no rótulo também funciona porque o
# clique sobe, e por isso os dois estão na lista.
BOTAO_CONFIRMAR = (
    '[data-e2e="post_video_confirm"]',
    'button:has-text("Publicar agora")',
    'button:has-text("Post now")',
    'div.TUXButton-label:has-text("Publicar agora")',
    'div.TUXButton-label:has-text("Post now")',
)

# O que prova que o vídeo foi mesmo publicado. Nenhum destes é garantido
# sozinho, por isso são vários — e por isso, quando NENHUM aparece, a função
# diz que não conseguiu confirmar em vez de inventar sucesso.
SINAIS_DE_SUCESSO = (
    "seu video esta sendo enviado", "seu video foi publicado",
    "video publicado", "publicado com sucesso",
    "gerenciar publicacoes", "gerenciar posts", "seus videos",
    "your video is being uploaded", "your video has been posted",
    "video published", "posted successfully",
    "manage your posts", "your videos", "view profile", "ver perfil",
)
ESPERA_CONFIRMAR_S = 90.0

# Toda frase de sucesso comeca com isto, e `confirmado()` e como quem chama
# pergunta. Sem um marcador, o chamador teria que adivinhar pelo texto — e
# `serie.py` registrava como publicado QUALQUER coisa que voltasse, inclusive
# um "nao consegui confirmar".
SUCESSO = "publicado no TikTok"


def confirmado(estado: str) -> bool:
    """O TikTok confirmou a publicacao? (a unica pergunta que vale)"""
    return str(estado or "").startswith(SUCESSO)


# A ÚNICA prova de que dá para postar: o botão existe E está habilitado.
#
# Isto já foi uma lista de três, com `div[class*="preview"] video` e `video`
# junto — e `_primeiro` devolve o primeiro que casar. O `<video>` do preview
# nasce assim que o arquivo chega, muito antes de o TikTok terminar de
# processar, então a espera de 300 s saía em poucos segundos e o clique caía
# num botão ainda desabilitado. O Playwright então esperava ele habilitar
# com o timeout PADRÃO (30 s) e estourava.
#
# Medido em 11/09/2026, 12:09: `duelo_00001` subiu no YouTube e ficou fora do
# TikTok exatamente assim, com 300 s de orçamento intactos e um erro que
# dizia "Timeout 30000ms" — o número que não era de ninguém.
PROVA_DE_PRONTO = 'button[data-e2e="post_video_button"]:not([disabled])'
# Estes dizem só que o arquivo CHEGOU. Servem para não desistir calado
# quando o TikTok troca o `data-e2e` do botão, e para nada mais.
SINAIS_DE_PROGRESSO = (
    'div[class*="preview"] video',
    'video',
)
# Quanto esperar o botão habilitar no momento do clique. O padrão do
# Playwright são 30 s, e o processamento do TikTok passa disso com folga.
ESPERA_HABILITAR_S = 120.0


class TikTokFalhou(RuntimeError):
    """Erro legível — o painel mostra a frase, não o traceback."""


def _primeiro(page, seletores, timeout: float = 5.0):
    """O primeiro seletor que casa, ou None. Nunca levanta."""
    for seletor in seletores:
        try:
            alvo = page.locator(seletor).first
            alvo.wait_for(state="visible", timeout=int(timeout * 1000))
            return alvo
        except Exception:
            continue
    return None


def _sem_acento(texto: str) -> str:
    """Minusculas, sem acento e com a LARGURA CHEIA dobrada para a comum.

    O NFKC vem antes do NFD (05/10/2026): o TikTok escreve "Enviado （60.85MB）"
    com o parentese de largura cheia (U+FF08), que o NFD sozinho mantem — e o
    sinal "enviado (" nunca casava.
    """
    import unicodedata
    texto = unicodedata.normalize("NFKC", str(texto or ""))
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower()


def _publicou(page, url_antes: str) -> bool:
    """Ha PROVA de que o video foi publicado? (nunca 'provavelmente')"""
    try:
        url = page.url
        if url != url_antes and "/upload" not in url:
            return True
        texto = _sem_acento(page.evaluate(
            "() => document.body ? document.body.innerText : ''"))
    except Exception:
        return False
    return any(sinal in texto for sinal in SINAIS_DE_SUCESSO)


# OS AVISOS DE CONTA NOVA (26/10/2026). O 1o upload de uma conta abre, um atras
# do outro, dialogos e cartoes por cima do formulario ("Ativar verificacoes
# automaticas de conteudo?", depois um cartao do editor de video no canto):
# a legenda fica coberta e estoura TimeoutError 3x (telas `20261026_102335` e
# `20261026_105433`). A regra e GENERICA: enquanto houver sobreposicao (role=
# dialog, aria-modal ou mascara de fundo) fecha-se pelo botao de DISPENSA, rolando
# ate ele, ou com Escape — ate `RODADAS_DE_AVISO` vezes, com uma captura de cada
# um para o registro. NUNCA se clica em botao que ATIVE algo na conta
# (`BOTOES_PROIBIDOS`: ativar, ligar, aceitar, permitir, publicar...).
RODADAS_DE_AVISO = 5
BOTOES_DE_DISPENSA = ("cancelar", "cancel", "entendi", "got it", "ok",
                      "agora nao", "not now", "fechar", "close", "dispensar",
                      "dismiss", "pular", "skip", "nao, obrigado", "no thanks",
                      "mais tarde", "later", "x", "×")
BOTOES_PROIBIDOS = ("ativar", "ligar", "turn on", "enable", "aceitar",
                    "accept", "permitir", "allow", "publicar", "post",
                    "postar", "continuar", "continue", "confirmar", "salvar",
                    "save", "experimentar", "try", "criar", "create")
# `trabalho` (opcional, 3o argumento; o Instagram usa — 26/10/2026): o que marca
# uma caixa como a JANELA DE TRABALHO, que NUNCA se fecha (no Instagram o proprio
# "Criar nova publicacao" e um role=dialog): {seletor, botoes}. Caixa que
# contem o seletor (ex.: input de arquivo) ou um botao com esses rotulos
# (ex.: "avancar") e de trabalho. Sem o 3o argumento nada muda (TikTok).
_JS_AVISO = r"""([dispensa, proibidos, trabalho]) => {
  trabalho = trabalho || {};
  const norm = t => (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .trim().toLowerCase();
  const visivel = e => { const r = e.getBoundingClientRect();
      const c = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && c.visibility !== 'hidden'
          && c.display !== 'none'; };
  const detrabalho = e => {
    if (trabalho.seletor && e.querySelector(trabalho.seletor)) return true;
    const rotulos = trabalho.botoes || [];
    if (!rotulos.length) return false;
    return [...e.querySelectorAll('button,[role=button],a,div')].some(b =>
        b.children.length <= 1 && rotulos.includes(norm(b.innerText || '')));
  };
  const caixas = [...document.querySelectorAll(
      '[role=dialog],[aria-modal=true],[class*=modal i],[class*=Modal],' +
      '[class*=mask i],[class*=overlay i],[class*=popup i],[class*=guide i]')]
      .filter(visivel).filter(e => !detrabalho(e));
  const fixos = caixas.filter(e => {
      const c = getComputedStyle(e); const r = e.getBoundingClientRect();
      return c.position === 'fixed' || e.getAttribute('role') === 'dialog'
          || e.getAttribute('aria-modal') === 'true'
          || (r.width * r.height > innerWidth * innerHeight * 0.5); });
  if (!fixos.length) return {sobreposicao: false};
  const alvos = [];
  for (const caixa of fixos) {
    for (const b of caixa.querySelectorAll(
        'button,[role=button],a,div[class*=close i],span[class*=close i],' +
        'svg')) {
      const el = b.closest('button,[role=button],a') || b;
      const t = norm(el.innerText || el.getAttribute('aria-label') || '');
      alvos.push([el, t]);
    }
  }
  const vistos = alvos.map(a => a[1]).filter(t => t).slice(0, 12);
  for (const [el, t] of alvos) {
    const rotulo = t || norm(el.getAttribute('aria-label') || '');
    if (!rotulo && !/close|fechar/i.test(el.className || '')) continue;
    if (proibidos.some(p => rotulo === p || rotulo.split(/\s+/).includes(p)))
      continue;
    if (dispensa.includes(rotulo) || /close|fechar/i.test(
        (el.className && el.className.baseVal === undefined
         ? el.className : '') + ' ' + (el.getAttribute('aria-label') || ''))) {
      el.scrollIntoView({block: 'center'});
      el.click();
      return {sobreposicao: true, clicou: rotulo || 'x', vistos};
    }
  }
  for (const caixa of fixos) { caixa.scrollTop = caixa.scrollHeight; }
  return {sobreposicao: true, clicou: '', vistos};
}"""


def _fechar_aviso(page, passo, laudo: dict | None = None, *,
                  prefixo: str = "tiktok", trabalho: dict | None = None,
                  proibidos: tuple = BOTOES_PROIBIDOS) -> str:
    """Fecha o que cobre o formulario. Devolve o que fez ("" = nada). Nunca
    levanta.

    GENERICA, e por isso o Instagram usa a mesma (`prefixo` da captura,
    `trabalho` = o que NAO se fecha, `proibidos` = botoes que nunca se clicam).
    """
    feitos = []
    for rodada in range(1, RODADAS_DE_AVISO + 1):
        try:
            r = page.evaluate(_JS_AVISO, [list(BOTOES_DE_DISPENSA),
                                          list(proibidos),
                                          trabalho or {}])
        except Exception:                                      # noqa: BLE001
            break
        if not isinstance(r, dict) or not r.get("sobreposicao"):
            break
        foto = escrita.fotografar(page, f"{prefixo}_aviso_{rodada}")
        if r.get("clicou"):
            feitos.append(r["clicou"])
            passo(f"aviso {rodada} fechado pelo botao '{r['clicou']}' "
                  f"(captura: {foto or '-'}).")
        else:
            passo(f"aviso {rodada} sem botao de dispensa (botoes vistos: "
                  f"{r.get('vistos')}); tentando Escape (captura: "
                  f"{foto or '-'}).")
            try:
                page.keyboard.press("Escape")
            except Exception:                                  # noqa: BLE001
                pass
            feitos.append("Escape")
        import time as _t
        _t.sleep(1.2)
    if feitos and laudo is not None:
        laudo["avisos_fechados"] = feitos
    return ", ".join(feitos)


def _escrever_legenda(page, texto: str, passo, laudo: dict, *,
                     campos=None, prefixo: str = "tiktok") -> bool:
    """Escreve a legenda, confere que ficou, e tenta DUAS vezes.

    Existe como funcao propria (e nao como um trecho dentro de `publicar`)
    para poder ser testada sem abrir o Chrome. Um teste que reproduzisse este
    laco por fora passaria com a producao quebrada — que e exatamente o
    defeito que ele deveria pegar.

    Grava o resultado em `laudo["legenda"]`, que e o que vai para a ficha e
    para a mensagem do erro: "legenda nao escreveu" e "botao nao habilitou"
    tem conserto diferente e nao podem chegar ao diario como a mesma falha.

    TRES TENTATIVAS desde 05/10/2026 (`MODOS_DA_LEGENDA`): digitada, colada
    e digitada DEVAGAR. As tres com a pausa depois de cada Enter
    (`escrita.PAUSA_DEPOIS_DO_ENTER_S`): o editor do TikTok come o trecho que
    chega colado ao Enter — h34 p06, 00:39 de 05/10, telas `_213926` (o
    paragrafo "Eu escrevo..." foi parar depois das hashtags) e `_213929`
    (sumiu). Nas ultimas 6000 linhas do log: 7 falhas na 1a tentativa e 5
    legendas adiadas.
    """
    ultima = len(MODOS_DA_LEGENDA)
    for tentativa, (modo, ajustes) in enumerate(MODOS_DA_LEGENDA, start=1):
        de_novo = "; tentando de novo." if tentativa < ultima else "."
        campo = _primeiro(page, campos or CAMPO_LEGENDA, timeout=10.0)
        if campo is None:
            laudo["legenda"] = "campo não encontrado"
            passo(f"campo de legenda não encontrado{de_novo}")
            continue
        # A 1a e TECLA A TECLA, o jeito que sempre produziu legenda inteira
        # aqui — mas com o prazo de `escrita` (180 s, conferido entre
        # palavras), e nao os 30 s do `type` para o texto inteiro, que venciam
        # no meio da frase com a maquina ocupada (22 legendas perdidas desde
        # 20/09; o defeito esta medido em `escrita`). A 2a COLA, para quando
        # a maquina esta lenta demais ate para isso.
        #
        # A ORDEM E MEDIDA. Colando primeiro, na rodada das 00:37 de
        # 28/09/2026, a legenda da historia_00031 p06 perdeu dois dos quatro
        # paragrafos: o editor do TikTok come o texto colado quando o Enter
        # chega logo atras (85 de 230 caracteres no contador). No YouTube a
        # colagem saiu identica nas duas publicacoes, conferida pela API.
        #
        # A 3a (05/10/2026) e TECLA A TECLA DEVAGAR, com pausa maior depois
        # do Enter: e a ultima chance antes de adiar o video, entao troca
        # velocidade por folga.
        colar = modo == "colada"
        try:
            escrita.escrever(page, campo, texto, colar=colar, **ajustes)
        except Exception as exc:                               # noqa: BLE001
            laudo["legenda"] = f"falhou: {type(exc).__name__}"
            laudo["tela"] = escrita.fotografar(page, f"{prefixo}_legenda")
            passo(f"não consegui escrever a legenda "
                  f"({type(exc).__name__}){de_novo}")
            continue
        # Escrever sem erro NAO e prova de que o texto ficou la — e a mesma
        # confusao do "botao habilitado". Le o campo de volta.
        estado = _estado_da_legenda(campo, texto)
        if estado != "escrita":
            laudo["legenda"] = estado
            laudo["tela"] = escrita.fotografar(page, f"{prefixo}_legenda")
            passo(f"escrevi a legenda mas ela {estado}{de_novo}")
            continue
        laudo["legenda"] = "escrita"
        laudo["legenda_modo"] = modo
        passo("legenda escrita." if tentativa == 1
              else f"legenda escrita ({tentativa}a tentativa, {modo}).")
        return True
    return False


# As tentativas da legenda, em ordem: (modo, ajustes de `escrita.escrever`).
# "digitada lenta" e o jeito tecla a tecla com 5x o atraso por tecla e uma
# pausa maior depois de cada Enter e da limpeza.
MODOS_DA_LEGENDA = (
    ("digitada", {}),
    ("colada", {}),
    ("digitada lenta", {"atraso_ms": 40, "pausa_s": 0.8}),
)


# A barra do arquivo no topo da tela de upload diz "Enviado (60.85MB)" quando
# o arquivo terminou de subir (telas de 04/10/2026, 21:39). Enquanto sobe, ha
# uma porcentagem. A legenda so e escrita depois disso: o editor e
# re-renderizado quando o envio termina, e texto escrito no meio vai junto.
# O espaco antes do parentese e opcional: o conferente viu na captura
# `20261004_213926` o parentese de largura cheia, que vem com o "espaco" no
# proprio desenho — depois do NFKC ele pode chegar colado ou nao.
SINAIS_DE_ENVIADO = re.compile(
    r"\b(?:enviado|uploaded)\s*\(|upload (?:concluido|complete)")
PALAVRAS_DE_ENVIANDO = ("enviando", "carregando", "uploading")
_PORCENTAGEM = re.compile(r"(?<![\d.,])(\d{1,3})(?:[.,]\d+)?\s*%")
ESPERA_DO_ENVIO_S = 120.0


# ---------------------------------------------------------------- a capa
# So a SERIE do Blue Lock escolhe a capa (26/10/2026): a capa do ep. 1 no
# perfil saiu um quadro do MEIO (~7 s, legenda "de Blue Lock."), e nao o gancho
# "POR QUE ELE PAROU?" do quadro 0. Os duelos e as historias nao passam
# `capa_s` e seguem com a capa que o TikTok escolhe. Melhor esforco: falha de
# capa NUNCA impede a publicacao (o quadro 0 e o padrao do formulario).
BOTAO_EDITAR_CAPA = ("text=/^(Editar capa|Edit cover)$/i",
                     "[data-e2e='edit-cover']")
ABA_CARREGAR_CAPA = ("text=/^(Carregar capa|Upload cover)$/i",
                     "[role='tab']:has-text('Carregar')",
                     "[role='tab']:has-text('Upload')")
BOTAO_CONFIRMAR_CAPA = ("button:has-text('Confirmar')",
                        "button:has-text('Confirm')",
                        "button:has-text('Salvar')",
                        "button:has-text('Save')")
BOTAO_CANCELAR_CAPA = ("button:has-text('Cancelar')",
                       "button:has-text('Cancel')")


def quadro_do_video(caminho, segundos: float = 0.0) -> Path | None:
    """O quadro de `segundos` do mp4, em PNG numa pasta temporaria; `None` se
    nao deu (sem ffmpeg, arquivo ruim). Nunca levanta."""
    import shutil
    import subprocess
    import tempfile
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    destino = Path(tempfile.mkdtemp(prefix="capa_tiktok_")) / "capa.png"
    try:
        subprocess.run(
            [exe, "-y", "-loglevel", "error", "-ss", f"{max(0.0, segundos):.2f}",
             "-i", str(caminho), "-frames:v", "1", str(destino)],
            capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:                                          # noqa: BLE001
        return None
    return destino if destino.is_file() and destino.stat().st_size > 0 else None


def _escolher_capa(page, quadro, passo, laudo: dict) -> bool:
    """Em "Editar capa": envia o `quadro` (PNG) como capa e confirma. Nunca
    levanta; o laudo diz o que houve (`laudo["capa"]`)."""
    def sair(motivo: str) -> bool:
        laudo["capa"] = f"padrao ({motivo})"
        passo(f"capa: ficou a do formulario ({motivo}).")
        cancelar = _primeiro(page, BOTAO_CANCELAR_CAPA, timeout=1.5)
        try:
            if cancelar is not None:
                cancelar.click(timeout=3000)
        except Exception:                                      # noqa: BLE001
            pass
        return False
    try:
        botao = _primeiro(page, BOTAO_EDITAR_CAPA, timeout=8.0)
        if botao is None:
            return sair("sem o botao Editar capa")
        botao.click(timeout=5000)
        aba = _primeiro(page, ABA_CARREGAR_CAPA, timeout=6.0)
        if aba is None:
            return sair("sem a aba Carregar capa")
        aba.click(timeout=5000)
        page.wait_for_timeout(800)
        entrada = page.locator("input[type='file']").last
        entrada.set_input_files(str(quadro), timeout=10000)
        page.wait_for_timeout(2500)
        confirmar = _primeiro(page, BOTAO_CONFIRMAR_CAPA, timeout=6.0)
        if confirmar is None:
            return sair("sem o botao Confirmar")
        confirmar.click(timeout=5000)
        page.wait_for_timeout(2000)
        laudo["capa"] = "enviada"
        passo("capa: quadro escolhido enviado e confirmado.")
        return True
    except Exception as exc:                                   # noqa: BLE001
        return sair(f"{type(exc).__name__}")



def _envio_concluido(page) -> bool | None:
    """O arquivo terminou de subir? True, False, ou None quando a tela nao diz.

    Nunca levanta. `None` NAO e "nao": quem espera segue em frente, porque
    trocar uma leitura que falhou por um horario perdido e o erro caro.
    """
    try:
        texto = _sem_acento(page.evaluate(
            "() => document.body ? document.body.innerText : ''"))
    except Exception:                                          # noqa: BLE001
        return None
    if SINAIS_DE_ENVIADO.search(texto):
        return True
    # A porcentagem so conta junto da palavra do envio: um "0%" qualquer da
    # tela (verificacao de direitos, por exemplo) seguraria toda legenda.
    if not any(palavra in texto for palavra in PALAVRAS_DE_ENVIANDO):
        return None
    numeros = [int(n) for n in _PORCENTAGEM.findall(texto)]
    if any(n < 100 for n in numeros):
        return False
    return None


def _esperar_envio(page, passo, espera: float = ESPERA_DO_ENVIO_S,
                   *, dormir=None, relogio=None) -> bool | None:
    """Espera o upload chegar a 100% antes da legenda. Devolve a ultima leitura.

    Sai na hora com True (enviado) ou None (a tela nao diz); so espera
    enquanto ha uma porcentagem abaixo de 100, e no maximo `espera`.
    """
    dormir = dormir or time.sleep
    relogio = relogio or time.monotonic
    fim = relogio() + espera
    avisou = False
    while True:
        estado = _envio_concluido(page)
        if estado is not False:
            return estado
        if relogio() >= fim:
            passo(f"o envio nao chegou a 100% em {espera:.0f}s; escrevo a "
                  "legenda assim mesmo.")
            return False
        if not avisou:
            passo("esperando o envio chegar a 100% antes da legenda...")
            avisou = True
        dormir(2.0)


# A CONFERENCIA MUDOU-SE PARA `escrita` em 27/09/2026, quando o YouTube passou
# a ler o campo de volta tambem. Os nomes daqui ficam como apelido — os testes
# e quem mais os chama continuam valendo —, mas o criterio e UM so: dois
# criterios de "o texto entrou" seriam o mesmo defeito do "publicado" duplo.
_sem_emoji = escrita.sem_emoji
_estado_da_legenda = escrita.estado


def _deve_barrar(postar: bool, texto: str, laudo: dict) -> bool:
    """Publicar agora seria publicar sem legenda?

    Funcao propria para que o teste chame A MESMA decisao que a producao. A
    versao anterior reproduzia esta condicao dentro do teste, e um teste que
    reimplementa a regra passa com a producao quebrada — que e exatamente o
    defeito que ele existe para pegar.

    `postar=False` NUNCA barra: e o modo do painel, em que a janela fica
    aberta para o Adrian conferir e clicar. Ali tem gente na frente da tela, e
    levantar excecao tiraria dele a chance de colar a legenda na mao.
    """
    return bool(postar and texto and laudo.get("legenda") != "escrita")


def _confirmar_publicacao(page, passo, espera: float = ESPERA_CONFIRMAR_S) -> str:
    """Clica "Publicar agora" se o modal aparecer, e so entao confere.

    Antes daqui a funcao dormia 15 s e devolvia "publicado no TikTok" sem
    olhar a tela — uma promessa, nao um fato. Com o modal aberto, o video
    ficava parado e o painel dizia que tinha subido.
    """
    url_antes = page.url
    confirmou = False
    fim = time.time() + espera
    while time.time() < fim:
        # A prova vem ANTES da cacada ao modal: `_primeiro` gasta ate 1 s por
        # seletor e, no fluxo normal (sem modal), isso atrasaria em varios
        # segundos o reconhecimento de um sucesso que ja esta na tela.
        if _publicou(page, url_antes):
            return (SUCESSO
                    + (" (com a confirmacao extra)" if confirmou else ""))
        if not confirmou:
            botao = _primeiro(page, BOTAO_CONFIRMAR, timeout=1.0)
            if botao is not None:
                try:
                    botao.click()
                    confirmou = True
                    passo('o TikTok pediu confirmacao: cliquei em "Publicar '
                          'agora".')
                    time.sleep(2.0)
                    continue
                except Exception as exc:
                    passo(f"achei a confirmacao mas nao consegui clicar "
                          f"({type(exc).__name__}).")
        time.sleep(1.5)

    if confirmou:
        return ("cliquei em publicar e na confirmacao, mas o TikTok nao "
                "mostrou o aviso de sucesso. Confira o perfil antes de "
                "publicar de novo.")
    return ("cliquei em publicar, mas o TikTok nao confirmou. A janela ficou "
            "aberta: confira se o video subiu.")


def _abrir(ctx, url: str):
    """A pagina, com novas tentativas (`browser.abrir_pagina`).

    Desde 05/10/2026: um `goto` de 90 s sem segunda chance perdeu o TikTok do
    23:37 de 04/10 e o das 09:37 de 05/10. Na falha final o erro DIZ que e
    infraestrutura — `desfecho.classificar` nao conta isso contra o video, e
    a rodada sabe que vale tentar de novo.
    """
    try:
        return abrir_pagina(ctx, url,
                            log=lambda t: print(f"[tiktok] {t}", flush=True))
    except AberturaFalhou as exc:
        raise TikTokFalhou(
            f"infraestrutura: a pagina do TikTok nao abriu ({exc})") from exc


def sondar(*, canal: str = "builds", saida: Path | None = None) -> Path:
    """Despeja o DOM da tela de upload (para ajustar seletor quando quebrar).

    Mesmo espírito do `identity probe`: quando o site muda, ninguém adivinha
    o seletor novo — a gente OLHA.
    """
    import json

    saida = saida or (RAIZ / "outputs" / "_identity" /
                      f"probe_tiktok_{time.strftime('%Y%m%d_%H%M%S')}.json")
    saida.parent.mkdir(parents=True, exist_ok=True)
    with contexto_persistente(headless=False, profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_UPLOAD)
        time.sleep(8)
        dados = page.evaluate("""() => ({
            url: location.href,
            titulo: document.title,
            arquivos: Array.from(document.querySelectorAll('input[type=file]'))
                .map(i => ({accept: i.accept, oculto: i.offsetParent === null})),
            editaveis: Array.from(document.querySelectorAll('[contenteditable=true]'))
                .map(e => ({role: e.getAttribute('role'),
                            e2e: e.getAttribute('data-e2e'),
                            texto: (e.innerText || '').slice(0, 40)})),
            botoes: Array.from(document.querySelectorAll('button'))
                .map(b => ({texto: (b.innerText || '').trim().slice(0, 40),
                            e2e: b.getAttribute('data-e2e'),
                            desabilitado: b.disabled}))
                .filter(b => b.texto || b.e2e),
        })""")
        saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        print(f"[tiktok] DOM despejado em {saida}")
        print(f"[tiktok] {len(dados['arquivos'])} input(s) de arquivo, "
              f"{len(dados['editaveis'])} editável(is), "
              f"{len(dados['botoes'])} botão(ões)")
    return saida


def login(*, canal: str = "builds", limpar: bool = False) -> None:
    """Abre a janela para o login manual, e CONSERTA o perfil se preciso.

    Duas coisas que faltavam e custaram uma tarde (31/08/2026):

    1. Se a sessao ja existe, a URL de login redireciona para o feed — a janela
       parecia travada quando na verdade nao havia nada a fazer. Agora isso
       e dito em voz alta.
    2. Um perfil velho de automacao acumula cache e service worker quebrados
       e o TikTok abre BRANCO (so o esqueleto cinza, zero texto). Nao parece
       cache, parece bloqueio. Quando a pagina nao monta, o cache e limpo
       (sem tocar no login) e a janela recarrega sozinha.
    """
    from ..identity.browser import limpar_cache

    perfil = perfil_da_conta(canal)
    if limpar:
        pastas, mb = limpar_cache(perfil)
        print(f"[tiktok] cache do perfil limpo: {len(pastas)} pasta(s), "
              f"{mb} MB. O login foi preservado.")

    if not _janela_de_login(perfil):
        return
    # A pagina nao montou. A limpeza e a segunda janela precisam acontecer
    # FORA do contexto anterior: `sync_playwright` nao pode ser aberto dentro
    # de outro (o erro e "Sync API inside the asyncio loop"), e o cache so
    # pode ser apagado com o Chrome ja fechado.
    if limpar:
        print("[tiktok] a pagina continua sem carregar mesmo com o cache "
              "limpo. Pode ser rede/VPN, ou o site fora do ar.")
        return
    print("[tiktok] a pagina abriu BRANCA (so o esqueleto cinza). Isso e "
          "perfil degradado, nao bloqueio: vou limpar o cache — o login e "
          "preservado — e abrir de novo.")
    time.sleep(1.0)
    login(canal=canal, limpar=True)


def _janela_de_login(perfil: Path) -> bool:
    """A janela do login. Devolve True se a pagina NAO montou (precisa reparo)."""
    from ..identity.browser import montou

    with contexto_persistente(headless=False, visivel=True, profile=perfil) as ctx:
        page = _abrir(ctx, "https://www.tiktok.com/login")

        # Esperar de VERDADE antes de acusar o perfil: a home do TikTok e
        # pesada e leva dezenas de segundos numa maquina ocupada. Seis
        # segundos declaravam "degradado" uma pagina que so estava lenta.
        montada, saiu_do_login = False, False
        fim = time.time() + PACIENCIA_LOGIN_S
        while time.time() < fim:
            time.sleep(2)
            try:
                if "/login" not in page.url:
                    saiu_do_login = True
                    break
                if montou(page, minimo=120):
                    montada = True
                    break
            except Exception:
                break
        if not (montada or saiu_do_login):
            return True

        if saiu_do_login:
            print(f"[tiktok] esta conta JA esta logada (o site foi direto para "
                  f"{page.url}). Nao ha nada a fazer aqui.")
            time.sleep(2)
            return False

        print(f"[tiktok] faça o login nesta janela ({perfil.name}); ela fecha "
              "sozinha em 5 min (ou feche depois de entrar).")
        limite = time.time() + 300
        while time.time() < limite:
            time.sleep(2)
            try:
                # O COOKIE VEM ANTES DA URL, e e o conserto de 15/09/2026. A
                # conta `zombie_surviv0rs` entrou de verdade — o titulo da
                # janela ja dizia "zombie_surviv0rs (@zombie_surviv0rs)" — e
                # mesmo assim o laco imprimiu "tempo esgotado sem login" e o
                # cadastro ficou sem identidade. `pagina(ctx)` e a PRIMEIRA
                # aba; o login acontecendo em outra deixa a primeira parada em
                # /login para sempre. O cookie e do contexto inteiro: nao
                # depende de em qual aba ele entrou.
                if _tem_sessao(ctx) or "login" not in pagina(ctx).url:
                    print(f"[tiktok] sessão iniciada; perfil salvo em {perfil}")
                    time.sleep(3)
                    return False
            except Exception:
                return False
        print("[tiktok] tempo esgotado sem login.")
        return False


# Os cookies que o TikTok grava quando a sessao vale. Basta um: `sessionid` e
# o principal, e `sid_tt`/`sessionid_ss` acompanham conforme o dominio.
COOKIES_DE_SESSAO = ("sessionid", "sessionid_ss", "sid_tt")


def _tem_sessao(ctx) -> bool:
    """Ha sessao de TikTok guardada neste contexto? Nunca levanta.

    NAO serve para dizer se a sessao ainda e VALIDA (cookie expirado continua
    no disco) — por isso quem pergunta "ja esta logado?" no comeco da janela
    continua olhando o redirecionamento, que so acontece com sessao viva.
    Aqui a pergunta e outra: "ele acabou de entrar?", e ai o cookie novo e a
    prova certa, venha de qual aba vier.
    """
    try:
        nomes = {c.get("name") for c in ctx.cookies("https://www.tiktok.com")}
    except Exception:                                          # noqa: BLE001
        return False
    return bool(set(COOKIES_DE_SESSAO) & nomes)


def publicar(video, *, postar: bool | None = None, config: dict | None = None,
             canal: str = "builds",
             progresso=None, prova: dict | None = None) -> str:
    """Sobe o vídeo e escreve a legenda. Só posta se `postar` for True.

    Devolve uma frase de estado — o que aconteceu de fato, não uma promessa.

    `prova` é um dicionário OPCIONAL preenchido no lugar, com o laudo do que
    deu para provar. O retorno e o comportamento não mudam.

    O laudo do TikTok é mais pobre que o do YouTube de propósito: aqui não
    volta id nem URL, então a prova possível é a da tela — a página saiu de
    `/upload` e mostrou sucesso. A conferência contra o Studio (que casa pela
    hora da postagem) é quem fecha a conta depois.
    """
    from . import catalogo

    config = catalogo.carregar_config() if config is None else config
    ajustes = config.get("tiktok", {})
    if postar is None:
        # Sem `postar` explicito, PARA antes de publicar (a chave
        # `postar_automatico` saiu do config em 14/10/2026).
        postar = False
    url_upload = ajustes.get("url_upload") or URL_UPLOAD

    caminho = Path(video.caminho)
    if not caminho.is_file():
        raise TikTokFalhou(f"arquivo sumiu: {caminho}")
    # A LUTA MUDA NAO SOBE, venha de onde vier (28/09/2026): antes de abrir o
    # Chrome e fora da fabrica do diario — e a guarda funcionando, nao uma
    # falha de publicacao. O motivo fica na lista "a conferir" do TikTok.
    audio.barrar_luta_muda(video, canal, "tiktok")
    if not video.vertical:
        # Não é impedimento técnico, mas 16:9 no TikTok entra com tarja e
        # some no feed — melhor avisar do que publicar torto.
        print("[tiktok] AVISO: este é o corte 16:9 (normal). O TikTok espera "
              "o 9:16 (celular).")

    def passo(texto: str):
        print(f"[tiktok] {texto}", flush=True)
        if progresso:
            progresso(texto)

    # Nasce pessimista: se estourar no meio, quem passou o dicionário fica
    # com o que deu tempo de medir em vez de ficar sem nada.
    from datetime import datetime as _dt
    laudo = prova if prova is not None else {}
    laudo.update({
        "plataforma": "tiktok", "canal": canal,
        "conta": _conta_ativa(canal), "estado": "nao_subiu",
        "url": "", "confirmado": False, "upload_s": None,
        "quando": _dt.now().isoformat(timespec="seconds"),
    })

    # A Vila mostra o que esta acontecendo lendo o diario, e ate 01/09/2026
    # publicar nao escrevia nada nele. Como o caminho padrao virou o
    # navegador, a fabrica "publicacao" ficava OCIOSA durante quase todo
    # upload de verdade -- so a API, hoje secundaria, reportava. Um painel
    # que mostra "parado" enquanto se publica e pior do que nao ter painel.
    # `etapa` e `ref` fecham a conta do /confiabilidade. Sem `etapa`, uma
    # excecao crua daqui (um TimeoutError no `goto`, por exemplo) entra no
    # diario sem dizer de que passo veio, e o relatorio conta "publicacao"
    # inteira como uma coisa so — misturando "o TikTok nao abriu" com "o
    # YouTube recusou", que tem consertos diferentes. `ref` liga a falha ao
    # video, sem o qual nao da para saber se e um video ruim ou o passo.
    with atividade.fabrica("publicacao", f"TikTok: {caminho.name}",
                           canal=canal, etapa="publicar.tiktok",
                           ref=getattr(video, "id", "")), \
            contexto_persistente(headless=False,
                                 profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, url_upload)
        passo("abrindo o estúdio de upload...")

        entrada = None
        limite = time.time() + ESPERA_PAGINA_S
        while time.time() < limite and entrada is None:
            if "login" in page.url:
                raise TikTokFalhou(
                    "o TikTok pediu login. Rode o login uma vez pelo painel "
                    "(botão 'Login no TikTok') e tente de novo.")
            try:
                candidato = page.locator(ENTRADA_ARQUIVO).first
                if candidato.count():
                    entrada = candidato
                    break
            except Exception:
                pass
            time.sleep(1.0)
        if entrada is None:
            raise TikTokFalhou(
                "não achei o campo de arquivo na página de upload. Rode "
                "`python -m builds.publicar.tiktok --sondar` para ver a tela.")

        entrada.set_input_files(str(caminho))
        comeco_do_upload = time.monotonic()
        passo(f"arquivo entregue ({caminho.name}); o TikTok está processando...")

        # O upload real acontece do lado deles; o sinal de pronto é a tela
        # mudar (preview do vídeo / botão de postar habilitado).
        pronto = chegou = None
        limite = time.time() + ESPERA_PROCESSAR_S
        while time.time() < limite and pronto is None:
            pronto = _primeiro(page, (PROVA_DE_PRONTO,), timeout=2.0)
            if pronto is None and chegou is None:
                chegou = _primeiro(page, SINAIS_DE_PROGRESSO, timeout=1.0)
                if chegou is not None:
                    passo("arquivo recebido; esperando o TikTok processar...")
            time.sleep(1.0)
        if pronto is None and chegou is None:
            raise TikTokFalhou(
                "o TikTok não confirmou o processamento do vídeo a tempo. A "
                "janela está aberta: dá para terminar na mão.")
        passo("vídeo processado." if pronto is not None else
              "o botão de publicar não habilitou no tempo, mas o vídeo está "
              "na tela — tentando publicar mesmo assim.")

        _fechar_aviso(page, passo, laudo)
        texto_legenda = video.descricao_completa[:2000]
        laudo["envio_concluido"] = _esperar_envio(page, passo)
        _escrever_legenda(page, texto_legenda, passo, laudo)
        capa_s = getattr(video, "capa_s", None)
        if capa_s is not None:
            quadro = quadro_do_video(caminho, float(capa_s))
            if quadro is None:
                laudo["capa"] = "padrao (sem o quadro)"
                passo("capa: nao tirei o quadro do video; fica a do formulario.")
            else:
                _escolher_capa(page, quadro, passo, laudo)

        if _deve_barrar(postar, texto_legenda, laudo):
            # "VOLTA NA FILA DE ATRASADOS" so e verdade porque, desde
            # 05/10/2026, a parte RETIDA so fica "a conferir" no destino onde
            # saiu (`postar._marcar_retido`): antes ela era marcada aqui tambem
            # e a recuperacao a descartava — h34 p06 e h42 p06 nunca chegaram.
            raise TikTokFalhou(
                f"a legenda não entrou ({laudo.get('legenda')}) e publicar sem "
                "ela queima o vídeo: sem título e sem hashtag ele não é "
                "encontrado por ninguém. Adiado de propósito — se já saiu no "
                "YouTube, a recuperação do TikTok o leva numa próxima rodada; "
                "senão ele volta à fila. A janela segue aberta.")

        if not postar:
            passo("PARANDO antes de publicar — confira e clique em Publicar. "
                  "A janela fica aberta por 5 minutos.")
            time.sleep(300)
            return ("vídeo carregado e legenda escrita; a publicação final "
                    "ficou com você")

        botao = _primeiro(page, BOTAO_POSTAR, timeout=15.0)
        if botao is None:
            raise TikTokFalhou(
                "não achei o botão de publicar (a janela segue aberta).")
        # O timeout PRECISA ser dito. Sem ele o Playwright usa 30 s para
        # esperar o botão ficar clicável, e o processamento do TikTok passa
        # disso — foi o que deixou `duelo_00001` fora do ar em 11/09/2026.
        try:
            botao.click(timeout=int(ESPERA_HABILITAR_S * 1000))
        except Exception as exc:
            # A etiqueta `[legenda: ...]` saiu daqui em 16/09/2026. Ela existia
            # para separar no diario "legenda nao escreveu" de "botao nao
            # habilitou" — mas agora legenda que nao entra LEVANTA antes, com
            # mensagem propria, e nunca chega neste ponto. Chegar aqui ja
            # significa que a legenda estava escrita.
            raise TikTokFalhou(
                "o botão de publicar não ficou clicável em "
                f"{ESPERA_HABILITAR_S / 60:.0f} min — o TikTok ainda estava "
                f"processando o vídeo. A janela segue aberta. ({exc})"
            ) from exc
        # A PROVA DO CLIQUE, GRAVADA NO INSTANTE EM QUE ELE SAI. O `laudo` e
        # preenchido no lugar (e o `prova` de quem chamou), entao esta marca
        # SOBREVIVE a qualquer excecao daqui para baixo — inclusive uma que
        # aconteca depois do post ja ter subido. Sem ela, a unica evidencia
        # de que o clique saiu era a frase de retorno, e uma excecao apaga a
        # frase: o video voltaria para a fila e seria reenviado, duplicando.
        laudo["clicou"] = True
        try:
            passo("publicar clicado; confirmando...")
            estado = _confirmar_publicacao(page, passo)
            passo(estado)
            laudo["upload_s"] = round(time.monotonic() - comeco_do_upload, 1)
            laudo["confirmacao_extra"] = "confirmacao extra" in estado
            if confirmado(estado):
                laudo["estado"] = "publicado"
                laudo["confirmado"] = True
                # O TikTok nao devolve URL nem id aqui; o registro vale para
                # saber O QUE ja foi publicado e onde (a metrica de retencao
                # segue sendo so do YouTube).
                from . import metricas
                metricas.registrar_publicado(
                    video, estado, "tiktok", canal=canal,
                    extra={"prova": [dict(laudo)],
                           "prova_ok": metricas.prova_ok(laudo)})
            else:
                laudo["estado"] = "sem_confirmacao"
        except Exception as exc:                               # noqa: BLE001
            # O CLIQUE JA SAIU (PUB-1, 14/10/2026). Como no
            # `youtube_web._depois_do_clique`: a excecao depois do clique
            # (Chrome fechando na confirmacao, `progresso` levantando) nao
            # passava por `desfecho.resolver`, e so a ficha da rodada sabia
            # do clique — o horario seguinte, a recuperacao e a reserva
            # escolhiam o video de novo. Aqui e o funil de todos os caminhos.
            if not laudo.get("confirmado"):
                laudo["estado"] = "sem_confirmacao"
            try:
                desfecho.resolver(
                    canal, video,
                    f"cliquei em publicar no TikTok e algo falhou depois "
                    f"({type(exc).__name__}): o post pode estar no ar — "
                    f"confira no perfil.", laudo)
            except Exception:                                  # noqa: BLE001
                # `marcar_para_conferir` ja avisou no diario e guardou a
                # marca na memoria desta execucao; sobe a excecao original.
                pass
            raise
        # A CLASSIFICACAO MORA AQUI, e nao em quem chama. Ela vivia dentro do
        # `postar.py`, e o `main.py publicar <id> --tiktok --postar` — que e
        # o `/publicar` do bot e o botao do app — chama esta funcao DIRETO:
        # um clique sem confirmacao por ali nao marcava nada, e a recuperacao
        # da grade repostava. Aqui e o funil por onde todos passam.
        laudo["desfecho"] = desfecho.resolver(canal, video, estado, laudo)
        return estado


# O EDITOR DE UM POST JA PUBLICADO. Achado em 28/09/2026 pelo lapis da lista
# do Studio (`tiktokstudio/content`): ele abre esta pagina, com a legenda
# editavel e os botoes "Salvar" / "Cancelar".
URL_EDITAR = ("https://www.tiktok.com/tiktokstudio/upload/post/{id}"
              "?from=creator_center")
BOTAO_SALVAR = (
    'button:has-text("Salvar")',
    'button:has-text("Save")',
)
ESPERA_LISTA_DO_STUDIO_S = 60.0


def mesma_legenda(no_ar: str | None, texto: str) -> bool:
    """A legenda que o TikTok devolve e o texto, iguais?

    Pelo espaco normalizado, e so por ele: o `desc` do Studio devolve os
    paragrafos com o espaco que o editor guardou, e a pergunta aqui e se o
    TEXTO e o mesmo — nao um criterio frouxo como "as primeiras palavras".
    `None` (nao consegui ler) nunca e igual.
    """
    if no_ar is None:
        return False
    return " ".join(str(no_ar).split()) == " ".join(str(texto or "").split())


def legenda_no_studio(page, tiktok_id: str,
                      espera: float = ESPERA_LISTA_DO_STUDIO_S) -> str | None:
    """O `desc` do post como o TikTok o guarda (JSON `item_list` do Studio).

    E a mesma fonte das metricas (`tiktok_metricas`), e nao a tela: o campo
    do editor mostra o que se digitou, o `item_list` mostra o que ficou
    salvo. `None` se o post nao veio na primeira pagina da lista.
    """
    from .tiktok_metricas import LISTA, URL_CONTEUDO
    achados: dict = {}

    def ouvir(resp):
        if LISTA not in resp.url:
            return
        try:
            corpo = resp.json()
        except Exception:                                      # noqa: BLE001
            return
        for bruto in corpo.get("item_list") or []:
            achados[str(bruto.get("item_id"))] = str(bruto.get("desc") or "")

    page.on("response", ouvir)
    # NA MESMA ABA (o ouvinte esta nela), com uma segunda chance.
    try:
        ir_para(page, URL_CONTEUDO,
                log=lambda t: print(f"[tiktok] {t}", flush=True))
    except AberturaFalhou as exc:
        raise TikTokFalhou(
            f"infraestrutura: a lista do Studio nao abriu ({exc})") from exc
    fim = time.time() + espera
    while str(tiktok_id) not in achados and time.time() < fim:
        page.wait_for_timeout(1000)
    return achados.get(str(tiktok_id))


def corrigir_legenda(tiktok_id: str, texto: str, *, canal: str = "historias",
                     salvar: bool = True, progresso=None) -> dict:
    """Reescreve a legenda de um post JA PUBLICADO e confere o que ficou.

    Existe pela decisao `legenda-h31-p06` (28/09/2026): a legenda da
    `historia_00031:celular:p06` saiu com 109 de 230 caracteres — o editor
    comeu dois paragrafos colados e o criterio antigo de leitura aprovou.
    A escrita e a MESMA do upload (`_escrever_legenda`: digita primeiro,
    le o campo de volta exigindo cada linha), e a prova final e o `desc` que
    o proprio TikTok devolve depois de salvar, comparado com o texto
    (`mesma_legenda`). Com `salvar=False` escreve, confere o campo e sai sem
    clicar em nada (o editor descarta ao fechar).
    """
    def passo(frase: str):
        print(f"[tiktok] {frase}", flush=True)
        if progresso:
            progresso(frase)

    laudo: dict = {"tiktok_id": str(tiktok_id), "canal": canal,
                   "salvou": False, "no_ar": None, "conferida": False}
    with atividade.fabrica("publicacao", f"TikTok: legenda de {tiktok_id}",
                           canal=canal, etapa="publicar.tiktok.legenda",
                           ref=str(tiktok_id)), \
            contexto_persistente(headless=False,
                                 profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_EDITAR.format(id=tiktok_id))
        passo("abrindo o editor do post...")
        page.wait_for_timeout(5000)
        if "login" in page.url:
            raise TikTokFalhou("o TikTok pediu login; nada foi mudado.")
        if not _escrever_legenda(page, texto, passo, laudo):
            raise TikTokFalhou(
                f"a legenda nao entrou no editor ({laudo.get('legenda')}); "
                "nada foi salvo.")
        # O CAMPO INTEIRO, NA ORDEM, antes de salvar. `_escrever_legenda`
        # confere que cada linha esta la, nao a ordem — e no ensaio de
        # 28/09, 23:13, a digitacao neste editor saiu EMBARALHADA (o cursor
        # pulou e "Eu escrevo..." foi parar depois das hashtags). Salvar um
        # texto fora de ordem trocaria uma legenda curta por uma errada.
        campo = _primeiro(page, CAMPO_LEGENDA, timeout=10.0)
        try:
            laudo["campo"] = campo.inner_text() if campo is not None else None
        except Exception:                                      # noqa: BLE001
            laudo["campo"] = None
        if not mesma_legenda(laudo["campo"], texto):
            laudo["tela"] = escrita.fotografar(page, "tiktok_legenda_campo")
            raise TikTokFalhou(
                "o campo nao ficou IGUAL ao texto (ordem ou pedaco); nada foi "
                f"salvo. Campo: {str(laudo['campo'])[:120]!r}")
        if not salvar:
            passo("legenda escrita e conferida no campo; NAO salvei.")
            return laudo
        botao = _primeiro(page, BOTAO_SALVAR, timeout=15.0)
        if botao is None:
            raise TikTokFalhou("nao achei o botao Salvar; nada foi salvo.")
        botao.click(timeout=int(ESPERA_HABILITAR_S * 1000))
        laudo["salvou"] = True
        passo("Salvar clicado; conferindo no Studio...")
        page.wait_for_timeout(8000)
        laudo["tela"] = escrita.fotografar(page, "tiktok_legenda_salva")
        laudo["no_ar"] = legenda_no_studio(page, tiktok_id)
        laudo["conferida"] = mesma_legenda(laudo["no_ar"], texto)
        passo("legenda no ar IGUAL ao texto." if laudo["conferida"] else
              f"a legenda no ar NAO confere: {laudo['no_ar']!r}")
    return laudo


def main(argv=None) -> int:
    import argparse

    from . import catalogo

    parser = argparse.ArgumentParser(
        description="Publica um vídeo do catálogo no TikTok (navegador)")
    parser.add_argument("video_id", nargs="?")
    parser.add_argument("--limpar", action="store_true",
                        help="limpa o cache do perfil antes (mantem o login)")
    parser.add_argument("--canal", default="builds",
                        help="de qual canal e a conta (builds|historias)")
    parser.add_argument("--login", action="store_true",
                        help="abre a janela para o login manual (uma vez)")
    parser.add_argument("--sondar", action="store_true",
                        help="despeja o DOM da tela de upload")
    parser.add_argument("--postar", action="store_true",
                        help="clica em publicar (o padrão é PARAR antes)")
    args = parser.parse_args(argv)

    if args.login:
        login(canal=args.canal, limpar=args.limpar)
        return 0
    if args.sondar:
        sondar(canal=args.canal)
        return 0
    if not args.video_id:
        parser.error("informe o video_id, --login ou --sondar")

    video = catalogo.por_id(args.video_id)
    if video is None:
        print(f"vídeo não encontrado: {args.video_id}")
        return 1
    try:
        print(publicar(video, postar=args.postar or None, canal=args.canal))
    except TikTokFalhou as exc:
        print(f"FALHOU: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["PERFIL", "TikTokFalhou", "login", "publicar", "sondar"]
