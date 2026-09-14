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
import re
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
        self.modelo_atual = ""
        # Comeca em False de proposito: enquanto ninguem confirmou o modelo
        # forte, a resposta honesta e "nao sei", e nao "esta tudo certo".
        self.modelo_confirmado = False

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
        self.modelo_atual = self.escolher_modelo()
        self.log(f"[{self.provedor}] chat novo aberto.")

    # ------------------------------------------------------------- modelo
    TENTATIVAS_DE_MODELO = 3

    def escolher_modelo(self, preferido=None) -> str:
        """Poe o chat no modelo mais forte que a conta tiver.

        POR QUE ISTO EXISTE: a URL nao carrega modelo nenhum — ela abre com o
        que estiver marcado na conta. Descoberto em 08/09/2026: estava em
        "3.6 Flash", o rapido, e as historias 3 a 10 inteiras sairam dele.
        Escrever historia e trabalho de raciocinio; deixar isso na sorte do
        que ficou selecionado da ultima vez e deixar a qualidade na sorte.

        TENTA DE NOVO ANTES DE DESISTIR. Em 09/09/2026 as 22:59 a troca deu
        `TimeoutError` na primeira tentativa e a `historia_00004` inteira saiu
        no Flash-Lite: respostas em 14 s no lugar de 42, partes com 200
        palavras no lugar de 400, e 84 imagens mais seis renders gastos em
        cima de um texto do modelo fraco. A pagina estava so terminando de
        hidratar — na segunda tentativa ela responde.

        Nunca levanta: um seletor que mudou nao pode impedir a geracao. Mas
        agora ela deixa RASTRO — `self.modelo_confirmado` diz se o alvo foi
        mesmo alcancado, e quem grava o roteiro registra isso em vez de
        gravar vazio.
        """
        self.modelo_confirmado = False
        ordem = preferido or self.sel.get("modelo_preferido")
        if not ordem or not self.sel.get("modelo_botao"):
            return ""
        ultimo = ""
        for volta in range(1, self.TENTATIVAS_DE_MODELO + 1):
            nome, confirmado = self._tentar_modelo(ordem)
            if confirmado:
                self.modelo_confirmado = True
                return nome
            ultimo = nome or ultimo
            if volta < self.TENTATIVAS_DE_MODELO:
                self.log(f"[{self.provedor}] a troca de modelo nao pegou "
                         f"(tentativa {volta}/{self.TENTATIVAS_DE_MODELO}); "
                         "esperando a pagina e tentando de novo.")
                time.sleep(2.5 * volta)
        self.log(f"[{self.provedor}] ATENCAO: nao consegui por no modelo "
                 f"forte depois de {self.TENTATIVAS_DE_MODELO} tentativas; "
                 f"a historia vai sair em {ultimo or 'modelo desconhecido'}.")
        return ultimo

    def _tentar_modelo(self, ordem) -> tuple:
        """(nome do modelo em uso, alcancou o alvo?). Nunca levanta."""
        try:
            botao = sel.encontrar(self.page, self.sel["modelo_botao"],
                                  timeout=6.0)
            if botao is None:
                self.log(f"[{self.provedor}] nao achei o seletor de modelo.")
                return "", False
            atual = (botao.inner_text(timeout=3000) or "").strip()
            if any(a.lower() in atual.lower() for a in ordem[:1]):
                self.log(f"[{self.provedor}] modelo: {atual} (ja era o alvo).")
                return atual, True
            botao.click(timeout=8000)
            _pausa(self.rng, 0.8, 1.4)
            opcoes = None
            for seletor in self.sel["modelo_opcao"]:
                achado = self.page.locator(seletor)
                if achado.count():
                    opcoes = achado
                    break
            if opcoes is None:
                self.log(f"[{self.provedor}] o menu de modelo nao abriu.")
                self.page.keyboard.press("Escape")
                return atual, False
            # Procura na ORDEM da preferencia: o primeiro alvo que existir
            # ganha, e "pro" antes de "flash" e o que faz o forte vencer.
            for alvo in ordem:
                for i in range(opcoes.count()):
                    texto = (opcoes.nth(i).inner_text(timeout=1500) or "")
                    if alvo.lower() in texto.lower():
                        opcoes.nth(i).click(timeout=8000)
                        _pausa(self.rng, 1.0, 1.8)
                        nome = " ".join(texto.split())[:40]
                        self.log(f"[{self.provedor}] modelo: {atual} -> {nome}")
                        return nome, True
            self.page.keyboard.press("Escape")
            # A conta nao TEM o modelo forte: tentar de novo nao muda isso.
            self.log(f"[{self.provedor}] nenhum modelo de {ordem} nesta conta; "
                     f"fico em {atual!r}.")
            return atual, True
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[{self.provedor}] a troca de modelo falhou "
                     f"({type(exc).__name__}).")
            return "", False

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
        botao de parar (que so existe enquanto o modelo escreve).

        O CONSENTIMENTO ENTRA AQUI, e nao ao anexar. Descoberto olhando a
        tela em 11/09/2026: com video anexado, o Gemini so abre o dialogo de
        direitos DEPOIS do clique em enviar. A mensagem fica pendurada
        esperando o "Concordo", o campo continua com o texto, e daqui de
        dentro isso e indistinguivel de um envio que nao pegou — foram
        quatro tentativas morrendo em "cliquei em enviar mas nada mudou".

        Aceitar aqui cobre qualquer envio, com anexo ou sem: o dialogo so
        existe quando ha video, e procurar por ele custa uma consulta de
        seletor por volta do laco.
        """
        fim = time.monotonic() + espera
        while time.monotonic() < fim:
            if sel.encontrar(self.page, self.sel["parar"], timeout=0.4) is not None:
                return True
            if len(self._texto_do_campo(campo).strip()) < 5:
                return True
            self._aceitar_consentimento(espera=0.3)
            time.sleep(0.4)
        return False

    # ------------------------------------------------------------ resposta
    def _resposta_atual(self) -> str:
        """O texto do ULTIMO turno do assistente."""
        try:
            # Scroll para o fim da pagina garante que a nova resposta
            # foi renderizada no DOM, evitando pegar a resposta anterior
            # em chats com multiplos turnos (gemini-resposta-anterior-multiplasturnos).
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass  # Se nao conseguir fazer scroll, tenta mesmo assim

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

    def _responder_agora(self) -> bool:
        """Clica em "Responder agora" se a tela oferecer. True se clicou.

        Nunca levanta: sem o botao (ou num provedor sem ele) a espera segue
        como sempre foi.
        """
        candidatos = self.sel.get("responder_agora") or []
        if not candidatos:
            return False
        try:
            botao = sel.encontrar(self.page, candidatos, timeout=0.3)
            if botao is None:
                return False
            botao.click(timeout=5000)
        except Exception:                                      # noqa: BLE001
            return False
        self.log(f"[{self.provedor}] raciocinio sem fim; cliquei em "
                 "'Responder agora'.")
        return True

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
        # Quanto o modelo pode pensar calado antes de ouvir "responda agora".
        # 300 s, e nao 120: escrevendo historia o Pro leva 120-132 s por parte
        # e pensa calado quase tudo isso (medido em 14/09/2026, 8:16-8:20), e
        # as 8:22 o clique a 120 s cortou o raciocinio de uma parte saudavel.
        # O raciocinio preso de verdade passava de 600 s.
        pensar_ate = float(self.ajustes.get("pensar_ate", 300))
        apressado = False

        while time.monotonic() < fim:
            texto = self._resposta_atual()
            # "Sem texto" e MENOS DE 40 caracteres, e nao vazio: as 7:29 de
            # 14/09/2026 a pagina mostrou 10 chars (o rotulo do raciocinio)
            # por minutos, o clique nunca veio e a revisao gastou 900 s.
            if (not apressado and len(texto.strip()) < 40
                    and time.monotonic() - inicio >= pensar_ate):
                apressado = self._responder_agora()
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
            "na tela. Pode ser raciocinio preso (o botao 'Responder agora' "
            "nao apareceu ou nao clicou) ou limite de uso da conta.")

    # ------------------------------------------------------------- anexo
    def anexar(self, caminhos, espera: float = 120.0) -> int:
        """Anexa arquivos ao proximo prompt. Devolve quantos entraram.

        Mesma doutrina do envio: nada e dado como feito sem prova na tela.
        `set_input_files` retorna na hora, mas o arquivo ainda esta subindo —
        mandar o prompt nesse instante faz o modelo responder sobre uma
        imagem que ele nao recebeu, e a resposta parece plausivel. A prova e
        a miniatura (o botao "Remover") aparecer, uma por arquivo.
        """
        arquivos = [Path(c) for c in (caminhos or [])]
        faltando = [c for c in arquivos if not c.is_file()]
        if faltando:
            raise LLMFalhou(
                "estes arquivos nao existem: "
                + ", ".join(str(c) for c in faltando[:4]))
        if not arquivos:
            return 0

        antes = self._provas_de_anexo()
        campo = sel.encontrar_oculto(self.page, self.sel["anexo_input"],
                                     timeout=3.0)
        if campo is None:
            # Alguns temas so criam o input depois de abrir o menu do clipe.
            botao = sel.encontrar(self.page, self.sel["anexo_botao"],
                                  timeout=5.0)
            if botao is not None:
                try:
                    botao.click(timeout=8000)
                except Exception:                              # noqa: BLE001
                    pass
                _pausa(self.rng, 0.4, 0.9)
            campo = sel.encontrar_oculto(self.page, self.sel["anexo_input"],
                                         timeout=8.0)
        if campo is None:
            raise LLMFalhou(
                f"nao achei onde anexar arquivo no {self.provedor}.\n"
                f"Rode: python main.py llm probe --provedor {self.provedor} "
                "e confira `anexo_input` em contos/llm/seletores.py.")

        campo.set_input_files([str(c) for c in arquivos])
        alvo = antes + len(arquivos)
        fim = time.monotonic() + float(espera)
        while time.monotonic() < fim:
            agora = self._provas_de_anexo()
            if agora >= alvo:
                self.log(f"[{self.provedor}] {len(arquivos)} anexo(s) "
                         "confirmado(s) na tela.")
                return len(arquivos)
            time.sleep(0.6)

        agora = self._provas_de_anexo()
        if agora > antes:
            self.log(f"[{self.provedor}] so {agora - antes} de "
                     f"{len(arquivos)} anexos apareceram em {espera:.0f}s; "
                     "sigo com o que subiu.")
            return agora - antes
        raise LLMFalhou(
            f"anexei {len(arquivos)} arquivo(s) mas nenhuma miniatura apareceu "
            f"em {espera:.0f}s. Pode ser arquivo grande demais para a conta, "
            "ou o site mudou a tela de anexo.")

    def anexar_video(self, caminho, espera: float = 900.0) -> str:
        """Sobe um VIDEO e so volta quando ele esta pronto para a pergunta.

        Video nao e anexo grande: e outro fluxo. Duas coisas o separam, e
        ignorar qualquer uma delas faz o envio falhar em silencio — medido em
        11/09/2026, tres tentativas seguidas morreram em "cliquei em enviar
        mas nada mudou na tela":

        1. CONSENTIMENTO. O Gemini abre um dialogo MODAL ("Confira se voce tem
           os direitos sobre os conteudos que enviar"). Enquanto ele esta
           aberto o botao de enviar existe, reporta `disabled: false` e o
           clique nao faz nada.
        2. A DURACAO E A PROVA, nao a miniatura. A miniatura sai em ~10 s; a
           duracao (`1:47`) aparece em ~30 s, e e ela que diz que o arquivo
           chegou inteiro. Perguntar entre uma e outra faz o modelo responder
           sobre um video que ele nao recebeu — e a resposta parece boa.

        Devolve a duracao lida na tela.
        """
        alvo = Path(caminho)
        if not alvo.is_file():
            raise LLMFalhou(f"o video nao existe: {alvo}")

        campo = sel.encontrar_oculto(self.page, self.sel["anexo_input"],
                                     timeout=3.0)
        if campo is None:
            botao = sel.encontrar(self.page, self.sel["anexo_botao"],
                                  timeout=8.0)
            if botao is not None:
                try:
                    botao.click(timeout=8000)
                except Exception:                              # noqa: BLE001
                    pass
                _pausa(self.rng, 0.4, 0.9)
            campo = sel.encontrar_oculto(self.page, self.sel["anexo_input"],
                                         timeout=8.0)
        if campo is None:
            raise LLMFalhou(
                f"nao achei onde anexar video no {self.provedor}.")
        campo.set_input_files(str(alvo))
        self.log(f"[{self.provedor}] {alvo.name} entregue "
                 f"({alvo.stat().st_size // (1024 * 1024)} MB).")

        # NAO aceita consentimento aqui: ele so aparece depois do ENVIO.
        # Quem trata e `_confirmou_envio`.
        return self._esperar_duracao(espera)

    def _aceitar_consentimento(self, espera: float = 25.0) -> bool:
        """Fecha o aviso de direitos. Best-effort: em algumas contas ele nao
        aparece, e nao aparecer nao e erro."""
        botao = sel.encontrar(self.page,
                              self.sel.get("consentimento_video") or [],
                              timeout=espera)
        if botao is None:
            return False
        try:
            botao.click(timeout=8000)
        except Exception:                                      # noqa: BLE001
            return False
        self.log(f"[{self.provedor}] aviso de direitos aceito.")
        _pausa(self.rng, 0.5, 1.0)
        return True

    def _esperar_duracao(self, espera: float) -> str:
        padrao = re.compile(r"^\d+:\d{2}$")
        fim = time.monotonic() + float(espera)
        while time.monotonic() < fim:
            for seletor in self.sel.get("anexo_duracao") or []:
                try:
                    textos = self.page.locator(seletor).all_text_contents()
                except Exception:                              # noqa: BLE001
                    continue
                for texto in textos:
                    limpo = str(texto).strip()
                    if padrao.match(limpo):
                        self.log(f"[{self.provedor}] video pronto ({limpo}).")
                        return limpo
            time.sleep(3.0)
        raise LLMFalhou(
            f"o video nao terminou de subir em {espera / 60:.0f} min "
            "(a duracao nunca apareceu ao lado do nome do arquivo).")

    def _provas_de_anexo(self) -> int:
        """Quantas miniaturas de anexo estao na tela agora."""
        total = 0
        for seletor in self.sel.get("anexo_prova") or []:
            try:
                total = max(total, self.page.locator(seletor).count())
            except Exception:                                  # noqa: BLE001
                continue
        return total

    def perguntar(self, prompt: str, timeout: float | None = None,
                  anexos=None) -> str:
        """Um turno completo: anexa (se houver), envia, espera, devolve."""
        if anexos:
            self.anexar(anexos)
            _pausa(self.rng, 0.4, 1.0)
        self.enviar(prompt)
        _pausa(self.rng, 0.5, 1.2)
        return self.esperar_resposta(timeout)


class ContaOcupada(LLMFalhou):
    """A conta esta com outro processo. E diferente de "deu erro": quem
    chama pode tentar OUTRO provedor em vez de desistir do turno."""


def abrir_cliente(provedor: str, *, headless: bool = False,
                  ajustes: dict | None = None, esperar: float = 10.0,
                  log=print):
    """Contexto: `with abrir_cliente('chatgpt') as cliente:`.

    `esperar` e quanto se espera pela conta. O padrao curto serve a quem tem
    o dia inteiro (a geracao); quem tem hora marcada, como o parecer antes de
    publicar, passa um valor maior — mas nao adianta esperar muito: a geracao
    segura a conta pela historia INTEIRA, que leva horas. Contra isso o que
    funciona e trocar de provedor, nao ter paciencia.
    """
    from contextlib import contextmanager

    @contextmanager
    def _abrir():
        browser = _rb_identity_browser
        travas = _rb_travas
        nome_trava = travas.do_perfil(provedor, "geral")
        with travas.trava(nome_trava, esperar=float(esperar)) as minha:
            if not minha:
                raise ContaOcupada(
                    f"a conta do {provedor} ({nome_trava}) esta em uso por "
                    "outra geracao agora. Espere ela terminar, ou cadastre "
                    "outra conta na pagina Contas para rodar em paralelo.")
            with browser.contexto_persistente(headless=headless,
                                              profile=perfil_de(provedor)) as ctx:
                page = browser.pagina(ctx)
                yield ClienteLLM(provedor, ctx, page, ajustes, log=log)

    return _abrir()
