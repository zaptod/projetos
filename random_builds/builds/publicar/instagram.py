# -*- coding: utf-8 -*-
"""Publicar um Reel no Instagram por automacao de navegador (patchright).

O molde e o `tiktok.py`: Chrome de verdade, perfil persistente POR CONTA
(`%LOCALAPPDATA%/neural-fights/browser_profiles/instagram__<conta>`), login
feito UMA vez pelo Adrian numa janela que nos abrimos (a senha nunca passa por
aqui). Reutilizavel por canal: tudo recebe `canal`, e quem diz QUAL conta e o
`contas.py` (servico "instagram", opcional: canal sem conta = destino desligado
e calado).

AS REGRAS DESTE MODULO (26/10/2026), todas nascidas de um erro do dia:

  1. IDENTIDADE ANTES DE PUBLICAR. Hoje um comentario saiu pela conta PESSOAL do
     Adrian porque ninguem leu qual identidade estava ativa. Aqui o @ ativo e
     lido NA TELA (captura em `outputs/_publicar/telas`) antes do upload e de
     novo antes do clique em "Compartilhar"; se nao for o @ configurado para o
     canal, ou se nao der para ler, RECUSA (falha fechada).
  2. NUNCA comentar, curtir, seguir ou responder. Este modulo so abre a
     home, o perfil da PROPRIA conta (leitura) e o fluxo "Criar". O fechamento
     de pop-ups e o generico do TikTok (`tiktok._fechar_aviso`): so botao de
     DISPENSA, nunca um que ative algo (`BOTOES_PROIBIDOS_NO_INSTAGRAM`), e a
     janela de trabalho ("Criar nova publicacao") nunca e fechada.
  3. A CAPA e escolhida ANTES de publicar (nao se troca depois). Ficha com
     `capa_s` e capa que nao entrou = NAO publica (adia), diferente do TikTok.
  4. Sempre o mp4 ORIGINAL da ficha (marca d'agua de outra rede derruba o
     alcance); este modulo nunca baixa nem converte nada.
  5. Nao ha comando de publicar aqui: quem publica e `ferramentas/postar.py`
     (funil `_instagram_da_serie`). A CLI so faz login, sonda, status e
     conferencia (leitura).

Os seletores NAO foram validados contra o site de verdade (ainda nao havia
conta quando isto foi escrito): o `--sondar` despeja o DOM e a primeira
publicacao deve ser vista na tela. Ate la o padrao seguro vale: sem ler o @,
nao publica.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from .. import atividade
from ..identity.browser import (AberturaFalhou, abrir_pagina,
                                contexto_persistente, ir_para)
from . import audio, desfecho, escrita, tiktok

SERVICO = "instagram"
URL_INICIO = "https://www.instagram.com/"
URL_LOGIN = "https://www.instagram.com/accounts/login/"
URL_PERFIL = "https://www.instagram.com/{arroba}/reels/"

SUCESSO = "publicado no Instagram"

LIMITE_LEGENDA = 2200
LIMITE_HASHTAGS = 30          # teto DO SITE
HASHTAGS_NA_LEGENDA = 5       # o que a casa usa (instagram-seo: 3 a 5, nao 30)

ESPERA_PAGINA_S = 60.0
ESPERA_PROCESSAR_S = 240.0
ESPERA_CONFIRMAR_S = 300.0
ESPERA_IDENTIDADE_S = 20.0
PAUSA_SEM_POSTAR_S = 300.0


class InstagramFalhou(RuntimeError):
    """Erro legivel — o painel mostra a frase, nao o traceback."""


class ContaErrada(InstagramFalhou):
    """O @ ativo na tela nao e o da conta configurada para o canal (ou nao deu
    para ler). Nada foi enviado nem clicado."""


def confirmado(estado) -> bool:
    """O Instagram confirmou a publicacao? (a unica pergunta que vale)"""
    return str(estado or "").startswith(SUCESSO)


# ------------------------------------------------------------------ a conta
def _limpo(arroba) -> str:
    return str(arroba or "").strip().lstrip("@").strip("/").lower()


def conta_do_canal(canal: str) -> str | None:
    """A conta de Instagram que ESTE canal escolheu, ou `None` (desligado)."""
    try:
        from .. import contas
        return contas.conta_propria(SERVICO, canal)
    except Exception:                                          # noqa: BLE001
        return None


def perfil_da_conta(canal: str) -> Path:
    from .. import contas
    return contas.perfil(SERVICO, canal)


def arroba_esperada(canal: str) -> str:
    """O @ que a tela TEM de mostrar para este canal ("" = canal sem conta).

    Ordem: o que o Adrian declarou no login (`arroba_esperada`), o @ ja
    conferido, o rotulo, o proprio nome da conta (regra de nomes: nome =
    destino)."""
    conta = conta_do_canal(canal)
    if not conta:
        return ""
    try:
        from .. import contas
        quem = contas.identidade(SERVICO, conta)
    except Exception:                                          # noqa: BLE001
        quem = {}
    return _limpo(quem.get("arroba_esperada") or quem.get("id")
                  or quem.get("rotulo") or conta)


def ligado(canal: str) -> bool:
    """O destino Instagram deste canal esta LIGADO? So com conta propria E o
    login conferido na tela (`login` grava o @ lido em `identidade.id`).

    Sem conta, ou conta ainda sem login conferido = desligado e CALADO (nenhum
    alarme, nenhuma ficha). Nunca levanta."""
    try:
        from .. import contas
        conta = contas.conta_propria(SERVICO, canal)
        if not conta:
            return False
        return bool(contas.identidade(SERVICO, conta).get("id"))
    except Exception:                                          # noqa: BLE001
        return False


def status(canal: str) -> dict:
    """Retrato barato (sem navegador) do destino deste canal."""
    conta = conta_do_canal(canal)
    ficha = {"canal": canal, "conta": conta or "", "ligado": ligado(canal),
             "arroba_esperada": arroba_esperada(canal)}
    if conta:
        try:
            from .. import contas
            quem = contas.identidade(SERVICO, conta)
            ficha.update(arroba_lido=quem.get("id") or "",
                         login_conferido_em=quem.get("conferido") or "",
                         vivo_em=quem.get("vivo_em") or "")
        except Exception:                                      # noqa: BLE001
            pass
    if not conta:
        ficha["motivo"] = "canal sem conta de Instagram (desligado, calado)"
    elif not ficha["ligado"]:
        ficha["motivo"] = ("conta escolhida, mas o login ainda nao foi "
                           "conferido na tela: rode o --login")
    return ficha


# ------------------------------------------------------------- a legenda
def _tamanho(texto: str) -> int:
    """Comprimento como o Instagram conta (UTF-16: emoji vale 2)."""
    return len(texto.encode("utf-16-le")) // 2


def _hashtags(tags, quantas: int) -> list:
    saida, vistas = [], set()
    for bruta in tags or []:
        tag = "#" + re.sub(r"\s+", "", str(bruta)).lstrip("#")
        chave = tag.lower()
        if len(tag) > 1 and chave not in vistas:
            vistas.add(chave)
            saida.append(tag)
    return saida[:max(0, quantas)]


def legenda_do_video(video, *, hashtags: int = HASHTAGS_NA_LEGENDA) -> str:
    """Titulo, descricao e hashtags, dentro dos limites do site (2200
    caracteres, 30 hashtags — e a casa usa so `hashtags`=5, instagram-seo).

    O titulo vem PRIMEIRO (e a palavra-chave/gancho da ficha). Estourou: corta
    a DESCRICAO em fim de palavra com reticencias; as hashtags ficam inteiras.
    As hashtags que o proprio texto ja tem contam para o teto."""
    titulo = str(getattr(video, "titulo", "") or "").strip()
    descricao = str(getattr(video, "descricao", "") or "").strip()
    if descricao.startswith(titulo):
        descricao = descricao[len(titulo):].strip()
    corpo = "\n\n".join(p for p in (titulo, descricao) if p)
    ja = len(re.findall(r"#(?=\w*[^\W\d_])\w+", corpo))   # "#1" nao e hashtag
    quantas = max(0, min(hashtags, LIMITE_HASHTAGS) - ja)
    tags = _hashtags(getattr(video, "hashtags", None), quantas)
    cola = " ".join(tags)
    reserva = _tamanho(cola) + (2 if cola else 0)
    orcamento = LIMITE_LEGENDA - reserva
    if _tamanho(corpo) > orcamento:
        corte = corpo
        while corte and _tamanho(corte) > orcamento - 1:
            corte = corte[:-1]
        corte = re.sub(r"\s+\S*$", "", corte) if " " in corte else corte
        corpo = corte.rstrip(" ,;:.") + "…"
    return (corpo + ("\n\n" + cola if cola else "")).strip()


# ----------------------------------------------------- a identidade na tela
_JS_ARROBA = r"""() => {
  const reservados = new Set(['explore','reels','reel','direct','accounts','p',
      'stories','about','legal','privacy','web','api','developer','press',
      'blog','challenge','emails','session','your_activity','settings',
      'notifications','create','tv','ar','directory','lite','topics']);
  const norm = t => (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .trim().toLowerCase();
  const porTexto = [], porFoto = [];
  for (const a of document.querySelectorAll('a[href^="/"]')) {
    const m = (a.getAttribute('href') || '').match(/^\/([A-Za-z0-9._]{1,30})\/?$/);
    if (!m || reservados.has(m[1].toLowerCase())) continue;
    const texto = norm(a.innerText || a.getAttribute('aria-label') || '');
    if (texto === 'perfil' || texto === 'profile') porTexto.push(m[1]);
    const img = a.querySelector('img[alt]');
    const alt = img ? (img.getAttribute('alt') || '') : '';
    if (/(foto do perfil|profile picture)/i.test(alt)
        && a.closest('nav,[role=navigation]')) porFoto.push(m[1]);
  }
  return {por: porTexto.length ? 'texto' : (porFoto.length ? 'foto' : ''),
          arrobas: porTexto.length ? porTexto : porFoto};
}"""


def ler_arroba(page) -> tuple:
    """(@ ativo na tela, motivo). `@` vazio = nao deu para ler (motivo diz).
    Nunca levanta. Mais de um @ distinto = ambiguo = nao leu."""
    try:
        r = page.evaluate(_JS_ARROBA)
    except Exception as exc:                                   # noqa: BLE001
        return "", f"a tela nao respondeu ({type(exc).__name__})"
    achados = {_limpo(a) for a in ((r or {}).get("arrobas") or []) if a}
    if len(achados) == 1:
        return next(iter(achados)), ""
    if not achados:
        return "", "nao achei o link 'Perfil' do menu"
    return "", f"mais de um @ no menu ({sorted(achados)})"


def conferir_identidade(page, canal: str, passo, laudo: dict, etapa: str, *,
                        espera: float = ESPERA_IDENTIDADE_S,
                        dormir=None) -> str:
    """Le o @ ativo, tira a captura e RECUSA se nao for o do canal. Devolve o @.

    Falha FECHADA: nao conseguir ler tambem recusa."""
    dormir = dormir or time.sleep
    esperado = arroba_esperada(canal)
    lido, motivo = "", ""
    fim = time.monotonic() + espera
    while True:
        lido, motivo = ler_arroba(page)
        if lido or time.monotonic() >= fim:
            break
        dormir(1.0)
    foto = escrita.fotografar(page, f"instagram_identidade_{etapa}")
    laudo.setdefault("identidade", []).append(
        {"etapa": etapa, "lido": lido, "esperado": esperado, "tela": foto})
    if not esperado:
        raise ContaErrada(f"o canal {canal} nao tem conta de Instagram "
                          "configurada; nao publico.")
    if not lido:
        raise ContaErrada(
            f"nao consegui ler qual @ esta ativo no Instagram ({motivo}); "
            f"recuso publicar sem saber (captura: {foto or '-'}).")
    if lido != esperado:
        raise ContaErrada(
            f"o Instagram esta logado como @{lido}, mas o canal {canal} "
            f"publica como @{esperado}: NAO publico (captura: {foto or '-'}).")
    laudo["arroba"] = lido
    passo(f"conta conferida na tela: @{lido} ({etapa}; captura: {foto or '-'}).")
    return lido


# ------------------------------------------------------------ pop-ups / telas
# O que NUNCA se fecha (e a janela de trabalho) e o que NUNCA se clica.
TRABALHO = {"seletor": "input[type='file'], [contenteditable='true']",
            "botoes": ["avancar", "next", "compartilhar", "share", "voltar",
                       "back", "selecionar do computador",
                       "select from computer"]}
BOTOES_PROIBIDOS_NO_INSTAGRAM = tuple(tiktok.BOTOES_PROIBIDOS) + (
    "seguir", "follow", "curtir", "like", "comentar", "comment", "responder",
    "reply", "compartilhar", "share", "avancar", "next", "adicionar", "add",
    "enviar", "send", "salvar informacoes", "save info")


def _fechar_aviso(page, passo, laudo: dict | None = None) -> str:
    return tiktok._fechar_aviso(page, passo, laudo, prefixo="instagram",
                                trabalho=TRABALHO,
                                proibidos=BOTOES_PROIBIDOS_NO_INSTAGRAM)


BOTAO_CRIAR = ('svg[aria-label="Nova publicação"]', 'svg[aria-label="New post"]',
               'a:has-text("Criar")', 'a:has-text("Create")',
               "text=/^(Criar|Create)$/")
ITEM_PUBLICACAO = ("text=/^(Publicação|Postagem|Post)$/",)
ENTRADA_ARQUIVO = 'input[type="file"]'
BOTAO_AVANCAR = ("[role=dialog] >> text=/^(Avançar|Next)$/ >> visible=true",
                 "text=/^(Avançar|Next)$/ >> visible=true")
ESCOLHER_CORTE = ('[aria-label="Selecionar corte"]',
                  '[aria-label="Select crop"]')
CORTE_ORIGINAL = ("text=/^Original$/",)
ABA_CAPA = ("text=/^(Capa|Cover)$/",)
CAMPO_LEGENDA = ('div[role="textbox"][contenteditable="true"]',
                 'div[contenteditable="true"][aria-label*="legenda" i]',
                 'div[contenteditable="true"][aria-label*="caption" i]',
                 'div[contenteditable="true"]')
BOTAO_COMPARTILHAR = (
    "[role=dialog] >> text=/^(Compartilhar|Share)$/ >> visible=true",)
SINAIS_DE_SUCESSO = (
    "seu reel foi compartilhado", "reel compartilhado",
    "sua publicacao foi compartilhada", "your reel has been shared",
    "reel shared", "your post has been shared", "post shared")
SINAIS_DE_ERRO = (
    "nao foi possivel compartilhar", "could not be shared",
    "couldn't be shared", "algo deu errado", "something went wrong")
SINAIS_DE_ARQUIVO_RUIM = (
    "nao foi possivel carregar", "couldn't be uploaded", "could not be uploaded",
    "arquivo nao e compativel", "file isn't supported", "this file couldn't")


def _texto_da_tela(page) -> str:
    try:
        return tiktok._sem_acento(page.evaluate(
            "() => document.body ? document.body.innerText : ''"))
    except Exception:                                          # noqa: BLE001
        return ""


def _clicar(page, seletores, rotulo: str, passo, *, timeout: float = 8.0,
            obrigatorio: bool = True, laudo: dict | None = None) -> bool:
    alvo = tiktok._primeiro(page, seletores, timeout=timeout)
    if alvo is None:
        if obrigatorio:
            foto = escrita.fotografar(page, f"instagram_sem_{rotulo[:20]}")
            raise InstagramFalhou(
                f"nao achei {rotulo} (captura: {foto or '-'}). Rode "
                "`python -m builds.publicar.instagram --sondar`.")
        return False
    alvo.click(timeout=5000)
    return True


# ----------------------------------------------------------------- o fluxo
def _corte_original(page, passo, laudo: dict) -> None:
    """Melhor esforco: mantem o corte ORIGINAL do arquivo (9:16)."""
    try:
        if not _clicar(page, ESCOLHER_CORTE, "o seletor de corte", passo,
                       timeout=4.0, obrigatorio=False):
            laudo["corte"] = "padrao (sem o seletor de corte)"
            return
        if _clicar(page, CORTE_ORIGINAL, "o corte Original", passo,
                   timeout=4.0, obrigatorio=False):
            laudo["corte"] = "original"
            passo("corte: original (9:16 do arquivo).")
        else:
            laudo["corte"] = "padrao (sem a opcao Original)"
    except Exception as exc:                                   # noqa: BLE001
        laudo["corte"] = f"padrao ({type(exc).__name__})"


def _escolher_capa(page, quadro, passo, laudo: dict) -> bool:
    """Envia o `quadro` (PNG) como capa. A capa NAO se troca depois de
    publicado: quem chama NAO publica se isto devolver False."""
    try:
        aba = tiktok._primeiro(page, ABA_CAPA, timeout=8.0)
        if aba is None:
            laudo["capa"] = "falhou (sem a aba Capa)"
            return False
        aba.click(timeout=5000)
        page.wait_for_timeout(800)
        page.locator(ENTRADA_ARQUIVO).last.set_input_files(str(quadro),
                                                           timeout=10000)
        page.wait_for_timeout(2500)
        laudo["capa"] = "enviada"
        passo("capa: quadro escolhido enviado.")
        return True
    except Exception as exc:                                   # noqa: BLE001
        laudo["capa"] = f"falhou ({type(exc).__name__})"
        return False


_JS_FEED = r"""(clicar) => {
  const norm = t => (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .trim().toLowerCase();
  const alvo = /(compartilhar tambem no feed|also share to feed|share to feed)/;
  const folhas = [...document.querySelectorAll('span,div,label')].filter(
      e => e.children.length === 0 && alvo.test(norm(e.innerText)));
  for (const f of folhas) {
    let linha = f;
    for (let i = 0; i < 6 && linha; i++, linha = linha.parentElement) {
      const sw = linha.querySelector(
          'input[type=checkbox],[role=switch],[role=checkbox]');
      if (!sw) continue;
      const lido = () => sw.matches('input') ? sw.checked
          : sw.getAttribute('aria-checked') === 'true';
      if (clicar && !lido()) sw.click();
      return {achou: true, ligado: lido()};
    }
  }
  return {achou: false, ligado: false};
}"""


def _ligar_feed(page, passo, laudo: dict) -> None:
    """"Compartilhar tambem no feed" LIGADO. Melhor esforco: o laudo diz o que
    houve (nao e o que impede publicar, e uma preferencia)."""
    try:
        r = page.evaluate(_JS_FEED, True)
        if r.get("achou") and not r.get("ligado"):
            page.wait_for_timeout(500)
            r = page.evaluate(_JS_FEED, True)
    except Exception as exc:                                   # noqa: BLE001
        laudo["feed"] = f"nao li ({type(exc).__name__})"
        return
    if not r.get("achou"):
        laudo["feed"] = "sem o controle na tela"
        passo("feed: nao achei o controle 'compartilhar tambem no feed'.")
    elif r.get("ligado"):
        laudo["feed"] = "ligado"
        passo("feed: compartilhar tambem no feed LIGADO.")
    else:
        laudo["feed"] = "nao consegui ligar"
        passo("feed: nao consegui ligar o controle.")


def _hrefs_do_perfil(page, arroba: str) -> set:
    """Os links de reel da grade do PROPRIO perfil (leitura). Melhor esforco:
    `set()` se nao deu. Nunca levanta."""
    try:
        ir_para(page, URL_PERFIL.format(arroba=arroba), tentativas=2,
                log=lambda t: print(f"[instagram] {t}", flush=True))
        page.wait_for_timeout(4000)
        achados = page.evaluate(
            "() => [...document.querySelectorAll('a[href*=\"/reel/\"]')]"
            ".map(a => a.getAttribute('href'))")
        return {str(h) for h in achados or []}
    except Exception:                                          # noqa: BLE001
        return set()


def _novo_reel(antes: set, depois: set) -> str:
    novos = sorted(depois - antes)
    if len(novos) == 1:
        return "https://www.instagram.com" + novos[0]
    return ""


def _esperar_confirmacao(page, passo, espera: float = ESPERA_CONFIRMAR_S, *,
                         dormir=None) -> str:
    dormir = dormir or time.sleep
    fim = time.monotonic() + espera
    while time.monotonic() < fim:
        texto = _texto_da_tela(page)
        if any(s in texto for s in SINAIS_DE_SUCESSO):
            return SUCESSO
        if any(s in texto for s in SINAIS_DE_ERRO):
            return ("cliquei em publicar, mas o Instagram mostrou erro "
                    "('nao foi possivel compartilhar'): confira o perfil "
                    "antes de publicar de novo.")
        dormir(1.5)
    return ("cliquei em publicar, mas o Instagram nao confirmou. Confira se o "
            "Reel subiu.")


def _executar(page, video, caminho: Path, canal: str, postar: bool, passo,
              laudo: dict, *, quadro=None) -> str:
    """O fluxo inteiro numa aba ja aberta no instagram.com (testavel com uma
    pagina simulada). Devolve a frase de estado."""
    if re.search(r"/accounts/login", page.url or ""):
        raise InstagramFalhou("o Instagram pediu login. Rode o login uma vez "
                              "(`python -m builds.publicar.instagram "
                              f"--login --canal {canal}`) e tente de novo.")
    _fechar_aviso(page, passo, laudo)
    arroba = conferir_identidade(page, canal, passo, laudo, "antes")
    antes = _hrefs_do_perfil(page, arroba)
    if "/reels" in (page.url or ""):
        ir_para(page, URL_INICIO, tentativas=2,
                log=lambda t: print(f"[instagram] {t}", flush=True))
    _fechar_aviso(page, passo, laudo)

    passo("abrindo o Criar...")
    _clicar(page, BOTAO_CRIAR, "o botao Criar", passo)
    page.wait_for_timeout(800)
    # O submenu do Criar (Publicacao): no site antigo o clique ja abria a janela
    # e este item nao existe — por isso opcional, mas SEMPRE tentado (o input de
    # arquivo pode existir escondido antes da janela abrir).
    _clicar(page, ITEM_PUBLICACAO, "o item Publicacao do menu Criar",
            passo, timeout=5.0, obrigatorio=False)
    entrada, limite = None, time.monotonic() + ESPERA_PAGINA_S
    while entrada is None and time.monotonic() < limite:
        candidato = page.locator(ENTRADA_ARQUIVO).first
        try:
            if candidato.count():
                entrada = candidato
                break
        except Exception:                                      # noqa: BLE001
            pass
        time.sleep(1.0)
    if entrada is None:
        raise InstagramFalhou(
            "nao achei o campo de arquivo na janela Criar. Rode "
            "`python -m builds.publicar.instagram --sondar` para ver a tela.")
    entrada.set_input_files(str(caminho))
    comeco = time.monotonic()
    passo(f"arquivo entregue ({caminho.name}); o Instagram esta processando...")

    # Ate o botao Avancar aparecer: o pop-up "Reels agora sao compartilhados"
    # e afins sao dispensados pelo caminho (so por botao de dispensa).
    pronto, limite = None, time.monotonic() + ESPERA_PROCESSAR_S
    while pronto is None and time.monotonic() < limite:
        _fechar_aviso(page, passo, laudo)
        pronto = tiktok._primeiro(page, BOTAO_AVANCAR, timeout=2.0)
        if pronto is None:
            texto = _texto_da_tela(page)
            if any(s in texto for s in SINAIS_DE_ARQUIVO_RUIM):
                foto = escrita.fotografar(page, "instagram_arquivo_recusado")
                raise InstagramFalhou("o Instagram recusou o arquivo "
                                      f"(captura: {foto or '-'}).")
    if pronto is None:
        raise InstagramFalhou("o Instagram nao terminou de processar o video "
                              "a tempo; nada foi publicado.")
    passo("video processado.")

    _corte_original(page, passo, laudo)
    _clicar(page, BOTAO_AVANCAR, "o botao Avancar (corte)", passo)
    page.wait_for_timeout(1500)
    _fechar_aviso(page, passo, laudo)

    # A capa, na tela de edicao e ANTES de publicar. Ficha com `capa_s` e capa
    # que nao entrou: NAO publica (a capa nao se troca depois).
    capa_s = getattr(video, "capa_s", None)
    if capa_s is not None:
        if quadro is None:
            laudo["capa"] = "falhou (sem o quadro do video)"
            raise InstagramFalhou(
                "nao tirei o quadro da capa do video; NAO publico sem a capa "
                "(ela nao se troca depois). Adiado.")
        if not _escolher_capa(page, quadro, passo, laudo):
            raise InstagramFalhou(
                f"a capa nao entrou ({laudo.get('capa')}); NAO publico sem "
                "ela (nao se troca depois). Adiado; captura: "
                f"{escrita.fotografar(page, 'instagram_capa') or '-'}.")
    _clicar(page, BOTAO_AVANCAR, "o botao Avancar (edicao)", passo)
    page.wait_for_timeout(1500)
    _fechar_aviso(page, passo, laudo)

    texto = legenda_do_video(video)
    laudo["legenda_tamanho"] = _tamanho(texto)
    tiktok._escrever_legenda(page, texto, passo, laudo,
                             campos=CAMPO_LEGENDA, prefixo="instagram")
    _ligar_feed(page, passo, laudo)

    if tiktok._deve_barrar(postar, texto, laudo):
        raise InstagramFalhou(
            f"a legenda nao entrou ({laudo.get('legenda')}); publicar sem ela "
            "queima o video. Adiado de proposito.")
    # a SEGUNDA leitura do @, colada no clique: a sessao pode ter trocado
    conferir_identidade(page, canal, passo, laudo, "antes_de_publicar",
                        espera=5.0)
    if not postar:
        passo("PARANDO antes de publicar — confira e clique em Compartilhar. "
              f"A janela fica aberta por {PAUSA_SEM_POSTAR_S / 60:.0f} minutos.")
        time.sleep(PAUSA_SEM_POSTAR_S)
        return ("video carregado e legenda escrita; a publicacao final "
                "ficou com voce")

    _clicar(page, BOTAO_COMPARTILHAR, "o botao Compartilhar", passo,
            timeout=15.0)
    # A PROVA DO CLIQUE, no instante em que ele sai (como no TikTok): sobrevive
    # a qualquer excecao daqui para baixo.
    laudo["clicou"] = True
    try:
        passo("publicar clicado; confirmando...")
        estado = _esperar_confirmacao(page, passo)
        laudo["upload_s"] = round(time.monotonic() - comeco, 1)
        if confirmado(estado):
            laudo["estado"] = "publicado"
            laudo["confirmado"] = True
            url = _novo_reel(antes, _hrefs_do_perfil(page, arroba))
            if url:
                laudo["url"] = url
                estado = f"{SUCESSO} ({url})"
            passo(estado)
        else:
            laudo["estado"] = "sem_confirmacao"
            passo(estado)
    except Exception as exc:                                   # noqa: BLE001
        if not laudo.get("confirmado"):
            laudo["estado"] = "sem_confirmacao"
        try:
            desfecho.resolver(
                canal, video,
                f"cliquei em publicar no Instagram e algo falhou depois "
                f"({type(exc).__name__}): o Reel pode estar no ar — confira "
                "no perfil.", laudo, plataforma="instagram")
        except Exception:                                      # noqa: BLE001
            pass
        raise
    return estado


def _abrir(ctx, url: str):
    try:
        return abrir_pagina(ctx, url,
                            log=lambda t: print(f"[instagram] {t}", flush=True))
    except AberturaFalhou as exc:
        raise InstagramFalhou(
            f"infraestrutura: a pagina do Instagram nao abriu ({exc})") from exc


def publicar(video, *, postar: bool | None = None, canal: str = "bluelock",
             progresso=None, prova: dict | None = None) -> str:
    """Sobe o Reel e escreve a legenda. So clica em Compartilhar se `postar` for
    True. Devolve a frase de estado — o que aconteceu de fato.

    O FUNIL: destino desligado (sem conta com login conferido) recusa aqui,
    antes de abrir o Chrome, por qualquer caminho que chegue."""
    if postar is None:
        postar = False
    if not ligado(canal):
        raise InstagramFalhou(
            f"o Instagram do canal {canal} esta desligado (sem conta com login "
            "conferido); nao publico.")
    caminho = Path(video.caminho)
    if not caminho.is_file():
        raise InstagramFalhou(f"arquivo sumiu: {caminho}")
    audio.barrar_luta_muda(video, canal, "instagram")
    if not getattr(video, "vertical", True):
        raise InstagramFalhou("este e o corte 16:9; o Reel pede o 9:16. Nao "
                              "publico torto.")

    def passo(texto: str):
        print(f"[instagram] {texto}", flush=True)
        if progresso:
            progresso(texto)

    laudo = prova if prova is not None else {}
    laudo.update({"plataforma": "instagram", "canal": canal,
                  "conta": conta_do_canal(canal) or "", "estado": "nao_subiu",
                  "url": "", "confirmado": False, "upload_s": None,
                  "quando": datetime.now().isoformat(timespec="seconds")})
    capa_s = getattr(video, "capa_s", None)
    quadro = (tiktok.quadro_do_video(caminho, float(capa_s))
              if capa_s is not None else None)

    with atividade.fabrica("publicacao", f"Instagram: {caminho.name}",
                           canal=canal, etapa="publicar.instagram",
                           ref=getattr(video, "id", "")), \
            contexto_persistente(headless=False,
                                 profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_INICIO)
        passo("abrindo o Instagram...")
        estado = _executar(page, video, caminho, canal, bool(postar), passo,
                           laudo, quadro=quadro)
        if not postar:
            return estado
        if canal == "builds":
            from . import metricas
            if confirmado(estado):
                metricas.registrar_publicado(
                    video, estado, "instagram", canal=canal,
                    extra={"prova": [dict(laudo)],
                           "prova_ok": metricas.prova_ok(laudo)})
        laudo["desfecho"] = desfecho.resolver(canal, video, estado, laudo,
                                              plataforma="instagram")
        return estado


# ------------------------------------------------- janela na tela do Adrian
def trazer_para_a_tela(perfil: Path, *, pids=None) -> int:
    """Move para a tela as janelas do Chrome DESTE perfil que estejam fora dela
    (o Windows lembra a posicao da ultima janela, e a nossa abre fora da
    tela). Devolve quantas moveu. Nunca levanta; so Windows."""
    try:
        import ctypes
        from ctypes import wintypes
        from ..identity.browser import _chrome_do_perfil
        pids = set(pids if pids is not None
                   else _chrome_do_perfil(str(perfil)))
        if not pids:
            return 0
        u = ctypes.windll.user32
        esq, topo, larg, alt = (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
                                u.GetSystemMetrics(78), u.GetSystemMetrics(79))
        primaria_l, primaria_a = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        movidas = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def olhar(hwnd, _):
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in pids or not u.IsWindowVisible(hwnd):
                return True
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            if (r.right - r.left) < 300:
                return True
            fora = (r.right < esq + 50 or r.left > esq + larg - 50
                    or r.bottom < topo + 50 or r.top > topo + alt - 50
                    or r.left > primaria_l or r.top > primaria_a
                    or u.IsIconic(hwnd))
            if fora:
                u.ShowWindow(hwnd, 9)                 # SW_RESTORE
                u.MoveWindow(hwnd, 80, 60, min(1280, primaria_l - 160),
                             min(860, primaria_a - 120), True)
                movidas.append(hwnd)
            u.SetForegroundWindow(hwnd)
            return True

        u.EnumWindows(olhar, 0)
        return len(movidas)
    except Exception:                                          # noqa: BLE001
        return 0


# --------------------------------------------------------------------- login
def login(canal: str, *, conta: str | None = None, arroba: str | None = None,
          espera_s: float = 600.0) -> dict:
    """Abre a janela VISIVEL para o Adrian logar, le o @ na tela e so entao
    LIGA o destino. A senha nunca passa por aqui. Nao clica em nada."""
    from .. import contas
    if conta:
        contas.escolher(SERVICO, canal, conta)
    nome = conta_do_canal(canal)
    if not nome:
        raise InstagramFalhou(
            f"o canal {canal} ainda nao tem conta de Instagram: passe "
            "--conta <nome> (o @ da conta, ex.: egoistsoccer).")
    esperado = _limpo(arroba or arroba_esperada(canal) or nome)
    quem = contas.identidade(SERVICO, nome)
    contas.identificar(SERVICO, nome, rotulo=quem.get("rotulo") or "",
                       identificador=quem.get("id") or "",
                       extra={"arroba_esperada": esperado})
    perfil = perfil_da_conta(canal)
    print(f"[instagram] canal {canal}: conta '{nome}', @ esperado "
          f"@{esperado}; perfil {perfil}")
    resultado = {"ok": False, "esperado": esperado, "arroba": "", "motivo": ""}
    with contexto_persistente(headless=False, visivel=True,
                              profile=perfil) as ctx:
        page = _abrir(ctx, URL_INICIO)
        trazer_para_a_tela(perfil)
        print(f"[instagram] entre no @{esperado} nesta janela; ela espera ate "
              f"{espera_s / 60:.0f} min e fecha sozinha quando eu conferir o @.")
        fim = time.monotonic() + espera_s
        sessao = False
        while time.monotonic() < fim:
            time.sleep(3)
            try:
                cookies = {c.get("name") for c in
                           ctx.cookies("https://www.instagram.com")}
                sessao = "sessionid" in cookies
                if sessao:
                    break
            except Exception:                                  # noqa: BLE001
                resultado["motivo"] = "a janela foi fechada antes do login"
                return resultado
        if not sessao:
            resultado["motivo"] = "tempo esgotado sem login"
            print("[instagram] tempo esgotado sem login.")
            return resultado
        time.sleep(4)
        try:
            ir_para(page, URL_INICIO, tentativas=2,
                    log=lambda t: print(f"[instagram] {t}", flush=True))
        except AberturaFalhou:
            pass
        lido, motivo = "", ""
        fim = time.monotonic() + 60
        while time.monotonic() < fim:
            lido, motivo = ler_arroba(page)
            if lido:
                break
            time.sleep(2)
        resultado["arroba"] = lido
        escrita.fotografar(page, "instagram_login")
        if not lido:
            resultado["motivo"] = f"nao consegui ler o @ na tela ({motivo})"
        elif lido != esperado:
            resultado["motivo"] = (f"logou como @{lido}, mas o canal {canal} "
                                   f"e @{esperado}: NAO liguei o destino")
        else:
            contas.identificar(SERVICO, nome, rotulo=f"@{lido}",
                               identificador=lido,
                               extra={"arroba_esperada": esperado,
                                      "vivo_em": datetime.now().isoformat(
                                          timespec="seconds")})
            resultado["ok"] = True
        print("[instagram] " + ("login conferido: @" + lido + ". Destino LIGADO."
                                if resultado["ok"] else resultado["motivo"]))
        time.sleep(2)
    return resultado


# ---------------------------------------------------------- sonda e conferencia
def sondar(canal: str) -> Path:
    """Despeja o DOM da home (e da janela Criar) para ajustar seletor quando o
    site mudar. So le; o unico clique e abrir o menu Criar."""
    import json
    saida = (Path(__file__).resolve().parents[2] / "outputs" / "_identity" /
             f"probe_instagram_{time.strftime('%Y%m%d_%H%M%S')}.json")
    saida.parent.mkdir(parents=True, exist_ok=True)
    js = """() => ({
        url: location.href, titulo: document.title,
        arquivos: [...document.querySelectorAll('input[type=file]')]
            .map(i => ({accept: i.accept})),
        editaveis: [...document.querySelectorAll('[contenteditable=true]')]
            .map(e => ({role: e.getAttribute('role'),
                        aria: e.getAttribute('aria-label')})),
        links: [...document.querySelectorAll('a[href^="/"]')].slice(0, 40)
            .map(a => ({href: a.getAttribute('href'),
                        texto: (a.innerText || '').trim().slice(0, 30)})),
        botoes: [...document.querySelectorAll('button,[role=button]')]
            .map(b => (b.innerText || b.getAttribute('aria-label') || '')
                .trim().slice(0, 40)).filter(t => t).slice(0, 60),
        dialogos: [...document.querySelectorAll('[role=dialog]')].length})"""
    with contexto_persistente(headless=False,
                              profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_INICIO)
        time.sleep(8)
        dados = {"home": page.evaluate(js), "arroba": ler_arroba(page)}
        escrita.fotografar(page, "instagram_sonda_home")
        if tiktok._primeiro(page, BOTAO_CRIAR, timeout=4.0) is not None:
            tiktok._primeiro(page, BOTAO_CRIAR, timeout=1.0).click()
            time.sleep(2)
            dados["criar"] = page.evaluate(js)
            escrita.fotografar(page, "instagram_sonda_criar")
            page.keyboard.press("Escape")
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"[instagram] DOM despejado em {saida}")
    return saida


def conferir(canal: str) -> dict:
    """O login esta VIVO e os Reels do ledger estao NO AR? So le (home e o
    perfil da propria conta). Nao escreve no ledger."""
    from .. import contas
    from . import metricas
    laudo: dict = {}
    r = {"canal": canal, "vivo": False, "arroba": "", "no_ar": None,
         "ledger": 0, "faltam": [], "motivo": ""}
    if not ligado(canal):
        r["motivo"] = "destino desligado (sem conta com login conferido)"
        return r
    with contexto_persistente(headless=False,
                              profile=perfil_da_conta(canal)) as ctx:
        page = _abrir(ctx, URL_INICIO)
        _fechar_aviso(page, lambda t: print(f"[instagram] {t}"), laudo)
        try:
            r["arroba"] = conferir_identidade(
                page, canal, lambda t: print(f"[instagram] {t}"), laudo,
                "conferencia")
        except ContaErrada as exc:
            r["motivo"] = str(exc)
            return r
        r["vivo"] = True
        hrefs = _hrefs_do_perfil(page, r["arroba"])
    r["no_ar"] = len(hrefs)
    try:
        linhas = [l for l in metricas.publicados(canal)
                  if str(l.get("plataforma")) == "instagram"
                  and metricas.publicado(l)]
    except Exception:                                          # noqa: BLE001
        linhas = []
    r["ledger"] = len(linhas)
    codigos = {h.rstrip("/").rsplit("/", 1)[-1] for h in hrefs}
    r["faltam"] = [l.get("video_id") for l in linhas
                   if "/reel/" in str(l.get("url") or "")
                   and str(l["url"]).rstrip("/").rsplit("/", 1)[-1]
                   not in codigos]
    quem = contas.identidade(SERVICO, conta_do_canal(canal) or "")
    contas.identificar(SERVICO, conta_do_canal(canal), rotulo=quem.get("rotulo", ""),
                       identificador=quem.get("id", ""),
                       extra={"arroba_esperada": arroba_esperada(canal),
                              "vivo_em": datetime.now().isoformat(
                                  timespec="seconds")})
    return r


def main(argv=None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="python -m builds.publicar.instagram",
        description="Instagram (Reels): login, sonda, status e conferencia. "
                    "NAO publica: quem publica e o ferramentas/postar.py.")
    parser.add_argument("--canal", default="bluelock")
    parser.add_argument("--conta", help="nome/@ da conta (so no --login)")
    parser.add_argument("--arroba", help="@ esperado, se diferir do nome")
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--sondar", action="store_true")
    parser.add_argument("--conferir", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--forcar", action="store_true",
                        help="ignora a janela das postagens (sonda/conferir)")
    args = parser.parse_args(argv)

    if args.status or not (args.login or args.sondar or args.conferir):
        print(json.dumps(status(args.canal), ensure_ascii=False, indent=2))
        return 0
    if (args.sondar or args.conferir) and not args.forcar:
        from .. import janela
        recusa = janela.recusa("instagram " + ("sondar" if args.sondar
                                               else "conferir"))
        if recusa:
            print(recusa)
            return 2
    try:
        if args.login:
            return 0 if login(args.canal, conta=args.conta,
                              arroba=args.arroba)["ok"] else 1
        if args.sondar:
            sondar(args.canal)
            return 0
        print(json.dumps(conferir(args.canal), ensure_ascii=False, indent=2))
        return 0
    except InstagramFalhou as exc:
        print(f"FALHOU: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ContaErrada", "InstagramFalhou", "SUCESSO", "arroba_esperada",
           "confirmado", "conferir", "legenda_do_video", "ligado", "login",
           "publicar", "sondar", "status"]
