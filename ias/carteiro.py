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


def _log_padrao(msg: str) -> None:
    print(f"{datetime.now():%d/%m %H:%M:%S} {msg}", flush=True)


# ================================================================ sessoes
class SessaoReal:
    """Uma IA aberta no navegador, por cima do `ClienteLLM` das historias."""

    def __init__(self, cliente, log=_log_padrao):
        self.cliente = cliente
        self.log = log

    @property
    def modelo(self) -> str:
        return getattr(self.cliente, "modelo_atual", "") or ""

    def _sem_query(self, url: str) -> str:
        return re.sub(r"[?#].*$", "", str(url or "")).rstrip("/")

    def abrir_casa(self, url: str) -> bool:
        """Reabre o chat da casa. True so com PROVA de que a conversa carregou."""
        from contos.llm import seletores as sel
        c = self.cliente
        site = self._sem_query(c.sel["url"])
        if not url or not self._sem_query(url).startswith(site.rsplit("/", 1)[0]):
            return False
        c.page.goto(url, wait_until="domcontentloaded",
                    timeout=int(float(c.ajustes.get("navigation_timeout", 90)) * 1000))
        c._esperar_montar()
        if not c.logado():
            from contos.llm.cliente import NaoLogado
            raise NaoLogado(f"a sessao do {c.provedor} nao esta valida neste perfil")
        turno = sel.encontrar_oculto(c.page, c.sel.get("turno_usuario") or [], timeout=10.0)
        if turno is None:
            self.log(f"[carteiro] {c.provedor}: a casa abriu sem nenhum turno nosso na tela")
            return False
        if self._sem_query(c.page.url) != self._sem_query(url):
            self.log(f"[carteiro] {c.provedor}: a casa redirecionou para {c.page.url}")
            return False
        c.turnos = 0
        c._ultima_resposta = ""
        c.modelo_atual = c.escolher_modelo()
        return True

    def novo_chat(self) -> None:
        self.cliente.abrir(novo_chat=True)

    def perguntar(self, texto: str, anexos=None) -> str:
        c = self.cliente
        if anexos and not (c.sel.get("anexo_prova") or []):
            from contos.llm.cliente import LLMFalhou
            raise LLMFalhou(
                f"o cliente do {c.provedor} ainda nao sabe confirmar anexo na tela "
                "(seletores `anexo_prova` vazios em contos/llm/seletores.py): mande sem anexo")
        return c.perguntar(texto, anexos=list(anexos) if anexos else None)

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
    'visivel' que o classificador de erro vai ler."""

    def __init__(self, ia: str, *, responder=None, falhar=None, tela: str = "",
                 casa_abre: bool = True, demora_s: float = 0.0, dormir=time.sleep):
        self.ia = ia
        self.responder = responder or (lambda texto: "OK (dublê)")
        self.falhar = falhar
        self.tela = tela
        self.casa_abre = casa_abre
        self.demora_s = demora_s
        self.dormir = dormir
        self.modelo = "dublê"
        self.turnos: list = []
        self._url = ""
        self.casas_novas = 0

    def abrir_casa(self, url: str) -> bool:
        if url and self.casa_abre:
            self._url = url
            return True
        return False

    def novo_chat(self) -> None:
        self.casas_novas += 1
        self._url = f"https://duble.local/{self.ia}/c/{self.casas_novas}-{int(time.time())}"

    def perguntar(self, texto: str, anexos=None) -> str:
        self.turnos.append({"texto": texto, "anexos": list(anexos or [])})
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


def classificar_erro(ia: str, exc: BaseException, tela: str = "") -> tuple:
    """(categoria, motivo legivel) de uma entrega que falhou.

    A ordem: o tipo da excecao (login caido, conta ocupada), depois os textos
    conhecidos da FICHA da IA (`catalogo_textos`, medidos na fase 1), depois
    o que a tela mostra agora (`catalogo.varrer`), e so entao a excecao crua.
    """
    nome = type(exc).__name__
    if nome == "NaoLogado":
        return ("login", f"a sessão do {correio.ROTULOS.get(ia, ia)} caiu no PC: "
                         f"faça login de novo (python main.py llm login --provedor {ia})")
    if nome == "ContaOcupada":
        return ("conta_ocupada", "a conta está em uso pela pipeline; tente de novo")
    tela_baixa = " ".join(str(tela or "").split()).lower()
    if tela_baixa:
        try:
            conhecidos = fichas.carregar(ia).get("catalogo_textos") or []
        except Exception:                                      # noqa: BLE001
            conhecidos = []
        for item in conhecidos:
            texto = " ".join(str(item.get("texto") or "").split()).lower()
            if (item.get("categoria") in CATEGORIAS_DE_TELA and len(texto) >= 12
                    and texto in tela_baixa):
                return (item["categoria"], f"o site diz: «{item['texto'][:160]}»")
        for item in catalogo.varrer(str(tela)):
            if item["categoria"] in CATEGORIAS_DE_TELA:
                return (item["categoria"], f"o site diz: «{item['texto'][:160]}»")
    mensagem = " ".join(str(exc).split())[:220]
    categoria = catalogo.classificar(mensagem) or "erro"
    return (categoria, f"{nome}: {mensagem}" if mensagem else nome)


# ================================================================= carteiro
class Carteiro:
    def __init__(self, *, fabrica_de_sessao=None, trava=None, nome_da_trava=None,
                 avisar=None, log=_log_padrao, dormir=time.sleep, relogio=time.monotonic,
                 ajustes: dict | None = None):
        self.ajustes = dict(config())
        self.ajustes.update(ajustes or {})
        self.fabrica = fabrica_de_sessao or self._fabrica_real
        self.trava = trava or self._trava_real
        self.nome_da_trava = nome_da_trava or self._nome_da_trava_real
        self.avisar = avisar if avisar is not None else avisar_telegram
        self.log = log
        self.dormir = dormir
        self.relogio = relogio
        self.entregues = 0
        self._ultimo_pulso = 0.0

    # ------------------------------------------------------------ real
    def _fabrica_real(self, ia: str):
        headless = bool((self.ajustes.get("headless") or {}).get(ia, False))
        return sessao_real(ia, headless=headless, log=self.log,
                           resposta_timeout_s=float(self.ajustes.get("resposta_timeout_s", 420)))

    @staticmethod
    def _trava_real(nome: str, esperar: float):
        import builds.travas as travas
        return travas.trava(nome, esperar=esperar)

    @staticmethod
    def _nome_da_trava_real(ia: str) -> str:
        import builds.travas as travas
        return travas.do_perfil(ia, "geral")

    # ---------------------------------------------------------- estado
    def _estado(self, situacao: str, ia: str | None = None, mensagem_id: str | None = None,
                desde: str | None = None, nota: str = "") -> None:
        try:
            correio.gravar_estado_do_carteiro({
                "situacao": situacao, "ia": ia, "mensagem_id": mensagem_id,
                "desde": desde or correio.agora(), "nota": nota,
                "entregues": self.entregues})
        except OSError:
            pass

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
        """Entrega UMA mensagem pendente (e as que chegarem na janela)."""
        ia = str(mensagem["para"])
        mid = str(mensagem["id"])
        desde = correio.agora()
        nome = self.nome_da_trava(ia)
        inicio = self.relogio()
        limite = float(self.ajustes.get("espera_conta_max_s", 10800))
        avisou = False
        while True:
            self._estado("esperando_trava" if avisou else "entregando", ia, mid, desde,
                         nota=f"esperando a pipeline soltar a conta ({nome})" if avisou else "")
            with self.trava(nome, esperar=PASSO_TRAVA_S) as minha:
                if minha:
                    if avisou:
                        self.log(f"[carteiro] a conta do {ia} soltou; entregando {mid}")
                    return self._entregar_com_a_conta(ia, mensagem, desde)
            if not avisou:
                avisou = True
                self.log(f"[carteiro] a conta do {ia} ({nome}) esta com a pipeline; "
                         f"espero ela soltar (mensagem {mid})")
                correio.atualizar(ia, mid, nota=f"esperando a pipeline soltar a conta "
                                                f"(desde {desde[11:16]})")
                self._diario(ia, "log", f"carteiro: esperando a pipeline soltar {nome}", mid)
            if self.relogio() - inicio >= limite:
                motivo = (f"a conta do {correio.ROTULOS.get(ia, ia)} ficou com a pipeline por "
                          f"{limite / 3600:.0f} h; não entreguei. Mande de novo mais tarde.")
                self.log(f"[carteiro] {mid}: {motivo}")
                atualizada = correio.atualizar(ia, mid, situacao="falhou", erro=motivo,
                                               categoria="conta_ocupada",
                                               falhou_em=correio.agora(), nota=None)
                self._anunciar(ia, atualizada)
                return atualizada

    def _entregar_com_a_conta(self, ia: str, mensagem: dict, desde: str) -> dict:
        mid = str(mensagem["id"])
        self._estado("entregando", ia, mid, desde)
        ultima = mensagem
        try:
            with self.fabrica(ia) as sessao:
                casa = self._abrir_casa(ia, sessao)
                fila = [mensagem]
                while fila:
                    atual = fila.pop(0)
                    ultima = self._um_turno(ia, sessao, casa, atual)
                    if ultima["situacao"] != "respondida":
                        break
                    proxima = self._esperar_proxima(ia)
                    if proxima is not None:
                        fila.append(proxima)
        except Exception as exc:                               # noqa: BLE001
            # A sessao nem abriu (login caido, Chrome ocupado, site fora):
            # a mensagem que estava na mao falha com o motivo legivel.
            pendente = correio.uma(ia, mid)
            if pendente is not None and pendente["situacao"] in ("pendente", "entregue"):
                categoria, motivo = classificar_erro(ia, exc)
                self.log(f"[carteiro] {ia} {mid}: {motivo}")
                ultima = correio.atualizar(ia, mid, situacao="falhou", erro=motivo,
                                           categoria=categoria, falhou_em=correio.agora(),
                                           nota=None)
                self._anunciar(ia, ultima)
                casa = correio.casa(ia)
                casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
                correio.gravar_casa(ia, casa)
        finally:
            self._estado("ocioso")
        return ultima

    def _abrir_casa(self, ia: str, sessao) -> dict:
        casa = correio.casa(ia)
        aberta = False
        if casa.get("url") and int(casa.get("falhas_seguidas") or 0) < 2:
            try:
                aberta = bool(sessao.abrir_casa(casa["url"]))
            except Exception as exc:                           # noqa: BLE001
                if type(exc).__name__ == "NaoLogado":
                    raise
                self.log(f"[carteiro] {ia}: a casa nao abriu ({type(exc).__name__}); "
                         "comeco uma nova")
                aberta = False
        if aberta:
            self.log(f"[carteiro] {ia}: casa reaberta (geracao {casa.get('geracao')}, "
                     f"{casa.get('mensagens')} mensagens)")
            return casa
        sessao.novo_chat()
        resumo = correio.resumo_da_casa(ia)
        nova = correio.casa_vazia(ia)
        nova["geracao"] = int(casa.get("geracao") or 0) + 1
        nova["aberta_em"] = correio.agora()
        if resumo.strip():
            try:
                sessao.perguntar(PROLOGO_CASA_NOVA + resumo.strip())
                nova["comecou_com_resumo"] = True
                self.log(f"[carteiro] {ia}: casa nova (geracao {nova['geracao']}) "
                         "aberta com o resumo da anterior")
            except Exception as exc:                           # noqa: BLE001
                self.log(f"[carteiro] {ia}: o resumo nao entrou na casa nova "
                         f"({type(exc).__name__}); sigo sem ele")
        else:
            self.log(f"[carteiro] {ia}: casa nova (geracao {nova['geracao']})")
        correio.gravar_casa(ia, nova)
        return nova

    def _um_turno(self, ia: str, sessao, casa: dict, mensagem: dict) -> dict:
        mid = str(mensagem["id"])
        desde = correio.agora()
        correio.atualizar(ia, mid, situacao="entregue", entregue_em=desde, nota=None)
        self._estado("entregando", ia, mid, desde)
        if hasattr(sessao, "cliente"):
            sessao.cliente.log = self._log_com_pulso(ia, mid, desde)
        t0 = self.relogio()
        try:
            resposta = sessao.perguntar(mensagem.get("texto") or "",
                                        anexos=mensagem.get("anexos") or None)
        except Exception as exc:                               # noqa: BLE001
            categoria, motivo = classificar_erro(ia, exc, sessao.texto_visivel())
            self.log(f"[carteiro] {ia} {mid} falhou: {motivo}")
            casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
            correio.gravar_casa(ia, casa)
            atualizada = correio.atualizar(ia, mid, situacao="falhou", erro=motivo,
                                           categoria=categoria, falhou_em=correio.agora())
            self._anunciar(ia, atualizada)
            return atualizada
        dur = self.relogio() - t0
        resposta = str(resposta or "").strip()
        casa["url"] = sessao.url() or casa.get("url")
        casa["mensagens"] = int(casa.get("mensagens") or 0) + 1
        casa["falhas_seguidas"] = 0
        correio.gravar_casa(ia, casa)
        atualizada = correio.atualizar(
            ia, mid, situacao="respondida", resposta=resposta,
            respondida_em=correio.agora(), dur_s=round(dur, 1),
            modelo=getattr(sessao, "modelo", "") or "")
        self.entregues += 1
        self.log(f"[carteiro] {ia} {mid}: respondida ({len(resposta)} chars em {dur:.0f}s)")
        self._anunciar(ia, atualizada)
        if (casa["mensagens"] - int(casa.get("resumo_mensagens") or 0)
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
        correio.gravar_resumo_da_casa(ia, texto)
        casa["resumo_mensagens"] = int(casa.get("mensagens") or 0)
        casa["ultimo_resumo_em"] = correio.agora()
        correio.gravar_casa(ia, casa)
        self.log(f"[carteiro] {ia}: resumo da casa guardado ({len(texto)} chars)")
        self._diario(ia, "log", f"carteiro: resumo da casa ({len(texto)} chars)", "")
        return True

    def _esperar_proxima(self, ia: str) -> dict | None:
        """Segura a conta por `janela_conversa_s` esperando a proxima dele."""
        janela = float(self.ajustes.get("janela_conversa_s", 90))
        fim = self.relogio() + janela
        while True:
            fila = correio.pendentes(ia)
            if fila:
                return fila[0]
            if self.relogio() >= fim:
                return None
            self._estado("entregando", ia, None, correio.agora(),
                         nota="conversa aberta: esperando a próxima mensagem")
            self.dormir(min(3.0, max(0.1, fim - self.relogio())))

    # ---------------------------------------------------------- anuncio
    def _anunciar(self, ia: str, mensagem: dict) -> None:
        rotulo = correio.ROTULOS.get(ia, ia)
        if mensagem["situacao"] == "respondida":
            texto = f"💬 {rotulo} respondeu:\n{str(mensagem.get('resposta') or '')[:1500]}"
        else:
            texto = (f"⚠ {rotulo}: não consegui entregar sua mensagem — "
                     f"{mensagem.get('erro') or 'sem motivo'}")
        if correio.app_esta_olhando(ia):
            self.log(f"[carteiro] {ia}: o app esta olhando a caixa; sem Telegram")
            return
        try:
            entregue = self.avisar(texto)
            self.log(f"[carteiro] {ia}: aviso no Telegram "
                     f"{'entregue' if entregue is not False else 'NAO entregue'}")
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[carteiro] o aviso no Telegram falhou ({type(exc).__name__})")

    def _diario(self, ia: str, status: str, detalhe: str, ref: str) -> None:
        try:
            import builds.atividade as atividade
            atividade.registrar(ia, status, detalhe, "adrian", etapa="correio", ref=ref)
        except Exception:                                      # noqa: BLE001
            pass

    # -------------------------------------------------------------- laco
    def uma_volta(self) -> dict | None:
        mensagem = correio.proxima_pendente()
        if mensagem is None:
            self._estado("ocioso")
            return None
        return self.entregar(mensagem)

    def rodar(self, *, uma_vez: bool = False, intervalo: float | None = None,
              parar=None) -> int:
        intervalo = float(self.ajustes.get("intervalo_s", 5) if intervalo is None else intervalo)
        self._estado("ocioso")
        self.log("[carteiro] no ar; olhando as caixas de " + ", ".join(correio.CHATS))
        while True:
            entregue = self.uma_volta()
            if uma_vez and entregue is not None:
                return 0
            if entregue is None:
                if uma_vez:
                    return 0
                if parar is not None and parar():
                    return 0
                self.dormir(intervalo)


def avisar_telegram(texto: str) -> bool:
    """Um aviso em texto puro para os autorizados (sem Markdown: ids com `_`)."""
    from remoto import config as rconfig
    from remoto.api import Telegram
    destinos = rconfig.carregar().get("autorizados") or []
    if not destinos:
        return False
    tg = Telegram(rconfig.token())
    entregues = 0
    for chat in destinos:
        try:
            tg.mensagem(chat, str(texto)[:3500])
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
        carteiro = Carteiro(fabrica_de_sessao=fabrica,
                            nome_da_trava=lambda ia: f"ias__duble__{ia}",
                            avisar=lambda texto: _log_padrao(f"[telegram-duble] {texto[:120]}"),
                            ajustes={"janela_conversa_s": float(getattr(args, "janela", 20))})
    else:
        carteiro = Carteiro()
    with travas.trava(nome, esperar=0.0) as minha:
        if not minha:
            _log_padrao("[carteiro] ja ha um carteiro rodando; saio.")
            return 3
        try:
            return carteiro.rodar(uma_vez=bool(args.uma_vez), intervalo=args.intervalo)
        except KeyboardInterrupt:
            carteiro._estado("parado", nota="interrompido")
            return 0


__all__ = ["Carteiro", "SessaoDuble", "SessaoReal", "fabrica_duble",
           "classificar_erro", "config", "sessao_real", "avisar_telegram",
           "PEDIDO_RESUMO", "PROLOGO_CASA_NOVA"]
