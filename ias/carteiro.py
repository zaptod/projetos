# -*- coding: utf-8 -*-
"""O CARTEIRO: entrega as mensagens do correio a cada IA e traz a resposta.

    python -m ias carteiro [--uma-vez] [--duble] [--intervalo S]

Processo proprio, fora do servidor do app: pega a proxima mensagem pendente
(`correio.proxima_pendente`), pega a TRAVA da conta, abre o cliente da IA no
chat "casa", envia, espera a resposta, grava, solta a trava. As regras:

  PRIORIDADE      decisao `ias-prioridade-conversa` (29/09/2026): quando o
                  Adrian fala com uma IA e a pipeline precisa da mesma conta,
                  ELE tem prioridade. Na pratica: o carteiro segura a conta
                  enquanto entrega e ainda por `janela_conversa_s` depois,
                  esperando a proxima mensagem dele — a pipeline, que pede a
                  trava com paciencia curta, cai para outro provedor. Se a
                  pipeline JA estiver com a conta, o carteiro espera (e
                  registra "esperando a pipeline soltar"); NUNCA mata nada.
  CASA            decisao `ias-chat-persistente`: um chat de longa duracao
                  por IA. `casa.json` guarda a URL; reabrir = navegar para
                  ela e provar que a conversa carregou (um turno nosso na
                  tela e a URL sem redirecionar). A cada `resumo_a_cada`
                  mensagens a IA resume o que foi combinado
                  (`casa_resumo.md`); se a casa ficar inutilizavel, comeca
                  uma casa nova com o resumo como primeira mensagem.
  UM NAVEGADOR    uma entrega por vez, um Chrome por vez.
  ERRO LEGIVEL    recusa de cota, parede, Cloudflare, login caido: o texto da
                  tela passa por `catalogo.classificar` e pela ficha da IA e
                  vira `erro` + `categoria` na mensagem, nao um traceback.
  DIARIO          cada turno vai ao `atividade.jsonl` pelo proprio cliente
                  (`papel=conversa`, `ref=Adrian`): a Vila mostra o
                  habitante "conversa Adrian".
  TELEGRAM        a resposta vai ao Telegram quando o app NAO esta olhando a
                  caixa daquela IA (`correio.app_esta_olhando`).

Tudo o que abre navegador e injetavel (`fabrica_de_sessao`, `trava`,
`avisar`, `dormir`): os testes usam um dublê e nunca abrem Chrome.
"""
from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import catalogo, correio, ficha as fichas

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
# Quanto cada tentativa de trava espera antes de o carteiro voltar a pulsar.
PASSO_TRAVA_S = 20.0
# Ocioso, o carteiro deixa uma linha no log a cada tanto (maquina.md #3).
PULSO_OCIOSO_S = 300.0

PEDIDO_RESUMO = (
    "PEDIDO DE TEXTO: resuma em até 12 linhas o que combinamos nesta conversa "
    "até aqui (decisões, pendências, preferências e o contexto que eu deveria "
    "colar numa conversa nova). Só o resumo, sem introdução.")
PROLOGO_CASA_NOVA = (
    "PEDIDO DE TEXTO: esta é a continuação da nossa conversa anterior, que "
    "ficou longa. Abaixo está o resumo do que combinamos. Responda só OK e "
    "guarde o contexto.\n\n")

PADRAO_CONFIG = {"resumo_a_cada": 12, "janela_conversa_s": 90,
                 "espera_conta_max_s": 10800, "resposta_timeout_s": 420,
                 "intervalo_s": 5, "headless": {}}

# O turno "responda OK" que leva o resumo para a casa nova: resposta curta,
# prazo curto (05/10 04:54Z: ele ficou os 420 s inteiros sem resposta).
PRAZO_PROLOGO_S = 90.0
# Resumo mais velho que isto nao entra numa casa nova (o contexto envelheceu),
# e resumo curto ou de recusa nunca e gravado nem injetado: o
# `gemini/casa_resumo.md` de 02/10 era so "Não fui programado para fazer
# essas coisas." e abria toda casa nova do Gemini.
RESUMO_VALIDADE_S = 48 * 3600.0
RESUMO_MINIMO = 40
# A recuperacao da imagem depois de o Chrome cair: o Gemini so carrega a
# imagem quando ela entra na vista, entao rola e le de novo ate o prazo
# (25 de 25 recuperacoes falharam em 04-05/10 com UMA leitura logo apos o goto).
RECUPERAR_PRAZO_S = 60.0
RECUPERAR_PASSO_S = 3.0
# Pedido reservado por um processo que morreu: o carteiro marca falhou (quem
# pediu nao vai ler), no maximo uma varredura por este intervalo.
VARRER_ABANDONADAS_S = 60.0
# Mensagem "entregue" por um carteiro que morreu (IAS-4): ate este tempo ela
# volta para a fila; mais velha, so falha (ninguem espera mais a resposta).
RETOMAR_ORFA_MAX_S = 6 * 3600.0

# Segmentos de URL que sao a RAIZ do site (chat sem conversa ainda):
# chatgpt.com/, chatgpt.com/?model=auto, gemini.google.com/app, grok.com/.
_SEGMENTOS_DA_RAIZ = {"app", "chat", "new", "a", "c", "s", "u", "g", "home"}


def e_raiz(url: str) -> bool:
    """A URL e a raiz do site (nenhuma conversa aberta)? Vazio conta como raiz.

    05/10/2026: `_abrir_casa` gravava a URL ANTES do primeiro turno, quando o
    site ainda mostra a raiz; a casa "reaberta" na entrega seguinte nao tinha
    nenhum turno nosso e virava casa nova: geracao 71 no Gemini, 59 no
    ChatGPT, 56 vezes "a casa abriu sem nenhum turno nosso" no log."""
    texto = str(url or "").strip()
    if not texto:
        return True
    caminho = re.sub(r"^[a-z]+://[^/?#]*", "", texto, flags=re.I)
    caminho = re.sub(r"[?#].*$", "", caminho)
    anterior = ""
    for segmento in (s for s in caminho.split("/") if s):
        baixo = segmento.lower()
        # `u/1` e o indice da conta Google (gemini.google.com/u/1/app)
        if baixo in _SEGMENTOS_DA_RAIZ or (anterior == "u" and baixo.isdigit()):
            anterior = baixo
            continue
        return False
    return True


_RECUSA_RESERVA = re.compile(
    r"n[aã]o fui (programad|criad)|sou (apenas |s[oó] )?(um modelo de linguagem|uma ia)|"
    r"al[eé]m das minhas capacidades|n[aã]o posso (te )?ajudar com isso|"
    r"I'?m (just )?a language model|can'?t help with that", re.I)


def e_recusa(texto: str) -> bool:
    """A frase enlatada de "isso eu nao faco" (a mesma lista das historias)."""
    try:
        from contos.llm import texto as llm_texto
        if llm_texto.e_recusa_enlatada(texto):
            return True
    except Exception:                                          # noqa: BLE001
        pass
    limpo = " ".join(str(texto or "").split())
    return bool(limpo) and len(limpo) <= 400 and bool(_RECUSA_RESERVA.search(limpo))


def resumo_aceitavel(texto: str) -> bool:
    """Resumo que vale guardar/injetar: nao curto e nao recusa."""
    corpo = "\n".join(linha for linha in str(texto or "").splitlines()
                      if not linha.lstrip().startswith("# Resumo da casa"))
    limpo = " ".join(corpo.split())
    return len(limpo) >= RESUMO_MINIMO and not e_recusa(limpo)


_CHROME_CAIU = re.compile(r"TargetClosed|Target page, context or browser has been closed|"
                          r"[Bb]rowser has been closed|Chrome (caiu|fechou)")


def chrome_caiu(exc: BaseException | None) -> bool:
    """O navegador fechou no meio (o download do Gemini, 04-05/10): olha o
    tipo e o texto da excecao e das que ela embrulha."""
    vistos = 0
    while exc is not None and vistos < 6:
        if _CHROME_CAIU.search(type(exc).__name__ + " " + str(exc)):
            return True
        exc = exc.__cause__ or exc.__context__
        vistos += 1
    return False


def _perguntar_com_prazo(sessao, texto: str, prazo_s: float) -> str:
    """`sessao.perguntar` com prazo proprio, se a sessao aceita `prazo_s`."""
    perguntar = sessao.perguntar
    try:
        import inspect
        aceita = "prazo_s" in inspect.signature(perguntar).parameters
    except (TypeError, ValueError):
        aceita = False
    return perguntar(texto, prazo_s=prazo_s) if aceita else perguntar(texto)


def _aceita_imagem(funcao) -> bool:
    try:
        import inspect
        return "imagem" in inspect.signature(funcao).parameters
    except (TypeError, ValueError):
        return False


def _chat_de_imagem(novo) -> None:
    """`novo_chat` para um pedido de IMAGEM: sem trocar o modelo, se a sessao
    sabe (HIS-11, 11/10/2026: a troca refeita a cada imagem somou ~1,9 h em
    06-08/10, mediana de 32 s por chat)."""
    if _aceita_imagem(novo):
        novo(imagem=True)
    else:
        novo()


def _reabrir_conversa_de_imagem(sessao, url: str) -> bool:
    """`abrir_casa` na conversa propria de uma imagem, sem trocar o modelo."""
    abrir = sessao.abrir_casa
    return bool(abrir(url, imagem=True) if _aceita_imagem(abrir) else abrir(url))


def config() -> dict:
    base = dict(PADRAO_CONFIG)
    try:
        with open(CONFIG, encoding="utf-8-sig") as fh:
            dados = json.load(fh)
        if isinstance(dados, dict):
            base.update({k: v for k, v in dados.items() if not k.startswith("_")})
    except (OSError, ValueError):
        pass
    return base


def _tempo_legivel(segundos: float) -> str:
    """Duracao para gente: "45 s", "12 min", "3 h". Ate 07/10/2026 a espera
    pela conta saia sempre em horas inteiras, e 10 min virava "0 h"."""
    segundos = max(0.0, float(segundos))
    if segundos < 90:
        return f"{segundos:.0f} s"
    if segundos < 5400:
        return f"{segundos / 60:.0f} min"
    return f"{segundos / 3600:.1f} h".replace(".0 h", " h").replace(".", ",")


def _log_padrao(msg: str) -> None:
    print(f"{datetime.now():%d/%m %H:%M:%S} {msg}", flush=True)


# ================================================================ sessoes
class SessaoReal:
    """Uma IA aberta no navegador, por cima do `ClienteLLM` das historias."""

    def __init__(self, cliente, log=_log_padrao):
        self.cliente = cliente
        self.log = log
        # a pagina ANTES do envio (e o que enviamos): o classificador de erro
        # so le o que surgiu depois (`texto_do_turno`), nunca o rodape fixo
        self._antes: list | None = None

    def _marcar_antes(self, *enviado) -> None:
        self._antes = [self.texto_visivel(), *(str(t or "") for t in enviado)]

    @property
    def modelo(self) -> str:
        return getattr(self.cliente, "modelo_atual", "") or ""

    @property
    def modelo_confirmado(self) -> bool:
        """O chat esta no modelo forte? (IAS-9). `modelo_forte` do cliente
        (HIS-2: o 2o da lista ou a conta sem o Pro NAO e forte); cliente sem o
        atributo = `modelo_confirmado`; sem nenhum dos dois, True."""
        forte = getattr(self.cliente, "modelo_forte", None)
        if forte is None:
            forte = getattr(self.cliente, "modelo_confirmado", True)
        return bool(forte)

    def _sem_query(self, url: str) -> str:
        return re.sub(r"[?#].*$", "", str(url or "")).rstrip("/")

    def abrir_casa(self, url: str, imagem: bool = False) -> bool:
        """Reabre o chat da casa. True so com PROVA de que a conversa carregou.

        `imagem=True` (a conversa propria de uma imagem, na recuperacao) nao
        mexe no modelo (HIS-11)."""
        from contos.llm import seletores as sel
        c = self.cliente
        site = self._sem_query(c.sel["url"])
        if not url or not self._sem_query(url).startswith(site.rsplit("/", 1)[0]):
            return False
        c.page.goto(url, wait_until="domcontentloaded",
                    timeout=int(float(c.ajustes.get("navigation_timeout", 90)) * 1000))
        c._esperar_montar()
        # login caido SO com a tela de login na frente; a pagina que nao
        # montou (30/09, o grok.com em branco) e `SiteIndisponivel`
        c.conferir_sessao()
        turno = sel.encontrar_oculto(c.page, c.sel.get("turno_usuario") or [], timeout=10.0)
        if turno is None:
            self.log(f"[carteiro] {c.provedor}: a casa abriu sem nenhum turno nosso na tela")
            return False
        if self._sem_query(c.page.url) != self._sem_query(url):
            self.log(f"[carteiro] {c.provedor}: a casa redirecionou para {c.page.url}")
            return False
        c.turnos = 0
        c._ultima_resposta = ""
        c.modelo_atual = c.escolher_modelo(False if imagem else None)
        return True

    def novo_chat(self, imagem: bool = False) -> None:
        """Chat novo. `imagem=True` nao troca o modelo (HIS-11): o pedido de
        imagem nao precisa do Pro, e a troca custava ~32 s por chat."""
        self.cliente.abrir(novo_chat=True, trocar_modelo=not imagem)

    def perguntar(self, texto: str, anexos=None, prazo_s: float | None = None) -> str:
        c = self.cliente
        if anexos and not (c.sel.get("anexo_prova") or []):
            from contos.llm.cliente import LLMFalhou
            raise LLMFalhou(
                f"o cliente do {c.provedor} ainda nao sabe confirmar anexo na tela "
                "(seletores `anexo_prova` vazios em contos/llm/seletores.py): mande sem anexo")
        self._marcar_antes(texto)
        if prazo_s:
            return c.perguntar(texto, timeout=float(prazo_s),
                               anexos=list(anexos) if anexos else None)
        return c.perguntar(texto, anexos=list(anexos) if anexos else None)

    def gerar_imagem(self, prompt: str, proporcao: str, mensagem_id: str = "",
                     anexos=None) -> dict:
        """Pede a imagem NA CASA (o chat ja aberto) e baixa a que nasce depois
        do nosso turno (`imagem.gerar_no_chat`, pelo `perguntar` de sempre: o
        turno vai ao diario como os de texto)."""
        from . import imagem
        self._marcar_antes(imagem.pedido_de_imagem(prompt, proporcao))
        return imagem.gerar_no_chat(self.cliente, prompt, proporcao,
                                    anexos=anexos, log=self.log)

    def imagem_da_resposta(self, prompt: str) -> dict | None:
        """A imagem que a ULTIMA resposta de conversa trouxe (o Gemini que
        desenha quando ele pede "gere um gato"), ou None."""
        from . import imagem
        return imagem.baixar_da_resposta(self.cliente, prompt, log=self.log)

    # Rola cada area com rolagem propria ate o fim e poe a ULTIMA imagem gerada
    # na vista: o Gemini so carrega a imagem que esta na vista.
    _JS_ROLAR_PARA_A_IMAGEM = (
        "(seletores) => {"
        " for (const el of document.querySelectorAll('*')) {"
        "   const st = getComputedStyle(el);"
        "   if (/(auto|scroll)/.test(st.overflowY) && el.scrollHeight > el.clientHeight + 40)"
        "     el.scrollTop = el.scrollHeight; }"
        " window.scrollTo(0, document.body ? document.body.scrollHeight : 0);"
        " let ultima = null;"
        " for (const s of seletores) {"
        "   try { const els = document.querySelectorAll(s);"
        "         if (els.length) ultima = els[els.length - 1]; } catch (e) {} }"
        " if (ultima) ultima.scrollIntoView({block: 'center'});"
        " return !!ultima; }")

    def _rolar_para_a_imagem(self) -> None:
        c = self.cliente
        try:
            c.page.evaluate(self._JS_ROLAR_PARA_A_IMAGEM,
                            list((getattr(c, "sel", None) or {}).get("imagem_gerada") or []))
        except Exception:                                      # noqa: BLE001
            pass

    def recuperar_imagem(self, prompt: str, proporcao: str, prazo_s: float | None = None,
                         passo_s: float | None = None) -> dict:
        """Baixa a imagem ja pronta na conversa reaberta, sem novo envio a IA.

        Le de novo, rolando ate a imagem, por ate `RECUPERAR_PRAZO_S`: uma
        leitura so, logo depois do goto, falhava sempre (25 de 25 em
        04-05/10) porque a imagem ainda nao tinha carregado."""
        from . import imagem
        c = self.cliente
        prazo = RECUPERAR_PRAZO_S if prazo_s is None else max(0.0, float(prazo_s))
        passo = RECUPERAR_PASSO_S if passo_s is None else max(0.1, float(passo_s))
        leituras = max(1, int(prazo // passo) + 1)
        pedido = imagem.pedido_de_imagem(prompt, proporcao)
        visto = ""
        for n in range(1, leituras + 1):
            self._rolar_para_a_imagem()
            achado = c.imagens_da_resposta() or {}
            prontas = c.imagens_prontas(achado)
            if prontas:
                c.imagens_na_resposta = prontas
                c._srcs_antes_do_envio = set()
                saida = imagem.baixar_da_resposta(c, pedido, proporcao, log=self.log)
                if saida is not None:
                    self.log(f"[carteiro] {c.provedor}: imagem recuperada na conversa "
                             f"reaberta (leitura {n}/{leituras})")
                    return saida
            estado = getattr(c, "_estado_da_imagem", None)
            if callable(estado):
                try:
                    visto = estado(achado, prontas) or visto
                except Exception:                              # noqa: BLE001
                    pass
            if n < leituras:
                c.page.wait_for_timeout(int(passo * 1000))
        raise imagem.SemImagem(
            f"a imagem nao apareceu na conversa reaberta em {prazo:.0f}s ({leituras} "
            f"leituras com rolagem; a ultima viu: {visto or 'nenhuma imagem na resposta'})")

    def url(self) -> str:
        try:
            return str(self.cliente.page.url or "")
        except Exception:                                      # noqa: BLE001
            return ""

    def texto_visivel(self) -> str:
        try:
            return self.cliente.page.evaluate(
                "() => document.body ? document.body.innerText : ''") or ""
        except Exception:                                      # noqa: BLE001
            return ""

    def texto_do_turno(self) -> str:
        """So o que a pagina ganhou desde o envio (a resposta do nosso turno e
        o aviso que surgiu depois). Sem envio marcado: nada — a pagina inteira
        traz botoes fixos ("Fazer upgrade" no rodape do Free) que nao sao o
        motivo de falha nenhuma (30/09: 82e154e4 e 5030f732)."""
        if self._antes is None:
            return ""
        return catalogo.linhas_novas(self._antes, self.texto_visivel())


def tela_do_turno(sessao) -> str:
    """O texto que o classificador de erro le: o do nosso turno quando a
    sessao sabe separa-lo, senao o visivel (dubles antigos)."""
    ler = getattr(sessao, "texto_do_turno", None)
    if not callable(ler):
        ler = getattr(sessao, "texto_visivel", None)
    if not callable(ler):
        return ""
    try:
        return str(ler() or "")
    except Exception:                                          # noqa: BLE001
        return ""


@contextmanager
def sessao_real(ia: str, *, headless: bool = False, log=_log_padrao,
                resposta_timeout_s: float = 420.0):
    """Abre a IA no perfil dela (a trava e reentrante: quem chama ja a tem)."""
    from contos.llm.cliente import abrir_cliente
    with abrir_cliente(ia, headless=headless, esperar=PASSO_TRAVA_S, log=log,
                       papel="conversa", ref="Adrian", canal="adrian",
                       ajustes={"resposta_timeout": float(resposta_timeout_s)}) as cliente:
        yield SessaoReal(cliente, log)


class SessaoDuble:
    """O dublê: responde sem navegador. `respostas` e uma funcao texto->texto
    (ou um texto fixo); `falhar` e uma excecao a levantar; `tela` e o texto
    'visivel' depois da falha; `tela_antes` e a pagina antes do envio (o
    rodape fixo): o classificador so le o que `tela` tem a mais."""

    def __init__(self, ia: str, *, responder=None, falhar=None, tela: str = "",
                 casa_abre: bool = True, demora_s: float = 0.0, dormir=time.sleep,
                 imagem_falhar=None, imagem_sem_prova: bool = False,
                 responder_com_imagem: bool = False, tela_antes: str = "",
                 antes_de_gerar=None, imagem_prova_extra: dict | None = None):
        self.ia = ia
        self.antes_de_gerar = antes_de_gerar
        self.tela_antes = tela_antes
        self.responder_com_imagem = responder_com_imagem
        self.responder = responder or (lambda texto: "OK (dublê)")
        self.falhar = falhar
        self.tela = tela
        self.casa_abre = casa_abre
        self.demora_s = demora_s
        self.dormir = dormir
        self.modelo = "dublê"
        self.turnos: list = []
        self._url = ""
        # a conversa nova so ganha endereco no primeiro turno (como no site):
        # ate la `url()` e a raiz (05/10/2026)
        self._url_da_conversa = ""
        self.casas_novas = 0
        self.chats_de_imagem = 0
        from .imagem import SessaoImagemDuble
        # a imagem na casa: o mesmo dublê do PicassoIA, sem navegador
        self._imagem = SessaoImagemDuble(ia, falhar=imagem_falhar,
                                         sem_prova=imagem_sem_prova, tela=tela,
                                         demora_s=demora_s, dormir=dormir,
                                         prova_extra=imagem_prova_extra)

    def _comecar_conversa(self) -> None:
        if self._url_da_conversa:
            self._url, self._url_da_conversa = self._url_da_conversa, ""
        if self.turnos:
            self.turnos[-1]["url"] = self._url      # em que conversa foi o turno

    def gerar_imagem(self, prompt: str, proporcao: str, mensagem_id: str = "",
                     anexos=None) -> dict:
        self.turnos.append({"texto": prompt, "anexos": [], "imagem": proporcao})
        self._comecar_conversa()
        if self.antes_de_gerar:
            self.antes_de_gerar(prompt)          # o teste pode recusar a 1a vez
        return self._imagem.gerar_imagem(prompt, proporcao, mensagem_id)

    def imagem_da_resposta(self, prompt: str) -> dict | None:
        """Com `responder_com_imagem`, a resposta de conversa traz uma imagem
        (o dublê do Gemini desenhando o gato)."""
        if not self.responder_com_imagem:
            return None
        return self._imagem.gerar_imagem(prompt, "1:1")

    def abrir_casa(self, url: str, imagem: bool = False) -> bool:
        if imagem:
            self.chats_de_imagem += 1
        if url and self.casa_abre:
            self._url = url
            self._url_da_conversa = ""
            return True
        return False

    def novo_chat(self, imagem: bool = False) -> None:
        # quantos chats foram abertos SEM trocar o modelo (HIS-11)
        if imagem:
            self.chats_de_imagem += 1
        self.casas_novas += 1
        self._url = "https://duble.local/"
        self._url_da_conversa = (f"https://duble.local/{self.ia}/c/"
                                 f"{self.casas_novas}-{int(time.time())}")

    def perguntar(self, texto: str, anexos=None, prazo_s: float | None = None) -> str:
        self.turnos.append({"texto": texto, "anexos": list(anexos or []), "prazo_s": prazo_s})
        self._comecar_conversa()
        if self.demora_s:
            self.dormir(self.demora_s)
        if self.falhar is not None:
            raise self.falhar
        if callable(self.responder):
            return str(self.responder(texto))
        return str(self.responder)

    def url(self) -> str:
        return self._url

    def texto_visivel(self) -> str:
        return self.tela

    def texto_do_turno(self) -> str:
        enviados = [t.get("texto") or "" for t in self.turnos[-1:]]
        return catalogo.linhas_novas([self.tela_antes, *enviados], self.tela)


def fabrica_duble(**ajustes):
    """Uma fabrica de sessoes dublê com os mesmos ajustes para toda IA."""
    criadas = []

    @contextmanager
    def _abrir(ia):
        sessao = SessaoDuble(ia, **ajustes)
        criadas.append(sessao)
        yield sessao

    _abrir.criadas = criadas
    return _abrir


# ============================================================= erro legivel
CATEGORIAS_DE_TELA = ("limite", "upgrade", "cloudflare", "indisponivel",
                      "erro_site", "conteudo", "login", "parede")


def motivo_da_tela(ia: str, tela: str = "") -> tuple | None:
    """(categoria, motivo) se a tela mostra um texto conhecido (a ficha da IA,
    depois o catalogo geral); None se nao."""
    tela_baixa = " ".join(str(tela or "").split()).lower()
    if not tela_baixa:
        return None
    try:
        conhecidos = fichas.carregar(ia).get("catalogo_textos") or []
    except Exception:                                          # noqa: BLE001
        conhecidos = []
    for item in conhecidos:
        texto = " ".join(str(item.get("texto") or "").split()).lower()
        if (item.get("categoria") in CATEGORIAS_DE_TELA and len(texto) >= 12
                and re.search(r"(?<!\w)" + re.escape(texto) + r"(?!\w)", tela_baixa)):
            return (item["categoria"], f"o site diz: «{item['texto'][:160]}»")
    for item in catalogo.varrer(str(tela)):
        if item["categoria"] in CATEGORIAS_DE_TELA:
            return (item["categoria"], f"o site diz: «{item['texto'][:160]}»")
    return None


# A internet caiu, nao o site: volta para a fila (02/10/2026)
REDE_CAIU = re.compile(r"net::ERR_(NAME_NOT_RESOLVED|INTERNET_DISCONNECTED|NETWORK_CHANGED|"
                       r"CONNECTION_(RESET|CLOSED|REFUSED|TIMED_OUT)|TIMED_OUT|ADDRESS_UNREACHABLE)")
REDE_TENTATIVAS = 5
AVISO_PREVIA = "prévia (o original não baixou)"
MOTIVO_REDE = "a rede caiu (DNS/internet); tente de novo quando voltar"


def rede_caiu(exc: BaseException | None) -> bool:
    """A excecao (ou uma que ela embrulha) e a internet/DNS que caiu?"""
    vistos = 0
    while exc is not None and vistos < 6:
        if REDE_CAIU.search(type(exc).__name__ + " " + str(exc)):
            return True
        exc = exc.__cause__ or exc.__context__
        vistos += 1
    return False


REFORCO_IMAGEM = ("GERE UMA IMAGEM (não responda com texto; use a geração de imagem). "
                  "A imagem pedida é esta:\n")


def classificar_erro(ia: str, exc: BaseException, tela: str = "") -> tuple:
    """(categoria, motivo legivel) de uma entrega que falhou.

    A ordem: o tipo da excecao (login caido, conta ocupada), depois os textos
    conhecidos da FICHA da IA (`catalogo_textos`, medidos na fase 1), depois
    o que a tela mostra agora (`catalogo.varrer`), e so entao a excecao crua.
    "limite" exige evidencia da tela: um palpite na excecao nao pausa a IA.
    """
    nome = type(exc).__name__
    if nome == "NaoLogado":
        return ("login", f"a sessão do {correio.ROTULOS.get(ia, ia)} caiu no PC: "
                         f"faça login de novo (python main.py llm login --provedor {ia})")
    if nome == "ContaOcupada":
        return ("conta_ocupada", "a conta está em uso pela pipeline; tente de novo")
    if nome == "SiteIndisponivel":
        # o card "Alta procura" do Grok (29/09): o cliente ja leu o aviso
        # no nosso turno; nao cai no `tente novamente` generico (erro_site)
        return ("indisponivel", " ".join(str(exc).split())[:400])
    if rede_caiu(exc):
        # a internet/DNS caiu, nao o site nem a IA (IAS-2)
        return ("rede", MOTIVO_REDE)
    achado = motivo_da_tela(ia, tela)
    if achado:
        return achado
    if getattr(exc, "legivel", False):
        # a mensagem ja e a frase para o Adrian (`AnexoRecusado`, 14/10/2026)
        return (getattr(exc, "categoria", None) or "erro",
                " ".join(str(exc).split())[:400])
    mensagem = " ".join(str(exc).split())[:220]
    categoria = catalogo.classificar(mensagem)
    # A excecao pode orientar quem vai olhar a janela, mas nao e evidencia de
    # cota. So `motivo_da_tela`, acima, pode marcar limite.
    if categoria == "limite":
        categoria = None
    categoria = categoria or "erro"
    if detalhe_tecnico(exc):
        # erro do navegador/Python: o app e o Telegram recebem a frase; a
        # excecao crua vai so ao log (quem chama loga `detalhe_tecnico`)
        return (categoria, frase_do_erro_tecnico(ia, exc))
    return (categoria, f"{nome}: {mensagem}" if mensagem else nome)


# Pacotes NOSSOS: as excecoes deles ja falam com o Adrian (LLMFalhou,
# ImagemFalhou...). O resto (Playwright, Python) e detalhe tecnico.
_PACOTES_NOSSOS = ("contos", "ias", "builds", "remoto", "coordenador", "historias",
                   "random_builds", "neural_fights", "painel", "vila")


def detalhe_tecnico(exc: BaseException) -> str:
    """"Classe: mensagem" da excecao crua quando ela NAO e nossa (Playwright,
    Python); "" quando a mensagem ja e legivel. Vai so para o log."""
    modulo = str(getattr(type(exc), "__module__", "") or "")
    if getattr(exc, "legivel", False) or modulo.split(".")[0] in _PACOTES_NOSSOS:
        return ""
    texto = " ".join(str(exc).split())[:600]
    return f"{type(exc).__name__}: {texto}" if texto else type(exc).__name__


def frase_do_erro_tecnico(ia: str, exc: BaseException) -> str:
    """O erro do navegador em portugues simples (14/10/2026: o app mostrava
    "Error: Locator.set_input_files: Error: Non-multiple file input...")."""
    rotulo = correio.ROTULOS.get(ia, ia)
    bruto = (type(exc).__name__ + " " + str(exc)).lower()
    if "set_input_files" in bruto or "file input" in bruto:
        frase = f"o {rotulo} não aceitou o anexo"
    elif "timeout" in bruto:
        frase = f"o {rotulo} demorou demais para responder na tela (tempo esgotado)"
    elif "closed" in bruto or "fechad" in bruto:
        frase = f"o navegador do {rotulo} fechou no meio do pedido"
    else:
        frase = f"o {rotulo} deu um erro inesperado no navegador"
    return frase + "; o detalhe técnico ficou no log do carteiro"


# ================================================================= carteiro
class _Reabrir(Exception):
    """Parede de planos na primeira volta: fechar o navegador e reabrir."""


class _ReabrirImagem(Exception):
    """O Chrome caiu baixando: reabre uma vez sem pedir a imagem de novo."""

    def __init__(self, caixa: str, mensagem: dict):
        self.caixa, self.mensagem = caixa, mensagem


class Carteiro:
    """`de_servico=True` so no carteiro de SERVICO (`python -m ias carteiro`).

    O padrao (False) e o Carteiro sincrono dos workers (historias, identity),
    que chamam `entregar()` direto e leem a resposta na hora (IAS-2/IAS-6,
    auditoria de 11/10/2026). Ele:
      - nao grava `carteiro.json` (o estado do app e do supervisor e o do
        servico; o worker sobrescrevia com o PID dele);
      - escreve no diario pelo canal `pipeline`, nao `adrian`;
      - nunca devolve o pedido `pendente`: "volta para a fila" so faz sentido
        no laco do servico (a rede que cai vira falha `rede`; o pedido que
        sobra pendente/entregue no fim vira `interrompida`);
      - nao avisa no Telegram (quem pediu le a resposta na hora)."""

    def __init__(self, *, fabrica_de_sessao=None, trava=None, nome_da_trava=None,
                 avisar=None, log=_log_padrao, dormir=time.sleep, relogio=time.monotonic,
                 ajustes: dict | None = None, fabrica_imagem=None, avisar_arquivo=None,
                 de_servico: bool = False):
        self.de_servico = bool(de_servico)
        # o que QUEM CHAMOU fixou vale sempre; o resto vem do config.json, que
        # o servico rele a cada volta (IAS-7: editar `cota_pausa_h` so valia
        # depois de reiniciar)
        self._ajustes_do_chamador = dict(ajustes or {})
        self.ajustes = {**config(), **self._ajustes_do_chamador}
        self.fabrica = fabrica_de_sessao or self._fabrica_real
        # o PicassoIA (gerador que nao e chat): outra sessao, outro cliente
        self.fabrica_imagem = fabrica_imagem or self._fabrica_imagem_real
        self.trava = trava or self._trava_real
        self.nome_da_trava = nome_da_trava or self._nome_da_trava_real
        # a situacao em texto ("entregue", "calado", "enfileirado"...) vai ao
        # log (IAS-8): o porteiro que cala nao e "entregue"
        self.avisar = avisar if avisar is not None else avisar_telegram_situacao
        self.avisar_arquivo = (avisar_arquivo if avisar_arquivo is not None
                               else avisar_telegram_arquivo)
        self.log = log
        self.dormir = dormir
        self.relogio = relogio
        self.entregues = 0
        self._ultimo_pulso = 0.0
        # a casa da sessao aberta agora: so abre no primeiro turno de TEXTO
        self._casa: dict | None = None
        self._fora_da_casa = False
        self._ultima_varredura: float | None = None
        self._ultimo_pulso_ocioso = 0.0

    # ------------------------------------------------------------ real
    def _fabrica_real(self, ia: str):
        headless = bool((self.ajustes.get("headless") or {}).get(ia, False))
        return sessao_real(ia, headless=headless, log=self.log,
                           resposta_timeout_s=float(self.ajustes.get("resposta_timeout_s", 420)))

    @staticmethod
    def _trava_real(nome: str, esperar: float):
        import builds.travas as travas
        return travas.trava(nome, esperar=esperar)

    def _fabrica_imagem_real(self, ia: str):
        from . import imagem
        if ia != "picasso":
            raise imagem.ImagemFalhou(
                f"{correio.ROTULOS.get(ia, ia)}: sem cliente de imagem", "indisponivel")
        headless = bool((self.ajustes.get("headless") or {}).get(ia, False))
        return imagem.sessao_picasso(headless=headless, log=self.log)

    @staticmethod
    def _nome_da_trava_real(ia: str) -> str:
        import builds.travas as travas
        # o PicassoIA das historias e o mesmo perfil do worker de builds: a
        # trava sai do CAMINHO do perfil, entao as duas pipelines e o
        # carteiro disputam a mesma
        return travas.do_perfil(ia, "historias" if ia == "picasso" else "geral")

    # ---------------------------------------------------------- estado
    def _estado(self, situacao: str, ia: str | None = None, mensagem_id: str | None = None,
                desde: str | None = None, nota: str = "") -> None:
        if not self.de_servico:
            # IAS-6: o Carteiro de um worker nao e o carteiro do app
            return
        try:
            correio.gravar_estado_do_carteiro({
                "situacao": situacao, "ia": ia, "mensagem_id": mensagem_id,
                "desde": desde or correio.agora(), "nota": nota,
                "entregues": self.entregues})
        except OSError:
            pass

    def _gravar_casa(self, ia: str, casa: dict) -> None:
        """`casa.json` que nao grava (o Windows tranca o arquivo aberto por
        outro processo) fica no log: a resposta ja obtida nao vira "falhou"
        por isso (IAS-5)."""
        try:
            correio.gravar_casa(ia, casa)
        except OSError as exc:
            self.log(f"[carteiro] {ia}: a casa não foi gravada ({type(exc).__name__}: "
                     f"{' '.join(str(exc).split())[:120]}); sigo")

    def _log_com_pulso(self, ia, mensagem_id, desde):
        """Um `log` para o cliente que tambem pulsa: a espera de uma resposta
        pode levar minutos, e sem pulso a Mesa diria 'parado'."""
        def _log(msg):
            self.log(msg)
            agora = self.relogio()
            if agora - self._ultimo_pulso >= 15:
                self._ultimo_pulso = agora
                self._estado("entregando", ia, mensagem_id, desde)
        return _log

    # --------------------------------------------------------- entrega
    def entregar(self, mensagem: dict) -> dict:
        """Entrega UMA mensagem pendente (e as que chegarem na janela).

        Pedido de imagem para a caixa `livre` e o RODIZIO: o carteiro escolhe
        o gerador na hora (`_entregar_livre`). Pedido de imagem para um
        gerador que a ficha diz que nao gera hoje falha na hora, com o motivo
        da ficha, sem abrir navegador.

        Fora do servico (`de_servico=False`) a mensagem devolvida nunca fica
        `pendente` nem `entregue` por este processo (IAS-2, 11/10/2026): quem
        chamou trata o retorno como final, e o pedido que sobrava reservado era
        entregue 4 h depois pelo servico (629 assim em 09/10), gastando a conta
        e mandando ao Telegram uma imagem que ninguem lia.
        """
        saida = self._entregar(mensagem)
        if self.de_servico:
            return saida
        return self._sem_sobra(mensagem, saida)

    def _sem_sobra(self, mensagem: dict, saida: dict) -> dict:
        """A rede de seguranca do Carteiro sincrono: o que sobrou `pendente`
        (livre ou reservado para mim) ou `entregue` por mim vira `falhou` /
        `interrompida`."""
        caixa, mid = str(mensagem["para"]), str(mensagem["id"])
        atual = correio.uma(caixa, mid)
        if atual is None:
            return saida
        situacao = atual.get("situacao")
        sobrou = ((situacao == "pendente" and not correio.reservado_por_outro(atual))
                  or (situacao == "entregue" and correio._entregador(atual) == os.getpid()))
        if not sobrou:
            return atual if situacao in ("respondida", "falhou") else saida
        ia = str(atual.get("gerador") or caixa)
        motivo = (f"a entrega terminou sem resposta (o pedido ficou {situacao}); "
                  "não volta para a fila: peça de novo")
        self.log(f"[carteiro] {caixa} {mid}: {motivo}")
        return self._falhar(caixa, ia, mid, motivo, "interrompida")

    def _entregar(self, mensagem: dict) -> dict:
        caixa = str(mensagem["para"])
        if correio.tipo(mensagem) == "imagem":
            if caixa == correio.LIVRE:
                return self._entregar_livre(mensagem)
            from . import imagem
            info = imagem.gerador(caixa)
            if not info["disponivel"]:
                return self._falhar(
                    caixa, caixa, str(mensagem["id"]),
                    f"{info['rotulo']} não gera imagem hoje: {info['motivo']}",
                    "indisponivel")
        return self._com_a_conta(caixa, caixa, mensagem)

    def _largou_na_espera(self, caixa: str, mensagem: dict) -> dict | None:
        """Relida a cada volta da ESPERA pela conta: se outra entrega ja a
        levou (respondida, falhou, entregue por outro) ou se ela ficou
        reservada para outro processo, devolve como esta e a espera acaba.
        05/10/2026: o 1b0e0ac6 ficou respondido pelo worker enquanto o carteiro
        de servico esperava a trava, e o estouro de 3 h o marcaria "falhou"
        com aviso falso no Telegram."""
        mid = str(mensagem["id"])
        atual = correio.uma(caixa, mid)
        if atual is None:
            return mensagem
        if atual.get("situacao") == "pendente" and not correio.reservado_por_outro(atual):
            return None
        self.log(f"[carteiro] {caixa} {mid}: ficou {atual.get('situacao')} enquanto eu "
                 "esperava a conta; largo a espera")
        return atual

    def _com_a_conta(self, caixa: str, ia: str, mensagem: dict) -> dict:
        """Pega a trava da conta de `ia` (esperando a pipeline, nunca matando)
        e entrega. `caixa` e onde a mensagem mora (a `livre`, no rodizio)."""
        mid = str(mensagem["id"])
        desde = correio.agora()
        nome = self.nome_da_trava(ia)
        inicio = self.relogio()
        limite = float(self.ajustes.get("espera_conta_max_s", 10800))
        avisou = False
        while True:
            # "entregando" so com a conta na mao (`_entregar_com_a_conta`):
            # antes a 1a volta ja dizia "entregando" so esperando a trava (IAS-6)
            self._estado("esperando_trava", ia, mid, desde,
                         nota=(f"esperando a pipeline soltar a conta ({nome})" if avisou
                               else f"pegando a conta ({nome})"))
            with self.trava(nome, esperar=PASSO_TRAVA_S) as minha:
                if minha:
                    atual = self._ainda_pendente(caixa, mensagem)
                    if atual is None:
                        return correio.uma(caixa, mid) or mensagem
                    if avisou:
                        self.log(f"[carteiro] a conta do {ia} soltou; entregando {mid}")
                    return self._entregar_com_a_conta(caixa, ia, atual, desde)
            largada = self._largou_na_espera(caixa, mensagem)
            if largada is not None:
                return largada
            if self.de_servico and avisou and caixa != correio.LIVRE:
                # chegou trabalho para uma conta LIVRE: larga esta espera (a
                # mensagem continua pendente) e vai entregar a outra. So no
                # servico: o worker leria o `pendente` como falha (IAS-2)
                outra = self._primeira_com_conta_livre(mensagem)
                if outra["id"] != mensagem["id"] and str(outra.get("para")) != ia:
                    return mensagem
            if not avisou:
                avisou = True
                self.log(f"[carteiro] a conta do {ia} ({nome}) esta com a pipeline; "
                         f"espero ela soltar (mensagem {mid})")
                correio.atualizar(caixa, mid, nota=f"esperando a pipeline soltar a conta "
                                                   f"(desde {desde[11:16]})")
                self._diario(ia, "log", f"carteiro: esperando a pipeline soltar {nome}", mid)
            if self.relogio() - inicio >= limite:
                motivo = (f"a conta do {correio.ROTULOS.get(ia, ia)} ficou com a pipeline por "
                          f"{_tempo_legivel(limite)}; não entreguei. Mande de novo mais tarde.")
                self.log(f"[carteiro] {mid}: {motivo}")
                return self._falhar(caixa, ia, mid, motivo, "conta_ocupada")

    def _entregar_livre(self, mensagem: dict) -> dict:
        """O RODIZIO ("qualquer um livre"): o primeiro gerador da lista
        `rodizio_imagem` do config que gera hoje (ficha), esta em cota (sem
        falha de limite/parede nas ultimas `cota_pausa_h`) e tem a conta
        LIVRE agora. Ninguem livre: espera, como a entrega comum; ninguem que
        possa gerar (todos fora da ficha ou da cota): falha com os motivos."""
        from . import imagem
        caixa, mid = correio.LIVRE, str(mensagem["id"])
        desde = correio.agora()
        inicio = self.relogio()
        limite = float(self.ajustes.get("espera_conta_max_s", 10800))
        ordem = self._ordem_do_rodizio()
        horas = float(self.ajustes.get("cota_pausa_h", 6))
        avisou = False
        while True:
            motivos, ocupados = [], []
            proporcao = str(mensagem.get("proporcao") or "")
            for g in ordem:
                info = imagem.gerador(g)
                if not info["disponivel"]:
                    motivos.append(f"{info['rotulo']}: {info['motivo'][:90]}")
                    continue
                if proporcao not in info["proporcoes"]:
                    motivos.append(f"{info['rotulo']}: não faz {proporcao}")
                    continue
                if mensagem.get("anexos") and g not in correio.CHATS:
                    # Pedido com referencia (a juncao dos builds) so vai a quem
                    # recebe anexo no chat: fora dele a imagem sairia sem as
                    # referencias, com outro rosto e outra arma (07/10/2026).
                    motivos.append(f"{info['rotulo']}: não recebe as imagens de referência")
                    continue
                fora = imagem.fora_de_cota(g, horas)
                if fora:
                    motivos.append(f"{info['rotulo']}: {fora}")
                    continue
                nome = self.nome_da_trava(g)
                with self.trava(nome, esperar=0.0) as minha:
                    if minha:
                        atual = self._ainda_pendente(caixa, mensagem)
                        if atual is None:
                            return correio.uma(caixa, mid) or mensagem
                        self.log(f"[carteiro] rodizio {mid}: {g} esta livre")
                        correio.atualizar(caixa, mid, gerador=g, nota=None,
                                          rodizio=f"{info['rotulo']} estava livre")
                        return self._entregar_com_a_conta(
                            caixa, g, dict(atual, gerador=g), desde)
                ocupados.append(info["rotulo"])
            largada = self._largou_na_espera(caixa, mensagem)
            if largada is not None:
                return largada
            if not ocupados:
                motivo = ("nenhum gerador do rodízio pode gerar agora — "
                          + "; ".join(motivos))[:600]
                return self._falhar(caixa, caixa, mid, motivo, "rodizio")
            if not avisou:
                avisou = True
                correio.atualizar(caixa, mid, nota="rodízio: todas as contas ocupadas "
                                  f"({', '.join(ocupados)}); esperando uma soltar")
            self._estado("esperando_trava", None, mid, desde,
                         nota=f"rodízio: esperando {', '.join(ocupados)}")
            if self.relogio() - inicio >= limite:
                motivo = (f"as contas do rodízio ({', '.join(ocupados)}) ficaram ocupadas "
                          f"por {_tempo_legivel(limite)}; não gerei. Peça de novo mais tarde.")
                return self._falhar(caixa, caixa, mid, motivo, "conta_ocupada")
            self.dormir(PASSO_TRAVA_S)

    def _ordem_do_rodizio(self) -> list:
        """A ordem em que o rodizio tenta os geradores.

        Do que gerou ha mais tempo ao mais recente (`imagem.rodizio_ordem`,
        que le o `rodizio_imagem` do config.json na hora): os geradores
        DIVIDEM o trabalho (03/10/2026). IAS-7: ate 14/10 o `rodizio_imagem`
        do config chegava em `self.ajustes` e vencia o `or rodizio_ordem()`,
        entao no servico o Gemini ia sempre primeiro. So uma lista que QUEM
        CHAMOU passou (o identity passa `[gerador]`) fixa a ordem."""
        from . import imagem
        fixada = self._ajustes_do_chamador.get("rodizio_imagem")
        if fixada:
            return [str(g).lower() for g in fixada if str(g).lower() in correio.GERADORES]
        return [g for g in imagem.rodizio_ordem() if g in correio.GERADORES]

    def _ainda_pendente(self, caixa: str, mensagem: dict) -> dict | None:
        """A mensagem RELIDA depois de pegar a trava, ou None se outra entrega
        ja a levou (respondida, falhou, entregue) ou se ela e reservada por
        outro processo vivo. Ate 05/10/2026 a copia antiga ia ao navegador: o
        worker das historias e o carteiro de servico entregavam o MESMO
        pedido, e a imagem era gerada duas vezes."""
        mid = str(mensagem["id"])
        atual = correio.uma(caixa, mid)
        if atual is None:
            return None
        reservada = correio.reservado_por_outro(atual)
        if atual.get("situacao") == "pendente" and not reservada:
            return atual
        self.log(f"[carteiro] {caixa} {mid}: ja esta {atual.get('situacao')}"
                 + (f" (reservada pelo processo {atual.get('dono')})" if reservada else "")
                 + "; nao entrego de novo")
        return None

    def _log_detalhe(self, ia: str, mid: str, exc: BaseException) -> None:
        """A excecao crua do navegador vai SO para o log (14/10/2026); o
        motivo que vai ao app e ao Telegram e a frase de `classificar_erro`."""
        detalhe = detalhe_tecnico(exc)
        if detalhe:
            self.log(f"[carteiro] {ia} {mid}: detalhe técnico: {detalhe}")

    def _falhar(self, caixa: str, ia: str, mid: str, motivo: str, categoria: str,
                **campos) -> dict:
        """Marca a falha (motivo legivel), vai ao DIARIO e avisa. Se outra
        entrega ja respondeu, nao desfaz: devolve a respondida (05/10: o
        607b37d6 e o debadd26 respondidos viraram "falhou" e um aviso falso)."""
        atual = correio.uma(caixa, mid)
        if atual is not None and atual.get("situacao") == "respondida":
            self.log(f"[carteiro] {ia} {mid}: falhou aqui, mas ja estava respondida; "
                     "fica a resposta")
            return atual
        atualizada = correio.atualizar(caixa, mid, situacao="falhou", erro=motivo,
                                       categoria=categoria, falhou_em=correio.agora(),
                                       nota=None, **campos)
        self._diario(ia, "erro", f"carteiro: {categoria}: {motivo}"[:400], mid)
        self._anunciar(caixa, atualizada)
        return atualizada

    def _entregar_com_a_conta(self, caixa: str, ia: str, mensagem: dict, desde: str) -> dict:
        mid = str(mensagem["id"])
        self._estado("entregando", ia, mid, desde)
        ultima = mensagem
        if ia not in correio.CHATS:
            return self._imagem_fora_do_chat(caixa, ia, mensagem, desde)
        na_mao = [(caixa, mensagem)]
        try:
            # a imagem de um carteiro que MORREU no meio, com a conversa dela
            # registrada (`_varrer_abandonadas`, IAS-4): volta nela e baixa o
            # que ja esta la, sem pedir outra
            recuperar_imagem = ((caixa, mensagem)
                                if (correio.tipo(mensagem) == "imagem"
                                    and mensagem.get("recuperar")
                                    and mensagem.get("chat_imagem_url")) else None)
            for volta in (1, 2):
                try:
                    with self.fabrica(ia) as sessao:
                        # A CASA SO ABRE NO PRIMEIRO TURNO DE TEXTO (`_casa_da_sessao`,
                        # 05/10/2026): pedido de imagem vai em conversa nova, e a
                        # recuperacao volta direto na conversa da imagem. Antes a
                        # casa abria a cada pedido de imagem, com o turno do resumo.
                        self._casa = None
                        self._fora_da_casa = False
                        if recuperar_imagem:
                            na_mao.append(recuperar_imagem)
                            ultima = self._recuperar(*recuperar_imagem, ia=ia, sessao=sessao)
                        else:
                            fila = [(caixa, mensagem)]
                            while fila:
                                onde, atual = fila.pop(0)
                                na_mao.append((onde, atual))
                                ultima = self._um_turno(ia, sessao, None, atual, caixa=onde)
                                if ultima["situacao"] != "respondida":
                                    break
                                proxima = self._esperar_proxima(ia)
                                if proxima is not None:
                                    fila.append((ia, proxima))
                    break
                except _ReabrirImagem as exc:
                    if volta == 2:
                        raise
                    recuperar_imagem = (exc.caixa, exc.mensagem)
                    recuperado = str(exc.mensagem["id"])
                    self.log(f"[carteiro] {ia} {recuperado}: Chrome fechou no download; "
                             "reabro a conversa da imagem uma vez sem pedir outra")
                    correio.atualizar(exc.caixa, recuperado, nota="Chrome fechou no download; "
                                                                 "reabrindo para recuperar a imagem")
        except Exception as exc:                               # noqa: BLE001
            # A sessao nem abriu (login caido, Chrome ocupado, site fora):
            # a mensagem que estava na mao falha com o motivo legivel.
            onde, atual = na_mao[-1]
            amid = str(atual["id"])
            pendente = correio.uma(onde, amid)
            if pendente is not None and self._rede_caiu(onde, pendente, exc):
                pendente = None
            if (pendente is not None and pendente["situacao"] in ("pendente", "entregue")
                    and not correio.reservado_por_outro(pendente)):
                categoria, motivo = classificar_erro(ia, exc)
                self.log(f"[carteiro] {ia} {amid}: {motivo}")
                self._log_detalhe(ia, amid, exc)
                # o site fora na abertura (pagina em branco, 30/09): o rodizio
                # tira o gerador por `cota_pausa_h`, como no "Alta procura"
                pausa = ({"pausa_rodizio": True} if getattr(exc, "pausa_rodizio", False)
                         else {})
                ultima = self._falhar(onde, ia, amid, motivo, categoria, **pausa)
                # ...e nao conta contra a casa: na 2a falha ela seria trocada
                # por uma nova sem ter culpa. Pedido de imagem nao usa a casa.
                if (type(exc).__name__ != "SiteIndisponivel"
                        and correio.tipo(atual) == "texto"):
                    casa = correio.casa(ia)
                    casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
                    self._gravar_casa(ia, casa)
        finally:
            self._casa = None
            self._estado("ocioso")
        return ultima

    def _recuperar(self, caixa: str, mensagem: dict, *, ia: str, sessao) -> dict:
        """Depois de o Chrome cair no download: volta na conversa PROPRIA da
        imagem e baixa o que ja esta la, sem pedir outra. Se a conversa nao
        reabre, falha dizendo isso (antes o retorno de `abrir_casa` era
        ignorado e a leitura caia na pagina errada)."""
        mid = str(mensagem["id"])
        url_img = str((correio.uma(caixa, mid) or {}).get("chat_imagem_url") or "")
        if url_img:
            if _reabrir_conversa_de_imagem(sessao, url_img):
                return self._turno_imagem(caixa, ia, sessao, mensagem, None, recuperar=True)
            motivo = (f"o Chrome caiu baixando a imagem e a conversa dela não reabriu "
                      f"({url_img[:90]}); não pedi outra")
        elif not callable(getattr(sessao, "novo_chat", None)):
            # sessao sem conversa avulsa: a imagem nasceu na propria casa
            return self._turno_imagem(caixa, ia, sessao, mensagem,
                                      self._casa_da_sessao(ia, sessao), recuperar=True)
        else:
            motivo = ("o Chrome caiu baixando a imagem e o endereço da conversa dela não "
                      "ficou registrado; não pedi outra")
        self.log(f"[carteiro] {ia} {mid}: {motivo}")
        return self._falhar(caixa, ia, mid, motivo, "recuperacao", gerador=ia)

    def _ja_guardada(self, caixa: str, ia: str, mid: str, exc) -> dict:
        """A imagem provada deste pedido ja esta no disco: nao sobrescreve e
        nao marca falha. Se o correio ainda nao diz respondida (o processo
        caiu entre gravar e responder), responde com a que ja estava."""
        atual = correio.uma(caixa, mid)
        self.log(f"[carteiro] {ia} {mid}: a imagem provada ja estava no disco; "
                 "fica a primeira (nada sobrescrito)")
        if atual is not None and atual.get("situacao") == "respondida":
            return atual
        resumo = dict(getattr(exc, "resumo", None) or {})
        return correio.atualizar(caixa, mid, situacao="respondida", gerador=ia,
                                 imagem=resumo, nota=None,
                                 resposta="imagem pronta (já estava no disco)",
                                 respondida_em=correio.agora())

    def _casa_da_sessao(self, ia: str, sessao) -> dict:
        """A casa desta sessao, aberta na primeira vez que um turno de texto
        precisa dela."""
        if self._casa is None:
            self._casa = self._abrir_casa(ia, sessao)
        return self._casa

    def _imagem_fora_do_chat(self, caixa: str, ia: str, mensagem: dict, desde: str) -> dict:
        """O PicassoIA: sessao propria (nao e chat). A PAREDE DE PLANOS reabre o
        perfil UMA vez, como no worker das historias (17/09/2026)."""
        from . import imagem
        mid = str(mensagem["id"])
        ultima = mensagem
        try:
            for volta in (1, 2):
                try:
                    with self.fabrica_imagem(ia) as sessao:
                        ultima = self._turno_imagem(caixa, ia, sessao, mensagem, None,
                                                    relancar_parede=volta == 1)
                    break
                except _Reabrir:
                    self.log(f"[carteiro] {ia}: parede de planos; fecho o navegador e "
                             "reabro o perfil uma vez")
                    correio.atualizar(caixa, mid, nota="o site pediu assinatura; "
                                                       "reabrindo o perfil uma vez")
        except Exception as exc:                               # noqa: BLE001
            pendente = correio.uma(caixa, mid)
            if (pendente is not None and pendente["situacao"] in ("pendente", "entregue")
                    and not correio.reservado_por_outro(pendente)):
                categoria, motivo = imagem.classificar(ia, exc)
                self.log(f"[carteiro] {ia} {mid}: {motivo}")
                self._log_detalhe(ia, mid, exc)
                ultima = self._falhar(caixa, ia, mid, motivo, categoria, gerador=ia)
        finally:
            self._estado("ocioso")
        return ultima

    def _rede_caiu(self, caixa: str, mensagem: dict, exc: BaseException) -> bool:
        """A internet/DNS caiu (net::ERR_NAME_NOT_RESOLVED...): nao e culpa do
        pedido nem da IA. O pedido volta para a fila e o carteiro espera, ate
        REDE_TENTATIVAS vezes; so entao falha (02/10/2026: 7 falhas assim)."""
        if not self.de_servico:
            # IAS-2: so o laco do servico volta a pegar a fila; no Carteiro
            # sincrono a falha segue, com a categoria `rede` (`classificar_erro`)
            return False
        if not REDE_CAIU.search(type(exc).__name__ + " " + str(exc)):
            return False
        mid = str(mensagem["id"])
        n = int(mensagem.get("rede_tentativas") or 0) + 1
        if n > REDE_TENTATIVAS:
            return False
        espera = min(60 * n, 300)
        self.log(f"[carteiro] {caixa} {mid}: a rede caiu; volta para a fila e espero {espera}s "
                 f"({n}/{REDE_TENTATIVAS})")
        correio.atualizar(caixa, mid, situacao="pendente", rede_tentativas=n,
                          nota=f"a rede caiu; tento de novo em {espera // 60} min ({n}/{REDE_TENTATIVAS})")
        self.dormir(espera)
        return True

    def _resumo_para_a_casa_nova(self, ia: str) -> str:
        """O resumo da casa anterior, se ele ainda serve: recente (ate
        `RESUMO_VALIDADE_S`), nao curto e nao recusa. Senao, ""."""
        texto = correio.resumo_da_casa(ia).strip()
        if not texto:
            return ""
        idade = correio.idade_do_resumo_da_casa(ia)
        if idade is not None and idade > RESUMO_VALIDADE_S:
            self.log(f"[carteiro] {ia}: o resumo da casa tem {idade / 3600:.0f} h "
                     f"(mais de {RESUMO_VALIDADE_S / 3600:.0f} h); a casa nova abre sem ele")
            return ""
        if not resumo_aceitavel(texto):
            self.log(f"[carteiro] {ia}: o resumo guardado é curto ou recusa "
                     f"(«{' '.join(texto.split())[-80:]}»); a casa nova abre sem ele")
            return ""
        return texto

    def _abrir_casa(self, ia: str, sessao) -> dict:
        casa = correio.casa(ia)
        aberta = False
        if casa.get("url") and e_raiz(casa["url"]):
            # a raiz do site nunca foi uma conversa (o defeito de ate 05/10)
            self.log(f"[carteiro] {ia}: a casa guardada era a raiz do site "
                     f"({casa['url']}); comeco uma nova")
        elif casa.get("url") and int(casa.get("falhas_seguidas") or 0) < 2:
            try:
                aberta = bool(sessao.abrir_casa(casa["url"]))
            except Exception as exc:                           # noqa: BLE001
                # login caido ou site fora (pagina em branco): um chat novo
                # daria no mesmo, e a casa seria abandonada sem culpa
                if type(exc).__name__ in ("NaoLogado", "SiteIndisponivel"):
                    raise
                self.log(f"[carteiro] {ia}: a casa nao abriu ({type(exc).__name__}); "
                         "comeco uma nova")
                aberta = False
        if aberta:
            self.log(f"[carteiro] {ia}: casa reaberta (geracao {casa.get('geracao')}, "
                     f"{casa.get('mensagens')} mensagens)")
            return casa
        sessao.novo_chat()
        resumo = self._resumo_para_a_casa_nova(ia)
        nova = correio.casa_vazia(ia)
        nova["geracao"] = int(casa.get("geracao") or 0) + 1
        nova["aberta_em"] = correio.agora()
        if resumo:
            try:
                _perguntar_com_prazo(sessao, PROLOGO_CASA_NOVA + resumo, PRAZO_PROLOGO_S)
                nova["comecou_com_resumo"] = True
                self.log(f"[carteiro] {ia}: casa nova (geracao {nova['geracao']}) "
                         "aberta com o resumo da anterior")
            except Exception as exc:                           # noqa: BLE001
                self.log(f"[carteiro] {ia}: o resumo nao entrou na casa nova "
                         f"({type(exc).__name__}); sigo sem ele")
        else:
            self.log(f"[carteiro] {ia}: casa nova (geracao {nova['geracao']})")
        # A URL SO DEPOIS DO PRIMEIRO TURNO (05/10/2026): antes dele a conversa
        # nao existe e o site mostra a raiz. Ainda a raiz = None; o primeiro
        # turno de texto respondido grava o endereco de verdade.
        endereco = sessao.url()
        nova["url"] = None if e_raiz(endereco) else endereco
        self._gravar_casa(ia, nova)
        return nova

    def _turno_imagem(self, caixa: str, ia: str, sessao, mensagem: dict,
                      casa: dict | None, relancar_parede: bool = False,
                      recuperar: bool = False) -> dict:
        """UM pedido de imagem: gera, exige prova, grava os bytes originais com
        a prova ao lado, e so entao marca respondida. Sem prova, nada vai ao
        disco e o pedido falha com o motivo."""
        from . import imagem
        mid = str(mensagem["id"])
        desde = correio.agora()
        info = imagem.gerador(ia)
        if not info["disponivel"]:
            return self._falhar(caixa, ia, mid,
                                f"{info['rotulo']} não gera imagem hoje: {info['motivo']}",
                                "indisponivel", gerador=ia)
        # pendente -> entregue sob a trava do arquivo: se outro carteiro ja a
        # levou (ou respondeu), nao se gera de novo
        if correio.reivindicar(caixa, mid, gerador=ia) is None:
            atual = correio.uma(caixa, mid) or mensagem
            self.log(f"[carteiro] {ia} {mid}: ja {atual.get('situacao')} em outra entrega; "
                     "nao gero de novo")
            return atual
        self._estado("entregando", ia, mid, desde, nota="gerando imagem")
        if hasattr(sessao, "cliente"):
            sessao.cliente.log = self._log_com_pulso(ia, mid, desde)
        t0 = self.relogio()
        prompt = str(mensagem.get("texto") or "")
        proporcao = str(mensagem.get("proporcao") or info["proporcao_padrao"])
        try:
            if recuperar:
                resultado = sessao.recuperar_imagem(prompt, proporcao)
            else:
                try:
                    anexos = mensagem.get("anexos") or None
                    resultado = (sessao.gerar_imagem(prompt, proporcao, mid, anexos=anexos)
                                 if anexos else sessao.gerar_imagem(prompt, proporcao, mid))
                except Exception as recusa:                    # noqa: BLE001
                    novo = getattr(sessao, "novo_chat", None)
                    if not (type(recusa).__name__ == "SemImagem" and callable(novo)):
                        raise
                    if self._recusa_e_cota(ia, recusa, sessao):
                        # IAS-1: «Poderei criar mais imagens assim que seu limite
                        # for redefinido» nao e recusa de modelo de linguagem: o
                        # reforco em conversa nova so gastava o 2o turno
                        raise
                    # "sou um modelo de linguagem, nao gero imagens" (6 vezes em
                    # 02/10): mais UMA vez, em conversa nova e dizendo que e imagem
                    self.log(f"[carteiro] {ia} {mid}: recusou a imagem; tento uma vez "
                             "em conversa nova")
                    correio.atualizar(caixa, mid, nota="recusou a imagem; tentando de novo "
                                                       "em conversa nova")
                    _chat_de_imagem(novo)
                    resultado = (sessao.gerar_imagem(
                        REFORCO_IMAGEM + prompt, proporcao, mid, anexos=anexos)
                        if anexos else sessao.gerar_imagem(REFORCO_IMAGEM + prompt,
                                                           proporcao, mid))
            salvo = imagem.guardar(ia, mid, resultado.get("bytes") or b"",
                                   resultado.get("prova") or {})
        except Exception as exc:                               # noqa: BLE001
            if isinstance(exc, imagem.JaGuardada):
                return self._ja_guardada(caixa, ia, mid, exc)
            if self._rede_caiu(caixa, mensagem, exc):
                return correio.uma(caixa, mid)
            if relancar_parede and type(exc).__name__ == "ParedeDePlanos":
                raise _Reabrir() from exc
            if chrome_caiu(exc) and not recuperar and (
                    casa is not None or getattr(self, "_fora_da_casa", False)):
                if casa is None:
                    try:
                        url_img = sessao.url()
                    except Exception:                          # noqa: BLE001
                        url_img = ""
                    if url_img and not e_raiz(url_img):
                        correio.atualizar(caixa, mid, chat_imagem_url=url_img)
                if (callable(getattr(sessao, "recuperar_imagem", None))
                        and imagem.pagina_viva(getattr(getattr(sessao, "cliente", None),
                                                       "page", None))):
                    # IAS-3: o TargetClosed foi do `Download`, nao do Chrome - a
                    # pagina esta viva. Recupera AQUI, sem fechar e reabrir o
                    # navegador (~1 min por queda em 12/10)
                    self.log(f"[carteiro] {ia} {mid}: o download caiu (TargetClosed) com a "
                             "página viva; recupero a imagem aqui, sem fechar o navegador")
                    correio.atualizar(caixa, mid, nota="o download caiu; recuperando a "
                                                       "imagem na mesma página")
                    return self._turno_imagem(caixa, ia, sessao, mensagem, casa,
                                              recuperar=True)
                raise _ReabrirImagem(caixa, mensagem) from exc
            # so o que surgiu depois do envio: o botao fixo "Fazer upgrade"
            # do rodape do ChatGPT Free nao e motivo (30/09)
            tela = tela_do_turno(sessao)
            categoria, motivo = imagem.classificar(ia, exc, tela)
            if recuperar:
                # quem pediu (o worker) nao culpa o gerador por isto
                categoria = "recuperacao"
                motivo = f"o Chrome caiu no download e a recuperação falhou: {motivo}"
            self.log(f"[carteiro] {ia} {mid} (imagem) falhou: {motivo}")
            self._log_detalhe(ia, mid, exc)
            if casa is not None:
                casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
                self._gravar_casa(ia, casa)
            # o aviso do site ("Alta procura"): o rodizio tira o gerador por
            # `cota_pausa_h`, como numa falha de cota (`imagem.fora_de_cota`)
            pausa = {"pausa_rodizio": True} if getattr(exc, "pausa_rodizio", False) else {}
            return self._falhar(caixa, ia, mid, motivo, categoria, gerador=ia, **pausa)
        reivindicar = getattr(sessao, "reivindicar", None)
        if callable(reivindicar):
            reivindicar(resultado, mid)
        dur = self.relogio() - t0
        kb = max(1, round(int(salvo["bytes"]) / 1024))
        medida = (f"{salvo['largura']}x{salvo['altura']}"
                  if salvo.get("largura") else salvo["formato"].upper())
        # A PREVIA FICA, MARCADA (decisao do Adrian, Grimorio
        # historias/previa-do-gemini, 14/10/2026): o original do Gemini nao
        # baixou e a imagem e a da tela, de meia resolucao. Nao gera de novo.
        previa = bool(salvo.get("previa"))
        resposta = f"imagem pronta · {medida} · {kb} KB"
        if previa:
            resposta += f" · {AVISO_PREVIA}"
        # respondida ANTES de gravar a casa: a casa trancada nao desfaz a
        # imagem ja gravada (IAS-5)
        atualizada = correio.atualizar(
            caixa, mid, situacao="respondida", gerador=ia,
            resposta=resposta, imagem=salvo,
            respondida_em=correio.agora(), dur_s=round(dur, 1),
            modelo=str(resultado.get("modelo") or getattr(sessao, "modelo", "") or ""),
            **({"previa": True} if previa else {}))
        if casa is not None:
            endereco = sessao.url()
            casa["url"] = endereco if endereco and not e_raiz(endereco) else casa.get("url")
            casa["mensagens"] = int(casa.get("mensagens") or 0) + 1
            casa["falhas_seguidas"] = 0
            self._gravar_casa(ia, casa)
        self.entregues += 1
        self.log(f"[carteiro] {ia} {mid}: imagem gravada ({salvo['arquivo']}, {kb} KB, "
                 f"prova {salvo['prova']}{', PRÉVIA' if previa else ''}) em {dur:.0f}s")
        self._diario(ia, "ok", f"carteiro: imagem {medida} ({salvo['prova']}"
                     f"{', prévia' if previa else ''})", mid)
        self._anunciar(caixa, atualizada)
        return atualizada

    def _recusa_e_cota(self, ia: str, recusa: BaseException, sessao) -> bool:
        """A "recusa" da imagem e, na verdade, o aviso de COTA? (IAS-1)"""
        from . import imagem
        texto = " ".join(str(recusa).split())
        if catalogo.classificar(texto) in ("limite", "upgrade"):
            return True
        return imagem.cota_no_texto(ia, tela_do_turno(sessao), texto) is not None

    def _um_turno(self, ia: str, sessao, casa: dict | None, mensagem: dict,
                  caixa: str | None = None) -> dict:
        """Um turno. `casa` None = a da sessao, aberta so se este turno for de
        TEXTO na casa (`_casa_da_sessao`)."""
        if correio.tipo(mensagem) == "imagem":
            # Imagem SEMPRE em conversa nova (02/10/2026): na casa, o Gemini lembrava
            # dos turnos de texto e do juiz e recusava ("como conversamos, nao
            # consigo gerar imagens"). A casa fica so para texto.
            novo = getattr(sessao, "novo_chat", None)
            if callable(novo):
                _chat_de_imagem(novo)
                self._fora_da_casa = True
                return self._turno_imagem(caixa or ia, ia, sessao, mensagem, None)
            if casa is None:
                casa = self._casa_da_sessao(ia, sessao)
            return self._turno_imagem(caixa or ia, ia, sessao, mensagem, casa)
        mid = str(mensagem["id"])
        # pendente -> entregue sob a trava do arquivo, ANTES de abrir a casa
        if correio.reivindicar(ia, mid) is None:
            atual = correio.uma(ia, mid) or mensagem
            self.log(f"[carteiro] {ia} {mid}: ja {atual.get('situacao')} em outra entrega; "
                     "nao entrego de novo")
            return atual
        # Pedido COM ANEXO (o juiz dos sprites) tambem vai em conversa nova
        # (02/10/2026, 14h): na casa, cheia de imagens, o Gemini recusou 17 de 31
        # julgamentos ("sou uma IA com base em texto") e travou 12 por 420 s.
        avulsa = bool(mensagem.get("anexos")) and callable(getattr(sessao, "novo_chat", None))
        if avulsa:
            sessao.novo_chat()
            self._fora_da_casa = True
        else:
            if casa is None:
                if self._fora_da_casa:
                    self._casa = None        # a sessao saiu da casa: volta nela
                casa = self._casa_da_sessao(ia, sessao)
            elif self._fora_da_casa:
                # depois de uma conversa avulsa, o texto volta para a casa
                casa.update(self._abrir_casa(ia, sessao))
            self._fora_da_casa = False
        desde = correio.agora()
        self._estado("entregando", ia, mid, desde)
        if hasattr(sessao, "cliente"):
            sessao.cliente.log = self._log_com_pulso(ia, mid, desde)
        t0 = self.relogio()
        try:
            resposta = sessao.perguntar(mensagem.get("texto") or "",
                                        anexos=mensagem.get("anexos") or None)
        except Exception as exc:                               # noqa: BLE001
            if self._rede_caiu(ia, mensagem, exc):
                return correio.uma(ia, mid)
            categoria, motivo = classificar_erro(ia, exc, tela_do_turno(sessao))
            self.log(f"[carteiro] {ia} {mid} falhou: {motivo}")
            self._log_detalhe(ia, mid, exc)
            if not avulsa:
                casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
                self._gravar_casa(ia, casa)
            return self._falhar(ia, ia, mid, motivo, categoria)
        dur = self.relogio() - t0
        resposta = str(resposta or "").strip()
        # A RESPOSTA PODE SER UMA IMAGEM (29/09, 14:24: "gere uma imagem de um
        # gato" ao Gemini ficou 420 s esperando texto e falhou). O cliente ja
        # reconhece a imagem; aqui ela e baixada com a prova do turno e
        # guardada como a de um pedido pelo Criar.
        extra = {}
        pegar = getattr(sessao, "imagem_da_resposta", None)
        if callable(pegar):
            from . import imagem
            try:
                achada = pegar(mensagem.get("texto") or "")
                if achada:
                    try:
                        salvo = imagem.guardar(ia, mid, achada.get("bytes") or b"",
                                               achada.get("prova") or {})
                    except imagem.JaGuardada as ja:
                        salvo = ja.resumo           # a primeira fica (nada sobrescrito)
                    extra = {"imagem": salvo, "gerador": ia}
                    kb = max(1, round(int(salvo["bytes"]) / 1024))
                    medida = (f"{salvo['largura']}x{salvo['altura']}"
                              if salvo.get("largura") else salvo["formato"].upper())
                    if salvo.get("previa"):
                        extra.update(previa=True, nota=f"a imagem é {AVISO_PREVIA}")
                    self.log(f"[carteiro] {ia} {mid}: a resposta trouxe uma imagem "
                             f"({salvo['arquivo']}, {medida}, {kb} KB"
                             f"{', PRÉVIA' if salvo.get('previa') else ''})")
                    if not resposta:
                        resposta = (f"(imagem · {medida} · {kb} KB"
                                    f"{' · ' + AVISO_PREVIA if salvo.get('previa') else ''})")
            except Exception as exc:                           # noqa: BLE001
                categoria, motivo = imagem.classificar(ia, exc)
                self.log(f"[carteiro] {ia} {mid}: a imagem da resposta nao foi guardada: "
                         f"{motivo}")
                self._log_detalhe(ia, mid, exc)
                if not resposta:
                    return self._falhar(ia, ia, mid, f"a resposta foi uma imagem, mas "
                                        f"ela não foi guardada: {motivo}", categoria)
                extra = {"nota": f"a resposta trouxe uma imagem que não foi guardada: "
                                 f"{motivo}"[:300]}
        # O MODELO QUE RESPONDEU FICA COM NOTA quando nao e o forte (IAS-9,
        # 11/10/2026): antes a resposta era gravada com o modelo fraco ou
        # vazio, e nada dizia que a troca de modelo nao tinha pegado.
        if getattr(sessao, "modelo_confirmado", True) is False:
            fraco = (f"modelo não confirmado (saiu em "
                     f"{getattr(sessao, 'modelo', '') or 'desconhecido'})")
            extra["nota"] = (f"{extra['nota']}; {fraco}" if extra.get("nota")
                             else fraco)[:300]
        atualizada = correio.atualizar(
            ia, mid, situacao="respondida", resposta=resposta,
            respondida_em=correio.agora(), dur_s=round(dur, 1),
            modelo=getattr(sessao, "modelo", "") or "", **extra)
        # a casa DEPOIS da resposta gravada: `casa.json` trancado por outro
        # processo (PermissionError no Windows) fazia a resposta obtida virar
        # "falhou" e, na 2a vez, derrubava o `rodar()` (IAS-5)
        if not avulsa:
            endereco = sessao.url()
            casa["url"] = endereco if endereco and not e_raiz(endereco) else casa.get("url")
            casa["mensagens"] = int(casa.get("mensagens") or 0) + 1
            casa["falhas_seguidas"] = 0
            self._gravar_casa(ia, casa)
        self.entregues += 1
        self.log(f"[carteiro] {ia} {mid}: respondida ({len(resposta)} chars em {dur:.0f}s)")
        self._anunciar(ia, atualizada)
        if not avulsa and (int(casa.get("mensagens") or 0) - int(casa.get("resumo_mensagens") or 0)
                           >= int(self.ajustes.get("resumo_a_cada", 12))):
            self._resumir(ia, sessao, casa)
        return atualizada

    def _resumir(self, ia: str, sessao, casa: dict) -> bool:
        self._estado("resumindo", ia, None, correio.agora())
        try:
            texto = str(sessao.perguntar(PEDIDO_RESUMO) or "").strip()
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[carteiro] {ia}: o resumo da casa falhou ({type(exc).__name__})")
            return False
        if not texto:
            return False
        if not resumo_aceitavel(texto):
            # 02/10: o "resumo" do Gemini foi "Não fui programado para fazer
            # essas coisas." e abriu toda casa nova dali em diante. Fica o
            # anterior; a proxima tentativa vem depois de mais `resumo_a_cada`.
            self.log(f"[carteiro] {ia}: o resumo veio curto ou de recusa "
                     f"(«{' '.join(texto.split())[:80]}»); fica o anterior")
            casa["resumo_mensagens"] = int(casa.get("mensagens") or 0)
            self._gravar_casa(ia, casa)
            return False
        correio.gravar_resumo_da_casa(ia, texto)
        casa["resumo_mensagens"] = int(casa.get("mensagens") or 0)
        casa["ultimo_resumo_em"] = correio.agora()
        self._gravar_casa(ia, casa)
        self.log(f"[carteiro] {ia}: resumo da casa guardado ({len(texto)} chars)")
        self._diario(ia, "log", f"carteiro: resumo da casa ({len(texto)} chars)", "")
        return True

    def _esperar_proxima(self, ia: str) -> dict | None:
        """Segura a conta por `janela_conversa_s` esperando a proxima dele.
        Janela 0 = nenhuma: o Carteiro sincrono do worker das historias so
        entrega o pedido dele (nao leva a fila do Adrian junto)."""
        janela = float(self.ajustes.get("janela_conversa_s", 90))
        if janela <= 0:
            return None
        fim = self.relogio() + janela
        while True:
            fila = correio.pendentes(ia, so_livres=True)
            if fila:
                return fila[0]
            if self.relogio() >= fim:
                return None
            self._estado("entregando", ia, None, correio.agora(),
                         nota="conversa aberta: esperando a próxima mensagem")
            self.dormir(min(3.0, max(0.1, fim - self.relogio())))

    # ---------------------------------------------------------- anuncio
    def _situacao_do_aviso(self, entregue) -> str:
        """O que o log diz do aviso (IAS-8): a situacao em texto quando o
        `avisar` a devolve; senao o bool de sempre."""
        if isinstance(entregue, str) and entregue:
            return {"entregue": "entregue",
                    "calado": "calado pelo porteiro (o mesmo aviso já saiu hoje)",
                    "enfileirado": "NAO entregue agora (ficou na fila; o bot manda "
                                   "quando a rede voltar)",
                    "sem_destino": "sem destino (ninguém autorizado no remoto)",
                    }.get(entregue, entregue)
        return "entregue" if entregue is not False else "NAO entregue"

    def _anunciar(self, ia: str, mensagem: dict) -> None:
        if not self.de_servico:
            # o worker le a resposta na hora; o Telegram e do servico. Ate
            # 14/10 o log dos workers tinha 276 "NAO entregue"/dia sem ninguem
            # ter tentado mandar nada (IAS-8)
            return
        if correio.tipo(mensagem) == "imagem" or (
                mensagem.get("situacao") == "respondida"
                and isinstance(mensagem.get("imagem"), dict)):
            return self._anunciar_imagem(ia, mensagem)
        rotulo = correio.ROTULOS.get(ia, ia)
        if mensagem["situacao"] == "respondida":
            texto = f"💬 {rotulo} respondeu:\n{str(mensagem.get('resposta') or '')[:1500]}"
            nota = str(mensagem.get("nota") or "")
            if mensagem.get("de") == "adrian" and "modelo não confirmado" in nota:
                # a pergunta foi DELE: ele precisa saber em que modelo saiu (IAS-9)
                texto += f"\n({nota[nota.index('modelo não confirmado'):][:120]})"
        else:
            texto = (f"⚠ {rotulo}: não consegui entregar sua mensagem — "
                     f"{mensagem.get('erro') or 'sem motivo'}")
        if correio.app_esta_olhando(ia):
            self.log(f"[carteiro] {ia}: o app esta olhando a caixa; sem Telegram")
            return
        try:
            entregue = self.avisar(texto)
            self.log(f"[carteiro] {ia}: aviso no Telegram "
                     f"{self._situacao_do_aviso(entregue)}")
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[carteiro] o aviso no Telegram falhou ({type(exc).__name__})")

    def _anunciar_imagem(self, caixa: str, mensagem: dict) -> None:
        """A imagem vai ao Telegram como DOCUMENTO (a qualidade original, sem
        a recompressao de foto do Telegram) quando o app nao esta olhando nem
        a caixa do pedido nem a do gerador. A falha vai em texto."""
        gerador = str(mensagem.get("gerador") or caixa)
        olhando = correio.app_esta_olhando(caixa) or (
            gerador in correio.CAIXAS and gerador != caixa
            and correio.app_esta_olhando(gerador))
        if olhando:
            self.log(f"[carteiro] {caixa}: o app esta olhando a caixa; sem Telegram")
            return
        rotulo = correio.ROTULOS.get(gerador, gerador)
        prompt = " ".join(str(mensagem.get("texto") or "").split())
        try:
            if mensagem.get("situacao") == "respondida":
                caminho = correio.arquivo_da_imagem(caixa, mensagem["id"])
                legenda = (f"🎨 {rotulo} · {mensagem.get('proporcao') or ''}: {prompt[:300]}"
                           + (" (rodízio)" if caixa == correio.LIVRE else "")
                           + (f"\n({AVISO_PREVIA})" if mensagem.get("previa") else ""))
                if caminho is None:
                    entregue = self.avisar(legenda + "\n(a imagem não está no disco)")
                else:
                    entregue = self.avisar_arquivo(caminho, legenda)
            else:
                entregue = self.avisar(f"⚠ {rotulo}: a imagem não saiu — "
                                       f"{mensagem.get('erro') or 'sem motivo'}\n"
                                       f"pedido: {prompt[:200]}")
            self.log(f"[carteiro] {caixa}: aviso no Telegram "
                     f"{self._situacao_do_aviso(entregue)}")
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[carteiro] o aviso no Telegram falhou ({type(exc).__name__})")

    def _diario(self, ia: str, status: str, detalhe: str, ref: str) -> None:
        try:
            import builds.atividade as atividade
            # canal `adrian` so no servico (as conversas dele); o Carteiro de
            # um worker e trabalho da pipeline (IAS-6)
            atividade.registrar(ia, status, detalhe,
                                "adrian" if self.de_servico else "pipeline",
                                etapa="correio", ref=ref)
        except Exception:                                      # noqa: BLE001
            pass

    # -------------------------------------------------------------- laco
    def _varrer_abandonadas(self) -> int:
        """Pedido reservado (`dono`) por um processo que morreu: quem pediu nao
        vai ler a resposta, entao nao se gasta a conta com ele (falha, sem
        Telegram). No maximo uma varredura por `VARRER_ABANDONADAS_S`."""
        agora = self.relogio()
        if (self._ultima_varredura is not None
                and agora - self._ultima_varredura < VARRER_ABANDONADAS_S):
            return 0
        self._ultima_varredura = agora
        quantas = 0
        meu = os.getpid()
        for caixa in correio.CAIXAS:
            for m in correio.ler(caixa):
                situacao = m.get("situacao")
                if situacao == "pendente":
                    erro = self._motivo_do_abandono(m, meu)
                    if not erro:
                        continue
                    correio.atualizar(caixa, m["id"], situacao="falhou",
                                      categoria="abandonado", erro=erro,
                                      falhou_em=correio.agora(), nota=None)
                    self.log(f"[carteiro] {caixa} {m['id']}: {erro}")
                    quantas += 1
                elif situacao == "entregue" and self._entrega_orfa(m, meu):
                    self._retomar_orfa(caixa, m)
                    quantas += 1
        return quantas

    @staticmethod
    def _motivo_do_abandono(m: dict, meu: int) -> str:
        """Por que este pendente reservado nao deve ser entregue ("" = deve)."""
        if correio.abandonada(m):
            return (f"quem pediu (processo {m.get('dono')}) terminou antes da entrega; "
                    "não gerei")
        dono = correio._dono(m)
        idade = correio._idade_da_reserva(m)
        if (dono is not None and dono != meu and idade is not None
                and idade > correio.RESERVA_MAX_S):
            # IAS-2: a reserva vencida virava LIVRE e o servico a entregava
            # 4 h depois, para ninguem (quem pediu ja tinha desistido)
            return (f"a reserva do processo {dono} passou de "
                    f"{correio.RESERVA_MAX_S / 3600:.0f} h sem entrega: quem pediu "
                    "já desistiu; não gerei")
        return ""

    @staticmethod
    def _entrega_orfa(m: dict, meu: int) -> bool:
        """`entregue` por um carteiro que MORREU no meio (IAS-4), ou ha mais
        de `RESERVA_MAX_S` (o Windows reusa PID: o morto pode parecer vivo)."""
        entregador = correio._entregador(m)
        if entregador is None or entregador == meu:
            return False
        if correio._pid_vivo(entregador) is False:
            return True
        try:
            desde = datetime.fromisoformat(str(m.get("entregue_em"))).timestamp()
        except (TypeError, ValueError):
            return False
        return time.time() - desde > correio.RESERVA_MAX_S

    def _retomar_orfa(self, caixa: str, m: dict) -> None:
        """A orfa volta para a fila (texto, ou imagem com a conversa dela
        registrada, que sera RECUPERADA sem novo pedido) ou falha (imagem sem
        o endereco: pedir de novo geraria outra, e quem pediu decide)."""
        entregador = correio._entregador(m)
        nota = "o carteiro anterior caiu no meio; volta para a fila"
        try:
            idade = time.time() - datetime.fromisoformat(str(m.get("entregue_em"))).timestamp()
        except (TypeError, ValueError):
            idade = None
        if idade is None or idade > RETOMAR_ORFA_MAX_S:
            # orfa VELHA (de dias atras): reenviar agora mandaria a IA um
            # pedido que ninguem espera mais; so sai do "em andamento"
            correio.atualizar(caixa, m["id"], situacao="falhou", categoria="interrompida",
                              erro=f"o carteiro que entregava (processo {entregador}) "
                                   "morreu no meio; o pedido ficou velho e não volta "
                                   "para a fila", falhou_em=correio.agora(), nota=None)
            self.log(f"[carteiro] {caixa} {m['id']}: órfã velha do carteiro {entregador}; "
                     "falhou (não reenvio)")
            return
        if correio.tipo(m) == "texto":
            correio.atualizar(caixa, m["id"], situacao="pendente", entregador=None, nota=nota)
        elif m.get("chat_imagem_url"):
            correio.atualizar(caixa, m["id"], situacao="pendente", entregador=None,
                              nota=nota, recuperar=True)
        else:
            correio.atualizar(caixa, m["id"], situacao="falhou", categoria="interrompida",
                              erro=f"o carteiro que entregava (processo {entregador}) "
                                   "morreu no meio", falhou_em=correio.agora(), nota=None)
            self.log(f"[carteiro] {caixa} {m['id']}: o carteiro {entregador} morreu "
                     "entregando a imagem; falhou")
            return
        self.log(f"[carteiro] {caixa} {m['id']}: o carteiro {entregador} morreu no meio; "
                 "volta para a fila")

    def uma_volta(self) -> dict | None:
        # o config.json vale na volta seguinte, sem reiniciar (IAS-7)
        self.ajustes = {**config(), **self._ajustes_do_chamador}
        self._varrer_abandonadas()
        mensagem = correio.proxima_pendente(correio.CAIXAS, so_livres=True)
        if mensagem is None:
            self._estado("ocioso")
            return None
        return self.entregar(self._primeira_com_conta_livre(mensagem))

    def _primeira_com_conta_livre(self, mais_velha: dict) -> dict:
        """A mais velha cuja conta esta LIVRE agora; se nenhuma, a mais velha.

        02/10/2026: a criacao de historias segurou a conta do ChatGPT por horas
        e o carteiro ficou parado esperando por ela, com 16 pedidos do Gemini
        (conta livre) na fila atras. Uma conta ocupada nao trava as outras."""
        candidatas = []
        for caixa in correio.CAIXAS:
            candidatas.extend(correio.pendentes(caixa, so_livres=True))
        candidatas.sort(key=lambda m: (str(m.get("em") or ""), m["id"]))
        vistas = set()
        for m in candidatas:
            ia = str(m.get("para") or "")
            if ia == correio.LIVRE:
                return m                     # o rodizio ja procura quem esta livre
            if ia in vistas:
                continue
            vistas.add(ia)
            try:
                with self.trava(self.nome_da_trava(ia), esperar=0.0) as minha:
                    livre = bool(minha)
            except Exception:                                  # noqa: BLE001
                livre = False
            if livre:
                if m["id"] != mais_velha["id"]:
                    self.log(f"[carteiro] a conta do {mais_velha.get('para')} esta ocupada; "
                             f"adianto {m['id']} do {ia}, que esta livre")
                return m
        return mais_velha

    def rodar(self, *, uma_vez: bool = False, intervalo: float | None = None,
              parar=None) -> int:
        intervalo = float(self.ajustes.get("intervalo_s", 5) if intervalo is None else intervalo)
        self._estado("ocioso")
        self.log("[carteiro] no ar; olhando as caixas de " + ", ".join(correio.CAIXAS))
        while True:
            try:
                entregue = self.uma_volta()
            except Exception as exc:                           # noqa: BLE001
                # uma volta que quebra nao derruba o carteiro (IAS-5): a
                # 2a falha dentro do `except` de uma entrega matava o processo
                import traceback
                self.log("[carteiro] a volta falhou; sigo na próxima:\n"
                         + traceback.format_exc().rstrip())
                self._estado("ocioso", nota=f"volta falhou: {type(exc).__name__}")
                if uma_vez:
                    return 1
                if parar is not None and parar():
                    return 0
                self.dormir(intervalo)
                continue
            if uma_vez and entregue is not None:
                return 0
            if entregue is None:
                if uma_vez:
                    return 0
                if parar is not None and parar():
                    return 0
                # PULSO NO LOG (maquina.md #3, 11/10/2026): o carteiro ficou
                # 38 h vivo e calado, sem uma linha, e nao dava para separar
                # "ocioso" de "travado". Ocioso fala a cada `PULSO_OCIOSO_S`.
                agora = self.relogio()
                if agora - self._ultimo_pulso_ocioso >= PULSO_OCIOSO_S:
                    self._ultimo_pulso_ocioso = agora
                    self.log("[carteiro] vivo; olhando as caixas")
                self.dormir(intervalo)


def avisar_telegram(texto: str, *, chave: str | None = None) -> bool:
    """Um aviso em texto puro para os autorizados (sem Markdown: ids com `_`).

    E por aqui que sai tudo o que o coordenador avisa; passa pelo porteiro
    (`remoto.avisos`): o mesmo texto, fora hora e data, so uma vez por dia.
    True quando saiu ou quando o porteiro calou (ja saiu hoje): o supervisor
    e a assembleia nao mudam. A situacao em texto: `avisar_telegram_situacao`.
    """
    return avisar_telegram_situacao(texto, chave=chave) in ("entregue", "calado")


def avisar_telegram_situacao(texto: str, *, chave: str | None = None) -> str:
    """O aviso, e O QUE ACONTECEU com ele (IAS-8, 11/10/2026: o porteiro que
    calava saia no log como "entregue"):

      entregue     ao menos um autorizado recebeu;
      calado       o porteiro calou (o mesmo texto ja saiu hoje);
      enfileirado  nao saiu (sem rede): fica na fila e o bot manda depois;
      sem_destino  ninguem autorizado no remoto.
    """
    from remoto import avisos
    from remoto import config as rconfig
    from remoto.api import Telegram
    destinos = rconfig.carregar().get("autorizados") or []
    if not destinos:
        return "sem_destino"
    if not avisos.liberar(texto, chave=chave, origem="carteiro.avisar_telegram"):
        return "calado"
    tg = Telegram(rconfig.token())
    entregues = 0
    for chat in destinos:
        try:
            # sem rede o `mensagem` devolve {} sem levantar: so `ok` e entrega
            if tg.mensagem(chat, str(texto)[:3500]).get("ok"):
                entregues += 1
        except Exception:                                      # noqa: BLE001
            pass
    origem = "carteiro.avisar_telegram"
    if entregues:
        avisos.confirmar(texto, chave=chave, origem=origem)
        return "entregue"
    # 09/10/2026: o aviso que nao saiu calava os iguais por um dia; agora
    # volta a valer e o bot o manda quando a rede voltar
    avisos.desfazer(texto, chave=chave)
    avisos.enfileirar(texto, chave=chave, origem=origem)
    return "enfileirado"


def avisar_telegram_arquivo(caminho, legenda: str = "") -> bool:
    """A imagem como DOCUMENTO (bytes originais) para os autorizados."""
    from remoto import config as rconfig
    from remoto.api import Telegram
    destinos = rconfig.carregar().get("autorizados") or []
    if not destinos:
        return False
    tg = Telegram(rconfig.token())
    entregues = 0
    for chat in destinos:
        try:
            resposta = tg.arquivo(chat, caminho, legenda=str(legenda)[:1000],
                                  como_video=False)
            if (resposta or {}).get("ok"):
                entregues += 1
        except Exception:                                      # noqa: BLE001
            pass
    return entregues > 0


def main(args) -> int:
    """`python -m ias carteiro`: um carteiro so por vez (trava propria)."""
    import sys
    import builds.travas as travas
    if getattr(args, "saida", None):
        # O proprio Python abre o log: o `>>` do cmd tranca o arquivo e a
        # segunda tarefa morre sem rastro (memoria agendador-arquivo-trancado).
        alvo = Path(args.saida)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        fh = open(alvo, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = fh
    nome = "ias__carteiro" + ("__duble" if args.duble else "")
    if args.duble:
        fabrica = fabrica_duble(responder=lambda t: f"OK (dublê) — recebi: {t[:80]}",
                                demora_s=float(getattr(args, "demora", 2.0)))
        # O dublê nunca toca a trava REAL da conta (ela e da pipeline) nem o
        # Telegram: trava propria por IA e aviso no log.
        from .imagem import fabrica_imagem_duble
        carteiro = Carteiro(fabrica_de_sessao=fabrica,
                            fabrica_imagem=fabrica_imagem_duble(
                                demora_s=float(getattr(args, "demora", 2.0))),
                            nome_da_trava=lambda ia: f"ias__duble__{ia}",
                            avisar=lambda texto: _log_padrao(f"[telegram-duble] {texto[:120]}"),
                            avisar_arquivo=lambda caminho, legenda: _log_padrao(
                                f"[telegram-duble] documento {Path(caminho).name}: "
                                f"{legenda[:100]}"),
                            ajustes={"janela_conversa_s": float(getattr(args, "janela", 20))},
                            de_servico=True)
    else:
        carteiro = Carteiro(de_servico=True)
    with travas.trava(nome, esperar=0.0) as minha:
        if not minha:
            _log_padrao("[carteiro] ja ha um carteiro rodando; saio.")
            return 3
        try:
            return carteiro.rodar(uma_vez=bool(args.uma_vez), intervalo=args.intervalo)
        except KeyboardInterrupt:
            carteiro._estado("parado", nota="interrompido")
            return 0


__all__ = ["Carteiro", "SessaoDuble", "SessaoReal", "fabrica_duble", "motivo_da_tela",
           "tela_do_turno",
           "avisar_telegram_arquivo",
           "classificar_erro", "config", "sessao_real", "avisar_telegram",
           "avisar_telegram_situacao", "rede_caiu", "AVISO_PREVIA",
           "e_raiz", "e_recusa", "resumo_aceitavel", "chrome_caiu",
           "PEDIDO_RESUMO", "PROLOGO_CASA_NOVA"]
