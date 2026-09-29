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

    def gerar_imagem(self, prompt: str, proporcao: str, mensagem_id: str = "") -> dict:
        """Pede a imagem NA CASA (o chat ja aberto) e baixa a que nasce depois
        do nosso turno (`imagem.gerar_no_chat`, pelo `perguntar` de sempre: o
        turno vai ao diario como os de texto)."""
        from . import imagem
        return imagem.gerar_no_chat(self.cliente, prompt, proporcao, log=self.log)

    def imagem_da_resposta(self, prompt: str) -> dict | None:
        """A imagem que a ULTIMA resposta de conversa trouxe (o Gemini que
        desenha quando ele pede "gere um gato"), ou None."""
        from . import imagem
        return imagem.baixar_da_resposta(self.cliente, prompt, log=self.log)

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
                 casa_abre: bool = True, demora_s: float = 0.0, dormir=time.sleep,
                 imagem_falhar=None, imagem_sem_prova: bool = False,
                 responder_com_imagem: bool = False):
        self.ia = ia
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
        self.casas_novas = 0
        from .imagem import SessaoImagemDuble
        # a imagem na casa: o mesmo dublê do PicassoIA, sem navegador
        self._imagem = SessaoImagemDuble(ia, falhar=imagem_falhar,
                                         sem_prova=imagem_sem_prova, tela=tela,
                                         demora_s=demora_s, dormir=dormir)

    def gerar_imagem(self, prompt: str, proporcao: str, mensagem_id: str = "") -> dict:
        self.turnos.append({"texto": prompt, "anexos": [], "imagem": proporcao})
        return self._imagem.gerar_imagem(prompt, proporcao, mensagem_id)

    def imagem_da_resposta(self, prompt: str) -> dict | None:
        """Com `responder_com_imagem`, a resposta de conversa traz uma imagem
        (o dublê do Gemini desenhando o gato)."""
        if not self.responder_com_imagem:
            return None
        return self._imagem.gerar_imagem(prompt, "1:1")

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
                and texto in tela_baixa):
            return (item["categoria"], f"o site diz: «{item['texto'][:160]}»")
    for item in catalogo.varrer(str(tela)):
        if item["categoria"] in CATEGORIAS_DE_TELA:
            return (item["categoria"], f"o site diz: «{item['texto'][:160]}»")
    return None


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
    achado = motivo_da_tela(ia, tela)
    if achado:
        return achado
    mensagem = " ".join(str(exc).split())[:220]
    categoria = catalogo.classificar(mensagem) or "erro"
    return (categoria, f"{nome}: {mensagem}" if mensagem else nome)


# ================================================================= carteiro
class _Reabrir(Exception):
    """Parede de planos na primeira volta: fechar o navegador e reabrir."""


class Carteiro:
    def __init__(self, *, fabrica_de_sessao=None, trava=None, nome_da_trava=None,
                 avisar=None, log=_log_padrao, dormir=time.sleep, relogio=time.monotonic,
                 ajustes: dict | None = None, fabrica_imagem=None, avisar_arquivo=None):
        self.ajustes = dict(config())
        self.ajustes.update(ajustes or {})
        self.fabrica = fabrica_de_sessao or self._fabrica_real
        # o PicassoIA (gerador que nao e chat): outra sessao, outro cliente
        self.fabrica_imagem = fabrica_imagem or self._fabrica_imagem_real
        self.trava = trava or self._trava_real
        self.nome_da_trava = nome_da_trava or self._nome_da_trava_real
        self.avisar = avisar if avisar is not None else avisar_telegram
        self.avisar_arquivo = (avisar_arquivo if avisar_arquivo is not None
                               else avisar_telegram_arquivo)
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
        """Entrega UMA mensagem pendente (e as que chegarem na janela).

        Pedido de imagem para a caixa `livre` e o RODIZIO: o carteiro escolhe
        o gerador na hora (`_entregar_livre`). Pedido de imagem para um
        gerador que a ficha diz que nao gera hoje falha na hora, com o motivo
        da ficha, sem abrir navegador.
        """
        caixa = str(mensagem["para"])
        if correio.tipo(mensagem) == "imagem":
            if caixa == correio.LIVRE:
                return self._entregar_livre(mensagem)
            from . import imagem
            info = imagem.gerador(caixa)
            if not info["disponivel"]:
                atualizada = correio.atualizar(
                    caixa, mensagem["id"], situacao="falhou", categoria="indisponivel",
                    erro=f"{info['rotulo']} não gera imagem hoje: {info['motivo']}",
                    falhou_em=correio.agora(), nota=None)
                self._anunciar(caixa, atualizada)
                return atualizada
        return self._com_a_conta(caixa, caixa, mensagem)

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
            self._estado("esperando_trava" if avisou else "entregando", ia, mid, desde,
                         nota=f"esperando a pipeline soltar a conta ({nome})" if avisou else "")
            with self.trava(nome, esperar=PASSO_TRAVA_S) as minha:
                if minha:
                    if avisou:
                        self.log(f"[carteiro] a conta do {ia} soltou; entregando {mid}")
                    return self._entregar_com_a_conta(caixa, ia, mensagem, desde)
            if not avisou:
                avisou = True
                self.log(f"[carteiro] a conta do {ia} ({nome}) esta com a pipeline; "
                         f"espero ela soltar (mensagem {mid})")
                correio.atualizar(caixa, mid, nota=f"esperando a pipeline soltar a conta "
                                                   f"(desde {desde[11:16]})")
                self._diario(ia, "log", f"carteiro: esperando a pipeline soltar {nome}", mid)
            if self.relogio() - inicio >= limite:
                motivo = (f"a conta do {correio.ROTULOS.get(ia, ia)} ficou com a pipeline por "
                          f"{limite / 3600:.0f} h; não entreguei. Mande de novo mais tarde.")
                self.log(f"[carteiro] {mid}: {motivo}")
                atualizada = correio.atualizar(caixa, mid, situacao="falhou", erro=motivo,
                                               categoria="conta_ocupada",
                                               falhou_em=correio.agora(), nota=None)
                self._anunciar(caixa, atualizada)
                return atualizada

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
        ordem = [g for g in (self.ajustes.get("rodizio_imagem") or imagem.rodizio_ordem())
                 if g in correio.GERADORES]
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
                fora = imagem.fora_de_cota(g, horas)
                if fora:
                    motivos.append(f"{info['rotulo']}: {fora}")
                    continue
                nome = self.nome_da_trava(g)
                with self.trava(nome, esperar=0.0) as minha:
                    if minha:
                        self.log(f"[carteiro] rodizio {mid}: {g} esta livre")
                        correio.atualizar(caixa, mid, gerador=g, nota=None,
                                          rodizio=f"{info['rotulo']} estava livre")
                        return self._entregar_com_a_conta(
                            caixa, g, dict(mensagem, gerador=g), desde)
                ocupados.append(info["rotulo"])
            if not ocupados:
                motivo = ("nenhum gerador do rodízio pode gerar agora — "
                          + "; ".join(motivos))[:600]
                atualizada = correio.atualizar(caixa, mid, situacao="falhou",
                                               categoria="rodizio", erro=motivo,
                                               falhou_em=correio.agora(), nota=None)
                self._anunciar(caixa, atualizada)
                return atualizada
            if not avisou:
                avisou = True
                correio.atualizar(caixa, mid, nota="rodízio: todas as contas ocupadas "
                                  f"({', '.join(ocupados)}); esperando uma soltar")
            self._estado("esperando_trava", None, mid, desde,
                         nota=f"rodízio: esperando {', '.join(ocupados)}")
            if self.relogio() - inicio >= limite:
                motivo = (f"as contas do rodízio ({', '.join(ocupados)}) ficaram ocupadas "
                          f"por {limite / 3600:.0f} h; não gerei. Peça de novo mais tarde.")
                atualizada = correio.atualizar(caixa, mid, situacao="falhou", erro=motivo,
                                               categoria="conta_ocupada",
                                               falhou_em=correio.agora(), nota=None)
                self._anunciar(caixa, atualizada)
                return atualizada
            self.dormir(PASSO_TRAVA_S)

    def _entregar_com_a_conta(self, caixa: str, ia: str, mensagem: dict, desde: str) -> dict:
        mid = str(mensagem["id"])
        self._estado("entregando", ia, mid, desde)
        ultima = mensagem
        if ia not in correio.CHATS:
            return self._imagem_fora_do_chat(caixa, ia, mensagem, desde)
        try:
            with self.fabrica(ia) as sessao:
                casa = self._abrir_casa(ia, sessao)
                fila = [(caixa, mensagem)]
                while fila:
                    onde, atual = fila.pop(0)
                    ultima = self._um_turno(ia, sessao, casa, atual, caixa=onde)
                    if ultima["situacao"] != "respondida":
                        break
                    proxima = self._esperar_proxima(ia)
                    if proxima is not None:
                        fila.append((ia, proxima))
        except Exception as exc:                               # noqa: BLE001
            # A sessao nem abriu (login caido, Chrome ocupado, site fora):
            # a mensagem que estava na mao falha com o motivo legivel.
            pendente = correio.uma(caixa, mid)
            if pendente is not None and pendente["situacao"] in ("pendente", "entregue"):
                categoria, motivo = classificar_erro(ia, exc)
                self.log(f"[carteiro] {ia} {mid}: {motivo}")
                ultima = correio.atualizar(caixa, mid, situacao="falhou", erro=motivo,
                                           categoria=categoria, falhou_em=correio.agora(),
                                           nota=None)
                self._anunciar(caixa, ultima)
                casa = correio.casa(ia)
                casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
                correio.gravar_casa(ia, casa)
        finally:
            self._estado("ocioso")
        return ultima

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
            if pendente is not None and pendente["situacao"] in ("pendente", "entregue"):
                categoria, motivo = imagem.classificar(ia, exc)
                self.log(f"[carteiro] {ia} {mid}: {motivo}")
                ultima = correio.atualizar(caixa, mid, situacao="falhou", erro=motivo,
                                           categoria=categoria, falhou_em=correio.agora(),
                                           nota=None, gerador=ia)
                self._anunciar(caixa, ultima)
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

    def _turno_imagem(self, caixa: str, ia: str, sessao, mensagem: dict,
                      casa: dict | None, relancar_parede: bool = False) -> dict:
        """UM pedido de imagem: gera, exige prova, grava os bytes originais com
        a prova ao lado, e so entao marca respondida. Sem prova, nada vai ao
        disco e o pedido falha com o motivo."""
        from . import imagem
        mid = str(mensagem["id"])
        desde = correio.agora()
        info = imagem.gerador(ia)
        if not info["disponivel"]:
            atualizada = correio.atualizar(
                caixa, mid, situacao="falhou", categoria="indisponivel", gerador=ia,
                erro=f"{info['rotulo']} não gera imagem hoje: {info['motivo']}",
                falhou_em=correio.agora(), nota=None)
            self._anunciar(caixa, atualizada)
            return atualizada
        correio.atualizar(caixa, mid, situacao="entregue", entregue_em=desde, gerador=ia,
                          nota=None)
        self._estado("entregando", ia, mid, desde, nota="gerando imagem")
        if hasattr(sessao, "cliente"):
            sessao.cliente.log = self._log_com_pulso(ia, mid, desde)
        t0 = self.relogio()
        prompt = str(mensagem.get("texto") or "")
        proporcao = str(mensagem.get("proporcao") or info["proporcao_padrao"])
        try:
            resultado = sessao.gerar_imagem(prompt, proporcao, mid)
            salvo = imagem.guardar(ia, mid, resultado.get("bytes") or b"",
                                   resultado.get("prova") or {})
        except Exception as exc:                               # noqa: BLE001
            if relancar_parede and type(exc).__name__ == "ParedeDePlanos":
                raise _Reabrir() from exc
            tela = ""
            try:
                tela = sessao.texto_visivel()
            except Exception:                                  # noqa: BLE001
                pass
            categoria, motivo = imagem.classificar(ia, exc, tela)
            self.log(f"[carteiro] {ia} {mid} (imagem) falhou: {motivo}")
            if casa is not None:
                casa["falhas_seguidas"] = int(casa.get("falhas_seguidas") or 0) + 1
                correio.gravar_casa(ia, casa)
            atualizada = correio.atualizar(caixa, mid, situacao="falhou", erro=motivo,
                                           categoria=categoria, falhou_em=correio.agora(),
                                           gerador=ia)
            self._anunciar(caixa, atualizada)
            return atualizada
        reivindicar = getattr(sessao, "reivindicar", None)
        if callable(reivindicar):
            reivindicar(resultado, mid)
        dur = self.relogio() - t0
        if casa is not None:
            casa["url"] = sessao.url() or casa.get("url")
            casa["mensagens"] = int(casa.get("mensagens") or 0) + 1
            casa["falhas_seguidas"] = 0
            correio.gravar_casa(ia, casa)
        kb = max(1, round(int(salvo["bytes"]) / 1024))
        medida = (f"{salvo['largura']}x{salvo['altura']}"
                  if salvo.get("largura") else salvo["formato"].upper())
        atualizada = correio.atualizar(
            caixa, mid, situacao="respondida", gerador=ia,
            resposta=f"imagem pronta · {medida} · {kb} KB", imagem=salvo,
            respondida_em=correio.agora(), dur_s=round(dur, 1),
            modelo=str(resultado.get("modelo") or getattr(sessao, "modelo", "") or ""))
        self.entregues += 1
        self.log(f"[carteiro] {ia} {mid}: imagem gravada ({salvo['arquivo']}, {kb} KB, "
                 f"prova {salvo['prova']}) em {dur:.0f}s")
        self._diario(ia, "ok", f"carteiro: imagem {medida} ({salvo['prova']})", mid)
        self._anunciar(caixa, atualizada)
        return atualizada

    def _um_turno(self, ia: str, sessao, casa: dict, mensagem: dict,
                  caixa: str | None = None) -> dict:
        if correio.tipo(mensagem) == "imagem":
            return self._turno_imagem(caixa or ia, ia, sessao, mensagem, casa)
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
                    salvo = imagem.guardar(ia, mid, achada.get("bytes") or b"",
                                           achada.get("prova") or {})
                    extra = {"imagem": salvo, "gerador": ia}
                    kb = max(1, round(int(salvo["bytes"]) / 1024))
                    medida = (f"{salvo['largura']}x{salvo['altura']}"
                              if salvo.get("largura") else salvo["formato"].upper())
                    self.log(f"[carteiro] {ia} {mid}: a resposta trouxe uma imagem "
                             f"({salvo['arquivo']}, {medida}, {kb} KB)")
                    if not resposta:
                        resposta = f"(imagem · {medida} · {kb} KB)"
            except Exception as exc:                           # noqa: BLE001
                categoria, motivo = imagem.classificar(ia, exc)
                self.log(f"[carteiro] {ia} {mid}: a imagem da resposta nao foi guardada: "
                         f"{motivo}")
                if not resposta:
                    atualizada = correio.atualizar(
                        ia, mid, situacao="falhou", erro=f"a resposta foi uma imagem, mas "
                        f"ela não foi guardada: {motivo}", categoria=categoria,
                        falhou_em=correio.agora())
                    self._anunciar(ia, atualizada)
                    return atualizada
                extra = {"nota": f"a resposta trouxe uma imagem que não foi guardada: "
                                 f"{motivo}"[:300]}
        casa["url"] = sessao.url() or casa.get("url")
        casa["mensagens"] = int(casa.get("mensagens") or 0) + 1
        casa["falhas_seguidas"] = 0
        correio.gravar_casa(ia, casa)
        atualizada = correio.atualizar(
            ia, mid, situacao="respondida", resposta=resposta,
            respondida_em=correio.agora(), dur_s=round(dur, 1),
            modelo=getattr(sessao, "modelo", "") or "", **extra)
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
        if correio.tipo(mensagem) == "imagem" or (
                mensagem.get("situacao") == "respondida"
                and isinstance(mensagem.get("imagem"), dict)):
            return self._anunciar_imagem(ia, mensagem)
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
                           + (" (rodízio)" if caixa == correio.LIVRE else ""))
                if caminho is None:
                    entregue = self.avisar(legenda + "\n(a imagem não está no disco)")
                else:
                    entregue = self.avisar_arquivo(caminho, legenda)
            else:
                entregue = self.avisar(f"⚠ {rotulo}: a imagem não saiu — "
                                       f"{mensagem.get('erro') or 'sem motivo'}\n"
                                       f"pedido: {prompt[:200]}")
            self.log(f"[carteiro] {caixa}: aviso no Telegram "
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
        mensagem = correio.proxima_pendente(correio.CAIXAS)
        if mensagem is None:
            self._estado("ocioso")
            return None
        return self.entregar(mensagem)

    def rodar(self, *, uma_vez: bool = False, intervalo: float | None = None,
              parar=None) -> int:
        intervalo = float(self.ajustes.get("intervalo_s", 5) if intervalo is None else intervalo)
        self._estado("ocioso")
        self.log("[carteiro] no ar; olhando as caixas de " + ", ".join(correio.CAIXAS))
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


__all__ = ["Carteiro", "SessaoDuble", "SessaoReal", "fabrica_duble", "motivo_da_tela",
           "avisar_telegram_arquivo",
           "classificar_erro", "config", "sessao_real", "avisar_telegram",
           "PEDIDO_RESUMO", "PROLOGO_CASA_NOVA"]
