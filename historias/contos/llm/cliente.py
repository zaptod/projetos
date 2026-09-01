# -*- coding: utf-8 -*-
"""Conversar com o ChatGPT ou o Gemini pelo browser, sem copiar e colar.

Mesma doutrina do resto do ecossistema: Chrome de verdade com perfil
persistente (login uma vez, na mao), patchright para nao vazar automacao,
pausa humana entre acoes, e NENHUMA acao dada como feita sem prova.

As duas provas que importam aqui:

  ENVIO    o campo esvaziou (ou o botao de parar apareceu). Sem isso um
           prompt que nao entrou no editor viraria "resposta vazia" tres
           tentativas depois, sem ninguem saber por que.
  RESPOSTA o texto PAROU de crescer. Ler assim que aparece texto devolve
           meia resposta - e numa historia longa, meia resposta e um
           roteiro sem final.

O mesmo chat e reusado entre as chamadas de proposito: e o que permite
mandar a biblia da historia primeiro e depois pedir cada parte com o
contexto inteiro ja carregado. Uma serie longa e uma CONVERSA, nao um
prompt gigante.
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from builds.identity import browser as _rb_identity_browser
import builds.contas as _rb_contas
import builds.travas as _rb_travas

from . import seletores as sel

RAIZ = Path(__file__).resolve().parents[2]
PERFIS = RAIZ / ".browser_profile"


class LLMFalhou(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


class NaoLogado(LLMFalhou):
    """A sessao daquele perfil caiu (ou nunca existiu)."""


def perfil_de(provedor: str, canal: str = "geral") -> Path:
    """A pasta de Chrome daquele LLM, na conta ativa.

    Vem do registro de contas do ecossistema (`random_builds/builds/contas.py`),
    entao o login feito aqui serve para qualquer outra coisa que precise do
    mesmo ChatGPT/Gemini depois — era o pedido: logar uma vez, reusar.
    """
    try:
        return _rb_contas.perfil(str(provedor).lower(), canal)
    except Exception:
        caminho = PERFIS / str(provedor).lower()
        caminho.mkdir(parents=True, exist_ok=True)
        return caminho


def _pausa(rng: random.Random, minimo: float = 0.4, maximo: float = 1.2) -> None:
    time.sleep(rng.uniform(minimo, maximo))


class ClienteLLM:
    """Um chat aberto num provedor. Duck typing entre ChatGPT e Gemini:
    o que muda sao os seletores, nao a porta."""

    def __init__(self, provedor: str, ctx, page, ajustes: dict | None = None,
                 rng: random.Random | None = None, log=print):
        self.provedor = str(provedor).lower()
        self.sel = sel.do_provedor(self.provedor)
        self.ctx = ctx
        self.page = page
        self.ajustes = ajustes or {}
        self.rng = rng or random.Random()
        self.log = log
        self.turnos = 0

    # ----------------------------------------------------------- navegacao
    def abrir(self, novo_chat: bool = True) -> None:
        url = self.sel["url_novo_chat"] if novo_chat else self.sel["url"]
        timeout = float(self.ajustes.get("navigation_timeout", 90))
        self.page.goto(url, wait_until="domcontentloaded",
                       timeout=int(timeout * 1000))
        self._esperar_montar()
        if not self.logado():
            raise NaoLogado(
                f"a sessao do {self.provedor} nao esta valida neste perfil.\n"
                f"Rode uma vez: python main.py llm login --provedor {self.provedor} "
                "(a janela abre, voce entra na conta, e o login fica salvo).")
        self.turnos = 0
        self.log(f"[{self.provedor}] chat novo aberto.")

    def _esperar_montar(self, quieto: float = 1.0) -> None:
        """Espera o app hidratar: os dois sites servem HTML vazio e montam
        tudo em JS, entao existir no DOM nao quer dizer utilizavel."""
        limite = time.monotonic() + float(self.ajustes.get("hydration_timeout", 45))
        while time.monotonic() < limite:
            if sel.encontrar(self.page, self.sel["campo"], timeout=1.0) is not None:
                time.sleep(quieto)
                return
            if sel.encontrar(self.page, self.sel["login"], timeout=0.5) is not None:
                return
            time.sleep(0.5)

    def logado(self) -> bool:
        if sel.encontrar(self.page, self.sel["logado"], timeout=6.0) is not None:
            return True
        return sel.encontrar(self.page, self.sel["login"], timeout=1.0) is None

    # -------------------------------------------------------------- envio
    def _texto_do_campo(self, campo) -> str:
        try:
            valor = campo.input_value()
            if valor is not None:
                return valor
        except Exception:
            pass
        try:
            return campo.inner_text()
        except Exception:
            return ""

    def enviar(self, prompt: str) -> None:
        """Cola o prompt e envia. Levanta se nao houver prova de envio."""
        campo = sel.resolver(self.page, self.sel["campo"], "o campo de prompt")
        campo.click()
        _pausa(self.rng, 0.2, 0.5)
        # Colar de uma vez, nunca digitar: um prompt de 4 mil caracteres a
        # 90 ms por tecla seria seis minutos de "digitacao humana" - e
        # justamente por isso, suspeito.
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        campo.fill(prompt) if self._aceita_fill(campo) else \
            self.page.keyboard.insert_text(prompt)
        _pausa(self.rng, 0.5, 1.1)

        antes = self._texto_do_campo(campo)
        if prompt[:40] not in antes and len(antes.strip()) < 20:
            raise LLMFalhou(
                "o prompt nao entrou no editor (o campo continua vazio). "
                f"Rode: python main.py llm probe --provedor {self.provedor}")

        botao = sel.encontrar(self.page, self.sel["enviar"], timeout=5.0)
        if botao is not None:
            try:
                botao.click(timeout=8000)
            except Exception:
                self.page.keyboard.press("Enter")
        else:
            self.page.keyboard.press("Enter")

        if not self._confirmou_envio(campo):
            raise LLMFalhou(
                "cliquei em enviar mas nada mudou na tela: o campo continua "
                "com o texto e nenhuma resposta comecou. Pode ser limite de "
                "uso da conta ou um desafio na tela - abra a janela e olhe.")
        self.turnos += 1

    @staticmethod
    def _aceita_fill(campo) -> bool:
        try:
            return campo.evaluate(
                "el => el.tagName === 'TEXTAREA' || el.tagName === 'INPUT' "
                "|| el.isContentEditable")
        except Exception:
            return False

    def _confirmou_envio(self, campo, espera: float = 25.0) -> bool:
        """Prova de que o turno comecou: o campo esvaziou OU apareceu o
        botao de parar (que so existe enquanto o modelo escreve)."""
        fim = time.monotonic() + espera
        while time.monotonic() < fim:
            if sel.encontrar(self.page, self.sel["parar"], timeout=0.4) is not None:
                return True
            if len(self._texto_do_campo(campo).strip()) < 5:
                return True
            time.sleep(0.4)
        return False

    # ------------------------------------------------------------ resposta
    def _resposta_atual(self) -> str:
        """O texto do ULTIMO turno do assistente."""
        for seletor in self.sel["resposta"]:
            try:
                alvos = self.page.locator(seletor)
                total = alvos.count()
            except Exception:
                continue
            if total:
                try:
                    return alvos.nth(total - 1).inner_text() or ""
                except Exception:
                    continue
        return ""

    def esperar_resposta(self, timeout: float | None = None,
                         estabilidade: float = 2.5) -> str:
        """Espera o modelo TERMINAR e devolve o texto.

        Duas condicoes, e as duas sao necessarias: o botao de parar sumiu
        (o modelo nao esta mais escrevendo) e o texto ficou do mesmo tamanho
        por `estabilidade` segundos. So a primeira falha quando o botao
        pisca entre blocos; so a segunda falha quando o modelo pensa alguns
        segundos antes de escrever.
        """
        timeout = float(timeout if timeout is not None
                        else self.ajustes.get("resposta_timeout", 600))
        inicio = time.monotonic()
        fim = inicio + timeout
        ultimo_tamanho = -1
        parado_desde = None
        ultimo_aviso = 0.0

        while time.monotonic() < fim:
            texto = self._resposta_atual()
            escrevendo = sel.encontrar(self.page, self.sel["parar"],
                                       timeout=0.3) is not None
            if len(texto) != ultimo_tamanho:
                ultimo_tamanho = len(texto)
                parado_desde = None
            elif not escrevendo and texto.strip():
                parado_desde = parado_desde or time.monotonic()
                if time.monotonic() - parado_desde >= estabilidade:
                    decorrido = time.monotonic() - inicio
                    self.log(f"[{self.provedor}] resposta pronta: "
                             f"{len(texto)} chars em {decorrido:.0f}s")
                    return texto
            decorrido = time.monotonic() - inicio
            if decorrido - ultimo_aviso >= 20:
                ultimo_aviso = decorrido
                self.log(f"[{self.provedor}] escrevendo... {decorrido:.0f}s "
                         f"({ultimo_tamanho} chars)", )
            time.sleep(1.0)

        texto = self._resposta_atual()
        if texto.strip():
            self.log(f"[{self.provedor}] espera estourou em {timeout:.0f}s; "
                     "uso o que ja veio.")
            return texto
        raise LLMFalhou(
            f"o {self.provedor} nao respondeu em {timeout:.0f}s e nao ha texto "
            "na tela. Verifique se a conta atingiu o limite de uso.")

    def perguntar(self, prompt: str, timeout: float | None = None) -> str:
        """Um turno completo: envia, espera, devolve o texto."""
        self.enviar(prompt)
        _pausa(self.rng, 0.5, 1.2)
        return self.esperar_resposta(timeout)


def abrir_cliente(provedor: str, *, headless: bool = False,
                  ajustes: dict | None = None, log=print):
    """Contexto: `with abrir_cliente('chatgpt') as cliente:`."""
    from contextlib import contextmanager

    @contextmanager
    def _abrir():
        browser = _rb_identity_browser
        travas = _rb_travas
        nome_trava = travas.do_perfil(provedor, "geral")
        with travas.trava(nome_trava, esperar=10.0) as minha:
            if not minha:
                raise LLMFalhou(
                    f"a conta do {provedor} ({nome_trava}) esta em uso por "
                    "outra geracao agora. Espere ela terminar, ou cadastre "
                    "outra conta na pagina Contas para rodar em paralelo.")
            with browser.contexto_persistente(headless=headless,
                                              profile=perfil_de(provedor)) as ctx:
                page = browser.pagina(ctx)
                yield ClienteLLM(provedor, ctx, page, ajustes, log=log)

    return _abrir()
