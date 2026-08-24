"""DigenClient: prompt -> video renderizado -> mp4 no disco.

O fluxo segue o que o Digen realmente faz (levantado do DOM em 22/08/2026):

  1. `/en/space` — o composer mora na propria pagina de Spaces.
  2. **New Space** — reseta para um espaco LIMPO. Clicar nao navega; ele so
     zera o composer. Isso e o que torna a espera confiavel: um espaco novo tem
     ZERO videos, entao o primeiro video que aparecer e o nosso. Sem isso a
     automacao teria que adivinhar qual dos N videos do usuario e o dela.
  3. Prompt no contenteditable (`role=textbox`), colado de uma vez.
  4. `button.submit-btn` — fica `disabled` enquanto o prompt esta vazio; ele
     habilitar e a confirmacao de que o texto entrou.

Interface estreita de proposito. Se o Digen publicar uma API estavel, e so
trocar o corpo destes metodos: fila, prompt, timeline e renderer nao ficam
sabendo.
"""
from __future__ import annotations

import random
import time
from pathlib import Path

from . import selectors
from .browser import escrever, esperar_hidratacao, pausa_humana


class GeracaoFalhou(RuntimeError):
    """O Digen recusou ou falhou: gerar de novo e o caminho."""


class EsperaEstourou(GeracaoFalhou):
    """Acabou o tempo, mas o video PODE estar so na fila.

    Diferente de `GeracaoFalhou` porque a resposta certa e outra: retomar o
    mesmo espaco depois, nao pedir um video novo.
    """


class BrowserMorreu(EsperaEstourou):
    """O Chrome caiu no meio da espera.

    Herda de `EsperaEstourou` de proposito: o browser morrer nao cancela o
    render, que segue acontecendo nos servidores do Digen. A resposta certa e a
    mesma — guardar o espaco e retomar depois — e NAO gerar outro video.
    """


# Frases que o Playwright/patchright usa quando o ALVO morreu de verdade.
# Tudo que nao casa com isto e transitorio (contexto destruido por navegacao,
# elemento removido no meio, re-render) e nao deve derrubar a rodada.
_MORTE = (
    "target page, context or browser has been closed",
    "target closed",
    "browser has been closed",
    "connection closed",
    "page has been closed",
)


def _e_alvo_fechado(exc: Exception) -> bool:
    texto = str(exc).lower()
    return any(frase in texto for frase in _MORTE)


class DigenClient:
    def __init__(self, ctx, page, ajustes: dict, rng: random.Random | None = None,
                 ao_descobrir_espaco=None):
        self.ctx = ctx
        self.page = page
        self.ajustes = ajustes
        self.rng = rng or random.Random()
        self.url_do_espaco: str | None = None
        # Presets que os controles mostravam no momento do envio. O worker
        # grava isso no metadado do clipe: sem registro, "o video saiu com 3 s"
        # vira discussao em vez de consulta.
        self.presets_aplicados: dict = {}
        # Chamado assim que a URL do espaco aparece. O worker usa para gravar
        # na fila NA HORA: a navegacao para /en/space/<id> costuma acontecer
        # depois do envio, ja durante a espera, e sem isso um worker morto no
        # meio perderia o video em voo e mandaria gerar outro.
        self._ao_descobrir_espaco = ao_descobrir_espaco

    # -------------------------------------------------------------- creditos
    def creditos(self, espera: float = 30.0) -> int | None:
        """Saldo de creditos, ou None se o contador nao for legivel.

        Vale a checagem antes de enviar: sem saldo o Digen aceita o clique e so
        depois falha, o que gastaria minutos de espera por job ate estourar o
        timeout — e a fila inteira tentaria isso tres vezes por job.

        MAS o chip carrega em DUAS etapas: nos primeiros ~15 s ele mostra o
        placeholder `Free, Meme 0, Pro Meme 0` (saldo 0) e so depois vira o
        valor real (`UltraMax, Meme 3, ...`). Ler cedo demais faria o worker
        abortar por "sem creditos" com a conta cheia. Por isso: zero e tratado
        como "talvez ainda nao carregou" ate a janela de espera acabar.
        """
        fim = time.monotonic() + espera
        ultimo = None
        while time.monotonic() < fim:
            botao = selectors.encontrar(self.page, selectors.CREDITOS, timeout=2.0)
            if botao is not None:
                texto = (botao.inner_text() or "").strip()
                if texto.isdigit():
                    ultimo = int(texto)
                    if ultimo > 0:
                        return ultimo
                rotulo = botao.get_attribute("aria-label") or ""
                # Placeholder tem plano "Free" com saldo 0; conta Free de
                # verdade tambem, mas ai esperar so custa a janela inteira.
                if ultimo == 0 and not rotulo.startswith("Free"):
                    return 0
            time.sleep(2.0)
        return ultimo

    # ------------------------------------------------------------- submissao
    def novo_espaco(self) -> None:
        """Espaco limpo, para o video gerado ser o unico la dentro."""
        page = self.page
        if not page.url.startswith(selectors.URL_SPACES):
            page.goto(selectors.URL_SPACES, wait_until="domcontentloaded",
                      timeout=int(float(self.ajustes.get("navigation_timeout", 60)) * 1000))
            esperar_hidratacao(page,
                               float(self.ajustes.get("hydration_timeout", 45)))
            pausa_humana(self.rng, 1.0, 2.0)

        selectors.resolver(page, selectors.BOTAO_NOVO_ESPACO,
                           "o botao 'New Space'").click()
        pausa_humana(self.rng, 2.0, 3.5)

        self._limpar_composer()
        print("[digen] espaco novo pronto (composer limpo).")

    def _limpar_composer(self) -> None:
        """Zera o campo de prompt. Sem isso o texto gruda no anterior."""
        campo = selectors.resolver(self.page, selectors.CAMPO_PROMPT,
                                   "o campo de prompt")
        if (campo.inner_text() or "").strip():
            campo.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            pausa_humana(self.rng, 0.3, 0.8)

    def preparar_espaco(self, espaco: str | None) -> list[str]:
        """Deixa a pagina pronta para receber o prompt e fotografa o que ja existe.

        Com `espaco`, os tres clipes da geracao nascem no MESMO espaco: menos
        navegacao, menos espacos soltos na conta, e o espaco vira o dossie
        daquela build — personagem, arma e os dois juntos, lado a lado.

        O espaco so e reaproveitado se der para DISTINGUIR os videos que ja
        estao la (miniatura presente e diferente uma da outra). Se nao der,
        este clipe ganha um espaco novo: perder a companhia dos outros dois e
        melhor do que arriscar baixar o video errado.
        """
        if espaco:
            self.abrir_espaco(espaco)
            fotos = selectors.cards_prontos(self.page)
            if self._distinguiveis(fotos):
                self._limpar_composer()
                print(f"[digen] reaproveitando o espaco "
                      f"({len(fotos)} video(s) la dentro).")
                return fotos
            print("[digen] nao da para distinguir os videos deste espaco; "
                  "abrindo um novo para nao baixar o clipe errado.")
        self.novo_espaco()
        return selectors.cards_prontos(self.page)

    @staticmethod
    def _distinguiveis(fotos: list[str]) -> bool:
        """Espaco vazio serve; com video dentro, cada um precisa de marca propria."""
        return all(fotos) and len(set(fotos)) == len(fotos)

    @staticmethod
    def _canonico(texto: str, conhecidos) -> str | None:
        """O nome catalogado que corresponde ao que o botao MOSTRA.

        Compara sem espaco e sem caixa: o pill mostra "720p" e o catalogo tem
        "720P", e a igualdade literal devolvia None — o que fazia o controle
        parecer inexistente e a resolucao nunca ser ajustada. Mesmo defeito do
        "Kling3.0" contra "Kling 3.0".
        """
        alvo = "".join((texto or "").split()).lower()
        if not alvo:
            return None
        for conhecido in conhecidos:
            if "".join(conhecido.split()).lower() == alvo:
                return conhecido
        return None

    def _valor_do_controle(self, candidatos, conhecidos) -> str | None:
        """Valor atual mostrado no proprio botao do rodape."""
        botao = selectors.encontrar(self.page, candidatos, timeout=2.0)
        if botao is None:
            return None
        return self._canonico(botao.inner_text() or "", conhecidos)

    @staticmethod
    def _preferencias(valor) -> list[str]:
        """Config aceita string ("max", "5s") ou lista em ordem de desejo."""
        if valor is None:
            return []
        if isinstance(valor, str):
            return [valor] if valor else []
        return [str(v) for v in valor if v]

    def _ajustar_controle(self, nome: str, candidatos, conhecidos,
                          preferencias) -> str | None:
        """Ajusta um pill do rodape (proporcao, duracao, resolucao).

        `preferencias` e uma lista em ordem de desejo — cada modelo oferece um
        conjunto diferente (o RM3.5 so tem 480P; o RM3.2 tinha 720P), entao
        valor fixo viraria aviso eterno pedindo algo que aquele modelo nao tem.

        O valor especial `"max"` le o menu aberto e pega o MAIOR numericamente.
        E o certo para "sempre o maximo possivel": funciona tambem em modelo
        novo que ofereca um valor que ninguem catalogou aqui.

        O botao e gatilho de POPOVER: clicar abre menu, nao alterna valor —
        entao fechamos com Escape se nada casar, senao o popover fica por cima
        do botao de enviar.
        """
        preferencias = self._preferencias(preferencias)
        if not preferencias:
            return None
        atual = self._valor_do_controle(candidatos, conhecidos)
        if atual is None:
            print(f"[digen] controle de {nome} nao encontrado; "
                  f"seguindo com o padrao do modelo.")
            return None
        quer_maximo = preferencias[0] == selectors.MAXIMO
        tem_maximo = selectors.MAXIMO in preferencias
        if not quer_maximo and atual == preferencias[0]:
            print(f"[digen] {nome} ja em {atual}.")
            return atual

        selectors.encontrar(self.page, candidatos, timeout=2.0).click()
        pausa_humana(self.rng, 0.5, 1.2)

        # "max" vale em QUALQUER posicao da lista de desejo: ele e resolvido
        # para a maior opcao do menu na hora, no lugar onde estava. Antes so a
        # primeira posicao era tratada, e um "max" no fim da lista virava
        # silenciosamente um texto de menu que nao existe.
        if tem_maximo:
            maior = selectors.maior_opcao(self.page, conhecidos)
            if maior is None:
                if quer_maximo:
                    self.page.keyboard.press("Escape")
                    print(f"[digen] nao consegui ler as opcoes de {nome}; "
                          f"ficando em {atual}.")
                    return atual
                preferencias = [p for p in preferencias
                                if p != selectors.MAXIMO]
            else:
                if quer_maximo and maior == atual:
                    self.page.keyboard.press("Escape")
                    print(f"[digen] {nome} ja no maximo ({atual}).")
                    return atual
                trocadas = [maior if p == selectors.MAXIMO else p
                            for p in preferencias]
                vistos: set[str] = set()
                preferencias = [p for p in trocadas
                                if not (p in vistos or vistos.add(p))]
        if not preferencias:
            self.page.keyboard.press("Escape")
            return atual

        for desejado in preferencias:
            opcao = selectors.encontrar(
                self.page, selectors.opcao_de_popover(desejado), timeout=1.5)
            if opcao is None:
                continue
            novo = self._clicar_e_conferir(nome, opcao, desejado, candidatos,
                                           conhecidos)
            print(f"[digen] {nome} {atual} -> {novo}"
                  + (" (maximo do modelo)" if quer_maximo else ""))
            return novo

        self.page.keyboard.press("Escape")
        print(f"[digen] nenhuma opcao de {nome} em {preferencias} existe neste "
              f"modelo; ficando em {atual}.")
        return atual

    def _clicar_e_conferir(self, nome: str, opcao, desejado: str,
                           candidatos, conhecidos) -> str:
        """Clica na opcao e CONFERE que o controle virou de verdade.

        Mesmo motivo do modelo: um clique que caiu no item errado (ou que o
        popover engoliu) so apareceria no video pronto — 3 s onde se pediu 8,
        480P onde se pediu 720P — com a geracao ja gasta. Um reclique cobre o
        popover que fecha sozinho; duas falhas seguidas sao problema real.
        """
        novo = None
        for tentativa in (1, 2):
            opcao.click()
            pausa_humana(self.rng, 0.4, 1.0)
            novo = self._valor_do_controle(candidatos, conhecidos)
            if novo == desejado:
                return novo
            if tentativa == 2:
                break
            print(f"[digen] {nome} nao virou para {desejado!r} (ficou em "
                  f"{novo!r}); reabrindo o menu e tentando de novo.")
            botao = selectors.encontrar(self.page, candidatos, timeout=2.0)
            if botao is None:
                break
            botao.click()
            pausa_humana(self.rng, 0.5, 1.2)
            opcao = selectors.encontrar(
                self.page, selectors.opcao_de_popover(desejado), timeout=1.5)
            if opcao is None:
                break
        raise GeracaoFalhou(
            f"pedi {nome} {desejado!r} e o controle ficou em {novo!r}. Nao vou "
            "gerar com preset errado: a geracao seria gasta num clipe fora do "
            "que a edicao espera.")

    def presets_atuais(self) -> dict:
        """O que os controles do rodape mostram AGORA."""
        return {
            "modelo": self._modelo_atual(),
            "duracao": self._valor_do_controle(selectors.BOTAO_DURACAO,
                                               selectors.DURACOES_CONHECIDAS),
            "resolucao": self._valor_do_controle(selectors.BOTAO_RESOLUCAO,
                                                 selectors.RESOLUCOES_CONHECIDAS),
            "aspecto": self._aspecto_atual(),
        }

    def _conferir_presets(self) -> dict:
        """Ultima conferida antes de gastar a geracao.

        Cada `_ajustar_*` ja confere o proprio controle, mas trocar um mexe nos
        outros (o modelo reseta todos), entao o que vale e o estado final,
        lido de uma vez so, imediatamente antes do clique de enviar.
        """
        aplicados = self.presets_atuais()
        print("[digen] presets: " + ", ".join(
            f"{chave}={valor}" for chave, valor in aplicados.items()))
        aspecto = aplicados.get("aspecto")
        if aspecto and aspecto not in selectors.ASPECTOS_VERTICAIS:
            if selectors.valor_deitado(aspecto):
                raise GeracaoFalhou(
                    f"a proporcao ficou em {aspecto!r}, que e deitada. O video "
                    "da roleta e 9:16; nao vou gastar a geracao num clipe que "
                    "entraria com tarja dos dois lados.")
            print(f"[digen] AVISO: proporcao em {aspecto!r} (nao e uma das "
                  f"verticais {selectors.ASPECTOS_VERTICAIS}).")
        self.presets_aplicados = aplicados
        return aplicados

    def _aspecto_atual(self) -> str | None:
        return self._valor_do_controle(selectors.BOTAO_ASPECTO,
                                       selectors.ASPECTOS_CONHECIDOS)

    def _ajustar_aspecto(self, aspect: str) -> None:
        """Sempre em pe: os fallbacks tambem sao verticais.

        `"max"` nao existe aqui de proposito — proporcao nao tem "maior", e o
        maior numero do menu seria 21:9, que e paisagem deitada.
        """
        preferencias = self._preferencias(aspect)
        for vertical in selectors.ASPECTOS_VERTICAIS:
            if vertical not in preferencias:
                preferencias.append(vertical)
        self._ajustar_controle("proporcao", selectors.BOTAO_ASPECTO,
                               selectors.ASPECTOS_CONHECIDOS, preferencias)

    def _ajustar_duracao(self, preferencias) -> None:
        self._ajustar_controle("duracao", selectors.BOTAO_DURACAO,
                               selectors.DURACOES_CONHECIDAS, preferencias)

    def _ajustar_resolucao(self, preferencias) -> None:
        self._ajustar_controle("resolucao", selectors.BOTAO_RESOLUCAO,
                               selectors.RESOLUCOES_CONHECIDAS, preferencias)

    @staticmethod
    def _mesmo_modelo(a: str | None, b: str | None) -> bool:
        """Compara nome de modelo ignorando espacos e caixa.

        O menu lista "Kling 3.0" e o botao mostra "Kling3.0" — sem o espaco.
        Comparar literal fazia a conferencia falhar DEPOIS de uma troca que
        deu certo, e o job caia repetindo "ficou em None"/"nao esta no menu"
        com o modelo ja correto na tela.
        """
        if a is None or b is None:
            return False
        return "".join(a.split()).lower() == "".join(b.split()).lower()

    def _modelo_atual(self) -> str | None:
        """Texto do botao de modelo (abreviado: "RM3.2"), ou None."""
        botao = selectors.encontrar(self.page, selectors.BOTAO_MODELO, timeout=2.0)
        if botao is None:
            return None
        return " ".join((botao.inner_text() or "").split()) or None

    def _ajustar_modelo(self, modelo: str) -> None:
        """Troca o modelo de geracao, com match EXATO no menu.

        Por que exato: "Real Motion 3.5 Turbo" aparece ANTES de "Real Motion
        3.5" na lista. Busca por substring (`has-text`) selecionaria o Turbo
        silenciosamente — e o video sairia de outro modelo sem ninguem notar.

        Falha e dura de proposito: gerar com o modelo errado gasta uma geracao
        e entrega um clipe que nao e o pedido. Melhor o job falhar dizendo o
        motivo.
        """
        if not modelo:
            return
        permitidos = self.ajustes.get("modelos_permitidos") or []
        if permitidos and modelo not in permitidos:
            # Recusa ANTES de gastar: o menu mistura o modelo incluso com
            # modelos cobrados por geracao, e escolher errado custa dinheiro.
            raise GeracaoFalhou(
                f"o modelo {modelo!r} nao esta na lista branca "
                f"(`modelos_permitidos` em config/identity.json). "
                f"Permitidos: {', '.join(permitidos[:4])}...")
        esperado = selectors.abreviar_modelo(modelo)
        atual = self._modelo_atual()
        if self._mesmo_modelo(atual, esperado):
            print(f"[digen] modelo ja em {modelo} ({atual}).")
            return
        if atual is None:
            raise GeracaoFalhou(
                "nao achei o botao de modelo no composer. Rode "
                "`python main.py identity doctor --online`.")

        selectors.resolver(self.page, selectors.BOTAO_MODELO,
                           "o botao de modelo").click()
        pausa_humana(self.rng, 0.6, 1.4)

        opcao = selectors.encontrar(self.page, selectors.opcao_de_modelo(modelo),
                                    timeout=3.0)
        if opcao is None:
            self.page.keyboard.press("Escape")
            raise GeracaoFalhou(
                f"o modelo {modelo!r} nao esta no menu do Digen. Conhecidos: "
                f"{', '.join(selectors.MODELOS_CONHECIDOS[:6])}...")
        opcao.click()
        pausa_humana(self.rng, 0.6, 1.4)

        # Conferir e obrigatorio: um clique que caiu no item errado (ou nao
        # registrou) so apareceria depois, no video pronto.
        virou = self._modelo_atual()
        if not self._mesmo_modelo(virou, esperado):
            raise GeracaoFalhou(
                f"pedi {modelo!r} (esperava o botao mostrar {esperado!r}) mas "
                f"ele ficou em {virou!r}. Nao vou gerar com o modelo errado.")
        print(f"[digen] modelo {atual} -> {virou}")

    def anexar_referencias(self, caminhos) -> list:
        """Anexa as imagens de referencia. NUNCA levanta.

        Devolve o que CONSEGUIU anexar — possivelmente nada. Quem chama decide
        o texto do prompt a partir disso: hoje esse video sai, e fazer o payoff
        falhar por causa de um controle de upload que pode nao existir seria
        trocar um video imperfeito por nenhum video.

        Roda depois do espaco pronto e ANTES de escrever o prompt e de clicar
        em enviar: falhar aqui custa zero credito.
        """
        if not caminhos:
            return []
        ajustes_ref = self.ajustes.get("referencias") or {}
        if not ajustes_ref.get("habilitado", True):
            print("[digen] anexo de referencia desligado no config.")
            return []
        from . import referencias, selectors as sel
        prontos = [referencias.para_upload(Path(c)) for c in caminhos]
        anexadas = referencias.anexar(self.page, prontos, sel, self.rng)
        if anexadas:
            print(f"[digen] {len(anexadas)} referencia(s) anexada(s): "
                  + ", ".join(Path(a).name for a in anexadas))
        else:
            print("[digen] nenhuma referencia anexada; o prompt vai carregar "
                  "as duas identidades por escrito.")
        return anexadas

    def submit_prompt(self, prompt: str, aspect: str = "9:16",
                      modelo: str | None = None, duracao=None,
                      resolucao=None, espaco: str | None = None,
                      antes: list[str] | None = None) -> list[str]:
        """Envia o prompt e devolve a FOTO dos cards que ja existiam no espaco.

        A foto e o que permite reconhecer o video novo depois: com os tres
        clipes no mesmo espaco, "o primeiro botao de download da tela" nao e
        mais o nosso.
        """
        page = self.page
        # `antes` ja preenchido = o espaco foi preparado por quem chamou (o
        # worker prepara antes para poder ANEXAR e so entao decidir o texto).
        # Preparar de novo aqui limparia o composer e perderia o anexo.
        if antes is None:
            antes = self.preparar_espaco(espaco)

        campo = selectors.resolver(page, selectors.CAMPO_PROMPT,
                                   "o campo de prompt")
        escrever(page, campo, prompt, self.rng)

        botao = selectors.resolver(page, selectors.BOTAO_GERAR,
                                   "o botao de enviar (submit-btn)")
        # O submit so habilita quando o texto entrou de verdade: esperar por
        # isso vale mais que qualquer assert no conteudo do contenteditable.
        limite = time.monotonic() + 20
        while botao.is_disabled() and time.monotonic() < limite:
            time.sleep(0.5)
        if botao.is_disabled():
            raise GeracaoFalhou(
                "o botao de enviar continuou desabilitado: o prompt nao entrou "
                "no campo. Rode `python main.py identity probe` para conferir "
                "o seletor do contenteditable.")

        # ORDEM IMPORTA: trocar o modelo RESETA os outros controles para os
        # padroes dele (visto em 22/08: RM3.2 -> RM3.5 derrubou 5s para 3s,
        # 9:16 para Auto e 720P para 480P). Modelo primeiro, resto depois.
        self._ajustar_modelo(modelo or self.ajustes.get("modelo", ""))
        self._ajustar_duracao(duracao if duracao is not None
                              else self.ajustes.get("duracao"))
        self._ajustar_resolucao(resolucao if resolucao is not None
                                else self.ajustes.get("resolucao"))
        self._ajustar_aspecto(aspect)
        self._conferir_presets()
        pausa_humana(self.rng)
        botao.click()

        # O app so navega para /en/space/<id> alguns segundos depois do clique;
        # ler `page.url` na hora devolvia ainda /en/space.
        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            if "/space/" in page.url:
                break
            time.sleep(1.0)
        self.url_do_espaco = page.url
        print(f"[digen] prompt enviado ({len(prompt)} chars) -> {self.url_do_espaco}")
        return antes

    def abrir_espaco(self, url: str) -> None:
        """Volta para um espaco ja criado, sem enviar nada.

        E o caminho de RETOMADA: o video daquele espaco pode ainda estar na
        fila do Digen, e reenviar o prompt so faria um segundo video do mesmo
        personagem.
        """
        self.url_do_espaco = url
        if self.page.url != url:
            self.page.goto(url, wait_until="domcontentloaded",
                           timeout=int(float(
                               self.ajustes.get("navigation_timeout", 60)) * 1000))
            # Deep-link hidrata devagar: sem esperar, os seletores do card
            # simplesmente "nao existem" e a retomada parece falha.
            esperar_hidratacao(self.page,
                               float(self.ajustes.get("hydration_timeout", 45)))
            pausa_humana(self.rng, 1.0, 2.0)
        print(f"[digen] retomando {url}")

    def _anotar_espaco(self) -> None:
        """Guarda a URL do espaco assim que ela aparecer.

        A navegacao para /en/space/<id> as vezes demora mais que a janela pos
        clique, entao vale continuar olhando durante a espera. Na primeira vez
        que aparece, avisa quem pediu para ser avisado (o worker persiste na
        fila) — assim o video em voo sobrevive ate a um kill -9.
        """
        atual = self.page.url
        if "/space/" not in atual or atual == self.url_do_espaco:
            return
        novo = self.url_do_espaco is None or "/space/" not in self.url_do_espaco
        self.url_do_espaco = atual
        if novo and self._ao_descobrir_espaco is not None:
            try:
                self._ao_descobrir_espaco(atual)
            except Exception:
                pass   # monitoramento/persistencia nao derruba a geracao

    def _checar_vivo(self) -> None:
        """Aborta se o Chrome caiu, em vez de esperar o timeout inteiro.

        `selectors.encontrar` engole toda excecao por candidato — o que e certo
        para "esse seletor nao existe nesta tela", mas faz uma pagina MORTA
        parecer identica a "ainda nao ficou pronto". Sem esta checagem o worker
        fica meia hora consultando um browser que nao existe mais (visto em
        22/08: Chrome caiu aos ~5 min e a espera seguiu ate o timeout).

        MAS so conta como morte o que e mesmo morte. Numa SPA, `evaluate` falha
        de forma TRANSITORIA o tempo todo — "Execution context was destroyed"
        acontece a cada re-render/navegacao do Digen. Tratar isso como browser
        morto derrubava a rodada logo depois de `abrir_espaco`, e o worker em
        `--watch` virava um ciclo de abrir e fechar o Chrome a cada ~50 s.
        """
        if self.page.is_closed():
            raise BrowserMorreu("a aba do Chrome foi fechada durante a espera.")
        try:
            self.page.evaluate("1")     # so uma chamada real acusa o alvo morto
        except Exception as exc:
            if not _e_alvo_fechado(exc):
                return              # transitorio: o proximo ciclo tenta de novo
            raise BrowserMorreu(
                f"o Chrome caiu durante a espera ({type(exc).__name__}). O video "
                f"segue sendo gerado em {self.url_do_espaco}; a proxima passada "
                "do worker retoma de la.") from exc

    # ----------------------------------------------------------------- espera
    def _indice_do_novo(self, antes: list[str]) -> int | None:
        """Indice do card que NAO estava na foto de antes do envio.

        Consome as marcas conhecidas uma a uma (e nao por conjunto): duas
        miniaturas iguais no espaco nao podem fazer o card novo desaparecer da
        conta.
        """
        agora = selectors.cards_prontos(self.page)
        if not agora:
            return None
        restantes = list(antes)
        novos = []
        for indice, marca in enumerate(agora):
            if marca in restantes:
                restantes.remove(marca)
            else:
                novos.append(indice)
        if len(novos) == 1:
            return novos[0]
        self._ambiguos = getattr(self, "_ambiguos", 0) + (1 if novos else 0)
        if self._ambiguos >= 3:
            raise GeracaoFalhou(
                f"{len(novos)} cards novos no espaco e so um video foi pedido; "
                "nao da para dizer qual e o nosso. Rode `python main.py "
                "identity probe` ou desligue `espaco_por_geracao` em "
                "config/identity.json.")
        return None

    def wait_for_render(self, timeout: float | None = None,
                        antes: list[str] | None = None) -> int:
        """Polling ate o video ficar pronto no espaco. Devolve o INDICE do card.

        Duas fases observadas no DOM: enquanto gera, o card mostra
        "Generating video ... Estimated completion: N seconds"; quando termina,
        ganha o botao de download.

        `antes` e a foto dos cards que ja existiam quando o prompt foi enviado.
        Com os tres clipes no mesmo espaco, e ela que diz qual card e o nosso —
        "o primeiro botao de download da tela" passaria a apontar para o clipe
        do personagem quando quem estivesse pronto fosse a arma.

        Erro explicito (sem credito, falha do modelo) derruba na hora: esperar
        10 minutos por algo que ja falhou so atrasa a fila.
        """
        timeout = float(timeout if timeout is not None
                        else self.ajustes.get("render_timeout", 600))
        intervalo = float(self.ajustes.get("poll_interval", 5))
        inicio = time.monotonic()
        fim = inicio + timeout
        ultimo_aviso = 0.0
        ultimo_estado = ""
        antes = list(antes or [])
        self._ambiguos = 0

        while time.monotonic() < fim:
            self._checar_vivo()
            self._anotar_espaco()
            gerando = selectors.encontrar(self.page, selectors.GERANDO, timeout=1.0)
            if gerando is None:
                # So procura o resultado quando o estado "gerando" sumiu: com o
                # card ainda em andamento o botao de download nem existe.
                indice = self._indice_do_novo(antes)
                if indice is not None:
                    print(f"[digen] render pronto (card {indice + 1}).")
                    return indice
            elif time.monotonic() - inicio > 5:
                estado = " ".join((gerando.inner_text() or "").split())[:90]
                if estado and estado != ultimo_estado:
                    ultimo_estado = estado
                    print(f"[digen] {estado}", flush=True)

            erro = selectors.encontrar(self.page, selectors.ERRO_GERACAO, timeout=1.0)
            if erro is not None:
                texto = (erro.inner_text() or "").strip()[:200]
                raise GeracaoFalhou(f"o Digen reportou erro: {texto!r}")

            decorrido = timeout - (fim - time.monotonic())
            if decorrido - ultimo_aviso >= 30:
                ultimo_aviso = decorrido
                print(f"[digen] renderizando... {decorrido:.0f}s", flush=True)
            time.sleep(intervalo)

        raise EsperaEstourou(
            f"o video nao ficou pronto em {timeout:.0f}s (ainda pode estar na "
            f"fila do Digen em {self.url_do_espaco}).")

    # --------------------------------------------------------------- download
    def _liberar_botao_de_download(self, indice: int) -> None:
        """Tira o composer da frente do botao de baixar.

        A barra flutuante do rodape (RealDance / Lip Gen) fica POR CIMA do
        botao de download do card. Com imagem anexada e texto escrito a caixa
        do composer cresce e empurra tudo, e o botao vira inalcancavel — o
        Playwright acusa "subtree intercepts pointer events" e forcar o clique
        so acerta a barra.

        A sequencia que funciona (observada na tela): tirar a imagem, apagar o
        texto, rolar um pouco e so entao passar o mouse no card.
        """
        removidas = selectors.esvaziar_composer(self.page)
        try:
            self._limpar_composer()
        except Exception:
            pass
        try:
            self.page.mouse.wheel(0, 320)
        except Exception:
            pass
        time.sleep(1.0)
        selectors.hover_no_card(self.page, indice)
        time.sleep(1.0)
        if removidas:
            print(f"[digen] composer esvaziado ({removidas} miniatura(s)) "
                  "para liberar o botao de baixar.")

    def _url_por_rede(self, indice: int, segundos: float = 15.0) -> str | None:
        """Manda o video tocar e pega a URL do mp4 que passar pela rede.

        E o caminho que sobra quando o DOM nao entrega nada: o player pode
        montar a fonte por JS ou por MSE, mas o arquivo tem que trafegar.
        """
        capturadas: list[str] = []

        def ao_responder(resposta):
            try:
                url = resposta.url
                tipo = (resposta.headers or {}).get("content-type", "")
            except Exception:
                return
            if ".mp4" in url.lower() or "video/" in tipo.lower():
                capturadas.append(url)

        self.page.on("response", ao_responder)
        try:
            selectors.acordar_video(self.page, indice)
            fim = time.monotonic() + segundos
            while time.monotonic() < fim and not capturadas:
                time.sleep(0.5)
        except Exception:
            pass
        finally:
            try:
                self.page.remove_listener("response", ao_responder)
            except Exception:
                pass
        if capturadas:
            print(f"[digen] URL do video capturada na rede "
                  f"({len(capturadas)} resposta(s) de video).")
        return capturadas[-1] if capturadas else None

    def download(self, alvo, dest: Path) -> Path:
        """Baixa o que `wait_for_render` identificou. Aqui, o INDICE do card.

        O parametro se chama `alvo` porque este e o contrato compartilhado
        entre os provedores: "baixe o que a espera devolveu". No Digen isso e
        um indice de card; no PicassoIA e a URL da imagem. Nomear diferente nos
        dois foi o que um teste de conformidade pegou — e e o tipo de
        divergencia que so aparece no dia em que alguem chama por keyword.

        Duas estrategias, nessa ordem: botao de download real, depois o src.
        A segunda usa `ctx.request`, que reusa cookies e headers da propria
        sessao do browser — por isso o projeto nao precisa de `requests`.
        """
        indice = int(alvo)
        dest.parent.mkdir(parents=True, exist_ok=True)

        self._liberar_botao_de_download(indice)
        botao = selectors.botao_download(self.page, indice)
        if botao is not None:
            # `force` porque a pagina tem uma barra flutuante (`pointer-events`
            # numa div z-30 no rodape) que INTERCEPTA o clique: o Playwright
            # recusa clicar em elemento coberto, e sem forcar o download nunca
            # comeca — o video fica pronto no site e preso la.
            for forcar in (False, True):
                try:
                    with self.page.expect_download(
                            timeout=float(self.ajustes.get("download_timeout", 120)) * 1000
                    ) as info:
                        botao.click(force=forcar, timeout=15000)
                    info.value.save_as(str(dest))
                    print(f"[digen] baixado via botao{' (forcado)' if forcar else ''}"
                          f" -> {dest}")
                    return dest
                except Exception as exc:
                    print(f"[digen] botao de download falhou"
                          f"{' mesmo forcado' if forcar else ''} "
                          f"({type(exc).__name__}: {str(exc)[:90]}).")

        # Plano B: OUVIR A REDE. O <video> do card nao tem `src` nem `<source>`
        # nem depois de tocar (verificado no DOM), entao nao existe URL para
        # ler — mas ela passa pela rede quando o player busca o arquivo. Isto
        # nao depende de nenhum seletor, que e a parte que mais quebra.
        src = self._url_por_rede(indice)
        if not src:
            src = selectors.src_do_card(self.page, indice)
        if not src:
            raise GeracaoFalhou(
                f"card {indice + 1} sem `src` e sem botao de download utilizavel.")
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = selectors.BASE_URL + src

        resposta = self.ctx.request.get(
            src, timeout=float(self.ajustes.get("download_timeout", 120)) * 1000)
        if not resposta.ok:
            raise GeracaoFalhou(f"download de {src} respondeu {resposta.status}.")
        dest.write_bytes(resposta.body())
        print(f"[digen] baixado via src -> {dest}")
        return dest
