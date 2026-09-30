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
import builds.atividade as _rb_atividade
import builds.contas as _rb_contas
import builds.travas as _rb_travas

from . import seletores as sel

RAIZ = Path(__file__).resolve().parents[2]
PERFIS = RAIZ / ".browser_profile"
# A partir de quantas falhas SEGUIDAS do mesmo provedor o diario ganha um
# erro (e o Telegram, um alerta). So a de numero exato: as seguintes voltam
# a ser aviso, para um login caido nao virar um alerta por rodada.
FALHAS_PARA_ERRO = 3
# Onde fica a tela da pagina que nao montou (`ClienteLLM.conferir_sessao`).
PASTA_EM_BRANCO = RAIZ / "outputs" / "_logs" / "llm_em_branco"


class LLMFalhou(RuntimeError):
    """Erro humano: o que se tentou, e o que fazer."""


class NaoLogado(LLMFalhou):
    """A sessao daquele perfil caiu (ou nunca existiu)."""


class EnvioTruncado(LLMFalhou):
    """So um PEDACO do prompt virou mensagem; o resto ficou na caixa.

    Visto em 15/09/2026 as 16:23, escrevendo a parte 6 da historia 14: na
    conversa havia um balao nosso com uma linha so ("ETAPA 2 - escreva agora a
    PARTE 6 de 6, e SO ela.") e a caixa de texto continuava com o resto do
    prompt e o botao Enviar aceso. Como existe turno do usuario na tela,
    `_envio_devolvido` nao pega este caso, e a espera gastou os 600 s inteiros
    para so entao falhar a rodada.

    E diferente de "nao foi recebida": quem chama pode REENVIAR, porque
    `enviar` limpa a caixa antes de colar.
    """


class SiteIndisponivel(LLMFalhou):
    """O SITE pos um aviso NO LUGAR da resposta ao nosso turno.

    29/09/2026, 17:30 e 17:44, dois pedidos de imagem ao Grok pelo carteiro
    da Vila: no lugar da resposta veio o card "Alta procura — Por favor, tente
    novamente em breve, ou atualize para um acesso com maior prioridade" (com
    o botao "Aprimorar", que NUNCA se clica: e o plano pago) e, no topo, o
    aviso "Grok is experiencing issues". A espera nao reconhecia o card e
    gastou os 420 s inteiros, duas vezes (outputs/carteiro.txt; tela em
    historias/outputs/_logs/llm_calado/grok_20260929_174936.png).

    Nao e recusa nem cota da conta: e a fila da conta gratis em hora de pico.
    Reenviar na hora nao adianta, entao quem chama nao reenvia; o carteiro
    marca `indisponivel` e o rodizio de imagens tira a IA por `cota_pausa_h`
    (`pausa_rodizio`).
    """

    categoria = "indisponivel"
    pausa_rodizio = True


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
        self._ultimo_prompt = ""
        self._ultima_resposta = ""
        # O DIARIO (atividade.jsonl) so e escrito por cliente aberto de
        # verdade (`abrir_cliente`): cliente montado em teste nao pode sujar
        # o diario de producao.
        self.diario = False
        self.papel, self.ref, self.canal = "", "", "historias"
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
        self.conferir_sessao()
        self.turnos = 0
        self._ultima_resposta = ""
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
        if self.sel.get("modelo_fixo"):
            # Site sem menu de modelo (DeepSeek): o que se escolhe e so o
            # raciocinio, e ele entra no nome para o roteiro dizer qual foi.
            pensa = self._ajustar_raciocinio()
            self.modelo_confirmado = pensa is not None
            nome = str(self.sel["modelo_fixo"])
            if pensa == self.RACIOCINIO_DA_CONTA:
                return nome + " (DeepThink como a conta estiver)"
            return nome + (" + DeepThink" if pensa else "")
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

    RACIOCINIO_DA_CONTA = "como_a_conta"

    def _ajustar_raciocinio(self):
        """Poe o DeepThink no estado do config. True/False, None se nao deu
        para saber, ou `RACIOCINIO_DA_CONTA` quando o config manda nao mexer
        (`"deepthink": null`). Nunca levanta.

        O estado so e lido de atributo (`aria-pressed`, classe "active" ou
        "selected"). Sem nenhum dos dois, NAO se clica: um clique no escuro
        pode ligar o que devia estar desligado.
        """
        try:
            from . import papeis
            querido = papeis.ajustes(self.provedor).get("deepthink")
        except Exception:                                      # noqa: BLE001
            querido = None
        if querido is None:
            return self.RACIOCINIO_DA_CONTA
        querido = bool(querido)
        candidatos = self.sel.get("deepthink_botao") or []
        if not candidatos:
            return None
        try:
            botao = sel.encontrar(self.page, candidatos, timeout=6.0)
            if botao is None:
                self.log(f"[{self.provedor}] nao achei o botao do DeepThink.")
                return None
            estado = botao.evaluate(
                "el => { const p = el.getAttribute('aria-pressed');"
                " if (p === 'true') return true; if (p === 'false') return false;"
                " const c = String(el.className || '').toLowerCase();"
                " if (/active|selected|checked/.test(c)) return true;"
                " return null; }")
            if estado is None:
                self.log(f"[{self.provedor}] nao sei se o DeepThink esta "
                         "ligado; deixo como esta.")
                return None
            if bool(estado) != querido:
                botao.click(timeout=5000)
                _pausa(self.rng, 0.5, 1.0)
                self.log(f"[{self.provedor}] DeepThink "
                         f"{'ligado' if querido else 'desligado'}.")
            return querido
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[{self.provedor}] o ajuste do DeepThink falhou "
                     f"({type(exc).__name__}).")
            return None

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

    # A PAGINA QUE NAO MONTOU NAO E LOGIN CAIDO (30/09/2026). 09:16, so
    # leitura: o grok.com abriu EM BRANCO no perfil `grok__principal` (titulo
    # "Grok", nada na tela, o app nao montou em 45 s, nenhum HTTP >= 400). O
    # `logado()` de antes respondia True para isso ("nao vi a tela de login"):
    # a abertura dizia "chat novo aberto" e o envio morria depois com "o site
    # provavelmente mudou". A resposta certa e "nao consegui olhar" — `None`
    # nunca vira `False` (probe.sessao_valida, 09/09), e tambem nao vira True.
    TEXTO_EM_BRANCO = 80

    def estado_da_pagina(self) -> str:
        """O que a pagina aberta mostra, sem clicar em nada. Nunca levanta.

        "logado"    o campo de quem esta logado (`logado`) esta na tela;
        "deslogado" a tela de login (`login`) esta na tela — a UNICA prova que
                    vira `NaoLogado`;
        "barrado"   o desafio anti-bot no titulo ("Um momento…", `probe.BARRADO`);
        "em_branco" nem campo nem login, e menos de `TEXTO_EM_BRANCO`
                    caracteres visiveis: o app nao montou;
        "nao_sei"   ha conteudo, mas nao o que eu conheco (ou a pagina nao
                    respondeu): segue como sempre seguiu — se o site mudou, o
                    envio diz qual seletor faltou.
        """
        self._pagina_vista = ("", 0)
        if sel.encontrar(self.page, self.sel["logado"], timeout=6.0) is not None:
            return "logado"
        if sel.encontrar(self.page, self.sel["login"], timeout=1.0) is not None:
            return "deslogado"
        if sel.encontrar(self.page, self.sel["campo"], timeout=1.0) is not None:
            return "nao_sei"
        try:
            titulo = " ".join(str(self.page.title() or "").split())
            texto = " ".join(str(self.page.evaluate(
                "() => (document.body && document.body.innerText) || ''") or "").split())
        except Exception:                                      # noqa: BLE001
            return "nao_sei"
        self._pagina_vista = (titulo, len(texto))
        from .probe import BARRADO
        if any(marca in titulo.lower() for marca in BARRADO):
            return "barrado"
        if len(texto) < self.TEXTO_EM_BRANCO:
            return "em_branco"
        return "nao_sei"

    def conferir_sessao(self) -> str:
        """Depois de `_esperar_montar`: `NaoLogado` SO com a tela de login na
        frente; `SiteIndisponivel` (pausa o rodizio, como o "Alta procura")
        para a pagina que nao montou ou o desafio anti-bot, com a tela salva
        em `PASTA_EM_BRANCO`. Devolve o estado."""
        estado = self.estado_da_pagina()
        if estado == "deslogado":
            raise NaoLogado(
                f"a sessao do {self.provedor} nao esta valida neste perfil (a tela "
                "de login esta na frente).\n"
                f"Rode uma vez: python main.py llm login --provedor {self.provedor} "
                "(a janela abre, voce entra na conta, e o login fica salvo).")
        if estado in ("em_branco", "barrado"):
            titulo, chars = getattr(self, "_pagina_vista", ("", 0))
            if estado == "barrado":
                oque = (f"o {self.provedor} parou no desafio anti-bot "
                        f"(título {titulo!r})")
            else:
                espera = float(self.ajustes.get("hydration_timeout", 45))
                oque = (f"o {self.provedor} não montou a página em {espera:.0f} s "
                        f"(título {titulo!r}, {chars} caracteres visíveis)")
            tela = self._salvar_tela(PASTA_EM_BRANCO)
            self.log(f"[{self.provedor}] {oque}; não é o login"
                     + (f" (tela em {tela})" if tela else "") + ".")
            raise SiteIndisponivel(
                f"{oque}: o site não carregou — não é o login; não reabro agora."
                + (f" Tela em _logs/{tela.parent.name}/{tela.name}." if tela else ""))
        if estado == "nao_sei":
            self.log(f"[{self.provedor}] não reconheço a página (sem o campo de quem "
                     "está logado e sem a tela de login); sigo — se o site mudou, "
                     "o envio diz o que faltou.")
        return estado

    def _salvar_tela(self, pasta):
        """A captura do proprio navegador (a do Windows devolve quadro velho
        com o monitor apagado). O caminho, ou None. Nunca levanta."""
        try:
            pasta = Path(pasta)
            pasta.mkdir(parents=True, exist_ok=True)
            destino = pasta / f"{self.provedor}_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.page.screenshot(path=str(destino))
            return destino
        except Exception:                                      # noqa: BLE001
            return None

    def logado(self) -> bool:
        """Compatibilidade: False SO com a tela de login na frente. Para
        decidir a abertura use `conferir_sessao` — a pagina em branco nao e
        login caido, e tambem nao e "logado"."""
        return self.estado_da_pagina() != "deslogado"

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
        # a foto das imagens da pagina ANTES do envio: a imagem da resposta
        # tem de ser nova (d228c94f, 29/09/2026). `None` = sem foto.
        self._srcs_antes_do_envio = (self._foto_das_imagens()
                                     if self.olha_imagem() else None)
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
        self._ultimo_prompt = prompt
        self.turnos += 1

    def _envio_devolvido(self) -> bool:
        """A pergunta VOLTOU para a caixa de texto, sem resposta comecando?

        Visto na tela em 14/09/2026 (18:21, `_logs/llm_calado/`): depois do
        upload do video o Gemini voltou para "E ai, Adrian, qual o plano?" com
        o nosso prompt inteiro de novo na caixa e sem o anexo. A confirmacao do
        envio tinha passado (o campo esvaziou por um instante), e a espera ficou
        900 s olhando uma resposta que nunca ia comecar — era isso o "raciocinio
        preso" das revisoes de video. Nunca levanta.
        """
        prompt = " ".join(str(getattr(self, "_ultimo_prompt", "") or "").split())
        if len(prompt) < 40:
            return False
        # SO SEM CONVERSA NA TELA. A primeira versao olhava so a caixa e deu
        # falso positivo as 18:56: a pergunta tinha entrado ("Voce disse", o
        # video 1:15, o Gemini "Analisando"), e mesmo assim a espera desistiu
        # em 20 s e jogou a revisao para o ChatGPT. Devolvido de verdade e a
        # pagina de inicio: nenhuma mensagem nossa na conversa.
        try:
            if sel.encontrar_oculto(self.page, self.sel.get("turno_usuario")
                                    or [], timeout=0.2) is not None:
                return False
        except Exception:                                      # noqa: BLE001
            return False
        try:
            campo = sel.encontrar(self.page, self.sel["campo"], timeout=0.3)
            if campo is None:
                return False
            na_caixa = " ".join(self._texto_do_campo(campo).split())
        except Exception:                                      # noqa: BLE001
            return False
        return prompt[:40] in na_caixa or prompt[-40:] in na_caixa

    def _texto_do_turno_usuario(self) -> str:
        """O texto do ULTIMO turno do usuario na conversa."""
        for seletor in self.sel.get("turno_usuario") or []:
            try:
                alvos = self.page.locator(seletor)
                total = alvos.count()
            except Exception:                                  # noqa: BLE001
                continue
            if total:
                try:
                    return alvos.nth(total - 1).inner_text() or ""
                except Exception:                              # noqa: BLE001
                    continue
        return ""

    def _envio_truncado(self) -> bool:
        """Foi so um PEDACO do prompt, e o fim dele continua na caixa?

        A diferenca para `_envio_devolvido` e o balao na conversa: la nao ha
        nenhum (a pagina voltou ao inicio), aqui ha um com um pedaco do
        prompt. E a diferenca para o caso saudavel de 14/09 as 18:56 — prompt
        inteiro na conversa, Gemini "Analisando" — e o TAMANHO do que foi
        enviado: ali o balao tinha o prompt todo, aqui tem uma linha.

        Nunca levanta: e checagem de tela dentro da espera.
        """
        prompt = " ".join(str(getattr(self, "_ultimo_prompt", "") or "").split())
        if len(prompt) < 200:
            return False
        turno = " ".join(self._texto_do_turno_usuario().split())
        if not turno:
            return False        # sem balao nenhum e caso do `_envio_devolvido`
        try:
            campo = sel.encontrar(self.page, self.sel["campo"], timeout=0.3)
            if campo is None:
                return False
            na_caixa = " ".join(self._texto_do_campo(campo).split())
        except Exception:                                      # noqa: BLE001
            return False
        fim = prompt[-40:]
        return (fim in na_caixa and fim not in turno
                and len(turno) < 0.6 * len(prompt))

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

        self._ancorado = False
        if self.sel.get("raciocinio") or self.sel.get("turno_usuario"):
            achado = self._resposta_no_dom()
            if achado is not None:
                self._ancorado = bool(achado.get("ancorado"))
                return str(achado.get("texto") or "")
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

    # A RESPOSTA E A QUE VEM DEPOIS DA NOSSA PERGUNTA. `ancorado` diz que o
    # ultimo turno do usuario foi achado na pagina e que o texto devolvido
    # esta DEPOIS dele na ordem do documento — prova de que e deste turno,
    # mesmo que o texto seja identico ao anterior (revisao "ja esta boa").
    _JS_RESPOSTA = (
        "([respostas, pensamentos, usuarios]) => {"
        " const dentro = el => pensamentos.some(s => {"
        "   try { return !!el.closest(s); } catch (e) { return false; } });"
        " const depois = (a, b) => !!(a.compareDocumentPosition(b)"
        "   & Node.DOCUMENT_POSITION_FOLLOWING);"
        " let usuario = null;"
        " for (const s of usuarios) {"
        "   let els = [];"
        "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
        "   const ultimo = els[els.length - 1];"
        "   if (ultimo && (!usuario || depois(usuario, ultimo))) usuario = ultimo;"
        " }"
        " for (const s of respostas) {"
        "   let achados = [];"
        "   try { achados = [...document.querySelectorAll(s)]; }"
        "   catch (e) { continue; }"
        "   achados = achados.filter(el => !dentro(el));"
        "   if (!achados.length) continue;"
        "   if (usuario) {"
        "     const novos = achados.filter(el => depois(usuario, el));"
        "     return {texto: novos.length"
        "       ? (novos[novos.length - 1].innerText || '') : '',"
        "       ancorado: true};"
        "   }"
        "   return {texto: achados[achados.length - 1].innerText || '',"
        "           ancorado: false};"
        " }"
        " return {texto: '', ancorado: !!usuario}; }")

    # A RESPOSTA PODE SER UMA IMAGEM (29/09/2026). As 14:24 o Adrian pediu pelo
    # app "gere uma imagem de um gato" ao Gemini; o Gemini desenhou, a tela
    # ficou com 0 caracteres de texto, e a espera gastou os 420 s inteiros e
    # disse "raciocinio preso ou limite".
    #
    # "DEPOIS DO NOSSO TURNO" NAO BASTA (29/09/2026, 16:02, correio
    # d228c94f). "Crie um gato" ao ChatGPT voltou como "imagem pronta" com a
    # foto de uma MESA DE SOM: era a miniatura (512x512, images.openai.com/
    # static-rsc) de um ANUNCIO ("CAVN AI · AI Music Videos · Anuncio") que o
    # ChatGPT poe embaixo da resposta — dentro do MESMO section[data-turn=
    # assistant] do gato (medido na tela, scratchpad/diag_chatgpt_baixar.py).
    # O gato (1254x1254, backend-api/estuary) estava la e foi ignorado.
    # Agora so vale imagem que esta:
    #  - no turno do assistente que RESPONDE ao nosso (`imagem_turno`: o
    #    primeiro depois do ultimo turno do usuario);
    #  - dentro de um recipiente de imagem GERADA (`imagem_gerada`: no
    #    ChatGPT o div#image-<uuid> "imagegen-image", no Gemini o
    #    generated-image) — anuncio, sugestao e anexo nunca estao la;
    #  - com src que NAO existia na pagina antes do envio (`enviar` tira a
    #    foto) — e so quando a geracao acabou (sem borrao, sem "Criando
    #    imagem", sem botao de parar, estavel; ver `esperar_resposta`).
    # IA sem os dois seletores nao tem imagem na resposta (falha fechada).
    _JS_IMAGENS = (
        "([usuarios, turnos, recipientes, gerando]) => {"
        " const depois = (a, b) => !!(a.compareDocumentPosition(b)"
        "   & Node.DOCUMENT_POSITION_FOLLOWING);"
        " const todos = (raiz, lista) => { let out = [];"
        "   for (const s of lista) {"
        "     try { if (raiz !== document && raiz.matches(s)) out.push(raiz); } catch (e) {}"
        "     try { out = out.concat([...raiz.querySelectorAll(s)]); } catch (e) {} }"
        "   return out; };"
        " let usuario = null;"
        " for (const s of usuarios) {"
        "   let els = [];"
        "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
        "   const ultimo = els[els.length - 1];"
        "   if (ultimo && (!usuario || depois(usuario, ultimo))) usuario = ultimo;"
        " }"
        " if (!usuario) return {ancorado: false, turno: '', resposta: false,"
        "   gerando: false, imagens: [], fora: 0};"
        " let resposta = null;"
        " for (const t of todos(document, turnos)) {"
        "   if (!depois(usuario, t) || t.contains(usuario) || usuario.contains(t)) continue;"
        "   if (!resposta || depois(t, resposta)) resposta = t;"
        " }"
        " const porSrc = new Map();"
        " if (resposta) {"
        "   for (const cx of todos(resposta, recipientes)) {"
        "     for (const im of cx.querySelectorAll('img')) {"
        "       const src = im.currentSrc || im.src || '';"
        "       if (!src || usuario.contains(im)) continue;"
        "       let borrada = false;"
        "       for (let e = im; e && e !== cx.parentElement; e = e.parentElement) {"
        "         const f = getComputedStyle(e).filter || '';"
        "         if (f.includes('blur')) { borrada = true; break; } }"
        "       const i = {src, src_attr: im.getAttribute('src') || '',"
        "         w: im.naturalWidth || 0, h: im.naturalHeight || 0,"
        "         pronta: !!im.complete && (im.naturalWidth || 0) > 0,"
        "         alt: (im.alt || '').slice(0, 160), borrada};"
        "       const velho = porSrc.get(src);"
        "       if (!velho) { porSrc.set(src, i); continue; }"
        "       velho.borrada = velho.borrada && i.borrada;"
        "       velho.pronta = velho.pronta || i.pronta;"
        "       velho.alt = velho.alt || i.alt;"
        "       velho.w = Math.max(velho.w, i.w); velho.h = Math.max(velho.h, i.h);"
        "     }"
        "   }"
        " }"
        " const imagens = [...porSrc.values()];"
        " const dentro = new Set(imagens.map(i => i.src));"
        " const fora = [...document.querySelectorAll('img')].filter(im =>"
        "   depois(usuario, im) && !usuario.contains(im) && (im.naturalWidth || 0) >= 256"
        "   && !dentro.has(im.currentSrc || im.src || '')).length;"
        " let emGeracao = false;"
        " if (resposta && gerando) {"
        "   try { emGeracao = new RegExp(gerando, 'i').test("
        "     (resposta.innerText || '').slice(0, 3000)); } catch (e) {} }"
        " return {ancorado: true, turno: (usuario.innerText || '').slice(0, 600),"
        "         resposta: !!resposta, gerando: emGeracao, imagens, fora}; }")

    # A FOTO DA PAGINA ANTES DO ENVIO: todo src de imagem que ja existe. A
    # imagem da resposta tem de ser NOVA (nao estar aqui).
    _JS_TODAS_AS_IMAGENS = (
        "() => { const out = [];"
        " for (const im of document.querySelectorAll('img')) {"
        "   if (im.currentSrc) out.push(im.currentSrc);"
        "   const a = im.getAttribute('src'); if (a) out.push(a);"
        "   if (im.src) out.push(im.src); }"
        " return out; }")

    # O texto que a IA mostra ENQUANTO desenha (o ChatGPT: "Criando imagem",
    # com o previa borrada nitidando). Com ele na resposta, a imagem ainda
    # nao e a final.
    GERANDO_IMAGEM_PADRAO = (r"(criando|gerando|creating|generating)\s+"
                             r"(a |uma |sua |your |an )?(imagem|image)")

    def olha_imagem(self) -> bool:
        """Esta IA tem onde procurar imagem na resposta? (os tres seletores)"""
        return bool(self.sel.get("turno_usuario") and self.sel.get("imagem_turno")
                    and self.sel.get("imagem_gerada"))

    def _foto_das_imagens(self) -> set:
        """Os src de TODAS as imagens da pagina agora (nunca levanta)."""
        try:
            achado = self.page.evaluate(self._JS_TODAS_AS_IMAGENS)
        except Exception:                                      # noqa: BLE001
            return set()
        return {str(s) for s in (achado or []) if s} if isinstance(achado, list) else set()

    def imagens_da_resposta(self) -> dict:
        """`{"ancorado", "turno", "resposta", "gerando", "fora", "imagens":
        [{src, src_attr, w, h, pronta, alt, borrada}]}`: as imagens DENTRO da
        resposta ao ultimo turno do usuario, nos recipientes de imagem gerada.
        Nunca levanta (pagina que nao responde = nenhuma imagem)."""
        vazio = {"ancorado": False, "turno": "", "resposta": False, "gerando": False,
                 "imagens": [], "fora": 0}
        if not self.olha_imagem():
            return vazio
        try:
            achado = self.page.evaluate(
                self._JS_IMAGENS, [list(self.sel.get("turno_usuario") or []),
                                   list(self.sel.get("imagem_turno") or []),
                                   list(self.sel.get("imagem_gerada") or []),
                                   str(self.sel.get("imagem_gerando")
                                       or self.GERANDO_IMAGEM_PADRAO)])
        except Exception:                                      # noqa: BLE001
            achado = None
        if not isinstance(achado, dict):
            return vazio
        achado.setdefault("imagens", [])
        return achado

    @staticmethod
    def _estado_da_imagem(achado: dict, prontas: list) -> str:
        """Uma linha do que a espera ve da imagem (vai ao log so quando muda):
        e a medida do que a tela mostrou durante a geracao. Vazio = nada."""
        imagens = (achado or {}).get("imagens") or []
        fora = int((achado or {}).get("fora") or 0)
        # turno so de texto (a pipeline reescrevendo prompt) nao vai ao log
        if not imagens and not fora and not (achado or {}).get("gerando"):
            return ""
        partes = [("resposta ao nosso turno na tela" if achado.get("resposta")
                   else "resposta ao nosso turno ainda nao apareceu")]
        if imagens:
            ultima = imagens[-1]
            partes.append(
                f"{len(imagens)} no recipiente (a ultima {ultima.get('w')}x{ultima.get('h')}"
                + (", borrada" if ultima.get("borrada") else "")
                + ("" if ultima.get("pronta") else ", carregando")
                + (f", alt «{str(ultima.get('alt'))[:40]}»" if ultima.get("alt") else "")
                + ")")
        if prontas:
            partes.append(f"{len(prontas)} final(is) e nova(s)")
        if achado.get("gerando"):
            partes.append("a IA diz que ainda esta gerando")
        if fora:
            partes.append(f"{fora} imagem(ns) grande(s) FORA da resposta ignorada(s) "
                          "(anuncio, sugestao)")
        return "; ".join(partes)

    def imagens_prontas(self, achado: dict, antes=()) -> list:
        """Das imagens da resposta, as que ja sao a FINAL: carregadas, 256+ px,
        sem borrao, com o `alt` de imagem final (quando a IA tem um medido) e
        com src que nao estava na pagina `antes` do envio. Sem a resposta ao
        nosso turno na tela, nenhuma."""
        if not (achado or {}).get("ancorado") or not achado.get("resposta"):
            return []
        antes = set(antes or ())
        finais = [str(a).lower() for a in (self.sel.get("imagem_final_alt") or [])]
        saida = []
        for i in achado.get("imagens") or []:
            src = i.get("src")
            if not src or src in antes or (i.get("src_attr") and i.get("src_attr") in antes):
                continue
            if not i.get("pronta") or i.get("borrada"):
                continue
            if int(i.get("w") or 0) < 256 or int(i.get("h") or 0) < 256:
                continue
            if finais and not any(str(i.get("alt") or "").lower().startswith(f)
                                  for f in finais):
                continue
            saida.append(i)
        return saida

    # O AVISO DO SITE NO LUGAR DA RESPOSTA (29/09/2026; ver `SiteIndisponivel`).
    # O que se le e o turno do assistente que RESPONDE ao nosso (o primeiro
    # depois do ultimo turno do usuario, `turno_assistente`) MENOS o conteudo
    # de resposta de verdade (`resposta`) e o raciocinio (`raciocinio`). O
    # card do Grok nao esta no markdown da resposta: medido pelo log de 29/09,
    # 420 s com "0 chars" lidos pelo seletor de resposta e o card na tela.
    # Assim uma resposta que so CITA "alta procura" no texto nao sobra aqui; e
    # se o DOM mudar e ela sobrar, o teto de `AVISO_MAXIMO` segura (card e
    # curto, resposta nao). `pagina`: o aviso do topo em qualquer lugar da
    # pagina (so vai ao log: ele sozinho nao encerra a espera).
    AVISO_MAXIMO = 400
    _JS_AVISO = (
        "([usuarios, turnos, conteudos, pagina]) => {"
        " const depois = (a, b) => !!(a.compareDocumentPosition(b)"
        "   & Node.DOCUMENT_POSITION_FOLLOWING);"
        " let aviso = false;"
        " if (pagina) { try { aviso = new RegExp(pagina, 'i').test("
        "   (document.body && document.body.innerText) || ''); } catch (e) {} }"
        " let usuario = null;"
        " for (const s of usuarios) {"
        "   let els = [];"
        "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
        "   const ultimo = els[els.length - 1];"
        "   if (ultimo && (!usuario || depois(usuario, ultimo))) usuario = ultimo;"
        " }"
        " if (!usuario) return {ancorado: false, turno: false, resto: '', pagina: aviso};"
        " let turno = null;"
        " for (const s of turnos) {"
        "   let els = [];"
        "   try { els = [...document.querySelectorAll(s)]; } catch (e) { continue; }"
        "   for (const t of els) {"
        "     if (!depois(usuario, t) || t.contains(usuario) || usuario.contains(t)) continue;"
        "     if (!turno || depois(t, turno)) turno = t;"
        "   }"
        " }"
        " if (!turno) return {ancorado: true, turno: false, resto: '', pagina: aviso};"
        " let resto = turno.innerText || '';"
        " for (const s of conteudos) {"
        "   let els = [];"
        "   try { els = [...turno.querySelectorAll(s)]; } catch (e) { continue; }"
        "   for (const el of els) {"
        "     const t = el.innerText || '';"
        "     if (t.trim()) resto = resto.split(t).join(' ');"
        "   }"
        " }"
        " return {ancorado: true, turno: true, resto: resto.slice(0, 4000),"
        "         pagina: aviso}; }")

    def aviso_do_site(self) -> dict:
        """`{"texto", "pagina"}`: `texto` e o aviso que o site pos no lugar da
        resposta ao nosso turno (casado com `indisponivel`, com borda de
        palavra), ou `""`; `pagina` diz se o aviso do topo esta na tela.
        Provedor sem `indisponivel` medido nao olha (e nada muda nele).
        Nunca levanta."""
        vazio = {"texto": "", "pagina": False}
        padroes = [str(p) for p in (self.sel.get("indisponivel") or []) if p]
        turnos = list(self.sel.get("turno_assistente") or [])
        if not padroes or not turnos or not self.sel.get("turno_usuario"):
            return vazio
        conteudos = [s for s in (list(self.sel.get("resposta") or [])
                                 + list(self.sel.get("raciocinio") or []))
                     if s not in turnos]
        try:
            achado = self.page.evaluate(
                self._JS_AVISO, [list(self.sel.get("turno_usuario") or []), turnos,
                                 conteudos, str(self.sel.get("indisponivel_pagina") or "")])
        except Exception:                                      # noqa: BLE001
            return vazio
        if not isinstance(achado, dict):
            return vazio
        pagina = bool(achado.get("pagina"))
        resto = " ".join(str(achado.get("resto") or "").split())
        if not resto or len(resto) > self.AVISO_MAXIMO:
            return {"texto": "", "pagina": pagina}
        for padrao in padroes:
            try:
                if re.search(padrao, resto, re.IGNORECASE):
                    return {"texto": resto, "pagina": pagina}
            except re.error:
                continue
        return {"texto": "", "pagina": pagina}

    def _resposta_no_dom(self):
        """`{"texto", "ancorado"}`, ou `None` se a pagina nao respondeu."""
        try:
            achado = self.page.evaluate(
                self._JS_RESPOSTA,
                [list(self.sel.get("resposta") or []),
                 list(self.sel.get("raciocinio") or []),
                 list(self.sel.get("turno_usuario") or [])])
        except Exception:                                      # noqa: BLE001
            return None
        return achado if isinstance(achado, dict) else None

    def _resposta_nova(self) -> str:
        """A resposta atual, ou `""` se ela ainda e a do turno ANTERIOR.

        17/09/2026, primeira historia pelo DeepSeek: a revisao da parte 1
        "respondeu" 6372 chars em 4 s — o mesmo texto da parte, porque o
        modelo ainda estava no raciocinio e o ultimo bloco de resposta final
        na tela era o do turno anterior, parado e sem botao de parar. Aceito
        assim, todas as respostas seguintes escorregariam um turno (a parte 2
        receberia a revisao da parte 1).

        A PROVA E A POSICAO: so vale o bloco que vem DEPOIS do ultimo turno do
        usuario na pagina (`_ancorado`). Assim uma revisao que devolve o texto
        identico ("a parte ja esta boa") e aceita. A igualdade com o ultimo
        texto devolvido fica so como reserva, para pagina onde o turno do
        usuario nao foi achado.
        """
        texto = self._resposta_atual()
        if getattr(self, "_ancorado", False):
            return texto
        anterior = getattr(self, "_ultima_resposta", "")
        if anterior and " ".join(texto.split()) == " ".join(anterior.split()):
            return ""
        return texto

    def _responder_agora(self) -> bool:
        """Clica em "Responder agora" se a tela oferecer. True se clicou.

        Nunca levanta: sem o botao (ou num provedor sem ele) a espera segue
        como sempre foi.
        """
        candidatos = self.sel.get("responder_agora") or []
        if not candidatos:
            return False
        try:
            # 3.0s em vez de 0.3s: quando o modelo fica pensando de verdade,
            # o botao leva mais tempo para aparecer na UI. Descoberto em
            # 15/09/2026: historia_00014 parte 6 esperou 600s sem tentar
            # clicar novamente porque o timeout era muito curto na primeira
            # tentativa.
            botao = sel.encontrar(self.page, candidatos, timeout=3.0)
            if botao is None:
                return False
            botao.click(timeout=5000)
        except Exception:                                      # noqa: BLE001
            return False
        self.log(f"[{self.provedor}] raciocinio sem fim; cliquei em "
                 "'Responder agora'.")
        return True

    def _diagnosticar_calado(self) -> None:
        """Guarda o que a pagina mostra quando o modelo fica calado SEM botao.

        Em 14/09/2026 as revisoes de video ficaram 900 s com 10 chars na tela
        e nenhum "Responder agora" para clicar — tres vezes. A captura de tela
        do Windows nao serve (com o monitor apagado ela devolve quadro velho);
        a do proprio navegador renderiza a pagina de verdade. Nunca levanta.
        """
        try:
            pasta = RAIZ / "outputs" / "_logs" / "llm_calado"
            pasta.mkdir(parents=True, exist_ok=True)
            destino = pasta / f"{self.provedor}_{time.strftime('%Y%m%d_%H%M%S')}.png"
            self.page.screenshot(path=str(destino))
            textos = self.page.evaluate(
                "() => Array.from(document.querySelectorAll('body *'))"
                ".filter(e => e.offsetParent !== null && e.children.length === 0)"
                ".map(e => (e.innerText || '').trim())"
                ".filter(t => t && t.length < 60)") or []
            self.log(f"[{self.provedor}] calado e sem 'Responder agora': tela "
                     f"em _logs/llm_calado/{destino.name}; visivel: "
                     + " | ".join(textos[-12:])[:400])
        except Exception as exc:                               # noqa: BLE001
            self.log(f"[{self.provedor}] nao consegui registrar a tela "
                     f"({type(exc).__name__}).")

    def esperar_resposta(self, timeout: float | None = None,
                         estabilidade: float = 2.5,
                         desistir_calado: float | None = None) -> str:
        """Espera o modelo TERMINAR e devolve o texto.

        Duas condicoes, e as duas sao necessarias: o botao de parar sumiu
        (o modelo nao esta mais escrevendo) e o texto ficou do mesmo tamanho
        por `estabilidade` segundos. So a primeira falha quando o botao
        pisca entre blocos; so a segunda falha quando o modelo pensa alguns
        segundos antes de escrever.

        `desistir_calado`: com ele, se o modelo passar esse tempo sem escrever
        e sem oferecer "Responder agora", a espera desiste antes do `timeout`.
        So quem tem reserva deve pedir isso (o parecer cai para o ChatGPT); a
        escrita da historia espera o prazo inteiro.
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
        # A partir de quando olhar se a pergunta voltou para a caixa: antes
        # disso o site ainda pode estar limpando o campo do envio.
        devolvido_apos = float(self.ajustes.get("devolvido_apos_s", 20))
        apressado = diagnosticado = False
        # a imagem que a resposta trouxe (quem chama baixa; ver `_JS_IMAGENS`)
        self.imagens_na_resposta = []
        # (assinatura das imagens prontas, desde quando, tamanho do texto)
        imagem_vista = (None, 0.0, -1)
        # A imagem tem de ser NOVA: fora da foto de antes do envio (`enviar`).
        # Sem a foto (quem chamou nao passou por `enviar`), vale o que ja
        # estava na resposta quando a espera comecou. Com ela, NAO: a previa
        # que o ChatGPT ja mostra no primeiro segundo tem o src da final.
        procura_imagem = self.olha_imagem()
        ja_na_tela = set()
        if procura_imagem:
            antes = getattr(self, "_srcs_antes_do_envio", None)
            ja_na_tela = (set(antes) if antes is not None else
                          {i.get("src") for i in
                           self.imagens_da_resposta().get("imagens") or []})
        # a previa do ChatGPT nitida em passos: mais folga que a do texto
        estavel_imagem = max(float(estabilidade),
                             float(self.ajustes.get("imagem_estabilidade", 5.0)))
        ultimo_estado_imagem = None
        # o aviso do site no lugar da resposta (`SiteIndisponivel`): so quem
        # tem os textos medidos olha, e ele tem de aparecer em DUAS voltas
        # seguidas (um quadro no meio da montagem nao encerra a espera)
        olha_aviso = bool(self.sel.get("indisponivel"))
        aviso_seguido = 0
        avisou_pagina = False

        while time.monotonic() < fim:
            texto = self._resposta_nova()
            if olha_aviso:
                aviso = self.aviso_do_site()
                if aviso["texto"]:
                    aviso_seguido += 1
                    if aviso_seguido >= 2:
                        decorrido = time.monotonic() - inicio
                        self.log(f"[{self.provedor}] o site pos um aviso no lugar da "
                                 f"resposta em {decorrido:.0f}s: «{aviso['texto'][:160]}»")
                        if not diagnosticado:
                            diagnosticado = True
                            self._diagnosticar_calado()
                        raise SiteIndisponivel(
                            f"o {self.provedor} respondeu com o aviso do site no lugar da "
                            f"resposta: «{aviso['texto'][:200]}»"
                            + (" (e o aviso no topo: o site diz que está com problemas)"
                               if aviso["pagina"] else "")
                            + "; não reenvio agora.")
                else:
                    aviso_seguido = 0
                    if aviso["pagina"] and not avisou_pagina:
                        avisou_pagina = True
                        self.log(f"[{self.provedor}] o site avisa no topo que está com "
                                 "problemas; sigo esperando a resposta.")
            calado = len(texto.strip()) < 40
            prontas = []
            achado = {}
            if procura_imagem:
                achado = self.imagens_da_resposta()
                prontas = self.imagens_prontas(achado, ja_na_tela)
                estado = self._estado_da_imagem(achado, prontas)
                if estado != ultimo_estado_imagem:
                    ultimo_estado_imagem = estado
                    if estado:
                        self.log(f"[{self.provedor}] imagem: {estado}")
            if prontas:
                assinatura = tuple((i.get("src"), i.get("w"), i.get("h")) for i in prontas)
                if assinatura != imagem_vista[0] or len(texto) != imagem_vista[2]:
                    imagem_vista = (assinatura, time.monotonic(), len(texto))
                elif (time.monotonic() - imagem_vista[1] >= estavel_imagem
                      and not achado.get("gerando")
                      and sel.encontrar(self.page, self.sel["parar"],
                                        timeout=0.3) is None):
                    self.imagens_na_resposta = prontas
                    decorrido = time.monotonic() - inicio
                    self.log(f"[{self.provedor}] resposta com imagem "
                             f"({prontas[-1].get('w')}x{prontas[-1].get('h')}) "
                             f"e {len(texto)} chars em {decorrido:.0f}s")
                    self._ultima_resposta = texto
                    return texto
            # "Sem texto" e MENOS DE 40 caracteres, e nao vazio: as 7:29 de
            # 14/09/2026 a pagina mostrou 10 chars (o rotulo do raciocinio)
            # por minutos, o clique nunca veio e a revisao gastou 900 s.
            if (not apressado and calado
                    and time.monotonic() - inicio >= pensar_ate):
                apressado = self._responder_agora()
                if not apressado and not diagnosticado:
                    diagnosticado = True
                    self._diagnosticar_calado()
            if (desistir_calado and not apressado and calado
                    and time.monotonic() - inicio >= float(desistir_calado)):
                raise LLMFalhou(
                    f"o {self.provedor} ficou {float(desistir_calado):.0f}s sem "
                    "escrever e sem oferecer 'Responder agora'; desisto antes "
                    f"do prazo de {timeout:.0f}s.")
            escrevendo = sel.encontrar(self.page, self.sel["parar"],
                                       timeout=0.3) is not None
            if (calado and not escrevendo
                    and time.monotonic() - inicio >= devolvido_apos
                    and self._envio_devolvido()):
                if not diagnosticado:
                    self._diagnosticar_calado()
                raise LLMFalhou(
                    f"o envio voltou para a caixa de texto do {self.provedor} "
                    "sem resposta comecar (a pagina voltou ao inicio, e o anexo "
                    "sumiu): a pergunta nao foi recebida.")
            # ENVIO PELA METADE: desiste em ~20 s em vez de gastar os 600 s,
            # porque quem chama pode reenviar na hora (15/09/2026).
            if (calado and not escrevendo
                    and time.monotonic() - inicio >= devolvido_apos
                    and self._envio_truncado()):
                if not diagnosticado:
                    self._diagnosticar_calado()
                raise EnvioTruncado(
                    f"so um pedaco do prompt virou mensagem no {self.provedor}: "
                    "o fim dele continua na caixa de texto.")
            if len(texto) != ultimo_tamanho:
                ultimo_tamanho = len(texto)
                parado_desde = None
            elif not escrevendo and texto.strip():
                parado_desde = parado_desde or time.monotonic()
                # Texto parado com a imagem ainda a caminho ("Aqui esta o seu
                # gato" + a previa nitidando): quem fecha e o ramo da imagem,
                # quando ela for a final e estavel.
                imagem_a_caminho = procura_imagem and (
                    bool(prontas) or (achado.get("gerando") and len(texto.strip()) < 300))
                if (time.monotonic() - parado_desde >= estabilidade
                        and not imagem_a_caminho):
                    decorrido = time.monotonic() - inicio
                    self.log(f"[{self.provedor}] resposta pronta: "
                             f"{len(texto)} chars em {decorrido:.0f}s")
                    self._ultima_resposta = texto
                    self.imagens_na_resposta = []
                    return texto
            decorrido = time.monotonic() - inicio
            if decorrido - ultimo_aviso >= 20:
                ultimo_aviso = decorrido
                self.log(f"[{self.provedor}] escrevendo... {decorrido:.0f}s "
                         f"({ultimo_tamanho} chars)", )
            time.sleep(1.0)

        texto = self._resposta_nova()
        if procura_imagem:
            # no estouro, a MESMA regua: so a imagem final, fora de geracao
            achado = self.imagens_da_resposta()
            ainda_gerando = (achado.get("gerando") or sel.encontrar(
                self.page, self.sel["parar"], timeout=0.3) is not None)
            self.imagens_na_resposta = ([] if ainda_gerando
                                        else self.imagens_prontas(achado, ja_na_tela))
        if texto.strip() or self.imagens_na_resposta:
            self.log(f"[{self.provedor}] espera estourou em {timeout:.0f}s; "
                     "uso o que ja veio.")
            self._ultima_resposta = texto
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
                self._esperar_subir(fim, espera)
                self.log(f"[{self.provedor}] {len(arquivos)} anexo(s) "
                         "confirmado(s) na tela.")
                return len(arquivos)
            time.sleep(0.6)

        agora = self._provas_de_anexo()
        if agora > antes:
            self._esperar_subir(time.monotonic() + 10.0, espera)
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

    def _esperar_subir(self, fim: float, espera: float) -> None:
        """Espera o site dizer que o upload TERMINOU (`anexo_subindo` some).

        So para quem tem o seletor (o DeepSeek, desde 29/09/2026): la a
        miniatura aparece em 0,07 s e o arquivo de 3,2 MB so termina em
        2,8 s — o botao de enviar fica desabilitado nesse intervalo, e mandar
        o prompt ali e clicar num botao morto. Os outros sites seguem com a
        miniatura como prova, sem espera nova.
        """
        candidatos = self.sel.get("anexo_subindo") or []
        if not candidatos:
            return
        while sel.encontrar(self.page, candidatos, timeout=0) is not None:
            if time.monotonic() >= fim:
                raise LLMFalhou(
                    f"a miniatura do anexo apareceu no {self.provedor}, mas o "
                    f"arquivo nao terminou de subir em {espera:.0f}s (o botao "
                    "de enviar continua desabilitado). Arquivo grande demais "
                    "para a conta, ou o site recusou o formato.")
            time.sleep(0.5)

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
        """Um turno completo: anexa (se houver), envia, espera, devolve.

        Cada turno vai ao DIARIO (17/09/2026): sem isso a Vila nao via o
        Gemini, o ChatGPT nem o DeepSeek trabalhando. So o papel, a ref e o
        tamanho — nunca o texto do prompt. Falha de turno e `aviso`, e nao
        `erro`: fecha o "trabalhando" sem virar alerta no Telegram nem abrir
        apuracao (quem decide o que fazer com a falha e quem chamou).
        """
        comeco = time.monotonic()
        ClienteLLM._registrar_turno(self, "inicio", "turno")
        try:
            texto = ClienteLLM._perguntar(self, prompt, timeout, anexos)
        except Exception as exc:
            seguidas = ClienteLLM._falhas_seguidas(self) + 1
            # A MESMA FALHA REPETIDA VIRA UM ERRO (login caido, conta
            # travada): so com aviso, ninguem ficaria sabendo.
            status = "erro" if seguidas == FALHAS_PARA_ERRO else "aviso"
            ClienteLLM._registrar_turno(
                self, status, f"turno falhou ({seguidas} seguida(s)): "
                f"{type(exc).__name__}: {str(exc)[:120]}",
                time.monotonic() - comeco)
            raise
        if (getattr(self, "sel", None) or {}).get("limpar_resposta"):
            from .texto import limpar_resposta
            texto = limpar_resposta(texto)
        ClienteLLM._registrar_turno(self, "ok", f"{len(texto)} chars",
                                    time.monotonic() - comeco)
        return texto

    def _falhas_seguidas(self) -> int:
        """Quantos turnos deste provedor falharam em seguida, pelo diario.

        Pelo DIARIO e nao por contador em memoria: cada rodada e um processo
        novo, e o login caido aparece como uma falha por rodada.
        """
        if not getattr(self, "diario", False):
            return 0
        try:
            eventos = _rb_atividade.recentes(80, fabrica=self.provedor)
        except Exception:                                      # noqa: BLE001
            return 0
        conta = 0
        for evento in eventos:
            if not str(evento.get("etapa") or "").startswith("llm."):
                continue
            status = evento.get("status")
            if status == "inicio":
                continue
            if status in ("aviso", "erro") and "turno falhou" in str(
                    evento.get("detalhe") or ""):
                conta += 1
                continue
            break
        return conta

    def _registrar_turno(self, status: str, detalhe: str,
                         dur_s: float | None = None) -> None:
        if not getattr(self, "diario", False):
            return
        try:
            papel = getattr(self, "papel", "") or "turno"
            _rb_atividade.registrar(
                self.provedor, status, f"{papel}: {detalhe}",
                getattr(self, "canal", "") or "historias",
                etapa=f"llm.{papel}", ref=str(getattr(self, "ref", "") or ""),
                dur_s=dur_s)
        except Exception:                                      # noqa: BLE001
            pass

    def _perguntar(self, prompt: str, timeout: float | None, anexos) -> str:
        if anexos:
            self.anexar(anexos)
            _pausa(self.rng, 0.4, 1.0)
        self.enviar(prompt)
        _pausa(self.rng, 0.5, 1.2)
        try:
            return self.esperar_resposta(timeout)
        except EnvioTruncado as exc:
            # SO SEM ANEXO. Reenviar um prompt que dependia de um video sem
            # reanexar o video e pior do que falhar: a resposta viria sobre
            # nada. Com anexo, quem chama decide (o parecer tem reserva).
            if anexos:
                raise
            self.log(f"[{self.provedor}] {exc} Reenvio uma vez — `enviar` "
                     "limpa a caixa antes de colar.")
            self.enviar(prompt)
            _pausa(self.rng, 0.5, 1.2)
            return self.esperar_resposta(timeout)


class ContaOcupada(LLMFalhou):
    """A conta esta com outro processo. E diferente de "deu erro": quem
    chama pode tentar OUTRO provedor em vez de desistir do turno."""


def abrir_cliente(provedor: str, *, headless: bool = False,
                  ajustes: dict | None = None, esperar: float = 10.0,
                  log=print, papel: str = "", ref: str = "",
                  canal: str = "historias"):
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
                cliente = ClienteLLM(provedor, ctx, page, ajustes, log=log)
                cliente.diario = True
                cliente.papel, cliente.ref, cliente.canal = papel, ref, canal
                yield cliente

    return _abrir()
